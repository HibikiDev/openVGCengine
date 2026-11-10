









from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from vgc_trainer import i18n
from vgc_trainer.showdown.tracker import to_id
from vgc_trainer.showdown.sheets import base_format


BOTS = {"practice": {"label": "PracticeBot (local server)", "profiles": "trainer/runs/buddy_profiles.json",
                     "results": "trainer/runs/buddy_results.jsonl", "series_pages": False}}
try:
    from .team_stats import BUDDY_LIVE
    BOTS = {"live": BUDDY_LIVE, **BOTS}
except ImportError:
    pass
NOTES = "trainer/runs/buddy_notes.jsonl"
KEEP = 200


def path_for(profiles: Path | str) -> Path:
    p = Path(profiles)
    return p.with_name(p.stem + "_sessions.json")


def load(path: Path) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return []


def _save(path: Path, sessions: list[dict]) -> None:
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps(sessions[-KEEP:], indent=1), encoding="utf8")
    tmp.replace(path)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def active(path: Path, user: str) -> dict | None:
    return next((s for s in reversed(load(path)) if s["user"] == to_id(user) and not s.get("end")), None)


def start(path: Path, user: str, name: str = "") -> tuple[dict, dict | None]:

    ss, uid = load(path), to_id(user)
    closed = None
    for s in ss:
        if s["user"] == uid and not s.get("end"):
            s["end"], closed = _now(), s
    n = sum(1 for s in ss if s["user"] == uid) + 1
    new = {"user": uid, "name": name.strip()[:60] or f"session {n}", "start": _now(), "end": None}
    _save(path, ss + [new])
    return new, closed


def end(path: Path, user: str) -> dict | None:

    ss, uid = load(path), to_id(user)
    s = next((s for s in reversed(ss) if s["user"] == uid and not s.get("end")), None)
    if s is not None:
        s["end"] = _now()
        _save(path, ss)
    return s


def resume(path: Path, user: str, t0: str | None = None) -> tuple[dict | None, list[dict]]:



    ss, uid = load(path), to_id(user)
    mine = [s for s in ss if s["user"] == uid]
    s = next((x for x in mine if x["start"] == t0), None) if t0 else next((x for x in reversed(mine) if x.get("end")), None)
    if s is None:
        return None, []
    folded = [x for x in mine if x is not s and s.get("end") and x["start"] >= s["end"]]
    for x in mine:
        if x is not s and x not in folded and not x.get("end"):
            x["end"] = _now()
    s["end"] = None
    _save(path, [x for x in ss if not any(x is f for f in folded)])
    return s, folded


def delete(path: Path, user: str, t0: str) -> dict | None:
    ss, uid = load(path), to_id(user)
    s = next((x for x in ss if x["user"] == uid and x["start"] == t0), None)
    if s is not None:
        _save(path, [x for x in ss if x is not s])
    return s


_RESULTS: dict[str, tuple[float, list[dict]]] = {}


def _results(root: Path, bot: str) -> list[dict]:

    f = root / BOTS[bot]["results"]
    try:
        m = f.stat().st_mtime
    except OSError:
        return []
    if _RESULTS.get(bot, (None,))[0] != m:
        rows = []
        for ln in f.read_text(encoding="utf8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                if r.get("opponent") and not r.get("ladder"):
                    rows.append({**r, "time": r.get("time", "").replace("T", " ")})
        _RESULTS[bot] = (m, rows)
    return _RESULTS[bot][1]


def contains(s: dict, r: dict) -> bool:

    if r["room"] in s.get("rooms", []):
        return True
    return (to_id(r["opponent"]) == s["user"] and r["time"] >= s["start"] and (not s.get("end") or r["time"] <= s["end"])
            and r["room"] not in s.get("excluded", []))


def _rows(root: Path, bot: str, s: dict) -> list[dict]:

    return [r for r in _results(root, bot) if contains(s, r)]


def add_game(path: Path, user: str, t0: str, room: str) -> dict | None:

    ss = load(path)
    s = next((x for x in ss if x["user"] == to_id(user) and x["start"] == t0), None)
    if s is not None:
        s["excluded"] = [x for x in s.get("excluded", []) if x != room]
        s.setdefault("rooms", [])
        if room not in s["rooms"]:
            s["rooms"].append(room)
        _save(path, ss)
    return s


def remove_game(path: Path, user: str, t0: str, room: str) -> dict | None:

    ss = load(path)
    s = next((x for x in ss if x["user"] == to_id(user) and x["start"] == t0), None)
    if s is not None:
        s["rooms"] = [x for x in s.get("rooms", []) if x != room]
        s.setdefault("excluded", [])
        if room not in s["excluded"]:
            s["excluded"].append(room)
        _save(path, ss)
    return s


def recent_games(root: Path, n: int = 30, who: str = "") -> list[dict]:


    out = []
    for bot, cfg in BOTS.items():
        ss = load(path_for(root / cfg["profiles"]))
        rows = [r for r in _results(root, bot) if not who or to_id(r["opponent"]) == to_id(who)]
        for r in rows[-n:]:
            out.append({**r, "bot": bot, "bot_label": cfg["label"], "won": _won(r),
                        "sessions": [x for x in ss if contains(x, r)],
                        "other_sessions": [x for x in reversed(ss) if not contains(x, r)][:12]})
    return sorted(out, key=lambda r: r["time"], reverse=True)[:n]


def _won(r: dict) -> bool | None:

    return None if not r.get("winner") else to_id(r["winner"]) == to_id(r["opponent"])


def players(root: Path) -> list[tuple[str, int]]:

    c, shown = Counter(), {}
    for bot in BOTS:
        for r in _results(root, bot):
            c[to_id(r["opponent"])] += 1
            shown[to_id(r["opponent"])] = r["opponent"]
    return [(shown[u], n) for u, n in c.most_common()]


def listing(root: Path) -> list[dict]:

    out = []
    for bot, cfg in BOTS.items():
        for s in load(path_for(root / cfg["profiles"])):
            rows = _rows(root, bot, s)
            w = sum(1 for r in rows if _won(r))
            out.append({**s, "bot": bot, "bot_label": cfg["label"], "games": len(rows), "wins": w,
                        "losses": sum(1 for r in rows if _won(r) is False)})
    return sorted(out, key=lambda s: s["start"], reverse=True)


def _pair(x: list[str]) -> str:
    return " + ".join(sorted(x))


def detail(root: Path, bot: str, user: str, t0: str) -> dict | None:

    from .game_views import _game_dir, parse_game
    cfg = BOTS.get(bot)
    s = next((x for x in load(path_for(root / cfg["profiles"])) if x["user"] == to_id(user) and x["start"] == t0), None) if cfg else None
    if s is None:
        return None
    rows = _rows(root, bot, s)
    notes = {}
    try:
        for ln in (root / NOTES).read_text(encoding="utf8").splitlines():
            if ln.strip():
                n = json.loads(ln)
                notes[n.get("room")] = n.get("notes")
    except OSError:
        pass
    games, per_side = [], {"you": [], "bot": []}
    leads, bot_leads, mons, teams = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for r in rows:
        g = parse_game(_game_dir(r["room"]) / f"{r['room']}.log") or {}
        won = _won(r)
        try:
            lines = (_game_dir(r["room"]) / f"{r['room']}.log").read_text(encoding="utf8", errors="replace").splitlines()
        except OSError:
            lines = []
        seat = next((ln.split("|")[2] for ln in lines if ln.startswith("|player|") and len(ln.split("|")) > 3
                     and to_id(ln.split("|")[3]) == to_id(r["opponent"])), None)
        if seat and won is not None:
            per_side["you"].append((lines, seat, won))
            per_side["bot"].append((lines, "p2" if seat == "p1" else "p1", won))
        x = {"room": r["room"], "time": r["time"][11:16] if r["time"][:10] == s["start"][:10] else r["time"][5:16], "series": r.get("series"), "game": r.get("game"), "won": won,
             "turns": r.get("turns"), "your_lead": g.get("foe_lead") or [], "your_four": g.get("foe_shown") or [],
             "bot_lead": g.get("my_lead") or [], "bot_four": g.get("my_bring") or [], "bot_six": g.get("my_six") or [],
             "your_six": g.get("foe_sheet") or [], "format": base_format(r["room"].split("-")[1]) if "-" in r["room"] else "",
             "notes": notes.get(r["room"]), "seat": seat}
        games.append(x)
        if won is None:
            continue
        if x["your_lead"]:
            leads[_pair(x["your_lead"])].append(won)
        if x["bot_lead"]:
            bot_leads[_pair(x["bot_lead"])].append(won)
        for m in x["your_four"]:
            mons[m].append(won)
        if x["bot_six"]:
            teams[" · ".join(x["bot_six"])].append(won)
    series = []
    for x in games:
        if x["series"] and series and series[-1]["id"] == x["series"]:
            series[-1]["games"].append(x)
        else:
            series.append({"id": x["series"], "games": [x]})
    for sr in series:
        w = sum(1 for g in sr["games"] if g["won"])
        lo = sum(1 for g in sr["games"] if g["won"] is False)
        sr.update(wins=w, losses=lo, bo3=bool(sr["id"]), won=(w >= 2) if sr["id"] and max(w, lo) >= 2 else None)
    tab = lambda d: sorted(({"key": k, "n": len(v), "wins": sum(v), "rate": sum(v) / len(v)} for k, v in d.items()),
                           key=lambda e: (-e["n"], e["key"]))
    done = [g for g in games if g["won"] is not None]
    bo3 = [sr for sr in series if sr["won"] is not None]
    return {**s, "bot": bot, "bot_label": cfg["label"], "series_pages": cfg["series_pages"], "series": series,
            "games": len(games), "wins": sum(1 for g in done if g["won"]), "losses": sum(1 for g in done if not g["won"]),
            "series_won": sum(1 for sr in bo3 if sr["won"]), "series_lost": sum(1 for sr in bo3 if not sr["won"]),
            "turns": round(sum(g["turns"] or 0 for g in done) / len(done), 1) if done else None,
            "your_leads": tab(leads), "your_mons": tab(mons), "bot_leads": tab(bot_leads), "bot_teams": tab(teams),
            "your_sixes": Counter(" · ".join(g["your_six"]) for g in games if g["your_six"]).most_common(),
            "your_side": side_stats(per_side["you"]), "bot_side": side_stats(per_side["bot"])}


def _game_sides(lines: list[str]) -> dict:



    sheet = {"p1": [], "p2": []}
    for ln in lines:
        q = ln.split("|")
        if len(q) > 3 and q[1] == "poke":
            sheet[q[2]].append(q[3].split(",")[0])

    def base(side: str, sp: str) -> str:
        sp = sp.split("-Mega")[0]
        return next((s for s in sheet[side] if sp == s), None) or next((s for s in sheet[side] if sp.startswith(s + "-") or s.startswith(sp + "-")), sp)

    out = {s: defaultdict(lambda: {"led": False, "fainted": False, "mega": False, "moves": Counter(), "targets": defaultdict(Counter),
                                   "switch": 0, "kos": Counter()}) for s in ("p1", "p2")}
    at: dict[str, str] = {}
    turn, last_hit, pending, actor = 0, {}, None, None
    for ln in lines:
        q = ln.split("|")
        if len(q) < 3:
            continue
        k = q[1]
        if k == "turn":
            turn, pending, actor = int(q[2]), None, None
        elif k in ("switch", "drag", "replace") and len(q) > 3:
            pos, side = q[2][:3], q[2][:2]
            sp = base(side, q[3].split(",")[0])
            if k == "switch" and turn > 0 and pos in at and not out[side][at[pos]]["fainted"]:
                out[side][at[pos]]["switch"] += 1
            at[pos] = sp
            m = out[side][sp]
            if turn == 0:
                m["led"] = True
        elif (k == "detailschange" and len(q) > 3 and "-Mega" in q[3]) or k == "-mega":
            if q[2][:3] in at:
                out[q[2][:2]][at[q[2][:3]]]["mega"] = True
        elif k == "move" and len(q) > 3 and q[2][:3] in at:
            side, me = q[2][:2], at[q[2][:3]]
            mv, tgt, rest = q[3], q[4] if len(q) > 4 else "", "|".join(q[5:])
            out[side][me]["moves"][mv] += 1
            pending = None
            if "[spread]" in rest:
                label = "spread"
            elif tgt and tgt[:3] in at:
                label = "no target" if tgt[:3] == q[2][:3] else ("ally " if tgt[:2] == side else "") + at[tgt[:3]]
            else:
                label, pending = None, (side, me, mv)
            if label:
                out[side][me]["targets"][mv][label] += 1
            actor = (side, me)
        elif k == "-damage" and len(q) > 3 and q[2][:3] in at and "[from]" not in "|".join(q[4:]):
            tside, tmon = q[2][:2], at[q[2][:3]]
            if pending is not None:
                side, me, mv = pending
                out[side][me]["targets"][mv][("ally " if tside == side else "") + tmon] += 1
                actor, pending = (side, me), None
            last_hit[q[2][:3]] = (turn, actor)
        elif k == "faint" and q[2][:3] in at:
            side, mon = q[2][:2], at[q[2][:3]]
            out[side][mon]["fainted"] = True
            hit = last_hit.get(q[2][:3])
            if hit and hit[0] == turn and hit[1] and hit[1][0] != side:
                out[hit[1][0]][hit[1][1]]["kos"][mon] += 1
    for side in ("p1", "p2"):
        for m in out[side].values():
            for mv, n in m["moves"].items():
                short = n - sum(m["targets"][mv].values())
                if short > 0:
                    m["targets"][mv]["no target"] += short
    return {"sheet": sheet, "sides": out}


def side_stats(games: list[tuple[list[str], str, bool | None]]) -> list[dict]:




    agg = defaultdict(lambda: {"sheet": 0, "brought": 0, "led": 0, "fainted": 0, "mega": 0, "won": 0.0, "moves": Counter(),
                               "used": Counter(), "targets": defaultdict(Counter), "switch": 0, "kos": Counter()})
    for lines, side, won in games:
        g = _game_sides(lines)
        for sp in dict.fromkeys(g["sheet"][side]):
            agg[sp]["sheet"] += 1
        for sp, m in g["sides"][side].items():
            a = agg[sp]
            a["brought"] += 1
            a["led"] += m["led"]
            a["fainted"] += m["fainted"]
            a["mega"] += m["mega"]
            a["won"] += 1.0 if won else 0.0
            a["moves"].update(m["moves"])
            a["used"].update(set(m["moves"]))
            for mv, t in m["targets"].items():
                a["targets"][mv].update(t)
            a["switch"] += m["switch"]
            a["kos"].update(m["kos"])
    rows = []
    for sp, a in agg.items():
        nb, dec = a["brought"], sum(a["moves"].values()) + a["switch"]
        moves = []
        for mv, n in a["moves"].most_common():
            tot = sum(a["targets"][mv].values()) or 1
            moves.append({"move": mv, "share": round(n / max(dec, 1), 3), "games": round(a["used"][mv] / max(nb, 1), 3),
                          "targets": [{"to": t, "share": round(c / tot, 3)} for t, c in a["targets"][mv].most_common() if c / tot >= 0.05]})
        rows.append({"mon": sp, "sub": i18n.t("on the sheet in {k} of {n} games", k=a['sheet'], n=len(games)) if a["sheet"] < len(games) else None,
                     "brought": round(nb / max(a["sheet"], 1), 3), "led": round(a["led"] / max(a["sheet"], 1), 3),
                     "fainted": round(a["fainted"] / nb, 3) if nb else None, "mega": round(a["mega"] / nb, 3) if nb and a["mega"] else None,
                     "score_when_brought": round(a["won"] / nb, 3) if nb else None, "decisions": dec, "moves": moves,
                     "switch": round(a["switch"] / max(dec, 1), 3),
                     "kos": round(sum(a["kos"].values()) / nb, 2) if nb else None,
                     "ko_list": [{"victim": v, "per_game": round(c / nb, 2)} for v, c in a["kos"].most_common() if nb and c / nb >= 0.05]})
    return rows

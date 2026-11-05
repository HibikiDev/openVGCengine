





from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME_DIRS: list[Path] = [ROOT / "trainer/runs/buddy_logs"]
BOT_NAMES: list[str] = ["PracticeBot"]
ROW_LOOKUP: list = [None]
_EXTENDED = [False]


def _extend() -> None:

    if not _EXTENDED[0]:
        _EXTENDED[0] = True
        try:
            import vgc_suite.team_stats
        except ImportError:
            pass


def _game_dir(room: str) -> Path:

    _extend()
    for d in GAME_DIRS:
        if (d / f"{room}.log").exists():
            return d
    return GAME_DIRS[0]

def _species(details: str) -> str:

    return details.split(",")[0].strip().split("-Mega")[0]

def _to_six(sp: str, six: list[str]) -> str | None:

    if sp in six:
        return sp
    return next((x for x in six if sp.startswith(x) or x.startswith(sp)), None)

def parse_game(path: Path) -> dict | None:


    try:
        lines = path.read_text(encoding="utf8", errors="replace").splitlines()
    except OSError:
        return None
    if not any(ln.startswith(("|win|", "|tie")) for ln in lines):
        return None
    sides, rating = {}, {}
    for ln in lines:
        p = ln.split("|")
        if len(p) > 3 and p[1] == "player" and p[3]:
            sides[p[2]] = p[3]
            if len(p) > 5 and p[5].strip().isdigit():
                rating[p[2]] = int(p[5])
    me = next((s for s, n in sides.items() if n in BOT_NAMES), None)
    if me is None or len(sides) < 2:
        return None
    foe = "p2" if me == "p1" else "p1"
    foe_sheet = [_species(ln.split("|")[3]) for ln in lines if ln.startswith(f"|poke|{foe}|")]
    six = sorted(foe_sheet)
    my_six = [_species(ln.split("|")[3]) for ln in lines if ln.startswith(f"|poke|{me}|")]
    my_bring, turn, foe_lead, foe_shown, my_shown = [], 0, [], [], []
    for ln in lines:
        p = ln.split("|")
        if len(p) < 2:
            continue
        if p[1] == "request" and not my_bring and len(p) > 2 and p[2].startswith('{"active"'):
            try:
                my_bring = [_species(m["details"]) for m in json.loads("|".join(p[2:]))["side"]["pokemon"]][:4]
            except (ValueError, KeyError):
                pass
        elif p[1] == "turn":
            turn = int(p[2])
        elif p[1] in ("switch", "drag", "replace") and len(p) > 3:
            sp = _species(p[3])
            if p[2].startswith(foe):
                if turn == 0 and len(foe_lead) < 2:
                    foe_lead.append(sp)
                if sp not in foe_shown:
                    foe_shown.append(sp)
            elif p[2].startswith(me) and sp not in my_shown:
                my_shown.append(sp)
    if not my_bring:
        my_bring = my_shown[:4]

    change = {}
    for ln in lines:
        m = re.match(r"\|raw\|(.+?)'s rating: (\d+) &rarr; <strong>(\d+)</strong>", ln)
        if m:
            change["me" if m.group(1) in BOT_NAMES else "foe"] = [int(m.group(2)), int(m.group(3))]
    who = sides[foe].lower()
    msgs = [ln.lower() for ln in lines if ln.startswith("|-message|")]
    forfeit = any(m.endswith((f"{who} forfeited.", f"{who} forfeited the series.")) for m in msgs)
    timeout = any(m.endswith(f"{who} lost due to inactivity.") for m in msgs)
    return {"six": six, "foe_sheet": foe_sheet, "my_six": my_six, "my_bring": my_bring, "my_lead": sorted(my_bring[:2]), "foe_lead": sorted(foe_lead),
            "foe_shown": [x for x in dict.fromkeys(_to_six(x, six) for x in foe_shown) if x], "turns": turn, "foe_ff": forfeit,
            "foe_timeout": timeout, "foe_rating": rating.get(foe), "rating_change": change or None}

def game_log(room: str) -> str | None:

    if not room or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in room):
        return None
    try:
        lines = (_game_dir(room) / f"{room}.log").read_text(encoding="utf8", errors="replace").splitlines()
    except OSError:
        return None
    return "\n".join(ln for ln in lines if not ln.startswith(("|c|", "|c:|", "|pm|", "|request|", "|raw|", "|html|", "|uhtml|", "|j|",
                                                                 "|l|", "|J|", "|L|", "|n|", "|N|")))

def _trace(room: str) -> list[dict]:
    try:
        t = json.loads((_game_dir(room) / f"{room}.trace.json").read_text(encoding="utf8"))
        return [d for d in t if isinstance(d, dict)]
    except (OSError, ValueError):
        return []

def game_view(room: str, pov: str | None = None) -> dict | None:



    if not room or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in room):
        return None
    try:
        lines = (_game_dir(room) / f"{room}.log").read_text(encoding="utf8", errors="replace").splitlines()
    except OSError:
        return None
    _extend()
    bots = tuple(BOT_NAMES)
    me = next((ln.split("|")[2] for ln in lines if ln.startswith("|player|") and len(ln.split("|")) > 3 and ln.split("|")[3] in bots), None)
    row = ROW_LOOKUP[0](room) if ROW_LOOKUP[0] else None
    human = pov == "human" and me is not None
    side = ("p2" if me == "p1" else "p1") if human else me
    v = view_from_lines(lines, side, _trace(room), trace_is_foe=human)
    names = v["players"]
    v.update(room=room, won=(v["result"] not in bots) if human else (v["result"] in bots), series=(row or {}).get("series"),
             game=(row or {}).get("game"), team=(row or {}).get("team"), pov_human=human, bot_side=me,
             human_side=("p2" if me == "p1" else "p1") if me else None,
             us=names.get(side) if human else None, them=names.get(me) if human else None)
    return v

def view_from_lines(lines: list[str], me: str | None, trace: list[dict], trace_is_foe: bool = False) -> dict:




    from vgc_suite.core.narrate import narrate
    n = narrate(lines, me)
    foe = "p2" if me == "p1" else "p1"
    T = "\u27e6{}|{}\u27e7"
    names: dict[str, str] = {}

    def disp(side: str, nick: str) -> str:

        sd = me if side == "us" else foe
        if f"{sd}:{nick}" in names:
            return names[f"{sd}:{nick}"]

        hit = [x for x in n["preview"].get(sd, []) if x == nick or x.startswith(nick + "-")]
        return hit[0] if len(hit) == 1 else nick

    def tag_action(text: str, actor: str) -> str:


        other = "them" if actor == "us" else "us"
        if text.startswith("switch "):
            return "switch " + T.format(actor, disp(actor, text[7:]))
        if " -> " in text:
            mv, tgt = text.split(" -> ", 1)
            tgt, mega = (tgt[:-6], " +mega") if tgt.endswith(" +mega") else (tgt, "")
            side = actor if tgt in cur.get(actor, ()) and tgt not in cur.get(other, ()) else other
            return f"{mv} -> " + T.format(side, disp(side, tgt)) + mega
        return text

    cur: dict[str, set] = {"us": set(), "them": set()}
    for ln in lines:
        q = ln.split("|")
        if len(q) > 3 and q[1] in ("switch", "drag", "replace") and q[2][:2] in ("p1", "p2"):
            cur["us" if q[2][:2] == me else "them"].add(q[2].split(": ", 1)[1])
    OWN, OTHER = ("them", "us") if trace_is_foe else ("us", "them")
    bot_view: dict[int, dict] = {}
    snap = {t["turn"]: t.get("names") or {} for t in n["turns"]}
    for d in trace:
        why = d.get("why") if isinstance(d.get("why"), dict) else {}
        t = d.get("turn")
        if t is None or not why:
            continue

        names = snap.get(int(t) - 1) or snap.get(int(t)) or {}
        v = bot_view.setdefault(int(t), {"win": why.get("win"), "slots": [], "foe_guess": []})
        for sl in why.get("slots") or []:

            if sl and sl.get("chosen") and sl["chosen"] != "pass":
                v["slots"].append({"mon": T.format(OWN, disp(OWN, sl.get("mon") or "")), "chosen": tag_action(sl["chosen"], OWN),
                                   "policy": tag_action(sl["policy"], OWN) if sl.get("policy") else None,
                                   "p": sl.get("p"), "same": sl.get("policy") == sl["chosen"]})
        if not v["foe_guess"]:
            v["foe_guess"] = [{"mon": T.format(OTHER, disp(OTHER, g.get("mon") or "")),
                               "options": [[tag_action(o, OTHER), pr] for o, pr in (g.get("options") or [])[:2] if o != "pass"]}
                              for g in (why.get("foe_guess") or []) if g]
            v["foe_guess"] = [g for g in v["foe_guess"] if g["options"]]
        sv = (d.get("search") or {}).get("view")
        if sv and "search" not in v:
            v["search"] = {"replies": [[[tag_action(o, OTHER) for o in r if o not in ("-", "pass")], w]
                                       for r, w in (sv.get("replies") or [])[:4]],
                           "cands": []}
            seen_c: dict[str, list] = {}
            for c, q, ch in sorted(sv.get("candidates") or [], key=lambda x: (not x[2], -(x[1] if x[1] is not None else -9))):
                key = json.dumps(c)
                if key not in seen_c:
                    seen_c[key] = [[tag_action(o, OWN) for o in c if o != "pass"], q, ch]
            v["search"]["cands"] = sorted(seen_c.values(), key=lambda x: -(x[1] if x[1] is not None else -9))[:4]
    turns = []
    for t in n["turns"]:
        hp = t.get("hp") or {}
        nm = t.get("names") or {}
        turns.append({**t, "ours": sorted((nm.get(k, k[3:]), v) for k, v in hp.items() if k.startswith(f"{me}:")),
                      "theirs": sorted((nm.get(k, k[3:]), v) for k, v in hp.items() if k.startswith(f"{foe}:")),
                      "bot": bot_view.get(t["turn"])})
    return {"players": n["players"], "me": me, "opp": n["players"].get(foe), "result": n["result"], "rating": n["rating"],
            "turns": turns, "foe_paste": sheet_paste(lines, foe), "own_paste": sheet_paste(lines, me)}

_NAMES: dict | None = None

def _names() -> dict:

    global _NAMES
    if _NAMES is None:
        _NAMES = {}
        for kind in ("species", "items", "abilities", "moves"):
            rows = json.loads((ROOT / f"tools/gen-data/out/{kind}.json").read_text(encoding="utf8"))
            _NAMES[kind] = {r["id"]: r["name"] for r in rows}
    return _NAMES

def sheet_paste(lines: list[str], side: str) -> str | None:




    import re as _re
    from vgc_trainer.showdown.live_search import _corpus
    from vgc_trainer.search import STATS, guessed_spreads
    from vgc_trainer.showdown.teams import to_paste, unpack
    raw = next((ln.split("|", 3)[3] for ln in lines if ln.startswith(f"|showteam|{side}|")), None)
    if not raw:
        return None
    nm = _names()

    def name(kind: str, v: str) -> str:
        return nm[kind].get(_re.sub(r"[^a-z0-9]", "", (v or "").lower()), v) if v else v

    genders = [(f.split("|") + [""] * 12)[7] for f in raw.split("]")]
    sets = []
    for st, g in zip(unpack(raw), genders):
        sets.append({**st, "gender": g, "species": name("species", st["species"]), "name": name("species", st.get("name") or st["species"]),
                     "item": name("items", st.get("item")), "ability": name("abilities", st.get("ability")),
                     "moves": [name("moves", m) for m in st.get("moves", [])]})
    guess = guessed_spreads([sets], _corpus())[0]
    for st, (nature, evs) in zip(sets, guess):
        st["nature"] = st.get("nature") or nature
        st["evs"] = dict(zip(STATS, evs))
    return to_paste(sets)

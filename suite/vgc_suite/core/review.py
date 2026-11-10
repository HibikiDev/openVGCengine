














from __future__ import annotations

from vgc_trainer import i18n
import hashlib
import random
from collections import Counter
from statistics import median

import numpy as np
import torch

from vgc_trainer.showdown.requests import PASS_ACTION, SWITCH_BASE

from .analysis import _label, calibrated_win, load_calibration, policy_view
from .positions import walk

SWING = 0.10
BAND = 0.05
TIERS = {"fast": 0, "standard": 4, "deep": 8}


REVIEW_VERSION = 8
CACHE = __import__("pathlib").Path(__file__).resolve().parents[3] / "trainer/runs/review_cache"


class _TurnCache:





    def __init__(self, log, ckpt: str, n: int, own: dict | None):
        import json
        import os
        try:
            import vgc_engine
            eng = os.path.dirname(vgc_engine.__file__)
            eng = f"{eng}|{os.path.getmtime(vgc_engine.__file__)}"
        except (ImportError, OSError, TypeError):
            eng = "?"
        try:
            st = os.stat(ckpt)
            ck = f"{os.path.abspath(ckpt)}|{st.st_size}|{st.st_mtime}"
        except OSError:
            ck = str(ckpt)
        text = "\n".join(log.lines)
        self.file = CACHE / f"{hashlib.sha1(text.encode('utf8')).hexdigest()[:20]}.json"
        self.base = hashlib.sha1(json.dumps([REVIEW_VERSION, ck, eng, n, own or {}], sort_keys=True, default=str).encode()).hexdigest()[:16]
        try:
            self.data = json.loads(self.file.read_text(encoding="utf8"))
        except (OSError, ValueError):
            self.data = {}
        self.hits = 0

    def key(self, side: str, turn: int) -> str:
        return f"{self.base}|{side}|{turn}"

    def get(self, side: str, turn: int) -> dict | None:
        hit = self.data.get(self.key(side, turn))
        self.hits += hit is not None
        return hit

    def put(self, side: str, turn: int, value: dict) -> None:
        import json
        self.data[self.key(side, turn)] = value
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            tmp = self.file.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data), encoding="utf8")
            tmp.replace(self.file)
        except OSError:
            pass


def _seed(*parts) -> int:
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "little") & ((1 << 62) - 1)


def _played_joint(d, fill: list[tuple[int, bool]] | None = None) -> tuple[list[tuple[int, bool]] | None, list[int]]:



    out, assumed = [], []
    for slot in (0, 1):
        p = d.played[slot]
        if p is not None:
            out.append((int(p[0]), bool(p[1])))
        elif d.active[slot] is None or not d.masks.actions[slot]:
            out.append((PASS_ACTION, False))
        elif fill is not None:
            out.append((int(fill[slot][0]), bool(fill[slot][1])))
            assumed.append(slot)
        else:
            return None, []
    return out, assumed


def _unseen_fill(d, pick: list[tuple[int, bool]], fmt: str | None) -> list[tuple[int, bool]]:





    from vgc_trainer.showdown.belief import FORMAT_MOD, dex
    from vgc_trainer.showdown.tracker import to_id
    moves = dex()["moves"][FORMAT_MOD.get(fmt, "champions")]
    out = []
    for slot in (0, 1):
        a, mega = int(pick[slot][0]), bool(pick[slot][1])
        names = d.moves[slot] if slot < len(d.moves) else []

        def info(a_: int) -> dict | None:
            return moves.get(to_id(names[a_ // 4])) if a_ < SWITCH_BASE and a_ // 4 < len(names) else None

        def later(a_: int) -> bool:
            return info(a_) is not None and info(a_)["pri"] <= 0

        if d.played[slot] is None and not later(a):
            legal = [a_ for a_ in range(SWITCH_BASE) if int(d.masks.actions[slot]) >> a_ & 1 and later(a_)]
            hits = [a_ for a_ in legal if info(a_)["bp"] > 0]
            if hits or legal:
                a, mega = (hits or legal)[0], False
        out.append((a, mega))
    return out


def _line_label(d, line) -> str:




    return " · ".join((f"{d.active[s]}: " if d.active[s] else "") + _label(d, s, a, m) for s, (a, m) in enumerate(line)
                      if a != PASS_ACTION)


def search_turn(d, side: str, ls, n: int, key: str, agent=None) -> dict:

    played, assumed = _played_joint(d)
    if played is None and agent is not None:
        played, assumed = _played_joint(d, _unseen_fill(d, agent.act(d.obs, d.masks, d.bring, d.ctx), d.tracker.fmt))
    if played is None:
        return {"skipped": "a slot's choice isn't in the log"}
    if assumed and all(s in assumed for s in (0, 1) if d.active[s] is not None and d.masks.actions[s]):
        return {"skipped": "neither choice is in the log"}
    from vgc_suite.core.positions import closed_world, tracked_request
    from .bundle import live_arm
    foe = "p2" if side == "p1" else "p1"
    arm = live_arm()
    runs = []
    for i in range(n):
        s = _seed(key, i)
        ls.rng, ls.np_rng = random.Random(s), np.random.default_rng(s)
        try:
            ls.choose(d.tracker, tracked_request(d, side), d.sheets[side], d.sheets[foe], d.bring, d.masks, d.ctx, None, None,
                      reply_temp=1.0, arm=arm, score_also=played, **closed_world(d, foe))
        except Exception as e:
            return {"skipped": f"{type(e).__name__}: {str(e)[:80]}"}
        last = ls.last
        q, cands, pi = last["q"], last["cands"], last["played_index"]
        b = int(np.argmax(q))
        runs.append({"gap": round((q[b] - q[pi]) / 2, 4), "best": tuple(tuple(c) for c in cands[b]), "best_win": round((q[b] + 1) / 2, 3),
                     "played_win": round((q[pi] + 1) / 2, 3), "replaced": last.get("played_replaced")})
    gaps = [r["gap"] for r in runs]
    votes = Counter(r["best"] for r in runs)
    top, top_n = votes.most_common(1)[0]
    played_key = tuple((a, int(m)) for a, m in played)
    return {"n": n, "gaps": gaps, "median_gap": round(median(gaps), 4), "costly": sum(g > BAND for g in gaps),
            "best": _line_label(d, [(a, bool(m)) for a, m in top]), "best_votes": top_n,
            "played_best_votes": votes.get(played_key, 0), "played": _line_label(d, played),
            "played_win": round(median(r["played_win"] for r in runs), 3), "best_win": round(median(r["best_win"] for r in runs), 3),
            "assumed": [d.active[s] for s in assumed]}


PROBE_MIN = 0.15


def _alternatives(d, foe: str, log, closed: bool, fits: dict | None = None) -> list[tuple[str, list[dict]]]:





    import copy
    from collections import Counter as _C
    from vgc_trainer.search import _spread
    from vgc_trainer.showdown import belief
    from vgc_trainer.showdown.live_search import _corpus_for
    sheet = d.sheets.get(foe) if d.sheets else None
    if not sheet:
        return []
    corpus = _corpus_for(d.tracker.fmt if d.tracker is not None else None)
    facts = None
    if closed:
        ev = belief.Evidence(log.fmt)
        for ln in log.lines:
            ev.feed(ln)
            if ln == f"|turn|{d.turn}":
                break
        facts = ev.mons.get(foe) or []
    out = []
    for name in d.foe_active:
        if not name:
            continue
        i = next((k for k, st in enumerate(sheet) if name in (st.get("name"), st.get("species"))), None)
        if i is None:
            continue
        st = sheet[i]
        counts = _C(_spread(s) for team in corpus for s in team if s.get("species") == st["species"]
                    and (not (closed is False and st.get("nature")) or s.get("nature") == st.get("nature")))
        ranked = [sp for sp, _ in counts.most_common(2)]
        ft = (fits or {}).get(i)
        if ft is not None:
            ranked = [ft.guess] + [sp for sp, _ in ft.posterior if sp != ft.guess][:1]
        if len(ranked) == 2:
            nat, evs = ranked[1]
            v = copy.deepcopy(sheet)
            v[i]["known_spread"] = [nat, list(evs)]
            out.append((f"{name} on {nat} {'/'.join(str(x) for x in evs)} (HP/Atk/Def/SpA/SpD/Spe)", v))
        if closed and facts and i < len(facts):
            f = facts[i]
            if f.item is None:
                prior = belief.SetPrior.load(log.fmt)
                items = [(k, p) for k, p in belief.posterior(prior, f)["items"] if k and k != belief.to_id(st.get("item") or "")]
                if items and items[0][1] >= PROBE_MIN:
                    v = copy.deepcopy(sheet)
                    v[i]["item"] = belief.name("items", items[0][0])
                    out.append((f"{name} holding {v[i]['item']}", v))
    return out


def probe_turn(d, side: str, ls, n: int, key: str, agent, log, closed: bool, fits: dict | None = None) -> dict:


    import dataclasses
    foe = "p2" if side == "p1" else "p1"
    hinges, tried = [], 0
    for label, variant in _alternatives(d, foe, log, closed, fits)[:4]:
        d2 = dataclasses.replace(d, sheets={**d.sheets, foe: variant})
        r = search_turn(d2, side, ls, n, key, agent)
        if "skipped" in r:
            continue
        tried += 1
        if r["costly"] <= r["n"] // 2:
            hinges.append({"label": label, "costly": r["costly"], "n": r["n"], "gap": r["median_gap"]})
    return {"probed": tried, "hinges": hinges}


def _result_for(log, side: str) -> float | None:

    from vgc_trainer.showdown.tracker import to_id
    for ln in log.lines:
        if ln.startswith("|win|"):
            return 1.0 if to_id(ln[5:]) == to_id(log.players.get(side, "")) else 0.0
        if ln == "|tie" or ln.startswith("|tie|"):
            return 0.5
    return None


SITE_WORDS = {1: ("hit", "missed", "to hit"), 2: ("a critical hit", "no crit", "to crit"), 4: ("it happened", "it didn't", "added effect"),
              5: ("flinched", "no flinch", "to flinch"), 6: ("confused", "not confused", "to confuse"),
              7: ("fully paralyzed", "it moved", "full paralysis"), 8: ("hit itself", "it acted", "to hit itself"),
              10: ("thawed", "stayed frozen", "to thaw"), 11: ("Quick Claw went first", "no Quick Claw", "Quick Claw")}
STAT_WORDS = {"atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe", "accuracy": "accuracy", "evasion": "evasion"}
STATUS_WORDS = {"brn": "burn", "par": "paralysis", "frz": "freeze", "psn": "poison", "tox": "bad poison", "slp": "sleep"}


def _turn_lines(log, turn: int) -> list[str]:

    lines, on = [], False
    for ln in log.lines:
        if ln.startswith("|turn|"):
            if on:
                break
            on = ln == f"|turn|{turn}"
            continue
        if on:
            lines.append(ln)
    return lines


def _realised(lines: list[str], site: int, actor: str, move: str, target: str) -> tuple[bool, str] | None:


    from vgc_trainer.showdown.tracker import to_id
    par = lambda ln: ln.split("|")
    if site == 7:
        return any(ln.startswith(f"|cant|{actor}") and ln.endswith("|par") for ln in lines), "full paralysis"
    if site == 10:
        return any(ln.startswith(f"|-curestatus|{actor}") and "|frz" in ln for ln in lines), "thaw"
    if site == 11:
        return any(ln.startswith(f"|-activate|{actor}") and "Quick Claw" in ln for ln in lines), "Quick Claw"
    if site == 8:
        return any(ln.startswith(f"|-damage|{actor}") and "[from] confusion" in ln for ln in lines), "confusion self-hit"
    seg = None
    for i, ln in enumerate(lines):
        p = par(ln)
        if len(p) > 3 and p[1] == "move" and p[2].startswith(actor) and to_id(p[3]) == to_id(move):
            j = i + 1
            while j < len(lines) and not lines[j].startswith(("|move|", "|cant|", "|upkeep")):
                j += 1
            seg = lines[i + 1:j]
            break
    if seg is None:
        return None
    on_target = lambda ln: len(par(ln)) > 2 and par(ln)[2].startswith(target)
    if site == 1:
        return not any(ln.startswith("|-miss|") and (target in ln) for ln in seg), "accuracy"
    if site == 2:
        return any(ln.startswith("|-crit|") and on_target(ln) for ln in seg), "crit"
    if site in (4, 5, 6):
        for ln in seg:
            p = par(ln)
            if on_target(ln) and "[from]" not in ln and p[1] in ("-status", "-unboost", "-boost", "-start"):
                what = (STATUS_WORDS.get(p[3], p[3]) if p[1] == "-status" else
                        f"{STAT_WORDS.get(p[3], p[3])} {'−' if p[1] == '-unboost' else '+'}{p[4] if len(p) > 4 else 1}" if p[1] in ("-unboost", "-boost") else
                        p[3].replace("move: ", ""))
                return True, what
        if any(ln.startswith(f"|cant|{target}") and ln.endswith("|flinch") for ln in lines):
            return True, "flinch"
        return False, ""
    return None


def chance_split(d, fd, side: str, agent, ls, now: float, realised: float | None, key: str, lines: list[str] | None = None,
                 seeds: int = 64) -> dict:







    fmt = d.tracker.fmt
    mine, assumed = _played_joint(d, _unseen_fill(d, agent.act(d.obs, d.masks, d.bring, d.ctx), fmt))
    theirs, foe_assumed = (_played_joint(fd, _unseen_fill(fd, agent.act(fd.obs, fd.masks, fd.bring, fd.ctx), fmt)) if fd is not None
                           else (None, []))
    if mine is None or realised is None:
        return {"skipped": "not enough of the turn is known"}
    from vgc_suite.core.positions import closed_world, tracked_request
    foe = "p2" if side == "p1" else "p1"
    args = (d.tracker, tracked_request(d, side), d.sheets[side], d.sheets[foe], d.bring, d.masks, mine, theirs, seeds)

    def run(force=None) -> dict:
        s = _seed(key, "chance")
        ls.rng, ls.np_rng = random.Random(s), np.random.default_rng(s)

        return ls.turn_rolls(*args, force=force, foe_names=fd.names if fd is not None else None,
                             foe_moves=fd.moves if fd is not None else None)
    try:
        base = run()
    except Exception as e:
        return {"skipped": f"{type(e).__name__}: {str(e)[:80]}"}
    exp = (base["value"] + 1) / 2
    out = {"now": round(now, 3), "expected": round(exp, 3), "realised": round(realised, 3), "choices": round(exp - now, 4),
           "dice": round(realised - exp, 4), "assumed": len(assumed) + len(foe_assumed), "rolls": []}
    if lines is None:
        return out
    ident = lambda pos: f"p{pos // 2 + 1}{'ab'[pos % 2]}"
    for key_, (site, actor, move_id, move, target, k, bound, num, yes, n_runs) in sorted(base["draws"].items()):
        if k or site not in SITE_WORDS:
            continue
        got = _realised(lines, site, ident(actor), move, ident(target) if target != 255 else "")
        if got is None:
            continue
        came_yes, what = got
        try:
            as_was = run([(site, actor, move_id, target, k, 0 if came_yes else bound - 1)])["value"]
            other = run([(site, actor, move_id, target, k, bound - 1 if came_yes else 0)])["value"]
        except Exception:
            continue
        yes_w, no_w, kind = SITE_WORDS[site]
        names = base["names"]
        who = names.get(actor, "?") + (f" → {names[target]}" if target in names and target != actor else "")
        chance = round(100 * num / bound)
        out["rolls"].append({"move": move, "who": who, "site": site, "kind": kind, "chance": chance,
                             "came": (yes_w if came_yes else no_w) + (f" ({what})" if came_yes and what and site in (4, 5, 6) else ""),
                             "other": no_w if came_yes else yes_w, "effect": round((as_was - base["value"]) / 2, 4),
                             "if_other": round((other + 1) / 2, 3), "if_as_was": round((as_was + 1) / 2, 3)})
    out["rolls"].sort(key=lambda r: -abs(r["effect"]))
    out["rolls"] = [r for r in out["rolls"] if abs(r["effect"]) >= 0.01]
    out["rest"] = round(out["dice"] - sum(r["effect"] for r in out["rolls"]), 4)
    return out


def _spread_text(sp) -> str:
    return f"{sp[0]} {'/'.join(str(x) for x in sp[1])}"


def _fit_foe(log, side: str, foe: str, decs, foe_decs: dict, ls, agent, own: dict | None) -> dict:




    if not log.sheets.get(foe) or (own or {}).get(foe):
        return {}
    from .spreadfit import fit_spreads
    try:
        with torch.inference_mode():
            return fit_spreads(log.lines, side, decs, foe_decs, ls, agent, seed=_seed(f"{log.source}|{side}", "fit"))
    except Exception:
        return {}


def _cached_fits(cache, side: str, run) -> dict:


    from .spreadfit import Fit
    tup = lambda sp: (sp[0], tuple(sp[1]))
    hit = cache.get(side, "fit") if cache is not None else None
    if hit is not None:
        return {int(i): Fit(index=f["index"], species=f["species"], spread=tup(f["spread"]), guess=tup(f["guess"]), turns=f["turns"],
                            posterior=[(tup(sp), p) for sp, p in f["posterior"]]) for i, f in hit["fits"].items()}
    fits = run()
    if cache is not None:
        cache.put(side, "fit", {"fits": {str(i): {"index": ft.index, "species": ft.species, "spread": list(ft.spread), "guess": list(ft.guess),
                                                   "turns": int(ft.turns), "posterior": [[[sp[0], [int(x) for x in sp[1]]], float(p)]
                                                                                        for sp, p in ft.posterior]}
                                         for i, ft in fits.items()}})
    return fits


def review(log, sides, agent, ls, ckpt: str, n: int = 4, own: dict | None = None, progress=None) -> dict:


    cal = load_calibration(ckpt)
    out = {"source": log.source, "players": log.players, "format": log.fmt, "n": n, "band": BAND, "swing": SWING,
           "calibrated": cal is not None, "turns": [], "luck": {}, "fits": {}}
    cache = _TurnCache(log, ckpt, n, own) if n > 0 else None
    for side in sides:
        foe = "p2" if side == "p1" else "p1"
        decs = walk(log, side, (own or {}).get(side), keep=n > 0)
        foe_decs = {fd.turn: fd for fd in walk(log, foe, (own or {}).get(foe))} if n > 0 else {}
        result = _result_for(log, side)
        fits = _cached_fits(cache, side, lambda: _fit_foe(log, side, foe, decs, foe_decs, ls, agent, own)) if n > 0 else {}
        if fits:
            out["fits"][foe] = [{"mon": ft.species, "spread": _spread_text(ft.spread), "guess": _spread_text(ft.guess),
                                 "changed": ft.spread != ft.guess, "turns": ft.turns} for _, ft in sorted(fits.items())]
        views = []
        for d in decs:
            v = policy_view(agent, d)
            v["win_raw"] = v["win"]
            if cal is not None:
                v["win"] = round(calibrated_win(v["win"], d.turn, cal), 3)
            views.append(v)
        rows = []
        for i, (d, v) in enumerate(zip(decs, views)):
            nxt = views[i + 1]["win"] if i + 1 < len(views) else None
            swing = round(nxt - v["win"], 3) if nxt is not None else None
            shares = [s.get("played_p") for s in v["slots"] if s and s.get("played_p") is not None]
            row = {"turn": d.turn, "side": side, "win": v["win"], "swing": swing, "played_p": shares,
                   "big_swing": swing is not None and abs(swing) >= SWING}
            if n > 0:
                realised = views[i + 1]["win_raw"] if i + 1 < len(views) else result
                hit = cache.get(side, d.turn)
                if progress is not None:
                    progress(i18n.t("Searching {side}'s turn {turn}", side=side, turn=d.turn) if hit is None
                             else i18n.t("{side}'s turn {turn}: from an earlier run", side=side, turn=d.turn))
                if hit is not None:
                    row["search"], row["chance"] = hit["search"], hit["chance"]
                else:
                    with torch.inference_mode():
                        row["search"] = search_turn(d, side, ls, n, f"{log.source}|{side}|{d.turn}", agent)
                        s_ = row["search"]
                        if s_.get("costly", 0) > s_.get("n", 0) // 2:
                            s_.update(probe_turn(d, side, ls, n, f"{log.source}|{side}|{d.turn}", agent, log,
                                                 closed=not log.sheets.get(foe), fits=fits))
                        row["chance"] = chance_split(d, foe_decs.get(d.turn), side, agent, ls, v["win_raw"], realised,
                                                     f"{log.source}|{side}|{d.turn}", _turn_lines(log, d.turn))
                    cache.put(side, d.turn, {"search": row["search"], "chance": row["chance"]})
            rows.append(row)
        split = [r for r in rows if "dice" in (r.get("chance") or {})]
        if split:
            big = max(split, key=lambda r: abs(r["chance"]["dice"]))
            out["luck"][side] = {"net": round(sum(r["chance"]["dice"] for r in split), 3), "turns": len(split),
                                 "biggest": {"turn": big["turn"], **big["chance"]}}
            rolls = [dict(r_, turn=r["turn"]) for r in split for r_ in r["chance"].get("rolls") or []]
            if rolls:
                out["luck"][side]["roll"] = max(rolls, key=lambda r_: abs(r_["effect"]))
        out["turns"] += rows
    out["turns"].sort(key=lambda r: (r["turn"], r["side"]))
    out["cached"] = cache.hits if cache is not None else 0
    return out

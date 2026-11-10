






















from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from dataclasses import dataclass, field

TOL, FLOOR = 1, 0.05
_HP = re.compile(r"^(\d+)/(\d+)")
_HP_LINES = ("switch", "drag", "replace", "-damage", "-heal", "-sethp")


def _pct(cur: int, mx: int) -> int:

    return 0 if cur == 0 else max(1, min(100 if cur == mx else 99, math.ceil(100 * cur / mx)))


def _base(species: str) -> str:
    from vgc_trainer.showdown.tracker import to_id
    return to_id(species).split("mega")[0]


def turn_hp(lines: list[str], turn: int) -> dict[tuple[str, str], int]:


    nick: dict[str, str] = {}
    hp: dict[tuple[str, str], int] = {}
    for ln in lines:
        p = ln.split("|")
        if len(p) < 3:
            continue
        if p[1] == "turn" and p[2].isdigit() and int(p[2]) == turn + 1:
            break
        if p[1] in ("switch", "drag", "replace", "detailschange") and len(p) > 3 and ": " in p[2]:
            nick[p[2].split(": ")[0][:2] + p[2].split(": ", 1)[1]] = _base(p[3].split(",")[0])
        if p[1] in _HP_LINES and len(p) > 3 and ": " in p[2]:
            k = 4 if p[1] in ("switch", "drag", "replace") else 3
            key = p[2].split(": ")[0][:2] + p[2].split(": ", 1)[1]
            if k < len(p) and key in nick:
                m = _HP.match(p[k])
                if p[k].startswith("0"):
                    hp[(key[:2], nick[key])] = 0
                elif m:
                    hp[(key[:2], nick[key])] = _pct(int(m.group(1)), int(m.group(2))) if int(m.group(2)) != 100 else int(m.group(1))
    return hp


def _moved(lines: list[str], turn: int) -> bool:

    on = False
    for ln in lines:
        if ln.startswith("|turn|"):
            if on:
                return False
            on = ln == f"|turn|{turn}"
        elif on and ln.startswith("|move|"):
            return True
    return False


@dataclass
class Fit:


    index: int
    species: str
    spread: tuple[str, tuple[int, ...]]
    guess: tuple[str, tuple[int, ...]]
    turns: int
    posterior: list = field(default_factory=list)


def fit_spreads(lines: list[str], side: str, decs: list, foe_decs: dict, ls, agent, k: int = 30, runs: int = 32,
                seed: int = 0, exclude: dict[int, tuple] | None = None) -> dict[int, Fit]:




    import vgc_engine as ve
    from vgc_suite.core.positions import tracked_request
    from vgc_trainer.search import _spread
    from vgc_trainer.showdown.live_search import _corpus_for, _which_mon
    from vgc_trainer.showdown.requests import PASS_ACTION, SWITCH_BASE
    from vgc_trainer.showdown.tracker import to_id
    from .review import _played_joint, _unseen_fill

    foe = "p2" if side == "p1" else "p1"
    rng = random.Random(seed)
    prior: dict[int, Counter] = {}
    hp_ll: dict[int, Counter] = {}
    turns: Counter = Counter()
    species: dict[int, str] = {}
    for d in decs:
        fd = foe_decs.get(d.turn)
        if fd is None or d.tracker is None or not _moved(lines, d.turn):
            continue
        fmt = d.tracker.fmt
        mine, _ = _played_joint(d, _unseen_fill(d, agent.act(d.obs, d.masks, d.bring, d.ctx), fmt))
        theirs, _ = _played_joint(fd, _unseen_fill(fd, agent.act(fd.obs, fd.masks, fd.bring, fd.ctx), fmt))
        if mine is None or theirs is None:
            continue
        sheet = d.sheets[foe]
        ids = [{to_id(s.get("name") or ""), to_id(s.get("species") or "")} for s in sheet]
        also = [i for i in (_which_mon(to_id(fd.names[a - SWITCH_BASE]), ids) for a, _ in theirs
                            if SWITCH_BASE <= a < PASS_ACTION and a - SWITCH_BASE < len(fd.names)) if i is not None]
        try:
            env, si = ls._review_root(d.tracker, tracked_request(d, side), d.sheets[side], sheet, d.bring, d.masks, foe_also=also)
            theirs = ls.remap_foe_actions(env, 1 - si, theirs, fd.names, fd.moves)
        except Exception:
            continue
        fi = 1 - si
        obs = turn_hp(lines, d.turn)
        if not obs:
            continue
        guesses = ls._guesses[json.dumps(env.teams, sort_keys=True)]
        foe_roots = [int(r) for r in env.bring[0, fi]]
        base_foe = [guesses[env.pairs[0, fi]][r] for r in foe_roots]
        st0 = env.pool.inspect(0)
        acts = [None, None]
        acts[si] = [[int(a), int(m)] for a, m in mine]
        acts[fi] = [[int(a), int(m)] for a, m in theirs]
        tags = {si: side, fi: foe}
        corpus = _corpus_for(fmt)
        for slot_k in st0["sides"][fi]["active"]:
            if slot_k >= len(foe_roots) or st0["sides"][fi]["mons"][slot_k]["hp"] == 0:
                continue
            i = foe_roots[slot_k]
            if i not in prior:
                st = sheet[i] if i < len(sheet) else {}
                nature = st.get("nature")
                c = Counter(_spread(s) for t in corpus for s in t
                            if to_id(s["species"]) == to_id(st.get("species") or "") and (not nature or s.get("nature") == nature))
                if exclude and exclude.get(i) in c:
                    c[exclude[i]] -= 1
                    c += Counter()
                if not c:
                    continue
                prior[i] = Counter(dict(c.most_common(k)))
                hp_ll[i] = Counter()
                species[i] = st.get("species") or ""
            cands = list(prior[i])
            n = len(cands) * runs
            pool = ve.BattlePool(n)
            crn = [rng.getrandbits(62) for _ in range(runs)]
            pool.copy_from(env.pool, [0] * n, list(range(n)), crn * len(cands))
            per = []
            for cand in cands:
                sp = list(base_foe)
                sp[slot_k] = cand
                per += [sp] * runs
            pool.set_spreads(list(range(n)), fi, per)
            hits = [Counter() for _ in cands]
            try:
                for j in range(n):
                    pool.step_scripted(j, acts, [])
                    out = pool.inspect(j)
                    for s_ in (0, 1):
                        for mon in out["sides"][s_]["mons"]:
                            key = (tags[s_], _base(mon["species"]))
                            if key in obs and abs(_pct(mon["hp"], mon["max_hp"]) - obs[key]) <= TOL:
                                hits[j // runs][key] += 1
            except ValueError:
                continue
            turns[i] += 1
            for ci, cand in enumerate(cands):
                hp_ll[i][cand] += sum(math.log(max(FLOOR, hits[ci][key] / runs)) for key in obs)
    fits = {}
    for i, c in prior.items():
        if not turns[i]:
            continue
        lp = {cand: math.log(nc) + hp_ll[i][cand] for cand, nc in c.items()}
        top = max(lp.values())
        z = sum(math.exp(v - top) for v in lp.values())
        post = sorted(((cand, math.exp(v - top) / z) for cand, v in lp.items()), key=lambda x: -x[1])
        guess = c.most_common(1)[0][0]


        mode = next(cand for cand, _ in post if cand[1][5] == guess[1][5])
        fits[i] = Fit(i, species[i], mode, guess, turns[i], post)
    return fits

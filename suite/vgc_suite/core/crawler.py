















from __future__ import annotations

import json
import random
import threading
import time
from pathlib import Path

import numpy as np
from vgc_trainer.amp import pick_device

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "trainer/runs/crawler"
CAP = 512
STATUS = ("", "brn", "frz", "par", "psn", "tox", "slp")
SITES = {1: "accuracy", 2: "crit", 3: "damage roll", 4: "secondary effect", 5: "flinch (King's Rock)", 6: "confusion",
         7: "full paralysis", 8: "confusion self-hit", 9: "sleep length", 10: "thaw", 11: "Quick Claw / Quick Draw"}
BOOSTS = ("Atk", "Def", "SpA", "SpD", "Spe", "acc", "eva")
PASS = 20
_MODELS: dict = {}
_LOCK = threading.Lock()


def _models(ckpt: Path, device: str):

    import torch
    from vgc_trainer.model import load_policy
    from .bundle import path as pinned
    key = (str(ckpt), device)
    if key not in _MODELS:
        dev = torch.device(device)
        pol = load_policy(torch.load(ckpt, map_location=dev, weights_only=True), dev).eval()
        bc = load_policy(torch.load(pinned("reply_policy"), map_location=dev, weights_only=True), dev).eval()
        _MODELS.clear()
        _MODELS[key] = (pol, bc, dev)
    return _MODELS[key]


def _check_pass() -> None:
    import vgc_engine as ve
    assert ve.PASS_ACTION == PASS, ve.PASS_ACTION


class Crawl:


    def __init__(self, data: dict, ckpt: Path, device: str | None = None):
        import vgc_engine as ve
        from vgc_trainer.env import VecEnv
        _check_pass()
        self.data = data
        self.ckpt, self.device = ckpt, device or pick_device().type
        brings = data["brings"]
        from vgc_suite.formats import engine
        efmt = engine(data.get("format"))
        self.env = VecEnv(1, teams=data["teams"], seed=data["seed"], pair_fn=lambda k: [[0, 1]] * k,
                          bring_fn=lambda idx, pairs: [brings] * len(idx), formats=[efmt, efmt] if efmt else None)
        self.cache = ve.BattlePool(CAP)
        self.tmp = ve.BattlePool(1)
        self.slot: dict[str, int] = {}
        self.lock = threading.Lock()
        self.ve = ve
        self.cache.copy_from(self.env.pool, [0], [0], [0])
        self.slot["0"] = 0
        data["nodes"].setdefault("0", {"parent": None, "seed": data["seed"], "actions": [], "kind": "start", "created": time.time()})


    def _inspect(self) -> dict:


        st = self.env.pool.inspect(0)
        for sd in st["sides"]:
            sd["active"] = list(sd["active"])[:2]
        return st

    def _load(self, nid: str) -> None:

        if nid not in self.slot:
            node = self.data["nodes"][nid]
            self._load(node["parent"])
            self._step(node)
            k = len(self.slot) if len(self.slot) < CAP else 1 + random.Random(nid).randrange(CAP - 1)
            for old in [n for n, s in self.slot.items() if s == k]:
                del self.slot[old]
            self.cache.copy_from(self.env.pool, [0], [k], [0])
            self.slot[nid] = k
            return
        self.env.pool.copy_from(self.cache, [self.slot[nid]], [0], [0])

    def _step(self, node: dict) -> dict:


        self.tmp.copy_from(self.env.pool, [0], [0], [int(node["seed"])])
        self.env.pool.copy_from(self.tmp, [0], [0], [int(node["seed"])])
        acts = [[[int(a), int(m)] for a, m in side] for side in node["actions"]]
        return self.env.pool.step_scripted(0, acts, [tuple(o) for o in node.get("overrides", [])])

    def state(self, nid: str) -> dict:
        with self.lock:
            self._load(nid)
            return self._inspect()


    def play(self, nid: str, actions: list, seed: int | None = None, overrides: list | None = None) -> str:



        seed = int(seed) if seed is not None else random.SystemRandom().randrange(1, 2**62)
        overrides = sorted([list(map(int, o)) for o in (overrides or [])])
        nodes = self.data["nodes"]
        for k, n in nodes.items():
            if n["parent"] == nid and n["actions"] == actions and n["seed"] == seed and n.get("overrides", []) == overrides:
                return k
        node = {"parent": nid, "seed": seed, "actions": actions, "overrides": overrides, "created": time.time()}
        with self.lock:
            self._load(nid)
            before = self._inspect()
            labels = self.labels(before)
            node["kind"] = "replace" if before["pending"] == "forced" else "turn"
            res = self._step(node)
            after = self._inspect()
        node["draws"] = [list(d) for d in res["draws"]]
        node["unused"] = [list(u) for u in res["unused"]]
        node["log"] = narrate(before, after, actions, labels) + dice_notes(before, node["draws"])
        nid2 = str(max(int(k) for k in nodes) + 1)
        nodes[nid2] = node
        return nid2

    def dice(self, nid: str) -> list[dict]:



        node = self.data["nodes"][nid]
        if node.get("parent") is None:
            return []
        with self.lock:
            self._load(node["parent"])
            before = self._inspect()
        out = []
        yes_no = {1: ("hit", "miss"), 2: ("crit", "no crit"), 4: ("yes", "no"), 5: ("flinch", "no flinch"), 6: ("confused", "not confused"),
                  7: ("fully paralyzed", "moves"), 8: ("hits itself", "acts"), 10: ("thaws", "stays frozen"), 11: ("goes first", "no")}
        for i, d in enumerate(node.get("draws", [])):
            site, actor, move_id, move, target, k, bound, num, rolled, result, forced = d
            row = {"i": i, "site": SITES.get(site, str(site)), "who": _pos(before, actor), "move": move, "target": _pos(before, target),
                   "k": k, "forced": forced, "key": [site, actor, move_id, target, k], "options": [], "value": result}
            if num is not None:
                yes, no = yes_no.get(site, ("yes", "no"))
                row["chance"] = f"1/{bound}" if site == 2 else f"{round(100 * num / bound)}%"
                row["outcome"] = yes if result < num else no
                row["current"] = 0 if result < num else bound - 1
                if 0 < num < bound:
                    row["options"] = [[0, yes], [bound - 1, no]]
            elif site == 9:
                row["outcome"] = "2 turns" if result == 0 else "3 turns"
                row["current"] = 0 if result == 0 else 1
                row["options"] = [[0, "2 turns"], [1, "3 turns"]]
            else:
                row["outcome"] = f"{100 - result}% roll"
                row["current"] = result
                row["options"] = [[0, "high (100%)"], [7, "average (93%)"], [15, "low (85%)"]]
                row["ko"] = self._ko_count(nid, d)
            out.append(row)
        return out

    def _ko_count(self, nid: str, draw: list) -> int | None:

        node = self.data["nodes"][nid]
        site, actor, move_id, _, target, k = draw[:6]
        base = [o for o in node.get("overrides", []) if o[:5] != [site, actor, move_id, target, k]]
        side, slot = divmod(target, 2)
        n = 0
        with self.lock:
            self._load(node["parent"])
            mi = self._inspect()["sides"][side]["active"][slot]
            for r in range(16):
                self._load(node["parent"])
                try:
                    self._step(dict(node, overrides=base + [[site, actor, move_id, target, k, r]]))
                except Exception:
                    return None
                if self._inspect()["sides"][side]["mons"][mi]["hp"] == 0:
                    n += 1
        return n


    def labels(self, st: dict) -> dict:

        from vgc_trainer.showdown.requests import describe_action
        env = self.env
        env.refresh()
        bits = env.masks.bits()[0]
        out = {}
        for side in (0, 1):
            s, o = st["sides"][side], st["sides"][1 - side]
            names = [m["species"] for m in s["mons"]]
            foe = [o["mons"][i]["species"] for i in o["active"]]
            out[side] = []
            for slot in (0, 1):
                me = s["mons"][s["active"][slot]]
                ally = s["mons"][s["active"][1 - slot]]["species"]
                legal = np.flatnonzero(bits[side, slot])
                out[side].append({int(a): describe_action(int(a), me["moves"], foe, ally, names) for a in legal})
        return out

    def evaluate(self, nid: str) -> dict:



        import torch
        from vgc_trainer.search import OneStepSearch
        from .bundle import live_searcher
        pol, bc, dev = _models(self.ckpt, self.device)
        from vgc_suite.formats import FORMATS, engine
        efmt = engine(self.data.get("format"))
        from vgc_trainer.closed_worlds import supported
        closed = efmt is not None and not FORMATS[efmt].open_sheets and supported()
        with _LOCK, self.lock, torch.inference_mode():
            self._load(nid)
            st = self._inspect()
            lab = self.labels(st)
            env = self.env
            res = {"state": st, "labels": {s: [{str(a): t for a, t in d.items()} for d in lab[s]] for s in (0, 1)}, "sides": {}}
            if st["pending"] == "over":
                return res
            mega = env.masks.mega[0].tolist()
            res["mega"] = mega
            for side in (0, 1):
                if not env.masks.to_move[0, side]:
                    continue
                if st["pending"] == "forced":
                    srch = OneStepSearch(pol, env, dev, k=8, m=8, seed=int(self.data["seed"]) & ((1 << 62) - 1), max_roots=1)
                    draws, _ = srch._sample(side, np.array([0]), 256, 1.0)
                    res["sides"][side] = {"policy": _shares(draws[0], lab[side]), "lines": [], "pick": _top(draws[0])}
                    continue
                sseed = (int(self.data["seed"]) + int(nid) * 7919 + side) & ((1 << 62) - 1)
                if closed:
                    from vgc_trainer.closed_worlds import ClosedSheetSearch

                    srch = ClosedSheetSearch(env, efmt, lambda w: live_searcher(pol, w, dev, sseed, bc, max_roots=1, hidden="true"), sseed)
                    srch.world.sync(side, np.array([0]))
                else:
                    srch = live_searcher(pol, env, dev, sseed, bc, max_roots=1)
                draws, _ = srch._sample(side, np.array([0]), 256, 1.0)
                cands, q, _ = srch.evaluate(side, np.array([0]))
                q1 = getattr(srch, "_last_q1", None)
                seen, lines = set(), []
                for i in np.argsort(-q[0]):
                    c = cands[0, i]
                    key = json.dumps(c.tolist())
                    if key in seen:
                        continue
                    seen.add(key)
                    lines.append({"actions": c.tolist(), "win": round((float(q[0, i]) + 1) / 2, 3),
                                  "win1": round((float(q1[0, i]) + 1) / 2, 3) if q1 is not None else None,
                                  "label": " · ".join(lab[side][s].get(int(c[s][0]), "?") + (" +mega" if c[s][1] else "") for s in (0, 1))})
                res["sides"][side] = {"policy": _shares(draws[0], lab[side]), "lines": lines, "pick": lines[0]["actions"] if lines else None}
            return res


    def save(self) -> None:
        DIR.mkdir(parents=True, exist_ok=True)
        (DIR / f"{self.data['id']}.json").write_text(json.dumps(self.data), encoding="utf8")


def _shares(draws: np.ndarray, lab: list[dict]) -> list[list]:

    out = []
    for slot in (0, 1):
        acts, cnt = np.unique(draws[:, slot, 0], return_counts=True)
        order = np.argsort(-cnt)
        out.append([[lab[slot].get(int(acts[i]), str(int(acts[i]))), round(float(cnt[i]) / len(draws), 3), int(acts[i])] for i in order[:6]])
    return out


def _top(draws: np.ndarray) -> list:
    keys, cnt = np.unique(draws.reshape(len(draws), -1), axis=0, return_counts=True)
    return keys[int(cnt.argmax())].reshape(2, 2).tolist()


def narrate(before: dict, after: dict, actions: list, labels: dict) -> list[str]:


    lines = []
    for side in (0, 1):
        s = before["sides"][side]
        if before["pending"] == "forced" and not before["forced"][side]:
            continue
        parts = []
        for slot in (0, 1):
            a, mg = actions[side][slot]
            if a == PASS:
                continue
            mon = s["mons"][s["active"][slot]]["species"]
            parts.append(f"{mon}: {labels[side][slot].get(int(a), str(a))}{' +mega' if mg else ''}")
        lines.append(f"{'AB'[side]} chose " + (" · ".join(parts) or "nothing"))
    n_new = (after["cursor"] - before["cursor"]) % 24 or (24 if after["turn"] != before["turn"] else 0)
    for kind, actor, target, subject, outcome, name in after["events"][-n_new:] if n_new else []:
        who = _mon(after, actor)
        if kind == 1:
            lines.append(f"{who} couldn't move" if outcome == -1 else f"{who} used {name}" + (f" -> {_mon(after, target)}" if target != 255 else ""))
        elif kind == 2:
            lines.append(f"{_side(actor)} sent in {who}" + (f" (for {_mon(after, target)})" if target != 255 else ""))
        elif kind == 3:
            lines.append(f"{who} fainted")
    for side in (0, 1):
        for k, (m0, m1) in enumerate(zip(before["sides"][side]["mons"], after["sides"][side]["mons"])):
            nm = f"{'AB'[side]}'s {m1['species']}"
            if m0["species"] != m1["species"]:
                lines.append(f"{'AB'[side]}'s {m0['species']} became {m1['species']}")
            if m0["hp"] != m1["hp"]:
                p0, p1 = 100 * m0["hp"] / m0["max_hp"], 100 * m1["hp"] / m1["max_hp"]
                lines.append(f"{nm} {p1 - p0:+.0f}% -> {p1:.0f}%")
            if m0["status"] != m1["status"]:
                lines.append(f"{nm} {('cured of ' + STATUS[m0['status']]) if not m1['status'] else STATUS[m1['status']]}")
            for i, (b0, b1) in enumerate(zip(m0["boosts"], m1["boosts"])):
                if b0 != b1 and m1["hp"]:
                    lines.append(f"{nm} {BOOSTS[i]} {b1 - b0:+d} (now {b1:+d})")
    f0, f1 = before["field"], after["field"]
    for key in ("weather", "terrain"):
        if f0[key] != f1[key]:
            lines.append(f"{key}: {f0[key]} -> {f1[key]}")
    if (f0["trick_room"] > 0) != (f1["trick_room"] > 0):
        lines.append("Trick Room " + ("up" if f1["trick_room"] else "ended"))
    for side in (0, 1):
        c0, c1 = before["sides"][side]["conds"], after["sides"][side]["conds"]
        for key in c1:
            if (c0[key] > 0) != (c1[key] > 0):
                lines.append(f"{'AB'[side]}'s {key.replace('_', ' ')} " + ("up" if c1[key] else "ended"))
    if after["pending"] == "over":
        w = after["winner"]
        lines.append("the game is over: " + ("a tie" if w is None else f"{'AB'[w]} won"))
    return lines


def dice_notes(before: dict, draws: list) -> list[str]:

    out = []
    for site, actor, _, move, target, _, bound, num, _, result, forced in draws:
        if num is None or not (0 < num < bound):
            continue
        hit = result < num
        f = " (set)" if forced else ""
        if site == 1 and not hit:
            out.append(f"{_pos(before, actor)}'s {move} missed {_pos(before, target)}{f}")
        elif site == 2 and hit:
            out.append(f"critical hit: {_pos(before, actor)}'s {move} on {_pos(before, target)}{f}")
        elif site in (4, 5, 6) and hit:
            out.append(f"{_pos(before, actor)}'s {move}: its {round(100 * num / bound)}% {SITES[site]} triggered on {_pos(before, target)}{f}")
        elif site == 7 and hit:
            out.append(f"{_pos(before, actor)} is fully paralyzed{f}")
        elif site == 8 and hit:
            out.append(f"{_pos(before, actor)} hit itself in its confusion{f}")
        elif site == 10 and hit:
            out.append(f"{_pos(before, actor)} thawed out{f}")
        elif site == 11 and hit:
            out.append(f"{_pos(before, actor)}'s Quick Claw / Quick Draw let it move first{f}")
    return out


def _pos(st: dict, pos: int) -> str:

    if pos == 255:
        return "?"
    side, slot = divmod(pos, 2)
    s = st["sides"][side]
    return f"{'AB'[side]}'s {s['mons'][s['active'][slot]]['species']}"


def _side(packed: int) -> str:
    return "AB"[packed // 4] if packed != 255 else "?"


def _mon(st: dict, packed: int) -> str:
    if packed == 255:
        return "?"
    return f"{'AB'[packed // 4]}'s {st['sides'][packed // 4]['mons'][packed % 4]['species']}"


_SESSIONS: dict[str, Crawl] = {}


def open_session(sid: str, ckpt: Path, device: str) -> Crawl | None:

    if sid not in _SESSIONS:
        f = DIR / f"{sid}.json"
        if not f.exists():
            return None
        _SESSIONS[sid] = Crawl(json.loads(f.read_text(encoding="utf8")), ckpt, device)
    return _SESSIONS[sid]


def new_session(teams: list[list[dict]], brings: list[list[int]], names: dict, ckpt: Path, device: str, fmt: str | None = None) -> Crawl:
    sid = time.strftime("%Y%m%d-%H%M%S-") + f"{random.SystemRandom().randrange(16**4):04x}"
    data = {"id": sid, "names": names, "teams": teams, "brings": brings, "seed": random.SystemRandom().randrange(1, 2**62),
            "nodes": {}, "created": time.time(), "format": fmt}
    c = Crawl(data, ckpt, device)
    _SESSIONS[sid] = c
    c.save()
    return c

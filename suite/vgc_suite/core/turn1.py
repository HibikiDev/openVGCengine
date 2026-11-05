














from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from .h2h_examples import LOCAL_PORT, ensure_local_server



def _turn1_lines(raw: list[str]) -> list[str]:

    out = []
    for ln in raw:
        if ln.startswith("|turn|2"):
            break
        if ln.startswith("|") and not ln.startswith(("|request|", "|c|", "|j|", "|l|", "|raw|", "|html|", "|uhtml")):
            out.append(ln)
    return out


def _outcome(lines: list[str]) -> dict:

    hp: dict[tuple[str, str], float] = {}
    species: dict[str, str] = {}
    first = None
    kos = []
    started = False

    def pct(x: str) -> float | None:
        if x.startswith("0"):
            return 0.0
        m = re.match(r"(\d+)/(\d+)", x)
        return 100 * int(m.group(1)) / int(m.group(2)) if m else None

    for ln in lines:
        p = ln.split("|")
        if len(p) < 3:
            continue
        kind = p[1]
        if kind == "turn":
            started = True
        if kind in ("switch", "drag", "replace") and len(p) > 4:
            slot = p[2][:3]
            species[slot] = p[3].split(",")[0]
            v = pct(p[4])
            if v is not None:
                hp[(slot[:2], species[slot])] = v
        elif kind == "move" and started and first is None:
            first = p[2][:2]
        elif kind in ("-damage", "-heal", "-sethp") and len(p) > 3 and p[2][:3] in species:
            v = pct(p[3])
            if v is not None:
                hp[(p[2][:2], species[p[2][:3]])] = v
        elif kind == "faint" and started:
            kos.append((p[2][:2], species.get(p[2][:3], p[2])))
    return {"first": first, "kos": kos, "hp": {k: round(v) for k, v in hp.items()}}


def _search_rows(trace: list[dict]) -> tuple[list | None, list[str] | None]:

    e = next((x for x in trace if x.get("turn") == 1 and x.get("search")), None)
    if e is None:
        e = next((x for x in trace if x.get("turn") == 1), None)
        return None, ([str(e.get("choice"))] if e else None)
    view = (e["search"].get("view") or {}).get("candidates") or []
    rows, seen, chosen = [], set(), None
    for labels, q, is_chosen in view:
        key = tuple(labels)
        if is_chosen and chosen is None:
            chosen = list(labels)
        if key not in seen:
            seen.add(key)
            rows.append((list(labels), float(q)))
    return rows, chosen


async def _pair(a, b, bring_a, bring_b, ckpt, n, device, seed, port, tag, full=False, force=(None, None), policy=(False, False),
                fmt: str | None = None) -> list[dict]:
    from vgc_suite.formats import FORMATS, MC, engine
    from vgc_trainer.showdown.agent import Agent
    from vgc_trainer.showdown.buddy_client import BuddyClient
    from vgc_trainer.showdown.live_search import SEARCH_ARMS, LiveSearch
    from .bundle import live_arm, path as pinned
    clients = []
    for name, sheet, bring, fz, raw in ((f"t1A{tag}", a, bring_a, force[0], policy[0]), (f"t1B{tag}", b, bring_b, force[1], policy[1])):
        efmt = engine(fmt)
        bfmt = (efmt or MC) + "buddy"
        c = BuddyClient(port, name, Agent(str(ckpt), device, seed=seed), sheet, fmt=bfmt, formats=[bfmt])
        c.closed_sheet_search = efmt is not None and not FORMATS[efmt].open_sheets
        c.teams = [sheet]
        c.request_timer = False
        c.force_bring = list(bring)
        c.stop_after_turn = None if full else 1
        c.force_turns = ({1: fz[0], **({2: fz[2]} if len(fz) > 2 and fz[2] else {})}) if fz else None
        c.live_search = LiveSearch(c.agent, 8, 8, seed=seed)
        c.live_search.load_reply_policy(str(pinned("reply_policy")))
        c.live_search.load_foe_preview(str(pinned("preview_head")))
        c.search_arms = [live_arm()]
        if raw:
            c.live_search = None
        clients.append(c)
    ca, cb = clients
    await ca.connect()
    await cb.connect()
    out, last = [], -1e9
    try:
        for g in range(n):
            wait = 10.5 - (time.monotonic() - last)
            if wait > 0:
                await asyncio.sleep(wait)
            last = time.monotonic()
            accept = asyncio.get_running_loop().create_task(cb.accept_one(timeout=40))
            try:
                battle_a = await ca.challenge(cb.username)
                battle_b = await accept
            except (RuntimeError, asyncio.TimeoutError) as e:
                accept.cancel()
                out.append({"error": f"sample {g + 1} did not start: {e}"})
                if "rejected" in str(e):
                    break
                continue
            ra, _ = await asyncio.wait_for(asyncio.gather(battle_a.done, battle_b.done), 900 if full else 300)
            me = next((ln.split("|")[2] for ln in ra.raw if ln.startswith("|player|") and len(ln.split("|")) > 3
                       and ln.split("|")[3] == ca.username), "p1")
            t1 = _turn1_lines(ra.raw)
            lines = [ln for ln in ra.raw if ln.startswith("|") and not ln.startswith(("|request|", "|c|", "|j|", "|l|"))] if full else t1
            out.append({"lines": lines, "t1": t1, "trace": battle_a.trace, "trace_b": battle_b.trace, "me": me, "a_name": ca.username,
                        "b_name": cb.username, "won": bool(full and ra.winner == ca.username), "turns": ra.turns if full else 1,
                        "game": g + 1})
            await ca.leave(battle_a)
            await cb.leave(battle_b)
    finally:
        for c in clients:
            try:
                await c.ws.close()
            except Exception:
                pass
    return out


async def _run(a, b, bring_a, bring_b, ckpt, n, device, seed, port, pairs, full=False, force=(None, None), policy=(False, False),
               fmt: str | None = None) -> list[dict]:
    tag = f"{random.Random(seed + time.time_ns()).randrange(100000):05d}"
    per = [n // pairs + (1 if i < n % pairs else 0) for i in range(pairs)]
    jobs = [_pair(a, b, bring_a, bring_b, ckpt, k, device, seed + 101 * i, port, f"{tag}{i}", full, force, policy, fmt)
            for i, k in enumerate(per) if k]
    out = []
    for part in await asyncio.gather(*jobs):
        out += part
    return out


def _mean(v: list[float]) -> int:
    return round(sum(v) / len(v))


def turn1_lab(a: list[dict], b: list[dict], bring_a: list[int], bring_b: list[int], ckpt: Path, n: int = 12, device: str = "cpu",
              seed: int = 0, port: int = LOCAL_PORT, pairs: int = 2, full: bool = False, force_a=None, force_b=None,
              policy_a: bool = False, policy_b: bool = False, fmt: str | None = None) -> dict:


    from .bundle import live_arm
    logging.getLogger("showdown").setLevel(logging.ERROR)
    missing = ensure_local_server(port)
    if missing:
        return {"error": f"turn-1 samples unavailable: {missing}"}
    try:
        games = asyncio.run(asyncio.wait_for(_run(a, b, bring_a, bring_b, ckpt, n, device, seed, port, pairs, full, (force_a, force_b),
                                                  (policy_a, policy_b), fmt),
                                             (300 + n * 300) if full else (120 + n * 60)))
    except Exception as e:
        return {"error": f"turn-1 samples unavailable ({type(e).__name__}: {e}) - is the local Showdown server running?"}
    games = [g for g in games if "lines" in g]
    if not games:
        return {"error": "no turn-1 sample finished"}
    def leads(sheet, bring):
        return [sheet[i].get("name") or sheet[i]["species"] for i in bring[:2]]

    def say(labels, who):
        return " · ".join(f"{w}: {x}" for w, x in zip(who, labels)) if len(labels) == len(who) else " · ".join(labels)

    who = {"a": leads(a, bring_a), "b": leads(b, bring_b)}
    forced = {"a": say(force_a[1], who["a"]) if force_a else None, "b": say(force_b[1], who["b"]) if force_b else None}
    sides = {}
    for key, tkey in (("a", "trace"), ("b", "trace_b")):
        if forced[key]:
            sides[key] = {"table": [], "chosen": [(forced[key], len(games))], "forced": True}
            continue
        q = defaultdict(list)
        chosen = Counter()
        for g in games:
            rows, pick = _search_rows(g[tkey])
            for labels, v in rows or []:
                q[say(labels, who[key])].append(v)
            if pick:
                chosen[say(pick, who[key])] += 1
        table = sorted(({"line": k, "q": round(sum(v) / len(v), 3), "seen": len(v), "chosen": chosen.get(k, 0)} for k, v in q.items()),
                       key=lambda r: (-r["chosen"], -r["q"]))
        sides[key] = {"table": table[:10], "chosen": chosen.most_common()}
    pairs_seen = Counter()
    outcomes = []
    for g in games:
        _, pa = _search_rows(g["trace"])
        _, pb = _search_rows(g["trace_b"])
        o = _outcome(g["t1"])
        a_side = g["me"]
        o["a_first"] = None if o["first"] is None else o["first"] == a_side
        o["a_kos"] = [sp for s, sp in o["kos"] if s != a_side]
        o["b_kos"] = [sp for s, sp in o["kos"] if s == a_side]
        o["a_hp"] = {sp: v for (side, sp), v in o["hp"].items() if side == a_side}
        o["b_hp"] = {sp: v for (side, sp), v in o["hp"].items() if side != a_side}
        line = (forced["a"] or (say(pa, who["a"]) if pa else "?"), forced["b"] or (say(pb, who["b"]) if pb else "?"))
        pairs_seen[line] += 1
        outcomes.append({"a": line[0], "b": line[1], "won": g["won"], "turns": g["turns"],
                         **{k: o[k] for k in ("a_first", "a_kos", "b_kos", "a_hp", "b_hp")}})
    by_pair = []
    for (la, lb), k in pairs_seen.most_common():
        sel = [o for o in outcomes if o["a"] == la and o["b"] == lb]
        mons_a = sorted({m for o in sel for m in o["a_hp"]})
        mons_b = sorted({m for o in sel for m in o["b_hp"]})
        by_pair.append({"a": la, "b": lb, "n": k,
                        "a_first": sum(1 for o in sel if o["a_first"]) / k,
                        "a_kos": Counter(m for o in sel for m in o["a_kos"]).most_common(),
                        "b_kos": Counter(m for o in sel for m in o["b_kos"]).most_common(),
                        "a_hp": {m: _mean([o["a_hp"][m] for o in sel if m in o["a_hp"]]) for m in mons_a},
                        "b_hp": {m: _mean([o["b_hp"][m] for o in sel if m in o["b_hp"]]) for m in mons_b},
                        "a_won": sum(o["won"] for o in sel), "turns": round(sum(o["turns"] for o in sel) / k, 1)})
    t2 = {}
    for key, tkey, fz in (("a", "trace", force_a), ("b", "trace_b", force_b)):
        if fz and len(fz) > 3 and fz[2]:
            used = sum(1 for g in games if any(e.get("turn") == 2 and e.get("forced") for e in g[tkey]))
            t2[key] = {"line": " · ".join(fz[3]), "applied": used}
    return {"n": len(games), "arm": live_arm()["name"], "turn2": t2, "policy": {"a": policy_a, "b": policy_b}, "sides": sides, "pairs": by_pair, "full": full, "a_won": sum(g["won"] for g in games),
            "examples": [{k: g[k] for k in ("lines", "trace", "trace_b", "me", "a_name", "b_name", "won", "turns", "game")} for g in games]}

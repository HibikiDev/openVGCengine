








from __future__ import annotations

import asyncio
import json
import random
from collections import Counter

import numpy as np
import torch
import websockets

COACH = "openvgccoach"
DEBUG = False


def _id(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum())


def _expected(d, side: str, runs: list[tuple[list, list[int]]]) -> list[dict]:




    from vgc_trainer.showdown.requests import PASS_ACTION
    from .core.labels import describe, mon
    import re
    foe = "p2" if side == "p1" else "p1"
    t = d.tracker
    shown = list(t.shown[foe])
    names = [d.foe_active[s] or "" for s in (0, 1)]
    moves = [[re.sub(r"(?<=[a-z])(?=[A-Z])", " ", mv) for mv in t.mons[foe][i].sheet.get("moves", [])] if i is not None else []
             for i in shown[:2]] + [[], []]
    mine = [d.active[s] or "" for s in (0, 1)]
    shares: list[dict[str, float]] = [{}, {}]
    for replies, foe_bring in runs:
        bring = [(d.sheets[foe][i].get("name") or d.sheets[foe][i]["species"]) for i in foe_bring]
        total = sum(w for _, w in replies) or 1.0
        for r, w in replies:
            for s, (a, m) in enumerate(r[:2]):
                if not names[s]:
                    continue
                if int(a) == PASS_ACTION:
                    continue
                lab = describe(int(a), moves[s], mine, names[1 - s], bring, bool(m)).replace(" -> ", " → ")[:80]
                shares[s][lab] = shares[s].get(lab, 0.0) + w / total / len(runs)
    return [{"mon": mon(names[s]), "top": [[lab, round(min(p, 1.0), 3)] for lab, p in sorted(sh.items(), key=lambda kv: -kv[1])[:3] if p >= 0.1]}
            for s, sh in enumerate(shares) if names[s] and sh]


def read_turn(lines: list[str], side: str, turn: int, agent, ls, ckpt: str, n: int = 2) -> dict | None:

    from vgc_suite.core.positions import closed_world, tracked_request
    from .core.analysis import calibrated_win, load_calibration, policy_view
    from .core.bundle import live_arm
    from .core.positions import walk
    from .core.replay import load_replay
    from .core.review import _line_label, _seed
    import time
    t0 = time.time()
    log = load_replay("\n".join(lines) + "\n")
    with torch.inference_mode():
        decs = [d for d in walk(log, side, keep=n > 0) if d.turn == turn]
        if DEBUG:
            print(f"coach: walk {time.time() - t0:.1f} s, {len(decs)} decision(s) at turn {turn}", flush=True)
        if not decs:
            return None
        d = decs[-1]
        v = policy_view(agent, d)
        if DEBUG:
            print(f"coach: policy view at {time.time() - t0:.1f} s", flush=True)
        cal = load_calibration(ckpt)
        win = calibrated_win(v["win"], d.turn, cal) if cal is not None else v["win"]
        from .core.labels import line_label, localize, mon
        slots = [{"mon": mon(s["mon"]) or "?", "top": [[localize(lab).replace(" -> ", " → ")[:80], round(p, 3)] for lab, p in s["top"][:3]]}
                 for s in v["slots"] if s]
        best, votes, alt, alt_votes, expect = None, 0, None, 0, []
        if n > 0:
            foe = "p2" if side == "p1" else "p1"
            picks, runs = [], []
            for i in range(n):
                sd = _seed("coach", lines[0] if lines else "", side, turn, i)
                ls.rng, ls.np_rng = random.Random(sd), np.random.default_rng(sd)
                try:
                    ls.choose(d.tracker, tracked_request(d, side), d.sheets[side], d.sheets[foe], d.bring, d.masks, d.ctx, None, None,
                              reply_temp=1.0, arm=live_arm(), **closed_world(d, foe))
                except Exception as e:
                    print(f"coach: turn {turn} without the search ({type(e).__name__}: {str(e)[:120]})", flush=True)
                    break
                q, cands = ls.last["q"], ls.last["cands"]
                picks.append(tuple(tuple(c) for c in cands[int(np.argmax(q))]))
                runs.append((ls.last.get("replies") or [], list(ls.last.get("foe_bring") or [])))
                if DEBUG:
                    print(f"coach: search {i + 1} done at {time.time() - t0:.1f} s", flush=True)
            if picks:
                ranked = Counter(picks).most_common(2)
                (top, votes), n = ranked[0], len(picks)
                best = line_label(_line_label(d, [(a, bool(m)) for a, m in top])).replace(" -> ", " → ")[:160]
                if len(ranked) > 1:
                    alt, alt_votes = line_label(_line_label(d, [(a, bool(m)) for a, m in ranked[1][0]])).replace(" -> ", " → ")[:160], ranked[1][1]
                slots = []
                try:
                    expect = _expected(d, side, runs)
                except Exception as e:
                    print(f"coach: no expectation for turn {turn}: {type(e).__name__}: {e}", flush=True)
            else:
                n = 0
    if DEBUG:
        print(f"coach: turn {turn} read in {time.time() - t0:.1f} s", flush=True)
    return {"turn": turn, "win": round(float(win), 3), "slots": slots, "best": best, "votes": votes, "alt": alt, "alt_votes": alt_votes,
            "foe": expect, "n": n, "guessed": bool(d.guessed)}


async def watch(port: int, user: str, agent, ls, ckpt: str, n: int = 2, find_for: float = 60.0, timeout: float = 3600.0,
                room: str | None = None) -> None:


    url = f"ws://127.0.0.1:{port}/showdown/websocket"
    side, lines, done_turns = None, [], set()
    known = room
    loop = asyncio.get_running_loop()
    async with websockets.connect(url, max_size=None) as ws:
        async def find() -> None:
            t0 = loop.time()
            while room is None and loop.time() - t0 < find_for:
                await ws.send(f"|/cmd userdetails {user}")
                await asyncio.sleep(2)

        finder = None

        async def run() -> None:
            nonlocal room, side, finder
            async for raw in ws:
                head, _, body = raw.partition("\n") if raw.startswith(">") else ("", "", raw)
                rid = head[1:] if head else ""
                if DEBUG:
                    print(f"coach: recv {raw[:160]!r}", flush=True)
                for line in body.split("\n"):
                    if line.startswith("|challstr|"):
                        await ws.send(f"|/trn {COACH}")
                    elif line.startswith("|updateuser|") and COACH in _id(line) and finder is None:
                        if known:
                            finder = asyncio.create_task(asyncio.sleep(0))
                            print(f"coach: joining {room} for {user}", flush=True)
                            await ws.send(f"|/join {room}")
                        else:
                            print(f"coach: signed in, looking for {user}'s battle", flush=True)
                            finder = asyncio.create_task(find())
                    elif line.startswith(("|error|", "|popup|")):
                        print(f"coach: server says {line[:160]}", flush=True)
                    elif line.startswith("|queryresponse|userdetails|") and room is None:
                        rooms = (json.loads(line.split("|", 3)[3]) or {}).get("rooms") or {}
                        battles = sorted((r.lstrip("*+%@#&~☆ ") for r in rooms if "battle-" in r), key=lambda r: int(r.rsplit("-", 1)[-1])
                                         if r.rsplit("-", 1)[-1].isdigit() else 0)
                        if battles:
                            room = battles[-1]
                            print(f"coach: joining {room} for {user}", flush=True)
                            await ws.send(f"|/join {room}")
                    elif rid and rid == room:
                        lines.append(line)
                        p = line.split("|")
                        if len(p) > 3 and p[1] == "player" and _id(p[3]) == _id(user):
                            side = p[2]
                        elif len(p) > 2 and p[1] == "turn" and side and p[2].isdigit():


                            latest[0] = (int(p[2]), list(lines))
                            wake.set()
                        elif len(p) > 1 and p[1] in ("win", "tie"):
                            print(f"coach: {user}'s game over ({len(lines)} lines, side {side}, {len(done_turns)} turns read)", flush=True)
                            return
                    elif rid and room and rid != room and DEBUG:
                        print(f"coach: other room {rid!r} (watching {room!r})", flush=True)

        latest: list = [None]
        wake = asyncio.Event()

        async def reader() -> None:
            while True:
                await wake.wait()
                wake.clear()
                turn, snap = latest[0]
                if turn in done_turns:
                    continue
                done_turns.add(turn)
                try:
                    panel = await loop.run_in_executor(None, read_turn, snap, side, turn, agent, ls, ckpt, n)
                except Exception as e:
                    print(f"coach: {user} turn {turn} no panel ({type(e).__name__}: {str(e)[:120]})", flush=True)
                    panel = None
                if panel is not None and latest[0][0] == turn:
                    await ws.send(f"{room}|/openvgccoach {json.dumps({'to': user, **panel})}")
                    print(f"coach: {user} turn {turn} panel sent ({room})", flush=True)

        reading = asyncio.create_task(reader())
        try:
            await asyncio.wait_for(run(), timeout)
        except asyncio.TimeoutError:
            pass
        finally:
            reading.cancel()
            if finder is not None:
                finder.cancel()

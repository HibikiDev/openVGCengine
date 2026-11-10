







from __future__ import annotations

from vgc_trainer import i18n
import asyncio
import logging
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCAL_PORT = 8000


def ensure_local_server(port: int = LOCAL_PORT) -> str | None:



    if port != LOCAL_PORT:
        return None
    from vgc_suite import buddy
    return buddy.start_server(ROOT)
BC_POLICY = None
PREVIEW_HEAD = None


async def _play(a: list[dict], b: list[dict], ckpt: Path, n: int, deep: bool, device: str, seed: int, port: int,
                bo3: bool = False, progress=None, g1_bring_a: list[int] | None = None, fmt: str | None = None) -> list[dict]:
    from vgc_suite.formats import CURRENT, FORMATS, engine
    from vgc_trainer.showdown.agent import Agent
    from vgc_trainer.showdown.buddy_client import BuddyClient
    from vgc_trainer.showdown.live_search import SEARCH_ARMS, LiveSearch



    efmt = engine(fmt)
    reg = fmt or CURRENT
    bfmt = (efmt or reg) + "buddy"
    bo3_twin = reg + "bo3buddy"
    series_fmt = bo3_twin if efmt is None else f"{bfmt}@@@Best Of = 3"

    tag = f"{random.Random(seed + time.time_ns()).randrange(100000):05d}"
    clients = []
    for name, sheet in ((f"h2hA{tag}", a), (f"h2hB{tag}", b)):
        c = BuddyClient(port, name, Agent(str(ckpt), device, seed=seed), sheet, fmt=bfmt, formats=[bfmt])
        c.teams = [sheet]
        c.request_timer = False
        if bo3:
            c.format = series_fmt
            c.formats = {bo3_twin if efmt is None else bfmt}

            from .bundle import path as pinned_
            c.lead_arms = ["v3"]
            c.lead_preview = c.agent.load_preview_head(str(PREVIEW_HEAD or pinned_("preview_head")))
        if deep:
            c.live_search = LiveSearch(c.agent, 8, 8, seed=seed)
            from .bundle import live_arm, path as pinned
            c.live_search.load_reply_policy(str(BC_POLICY or pinned("reply_policy")))
            c.live_search.load_foe_preview(str(PREVIEW_HEAD or pinned("preview_head")))
            c.search_arms = [live_arm()]

            c.closed_sheet_search = efmt is not None and not FORMATS[efmt].open_sheets
        clients.append(c)
    ca, cb = clients
    ca.g1_bring = list(g1_bring_a) if g1_bring_a is not None else None
    await ca.connect()
    await cb.connect()
    out = []
    last = -1e9
    try:
        for g in range(n):
            if progress is not None:
                progress(i18n.t("Example series {n} of {total}", n=g + 1, total=n) if bo3
                         else i18n.t("Example game {n} of {total}", n=g + 1, total=n), g, n, "examples")
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
                out.append({"error": f"game {g + 1} did not start: {e}"})
                if "rejected" in str(e):
                    break
                continue
            rooms, wins, game = [], [0, 0], 1
            while True:
                ra, _ = await asyncio.wait_for(asyncio.gather(battle_a.done, battle_b.done), 900)
                me = next((ln.split("|")[2] for ln in ra.raw if ln.startswith("|player|") and len(ln.split("|")) > 3
                           and ln.split("|")[3] == ca.username), "p1")
                out.append({"lines": [ln for ln in ra.raw if ln.startswith("|") and not ln.startswith(("|request|", "|c|", "|j|", "|l|"))],
                            "trace": battle_a.trace, "me": me, "a_name": ca.username, "b_name": cb.username,
                            "won": ra.winner == ca.username, "turns": ra.turns, "errors": len(ra.errors),
                            "series": g + 1 if bo3 else None, "game": game if bo3 else None})
                rooms.append((battle_a, battle_b))
                wins[0 if ra.winner == ca.username else 1] += 1 if ra.winner else 0
                if not bo3 or max(wins) >= 2 or game >= 3:
                    break

                game += 1
                battle_a = await asyncio.wait_for(ca.new_battle.get(), 180)
                battle_b = await asyncio.wait_for(cb.new_battle.get(), 180)
            for ba, bb in rooms:
                await ca.leave(ba)
                await cb.leave(bb)
    finally:
        for c in clients:
            try:
                await c.ws.close()
            except Exception:
                pass
    return out


def game_summary(lines: list[str]) -> dict:


    seat = {}
    for ln in lines:
        p = ln.split("|")
        if len(p) > 3 and p[1] == "player" and p[3]:
            seat[p[2]] = "a" if p[3].startswith("h2hA") else "b"
    leads, brought = {"a": [], "b": []}, {"a": [], "b": []}
    turn = 0
    for ln in lines:
        p = ln.split("|")
        if len(p) > 1 and p[1] == "turn":
            turn += 1
        if len(p) > 3 and p[1] in ("switch", "drag") and len(p[2]) > 2 and p[2][:2] in seat:
            side, species = seat[p[2][:2]], p[3].split(",")[0]
            if species not in brought[side]:
                brought[side].append(species)
            if turn == 0 and len(leads[side]) < 2:
                leads[side].append(species)
    return {"leads": leads, "brought": brought}


def play_examples(a: list[dict], b: list[dict], ckpt: Path, n: int = 3, deep: bool = False, device: str = "cpu", seed: int = 0,
                  port: int = LOCAL_PORT, bo3: bool = False, progress=None, g1_bring_a: list[int] | None = None,
                  fmt: str | None = None) -> list[dict]:




    logging.getLogger("showdown").setLevel(logging.ERROR)
    missing = ensure_local_server(port)
    if missing:
        return [{"error": f"example games unavailable: {missing}"}]
    try:
        return asyncio.run(asyncio.wait_for(_play(a, b, ckpt, n, deep, device, seed, port, bo3, progress, g1_bring_a, fmt),
                                            60 + n * (2700 if bo3 else 900)))
    except Exception as e:
        return [{"error": f"example games unavailable ({type(e).__name__}: {e}) - is the local Showdown server running?"}]

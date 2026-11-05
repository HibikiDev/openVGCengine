









from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "trainer"))
sys.path.insert(0, str(ROOT / "suite"))
from vgc_suite.core.models import newest_checkpoint
from vgc_suite.core.teams import lookup_team
from vgc_trainer.showdown.agent import Agent
from vgc_trainer.showdown.buddy_client import BuddyClient

BOT, ME = "BuddyBot", "BuddyTester"
FMT = "gen9championsvgc2026regmcbuddy"


async def main() -> None:
    ckpt = str(newest_checkpoint())
    logs = ROOT / "trainer/runs/buddy_host_test"
    logs.mkdir(parents=True, exist_ok=True)
    for f in ("profiles.json", "results.jsonl", "notes.jsonl"):
        (logs / f).unlink(missing_ok=True)
    host = subprocess.Popen([sys.executable, "-u", str(ROOT / "trainer/scripts/buddy_host.py"), "--checkpoint", ckpt, "--team", "BR-111",
                             "--username", BOT, "--buddy-profiles", str(logs / "profiles.json"), "--buddy-notes", str(logs / "notes.jsonl"),
                             "--search", "off", "--logs", str(logs), "--results", str(logs / "results.jsonl"), "--join-rooms", ""],
                            env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, checks = "", {}
    try:
        await asyncio.sleep(15)
        me = BuddyClient(8000, ME, Agent(ckpt, "cpu"), lookup_team("BA-427"), fmt=FMT)
        await me.connect()
        from vgc_suite.buddy import Buddy
        page = Buddy(logs / "profiles.json")
        replies = {cmd: page.handle(ME, cmd) for cmd in (".team FR-12", ".sheets off", ".status")}
        for cmd, r in replies.items():
            print(f"  {cmd!r:16} -> {r}")
        checks["commands"] = bool(replies[".team FR-12"] and "FR-12" in replies[".team FR-12"] and replies[".status"]
                                  and "FR-12" in replies[".status"])
        battle = await me.challenge(BOT)
        result = await asyncio.wait_for(battle.done, 600)
        await asyncio.sleep(40)
        lines = list(result.raw)
        bot_side = next((ln.split("|")[2] for ln in lines if ln.startswith("|player|") and BOT.lower() in ln.lower()), None)
        species = {ln.split("|")[3].split(",")[0].split("-")[0] for ln in lines if ln.startswith("|poke|") and ln.split("|")[2] == bot_side}
        checks["team"] = species == {s["species"].split("-")[0] for s in lookup_team("FR-12")}
        checks["sheets declined"] = "|showteam|" not in "\n".join(lines)
        rows = [json.loads(x) for x in (logs / "results.jsonl").read_text(encoding="utf8").splitlines() if x.strip()]
        checks["result row"] = bool(rows) and rows[-1]["room"] == battle.room and rows[-1]["buddy"] is True
        checks["note"] = (logs / "notes.jsonl").exists() and battle.room in (logs / "notes.jsonl").read_text(encoding="utf8")

        me.format = "gen9championsvgc2026regmc"
        try:
            await me.challenge(BOT, timeout=20)
            checks["plain format refused"] = False
        except RuntimeError:
            checks["plain format refused"] = True
        await me.ws.close()
    finally:
        host.terminate()
        try:
            out = host.communicate(timeout=10)[0]
        except subprocess.TimeoutExpired:
            host.kill()
            out = host.communicate()[0]
    for k, v in checks.items():
        print(f"  {k:22s} {'ok' if v else 'FAILED'}")
    ok = len(checks) == 6 and all(checks.values())
    print("BUDDY HOST TEST", "PASSED" if ok else "FAILED")
    if not ok:
        print("--- host output (tail) ---")
        for ln in out.splitlines()[-20:]:
            print(ln)


if __name__ == "__main__":
    asyncio.run(main())

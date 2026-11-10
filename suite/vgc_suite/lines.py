








from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "trainer/runs/buddy_server/logs"
OUT = ROOT / "trainer/runs/practise_lines"
NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}


def game_file(room: str) -> Path | None:

    name = room.removeprefix("battle-") + ".log.json"
    hits = sorted(LOGS.rglob(name)) if LOGS.exists() else []
    return hits[-1] if hits else None


def info(room: str) -> dict | None:

    f = game_file(room)
    if f is None:
        return None
    try:
        d = json.loads(f.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return None
    if not d.get("inputLog") or not d.get("turns"):
        return None
    return {"turns": int(d["turns"]), "players": {"p1": d.get("p1"), "p2": d.get("p2")}, "format": d.get("format")}


PID = OUT / "line.pid"


def _stop_previous() -> None:


    try:
        pid = int(PID.read_text().strip())
    except (OSError, ValueError):
        return
    try:
        if os.name == "nt":
            q = f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"
            cmd = subprocess.run(["powershell", "-NoProfile", "-Command", q], capture_output=True, text=True, errors="replace",
                                 timeout=30, **NO_WINDOW).stdout or ""
            if "practise_line.py" in cmd:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=30, **NO_WINDOW)
        else:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace") if Path(f"/proc/{pid}/cmdline").exists() else ""
            if "practise_line.py" in cmd:
                os.kill(pid, 15)
    except (OSError, subprocess.SubprocessError):
        pass
    PID.unlink(missing_ok=True)


def start(room: str, turn: int, me: str, side: str, same_first: bool, device: str) -> tuple[bool, str]:


    f = game_file(room)
    if f is None:
        return False, "This game was played before games were saved with their choices, so it can't be reopened."
    if not shutil.which("node"):
        return False, "Reopening a game needs Node.js on this PC's PATH (it replays the game in Showdown's simulator)."
    from .buddy import practice_pid
    if practice_pid(ROOT) is None:
        return False, "Start the practice bot on the Buddy page first: it plays the reopened game."
    OUT.mkdir(parents=True, exist_ok=True)
    _remember(me)
    _launch(f"{room}-t{turn}", [str(f), "--turn", str(turn), "--me", me, "--side", side, "--device", device,
                                "--kind", "game", "--back", f"/status/game/{room}?pov=human"] + (["--force-first"] if same_first else []))
    how = "repeats its original choice on that turn, then decides fresh" if same_first else "decides fresh from that turn"
    return True, (f"Turn {turn} is opening on the local Showdown: accept the invite from openvgchost there, signed in as {me}. "
                  f"The bot {how}.")


def _launch(tag: str, args: list[str]) -> None:

    OUT.mkdir(parents=True, exist_ok=True)
    _stop_previous()
    log = OUT / f"{tag}-{time.strftime('%H%M%S')}.out"
    cmd = [sys.executable, "-u", str(ROOT / "tools/buddy/practise_line.py")] + args
    with open(log, "w", encoding="utf8") as out:
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **NO_WINDOW)
    PID.write_text(str(p.pid), encoding="utf8")


REPLAYS = OUT / "replays"
LAST_NAME = OUT / "last_name.txt"


def default_name() -> str:


    try:
        name = LAST_NAME.read_text(encoding="utf8").strip()
        if name:
            return name
    except OSError:
        pass
    from .buddy import PRACTICE
    try:
        profiles = json.loads((ROOT / PRACTICE["profiles"]).read_text(encoding="utf8"))
    except (OSError, ValueError):
        return ""
    return max(profiles, key=lambda u: profiles[u].get("games", 0), default="")


def _remember(name: str) -> None:
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        LAST_NAME.write_text(name, encoding="utf8")
    except OSError:
        pass


def replay_key(src: str) -> str:

    if src.startswith(("http://", "https://")):
        return src
    import hashlib
    return f"{hashlib.sha1(src.encode('utf8')).hexdigest()[:16]}.log"


def crawl_key(crawl_id: str, nid: str) -> str:

    return f"crawl-{crawl_id}-{nid}.spec.json"


def branches(key: str) -> list[dict]:


    from .buddy_sessions import BOTS, _results
    from vgc_trainer.showdown.tracker import to_id
    out = []
    for bot in BOTS:
        for r in _results(ROOT, bot):
            ln = r.get("line") or {}
            if ln.get("from") != key:
                continue
            won = None if not r.get("winner") else to_id(r["winner"]) == to_id(r.get("opponent") or "")
            out.append({"room": r["room"], "time": r["time"][5:16], "turn": ln.get("turn"), "mode": ln.get("mode"),
                        "side": ln.get("side"), "me": r.get("opponent"), "won": won, "turns": r.get("turns")})
    return sorted(out, key=lambda b: b["time"])


def line_of(room: str) -> dict | None:

    from .buddy_sessions import BOTS, _results
    for bot in BOTS:
        for r in _results(ROOT, bot):
            if r["room"] == room and r.get("line"):
                return r["line"]
    return None


def origin(line: dict | None) -> dict | None:


    if not line:
        return None
    src = line.get("from") or ""
    kind = line.get("kind") or ("crawl" if src.startswith("crawl-") else "replay" if line.get("replay") else "game")
    href = line.get("back")
    if href is None:
        if kind == "game":
            href = f"/status/game/{src}?pov=human"
        elif kind == "crawl":
            cid, _, nid = src.removeprefix("crawl-").removesuffix(".spec.json").rpartition("-")
            href = f"/crawler/s/{cid}?n={nid}"
        elif src.startswith(("http://", "https://")):
            href = src
    label = {"game": "a practice game", "replay": "a replay", "crawl": "a Line Crawler position"}[kind]
    return {"kind": kind, "href": href, "label": label, "turn": line.get("turn")}


def start_replay(src: str, turn: int, me: str, side: str, device: str, back: str | None = None) -> tuple[bool, str]:



    if not shutil.which("node"):
        return False, "Opening a replay's position needs Node.js on this PC's PATH (the local Showdown runs on it)."
    from .buddy import practice_pid
    if practice_pid(ROOT) is None:
        return False, "Start the practice bot on the Buddy page first: it plays the position."
    if not src.startswith(("http://", "https://")):
        REPLAYS.mkdir(parents=True, exist_ok=True)
        f = REPLAYS / replay_key(src)
        f.write_text(src, encoding="utf8")
        src = str(f)
    _remember(me)
    _launch(f"replay-t{turn}", [src, "--replay", "--turn", str(turn), "--me", me, "--side", side, "--device", device, "--kind", "replay"]
            + (["--back", back] if back else []))
    return True, (f"Turn {turn} is being rebuilt from the replay and opened on the local Showdown (it takes a moment): accept the invite "
                  f"from openvgchost there, signed in as {me}. Approximate - guessed spreads and unseen sets, HP to the percent, a new "
                  f"seed. The bot decides fresh.")


def start_crawl(crawl, nid: str, me: str, side: str, device: str) -> tuple[bool, str]:



    if not shutil.which("node"):
        return False, "Opening a position needs Node.js on this PC's PATH (the local Showdown runs on it)."
    from .buddy import practice_pid
    if practice_pid(ROOT) is None:
        return False, "Start the practice bot on the Buddy page first: it plays the position."
    import json
    from .core.crawl_position import build
    try:
        spec, notes = build(crawl, nid, {"p1": "p1", "p2": "p2"})
    except ValueError as e:
        return False, str(e)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / crawl_key(crawl.data["id"], nid)
    f.write_text(json.dumps({"spec": spec, "notes": notes}), encoding="utf8")
    _remember(me)
    _launch(f"crawl-{nid}", [str(f), "--replay", "--turn", str(spec["turn"]), "--me", me, "--side", side, "--device", device,
                             "--kind", "crawl", "--back", f"/crawler/s/{crawl.data['id']}?n={nid}"])
    return True, (f"This position is being opened on the local Showdown (it takes a moment): accept the invite from openvgchost "
                  f"there, signed in as {me}. The engine's own state - HP, status, boosts, PP, items, the field - with a new seed; "
                  f"the bot decides fresh.")

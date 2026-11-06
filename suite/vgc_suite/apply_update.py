









from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

KEEP = {".venv", "runtime", "sprites", "replays"}
SHIPPED_RUNS = {"buddy_server", "set_prior"}
SERVER = "trainer/runs/buddy_server"
SERVER_STATE = ("logs", "config", "databases")
WIN = sys.platform == "win32"
RETRY_S = 30


class Failed(Exception):
    pass


def say(text: str) -> None:


    try:
        print(text, flush=True)
    except (OSError, ValueError):
        try:
            sys.stdout = open("CONOUT$", "w", encoding="utf8", buffering=1)
            print(text, flush=True)
        except (OSError, ValueError):
            pass


def moves_of(stage: Path) -> list[str]:

    out = []
    for e in sorted(stage.iterdir(), key=lambda p: p.name):
        if e.name in KEEP:
            continue
        if e.name != "trainer":
            out.append(e.name)
            continue
        for c in sorted(e.iterdir(), key=lambda p: p.name):
            if c.name != "runs":
                out.append(f"trainer/{c.name}")
                continue
            out += [f"trainer/runs/{r.name}" for r in sorted(c.iterdir(), key=lambda p: p.name) if r.name in SHIPPED_RUNS]
    return out


class Swap:
    def __init__(self, root: Path):
        self.root = root
        self.dir = root / "trainer/runs/update"
        self.stage = self.dir / "stage/openVGCengine"
        self.old = self.dir / "old"
        self.journal = self.dir / "journal.json"
        self.result = self.dir / "result.json"

    def log(self, text: str) -> None:
        say(text)
        with open(self.dir / "apply.log", "a", encoding="utf8") as f:
            f.write(time.strftime("%H:%M:%S ") + text + "\n")

    def write_json(self, path: Path, data: dict) -> None:
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf8") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def begin(self) -> None:

        if self.journal.exists():
            raise Failed("an update is still unfinished")
        shutil.rmtree(self.old, ignore_errors=True)
        self.result.unlink(missing_ok=True)

    def state(self) -> dict:
        return json.loads(self.journal.read_text(encoding="utf8"))

    def rename(self, a: Path, b: Path) -> None:
        b.parent.mkdir(parents=True, exist_ok=True)
        end = time.time() + RETRY_S
        while True:
            try:
                os.replace(a, b)
                return
            except OSError as e:
                if time.time() > end:
                    raise Failed(f"{a.name} is in use ({e})") from e
                time.sleep(0.5)

    def forward(self, rel: str) -> None:

        r, o, s = self.root / rel, self.old / rel, self.stage / rel
        if not s.exists():
            if not r.exists():
                raise Failed(f"{rel}: neither the new nor the installed copy is there")
            return
        if r.exists():
            if o.exists():
                raise Failed(f"{rel}: already set aside once")
            self.rename(r, o)
        self.rename(s, r)
        if rel == SERVER and o.exists():
            self.carry_server(o, r)

    def backward(self, rel: str, fresh: bool) -> None:

        r, o, s = self.root / rel, self.old / rel, self.stage / rel
        if o.exists():
            if r.exists():
                if s.exists():
                    shutil.rmtree(r, ignore_errors=True) if r.is_dir() else r.unlink()
                else:
                    self.rename(r, s)
            self.rename(o, r)
        elif fresh and r.exists() and not s.exists():
            self.rename(r, s)

    def carry_server(self, old: Path, new: Path) -> None:

        for sub in SERVER_STATE:
            for f in (old / sub).rglob("*") if (old / sub).is_dir() else ():
                t = new / f.relative_to(old)
                if f.is_file() and not t.exists():
                    t.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, t)

    def stop_others(self) -> None:

        me, prefix = os.getpid(), str(self.root).rstrip("\\/") + os.sep
        if WIN:
            ps = "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath } | ForEach-Object { \"$($_.ProcessId)`t$($_.ExecutablePath)\" }"
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, errors="replace", timeout=60).stdout
        else:
            out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, errors="replace", timeout=60).stdout
        for line in (out or "").splitlines():
            pid, _, exe = line.strip().replace("\t", " ").partition(" ")
            if pid.isdigit() and int(pid) != me and exe.strip().lower().startswith(prefix.lower()):
                self.log(f"stopping {exe.strip()[:80]}")
                if WIN:
                    subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True, timeout=30)
                else:
                    subprocess.run(["kill", "-9", pid], capture_output=True, timeout=30)

    def setup(self) -> None:

        log = open(self.dir / "setup.out", "w", encoding="utf8")
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.root / "setup.ps1")] if WIN else ["bash", str(self.root / "setup.command")]
        with log:
            code = subprocess.run(cmd, cwd=self.root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=7200).returncode
        if code:
            raise Failed(f"setup failed (exit {code}): see trainer/runs/update/setup.out")

    def check(self) -> None:

        py = self.root / (".venv/Scripts/python.exe" if WIN else ".venv/bin/python")
        code = "import sys; sys.path[:0] = ['suite', 'suite/web', 'trainer']; import server"
        r = subprocess.run([str(py), "-c", code], cwd=self.root, capture_output=True, text=True, errors="replace", timeout=300)
        if r.returncode:
            raise Failed("the new version doesn't start: " + r.stderr.strip()[-300:])

    def run(self, st: dict) -> None:
        if st["phase"] == "rollback":
            raise Failed(st.get("error") or "an earlier update failed")
        for rel in st["moves"]:
            self.forward(rel)
        st["phase"] = "setup"
        self.write_json(self.journal, st)
        self.log("running setup")
        self.setup()
        self.check()

    def roll_back(self, st: dict, why: str) -> None:
        self.log(f"rolling back: {why}")
        st.update(phase="rollback", error=why)
        self.write_json(self.journal, st)
        for rel in reversed(st["moves"]):
            self.backward(rel, rel in st["fresh"])
        if st.get("ran_setup"):
            try:
                self.setup()
            except Exception as e:
                why += f"; setup after the rollback: {e}"
        self.journal.unlink()
        self.write_json(self.result, {"ok": False, "version": st["version"], "error": why})

    def go(self, st: dict) -> bool:
        try:
            self.run(st)
        except Exception as e:
            st["ran_setup"] = st.get("phase") == "setup"
            self.roll_back(st, str(e))
            return False
        self.journal.unlink()
        self.write_json(self.result, {"ok": True, "version": st["version"]})
        self.log(f"updated to {st['version']}")
        return True

    def start_app(self) -> None:
        if WIN:
            subprocess.Popen(["cmd", "/c", str(self.root / "openVGCengine.cmd")], cwd=self.root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(["open", str(self.root / "openVGCengine.command")], cwd=self.root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_exit(pid: int, seconds: float) -> None:
    end = time.time() + seconds
    if WIN:
        import ctypes
        k = ctypes.windll.kernel32
        k.OpenProcess.restype = ctypes.c_void_p
        h = k.OpenProcess(0x00100000, False, pid)
        if h:
            k.WaitForSingleObject(ctypes.c_void_p(h), int(seconds * 1000))
            k.CloseHandle(ctypes.c_void_p(h))
        return
    while time.time() < end:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.2)


def lock(path: Path, wait: float):

    f = open(path, "a+")
    end = time.time() + wait
    while True:
        try:
            if WIN:
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            if time.time() > end:
                raise
            time.sleep(1)


def base_python() -> str:

    base = Path(sys.base_prefix)
    return str(base / "python.exe") if WIN else str(base / "bin/python3")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pid", type=int)
    ap.add_argument("--version", default="?")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    if sys.prefix != sys.base_prefix:
        return subprocess.run([base_python(), *sys.argv]).returncode
    sw = Swap(Path(a.root).resolve())
    held = lock(sw.dir / "apply.lock", 7200 if a.resume else 0)
    if a.resume:
        if sw.journal.exists():
            sw.log("resuming an update that was cut off")
            sw.go(sw.state())
        held.close()
        return 0
    try:
        say("Updating openVGCengine. This window closes when it's done; the app then reopens.")
        if a.pid:
            wait_exit(a.pid, 60)
        sw.stop_others()
        sw.begin()
        moves = moves_of(sw.stage)
        st = {"version": a.version, "phase": "swap", "moves": moves, "fresh": [m for m in moves if not (sw.root / m).exists()]}
        sw.write_json(sw.journal, st)
        sw.go(st)
    except Exception as e:
        sw.log("the update stopped: " + traceback.format_exc()[-800:])
        if not sw.journal.exists():
            sw.write_json(sw.result, {"ok": False, "version": a.version, "error": str(e) or type(e).__name__})
    held.close()
    sw.start_app()
    return 0


if __name__ == "__main__":
    sys.exit(main())

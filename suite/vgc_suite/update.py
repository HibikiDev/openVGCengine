



from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from . import __version__, about

ROOT = about.ROOT
DIR = ROOT / "trainer/runs/update"
HOSTS = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}
TOP = "openVGCengine"
STATE: dict = {"phase": "idle"}
LAST: dict = {}
_lock = threading.Lock()


class Refused(Exception):
    pass


class _Hosts(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _allowed(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _allowed(url: str) -> None:
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.hostname not in HOSTS:
        raise Refused(f"the download went to {u.hostname or url!r}, not GitHub")


def fetch(url: str, dest: Path, size: int, sha256: str, on_bytes=None, opener=None) -> None:

    if opener is None:
        _allowed(url)
        opener = urllib.request.build_opener(_Hosts)
    h, got = hashlib.sha256(), 0
    req = urllib.request.Request(url, headers={"User-Agent": f"openVGCengine/{__version__}"})
    with opener.open(req, timeout=60) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            got += len(chunk)
            if got > size:
                raise Refused("the download is bigger than the release says")
            h.update(chunk)
            f.write(chunk)
            if on_bytes:
                on_bytes(got)
    if got != size:
        raise Refused(f"the download stopped at {got:,} of {size:,} bytes")
    if h.hexdigest() != sha256:
        raise Refused("the download doesn't match the release's checksum")


def safe_extract(zf: Path, dest: Path) -> None:

    base = dest.resolve()
    with zipfile.ZipFile(zf) as z:
        for i in z.infolist():
            name = i.filename.replace("\\", "/")
            mode = i.external_attr >> 16
            if name.startswith("/") or ".." in name.split("/") or ":" in name or (mode and stat.S_ISLNK(mode)):
                raise Refused(f"the zip has an unsafe entry: {i.filename!r}")
            if not (base / name).resolve().is_relative_to(base):
                raise Refused(f"the zip has an unsafe entry: {i.filename!r}")
        for i in z.infolist():
            out = Path(z.extract(i, base))
            if i.external_attr >> 16 & 0o111 and sys.platform != "win32":
                out.chmod(out.stat().st_mode | 0o755)


def check_stage(stage: Path, version: str, platform_id: str) -> None:

    try:
        b = json.loads((stage / "bundle.json").read_text(encoding="utf8"))
    except (OSError, ValueError) as e:
        raise Refused("the zip isn't an openVGCengine package") from e
    if b.get("version") != version or b.get("platform") != platform_id:
        raise Refused(f"the zip is {b.get('version')} for {b.get('platform')}, not {version} for {platform_id}")
    if not (stage / "suite/vgc_suite/apply_update.py").is_file():
        raise Refused("the zip has no update helper")


def room_needed(zf_size: int, unpacked: int) -> int:
    return zf_size + 2 * unpacked


def _set(**kw) -> None:
    with _lock:
        STATE.clear()
        STATE.update(kw)


def status() -> dict:
    with _lock:
        return dict(STATE)


def _run(asset: dict, version: str, platform_id: str, opener=None) -> None:
    try:
        if shutil.disk_usage(ROOT).free < room_needed(asset["size"], 3 * asset["size"]):
            raise Refused("not enough free disk space for the update")
        shutil.rmtree(DIR / "stage", ignore_errors=True)
        DIR.mkdir(parents=True, exist_ok=True)
        zf = DIR / "update.zip"
        _set(phase="download", version=version, done=0, total=asset["size"])
        fetch(asset["url"], zf, asset["size"], asset["sha256"], lambda n: STATE.update(done=n), opener)
        _set(phase="check", version=version)
        with zipfile.ZipFile(zf) as z:
            unpacked = sum(i.file_size for i in z.infolist())
        if shutil.disk_usage(ROOT).free < 2 * unpacked:
            raise Refused("not enough free disk space for the update")
        safe_extract(zf, DIR / "stage")
        zf.unlink()
        check_stage(DIR / "stage" / TOP, version, platform_id)
        _set(phase="ready", version=version)
    except (Refused, OSError, zipfile.BadZipFile, urllib.error.URLError, ValueError) as e:
        shutil.rmtree(DIR / "stage", ignore_errors=True)
        (DIR / "update.zip").unlink(missing_ok=True)
        _set(phase="error", error=str(e) if isinstance(e, Refused) else f"The download failed ({type(e).__name__}). Nothing was changed.")


def start() -> dict:

    if status()["phase"] in ("download", "check"):
        return status()
    info = about.check_update()
    if info.get("error") or not info.get("newer") or not info.get("asset"):
        return {"phase": "error", "error": info.get("error") or "There's no update to install here."}
    platform_id = about.bundle_info().get("platform")
    s = status()
    if s["phase"] == "ready" and s.get("version") == info["latest"]:
        try:
            check_stage(DIR / "stage" / TOP, info["latest"], platform_id)
            return s
        except Refused:
            pass
    _set(phase="download", version=info["latest"], done=0, total=info["asset"]["size"])
    threading.Thread(target=_run, args=(info["asset"], info["latest"], platform_id), daemon=True).start()
    return status()


def apply(pid: int) -> None:

    if status()["phase"] != "ready":
        raise Refused("no update is ready")
    helper = DIR / "apply_update.py"
    shutil.copy2(DIR / "stage" / TOP / "suite/vgc_suite/apply_update.py", helper)
    base = Path(sys.base_prefix)
    py = base / "python.exe" if sys.platform == "win32" else base / "bin/python3"
    cmd = [str(py), str(helper), "--root", str(ROOT), "--pid", str(pid), "--version", str(status()["version"])]
    if sys.platform == "win32":
        subprocess.Popen(cmd, cwd=DIR, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen(cmd, cwd=DIR, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def finish() -> dict | None:

    try:
        res = json.loads((DIR / "result.json").read_text(encoding="utf8"))
    except (OSError, ValueError):
        return None
    if not (DIR / "journal.json").exists():
        for leftover in ("old", "stage"):
            shutil.rmtree(DIR / leftover, ignore_errors=True)
        (DIR / "result.json").unlink(missing_ok=True)
    LAST.update(res)
    return res

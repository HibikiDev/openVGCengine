






from __future__ import annotations

import json
import platform
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__

ROOT = Path(__file__).resolve().parents[2]
REPO = "HibikiDev/openVGCengine"
RELEASES = f"https://github.com/{REPO}/releases"
ISSUES = f"https://github.com/{REPO}/issues"
CONTACT = "openvgcengine@gmail.com"


ASSETS = {"win64": "-win64.zip", "macos": "-macos-arm64.zip"}


def _ver(tag: str) -> tuple[int, ...] | None:

    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+))?", tag.strip())
    if not m:
        return None
    return (*(int(x) for x in m.groups()[:3]), 0 if m[4] else 1, int(m[4] or 0))


def pick_release(releases: list[dict], current: str) -> dict | None:

    cur = _ver(current)
    beta = bool(cur) and cur[3] == 0
    ok = [(v, r) for r in releases if isinstance(r, dict) and not r.get("draft") and (v := _ver(str(r.get("tag_name") or "")))
          and (beta or (v[3] == 1 and not r.get("prerelease")))]
    return max(ok, key=lambda x: x[0])[1] if ok else None


def pick_asset(release: dict, platform_id: str | None) -> dict | None:

    want = ASSETS.get(platform_id or "")
    for a in release.get("assets") or []:
        name, digest = str(a.get("name") or ""), str(a.get("digest") or "")
        if want and name.endswith(want) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest) and a.get("browser_download_url") and a.get("size"):
            return {"name": name, "url": str(a["browser_download_url"]), "size": int(a["size"]), "sha256": digest.split(":", 1)[1]}
    return None


def bundle_info() -> dict:

    try:
        return json.loads((ROOT / "bundle.json").read_text(encoding="utf8"))
    except (OSError, ValueError):
        return {}


def check_update(timeout: float = 10.0, url: str | None = None) -> dict:


    api = url or f"https://api.github.com/repos/{REPO}/releases?per_page=30"
    req = urllib.request.Request(api, headers={"User-Agent": f"openVGCengine/{__version__}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rel = json.loads(r.read().decode("utf8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"current": __version__, "error": "No public release yet."}
        return {"current": __version__, "error": f"GitHub answered {e.code}; try again later."}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"current": __version__, "error": f"Couldn't reach GitHub ({type(e).__name__})."}
    d = pick_release(rel if isinstance(rel, list) else [], __version__)
    if d is None:
        return {"current": __version__, "error": "No public release yet."}
    tag = str(d.get("tag_name") or "")
    latest, cur = _ver(tag), _ver(__version__)
    return {"current": __version__, "latest": tag.lstrip("v") or None, "newer": bool(latest and cur and latest > cur),
            "url": str(d.get("html_url") or RELEASES), "published": str(d.get("published_at") or "")[:10],
            "notes": str(d.get("body") or "")[:4000], "asset": pick_asset(d, bundle_info().get("platform"))}


def _scrub(text: str) -> str:

    home = str(Path.home())
    for h in {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}:
        text = text.replace(h, "~")
    return re.sub(r"([A-Za-z]:[\\/]+Users[\\/]+)[^\\/\s\"']+", r"\1<user>", text)


def diagnostics(jobs: list[dict] | None = None, device: str = "", gpu_name: str = "") -> str:

    b = bundle_info()
    lines = [f"openVGCengine {__version__}" + (f" (bundle {b.get('export', '')[:10]}, built {b.get('built', '')[:10]})" if b else
                                                 " (from source)")]
    if b:
        eng, mods = b.get("engine") or {}, (b.get("models") or {}).get("files") or {}
        lines.append(f"engine {eng.get('commit', '?')}; models: {', '.join(mods) or '?'}; Showdown {str(b.get('showdown_pin', ''))[:10]}")
    try:
        import torch
        lines.append(f"torch {torch.__version__}; device: {device or '?'}{f' ({gpu_name})' if gpu_name else ''}")
    except Exception:
        lines.append("torch: not importable")
    try:
        import vgc_engine
        lines.append(f"engine observation v{vgc_engine.OBS_VERSION}")
    except Exception:
        lines.append("vgc_engine: not importable")
    lines.append(f"{platform.system()} {platform.release()} ({platform.machine()}); Python {sys.version.split()[0]}")
    failed = [j for j in (jobs or []) if j.get("status") == "error" and j.get("error") not in ("Cancelled.", "Cancelled before it started.")]
    for j in failed[:3]:
        lines.append("")
        lines.append(f"failed run: {j.get('tool')} {j.get('id')}: {j.get('error')}")
        tail = [ln for ln in str(j.get("trace") or "").splitlines() if ln.strip()][-8:]
        lines += [f"  {ln}" for ln in tail]
    return _scrub("\n".join(lines))

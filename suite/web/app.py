


















from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

TITLE = "openVGCengine"
LOG = ROOT / "trainer/runs/app.out"
INSTANCE = ROOT / "trainer/runs/app_instance.json"


def _other_copy() -> bool:




    try:
        rec = json.loads(INSTANCE.read_text(encoding="utf8"))
        pid, port = int(rec["pid"]), int(rec["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    if pid == os.getpid():
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/app/focus", timeout=3) as r:
            ans = json.loads(r.read().decode("utf8"))
    except (OSError, ValueError):
        return False
    return ans.get("app") == TITLE and ans.get("pid") == pid


def _log_to_file() -> None:




    pythonw = Path(sys.executable).name.lower().startswith("pythonw")
    if not pythonw and sys.stdout is not None and sys.stderr is not None:
        return
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > 1_000_000:
            LOG.replace(LOG.with_name("app.out.1"))
        f = open(LOG, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        return
    sys.stdout = sys.stderr = f


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", help="cuda | mps | cpu (default: the best available)")
    ap.add_argument("--sprites", default=str(ROOT / "sprites"), help="a folder of Pokemon sprite images for the optional icons")
    ap.add_argument("--smoke", action="store_true", help="open, check the page loaded, close (exit 1 if it didn't)")
    ap.add_argument("--debug", action="store_true", help="the web inspector (right click -> Inspect)")
    ap.add_argument("--browser", action="store_true", help="the pages in the default browser instead of the app's window (what the "
                    "app does by itself without pywebview or, on Windows, without the Edge WebView2 Runtime)")
    args = ap.parse_args()
    try:
        import webview
    except ImportError:
        webview = None
    _log_to_file()
    if not args.smoke and _other_copy():
        print(f"app: {time.strftime('%Y-%m-%d %H:%M:%S')} another copy is open - its window was brought forward; this one exits", flush=True)
        return 0
    import server

    from vgc_suite.buddy import practice_pid, server_pid
    before = (practice_pid(ROOT), server_pid(ROOT))
    print(f"app: started {time.strftime('%Y-%m-%d %H:%M:%S')}, pid {os.getpid()}; already running: practice bot {before[0]}, "
          f"buddy server {before[1]} (left running at close)", flush=True)
    from vgc_suite import update
    update.finish()
    srv, url = server.start(0, args.device, False, Path(args.sprites))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"suite on {url}  (device {server.Handler.jobs.device})", flush=True)
    if not args.smoke:
        try:
            INSTANCE.write_text(json.dumps({"pid": os.getpid(), "port": int(url.rstrip("/").rsplit(":", 1)[1])}), encoding="utf8")
        except (OSError, ValueError):
            pass
    if args.browser or webview is None or not _webview2_ok():
        why = "--browser" if args.browser else "no pywebview" if webview is None else "no Edge WebView2 Runtime"
        return _browser(server, srv, url, before, why, args.smoke)

    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    webview.settings["ALLOW_DOWNLOADS"] = True
    storage = Path.home() / ".openvgcengine" / "webview"
    storage.mkdir(parents=True, exist_ok=True)
    window = webview.create_window(TITLE, url, width=1360, height=900, min_size=(900, 600), text_select=True)

    play = {}

    def open_window(u: str, title: str) -> None:
        w = play.get("w")
        if w is not None and w in webview.windows:


            if play.get("minimized"):
                w.restore()
            w.show()
            return
        play["w"] = w = webview.create_window(title, u, width=1280, height=860, min_size=(800, 600), text_select=True)
        play["minimized"] = False
        w.events.minimized += lambda: play.__setitem__("minimized", True)
        w.events.restored += lambda: play.__setitem__("minimized", False)
        w.events.maximized += lambda: play.__setitem__("minimized", False)
    server.OPEN_WINDOW = open_window
    server.QUIT_APP = window.destroy
    main_state = {"minimized": False}
    window.events.minimized += lambda: main_state.__setitem__("minimized", True)
    window.events.restored += lambda: main_state.__setitem__("minimized", False)
    window.events.maximized += lambda: main_state.__setitem__("minimized", False)

    def focus() -> None:
        if main_state["minimized"]:
            window.restore()
        window.show()



    server.FOCUS_APP = lambda: threading.Thread(target=focus, daemon=True).start()

    def close_others() -> None:
        for w in list(webview.windows):
            if w is not window:
                w.destroy()
    window.events.closed += close_others
    result = {"ok": not args.smoke}

    def smoke() -> None:
        try:
            window.events.loaded.wait(60)
            title = window.evaluate_js("document.title")
            links = window.evaluate_js("document.querySelectorAll('nav a').length")
            result["ok"] = bool(title) and (links or 0) > 3
            print(f"smoke: title {title!r}, {links} nav links -> {'ok' if result['ok'] else 'FAILED'}", flush=True)
        finally:
            window.destroy()

    try:
        webview.start(smoke if args.smoke else None, private_mode=False, storage_path=str(storage), debug=args.debug)
    finally:
        _shutdown(srv, before)
    return 0 if result["ok"] else 1


WEBVIEW2_KEYS = ("{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}", "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",
                 "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}", "{65C35B14-6C1D-4122-AC46-7148CC9D6497}")


def _webview2_ok() -> bool:





    if sys.platform != "win32":
        return True
    import platform
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full") as k:
            if winreg.QueryValueEx(k, "Release")[0] < 394802:
                return False
    except OSError:
        return False
    for key in WEBVIEW2_KEYS:
        for hive in ("HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE"):
            sub = "" if hive == "HKEY_CURRENT_USER" or platform.machine() == "x86" else "WOW6432Node\\"
            try:
                with winreg.OpenKey(getattr(winreg, hive), rf"SOFTWARE\{sub}Microsoft\EdgeUpdate\Clients\{key}") as k:
                    if int(str(winreg.QueryValueEx(k, "pv")[0]).split(".")[0]) >= 86:
                        return True
            except (OSError, ValueError):
                pass
    return False


IDLE_S = 600


def _browser(server, srv, url: str, before: tuple, why: str, smoke: bool) -> int:




    import webbrowser

    stop = threading.Event()
    server.BROWSER_MODE = True
    server.OPEN_WINDOW = lambda u, title: webbrowser.open(u)
    server.FOCUS_APP = lambda: webbrowser.open(url)
    server.QUIT_APP = stop.set
    print(f"app: in the default browser ({why})", flush=True)
    if smoke:
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                page = r.read().decode("utf8")
            ok = "<title>" in page and page.count('class="tab') > 3 and "/app/quit" in page
            print(f"smoke: browser mode page -> {'ok' if ok else 'FAILED'}", flush=True)
        except OSError as e:
            ok = False
            print(f"smoke: browser mode page -> FAILED ({e})", flush=True)
        _shutdown(srv, before)
        return 0 if ok else 1
    server.APP_SEEN = time.monotonic()
    webbrowser.open(url)
    tick = time.monotonic()
    while not stop.wait(15):
        now = time.monotonic()
        if now - tick > 60:
            server.APP_SEEN = now
        tick = now
        busy = any(j.get("status") in ("queued", "running") for j in server.Handler.jobs.jobs.values())
        if now - server.APP_SEEN > IDLE_S and not busy:
            print("app: no page open - closing", flush=True)
            break
    _shutdown(srv, before)
    return 0


def _shutdown(srv, before: tuple) -> None:


    print(f"app: closing {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    try:
        if json.loads(INSTANCE.read_text(encoding="utf8")).get("pid") == os.getpid():
            INSTANCE.unlink()
    except (OSError, ValueError):
        pass
    try:
        from vgc_suite.buddy import practice_pid, server_pid, stop_practice, stop_server
        pid = practice_pid(ROOT)
        if pid and pid != before[0]:
            print(stop_practice(ROOT), flush=True)
        pid = server_pid(ROOT)
        if pid and pid != before[1]:
            print(stop_server(ROOT), flush=True)
    except Exception as e:
        print(f"buddy: {type(e).__name__}: {e}", flush=True)
    srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())

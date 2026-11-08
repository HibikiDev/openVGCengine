















from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

TITLE = "openVGCengine"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", help="cuda | mps | cpu (default: the best available)")
    ap.add_argument("--sprites", default=str(ROOT / "sprites"), help="a folder of Pokemon sprite images for the optional icons")
    ap.add_argument("--smoke", action="store_true", help="open, check the page loaded, close (exit 1 if it didn't)")
    ap.add_argument("--debug", action="store_true", help="the web inspector (right click -> Inspect)")
    args = ap.parse_args()
    try:
        import webview
    except ImportError:
        print("The desktop app needs pywebview: pip install -r requirements/app.txt (or run suite/web/server.py and open the browser).")
        return 2
    import server

    from vgc_suite.buddy import practice_pid, server_pid
    before = (practice_pid(ROOT), server_pid(ROOT))
    from vgc_suite import update
    update.finish()
    srv, url = server.start(0, args.device, False, Path(args.sprites))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"suite on {url}  (device {server.Handler.jobs.device})", flush=True)

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


def _shutdown(srv, before: tuple) -> None:


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

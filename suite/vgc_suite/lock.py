








from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

LOCK = Path(__file__).resolve().parents[2] / "trainer/runs/SUITE_LOCK"


def state() -> dict | None:

    if not LOCK.exists():
        return None
    try:
        return json.loads(LOCK.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return {"reason": "this PC is busy", "since": "", "until": ""}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", choices=["on", "off", "status"], default="status")
    ap.add_argument("reason", nargs="?", default="this PC is busy with a long job")
    ap.add_argument("--until", default="", help="a rough end, as text (e.g. '10-21 20:00')")
    a = ap.parse_args()
    if a.action == "on":
        LOCK.write_text(json.dumps({"reason": a.reason, "since": time.strftime("%m-%d %H:%M"), "until": a.until}), encoding="utf8")
    elif a.action == "off":
        LOCK.unlink(missing_ok=True)
    s = state()
    print(f"locked since {s['since']}: {s['reason']}" + (f" (until ~{s['until']})" if s.get("until") else "") if s else "unlocked")


if __name__ == "__main__":
    main()

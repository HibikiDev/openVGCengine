







from __future__ import annotations

import json
import time
from pathlib import Path

LIST = Path(__file__).with_name("bot_accounts.json")


def to_id(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def load() -> list[dict]:
    try:
        return json.loads(LIST.read_text(encoding="utf8")).get("accounts", [])
    except (OSError, ValueError):
        return []


KNOWN_BOTS = frozenset(a["id"] for a in load())
_seen = (LIST.stat().st_mtime if LIST.exists() else 0.0, time.monotonic())


def _refresh() -> None:


    global KNOWN_BOTS, _seen
    if time.monotonic() - _seen[1] < 60:
        return
    try:
        m = LIST.stat().st_mtime
    except OSError:
        m = 0.0
    if m != _seen[0]:
        KNOWN_BOTS = frozenset(a["id"] for a in load())
    _seen = (m, time.monotonic())


def is_bot(name: str) -> bool:
    _refresh()
    return to_id(name) in KNOWN_BOTS

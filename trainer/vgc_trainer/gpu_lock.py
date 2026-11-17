












from __future__ import annotations

import asyncio
import contextlib
import functools
import os
import threading
import traceback

_LOCK = threading.RLock()
_STATE = {"on": False, "check": False}
_HELD = threading.local()
VIOLATIONS: list[str] = []


def configure(device) -> bool:

    kind = getattr(device, "type", device)
    _STATE["check"] = os.environ.get("VGC_GPU_CHECK") == "1"
    _STATE["on"] = kind == "mps" or _STATE["check"]
    return _STATE["on"]


def on() -> bool:
    return _STATE["on"]


@contextlib.contextmanager
def section():

    if not _STATE["on"]:
        yield
        return
    with _LOCK:
        _HELD.n = getattr(_HELD, "n", 0) + 1
        try:
            yield
        finally:
            _HELD.n -= 1


def locked(fn):

    @functools.wraps(fn)
    def run(*a, **k):
        with section():
            return fn(*a, **k)
    return run


async def call(fn, *a, **k):

    if not _STATE["on"]:
        return fn(*a, **k)
    return await asyncio.to_thread(locked(fn), *a, **k)


def check(device=None) -> None:


    if _STATE["check"] and not getattr(_HELD, "n", 0) and getattr(device, "type", "cuda") != "cpu":
        site = "".join(traceback.format_stack(limit=8)[:-1])
        if len(VIOLATIONS) < 50:
            VIOLATIONS.append(f"thread {threading.current_thread().name}:\n{site}")
            print(f"GPU CHECK: model call outside gpu_lock.section() on thread {threading.current_thread().name}\n{site}", flush=True)

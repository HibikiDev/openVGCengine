
















from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILE = ROOT / "suite/pins.json"
_PINS: dict = {}
_MTIME = [0.0]


def _pins() -> dict:

    m = FILE.stat().st_mtime
    if not _PINS or m != _MTIME[0]:
        _PINS.clear()
        _PINS.update(json.loads(FILE.read_text(encoding="utf8")))
        _MTIME[0] = m
    return _PINS


def path(kind: str) -> Path:

    return ROOT / _pins()[kind]["path"]


def live_arm() -> dict:

    from vgc_trainer.showdown.live_search import SEARCH_ARMS
    return SEARCH_ARMS[_pins()["search_arm"]["name"]]


def live_searcher(policy, env, dev, seed: int, reply_policy, arm: dict | None = None, **over):



    from vgc_trainer.search import OneStepSearch
    arm = arm or live_arm()
    return OneStepSearch(policy, env, dev, k=arm.get("k", 8), m=8, samples=arm.get("samples", 32), seed=seed,
                         replies="policy", reply_policy=reply_policy, score=arm.get("score", "value"), finish_switch=False,
                         greedy_column=True, cand_temp=2.0, inject_protect=arm.get("inject_protect", False), seeds=arm.get("seeds", 1),
                         reply_mode=arm.get("reply_mode", "sample"), robust=arm.get("robust", 0.0), depth2=arm.get("rollouts", 0),
                         depth2_mix=arm.get("rollout_mix", 0.0), rollout_fix=bool(arm.get("rollouts")), rollout_len=arm.get("rollout_len", 1),
                         rollout_dedupe=arm.get("rollout_dedupe", "off") if arm.get("rollouts") else "off",
                         rollout_trigger=arm.get("rollout_trigger") if arm.get("rollouts") else None,
                         slot_variants=arm.get("slot_variants", 0), **over)


def closed_searcher(policy, env, dev, seed: int, **over):





    from vgc_trainer.search import OneStepSearch
    return OneStepSearch(policy, env, dev, k=8, m=8, samples=32, seed=seed, replies="self", score="value", finish_switch=False,
                         greedy_column=True, cand_temp=2.0, **over)




from __future__ import annotations

import json
from pathlib import Path

from vgc_trainer.showdown.agent import Agent

ROOT = Path(__file__).resolve().parents[3]
LIVE_DIR = ROOT / "trainer/runs/ml1_copy"


def newest_checkpoint() -> Path:





    from .bundle import path as pinned
    try:
        p = pinned("checkpoint")
    except (OSError, KeyError):
        p = None
    if p is not None:
        if p.is_dir():
            cks = sorted(p.glob("ckpt_*.pt"), key=lambda c: int(c.stem.split("_")[1]))
            if not cks:
                raise FileNotFoundError(f"suite/pins.json pins the checkpoint folder {p}, which has no ckpt_*.pt")
            return cks[-1]
        if not p.exists():
            raise FileNotFoundError(f"suite/pins.json pins checkpoint {p}, which doesn't exist")
        return p
    try:
        live = json.loads((LIVE_DIR / "confirmed.json").read_text(encoding="utf8")).get("_live")
        if live and (LIVE_DIR / live).exists():
            return LIVE_DIR / live
    except (OSError, json.JSONDecodeError):
        pass
    cks = sorted(LIVE_DIR.glob("ckpt_*.pt"), key=lambda p: int(p.stem.split("_")[1]))
    if not cks:
        raise FileNotFoundError(f"no checkpoint in {LIVE_DIR}")
    return cks[-1]


def load_agent(ckpt: str | Path | None = None, device: str = "cpu") -> tuple[Agent, Path]:

    path = Path(ckpt) if ckpt else newest_checkpoint()
    return Agent(str(path), device), path

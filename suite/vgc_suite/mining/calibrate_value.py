














from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.core.models import load_agent
from vgc_suite.mining.evaluate import DATA
from vgc_suite.mining.finetune_opp import KEYS, split
from vgc_trainer.amp import pick_device, amp


TURN_BUCKETS = ((1, 2), (2, 3), (3, 4), (4, 6), (6, 9), (9, 10**6))


def _name(lo: int, hi: int) -> str:
    return f"turn {lo}" if hi == lo + 1 else (f"turns {lo}+" if hi > 1000 else f"turns {lo}-{hi - 1}")


@torch.no_grad()
def values(pol, data: Path, dev, cache: Path, bs: int = 2048) -> np.ndarray:

    if cache.exists():
        return np.load(cache)
    with np.load(data) as z:
        arrays = {k: z[k] for k in KEYS}
    n = len(arrays["field"])
    out = np.zeros(n, np.float32)
    with amp(dev):
        for a in range(0, n, bs):
            out[a:a + bs] = pol.values(*(torch.from_numpy(arrays[k][a:a + bs]).to(dev) for k in KEYS)).float().cpu().numpy()
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, out)
    return out


def _ll(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


EPS = 0.005


def feature(v: np.ndarray) -> np.ndarray:

    r = np.clip((v + 1) / 2, EPS, 1 - EPS)
    return np.log(r / (1 - r))


def calibrated(v: np.ndarray, a: float, b: float) -> np.ndarray:
    return 1 / (1 + np.exp(-(a * feature(v) + b)))


def platt(v: np.ndarray, y: np.ndarray, steps: int = 50) -> tuple[float, float]:

    v = feature(v)
    a, b = 1.0, 0.0
    x = np.stack([v, np.ones_like(v)], 1).astype(np.float64)
    w = np.array([a, b])
    for _ in range(steps):
        p = 1 / (1 + np.exp(-x @ w))
        g = x.T @ (y - p)
        h = -(x * (p * (1 - p))[:, None]).T @ x - 1e-6 * np.eye(2)
        step = np.linalg.solve(h, g)
        w = w - step
        if np.abs(step).max() < 1e-8:
            break
    return float(w[0]), float(w[1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(ROOT / "trainer/runs/opp_human/value_calibration.json"))
    args = ap.parse_args()
    dev = pick_device()
    agent, ckpt = load_agent(args.ckpt, str(dev))
    pol = agent.policy.eval()
    data = Path(args.data)
    v = values(pol, data, dev, Path(args.out).with_name(f"values_{Path(ckpt.name).stem}.npy"))
    with np.load(data) as z:
        won, turn = z["won"], z["turn"]
    rows = [json.loads(ln) for ln in open(data.with_name("rows.jsonl"), encoding="utf8")]
    last = {}
    for r, t in zip(rows, turn):
        last[r["id"]] = max(last.get(r["id"], 0), int(t))
    played = np.array([last[r["id"]] > 2 for r in rows])
    train, val = split(data.with_name("rows.jsonl"), len(won), ROOT / "trainer/runs/replays/index.jsonl")
    keep = played & (won >= 0)
    train, val = train[keep[train]], val[keep[val]]
    print(f"{ckpt.name}: {len(train)} training rows, {len(val)} held-out rows (pairs held out; bots, ties, games <= 2 turns out)")
    raw = np.clip((v + 1) / 2, EPS, 1 - EPS)
    fits = {}
    for lo, hi in TURN_BUCKETS:
        tr = train[(turn[train] >= lo) & (turn[train] < hi)]
        va = val[(turn[val] >= lo) & (turn[val] < hi)]
        a, b = platt(v[tr], won[tr].astype(np.float64))
        cal = calibrated(v[va], a, b)
        y = won[va].astype(np.float64)
        fits[_name(lo, hi)] = {"lo": lo, "hi": hi, "a": round(a, 4), "b": round(b, 4), "n_train": int(len(tr)), "n_val": int(len(va)),
                               "ll_raw": round(_ll(raw[va], y), 4), "ll_cal": round(_ll(cal, y), 4)}
        f = fits[_name(lo, hi)]
        print(f"{_name(lo, hi):<10} a {a:+.3f} b {b:+.3f}  held-out LL raw {f['ll_raw']:.4f} -> calibrated {f['ll_cal']:.4f} "
              f"({f['ll_cal'] - f['ll_raw']:+.4f}), n {len(va)}")

    t1 = val[turn[val] == 1]
    f1 = fits[_name(1, 2)]
    cal1 = calibrated(v[t1], f1["a"], f1["b"])
    rel = []
    print("turn-1 reliability (held out): raw bin -> observed win rate / mean raw / mean calibrated (n)")
    for lo in np.arange(0, 1, 0.1):
        m = (raw[t1] >= lo) & (raw[t1] < lo + 0.1 + (1e-9 if lo >= 0.9 else 0))
        if m.sum() < 50:
            continue
        row = {"bin": round(float(lo), 1), "won": round(float(won[t1][m].mean()), 3), "raw": round(float(raw[t1][m].mean()), 3),
               "cal": round(float(cal1[m].mean()), 3), "n": int(m.sum())}
        rel.append(row)
        print(f"  {lo:.1f}-{lo + 0.1:.1f}: {row['won']:.3f} / {row['raw']:.3f} / {row['cal']:.3f} ({row['n']})")
    out = {"ckpt": ckpt.name, "form": "p = sigmoid(a * logit(clip((v + 1) / 2, eps, 1 - eps)) + b) for the decision's turn bucket", "eps": EPS, "buckets": fits,
           "turn1_reliability": rel}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf8")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

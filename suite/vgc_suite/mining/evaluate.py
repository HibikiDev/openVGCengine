











from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.core.models import load_agent
from vgc_trainer.canonical import Framed
from vgc_trainer.model import narrow_slot_b
from vgc_trainer.showdown.requests import SLOT_ACTIONS, SWITCH_BASE
from vgc_trainer.amp import pick_device

DATA = ROOT / "trainer/runs/human_data/decisions.npz"


def move_level(logits: torch.Tensor) -> torch.Tensor:

    p = torch.softmax(logits.float(), -1)
    moves = p[..., :SWITCH_BASE].reshape(*p.shape[:2], 4, 4).sum(-1)
    switch = p[..., SWITCH_BASE:SWITCH_BASE + 4].sum(-1, keepdim=True)
    q = torch.cat([moves, switch], -1)
    return torch.log(q / q.sum(-1, keepdim=True).clamp(min=1e-9)).clamp(min=-20)


@torch.inference_mode()
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--min-rating", type=int, default=0, help="only rows whose player is rated at least this")
    ap.add_argument("--device", default=pick_device().type)
    args = ap.parse_args()
    agent, ckpt = load_agent(args.ckpt, args.device)
    pol, dev = agent.policy, agent.dev
    d = np.load(args.data)
    keep = np.flatnonzero(d["rating_me"] >= args.min_rating)
    print(f"{ckpt.name} on {len(keep)} human decisions ({args.data})")
    temps = (1.0, 2.0, 3.42, 5.0)
    ll = {t: [] for t in temps}
    top1 = []
    pol_p, pol_top, values, won, turns = [], [], [], [], []
    for a in range(0, len(keep), 256):
        idx = keep[a:a + 256]
        x = [torch.from_numpy(d[k][idx]).to(dev) for k in ("field", "mon_ids", "mon_features", "history", "bring")]
        masks = d["masks"][idx]
        bits = torch.tensor([[[(int(m[s]) >> i) & 1 == 1 for i in range(SLOT_ACTIONS)] for s in (0, 1)] for m in masks], device=dev)


        fr = Framed(pol, x, bits)
        net, x, bits = fr.net, list(fr.inputs), fr.bits

        logits = fr.aux_to_engine(net.opponent_logits(*x)).float()
        lab = torch.from_numpy(d["foe_moves"][idx]).to(dev)
        for t in temps:
            lp = move_level(logits / t)
            ok = lab >= 0
            ll[t].append(lp.gather(-1, lab.clamp(min=0).unsqueeze(-1)).squeeze(-1)[ok].cpu().numpy())
            if t == 1.0:
                top1.append((lp.argmax(-1) == lab)[ok].cpu().numpy())

        st = net.encode(*x)
        values.append(st.value.float().cpu().numpy())
        won.append(d["won"][idx])
        turns.append(d["turn"][idx])
        my = fr.actions_to_canon(torch.from_numpy(d["my_actions"][idx]).to(dev))
        mins = torch.from_numpy(d["min_switches"][idx]).to(dev)
        lg0, _ = net.slot_logits(st, 0, None)
        p0 = torch.softmax(lg0.float().masked_fill(~bits[:, 0], float("-inf")), -1)
        a0 = torch.where(my[:, 0, 0] >= 0, my[:, 0, 0], p0.argmax(-1))
        cond = net.condition(st, a0, my[:, 0, 1].clamp(min=0))
        lg1, _ = net.slot_logits(st, 1, cond)
        b1 = narrow_slot_b(bits[:, 1], a0, mins)
        p1 = torch.softmax(lg1.float().masked_fill(~b1, float("-inf")), -1)
        for s, p in ((0, p0), (1, p1)):
            ok = (my[:, s, 0] >= 0) & torch.isfinite(p).all(-1)
            if ok.any():
                pp = p[ok].gather(-1, my[ok, s, 0].unsqueeze(-1)).squeeze(-1)
                pol_p.append(pp.cpu().numpy())
                pol_top.append((p[ok].argmax(-1) == my[ok, s, 0]).cpu().numpy())
    print("1. opponent model (aux head, move level; uniform over 5 = %.3f):" % np.log(1 / 5))
    for t in temps:
        v = np.concatenate(ll[t])
        print(f"   T={t:<4}  mean log-likelihood {v.mean():.3f} +- {v.std() / np.sqrt(len(v)):.3f}   ({len(v)} choices)")
    print(f"   top-1 (T=1) {np.concatenate(top1).mean():.3f}")
    pp, pt = np.concatenate(pol_p), np.concatenate(pol_top)
    print(f"2. policy on the human's own action: mean p {pp.mean():.3f}, median {np.median(pp):.3f}, top-1 {pt.mean():.3f} ({len(pp)} slot-choices)")
    v, w, tr = np.concatenate(values), np.concatenate(won), np.concatenate(turns)
    m = w >= 0
    pw = np.clip((v[m] + 1) / 2, 1e-4, 1 - 1e-4)
    y = w[m]
    print(f"3. value on human games: log-loss {-(y * np.log(pw) + (1 - y) * np.log(1 - pw)).mean():.3f} "
          f"(coin flip {np.log(2):.3f}), Brier {((pw - y) ** 2).mean():.3f}")
    for lo, hi in ((1, 1), (2, 3), (4, 6), (7, 99)):
        sel = (tr[m] >= lo) & (tr[m] <= hi)
        if sel.sum() < 20:
            continue
        parts = []
        for a_, b_ in ((0, .3), (.3, .5), (.5, .7), (.7, .9), (.9, 1.01)):
            s2 = sel & (pw >= a_) & (pw < b_)
            if s2.sum() >= 10:
                parts.append(f"{a_:.1f}-{min(b_, 1):.1f}: {y[s2].mean():.2f} (n={s2.sum()})")
        print(f"   turns {lo}-{hi if hi < 99 else '+'}: estimate bucket -> actual win rate  " + "; ".join(parts))


if __name__ == "__main__":
    main()

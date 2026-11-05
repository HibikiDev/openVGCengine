""














from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.mining.finetune_bc import arrays, batch, logp_of, usable
from vgc_suite.mining.finetune_opp import _pid
from vgc_trainer.model import load_policy
from vgc_trainer.showdown.requests import SWITCH_BASE

DATA = ROOT / "trainer/runs/human_data_live/decisions.npz"
INDEX = ROOT / "trainer/runs/replays_live/index.jsonl"
PROTECTS = {"Protect", "Detect", "Spiky Shield", "King's Shield", "Baneful Bunker", "Silk Trap", "Burning Bulwark", "Obstruct"}
BANDS = [(-1.01, -0.4, "far behind"), (-0.4, -0.1, "behind"), (-0.1, 0.1, "even"), (0.1, 0.4, "ahead"), (0.4, 1.01, "far ahead")]


@torch.no_grad()
def score(pol, bc, d, idx, dev, bs=1024):

    vals, exc, nch = [], [], []
    for a in range(0, len(idx), bs):
        x, bits, actions, mega_ok, mins = batch(d, idx[a:a + bs], dev)
        vals.append(pol.values(*x).float().cpu().numpy())
        _, logits, mask1 = logp_of(bc, x, bits, actions, mega_ok, mins)
        e = torch.zeros(len(actions))
        n = torch.zeros(len(actions))
        for s, m in ((0, bits[:, 0]), (1, mask1)):
            real = m.sum(-1) > 1
            lp = torch.log_softmax(logits[:, s].float().masked_fill(~m, float("-inf")), -1)
            ent = -(lp.exp() * lp.masked_fill(~m, 0.0)).sum(-1)
            sur = -lp.gather(1, actions[:, s, 0:1]).squeeze(1)
            ok = real & torch.isfinite(sur)
            e += torch.where(ok, sur - ent, torch.zeros_like(sur)).cpu()
            n += ok.float().cpu()
        exc.append(e.numpy())
        nch.append(n.numpy())
    return np.concatenate(vals), np.concatenate(exc), np.concatenate(nch)


def boot(values: np.ndarray, groups: np.ndarray, weights: np.ndarray | None = None, n: int = 500) -> tuple[float, float, float]:

    w = np.ones(len(values)) if weights is None else weights
    g, inv = np.unique(groups, return_inverse=True)
    s, c = np.bincount(inv, values * w, len(g)), np.bincount(inv, w, len(g))
    rng = np.random.default_rng(0)
    bs = []
    for _ in range(n):
        k = np.bincount(rng.integers(0, len(g), len(g)), minlength=len(g))
        bs.append((k * s).sum() / max((k * c).sum(), 1e-9))
    return float(s.sum() / c.sum()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    from vgc_suite.core.bundle import path as pinned
    from vgc_suite.core.models import newest_checkpoint
    ap.add_argument("--ckpt", default=str(newest_checkpoint()))
    ap.add_argument("--reply-policy", default=str(pinned("reply_policy")))
    ap.add_argument("--sample", type=int, default=60000, help="rows below 1400 (all 1400+ rows are kept)")
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "trainer/runs/risk_state.json"))
    ap.add_argument("--heldout", action="store_true", help="only rows held out of the human-model fits (player-pair split over "
                    "both indexes) - for a reply model trained on the watcher's games (bc_93000_u)")
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    dev = torch.device("cpu")
    pol = load_policy(torch.load(args.ckpt, map_location=dev, weights_only=True), dev).eval()
    bc = load_policy(torch.load(args.reply_policy, map_location=dev, weights_only=True), dev).eval()
    d = arrays(DATA)
    rows = [json.loads(ln) for ln in open(DATA.with_name("rows.jsonl"), encoding="utf8")]
    games = {}
    series: dict[str, dict[int, str]] = defaultdict(dict)
    for ln in open(INDEX, encoding="utf8"):
        r = json.loads(ln)
        games[r["id"]] = r
        if r.get("series") and str(r.get("game", "")).isdigit():
            series[r["series"]][int(r["game"])] = _pid(r.get("winner") or "")
    rating = np.asarray(d["rating_me"])
    ok = usable(d) & np.array([not (r.get("bot") or r.get("vs_bot")) for r in rows])
    if args.heldout:
        from vgc_suite.mining.finetune_bc import INDEXES
        from vgc_suite.mining.finetune_opp import split
        crawl = ROOT / "trainer/runs/human_data/rows.jsonl"
        n_crawl = sum(1 for _ in open(crawl, encoding="utf8"))
        _, val = split([crawl, DATA.with_name("rows.jsonl")], n_crawl + len(rows), [ROOT / INDEXES["human_data"], INDEX])
        held = np.zeros(len(rows), bool)
        held[val[val >= n_crawl] - n_crawl] = True
        ok &= held
    hi = np.flatnonzero(ok & (rating >= 1400))
    lo = np.flatnonzero(ok & (rating < 1400))
    lo = np.sort(np.random.default_rng(0).choice(lo, min(len(lo), args.sample), replace=False))
    idx = np.concatenate([hi, lo])
    print(f"{len(hi)} decisions by 1400+ players, {len(lo)} sampled below; scoring on the CPU ...", flush=True)
    v, exc, nch = score(pol, bc, d, idx, dev)
    my = np.asarray(d["my_actions"])[idx]
    masks = np.asarray(d["masks"])[idx]
    real = (masks != 0) & (masks != (1 << 20))
    sw = ((my[:, :, 0] >= SWITCH_BASE) & (my[:, :, 0] < 20) & real).sum(1)
    pr = np.array([sum(1 for k, m in enumerate(rows[i].get("played") or []) if m in PROTECTS and real[j, k])
                   for j, i in enumerate(idx)])
    nreal = real.sum(1)
    player = np.array([_pid(rows[i]["player"]) for i in idx])
    gnum, after = np.zeros(len(idx), int), np.array([""] * len(idx), dtype=object)
    for j, i in enumerate(idx):
        g = games.get(rows[i]["id"], {})
        n = int(g["game"]) if str(g.get("game", "")).isdigit() else 0
        gnum[j] = n
        if n == 2:
            prev = series.get(g.get("series"), {}).get(1)
            if prev is not None:
                after[j] = "after W" if prev == player[j] else "after L"
    band = np.full(len(idx), "", dtype=object)
    for lo_, hi_, name in BANDS:
        band[(v >= lo_) & (v < hi_)] = name
    res = {}

    def line(name, m):
        if m.sum() < 50:
            return
        e = boot(exc[m] / np.maximum(nch[m], 1), player[m], nch[m] > 0)
        p = boot(pr[m] / np.maximum(nreal[m], 1), player[m], nreal[m] > 0)
        s = boot(sw[m] / np.maximum(nreal[m], 1), player[m], nreal[m] > 0)
        res[name] = {"rows": int(m.sum()), "players": int(len(set(player[m]))), "excess_surprise": e, "protect": p, "switch": s}
        print(f"  {name:<34} {m.sum():>6} rows {len(set(player[m])):>5} pl  excess surprise {e[0]:+.3f} [{e[1]:+.3f}, {e[2]:+.3f}]  "
              f"protect {p[0]:.3f} [{p[1]:.3f}, {p[2]:.3f}]  switch {s[0]:.3f} [{s[1]:.3f}, {s[2]:.3f}]", flush=True)

    r_hi = rating[idx] >= 1400
    for pop, pm in (("1400+", r_hi), ("all (sampled)", np.ones(len(idx), bool))):
        print(f"\n{pop}: by the value of the position (deciding player's view, {Path(args.ckpt).name}); per slot with a real choice")
        for _, _, name in BANDS:
            line(f"{name}", pm & (band == name))
        print(f"{pop}: G2 by the series state, behind (< -0.1) / even / ahead (> 0.1)")
        for st in ("after W", "after L"):
            for nm, vm in (("behind", v < -0.1), ("even", (v >= -0.1) & (v <= 0.1)), ("ahead", v > 0.1)):
                line(f"G2 {st}, {nm}", pm & (gnum == 2) & (after == st) & vm)
        for nm, vm in (("behind", v < -0.1), ("even", (v >= -0.1) & (v <= 0.1)), ("ahead", v > 0.1)):
            line(f"G3, {nm}", pm & (gnum == 3) & vm)
    Path(args.out).write_text(json.dumps(res, indent=1), encoding="utf8")


if __name__ == "__main__":
    main()

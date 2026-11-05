



















from __future__ import annotations

import argparse
import copy
import hashlib
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
from vgc_suite.mining.dataset import OWN_OUT, is_bot
from vgc_suite.mining.evaluate import DATA, move_level
from vgc_trainer.showdown.requests import SLOT_ACTIONS
from vgc_trainer.amp import pick_device, amp

KEYS = ("field", "mon_ids", "mon_features", "history", "bring")


def held_out(key: str, frac: float = 0.1) -> bool:
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < frac


def _pid(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def split(rows_path: Path | list[Path], n: int, index_path: Path | list[Path]) -> tuple[np.ndarray, np.ndarray]:





    pairs, bot_games = {}, set()
    for ip in (index_path if isinstance(index_path, list) else [index_path]):
        with open(ip, encoding="utf8") as f:
            for ln in f:
                r = json.loads(ln)
                pairs[r["id"]] = "|".join(sorted(_pid(p) for p in r.get("players", [])))
                if any(is_bot(p) for p in r.get("players", [])):
                    bot_games.add(r["id"])
    ids = []
    for rp in (rows_path if isinstance(rows_path, list) else [rows_path]):
        with open(rp, encoding="utf8") as f:
            for ln in f:
                r = json.loads(ln)
                ids.append(r["id"])
                if r.get("bot") or r.get("vs_bot") or is_bot(r.get("player", "")):
                    bot_games.add(r["id"])
    missing = sum(g not in pairs for g in set(ids))
    if missing:
        raise SystemExit(f"{missing} games of the rows are in no index (they would split per game): pass every index")
    if len(ids) != n:
        raise SystemExit(f"rows.jsonl has {len(ids)} rows, decisions.npz {n}")
    val = np.array([held_out(pairs.get(g, g)) for g in ids])
    human = np.array([g not in bot_games for g in ids])
    return np.flatnonzero(human & ~val), np.flatnonzero(human & val)


def encode_all(pol, data: Path, dev, cache_dir: Path, ckpt_name: str, bs: int = 2048, tag: str = "") -> np.ndarray:


    path = cache_dir / f"feat_{Path(ckpt_name).stem}{tag}.npy"
    if getattr(pol, "aux_head", "slot") != "slot":
        raise SystemExit("finetune_opp fits the slot aux head's form; this checkpoint's aux head is a pointer head (not ported yet)")
    f_dim = pol.aux[0].in_features
    with np.load(data) as z:
        n = len(z["turn"])
        if path.exists():
            feat = np.load(path, mmap_mode="r")
            if feat.shape == (n, 2, f_dim):
                return feat
        arrays = {k: z[k] for k in KEYS}
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = cache_dir / f"feat_{Path(ckpt_name).stem}{tag}.tmp.npy"
    out = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float16, shape=(n, 2, f_dim))
    with torch.no_grad(), amp(dev):
        for a in range(0, n, bs):
            st = pol.encode(*(torch.from_numpy(arrays[k][a:a + bs]).to(dev) for k in KEYS))
            out[a:a + bs] = torch.cat([st.foe_active, st.summary.unsqueeze(1).expand(-1, 2, -1)], -1).half().cpu().numpy()
    out.flush()
    del out, arrays
    tmp.replace(path)
    print(f"cached trunk features -> {path}", flush=True)
    return np.load(path, mmap_mode="r")



BUCKETS = (("unrated", -10**9, 1), ("<1100", 1, 1100), ("1100-1199", 1100, 1200), ("1200+", 1200, 10**9), ("1300+", 1300, 10**9),
           ("1400+", 1400, 10**9), ("1500+", 1500, 10**9))
METRICS = ("act", "move", "joint")


def per_label(head, feat, lab, mv, rating, idx, dev, temps: tuple[float, ...], bs: int = 8192) -> dict:




    out = {k: {t: [] for t in temps} for k in METRICS}
    hit_a, hit_m, rt = [], [], {k: [] for k in METRICS}
    with torch.no_grad():
        for a in range(0, len(idx), bs):
            part = idx[a:a + bs]
            logits = head(torch.from_numpy(np.asarray(feat[part])).to(dev).float())
            la, lm = torch.from_numpy(lab[part]).to(dev), torch.from_numpy(mv[part]).to(dev)
            ok_a, ok_m = lab[part] >= 0, mv[part] >= 0
            both = ok_a.all(1)
            for t in temps:
                lp = torch.log_softmax(logits / t, -1)
                ga = lp.gather(-1, la.clamp(min=0).unsqueeze(-1)).squeeze(-1).cpu().numpy()
                out["act"][t].append(ga[ok_a])
                out["joint"][t].append(ga.sum(1)[both])
                lpm = move_level(logits / t)
                out["move"][t].append(lpm.gather(-1, lm.clamp(min=0).unsqueeze(-1)).squeeze(-1).cpu().numpy()[ok_m])
                if t == temps[0]:
                    hit_a.append((lp.argmax(-1) == la).cpu().numpy()[ok_a])
                    hit_m.append((lpm.argmax(-1) == lm).cpu().numpy()[ok_m])
            r = np.repeat(rating[part][:, None], 2, 1)
            rt["act"].append(r[ok_a])
            rt["move"].append(r[ok_m])
            rt["joint"].append(rating[part][both])
    cat = np.concatenate
    return {"ll": {k: {t: cat(v) for t, v in d.items()} for k, d in out.items()},
            "hit": {"act": float(cat(hit_a).mean()), "move": float(cat(hit_m).mean())},
            "rating": {k: cat(v) for k, v in rt.items()}}


def bucketed(ll: np.ndarray, rt: np.ndarray) -> dict:
    row = {"all": float(ll.mean())}
    for b, lo, hi in BUCKETS:
        m = (rt >= lo) & (rt < hi)
        if m.any():
            row[b] = float(ll[m].mean())
    return row


def report(name: str, r: dict, temps: dict, base: dict | None = None) -> dict:

    rows = {}
    for k in METRICS:
        rows[k] = bucketed(r["ll"][k][temps[k]], r["rating"][k])
        txt = "; ".join(f"{b} {v:.4f}" + (f" ({v - base[k][b]:+.4f})" if base and b in base[k] else "") for b, v in rows[k].items())
        print(f"{name:<24} {k:<5} T={temps[k]:<4} {txt}", flush=True)
    rows["top1"] = r["hit"]
    print(f"{name:<24} top-1 act {r['hit']['act']:.3f}, move {r['hit']['move']:.3f}", flush=True)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--bs", type=int, default=1024)
    ap.add_argument("--out", default=str(ROOT / "trainer/runs/opp_human"))
    ap.add_argument("--score", help="only evaluate this head.pt on --ckpt's trunk (e.g. a head fitted on another checkpoint)")
    ap.add_argument("--vs-bot", default=str(OWN_OUT / "decisions.npz"),
                    help="the bot's own games (`dataset --own`): evaluated as a separate slice, never trained on")
    args = ap.parse_args()
    dev = pick_device()
    agent, ckpt = load_agent(args.ckpt, str(dev))
    pol = agent.policy.eval()
    for prm in pol.parameters():
        prm.requires_grad_(False)
    out = Path(args.out)
    feat = encode_all(pol, Path(args.data), dev, out, ckpt.name)
    with np.load(args.data) as z:
        lab = np.ascontiguousarray(z["foe_actions"][..., 0])
        mv, rating = z["foe_moves"], z["rating_foe"]
    lab = np.where(lab < SLOT_ACTIONS, lab, -1)
    train, val = split(Path(args.data).with_name("rows.jsonl"), len(lab), ROOT / "trainer/runs/replays/index.jsonl")
    print(f"{ckpt.name}: {len(train)} training rows, {len(val)} held-out rows (by player pair; bot games left out)", flush=True)

    base = pol.aux.float()

    grid = (1.0, 2.0, 3.0, 3.42, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 16.0, 24.0, 32.0)
    sample = np.sort(np.random.default_rng(1).choice(train, min(len(train), 120_000), replace=False))
    fit = per_label(base, feat, lab, mv, rating, sample, dev, grid)
    t_fit = {k: max(grid, key=lambda t: fit["ll"][k][t].mean()) for k in METRICS}
    print(f"fitted temperatures on training rows: {t_fit}", flush=True)
    rb = per_label(base, feat, lab, mv, rating, val, dev, tuple(sorted(set(t_fit.values()))))
    baseline = report("baseline (fitted T)", rb, t_fit)
    one = {k: 1.0 for k in METRICS}

    vs = None
    if Path(args.vs_bot).exists():
        with np.load(args.vs_bot) as z:
            vs = {"feat": encode_all(pol, Path(args.vs_bot), dev, out, ckpt.name, tag="_vsbot"),
                  "lab": np.where(z["foe_actions"][..., 0] < SLOT_ACTIONS, z["foe_actions"][..., 0], -1), "mv": z["foe_moves"],
                  "rating": z["rating_foe"]}
        vs["idx"] = np.arange(len(vs["lab"]))
        vs["base"] = report("vs-bot baseline", per_label(base, vs["feat"], vs["lab"], vs["mv"], vs["rating"], vs["idx"], dev,
                                                         tuple(sorted(set(t_fit.values())))), t_fit)

    def vs_report(name: str, h) -> dict | None:
        if vs is None:
            return None
        return report(name, per_label(h, vs["feat"], vs["lab"], vs["mv"], vs["rating"], vs["idx"], dev, (1.0,)), one, vs["base"])

    if args.score:
        sd = torch.load(args.score, map_location=dev, weights_only=True)
        head = copy.deepcopy(base)
        head.load_state_dict(sd["aux"])
        head.eval()
        print(f"scoring {args.score} (fitted on {sd['meta'].get('ckpt')}, loss {sd['meta'].get('loss', 'move level')})", flush=True)
        report("head T=1", per_label(head, feat, lab, mv, rating, val, dev, (1.0,)), one, baseline)
        vs_report("vs-bot head T=1", head)
        return

    head = copy.deepcopy(base)
    for prm in head.parameters():
        prm.requires_grad_(True)
    opt = torch.optim.AdamW(head.parameters(), lr=args.lr, weight_decay=1e-4)
    rng = np.random.default_rng(0)
    best = (-1e9, None, 0, {})
    steps = args.epochs * ((len(train) + args.bs - 1) // args.bs)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    for ep in range(args.epochs):
        order = train[rng.permutation(len(train))]
        head.train()
        run, n = 0.0, 0
        for a in range(0, len(order), args.bs):
            part = np.sort(order[a:a + args.bs])
            logits = head(torch.from_numpy(np.asarray(feat[part])).to(dev).float())

            loss = torch.nn.functional.cross_entropy(logits.reshape(-1, logits.shape[-1]),
                                                     torch.from_numpy(lab[part]).to(dev).reshape(-1), ignore_index=-1)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            run += loss.item()
            n += 1
        head.eval()
        rows = report(f"epoch {ep + 1} (train {run / n:.4f})", per_label(head, feat, lab, mv, rating, val, dev, (1.0,)), one, baseline)
        if rows["act"]["all"] > best[0]:
            best = (rows["act"]["all"], copy.deepcopy(head.state_dict()), ep + 1, rows)
    gain = {k: {b: v - baseline[k][b] for b, v in best[3][k].items()} for k in METRICS}
    head.load_state_dict(best[1])
    vs_rows = vs_report("vs-bot (best epoch)", head)
    torch.save({"aux": best[1], "meta": {"ckpt": ckpt.name, "loss": "full action", "held_out": best[3], "epoch": best[2],
                                         "baseline": baseline, "gain_vs_fitted_t": gain, "vs_bot": vs_rows, "fitted_t": t_fit, "data": args.data,
                                         "split": "player pair", "train_rows": int(len(train)), "val_rows": int(len(val))}},
               out / "head.pt")
    print(f"best: epoch {best[2]}, held-out act LL {best[0]:.4f} -> {out / 'head.pt'}")


if __name__ == "__main__":
    main()

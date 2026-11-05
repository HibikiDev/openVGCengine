

















from __future__ import annotations

import argparse
import copy
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.mining.dataset import OUT, is_bot
from vgc_suite.mining.finetune_opp import _pid, held_out
from vgc_trainer.model import load_weights
from vgc_trainer.preview import _pl_logp
from vgc_trainer.showdown.agent import Agent, sheet_tokens
from vgc_trainer.showdown.sheets import playable_sheet
from vgc_trainer.amp import pick_device

BACK_PAIRS = list(itertools.permutations(range(4), 2))
LOG_DIRS = [ROOT / "trainer/runs" / d / "logs" for d in ("replays", "replays_live", "replays_mb", "replays_ma")]
_GAME_RE = __import__("re").compile(r"\|Game (\d)|>Game (\d)<")


def game_number(gid: str) -> int:


    for d in LOG_DIRS:
        f = d / f"{gid}.log"
        if f.exists():
            with open(f, encoding="utf8", errors="replace") as fh:
                for _, ln in zip(range(400), fh):
                    m = _GAME_RE.search(ln)
                    if m:
                        return int(m.group(1) or m.group(2))
            return 0
    return 0


def build(rows_path: Path) -> dict:


    cache: dict[str, np.ndarray | None] = {}

    def tokens(sheet: list[dict]) -> np.ndarray | None:
        key = json.dumps(sheet, sort_keys=True)
        if key not in cache:
            try:
                cache[key] = sheet_tokens(playable_sheet(sheet))
            except Exception:
                cache[key] = None
        return cache[key]

    xs, leads, rests, masks, val, rating, pairs, games = [], [], [], [], [], [], [], []
    for ln in open(rows_path, encoding="utf8"):
        g = json.loads(ln)
        if any(is_bot(p) for p in g["players"].values()):
            continue
        pair = "|".join(sorted(_pid(p) for p in g["players"].values()))
        gno = game_number(g["id"])
        for side, foe in (("p1", "p2"), ("p2", "p1")):
            b = g["bring"].get(side) or []
            if len(b) < 2 or len(g["sheets"][side]) != 6 or len(g["sheets"][foe]) != 6:
                continue
            mine, theirs = tokens(g["sheets"][side]), tokens(g["sheets"][foe])
            if mine is None or theirs is None:
                continue
            rest = [i for i in range(6) if i not in b[:2]]
            xs.append(np.concatenate([mine, theirs]))
            leads.append(b[:2])
            rests.append(rest)
            masks.append([i in b[2:] for i in rest])
            val.append(held_out(pair))
            rating.append((g.get("ratings") or {}).get(side) or 0)
            pairs.append(pair)
            games.append(gno)
    return {"x": np.stack(xs), "lead": np.array(leads), "rest": np.array(rests), "back_mask": np.array(masks), "val": np.array(val),
            "rating": np.array(rating), "pair": np.array(pairs), "game": np.array(games, np.int8)}


def label_logp(lead_s: torch.Tensor, back_s: torch.Tensor, lead: torch.Tensor, rest: torch.Tensor, back_mask: torch.Tensor,
               t: float = 1.0) -> tuple[torch.Tensor, torch.Tensor]:

    b = lead.shape[0]
    all6 = torch.ones(b, 6, dtype=torch.bool, device=lead.device)
    lp_lead = _pl_logp(lead_s / t, lead, all6)
    avail = all6.clone()
    avail[torch.arange(b).unsqueeze(1), lead] = False
    terms = []
    for i, j in BACK_PAIRS:
        picks = torch.stack([rest[:, i], rest[:, j]], 1)
        lp = _pl_logp(back_s / t, picks, avail)

        sel = torch.zeros_like(back_mask)
        sel[:, i] = True
        sel[:, j] = True
        ok = (~back_mask | sel).all(1)
        terms.append(torch.where(ok, lp, torch.full_like(lp, float("-inf"))))
    return lp_lead, torch.logsumexp(torch.stack(terms, 1), 1)


@torch.no_grad()
def choice_ll(net, d: dict, idx: np.ndarray, dev, t: float = 1.0, bs: int = 4096) -> np.ndarray:

    out = []
    for a in range(0, len(idx), bs):
        part = idx[a:a + bs]
        ls, bk, _ = net(torch.from_numpy(d["x"][part]).to(dev))
        l1, l2 = label_logp(ls, bk, *(torch.from_numpy(d[k][part]).to(dev) for k in ("lead", "rest", "back_mask")), t)
        out.append((l1 + l2).cpu().numpy())
    return np.concatenate(out)


@torch.no_grad()
def score(net, d: dict, idx: np.ndarray, dev, t: float = 1.0, bs: int = 4096) -> dict:
    lead_ll, back_ll, top1 = [], [], []
    for a in range(0, len(idx), bs):
        part = idx[a:a + bs]
        x = torch.from_numpy(d["x"][part]).to(dev)
        ls, bk, _ = net(x)
        lead, rest, mask = (torch.from_numpy(d[k][part]).to(dev) for k in ("lead", "rest", "back_mask"))
        l1, l2 = label_logp(ls, bk, lead, rest, mask, t)
        lead_ll.append(l1.cpu().numpy())
        back_ll.append(l2.cpu().numpy())

        p = torch.softmax(ls / t, -1)
        pair_p = p.unsqueeze(2) * p.unsqueeze(1) / (1 - p).unsqueeze(1).clamp(min=1e-6)
        pair_p = pair_p + pair_p.transpose(1, 2)
        pair_p = pair_p - torch.diag_embed(torch.diagonal(pair_p, dim1=1, dim2=2))
        best = pair_p.flatten(1).argmax(1)
        top1.append(((best // 6 == lead.min(1).values) & (best % 6 == lead.max(1).values)
                     | (best % 6 == lead.min(1).values) & (best // 6 == lead.max(1).values)).cpu().numpy())
    lead_ll, back_ll = np.concatenate(lead_ll), np.concatenate(back_ll)
    return {"lead": float(lead_ll.mean()), "back": float(back_ll.mean()), "all": float((lead_ll + back_ll).mean()),
            "top1_pair": float(np.concatenate(top1).mean()), "n": int(len(idx))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--bs", type=int, default=512)
    ap.add_argument("--out", default=str(ROOT / "trainer/runs/opp_human/preview_head.pt"))
    ap.add_argument("--data", help="preview.jsonl files, comma-separated (default: the crawl's); arrays cached as <out>_data.npz")
    ap.add_argument("--rating-mean", type=float, help="weight choices by a normal on the player's rating around this (default: equal)")
    ap.add_argument("--rating-sd", type=float, default=100)
    ap.add_argument("--last", action="store_true", help="keep the last epoch (no epoch selection on the held-out set)")
    ap.add_argument("--ref", help="a reference preview head scored on the identical held-out choices (e.g. the live preview_head.pt)")
    ap.add_argument("--games", help="train on these game numbers only, e.g. 1 (needs arrays built with game numbers)")
    ap.add_argument("--eval-games", help="score on held-out choices of these game numbers only, e.g. 1")
    ap.add_argument("--eval-sources", help="score on held-out choices of these --data positions only, e.g. 0,1 (an extra source's held-out "
                    "choices - e.g. an older regulation - left out of the epoch reads and the --ref read)")
    args = ap.parse_args()
    dev = pick_device()
    agent = Agent(args.ckpt, str(dev))
    base = agent.preview.float().eval()
    srcs = [Path(s) for s in args.data.split(",")] if args.data else [OUT / "preview.jsonl"]
    cache = Path(args.out).with_name(Path(args.out).stem + "_data.npz") if args.data else Path(args.out).with_name("preview_data.npz")
    if cache.exists():
        d = dict(np.load(cache))
    else:
        parts = [build(s) for s in srcs]
        d = {k: np.concatenate([x[k] for x in parts]) for k in parts[0]}
        d["src"] = np.concatenate([np.full(len(x["val"]), i, np.int8) for i, x in enumerate(parts)])
        np.savez_compressed(cache, **d)
    train, val = np.flatnonzero(~d["val"]), np.flatnonzero(d["val"])
    if args.eval_sources:
        val = val[np.isin(d.get("src", np.zeros(len(d["val"]), np.int8))[val], [int(x) for x in args.eval_sources.split(",")])]
    if (args.games or args.eval_games) and "game" not in d:
        sys.exit("these arrays have no game numbers: rebuild them (a new --out, or delete the cached _data.npz)")
    if args.games:
        train = train[np.isin(d["game"][train], [int(x) for x in args.games.split(",")])]
    if args.eval_games:
        val = val[np.isin(d["game"][val], [int(x) for x in args.eval_games.split(",")])]
    if "game" in d:
        print("game numbers (all choices): " + ", ".join(f"G{g} {int((d['game'] == g).sum())}" for g in (0, 1, 2, 3)), flush=True)
    print(f"{len(train)} training choices, {len(val)} held out (by player pair; bots out); "
          f"back mons revealed per choice {d['back_mask'].sum(1).mean():.2f}", flush=True)
    grid = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
    sample = np.random.default_rng(1).choice(train, min(len(train), 30000), replace=False)
    t_fit = max(grid, key=lambda t: score(base, d, sample, dev, t)["all"])
    rb = score(base, d, val, dev, t_fit)
    print(f"baseline (self-play preview head, fitted T={t_fit}): {rb}", flush=True)
    print(f"baseline at T=1: {score(base, d, val, dev, 1.0)}", flush=True)
    net = copy.deepcopy(base).train()
    for prm in net.parameters():
        prm.requires_grad_(True)
    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=1e-4)
    rng = np.random.default_rng(0)
    best = (-1e9, None, 0, None)
    for ep in range(args.epochs):
        order = train[rng.permutation(len(train))]
        net.train()
        run, n = 0.0, 0
        for a in range(0, len(order), args.bs):
            part = order[a:a + args.bs]
            x = torch.from_numpy(d["x"][part]).to(dev)
            ls, bk, _ = net(x)
            l1, l2 = label_logp(ls, bk, *(torch.from_numpy(d[k][part]).to(dev) for k in ("lead", "rest", "back_mask")))
            if args.rating_mean is None:
                loss = -(l1 + l2).mean()
            else:
                r = torch.from_numpy(d["rating"][part].astype(np.float32)).to(dev)
                wt = torch.where(r > 0, torch.exp(-0.5 * ((r - args.rating_mean) / args.rating_sd) ** 2), torch.zeros_like(r)) + 1e-3
                loss = -((l1 + l2) * wt).sum() / wt.sum()
            opt.zero_grad()
            loss.backward()
            opt.step()
            run += loss.item()
            n += 1
        net.eval()
        r = score(net, d, val, dev)
        print(f"epoch {ep + 1} (train {run / n:.4f}): {r}; gain all {r['all'] - rb['all']:+.4f}, lead {r['lead'] - rb['lead']:+.4f}, "
              f"back {r['back'] - rb['back']:+.4f}", flush=True)
        if r["all"] > best[0] or args.last:
            best = (r["all"], copy.deepcopy(net.state_dict()), ep + 1, r)
    torch.save({"preview": best[1], "meta": {"ckpt": Path(args.ckpt).name, "epoch": best[2], "held_out": best[3], "baseline": rb,
                                             "fitted_t": t_fit, "split": "player pair", "data": args.data,
                                             "selection": "last epoch" if args.last else "best held-out epoch"}}, args.out)
    print(f"{'last' if args.last else 'best'} epoch {best[2]} -> {args.out}")
    if args.ref:
        from vgc_suite.mining.finetune_bc import compare
        refn = copy.deepcopy(base)
        load_weights(refn, torch.load(args.ref, map_location=dev, weights_only=True)["preview"])
        net.load_state_dict(best[1])
        net.eval()
        lls = {"ref": choice_ll(refn.eval(), d, val, dev), "start": choice_ll(base, d, val, dev), "fit": choice_ll(net, d, val, dev)}
        src = d.get("src", np.zeros(len(d["val"]), np.int8))[val]
        slices = {"all": np.ones(len(val), bool)}
        for i, s in enumerate(srcs):
            slices[s.parent.name] = src == i
        rv = d["rating"][val]
        tag = "eval sources" if args.eval_sources else "all sources"
        slices[f"1400+ ({tag})"] = rv >= 1400
        slices[f"1500+ ({tag})"] = rv >= 1500
        if "game" in d:
            for gn in (1, 2, 3):
                slices[f"G{gn}"] = d["game"][val] == gn
        print(f"\nheld-out log-likelihood per choice (ref = {Path(args.ref).name} at T=1, start = {Path(args.ckpt).name}'s head at T=1, "
              "fit; 95% interval over player pairs):")
        res = compare(lls, "ref", slices, d["pair"][val])
        Path(args.out).with_suffix(".read.json").write_text(json.dumps({"ref": args.ref, "start": args.ckpt, "data": args.data,
                                                                        "epoch": best[2], "slices": res}, indent=1), encoding="utf8")


if __name__ == "__main__":
    main()
























from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.mining.evaluate import DATA
from vgc_suite.mining.finetune_opp import BUCKETS, KEYS, _pid, held_out, split
from vgc_trainer.canonical import Framed, bare, relabel_masks
from vgc_trainer.model import load_policy, log_prob, narrow_slot_b
from vgc_trainer.showdown.requests import PASS_ACTION, SLOT_ACTIONS
from vgc_trainer.amp import pick_device, amp, grad_scaler

COLS = KEYS + ("my_actions", "masks", "mega", "min_switches", "rating_me")


def arrays(data: Path) -> dict[str, np.ndarray]:

    out_dir = data.with_name("npy")
    out_dir.mkdir(exist_ok=True)
    if not all((out_dir / f"{k}.npy").exists() for k in COLS):
        with np.load(data) as z:
            for k in COLS:
                np.save(out_dir / f"{k}.npy", z[k])
    return {k: np.load(out_dir / f"{k}.npy", mmap_mode="r") for k in COLS}


INDEXES = {"human_data": "trainer/runs/replays/index.jsonl", "human_data_live": "trainer/runs/replays_live/index.jsonl",
           "human_data_live2": "trainer/runs/replays_live/index.jsonl", "human_data_mb": "trainer/runs/replays_mb/index.jsonl",
           "human_data_regi": "trainer/runs/replays_regi/index.jsonl"}


def index_for(name: str) -> str:


    for prefix in ("human_data_live", "human_data_mb", "human_data_regi"):
        if name.startswith(prefix):
            return INDEXES[prefix]
    return INDEXES["human_data"]


class _Cat:


    def __init__(self, parts: list):
        self.parts = parts
        self.off = np.cumsum([0] + [len(p) for p in parts])
        assert all(p.shape[1:] == parts[0].shape[1:] and p.dtype == parts[0].dtype for p in parts), "datasets differ in layout"

    def __len__(self) -> int:
        return int(self.off[-1])

    def __getitem__(self, idx):
        idx = np.asarray(idx)
        src = np.searchsorted(self.off, idx, side="right") - 1
        out = np.empty((len(idx),) + self.parts[0].shape[1:], self.parts[0].dtype)
        for s in np.unique(src):
            m = src == s
            out[m] = self.parts[s][idx[m] - self.off[s]]
        return out

    def __array__(self, dtype=None, copy=None):
        a = np.concatenate([np.asarray(p) for p in self.parts])
        return a.astype(dtype) if dtype is not None else a


def load_many(paths: list[Path]) -> tuple[dict, np.ndarray]:

    ds = [arrays(p) for p in paths]
    src = np.concatenate([np.full(len(x["rating_me"]), i, np.int8) for i, x in enumerate(ds)])
    if len(ds) == 1:
        return ds[0], src
    return {k: _Cat([x[k] for x in ds]) for k in COLS}, src


def bits_of(masks: torch.Tensor) -> torch.Tensor:

    return (masks.unsqueeze(-1) >> torch.arange(SLOT_ACTIONS, device=masks.device)) & 1 == 1


def ids_probe(data: Path, n: int = 200) -> list[str]:

    import json
    out = []
    with open(data.with_name("rows.jsonl"), encoding="utf8") as f:
        for ln in f:
            out.append(json.loads(ln)["id"])
            if len(out) >= n:
                break
    return out


def game_numbers(ids: list[str], cache: Path) -> dict[str, int | None]:

    import json
    import re
    have = json.loads(cache.read_text(encoding="utf8")) if cache.exists() else {}
    for i in ids:
        if i in have:
            continue
        g = None
        for logs in (ROOT / "trainer/runs/replays/logs", ROOT / "trainer/runs/replays_live/logs", ROOT / "trainer/runs/showdown_logs",
                     ROOT / "trainer/runs/replays_regi/logs"):
            f = logs / f"{i}.log"
            if f.exists():
                m = re.search(r"\|uhtml(?:change)?\|bestof\|<h2><strong>Game (\d)</strong>", f.read_text(encoding="utf8", errors="replace"))
                g = int(m.group(1)) if m else None
                break
        have[i] = g
    cache.write_text(json.dumps(have), encoding="utf8")
    return have


def usable(d: dict) -> np.ndarray:


    masks, my = np.asarray(d["masks"]), np.asarray(d["my_actions"])
    choice = (masks != 0) & (masks != (1 << PASS_ACTION))
    lab = my[:, :, 0]
    illegal = (lab >= 0) & (((masks >> np.clip(lab, 0, SLOT_ACTIONS - 1)) & 1) == 0)
    return ~(choice & (lab < 0)).any(1) & ~illegal.any(1)


def batch(d: dict, idx: np.ndarray, dev):
    x = [torch.from_numpy(np.asarray(d[k][idx])).to(dev) for k in KEYS]
    masks = torch.from_numpy(np.asarray(d["masks"][idx]).astype(np.int64)).to(dev)
    bits = bits_of(masks)
    my = torch.from_numpy(np.asarray(d["my_actions"][idx])).to(dev).long()

    only = bits.float().argmax(-1)
    act = torch.where(my[:, :, 0] >= 0, my[:, :, 0], only)
    mega = torch.where(my[:, :, 0] >= 0, my[:, :, 1].clamp(min=0), torch.zeros_like(my[:, :, 1]))
    actions = torch.stack([act, mega], -1)
    mega_ok = torch.from_numpy(np.asarray(d["mega"][idx])).to(dev).bool()
    mins = torch.from_numpy(np.asarray(d["min_switches"][idx])).to(dev)
    return x, bits, actions, mega_ok, mins


def in_frame(pol, x, bits, actions, mega_ok):




    fr = Framed(pol, x, bits)
    if not fr.on:
        return pol, x, bits, actions, mega_ok
    return fr.net, list(fr.inputs), fr.bits, fr.actions_to_canon(actions), relabel_masks(mega_ok, fr.own, fr.foe, fr.perm)


def logp_of(pol, x, bits, actions, mega_ok, mins):
    logits, mega_logits, _, _ = pol(*x, actions)
    mask1 = narrow_slot_b(bits[:, 1], actions[:, 0, 0], mins)
    lp, _ = log_prob(logits.float(), mega_logits.float(), actions, bits[:, 0], mask1, mega_ok)
    return lp, logits, mask1


@torch.no_grad()
def evaluate(pol, d: dict, idx: np.ndarray, dev, bs: int = 1024) -> dict:

    lls, hits, rates_r, rates_s = [], [], [], []
    for a in range(0, len(idx), bs):
        part = idx[a:a + bs]
        x, bits, actions, mega_ok, mins = batch(d, part, dev)
        net, x, bits, actions, mega_ok = in_frame(pol, x, bits, actions, mega_ok)
        with amp(dev):
            lp, logits, mask1 = logp_of(net, x, bits, actions, mega_ok, mins)
        fin = torch.isfinite(lp).cpu().numpy()
        lls.append(np.where(fin, lp.cpu().numpy(), np.nan))
        rating = np.asarray(d["rating_me"][part])
        rates_r.append(rating)
        for s, m in ((0, bits[:, 0]), (1, mask1)):
            real = (m.sum(-1) > 1)
            top = logits[:, s].float().masked_fill(~m, float("-inf")).argmax(-1)
            hits.append(((top == actions[:, s, 0])[real]).cpu().numpy())
            rates_s.append(rating[real.cpu().numpy()])
    ll, hit, rr, rs = np.concatenate(lls), np.concatenate(hits), np.concatenate(rates_r), np.concatenate(rates_s)
    out = {"all": (float(np.nanmean(ll)), float(hit.mean()))}
    for b, lo, hi in BUCKETS:
        mr, ms = (rr >= lo) & (rr < hi), (rs >= lo) & (rs < hi)
        if mr.any() and ms.any():
            out[b] = (float(np.nanmean(ll[mr])), float(hit[ms].mean()))
    out["_dropped"] = (int(np.isnan(ll).sum()), 0.0)
    return out


@torch.no_grad()
def row_ll(pol, d: dict, idx: np.ndarray, dev, bs: int = 1024) -> np.ndarray:

    out = []
    for a in range(0, len(idx), bs):
        x, bits, actions, mega_ok, mins = batch(d, idx[a:a + bs], dev)
        net, x, bits, actions, mega_ok = in_frame(pol, x, bits, actions, mega_ok)
        with amp(dev):
            lp, _, _ = logp_of(net, x, bits, actions, mega_ok, mins)
        lp = lp.float().cpu().numpy()
        out.append(np.where(np.isfinite(lp), lp, np.nan))
    return np.concatenate(out)


def compare(lls: dict[str, np.ndarray], ref: str, slices: dict[str, np.ndarray], pair: np.ndarray, n_boot: int = 2000) -> dict:


    rng = np.random.default_rng(0)
    ok = np.all([np.isfinite(v) for v in lls.values()], axis=0)
    res = {}
    for sname, m in slices.items():
        m = m & ok
        if not m.any():
            continue
        groups, inv = np.unique(pair[m], return_inverse=True)
        cnt = np.bincount(inv, minlength=len(groups)).astype(np.float64)
        row = {"rows": int(m.sum()), "pairs": len(groups)}
        for name, v in lls.items():
            row[name] = float(v[m].mean())
            if name == ref:
                continue
            dsum = np.bincount(inv, weights=v[m] - lls[ref][m], minlength=len(groups))
            boot = []
            for _ in range(n_boot):
                w = np.bincount(rng.integers(0, len(groups), len(groups)), minlength=len(groups))
                boot.append((w * dsum).sum() / (w * cnt).sum())
            row[f"{name}-{ref}"] = (float(dsum.sum() / cnt.sum()), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)))
        res[sname] = row
        parts = [f"{name} {row[name]:.4f}" for name in lls]
        parts += [f"{k} {v[0]:+.4f} [{v[1]:+.4f}, {v[2]:+.4f}]" for k, v in row.items() if "-" in k]
        print(f"  {sname:<26} {row['rows']:>7} rows {row['pairs']:>5} pairs  " + "  ".join(parts), flush=True)
    return res


def show(name: str, r: dict, base: dict | None = None) -> None:
    parts = []
    for b, (ll, hit) in r.items():
        if b == "_dropped":
            parts.append(f"(rows ruled out by slot b's narrowing: {ll})")
            continue
        g = f" ({ll - base[b][0]:+.3f} / {hit - base[b][1]:+.3f})" if base and b in base else ""
        parts.append(f"{b} LL {ll:.3f} top-1 {hit:.3f}{g}")
    print(f"{name:<22} " + "; ".join(parts), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--data", default=str(DATA), help="decisions.npz, or a comma list (rows concatenated; both indexes read)")
    ap.add_argument("--train-sources", help="train on rows of these --data positions only, e.g. 1 (held-out rows: all sources)")
    ap.add_argument("--eval-sources", help="score on held-out rows of these --data positions only, e.g. 0,1 (an extra source's held-out "
                    "rows - e.g. an older regulation - left out of epoch selection and the read)")
    ap.add_argument("--rating-mean", type=float, default=1245, help="rows weighted by a normal on the player's rating around this "
                    "(1245: the live population; 1420: the top-end refit, 10-14)")
    ap.add_argument("--rating-sd", type=float, default=90)
    ap.add_argument("--last", action="store_true", help="keep the last epoch (no epoch selection on the held-out set)")
    ap.add_argument("--ref", help="a reference model scored on the identical held-out rows (e.g. the live bc_66250.pt)")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--bs", type=int, default=512)
    ap.add_argument("--out")
    ap.add_argument("--games", help="keep rows from these game numbers of a Bo3 series (train and held-out), e.g. 3 or 1,2 - read from "
                    "each replay's 'Game N of a best-of-3' line (cached in <data>/game_numbers.json)")
    ap.add_argument("--eval-games", help="score on held-out rows of these game numbers instead (default: --games)")
    ap.add_argument("--max-rows", type=int, help="cap the training rows (a same-size control for a --games subset)")
    ap.add_argument("--half", choices=["a", "b"], help="train on one half of the training player pairs (a held-out human model: "
                    "the league member on one half, the judge on the other)")
    ap.add_argument("--preview", help="a preview head to pack into the checkpoint instead of the starting one's (e.g. the human "
                    "preview head, opp_human/preview_head.pt)")
    args = ap.parse_args()
    dev = pick_device()
    ck = torch.load(args.ckpt, map_location=dev, weights_only=True)
    base = load_policy(ck, dev)
    paths = [Path(p) for p in args.data.split(",")]
    data = paths[0]
    d, source = load_many(paths)
    train, val = split([p.with_name("rows.jsonl") for p in paths], len(d["rating_me"]),
                       [ROOT / index_for(p.parent.name) for p in paths])
    ok = usable(d)
    train, val = train[ok[train]], val[ok[val]]
    if len(paths) > 1 and (args.half or args.games):
        raise SystemExit("--half / --games read the crawl's files: one --data only")
    if args.train_sources:
        train = train[np.isin(source[train], [int(s) for s in args.train_sources.split(",")])]
    if args.eval_sources:
        val = val[np.isin(source[val], [int(s) for s in args.eval_sources.split(",")])]
    if args.half:
        import json
        pairs = {}
        for ln in open(ROOT / index_for(data.parent.name), encoding="utf8"):
            r = json.loads(ln)
            pairs[r["id"]] = "|".join(sorted(_pid(x) for x in r.get("players", [])))
        if not any(g in pairs for g in ids_probe(data)):
            raise SystemExit(f"--half: no game of {data.parent.name} is in {index_for(data.parent.name)}")
        ids = [json.loads(ln)["id"] for ln in open(data.with_name("rows.jsonl"), encoding="utf8")]
        in_a = np.array([held_out("half:" + pairs.get(g, g), 0.5) for g in ids])
        train = train[in_a[train] == (args.half == "a")]
    if args.games:
        import json
        ids = [json.loads(ln)["id"] for ln in open(data.with_name("rows.jsonl"), encoding="utf8")]
        gn = game_numbers(sorted(set(ids)), data.with_name("game_numbers.json"))
        keep = {int(g) for g in args.games.split(",")}
        keep_val = {int(g) for g in (args.eval_games or args.games).split(",")}
        train = train[np.array([gn.get(i) in keep for i in ids])[train]]
        val = val[np.array([gn.get(i) in keep_val for i in ids])[val]]
    if args.max_rows and len(train) > args.max_rows:
        train = np.sort(np.random.default_rng(1).choice(train, args.max_rows, replace=False))
    rating = np.asarray(d["rating_me"]).astype(np.float64)
    w = np.exp(-0.5 * ((rating - args.rating_mean) / args.rating_sd) ** 2)
    w = np.where(rating > 0, w, w[rating > 0].mean())
    w = w / w[train].mean()
    ess = w[train].sum() ** 2 / (w[train] ** 2).sum()
    print(f"{Path(args.ckpt).name}: {len(train)} training rows (weighted toward ~{args.rating_mean:.0f}, ESS {ess:.0f}), {len(val)} held out "
          f"(per source: train {np.bincount(source[train], minlength=len(paths)).tolist()}, held out "
          f"{np.bincount(source[val], minlength=len(paths)).tolist()})", flush=True)
    rb = evaluate(base, d, val, dev)
    show("start (the checkpoint)", rb)
    pol = copy.deepcopy(base).train()
    opt = torch.optim.AdamW(pol.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * ((len(train) + args.bs - 1) // args.bs)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    scaler = grad_scaler(dev)
    rng = np.random.default_rng(0)
    best = (-1e9, None, 0, None)
    for ep in range(args.epochs):
        order = train[rng.permutation(len(train))]
        pol.train()
        run, n = 0.0, 0
        for a in range(0, len(order), args.bs):
            part = np.sort(order[a:a + args.bs])
            x, bits, actions, mega_ok, mins = batch(d, part, dev)
            net, x, bits, actions, mega_ok = in_frame(pol, x, bits, actions, mega_ok)
            wt = torch.from_numpy(w[part]).to(dev).float()
            with amp(dev):
                lp, _, _ = logp_of(net, x, bits, actions, mega_ok, mins)
            fin = torch.isfinite(lp)
            wt = wt * fin
            loss = -(torch.where(fin, lp, torch.zeros_like(lp)) * wt).sum() / wt.sum()
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(pol.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            run += loss.item()
            n += 1
            if n % 200 == 0:
                print(f"  epoch {ep + 1} step {n}: loss {run / n:.4f}", flush=True)
        pol.eval()
        r = evaluate(pol, d, val, dev)
        show(f"epoch {ep + 1} (train {run / n:.3f})", r, rb)
        if r["all"][0] > best[0] or args.last:
            best = (r["all"][0], copy.deepcopy(bare(pol).state_dict()), ep + 1, r)
    out = Path(args.out or ROOT / f"trainer/runs/opp_human/bc_{Path(args.ckpt).stem.split('_')[-1]}{'_' + args.half if args.half else ''}.pt")
    meta = dict(ck.get("meta", {}), bc={"from": Path(args.ckpt).name, "epoch": best[2], "held_out": best[3], "start": rb,
                                        "weights": f"N({args.rating_mean:.0f}, {args.rating_sd:.0f}) on rating_me", "split": "player pair",
                                        "half": args.half, "preview": args.preview or "the starting checkpoint's",
                                        "data": args.data, "train_sources": args.train_sources,
                                        "selection": "last epoch" if args.last else "best held-out epoch"})
    preview = ck.get("preview")
    if args.preview:
        preview = torch.load(args.preview, map_location=dev, weights_only=True)["preview"]
    torch.save({"model": best[1], "preview": preview, "update": ck.get("update"), "games": ck.get("games"), "meta": meta}, out)
    print(f"best epoch {best[2]} -> {out}")
    if args.ref:
        report(args, base, best, paths, d, source, train, val, dev, out)


def report(args, base, best, paths, d, source, train, val, dev, out) -> None:

    import json
    rows = []
    for p in paths:
        with open(p.with_name("rows.jsonl"), encoding="utf8") as f:
            rows += [(r["id"], _pid(r.get("player", ""))) for r in map(json.loads, f)]
    pairs = {}
    for p in paths:
        with open(ROOT / index_for(p.parent.name), encoding="utf8") as f:
            for r in map(json.loads, f):
                pairs[r["id"]] = "|".join(sorted(_pid(x) for x in r.get("players", [])))
    seen = {rows[i][1] for i in train}
    pair = np.array([pairs.get(rows[i][0], rows[i][0]) for i in val])
    unseen = np.array([rows[i][1] not in seen for i in val])
    fit = copy.deepcopy(base)
    bare(fit).load_state_dict(best[1])
    fit.eval()
    refm = load_policy(torch.load(args.ref, map_location=dev, weights_only=True), dev).eval()
    lls = {"ref": row_ll(refm, d, val, dev), "start": row_ll(base.eval(), d, val, dev), "fit": row_ll(fit, d, val, dev)}
    src = source[val]
    slices = {"all": np.ones(len(val), bool)}
    for i, p in enumerate(paths):
        slices[p.parent.name] = src == i
        if i:
            slices[p.parent.name + " (player unseen)"] = (src == i) & unseen
    rv = np.asarray(d["rating_me"])[val]
    tag = "eval sources" if args.eval_sources else "all sources"
    slices[f"1400+ ({tag})"] = rv >= 1400
    slices[f"1500+ ({tag})"] = rv >= 1500
    print(f"\nheld-out log-likelihood per row (ref = {Path(args.ref).name}, start = {Path(args.ckpt).name}, fit = {out.name}; "
          "95% interval over player pairs):")
    res = compare(lls, "ref", slices, pair)
    out.with_suffix(".read.json").write_text(json.dumps({"ref": args.ref, "start": args.ckpt, "fit": str(out), "data": args.data,
                                                          "train_sources": args.train_sources, "eval_sources": args.eval_sources,
                                                          "epochs": args.epochs, "slices": res},
                                                         indent=1), encoding="utf8")


if __name__ == "__main__":
    main()

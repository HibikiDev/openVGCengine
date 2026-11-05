""
















from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.mining.bo3_preview import _series_of
from vgc_suite.mining.bots import is_bot
from vgc_suite.mining.dataset import LOGS
from vgc_suite.mining.evaluate import DATA
from vgc_suite.mining.series_summary import N_GLOBAL, N_TOKEN, SERIES_FEATURES, SERIES_VERSION, SeriesState
from vgc_trainer.amp import pick_device, amp, grad_scaler

HD = Path(DATA).parent
OUT = HD / "series.npz"
SWITCH_BASE = 16


def _meta() -> tuple[list[str], list[str], list[str], np.ndarray]:
    ids, sides, players, bot = [], [], [], []
    for ln in open(HD / "rows.jsonl", encoding="utf8"):
        r = json.loads(ln)
        ids.append(r["id"])
        sides.append(r["side"])
        players.append(r["player"])
        bot.append(bool(r.get("bot")) or is_bot(r["player"]))
    return ids, sides, players, np.array(bot)


def _series_map(ids: list[str]) -> dict[str, tuple[str, int] | None]:
    cache = HD / "series_of.json"
    have = json.loads(cache.read_text(encoding="utf8")) if cache.exists() else {}
    todo = sorted(set(ids) - set(have))
    for g in todo:
        f = LOGS / f"{g}.log"
        have[g] = list(_series_of(f)) if f.exists() else None
    if todo:
        cache.write_text(json.dumps(have), encoding="utf8")
    return {k: (tuple(v) if v else None) for k, v in have.items()}


def run_state(seqs: list[np.ndarray], gno: np.ndarray, won: np.ndarray, arr: dict, chunk: int = 4096):


    n_rows = len(gno)
    feat = np.zeros((n_rows, SERIES_FEATURES), np.float16)
    valid = np.zeros(n_rows, bool)
    cap = np.zeros(4, np.int64)
    my_act, foe_act = arr["my_actions"], arr["foe_actions"]
    for c0 in range(0, len(seqs), chunk):
        part = seqs[c0:c0 + chunk]
        n = len(part)
        st = SeriesState(n, sides=1)
        lens = np.array([len(s) for s in part])
        present = [set(gno[s].tolist()) for s in part]
        for step in range(lens.max()):
            slots = np.nonzero(lens > step)[0]
            rows = np.array([part[k][step] for k in slots])
            if step:
                prev = np.array([part[k][step - 1] for k in slots])
                ch = gno[rows] != gno[prev]
                if ch.any():
                    s_ch, p_ch = slots[ch], prev[ch]
                    cap[0] += int(st.cur_moves[s_ch, 0, :6].sum())
                    cap[1] += int(st.cur_moves[s_ch, 0, 6:].sum())
                    code = np.where(won[p_ch] == 1, 0, np.where(won[p_ch] == 0, 1, 2))
                    st.end_game(s_ch, code)
            g = gno[rows]
            ok = (st.game[slots] == g) & np.array([all(x in present[k] for x in range(1, gi)) for k, gi in zip(slots, g)])
            feat[rows] = st.features()[slots, 0].astype(np.float16)
            valid[rows] = ok
            full = {}
            for key in ("field", "mon_ids", "mon_features", "history"):
                a = np.asarray(arr[key][np.sort(rows)])
                buf = np.zeros((n,) + a.shape[1:], a.dtype)
                buf[slots[np.argsort(rows)]] = a
                full[key] = buf
            st.observe(0, full["field"], full["mon_ids"], full["mon_features"], full["history"], slots)
        for k in range(n):
            cap[0] += int(st.cur_moves[k, 0, :6].sum())
            cap[1] += int(st.cur_moves[k, 0, 6:].sum())
    for s in seqs:
        ma, fa = np.asarray(my_act[np.sort(s)])[:, :, 0], np.asarray(foe_act[np.sort(s)])
        fa = fa[..., 0] if fa.ndim == 3 else fa
        cap[2] += int(((ma >= 0) & (ma < SWITCH_BASE)).sum())
        cap[3] += int(((fa >= 0) & (fa < SWITCH_BASE)).sum())
    return feat, valid, cap


def build() -> None:
    from vgc_suite.mining.finetune_bc import arrays
    t0 = time.time()
    ids, sides, players, bot = _meta()
    smap = _series_map(ids)
    z = np.load(Path(DATA))
    won, turn = z["won"], z["turn"]
    arr = dict(arrays(Path(DATA)))
    arr["foe_actions"] = z["foe_actions"]
    n = len(ids)
    gno = np.zeros(n, np.int64)
    bot_games = {ids[i] for i in np.nonzero(bot)[0]}
    groups: dict[tuple[str, str], list[int]] = {}
    for i in range(n):
        s = smap.get(ids[i])
        if not s or ids[i] in bot_games:
            continue
        gno[i] = s[1]
        groups.setdefault((s[0], players[i].lower()), []).append(i)
    keys = sorted(groups)
    seqs = [np.array(sorted(groups[k], key=lambda i: (gno[i], int(turn[i]), i))) for k in keys]
    seq_id = np.full(n, -1, np.int64)
    for j, s in enumerate(seqs):
        seq_id[s] = j
    print(f"{n} rows; {len(seqs)} (series, player) sequences; rows in series {int((gno > 0).sum())} "
          f"(G1 {int((gno == 1).sum())}, G2 {int((gno == 2).sum())}, G3 {int((gno == 3).sum())}) ({time.time() - t0:.0f} s)", flush=True)
    feat, valid, cap = run_state(seqs, gno, won, arr)
    print(f"summary built ({time.time() - t0:.0f} s); valid G2 {int((valid & (gno == 2)).sum())}, G3 {int((valid & (gno == 3)).sum())}")
    print(f"move-use capture: own {cap[0]} counted of {cap[2]} labelled move actions ({cap[0] / max(cap[2], 1):.2f}); "
          f"foe {cap[1]} of {cap[3]} ({cap[1] / max(cap[3], 1):.2f})")

    rng = np.random.default_rng(0)
    pick = [seqs[j] for j in rng.choice(len(seqs), 100, replace=False) if len(set(gno[seqs[j]].tolist())) > 1][:100]
    bad = 0
    for s in pick:
        f1, v1, _ = run_state([s], gno, won, arr, chunk=1)
        bad += int(not (np.array_equal(f1[s], feat[s]) and np.array_equal(v1[s], valid[s])))
    print(f"reference check: {len(pick) - bad} of {len(pick)} multi-game sequences identical one at a time")
    np.savez(OUT, feat=feat, valid=valid, gno=gno, seq=seq_id, version=SERIES_VERSION)
    print(f"-> {OUT} ({time.time() - t0:.0f} s)")


class SeriesHooks:



    def __init__(self, pol, d: int, dev):
        self.s = None
        self.field = torch.nn.Parameter(torch.zeros(d, N_GLOBAL, device=dev))
        self.mon = torch.nn.Parameter(torch.zeros(d, N_TOKEN, device=dev))
        pol.field.register_forward_hook(self._field)
        pol.mon_feat.register_forward_hook(self._mon)

    def _field(self, mod, inp, out):
        if self.s is None:
            return out
        return out + torch.nn.functional.linear(self.s[:, :N_GLOBAL].to(out.dtype), self.field.to(out.dtype))

    def _mon(self, mod, inp, out):
        if self.s is None:
            return out
        sr = self.s[:, N_GLOBAL:].reshape(-1, out.shape[1], N_TOKEN).to(out.dtype)
        return out + torch.nn.functional.linear(sr, self.mon.to(out.dtype))


def fit(args) -> None:
    from vgc_suite.mining.finetune_bc import arrays, batch, logp_of, usable
    from vgc_suite.mining.finetune_opp import split
    from vgc_trainer.model import load_policy
    dev = pick_device()
    t0 = time.time()
    d = arrays(Path(DATA))
    sz = np.load(OUT)
    feat, valid, gno, seq = sz["feat"], sz["valid"], sz["gno"], sz["seq"]
    turn = np.load(Path(DATA))["turn"]
    rating = np.asarray(d["rating_me"]).astype(np.float64)
    train, val = split(HD / "rows.jsonl", len(rating), ROOT / "trainer/runs/replays/index.jsonl")
    ok = usable(d)
    train, val = train[ok[train]], val[ok[val]]
    later = (gno >= 2) & valid
    rng = np.random.default_rng(0)
    tr23 = train[later[train]]
    tr1 = train[(gno[train] == 1) & (seq[train] >= 0)]
    tr1 = np.sort(rng.choice(tr1, min(len(tr1), len(tr23) // 2), replace=False))
    tr = np.sort(np.concatenate([tr23, tr1]))
    ev = val[((gno[val] == 1) & (seq[val] >= 0)) | later[val]]
    w = np.exp(-0.5 * ((rating - 1245) / 90) ** 2)
    w = np.where(rating > 0, w, w[rating > 0].mean())
    w = w / w[tr].mean()
    print(f"training rows {len(tr)} (G2/G3 {len(tr23)}, G1 {len(tr1)}); held-out scored {len(ev)} (G1 {int((gno[ev] == 1).sum())}, "
          f"G2 {int((gno[ev] == 2).sum())}, G3 {int((gno[ev] == 3).sum())})", flush=True)
    ck = torch.load(args.ckpt, map_location=dev, weights_only=True)
    base = load_policy(ck, dev).eval()
    dmodel = base.field.out_features

    perm = feat.copy()
    for g in (2, 3):
        r = ev[gno[ev] == g]
        perm[r] = feat[np.random.default_rng(g).permutation(r)]

    def score(pol, hooks, src) -> np.ndarray:
        out = np.full(len(ev), np.nan)
        with torch.no_grad():
            for a in range(0, len(ev), 1024):
                part = ev[a:a + 1024]
                x, bits, actions, mega_ok, mins = batch(d, part, dev)
                if hooks is not None:
                    hooks.s = None if src is None else torch.from_numpy(src[part].astype(np.float32)).to(dev)
                with amp(dev):
                    lp, _, _ = logp_of(pol, x, bits, actions, mega_ok, mins)
                lp = lp.float().cpu().numpy()
                out[a:a + len(part)] = np.where(np.isfinite(lp), lp, np.nan)
        if hooks is not None:
            hooks.s = None
        return out

    def train_arm(use_series: bool):
        pol = copy.deepcopy(base).train()
        hooks = SeriesHooks(pol, dmodel, dev) if use_series else None
        params = list(pol.parameters()) + ([hooks.field, hooks.mon] if hooks else [])


        groups = [{"params": list(pol.parameters()), "lr": args.lr, "weight_decay": 1e-4}]
        if hooks:
            groups.append({"params": [hooks.field, hooks.mon], "lr": args.map_lr, "weight_decay": 0.0})
        opt = torch.optim.AdamW(groups)
        steps = (len(tr) + args.bs - 1) // args.bs
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
        scaler = grad_scaler(dev)
        order = tr[np.random.default_rng(1).permutation(len(tr))]
        run, n = 0.0, 0
        for a in range(0, len(order), args.bs):
            part = np.sort(order[a:a + args.bs])
            x, bits, actions, mega_ok, mins = batch(d, part, dev)
            if hooks:
                hooks.s = torch.from_numpy(feat[part].astype(np.float32)).to(dev)
            wt = torch.from_numpy(w[part]).to(dev).float()
            with amp(dev):
                lp, _, _ = logp_of(pol, x, bits, actions, mega_ok, mins)
            fin = torch.isfinite(lp)
            wt = wt * fin
            loss = -(torch.where(fin, lp, torch.zeros_like(lp)) * wt).sum() / wt.sum()
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            run += loss.item()
            n += 1
            if n % 200 == 0:
                print(f"  {'S' if use_series else 'Z'} step {n}/{steps}: loss {run / n:.4f} ({time.time() - t0:.0f} s)", flush=True)
        pol.eval()
        if hooks:
            hooks.s = None
        return pol, hooks


    chk = copy.deepcopy(base).eval()
    hk = SeriesHooks(chk, dmodel, dev)
    probe = ev[:64]
    x, bits, actions, mega_ok, mins = batch(d, probe, dev)
    with torch.no_grad():
        hk.s = torch.from_numpy(feat[probe].astype(np.float32)).to(dev)
        a1 = logp_of(chk, x, bits, actions, mega_ok, mins)[0]
        a0 = logp_of(base, x, bits, actions, mega_ok, mins)[0]
    print(f"identity check (zero maps): max |dlogp| {float((a1 - a0).abs().max()):.2e}", flush=True)
    del chk, hk

    ll = {"start": score(base, None, None)}
    pz, _ = train_arm(False)
    ll["Z"] = score(pz, None, None)
    del pz
    ps, hs = train_arm(True)
    ll["S"] = score(ps, hs, feat)
    ll["S_perm"] = score(ps, hs, perm)
    ll["S_none"] = score(ps, hs, None)

    g, t, sq, rt = gno[ev], turn[ev], seq[ev], rating[ev]
    prev_lost = np.zeros(len(ev), bool)
    res = feat[ev][:, 4].astype(np.float32)
    prev_lost = res < 0
    slices = {"G1": g == 1, "G2/G3": g >= 2, "G2/G3 turns 1-3": (g >= 2) & (t <= 3), "G2": g == 2, "G3": g == 3,
              "G2/G3 1200+": (g >= 2) & (rt >= 1200), "G2/G3 after a loss": (g >= 2) & prev_lost, "G2/G3 after a win": (g >= 2) & (res > 0)}

    def boot(diff: np.ndarray, m: np.ndarray, reps: int = 1000) -> tuple[float, float, float]:
        keep = m & np.isfinite(diff)
        u, inv = np.unique(sq[keep], return_inverse=True)
        sums = np.bincount(inv, weights=diff[keep], minlength=len(u))
        cnt = np.bincount(inv, minlength=len(u)).astype(np.float64)
        r = np.random.default_rng(7)
        bs = []
        for _ in range(reps):
            k = r.integers(0, len(u), len(u))
            bs.append(sums[k].sum() / cnt[k].sum())
        return float(diff[keep].mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))

    out = {"ckpt": Path(args.ckpt).name, "version": SERIES_VERSION, "rows": {"train": len(tr), "eval": len(ev)}, "slices": {}}
    print(f"\n{'slice':<22} {'n':>7} {'start':>8} {'Z':>8} {'S':>8}   S-Z [95%]              S-S_perm [95%]          S_none-Z")
    for name, m in slices.items():
        sz_ = boot(ll["S"] - ll["Z"], m)
        sp_ = boot(ll["S"] - ll["S_perm"], m)
        sn_ = boot(ll["S_none"] - ll["Z"], m)
        row = {k: float(np.nanmean(v[m])) for k, v in ll.items()}
        out["slices"][name] = {"n": int(m.sum()), **row, "S-Z": sz_, "S-S_perm": sp_, "S_none-Z": sn_}
        print(f"{name:<22} {int(m.sum()):>7} {row['start']:>8.3f} {row['Z']:>8.3f} {row['S']:>8.3f}   "
              f"{sz_[0]:+.4f} [{sz_[1]:+.4f},{sz_[2]:+.4f}]  {sp_[0]:+.4f} [{sp_[1]:+.4f},{sp_[2]:+.4f}]  {sn_[0]:+.4f}")
    a, b = out["slices"]["G2/G3"], out["slices"]["G2/G3 turns 1-3"]
    passed = ((a["S-Z"][0] >= 0.02 and a["S-S_perm"][1] > 0) or (b["S-Z"][0] >= 0.04 and b["S-S_perm"][1] > 0))
    g1_ok = boot(ll["S"] - ll["Z"], slices["G1"])[1] >= -0.005
    out["verdict"] = {"pass": bool(passed and g1_ok), "primary": bool(passed), "g1_no_harm": bool(g1_ok)}
    print(f"series maps: field column norms {[round(x, 3) for x in hs.field.norm(dim=0).tolist()]}, mon "
          f"{[round(x, 3) for x in hs.mon.norm(dim=0).tolist()]} (the existing input maps: field "
          f"{float(ps.field.weight.norm(dim=0).mean()):.2f}, mon_feat {float(ps.mon_feat.weight.norm(dim=0).mean()):.2f})")
    print(f"\nverdict: {'PASS' if passed and g1_ok else 'FAIL'} (G2/G3 bar {'met' if passed else 'not met'}; G1 no-harm "
          f"{'ok' if g1_ok else 'violated'}) ({time.time() - t0:.0f} s)")
    (ROOT / "trainer/runs/opp_human/series_human.json").write_text(json.dumps(out, indent=1), encoding="utf8")
    torch.save({"model": ps.state_dict(), "series_maps": {"field": hs.field.detach().cpu(), "mon": hs.mon.detach().cpu()},
                "series_version": SERIES_VERSION, "meta": dict(ck.get("meta", {}), series_human=out["verdict"]),
                "preview": ck.get("preview")}, ROOT / "trainer/runs/opp_human/bc_series_S.pt")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    f = sub.add_parser("fit")
    f.add_argument("--ckpt", default=str(ROOT / "trainer/runs/opp_human/bc_66250.pt"))
    f.add_argument("--lr", type=float, default=1e-4)
    f.add_argument("--bs", type=int, default=512)
    f.add_argument("--map-lr", type=float, default=3e-3, help="the series maps' lr (zero-init; the policy's lr is far too small)")
    args = ap.parse_args()
    build() if args.cmd == "build" else fit(args)


if __name__ == "__main__":
    main()

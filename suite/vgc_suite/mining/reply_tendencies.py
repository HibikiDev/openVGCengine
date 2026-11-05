""














from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.mining.finetune_bc import batch, bits_of, index_for, load_many, usable
from vgc_suite.mining.finetune_opp import split
from vgc_trainer.model import load_policy, narrow_slot_b
from vgc_trainer.showdown.requests import SWITCH_BASE
from vgc_trainer.amp import pick_device, amp

DATA = [ROOT / "trainer/runs/human_data/decisions.npz", ROOT / "trainer/runs/human_data_live/decisions.npz"]
PROTECTS = {"Protect", "Detect", "Spiky Shield", "King's Shield", "Baneful Bunker", "Silk Trap", "Burning Bulwark", "Obstruct"}
MOVES, HP, ACTIVE_A, ACTIVE_B, FAINTED, TURNS_ACTIVE, PROTECT_STREAK = 3, 5, 2, 3, 4, 23, 29


def learn_ids(d: dict, rows_paths: list[Path], sample: int = 400_000) -> tuple[set, set]:

    prot, fake = Counter(), Counter()
    i = 0
    acts = np.asarray(d["my_actions"])
    for rp in rows_paths:
        with open(rp, encoding="utf8") as f:
            for ln in f:
                if i >= sample:
                    break
                r = json.loads(ln)
                for s, txt in enumerate(r.get("played") or []):
                    a = int(acts[i, s, 0])
                    if txt and 0 <= a < SWITCH_BASE:
                        name = txt.split(" -> ")[0]
                        if name in PROTECTS or name == "Fake Out":
                            feats = np.asarray(d["mon_features"][[i]])[0]
                            tok = int(np.argmax(feats[:6, ACTIVE_A if s == 0 else ACTIVE_B]))
                            mid = int(np.asarray(d["mon_ids"][[i]])[0][tok, MOVES + a // 4])
                            (prot if name in PROTECTS else fake)[mid] += 1
                i += 1
    keep = lambda c: {k for k, v in c.items() if v >= max(20, 0.02 * sum(c.values())) and k}
    return keep(prot), keep(fake)


@torch.no_grad()
def run(pol, d: dict, idx: np.ndarray, dev, prot_ids: set, fake_ids: set, bs: int = 1024) -> list[dict]:
    out = []
    pid = torch.tensor(sorted(prot_ids), device=dev)
    fid = torch.tensor(sorted(fake_ids), device=dev)
    for a in range(0, len(idx), bs):
        part = idx[a:a + bs]
        x, bits, actions, mega_ok, mins = batch(d, part, dev)
        with amp(dev):
            logits = pol(*x, actions)[0].float()
        mask1 = narrow_slot_b(bits[:, 1], actions[:, 0, 0], mins)
        feats, ids = x[2], x[1]
        turn = np.asarray(d["turn"][part]) if "turn" in d else None
        fainted_me = feats[:, :6, FAINTED].sum(-1)
        fainted_foe = feats[:, 6:, FAINTED].sum(-1)
        lead = (fainted_foe - fainted_me).cpu().numpy()
        for s, m in ((0, bits[:, 0]), (1, mask1)):
            real = m.sum(-1) > 1
            p = torch.softmax(logits[:, s].masked_fill(~m, float("-inf")), -1)
            tok = feats[:, :6, ACTIVE_A if s == 0 else ACTIVE_B].argmax(-1)
            ar = torch.arange(len(part), device=dev)
            moves = ids[ar, tok, MOVES:MOVES + 4].long()
            is_p = torch.isin(moves, pid).repeat_interleave(4, -1)
            is_f = torch.isin(moves, fid).repeat_interleave(4, -1)
            p_prot = (p[:, :SWITCH_BASE] * is_p).sum(-1)
            p_fake = (p[:, :SWITCH_BASE] * is_f).sum(-1)
            p_sw = p[:, SWITCH_BASE:SWITCH_BASE + 4].sum(-1)
            act = actions[:, s, 0]
            mv = act.clamp(max=SWITCH_BASE - 1)
            a_prot = (act < SWITCH_BASE) & is_p.gather(1, mv[:, None])[:, 0]
            a_fake = (act < SWITCH_BASE) & is_f.gather(1, mv[:, None])[:, 0]
            a_sw = (act >= SWITCH_BASE) & (act < SWITCH_BASE + 4)
            fake_ok = (m[:, :SWITCH_BASE] & is_f).any(-1) & (feats[ar, tok, TURNS_ACTIVE] < 0.3)
            sw_ok = m[:, SWITCH_BASE:SWITCH_BASE + 4].any(-1)
            prot_ok = (m[:, :SWITCH_BASE] & is_p).any(-1)
            other_sw = (actions[:, 0, 0] >= SWITCH_BASE) & (actions[:, 0, 0] < SWITCH_BASE + 4)
            cols = {k: v.cpu().numpy() for k, v in dict(real=real, p_prot=p_prot, p_fake=p_fake, p_sw=p_sw, a_prot=a_prot, a_fake=a_fake,
                    a_sw=a_sw, fake_ok=fake_ok, sw_ok=sw_ok, prot_ok=prot_ok, hp=feats[ar, tok, HP],
                    streak=feats[ar, tok, PROTECT_STREAK], other_sw=other_sw).items()}
            for j in range(len(part)):
                if not cols["real"][j]:
                    continue
                out.append({"slot": s, "row": int(part[j]), "turn": int(turn[j]) if turn is not None else None, "lead": float(lead[j]),
                            **{k: float(v[j]) for k, v in cols.items() if k != "real"}})
    return out


def table(recs: list[dict]) -> dict:
    def cell(sel, a, p):
        xs = [r for r in recs if sel(r)]
        if not xs:
            return None
        return {"n": len(xs), "actual": round(float(np.mean([r[a] for r in xs])), 4), "model": round(float(np.mean([r[p] for r in xs])), 4)}

    prot = lambda r: r["prot_ok"] > 0
    out = {
        "protect turn 1": cell(lambda r: prot(r) and r["turn"] == 1, "a_prot", "p_prot"),
        "protect later, fresh": cell(lambda r: prot(r) and (r["turn"] or 0) > 1 and r["streak"] == 0, "a_prot", "p_prot"),
        "double protect": cell(lambda r: prot(r) and r["streak"] > 0, "a_prot", "p_prot"),
        "double protect, hp < 50%": cell(lambda r: prot(r) and r["streak"] > 0 and r["hp"] < 0.5, "a_prot", "p_prot"),
        "double protect, hp >= 50%": cell(lambda r: prot(r) and r["streak"] > 0 and r["hp"] >= 0.5, "a_prot", "p_prot"),
        "double protect, behind": cell(lambda r: prot(r) and r["streak"] > 0 and r["lead"] < 0, "a_prot", "p_prot"),
        "double protect, even": cell(lambda r: prot(r) and r["streak"] > 0 and r["lead"] == 0, "a_prot", "p_prot"),
        "double protect, ahead": cell(lambda r: prot(r) and r["streak"] > 0 and r["lead"] > 0, "a_prot", "p_prot"),
        "fresh protect, behind": cell(lambda r: prot(r) and (r["turn"] or 0) > 1 and r["streak"] == 0 and r["lead"] < 0, "a_prot", "p_prot"),
        "fresh protect, ahead": cell(lambda r: prot(r) and (r["turn"] or 0) > 1 and r["streak"] == 0 and r["lead"] > 0, "a_prot", "p_prot"),
        "fake out when it works": cell(lambda r: r["fake_ok"] > 0, "a_fake", "p_fake"),
        "switch (slot can switch)": cell(lambda r: r["sw_ok"] > 0, "a_sw", "p_sw"),
        "slot b switch after slot a switched": cell(lambda r: r["slot"] == 1 and r["sw_ok"] > 0 and r["other_sw"] > 0, "a_sw", "p_sw"),
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", action="append", help="policy checkpoints to score (default: the live reply model)")
    ap.add_argument("--min-rating", type=int, default=1300)
    ap.add_argument("--max-rows", type=int, default=120_000, help="held-out rows scored (a random subset when more)")
    ap.add_argument("--out", default=str(ROOT / "trainer/runs/reply_tendencies.json"))
    args = ap.parse_args()
    from vgc_suite.core.bundle import path as pinned
    models = args.model or [str(pinned("reply_policy"))]
    dev = pick_device()
    d, _ = load_many(DATA)
    rows_paths = [p.with_name("rows.jsonl") for p in DATA]
    _, val = split(rows_paths, len(d["rating_me"]), [ROOT / index_for(p.parent.name) for p in DATA])
    val = val[usable(d)[val]]
    if args.max_rows and len(val) > args.max_rows:
        val = np.sort(np.random.default_rng(0).choice(val, args.max_rows, replace=False))
    d["turn"] = np.concatenate([np.load(p)["turn"] for p in DATA])
    prot_ids, fake_ids = learn_ids(d, rows_paths)
    print(f"{len(val)} held-out rows; protect move ids {sorted(prot_ids)}, Fake Out {sorted(fake_ids)}", flush=True)
    rating = np.asarray(d["rating_me"])
    result = {}
    for mp in models:
        pol = load_policy(torch.load(mp, map_location=dev, weights_only=True), dev).eval()
        recs = run(pol, d, val, dev, prot_ids, fake_ids)
        result[Path(mp).name] = {"all": table(recs), f"{args.min_rating}+": table([r for r in recs if rating[r["row"]] >= args.min_rating])}
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf8")
    for name, by in result.items():
        for bucket, t in by.items():
            print(f"\n{name} - held-out human rows, {bucket}")
            print(f"  {'situation':40} {'n':>7} {'humans':>8} {'model':>8}")
            for k, v in t.items():
                if v:
                    print(f"  {k:40} {v['n']:>7} {v['actual']:>8.3f} {v['model']:>8.3f}")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

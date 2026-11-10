





from __future__ import annotations

import re
import json
import math
from pathlib import Path

import torch

from vgc_trainer.canonical import _FOE_PERM, Framed
from vgc_trainer.model import narrow_slot_b
from vgc_trainer.showdown.agent import Agent, canonical_targets
from vgc_trainer.showdown.requests import PASS_ACTION, SLOT_ACTIONS, describe_action

from .positions import Decision



CALIBRATION = Path(__file__).resolve().parents[3] / "trainer/runs/opp_human/value_calibration.json"


def load_calibration(ckpt: str) -> dict | None:
    try:
        cal = json.loads(CALIBRATION.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return None
    return cal if cal.get("ckpt") == Path(ckpt).name else None


def calibrated_win(raw: float, turn: int, cal: dict) -> float:
    eps = cal.get("eps", 0.005)
    r = min(1 - eps, max(eps, raw))
    for b in cal["buckets"].values():
        if b["lo"] <= turn < b["hi"]:
            return 1 / (1 + math.exp(-(b["a"] * math.log(r / (1 - r)) + b["b"])))
    return raw



TIERS = ((0.75, "agrees"), (0.35, "close alternative"), (0.1, "model prefers another"), (0.0, "model strongly prefers another"))


def tier(p_played: float, p_top: float) -> str:
    ratio = p_played / max(p_top, 1e-9)
    return next(name for lo, name in TIERS if ratio >= lo)


def _label(d: Decision, slot: int, action: int, mega: bool = False) -> str:
    ally = d.active[1 - slot] or ""
    ctx = d.ctx or {}
    tag = (ctx.get("gimmick_played") or [None, None])[slot] or ctx.get("gimmick", "+mega")


    from vgc_trainer.showdown.requests import describe_action
    return describe_action(action, d.moves[slot], d.foe_active, ally, d.display) + (f" {tag}" if mega else "")


@torch.inference_mode()
def policy_view(agent: Agent, d: Decision, k: int = 3) -> dict:





    dev = agent.dev
    masks = d.masks
    bits = torch.tensor([[[(masks.actions[s] >> i) & 1 == 1 for i in range(SLOT_ACTIONS)] for s in (0, 1)]], device=dev)
    min_switches = torch.tensor([masks.min_switches], device=dev)
    inputs = tuple(torch.from_numpy(a[None]).to(dev) for a in d.obs) + (torch.tensor([(list(d.bring) + [i for i in range(6) if i not in d.bring])[:4]], device=dev),)
    fr = Framed(agent.policy, inputs, bits)
    pol, bits = fr.net, fr.bits
    flip_own, flip_foe = bool(fr.own[0]), bool(fr.foe[0])
    to_c = (lambda a: int(_FOE_PERM[a])) if flip_foe else (lambda a: int(a))
    foe_empty = list(d.ctx.get("foe_empty", [False, False]))
    foe_empty = foe_empty[::-1] if flip_foe else foe_empty
    st = pol.encode(*fr.inputs)
    v = float(st.value[0])
    out = {"value": round(v, 3), "win": round(min(1.0, max(0.0, (v + 1) / 2)), 3), "slots": [None, None],
           "field": {"mine": list(d.active), "foe": list(d.foe_active)}}
    cond = None
    mask = bits[:, 0]
    a0 = m0 = None
    first = None
    for c in (0, 1):
        slot = c ^ int(flip_own)
        if c == 1:
            mask = narrow_slot_b(bits[:, 1], torch.tensor([a0], device=dev), min_switches)
            cond = pol.condition(st, torch.tensor([a0], device=dev), torch.tensor([m0], device=dev))
        logits, mega_logit = pol.slot_logits(st, c, cond)
        if not bool(mask[0].any()) or d.active[slot] is None:
            a0, m0 = (PASS_ACTION, False) if c == 0 else (a0, m0)
            continue
        p = torch.softmax(logits[0].float().masked_fill(~mask[0], float("-inf")), -1)
        p = fr.probs_to_engine(canonical_targets(p, mask[0], foe_empty)[None])[0]
        top_i = torch.argsort(p, descending=True)[:k].tolist()
        played = d.played[slot]


        label = _label(d, slot, played[0], played[1]) if played is not None else d.played_text[slot]
        hit = None
        if played is not None and d.played_text[slot] and " -> " in d.played_text[slot] and " -> " in label:
            was, now = re.sub(r" \+[\w-]+$", "", label.split(" -> ", 1)[1]), d.played_text[slot].split(" -> ", 1)[1]
            hit = now if now != was else None
        entry = {"mon": d.active[slot], "top": [(_label(d, slot, a), round(float(p[a]), 3)) for a in top_i if float(p[a]) > 0.005],
                 "played": label, "hit": hit}
        if played is not None:
            pa = float(p[played[0]])
            rank = int((p > pa).sum()) + 1
            entry.update(played_p=round(pa, 3), played_rank=rank, tier=tier(pa, float(p[top_i[0]])))
        if c == 1 and first is not None:
            entry["after"] = first
        out["slots"][slot] = entry
        if c == 0:
            first = {"mon": d.active[slot], "act": label if played is not None else _label(d, slot, top_i[0]),
                     "own_pick": played is None}
            a0, m0 = (played if played is not None else (top_i[0], False))
            a0, m0 = to_c(a0), bool(m0)
    return out


def analyze(log, decisions_by_side: dict[str, list[Decision]], agent: Agent, ckpt: str) -> dict:

    res = {"replay": {"source": log.source, "players": log.players, "format": log.fmt, "ots": log.ots},
           "model": {"checkpoint": ckpt}, "view": "player", "search": None, "turns": [], "win_curve": {}}
    cal = load_calibration(ckpt)
    res["model"]["calibrated"] = cal is not None
    res["bring"] = {}
    res["guessed"] = any(d.guessed for decs in decisions_by_side.values() for d in decs[:1])
    for side, decs in decisions_by_side.items():
        res["win_curve"][side] = []
        res["bring"][side] = decs[0].fill if decs else None
        for d in decs:
            view = policy_view(agent, d)
            if cal is not None:
                view["win_raw"] = view["win"]
                view["win"] = round(calibrated_win(view["win"], d.turn, cal), 3)
            res["turns"].append({"turn": d.turn, "side": side, **view})
            res["win_curve"][side].append([d.turn, view["win"]])
    res["turns"].sort(key=lambda t: (t["turn"], t["side"]))
    return res


def render_text(res: dict) -> str:

    out = [f"{res['replay']['players'].get('p1', 'p1')} vs {res['replay']['players'].get('p2', 'p2')}  ({res['replay']['format']}, "
           f"model {res['model']['checkpoint']}; win estimates "
           + ("calibrated on human games)" if res["model"].get("calibrated") else "are the model's raw view, uncalibrated)")]
    for side, f in (res.get("bring") or {}).items():
        if f:
            alt = "; ".join(f"{', '.join(a['assumed'])} {a['p']:.0%}" for a in f.get("alts", []))
            out.append(f"{res['replay']['players'].get(side, side)}: {f['shown']} of 4 shown - assumed {', '.join(f['assumed'])}"
                       + (f" ({f['p']:.0%}" + (f"; else {alt}" if alt else "") + ")" if f.get("p") is not None else ""))
    for t in res["turns"]:
        name = res["replay"]["players"].get(t["side"], t["side"])
        out.append(f"turn {t['turn']}  {name}  win {t['win']:.0%}")
        for s in t["slots"]:
            if not s:
                continue
            fav = ", ".join(f"{a} {p:.0%}" for a, p in s["top"])
            played = s.get("played") or "?"
            note = f"  [{s['tier']}: played at {s['played_p']:.0%}, rank {s['played_rank']}]" if "tier" in s else ""
            out.append(f"   {s['mon']:<14} played {played}{note}\n   {'':<14} model: {fav}")
    return "\n".join(out)

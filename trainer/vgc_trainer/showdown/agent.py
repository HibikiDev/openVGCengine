


from __future__ import annotations

import numpy as np
import torch
import vgc_engine as ve

from ..canonical import _FOE_PERM, Framed, bare
from ..model import (gimmick_codes, load_policy, load_weights, obs_compatible, sample_independent, slot_a_gimmick, slot_a_mask,
                     slot_b_gimmick, slot_b_mask)
from ..preview import PreviewNet, sample_bring
from .requests import PASS_ACTION, SLOT_ACTIONS, SWITCH_BASE, TARGET_ALLY, TARGET_FOE_A, TARGET_FOE_B, RequestMasks




CLOSER_MIN_TURN = 4



M_IN_BATTLE, M_ACTIVE_A, M_ACTIVE_B, M_FAINTED, M_HP, M_PERISH = 1, 2, 3, 4, 5, 30
SHADOW_TAG = ve.lookup("ability", "Shadow Tag")
SHED_SHELL = ve.lookup("item", "Shed Shell")
GHOST = 9


def perish_doomed(mon_ids: torch.Tensor, feats: torch.Tensor) -> torch.Tensor:


    foe_tag = ((mon_ids[:, 6:, 2] == SHADOW_TAG) & (feats[:, 6:, M_FAINTED] < 0.5) & (feats[:, 6:, M_IN_BATTLE] > 0.5)
               & ((feats[:, 6:, M_ACTIVE_A] > 0.5) | (feats[:, 6:, M_ACTIVE_B] > 0.5))).any(1)
    active = (feats[:, :6, M_ACTIVE_A] > 0.5) | (feats[:, :6, M_ACTIVE_B] > 0.5)
    free = ((mon_ids[:, :6, 7] == GHOST) | (mon_ids[:, :6, 8] == GHOST) | (mon_ids[:, :6, 2] == SHADOW_TAG)
            | (mon_ids[:, :6, 1] == SHED_SHELL))
    return active & (feats[:, :6, M_PERISH] > 0.01) & ~free & foe_tag[:, None]


def sheet_tokens(sheet: list[dict], fmt: str | None = None, as_opponent: bool = False) -> np.ndarray:





    pool = ve.BattlePool(1)
    out = np.zeros((ve.ROSTER_SIZE, ve.MON_IDS), np.int32)
    n = len(sheet)
    padded = (list(sheet) * ve.ROSTER_SIZE)[: ve.ROSTER_SIZE]
    tid = pool.register_team(padded) if fmt is None else pool.register_team(padded, fmt)
    from ..env import SHEETS_OPEN
    pool.sheet_ids(tid, out, as_opponent, *((True,) if SHEETS_OPEN.get() and fmt is not None else ()))
    out[n:] = 0
    return out


def _top(p: torch.Tensor, k: int, keep: int | None = None) -> list[tuple[int, float]]:

    vals, idx = p.topk(min(k, p.numel()))
    out = [(int(i), round(float(v), 3)) for v, i in zip(vals, idx) if v > 0.005]
    if keep is not None and keep not in [i for i, _ in out]:
        out.append((keep, round(float(p[keep]), 3)))
    return out


def explain(s: dict, policy, inputs, k: int = 4) -> dict:





    assert bare(policy) is policy or not policy.on, "explain(): a canonical-slots net goes through Agent._select"
    v = float(s["value"][0])
    out = {"value": round(v, 3), "win": round(min(1.0, max(0.0, (v + 1) / 2)), 3), "slots": [], "foe": None}
    for slot, mask in enumerate((s["mask0"], s["mask1"])):
        chosen, mega = s["actions"][0, slot].tolist()
        if not bool(mask[0].any()):
            out["slots"].append(None)
            continue
        p = torch.softmax(s["logits"][0, slot].float().masked_fill(~mask[0], float("-inf")), -1)
        entry = {"top": _top(p, k, int(chosen)), "chosen": int(chosen), "p": round(float(p[chosen]), 3)}
        if bool(s["mega_ok"][0, slot]):
            entry["mega_p"] = round(float(torch.sigmoid(s["mega_logits"][0, slot].float())), 3)
        out["slots"].append(entry)
    if hasattr(bare(policy), "opponent_logits"):
        fr = Framed(policy, inputs)
        aux = torch.softmax(fr.aux_to_engine(fr.net.opponent_logits(*fr.inputs).float())[0], -1)
        out["foe"] = [_top(aux[slot], 3) for slot in (0, 1)]
    return out


def canonical_targets(p: torch.Tensor, mask: torch.Tensor, foe_empty: list[bool]) -> torch.Tensor:


    p = p.clone()
    for t in (TARGET_FOE_A, TARGET_FOE_B):
        if foe_empty[t] and not foe_empty[1 - t]:
            for m in range(4):
                a, b = m * 4 + t, m * 4 + (1 - t)
                if mask[b] and p[a] > 0:
                    p[b] += p[a]
                    p[a] = 0.0
    return p


class Agent:









    def __init__(self, checkpoint: str, device: str = "cpu", seed: int = 0, temperature: float = 1.0, min_p: float = 0.0,
                 closer: float | None = None):
        self.temperature, self.min_p, self.closer = temperature, min_p, closer
        self.checkpoint = checkpoint
        self.dev = torch.device(device)
        self.gen = torch.Generator(device=self.dev)
        self.gen.manual_seed(seed)
        self.rng = np.random.default_rng(seed)
        self.policy = self.preview = None
        self.last_explain: dict | None = None
        if checkpoint != "random":
            ck = torch.load(checkpoint, map_location=self.dev)
            meta = ck.get("meta", {})

            if not obs_compatible(meta.get("obs_version"), ve.OBS_VERSION):
                raise ValueError(f"{checkpoint} was trained on observation v{meta['obs_version']}, this engine is v{ve.OBS_VERSION}")
            self.policy = load_policy(ck, self.dev)
            if ck.get("preview"):
                self.preview = PreviewNet().to(self.dev).eval()
                load_weights(self.preview, ck["preview"])

    def load_preview_head(self, path: str) -> torch.nn.Module:


        import copy
        sd = torch.load(path, map_location=self.dev, weights_only=True)
        net = copy.deepcopy(self.preview).float() if self.preview is not None else PreviewNet().to(self.dev)
        load_weights(net, sd["preview"])
        return net.eval()

    @torch.inference_mode()
    def choose_bring(self, my_sheet: list[dict], foe_sheet: list[dict], avoid_lead: list[int] | None = None,
                     force_lead: list[int] | None = None, avoid_leads: list[list[int]] | None = None,
                     fmt: str | None = None, closed: bool | None = None, alt_head: torch.nn.Module | None = None) -> list[int]:








        n = len(my_sheet)
        self.last_preview = None
        if self.preview is None:
            return [int(i) for i in self.rng.permutation(n)[:4]]


        closed = fmt is not None if closed is None else closed
        x = np.concatenate([sheet_tokens(my_sheet, fmt), sheet_tokens(foe_sheet, fmt, as_opponent=closed)])[None]
        lead, back, _ = self.preview(torch.from_numpy(x).to(self.dev))
        if n < 6:
            lead[:, n:] = float("-inf")
            back[:, n:] = float("-inf")


        s = lead[0].double()
        p = torch.softmax(s, -1)
        rest = [torch.softmax(s.masked_fill(torch.arange(6, device=s.device) == i, float("-inf")), -1) for i in range(n)]
        pairs = {(i, j): float(p[i] * rest[i][j]) for i in range(n) for j in range(n) if i != j}
        unordered = lambda i, j: pairs[i, j] + pairs[j, i]
        avoid_set = [set(x) for x in (avoid_leads or []) if set(x) <= set(range(n))]
        if avoid_lead and set(avoid_lead) <= set(range(n)):
            avoid_set.append(set(avoid_lead))
        allowed = [k for k in pairs if set(k) not in avoid_set]
        forced = force_lead is not None and len(set(force_lead)) == 2 and set(force_lead) <= set(range(n))
        rank, self.last_alt = pairs, False
        if alt_head is not None and not forced and avoid_set and allowed:
            a_lead, a_back, _ = alt_head(torch.from_numpy(x).to(self.dev))
            a_lead, a_back = a_lead.float(), a_back.float()
            if n < 6:
                a_lead[:, n:] = float("-inf")
                a_back[:, n:] = float("-inf")
            sa = a_lead[0].double()
            pa = torch.softmax(sa, -1)
            rest_a = [torch.softmax(sa.masked_fill(torch.arange(6, device=sa.device) == i, float("-inf")), -1) for i in range(n)]
            rank = {(i, j): float(pa[i] * rest_a[i][j]) for i in range(n) for j in range(n) if i != j}
            back, self.last_alt = a_back, True
        if forced or (avoid_set and allowed):
            i, j = (int(force_lead[0]), int(force_lead[1])) if forced else max(allowed, key=rank.get)
            avail = torch.ones(6, dtype=torch.bool, device=lead.device)
            avail[n:] = False
            avail[[i, j]] = False
            backs = []
            for _ in range(2):
                q = torch.softmax(back[0].masked_fill(~avail, float("-inf")), -1)
                k = int(torch.multinomial(q, 1, generator=self.gen))
                backs.append(k)
                avail[k] = False
            bring = [i, j, *backs]
        else:
            bring = [int(i) for i in sample_bring(lead, back, self.gen)[0][0].tolist()]
        best = max(pairs, key=pairs.get)
        top = sorted({tuple(sorted(k)) for k in pairs}, key=lambda k: -unordered(*k))[:3]
        self.last_preview = {"lead_p": round(unordered(*bring[:2]), 3), "top_p": round(unordered(*best), 3),
                             "changed": bool(avoid_lead or avoid_leads or forced), "by_human_head": self.last_alt,
                             "top_pairs": [[list(k), round(unordered(*k), 3)] for k in top]}
        return bring

    @torch.inference_mode()
    def act(self, obs, masks: RequestMasks, bring: list[int], ctx: dict | None = None) -> list[tuple[int, bool]]:



        bits = torch.tensor([[[(masks.actions[s] >> i) & 1 == 1 for i in range(SLOT_ACTIONS)] for s in (0, 1)]], device=self.dev)

        mega = torch.tensor([masks.gimmick_codes()], dtype=torch.int8, device=self.dev)
        min_switches = torch.tensor([masks.min_switches], device=self.dev)
        if self.policy is None:
            self.last_explain = None
            return random_actions(bits, mega, min_switches, self.gen)
        inputs = tuple(torch.from_numpy(a[None]).to(self.dev) for a in obs) + (torch.tensor([bring], device=self.dev),)
        if not hasattr(bare(self.policy), "condition"):
            s = self.policy.act(inputs, bits, mega, min_switches, self.gen, temperature=self.temperature)
            self.last_explain = explain(s, self.policy, inputs)
            return [(int(a), bool(m)) for a, m in s["actions"][0].tolist()]
        return self._select(inputs, bits, mega, min_switches, ctx or {})

    def _pick(self, p: torch.Tensor, closer: bool, damaging: list[bool]) -> int:

        best = int(p.argmax())
        if closer:
            def risky(a: int) -> bool:
                return SWITCH_BASE <= a < PASS_ACTION or (a < SWITCH_BASE and a % 4 == TARGET_ALLY and damaging[a // 4])

            if risky(best) and float(p[best]) <= 0.5:
                safe = torch.tensor([bool(p[a] > 0) and not risky(a) for a in range(SLOT_ACTIONS)], device=p.device)
                if bool(safe.any()):
                    best = int(p.masked_fill(~safe, -1.0).argmax())
            return best
        if self.temperature == 0:
            return best
        q = p.masked_fill(p < self.min_p, 0.0)
        q[best] = p[best]
        if self.temperature != 1:
            q = q.pow(1.0 / self.temperature)
        return int(torch.multinomial(q / q.sum(), 1, generator=self.gen))

    def _select(self, inputs, bits, mega, min_switches, ctx: dict) -> list[tuple[int, bool]]:





        fr = Framed(self.policy, inputs, bits, mega)
        pol, inputs, bits, mega = fr.net, fr.inputs, fr.bits, fr.codes
        flip_own, flip_foe = bool(fr.own[0]), bool(fr.foe[0])
        st = pol.encode(*inputs)
        v = float(st.value[0])
        doomed = perish_doomed(inputs[1], inputs[2])
        if bool(doomed.any()):



            f = inputs[2].clone()
            f[:, :6, M_HP] = torch.where(doomed, torch.zeros_like(f[:, :6, M_HP]), f[:, :6, M_HP])
            f[:, :6, M_FAINTED] = torch.where(doomed, torch.ones_like(f[:, :6, M_FAINTED]), f[:, :6, M_FAINTED])
            v = float(pol.values(inputs[0], inputs[1], f, inputs[3], inputs[4])[0])
        closer = self.closer is not None and v > self.closer and ctx.get("turn", CLOSER_MIN_TURN) >= CLOSER_MIN_TURN
        foe_empty = list(ctx.get("foe_empty", [False, False]))
        damaging = list(ctx.get("damaging", [[True] * 4, [True] * 4]))
        if flip_foe:
            foe_empty = foe_empty[::-1]
        if flip_own:
            damaging = damaging[::-1]
        out = {"value": round(v, 3), "win": round(min(1.0, max(0.0, (v + 1) / 2)), 3), "mode": "closer" if closer else "sample",
               "slots": [], "foe": None}
        if bool(doomed.any()):
            out["perish_doomed"] = int(doomed.sum())
        actions: list[tuple[int, bool]] = []
        cond = None
        codes = gimmick_codes(mega)
        mask = slot_a_mask(bits[:, 0], codes)
        same = torch.zeros(1, dtype=torch.bool, device=self.dev)
        for slot in (0, 1):
            if slot == 1:
                a0, m0 = actions[0]
                mask, same = slot_b_mask(bits[:, 1], codes, torch.tensor([a0], device=self.dev), torch.tensor([m0], device=self.dev),
                                         min_switches)
                cond = pol.condition(st, torch.tensor([a0], device=self.dev), torch.tensor([m0], device=self.dev))
            logits, mega_logit = pol.slot_logits(st, slot, cond)
            if not bool(mask[0].any()):
                actions.append((PASS_ACTION, False))
                out["slots"].append(None)
                continue
            p = torch.softmax(logits[0].float().masked_fill(~mask[0], float("-inf")), -1)
            p = canonical_targets(p, mask[0], foe_empty)
            a = self._pick(p, closer, damaging[slot])
            at = torch.tensor([a], device=self.dev)
            ok_t, forced_t = slot_a_gimmick(codes, at) if slot == 0 else slot_b_gimmick(codes, at, same)
            ok, forced = bool(ok_t[0]), bool(forced_t[0])
            if hasattr(pol, "gimmick_logit"):
                mega_logit = pol.gimmick_logit(st, slot, at, mega_logit)
            mp = float(torch.sigmoid(mega_logit[0].float()))
            m = forced or (ok and (mp > 0.5 if closer or self.temperature == 0
                                   else float(torch.rand(1, generator=self.gen, device=self.gen.device)) < mp))
            actions.append((a, m))
            entry = {"top": _top(p, 4, a), "chosen": a, "p": round(float(p[a]), 3)}
            if ok:
                entry["mega_p"] = round(mp, 3)
            out["slots"].append(entry)
        aux = torch.softmax(fr.aux_to_engine(pol.aux_logits(st).float())[0], -1)
        out["foe"] = [_top(aux[slot], 3) for slot in (0, 1)]
        if fr.on:

            act = (lambda a: int(_FOE_PERM[a])) if flip_foe else (lambda a: a)
            for e in out["slots"]:
                if e is not None:
                    e["top"] = [(act(a), p) for a, p in e["top"]]
                    e["chosen"] = act(e["chosen"])
            if flip_own:
                out["slots"] = out["slots"][::-1]
            back = fr.actions_to_engine(torch.tensor([[[a, int(m)] for a, m in actions]], device=self.dev))[0].tolist()
            actions = [(int(a), bool(m)) for a, m in back]
        self.last_explain = out
        return actions


def random_actions(bits, mega, min_switches, gen) -> list[tuple[int, bool]]:

    zeros = torch.zeros(bits.shape, device=bits.device)
    s = sample_independent(zeros, zeros[..., 0], zeros[:, 0, 0], bits, mega, min_switches, gen)
    return [(int(a), bool(m)) for a, m in s["actions"][0].tolist()]

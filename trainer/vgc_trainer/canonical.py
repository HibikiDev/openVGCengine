



















from __future__ import annotations

import numpy as np
import torch
from torch import nn


ROSTER = 6
M_ACTIVE_A, M_ACTIVE_B = 2, 3
EV_SWITCH = 2
TARGET_FOE_A, TARGET_FOE_B = 0, 1
SWITCH_BASE = 16

_FOE_PERM = np.arange(64)
for _mv in range(4):
    _FOE_PERM[[_mv * 4 + TARGET_FOE_A, _mv * 4 + TARGET_FOE_B]] = [_mv * 4 + TARGET_FOE_B, _mv * 4 + TARGET_FOE_A]


def flips(mon_features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:


    idx = torch.arange(ROSTER, device=mon_features.device)

    def key(lo: int, col: int) -> torch.Tensor:
        on = mon_features[:, lo:lo + ROSTER, col] > 0.5
        return torch.where(on, idx, ROSTER).amin(1)

    return key(0, M_ACTIVE_B) < key(0, M_ACTIVE_A), key(ROSTER, M_ACTIVE_B) < key(ROSTER, M_ACTIVE_A)


def relabel_obs(mon_features: torch.Tensor, history: torch.Tensor, own: torch.Tensor, foe: torch.Tensor):

    f = mon_features.clone()
    for lo, flag in ((0, own), (ROSTER, foe)):
        a, b = mon_features[:, lo:lo + ROSTER, M_ACTIVE_A], mon_features[:, lo:lo + ROSTER, M_ACTIVE_B]
        o = flag[:, None]
        f[:, lo:lo + ROSTER, M_ACTIVE_A] = torch.where(o, b, a)
        f[:, lo:lo + ROSTER, M_ACTIVE_B] = torch.where(o, a, b)
    h = history.clone()
    actor = history[..., 1]
    mine = (actor >= 0) & (actor < ROSTER)
    flip = (history[..., 0] == EV_SWITCH) & ((mine & own[:, None]) | ((actor >= ROSTER) & foe[:, None]))
    h[..., 4] = torch.where(flip, 1 - history[..., 4], history[..., 4])
    return f, h


def relabel_masks(m: torch.Tensor, own: torch.Tensor, foe: torch.Tensor, perm: torch.Tensor | None = None) -> torch.Tensor:


    o = own.view(-1, *([1] * (m.dim() - 1)))
    m = torch.where(o, m.flip(1), m)
    if m.dim() == 3:
        perm = (torch.as_tensor(_FOE_PERM, device=m.device) if perm is None else perm)[: m.shape[-1]]
        m = torch.where(foe[:, None, None], m[:, :, perm], m)
    return m


def relabel_actions(a: torch.Tensor, own: torch.Tensor, foe: torch.Tensor) -> torch.Tensor:

    a = torch.where(own[:, None, None], a.flip(1), a)
    i = a[..., 0]
    t = i % 4
    swap = foe[:, None] & (i < SWITCH_BASE) & ((t == TARGET_FOE_A) | (t == TARGET_FOE_B))
    out = a.clone()
    out[..., 0] = torch.where(swap, i - t + (TARGET_FOE_A + TARGET_FOE_B - t), i)
    return out


def relabel_actions_np(a: np.ndarray, own: np.ndarray, foe: np.ndarray) -> np.ndarray:

    a = np.where(own.reshape(-1, *([1] * (a.ndim - 1))), a[:, ::-1], a)
    i = a[..., 0] if a.ndim == 3 else a
    t = i % 4
    swap = foe[:, None] & (i < SWITCH_BASE) & ((t == TARGET_FOE_A) | (t == TARGET_FOE_B))
    j = np.where(swap, i - t + (TARGET_FOE_A + TARGET_FOE_B - t), i)
    if a.ndim == 3:
        a = a.copy()
        a[..., 0] = j
        return a
    return j


BYPASS = frozenset({"forward", "encode", "slot_logits", "condition", "gimmick_logit", "opponent_logits", "aux_logits", "aux"})


class CanonicalPolicy(nn.Module):




    def __init__(self, inner: nn.Module, on: bool):
        super().__init__()
        self.inner = inner
        dev = next(inner.parameters()).device
        self.register_buffer("canon_on", torch.tensor(bool(on), device=dev))
        self.register_buffer("foe_perm", torch.as_tensor(_FOE_PERM, device=dev), persistent=False)
        self.on = bool(on)

    def _flips(self, mon_features):
        own, foe = flips(mon_features)
        return own & self.canon_on, foe & self.canon_on

    def act(self, inputs, bits, mega_allowed, min_switches, generator=None, temperature: float = 1.0, repeat: int = 1):
        field, ids, feats, hist, bring = inputs
        own, foe = self._flips(feats)
        f, h = relabel_obs(feats, hist, own, foe)

        r_own, r_foe = (own, foe) if repeat == 1 else (own.repeat_interleave(repeat), foe.repeat_interleave(repeat))
        masks = (relabel_masks(bits, r_own, r_foe, self.foe_perm), relabel_masks(mega_allowed, r_own, r_foe, self.foe_perm))
        extra = {} if repeat == 1 else {"repeat": repeat}
        s = self.inner.act((field, ids, f, h, bring), *masks, min_switches, generator, temperature, **extra)
        out = dict(s)
        out["c_actions"] = s["actions"]
        out["actions"] = relabel_actions(s["actions"], r_own, r_foe)
        out["c_mon_features"], out["c_history"], out["flip_own"], out["flip_foe"] = f, h, own, foe
        return out

    def values(self, field, mon_ids, mon_features, history, bring=None):
        own, foe = self._flips(mon_features)
        f, h = relabel_obs(mon_features, history, own, foe)
        return self.inner.values(field, mon_ids, f, h, bring)

    def forward(self, *a, **k):
        if self.on:
            raise RuntimeError("canonical-slots network: forward() bypasses the canonical frame - call act / values, or relabel first")
        return self.inner(*a, **k)

    def __getattr__(self, name):
        try:
            return super().__getattr__(name)
        except AttributeError:
            pass
        if name in BYPASS and self.__dict__.get("on"):
            raise RuntimeError(f"canonical-slots network: {name} bypasses the canonical frame (canonical.py) - this caller isn't "
                               "canonicalised yet")
        return getattr(self._modules["inner"], name)


def is_canonical(meta: dict | None) -> bool:

    return bool(((meta or {}).get("cfg") or {}).get("canonical_slots"))


def bare(policy: nn.Module) -> nn.Module:


    return policy._modules["inner"] if isinstance(policy, CanonicalPolicy) else policy


class Framed:








    def __init__(self, policy: nn.Module, inputs, bits: torch.Tensor | None = None, codes: torch.Tensor | None = None):
        self.on = isinstance(policy, CanonicalPolicy) and policy.on
        self.net = bare(policy)
        field, ids, feats, hist, *rest = inputs
        if self.on:
            self.own, self.foe = flips(feats)
            f, h = relabel_obs(feats, hist, self.own, self.foe)
            self.inputs = (field, ids, f, h, *rest)
            self.perm = policy.foe_perm
            self.bits = None if bits is None else relabel_masks(bits, self.own, self.foe, self.perm)
            self.codes = None if codes is None else relabel_masks(codes, self.own, self.foe, self.perm)
        else:
            self.own = self.foe = torch.zeros(feats.shape[0], dtype=torch.bool, device=feats.device)
            self.inputs, self.bits, self.codes, self.perm = tuple(inputs), bits, codes, None

    def engine_slot(self, c_slot: int) -> torch.Tensor:

        return (self.own.long() ^ c_slot) if self.on else torch.full_like(self.own, c_slot, dtype=torch.long)

    def probs_to_engine(self, p: torch.Tensor) -> torch.Tensor:

        if not self.on:
            return p
        return torch.where(self.foe[:, None], p[:, self.perm[: p.shape[-1]]], p)

    def actions_to_engine(self, a: torch.Tensor) -> torch.Tensor:

        return relabel_actions(a, self.own, self.foe) if self.on else a

    actions_to_canon = actions_to_engine

    def aux_to_engine(self, aux: torch.Tensor) -> torch.Tensor:

        if not self.on:
            return aux
        aux = torch.where(self.foe[:, None, None], aux.flip(1), aux)
        return torch.where(self.own[:, None, None], aux[:, :, self.perm[: aux.shape[-1]]], aux)

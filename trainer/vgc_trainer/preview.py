







from __future__ import annotations

import itertools

import torch
import torch.nn as nn
import vgc_engine as ve


class PreviewNet(nn.Module):
    def __init__(self, d: int = 128, layers: int = 2, heads: int = 4):
        super().__init__()
        self.species = nn.Embedding(ve.SPECIES_VOCAB, d)
        self.item = nn.Embedding(ve.ITEM_VOCAB, d)
        self.ability = nn.Embedding(ve.ABILITY_VOCAB, d)
        self.move = nn.Embedding(ve.MOVE_VOCAB, d)
        self.type_emb = nn.Embedding(ve.TYPE_VOCAB, d)
        self.owner = nn.Embedding(2, d)
        layer = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=0.0, batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d)
        self.scores = nn.Linear(d, 2)
        self.value = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))

    def forward(self, sheet_ids):

        ids = sheet_ids.long()

        owner = torch.cat([torch.zeros(6, dtype=torch.long, device=ids.device), torch.ones(6, dtype=torch.long, device=ids.device)])
        x = (
            self.species(ids[..., 0])
            + self.item(ids[..., 1])
            + self.ability(ids[..., 2])
            + self.move(ids[..., 3:7]).sum(-2)
            + self.type_emb(ids[..., 7:9]).sum(-2)
            + self.owner(owner)
        )
        x = self.norm(self.encoder(x))
        s = self.scores(x[:, :6]).float()
        return s[..., 0], s[..., 1], self.value(x.mean(1)).squeeze(-1).float()


def _hot(p):


    return nn.functional.one_hot(p.long(), 6).bool()


def _pl_logp(scores, picks, available):

    avail = available.clone()
    total = torch.zeros(scores.shape[0], device=scores.device)
    for j in range(picks.shape[1]):
        lp = torch.log_softmax(scores.masked_fill(~avail, float("-inf")), -1)
        p = picks[:, j]
        total = total + lp.gather(1, p.unsqueeze(1)).squeeze(1)
        avail = avail & ~_hot(p)
    return total


def sample_bring(lead, back, generator=None):

    b = lead.shape[0]
    avail = torch.ones(b, 6, dtype=torch.bool, device=lead.device)
    picks = []
    for scores, k in ((lead, 2), (back, 2)):
        for _ in range(k):
            probs = torch.softmax(scores.masked_fill(~avail, float("-inf")), -1)
            p = torch.multinomial(probs, 1, generator=generator).squeeze(1)
            picks.append(p)
            avail = avail & ~_hot(p)
    bring = torch.stack(picks, 1)
    return bring, bring_logp(lead, back, bring)


def bring_logp(lead, back, bring):

    b = lead.shape[0]
    all6 = torch.ones(b, 6, dtype=torch.bool, device=lead.device)
    lp_lead = _pl_logp(lead, bring[:, :2], all6)
    rest = all6.clone()
    rest = rest & ~(_hot(bring[:, 0]) | _hot(bring[:, 1]))
    return lp_lead + _pl_logp(back, bring[:, 2:], rest)


def _outcome_table():


    seqs, ids, keys = [], [], {}
    for p in itertools.permutations(range(6), 4):
        seqs.append(p)
        ids.append(keys.setdefault((frozenset(p[:2]), frozenset(p[2:])), len(keys)))
    return torch.tensor(seqs), torch.tensor(ids), len(keys)


_SEQS, _OUTCOME_IDS, N_OUTCOMES = _outcome_table()


def outcome_probs(lead, back):


    b, dev = lead.shape[0], lead.device
    seqs = _SEQS.to(dev).repeat(b, 1)
    p = bring_logp(lead.repeat_interleave(len(_SEQS), 0), back.repeat_interleave(len(_SEQS), 0), seqs).exp().view(b, -1)
    return torch.zeros(b, N_OUTCOMES, device=dev).index_add_(1, _OUTCOME_IDS.to(dev), p)


@torch.inference_mode()
def preview_report(net, x, prev=None):



    lead, back, _ = net(x)
    p = outcome_probs(lead.float(), back.float())
    stats = {"pv_entropy": round(float(-(p * p.clamp_min(1e-12).log()).sum(-1).mean()), 3), "pv_top": round(float(p.max(-1).values.mean()), 3)}
    if prev is not None:
        stats["pv_drift_tv"] = round(float(0.5 * (p - prev).abs().sum(-1).mean()), 3)
        stats["pv_same_top"] = round(float((p.argmax(-1) == prev.argmax(-1)).float().mean()), 3)
    return stats, p


def bring_entropy_proxy(lead, back):


    def ent(s):
        lp = torch.log_softmax(s, -1)
        return -(lp.exp() * lp).sum(-1)

    return ent(lead) + ent(back)

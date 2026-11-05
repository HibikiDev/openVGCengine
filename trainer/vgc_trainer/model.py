























from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import torch
import torch.nn as nn
import vgc_engine as ve


ACTIVE_A, ACTIVE_B, IS_MINE, PP = 2, 3, 0, 45

TERA_TYPE = 9
MODEL_VERSION = 3


def _masked_log_softmax(logits, allowed):

    masked = logits.float().masked_fill(~allowed, float("-inf"))
    masked = torch.where(allowed.any(-1, keepdim=True), masked, torch.zeros_like(masked))
    return torch.log_softmax(masked, -1)


_SWITCH: dict = {}


def _switch_actions(dev) -> torch.Tensor:


    key = str(dev)
    if key not in _SWITCH:
        with torch.inference_mode(False):
            switch = torch.zeros(ve.SLOT_ACTIONS, dtype=torch.bool, device=dev)
            switch[ve.SWITCH_BASE : ve.PASS_ACTION] = True
        _SWITCH[key] = switch
    return _SWITCH[key]


def _draw(logits, allowed, generator, temperature: float):

    if temperature == 0:
        return _masked_log_softmax(logits, allowed).argmax(-1)
    lp = _masked_log_softmax(logits.float() / temperature, allowed)
    return torch.multinomial(lp.exp(), 1, generator=generator).squeeze(-1)


def _draw_mega(mega_logits, ok, generator, temperature: float):
    p = torch.sigmoid(mega_logits.float() / max(temperature, 1e-6))
    if temperature == 0:
        return (p > 0.5) & ok
    return (torch.rand(p.shape, device=p.device, generator=generator) < p) & ok


def narrow_slot_b(bits_b, a0, min_switches):



    switch = _switch_actions(bits_b.device)
    a0 = a0.long()
    a0_switch = switch[a0]
    same_mon = nn.functional.one_hot(a0, bits_b.shape[-1]).bool() & a0_switch[:, None]
    mask1 = bits_b & ~same_mon
    need = min_switches.long() - a0_switch.long()
    force = (need >= 1) & (mask1 & switch).any(-1)
    return torch.where(force[:, None], mask1 & switch, mask1)





GIMMICK_FREE, GIMMICK_FORCED = 1, 2


def gimmick_codes(mega_allowed):


    if mega_allowed.dim() == 3:
        return mega_allowed
    is_move = torch.arange(ve.SLOT_ACTIONS, device=mega_allowed.device) < ve.SWITCH_BASE
    return ((mega_allowed[:, :, None] & is_move).to(torch.int8) * (4 + GIMMICK_FREE)).to(torch.int8)


def _forced(codes_s):

    return (codes_s & 3) == GIMMICK_FORCED


def _gimmick_at(codes_s, a):

    c = codes_s.gather(1, a.long()[:, None]).squeeze(1).long()
    return (c & 3) == GIMMICK_FREE, (c & 3) == GIMMICK_FORCED, c >> 2


def slot_a_mask(bits_a, codes):

    return bits_a | _forced(codes[:, 0])


def slot_a_gimmick(codes, a0):

    ok0, f0, _ = _gimmick_at(codes[:, 0], a0)
    return ok0, f0


def slot_b_mask(bits_b, codes, a0, mega0, min_switches):


    _, _, k0 = _gimmick_at(codes[:, 0], a0)
    k1 = (codes[:, 1].long() >> 2).amax(-1)
    same = mega0.bool() & (k0 == k1) & (k0 > 0)
    f1 = _forced(codes[:, 1])
    return narrow_slot_b(bits_b | (f1 & ~same[:, None]), a0, min_switches), same


def slot_b_gimmick(codes, a1, same):

    ok1, f1, _ = _gimmick_at(codes[:, 1], a1)
    return ok1 & ~same, f1 & ~same


def joint_mega_ok(codes, actions, bits1, min_switches):

    a = actions.long()
    a0, a1 = a[:, 0, 0], a[:, 1, 0]
    ok0, _ = slot_a_gimmick(codes, a0)
    mask1, same = slot_b_mask(bits1, codes, a0, a[:, 0, 1] == 1, min_switches)
    ok1, _ = slot_b_gimmick(codes, a1, same)
    return mask1, torch.stack([ok0, ok1], 1)


def log_prob(action_logits, mega_logits, actions, mask0, mask1, mega_ok):



    a = actions.long()
    lp0 = _masked_log_softmax(action_logits[:, 0], mask0)
    lp1 = _masked_log_softmax(action_logits[:, 1], mask1)
    logp = lp0.gather(1, a[:, 0, :1]).squeeze(1) + lp1.gather(1, a[:, 1, :1]).squeeze(1)

    def ent(lp, mask):
        return -(lp.exp() * torch.where(mask, lp, torch.zeros_like(lp))).sum(-1)

    entropy = ent(lp0, mask0) + ent(lp1, mask1)
    m = mega_logits.float()
    ok = mega_ok.float()
    mega_lp = torch.where(a[:, :, 1] == 1, nn.functional.logsigmoid(m), nn.functional.logsigmoid(-m))
    logp = logp + (mega_lp * ok).sum(-1)
    pm = torch.sigmoid(m)
    mega_ent = -(pm * nn.functional.logsigmoid(m) + (1 - pm) * nn.functional.logsigmoid(-m))
    entropy = entropy + (mega_ent * ok).sum(-1)
    return logp, entropy


def _pack(a0, mega0, a1, mega1):
    return torch.stack([torch.stack([a0, mega0.long()], -1), torch.stack([a1, mega1.long()], -1)], 1).int()


def _gather_tokens(x, idx):

    return x.gather(1, idx.long().unsqueeze(-1).expand(-1, -1, x.shape[-1]))


def _active(features):

    flags = torch.stack([features[..., ACTIVE_A], features[..., ACTIVE_B]], 1)
    best, idx = flags.max(-1)
    return idx, best > 0.5



@dataclass
class _State:
    ctx: torch.Tensor
    move_h: torch.Tensor
    tgt_h: torch.Tensor
    bench_h: torch.Tensor
    summary: torch.Tensor
    foe_active: torch.Tensor
    value: torch.Tensor
    foe_moves: torch.Tensor
    my_active: torch.Tensor


class PolicyNet(nn.Module):



    version = MODEL_VERSION

    def __init__(self, d: int = 256, layers: int = 4, heads: int = 4, aux_head: str = "slot"):
        super().__init__()
        if aux_head not in ("slot", "pointer"):
            raise ValueError(f"aux_head {aux_head!r}")
        self.aux_head = aux_head
        self.aux_detach = False
        move_dex, species_dex = ve.dex_tables()
        self.register_buffer("move_dex", torch.from_numpy(move_dex), persistent=False)
        self.register_buffer("species_dex", torch.from_numpy(species_dex), persistent=False)
        self.species = nn.Embedding(ve.SPECIES_VOCAB, d)
        self.species_feat = nn.Linear(species_dex.shape[1], d)
        self.item = nn.Embedding(ve.ITEM_VOCAB, d)
        self.ability = nn.Embedding(ve.ABILITY_VOCAB, d)
        self.move = nn.Embedding(ve.MOVE_VOCAB, d)
        self.move_feat = nn.Linear(move_dex.shape[1], d)
        self.type_emb = nn.Embedding(ve.TYPE_VOCAB, d)
        self.mon_feat = nn.Linear(ve.MON_FEATURES, d)
        self.field = nn.Linear(ve.FIELD_FEATURES, d)
        self.event_kind = nn.Embedding(16, d)
        self.event_actor = nn.Embedding(ve.MON_TOKENS + 1, d)
        self.event_outcome = nn.Embedding(8, d)
        self.token_type = nn.Embedding(3, d)
        self.mon_pos = nn.Embedding(ve.MON_TOKENS, d)
        self.hist_pos = nn.Embedding(ve.HISTORY_LEN, d)
        layer = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=0.0, batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d)
        self.slot_embed = nn.Embedding(2, d)
        self.ctx = nn.Sequential(nn.Linear(2 * d, d), nn.GELU(), nn.Linear(d, d))

        self.head_ctx = nn.Linear(d, d)
        self.head_move = nn.Linear(d, d)
        self.pp_feat = nn.Linear(1, d, bias=False)
        self.head_target = nn.Linear(d, d)
        self.target_type = nn.Embedding(4, d)
        self.move_out = nn.Sequential(nn.GELU(), nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))

        self.sw_ctx = nn.Linear(d, d)
        self.sw_mon = nn.Linear(d, d)
        self.sw_out = nn.Sequential(nn.GELU(), nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))
        self.misc = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 2))

        self.act_emb = nn.Embedding(ve.SLOT_ACTIONS, d)
        self.mega_emb = nn.Embedding(2, d)
        self.cond = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, d))
        self.value = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))
        self.aux = nn.Sequential(nn.Linear(2 * d, d), nn.GELU(), nn.Linear(d, ve.SLOT_ACTIONS))
        if aux_head == "pointer":


            self.auxp_ctx = nn.Sequential(nn.Linear(2 * d, d), nn.GELU(), nn.Linear(d, d))
            self.auxp_move = nn.Linear(d, d)
            self.auxp_tgt = nn.Linear(d, d)
            self.auxp_tgt_type = nn.Embedding(4, d)
            self.auxp_out = nn.Sequential(nn.GELU(), nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))
            self.auxp_misc = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, ve.SLOT_ACTIONS - ve.SWITCH_BASE))



        self.gimmick_move = nn.Linear(d, 1)
        nn.init.zeros_(self.gimmick_move.weight)
        nn.init.zeros_(self.gimmick_move.bias)



        self.tera_emb = nn.Embedding(ve.TYPE_VOCAB, d, padding_idx=0)
        nn.init.zeros_(self.tera_emb.weight)

    def move_vec(self, ids):
        ids = ids.clamp(0, ve.MOVE_VOCAB - 1)
        return self.move(ids) + self.move_feat(self.move_dex[ids])

    def encode(self, field, mon_ids, mon_features, history, bring) -> _State:
        ids = mon_ids.long()
        mv = self.move_vec(ids[..., 3:7])
        mons = (
            self.species(ids[..., 0])
            + self.species_feat(self.species_dex[ids[..., 0]])
            + self.item(ids[..., 1])
            + self.ability(ids[..., 2])
            + mv.sum(-2)
            + self.type_emb(ids[..., 7:9]).sum(-2)
            + self.mon_feat(mon_features)
            + self.mon_pos.weight
            + self.token_type.weight[1]
        )
        if ids.shape[-1] > TERA_TYPE:
            mons = mons + self.tera_emb(ids[..., TERA_TYPE])
        h = history.long()
        events = (
            self.event_kind(h[..., 0].clamp(0, 15))
            + self.event_actor(h[..., 1] + 1)
            + self.event_actor(h[..., 2] + 1)
            + self.move_vec(h[..., 3])
            + self.event_outcome(h[..., 4].clamp(-1, 6) + 1)
            + self.hist_pos.weight
            + self.token_type.weight[2]
        )
        f = (self.field(field) + self.token_type.weight[0]).unsqueeze(1)
        x = self.norm(self.encoder(torch.cat([f, mons, events], dim=1)))
        summary = x[:, 0]
        mon_x = x[:, 1 : 1 + ve.MON_TOKENS]
        r = ve.ROSTER_SIZE
        my_idx, my_ok = _active(mon_features[:, :r])
        foe_idx, foe_ok = _active(mon_features[:, r:])
        my_act = _gather_tokens(mon_x, my_idx)
        foe_act = _gather_tokens(mon_x, foe_idx + r) * foe_ok.unsqueeze(-1).to(mon_x.dtype)
        ctx = self.ctx(torch.cat([my_act + self.slot_embed.weight, summary.unsqueeze(1).expand(-1, 2, -1)], -1))

        b = field.shape[0]
        rows = torch.arange(b, device=field.device).unsqueeze(1)
        my_moves = mv[rows, my_idx]
        pp = mon_features[rows, my_idx][..., PP : PP + 4].unsqueeze(-1)
        move_h = self.head_move(my_moves) + self.pp_feat(pp.to(my_moves.dtype))
        ally = my_act.flip(1) * my_ok.flip(1).unsqueeze(-1).to(my_act.dtype)
        targets = torch.stack([foe_act[:, :1].expand(-1, 2, -1), foe_act[:, 1:].expand(-1, 2, -1), ally, my_act], 2)
        tgt_h = self.head_target(targets + self.target_type.weight)
        bench_h = self.sw_mon(_gather_tokens(mon_x, bring))
        foe_moves = mv[rows, foe_idx + r]
        my_seen = my_act * my_ok.unsqueeze(-1).to(my_act.dtype)
        return _State(ctx, move_h, tgt_h, bench_h, summary, foe_act, self.value(summary).squeeze(-1), foe_moves, my_seen)

    def aux_logits(self, st: _State) -> torch.Tensor:


        if self.aux_head == "slot":
            return self.aux(torch.cat([st.foe_active, st.summary.unsqueeze(1).expand(-1, 2, -1)], -1))
        b = st.summary.shape[0]
        se = self.slot_embed.weight.detach() if self.aux_detach else self.slot_embed.weight
        c = self.auxp_ctx(torch.cat([st.foe_active + se, st.summary.unsqueeze(1).expand(-1, 2, -1)], -1))

        tg = torch.stack([st.my_active[:, :1].expand(-1, 2, -1), st.my_active[:, 1:].expand(-1, 2, -1), st.foe_active.flip(1),
                          st.foe_active], 2)
        hm = (c[:, :, None, None] + self.auxp_move(st.foe_moves)[:, :, :, None]
              + self.auxp_tgt(tg + self.auxp_tgt_type.weight)[:, :, None, :])
        moves = self.auxp_out(hm).reshape(b, 2, 16)
        return torch.cat([moves, self.auxp_misc(c)], -1)

    def slot_logits(self, st: _State, s: int, cond=None):

        c = st.ctx[:, s] if cond is None else st.ctx[:, s] + cond
        b = c.shape[0]
        hm = self.head_ctx(c)[:, None, None] + st.move_h[:, s, :, None] + st.tgt_h[:, s, None, :]
        move_logits = self.move_out(hm).reshape(b, 16)
        sw_logits = self.sw_out(self.sw_ctx(c)[:, None] + st.bench_h).squeeze(-1)
        misc = self.misc(c)
        return torch.cat([move_logits, sw_logits, misc[:, :1]], -1), misc[:, 1]

    def gimmick_logit(self, st: _State, s: int, a, mg):

        a = a.long()
        rows = torch.arange(a.shape[0], device=a.device)
        h = st.move_h[rows, s, (a // 4).clamp(max=3)] + self.act_emb(a)
        term = self.gimmick_move(h).squeeze(-1)
        return mg + torch.where(a < ve.SWITCH_BASE, term, torch.zeros_like(term))

    def condition(self, st: _State, a0, mega0):

        a0 = a0.long()
        rows = torch.arange(a0.shape[0], device=a0.device)
        e = self.act_emb(a0) + self.mega_emb(mega0.long())
        is_move = (a0 < ve.SWITCH_BASE).unsqueeze(-1).to(e.dtype)
        m, t = (a0 // 4).clamp(max=3), a0 % 4
        e = e + is_move * (st.move_h[rows, 0, m] + st.tgt_h[rows, 0, t])
        is_switch = ((a0 >= ve.SWITCH_BASE) & (a0 < ve.PASS_ACTION)).unsqueeze(-1).to(e.dtype)
        e = e + is_switch * st.bench_h[rows, (a0 - ve.SWITCH_BASE).clamp(0, 3)]
        return self.cond(e)

    def forward(self, field, mon_ids, mon_features, history, bring, actions):


        st = self.encode(field, mon_ids, mon_features, history, bring)
        l0, m0 = self.slot_logits(st, 0)
        l1, m1 = self.slot_logits(st, 1, self.condition(st, actions[:, 0, 0], actions[:, 0, 1]))
        m0, m1 = self.gimmick_logit(st, 0, actions[:, 0, 0], m0), self.gimmick_logit(st, 1, actions[:, 1, 0], m1)

        aux = self.aux_logits(dataclasses.replace(st, summary=st.summary.detach(), foe_active=st.foe_active.detach(),
                                                  foe_moves=st.foe_moves.detach(), my_active=st.my_active.detach())
                              if self.aux_detach else st)
        return torch.stack([l0, l1], 1), torch.stack([m0, m1], 1), st.value, aux

    def act(self, inputs, bits, mega_allowed, min_switches, generator=None, temperature: float = 1.0, repeat: int = 1):







        st = self.encode(*inputs)
        if repeat > 1:
            st = _State(*(getattr(st, f.name).repeat_interleave(repeat, 0) for f in dataclasses.fields(st)))
        codes = gimmick_codes(mega_allowed)
        l0, mg0 = self.slot_logits(st, 0)
        mask0 = slot_a_mask(bits[:, 0], codes)
        a0 = _draw(l0, mask0, generator, temperature)
        ok0, f0 = slot_a_gimmick(codes, a0)
        mg0 = self.gimmick_logit(st, 0, a0, mg0)
        mega0 = _draw_mega(mg0, ok0, generator, temperature) | f0
        mask1, same = slot_b_mask(bits[:, 1], codes, a0, mega0, min_switches)
        l1, mg1 = self.slot_logits(st, 1, self.condition(st, a0, mega0))
        a1 = _draw(l1, mask1, generator, temperature)
        ok1, f1 = slot_b_gimmick(codes, a1, same)
        mg1 = self.gimmick_logit(st, 1, a1, mg1)
        mega1 = _draw_mega(mg1, ok1, generator, temperature) | f1
        actions = _pack(a0, mega0, a1, mega1)
        mega_ok = torch.stack([ok0, ok1], 1)
        logp, _ = log_prob(torch.stack([l0, l1], 1), torch.stack([mg0, mg1], 1), actions, mask0, mask1, mega_ok)
        return {"actions": actions, "mask0": mask0, "mask1": mask1, "mega_ok": mega_ok, "logp": logp, "value": st.value.float(),
                "logits": torch.stack([l0, l1], 1), "mega_logits": torch.stack([mg0, mg1], 1)}

    def values(self, field, mon_ids, mon_features, history, bring):
        return self.encode(field, mon_ids, mon_features, history, bring).value

    def opponent_logits(self, field, mon_ids, mon_features, history, bring):

        return self.aux_logits(self.encode(field, mon_ids, mon_features, history, bring))



class PolicyNetV2(nn.Module):



    version = 2

    def __init__(self, d: int = 256, layers: int = 4, heads: int = 4):
        super().__init__()
        self.species = nn.Embedding(ve.SPECIES_VOCAB, d)
        self.item = nn.Embedding(ve.ITEM_VOCAB, d)
        self.ability = nn.Embedding(ve.ABILITY_VOCAB, d)
        self.move = nn.Embedding(ve.MOVE_VOCAB, d)
        self.type_emb = nn.Embedding(ve.TYPE_VOCAB, d)
        self.mon_feat = nn.Linear(ve.MON_FEATURES, d)
        self.field = nn.Linear(ve.FIELD_FEATURES, d)
        self.event_kind = nn.Embedding(16, d)
        self.event_actor = nn.Embedding(ve.MON_TOKENS + 1, d)
        self.event_outcome = nn.Embedding(8, d)
        self.token_type = nn.Embedding(3, d)
        self.mon_pos = nn.Embedding(ve.MON_TOKENS, d)
        self.hist_pos = nn.Embedding(ve.HISTORY_LEN, d)
        layer = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=0.0, batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d)
        self.slot_embed = nn.Embedding(2, d)
        self.policy = nn.Sequential(nn.Linear(2 * d, d), nn.GELU(), nn.Linear(d, ve.SLOT_ACTIONS + 1))
        self.value = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))

    def forward(self, field, mon_ids, mon_features, history, bring=None):

        ids = mon_ids.long()
        mons = (
            self.species(ids[..., 0])
            + self.item(ids[..., 1])
            + self.ability(ids[..., 2])
            + self.move(ids[..., 3:7]).sum(-2)
            + self.type_emb(ids[..., 7:9]).sum(-2)
            + self.mon_feat(mon_features)
            + self.mon_pos.weight
            + self.token_type.weight[1]
        )
        h = history.long()
        events = (
            self.event_kind(h[..., 0].clamp(0, 15))
            + self.event_actor(h[..., 1] + 1)
            + self.event_actor(h[..., 2] + 1)
            + self.move(h[..., 3].clamp(0, ve.MOVE_VOCAB - 1))
            + self.event_outcome(h[..., 4].clamp(-1, 6) + 1)
            + self.hist_pos.weight
            + self.token_type.weight[2]
        )
        f = (self.field(field) + self.token_type.weight[0]).unsqueeze(1)
        x = self.norm(self.encoder(torch.cat([f, mons, events], dim=1)))
        summary = x[:, 0]
        mon_x = x[:, 1 : 1 + ve.MON_TOKENS]
        mine = mon_features[:, : ve.ROSTER_SIZE]
        idx = torch.stack([mine[..., ACTIVE_A].argmax(-1), mine[..., ACTIVE_B].argmax(-1)], dim=1)
        active = mon_x.gather(1, idx.unsqueeze(-1).expand(-1, -1, mon_x.shape[-1]))
        slot = active + self.slot_embed.weight.unsqueeze(0)
        out = self.policy(torch.cat([slot, summary.unsqueeze(1).expand(-1, 2, -1)], dim=-1))
        return out[..., : ve.SLOT_ACTIONS], out[..., ve.SLOT_ACTIONS], self.value(summary).squeeze(-1)

    def act(self, inputs, bits, mega_allowed, min_switches, generator=None, temperature: float = 1.0, repeat: int = 1):
        logits, mega_logits, value = (t.repeat_interleave(repeat, 0) for t in self(*inputs))
        return sample_independent(logits, mega_logits, value, bits, mega_allowed, min_switches, generator, temperature)

    def values(self, field, mon_ids, mon_features, history, bring=None):
        return self(field, mon_ids, mon_features, history)[2]


def sample_independent(logits, mega_logits, value, bits, mega_allowed, min_switches, generator=None, temperature: float = 1.0):


    codes = gimmick_codes(mega_allowed)
    mask0 = slot_a_mask(bits[:, 0], codes)
    a0 = _draw(logits[:, 0], mask0, generator, temperature)


    ok0, f0 = slot_a_gimmick(codes, a0)
    could = ok0 | f0
    mask1, same = slot_b_mask(bits[:, 1], codes, a0, could, min_switches)
    a1 = _draw(logits[:, 1], mask1, generator, temperature)
    mega0 = _draw_mega(mega_logits[:, 0], ok0, generator, temperature) | f0
    _, _, k0 = _gimmick_at(codes[:, 0], a0)
    same = mega0 & (k0 == (codes[:, 1].long() >> 2).amax(-1)) & (k0 > 0)
    ok1, f1 = slot_b_gimmick(codes, a1, same)
    mega1 = _draw_mega(mega_logits[:, 1], ok1, generator, temperature) | f1
    actions = _pack(a0, mega0, a1, mega1)
    mega_ok = torch.stack([ok0, ok1], 1)
    logp, _ = log_prob(logits, mega_logits, actions, mask0, mask1, mega_ok)
    return {"actions": actions, "mask0": mask0, "mask1": mask1, "mega_ok": mega_ok, "logp": logp, "value": value.float(),
            "logits": logits, "mega_logits": mega_logits}


def build_policy(meta: dict) -> nn.Module:

    if meta.get("model_version", 2) == MODEL_VERSION:
        return PolicyNet(d=meta.get("d", 256), layers=meta.get("layers", 4), aux_head=(meta.get("cfg") or {}).get("aux_head", "slot"))
    return PolicyNetV2(d=meta.get("d", 256), layers=meta.get("layers", 4))



VOCAB_TABLES = frozenset({"species.weight", "item.weight", "ability.weight", "move.weight"})


INPUT_GROWN = frozenset({"field.weight", "mon_feat.weight"})






OBS_CARRIES_OVER = frozenset({(2, 3), (3, 4), (2, 4), (4, 5), (3, 5), (2, 5), (5, 6), (4, 6), (3, 6), (2, 6)})


def obs_compatible(obs_version, current: int) -> bool:

    return obs_version is None or obs_version == current or (obs_version, current) in OBS_CARRIES_OVER





OPTIONAL_PREFIXES = ("auxp_", "gimmick_move.", "tera_emb.")


def load_weights(module: nn.Module, state: dict) -> list[str]:




    own = module.state_dict()
    state = dict(state)
    grown = []
    for k, v in state.items():
        o = own.get(k)
        if (o is not None and k in VOCAB_TABLES and v.shape != o.shape and v.dim() == o.dim() == 2 and v.shape[1] == o.shape[1]
                and v.shape[0] < o.shape[0]):
            t = o.clone()
            t[: v.shape[0]] = v.to(t.dtype)
            state[k] = t
            grown.append(k)
        elif (o is not None and k in INPUT_GROWN and v.shape != o.shape and v.dim() == o.dim() == 2 and v.shape[0] == o.shape[0]
                and v.shape[1] < o.shape[1]):
            t = torch.zeros_like(o)
            t[:, : v.shape[1]] = v.to(t.dtype)
            state[k] = t
            grown.append(k)
    missing = [k for k in module.state_dict() if k not in state]
    if missing and all(k.startswith(OPTIONAL_PREFIXES) for k in missing):
        module.load_state_dict(state, strict=False)
        grown += missing
    else:
        module.load_state_dict(state)
    return grown


def pad_optimizer_state(module: nn.Module, opt_state: dict, grown: list[str]) -> dict:



    opt_state = {"state": dict(opt_state["state"]), "param_groups": opt_state["param_groups"]}
    n_params = len(list(module.parameters()))
    groups = opt_state["param_groups"]
    if len(groups) == 1 and len(groups[0]["params"]) < n_params:

        opt_state["param_groups"] = [dict(groups[0], params=list(range(n_params)))]
    for i, (name, p) in enumerate(module.named_parameters()):
        st = opt_state["state"].get(i)
        if name not in grown or st is None:
            continue
        st = dict(st)
        for k in ("exp_avg", "exp_avg_sq"):
            old = st[k]
            if old.shape != p.shape:
                new = torch.zeros(p.shape, dtype=old.dtype, device=old.device)
                new[tuple(slice(0, s) for s in old.shape)] = old
                st[k] = new
        opt_state["state"][i] = st
    return opt_state


def load_policy(ck: dict, dev: torch.device, raw: bool = False) -> nn.Module:



    from .canonical import CanonicalPolicy, is_canonical

    net = build_policy(ck.get("meta", {})).to(dev).eval()
    load_weights(net, ck["model"])
    return CanonicalPolicy(net, True).eval() if is_canonical(ck.get("meta")) and not raw else net

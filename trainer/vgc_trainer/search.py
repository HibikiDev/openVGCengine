



















from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import torch
import vgc_engine as ve

from .amp import amp
from .canonical import Framed
from .env import Masks, Observation, VecEnv, load_teams, potential, read_masks
from .model import sample_independent
from .preview import _OUTCOME_IDS, _SEQS, N_OUTCOMES, outcome_probs


STATS = ("hp", "atk", "def", "spa", "spd", "spe")
PROTECT_MOVES = {ve.lookup("move", n) for n in ("Protect", "Detect", "Spiky Shield", "King's Shield", "Baneful Bunker", "Silk Trap",
                                                "Burning Bulwark", "Obstruct")} - {0}
FALLBACK_SPREAD = ("Hardy", (22, 11, 0, 11, 0, 22))


def _spread(s: dict) -> tuple[str, tuple[int, ...]]:
    evs = s.get("evs") or {}
    return (s.get("nature") or "Hardy", tuple(int(evs.get(k, 0) or 0) for k in STATS))


def guessed_spreads(teams: list[list[dict]], corpus: list[list[dict]]) -> list[list[tuple[str, tuple[int, ...]]]]:



    by_species: dict[str, Counter] = defaultdict(Counter)
    by_nature: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for t in corpus:
        for st in t:
            by_species[st["species"]][_spread(st)] += 1
            by_nature[st["species"], _spread(st)[0]][_spread(st)] += 1

    def most_common(c: Counter, own: tuple) -> tuple | None:
        c = c.copy()
        c[own] -= 1
        c = +c
        return c.most_common(1)[0][0] if c else None

    out = []
    for t in teams:
        row = []
        for st in t:
            own, nature = _spread(st), st.get("nature")
            guess = most_common(by_nature[st["species"], nature], own) if nature else None
            if guess is None:
                guess = most_common(by_species[st["species"]], own) or FALLBACK_SPREAD
                if nature:
                    guess = (nature, guess[1])
            row.append(guess)
        row += [FALLBACK_SPREAD] * (6 - len(row))
        out.append(row)
    return out


def gimmick_bit(code: int, wanted: int) -> int:


    state = int(code) & 3
    return 1 if state == 2 else (int(wanted) if state == 1 else 0)


def gimmicks_compatible(codes: np.ndarray, v: np.ndarray) -> bool:

    if not (v[0, 1] and v[1, 1]):
        return True
    return int(codes[0, v[0, 0]]) >> 2 != int(codes[1, v[1, 0]]) >> 2


class OneStepSearch:
    def __init__(self, model: torch.nn.Module, env: VecEnv, dev: torch.device, k: int = 8, m: int = 8, samples: int = 32,
                 shaping: float = 0.5, seed: int = 0, chunk: int = 4096, replies: str = "self", max_roots: int | None = None,
                 spreads: str = "true", score: str = "both", crn: bool = True, finish_switch: bool = True, hidden: str = "true",
                 preview: torch.nn.Module | None = None, greedy_column: bool = False, cand_temp: float = 1.0,
                 protect_variants: bool = False, inject_protect: bool = False, seeds: int = 1, reply_mode: str = "sample",
                 robust: float = 0.0, top_draws: int = 64, opp_head: torch.nn.Module | None = None, depth2: int = 0,
                 depth2_mix: float = 0.0, reply_policy: torch.nn.Module | None = None, rollout_fix: bool = False,
                 rollout_len: int = 1, br_column: bool = False, br_top: int = 3, br_weight: float | None = None,
                 br_max_cols: int = 96, rollout_dedupe: str = "off", rollout_trigger: float | None = None,
                 slot_variants: int = 0):




















































        self.model, self.env, self.dev, self.replies = model, env, dev, replies
        self.score_mode, self.crn, self.finish_switch = score, crn, finish_switch
        self.k, self.m, self.samples, self.shaping, self.chunk = k, m, samples, shaping, chunk
        if seeds < 1 or reply_mode not in ("sample", "top") or not 0.0 <= robust <= 1.0:
            raise ValueError(f"bad search options: seeds={seeds}, reply_mode={reply_mode}, robust={robust}")
        self.seeds, self.reply_mode, self.robust, self.top_draws = seeds, reply_mode, robust, top_draws
        self.opp_head = opp_head
        self.depth2, self.depth2_mix = depth2, depth2_mix
        self.reply_policy = reply_policy
        if rollout_len < 1 or (rollout_len > 1 and not rollout_fix):
            raise ValueError(f"rollout_len {rollout_len} needs rollout_fix")
        self.rollout_fix, self.rollout_len = rollout_fix, rollout_len
        if rollout_dedupe not in ("off", "equal", "save") or (rollout_dedupe != "off" and not rollout_fix):
            raise ValueError(f"rollout_dedupe {rollout_dedupe!r}: off / equal / save, with rollout_fix")
        self.rollout_dedupe, self.rollout_trigger = rollout_dedupe, rollout_trigger


        self.reply_policy_temp = 1.0
        self._last_trigger = None
        self.br_column, self.br_top, self.br_max_cols = br_column, br_top, br_max_cols
        self.br_weight = 1.0 / m if br_weight is None else br_weight
        if br_column and depth2:
            raise ValueError("br_column scores its column one turn deep: not with depth2 rollouts (yet)")
        self.mb = m * seeds
        self.max_roots = env.n if max_roots is None else max_roots
        self.guesses = guessed_spreads(env.teams, load_teams()) if spreads == "guess" else None
        if hidden == "sample" and preview is None:
            raise ValueError('hidden="sample" needs a preview net')
        self.hidden, self.preview = hidden, preview

        self.greedy_column = greedy_column


        self.cand_temp = cand_temp



        self.protect_variants = protect_variants



        self.k_sampled = self.k
        if inject_protect:
            self.k += 3
        self.inject_protect = inject_protect




        self.slot_variants = slot_variants
        self.k += slot_variants


        self.reply_adjust = None

        self.outcome_seq = np.zeros((N_OUTCOMES, 4), np.int64)
        for seq, o in zip(_SEQS.numpy(), _OUTCOME_IDS.numpy()):
            self.outcome_seq[o] = seq
        self.branches = self.max_roots * self.k * self.mb
        self.scratch = ve.BattlePool(self.branches)
        if depth2:
            self.pool2 = ve.BattlePool(self.branches)
            self.obs2, self.masks2 = Observation.empty(self.branches), Masks.empty(self.branches)
            self.status2 = np.zeros(self.branches, np.int8)
        if br_column:
            self.br_rows = self.max_roots * max(br_top * br_max_cols, self.k) * self.seeds
            self.br_pool = ve.BattlePool(self.br_rows)
            self.br_obs, self.br_status = Observation.empty(self.br_rows), np.zeros(self.br_rows, np.int8)
        self.obs = Observation.empty(self.branches)
        self.foe_obs = Observation.empty(self.branches)
        self.masks = Masks.empty(self.branches)
        self.status = np.zeros(self.branches, np.int8)
        self.rng = np.random.default_rng(seed)
        self.gen = torch.Generator(device=dev)
        self.gen.manual_seed(seed)

    def _rows(self, side: int, idx: np.ndarray, repeat: int):

        o, msk, env = self.env.obs[side], self.env.masks, self.env

        def t(a, r=1):
            return torch.from_numpy(np.repeat(a[idx], r, axis=0)).to(self.dev)

        def tr(a, r=1):
            return torch.from_numpy(np.repeat(a, r, axis=0)).to(self.dev)

        inputs = (t(o.field), t(o.mon_ids), t(o.mon_features), t(o.history), t(env.bring[:, side]))
        return inputs, tr(msk.bits_at(idx, side), repeat), tr(msk.gimmick_codes_at(idx, side), repeat), t(msk.min_switches[:, side], repeat)

    def _sample(self, side: int, idx: np.ndarray, repeat: int, temperature: float = 1.0):


        acts, logps = [], []
        step = max(1, self.chunk // repeat)
        for a in range(0, len(idx), step):
            part = idx[a : a + step]
            inputs, bits, mega, min_sw = self._rows(side, part, repeat)
            with amp(self.dev):
                s = self.model.act(inputs, bits, mega, min_sw, self.gen, temperature=temperature, repeat=repeat)
            acts.append(s["actions"].cpu().numpy().reshape(len(part), repeat, 2, 2))
            logps.append(s["logp"].float().cpu().numpy().reshape(len(part), repeat))
        return np.concatenate(acts), np.concatenate(logps)

    def _opp_logits(self, inputs: list[torch.Tensor]) -> torch.Tensor:



        fr = Framed(self.model, inputs)
        if self.opp_head is None:
            return fr.aux_to_engine(fr.net.opponent_logits(*fr.inputs))

        st = fr.net.encode(*fr.inputs)
        return self.opp_head(torch.cat([st.foe_active, st.summary.unsqueeze(1).expand(-1, 2, -1)], -1))

    def _aux_replies(self, side: int, idx: np.ndarray) -> np.ndarray:

        foe, m = 1 - side, self.m
        inputs, _, _, _ = self._rows(side, idx, 1)
        _, bits, mega, min_sw = self._rows(foe, idx, m)
        with amp(self.dev):
            logits = torch.cat([self._opp_logits([x[a : a + self.chunk] for x in inputs]).float()
                                for a in range(0, len(idx), self.chunk)])
        if self.reply_adjust is not None:
            logits = self.reply_adjust(logits, idx)
        logits = logits.repeat_interleave(m, 0)
        always = torch.full(logits.shape[:2], 20.0, device=self.dev)
        s = sample_independent(logits, always, always[:, 0], bits, mega, min_sw, self.gen)
        return s["actions"].cpu().numpy().reshape(len(idx), m, 2, 2)

    def _aux_top_replies(self, side: int, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:




        foe, m, d = 1 - side, self.m, self.top_draws
        inputs, _, _, _ = self._rows(side, idx, 1)
        _, bits, mega, min_sw = self._rows(foe, idx, d)
        with amp(self.dev):
            logits = torch.cat([self._opp_logits([x[a : a + self.chunk] for x in inputs]).float()
                                for a in range(0, len(idx), self.chunk)])
        if self.reply_adjust is not None:
            logits = self.reply_adjust(logits, idx)
        logits = logits.repeat_interleave(d, 0)
        always = torch.full(logits.shape[:2], 20.0, device=self.dev)
        s = sample_independent(logits, always, always[:, 0], bits, mega, min_sw, self.gen)
        acts = s["actions"].detach().cpu().numpy().reshape(len(idx), d, 2, 2)
        logp = s["logp"].detach().float().cpu().numpy().reshape(len(idx), d)
        keep = m - 1 if self.greedy_column else m
        share = keep / m
        out = np.zeros((len(idx), m, 2, 2), np.int32)
        w = np.zeros((len(idx), m))

        self.last_cover = np.zeros(len(idx))
        for r in range(len(idx)):
            seen: dict[bytes, float] = {}
            for j in np.argsort(-logp[r]):
                key = acts[r, j].tobytes()
                if key not in seen:
                    seen[key] = float(logp[r, j])
                    out[r, len(seen) - 1] = acts[r, j]
                    if len(seen) == keep:
                        break
            n = len(seen)
            lp = np.array(list(seen.values()))
            self.last_cover[r] = float(np.exp(lp).sum())
            p = np.exp(lp - lp.max())
            w[r, :n] = share * p / p.sum()
            out[r, n:keep] = out[r, 0]
            if self.greedy_column:
                w[r, m - 1] = 1.0 / m
        return out, w

    def _policy_replies(self, side: int, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:



        foe, m = 1 - side, self.m
        d = self.top_draws if self.reply_mode == "top" else m
        inputs, bits, mega, min_sw = self._rows(foe, idx, d)
        with amp(self.dev):
            s = self.reply_policy.act(inputs, bits, mega, min_sw, self.gen, self.reply_policy_temp, repeat=d)
        acts = s["actions"].detach().cpu().numpy().reshape(len(idx), d, 2, 2)
        if self.reply_mode != "top":
            return acts, np.full((len(idx), m), 1.0 / m)
        logp = s["logp"].detach().float().cpu().numpy().reshape(len(idx), d)
        keep = m - 1 if self.greedy_column else m
        share = keep / m
        out = np.zeros((len(idx), m, 2, 2), np.int32)
        w = np.zeros((len(idx), m))
        self.last_cover = np.zeros(len(idx))
        for r in range(len(idx)):
            seen: dict[bytes, float] = {}
            for j in np.argsort(-logp[r]):
                key = acts[r, j].tobytes()
                if key not in seen:
                    seen[key] = float(logp[r, j])
                    out[r, len(seen) - 1] = acts[r, j]
                    if len(seen) == keep:
                        break
            n = len(seen)
            lp = np.array(list(seen.values()))
            self.last_cover[r] = float(np.exp(lp).sum())
            p = np.exp((lp - lp.max()) / self.reply_policy_temp)
            w[r, :n] = share * p / p.sum()
            out[r, n:keep] = out[r, 0]
            if self.greedy_column:
                w[r, m - 1] = 1.0 / m
        return out, w

    def _candidates(self, side: int, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:


        acts, logp = self._sample(side, idx, self.samples, self.cand_temp)
        out = np.zeros((len(idx), self.k, 2, 2), np.int32)
        out_logp = np.zeros((len(idx), self.k), np.float32)
        for r in range(len(idx)):
            seen: dict[bytes, float] = {}
            first: dict[bytes, np.ndarray] = {}
            for s in range(self.samples):
                key = acts[r, s].tobytes()
                if key not in seen:
                    seen[key], first[key] = logp[r, s], acts[r, s]
            ranked = sorted(seen, key=lambda key: -seen[key])[: self.k_sampled]
            for i in range(self.k):
                key = ranked[i] if i < len(ranked) else ranked[0]
                out[r, i], out_logp[r, i] = first[key], seen[key]
            if self.protect_variants:
                self._add_protect_variants(side, idx[r], out[r][: self.k_sampled], out_logp[r][: self.k_sampled], len(ranked))
            if self.inject_protect:
                self._inject_protect(side, idx[r], out[r], out_logp[r], len(ranked))
            if self.slot_variants:
                self._add_slot_variants(side, idx[r], out[r], out_logp[r], len(ranked))
        return out, out_logp

    def _add_slot_variants(self, side: int, battle: int, cand: np.ndarray, logp: np.ndarray, distinct: int) -> None:



        n_s = max(min(distinct, self.k_sampled), 1)
        top = cand[0]
        frozen = [s for s in (0, 1) if len({cand[i, s].tobytes() for i in range(n_s)}) == 1]
        if not frozen:
            return
        masks = self.env.masks
        codes = masks.gimmick_codes()[battle, side]
        per_slot = []
        for s in frozen:

            legal = np.flatnonzero(((int(masks.actions[battle, side, s]) | int(masks.forced[battle, side, s])) >> np.arange(ve.SLOT_ACTIONS)) & 1)
            legal = [int(a) for a in legal if a != top[s, 0] and a != ve.PASS_ACTION]
            first, rest, seen = [], [], set()
            for a in legal:
                if a < ve.SWITCH_BASE:
                    (rest if a // 4 in seen else first).append(a)
                    seen.add(a // 4)
            order = first + [a for a in legal if a >= ve.SWITCH_BASE] + rest
            vs = []
            for a in order:
                v = top.copy()
                v[s, 0] = a
                v[s, 1] = gimmick_bit(codes[s, a], top[s, 1])
                if v[0, 0] >= ve.SWITCH_BASE and v[0, 0] == v[1, 0]:
                    continue
                if not gimmicks_compatible(codes, v):
                    continue
                vs.append(v)
            per_slot.append(vs)
        variants = [v for group in zip(*[g + [None] * (max(map(len, per_slot)) - len(g)) for g in per_slot]) for v in group if v is not None]
        keys = {cand[i].tobytes() for i in range(n_s)}
        floor = logp[:n_s].min()
        pos = len(cand) - self.slot_variants
        for v in variants:
            if pos >= len(cand):
                break
            if v.tobytes() in keys:
                continue
            cand[pos], logp[pos] = v, floor
            keys.add(v.tobytes())
            pos += 1

    def _protect_actions(self, side: int, battle: int) -> dict[int, int]:

        o, bits = self.env.obs[side], self.env.masks.actions[battle, side]
        out = {}
        for slot in (0, 1):
            tok = np.flatnonzero(o.mon_features[battle, :6, 2 + slot] > 0.5)
            if len(tok) == 0:
                continue
            for j, mid in enumerate(o.mon_ids[battle, tok[0], 3:7]):
                if int(mid) in PROTECT_MOVES:
                    legal = [a for a in range(4 * j, 4 * j + 4) if (int(bits[slot]) >> a) & 1]
                    if legal:
                        out[slot] = legal[0]
                    break
        return out

    def _inject_protect(self, side: int, battle: int, cand: np.ndarray, logp: np.ndarray, distinct: int) -> None:


        prot = self._protect_actions(side, battle)
        variants = []
        for slot, a in prot.items():
            v = cand[0].copy()
            v[slot] = (a, 0)
            variants.append(v)
        if len(prot) == 2:
            v = cand[0].copy()
            for slot, a in prot.items():
                v[slot] = (a, 0)
            variants.append(v)
        keys = {c.tobytes() for c in cand[: min(distinct, self.k_sampled)]}
        floor = logp[: max(min(distinct, self.k_sampled), 1)].min()
        pos = self.k_sampled
        for v in variants:
            if v.tobytes() in keys or pos >= len(cand):
                continue
            cand[pos], logp[pos] = v, floor
            keys.add(v.tobytes())
            pos += 1

    def _add_protect_variants(self, side: int, battle: int, cand: np.ndarray, logp: np.ndarray, distinct: int) -> None:


        o, bits = self.env.obs[side], self.env.masks.actions[battle, side]
        codes = self.env.masks.gimmick_codes()[battle, side]
        variants = []
        for slot in (0, 1):
            tok = np.flatnonzero(o.mon_features[battle, :6, 2 + slot] > 0.5)
            if len(tok) == 0:
                continue
            moves = o.mon_ids[battle, tok[0], 3:7]
            for j, mid in enumerate(moves):
                if int(mid) not in PROTECT_MOVES:
                    continue
                legal = [a for a in range(4 * j, 4 * j + 4) if (int(bits[slot]) >> a) & 1]
                if legal and cand[0, slot, 0] != legal[0]:
                    v = cand[0].copy()
                    v[slot, 0] = legal[0]
                    v[slot, 1] = gimmick_bit(codes[slot, legal[0]], v[slot, 1])
                    if gimmicks_compatible(codes, v):
                        variants.append(v)
                break
        keys = {c.tobytes() for c in cand[:distinct]}
        pos = len(cand) - 1
        floor = logp[: max(distinct, 1)].min()
        for v in variants:
            if v.tobytes() in keys or pos < 1:
                continue
            cand[pos], logp[pos] = v, floor
            keys.add(v.tobytes())
            pos -= 1

    @torch.inference_mode()
    def choose(self, side: int, actions: np.ndarray, battles: np.ndarray | None = None, pick=None) -> None:



        env = self.env
        live = env.masks.to_move[:, side] & (env.status == -1)
        idx = np.flatnonzero(live if battles is None else live & battles)
        if len(idx) == 0:
            return
        cand, q, _ = self.evaluate(side, idx)
        best = q.argmax(-1) if pick is None else np.array([pick(q[r], cand[r]) for r in range(len(idx))])
        actions[idx, side] = cand[np.arange(len(idx)), best]

    @torch.inference_mode()
    def evaluate(self, side: int, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:


        cands, qs, priors, full, wts, reps = [], [], [], [], [], []
        for a in range(0, len(idx), self.max_roots):
            c, q, pr = self._evaluate(side, idx[a : a + self.max_roots])
            cands.append(c)
            qs.append(q)
            priors.append(pr)
            full.append(self._last_full)
            wts.append(self._last_weights)
            reps.append(self._last_replies)


        self.last_scores = np.concatenate(full)
        self.last_weights = np.concatenate(wts)
        self.last_replies = np.concatenate(reps)
        return np.concatenate(cands), np.concatenate(qs), np.concatenate(priors)

    def _evaluate(self, side: int, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        env, k, m, S = self.env, self.k, self.m, self.seeds
        mb = self.mb
        foe = 1 - side
        cand, prior = self._candidates(side, idx)
        replies = np.zeros((len(idx), m, 2, 2), np.int32)
        weights = np.full((len(idx), m), 1.0 / m)
        foe_moves = env.masks.to_move[idx, foe]
        if foe_moves.any():
            if self.replies == "policy":
                replies[foe_moves], weights[foe_moves] = self._policy_replies(side, idx[foe_moves])
            elif self.replies == "aux" and self.reply_mode == "top":
                replies[foe_moves], weights[foe_moves] = self._aux_top_replies(side, idx[foe_moves])
            elif self.replies == "aux":
                replies[foe_moves] = self._aux_replies(side, idx[foe_moves])
            elif self.replies == "greedy":
                out = np.zeros((env.n, 2, 2), np.int32)
                for j in range(m):
                    env.pool.greedy_actions(foe, int(self.rng.integers(1 << 62)), out)
                    replies[foe_moves, j] = out[idx[foe_moves]]
            else:
                replies[foe_moves] = self._sample(foe, idx[foe_moves], m)[0]
            if self.greedy_column and self.replies != "greedy":
                out = np.zeros((env.n, 2, 2), np.int32)
                env.pool.greedy_actions(foe, int(self.rng.integers(1 << 62)), out)
                replies[foe_moves, -1] = out[idx[foe_moves]]

        dst = (np.arange(len(idx))[:, None] * k * mb + np.arange(k * mb)[None]).reshape(-1)
        src = np.repeat(idx, k * mb)
        self.scratch.drop_battles(list(range(len(idx) * k * mb, self.branches)))
        if self.crn:
            seeds = np.broadcast_to(self.rng.integers(0, 2**63 - 1, size=(len(idx), 1, mb)), (len(idx), k, mb)).reshape(-1)
        else:
            seeds = self.rng.integers(0, 2**63 - 1, size=len(dst))
        self.scratch.copy_from(env.pool, src.tolist(), dst.tolist(), seeds.tolist())
        foe_bring = env.bring[idx, foe]
        swaps, per_root = None, None
        if self.hidden == "sample":
            foe_bring, swaps = self._sample_worlds(foe, idx)
            self.scratch.mask_hidden(env.pool, dst.tolist(), foe, [env.team_ids[t] for t in np.repeat(env.pairs[idx, foe], k * mb)],
                                     [swaps[r] for r in range(len(idx)) for _ in range(k * mb)], True)
        if self.guesses is not None:
            per_root = [[self.guesses[env.pairs[i, foe]][r] for r in foe_bring[n]] for n, i in enumerate(idx)]
            self.scratch.set_spreads(dst.tolist(), foe, [per_root[r] for r in range(len(idx)) for _ in range(k * mb)])
        branch = np.zeros((self.branches, 2, 2, 2), np.int32)
        branch[dst, side] = np.repeat(cand, mb, axis=1).reshape(-1, 2, 2)
        branch[dst, foe] = np.tile(np.repeat(replies, S, axis=1), (1, k, 1, 1)).reshape(-1, 2, 2)
        self.scratch.step(branch)
        self.scratch.status(self.status)
        if self.finish_switch:
            self._finish_foe_switches(side, idx, len(dst))
        o = self.obs
        self.scratch.observe(side, o.field, o.mon_ids, o.mon_features, o.history)
        n_rows = len(dst)
        score = np.zeros(n_rows, np.float32)
        bring = np.repeat(env.bring[idx, side], k * mb, axis=0)
        for a in range(0, n_rows, self.chunk):
            sl = slice(a, min(a + self.chunk, n_rows))
            x = [torch.from_numpy(arr[sl]).to(self.dev) for arr in (o.field, o.mon_ids, o.mon_features, o.history, bring)]
            v = torch.zeros(x[0].shape[0], device=self.dev)
            if self.score_mode in ("both", "value"):
                with amp(self.dev):
                    v = self.model.values(*x).float()
            if self.score_mode == "phi":
                v = v + potential(x[2].float(), self.shaping or 1.0)
            elif self.score_mode == "both" and self.shaping:


                v = v + potential(x[2].float(), self.shaping)
            score[sl] = v.cpu().numpy()
        st = self.status[:n_rows]
        score = np.where(st == side, 1.0, np.where(st == foe, -1.0, np.where(st == 2, 0.0, score)))
        self._last_full1 = None
        if self.depth2:

            self._last_full1 = score.reshape(len(idx), k, m, S).mean(-1)
            trig = None
            if self.rollout_trigger is not None:
                trig = self._close_roots(cand, score.reshape(len(idx), k, m, S).mean(-1), weights)
                self._last_trigger = trig
            if trig is not None and not trig.any():
                pass
            elif self.rollout_fix:
                score = self._rollouts(side, idx, n_rows, score, cand, trig)
            else:
                if trig is not None:
                    raise ValueError("rollout_trigger needs rollout_fix")
                score = self._depth2(side, idx, n_rows, score)
        self._last_full = score.reshape(len(idx), k, m, S).mean(-1)
        self._last_weights = weights
        self._last_replies = replies
        if self.br_column:
            self._add_br_column(side, idx, cand, foe_moves, foe_bring, swaps, per_root)
        weights = self._last_weights
        q = (self._last_full * weights[:, None, :]).sum(-1)
        if self.robust:
            q = (1.0 - self.robust) * q + self.robust * self._last_full.min(-1)
        self._last_q1 = None
        if self._last_full1 is not None and self._last_full1.shape == self._last_full.shape:
            q1 = (self._last_full1 * weights[:, None, :]).sum(-1)
            self._last_q1 = (1.0 - self.robust) * q1 + self.robust * self._last_full1.min(-1) if self.robust else q1
        return cand, q, prior


    def _act_rows(self, pool, obs, masks, rows: np.ndarray, who: int, bring: np.ndarray, model=None) -> np.ndarray:

        model = self.model if model is None else model
        pool.observe(who, obs.field, obs.mon_ids, obs.mon_features, obs.history)
        out = []
        for a in range(0, len(rows), self.chunk):
            r, sl = rows[a : a + self.chunk], slice(a, a + self.chunk)
            x = tuple(torch.from_numpy(arr[r]).to(self.dev) for arr in (obs.field, obs.mon_ids, obs.mon_features, obs.history)) + (
                torch.from_numpy(bring[sl]).to(self.dev),)
            with amp(self.dev):
                s = model.act(x, torch.from_numpy(masks.bits_at(r, who)).to(self.dev), torch.from_numpy(masks.gimmick_codes_at(r, who)).to(self.dev),
                              torch.from_numpy(masks.min_switches[r, who]).to(self.dev), self.gen)
            out.append(s["actions"].cpu().numpy())
        return np.concatenate(out)

    def _reply_rows(self, pool, obs, masks, rows: np.ndarray, side: int, bring: np.ndarray, roots: np.ndarray) -> np.ndarray:

        foe = 1 - side
        pool.observe(side, obs.field, obs.mon_ids, obs.mon_features, obs.history)
        out = []
        for a in range(0, len(rows), self.chunk):
            r, sl = rows[a : a + self.chunk], slice(a, a + self.chunk)
            x = [torch.from_numpy(arr[r]).to(self.dev) for arr in (obs.field, obs.mon_ids, obs.mon_features, obs.history)]
            x.append(torch.from_numpy(bring[sl]).to(self.dev))
            with amp(self.dev):
                logits = self._opp_logits(x).float()
            if self.reply_adjust is not None:
                logits = self.reply_adjust(logits, roots[sl])
            always = torch.full(logits.shape[:2], 20.0, device=self.dev)
            s = sample_independent(logits, always, always[:, 0], torch.from_numpy(masks.bits_at(r, foe)).to(self.dev),
                                   torch.from_numpy(masks.gimmick_codes_at(r, foe)).to(self.dev),
                                   torch.from_numpy(masks.min_switches[r, foe]).to(self.dev), self.gen)
            out.append(s["actions"].cpu().numpy())
        return np.concatenate(out)

    def _resolve_forced(self, pool, obs, masks, status, rows_all: np.ndarray, brings: dict, models: dict | None = None) -> None:


        for _ in range(3):
            pool.status(status)
            read_masks(pool, masks)
            forced = (status[rows_all] == -1) & ((masks.min_switches[rows_all] > 0) & masks.to_move[rows_all]).any(1)
            rows = rows_all[forced]
            if len(rows) == 0:
                return
            branch = np.full((status.shape[0], 2, 2, 2), [ve.PASS_ACTION, 0], np.int32)
            for who in (0, 1):
                need = rows[(masks.min_switches[rows, who] > 0) & masks.to_move[rows, who]]
                if len(need):
                    branch[need, who] = self._act_rows(pool, obs, masks, need, who, brings[who][need], (models or {}).get(who))
            pool.step(branch, rows.tolist())

    def _depth2(self, side: int, idx: np.ndarray, n_rows: int, score: np.ndarray) -> np.ndarray:

        foe, km = 1 - side, self.k * self.mb
        rows_all = np.arange(n_rows)
        roots = idx[rows_all // km]
        brings = {0: self.env.bring[roots, 0], 1: self.env.bring[roots, 1]}
        self._resolve_forced(self.scratch, self.obs, self.masks, self.status, rows_all, brings)
        self.scratch.status(self.status)
        read_masks(self.scratch, self.masks)
        live = rows_all[(self.status[:n_rows] == -1) & self.masks.to_move[:n_rows, side]]
        if len(live) == 0:
            return score

        acc = np.zeros(len(live), np.float32)
        dst = np.arange(len(live))
        b_live = {0: brings[0][live], 1: brings[1][live]}
        for _ in range(self.depth2):
            pool, obs, masks = self.pool2, self.obs2, self.masks2
            pool.drop_battles(list(range(len(live), self.branches)))
            pool.copy_from(self.scratch, live.tolist(), dst.tolist(), self.rng.integers(0, 2**62, size=len(live)).tolist())
            read_masks(pool, masks)
            branch = np.full((self.branches, 2, 2, 2), [ve.PASS_ACTION, 0], np.int32)
            branch[dst, side] = self._act_rows(pool, obs, masks, dst, side, b_live[side])
            movers = dst[masks.to_move[dst, foe]]
            if len(movers):
                branch[movers, foe] = self._reply_rows(pool, obs, masks, movers, side, b_live[side][movers], roots[live][movers])
            pool.step(branch, dst.tolist())
            pool.status(self.status2)
            pool.observe(side, obs.field, obs.mon_ids, obs.mon_features, obs.history)
            v = np.zeros(len(live), np.float32)
            for a in range(0, len(live), self.chunk):
                sl = slice(a, min(a + self.chunk, len(live)))
                x = [torch.from_numpy(arr[sl]).to(self.dev) for arr in (obs.field, obs.mon_ids, obs.mon_features, obs.history)]
                x.append(torch.from_numpy(b_live[side][sl]).to(self.dev))
                with amp(self.dev):
                    v[sl] = self.model.values(*x).float().cpu().numpy()
            st2 = self.status2[: len(live)]
            acc += np.where(st2 == side, 1.0, np.where(st2 == foe, -1.0, np.where(st2 == 2, 0.0, v)))
        out = score.copy()
        out[live] = self.depth2_mix * score[live] + (1 - self.depth2_mix) * acc / self.depth2
        return out

    def _close_roots(self, cand: np.ndarray, full: np.ndarray, weights: np.ndarray) -> np.ndarray:

        q = (full * weights[:, None, :]).sum(-1)
        if self.robust:
            q = (1.0 - self.robust) * q + self.robust * full.min(-1)
        out = np.zeros(len(cand), bool)
        for r in range(len(cand)):
            best: dict[bytes, float] = {}
            for i in range(cand.shape[1]):
                key = cand[r, i].tobytes()
                best[key] = max(best.get(key, -np.inf), float(q[r, i]))
            top = sorted(best.values(), reverse=True)
            out[r] = len(top) > 1 and top[0] - top[1] < self.rollout_trigger
        return out

    def _rollouts(self, side: int, idx: np.ndarray, n_rows: int, score: np.ndarray, cand: np.ndarray | None = None,
                  trig: np.ndarray | None = None) -> np.ndarray:


        foe, km, mb = 1 - side, self.k * self.mb, self.mb
        rows_all = np.arange(n_rows)
        roots = idx[rows_all // km]
        brings = {0: self.env.bring[roots, 0], 1: self.env.bring[roots, 1]}
        foe_model = self.reply_policy if (self.replies == "policy" and self.reply_policy is not None) else None
        models = {foe: foe_model} if foe_model is not None else None
        self._resolve_forced(self.scratch, self.obs, self.masks, self.status, rows_all, brings, models)
        self.scratch.status(self.status)
        live = rows_all[self.status[:n_rows] == -1]
        if trig is not None:
            live = live[trig[live // km]]
        if len(live) == 0:
            return score

        reps, n_roll = None, np.full(len(idx), self.depth2)
        if self.rollout_dedupe != "off":
            first = np.zeros((len(idx), self.k), np.int64)
            for r in range(len(idx)):
                seen: dict[bytes, int] = {}
                for i in range(self.k):
                    first[r, i] = seen.setdefault(cand[r, i].tobytes(), i)
                if len(seen) == 1:
                    n_roll[r] = 0
                elif self.rollout_dedupe == "equal":
                    n_roll[r] = min(3 * self.depth2, max(self.depth2, self.depth2 * self.k // len(seen)))
            live = live[n_roll[live // km] > 0]
            slot = (live % km) // mb
            reps = live - (slot - first[live // km, slot]) * mb
            dup, dup_rep = live[reps != live], reps[reps != live]
            live = live[reps == live]
            if len(live) == 0:
                return score


        root_all = live // km
        rounds = int(n_roll[root_all].max())
        base = self.rng.integers(0, 2**62, size=(len(idx), mb, rounds))
        acc = np.zeros(len(live), np.float32)
        pool, obs, masks, st2 = self.pool2, self.obs2, self.masks2, self.status2
        for n in range(rounds):
            pick = np.flatnonzero(n_roll[root_all] > n)
            rows = live[pick]
            col, root_n = rows % mb, rows // km
            dst = np.arange(len(rows))
            b_live = {0: brings[0][rows], 1: brings[1][rows]}
            pool.drop_battles(list(range(len(rows), self.branches)))
            pool.copy_from(self.scratch, rows.tolist(), dst.tolist(), base[root_n, col, n].tolist())
            alive = dst
            for _ in range(self.rollout_len):
                read_masks(pool, masks)
                branch = np.full((self.branches, 2, 2, 2), [ve.PASS_ACTION, 0], np.int32)
                mine = alive[masks.to_move[alive, side]]
                if len(mine):
                    branch[mine, side] = self._act_rows(pool, obs, masks, mine, side, b_live[side][mine])
                movers = alive[masks.to_move[alive, foe]]
                if len(movers):
                    if foe_model is not None:
                        branch[movers, foe] = self._act_rows(pool, obs, masks, movers, foe, b_live[foe][movers], foe_model)
                    else:
                        branch[movers, foe] = self._reply_rows(pool, obs, masks, movers, side, b_live[side][movers],
                                                               roots[rows][movers])
                pool.step(branch, alive.tolist())
                pool.status(st2)
                alive = alive[st2[alive] == -1]
                if len(alive):
                    self._resolve_forced(pool, obs, masks, st2, alive, b_live, models)
                    pool.status(st2)
                    alive = alive[st2[alive] == -1]
                if len(alive) == 0:
                    break
            pool.status(st2)
            pool.observe(side, obs.field, obs.mon_ids, obs.mon_features, obs.history)
            v = np.zeros(len(rows), np.float32)
            for a in range(0, len(rows), self.chunk):
                sl = slice(a, min(a + self.chunk, len(rows)))
                x = [torch.from_numpy(arr[sl]).to(self.dev) for arr in (obs.field, obs.mon_ids, obs.mon_features, obs.history)]
                x.append(torch.from_numpy(b_live[side][sl]).to(self.dev))
                with amp(self.dev):
                    v[sl] = self.model.values(*x).float().cpu().numpy()
            fin = st2[: len(rows)]
            acc[pick] += np.where(fin == side, 1.0, np.where(fin == foe, -1.0, np.where(fin == 2, 0.0, v)))
        out = score.copy()
        out[live] = self.depth2_mix * score[live] + (1 - self.depth2_mix) * acc / n_roll[root_all].astype(np.float32)
        if reps is not None and len(dup):
            out[dup] = out[dup_rep]
        return out


    def _br_prepare(self, src: np.ndarray, dst: np.ndarray, seeds: np.ndarray, root_of: np.ndarray, idx: np.ndarray, foe: int,
                    swaps, per_root) -> None:

        env = self.env
        self.br_pool.drop_battles(list(range(len(dst), self.br_rows)))
        self.br_pool.copy_from(env.pool, src.tolist(), dst.tolist(), seeds.tolist())
        if swaps is not None:
            self.br_pool.mask_hidden(env.pool, dst.tolist(), foe, [env.team_ids[env.pairs[idx[r], foe]] for r in root_of],
                                     [swaps[r] for r in root_of], True)
        if per_root is not None:
            self.br_pool.set_spreads(dst.tolist(), foe, [per_root[r] for r in root_of])

    def _br_values(self, n_rows: int, side: int, bring: np.ndarray) -> np.ndarray:

        foe = 1 - side
        self.br_pool.status(self.br_status)
        o = self.br_obs
        self.br_pool.observe(side, o.field, o.mon_ids, o.mon_features, o.history)
        score = np.zeros(n_rows, np.float32)
        for a in range(0, n_rows, self.chunk):
            sl = slice(a, min(a + self.chunk, n_rows))
            x = [torch.from_numpy(arr[sl]).to(self.dev) for arr in (o.field, o.mon_ids, o.mon_features, o.history)]
            x.append(torch.from_numpy(bring[sl]).to(self.dev))
            v = torch.zeros(x[0].shape[0], device=self.dev)
            if self.score_mode in ("both", "value"):
                with amp(self.dev):
                    v = self.model.values(*x).float()
            if self.score_mode == "phi":
                v = v + potential(x[2].float(), self.shaping or 1.0)
            elif self.score_mode == "both" and self.shaping:
                v = v + potential(x[2].float(), self.shaping)
            score[sl] = v.cpu().numpy()
        st = self.br_status[:n_rows]
        return np.where(st == side, 1.0, np.where(st == foe, -1.0, np.where(st == 2, 0.0, score)))

    def _br_columns(self, r: int, root: int, foe: int, replies: np.ndarray, weights: np.ndarray) -> list[np.ndarray]:

        masks = self.env.masks
        legal = [np.flatnonzero((int(masks.actions[root, foe, s]) >> np.arange(ve.SLOT_ACTIONS)) & 1) for s in (0, 1)]
        have = {replies[r, j].tobytes() for j in range(replies.shape[1])}
        out: dict[bytes, np.ndarray] = {}
        for b in np.argsort(-weights[r])[:2]:
            base = replies[r, b]
            for s in (0, 1):
                for a in legal[s]:
                    j = base.copy()
                    j[s, 0] = a
                    j[s, 1] = base[s, 1] if a < ve.SWITCH_BASE else 0
                    if j[0, 0] >= ve.SWITCH_BASE and j[0, 0] == j[1, 0] and j[0, 0] != ve.PASS_ACTION:
                        continue
                    if j[0, 1] and j[1, 1]:
                        continue
                    key = j.tobytes()
                    if key not in have and key not in out:
                        out[key] = j
        return list(out.values())[: self.br_max_cols]

    def _add_br_column(self, side: int, idx: np.ndarray, cand: np.ndarray, foe_moves: np.ndarray, foe_bring, swaps, per_root) -> None:

        env, foe, k, S = self.env, 1 - side, cand.shape[1], self.seeds
        full, weights, replies = self._last_full, self._last_weights, self._last_replies
        R, m = full.shape[0], full.shape[2]
        q0 = (full * weights[:, None, :]).sum(-1)
        if self.robust:
            q0 = (1.0 - self.robust) * q0 + self.robust * full.min(-1)
        tops, cols = [], []
        for r in range(R):
            seen, top = set(), []
            for i in np.argsort(-q0[r]):
                key = cand[r, i].tobytes()
                if key not in seen:
                    seen.add(key)
                    top.append(i)
                if len(top) == self.br_top:
                    break
            tops.append(top)
            cols.append(self._br_columns(r, idx[r], foe, replies, weights) if foe_moves[r] else [])

        rows_r, rows_c, rows_i, rows_s = [], [], [], []
        for r in range(R):
            for c in range(len(cols[r])):
                for i in tops[r]:
                    for sd in range(S):
                        rows_r.append(r), rows_c.append(c), rows_i.append(i), rows_s.append(sd)
        new_col = np.zeros((R, k), np.float32)
        found = np.zeros((R, 2, 2), np.int32)
        has = np.zeros(R, bool)
        if rows_r:
            rr, cc, ii, ss = map(np.array, (rows_r, rows_c, rows_i, rows_s))
            n = len(rr)
            seed_tab = self.rng.integers(0, 2**62, size=(R, max(len(c) for c in cols), S))
            self._br_prepare(idx[rr], np.arange(n), seed_tab[rr, cc, ss], rr, idx, foe, swaps, per_root)
            branch = np.zeros((self.br_rows, 2, 2, 2), np.int32)
            branch[:n, side] = cand[rr, ii]
            branch[:n, foe] = np.array([cols[a][b] for a, b in zip(rr, cc)])
            self.br_pool.step(branch, list(range(n)))
            v = self._br_values(n, side, env.bring[idx[rr], side])

            key = rr * 100000 + cc
            uk, inv = np.unique(key, return_inverse=True)
            mean = np.bincount(inv, weights=v) / np.bincount(inv)
            best: dict[int, tuple[float, int]] = {}
            for kk, val in zip(uk, mean):
                r, c = int(kk // 100000), int(kk % 100000)
                if r not in best or val < best[r][0]:
                    best[r] = (float(val), c)

            r2 = np.array(sorted(best))
            rows = [(r, i, sd) for r in r2 for i in range(k) for sd in range(S)]
            rr2, ii2, ss2 = map(np.array, zip(*rows))
            n2 = len(rr2)
            seed2 = self.rng.integers(0, 2**62, size=(R, S))
            self._br_prepare(idx[rr2], np.arange(n2), seed2[rr2, ss2], rr2, idx, foe, swaps, per_root)
            branch = np.zeros((self.br_rows, 2, 2, 2), np.int32)
            branch[:n2, side] = cand[rr2, ii2]
            for r in r2:
                found[r] = cols[r][best[r][1]]
                has[r] = True
            branch[:n2, foe] = found[rr2]
            self.br_pool.step(branch, list(range(n2)))
            v2 = self._br_values(n2, side, env.bring[idx[rr2], side])
            np.add.at(new_col, (rr2, ii2), v2 / S)

        mean_col = (full * weights[:, None, :]).sum(-1)
        new_col = np.where(has[:, None], new_col, mean_col)
        wb = np.where(has, self.br_weight, 0.0)
        self._last_full = np.concatenate([full, new_col[:, :, None]], -1)
        self._last_weights = np.concatenate([weights * (1.0 - wb)[:, None], wb[:, None]], -1)
        self._last_replies = np.concatenate([replies, found[:, None]], 1)
        self.last_br = found
        self.last_br_has = has

    @torch.inference_mode()
    def _sample_worlds(self, foe: int, idx: np.ndarray) -> tuple[np.ndarray, list[list[tuple[int, int]]]]:


        env = self.env
        hidden = env.pool.hidden_bench(idx.tolist(), foe)
        bring = env.bring[idx, foe].copy()
        swaps: list[list[tuple[int, int]]] = [[] for _ in idx]
        need = [n for n in range(len(idx)) if hidden[n]]
        if not need:
            return bring, swaps
        from .batch import preview_inputs
        x = torch.from_numpy(preview_inputs(env, env.pairs[idx[need]])[:, foe]).to(self.dev)
        lead, back, _ = self.preview(x)
        probs = outcome_probs(lead.float(), back.float()).cpu().numpy()
        seq = self.outcome_seq
        for j, n in enumerate(need):
            b, hk = bring[n], hidden[n]
            leads = {int(b[0]), int(b[1])}
            seen = {int(b[k]) for k in (2, 3) if k not in hk}
            ok = np.array([set(seq[o, :2]) == leads and seen <= set(seq[o, 2:]) for o in range(N_OUTCOMES)])
            p = np.where(ok, probs[j], 0.0)
            p = p / p.sum() if p.sum() > 0 else ok / ok.sum()
            o = self.rng.choice(N_OUTCOMES, p=p)
            fresh = [int(s) for s in self.rng.permutation(seq[o, 2:]) if int(s) not in seen]
            swaps[n] = [(int(k), s) for k, s in zip(hk, fresh)]
            for k, s in swaps[n]:
                b[k] = s
        return bring, swaps

    def _finish_foe_switches(self, side: int, idx: np.ndarray, n_rows: int) -> None:


        foe, km = 1 - side, self.k * self.mb
        mk = self.masks
        read_masks(self.scratch, mk)
        rows = np.flatnonzero((self.status[:n_rows] == -1) & mk.to_move[:n_rows, foe] & ~mk.to_move[:n_rows, side])
        if len(rows) == 0:
            return
        fo = self.foe_obs
        self.scratch.observe(foe, fo.field, fo.mon_ids, fo.mon_features, fo.history)
        bring = self.env.bring[idx[rows // km], foe]
        bits = mk.bits_at(rows, foe)
        acts = []
        for a in range(0, len(rows), self.chunk):
            sl = slice(a, a + self.chunk)
            r = rows[sl]
            x = tuple(torch.from_numpy(arr[r]).to(self.dev) for arr in (fo.field, fo.mon_ids, fo.mon_features, fo.history)) + (
                torch.from_numpy(bring[sl]).to(self.dev),)
            with amp(self.dev):
                s = self.model.act(x, torch.from_numpy(bits[sl]).to(self.dev), torch.from_numpy(mk.mega[r, foe]).to(self.dev),
                                   torch.from_numpy(mk.min_switches[r, foe]).to(self.dev), self.gen)
            acts.append(s["actions"].cpu().numpy())
        branch = np.zeros((self.branches, 2, 2, 2), np.int32)
        branch[rows, foe] = np.concatenate(acts)
        self.scratch.step(branch, rows.tolist())
        self.scratch.status(self.status)

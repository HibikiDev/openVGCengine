








from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import numpy as np
import torch
import vgc_engine as ve

from ..canonical import bare
from ..env import Masks, Observation, load_teams, read_masks
from ..model import load_weights
from ..preview import N_OUTCOMES, outcome_probs
from ..search import OneStepSearch, guessed_spreads
from .agent import CLOSER_MIN_TURN, sheet_tokens
from .requests import PASS_ACTION, SWITCH_BASE, TARGET_ALLY, RequestMasks
from .snapshot import Unsupported, party_order, snapshot
from .tracker import Tracker

_CORPUS: list[list[dict]] | None = None
STANDINGS = Path(__file__).resolve().parents[3] / "tools/corpus/out/standings-sets-v2.json"

SV_TEAMS = {f: Path(__file__).resolve().parents[3] / f"tools/corpus/out/teams-sv-{r}.json"
            for f, r in (("gen9vgc2023regc", "regc"), ("gen9vgc2023regd", "regd"), ("gen9vgc2024regg", "regg"), ("gen9vgc2025regi", "regi"))}
_SV_CORPUS: dict[str, list[list[dict]]] = {}


USAGE = Path(__file__).resolve().parents[3] / "data/smogon-usage"


def _corpus_for(fmt: str | None) -> list[list[dict]]:


    if fmt in SV_TEAMS:
        if fmt not in _SV_CORPUS:
            f = SV_TEAMS[fmt]
            _SV_CORPUS[fmt] = ([e["sets"] for e in json.loads(f.read_text(encoding="utf8"))["teams"]] if f.exists()
                               else usage_corpus(fmt))
        return _SV_CORPUS[fmt]
    return _corpus()


def _corpus() -> list[list[dict]]:



    global _CORPUS
    if _CORPUS is None:
        from ..env import DEFAULT_TEAMS
        _CORPUS = (load_teams() + load_teams(STANDINGS) if DEFAULT_TEAMS.exists() and STANDINGS.exists()
                   else usage_corpus("gen9championsvgc2026regmc"))
    return _CORPUS


def usage_corpus(fmt: str, top: int = 20, scale: int = 20) -> list[list[dict]]:




    import gzip
    try:
        files = json.loads((USAGE / "manifest.json").read_text(encoding="utf8"))["files"]
        entry = next(e for e in files if e["format"] == fmt)
        data = json.loads(gzip.decompress((USAGE / entry["file"]).read_bytes()))["data"]
    except (OSError, ValueError, StopIteration, KeyError):
        return []
    sets = []
    for species, v in data.items():
        spreads = sorted((v.get("Spreads") or {}).items(), key=lambda kv: -kv[1])[:top]
        if not spreads:
            continue
        best = spreads[0][1] or 1.0
        for key, w in spreads:
            nature, _, stats = key.partition(":")
            try:
                vals = [int(x) for x in stats.split("/")]
            except ValueError:
                continue
            if len(vals) != 6:
                continue
            s = {"species": species, "nature": nature, "evs": dict(zip(("hp", "atk", "def", "spa", "spd", "spe"), vals))}
            sets += [s] * max(1, round(scale * w / best))
    return [sets]


class RootEnv:



    def __init__(self, sheets: list[list[dict]], fmt: str | None = None):
        self.n = 1
        self.pool = ve.BattlePool(1)

        self.teams = [(s * 6)[:6] for s in sheets]
        self.team_ids = [self.pool.register_team(t) if fmt is None else self.pool.register_team(t, fmt) for t in self.teams]
        self.pairs = np.array([[0, 1]], np.int64)
        self.bring = np.zeros((1, 2, ve.BROUGHT_SIZE), np.int64)
        self.obs = [Observation.empty(1), Observation.empty(1)]
        self.masks = Masks.empty(1)
        self.status = np.full(1, -1, np.int8)

    def load(self, snap: dict, seed: int) -> None:
        self.pool.load_state(0, snap, seed)
        self.bring[0] = np.array(snap["bring"])
        for side in (0, 1):
            o = self.obs[side]
            self.pool.observe(side, o.field, o.mon_ids, o.mon_features, o.history)
        m = self.masks
        read_masks(self.pool, m)
        self.pool.status(self.status)


class LiveSearch:









    def __init__(self, agent, k: int = 8, m: int = 8, seed: int = 0, score: str = "value", greedy_column: bool = True,
                 margin: float = 0.1, soft_temp: float = 0.05, cand_temp: float = 2.0,
                 protect_variants: bool = False):
        self.agent, self.k, self.m, self.cand_temp, self.protect_variants = agent, k, m, cand_temp, protect_variants
        self.score, self.greedy_column, self.margin, self.soft_temp = score, greedy_column, margin, soft_temp
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        self.last: dict | None = None
        self._guesses: dict[str, list] = {}
        self.opp_head: torch.nn.Module | None = None
        self.opp_head_ckpt: str | None = None
        self.foe_preview: torch.nn.Module | None = None
        self.reply_policy: torch.nn.Module | None = None

    def load_reply_policy(self, path: str) -> None:



        from ..model import load_policy

        self.reply_policy = load_policy(torch.load(path, map_location=self.agent.dev, weights_only=True), self.agent.dev).eval()

    def load_foe_preview(self, path: str) -> None:


        sd = torch.load(path, map_location=self.agent.dev, weights_only=True)
        net = copy.deepcopy(self.agent.preview).float()
        load_weights(net, sd["preview"])
        self.foe_preview = net.eval()

    def load_opp_head(self, path: str) -> None:


        sd = torch.load(path, map_location=self.agent.dev, weights_only=True)
        head = copy.deepcopy(bare(self.agent.policy).aux).float()
        head.load_state_dict(sd["aux"])
        self.opp_head, self.opp_head_ckpt = head.eval(), sd["meta"]["ckpt"]

    def _reply_adjust(self, t: Tracker, memory: dict | None):

        counts = _choice_counts(t, memory)
        slots, seen = [], 0
        for slot in (0, 1):
            i = t.shown[t.foe][slot]
            if i is None or t.mons[t.foe][i].fainted:
                slots.append(None)
                continue
            moves = list(t.mons[t.foe][i].moves)
            slots.append((moves, counts[i]))
            seen += sum(k for mid, k in counts[i].items() if mid in moves)
        return (_reply_adjust_fn(slots, self.agent.dev) if seen else None), seen

    @torch.inference_mode()
    def foe_bring(self, t: Tracker, my_sheet: list[dict], foe_sheet: list[dict], memory: dict | None = None,
                  fmt: str | None = None) -> list[int]:






        foe = t.foe
        seen = [i for i, m in enumerate(t.mons[foe]) if m.revealed]
        if len(seen) >= 4 or self.agent.preview is None:
            rest = [i for i in range(len(foe_sheet)) if i not in seen]
            return (seen + self.rng.sample(rest, 4 - len(seen)))[:4] if len(seen) < 4 else seen[:4]

        x = np.concatenate([sheet_tokens((foe_sheet * 6)[:6], fmt), sheet_tokens((my_sheet * 6)[:6], fmt, as_opponent=not t.open_sheets)])[None]
        net = self.foe_preview if self.foe_preview is not None and fmt is None else self.agent.preview
        with torch.no_grad():
            lead, back, _ = net(torch.from_numpy(x).to(self.agent.dev))
        n = len(foe_sheet)
        if n < 6:
            lead[:, n:] = float("-inf")
            back[:, n:] = float("-inf")
        p = outcome_probs(lead.float(), back.float())[0].cpu().numpy()
        seq = _outcome_seq()
        leads = set(getattr(t, "leads", {}).get(foe, []))
        ok = np.array([set(seen) <= set(seq[o]) and max(seq[o]) < n and (len(leads) < 2 or set(int(x) for x in seq[o][:2]) == leads)
                       for o in range(N_OUTCOMES)])
        p = np.where(ok, p, 0.0)
        before = set((memory or {}).get("brought", ()))
        if before:
            p = p * np.array([BROUGHT_WEIGHT ** len(before & set(int(x) for x in seq[o])) for o in range(N_OUTCOMES)])
        p = p / p.sum() if p.sum() > 0 else ok / ok.sum()
        o = int(np.argmax(p)) if self.foe_preview is not None else int(self.np_rng.choice(N_OUTCOMES, p=p))
        return seen + [int(s) for s in seq[o] if int(s) not in seen]

    def choose(self, t: Tracker, req: dict, my_sheet: list[dict], foe_sheet: list[dict], bring: list[int],
               masks: RequestMasks, ctx: dict | None = None, value: float | None = None,
               memory: dict | None = None, reply_temp: float = 1.0, arm: dict | None = None,
               explain: dict | None = None, foe_world: list[dict] | None = None,
               fmt: str | None = None) -> list[tuple[int, bool]]:














        arm = arm or {}
        closed = not t.open_sheets
        if closed:
            if not foe_world:
                raise ValueError("closed sheets: no world for the opponent's sets")

            arm = {k: v for k, v in arm.items() if k not in ("opp_head", "reply_policy") and not k.startswith("rollout")}
            if any((s_.get("ability") or "") == "Illusion" for s_ in foe_world):

                raise Unsupported("Illusion possible in the opponent's world")
            foe_sheet = foe_world
        reply_temp = arm.get("reply_temp", reply_temp)
        opp_head = None
        if arm.get("opp_head"):
            playing = Path(getattr(self.agent, "checkpoint", "") or "").name
            if self.opp_head is None or self.opp_head_ckpt != playing:

                raise ValueError(f"human head fitted on {self.opp_head_ckpt}, playing {playing or '?'}")
            if bare(self.agent.policy) is not self.agent.policy and self.agent.policy.on:

                raise ValueError("human head (arm H) is fitted on a raw-frame trunk - not usable with a canonical-slots checkpoint")
            opp_head = self.opp_head
        reply_policy = None
        if arm.get("reply_policy"):
            if self.reply_policy is None:
                raise ValueError("arm wants the human-imitation reply policy, none loaded (--reply-policy)")
            reply_policy = self.reply_policy
        """The searched joint action for a `Turn` request, legal under `masks`; raises (`snapshot.Unsupported` or anything else)
        when the position can't be searched."""
        if req.get("forceSwitch") or not req.get("active") or masks.min_switches:
            raise ValueError("not a Turn request")
        me, foe = t.me, t.foe
        side = 0 if me == "p1" else 1
        sheets = {me: my_sheet, foe: foe_sheet}

        bfmt = fmt if closed else t.fmt
        env = RootEnv([sheets["p1"], sheets["p2"]], bfmt)
        brings = {me: list(bring), foe: self.foe_bring(t, my_sheet, foe_sheet, memory, bfmt)}
        foe_sets = ([{"moves": ([ve.lookup("move", mv) for mv in s_["moves"]] + [0] * 4)[:4], "ability": ve.lookup("ability", s_["ability"]),
                      "item": ve.lookup("item", s_["item"]) if s_.get("item") else 0} for s_ in foe_world] if closed else None)
        snap = snapshot(t, {"p1": env.team_ids[0], "p2": env.team_ids[1]}, brings, party_order(t, req, bring), None, self.rng,
                        foe_sets=foe_sets)
        env.load(snap, self.rng.getrandbits(62))
        if not env.masks.to_move[0, side]:
            raise ValueError("the rebuilt battle has no decision for me")



        tier = None
        if arm.get("deepen"):
            mf = env.obs[side].mon_features[0]
            seen, hp = mf[:, 1] > 0.5, mf[:, 5]
            mine = int((seen[:6] & (hp[:6] > 0)).sum())
            foe_left = int((seen[6:] & (hp[6:] > 0)).sum()) + max(0, 4 - int(seen[6:].sum()))
            for max_mons, over in arm["deepen"]:
                if mine <= max_mons and foe_left <= max_mons:
                    arm, tier = {**arm, **over}, max_mons
                    break
        pol = self.agent.policy
        search = OneStepSearch(pol, env, self.agent.dev, k=arm.get("k", self.k), m=self.m, samples=arm.get("samples", 32),
                               seed=self.rng.getrandbits(62),
                               replies=arm.get("replies") or ("self" if closed else "policy" if reply_policy is not None else "aux"),
                               reply_policy=reply_policy,
                               score=arm.get("score", self.score), finish_switch=False, greedy_column=self.greedy_column,
                               cand_temp=self.cand_temp, protect_variants=self.protect_variants,
                               inject_protect=arm.get("inject_protect", False), seeds=arm.get("seeds", 1),
                               reply_mode=arm.get("reply_mode", "sample"), robust=arm.get("robust", 0.0), opp_head=opp_head,
                               depth2=arm.get("rollouts", 0), depth2_mix=arm.get("rollout_mix", 0.0),
                               rollout_fix=bool(arm.get("rollouts")), rollout_len=arm.get("rollout_len", 1),
                               rollout_dedupe=arm.get("rollout_dedupe", "off") if arm.get("rollouts") else "off",
                               rollout_trigger=arm.get("rollout_trigger") if arm.get("rollouts") else None,
                               slot_variants=arm.get("slot_variants", 0))


        key = json.dumps(env.teams, sort_keys=True)
        if closed:
            self._guesses[key] = None
        if key not in self._guesses:
            if len(self._guesses) > 64:
                self._guesses.clear()
            self._guesses[key] = guessed_spreads(env.teams, _corpus_for(t.fmt))


            for k, team in enumerate(env.teams):
                for r, st in enumerate(team):
                    if st.get("known_spread"):
                        self._guesses[key][k][r] = (st["known_spread"][0], tuple(int(x) for x in st["known_spread"][1]))
        search.guesses = self._guesses[key]
        adjust, seen = self._reply_adjust(t, memory)
        if reply_temp != 1.0:
            memory_adjust = adjust
            adjust = lambda logits, idx: (logits / reply_temp if memory_adjust is None
                                          else memory_adjust(logits / reply_temp, idx))
        search.reply_adjust = adjust
        cand, q, _ = search.evaluate(side, np.array([0]))
        q = q[0]
        acts = [[(int(cand[0, i, s, 0]), bool(cand[0, i, s, 1])) for s in (0, 1)] for i in range(len(q))]
        ok = np.array([_legal(a, masks) for a in acts])
        if not ok.any():
            raise ValueError("no searched candidate is legal under the request")
        held = 0
        if arm.get("min_margin"):


            conf = {slot: e["top"][0][0] for slot, e in enumerate((explain or {}).get("slots") or [])
                    if e and e.get("top") and e["top"][0][1] >= CONFIDENT_P}
            keeps = ok & np.array([all(a[slot][0] == act for slot, act in conf.items()) for a in acts])
            if conf and keeps.any():
                best_keep = float(np.max(np.where(keeps, q, -np.inf)))
                allowed = ok & (keeps | (q >= best_keep + arm["min_margin"]))
                held = int(ok.sum() - allowed.sum())
                ok = allowed
        closer = (self.agent.closer is not None and value is not None and value > self.agent.closer
                  and (ctx or {}).get("turn", CLOSER_MIN_TURN) >= CLOSER_MIN_TURN)
        mode = "soft"
        if closer:
            damaging = (ctx or {}).get("damaging", [[True] * 4, [True] * 4])
            safe = ok & np.array([not _risky(a, damaging) for a in acts])
            pool = safe if safe.any() else ok
            i = int(np.argmax(np.where(pool, q, -np.inf)))
            mode = "closer"
        else:
            w = soft_pick(q, ok, acts, arm.get("margin", self.margin), arm.get("soft_temp", self.soft_temp), arm.get("distinct", False))
            i = int(self.np_rng.choice(len(q), p=w))
        self.last = {"q": [round(float(v), 3) for v in q], "chosen": i, "mode": mode, "foe_bring": brings[foe], "foe_seen": seen,
                     "reply_temp": reply_temp, "arm": arm.get("name"), "held": held, "deepen": tier}
        if getattr(search, "_last_trigger", None) is not None:
            self.last["rolled_out"] = bool(search._last_trigger[0])
        q1 = getattr(search, "_last_q1", None)
        if q1 is not None and self.last.get("rolled_out", True):


            self.last["q1"] = [round(float(v), 3) for v in q1[0]]


        self.last["cands"] = [[[a, int(m)] for a, m in c] for c in acts]
        reps: dict = {}
        for r, w in zip(search.last_replies[0].tolist(), search.last_weights[0].tolist()):
            key = json.dumps(r)
            reps[key] = reps.get(key, 0.0) + float(w)
        self.last["replies"] = [[json.loads(k), round(w, 3)] for k, w in sorted(reps.items(), key=lambda kv: -kv[1])]
        cover = getattr(search, "last_cover", None)
        if cover is not None and len(cover):
            self.last["cover"] = round(float(cover[0]), 3)
        return acts[i]


def soft_pick(q: np.ndarray, ok: np.ndarray, acts: list, margin: float, temp: float, distinct: bool = False) -> np.ndarray:



    if distinct:
        first = np.zeros(len(acts), bool)
        seen: set = set()
        for n, a in enumerate(acts):
            key = tuple(map(tuple, a))
            if key not in seen:
                seen.add(key)
                first[n] = True
        ok = ok & first
    best = float(np.max(np.where(ok, q, -np.inf)))
    near = ok & (q >= best - margin)
    w = np.where(near, np.exp((q - best) / temp), 0.0)
    return w / w.sum()


CONFIDENT_P = 0.8


SEARCH_ARMS = {
    "A": {"name": "A"},
    "B": {"name": "B", "score": "both", "inject_protect": True, "min_margin": 0.05},
    "C": {"name": "C", "min_margin": 0.05},


    "E": {"name": "E", "min_margin": 0.05, "seeds": 4, "reply_mode": "top"},
    "F": {"name": "F", "min_margin": 0.05, "seeds": 4, "reply_mode": "top", "robust": 0.25},


    "G": {"name": "G", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 8.0},
    "H": {"name": "H", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "opp_head": True},


    "J": {"name": "J", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "reply_policy": True},


    "K": {"name": "K", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "reply_policy": True,
          "distinct": True, "margin": 0.05, "soft_temp": 0.02},



    "L": {"name": "L", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "reply_policy": True,
          "distinct": True, "margin": 0.05, "soft_temp": 0.02, "rollouts": 8, "rollout_len": 2, "rollout_mix": 0.5},



    "T15": {"name": "T15", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "reply_policy": True,
            "distinct": True, "margin": 0.05, "soft_temp": 0.02, "rollouts": 8, "rollout_len": 2, "rollout_mix": 0.5,
            "rollout_dedupe": "save", "rollout_trigger": 0.15},


    "D3": {"name": "D3", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "reply_policy": True,
           "distinct": True, "margin": 0.05, "soft_temp": 0.02, "rollouts": 8, "rollout_len": 3, "rollout_mix": 0.5,
           "rollout_dedupe": "save", "rollout_trigger": 0.15},




    "S256": {"name": "S256", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "reply_policy": True,
             "distinct": True, "margin": 0.05, "soft_temp": 0.02, "rollouts": 8, "rollout_len": 2, "rollout_mix": 0.5,
             "rollout_dedupe": "save", "rollout_trigger": 0.15, "samples": 256},




    "S256D": {"name": "S256D", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "reply_policy": True,
              "distinct": True, "margin": 0.05, "soft_temp": 0.02, "rollouts": 8, "rollout_len": 2, "rollout_mix": 0.5,
              "rollout_dedupe": "save", "rollout_trigger": 0.15, "samples": 256,


              "deepen": [[2, {"k": 16, "rollouts": 8, "rollout_len": 8, "rollout_mix": 0.0, "rollout_trigger": None,
                              "rollout_dedupe": "equal"}],
                         [3, {"rollouts": 8, "rollout_len": 3, "rollout_trigger": None}]]},



    "S256S": {"name": "S256S", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "replies": "self",
              "distinct": True, "margin": 0.05, "soft_temp": 0.02, "rollouts": 8, "rollout_len": 2, "rollout_mix": 0.5,
              "rollout_dedupe": "save", "rollout_trigger": 0.15, "samples": 256},



    "SV": {"name": "SV", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "reply_policy": True,
           "distinct": True, "margin": 0.05, "soft_temp": 0.02, "rollouts": 8, "rollout_len": 2, "rollout_mix": 0.5,
           "rollout_dedupe": "save", "rollout_trigger": 0.15, "slot_variants": 12},
    "S256SV": {"name": "S256SV", "min_margin": 0.05, "reply_mode": "top", "robust": 0.25, "reply_temp": 1.0, "reply_policy": True,
               "distinct": True, "margin": 0.05, "soft_temp": 0.02, "rollouts": 8, "rollout_len": 2, "rollout_mix": 0.5,
               "rollout_dedupe": "save", "rollout_trigger": 0.15, "samples": 256, "slot_variants": 12},
}
BROUGHT_WEIGHT = 3.0
PRIOR_CHOICES = 4.0

FIRST_TURN_MOVES = {ve.lookup("move", n) for n in ("Fake Out", "First Impression", "Mat Block")}


def _choice_counts(t: Tracker, memory: dict | None) -> dict[int, dict[int, int]]:

    out: dict[int, dict[int, int]] = {}
    earlier = (memory or {}).get("used", {})
    for i, m in enumerate(t.mons[t.foe]):
        c = dict(earlier.get(i, {}))
        for mid, k in m.used.items():
            c[mid] = c.get(mid, 0) + k
        out[i] = c
    return out


def _reply_adjust_fn(slots: list[tuple[list[int], dict[int, int]] | None], dev):




    def adjust(logits: torch.Tensor, idx) -> torch.Tensor:
        logits = logits.clone()
        for s, slot in enumerate(slots):
            if slot is None:
                continue
            moves, counts = slot
            c = np.array([0.0 if mid in FIRST_TURN_MOVES or mid == 0 else float(counts.get(mid, 0)) for mid in moves[:4]])
            n = c.sum()
            if n == 0:
                continue
            probs = torch.softmax(logits[:, s].float(), -1).cpu().numpy()
            q = probs[:, :SWITCH_BASE].reshape(len(probs), 4, 4).sum(-1)
            usable = np.array([mid != 0 and mid not in FIRST_TURN_MOVES for mid in moves[:4]])
            q_all = (q * usable).sum(-1, keepdims=True)
            post = (PRIOR_CHOICES * q + q_all * c) / (PRIOR_CHOICES + n)
            bias = np.where(usable, np.clip(np.log(np.maximum(post, 1e-6) / np.maximum(q, 1e-6)), -4.0, 4.0), 0.0)
            logits[:, s, :SWITCH_BASE] += torch.from_numpy(np.repeat(bias, 4, axis=-1)).to(logits.device, logits.dtype)
        return logits
    return adjust


def _risky(actions: list[tuple[int, bool]], damaging: list[list[bool]]) -> bool:

    for s, (a, _) in enumerate(actions):
        if SWITCH_BASE <= a < PASS_ACTION or (a < SWITCH_BASE and a % 4 == TARGET_ALLY and damaging[s][a // 4]):
            return True
    return False


def _legal(actions: list[tuple[int, bool]], masks: RequestMasks) -> bool:


    for s, (a, mega) in enumerate(actions):
        forced = (masks.forced[s] >> a) & 1
        if not ((masks.actions[s] >> a) & 1 or forced):
            return False
        if mega and not (masks.gimmick[s] >> a) & 1:
            return False
        if forced and not mega:
            return False
    if actions[0][1] and actions[1][1] and masks.kind[0] == masks.kind[1]:
        return False
    return True


_SEQ: np.ndarray | None = None


def _outcome_seq() -> np.ndarray:

    global _SEQ
    if _SEQ is None:
        from ..preview import _OUTCOME_IDS, _SEQS
        _SEQ = np.zeros((N_OUTCOMES, 4), np.int64)
        for s, o in zip(_SEQS.numpy(), _OUTCOME_IDS.numpy()):
            _SEQ[o] = s
    return _SEQ














from __future__ import annotations

import copy
import threading
import time

import numpy as np
import torch

from ..env import VecEnv
from ..model import load_policy, load_weights
from ..batch import Batch, side_actions
from ..preview import _SEQS, bring_logp
from .agent import Agent, sheet_tokens


class CounterBring:
    def __init__(self, checkpoint: str, reply_policy: str, foe_preview: str, device: str = "cuda", games: int = 128,
                 top: int = 6, seed: int = 101):
        self.dev = torch.device(device)
        ours = Agent(checkpoint, device=device)
        if ours.policy is None or ours.preview is None:
            raise ValueError(f"{checkpoint}: no policy / preview head for the counter-bring selector")
        self.policy, self.preview = ours.policy.eval(), ours.preview.eval()
        self.reply = load_policy(torch.load(reply_policy, map_location=self.dev, weights_only=True), self.dev).eval()
        sd = torch.load(foe_preview, map_location=self.dev, weights_only=True)
        self.foe_preview = copy.deepcopy(self.preview).float()
        load_weights(self.foe_preview, sd["preview"])
        self.foe_preview.eval()
        self.games, self.top, self.seed = games, top, seed
        self.lock = threading.Lock()
        self.calls = 0

    @torch.inference_mode()
    def _outcomes(self, head, mine: list[dict], theirs: list[dict]) -> tuple[np.ndarray, np.ndarray]:

        x = np.concatenate([sheet_tokens(mine), sheet_tokens(theirs)])[None]
        lead, back, _ = head(torch.from_numpy(x).to(self.dev))
        n = len(mine)
        if n < 6:
            lead[:, n:] = float("-inf")
            back[:, n:] = float("-inf")
        seqs = _SEQS.to(self.dev)
        lp = bring_logp(lead.float().repeat(len(seqs), 1), back.float().repeat(len(seqs), 1), seqs).cpu().numpy()
        return _SEQS.numpy(), lp

    def target(self, mine: list[dict], theirs: list[dict], lead: list[int], shown: list[int]) -> list[int]:


        if len(shown) >= 2:
            return lead + shown[:2]
        seqs, lp = self._outcomes(self.foe_preview, theirs, mine)
        best, arg = -np.inf, None
        for s, v in zip(seqs, lp):
            if set(s[:2]) == set(lead) and set(shown) <= set(s[2:]) and v > best:
                best, arg = v, s
        if arg is None:
            raise ValueError("no outcome consistent with their previous lead")
        return lead + [int(b) for b in (shown + [b for b in arg[2:] if b not in shown])][:2]

    def candidates(self, mine: list[dict], theirs: list[dict]) -> list[list[int]]:


        seqs, lp = self._outcomes(self.preview, mine, theirs)
        top = [int(x) for x in seqs[int(np.argmax(lp))]]
        best: dict = {}
        for s, v in zip(seqs, lp):
            key = frozenset(s[:2].tolist())
            if key not in best or v > best[key][0]:
                best[key] = (v, [int(x) for x in s])
        out = [top]
        for _, s in sorted(best.values(), key=lambda t: -t[0])[:self.top]:
            if not (set(s[:2]) == set(top[:2]) and set(s[2:]) == set(top[2:])):
                out.append(s)
        return out

    @torch.inference_mode()
    def _play(self, mine, theirs, brings: list[list[int]], target: list[int]) -> np.ndarray:

        jobs = [b for b in brings for _ in range(self.games)]
        n = len(jobs)
        teams = [t for _ in range(n) for t in (mine, theirs)]
        pairs = np.array([[2 * i, 2 * i + 1] for i in range(n)], np.int64)
        bring = np.array([[j, target] for j in jobs], np.int64)
        env = VecEnv(n, teams, seed=self.seed + self.calls, bring_fn=lambda idx, prs: bring[idx], pair_fn=lambda k: pairs[:k])
        env.reset_battles(np.arange(n))
        env.refresh()
        gen = torch.Generator(device=self.dev)
        gen.manual_seed(self.seed + self.calls)
        out = np.zeros(n)
        done = np.zeros(n, bool)
        for _ in range(400):
            b = Batch(env, self.dev)
            with torch.autocast(self.dev.type, dtype=torch.float16, enabled=self.dev.type == "cuda"):
                acts = self.policy.act(b.inputs(), b.bits, b.mega, b.min_switches, gen, 1.0)["actions"].cpu().numpy()
                acts[n:] = self.reply.act(b.inputs(), b.bits, b.mega, b.min_switches, gen, 1.0)["actions"].cpu().numpy()[n:]
            status = env.step(side_actions(acts, n))
            for i in np.flatnonzero((status >= 0) & ~done):
                done[i] = True
                out[i] = 1.0 if status[i] == 0 else (0.5 if status[i] == 2 else 0.0)
            if done.all():
                break
            env.refresh()
        return out.reshape(len(brings), self.games).mean(1)

    def choose(self, mine: list[dict], theirs: list[dict], prev_lead: list[int], prev_shown: list[int]) -> tuple[list[int], dict]:

        t0 = time.monotonic()
        with self.lock:
            self.calls += 1
            target = self.target(mine, theirs, list(prev_lead), list(prev_shown))
            cands = self.candidates(mine, theirs)
            wr = self._play(mine, theirs, cands, target)
        k = int(np.argmax(wr))
        return cands[k], {"target": target, "cands": cands, "wr": [round(float(w), 3) for w in wr], "pick": k,
                          "ms": round(1000 * (time.monotonic() - t0))}

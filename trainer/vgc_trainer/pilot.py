



from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from .amp import amp
from .batch import Batch, preview_inputs, side_actions
from .env import VecEnv, random_legal_actions
from .model import load_policy, load_weights
from .preview import PreviewNet, sample_bring


class Agent:
    def __init__(self, path: str, dev: torch.device):
        self.random = path == "random"
        self.greedy = path == "greedy"
        self.policy = self.preview = self.shaping = self.previews = None
        self.preview_temp = 1.0
        self.temperature = None
        if self.random or self.greedy:
            return
        ck = torch.load(path, map_location=dev)
        self.shaping = ck.get("meta", {}).get("cfg", {}).get("shaping")
        self.policy = load_policy(ck, dev)
        if ck.get("preview"):
            self.preview = PreviewNet().to(dev).eval()
            load_weights(self.preview, ck["preview"])
        self.previews = None if self.preview is None else [self.preview]
        self.preview_temp = 1.0

    def use_previews(self, spec: str, dev: torch.device) -> None:

        if spec == "random":
            self.previews = None
            return
        self.previews = []
        for path in spec.split(","):
            net = PreviewNet().to(dev).eval()
            load_weights(net, torch.load(path, map_location=dev)["preview"])
            self.previews.append(net)


def play(pilots: list[Agent], teams: list[list[dict]], games: int, n: int, seed: int, dev: torch.device, focus: list[int] | None,
         temperature: float = 1.0, on_step=None, opp_p=None, on_done=None, pairs=None, search=None, max_steps: int = 60,
         fmt: str | None = None) -> dict:












    rng = np.random.default_rng(seed + 7)
    nt = len(teams)

    first = None if pairs is None else np.asarray(pairs)

    def pair_fn(k):
        nonlocal first
        if first is not None and len(first) == k:
            out, first = first, None
            return out
        if not focus:
            return rng.choice(nt, size=(k, 2))
        pairs = np.stack([rng.choice(focus, size=k), rng.choice(nt, size=k, p=opp_p)], 1)
        swap = rng.random(k) < 0.5
        pairs[swap] = pairs[swap][:, ::-1]
        return pairs

    env = VecEnv(n, teams, seed=seed, formats=[fmt] * len(teams) if fmt else None)
    env.pair_fn = pair_fn
    a_side = np.arange(n) % 2
    gen = torch.Generator(device=dev)
    gen.manual_seed(seed)
    pv = np.zeros((n, 2), np.float32)

    def bring_fn(idx, pairs):
        bring = env.choose_bring(len(idx)).astype(np.int64)
        pv[idx] = np.nan
        x = torch.from_numpy(preview_inputs(env, pairs).reshape(2 * len(idx), 12, -1)).to(dev)
        for k, agent in enumerate(pilots):
            if agent.preview is None:
                continue
            with torch.inference_mode():
                lead, back, value = agent.preview(x)
                chosen = sample_bring(lead.float() / temperature, back.float() / temperature, gen)[0].cpu().numpy().reshape(len(idx), 2, 4)
                value = value.cpu().numpy().reshape(len(idx), 2)
            for j, i in enumerate(idx):


                for side in ((0, 1) if len(pilots) == 1 else (a_side[i] if k == 0 else 1 - a_side[i],)):
                    bring[j, side] = chosen[j, side]
                    pv[i, side] = value[j, side]
        return bring

    env.bring_fn = bring_fn
    env.reset_battles(np.arange(n))
    env.refresh()
    cols = {k: [] for k in ("pairs", "bring", "result", "turns", "pv", "seed", "a_side")}
    finished = 0
    searcher = search(env, seed) if search is not None else None
    served = np.zeros(n, bool) if search is not None else None
    t0 = time.time()

    def on_finish(status):
        nonlocal finished
        done = np.flatnonzero(status >= 0)
        if served is not None:
            done = done[~served[done]]
            served[(status >= 0) | (status == -3)] = True
        if len(done) == 0:
            return
        if served is None:
            done = done[: max(0, games - finished)]
        turns = np.asarray(env.pool.turns())[done]
        res = np.where(status[done] == 0, 1.0, np.where(status[done] == 1, 0.0, 0.5))
        cols["pairs"].append(env.pairs[done].copy())
        cols["bring"].append(env.bring[done].copy())
        cols["result"].append(res.astype(np.float32))
        cols["turns"].append(turns.astype(np.int16))
        cols["pv"].append(pv[done].copy())
        cols["seed"].append(env.seeds[done].copy())
        cols["a_side"].append(a_side[done].astype(np.int8))
        if on_done is not None:
            on_done(env, done, res)
        finished += len(done)

    last = 0
    step, dropped = 0, []
    recent: list[np.ndarray] = []
    while (finished < games) if served is None else not served.all():
        if served is not None and step >= max_steps:
            turns_now, cut = np.asarray(env.pool.turns()), np.flatnonzero(~served)
            for i in cut:
                dropped.append((int(env.pairs[i, 0]), int(env.pairs[i, 1]), int(turns_now[i])))
            print(f"  dropped {len(dropped)} battles still running after {max_steps} decision steps (pair, turn): {dropped}", flush=True)
            try:
                with open(Path(__file__).resolve().parents[1] / "runs/search_dropped.jsonl", "a", encoding="utf8") as f:
                    for i in cut:
                        f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "step": step, "pair": env.pairs[i].tolist(),
                                            "state": env.pool.inspect(int(i)), "last_actions": [a[i].tolist() for a in recent]},
                                           default=str) + "\n")
            except Exception as e:
                print(f"  (couldn't record the dropped battles: {e})", flush=True)
            served[:] = True
            break
        step += 1
        batch = Batch(env, dev)
        acts = []
        for agent in pilots:
            if agent.random:
                acts.append(random_legal_actions(env.masks, rng))
                continue
            if agent.greedy:
                g = np.zeros((n, 2, 2, 2), np.int32)
                for side in (0, 1):
                    out = np.zeros((n, 2, 2), np.int32)
                    env.pool.greedy_actions(side, int(rng.integers(1 << 62)), out)
                    g[:, side] = out
                acts.append(g)
                continue
            with torch.inference_mode(), amp(dev):
                t = agent.temperature if getattr(agent, "temperature", None) is not None else temperature
                s = agent.policy.act(batch.inputs(), batch.bits, batch.mega, batch.min_switches, gen, t)
            acts.append(side_actions(s["actions"].cpu().numpy(), n))
        actions = acts[-1].copy()
        for side in (0, 1):
            sel = a_side == side
            actions[sel, side] = acts[0][sel, side]
        if searcher is not None:
            for side in (0, 1):
                searcher.choose(side, actions, (env.masks.min_switches[:, side] == 0) & ~served)
            recent = (recent + [actions.copy()])[-8:]
        if on_step is not None:
            on_step(env, actions)
        env.step(actions, on_finish)
        env.refresh()
        if finished - last >= 50000:
            last = finished
            print(f"  {finished} games, {finished / (time.time() - t0):.0f}/s", flush=True)
    if env.engine_errors:
        print(f"engine errors: {len(env.engine_errors)} (first: {env.engine_errors[0]})")
    out = {k: np.concatenate(v) if v else np.zeros(0) for k, v in cols.items()}
    if served is not None:
        out["dropped"] = np.array(dropped, np.int64).reshape(-1, 3)
    return out

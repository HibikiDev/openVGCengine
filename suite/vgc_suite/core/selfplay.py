



from __future__ import annotations

import numpy as np
import torch

from vgc_trainer.env import VecEnv
from vgc_trainer.batch import Batch, side_actions


def play_fixed(policy, sheets: list[list[dict]], cells: list[tuple[list[int], list[int]]], games_per_cell: int, dev: torch.device,
               seed: int = 0, batch: int = 1024, policy_b=None, search=None, progress=None, fmt: str | None = None,
               watch=None) -> tuple[np.ndarray, np.ndarray]:









    jobs = np.repeat(np.arange(len(cells)), games_per_cell)
    points = np.zeros(len(cells))
    played = np.zeros(len(cells), np.int64)
    gen = torch.Generator(device=dev)
    gen.manual_seed(seed)
    amp = dev.type == "cuda"
    for start in range(0, len(jobs), batch):
        cell_of = jobs[start:start + batch]
        n = len(cell_of)
        bring = np.array([[cells[c][0], cells[c][1]] for c in cell_of], np.int64)

        def bring_fn(idx, pairs, bring=bring):
            return bring[idx]

        env = VecEnv(n, sheets, seed=seed + start, bring_fn=bring_fn, pair_fn=lambda k: np.tile(np.array([0, 1]), (k, 1)),
                     formats=[fmt] * len(sheets) if fmt else None)
        env.reset_battles(np.arange(n))
        env.refresh()
        searcher = search(env, seed + start) if search is not None else None
        done = np.zeros(n, bool)
        if watch is not None:
            watch.start(n, cell_of)

        def on_finish(st, done=done):
            fin = np.flatnonzero((st >= 0) & ~done)
            if len(fin):
                watch.on_done(env, fin, np.where(st[fin] == 0, 1.0, np.where(st[fin] == 1, 0.0, 0.5)))
        for _ in range(400):
            b = Batch(env, dev)
            with torch.inference_mode(), torch.autocast(dev.type, dtype=torch.float16, enabled=amp):
                s = policy.act(b.inputs(), b.bits, b.mega, b.min_switches, gen, 1.0)
                acts = s["actions"].cpu().numpy()
                if policy_b is not None:
                    acts[n:] = policy_b.act(b.inputs(), b.bits, b.mega, b.min_switches, gen, 1.0)["actions"].cpu().numpy()[n:]
            acts = side_actions(acts, n)
            if searcher is not None:
                for side in (0, 1):
                    searcher.choose(side, acts, (env.masks.min_switches[:, side] == 0) & ~done)
            if watch is not None:
                watch.on_step(env, acts)
            status = env.step(acts, on_finish if watch is not None else None)
            for i in np.flatnonzero((status >= 0) & ~done):
                done[i] = True
                c = cell_of[i]
                played[c] += 1
                points[c] += 1.0 if status[i] == 0 else (0.5 if status[i] == 2 else 0.0)
            if progress is not None:
                progress(int(played.sum()), len(jobs))
            if done.all():
                break
            env.refresh()
    return points, played

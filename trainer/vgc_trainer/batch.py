


from __future__ import annotations

import numpy as np
import torch

from .env import VecEnv


class Batch:


    def __init__(self, env: VecEnv, dev: torch.device):
        o0, o1 = env.obs
        m = env.masks
        bits = m.bits()

        def cat(a, b):
            return torch.from_numpy(np.concatenate([a, b])).to(dev, non_blocking=True)

        self.field = cat(o0.field, o1.field)
        self.mon_ids = cat(o0.mon_ids, o1.mon_ids)
        self.mon_features = cat(o0.mon_features, o1.mon_features)
        self.history = cat(o0.history, o1.history)
        self.bring = cat(env.bring[:, 0], env.bring[:, 1])
        self.bits = cat(bits[:, 0], bits[:, 1])

        codes = m.gimmick_codes()
        self.mega = cat(codes[:, 0], codes[:, 1])
        self.min_switches = cat(m.min_switches[:, 0], m.min_switches[:, 1])
        self.to_move = cat(m.to_move[:, 0], m.to_move[:, 1])

    def inputs(self, rows=None):
        x = (self.field, self.mon_ids, self.mon_features, self.history, self.bring)
        return x if rows is None else tuple(a[rows] for a in x)


def side_actions(acts: np.ndarray, n: int) -> np.ndarray:

    return np.stack([acts[:n], acts[n:]], axis=1)


def preview_inputs(env: VecEnv, pairs: np.ndarray) -> np.ndarray:

    a, b = env.sheet_ids[pairs[:, 0]], env.sheet_ids[pairs[:, 1]]

    fa, fb = (env.foe_sheet_ids[pairs[:, 0]], env.foe_sheet_ids[pairs[:, 1]]) if hasattr(env, "foe_sheet_ids") else (a, b)
    return np.stack([np.concatenate([a, fb], 1), np.concatenate([b, fa], 1)], 1)

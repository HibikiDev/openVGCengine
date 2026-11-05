




























from __future__ import annotations

import numpy as np

from .preview_advisor import _names, _top, equilibrium, head_orders, head_view, human_view
from .selfplay import play_fixed


class Options:



    def __init__(self, agent, mine: list[dict], theirs: list[dict], k: int, k_human: int | None = None, trim: bool = False,
                 fmt: str | None = None):
        self.fmt = fmt
        self.p_me, self.p_foe = head_view(agent, mine, theirs, fmt), head_view(agent, theirs, mine, fmt)
        self.h_me, self.h_foe = human_view(mine, theirs, fmt), human_view(theirs, mine, fmt)
        k_human = k if k_human is None else k_human
        self.top_me, self.top_foe = _top(self.p_me, k, self.h_me, k_human), _top(self.p_foe, k, self.h_foe, k_human)
        if trim:
            self.top_me, self.top_foe = self.top_me[:k], self.top_foe[:k]
        self.seq_me, self.seq_foe = head_orders(agent, mine, theirs, fmt), head_orders(agent, theirs, mine, fmt)
        self.n_head_foe = self.n_head_me = None


def _flip(seq) -> list[int]:

    s = [int(x) for x in seq]
    return [s[1], s[0], s[2], s[3]]


def play_cells(agent, mine: list[dict], theirs: list[dict], cells: list[tuple[list[int], list[int]]], games: int, seed: int,
               search=None, progress=None, fmt: str | None = None) -> np.ndarray:




    per = max(games // 8, 1)
    variants = [(fa, fb) for fa in (False, True) for fb in (False, True)]
    seat0 = [(_flip(a) if fa else list(a), _flip(b) if fb else list(b)) for a, b in cells for fa, fb in variants]
    half = len(seat0) * per
    pts, n = play_fixed(agent.policy, [mine, theirs], seat0, per, agent.dev, seed=seed, search=search,
                        progress=None if progress is None else lambda d, t: progress(d, 2 * half), fmt=fmt)
    pts2, n2 = play_fixed(agent.policy, [theirs, mine], [(b, a) for a, b in seat0], per, agent.dev, seed=seed + 500, search=search,
                          progress=None if progress is None else lambda d, t: progress(half + d, 2 * half), fmt=fmt)
    won, played = (pts + (n2 - pts2)).reshape(len(cells), 4).sum(1), (n + n2).reshape(len(cells), 4).sum(1)
    return won / np.maximum(played, 1)


def play_matrix(agent, mine: list[dict], theirs: list[dict], o: Options, games: int, seed: int) -> np.ndarray:

    cells = [(list(o.seq_me[a]), list(o.seq_foe[b])) for a in o.top_me for b in o.top_foe]
    return play_cells(agent, mine, theirs, cells, games, seed, fmt=o.fmt).reshape(len(o.top_me), len(o.top_foe))


def _fours(p: np.ndarray) -> list[int]:

    from .preview_advisor import _OUTCOME_SEQ
    best: dict = {}
    for oc in range(len(p)):
        four = frozenset(int(i) for i in _OUTCOME_SEQ[oc])
        if four not in best or p[oc] > p[best[four]]:
            best[four] = oc
    return sorted(best.values())


def screen_answers(agent, mine: list[dict], theirs: list[dict], o: Options, games: int, seed: int, keep: int) -> list[int]:


    outs = _fours(o.p_foe)
    mine_seq = list(o.seq_me[o.top_me[0]])
    v = play_cells(agent, mine, theirs, [(mine_seq, list(o.seq_foe[oc])) for oc in outs], games, seed, fmt=o.fmt)
    return [outs[i] for i in np.argsort(v)[:keep]]


def screen_counters(agent, mine: list[dict], theirs: list[dict], o: Options, games: int, seed: int, keep: int) -> list[int]:


    outs = _fours(o.p_me)
    cells = [(list(o.seq_me[a]), list(o.seq_foe[b])) for a in outs for b in o.top_foe]
    worst = play_cells(agent, mine, theirs, cells, games, seed, fmt=o.fmt).reshape(len(outs), len(o.top_foe)).min(1)
    return [outs[i] for i in np.argsort(-worst)[:keep]]


def derive(agent, mine: list[dict], theirs: list[dict], o: Options, m: np.ndarray, games: int, seed: int) -> dict:

    km, kf = m.shape
    se = float(np.sqrt(max(float((m * (1 - m)).max()), 1e-4) / max(games, 1)))
    worst = m.min(1)
    r_mix, c_mix, value = equilibrium(m)
    safest = int(np.argmax(worst))

    rec = int(max(range(km), key=lambda i: (round(float(r_mix[i]), 3), float(worst[i]), -i)))
    vs_h = None
    if o.h_foe is not None:
        hm = o.h_foe[o.top_foe] / max(float(o.h_foe[o.top_foe].sum()), 1e-9)
        vs_h = m @ hm
    opt = lambda sheet, seq, oc, p, h: {**_names(sheet, seq[oc]), "head_p": round(float(p[oc]), 3),
                                        "human_p": None if h is None else round(float(h[oc]), 3)}
    rec_names = _names(mine, o.seq_me[o.top_me[rec]])
    return {
        "games_per_cell": games, "k": km, "se": round(se, 3),
        "mine": [opt(mine, o.seq_me, oc, o.p_me, o.h_me) for oc in o.top_me],
        "theirs": [opt(theirs, o.seq_foe, oc, o.p_foe, o.h_foe) for oc in o.top_foe],
        "matrix": [[round(float(v), 3) for v in row] for row in m],
        "as_picked": round(float(m[0, 0]), 3),
        "best_answer": {"value": round(float(m[0].min()), 3), "col": int(m[0].argmin()),
                        "outside_heads": bool(o.n_head_foe is not None and int(m[0].argmin()) >= o.n_head_foe)},
        "screened": None if o.n_head_foe is None else {"mine_from": o.n_head_me, "theirs_from": o.n_head_foe},
        "safest": {"row": safest, "value": round(float(worst[safest]), 3)},
        "equilibrium": {"value": round(value, 3), "mine": [round(float(v), 3) for v in r_mix], "theirs": [round(float(v), 3) for v in c_mix]},
        "vs_human": None if vs_h is None else [round(float(v), 3) for v in vs_h],
        "human_coverage": None if o.h_foe is None else round(float(o.h_foe[o.top_foe].sum()), 3),
        "recommended": {"row": rec, **rec_names},
    }


def summary(agent, mine: list[dict], theirs: list[dict], k: int = 3, games: int = 256, seed: int = 0,
            screen: bool = True, screen_games: int = 64, screen_keep: int = 3, fmt: str | None = None) -> dict:



    o = Options(agent, mine, theirs, k, k, trim=True, fmt=fmt)
    if screen:
        o.n_head_foe, o.n_head_me = len(o.top_foe), len(o.top_me)
        extra = [oc for oc in screen_answers(agent, mine, theirs, o, screen_games, seed + 2000, screen_keep) if oc not in o.top_foe]
        o.top_foe = np.concatenate([o.top_foe, np.array(extra, dtype=o.top_foe.dtype)]) if extra else o.top_foe
        extra = [oc for oc in screen_counters(agent, mine, theirs, o, screen_games, seed + 3000, screen_keep) if oc not in o.top_me]
        o.top_me = np.concatenate([o.top_me, np.array(extra, dtype=o.top_me.dtype)]) if extra else o.top_me
    return derive(agent, mine, theirs, o, play_matrix(agent, mine, theirs, o, games, seed), games, seed)

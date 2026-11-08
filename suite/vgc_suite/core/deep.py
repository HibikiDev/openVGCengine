

















from __future__ import annotations

import math
from collections import Counter

import numpy as np

from .brings import Options, derive, play_cells, screen_options
from .h2h import make_searcher
from .matchup_stats import CellStats, MatchupStats
from .preview_advisor import equilibrium
from .validator import _field_brings

STAGE1, STAGE2 = 8, 32
SUPPORT = 0.05
NEAR = 0.03
HARD = 0.50


HEAVIEST = 4
SCALE = 100_000


def to_refine(values: list[float], shares: list[float] | None, ses: list[float] | None = None) -> set[int]:


    out = {i for i, v in enumerate(values) if v < HARD or (ses is not None and v - ses[i] < HARD)}
    if shares and len(set(shares)) > 1:
        out |= set(sorted(range(len(shares)), key=lambda i: -shares[i])[:HEAVIEST])
    return out


def support_cells(m: np.ndarray) -> list[tuple[int, int]]:


    r, c, _ = equilibrium(m)
    rows = set(np.flatnonzero(r >= SUPPORT).tolist()) | {int(np.argmax(m @ c))}
    cols = set(np.flatnonzero(c >= SUPPORT).tolist()) | {int(np.argmin(r @ m))}
    km, kf = m.shape
    return sorted({(i, j) for i in rows for j in range(kf)} | {(i, j) for i in range(km) for j in cols})


def near_rows(m: np.ndarray, near: float = NEAR) -> list[int]:

    _, c, _ = equilibrium(m)
    v = m @ c
    return [int(i) for i in np.argsort(-v) if v[i] >= v.max() - near]


def value_se(m: np.ndarray, n: np.ndarray, r: np.ndarray, c: np.ndarray) -> float:

    w = np.outer(r, c)
    p = np.clip(m, 0.05, 0.95)
    return float(math.sqrt(float((w ** 2 * p * (1 - p) / np.maximum(n, 1)).sum())))


class Matchup:


    def __init__(self, agent, mine: list[dict], theirs: list[dict], seed: int, fmt: str | None, k: int = 3):
        self.agent, self.mine, self.theirs, self.seed, self.fmt = agent, mine, theirs, seed, fmt
        self.o = screen_options(agent, mine, theirs, k, seed, fmt)
        self.shape = (len(self.o.top_me), len(self.o.top_foe))
        self.won, self.played = np.zeros(self.shape), np.zeros(self.shape, np.int64)
        self.stats = CellStats(mine, theirs, self.shape[0] * self.shape[1])

    def cells(self) -> list[tuple[int, int]]:
        return [(i, j) for i in range(self.shape[0]) for j in range(self.shape[1])]

    def matrix(self) -> np.ndarray:
        return self.won / np.maximum(self.played, 1)

    def play(self, cells: list[tuple[int, int]], games: int, seed: int, progress=None) -> None:

        if not cells or games <= 0:
            return
        o, a = self.o, self.agent
        pairs = [(list(o.seq_me[o.top_me[i]]), list(o.seq_foe[o.top_foe[j]])) for i, j in cells]
        self.stats.cell_map = [i * self.shape[1] + j for i, j in cells]
        won, played = play_cells(a, self.mine, self.theirs, pairs, games, seed, fmt=self.fmt, progress=progress, watch=self.stats, tally=True,
                                 search=lambda env, s: make_searcher(a, env, a.dev, s))
        for (i, j), w, n in zip(cells, won, played):
            self.won[i, j] += w
            self.played[i, j] += n

    def stage1(self, progress=None) -> float:
        self.play(self.cells(), STAGE1, self.seed, progress)
        v = equilibrium(self.matrix())[2]
        self.passes = [round(float(v), 3)]
        return v

    def stage2_cells(self) -> list[tuple[int, int]]:
        return [c for c in support_cells(self.matrix()) if self.played[c] < STAGE2]

    def stage2(self, progress=None, more=None) -> None:


        done = 0
        for r in range(2):
            cells = self.stage2_cells()
            n = len(cells) * (STAGE2 - STAGE1)
            if r and more is not None and n:
                more(n)
            self.play(cells, STAGE2 - STAGE1, self.seed + 50_000 * (r + 1), None if progress is None else (lambda d, t, o=done: progress(o + d, t)))
            done += n
            self.passes.append(round(float(equilibrium(self.matrix())[2]), 3))
        self.refined = True

    refined = False
    passes: list[float] = []

    def summary(self) -> dict:

        m = self.matrix()
        b = derive(self.agent, self.mine, self.theirs, self.o, m, int(self.played.max()), self.seed)
        r, c = np.array(b["equilibrium"]["mine"]), np.array(b["equilibrium"]["theirs"])
        near = near_rows(m)
        b.update({"deep": True, "refined": self.refined, "played": self.played.tolist(), "searched": [list(x) for x in self.cells()],
                  "passes": list(self.passes),
                  "value_se": round(value_se(m, self.played, r, c), 3), "near": near,
                  "mon_share": [round(sum(w for o, w in zip(b["mine"], r) if k in o["bring"]), 3) for k in range(len(self.mine))]})
        return b

    def weights(self) -> np.ndarray:

        r, c, _ = equilibrium(self.matrix())
        return np.outer(r, c).ravel()


def _pair(names: list[str], ks) -> str:
    return "/".join(names[i] for i in ks)


def run_deep(team: list[dict], field: list[tuple[str, list[dict]]], agent, model: str, seed: int = 0, team_id: str = "submitted",
             weights: list[float] | None = None, field_name: str | None = None, progress=None, fmt: str | None = None) -> dict:


    live = [(i, fid, fs) for i, (fid, fs) in enumerate(field) if not weights or weights[i] > 0]
    tot = float(sum(weights[i] for i, _, _ in live)) if weights else float(len(live))
    shares = [(weights[i] if weights else 1.0) / tot for i, _, _ in live]
    say = progress or (lambda *a: None)
    games = [0, 0]
    runs = []
    for x, (i, fid, fs) in enumerate(live):
        say(f"Options: {fid} ({x + 1} of {len(live)})", x, len(live), "options")
        runs.append(Matchup(agent, team, fs, seed + 101 * (i + 1), fmt))
    games[1] = sum(m.shape[0] * m.shape[1] * STAGE1 for m in runs)

    def tick(fid: str, base: int, label: str):
        return lambda d, t: say(f"{label}: {fid} ({base + d} of {games[1]} searched games)", base + d, games[1], label)
    values, ses = [], []
    for m, (_, fid, _) in zip(runs, live):
        values.append(m.stage1(tick(fid, games[0], "Searched matrix")))
        r, c, _ = equilibrium(m.matrix())
        ses.append(value_se(m.matrix(), m.played, r, c))
        games[0] += int(m.played.sum())
    refine = sorted(to_refine(values, shares, ses), key=lambda x: values[x])
    plan = {x: runs[x].stage2_cells() for x in refine}
    games[1] += sum(len(c) * (STAGE2 - STAGE1) for c in plan.values())
    for x in refine:
        before = int(runs[x].played.sum())
        runs[x].stage2(tick(live[x][1], games[0], "Refining"), more=lambda n: games.__setitem__(1, games[1] + n))
        games[0] += int(runs[x].played.sum()) - before

    names = [s.get("name") or s["species"] for s in team]
    teams = [team] + [fs for _, _, fs in live]
    stats = MatchupStats(1, teams)
    per_opp = []
    for x, (m, (_, fid, fs)) in enumerate(zip(runs, live)):
        b = m.summary()
        stats.absorb(x + 1, m.stats, m.weights(), int(SCALE * shares[x] * len(live)))
        d = stats.report(x + 1)
        if d:
            played = int(m.played.sum())
            d["games"] = played
            for key in ("leads", "pairings"):
                for row in d[key]:
                    row["games"] = round(row["share"] * played)
        v, se = b["equilibrium"]["value"], b["value_se"]
        rec = b["mine"][b["recommended"]["row"]]
        top_foe = b["theirs"][int(np.argmax(b["equilibrium"]["theirs"]))]
        leads = d["leads"][0] if d and d["leads"] else None
        per_opp.append({"id": fid, "species": [s["species"] for s in fs], "games": int(m.played.sum()), "score": v,
                        "share": round(shares[x], 3) if weights else None,
                        "ci": [round(max(0.0, v - 1.96 * se), 3), round(min(1.0, v + 1.96 * se), 3)],
                        "my_lead": f"{leads['mine'].replace(' + ', '/')} ({leads['share']:.0%})" if leads else "",
                        "their_lead": f"{leads['theirs'].replace(' + ', '/')} ({leads['share']:.0%})" if leads else "",
                        "my_bring": {"lead": rec["lead"], "back": rec["back"]}, "their_bring": {"lead": top_foe["lead"], "back": top_foe["back"]},
                        "detail": d, "unfinished": int(m.shape[0] * m.shape[1] * STAGE1 - min(int(m.played.sum()), m.shape[0] * m.shape[1] * STAGE1)),
                        "my_brought": b["mon_share"], "brings": b})
    per_opp.sort(key=lambda r: r["score"])
    w = np.array([s for s in shares])
    vals = np.array([r["score"] for r in sorted(per_opp, key=lambda r: [f for _, f, _ in live].index(r["id"]))])
    ses = np.array([r["brings"]["value_se"] for r in sorted(per_opp, key=lambda r: [f for _, f, _ in live].index(r["id"]))])
    p = float((w * vals).sum())
    se = float(math.sqrt(float((w ** 2 * ses ** 2).sum())))
    usage = stats.overall()
    mons = [{k: u[k] for k in ("mon", "brought", "led", "score_when_brought", "fainted", "mega", "moves", "switch", "decisions")} for u in usage]
    lead_w = Counter()
    for (_, a, _b), (n, _p) in stats.leads.items():
        lead_w[a] += n
    n_all = max(sum(lead_w.values()), 1e-9)
    total = sum(int(m.played.sum()) for m in runs)
    return {"team": {"id": team_id, "species": [s["species"] for s in team]}, "model": model, "games": total,
            "field": {"teams": len(field), "name": field_name, "weighted": bool(weights)},
            "overall": {"score": round(p, 3), "ci": [round(max(0.0, p - 1.96 * se), 3), round(min(1.0, p + 1.96 * se), 3)],
                        "elo_vs_field": round(400 * math.log10(max(p, 1e-3) / max(1 - p, 1e-3)), 0)},
            "search": {"deep": True, "games_per_team": round(total / max(len(runs), 1)), "unfinished": 0, "unfinished_by": {},
                       "refined": [live[x][1] for x in refine], "stage1": STAGE1, "stage2": STAGE2},
            "mons": mons, "leads": [{"lead": _pair(names, k), "share": round(c / n_all, 3)} for k, c in lead_w.most_common(4)],
            "worst": per_opp[:8], "best": per_opp[-8:][::-1], "opponents": per_opp,
            "caveats": ["the bot pilots both teams: this rates how well the bot plays them, not how a human would",
                        "each matchup's score is the searched matrix's both-adapt value: both sides choosing their four well",
                        "\"brought\" and \"led\" are shares of the recommended mix, not counts of what the bot chose",
                        "a cell of 8 games is a rough read: refined matchups rest on up to 32 a cell"],
            "brings": {"k": 3, "games_per_cell": STAGE2, **_field_brings(per_opp)}}

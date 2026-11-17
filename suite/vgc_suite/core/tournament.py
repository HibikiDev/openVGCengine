



















from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

MIN_RESISTANCE = 0.25




STRUCTURE = [(8, 3, 3, None, 0), (16, 4, 4, None, 2), (32, 6, 6, None, 4), (64, 7, 7, None, 6), (128, 9, 7, 13, 8),
             (256, 10, 8, 16, 8), (512, 11, 8, 16, 8), (1024, 12, 8, 16, 8), (2048, 13, 8, 16, 8), (4096, 14, 8, 16, 8),
             (8192, 15, 9, 19, 8)]
MAX_CUT = 16
MAX_GAMES = 5


@dataclass
class MatchResult:
    winner: int
    games: list[int]
    note: str = ""


@dataclass
class Player:
    pid: int
    team: int
    wins: int = 0
    losses: int = 0
    opps: list[int] = field(default_factory=list)
    byes: int = 0
    phase: int = 1
    finish: int | None = None

    @property
    def played(self) -> int:
        return self.wins + self.losses


def official_structure(players: int) -> dict:


    if players < 4:
        raise ValueError("Play! Pokémon's structures start at 4 players")
    for most, total, p1, thr, cut in STRUCTURE:
        if players <= most:
            return {"phase1_rounds": p1, "phase2_rounds": total - p1, "advance_points": thr, "cut": cut}
    raise ValueError(f"Play! Pokémon's table ends at {STRUCTURE[-1][0]} players")


def field_counts(weights: list[float], players: int) -> list[int]:


    w = np.asarray(weights, float)
    if players <= 0 or (w <= 0).all():
        raise ValueError("a field needs players and at least one team with a weight")
    w = np.where(w > 0, w, 0) / w[w > 0].sum()
    raw = w * players
    n = np.floor(raw).astype(int)
    for i in np.argsort(-(raw - n), kind="stable")[: players - int(n.sum())]:
        n[i] += 1
    if players >= int((w > 0).sum()):
        for i in np.flatnonzero((w > 0) & (n == 0)):
            n[int(np.argmax(n))] -= 1
            n[i] = 1
    return n.tolist()


class Tournament:
    def __init__(self, weights: list[float], players: int = 512, seed: int = 0, structure: dict | None = None,
                 drop_losses: int | None = None):




        st = structure or official_structure(players)
        self.rng = np.random.default_rng(seed)
        counts = field_counts(weights, players)
        teams = [t for t, c in enumerate(counts) for _ in range(c)]
        self.rng.shuffle(teams)
        self.players = [Player(pid, int(t)) for pid, t in enumerate(teams)]
        self.counts = counts
        self.phase1_rounds, self.phase2_rounds = st["phase1_rounds"], st["phase2_rounds"]
        self.advance_points, self.cut = st["advance_points"], st["cut"]
        self.drop_losses = drop_losses
        self.tiebreak = self.rng.permutation(len(teams))
        self.rounds: list[dict] = []
        self.bracket: list[dict] = []
        self.advanced: list[int] = []
        self.cut_seeds: list[int] = []


    def _win_pct(self, p: Player) -> float:
        return max(MIN_RESISTANCE, p.wins / p.played) if p.played else MIN_RESISTANCE

    def standings(self, pids: list[int] | None = None) -> list[dict]:


        P = self.players
        wp = [self._win_pct(p) for p in P]
        owp = [float(np.mean([wp[o] for o in p.opps])) if p.opps else 0.0 for p in P]
        oowp = [float(np.mean([owp[o] for o in p.opps])) if p.opps else 0.0 for p in P]
        ids = range(len(P)) if pids is None else pids
        rows = [{"pid": i, "team": P[i].team, "wins": P[i].wins, "losses": P[i].losses, "owp": round(owp[i], 4), "oowp": round(oowp[i], 4)}
                for i in ids]
        rows.sort(key=lambda r: (-r["wins"], -r["owp"], -r["oowp"], self.tiebreak[r["pid"]]))
        return rows


    def pair_swiss(self, pids: list[int]) -> list[tuple[int, int | None]]:

        P = self.players
        order = sorted(pids, key=lambda i: (-P[i].wins, self.rng.random()))
        out: list[tuple[int, int | None]] = []
        if len(order) % 2:
            ranked = [r["pid"] for r in self.standings(pids)]
            bye = next((i for i in reversed(ranked) if P[i].byes == 0), ranked[-1])
            order.remove(bye)
            out.append((bye, None))
        left = order
        while left:
            p = left.pop(0)
            k = next((j for j, q in enumerate(left) if q not in P[p].opps), 0)
            out.append((p, left.pop(k)))
        return out

    def _apply(self, pairs: list[tuple[int, int | None]], results: list[MatchResult], swiss: bool) -> list:
        P, rows, it = self.players, [], iter(results)
        for p, q in pairs:
            if q is None:
                P[p].wins += 1
                P[p].byes += 1
                rows.append((p, None, None))
                continue
            r = next(it)
            if swiss:
                w, l_ = (p, q) if r.winner == 0 else (q, p)
                P[w].wins += 1
                P[l_].losses += 1
                P[p].opps.append(q)
                P[q].opps.append(p)
            rows.append((p, q, r))
        return rows

    def _play(self, pairs, play_round, swiss: bool, phase: int, rnd: int, label: str, log: list) -> list:
        real = [(p, q) for p, q in pairs if q is not None]
        res = play_round([(self.players[p].team, self.players[q].team) for p, q in real], label) if real else []
        if len(res) != len(real):
            raise RuntimeError(f"{label}: {len(res)} results for {len(real)} matches")
        rows = self._apply(pairs, res, swiss)
        log.append({"phase": phase, "round": rnd, "label": label, "matches": rows})
        return rows


    @staticmethod
    def bracket_order(size: int) -> list[int]:

        order = [1]
        while len(order) < size:
            n = 2 * len(order) + 1
            order = [x for s in order for x in (s, n - s)]
        return order

    def run(self, play_round, progress=None) -> dict:

        P = self.players
        total = self.phase1_rounds + self.phase2_rounds + (math.ceil(math.log2(self.cut)) if self.cut else 0)
        k = 0

        def step(label):
            nonlocal k
            k += 1
            if progress is not None:
                progress(label, k, total)

        everyone = list(range(len(P)))
        live = lambda pids: [i for i in pids if self.drop_losses is None or P[i].losses < self.drop_losses]
        for r in range(1, self.phase1_rounds + 1):
            step(f"Swiss round {r}")
            self._play(self.pair_swiss(live(everyone)), play_round, True, 1, r, f"Swiss round {r}", self.rounds)
        two = bool(self.phase2_rounds) and self.advance_points is not None
        self.advanced = [i for i in everyone if 3 * P[i].wins >= self.advance_points] if two else everyone
        if len(self.advanced) < self.cut:
            self.advanced = [r["pid"] for r in self.standings()][: max(self.cut, len(self.advanced))]
        if two:
            for i in self.advanced:
                P[i].phase = 2
        for r in range(self.phase1_rounds + 1, self.phase1_rounds + self.phase2_rounds + 1):
            step(f"Swiss round {r}")
            self._play(self.pair_swiss(self.advanced), play_round, True, 2, r, f"Swiss round {r}", self.rounds)
        swiss = self.standings()

        pool = [r["pid"] for r in swiss if P[r["pid"]].phase == 2] if two else live([r["pid"] for r in swiss])
        if self.cut:
            bar = P[pool[min(self.cut, len(pool)) - 1]].wins
            self.cut_seeds = [i for i in pool if P[i].wins >= bar][:MAX_CUT]
        else:
            self.cut_seeds = []
        for i in self.cut_seeds:
            P[i].phase = 3

        place = len(self.cut_seeds) + 1
        for r in swiss:
            if P[r["pid"]].phase != 3:
                P[r["pid"]].finish = place
                place += 1
        if not self.cut_seeds:
            return self.report()
        size = 1 << math.ceil(math.log2(len(self.cut_seeds)))
        total = k + int(math.log2(size))

        slots: list[int | None] = [self.cut_seeds[s - 1] if s <= len(self.cut_seeds) else None for s in self.bracket_order(size)]
        while len(slots) > 1:
            n = len(slots)
            label = {2: "Final", 4: "Semifinals", 8: "Top 8", 16: "Top 16", 32: "Top 32", 64: "Top 64"}.get(n, f"Top {n}")
            step(label)
            pairs = [(slots[j], slots[j + 1]) for j in range(0, n, 2)]
            real = [(p, q) for p, q in pairs if p is not None and q is not None]
            res = iter(play_round([(P[p].team, P[q].team) for p, q in real], label) if real else [])
            rows, nxt = [], []
            for p, q in pairs:
                if p is None or q is None:
                    nxt.append(p if q is None else q)
                    if (p if q is None else q) is not None:
                        rows.append((p if q is None else q, None, None))
                    continue
                r = next(res)
                w, l_ = (p, q) if r.winner == 0 else (q, p)
                P[l_].finish = n // 2 + 1
                nxt.append(w)
                rows.append((p, q, r))
            self.bracket.append({"phase": 3, "round": label, "label": label, "matches": rows})
            slots = nxt
        if slots[0] is not None:
            P[slots[0]].finish = 1
        return self.report()


    def report(self, labels: list[str] | None = None) -> dict:


        P = self.players
        T = len(self.counts)
        labels = labels or [f"Team {t + 1}" for t in range(T)]
        won = np.zeros((T, T))
        met = np.zeros((T, T))
        games_won = np.zeros((T, T))
        games = np.zeros((T, T))
        for rnd in self.rounds + self.bracket:
            for p, q, r in rnd["matches"]:
                if q is None:
                    continue
                a, b = P[p].team, P[q].team
                w = (a, b) if r.winner == 0 else (b, a)
                won[w] += 1
                met[a, b] += 1
                met[b, a] += 1
                for g in r.games:
                    gw = (a, b) if g == 0 else (b, a)
                    games_won[gw] += 1
                    games[a, b] += 1
                    games[b, a] += 1
        teams = []
        for t in range(T):
            ps = [p for p in P if p.team == t]
            if not ps:
                continue
            sw, sl = sum(p.wins - p.byes for p in ps), sum(p.losses for p in ps)
            off = met[t].sum() - met[t, t]
            teams.append({"team": t, "label": labels[t], "players": len(ps), "share": round(len(ps) / len(P), 4),
                          "phase2": sum(p.phase >= 2 for p in ps), "cut": sum(p.phase == 3 for p in ps),
                          "best": min(p.finish for p in ps if p.finish is not None) if any(p.finish is not None for p in ps) else None,
                          "swiss_wr": round(sw / (sw + sl), 4) if sw + sl else None,
                          "wr_vs_others": round(float((won[t].sum() - won[t, t]) / off), 4) if off else None})
        matchups = [{"a": a, "b": b, "series": int(met[a, b]), "a_won": int(won[a, b]),
                     "games": int(games[a, b]), "a_games": int(games_won[a, b])}
                    for a in range(T) for b in range(a + 1, T) if met[a, b]]

        def rows(log):
            return [{"label": r["label"], "phase": r["phase"],
                     "matches": [[p, q, None if res is None else res.winner, None if res is None else res.games,
                                  None if res is None else res.note or None] for p, q, res in r["matches"]]} for r in log]
        top = self.standings()
        finals = sorted((p for p in P if p.phase == 3), key=lambda p: (p.finish, self.cut_seeds.index(p.pid)))
        return {"players": len(P), "teams": teams, "matchups": matchups,
                "config": {"phase1_rounds": self.phase1_rounds, "advance_points": self.advance_points, "phase2_rounds": self.phase2_rounds,
                           "cut": self.cut, "cut_size": len(self.cut_seeds), "drop_losses": self.drop_losses},
                "advanced": len(self.advanced),
                "winner": next(({"pid": p.pid, "team": p.team} for p in P if p.finish == 1), None),
                "top_cut": [{"pid": p.pid, "team": p.team, "seed": self.cut_seeds.index(p.pid) + 1, "finish": p.finish,
                             "record": f"{p.wins}-{p.losses}"} for p in finals],
                "standings": top[:64], "player_team": [p.team for p in P],
                "rounds": rows(self.rounds), "bracket": rows(self.bracket)}


class Pool:






    def __init__(self, teams: int):
        self.T = teams
        self.won = np.zeros((teams, teams), int)
        self.met = np.zeros((teams, teams), int)
        self.late_won = np.zeros(teams, int)
        self.late_met = np.zeros(teams, int)
        self.rows = [{"players": 0, "phase2": 0, "cut": 0, "finals": 0, "titles": 0} for _ in range(teams)]
        self.events: list[dict] = []
        self.two_phase = False

    def add(self, t: "Tournament") -> None:
        P = t.players
        for rnd in t.rounds + t.bracket:
            for p, q, r in rnd["matches"]:
                if q is None:
                    continue
                a, b = P[p].team, P[q].team
                w, l_ = (a, b) if r.winner == 0 else (b, a)
                self.won[w, l_] += 1
                self.met[a, b] += 1
                self.met[b, a] += 1
                if rnd["phase"] >= 2 and a != b:
                    self.late_won[w] += 1
                    self.late_met[a] += 1
                    self.late_met[b] += 1
        for pl in P:
            row = self.rows[pl.team]
            row["players"] += 1
            row["phase2"] += pl.phase >= 2
            row["cut"] += pl.phase == 3
            row["finals"] += pl.phase == 3 and pl.finish in (1, 2)
            row["titles"] += pl.finish == 1
        self.two_phase = self.two_phase or any(pl.phase == 2 for pl in P) or bool(t.phase2_rounds and t.advance_points is not None)
        first = next((pl for pl in P if pl.finish == 1), None)
        second = next((pl for pl in P if pl.finish == 2), None)
        self.events.append({"winner": first.team if first else None, "second": second.team if second else None,
                            "cut": [P[i].team for i in t.cut_seeds], "advanced": len(t.advanced) if t.phase2_rounds else None})

    def report(self, labels: list[str] | None = None) -> dict:
        labels = labels or [f"Team {t + 1}" for t in range(self.T)]
        players = sum(r["players"] for r in self.rows)
        cut = sum(r["cut"] for r in self.rows)
        teams = []
        for t, r in enumerate(self.rows):
            if not r["players"]:
                continue
            n = int(self.met[t].sum() - self.met[t, t])
            w = int(self.won[t].sum() - self.won[t, t])
            wr = w / n if n else None
            late = int(self.late_met[t])
            teams.append(dict(r, team=t, label=labels[t], share=round(r["players"] / players, 4),
                              series=n, wr=None if wr is None else round(wr, 4),
                              margin=None if wr is None else round(1.96 * math.sqrt(max(wr * (1 - wr), 1e-9) / n), 4),
                              late_series=late, late_wr=round(int(self.late_won[t]) / late, 4) if late else None,
                              cut_vs_share=round((r["cut"] / cut) / (r["players"] / players), 2) if cut else None))
        teams.sort(key=lambda x: (-(x["wr"] if x["wr"] is not None else -1), x["team"]))
        return {"events": self.events, "players": players, "cut": cut, "two_phase": self.two_phase, "teams": teams,
                "met": self.met.tolist(), "won": self.won.tolist()}



class SelfPlayRunner:




    def __init__(self, teams: list[list[dict]], ckpt, dev, seed: int = 0, fmt: str | None = None, progress=None, deep: bool = False):
        from vgc_trainer.pilot import Agent
        self.teams, self.dev, self.fmt, self.progress, self.deep = teams, dev, fmt, progress, deep
        self.pilot = Agent(str(ckpt), dev)
        self.human = None
        if self.pilot.preview is not None:
            from .positions import _human_preview
            self.human = _human_preview()
        self.seed = seed
        self.calls = 0
        self.games = 0

    def __call__(self, matches: list[tuple[int, int]], label: str = "") -> list[MatchResult]:
        import torch
        from vgc_trainer.amp import amp
        from vgc_trainer.batch import Batch, preview_inputs, side_actions
        from vgc_trainer.env import VecEnv
        from vgc_trainer.preview import sample_bring
        from vgc_trainer.showdown.sheets import lead_rule_v3
        from .h2h import _backs, _bring_outside

        self.calls += 1
        seed = self.seed * 1000 + self.calls
        rng = np.random.default_rng(seed + 11)
        m = len(matches)
        swap = rng.random(m) < 0.5
        seat = np.array([(b, a) if s else (a, b) for (a, b), s in zip(matches, swap)], np.int64).reshape(m, 2)
        live = np.ones(m, bool)
        g_no = np.ones(m, np.int64)
        wins = np.zeros((m, 2), np.int64)
        errors = np.zeros(m, np.int64)
        hist = [[[], []] for _ in range(m)]
        games: list[list[int]] = [[] for _ in range(m)]
        notes = [""] * m
        reset_queue: list[int] = []
        pilot, gen = self.pilot, torch.Generator(device=self.dev)
        gen.manual_seed(seed)

        def pair_fn(k):
            idx = reset_queue[:k] if reset_queue else list(range(k))
            del reset_queue[:k]
            return seat[idx]

        def bring_fn(idx, pairs):
            x = torch.from_numpy(preview_inputs(env, pairs).reshape(2 * len(idx), 12, -1)).to(self.dev)
            with torch.inference_mode():
                lead, back, _ = pilot.preview(x)
                lead, back = lead.float(), back.float()
                bring = sample_bring(lead, back, gen)[0].cpu().numpy().reshape(len(idx), 2, 4).astype(np.int64)
            bk, hl, hb = back.cpu().numpy(), None, None
            for j, i in enumerate(idx):
                for side in (0, 1):
                    if not live[i] or not hist[i][side]:
                        continue
                    kw = lead_rule_v3(hist[i][side], rng.random())
                    if "force_lead" in kw:
                        f = tuple(int(v) for v in kw["force_lead"])
                        bring[j, side] = [f[0], f[1], *_backs(bk[2 * j + side], f, rng)]
                    elif "avoid_leads" in kw:
                        if hl is None:
                            if self.human is not None:
                                with torch.inference_mode():
                                    a_, b_, _ = self.human(x.cpu())
                                hl, hb = a_.float().numpy(), b_.float().numpy()
                            else:
                                hl, hb = lead.cpu().numpy(), bk
                        got = _bring_outside(hl[2 * j + side], hb[2 * j + side], [set(v) for v in kw["avoid_leads"]], rng)
                        if got is not None:
                            bring[j, side] = got
            return bring


        env = VecEnv(m, self.teams, seed=seed, formats=[self.fmt] * len(self.teams) if self.fmt else None)
        env.pair_fn, env.bring_fn = pair_fn, bring_fn
        reset_queue.extend(range(m))
        env.reset_battles(np.arange(m))
        env.refresh()
        searcher = None
        if self.deep:
            from .h2h import make_searcher
            searcher = make_searcher(pilot, env, self.dev, seed)

        def on_finish(status):
            for i in np.flatnonzero((status >= 0) | (status == -3)):
                reset_queue.append(int(i))
                if not live[i]:
                    continue
                st = int(status[i])
                if st in (0, 1):
                    wins[i, st] += 1
                    games[i].append(st)
                    self.games += 1
                    for side in (0, 1):
                        hist[i][side].append({"lead": [int(v) for v in env.bring[i, side, :2]], "won": st == side, "chaos": 0.0})
                    g_no[i] += 1
                elif st == -3:
                    errors[i] += 1

                if wins[i].max() >= 2:
                    live[i] = False
                elif g_no[i] > MAX_GAMES or errors[i] >= 3:
                    live[i] = False
                    notes[i] = "coin"
                    if wins[i, 0] == wins[i, 1]:
                        wins[i, int(rng.integers(2))] += 1

        t0 = time.time()
        while live.any():
            batch = Batch(env, self.dev)
            with torch.inference_mode(), amp(self.dev):
                s = pilot.policy.act(batch.inputs(), batch.bits, batch.mega, batch.min_switches, gen, 1.0)
            actions = side_actions(s["actions"].cpu().numpy(), m)
            if searcher is not None:
                for side in (0, 1):
                    searcher.choose(side, actions, (env.masks.min_switches[:, side] == 0) & live)
            env.step(actions, on_finish)
            env.refresh()
            if self.progress is not None:
                self.progress(label, int((~live).sum()), m, time.time() - t0)
        out = []
        for j in range(m):
            seat_w = int(np.argmax(wins[j]))
            to_match = (lambda s_, j=j: s_ if not swap[j] else 1 - s_)
            out.append(MatchResult(to_match(seat_w), [to_match(g) for g in games[j]], notes[j]))
        return out


def coin_runner(strength: list[float], seed: int = 0):

    rng = np.random.default_rng(seed)

    def play(matches, label=""):
        out = []
        for a, b in matches:
            p = 1 / (1 + 10 ** ((strength[b] - strength[a]) / 400))
            g: list[int] = []
            while g.count(0) < 2 and g.count(1) < 2:
                g.append(0 if rng.random() < p else 1)
            out.append(MatchResult(0 if g.count(0) == 2 else 1, g))
        return out
    return play

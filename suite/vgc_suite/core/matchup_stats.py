

















from __future__ import annotations

import re
from collections import defaultdict

import numpy as np

ACTIVE_A, FAINTED = 2, 4
SWITCH_BASE, PASS_ACTION = 16, 20
CATS = 5
TGT = 8
EV_MOVE, EV_FAINT = 1, 3
MEGA_STONE = re.compile(r"ite( [XY])?$")


class MatchupStats:




    def __init__(self, n: int, teams: list[list[dict]], focus: int = 0):
        nt = len(teams)
        self.teams, self.focus = teams, focus

        self.run = np.zeros((n, 2, 6, CATS), np.int32)
        self.run_tgt = np.zeros((n, 2, 6, 4, TGT), np.int32)
        self.run_mega = np.zeros((n, 2, 6), bool)
        self.run_ko = np.zeros((n, 2, 6, 6), np.int32)
        self.run_own = np.zeros((n, 2, 6, 2), np.int32)
        self.credited = np.zeros((n, 2, 6), bool)
        self.prev_faint = np.zeros((n, 2, 6), bool)
        self.seed = np.full(n, -1, np.int64)
        self.choice = np.zeros((nt, 2, 6, CATS), np.int64)
        self.used = np.zeros((nt, 2, 6, CATS), np.int64)
        self.tgt = np.zeros((nt, 2, 6, 4, TGT), np.int64)
        self.mega = np.zeros((nt, 2, 6), np.int64)
        self.brought = np.zeros((nt, 2, 6), np.int64)
        self.led = np.zeros((nt, 2, 6), np.int64)
        self.fainted = np.zeros((nt, 2, 6), np.int64)
        self.ko = np.zeros((nt, 2, 6, 6), np.int64)
        self.own_faint = np.zeros((nt, 2, 6, 2), np.int64)
        self.points_brought = np.zeros((nt, 2, 6))
        self.games = np.zeros(nt, np.int64)
        self.points = np.zeros(nt)
        self.turns = np.zeros(nt, np.int64)
        self.leads: dict = defaultdict(lambda: [0, 0.0])
        self.pairings: dict = defaultdict(lambda: [0, 0.0])

    def on_step(self, env, actions: np.ndarray) -> None:
        new = env.seeds != self.seed
        if new.any():
            for a in (self.run, self.run_tgt, self.run_ko, self.run_own):
                a[new] = 0
            for a in (self.run_mega, self.credited, self.prev_faint):
                a[new] = False
            self.seed[new] = env.seeds[new]
        bits = env.masks.bits()
        for side in (0, 1):
            feats = env.obs[side].mon_features
            for slot in (0, 1):
                flag = feats[:, :6, ACTIVE_A + slot]
                act = actions[:, side, slot, 0]
                live = env.masks.to_move[:, side] & (bits[:, side, slot].sum(-1) > 1) & (flag.max(-1) > 0.5) & (act < PASS_ACTION)
                i = np.flatnonzero(live)
                if len(i) == 0:
                    continue
                k = flag[i].argmax(-1)
                a = act[i]
                np.add.at(self.run, (i, side, k, np.where(a < SWITCH_BASE, a // 4, 4)), 1)
                mg = (actions[i, side, slot, 1] != 0) & (a < SWITCH_BASE)
                self.run_mega[i[mg], side, k[mg]] = True
                mv = a < SWITCH_BASE
                if mv.any():
                    im, km, t = i[mv], k[mv], a[mv] % 4
                    foe = np.stack([feats[im, 6:, ACTIVE_A], feats[im, 6:, ACTIVE_A + 1]], 1)
                    tf = np.minimum(t, 1)
                    seat = foe[np.arange(len(im)), tf]
                    to = np.where(t == 2, 6, np.where((t < 2) & (seat.max(-1) > 0.5), seat.argmax(-1), 7))
                    np.add.at(self.run_tgt, (im, side, km, a[mv] // 4, to), 1)

        f = env.obs[0].mon_features[:, :, FAINTED] > 0.5
        now = np.stack([f[:, :6], f[:, 6:]], 1)
        for i in np.flatnonzero((now & ~self.prev_faint).any((1, 2))):
            self._credit(env, int(i), env.pool.inspect(int(i))["events"], now[i] & ~self.prev_faint[i])
        self.prev_faint = now

    def _credit(self, env, i: int, events, victims: np.ndarray) -> None:

        for side, k in zip(*np.nonzero(victims & ~self.credited[i])):
            br = list(env.bring[i, side])
            if k not in br:
                continue
            packed = side * 4 + br.index(k)
            at = [e for e, ev in enumerate(events) if ev[0] == EV_FAINT and ev[1] == packed]
            mover = next((events[e][1] for e in range(at[-1] - 1, -1, -1) if events[e][0] == EV_MOVE and events[e][4] == 1), None) \
                if at else None
            self.credited[i, side, k] = True
            if mover is None:
                self.run_own[i, side, k, 1] += 1
            elif mover // 4 != side:
                self.run_ko[i, mover // 4, int(env.bring[i, mover // 4, mover % 4]), k] += 1
            else:
                self.run_own[i, side, k, 0] += 1

    def on_done(self, env, done: np.ndarray, result: np.ndarray) -> None:
        for j, i in enumerate(done):
            a, b = env.pairs[i]
            if a == b:
                continue
            fs = 0 if a == self.focus else 1
            opp = int(env.pairs[i, 1 - fs])
            pts = float(result[j] if fs == 0 else 1 - result[j])
            st = env.pool.inspect(int(i))
            self.games[opp] += 1
            self.points[opp] += pts
            self.turns[opp] += int(st["turn"])
            final = np.zeros((2, 6), bool)
            for side in (0, 1):
                for x, m in enumerate(st["sides"][side]["mons"][: len(env.bring[i, side])]):
                    final[side, env.bring[i, side, x]] = m["hp"] == 0
            self._credit(env, int(i), st["events"], final)
            for side in (0, 1):
                role = 0 if side == fs else 1
                br = env.bring[i, side]
                self.brought[opp, role, br] += 1
                self.led[opp, role, br[:2]] += 1
                self.points_brought[opp, role, br] += pts
                self.fainted[opp, role] += final[side]
                self.choice[opp, role] += self.run[i, side]
                self.used[opp, role] += self.run[i, side] > 0
                self.tgt[opp, role] += self.run_tgt[i, side]
                self.mega[opp, role] += self.run_mega[i, side]
                self.ko[opp, role] += self.run_ko[i, side]
                self.own_faint[opp, role] += self.run_own[i, side]
            rec = self.leads[(opp, tuple(sorted(env.bring[i, fs, :2])), tuple(sorted(env.bring[i, 1 - fs, :2])))]
            rec[0] += 1
            rec[1] += pts
            rec = self.pairings[(opp, tuple(sorted(env.bring[i, fs])), tuple(sorted(env.bring[i, 1 - fs])))]
            rec[0] += 1
            rec[1] += pts

    def _mons(self, sets: list[dict], choice, used, mega, brought, led, fainted, points_brought, games: int, tgt=None, ko=None,
              own=None, foe: list[dict] | None = None) -> list[dict]:

        name = lambda s: s.get("name") or s["species"]
        out = []
        for k, s in enumerate(sets):
            nb, dec = int(brought[k]), int(choice[k].sum())
            names = list(s["moves"][:4]) + ["switch"]
            moves = []
            for c in range(len(names) - 1):
                mv = {"move": names[c], "share": round(float(choice[k, c]) / max(dec, 1), 3), "games": round(float(used[k, c]) / max(nb, 1), 3)}
                if tgt is not None and foe is not None and tgt[k, c].sum():
                    labels = [name(x) for x in foe] + ["ally", "no target"]
                    tot = float(tgt[k, c].sum())
                    mv["targets"] = [{"to": labels[t], "share": round(float(tgt[k, c, t]) / tot, 3)}
                                     for t in np.argsort(-tgt[k, c]) if tgt[k, c, t] / tot >= 0.05]
                moves.append(mv)
            stone = MEGA_STONE.search(s.get("item") or "") and (s.get("item") or "") != "Eviolite"
            row = {"mon": name(s), "brought": round(nb / max(games, 1), 3), "led": round(int(led[k]) / max(games, 1), 3),
                   "score_when_brought": round(float(points_brought[k]) / nb, 3) if nb else None,
                   "fainted": round(int(fainted[k]) / nb, 3) if nb else None,
                   "mega": round(int(mega[k]) / nb, 3) if nb and (stone or mega[k]) else None,
                   "decisions": dec, "moves": sorted(moves, key=lambda m: -m["share"]),
                   "switch": round(float(choice[k, 4]) / max(dec, 1), 3)}
            if ko is not None and nb:
                row["kos"] = round(float(ko[k].sum()) / nb, 2)
                if foe is not None:
                    row["ko_list"] = [{"victim": name(foe[v]), "per_game": round(float(ko[k, v]) / nb, 2)}
                                      for v in np.argsort(-ko[k]) if ko[k, v] / nb >= 0.05]
            if own is not None and nb:
                row["own_faint"] = round(float(own[k, 0]) / nb, 2)
            out.append(row)
        return out

    def report(self, opp: int, names_of=lambda s: s.get("name") or s["species"], top_leads: int = 6) -> dict | None:


        g = int(self.games[opp])
        if g == 0:
            return None
        mine, theirs = self.teams[self.focus], self.teams[opp]
        sides = []
        for role, team, other in ((0, mine, theirs), (1, theirs, mine)):
            sides.append(self._mons(team, self.choice[opp, role], self.used[opp, role], self.mega[opp, role],
                                    self.brought[opp, role], self.led[opp, role], self.fainted[opp, role],
                                    self.points_brought[opp, role], g, tgt=self.tgt[opp, role], ko=self.ko[opp, role],
                                    own=self.own_faint[opp, role], foe=other))
        names = lambda team, ks: " + ".join(names_of(team[x]) for x in ks)
        top = lambda d: sorted(((k, v) for k, v in d.items() if k[0] == opp), key=lambda kv: -kv[1][0])[:top_leads]
        return {"games": g, "score": round(float(self.points[opp]) / g, 3), "turns": round(float(self.turns[opp]) / g, 1),
                "mine": sides[0], "theirs": sides[1],
                "leads": [{"mine": names(mine, a), "theirs": names(theirs, b), "games": n, "share": round(n / g, 3),
                           "score": round(p / n, 3)} for (_, a, b), (n, p) in top(self.leads)],
                "pairings": [{"mine": names(mine, a), "theirs": names(theirs, b), "games": n, "share": round(n / g, 3),
                              "score": round(p / n, 3)} for (_, a, b), (n, p) in top(self.pairings)]}

    def overall(self) -> list[dict]:

        s = lambda a: a[:, 0].sum(0)
        return self._mons(self.teams[self.focus], s(self.choice), s(self.used), s(self.mega), s(self.brought), s(self.led),
                          s(self.fainted), s(self.points_brought), int(self.games.sum()), ko=s(self.ko), own=s(self.own_faint))

    def brought_by_team(self) -> np.ndarray:

        return self.brought[:, 0] / np.maximum(self.games, 1)[:, None]

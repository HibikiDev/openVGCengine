





















from __future__ import annotations

import numpy as np
import vgc_engine as ve

SERIES_VERSION = 1
N_GLOBAL = 7
N_TOKEN = 12
SERIES_FEATURES = N_GLOBAL + ve.MON_TOKENS * N_TOKEN


TURN = 14
IN_BATTLE, ACTIVE_A, ACTIVE_B = 1, 2, 3
MOVES = 3
EV_MOVE = 1


def _pack(h: np.ndarray) -> np.ndarray:

    h = h.astype(np.int64)

    return ((((h[..., 0] * 16 + h[..., 1] + 1) * 16 + h[..., 2] + 1) * 4096 + h[..., 3]) << 24) + (h[..., 4] + (1 << 23))


def new_events(prev: np.ndarray, cur: np.ndarray) -> np.ndarray:


    a = _pack(prev) if prev.ndim == 3 else prev
    b = _pack(cur) if cur.ndim == 3 else cur
    r, h = b.shape
    shift = np.full(r, h, np.int64)
    for m in range(h - 1, -1, -1):
        ok = np.all(b[:, : h - m] == a[:, m:], axis=1)
        shift[ok] = m
    return np.arange(h)[None, :] >= (h - shift)[:, None]


EMPTY_KEY = int(_pack(np.zeros((1, 1, ve.EVENT_FIELDS), np.int32))[0, 0])


class SeriesState:




    def __init__(self, n: int, sides: int = 2, max_games: int = 3):
        assert ve.MOVE_VOCAB < 4096
        self.n, self.sides, self.max_games = n, sides, max_games
        t, s = ve.MON_TOKENS, (n, sides)
        self.game = np.ones(n, np.int64)
        self.wins = np.zeros(s, np.int64)
        self.losses = np.zeros(s, np.int64)
        self.res = np.zeros(s + (2,), np.float32)
        self.prev_len = np.zeros(n, np.float32)
        self.led = np.zeros(s + (2, t), np.float32)
        self.appeared = np.zeros(s + (2, t), np.float32)
        self.moves = np.zeros(s + (t, 4), np.float32)
        self.turn1 = np.zeros(s + (t, 4), np.float32)

        self.cur_seen = np.zeros(s, bool)
        self.cur_led = np.zeros(s + (t,), np.float32)
        self.cur_app = np.zeros(s + (t,), np.float32)
        self.cur_moves = np.zeros(s + (t, 4), np.float32)
        self.cur_turn1 = np.zeros(s + (t, 4), np.float32)
        self.cur_turn = np.zeros(n, np.float32)
        self.hist = np.full(s + (ve.HISTORY_LEN,), EMPTY_KEY, np.int64)
        self.out = np.zeros(s + (SERIES_FEATURES,), np.float32)

    def observe(self, side: int, field: np.ndarray, mon_ids: np.ndarray, mon_features: np.ndarray, history: np.ndarray,
                rows: np.ndarray) -> None:

        if len(rows) == 0:
            return
        turn = np.rint(field[:, TURN][rows] * 30.0)
        self.cur_turn[rows] = np.maximum(self.cur_turn[rows], turn)
        first = rows[~self.cur_seen[rows, side]]
        if len(first):
            self.cur_led[first, side] = ((mon_features[:, :, ACTIVE_A][first] > 0.5) | (mon_features[:, :, ACTIVE_B][first] > 0.5))
            self.cur_seen[first, side] = True
        self.cur_app[rows, side] = mon_features[:, :, IN_BATTLE][rows] > 0.5
        h = history[rows]
        key = _pack(h)
        is_move = (h[..., 0] == EV_MOVE) & (h[..., 4] == 1) & (h[..., 1] >= 0)
        new = new_events(self.hist[rows, side], key) & is_move
        self.hist[rows, side] = key
        rr, ee = np.nonzero(new)
        if len(rr):
            actor = h[rr, ee, 1]
            move = h[rr, ee, 3]
            hit = mon_ids[rows[rr], actor, MOVES : MOVES + 4] == move[:, None]
            ok = hit.any(1)
            r_ok, a_ok, j = rows[rr[ok]], actor[ok], hit[ok].argmax(1)
            t, flat = ve.MON_TOKENS, self.cur_moves[:, side].reshape(self.n, -1)
            flat += np.bincount(r_ok * (t * 4) + a_ok * 4 + j, minlength=self.n * t * 4).reshape(self.n, t * 4).astype(np.float32)
            self.cur_moves[:, side] = flat.reshape(self.n, t, 4)
            t1 = turn[rr[ok]] <= 2
            self.cur_turn1[r_ok[t1], side, a_ok[t1], j[t1]] = 1.0

    def end_game(self, rows: np.ndarray, winner: np.ndarray) -> np.ndarray:


        rows = np.asarray(rows)
        w = np.asarray(winner, np.int64)
        decided = (w == 0) | (w == 1)
        res = np.where(w[:, None] == np.arange(self.sides)[None, :], 1.0, np.where(decided[:, None], -1.0, 0.0)).astype(np.float32)
        self.wins[rows] += res > 0
        self.losses[rows] += res < 0
        self.res[rows] = np.stack([res, self.res[rows][..., 0]], -1)
        self.led[rows] = np.stack([self.cur_led[rows], self.led[rows][:, :, 0]], 2)
        self.appeared[rows] = np.stack([self.cur_app[rows], self.appeared[rows][:, :, 0]], 2)
        self.moves[rows] += self.cur_moves[rows]
        self.turn1[rows] = self.cur_turn1[rows]
        self.prev_len[rows] = np.minimum(self.cur_turn[rows], 30.0) / 30.0
        over = (self.wins[rows, 0] >= 2) | (self.losses[rows, 0] >= 2)
        cont = decided & ~over & (self.game[rows] < self.max_games)
        self.game[rows[cont]] += 1
        self._clear_series(rows[~cont])
        self._clear_game(rows)
        self._write(rows)
        return cont

    def reset_rows(self, rows: np.ndarray) -> None:

        rows = np.asarray(rows)
        self._clear_series(rows)
        self._clear_game(rows)
        self._write(rows)

    def features(self) -> np.ndarray:

        return self.out


    def _clear_game(self, rows: np.ndarray) -> None:
        for a in (self.cur_seen, self.cur_led, self.cur_app, self.cur_moves, self.cur_turn1, self.cur_turn):
            a[rows] = 0
        self.hist[rows] = EMPTY_KEY

    def _clear_series(self, rows: np.ndarray) -> None:
        self.game[rows] = 1
        for a in (self.wins, self.losses, self.res, self.led, self.appeared, self.moves, self.turn1, self.prev_len):
            a[rows] = 0

    def _write(self, rows: np.ndarray) -> None:
        self.out[rows] = 0.0
        rows = rows[self.game[rows] > 1]
        if len(rows) == 0:
            return
        g = self.game[rows][:, None].repeat(self.sides, 1)
        glob = np.stack([(g == 2), (g == 3), self.wins[rows] / 2.0, self.losses[rows] / 2.0, self.res[rows][..., 0], self.res[rows][..., 1],
                         self.prev_len[rows][:, None].repeat(self.sides, 1)], -1)

        tok = np.concatenate([self.led[rows].transpose(0, 1, 3, 2), self.appeared[rows].transpose(0, 1, 3, 2),
                              np.minimum(self.moves[rows], 3.0) / 3.0, self.turn1[rows]], -1)
        self.out[rows, :, :N_GLOBAL] = glob
        self.out[rows, :, N_GLOBAL:] = tok.reshape(len(rows), self.sides, -1)

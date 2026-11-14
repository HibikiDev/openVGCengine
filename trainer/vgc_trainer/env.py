






from __future__ import annotations

import contextvars
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import vgc_engine as ve

from .formats import is_champions, training_format

REPO = Path(__file__).resolve().parents[2]
DEFAULT_TEAMS = REPO / "tools" / "corpus" / "out" / "teams-sets.json"

HOLDOUT_IDS = REPO / "trainer" / "holdout_teams.json"


HOLDOUT_TEAMS = 40


_GENDER_RATIOS: dict[str, tuple[str, float]] | None = None


def with_genders(sets: list[dict], rng: np.random.Generator) -> list[dict]:


    global _GENDER_RATIOS
    if _GENDER_RATIOS is None:
        species = json.loads((REPO / "tools/gen-data/out/species.json").read_text(encoding="utf8"))
        _GENDER_RATIOS = {s["id"]: (s.get("gender", ""), float((s.get("genderRatio") or {}).get("M", 0.5))) for s in species}
    out = []
    for s in sets:
        if s.get("gender"):
            out.append(s)
            continue
        fixed, male = _GENDER_RATIOS.get(re.sub(r"[^a-z0-9]", "", s["species"].lower()), ("", 0.5))
        out.append(dict(s, gender=fixed or ("M" if rng.random() < male else "F")))
    return out


def load_teams(path: Path = DEFAULT_TEAMS, split: str = "all") -> list[list[dict]]:




    return [e["sets"] for e in load_entries(path, split)]


def load_team_ids(path: Path = DEFAULT_TEAMS, split: str = "all") -> list[str]:

    return [e["id"] for e in load_entries(path, split)]



def load_team_file(path: Path) -> list[dict]:



    doc = json.loads(Path(path).read_text(encoding="utf8"))
    entries = doc["teams"]


    fmt = training_format(doc.get("format"))
    probe = ve.BattlePool(1)
    usable = []
    for e in entries:
        try:
            if fmt is None:
                probe.register_team(e["sets"])
            else:
                probe.register_team(e["sets"], fmt)
                e = dict(e, format=fmt)
            usable.append(e)
        except Exception:
            pass
    if len(usable) < len(entries):
        print(f"{path}: {len(entries) - len(usable)} of {len(entries)} teams left out (not loadable by this engine build)")
    return usable


def load_entries(path: Path = DEFAULT_TEAMS, split: str = "all") -> list[dict]:
    entries = json.loads(Path(path).read_text(encoding="utf8"))["teams"]
    if split == "all":
        return entries
    if HOLDOUT_IDS.exists():
        ids = set(json.loads(HOLDOUT_IDS.read_text(encoding="utf8")))
        held = {i for i, t in enumerate(entries) if t["id"] in ids}
    else:
        held = set(np.random.default_rng(20261006).permutation(len(entries))[:HOLDOUT_TEAMS].tolist())
    if split == "holdout":
        return [t for i, t in enumerate(entries) if i in held]
    if split == "train":
        return [t for i, t in enumerate(entries) if i not in held]
    raise ValueError(f"unknown split {split!r}")


@dataclass
class Observation:


    field: np.ndarray
    mon_ids: np.ndarray
    mon_features: np.ndarray
    history: np.ndarray

    @staticmethod
    def empty(n: int) -> "Observation":
        return Observation(
            field=np.zeros((n, ve.FIELD_FEATURES), np.float32),
            mon_ids=np.zeros((n, ve.MON_TOKENS, ve.MON_IDS), np.int32),
            mon_features=np.zeros((n, ve.MON_TOKENS, ve.MON_FEATURES), np.float32),
            history=np.zeros((n, ve.HISTORY_LEN, ve.EVENT_FIELDS), np.int32),
        )


@dataclass
class Masks:


    actions: np.ndarray
    mega: np.ndarray
    to_move: np.ndarray
    min_switches: np.ndarray


    gimmick: np.ndarray
    forced: np.ndarray
    kind: np.ndarray

    @staticmethod
    def empty(n: int) -> "Masks":
        return Masks(
            actions=np.zeros((n, 2, 2), np.uint32),
            mega=np.zeros((n, 2, 2), bool),
            to_move=np.zeros((n, 2), bool),
            min_switches=np.zeros((n, 2), np.uint8),
            gimmick=np.zeros((n, 2, 2), np.uint32),
            forced=np.zeros((n, 2, 2), np.uint32),
            kind=np.zeros((n, 2, 2), np.uint8),
        )

    def bits(self) -> np.ndarray:

        return ((self.actions[..., None] >> np.arange(ve.SLOT_ACTIONS, dtype=np.uint32)) & 1).astype(bool)

    def bits_at(self, rows, side: int) -> np.ndarray:


        return ((self.actions[rows, side][..., None] >> np.arange(ve.SLOT_ACTIONS, dtype=np.uint32)) & 1).astype(bool)

    def gimmick_codes_at(self, rows, side: int) -> np.ndarray:

        sh = np.arange(ve.SLOT_ACTIONS, dtype=np.uint32)
        g = ((self.gimmick[rows, side][..., None] >> sh) & 1).astype(bool)
        f = ((self.forced[rows, side][..., None] >> sh) & 1).astype(bool)
        state = np.where(f, 2, np.where(g, 1, 0)).astype(np.int8)
        return np.where(state > 0, state + 4 * self.kind[rows, side][..., None].astype(np.int8), 0).astype(np.int8)

    def gimmick_codes(self) -> np.ndarray:


        sh = np.arange(ve.SLOT_ACTIONS, dtype=np.uint32)
        g = ((self.gimmick[..., None] >> sh) & 1).astype(bool)
        f = ((self.forced[..., None] >> sh) & 1).astype(bool)
        state = np.where(f, 2, np.where(g, 1, 0)).astype(np.int8)
        return np.where(state > 0, state + 4 * self.kind[..., None].astype(np.int8), 0).astype(np.int8)

    def fill_gimmicks_legacy(self) -> None:


        moves = np.uint32((1 << ve.SWITCH_BASE) - 1)
        self.gimmick[:] = np.where(self.mega, self.actions & moves, 0)
        self.forced[:] = 0
        self.kind[:] = self.mega.astype(np.uint8)


_GIMMICK_MASKS = True


def read_masks(pool, m: Masks) -> None:


    global _GIMMICK_MASKS
    if _GIMMICK_MASKS:
        try:
            pool.masks(m.actions, m.mega, m.to_move, m.min_switches, m.gimmick, m.forced, m.kind)
            return
        except TypeError:
            _GIMMICK_MASKS = False
    pool.masks(m.actions, m.mega, m.to_move, m.min_switches)
    m.fill_gimmicks_legacy()





SHEETS_OPEN = contextvars.ContextVar("sheets_open", default=False)

class VecEnv:





    def __init__(self, n: int, teams: list[list[dict]] | None = None, seed: int = 0, bring_fn=None, pair_fn=None,
                 formats: list[str | None] | None = None, open_sheets: bool | None = None):





        open_sheets = SHEETS_OPEN.get() if open_sheets is None else open_sheets
        self.n = n
        self.open_sheets = open_sheets
        self.pool = ve.BattlePool(n)
        self.rng = np.random.default_rng(seed)
        self.teams = teams if teams is not None else load_teams()
        self.formats = formats if formats is not None else [None] * len(self.teams)

        grng = np.random.default_rng(seed + 0x6E6)
        self.team_ids = [self.pool.register_team(with_genders(t, grng)) if f is None else self.pool.register_team(with_genders(t, grng), f)
                         for t, f in zip(self.teams, self.formats)]


        self.sheet_ids = np.zeros((len(self.team_ids), ve.ROSTER_SIZE, ve.MON_IDS), np.int32)
        self.foe_sheet_ids = np.zeros_like(self.sheet_ids)
        for k, tid in enumerate(self.team_ids):
            self.pool.sheet_ids(tid, self.sheet_ids[k])
            if is_champions(self.formats[k]):
                self.foe_sheet_ids[k] = self.sheet_ids[k]
            else:
                self.pool.sheet_ids(tid, self.foe_sheet_ids[k], True, *((True,) if open_sheets else ()))
        self.bring_fn = bring_fn
        self.pair_fn = pair_fn
        self.pairs = np.zeros((n, 2), np.int64)
        self.seeds = np.zeros(n, np.int64)
        self.bring = np.zeros((n, 2, ve.BROUGHT_SIZE), np.int64)
        self.obs = [Observation.empty(n), Observation.empty(n)]
        self.masks = Masks.empty(n)
        self.status = np.zeros(n, np.int8)
        self.games_finished = 0
        self.engine_errors: list[str] = []
        self.reset_battles(np.arange(n))

    def choose_bring(self, k: int) -> np.ndarray:

        return np.argsort(self.rng.random((k, 2, ve.ROSTER_SIZE)), axis=-1)[..., : ve.BROUGHT_SIZE].astype(np.uint8)

    def reset_battles(self, idx: np.ndarray) -> None:
        if len(idx) == 0:
            return
        k = len(idx)
        pairs = self.rng.choice(len(self.team_ids), size=(k, 2)) if self.pair_fn is None else np.asarray(self.pair_fn(k), np.int64)
        self.pairs[idx] = pairs
        bring = self.choose_bring(k) if self.bring_fn is None else np.asarray(self.bring_fn(idx, pairs), dtype=np.uint8)
        self.bring[idx] = bring
        seeds = self.rng.integers(0, 2**63 - 1, size=k, dtype=np.int64)
        self.seeds[idx] = seeds
        self.pool.reset(
            [int(i) for i in idx],
            [(self.team_ids[a], self.team_ids[b]) for a, b in pairs],
            [[list(map(int, bring[j, 0])), list(map(int, bring[j, 1]))] for j in range(k)],
            [int(s) for s in seeds],
        )
        if self.open_sheets:
            self.pool.set_open_sheets([int(i) for i in idx], True)

    def refresh(self) -> None:

        for side in (0, 1):
            o = self.obs[side]
            self.pool.observe(side, o.field, o.mon_ids, o.mon_features, o.history)
        m = self.masks
        read_masks(self.pool, self.masks)
        self.pool.status(self.status)

    def step(self, actions: np.ndarray, on_finish=None) -> np.ndarray:



        self.pool.step(np.ascontiguousarray(actions, dtype=np.int32))
        self.pool.status(self.status)
        finished = self.status.copy()
        self.engine_errors += self.pool.errors()
        if on_finish is not None:
            on_finish(finished)
        done = np.flatnonzero(finished >= 0)
        self.games_finished += len(done)
        self.reset_battles(np.flatnonzero((finished >= 0) | (finished == -3)))
        return finished


def potential(mon_features: torch.Tensor, scale: float) -> torch.Tensor:


    in_battle = mon_features[:, :, 1]
    hp = mon_features[:, :, 5] * in_battle
    mine = hp[:, :6].sum(1)
    foe = hp[:, 6:].sum(1) + (4 - in_battle[:, 6:].sum(1)).clamp(min=0)
    return scale * (mine - foe) / 4


def random_legal_actions(masks: Masks, rng: np.random.Generator) -> np.ndarray:


    codes = masks.gimmick_codes()
    state, kinds = codes & 3, (codes >> 2).max(-1)
    bits = masks.bits() | (state == 2)
    n = bits.shape[0]
    out = np.zeros((n, 2, 2, 2), np.int32)
    is_switch = np.zeros(ve.SLOT_ACTIONS, bool)
    is_switch[ve.SWITCH_BASE : ve.PASS_ACTION] = True

    def sample(allowed: np.ndarray) -> np.ndarray:
        scores = np.where(allowed, rng.random(allowed.shape), -1.0)
        return scores.argmax(-1)

    a0 = sample(bits[:, :, 0])
    st0 = np.take_along_axis(state[:, :, 0], a0[..., None], -1)[..., 0]
    st1_all = state[:, :, 1]


    same_kind = (st0 > 0) & (kinds[:, :, 0] == kinds[:, :, 1])
    slot1 = bits[:, :, 1].copy()
    slot1[same_kind] &= st1_all[same_kind] != 2

    rows, sides = np.nonzero(is_switch[a0])
    slot1[rows, sides, a0[rows, sides]] = False

    need = masks.min_switches.astype(np.int32) - is_switch[a0].astype(np.int32)
    can_switch = (slot1 & is_switch).any(-1)
    force = (need >= 1) & can_switch
    slot1[force] &= is_switch
    a1 = sample(slot1)
    st1 = np.take_along_axis(st1_all, a1[..., None], -1)[..., 0]
    mega0 = ((st0 == 1) & (rng.random(a0.shape) < 0.5)) | (st0 == 2)
    taken = mega0 & (kinds[:, :, 0] == kinds[:, :, 1])
    mega1 = (((st1 == 1) & (rng.random(a1.shape) < 0.5)) | (st1 == 2)) & ~taken
    out[:, :, 0, 0] = a0
    out[:, :, 0, 1] = mega0
    out[:, :, 1, 0] = a1
    out[:, :, 1, 1] = mega1
    return out

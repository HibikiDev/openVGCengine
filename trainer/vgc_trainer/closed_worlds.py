







from __future__ import annotations

from .showdown import belief


def supported() -> bool:


    import vgc_engine as ve
    return hasattr(ve.BattlePool, "set_sets")


class BeliefWorlds:
    def __init__(self, fmt: str):

        self.fmt = fmt
        self.prior = belief.SetPrior.load(fmt)
        self._sets: dict[tuple, dict] = {}
        self._teams: dict[tuple, int] = {}

    def guess(self, shown: tuple) -> dict:


        species, moves, item, gone, holds, ability = shown
        key = (belief.to_id(species), tuple(belief.move_id(m) for m in moves), belief.to_id(item), gone, holds, belief.to_id(ability))
        s = self._sets.get(key)
        if s is None:
            facts = belief.MonFacts(species=key[0], moves=list(key[1]), item=key[2] if ability else (key[2] or None), holds=holds,
                                    item_gone=gone, ability=key[5] or None)
            s = self._sets[key] = belief.world_set(self.prior, facts, self.fmt)
        return s

    def team_for(self, pool, index: int, side: int, src=None) -> int:

        sets = [self.guess(r) for r in (src if src is not None else pool).shown_sets(index, side)]
        key = (id(pool), tuple((s["species"], tuple(s["moves"]), s["item"], s["ability"], s["nature"], tuple(s["evs"].items()),
                                tuple((s.get("ivs") or {}).items())) for s in sets))
        tid = self._teams.get(key)
        if tid is None:
            tid = self._teams[key] = pool.register_team(sets, self.fmt)
        return tid

    def overlay(self, pool, indices: list[int], side: int, roots: list[int] | None = None, source=None) -> None:


        src = source if source is not None else pool
        roots = roots if roots is not None else indices
        cache: dict[int, int] = {}
        teams = []
        for r in roots:
            if r not in cache:
                cache[r] = self.team_for(pool, r, side, src)
            teams.append(cache[r])
        pool.set_sets(list(indices), side, teams)


class GuessedWorldEnv:






    def __init__(self, env, worlds: BeliefWorlds, seed: int = 0):
        import numpy as np
        import vgc_engine as ve
        from .env import Masks, Observation

        self.env, self.worlds, self.n = env, worlds, env.n
        self.pool = ve.BattlePool(env.n)
        for t, f in zip(env.teams, env.formats):
            self.pool.register_team(t) if f is None else self.pool.register_team(t, f)
        self.obs = [Observation.empty(env.n), Observation.empty(env.n)]
        self.masks = Masks.empty(env.n)
        self.status = np.zeros(env.n, np.int8)
        self.rng = np.random.default_rng(seed)

    def __getattr__(self, name):
        return getattr(self.env, name)

    def sync(self, side: int, idx) -> None:

        from .env import read_masks

        n = self.n
        self.pool.copy_from(self.env.pool, list(range(n)), list(range(n)), [int(x) for x in self.rng.integers(0, 2**62, n)])
        live = [int(i) for i in idx if self.env.status[i] == -1]
        if live:
            self.worlds.overlay(self.pool, live, 1 - side)
        for s in (0, 1):
            o = self.obs[s]
            self.pool.observe(s, o.field, o.mon_ids, o.mon_features, o.history)
        read_masks(self.pool, self.masks)
        self.pool.status(self.status)


class ClosedSheetSearch:



    def __init__(self, env, fmt: str, make, seed: int = 0, worlds: BeliefWorlds | None = None):
        self.world = GuessedWorldEnv(env, worlds or BeliefWorlds(fmt), seed)
        self.inner = make(self.world)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def choose(self, side: int, actions, battles=None, pick=None) -> None:
        import numpy as np
        live = self.world.env.masks.to_move[:, side] & (self.world.env.status == -1)
        self.world.sync(side, np.flatnonzero(live if battles is None else live & battles))
        self.inner.choose(side, actions, battles, pick)

    def evaluate(self, side: int, idx):
        self.world.sync(side, idx)
        return self.inner.evaluate(side, idx)

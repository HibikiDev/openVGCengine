























from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import torch
from vgc_trainer.amp import pick_device

SITE = {1: "miss", 2: "crit", 3: "damage roll", 4: "secondary effect", 5: "flinch (King's Rock)", 6: "confusion inflicted",
        7: "full paralysis", 8: "confusion self-hit", 9: "short sleep (2 turns)", 10: "thaw", 11: "Quick Claw / Quick Draw"}


_SECONDARY: dict[str, str] = {}
STATUS = {"brn": "burn", "par": "paralysis", "psn": "poison", "tox": "bad poison", "slp": "sleep", "frz": "freeze"}
STAT = {"atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe", "accuracy": "accuracy", "evasion": "evasion"}


def secondary_name(move: str) -> str:

    if not _SECONDARY:
        import json
        from pathlib import Path
        f = Path(__file__).resolve().parents[3] / "tools/gen-data/out/moves.json"
        for m in json.loads(f.read_text(encoding="utf8")):
            sec = m.get("secondary") or {}
            if sec.get("volatileStatus") == "flinch":
                txt = "flinch"
            elif sec.get("volatileStatus") == "confusion":
                txt = "confusion"
            elif sec.get("status"):
                txt = STATUS.get(sec["status"], sec["status"])
            elif sec.get("boosts"):
                txt = ", ".join(f"{v:+d} {STAT.get(k, k)}" for k, v in sec["boosts"].items())
            elif (sec.get("self") or {}).get("boosts"):
                txt = "own " + ", ".join(f"{v:+d} {STAT.get(k, k)}" for k, v in sec["self"]["boosts"].items())
            else:
                txt = "added effect"
            _SECONDARY[m["name"]] = txt
    return _SECONDARY.get(move, "added effect")


def _mon(species: str, sheet: list[dict]) -> str:


    base = species.split("-")[0]
    return next((st["species"] for st in sheet if st["species"].split("-")[0] == base), species)


def _event(site: int, bound: int, num: int | None) -> tuple[int, int, float] | None:


    if site == 3:
        return (0, bound - 1, 0.5)
    if site == 9:
        return (0, 1, 1 / 3)
    if num is None or not 0 < num < bound:
        return None
    if site == 1:
        return (bound - 1, 0, (bound - num) / bound)
    return (0, bound - 1, num / bound)


@torch.inference_mode()
def measure(team: list[dict], field: list[list[dict]], ckpt, probe_games: int = 96, seed: int = 0, dev=None,
            max_draws: int = 30, fmt: str | None = None) -> dict:



    import vgc_engine as ve
    from vgc_trainer.pilot import Agent
    from vgc_trainer.batch import Batch, preview_inputs, side_actions
    from vgc_trainer.preview import sample_bring
    from vgc_trainer.env import VecEnv
    dev = dev or pick_device()
    pilot = Agent(str(ckpt), dev)
    teams = [team] + list(field)
    n = probe_games
    rng = np.random.default_rng(seed + 29)
    gen = torch.Generator(device=dev)
    gen.manual_seed(seed)
    amp = dev.type == "cuda"

    def pair_fn(k):
        opp = rng.integers(1, len(teams), k)
        pairs = np.stack([np.zeros(k, np.int64), opp], 1)
        swap = rng.random(k) < 0.5
        pairs[swap] = pairs[swap][:, ::-1]
        return pairs

    def bring_fn(idx, pairs):
        if pilot.preview is None:
            return env.choose_bring(len(idx)).astype(np.int64)
        x = torch.from_numpy(preview_inputs(env, pairs).reshape(2 * len(idx), 12, -1)).to(dev)
        lead, back, _ = pilot.preview(x)
        return sample_bring(lead.float(), back.float(), gen)[0].cpu().numpy().reshape(len(idx), 2, 4).astype(np.int64)

    env = VecEnv(n, teams, seed=seed, formats=[fmt] * len(teams) if fmt else None)
    env.pair_fn, env.bring_fn = pair_fn, bring_fn
    env.reset_battles(np.arange(n))
    env.refresh()

    store_cap = n * 40
    store = ve.BattlePool(store_cap)
    kept: list[tuple[int, int, list, int, list]] = []
    live = np.ones(n, bool)
    team_side = (env.pairs[:, 1] == 0).astype(int)
    for _ in range(300):
        b = Batch(env, dev)
        with torch.autocast(dev.type, dtype=torch.float16, enabled=amp):
            acts = side_actions(pilot.policy.act(b.inputs(), b.bits, b.mega, b.min_switches, gen, 1.0)["actions"].cpu().numpy(), n)
        idx = [i for i in np.flatnonzero(live & (env.status == -1)) if len(kept) < store_cap]
        if idx:
            k0 = len(kept)
            seeds = [int(rng.integers(1, 2**62)) for _ in idx]
            store.copy_from(env.pool, [int(i) for i in idx], list(range(k0, k0 + len(idx))), seeds)
            for j, i in enumerate(idx):
                kept.append((k0 + j, int(team_side[i]), acts[i].tolist(), seeds[j], env.pairs[i].tolist()))
        status = env.step(acts)
        live &= ~((status >= 0) | (status == -3))
        if not live.any():
            break
        env.refresh()

    R = 1 + 2 * max_draws
    ev = VecEnv(R, teams, seed=seed + 1, pair_fn=lambda k: [[0, 1]] * k, bring_fn=lambda idx, pairs: [[[0, 1, 2, 3]] * 2] * len(idx),
                formats=[fmt] * len(teams) if fmt else None)
    ev.reset_battles(np.arange(R))
    rows: dict[tuple, dict] = defaultdict(lambda: {"w": 0.0, "events": 0, "var": 0.0, "spread": 0.0})
    var_total, n_probes, skipped = 0.0, 0, 0
    for k, side, acts, sd, pair in kept:
        ev.pool.copy_from(store, [k], [0], [sd])
        st = ev.pool.inspect(0)
        try:
            draws = ev.pool.step_scripted(0, acts, [])["draws"]
        except Exception:
            skipped += 1
            continue
        cand = []
        for d in draws:
            site, actor, move_id, move, target, kk, bound, num, rolled, result, forced = d
            e = _event(int(site), int(bound), num)
            if e is not None:
                cand.append((d, e))
        cand = cand[:max_draws]
        if not cand:
            n_probes += 1
            continue
        slots = []
        for j, (d, (v_event, v_usual, p)) in enumerate(cand):
            site, actor, move_id, move, target, kk = d[:6]
            for s, val in ((1 + 2 * j, v_event), (2 + 2 * j, v_usual)):
                ev.pool.copy_from(store, [k], [s], [sd])
                try:
                    ev.pool.step_scripted(s, acts, [(int(site), int(actor), int(move_id), int(target), int(kk), int(val))])
                except Exception:
                    pass
                slots.append(s)
        ev.refresh()
        b = Batch(ev, dev)
        with torch.autocast(dev.type, dtype=torch.float16, enabled=amp):
            v = pilot.policy.act(b.inputs(), b.bits, b.mega, b.min_switches, gen, 1.0)["value"].float().cpu().numpy()
        win = (v[side * R:(side + 1) * R] + 1) / 2
        n_probes += 1
        for j, (d, (v_event, v_usual, p)) in enumerate(cand):
            site, actor, move_id, move = int(d[0]), int(d[1]), int(d[2]), d[3]
            delta = float(win[1 + 2 * j] - win[2 + 2 * j])
            a_side, a_slot = divmod(actor, 2)
            try:
                who = st["sides"][a_side]["mons"][st["sides"][a_side]["active"][a_slot]]["species"]
            except (IndexError, KeyError, TypeError):
                who = "?"
            owner = "own" if a_side == side else "field"
            label = secondary_name(move) if site == 4 else SITE.get(site, str(site))
            key = (owner, _mon(who, teams[pair[a_side]]), move or "-", label)
            r = rows[key]
            r["events"] += 1
            r["site"] = site
            if site == 3:
                r["spread"] += abs(delta) / 4
                var_total += 0.25 * delta * delta
            else:
                r["w"] += p * delta
                r["var"] += p * (1 - p) * delta * delta
                var_total += p * (1 - p) * delta * delta
    games = max(1, n)
    out_rows = [{"owner": o, "mon": m, "move": mv, "event": lab, "site": r["site"], "per_game": round(r["w"] / games, 4),
                 "spread": round(r["spread"] / games, 4), "events": r["events"]} for (o, m, mv, lab), r in rows.items()]
    def tot(owner, sign):
        return round(sum(x["per_game"] for x in out_rows if x["owner"] == owner and (x["per_game"] > 0) == (sign > 0) and x["per_game"] != 0), 4)
    mons: dict[str, dict] = defaultdict(lambda: {"creates": 0.0, "carries": 0.0, "spread": 0.0})
    for x in out_rows:
        if x["owner"] == "own":
            if x["per_game"] > 0:
                mons[x["mon"]]["creates"] += x["per_game"]
            else:
                mons[x["mon"]]["carries"] += x["per_game"]
            mons[x["mon"]]["spread"] += x["spread"]
    return {"games": n, "probes": n_probes, "skipped": skipped, "model": getattr(ckpt, "name", str(ckpt)),
            "own_creates": tot("own", 1), "own_carries": tot("own", -1), "field_helps": tot("field", 1), "field_hurts": tot("field", -1),
            "roll_spread_own": round(sum(x["spread"] for x in out_rows if x["owner"] == "own"), 4),
            "roll_spread_field": round(sum(x["spread"] for x in out_rows if x["owner"] == "field"), 4),
            "sd": round(math.sqrt(var_total / games), 4),
            "mons": sorted(({"mon": m, **{k: round(v, 4) for k, v in d.items()}} for m, d in mons.items()), key=lambda r: r["carries"]),
            "rows": sorted(out_rows, key=lambda x: -abs(x["per_game"]) - x["spread"])}


def matchup(a: list[dict], b: list[dict], ckpt, probe_games: int = 128, seed: int = 0, dev=None, fmt: str | None = None) -> dict:



    r = measure(a, [b], ckpt, probe_games=probe_games, seed=seed, dev=dev, fmt=fmt)
    events = [dict(x, side="A" if x["owner"] == "own" else "B") for x in r["rows"] if x["site"] != 3 and x["per_game"] != 0]
    total = sum(abs(x["per_game"]) for x in events) or 1.0
    top = sorted(events, key=lambda x: -abs(x["per_game"]))
    return {"games": r["games"], "probes": r["probes"], "sd": r["sd"], "model": r["model"],
            "a": {"creates": r["own_creates"], "carries": r["own_carries"], "rolls": r["roll_spread_own"]},
            "b": {"creates": round(-r["field_hurts"], 4), "carries": round(-r["field_helps"], 4), "rolls": r["roll_spread_field"]},
            "net_a": round(r["own_creates"] + r["own_carries"] + r["field_helps"] + r["field_hurts"], 4),
            "top": top[:12], "top3_share": round(sum(abs(x["per_game"]) for x in top[:3]) / total, 3)}

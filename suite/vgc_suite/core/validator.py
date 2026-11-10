







from __future__ import annotations

from vgc_trainer import i18n
import json
import math
import time
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "trainer/scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "trainer/scripts"))

from .teams import lookup_team
from vgc_trainer.amp import pick_device

FIELDS = {
    "brisbane": ROOT / "tools/corpus/out/standings-brisbane-v2.json",
    "train": ROOT / "tools/corpus/out/standings-train-v2.json",
}


META_FIELD = ROOT / "trainer/runs/fields/current_meta.json"
META_NAME = "Current Metagame"
ROTATION = ["BR-111", "BA-427", "FR-2", "FR-12", "FR-15", "BR-1"]


def load_field(spec: str, fmt: str | None = None) -> list[tuple[str, list[dict]]]:



    from vgc_suite.formats import CURRENT, MC, get as get_format
    fmt = fmt or CURRENT
    if spec.startswith("bucket:"):
        from .buckets import format_of, teams
        if format_of(spec[7:]) != fmt:
            raise ValueError(i18n.t("the bucket {spec} holds {short} teams; this run is {short2} - pick a {short2} bucket", spec=spec[7:], short=get_format(format_of(spec[7:])).short, short2=get_format(fmt).short))
        return [(label, _ready(sets, fmt)) for label, sets, _ in teams(spec[7:])]
    if fmt != MC:
        raise ValueError(i18n.t("the built-in fields are Reg M-C's: for {short}, make a bucket of the teams you expect (Buckets)", short=get_format(fmt).short))
    if spec == "meta":
        if not META_FIELD.exists():
            raise ValueError(i18n.t("there's no built-in field here: make a team bucket of the teams you expect to face (Buckets) and pick it"))
        return [(t["label"], _ready(lookup_team(t["src"]))) for t in json.loads(META_FIELD.read_text(encoding="utf8"))["teams"]]
    if spec in FIELDS:
        if not FIELDS[spec].exists():
            raise ValueError(i18n.t("the {spec} field's file isn't in this install: pick a team bucket", spec=f"{spec!r}"))
        teams = json.loads(FIELDS[spec].read_text(encoding="utf8"))["teams"]
        out = []
        for t in teams:
            try:
                out.append((t["id"], _ready(t["sets"])))
            except Exception:
                continue
        return out
    ids = ROTATION if spec == "rotation" else [s for s in spec.split(",") if s]
    return [(i, lookup_team(i)) for i in ids]


def field_weights(spec: str) -> list[float] | None:

    if spec == "meta":
        return [float(t["weight"]) for t in json.loads(META_FIELD.read_text(encoding="utf8"))["teams"]]
    if not spec.startswith("bucket:"):
        return None
    from .buckets import get
    return [float(t["weight"]) for t in get(spec[7:])["teams"]]


def weighted_list(field: list[list[dict]], weights: list[float] | None, k: int = 48) -> list[list[dict]]:


    if not weights:
        return field
    tot = sum(weights)
    return [t for t, w in zip(field, weights) for _ in range(max(1, round(k * w / tot)))]


def _ready(sets: list[dict], fmt: str | None = None) -> list[dict]:


    import vgc_engine as ve
    from vgc_suite.formats import engine
    efmt = engine(fmt)
    if efmt is not None:
        ve.BattlePool(1).register_team(sets, efmt)
        return sets
    from vgc_trainer.showdown.sheets import playable_sheet
    sets = playable_sheet(sets)
    ve.BattlePool(1).register_team(sets)
    return sets


def _ci(p: float, n: int) -> tuple[float, float]:
    se = math.sqrt(max(p * (1 - p), 1e-9) / max(n, 1))
    return round(max(0.0, p - 1.96 * se), 3), round(min(1.0, p + 1.96 * se), 3)


def run_validation(team: list[dict], field: list[tuple[str, list[dict]]], ckpt: Path, games: int = 20000, seed: int = 0,
                   dev: torch.device | None = None, team_id: str = "submitted", weights: list[float] | None = None,
                   field_name: str | None = None, brings_agent=None, brings_k: int = 3, brings_games: int = 256,
                   progress=None, search_games: int = 0, fmt: str | None = None) -> dict:








    from vgc_trainer.pilot import Agent
    from vgc_trainer.pilot import play
    dev = dev or pick_device()
    pilot = Agent(str(ckpt), dev)
    teams = [team] + [s for _, s in field]
    opp_p = None
    if weights:
        w = np.array([0.0] + list(weights))
        opp_p = w / w.sum()
    from .matchup_stats import MatchupStats
    pairs = search = None
    if search_games > 0:
        from .h2h import make_searcher
        js = [j for j in range(1, len(teams)) if opp_p is None or opp_p[j] > 0]
        pairs = np.array([[0, j] if k % 2 == 0 else [j, 0] for j in js for k in range(search_games)])
        games = len(pairs)
        search = lambda env, s: make_searcher(pilot, env, dev, s)
    n_slots = games if search is not None else min(1024, games)
    stats = MatchupStats(n_slots, teams)
    seen = [0]
    t0, steps, first = time.time(), [0], {}

    def on_step(env, actions):
        stats.on_step(env, actions)
        if search is None or progress is None:
            return
        if "seeds" not in first:
            first["seeds"] = env.seeds.copy()
        steps[0] += 1
        live = (env.seeds == first["seeds"]) & (env.status == -1)

        est = seen[0] + float(np.minimum(np.asarray(env.pool.turns())[live] / 7.0, 0.95).sum())
        k = int(live.sum())
        if seen[0] and k <= max(2, games // 20):
            progress(i18n.t("Searched games: {done} of {total} - finishing the last {k} long ones", done=seen[0], total=games, k=k), min(est, games), games, "search-tail")
            return
        progress(i18n.t("Searched games: {done} of {total}", done=seen[0], total=games), min(est, games), games, "search")

    def on_done(env, done, res):
        stats.on_done(env, done, res)
        seen[0] += len(done)
        if progress is not None and search is None:
            progress(i18n.t("Games: {done} of {total}", done=f"{seen[0]:,}", total=f"{games:,}"), seen[0], games, "games")
    if search is not None and progress is not None:
        progress(i18n.t("Searched games: starting {total} (the first step is the slowest)", total=games), 0, games, "search")
    log = play([pilot], teams, games, n=n_slots, seed=seed, dev=dev, focus=[0], opp_p=None if search else opp_p,
               on_step=on_step, on_done=on_done, pairs=pairs, search=search, fmt=fmt)
    pairs, bring, result = log["pairs"], log["bring"], log["result"]
    dropped = Counter(int(b if a == 0 else a) for a, b, _ in log.get("dropped", []))
    mine_side = np.where(pairs[:, 0] == 0, 0, 1)
    keep = (pairs[:, 0] != pairs[:, 1])
    opp = np.where(mine_side == 0, pairs[:, 1], pairs[:, 0])[keep]
    score = np.where(mine_side == 0, result, 1 - result)[keep]
    my_bring = bring[np.arange(len(bring)), mine_side][keep]
    foe_bring = bring[np.arange(len(bring)), 1 - mine_side][keep]
    n = len(score)
    p, ci = float(score.mean()), None
    if search is not None and opp_p is not None:
        js = np.unique(opp)
        w = opp_p[js] / opp_p[js].sum()
        sj = np.array([score[opp == j].mean() for j in js])
        p = float((w * sj).sum())
        se = math.sqrt(float((w ** 2 * np.maximum(sj * (1 - sj), 1e-9) / np.array([(opp == j).sum() for j in js])).sum()))
        ci = (round(max(0.0, p - 1.96 * se), 3), round(min(1.0, p + 1.96 * se), 3))
    elo = 400 * math.log10(max(p, 1e-3) / max(1 - p, 1e-3))
    names = [s.get("name") or s["species"] for s in team]
    per_opp = []
    for j in np.unique(opp):
        sel = opp == j
        fid, fs = field[j - 1]
        leads = Counter(tuple(sorted(b[:2])) for b in my_bring[sel]).most_common(1)[0]
        flead = Counter(tuple(sorted(b[:2])) for b in foe_bring[sel]).most_common(1)[0]
        four = Counter((tuple(sorted(b[:2])), tuple(sorted(b[2:]))) for b in my_bring[sel]).most_common(1)[0][0]
        ffour = Counter((tuple(sorted(b[:2])), tuple(sorted(b[2:]))) for b in foe_bring[sel]).most_common(1)[0][0]
        fnames = [s.get("name") or s["species"] for s in fs]
        sp = float(score[sel].mean())
        per_opp.append({"id": fid, "species": [s["species"] for s in fs], "games": int(sel.sum()), "score": round(sp, 3),
                        "share": round(float(opp_p[j]), 3) if opp_p is not None else None,
                        "ci": _ci(sp, int(sel.sum())), "my_lead": "/".join(names[i] for i in leads[0]) + f" ({leads[1] / sel.sum():.0%})",
                        "their_lead": "/".join((fs[i].get("name") or fs[i]["species"]) for i in flead[0]) + f" ({flead[1] / sel.sum():.0%})",

                        "my_bring": {"lead": [names[i] for i in four[0]], "back": [names[i] for i in four[1]]},
                        "their_bring": {"lead": [fnames[i] for i in ffour[0]], "back": [fnames[i] for i in ffour[1]]},
                        "detail": stats.report(int(j)), "unfinished": dropped.get(int(j), 0),

                        "my_brought": [round(float(x), 3) for x in stats.brought_by_team()[int(j)]]})
    if brings_agent is not None:
        from .brings import summary
        for x, r in enumerate(per_opp):
            if progress is not None:
                progress(i18n.t("Bring matrix: {team} ({n} of {total})", team=r['id'], n=x + 1, total=len(per_opp)), x, len(per_opp), "brings")
            j = next(i for i, (fid, _) in enumerate(field) if fid == r["id"])
            r["brings"] = b = summary(brings_agent, team, field[j][1], k=brings_k, games=brings_games, seed=seed + 101 * (j + 1), fmt=fmt)

            b["mon_share"] = [round(sum(w for o, w in zip(b["mine"], b["equilibrium"]["mine"]) if k in o["bring"]), 3) for k in range(len(team))]
    per_opp.sort(key=lambda r: r["score"])
    mons = []
    usage = stats.overall()
    for i, nm in enumerate(names):
        brought = (my_bring == i).any(1)
        led = (my_bring[:, :2] == i).any(1)
        mons.append({"mon": nm, "brought": round(float(brought.mean()), 3), "led": round(float(led.mean()), 3),
                     "score_when_brought": round(float(score[brought].mean()), 3) if brought.any() else None,
                     **{k: usage[i][k] for k in ("fainted", "mega", "moves", "switch", "decisions")}})
    leads = Counter(tuple(sorted(b[:2])) for b in my_bring).most_common(4)
    return {"team": {"id": team_id, "species": [s["species"] for s in team]}, "model": ckpt.name, "games": n,
            "field": {"teams": len(field), "name": field_name, "weighted": opp_p is not None},
            "overall": {"score": round(p, 3), "ci": ci or _ci(p, n), "elo_vs_field": round(elo, 0)},
            "search": {"games_per_team": search_games, "unfinished": sum(dropped.values()),
                       "unfinished_by": {field[j - 1][0]: k for j, k in sorted(dropped.items())}} if search is not None else None,
            "mons": mons, "leads": [{"lead": "/".join(names[i] for i in k), "share": round(c / n, 3)} for k, c in leads],
            "worst": per_opp[:8], "best": per_opp[-8:][::-1], "opponents": per_opp,
            "caveats": ["the bot pilots both teams: this rates how well the bot plays them, not how a human would",
                        "opponent spreads are guessed where the sheets don't show them"],
            "brings": None if brings_agent is None else {"k": brings_k, "games_per_cell": brings_games, **_field_brings(per_opp)}}


def _field_brings(per_opp: list[dict]) -> dict:

    rows = [r for r in per_opp if r.get("brings")]
    w = [r["share"] if r["share"] is not None else 1.0 for r in rows]
    avg = lambda f: round(sum(f(r["brings"]) * x for r, x in zip(rows, w)) / max(sum(w), 1e-9), 3) if rows else None
    return {"as_picked": avg(lambda b: b["as_picked"]), "best_answer": avg(lambda b: b["best_answer"]["value"]),
            "equilibrium": avg(lambda b: b["equilibrium"]["value"])}


def render(rep: dict) -> str:
    o = rep["overall"]
    out = [f"Team Validator - {', '.join(rep['team']['species'])}",
           f"model {rep['model']}, {rep['games']} self-play games vs {rep['field']['teams']} field teams",
           f"Overall score {o['score']:.1%} (95% {o['ci'][0]:.1%}-{o['ci'][1]:.1%}), {o['elo_vs_field']:+.0f} Elo vs the field", "",
           "How the bot uses it:"]
    out += [f"  {m['mon']:<16} brought {m['brought']:>4.0%}  led {m['led']:>4.0%}" +
            (f"  score when brought {m['score_when_brought']:.0%}" if m["score_when_brought"] is not None else "") for m in rep["mons"]]
    out += ["  most common leads: " + ", ".join(f"{x['lead']} {x['share']:.0%}" for x in rep["leads"]), "", "Hardest matchups:"]
    out += [f"  {r['score']:>4.0%} ({r['games']:>3} g)  {r['id']:<10} {'/'.join(r['species'])}  - their lead {r['their_lead']}" for r in rep["worst"][:6]]
    out += ["", "Best matchups:"]
    out += [f"  {r['score']:>4.0%} ({r['games']:>3} g)  {r['id']:<10} {'/'.join(r['species'])}" for r in rep["best"][:6]]
    out += ["", "Caveats: " + "; ".join(rep["caveats"])]
    return "\n".join(out)

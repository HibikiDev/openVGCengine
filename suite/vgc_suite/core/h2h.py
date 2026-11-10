







from __future__ import annotations

from vgc_trainer import i18n
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "trainer/scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "trainer/scripts"))

from .validator import _ci, _ready
from vgc_trainer.amp import amp, pick_device

BO3_GAMES_PER_SERIES = 2.4
TOP_MATCHUPS = 4
TOP_LINES = 3


def _names(sheet: list[dict]) -> list[str]:
    return [s.get("name") or s["species"] for s in sheet]


BC_POLICY = None


def make_searcher(pilot, env, dev, seed: int):





    from vgc_trainer.model import load_policy
    from vgc_suite.formats import FORMATS
    from .bundle import closed_searcher, live_searcher, path as pinned
    bc = load_policy(torch.load(BC_POLICY or pinned("reply_policy"), map_location=dev, weights_only=True), dev).eval()
    closed = sorted({f for f in env.formats if f is not None and not FORMATS[f].open_sheets})
    if closed:
        from vgc_trainer.closed_worlds import ClosedSheetSearch, supported
        if not supported():
            raise ValueError("this engine build predates the closed-sheet search (BattlePool.set_sets)")
        if len(closed) > 1 or None in env.formats:
            raise ValueError(f"a closed-sheet search runs one format at a time, not {sorted(map(str, set(env.formats)))}")


        return ClosedSheetSearch(env, closed[0], lambda world: closed_searcher(pilot.policy, world, dev, seed), seed)




    if pilot.preview is None:
        raise ValueError("the tools' search needs the policy's preview head (the client's view samples the opponent's unseen mons)")
    return live_searcher(pilot.policy, env, dev, seed, bc, hidden="sample", spreads="guess", preview=pilot.preview)


def _backs(back: np.ndarray, lead: tuple[int, int], rng) -> list[int]:

    avail = np.isfinite(back.astype(np.float64))
    avail[list(lead)] = False
    out = []
    for _ in range(2):
        q = np.where(avail, back.astype(np.float64), -np.inf)
        q = np.exp(q - q[avail].max())
        k = int(rng.choice(len(q), p=q / q.sum()))
        out.append(k)
        avail[k] = False
    return out


def _bring_outside(lead: np.ndarray, back: np.ndarray, excluded: list[set], rng) -> list[int] | None:


    def logsm(x):
        x = x - x[np.isfinite(x)].max()
        return x - np.log(np.exp(x).sum())
    lp = logsm(lead.astype(np.float64))
    best, best_v = None, -np.inf
    for i in range(len(lp)):
        if not np.isfinite(lp[i]):
            continue
        rest = logsm(np.where(np.arange(len(lp)) == i, -np.inf, lead.astype(np.float64)))
        for j in range(len(lp)):
            if i != j and np.isfinite(rest[j]) and {i, j} not in excluded and lp[i] + rest[j] > best_v:
                best, best_v = (i, j), lp[i] + rest[j]
    return None if best is None else [best[0], best[1], *_backs(back, best, rng)]


def play_h2h(pilot, teams: list[list[dict]], games: int, seed: int, dev: torch.device, bring_temp: float = 1.0,
             deep: bool = False, bo3: bool = False, progress=None, fmt: str | None = None) -> dict:












    from collections import deque

    from vgc_trainer.batch import Batch, preview_inputs, side_actions
    from vgc_trainer.preview import sample_bring
    from vgc_trainer.env import VecEnv

    series_n = max(1, round(games / BO3_GAMES_PER_SERIES)) if bo3 else 0
    n = min(1024, series_n if bo3 else games)
    rng = np.random.default_rng(seed + 11)
    env = VecEnv(n, teams, seed=seed, formats=[fmt] * len(teams) if fmt else None)
    queue: deque = deque()

    def fresh(k):
        pairs = np.tile(np.array([0, 1]), (k, 1))
        swap = rng.random(k) < 0.5
        pairs[swap] = pairs[swap][:, ::-1]
        return pairs

    def pair_fn(k):
        out = fresh(k)
        for j in range(k):
            if queue:
                out[j] = queue.popleft()
        return out

    env.pair_fn = pair_fn
    gen = torch.Generator(device=dev)
    gen.manual_seed(seed)
    g_no = np.ones(n, np.int64)
    wins = np.zeros((n, 2), np.int64)
    hist = [[[], []] for _ in range(n)]
    human = None
    if bo3 and pilot.preview is not None:
        from .positions import _human_preview
        human = _human_preview()
    sid = np.arange(n)
    next_sid = {"v": n}

    def bring_fn(idx, pairs):
        bring = env.choose_bring(len(idx)).astype(np.int64)
        if pilot.preview is None:
            return bring
        x = torch.from_numpy(preview_inputs(env, pairs).reshape(2 * len(idx), 12, -1)).to(dev)
        with torch.inference_mode():
            lead, back, _ = pilot.preview(x)
            lead, back = lead.float() / bring_temp, back.float() / bring_temp
            bring = sample_bring(lead, back, gen)[0].cpu().numpy().reshape(len(idx), 2, 4).astype(np.int64)
        if bo3:
            from vgc_trainer.showdown.sheets import lead_rule_v3
            bk = back.cpu().numpy()
            hl = hb = None
            for j, i in enumerate(idx):
                for side in (0, 1):
                    if g_no[i] == 1 or not hist[i][side]:
                        continue
                    kw = lead_rule_v3(hist[i][side], rng.random())
                    if "force_lead" in kw:
                        f = tuple(int(v) for v in kw["force_lead"])
                        bring[j, side] = [f[0], f[1], *_backs(bk[2 * j + side], f, rng)]
                    elif "avoid_leads" in kw:
                        if hl is None:
                            if human is not None:
                                with torch.inference_mode():
                                    a, b_, _ = human(x.cpu())
                                hl, hb = a.float().numpy(), b_.float().numpy()
                            else:
                                hl, hb = lead.cpu().numpy(), bk
                        got = _bring_outside(hl[2 * j + side], hb[2 * j + side], [set(v) for v in kw["avoid_leads"]], rng)
                        if got is not None:
                            bring[j, side] = got
        return bring

    env.bring_fn = bring_fn
    env.reset_battles(np.arange(n))
    env.refresh()
    searcher = make_searcher(pilot, env, dev, seed) if deep else None
    t1 = np.zeros((n, 2, 2, 2), np.int32)
    have_t1 = np.zeros(n, bool)
    cols = defaultdict(list)
    finished = 0






    counted = np.ones(n, bool)
    launched = {"v": n}
    seen = env.seeds.copy()

    def on_finish(status):
        nonlocal finished
        done = np.flatnonzero(status >= 0)
        keep = np.array([i for i in done if counted[i]], dtype=np.int64)
        if not bo3:
            keep = keep[: max(0, games - finished)]
        launched["v"] -= int(((status == -3) & counted).sum())
        if len(keep):
            cols["a_side"].append((env.pairs[keep, 0] != 0).astype(np.int8))
            cols["bring"].append(env.bring[keep].copy())
            cols["t1"].append(t1[keep].copy())
            cols["result"].append(np.where(status[keep] == 0, 1.0, np.where(status[keep] == 1, 0.0, 0.5)).astype(np.float32))
            cols["turns"].append(np.asarray(env.pool.turns())[keep].astype(np.int16))
            cols["has_t1"].append(have_t1[keep].copy())
            cols["game_no"].append(g_no[keep].copy())
            cols["sid"].append(sid[keep].copy())
            finished += len(keep)
        have_t1[done] = False
        if not bo3:
            return
        for i in np.flatnonzero((status >= 0) | (status == -3)):
            over = bool(status[i] == -3)
            if not over:
                if status[i] in (0, 1):
                    wins[i, status[i]] += 1
                for side in (0, 1):
                    hist[i][side].append({"lead": [int(v) for v in env.bring[i, side, :2]], "won": bool(status[i] == side), "chaos": 0.0})
                over = bool(wins[i].max() >= 2 or g_no[i] >= 3)
            if over:
                g_no[i], wins[i] = 1, 0
                hist[i] = [[], []]
                sid[i] = next_sid["v"]
                next_sid["v"] += 1
                queue.append(fresh(1)[0])
            else:
                g_no[i] += 1
                queue.append(env.pairs[i].copy())

    t_start, step = time.time(), 0
    while finished < games or bo3:
        new = np.flatnonzero(env.seeds != seen)
        for i in new:
            if bo3 and g_no[i] > 1:
                continue
            counted[i] = launched["v"] < (series_n if bo3 else games)
            launched["v"] += 1
        seen[new] = env.seeds[new]
        if bo3 and not (counted & (env.status == -1)).any():
            break
        batch = Batch(env, dev)
        with torch.inference_mode(), amp(dev):
            s = pilot.policy.act(batch.inputs(), batch.bits, batch.mega, batch.min_switches, gen, 1.0)
        actions = side_actions(s["actions"].cpu().numpy(), n)
        turns = np.asarray(env.pool.turns())
        if searcher is not None:
            for side in (0, 1):
                searcher.choose(side, actions, (env.masks.min_switches[:, side] == 0) & counted)
        step += 1
        if progress is not None:
            live = counted & (env.status == -1)


            est = finished + float(np.minimum(turns[live] / 7.0, 0.95).sum())
            progress(i18n.t("Searched games: {done} of {total}", done=finished, total=games) if deep
                     else i18n.t("Games: {done} of {total}", done=finished, total=games), min(est, games), games, "games")
        first = (turns == 0) & ~have_t1 & (env.status == -1)
        t1[first] = actions[first]
        have_t1 |= first
        env.step(actions, on_finish)
        env.refresh()
    if env.engine_errors:
        print(f"engine errors: {len(env.engine_errors)} (first: {env.engine_errors[0]})")
    return {k: np.concatenate(v) for k, v in cols.items()}


def _line(t1_side: np.ndarray, own: list[dict], bring: np.ndarray, foe: list[dict], foe_bring: np.ndarray) -> str:

    from vgc_trainer.showdown.requests import describe_action
    names, foe_names = _names(own), _names(foe)
    out = []
    for k in (0, 1):
        mon = own[bring[k]]
        moves = list(mon.get("moves") or [])
        a, mega = int(t1_side[k, 0]), bool(t1_side[k, 1])
        out.append(f"{names[bring[k]]}: " + describe_action(a, moves, [foe_names[foe_bring[0]], foe_names[foe_bring[1]]],
                                                           names[bring[1 - k]], [names[i] for i in bring], mega))
    return " · ".join(sorted(out))


def _pair(names: list[str], idx) -> str:
    return " + ".join(sorted(names[i] for i in idx))


def summarise(log: dict, a: list[dict], b: list[dict]) -> dict:

    N = len(log["result"])
    rows = np.arange(N)
    sa = log["a_side"].astype(int)
    score = np.where(sa == 0, log["result"], 1 - log["result"])
    bring = {"a": log["bring"][rows, sa], "b": log["bring"][rows, 1 - sa]}
    t1 = {"a": log["t1"][rows, sa], "b": log["t1"][rows, 1 - sa]}
    sheets = {"a": a, "b": b}
    names = {"a": _names(a), "b": _names(b)}
    p = float(score.mean())

    def rec(sel) -> dict:
        k = int(sel.sum())
        return {"n": k, "share": round(k / N, 3), "score": round(float(score[sel].mean()), 3) if k else None}

    teams = {}
    for s in ("a", "b"):
        own_score = score if s == "a" else 1 - score
        mons = []
        for i, nm in enumerate(names[s]):
            brought = (bring[s] == i).any(1)
            led = (bring[s][:, :2] == i).any(1)
            mons.append({"mon": nm, "brought": round(float(brought.mean()), 3), "led": round(float(led.mean()), 3),
                         "score_brought": round(float(own_score[brought].mean()), 3) if brought.any() else None,
                         "score_led": round(float(own_score[led].mean()), 3) if led.any() else None})
        leads = Counter(_pair(names[s], x[:2]) for x in bring[s])
        fours = Counter(_pair(names[s], x) for x in bring[s])
        lead_key = np.array([_pair(names[s], x[:2]) for x in bring[s]])
        four_key = np.array([_pair(names[s], x) for x in bring[s]])
        teams[s] = {"names": names[s], "mons": mons,
                    "leads": [{"name": k, "n": c, "share": round(c / N, 3), "score": round(float(own_score[lead_key == k].mean()), 3)}
                              for k, c in leads.most_common(6)],
                    "fours": [{"name": k, "n": c, "share": round(c / N, 3), "score": round(float(own_score[four_key == k].mean()), 3)}
                              for k, c in fours.most_common(5)]}

    la = np.array([_pair(names["a"], x[:2]) for x in bring["a"]])
    lb = np.array([_pair(names["b"], x[:2]) for x in bring["b"]])
    pairs = Counter(zip(la, lb)).most_common(10)
    matchups = [{"a": x, "b": y, **rec((la == x) & (lb == y))} for (x, y), _ in pairs]

    plans = []
    ok = log["has_t1"].astype(bool)
    for m in matchups[:TOP_MATCHUPS]:
        sel = (la == m["a"]) & (lb == m["b"]) & ok
        if sel.sum() < 20:
            continue
        sides = {}
        for s, o in (("a", "b"), ("b", "a")):
            lines = np.array([_line(t1[s][r], sheets[s], bring[s][r], sheets[o], bring[o][r]) for r in np.flatnonzero(sel)])
            own_score = score[sel] if s == "a" else 1 - score[sel]
            top = Counter(lines).most_common(TOP_LINES)
            sides[s] = [{"line": ln, "share": round(c / len(lines), 3), "n": c,
                         "score": round(float(own_score[lines == ln].mean()), 3)} for ln, c in top]
        plans.append({"a": m["a"], "b": m["b"], "n": int(sel.sum()), "score": m["score"], "lines": sides})

    return {"games": N, "overall": {"score": round(p, 3), "ci": _ci(p, N), "elo": round(400 * math.log10(max(p, 1e-3) / max(1 - p, 1e-3)))},
            "turns": round(float(log["turns"].mean()), 1), "teams": teams, "matchups": matchups, "plans": plans}


def summarise_bo3(log: dict, a: list[dict], b: list[dict]) -> dict:



    N = len(log["result"])
    rows = np.arange(N)
    sa = log["a_side"].astype(int)
    score = np.where(sa == 0, log["result"], 1 - log["result"])
    names = {"a": _names(a), "b": _names(b)}
    lead = {"a": [_pair(names["a"], x[:2]) for x in log["bring"][rows, sa]],
            "b": [_pair(names["b"], x[:2]) for x in log["bring"][rows, 1 - sa]]}
    by_sid: dict[int, list[int]] = defaultdict(list)
    for r in rows:
        by_sid[int(log["sid"][r])].append(r)
    series, to_g3 = [], 0
    for rs in by_sid.values():
        rs = sorted(rs, key=lambda r: log["game_no"][r])
        if [int(log["game_no"][r]) for r in rs] != list(range(1, len(rs) + 1)):
            continue
        wa = sum(score[r] for r in rs)
        wb = len(rs) - wa
        if max(wa, wb) < 2 and len(rs) < 3:
            continue
        series.append(1.0 if wa > wb else 0.0 if wb > wa else 0.5)
        to_g3 += len(rs) == 3
    s = np.array(series) if series else np.zeros(0)
    games = []
    for g in (1, 2, 3):
        sel = log["game_no"] == g
        if not sel.any():
            continue
        entry = {"game": g, "n": int(sel.sum()), "score": round(float(score[sel].mean()), 3)}
        for side in ("a", "b"):
            own = score[sel] if side == "a" else 1 - score[sel]
            keys = np.array(lead[side])[sel]
            entry[side] = [{"name": k, "share": round(c / sel.sum(), 3), "score": round(float(own[keys == k].mean()), 3)}
                           for k, c in Counter(keys).most_common(3)]
        games.append(entry)
    changes = {}
    for side in ("a", "b"):
        kept, changed = [], []
        for rs in by_sid.values():
            rs = sorted(rs, key=lambda r: log["game_no"][r])
            for prev, cur in zip(rs, rs[1:]):
                own = score[cur] if side == "a" else 1 - score[cur]
                (kept if lead[side][cur] == lead[side][prev] else changed).append(own)
        n = len(kept) + len(changed)
        changes[side] = {"n": n, "changed": round(len(changed) / n, 3) if n else None,
                         "score_kept": round(float(np.mean(kept)), 3) if kept else None,
                         "score_changed": round(float(np.mean(changed)), 3) if changed else None}
    return {"series": len(s), "score": round(float(s.mean()), 3) if len(s) else None, "ci": _ci(float(s.mean()), len(s)) if len(s) else None,
            "to_g3": round(to_g3 / len(s), 3) if len(s) else None, "games": games, "changes": changes}


def run_h2h(a: list[dict], b: list[dict], ckpt: Path, games: int = 4000, seed: int = 0, dev: torch.device | None = None,
            agent=None, matrix_k: int = 4, matrix_games: int = 64, ids: tuple[str, str] = ("A", "B"), bring_temp: float = 1.0,
            deep: bool = False, examples: int = 0, bo3: bool = False, progress=None, fmt: str | None = None) -> dict:



    from vgc_trainer.pilot import Agent
    from vgc_suite.formats import FORMATS, engine, get as get_format
    dev = dev or pick_device()
    efmt = engine(fmt)
    closed = efmt is not None and not FORMATS[efmt].open_sheets
    from vgc_trainer.closed_worlds import supported
    deep_off = closed and deep and not supported()
    deep = deep and not deep_off
    a, b = _ready(a, fmt), _ready(b, fmt)
    log = play_h2h(Agent(str(ckpt), dev), [a, b], games, seed, dev, bring_temp, deep, bo3, progress, fmt=efmt)
    rep = summarise(log, a, b)
    if bo3:
        rep["bo3"] = summarise_bo3(log, a, b)
    rep.update(model=ckpt.name, bring_temp=bring_temp, deep=deep, ids={"a": ids[0], "b": ids[1]},
               species={"a": [s["species"] for s in a], "b": [s["species"] for s in b]}, format=get_format(fmt).id, format_name=get_format(fmt).short)
    if agent is not None and matrix_k and efmt is None:
        from .preview_advisor import advise
        rep["matrix"] = advise(agent, a, b, k=matrix_k, games=matrix_games, seed=seed, all_rows=True)
    if examples:
        from .h2h_examples import play_examples
        rep["examples"] = play_examples(a, b, ckpt, examples, deep=deep, device=str(dev), seed=seed, bo3=bo3, progress=progress, fmt=fmt)
    rep["caveats"] = ["the model pilots both teams (self-play" + (", both sides searching" if deep else ", no search")
                      + "): this is how the bot plays the matchup, not how a human would",
                      "spreads not given in a paste are the corpus guesses for the species",
                      "turn-1 lines are the policy's draws; a line seen a handful of times says little on its own"]
    if deep_off:
        rep["caveats"].append(f"{get_format(fmt).short} uses closed team sheets and this engine build can't search them yet, so these "
                              "games are played without search")
    if closed and deep:
        rep["caveats"].append(f"{get_format(fmt).short} uses closed team sheets: each side's search guesses the moves, items, abilities and "
                              "spreads the battle hasn't shown yet, like the practice bot")
    return rep


def render(rep: dict) -> str:

    A, B = rep["teams"]["a"], rep["teams"]["b"]
    o = rep["overall"]
    pc = lambda v: "-" if v is None else f"{v:.0%}"
    out = [f"Head-to-head: {rep['ids']['a']} ({' / '.join(rep['species']['a'])})",
           f"           vs {rep['ids']['b']} ({' / '.join(rep['species']['b'])})",
           f"model {rep['model']}, {rep['games']} self-play games, {rep['turns']} turns on average"
           + (f", team preview varied (T {rep['bring_temp']:g})" if rep.get("bring_temp", 1) != 1 else ""),
           f"{rep['ids']['a']} scores {o['score']:.1%} (95% {o['ci'][0]:.1%}-{o['ci'][1]:.1%}), {o['elo']:+d} Elo", ""]
    for s, T in (("a", A), ("b", B)):
        out.append(f"{rep['ids'][s]}: brought / led / own score when brought")
        for m in T["mons"]:
            out.append(f"  {m['mon']:<18} {pc(m['brought']):>5} {pc(m['led']):>5} {pc(m['score_brought']):>6}")
        out.append("  leads: " + ", ".join(f"{x['name']} {x['share']:.0%} (scores {x['score']:.0%})" for x in T["leads"][:4]))
        out.append("")
    out.append(f"Lead matchups ({rep['ids']['a']}'s lead vs {rep['ids']['b']}'s; share of games, {rep['ids']['a']}'s score):")
    for m in rep["matchups"][:8]:
        out.append(f"  {m['a']:<36} vs {m['b']:<36} {m['share']:>5.0%}  {m['score']:.0%}")
    for pl in rep["plans"]:
        out += ["", f"Turn 1 when {pl['a']} meets {pl['b']} ({pl['n']} games, {rep['ids']['a']} scores {pl['score']:.0%}):"]
        for s in ("a", "b"):
            for ln in pl["lines"][s]:
                out.append(f"  {rep['ids'][s]} {ln['share']:>4.0%}  {ln['line']}  (scores {ln['score']:.0%})")
    if "matrix" in rep:
        from .preview_advisor import render as render_matrix
        out += ["", "Bring matrix (Preview Advisor):", render_matrix(rep["matrix"])]
    out += ["", "Caveats: " + "; ".join(rep["caveats"]) + "."]
    return "\n".join(out)

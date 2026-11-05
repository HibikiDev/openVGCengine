








from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.core.analysis import analyze, render_text
from vgc_suite.core.models import load_agent
from vgc_suite.core.positions import walk
from vgc_suite.core.replay import load_replay
from vgc_trainer.showdown.teams import base_megas, parse_paste
from vgc_trainer.amp import pick_device


def cmd_analyze(args) -> None:
    log = load_replay(args.replay)
    agent, ckpt = load_agent(args.ckpt, args.device)
    sides = ["p1", "p2"] if args.side == "both" else [args.side]
    decs = {}
    for side in sides:
        paste = getattr(args, f"paste_{side}")
        own = [base_megas(s) for s in parse_paste(Path(paste).read_text(encoding="utf8"))] if paste else None
        decs[side] = walk(log, side, own)
    res = analyze(log, decs, agent, ckpt.name)
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1), encoding="utf8")
    print(render_text(res))


def cmd_preview(args) -> None:
    import torch
    from vgc_suite.core.preview_advisor import advise, render
    from vgc_suite.core.teams import lookup_team
    dev = args.device or pick_device().type
    agent, ckpt = load_agent(args.ckpt, dev)
    rep = advise(agent, lookup_team(args.mine), lookup_team(args.theirs), k=args.k, games=args.games, seed=args.seed,
                 all_rows=args.all_rows, answers=args.answers)
    rep["model"] = ckpt.name
    if args.json:
        Path(args.json).write_text(json.dumps(rep, indent=1), encoding="utf8")
    print(f"model {ckpt.name}")
    print(render(rep))


def cmd_opener_tree(args) -> None:
    import torch
    from vgc_suite.core.opener_tree import opener_tree, render
    from vgc_suite.core.teams import lookup_team
    dev = args.device or pick_device().type
    agent, ckpt = load_agent(args.ckpt, dev)
    rep = opener_tree(agent, lookup_team(args.mine), lookup_team(args.theirs), answers=args.answers, screen=args.screen,
                      confirm=args.confirm, seed=args.seed)
    rep["model"] = ckpt.name
    if args.json:
        Path(args.json).write_text(json.dumps(rep, indent=1), encoding="utf8")
    print(f"model {ckpt.name}")
    print(render(rep))


def cmd_validate(args) -> None:
    import torch
    from vgc_suite.core.models import newest_checkpoint
    from vgc_suite.core.teams import lookup_team
    from vgc_suite.core.validator import field_weights, load_field, render, run_validation
    ckpt = Path(args.ckpt) if args.ckpt else newest_checkpoint()
    field = load_field(args.field)
    dev = torch.device(args.device or pick_device().type)
    rep = run_validation(lookup_team(args.team), field, ckpt, games=args.games, seed=args.seed, dev=dev, team_id=args.team,
                         weights=field_weights(args.field), field_name=args.field)
    if args.json:
        Path(args.json).write_text(json.dumps(rep, indent=1), encoding="utf8")
    print(render(rep))


def cmd_deepdive(args) -> None:

    try:
        from vgc_suite.core import deepdive as dd
    except ImportError:
        raise SystemExit("deepdive: not in this build") from None
    cache = dd.cached(args.team)
    if cache.exists() and not args.refresh:
        d = json.loads(cache.read_text(encoding="utf8"))
        print(f"{args.team}: cached deep dive from {d['generated']} ({d['games']} games); --refresh to redo it")
    else:
        d = dd.deep_dive(args.team, threats=args.threats, pairs=args.pairs, step=args.step)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(d, indent=1, default=list), encoding="utf8")
        print(f"-> {cache} ({d['seconds']} s)")
    if args.html:
        Path(args.html).write_text(dd.render(d, standalone=True), encoding="utf8")
        print(f"-> {args.html}")


def cmd_h2h(args) -> None:
    import torch
    from vgc_suite.core.h2h import render, run_h2h
    from vgc_suite.core.teams import lookup_team
    dev = torch.device(args.device or pick_device().type)
    agent, ckpt = load_agent(args.ckpt, str(dev))
    rep = run_h2h(lookup_team(args.a), lookup_team(args.b), ckpt, games=args.games, seed=args.seed, dev=dev,
                  agent=agent if args.matrix_k else None, matrix_k=args.matrix_k,
                  ids=tuple(Path(x).stem if Path(x).exists() else x for x in (args.a, args.b)), bring_temp=args.bring_temp,
                  deep=args.deep, examples=args.examples, bo3=args.bo3)
    if args.json:
        Path(args.json).write_text(json.dumps(rep, indent=1), encoding="utf8")
    print(render(rep))


def main() -> None:
    ap = argparse.ArgumentParser(prog="vgc_suite")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("analyze", help="the model's view of every decision in a replay")
    p.add_argument("replay")
    p.add_argument("--side", default="both", choices=["p1", "p2", "both"])
    p.add_argument("--paste-p1")
    p.add_argument("--paste-p2")
    p.add_argument("--ckpt", help="checkpoint (default: the current one)")
    p.add_argument("--device", default="cpu")
    p.add_argument("--json", help="also write the ReplayAnalysis JSON here")
    p = sub.add_parser("preview", help="team-preview advisor: what to bring and lead against a known team")
    p.add_argument("--mine", required=True, help="team id, team file or paste file")
    p.add_argument("--theirs", required=True)
    p.add_argument("--k", type=int, default=5, help="options per side in the payoff matrix")
    p.add_argument("--games", type=int, default=96, help="self-play games per matrix cell")
    p.add_argument("--all-rows", action="store_true", help="also screen all 90 of my brings and add the best ones the models left out")
    p.add_argument("--answers", type=int, default=0, help="the opener tree: their N best answers to my main bring, my counter to each")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--ckpt")
    p.add_argument("--device")
    p.add_argument("--json")
    p = sub.add_parser("opener-tree", help="training buddy: my main bring, their best answers to it, my counter to each")
    p.add_argument("--mine", required=True, help="team id, team file or paste file")
    p.add_argument("--theirs", required=True)
    p.add_argument("--answers", type=int, default=3, help="their answers to list")
    p.add_argument("--screen", type=int, default=64, help="self-play games per cell in the screens (all 90 brings)")
    p.add_argument("--confirm", type=int, default=512, help="games per cell in the confirming replays (every reported value)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--ckpt")
    p.add_argument("--device")
    p.add_argument("--json")
    p = sub.add_parser("validate", help="team validator: a team vs a field of teams in self-play")
    p.add_argument("--team", required=True, help="team id, team file or paste file")
    p.add_argument("--field", default="brisbane", help="brisbane | train | rotation | bucket:<name> | comma-separated team ids/files")
    p.add_argument("--games", type=int, default=20000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--ckpt")
    p.add_argument("--device")
    p.add_argument("--json")
    p = sub.add_parser("h2h", help="head-to-head: two teams against each other in self-play - leads, turn-1 plans, bring matrix")
    p.add_argument("--a", required=True, help="team id, team file or paste file")
    p.add_argument("--b", required=True)
    p.add_argument("--games", type=int, default=4000)
    p.add_argument("--matrix-k", type=int, default=4, help="brings per side in the bring matrix (0: skip it)")
    p.add_argument("--bring-temp", type=float, default=1.0, help="team-preview temperature (> 1: see other leads play out)")
    p.add_argument("--bo3", action="store_true", help="best-of-three series with the bot's between-game lead rule")
    p.add_argument("--deep", action="store_true", help="both sides search every turn (~60x slower: use ~1,000 games)")
    p.add_argument("--examples", type=int, default=0, help="example games played in real Showdown (the local server on :8000)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--ckpt")
    p.add_argument("--device")
    p.add_argument("--json")
    p = sub.add_parser("deepdive", help="Team Deep Dive of a team: moves, threats, spread optimizer")
    p.add_argument("team", help="the team id (e.g. LO-14)")
    p.add_argument("--html", help="write the page here (standalone file)")
    p.add_argument("--refresh", action="store_true", help="redo the analysis even if a cached one exists")
    p.add_argument("--threats", type=int, default=6, help="single lethal hits per mon")
    p.add_argument("--pairs", type=int, default=4, help="two-hit focus-fire pairs per mon")
    p.add_argument("--step", type=int, default=2, help="stat-point grid step of the spread optimizer")
    args = ap.parse_args()
    {"analyze": cmd_analyze, "preview": cmd_preview, "opener-tree": cmd_opener_tree, "validate": cmd_validate, "h2h": cmd_h2h,
     "deepdive": cmd_deepdive}[args.cmd](args)


if __name__ == "__main__":
    main()












from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "trainer", ROOT / "suite", ROOT / "trainer/scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import show_trace
from vgc_suite.buddy import Buddy, disagreements, log_notes
from vgc_suite.core.teams import lookup_team
from vgc_trainer.formats import REGULATIONS
from vgc_trainer.showdown.agent import Agent
from vgc_trainer.showdown.buddy_client import BuddyClient
from vgc_trainer.showdown.live_search import SEARCH_ARMS, LiveSearch
from vgc_trainer.showdown.sheets import base_format, buddy_format
from vgc_trainer.showdown.teams import pack
from vgc_trainer.showdown.tracker import to_id



PLAYED = [f for reg in REGULATIONS for f in (reg, reg + "bo3")] + [
    "gen5vgc2013", "gen6vgc2014", "gen6vgc2015", "gen6vgc2016", "gen7vgc2017", "gen7vgc2018", "gen7vgc2019",
    "gen8vgc2020", "gen8vgc2021", "gen8vgc2022", "gen9vgc2023regc", "gen9vgc2023regd", "gen9vgc2024regg", "gen9vgc2025regi"]


LINE_HOST = "openvgchost"
PENDING = ROOT / "trainer/runs/practise_lines/pending.json"


def take_line(fmt: str) -> dict | None:



    try:
        d = json.loads(PENDING.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return None
    PENDING.unlink(missing_ok=True)
    if time.time() - d.get("time", 0) > 1800 or d.get("format") != fmt.partition("@@@")[0] or not d.get("team"):
        return None
    return d


def group(fmt: str) -> str:


    base = base_format(fmt.partition("@@@")[0])
    return next((reg for reg in REGULATIONS if base.startswith(reg)), base)


def make_client(args):



    team_ids = [t for t in args.team.split(",") if t]
    teams = [lookup_team(t) for t in team_ids]
    agent = Agent(args.checkpoint, args.device, seed=args.seed, temperature=args.temperature, min_p=args.min_p, closer=args.closer)
    formats = [buddy_format(f) for f in (args.formats.split(",") if args.formats else PLAYED)]
    client = BuddyClient(args.port, args.username, agent, teams[0] if teams else [], fmt=formats[0], formats=formats,
                         allow=set(args.allow.split(",")) if args.allow else None)
    client.join_rooms = [r for r in args.join_rooms.split(",") if r]
    if args.search_deadline is not None:
        client.search_deadline = args.search_deadline or None
    if args.search != "off" and agent.policy is not None:
        k, m = map(int, args.search.split(","))
        client.live_search = LiveSearch(agent, k, m, seed=args.seed, score="value", cand_temp=args.cand_temp)
        if args.opp_head:
            client.live_search.load_opp_head(args.opp_head)
        if args.reply_policy:
            client.live_search.load_reply_policy(args.reply_policy)
        if args.foe_preview:
            client.live_search.load_foe_preview(args.foe_preview)


        from vgc_trainer.showdown import belief
        client.closed_sheet_search = belief.DEX.exists() and any(belief.PRIORS.glob("*.json"))
    if not args.lead_preview:
        from vgc_suite.core.bundle import path as pinned
        args.lead_preview = str(pinned("preview_head"))
    if args.lead_preview and Path(args.lead_preview).exists():
        client.lead_preview = client.agent.load_preview_head(args.lead_preview)
    client.reply_temps = [float(x) for x in args.reply_temps.split(",")]
    client.search_arms = [SEARCH_ARMS[a] for a in args.search_arms.split(",")]
    client.closed_search_arms = [SEARCH_ARMS[a] for a in args.closed_search_arms.split(",")]
    client.closed_reply_temps = [float(x) for x in args.closed_reply_temps.split(",")]
    client.lead_arms = args.lead_arms.split(",")
    client.teams = list(teams)
    return client, team_ids, teams, formats


_COACH_LS: list = []


async def _coach(args, agent, user: str, room: str | None = None) -> None:


    from vgc_suite import coach
    from vgc_suite.core.bundle import path as pinned
    try:
        if not _COACH_LS:
            ls = LiveSearch(agent, 8, 8, seed=0, score="value", cand_temp=2.0)
            ls.load_reply_policy(str(pinned("reply_policy")))
            ls.load_foe_preview(str(pinned("preview_head")))
            _COACH_LS.append(ls)
        await coach.watch(args.port, user, agent, _COACH_LS[0], str(args.checkpoint), room=room)
    except Exception as e:
        print(f"coach for {user} stopped ({type(e).__name__}: {e})", flush=True)


async def main(args) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


    client, team_ids, teams, formats = make_client(args)
    buddy = Buddy(Path(args.buddy_profiles), formats=tuple(sorted({group(f) for f in formats})), accepted=tuple(formats))
    logs = Path(args.logs) if args.logs else None
    active: set[str] = set()
    coach_for: list[str] = []
    line_marks: dict[int, dict] = {}
    print(f"{args.username} on the local server (port {args.port}): {', '.join(formats)}; teams {', '.join(team_ids) or 'none (each challenger picks one)'}; "
          f"search arms {args.search_arms}, closed sheets {'searched' if client.closed_sheet_search else 'the raw policy'}, lead rule {args.lead_arms}", flush=True)
    await client.connect()

    def team_id(sheet) -> str:
        return next((i for i, t in zip(team_ids, teams) if t is sheet), "buddy")

    async def watch(battle) -> None:
        active.add(battle.room)
        try:
            try:
                result = await asyncio.wait_for(battle.done, args.timeout)
            except asyncio.TimeoutError:
                result = None
            record = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "room": battle.room, "checkpoint": args.checkpoint,
                      "team": team_id(battle.team), "ladder": False, "buddy": True, "ots": battle.ots, "series": battle.series,
                      "game": battle.series_game, "opponent": None, "winner": None, "turns": None, "errors": None,
                      "reply_temp": battle.reply_temp, "search_arm": (battle.search_arm or {}).get("name"), "lead_arm": battle.lead_arm}
            if id(battle.team) in line_marks:
                record.update(line=line_marks.pop(id(battle.team)), team="reopened")
            if result is not None:
                foe = [ln.split("|")[3] for ln in result.raw if ln.startswith("|player|") and len(ln.split("|")) > 3
                       and to_id(ln.split("|")[3]) != to_id(args.username)]
                record.update(opponent=foe[0] if foe else None, winner=result.winner, turns=result.turns, errors=len(result.errors))
                outcome = "tie" if result.winner is None else "won" if to_id(result.winner) == to_id(args.username) else "lost"
                print(f"{battle.room}: {outcome} vs {record['opponent']} in {result.turns} turns", flush=True)
                if logs:
                    logs.mkdir(parents=True, exist_ok=True)
                    (logs / f"{battle.room}.log").write_text("\n".join(result.raw), encoding="utf8")
                    (logs / f"{battle.room}.trace.json").write_text(json.dumps(battle.trace), encoding="utf8")
                    try:
                        (logs / f"{battle.room}.why.txt").write_text(show_trace.render(logs / f"{battle.room}.trace.json"), encoding="utf8")
                    except Exception as e:
                        print(f"{battle.room}: no .why.txt ({type(e).__name__}: {e})", flush=True)
            else:
                print(f"{battle.room}: no result after {args.timeout:.0f} s", flush=True)
            if args.results:
                with open(args.results, "a", encoding="utf8") as f:
                    f.write(json.dumps(record) + "\n")
            if args.post_game and result is not None and record["opponent"]:
                try:
                    lines = await asyncio.to_thread(disagreements, client.agent, result.raw, record["opponent"])
                    log_notes(Path(args.buddy_notes), battle.room, record["opponent"], lines)
                    print(f"{battle.room}: buddy notes for {record['opponent']}: {len(lines)}", flush=True)
                except Exception as e:
                    print(f"{battle.room}: no buddy note ({type(e).__name__}: {e})", flush=True)
            if battle.in_series:
                await asyncio.sleep(180)
            await client.leave(battle)
        except Exception:
            print(f"{battle.room}: recording the game failed: {traceback.format_exc(limit=3)}", flush=True)
        finally:
            active.discard(battle.room)

    async def battles() -> None:
        while True:
            battle = await client.new_battle.get()
            asyncio.get_running_loop().create_task(watch(battle))
            if coach_for:
                asyncio.get_running_loop().create_task(_coach(args, client.agent, coach_for.pop(0), battle.room))

    async def challenges() -> None:
        while True:
            challenger, fmt = await client.challenges.get()
            line = take_line(fmt) if to_id(challenger) == LINE_HOST else None
            if to_id(challenger) == LINE_HOST and line is None:
                await client.send(f"|/reject {challenger}")
                print(f"rejected an invite from {challenger} ({fmt}): no line handed over", flush=True)
                continue
            if Path(args.drain_file).exists() or len(active) >= args.max_battles or \
                    (client.allow and to_id(challenger) not in client.allow and line is None):
                await client.send(f"|/reject {challenger}")
                print(f"rejected a challenge from {challenger} ({fmt})", flush=True)
                continue
            if line is not None:
                client.team = line["team"]
                client.teams.append(client.team)
                line_marks[id(client.team)] = line["line"]
                me = to_id(line["line"].get("me", ""))
                client.timer_for[me] = False
                client.bring_for.pop(me, None)
                client.started = True
                await client.send(f"|/accept {challenger}")
                print(f"accepted a line: {line['line']} ({fmt})", flush=True)
                continue
            g = group(fmt)
            try:
                chosen = buddy.team_for(challenger, g)
            except Exception as e:
                print(f"buddy team for {challenger} unavailable ({type(e).__name__}: {e}); using the rotation", flush=True)
                chosen = None
            if not chosen and not teams:
                await client.send(f"|/reject {challenger}")
                print(f"rejected a challenge from {challenger} ({fmt}): no team set for {g} - pick the bot's team on the Buddy page",
                      flush=True)
                continue
            client.team = chosen or random.choice(teams)
            if chosen and not any(chosen is t for t in client.teams):
                client.teams.append(chosen)
            p = buddy.profile(challenger)
            client.ots_for[to_id(challenger)] = p.sheets
            client.timer_for[to_id(challenger)] = p.timer
            lead, back = buddy.drill_for(challenger, g)
            if lead and chosen:
                client.bring_for[to_id(challenger)] = {"lead": lead, "back": back}
            else:
                client.bring_for.pop(to_id(challenger), None)
            buddy.game_started(challenger)
            client.started = True
            await client.send(f"|/utm {pack(client.team)}")
            await client.send(f"|/accept {challenger}")
            print(f"accepted a {fmt} challenge from {challenger} (team {team_id(client.team)})", flush=True)
            if p.coach and client.agent.policy is not None:


                coach_for.append(challenger)

    await asyncio.gather(battles(), challenges())


def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--team", default="", help="comma-separated team ids, paste files or links: the rotation, played when a challenger "
                                           "set no team (empty: only the challengers' own picks)")
    ap.add_argument("--port", type=int, default=8000, help="the local Showdown server's port (the host is always 127.0.0.1)")
    ap.add_argument("--username", default="PracticeBot")
    ap.add_argument("--formats", default="", help="comma-separated base format ids (default every one the buddy plays)")
    ap.add_argument("--allow", default="", help="comma-separated names whose challenges and commands are taken (default anyone)")
    ap.add_argument("--join-rooms", default="lobby")
    ap.add_argument("--buddy-profiles", default=str(ROOT / "trainer/runs/buddy_profiles.json"))
    ap.add_argument("--buddy-notes", default=str(ROOT / "trainer/runs/buddy_notes.jsonl"))
    ap.add_argument("--no-post-game", dest="post_game", action="store_false")
    ap.add_argument("--logs", default=str(ROOT / "trainer/runs/buddy_logs"))
    ap.add_argument("--results", default=str(ROOT / "trainer/runs/buddy_results.jsonl"))
    ap.add_argument("--drain-file", default=str(ROOT / "trainer/runs/BUDDY_DRAIN"))
    ap.add_argument("--max-battles", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=3600)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--min-p", type=float, default=0.05)
    ap.add_argument("--closer", type=lambda x: None if x == "off" else float(x), default=0.9)
    ap.add_argument("--search", default="8,8", help="k,m of the live search, or off (the raw policy)")
    ap.add_argument("--cand-temp", type=float, default=2.0)
    ap.add_argument("--search-arms", default="S256")
    ap.add_argument("--search-deadline", type=float, default=None,
                    help="seconds from a request's arrival after which a search still running is dropped for the policy's choice "
                         "(default: battle.SEARCH_DEADLINE, and at most a sixth of the game clock left)")
    ap.add_argument("--closed-search-arms", default="A", help="closed-sheet formats: arm A at reply T 1, the setting VGC13's closed-sheet search was tested with (0.593 vs raw, 10-24) and the tools' closed_searcher; the A/B/C x 1/3.42 draw was a leftover of the null 10-08 A/Bs (user 11-08)")
    ap.add_argument("--reply-temps", default="1")
    ap.add_argument("--closed-reply-temps", default="1")
    ap.add_argument("--lead-arms", default="v3")
    ap.add_argument("--reply-policy", default="")
    ap.add_argument("--foe-preview", default="")
    ap.add_argument("--lead-preview", default="")
    ap.add_argument("--opp-head", default="")
    return ap


if __name__ == "__main__":
    asyncio.run(main(make_parser().parse_args()))











from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import urllib.parse
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from jinja2 import Environment, FileSystemLoader, select_autoescape
from vgc_suite import lock as suite_lock
from vgc_trainer.amp import pick_device

WEB = Path(__file__).resolve().parent
JOB_DIR = ROOT / "trainer/runs/web_jobs"
TOOLS = {
    "analyze": ("Replay Analyzer", "Walk through a replay turn by turn and see where the model would have played differently."),
    "preview": ("Preview Advisor", "Two teams in, a bring-and-lead plan out: what to bring, what they'll likely bring, how it plays out."),
    "validate": ("Team Deep Dive", "Your team against a field of teams, every game played the way the bot plays (searched)."),
    "h2h": ("Head-to-head", "Two teams against each other: leads, turn-1 plans and how the brings fare, in searched games."),
    "playout": ("Play-out", "Two teams, your pick of leads and back for each: the bot plays turn 1 or whole games, a few times."),
    "fieldplay": ("Series vs a field", "Your team against every team of a field: a few best-of-three series each, real games to study."),
    "crawler": ("Line Crawler", "Step one game turn by turn: pick both sides' moves with the bot's view of each, and keep every branch."),
}




import importlib.util
PRIVATE = importlib.util.find_spec("vgc_suite.team_stats") is not None


OPEN_WINDOW = None
QUIT_APP = None
FOCUS_APP = None



BROWSER_MODE = False
APP_SEEN = time.monotonic()





SHOWDOWN_URL = "http://127.0.0.1:8000" if sys.platform == "darwin" else "http://localhost:8000"


def private_route(path: str) -> bool:



    head = path.split("/")[0]
    return (head == "status" and not path.startswith("status/game/")) or head in ("prep", "deepdive") or path == "api/status"


WAIT: dict[str, str] = {}
FAST_FACTOR = 80
LIMITS = {"search_games": 128, "search_total": 1024, "brings_games": 512, "preview_games": 256, "preview_k": 8,"validate_games": 20000, "sixth_games": 10000, "sixth_candidates": 16, "sixth_field_top": 12, "sixth_robust_top": 8, "h2h_games": 20000, "h2h_deep_games": 4000, "h2h_examples": 5, "turn1_n": 24, "playout_games": 10, "playout_series": 5}




class Cancelled(BaseException):
    pass


class Jobs:


    def __init__(self, device: str):
        self.device = device
        self.jobs: dict[str, dict] = {}
        self.q: queue.Queue[str] = queue.Queue()
        self._agents: dict[str, object] = {}
        JOB_DIR.mkdir(parents=True, exist_ok=True)
        self._mark_interrupted()
        threading.Thread(target=self._work, daemon=True).start()
        threading.Thread(target=self._watch_lock, daemon=True).start()

    def _watch_lock(self) -> None:

        freed = False
        while True:
            locked = suite_lock.state() is not None
            if locked and not freed:
                from vgc_suite.core import crawler
                self._agents = {}
                crawler._SESSIONS.clear()
                crawler._MODELS.clear()
                import gc
                gc.collect()
                try:
                    import torch
                    from vgc_trainer.amp import free_memory
                    free_memory()
                except Exception:
                    pass
                print(f"{time.strftime('%H:%M:%S')} suite lock on: models dropped, GPU cache freed", flush=True)
            freed = locked
            time.sleep(5)

    @staticmethod
    def _mark_interrupted() -> None:


        for f in JOB_DIR.glob("*.json"):
            try:
                j = json.loads(f.read_text(encoding="utf8"))
            except (OSError, json.JSONDecodeError):
                continue
            if j.get("status") in ("queued", "running"):
                j.update(status="error", finished=time.time(),
                         error="The dashboard restarted while this run was waiting or running, so it was lost. Run it again: "
                               "\"use again\" in the tool's recent runs keeps your inputs.")
                f.write_text(json.dumps(j, indent=1, default=str), encoding="utf8")

    def submit(self, tool: str, params: dict) -> str:
        jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.jobs[jid] = {"id": jid, "tool": tool, "params": params, "status": "queued", "created": time.time()}

        (JOB_DIR / f"{jid}.json").write_text(json.dumps(self.jobs[jid], indent=1, default=str), encoding="utf8")
        self.q.put(jid)
        return jid

    def get(self, jid: str) -> dict | None:
        if jid in self.jobs:
            return self.jobs[jid]
        f = JOB_DIR / f"{jid}.json"
        if "/" not in jid and "\\" not in jid and f.exists():
            return json.loads(f.read_text(encoding="utf8"))
        return None

    def ahead_of(self, jid: str) -> int:
        return sum(1 for j in self.jobs.values() if j["status"] in ("queued", "running") and j["created"] < self.jobs[jid]["created"])

    def recent(self, n: int = 8) -> list[dict]:
        done = [json.loads(f.read_text(encoding="utf8")) for f in sorted(JOB_DIR.glob("*.json"))[-n:]]
        live = [j for j in self.jobs.values() if j["status"] in ("queued", "running")]
        return sorted(live + done, key=lambda j: j["created"], reverse=True)[:n]

    def history(self, tool: str, n: int = 15, fav_only: bool = False, every: bool = False, slot: bool | None = None) -> list[dict]:



        favs = favorites()
        if fav_only or every:
            n = 1000
        out, seen = [], set()
        live = [j for j in self.jobs.values() if j["tool"] == tool]
        for f in sorted(JOB_DIR.glob("*.json"), reverse=True):
            if len(out) >= n or len(seen) > 400:
                break
            try:
                j = json.loads(f.read_text(encoding="utf8"))
            except (OSError, ValueError):
                continue
            live.append(j)
        for j in sorted(live, key=lambda j: j.get("created", 0), reverse=True):
            if j.get("tool") != tool:
                continue
            if fav_only and j["id"] not in favs:
                continue
            if slot is not None and is_slot_run(j) != slot:
                continue
            key = j["id"] if (fav_only or every) else json.dumps({k: v for k, v in (j.get("params") or {}).items()}, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            teams = run_teams(tool, j.get("params") or {})
            if j.get("status") == "error" and any(not t["species"] for t in teams):
                continue
            res = j.get("result") if isinstance(j.get("result"), dict) else {}

            summary = None
            if tool == "validate" and j.get("status") == "done":
                fld = (j.get("params") or {}).get("field", "")
                fld = _i18n.t("bucket {name}", name=fld[7:]) if fld.startswith("bucket:") else _i18n.t("Current Metagame") if fld == "meta" \
                    else _i18n.t(fld)
                mode = _i18n.t("Search Mode {n} a team", n=res['search']['games_per_team']) if res.get("search") else _i18n.t("quick")
                if res.get("sweep"):
                    best = (res.get("rows") or [{}])[0]
                    summary = f"{fld} · {mode} · " + _i18n.t("{kind}: best {label} {pct}", kind=_i18n.t("slot") if res.get('slot') else _i18n.t("sixth"),
                                                            label=_cand_label(best.get('label')), pct=f"{best.get('overall', {}).get('score', 0):.0%}")
                elif res.get("overall"):
                    summary = f"{fld} · {mode} · " + _i18n.t("{pct} vs the field", pct=f"{res['overall']['score']:.0%}")
            out.append({"id": j["id"], "created": j.get("created"), "status": j.get("status"), "params": j.get("params") or {},
                        "teams": teams, "fav": favs.get(j["id"]), "summary": summary})
            if len(out) >= n:
                break
        return out

    def _agent(self):
        from vgc_suite.core.models import load_agent, newest_checkpoint
        ckpt = newest_checkpoint()
        key = str(ckpt)
        if key not in self._agents:
            self._agents = {key: load_agent(ckpt, self.device)}
        return self._agents[key]

    def _work(self) -> None:
        while True:
            jid = self.q.get()
            job = self.jobs[jid]
            if job.get("cancel"):
                job.update(status="error", error="Cancelled before it started.", finished=time.time())
                (JOB_DIR / f"{jid}.json").write_text(json.dumps(job, indent=1, default=str), encoding="utf8")
                continue
            while suite_lock.state() is not None:
                job["status"] = "queued"
                time.sleep(10)
            job.update(status="running", started=time.time())
            self._job = job
            from vgc_trainer.env import SHEETS_OPEN
            sheets_open = _sheets_open(job["params"])
            token = SHEETS_OPEN.set(sheets_open)
            try:
                job["result"] = getattr(self, f"_run_{job['tool']}")(job["params"])
                if sheets_open and isinstance(job["result"], dict) and job["result"].get("format_name"):
                    job["result"]["format_name"] += " · open team sheets"
                job["status"] = "error" if "error" in job["result"] else "done"
                if job["status"] == "error":
                    job["error"] = job["result"]["error"]
            except Cancelled:
                job.update(status="error", error="Cancelled.")
            except BaseException as e:
                job.update(status="error", error=str(e)[:300] if isinstance(e, BadInput) else f"{type(e).__name__}: {e}"[:300],
                           trace=traceback.format_exc()[-3000:])
            finally:
                SHEETS_OPEN.reset(token)
            job["finished"] = time.time()
            (JOB_DIR / f"{jid}.json").write_text(json.dumps(job, indent=1, default=str), encoding="utf8")



    @staticmethod
    def _own(params: dict, fmt: str | None = None) -> dict:

        from vgc_suite.formats import engine
        from vgc_trainer.showdown.teams import base_megas, parse_paste
        texts = {s: params[f"paste_{s}"] for s in ("p1", "p2") if params.get(f"paste_{s}", "").strip()}
        if engine(fmt) is None:
            return {s: [base_megas(x) for x in parse_paste(t)] for s, t in texts.items()}
        return {s: _read(t, fmt, f"The {s} paste") for s, t in texts.items()}

    def _run_analyze(self, params: dict) -> dict:
        from vgc_suite.core.analysis import analyze
        from vgc_suite.core.positions import walk
        from vgc_suite.core.replay import load_replay
        agent, ckpt = self._agent()
        rep = _report_of(params.get("replay", ""))
        if rep is not None:
            old = rep["job"].get("params") or {}
            params = {**params, **{k: old[k] for k in ("side", "depth", "paste_p1", "paste_p2") if k in old}}
        log = load_replay(_replay_src(params["replay"]))

        from vgc_suite.core.positions import replay_regulation
        from vgc_suite.formats import FORMATS, IN_ANALYZER, get as get_format
        fmt = replay_regulation(log)
        if fmt not in IN_ANALYZER:
            raise BadInput(_i18n.t("The Analyzer reads {list} replays for now; this one is {short} (its Z-Moves / Dynamax / Tera come next).", list=', '.join(FORMATS[f].short for f in IN_ANALYZER), short=get_format(fmt).short))
        own = self._own(params, fmt)


        from vgc_trainer.showdown.tracker import to_id
        base = lambda name: to_id((name or "").split("-")[0])
        ignored = [s for s, sets in own.items() if log.species.get(s)
                   and not {base(x) for x in log.species[s]} <= {base(m.get("species") or m.get("name")) for m in sets}]
        for s in ignored:
            own.pop(s)
            params = {**params, f"paste_{s}": ""}
        sides = ["p1", "p2"] if params.get("side", "both") == "both" else [params["side"]]
        res = analyze(log, {s: walk(log, s, own.get(s)) for s in sides}, agent, ckpt.name)
        res["paste_ignored"] = ignored
        if not res["turns"]:
            return {"error": f"no decisions found in that replay (is it a {get_format(fmt).short} doubles game?)"}


        from vgc_suite.game_views import view_from_lines
        v = view_from_lines(log.lines, sides[0], [])

        from vgc_suite.game_views import sheet_paste
        res["pastes"] = {s: {"text": (params.get(f"paste_{s}") or "").strip() or sheet_paste(log.lines, s),
                             "guessed": not (params.get(f"paste_{s}") or "").strip()} for s in ("p1", "p2")}

        from vgc_suite.core.positions import filled_sets, set_sources
        res["sets"], res["guess_paste"] = {}, {}
        for s in ("p1", "p2"):
            if not log.sheets.get(s) and not (params.get(f"paste_{s}") or "").strip():
                try:
                    res["sets"][s] = set_sources(log, s, fmt)
                    fs = filled_sets(log, s, fmt)
                    res["guess_paste"][s] = _guess_paste(fs, fmt) if fs else None
                except Exception:
                    res["sets"][s] = None
        res["narration"] = {"me": sides[0], "result": v["result"],
                            "turns": [{"turn": t["turn"], "events": t["events"], "ours": t["ours"], "theirs": t["theirs"]} for t in v["turns"]]}
        res["format"], res["format_name"] = fmt, get_format(fmt).short

        from vgc_suite.core.review import TIERS, review as run_review
        n = TIERS.get(params.get("depth") or "fast", 0)
        if n:
            done, total = [0], len(res["turns"])

            def prog(msg: str) -> None:
                done[0] += 1
                self._progress(msg, done[0], total, "review")
            rv = run_review(log, sides, agent, self._review_search(agent), str(ckpt), n=n, own=own, progress=prog)
            by = {(t["turn"], t["side"]): t for t in rv["turns"]}
            for t in res["turns"]:
                x = by.get((t["turn"], t["side"])) or {}
                for k in ("search", "chance"):
                    if x.get(k):
                        t[k] = x[k]
            res["review"] = {"n": n, "band": rv["band"]}
            res["luck"] = rv["luck"]
            res["fits"] = rv.get("fits") or {}

            costly: dict[str, list] = {s: [] for s in sides}
            for t in res["turns"]:
                s = t.get("search") or {}
                if s.get("costly", 0) > s.get("n", 0) // 2 and not s.get("hinges"):
                    costly[t["side"]].append({"turn": t["turn"], "gap": s["median_gap"], "votes": s["costly"], "n": s["n"],
                                              "played": s["played"], "best": s["best"]})
            swings = [t for t in rv["turns"] if t.get("swing") is not None]
            tip = max(swings, key=lambda t: abs(t["swing"])) if swings else None
            res["report"] = {"costly": {s: sorted(v, key=lambda c: -c["gap"])[:3] for s, v in costly.items()},
                             "tip": {"turn": tip["turn"], "side": tip["side"], "before": tip["win"],
                                     "after": round(tip["win"] + tip["swing"], 3)} if tip else None}
        return res

    def _review_search(self, agent):

        if getattr(self, "_review_ls", (None, None))[0] is not agent:
            from vgc_suite.core.bundle import path as pinned
            from vgc_trainer.showdown.live_search import LiveSearch
            ls = LiveSearch(agent, 8, 8, seed=0, score="value", cand_temp=2.0)
            ls.load_reply_policy(str(pinned("reply_policy")))
            ls.load_foe_preview(str(pinned("preview_head")))
            self._review_ls = (agent, ls)
        return self._review_ls[1]

    def _run_preview(self, params: dict) -> dict:
        from vgc_suite.core.preview_advisor import advise
        from vgc_suite.formats import engine, get as get_format, tool_format
        try:
            fmt = tool_format(params.get("format"))
        except ValueError as e:
            raise BadInput(str(e)) from None
        agent, ckpt = self._agent()
        mine = _legal(_read(_team_src(params["mine"]), fmt, "Your team"), "Your team", fmt)
        theirs = _legal(_read(_team_src(params["theirs"]), fmt, "Their team"), "Their team", fmt)
        rep = advise(agent, mine, theirs, k=_int(params, "k", 5, LIMITS["preview_k"]), games=_int(params, "games", 96, LIMITS["preview_games"]),
                     all_rows=bool(params.get("all_rows")), answers=3 if params.get("answers") else 0, progress=self._progress,
                     fmt=engine(fmt))
        rep["model"] = ckpt.name
        rep["format"], rep["format_name"] = fmt, get_format(fmt).short
        rep["names"] = {s: (params.get(f"name_{s}") or "").strip()[:40] or d for s, d in (("a", "Team A"), ("b", "Team B"))}
        return rep

    def _run_turn1(self, params: dict) -> dict:


        from vgc_suite.core.models import newest_checkpoint
        from vgc_suite.core.teams import lookup_team
        from vgc_suite.core.turn1 import turn1_lab
        src = self.get(params.get("src", ""))
        if not src or src.get("tool") != "preview" or not src.get("result"):
            raise BadInput(_i18n.t("Start from a finished Preview Advisor result."))
        r = src["result"]
        fmt = src["params"].get("format") or ENV.globals["current_format"]
        a, b = _read(_team_src(src["params"]["mine"]), fmt, "Your team"), _read(_team_src(src["params"]["theirs"]), fmt, "Their team")
        oa, ai = _turn1_bring(params, "a", r["my_options"], a)
        ob, bi = _turn1_bring(params, "b", r["their_options"], b)
        rep = turn1_lab(a, b, oa["bring"], ob["bring"], newest_checkpoint(), n=_int(params, "n", 12, LIMITS["turn1_n"]),
                        device=self.device, full=params.get("full") == "1", fmt=fmt)
        if "error" in rep:
            return rep
        names = r.get("names") or {"a": "Team A", "b": "Team B"}
        rep.update(src=src["id"], ai=ai + 1 if ai is not None else None, bi=bi + 1 if bi is not None else None, opt_a=oa, opt_b=ob,
                   names=names, ids={"a": names["a"], "b": names["b"]},
                   cell=r["matrix"][ai][bi] if ai is not None and bi is not None else None)
        return rep

    def _run_fieldplay(self, params: dict) -> dict:




        from collections import defaultdict

        from vgc_suite.core import buckets
        from vgc_suite.core.h2h_examples import game_summary, play_examples
        from vgc_suite.core.models import newest_checkpoint
        from vgc_suite.core.teams import legal
        from vgc_suite.core.validator import _ready, load_field


        g1 = params.get("g1", "own")
        sheet = params.get("sheet", "") if g1 in ("recommended", "safest") else ""
        g1_brings, dd = {}, None
        if sheet:
            try:
                dd = json.loads((JOB_DIR / f"{sheet}.json").read_text(encoding="utf8"))
            except (OSError, ValueError):
                raise BadInput(_i18n.t("that Deep Dive run isn't there any more")) from None
            params = dict(params, team=(dd.get("params") or {}).get("team", ""), field=(dd.get("params") or {}).get("field", "meta"),
                          format=(dd.get("params") or {}).get("format", ""))
        from vgc_suite.formats import get as get_format, tool_format
        try:
            fmt = tool_format(params.get("format"))
        except ValueError as e:
            raise BadInput(str(e)) from None
        team = _legal(_read(_team_src(params.get("team", "")), fmt, "Your team"), "Your team", fmt)
        field = params.get("field", "meta")
        if field != "meta" and not (field.startswith("bucket:") and field[7:] in buckets.names()):
            raise BadInput(_i18n.t("unknown field"))
        try:
            fld = load_field(field, fmt)
        except ValueError as e:
            raise BadInput(str(e)) from None
        if dd is not None:
            fld = []
            for o in (dd.get("result") or {}).get("opponents") or []:
                pair = _deepdive_matchup(dd, o["id"])
                if pair is None:
                    continue
                fld.append((o["id"], _ready(_read(_team_src(pair[1]), fmt, o["id"]), fmt)))
                if o.get("brings"):
                    b = checked_brings(sheet, o["id"], o["brings"])
                    g1_brings[o["id"]] = [int(i) for i in b["mine"][b[g1]["row"]]["bring"]]
        if len(fld) > buckets.MAX_TEAMS:
            raise BadInput(_i18n.t("At most {max_teams} teams (this field has {n}).", max_teams=buckets.MAX_TEAMS, n=len(fld)))
        n = _int(params, "series", 2, 3)
        deep = params.get("raw") != "1"
        ckpt, mine = newest_checkpoint(), _ready(team, fmt)
        games, teams, skipped = [], [], []
        total = len(fld) * n
        for k, (label, sets) in enumerate(fld):
            short = label.split(" (")[0]
            try:
                legal(sets, fmt)
            except ValueError as e:
                skipped.append(f"{short}: {e}")
                continue
            prog = lambda m, d=None, t=None, ph=None, k=k, short=short: self._progress(
                _i18n.t("{team} ({n} of {total}) · {step}", team=short, n=k + 1, total=len(fld), step=m), k * n + (d or 0), total, "series")
            got = play_examples(mine, sets, ckpt, n, deep=deep, device=self.device, seed=int(time.time()) % 100000 + k, bo3=True,
                                progress=prog, g1_bring_a=g1_brings.get(label), fmt=fmt)
            if got and all("error" in g for g in got):
                if not games:
                    return {"error": got[0]["error"]}
                skipped.append(f"{short}: {got[0]['error']}")
                continue
            first = len(games)
            for g in got:
                if "lines" in g:
                    g.update(game_summary(g["lines"]))
                g["opp"] = short
            games += got
            series = defaultdict(list)
            for g in got:
                if "lines" in g:
                    series[g["series"]].append(g["won"])
            gb = g1_brings.get(label)
            teams.append({"id": label, "short": short, "species": [s["species"] for s in sets], "first": first, "count": len(got),
                          "g1": {"lead": [mine[i]["species"] for i in gb[:2]], "back": [mine[i]["species"] for i in gb[2:]]} if gb else None,
                          "series": [{"n": s, "a": sum(v), "b": len(v) - sum(v)} for s, v in sorted(series.items())]})
        for t in teams:
            t["won"] = sum(s["a"] > s["b"] for s in t["series"])
        return {"team": [s["species"] for s in team], "field": f"bucket {field[7:]}" if field.startswith("bucket:") else "Current Metagame",
                "deep": deep, "series_each": n, "model": ckpt.name, "teams": teams, "examples": games, "skipped": skipped,
                "g1": g1 if sheet else "own", "sheet": sheet or None,
                "series_won": sum(t["won"] for t in teams), "series_played": sum(len(t["series"]) for t in teams),
                "ids": {"a": "your team", "b": "the field team"}, "format": fmt, "format_name": get_format(fmt).short}

    def _run_playout(self, params: dict) -> dict:


        from vgc_suite.core.models import newest_checkpoint
        from vgc_suite.core.turn1 import turn1_lab
        from vgc_suite.formats import get as get_format, tool_format
        try:
            fmt = tool_format(params.get("format"))
        except ValueError as e:
            raise BadInput(str(e)) from None
        names = {s: (params.get(f"name_{s}") or "").strip()[:40] or d for s, d in (("a", "Team A"), ("b", "Team B"))}

        a = _legal(_read(_team_src(params.get("a", "")), fmt, names["a"]), names["a"], fmt)
        b = _legal(_read(_team_src(params.get("b", "")), fmt, names["b"]), names["b"], fmt)
        if params.get("pick") == "bots":


            from collections import defaultdict

            from vgc_suite.core.h2h_examples import game_summary, play_examples
            bo3 = params.get("bo3") == "1"
            deep = params.get("raw") != "1"
            n = _int(params, "n", 2 if bo3 else 4, LIMITS["playout_series" if bo3 else "playout_games"])
            games = play_examples(a, b, newest_checkpoint(), n, deep=deep, device=self.device, seed=int(time.time()) % 100000, bo3=bo3,
                                  progress=self._progress, fmt=fmt)
            if games and all("error" in g for g in games):
                return {"error": games[0]["error"]}
            for g in games:
                if "lines" in g:
                    g.update(game_summary(g["lines"]))
            played = [g for g in games if "lines" in g]
            res = {"mode": "bots", "examples": games, "names": names, "ids": names, "deep": deep, "bo3": bo3,
                   "a_wins": sum(g["won"] for g in played), "games": len(played), "format": fmt, "format_name": get_format(fmt).short}
            if bo3:
                series = defaultdict(list)
                for g in played:
                    series[g["series"]].append(g["won"])
                res["series"] = [{"n": k, "a": sum(v), "b": len(v) - sum(v)} for k, v in sorted(series.items())]
                res["a_series"] = sum(s["a"] > s["b"] for s in res["series"])
            return res
        oa, _ = _turn1_bring({**params, "ai": "c"}, "a", [], a)
        ob, _ = _turn1_bring({**params, "bi": "c"}, "b", [], b)
        names_a = [m.get("name") or m["species"] for m in a]
        names_b = [m.get("name") or m["species"] for m in b]
        fa = _forced_turn1(params, "a", names_a, oa["bring"], [names_b[i] for i in ob["bring"][:2]])
        fb = _forced_turn1(params, "b", names_b, ob["bring"], [names_a[i] for i in oa["bring"][:2]])
        fa = _with_turn2(params, "a", names_a, oa["bring"], fa)
        fb = _with_turn2(params, "b", names_b, ob["bring"], fb)
        rep = turn1_lab(a, b, oa["bring"], ob["bring"], newest_checkpoint(), n=_int(params, "n", 8, LIMITS["turn1_n"]),
                        device=self.device, full=params.get("full") == "1", force_a=fa, force_b=fb,
                        policy_a=params.get("pa") == "1", policy_b=params.get("pb") == "1", fmt=fmt)
        if "error" in rep:
            return rep
        names = {s: (params.get(f"name_{s}") or "").strip()[:40] or d for s, d in (("a", "Team A"), ("b", "Team B"))}
        oa.pop("custom"), ob.pop("custom")
        rep.update(src=None, ai=None, bi=None, opt_a=oa, opt_b=ob, names=names, ids=names, cell=None, format=fmt,
                   format_name=get_format(fmt).short)
        return rep

    def _run_muselfplay(self, params: dict) -> dict:

        import torch
        from vgc_suite import matchups as mu
        lo = params.get("min", "")
        res = mu.selfplay_fill(params.get("k", ""), params.get("mode", "exact"), params.get("group", "family"), params.get("tc", "1") != "0",
                               int(lo) if lo.isdigit() else None, "sd" if params.get("sort") == "sd" else "tour",
                               update=params.get("update") == "1", dev=torch.device(self.device), log=lambda m: None)
        from urllib.parse import urlencode
        res["back"] = "/status/matchups/six?" + urlencode({x: params.get(x, "") for x in ("k", "mode", "group", "tc", "min", "sort")})
        return res

    def _run_validate(self, params: dict) -> dict:
        import torch
        from vgc_suite.core import buckets
        from vgc_suite.core.validator import field_weights, load_field, run_validation, weighted_list
        from vgc_suite.formats import FORMATS, MC, engine, get as get_format, tool_format
        try:
            fmt = tool_format(params.get("format"))
        except ValueError as e:
            raise BadInput(str(e)) from None
        efmt = engine(fmt)
        closed = not FORMATS[fmt].open_sheets
        _, ckpt = self._agent()
        spec = _team_src(params["team"])
        field = params.get("field", "meta")
        if field not in ("meta", "brisbane", "train", "rotation") and not (field.startswith("bucket:") and field[7:] in buckets.names()):
            raise BadInput(_i18n.t("unknown field"))
        team = _read(spec, fmt, "Your team")
        try:
            fld = load_field(field, fmt)
        except ValueError as e:
            raise BadInput(str(e)) from None
        weights = field_weights(field)
        from vgc_suite.core.teams import legal
        try:
            team, legal_notes = legal(team, fmt, partial=len(team) < 6)
        except ValueError as e:
            raise BadInput(_i18n.t("Your team: {error}", error=e)) from None


        legacy = "fast" not in params and ("search" in params or "games" in params)
        per_team = _int(params, "search_games", 48, LIMITS["search_games"])
        per_team = max(8, per_team + per_team % 2)
        tier = params.get("tier")
        fast = tier == "fast" or params.get("fast") == "1" or (legacy and params.get("search") != "1")
        deep = tier == "deep"
        from vgc_trainer.closed_worlds import supported
        search_games = 0 if fast or (closed and not supported()) else per_team

        quick_games = _int(params, "games", 4000, LIMITS["validate_games"]) if legacy else \
            FAST_FACTOR * min(per_team * len(fld), LIMITS["search_total"])
        with_brings = legacy and params.get("brings") == "1"
        slot_lab = params.get("lab") == "slot"
        if len(team) == 5 and not slot_lab and not legacy:
            raise BadInput(_i18n.t("Five Pokémon: find the sixth under Team Lab → Change a slot."))
        if slot_lab and len(team) == 6 and not (params.get("replace") or "").strip():
            raise BadInput(_i18n.t("Name the Pokémon to replace - or give five to find a sixth."))
        if len(fld) > buckets.MAX_TEAMS:
            raise BadInput(_i18n.t("Team Lab plays at most {max_teams} teams, and this field has {n}: pick a bucket (the Buckets page makes one).", max_teams=buckets.MAX_TEAMS, n=len(fld)))
        if deep and (len(team) != 6 or slot_lab):
            raise BadInput(_i18n.t("Deep Mode is for a full team of six in the Deep Dive."))
        if deep and not search_games:
            raise BadInput(_i18n.t("Deep Mode needs the search, and this format's closed team sheets can't be searched on this engine build."))
        if search_games * len(fld) > LIMITS["search_total"] and not deep:
            raise BadInput(_i18n.t("Search Mode plays at most {search_total} games at once: {search_games} a team x {n} teams is {value} - use {value2} or fewer a team.", search_total=LIMITS['search_total'], search_games=search_games, n=len(fld), value=search_games * len(fld), value2=LIMITS['search_total'] // len(fld)))
        if closed:
            legal_notes = legal_notes + [f"{get_format(fmt).short} uses closed team sheets: the bot's search guesses the moves, items, "
                                         "abilities and spreads the battle hasn't shown yet, like the practice bot." if supported() else
                                         f"{get_format(fmt).short} uses closed team sheets and this engine build can't search them yet, so "
                                         "the games and bring tables are played without search."]
        if len(team) == 5:
            return _with_notes(self._run_sixth(team, params, fld, weights, field, ckpt, mode=(search_games, quick_games, fast), fmt=fmt),
                               legal_notes)
        slot = (params.get("replace") or "").strip().lower()
        if slot and len(team) == 6:
            hit = [i for i, m in enumerate(team) if slot in ((m.get("name") or "").lower(), m["species"].lower())] or                   [i for i, m in enumerate(team) if m["species"].lower().startswith(slot)]
            if len(hit) != 1:
                raise BadInput(_i18n.t("Name one Pokémon of your team to replace (\"{replace}\" matches {n}).", replace=params['replace'].strip(), n=len(hit)))
            k = hit[0]
            return _with_notes(self._run_sixth(team[:k] + team[k + 1:], params, fld, weights, field, ckpt,
                                               baseline=(team[k].get("name") or team[k]["species"], team[k]),
                                               mode=(search_games, quick_games, fast), fmt=fmt), legal_notes)
        if len(team) != 6:
            raise BadInput(_i18n.t("Give six Pokémon - or five, to find the sixth (this team has {n}).", n=len(team)))
        ref_src = (params.get("reference") or "").strip()
        tag = lambda who: (lambda m, d=None, t=None, ph=None: self._progress(f"{who}{m}", d, t, f"{who}{ph}")) if ref_src \
            else self._progress
        fname = f"bucket {field[7:]}" if field.startswith("bucket:") else "Current Metagame" if field == "meta" else None
        run_deep_ = lambda t, tid, who="": __import__("vgc_suite.core.deep", fromlist=["run_deep"]).run_deep(
            t, fld, self._agent()[0], Path(ckpt).name, team_id=tid, weights=weights, field_name=fname, progress=tag(who), fmt=efmt)
        run = run_deep_ if deep else lambda t, tid, who="": run_validation(
            t, fld, ckpt, games=quick_games, dev=torch.device(self.device), team_id=tid,
            weights=weights, field_name=f"bucket {field[7:]}" if field.startswith("bucket:") else "Current Metagame" if field == "meta" else None,
            brings_agent=self._agent()[0] if with_brings else None,
            brings_games=_int(params, "brings_games", 256, LIMITS["brings_games"]), progress=tag(who), search_games=search_games, fmt=efmt)
        ref = None
        if ref_src:
            ref = _read(_team_src(ref_src), fmt, "The reference team")
            if len(ref) != 6:
                raise BadInput(_i18n.t("The reference team needs six Pokémon (it has {n}).", n=len(ref)))
            try:
                ref, ref_notes = legal(ref, fmt)
            except ValueError as e:
                raise BadInput(_i18n.t("The reference team: {error}", error=e)) from None
            legal_notes += [f"reference team: {n}" for n in ref_notes]
        res = run(team, spec if "\n" not in spec else "your paste", _i18n.t("your team") + " · ")
        if ref is not None:
            rr = run(ref, ref_src if "\n" not in ref_src else "the reference", _i18n.t("the reference team") + " · ")
            res["reference"] = {"team": rr["team"], "overall": rr["overall"], "brings": rr["brings"], "mons": rr["mons"],
                                "opponents": {o["id"]: {"score": o["score"], "games": o["games"],
                                                        "both_adapt": (o.get("brings") or {}).get("equilibrium", {}).get("value")}
                                              for o in rr["opponents"]}}
        res["format"], res["format_name"] = fmt, get_format(fmt).short
        _with_notes(res, legal_notes)
        if params.get("luck", "1") == "1":
            self._progress(_i18n.t("Luck: replaying the chance rolls"))
            from vgc_suite.core.entropy import measure
            from vgc_suite.core.validator import _ready
            try:
                res["luck"] = measure(_ready(team, fmt), weighted_list([s for _, s in fld], weights), ckpt, probe_games=128,
                                      dev=torch.device(self.device), fmt=efmt)
            except Exception as e:
                res["luck_error"] = f"{type(e).__name__}: {e}"
        return res

    def _run_mxcheck(self, params: dict) -> dict:




        import numpy as np
        from vgc_suite.core.brings import play_cells
        from vgc_suite.core.h2h import make_searcher
        from vgc_suite.core.preview_advisor import equilibrium
        from vgc_suite.core.validator import _ready
        from vgc_suite.formats import engine, tool_format
        dd, opp = self.get(params.get("dd", "")), params.get("opp", "")
        row = next((o for o in ((dd or {}).get("result") or {}).get("opponents") or [] if o.get("id") == opp), None)
        if not dd or dd.get("tool") != "validate" or row is None or not row.get("brings"):
            raise BadInput(_i18n.t("That Deep Dive run or its bring matrix for this team isn't available."))
        raw_matrix = row["brings"]["matrix"]
        gaps = params.get("gaps") == "1"
        b = checked_brings(dd["id"], opp, row["brings"]) if gaps else row["brings"]
        pair = _deepdive_matchup(dd, opp)
        try:
            fmt = tool_format(((dd.get("params") or {}).get("format")))
        except ValueError as e:
            raise BadInput(str(e)) from None
        from vgc_suite.formats import FORMATS
        from vgc_trainer.closed_worlds import supported
        if not FORMATS[fmt].open_sheets and not supported():
            raise BadInput(_i18n.t("This engine build can't search closed team sheets yet."))
        mine, theirs = _ready(_read(_team_src(pair[0]), fmt, "Your team"), fmt), _ready(_read(_team_src(pair[1]), fmt, opp), fmt)
        eqm, eqt = b["equilibrium"]["mine"], b["equilibrium"]["theirs"]
        rows = [i for i, w in enumerate(eqm) if w >= 0.05]
        cols = [j for j, w in enumerate(eqt) if w >= 0.05]
        done_cells = {tuple(c) for c in b.get("searched") or []} if gaps else set()
        cells, tags = [], {}
        for i, j, tag in reference_cells(b):
            if (i, j) in done_cells:
                continue
            if (i, j) not in tags and len(cells) < 12:
                cells.append((i, j))
            tags.setdefault((i, j), []).append(tag)
        if not cells:
            return {"dd": dd["id"], "opp": opp, "species": row["species"], "team": dd["result"]["team"]["species"], "games": 0,
                    "cells": [], "both_adapt": None, "model": dd["result"].get("model"), "gaps": gaps,
                    "note": _i18n.t("Nothing left to search: every cell the quick references rest on is searched.")}
        games = _int(params, "games", 64, 128)
        agent = self._agent()[0]
        vals = play_cells(agent, mine, theirs, [(b["mine"][i]["bring"], b["theirs"][j]["bring"]) for i, j in cells], games,
                          7100 if params.get("fresh") != "1" else 7100 + int(time.time()) % 100000,
                          search=lambda env, seed: make_searcher(agent, env, agent.dev, seed),
                          progress=lambda d, t: self._progress(_i18n.t("Searched games: {done} of {total}", done=d, total=t),
                                                               d, t, "search"), fmt=engine(fmt))
        got = {c: float(v) for c, v in zip(cells, vals)}
        out = [{"row": i, "col": j, "mine": b["mine"][i]["lead"] + b["mine"][i]["back"], "theirs": b["theirs"][j]["lead"] + b["theirs"][j]["back"],
                "tags": tags[(i, j)], "raw": raw_matrix[i][j], "search": round(got[(i, j)], 3)} for i, j in cells]
        both = None
        if rows and cols and all((i, j) in got for i in rows for j in cols):
            sub = np.array([[got[(i, j)] for j in cols] for i in rows])
            both = {"raw": b["equilibrium"]["value"], "search": round(float(equilibrium(sub)[2]), 3),
                    "brings": {"mine": [b["mine"][i]["lead"] + b["mine"][i]["back"] for i in rows],
                               "theirs": [b["theirs"][j]["lead"] + b["theirs"][j]["back"] for j in cols]}}
        return {"dd": dd["id"], "opp": opp, "species": row["species"], "team": dd["result"]["team"]["species"], "games": games,
                "cells": out, "both_adapt": both, "model": dd["result"].get("model"), "gaps": gaps}

    def _run_mxsearch(self, params: dict) -> dict:

        from vgc_suite.core.deep import Matchup
        from vgc_suite.core.validator import _ready
        from vgc_suite.formats import FORMATS, engine, tool_format
        from vgc_trainer.closed_worlds import supported
        dd, opp = self.get(params.get("dd", "")), params.get("opp", "")
        pair = _deepdive_matchup(dd, opp)
        if pair is None:
            raise BadInput(_i18n.t("That Deep Dive run or this team isn't available."))
        try:
            fmt = tool_format((dd.get("params") or {}).get("format"))
        except ValueError as e:
            raise BadInput(str(e)) from None
        if not FORMATS[fmt].open_sheets and not supported():
            raise BadInput(_i18n.t("This engine build can't search closed team sheets yet."))
        mine, theirs = _ready(_read(_team_src(pair[0]), fmt, "Your team"), fmt), _ready(_read(_team_src(pair[1]), fmt, opp), fmt)
        self._progress(_i18n.t("Finding the fours to look at"))
        m = Matchup(self._agent()[0], mine, theirs, 7300, engine(fmt))
        m.stage1(lambda d, t: self._progress(_i18n.t("Searched matrix: {done} of {total} games", done=d, total=t), d, t, "search"))
        m.stage2(lambda d, t: self._progress(_i18n.t("Refining the cells that decide it: {done} of {total} games", done=d, total=t), d, t,
                                               "refine"))
        row = next((o for o in (dd.get("result") or {}).get("opponents") or [] if o.get("id") == opp), {})
        return {"dd": dd["id"], "opp": opp, "species": row.get("species") or [s["species"] for s in theirs], "team": [s["species"] for s in mine],
                "model": (dd.get("result") or {}).get("model"), "games": int(m.played.sum()), "brings": m.summary()}

    def _progress(self, msg: str, done: float | None = None, total: float | None = None, phase: str | None = None) -> None:



        job = getattr(self, "_job", None)
        if job is None:
            return
        if job.get("cancel"):
            raise Cancelled()
        meta = job.get("progress_meta") or {}
        key = phase or msg
        now = time.time()
        if meta.get("phase") != key:
            meta = {"phase": key, "t0": now, "t_done": now}
        if done is not None and done != meta.get("done"):
            meta["t_done"] = now
        meta.update(done=done, total=total)
        job["progress_meta"], job["progress"] = meta, msg

    def _run_sixth(self, five: list[dict], params: dict, fld: list, weights, field: str, ckpt, baseline=None, mode=(48, 4000, False),
                   fmt: str | None = None) -> dict:



        import torch
        from vgc_suite.core.sixth import clash, field_candidates, sweep
        from vgc_suite.core.teams import lookup_team
        from vgc_suite.formats import CURRENT, engine, get as get_format
        fmt = fmt or CURRENT
        cands = []
        paste = (params.get("candidates") or "").strip()
        if paste and engine(fmt) is not None:
            from vgc_suite.core.teams import read_team, validated_sets
            from vgc_trainer.showdown.teams import to_paste
            try:
                parsed = validated_sets(paste if "\n" in paste else paste + "\n", engine(fmt), parse_only=True)
            except ValueError as e:
                raise BadInput(_i18n.t("Couldn't read your candidate sets: {error}", error=e)) from None
            merged = [s.get("name") or s["species"] for s in parsed if len(s.get("moves") or []) > 4]
            if merged:
                raise BadInput(_i18n.t("{list}: more than four moves - two sets ran together? Put a blank line between sets.", list=', '.join(merged)))
            for s in parsed:
                label = s.get("name") or s["species"]
                if clash(five, s):
                    cands.append((label, "yours", s))
                    continue
                try:
                    cands.append((label, "yours", read_team(to_paste(five + [s]), fmt)[-1]))
                except ValueError as e:
                    raise BadInput(_i18n.t("Candidate {label}: {error}", label=label, error=e)) from None
        elif paste:
            try:
                cands += [(s.get("name") or s["species"], "yours", s) for s in lookup_team(paste if "\n" in paste else paste + "\n")]
            except Exception as e:
                raise BadInput(_i18n.t("Couldn't read your candidate sets: {error}", error=e)) from e
            merged = [c[0] for c in cands if len(c[2].get("moves") or []) > 4]
            if merged:
                raise BadInput(_i18n.t("{list}: more than four moves - two sets ran together? Put a blank line between sets.", list=', '.join(merged)))
            from vgc_suite.core.teams import legal_mc
            for k, (label, src, s) in enumerate(cands):
                try:
                    cands[k] = (label, src, legal_mc([s], partial=True)[0][0])
                except ValueError as e:
                    raise BadInput(_i18n.t("Candidate {label}: {error}", label=label, error=e)) from None
        top = _int(params, "field_top", 8, LIMITS["sixth_field_top"]) if params.get("field_cands") == "1" else 0
        usage_note = None
        if top:
            skip = {c[2]["species"] for c in cands} | ({baseline[1]["species"]} if baseline else set())
            kind = params.get("field_kind") if params.get("field_kind") in ("mega", "plain") and get_format(fmt).megas else "any"
            if params.get("field_src") == "smogon" and engine(fmt) is not None:
                raise BadInput(_i18n.t("Ladder usage (Smogon) candidates are Reg M-C only - take the field's most used Pokémon instead."))
            if params.get("field_src") == "smogon":
                from vgc_suite.core import smogon_usage
                got, month = smogon_usage.candidates(five, top, skip=skip, kind=kind)
                if month is None:
                    raise BadInput(_i18n.t("No Smogon usage data for this format in this install (data/smogon-usage/)."))
                cands += [(sp, "usage", s) for sp, s in got]
                usage_note = f"Smogon usage stats {month}, Reg M-C ladder 1630+ (smogon.com/stats, from Pokémon Showdown's ladder)"
            else:
                cands += [(sp, "field", s) for sp, s in field_candidates(five, fld, weights, top, skip=skip, kind=kind)]
        if not cands:
            raise BadInput(_i18n.t("Candidates needed: paste some sets, or tick the field's most used Pokémon."))
        if len(cands) > LIMITS["sixth_candidates"]:
            raise BadInput(_i18n.t("At most {sixth_candidates} candidates in one run (this one has {n}).", sixth_candidates=LIMITS['sixth_candidates'], n=len(cands)))
        search_games, quick_games, fast = mode
        top = _int(params, "robust_top", 4, LIMITS["sixth_robust_top"]) if params.get("robust_top", "4") != "0" and not fast else 0
        res = sweep(five, cands, fld, ckpt, games=quick_games, dev=torch.device(self.device),
                    weights=weights, field_name=f"bucket {field[7:]}" if field.startswith("bucket:") else "Current Metagame" if field == "meta" else field, progress=self._progress,
                    baseline=baseline,
                    brings_agent=self._agent()[0] if top else None, robust_top=top,
                    robust_games=_int(params, "brings_games", 256, LIMITS["brings_games"]),
                    search_games=search_games, fmt=fmt)
        if usage_note and "error" not in res:
            res["usage_note"] = usage_note
        if "error" not in res:
            res["format"], res["format_name"] = fmt, get_format(fmt).short
        return res

    def _run_h2h(self, params: dict) -> dict:
        import torch
        from vgc_suite.core.h2h import run_h2h
        from vgc_suite.core.teams import read_team
        from vgc_suite.formats import engine, tool_format
        try:
            fmt = tool_format(params.get("format"))
        except ValueError as e:
            raise BadInput(str(e)) from None
        agent, ckpt = self._agent()
        a, b = _team_src(params["a"]), _team_src(params["b"])
        temp = 3.0 if params.get("vary") == "3" else 1.0

        deep = params.get("deep") == "1" or (not params.get("_checks") and ENV.globals["gpu"]["on"])

        matrix = params.get("matrix") == "1" or (not params.get("_checks") and ENV.globals["gpu"]["on"])
        games = max(200, _int(params, "games", 400 if deep else 4000, LIMITS["h2h_deep_games"] if deep else LIMITS["h2h_games"]))
        ta, tb = _legal(_read(a, fmt, "Team A"), "Team A", fmt), _legal(_read(b, fmt, "Team B"), "Team B", fmt)
        rep = run_h2h(ta, tb, ckpt, games=games, deep=deep, fmt=fmt,
                      examples=min(_int(params, "examples", 0, LIMITS["h2h_examples"]), LIMITS["h2h_examples"]) if params.get("examples", "0") != "0" else 0,
                      dev=torch.device(self.device), agent=agent if matrix else None,
                      ids=(a if "\n" not in a else "Team A", b if "\n" not in b else "Team B"),
                      bring_temp=temp, bo3=params.get("bo3") == "1", progress=self._progress)
        if params.get("luck") == "1" and "error" not in rep:
            from vgc_suite.core.entropy import matchup
            from vgc_suite.core.validator import _ready
            try:
                rep["luck"] = matchup(_ready(ta, fmt), _ready(tb, fmt), ckpt, probe_games=128, dev=torch.device(self.device), fmt=engine(fmt))
            except Exception as e:
                rep["luck_error"] = f"{type(e).__name__}: {e}"
        return rep


class BadInput(ValueError):
    pass





REPLAY_HOSTS = ("replay.pokemonshowdown.com",)
REPLAY_DIR = ROOT / "replays"
REPLAY_KINDS = (".html", ".htm", ".log", ".txt")


def replay_files(n: int = 30) -> list[dict]:

    try:
        fs = [p for p in REPLAY_DIR.iterdir() if p.is_file() and p.suffix.lower() in REPLAY_KINDS and p.name != "README.txt"]
    except OSError:
        return []
    fs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "when": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))} for p in fs[:n]]


def _replay_file(name: str) -> str:

    p = REPLAY_DIR / name
    if Path(name).name != name or p.suffix.lower() not in REPLAY_KINDS or not p.is_file():
        raise BadInput(_i18n.t("That replay isn't in the replays folder."))
    return p.read_text(encoding="utf8", errors="replace")


def open_replay_folder() -> None:
    REPLAY_DIR.mkdir(exist_ok=True)
    if sys.platform == "win32":
        os.startfile(REPLAY_DIR)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(REPLAY_DIR)])


def _line_name(job: dict) -> str:

    if job.get("tool") != "analyze" or job.get("status") != "done":
        return ""
    from vgc_suite import lines
    return lines.default_name()


REPLAY_ID = re.compile(r"(?:battle-)?([a-z0-9]+-\d+(?:-[a-z0-9]+pw)?)")


def _replay_link(text: str) -> str:



    t = text.strip()
    bare = t.removeprefix("https://").removeprefix("http://")
    host, _, rest = bare.partition("/")
    rest = rest.split("?")[0].split("#")[0].rstrip("/")
    if host in ("replay.pokemonshowdown.com", "psim.us", "play.pokemonshowdown.com") and REPLAY_ID.fullmatch(rest.lower()):
        return "https://replay.pokemonshowdown.com/" + REPLAY_ID.fullmatch(rest.lower()).group(1)
    if "/" not in t and REPLAY_ID.fullmatch(t.lower()):
        return "https://replay.pokemonshowdown.com/" + REPLAY_ID.fullmatch(t.lower()).group(1)
    return text


def _report_of(text: str) -> dict | None:

    t = (text or "").strip()
    if not t.startswith("{") or "openvgc-report" not in t[:200]:
        return None
    try:
        d = json.loads(t)
    except ValueError:
        return None
    return d if isinstance(d, dict) and d.get("kind") == "openvgc-report" and isinstance(d.get("job"), dict) else None


def _renarrated(job: dict) -> dict | None:



    r = job.get("result") or {}
    turns = (r.get("narration") or {}).get("turns") or []
    if not any(isinstance(e, dict) and "text" in e and "msg" not in e for t in turns for e in t.get("events", [])):
        return None
    try:
        src = _replay_src(job["params"]["replay"])
        if src.startswith(("http://", "https://")):
            return None
        from vgc_suite.core.replay import load_replay
        from vgc_suite.game_views import view_from_lines
        v = view_from_lines(load_replay(src).lines, r["narration"]["me"], [])
    except Exception:
        return None
    new = {t["turn"]: t["events"] for t in v["turns"]}
    return {**r, "narration": {**r["narration"], "turns": [{**t, "events": new.get(t["turn"], t["events"])} for t in turns]}}


def _replay_src(text: str) -> str:
    rep = _report_of(text)
    if rep is not None:
        text = rep.get("replay_log") or ((rep["job"].get("params") or {}).get("replay") or "")
        if _report_of(text) is not None:
            raise BadInput(_i18n.t("That report file holds no replay."))
    text = _replay_link(text).strip()
    if text.startswith("room:"):
        from vgc_suite.game_views import game_log
        log = game_log(text[5:])
        if log is None:
            raise BadInput(_i18n.t("That game's log isn't on this PC."))
        return log
    if text.startswith("file:"):
        text = _replay_file(text[5:].strip()).strip()
    elif text.startswith(("http://", "https://")):
        u = urlparse(text)
        if u.hostname not in REPLAY_HOSTS or "\n" in text:
            raise BadInput(_i18n.t("Only replay.pokemonshowdown.com links work here (or open a downloaded replay file)."))
        return text
    if "battle-log-data" in text or any(ln.startswith("|") for ln in text.splitlines()):
        return text
    if "Battle started between" in text or "\nTurn 1" in text:
        raise BadInput(_i18n.t("That's the text from the battle window, which the Analyzer can't read. Use the game's replay link (Upload and Share in Showdown), or a downloaded replay."))
    raise BadInput(_i18n.t("Paste a replay.pokemonshowdown.com link, or open a downloaded replay file."))


PACE_FILE = ROOT / "trainer/runs/web_progress_pace.json"
_PACE: dict = {}


def _pace(ph: str, per: float | None = None) -> float | None:



    if not _PACE and PACE_FILE.exists():
        try:
            _PACE.update(json.loads(PACE_FILE.read_text(encoding="utf8")))
        except (OSError, ValueError):
            pass
    if per is not None and per > 0 and abs(per - _PACE.get(ph, 0)) > 0.05 * per:
        _PACE[ph] = round(per, 3)
        try:
            PACE_FILE.write_text(json.dumps(_PACE, indent=1), encoding="utf8")
        except OSError:
            pass
    return _PACE.get(ph)


def _bar(meta: dict | None) -> dict | None:




    if not meta or meta.get("done") is None or not meta.get("total"):
        return None
    now = time.time()
    done, total = float(meta["done"]), float(meta["total"])
    t0, t_done = meta.get("t0", now), meta.get("t_done", now)
    key = str(meta.get("phase") or "")
    who, _, ph = key.rpartition(" · ")
    left, frac, busy = None, max(0.0, min(1.0, done / total)), False
    if ph.endswith("-tail"):

        return {"frac": round(min(frac, 0.97), 4), "left": None, "what": PHASE_NAMES.get(ph, "this part"), "busy": True}
    per = (t_done - t0) / done if done > 0 and t_done - t0 > 3 else None
    if per is not None:
        _pace(ph, per)
    else:
        per, t_done = _pace(ph), t0
        busy = per is None
    if per:
        into = min((now - t_done) / per, 0.95)
        frac = max(0.0, min(1.0, (done + into) / total))
        left = max(per * (total - done) - (now - t_done), per * max(total - done - 1, 0), 0.0)


    what = PHASE_NAMES.get(ph) or "this part"
    return {"frac": round(frac, 4), "left": None if left is None else round(left), "what": f"{who}: {what}" if who else what,
            "busy": busy}


PHASE_NAMES = {"search": "the searched games", "search-tail": "the last long games", "games": "the self-play games", "brings": "the bring matrices", "fast": "the candidates' games",
               "robust": "the both-adapt pass", "examples": "the example games"}


def _legal(sets: list[dict], who: str, fmt: str | None = None) -> list[dict]:


    from vgc_suite.core.teams import legal
    try:
        return legal(sets, fmt)[0]
    except ValueError as e:
        raise BadInput(_i18n.t("{who}: {error}", who=_i18n.t(who), error=e)) from None


def _sheets_open(params: dict) -> bool:

    if params.get("sheets") != "open":
        return False
    from vgc_suite.formats import FORMATS, tool_format
    from vgc_trainer.closed_worlds import supported
    try:
        fmt = tool_format(params.get("format"))
    except ValueError:
        return False
    return not FORMATS[fmt].open_sheets and supported()

def _guess_paste(sets: list[dict], fmt: str | None) -> str:



    import copy
    from vgc_suite.core.teams import read_team
    from vgc_trainer.showdown.teams import to_paste
    sets = copy.deepcopy(sets)
    for _ in range(len(sets) + 1):
        text = to_paste(sets)
        try:
            read_team(text, fmt)
            return text
        except (ValueError, KeyError) as e:
            fixes = re.findall(r"([\w .'-]+?) must have an? (\w+) nature", str(e))
            changed = False
            for who, nature in fixes:
                for st in sets:
                    if who.strip() in (st.get("name"), st.get("species")) and st.get("nature") != nature:
                        st["nature"], changed = nature, True
            if not changed:
                return text
    return to_paste(sets)


def _read(spec: str, fmt: str | None, who: str) -> list[dict]:

    from vgc_suite.core.teams import read_team
    from vgc_suite.formats import engine
    if engine(fmt) is None:
        return read_team(spec, fmt)
    try:
        return read_team(spec, fmt)
    except (ValueError, KeyError) as e:
        raise BadInput(_i18n.t("{who}: {error}", who=_i18n.t(who), error=e)) from None


FAV_FILE = ROOT / "trainer/runs/web_favorites.json"


def favorites() -> dict[str, dict]:
    try:
        return json.loads(FAV_FILE.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return {}


def set_favorite(jid: str, on: bool, note: str = "") -> dict:
    favs = favorites()
    if on:
        favs[jid] = {"note": note.strip()[:80], "at": time.time()}
    else:
        favs.pop(jid, None)
    tmp = FAV_FILE.with_suffix(".part")
    tmp.write_text(json.dumps(favs, indent=1), encoding="utf8")
    tmp.replace(FAV_FILE)
    return favs.get(jid) or {}


_MXCHECKS: dict[str, tuple[float, tuple | None]] = {}


def mxchecks() -> dict[tuple[str, str], dict]:



    out: dict[tuple[str, str], dict] = {}
    for f in JOB_DIR.glob("*.json"):
        t = f.stat().st_mtime
        hit = _MXCHECKS.get(f.name)
        if hit is None or hit[0] != t:
            try:
                j = json.loads(f.read_text(encoding="utf8"))
                p = j.get("params") or {}
                hit = (t, (p.get("dd"), p.get("opp"), j["id"], j.get("status"), j.get("created") or 0)) if j.get("tool") == "mxcheck" else (t, None)
            except (OSError, ValueError, KeyError):
                hit = (t, None)
            _MXCHECKS[f.name] = hit
        if hit[1] and hit[1][3] in ("done", "queued", "running"):
            dd, opp, jid, st, created = hit[1]
            cur = out.get((dd, opp))
            if cur is None or ((st == "done", created) > (cur["status"] == "done", cur["created"])):
                out[(dd, opp)] = {"id": jid, "status": st, "created": created}
    return out


def mxsearches() -> dict[tuple[str, str], dict]:

    out: dict[tuple[str, str], dict] = {}
    for f in JOB_DIR.glob("*.json"):
        if f.stat().st_size > 2_000_000:
            continue
        try:
            j = json.loads(f.read_text(encoding="utf8"))
        except (OSError, ValueError):
            continue
        p = j.get("params") or {}
        if j.get("tool") == "mxsearch" and j.get("status") in ("done", "queued", "running"):
            key = (p.get("dd"), p.get("opp"))
            if key not in out or j["status"] == "done":
                out[key] = {"id": j["id"], "status": j["status"]}
    return out


_PASTES: dict[str, str | None] = {}


def team_paste(spec: str | None) -> str | None:


    spec = (spec or "").strip()
    if not spec:
        return None
    if spec not in _PASTES:
        from vgc_suite.core.teams import lookup_team
        from vgc_trainer.showdown.teams import to_paste
        try:
            _PASTES[spec] = to_paste(lookup_team(_team_src(spec)))
        except BaseException:
            _PASTES[spec] = None
    return _PASTES[spec]


def sweep_six_paste(job: dict | None, row: dict) -> str | None:


    if row.get("six_paste"):
        return row["six_paste"]
    r, text = (job or {}).get("result") or {}, ((job or {}).get("params") or {}).get("team", "")
    if not text or not row.get("paste"):
        return None
    key = f"{text}\n\n#six {row['label']}"
    if key not in _PASTES:
        from vgc_suite.core.teams import lookup_team
        from vgc_trainer.showdown.teams import to_paste
        try:
            team = lookup_team(_team_src(text))
            gone = (r.get("slot") or {}).get("replaced")
            if row.get("source") != "current":
                if gone:
                    team = [m for m in team if (m.get("name") or m["species"]) != gone]
                team = team + lookup_team(row["paste"].strip() + "\n")
            _PASTES[key] = to_paste(team) if len(team) == 6 else None
        except BaseException:
            _PASTES[key] = None
    return _PASTES[key]


def dd_team_paste(job: dict | None, opp: str) -> str | None:

    pair = _deepdive_matchup(job, opp)
    return team_paste(pair[1]) if pair else None


def _with_notes(res: dict, notes: list[str]) -> dict:

    if notes and isinstance(res, dict) and "error" not in res:
        res["caveats"] = list(res.get("caveats") or []) + notes
    return res


def _deepdive_matchup(job: dict | None, opp: str, sixth: str = "") -> tuple[str, str] | None:


    if not job or job.get("tool") != "validate" or not opp:
        return None
    mine = (job.get("params") or {}).get("team", "")
    if sixth:
        row = next((r for r in ((job.get("result") or {}).get("rows") or []) if r.get("label") == sixth), None)
        if row is None or not row.get("paste"):
            return None
        mine = mine.rstrip() + "\n\n" + row["paste"]
    field = (job.get("params") or {}).get("field", "")
    theirs = opp
    if field.startswith("bucket:"):
        from vgc_suite.core import buckets
        try:
            theirs = next(t["src"] for t in buckets.get(field[7:])["teams"] if t["label"] == opp)
        except (KeyError, StopIteration):
            return None
    elif field == "meta":
        from vgc_suite.core.validator import META_FIELD
        try:
            theirs = next(t["src"] for t in json.loads(META_FIELD.read_text(encoding="utf8"))["teams"] if t["label"] == opp)
        except (OSError, ValueError, StopIteration):
            return None
    return mine, theirs


def _playout_brings(job: dict | None, opp: str, cell_row: str = "", cell_col: str = "") -> dict:



    row = next((o for o in ((job or {}).get("result") or {}).get("opponents") or [] if o.get("id") == opp), None)
    b = (row or {}).get("brings")
    if not b:
        return {"pick": "bots"}
    heavy = lambda opts, mix: opts[max(range(len(mix)), key=lambda i: mix[i])]["bring"]
    mine, theirs = heavy(b["mine"], b["equilibrium"]["mine"]), heavy(b["theirs"], b["equilibrium"]["theirs"])
    if cell_row.isdigit() and cell_col.isdigit() and int(cell_row) < len(b["mine"]) and int(cell_col) < len(b["theirs"]):
        mine, theirs = b["mine"][int(cell_row)]["bring"], b["theirs"][int(cell_col)]["bring"]
    return {"pick": "you", "full": "1", **{f"a{k + 1}": str(i) for k, i in enumerate(mine)},
            **{f"b{k + 1}": str(i) for k, i in enumerate(theirs)}}


def _team_src(text: str) -> str:
    text = text.strip()
    if "\n" in text:
        return text
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", text) or Path(text).exists():
        raise BadInput(_i18n.t("Paste a Showdown team export, or give a team id from the library (e.g. BR-111).") if _has_library()
                       else _i18n.t("Paste a Showdown team export."))
    return text



TEAM_FIELDS = {"preview": [("A", "mine"), ("B", "theirs")], "h2h": [("A", "a"), ("B", "b")], "playout": [("A", "a"), ("B", "b")],
               "validate": [("team", "team"), ("reference", "reference")], "fieldplay": [("team", "team")],
               "analyze": [("P1", "paste_p1"), ("P2", "paste_p2")]}
SWAP = {"preview": [("mine", "theirs"), ("name_a", "name_b")], "h2h": [("a", "b")],
        "playout": [("a", "b"), ("name_a", "name_b"), ("a1", "b1"), ("a2", "b2"), ("a3", "b3"), ("a4", "b4")]}
_SPECIES: dict[str, list[str]] = {}


def team_species(text: str) -> list[str]:


    text = (text or "").strip()
    if not text:
        return []
    if text not in _SPECIES:
        sp = []
        if "\n" in text:
            for block in re.split(r"\n\s*\n", text.replace("\r", "")):
                line = block.strip().split("\n")[0] if block.strip() else ""
                head = line.split("@")[0].strip()
                head = re.sub(r"\((M|F)\)\s*$", "", head).strip()
                m = re.search(r"\(([^()]+)\)\s*$", head)
                if head:
                    sp.append(m.group(1).strip() if m else head)
        else:
            try:
                from vgc_suite.core.teams import lookup_team
                sp = [x["species"] for x in lookup_team(_team_src(text))]
            except BaseException:
                sp = []
        _SPECIES[text] = sp[:6]
    return _SPECIES[text]


def run_teams(tool: str, params: dict) -> list[dict]:

    out = []
    for label, key in TEAM_FIELDS.get(tool, []):
        v = (params.get(key) or "").strip()
        if v:
            out.append({"label": params.get({"mine": "name_a", "theirs": "name_b"}.get(key, ""), "") or label,
                        "species": team_species(v), "id": None if "\n" in v else v})
    return out


def _forced_turn1(params: dict, side: str, names: list[str], bring: list[int], foe_leads: list[str]):


    raw = [params.get(f"{side}f{k}", "") for k in (1, 2)]
    if not any(raw):
        return None
    if not all(raw):
        raise BadInput(_i18n.t("Team {side}: set both leads' turn-1 actions, or leave both to the bot.", side=side.upper()))
    slots, labels = [], []
    for k, v in enumerate(raw):
        kind, *rest = v.split("|")
        if kind == "switch":
            i = int(rest[0])
            if i not in bring[2:]:
                raise BadInput(_i18n.t("Team {side}: a turn-1 switch must go to one of the two in the back.", side=side.upper()))
            slots.append({"switch": i})
            labels.append(f"switch {names[i]}")
        else:
            mv, tgt = rest[0], (rest[1] if len(rest) > 1 else "") or None
            mega = params.get(f"{side}m{k + 1}") == "1"
            slots.append({"move": mv, "target": tgt, "mega": mega})
            to = {"foe1": foe_leads[0], "foe2": foe_leads[1], "ally": names[bring[1 - k]]}.get(tgt or "")
            labels.append(mv + (f" -> {to}" if to else "") + (" +mega" if mega else ""))
    if all("switch" in x for x in slots) and slots[0]["switch"] == slots[1]["switch"]:
        raise BadInput(_i18n.t("Team {side}: the two leads can't switch to the same Pokemon.", side=side.upper()))
    return slots, labels


def _with_turn2(params: dict, side: str, names: list[str], bring: list[int], f1):



    raw = [params.get(f"{side}2f{k}", "") for k in (1, 2)]
    if not any(raw):
        return f1
    if not all(raw):
        raise BadInput(_i18n.t("Team {side}: set both slots' turn-2 actions, or leave turn 2 to the bot.", side=side.upper()))
    if not f1:
        raise BadInput(_i18n.t("Team {side}: a forced turn 2 needs a forced turn 1 (the slots' occupants follow from it).", side=side.upper()))
    slots, labels = [], []
    for k, v in enumerate(raw):
        kind, mon, *rest = v.split("|")
        who = names[int(mon)]
        if kind == "switch":
            slots.append({"mon": who, "switch": int(rest[0])})
            labels.append(f"{who}: switch {names[int(rest[0])]}")
        else:
            mv, tgt = rest[0], (rest[1] if len(rest) > 1 else "") or None
            mega = params.get(f"{side}2m{k + 1}") == "1"
            slots.append({"mon": who, "move": mv, "target": tgt, "mega": mega})
            to = {"foe1": "their left", "foe2": "their right", "ally": "ally"}.get(tgt or "")
            labels.append(f"{who}: {mv}" + (f" -> {to}" if to else "") + (" +mega" if mega else ""))
    return (f1[0], f1[1], slots, labels)


def _move_targets() -> dict[str, str]:

    if not _TARGETS:
        ids = {}
        for path in ("vendor/pokemon-showdown/data/moves.ts", "vendor/pokemon-showdown/data/mods/champions/moves.ts"):
            cur = None
            for ln in (ROOT / path).read_text(encoding="utf8").splitlines():
                m = re.match(r"^\t([a-z0-9]+): \{", ln)
                if m:
                    cur = m.group(1)
                    continue
                m = re.match(r'^\t\tname: "(.*)",', ln)
                if m and cur:
                    ids[cur] = m.group(1)
                m = re.match(r'^\t\ttarget: "(\w+)",', ln)
                if m and cur in ids:
                    _TARGETS[ids[cur]] = m.group(1)
    return _TARGETS


_TARGETS: dict[str, str] = {}


def team_sheet_info(text: str) -> list[dict]:

    from vgc_suite.core.teams import lookup_team
    text = (text or "").strip()
    try:
        team = lookup_team(_team_src(text)) if text else []
    except Exception:
        return []
    tg = _move_targets()
    return [{"name": m.get("name") or m["species"], "moves": [{"name": mv, "t": tg.get(mv, "")} for mv in m.get("moves", [])],
             "mega": bool(re.search(r"ite( [XYZ])?$", m.get("item") or "")) and m.get("item") != "Eviolite"} for m in team]


def team_sheet_names(text: str) -> list[str]:

    from vgc_suite.core.teams import lookup_team
    text = (text or "").strip()
    if text not in _NAMES:
        try:
            _NAMES[text] = [m.get("name") or m["species"] for m in lookup_team(_team_src(text))] if text else []
        except Exception:
            _NAMES[text] = []
    return _NAMES[text]


_NAMES: dict[str, list[str]] = {}


def _preview_sheets(job: dict) -> dict | None:

    from vgc_suite.core.teams import lookup_team
    if job["id"] not in _SHEETS:
        try:
            _SHEETS[job["id"]] = {s: [m.get("name") or m["species"] for m in lookup_team(_team_src(job["params"][k]))]
                                  for s, k in (("a", "mine"), ("b", "theirs"))}
        except Exception:
            _SHEETS[job["id"]] = None
    return _SHEETS[job["id"]]


_SHEETS: dict[str, dict | None] = {}


def crawler_tree(data: dict, cur: str) -> tuple[list[dict], list[str]]:


    nodes = data["nodes"]
    kids: dict = {}
    for k, n in nodes.items():
        kids.setdefault(n["parent"], []).append(k)
    path, k = [], cur
    while k is not None and k in nodes:
        path.append(k)
        k = nodes[k]["parent"]
    path.reverse()
    rows = []

    def walk(k: str, depth: int, turn: int) -> None:
        n = nodes[k]
        t = turn + (1 if n.get("kind") == "turn" else 0)
        chose = [ln.split(" chose ", 1)[1] for ln in n.get("log", []) if " chose " in ln]
        fainted = [ln.replace(" fainted", "") for ln in n.get("log", []) if ln.endswith(" fainted")]
        rows.append({"id": k, "depth": depth, "turn": t, "kind": n.get("kind"), "on_path": k in path, "current": k == cur,
                     "summary": " / ".join(chose), "fainted": fainted, "over": any(ln.startswith("the game is over") for ln in n.get("log", []))})
        for c in sorted(kids.get(k, []), key=int):
            walk(c, depth + (1 if len(kids.get(k, [])) > 1 else 0), t)

    walk("0", 0, 0)
    return rows, path


def crawler_sessions(n: int = 12) -> list[dict]:
    from vgc_suite.core.crawler import DIR
    out = []
    for f in sorted(DIR.glob("*.json"), reverse=True)[:n] if DIR.exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf8"))
        except (OSError, ValueError):
            continue
        out.append({"id": d["id"], "names": d.get("names") or {}, "nodes": len(d.get("nodes") or {}), "created": d.get("created"),
                    "leads": [[d["teams"][s][i].get("name") or d["teams"][s][i]["species"] for i in d["brings"][s]] for s in (0, 1)]})
    return out


def _turn1_bring(params: dict, side: str, options: list[dict], sheet: list[dict]) -> tuple[dict, int | None]:



    key = "ai" if side == "a" else "bi"
    if params.get(key) != "c":
        i = _int(params, key, 1, len(options)) - 1
        return options[i], i
    try:
        bring = [int(params.get(f"{side}{k}", "")) for k in (1, 2, 3, 4)]
    except ValueError:
        raise BadInput(_i18n.t("Pick two leads and two in the back for a custom bring.")) from None
    if len(set(bring)) != 4 or not all(0 <= i < len(sheet) for i in bring):
        raise BadInput(_i18n.t("A custom bring needs four different Pokemon from the team."))
    name = [sheet[i].get("name") or sheet[i]["species"] for i in bring]
    same = next((i for i, o in enumerate(options) if set(o["bring"][:2]) == set(bring[:2]) and set(o["bring"][2:]) == set(bring[2:])), None)
    return {"lead": name[:2], "back": name[2:], "bring": bring, "custom": True}, same


def _int(params: dict, key: str, default: int, hi: int) -> int:
    try:
        return max(1, min(hi, int(params.get(key) or default)))
    except ValueError:
        return default




def win_curve_svg(curves: dict, players: dict, w: int = 640, h: int = 190) -> dict:

    turns = [t for pts in curves.values() for t, _ in pts]
    if not turns:
        return {"w": w, "h": h, "lines": [], "ticks": []}
    lo, hi = min(turns), max(max(turns), min(turns) + 1)
    pad_l, pad_r, pad_t, pad_b = 36, 12, 12, 26
    x = lambda t: pad_l + (t - lo) / (hi - lo) * (w - pad_l - pad_r)
    y = lambda v: pad_t + (1 - v) * (h - pad_t - pad_b)
    lines = [{"side": s, "name": players.get(s, s), "points": " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in pts),
              "dots": [(round(x(t), 1), round(y(v), 1), t, v) for t, v in pts]} for s, pts in curves.items()]
    step = max(1, (hi - lo) // 10)
    return {"w": w, "h": h, "lines": lines, "ticks": [(round(x(t), 1), t) for t in range(lo, hi + 1, step)],
            "y50": round(y(0.5), 1), "y0": round(y(0), 1), "y1": round(y(1), 1), "pad_l": pad_l, "right": w - pad_r}


def line_chart(series: list[tuple[str, str, list[tuple[float, float]]]], x_labels: list[tuple[float, str]] | None = None,
               w: int = 640, h: int = 180, y_fmt: str = "{:.0f}", y_range: tuple[float, float] | None = None):


    from markupsafe import Markup

    pts = [p for _, _, ps in series for p in ps if p[1] is not None]
    if len(pts) < 2:
        return Markup('<p class="small muted">Not enough points for a chart yet.</p>')
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    if y_range:
        y0, y1 = y_range
    else:
        y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
        pad = max((y1 - y0) * 0.08, 1e-9)
        y0, y1 = y0 - pad, y1 + pad
    L, R, T, B = 46, 10, 10, 24

    def X(x):
        return L + (x - x0) / max(x1 - x0, 1e-9) * (w - L - R)

    def Y(y):
        return T + (1 - (y - y0) / max(y1 - y0, 1e-9)) * (h - T - B)

    parts = [f'<svg class="curve" viewBox="0 0 {w} {h}" role="img">']
    for frac in (0, 0.5, 1):
        yv = y0 + frac * (y1 - y0)
        parts.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}" stroke="#e5e6dd" stroke-width="1"/>'
                     f'<text x="4" y="{Y(yv) + 4:.1f}" font-size="11" fill="#676860">{y_fmt.format(yv)}</text>')
    for x, text in (x_labels or []):
        parts.append(f'<text x="{X(x):.1f}" y="{h - 6}" font-size="11" fill="#676860" text-anchor="middle">{text}</text>')
    for name, colour, ps in series:
        ps = [p for p in ps if p[1] is not None]
        if not ps:
            continue
        d = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in ps)
        parts.append(f'<polyline points="{d}" fill="none" stroke="{colour}" stroke-width="2.5" stroke-linejoin="round"/>')
        lx, ly = ps[-1]
        parts.append(f'<circle cx="{X(lx):.1f}" cy="{Y(ly):.1f}" r="3.5" fill="{colour}"><title>{name}: {y_fmt.format(ly)}</title></circle>')
    parts.append("</svg>")
    legend = " ".join(f'<span class="small"><span style="display:inline-block;width:12px;height:4px;background:{c};vertical-align:middle"></span> {n}</span>'
                      for n, c, _ in series)
    return Markup("".join(parts) + f'<div class="legend">{legend}</div>')


def pct(v) -> str:
    return "-" if v is None else f"{100 * float(v):.1f}%"


def pct0(v) -> str:
    return "-" if v is None else f"{100 * float(v):.0f}%"


def status_page(rep_h: float = 6) -> dict:
    from vgc_suite.status import gather, repeats

    d = gather()
    if rep_h != 6:
        d = {**d, "repeats_update": repeats(d["repeats_since"], rep_h), "repeats_all": repeats("2026-10-08 00:00:00", rep_h)}

    cutoff = time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - 24 * 3600))
    rp = [p for p in d["ladder_all"]["rating_pts"] if p.get("t", "") >= cutoff]


    now = time.time()

    def hrs(t: str) -> float:
        return 24 - (now - time.mktime(time.strptime(t, "%Y-%m-%d %H:%M"))) / 3600

    pts = [(hrs(p["t"]), p["elo"]) for p in rp]
    if pts:
        pts.append((24.0, pts[-1][1]))
    ticks = [(24 - (now - t) / 3600, time.strftime("%H:%M", time.localtime(t)))
             for t in range(int((now - 24 * 3600) // 10800 + 1) * 10800, int(now), 10800)]
    top = max([1800] + [int(e // 100 + 1) * 100 for _, e in pts])
    rating_chart = line_chart([("Elo, last 24 h", "#a06146", pts)], ticks if pts else None, y_range=(1200, top))


    reads = [r for r in ((d.get("ml1") or {}).get("read_table") or []) if r.get("rows")]
    def mean_elo(r, keys, ref):
        v = [r["rows"][k][ref]["elo"] for k in keys if ref in r["rows"].get(k, {})]
        return round(sum(v) / len(v)) if v else None
    old = [f"VGC{n}" for n in range(13, 20)]
    sv = ["SV regc", "SV regd", "SV regg", "SV regi"]
    start_u = 217250
    gauntlet_chart = line_chart(
        [("Reg M-C vs the baseline", "#7c5f4a", [(r["update"], (r["rows"].get("M-C", {}).get("mx1") or {}).get("elo")) for r in reads]),
         ("VGC13-19 vs box start (mean)", "#aadc26", [(start_u, 0)] + [(r["update"], mean_elo(r, old, "start")) for r in reads]),
         ("SV Reg C/D/G/I vs box start (mean)", "#5aa9e6", [(start_u, 0)] + [(r["update"], mean_elo(r, sv, "start")) for r in reads])],
        [(start_u, "217k")] + [(r["update"], f"{r['update'] / 1000:.1f}k") for r in reads]) if reads else None
    from vgc_suite.status import team_tables

    rotation, rotated_out = team_tables(d)
    from vgc_suite.team_stats import arena_summary, recent_challenges, recent_series

    return {"d": d, "rating_chart": rating_chart, "gauntlet_chart": gauntlet_chart, "pct": pct, "rotation": rotation,
            "rotated_out": rotated_out, "recent_series": recent_series(60), "challenges": recent_challenges(25),
            "arena": arena_summary(30)}


def tier_class(tier: str | None) -> str:
    return {"agrees": "t-agree", "close alternative": "t-close", "model prefers another": "t-other",
            "model strongly prefers another": "t-strong"}.get(tier or "", "t-none")


def heat(v: float) -> str:

    lo, mid, hi = (250, 168, 166), (245, 234, 223), (187, 227, 82)
    a, b, f = (lo, mid, v * 2) if v < 0.5 else (mid, hi, (v - 0.5) * 2)
    return "rgb({},{},{})".format(*(round(a[i] + (b[i] - a[i]) * f) for i in range(3)))


ENV = Environment(loader=FileSystemLoader(WEB / "templates"), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
def _smogon_month() -> str | None:

    from vgc_suite.core import smogon_usage
    got = smogon_usage.cached()
    return got[0] if got else None


ENV.filters["pct"] = lambda v: "-" if v is None else f"{v:.0%}"
ENV.filters["prob"] = lambda v: "-" if v is None else ("<1%" if v < 0.005 else f"{v:.0%}")
ENV.filters["tier_class"] = tier_class


def their_tags(b: dict) -> dict:



    m, mix = b["matrix"], b["equilibrium"]["theirs"]
    top = [max(row[j] for row in m) for j in range(len(m[0]))]
    safest = min(range(len(top)), key=lambda j: (top[j], j))
    rec = max(range(len(top)), key=lambda j: (round(mix[j], 3), -top[j], -j))
    return {"safest": safest, "recommended": rec}


ENV.globals["their_tags"] = their_tags
ENV.globals["replay_files"] = replay_files
from vgc_suite import formats as _formats
ENV.globals["tool_formats"] = [(f, _formats.FORMATS[f].short) for f in _formats.IN_TOOLS]
ENV.globals["format_short"] = {k: f.short for k, f in _formats.FORMATS.items()}
ENV.globals["current_format"] = _formats.CURRENT


from vgc_trainer import i18n as _i18n


def _own_addresses() -> set[str]:

    import socket
    try:
        return {a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None)}
    except OSError:
        return set()


def _tpl_t(text, **slots):



    if not any(hasattr(v, "__html__") for v in slots.values()):
        return _i18n.t(text, **slots)
    from markupsafe import Markup, escape
    out = _i18n.t(text)
    return Markup(_i18n._SLOT.sub(lambda m: str(escape(slots[m.group(1)])) if m.group(1) in slots else m.group(0), str(out)))


ENV.globals["_"] = _tpl_t

EXTRA_TITLES = {"muselfplay": "Matchup self-play", "mxcheck": "Matrix checked with search", "mxsearch": "Matchup searched", "turn1": "Turn-1 lab"}
ENV.globals["tool_title"] = lambda tool: _i18n.t((TOOLS.get(tool) or (EXTRA_TITLES.get(tool, "Turn-1 lab"),))[0])
ENV.globals["lang"] = _i18n.language
ENV.globals["languages"] = _i18n.LANGUAGES
def _names(xs, sep=", "):

    ja = _i18n.language() != "en"
    return ("、" if ja and sep == ", " else sep).join(_i18n.dex("species", x) if isinstance(x, str) else str(x) for x in xs or [])


ENV.filters["names"] = _names
ENV.filters["dex"] = lambda v, kind: _i18n.dex(kind, v) if isinstance(v, str) else v


def team_label(s: str) -> str:


    if not isinstance(s, str):
        return s
    if s in ("your pasted team", "my rotation"):
        return _i18n.t(s)
    m = re.fullmatch(r"bucket (.+) \((\d+) teams, one drawn by weight per game\)", s)
    if m:
        return _i18n.t("bucket {name} ({n} teams, one drawn by weight per game)", name=m.group(1), n=m.group(2))
    m = re.fullmatch(r"your paste \((.+)\)", s)
    if m:
        return _i18n.t("your paste ({id})", id=m.group(1))
    m = re.fullmatch(r"the (.+) bucket", s)
    return _i18n.t("the {name} bucket", name=m.group(1)) if m else s


ENV.filters["team_label"] = team_label
ENV.globals["format_open"] = {k: f.open_sheets for k, f in _formats.FORMATS.items()}
ENV.globals["format_megas"] = {k: f.megas for k, f in _formats.FORMATS.items()}


def _cts_ready() -> bool:
    from vgc_trainer.closed_worlds import supported
    return supported()


ENV.globals["cts_ready"] = _cts_ready()


def _bucket_format(name: str) -> str:
    from vgc_suite.core import buckets
    try:
        return buckets.format_of(name)
    except KeyError:
        return _formats.CURRENT


ENV.globals["bucket_format"] = _bucket_format

SWITCH_MIN_GAIN = 0.10


def counter_switch(b: dict) -> dict | None:






    m, r = b["matrix"], b["recommended"]["row"]
    row = m[r]
    c = min(range(len(row)), key=lambda j: (row[j], j))
    if row[c] >= 0.5:
        return {"needed": False}
    best = None
    for i, mr in enumerate(m):
        if i == r or mr[c] < row[c] + SWITCH_MIN_GAIN or mr[0] < row[c]:
            continue
        if best is None or (mr[c], -i) > (m[best][c], -best):
            best = i
    if best is None:
        return {"needed": True, "row": None, "col": c, "rec_value": row[c], "answer": b["theirs"][c]}
    return {"needed": True, "row": best, "col": c, "value": m[best][c], "rec_value": row[c], "mine": b["mine"][best],
            "answer": b["theirs"][c]}


ENV.globals["counter_switch"] = counter_switch


def their_recommended(b: dict) -> dict:


    m, mix = b["matrix"], b["equilibrium"]["theirs"]
    c = max(range(len(mix)), key=lambda j: (round(mix[j], 3), -max(row[j] for row in m), -j))
    return b["theirs"][c]


ENV.globals["their_recommended"] = their_recommended

def reference_cells(b: dict) -> list[tuple[int, int, str]]:



    eqm, eqt = b["equilibrium"]["mine"], b["equilibrium"]["theirs"]
    rows = [i for i, w in enumerate(eqm) if w >= 0.05]
    cols = [j for j, w in enumerate(eqt) if w >= 0.05]
    want = [(0, 0, "the bot's own pairing")] + [(i, j, "both-adapt mix") for i in rows for j in cols] + \
           [(0, b["best_answer"]["col"], "their best answer to your usual four")]
    mm = b["matrix"]
    for i, tag in ((b["recommended"]["row"], "your recommended four's worst case"), (b["safest"]["row"], "the safest four's worst case")):
        want.append((i, min(range(len(mm[i])), key=lambda j: (mm[i][j], j)), tag))
    cs = counter_switch(b)
    if cs.get("needed") and cs.get("row") is not None:
        want += [(cs["row"], cs["col"], "the counter-switch vs their answer"), (cs["row"], 0, "the counter-switch vs their usual bring")]
    return want


def _checks_of(dd_id: str, opp: str) -> tuple[list[str], bool]:

    mxchecks()
    done, pending = [], False
    for v in _MXCHECKS.values():
        if v[1] and v[1][0] == dd_id and v[1][1] == opp:
            if v[1][3] == "done":
                done.append((v[1][4], v[1][2]))
            elif v[1][3] in ("queued", "running"):
                pending = True
    return [i for _, i in sorted(done)], pending


def check_gaps(dd_id: str, r: dict) -> dict:


    out, pending = {}, 0
    for o in r.get("opponents") or []:
        if not o.get("brings"):
            continue
        ids, busy = _checks_of(dd_id, o["id"])
        if busy:
            pending += 1
            continue
        b = checked_brings(dd_id, o["id"], o["brings"])
        done_cells = {tuple(c) for c in b["searched"]}
        n = len({(i, j) for i, j, _ in reference_cells(b)} - done_cells)
        if n:
            out[o["id"]] = n
    return {"teams": out, "pending": pending}


_CHECKED: dict[tuple, dict] = {}


def checked_brings(dd_id: str, opp: str, b: dict) -> dict:






    import numpy as np
    from vgc_suite.core.preview_advisor import equilibrium
    ids = _checks_of(dd_id, opp)[0] if dd_id else []
    cid = ids[-1] if ids else None
    key = (dd_id, opp, tuple(ids))
    if key in _CHECKED:
        return _CHECKED[key]
    merged: dict[tuple[int, int], dict] = {}
    for i in ids:
        try:
            for c in (json.loads((JOB_DIR / f"{i}.json").read_text(encoding="utf8")).get("result") or {}).get("cells") or []:
                merged[(c["row"], c["col"])] = c
        except (OSError, ValueError):
            continue
    cells = list(merged.values())
    out = dict(b)
    if cells:
        M = np.array(b["matrix"], dtype=float)
        for c in cells:
            M[c["row"], c["col"]] = c["search"]
        r_mix, c_mix, value = equilibrium(M)
        worst = M.min(1)
        safest = int(np.argmax(worst))
        rec = int(max(range(len(M)), key=lambda i: (round(float(r_mix[i]), 3), float(worst[i]), -i)))
        col = int(M[0].argmin())
        sc = b.get("screened")
        out.update(matrix=[[round(float(v), 3) for v in row] for row in M], as_picked=round(float(M[0, 0]), 3),
                   best_answer={"value": round(float(M[0].min()), 3), "col": col,
                                "outside_heads": bool(sc and col >= sc["theirs_from"])},
                   safest={"row": safest, "value": round(float(worst[safest]), 3)},
                   equilibrium={"value": round(value, 3), "mine": [round(float(v), 3) for v in r_mix],
                                "theirs": [round(float(v), 3) for v in c_mix]},
                   recommended={"row": rec, "lead": b["mine"][rec]["lead"], "back": b["mine"][rec]["back"]})
    m = out["matrix"]
    srch = [[c["row"], c["col"]] for c in cells]
    rr, sr = out["recommended"]["row"], out["safest"]["row"]
    rc = min(range(len(m[rr])), key=lambda j: (m[rr][j], j))
    sc_ = min(range(len(m[sr])), key=lambda j: (m[sr][j], j))
    eq = out["equilibrium"]
    support = [[i, j] for i, wi in enumerate(eq["mine"]) if wi >= 0.05 for j, wj in enumerate(eq["theirs"]) if wj >= 0.05]
    out.update(searched=srch, check=cid, rec_worst={"value": m[rr][rc], "col": rc}, safe_worst={"value": m[sr][sc_], "col": sc_},
               eq_searched=bool(srch) and all(c in srch for c in support))
    _CHECKED[key] = out
    return out


def checked_field(dd_id: str, r: dict) -> dict:


    rows = [(o, checked_brings(dd_id, o["id"], o["brings"])) for o in r.get("opponents") or [] if o.get("brings")]
    w = [o["share"] if o.get("share") is not None else 1.0 for o, _ in rows]
    avg = lambda f: round(sum(f(b) * x for (_, b), x in zip(rows, w)) / max(sum(w), 1e-9), 3) if rows else None
    return {"as_picked": avg(lambda b: b["as_picked"]), "best_answer": avg(lambda b: b["best_answer"]["value"]),
            "equilibrium": avg(lambda b: b["equilibrium"]["value"]), "checked": sum(1 for _, b in rows if b["check"]),
            "teams": len(rows)}


ENV.globals.update(checked_brings=checked_brings, checked_field=checked_field, check_gaps=check_gaps)


def deep_dive_sheets(n: int = 30) -> list[dict]:


    out = []
    for f in sorted(JOB_DIR.glob("*.json"), reverse=True):
        try:
            j = json.loads(f.read_text(encoding="utf8"))
        except (OSError, ValueError):
            continue
        r = j.get("result") if isinstance(j.get("result"), dict) else {}
        if j.get("tool") != "validate" or j.get("status") != "done" or r.get("sweep"):
            continue
        k = sum(1 for o in r.get("opponents") or [] if o.get("brings"))
        if not k:
            continue
        fld = (j.get("params") or {}).get("field", "")
        out.append({"id": j["id"], "team": (r.get("team") or {}).get("species") or run_teams("validate", j.get("params") or {})[0]["species"],
                    "field": f"bucket {fld[7:]}" if fld.startswith("bucket:") else "Current Metagame" if fld == "meta" else fld,
                    "created": j.get("created"), "teams": k, "search": bool(r.get("search"))})
        if len(out) >= n:
            break
    return out


ENV.globals["deep_dive_sheets"] = deep_dive_sheets


def is_slot_run(j: dict) -> bool:


    p = j.get("params") or {}
    res = j.get("result") if isinstance(j.get("result"), dict) else {}
    return p.get("lab") == "slot" or bool(res.get("sweep")) or bool((p.get("replace") or "").strip()) or bool((p.get("candidates") or "").strip())


def _mons(text):


    from markupsafe import Markup
    from vgc_suite.core.narrate import tagged_html
    return Markup(tagged_html(str(text), name=lambda n: _i18n.dex("species", n)))


def _ev_text(ev):

    from vgc_suite.core.narrate import render_event
    return render_event(ev) if isinstance(ev, dict) else ev


def _act(label):

    from vgc_suite.core.labels import localize
    return localize(label)


ENV.filters["mons"] = _mons
ENV.filters["ev_text"] = _ev_text
ENV.filters["act"] = _act

ENV.filters["line_label"] = lambda s: __import__("vgc_suite.core.labels", fromlist=["line_label"]).line_label(s)
ENV.filters["roll_word"] = lambda s: __import__("vgc_suite.core.labels", fromlist=["roll_word"]).roll_word(s)
ENV.filters["who_label"] = lambda s: __import__("vgc_suite.core.labels", fromlist=["who_label"]).who_label(s)
ENV.filters["spread_text"] = lambda s: __import__("vgc_suite.core.labels", fromlist=["spread_text"]).spread_text(s)
_CAVEAT_FMT = re.compile(r"^(.+?) uses closed team sheets(.*)$")


def _caveat(c: str) -> str:


    if _i18n.language() == "en" or _i18n.has(c):
        return _i18n.t(c)
    m = _CAVEAT_FMT.match(c)
    return _i18n.t("{fmt} uses closed team sheets" + m.group(2), fmt=m.group(1)) if m else c


ENV.filters["caveat"] = _caveat


def _target_label(t: str) -> str:


    if _i18n.language() == "en" or not isinstance(t, str):
        return t
    if _i18n.has(t):
        return _i18n.t(t)
    if t.startswith("ally "):
        return _i18n.t("ally {mon}", mon=_i18n.dex("species", t[5:]))
    return _i18n.dex("species", t)


ENV.filters["target_label"] = _target_label


def _cand_label(s):

    if not isinstance(s, str) or _i18n.language() == "en":
        return s
    return _i18n.t("keep {mon}", mon=_i18n.dex("species", s[5:])) if s.startswith("keep ") else _i18n.dex("species", s)


ENV.filters["cand_label"] = _cand_label
_MONS_SEP = re.compile(r"( \+ |\+|/| · |, | \()")


def _mons_text(s):


    if not isinstance(s, str) or _i18n.language() == "en":
        return s
    parts = _MONS_SEP.split(s)
    out, tail = [], False
    for p in parts:
        if p == " (":
            tail = True
        out.append(p if tail or _MONS_SEP.fullmatch(p) or not p else _i18n.dex("species", p))
    return "".join(out)


ENV.filters["mons_text"] = _mons_text


def _set_text(s):


    if not isinstance(s, str) or _i18n.language() == "en":
        return s
    out = []
    for p in s.split(" · "):
        if " / " in p:
            out.append(" / ".join(_i18n.dex("move", m) for m in p.split(" / ")))
        else:
            it = _i18n.dex("item", p)
            out.append(it if it != p else _i18n.dex("ability", p) if _i18n.dex("ability", p) != p else _i18n.dex("move", p))
    return " · ".join(out)


ENV.filters["set_text"] = _set_text
_STAT_NAMES = ("HP", "Atk", "Def", "SpA", "SpD", "Spe")


def _fitted_paste(text: str, fits) -> tuple[str, bool]:



    if not text or not fits:
        return text, False
    from vgc_trainer.showdown.tracker import to_id
    by = {to_id(f["mon"]): f for f in fits if f.get("spread")}
    out, changed = [], False
    for block in text.replace("\r", "").split("\n\n"):
        lines = block.split("\n")
        head = re.sub(r"\s*@.*$", "", lines[0]).strip()
        head = re.sub(r"\((M|F)\)\s*$", "", head).strip()
        m = re.search(r"\(([^()]+)\)\s*$", head)
        f = by.get(to_id(m.group(1) if m else head))
        if f:
            nat, pts = f["spread"].split(" ", 1)
            evs = " / ".join(f"{v} {n}" for v, n in zip(pts.split("/"), _STAT_NAMES) if v != "0")
            new = [ln for ln in lines if not ln.strip().startswith("EVs:") and not ln.strip().endswith("Nature")]
            at = next((i for i, ln in enumerate(new) if ln.startswith("- ")), len(new))
            new[at:at] = [f"EVs: {evs}  ", f"{nat} Nature  "]
            changed = changed or bool(f.get("changed"))
            lines = new
        out.append("\n".join(lines))
    return "\n\n".join(out), changed


ENV.globals["fitted_paste"] = _fitted_paste


def _team_id(s):



    if not isinstance(s, str) or "/" not in s or not s.endswith("/..."):
        return s
    return "/".join(_i18n.dex("species", x) for x in s[:-4].split("/")) + "/…"


ENV.filters["team_id"] = _team_id
ENV.filters["field_label"] =lambda s: (_i18n.t("bucket {name}", name=s[7:]) if isinstance(s, str) and s.startswith("bucket ")
                                        else _i18n.t(s) if isinstance(s, str) else s)
for _f in ("crawl_line", "crawl_pos", "dice_word"):
    ENV.filters[_f] = (lambda name: lambda s: getattr(__import__("vgc_suite.core.labels", fromlist=[name]), name)(s))(_f)
ENV.filters["note_label"] = lambda s: __import__("vgc_suite.core.labels", fromlist=["note_label"]).note_label(s)


def _replay_label(text: str) -> str:



    s = (text or "").strip()
    if "\n" not in s and "<" not in s:
        return s[:90]
    import html as _html
    m = re.search(r"<title>(.*?)</title>", s, re.S | re.I)
    if m:
        return _html.unescape(m.group(1)).strip()[:90]
    who = dict(re.findall(r"^\|player\|(p[12])\|([^|\n]+)", s, re.M))
    tier = re.search(r"^\|tier\|([^\n]+)", s, re.M)
    if who.get("p1") and who.get("p2"):
        return _i18n.t("{p1} vs {p2}", p1=who["p1"], p2=who["p2"]) + (f" · {tier.group(1).strip()}" if tier else "")
    return s.splitlines()[0][:90]


ENV.filters["replay_label"] = _replay_label
ENV.filters["luck_event"] = lambda s: __import__("vgc_suite.core.labels", fromlist=["luck_event"]).luck_event(s)
ENV.filters["reading_label"] = lambda s: __import__("vgc_suite.core.labels", fromlist=["reading_label"]).reading_label(s)
ENV.filters["heat"] = heat
ENV.filters["ago"] = lambda t: (time.strftime("%d %b %H:%M", time.localtime(t)) if _i18n.language() == "en" else
                                f"{time.localtime(t).tm_mon}月{time.localtime(t).tm_mday}日 " + time.strftime("%H:%M", time.localtime(t)))
def _bucket_names() -> list[str]:

    try:
        from vgc_suite.core import buckets
        return buckets.names()
    except Exception:
        return []


def _has_library() -> bool:


    from vgc_trainer.showdown.teams import TEAM_FILES
    return any(f.exists() for f in TEAM_FILES)


def _has_meta_field() -> bool:

    from vgc_suite.core.validator import META_FIELD
    return META_FIELD.exists()


ENV.globals.update(in_app=lambda: OPEN_WINDOW is not None, browser_mode=lambda: BROWSER_MODE, private=PRIVATE, favorites=favorites, mxchecks=mxchecks, mxsearches=mxsearches, sweep_six_paste=sweep_six_paste, team_paste=team_paste, dd_team_paste=dd_team_paste, has_mxcheck=True, smogon_month=_smogon_month, TOOLS=TOOLS, LIMITS=LIMITS, WAIT=WAIT, win_curve_svg=win_curve_svg, suite_lock=lambda: suite_lock.state(),
                   team_buckets=_bucket_names, has_meta_field=_has_meta_field,
                   has_library=_has_library())
STATIC = {"style.css": "text/css", "app.js": "text/javascript", "sprites.js": "text/javascript", "fonts/fonts.css": "text/css",
          **{f"fonts/{n}-{s}.woff2": "font/woff2" for n in ("fredoka", "nunito") for s in ("latin", "latin-ext")}}

IMAGE_TYPES = {".png": "image/png", ".gif": "image/gif", ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}
SPRITES = {"dir": ROOT / "sprites", "key": None, "index": None}


def sprite_index() -> dict | None:

    d = SPRITES["dir"]
    if not d.is_dir():
        return None
    files = [f for f in d.rglob("*") if f.suffix.lower() in IMAGE_TYPES]
    key = (len(files), max((f.stat().st_mtime for f in files), default=0))
    if key != SPRITES["key"]:
        from vgc_suite.sprites import build_index
        SPRITES.update(key=key, index=build_index(d))
    return SPRITES["index"] if SPRITES["index"]["names"] else None


class Handler(BaseHTTPRequestHandler):
    jobs: Jobs
    lan = False

    def log_message(self, fmt, *args):
        pass

    def _send(self, body: str | bytes, ctype: str = "text/html; charset=utf-8", code: int = 200, cache: int = 0) -> None:
        data = body.encode("utf8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if cache:
            self.send_header("Cache-Control", f"max-age={cache}")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _page(self, name: str, **ctx) -> None:
        self._send(ENV.get_template(name).render(**ctx))

    def _foreign(self, post: bool) -> bool:



        host = (self.headers.get("Host") or "").lower()
        origin = urlparse(self.headers.get("Origin") or "").netloc.lower()
        bad = post and ((self.headers.get("Sec-Fetch-Site") or "same-origin") not in ("same-origin", "none") or (origin and origin != host))
        if not self.lan and (host.rpartition(":")[0] if host.rpartition(":")[2].isdigit() else host) not in ("127.0.0.1", "localhost", "[::1]"):
            bad = True
        if bad:
            self._send("Not from this app.", "text/plain; charset=utf-8", 403)
        return bool(bad)

    def _game_back(self) -> dict:

        ref = urlparse(self.headers.get("Referer") or "")
        path = ref.path if ref.netloc == self.headers.get("Host") else ""
        if path == "/buddy/session":
            return {"back": path + ("?" + ref.query if ref.query else ""), "back_label": "the session"}
        if path == "/analyze" or path.startswith("/job/"):
            return {"back": "/analyze", "back_label": "the Replay Analyzer"}
        return {"back": "/buddy", "back_label": "Buddy"}

    def do_GET(self) -> None:
        if self._foreign(False):
            return
        path = urlparse(self.path).path.strip("/")
        if not PRIVATE and private_route(path):
            return self._send("Not in this build.", "text/plain; charset=utf-8", 404)
        if path == "":
            return self._page("index.html", recent=self.jobs.recent(), active="home")
        if path == "about":
            from vgc_suite import __version__, about
            g = ENV.globals.get("gpu") or {}
            from vgc_suite import update
            return self._page("about.html", active="about", version=__version__, bundle=about.bundle_info(), contact=about.CONTACT, last_update=update.LAST,
                              issues=about.ISSUES, releases=about.RELEASES,
                              diag=about.diagnostics(self.jobs.recent(40), self.jobs.device, g.get("name", "")))
        if path == "status":
            try:
                from urllib.parse import parse_qs
                pn = parse_qs(urlparse(self.path).query).get("panel", [""])[0]
                rh = parse_qs(urlparse(self.path).query).get("rep", ["6"])[0]
                return self._page("status.html", active="status", panel=pn if pn in ("ladder", "ml1", "train", "pc1", "challenge", "arena") else None,
                                  **status_page(float(rh) if rh in ("2", "6", "24") else 6))
            except Exception as e:
                return self._send(f"status page error: {type(e).__name__}: {e}", "text/plain; charset=utf-8", 500)

        if path == "status/matchups" or path.startswith("status/matchups/"):
            from urllib.parse import parse_qs
            from vgc_suite import matchups as mu
            q = parse_qs(urlparse(self.path).query)
            try:
                if path == "status/matchups/six":
                    lo = q.get("min", [""])[0]
                    v = mu.six_view(q.get("k", [""])[0], q.get("mode", ["exact"])[0], q.get("group", ["family"])[0],
                                    q.get("tc", ["1"])[0] != "0", int(lo) if lo.isdigit() else None,
                                    "sd" if q.get("sort", ["tour"])[0] == "sd" else "tour")
                    if v is None:
                        return self._send("no team with that six in the corpus", "text/plain; charset=utf-8", 404)
                    return self._page("matchup_six.html", active="matchups", v=v, pct=pct)
                near = mu.nearest(q.get("s", [])) if path == "status/matchups/find" else None
                species = sorted({mu._base(x) for p in mu.load()["players"].values() if p["six"] for x in p["six"]})
                return self._page("matchups.html", active="matchups", L=mu.library(), near=near, species=species, pct=pct,
                                  popular=mu.popular(40))
            except Exception as e:
                return self._send(f"matchups error: {type(e).__name__}: {e}", "text/plain; charset=utf-8", 500)


        TABS = {"status/meta": {"key": "watch", "base": "/status/meta", "name": "Metagame", "active": "meta", "invert": False},
                "status/opp": {"key": "own", "base": "/status/opp", "name": "Opponents", "active": "opp", "invert": True}}
        SUB = {"matchups": ("Matchups", "matchup_view", "How the most used archetypes do against each other.",
                            "The opponents' archetypes against the bot's teams."),
               "leads": ("Leads", "leads_view", "The most used lead pairs against each other, and what people lead into them.",
                         "The opponents' leads against the bot's leads."),
               "bo3": ("Bo3", "bo3_view", "How players adapt between the games of a series.",
                       "How opponents adapt between the games of a series against the bot."),
               "speed": ("Speed", "speed_view", "Speed tiers of the most used Pokemon.", "Speed tiers of the Pokemon the bot faces."),
               "trends": ("Trends", "trends_view", "What is rising and falling, and what the 1300+ games play more.",
                          "What the bot faces more or less of lately, and what 1300+ opponents bring."),
               "bot": ("The bot", "bot_view", "How the bot does against the field's archetypes.", None)}
        tab = next((t for b, t in TABS.items() if path == b or path.startswith(b + "/")), None)
        if tab is not None:
            from urllib.parse import parse_qs, unquote
            from vgc_suite import meta_pages
            from vgc_suite.meta_stats import meta_view, team_view
            base = tab["base"][1:]
            rest = path[len(base):].lstrip("/")
            q = parse_qs(urlparse(self.path).query)
            lo, dy = q.get("min", [""])[0], q.get("days", [""])[0]
            f = {"min": int(lo) if lo.isdigit() else None, "days": int(dy) if dy.isdigit() else None, "w": q.get("w", ["1"])[0] != "0"}
            src = tab
            try:
                if rest == "chat" and src["key"] == "own":
                    from vgc_suite.chat_log import chat_view
                    c = chat_view(q.get("who", ["opponents"])[0], q.get("bots", ["0"])[0] == "1")
                    return self._page("chat.html", active=src["active"], c=c, f=f, src=src)
                if rest in SUB and (SUB[rest][3] is not None or src["key"] == "watch"):
                    title, fn, intro_w, intro_o = SUB[rest]
                    if rest == "matchups":
                        f["core"] = 5 if q.get("core", ["4"])[0] == "5" else 4
                        d = meta_pages.matchup_view(f["min"], f["days"], src["key"], f["core"])
                    else:
                        d = getattr(meta_pages, fn)(f["min"], f["days"], src["key"])
                    return self._page("meta_sub.html", active=src["active"], page=rest, title=title,
                                      intro=intro_o if src["key"] == "own" else intro_w, d=d, f=f, src=src, pct=pct, pct0=pct0)
                args = (f["min"], f["days"], f["w"])
                if rest.startswith("team/"):
                    t = team_view(unquote(rest[len("team/"):]), *args, source=src["key"])
                    if t is None:
                        return self._send("no games with that team in this selection", "text/plain; charset=utf-8", 404)
                    return self._page("meta_team.html", active=src["active"], t=t, src=src, pct=pct, pct0=pct0)
                m = meta_view(*args, source=src["key"])
                if rest == "":
                    colours = ["#a06146", "#7c5f4a", "#c98a46", "#aadc26", "#fdc32a", "#b7d8f9", "#faa8a6", "#676860", "#c8a47c", "#625a51"]
                    days = m["days_list"]
                    chart = line_chart([(t["name"], colours[i % len(colours)], [(days.index(d), 100 * v) for d, v in t["points"]])
                                        for i, t in enumerate(m["trend"])], [(i, d[5:]) for i, d in enumerate(days)],
                                       w=640, h=220, y_fmt="{:.0f}%") if len(days) >= 2 else None
                    return self._page("meta.html", active=src["active"], m=m, src=src, pct=pct, pct0=pct0, trend_chart=chart or "")
                if rest.startswith("species/"):
                    sp = unquote(rest[len("species/"):])
                    srow = next((x for x in m["species"] if x["name"] == sp), None)
                    return self._page("meta_species.html", active=src["active"], m=m, sp=sp, s=srow, d=m["detail"].get(sp), src=src,
                                      pct=pct, pct0=pct0, deltas=meta_pages.species_deltas(sp, f["min"], f["days"], src["key"]))
                return self._send("not found", "text/plain", 404)
            except Exception as e:
                return self._send(f"{src['name']} page error: {type(e).__name__}: {e}", "text/plain; charset=utf-8", 500)
        if path == "status/nice":
            import json as _json
            src = ROOT / "trainer/runs/snapshots/nice-deepdive.json"
            if not src.exists():
                return self._send("no Nice data yet: run trainer/scripts/nice_deepdive_data.py", "text/plain; charset=utf-8", 404)
            return self._page("nice.html", active="nice", d=_json.loads(src.read_text(encoding="utf8")), pct=pct, pct0=pct0)
        if path.startswith("status/game/"):
            from urllib.parse import parse_qs
            from vgc_suite.game_views import game_log, game_view
            if parse_qs(urlparse(self.path).query).get("raw"):
                text = game_log(path[12:])
                return self._send(text, "text/plain; charset=utf-8") if text is not None else self._send("no such game", "text/plain", 404)
            try:
                g = game_view(path[12:], pov=parse_qs(urlparse(self.path).query).get("pov", [None])[0])
                if g is None:
                    return self._send("no such game", "text/plain", 404)
                if not PRIVATE and not g.get("back"):
                    g.update(self._game_back())


                from vgc_suite import lines
                q = parse_qs(urlparse(self.path).query)
                g.update(line=lines.info(path[12:]) if g.get("bot_side") and self._local() else None,
                         linemsg=q.get("linemsg", [None])[0])

                if g.get("bot_side"):
                    g.update(branches=lines.branches(path[12:]), origin=lines.origin(lines.line_of(path[12:])))
                return self._page("game.html", active="status" if PRIVATE else "buddy", g=g, pct=pct, pct0=pct0)
            except Exception as e:
                return self._send(f"game page error: {type(e).__name__}: {e}", "text/plain; charset=utf-8", 500)
        if path.startswith("status/series/"):
            from vgc_suite.team_stats import series_detail
            try:
                s = series_detail(path[14:])
                if s is None:
                    return self._send("no such series", "text/plain", 404)
                for g in s["games"]:
                    pts = [(t, 100 * w) for t, w in g["curve"]]
                    g["chart"] = line_chart([("win estimate", "#a06146", pts)], [(t, f"T{t}") for t, _ in pts],
                                            w=420, h=140, y_fmt="{:.0f}%", y_range=(0, 100)) if len(pts) >= 2 else None
                return self._page("series.html", active="status", s=s, pct=pct, pct0=pct0)
            except Exception as e:
                return self._send(f"series page error: {type(e).__name__}: {e}", "text/plain; charset=utf-8", 500)
        if path.startswith("status/team/") and path.endswith("/six"):
            from urllib.parse import parse_qs, unquote
            from vgc_suite.team_stats import six_detail
            q = parse_qs(urlparse(self.path).query)
            try:
                d = six_detail(unquote(path[12:-4]), q.get("s", [""])[0], q.get("since", ["update"])[0])
                return self._page("six.html", active="status", d=d, pct=pct, pct0=pct0)
            except Exception as e:
                return self._send(f"six page error: {type(e).__name__}: {e}", "text/plain; charset=utf-8", 500)
        if path.startswith("status/team/"):
            from urllib.parse import parse_qs, unquote
            from vgc_suite.team_stats import team_detail
            since = parse_qs(urlparse(self.path).query).get("since", ["update"])[0]
            try:
                return self._page("team.html", active="status", t=team_detail(unquote(path[12:]), since), pct=pct, pct0=pct0,
                                  upd=__import__("vgc_suite.status", fromlist=["newest_update"]).newest_update())
            except Exception as e:
                return self._send(f"team page error: {type(e).__name__}: {e}", "text/plain; charset=utf-8", 500)
        if path.startswith("deepdive/"):
            from urllib.parse import unquote
            from vgc_suite.core import deepdive as dd
            team = unquote(path[len("deepdive/"):])
            f = dd.cached(team) if all(ch.isalnum() or ch in "-_" for ch in team) else None
            if f is None or not f.exists():
                return self._send(f"no deep dive for {team} yet: run python -m vgc_suite.cli deepdive {team}", "text/plain; charset=utf-8", 404)
            return self._send(dd.render(json.loads(f.read_text(encoding="utf8")), standalone=False))
        if path == "api/status":
            from vgc_suite.status import gather
            return self._send(json.dumps(gather()), "application/json")
        if path == "crawler" or path.startswith("crawler/s/"):
            return self._crawler_get(path)
        if path == "buddy/session":
            from urllib.parse import parse_qs as qs
            from vgc_suite import buddy_sessions
            q = qs(urlparse(self.path).query)
            s = buddy_sessions.detail(ROOT, q.get("bot", [""])[0], q.get("u", [""])[0], q.get("s", [""])[0])
            if s is None:
                return self._send(ENV.get_template("base.html").render(missing=True), code=404)
            return self._page("buddy_session.html", active="buddy", s=s)
        if path == "app/focus":
            if FOCUS_APP is not None and self._local():
                FOCUS_APP()
            return self._send(json.dumps({"app": "openVGCengine", "pid": os.getpid()}), "application/json")
        if path == "app/alive":
            if self._local():
                globals()["APP_SEEN"] = time.monotonic()
            return self._send(json.dumps({"ok": True}), "application/json")
        if path == "buddy/play":
            from urllib.parse import urlencode
            from vgc_suite.core.h2h_examples import ensure_local_server
            if OPEN_WINDOW is None or not self._local():
                msg = _i18n.t("Open the local Showdown at localhost:8000.")
            else:
                missing = ensure_local_server()
                msg = missing or "Showdown opened in its own window."
                if not missing:
                    OPEN_WINDOW(SHOWDOWN_URL, "Showdown - training buddy")
            self.send_response(303)
            self.send_header("Location", "/buddy?" + urlencode({"msg": msg}))
            self.end_headers()
            return
        if path == "buddy/latest":
            from vgc_suite.buddy_sessions import BOTS
            stamp = []
            for cfg in BOTS.values():
                f = ROOT / cfg["results"]
                stamp.append(f"{f.stat().st_size}-{f.stat().st_mtime_ns}" if f.exists() else "-")
            return self._send(json.dumps({"stamp": "|".join(stamp)}), "application/json")
        if path == "buddy":
            from urllib.parse import parse_qs as qs
            q = qs(urlparse(self.path).query)
            return self._buddy_page(q.get("msg", [])[:1], who=q.get("who", [""])[0])
        if path == "prep":
            return self._page("prep.html", active="prep")
        if path == "compare":
            from urllib.parse import parse_qs as qs
            from vgc_suite.core import compare
            q = qs(urlparse(self.path).query)
            entries = compare.index(JOB_DIR)
            fields: dict[str, int] = {}
            for e in entries:
                fields[e["field"]] = fields.get(e["field"], 0) + 1
            field = q.get("field", [""])[0] or next(iter(fields), "")
            favs, fav_only = favorites(), q.get("fav", [""])[0] == "1"
            mine = [{**e, "fav": favs.get(e["job"])} for e in entries if e["field"] == field]
            chosen = [k for k in q.get("run", []) if any(e["key"] == k for e in mine)]
            listed = [e for e in mine if e["fav"] or e["key"] in chosen] if fav_only else mine
            cmp = compare.compare([e for e in mine if e["key"] in chosen]) if chosen else None
            return self._page("compare.html", active="validate", fields=list(fields.items()), field=field, entries=listed,
                              chosen=chosen, cmp=cmp, field_label=compare.field_label, fav_only=fav_only)
        if path == "buckets":
            return self._buckets_page()
        if path == "api/buckets":
            from vgc_suite.core import buckets
            return self._send(json.dumps(buckets.summaries()), "application/json")
        if path in TOOLS or path == "slot":
            tool = "validate" if path == "slot" else path
            from urllib.parse import parse_qs as _pq
            q = _pq(urlparse(self.path).query)
            prefill = {}
            src = self.jobs.get(q.get("from", [""])[0]) if q.get("from") else None
            if src and src.get("tool") == tool:
                prefill = dict(src.get("params") or {})
                if tool == "analyze" and q.get("edit") and src.get("result"):


                    res_ = src["result"]
                    for s in ("p1", "p2"):
                        if not (prefill.get(f"paste_{s}") or "").strip():
                            prefill[f"paste_{s}"] = (((res_.get("pastes") or {}).get(s) or {}).get("text")
                                                     or (res_.get("guess_paste") or {}).get(s) or "")
                if q.get("swap"):
                    for x, y in SWAP.get(path, []):
                        prefill[x], prefill[y] = prefill.get(y, ""), prefill.get(x, "")
            elif q.get("dd") and path in ("h2h", "preview", "playout"):


                dd = self.jobs.get(q["dd"][0])
                pair = _deepdive_matchup(dd, q.get("opp", [""])[0], q.get("sixth", [""])[0])
                if pair:
                    (a, b) = [k for _, k in TEAM_FIELDS[path]]
                    prefill = {a: pair[0], b: pair[1], **({"deep": "1", "bo3": "1"} if path == "h2h" else {"all_rows": "1"} if path == "preview" else {})}
                    if (dd.get("params") or {}).get("format"):
                        prefill["format"] = dd["params"]["format"]
                    if path == "playout":
                        prefill.update(_playout_brings(dd, q.get("opp", [""])[0], q.get("row", [""])[0], q.get("col", [""])[0]))
            elif path == "preview" and q.get("analyzed"):


                aj = self.jobs.get(q["analyzed"][0])
                res_ = (aj or {}).get("result") or {}
                if aj and aj.get("tool") == "analyze" and res_.get("pastes"):
                    pl = (res_.get("replay") or {}).get("players") or {}
                    texts = [_fitted_paste(((res_["pastes"].get(s) or {}).get("text") or ""), (res_.get("fits") or {}).get(s))[0]
                             for s in ("p1", "p2")]
                    prefill = {"mine": texts[0], "theirs": texts[1], "name_a": pl.get("p1", "")[:40], "name_b": pl.get("p2", "")[:40],
                               "format": res_.get("format") or ""}
            elif path == "analyze" and q.get("replay"):


                prefill = {"replay": q["replay"][0][:4000]}
                if q.get("side", [""])[0] in ("both", "p1", "p2"):
                    prefill["side"] = q["side"][0]
                if q.get("depth", [""])[0] in ("fast", "standard", "deep"):
                    prefill["depth"] = q["depth"][0]
            elif any(k in q for _, k in TEAM_FIELDS.get(path, [])):


                keep = [k for _, k in TEAM_FIELDS.get(path, [])] + ["deep", "bo3", "luck", "games"]
                prefill = {k: q[k][0][:4000] for k in keep if q.get(k)}
            fav_only, every = q.get("fav", [""])[0] == "1", q.get("all", [""])[0] == "1"
            return self._page(f"{path}.html", active=path,
                              history=self.jobs.history(tool, fav_only=fav_only, every=every,
                                                        slot=(path == "slot") if tool == "validate" else None),
                              fav_only=fav_only, every=every, slot=path == "slot", FAST_FACTOR=FAST_FACTOR,
                              prefill=prefill, can_swap=path in SWAP)
        if path == "sprites/index.json":
            idx = sprite_index()
            if idx is None:
                return self._send("no sprite folder", "text/plain", 404)
            from urllib.parse import quote
            out = {n: "/sprites/f/" + quote(f) for n, f in idx["names"].items()}
            if _i18n.language() != "en":
                out.update({ja: u for n, u in list(out.items()) if (ja := _i18n.dex("species", n)) and ja != n})
            return self._send(json.dumps(out), "application/json", cache=300)
        if path.startswith("sprites/f/"):
            from urllib.parse import unquote
            base = SPRITES["dir"].resolve()
            f = (base / unquote(path[len("sprites/f/"):])).resolve()
            if not f.is_relative_to(base) or f.suffix.lower() not in IMAGE_TYPES or not f.is_file():
                return self._send("not found", "text/plain", 404)
            return self._send(f.read_bytes(), IMAGE_TYPES[f.suffix.lower()], cache=86400)
        if path.startswith("static/") and path[7:] in STATIC:
            return self._send((WEB / "static" / path[7:]).read_bytes(), STATIC[path[7:]])
        if path.startswith("job/") and path.endswith("/report.json"):


            job = self.jobs.get(path[4:-len("/report.json")])
            if job is None or job["tool"] != "analyze":
                return self._send("no such analysis", "text/plain", 404)
            from vgc_suite import __version__, about
            from vgc_suite.core.replay import load_replay
            try:
                log_text = "\n".join(load_replay(_replay_src(job["params"]["replay"])).lines)
            except Exception as e:
                log_text, err = None, f"{type(e).__name__}: {e}"
            else:
                err = None
            try:
                import vgc_engine
                eng = Path(vgc_engine.__file__).resolve().parents[1].name
            except ImportError:
                eng = None
            rep = {"kind": "openvgc-report", "version": __version__, "bundle": about.bundle_info(), "engine": eng,
                   "job": {k: job.get(k) for k in ("id", "tool", "params", "created", "status")}, "replay_log": log_text,
                   **({"replay_error": err} if err else {}), "result": job.get("result")}
            data = json.dumps(rep, indent=1).encode("utf8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition", f'attachment; filename="openvgc-report-{job["id"]}.json"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith("job/") and path.endswith("/brings-print"):

            job = self.jobs.get(path[4:].rsplit("/", 1)[0])
            r = (job or {}).get("result") or {}
            if not job or job.get("tool") != "validate" or not r.get("brings") or r.get("sweep"):
                return self._send("This run has no bring matrices.", "text/plain; charset=utf-8", 404)
            return self._page("brings_print.html", job=job, r=r)
        if path.startswith("job/") and "/game/" in path:
            jid, _, k = path[4:].partition("/game/")
            job = self.jobs.get(jid)
            ex = ((job or {}).get("result") or {}).get("examples") or []
            if not k.isdigit() or int(k) >= len(ex) or "lines" not in ex[int(k)]:
                return self._send("no such game", "text/plain", 404)
            e = ex[int(k)]
            from urllib.parse import parse_qs
            if parse_qs(urlparse(self.path).query).get("raw"):
                return self._send("\n".join(e["lines"]), "text/plain; charset=utf-8")
            from vgc_suite.game_views import view_from_lines
            ids = job["result"].get("ids") or {}

            names = {e.get("a_name", "\0"): f"A ({ids.get('a', 'Team A')})", e.get("b_name", "\0"): f"B ({ids.get('b', 'Team B')})"}
            lines = [ln.replace(e["a_name"], names[e["a_name"]]).replace(e["b_name"], names[e["b_name"]]) if "a_name" in e else ln
                     for ln in e["lines"]]
            if job["tool"] == "fieldplay":
                ids = {"a": "your team", "b": e.get("opp", "the field team")}
                names = {e.get("a_name", "\0"): "A (your team)", e.get("b_name", "\0"): f"B ({ids['b']})"}
                lines = [ln.replace(e["a_name"], names[e["a_name"]]).replace(e["b_name"], names[e["b_name"]]) if "a_name" in e else ln
                         for ln in e["lines"]]
            us, them, me, trace = ids.get("a", "Team A"), ids.get("b", "Team B"), e["me"], e["trace"]
            if parse_qs(urlparse(self.path).query).get("side") == ["b"] and e.get("trace_b") is not None:
                us, them, me, trace = them, us, {"p1": "p2", "p2": "p1"}[e["me"]], e["trace_b"]
            g = view_from_lines(lines, me, trace)
            g.update(won=e["won"] if me == e["me"] else not e["won"], game=e.get("game") or int(k) + 1, example=True, back=f"/job/{jid}",
                     us=us, them=them)
            if job["tool"] == "fieldplay":
                g.update(back_label="the series vs the field")
            if job["tool"] in ("turn1", "playout"):
                g.update(back_label="the play-out" if job["tool"] == "playout" else "the turn-1 lab")
                if not job["result"].get("full"):
                    g.update(result=None)
            return self._page("game.html", active={"turn1": "preview", "playout": "playout", "fieldplay": "fieldplay"}.get(job["tool"], "h2h"),
                              g=g, pct=pct, pct0=pct0)
        if path.startswith("job/"):
            job = self.jobs.get(path[4:])

            if job is None or (job["tool"] not in TOOLS and job["tool"] not in ("turn1", "muselfplay", "mxcheck", "mxsearch")):
                return self._send(ENV.get_template("base.html").render(missing=True), code=404)
            ahead = self.jobs.ahead_of(job["id"]) if job["status"] == "queued" else 0
            sheets = _preview_sheets(job) if job["tool"] == "preview" and job["status"] == "done" else None
            branches = []
            if job["tool"] == "analyze" and job["status"] == "done":
                from vgc_suite import lines
                try:
                    branches = lines.branches(lines.replay_key(_replay_src(job["params"]["replay"])))
                except Exception:
                    branches = []
            r = job.get("result")
            if job["tool"] == "analyze" and job["status"] == "done" and _i18n.language() != "en":
                r = _renarrated(job) or r
            return self._page("job.html", job=job, r=r, ahead=ahead, sheets=sheets, branches=branches,
                              linemsg=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("linemsg", [None])[0],
                              local=self._local(), line_name=_line_name(job),
                              active="preview" if job["tool"] == "turn1" else "slot" if job["tool"] == "validate" and is_slot_run(job) else job["tool"])
        if path.startswith("api/job/"):
            job = self.jobs.get(path[8:])
            return self._send(json.dumps({"status": job["status"] if job else "missing", "progress": (job or {}).get("progress"),
                                          "bar": _bar((job or {}).get("progress_meta"))}), "application/json")
        self._send("not found", "text/plain", 404)

    def _crawler_get(self, path: str) -> None:

        from urllib.parse import parse_qs as _pq
        from vgc_suite import lines
        from vgc_suite.core import crawler
        from vgc_suite.core.models import newest_checkpoint
        q = _pq(urlparse(self.path).query)
        if path == "crawler":
            return self._page("crawler.html", active="crawler", sessions=crawler_sessions(), history=[], prefill={}, can_swap=False)
        sid = path.split("/")[2]
        if suite_lock.state() is not None:
            return self._locked_page()
        c = crawler.open_session(sid, newest_checkpoint(), self.jobs.device)
        if c is None:
            return self._send("no such crawl", "text/plain", 404)
        nid = q.get("n", ["0"])[0]
        if nid not in c.data["nodes"]:
            nid = "0"
        try:
            ev = c.evaluate(nid)
        except Exception as e:
            return self._send(f"crawler error: {type(e).__name__}: {e}", "text/plain; charset=utf-8", 500)
        rows, trail = crawler_tree(c.data, nid)
        node = c.data["nodes"][nid]
        try:
            dice = c.dice(nid)
        except Exception:
            dice = []
        return self._page("crawler_session.html", active="crawler", c=c.data, nid=nid, node=node, ev=ev, rows=rows, trail=trail, dice=dice,
                          turn=next(r["turn"] for r in rows if r["id"] == nid), err=q.get("err", [""])[0], msg=q.get("msg", [""])[0], STATUS=crawler.STATUS,
                          BOOSTS=crawler.BOOSTS, PASS=crawler.PASS, line_name=lines.default_name(),
                          branches=lines.branches(lines.crawl_key(c.data["id"], nid)))

    def _crawler_post(self, path: str, params: dict) -> None:
        from urllib.parse import quote
        from vgc_suite.core import crawler
        from vgc_suite.core.models import newest_checkpoint
        from vgc_suite.core.teams import lookup_team
        if path == "crawler":
            from vgc_suite.formats import tool_format
            try:
                fmt = tool_format(params.get("format"))
            except ValueError as e:
                return self._send(str(e), "text/plain; charset=utf-8", 400)
            try:
                a, b = _read(_team_src(params.get("a", "")), fmt, "Team A"), _read(_team_src(params.get("b", "")), fmt, "Team B")
            except BadInput as e:
                return self._send(str(e), "text/plain; charset=utf-8", 400)
            oa, _ = _turn1_bring({**params, "ai": "c"}, "a", [], a)
            ob, _ = _turn1_bring({**params, "bi": "c"}, "b", [], b)
            names = {s: (params.get(f"name_{s}") or "").strip()[:40] or d for s, d in (("a", "Team A"), ("b", "Team B"))}
            c = crawler.new_session([a, b], [oa["bring"], ob["bring"]], names, newest_checkpoint(), self.jobs.device, fmt=fmt)
            return self._redirect(f"/crawler/s/{c.data['id']}")
        sid = path.split("/")[2]
        c = crawler.open_session(sid, newest_checkpoint(), self.jobs.device)
        if c is None:
            return self._send("no such crawl", "text/plain", 404)
        nid = params.get("n", "0")
        try:
            if params.get("mode") == "reroll":
                node = c.data["nodes"][nid]
                child = c.play(node["parent"], node["actions"])
            elif params.get("mode") == "dice":
                node = c.data["nodes"][nid]
                draws = node.get("draws", [])
                keep = {tuple(o[:5]): o for o in node.get("overrides", [])}
                for i, d in enumerate(draws):
                    v = params.get(f"d{i}", "")
                    key = (d[0], d[1], d[2], d[4], d[5])
                    if v == "":
                        keep.pop(key, None)
                    else:
                        keep[key] = [*key, int(v)]
                child = c.play(node["parent"], node["actions"], seed=node["seed"], overrides=list(keep.values()))
            else:
                acts = [[[int(params.get(f"{s}{k}", crawler.PASS) or crawler.PASS), int(params.get(f"{s}{k}m") == "1")] for k in (0, 1)]
                        for s in ("a", "b")]
                child = c.play(nid, acts)
            c.save()
        except Exception as e:
            return self._redirect(f"/crawler/s/{sid}?n={nid}&err=" + quote(f"{type(e).__name__}: {e}"[:300]))
        return self._redirect(f"/crawler/s/{sid}?n={child}")

    def _redirect(self, where: str) -> None:
        self.send_response(303)
        self.send_header("Location", where)
        self.end_headers()

    def _locked_page(self) -> None:
        s = suite_lock.state() or {}
        self.send_response(503)
        body = ENV.get_template("locked.html").render(lock=s, active="")
        data = body.encode("utf8")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _local(self) -> bool:


        return self.client_address[0] in ("127.0.0.1", "::1") or self.client_address[0] in _own_addresses()

    def _buckets_page(self, msgs: list[str] | None = None, edit: str | None = None, text: str | None = None,
                      note: str | None = None, ok: bool = False, fmt: str | None = None) -> None:

        from vgc_suite.core import buckets
        if edit is None:
            edit = parse_qs(urlparse(self.path).query).get("edit", [""])[0]
        if edit and text is None and edit in buckets.names():
            text, note, fmt = buckets.to_text(edit), buckets.get(edit).get("note", ""), buckets.format_of(edit)
        return self._page("buckets.html", active="buckets", buckets=buckets.summaries(), msgs=msgs or [], ok=ok, edit=edit or "",
                          text=text or "", note=note or "", fmt=fmt or ENV.globals["current_format"])

    def _buckets_post(self, action: str) -> None:
        from vgc_suite.core import buckets
        n = min(int(self.headers.get("Content-Length") or 0), 2_000_000)
        params = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf8"), keep_blank_values=True).items()}
        name, old = params.get("name", "").strip(), params.get("old", "").strip()
        if action == "save":
            fmt = params.get("format") or ENV.globals["current_format"]
            b, problems = buckets.save(name, params.get("text", ""), params.get("note", ""), old_name=old or None, fmt=fmt)
            if problems:
                return self._buckets_page(problems, edit=old, text=params.get("text", ""), note=params.get("note", ""), fmt=fmt)
            return self._buckets_page([_i18n.t("Saved bucket {name}: {n} {format} teams.", name=name, n=len(b['teams']), format=ENV.globals['format_short'].get(fmt, fmt))],
                                      edit=name, ok=True)
        if action == "delete" and name in buckets.names():
            buckets.delete(name)
            return self._buckets_page([_i18n.t("Deleted bucket {name}.", name=name)], edit="", ok=True)
        return self._send("not found", "text/plain", 404)

    def _buddy_page(self, msgs: list[str] | None = None, who: str = "") -> None:
        from vgc_suite import buddy
        try:
            d = buddy.page_data(ROOT, who)
        except Exception as e:
            return self._send(f"buddy page error: {type(e).__name__}: {e}", "text/plain; charset=utf-8", 500)
        return self._page("buddy.html", active="buddy", d=d, msgs=msgs or [], local=self._local())

    def _buddy_post(self, action: str) -> None:
        from vgc_suite import buddy
        n = min(int(self.headers.get("Content-Length") or 0), 200_000)
        params = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf8"), keep_blank_values=True).items()}
        if action == "settings":

            drills = {k.split("@", 1)[1]: ([params.get(f"lead1@{k.split('@', 1)[1]}", ""), params.get(f"lead2@{k.split('@', 1)[1]}", "")],
                                           [params.get(f"back1@{k.split('@', 1)[1]}", ""), params.get(f"back2@{k.split('@', 1)[1]}", "")])
                      for k in params if k.startswith("lead1@")}
            msgs = buddy.save_settings(ROOT, params.get("user", ""), params.get("team", ""), params.get("rotation") == "on",
                                       params.get("sheets") == "on", fmt=params.get("team_fmt") or buddy.CURRENT, drills=drills,
                                       coach=params.get("coach") == "on")
        elif action in ("session-start", "session-end", "session-resume", "session-delete", "session-add", "session-remove"):
            from vgc_suite import buddy_sessions as bs
            cfg, user = bs.BOTS.get(params.get("bot", "")), params.get("user", "").strip()
            if cfg is None or not user:
                msgs = [_i18n.t("Pick the bot and your Showdown name.")]
            else:
                where = bs.path_for(ROOT / cfg["profiles"])
                gone = _i18n.t("That session isn't there any more.")
                if action == "session-start":
                    new, closed = bs.start(where, user, params.get("name", ""))
                    msgs = [_i18n.t("Session \"{name}\" started for {user} on {bot}: games from now on are grouped below.", name=new['name'],
                                    user=user, bot=_i18n.t(cfg['label']))
                            + (" " + _i18n.t("(Closed \"{name}\" first.)", name=closed['name']) if closed else "")]
                elif action == "session-resume":
                    s, folded = bs.resume(where, user, params.get("start", ""))
                    msgs = [_i18n.t("Session \"{name}\" is running again.", name=s['name'])
                            + (" " + _i18n.t("Folded in {n} later session(s).", n=len(folded)) if folded else "") if s else gone]
                elif action in ("session-add", "session-remove"):
                    start_, room = params.get("start", ""), params.get("room", "")
                    s = (bs.add_game if action == "session-add" else bs.remove_game)(where, user, start_, room)
                    msgs = [(_i18n.t("Game added to \"{name}\".", name=s['name']) if action == "session-add"
                             else _i18n.t("Game taken out of \"{name}\".", name=s['name'])) if s else gone]
                elif action == "session-delete":
                    s = bs.delete(where, user, params.get("start", ""))
                    msgs = [_i18n.t("Session \"{name}\" deleted (its games are untouched).", name=s['name']) if s else gone]
                else:
                    s = bs.end(where, user)
                    msgs = [_i18n.t("Session \"{name}\" ended.", name=s['name']) if s
                            else _i18n.t("{user} has no session running on {bot}.", user=user, bot=_i18n.t(cfg['label']))]


            from urllib.parse import urlencode
            self.send_response(303)
            self.send_header("Location", "/buddy?" + urlencode({"msg": msgs[0]}) + "#sessions")
            self.end_headers()
            return
        elif action == "line":
            from urllib.parse import urlencode
            from vgc_suite import lines
            room, side, me = params.get("room", ""), params.get("side", ""), params.get("me", "").strip()
            meta = lines.info(room)
            turn = _int(params, "turn", 1, 999)
            if not self._local():
                ok, msg = False, _i18n.t("Reopening a game works only from this PC itself (this page opened at 127.0.0.1).")
            elif meta is None:
                ok, msg = False, _i18n.t("This game can't be reopened: it has no saved choices (games before 11-08, or not played on the local server).")
            elif side not in ("p1", "p2") or not me:
                ok, msg = False, _i18n.t("Give your side and your Showdown name.")
            elif not 1 <= turn <= meta["turns"]:
                ok, msg = False, _i18n.t("Pick a turn from {lo} to {hi}.", lo=1, hi=meta['turns'])
            else:
                ok, msg = lines.start(room, turn, me, side, params.get("mode") == "same", self.jobs.device)
                if ok and OPEN_WINDOW is not None:
                    from vgc_suite.core.h2h_examples import ensure_local_server
                    if not ensure_local_server():
                        OPEN_WINDOW(SHOWDOWN_URL, "Showdown - training buddy")
            self.send_response(303)
            self.send_header("Location", f"/status/game/{room}?" + urlencode({"pov": "human", "linemsg": msg}))
            self.end_headers()
            return
        elif action == "line-replay":
            from urllib.parse import urlencode
            from vgc_suite import lines
            job = self.jobs.get(params.get("job", ""))
            side, me = params.get("side", ""), params.get("me", "").strip()
            turn = _int(params, "turn", 1, 999)
            turns = [t["turn"] for t in (((job or {}).get("result") or {}).get("narration") or {}).get("turns", []) if t["turn"] >= 1]
            if not self._local():
                ok, msg = False, _i18n.t("Opening a position works only from this PC itself (this page opened at 127.0.0.1).")
            elif job is None or job["tool"] != "analyze" or not turns:
                ok, msg = False, _i18n.t("That analysis isn't here any more: analyze the replay again.")
            elif side not in ("p1", "p2") or not me:
                ok, msg = False, _i18n.t("Give your side and your Showdown name.")
            elif turn not in turns:
                ok, msg = False, _i18n.t("Pick a turn from {lo} to {hi}.", lo=min(turns), hi=max(turns))
            else:
                try:
                    src = _replay_src(job["params"]["replay"])
                except BadInput as e:
                    ok, msg = False, str(e)
                else:
                    ok, msg = lines.start_replay(src, turn, me, side, self.jobs.device, back=f"/job/{job['id']}")
                    if ok and OPEN_WINDOW is not None:
                        from vgc_suite.core.h2h_examples import ensure_local_server
                        if not ensure_local_server():
                            OPEN_WINDOW(SHOWDOWN_URL, "Showdown - training buddy")
            self.send_response(303)
            self.send_header("Location", f"/job/{(job or {}).get('id', '')}?" + urlencode({"linemsg": msg}))
            self.end_headers()
            return
        elif action in ("start", "stop"):
            if not self._local():
                msgs = [_i18n.t("Start and stop work only from this PC itself (this page opened at 127.0.0.1).")]
            else:
                msgs = [buddy.start_practice(ROOT) if action == "start" else buddy.stop_practice(ROOT)]
        else:
            return self._send("not found", "text/plain", 404)
        return self._buddy_page(msgs)

    def do_POST(self) -> None:
        if self._foreign(True):
            return
        tool = urlparse(self.path).path.strip("/")
        if not PRIVATE and private_route(tool):
            return self._send("Not in this build.", "text/plain; charset=utf-8", 404)
        if tool == "app/quit":
            if not BROWSER_MODE or QUIT_APP is None or not self._local():
                return self._send("Not from this app.", "text/plain; charset=utf-8", 403)
            threading.Timer(0.5, QUIT_APP).start()
            return self._page("base.html", closed=True, standalone=True)
        if suite_lock.state() is not None and tool != "api/species":
            return self._locked_page()
        if tool == "api/cancel":
            n = min(int(self.headers.get("Content-Length") or 0), 10_000)
            jid = parse_qs(self.rfile.read(n).decode("utf8")).get("id", [""])[0]
            job = self.jobs.jobs.get(jid)
            if job is not None and job["status"] in ("queued", "running"):
                job["cancel"] = True
                if job["status"] == "queued":
                    job["progress"] = _i18n.t("cancelled - it won't start")
            self.send_response(303)
            self.send_header("Location", f"/job/{jid}")
            self.end_headers()
            return
        if tool == "lang":
            n = min(int(self.headers.get("Content-Length") or 0), 2_000)
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf8")).items()}
            from vgc_trainer import i18n
            if form.get("to") in i18n.LANGUAGES or form.get("to") == i18n.PSEUDO:
                i18n.set_language(form["to"])
            back = form.get("back") or "/"
            self.send_response(303)
            self.send_header("Location", back if back.startswith("/") and not back.startswith("//") else "/")
            self.end_headers()
            return
        if tool.startswith("buddy/"):
            return self._buddy_post(tool[6:])
        if tool.startswith("buckets/"):
            return self._buckets_post(tool[8:])
        if tool.startswith("crawler/s/") and tool.endswith("/showdown"):
            n = min(int(self.headers.get("Content-Length") or 0), 100_000)
            params = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf8"), keep_blank_values=True).items()}
            from urllib.parse import quote
            from vgc_suite import lines
            from vgc_suite.core import crawler
            from vgc_suite.core.models import newest_checkpoint
            sid, nid = tool.split("/")[2], params.get("n", "0")
            c = crawler.open_session(sid, newest_checkpoint(), self.jobs.device)
            if c is None or nid not in c.data["nodes"]:
                return self._send("no such crawl node", "text/plain", 404)
            me, side = (params.get("me") or "").strip()[:18], params.get("side") if params.get("side") in ("p1", "p2") else "p1"
            ok, msg = lines.start_crawl(c, nid, me, side, self.jobs.device) if me else (False, "Enter your name on the local Showdown.")

            return self._redirect(f"/crawler/s/{sid}?n={nid}&" + ("msg=" + quote(msg) if ok else "err=" + quote("Couldn't open it: " + msg)))
        if tool == "crawler" or (tool.startswith("crawler/s/") and tool.endswith("/play")):
            n = min(int(self.headers.get("Content-Length") or 0), 2_000_000)
            params = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf8"), keep_blank_values=True).items()}
            try:
                return self._crawler_post(tool, params)
            except BadInput as e:
                return self._send(str(e), "text/plain; charset=utf-8", 400)
        if tool == "api/fav":
            n = min(int(self.headers.get("Content-Length") or 0), 10_000)
            p = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf8"), keep_blank_values=True).items()}
            if not self.jobs.get(p.get("id", "")):
                return self._send(json.dumps({"error": "no such run"}), "application/json")
            return self._send(json.dumps({"fav": set_favorite(p["id"], p.get("on") == "1", p.get("note", ""))}), "application/json")
        if tool == "api/replay-folder":
            if self._local():
                open_replay_folder()
            return self._send(json.dumps({"ok": self._local()}), "application/json")
        if tool == "api/update-check":
            from vgc_suite import about
            return self._send(json.dumps({**about.check_update(), "can_install": QUIT_APP is not None}), "application/json")
        if tool == "api/update-start":
            from vgc_suite import update
            return self._send(json.dumps(update.start() if QUIT_APP and self._local() else {"phase": "error", "error": "Updates install from the desktop app."}), "application/json")
        if tool == "api/update-status":
            from vgc_suite import update
            return self._send(json.dumps(update.status()), "application/json")
        if tool == "api/update-apply":
            from vgc_suite import update
            from vgc_suite.buddy import practice_pid
            if not QUIT_APP or not self._local():
                return self._send(json.dumps({"error": "Updates install from the desktop app."}), "application/json")
            if any(j.get("status") in ("queued", "running") for j in self.jobs.jobs.values()):
                return self._send(json.dumps({"error": "A run is going: let it finish first."}), "application/json")
            if practice_pid(ROOT):
                return self._send(json.dumps({"error": "The practice bot is running: stop it on the Buddy page first."}), "application/json")
            try:
                update.apply(os.getpid())
            except (update.Refused, OSError) as e:
                return self._send(json.dumps({"error": str(e)}), "application/json")
            threading.Timer(0.5, QUIT_APP).start()
            return self._send(json.dumps({"ok": True}), "application/json")
        if tool == "api/species":
            n = min(int(self.headers.get("Content-Length") or 0), 200_000)
            text = parse_qs(self.rfile.read(n).decode("utf8")).get("team", [""])[0]

            mons = [{**m, "label": _i18n.dex("species", m["name"]),
                     "moves": [{**mv, "label": _i18n.dex("move", mv["name"])} for mv in m["moves"]]} for m in team_sheet_info(text)]
            return self._send(json.dumps({"species": [_i18n.dex("species", x) for x in team_sheet_names(text)], "mons": mons}),
                              "application/json")
        if tool == "mxcheck-all":
            n = min(int(self.headers.get("Content-Length") or 0), 10_000)
            dd = parse_qs(self.rfile.read(n).decode("utf8")).get("dd", [""])[0]
            job = self.jobs.get(dd)
            opps = [o["id"] for o in ((job or {}).get("result") or {}).get("opponents") or [] if o.get("brings")]
            gaps = check_gaps(dd, (job or {}).get("result") or {})["teams"]
            for opp in opps:
                if opp in gaps:
                    self.jobs.submit("mxcheck", {"dd": dd, "opp": opp, "gaps": "1"})
            self.send_response(303)
            self.send_header("Location", f"/job/{dd}#brings")
            self.end_headers()
            return
        if tool not in TOOLS and tool not in ("turn1", "muselfplay", "mxcheck", "mxsearch"):
            return self._send("not found", "text/plain", 404)
        n = min(int(self.headers.get("Content-Length") or 0), 2_000_000)
        params = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf8"), keep_blank_values=True).items()}
        if tool == "fieldplay" and params.get("g1", "own") != "own" and params.get("sheet"):

            dd = self.jobs.get(params["sheet"]) or {}
            params.update(team=(dd.get("params") or {}).get("team", ""), field=(dd.get("params") or {}).get("field", "meta"))
        if tool == "mxsearch":
            hit = mxsearches().get((params.get("dd"), params.get("opp")))
            if hit:
                self.send_response(303)
                self.send_header("Location", f"/job/{hit['id']}")
                self.end_headers()
                return None
        if tool == "mxcheck" and params.get("fresh") != "1":
            hit = mxchecks().get((params.get("dd"), params.get("opp")))
            if hit:
                self.send_response(303)
                self.send_header("Location", f"/job/{hit['id']}")
                self.end_headers()
                return
        jid = self.jobs.submit(tool, params)
        self.send_response(303)
        self.send_header("Location", f"/job/{jid}")
        self.end_headers()


def _lan_ip() -> str:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.168.0.1", 9))
        return s.getsockname()[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--device", help="cuda | cpu (default: cuda when available)")
    ap.add_argument("--lan", action="store_true", help="listen on the home network too (no auth: trusted networks only)")
    ap.add_argument("--sprites", default=str(ROOT / "sprites"),
                    help="a folder of Pokemon sprite images for the optional icons (git-ignored; `python -m vgc_suite.sprites --check`)")
    args = ap.parse_args()
    srv, url = start(args.port, args.device, args.lan, Path(args.sprites))
    print(f"suite web on {url}  (device {Handler.jobs.device})", flush=True)
    srv.serve_forever()


def _gpu_info(device: str) -> dict:


    import torch
    name = "CPU"
    try:
        if device == "cuda":
            name = torch.cuda.get_device_name(0)
        elif device == "xpu":
            name = torch.xpu.get_device_name(0)
        elif device == "mps":
            name = "Apple GPU"
    except Exception:
        name = device.upper()
    return {"on": device != "cpu", "name": name}


def start(port: int = 8765, device: str | None = None, lan: bool = False, sprites: Path | None = None) -> tuple[ThreadingHTTPServer, str]:


    SPRITES["dir"] = Path(sprites) if sprites else ROOT / "sprites"
    Handler.lan = lan
    import torch
    Handler.jobs = Jobs(device or pick_device().type)
    ENV.globals["gpu"] = _gpu_info(Handler.jobs.device)
    def _warm_matchups() -> None:
        try:
            from vgc_suite import matchups as mu
            mu.load()
            mu.showdown_series("watch")
            mu.showdown_series("own")
            mu.core4_list()
        except Exception as e:
            print(f"matchups warm-up failed: {type(e).__name__}: {e}", flush=True)
    if PRIVATE:
        threading.Thread(target=_warm_matchups, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0" if lan else "127.0.0.1", port), Handler)
    port = srv.server_address[1]
    return srv, (f"http://{_lan_ip()}:{port} (home network)" if lan else f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    main()

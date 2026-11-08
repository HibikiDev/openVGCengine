





from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import random
import re
import threading
import time
import traceback
from dataclasses import dataclass, field

import vgc_engine as ve
import websockets
import websockets.http11

from .agent import Agent
from .chaos import HIGH_CHAOS, net_bad_luck
from .requests import REQUEST_TARGET, RequestMasks, describe_action, team_choice
from .teams import pack, unpack
from .tracker import Tracker, to_id

VERSION = "0.1"
USER_AGENT = f"{websockets.http11.USER_AGENT} openVGCengine-buddy/{VERSION}"

from .sheets import (
    CLOSED_SHEET_FORMATS,
    COSMETIC_FORMES,
    FALLBACK_ABILITY,
    KEEP_WINNING_LEAD,
    STATUS_COLUMN,
    SV_FORMATS,
    _BASE_STATS,
    _MOVE_DEX,
    _NATURE_MODS,
    _base_stats,
    _champions_stat,
    _move_dex,
    base_format,
    forced_choice,
    handed_sheet,
    lead_rule_v3,
    playable_sheet,
    request_signature,
    sheet_signature,
    stat_points,
)

log = logging.getLogger("showdown")


def recoverable(e: BaseException) -> bool:



    return isinstance(e, Exception) or type(e).__name__ == "PanicException"




CLOCK_FLOOR = 150



SEARCH_DEADLINE = 45.0
DEADLINE_CLOCK_SHARE = 6.0


@dataclass
class Result:
    room: str
    me: str
    winner: str | None
    turns: int
    errors: list = field(default_factory=list)
    raw: list = field(default_factory=list)


class Battle:


    @property
    def in_series(self) -> bool:


        return "bo3" in self.room or self.series is not None

    def __init__(self, client: "BaseClient", room: str):
        self.client, self.room = client, room


        fmt = base_format(room.split("-")[1]) if room.startswith("battle-") and len(room.split("-")) > 2 else None



        self.fmt = fmt if fmt in CLOSED_SHEET_FORMATS else None
        self.engine_fmt = fmt if fmt in CLOSED_SHEET_FORMATS or fmt in SV_FORMATS else None

        self.agent, self.live_search = client.format_models.get(self.engine_fmt, (client.agent, None))
        if self.agent is client.agent:
            self.live_search = None
        self.me: str | None = None
        self.foe_name: str | None = None
        self.my_sheet = client.team
        self.team = client.team
        self.foe_sheet: list[dict] | None = None
        self.my_showteam: list[dict] | None = None
        self.foe_species: list[str] = []
        self.bring: list[int] | None = None
        self.tracker: Tracker | None = None
        self.lines: list[str] = []
        self.request: dict | None = None
        self.decided_rqid = None
        self.ots_sent = False
        self.timer_requested = False
        self.ots: bool | None = None
        self.series: str | None = None
        self.series_game: int | None = None
        self.reply_temp: float | None = None
        self.search_arm: dict | None = None
        self.preview_forfeit = False
        self.lead_arm: str | None = None
        self.cb_arm: str | None = None
        self.turn = 0
        self.clock_total: int | None = None
        self.searching_rqid = None
        self.errors: list[str] = []
        self.raw: list[str] = []
        self.trace: list[dict] = []
        self.timer: asyncio.Task | None = None
        self.done = asyncio.get_running_loop().create_future()

    async def send(self, msg: str) -> None:
        await self.client.send(f"{self.room}|{msg}")


    async def on_message(self, lines: list[str]) -> None:
        had_log = new_request = False


        if self.client.request_timer and not self.timer_requested and self.foe_name:
            self.timer_requested = True
            if self.client.timer_for.get(self.foe_name, True):
                await self.send("/timer on")
        if "|init|battle" in lines and self.raw:
            self._resync()
        self.raw.append("#chunk")
        self.raw.extend(lines)


        past_preview = any(ln.startswith("|turn|") for ln in lines)
        for line in lines:
            if not line.startswith("|"):
                continue
            parts = line.split("|")
            kind = parts[1] if len(parts) > 1 else ""
            if kind == "request":
                if parts[2]:
                    self.request = json.loads("|".join(parts[2:]))
                    self._arm_timer()
                    new_request = True
                continue
            if kind == "player" and len(parts) > 3 and to_id(parts[3]) == to_id(self.client.username):
                self.me = parts[2]
            elif kind == "player" and len(parts) > 3 and parts[3]:
                self.foe_name = to_id(parts[3])
            elif kind == "poke" and self.me and parts[2] != self.me:
                self.foe_species.append(parts[3].split(",")[0])
            elif kind == "showteam" and self.me and parts[2] == self.me:
                self.my_showteam = unpack("|".join(parts[3:]))
            elif kind == "showteam" and self.me and parts[2] != self.me:
                self.foe_sheet = playable_sheet(unpack("|".join(parts[3:])), self.room, self.engine_fmt)
                self.ots = True
                if self.room.split("-")[1] in self.client.random_formats:
                    self._known_spreads()
            elif kind == "uhtml" and len(parts) > 3 and parts[2] == "bestof":
                m = re.search(r'Game (\d+)</strong> of <a href="/(game-bestof\d+-[^"]+)"', line)
                if m:
                    self.series_game, self.series = int(m.group(1)), m.group(2)
            elif kind == "uhtml" and len(parts) > 2 and parts[2] == "otsrequest" and not self.ots_sent and not past_preview:
                self.ots_sent = True

                accept = self.client.ots_for.get(self.foe_name or "", True)
                await self.send("/acceptopenteamsheets" if accept else "/rejectopenteamsheets")
            elif kind == "c" and "/uhtml controls," in line and "confirmready" in line and 'disabled' not in line:

                m = re.search(r'value="([^"]*confirmready[^"]*)"', line)
                if m:
                    await self.client.send(f"|{html.unescape(m.group(1))}")
            elif kind == "turn":
                self.turn = int(parts[2])
            elif kind == "inactive":
                m = re.search(r"Time left: \d+ sec this turn \| (\d+) sec total", line)
                if m:
                    self.clock_total = int(m.group(1))
            elif kind == "error":
                self.errors.append(line)
                log.warning("%s %s", self.room, line)


                rejected = "[Invalid choice]" in line or "[Unavailable choice]" in line
                rq = (self.request or {}).get("rqid")
                self._retries = getattr(self, "_retries", {})
                if rejected and not self.done.done() and "nothing to choose" not in line and self._retries.get(rq, 0) < 3:
                    self._retries[rq] = self._retries.get(rq, 0) + 1
                    self.decided_rqid = None



                    if "[Unavailable choice]" not in line or self._retries[rq] > 1:
                        self._arm_timer(random_fallback=True)
                continue
            elif kind in ("win", "tie"):
                winner = parts[2] if kind == "win" else None
                if self.in_series and self.foe_name:

                    won = bool(winner) and to_id(winner) == to_id(self.client.username)
                    record = self.client.series.setdefault(self.foe_name, [0, 0])
                    record[0 if won else 1] += 1
                    last = self.client.last_leads.get(self.foe_name)
                    try:
                        if self.bring and self.me:
                            self.client.series_leads.setdefault(self.foe_name, []).append(
                                {"lead": [int(i) for i in self.bring[:2]], "won": won, "chaos": round(net_bad_luck(self.raw, self.me), 2)})
                    except BaseException as _exc:
                        if not recoverable(_exc):
                            raise
                        self.errors.append("series leads: " + traceback.format_exc(limit=2))
                    try:
                        if last and self.bring:
                            p, early = self._lead_avoid(won)
                            self.client.last_leads[self.foe_name] = (last[0], last[1], p)
                            log.warning("%s: %s game %s; win estimate by turn 3 %s; the next game avoids lead %s with p %.2f",
                                        self.room, "won" if won else "lost", self.series_game, "?" if early is None else f"{early:.2f}",
                                        "/".join(self.my_sheet[i]["species"] for i in last[0]), p)
                    except BaseException as _exc:
                        if not recoverable(_exc):
                            raise
                        self.errors.append("lead review: " + traceback.format_exc(limit=2))
                    try:
                        prev = self._foe_bring()
                        if prev:
                            self.client.prev_foe_bring[self.foe_name] = tuple([self.foe_sheet[i]["species"] for i in part] for part in prev)
                    except BaseException as _exc:
                        if not recoverable(_exc):
                            raise
                        self.errors.append("foe bring: " + traceback.format_exc(limit=2))
                    try:
                        self._remember_opponent()
                    except BaseException as _exc:
                        if not recoverable(_exc):
                            raise
                        self.errors.append("opponent memory: " + traceback.format_exc(limit=2))
                    try:
                        self._remember_sets()
                    except BaseException as _exc:
                        if not recoverable(_exc):
                            raise
                        self.errors.append("series set memory: " + traceback.format_exc(limit=2))
                    if max(record) >= 2:
                        self.client.series.pop(self.foe_name, None)
                        self.client.last_leads.pop(self.foe_name, None)
                        self.client.series_memory.pop(self.foe_name, None)
                        self.client.prev_foe_bring.pop(self.foe_name, None)
                        self.client.series_leads.pop(self.foe_name, None)
                        self.client.series_facts.pop(self.foe_name, None)
                if not self.done.done():
                    self.done.set_result(Result(self.room, self.client.username, winner, self.turn, self.errors, self.raw))
            self.lines.append(line)
            had_log = True
        if had_log and self.request is not None:
            self._arm_timer(delay=0.0)
        elif new_request and any(ln.startswith(("|turn|", "|upkeep", "|teampreview")) for ln in self.lines):



            self._arm_timer(delay=0.0)

    def _known_spreads(self) -> None:



        want = sorted(sheet_signature(s) for s in self.foe_sheet)
        for team in reversed(self.client.handed):
            if sorted(sheet_signature(s) for s in team) != want:
                continue
            by_sig = {sheet_signature(s): s for s in team}
            for s in self.foe_sheet:
                mine = by_sig.get(sheet_signature(s))
                if mine:
                    s["known_spread"] = [mine.get("nature") or "Hardy", [int((mine.get("evs") or {}).get(k, 0) or 0)
                                                                         for k in ("hp", "atk", "def", "spa", "spd", "spe")]]
            log.warning("%s: the opponent pilots a team we played earlier: its spreads are known", self.room)
            return

    def _preview_waits_mine(self) -> int:
        self._waits_mine = getattr(self, "_waits_mine", 0) + 1
        return self._waits_mine

    def _draw_search_arms(self) -> None:




        closed = self.fmt is not None
        temps = (self.client.closed_reply_temps if closed else None) or self.client.reply_temps
        arms = (self.client.closed_search_arms if closed else None) or self.client.search_arms
        self.reply_temp = self.client.reply_arm.setdefault(self.series or self.room, random.choice(temps))
        self.search_arm = self.client.search_arm.setdefault(self.series or self.room, random.choice(arms))

    async def _late_join_sheets(self) -> None:



        self.foe_sheet = playable_sheet([{"name": s, "species": s, "item": "", "ability": "", "moves": []}
                                         for s in self.foe_species], self.room, self.engine_fmt)
        self.ots = False
        if self.fmt is None:
            log.warning("%s: joined past team preview with no open sheet for the opponent - species only", self.room)
            self.errors.append("late join: no open sheet for the opponent (species only)")
        else:
            log.info("%s: joined past team preview on closed sheets - species and what the battle has shown", self.room)

    def _resync(self) -> None:



        log.warning("%s: the battle was sent again (a reconnect); rebuilding it from the log", self.room)
        self.tracker, self.lines, self.raw, self.foe_species = None, [], [], []
        self.request, self.decided_rqid = None, None

    def _drill_bring(self) -> bool:




        drill = self.client.bring_for.get(to_id(self.foe_name or ""))
        if not drill or len(drill.get("lead") or []) != 2:
            return False
        def idx(name: str) -> int | None:
            ids = [to_id(m.get("species") or m.get("name") or "") for m in self.my_sheet]
            want = to_id(name)
            if want in ids:
                return ids.index(want)
            base = to_id(name.split("-")[0])
            hits = [i for i, x in enumerate(ids) if to_id((self.my_sheet[i].get("species") or "").split("-")[0]) == base]
            return hits[0] if len(hits) == 1 else None
        lead = [idx(s) for s in drill["lead"]]
        back = [idx(s) for s in drill.get("back") or []]
        if None in lead or len(set(lead)) != 2:
            log.warning("%s: drill lead %s isn't on our sheet - ignored", self.room, drill["lead"])
            return False
        if len(back) == 2 and None not in back and len(set(lead + back)) == 4:
            self.bring = lead + back
        else:
            self.bring = self.agent.choose_bring(self.my_sheet, self.foe_sheet, force_lead=lead, fmt=self.engine_fmt, closed=self.fmt is not None)
        log.warning("%s: drill bring %s", self.room, "/".join(self.my_sheet[i]["species"] for i in self.bring))
        return True

    def _bring_from_request(self, req: dict, names: list[str]) -> list[int] | None:



        party = (req.get("side") or {}).get("pokemon") or []
        idents = [to_id(p["ident"].split(": ", 1)[1]) for p in party]
        if not party or all(n in names for n in idents):
            return None
        sheet_names = [to_id(s.get("name") or s["species"]) for s in self.my_sheet]
        out: list[int] = []
        for p, n in zip(party, idents):
            sp = to_id(p.get("details", "").split(",")[0])
            k = next((i for i, x in enumerate(sheet_names) if x == n and i not in out), None)
            if k is None:
                k = next((i for i, s in enumerate(self.my_sheet) if i not in out and (to_id(s["species"]) == sp or sp.startswith(to_id(s["species"]))
                                                                                       or to_id(s["species"]).startswith(sp))), None)
            if k is None:
                return None
            out.append(k)
        if len(out) != len(party) or set(out) == set(self.bring):
            return None
        return out

    async def _counter_bring(self, key: str | None, req: dict) -> None:


        prev = self.client.prev_foe_bring.get(key) if key else None
        if prev and self.foe_sheet:
            sp = [s["species"] for s in self.foe_sheet]
            prev = ([sp.index(x) for x in prev[0] if x in sp], [sp.index(x) for x in prev[1] if x in sp])
            prev = prev if len(prev[0]) == 2 else None
        if self.cb_arm == "cb" and prev and (self.series_game or 1) >= 2 and self.client.counter_bring is not None and self.ots:


            rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "room": self.room, "series": self.series, "game": self.series_game,
                   "foe": self.foe_name, "today": list(self.bring), "prev_lead": prev[0], "prev_shown": prev[1]}
            self.searching_rqid = req.get("rqid")
            try:


                bring, info = await asyncio.wait_for(
                    asyncio.to_thread(self.client.counter_bring.choose, self.my_sheet, self.foe_sheet, prev[0], prev[1]), CB_DEADLINE)
                self.bring = [int(i) for i in bring]
                rec.update(info, bring=self.bring)
                log.warning("%s: counter-bring G%s: %s vs their %s (WR %.2f, today's pick %s; %d ms)", self.room, self.series_game,
                            "/".join(self.my_sheet[i]["species"] for i in self.bring),
                            "/".join(self.foe_sheet[i]["species"] for i in info["target"]), info["wr"][info["pick"]],
                            "/".join(self.my_sheet[i]["species"] for i in rec["today"]), info["ms"])
            except BaseException as e:
                if not recoverable(e):
                    raise
                rec["fallback"] = f"{type(e).__name__}: {str(e)[:160]}"
                log.warning("%s: counter-bring failed, playing today's pick (%s)", self.room, rec["fallback"])
            finally:
                self.searching_rqid = None
            if self.client.cb_log:
                try:
                    with open(self.client.cb_log, "a", encoding="utf8") as f:
                        f.write(json.dumps(rec) + "\n")
                except OSError:
                    pass

    def _foe_bring(self) -> tuple[list[int], list[int]] | None:


        if not self.foe_sheet or not self.me:
            return None
        foe = "p2" if self.me == "p1" else "p1"
        names = [(s.get("species") or "").lower() for s in self.foe_sheet]

        def index(details: str) -> int | None:
            sp = details.split(",")[0].strip().lower()
            for i, n in enumerate(names):
                if n == sp:
                    return i
            base = sp.split("-mega")[0]
            hits = [i for i, n in enumerate(names) if n and (n == base or base.startswith(n + "-") or n.startswith(base + "-"))]
            return hits[0] if len(hits) == 1 else None

        lead: dict[str, int] = {}
        shown: list[int] = []
        started = False
        for ln in self.raw:
            q = ln.split("|")
            if len(q) > 2 and q[1] == "turn":
                started = True
            elif len(q) > 3 and q[1] in ("switch", "drag") and q[2].startswith(foe):
                i = index(q[3])
                if i is None:
                    continue
                if not started and q[2][2] in "ab" and q[2][2] not in lead:
                    lead[q[2][2]] = i
                elif i not in lead.values() and i not in shown:
                    shown.append(i)
        if set(lead) != {"a", "b"}:
            return None
        return [lead["a"], lead["b"]], shown[:2]

    def _remember_opponent(self) -> None:


        t = self.tracker
        if t is None:
            return
        mem = self.client.series_memory.get(self.foe_name)
        if mem is None or time.monotonic() - mem["when"] > 3600:
            mem = {"used": {}, "brought": set(), "games": 0}
        for i, m in enumerate(t.mons[t.foe]):
            if m.brought:
                mem["brought"].add(i)
            for mid, k in m.used.items():
                mem["used"].setdefault(i, {})
                mem["used"][i][mid] = mem["used"][i].get(mid, 0) + k
        mem["games"] += 1
        mem["when"] = time.monotonic()
        self.client.series_memory[self.foe_name] = mem

    def _lead_avoid(self, won: bool) -> tuple[float, float | None]:





        base = self.client.bo3_lead_avoid
        est = [e["why"]["win"] for e in self.trace if e.get("why") and e.get("turn", 99) <= 3]
        early = est[-1] if est else None
        if early is None:
            return (1.0 if not won else base), None
        if not won:
            return (0.9 if early < 0.35 else 0.75 if early < 0.6 else 0.25), early
        return (0.1 if early >= 0.75 else base), early

    def _arm_timer(self, random_fallback: bool = False, delay: float = 1.0) -> None:



        if self.timer and not self.timer.done():
            self.timer.cancel()

        async def later():
            if delay > 0:
                await asyncio.sleep(delay)
            await self.decide(random_fallback)

        self.timer = asyncio.get_running_loop().create_task(later())


    async def decide(self, random_fallback: bool = False) -> None:
        req = self.request
        if req is None or req.get("wait") or self.decided_rqid == req.get("rqid") or self.searching_rqid == req.get("rqid"):
            return
        if req.get("teamPreview") and not self.preview_forfeit and self.client.pre_game_check is not None and self.foe_name:
            try:
                go = self.client.pre_game_check(self)
            except Exception as _exc:
                go = False
                self.errors.append(f"pre-game check: {type(_exc).__name__}: {_exc}")
            if go:
                self.preview_forfeit = True
                self.decided_rqid = req.get("rqid")
                log.warning("%s: forfeit at team preview vs %s (%s; %s)", self.room, self.foe_name, self.client.forfeit_note,
                            "whole series" if self.series else "this game")

                if self.series:
                    await self.client.send(f"{self.series}|/forfeit")
                else:
                    await self.send("/forfeit")
                return
        if req.get("teamPreview"):

            seen = sorted(request_signature(p) for p in req["side"]["pokemon"])
            for sheet in self.client.teams:
                if sorted(sheet_signature(s) for s in sheet) == seen:
                    self.my_sheet = self.team = sheet
                    break
            else:
                if self.room.split("-")[1] in self.client.random_formats:
                    if self.my_showteam is None and not random_fallback and self._preview_waits_mine() < 15:
                        self._arm_timer()
                        return
                    self.my_sheet = self.team = playable_sheet(handed_sheet(req["side"]["pokemon"], self.my_showteam),
                                                              self.room, self.engine_fmt)

                    self.client.handed = (self.client.handed + [self.my_sheet])[-20:]
                    log.warning("%s: random team %s", self.room, ", ".join(s["species"] for s in self.my_sheet))


            self.my_sheet = [dict(s, name=p["ident"].split(": ", 1)[1]) for s, p in zip(self.my_sheet, req["side"]["pokemon"])]
            if self.foe_sheet is None and not random_fallback and self.fmt is None:

                self._preview_waits = getattr(self, "_preview_waits", 0) + 1
                if self._preview_waits < 15:
                    self._arm_timer()
                    return
            if self.foe_sheet is None:
                (log.info if self.fmt else log.warning)("%s: no open team sheet from the opponent, playing on species only", self.room)

                self.foe_sheet = playable_sheet([{"name": s, "species": s, "item": "", "ability": "", "moves": []}
                                                 for s in self.foe_species], self.room, self.engine_fmt)
                self.ots = False

            key = self.foe_name if self.in_series else None
            self.cb_arm = self.client.cb_arm.setdefault(self.series or self.room, random.choice(self.client.cb_arms))
            self.lead_arm = self.client.lead_arm.setdefault(self.series or self.room, random.choice(self.client.lead_arms))
            if key and self.series_game == 1:



                self.client.last_leads.pop(key, None)
                self.client.series.pop(key, None)
                self.client.series_memory.pop(key, None)
                self.client.prev_foe_bring.pop(key, None)
                self.client.series_leads.pop(key, None)
                self.client.series_facts.pop(key, None)
            last = self.client.last_leads.get(key) if key else None
            avoid = None
            if self.lead_arm == "v3" and key and self.client.series_leads.get(key):
                lead_kw = lead_rule_v3(self.client.series_leads[key], random.random())
                self.lead_v3 = lead_kw

                ls = self.live_search or self.client.live_search
                alt = (self.client.lead_preview or getattr(ls, "foe_preview", None)) if self.engine_fmt is None else None
                self.bring = self.agent.choose_bring(self.my_sheet, self.foe_sheet, fmt=self.engine_fmt, closed=self.fmt is not None,
                                                     alt_head=alt, **lead_kw)
            else:
                if last and time.monotonic() - last[1] < 3600 and random.random() < (last[2] if len(last) > 2 else self.client.bo3_lead_avoid):
                    avoid = last[0]
                self.bring = self.agent.choose_bring(self.my_sheet, self.foe_sheet, avoid_lead=avoid, fmt=self.engine_fmt,
                                                     closed=self.fmt is not None)
            drilled = self._drill_bring()
            pv = getattr(self.agent, "last_preview", None)
            if self.client.force_bring is not None:
                self.bring = [int(i) for i in self.client.force_bring]
            elif self.client.g1_bring is not None and (not self.in_series or self.series_game == 1):
                self.bring = [int(i) for i in self.client.g1_bring]
            elif not drilled:
                try:
                    await self._counter_bring(key, req)
                except BaseException as e:
                    if not recoverable(e):
                        raise
                    self.errors.append("counter-bring: " + traceback.format_exc(limit=2))
            self._draw_search_arms()
            if pv:
                log.warning("%s: preview lead %s (p %.2f, head's top pair p %.2f)%s", self.room,
                         "/".join(self.my_sheet[i]["species"] for i in self.bring[:2]), pv["lead_p"], pv["top_p"],
                         " - changed from the last game's lead" if pv["changed"] else "")
            if key:
                self.client.last_leads[key] = (self.bring[:2], time.monotonic())
            sp = [s_["species"] for s_ in self.my_sheet]
            self.trace.append({"turn": 0, "choice": team_choice(self.bring), "preview": {
                "bring": [sp[i] for i in self.bring], **({"lead_p": pv["lead_p"], "top_p": pv["top_p"], "changed": pv["changed"],
                "by_human_head": pv.get("by_human_head", False),
                "top_pairs": [[[sp[i] for i in k], p_] for k, p_ in pv.get("top_pairs", [])]} if pv else {})}})
            self.decided_rqid = req.get("rqid")
            await self.send(f"/choose {self.client.choice_text(team_choice(self.bring))}|{req.get('rqid')}")
            return
        if self.client.stop_after_turn is not None and self.turn > self.client.stop_after_turn and not req.get("forceSwitch"):
            self.decided_rqid = req.get("rqid")
            await self.send("/forfeit")
            return
        late = self.bring is None
        if late:

            self.bring = list(range(4))
            if self.search_arm is None:
                self._draw_search_arms()
        if self.foe_sheet is None and self.me:
            await self._late_join_sheets()
        names = [to_id(self.my_sheet[i].get("name") or self.my_sheet[i]["species"]) for i in self.bring]
        actual = self._bring_from_request(req, names)
        if actual is not None and late:
            self.bring = actual
            names = [to_id(self.my_sheet[i].get("name") or self.my_sheet[i]["species"]) for i in self.bring]
            self.tracker = None
        elif actual is not None:


            log.warning("%s: the request's party is not our bring %s - using %s", self.room, self.bring, actual)
            self.errors.append(f"bring mismatch: chose {self.bring}, the server has {actual}")
            self.bring = actual
            names = [to_id(self.my_sheet[i].get("name") or self.my_sheet[i]["species"]) for i in self.bring]
            self.tracker = None
        try:
            if self.tracker is None:
                self.tracker = Tracker(self.me, self.my_sheet, self.foe_sheet, fmt=self.engine_fmt)


            lines, self.lines = self.lines, []
            for line in lines:
                try:
                    self.tracker.feed([line])
                except BaseException as _exc:
                    if not recoverable(_exc):
                        raise
                    self.errors.append(f"tracker skipped {line[:120]!r}: " + traceback.format_exc(limit=2))
                    log.warning("%s tracker skipped a line it can't follow: %s\n%s", self.room, line[:200], traceback.format_exc(limit=2))
            self.tracker.set_request(req)
            masks = RequestMasks(req, names, self.tracker)
            obs = self.tracker.observe()
        except BaseException as _exc:
            if not recoverable(_exc):
                raise
            names_seen = self.tracker.names if self.tracker else None
            self.errors.append(f"tracker (me={self.me}, names={names_seen}): " + traceback.format_exc(limit=3))
            log.warning("%s tracker failed, playing at random: %s", self.room, traceback.format_exc(limit=3))
            obs = None
            random_fallback = True
            try:
                masks = RequestMasks(req, names)
            except BaseException as _exc:
                if not recoverable(_exc):
                    raise
                self.errors.append("masks: " + traceback.format_exc(limit=3))
                self.decided_rqid = req.get("rqid")
                await self.send(f"/choose {self.client.choice_text('default')}|{req.get('rqid')}")
                return
        if not masks.to_move:
            return
        forced = (self.client.force_turns or {}).get(self.turn) if not req.get("forceSwitch") else None
        choice = forced_choice(req, forced, self.my_sheet) if forced else None
        if choice:
            self.decided_rqid = req.get("rqid")
            self.trace.append({"turn": self.turn, "rqid": req.get("rqid"), "choice": choice, "forced": True})
            self.tracker.note_choice(choice)
            await self.send(f"/choose {self.client.choice_text(choice)}|{req.get('rqid')}")
            return
        if forced:
            self.trace.append({"turn": self.turn, "forced_skipped": True})
        searched = None
        explained = None


        if random_fallback or obs is None:
            actions = self.client.random_agent.act(None, masks, self.bring)
        else:
            play_ctx = self._play_context(req)
            actions = self.agent.act(obs, masks, self.bring, play_ctx)
            explained = self.agent.last_explain

            ls = (self.live_search or self.client.live_search) if self.fmt is None or self.client.closed_sheet_search else None
            if ls is not None and not req.get("forceSwitch"):
                t0 = time.monotonic()
                try:
                    value = (explained or {}).get("value")
                    memory = self.client.series_memory.get(self.foe_name) if self.in_series else None
                    arm, guard = self.search_arm, False
                    if arm and arm.get("rollouts") and self.clock_total is not None and self.clock_total < CLOCK_FLOOR:
                        arm, guard = dict(arm, rollouts=0, deepen=[]), True


                    raw = list(self.raw) if self.fmt is not None else None

                    def run(tracker=self.tracker, sheets=(self.my_sheet, self.foe_sheet), bring=self.bring, arm=arm, explained=explained):
                        t_wait = time.monotonic()
                        with self.client.search_lock:
                            waited = time.monotonic() - t_wait
                            t_world = time.monotonic()
                            world = self._foe_world(raw) if raw is not None else None
                            world_ms = round(1000 * (time.monotonic() - t_world))
                            out = ls.choose(tracker, req, sheets[0], sheets[1], bring, masks, play_ctx, value, memory,
                                            reply_temp=self.reply_temp or 1.0, arm=arm, explain=explained,
                                            foe_world=world, fmt=self.fmt)
                            if raw is not None and ls.last is not None:
                                ls.last["world_ms"] = world_ms


                                ls.last["world"] = [{"species": w_["species"], "moves": list(w_["moves"])} for w_ in world]
                                ls.last["world_active"] = list(tracker.shown[tracker.foe])
                            return out, dict(ls.last or {}, lock_ms=round(1000 * waited))
                    self.searching_rqid = req.get("rqid")
                    try:
                        if self.client.search_deadline:

                            deadline = self.client.search_deadline
                            if self.client.deadline_clock_share and self.clock_total is not None:
                                deadline = min(deadline, self.clock_total / self.client.deadline_clock_share)
                            left = deadline - (time.monotonic() - getattr(self.client, "msg_t", t0))
                            actions, last = await asyncio.wait_for(asyncio.to_thread(run), max(left, 1.0))
                        else:
                            actions, last = await asyncio.to_thread(run)
                    finally:
                        self.searching_rqid = None
                    searched = dict(last, ms=round(1000 * (time.monotonic() - t0)),
                                    queue_ms=round(1000 * (t0 - getattr(self.client, "msg_t", t0))))
                    if guard:
                        searched["clock_guard"] = self.clock_total
                except BaseException as e:
                    if not recoverable(e):
                        raise
                    searched = {"fallback": f"{type(e).__name__}: {str(e)[:120]}"}
        self.decided_rqid = req.get("rqid")
        choice = masks.choice(actions)
        self.trace.append({"turn": self.turn, "rqid": req.get("rqid"), "actions": actions, "choice": choice, "masks": list(masks.actions),
                           "random": bool(random_fallback or obs is None),
                           "obs_active": None if obs is None else [[int(t) for t in range(12) if obs[2][t, 2 + k] > 0.5] for k in (0, 1)],
                           "req_active": [p["ident"] for p in req["side"]["pokemon"] if p.get("active")]})
        if searched is not None:
            self.trace[-1]["search"] = searched
            if "cands" in searched:
                try:
                    searched["view"] = self._search_view(req, searched)
                except BaseException as _exc:
                    if not recoverable(_exc):
                        raise
                    searched["view_error"] = f"{type(_exc).__name__}: {str(_exc)[:120]}"
        if explained:
            try:
                self.trace[-1]["why"] = self._why(req, explained, actions)
            except BaseException as _exc:
                if not recoverable(_exc):
                    raise
                self.trace[-1]["why_error"] = traceback.format_exc(limit=2)
        self.tracker.note_choice(choice)
        await self.send(f"/choose {self.client.choice_text(choice)}|{req.get('rqid')}")

    def _play_context(self, req: dict) -> dict | None:


        try:
            foe = self.tracker.foe
            empty = [i is None or self.tracker.mons[foe][i].fainted for i in self.tracker.shown[foe]]
            active = req.get("active") or []
            damaging = [[bool(_move_dex()[ve.lookup("move", mv["id"]), STATUS_COLUMN] == 0) for mv in active[slot]["moves"]] + [False] * 4
                        if slot < len(active) else [True] * 4 for slot in (0, 1)]
            return {"foe_empty": empty, "damaging": [d[:4] for d in damaging], "turn": self.turn}
        except BaseException as _exc:
            if not recoverable(_exc):
                raise
            self.errors.append("play context: " + traceback.format_exc(limit=2))
            return None

    def _search_view(self, req: dict, searched: dict) -> dict:



        def sheet_name(s: dict) -> str:
            return s.get("name") or s["species"]

        def spaced(mv: str) -> str:
            return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", mv)

        mine = [p["ident"].split(": ", 1)[1] for p in req["side"]["pokemon"][:2]]
        foe_side = self.tracker.foe
        shown = self.tracker.shown[foe_side]
        foe = [sheet_name(self.tracker.mons[foe_side][i].sheet) if i is not None else "" for i in shown]
        bring = [sheet_name(self.my_sheet[i]) for i in self.bring]
        foe_bring = [sheet_name(self.foe_sheet[i]) for i in searched.get("foe_bring") or []]
        active = req.get("active") or []
        my_moves = [[mv["move"] for mv in active[s]["moves"]] if s < len(active) else [] for s in (0, 1)]
        world = searched.get("world")
        foe_moves = [[spaced(mv) for mv in (world[i]["moves"] if world and i < len(world) else
                                            self.tracker.mons[foe_side][i].sheet.get("moves", []))] if i is not None else [] for i in shown]
        q, chosen = searched.get("q") or [], searched.get("chosen")
        cands = [[[describe_action(a, my_moves[s], foe, mine[1 - s], bring, bool(m)) for s, (a, m) in enumerate(c)],
                  q[n] if n < len(q) else None, n == chosen] for n, c in enumerate(searched["cands"])]
        replies = [[[describe_action(a, foe_moves[s], mine, foe[1 - s], foe_bring, bool(m)) if foe[s] else "-"
                     for s, (a, m) in enumerate(r)], w] for r, w in searched.get("replies") or []]
        return {"candidates": cands, "replies": replies}

    def _why(self, req: dict, ex: dict, played: list | None = None) -> dict:


        def sheet_name(s: dict) -> str:
            return s.get("name") or s["species"]

        mine = [p["ident"].split(": ", 1)[1] for p in req["side"]["pokemon"][:2]]
        foe_side = self.tracker.foe
        foe = [sheet_name(self.tracker.mons[foe_side][i].sheet) if i is not None else "" for i in self.tracker.shown[foe_side]]
        bring = [sheet_name(self.my_sheet[i]) for i in self.bring]
        active = req.get("active") or []
        out = {"value": ex["value"], "win": ex["win"], "mode": ex.get("mode"), "slots": [], "foe_guess": None}
        for slot, e in enumerate(ex["slots"]):
            if e is None:
                out["slots"].append(None)
                continue
            moves = [mv["move"] for mv in active[slot]["moves"]] if slot < len(active) else []

            def label(a: int) -> str:
                return describe_action(a, moves, foe, mine[1 - slot], bring)

            sent = played[slot][0] if played else e["chosen"]
            row = {"mon": mine[slot], "chosen": label(sent), "policy": label(e["chosen"]), "p": e["p"],
                   "options": [[label(a), p] for a, p in e["top"]]}
            if "mega_p" in e:
                row["mega_p"] = e["mega_p"]
            out["slots"].append(row)
        if ex.get("foe"):
            out["foe_guess"] = []
            for slot, top in enumerate(ex["foe"]):
                if not foe[slot]:
                    out["foe_guess"].append(None)
                    continue

                fm = self.tracker.mons[foe_side][self.tracker.shown[foe_side][slot]]
                if self.tracker.open_sheets:
                    moves = [re.sub(r"(?<=[a-z])(?=[A-Z])", " ", mv) for mv in fm.sheet.get("moves", [])]
                else:
                    moves = []
                out["foe_guess"].append({"mon": foe[slot], "options": [[describe_action(a, moves, mine, foe[1 - slot], []), p] for a, p in top]})
        if not self.tracker.open_sheets:
            out["foe_sets"] = self._foe_sets()
        return out

    def _evidence(self, raw: list[str] | None = None):


        from . import belief
        if self.fmt not in _BELIEF_PRIORS:
            _BELIEF_PRIORS[self.fmt] = belief.SetPrior.load(self.fmt)
        ev = belief.Evidence(self.fmt)
        me = self.tracker.me
        ev.know(me, [x.get("item") or "" for x in self.my_sheet], [x.get("ability") or "" for x in self.my_sheet],
                [(m.stats[5] if m.stats else 0) for m in self.tracker.mons[me]])
        for line in (self.raw if raw is None else raw):
            if line.startswith("|"):
                ev.feed(line)

        carried = self.client.series_facts.get(self.foe_name) if self.in_series and self.foe_name else None
        if carried:
            for f in ev.mons[self.tracker.foe]:
                if f.species in carried:
                    f.absorb(carried[f.species])
        return ev, _BELIEF_PRIORS[self.fmt]

    def _remember_sets(self) -> None:


        if self.fmt is None or self.tracker is None or not self.foe_name:
            return
        ev, _ = self._evidence()
        store = self.client.series_facts.setdefault(self.foe_name, {})
        for f in ev.mons[self.tracker.foe]:
            store[f.species] = f.carried()
        log.warning("%s: series memory for %s: %s", self.room, self.foe_name,
                    "; ".join(f"{sp} {'/'.join(f.moves) or '-'}{' @' + f.item if f.item else ''}{' [' + f.ability + ']' if f.ability else ''}"
                              for sp, f in store.items()))

    def _foe_world(self, raw: list[str] | None = None) -> list[dict]:

        from . import belief
        ev, prior = self._evidence(raw)
        mons = ev.mons[self.tracker.foe]
        if len(mons) != len(self.foe_sheet):
            raise ValueError(f"the log's preview has {len(mons)} opposing mons, the sheet {len(self.foe_sheet)}")
        return [belief.world_set(prior, f, self.fmt) for f in mons]

    def _foe_sets(self) -> list | None:


        try:
            from . import belief
            ev, prior = self._evidence()
            foe = self.tracker.foe
            return [belief.describe(prior, ev.mons[foe][ev.active[foe + s]]) if foe + s in ev.active else None for s in "ab"]
        except Exception as e:
            return [f"(no set guess: {type(e).__name__}: {e})"]


_BELIEF_PRIORS: dict = {}


CB_DEADLINE = 25.0


class BaseClient:






    def __init__(self, url: str, username: str, agent: Agent, team: list[dict], fmt: str = "gen9championsvgc2026regmc",
                 formats: list[str] | None = None):
        self.url, self.username, self.agent, self.team, self.format = url, username, agent, team, fmt
        self.formats = set(formats or [fmt])
        self.random_agent = Agent("random", seed=random.randrange(1 << 30))
        self.live_search = None


        self.format_models: dict[str, tuple[Agent, object]] = {}

        self.closed_sheet_search = False


        self.force_bring: list[int] | None = None


        self.g1_bring: list[int] | None = None
        self.stop_after_turn: int | None = None
        self.force_turns: dict[int, list[dict]] | None = None
        self.search_lock = threading.Lock()
        self.request_timer = True


        self.join_rooms: list[str] = []
        self.ws = None
        self.on_login = None
        self.random_formats: set[str] = set()
        self.listed_games: list[str] = []
        self.handed: list[list[dict]] = []
        self.search_deadline: float | None = SEARCH_DEADLINE
        self.deadline_clock_share: float | None = DEADLINE_CLOCK_SHARE
        self.msg_t = 0.0
        self.battles: dict[str, Battle] = {}
        self.stale: set[str] = set()
        self.started = False
        self.last_popup = ""
        self.logged_in = asyncio.Event()
        self.challstr = ""
        self.relogins: list[float] = []
        self.new_battle: asyncio.Queue[Battle] = asyncio.Queue()
        self.challenges: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self.pms: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self.ots_for: dict[str, bool] = {}
        self.timer_for: dict[str, bool] = {}

        self.bring_for: dict[str, dict] = {}
        self.last_leads: dict[str, tuple] = {}
        self.teams: list[list[dict]] = [team]
        self.bo3_lead_avoid = 0.5
        self.series: dict[str, list[int]] = {}

        self.series_memory: dict[str, dict] = {}


        self.series_facts: dict[str, dict[str, object]] = {}

        self.reply_temps: list[float] = [1.0]
        self.reply_arm: dict[str, float] = {}

        self.search_arms: list[dict] = [{"name": "A"}]


        self.closed_search_arms: list[dict] | None = None
        self.closed_reply_temps: list[float] | None = None
        self.search_arm: dict[str, dict] = {}


        self.cb_arms: list[str] = ["today"]
        self.cb_arm: dict[str, str] = {}


        self.lead_arms: list[str] = ["v2"]


        self.lead_preview = None


        self.pre_game_check = None
        self.forfeit_note = ""
        self.lead_arm: dict[str, str] = {}
        self.series_leads: dict[str, list[dict]] = {}
        self.counter_bring = None
        self.cb_log: str | None = None
        self.prev_foe_bring: dict[str, tuple] = {}

    async def send(self, msg: str) -> None:

        log.debug(">> %s", "|/trn <hidden>" if msg.startswith("|/trn ") else msg)
        try:
            await self.ws.send(msg)
        except websockets.ConnectionClosed:
            if not self.on_send_closed(msg):
                raise

    def on_send_closed(self, msg: str) -> bool:

        return False

    def choice_text(self, choice: str) -> str:

        return choice

    async def connect(self) -> None:

        self.ws = await websockets.connect(self.url, max_size=None, ping_interval=20, ping_timeout=60, user_agent_header=USER_AGENT)
        self.inbox: asyncio.Queue = asyncio.Queue()
        asyncio.get_running_loop().create_task(self._receiver())
        asyncio.get_running_loop().create_task(self._reader())
        await self.logged_in.wait()

    async def _login(self) -> None:

        await self.send(f"|/trn {self.username},0,")

    async def _first_login(self) -> None:

        await self._login()

    def on_signed_in(self) -> None:
        pass

    def on_signed_out(self) -> None:
        pass

    async def _receiver(self) -> None:



        try:
            async for msg in self.ws:
                await self.inbox.put((time.monotonic(), msg))
        except BaseException as _exc:
            self.closed_reason = f"{type(_exc).__name__}: {_exc}"
        finally:
            await self.inbox.put((time.monotonic(), None))

    async def _reader(self) -> None:
        while True:
            self.msg_t, msg = await self.inbox.get()
            if msg is None:
                if await self.on_connection_lost():
                    continue
                return
            room = ""
            lines = msg.split("\n")
            if lines and lines[0].startswith(">"):
                room, lines = lines[0][1:], lines[1:]
            try:
                await self._dispatch(room, lines)
            except BaseException as _exc:
                if not recoverable(_exc):
                    raise
                log.error("dispatch failed: %s", traceback.format_exc())

    async def on_connection_lost(self) -> bool:

        log.info("the server connection is gone (%s)", getattr(self, "closed_reason", "closed by the server"))
        return False

    async def on_server_line(self, parts: list[str]) -> None:
        pass

    async def _dispatch(self, room: str, lines: list[str]) -> None:
        if room.startswith("battle-"):
            if room in self.stale:
                return
            if room not in self.battles:
                self.battles[room] = Battle(self, room)
                await self.new_battle.put(self.battles[room])
            await self.battles[room].on_message(lines)
            return
        for line in lines:
            parts = line.split("|")
            if len(parts) < 2:
                continue
            if parts[1] == "popup":
                self.last_popup = "|".join(parts[2:])
                log.warning("%s popup: %s", self.username, self.last_popup[:300])
            await self.on_server_line(parts)
            if parts[1] == "challstr":
                self.challstr = "|".join(parts[2:])
                await self._first_login()
            elif parts[1] == "updateuser" and to_id(parts[2]) == to_id(self.username):
                if self.relogins and not self.logged_in.is_set():
                    log.warning("%s: signed back in", self.username)
                if not self.logged_in.is_set():
                    for room in self.join_rooms:
                        await self.send(f"|/join {room}")
                    self.on_signed_in()
                    if self.on_login is not None:
                        await self.on_login()
                self.logged_in.set()
            elif parts[1] == "updateuser" and self.logged_in.is_set():



                self.logged_in.clear()
                log.error("%s: signed out (this connection is now %r)", self.username, parts[2].strip())
                self.on_signed_out()
            if parts[1] == "updatesearch":
                self.listed_games = list(json.loads(parts[2]).get("games") or {})
            if parts[1] == "updatesearch" and not self.started:

                for room in (json.loads(parts[2]).get("games") or {}):
                    if room not in self.battles and room not in self.stale:
                        self.stale.add(room)
                        await self.send(f"{room}|/forfeit")
                        await self.send(f"|/leave {room}")
            elif parts[1] == "updatechallenges":
                for user, fmt in json.loads(parts[2]).get("challengesFrom", {}).items():
                    if self.accepts_format(fmt):
                        await self.challenges.put((user, fmt))
            elif parts[1] == "pm" and len(parts) > 4 and parts[4].startswith("/challenge "):

                sender, receiver = parts[2].strip(), parts[3].strip()
                if to_id(receiver) == to_id(self.username) and to_id(sender) != to_id(self.username):
                    fmt = parts[4].split(" ", 1)[1].strip()
                    if self.accepts_format(fmt):
                        await self.challenges.put((sender, fmt))
            elif parts[1] == "pm" and len(parts) > 4 and "|".join(parts[4:]).startswith("."):
                sender, receiver = parts[2].strip(), parts[3].strip()
                if to_id(receiver) == to_id(self.username) and to_id(sender) != to_id(self.username):
                    await self.pms.put((sender.lstrip("+%@*#&~ "), "|".join(parts[4:])))
            elif parts[1] == "pm" and len(parts) > 4 and to_id(parts[2]) != to_id(self.username) and not parts[4].startswith("/"):


                log.warning("%s PM from %s: %r", self.username, parts[2].strip(), "|".join(parts[4:])[:500])

    def accepts_format(self, fmt: str) -> bool:



        base, _, rules = fmt.partition("@@@")
        return base in self.formats and all(to_id(r) == "bestof3" for r in rules.split(",") if rules)

    async def pm(self, user: str, text: str) -> None:


        pieces, cur = [], ""
        for part in text.split(" | "):
            joined = f"{cur} | {part}" if cur else part
            if len(joined) <= 290:
                cur = joined
            else:
                if cur:
                    pieces.append(cur)
                cur = part
        pieces.append(cur)
        for i, piece in enumerate(pieces[:6]):
            if i:
                await asyncio.sleep(0.7)
            await self.send(f"|/pm {to_id(user)}, {piece[:290]}")

    async def challenge(self, opponent: str, timeout: float = 30) -> Battle:

        self.started = True
        self.last_popup = ""
        await self.send(f"|/utm {pack(self.team)}")
        await self.send(f"|/challenge {opponent}, {self.format}")
        try:
            return await asyncio.wait_for(self.new_battle.get(), timeout)
        except asyncio.TimeoutError:
            await self.send(f"|/cancelchallenge {opponent}")
            raise RuntimeError(f"challenge to {opponent} didn't start a battle: {self.last_popup or 'no reply'}")

    async def accept_one(self, timeout: float | None = None) -> Battle:
        user, _ = await asyncio.wait_for(self.challenges.get(), timeout)
        self.started = True
        self.last_popup = ""
        await self.send(f"|/utm {pack(self.team)}")
        await self.send(f"|/accept {user}")
        try:
            return await asyncio.wait_for(self.new_battle.get(), 30)
        except asyncio.TimeoutError:
            raise RuntimeError(f"accepting {user} didn't start a battle: {self.last_popup or 'no reply'}")

    async def leave(self, battle: Battle) -> None:
        self.stale.add(battle.room)
        await self.send(f"|/leave {battle.room}")
        self.battles.pop(battle.room, None)

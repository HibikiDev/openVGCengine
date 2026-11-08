""














from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "suite", ROOT / "trainer"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.core.positions import (_spread_corpus, fill_bring, filled_sets, replay_format, side_bring,
                                      with_spreads)
from vgc_suite.core.replay import ReplayLog, load_replay
import vgc_engine as ve
from vgc_trainer.search import guessed_spreads
from vgc_trainer.showdown.sheets import BUDDY_SUFFIX, base_format
from vgc_trainer.showdown.teams import pack
from vgc_trainer.showdown.tracker import BOOSTS, TERRAINS, Tracker, to_id

TERRAIN_IDS = {v: to_id(k) for k, v in TERRAINS.items()}

SHOWN_VOLATILES = {"substitute": "Substitute", "taunt": "Taunt", "encore": "Encore", "confusion": "confusion", "leechseed": "Leech Seed",
                   "yawn": "Yawn", "perish": "Perish Song", "perishsong": "Perish Song", "disable": "Disable", "torment": "Torment",
                   "healblock": "Heal Block", "saltcure": "Salt Cure", "choicelock": "a Choice lock", "throatchop": "Throat Chop",
                   "destinybond": "Destiny Bond", "focusenergy": "Focus Energy", "charge": "Charge", "attract": "infatuation",
                   "partiallytrapped": "a binding move", "trapped": "a trap", "protosynthesis": "Protosynthesis",
                   "quarkdrive": "Quark Drive", "flashfire": "Flash Fire", "unburden": "Unburden", "stockpile": "Stockpile",
                   "dynamax": "Dynamax"}
CARRIED = ("confusion", "substitute", "taunt", "focusenergy", "yawn", "leechseed", "choicelock")


def public_lines(game: dict) -> list[str]:

    out, skip = [], False
    for ln in game["log"]:
        if skip:
            skip = False
            continue
        if ln.startswith("|split|"):
            skip = True
            continue
        out.append(ln)
    return out


def _sheet(log: ReplayLog, side: str, fmt: str | None) -> tuple[list[dict], bool]:

    sh = log.sheets.get(side)
    guessed = False
    if not sh:
        sh = filled_sets(log, side, fmt)
        if sh is None:
            raise ValueError(f"{side}: the replay shows no team sheet and there is no set data for {log.fmt} to fill one")
        guessed = True
    sh = [dict(s) for s in sh]
    return with_spreads(sh, guessed_spreads([sh], _spread_corpus(fmt))[0]), guessed


def _ident_names(lines: list[str], side: str, sheet: list[dict]) -> dict[str, int]:


    names = [to_id(s.get("name") or s["species"]) for s in sheet]
    species = [to_id(s["species"]) for s in sheet]
    out = {n: i for i, n in enumerate(names)}
    for ln in lines:
        p = ln.split("|")
        if len(p) > 3 and p[1] in ("switch", "drag", "replace") and p[2].startswith(side):
            nick, sp = to_id(p[2].split(": ", 1)[1]), to_id(p[3].split(",")[0])
            if nick not in out:
                k = next((i for i, s in enumerate(species) if sp.startswith(s) or s.startswith(sp)), None)
                if k is not None:
                    out[nick] = k
    return out


def build(log: ReplayLog, turn: int, names: dict[str, str]) -> tuple[dict, list[str]]:

    fmt = replay_format(log)
    base = base_format((log.fmt or "").partition("@@@")[0])
    if not base:
        raise ValueError("the replay names no format (no |tier| line)")
    lines = [ln for ln in log.lines if ln.startswith("|") and not ln.startswith(("|request|", "|showteam|"))]
    at = next((k for k, ln in enumerate(lines) if ln == f"|turn|{turn}"), None)
    if at is None:
        last = max((int(ln.split("|")[2]) for ln in lines if ln.startswith("|turn|")), default=0)
        raise ValueError(f"the replay has no turn {turn} (it ends at turn {last})")
    notes = ["spreads guessed from the format's usage (a replay never shows EVs)", "a new random seed: rolls, crits and speed ties differ",
             "HP to the replay's percentage"]
    sheets, guessed = {}, {}
    for s in ("p1", "p2"):
        sheets[s], guessed[s] = _sheet(log, s, fmt)
        if guessed[s]:
            notes.append(f"{log.players.get(s, s)}'s sets: what the game showed, the rest the likeliest for the format")
    t = Tracker("p1", sheets["p1"], sheets["p2"], fmt)
    t.feed(lines[:at + 1])
    spec = {"format": base + BUDDY_SUFFIX, "ots": all(log.sheets.get(s) for s in ("p1", "p2")), "turn": turn,
            "mons": {}, "sides": {}}
    for s in ("p1", "p2"):
        foe = "p2" if s == "p1" else "p1"
        shown = side_bring(log, s, sheets[s])
        bring, fill = fill_bring(sheets[s], sheets[foe], shown, fmt)
        if fill:
            notes.append(f"{log.players.get(s, s)}'s {', '.join(fill['assumed'])}: never shown, assumed brought")
        mons = t.mons[s]
        actives = sorted((i for i in bring if mons[i].slot is not None and not mons[i].fainted), key=lambda i: mons[i].slot)
        if len(actives) == 1 and mons[actives[0]].slot == 1 and any(not mons[i].fainted for i in bring if i not in actives):
            notes.append(f"{log.players.get(s, s)}: the right slot's mon starts on the left")
        bench = [i for i in bring if i not in actives and not mons[i].fainted]
        fainted = [i for i in bring if mons[i].fainted]
        order = actives + bench + fainted
        idents = _ident_names(lines[:at + 1], s, sheets[s])
        spent = _items_spent(lines[:at + 1], s, idents)
        pp = _pp_used(lines[:at + 1], s, idents)
        fallen = _fallen(lines[:at + 1], s, idents)
        seen = _seen(lines[:at], s, idents)
        out = []
        for i in order:
            m = mons[i]
            hp = 0 if m.fainted else max(1, min(1000, round(m.hp * 1000)))
            e = {"hp": hp}
            if i in seen:
                e["seen"] = True
            if m.status and not m.fainted:
                e["status"] = m.status
                if m.status == "tox":
                    e["toxStage"] = int(m.toxic_stage)
                if m.status == "slp":
                    notes.append(f"{m.sheet.get('name') or m.sheet['species']}'s sleep: turns left drawn afresh")
            b = {k: int(m.boosts[j]) for k, j in BOOSTS.items() if m.boosts[j]}
            if b and m.slot is not None:
                e["boosts"] = b
            if i in spent and sheets[s][i].get("item"):
                e["noItem"] = True
            if m.mega:
                e["mega"] = True
            if m.tera:
                e["tera"] = True
            if pp.get(i):
                e["ppUsed"] = pp[i]
            if m.slot is not None and not m.fainted:


                e["activeTurns"] = int(m.turns_active)
                if m.acted:
                    e["acted"] = True
                if m.last_move:
                    mv = next((x for x in sheets[s][i].get("moves") or [] if ve.lookup("move", x) == m.last_move), None)
                    if mv:
                        e["lastMove"] = to_id(mv)
                if m.times_attacked:
                    e["timesAttacked"] = int(m.times_attacked)
                r = m.result
                if r is not None and m.result_turn == t.turn - 1 and (r["fail"] or r["miss"] or r["still"]) and not r["hit"] and not r["null"]:
                    e["lastFailed"] = True
                if fallen.get(i):
                    e["fallen"] = fallen[i]
            lock = m.vol.get("choicelock")
            if m.slot is not None and lock not in (None, True, False, 0):
                mv = next((x for x in sheets[s][i].get("moves") or [] if ve.lookup("move", x) == lock), None)
                if mv:
                    e["choiceLock"] = to_id(mv)
            if m.slot is not None and m.vol.get("protect") and m.protect_streak:
                e["stall"] = min(6, int(m.protect_streak))
            if m.slot is not None and not m.fainted:
                name = m.sheet.get("name") or m.sheet["species"]
                carried = sorted(v for v in CARRIED if m.vol.get(v) and v != "choicelock")
                if carried:
                    e["vols"] = carried
                    timed = [SHOWN_VOLATILES[v] for v in carried if v in ("confusion", "taunt")]
                    if timed:
                        notes.append(f"{name}'s {', '.join(timed)}: turns left drawn afresh")
                vols = sorted({SHOWN_VOLATILES[v] for v in m.vol if v in SHOWN_VOLATILES and v not in CARRIED and m.vol.get(v)})
                if vols:
                    notes.append(f"{name}: {', '.join(vols)} not carried over")
            out.append(e)
        spec[s] = {"name": names[s], "team": pack(sheets[s]), "order": [i + 1 for i in order]}
        spec["mons"][s] = out
        sd = t.side[s]
        side = {k: int(sd[k]) for k in ("tailwind", "reflect", "lightscreen", "auroraveil", "safeguard") if sd.get(k)}
        side.update({k: int(sd[k]) for k in ("stealthrock", "spikes", "toxicspikes", "stickyweb") if sd.get(k)})
        spec["sides"][s] = side
    f = {}
    if t.weather:
        f["weather"] = to_id(getattr(t, "weather_name", "") or "")
        f["weatherTurns"] = int(t.weather_turns)
    if t.terrain:
        f["terrain"] = TERRAIN_IDS[t.terrain]
        f["terrainTurns"] = int(t.terrain_turns)
    if t.trick_room:
        f["trickRoom"] = int(t.trick_room)
    if t.gravity:
        f["gravity"] = int(t.gravity)
    spec["field"] = f
    spec["ghost"] = _ghost(lines[:at])
    if t.other_fields:
        notes.append(f"not carried over: {', '.join(sorted(t.other_fields))}")
    return spec, notes


def _who(ident: str, side: str, names: dict[str, int]) -> int | None:
    pos, _, name = ident.partition(": ")
    return names.get(to_id(name)) if pos.startswith(side) else None


def _items_spent(lines: list[str], side: str, names: dict[str, int]) -> set[int]:

    gone: set[int] = set()
    for ln in lines:
        p = ln.split("|")
        if len(p) > 2 and p[1] in ("-enditem", "-item"):
            i = _who(p[2], side, names)
            if i is not None:
                (gone.add if p[1] == "-enditem" else gone.discard)(i)
    return gone


GHOST_FIELD = {"electricterrain", "grassyterrain", "mistyterrain", "psychicterrain", "trickroom", "gravity", "magicroom", "wonderroom"}
GHOST_SIDE = {"tailwind", "reflect", "lightscreen", "auroraveil", "safeguard", "stealthrock", "spikes", "toxicspikes", "stickyweb"}
GHOST_WEATHER = {"none", "sunnyday", "raindance", "sandstorm", "snowscape", "snow", "hail", "desolateland", "primordialsea", "deltastream"}


def _ghost(lines: list[str]) -> list[dict]:




    out: list[dict] = []
    for ln in lines:
        p = ln.split("|")
        if len(p) < 2:
            continue
        k = p[1]
        if k == "turn" and len(p) > 2 and p[2].isdigit() and int(p[2]) > 1:
            out.append({"k": "turn", "n": int(p[2])})
        elif k == "upkeep":
            out.append({"k": "upkeep"})
        elif k == "-weather" and len(p) > 2 and to_id(p[2]) in GHOST_WEATHER:
            out.append({"k": "weather", "name": p[2], "upkeep": "[upkeep]" in p[3:]})
        elif k in ("-fieldstart", "-fieldend") and len(p) > 2 and to_id(p[2].removeprefix("move: ")) in GHOST_FIELD:
            out.append({"k": k[1:], "name": p[2]})
        elif k in ("-sidestart", "-sideend") and len(p) > 3 and p[2][:2] in ("p1", "p2") and to_id(p[3].removeprefix("move: ")) in GHOST_SIDE:
            out.append({"k": k[1:], "side": p[2][:2], "name": p[3]})
    return out


def _seen(lines: list[str], side: str, names: dict[str, int]) -> set[int]:

    out: set[int] = set()
    for ln in lines:
        p = ln.split("|")
        if len(p) > 3 and p[1] in ("switch", "drag", "replace"):
            i = _who(p[2], side, names)
            if i is not None:
                out.add(i)
    return out


def _fallen(lines: list[str], side: str, names: dict[str, int]) -> dict[int, int]:

    out: dict[int, int] = {}
    for ln in lines:
        p = ln.split("|")
        if len(p) > 3 and p[1] in ("switch", "drag", "replace"):
            i = _who(p[2], side, names)
            if i is not None:
                out.pop(i, None)
        elif len(p) > 3 and p[1] == "-start" and p[3].startswith("fallen") and p[3][6:].isdigit():
            i = _who(p[2], side, names)
            if i is not None:
                out[i] = int(p[3][6:])
    return out


def _pp_used(lines: list[str], side: str, names: dict[str, int]) -> dict[int, dict[str, int]]:


    out: dict[int, dict[str, int]] = {}
    for ln in lines:
        p = ln.split("|")
        if len(p) > 3 and p[1] == "move" and not any(x.startswith("[from]") for x in p[4:]):
            i = _who(p[2], side, names)
            if i is not None:
                mid = to_id(p[3])
                out.setdefault(i, {})[mid] = out.get(i, {}).get(mid, 0) + 1
    return out


def load(src: str) -> ReplayLog:

    if src.endswith(".log.json") and Path(src).exists():
        return load_replay("\n".join(public_lines(json.loads(Path(src).read_text(encoding="utf8")))))
    return load_replay(src)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("replay")
    ap.add_argument("--turn", type=int, required=True)
    ap.add_argument("--p1", default="Player 1")
    ap.add_argument("--p2", default="Player 2")
    ap.add_argument("--out")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    spec, notes = build(load(args.replay), args.turn, {"p1": args.p1, "p2": args.p2})
    text = json.dumps(spec)
    if args.out:
        Path(args.out).write_text(text, encoding="utf8")
    else:
        print(text)
    for n in notes:
        print("approximate: " + n, file=sys.stderr)


if __name__ == "__main__":
    main()

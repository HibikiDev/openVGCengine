



from __future__ import annotations

import json
from ..winproc import NO_WINDOW
import logging
import random
import re

import vgc_engine as ve

from .chaos import HIGH_CHAOS
from .requests import REQUEST_TARGET
from .tracker import to_id

log = logging.getLogger("showdown")

_MOVE_DEX = None
KEEP_WINNING_LEAD = 0.9


def lead_rule_v3(history: list[dict], u: float) -> dict:



    excluded = [g["lead"] for g in history if not g["won"] and g.get("chaos", 0.0) < HIGH_CHAOS]
    out = {frozenset(x) for x in excluded}
    last = history[-1]
    if last["won"] and frozenset(last["lead"]) not in out and u < KEEP_WINNING_LEAD:
        return {"force_lead": list(last["lead"])}
    return {"avoid_leads": excluded} if excluded else {}




STATUS_COLUMN = 4 + 19 + 2



FALLBACK_ABILITY = "Run Away"



COSMETIC_FORMES = {**{f"Florges-{c}": "Florges" for c in ("Blue", "Orange", "White", "Yellow")},
                   **{f"Furfrou-{t}": "Furfrou" for t in ("Dandy", "Debutante", "Diamond", "Heart", "Kabuki", "La Reine", "Matron", "Pharaoh",
                                                          "Star")},
                   "Alcremie-Salted-Cream": "Alcremie"}



CLOSED_SHEET_FORMATS = {"gen5vgc2013", "gen6vgc2014", "gen6vgc2015", "gen6vgc2016", "gen7vgc2017", "gen7vgc2018", "gen7vgc2019",
                        "gen8vgc2020", "gen8vgc2021", "gen8vgc2022"}


SV_FORMATS = {"gen9vgc2023regc", "gen9vgc2023regd", "gen9vgc2024regg", "gen9vgc2025regi"}





BUDDY_SUFFIX = "buddy"


def base_format(fmt: str) -> str:

    return fmt[: -len(BUDDY_SUFFIX)] if fmt.endswith(BUDDY_SUFFIX) else fmt


def buddy_format(fmt: str) -> str:

    return fmt if fmt.endswith(BUDDY_SUFFIX) else fmt + BUDDY_SUFFIX


def playable_sheet(sheet: list[dict], room: str = "", fmt: str | None = None) -> list[dict]:



    out = [dict(s) for s in sheet]
    if len(out) != ve.ROSTER_SIZE:
        return out
    for _ in range(2 * len(out)):
        try:
            ve.BattlePool(1).register_team(out) if fmt is None else ve.BattlePool(1).register_team(out, fmt)
            return out
        except ValueError as e:
            sp = re.match(r'unknown species "(.+)"', str(e))
            if sp:
                base = COSMETIC_FORMES.get(sp.group(1))
                hit = next((i for i, s in enumerate(out) if s.get("species") == sp.group(1)), None)
                if base is None or hit is None:
                    return out
                for s in out:
                    if s.get("species") == sp.group(1):
                        s["species"] = base
                        if s.get("name") == sp.group(1):
                            s["name"] = base
                log.info("%s: the opponent's %s is played as %s (a cosmetic forme)", room, sp.group(1), base)
                continue
            mv = re.match(r'unknown move "(.+)"', str(e)) or re.match(r"set \d+: move (.+) isn't implemented", str(e))
            if mv:

                key = re.sub(r"[^a-z0-9]", "", mv.group(1).lower())
                hit = next(((i, x) for i, s in enumerate(out) for x in s.get("moves", []) if re.sub(r"[^a-z0-9]", "", x.lower()) == key), None)
                if hit is None:
                    return out
                i, name = hit
                out[i]["moves"] = [x for x in out[i]["moves"] if x != name]
                log.warning("%s: the opponent's %s: move %s isn't implemented, so it is played without it", room, out[i].get("species"), name)
                continue
            m = re.match(r"set (\d+): (its Mega forme's )?(ability|item) (.+) isn't implemented", str(e))
            if not m:
                return out
            i = int(m.group(1))
            if m.group(3) == "ability" and not m.group(2):
                out[i]["ability"], instead = FALLBACK_ABILITY, f"ability {FALLBACK_ABILITY}"
            else:
                out[i]["item"], instead = "", "no item"
            log.warning("%s: the opponent's %s: %s, so it is played with %s", room, out[i].get("species"), str(e).split(": ", 1)[1],
                        instead)
    return out


_BASE_STATS: dict[str, dict] = {}
_NATURE_MODS = {"Lonely": ("atk", "def"), "Adamant": ("atk", "spa"), "Naughty": ("atk", "spd"), "Brave": ("atk", "spe"),
                "Bold": ("def", "atk"), "Impish": ("def", "spa"), "Lax": ("def", "spd"), "Relaxed": ("def", "spe"),
                "Modest": ("spa", "atk"), "Mild": ("spa", "def"), "Rash": ("spa", "spd"), "Quiet": ("spa", "spe"),
                "Calm": ("spd", "atk"), "Gentle": ("spd", "def"), "Careful": ("spd", "spa"), "Sassy": ("spd", "spe"),
                "Timid": ("spe", "atk"), "Hasty": ("spe", "def"), "Jolly": ("spe", "spa"), "Naive": ("spe", "spd")}


def _base_stats(species: str) -> dict:

    if not _BASE_STATS:
        import subprocess
        from pathlib import Path
        js = ("const {Dex}=require('./tools/showdown-oracle/lib/showdown');const D=Dex.mod('champions');const s={};"
              "for(const x of D.species.all())s[x.id]=x.baseStats;console.log(JSON.stringify(s))")
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf8", check=True,
                           cwd=Path(__file__).resolve().parents[3], **NO_WINDOW)
        _BASE_STATS.update(json.loads(r.stdout))
    return _BASE_STATS[to_id(species)]


def _champions_stat(base: int, stat: str, pts: int, nature: str) -> int:

    if stat == "hp":
        return base + pts + 75
    v = base + pts + 20
    plus, minus = _NATURE_MODS.get(nature, (None, None))
    return v * 110 // 100 if plus == stat else v * 90 // 100 if minus == stat else v


def stat_points(species: str, stats: dict, nature: str | None) -> tuple[str, dict]:


    base = _base_stats(species)
    best = None
    for nat in ([nature] if nature else ["Serious", *_NATURE_MODS]):
        pts, miss = {}, 0
        for k in ("hp", "atk", "def", "spa", "spd", "spe"):
            fits = [x for x in range(33) if _champions_stat(base[k], k, x, nat) == stats[k]]
            pts[k] = fits[0] if fits else min(range(33), key=lambda x: abs(_champions_stat(base[k], k, x, nat) - stats[k]))
            miss += not fits
        if best is None or miss < best[2]:
            best = (nat, pts, miss)
        if not miss:
            break
    if best[2]:
        log.warning("%s: %d stat(s) of %s fit no stat points (nature %s): the nearest kept", species, best[2], stats, best[0])
    return best[0], best[1]


def handed_sheet(pokemon: list[dict], shown: list[dict] | None) -> list[dict]:



    sheet = []
    for i, p in enumerate(pokemon):
        species = p["details"].split(",")[0]
        lvl = next((int(x.strip()[1:]) for x in p["details"].split(",")[1:] if x.strip()[:1] == "L" and x.strip()[1:].isdigit()), 50)
        mine = [s for s in (shown or []) if to_id(s["species"]) == to_id(species)]
        s = dict(mine[0]) if mine else {"name": species, "species": species, "item": p.get("item") or "",
                                        "ability": p.get("baseAbility") or p.get("ability") or "", "moves": list(p.get("moves", [])), "nature": ""}
        stats = dict(p["stats"], hp=int(p["condition"].split()[0].split("/")[1]))
        s["nature"], s["evs"] = stat_points(species, stats, s.get("nature") or None)
        s["level"] = lvl
        if p.get("teraType"):
            s.setdefault("teraType", p["teraType"])
        sheet.append(s)
    return sheet


def _move_dex():

    global _MOVE_DEX
    if _MOVE_DEX is None:
        _MOVE_DEX = ve.dex_tables()[0]
    return _MOVE_DEX


def sheet_signature(s: dict) -> tuple:

    return (to_id(s["species"]), to_id(s.get("item") or ""), tuple(sorted(to_id(m) for m in s["moves"])))


def request_signature(p: dict) -> tuple:

    return (to_id(p["details"].split(",")[0]), to_id(p.get("item") or ""), tuple(sorted(to_id(m) for m in p.get("moves", []))))


def forced_choice(req: dict, slots: list[dict], sheet: list[dict]) -> str | None:




    party = req["side"]["pokemon"]

    def name_of(p: dict) -> str:
        return to_id(p["ident"].split(": ", 1)[1])

    out = []
    for i, sl in enumerate(slots[:2]):
        if sl.get("mon") and (i >= len(party) or not party[i].get("active") or name_of(party[i]) != to_id(sl["mon"])):
            return None
        if "switch" in sl:
            want = to_id(sheet[int(sl["switch"])].get("name") or sheet[int(sl["switch"])]["species"])
            k = next((k for k, p in enumerate(party) if name_of(p) == want and not p.get("active") and not p["condition"].endswith(" fnt")), None)
            if k is None:
                return None
            out.append(f"switch {k + 1}")
            continue
        act = (req.get("active") or [{}, {}])[i]
        moves = act.get("moves") or []
        j = next((k for k, mv in enumerate(moves) if (to_id(mv.get("move", "")) == to_id(sl["move"]) or mv.get("id") == to_id(sl["move"]))
                  and not mv.get("disabled")), None)
        if j is None:
            return None
        part = f"move {j + 1}"
        if moves[j].get("target") in REQUEST_TARGET:
            part += {"foe1": " 1", "foe2": " 2", "ally": f" -{2 - i}"}.get(sl.get("target") or "foe1", " 1")
        if sl.get("mega") and act.get("canMegaEvo"):
            part += " mega"
        out.append(part)
    return ", ".join(out)










from __future__ import annotations

import random

import vgc_engine as ve

from .tracker import ILLUSION, NEUTRALIZING_GAS, STATUSES, TRACE, UNKNOWN_ITEM, Tracker

TATSUGIRI_DROOPY, TATSUGIRI_STRETCHY = ve.lookup("species", "Tatsugiri-Droopy"), ve.lookup("species", "Tatsugiri-Stretchy")
TERAPAGOS = ve.lookup("species", "Terapagos")
TERA_FORME_BASE = {ve.lookup("species", t): ve.lookup("species", b) for t, b in (
    ("Ogerpon-Teal-Tera", "Ogerpon"), ("Ogerpon-Wellspring-Tera", "Ogerpon-Wellspring"), ("Ogerpon-Hearthflame-Tera", "Ogerpon-Hearthflame"),
    ("Ogerpon-Cornerstone-Tera", "Ogerpon-Cornerstone"), ("Terapagos-Stellar", "Terapagos"))}

NO_MON = 0xFF



STRONG_WEATHER_IDS = {"DesolateLand": 6, "PrimordialSea": 7, "DeltaStream": 8}
GEN8 = ("gen8vgc2020", "gen8vgc2021", "gen8vgc2022")
GMAX_CHI_STRIKE_COND = 50
STALL = {None: (3, 729), "gen5vgc2013": (2, 256), "gen6vgc2014": (3, 729), "gen6vgc2015": (3, 729), "gen6vgc2016": (3, 729),
         "gen7vgc2017": (3, 729), "gen7vgc2018": (3, 729), "gen7vgc2019": (3, 729),
         **{f: (3, 729) for f in ("gen9vgc2024regg", "gen9vgc2025regi", "gen9vgc2023regc", "gen9vgc2023regd") + GEN8}}
CHOICE_ITEM_IDS = {ve.lookup("item", x) for x in ("Choice Scarf", "Choice Band", "Choice Specs")}
SHOWN_HP_SCALE = {None: 100, "gen5vgc2013": 48, "gen6vgc2014": 48, "gen6vgc2015": 48, "gen6vgc2016": 48,
                  "gen7vgc2017": 100, "gen7vgc2018": 100, "gen7vgc2019": 100,
                  **{f: 100 for f in ("gen9vgc2024regg", "gen9vgc2025regi", "gen9vgc2023regc", "gen9vgc2023regd") + GEN8}}


SHOWN_HP_ROUNDS_UP = frozenset({"gen7vgc2017", "gen7vgc2018", "gen7vgc2019", "gen9vgc2024regg", "gen9vgc2025regi", "gen9vgc2023regc",
                                "gen9vgc2023regd", *GEN8})
TRAPPER_GONE = 0xFF
GMAX_TRAP, GMAX_TRAP_BAND = 0xF0, 0xF1


class Unsupported(Exception):
    pass



HIDDEN_TURNS = {"confusion": 2, "taunt": 2, "encore": 2, "disable": 3, "healblock": 3, "throatchop": 1, "yawn": 1, "trapped": 3}
SIDE_NUM = {"p1": 0, "p2": 1}


KNOWN_VOLS = {"confusion", "taunt", "encore", "encore_move", "disable", "disable_move", "healblock", "throatchop", "perish", "yawn",
              "trapped", "trapped_by", "choicelock", "charging", "charge_move", "recharge", "imprison", "gastroacid", "item_consumed",
              "torment", "abilityflashfire", "stats_raised", "stats_lowered", "substitute", "stockpile", "protect", "roost",
              "leechseed", "magnetrise", "typechange", "transform", "raw", "attract", "lockedmove",
              "charge_pressure",
              "powertrick", "split",
              "ngas", "ngas_ended", "commanding",
              "tera_logged",
              "dynamax", "dynamax_base_hp", "chistrike", "gmax_trap", "unnerved"}


PARADOX_COND, PARADOX_STATS = 42, {"atk": 0, "def": 1, "spa": 2, "spd": 3, "spe": 4}
SHELLTRAP_COND = 46

SEMI_INVULNERABLE = {"fly", "dig", "dive", "bounce", "phantomforce", "shadowforce"}

VOL_FLAGS = (("glaiverush", "glaiverush"), ("minimize", "minimized"), ("charge", "charge"), ("protean", "protean"),
             ("focusenergy", "focusenergy"), ("dragoncheer", "dragoncheer"), ("dragoncheer_dragon", "dragoncheer_dragon"),
             ("smackdown", "smacked_down"), ("aquaring", "aqua_ring"), ("ingrain", "ingrain"), ("saltcure", "salt_cure"),
             ("curse", "cursed"), ("destinybond", "destiny_bond"), ("noretreat", "no_retreat"))


def _status_counter(m, rng: random.Random | None) -> int:


    if m.status == "tox":
        return m.toxic_stage
    if m.status == "frz" or (m.status == "slp" and m.rest_sleep):
        return max(1, 3 - m.status_tries)
    if m.status == "slp":
        start = 3 if m.status_tries >= 2 or rng is None or rng.random() >= 1 / 3 else 2
        return max(1, start - m.status_tries)
    return 0


def _mon(m, first_turn: bool, gravity: bool, trapper_slot: int | None, charge_target: int | None, turn: int,
         rng: random.Random | None, attract_code: int = 0) -> dict:


    v = m.vol
    gastro = "gastroacid" in v
    flags = []
    if v.get("charging"):
        flags.append("charging")
    if v.get("recharge"):
        flags.append("mustrecharge")
    if v.get("choicelock"):
        flags.append("choice_locked")
    if v.get("imprison"):
        flags.append("imprison")
    if gastro:
        flags.append("gastro_acid")
    if v.get("item_consumed"):
        flags.append("item_consumed")
    if v.get("torment"):
        flags.append("torment")
    if v.get("abilityflashfire"):
        flags.append("flashfire")
    for key, flag in VOL_FLAGS:
        if v.get(key):
            flags.append(flag)
    if gravity and m.slot is not None:
        flags.append("gravity")
    if v.get("charging") and v.get("charge_move") in SEMI_INVULNERABLE:
        flags.append("invulnerable")
    if m.syrup:
        flags.append("syrup_triggered")
    if m.bond:
        flags.append("bond_triggered")
    if v.get("unnerved") and not m.fainted and m.slot is not None:
        flags.append("unnerved")

    if v.get("commanding") and not m.fainted:
        flags.append("commanding")
    ngas = "ngas" in v
    if ngas:
        flags.append("ngas_suppressed")
    if (m.ability == NEUTRALIZING_GAS and m.slot is not None and not m.fainted and "transform" not in v
            and "ngas_ended" not in v):
        flags.append("ngas_live")

    if m.ability == TRACE and m.slot is not None and not m.fainted and not ngas and not v.get("trace_blocked"):
        flags.append("trace_seek")
    if first_turn:
        flags += [f for f in ("stats_raised", "stats_lowered") if v.get(f)]
    d = {
        **({"gender": m.gender} if m.gender is not None else {}),
        "species": m.species,
        "mega": bool(m.mega),

        "types": [int(x) for x in (m.types if m.brought else m.live_types())] + [0],
        "ability": 0 if gastro else m.ability,
        "base_ability": m.base_ability,
        "suppressed_ability": v["gastroacid"] if gastro else v["ngas"] if ngas else 0,
        "item": m.item,
        "moves": list(m.moves),
        "pp": list(m.pp),

        "hp_frac": 0.0 if m.fainted else (1.0 if m.hp >= 1.0 else (round(m.hp * SHOWN_HP_SCALE[m.fmt]) + (-0.5 if m.fmt in SHOWN_HP_ROUNDS_UP else 0.5))
                                                                     / SHOWN_HP_SCALE[m.fmt]),
        "fainted": bool(m.fainted),
        "revealed": bool(m.revealed),
        "status": STATUSES.get(m.status, 0),
        "status_counter": _status_counter(m, rng),
        "boosts": list(m.boosts),
        "turns_active": m.turns_active,
        "move_actions": 1 if m.acted else 0,
        "protect_counter": (min(STALL[m.fmt][1], STALL[m.fmt][0] ** m.protect_streak)
                            if v.get("protect") and m.protect_streak else 0),
        "times_attacked": min(255, m.times_attacked),
        "move_result": _move_result(m, turn),
        "leech_seeder": int(v.get("leechseed") or 0),
        "magnet_rise": max(1, 5 - (turn - v["magnetrise"])) if "magnetrise" in v else 0,
        "confusion": HIDDEN_TURNS["confusion"] if v.get("confusion") else 0,
        "taunt": HIDDEN_TURNS["taunt"] if v.get("taunt") else 0,
        "encore": HIDDEN_TURNS["encore"] if v.get("encore") else 0,
        "encore_move": v.get("encore_move", 0) if v.get("encore") else 0,
        "disable": HIDDEN_TURNS["disable"] if v.get("disable") else 0,
        "disable_move": v.get("disable_move", 0) if v.get("disable") else 0,
        "heal_block": HIDDEN_TURNS["healblock"] if v.get("healblock") else 0,
        "throat_chop": HIDDEN_TURNS["throatchop"] if v.get("throatchop") else 0,
        "perish": int(v.get("perish", 0)),
        "yawn": HIDDEN_TURNS["yawn"] if v.get("yawn") else 0,
        "trap_turns": HIDDEN_TURNS["trapped"] if v.get("trapped") else 0,



        "trapped_by": (GMAX_TRAP_BAND if v["gmax_trap"] == "band" else GMAX_TRAP) if v.get("trapped") and v.get("gmax_trap")
        else (trapper_slot + 1 if trapper_slot is not None else TRAPPER_GONE) if v.get("trapped") else 0,
        "charge_target": charge_target or 0,
        "choice_move": int(v["choicelock"]) if v.get("choicelock") else 0,


        "lock_move": v["lockedmove"][0] if v.get("lockedmove") else 0,
        "lock_turns": 1 if v.get("lockedmove") else 0,
        "lock_true": (v["lockedmove"][1] or (2 if rng is not None and rng.random() < 0.5 else 1)) if v.get("lockedmove") else 0,
        "last_move": m.last_move,
        "last_move_z": bool(getattr(m, "last_move_z", False)),


        "last_move_target": charge_target if charge_target is not None and not v.get("encore") else m.last_move_target,
        "stockpile": int(v.get("stockpile", 0)),

        "sub_hp": (m.stats[0] if m.stats else ve.set_stats(m.sheet, m.species, m.fmt)[0]) // 4 if v.get("substitute") else 0,
        "flags": flags,
    }
    if v.get("charging") and v.get("charge_move"):
        d["charge_move"] = ve.lookup("move", v["charge_move"])
    conds = []
    if attract_code:
        conds.append((3, attract_code))
    if d["protect_counter"]:

        conds.append((29, 1))
    if m.metronome is not None:

        mid, count = m.metronome
        conds += [(22, mid & 0xFF), (23, (mid >> 8) & 3 | count << 2)]
    para = next((k for k in m.vol if k.startswith(("protosynthesis", "quarkdrive")) and k[-3:] in PARADOX_STATS), None)
    if para is not None:

        booster = (m.sheet or {}).get("item") == "Booster Energy" and not m.item
        conds.append((PARADOX_COND, PARADOX_STATS[para[-3:]] | int(booster) << 3))
    if v.get("shelltrap"):
        conds.append((SHELLTRAP_COND, v["shelltrap"]))
    if v.get("chistrike"):
        conds.append((GMAX_CHI_STRIKE_COND, int(v["chistrike"])))
    if conds:
        d["conds"] = conds
    if m.stats:
        d["hp"] = 0 if m.fainted else round(m.hp * m.stats[0])
        del d["hp_frac"]
    if "transform" in v:
        d["transform"] = d.pop("species")
        d.pop("mega")
        own = v["transform"]
        d["base_moves"], d["base_pp"] = [int(x) for x in own[1]], [int(x) for x in own[2]]
        d["transform_known"] = sum(1 << k for k, x in enumerate(m.moves) if x)
    if "raw" in v:
        d["raw_stats"] = [int(x) for x in v["raw"]]
        if v.get("powertrick") is not None:
            d["stats_split"] = bool(v.get("split")) and "transform" not in v
    if v.get("powertrick"):
        d["power_trick"] = True
    if m.fmt in GEN8:


        d["gigantamax"] = bool(m.gmax)
        d["dynamax_level"] = int((m.sheet or {}).get("dynamaxLevel", 10))
        if "dynamax" in v and not m.fainted:
            d["dynamaxed"] = True
            d["dynamax_turns"] = int(v["dynamax"])
        elif m.fainted and m.dynamax_fainted:
            d["dynamax_max_hp"] = True
        d["last_move_max"] = bool(m.last_move_max)
    if m.tera_type:
        d["tera_type"] = int(m.tera_type)
        d["tera"] = bool(m.tera)
        d["stellar_boosted"] = int(m.stellar_spent) >> 1

        base = TERA_FORME_BASE.get(m.species)
        if base is not None and m.tera:
            d["forme_base"] = [base, ve.species_ability(base) if base == TERAPAGOS else ve.lookup("ability", (m.sheet or {}).get("ability", ""))]


    if m.slot is not None and getattr(ve, "MON_FEATURES", 0) > 50:
        flags.append("booster_started")
    return d


def _mine_closed(d: dict, m) -> dict:


    d["moves_revealed"] = sum(1 << k for k, x in enumerate(m.moves) if x and x in m.used)
    return d


def _closed(d: dict, m, set_: dict | None) -> dict:

    if m.item == UNKNOWN_ITEM:
        d.pop("item")

        if set_ is not None and set_.get("item") in CHOICE_ITEM_IDS and m.moved and m.last_move and not d["choice_move"]:
            d["choice_move"] = int(m.last_move)
            d["flags"] = d["flags"] + ["choice_locked"]
    if set_ is not None:
        if not m.base_ability:
            d["base_ability"] = int(set_["ability"])
        if not m.ability and not d.get("suppressed_ability"):
            d["ability"] = int(set_["ability"])
    if "transform" in d:
        if set_ is not None:
            pp = {mid: p for mid, p in zip(m.vol["transform"][1], m.vol["transform"][2]) if mid}
            d["base_moves"] = [int(x) for x in set_["moves"]]
            d["base_pp"] = [int(pp[x]) if x in pp else int(ve.max_pp(x, m.fmt)) if x else 0 for x in set_["moves"]]
        return d
    if set_ is None:
        d.pop("moves")
        d.pop("pp")
        return d
    pp = {mid: p for mid, p in zip(m.moves, m.pp) if mid}
    d["moves"] = [int(x) for x in set_["moves"]]
    d["pp"] = [int(pp[x]) if x in pp else int(ve.max_pp(x, m.fmt)) if x else 0 for x in set_["moves"]]
    d["moves_revealed"] = sum(1 << k for k, x in enumerate(set_["moves"]) if x and x in pp)
    return d


def _move_result(m, turn: int) -> int:


    if m.result is None or m.result_turn != turn - 1:
        return 0
    r = m.result
    return 2 if (r["fail"] or r["miss"] or r["still"]) and not r["hit"] and not r["null"] else 1


def unsupported(t: Tracker) -> str | None:

    if t.magic_room or t.other_fields:
        return f"field: {'Magic Room' if t.magic_room else sorted(t.other_fields)[0]}"
    if t.turn - t.fairy_lock_turn <= 1:
        return "Fairy Lock"
    if t.illusion_seen:
        return "Illusion"
    for side in (t.me, t.foe):
        for m in t.mons[side]:
            if m.ability == ILLUSION or (m.sheet.get("ability") or "") == "Illusion":
                return "Illusion"
            if side == t.me and not t.open_sheets and "transform" in m.vol:
                return "transformed under closed sheets"
            unknown = {k for k in set(m.vol) - KNOWN_VOLS - {key for key, _ in VOL_FLAGS}
                       if not (k.startswith(("protosynthesis", "quarkdrive")) and k[-3:] in PARADOX_STATS)}
            if unknown:
                return f"volatile: {sorted(unknown)[0]}"
    return None


def party_order(t: Tracker, request: dict, bring: list[int]) -> list[int]:

    order = []
    for p in request["side"]["pokemon"]:
        ident = p["ident"].replace(": ", "a: ", 1) if p["ident"][2] == ":" else p["ident"]
        order.append(bring.index(t._mon(ident, real=False)[1]))
    return order


def snapshot(t: Tracker, teams: dict[str, int], bring: dict[str, list[int]], party_order: list[int] | None = None,
             charge_targets: dict[int, int] | None = None, rng: random.Random | None = None,
             foe_sets: list[dict] | None = None) -> dict:










    why = unsupported(t)
    if why:
        raise Unsupported(why)
    def trapper(m) -> int | None:
        ref = m.vol.get("trapped_by")
        if ref is None or t.mons[ref[0]][ref[1]].slot is None:
            return None
        return SIDE_NUM[ref[0]] * 2 + t.mons[ref[0]][ref[1]].slot

    sides = []
    battle_index = {}
    for side in ("p1", "p2"):
        battle_index[side] = {sheet: k for k, sheet in enumerate(bring[side])}

    def attract_code(m) -> int:
        src = m.vol.get("attract")
        if src is None or src[1] not in battle_index[src[0]]:
            return 0
        return SIDE_NUM[src[0]] * 4 + battle_index[src[0]][src[1]] + 1

    def future(s: dict) -> tuple[list, list, list]:


        turns, source, move = [0, 0], [0, 0], [0, 0]
        for k, f in enumerate(s.get("future", [None, None])):
            if f is None:
                continue
            used, (src_side, src_sheet), mid = f
            left = 3 - (t.turn - used)
            if used >= 254:
                left = 255
            if left > 0 and src_sheet in battle_index[src_side]:
                turns[k], source[k], move[k] = left, SIDE_NUM[src_side] * 4 + battle_index[src_side][src_sheet], mid
        return turns, source, move
    for side in ("p1", "p2"):
        mons = [t.mons[side][sheet] for sheet in bring[side]]
        active = [None, None]
        for k, m in enumerate(mons):
            if m.slot is not None:
                active[m.slot] = k


        for slot in (0, 1):
            if active[slot] is None:
                free = [k for k in range(len(mons)) if k not in active]
                active[slot] = next((k for k in free if mons[k].fainted), free[0])
        if side == t.me and party_order is not None:
            order = list(party_order)
        else:
            order = active + [k for k in range(4) if k not in active]
        s = t.side[side]
        sides.append({
            "active": active,
            "order": order,
            "mega_used": bool(s["mega_used"]),
            "z_used": bool(s.get("z_used", False)),
            "ultra_used": bool(s.get("ultra_used", False)),
            "tera_used": bool(s.get("tera_used", False)),
            "dynamax_used": bool(s.get("dynamax_used", False)),
            "revivals": int(s.get("revivals", 0)),
            "conds": {
                "reflect": s["reflect"], "light_screen": s["lightscreen"], "aurora_veil": s["auroraveil"], "tailwind": s["tailwind"],
                "safeguard": s.get("safeguard", 0), "stealth_rock": bool(s.get("stealthrock")), "spikes": s.get("spikes", 0),
                "toxic_spikes": s.get("toxicspikes", 0), "sticky_web": bool(s.get("stickyweb")),

                "steelsurge": bool(s.get("steelsurge", False)), "gmax_residual": list(s.get("gmax_residual", [0, 0, 0, 0])),
                "hazard_order": list(s.get("hazard_order", [0, 0, 0, 0, 0])),
                "healing_wish": list(s.get("healing_wish_slots", [False, False])),

                "wish_turns": [1 if turn == t.turn - 1 else 0 for turn, _ in s["wish"]],
                "wish_hp": [hp if turn == t.turn - 1 else 0 for turn, hp in s["wish"]],

                "fainted_count": t.fainted_at_turn.get(t.turn, {}).get(side, 0),
                "fainted_last_turn": t.fainted_at_turn.get(t.turn, {}).get(side, 0) > t.fainted_at_turn.get(t.turn - 1, {}).get(side, 0),
                **dict(zip(("future_turns", "future_source", "future_move"), future(s))),
            },
            "mons": [_mine_closed(_mon(m, t.turn == 0, t.gravity > 0, trapper(m), (charge_targets or {}).get(sheet),
                                       t.turn, rng, attract_code(m)), m)
                     if side == t.me and not t.open_sheets else
                     _closed(_mon(m, t.turn == 0, t.gravity > 0, trapper(m), (charge_targets or {}).get(sheet) if side == t.me else None,
                                  t.turn, rng, attract_code(m)), m, foe_sets[sheet] if foe_sets else None)
                     if side == t.foe and not t.open_sheets else
                     _mon(m, t.turn == 0, t.gravity > 0, trapper(m), (charge_targets or {}).get(sheet) if side == t.me else None,
                          t.turn, rng, attract_code(m))
                     for sheet, m in zip(bring[side], mons)],
        })

        for m in mons:
            if m.vol.get("commanding") and m.slot is not None and not m.fainted:
                ally = next((j for j, o in enumerate(mons) if o.slot == 1 - m.slot and not o.fainted), None)
                if ally is not None:
                    forme = {TATSUGIRI_DROOPY: ["commanded_droopy"], TATSUGIRI_STRETCHY: ["commanded_stretchy"]}.get(m.species, [])
                    sides[-1]["mons"][ally]["flags"] = sides[-1]["mons"][ally]["flags"] + ["commanded"] + forme

    def code(ref) -> int:
        if ref is None:
            return NO_MON
        side, sheet = ref
        return SIDE_NUM[side] * 4 + battle_index[side][sheet]

    def weather_source() -> int:
        src = getattr(t, "weather_source", None)
        if src is None or src[1] not in battle_index.get(src[0], {}):
            return 0
        return SIDE_NUM[src[0]] * 4 + battle_index[src[0]][src[1]] + 1

    history = [(kind, code(actor), code(target), subject, outcome) for kind, actor, target, subject, outcome in t.history[-24:]]
    return {
        "teams": [teams["p1"], teams["p2"]],
        "bring": [list(bring["p1"]), list(bring["p2"])],
        "turn": t.turn,



        "field": {"weather": STRONG_WEATHER_IDS.get(getattr(t, "weather_name", ""))
                  or (5 if t.weather == 4 and getattr(t, "weather_name", "") == "Hail" else t.weather),
                  "weather_source": weather_source(),
                  "weather_turns": t.weather_turns, "terrain": t.terrain, "terrain_turns": t.terrain_turns,
                  "trick_room": t.trick_room, "gravity": t.gravity, "last_move": t.battle_last_move,
                  "hazard_seq": getattr(t, "hazard_seq", 0),
                  "last_move_z": bool(getattr(t, "battle_last_move_z", False))},
        "sides": sides,
        "history": history,
    }

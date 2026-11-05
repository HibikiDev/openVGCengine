






from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import vgc_engine as ve


F_WEATHER, F_WEATHER_TURNS, F_TERRAIN, F_TERRAIN_TURNS, F_TR, F_GRAVITY, F_TURN, F_MY_SIDE, F_FOE_SIDE, F_DECISION = 0, 5, 6, 11, 12, 13, 14, 15, 21, 27

F_FORMAT = 30
F_MY_Z_USED, F_FOE_Z_USED = 34, 35


F_FORMAT2 = 36
F_MY_TERA_USED, F_FOE_TERA_USED = 40, 41

F_MY_DYNAMAX_USED, F_FOE_DYNAMAX_USED, F_MY_GMAX_RESIDUAL, F_FOE_GMAX_RESIDUAL = 42, 43, 44, 45

FORMATS = {None: (0, True), "gen9championsvgc2026regmc": (0, True), "gen9championsvgc2026regmcbo3": (0, True), "gen5vgc2013": (1, False),
           "gen6vgc2014": (2, False), "gen6vgc2015": (2, False), "gen6vgc2016": (2, False),
           "gen7vgc2017": (3, False), "gen7vgc2018": (3, False), "gen7vgc2019": (3, False),
           "gen9vgc2024regg": (4, True), "gen9vgc2025regi": (4, True), "gen9vgc2023regc": (5, True), "gen9vgc2023regd": (5, True),
           "gen8vgc2020": (6, False), "gen8vgc2021": (6, False), "gen8vgc2022": (6, False)}
TERA_FORMATS = (4, 5)
DYNAMAX_FORMATS = (6,)
PREVIEW_HIDES_ITEMS = (6,)

GMAX_RESIDUALS = ("gmaxvinelash", "gmaxwildfire", "gmaxcannonade", "gmaxvolcalith")

CANNOT_DYNAMAX = {ve.lookup("species", n) for n in ("Zacian", "Zacian-Crowned", "Zamazenta", "Zamazenta-Crowned", "Eternatus",
                                                    "Eternatus-Eternamax")} - {0}

UNKNOWN_ITEM = -1
STRUGGLE = ve.lookup("move", "Struggle")
ULTRANECROZIUM = ve.lookup("item", "Ultranecrozium Z")
NECROZMA_FUSED = {ve.lookup("species", "Necrozma-Dusk-Mane"), ve.lookup("species", "Necrozma-Dawn-Wings")}
Z_CAPABLE = getattr(ve, "z_capable", None)
(M_IS_MINE, M_IN_BATTLE, M_ACTIVE_A, M_ACTIVE_B, M_FAINTED, M_HP, M_STATUS, M_TOXIC, M_BOOSTS, M_MEGA, M_CAN_MEGA, M_TURNS_ACTIVE,
 M_CONFUSED, M_TAUNTED, M_ENCORED, M_DISABLED, M_SUB, M_PROTECT, M_PERISH, M_YAWN, M_TRAPPED, M_CHARGING, M_RECHARGE, M_CHOICE,
 M_THROAT_CHOP, M_HEAL_BLOCK, M_HOLDS_ITEM, M_STATS, M_PP, M_STOCKPILE) = (
    0, 1, 2, 3, 4, 5, 6, 13, 14, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 45, 49)
M_TERASTALLIZED, M_STELLAR_LEFT, M_COMMANDING = 50, 51, 52
M_DYNAMAX_TURNS, M_GIGANTAMAX, M_CHI_STRIKE = 53, 54, 55
I_TERA_TYPE = 9

TYPE_ORDER = ["Bug", "Dark", "Dragon", "Electric", "Fairy", "Fighting", "Fire", "Flying", "Ghost", "Grass", "Ground", "Ice", "Normal",
              "Poison", "Psychic", "Rock", "Steel", "Stellar", "Water"]


def type_id(name: str | None) -> int:
    return TYPE_ORDER.index(name) + 1 if name in TYPE_ORDER else 0


STELLAR = type_id("Stellar")

REQUIRED_TERA = {sp: type_id(t) for sp, t in ((ve.lookup("species", n), t) for n, t in (
    ("Ogerpon", "Grass"), ("Ogerpon-Teal-Tera", "Grass"), ("Ogerpon-Wellspring", "Water"), ("Ogerpon-Wellspring-Tera", "Water"),
    ("Ogerpon-Hearthflame", "Fire"), ("Ogerpon-Hearthflame-Tera", "Fire"), ("Ogerpon-Cornerstone", "Rock"),
    ("Ogerpon-Cornerstone-Tera", "Rock"), ("Terapagos", "Stellar"), ("Terapagos-Terastal", "Stellar"),
    ("Terapagos-Stellar", "Stellar"))) if sp}
TERAPAGOS_STELLAR = ve.lookup("species", "Terapagos-Stellar")
NEUTRALIZING_GAS = ve.lookup("ability", "Neutralizing Gas")
SHEDINJA = ve.lookup("species", "Shedinja")
TRACE = ve.lookup("ability", "Trace")
REGENERATOR = ve.lookup("ability", "Regenerator")
AS_ONE = {ve.lookup("ability", n) for n in ("asoneglastrier", "asonespectrier")} - {0}
TERA_BLAST = ve.lookup("move", "Tera Blast")
IRON_HEAD = ve.lookup("move", "Iron Head")
SKETCH = ve.lookup("move", "Sketch")


def base_pp(move: int, fmt) -> int:

    mx = ve.max_pp(move, fmt)
    return mx if fmt is None or fmt.startswith("gen9champions") else mx * 5 // 8
CROWNED = {(ve.lookup("species", a), ve.lookup("item", i)): (ve.lookup("species", c), ve.lookup("move", sig)) for a, i, c, sig in (
    ("Zacian", "Rusted Sword", "Zacian-Crowned", "Behemoth Blade"), ("Zamazenta", "Rusted Shield", "Zamazenta-Crowned", "Behemoth Bash"))}

NO_STELLAR_SPEND = {ve.lookup("move", n) for n in (
    "Super Fang", "Nature's Madness", "Ruination", "Guardian of Alola", "Final Gambit", "Night Shade", "Seismic Toss", "Endeavor",
    "Psywave", "Counter", "Mirror Coat", "Metal Burst", "Comeuppance", "Fissure", "Sheer Cold", "Guillotine", "Horn Drill")} - {0}
_MOVE_TYPES = None


def move_type(move: int) -> int:

    global _MOVE_TYPES
    if _MOVE_TYPES is None:
        _MOVE_TYPES = ve.dex_tables()[0][:, 4:4 + len(TYPE_ORDER)].argmax(1) + 1
    return int(_MOVE_TYPES[move]) if 0 < move < len(_MOVE_TYPES) else 0

WEATHERS = {"none": 0, "SunnyDay": 1, "DesolateLand": 1, "RainDance": 2, "PrimordialSea": 2, "Sandstorm": 3, "Snowscape": 4, "Snow": 4, "Hail": 4,
            "DeltaStream": 0}


STRONG_WEATHERS = ("DesolateLand", "PrimordialSea", "DeltaStream")
WEATHER_ROCKS = {1: "heatrock", 2: "damprock", 3: "smoothrock", 4: "icyrock"}
TERRAINS = {"Electric Terrain": 1, "Grassy Terrain": 2, "Misty Terrain": 3, "Psychic Terrain": 4}
STATUSES = {"": 0, "brn": 1, "frz": 2, "par": 3, "psn": 4, "tox": 5, "slp": 6}
BOOSTS = {"atk": 0, "def": 1, "spa": 2, "spd": 3, "spe": 4, "accuracy": 5, "evasion": 6}
STALL_MOVES = {"protect", "detect", "spikyshield", "banefulbunker", "kingsshield", "silktrap", "burningbulwark", "obstruct", "endure",
               "obstruct", "wideguard", "quickguard", "maxguard"}
def _any_move(name: str) -> int:

    try:
        return ve.lookup("zmove", name)
    except ValueError:
        return ve.lookup("move", name)


STALL_IDS = {_any_move(n) for n in STALL_MOVES}
METRONOME_ITEM = ve.lookup("item", "Metronome")
EV_MOVE, EV_SWITCH, EV_FAINT = 1, 2, 3


def to_id(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def details_gender(details: str) -> str:


    tags = {x.strip() for x in details.split(",")[1:]}
    return "M" if "M" in tags else "F" if "F" in tags else ""


@dataclass
class MonState:
    sheet: dict
    species: int = 0
    item: int = 0
    ability: int = 0
    base_ability: int = 0
    pre_forme: int = 0
    moved: bool = False
    revived: bool = False
    before_switch_in: tuple | None = None
    moves: list = field(default_factory=lambda: [0, 0, 0, 0])
    types: tuple = (0, 0)
    fmt: str | None = None
    brought: bool = False
    slot: int | None = None
    fainted: bool = False
    hp: float = 1.0
    status: str = ""
    toxic_stage: int = 0
    boosts: list = field(default_factory=lambda: [0] * 7)
    mega: bool = False
    turns_active: int = 0
    gender: str | None = None
    vol: dict = field(default_factory=dict)
    stats: list | None = None
    pp: list = field(default_factory=lambda: [0, 0, 0, 0])

    revealed: bool = False
    last_move: int = 0


    last_move_target: int = 0
    move_turn: int = -1
    acted: bool = False
    result: dict | None = None
    result_turn: int = -1
    times_attacked: int = 0
    status_tries: int = 0
    rest_sleep: bool = False
    protect_streak: int = 0
    stall_turn: int = -9


    metronome: tuple | None = None
    metronome_prev: tuple | None = None
    metronome_worked: bool = False
    syrup: bool = False
    bond: bool = False
    used: dict = field(default_factory=dict)
    move_names: dict = field(default_factory=dict)
    last_move_z: bool = False
    tera_type: int = 0
    tera: bool = False
    tera_shown: int = 0
    stellar_spent: int = 0
    gmax: bool = False
    last_move_max: bool = False
    dynamax_fainted: bool = False

    def tera_types(self) -> None:

        if self.tera and self.tera_shown and self.tera_shown != STELLAR:
            self.types = (self.tera_shown, 0)

    def live_types(self):


        try:

            return ve.species_types(self.species, self.fmt, self.ability, max(self.item, 0))
        except TypeError:
            return ve.species_types(self.species, self.fmt)

    def untransform(self) -> None:

        if "transform" in self.vol:
            self.species, self.moves, self.pp = self.vol.pop("transform")
            self.types = self.live_types()
            self.vol.pop("raw", None)
            if self.stats:
                self.stats = [self.stats[0]] + list(ve.set_stats(self.sheet, self.species, self.fmt))[1:]

    def clear_mimic(self) -> None:

        if "mimic" in self.vol:
            k, mid, pp = self.vol.pop("mimic")
            self.moves[k], self.pp[k] = mid, pp

    def switch_out(self) -> None:
        self.untransform()
        self.clear_mimic()
        self.slot = None
        self.ability = self.base_ability
        if self.pre_forme:

            self.species, self.pre_forme = self.pre_forme, 0
            if self.stats:
                self.stats = [self.stats[0]] + list(ve.set_stats(self.sheet, self.species, self.fmt))[1:]
        self.boosts = [0] * 7
        self.vol = {}
        self.types = self.live_types()
        self.tera_types()
        self.last_move = 0
        self.last_move_max = False
        self.result, self.protect_streak = None, 0
        if self.fmt is None or self.fmt.startswith("gen9champions"):
            self.times_attacked = 0
        self.metronome = None


PRESSURE = ve.lookup("ability", "Pressure")
HEALING_WISH = ve.lookup("move", "Healing Wish")
GLAIVE_RUSH = ve.lookup("move", "Glaive Rush")

RAMPAGE_MOVES = {"outrage", "thrash", "petaldance", "ragingfury"}
ROLLOUT_MOVES = {"rollout", "iceball"}
PERISH_SONG = ve.lookup("move", "Perish Song")

ABSORBERS = {"Lightning Rod", "Storm Drain", "Volt Absorb", "Water Absorb", "Flash Fire", "Sap Sipper", "Motor Drive", "Dry Skin",
             "Earth Eater", "Well-Baked Body", "Wind Rider", "Levitate", "Good as Gold", "Bulletproof", "Soundproof", "Telepathy"}
ILLUSION = ve.lookup("ability", "Illusion")
SHADOW_TAG = ve.lookup("ability", "Shadow Tag")
ARENA_TRAP, MAGNET_PULL, LEVITATE = (ve.lookup("ability", n) for n in ("Arena Trap", "Magnet Pull", "Levitate"))
AIR_BALLOON, IRON_BALL = ve.lookup("item", "Air Balloon"), ve.lookup("item", "Iron Ball")
BINDING_BAND = ve.lookup("item", "Binding Band")

HAZARD_INDEX = {"stealthrock": 0, "gmaxsteelsurge": 1, "spikes": 2, "stickyweb": 3, "toxicspikes": 4}

CHOICE_ITEMS = {i for i in (ve.lookup("item", n) for n in ("Choice Scarf", "Choice Band", "Choice Specs")) if i}
SPLITS = {"move: Power Split": (0, 2), "move: Guard Split": (1, 3), "move: Speed Swap": (4,)}


_GEN7_CANT_SUPPRESS = ("Battle Bond", "Comatose", "Disguise", "Multitype", "Power Construct", "RKS System", "Schooling", "Shields Down",
                       "Stance Change", "Zen Mode")
CANT_SUPPRESS = {ve.lookup("ability", n) for n in _GEN7_CANT_SUPPRESS + ("As One (Glastrier)", "As One (Spectrier)", "Gulp Missile",
                                                                          "Ice Face", "Tera Shift", "Zero to Hero")} - {0}
CANT_SUPPRESS_BY_FORMAT = {1: {ve.lookup("ability", "Multitype")} - {0},
                           2: {ve.lookup("ability", n) for n in ("Multitype", "Stance Change")} - {0},
                           3: {ve.lookup("ability", n) for n in _GEN7_CANT_SUPPRESS} - {0}}
MUST_PRESSURE = {ve.lookup("move", n) for n in ("Imprison", "Spikes", "Stealth Rock", "Toxic Spikes")}


class Tracker:
    def __init__(self, me: str, my_sheet: list[dict], foe_sheet: list[dict], fmt: str | None = None):




        self.me = me
        if fmt not in FORMATS:
            raise ValueError(f"no tracker support for format {fmt!r}")
        self.fmt = None if FORMATS[fmt][0] == 0 else fmt
        self.format_index, self.open_sheets = FORMATS[fmt]
        self.foe = "p2" if me == "p1" else "p1"
        if not self.open_sheets:
            foe_sheet = [{"name": s.get("name") or s["species"], "species": s["species"], "item": "", "ability": "", "moves": []}
                         for s in foe_sheet]
        self.mons = {self.me: [self._from_sheet(s, self.fmt) for s in my_sheet], self.foe: [self._from_sheet(s, self.fmt) for s in foe_sheet]}
        for m in self.mons[self.me] + self.mons[self.foe]:


            crowned = CROWNED.get((m.species, m.item))
            if crowned:
                m.species, sig = crowned
                m.ability = m.base_ability = ve.species_ability(m.species)
                m.types = m.live_types()
                if IRON_HEAD in m.moves:
                    k = m.moves.index(IRON_HEAD)
                    m.moves[k], m.pp[k] = sig, ve.max_pp(sig, m.fmt)
        if self.format_index in TERA_FORMATS:

            for sheet, mons in ((my_sheet, self.mons[self.me]), (foe_sheet, self.mons[self.foe])):
                for s, m in zip(sheet, mons):
                    m.tera_type = type_id(s.get("teraType")) or REQUIRED_TERA.get(m.species) or m.types[0]
        if self.format_index in DYNAMAX_FORMATS:
            for s, m in zip(my_sheet, self.mons[self.me]):
                m.gmax = bool(s.get("gigantamax"))
        if self.format_index in PREVIEW_HIDES_ITEMS:
            for m in self.mons[self.foe]:
                m.item = UNKNOWN_ITEM
        self.names = {side: [to_id(s.get("name") or s["species"]) for s in sheet] for side, sheet in ((self.me, my_sheet), (self.foe, foe_sheet))}
        self.shown = {self.me: [None, None], self.foe: [None, None]}
        self.leads = {self.me: [], self.foe: []}
        self.weather = 0
        self.weather_turns = 0
        self.weather_source = None
        self.terrain = 0
        self.terrain_turns = 0
        self.trick_room = 0
        self.gravity = 0
        self.magic_room = False
        self.hazard_seq = 0
        self.illusion_seen = False
        self._reflector = None
        self._dance = None
        self._zpower = None
        self._rampage = None
        self.other_fields: set[str] = set()
        self.fairy_lock_turn = -9
        self._future_target = ""
        self._future_hit = None
        self.turn = 0
        self._turn_counted = False
        self._weather_upkeep = False
        self._weather_fresh = False
        self.side = {s: {"reflect": 0, "lightscreen": 0, "auroraveil": 0, "tailwind": 0, "mega_used": False, "healing_wish": False,
                         "z_used": False, "ultra_used": False, "tera_used": False, "dynamax_used": False,

                         "gmax_residual": [0, 0, 0, 0], "steelsurge": False,

                         "stealthrock": False, "spikes": 0, "toxicspikes": 0, "stickyweb": False, "safeguard": 0,


                         "hazard_order": [0, 0, 0, 0, 0],
                         "healing_wish_slots": [False, False], "revivals": 0, "wish": [(-9, 0), (-9, 0)],


                         "future": [None, None]}
                     for s in (self.me, self.foe)}
        self.request = None
        self.over = False
        self.history: list[tuple] = []
        self.started = False
        self._spent: dict = {}
        self._last_move = None
        self.battle_last_move = 0
        self.battle_last_move_z = False
        self.fainted_at_turn: dict[int, dict[str, int]] = {}
        self._my_choice = [None, None]
        self._move_request = None

    def note_choice(self, choice: str) -> None:



        if self.request and self.request.get("forceSwitch"):
            return
        parts = [p.strip() for p in choice.split(",")]
        for slot in range(2):
            p = parts[slot].split() if slot < len(parts) else []
            self._my_choice[slot] = int(p[1]) - 1 if len(p) > 1 and p[0] == "move" and p[1].isdigit() else None

    @staticmethod
    def _from_sheet(s: dict, fmt: str | None = None) -> MonState:
        species = ve.lookup("species", s["species"])
        m = MonState(sheet=s, species=species, item=ve.lookup("item", s.get("item") or "") if s.get("item") else 0,
                     ability=ve.lookup("ability", s.get("ability") or "") if s.get("ability") else 0,
                     moves=[ve.lookup("move", mv) for mv in s["moves"]] + [0] * (4 - len(s["moves"])), fmt=fmt)
        m.types = ve.species_types(species, fmt)
        m.base_ability = m.ability
        m.pp = [ve.max_pp(mv, fmt) if mv else 0 for mv in m.moves]
        return m


    def _alias(self, side: str, name: str, details: str | None) -> None:


        species = [to_id(m.sheet["species"]) for m in self.mons[side]]
        want = to_id(details.split(",")[0]) if details else name
        for i, sp in enumerate(species):
            if self.names[side][i] in species and (want.startswith(sp) or sp.startswith(want)):
                self.names[side][i] = name
                return
        raise ValueError(f"no {side} sheet mon matches {name!r}")

    def _mon(self, ident: str, real: bool = True, details: str | None = None):



        pos, name = ident.split(": ", 1)
        side = pos[:2]
        if to_id(name) not in self.names[side]:
            self._alias(side, to_id(name), details)
        idx = self.names[side].index(to_id(name))
        m = self.mons[side][idx]
        if real and len(pos) == 3:
            occupant = next((o for o in self.mons[side] if o.slot == ord(pos[2]) - ord("a")), None)
            if occupant is not None and occupant is not m and occupant.ability == ILLUSION:
                m = occupant
        return side, idx, m

    @staticmethod
    def _slot(ident: str) -> int:
        return ord(ident.split(":")[0][2]) - ord("a")

    def _hp(self, side: str, m: MonState, cond: str) -> None:
        hp_part = cond.split(" ")[0]
        if hp_part.endswith("fnt") or hp_part == "0":
            m.hp, m.fainted = 0.0, True
            return
        cur, mx = hp_part.rstrip("gyr").split("/")
        m.hp = int(cur) / int(mx)
        m.fainted = False
        status = cond.split(" ")[1] if " " in cond else ""
        if status != m.status:
            if status != "tox":
                m.toxic_stage = 0
            m.status = status

    def feed(self, lines: list[str]) -> None:
        for line in lines:
            if not line.startswith("|"):
                continue
            parts = line.split("|")[1:]
            if parts[0] in ("move", "switch", "drag", "cant", "upkeep", "turn"):
                self._spent = {}
            self._line(parts[0], parts[1:])

    def set_request(self, request: dict | None) -> None:
        self.request = request
        if not request:
            return
        if request.get("active"):
            self._move_request = request
        party = request["side"]["pokemon"]

        for k, p in enumerate(party[:2]):
            if p.get("active"):
                side, idx, m = self._mon(p["ident"].replace(": ", "a: ", 1), real=False)
                if m.slot != k:
                    shown = next((o for o in self.mons[side] if o.slot == k and o is not m), None)
                    self._take_over(m, shown, k)
        for p in party:
            side, idx, m = self._mon(p["ident"].replace(": ", "a: ", 1) if p["ident"][2] == ":" else p["ident"], real=False)
            if not m.brought:
                m.types = m.live_types()
            m.brought = True
            st = p["stats"]
            cond = p["condition"]
            if cond.startswith("0") and m.stats:

                self._hp(side, m, cond)
                continue
            if not cond.startswith("0"):
                mx = int(cond.split(" ")[0].split("/")[1])
            else:
                mx = m.stats[0] if m.stats else 1
            m.stats = [mx, st["atk"], st["def"], st["spa"], st["spd"], st["spe"]]
            if not self.open_sheets:


                m.item = ve.lookup("item", p["item"]) if p.get("item") else 0
                if "transform" in m.vol and p.get("moves"):
                    m.moves = [_request_move(x) for x in p["moves"]][:4]
                    m.moves += [0] * (4 - len(m.moves))
            if "raw" in m.vol:
                m.stats[1:] = m.vol["raw"]
            self._hp(side, m, cond)
        for k, act in enumerate(request.get("active", []) or []):
            if k >= len(party):
                break
            side, idx, m = self._mon(party[k]["ident"].replace(": ", "a: ", 1), real=False)
            for mv in act.get("moves", []):
                mid = _request_move(mv.get("id", ""))
                if mid in m.moves and "pp" in mv:
                    m.pp[m.moves.index(mid)] = mv["pp"]


            moves = act.get("moves", []) or []
            locked = len(moves) == 1 and to_id(moves[0].get("id", "")) in RAMPAGE_MOVES
            if locked and "lockedmove" not in m.vol:
                m.vol["lockedmove"] = (ve.lookup("move", moves[0]["id"]), 1, self.turn)
            elif not locked and "lockedmove" in m.vol:
                m.vol.pop("lockedmove")


    def _line(self, kind: str, a: list[str]) -> None:
        if self._last_move and kind.startswith("-"):
            user = self.mons[self._last_move[0]][self._last_move[1]]
            if user.result is not None:
                user.result["still"] = False
                if kind == "-heal" and not any(x.startswith("[from]") or x == "[silent]" for x in a[2:]):
                    user.result["hit"] = True

        if self._last_move and kind in ("-ability", "-start", "-heal", "-boost", "-immune", "-activate") and any(
                x.replace("[from] ", "").replace("ability: ", "") in (ABSORBERS if kind != "-activate" else {"Telepathy"}) for x in a[1:]):
            user = self.mons[self._last_move[0]][self._last_move[1]]
            if user.result is not None and self._last_move[2] != PERISH_SONG:

                user.result["miss"] = True
        if (self._last_move and kind == "-start" and len(a) > 1 and a[1] == "confusion" and not any(x.startswith("[") for x in a[2:])
                and self._mon(a[0])[:2] != tuple(self._last_move[:2])):
            user = self.mons[self._last_move[0]][self._last_move[1]]
            if user.result is not None:
                user.result["hit"] = True
        if kind in ("switch", "drag"):
            side, idx, m = self._mon(a[0], real=False, details=a[1])
            m.gender = details_gender(a[1])
            slot = self._slot(a[0])
            if side == self.foe and m.slot is not None and m.slot != slot and not m.fainted:


                holder = next((o for o in self.mons[side] if o.ability == ILLUSION and o is not m), None)
                if holder is None:

                    self.illusion_seen = True
                if holder is not None:
                    if slot == 0 and sum(o.fainted for o in self.mons[side]) >= 2:
                        m.before_switch_in = (m.hp, m.status, m.toxic_stage, m.fainted, m.item)
                        m = holder
                    else:
                        self._take_over(holder, m, m.slot)
            m.before_switch_in = (m.hp, m.status, m.toxic_stage, m.fainted, m.item)
            m.moved = False
            m.acted = False
            m.revealed = True
            slot = self._slot(a[0])
            out = next((i for i, o in enumerate(self.mons[side]) if o.slot == slot), None)
            baton = None
            if out is not None and "[from] Baton Pass" in a[3:]:


                o = self.mons[side][out]
                keys = ("confusion", "perish", "taunt", "healblock", "substitute", "trapped", "trapped_by", "gmax_trap", "gastroacid")
                baton = (list(o.boosts), {k: o.vol[k] for k in keys if k in o.vol})
            elif out is not None and "[from] Shed Tail" in a[3:]:

                o = self.mons[side][out]
                baton = ([0] * 7, {"substitute": True} if "substitute" in o.vol else {})


            holder = None
            if side == self.foe and out == idx and not m.revived:
                holder = next((i for i, o in enumerate(self.mons[side]) if o.ability == ILLUSION and o is not m and o.slot is None
                               and not o.fainted), None)
            if out is not None:
                o = self.mons[side][out]
                if (o.ability == REGENERATOR and not o.fainted and o.hp > 0 and o.fmt is not None and not o.fmt.startswith("gen9champions")
                        and (side == self.me or self.open_sheets)):



                    if side == self.me and o.stats:
                        mx = o.stats[0]
                        o.hp = min(mx, round(o.hp * mx) + mx // 3) / mx
                    else:
                        o.hp = min(100, int(o.hp * 100 + 1e-6) + 100 // 3) / 100
                o.switch_out()
            if holder is not None:
                m.vol["illusion_holder"] = holder
            if baton:
                m.boosts, carried = baton
                m.vol.update(carried)
                if "gastroacid" in carried:
                    if m.ability in CANT_SUPPRESS_BY_FORMAT.get(self.format_index, CANT_SUPPRESS):
                        m.vol.pop("gastroacid")
                    else:
                        m.vol["gastroacid"], m.ability = m.ability, 0
            if not m.brought:
                m.types = m.live_types()
            m.slot, m.brought, m.fainted = slot, True, False
            m.turns_active = 0
            if m.status == "tox":
                m.toxic_stage = 0
            self._hp(side, m, a[2])
            if m.ability != NEUTRALIZING_GAS and self._gas_holder(exclude=(side, idx)) is not None:
                self._suppress(m)

            shown_out = self.shown[side][slot] if self.shown[side][slot] is not None else out
            self.shown[side][slot] = idx
            if self.turn == 0 and idx not in self.leads[side] and len(self.leads[side]) < 2:
                self.leads[side].append(idx)
            revived = out == idx and m.revived
            m.revived = False
            if shown_out is not None and not revived:
                self._event(EV_SWITCH, (side, idx), (side, shown_out), slot)
            return
        if kind == "replace":

            side, idx, m = self._mon(a[0], real=False)
            slot = self._slot(a[0])
            shown = next((o for o in self.mons[side] if o.slot == slot and o is not m), None)
            self._take_over(m, shown, slot)
            m.revealed = True
            self.shown[side][slot] = idx
            return
        if kind == "swap":

            side, idx, m = self._mon(a[0])
            to = int(a[1])
            self.shown[side][to], self.shown[side][1 - to] = self.shown[side][1 - to], self.shown[side][to]
            other = next((o for o in self.mons[side] if o.slot == to and o is not m), None)
            if other is not None:
                other.slot = m.slot
            m.slot = to
            return
        if kind == "turn":
            self.started = True
            if a and a[0].isdigit():
                self.fainted_at_turn[int(a[0])] = {s: sum(1 for m in self.mons[s] if m.fainted) for s in (self.me, self.foe)}
            self._turn_counted = False
            self._weather_upkeep = False
            self._weather_fresh = False
            for side in (self.me, self.foe):
                for m in self.mons[side]:
                    if m.item not in CHOICE_ITEMS:
                        m.vol.pop("choicelock", None)
                    m.vol.pop("shelltrap", None)
            for side in (self.me, self.foe):
                for m in self.mons[side]:
                    if m.slot is not None and not m.fainted:
                        m.turns_active += 1
            return
        if kind == "upkeep":
            self._future_hit = None
            for side in (self.me, self.foe):
                for m in self.mons[side]:
                    if m.vol.get("protect") and m.stall_turn != self.turn:
                        m.vol["protect"], m.protect_streak = False, 0
            for side in (self.me, self.foe):
                for m in self.mons[side]:
                    lock = m.vol.get("lockedmove")
                    if lock and (lock[2] != self.turn or m.status == "slp"):


                        m.vol.pop("lockedmove")
                    if m.vol.get("rollout") is not None and m.vol["rollout"] != self.turn:
                        m.vol.pop("rollout")
                    if m.vol.get("lockon") is not None and m.vol["lockon"] != self.turn:
                        m.vol.pop("lockon")
            for side in (self.me, self.foe):
                for m in self.mons[side]:
                    if "dynamax" in m.vol:
                        m.vol["dynamax"] += 1
            self._rampage = None
            self.turn += 1
            self._turn_counted = True
            for side in (self.me, self.foe):
                for m in self.mons[side]:
                    if "roost" in m.vol:
                        m.types = m.vol.pop("roost")
            self._tick()
            return
        if kind in ("win", "tie"):

            if not self._turn_counted:
                self.turn += 1

                if self._weather_upkeep and self.weather_turns > 0:
                    self.weather_turns -= 1
                    if self.weather_turns == 0:
                        self.weather = 0
            self.over = True
            return
        if kind == "faint":
            side, idx, m = self._mon(a[0])
            if self._last_move and self._last_move[:3] == (side, idx, HEALING_WISH) and m.slot is not None:


                self._set_healing_wish(side, m.slot, True)
            m.hp, m.fainted = 0.0, True
            m.untransform()
            m.clear_mimic()

            m.ability = m.base_ability
            if m.pre_forme:
                m.species, m.pre_forme = m.pre_forme, 0
                m.types = m.live_types()
                if m.stats:
                    m.stats = [m.stats[0]] + list(ve.set_stats(m.sheet, m.species, m.fmt))[1:]
            if "raw" in m.vol and m.stats:


                m.stats = [m.stats[0]] + list(ve.set_stats(m.sheet, m.species, m.fmt))[1:]
            m.dynamax_fainted = "dynamax" in m.vol
            m.vol = {}
            m.boosts = [0] * 7
            if m.tera:
                m.tera = False
                m.types = m.live_types()
            if m.slot is not None:
                partner = next((o for o in self.mons[side] if o.slot == 1 - m.slot and not o.fainted), None)
                if partner is not None:
                    partner.vol.pop("commanding", None)
            self._event(EV_FAINT, (side, idx), None, 0)
            return
        if kind in ("-damage", "-heal", "-sethp"):
            side, idx, m = self._mon(a[0])
            self._hp(side, m, a[1])
            frm = next((x for x in a[2:] if x.startswith("[from]")), None)
            if kind == "-damage" and frm is None:
                self._hit(side, idx, a[0])
                src = (self._last_move[:3] if self._last_move is not None
                       else (*self._future_hit, self._future_move) if self._future_hit is not None else None)
                if src is not None and src[2] not in NO_STELLAR_SPEND:
                    user = self.mons[src[0]][src[1]]
                    if "illusion_holder" in user.vol:
                        user = self.mons[src[0]][user.vol["illusion_holder"]]
                    if user.tera and user.tera_shown == STELLAR and user.species != TERAPAGOS_STELLAR:
                        t = STELLAR if src[2] == TERA_BLAST else move_type(src[2])
                        if t:
                            user.stellar_spent |= 1 << t
            if kind == "-heal" and frm == "[from] move: Revival Blessing":
                m.fainted, m.revived = False, True
                self.side[side]["revivals"] += 1
            if kind == "-heal" and frm == "[from] move: Healing Wish" and m.slot is not None:
                self._set_healing_wish(side, m.slot, False)
            if kind == "-damage" and frm == "[from] confusion":

                self._event(EV_MOVE, (side, idx), None, 0, outcome=-1)
                self._last_move = None
                m.vol.pop("charging", None)

                if self._dance != (side, idx):
                    m.acted = True
                self._dance = None
                m.vol.pop("glaiverush", None)
                m.vol.pop("destinybond", None)
                m.result = {"fail": True, "miss": False, "hit": False, "null": False, "still": False}
                m.result_turn = self.turn
            if frm == "[from] Leech Seed":
                of = next((x[5:] for x in a[2:] if x.startswith("[of] ")), None)
                if of and of[2] in "ab":
                    m.vol["leechseed"] = {"p1": 0, "p2": 1}[of[:2]] * 2 + "ab".index(of[2]) + 1
            if frm and "psn" in frm and m.status == "tox":
                m.toxic_stage = min(15, m.toxic_stage + 1)
            return
        if kind == "-status":
            side, idx, m = self._mon(a[0])
            m.status = a[1]
            m.toxic_stage = 0
            m.status_tries, m.rest_sleep = 0, "[from] move: Rest" in a[2:]
            if a[1] == "slp":
                m.vol.pop("yawn", None)
            return
        if kind == "-curestatus":
            side, idx, m = self._mon(a[0]) if ": " in a[0] else (None, None, None)
            if m:
                m.status, m.toxic_stage = "", 0
            return
        if kind in ("-boost", "-unboost"):
            side, idx, m = self._mon(a[0])
            d = int(a[2]) * (1 if kind == "-boost" else -1)
            if d:
                m.vol["stats_raised" if d > 0 else "stats_lowered"] = True
            i = BOOSTS[a[1]]
            m.boosts[i] = max(-6, min(6, m.boosts[i] + d))
            return
        if kind == "-setboost":
            side, idx, m = self._mon(a[0])
            m.boosts[BOOSTS[a[1]]] = int(a[2])
            return
        if kind in ("-clearboost", "-clearallboost"):
            targets = [self._mon(a[0])[2]] if kind == "-clearboost" else [m for s in self.mons.values() for m in s]
            for m in targets:
                m.boosts = [0] * 7
            return
        if kind == "-clearnegativeboost":
            m = self._mon(a[0])[2]
            m.boosts = [max(0, b) for b in m.boosts]
            return
        if kind == "-weather":
            w = WEATHERS.get(a[0], 0)
            if any(x == "[upkeep]" for x in a[1:]):
                self._weather_upkeep = True
                return
            self.weather = w
            self.weather_name = a[0]
            self.weather_source = None
            if a[0] in STRONG_WEATHERS:
                self.weather_turns = 0
                of = next((x[5:] for x in a if x.startswith("[of] ")), None)
                if of:
                    side, idx, _ = self._mon(of)
                    self.weather_source = (side, idx)
                return
            if w == 0:
                self.weather_turns = 0
                return
            if self.format_index == 1 and any(x.startswith("[from] ability:") for x in a[1:]):
                self.weather_turns = 0
                return
            setter = self._setter(a)
            rock = WEATHER_ROCKS.get(w)
            self.weather_turns = 8 if setter is not None and setter.item and ve.lookup("item", rock) == setter.item else 5

            self._weather_fresh = self._weather_upkeep
            return
        if kind == "-fieldstart":
            name = a[0].replace("move: ", "")
            setter = self._setter(a)
            if name in TERRAINS:
                self.terrain = TERRAINS[name]
                ext = ve.lookup("item", "Terrain Extender")
                self.terrain_turns = 8 if setter is not None and setter.item == ext and not self.magic_room else 5
            elif name == "Trick Room":
                self.trick_room = 5
            elif name == "Gravity":
                self.gravity = 5
            elif name == "Magic Room":
                self.magic_room = True
            else:
                self.other_fields.add(name)
            return
        if kind == "-fieldend":
            name = a[0].replace("move: ", "")
            if name in TERRAINS:
                self.terrain, self.terrain_turns = 0, 0
            elif name == "Trick Room":
                self.trick_room = 0
            elif name == "Gravity":
                self.gravity = 0
            elif name == "Magic Room":
                self.magic_room = False
            else:
                self.other_fields.discard(name)
            return
        if kind == "-swapsideconditions":

            keys = ("reflect", "lightscreen", "auroraveil", "tailwind", "safeguard", "stealthrock", "spikes", "toxicspikes", "stickyweb",
                    "gmax_residual", "steelsurge", "hazard_order")
            mine, theirs = self.side[self.me], self.side[self.foe]
            for k in keys:
                mine[k], theirs[k] = theirs[k], mine[k]
            return
        if kind in ("-sidestart", "-sideend"):
            side = a[0][:2]
            cond = to_id(a[1].replace("move: ", ""))
            k = HAZARD_INDEX.get(cond)
            if kind == "-sidestart" and k is not None and not self.side[side]["steelsurge" if cond == "gmaxsteelsurge" else cond]:

                self.hazard_seq = min(self.hazard_seq + 1, 0xFFFF)
                self.side[side]["hazard_order"][k] = self.hazard_seq
            if cond in GMAX_RESIDUALS:
                self.side[side]["gmax_residual"][GMAX_RESIDUALS.index(cond)] = 4 if kind == "-sidestart" else 0
            elif cond == "gmaxsteelsurge":
                self.side[side]["steelsurge"] = kind == "-sidestart"
            if cond in ("stealthrock", "stickyweb"):
                self.side[side][cond] = kind == "-sidestart"
            elif cond in ("spikes", "toxicspikes"):
                cap = 3 if cond == "spikes" else 2
                self.side[side][cond] = min(cap, self.side[side][cond] + 1) if kind == "-sidestart" else 0
            elif cond == "safeguard":
                self.side[side][cond] = 5 if kind == "-sidestart" else 0
            if cond in ("reflect", "lightscreen", "auroraveil", "tailwind"):
                if kind == "-sideend":
                    self.side[side][cond] = 0
                else:
                    setter = self._last_move_mon()
                    clay = ve.lookup("item", "Light Clay")
                    self.side[side][cond] = 4 if cond == "tailwind" else (8 if setter is not None and setter.item == clay and not self.magic_room else 5)
            return
        if kind == "-mega":
            side, idx, m = self._mon(a[0])
            m.mega = True
            self.side[side]["mega_used"] = True
            return
        if kind == "-burst":

            side, idx, m = self._mon(a[0])
            m.mega = True
            self.side[side]["ultra_used"] = True
            return
        if kind == "-zpower":

            side, idx, m = self._mon(a[0])
            self.side[side]["z_used"] = True
            self._zpower = (side, idx)
            return
        if kind == "-invertboost":
            m = self._mon(a[0])[2]
            m.boosts = [-b for b in m.boosts]
            return
        if kind == "-terastallize":

            side, idx, m = self._mon(a[0])
            if "illusion_holder" in m.vol:

                holder = self.mons[side][m.vol["illusion_holder"]]
                holder.tera, holder.tera_shown = True, type_id(a[1])
                holder.tera_types()
                m.tera_shown = holder.tera_shown
                if m.tera_shown != STELLAR:
                    m.types = (m.tera_shown, 0)
            else:
                m.tera, m.tera_shown = True, type_id(a[1])
                m.tera_types()
                m.vol["tera_logged"] = True
            self.side[side]["tera_used"] = True
            return
        if kind == "-primal":


            self._mon(a[0])[2].mega = True
            return
        if kind == "detailschange":
            side, idx, m = self._mon(a[0])
            sp = ve.lookup("species", a[1].split(",")[0])

            if sp and sp == ve.lookup("species", "greninja") and m.species == ve.lookup("species", "greninjaash"):
                sp = ve.lookup("species", "greninjabond")
            if sp:
                old_species, m.species = m.species, sp
                m.types = m.live_types()
                m.tera_types()


                if m.fainted and m.sheet and m.sheet.get("ability"):
                    m.base_ability = ve.lookup("ability", m.sheet["ability"])
                else:
                    m.base_ability = ve.species_ability(sp)
                self._set_ability(m, m.base_ability)
                m.vol.pop("raw", None)
                if side == self.me:

                    hp = m.stats[0] if m.stats else None
                    m.stats = list(ve.set_stats(m.sheet, sp, m.fmt))

                    if hp is not None and ve.set_stats(m.sheet, old_species, m.fmt)[0] == m.stats[0]:
                        m.stats[0] = hp
            return
        if kind == "-ability" and a[1] == "Neutralizing Gas" and len(a) == 2:

            side, idx, m = self._mon(a[0])
            self._set_ability(m, NEUTRALIZING_GAS)
            m.vol.pop("ngas_ended", None)
            for sd in (self.me, self.foe):
                for o in self.mons[sd]:
                    if o is not m and o.slot is not None and not o.fainted:
                        self._suppress(o)
            return
        if kind == "-end" and len(a) > 1 and a[1] == "ability: Neutralizing Gas":


            self._mon(a[0])[2].vol["ngas_ended"] = True
            self._release_gas()
            return
        if kind == "-activate" and len(a) > 2 and a[1] == "ability: Symbiosis":

            of = next((x[5:] for x in a[3:] if x.startswith("[of] ")), None)
            self._mon(a[0])[2].item = 0
            if of:
                self._mon(of)[2].item = ve.lookup("item", a[2])
            return
        if kind == "-singleturn" and len(a) > 1 and a[1] == "move: Shell Trap":
            self._mon(a[0])[2].vol["shelltrap"] = 1
        if kind == "-activate" and len(a) > 1 and a[1] == "ability: Battle Bond":
            self._mon(a[0])[2].bond = True
        if kind == "-activate" and len(a) > 1 and a[1] == "ability: Dancer":

            self._dance = self._mon(a[0])[:2]
            return
        if kind == "-activate" and len(a) > 1 and a[1] == "ability: Commander":

            self._mon(a[0])[2].vol["commanding"] = True
            return
        if kind == "-ability":
            side, idx, m = self._mon(a[0])
            if a[1] == "Unnerve" and len(a) == 2:
                m.vol["unnerved"] = True
            elif a[1] != "As One":
                m.vol.pop("unnerved", None)
            if a[1] == "Unnerve" and len(a) == 2 and self._real_ability(m) in AS_ONE:
                return
            if a[1] in ("Chilling Neigh", "Grim Neigh") and self._real_ability(m) in AS_ONE:
                return
            if a[1] == "As One":

                if self._real_ability(m) not in AS_ONE:
                    of = next((x[5:] for x in a[2:] if x.startswith("[of] ")), None)
                    src = self._real_ability(self._mon(of)[2]) if of else 0
                    if src in AS_ONE:
                        self._set_ability(m, src)
                return
            ab = ve.lookup("ability", a[1])


            if ab and not any(x.startswith("[from] ability:") and not any(k in x for k in ("Trace", "Receiver", "Power of Alchemy"))
                              for x in a[2:]):
                self._set_ability(m, ab)
                if m.slot is not None and not m.fainted and self._gas_holder(exclude=(side, idx)) is not None:
                    self._suppress(m)


            if a[1] == "Perish Body" and self._last_move:
                for mon in (self.mons[self._last_move[0]][self._last_move[1]], m):
                    if not mon.fainted and not mon.vol.get("perish"):
                        mon.vol["perish"] = 4
            if a[1] == "Supersweet Syrup":
                m.syrup = True
            return
        if kind == "-transform":


            side, idx, m = self._mon(a[0])
            tside, _, t = self._mon(a[1])
            if m.ability == NEUTRALIZING_GAS and self._gas_holder(exclude=(side, idx)) is None:
                self._release_gas()
            m.vol["transform"] = (m.species, list(m.moves), list(m.pp))
            m.vol["raw"] = self._raw(tside, t)
            m.species = t.species
            m.types = tuple(t.vol.get("roost", t.types))
            m.tera_types()
            m.moves = list(t.moves)
            m.pp = [5 if mv else 0 for mv in m.moves]
            m.boosts = list(t.boosts)
            m.times_attacked = t.times_attacked
            for k in ("focusenergy", "dragoncheer", "dragoncheer_dragon"):
                m.vol.pop(k, None)
                if k in t.vol:
                    m.vol[k] = t.vol[k]
            self._set_ability(m, self._real_ability(t))
            if m.ability == NEUTRALIZING_GAS and self._gas_holder(exclude=(side, idx)) is not None:

                m.vol["ngas"], m.ability = NEUTRALIZING_GAS, 0
            if m.vol.get("choicelock") not in (None, True) and m.vol["choicelock"] not in m.moves:
                m.vol.pop("choicelock")
            if side == self.me and m.stats:
                m.stats[1:] = m.vol["raw"]
            return
        if kind == "-endability":

            side, idx, m = self._mon(a[0])
            if "gastroacid" not in m.vol:
                m.vol["gastroacid"], m.ability = m.vol.pop("ngas", m.ability), 0
            return
        if kind == "poke" and not self.open_sheets and len(a) > 2 and a[0] == self.foe:

            k = self._poke_seen = getattr(self, "_poke_seen", 0) + 1
            if k <= len(self.mons[self.foe]) and self.format_index not in PREVIEW_HIDES_ITEMS:
                self.mons[self.foe][k - 1].item = UNKNOWN_ITEM if a[2] in ("item", "mail") else 0
            return
        if kind in ("-item",) and not a[0]:
            return
        if kind in ("-item",):
            side, idx, m = self._mon(a[0])
            if m.item and any(x in ("[from] move: Trick", "[from] move: Switcheroo") for x in a[2:]):
                m.vol["item_consumed"] = True
            if "[from] ability: Pickpocket" in a[2:]:
                m.vol.pop("item_consumed", None)
            m.item = ve.lookup("item", a[1])
            if any(x in ("[from] move: Trick", "[from] move: Switcheroo") for x in a[2:]) and self._spent.get(a[0]) == a[1]:

                m.item = 0
            if "[from] ability: Magician" in a[2:]:

                of = next((x[5:] for x in a[2:] if x.startswith("[of] ")), None)
                if of:
                    self._mon(of)[2].item = 0
            if m.item in CHOICE_ITEMS:
                m.vol.pop("choicelock", None)
            return
        if kind == "-enditem":
            side, idx, m = self._mon(a[0])
            if "illusion_holder" in m.vol:
                m = self.mons[side][m.vol["illusion_holder"]]
            if not any(x.startswith("[from]") for x in a[2:]):
                self._spent[a[0]] = a[1]
            m.item = 0
            m.vol["item_consumed"] = True
            if to_id(a[1]) == "powerherb":
                m.vol.pop("charging", None)
            return
        if kind == "-anim":

            side, idx, m = self._mon(a[0])
            m.vol.pop("charging", None)
            return
        if kind in ("-start", "-end"):
            side, idx, m = self._mon(a[0])
            if kind == "-end" and a[1] == "Substitute" and len(a) == 2:
                self._hit(side, idx, a[0], into_sub=True)
            if kind == "-end" and "[partiallytrapped]" in a[2:]:
                m.vol.pop("trapped", None)
                m.vol.pop("gmax_trap", None)
                return
            eff = to_id(a[1].replace("move: ", ""))
            on = kind == "-start"
            if eff == "dynamax":


                if on:
                    m.vol["dynamax"] = 0
                    self.side[side]["dynamax_used"] = True
                    if "Gmax" in a[2:]:
                        m.gmax = True
                    if m.stats and m.species != SHEDINJA:

                        level = m.sheet.get("dynamaxLevel", 10) if isinstance(m.sheet, dict) else 10
                        m.vol["dynamax_base_hp"] = m.stats[0]
                        m.stats[0] = int(m.stats[0] * (1.5 + level * 0.05))
                else:
                    m.vol.pop("dynamax", None)
                    if "dynamax_base_hp" in m.vol and m.stats:
                        m.stats[0] = m.vol.pop("dynamax_base_hp")
                return
            if eff == "gmaxchistrike" and on:
                m.vol["chistrike"] = min(3, m.vol.get("chistrike", 0) + 1)
                return
            if eff == "mimic" and on and len(a) > 2:


                mimic, new = ve.lookup("move", "Mimic"), ve.lookup("move", a[2])
                if mimic in m.moves and new:
                    k = m.moves.index(mimic)
                    m.vol["mimic"] = (k, mimic, m.pp[k])
                    m.moves[k] = new
                    m.pp[k] = base_pp(new, m.fmt)
                elif new and side == self.foe and not self.open_sheets and new not in m.moves and 0 in m.moves:

                    k = m.moves.index(0)
                    m.vol["mimic"] = (k, 0, 0)
                    m.moves[k] = new
                return
            if eff == "powertrick":


                raw = self._raw(side, m)
                raw[0], raw[1] = raw[1], raw[0]
                m.vol["raw"] = raw
                m.vol["powertrick"] = on
                if m.stats:
                    m.stats[1:] = raw
                return
            if eff == "confusion" and on and "[fatigue]" in a[2:]:
                m.vol.pop("lockedmove", None)
            if eff == "attract":


                if on:
                    of = next((x[5:] for x in a[2:] if x.startswith("[of] ")), None)
                    src = self._mon(of)[:2] if of else (tuple(self._last_move[:2]) if self._last_move else None)
                    if src is not None:
                        m.vol["attract"] = src
                else:
                    m.vol.pop("attract", None)
                return
            if eff in ("futuresight", "doomdesire"):



                if on:
                    tgt = self._future_target
                    pos = tgt.split(": ", 1)[0] if tgt else ""
                    if len(pos) == 3:
                        tside, tslot = pos[:2], ord(pos[2]) - ord("a")
                    else:
                        tside = pos[:2] if pos else (self.foe if side == self.me else self.me)
                        tslot = (1 - m.slot) if tside == side and m.slot is not None else 0
                    name = "Doom Desire" if eff == "doomdesire" else "Future Sight"
                    self.side[tside]["future"][tslot] = (self.turn, (side, idx), ve.lookup("move", name))
                elif len(a[0].split(": ", 1)[0]) == 3:

                    f = self.side[a[0][:2]]["future"][self._slot(a[0])]
                    self.side[a[0][:2]]["future"][self._slot(a[0])] = None
                    self._last_move = None
                    self._future_hit = f[1] if f else None
                    self._future_move = f[2] if f else 0
                return
            if eff == "dragoncheer" and on and self._type_id("Dragon") in m.types:
                m.vol["dragoncheer_dragon"] = True
            if eff == "encore" and on:
                m.vol["encore_move"] = m.last_move
            elif eff == "disable" and on and len(a) > 2:
                m.vol["disable_move"] = ve.lookup("move", a[2].replace("move: ", ""))
            if eff == "leechseed" and on and (self._reflector or self._last_move):
                ref = self._reflector or self._last_move[:2]
                seeder = self.mons[ref[0]][ref[1]]
                if seeder.slot is not None:
                    m.vol["leechseed"] = {"p1": 0, "p2": 1}[ref[0]] * 2 + seeder.slot + 1
            elif eff == "magnetrise":
                if on:
                    m.vol["magnetrise"] = self.turn
                else:
                    m.vol.pop("magnetrise", None)
            elif eff.startswith("perish"):
                m.vol["perish"] = int(eff[-1]) if on else 0
            elif eff.startswith("stockpile"):
                m.vol["stockpile"] = int(eff[-1]) if on else 0
            elif eff == "typechange" and not on:

                m.types = m.live_types()
                m.tera_types()
            elif eff == "typechange" and on and m.hp <= 0 and "[from] ability: Mimicry" in a[3:]:
                pass
            elif eff == "typechange" and on:
                if any(x in ("[from] ability: Protean", "[from] ability: Libero") for x in a[3:]):
                    m.vol["protean"] = True
                if a[2].startswith("[from]"):


                    of = next((x[5:] for x in a[2:] if x.startswith("[of] ")), None)
                    if of:
                        m.types = tuple(self._mon(of)[2].types)
                else:
                    ts = a[2].split("/")
                    m.types = tuple([self._type_id(t) for t in ts] + [0] * (2 - len(ts)))
            else:
                if on:
                    m.vol[eff] = True
                else:
                    m.vol.pop(eff, None)
            return
        if kind == "-activate" and len(a) > 3 and a[1] in ("move: Spite", "move: Eerie Spell", "move: G-Max Depletion"):


            m, mid = self._mon(a[0])[2], ve.lookup("move", a[2])
            if mid in m.moves and a[3].isdigit():
                k = m.moves.index(mid)
                m.pp[k] = max(0, m.pp[k] - int(a[3]))
            return
        if kind == "-activate" and len(a) > 1 and a[1] in ("move: Lock-On", "move: Mind Reader"):

            self._mon(a[0])[2].vol["lockon"] = self.turn
            return
        if kind == "-activate" and len(a) > 2 and a[1] == "move: Sketch":

            m, new = self._mon(a[0])[2], ve.lookup("move", a[2])
            if SKETCH in m.moves and new:
                k = m.moves.index(SKETCH)
                m.moves[k], m.pp[k] = new, base_pp(new, m.fmt)
            return
        if kind == "-activate" and len(a) > 2 and a[1] == "ability: Mummy":

            self._set_ability(self._mon(a[2])[2], ve.lookup("ability", "Mummy"))
            return
        if kind == "-activate" and len(a) > 1 and a[1] in ("Skill Swap", "move: Skill Swap"):

            side, idx, m = self._mon(a[0])
            of = next((x[5:] for x in a[2:] if x.startswith("[of] ")), None)
            if of:
                o = self._mon(of)[2]
                named = [x for x in a[2:4] if not x.startswith("[")]
                if len(named) == 2 and all(named):

                    self._set_ability(m, ve.lookup("ability", named[0]))
                    self._set_ability(o, ve.lookup("ability", named[1]))
                else:
                    mine, theirs = self._real_ability(m), self._real_ability(o)
                    self._set_ability(m, theirs)
                    self._set_ability(o, mine)
            return
        if kind == "-activate" and len(a) > 1 and a[1] in SPLITS:


            of = next((x[5:] for x in a[2:] if x.startswith("[of] ")), None)
            if of:
                pair = [self._mon(a[0]), self._mon(of)]
                raws = [self._raw(sd, mm) for sd, _, mm in pair]
                for k in SPLITS[a[1]]:
                    if a[1] == "move: Speed Swap":
                        raws[0][k], raws[1][k] = raws[1][k], raws[0][k]
                    else:
                        raws[0][k] = raws[1][k] = (raws[0][k] + raws[1][k]) // 2
                for (sd, _, mm), raw in zip(pair, raws):
                    mm.vol["raw"] = raw
                    mm.vol["split"] = True
            return
        if kind == "-formechange":
            side, idx, m = self._mon(a[0])
            sp = ve.lookup("species", a[1].split(",")[0])
            if sp:
                m.pre_forme = m.pre_forme or m.species
                m.species = sp
                m.types = m.live_types()
                m.tera_types()
                if side == self.me and m.stats:
                    m.stats = [m.stats[0]] + list(ve.set_stats(m.sheet, sp, m.fmt))[1:]
                m.vol.pop("raw", None)
            return
        if kind == "-copyboost":


            m, t = self._mon(a[0])[2], self._mon(a[1])[2]
            m.boosts = list(t.boosts)
            if self.format_index != 1:
                for k in ("focusenergy", "dragoncheer", "dragoncheer_dragon", "chistrike"):
                    m.vol.pop(k, None)
                    if k in t.vol:
                        m.vol[k] = t.vol[k]
            return
        if kind == "-swapboost" and len(a) > 1:


            u, t = self._mon(a[0])[2], self._mon(a[1])[2]
            named = a[2] if len(a) > 2 and not a[2].startswith("[") else ""
            idx = [BOOSTS[x.strip()] for x in named.split(",") if x.strip() in BOOSTS] if named else list(range(7))
            for i in idx:
                u.boosts[i], t.boosts[i] = t.boosts[i], u.boosts[i]
            return
        if kind == "-activate" and len(a) > 2 and a[1] in ("Substitute", "move: Substitute") and a[2] == "[damage]":
            self._hit(*self._mon(a[0])[:2], a[0], into_sub=True)
            return
        if kind == "-activate" and len(a) > 1 and (a[1] == "move: Feint" or "[broken]" in a[2:]):


            if self.format_index != 1:
                self._mon(a[0])[2].vol["protect"] = False
            return
        if kind == "-activate" and len(a) > 2 and a[1] == "item: Leppa Berry":
            side, idx, m = self._mon(a[0])
            mid = ve.lookup("move", a[2])
            if mid in m.moves:
                k = m.moves.index(mid)
                m.pp[k] = min(ve.max_pp(mid, m.fmt), m.pp[k] + 10)
            return
        if kind == "-activate":
            if len(a) > 1 and a[1].startswith("move: ") and to_id(a[1][6:]) in ("infestation", "firespin", "whirlpool", "sandtomb", "wrap", "bind", "magmastorm", "snaptrap", "thundercage", "clamp", "gmaxcentiferno", "gmaxsandblast"):
                side, idx, m = self._mon(a[0])
                m.vol["trapped"] = True
                of = next((x[5:] for x in a[2:] if x.startswith("[of] ")), None)


                if of and to_id(a[1][6:]).startswith("gmax"):
                    m.vol.pop("trapped_by", None)
                    m.vol["gmax_trap"] = "band" if self._mon(of)[2].item == BINDING_BAND else "plain"
                elif of:
                    m.vol.pop("gmax_trap", None)
                    m.vol["trapped_by"] = self._mon(of)[:2]
            if len(a) > 1 and a[1] in ("move: Protect", "move: Wide Guard", "move: Quick Guard") and self._last_move:
                user = self.mons[self._last_move[0]][self._last_move[1]]
                if user.result is not None:
                    user.result["null"] = True
            if len(a) > 1 and a[1] == "move: Psychic Terrain" and self._last_move:
                user = self.mons[self._last_move[0]][self._last_move[1]]
                if user.result is not None:
                    user.result["miss"] = True
            return
        if kind == "-singlemove":
            if a[1] == "Destiny Bond":
                self._mon(a[0])[2].vol["destinybond"] = True
            return
        if kind == "-singleturn":
            side, idx, m = self._mon(a[0])
            flying = self._type_id("Flying")
            if a[1] == "move: Roost" and "roost" not in m.vol and flying in m.types:

                m.vol["roost"] = m.types
                m.types = tuple(0 if t == flying else t for t in m.types)
            return
        if kind == "-prepare":
            side, idx, m = self._mon(a[0])
            if a[1] != "Chilly Reception":
                m.metronome = m.metronome_prev
                m.vol["charging"] = True
                m.vol["charge_move"] = to_id(a[1])
                if side == self.me:


                    foe = self.foe if side == self.me else self.me
                    m.vol["charge_pressure"] = {o.slot: (not o.fainted and o.ability == PRESSURE) for o in self.mons[foe] if o.slot is not None}
                if m.result is not None:
                    m.result["still"] = False
            return
        if kind == "-mustrecharge":
            side, idx, m = self._mon(a[0])
            m.vol["recharge"] = True
            return
        if kind == "move":
            z_name, was_z = None, False
            if self._zpower is not None and self._zpower == self._mon(a[0])[:2] and not any(x.startswith("[from]") for x in a[3:]):
                was_z = True


                self._zpower = None
                if a[1].startswith("Z-"):
                    a = [a[0], a[1][2:], *a[2:]]
                else:
                    z_name = a[1]
            if any(x in ("[from] ability: Magic Bounce", "[from] move: Magic Coat") for x in a[3:]):
                self._reflector = self._mon(a[0])[:2]
                if self._last_move and self.mons[self._last_move[0]][self._last_move[1]].result is not None:
                    self.mons[self._last_move[0]][self._last_move[1]].result["miss"] = True
                return
            self._reflector = None
            side, idx, m = self._mon(a[0])
            dance = self._dance == (side, idx)
            self._dance = None



            choice_fail = dance and "[still]" in a[3:] and not (len(a) > 2 and a[2]) and "[from] ability: Dancer" not in a[3:]
            if dance and "[from] ability: Dancer" not in a[3:]:
                a = [*a, "[from] ability: Dancer"]

            was_max = a[1].startswith(("Max ", "G-Max "))
            mid = ve.lookup("zmove" if z_name is not None or was_max else "move", a[1])


            max_base = self._max_base(side, m, a[1], mid) if was_max else 0
            self.battle_last_move = max_base if was_max else mid
            self.battle_last_move_z = was_z
            if self.history and self.history[-1] == (EV_MOVE, (side, idx), None, 0, -1) and m.status == "slp"                     and not any(x.startswith("[from]") for x in a[3:]):


                self.history.pop()
            self._metronome(m, mid, a)


            reveal = 0 if was_max else (mid if z_name is None else ve.z_base_move(mid))
            if not any(x.startswith("[from]") for x in a[3:]):
                m.move_turn = self.turn
                if (not self.open_sheets and side == self.foe and reveal and reveal != STRUGGLE
                        and reveal not in m.moves and 0 in m.moves):

                    k = m.moves.index(0)
                    m.moves[k] = reveal
                    m.pp[k] = min(5, ve.max_pp(reveal, m.fmt)) if "transform" in m.vol else ve.max_pp(reveal, m.fmt)
                    if z_name is None:
                        m.move_names[reveal] = a[1]
            if (not any(x.startswith("[from]") for x in a[3:]) and len(a) > 2 and len(a[2].split(": ", 1)[0]) == 3 and a[2][:2] in (self.me, self.foe)
                    and mid and ve.move_choice_target(mid) != "none"):
                m.last_move_target = self._slot(a[2]) + (2 if a[2][:2] == side else 0)
            if not dance:
                m.moved = True
                m.acted = True
            m.vol.pop("glaiverush", None)
            m.vol.pop("destinybond", None)
            if to_id(a[1]) == "minimize":
                m.vol["minimize"] = True
            if to_id(a[1]) == "naturalgift" and self.format_index == 1 and not any(x.startswith("[from]") for x in a[3:]):
                m.item = 0
                m.vol["item_consumed"] = True
            if m.status in ("slp", "frz") and not any(x.startswith("[from]") for x in a[3:]):
                m.status_tries += 1
            if dance or not any(x.startswith("[from]") and x != "[from] lockedmove" for x in a[3:]):

                m.result = {"fail": "[notarget]" in a[3:], "miss": False, "hit": False, "null": False,
                            "still": "[still]" in a[3:] and not (len(a) > 2 and a[2])}
                m.result_turn = self.turn
                if "[from] lockedmove" not in a[3:] and not dance:
                    m.used[mid] = m.used.get(mid, 0) + 1
            if to_id(a[1]) == "wish" and m.slot is not None and self.side[side]["wish"][m.slot][0] != self.turn - 1:


                mx = m.stats[0] if m.stats else ve.set_stats(m.sheet, m.species, m.fmt)[0]
                self.side[side]["wish"][m.slot] = (self.turn, max(1, mx // 2))


            if side == self.me and mid and mid in m.moves and not any(x.startswith("[from]") for x in a[3:]) and "charging" not in m.vol:
                self._deduct_pp(side, m, mid, a[2] if len(a) > 2 else "")
            elif side == self.me and was_max and not any(x.startswith("[from]") for x in a[3:]) and m.slot is not None:
                k = self._max_slot(m, a[1])
                if k is not None:
                    tgt = a[2] if len(a) > 2 else ""
                    foe = self.foe if side == self.me else self.me
                    extra = 0
                    if tgt.startswith(foe) and to_id(a[1]) != "maxguard":
                        o = self._mon(tgt)[2]
                        extra = int(o.slot is not None and not o.fainted and o.ability == PRESSURE)
                    m.pp[k] = max(0, m.pp[k] - 1 - extra)
            elif side == self.me and z_name is not None:


                base = next((x for x in m.moves if x and ve.z_move_of(m.item, m.species, x, m.fmt) == mid), 0)
                if base:
                    self._deduct_pp(side, m, base, a[2] if len(a) > 2 else "")
            if "charging" in m.vol and "[still]" not in a[3:]:
                m.vol.pop("charging")
                cp = m.vol.pop("charge_pressure", None)
                tgt = a[2] if len(a) > 2 else ""
                foe = self.foe if side == self.me else self.me
                if cp and mid in m.moves and ve.move_target(mid) == "normal" and tgt.startswith(foe) and len(tgt.split(": ", 1)[0]) == 3:
                    if cp.get(ord(tgt[2]) - ord("a")):
                        k = m.moves.index(mid)
                        m.pp[k] = max(0, m.pp[k] - 1)
            mv = to_id(a[1])


            self._rampage = None
            if (mv in RAMPAGE_MOVES or mv in ROLLOUT_MOVES) and not dance:
                prev = m.vol.pop("lockedmove", None) if mv in RAMPAGE_MOVES else None


                self._rampage = (side, idx, mid, "[from] lockedmove" in a[3:], mv, prev[1] if prev else 0, bool(m.vol.get("confusion")))


            called = any(x.startswith("[from]") and x != "[from] lockedmove" for x in a[3:])
            if mv in STALL_MOVES and not called:

                m.protect_streak = m.protect_streak + 1 if m.vol.get("protect") else 1
                m.vol["protect"] = True
                m.stall_turn = self.turn
            if m.item in CHOICE_ITEMS and not self.magic_room:
                m.vol.setdefault("choicelock", mid)
            if choice_fail:
                self._event(EV_MOVE, (side, idx), None, 0, outcome=-1)
                self._last_move = None
                return
            if dance:

                self._event(EV_MOVE, (side, idx), None, mid, outcome=1)
                self._last_move = (side, idx, mid, len(self.history) - 1, a[0][:3])
                return
            if called:
                return
            if mv in ("futuresight", "doomdesire"):
                self._future_target = a[2] if len(a) > 2 else ""
            m.last_move = max_base if was_max else mid
            m.last_move_z = was_z
            m.last_move_max = was_max
            self._event(EV_MOVE, (side, idx), None, mid, outcome=1)
            self._last_move = (side, idx, mid, len(self.history) - 1, a[0][:3])
            return
        if kind == "cant" and len(a) > 1 and a[1] == "Shell Trap":

            m = self._mon(a[0])[2]
            if m.result is not None:
                m.result.update(null=True)
            return
        if kind == "cant":
            if any(x.startswith("[of]") for x in a[2:]):


                return
            side, idx, m = self._mon(a[0])
            dance = self._dance == (side, idx)
            self._dance = None
            if not dance:
                m.acted = True
            m.vol.pop("glaiverush", None)
            m.vol.pop("destinybond", None)
            if a[1] in ("slp", "frz"):
                m.status_tries += 1

            m.result = {"fail": a[1] != "recharge", "miss": False, "hit": False, "null": a[1] == "recharge", "still": False}
            m.result_turn = self.turn
            if a[1] == "recharge":
                m.vol.pop("recharge", None)
            m.vol.pop("charging", None)
            self._event(EV_MOVE, (side, idx), None, 0, outcome=-1)
            self._last_move = None
            return
        if kind == "-block" and len(a) > 1 and a[1] == "item: Ability Shield" and self._mon(a[0])[2].ability == TRACE:
            self._mon(a[0])[2].vol["trace_blocked"] = True
        if kind in ("-miss", "-immune", "-block"):
            user = self.mons[self._last_move[0]][self._last_move[1]] if self._last_move else None

            if user is not None and user.result is not None and self._last_move[2] != PERISH_SONG:
                user.result["miss"] = True
            return
        if kind == "-fieldactivate" and a[0] == "move: Fairy Lock":
            self.fairy_lock_turn = self.turn
            return
        if kind == "-fail":
            if self._last_move:
                side, idx = self._last_move[:2]
                if self._last_move[2] in STALL_IDS:


                    self.mons[side][idx].vol["protect"] = False
                    self.mons[side][idx].protect_streak = 0



                extra = [x for x in a[1:] if not x.startswith("[")]
                if self.mons[side][idx].result is not None and extra in (["move: Double Shock"], ["move: Burn Up"]):
                    self.mons[side][idx].result["null"] = True
                elif self.mons[side][idx].result is not None and all(x.startswith("move: ") or x in STATUSES or x == "heal" for x in extra):
                    self.mons[side][idx].result["fail"] = True

            return

    def _gas_holder(self, exclude=None):

        for sd in (self.me, self.foe):
            for i, o in enumerate(self.mons[sd]):
                if ((sd, i) != exclude and o.slot is not None and not o.fainted and o.ability == NEUTRALIZING_GAS
                        and "transform" not in o.vol and "ngas_ended" not in o.vol):
                    return (sd, i)
        return None

    @staticmethod
    def _suppress(m: MonState) -> None:

        if m.ability and m.ability != NEUTRALIZING_GAS and m.ability not in CANT_SUPPRESS and "ngas" not in m.vol and not m.vol.get("commanding"):
            m.vol["ngas"], m.ability = m.ability, 0

    def _release_gas(self) -> None:
        for sd in (self.me, self.foe):
            for o in self.mons[sd]:
                if "ngas" in o.vol:
                    o.ability = o.vol.pop("ngas")

    def _set_healing_wish(self, side: str, slot: int, on: bool) -> None:
        self.side[side]["healing_wish_slots"][slot] = on
        self.side[side]["healing_wish"] = any(self.side[side]["healing_wish_slots"])

    @staticmethod
    def _real_ability(m: MonState) -> int:
        return m.vol["gastroacid"] if "gastroacid" in m.vol else m.vol["ngas"] if "ngas" in m.vol else m.ability

    @staticmethod
    def _set_ability(m: MonState, ability: int) -> None:

        if "gastroacid" in m.vol:
            m.vol["gastroacid"] = ability
        elif "ngas" in m.vol and ability not in CANT_SUPPRESS and ability != NEUTRALIZING_GAS:
            m.vol["ngas"] = ability
        else:
            m.vol.pop("ngas", None)
            m.ability = ability

    def _raw(self, side: str, m: MonState) -> list:

        if "raw" in m.vol:
            return list(m.vol["raw"])
        if side == self.me and m.stats:
            return list(m.stats[1:])
        return list(ve.set_stats(m.sheet, m.species, m.fmt))[1:]

    @staticmethod
    def _take_over(real: MonState, shown: MonState | None, slot: int) -> None:


        real.slot, real.brought = slot, True
        if shown is None:
            return
        real.hp, real.status, real.toxic_stage, real.fainted = shown.hp, shown.status, shown.toxic_stage, shown.fainted
        real.boosts, real.vol, real.turns_active = shown.boosts, shown.vol, shown.turns_active
        if shown.tera and not real.tera and shown.vol.get("tera_logged"):

            real.tera, real.tera_shown, real.stellar_spent = True, shown.tera_shown, shown.stellar_spent
            real.tera_types()
            shown.tera, shown.stellar_spent = False, 0
        if shown.tera_shown and not shown.tera:
            shown.tera_shown = 0
            shown.types = shown.live_types()
        if shown.moved and real.item in CHOICE_ITEMS:
            real.vol["choicelock"] = True
        if shown.before_switch_in is not None:
            shown.hp, shown.status, shown.toxic_stage, shown.fainted, item = shown.before_switch_in
            if shown.item != item:
                real.item, shown.item = shown.item, item
        shown.slot, shown.boosts, shown.vol = None, [0] * 7, {}

    def shadow_tagged(self, slot: int) -> bool:


        m = next((o for o in self.mons[self.me] if o.slot == slot), None)
        if m is None or m.fainted or self._type_id("Ghost") in m.types:
            return False
        grounded = (self.gravity > 0 or m.item == IRON_BALL or "smackdown" in m.vol
                    or not (self._type_id("Flying") in m.types or m.ability == LEVITATE or m.item == AIR_BALLOON
                            or "magnetrise" in m.vol or "telekinesis" in m.vol))
        steel = self._type_id("Steel") in m.types
        return any(o.slot is not None and not o.fainted and ((o.ability == SHADOW_TAG and m.ability != SHADOW_TAG)
                                                              or (o.ability == ARENA_TRAP and grounded)
                                                              or (o.ability == MAGNET_PULL and steel))
                   for o in self.mons[self.foe])

    def imprisoned(self) -> set:

        return {mv for o in self.mons[self.foe] if o.slot is not None and not o.fainted and o.vol.get("imprison") for mv in o.moves if mv}

    def _hit(self, side: str, idx: int, ident: str, into_sub: bool = False) -> None:

        if self._future_hit is not None and not self._last_move:
            if (side, idx) != self._future_hit and not into_sub:
                self.mons[side][idx].times_attacked += 1
            return
        if self._last_move:
            user = self.mons[self._last_move[0]][self._last_move[1]]
            if user.result is not None:
                user.result["hit"] = True

            tgt = self.mons[side][idx]
            if (tgt.vol.get("shelltrap") == 1 and side != self._last_move[0] and not into_sub and self._last_move[2]
                    and ve.move_category(self._last_move[2]) == "physical"):
                tgt.vol["shelltrap"] = 3
            if (side, idx) != tuple(self._last_move[:2]) and not into_sub:
                self.mons[side][idx].times_attacked += 1
        if self._rampage is not None and (side, idx) != self._rampage[:2]:
            rs, ri, rmid, cont, rmv, prev_true, confused = self._rampage
            if rmv in ROLLOUT_MOVES:
                self.mons[rs][ri].vol["rollout"] = self.turn
            elif not cont:

                self.mons[rs][ri].vol["lockedmove"] = (rmid, 0, self.turn)
            elif prev_true != 1 and not confused:



                self.mons[rs][ri].vol["lockedmove"] = (rmid, 1, self.turn)
        if self._last_move and self._last_move[2] == GLAIVE_RUSH:
            self.mons[self._last_move[0]][self._last_move[1]].vol["glaiverush"] = True
        if self._last_move and self._last_move[3] is not None:
            ev = self.history[self._last_move[3]]

            if ev[2] is None and ident[:3] != self._last_move[4]:
                self.history[self._last_move[3]] = (ev[0], ev[1], (side, idx), ev[3], ev[4])

    def _max_slot(self, m: MonState, name: str):

        if m.slot is None:
            return None
        act = (self._move_request or {}).get("active") or []
        maxes = ((act[m.slot].get("maxMoves") or {}).get("maxMoves") or []) if m.slot < len(act) else []
        hits = [i for i, x in enumerate(maxes) if to_id(x.get("move", "")) == to_id(name) and i < 4 and m.moves[i]]
        chosen = self._my_choice[m.slot]
        return chosen if chosen in hits else (hits[0] if hits else None)

    def _max_base(self, side: str, m: MonState, name: str, mid: int) -> int:


        if side == self.me:
            k = self._max_slot(m, name)
            return m.moves[k] if k is not None else 0
        status = to_id(name) == "maxguard"
        cands = [x for x in m.moves if x and (ve.move_category(x) == "status") == status and (status or move_type(x) == move_type(mid))]

        return cands[0] if len(cands) == 1 and 0 not in m.moves else 0

    def _deduct_pp(self, side: str, m: MonState, mid: int, target: str) -> None:




        k = m.moves.index(mid)
        foe = self.foe if side == self.me else self.me
        pressure = lambda o: o.slot is not None and not o.fainted and o.ability == PRESSURE
        tgt = ve.move_target(mid)
        if tgt == "all" or mid in MUST_PRESSURE:
            extra = sum(pressure(o) for o in self.mons[foe])
        elif tgt in ("alladjacent", "alladjacentfoes"):
            extra = sum(pressure(o) for o in self.mons[foe])
        elif tgt == "normal" and target.startswith(foe):
            extra = int(pressure(self._mon(target)[2]))
        else:
            extra = 0
        m.pp[k] = max(0, m.pp[k] - 1 - extra)

    def _type_id(self, name: str) -> int:

        order = ["Bug", "Dark", "Dragon", "Electric", "Fairy", "Fighting", "Fire", "Flying", "Ghost", "Grass", "Ground", "Ice", "Normal",
                 "Poison", "Psychic", "Rock", "Steel", "Stellar", "Water"]
        return order.index(name) + 1 if name in order else 0

    def _setter(self, a: list[str]):
        of = next((x[5:] for x in a if x.startswith("[of] ")), None)
        if of:
            return self._mon(of)[2]
        return self._last_move_mon()

    def _last_move_mon(self):
        if self._last_move:
            return self.mons[self._last_move[0]][self._last_move[1]]
        return None

    def _metronome(self, m: MonState, mid: int, a: list) -> None:


        m.metronome_prev = m.metronome
        if m.item != METRONOME_ITEM or self.magic_room:
            m.metronome = None
            return
        if not any(x.startswith("[from]") and x != "[from] lockedmove" for x in a[3:]):
            r = m.result
            m.metronome_worked = (r is not None and m.result_turn == self.turn - 1
                                  and not ((r["fail"] or r["miss"] or r["still"]) and not r["hit"] and not r["null"]))
        last, count = m.metronome or (0, 0)
        if last == mid and m.metronome_worked:
            count = min(count + 1, 15)
        elif "charging" in m.vol and "[from] lockedmove" in a[3:]:
            count = 1 if last != mid else min(count + 1, 15)
        else:
            count = 0
        m.metronome = (mid, count)

    def _event(self, kind: int, actor, target, subject: int, outcome: int = 0) -> None:
        self.history.append((kind, actor, target, subject, outcome))

    def _tick(self) -> None:

        if self.weather_turns > 0 and not self._weather_fresh:
            self.weather_turns -= 1
            if self.weather_turns == 0:
                self.weather = 0
        self._weather_fresh = False
        if self.terrain_turns > 0:
            self.terrain_turns -= 1
            if self.terrain_turns == 0:
                self.terrain = 0
        self.trick_room = max(0, self.trick_room - 1)
        self.gravity = max(0, self.gravity - 1)
        for s in self.side.values():
            for k in ("reflect", "lightscreen", "auroraveil", "tailwind", "safeguard"):
                s[k] = max(0, s[k] - 1)
            s["gmax_residual"] = [max(0, t - 1) for t in s["gmax_residual"]]


    def observe(self):

        f = np.zeros(ve.FIELD_FEATURES, np.float32)
        ids = np.zeros((ve.MON_TOKENS, ve.MON_IDS), np.int32)
        feats = np.zeros((ve.MON_TOKENS, ve.MON_FEATURES), np.float32)
        hist = np.zeros((ve.HISTORY_LEN, ve.EVENT_FIELDS), np.int32)
        suppressors = (ve.lookup("ability", "Cloud Nine"), ve.lookup("ability", "Air Lock"))
        cloud_nine = any(m.slot is not None and not m.fainted and m.ability in suppressors for s in self.mons.values() for m in s)
        w = 0 if cloud_nine else self.weather
        f[F_WEATHER + w] = 1
        if w:
            f[F_WEATHER_TURNS] = self.weather_turns / 8
        f[F_TERRAIN + self.terrain] = 1
        f[F_TERRAIN_TURNS] = self.terrain_turns / 8
        f[F_TR] = self.trick_room / 5
        f[F_GRAVITY] = self.gravity / 5
        f[F_TURN] = min(self.turn, 30) / 30
        for side, base in ((self.me, F_MY_SIDE), (self.foe, F_FOE_SIDE)):
            s = self.side[side]
            f[base:base + 6] = [s["reflect"] / 8, s["lightscreen"] / 8, s["auroraveil"] / 8, s["tailwind"] / 4, s["mega_used"], s["healing_wish"]]
        if ve.FIELD_FEATURES > F_FOE_Z_USED:
            f[F_MY_Z_USED] = self.side[self.me]["z_used"]
            f[F_FOE_Z_USED] = self.side[self.foe]["z_used"]
        if ve.FIELD_FEATURES > F_FOE_TERA_USED:
            f[F_MY_TERA_USED] = self.side[self.me]["tera_used"]
            f[F_FOE_TERA_USED] = self.side[self.foe]["tera_used"]
        if ve.FIELD_FEATURES > F_FOE_GMAX_RESIDUAL:
            f[F_MY_DYNAMAX_USED] = self.side[self.me]["dynamax_used"]
            f[F_FOE_DYNAMAX_USED] = self.side[self.foe]["dynamax_used"]
            f[F_MY_GMAX_RESIDUAL] = max(self.side[self.me]["gmax_residual"]) / 4
            f[F_FOE_GMAX_RESIDUAL] = max(self.side[self.foe]["gmax_residual"]) / 4
        decision = 0
        if not self.over:
            if self.request and self.request.get("forceSwitch"):
                decision = 1
            elif self.request is None:
                decision = 2
        f[F_DECISION + decision] = 1
        if self.format_index < 4 or ve.FIELD_FEATURES <= F_FORMAT2:
            f[F_FORMAT + min(self.format_index, 3)] = 1
        else:
            f[F_FORMAT2 + min(self.format_index - 4, 3)] = 1
        for side, base in ((self.me, 0), (self.foe, ve.ROSTER_SIZE)):
            for r, m in enumerate(self.mons[side]):
                self._encode_mon(side, m, ids[base + r], feats[base + r])
        rows = self.history[-ve.HISTORY_LEN:]
        start = ve.HISTORY_LEN - len(rows)
        for k, (kind, actor, target, subject, outcome) in enumerate(rows):
            hist[start + k] = [kind, self._token(actor), self._token(target), subject if kind == EV_MOVE else 0,
                               subject if kind == EV_SWITCH else outcome]
        return f, ids, feats, hist

    def _can_gimmick(self, side: str, m: MonState, known: bool) -> bool:


        if not known:
            return False
        s = self.side[side]
        own_species = m.vol["transform"][0] if "transform" in m.vol else m.species
        ultra = m.item == ULTRANECROZIUM and own_species in NECROZMA_FUSED
        if not s["ultra_used" if ultra else "mega_used"] and not m.mega and _mega_forme(m) != 0:
            return True
        if (not s["z_used"] and Z_CAPABLE is not None and m.item != 0
                and Z_CAPABLE(m.item, m.species, [x for x in m.moves if x], m.fmt)):
            return True


        if (self.format_index in TERA_FORMATS and not s["tera_used"] and not m.tera and m.tera_type != 0
                and not ("transform" in m.vol and m.species in REQUIRED_TERA) and _mega_forme(m) == 0):
            return True



        disguise = self.mons[side][self.shown[side][m.slot]] if m.slot is not None and self.shown[side][m.slot] is not None else m
        return (self.format_index in DYNAMAX_FORMATS and not s["dynamax_used"] and "dynamax" not in m.vol
                and m.species not in CANNOT_DYNAMAX and disguise.species not in CANNOT_DYNAMAX)

    def _token(self, who) -> int:
        if who is None:
            return -1
        side, idx = who
        return idx if side == self.me else ve.ROSTER_SIZE + idx

    def _encode_mon(self, side: str, m: MonState, ids: np.ndarray, f: np.ndarray) -> None:
        mine = side == self.me
        f[M_IS_MINE] = mine
        live = m.brought
        known = mine or self.open_sheets
        item, ability = (m.item, m.ability) if known else (0, 0)

        holds = m.item != 0 and (known or self.format_index not in PREVIEW_HIDES_ITEMS)
        if not self.open_sheets and "transform" in m.vol:
            ability = 0
        row = [m.species, item, ability, *m.moves, *m.types]
        if ve.MON_IDS > I_TERA_TYPE:
            row.append(m.tera_type if known and self.format_index in TERA_FORMATS else 0)
        if not live:
            ids[:] = row
            f[M_HP] = 1.0
            f[M_STATUS] = 1.0
            f[M_HOLDS_ITEM] = holds
            f[M_CAN_MEGA] = self._can_gimmick(side, m, known)
            return
        ids[:] = row
        f[M_IN_BATTLE] = 1
        if m.slot == 0:
            f[M_ACTIVE_A] = 1
        if m.slot == 1:
            f[M_ACTIVE_B] = 1
        f[M_FAINTED] = m.fainted
        f[M_HP] = 0.0 if m.fainted else m.hp
        f[M_STATUS + STATUSES.get(m.status, 0)] = 1
        if m.status == "tox":
            f[M_TOXIC] = m.toxic_stage / 15
        f[M_BOOSTS:M_BOOSTS + 7] = [b / 6 for b in m.boosts]
        f[M_MEGA] = m.mega
        f[M_CAN_MEGA] = self._can_gimmick(side, m, known)
        if ve.MON_FEATURES > M_COMMANDING:
            src = self.mons[side][m.vol["illusion_holder"]] if "illusion_holder" in m.vol else m
            f[M_TERASTALLIZED] = src.tera
            if src.tera and src.tera_shown == STELLAR:
                spent = bin(src.stellar_spent & ~(1 << STELLAR)).count("1")
                f[M_STELLAR_LEFT] = 1.0 if src.species == TERAPAGOS_STELLAR else (18 - spent) / 18
            f[M_COMMANDING] = bool(m.vol.get("commanding")) and not m.fainted
        if ve.MON_FEATURES > M_CHI_STRIKE and self.format_index in DYNAMAX_FORMATS:
            dynamaxed = "dynamax" in m.vol and not m.fainted
            if dynamaxed:
                f[M_DYNAMAX_TURNS] = max(0, 3 - m.vol["dynamax"]) / 3
            f[M_GIGANTAMAX] = m.gmax and (known or dynamaxed)
            if not m.fainted:
                f[M_CHI_STRIKE] = m.vol.get("chistrike", 0) / 3
        if m.slot is not None and not m.fainted:
            v = m.vol
            f[M_TURNS_ACTIVE] = min(m.turns_active, 5) / 5
            f[M_CONFUSED] = v.get("confusion", False)
            f[M_TAUNTED] = v.get("taunt", False)
            f[M_ENCORED] = v.get("encore", False)
            f[M_DISABLED] = v.get("disable", False)
            f[M_SUB] = v.get("substitute", False)
            f[M_PROTECT] = v.get("protect", False)
            f[M_PERISH] = v.get("perish", 0) / 4
            f[M_YAWN] = v.get("yawn", False)
            f[M_TRAPPED] = v.get("trapped", False)
            f[M_CHARGING] = v.get("charging", False)
            f[M_RECHARGE] = v.get("recharge", False)
            f[M_CHOICE] = known and bool(v.get("choicelock", False))
            f[M_THROAT_CHOP] = v.get("throatchop", False)
            f[M_HEAL_BLOCK] = v.get("healblock", False)
            f[M_STOCKPILE] = v.get("stockpile", 0) / 3
        f[M_HOLDS_ITEM] = holds
        if mine and m.stats:
            f[M_STATS] = m.stats[0] / 300
            if self.open_sheets or "transform" not in m.vol:
                f[M_STATS + 1:M_STATS + 6] = [s / 250 for s in m.stats[1:]]
            for k, mv in enumerate(m.moves):
                if mv:
                    f[M_PP + k] = m.pp[k] / max(1, ve.max_pp(mv, m.fmt))


def _request_move(move_id: str) -> int:

    return ve.lookup("move", "hiddenpower" if to_id(move_id).startswith("hiddenpower") else move_id)


def _mega_forme(m) -> int:



    species, moves = (m.vol["transform"][0], m.vol["transform"][1]) if "transform" in m.vol else (m.species, m.moves)
    moves = [x for x in moves if x]
    try:
        return ve.mega_forme(m.item, species, moves, m.fmt)
    except TypeError:
        if m.fmt is not None and not m.fmt.startswith(("gen6", "gen7")):
            moves = []
        try:
            return ve.mega_forme(m.item, species, moves)
        except TypeError:
            return ve.mega_forme(m.item, species)

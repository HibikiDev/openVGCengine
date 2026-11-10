


















from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEX = ROOT / "tools/corpus/out/dex-tables.json"
PRIORS = ROOT / "trainer/runs/set_prior"
MISMATCH = 0.01
FIT_WEIGHT = 1.0

USAGE_PER, USAGE_MAX = 50, 20.0

FORMAT_MOD = {None: "champions", "gen9championsvgc2026regmc": "champions", "gen9championsvgc2026regmcbo3": "champions",
              "gen5vgc2013": "gen5", "gen6vgc2014": "gen6", "gen6vgc2015": "gen6", "gen6vgc2016": "gen6",
              "gen7vgc2017": "gen7", "gen7vgc2018": "gen7", "gen7vgc2019": "gen7",
              "gen8vgc2020": "gen8", "gen8vgc2021": "gen8", "gen8vgc2022": "gen8",
              "gen9vgc2023regc": "gen9", "gen9vgc2023regd": "gen9", "gen9vgc2024regg": "gen9", "gen9vgc2025regi": "gen9"}

FORMAT_PRIOR = {"gen6vgc2016": "gen6vgc16", "gen7vgc2017": "gen7vgc17", "gen7vgc2018": "gen7vgc18", "gen7vgc2019": "gen7vgc19",
                "gen8vgc2020": "gen8vgc20", "gen8vgc2021": "gen8vgc21", "gen8vgc2022": "gen8vgc22",
                "gen9vgc2023regc": "gen9regc", "gen9vgc2023regd": "gen9regd", "gen9vgc2024regg": "gen9regg", "gen9vgc2025regi": "gen9regi"}
ITEM_GAIN = {"move: Thief", "move: Covet", "move: Bestow", "ability: Magician", "ability: Pickpocket"}
ITEM_SWAP = {"move: Trick", "move: Switcheroo", "ability: Pickup", "move: G-Max Replenish"}
CHOICE_ITEMS = {"choicescarf", "choiceband", "choicespecs"}



SPEED_UP = {"Chlorophyll": "SunnyDay", "Swift Swim": "RainDance", "Sand Rush": "Sandstorm", "Slush Rush": "Snow",
            "Surge Surfer": "Electric Terrain", "Unburden": None, "Quick Feet": None, "Protosynthesis": None, "Quark Drive": None}
LATE_ITEMS = {"ironball", "laggingtail", "fullincense"}
REORDER_MOVES = {"afteryou", "quash", "instruct", "pursuit", "grassyglide"}
ORDER_BREAKS = {"-boost", "-unboost", "-setboost", "-clearboost", "-clearallboost", "-clearnegativeboost", "-copyboost",
                "-invertboost", "-swapboost", "-transform", "-weather", "-status", "-curestatus", "-enditem", "-item",
                "detailschange", "-mega", "-formechange", "swap", "replace"}
ORDER_WORDS = ("Quick Claw", "Custap", "Quick Draw", "After You", "Quash", "Tailwind", "Trick Room", "Terrain")
ABILITY_SWAP_MOVES = {"skillswap", "roleplay", "entrainment", "simplebeam", "worryseed", "doodle", "transform"}

ABILITY_PASS = {"Mummy", "Lingering Aroma", "Wandering Spirit"}


def to_id(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def move_id(s: str) -> str:

    m = to_id(s)
    return "hiddenpower" if m.startswith("hiddenpower") else m


_DEX: dict | None = None


def dex() -> dict:
    global _DEX
    if _DEX is None:
        _DEX = json.loads(DEX.read_text(encoding="utf8"))
    return _DEX


def name(kind: str, ident: str) -> str:

    if kind == "moves" and ident == "hiddenpower":
        return "Hidden Power"
    return dex()["names"][kind].get(ident, ident) if ident else "(none)"




@dataclass
class MonFacts:
    species: str
    moves: list = field(default_factory=list)
    item: str | None = None
    holds: bool | None = None
    ability: str | None = None
    item_swapped: bool = False
    ability_swapped: bool = False
    ability_moved: bool = False
    transformed: bool = False


    not_items: set = field(default_factory=set)
    last_used: str | None = None
    item_gone: bool = False
    embargo: bool = False


    speed_item: str | None = None


    speed_lo: float = 0.0
    speed_hi: float = float("inf")

    hp_types: set | None = None

    def carried(self) -> "MonFacts":




        return MonFacts(species=self.species, moves=[] if self.transformed else list(self.moves),
                        item=None if self.item_swapped else self.item, holds=self.holds,
                        ability=None if self.ability_swapped else self.ability, not_items=set(self.not_items),
                        speed_item=self.speed_item, speed_lo=self.speed_lo, speed_hi=self.speed_hi,
                        hp_types=None if self.hp_types is None else set(self.hp_types))

    def absorb(self, prev: "MonFacts") -> None:

        self.moves += [m for m in prev.moves if m not in self.moves]
        if self.item is None and prev.item is not None and not self.item_swapped:
            self.item = prev.item
        if self.holds is None:
            self.holds = prev.holds
        if self.ability is None and prev.ability is not None and not self.ability_swapped:
            self.ability = prev.ability
        self.not_items |= prev.not_items
        self.speed_item = self.speed_item or prev.speed_item
        self.speed_lo, self.speed_hi = max(self.speed_lo, prev.speed_lo), min(self.speed_hi, prev.speed_hi)
        if prev.hp_types is not None:
            self.hp_types = set(prev.hp_types) if self.hp_types is None else self.hp_types & prev.hp_types


class Evidence:


    def __init__(self, fmt: str | None = None):
        self.mod = FORMAT_MOD.get(fmt, "champions")
        self.mons: dict[str, list[MonFacts]] = {"p1": [], "p2": []}
        self.nick: dict[str, int] = {}
        self.active: dict[str, int] = {}
        self.cur_species: dict[tuple, str] = {}
        self.last_move: tuple | None = None
        self.magic_room = False
        self.berry_eater: tuple | None = None


        self.known: dict | None = None
        self.turn_moves: list[tuple] = []
        self.order_ok = False
        self.spe_stage: dict[tuple, int | None] = {}
        self.status: dict[tuple, str] = {}
        self.tailwind = {"p1": False, "p2": False}
        self.trick_room = False
        self.weather = ""
        self.terrain = ""



        self.journal: dict[str, list[tuple]] = {}

        self.hp_pending: tuple | None = None


        self.hp_undo: tuple | None = None

        self.cur_types: dict[tuple, list[str]] = {}



        self.hp: dict[tuple, float] = {}
        self.cause: tuple | None = None
        self.sitrus: set = set()
        self.lo: list | None = None
        self.timed: dict = {}
        self.healblock: set = set()

    def know(self, side: str, items: list[str], abilities: list[str], speeds: list[int] | None = None) -> None:


        self.known = {"side": side, "items": [to_id(x or "") for x in items], "abilities": [to_id(x or "") for x in abilities],
                      "speeds": speeds}


    def _key(self, ident: str) -> tuple | None:
        if not ident or len(ident) < 4 or ident[:2] not in ("p1", "p2") or ": " not in ident:
            return None
        side, nick = ident[:2], ident.split(": ", 1)[1]
        slot = ident[:3] if len(ident.split(":")[0]) == 3 else None
        idx = self.active.get(slot) if slot else None
        if idx is None:
            idx = self.nick.get(f"{side}: {nick}")
        return (side, idx, slot) if idx is not None else None

    def _note(self, key: tuple, field_: str, value: str) -> None:
        if key[2]:
            self.journal.setdefault(key[2], []).append((field_, value, key[1]))

    def _mon(self, key: tuple | None) -> MonFacts | None:
        return self.mons[key[0]][key[1]] if key else None

    def _index_for(self, side: str, species: str) -> int | None:
        mons = self.mons[side]
        for i, m in enumerate(mons):
            if m.species == species:
                return i
        for i, m in enumerate(mons):
            if species.startswith(m.species) or m.species.startswith(species):
                return i
        return None

    def _set_item(self, key: tuple | None, item: str) -> None:
        m = self._mon(key)
        if m and not m.item_swapped and m.item is None and item:
            m.item = to_id(item)
            self._note(key, "item", m.item)

    def _set_ability(self, key: tuple | None, ability: str) -> None:
        m = self._mon(key)
        if m and not m.ability_swapped and m.ability is None and ability:
            m.ability = to_id(ability)
            self._note(key, "ability", m.ability)

    def _hidden_power(self, kind: str, a: list, frm: str | None) -> None:



        user, target = self.hp_pending
        on_target = bool(a) and target is not None and self._key(a[0]) is not None and self._key(a[0])[:2] == target[:2]
        if kind == "-crit" and on_target:
            return
        self.hp_pending = None
        if not on_target:
            return
        absorbed = HP_ABSORB.get(to_id(frm[9:])) if frm and frm.startswith("ability: ") else None
        if kind == "-start" and len(a) > 1 and to_id(a[1].replace("ability: ", "")) == "flashfire":
            absorbed = "fire"
        if absorbed is None and frm:
            return
        if absorbed is None:
            seen = {"-supereffective": "se", "-resisted": "res", "-immune": "imm", "-damage": "neutral"}.get(kind)
            if kind == "-activate" and len(a) > 1 and "Substitute" in a[1] and "[damage]" in a:
                seen = "neutral"
            if seen is None:
                return
        m = self._mon(user)
        types = self._types(target)
        if not m or not types:
            return
        fits = {absorbed} if absorbed else {t for t in HP_TYPES if hp_effect(t, types, self.mod) == seen}
        before = m.hp_types
        narrowed = (before if before is not None else set(HP_TYPES)) & fits
        if narrowed:
            m.hp_types = narrowed
            if not absorbed:
                self.hp_undo = (m, before, seen, a[0][:3])

    def _types(self, key: tuple) -> list[str]:

        if key[:2] in self.cur_types:
            return list(self.cur_types[key[:2]])
        species = self.cur_species.get(key[:2]) or (self._mon(key).species if self._mon(key) else None)
        return [t.lower() for t in dex()["species"].get(self.mod, {}).get(species, {}).get("types", [])]

    def _learns(self, species: str, mid: str, base: str) -> bool:

        pools = dex()["movepools"][self.mod]
        if mid == "hiddenpower" or (species not in pools and base not in pools):
            return True
        return mid in pools.get(species, ()) or mid in pools.get(base, ())


    def _speed_state(self, kind: str, a: list) -> None:


        if kind == "turn":
            self.turn_moves, self.order_ok = [], True
            return
        joined = "|".join(a)
        if kind in ORDER_BREAKS or (kind in ("-activate", "-sidestart", "-sideend", "-fieldstart", "-fieldend")
                                    and any(x in joined for x in ORDER_WORDS)):
            self.order_ok = False
        key = self._key(a[0]) if a else None
        k2 = key[:2] if key else None
        if kind in ("-boost", "-unboost") and len(a) >= 3 and a[1] == "spe" and k2 in self.spe_stage:
            if self.spe_stage[k2] is not None:
                n = int(a[2]) if a[2].lstrip("-").isdigit() else 0
                self.spe_stage[k2] = max(-6, min(6, self.spe_stage[k2] + (n if kind == "-boost" else -n)))
        elif kind == "-setboost" and len(a) >= 3 and a[1] == "spe" and k2:
            self.spe_stage[k2] = int(a[2]) if a[2].lstrip("-").isdigit() else None
        elif kind == "-clearboost" and k2:
            self.spe_stage[k2] = 0
        elif kind == "-clearallboost":
            self.spe_stage = {k: (0 if v is not None else None) for k, v in self.spe_stage.items()}
        elif kind == "-clearnegativeboost" and k2 and self.spe_stage.get(k2) is not None:
            self.spe_stage[k2] = max(0, self.spe_stage[k2])
        elif kind in ("-copyboost", "-invertboost", "-swapboost", "-transform") and k2:
            self.spe_stage[k2] = None
            other = self._key(a[1]) if len(a) > 1 else None
            if kind != "-transform" and other:
                self.spe_stage[other[:2]] = None
        elif kind == "-status" and len(a) >= 2 and k2:
            self.status[k2] = a[1]
        elif kind == "-curestatus" and k2:
            self.status[k2] = ""
        elif kind in ("-sidestart", "-sideend") and len(a) >= 2 and a[1].endswith("Tailwind"):
            self.tailwind[a[0][:2]] = kind == "-sidestart"
        elif kind in ("-fieldstart", "-fieldend") and a and a[0].endswith("Trick Room"):
            self.trick_room = kind == "-fieldstart"
        elif kind in ("-fieldstart", "-fieldend") and a and a[0].endswith("Terrain"):
            self.terrain = a[0].replace("move: ", "") if kind == "-fieldstart" else ""
        elif kind == "-weather" and a:
            self.weather = "" if a[0] == "none" else a[0]

    def _speed_range(self, k: tuple) -> tuple[int, int] | None:

        table = dex()["species"][self.mod]
        sp = table.get(self.cur_species.get(k[:2], "")) or table.get(self._mon(k).species)
        if not sp:
            return None
        b = sp["bs"]["spe"]
        hi = int((((2 * b + 31 + 63) // 2) + 5) * 1.1)
        lo = int((((2 * b + (31 if self.mod == "champions" else 0)) // 2) + 5) * 0.9)
        return lo, hi

    def _known_mult(self, k: tuple, can_quick_feet: bool) -> float | None:
        st = self.spe_stage.get(k[:2], 0)
        if st is None:
            return None
        m = (2 + st) / 2 if st >= 0 else 2 / (2 - st)
        if self.status.get(k[:2]) == "par":
            if can_quick_feet:
                return None
            m *= 0.25 if self.mod in ("gen5", "gen6") else 0.5
        if self.tailwind[k[0]]:
            m *= 2
        return m

    def _priority(self, mid: str, abilities: list[str]) -> int | None:

        mv = dex()["moves"][self.mod].get(mid)
        if not mv:
            return None
        ab = set(abilities)
        if mv["cat"] == "Status" and ab & {"Prankster", "Mycelium Might"}:
            return None
        if mv["type"] == "Flying" and "Gale Wings" in ab:
            return None
        if mv.get("heal") and "Triage" in ab:
            return None
        if ab & {"Stall", "Quick Draw"}:
            return None
        return mv["pri"]

    def _speed_pair(self, k1: tuple, mid1: str, k2: tuple, mid2: str) -> None:


        kn = self.known
        if kn is None or self.trick_room or k1[0] == kn["side"] or k2[0] != kn["side"]:
            return
        m1 = self._mon(k1)
        if m1.ability_moved or self._mon(k2).ability_moved:
            return
        if m1.speed_item or m1.item_gone or m1.item_swapped or "choicescarf" in m1.not_items or self.magic_room or m1.embargo:
            return
        if m1.item is not None and m1.item != "choicescarf":
            return
        legal = dex()["abilities"][self.mod]
        legal1 = legal.get(self.cur_species.get(k1[:2], "")) or legal.get(m1.species) or []
        poss1 = [x for x in legal1 if m1.ability is None or to_id(x) == m1.ability]
        for ab in poss1:
            if ab in SPEED_UP and (SPEED_UP[ab] is None or SPEED_UP[ab] in (self.weather, self.terrain)):
                return
        i2 = k2[1]
        item2 = kn["items"][i2] if i2 < len(kn["items"]) else ""
        ab2 = kn["abilities"][i2] if i2 < len(kn["abilities"]) else ""
        if item2 in LATE_ITEMS or ab2 in ("stall", "myceliummight"):
            return
        p1 = self._priority(mid1, poss1)
        p2 = self._priority(mid2, [dex()["names"]["abilities"].get(ab2, ab2)])
        if p1 is None or p2 is None or p1 != p2:
            return
        r1, r2 = self._speed_range(k1), self._speed_range(k2)
        mult1 = self._known_mult(k1, "Quick Feet" in poss1)
        mult2 = self._known_mult(k2, ab2 == "quickfeet")
        if r1 is None or r2 is None or mult1 is None or mult2 is None:
            return
        exact = kn.get("speeds") and i2 < len(kn["speeds"]) and kn["speeds"][i2]
        sp2 = kn["speeds"][i2] if exact else r2[0]
        if item2 == "choicescarf":
            sp2 = int(sp2 * 1.5)
        if r1[1] * mult1 < sp2 * mult2:
            m1.speed_item = "choicescarf"
            self._note(k1, "speed_item", "choicescarf")

    def _speed_bounds(self, k1: tuple, mid1: str, k2: tuple, mid2: str) -> None:



        kn = self.known
        if kn is None or self.trick_room or self.magic_room or k1[0] == k2[0]:
            return
        first_unknown = k1[0] != kn["side"]
        ku, kk, mid_u, mid_k = (k1, k2, mid1, mid2) if first_unknown else (k2, k1, mid2, mid1)
        mu = self._mon(ku)
        if mu.transformed or mu.embargo or mu.ability_moved or self._mon(kk).ability_moved:
            return
        legal = dex()["abilities"][self.mod]
        legal_u = legal.get(self.cur_species.get(ku[:2], "")) or legal.get(mu.species) or []
        poss = [x for x in legal_u if mu.ability is None or to_id(x) == mu.ability]
        if "Stall" in poss or "Quick Draw" in poss:
            return
        if first_unknown and any(ab in SPEED_UP and (SPEED_UP[ab] is None or SPEED_UP[ab] in (self.weather, self.terrain))
                                 for ab in poss):
            return
        i = kk[1]
        item_k = kn["items"][i] if i < len(kn["items"]) else ""
        ab_k = kn["abilities"][i] if i < len(kn["abilities"]) else ""
        if item_k in LATE_ITEMS or ab_k in ("stall", "myceliummight", "quickdraw"):
            return
        pu = self._priority(mid_u, poss)
        pk = self._priority(mid_k, [dex()["names"]["abilities"].get(ab_k, ab_k)])
        if pu is None or pk is None or pu != pk:
            return
        mult_u = self._known_mult(ku, "Quick Feet" in poss)
        mult_k = self._known_mult(kk, ab_k == "quickfeet")
        boost_k = self._known_ability_speed(kk, ab_k)
        r_k = self._speed_range(kk)
        if mult_u is None or mult_k is None or r_k is None or boost_k is None:
            return
        mult_k *= boost_k
        exact = kn.get("speeds") and i < len(kn["speeds"]) and kn["speeds"][i]
        scarf = 1.5 if item_k == "choicescarf" else 1.0
        if first_unknown:
            sp = (kn["speeds"][i] if exact else r_k[0]) * scarf
            mu.speed_lo = max(mu.speed_lo, sp * mult_k / mult_u)
        else:
            sp = (kn["speeds"][i] if exact else r_k[1]) * scarf
            mu.speed_hi = min(mu.speed_hi, sp * mult_k / mult_u)

    def _known_ability_speed(self, k: tuple, ability: str) -> float | None:


        m = self._mon(k)
        if ability == "unburden":
            return 2.0 if m.item_gone else 1.0
        if ability in ("protosynthesis", "quarkdrive"):
            return None
        if ability == "quickfeet":
            return 1.5 if self.status.get(k[:2]) else 1.0
        cond = {"chlorophyll": "SunnyDay", "swiftswim": "RainDance", "sandrush": "Sandstorm", "slushrush": "Snow",
                "surgesurfer": "Electric Terrain"}.get(ability)
        if cond:
            return 2.0 if cond in (self.weather, self.terrain) or (cond == "Snow" and self.weather == "Hail") else 1.0
        return 1.0

    def _rule_out_items(self, m: MonFacts, mid: str, key: tuple) -> None:

        legal = dex()["abilities"][self.mod].get(m.species) or []
        if (m.item_gone or m.item_swapped or self.magic_room or m.embargo
                or ("Klutz" in legal and m.ability in (None, "klutz"))):
            m.last_used = mid
            return
        out = set()
        if m.last_used and mid != m.last_used:
            out |= CHOICE_ITEMS
        mv = dex()["moves"][self.mod].get(mid)
        if mv and mv["cat"] == "Status":
            out.add("assaultvest")
        for x in out - m.not_items:
            m.not_items.add(x)
            self._note(key, "not_item", x)
        m.last_used = mid


    def _works(self, m: MonFacts) -> bool:

        legal = dex()["abilities"][self.mod].get(m.species) or []
        return not (m.item_gone or m.item_swapped or self.magic_room or m.embargo or ("Klutz" in legal and m.ability in (None, "klutz")))

    def _might_have(self, m: MonFacts, abilities: tuple) -> bool:

        legal = dex()["abilities"][self.mod].get(m.species) or []


        return any(x in legal and (m.ability is None or to_id(x).startswith(m.ability) or m.ability_swapped) for x in abilities)

    def _rule_out(self, key: tuple | None, item: str) -> None:
        m = self._mon(key)
        if m and m.item is None and self._works(m) and item not in m.not_items:
            m.not_items.add(item)
            self._note(key, "not_item", item)

    def _foe_cause(self, key: tuple | None) -> tuple | None:

        c = self.cause
        if key is None or c is None:
            return None
        if c[0] == "move" and c[1] is not None and c[1][0] != key[0]:
            return c
        if c[0] == "intimidate" and c[1] != key[0]:
            return c
        return None

    def _damaging(self, mid: str) -> bool:
        mv = dex()["moves"][self.mod].get(mid)
        return bool(mv) and mv["cat"] != "Status"

    def _resolve(self, kind: str) -> None:



        if kind in ("move", "turn"):
            self._resolve_sitrus()
        self._resolve_lo()

    def _resolve_sitrus(self) -> None:
        for k in self.sitrus:
            m = self.mons[k[0]][k[1]] if k[1] < len(self.mons[k[0]]) else None
            if m is None or not 0 < self.hp.get(k, 0) or k in self.healblock:
                continue
            foe = "p2" if k[0] == "p1" else "p1"
            unnerve = any(self._might_have(self.mons[foe][i], ("Unnerve", "As One (Glastrier)", "As One (Spectrier)"))
                          for s, i in self.active.items() if s[:2] == foe and i is not None and i < len(self.mons[foe]))
            if not unnerve:
                self._rule_out((k[0], k[1], None), "sitrusberry")
        self.sitrus = set()

    def _resolve_lo(self) -> None:
        if self.lo is not None:
            user, mid, hit = self.lo
            m = self._mon(user)
            if (hit and m and self.hp.get(user[:2], 0) > 0 and mid not in ("dragontail", "circlethrow")
                    and not self._might_have(m, ("Magic Guard", "Sheer Force"))):
                self._rule_out(user, "lifeorb")
            self.lo = None

    @staticmethod
    def _pct(hp: str) -> float | None:

        import re
        s = hp.split(" ")[0]
        if s == "0":
            return 0.0
        m = re.match(r"(\d+)/(\d+)", s)
        if not m:
            return None
        cur, mx = float(m.group(1)), float(m.group(2))
        return cur / mx if mx else None

    def _rules(self, kind: str, a: list, frm: str | None, of: tuple | None) -> None:







        if kind == "replace" and a:


            shown = self.active.get(a[0][:3])
            if shown is not None:
                self.sitrus.discard((a[0][:2], shown))
                self.hp.pop((a[0][:2], shown), None)
                if self.lo is not None and self.lo[0] and self.lo[0][:2] == (a[0][:2], shown):
                    self.lo = None
        elif kind in ("move", "turn", "upkeep", "switch", "drag"):
            self._resolve(kind)
        if kind == "upkeep":
            for t in self.timed.values():
                t["ups"] += 1
                if t["ups"] == 5 and not t["done"]:
                    m = self._mon(t["setter"])
                    if m and self._works(m):
                        self._set_item(t["setter"], t["item"])
                    t["done"] = True
        if kind == "move" and len(a) >= 2 and not any(x.startswith("[from]") for x in a[2:]):
            key, mid = self._key(a[0]), move_id(a[1])
            self.cause = ("move", key, mid)
            self.lo = [key, mid, False] if key and self._damaging(mid) else None
            return
        if kind == "-ability" and len(a) >= 2:
            self.cause = ("intimidate", a[0][:2]) if a[1] == "Intimidate" and frm is None else None
            return
        if kind in ("-damage", "-heal", "-sethp") and len(a) >= 2:
            key = self._key(a[0])
            if key is None:
                return
            k, before, after = key[:2], self.hp.get(key[:2]), self._pct(a[1])
            if after is not None:
                self.hp[k] = after
            if kind != "-damage" or after is None:
                return
            if frm in ("Stealth Rock", "Spikes"):
                self._rule_out(key, "heavydutyboots")
            elif frm in ("Sandstorm", "hail", "Hail"):
                self._rule_out(key, "safetygoggles")
            elif frm is None and self._foe_cause(key) and self._foe_cause(key)[0] == "move":
                if before == 1.0 and after == 0.0:
                    self._rule_out(key, "focussash")
            if frm is None and self.lo is not None and self.cause and self.cause[0] == "move" and self.cause[1] == self.lo[0] \
                    and key[:2] != self.lo[0][:2]:
                self.lo[2] = True
            if 0 < after <= 0.49:
                self.sitrus.add(k)
            return
        if kind == "-status" and len(a) >= 2 and frm is None:
            key = self._key(a[0])
            c = self._foe_cause(key)
            if c and c[0] == "move":
                if c[2] in ("spore", "sleeppowder", "stunspore", "poisonpowder"):
                    self._rule_out(key, "safetygoggles")
                elif self._damaging(c[2]):
                    self._rule_out(key, "covertcloak")
            return
        if kind == "cant" and len(a) >= 2 and a[1] == "flinch":
            self._rule_out(self._key(a[0]), "covertcloak")
            self.cause = None
            return
        if kind == "-start" and len(a) >= 2:
            key = self._key(a[0])
            if a[1].endswith("Heal Block") and key:
                self.healblock.add(key[:2])
            elif a[1] == "confusion" and frm is None:
                c = self._foe_cause(key)
                if c and c[0] == "move" and self._damaging(c[2]):
                    self._rule_out(key, "covertcloak")
            return
        if kind == "-end" and len(a) >= 2 and a[1].endswith("Heal Block") and self._key(a[0]):
            self.healblock.discard(self._key(a[0])[:2])
            return
        if kind == "-unboost" and len(a) >= 2 and frm is None:
            key = self._key(a[0])
            c = self._foe_cause(key)
            if c:
                self._rule_out(key, "clearamulet")
                if c[0] == "move" and self._damaging(c[2]):
                    self._rule_out(key, "covertcloak")
            return

        setter = of if frm and frm.startswith("ability: ") else (self.cause[1] if self.cause and self.cause[0] == "move" else None)
        if kind == "-weather" and a and self.mod != "gen5":
            rock = {"RainDance": "Damp Rock", "SunnyDay": "Heat Rock", "Sandstorm": "Smooth Rock", "Hail": "Icy Rock",
                    "Snow": "Icy Rock", "Snowscape": "Icy Rock"}
            if "[upkeep]" in a:
                pass
            elif a[0] == "none":
                t = self.timed.pop("weather", None)
                if t and t["ups"] == 4 and not t["done"]:
                    self._rule_out(t["setter"], to_id(t["item"]))
            elif a[0] in rock and setter:
                self.timed["weather"] = {"setter": setter, "item": rock[a[0]], "ups": 0, "done": False}
            else:
                self.timed.pop("weather", None)
        elif kind == "-fieldstart" and a and a[0].endswith("Terrain") and self.mod != "gen5":
            self.timed["terrain"] = {"setter": setter, "item": "Terrain Extender", "ups": 0, "done": False} if setter else None
            if self.timed["terrain"] is None:
                self.timed.pop("terrain")
        elif kind == "-fieldend" and a and a[0].endswith("Terrain"):
            t = self.timed.pop("terrain", None)
            broke = self.cause and self.cause[0] == "move" and self.cause[2] in ("steelroller", "icespinner", "defog")
            if t and frm is None and not broke and t["ups"] == 4 and not t["done"]:
                self._rule_out(t["setter"], "terrainextender")
        elif kind == "-sidestart" and len(a) >= 2 and a[1].removeprefix("move: ") in ("Reflect", "Light Screen", "Aurora Veil"):
            if setter and setter[0] == a[0][:2]:
                self.timed[("screen", a[0][:2], a[1].removeprefix("move: "))] = {"setter": setter, "item": "Light Clay", "ups": 0,
                                                                                    "done": False}
        elif kind == "-sideend" and len(a) >= 2 and a[1].removeprefix("move: ") in ("Reflect", "Light Screen", "Aurora Veil"):
            t = self.timed.pop(("screen", a[0][:2], a[1].removeprefix("move: ")), None)


            broke = self.cause and self.cause[0] == "move" and self.cause[2] in ("brickbreak", "psychicfangs", "ragingbull", "defog")
            if t and frm is None and not broke and t["ups"] == 4 and not t["done"]:
                self._rule_out(t["setter"], "lightclay")
        if kind == "-enditem" and len(a) >= 2 and a[1] == "Red Card":
            self.lo = None
        if kind in ("switch", "drag", "replace", "turn", "upkeep", "-activate", "-item", "-enditem", "-sidestart", "-sideend",
                    "-fieldstart", "-fieldend", "-weather", "-mega", "detailschange", "-terastallize", "-formechange", "faint"):
            self.cause = None

    def _can_have(self, key: tuple | None, ability: str) -> bool:
        m = self._mon(key)
        legal = dex()["abilities"][self.mod].get(m.species) if m else None
        return bool(legal) and ability in legal

    def _ability_on(self, keys: list, ability: str) -> None:

        cands = list({k[:2]: k for k in keys if k and self._can_have(k, ability)}.values())
        if len(cands) == 1:
            self._set_ability(cands[0], ability)

    def feed(self, line: str) -> None:
        p = line.split("|")
        if len(p) < 2:
            return
        kind, a = p[1], p[2:]
        of = next((self._key(x[5:]) for x in a if x.startswith("[of] ")), None)
        frm = next((x[6:].strip() for x in a if x.startswith("[from]")), None)
        self._rules(kind, a, frm, of)
        self._speed_state(kind, a)
        if self.hp_undo and kind == "replace" and a and a[0][:3] == self.hp_undo[3] and len(a) >= 2:

            m, before, seen, _ = self.hp_undo
            types = [t.lower() for t in dex()["species"].get(self.mod, {}).get(to_id(a[1].split(",")[0]), {}).get("types", [])]
            fits = {t for t in HP_TYPES if hp_effect(t, types, self.mod) == seen} if types else set(HP_TYPES)
            m.hp_types = ((before or set(HP_TYPES)) & fits) or before
            self.hp_undo = None
        elif kind in ("move", "turn"):
            self.hp_undo = None
        if self.hp_pending:
            self._hidden_power(kind, a, frm)
        if kind == "-start" and len(a) >= 3 and a[1] in ("typechange", "typeadd"):
            key = self._key(a[0])
            if key:
                new = [t.lower() for t in a[2].split("/") if t and t != "???"]
                self.cur_types[key[:2]] = (self._types(key) + new) if a[1] == "typeadd" else new
        if kind == "poke" and len(a) >= 2:
            self.mons[a[0]].append(MonFacts(species=to_id(a[1].split(",")[0])))
            if self.mod == "gen5" and len(a) >= 3:
                self.mons[a[0]][-1].holds = a[2] in ("item", "mail")
            return
        if kind in ("switch", "drag", "replace") and len(a) >= 2:
            side, nick = a[0][:2], a[0].split(": ", 1)[1]
            species = to_id(a[1].split(",")[0])
            if kind == "replace":
                idx = self._index_for(side, species)
                shown = self.active.get(a[0][:3])
                if idx is not None and shown is not None and shown != idx:
                    fake, real = self.mons[side][shown], self.mons[side][idx]
                    for field_, value, i in self.journal.get(a[0][:3], []):
                        if i != shown:
                            continue
                        if field_ == "move":
                            if value in fake.moves:
                                fake.moves.remove(value)
                            if value not in real.moves and self._learns(real.species, value, real.species):
                                real.moves.append(value)
                        elif field_ == "not_item":
                            fake.not_items.discard(value)
                            real.not_items.add(value)
                        elif getattr(fake, field_) == value:
                            setattr(fake, field_, None)
                            if getattr(real, field_) is None:
                                setattr(real, field_, value)
            else:
                idx = self.nick.get(f"{side}: {nick}")
                if idx is None:
                    idx = self._index_for(side, species)
            old = self.active.get(a[0][:3])
            if old is not None:
                self.cur_types.pop((side, old), None)
                self.mons[side][old].transformed = False
                self.mons[side][old].last_used = None
                self.mons[side][old].embargo = False
            if idx is not None:
                self.nick[f"{side}: {nick}"] = idx
                self.active[a[0][:3]] = idx
                self.cur_species[(side, idx)] = species
                self.journal[a[0][:3]] = []
                if len(a) >= 3 and self._pct(a[2]) is not None:
                    self.hp[(side, idx)] = self._pct(a[2])
                self.healblock.discard((side, idx))
                passed = old is not None and any(x.endswith("Baton Pass") for x in a[2:])
                self.spe_stage[(side, idx)] = self.spe_stage.get((side, old)) if passed else 0
            return
        if kind == "swap" and len(a) >= 2 and a[1].isdigit():

            side, frm_slot = a[0][:2], a[0][:3]
            to_slot = side + "abc"[int(a[1])]
            if frm_slot != to_slot:
                for d in (self.active, self.journal):
                    x, y = d.get(frm_slot), d.get(to_slot)
                    d.pop(frm_slot, None)
                    d.pop(to_slot, None)
                    if x is not None:
                        d[to_slot] = x
                    if y is not None:
                        d[frm_slot] = y
            return
        if kind in ("detailschange", "-mega"):
            key = self._key(a[0])
            m = self._mon(key)
            if m:
                m.ability_swapped = True
                if kind == "detailschange" and len(a) >= 2:
                    self.cur_species[key[:2]] = to_id(a[1].split(",")[0])
            return
        if kind == "-transform":
            key = self._key(a[0])
            other = self._key(a[1]) if len(a) > 1 else None
            if key and other:
                self.cur_types[key[:2]] = self._types(other)
            if frm and frm.startswith("ability: "):
                self._set_ability(key, frm[9:])
            m = self._mon(key)
            if m:
                m.transformed = True
                m.ability_swapped = m.ability_moved = True
            return
        if kind == "move" and len(a) >= 2:
            key = self._key(a[0])
            self.last_move = (key, self._key(a[2]) if len(a) > 2 else None)
            mid = move_id(a[1])
            self.berry_eater = None
            if any(x.startswith("[from]") for x in a[2:]):
                return
            m = self._mon(key)
            if mid == "hiddenpower" and m and not m.transformed and m.ability != "normalize" and len(a) > 2:
                self.hp_pending = (key, self._key(a[2]))
            learnable = bool(m) and self._learns(self.cur_species.get(key[:2], m.species), mid, m.species)
            if m and not m.transformed and mid != "struggle" and learnable:
                self._rule_out_items(m, mid, key)
            if mid in REORDER_MOVES:
                self.order_ok = False
            if m and self.order_ok and not m.transformed and mid != "struggle":
                for k0, mid0 in self.turn_moves:
                    if k0[0] != key[0]:
                        self._speed_pair(k0, mid0, key, mid)
                        self._speed_bounds(k0, mid0, key, mid)
                self.turn_moves.append((key, mid))
            if m and not m.transformed and mid != "struggle" and mid not in m.moves and learnable:
                m.moves.append(mid)
                self._note(key, "move", mid)
            if mid in ABILITY_SWAP_MOVES:
                for k in self.last_move:
                    if self._mon(k):
                        self._mon(k).ability_swapped = self._mon(k).ability_moved = True
            if mid in ("trick", "switcheroo"):
                for k in self.last_move:
                    if self._mon(k):
                        self._mon(k).item_swapped = True
            return
        if kind == "-item" and len(a) >= 2:
            key = self._key(a[0])
            if frm == "ability: Frisk":
                if key:
                    self._set_item(key, a[1])
                self._set_ability(of, "frisk")
                return
            if frm in ITEM_GAIN:
                self._set_item(of, a[1])
                for k in (of, key):
                    if self._mon(k):
                        self._mon(k).item_swapped = True
                if frm.startswith("ability: "):
                    self._set_ability(key, frm[9:])
                return
            if frm in ITEM_SWAP or (frm and frm.startswith("move: ")):
                if self._mon(key):
                    self._mon(key).item_swapped = True
                return
            if frm == "ability: Harvest":
                self._set_ability(key, "harvest")
            self._set_item(key, a[1])
            return
        if kind == "-enditem" and len(a) >= 2:
            self._set_item(self._key(a[0]), a[1])

            self.berry_eater = of[:2] if of and "stealeat" in "|".join(a) else None
            if self._mon(self._key(a[0])):
                self._mon(self._key(a[0])).item_gone = True
            return
        if kind in ("-fieldstart", "-fieldend") and len(a) >= 1 and a[0].endswith("Magic Room"):
            self.magic_room = kind == "-fieldstart"
            return
        if kind in ("-start", "-end") and len(a) >= 2 and a[1].endswith("Embargo"):
            if self._mon(self._key(a[0])):
                self._mon(self._key(a[0])).embargo = kind == "-start"
        if kind == "-ability" and len(a) >= 2:
            key = self._key(a[0])
            if frm in ("ability: Trace", "ability: Receiver", "ability: Power of Alchemy"):
                self._set_ability(key, frm[9:])
                self._set_ability(of, a[1])
                if self._mon(key):
                    self._mon(key).ability_swapped = self._mon(key).ability_moved = True
                return
            if frm and frm.startswith("move: "):
                if self._mon(key):
                    self._mon(key).ability_swapped = self._mon(key).ability_moved = True
                return
            if frm and frm.startswith("ability: "):
                self._ability_on([key, of], frm[9:])
                return
            self._set_ability(key, a[1])
            return
        if kind == "-activate" and len(a) >= 2 and a[1] in ("Skill Swap", "move: Skill Swap"):
            for k in (self._key(a[0]), of):
                if self._mon(k):
                    self._mon(k).ability_swapped = self._mon(k).ability_moved = True
            return

        effects = [x[6:].strip() for x in a if x.startswith("[from]")] + [x for x in a[1:3] if x.startswith(("item: ", "ability: "))]
        if not effects:
            return
        key = self._key(a[0]) if a else None
        for eff in effects:
            if eff.startswith("item: ") and self.berry_eater and key and key[:2] == self.berry_eater:
                continue
            if eff.startswith("item: "):

                self._set_item(of if kind == "-damage" and of else key, eff[6:])
            elif eff.startswith("ability: "):
                ab = eff[9:]
                if ab in ABILITY_PASS and kind == "-activate":
                    self._set_ability(key, ab)
                    other = of or (self._key(a[2]) if len(a) > 2 else None)
                    old = next((x[10:] for x in a if x.startswith("[ability] ")), None)
                    if old:
                        self._set_ability(other, old)
                    for k in (key, other) if ab == "Wandering Spirit" else (other,):
                        if self._mon(k):
                            self._mon(k).ability_swapped = self._mon(k).ability_moved = True
                    continue
                self._ability_on([key, of], ab)




FEATURES = ("bias", "damaging", "stab", "phys_fit", "power", "stab_power", "priority", "spread", "inaccurate", "glob", "has_glob",
            "pool", "learners")


def glob_input(mid: str, glob: dict, fit_mod: str) -> float | None | str:



    if mid in glob:
        return glob[mid]
    return None if mid in dex()["moves"][fit_mod] else "median"


def move_features(sp: dict, mv: dict, glob: float | None | str, pool: int, glob_missing: float = 0.0, learners: int = 1) -> list[float]:



    if glob == "median":
        glob = glob_missing
    dmg = mv["cat"] != "Status"
    stab = dmg and mv["type"] in sp["types"]
    bs = sp["bs"]
    r = (bs["atk"] - bs["spa"]) / max(1, bs["atk"] + bs["spa"])
    fit = (r if mv["cat"] == "Physical" else -r) if dmg else 0.0
    power = (min(mv["bp"], 150) / 100 if mv["bp"] else 0.6) if dmg else 0.0
    return [1.0, float(dmg), float(stab), fit, power, power * stab, float(mv["pri"] > 0),
            float(mv["target"] in ("allAdjacentFoes", "allAdjacent")), float(mv["acc"] < 100),
            glob if glob is not None else glob_missing, float(glob is not None), math.log(max(1, pool)) / 5,
            math.log(max(1, learners)) / 5]


class SetPrior:



    def __init__(self, data: dict):
        self.fmt, self.mod = data["format"], data["mod"]
        self.sets = data["sets"]
        self.coef, self.glob, self.glob_missing = data["fit"]["coef"], data["fit"]["glob"], data["fit"].get("glob_missing", 0.0)
        self.fit_mod = data["fit"].get("mod", "champions")
        self.items = data.get("items", {})
        self.usage = data.get("usage", {})
        self._fit: dict[str, dict[str, float]] = {}

    @classmethod
    def load(cls, fmt: str | None) -> "SetPrior":
        name = FORMAT_PRIOR.get(fmt) or FORMAT_MOD.get(fmt, "champions")
        if not (PRIORS / f"{name}.json").exists():
            name = FORMAT_MOD.get(fmt, "champions")
        return cls(json.loads((PRIORS / f"{name}.json").read_text(encoding="utf8")))

    def fit(self, species: str) -> dict[str, float]:

        if species not in self._fit:
            d = dex()
            pool = d["movepools"][self.mod].get(species) or d["movepools"][self.mod].get(_base(species), [])
            sp = d["species"][self.mod].get(species) or d["species"][self.mod].get(_base(species))
            moves = d["moves"][self.mod]
            out = {}
            if sp:
                for mid in pool:
                    if mid in moves:
                        z = sum(c * x for c, x in zip(self.coef, move_features(sp, moves[mid], glob_input(mid, self.glob, self.fit_mod), len(pool), self.glob_missing,
                                                                  learner_counts(self.mod).get(mid, 1))))
                        out[mid] = 1 / (1 + math.exp(-z))
            self._fit[species] = _scale_to(out, 4.0)
        return self._fit[species]


_LEARNERS: dict[str, dict[str, int]] = {}


def learner_counts(mod: str) -> dict[str, int]:

    if mod not in _LEARNERS:
        c: dict[str, int] = {}
        for pool in dex()["movepools"][mod].values():
            for m in pool:
                c[m] = c.get(m, 0) + 1
        _LEARNERS[mod] = c
    return _LEARNERS[mod]


def _base(species: str) -> str:
    return species.split("mega")[0] if "mega" in species[3:] else species


def _scale_to(p: dict[str, float], total: float) -> dict[str, float]:

    p = dict(p)
    for _ in range(20):
        free = {k: v for k, v in p.items() if v < 1}
        s = sum(free.values())
        room = total - (len(p) - len(free))
        if s <= 0 or room <= 0:
            break
        f = room / s
        if abs(f - 1) < 1e-6:
            break
        for k in free:
            p[k] = min(1.0, free[k] * f)
    return p




def posterior(prior: SetPrior, facts: MonFacts, top: int = 8) -> dict:


    sets = prior.sets.get(facts.species) or prior.sets.get(_base(facts.species)) or []
    known_moves = set(facts.moves)
    ws = []
    for w, item, ability, moves, nature in sets:
        miss = len(known_moves - set(moves))
        if facts.item is not None and item != facts.item:
            miss += 1
        if facts.holds is not None and bool(item) != facts.holds:
            miss += 1
        if facts.ability is not None and ability != facts.ability:
            miss += 1
        if item in facts.not_items:
            miss += 1
        if facts.speed_item and item != facts.speed_item:
            miss += 1
        ws.append(w * MISMATCH ** miss)
    total = sum(ws)

    fit = {k: v for k, v in prior.fit(facts.species).items() if k not in known_moves}
    fit = _scale_to(fit, max(0, 4 - len(known_moves)))
    fw = FIT_WEIGHT
    use = prior.usage.get(facts.species) or prior.usage.get(_base(facts.species))
    uw = min(use["n"] / USAGE_PER, USAGE_MAX) if use else 0.0
    norm = total + fw + uw
    moves: dict[str, float] = {}
    items: dict[str, float] = {}
    abilities: dict[str, float] = {}
    natures: dict[str, float] = {}
    for w, (_, item, ability, mv, nature) in zip(ws, sets):
        q = w / norm
        for m in mv:
            moves[m] = moves.get(m, 0) + q
        items[item] = items.get(item, 0) + q
        abilities[ability] = abilities.get(ability, 0) + q
        natures[nature] = natures.get(nature, 0) + q
    for m, p in fit.items():
        moves[m] = moves.get(m, 0) + p * fw / norm

    item_pool = {k: v for k, v in prior.items.items() if (facts.holds is None or bool(k) == facts.holds) and k not in facts.not_items}
    s = sum(item_pool.values()) or 1
    for k, v in item_pool.items():
        items[k] = items.get(k, 0) + v / s * fw / norm
    legal = dex()["abilities"][prior.mod].get(facts.species) or []
    for ab in legal:
        abilities[to_id(ab)] = abilities.get(to_id(ab), 0) + fw / norm / len(legal)
    if use:
        um = _scale_to({k: v for k, v in use["moves"].items() if k not in known_moves}, max(0, 4 - len(known_moves)))
        for m, p in um.items():
            moves[m] = moves.get(m, 0) + p * uw / norm
        ui = {k: v for k, v in use["items"].items() if (facts.holds is None or bool(k) == facts.holds) and k not in facts.not_items}
        si = sum(ui.values()) or 1
        for k, v in ui.items():
            items[k] = items.get(k, 0) + v / si * uw / norm
        sa = sum(use["abilities"].values()) or 1
        for k, v in use["abilities"].items():
            abilities[k] = abilities.get(k, 0) + v / sa * uw / norm
    for m in known_moves:
        moves[m] = 1.0
    for k in facts.not_items:
        items.pop(k, None)
    if facts.speed_item and facts.item is None:
        rest = sum(v for k, v in items.items() if k != facts.speed_item) or 1.0
        items = {facts.speed_item: 0.9, **{k: v / rest * 0.1 for k, v in items.items() if k != facts.speed_item}}
    if facts.item is not None:
        items = {facts.item: 1.0}
    elif facts.holds is False:
        items = {"": 1.0}
    if facts.ability is not None:
        abilities = {facts.ability: 1.0}
    rank = lambda d: sorted(d.items(), key=lambda kv: -kv[1])[:top]
    best = sorted(range(len(sets)), key=lambda i: -ws[i])[:3]
    return {"moves": rank(moves), "items": rank(items), "abilities": rank(abilities), "natures": rank(natures),
            "sets": [(ws[i] / norm, sets[i]) for i in best], "data_players": sum(s[0] for s in sets), "fit_share": fw / norm,
            "usage_share": uw / norm}


def describe(prior: SetPrior, facts: MonFacts, n_moves: int = 6) -> str:

    b = posterior(prior, facts)
    def mname(m: str) -> str:
        if m == "hiddenpower" and facts.hp_types and len(facts.hp_types) <= 2:
            return f"Hidden Power [{'/'.join(sorted(t.title() for t in facts.hp_types))}]"
        return name("moves", m)
    mv = ", ".join(f"{mname(m)} {'(seen)' if m in facts.moves else f'{p:.0%}'}" for m, p in b["moves"][:max(n_moves, len(facts.moves))])
    it = f"{name('items', facts.item)} (seen)" if facts.item is not None else ", ".join(f"{name('items', i)} {p:.0%}" for i, p in b["items"][:2])
    ab = (f"{name('abilities', facts.ability)} (seen)" if facts.ability is not None
          else ", ".join(f"{name('abilities', x)} {p:.0%}" for x, p in b["abilities"][:2]))
    return f"{name('species', facts.species)}: {mv} | {it} | {ab}"




PLUS_SPE, MINUS_SPE = {"timid", "hasty", "jolly", "naive"}, {"brave", "relaxed", "quiet", "sassy"}


def speed_stat(prior: SetPrior, species: str, nature: str, ev: int, iv: int = 31) -> int:

    b = (dex()["species"][prior.mod].get(species) or {"bs": {"spe": 80}})["bs"]["spe"]
    inv = ev * 2 if prior.mod == "champions" else ev // 4
    n = to_id(nature)
    return int(((2 * b + iv + inv) * 50 // 100 + 5) * (1.1 if n in PLUS_SPE else 0.9 if n in MINUS_SPE else 1.0))


def _fitting_spread(prior: SetPrior, facts: MonFacts, spreads: list[str], item: str) -> str | None:


    if not spreads or (facts.speed_lo <= 0 and facts.speed_hi == float("inf")):
        return spreads[0] if spreads else None
    factor = 1.5 if item == "choicescarf" else 1.0

    def eff(sp: str) -> float:
        nature, evs = sp.split(":")
        return speed_stat(prior, facts.species, nature, int(evs.split("/")[5])) * factor

    fits = [sp for sp in spreads if facts.speed_lo <= eff(sp) <= facts.speed_hi]
    if fits:
        return fits[0]
    nature, evs = spreads[0].split(":")
    ev = evs.split("/")
    if facts.speed_lo > eff(spreads[0]):
        ev[5] = "252" if prior.mod != "champions" else "32"
        nature = "Jolly" if to_id(nature) in ("adamant", "jolly", "brave", "impish", "careful") else "Timid"
    else:
        ev[5] = "0"
        nature = "Brave" if to_id(nature) in ("adamant", "jolly", "brave", "impish", "careful") else "Quiet"
    return f"{nature}:{'/'.join(ev)}"

STATS = ("hp", "atk", "def", "spa", "spd", "spe")
HP_TYPES = ("fighting", "flying", "poison", "ground", "rock", "bug", "ghost", "steel", "fire", "water", "grass", "electric",
            "psychic", "ice", "dragon", "dark")



HP_CHART = {
    "fighting": ("normal rock steel ice dark", "flying poison bug psychic fairy", "ghost"),
    "flying": ("fighting bug grass", "rock steel electric", ""),
    "poison": ("grass fairy", "poison ground rock ghost", "steel"),
    "ground": ("poison rock steel fire electric", "bug grass", "flying"),
    "rock": ("flying bug fire ice", "fighting ground steel", ""),
    "bug": ("grass psychic dark", "fighting flying poison ghost steel fire fairy", ""),
    "ghost": ("ghost psychic", "dark", "normal"),
    "steel": ("rock ice fairy", "steel fire water electric", ""),
    "fire": ("bug steel grass ice", "rock fire water dragon", ""),
    "water": ("ground rock fire", "water grass dragon", ""),
    "grass": ("ground rock water", "flying poison bug steel fire grass dragon", ""),
    "electric": ("flying water", "grass electric dragon", "ground"),
    "psychic": ("fighting poison", "steel psychic", "dark"),
    "ice": ("flying ground grass dragon", "steel fire water ice", ""),
    "dragon": ("dragon", "steel", "fairy"),
    "dark": ("ghost psychic", "fighting dark fairy", ""),
}

HP_ABSORB = {"flashfire": "fire", "waterabsorb": "water", "stormdrain": "water", "dryskin": "water", "voltabsorb": "electric",
             "lightningrod": "electric", "motordrive": "electric", "sapsipper": "grass", "levitate": "ground"}


def hp_effect(hp_type: str, target_types: list[str], mod: str) -> str:


    se, res, imm = (set(x.split()) for x in HP_CHART[hp_type])
    if mod == "gen5" and hp_type in ("ghost", "dark"):
        res.add("steel")
    mult = 1.0
    for t in target_types:
        mult *= 0.0 if t in imm else 2.0 if t in se else 0.5 if t in res else 1.0
    return "imm" if mult == 0 else "se" if mult > 1 else "res" if mult < 1 else "neutral"


def hp_ivs(hp_type: str) -> dict:


    cost = {"hp": 1, "atk": 2, "def": 1, "spe": 6, "spa": 2, "spd": 1}
    best, best_cost = None, None
    for mask in range(64):
        bits = [(mask >> i) & 1 for i in range(6)]
        low = dict(zip(("hp", "atk", "def", "spe", "spa", "spd"), bits))
        t = (low["hp"] + 2 * low["atk"] + 4 * low["def"] + 8 * low["spe"] + 16 * low["spa"] + 32 * low["spd"]) * 15 // 63
        c = sum(cost[k] for k, b in low.items() if not b)
        if HP_TYPES[t] == hp_type and (best is None or c < best_cost):
            best, best_cost = low, c
    return {k: 31 if best[k] else 30 for k in STATS}


def _draw(ranked: list[tuple[str, float]], rng) -> str:

    x = rng.random() * sum(p for _, p in ranked)
    for k, p in ranked:
        x -= p
        if x <= 0:
            return k
    return ranked[-1][0]


def world_set(prior: SetPrior, facts: MonFacts, fmt: str | None, rng=None, sample: bool = False) -> dict:






    import vgc_engine as ve

    b = posterior(prior, facts, top=40)
    revealed = list(dict.fromkeys(facts.moves))[:4]
    others = [m for m, _ in b["moves"] if m not in revealed]
    if rng is not None and others:
        w = {m: p for m, p in b["moves"] if m not in revealed}
        if sample:
            others = sorted(others, key=lambda m: -(rng.random() ** (1.0 / max(w[m], 1e-9))))
        else:
            others = sorted(others, key=lambda m: -(w[m] * (0.5 + rng.random())))
    drawn = sample and rng is not None
    if facts.item is not None:
        item = facts.item
    elif facts.holds is False:
        item = ""
    else:
        item = (_draw(b["items"], rng) if drawn else b["items"][0][0]) if b["items"] else ""
    ability = facts.ability or ((_draw(b["abilities"], rng) if drawn else b["abilities"][0][0]) if b["abilities"] else "")
    if ability == "asone":
        ability = "asonespectrier" if "shadow" in facts.species else "asoneglastrier"
    use = prior.usage.get(facts.species) or {}
    spread = _fitting_spread(prior, facts, list(use.get("spreads", {})), item)
    if spread:
        nature, evs = spread.split(":")
        evs = dict(zip(STATS, (int(x) for x in evs.split("/"))))
    else:
        sp = dex()["species"][prior.mod].get(facts.species, {"bs": {"atk": 100, "spa": 100}})
        phys = sp["bs"]["atk"] >= sp["bs"]["spa"]
        nature = "Adamant" if phys else "Modest"
        evs = {"hp": 4, "atk": 252 if phys else 0, "def": 0, "spa": 0 if phys else 252, "spd": 0, "spe": 252}
    if prior.mod == "champions":
        evs = {k: min(32, v // 8) for k, v in evs.items()}


    by_use = list(use.get("hp_types", {}))
    if facts.hp_types:
        fits = [t for t in by_use if t in facts.hp_types] or [t for t in HP_TYPES if t in facts.hp_types]
        hp_type = fits[0]
    else:
        hp_type = next(iter(by_use), None)
    ivs = hp_ivs(hp_type) if hp_type in HP_TYPES else None
    pool = ve.BattlePool(1)
    moves = revealed + others[: 4 - len(revealed)]
    rest = others[4 - len(revealed):]
    item_rest = [i for i, _ in b["items"] if i != item]
    ability_rest = [x for x, _ in b["abilities"] if x != ability]
    for _ in range(12):
        s = {"species": name("species", facts.species), "item": name("items", item) if item else "",
             "ability": name("abilities", ability) if ability else "", "moves": [name("moves", m) for m in moves],
             "nature": nature, "evs": evs, "level": 50}
        if ivs and "hiddenpower" in moves:
            s["ivs"] = ivs
        try:
            pool.register_team([s] * 6) if fmt is None else pool.register_team([s] * 6, fmt)
            return s
        except ValueError as e:
            msg = str(e)
            if item and name("items", item) in msg and facts.item is None:
                item = item_rest.pop(0) if item_rest else ""
                continue
            if ability and name("abilities", ability) in msg and facts.ability is None:
                ability = ability_rest.pop(0) if ability_rest else ""
                continue
            bad = next((m for m in moves if m not in revealed and name("moves", m) in msg), None)
            if bad is None:
                bad = next((m for m in reversed(moves) if m not in revealed), None)
            if bad is None:
                raise
            moves = [m for m in moves if m != bad] + rest[:1]
            rest = rest[1:]
    raise ValueError(f"no playable set for {facts.species}")

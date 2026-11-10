









from __future__ import annotations

from vgc_trainer import i18n

import re

from vgc_trainer.showdown.sheets import BUDDY_SUFFIX
from vgc_trainer.showdown.teams import pack
from vgc_trainer.showdown.tracker import to_id

STATUS = ("", "brn", "frz", "par", "psn", "tox", "slp")
BOOST_NAMES = ("atk", "def", "spa", "spd", "spe", "accuracy", "evasion")
WEATHER = {"Sun": "sunnyday", "Rain": "raindance", "Sand": "sandstorm", "Snow": "snowscape", "Hail": "hail",
           "HarshSun": "desolateland", "HeavyRain": "primordialsea", "StrongWinds": "deltastream"}
TERRAIN = {"Electric": "electricterrain", "Grassy": "grassyterrain", "Misty": "mistyterrain", "Psychic": "psychicterrain"}
TIMED = {"tailwind": "tailwind", "reflect": "reflect", "light_screen": "lightscreen", "aurora_veil": "auroraveil", "safeguard": "safeguard"}



_TOK = re.compile(r"\s*(?:(?P<num>-?\d+(?:\.\d+)?)|(?P<str>\"(?:[^\"\\]|\\.)*\")|(?P<id>[A-Za-z_][A-Za-z0-9_]*)|(?P<p>[{}\[\](),:]))")


def _tokens(text: str) -> list[str]:
    out, i = [], 0
    while i < len(text):
        m = _TOK.match(text, i)
        if not m or m.end() == i:
            if text[i:].strip() == "":
                break
            raise ValueError(f"dump: can't read {text[i:i + 30]!r}")
        out.append(m.group(m.lastgroup))
        i = m.end()
    return out


def parse_dump(text: str):


    toks, pos = _tokens(text), [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take(want=None):
        t = toks[pos[0]]
        if want is not None and t != want:
            raise ValueError(f"dump: wanted {want!r}, got {t!r}")
        pos[0] += 1
        return t

    def seq(close):
        items = []
        while peek() != close:
            items.append(value())
            if peek() == ",":
                take(",")
        take(close)
        return items

    def value():
        t = take()
        if t == "[":
            return seq("]")
        if t == "(":
            return seq(")")
        if t[0] == '"':
            return t[1:-1]
        if t[0].isdigit() or t[0] == "-":
            return float(t) if "." in t else int(t)
        if t in ("true", "false"):
            return t == "true"
        if peek() == "{":
            take("{")
            d = {"_type": t}
            while peek() != "}":
                k = take()
                take(":")
                d[k] = value()
                if peek() == ",":
                    take(",")
            take("}")
            return d
        if peek() == "(":
            take("(")
            inner = seq(")")
            return inner[0] if len(inner) == 1 else inner
        return t

    return value()


def _mons(side: dict) -> list[dict]:
    m = side.get("mons")
    return m if isinstance(m, list) else []


def build(crawl, nid: str, names: dict[str, str]) -> tuple[dict, list[str]]:


    from vgc_trainer.formats import CURRENT
    with crawl.lock:
        root = next(iter(crawl.data["nodes"]))
        crawl._load(root)
        full_pp = [[list(m["pp"]) for m in sd["mons"]] for sd in crawl._inspect()["sides"]]
        crawl._load(nid)
        st = crawl._inspect()
        dump = parse_dump(crawl.env.pool.dump(0))
    if st["pending"] != "turn" or st.get("winner") is not None:
        raise ValueError(i18n.t("pick a node at the start of a turn (not a pending replacement, not the end of the game)"))
    sides_d = dump[0] if isinstance(dump, list) else []
    fmt = crawl.data.get("format") or CURRENT
    teams, brings = crawl.data["teams"], crawl.data["brings"]

    spec = {"format": fmt + BUDDY_SUFFIX, "ots": True, "turn": int(st["turn"]) + 1, "mons": {}, "sides": {}, "ghost": []}
    notes = ["a new seed: the dice from here are fresh", "the client counts the field's turns from the reopen"]
    for k, s in enumerate(("p1", "p2")):
        sd, team, bring = st["sides"][k], teams[k], brings[k]
        dmons = _mons(sides_d[k]) if k < len(sides_d) else []
        mons = sd["mons"]
        actives = [i for i in sd["active"] if i is not None and i < len(mons) and mons[i]["hp"] > 0]
        bench = [i for i in range(len(mons)) if i not in actives and mons[i]["hp"] > 0]
        fainted = [i for i in range(len(mons)) if mons[i]["hp"] <= 0]
        out = []
        for i in actives + bench + fainted:
            m, sheet = mons[i], team[bring[i]]
            dm = dmons[i] if i < len(dmons) and isinstance(dmons[i], dict) else {}
            hp = 0 if m["hp"] <= 0 else max(1, min(1000, round(m["hp"] * 1000 / m["max_hp"])))
            e = {"hp": hp}
            status = STATUS[m["status"]] if 0 <= m["status"] < len(STATUS) else ""
            if hp and status:
                e["status"] = status
                if status == "tox" and isinstance(dm.get("status_counter"), int):
                    e["toxStage"] = max(1, min(15, int(dm["status_counter"])))
                if status == "slp":
                    notes.append(f"{sheet['species']}'s sleep: turns left drawn afresh")
            b = {n: int(v) for n, v in zip(BOOST_NAMES, m["boosts"]) if v}
            if b and i in actives:
                e["boosts"] = b
            if sheet.get("item") and not m["item"]:
                e["noItem"] = True
            if "-Mega" in m["species"] and "-Mega" not in sheet["species"]:
                e["mega"] = True
            used = {to_id(mv): int(full_pp[k][i][j]) - int(m["pp"][j]) for j, mv in enumerate(m["moves"])
                    if j < len(full_pp[k][i]) and int(full_pp[k][i][j]) > int(m["pp"][j])}
            if used:
                e["ppUsed"] = used
            if hp == 0 or hp < 1000 or status or e.get("noItem") or e.get("mega") or i in actives or used:
                e["seen"] = True
            if i in actives and hp:
                if isinstance(dm.get("turns_active"), int):
                    e["activeTurns"] = int(dm["turns_active"])
                if isinstance(dm.get("times_attacked"), int) and dm["times_attacked"]:
                    e["timesAttacked"] = int(dm["times_attacked"])
                vols = []
                if isinstance(dm.get("sub_hp"), int) and dm["sub_hp"] > 0:
                    vols.append("substitute")
                if isinstance(dm.get("taunt_turns"), int) and dm["taunt_turns"] > 0:
                    vols.append("taunt")
                    notes.append(f"{sheet['species']}'s Taunt: turns left drawn afresh")
                if vols:
                    e["vols"] = vols
                if isinstance(dm.get("protect_counter"), int) and dm["protect_counter"] > 0:
                    e["stall"] = min(6, int(dm["protect_counter"]))
            out.append(e)
        spec[s] = {"name": names[s], "team": pack(team), "order": [bring[i] + 1 for i in actives + bench + fainted]}
        spec["mons"][s] = out
        side = {TIMED[c]: int(v) for c, v in (sd.get("conds") or {}).items() if c in TIMED and v}
        ds = sides_d[k] if k < len(sides_d) and isinstance(sides_d[k], dict) else {}
        hz = next((v for v in ds.values() if isinstance(v, dict) and "stealth_rock" in v), ds)
        if hz.get("stealth_rock"):
            side["stealthrock"] = 1
        for key, name in (("spikes", "spikes"), ("toxic_spikes", "toxicspikes")):
            if isinstance(hz.get(key), int) and hz[key]:
                side[name] = int(hz[key])
        if hz.get("sticky_web"):
            side["stickyweb"] = 1
        spec["sides"][s] = side
    f, fd = {}, st["field"]
    if fd.get("weather") in WEATHER:
        f["weather"], f["weatherTurns"] = WEATHER[fd["weather"]], int(fd.get("weather_turns") or 0)
    if fd.get("terrain") in TERRAIN:
        f["terrain"], f["terrainTurns"] = TERRAIN[fd["terrain"]], int(fd.get("terrain_turns") or 0)
    if fd.get("trick_room"):
        f["trickRoom"] = int(fd["trick_room"])
    if fd.get("gravity"):
        f["gravity"] = int(fd["gravity"])
    spec["field"] = f
    return spec, notes

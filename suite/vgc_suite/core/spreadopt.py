





























from __future__ import annotations

import gzip
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from vgc_trainer.winproc import NO_WINDOW

ROOT = Path(__file__).resolve().parents[3]
CALC = ROOT / "tools/showdown-oracle/calc.js"
USAGE = ROOT / "data/smogon-usage"
STATS = ("hp", "atk", "def", "spa", "spd", "spe")
TWO_HKO = 0.15
NEAR = 1e-9
USAGE_SPREADS = 3









PRESETS = {
    "improve": ((1.5, 1.0, 0.5), ("risk", "reach", "speed", "first"), 0.0),
    "bulk": ((1.0, 0.25, 0.0), ("speed",), 0.0),
    "damage": ((0.25, 1.0, 0.0), ("speed",), 0.0),
    "free": ((0.25, 0.25, 1.0), ("risk", "reach"), 0.03),
}
NATURES = {("atk", "def"): "Lonely", ("atk", "spa"): "Adamant", ("atk", "spd"): "Naughty", ("atk", "spe"): "Brave",
           ("def", "atk"): "Bold", ("def", "spa"): "Impish", ("def", "spd"): "Lax", ("def", "spe"): "Relaxed",
           ("spa", "atk"): "Modest", ("spa", "def"): "Mild", ("spa", "spd"): "Rash", ("spa", "spe"): "Quiet",
           ("spd", "atk"): "Calm", ("spd", "def"): "Gentle", ("spd", "spa"): "Careful", ("spd", "spe"): "Sassy",
           ("spe", "atk"): "Timid", ("spe", "def"): "Hasty", ("spe", "spa"): "Jolly", ("spe", "spd"): "Naive"}
PLUSMINUS = {v: k for k, v in NATURES.items()}
WEATHER_ABILITIES = {"Drizzle": "RainDance", "Drought": "SunnyDay", "Sand Stream": "Sandstorm", "Snow Warning": "Snowscape",
                     "Orichalcum Pulse": "SunnyDay", "Primordial Sea": "PrimordialSea", "Desolate Land": "DesolateLand"}
TERRAIN_ABILITIES = {"Grassy Surge": "Grassy Terrain", "Electric Surge": "Electric Terrain", "Psychic Surge": "Psychic Terrain",
                     "Misty Surge": "Misty Terrain", "Hadron Engine": "Electric Terrain", "Seed Sower": "Grassy Terrain"}
SPREAD_TARGETS = ("allAdjacentFoes", "allAdjacent")
_DEX: dict = {}
_MEMO: dict = {}


WEATHER_MOVES_DMG = {"Weather Ball", "Solar Beam", "Solar Blade", "Hydro Steam", "Electro Shot", "Psyblade"}

WEATHER_ABILITIES_DMG = {"Protosynthesis", "Solar Power", "Sand Force", "Flower Gift", "Orichalcum Pulse", "Forecast", "Ice Face"}




def rules(fmt: str | None) -> dict:

    from vgc_suite.formats import get
    f = get(fmt)
    return {"points": f.stat_points, "total": 66 if f.stat_points else 508, "cap": 32 if f.stat_points else 252, "fmt": f.id, "gen": f.gen,
            "open": f.open_sheets}


def stat_value(r: dict, base: int, stat: str, inv: int, nature: str, iv: int = 31) -> int:


    if r["points"]:
        if stat == "hp":
            return base + inv + 75
        v = base + inv + 20
    else:
        x = (2 * base + iv + inv // 4) * 50 // 100
        if stat == "hp":
            return x + 60
        v = x + 5
    plus, minus = PLUSMINUS.get(nature, (None, None))
    if plus == stat:
        v = v * 110 // 100
    elif minus == stat:
        v = v * 90 // 100
    return v


def levels(r: dict, base: int, stat: str, nature: str, iv: int = 31) -> list[tuple[int, int]]:

    out, seen = [], set()
    for inv in (range(0, r["cap"] + 1) if r["points"] else range(0, r["cap"] + 1, 4)):
        v = stat_value(r, base, stat, inv, nature, iv)
        if v not in seen:
            seen.add(v)
            out.append((inv, v))
    return out


def dex(fmt: str) -> dict:

    if fmt not in _DEX:
        js = ("const {Dex}=require('./tools/showdown-oracle/lib/showdown');const D=Dex.forFormat(Dex.formats.get(process.argv[1]));"
              "const m={},s={},i={};for(const x of D.moves.all())m[x.name]={category:x.category,target:x.target,bp:x.basePower,type:x.type,"
              "od:x.overrideDefensiveStat||null,oo:x.overrideOffensiveStat||null,oop:x.overrideOffensivePokemon||null,damage:x.damage||null};"
              "for(const x of D.species.all())s[x.name]={base:x.baseStats,abilities:x.abilities,types:x.types};"
              "for(const x of D.items.all())if(x.megaStone)i[x.name]=typeof x.megaStone==='string'?x.megaStone:Object.values(x.megaStone)[0];"
              "console.log(JSON.stringify({m,s,i}))")
        r = subprocess.run(["node", "-e", js, fmt], capture_output=True, text=True, encoding="utf8", check=True, cwd=ROOT, **NO_WINDOW)
        _DEX[fmt] = json.loads(r.stdout)
    return _DEX[fmt]


def forme(d: dict, s: dict, megas: bool) -> str:


    mf = d["i"].get(s.get("item") or "") if megas and s.get("_forme") != "base" else None
    if mf and mf in d["s"] and mf.split("-Mega")[0] == s["species"].split("-Mega")[0]:
        return mf
    return s["species"] if s["species"] in d["s"] else s["species"].split("-Mega")[0]




def usage_spreads(fmt: str) -> dict:

    files = sorted(USAGE.glob(f"{fmt}-1630-*.json.gz"))
    if not files:
        return {}
    data = json.loads(gzip.open(files[-1]).read())["data"]
    out = {}
    for sp, m in data.items():
        rows = sorted((m.get("Spreads") or {}).items(), key=lambda kv: -kv[1])
        tot = sum(v for _, v in rows) or 1
        out[sp] = [(k.split(":")[0], dict(zip(STATS, map(int, k.split(":")[1].split("/")))), v / tot) for k, v in rows[:12]]
    return out


def variants(s: dict, usage: dict, r: dict, mega_p: float = 1.0, mega_name: str | None = None) -> list[tuple[dict, float]]:




    own = {"nature": s.get("nature") or "Serious", "evs": {k: (s.get("evs") or {}).get(k, 0) for k in STATS}}

    rows = (mega_name and usage.get(mega_name)) or usage.get(s["species"]) or usage.get(s["species"].split("-Mega")[0]) or []
    if r["open"] and s.get("nature"):
        rows = [x for x in rows if x[0] == s["nature"]]
    rows = rows[:USAGE_SPREADS]
    tot = sum(x[2] for x in rows)
    out: dict[str, tuple[dict, float]] = {}

    def add(sp, w):
        k = json.dumps(sp, sort_keys=True)
        out[k] = (sp, out.get(k, (sp, 0.0))[1] + w)
    add(dict(own, _src="sheet"), 0.5 if rows else 1.0)
    for nat, evs, sh in rows:
        add({"nature": nat, "evs": evs, "_src": "usage"}, 0.5 * sh / tot)
    if mega_p >= 1.0:
        return [(dict(s, **sp), w) for sp, w in out.values()]
    return [(dict(s, **sp), w * mega_p) for sp, w in out.values()] + [(dict(s, **sp, _forme="base"), w * (1 - mega_p)) for sp, w in out.values()]


def field_sets(field: list[tuple[str, list[dict]]], weights: list[float] | None) -> list[dict]:



    ws = weights or [1.0] * len(field)
    tot = sum(ws) or 1.0
    out: dict[str, dict] = {}
    for (label, sets), w in zip(field, ws):
        k_t = sum(1 for s in sets if _stone(s))
        for s in sets:
            k = json.dumps({x: s.get(x) for x in ("species", "item", "ability", "nature", "evs", "ivs", "moves")}, sort_keys=True)
            e = out.setdefault(k, {"set": s, "w": 0.0, "teams": [], "_mw": 0.0})
            share = w / tot / max(len(sets), 1)
            e["w"] += share
            e["_mw"] += share * (1.0 / k_t if _stone(s) and k_t >= 2 else 1.0)
            e["teams"].append(label)
    for e in out.values():
        e["mega_p"] = round(e.pop("_mw") / e["w"], 6) if e["w"] else 1.0
    return sorted(out.values(), key=lambda e: -e["w"])


def _stone(s: dict) -> bool:

    import re
    it = (s.get("item") or "").replace(" ", "").lower()
    return bool(re.search(r"ite[xyz]?$", it)) and it != "eviolite"


def own_weather(team: list[dict], d: dict, mega: dict | None) -> tuple[str | None, str | None]:


    w = t = None
    for s in team:
        f = forme(d, s, True) if s is mega else s["species"]
        abil = [s.get("ability") or ""] + (list((d["s"].get(f, {}).get("abilities") or {}).values()) if f != s["species"] else [])
        for a in abil:
            w = w or WEATHER_ABILITIES.get(a)
            t = t or TERRAIN_ABILITIES.get(a)
    return w, t


def _attacker_field(s: dict, d: dict, megas: bool, ours: tuple) -> tuple[str | None, str | None]:

    abil = [s.get("ability") or ""]
    f = forme(d, s, megas)
    if f != s["species"]:
        abil += list((d["s"].get(f, {}).get("abilities") or {}).values())
    w = ours[0] or next((WEATHER_ABILITIES[a] for a in abil if a in WEATHER_ABILITIES), None)
    t = ours[1] or next((TERRAIN_ABILITIES[a] for a in abil if a in TERRAIN_ABILITIES), None)
    return w, t




def _calc(cases: list[dict], workers: int | None = None) -> list[dict]:

    if not cases:
        return []
    keys = [json.dumps(c, sort_keys=True) for c in cases]


    todo = [k for k in dict.fromkeys(keys) if k not in _MEMO]
    if todo:
        _MEMO.update(zip(todo, _calc_raw([json.loads(k) for k in todo], workers)))
    return [_MEMO[k] for k in keys]


def _calc_raw(cases: list[dict], workers: int | None = None) -> list[dict]:
    if not cases:
        return []
    n = max(1, min(workers or max(1, (os.cpu_count() or 2) - 1), 6, len(cases) // 20 + 1))
    chunks = [cases[i::n] for i in range(n)]

    def one(chunk):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf8") as f:
            json.dump(chunk, f)
        try:
            r = subprocess.run(["node", str(CALC), f.name], capture_output=True, text=True, encoding="utf8", check=True, cwd=ROOT, **NO_WINDOW)
        finally:
            Path(f.name).unlink()
        return json.loads(r.stdout)
    with ThreadPoolExecutor(n) as ex:
        parts = list(ex.map(one, chunks))
    out = [None] * len(cases)
    for i, part in enumerate(parts):
        for j, x in enumerate(part):
            out[i + j * n] = x
    return out


def _weather_matters(d: dict, weather: str | None, mv: str, m: dict, atk_forme: str, def_forme: str, atk: dict, dfn: dict) -> bool:

    if not weather:
        return False
    w = weather.lower()
    mtype = (d["m"].get(mv) or {}).get("type")
    if mv in WEATHER_MOVES_DMG or mtype is None or (mtype in ("Fire", "Water") and ("sun" in w or "rain" in w or "land" in w or "sea" in w)):
        return True
    abil = {atk.get("ability") or "", dfn.get("ability") or ""}
    for f, st in ((atk_forme, atk), (def_forme, dfn)):
        if f != st.get("species"):
            abil |= set(((d["s"].get(f) or {}).get("abilities") or {}).values())
    if abil & WEATHER_ABILITIES_DMG:
        return True
    types = (d["s"].get(def_forme) or {}).get("types") or []
    return ("sand" in w and "Rock" in types and m["category"] == "Special") or (("snow" in w or "hail" in w) and "Ice" in types and m["category"] == "Physical")


def _calc_set(s: dict, keep: tuple = STATS, move: str | None = None) -> dict:


    out = {k: s.get(k) for k in ("species", "item", "ability", "nature", "moves")}
    out["evs"] = {k: (s.get("evs") or {}).get(k, 0) if k in keep else 0 for k in STATS}
    if move:
        out["moves"] = [move]
    if s.get("ivs"):
        out["ivs"] = s["ivs"]
    out["nature"] = out["nature"] or "Serious"
    return out


def _damaging(d: dict, mv: str) -> dict | None:
    m = d["m"].get(mv)
    if not m or m["category"] == "Status":
        return None
    return m


def _grid(cases: list[dict], key: str, vals_of, need) -> list[list[list[int]] | None]:


    lo_hi = [dict(c, **{key: [vals_of(c)[0], vals_of(c)[-1]]}) for c in cases]
    first = _calc(lo_hi)
    full_idx = [i for i, r in enumerate(first) if "error" not in r and need(cases[i], r[key.replace("Vals", "Rolls")])]
    full = _calc([dict(cases[i], **{key: vals_of(cases[i])}) for i in full_idx])
    out: list = [None] * len(cases)
    for i, r in enumerate(first):
        if "error" in r:
            continue
        rr = r[key.replace("Vals", "Rolls")]
        vals = vals_of(cases[i])

        out[i] = [rr[0] if k < len(vals) / 2 else rr[1] for k in range(len(vals))]
    for i, r in zip(full_idx, full):
        if "error" not in r:
            out[i] = r[key.replace("Vals", "Rolls")]
    return out


def _ko(rolls: np.ndarray, hp: np.ndarray) -> np.ndarray:

    r = rolls[None, ...]
    h = hp.reshape((-1,) + (1,) * rolls.ndim)[..., 0]
    return np.stack([(r >= h[..., None]).mean(-1), (2 * r >= h[..., None]).mean(-1)])


def _mix(a: np.ndarray, t: float) -> np.ndarray:

    return a[0] + t * (a[1] - a[0])




def _trick_room(s: dict) -> bool:
    return (s.get("ivs") or {}).get("spe", 31) == 0 or PLUSMINUS.get(s.get("nature") or "", (None, None))[1] == "spe"


def _natures(s: dict, uses: set[str], tr: bool) -> list[str]:


    nat = s.get("nature") or "Serious"
    minus = [x for x in ("atk", "spa") if x not in uses] + (["spe"] if tr else [])
    plus = ["def", "spd", *sorted(uses)] + ([] if tr else ["spe"])
    out = [nat]
    for m in minus:
        for p in plus:
            if p != m and NATURES.get((p, m)) and NATURES[(p, m)] not in out:
                out.append(NATURES[(p, m)])
    return out


def _holds_stone(d: dict, s: dict) -> bool:

    return forme(d, s, True) != (s["species"] if s["species"] in d["s"] else s["species"].split("-Mega")[0])


def _scenarios(mine: dict, team: list[dict], d: dict) -> list[tuple[float, str, tuple]]:




    holders = [s for s in team if _holds_stone(d, s)]
    base = mine["species"] if mine["species"] in d["s"] else mine["species"].split("-Mega")[0]
    if not holders:
        return [(1.0, base, own_weather(team, d, None))]
    out: dict = {}
    for h in holders:
        f = forme(d, mine, True) if h is mine else base
        key = (f, own_weather(team, d, h))
        out[key] = out.get(key, 0.0) + 1.0 / len(holders)
    return sorted(((w, f, wt) for (f, wt), w in out.items()), key=lambda x: (-x[0], x[1] == base))


def tune_mon(mine: dict, team: list[dict], field: list[dict], r: dict, usage: dict, log=print) -> dict:






    d = dex(r["fmt"])
    scen = _scenarios(mine, team, d)
    ivs = {k: (mine.get("ivs") or {}).get(k, 31) for k in STATS}
    moves = [(mv, m) for mv in mine.get("moves") or [] if (m := _damaging(d, mv))]
    uses = {("def" if m["oo"] == "def" else "atk" if m["category"] == "Physical" else "spa") for _, m in moves if not m["oop"] and not m["damage"]}
    uses.discard("def")
    tr = _trick_room(mine)
    nats = _natures(mine, uses, tr)
    bases = [d["s"][f]["base"] for _, f, _ in scen]

    grid = {n: {st: sorted({i for b in bases for i, _ in levels(r, b[st], st, n, ivs[st])}) for st in STATS} for n in nats}
    var = [variants(e["set"], usage, r, e.get("mega_p", 1.0), forme(d, e["set"], True)) for e in field]
    tot_w = sum(e["w"] for e in field) or 1.0

    groups: dict[tuple, list[int]] = {}
    gw: dict[tuple, float] = {}
    for ui in range(len(field)):
        for vi, (vs, vw) in enumerate(var[ui]):
            g = (ui, forme(d, vs, True))
            groups.setdefault(g, []).append(vi)
            gw[g] = gw.get(g, 0.0) + field[ui]["w"] * vw / tot_w
    my_scarf = (mine.get("item") or "") == "Choice Scarf"
    foe_spe = {}
    for ui in range(len(field)):
        for vi, (vs, _) in enumerate(var[ui]):
            v = stat_value(r, d["s"][forme(d, vs, True)]["base"]["spe"], "spe", vs["evs"].get("spe", 0), vs["nature"], (vs.get("ivs") or {}).get("spe", 31))
            foe_spe[(ui, vi)] = v * 3 // 2 if (vs.get("item") or "") == "Choice Scarf" else v

    def one(my_forme: str, b: dict, ours: tuple) -> dict:

        lv = {n: {st: [(i, stat_value(r, b[st], st, i, n, ivs[st])) for i in grid[n][st]] for st in STATS} for n in nats}
        dvals = {st: sorted({v for n in nats for _, v in lv[n][st]}) for st in ("def", "spd", "atk", "spa")}
        hp_vals = np.array([v for _, v in lv[nats[0]]["hp"]])
        cases, meta = [], []
        for ui, e in enumerate(field):
            for vi, (vs, _) in enumerate(var[ui]):
                wt, te = _attacker_field(vs, d, True, ours)
                for mv in vs.get("moves") or []:
                    m = _damaging(d, mv)
                    if not m:
                        continue
                    st = m["od"] or ("def" if m["category"] == "Physical" else "spd")
                    ast = m["oo"] or ("atk" if m["category"] == "Physical" else "spa")
                    af, df = forme(d, vs, True), my_forme
                    cases.append({"format": r["fmt"], "atk": _calc_set(vs, (ast, "spe"), mv), "def": _calc_set(mine, ("hp", "def", "spd")),
                                  "atkForme": af, "defForme": df, "move": mv, "spread": m["target"] in SPREAD_TARGETS,
                                  "weather": wt if _weather_matters(d, wt, mv, m, af, df, vs, mine) else None, "terrain": te, "defVals": dvals[st]})
                    meta.append((ui, vi, st, mv))
        hp_lo, hp_hi = int(hp_vals.min()), int(hp_vals.max())
        need = lambda c, rr: not (min(rr[1]) >= hp_hi or 2 * max(rr[0]) < hp_lo)
        log(f"{mine['species']} as {my_forme}: {len(cases)} hits on it")
        rolls = _grid(cases, "defVals", lambda c: c["defVals"], need)
        risk: dict = {}
        for (ui, vi, st, mv), rr in zip(meta, rolls):
            if rr is not None:
                risk.setdefault((ui, vi), {}).setdefault(st, []).append((_ko(np.array(rr, dtype=float), hp_vals), mv))
        ocases, ometa = [], []
        for ui, e in enumerate(field):
            for vi, (vs, _) in enumerate(var[ui]):
                for mv, m in moves:
                    if m["oop"] or m["damage"] or m["oo"] == "def":
                        continue
                    st = "atk" if m["category"] == "Physical" else "spa"
                    af, df = my_forme, forme(d, vs, True)
                    ocases.append({"format": r["fmt"], "atk": _calc_set(mine, (st, "spe"), mv), "def": _calc_set(vs, ("hp", "def", "spd", "spe")),
                                   "atkForme": af, "defForme": df, "move": mv, "spread": m["target"] in SPREAD_TARGETS,
                                   "weather": ours[0] if _weather_matters(d, ours[0], mv, m, af, df, mine, vs) else None, "terrain": ours[1],
                                   "atkVals": dvals[st]})
                    ometa.append((ui, vi, st, mv))
        log(f"{mine['species']} as {my_forme}: {len(ocases)} of its hits")
        first = _calc([dict(c, atkVals=[c["atkVals"][0], c["atkVals"][-1]]) for c in ocases])
        hp_of = [x["def"]["hp"] if "error" not in x else 1 for x in first]
        need_o = [i for i, x in enumerate(first) if "error" not in x and not (min(x["atkRolls"][0]) >= hp_of[i] or 2 * max(x["atkRolls"][1]) < hp_of[i])]
        full = dict(zip(need_o, _calc([ocases[i] for i in need_o])))
        reach: dict = {}
        for i, ((ui, vi, st, mv), x) in enumerate(zip(ometa, first)):
            if "error" in x:
                continue
            n_v = len(ocases[i]["atkVals"])
            rr = full[i]["atkRolls"] if i in full and "error" not in full[i] else [x["atkRolls"][0] if k < n_v / 2 else x["atkRolls"][1] for k in range(n_v)]
            reach.setdefault((ui, vi), {}).setdefault(st, []).append((_ko(np.array(rr, dtype=float), np.array([hp_of[i]]))[:, 0], mv))
        return {"lv": lv, "dvals": dvals, "hp_vals": hp_vals, "risk": risk, "reach": reach, "n_on": len(cases), "n_by": len(ocases)}

    S = [one(f, b, wt) for (_, f, wt), b in zip(scen, bases)]

    def ledgers_one(c: dict, n: str, t: float) -> dict:




        lv, dvals = c["lv"], c["dvals"]
        ix = {st: np.array([dvals[st].index(v) for _, v in lv[n][st]]) for st in ("def", "spd", "atk", "spa")}
        spe = np.array([v for _, v in lv[n]["spe"]]) * (3 / 2 if my_scarf else 1)
        E = len(spe)
        shape_b = (len(c["hp_vals"]), len(ix["def"]), len(ix["spd"]))
        K_shape = (len(ix["atk"]), len(ix["spa"]))
        R = np.zeros(shape_b)
        K = np.zeros(K_shape)





        dR = np.zeros((E + 1,) + shape_b, dtype=np.float32)
        dK = np.zeros((E + 1,) + K_shape, dtype=np.float32)
        for g, vis in groups.items():
            ui = g[0]
            rus, kus, fvs = [], [], []
            for vi in vis:
                by_st = c["risk"].get((ui, vi), {})
                pd = np.max([_mix(a, t) for a, _ in by_st["def"]], 0)[:, ix["def"]][:, :, None] if "def" in by_st else 0.0
                ps = np.max([_mix(a, t) for a, _ in by_st["spd"]], 0)[:, ix["spd"]][:, None, :] if "spd" in by_st else 0.0
                rus.append(np.broadcast_to(np.maximum(pd, ps), shape_b))
                by_st = c["reach"].get((ui, vi), {})
                pa = np.max([_mix(a, t) for a, _ in by_st["atk"]], 0)[ix["atk"]][:, None] if "atk" in by_st else 0.0
                pp = np.max([_mix(a, t) for a, _ in by_st["spa"]], 0)[ix["spa"]][None, :] if "spa" in by_st else 0.0
                kus.append(np.broadcast_to(np.maximum(pa, pp), K_shape))
                fvs.append(foe_spe[(ui, vi)])
            w = gw[g]
            r_g, k_g = np.max(rus, 0), np.min(kus, 0)
            R += w * r_g
            K += w * k_g

            order = sorted(range(len(vis)), key=lambda i: -fvs[i] if not tr else fvs[i])
            run = np.zeros(shape_b)
            for i in order:
                step = np.maximum(run, rus[i]) - run
                run = run + step
                if not tr:
                    last = int(np.searchsorted(spe, fvs[i], side="right")) - 1
                    if last >= 0:
                        dR[last] += np.float32(w) * step
                else:
                    first_e = int(np.searchsorted(spe, fvs[i], side="left"))
                    if first_e < E:
                        dR[first_e] += np.float32(w) * step

            if not tr:
                e0 = int(np.searchsorted(spe, max(fvs), side="right"))
                if e0 < E:
                    dK[e0] += np.float32(w) * k_g
            else:
                e1 = int(np.searchsorted(spe, min(fvs), side="left")) - 1
                if e1 >= 0:
                    dK[e1] += np.float32(w) * k_g
        if not tr:
            SR = np.cumsum(dR[:E][::-1], 0)[::-1]
            SK = np.cumsum(dK[:E], 0)
        else:
            SR = np.cumsum(dR[:E], 0)
            SK = np.cumsum(dK[:E][::-1], 0)[::-1]
        return {"R": R, "K": K, "SR": np.moveaxis(SR, 0, -1).copy(), "SK": np.moveaxis(SK, 0, -1).copy(), "ix": ix}

    def ledgers(n: str, t: float) -> dict:

        parts = [ledgers_one(c, n, t) for c in S]
        out = {k: sum(w * p[k] for (w, _, _), p in zip(scen, parts)) for k in ("R", "K", "SR", "SK")}
        lv0 = S[0]["lv"][n]
        out.update(inv={st: np.array([i for i, _ in lv0[st]]) for st in STATS}, val={st: np.array([v for _, v in lv0[st]]) for st in STATS},
                   ix=[p["ix"] for p in parts])
        return out

    def per_mon(n: str, idx: dict) -> dict:



        L = led[n]
        rows: dict = {}
        for (w_s, f_s, _), c, ix in zip(scen, S, L["ix"]):
            for g, vis in groups.items():
                ui = g[0]
                risk, risk_mv, reach, reach_mv = 0.0, None, None, None
                for vi in vis:
                    for st in ("def", "spd"):
                        for a, mv in c["risk"].get((ui, vi), {}).get(st, []):
                            x = float(a[0][idx["hp"], ix[st][idx[st]]])
                            if x > risk:
                                risk, risk_mv = x, mv
                    best, best_mv = 0.0, None
                    for st in ("atk", "spa"):
                        for a, mv in c["reach"].get((ui, vi), {}).get(st, []):
                            x = float(a[0][ix[st][idx[st]]])
                            if x > best:
                                best, best_mv = x, mv
                    if reach is None or best < reach:
                        reach, reach_mv = best, best_mv
                key = (g, f_s)
                row = rows.setdefault(key, {"risk": 0.0, "risk_mv": None, "reach": 1.0, "reach_mv": None, "w": gw[g]})
                if risk >= row["risk"]:
                    row["risk"], row["risk_mv"] = risk, risk_mv or row["risk_mv"]
                if (reach or 0.0) <= row["reach"]:
                    row["reach"], row["reach_mv"] = reach or 0.0, reach_mv or row["reach_mv"]
        return rows

    led = {n: ledgers(n, TWO_HKO) for n in nats}
    show = {n: ledgers(n, 0.0) for n in nats}

    def shown(n: str, idx: dict) -> dict:
        x = _point_at(show[n], idx)
        return {k: round(v, 4) for k, v in x.items() if k != "idx"}
    cur_inv = {k: (mine.get("evs") or {}).get(k, 0) for k in STATS}
    cur = _point(led[nats[0]], cur_inv)
    formes = sorted({f for _, f, _ in scen}, key=lambda f: [x[1] for x in scen].index(f))
    out = {"species": mine["species"], "forme": scen[0][1], "item": mine.get("item") or "", "nature": nats[0], "evs": cur_inv,
           "stats": {st: int(led[nats[0]]["val"][st][cur["idx"][st]]) for st in STATS}, "trick_room": tr, "uses": sorted(uses),
           "current": cur, "presets": {}, "hits_on": sum(c["n_on"] for c in S), "hits_by": sum(c["n_by"] for c in S),
           "formes": formes if len(formes) > 1 else [],
           "scenarios": [{"w": round(w, 3), "forme": f, "weather": wt[0], "terrain": wt[1]} for w, f, wt in scen]}
    for name, (wts, keep, tol) in PRESETS.items():
        best = None
        cons = {"risk": cur["risk"] + tol if "risk" in keep else None, "reach": cur["reach"] - tol if "reach" in keep else None,
                "spe": out["stats"]["spe"] if "speed" in keep else None, "tr": tr, "near": cur_inv,
                "first": (cur["first_ko"], cur["ko_before"]) if "first" in keep else None}
        for n in nats:
            x = _best(led[n], wts, r, unused=[st for st in ("atk", "spa") if st not in uses], cons=cons)
            if x is None:
                continue
            if n != nats[0]:
                x["score"] -= NEAR
            if best is None or x["score"] > best["score"] + 1e-12:
                best = dict(x, nature=n)
        if best is not None:
            best["show"] = shown(best["nature"], best["idx"])
        out["presets"][name] = best
    out["current"]["show"] = shown(nats[0], cur["idx"])
    for p in out["presets"].values():
        if p is not None and all(abs(p["show"][k] - out["current"]["show"][k]) < 0.005 for k in ("risk", "reach", "first_ko", "ko_before")):
            p.update(nature=nats[0], idx=cur["idx"], evs=dict(cur_inv), show=dict(out["current"]["show"]),
                     stats={st: int(led[nats[0]]["val"][st][cur["idx"][st]]) for st in STATS})
    base_rows = per_mon(nats[0], cur["idx"])
    base_spe = out["stats"]["spe"]
    for name, p in out["presets"].items():
        if p is None:
            continue
        rows = per_mon(p["nature"], p["idx"])
        p["changes"] = _changes(base_rows, rows, base_spe, p["stats"]["spe"], field, var, foe_spe, groups, d, tr, len(formes) > 1)
    return out


def _point(L: dict, inv: dict) -> dict:

    return _point_at(L, {st: max(0, int(np.searchsorted(L["inv"][st], inv.get(st, 0), side="right") - 1)) for st in STATS})


def _point_at(L: dict, idx: dict) -> dict:


    h, d, s, a, p, e = (idx[k] for k in ("hp", "def", "spd", "atk", "spa", "spe"))
    return {"risk": float(L["R"][h, d, s]), "reach": float(L["K"][a, p]), "first_ko": float(L["SK"][a, p, e]),
            "ko_before": float(L["SR"][h, d, s, e]), "idx": idx}


def _changes(a: dict, b: dict, spe0: int, spe1: int, field: list[dict], var: list, foe_spe: dict, groups: dict, d: dict, tr: bool,
             our_formes: bool, step: float = 0.25) -> dict:





    tot = sum(e["w"] for e in field) or 1.0
    out = {"safe": [], "ko_by": [], "kos": [], "no_ko": [], "faster": [], "slower": []}
    for key in sorted(set(a) | set(b), key=lambda k: -(a.get(k) or b.get(k))["w"]):
        x, y = a.get(key), b.get(key)
        if x is None or y is None:
            continue
        (ui, who), ours = key
        base = {"who": who, "ours": ours if our_formes else None, "w": round(x["w"], 4)}
        if x["risk"] - y["risk"] >= step:
            out["safe"].append(dict(base, move=x["risk_mv"], **{"from": x["risk"], "to": y["risk"]}))
        elif y["risk"] - x["risk"] >= step:
            out["ko_by"].append(dict(base, move=y["risk_mv"], **{"from": x["risk"], "to": y["risk"]}))
        if y["reach"] - x["reach"] >= step:
            out["kos"].append(dict(base, move=y["reach_mv"], **{"from": x["reach"], "to": y["reach"]}))
        elif x["reach"] - y["reach"] >= step:
            out["no_ko"].append(dict(base, move=x["reach_mv"], **{"from": x["reach"], "to": y["reach"]}))
    relevant = {k[0] for k in set(a) | set(b) if max((a.get(k) or {}).get("risk", 0), (a.get(k) or {}).get("reach", 0),
                                                       (b.get(k) or {}).get("risk", 0), (b.get(k) or {}).get("reach", 0)) >= step}
    for g, vis in groups.items():
        if g not in relevant:
            continue
        ui, who = g
        fv = (min if tr else max)(foe_spe[(ui, vi)] for vi in vis)
        w = round(sum(field[ui]["w"] * var[ui][vi][1] for vi in vis) / tot, 4)
        before, after = (spe0 > fv, spe1 > fv) if not tr else (spe0 < fv, spe1 < fv)
        if after and not before:
            out["faster"].append({"who": who, "spe": fv, "w": w})
        elif before and not after:
            out["slower"].append({"who": who, "spe": fv, "w": w})
    for k in ("safe", "ko_by", "kos", "no_ko"):
        merged: dict = {}
        for x in out[k]:
            mk = (x["who"], x["move"], x["ours"], round(16 * x["from"]), round(16 * x["to"]))
            if mk in merged:
                merged[mk]["w"] = round(merged[mk]["w"] + x["w"], 4)
            else:
                merged[mk] = x
        out[k] = sorted(merged.values(), key=lambda x: -x["w"])
    for k in ("faster", "slower"):
        merged = {}
        for x in out[k]:
            m = merged.setdefault((x["who"], x["spe"]), dict(x, w=0.0))
            m["w"] = round(m["w"] + x["w"], 4)
        out[k] = sorted(merged.values(), key=lambda x: -x["w"])
    _ = d
    return out


def _best(L: dict, wts: tuple, r: dict, unused: list[str], cons: dict) -> dict | None:





    wr, wk, ws = wts
    inv, total = L["inv"], r["total"]
    step = 1 if r["points"] else 4
    nb = total // step + 1
    near = cons.get("near") or {}
    dist = lambda st: np.abs(inv[st] - near.get(st, 0)) * NEAR / total
    c_b = (inv["hp"][:, None, None] + inv["def"][None, :, None] + inv["spd"][None, None, :]) // step
    v_b0 = -wr * L["R"] - dist("hp")[:, None, None] - dist("def")[None, :, None] - dist("spd")[None, None, :]
    if cons.get("risk") is not None:
        v_b0 = np.where(L["R"] <= cons["risk"] + 1e-9, v_b0, -np.inf)
    a_ok = np.arange(len(inv["atk"])) if "atk" not in unused else np.array([0])
    p_ok = np.arange(len(inv["spa"])) if "spa" not in unused else np.array([0])
    c_o = (inv["atk"][a_ok][:, None] + inv["spa"][p_ok][None, :]) // step
    K = L["K"][np.ix_(a_ok, p_ok)]
    v_o0 = wk * K - dist("atk")[a_ok][:, None] - dist("spa")[p_ok][None, :]
    if cons.get("reach") is not None:
        v_o0 = np.where(K >= cons["reach"] - 1e-9, v_o0, -np.inf)
    spe_ok = np.ones(len(inv["spe"]), dtype=bool)
    if cons.get("spe") is not None:
        spe_ok = L["val"]["spe"] <= cons["spe"] if cons.get("tr") else L["val"]["spe"] >= cons["spe"]
    first = cons.get("first")
    ij = np.arange(nb)[:, None] + np.arange(nb)[None, :]
    best = None
    for e in np.nonzero(spe_ok)[0]:
        left = (total - int(inv["spe"][e])) // step
        if left < 0:
            continue
        SR, SK = L["SR"][..., e], L["SK"][np.ix_(a_ok, p_ok, [e])][..., 0]
        v_b = v_b0 - ws * SR if ws else v_b0
        v_o = v_o0 + ws * SK if ws else v_o0
        if first is not None:
            v_b = np.where(SR <= first[1] + 1e-6, v_b, -np.inf)
            v_o = np.where(SK >= first[0] - 1e-6, v_o, -np.inf)
        bb, ob = _per_cost(c_b, v_b, nb), _per_cost(c_o, v_o, nb)
        tot = np.where(ij <= left, bb[0][:, None] + ob[0][None, :], -np.inf) - dist("spe")[e]
        k = int(np.argmax(tot))
        if not np.isfinite(tot.flat[k]):
            continue
        if best is None or tot.flat[k] > best[0] + 1e-12:
            i, j = np.unravel_index(k, tot.shape)
            best = (float(tot.flat[k]), int(bb[1][i]), int(ob[1][j]), int(e))
    if best is None:
        return None
    _, fb, fo, e = best
    bi = np.unravel_index(fb, c_b.shape)
    oi = np.unravel_index(fo, c_o.shape)
    idx = {"hp": int(bi[0]), "def": int(bi[1]), "spd": int(bi[2]), "atk": int(a_ok[oi[0]]), "spa": int(p_ok[oi[1]]), "spe": e}

    for st in ("hp", "def", "spd"):
        spent = sum(int(inv[k][idx[k]]) for k in STATS)
        while idx[st] + 1 < len(inv[st]) and spent - int(inv[st][idx[st]]) + int(inv[st][idx[st] + 1]) <= total:
            spent += int(inv[st][idx[st] + 1]) - int(inv[st][idx[st]])
            idx[st] += 1
    x = _point_at(L, idx)
    return {"evs": {st: int(inv[st][idx[st]]) for st in STATS}, "stats": {st: int(L["val"][st][idx[st]]) for st in STATS},
            **{k: v for k, v in x.items() if k != "idx"}, "idx": idx,
            "score": -wr * x["risk"] + wk * x["reach"] + ws * (x["first_ko"] - x["ko_before"])}


def _per_cost(cost: np.ndarray, val: np.ndarray, nb: int) -> tuple[np.ndarray, np.ndarray]:

    c = cost.ravel()
    v = val.ravel()
    best = np.full(nb, -np.inf)
    arg = np.zeros(nb, dtype=np.int64)
    ok = np.nonzero(np.isfinite(v) & (c < nb))[0]
    if len(ok):
        order = ok[np.lexsort((-v[ok], c[ok]))]
        cs = c[order]
        head = np.r_[True, cs[1:] != cs[:-1]]
        best[cs[head]] = v[order[head]]
        arg[cs[head]] = order[head]
    for b in range(1, nb):
        if best[b - 1] >= best[b]:
            best[b], arg[b] = best[b - 1], arg[b - 1]
    return best, arg




def tune_team(team: list[dict], field: list[tuple[str, list[dict]]], weights: list[float] | None, fmt: str | None, log=print,
              progress=None) -> dict:


    from vgc_trainer.showdown.teams import to_paste
    r = rules(fmt)
    usage = usage_spreads(r["fmt"])
    fs = field_sets(field, weights)
    _MEMO.clear()
    d = dex(r["fmt"])
    spreads_seen: dict = {}
    for e in fs:
        for vs, _ in variants(e["set"], usage, r, 1.0, forme(d, e["set"], True)):
            row = spreads_seen.setdefault(forme(d, e["set"], True), {"bucket": [], "ladder": []})
            sp = {"nature": vs["nature"], "evs": {k: vs["evs"].get(k, 0) for k in STATS}}
            lst = row["bucket" if vs.get("_src") == "sheet" else "ladder"]
            if sp not in lst:
                lst.append(sp)
    mons = []
    for k, s in enumerate(team):
        if progress:
            progress(k, len(team), s["species"])
        try:
            m = tune_mon(s, team, fs, r, usage, log=log)
        except Exception as e:
            mons.append({"species": s["species"], "error": str(e)[:200], "sets": {"current": to_paste([s]).strip()}})
            continue
        m["sets"] = {"current": to_paste([s]).strip()}
        seen: dict[str, str] = {}
        for name, p in m["presets"].items():
            if p is not None:
                p["same"] = p["nature"] == m["nature"] and all(p["evs"][x] == m["evs"].get(x, 0) for x in STATS)

                key = json.dumps([p["nature"], p["evs"]], sort_keys=True)
                counts = json.dumps([round(100 * p["show"][k]) for k in ("risk", "reach", "first_ko", "ko_before")])
                p["dup"] = seen.get(key) or seen.get(counts)
                seen.setdefault(key, name)
                seen.setdefault(counts, name)
                m["sets"][name] = to_paste([dict(s, nature=p["nature"], evs=dict(p["evs"]))]).strip()
        mons.append(m)
    _MEMO.clear()
    return {"format": r["fmt"], "points": r["points"], "total": r["total"], "cap": r["cap"], "field_sets": len(fs), "teams": len(field),
            "usage": bool(usage), "mons": mons, "presets": list(PRESETS),
            "field_spreads": [{"who": k, **v} for k, v in sorted(spreads_seen.items())]}

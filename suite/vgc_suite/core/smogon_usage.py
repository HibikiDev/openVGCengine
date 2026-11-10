















from __future__ import annotations

import gzip
import json
import re
import subprocess
from pathlib import Path
from vgc_trainer.winproc import NO_WINDOW
from vgc_trainer.formats import CURRENT

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "tools/corpus/.cache/smogon-stats/chaos"
SNAPSHOT = ROOT / "data/smogon-usage"
FORMAT = CURRENT
_DEX: dict = {}


def cached(fmt: str = FORMAT, cutoff: int = 1630) -> tuple[str, Path] | None:

    found = []
    for month in sorted((p.name for p in CACHE.glob("20*-*")), reverse=True):
        f = CACHE / month / f"{fmt}-{cutoff}.json.gz"
        if f.exists():
            found.append((month, f))
            break
    try:
        manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf8"))
    except (OSError, ValueError):
        manifest = {"files": []}
    found += [(e["month"], SNAPSHOT / e["file"]) for e in manifest["files"]
              if e["format"] == fmt and e["cutoff"] == cutoff and (SNAPSHOT / e["file"]).exists()]
    return max(found, key=lambda mf: mf[0]) if found else None


def _dex(names: list[str]) -> dict:


    if not _DEX.get("ok") or any(n not in _DEX["species"] for n in names):
        js = ("const {Dex}=require('./tools/showdown-oracle/lib/showdown');const D=Dex.mod('champions');const names=" + json.dumps(names) + ";"
              "const o={items:{},moves:{},abilities:{},natures:{},species:{}};"
              "for(const x of D.items.all())o.items[x.id]=x.name;for(const x of D.moves.all())o.moves[x.id]={n:x.name,c:x.category};"
              "for(const x of D.abilities.all())o.abilities[x.id]=x.name;for(const x of D.natures.all())o.natures[x.name]={p:x.plus||null,m:x.minus||null};"
              "for(const n of names){const s=D.species.get(n);o.species[n]=s.exists?{base:s.baseSpecies,mega:!!(s.forme&&s.forme.startsWith('Mega')),"
              "stone:s.requiredItem||null}:null}console.log(JSON.stringify(o))")
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf8", check=True, cwd=ROOT, **NO_WINDOW)
        _DEX.clear()
        _DEX.update(json.loads(r.stdout), ok=True)
    return _DEX


def candidates(five: list[dict], top: int, skip: set[str] = frozenset(), kind: str = "any", fmt: str = FORMAT,
               cutoff: int = 1630) -> tuple[list[tuple[str, dict]], str | None]:


    from .sixth import _base, _item
    got = cached(fmt, cutoff)
    if got is None:
        return [], None
    month, path = got
    data = json.loads(gzip.open(path).read())["data"]
    names = [n for n, m in sorted(data.items(), key=lambda kv: -float(kv[1].get("usage") or 0)) if float(m.get("usage") or 0) > 0.002]
    dex = _dex(names)
    have = {_base(x["species"]) for x in five} | {_base(k) for k in skip}
    held = {_item(x) for x in five if _item(x)}
    out = []
    for n in names:
        sp = dex["species"].get(n)
        if not sp or _base(sp["base"]) in have or _base(sp["base"]) in {_base(s["species"]) for _, s in out}:
            continue
        if (kind == "mega" and not sp["mega"]) or (kind == "plain" and sp["mega"]):
            continue
        s = _build(n, sp, data[n], dex, held)
        if s is not None:
            out.append((f"{n}", s))
        if len(out) >= top:
            break
    return out, month


def _top(d: dict, ok=lambda k: True):
    return next((k for k, _ in sorted(d.items(), key=lambda kv: -float(kv[1] or 0)) if k and ok(k)), None)


def _build(name: str, sp: dict, m: dict, dex: dict, held: set[str]) -> dict | None:

    spread = _top(m.get("Spreads") or {}, lambda k: ":" in k)
    if spread is None:
        return None
    nature, pts = spread.split(":", 1)
    pts = [int(x) for x in pts.split("/")]
    if sp["mega"]:
        item = sp["stone"]
    else:
        iid = _top(m.get("Items") or {}, lambda k: k != "nothing" and k not in held and not re.search(r"ite[xyz]?$", k))
        item = dex["items"].get(iid, "") if iid else ""
    if item.replace(" ", "").lower() in held:
        return None
    ability = dex["abilities"].get(_top(m.get("Abilities") or {}) or "", "")
    nat = dex["natures"].get(nature, {})
    choice = item.replace(" ", "").lower()
    off = "Special" if choice == "choiceband" or nat.get("p") == "atk" or nat.get("m") == "spa" else \
        "Physical" if choice == "choicespecs" or nat.get("p") == "spa" or nat.get("m") == "atk" else None
    attacks_only = choice.startswith("choice") or choice == "assaultvest"
    scored = []
    for mid, w in (m.get("Moves") or {}).items():
        mv = dex["moves"].get(mid)
        if not mid or mid == "nothing" or mv is None or (attacks_only and mv["c"] == "Status"):
            continue
        scored.append((float(w) * (0.1 if off and mv["c"] == off else 1.0), mv["n"]))
    moves = [n for _, n in sorted(scored, reverse=True)[:4]]
    if len(moves) < 4:
        return None
    return {"name": sp["base"], "species": sp["base"], "item": item, "ability": ability, "moves": moves, "nature": nature,
            "evs": dict(zip(("hp", "atk", "def", "spa", "spd", "spe"), pts)), "level": 50}

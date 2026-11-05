
















from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from vgc_trainer.winproc import NO_WINDOW

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / "sprites"
EXTS = {".png", ".gif", ".webp", ".jpg", ".jpeg", ".svg"}
NOISE = {"menu", "champs", "champions", "sv", "icon", "icons", "sprite", "sprites", "pokemon", "box", "mini", "home", "normal", "regular"}
SYNONYMS = {"female": "f", "male": "", "alolan": "alola", "galarian": "galar", "hisuian": "hisui", "paldean": "paldea", "jumbo": "super"}
SKIP = {"shiny", "back"}
_DEX: list[dict] = []


def to_id(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def dex() -> list[dict]:

    if not _DEX:
        js = ("const {Dex}=require('./tools/showdown-oracle/lib/showdown');const D=Dex.mod('champions');const o=[],seen=new Set();"
              "const add=s=>{if(!s.exists||seen.has(s.name))return;seen.add(s.name);o.push({name:s.name,num:s.num,base:s.baseSpecies,"
              "forme:s.forme||'',baseForme:s.baseForme||'',spriteid:s.spriteid})};"
              "for(const s of D.species.all()){add(s);for(const c of s.cosmeticFormes||[])add(D.species.get(c))}console.log(JSON.stringify(o))")
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf8", check=True, cwd=ROOT, **NO_WINDOW)
        _DEX.extend(x for x in json.loads(r.stdout) if x["num"] > 0)
    return _DEX


def _words(stem: str) -> list[str]:
    s = unicodedata.normalize("NFKD", __import__("urllib.parse").parse.unquote(stem)).encode("ascii", "ignore").decode().lower()
    return [w for w in re.split(r"[^a-z0-9]+", s) if w]


def match(stem: str) -> tuple[str | None, str]:

    D = dex()
    by_sprite = {x["spriteid"]: x["name"] for x in D}
    by_id = {to_id(x["name"]): x["name"] for x in D}
    words = _words(stem)
    if SKIP & set(words):
        return None, "shiny / back sprite"
    if stem.lower() in by_sprite:
        return by_sprite[stem.lower()], "sprite id"
    if to_id(stem) in by_id:
        return by_id[to_id(stem)], "species name"
    words = [w for w in words if w not in NOISE]
    base, rest = None, []
    for i, w in enumerate(words):
        if w.isdigit() and len(w) <= 4 and int(w) > 0:
            bases = [x for x in D if x["num"] == int(w) and not x["forme"]]
            if bases:
                base, rest = bases[0]["name"], words[:i] + words[i + 1:]
                break
    if base is None:
        bases = {to_id(x["name"]): x["name"] for x in D if not x["forme"]}
        best = None
        for i in range(len(words)):
            for j in range(len(words), i, -1):
                if "".join(words[i:j]) in bases and (best is None or j - i > best[1] - best[0]):
                    best = (i, j)
        if best is None:
            return None, "no dex number or species name"
        base, rest = bases["".join(words[best[0]:best[1]])], words[:best[0]] + words[best[1]:]
    want = "".join(SYNONYMS.get(w, w) for w in rest if not w.isdigit())
    if not want:
        return base, "base"
    formes = {to_id(x["forme"]): x["name"] for x in D if x["base"] == base and x["forme"]}
    if want in formes:
        return formes[want], "forme"
    if "m" + want in formes:
        return formes["m" + want], "forme (male)"
    if want == to_id(next(x["baseForme"] for x in D if x["name"] == base)):
        return base, "base forme"
    if set(rest) <= {"female", "male", "f", "m"}:
        return None, f"{base}: a gender difference only (no Showdown forme)"
    pre = [n for f, n in formes.items() if f.startswith(want)]
    if len(pre) == 1:
        return pre[0], "forme prefix"
    return None, f"{base}: no forme '{'-'.join(rest)}'" + (f" (several start with it: {', '.join(pre)})" if pre else "")


def build_index(folder: Path | str = DEFAULT_DIR) -> dict:


    folder = Path(folder)
    names: dict[str, str] = {}
    unmatched: dict[str, str] = {}
    dupes: dict[str, str] = {}
    if folder.is_dir():
        for f in sorted(p for p in folder.rglob("*") if p.suffix.lower() in EXTS and p.is_file()):
            rel = f.relative_to(folder).as_posix()
            sp, why = match(f.stem)
            if sp is None:
                unmatched[rel] = why
            elif sp in names:
                dupes[rel] = sp
            else:
                names[sp] = rel
    fallback = []
    for x in dex() if names else []:

        if not x["forme"] and x["name"] not in names:
            own = [y["name"] for y in dex() if y["base"] == x["name"] and y["forme"] and "Mega" not in y["forme"] and y["name"] in names]
            if len(own) == 1:
                names[x["name"]] = names[own[0]]
                fallback.append(x["name"])
    if names:
        for x in dex():
            if x["name"] not in names and x["base"] in names:
                names[x["name"]] = names[x["base"]]
                fallback.append(x["name"])
    return {"names": names, "fallback": fallback, "unmatched": unmatched, "dupes": dupes}


def main() -> None:
    ap = argparse.ArgumentParser(description="Match a sprite folder to species names (the dashboard's optional icons).")
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    ap.add_argument("--check", action="store_true", help="list every file the rules could not place, and duplicates")
    a = ap.parse_args()
    idx = build_index(a.dir)
    own = len(idx["names"]) - len(idx["fallback"])
    print(f"{a.dir}: {own} species / formes with their own icon, {len(idx['fallback'])} more borrow their base species' icon, "
          f"{len(idx['unmatched'])} files unplaced, {len(idx['dupes'])} duplicates")
    if a.check:
        for f, why in idx["unmatched"].items():
            print(f"  unplaced  {f}: {why}")
        for f, sp in idx["dupes"].items():
            print(f"  duplicate {f}: {sp} already has {idx['names'][sp]}")


if __name__ == "__main__":
    sys.exit(main())

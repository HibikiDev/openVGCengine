



from __future__ import annotations

import json
import re
from pathlib import Path

from .tracker import to_id

_OUT = Path(__file__).resolve().parents[3] / "tools/corpus/out"


TEAM_FILES = [_OUT / f for f in (
    "teams-sets.json", "standings-sets-v2.json", "standings-sets-louisville.json", "standings-sets-recife.json", "standings-sets.json",
    "standings-sets-nice.json",
    "teams-vgc13.json", "teams-vgc14.json", "teams-vgc15.json", "teams-vgc16.json",
    "teams-vgc17.json", "teams-vgc18.json", "teams-vgc19.json",
    "teams-mix-vgc20.json", "teams-mix-vgc21.json", "teams-mix-vgc22.json",
    "teams-sv-regc.json", "teams-sv-regd.json", "teams-sv-regg.json", "teams-sv-regi.json")]


class UnknownTeam(ValueError):
    pass


def load_team(spec: str) -> list[dict]:

    path = Path(spec)
    if path.exists():
        return parse_paste(path.read_text(encoding="utf8"))
    for f in TEAM_FILES:
        if f.exists():
            for t in json.loads(f.read_text(encoding="utf8"))["teams"]:
                if t["id"] == spec:
                    return t["sets"]
    raise UnknownTeam(f"{spec!r} is neither a team file nor a team id in the library")

STATS = ("hp", "atk", "def", "spa", "spd", "spe")


def pack(sets: list[dict]) -> str:
    out = []
    for s in sets:
        evs = s.get("evs") or {}
        ivs = s.get("ivs") or {}
        fields = [
            s.get("name") or s["species"],
            s["species"],
            to_id(s.get("item") or ""),
            to_id(s.get("ability") or ""),
            ",".join(to_id(m) for m in s["moves"]),
            s.get("nature") or "",
            ",".join(str(evs.get(k, 0) or "") for k in STATS) if any(evs.values()) else "",
            s.get("gender") or "",
            ",".join("" if ivs.get(k, 31) == 31 else str(ivs[k]) for k in STATS) if any(ivs.get(k, 31) != 31 for k in STATS) else "",
            "",
            str(s["level"]) if s.get("level") and s["level"] != 100 else "",

            _misc(s),
        ]
        out.append("|".join(fields))
    return "]".join(out)


def _misc(s: dict) -> str:


    gmax = "G" if s.get("gigantamax") else ""
    level = str(s["dynamaxLevel"]) if s.get("dynamaxLevel") not in (None, 10) else ""
    tera = s.get("teraType") or ""
    return f",,,{gmax},{level},{tera}" if gmax or level or tera else ""


def unpack(buf: str) -> list[dict]:
    sets = []
    for chunk in buf.split("]"):
        f = chunk.split("|")
        if len(f) < 6:
            continue
        species = f[1] or f[0]

        s = {"name": f[0], "species": species, "item": f[2], "ability": f[3], "moves": [m for m in f[4].split(",") if m],
             "nature": f[5] if len(f) > 5 else ""}
        if len(f) > 6 and f[6]:
            vals = f[6].split(",")
            s["evs"] = {k: int(vals[i]) if i < len(vals) and vals[i] else 0 for i, k in enumerate(STATS)}
        if len(f) > 10 and f[10]:
            s["level"] = int(f[10])
        misc = f[11].split(",") if len(f) > 11 else []
        if len(misc) > 3 and misc[3]:
            s["gigantamax"] = True
        if len(misc) > 4 and misc[4]:
            s["dynamaxLevel"] = int(misc[4])
        if len(misc) > 5 and misc[5]:
            s["teraType"] = misc[5]
        sets.append(s)
    return sets


_STAT_NAMES = {"hp": "hp", "atk": "atk", "def": "def", "spa": "spa", "spd": "spd", "spe": "spe"}


_LABELS = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}


def to_paste(sets: list[dict], level: int = 50) -> str:


    blocks = []
    for st in sets:
        name, species = st.get("name") or st["species"], st["species"]
        head = species if name == species else f"{name} ({species})"
        if st.get("gender") in ("M", "F"):
            head += f" ({st['gender']})"
        if st.get("item"):
            head += f" @ {st['item']}"
        lines = [head]
        if st.get("ability"):
            lines.append(f"Ability: {st['ability']}")
        lines.append(f"Level: {st.get('level') or level}")
        evs = st.get("evs") or {}
        ev = " / ".join(f"{evs[k]} {_LABELS[k]}" for k in STATS if evs.get(k))
        if ev:
            lines.append(f"EVs: {ev}")
        if st.get("teraType"):
            lines.append(f"Tera Type: {st['teraType']}")
        if st.get("gigantamax"):
            lines.append("Gigantamax: Yes")
        if st.get("nature"):
            lines.append(f"{st['nature']} Nature")
        ivs = st.get("ivs") or {}
        iv = " / ".join(f"{ivs[k]} {_LABELS[k]}" for k in STATS if k in ivs and ivs[k] != 31)
        if iv:
            lines.append(f"IVs: {iv}")
        lines += [f"- {m}" for m in st.get("moves", [])]
        blocks.append("\n".join(ln + "  " for ln in lines))
    return "\n\n".join(blocks) + "\n"


def parse_paste(text: str) -> list[dict]:


    sets: list[dict] = []
    for block in [b for b in text.replace("\r", "").split("\n\n") if b.strip()]:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        head = lines[0]
        item = ""
        if " @ " in head:
            head, item = head.split(" @ ", 1)
        head = head.strip()
        gender = ""
        for g in ("(M)", "(F)"):
            if head.endswith(g):
                gender, head = g[1], head[: -len(g)].strip()
        name = species = head
        if head.endswith(")") and "(" in head:
            name, species = head[: head.rindex("(")].strip(), head[head.rindex("(") + 1 : -1].strip()
        s: dict = {"name": name, "species": species, "item": item.strip(), "ability": "", "moves": [], "nature": "", "evs": {}}
        if gender:
            s["gender"] = gender
        for ln in lines[1:]:
            if ln.startswith("- "):
                s["moves"].append(ln[2:].split(" / ")[0].strip())
            elif ln.startswith("Ability:"):
                s["ability"] = ln.split(":", 1)[1].strip()
            elif ln.startswith("Level:"):
                s["level"] = int(ln.split(":", 1)[1])
            elif ln.startswith("Tera Type:"):
                s["teraType"] = ln.split(":", 1)[1].strip()
            elif ln.startswith(("EVs:", "IVs:")):
                key = "evs" if ln.startswith("EVs:") else "ivs"
                vals = {}
                for part in ln.split(":", 1)[1].split("/"):
                    num, stat = part.split()
                    vals[_STAT_NAMES[stat.lower()]] = int(num)
                s[key] = vals
            elif ln.endswith(" Nature"):
                s["nature"] = ln[: -len(" Nature")].strip()
        sets.append(base_megas(s))
    return sets


_MEGA = re.compile(r"^(.+?)-Mega(-[XYZ])?$")

MEGA_BASE = {"Floette-Mega": "Floette-Eternal", "Meowstic-M-Mega": "Meowstic", "Tatsugiri-Curly-Mega": "Tatsugiri"}
_ABILITIES: dict | None = None


def base_megas(s: dict) -> dict:




    m = _MEGA.match(s["species"])
    if not m or not s.get("item", "").lower().endswith(("ite", "ite x", "ite y", "ite z")):
        return s
    global _ABILITIES
    if _ABILITIES is None:
        from collections import Counter, defaultdict

        _ABILITIES = defaultdict(Counter)
        path = _OUT / "standings-sets-v2.json"
        for t in (json.loads(path.read_text(encoding="utf8"))["teams"] if path.exists() else ()):
            for st in t["sets"]:
                _ABILITIES[st["species"]][st["ability"]] += 1
    base = MEGA_BASE.get(s["species"], m.group(1))
    seen = _ABILITIES.get(base)
    out = dict(s, species=base, name=base if s.get("name") == s["species"] else s.get("name"))
    if seen and seen.get(s.get("ability", ""), 0) < 3:
        out["ability"] = seen.most_common(1)[0][0]
    return out

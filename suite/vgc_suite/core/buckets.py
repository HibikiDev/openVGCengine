


















from __future__ import annotations

import json
import re
import time
from pathlib import Path

from vgc_suite.formats import MC, get as get_format

ROOT = Path(__file__).resolve().parents[3]
STORE = ROOT / "trainer/runs/team_buckets.json"
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}")
PASTE_RE = re.compile(r"https?://pokepast\.es/([0-9a-fA-F]+)/?(?:raw)?")
WEIGHT_RE = re.compile(r"\s+x\s*(\d+(?:\.\d+)?)\s*$", re.I)
MAX_TEAMS = 20
DEFAULT = "Default"
SEED = ROOT / "data/default_bucket.json"
SEEDED = ROOT / "trainer/runs/default_bucket.seeded"


def _load() -> dict:
    try:
        text = STORE.read_text(encoding="utf8")
    except OSError:
        return _seeded({})
    try:
        return _seeded(json.loads(text))
    except json.JSONDecodeError:
        return {}


def _seeded(d: dict) -> dict:

    if SEEDED.exists() or not SEED.is_file():
        return d
    if DEFAULT not in d:
        d[DEFAULT] = json.loads(SEED.read_text(encoding="utf8"))
        _save(d)
    SEEDED.touch()
    return d


def _save(d: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".part")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf8")
    tmp.replace(STORE)


def names(fmt: str | None = None) -> list[str]:

    d = _load()
    return sorted((k for k in d if fmt is None or d[k].get("format", MC) == fmt), key=str.lower)


def default_spec(fmt: str = MC) -> str | None:


    return f"bucket:{DEFAULT}" if SEED.is_file() and DEFAULT in names(fmt) else None


def format_of(name: str) -> str:

    return get(name).get("format", MC)


def summaries() -> list[dict]:

    d = _load()
    return [{"name": k, "note": d[k].get("note", ""), "updated": d[k].get("updated", ""), "format": d[k].get("format", MC),
             "teams": [{"label": t["label"], "weight": t["weight"], "species": t["species"], "src": t["src"]} for t in d[k]["teams"]]}
            for k in sorted(d, key=str.lower)]


def get(name: str) -> dict:
    d = _load()
    if name not in d:
        raise KeyError(f"no team bucket called {name!r}")
    return d[name]


def delete(name: str) -> None:
    d = _load()
    d.pop(name, None)
    _save(d)


def _weight(text: str) -> tuple[str, float]:
    m = WEIGHT_RE.search(text)
    if not m:
        return text.strip(), 1.0
    return text[:m.start()].strip(), float(m.group(1))


def parse(text: str) -> list[dict]:


    out = []
    for block in re.split(r"(?m)^\s*-{3,}\s*$", text.replace("\r", "")):
        lines = [ln for ln in block.split("\n")]
        label, weight = None, 1.0
        body = []
        for ln in lines:
            if ln.strip().startswith("#") and not any(x.strip() for x in body):
                label, weight = _weight(ln.strip().lstrip("#"))
                label = label or None
            else:
                body.append(ln)
        rest = [ln.strip() for ln in body if ln.strip()]
        if not rest:
            continue
        singles = [_weight(ln) for ln in rest]
        if all(PASTE_RE.fullmatch(s) or ID_RE.fullmatch(s) for s, _ in singles):
            one = len(singles) == 1
            for ln, (s, w) in zip(rest, singles):
                m = PASTE_RE.fullmatch(s)
                spec = f"paste:{m.group(1)}" if m else s
                lab = label if (label and one) else (f"pokepast {m.group(1)[:8]}" if m else s)
                out.append({"label": lab, "spec": spec, "weight": w if (WEIGHT_RE.search(ln) or not one) else weight,
                            "link": s if m else None})
        else:
            out.append({"label": label, "spec": "\n".join(body).strip() + "\n", "weight": weight, "link": None})
    for e in out:
        if not (0 < e["weight"] <= 100):
            raise ValueError(f"weight {e['weight']:g} for {e['label'] or 'a team'}: use a number above 0 (at most 100)")
    if len(out) > MAX_TEAMS:
        raise ValueError(f"{len(out)} teams: a bucket holds at most {MAX_TEAMS}")
    return out


def _resolve(spec: str, fmt: str = MC) -> tuple[str, list[dict]]:


    from .teams import read_team
    from .validator import _ready
    if spec.startswith("paste:"):
        from vgc_suite.buddy import _fetch_paste
        src = _fetch_paste(spec[6:]).replace("\r", "").strip() + "\n"
    else:
        src = spec
    sets = read_team(src, fmt)
    _ready(sets, fmt)
    return src, sets


def save(name: str, text: str, note: str = "", old_name: str | None = None, fmt: str = MC) -> tuple[dict, list[str]]:

    name = (name or "").strip()
    try:
        fmt = get_format(fmt).id
    except ValueError as e:
        return {}, [str(e)]
    if not NAME_RE.fullmatch(name):
        return {}, ["Name the bucket: letters, digits, spaces, '-', '_' or '.', up to 40 characters."]
    try:
        entries = parse(text)
    except ValueError as e:
        return {}, [str(e)]
    if not entries:
        return {}, ["Add at least one team."]
    prev_bucket = _load().get(old_name or name, {})

    old = {t["src"]: t for t in prev_bucket.get("teams", [])} if prev_bucket.get("format", MC) == fmt else {}
    teams, problems = [], []
    for k, e in enumerate(entries, 1):
        try:
            prev = old.get(e["spec"]) if not e["spec"].startswith("paste:") else next(
                (t for t in old.values() if t.get("link") and PASTE_RE.fullmatch(t["link"]) and
                 PASTE_RE.fullmatch(t["link"]).group(1) == e["spec"][6:]), None)
            if prev is not None:
                src, species = prev["src"], prev["species"]
                e["link"] = e.get("link") or prev.get("link")
            else:
                src, sets = _resolve(e["spec"], fmt)
                species = [s["species"] for s in sets]
        except SystemExit:
            problems.append(f"team {k} ({e['label'] or e['spec'][:30]}): no library team with that id")
            continue
        except Exception as ex:
            problems.append(f"team {k} ({e['label'] or e['spec'][:30].strip()}): {type(ex).__name__}: {str(ex)[:160]}")
            continue
        label = e["label"] or (e["spec"] if "\n" not in e["spec"] and not e["spec"].startswith("paste:") else "/".join(species[:3]) + "/...")
        teams.append({"label": label, "src": src, "link": e.get("link"), "weight": e["weight"], "species": species})
    if problems:
        return {}, problems
    d = _load()
    if old_name and old_name != name:
        d.pop(old_name, None)
    d[name] = {"note": note.strip()[:300], "updated": time.strftime("%Y-%m-%d %H:%M"), "teams": teams, "format": fmt}
    _save(d)
    return d[name], []


def to_text(name: str) -> str:

    blocks = []
    for t in get(name)["teams"]:
        w = "" if t["weight"] == 1 else f" x{t['weight']:g}"
        if "\n" in t["src"]:
            blocks.append(f"# {t['label']}{w}\n{t['src'].strip()}")
        else:
            blocks.append(f"# {t['label']}{w}\n{t['src']}" if t["label"] != t["src"] else f"{t['src']}{w}")
    return "\n---\n".join(blocks) + "\n"


def teams(name: str) -> list[tuple[str, list[dict], float]]:


    from .teams import read_team
    fmt = format_of(name)
    return [(t["label"], read_team(t["src"], fmt), float(t["weight"])) for t in get(name)["teams"]]


def draw(name: str, rng=None) -> tuple[str, str]:

    import random
    ts = get(name)["teams"]
    r = rng or random
    t = r.choices(ts, weights=[x["weight"] for x in ts], k=1)[0]
    return t["label"], t["src"]

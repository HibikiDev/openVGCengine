


















from __future__ import annotations

from vgc_trainer import i18n

import json
import re
import time
from pathlib import Path

from vgc_suite.formats import CURRENT, MC, get as get_format

ROOT = Path(__file__).resolve().parents[3]
STORE = ROOT / "trainer/runs/team_buckets.json"
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}")
PASTE_RE = re.compile(r"https?://pokepast\.es/([0-9a-fA-F]+)/?(?:raw)?")
WEIGHT_RE = re.compile(r"\s+x\s*(\d+(?:\.\d+)?)\s*$", re.I)
FIELD_MAX = 20

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


T = lambda s: s
NOTE_OFFICIAL = T("The {n} most represented teams of {events} official events, weighted by how often they were brought (newer events count more). The spreads are each Pokémon's most used one, not the players' own: edit a team to change them. Updated with the app.")
NOTE_IMPORTED = T("Imported from a Showdown backup.")


def note_of(b: dict) -> str:


    nt = b.get("note_t")
    if nt:
        return i18n.t(nt[0], **(nt[1] if len(nt) > 1 else {}))
    return b.get("note", "")


FORMAT_DIR = ROOT / "data/format_buckets"
FORMAT_SEEN = None

_format_synced = False


def _format_buckets(d: dict) -> dict:




    global _format_synced
    if _format_synced or not FORMAT_DIR.is_dir():
        return d
    _format_synced = True
    seen_file = FORMAT_SEEN or STORE.with_name("format_buckets.seen")
    try:
        seen = json.loads(seen_file.read_text(encoding="utf8"))
    except (OSError, ValueError):
        seen = {}
    changed = False
    for f in sorted(FORMAT_DIR.glob("*.json")):
        try:
            b = json.loads(f.read_text(encoding="utf8"))
            name, stamp = b["name"], b["built"]
        except (OSError, ValueError, KeyError):
            continue
        cur = d.get(name)
        if seen.get(name) == stamp or (cur is not None and not (cur.get("official") and cur["official"] == seen.get(name))):
            continue
        d[name] = {"note": "", "note_t": [NOTE_OFFICIAL, {"n": len(b["teams"]), "events": len(b["events"])}],
                   "updated": stamp, "format": b["format"], "official": stamp,
                   "teams": [{"label": t["label"], "src": t["src"], "link": None, "weight": t["weight"], "species": t["species"]}
                             for t in b["teams"]]}
        seen[name] = stamp
        changed = True
    if changed:
        _save(d)
        seen_file.write_text(json.dumps(seen), encoding="utf8")
    return d


def _seeded(d: dict) -> dict:

    d = _format_buckets(d)
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


def default_spec(fmt: str = CURRENT) -> str | None:


    return f"bucket:{DEFAULT}" if SEED.is_file() and DEFAULT in names(fmt) else None


def format_of(name: str) -> str:

    return get(name).get("format", MC)


def summaries() -> list[dict]:

    d = _load()
    return [{"name": k, "note": note_of(d[k]), "updated": d[k].get("updated", ""), "format": d[k].get("format", MC),
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
            raise ValueError(i18n.t("weight {w} for {team}: use a number above 0 (at most 100)", w=f"{e['weight']:g}", team=e['label'] or i18n.t('a team')))
    return out


def _resolve(spec: str, fmt: str = CURRENT) -> tuple[str, list[dict]]:


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


def save(name: str, text: str, note: str = "", old_name: str | None = None, fmt: str = CURRENT) -> tuple[dict, list[str]]:

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
            problems.append(i18n.t("team {k} ({team}): not a team - paste its Showdown export or a pokepast.es link", k=k, team=e['label'] or e['spec'][:30]))
            continue
        except Exception as ex:
            problems.append(i18n.t("team {k} ({team}): {error}", k=k, team=e['label'] or e['spec'][:30].strip(), error=f"{type(ex).__name__}: {str(ex)[:160]}"))
            continue
        label = e["label"] or (e["spec"] if "\n" not in e["spec"] and not e["spec"].startswith("paste:") else "/".join(species[:3]) + "/...")
        teams.append({"label": label, "src": src, "link": e.get("link"), "weight": e["weight"], "species": species})
    if problems:
        return {}, problems
    d = _load()
    if old_name and old_name != name:
        d.pop(old_name, None)
    d[name] = {"note": note.strip()[:300], "updated": time.strftime("%Y-%m-%d %H:%M"), "teams": teams, "format": fmt}
    if prev_bucket.get("note_t") and note.strip() == note_of(prev_bucket).strip():
        d[name].update(note="", note_t=prev_bucket["note_t"])
    _save(d)
    return d[name], []


BACKUP_RE = re.compile(r"(?m)^[ \t]*===[ \t]*\[([^\]\n]+)\][ \t]*(.*?)[ \t]*===[ \t]*$")


def split_backup(text: str) -> list[dict]:


    parts = BACKUP_RE.split(text.replace("\r", ""))
    out = []
    for fmt, title, body in zip(parts[1::3], parts[2::3], parts[3::3]):
        folder, _, name = title.rpartition("/")
        out.append({"format": fmt.strip(), "folder": folder.strip(), "name": name.strip(), "export": body.strip() + "\n"})
    return out


def buddy_backup(teams: list[dict], bo3: bool | None = None) -> str:



    from vgc_trainer.formats import REGULATIONS, base_id
    from vgc_trainer.showdown.sheets import buddy_format
    from vgc_suite.formats import IN_TOOLS
    out = []
    for t in teams:
        b = base_id(t["format"])
        if b not in IN_TOOLS:
            out.append(f"=== [{t['format']}] {t['folder'] + '/' if t['folder'] else ''}{t['name']} ===\n\n{t['export'].strip()}\n")
            continue
        keep3 = t["format"].removesuffix("buddy").endswith("bo3")
        fmt = buddy_format(b + ("bo3" if (keep3 if bo3 is None else bo3) and b in REGULATIONS else ""))
        out.append(f"=== [{fmt}] {t['folder'] + '/' if t['folder'] else ''}{t['name']} ===\n\n{t['export'].strip()}\n")
    return "\n\n".join(out)


def backup_text(name: str, bo3: bool = True) -> str:


    b = get(name)
    fmt = b.get("format", MC)
    teams = [{"format": fmt + ("bo3" if bo3 else ""), "folder": name, "name": t["label"], "export": x}
             for t, x in zip(b["teams"], team_exports(name))]
    return buddy_backup(teams)


def team_exports(name: str) -> list[str]:


    from vgc_trainer.showdown.teams import to_paste
    from .teams import read_team
    b = get(name)
    fmt = b.get("format", MC)
    out = []
    for t in b["teams"]:
        src = t["src"]
        if "\n" not in src:
            if (src, fmt) not in _ID_EXPORTS:
                _ID_EXPORTS[(src, fmt)] = to_paste(read_team(src, fmt))
            src = _ID_EXPORTS[(src, fmt)]
        out.append(src.strip())
    return out


_ID_EXPORTS: dict[tuple[str, str], str] = {}


def import_backup(text: str, prefix: str = "Showdown") -> dict:





    from vgc_trainer.formats import base_id
    from vgc_suite.formats import IN_TOOLS
    teams = split_backup(text)
    added: dict[str, int] = {}
    skipped: list[tuple[str, str]] = []
    d = _load()
    for t in teams:
        label = WEIGHT_RE.sub("", (t["name"] or t["folder"] or "team")).strip()[:40] or "team"
        fmt = base_id(t["format"])
        if fmt not in IN_TOOLS:
            skipped.append((label, i18n.t("{format} isn't a format the tools play", format=t["format"])))
            continue
        try:
            src, sets = _resolve(t["export"], fmt)
        except SystemExit:
            skipped.append((label, i18n.t("not a team the tools can read")))
            continue
        except Exception as ex:
            skipped.append((label, f"{type(ex).__name__}: {str(ex)[:160]}"))
            continue
        base = f"{prefix} {get_format(fmt).short}"[:40].strip()
        k, name = 1, base
        while True:
            b = d.get(name)
            if b is not None and (b.get("format", MC) != fmt or b.get("official")):
                k += 1
                name = f"{base} {k}"
                continue
            if b is not None and any(x["src"] == src for x in b["teams"]):
                skipped.append((label, i18n.t("already in {bucket}", bucket=name)))
                break
            b = d.setdefault(name, {"note": "", "note_t": [NOTE_IMPORTED], "teams": [], "format": fmt})
            b["teams"].append({"label": label, "src": src, "link": None, "weight": 1.0, "species": [s["species"] for s in sets]})
            b["updated"] = time.strftime("%Y-%m-%d %H:%M")
            added[name] = added.get(name, 0) + 1
            break
    if added:
        _save(d)
    return {"buckets": added, "skipped": skipped, "teams": teams, "buddy": buddy_backup(teams)}


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

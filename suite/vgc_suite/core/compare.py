








from __future__ import annotations

import json
from pathlib import Path

_CACHE: dict[str, tuple[float, list[dict]]] = {}


def _mode(r: dict, games: int) -> dict:
    s = r.get("search")
    return {"search": s["games_per_team"], "label": f"Search Mode, {s['games_per_team']} a team"} if s else \
        {"search": 0, "label": f"quick, {games:,} games"}


def _entries(j: dict) -> list[dict]:

    r = j.get("result") or {}
    if j.get("tool") != "validate" or j.get("status") != "done" or "error" in r:
        return []
    base = {"job": j["id"], "created": j.get("created"), "field": (j.get("params") or {}).get("field", ""), "model": r.get("model"),

            "opp_species": {o["id"]: o.get("species") or [] for o in r.get("opponents") or [] if isinstance(o, dict) and "id" in o}}
    out = []
    if r.get("sweep"):
        for k, row in enumerate(r.get("rows") or []):
            five = " · ".join(r.get("five") or [])
            out.append({**base, "key": f"{j['id']}:{k}", "kind": "current team" if row.get("source") == "current" else "candidate",
                        "label": f"{five} + {row['label'].removeprefix('keep ')}", "species": (r.get("five") or []) + [row["species"]],
                        "mode": _mode(r, row.get("games") or r.get("games_each") or 0),
                        "overall": row["overall"]["score"], "ci": row["overall"].get("ci"),
                        "both_adapt": (row.get("robust") or {}).get("equilibrium"),
                        "opponents": {i: {"score": v, "games": (row.get("opp_games") or {}).get(i), "both_adapt": None}
                                      for i, v in (row.get("opponents") or {}).items()},
                        "shares": {o["id"]: o.get("share") for o in r.get("opponents") or []}})
        return out
    sp = (r.get("team") or {}).get("species") or []
    out.append({**base, "key": j["id"], "kind": "team", "label": " · ".join(sp), "species": sp, "mode": _mode(r, r.get("games") or 0),
                "overall": r["overall"]["score"], "ci": r["overall"].get("ci"),
                "both_adapt": (r.get("brings") or {}).get("equilibrium"),
                "opponents": {o["id"]: {"score": o["score"], "games": o.get("games"),
                                        "both_adapt": ((o.get("brings") or {}).get("equilibrium") or {}).get("value")}
                              for o in r.get("opponents") or []},
                "shares": {o["id"]: o.get("share") for o in r.get("opponents") or []}})
    ref = r.get("reference")
    if ref:
        rs = (ref.get("team") or {}).get("species") or []
        out.append({**base, "key": f"{j['id']}:ref", "kind": "reference team", "label": " · ".join(rs), "species": rs,
                    "mode": _mode(r, r.get("games") or 0), "overall": ref["overall"]["score"], "ci": ref["overall"].get("ci"),
                    "both_adapt": (ref.get("brings") or {}).get("equilibrium"),
                    "opponents": {i: {"score": o["score"], "games": o.get("games"), "both_adapt": o.get("both_adapt")}
                                  for i, o in (ref.get("opponents") or {}).items()},
                    "shares": out[0]["shares"]})
    return out


def index(job_dir: Path) -> list[dict]:
    out = []
    for f in job_dir.glob("*.json"):
        t = f.stat().st_mtime
        hit = _CACHE.get(f.name)
        if hit is None or hit[0] != t:
            try:
                hit = (t, _entries(json.loads(f.read_text(encoding="utf8"))))
            except (OSError, ValueError, KeyError, TypeError):
                hit = (t, [])
            _CACHE[f.name] = hit
        out += hit[1]
    return sorted(out, key=lambda e: (-(e["created"] or 0), e["key"]))


def field_label(field: str) -> str:
    return f"bucket {field[7:]}" if field.startswith("bucket:") else "Current Metagame" if field == "meta" else field


def compare(entries: list[dict]) -> dict:

    rows = sorted(entries, key=lambda e: -e["overall"])
    teams = sorted({i for e in rows for i in e["opponents"]})
    shared = [i for i in teams if all(i in e["opponents"] for e in rows)]
    shares = {}
    for e in rows:
        for i, v in e["shares"].items():
            shares.setdefault(i, v)
    best = {i: max((e["opponents"][i]["score"] for e in rows if i in e["opponents"]), default=None) for i in teams}
    species = {}
    for e in rows:
        for i, v in (e.get("opp_species") or {}).items():
            if v:
                species.setdefault(i, v)

    lead = rows[0] if rows else None
    teams = sorted(teams, key=lambda i: (lead["opponents"][i]["score"] if lead and i in lead["opponents"] else 2, i))

    for e in rows:
        w = [(shares.get(i) or 1.0, e["opponents"][i]["score"]) for i in shared]
        e["on_shared"] = round(sum(a * b for a, b in w) / sum(a for a, _ in w), 3) if w else None
    warn = []
    if len({e["model"] for e in rows}) > 1:
        warn.append("These runs used different models (" + ", ".join(sorted({str(e["model"]) for e in rows})) + "): a gap can be the "
                    "model's, not the team's - rerun the older ones to compare like with like.")
    if len({bool(e["mode"]["search"]) for e in rows}) > 1:
        warn.append("Quick and Search Mode runs are mixed: quick numbers can sit ~20 points off a matchup the way the bot really plays "
                    "it, so compare quick with quick and Search Mode with Search Mode.")
    if len(shared) < len(teams):
        warn.append(f"Not every run played the same teams (the bucket changed between runs): the \"shared teams\" column scores each "
                    f"run on the {len(shared)} teams all of them played.")
    return {"rows": rows, "teams": teams, "shared": shared, "shares": shares, "best": best, "warn": warn, "species": species,
            "has_both": any(e["both_adapt"] is not None for e in rows)}

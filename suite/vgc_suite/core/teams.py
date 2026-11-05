


from __future__ import annotations

import sys
from pathlib import Path
from vgc_trainer.winproc import NO_WINDOW

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "trainer/scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "trainer/scripts"))

from vgc_trainer.search import guessed_spreads
from vgc_trainer.showdown.sheets import playable_sheet
from vgc_trainer.showdown.live_search import _corpus
from vgc_trainer.showdown.teams import base_megas, parse_paste

from .positions import with_spreads


def lookup_team(spec: str) -> list[dict]:

    if "\n" in spec:
        sets = [base_megas(s) for s in parse_paste(spec)]
    else:
        from vgc_trainer.showdown.teams import load_team
        sets = load_team(spec)
    if any(not any((s.get("evs") or {}).values()) for s in sets):
        sets = with_spreads(sets, guessed_spreads([sets], _corpus())[0])
    return playable_sheet(sets)


def read_team(spec: str, fmt: str | None = None) -> list[dict]:




    from vgc_suite.formats import engine
    efmt = engine(fmt)
    if efmt is None:
        return lookup_team(spec)
    import json

    import vgc_engine as ve
    from vgc_trainer.showdown.teams import load_team
    sets = validated_sets(spec, efmt, parse_only=True) if "\n" in spec else load_team(spec)
    if "\n" in spec and "serious nature" not in spec.lower():

        sets = [dict(s, nature="") if s.get("nature") == "Serious" and not any((s.get("evs") or {}).values()) else s for s in sets]

    if any(not any((s.get("evs") or {}).values()) for s in sets):
        from vgc_trainer.showdown.live_search import usage_corpus
        sets = with_spreads(sets, guessed_spreads([sets], usage_corpus(efmt))[0])
    sets = validated_sets(json.dumps(sets), efmt)

    ve.BattlePool(1).register_team((list(sets) * 6)[:6], efmt)
    return sets


def validated_sets(text: str, fmt: str, parse_only: bool = False) -> list[dict]:



    import json
    import subprocess
    r = subprocess.run(["node", str(ROOT / "tools/showdown-oracle/validate-team.js"), "--format", fmt] + (["--parse-only"] if parse_only else []),
                       input=text, capture_output=True,
                       text=True, encoding="utf8", timeout=60, cwd=ROOT, **NO_WINDOW)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        raise ValueError(f"the validator gave no answer ({r.stderr.strip()[-160:]})") from None
    if "problems" in out:
        raise ValueError("Showdown's validator refused it: " + "; ".join(out["problems"])[:240])
    return out["sets"]


def legal(sets: list[dict], fmt: str | None = None, partial: bool = False) -> tuple[list[dict], list[str]]:

    from vgc_suite.formats import engine
    return legal_mc(sets, partial) if engine(fmt) is None else (sets, [])


def legal_mc(sets: list[dict], partial: bool = False) -> tuple[list[dict], list[str]]:




    import json
    import subprocess
    fixed, notes = [], []
    for s in sets:
        iv = {k: v for k, v in (s.get("ivs") or {}).items() if v != 31}
        if iv:
            notes.append(f"{s.get('name') or s['species']}'s IVs set to 31 (Champions has no IVs)")
        fixed.append({k: v for k, v in s.items() if k != "ivs"} if iv else s)
    r = subprocess.run(["node", str(ROOT / "tools/showdown-oracle/validate-team.js"), "--format", "gen9championsvgc2026regmc"],
                       input=json.dumps(fixed), capture_output=True, text=True, encoding="utf8", timeout=60, cwd=ROOT, **NO_WINDOW)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        raise ValueError(f"Showdown's validator gave no answer ({r.stderr.strip()[-160:]})") from None
    problems = [p for p in out.get("problems") or [] if not (partial and ("at least" in p or "at most" in p))]
    if problems:
        raise ValueError("Not a legal Reg M-C team (Showdown's validator): " + " ".join(problems))
    return fixed, notes

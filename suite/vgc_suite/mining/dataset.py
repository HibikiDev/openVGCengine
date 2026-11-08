



















from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.core.positions import walk
from vgc_suite.core.replay import load_replay
from vgc_trainer.showdown.requests import SWITCH_BASE

OUT = ROOT / "trainer/runs/human_data"
LOGS = ROOT / "trainer/runs/replays/logs"
OWN_LOGS, OWN_OUT = ROOT / "trainer/runs/showdown_logs", ROOT / "trainer/runs/human_data_own"
RESULTS = ROOT / "trainer/runs/showdown_results.jsonl"
TEAM_FILES = [ROOT / "tools/corpus/out/teams-sets.json", ROOT / "tools/corpus/out/standings-sets-v2.json",
              ROOT / "tools/corpus/out/standings-sets.json"]


from vgc_suite.mining.bots import KNOWN_BOTS, is_bot


def own_sheet(spec: str) -> list[dict] | None:



    scripts = str(ROOT / "trainer/scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from vgc_trainer.showdown.teams import UnknownTeam, load_team

    path = ROOT / spec
    try:
        return load_team(str(path) if path.exists() else spec)
    except (SystemExit, UnknownTeam):
        return None


def _ratings(log) -> dict[str, int | None]:
    out = {}
    for ln in log.lines:
        p = ln.split("|")
        if len(p) > 5 and p[1] == "player" and p[2] in ("p1", "p2"):
            out[p[2]] = int(p[5]) if p[5].isdigit() else None
    return out


def _winner(log) -> str | None:
    for ln in reversed(log.lines):
        if ln.startswith("|win|"):
            return log.side_of(ln.split("|")[2])
        if ln.startswith("|tie"):
            return "tie"
    return None


def _acts(played) -> list[list[int]]:
    return [[a, int(m)] if a is not None else [-1, 0] for a, m in ((x if x else (None, False)) for x in played)]


def _move_level(played) -> list[int]:

    out = []
    for x in played:
        if not x:
            out.append(-1)
        elif x[0] >= SWITCH_BASE:
            out.append(4 if x[0] < SWITCH_BASE + 4 else -1)
        else:
            out.append(x[0] // 4)
    return out


def game_rows(path: Path, own: dict[str, list[dict]] | None = None) -> tuple[list[dict], dict | None, str | None]:

    log = load_replay(str(path))
    if not log.ots:
        return [], None, "no open team sheets"
    winner = _winner(log)
    if winner is None:
        return [], None, "unfinished"
    ratings = _ratings(log)
    decs = {s: {d.turn: d for d in walk(log, s, own_sheet=(own or {}).get(s))} for s in ("p1", "p2")}
    rows = []
    for side in (own or ("p1", "p2")):
        foe = "p2" if side == "p1" else "p1"
        for turn, d in decs[side].items():
            fd = decs[foe].get(turn)
            rows.append({"obs": d.obs, "bring": (list(d.bring) + [i for i in range(6) if i not in d.bring])[:4], "my": _acts(d.played),
                         "masks": list(d.masks.actions), "mega": [int(x) for x in d.masks.mega], "min_switches": d.masks.min_switches,
                         "foe": _acts(fd.played) if fd else [[-1, 0], [-1, 0]],
                         "foe_moves": _move_level(fd.played) if fd else [-1, -1],
                         "won": -1 if winner == "tie" else int(winner == side), "turn": turn,
                         "rating_me": ratings.get(side) or 0, "rating_foe": ratings.get(foe) or 0,
                         "meta": {"id": path.stem, "side": side, "turn": turn, "player": log.players.get(side),
                                  "bot": is_bot(log.players.get(side, "")), "vs_bot": is_bot(log.players.get(foe, "")),
                                  "active": d.active, "foe_active": d.foe_active, "played": d.played_text}})
    first = {s: (sorted(decs[s].values(), key=lambda d: d.turn)[0] if decs[s] else None) for s in ("p1", "p2")}
    preview = {"id": path.stem, "format": log.fmt, "players": log.players, "ratings": ratings, "winner": winner,
               "sheets": {s: [{k: m.get(k) for k in ("species", "item", "ability", "moves", "nature")} for m in log.sheets[s]]
                          for s in ("p1", "p2")},

               "bring": {s: (first[s].bring[:first[s].shown] if first[s] else None) for s in ("p1", "p2")}}
    return rows, preview, None


def _team_key(sets: list[dict]) -> tuple:

    from vgc_trainer.showdown.tracker import to_id
    return tuple(sorted((to_id(m.get("item") or ""), tuple(sorted(to_id(mv) for mv in m.get("moves", [])))) for m in sets))


_BY_KEY: dict | None = None


def _team_by_shown(shown: list[dict]) -> list[dict] | None:



    global _BY_KEY
    if _BY_KEY is None:
        from vgc_trainer.showdown.teams import TEAM_FILES as HOST_FILES
        from vgc_trainer.showdown.teams import parse_paste
        _BY_KEY = {}
        for f in (f for f in HOST_FILES if f.exists()):
            for t in json.loads(f.read_text(encoding="utf8"))["teams"]:
                _BY_KEY.setdefault(_team_key(t["sets"]), t["sets"])
        for f in sorted((ROOT / "handmade_teams").glob("*.txt")):
            sets = parse_paste(f.read_text(encoding="utf8"))
            _BY_KEY.setdefault(_team_key(sets), sets)
    return _BY_KEY.get(_team_key(shown))


def _own_sides(results: Path) -> dict[str, dict[str, list[dict]] | None]:

    out, sheets = {}, {}
    for ln in results.read_text(encoding="utf8").splitlines():
        r = json.loads(ln) if ln.strip() else {}
        if r.get("room") and r.get("team"):
            if r["team"] not in sheets:
                sheets[r["team"]] = own_sheet(r["team"])
            out[r["room"]] = sheets[r["team"]]
    return out


def build(logs: Path, out: Path = OUT, own_results: Path | None = None, shard: tuple[int, int] = (0, 1)) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    rows, previews, games = [], [], []
    t0 = time.time()
    own_teams = _own_sides(own_results) if own_results else None
    for k, path in enumerate(sorted(logs.glob("*.log"))):
        if k % shard[1] != shard[0]:
            continue
        try:
            own = None
            if own_teams is not None:
                sheet = own_teams.get(path.stem)
                text = path.read_text(encoding="utf8").splitlines()
                me = next((ln.split("|")[2] for ln in text
                           if ln.startswith("|player|") and len(ln.split("|")) > 3 and is_bot(ln.split("|")[3])), None)
                shown = next((ln for ln in text if me and ln.startswith(f"|showteam|{me}|")), None)
                if shown:
                    from vgc_trainer.showdown.teams import unpack
                    seen = unpack("|".join(shown.split("|")[3:]))
                    if sheet is None or _team_key(sheet) != _team_key(seen):
                        sheet = _team_by_shown(seen) or sheet
                if sheet is None or me is None:
                    games.append({"id": path.stem, "rows": 0, "skipped": "own team or side unknown"})
                    continue
                own = {me: sheet}
            r, pv, why = game_rows(path, own)
        except KeyboardInterrupt:
            raise
        except BaseException as e:
            r, pv, why = [], None, f"error {type(e).__name__}: {str(e)[:100]}"
        games.append({"id": path.stem, "rows": len(r), "skipped": why})
        rows += r
        if pv:
            previews.append(pv)
    if rows:
        np.savez_compressed(
            out / "decisions.npz",
            **{k: np.stack([r["obs"][i] for r in rows]) for i, k in enumerate(("field", "mon_ids", "mon_features", "history"))},
            bring=np.array([r["bring"] for r in rows], np.int64), my_actions=np.array([r["my"] for r in rows], np.int64),
            foe_actions=np.array([r["foe"] for r in rows], np.int64), foe_moves=np.array([r["foe_moves"] for r in rows], np.int64),
            masks=np.array([r["masks"] for r in rows], np.int64), mega=np.array([r["mega"] for r in rows], np.int64),
            min_switches=np.array([r["min_switches"] for r in rows], np.int64),
            won=np.array([r["won"] for r in rows], np.int64), turn=np.array([r["turn"] for r in rows], np.int64),
            rating_me=np.array([r["rating_me"] for r in rows], np.int64), rating_foe=np.array([r["rating_foe"] for r in rows], np.int64))
    (out / "rows.jsonl").write_text("\n".join(json.dumps(r["meta"]) for r in rows), encoding="utf8")
    (out / "preview.jsonl").write_text("\n".join(json.dumps(p) for p in previews), encoding="utf8")
    (out / "games.jsonl").write_text("\n".join(json.dumps(g) for g in games), encoding="utf8")
    used = [g for g in games if g["rows"]]
    stats = {"games": len(games), "used": len(used), "rows": len(rows),
             "labelled_own": int(sum(a[0] >= 0 for r in rows for a in r["my"])),
             "labelled_foe": int(sum(a[0] >= 0 for r in rows for a in r["foe"])),
             "skipped": {k: sum(1 for g in games if (g["skipped"] or "").startswith(k)) for k in ("no open", "unfinished", "error")},
             "seconds": round(time.time() - t0, 1)}
    (out / "stats.json").write_text(json.dumps(stats, indent=1), encoding="utf8")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default=str(LOGS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--shard", default="0/1", help="I/N: only every N-th log from the I-th (sorted by name) - N builds in parallel")
    ap.add_argument("--own", action="store_true", help="the bot's own game logs (defaults: showdown_logs -> human_data_own)")
    args = ap.parse_args()
    if args.own:
        logs = Path(args.logs) if args.logs != str(LOGS) else OWN_LOGS
        out = Path(args.out) if args.out != str(OUT) else OWN_OUT
        print(json.dumps(build(logs, out, RESULTS), indent=1))
    else:
        i, n = (int(x) for x in args.shard.split("/"))
        print(json.dumps(build(Path(args.logs), Path(args.out), shard=(i, n)), indent=1))


if __name__ == "__main__":
    main()

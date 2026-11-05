










from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / "trainer", ROOT / "suite"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_suite.mining.dataset import LOGS, OUT, is_bot

BESTOF = re.compile(r"Game (\d)</strong> of <a href=\"/game-bestof3-([a-z0-9-]+)\"")


def _series_of(path: Path) -> tuple[str, int] | None:
    with open(path, encoding="utf8") as f:
        for k, ln in enumerate(f):
            if ln.startswith("|uhtml|bestof|"):
                m = BESTOF.search(ln)
                return (m.group(2), int(m.group(1))) if m else None
            if k > 40:
                return None
    return None


def _wr(k: float, n: int) -> str:
    if n == 0:
        return "-"
    p = k / n
    return f"{p:.3f}+-{np.sqrt(p * (1 - p) / n):.3f} (n {n})"


def _species(game: dict, side: str, idx: list[int]) -> list[str]:
    return [game["sheets"][side][i]["species"] for i in idx if i < len(game["sheets"][side])]


def load_series() -> dict[str, dict[int, dict]]:
    games = {}
    for ln in open(OUT / "preview.jsonl", encoding="utf8"):
        g = json.loads(ln)
        if any(is_bot(p) for p in g["players"].values()) or not all(g["bring"].get(s) for s in ("p1", "p2")):
            continue
        games[g["id"]] = g
    series: dict[str, dict[int, dict]] = defaultdict(dict)
    for gid, g in games.items():
        s = _series_of(LOGS / f"{gid}.log")
        if s:
            g["game_no"] = s[1]
            series[s[0]][s[1]] = g
    return series


def by_player(game: dict) -> dict[str, dict]:

    out = {}
    for side in ("p1", "p2"):
        name = "".join(ch for ch in game["players"][side].lower() if ch.isalnum())
        b = game["bring"][side]
        out[name] = {"lead": frozenset(_species(game, side, b[:2])), "bring": frozenset(_species(game, side, b)),
                     "sheet": frozenset(m["species"] for m in game["sheets"][side]), "won": game["winner"] == side,
                     "rating": (game.get("ratings") or {}).get(side) or 0}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="also write the numbers here")
    args = ap.parse_args()
    series = load_series()
    full = {k: v for k, v in series.items() if 1 in v and 2 in v}
    print(f"{sum(len(v) for v in series.values())} games in {len(series)} series; {len(full)} with games 1 and 2, "
          f"{sum(1 for v in full.values() if 3 in v)} of them with game 3 as well")
    res: dict = {}


    for a, b in ((1, 2), (2, 3), (1, 3)):
        same_lead, same_one, same_bring, n = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
        n4 = defaultdict(int)
        for s in full.values():
            if a not in s or b not in s:
                continue
            pa, pb = by_player(s[a]), by_player(s[b])
            for name in pa:
                if name not in pb or pa[name]["sheet"] != pb[name]["sheet"]:
                    continue
                key = "won" if pa[name]["won"] else "lost"
                for k in (key, "all"):
                    n[k] += 1
                    same_lead[k] += pa[name]["lead"] == pb[name]["lead"]
                    same_one[k] += len(pa[name]["lead"] & pb[name]["lead"]) >= 1
                    if len(pa[name]["bring"]) == 4 and len(pb[name]["bring"]) == 4:
                        n4[k] += 1
                        same_bring[k] += pa[name]["bring"] == pb[name]["bring"]
        print(f"\nGame {a} -> game {b} (by the game-{a} result of the player choosing)")
        for k in ("all", "won", "lost"):
            print(f"  {k:<5} same lead pair {_wr(same_lead[k], n[k])}; >= 1 lead mon kept {_wr(same_one[k], n[k])}; "
                  f"same four (fully seen) {_wr(same_bring[k], n4[k])}")
            res[f"g{a}g{b}_{k}"] = {"n": n[k], "same_lead": same_lead[k] / max(n[k], 1), "one_lead": same_one[k] / max(n[k], 1),
                                    "same_bring": same_bring[k] / max(n4[k], 1), "n_full": n4[k]}


    print("\nAfter losing game 1: game-2 win rate by whether the lead pair changed")
    for kept in (True, False):
        k = n_ = 0
        for s in full.values():
            pa, pb = by_player(s[1]), by_player(s[2])
            for name in pa:
                if name in pb and pa[name]["sheet"] == pb[name]["sheet"] and not pa[name]["won"] and (pa[name]["lead"] == pb[name]["lead"]) == kept:
                    n_ += 1
                    k += pb[name]["won"]
        print(f"  {'kept' if kept else 'changed':<8} {_wr(k, n_)}")
        res[f"g2_after_loss_{'kept' if kept else 'changed'}"] = {"n": n_, "wr": k / max(n_, 1)}


    g3 = [s for s in full.values() if 3 in s]
    w1 = sum(by_player(s[3])[n]["won"] for s in g3 for n, p in by_player(s[1]).items() if p["won"] and n in by_player(s[3]))
    w2 = sum(by_player(s[3])[n]["won"] for s in g3 for n, p in by_player(s[2]).items() if p["won"] and n in by_player(s[3]))
    print(f"\nGame 3 ({len(g3)} series): won by the game-1 winner {_wr(w1, len(g3))}; by the game-2 winner {_wr(w2, len(g3))}")
    res["g3_won_by_g1_winner"], res["g3_won_by_g2_winner"] = w1 / max(len(g3), 1), w2 / max(len(g3), 1)
    back = new = again2 = n3 = 0
    for s in g3:
        p1_, p2_, p3_ = by_player(s[1]), by_player(s[2]), by_player(s[3])
        for name in p3_:
            if name not in p1_ or name not in p2_ or not (p1_[name]["sheet"] == p2_[name]["sheet"] == p3_[name]["sheet"]):
                continue
            n3 += 1
            l1, l2, l3 = p1_[name]["lead"], p2_[name]["lead"], p3_[name]["lead"]
            again2 += l3 == l2
            back += l3 == l1 and l1 != l2
            new += l3 != l1 and l3 != l2
    print(f"  game-3 lead: = game 2 {_wr(again2, n3)}; back to game 1's (which game 2 had changed) {_wr(back, n3)}; "
          f"a third lead {_wr(new, n3)}")
    res["g3_lead"] = {"n": n3, "as_g2": again2 / max(n3, 1), "back_to_g1": back / max(n3, 1), "new": new / max(n3, 1)}


    turns = defaultdict(list)
    for s in full.values():
        for no, g in s.items():
            path = LOGS / f"{g['id']}.log"
            try:
                t = max((int(ln.split("|")[2]) for ln in open(path, encoding="utf8") if ln.startswith("|turn|")), default=0)
            except (OSError, ValueError):
                continue
            turns[no].append(t)
    print("\nGame length (turns): " + "; ".join(f"game {no} mean {np.mean(v):.1f}, <= 2 turns {np.mean(np.array(v) <= 2):.3f} (n {len(v)})"
                                             for no, v in sorted(turns.items())))
    res["turns"] = {no: {"mean": float(np.mean(v)), "short": float(np.mean(np.array(v) <= 2))} for no, v in turns.items()}
    print("\nLead pair kept game 1 -> 2, by the player's rating")
    for label, lo, hi in (("<1100", 1, 1100), ("1100-1199", 1100, 1200), ("1200-1299", 1200, 1300), ("1300+", 1300, 10**9)):
        k = n_ = 0
        for s in full.values():
            pa, pb = by_player(s[1]), by_player(s[2])
            for name in pa:
                if name in pb and pa[name]["sheet"] == pb[name]["sheet"] and lo <= pa[name]["rating"] < hi:
                    n_ += 1
                    k += pa[name]["lead"] == pb[name]["lead"]
        print(f"  {label:<10} {_wr(k, n_)}")
        res[f"keep12_{label}"] = {"n": n_, "p": k / max(n_, 1)}
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1), encoding="utf8")


if __name__ == "__main__":
    main()

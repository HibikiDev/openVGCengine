






from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "suite", ROOT / "trainer", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vgc_trainer.showdown.teams import unpack
from vgc_trainer.showdown.tracker import TERRAINS, Tracker, to_id


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
    lines = Path(sys.argv[2]).read_text(encoding="utf8").split("\n")
    sheets = {s: unpack(spec[s]["team"]) for s in ("p1", "p2")}
    bad = []
    for me in ("p1", "p2"):
        foe = "p2" if me == "p1" else "p1"
        t = Tracker(me, sheets[me], sheets[foe], spec["format"].removesuffix("buddy"))
        t.feed(lines)
        f = spec["field"]
        want = {"weather": (to_id(f.get("weather", "")), f.get("weatherTurns", 0)), "terrain": (f.get("terrain", ""), f.get("terrainTurns", 0)),
                "trickroom": f.get("trickRoom", 0), "gravity": f.get("gravity", 0)}
        got = {"weather": (to_id(getattr(t, "weather_name", "")) if t.weather else "", t.weather_turns if t.weather else 0),
               "terrain": (next((to_id(k) for k, v in TERRAINS.items() if v == t.terrain), ""), t.terrain_turns if t.terrain else 0),
               "trickroom": t.trick_room, "gravity": t.gravity}
        for s in ("p1", "p2"):
            for k in ("tailwind", "reflect", "lightscreen", "auroraveil", "safeguard"):
                want[f"{s} {k}"] = spec["sides"][s].get(k, 0)
                got[f"{s} {k}"] = t.side[s].get(k, 0)

            want[f"{s} fainted"] = sum(1 for m in spec["mons"][s] if m["hp"] == 0 and (s == me or m.get("seen")))
            got[f"{s} fainted"] = sum(1 for m in t.mons[s] if m.fainted)
        for k in want:
            if want[k] != got[k]:
                bad.append(f"bot as {me}: {k} replay {want[k]} vs tracker {got[k]}")
    for b in bad:
        print("  " + b)
    print(f"tracker: {'counts as the replay' if not bad else f'{len(bad)} differ'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())











import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "trainer"))
from vgc_trainer.showdown.tracker import Tracker
import vgc_engine as ve

FIELD_NAMES = (["weather:none", "weather:sun", "weather:rain", "weather:sand", "weather:snow", "weather_turns"]
               + [f"terrain:{t}" for t in ("none", "electric", "grassy", "misty", "psychic")]
               + ["terrain_turns", "trick_room", "gravity", "turn"]
               + [f"{w}:{k}" for w in ("my", "foe") for k in ("reflect", "lightscreen", "auroraveil", "tailwind", "mega_used", "healing_wish")]
               + ["decision:turn", "decision:my_switch", "decision:their_switch"]
               + ["format:champions_mc", "format:gen5vgc13", "format:gen6", "format:gen7"] + ["my:z_used", "foe:z_used"]
               + ["format2:gen9sv", "format2:gen9sv_predlc", "format2:gen8", "format2:7"] + ["my:tera_used", "foe:tera_used"]
               + ["my:dynamax_used", "foe:dynamax_used", "my:gmax_residual", "foe:gmax_residual"])
MON_NAMES = (["is_mine", "in_battle", "active_a", "active_b", "fainted", "hp"] + [f"status:{s}" for s in ("none", "brn", "frz", "par", "psn", "tox", "slp")]
             + ["toxic_stage"] + [f"boost:{b}" for b in ("atk", "def", "spa", "spd", "spe", "acc", "eva")]
             + ["mega", "can_mega", "turns_active", "confused", "taunted", "encored", "disabled", "substitute", "protect_streak", "perish",
                "yawn", "trapped", "charging", "recharge", "choice_locked", "throat_chopped", "heal_blocked", "holds_item"]
             + ["stat:hp", "stat:atk", "stat:def", "stat:spa", "stat:spd", "stat:spe"] + [f"pp{k}" for k in range(4)] + ["stockpile"]
             + ["terastallized", "stellar_left", "commanding"] + ["dynamax_turns", "gigantamax", "chi_strike"])
ID_NAMES = ["species", "item", "ability", "move0", "move1", "move2", "move3", "type0", "type1", "tera_type"]
HIST_NAMES = ["kind", "actor", "target", "move", "outcome"]


def check(scenario_path: Path, show: int, counts: Counter) -> int:
    scenario = json.loads(scenario_path.read_text(encoding="utf8"))
    with tempfile.TemporaryDirectory() as tmp:
        obs_path = Path(tmp) / "obs.json"
        run = subprocess.run([str(ROOT / "target/debug/diff.exe"), "obs", str(scenario_path), str(obs_path)], capture_output=True, text=True, encoding="utf8")
        if run.returncode != 0:

            print(f"  {scenario_path.name}: engine replay diverged, skipped ({run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr.strip()[-200:]})")
            counts["skipped: engine replay diverged"] += 1
            return 0
        engine = json.loads(obs_path.read_text())
    proto = json.loads(subprocess.run(["node", str(ROOT / "tools/showdown-oracle/protocol.js"), str(scenario_path)], check=True,
                                      capture_output=True, text=True, encoding="utf8").stdout)["steps"]
    sheets = {"p1": scenario["team1"], "p2": scenario["team2"]}
    fmt = scenario.get("format")
    fmt = None if fmt == "gen9championsvgc2026regmc" else fmt
    trackers = {p: Tracker(p, sheets[p], sheets["p2" if p == "p1" else "p1"], fmt=fmt) for p in ("p1", "p2")}
    mismatches = 0
    turns = scenario.get("turns", [])
    for step, (eng, pro) in enumerate(zip(engine, proto)):
        for side, p in ((0, "p1"), (1, "p2")):
            t = trackers[p]
            t.feed(pro[p]["lines"])
            t.set_request(pro[p]["request"])
            if pro[p]["request"] is None:
                continue
            f, ids, feats, hist = t.observe()
            if step < len(turns):
                t.note_choice(turns[step][p])
            e = eng[side]
            groups = [
                ("field", np.array(e["field"], np.float32), f, lambda i: FIELD_NAMES[i]),
                ("ids", np.array(e["mon_ids"]).reshape(ids.shape), ids, lambda i: f"tok{i // ve.MON_IDS}.{ID_NAMES[i % ve.MON_IDS]}"),
                ("mon", np.array(e["mon_features"], np.float32).reshape(feats.shape), feats, lambda i: f"tok{i // ve.MON_FEATURES}.{MON_NAMES[i % ve.MON_FEATURES]}"),
                ("hist", np.array(e["history"]).reshape(hist.shape), hist, lambda i: f"row{i // ve.EVENT_FIELDS}.{HIST_NAMES[i % ve.EVENT_FIELDS]}"),
            ]
            if fmt is not None and not t.open_sheets:


                r = ve.ROSTER_SIZE
                groups[1][1].reshape(ids.shape)[r:, 3:7].sort(axis=1)
                ids[r:, 3:7].sort(axis=1)
            for name, want, got, label in groups:
                bad = np.flatnonzero(~np.isclose(want.ravel(), got.ravel(), atol=1e-5))
                for i in bad:
                    key = f"{name}:{label(i).split('.', 1)[-1]}"
                    counts[key] += 1
                    mismatches += 1
                    if show > 0:
                        print(f"  {scenario_path.name} step {step} {p} {label(i)}: engine {want.ravel()[i]:g} tracker {got.ravel()[i]:g}")
                        show -= 1
    return mismatches


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", nargs="+", help="scenario files, or directories of them")
    ap.add_argument("--show", type=int, default=8, help="print this many individual mismatches per scenario")
    args = ap.parse_args()
    counts: Counter = Counter()
    clean = 0
    paths = [q for s in args.scenarios for q in (sorted(Path(s).glob("*.json")) if Path(s).is_dir() else [Path(s)])]
    for p in paths:
        n = check(p, args.show, counts)
        clean += n == 0
        print(f"{p.name}: {'OK' if n == 0 else f'{n} mismatched elements'}", flush=True)
    print(f"\n{clean}/{len(paths)} scenarios exact")
    for k, v in counts.most_common(30):
        print(f"  {v:6d}  {k}")


if __name__ == "__main__":
    main()

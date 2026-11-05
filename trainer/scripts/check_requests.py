







import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "trainer"))
from vgc_trainer.showdown.requests import RequestMasks
from vgc_trainer.showdown.tracker import Tracker, to_id


def check(path: Path, show: int, counts: Counter) -> int:
    scenario = json.loads(path.read_text(encoding="utf8"))
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "obs.json"
        run = subprocess.run([str(ROOT / "target/debug/diff.exe"), "obs", str(path), str(out)], capture_output=True, text=True, encoding="utf8")
        if run.returncode != 0:
            counts["skipped: engine replay diverged"] += 1
            return 0
        engine = json.loads(out.read_text())
    proto = json.loads(subprocess.run(["node", str(ROOT / "tools/showdown-oracle/protocol.js"), str(path)], check=True,
                                      capture_output=True, text=True, encoding="utf8").stdout)["steps"]
    names = {p: [to_id(m.get("name") or m["species"]) for m in scenario[t]] for p, t in (("p1", "team1"), ("p2", "team2"))}
    fmt = scenario.get("format")
    fmt = None if fmt == "gen9championsvgc2026regmc" else fmt
    trackers = {p: Tracker(p, scenario["team1" if p == "p1" else "team2"], scenario["team2" if p == "p1" else "team1"], fmt=fmt)
                for p in ("p1", "p2")}
    bad = 0
    for step, (eng, pro) in enumerate(zip(engine, proto)):
        for side, p in ((0, "p1"), (1, "p2")):
            req = pro[p]["request"]
            trackers[p].feed(pro[p]["lines"])
            trackers[p].set_request(req)
            want = eng[side]["masks"]
            got = RequestMasks(req, names[p], trackers[p])
            if not want["to_move"] and not got.to_move:
                continue
            diffs = []
            if want["to_move"] != got.to_move:
                diffs.append(f"to_move {want['to_move']} vs {got.to_move}")
            else:
                for s in (0, 1):
                    if want["actions"][s] != got.actions[s]:
                        extra, missing = got.actions[s] & ~want["actions"][s], want["actions"][s] & ~got.actions[s]
                        diffs.append(f"slot{s} actions: request adds {[i for i in range(21) if extra >> i & 1]}, misses {[i for i in range(21) if missing >> i & 1]}")
                    if want["mega"][s] != got.mega[s]:
                        diffs.append(f"slot{s} mega {want['mega'][s]} vs {got.mega[s]}")
                    for key in ("gimmick", "forced", "kind"):
                        if key in want and want[key][s] != getattr(got, key)[s]:
                            diffs.append(f"slot{s} {key}: engine {want[key][s]} vs request {getattr(got, key)[s]}")
                if want["min_switches"] != got.min_switches:
                    diffs.append(f"min_switches {want['min_switches']} vs {got.min_switches}")
            for d in diffs:
                counts[d.split(":")[0].split(" ")[0] + " " + (d.split(" ")[1] if " " in d else "")] += 1
                bad += 1
                if show > 0:
                    print(f"  {path.name} step {step} {p}: {d}")
                    show -= 1
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", nargs="+")
    ap.add_argument("--show", type=int, default=8)
    args = ap.parse_args()
    paths = [q for s in args.scenarios for q in (sorted(Path(s).glob("*.json")) if Path(s).is_dir() else [Path(s)])]
    counts: Counter = Counter()
    clean = 0
    for p in paths:
        n = check(p, args.show, counts)
        clean += n == 0
        if n:
            print(f"{p.name}: {n} mismatches", flush=True)
    print(f"\n{clean}/{len(paths)} scenarios exact")
    for k, v in counts.most_common(20):
        print(f"  {v:6d}  {k}")


if __name__ == "__main__":
    main()













import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "trainer"))
import numpy as np
from check_tracker import FIELD_NAMES, HIST_NAMES, ID_NAMES, MON_NAMES
from vgc_trainer.showdown.snapshot import SHOWN_HP_SCALE, Unsupported, party_order, snapshot

HP_SCALE = 100
from vgc_trainer.showdown.tracker import Tracker
import vgc_engine as ve


EXCLUDED = {
    r"mon\.speed_cache": "refreshed by `resolve_turn` before anything reads it",
    r"mon\.faint_seq": "orders faint events within one action; only compared inside an action",
    r"mon\.ability_order|ability_seq": "ability-state age (redirect speed ties only): the rebuild leaves 0 = older than anything the search "
                                       "switches in; two rebuilt holders tied on Speed fall back on the listed order",
    r"mon\.illusion": "Illusion holders are on the fallback list",
    r"mon\.moves_used": "bookkeeping for Last Resort-style checks",
    r"mon\.last_item": "Recycle / Harvest / Pickup only (no corpus use yet); not tracked in v1",
    r"mon\.cud_(berry|counter)": "Cud Chew (no corpus use yet); not tracked in v1",
    r"mon\.hurt_hp": "turn-scoped (Emergency Exit threshold within a turn)",
    r"mon\.move_result_last_turn": "overwritten from `move_result_this_turn` at the top of `resolve_turn`, before anything reads it",
    r"mon\.last_hit_\w+": "turn-scoped (Counter-family, Metal Burst)",
    r"mon\.stockpile_(def|spd)": "the boosts Stockpile added (only for Spit Up's undo); the boosts themselves are compared",
    r"mon\.ally_switch_\w+": "turn-scoped",
    r"mon\.hit_by_this_turn": "turn-scoped",
    r"mon\.stat_points\.\d|mon\.nature\.\w+": "spreads: identical by construction here (true sheets)",
    r"mon\.(counter|mirror)_(slot|damage)|mon\.last_hit_this_turn": "Counter / Mirror Coat: cleared at the top of `resolve_turn`",
    r"foe\.order\.\d": "the foe's party positions: only Illusion reads them (on the fallback list)",
    r"side_conditions\.(wide_guard|quick_guard|crafty_shield|mat_block)": "turn-scoped (cleared at the top of `resolve_turn`)",
    r"foe\.mon\.charge_target": "hidden: the charge turn's log line has no target",
    r"foe\.mon\.last_move_target": "hidden under redirection (Follow Me, Storm Drain): the log shows where the move went, not the choice",

    r"mon\.last_move_used_type": "Conversion 2 only (not M-C legal)",
    r"mon\.bide_damage": "Bide only (not M-C legal)",
    r"mon\.sleep_start": "Gen 5 only (slp.onSwitchIn resets the counter to it)",
    r"mon\.moves_revealed": "closed-sheet formats only (VGC13): the observation reads it only when sheets are closed",
    r"side_conditions\.(sea_of_fire|swamp|rainbow)_turns": "the Pledges only (not M-C legal)",
}


FAINTED_KEEP = {"species", "ability", "base_ability", "suppressed_ability", "item", "moves", "pp", "hp", "max_hp", "stats", "status",
                "boosts", "types", "mega", "flags", "base_moves", "base_pp", "pre_transform_species", "stat_points", "nature"}

GATES = {"choice_move": ("flag", "CHOICE_LOCKED"), "roost_types": ("flag", "ROOST"), "charge_target": ("flag", "CHARGING"),
         "charge_move": ("flag", "CHARGING"),

         "last_move_target": ("targeted_last_move", None), "encore_move": ("field", "encore_turns"),
         "disable_move": ("field", "disable_turns"), "trapped_by": ("field", "trap_turns"),
         "status_counter": ("status", None),


         "base_moves": ("mon_flag", "TRANSFORMED"), "base_pp": ("mon_flag", "TRANSFORMED"),
         "pre_transform_species": ("mon_flag", "TRANSFORMED"),

         "suppressed_ability": ("ability_empty", None)}

TURN_SCOPED_FLAGS = {"FLINCH", "PROTECTED", "ENDURING", "HELPINGHAND", "FOLLOWME", "RAGEPOWDER", "KINGSSHIELD", "SPIKYSHIELD",
                     "BANEFULBUNKER", "BERRY_CHECK", "ACTED_THIS_TURN", "QUASHED", "FOCUSING", "FOCUS_LOST", "BEAK_BLAST", "ELECTRIFIED",
                     "ROUND_UP", "AFTER_YOU", "DRAGGED_IN", "MOVED_THIS_TURN", "ALIVE_AT_HIT_START", "ATE_BERRY", "SEEN_FAINTED",
                     "QUICK_CLAW", "RED_CARD_DRAG", "RED_CARD_HIT", "SELF_DESTRUCTING", "BEAK_BURN_DUE", "ELECTRIFY_FAILS",
                     "MOVES_LAST", "STALL_SLOW", "USED_ITEM_TURN", "IN_RESIDUAL"}

TURN_SCOPED_FLAGS |= {"MOVE_USED", "ITEM_USED", "DISGUISE_BUSTED", "ENCORE_REQUEUED", "SPARKLING_ARIA", "ALLY_SWITCHED", "BATON_PASS",
                      "SHED_TAIL", "SELF_SWITCH", "DRAG_PENDING", "REVIVAL", "VOLUNTARY_SWITCH", "MOVE_CANCELLED", "SUB_HIT", "GEM",
                      "UNBURDEN_LATE",
                      "TRANSFORM_STASH"}
TURN_SCOPED_AFTER_TURN_1 = {"HURT_THIS_TURN", "STATS_RAISED", "STATS_LOWERED"}

PRESENCE_ONLY = {"confusion_turns", "taunt_turns", "encore_turns", "disable_turns", "heal_block_turns", "throat_chop_turns", "yawn_turns",
                 "trap_turns", "sub_hp", "lock_turns", "lock_true", "move_actions_since_switch_in", "magnet_rise_turns"}

FOE_HIDDEN = {"pp", "base_pp"}


def flag_names() -> dict[str, dict[int, str]]:
    src = (ROOT / "crates/engine-core/src/mon.rs").read_text(encoding="utf8")
    out = {}
    for mod in ("volatile_flags", "mon_flags"):
        body = src.split(f"pub mod {mod}", 1)[1].split("\n}", 1)[0]
        out[mod] = {1 << int(n): name for name, n in re.findall(r"pub const (\w+): u\d+ = 1 << (\d+);", body)}
    return out


FLAGS = flag_names()


def condition_ids() -> dict[int, str]:
    src = (ROOT / "crates/engine-core/src/mon.rs").read_text(encoding="utf8")
    body = src.split("pub mod condition_ids", 1)[1].split("\n}", 1)[0]
    return {int(n): name for name, n in re.findall(r"pub const (\w+): u8 = (\d+);", body)}


CONDS = condition_ids()

TURN_SCOPED_CONDS = {"PRESENT", "FOCUSBAND_DRAW", "CALLED_PRIORITY", "CALLED_SLEEP_USABLE", "SNATCHED", "INSTRUCTED",
                     "HELPINGHAND_RESTARTS", "MEFIRST",
                     "MIMIC", "BIDE", "PLEDGE",
                     "SHELLTRAP",
                     "MAXGUARD"}


def conds_of(d: dict) -> dict[str, set]:


    out: dict[str, set] = {}
    for path, v in d.items():
        m = re.fullmatch(r"(.*)\.volatiles\.conds\.slots\.(\d+)\.0", path)
        if m and v != "0":
            name = CONDS.get(int(v), v)
            if name not in TURN_SCOPED_CONDS:
                out.setdefault(m.group(1), set()).add((name, d.get(f"{m.group(1)}.volatiles.conds.slots.{m.group(2)}.1")))
    return out


def flatten(dump: str) -> dict[str, str]:

    out: dict[str, str] = {}
    stack: list[list] = [["", 0, True]]
    for raw in dump.splitlines():
        line = raw.strip().rstrip(",")
        if not line:
            continue
        top = stack[-1]
        if line in ("}", "]", ")"):
            stack.pop()
            continue
        m = re.match(r"^(\w+): (.*)$", line)
        if m:
            name, rest = m.group(1), m.group(2)
        else:
            name, rest = str(top[1]), line
            top[1] += 1
        path = top[0] if top[2] else (f"{top[0]}.{name}" if top[0] else name)
        if rest.endswith(("{", "[", "(")):
            stack.append([path, 0, rest == "Some("])
        else:
            out[path] = rest
    return out


def side_index(path: str) -> tuple[int | None, str]:

    parts = path.split(".")
    if parts[0] == "0" and len(parts) > 1:
        return int(parts[1]), ".".join(parts[2:])
    return None, {"1": "field", "2": "turn", "3": "pending"}[parts[0]] + ("." + ".".join(parts[1:]) if len(parts) > 1 else "")


def generic(rest: str) -> str:

    return re.sub(r"^mons\.\d+\.", "mon.", rest)


def compare(want: dict, got: dict, me: int, max_hp: dict, turn: int) -> list[tuple[str, str, str, str]]:

    bad = []
    cw, cg = conds_of(want), conds_of(got)
    for base in sorted(set(cw) | set(cg)):
        if cw.get(base, set()) != cg.get(base, set()):
            side, rest = side_index(base + ".x")
            who = "" if side is None else ("my." if side == me else "foe.")
            bad.append((who + "mon.conds", base, str(sorted(cw.get(base, set()))), str(sorted(cg.get(base, set())))))
    for path in sorted(set(want) | set(got)):
        w, g = want.get(path), got.get(path)
        if w == g or ".volatiles.conds.slots." in path:
            continue
        side, rest = side_index(path)
        who = "" if side is None else ("my." if side == me else "foe.")
        key = generic(rest)
        if any(re.fullmatch(p, key) or re.fullmatch(p, who + key) for p in EXCLUDED):
            continue

        field_name = key.split(".")[1] if key.startswith("mon.") else key.rsplit(".", 1)[-1]
        base = ".".join(path.split(".")[:4])
        if key.startswith("mon.") and field_name not in FAINTED_KEEP:
            fainted_bit = next(b for b, n in FLAGS["mon_flags"].items() if n == "FAINTED")
            if int(want.get(base + ".flags.0", 0)) & fainted_bit:
                continue
        if key.startswith("mon.") and field_name in GATES:
            kind, gate = GATES[field_name]
            if kind == "flag":
                bit = next(b for b, n in FLAGS["volatile_flags"].items() if n == gate)
                if not int(want.get(f"{base}.volatiles.flags", 0)) & bit:
                    continue
            elif kind == "mon_flag":
                bit = next(b for b, n in FLAGS["mon_flags"].items() if n == gate)
                if not int(want.get(f"{base}.flags.0", 0)) & bit:
                    continue
            elif kind == "ability_empty":
                if want.get(f"{base}.ability", "0") != "0":
                    continue
            elif kind == "targeted_last_move":
                last = int(want.get(f"{base}.last_move", 0))
                if last == 0 or ve.move_choice_target(last) == "none":
                    continue
            elif kind == "status":
                if want.get(f"{base}.status") == "None":
                    continue
            elif want.get(f"{base}.{gate}", "0") == "0":
                continue
        m = re.fullmatch(r"(.*side_conditions)\.wish_hp\.(\d)", path)
        if m and want.get(f"{m.group(1)}.wish_turns.{m.group(2)}", "0") == "0":
            continue
        if key == "mon.move_result_this_turn" and (w == "2") == (g == "2"):
            continue
        if key == "mon.status_counter" and want.get(f"{base}.status") == "Sleep" and 0 <= int(g or 0) - int(w or 0) <= 1:
            continue
        if key.startswith("mon.") and field_name in PRESENCE_ONLY:
            if (w not in (None, "0")) == (g not in (None, "0")):
                continue
        if who == "foe." and key.startswith("mon.") and key.split(".")[1] in FOE_HIDDEN:
            continue
        if who == "foe." and key == "mon.hp" and w is not None and g is not None:
            mx = max_hp.get(base, 100)
            if abs(int(w) - int(g)) <= mx // HP_SCALE + 1:
                continue
        if key in ("mon.volatiles.flags", "mon.flags.0"):
            names = FLAGS["volatile_flags" if key == "mon.volatiles.flags" else "mon_flags"]
            x = int(w or 0) ^ int(g or 0)
            for bit, name in names.items():
                if x & bit and name not in TURN_SCOPED_FLAGS and not (turn > 0 and name in TURN_SCOPED_AFTER_TURN_1):
                    bad.append((f"{who}{key}:{name}", path, str(bool(int(w or 0) & bit)), str(bool(int(g or 0) & bit))))
            continue
        bad.append((who + key, path, str(w), str(g)))
    return bad


def choice_targets(choice: str) -> list[int | None]:

    out = []
    for part in choice.split(","):
        w = part.split()
        if len(w) >= 3 and w[0] == "move" and w[2].lstrip("-").isdigit():
            n = int(w[2])
            out.append(n - 1 if n > 0 else 2 + (-n - 1))
        else:
            out.append(None)
    return out


PADDING = [4, 5, 10, 11]


def compare_obs(pool, side: int, e: dict) -> list[tuple[str, str, str, str]]:


    f = np.zeros((1, ve.FIELD_FEATURES), np.float32)
    ids = np.zeros((1, ve.MON_TOKENS, ve.MON_IDS), np.int32)
    feats = np.zeros((1, ve.MON_TOKENS, ve.MON_FEATURES), np.float32)
    hist = np.zeros((1, ve.HISTORY_LEN, ve.EVENT_FIELDS), np.int32)
    pool.observe(side, f, ids, feats, hist)
    groups = [
        ("field", np.array(e["field"], np.float32), f[0], lambda i: FIELD_NAMES[i]),
        ("ids", np.array(e["mon_ids"]).reshape(ids[0].shape), ids[0], lambda i: f"tok{i // ve.MON_IDS}.{ID_NAMES[i % ve.MON_IDS]}"),
        ("mon", np.array(e["mon_features"], np.float32).reshape(feats[0].shape), feats[0],
         lambda i: f"tok{i // ve.MON_FEATURES}.{MON_NAMES[i % ve.MON_FEATURES]}"),
        ("hist", np.array(e["history"]).reshape(hist[0].shape), hist[0], lambda i: f"row{i // ve.EVENT_FIELDS}.{HIST_NAMES[i % ve.EVENT_FIELDS]}"),
    ]
    bad = []
    for name, want, got, label in groups:
        if name in ("ids", "mon"):

            want, got = np.delete(want, PADDING, 0), np.delete(got, PADDING, 0)
        for i in np.flatnonzero(~np.isclose(want.ravel(), got.ravel(), atol=1e-5)):
            bad.append((f"obs.{name}:{label(i).split('.', 1)[-1]}", f"obs {label(i)}", f"{want.ravel()[i]:g}", f"{got.ravel()[i]:g}"))
    return bad


def check(path: Path, diff_exe: Path, show: int, counts: Counter, errors: Counter) -> tuple[int, int]:
    scenario = json.loads(path.read_text(encoding="utf8"))
    if any(m.get("ability") == "Illusion" for m in scenario["team1"] + scenario["team2"]):
        counts["skipped: Illusion (fallback list)"] += 1
        return 0, 0
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "obs.json"
        run = subprocess.run([str(diff_exe), "obs", str(path), str(out)], capture_output=True, text=True, encoding="utf8")
        if run.returncode != 0:
            counts["skipped: engine replay diverged"] += 1
            return 0, 0
        dumps = json.loads(Path(str(out) + ".dumps.json").read_text())
        engine_obs = json.loads(out.read_text())
    proto = json.loads(subprocess.run(["node", str(ROOT / "tools/showdown-oracle/protocol.js"), str(path)], check=True,
                                      capture_output=True, text=True, encoding="utf8").stdout)["steps"]
    sheets = {"p1": scenario["team1"], "p2": scenario["team2"]}
    pool = ve.BattlePool(1)

    fmt = scenario.get("format")
    fmt = None if fmt in (None, "gen9championsvgc2026regmc") else fmt
    global HP_SCALE
    HP_SCALE = SHOWN_HP_SCALE[fmt]
    try:
        teams = {p: (pool.register_team((sheets[p] * 2)[:6]) if fmt is None else pool.register_team((sheets[p] * 2)[:6], fmt))
                 for p in ("p1", "p2")}
    except ValueError as e:
        counts[f"skipped: {str(e)[:60]}"] += 1
        return 0, 0

    set_info = {p: [{"moves": [ve.lookup("move", mv) for mv in s_["moves"]] + [0] * (4 - len(s_["moves"])),
                     "ability": ve.lookup("ability", s_["ability"]), "item": ve.lookup("item", s_.get("item") or "")}
                    for s_ in sheets[p]] for p in ("p1", "p2")}
    trackers = {p: Tracker(p, sheets[p], sheets["p2" if p == "p1" else "p1"], fmt=fmt) for p in ("p1", "p2")}
    bring = {"p1": [0, 1, 2, 3], "p2": [0, 1, 2, 3]}
    mismatches = points = 0
    last_targets = {"p1": {}, "p2": {}}
    pending = {"p1": {}, "p2": {}}
    for step, pro in enumerate(proto):
        want = flatten(dumps[step])
        turn_decision = want.get("3") == "Turn"
        max_hp = {k.rsplit(".", 1)[0]: int(v) for k, v in want.items() if k.endswith(".max_hp")}
        for side, p in ((0, "p1"), (1, "p2")):
            t = trackers[p]
            t.feed(pro[p]["lines"])
            t.set_request(pro[p]["request"])
            if pro[p]["request"] is None:
                continue

            for k, (tg, turn) in list(pending[p].items()):
                if t.mons[p][k].move_turn >= turn:
                    last_targets[p][k] = tg
                    del pending[p][k]
            charge_targets = dict(last_targets[p])
            if step < len(scenario["turns"]):
                t.note_choice(scenario["turns"][step][p])
                active = {m.slot: k for k, m in enumerate(t.mons[p]) if m.slot is not None}
                parts = scenario["turns"][step][p].split(",")
                for k, tg in enumerate(choice_targets(scenario["turns"][step][p])):
                    if k not in active or parts[k].split()[0] == "pass":
                        continue
                    if tg is None:
                        pending[p].pop(active[k], None)
                    else:
                        pending[p][active[k]] = (tg, t.turn)
            if not turn_decision:
                continue
            points += 1
            try:
                snap = snapshot(t, teams, bring, party_order(t, pro[p]["request"], bring[p]), charge_targets,
                                foe_sets=set_info["p2" if p == "p1" else "p1"])
                pool.load_state(0, snap, 0)
            except Unsupported as e:
                counts[f"fallback: {e}"] += 1
                continue
            except Exception as e:
                msg = str(e).split("\n")[0][:120]
                errors[msg] += 1
                mismatches += 1
                if show > 0:
                    print(f"  {path.name} step {step} {p}: load_state failed: {msg}")
                    show -= 1
                continue
            bad = compare(want, flatten(pool.dump(0)), side, max_hp, int(want["2"])) + compare_obs(pool, side, engine_obs[step][side])
            for key, where, w, g in bad:
                counts[key] += 1
                mismatches += 1
                if show > 0:
                    print(f"  {path.name} step {step} {p} {where} [{key}]: true {w} rebuilt {g}")
                    show -= 1
    return mismatches, points


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", nargs="+", help="scenario files, or directories of them")
    ap.add_argument("--show", type=int, default=8, help="print this many individual mismatches per scenario")
    ap.add_argument("--diff", default=str(ROOT / "target/debug/diff.exe"), help="the diff binary (writes .dumps.json)")
    args = ap.parse_args()
    counts: Counter = Counter()
    errors: Counter = Counter()
    clean = total_points = 0
    paths = [q for s in args.scenarios for q in (sorted(Path(s).glob("scenario-*.json")) or sorted(Path(s).glob("*.json"))
                                                 if Path(s).is_dir() else [Path(s)])]
    for p in paths:
        n, pts = check(p, Path(args.diff), args.show, counts, errors)
        clean += n == 0
        total_points += pts
        print(f"{p.name}: {'OK' if n == 0 else f'{n} mismatches'} ({pts} decision points)", flush=True)
    print(f"\n{clean}/{len(paths)} scenarios exact, {total_points} decision points")
    for k, v in errors.most_common(10):
        print(f"  {v:6d}  load_state: {k}")
    for k, v in counts.most_common(40):
        print(f"  {v:6d}  {k}")


if __name__ == "__main__":
    main()













from __future__ import annotations

SLEEP_EXPECTED = 5 / 3
HIGH_CHAOS = 2.0


def net_bad_luck(lines: list[str], me: str) -> float:

    bad = good = 0.0
    asleep: dict[str, int] = {}
    for ln in lines:
        if not ln.startswith("|") or ln.startswith(("|c|", "|chat|", "|raw|", "|html|", "|uhtml", "|pm|")):
            continue
        p = ln.split("|")
        kind = p[1] if len(p) > 1 else ""
        who = p[2][:2] if len(p) > 2 else ""
        mine = who == me
        if kind == "-crit":
            bad, good = (bad + 1, good) if mine else (bad, good + 1)
        elif kind == "-miss":
            bad, good = (bad + 1, good) if mine else (bad, good + 1)
        elif kind == "cant" and len(p) > 3 and p[3] in ("par", "frz", "flinch"):
            bad, good = (bad + 1, good) if mine else (bad, good + 1)
        elif kind == "-status" and len(p) > 3 and p[3] == "slp":
            asleep[p[2][:2] + p[2][3:]] = 0
        elif kind == "cant" and len(p) > 3 and p[3] == "slp":
            key = p[2][:2] + p[2][3:]
            if key in asleep:
                asleep[key] += 1
        elif kind == "-curestatus" and len(p) > 3 and p[3] == "slp":
            key = p[2][:2] + p[2][3:]
            if key in asleep and "[msg]" in p[4:]:
                dev = asleep.pop(key) - SLEEP_EXPECTED
                bad, good = (bad + dev, good) if mine else (bad, good + dev)
        elif kind == "-activate" and len(p) > 3 and p[3] == "confusion":
            continue
        elif kind == "-damage" and len(p) > 4 and "[from] confusion" in p[4:]:
            bad, good = (bad + 1, good) if mine else (bad, good + 1)
    return bad - good

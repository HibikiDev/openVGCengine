







from __future__ import annotations

import argparse
import json
from pathlib import Path

LOGS = Path("trainer/runs/showdown_logs")


class Names:




    def __init__(self, lines: list[str]):
        self.preview: dict[str, list[str]] = {"p1": [], "p2": []}
        self.at: dict[int, dict[str, str]] = {}
        self.final: dict[str, str] = {}
        cur = self.final
        for line in lines:
            q = line.split("|")
            if len(q) > 3 and q[1] == "poke" and q[2] in self.preview:
                self.preview[q[2]].append(q[3].split(",")[0])
            elif len(q) > 3 and q[1] in ("switch", "drag", "replace", "detailschange") and q[2][:2] in ("p1", "p2") and ": " in q[2]:
                k = f"{q[2][:2]}:{q[2].split(': ', 1)[1]}"
                if q[1] == "detailschange" or "-Mega" not in cur.get(k, ""):
                    cur[k] = q[3].split(",")[0]
            elif len(q) > 2 and q[1] == "turn" and q[2].isdigit():
                self.at[int(q[2])] = dict(cur)

    def _map(self, turn: int | None) -> dict[str, str]:
        if turn is None:
            return self.final
        return self.at.get(turn) or self.at.get(turn - 1) or ({} if turn <= 1 else self.final)

    def get(self, side: str, nick: str, turn: int | None = None) -> str:
        m = self._map(turn)
        if f"{side}:{nick}" in m:
            return m[f"{side}:{nick}"]
        hit = [x for x in self.preview.get(side, []) if x == nick or x.startswith(nick + "-")]
        return hit[0] if len(hit) == 1 else nick

    def label(self, text: str, actor: str, other: str, turn: int | None) -> str:


        if text.startswith("switch "):
            return "switch " + self.get(actor, text[7:], turn)
        if " -> " not in text:
            return text
        mv, tgt = text.split(" -> ", 1)
        tgt, mega = (tgt[:-6], " +mega") if tgt.endswith(" +mega") else (tgt, "")
        m = self._map(turn)
        side = actor if f"{actor}:{tgt}" in m and f"{other}:{tgt}" not in m else other
        return f"{mv} -> {self.get(side, tgt, turn)}{mega}"


def actual_moves(lines: list[str], me: str | None) -> dict[int, list[str]]:

    out: dict[int, list[str]] = {}
    turn = 0
    cur: dict[str, str] = {}

    def sp(ident: str) -> str:
        return cur.get(f"{ident[:2]}:{ident.split(': ', 1)[1]}", ident.split(": ", 1)[1])

    for line in lines:
        parts = line.split("|")
        if len(parts) > 2 and parts[1] == "turn":
            turn = int(parts[2])
            continue
        if len(parts) > 3 and parts[1] in ("switch", "drag", "replace", "detailschange") and ": " in parts[2]:
            k = f"{parts[2][:2]}:{parts[2].split(': ', 1)[1]}"
            if parts[1] == "detailschange" or "-Mega" not in cur.get(k, ""):
                cur[k] = parts[3].split(",")[0]
        if len(parts) > 3 and parts[1] in ("move", "switch", "drag") and me and not parts[2].startswith(me):
            who = sp(parts[2])
            if parts[1] == "move":
                tgt = sp(parts[4]) if len(parts) > 4 and ": " in parts[4] else ""
                out.setdefault(turn, []).append(f"{who}: {parts[3]}" + (f" -> {tgt}" if tgt and parts[4] != parts[2] else ""))
            elif turn:
                out.setdefault(turn, []).append(f"switch in {who}")
    return out


def options(row: dict) -> str:


    text = ", ".join(f"{'*' if label == row.get('chosen') else ''}{label} {p:.0%}" for label, p in row["options"])
    if "policy" in row and row["chosen"] not in [label for label, _ in row["options"]]:
        text += f"  | played *{row['chosen']} (searched)"
    return text


def render(path: Path) -> str:

    trace = json.loads(path.read_text(encoding="utf8"))
    me = next((e["req_active"][0][:2] for e in trace if e.get("req_active")), None)
    log = path.with_name(path.name.replace(".trace.json", ".log"))
    lines = log.read_text(encoding="utf8").splitlines() if log.exists() else []
    foe_did = actual_moves(lines, me)
    names = Names(lines)
    foe = {"p1": "p2", "p2": "p1"}.get(me or "", "")
    out = [path.name]
    shown: set[int] = set()
    for e in trace:
        why = e.get("why")
        head = f"turn {e['turn']}"
        if "preview" in e:
            pv = e["preview"]
            out.append(f"preview: bring {' / '.join(pv.get('bring', []))}" + (f"  (lead p {pv['lead_p']:.2f})" if "lead_p" in pv else ""))
            continue
        if not why:
            out.append(f"{head}: {e['choice']}" + (" (random fallback)" if e.get("random") else ""))
            continue
        mode = "  [closing out]" if why.get("mode") == "closer" else ""
        s = e.get("search") or {}
        if "q" in s:
            mode += f"  [search: {len(set(s['q']))} distinct, picked q {s['q'][s['chosen']]:+.2f} vs policy top {s['q'][0]:+.2f}]"
        out.append(f"{head}  win {why['win']:.0%}  ->  {e['choice']}{mode}")
        t = e["turn"]

        def ours(x: str) -> str:
            return names.label(x, me, foe, t) if me else x

        def theirs(x: str) -> str:
            return names.label(x, foe, me, t) if me else x

        for row in why["slots"]:
            if row:
                row = {**row, "mon": names.get(me, row["mon"], t) if me else row["mon"], "chosen": ours(row["chosen"]),
                       "options": [[ours(a), p] for a, p in row["options"]], **({"policy": ours(row["policy"])} if "policy" in row else {})}
                mega = f"  [mega {row['mega_p']:.0%}]" if "mega_p" in row else ""
                out.append(f"   {row['mon']:<12} {options(row)}{mega}")
        for g in why.get("foe_guess") or []:
            if g:
                mon = names.get(foe, g["mon"], t) if me else g["mon"]
                out.append(f"   expects {mon:<12} " + ", ".join(f"{theirs(label)} {p:.0%}" for label, p in g["options"]))
        if e["turn"] in foe_did and why.get("foe_guess") and e["turn"] not in shown:
            shown.add(e["turn"])
            out.append(f"   foe did: {'; '.join(foe_did[e['turn']])}")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trace", nargs="?")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--write-missing", action="store_true", help="write <room>.why.txt for every logged game that lacks one")
    ap.add_argument("--rewrite", action="store_true", help="with --write-missing: rewrite the existing ones too (after a format fix)")
    args = ap.parse_args()
    if args.write_missing:
        n = 0
        for p in LOGS.glob("*.trace.json"):
            dst = p.with_name(p.name.replace(".trace.json", ".why.txt"))
            if args.rewrite or not dst.exists():
                try:
                    dst.write_text(render(p), encoding="utf8")
                    n += 1
                except Exception as e:
                    print(f"{p.name}: {type(e).__name__}: {e}")
        print(f"wrote {n} .why.txt files")
        return
    path = max(LOGS.glob("*.trace.json"), key=lambda p: p.stat().st_mtime) if args.latest or not args.trace else Path(args.trace)
    print(render(path))


if __name__ == "__main__":
    main()

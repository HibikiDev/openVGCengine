







from __future__ import annotations

STATS = {"atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe", "accuracy": "accuracy", "evasion": "evasion"}
STATUS = {"brn": "burned", "par": "paralyzed", "slp": "fell asleep", "psn": "was poisoned", "tox": "was badly poisoned",
          "frz": "was frozen"}
CANT = {"flinch": "flinched", "par": "is fully paralyzed", "slp": "is fast asleep", "frz": "is frozen solid",
        "recharge": "must recharge", "Taunt": "can't use that move (Taunt)", "Encore": "is locked by Encore", "nopp": "has no PP left"}
WEATHER = {"SunnyDay": "harsh sunlight", "RainDance": "rain", "Sandstorm": "a sandstorm", "Snowscape": "snow", "Snow": "snow",
           "DesolateLand": "extremely harsh sunlight", "PrimordialSea": "heavy rain", "DeltaStream": "strong winds"}
SKIP = {"j", "J", "l", "L", "n", "N", "c", "c:", "pm", "raw", "html", "uhtml", "uhtmlchange", "request", "inactive", "inactiveoff",
        "t:", "gametype", "gen", "tier", "rule", "rated", "title", "init", "teamsize", "teampreview", "showteam", "poke", "clearpoke",
        "tempnotify", "tempnotifyoff", "-anim", "-hint", "upkeep", "detailschange", "chat", "timestamp", "badge", "", "split",
        "-nothing", "-center", "-combine", "-waiting", "debug", "seed", "error", "bigerror", "sentchoice", "start"}


def _clean(s: str) -> str:
    for pre in ("move: ", "ability: ", "item: "):
        if s.startswith(pre):
            return s[len(pre):]
    return s


def _pct(cond: str) -> float | None:


    hp = (cond.split()[0] if cond else "").rstrip("gyr")
    if hp == "0":
        return 0.0
    if "/" in hp:
        a, b = hp.split("/", 1)
        try:
            return 100.0 * float(a) / float(b) if float(b) else None
        except ValueError:
            return None
    return None


def narrate(lines: list[str], me: str | None = None) -> dict:
    players, turns, result = {}, [{"turn": 0, "events": []}], None
    hp: dict[str, float] = {}
    active: dict[str, str] = {}
    forms: dict[str, str] = {}
    species_of: dict[str, str] = {}
    rating = []
    preview: dict[str, list[str]] = {"p1": [], "p2": []}

    def side_of(ident: str) -> str | None:
        s = ident[:2] if ident[:2] in ("p1", "p2") else None
        return None if s is None or me is None else ("us" if s == me else "them")

    def bare(ident: str) -> str:
        return ident.split(": ", 1)[1] if ": " in ident else ident

    def name(ident: str, base: bool = False) -> str:


        n = species_of.get(key(ident)) or bare(ident)
        f = None if base else forms.get(key(ident))
        if f:
            n = f
        s = ident[:2] if ident[:2] in ("p1", "p2") else None
        if s is None:
            return n
        return f"⟦{s if me is None else ('us' if s == me else 'them')}|{n}⟧"

    def key(ident: str) -> str:
        return f"{ident[:2]}:{bare(ident)}"

    def add(text: str, ident: str = "", kind: str = "event") -> None:
        turns[-1]["events"].append({"side": side_of(ident) if ident else None, "text": text, "kind": kind})

    def tags(p: list[str]) -> dict[str, str]:
        out = {}
        for x in p:
            if x.startswith("[") and "]" in x:
                k, _, v = x[1:].partition("]")
                out[k] = v.strip()
        return out

    for ln in lines:
        if not ln.startswith("|"):
            continue
        p = ln.split("|")
        cmd = p[1] if len(p) > 1 else ""
        if cmd == "poke" and len(p) > 3 and p[2] in preview:
            preview[p[2]].append(p[3].split(",")[0])
            continue
        if cmd == "detailschange" and len(p) > 3:
            forms[key(p[2])] = p[3].split(",")[0]
            continue
        if cmd in SKIP:
            if cmd == "raw" and "'s rating: " in ln:
                rating.append(ln.split("|", 2)[2].replace("&rarr;", "→").replace("<strong>", "").replace("</strong>", "")
                              .replace("<br />", " ").strip())
            continue
        t = tags(p[2:])
        src = f" ({_clean(t['from'])})" if t.get("from") else ""
        if cmd == "player" and len(p) > 3 and p[3]:
            players[p[2]] = p[3]
        elif cmd == "turn":
            turns.append({"turn": int(p[2]), "events": []})
        elif cmd in ("switch", "drag", "replace"):
            pos, nm, cond = p[2][:3], bare(p[2]), p[4] if len(p) > 4 else ""
            species = p[3].split(",")[0]
            if key(p[2]) not in forms:
                species_of[key(p[2])] = species

            out = active.get(pos) if cmd != "replace" else None
            active[pos] = nm
            pc = _pct(cond)
            if pc is not None:
                hp[key(p[2])] = pc
            label = name(p[2])
            who = players.get(p[2][:2], p[2][:2])
            hp_note = f" ({pc:.0f}%)" if pc is not None and pc < 100 else ""
            if out and out != nm:
                out_tag = name(f"{pos}: {out}")
                text = (f"{who} withdrew {out_tag}, sent out {label}" if cmd == "switch"
                        else f"{out_tag} was dragged out; {label} came in")
            else:
                text = f"{who} " + {"switch": "sent out", "drag": "had dragged in", "replace": "revealed"}[cmd] + f" {label}"
            add(text + hp_note, p[2], "switch")
        elif cmd == "move":
            target = name(p[4]) if len(p) > 4 and p[4] and not p[4].startswith("[") else ""
            extra = []
            if "spread" in t:
                extra.append("spread")
            if "miss" in t:
                extra.append("missed")
            if "notarget" in t:
                extra.append("no target")
            text = f"{name(p[2])} used {p[3]}" + (f" → {target}" if target and target != name(p[2]) else "")
            add(text + (f" [{', '.join(extra)}]" if extra else "") + src, p[2], "move")
        elif cmd in ("-damage", "-heal", "-sethp"):
            k = key(p[2])
            new = _pct(p[3]) if len(p) > 3 else None
            old = hp.get(k)
            if new is not None:
                hp[k] = new
            if new is None:
                continue
            if old is None:
                delta = ""
            else:
                d = new - old
                delta = f"{'+' if d >= 0 else '−'}{abs(d):.0f}% " if abs(d) >= 0.5 else ""
            add(f"{name(p[2])} {delta}→ {new:.0f}%{src}", p[2], "damage" if cmd == "-damage" else "heal")
        elif cmd == "faint":
            hp[key(p[2])] = 0.0
            if active.get(p[2][:3]) == bare(p[2]):
                active[p[2][:3]] = None
            add(f"{name(p[2])} fainted", p[2], "faint")
        elif cmd == "-supereffective":
            add("  super effective" + (f" on {name(p[2])}" if len(p) > 2 else ""), p[2], "note")
        elif cmd == "-resisted":
            add("  resisted" + (f" by {name(p[2])}" if len(p) > 2 else ""), p[2], "note")
        elif cmd == "-crit":
            add(f"  critical hit on {name(p[2])}", p[2], "note")
        elif cmd == "-immune":
            add(f"  {name(p[2])} is immune{src}", p[2], "note")
        elif cmd == "-miss":
            add(f"  {name(p[2])} missed" + (f" {name(p[3])}" if len(p) > 3 and p[3] else ""), p[2], "note")
        elif cmd == "-fail":
            add(f"  it failed ({name(p[2])}{', ' + _clean(p[3]) if len(p) > 3 and p[3] and not p[3].startswith('[') else ''})", p[2], "note")
        elif cmd in ("-boost", "-unboost"):
            n = int(p[4]) if len(p) > 4 and p[4].lstrip("-").isdigit() else 1
            add(f"{name(p[2])} {STATS.get(p[3], p[3])} {'+' if cmd == '-boost' else '−'}{n}{src}", p[2], "boost")
        elif cmd == "-clearnegativeboost":
            add(f"{name(p[2])}'s lowered stats were restored{src}", p[2], "boost")
        elif cmd == "-status":
            add(f"{name(p[2])} {STATUS.get(p[3], p[3])}{src}", p[2], "status")
        elif cmd == "-curestatus":
            add(f"{name(p[2])} is no longer {STATUS.get(p[3], p[3]).replace('was ', '').replace('fell ', '')}{src}", p[2], "status")
        elif cmd == "-weather":
            if "upkeep" in t:
                continue
            w = p[2]
            add("the weather cleared" if w == "none" else f"{WEATHER.get(w, w)} started{src}", t.get("of", ""), "field")
        elif cmd in ("-fieldstart", "-fieldend"):
            add(f"{_clean(p[2])} {'started' if cmd == '-fieldstart' else 'ended'}{src}", t.get("of", ""), "field")
        elif cmd in ("-sidestart", "-sideend"):
            who = players.get(p[2][:2], p[2][:2])
            add(f"{_clean(p[3])} {'up' if cmd == '-sidestart' else 'ended'} on {who}'s side", p[2][:2] + "a: x", "field")
        elif cmd == "-singleturn":
            continue
        elif cmd == "-activate":
            what = _clean(p[3]) if len(p) > 3 else ""
            if what == "Protect":
                add(f"  {name(p[2])} protected itself", p[2], "note")
            elif what:
                add(f"  {what} ({name(p[2])})" + (f": {_clean(p[4])}" if len(p) > 4 and p[4] and not p[4].startswith("[") else ""), p[2], "note")
        elif cmd in ("-start", "-end"):
            what = _clean(p[3]) if len(p) > 3 else ""
            if what.startswith("perish"):
                add(f"{name(p[2])}: Perish count {what[6:]}", p[2], "note")
            else:
                add(f"{name(p[2])}: {what} {'started' if cmd == '-start' else 'ended'}{src}", p[2], "note")
        elif cmd == "-ability":
            add(f"{name(p[2])}'s {p[3]}{src}", p[2], "ability")
        elif cmd in ("-item", "-enditem"):
            if "weaken" in t:
                add(f"  {p[3]} weakened the hit", p[2], "note")
                continue
            verb = "has" if cmd == "-item" else ("ate its" if "eat" in t else "used up its")
            add(f"{name(p[2])} {verb} {p[3]}{src}", p[2], "item")
        elif cmd == "-mega":

            add(f"{name(p[2], base=True)} Mega Evolved ({p[4] if len(p) > 4 else ''})", p[2], "mega")
        elif cmd == "-formechange":
            add(f"{name(p[2])} changed form: {p[3]}", p[2], "note")
        elif cmd == "cant":
            why = _clean(p[3]) if len(p) > 3 else ""
            add(f"{name(p[2])} " + CANT.get(why, f"can't move ({why})" if why else "can't move"), p[2], "note")
        elif cmd == "-prepare":
            add(f"{name(p[2])} is charging {p[3]}", p[2], "note")
        elif cmd == "-mustrecharge":
            add(f"{name(p[2])} must recharge", p[2], "note")
        elif cmd == "-hitcount":
            add(f"  hit {p[3]} times", p[2], "note")
        elif cmd == "-transform":
            add(f"{name(p[2])} transformed into {name(p[3])}", p[2], "note")
        elif cmd == "-fieldactivate":
            add(f"{_clean(p[2])} affects the field", "", "field")
        elif cmd == "-copyboost":
            add(f"{name(p[2])} copied {name(p[3])}'s stat changes{src}", p[2], "boost")
        elif cmd == "-clearallboost":
            add("all stat changes were cleared", "", "boost")
        elif cmd == "-block":
            add(f"  {name(p[2])} blocked it ({_clean(p[3]) if len(p) > 3 else ''})", p[2], "note")
        elif cmd == "-message":
            add(p[2], "", "message")
        elif cmd == "win":
            result = p[2]
        elif cmd == "tie":
            result = "tie"
        elif cmd.startswith("-"):
            add(f"{cmd[1:]}: " + " ".join(_clean(x) for x in p[2:] if x and not x.startswith("[")), p[2] if len(p) > 2 else "", "other")

        turns[-1]["hp"] = {k: round(v) for k, v in hp.items()}


        turns[-1]["names"] = {k: forms.get(k) or species_of[k] for k in species_of}
    return {"players": players, "turns": turns, "result": result, "rating": rating, "preview": preview}


def tagged_html(text: str) -> str:

    import html
    import re
    out = html.escape(text)
    return re.sub(r"⟦(us|them|p1|p2)\|(.*?)⟧", lambda m: f'<span class="mon {m.group(1)}">{m.group(2)}</span>', out)


def plain(text: str) -> str:

    import re
    return re.sub(r"⟦(?:us|them|p1|p2)\|(.*?)⟧", r"\1", text)

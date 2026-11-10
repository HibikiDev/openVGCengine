







from __future__ import annotations

STATS = {"atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe", "accuracy": "accuracy", "evasion": "evasion"}
STATUS = {"brn": "burned", "par": "paralyzed", "slp": "fell asleep", "psn": "was poisoned", "tox": "was badly poisoned",
          "frz": "was frozen"}

STATUS_MSG = {"brn": "{mon} burned", "par": "{mon} paralyzed", "slp": "{mon} fell asleep", "psn": "{mon} was poisoned",
              "tox": "{mon} was badly poisoned", "frz": "{mon} was frozen"}
CURE_MSG = {"brn": "{mon} is no longer burned", "par": "{mon} is no longer paralyzed", "slp": "{mon} is no longer asleep",
            "psn": "{mon} is no longer poisoned", "tox": "{mon} is no longer badly poisoned", "frz": "{mon} is no longer frozen"}
CANT = {"flinch": "flinched", "par": "is fully paralyzed", "slp": "is fast asleep", "frz": "is frozen solid",
        "recharge": "must recharge", "Taunt": "can't use that move (Taunt)", "Encore": "is locked by Encore", "nopp": "has no PP left"}
CANT_MSG = {k: "{mon} " + v for k, v in CANT.items()}
WEATHER = {"SunnyDay": "harsh sunlight", "RainDance": "rain", "Sandstorm": "a sandstorm", "Snowscape": "snow", "Snow": "snow",
           "DesolateLand": "extremely harsh sunlight", "PrimordialSea": "heavy rain", "DeltaStream": "strong winds"}
WEATHER_MSG = {k: v + " started" for k, v in WEATHER.items()}
MOVE_FLAGS = {"spread": "spread", "miss": "missed", "notarget": "no target"}
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

    def add(msg: str, ident: str = "", kind: str = "event", *, src: str = "", hp_note: float | None = None,
            flags: list[str] | None = None, raw: bool = False, **slots) -> None:




        ev = {"side": side_of(ident) if ident else None, "kind": kind}
        if raw:
            ev["text"] = msg
        else:
            ev.update(msg=msg, slots=slots)
            if src:
                ev["src"] = src
            if hp_note is not None:
                ev["hp"] = hp_note
            if flags:
                ev["flags"] = flags
            ev["text"] = render_event(ev, "en")
        turns[-1]["events"].append(ev)

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
        src = _clean(t["from"]) if t.get("from") else ""
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
            hp_note = round(pc) if pc is not None and pc < 100 else None
            if out and out != nm:
                out_tag = name(f"{pos}: {out}")
                if cmd == "switch":
                    add("{who} withdrew {out}, sent out {mon}", p[2], "switch", hp_note=hp_note, who=who, out=out_tag, mon=label)
                else:
                    add("{out} was dragged out; {mon} came in", p[2], "switch", hp_note=hp_note, out=out_tag, mon=label)
            else:
                add({"switch": "{who} sent out {mon}", "drag": "{who} had dragged in {mon}", "replace": "{who} revealed {mon}"}[cmd],
                    p[2], "switch", hp_note=hp_note, who=who, mon=label)
        elif cmd == "move":
            target = name(p[4]) if len(p) > 4 and p[4] and not p[4].startswith("[") else ""
            extra = [MOVE_FLAGS[f] for f in ("spread", "miss", "notarget") if f in t]
            if target and target != name(p[2]):
                add("{mon} used {move} → {target}", p[2], "move", src=src, flags=extra, mon=name(p[2]), move=["move", p[3]], target=target)
            else:
                add("{mon} used {move}", p[2], "move", src=src, flags=extra, mon=name(p[2]), move=["move", p[3]])
        elif cmd in ("-damage", "-heal", "-sethp"):
            k = key(p[2])
            new = _pct(p[3]) if len(p) > 3 else None
            old = hp.get(k)
            if new is not None:
                hp[k] = new
            if new is None:
                continue
            kind_ = "damage" if cmd == "-damage" else "heal"
            d = None if old is None else new - old
            if d is not None and abs(d) >= 0.5:
                add("{mon} {delta}% → {hp}%", p[2], kind_, src=src, mon=name(p[2]), delta=f"{'+' if d >= 0 else '−'}{abs(d):.0f}",
                    hp=f"{new:.0f}")
            else:
                add("{mon} → {hp}%", p[2], kind_, src=src, mon=name(p[2]), hp=f"{new:.0f}")
        elif cmd == "faint":
            hp[key(p[2])] = 0.0
            if active.get(p[2][:3]) == bare(p[2]):
                active[p[2][:3]] = None
            add("{mon} fainted", p[2], "faint", mon=name(p[2]))
        elif cmd == "-supereffective":
            add("  super effective on {mon}", p[2], "note", mon=name(p[2])) if len(p) > 2 else add("  super effective", "", "note")
        elif cmd == "-resisted":
            add("  resisted by {mon}", p[2], "note", mon=name(p[2])) if len(p) > 2 else add("  resisted", "", "note")
        elif cmd == "-crit":
            add("  critical hit on {mon}", p[2], "note", mon=name(p[2]))
        elif cmd == "-immune":
            add("  {mon} is immune", p[2], "note", src=src, mon=name(p[2]))
        elif cmd == "-miss":
            if len(p) > 3 and p[3]:
                add("  {mon} missed {target}", p[2], "note", mon=name(p[2]), target=name(p[3]))
            else:
                add("  {mon} missed", p[2], "note", mon=name(p[2]))
        elif cmd == "-fail":
            if len(p) > 3 and p[3] and not p[3].startswith("["):
                add("  it failed ({mon}, {effect})", p[2], "note", mon=name(p[2]), effect=["effect", _clean(p[3])])
            else:
                add("  it failed ({mon})", p[2], "note", mon=name(p[2]))
        elif cmd in ("-boost", "-unboost"):
            n = int(p[4]) if len(p) > 4 and p[4].lstrip("-").isdigit() else 1
            add("{mon} {stat} {change}", p[2], "boost", src=src, mon=name(p[2]), stat=["stat", p[3]],
                change=f"{'+' if cmd == '-boost' else '−'}{n}")
        elif cmd == "-clearnegativeboost":
            add("{mon}'s lowered stats were restored", p[2], "boost", src=src, mon=name(p[2]))
        elif cmd == "-status":
            if p[3] in STATUS_MSG:
                add(STATUS_MSG[p[3]], p[2], "status", src=src, mon=name(p[2]))
            else:
                add("{mon} {effect}", p[2], "status", src=src, mon=name(p[2]), effect=["effect", p[3]])
        elif cmd == "-curestatus":
            if p[3] in CURE_MSG:
                add(CURE_MSG[p[3]], p[2], "status", src=src, mon=name(p[2]))
            else:
                add("{mon} is no longer {effect}", p[2], "status", src=src, mon=name(p[2]), effect=["effect", p[3]])
        elif cmd == "-weather":
            if "upkeep" in t:
                continue
            w = p[2]
            if w == "none":
                add("the weather cleared", t.get("of", ""), "field")
            elif w in WEATHER_MSG:
                add(WEATHER_MSG[w], t.get("of", ""), "field", src=src)
            else:
                add("{effect} started", t.get("of", ""), "field", src=src, effect=["effect", w])
        elif cmd in ("-fieldstart", "-fieldend"):
            add("{effect} started" if cmd == "-fieldstart" else "{effect} ended", t.get("of", ""), "field", src=src,
                effect=["effect", _clean(p[2])])
        elif cmd in ("-sidestart", "-sideend"):
            who = players.get(p[2][:2], p[2][:2])
            add("{effect} up on {who}'s side" if cmd == "-sidestart" else "{effect} ended on {who}'s side", p[2][:2] + "a: x", "field",
                effect=["effect", _clean(p[3])], who=who)
        elif cmd == "-singleturn":
            continue
        elif cmd == "-activate":
            what = _clean(p[3]) if len(p) > 3 else ""
            if what == "Protect":
                add("  {mon} protected itself", p[2], "note", mon=name(p[2]))
            elif what and len(p) > 4 and p[4] and not p[4].startswith("["):
                add("  {effect} ({mon}): {detail}", p[2], "note", effect=["effect", what], mon=name(p[2]), detail=["effect", _clean(p[4])])
            elif what:
                add("  {effect} ({mon})", p[2], "note", effect=["effect", what], mon=name(p[2]))
        elif cmd in ("-start", "-end"):
            what = _clean(p[3]) if len(p) > 3 else ""
            if what.startswith("perish"):
                add("{mon}: Perish count {n}", p[2], "note", mon=name(p[2]), n=what[6:])
            else:
                add("{mon}: {effect} started" if cmd == "-start" else "{mon}: {effect} ended", p[2], "note", src=src, mon=name(p[2]),
                    effect=["effect", what])
        elif cmd == "-ability":
            add("{mon}'s {ability}", p[2], "ability", src=src, mon=name(p[2]), ability=["ability", p[3]])
        elif cmd in ("-item", "-enditem"):
            if "weaken" in t:
                add("  {item} weakened the hit", p[2], "note", item=["item", p[3]])
                continue
            msg = "{mon} has {item}" if cmd == "-item" else ("{mon} ate its {item}" if "eat" in t else "{mon} used up its {item}")
            add(msg, p[2], "item", src=src, mon=name(p[2]), item=["item", p[3]])
        elif cmd == "-mega":

            add("{mon} Mega Evolved ({item})", p[2], "mega", mon=name(p[2], base=True), item=["item", p[4] if len(p) > 4 else ""])
        elif cmd == "-formechange":
            add("{mon} changed form: {form}", p[2], "note", mon=name(p[2]), form=["species", p[3]])
        elif cmd == "cant":
            why = _clean(p[3]) if len(p) > 3 else ""
            if why in CANT_MSG:
                add(CANT_MSG[why], p[2], "note", mon=name(p[2]))
            elif why:
                add("{mon} can't move ({effect})", p[2], "note", mon=name(p[2]), effect=["effect", why])
            else:
                add("{mon} can't move", p[2], "note", mon=name(p[2]))
        elif cmd == "-prepare":
            add("{mon} is charging {move}", p[2], "note", mon=name(p[2]), move=["move", p[3]])
        elif cmd == "-mustrecharge":
            add("{mon} must recharge", p[2], "note", mon=name(p[2]))
        elif cmd == "-hitcount":
            add("  hit {n} times", p[2], "note", n=p[3])
        elif cmd == "-transform":
            add("{mon} transformed into {target}", p[2], "note", mon=name(p[2]), target=name(p[3]))
        elif cmd == "-fieldactivate":
            add("{effect} affects the field", "", "field", effect=["effect", _clean(p[2])])
        elif cmd == "-copyboost":
            add("{mon} copied {target}'s stat changes", p[2], "boost", src=src, mon=name(p[2]), target=name(p[3]))
        elif cmd == "-clearboost":
            add("{mon}'s stat changes were cleared", p[2], "boost", mon=name(p[2]))
        elif cmd == "-setboost" and len(p) > 4:
            add("{mon} {stat} set to {n}", p[2], "boost", mon=name(p[2]), stat=["stat", p[3]],
                n=f"+{p[4]}" if p[4].lstrip("-").isdigit() and int(p[4]) > 0 else p[4])
        elif cmd == "-clearallboost":
            add("all stat changes were cleared", "", "boost")
        elif cmd == "-block":
            add("  {mon} blocked it ({effect})", p[2], "note", mon=name(p[2]), effect=["effect", _clean(p[3]) if len(p) > 3 else ""])
        elif cmd == "-message":
            add(p[2], "", "message", raw=True)
        elif cmd == "win":
            result = p[2]
        elif cmd == "tie":
            result = "tie"
        elif cmd.startswith("-"):
            add(f"{cmd[1:]}: " + " ".join(_clean(x) for x in p[2:] if x and not x.startswith("[")), p[2] if len(p) > 2 else "", "other",
                raw=True)

        turns[-1]["hp"] = {k: round(v) for k, v in hp.items()}


        turns[-1]["names"] = {k: forms.get(k) or species_of[k] for k in species_of}
    return {"players": players, "turns": turns, "result": result, "rating": rating, "preview": preview}


def templates() -> list[str]:


    import re
    from pathlib import Path
    src = Path(__file__).read_text(encoding="utf8")
    body = src[src.index("def narrate("):src.index("def templates(")]
    out = re.findall(r'(?<![\w.])add\(\s*"((?:[^"\\]|\\.)*)"', body)
    out += re.findall(r'(?:if [^"]+ else |else )"((?:[^"\\]|\\.)*\{[a-z_]+\}(?:[^"\\]|\\.)*)"', body)
    out += [m for d in (STATUS_MSG, CURE_MSG, CANT_MSG, WEATHER_MSG) for m in d.values()]
    out += list(MOVE_FLAGS.values()) + list(STATS.values()) + [" ({hp}%)", " [{flags}]", " ({source})"]
    out += ["{who} sent out {mon}", "{who} had dragged in {mon}", "{who} revealed {mon}", "{mon} has {item}",
            "{mon} ate its {item}", "{mon} used up its {item}"]
    return sorted({x.encode().decode("unicode_escape") if "\\" in x else x for x in out})


def _game_name(kind: str, raw: str, lang: str) -> str:


    if lang == "en" or not raw:
        return STATS.get(raw, raw) if kind == "stat" else raw
    from vgc_trainer import i18n
    if kind == "stat":
        return i18n.t(STATS.get(raw, raw), lang)
    if kind == "effect":

        if i18n.has(raw):
            return i18n.t(raw, lang)
        for k in ("move", "ability", "item"):
            ja = i18n.name_ja(k, raw)
            if ja:
                return ja
        return raw
    return i18n.name_ja(kind, raw) or raw


def render_event(ev: dict, lang: str | None = None) -> str:



    if "msg" not in ev:
        return ev.get("text", "")
    if lang is None:
        from vgc_trainer.i18n import language
        lang = language()
    if lang == "en":
        fill = lambda m, **kw: m.format(**kw)
    else:
        from vgc_trainer.i18n import t
        fill = lambda m, **kw: t(m, lang, **kw)
    slots = {k: _game_name(v[0], v[1], lang) if isinstance(v, list) else v for k, v in (ev.get("slots") or {}).items()}
    out = fill(ev["msg"], **slots)
    if ev.get("hp") is not None:
        out += fill(" ({hp}%)", hp=ev["hp"])
    if ev.get("flags"):
        out += fill(" [{flags}]", flags=(", " if lang == "en" else "、").join(fill(f) for f in ev["flags"]))
    if ev.get("src"):
        out += fill(" ({source})", source=_game_name("effect", ev["src"], lang))
    return out


def tagged_html(text: str, name=None) -> str:


    import html
    import re
    out = html.escape(text)
    show = name or (lambda n: n)
    return re.sub(r"⟦(us|them|p1|p2)\|(.*?)⟧",
                  lambda m: f'<span class="mon {m.group(1)}">{html.escape(show(html.unescape(m.group(2))))}</span>', out)


def plain(text: str) -> str:

    import re
    return re.sub(r"⟦(?:us|them|p1|p2)\|(.*?)⟧", r"\1", text)

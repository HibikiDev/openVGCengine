




from __future__ import annotations

from vgc_trainer import i18n
from vgc_trainer.showdown.requests import PASS_ACTION, SWITCH_BASE, TARGET_ALLY, TARGET_FOE_A, TARGET_FOE_B, describe_action


def mon(name: str | None, lang: str | None = None) -> str:

    return i18n.dex("species", name, lang) if name else (name or "")


_TAGGED_LABEL = __import__("re").compile(r"^(?P<move>.+?)(?: (?:->|→) (?P<target>.+?))?(?P<tag> \+(?:mega|Z-Move|Dynamax|Tera))?$")


def localize(label: str, lang: str | None = None) -> str:



    lang = lang or i18n.language()
    if not isinstance(label, str) or lang == "en":
        return label
    t = lambda text, **k: i18n.t(text, lang, **k)
    plain = lambda n: n if "⟦" in n else mon(n, lang)
    if label == "pass":
        return t("pass")
    if label.startswith("switch "):
        return t("switch {mon}", mon=plain(label[7:]))
    m = _TAGGED_LABEL.match(label)
    if not m:
        return label
    s = i18n.dex("move", m.group("move"), lang)
    if m.group("target"):
        s += f" -> {plain(m.group('target'))}"
    return s + (f" {t(m.group('tag').strip())}" if m.group("tag") else "")


def line_label(label: str, lang: str | None = None) -> str:


    lang = lang or i18n.language()
    if not isinstance(label, str) or lang == "en":
        return label
    out = []
    for part in label.split(" · "):
        who, sep, act = part.partition(": ")
        out.append(f"{mon(who, lang)}: {localize(act, lang)}" if sep and not who.startswith(("switch ", "pass")) else localize(part, lang))
    return " · ".join(out)


def roll_word(text: str, lang: str | None = None) -> str:


    lang = lang or i18n.language()
    if not isinstance(text, str) or lang == "en":
        return text
    word, sep, what = text.partition(" (")
    out = i18n.t(word, lang)
    if sep:
        what = what.rstrip(")")
        stat, _, n = what.partition(" ")
        out += f"（{i18n.t(stat, lang)} {n}）" if n else f"（{i18n.t(what, lang)}）"
    return out


def who_label(text: str, lang: str | None = None) -> str:

    lang = lang or i18n.language()
    if not isinstance(text, str) or lang == "en":
        return text
    return " → ".join(mon(x, lang) for x in text.split(" → "))


def spread_text(text: str, lang: str | None = None) -> str:

    lang = lang or i18n.language()
    if not isinstance(text, str) or lang == "en":
        return text
    nat, sep, rest = text.partition(" ")
    return f"{i18n.dex('nature', nat, lang)}{sep}{rest}"


_READING = __import__("re").compile(r"^(?P<mon>.+?) (?:on (?P<nat>\w+) (?P<evs>[\d/]+) \(HP/Atk/Def/SpA/SpD/Spe\)|holding (?P<item>.+))$")


def reading_label(text: str, lang: str | None = None) -> str:


    lang = lang or i18n.language()
    if not isinstance(text, str) or lang == "en":
        return text
    m = _READING.match(text)
    if not m:
        return text
    if m.group("item"):
        return i18n.t("{mon} holding {item}", lang, mon=mon(m.group("mon"), lang), item=i18n.dex("item", m.group("item"), lang))
    return i18n.t("{mon} as {nature} {spread} (HP/Atk/Def/SpA/SpD/Spe)", lang, mon=mon(m.group("mon"), lang),
                  nature=i18n.dex("nature", m.group("nat"), lang), spread=m.group("evs"))


def describe(action: int, moves: list[str], foe: list[str], ally: str, bring: list[str], mega: bool = False,
             tag: str = "+mega") -> str:

    if i18n.language() == "en":
        return describe_action(action, moves, foe, ally, bring) + (f" {tag}" if mega else "")
    t = i18n.t
    if action == PASS_ACTION:
        return t("pass")
    if action >= SWITCH_BASE:
        k = action - SWITCH_BASE
        return t("switch {mon}", mon=mon(bring[k]) if k < len(bring) else f"#{k + 1}")
    m, tg = divmod(action, 4)
    s = i18n.dex("move", moves[m]) if m < len(moves) and moves[m] else t("move {n}", n=m + 1)
    if tg in (TARGET_FOE_A, TARGET_FOE_B):
        s += f" -> {mon(foe[tg]) if tg < len(foe) and foe[tg] else t(('foe A', 'foe B')[tg])}"
    elif tg == TARGET_ALLY:
        s += f" -> {mon(ally) or t('ally')}"
    return s + (f" {t(tag)}" if mega else "")


_BOOST = __import__("re").compile(r"^([+-]\d+) (\w+)$")


def luck_event(text: str, lang: str | None = None) -> str:


    lang = lang or i18n.language()
    if not isinstance(text, str) or lang == "en":
        return text
    if i18n.has(text):
        return i18n.t(text, lang)
    own = text.startswith("own ")
    parts = []
    for p in (text[4:] if own else text).split(", "):
        m = _BOOST.match(p)
        parts.append(f"{i18n.t(m.group(2), lang)} {m.group(1)}" if m else i18n.t(p, lang))
    out = "、".join(parts)
    return i18n.t("own {effects}", lang, effects=out) if own else out


_NOTE = __import__("re").compile(r"^T(?P<turn>\d+) (?P<mon>.+?): you played (?P<played>.+) \((?P<p>\d+%)\); model preferred (?P<top>.+) \((?P<q>\d+%)\)$")


def note_label(text: str, lang: str | None = None) -> str:


    lang = lang or i18n.language()
    if not isinstance(text, str) or lang == "en":
        return text
    m = _NOTE.match(text)
    if not m:
        return text
    return i18n.t("T{turn} {mon}: you played {played} ({p}); model preferred {top} ({q})", lang, turn=m.group("turn"),
                  mon=mon(m.group("mon"), lang), played=localize(m.group("played"), lang), p=m.group("p"),
                  top=localize(m.group("top"), lang), q=m.group("q"))


_POS = __import__("re").compile(r"^([AB])'s (.+)$")


def crawl_pos(text: str, lang: str | None = None) -> str:

    lang = lang or i18n.language()
    if not isinstance(text, str) or lang == "en":
        return text
    m = _POS.match(text)
    return i18n.t("{side}'s {mon}", lang, side=m.group(1), mon=mon(m.group(2), lang)) if m else text


_P = r"([AB]'s .+?)"
_SET = r"( \(set\))?"
_CRAWL = [(__import__("re").compile(rx), key) for rx, key in (
    (r"^([AB]) chose (.+)$", "chose"),
    (r"^" + _P + r" couldn't move$", "{who} couldn't move"),
    (r"^" + _P + r"'s (.+?) missed " + _P + _SET + "$", "missed"),
    (r"^critical hit: " + _P + r"'s (.+?) on " + _P + _SET + "$", "crit"),
    (r"^" + _P + r"'s (.+?): its (\d+)% (.+?) triggered on " + _P + _SET + "$", "triggered"),
    (r"^" + _P + r" is fully paralyzed" + _SET + "$", "{who} is fully paralyzed"),
    (r"^" + _P + r" hit itself in its confusion" + _SET + "$", "{who} hit itself in its confusion"),
    (r"^" + _P + r" thawed out" + _SET + "$", "{who} thawed out"),
    (r"^" + _P + r"'s Quick Claw / Quick Draw let it move first" + _SET + "$", "{who}'s Quick Claw / Quick Draw let it move first"),
    (r"^" + _P + r" used (.+?) -> " + _P + "$", "{who} used {move} -> {target}"),
    (r"^" + _P + r" used (.+)$", "{who} used {move}"),
    (r"^([AB]) sent in " + _P + r" \(for " + _P + r"\)$", "{side} sent in {who} (for {target})"),
    (r"^([AB]) sent in " + _P + "$", "{side} sent in {who}"),
    (r"^" + _P + r" fainted$", "{who} fainted"),
    (r"^([AB])'s (.+?) became (.+)$", "{side}'s {mon} became {new}"),
    (r"^" + _P + r" ([+-]\d+)% -> (\d+)%$", "{who} {change}% -> {now}%"),
    (r"^" + _P + r" cured of (\w+)$", "{who} cured of {status}"),
    (r"^" + _P + r" (brn|frz|par|psn|tox|slp)$", "{who}: {status}"),
    (r"^" + _P + r" (Atk|Def|SpA|SpD|Spe|acc|eva) ([+-]\d+) \(now ([+-]\d+)\)$", "{who} {stat} {change} (now {now})"),
    (r"^(weather|terrain): (.+) -> (.+)$", "{what}: {old} -> {new}"),
    (r"^Trick Room (up|ended)$", "trick room"),
    (r"^([AB])'s (.+) (up|ended)$", "cond"),
    (r"^the game is over: a tie$", "the game is over: a tie"),
    (r"^the game is over: ([AB]) won$", "the game is over: {side} won"),
)]


def crawl_line(text: str, lang: str | None = None) -> str:


    lang = lang or i18n.language()
    if not isinstance(text, str) or lang == "en":
        return text
    t = lambda s, **k: i18n.t(s, lang, **k)
    P = lambda s: crawl_pos(s, lang)
    mv = lambda s: i18n.dex("move", s, lang)
    for rx, key in _CRAWL:
        m = rx.match(text)
        if not m:
            continue
        g = m.groups()
        st = t(" (set)") if g and g[-1] == " (set)" else ""
        if key == "chose":
            return t("{side} chose {choices}", side=g[0], choices=t("nothing") if g[1] == "nothing" else line_label(g[1], lang))
        if key == "missed":
            return t("{who}'s {move} missed {target}", who=P(g[0]), move=mv(g[1]), target=P(g[2])) + st
        if key == "crit":
            return t("critical hit: {who}'s {move} on {target}", who=P(g[0]), move=mv(g[1]), target=P(g[2])) + st
        if key == "triggered":
            return t("{who}'s {move}: its {pct}% {effect} triggered on {target}", who=P(g[0]), move=mv(g[1]), pct=g[2],
                     effect=t(g[3]), target=P(g[4])) + st
        if key == "trick room":
            return t("Trick Room up") if g[0] == "up" else t("Trick Room ended")
        if key == "cond":
            return (t("{side}'s {cond} up", side=g[0], cond=t(g[1])) if g[2] == "up"
                    else t("{side}'s {cond} ended", side=g[0], cond=t(g[1])))
        if key.startswith("{who}") and len(g) >= 1 and key.count("{") == 1:
            return t(key, who=P(g[0])) + st
        slots = {"{who} used {move} -> {target}": lambda: dict(who=P(g[0]), move=mv(g[1]), target=P(g[2])),
                 "{who} used {move}": lambda: dict(who=P(g[0]), move=mv(g[1])),
                 "{side} sent in {who} (for {target})": lambda: dict(side=g[0], who=P(g[1]), target=P(g[2])),
                 "{side} sent in {who}": lambda: dict(side=g[0], who=P(g[1])),
                 "{side}'s {mon} became {new}": lambda: dict(side=g[0], mon=mon(g[1], lang), new=mon(g[2], lang)),
                 "{who} {change}% -> {now}%": lambda: dict(who=P(g[0]), change=g[1], now=g[2]),
                 "{who} cured of {status}": lambda: dict(who=P(g[0]), status=t(g[1])),
                 "{who}: {status}": lambda: dict(who=P(g[0]), status=t(g[1])),
                 "{who} {stat} {change} (now {now})": lambda: dict(who=P(g[0]), stat=t(g[1]), change=g[2], now=g[3]),
                 "{what}: {old} -> {new}": lambda: dict(what=t(g[0]), old=t(g[1]), new=t(g[2])),
                 "the game is over: {side} won": lambda: dict(side=g[0]),
                 "the game is over: a tie": lambda: {}}
        return t(key, **slots[key]())
    return text


def dice_word(text: str, lang: str | None = None) -> str:

    lang = lang or i18n.language()
    if not isinstance(text, str) or lang == "en":
        return text
    m = __import__("re").match(r"^(\d+)% roll$", text)
    return i18n.t("{n}% roll", lang, n=m.group(1)) if m else i18n.t(text, lang)

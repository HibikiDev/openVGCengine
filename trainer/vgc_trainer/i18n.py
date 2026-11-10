












from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMES = ROOT / "data/i18n/ja/names.json"
CATALOG = ROOT / "data/i18n/ja/ui.json"
TERMS = ROOT / "data/i18n/ja/terms.json"
SETTINGS = ROOT / "trainer/runs/app_settings.json"

LANGUAGES = {"en": "English", "ja": "日本語"}
PSEUDO = "qps"




def _os_language() -> str:

    try:
        import ctypes
        if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x11:
            return "ja"
    except (AttributeError, OSError):
        pass
    import locale
    loc = (locale.getlocale()[0] or "").lower()
    return "ja" if loc.startswith(("ja", "japanese")) else "en"


def language() -> str:

    try:
        lang = json.loads(SETTINGS.read_text(encoding="utf8")).get("language")
        if lang in LANGUAGES or lang == PSEUDO:
            return lang
    except (OSError, ValueError):
        pass
    lang = _os_language()
    set_language(lang)
    return lang


def set_language(lang: str) -> None:
    if lang not in LANGUAGES and lang != PSEUDO:
        raise ValueError(f"unknown language {lang!r}")
    try:
        cur = json.loads(SETTINGS.read_text(encoding="utf8"))
    except (OSError, ValueError):
        cur = {}
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps({**cur, "language": lang}, ensure_ascii=False, indent=1), encoding="utf8")




_catalog_cache: dict = {}


def _load(path: Path) -> dict:

    try:
        st = path.stat().st_mtime_ns
    except OSError:
        return {}
    hit = _catalog_cache.get(path)
    if hit is None or hit[0] != st:
        hit = (st, json.loads(path.read_text(encoding="utf8")))
        _catalog_cache[path] = hit
    return hit[1]


_TOKEN = re.compile(r"\{t:([a-z0-9_]+)\}")
_SLOT = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def term(key: str, lang: str | None = None) -> str:

    e = _load(TERMS).get(key) or {}
    return e.get("ja" if (lang or language()) != "en" else "en") or e.get("en") or key


def t(text: str, lang: str | None = None, **slots) -> str:


    lang = lang or language()
    out = text
    if lang != "en":
        e = _load(CATALOG).get(text)
        if e and e.get("ja"):
            out = _TOKEN.sub(lambda m: term(m.group(1), "ja"), e["ja"])
        if lang == PSEUDO:
            out = f"［{text}］"
    if slots:
        out = _SLOT.sub(lambda m: str(slots[m.group(1)]) if m.group(1) in slots else m.group(0), out)
    return out


def has(text: str) -> bool:

    e = _load(CATALOG).get(text)
    return bool(e and e.get("ja"))


def dex(kind: str, ident: str, lang: str | None = None) -> str:

    if (lang or language()) == "en" or not ident:
        return ident
    return name_ja(kind, ident) or ident
STATS = ("hp", "atk", "def", "spa", "spd", "spe")
_LETTERS = {"H": "hp", "A": "atk", "B": "def", "C": "spa", "D": "spd", "S": "spe"}

NATURE_MOD = {
    "lonely": ("atk", "def"), "brave": ("atk", "spe"), "adamant": ("atk", "spa"), "naughty": ("atk", "spd"),
    "bold": ("def", "atk"), "relaxed": ("def", "spe"), "impish": ("def", "spa"), "lax": ("def", "spd"),
    "timid": ("spe", "atk"), "hasty": ("spe", "def"), "jolly": ("spe", "spa"), "naive": ("spe", "spd"),
    "modest": ("spa", "atk"), "mild": ("spa", "def"), "quiet": ("spa", "spe"), "rash": ("spa", "spd"),
    "calm": ("spd", "atk"), "gentle": ("spd", "def"), "sassy": ("spd", "spe"), "careful": ("spd", "spa"),
}
_KANA = re.compile(r"[぀-ヿ]")
_KINDS = {"species": "species", "move": "moves", "item": "items", "ability": "abilities", "nature": "natures", "type": "types"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).strip()
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
    return re.sub(r"\s+", "", s)


def _to_id(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower())


@lru_cache(maxsize=1)
def _table() -> dict:
    return json.loads(NAMES.read_text(encoding="utf8"))


@lru_cache(maxsize=None)
def _reverse(kind: str) -> dict[str, str]:

    out: dict[str, str] = {}
    for i, n in sorted(_table()[_KINDS[kind]].items(), key=lambda kv: (len(kv[0]), kv[0])):
        out.setdefault(_norm(n), i)
    return out


def name_ja(kind: str, ident: str) -> str | None:

    return _table()[_KINDS[kind]].get(_to_id(ident))


def id_from_ja(kind: str, text: str) -> str | None:
    return _reverse(kind).get(_norm(text))


_SHOWDOWN_LABELS = re.compile(r"^\s*(Ability|EVs|IVs|Level|Tera Type|Gigantamax):", re.M)


def is_japanese(text: str) -> bool:


    return bool(_KANA.search(text)) and not _SHOWDOWN_LABELS.search(text)


def _english(kind: str, ident: str) -> str:
    from .showdown.belief import name
    return name({"species": "species", "move": "moves", "item": "items", "ability": "abilities", "nature": "natures"}[kind], ident)


def _need(kind: str, text: str, where: str) -> str:
    i = id_from_ja(kind, text)
    if i is None:
        raise ValueError(f"{where}: 「{text.strip()}」 isn't a {kind} name we know")
    return i


def stats_of(species_id: str, points: dict[str, int], nature: str | None) -> dict[str, int] | None:


    from .showdown.belief import dex
    bs = (dex()["species"].get("champions", {}).get(species_id) or {}).get("bs")
    if not bs:
        return None
    up, down = NATURE_MOD.get(_to_id(nature or ""), (None, None))
    out = {}
    for k in STATS:
        v = (2 * bs[k] + 31) // 2 + points.get(k, 0)
        out[k] = v + 60 if k == "hp" else int((v + 5) * (1.1 if k == up else 0.9 if k == down else 1.0))
    return out


_STATLINE = re.compile(r"^\d+(?:\(\d+\))?(?:-(?:\d+(?:\(\d+\))?|x|X|-))+$")


def _points_row(text: str) -> dict[str, int]:

    t = _norm(text)
    if re.fullmatch(r"(\d+-){5}\d+", t):
        return dict(zip(STATS, map(int, t.split("-"))))
    pairs = re.findall(r"([HABCDS])(\d+)", t)
    if not pairs:
        raise ValueError(f"「{text}」 isn't a stat point row (11-30-11-0-10-4 or H11 A30 ...)")
    return {_LETTERS[a]: int(n) for a, n in pairs}


def parse_ja(text: str) -> list[dict]:

    sets = []
    for n, block in enumerate([b for b in re.split(r"\n\s*\n", text.replace("\r", "")) if b.strip()], 1):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        where = f"mon {n}"
        head = unicodedata.normalize("NFKC", lines[0])
        sp_txt, _, it_txt = head.partition("@")
        sp = _need("species", sp_txt, where)
        s: dict = {"species": _english("species", sp), "item": _english("item", _need("item", it_txt, where)) if it_txt.strip() else "",
                   "ability": "", "moves": [], "nature": "", "evs": {}}
        s["name"] = s["species"]
        printed = None
        for ln in lines[1:]:
            t = unicodedata.normalize("NFKC", ln)
            key, sep, val = t.partition(":")
            key = key.strip()
            if sep and key in ("テラスタイプ", "テラス", "テラスタル"):
                s["teraType"] = _english_type(_need("type", val, where))
            elif sep and key == "特性":
                s["ability"] = _english("ability", _need("ability", val, where))
            elif sep and key in ("能力補正", "性格"):
                s["nature"] = _english("nature", _need("nature", re.sub(r"な?性格$", "", val.strip()), where))
            elif sep and key == "持ち物":
                s["item"] = _english("item", _need("item", val, where))
            elif sep and key in ("努力値", "能力ポイント", "ポイント"):
                s["evs"] = _points_row(val)
            elif sep and key == "実数値" or _STATLINE.match(t.replace(" ", "")):
                parts = (val if sep else t).replace(" ", "").split("-")
                if len(parts) != 6:
                    raise ValueError(f"{where}: the stats line 「{ln}」 needs six values (H-A-B-C-D-S)")
                printed = {}
                for k, p in zip(STATS, parts):
                    m = re.fullmatch(r"(\d+)(?:\((\d+)\))?", p)
                    if m:
                        printed[k] = int(m.group(1))
                        if m.group(2):
                            s["evs"][k] = int(m.group(2))
            elif t.startswith(("-", "・")):
                s["moves"].append(_english("move", _need("move", t.lstrip("-・ "), where)))
            elif "/" in t or id_from_ja("move", t):
                s["moves"] += [_english("move", _need("move", m, where)) for m in t.split("/") if m.strip()]
            else:
                raise ValueError(f"{where}: can't read the line 「{ln}」")
        s["evs"] = {k: v for k, v in s["evs"].items() if v}
        if sum(s["evs"].values()) > 66 or any(v > 32 for v in s["evs"].values()):
            raise ValueError(f"{where}: stat points over the limit (32 a stat, 66 in all): {s['evs']}")
        if printed:
            want = stats_of(sp, s["evs"], s["nature"])
            bad = [k for k in STATS if want and k in printed and printed[k] != want[k]]
            if bad:
                raise ValueError(f"{where}: the stats line doesn't match the points and nature ({', '.join(f'{k} {printed[k]} vs {want[k]}' for k in bad)})"
                                 " - a misread line, or another level / format")
        sets.append(s)
    return sets


def _english_type(type_id: str) -> str:
    return type_id[:1].upper() + type_id[1:]


def to_ja_text(sets: list[dict]) -> str:

    blocks = []
    for st in sets:
        sp = _to_id(st["species"])
        ja = lambda kind, v: (name_ja(kind, v) or v) if v else ""
        head = ja("species", st["species"]) + (f" @ {ja('item', st['item'])}" if st.get("item") else "")
        lines = [head]
        if st.get("teraType"):
            lines.append(f"テラスタイプ: {ja('type', st['teraType'])}")
        if st.get("ability"):
            lines.append(f"特性: {ja('ability', st['ability'])}")
        if st.get("nature"):
            lines.append(f"能力補正: {ja('nature', st['nature'])}")
        pts = {k: int(v) for k, v in (st.get("evs") or {}).items() if v}
        stats = stats_of(sp, pts, st.get("nature"))
        if stats:
            lines.append("-".join(f"{stats[k]}({pts[k]})" if pts.get(k) else str(stats[k]) for k in STATS))
        if st.get("moves"):
            lines.append(" / ".join(ja("move", m) for m in st["moves"]))
        blocks.append("\n".join(lines))

    return re.sub(r"[Ａ-Ｚａ-ｚ０-９]", lambda m: chr(ord(m.group()) - 0xFEE0), "\n\n".join(blocks)) + "\n"

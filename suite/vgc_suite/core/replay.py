






from __future__ import annotations

from vgc_trainer import i18n

import html
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from vgc_trainer.showdown.teams import unpack
from vgc_trainer.showdown.tracker import to_id

USER_AGENT = "Mozilla/5.0 (openVGCengine suite)"


@dataclass
class ReplayLog:
    lines: list[str]
    source: str
    fmt: str = ""
    players: dict[str, str] = field(default_factory=dict)
    sheets: dict[str, list[dict] | None] = field(default_factory=dict)
    species: dict[str, list[str]] = field(default_factory=dict)

    @property
    def ots(self) -> bool:
        return all(self.sheets.get(s) for s in ("p1", "p2"))

    def side_of(self, name: str) -> str | None:
        return next((s for s, n in self.players.items() if to_id(n) == to_id(name)), None)


def _fetch(url: str) -> str:
    if "replay.pokemonshowdown.com" in url and not url.endswith((".log", ".json")):
        url = url.split("?")[0].rstrip("/") + ".log"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(i18n.t("That replay isn't on replay.pokemonshowdown.com. A battle's link works once its replay is uploaded (Upload and Share in Showdown); a private replay needs its whole link, password part included.")) from None
        raise


def _from_html(text: str) -> str:

    m = re.search(r'<script[^>]*class="battle-log-data"[^>]*>(.*?)</script>', text, re.S)
    if not m:
        raise ValueError(i18n.t("no battle log found in this HTML (expected a Showdown replay page)"))
    return html.unescape(m.group(1))


def load_replay(src: str) -> ReplayLog:

    if src.startswith(("http://", "https://")):
        text, source = _fetch(src), src
    elif "\n" not in src and Path(src).exists():
        text, source = Path(src).read_text(encoding="utf8"), src
    else:
        text, source = src, "text"
    if "battle-log-data" in text[:200000] and "<script" in text:
        text = _from_html(text)

    log = ReplayLog(lines=[ln for ln in text.replace("\r", "").replace("\\/", "/").split("\n")], source=source)
    for ln in log.lines:
        p = ln.split("|")
        if len(p) < 3:
            continue
        if p[1] == "player" and len(p) > 3 and p[3]:
            log.players[p[2]] = p[3]
        elif p[1] == "showteam" and len(p) > 3:
            log.sheets[p[2]] = unpack("|".join(p[3:]))
        elif p[1] == "poke" and len(p) > 3:
            log.species.setdefault(p[2], []).append(p[3].split(",")[0])
        elif p[1] == "tier" and not log.fmt:
            log.fmt = to_id(p[2])
    for s in ("p1", "p2"):
        log.sheets.setdefault(s, None)
    return log

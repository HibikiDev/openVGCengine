











from __future__ import annotations

from vgc_trainer import i18n

import copy
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import vgc_engine as ve

from vgc_trainer.search import STATS, guessed_spreads
from vgc_trainer.showdown.live_search import _corpus_for, _outcome_seq, usage_corpus
from vgc_trainer.showdown.requests import (KIND_MEGA, PASS_ACTION, SWITCH_BASE, TARGET_ALLY, TARGET_FOE_A, TARGET_FOE_B, TARGET_SELF,
                                           RequestMasks)
from vgc_trainer.showdown.sheets import CLOSED_SHEET_FORMATS, base_format, playable_sheet
from vgc_trainer.showdown.tracker import FORMATS, Tracker, move_type, to_id

from .replay import ReplayLog


@dataclass
class Decision:

    turn: int
    side: str
    obs: tuple
    masks: RequestMasks
    bring: list[int]
    names: list[str]
    request: dict
    played: list[tuple[int, bool] | None]
    played_text: list[str | None] = field(default_factory=lambda: [None, None])
    active: list[str | None] = field(default_factory=lambda: [None, None])
    foe_active: list[str | None] = field(default_factory=lambda: [None, None])
    ctx: dict = field(default_factory=dict)
    moves: list[list[str]] = field(default_factory=lambda: [[], []])
    display: list[str] = field(default_factory=list)
    shown: int = 4
    fill: dict | None = None
    guessed: bool = False
    tracker: Tracker | None = None
    sheets: dict | None = None


def with_spreads(sheet: list[dict], spreads: list[tuple[str, tuple[int, ...]]]) -> list[dict]:

    out = []
    for s, (nature, evs) in zip(sheet, spreads):
        s = dict(s)
        s["nature"] = s.get("nature") or nature
        if not any((s.get("evs") or {}).values()):
            s["evs"] = dict(zip(STATS, evs))
        out.append(s)
    return out


def species_sheet(species: list[str]) -> list[dict]:

    return [{"name": sp, "species": sp, "item": "", "ability": "", "moves": []} for sp in species]


def _spaced(name: str) -> str:

    import re
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def side_bring(log: ReplayLog, side: str, sheet: list[dict]) -> list[int]:

    names = [to_id(s.get("name") or s["species"]) for s in sheet]
    species = [to_id(s["species"]) for s in sheet]
    out: list[int] = []
    for ln in log.lines:
        p = ln.split("|")
        if len(p) > 3 and p[1] in ("switch", "drag", "replace") and p[2].startswith(side):
            nick, sp = to_id(p[2].split(": ", 1)[1]), to_id(p[3].split(",")[0])
            k = next((i for i, n in enumerate(names) if n == nick), None)
            if k is None:
                k = next((i for i, s in enumerate(species) if sp.startswith(s) or s.startswith(sp)), None)
            if k is not None and k not in out:
                out.append(k)
    return out[:4]


HUMAN_PREVIEW = None
_PREVIEW: dict = {}


def _human_preview():


    if "net" not in _PREVIEW:
        net = None
        try:
            import torch
            from vgc_trainer.model import load_weights
            from vgc_trainer.preview import PreviewNet
            from .bundle import path as pinned
            sd = torch.load(HUMAN_PREVIEW or pinned("preview_head"), map_location="cpu", weights_only=True)
            net = PreviewNet().eval()
            load_weights(net, sd["preview"])
        except (OSError, KeyError, RuntimeError):
            net = None
        _PREVIEW["net"] = net
    return _PREVIEW["net"]


def fill_bring(side_sheet: list[dict], foe_sheet: list[dict], shown: list[int], fmt: str | None = None) -> tuple[list[int], dict | None]:





    n = len(side_sheet)
    if len(shown) >= 4 or n <= len(shown):
        return list(shown[:4]), None
    from vgc_trainer.preview import N_OUTCOMES, outcome_probs
    from vgc_trainer.showdown.agent import sheet_tokens
    name = lambda i: side_sheet[i].get("name") or side_sheet[i]["species"]
    seq = _outcome_seq()
    leads = set(shown[:2])
    ok = np.array([set(shown) <= set(int(x) for x in seq[o]) and max(seq[o]) < n
                   and (len(leads) < 2 or set(int(x) for x in seq[o][:2]) == leads) for o in range(N_OUTCOMES)])
    net = _human_preview()
    x = None
    if net is not None and ok.any() and len(foe_sheet) > 0:
        try:
            x = np.concatenate([sheet_tokens(side_sheet, fmt), sheet_tokens(foe_sheet, fmt, as_opponent=fmt is not None)])[None]
        except ValueError:
            x = None
    if x is not None:
        import torch
        with torch.no_grad():
            lead, back, _ = net(torch.from_numpy(x))
        if n < 6:
            lead[:, n:] = float("-inf")
            back[:, n:] = float("-inf")
        p = outcome_probs(lead.float(), back.float())[0].numpy()
    else:
        p = np.ones(N_OUTCOMES)
    p = np.where(ok, p, 0.0)
    if p.sum() <= 0:
        rest = [i for i in range(n) if i not in shown]
        return list(shown) + rest[:4 - len(shown)], {"shown": len(shown), "assumed": [name(i) for i in rest[:4 - len(shown)]],
                                                     "p": None, "alts": []}
    fills: dict[tuple[int, ...], float] = {}
    for o in np.flatnonzero(p):
        key = tuple(sorted(int(i) for i in seq[o] if int(i) not in shown))
        fills[key] = fills.get(key, 0.0) + float(p[o])
    total = sum(fills.values())
    ranked = sorted(fills.items(), key=lambda kv: -kv[1])
    best = list(ranked[0][0])
    return list(shown) + best, {"shown": len(shown), "assumed": [name(i) for i in best], "p": round(ranked[0][1] / total, 3),
                                "alts": [{"assumed": [name(i) for i in k], "p": round(v / total, 3)} for k, v in ranked[1:3]]}


def _condition(m, maxhp: int) -> str:
    if m.fainted:
        return "0 fnt"
    cur = max(1, round(m.hp * maxhp))
    return f"{cur}/{maxhp}" + (f" {m.status}" if m.status else "")


from vgc_suite.formats import FORMATS as FORMATS_REG


GIMMICK_TAG = {"Mega": "+mega", "Z": "+Z-Move", "Dynamax": "+Dynamax", "Tera": "+Tera"}


def stand_in_request(t: Tracker, sheet: list[dict], bring: list[int]) -> dict:



    me = t.me
    mons = t.mons[me]
    order = sorted(bring, key=lambda i: (mons[i].slot is None, mons[i].slot if mons[i].slot is not None else 9))
    party = []
    for i in order:
        m = mons[i]
        st = ve.set_stats(sheet[i], m.species, t.fmt) if m.species else [1] * 6
        if m.stats is None:
            m.stats = list(st)
        party.append({"ident": f"{me}: {sheet[i].get('name') or sheet[i]['species']}", "active": m.slot is not None and not m.fainted,
                      "condition": _condition(m, m.stats[0]),
                      "stats": dict(zip(("atk", "def", "spa", "spd", "spe"), m.stats[1:]))})
    active = []
    for slot in (0, 1):
        m = next((mons[i] for i in bring if mons[i].slot == slot and not mons[i].fainted), None)
        if m is None:
            active.append(None)
            continue
        if m.vol.get("charging") or m.vol.get("recharge"):
            active.append({"moves": [{"id": "recharge" if m.vol.get("recharge") else "charge"}]})
            continue
        lock = m.vol.get("choicelock")
        encore = m.vol.get("encore_move") if m.vol.get("encore") else None
        disabled_move = m.vol.get("disable_move") if m.vol.get("disable") else None
        moves = []
        for j, mid in enumerate(m.moves):
            if not mid:
                continue
            dis = (m.pp[j] <= 0 or (lock and mid != lock) or (encore and mid != encore) or (disabled_move and mid == disabled_move)
                   or ((m.vol.get("taunt") or m.item == ASSAULT_VEST) and _is_status(mid))
                   or (mid in FIRST_ACTION_ONLY and m.acted)
                   or (mid in NOT_TWICE and m.last_move == mid) or (m.vol.get("torment") and m.last_move == mid))
            moves.append({"id": str(mid), "_mid": int(mid), "pp": int(m.pp[j]), "disabled": bool(dis),
                          "_class": ve.move_choice_target(mid)})
        side = t.side[me]
        can_mega = (not side["mega_used"]) and not m.mega and ve.mega_forme(m.item, m.species) != 0
        trapped = bool(m.vol.get("trapped"))
        active.append({"moves": moves, "canMegaEvo": can_mega, "trapped": trapped, "maybeTrapped": False,
                       "_dynamaxed": "dynamax" in m.vol})
    return {"side": {"pokemon": party}, "active": active, "rqid": 0, "_stand_in": True}


_DEX = None
ASSAULT_VEST = ve.lookup("item", "Assault Vest") or -1


FIRST_ACTION_ONLY = {ve.lookup("move", n) for n in ("Fake Out", "First Impression")} - {0}
NOT_TWICE = {ve.lookup("move", n) for n in ("Gigaton Hammer", "Blood Moon")} - {0}


def _is_status(mid: int) -> bool:
    global _DEX
    if _DEX is None:
        from vgc_trainer.showdown.sheets import STATUS_COLUMN, _move_dex
        _DEX = (_move_dex(), STATUS_COLUMN)
    return bool(_DEX[0][mid, _DEX[1]] != 0)


class _Masks(RequestMasks):


    def _turn_slot(self, slot, party, active):
        from vgc_trainer.showdown.requests import CHOOSABLE, _fainted
        if slot >= len(active) or active[slot] is None:
            self._allow(slot, PASS_ACTION)
            return
        a = active[slot]
        moves = a.get("moves", [])
        if len(moves) == 1 and "pp" not in moves[0]:
            self._allow(slot, 0 * 4 + TARGET_SELF)
        else:
            usable = False
            for i, mv in enumerate(moves):
                if mv.get("disabled"):
                    continue
                usable = True


                cls = ("none" if _is_status(mv["_mid"]) else "adjacentfoe") if a.get("_dynamaxed") else mv["_class"]
                for tg in CHOOSABLE[cls]:
                    self._allow(slot, i * 4 + tg)
            if usable:
                self.mega[slot] = bool(a.get("canMegaEvo"))
                if self.mega[slot]:
                    self.kind[slot] = KIND_MEGA
                    self.gimmick[slot] = self.actions[slot] & ((1 << SWITCH_BASE) - 1)
            else:
                self._allow(slot, 0 * 4 + TARGET_SELF)
        if not a.get("trapped") and not self.shadow_tagged(slot):
            for p in party:
                if not p.get("active") and not _fainted(p):
                    self._allow(slot, SWITCH_BASE + self._k(p))


def _played(lines: list[str], t: Tracker, bring: list[int], sheet: list[dict]) -> tuple[list, list]:


    me, foe = t.me, t.foe
    mons = t.mons[me]
    slot_mon = {m.slot: i for i, m in enumerate(mons) if m.slot is not None and not m.fainted}
    out: list = [None, None]
    text: list = [None, None]
    mega = [False, False]
    tags: list = [None, None]
    acted = False
    for ln in lines:
        p = ln.split("|")
        if len(p) < 3:
            continue
        kind = p[1]


        if p[2:3] and p[2].startswith(me) and len(p[2]) > 2 and p[2][2] in "ab" and (
                kind in ("-mega", "-zpower", "-terastallize") or kind == "-start" and len(p) > 3 and p[3] == "Dynamax"):
            mega["ab".index(p[2][2])] = True
            tags["ab".index(p[2][2])] = {"-mega": "+mega", "-zpower": "+Z-Move", "-terastallize": "+Tera"}.get(kind, "+Dynamax")
        if kind in ("move", "cant", "upkeep"):
            was, acted = acted, True
        else:
            was = acted
        if len(p) < 4 or not p[2].startswith(me) or len(p[2]) < 3 or p[2][2] not in "ab":
            continue
        slot = "ab".index(p[2][2])
        if out[slot] is not None or slot not in slot_mon:
            continue
        i = slot_mon[slot]
        if kind == "move" and not any(x.startswith("[from]") for x in p[4:]):
            mid = ve.lookup("move", p[3])
            if mid == 0 or mid not in mons[i].moves:
                mid, cls_override = _base_of(mons[i], p[3], t.fmt)
            else:
                cls_override = None


            if mid == 0 or mid not in mons[i].moves:
                continue
            j = mons[i].moves.index(mid)
            cls = cls_override or ve.move_choice_target(mid)
            tgt = p[4] if len(p) > 4 else ""
            if cls == "none" or not tgt or "[spread]" in "|".join(p[5:]) or tgt.startswith(me) and tgt[2:3] == p[2][2]:
                tcode = TARGET_SELF if cls in ("none", "allyorself") else TARGET_FOE_A
                if cls == "allyorself":
                    tcode = TARGET_SELF
            elif tgt.startswith(foe) and tgt[2:3] in ("a", "b"):
                tcode = TARGET_FOE_A if tgt[2] == "a" else TARGET_FOE_B
            elif tgt.startswith(me):
                tcode = TARGET_ALLY
            else:
                tcode = TARGET_FOE_A
            out[slot] = (j * 4 + tcode, mega[slot])
            aimed = tcode in (TARGET_FOE_A, TARGET_FOE_B, TARGET_ALLY) and cls != "none" and ": " in tgt
            text[slot] = p[3] + (f" -> {tgt.split(': ', 1)[1]}" if aimed else "")
        elif kind == "switch" and not was:
            nick, sp = to_id(p[2].split(": ", 1)[1]), to_id(p[3].split(",")[0])
            k = next((b for b, si in enumerate(bring) if to_id(sheet[si].get("name") or sheet[si]["species"]) == nick), None)
            if k is None:
                k = next((b for b, si in enumerate(bring) if sp.startswith(to_id(sheet[si]["species"]))
                          or to_id(sheet[si]["species"]).startswith(sp)), None)
            if k is not None:
                out[slot] = (SWITCH_BASE + k, False)
                text[slot] = f"switch {p[2].split(': ', 1)[1]}"
    return out, text, tags


def _base_of(m, name: str, fmt: str | None) -> tuple[int, str | None]:




    zmid = ve.lookup("zmove", name)
    if not zmid:
        return 0, None
    if name.startswith(("Max ", "G-Max ")):
        status = to_id(name) == "maxguard"
        cands = [x for x in m.moves if x and (ve.move_category(x) == "status") == status and (status or move_type(x) == move_type(zmid))]
        return (cands[0], "none" if status else "adjacentfoe") if cands else (0, None)
    base = ve.z_base_move(zmid) or next((x for x in m.moves if x and ve.z_move_of(m.item, m.species, x, fmt) == zmid), 0)
    return (base, None) if base in m.moves else (0, None)


def replay_format(log: ReplayLog) -> str | None:



    base = base_format((log.fmt or "").partition("@@@")[0])
    if base not in FORMATS and base.endswith("bo3"):
        base = base[:-3]
    return base if base in FORMATS and FORMATS[base][0] != 0 else None


def replay_regulation(log: ReplayLog) -> str:


    from vgc_trainer.formats import CURRENT, REGULATIONS, base_id
    past = replay_format(log)
    if past is not None:
        return past
    base = base_id(base_format((log.fmt or "").partition("@@@")[0]))
    return base if base in REGULATIONS else CURRENT


def _spread_corpus(fmt: str | None) -> list[list[dict]]:

    if fmt is None or fmt not in CLOSED_SHEET_FORMATS:
        return _corpus_for(fmt)
    if fmt not in _USAGE:
        _USAGE[fmt] = usage_corpus(fmt)
    return _USAGE[fmt]


_USAGE: dict[str, list[list[dict]]] = {}


_PRIORS: dict = {}


_WORLD_SETS: dict = {}


def _foe_at(log: ReplayLog, foe: str, fmt: str | None, lines: list[str], now: list[dict]) -> list[dict]:
    sh = filled_sets(log, foe, fmt, lines)
    if sh is None:
        return now
    return playable_sheet(sh, fmt=fmt) if len(sh) == ve.ROSTER_SIZE else sh


def filled_sets(log: ReplayLog, side: str, fmt: str | None, lines: list[str] | None = None) -> list[dict] | None:


    from vgc_trainer.showdown import belief
    if fmt not in belief.FORMAT_MOD:
        return None
    if fmt not in _PRIORS:
        _PRIORS[fmt] = belief.SetPrior.load(fmt)
    ev = belief.Evidence(fmt)
    for ln in log.lines if lines is None else lines:
        if ln.startswith("|"):
            ev.feed(ln)
    names = log.species.get(side, [])
    if len(ev.mons[side]) != len(names):
        return None
    out = []
    for sp, f in zip(names, ev.mons[side]):
        key = (fmt, repr(f))
        if key not in _WORLD_SETS:
            try:
                _WORLD_SETS[key] = belief.world_set(_PRIORS[fmt], f, fmt)
            except ValueError:
                _WORLD_SETS[key] = {"item": "", "ability": "", "moves": list(dict.fromkeys(f.moves))[:4]}
        out.append(dict(_WORLD_SETS[key], name=sp, species=sp))
    return out


def set_sources(log: ReplayLog, side: str, fmt: str | None) -> list[dict] | None:



    from vgc_trainer.showdown import belief
    sets = filled_sets(log, side, fmt)
    if sets is None:
        return None
    ev = belief.Evidence(fmt)
    for ln in log.lines:
        if ln.startswith("|"):
            ev.feed(ln)
    out = []
    for s, f in zip(sets, ev.mons[side]):
        shown = set(f.moves)
        moves = [{"name": belief.name("moves", belief.move_id(m)), "src": "shown" if belief.move_id(m) in shown else "guess"}
                 for m in s.get("moves") or []]
        item = belief.to_id(s.get("item") or "")
        ability = belief.to_id(s.get("ability") or "")
        out.append({"species": s["species"], "moves": moves,
                    "item": {"name": belief.name("items", item) if item else "no item",
                             "src": "shown" if f.item is not None and not f.item_swapped else "guess"},
                    "ability": {"name": belief.name("abilities", ability) if ability else "?",
                                "src": "shown" if f.ability is not None and not f.ability_swapped else "guess"},

                    "not_items": sorted(belief.name("items", x) for x in f.not_items if x in _PRIORS[fmt].items) if f.item is None else []})
    return out


def walk(log: ReplayLog, side: str, own_sheet: list[dict] | None = None, keep: bool = False) -> list[Decision]:




    foe = "p2" if side == "p1" else "p1"
    fmt = replay_format(log)
    sheets = {}
    guessed = rebuild = False
    for s in ("p1", "p2"):
        sh = log.sheets.get(s)


        if not sh and not (s == side and own_sheet is not None) and (s == side or fmt not in CLOSED_SHEET_FORMATS):
            sh = filled_sets(log, s, fmt)
            guessed = guessed or sh is not None
            rebuild = rebuild or (s == foe and sh is not None)
        sh = sh or species_sheet(log.species.get(s, []))

        sheets[s] = playable_sheet(sh, fmt=fmt) if len(sh) == ve.ROSTER_SIZE else sh
    if own_sheet is not None:
        sheets[side] = own_sheet
    else:
        sheets[side] = with_spreads(sheets[side], guessed_spreads([sheets[side]], _spread_corpus(fmt))[0])
    unknown = [s["species"] for sh in (sheets[side], sheets[foe]) for s in sh if not ve.lookup("species", s["species"])]
    if unknown:
        raise ValueError(i18n.t("species not in the engine: {list}", list=', '.join(sorted(set(unknown)))))
    shown = side_bring(log, side, sheets[side])
    bring, fill = fill_bring(sheets[side], sheets[foe], shown, fmt)
    t = Tracker(side, sheets[side], sheets[foe], fmt)
    for i in bring:
        t.mons[side][i].brought = True
    names = [to_id(sheets[side][i].get("name") or sheets[side][i]["species"]) for i in bring]
    lines = [ln for ln in log.lines if ln.startswith("|") and not ln.startswith(("|request|", "|showteam|"))]
    pretty = {to_id(ln.split("|")[3]): ln.split("|")[3] for ln in lines if ln.startswith("|move|") and len(ln.split("|")) > 3}
    turn_at = [(int(ln.split("|")[2]), k) for k, ln in enumerate(lines) if ln.startswith("|turn|")]
    out, fed = [], 0
    for n, (turn, k) in enumerate(turn_at):
        if rebuild:
            sheets[foe] = _foe_at(log, foe, fmt, lines[:k + 1], sheets[foe])
            t = Tracker(side, sheets[side], sheets[foe], fmt)
            for i in bring:
                t.mons[side][i].brought = True
            done = 0
            for _, kk in turn_at[:n + 1]:
                t.feed(lines[done:kk + 1])
                done = kk + 1
                if kk != k and not t.over:
                    t.request = stand_in_request(t, sheets[side], bring)
        else:
            t.feed(lines[fed:k + 1])
        fed = k + 1
        if t.over:
            break
        req = stand_in_request(t, sheets[side], bring)
        t.request = req
        masks = _Masks(req, names, t)
        if not masks.to_move:
            continue
        obs = t.observe()
        stop = turn_at[n + 1][1] if n + 1 < len(turn_at) else len(lines)
        played, text, tags = _played(lines[fed:stop], t, bring, sheets[side])
        mons = t.mons[side]
        act = [next((sheets[side][i].get("name") or sheets[side][i]["species"] for i in bring if mons[i].slot == s and not mons[i].fainted),
                    None) for s in (0, 1)]
        fmons = t.mons[foe]
        fact = [next((fmons[i].sheet.get("name") or fmons[i].sheet["species"] for i in range(len(fmons)) if fmons[i].slot == s
                      and not fmons[i].fainted), None) for s in (0, 1)]
        ctx = {"foe_empty": [x is None for x in fact], "turn": turn, "gimmick_played": tags, "gimmick": GIMMICK_TAG.get((FORMATS_REG[fmt].gimmick if fmt in FORMATS_REG else None) or "Mega", "+mega"),
               "damaging": [[not _is_status(mv["_mid"]) for mv in (a or {}).get("moves", []) if "_mid" in mv][:4] + [False] * 4
                            for a in req["active"]]}
        ctx["damaging"] = [d[:4] for d in ctx["damaging"]]
        moves = []
        for s_ in (0, 1):
            i = next((i for i in bring if mons[i].slot == s_ and not mons[i].fainted), None)
            moves.append([pretty.get(to_id(mv), _spaced(mv)) for mv in (sheets[side][i].get("moves") or [])] if i is not None else [])
        display = [sheets[side][i].get("name") or sheets[side][i]["species"] for i in bring]
        out.append(Decision(turn, side, obs, masks, list(bring), names, req, played, text, act, fact, ctx, moves, display,
                            shown=len(shown), fill=fill, guessed=guessed, tracker=copy.deepcopy(t) if keep else None, sheets=sheets if keep else None))
    return out


def tracked_request(d, side: str) -> dict:

    from vgc_trainer.showdown.tracker import to_id as _to_id

    t, sheet = d.tracker, d.sheets[side]
    by_id = {_to_id(s_.get("name") or s_["species"]): i for i, s_ in enumerate(sheet)}
    party = [dict(p, ident=f"{side}: {t.names[side][by_id[_to_id(p['ident'].split(': ', 1)[1])]]}") for p in d.request["side"]["pokemon"]]
    return dict(d.request, side=dict(d.request["side"], pokemon=party))


def closed_world(d, foe: str) -> dict:



    t = d.tracker
    return {} if t.open_sheets else {"foe_world": d.sheets[foe], "fmt": t.fmt}

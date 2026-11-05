








from __future__ import annotations

import vgc_engine as ve

from .tracker import to_id

TARGET_FOE_A, TARGET_FOE_B, TARGET_ALLY, TARGET_SELF = 0, 1, 2, 3
SWITCH_BASE, PASS_ACTION, SLOT_ACTIONS = 16, 20, 21
KIND_MEGA, KIND_Z, KIND_ULTRA, KIND_TERA, KIND_DYNAMAX = 1, 2, 3, 4, 5

CHOOSABLE = {
    "none": (TARGET_SELF,),
    "adjacent": (TARGET_FOE_A, TARGET_FOE_B, TARGET_ALLY),
    "adjacentfoe": (TARGET_FOE_A, TARGET_FOE_B),
    "adjacentally": (TARGET_ALLY,),
    "allyorself": (TARGET_ALLY, TARGET_SELF),
}




REQUEST_TARGET = {
    "normal": "adjacent", "any": "adjacent", "adjacentFoe": "adjacentfoe", "adjacentAlly": "adjacentally",
    "adjacentAllyOrSelf": "allyorself",
}


def _max_targets(mx: dict) -> tuple:


    return CHOOSABLE[REQUEST_TARGET.get(mx.get("target", ""), "none")]


def _choice_class(mv: dict) -> str:
    if "target" in mv:
        return REQUEST_TARGET.get(mv["target"], "none")
    return ve.move_choice_target(ve.lookup("move", mv["id"]))


def _name(ident: str) -> str:
    return to_id(ident.split(": ", 1)[1])


def _fainted(p: dict) -> bool:
    return p["condition"].split(" ")[0] in ("0", "0fnt") or p["condition"].endswith("fnt")


class RequestMasks:



    def __init__(self, request: dict | None, bring_names: list[str], tracker=None):




        self.shadow_tagged = tracker.shadow_tagged if tracker else (lambda slot: False)
        self.imprisoned = tracker.imprisoned() if tracker else set()
        self.request = request
        self.bring = [to_id(n) for n in bring_names]
        self.actions = [0, 0]
        self.mega = [False, False]


        self.gimmick = [0, 0]
        self.forced = [0, 0]
        self.kind = [0, 0]
        self.z_target = [{}, {}]
        self.min_switches = 0
        self.to_move = bool(request) and not request.get("wait") and not request.get("teamPreview")
        if not self.to_move:
            return
        party = request["side"]["pokemon"]
        self.party_names = [_name(p["ident"]) for p in party]
        if request.get("forceSwitch"):
            self._switch_request(party, request["forceSwitch"])
        else:
            for slot in (0, 1):
                self._turn_slot(slot, party, request.get("active") or [])

    def gimmick_codes(self) -> list[list[int]]:


        def code(s: int, a: int) -> int:
            state = 2 if self.forced[s] >> a & 1 else 1 if self.gimmick[s] >> a & 1 else 0
            return state + 4 * self.kind[s] if state else 0

        return [[code(s, a) for a in range(SLOT_ACTIONS)] for s in (0, 1)]

    def _k(self, p: dict) -> int:
        return self.bring.index(_name(p["ident"]))

    def _allow(self, slot: int, action: int) -> None:
        self.actions[slot] |= 1 << action

    def _switch_request(self, party: list, force: list) -> None:
        owed = [bool(force[0]), bool(force[1]) if len(force) > 1 else False]
        reviving = [owed[s] and s < len(party) and bool(party[s].get("reviving")) for s in (0, 1)]
        bench = [p for p in party if not p.get("active") and not _fainted(p)]
        asked = sum(owed)
        required = min(asked, len(bench))
        self.min_switches = required
        for s in (0, 1):
            if not owed[s] or asked > required:
                self._allow(s, PASS_ACTION)
            if owed[s]:
                for p in party:
                    candidate = _fainted(p) if reviving[s] else (not p.get("active") and not _fainted(p))
                    if candidate:
                        self._allow(s, SWITCH_BASE + self._k(p))

    def _turn_slot(self, slot: int, party: list, active: list) -> None:
        if slot >= len(party) or _fainted(party[slot]) or slot >= len(active) or not active[slot] or party[slot].get("commanding"):

            self._allow(slot, PASS_ACTION)
            return
        a = active[slot]
        moves = a.get("moves", [])
        maxes = (a.get("maxMoves") or {}).get("maxMoves") or []
        if len(moves) == 1 and "pp" not in moves[0] or (len(moves) == 1 and moves[0]["id"] == "struggle"):

            self._allow(slot, 0 * 4 + TARGET_SELF)
        elif maxes and not a.get("canDynamax"):


            if any(not mv.get("disabled") for mv in moves):
                for i, mx in enumerate(maxes[:len(moves)]):
                    if not mx.get("disabled"):
                        for t in _max_targets(mx):
                            self._allow(slot, i * 4 + t)
            else:
                self._allow(slot, 0 * 4 + TARGET_SELF)
        else:
            usable = False
            plain = [False] * len(moves)
            for i, mv in enumerate(moves):
                if mv.get("disabled") or a.get("maybeDisabled") and ve.lookup("move", mv["id"]) in self.imprisoned:
                    continue
                usable = plain[i] = True
                for t in CHOOSABLE[_choice_class(mv)]:
                    self._allow(slot, i * 4 + t)
            if usable:
                forme = bool(a.get("canMegaEvo") or a.get("canUltraBurst"))
                zs = a.get("canZMove") or []
                if a.get("canDynamax") and maxes:


                    self.kind[slot] = KIND_DYNAMAX
                    plain_actions = self.actions[slot]
                    for i, mx in enumerate(maxes[:len(moves)]):
                        if mx.get("disabled"):
                            continue
                        for t in _max_targets(mx):
                            bit = 1 << (i * 4 + t)
                            self.gimmick[slot] |= bit
                            if not plain_actions & bit:
                                self.forced[slot] |= bit
                elif forme or a.get("canTerastallize"):

                    self.kind[slot] = KIND_ULTRA if a.get("canUltraBurst") else KIND_MEGA if forme else KIND_TERA
                    self.gimmick[slot] = self.actions[slot] & ((1 << SWITCH_BASE) - 1)
                elif any(zs):
                    self.kind[slot] = KIND_Z
                    for i, z in enumerate(zs[:len(moves)]):
                        if not z:
                            continue
                        self.z_target[slot][i] = z.get("target", "")
                        cls = _choice_class(moves[i])


                        untargeted = REQUEST_TARGET.get(z.get("target", ""), "none") == "none" and cls != "none"
                        targets = (TARGET_FOE_A,) if untargeted else CHOOSABLE[cls]
                        for t in targets:
                            bit = 1 << (i * 4 + t)
                            self.gimmick[slot] |= bit
                            if not plain[i]:
                                self.forced[slot] |= bit
                self.mega[slot] = self.kind[slot] != 0
            else:
                self._allow(slot, 0 * 4 + TARGET_SELF)


                forme = bool(a.get("canMegaEvo") or a.get("canUltraBurst"))
                if forme or a.get("canTerastallize"):
                    self.kind[slot] = KIND_ULTRA if a.get("canUltraBurst") else KIND_MEGA if forme else KIND_TERA
                    self.gimmick[slot] = 1 << (0 * 4 + TARGET_SELF)
                    self.mega[slot] = True
        if not a.get("trapped") and not (a.get("maybeTrapped") and self.shadow_tagged(slot)):
            for p in party:
                if not p.get("active") and not _fainted(p):
                    self._allow(slot, SWITCH_BASE + self._k(p))


    def choice(self, actions: list[tuple[int, bool]]) -> str:

        if not self.to_move:
            return ""
        party = self.request["side"]["pokemon"]
        parts = []
        for slot, (action, mega) in enumerate(actions):
            if action == PASS_ACTION:
                parts.append("pass")
            elif action >= SWITCH_BASE:
                parts.append(f"switch {self.party_names.index(self.bring[action - SWITCH_BASE]) + 1}")
            else:
                m, t = divmod(action, 4)
                move = (self.request.get("active") or [])[slot]["moves"][m]
                cls = ve.move_choice_target(ve.lookup("move", move["id"])) if "target" in move else "none"
                act = (self.request.get("active") or [])[slot]
                if act.get("maxMoves") and (not act.get("canDynamax") or (mega and self.kind[slot] == KIND_DYNAMAX)):

                    mx = act["maxMoves"]["maxMoves"][m]
                    cls = REQUEST_TARGET.get(mx.get("target", ""), "none")
                s = f"move {m + 1}"
                ztgt = self.z_target[slot].get(m) if mega and self.kind[slot] == KIND_Z else None
                if ztgt is not None and REQUEST_TARGET.get(ztgt, "none") == "none":
                    t, cls = None, "none"
                elif ztgt is not None and t == TARGET_SELF and cls == "none":
                    t = TARGET_FOE_A
                if t == TARGET_FOE_A:
                    s += " 1"
                elif t == TARGET_FOE_B:
                    s += " 2"
                elif t == TARGET_ALLY:
                    s += f" -{2 - slot}"
                elif cls == "allyorself":
                    s += f" -{slot + 1}"
                if mega:
                    s += {KIND_Z: " zmove", KIND_ULTRA: " ultra", KIND_TERA: " terastallize", KIND_DYNAMAX: " dynamax"}.get(self.kind[slot], " mega")
                parts.append(s)
        if self.request.get("forceSwitch"):

            parts = [p for s, p in enumerate(parts) if self.request["forceSwitch"][s]]
        return ", ".join(parts)


def describe_action(action: int, moves: list[str], foe: list[str], ally: str, bring: list[str], mega: bool = False) -> str:


    if action == PASS_ACTION:
        return "pass"
    if action >= SWITCH_BASE:
        k = action - SWITCH_BASE
        return f"switch {bring[k] if k < len(bring) else f'#{k + 1}'}"
    m, t = divmod(action, 4)
    s = moves[m] if m < len(moves) and moves[m] else f"move {m + 1}"
    if t in (TARGET_FOE_A, TARGET_FOE_B):
        s += f" -> {foe[t] or ('foe A', 'foe B')[t]}"
    elif t == TARGET_ALLY:
        s += f" -> {ally or 'ally'}"
    return s + (" +mega" if mega else "")


def team_choice(bring: list[int]) -> str:

    return "team " + "".join(str(i + 1) for i in bring)

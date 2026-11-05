













from __future__ import annotations

import numpy as np

from vgc_trainer.preview import N_OUTCOMES
from vgc_trainer.showdown.agent import Agent

from .preview_advisor import _names, head_orders, head_view, human_view
from .selfplay import play_fixed


def _rates(agent: Agent, mine: list[dict], theirs: list[dict], cells: list[tuple], games: int, seed: int) -> np.ndarray:
    pts, n = play_fixed(agent.policy, [mine, theirs], cells, games, agent.dev, seed=seed)
    return pts / np.maximum(n, 1)


def _screen_confirm(agent, mine, theirs, cells, screen, confirm, keep, seed, low: bool, always: list[int] = ()) -> tuple[list, dict]:


    s = _rates(agent, mine, theirs, cells, screen, seed)
    order = np.argsort(s if low else -s)
    short = list(dict.fromkeys([int(i) for i in order[:2 * keep]] + [int(i) for i in always]))
    c = _rates(agent, mine, theirs, [cells[i] for i in short], confirm, seed + 1000)
    res = sorted(zip(short, c.tolist()), key=lambda t: t[1] if low else -t[1])
    return res, dict(zip(short, c.tolist()))


def opener_tree(agent: Agent, mine: list[dict], theirs: list[dict], answers: int = 3, screen: int = 64, confirm: int = 512,
                seed: int = 0) -> dict:

    p_me, p_foe = head_view(agent, mine, theirs), head_view(agent, theirs, mine)
    h_me, h_foe = human_view(mine, theirs), human_view(theirs, mine)
    seq_me, seq_foe = head_orders(agent, mine, theirs), head_orders(agent, theirs, mine)
    main, usual = int(np.argmax(p_me)), int(np.argmax(p_foe))
    se = lambda v: round(float(np.sqrt(max(v * (1 - v), 1e-4) / confirm)), 3)
    hp = lambda h, o: None if h is None else round(float(h[o]), 3)

    def mine_opt(o):
        return {**_names(mine, seq_me[o]), "head_p": round(float(p_me[o]), 3), "human_p": hp(h_me, o)}

    def their_opt(o):
        return {**_names(theirs, seq_foe[o]), "head_p": round(float(p_foe[o]), 3), "human_p": hp(h_foe, o)}

    cols = [(list(seq_me[main]), list(seq_foe[o])) for o in range(N_OUTCOMES)]
    best_for_them, confirmed = _screen_confirm(agent, mine, theirs, cols, screen, confirm, answers, seed, low=True, always=[usual])
    rep = {"screen": screen, "confirm": confirm, "main": {**mine_opt(main), "vs_usual": round(confirmed[usual], 3),
                                                            "vs_usual_se": se(confirmed[usual])},
           "usual": their_opt(usual), "answers": []}
    for k, (o, v) in enumerate(best_for_them[:answers]):
        rows = [(list(seq_me[a]), list(seq_foe[o])) for a in range(N_OUTCOMES)]
        best_for_me, mine_conf = _screen_confirm(agent, mine, theirs, rows, screen, confirm, 1, seed + 10 * (k + 1), low=False,
                                                 always=[main])
        a, cv = best_for_me[0]
        rep["answers"].append({**their_opt(o), "vs_main": round(v, 3), "vs_main_se": se(v),
                               "counter": {**mine_opt(a), "value": round(cv, 3), "value_se": se(cv),
                                           "main_again": round(mine_conf[main], 3), "is_main": a == main}})
    return rep


def render(rep: dict) -> str:
    lab = lambda o: f"{'/'.join(o['lead'])} (+{'/'.join(o['back'])})"
    hum = lambda o: "" if o.get("human_p") is None else f", human head {o['human_p']:.0%}"
    m, u = rep["main"], rep["usual"]
    out = [f"Opener tree - self-play, every value from {rep['confirm']} confirming games (screens at {rep['screen']}); the bot's "
           "view, not a forecast of humans", "",
           f"My main line: {lab(m)}  (head {m['head_p']:.0%}{hum(m)})",
           f"  vs their usual bring {lab(u)} (head {u['head_p']:.0%}{hum(u)}): {m['vs_usual']:.0%} +- {1.96 * m['vs_usual_se']:.0%}", "",
           "Their best answers to it, and my counter to each:"]
    for j, a in enumerate(rep["answers"]):
        c = a["counter"]
        out.append(f"  {j + 1}. {lab(a)}  (their head {a['head_p']:.0%}{hum(a)}): my main line {a['vs_main']:.0%} +- "
                   f"{1.96 * a['vs_main_se']:.0%}")
        if c["is_main"]:
            out.append(f"     counter: none better - my main line stays best here ({c['value']:.0%})")
        else:
            out.append(f"     counter: {lab(c)} {c['value']:.0%} +- {1.96 * c['value_se']:.0%} (main line on the same seed "
                       f"{c['main_again']:.0%}; my head {c['head_p']:.0%}{hum(c)})")
    return "\n".join(out)

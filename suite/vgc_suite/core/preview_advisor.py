









from __future__ import annotations

from vgc_trainer import i18n
import numpy as np
import torch

from vgc_trainer.preview import _OUTCOME_IDS, _SEQS, N_OUTCOMES, bring_logp, outcome_probs
from vgc_trainer.showdown.agent import Agent, sheet_tokens



_OUTCOME_SEQ = np.zeros((N_OUTCOMES, 4), np.int64)
for _seq, _o in zip(_SEQS.numpy(), _OUTCOME_IDS.numpy()):
    _OUTCOME_SEQ[_o] = _seq


def _tokens(mine: list[dict], theirs: list[dict], fmt: str | None) -> np.ndarray:


    return np.concatenate([sheet_tokens(mine, fmt), sheet_tokens(theirs, fmt, as_opponent=fmt is not None)])[None]


@torch.inference_mode()
def head_view(agent: Agent, mine: list[dict], theirs: list[dict], fmt: str | None = None) -> np.ndarray:

    x = _tokens(mine, theirs, fmt)
    lead, back, _ = agent.preview(torch.from_numpy(x).to(agent.dev))
    return outcome_probs(lead.float(), back.float())[0].cpu().numpy()


@torch.inference_mode()
def head_orders(agent: Agent, mine: list[dict], theirs: list[dict], fmt: str | None = None) -> np.ndarray:

    x = _tokens(mine, theirs, fmt)
    lead, back, _ = agent.preview(torch.from_numpy(x).to(agent.dev))
    seqs = _SEQS.to(lead.device)
    lp = bring_logp(lead.float().repeat(len(seqs), 1), back.float().repeat(len(seqs), 1), seqs).cpu().numpy()
    best = np.full(N_OUTCOMES, -np.inf)
    out = _OUTCOME_SEQ.copy()
    for seq, o, v in zip(_SEQS.numpy(), _OUTCOME_IDS.numpy(), lp):
        if v > best[o]:
            best[o], out[o] = v, seq
    return out


def _names(sheet: list[dict], seq) -> dict:
    n = [sheet[i].get("name") or sheet[i]["species"] for i in seq]
    return {"lead": n[:2], "back": n[2:], "bring": [int(i) for i in seq]}


def equilibrium(m: np.ndarray, iters: int = 20000) -> tuple[np.ndarray, np.ndarray, float]:

    r, c = np.zeros(m.shape[0]), np.zeros(m.shape[1])
    r[0] = c[0] = 1
    for _ in range(iters):
        r[np.argmax(m @ (c / c.sum()))] += 1
        c[np.argmin((r / r.sum()) @ m)] += 1
    r, c = r / r.sum(), c / c.sum()
    return r, c, float(r @ m @ c)


@torch.inference_mode()
def human_view(mine: list[dict], theirs: list[dict], fmt: str | None = None) -> np.ndarray | None:


    from .positions import _human_preview
    net = _human_preview()
    if net is None:
        return None
    x = _tokens(mine, theirs, fmt)
    lead, back, _ = net(torch.from_numpy(x))
    return outcome_probs(lead.float(), back.float())[0].numpy()


BOT_MIN_P = 0.02


def _top(p: np.ndarray, k: int, extra: np.ndarray | None, k_extra: int) -> np.ndarray:


    order = np.argsort(-p)
    top = [int(order[0])] + [int(o) for o in order[1:k] if p[o] >= BOT_MIN_P]
    if extra is not None:
        top += [int(o) for o in np.argsort(-extra)[:k_extra] if o not in top]
    else:
        top = [int(o) for o in order[:k]]
    return np.array(top)


def advise(agent: Agent, mine: list[dict], theirs: list[dict], k: int = 5, games: int = 64, seed: int = 0, k_human: int | None = None,
           all_rows: bool = False, screen: int = 64, answers: int = 0, progress=None, screen_keep: int = 3, fmt: str | None = None) -> dict:










    from .brings import Options, derive, play_matrix, screen_answers, screen_counters
    o = Options(agent, mine, theirs, k, k_human, fmt=fmt)
    p_me, p_foe, h_me, h_foe = o.p_me, o.p_foe, o.h_me, o.h_foe
    top_me, top_foe, seq_me, seq_foe = o.top_me, o.top_foe, o.seq_me, o.seq_foe
    screened: set[int] = set()
    screened_foe: set[int] = set()
    say = progress or (lambda *a, **k: None)
    if all_rows:
        o.n_head_foe, o.n_head_me = len(top_foe), len(top_me)
        say(i18n.t("Screening their fours: their best answers to your usual bring"))
        extra = [int(x) for x in screen_answers(agent, mine, theirs, o, screen, seed + 2000, screen_keep) if x not in set(top_foe.tolist())]
        screened_foe = set(extra)
        top_foe = o.top_foe = np.concatenate([top_foe, np.array(extra, dtype=top_foe.dtype)]) if extra else top_foe
        say(i18n.t("Screening your fours: the most robust against all of theirs"))
        extra = [int(x) for x in screen_counters(agent, mine, theirs, o, screen, seed + 3000, screen_keep) if x not in set(top_me.tolist())]
        screened = set(extra)
        top_me = o.top_me = np.concatenate([top_me, np.array(extra, dtype=top_me.dtype)]) if extra else top_me
    km, kf = len(top_me), len(top_foe)
    say(i18n.t("Bring matrix: {mine} x {theirs} brings", mine=len(o.top_me), theirs=len(o.top_foe)))
    m = play_matrix(agent, mine, theirs, o, games, seed)
    se = np.sqrt(m * (1 - m) / max(games, 1))
    foe_mix = p_foe[top_foe] / p_foe[top_foe].sum()
    vs_pred = m @ foe_mix
    worst = m.min(1)
    r_mix, c_mix, value = equilibrium(m)
    hp = lambda h, o: None if h is None else round(float(h[o]), 3)
    opt = lambda i: {**_names(mine, seq_me[top_me[i]]), "head_p": round(float(p_me[top_me[i]]), 3), "human_p": hp(h_me, top_me[i]),
                     "human_only": bool(p_me[top_me[i]] < BOT_MIN_P and i > 0 and int(top_me[i]) not in screened),
                     "screened": int(top_me[i]) in screened}
    rep = {
        "games_per_cell": games, "k": k,
        "my_options": [opt(i) for i in range(km)],
        "their_options": [{**_names(theirs, seq_foe[top_foe[j]]), "head_p": round(float(p_foe[top_foe[j]]), 3),
                           "human_p": hp(h_foe, top_foe[j]),
                           "human_only": bool(p_foe[top_foe[j]] < BOT_MIN_P and j > 0 and int(top_foe[j]) not in screened_foe),
                           "screened": int(top_foe[j]) in screened_foe} for j in range(kf)],
        "matrix": [[round(float(v), 3) for v in row] for row in m], "matrix_se": round(float(se.max()), 3),
        "vs_predicted": [round(float(v), 3) for v in vs_pred],
        "best_response": int(np.argmax(vs_pred)), "safest": int(np.argmax(worst)), "worst_case": [round(float(v), 3) for v in worst],
        "equilibrium": {"mine": [round(float(v), 3) for v in r_mix], "theirs": [round(float(v), 3) for v in c_mix],
                        "value": round(value, 3)},
    }
    if h_foe is not None:
        hm = h_foe[top_foe] / h_foe[top_foe].sum()
        vs_h = m @ hm
        rep.update(vs_human=[round(float(v), 3) for v in vs_h], best_vs_human=int(np.argmax(vs_h)),
                   human_coverage={"mine": round(float(h_me[top_me].sum()), 3), "theirs": round(float(h_foe[top_foe].sum()), 3)})

    mt = 1 - m.T
    my_mix = p_me[top_me] / p_me[top_me].sum()
    b = {"vs_predicted": mt @ my_mix, "worst_case": mt.min(1)}
    if h_me is not None:
        b["vs_human"] = mt @ (h_me[top_me] / h_me[top_me].sum())
    rep["theirs_view"] = {k: [round(float(v), 3) for v in x] for k, x in b.items()}
    rep["theirs_view"].update(best_response=int(np.argmax(b["vs_predicted"])), safest=int(np.argmax(b["worst_case"])),
                              **({"best_vs_human": int(np.argmax(b["vs_human"]))} if "vs_human" in b else {}))
    rep["all_rows"] = bool(all_rows)


    rep["summary"] = derive(agent, mine, theirs, o, m, games, seed)
    if answers:
        say(i18n.t("Opener tree"))
        from .opener_tree import opener_tree
        rep["opener_tree"] = opener_tree(agent, mine, theirs, answers=answers, seed=seed + 31)
    return rep


def render(rep: dict) -> str:
    me, foe = rep["my_options"], rep["their_options"]
    lab = lambda o: f"{'/'.join(o['lead'])} (+{'/'.join(o['back'])})"
    out = [f"Preview advisor - self-play payoff, {rep['games_per_cell']} games per cell (+-{rep['matrix_se']:.2f} at worst); "
           "the bot's view, not a guarantee against humans", "", "Their likely brings (preview head):"]
    out += [f"  {j + 1}. {lab(o)}  {o['head_p']:.0%}" for j, o in enumerate(foe)]
    out += ["", f"{'My option':<52} head   vs-pred  worst  eq-mix   " + "  ".join(f"T{j + 1:<4}" for j in range(len(foe)))]
    for i, o in enumerate(me):
        tags = (" <- best vs predicted" if i == rep["best_response"] else "") + (" <- safest" if i == rep["safest"] else "")
        out.append(f"{lab(o) + (' *' if o.get('screened') else ''):<52} {o['head_p']:>4.0%}  {rep['vs_predicted'][i]:>6.0%}  "
                   f"{rep['worst_case'][i]:>5.0%}  {rep['equilibrium']['mine'][i]:>5.0%}   "
                   + "  ".join(f"{v:>5.0%}" for v in rep["matrix"][i]) + tags)
    out.append(f"\nEquilibrium value (both sides adapt): {rep['equilibrium']['value']:.0%}")
    if any(o.get("screened") for o in me):
        out.append("(* found by screening all 90 brings: neither preview model lists it)")
    if rep.get("opener_tree"):
        from .opener_tree import render as render_tree
        out += ["", render_tree(rep["opener_tree"])]
    return "\n".join(out)

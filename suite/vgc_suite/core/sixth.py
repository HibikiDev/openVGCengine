




















from __future__ import annotations

from vgc_trainer import i18n
import re
from collections import Counter, defaultdict
from pathlib import Path

import torch


def _base(species: str) -> str:
    return species.split("-")[0].strip().lower()


def _item(s: dict) -> str:
    return (s.get("item") or "").replace(" ", "").lower()


def clash(five: list[dict], s: dict) -> str | None:

    if _base(s["species"]) in {_base(x["species"]) for x in five}:
        return "Species Clause: the five already have it"
    if _item(s) and _item(s) in {_item(x) for x in five}:
        return f"Item Clause: the five already hold {s['item']}"
    return None


def is_mega(s: dict) -> bool:

    it = _item(s)
    return bool(re.search(r"ite[xyz]?$", it)) and it != "eviolite"


def field_candidates(five: list[dict], field: list[tuple[str, list[dict]]], weights: list[float] | None, top: int,
                     skip: set[str] = frozenset(), kind: str = "any") -> list[tuple[str, dict]]:




    weights = weights or [1.0] * len(field)
    have = {_base(x["species"]) for x in five} | {_base(k) for k in skip}
    held = {_item(x) for x in five if _item(x)}
    usage: Counter = Counter()
    variants: dict = defaultdict(Counter)
    example: dict = {}
    for (_, sets), w in zip(field, weights):
        for s in sets:
            k = s["species"]
            if _base(k) in have or (kind == "mega" and not is_mega(s)) or (kind == "plain" and is_mega(s)):
                continue
            usage[k] += w
            key = (_item(s), s.get("ability") or "", tuple(sorted(s.get("moves") or [])))
            variants[k][key] += w
            example.setdefault((k, key), s)
    out = []
    for k, _ in usage.most_common():
        key = next((v for v, _ in variants[k].most_common() if not v[0] or v[0] not in held), None)
        if key is not None and _base(k) not in {_base(x["species"]) for _, x in out}:
            out.append((k, dict(example[(k, key)])))
        if len(out) >= top:
            break
    return out


def set_line(s: dict) -> str:
    return " · ".join(x for x in [s.get("item") or "", s.get("ability") or "", " / ".join(s.get("moves") or [])] if x)


def sweep(five: list[dict], candidates: list[tuple[str, str, dict]], field: list[tuple[str, list[dict]]], ckpt: Path, games: int,
          seed: int = 0, dev: torch.device | None = None, weights: list[float] | None = None, field_name: str | None = None,
          progress=None, brings_agent=None, robust_top: int = 0, robust_k: int = 3, robust_games: int = 256,
          baseline: tuple[str, dict] | None = None, search_games: int = 0, fmt: str | None = None) -> dict:












    from vgc_trainer.showdown.teams import to_paste
    from vgc_suite.formats import engine
    from .validator import _ready, run_validation
    efmt = engine(fmt)
    rows, skipped = [], []
    todo = []
    if baseline is not None:
        candidates = [(f"keep {baseline[0]}", "current", baseline[1])] + list(candidates)
    for label, src, s in candidates:
        why = clash(five, s)
        if why is None:
            try:
                todo.append((label, src, s, _ready(five + [s], fmt)))
                continue
            except Exception as e:
                why = f"the engine can't play it ({e})"
        skipped.append({"label": label, "source": src, "why": why})

    per = games if not search_games else search_games * sum(1 for x in (weights or [1.0] * len(field)) if x > 0)
    for n, (label, src, s, six) in enumerate(todo):

        step = None if progress is None else (
            lambda m, d=None, t=None, ph=None, n=n, label=label: progress(i18n.t("Candidate {n} of {total} ({label}) · {step}", n=n + 1, total=len(todo), label=label, step=m),
                                                                          n * per + (d or 0), len(todo) * per,
                                                                          ph if ph == "search-tail" else "search" if search_games else "fast"))
        if step:
            step(i18n.t("starting"))
        rep = run_validation(six, field, ckpt, games=games, seed=seed, dev=dev, team_id=f"five + {label}", weights=weights,
                             field_name=field_name, progress=step, search_games=search_games, fmt=efmt)
        rows.append({"label": label, "source": src, "species": s["species"], "set": set_line(s), "paste": to_paste([s]), "six_paste": to_paste(six),
                     "overall": rep["overall"], "_six": six,
                     "games": rep["games"], "mon": rep["mons"][5],
                     "opponents": {r["id"]: r["score"] for r in rep["opponents"]},
                     "opp_games": {r["id"]: r["games"] for r in rep["opponents"]},
                     "opp_info": {r["id"]: {"species": r["species"], "share": r["share"]} for r in rep["opponents"]}})
    if not rows:
        return {"error": "no candidate could be run: " + "; ".join(f"{x['label']}: {x['why']}" for x in skipped)}
    rows.sort(key=lambda r: -r["overall"]["score"])
    mean = sum(r["overall"]["score"] for r in rows) / len(rows)
    for r in rows:
        r["vs_mean"] = round(r["overall"]["score"] - mean, 3)
    ids = list(rows[0]["opponents"])
    opp_mean = {i: sum(r["opponents"].get(i, 0) for r in rows) / len(rows) for i in ids}
    opponents = [{"id": i, **rows[0]["opp_info"][i], "games": rows[0]["opp_games"][i], "mean": round(opp_mean[i], 3),
                  "best": max(rows, key=lambda r: r["opponents"].get(i, 0))["label"]} for i in sorted(ids, key=lambda i: opp_mean[i])]
    robust_rows = [r for r in rows if r["source"] == "current"] + [r for r in rows if r["source"] != "current"][:robust_top]
    robust_n = len(robust_rows) if brings_agent is not None and robust_top else 0
    for n, r in enumerate(robust_rows[:robust_n]):
        r["robust"] = _both_adapt(brings_agent, r["_six"], field, weights, robust_k, robust_games, seed, efmt,
                                  lambda j, r=r, n=n: progress and progress(i18n.t("Both-adapt pass: candidate {n} of {total} ({label}), team {j} of {teams}",
                                                                                    n=n + 1, total=robust_n, label=r['label'], j=j + 1, teams=len(field)),
                                                                             n * len(field) + j, robust_n * len(field), "robust"))
    for r in rows:
        r.pop("opp_info")
        r.pop("_six")
    robust = sorted((r for r in rows if r.get("robust")), key=lambda r: -r["robust"]["equilibrium"])
    return {"sweep": True, "slot": {"replaced": baseline[0], "baseline": f"keep {baseline[0]}"} if baseline is not None else None,
            "five": [s.get("name") or s["species"] for s in five], "model": Path(ckpt).name, "games_each": per,
            "search": {"games_per_team": search_games} if search_games else None,
            "field": {"teams": len(field), "name": field_name, "weighted": weights is not None}, "rows": rows, "opponents": opponents,
            "skipped": skipped,
            "robust": {"k": robust_k, "games_per_cell": robust_games, "order": [r["label"] for r in robust]} if robust_n else None,
            "caveats": ["the bot pilots both teams", "a field candidate gets its commonest set in the field, spreads guessed where unknown"]}


def _both_adapt(agent, six: list[dict], field: list[tuple[str, list[dict]]], weights: list[float] | None, k: int, games: int, seed: int,
                efmt: str | None, progress) -> dict:

    from .brings import summary
    w = weights or [1.0] * len(field)
    per = {}
    for j, (fid, sets) in enumerate(field):
        progress(j)
        b = summary(agent, six, sets, k=k, games=games, seed=seed + 101 * (j + 1), fmt=efmt)
        eq_me, eq_them = b["equilibrium"]["mine"], b["equilibrium"]["theirs"]
        top_me = b["mine"][max(range(len(eq_me)), key=lambda i: eq_me[i])]
        ans = b["theirs"][b["best_answer"]["col"]]
        per[fid] = {"best_answer": b["best_answer"]["value"], "answer_bring": ans["lead"] + ans["back"],
                    "outside_heads": b["best_answer"]["outside_heads"],
                    "as_picked": b["as_picked"], "equilibrium": b["equilibrium"]["value"], "safest": b["safest"]["value"],
                    "vs_human": b["vs_human"][0] if b["vs_human"] else None,

                    "my_bring": top_me["lead"] + top_me["back"],
                    "sixth_share": round(sum(v for o, v in zip(b["mine"], eq_me) if 5 in o["bring"]), 3)}

    def avg(key: str) -> float | None:
        vals = [(per[fid][key], wt) for (fid, _), wt in zip(field, w) if per[fid][key] is not None]
        return round(sum(v * wt for v, wt in vals) / sum(wt for _, wt in vals), 3) if vals else None
    return {"eq_by_team": {fid: p["equilibrium"] for fid, p in per.items()},
            "best_answer": avg("best_answer"), "equilibrium": avg("equilibrium"), "vs_human": avg("vs_human"), "as_picked": avg("as_picked"), "safest": avg("safest"),
            "sixth_share": avg("sixth_share"), "per": per}

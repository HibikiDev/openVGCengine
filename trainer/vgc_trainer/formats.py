









from __future__ import annotations

import os



REGULATIONS = ("gen9championsvgc2026regmc",)

STANDIN = "gen9championsvgc2026regzz"
if os.environ.get("OPENVGC_STANDIN_REGULATION") == "1":
    REGULATIONS = REGULATIONS + (STANDIN,)
CURRENT = REGULATIONS[-1]
CHAMPIONS_PREFIX = "gen9champions"

SUFFIXES = ("bo3buddy", "buddy", "bo3")


def base_id(fmt: str) -> str:

    for s in SUFFIXES:
        if fmt.endswith(s):
            return fmt[: -len(s)]
    return fmt


def is_champions(fmt: str | None) -> bool:

    return fmt is None or base_id(fmt).startswith(CHAMPIONS_PREFIX)


def engine_format(fmt: str | None) -> str | None:

    return None if is_champions(fmt) else fmt




ENGINE_CHAMPIONS = ("gen9championsvgc2026regmb",)


def training_format(fmt: str | None) -> str | None:



    if fmt is not None and base_id(fmt) in ENGINE_CHAMPIONS:
        return base_id(fmt)
    return engine_format(fmt)


def newest_first(regs: tuple[str, ...] = REGULATIONS) -> tuple[str, ...]:

    return tuple(reversed(regs))







from __future__ import annotations

from dataclasses import dataclass

MC = "gen9championsvgc2026regmc"


@dataclass(frozen=True)
class Format:
    id: str
    name: str
    short: str
    gen: int
    open_sheets: bool
    stat_points: bool
    megas: bool
    gimmick: str | None


FORMATS = {f.id: f for f in (
    Format(MC, "[Gen 9 Champions] VGC 2026 Reg M-C", "Reg M-C", 9, True, True, True, "Mega"),
    Format("gen5vgc2013", "[Gen 5] VGC 2013", "VGC 2013", 5, False, False, False, None),
    Format("gen6vgc2014", "[Gen 6] VGC 2014", "VGC 2014", 6, False, False, True, "Mega"),
    Format("gen6vgc2015", "[Gen 6] VGC 2015", "VGC 2015", 6, False, False, True, "Mega"),
    Format("gen6vgc2016", "[Gen 6] VGC 2016", "VGC 2016", 6, False, False, True, "Mega"),
    Format("gen7vgc2017", "[Gen 7] VGC 2017", "VGC 2017", 7, False, False, True, "Z"),
    Format("gen7vgc2018", "[Gen 7] VGC 2018", "VGC 2018", 7, False, False, True, "Z"),
    Format("gen7vgc2019", "[Gen 7] VGC 2019", "VGC 2019", 7, False, False, True, "Z"),
    Format("gen8vgc2020", "[Gen 8] VGC 2020", "VGC 2020", 8, False, False, False, "Dynamax"),
    Format("gen8vgc2021", "[Gen 8] VGC 2021", "VGC 2021", 8, False, False, False, "Dynamax"),
    Format("gen8vgc2022", "[Gen 8] VGC 2022", "VGC 2022", 8, False, False, False, "Dynamax"),
    Format("gen9vgc2023regc", "[Gen 9] VGC 2023 Reg C", "SV Reg C", 9, True, False, False, "Tera"),
    Format("gen9vgc2023regd", "[Gen 9] VGC 2023 Reg D", "SV Reg D", 9, True, False, False, "Tera"),
    Format("gen9vgc2024regg", "[Gen 9] VGC 2024 Reg G", "SV Reg G", 9, True, False, False, "Tera"),
    Format("gen9vgc2025regi", "[Gen 9] VGC 2025 Reg I", "SV Reg I", 9, True, False, False, "Tera"),
)}
CURRENT = MC


IN_TOOLS = (MC, "gen9vgc2025regi", "gen9vgc2024regg", "gen9vgc2023regd", "gen9vgc2023regc", "gen8vgc2022", "gen8vgc2021",
            "gen8vgc2020", "gen7vgc2019", "gen7vgc2018", "gen7vgc2017", "gen6vgc2016", "gen6vgc2015", "gen6vgc2014", "gen5vgc2013")



IN_ANALYZER = IN_TOOLS


def get(fmt: str | None) -> Format:

    f = FORMATS.get(fmt or CURRENT)
    if f is None:
        raise ValueError(f"unknown format {fmt!r}")
    return f


def engine(fmt: str | None) -> str | None:

    return None if fmt in (None, MC) else get(fmt).id


def tool_format(value: str | None) -> str:

    fmt = value or CURRENT
    if fmt not in IN_TOOLS:
        raise ValueError(f"the tools don't play {FORMATS[fmt].short if fmt in FORMATS else fmt} yet")
    return fmt

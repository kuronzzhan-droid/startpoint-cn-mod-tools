"""Player-facing form tags from explicit character markers, never costume guesses."""
from __future__ import annotations

import re


# Audited official CN rows: six story-only records (c32=2) and fifteen assist
# records (c32=4). An explicit ID list prevents future unrelated rows being
# silently excluded just because their undocumented marker has the same value.
OFFICIAL_NON_PLAYABLE_IDS = frozenset({
    "700000", "700001", "700002", "700003", "700004", "700005", "700006",
    "700007", "700008", "700009", "700010", "700011", "700012", "700013",
    "700014", "700015", "700016", "700017", "700018", "700019", "999999",
})
THEME_MARKERS = (
    (r"_(?:smr\d{2}|swim|summer|seaside)(?:_|$)", "泳装"),
    (r"_xm\d{2}(?:_|$)", "圣诞"),
    (r"_ny\d{2}(?:_|$)", "新春"),
    (r"_hw\d{2}(?:_|$)", "万圣节"),
    (r"_(?:vt\d{2}|valentine)(?:_|$)", "情人节"),
    (r"_wt\d{2}(?:_|$)", "白色情人节"),
    (r"_(?:\d+)?(?:half)?anv(?:_|$)", "周年"),
    (r"_campus(?:_|$)", "校园"),
    (r"_autumn(?:_|$)", "秋日"),
)


def character_tags(cid: str, row: list, name: str, aliases: list[str]) -> dict:
    code = str(row[0])
    themes = [label for pattern, label in THEME_MARKERS if re.search(pattern, code)]
    if str(cid) in {"119990", "119991", "119992", "139991", "139992", "149986", "149987", "159995", "169988", "169991"}:
        themes = ["中秋"]
    if not themes:
        identity = str(row[27]) if len(row) > 27 else ""
        themes = ["其他变体" if identity not in ("", "(None)", str(cid)) else "通常版"]
    search_aliases = list(aliases)
    if name and themes[0] not in ("通常版", "其他变体"):
        search_aliases.extend(f"{theme}{name}" for theme in themes)
    return {"theme": themes[0], "themes": themes,
            "aliases": list(dict.fromkeys(search_aliases))}

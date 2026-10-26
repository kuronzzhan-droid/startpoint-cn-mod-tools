"""Group confirmed dungeon families without replacing their persistent entry IDs."""
from __future__ import annotations

import re

from wf_wiki_dungeons_schema import cell, event_table, quest_table
from wf_wiki_dungeon_event_groups import extra_boss_series, extra_event_series
from wf_wiki_dungeon_groups import SERIES_VARIANTS, validate_series_fields


ELEMENT_LABELS = {"fire": "火", "water": "水", "thunder": "雷", "wind": "风",
                  "storm": "风", "light": "光", "dark": "暗", "another": "无属性"}
FAMILIES = {"steam_robot": "series-machina", "discarded_dragon": "series-waste-dragons",
            "spirit_beast": "series-spirit-beasts"}
GAUNTLET_ENTRIES = {
    ("rush", "700098"): "幻想连战", ("rush", "700099"): "普通深渊",
    ("rush", "700100"): "深渊连战EX",
    ("advent", "300098"): "幻想连战",
}


def series_fields(family, element):
    series, label = FAMILIES.get(family), ELEMENT_LABELS.get(element)
    return {"seriesId": series, "variantLabel": label} if label in SERIES_VARIANTS.get(series, ()) else {}


def event_series(kind, key, row):
    """Use the master family code, never an inherited banner or recommended element."""
    if (kind, str(key)) in GAUNTLET_ENTRIES:
        return {"seriesId": "series-gauntlets", "variantLabel": GAUNTLET_ENTRIES[kind, str(key)]}
    if kind not in ("advent", "hard_multi"):
        return extra_event_series(kind, row)
    prefix = "advent_" if kind == "advent" else r"hard_multi_(?:advent_)?"
    families = "steam_robot|discarded_dragon|spirit_beast" if kind == "advent" else "steam_robot"
    match = re.match(r"^" + prefix + "(" + families + r")_"
                     r"(fire|water|thunder|wind|storm|light|dark|another)(?=$|_|[0-9])", cell(row, 0))
    if match and match[2] == "storm" and match[1] != "spirit_beast":
        return {}
    return series_fields(*match.groups()) if match else extra_event_series(kind, row)


def boss_series(row):
    """Stage-node artwork names identify the actual enemy family and its element."""
    match = re.fullmatch(r"quest/boss_battle/background/boss_battle_"
                         r"(steam_robot|discarded_dragon|spirit_beast)_"
                         r"(fire|water|thunder|wind|light|dark|another)(?:\.png)?", cell(row, 12))
    return series_fields(*match.groups()) if match else extra_boss_series(cell(row, 12))


def correct_gauntlet_images(items):
    """Remove visibly inherited Combat Diver/Steam Robot artwork from custom modes.

    Fantasy's cooperative stages are part of the same gauntlet (stages 5/10/15),
    not a Steam Robot activity. Keep their ID for saved guides and recommendations.
    """
    by_id = {item["id"]: item for item in items}
    fantasy = by_id.get("event-rush-700098")
    for item in items:
        if item.get("seriesId") != "series-gauntlets":
            continue
        for field in ("_banners", "_entries", "_previews"):
            item[field] = [path for path in item[field] if "combat_diver" not in path
                           and not (item["id"] == "event-advent-300098" and "steam_robot" in path)]
        if item["id"] == "event-advent-300098" and not item["_banners"] and fantasy:
            item["_banners"] = list(fantasy["_banners"])
            item["_sources"].append(event_table("rush"))


def validate_series(item):
    validate_series_fields(item)


def verified_gauntlet_tables(sources, identifier):
    """Only actual published master overlays support the stronger source label."""
    if identifier not in {"event-rush-700098", "event-rush-700099", "event-rush-700100"}:
        return False
    for logical in (event_table("rush"), quest_table("rush")):
        record = sources.records.get(logical, {})
        if (record.get("origin") not in ("gray", "gray-snapshot") or not record.get("patchVersion")
                or not re.fullmatch(r"[0-9a-f]{64}", record.get("archiveSha256", ""))):
            return False
    return True

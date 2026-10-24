"""Historical CN availability badges from explicitly identified offline records.

The supplied localApi role.id is an unrelated database ID. Across all 484
official playable records, codeName and showOrder jointly match the game's
code and character ID, and property matches its element. Names can have
translation differences; costumes and names are never availability evidence.
"""
from __future__ import annotations

from collections import defaultdict
import json

SOURCE = "《弹射世界中文 WIKI》离线版 v3.0.0 · 国服获取方式"
NOTE = "依据旧 Wiki 国服获取方式标记，不代表当前 MOD 服卡池安排。"


def availability_from_role(character: dict, role: dict) -> dict:
    """Return only an explicit, same-character CN acquisition classification."""
    if character.get("origin") not in {"官方原版", "改版官方"}:
        return {}
    if not character.get("code") or character["code"] != role.get("codeName"):
        return {}
    if str(character.get("id")) != str(role.get("showOrder")):
        return {}
    if character.get("elementId") is None or str(character["elementId"]) != str(role.get("property")):
        return {}
    # Use CN acquisition data only. JP availability is not a CN fallback.
    try:
        ways = json.loads(role.get("wayCn") or "[]")
    except (TypeError, ValueError):
        return {}
    if not isinstance(ways, list) or any(not isinstance(item, str) for item in ways):
        return {}
    limited = any(("限定卡池" in item or "限定扭蛋" in item) and "非限定" not in item for item in ways)
    permanent = any("常驻池" in item for item in ways)
    if limited == permanent:  # Conflicting sources, or neither explicitly stated.
        return {}
    return {"limited": limited, "availabilitySource": SOURCE, "availabilityNote": NOTE}


def enrich_availability(catalog: dict, roles: list[dict]) -> dict:
    """Add badges using a unique code plus independently agreeing ID/element."""
    by_code = defaultdict(list)
    for role in roles:
        if isinstance(role, dict) and role.get("codeName"):
            by_code[role["codeName"]].append(role)
    counts = {"limited": 0, "permanent": 0, "unmarked": 0}
    for character in catalog["characters"]:
        matches = by_code.get(character.get("code"), [])
        fields = availability_from_role(character, matches[0]) if len(matches) == 1 else {}
        character.update(fields)
        if "limited" in fields:
            counts["limited" if fields["limited"] else "permanent"] += 1
        else:
            counts["unmarked"] += 1
    catalog["meta"]["availability"] = {"source": SOURCE, "note": NOTE,
        "unmarkedNote": "缺少明确限定/常驻记载或无法准确对应的条目不作推断。", **counts}
    return counts

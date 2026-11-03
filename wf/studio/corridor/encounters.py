"""Encounter bands and act bosses, ported from rogue-map-v3.js / rogue-rules-v3f.js.

Act boss = highest-threat encounter of the act's rank band (after global exclude_rounds); act 1
skips encounters whose damage rate vs the start element is at/below v3f.boss_elements.threshold.
"""
from __future__ import annotations

import re

from .effects import ELEMENTS, ELEMENT_NAMES

ELEMENT_CHARS = {"火": 1, "水": 2, "雷": 3, "风": 4, "光": 5, "暗": 6}
RATES = {"减半": 0.5, "降至1/10": 0.1, "降至1%": 0.01}
MATCH = re.compile(r"((?:[火水雷风光暗]·)*[火水雷风光暗])(?:属性)?伤害(减半|降至1/10|降至1%)")
LOOSE = re.compile(r"[火水雷风光暗](?:·[火水雷风光暗])*(?:属性)?伤害")


def _round4(n: float) -> float:
    import math
    return math.floor(n * 10000 + 0.5) / 10000


def element_damage(curse_details) -> dict:
    rates = {e: 1.0 for e in ELEMENTS}
    issues = []
    for c in curse_details if isinstance(curse_details, list) else []:
        text = c.get("effect") if isinstance(c, dict) and isinstance(c.get("effect"), str) else ""
        rest = text
        for m in MATCH.finditer(text):
            for ch in m.group(1).split("·"):
                e = ELEMENT_CHARS[ch]
                rates[e] = _round4(rates[e] * RATES[m.group(2)])
            rest = rest.replace(m.group(0), "", 1)
        if LOOSE.search(rest):
            issues.append(f"{c.get('name')}: element damage text not understood: {text}")
    return {"rates": rates, "issues": issues}


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def host_encounters(pool: dict) -> list[dict]:
    out = []
    for e in (pool.get("encounters") or []):
        if not isinstance(e, dict):
            continue
        dmg = element_damage(e.get("curse_details"))
        out.append({"quest_id": str(e.get("quest_id")), "round": _int(e.get("round")),
                    "threat": e.get("threat") if isinstance(e.get("threat"), (int, float)) else _int(e.get("round")),
                    "element": e.get("element"), "kind_hint": e.get("kind_hint"), "label": e.get("enemy_label"),
                    "mechanic_text": e.get("mechanic_text"), "field": e.get("field"), "curses": e.get("curses") or [],
                    "element_damage": dmg["rates"], "damage_issues": dmg["issues"],
                    "source_quest_id": e.get("source_quest_id")})
    return out


def acts_view(rules: dict, pool: dict) -> dict:
    enc_cfg = rules.get("encounters") or {}
    exclude = set(enc_cfg.get("exclude_rounds") or [])
    host = host_encounters(pool)
    active = [e for e in host if e["round"] not in exclude]
    ranked = sorted(active, key=lambda e: (e["threat"], e["round"]))
    for rank, e in enumerate(ranked, 1):
        e["rank"] = rank
    v3f = rules.get("v3f") or {}
    be = v3f.get("boss_elements") or {}
    threshold = be.get("threshold", 0.1)
    acts, problems = [], []
    for i, act in enumerate(((rules.get("map") or {}).get("acts") or [])):
        lo, hi = (act.get("encounter_ranks") or [1, 0])[:2]
        band = ranked[lo - 1:hi] if isinstance(lo, int) and isinstance(hi, int) and lo >= 1 else []
        info = {"act": i + 1, "ranks": [lo, hi], "quests": [e["quest_id"] for e in band], "size": len(band),
                "boss": band[-1]["quest_id"] if band else None, "boss_by_element": {}, "excluded_by_element": {}}
        if len(band) < 4:
            problems.append({"act": i + 1, "message": f"第{i + 1}幕遭遇段只剩 {len(band)} 个（服务端要求至少 4 个，否则开局生成地图时报错）"})
        if band:
            for el in ELEMENTS:
                if i == 0 and be.get("exclude_act1", True):
                    idx = len(band) - 1
                    while idx >= 0 and band[idx]["element_damage"].get(el, 1) <= threshold:
                        idx -= 1
                    info["excluded_by_element"][str(el)] = [e["quest_id"] for e in band
                                                            if e["element_damage"].get(el, 1) <= threshold]
                    if idx < 0:
                        info["boss_by_element"][str(el)] = None
                        problems.append({"act": 1, "element": el,
                                         "message": f"第1幕对开局属性{ELEMENT_NAMES[el]}没有可用首领（全部伤害倍率≤{threshold}），服务端会拒绝加载配置"})
                    else:
                        info["boss_by_element"][str(el)] = band[idx]["quest_id"]
                else:
                    info["boss_by_element"][str(el)] = band[-1]["quest_id"]
        acts.append(info)
    return {"host": host, "ranked": [e["quest_id"] for e in ranked], "acts": acts, "problems": problems,
            "excluded_rounds": sorted(exclude), "threshold": threshold}

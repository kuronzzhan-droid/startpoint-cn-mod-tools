"""Export only native degree images explicitly linked to visible characters."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path

import wf_mod_tool as core
import wf_quest_lib
from wf_wiki_categories import HIDDEN_CHARACTER_IDS

DEGREES = "master/degree/degree.orderedmap"
MISSIONS = "master/mission/degree_mission.orderedmap"
REWARDS = "master/mission/degree_mission_reward.orderedmap"
MOD_LINKS = "assets/character_degree_rewards.json"


def cell(row, index):
    return row[index] if index < len(row) else ""


def native_links(source) -> dict:
    """Use mission.character_id, never a character name or an image filename.

    DegreeMissionValues c15 is character_id. DegreeMissionRewardValues has
    four reward blocks at c5/11/17/23: kind 6 is Degree, its ID is offset +5.
    Reward rows are nested by mission ID and stage. Awake-mission rewards use
    a different layout; the current table contains no Degree rewards.
    """
    links = defaultdict(dict)
    missions = source.table(MISSIONS)
    if not missions:
        return links
    raw = source.raw(REWARDS)
    rewards = wf_quest_lib.parse_node(raw) if raw else {}
    labels = {"44": "信赖铭牌", "48": "第二玛纳板铭牌"}
    for key, rows in missions.items():
        stages = rewards.get(key, {})
        if not isinstance(stages, dict):
            continue
        for row in rows:
            cid = cell(row, 15)
            if not cid.isdigit() or cid in HIDDEN_CHARACTER_IDS:
                continue
            for value in stages.values():
                for reward in core.read_csv_lines(value):
                    for offset in (5, 11, 17, 23):
                        if cell(reward, offset) == "6" and cell(reward, offset + 5).isdigit():
                            links[cid][reward[offset + 5]] = labels.get(cell(row, 3), "角色铭牌")
    return links


def attach_nameplates(repo: Path, source, characters: list[dict], media) -> dict:
    """Attach real image references; report absent definitions/images without substitution."""
    visible = {str(character["id"]): character for character in characters
               if str(character["id"]) not in HIDDEN_CHARACTER_IDS}
    for character in characters:
        character["nameplates"] = []
    links = native_links(source)
    config = Path(repo) / MOD_LINKS
    config_raw = config.read_bytes() if config.is_file() else None
    if config_raw is not None:
        settings = json.loads(config_raw)
        if settings.get("schema_version") != 1 or not isinstance(settings.get("characters"), list):
            raise ValueError("角色专属铭牌登记格式不受支持")
        for entry in settings["characters"]:
            cid = str(entry["character_id"])
            if cid in visible:
                for degree in entry["degree_ids"]:
                    links[cid][str(degree)] = "专属铭牌"
    definitions = source.table(DEGREES)
    counts = {"total": 0, "characters": 0, "missingDefinitions": 0, "missingImages": 0}
    for cid, character in visible.items():
        for key, label in sorted(links.get(cid, {}).items(), key=lambda pair: int(pair[0])):
            rows = definitions.get(key, [])
            row = rows[0] if rows else []
            logical = cell(row, 8)
            if not logical.startswith("dynamic/degree/") or not cell(row, 2):
                counts["missingDefinitions"] += 1
                continue
            url = media.image(logical + ".png")
            if not url:
                counts["missingImages"] += 1
                continue
            character["nameplates"].append({
                "name": row[2], "url": url, "acquisition": cell(row, 4), "label": label,
            })
        counts["total"] += len(character["nameplates"])
        counts["characters"] += bool(character["nameplates"])
    if (config.read_bytes() if config.is_file() else None) != config_raw:
        raise RuntimeError("导出期间角色铭牌登记变化，请重新导出")
    return {**counts,
        "sourceFiles": {MOD_LINKS: hashlib.sha256(config_raw).hexdigest()} if config_raw else {},
        "note": "仅展示角色任务或专属登记明确关联的游戏铭牌原图；未关联或图片缺失时不使用替代图。获得条件保留当前游戏文案。"}

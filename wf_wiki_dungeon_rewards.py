"""Export read-only gray-server rewards/shops without exposing raw game IDs."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from wf_wiki_dungeon_rewards_mapping import boss_shop_links, build_mapping
from wf_wiki_dungeon_rewards_rules import QuestRewards, folder_rewards, rogue_round
from wf_wiki_dungeon_rewards_schema import PREFIX, require, validate_payload
from wf_wiki_dungeon_rewards_shops import build_shops
from wf_wiki_dungeon_rewards_special import score_rewards, special_mode_rewards
from wf_wiki_dungeon_rewards_sources import GrayAssets, Names, collect_event_titles, read_assignment, wiki_catalog
from wf_wiki_dungeons_sources import DungeonSources
from wf_wiki_paths import is_junction

SOURCE_RULES = {
    "lib/assets.ts": ["quest.sPlusReward = { type: 0, id: 14040, count: 3 }", "eventId = ABYSS_NORMAL_EVENT_ID",
                      "isAbyssExEndlessQuest(category, questId)", "shouldRollRogueFolderRandomReward"],
    "lib/content-master.ts": ['new Set(["59001010"])', '"700099"'],
    "lib/quest.ts": ["reward.rarity >= randomInt(0, 100) / 100", "randomInt(group.length)", "DROP_MULTIPLIER"],
    "lib/shop-sales.ts": ["9_700_201", "9_700_301", "stock !== undefined", ": -1"],
    "lib/boss/reward-profile.ts": ["questId: 1020004", "scoreGroupId: 209990", "tokenItemId: 40193",
                                   "solo: 1, multi: 3", "rareGroupId: 3099900", "rareChanceBasisPoints: 100"],
    "lib/quest/finish/rogue-drops.ts": ["ABYSS_EX_EVENT_ID && rushEventRound === 0", "match_party_element", "guarantee_weapon"],
    "lib/quest/finish/rogue-drop-schedule.ts": ["guaranteed_slots", "exclude_rounds", "base_round", "random() <"],
    "lib/mode15.ts": ["MODE15_SOLO_FIXED_REWARDS", "5: 5", "10: 10", "15: 20",
                      "MODE15_DREAM_EMBLEM_ID, count: 200", "ref.stage === 15 && !options.rescue"],
    "multi/five-boss/rewards.ts": ["FIVE_BOSS_BLUEPRINT_DROP_RATE = 0.5", "amount: 5 * input.rewardMultiplier",
                                  "randomFloat) < 0.25", "firstClearEmblem: 10000146"],
    "lib/quest/finish/carnival-reward-handler.ts": ["kind === 7", "case 6:", "case 2:", "RewardType.BEADS"],
    "lib/quest/finish/score-attack-handler.ts": ["reward.kind !== 0", "tier.score <= previousHighScore"],
}


def source_receipt(directory):
    result = {}
    for name, snippets in SOURCE_RULES.items():
        path = directory / name
        require(path.is_file() and not path.is_symlink(), "Missing gray runtime rule source: " + name)
        raw = path.read_bytes()
        value = raw.decode("utf-8-sig")
        require(all(text in value for text in snippets), "Gray runtime rule changed: " + name)
        result[name] = hashlib.sha256(raw).hexdigest()
    return result


def build_payload(assets, wiki, catalog, mapping, boss_links=None, gray_source=None, collect_titles=None):
    names = Names(assets, wiki)
    resolver = QuestRewards(assets, names)
    rogue = assets.rogue()
    special = special_mode_rewards(names, gray_source) if gray_source else {}
    dungeons = {}
    for leaf in catalog["items"]:
        key = leaf["id"]
        entry = {"quests": [], "shopIds": [], "notes": []}
        for kind, quest_id, record, title in mapping.get(key, []):
            if key == "boss-1-99" and quest_id != "1099001":
                continue
            quest = resolver.regular(kind, quest_id, record, title)
            if key == "boss-1-99":
                quest["name"] += " · 单人基础结算"
                quest["notes"].append("此段为单人普通结算；协力使用独立结算，只参考下面的模式奖励。内部阶段关卡不单独结算。")
            event_id = str(record.get("rushEventId", ""))
            config = rogue.get(event_id, {})
            if kind == "rush" and config and quest_id != "700100099":
                quest["drops"] += rogue_round(names, config, record.get("rushEventRound", 0))
            entry["quests"].append(quest)
        # Fantasy's native folder row mirrors the mode15 non-rescue completion
        # grant. Showing both would incorrectly imply two separate grants.
        if key.startswith("event-rush-") and key != "event-rush-700098":
            event_id = key.removeprefix("event-rush-")
            entry["quests"] += folder_rewards(names, assets, event_id, rogue.get(event_id, {}))
        entry["quests"] += score_rewards(assets, names, key, mapping.get(key, []))
        entry["quests"] += special.get(key, [])
        if not entry["quests"]:
            entry["notes"].append("当前灰服快照中尚未对应此入口的奖励资料。")
        if key in ("event-rush-700098", "event-advent-300098"):
            entry["notes"].append("幻想奖励按灰服已安装模块配置展示；运行环境可能停用或替换该模块，游戏开放状态未实测。")
        dungeons[key] = entry
    shops = build_shops(assets, names, catalog, dungeons, boss_links, collect_titles)
    payload = {"schemaVersion": 1, "source": {
        "label": "灰服当前配置快照；掉落显示基础数量，活动加倍和个人库存另计。",
        "status": "gray-snapshot", "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "dungeons": dungeons, "shops": shops}
    validate_payload(payload, dungeon_ids=set(dungeons), equipment_ids=set(names.equipment), character_ids=set(names.characters))
    return payload, names


def export_rewards(site, gray_assets, gray_source, dungeon_snapshot, store, receipt):
    site, receipt = Path(site).resolve(), Path(receipt).resolve()
    gray_assets, gray_source = Path(gray_assets).resolve(), Path(gray_source).resolve()
    require(site.is_dir() and site != gray_assets and not site.is_relative_to(gray_assets), "Invalid output site")
    require(not site.is_symlink() and not is_junction(site), "Linked output site")
    require(not receipt.is_relative_to(site), "Private export receipt must be outside public site")
    evidence = source_receipt(gray_source)
    assets = GrayAssets(gray_assets)
    catalog = read_assignment(site / "dungeons-data.js", "WF_WIKI_DUNGEONS")
    wiki = wiki_catalog(site)
    sources = DungeonSources(Path(store), snapshot=Path(dungeon_snapshot))
    mapping, mapping_audit = build_mapping(sources, catalog, assets)
    titles, title_evidence = collect_event_titles(store)
    payload, names = build_payload(assets, wiki, catalog, mapping, boss_shop_links(sources, catalog), gray_source, titles)
    raw = (PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n").encode("utf-8")
    target = site / "rewards-data.js"
    require(not target.is_symlink(), "Linked reward output")
    target.write_bytes(raw)
    audit = {"schemaVersion": 1, "checkedAt": payload["source"]["checkedAt"], "bytes": len(raw),
             "sha256": hashlib.sha256(raw).hexdigest(), "dungeons": len(payload["dungeons"]),
             "quests": sum(len(row["quests"]) for row in payload["dungeons"].values()),
             "shops": len(payload["shops"]), "products": sum(len(row["items"]) for row in payload["shops"]),
             "mapping": mapping_audit, "grayAssets": assets.hashes, "grayRuntimeRules": evidence,
             "clientTitleReference": title_evidence,
             "unresolvedNames": sorted([list(x) for x in names.unknown])}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {key: audit[key] for key in ("dungeons", "quests", "shops", "products", "bytes", "sha256", "mapping")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("site", "gray-assets", "gray-source", "dungeon-snapshot", "store", "receipt"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    print(json.dumps(export_rewards(**vars(args)), ensure_ascii=False))


if __name__ == "__main__":
    main()

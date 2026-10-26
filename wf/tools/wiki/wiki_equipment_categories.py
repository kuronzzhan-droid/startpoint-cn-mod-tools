"""Weapon series from verified native sources, without changing game data."""
from __future__ import annotations

from wf_wiki_equipment_helpers import cell, integer

QUEST_SEARCH = "master/search/equipment_quest_search.orderedmap"
BOSS_SHOP = "master/shop/boss_coin_shop.orderedmap"
BOND_IDS = frozenset("5010005 5030005 5040022 5020024 5070027 5050026 5020041 5060044".split())

# Series identity was checked against the current native enhancement shop categories:
# 2 = epuration, 3 = steam robot, 4 = score attack (Pu Lilie's medals).
# The epuration event shops also match advent quests named 女帝歼灭者.
# Pu Lilie weapons cost item 49100, named 普·莉莉艾的勋章 in native item data.
SERIES_IDS = {
    "女帝武器": frozenset("5010070 5020043".split()),
    "普莉莉艾武器": frozenset("5010032 5010045 5010056 5030028 5040020 5100011".split()),
    "机兵武器": frozenset("5010073 5020042 5070044 5080032 5090047 5100020".split()),
    # Verified against the author's offline Wiki v3.0.0 weaponData.way/wayCn:
    # each explicitly lists 临境域 and 深渊兽 阿比斯. This is not the MOD abyss set.
    "临境域武器": frozenset("5090018 5010042 5020025 5010033 5040029 5040026 5050025 5060037".split()),
}

CATEGORY_NOTE = (
    "按已核对的系列、原生掉落检索及领主币商店归类；领主分类包括掉落与兑换。"
    "临境域系列另参考旧 Wiki 的明确来源记录。分类不代表当前一定开放获取；未确认来源的保留在其他武器。"
)


def source_categories(source) -> dict[str, str]:
    """Read native quest references and all six reward slots of boss coin shops.

    EquipmentQuestSearchValues uses c0: Main=0, Ex=1, BossBattle=2,
    StoryEvent=5, AdventEvent=6, ChallengeDungeon=7, WorldStory=9/10.
    BossCoinShopValues uses reward type/id/count triples from c32; type 4
    is equipment. Shop row c0 is its category, not an equipment identifier.
    Specific series are applied later and always take precedence.
    """
    result = {}
    for key, rows in source.table(QUEST_SEARCH).items():
        kinds = {cell(row, 0) for row in rows}
        if "2" in kinds:
            result[key] = "领主掉落与兑换"
        elif "7" in kinds:
            result[key] = "深层域武器"
        elif kinds & {"0", "1"}:
            result[key] = "主线武器"
        elif kinds & {"5", "6", "9", "10"}:
            result[key] = "活动武器"
    for rows in source.table(BOSS_SHOP).values():
        for row in rows:
            for offset in range(32, 50, 3):
                key = cell(row, offset + 1)
                if cell(row, offset) == "4" and key and integer(cell(row, offset + 2)) > 0:
                    result[key] = "领主掉落与兑换"
    return result


def category_for(key: str, row, categories=None) -> str:
    """Only exact IDs or explicit acquisition fields determine a category."""
    key = str(key)
    number = integer(key)
    # Author-requested display grouping: both native 破星剑 entries join PARADOX.
    # This label must NOT confer PARADOX's client-side decay rule on either sword.
    if key in {"300001", "300002", "5920001"}:
        return "悖论武器"
    if 5910101 <= number <= 5910129:
        return "诅咒武器"
    if key in BOND_IDS:
        return "羁绊武器"
    if 8000101 <= number <= 8000115:
        return "深渊武器"
    if key == "5900101":
        return "五重决战武器"
    # src/lib/fantasy-gauntlet/contract.ts: FANTASY_EXCLUSIVE_EQUIPMENT_IDS.
    if 100013 <= number <= 100023:
        return "幻想武器"
    for label, identifiers in SERIES_IDS.items():
        if key in identifiers:
            return label
    if cell(row, 2) == "1":
        return "世界弹射器宝珠"
    # EquipmentValues.obtain_source=0 is the native gacha source. Cross-check:
    # all 70 official rows exactly match the old Wiki's explicit 装备池 entries.
    # MOD series above override it (e.g. the MOD abyss rotation core).
    if cell(row, 15) == "0":
        return "装备扭蛋武器"
    return (categories or {}).get(key, "其他武器")

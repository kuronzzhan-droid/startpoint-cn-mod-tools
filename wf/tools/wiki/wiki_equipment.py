"""Public, read-only catalog of the locally registered weapons and soul orbs."""
from __future__ import annotations

import hashlib
import json
import ast
from collections import Counter, defaultdict
from pathlib import Path

from wf_wiki_catalog_source import WikiSource
from wf_wiki_equipment_helpers import (
    EquipmentImages, PublicText, cell, effects, integer, status_points,
)
from wf_wiki_equipment_forms import FORM_NOTE, paradox_forms
from wf_wiki_equipment_final import final_effect_fields
from wf_wiki_equipment_categories import BOND_IDS, CATEGORY_NOTE, category_for, source_categories

EQUIPMENT = "master/item/equipment.orderedmap"
SOUL = "master/ability/ability_soul.orderedmap"
STATUS = "master/item/equipment_status.orderedmap"
ENHANCEMENT = "master/equipment_enhancement/equipment_enhancement.orderedmap"
ENHANCEMENT_ABILITY = "master/equipment_enhancement/equipment_enhancement_ability.orderedmap"
ENHANCEMENT_STATUS = "master/equipment_enhancement/equipment_enhancement_status.orderedmap"
ITEM = "master/item/item.orderedmap"
ELEMENTS = {0: "火", 1: "水", 2: "雷", 3: "风", 4: "光", 5: "暗", -1: "通用/未分类"}
ELEMENT_NOTE = "沿用服务端装备属性分类；魂珠使用对应武器分类。通用/未分类不代表能力没有属性条件，具体限制仍以效果说明为准。"


def equipment_element(value):
    """The server's explicit classification, never inferred from public names."""
    return ELEMENTS.get(value, "未标注") if type(value) is int else "未标注"


def party_rules(raw):
    """Read the client patch's literal policy without importing or applying it."""
    config = next(node for node in ast.parse(raw).body
                  if isinstance(node, ast.ClassDef) and node.name == "Config")
    values = {node.target.id: ast.literal_eval(node.value) for node in config.body
              if isinstance(node, ast.AnnAssign)}
    return {"countScope": "本方三个有主位角色的位置，各自的武器槽与魂珠槽；不计其他参战玩家。",
            "curseExclusion": {"threshold": values["cursed_threshold"], "includesSouls": True,
                "paradoxIncluded": False, "affected": "整件能力（本体与强化），不移除装备 HP / 攻击力"},
            "paradoxDecay": {"offAtOtherCount": values["decay_off"], "includesSouls": True,
                "excludeSelf": True, "duplicateItemsCountSeparately": True,
                "note": "其他已装槽位逐件计数；另一个悖论也计 1 件。按对应分档能力生效，不能把所有词条统一乘系数。"},
            "requiresClientSupport": True}


def enhancement_costs(records, names):
    """Server purchases advance one level; boundary stages therefore count once."""
    totals = Counter()
    stages = []
    previous = 0
    for row in sorted(records, key=lambda item: item.get("stage", 0)):
        cap = integer(row.get("enhancementMaxLevel"))
        count = max(0, cap - previous)
        costs = []
        for cost in row.get("costs", []):
            name = names.get(str(cost["id"]), "未收录材料")
            amount = integer(cost.get("amount"))
            costs.append({"name": name, "amount": amount})
            totals[name] += amount * count
        user_cost = row.get("userCost")
        if user_cost:
            name = {0: "玛纳", 1: "星导石", 2: "羁绊证"}.get(user_cost["type"], "其他货币")
            amount = integer(user_cost.get("amount"))
            costs.append({"name": name, "amount": amount})
            totals[name] += amount * count
        stages.append({"fromLevel": previous, "toLevel": cap, "perLevelCosts": costs,
                       "requiredAwakeningLevel": row.get("requireAwakeningLevel")})
        previous = cap
    return {"stages": stages, "total": [{"name": key, "amount": value} for key, value in totals.items()],
            "note": "按本机强化商店每份提升 1 级计算；从强化 0 级到当前最高档。"}


def build_equipment_catalog(repo: Path, media, source=None) -> dict:
    source = source or WikiSource(repo, media.store)
    tracked = {}

    def read_json(relative):
        path = Path(repo) / relative
        raw = path.read_bytes()
        tracked[relative] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    known = {str(value) for value in read_json("assets/equipment_ids.json")}
    known_souls = {str(value) for value in read_json("assets/soul_item_ids.json")}
    element_map = read_json("assets/equipment_element.json")
    rules_path = "client-patch/equipment-rules/rules.py"
    rules_raw = (Path(repo) / rules_path).read_bytes()
    tracked[rules_path] = hashlib.sha256(rules_raw).hexdigest()
    rules = party_rules(rules_raw)
    shops = defaultdict(list)
    for row in read_json("assets/equipment_enhancement_shop.json").values():
        shops[str(row.get("equipmentId"))].append(row)
    equipment, souls = source.table(EQUIPMENT), source.table(SOUL)
    categories = source_categories(source)
    enhanced, additional = source.table(ENHANCEMENT), source.table(ENHANCEMENT_ABILITY)
    item_names = {key: cell(rows[0], 2) for key, rows in source.table(ITEM).items() if rows}
    text, pictures = PublicText(source), EquipmentImages(media)
    entries = []
    for key in sorted(known & set(equipment), key=int):
        row = equipment[key][0]
        notes = []
        limit = max(1, integer(cell(row, 8), 1))
        points = status_points(source, STATUS, key)
        base = {k: points[0][k] for k in ("hp", "atk")} if points else None
        maximum = {k: points[-1][k] for k in ("hp", "atk")} if points else None
        if not points:
            notes.append("装备 HP / 攻击力表缺失，未推算数值。")
        soul_rows = souls.get(cell(row, 10), [])
        first_effects = effects(soul_rows, "ability_soul", 1, text, maximum=False)
        max_effects = effects(soul_rows, "ability_soul", limit, text)
        override = text.override("desc_override_equipment_" + key)
        icon = pictures.image(cell(row, 6))
        if not icon:
            notes.append("当前图标资源缺失。")
        entry = {
            "id": key, "name": text.clean(cell(row, 1)), "rarity": integer(cell(row, 11)),
            "element": equipment_element(element_map.get(key)),
            "category": category_for(key, row, categories), "icon": icon, "description": text.clean(cell(row, 7)),
            "maxAwakeningLevel": limit, "stats": {"base": base, "awakened": maximum,
                                                    "checkpoints": points},
            "baseEffects": first_effects, "awakenedEffects": max_effects,
            "descriptionSource": "当前数据自动解析；专用面板文案另列。",
            "panelDescription": override, "canSoul": key in known_souls and bool(soul_rows),
            "soul": {"effects": first_effects, "available": key in known_souls and bool(soul_rows),
                "canGenerate": cell(row, 9).lower() == "true",
                "note": "魂珠使用最低档能力，不继承武器 HP / 攻击力及强化追加能力。"},
            "enhancement": None, "notes": notes,
        }
        # c9 controls generation, while the server registry controls available soul items.
        if not entry["canSoul"]:
            entry["soul"]["note"] = "当前服务端未登记此装备的可用魂珠。"
            entry["soul"]["effects"] = []
        if key in enhanced:
            erow = enhanced[key][0]
            max_level = integer(cell(erow, 0))
            increments = status_points(source, ENHANCEMENT_STATUS, key)
            increment = increments[-1] if increments else None
            total = ({k: maximum[k] + increment[k] for k in ("hp", "atk")}
                     if maximum is not None and increment is not None else None)
            image_path = cell(erow, 4) or cell(row, 6)
            tier2 = text.custom.get("enhanced_pixelart_tier2_" + image_path, "").split(",", 1)
            if len(tier2) == 2 and integer(tier2[0], max_level + 1) <= max_level:
                image_path = tier2[1]
            entry["enhancement"] = {
                "maxLevel": max_level, "name": text.clean(cell(erow, 2) or cell(row, 1)),
                "icon": pictures.image(image_path), "description": text.clean(cell(erow, 6)),
                "effects": effects(additional.get(key, []), "equipment_enhancement_ability", max_level, text),
                "panelDescription": text.override("desc_override_equipment_enhancement_" + key),
                "finalDescription": text.override("desc_override_equipment_enhancement_" + key + "_final"),
                "stats": {"additional": {k: increment[k] for k in ("hp", "atk")} if increment else None,
                          "total": total, "checkpoints": increments},
                "costs": enhancement_costs(shops[key], item_names),
                "note": "所列能力为强化满级的追加效果，与满觉醒本体叠加；专用终式合计文案已经包含本体。",
            }
            entry["enhancement"].update(final_effect_fields(
                soul_rows, additional.get(key, []), limit, max_level, text))
            if key == "5920001":
                entry["enhancement"]["forms"] = paradox_forms(
                    entry, erow, soul_rows, additional.get(key, []), increments, text, pictures)
                entry["enhancement"]["note"] = FORM_NOTE
            if not increments or increments[-1]["level"] != max_level:
                notes.append("强化数值表未覆盖当前最高等级；请以游戏内面板为准。")
            if key in BOND_IDS:
                notes.append("羁绊武器强化只增加词条，HP 与攻击力保持本体数值。")
        if key == "5920001":
            entry["partyRule"] = "paradoxDecay"
            notes.append("同队其他武器或魂珠每多 1 件，增益降低 25%；达到 4 件时整件失效。诅咒代价不随增益衰减。")
        elif entry["category"] == "诅咒武器":
            entry["partyRule"] = "curseExclusion"
            notes.append("同队装备两件以上诅咒武器或魂珠时，全部诅咒武器与魂珠失效；强化 1 级起诅咒生效。")
        entries.append(entry)
    source.verify_unchanged()
    for relative, expected in tracked.items():
        if hashlib.sha256((Path(repo) / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError("导出期间装备登记或商店数据变化，请重新导出")
    return {"equipment": entries, "meta": {
        "counts": dict(Counter(entry["category"] for entry in entries)), "total": len(entries),
        "enhanced": sum(entry["enhancement"] is not None for entry in entries),
        "partyRules": rules,
        "categoryNote": CATEGORY_NOTE,
        "elementNote": ELEMENT_NOTE,
        "sourceHashes": dict(source.live_hashes), "sourceMissing": sorted(source.missing),
        "sourceFiles": tracked, "note": "收录当前本机登记的装备；收录不代表所有装备当前都有获取渠道。",
        "effectNote": "按原生能力槽选择已解锁最高档，分别列最低档、满觉醒和满强化；复杂能力以游戏内说明为准。",
    }}

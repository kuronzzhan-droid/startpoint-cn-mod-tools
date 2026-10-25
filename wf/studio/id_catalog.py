"""Read-only ID evidence from native tables and an optional server mirror."""
from __future__ import annotations

import json
from pathlib import Path

import wf_quest_lib as codec
from wf.boss.schema import iter_leaves, parse_rows
from wf.boss.shop_model import WEAPON_TABLES, ENH_SHOP
from .drafts import DraftError

CHARACTER = "master/character/character.orderedmap"
MANA = "master/mana_board/mana_node.orderedmap"
TABLES = {
    "character": (CHARACTER, "master/character/character_status.orderedmap",
                  "master/character/character_text.orderedmap"),
    "multiball": ("master/battle/multiball/multiball.orderedmap",
                  "master/battle/multiball/multiball_level.orderedmap"),
    "weapon": WEAPON_TABLES,
    "soul_item": ("master/item/item.orderedmap", "master/ability/ability_soul.orderedmap"),
    "unique_condition": ("master/character/unique_condition.orderedmap",),
    "string_id": ("master/string/custom_ability_string.orderedmap",),
    "mana_node": (MANA, "master/generated/mana_board.orderedmap"),
    "enhancement_shop": (ENH_SHOP,),
}
SERVER_FILES = {
    "character": ("character.json", "cdndata/character.json", "cdndata/character_text.json"),
    "multiball": ("multiball.json", "multiball_level.json", "cdndata/multiball.json"),
    "weapon": ("equipment_lookup.json", "equipment_ids.json", "equipment_max_level.json",
               "equipment_element.json", "item_ids.json", "item_lookup.json", "item_sale.json",
               "equipment_awakening_material.json"),
    "soul_item": ("item_ids.json", "item_lookup.json", "item_sale.json", "ability_soul.json"),
    "unique_condition": ("unique_condition.json", "cdndata/unique_condition.json"),
    "string_id": ("custom_ability_string.json", "cdndata/custom_ability_string.json"),
    "mana_node": ("mana_node.json", "mana_node_cnmod.json", "mana_board.json"),
    "enhancement_shop": ("equipment_enhancement_shop.json",),
}


def load_json(filename):
    try:
        value = json.loads(Path(filename).read_text("utf-8-sig"))
    except (ValueError, OSError) as exc:
        raise DraftError(f"无法读取 ID 来源 {filename}: {exc}") from exc
    if not isinstance(value, (dict, list)):
        raise DraftError(f"ID 来源必须是对象或数组: {filename}")
    return value


def table(source, logical):
    """Use the nested native codec, including mana-board/status inner maps."""
    try:
        raw = source.raw(logical)
    except (FileNotFoundError, KeyError):
        raw = None
    if raw is None:
        return {}
    try:
        result = codec.parse_node(raw)
    except (ValueError, TypeError) as exc:
        raise DraftError(f"无法解码 ID 来源表 {logical}: {exc}") from exc
    if not isinstance(result, dict):
        raise DraftError(f"ID 来源表不是 ordered map: {logical}")
    return result


def mana_segment(node):
    """Native IDs are str(cid * 2) + a three-digit suffix (1000 slots)."""
    text = str(node)
    if not text.isdigit() or len(text) <= 3:
        return None
    prefix = int(text[:-3])
    return str(prefix // 2) if prefix > 0 and prefix % 2 == 0 else None


def table_ids(kind, logical, rows):
    if not isinstance(rows, dict):
        raise DraftError(f"ID 来源表不是 ordered map: {logical}")
    for identity, value in rows.items():
        # mana_node queries allocate a whole character-owned segment, not a slot.
        yield str(identity), str(identity)
        if kind == "mana_node" and logical == MANA:
            for _, text in iter_leaves(value):
                for row in parse_rows(text):
                    segment = mana_segment(row[0]) if row else None
                    if segment is not None:
                        yield segment, str(identity)


def server_ids(kind, name, rows):
    if name.endswith("equipment_awakening_material.json"):
        if not isinstance(rows, dict):
            raise DraftError(f"装备觉醒来源必须是对象: {name}")
        for section in ("materialByEquipment", "rarityOverrides"):
            values = rows.get(section, {})
            if not isinstance(values, dict):
                raise DraftError(f"装备觉醒 {section} 必须是对象: {name}")
            yield from ((str(identity), str(identity)) for identity in values)
        return
    for identity in rows:
        if not isinstance(identity, (str, int)) or isinstance(identity, bool):
            raise DraftError(f"ID 来源包含非标量标识符: {name}")
        yield str(identity), str(identity)
    if kind == "mana_node" and isinstance(rows, dict) and "mana_node" in name:
        for owner, boards in rows.items():
            for board in boards.values() if isinstance(boards, dict) else ():
                for node in board if isinstance(board, dict) else ():
                    segment = mana_segment(node)
                    if segment is not None:
                        yield segment, str(owner)


def collect_tables(source, add):
    cache = {}
    for kind, logicals in TABLES.items():
        for logical in logicals:
            if logical not in cache:
                cache[logical] = table(source, logical)
            for identity, owner in table_ids(kind, logical, cache[logical]):
                add(kind, identity, owner, "view", logical)
    # Any stage inside the native 99-slot range occupies its parent weapon ID.
    for identity in cache.get(ENH_SHOP, {}):
        if identity.isdigit():
            add("weapon", str(int(identity) // 100), identity, "view", ENH_SHOP)


def collect_server(server_dir, add):
    if server_dir is None:
        return
    root = Path(server_dir).resolve()
    if not root.is_dir():
        raise DraftError(f"服务端镜像目录不存在: {root}")
    cache = {}
    for kind, names in SERVER_FILES.items():
        for name in names:
            # Accept a repository root or its assets directory; inspect both if present.
            for filename in (root / "assets" / name, root / name):
                if not filename.is_file():
                    continue
                if not filename.resolve().is_relative_to(root):
                    raise DraftError(f"服务端 ID 来源越界: {filename}")
                if filename not in cache:
                    cache[filename] = load_json(filename)
                rows = cache[filename]
                for identity, owner in server_ids(kind, name, rows):
                    add(kind, identity, owner, "server", str(filename))
                    if kind == "enhancement_shop" and identity.isdigit():
                        add("weapon", str(int(identity) // 100), owner, "server", str(filename))
                        entry = rows.get(identity, {}) if isinstance(rows, dict) else {}
                        if isinstance(entry, dict) and str(entry.get("equipmentId", "")).isdigit():
                            add("weapon", str(entry["equipmentId"]), owner, "server", str(filename))
                if name == "equipment_awakening_material.json":
                    for identity in rows.get("materialByEquipment", {}):
                        add("string_id", "awakening_material_" + str(identity), str(identity),
                            "server", str(filename))

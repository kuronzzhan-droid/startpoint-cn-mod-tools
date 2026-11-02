"""Clone the imported scenario graph in memory, reserving no IDs or files."""
from __future__ import annotations

import copy
import re
from .scene_spec import validate_spec
from .scene_types import CONTINUE_PREFIX


def clone_scene(spec, event_id, name=None):
    validate_spec(spec)
    if not isinstance(event_id, str) or not re.fullmatch(r"[3-9][0-9]{5}", event_id):
        raise ValueError("新活动 ID 必须是 300000–999999 的六位字符串")
    old = spec["event"]["id"]
    if old == event_id or spec.get("creation"):
        raise ValueError("须从已有活动母本克隆到不同 ID")
    replacements = {old: event_id}
    for tier in spec["tiers"]:
        new_quest = event_id + str(int(tier["id"])).zfill(3)
        replacements[tier["quest"]] = new_quest
        replacements[CONTINUE_PREFIX + tier["quest"]] = CONTINUE_PREFIX + new_quest
    for table in spec["tables"]:
        for entry in table["entries"]:
            for key in entry["path"]:
                if key.isdigit() and key.startswith(old):
                    replacements[key] = event_id + key[len(old):]
                elif key.startswith(CONTINUE_PREFIX + old):
                    replacements[key] = CONTINUE_PREFIX + event_id + key[len(CONTINUE_PREFIX + old):]
        if table["logical"] == "master/shop/event_item_shop.orderedmap":
            for index, entry in enumerate(table["entries"], 1):
                replacements[entry["path"][0]] = str(int(event_id) * 100 + index)
        elif table["logical"] == "master/item/item.orderedmap":
            for index, entry in enumerate(table["entries"], 1):
                replacements[entry["path"][0]] = str(int(event_id) * 100 + 50 + index)
    replacements["mod_hp_"] = "mod_scene_" + event_id + "_"
    replacements["mod_hell_pumpkin"] = "mod_studio_scene_" + event_id
    # Namespace all logic paths, including marker and terrain; retain existing
    # art/BGM references so originals are neither replaced nor re-authored.
    for prefix in ("battle/action/enemy/action", "battle/action/item/action", "battle/terrain"):
        replacements[prefix + "/mod/hell_pumpkin/"] = prefix + "/mod/studio_scene_" + event_id + "/"
    for resource in spec["resources"]:
        logical = resource["logical"]
        if logical.startswith("battle/boss/mod/hell_pumpkin/") and "_marker." in logical:
            base = logical.removesuffix(".timeline.amf3.deflate")
            replacements[base] = base.replace("/mod/hell_pumpkin/", "/mod/studio_scene_" + event_id + "/")
    # IDs match complete digit tokens, never arbitrary substrings of numbers.
    pattern = re.compile("|".join((r"(?<![A-Za-z0-9_/])" + re.escape(key) + r"(?![A-Za-z0-9_/])")
        if key.isdigit() or key == "mod_hell_pumpkin" or key.startswith(CONTINUE_PREFIX) else re.escape(key)
        for key in sorted(replacements, key=len, reverse=True)))
    def replace(value):
        if isinstance(value, str):
            return pattern.sub(lambda m: replacements[m.group()], value)
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value
    cloned = replace(spec)
    cloned["id"] = "scene-" + event_id
    cloned["name"] = name or "新场景 " + event_id
    for item in cloned["event"]["settings"]:
        if item["kind"] == "name":
            item["value"] = cloned["name"]
    cloned["creation"] = {"sourceEvent": old, "tableTargets": [], "resourceTargets": []}
    for original, target in zip(spec["tiers"], cloned["tiers"]):
        target["sourceQuest"] = original["quest"]
    for original, target in zip(spec["tables"], cloned["tables"]):
        for before, after in zip(original["entries"], target["entries"]):
            if before["path"] != after["path"]:
                cloned["creation"]["tableTargets"].append({"logical": target["logical"], "path": after["path"]})
    for before, after in zip(spec["resources"], cloned["resources"]):
        if before["logical"] != after["logical"]:
            cloned["creation"]["resourceTargets"].append(after["logical"])
    cloned["provenance"] = {"kind": "scene-clone", "sourceEvent": old, "version": spec["sourceVersion"],
                             "note": "完整逻辑图独立命名，沿用当前视图的美术及 BGM；ID 未预留，预览与生成重新防撞。"}
    validate_spec(cloned)
    return cloned

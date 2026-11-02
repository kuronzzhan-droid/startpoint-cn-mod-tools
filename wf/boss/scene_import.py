"""Read-only import of the Hell Pumpkin encounter into portable scene specs."""
from __future__ import annotations

import re
import wf_quest_lib as codec
from .schema import iter_leaves, parse_rows
from .scene_spec import logical_path
from .scene_types import AE, AQ, CAS, CONTINUE_PREFIX
from wf.tools.boss.five_boss_v2 import decode_amf

GBS = "master/battle/boss/general_boss_state.orderedmap"
GFS = "master/battle/boss/funnel/general_funnel_state.orderedmap"
TABLES = [AE, AQ, CAS, "master/quest/event/event_list.orderedmap", "master/item/item.orderedmap",
          "master/shop/event_item_shop.orderedmap", "master/reward/score_reward.orderedmap",
          "master/reward/rare_score_reward.orderedmap", "master/asset/bgm_asset.orderedmap",
          *["master/battle/" + name + ".orderedmap" for name in (
              "boss/general_boss", "boss/general_boss_state", "boss/general_boss_variable",
              "boss/boss_level", "boss/general_enemy_watch", "boss/funnel/general_funnel",
              "boss/funnel/general_funnel_state", "boss/funnel/general_funnel_variable",
              "boss/funnel_level", "field", "field_data", "zone",
              "yakumono/direct_instant_item", "item/executable_instant_item", "item/executable_instant_item_level")]]
PATH = re.compile(r"(?:battle|bgm|quest|item|character)/[a-zA-Z0-9_$/.-]+")


def walk(value, path=()):
    yield path, value
    if isinstance(value, (dict, list)):
        for key, child in (value.items() if isinstance(value, dict) else enumerate(value)):
            yield from walk(child, (*path, key))


def owned(path, text):
    return any(k.startswith(("mod_hp_", "300097", "97300", "10009701", "continue_cost_300097")) or
               "mod/hell_pumpkin/" in k for k in path)


def setting(identifier, kind, value, binding):
    return {"id": identifier, "kind": kind, "value": value, "bindings": [binding]}


def column(table, path, row, index, name, kind="parameter"):
    return setting(name, kind, row[index], {"table": table, "path": list(path), "column": index})


def _resource_candidates(path):
    if path.endswith(".amf3.deflate"):
        return [path]
    if path.startswith("battle/action/"):
        return [path + ".action.dsl.amf3.deflate"]
    if path.startswith("battle/terrain/"):
        return [path + ".amf3.deflate"]
    return [path + suffix for suffix in (".parts.amf3.deflate", ".atlas.amf3.deflate", ".timeline.amf3.deflate")]


def _resources(loader, tables):
    pending, seen, resources, missing = [], set(), {}, []
    def enqueue(value):
        for _, node in walk(value):
            if isinstance(node, str):
                pending.extend(p for p in PATH.findall(node) if "/mod/hell_pumpkin/" in p and p.startswith("battle/"))
    enqueue(tables)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        found = False
        for logical in _resource_candidates(name):
            try:
                raw = loader(logical)
            except (FileNotFoundError, KeyError):
                continue
            value = decode_amf(raw)
            found = True
            resources[logical] = {"logical": logical, "encoding": "amf3", "value": value}
            enqueue(value)
        if not found and name.startswith(("battle/action/", "battle/terrain/")):
            missing.append(name)
    if missing:
        raise ValueError("场景逻辑资源引用缺失：" + ", ".join(sorted(missing)))
    return [resources[k] for k in sorted(resources)]


def _scene_settings(spec):
    phases = {p: {"id": p, "name": name, "settings": []} for p, name in
              (("p1", "南瓜潮"), ("p2", "技能盾"), ("p3", "万圣狂欢"))}
    for resource in spec["resources"]:
        logical = resource["logical"]
        for path, node in walk(resource["value"]):
            if not isinstance(node, list) or not node or not isinstance(node[0], str):
                continue
            command = node[0]
            binding = {"resource": logical, "path": list(path)}
            identifier = logical.rsplit("/", 1)[-1].split(".")[0] + ":" + "/".join(map(str, path))
            # Exact emitted program names from the old builder's phase entry
            # functions; filenames outside this map do not establish a phase.
            program = logical.rsplit("/", 1)[-1].split(".")[0]
            phase = {"hp_bgm_p1": "p1", "hp_bgm_p2": "p2", "hp_awaken": "p2",
                     "hp_r_bgm": "p3", "hp_r_field": "p3"}.get(program)
            if command == "ChangeBgm" and len(node) > 1 and phase:
                phases[phase]["settings"].append(setting(identifier, "bgm", node[1], {**binding, "path": [*path, 1]}))
            elif command == "ChangeFieldAssets" and phase:
                for i in range(1, len(node)):
                    phases[phase]["settings"].append(setting(identifier + f":{i}", "field", node[i], {**binding, "path": [*path, i]}))
            elif command == "SpawnFunnel" and len(node) > 1:
                spec["summons"].append(setting(identifier, "summon", node[1], {**binding, "path": [*path, 1]}))
            elif command in {"StartModifierField", "CreateRatioAttack", "AddSkillPoint", "SubtractSkillPoint"}:
                spec["mechanisms"].append(setting(identifier, "mechanism", node, binding))
    spec["phases"] = list(phases.values())
    for table in spec["tables"]:
        for entry in table["entries"]:
            path = entry["path"]
            rows = parse_rows(entry["value"])
            if not rows:
                continue
            row = rows[0]
            if table["logical"] in {GBS, GFS} and len(row) > 23 and row[22] in {"0", "1", "2", "3"}:
                spec["trials"].append(column(table["logical"], path, row, 23, "/".join(path), "threshold"))
            elif table["logical"] == GBS and len(row) > 30 and "fv1" in path[-1]:
                spec["trials"].append(column(GBS, path, row, 47, "/".join(path) + ":fever-time", "time"))


def import_hell_pumpkin(loader, version):
    """Import actual chain data; this proves roundtrip, never historical-build equivalence."""
    tables = []
    for logical in TABLES:
        try:
            tree = codec.parse_node(loader(logical))
        except FileNotFoundError as exc:
            if logical == CAS:
                continue
            raise ValueError("导入场景缺少必需表：" + logical) from exc
        entries = [{"path": list(path), "value": value} for path, value in iter_leaves(tree) if owned(path, value)]
        if entries:
            tables.append({"logical": logical, "entries": entries})
    spec = {"schema": "wf-boss-scene/1", "id": "hell-pumpkin", "name": "地狱南瓜",
            "sourceVersion": version, "tables": tables, "resources": _resources(loader, tables),
            "event": {"id": "300097", "settings": []}, "tiers": [], "phases": [],
            "summons": [], "mechanisms": [], "trials": [], "shops": [], "drops": [], "requirements": [],
            "provenance": {"kind": "current-view-import", "version": version,
                "note": "从当前视图导入的可编辑规格。默认往返不等于旧构建器复现；旧构建产物差异应独立审计。"}}
    continue_rows = {}
    for table in tables:
        logical = table["logical"]
        for entry in table["entries"]:
            path, row = entry["path"], parse_rows(entry["value"])[0]
            if logical == AE and path == ["300097"]:
                spec["event"]["settings"] = [column(logical, path, row, 0, "event-code"),
                                                column(logical, path, row, 2, "event-name", "name")]
            elif logical == AQ and path[0] == "300097":
                choices = [(2, "name"), (105, "hp"), (108, "attack"), (112, "level"),
                           (115, "field"), (116, "bgm"), (117, "time")]
                spec["tiers"].append({"id": path[-1], "name": row[2], "quest": row[0],
                    "settings": [column(logical, path, row, c, kind, kind) for c, kind in choices]})
            elif logical == CAS and len(path) == 1 and path[0].startswith(CONTINUE_PREFIX):
                continue_rows[path[0]] = row
            elif logical == "master/shop/event_item_shop.orderedmap":
                # Explicit full-row binding via each column retains unknown native columns.
                spec["shops"].append({"id": "/".join(path), "settings":
                    [column(logical, path, row, c, f"c{c}", "shop") for c in range(1, len(row))]})
            elif logical in {"master/reward/score_reward.orderedmap", "master/reward/rare_score_reward.orderedmap"}:
                spec["drops"].append({"id": logical.rsplit("/", 1)[-1] + ":" + "/".join(path), "settings":
                    [column(logical, path, row, c, f"c{c}", "reward") for c in range(len(row))]})
    for tier in spec["tiers"]:
        continue_key = CONTINUE_PREFIX + tier["quest"]
        if continue_key in continue_rows:
            tier["settings"].append(column(CAS, [continue_key], continue_rows[continue_key], 0, "continue-cost"))
    _scene_settings(spec)
    if len(spec["tiers"]) != 5:
        raise ValueError("当前视图缺少地狱南瓜活动 300097 的完整五档；未用合成数据代替")
    return spec

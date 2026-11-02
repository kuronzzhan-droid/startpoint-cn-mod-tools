"""Build Advent server JSON candidates in memory; never write the input mirror."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .edit_state import merge_keys, digest
from .edit_bytes import append_values
from .scene_import import AQ
from .scene_server_projection import (ITEM, RARE, SCORE, SHOP, changed_projection, number,
                                      original_rows, product, quest, reward, rows)
from .scene_types import CAS, CONTINUE_PREFIX, parse_continue_cost
from wf.rules.catalog import result

FILES = ("advent_event_quest.json", "score_reward_cnmod.json", "rare_score_reward_cnmod.json",
         "event_item_shop.json", "event_item_shop_id_map.json", "item_ids.json", "item_lookup_cnmod.json")
CONTINUE_COST = "continue_cost.json"


def _load(root):
    originals, current = {}, {}
    for name in FILES:
        target = (root / "assets" / name).resolve()
        if not target.is_relative_to(root):
            raise ValueError("服务端镜像文件越过配置目录")
        raw = target.read_bytes()
        originals["assets/" + name] = raw
        current[name] = json.loads(raw)
        expected = list if name == "item_ids.json" else dict
        if not isinstance(current[name], expected):
            raise ValueError("服务端镜像表的根类型不符合契约")
    cc_target = (root / "assets" / CONTINUE_COST).resolve()
    if not cc_target.is_relative_to(root):
        raise ValueError("服务端镜像文件越过配置目录")
    if cc_target.exists():
        raw = cc_target.read_bytes()
        originals["assets/" + CONTINUE_COST] = raw
        current[CONTINUE_COST] = json.loads(raw)
        if not isinstance(current[CONTINUE_COST], dict):
            raise ValueError("服务端镜像表的根类型不符合契约")
    return originals, current


def _project(state, spec, current):
    event, creating = spec["event"]["id"], bool(spec.get("creation"))
    if not event.isdigit() or creating and spec["creation"].get("sourceEvent") == event:
        raise ValueError("新活动需要不同于只读母本的数字 event ID")
    updates = {name: {} for name in FILES if name != "item_ids.json"}
    drift, desired = [], []

    def project(filename, key, original, candidate, *, before=None):
        source = current[filename].get(key) if before is None else before
        value = changed_projection(source, original, candidate, target=f"{filename}/{key}",
                                   drift=drift, creating=creating)
        updates[filename][key] = value
        desired.append((filename, key, value))
        return value

    candidates = {path[-1]: row for path, row in rows(state, AQ, {event})}
    originals = {path[-1]: row for path, row in original_rows(spec, AQ, {event})}
    for tier in spec["tiers"]:
        qid = tier["quest"]
        row, original = candidates[tier["id"]], originals[tier["id"]]
        if row[0] != qid or not qid.isdigit():
            raise ValueError("五档 quest ID 与客户端任务行不一致")
        if creating and qid in current["advent_event_quest.json"]:
            raise ValueError("新活动 quest ID 已被服务端占用")
        mother = tier.get("sourceQuest") if creating else qid
        if creating and (not isinstance(mother, str) or not mother.isdigit()
                         or not mother.startswith(spec["creation"]["sourceEvent"])
                         or len(mother) != len(spec["creation"]["sourceEvent"]) + 3):
            raise ValueError("服务端只读母本 quest 必须属于 sourceEvent")
        before = current["advent_event_quest.json"].get(mother)
        if not isinstance(before, dict):
            raise ValueError("缺少活动任务服务端只读母本：" + str(mother))
        candidate = quest(row)
        if creating:
            candidate = {**copy.deepcopy(before), **candidate}
        project("advent_event_quest.json", qid, quest(original), candidate, before=before)
    for filename, logical in (("score_reward_cnmod.json", SCORE), ("rare_score_reward_cnmod.json", RARE)):
        keys = {entry["path"][0] for table in spec["tables"] if table["logical"] == logical for entry in table["entries"]}
        for key in keys:
            if creating and key in current[filename]:
                raise ValueError("新活动掉落组已被服务端占用")
            before = reward(original_rows(spec, logical, {key}), rare=logical == RARE)
            after = reward(rows(state, logical, {key}), rare=logical == RARE)
            project(filename, key, before, after)
    score_keys = set(current["score_reward_cnmod.json"]) | set(updates["score_reward_cnmod.json"])
    rare_keys = set(current["rare_score_reward_cnmod.json"]) | set(updates["rare_score_reward_cnmod.json"])
    for row in candidates.values():
        if row[76] not in state.table(SCORE) or row[76] not in score_keys:
            raise ValueError("活动五档引用的掉落组未在客户端和服务端同时登记")
    for entries in updates["score_reward_cnmod.json"].values():
        for entry in entries:
            if entry.get("type") == 1 and (str(entry["id"]) not in state.table(RARE) or str(entry["id"]) not in rare_keys):
                raise ValueError("活动掉落引用的稀有池未在客户端和服务端同时登记")
    shop = copy.deepcopy(current["event_item_shop.json"].get("0", {}))
    if not isinstance(shop, dict) or creating and event in shop:
        raise ValueError("活动商店分类错误或新活动 ID 已占用")
    products = copy.deepcopy(shop.get(event, {}))
    if not isinstance(products, dict):
        raise ValueError("活动商店商品必须是对象")
    product_ids = {item["id"] for item in spec["shops"]}
    selected = rows(state, SHOP, product_ids)
    baseline = {path[0]: row for path, row in original_rows(spec, SHOP, product_ids)}
    if {path[0] for path, _ in selected} != product_ids:
        raise ValueError("活动商品列表缺少客户端同号行")
    candy = set()
    for path, row in selected:
        pid = path[0]
        if creating and pid in current["event_item_shop_id_map.json"]:
            raise ValueError("新活动商品 ID 已被服务端占用")
        after, original = product(row, event), product(baseline[pid], event)
        products[pid] = changed_projection(products.get(pid), original, after,
            target=f"event_item_shop.json/0/{event}/{pid}", drift=drift, creating=creating)
        mapping = {"eventType": 0, "eventId": number(event)}
        existing = current["event_item_shop_id_map.json"].get(pid)
        if not creating and existing is not None and existing != mapping:
            raise ValueError("现有商品 ID 映射不指向当前活动")
        updates["event_item_shop_id_map.json"][pid] = mapping
        candy.update(str(item["id"]) for item in after["costs"])
    shop[event] = products
    updates["event_item_shop.json"] = {"0": shop}
    names = {path[0]: row[2] for path, row in rows(state, ITEM, candy)}
    old_names = {path[0]: row[2] for path, row in original_rows(spec, ITEM, candy)}
    if set(names) != candy:
        raise ValueError("活动商店币种缺少客户端道具行")
    for item in candy:
        if creating and (number(item) in current["item_ids.json"] or item in current["item_lookup_cnmod.json"]):
            raise ValueError("新活动币种 ID 已被服务端占用")
        project("item_lookup_cnmod.json", item, old_names.get(item), names[item])
    continue_keys = {CONTINUE_PREFIX + tier["quest"] for tier in spec["tiers"]}
    for table in spec["tables"]:
        if table["logical"] == CAS:
            for entry in table["entries"]:
                if (len(entry["path"]) == 1 and entry["path"][0].startswith(CONTINUE_PREFIX)
                        and entry["path"][0] not in continue_keys):
                    raise ValueError("规格包含不属于当前活动五档的 continue_cost 键：" + entry["path"][0])
    client_continue = {path[0]: row for path, row in rows(state, CAS, continue_keys)}
    base_continue = {path[0]: row for path, row in original_rows(spec, CAS, continue_keys)}
    known_server_items = {str(item) for item in current["item_ids.json"]} | candy
    parsed_continue = {}
    for key, row in client_continue.items():
        if len(row) != 1:
            raise ValueError("续战消耗行必须是单列 CSV：" + key)
        parsed = parse_continue_cost(row[0], key)
        item_key = str(parsed["item_id"])
        if item_key not in state.table(ITEM) or item_key not in known_server_items:
            raise ValueError("活动续战消耗道具未在客户端和服务端同时登记：" + item_key)
        parsed_continue[key] = parsed
    if CONTINUE_COST in current:
        updates[CONTINUE_COST] = {}
        for tier in spec["tiers"]:
            qid = tier["quest"]
            ckey = CONTINUE_PREFIX + qid
            if creating and qid in current[CONTINUE_COST]:
                raise ValueError("新活动续战消耗 quest ID 已被服务端占用")
            if ckey in parsed_continue:
                orig_row = base_continue.get(ckey)
                orig_cc = parse_continue_cost(orig_row[0], ckey) if orig_row and len(orig_row) == 1 else None
                mother_qid = tier.get("sourceQuest") if creating else qid
                before_cc = current[CONTINUE_COST].get(mother_qid)
                if before_cc is not None and not isinstance(before_cc, dict):
                    raise ValueError("服务端 continue_cost 条目必须是对象：" + str(mother_qid))
                project(CONTINUE_COST, qid, orig_cc, parsed_continue[ckey], before=before_cc)
    return updates, candy, drift, desired, parsed_continue


def server_candidate(state, spec, server_dir):
    if server_dir is None:
        return {}, {}, [result("scene.server", "待验证", "未配置只读服务端镜像，不能生成完整活动/商店/掉落交付", blocking=True)]
    try:
        root = Path(server_dir).resolve()
        originals, current = _load(root)
    except (OSError, ValueError, TypeError):
        return {}, {}, [result("scene.server", "待验证", "服务端镜像输入不完整或 JSON 结构错误", blocking=True)]
    try:
        updates, candy, drift, desired, parsed_continue = _project(state, spec, current)
        files = {}
        for name, values in updates.items():
            target = "assets/" + name
            output = merge_keys(originals[target], values)
            if output != originals[target]:
                files[target] = output
        target = "assets/item_ids.json"
        output = append_values(originals[target], [number(item) for item in sorted(candy)])
        if output != originals[target]:
            files[target] = output
        for filename, key, expected in desired:
            actual = json.loads(files.get("assets/" + filename, originals["assets/" + filename]))
            if actual.get(key) != expected:
                raise ValueError("活动经济候选 JSON 回读不匹配")
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        return {}, {key: digest(raw) for key, raw in originals.items()}, [
            result("scene.server", "问题", "活动/商店/掉落候选校验失败：" + str(exc), blocking=True)]
    checks = [result("scene.server", "满足", "已核对活动五档及生成 JSON 回读；只生成内存候选，镜像未写入"),
              result("scene.server-shop-sync", "满足", "活动商品、Advent ID 映射、币种道具及名称投影闭合；保留未编辑历史字段"),
              result("scene.server-reward-sync", "满足", "五档掉落组与稀有池在客户端、服务端同时存在；编辑字段按已核实投影同步")]
    if CONTINUE_COST not in current:
        checks.append(result("scene.server-continue-cost", "待验证",
                             "服务端镜像缺少 assets/continue_cost.json，未生成服务端续战消耗候选", blocking=False))
    else:
        creating = bool(spec.get("creation"))
        missing_cc = [tier["quest"] for tier in spec["tiers"]
                      if (CONTINUE_PREFIX + tier["quest"]) not in parsed_continue
                      and (tier.get("sourceQuest") if creating else tier["quest"]) in current[CONTINUE_COST]]
        if missing_cc:
            checks.append(result("scene.server-continue-cost", "待验证",
                                 "服务端存在续战消耗配置但客户端规格未包含对应 continue_cost 键：" + ", ".join(missing_cc),
                                 blocking=False))
        elif parsed_continue:
            checks.append(result("scene.server-continue-cost", "满足",
                                 "五档续战消耗已与客户端 custom_ability_string 及 assets/continue_cost.json 对齐"))
        else:
            checks.append(result("scene.server-continue-cost", "满足",
                                 "当前活动未声明自定义续战消耗，assets/continue_cost.json 保持原值"))
    if drift:
        checks.append(result("scene.server-baseline", "待验证", "已有客户端/服务端投影漂移保持原值；本次只同步明确编辑字段", differences=drift))
    return files, {key: digest(value) for key, value in originals.items()}, checks

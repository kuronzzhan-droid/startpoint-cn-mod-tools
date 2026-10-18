"""Boss entry, route, time and server/client identity checks."""
from __future__ import annotations

import json

from .boss_common import CandidateView, EMPTY, cell, cells, fields, leaves
from .catalog import result


def choice_check(context):
    count = context.get("choice_count")
    if count is None:
        return result("boss.choice-folder", "未执行", "未提供选门设计意图，不能把同轮 quest 自动解释为并列选择")
    if count <= 1:
        return result("boss.choice-folder", "不适用", "未设计并列选门")
    valid = context.get("choice_level") == "folder"
    return result("boss.choice-folder", "满足" if valid else "问题",
                  "并列选门必须建在 folder 层；quest 同轮只显示首个未清关卡", blocking=not valid)


def time_check(document, context):
    if context.get("custom_content") is not True:
        return result("boss.custom-time", "未执行", "未声明为本次自制内容，不将官方活动期间强制改写为自制规范")
    quest = document.get("quest", {})
    times = [("quest", cell(quest, 5), cell(quest, 6))]
    entrance = document.get("entrance") or {}
    event = entrance.get("event")
    if event:
        times.append(("hard_multi_event", cell(event, 23), cell(event, 24)))
    issues = [f"{label}: start={start!r}, end={end!r}" for label, start, end in times
              if start != "2000-01-01 00:00:00" or end not in EMPTY]
    return result("boss.custom-time", "问题" if issues else "满足",
                  "自制内容期间应为 2000-01-01 00:00:00 至 (None)，不依赖当前服务端时间",
                  blocking=bool(issues), issues=issues)


def prerequisite_check(document, context=None):
    quest = document.get("quest", {})
    if quest.get("kind") not in {"hard_multi", "hard_multi_event"}:
        return result("boss.visible-prerequisites", "不适用", "共同决战无前置规则不外推其它副本")
    if not (context or {}).get("custom_content"):
        return result("boss.visible-prerequisites", "未执行", "未声明自制共同决战；官方活动的合法解锁条件不适用无前置规范")
    row = cells(quest)
    if len(row) < 17:
        return result("boss.visible-prerequisites", "未执行", "缺少共同决战原始前置列 c7–c16")
    issues = [{"column": i, "value": row[i]} for i in range(7, 17) if row[i] not in EMPTY]
    return result("boss.visible-prerequisites", "问题" if issues else "满足",
                  "共同决战 c7–c16 不设前置，避免活动页隐藏", blocking=bool(issues), issues=issues)


def both_route_check(document, view, context):
    quest = document.get("quest", {})
    enabled = str(cell(quest, 122)).lower() == "true" if quest.get("kind") == "boss_battle" else False
    requested = context.get("both_boss") is True
    if not enabled and not requested:
        return result("boss.both-route", "不适用", "此关没有启用 BothBoss 路由")
    if quest.get("kind") != "boss_battle" or context.get("both_boss_purpose") == "simultaneous":
        return result("boss.both-route", "问题", "BothBoss 仅为 boss_battle 两轮隐藏关路由；同场多 boss 由 zone c22/槽位控制",
                      blocking=True)
    if view is None:
        return result("boss.both-route", "未执行", "需候选 both_boss_group/map 和隐藏 quest 行核对路由闭合")
    source = CandidateView(view)
    groups = source.table("master/quest/both_boss/both_boss_group.orderedmap") or {}
    maps = source.table("master/quest/both_boss/both_boss_map.orderedmap") or {}
    quests = source.table("master/quest/boss_battle_quest.orderedmap") or {}
    identity = str(quest.get("id", cell(quest, 0)))
    group = groups.get(identity)
    if group is None:
        return result("boss.both-route", "问题", f"BothBoss 入口 {identity} 缺少 group", blocking=True)
    map_ids = [value for value in str(cell(group, 1, "")).split(",") if value not in EMPTY]
    quest_rows = {row[0]: row for _, row in leaves(quests) if row}
    issues, has_fallback = [], False
    for map_id in map_ids:
        row = cells(maps.get(str(map_id)))
        if len(row) < 15:
            issues.append(f"map {map_id} 缺失或不满 15 列")
            continue
        targets = row[11:15]
        has_fallback |= all(value not in EMPTY for value in targets[2:])
        for target in targets:
            if target in EMPTY:
                continue
            hidden = quest_rows.get(target)
            if hidden is None or str(cell(hidden, 123)).lower() != "true":
                issues.append(f"map {map_id} 引用 {target} 缺失或不是隐藏 boss_battle quest")
    if not map_ids:
        issues.append("BothBoss group 无 map")
    if not has_fallback:
        issues.append("BothBoss map 缺少完整 default 两轮兜底")
    return result("boss.both-route", "问题" if issues else "满足", "检查两轮隐藏关路由与 default 兜底；不把路由解释为同屏或共血",
                  blocking=bool(issues), issues=issues)


def reward_check(view, server_changes, server_before):
    from wf.check_delivery import reward_results
    if view is None or server_changes is None:
        return reward_results({"findings": []})
    from wf.deliver.prepush_base import Report
    from wf.deliver.prepush_companion import check_server_rewards
    from wf.deliver.prepush_rewards import SERVER_REWARD_PATHS
    if not set(server_changes) & set(SERVER_REWARD_PATHS):
        return result("delivery.reward-keys", "不适用", "本次没有服务端 score_reward/rare_score_reward 变更")
    report = Report(set())
    evidence = check_server_rewards(CandidateView(view), report, server_changes, server_before or {})
    return reward_results({"findings": [item.__dict__ for item in report.items], "companion_reward_keys": evidence})


def collision_check(context):
    if "new_ids" not in context or "existing_ids" not in context:
        return result("boss.unique-ids", "未执行", "未提供新增键与来源占用键；编辑已有键不视为撞号")
    duplicates = []
    for table, values in context["new_ids"].items():
        values = [str(value) for value in values]
        occupied = {str(value) for value in context["existing_ids"].get(table, [])}
        if len(values) != len(set(values)):
            duplicates.append(f"{table} 本次新增键重复")
        duplicates.extend(f"{table}/{key}" for key in values if key in occupied)
    return result("boss.unique-ids", "问题" if duplicates else "满足", "新增 quest/zone/入口键与来源占用键对照",
                  blocking=bool(duplicates), collisions=duplicates)


def shop_check(document, view, server_changes, server_before):
    shops = document.get("shops")
    if shops is None:
        return result("boss.shop-sync", "未执行", "未提供商店关联")
    if not shops:
        return result("boss.shop-sync", "不适用", "此副本没有关联领主币商店商品")
    paths = ("assets/boss_coin_shop.json", "assets/boss_coin_shop_item_category_map.json")
    files = {**(server_before or {}), **(server_changes or {})}
    if view is None or any(path not in files for path in paths):
        return result("boss.shop-sync", "未执行", "需客户端主表、服务端商品与 category_map 三份实际输入")
    server, category_map = [json.loads(files[path] or b"{}") for path in paths]
    table = CandidateView(view).table("master/shop/boss_coin_shop.orderedmap") or {}
    product_ids = {str(shop.get("id")) for shop in shops if isinstance(shop, dict) and shop.get("row")}
    categories = {str(shop.get("id")) for shop in shops if shop.get("products") is not None}
    for category in categories:
        product_ids.update(map(str, server.get(category, {})))
    for shop in shops:
        product_ids.update(str(product.get("id", product.get("path", [None])[0]))
                           for product in shop.get("products", []))
    if not product_ids:
        return result("boss.shop-sync", "待验证", "已读商店关联，但缺少商品 ID，未执行三处逐键核对")
    issues = []
    for identity in sorted(product_ids):
        row = cells(table.get(identity))
        if not row:
            issues.append(f"商品 {identity} 缺客户端 boss_coin_shop 行（C8601）")
            continue
        category = str(row[0])
        if identity not in server.get(category, {}):
            issues.append(f"商品 {identity} 缺服务端分类 {category} 商品行")
        if str(category_map.get(identity)) != category:
            issues.append(f"商品 {identity} category_map 不指向分类 {category}")
    return result("boss.shop-sync", "问题" if issues else "满足", "关联商品客户端、服务端与 category_map 三处逐键核对",
                  blocking=bool(issues), checked_products=len(product_ids), issues=issues)

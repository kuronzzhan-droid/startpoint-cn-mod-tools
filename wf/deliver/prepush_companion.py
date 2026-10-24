"""道具伴随表检查。"""
from __future__ import annotations

from .prepush_base import *
from .prepush_rewards import (SERVER_REWARD_PATHS, REWARD_TABLES, client_rewards,
                              merged_rewards, reward_groups, reward_rows)

ITEM = "master/item/item.orderedmap"
ITEM_QUEST_SEARCH = "master/search/item_quest_search.orderedmap"
EII = "master/battle/item/executable_instant_item.orderedmap"
EII_LEVEL = "master/battle/item/executable_instant_item_level.orderedmap"


def check_server_rewards(view, rep, server_changes, server_before):
    """Validate changed reward files against the actual candidate client tables.

    A row is identified by (table, group, position). Existing rows remain WARN,
    including edited rows; newly introduced identities are ERROR. The baseline
    includes both base and _cnmod files so overrides do not invent new rows.
    """
    targets = sorted(set(server_changes) & set(SERVER_REWARD_PATHS))
    evidence = {"executed": True, "server_targets": targets, "checked_rows": 0,
                "server_baseline_complete": all(p in server_before for p in SERVER_REWARD_PATHS)
                if targets else True}
    if not targets:
        return evidence
    before = dict(server_before)
    after = {**before, **server_changes}
    clients = {name: client_rewards(view, name) for name in REWARD_TABLES}
    effective = {name: merged_rewards(after, name) for name in REWARD_TABLES}
    previous = {name: merged_rewards(before, name)[0] for name in REWARD_TABLES}

    def require(name, group, position, level, target, origin):
        group = str(group)
        client_group = clients[name].get(group)
        if position is None:
            present = isinstance(client_group, dict) and bool(client_group)
        else:
            present = isinstance(client_group, dict) and position in client_group
        if not present:
            key = group if position is None else f"{group}/{position}"
            rep.add(level, "companion", f"companion.reward_key:{target}:{origin}:{name}:{key}",
                    f"服务端 {target} 奖励行 {origin} 引用的客户端 {name} 键 {key} 不存在",
                    ["候选视图包含本次客户端包和 _cnmod 合并表；存量行 WARN，新增行 ERROR"])

    for name in REWARD_TABLES:
        groups, sources = effective[name]
        relevant = set()
        for target in targets:
            if target in (f"assets/{name}.json", f"assets/{name}_cnmod.json"):
                relevant.update(reward_groups(server_changes[target], target))
                relevant.update(reward_groups(before.get(target), target))
        for group in sorted(relevant):
            if group not in groups:
                continue
            target = sources[group]
            # A base edit masked by an unchanged _cnmod group has no runtime change.
            if target not in targets and groups[group] == previous[name].get(group):
                continue
            old_rows = reward_rows(previous[name].get(group, []), name)
            for position, entry in reward_rows(groups[group], name).items():
                evidence["checked_rows"] += 1
                level = "WARN" if position in old_rows else "ERROR"
                origin = f"{group}/{position}"
                require(name, group, position, level, target, origin)
                if name == "score_reward" and entry.get("type") == 1:
                    rare_group = entry.get("id")
                    if rare_group is None:
                        raise ValueError(f"{target}:{origin}: rare pool lacks id")
                    require("rare_score_reward", rare_group, None, level, target, origin)
                    # The server emits rare index + 1, not just the group id.
                    rare_entries = effective["rare_score_reward"][0].get(str(rare_group), [])
                    for rare_position in reward_rows(rare_entries, "rare_score_reward"):
                        require("rare_score_reward", rare_group, rare_position, level, target, origin)
    return evidence


def check_companion(args, view: View, old: View | None, rep: Report, allow_iqs: set[str]):
    items = view.table(ITEM)
    if items is None:
        rep.add("WARN", "companion", "companion.item.skipped", "视图里没有 item 表,道具伴随检查跳过")
    else:
        old_items = set(old.table(ITEM) or {}) if old is not None else None
        def is_new(k):
            return old_items is not None and k not in old_items
        ids_path = args.server_dir / "assets" / "item_ids.json"
        if ids_path.is_file():
            ids = {str(x) for x in json.loads(ids_path.read_text("utf-8"))}
            for k in sorted(set(items) - ids, key=lambda s: (len(s), s)):
                name = row(items[k])[2] if isinstance(items[k], str) and len(row(items[k])) > 2 else ""
                rep.add("ERROR" if (is_new(k) or old_items is None) else "WARN", "companion",
                        f"companion.item_ids:{k}",
                        f"道具 {k}({name})在客户端 item 表里,但不在服务端 assets/item_ids.json")
        iqs = view.table(ITEM_QUEST_SEARCH)
        if iqs is not None and old_items is not None:
            for k in sorted(set(items) - set(iqs) - old_items - allow_iqs, key=lambda s: (len(s), s)):
                name = row(items[k])[2] if isinstance(items[k], str) and len(row(items[k])) > 2 else ""
                rep.add("WARN", "companion", f"companion.item_quest_search:{k}",
                        f"新道具 {k}({name})没有 item_quest_search 行(获取途径页空白)")
        elif iqs is not None and args.custom_item_min is not None:
            for k in sorted(set(items) - set(iqs) - allow_iqs, key=lambda s: (len(s), s)):
                if k.isdigit() and int(k) >= args.custom_item_min:
                    name = row(items[k])[2] if isinstance(items[k], str) and len(row(items[k])) > 2 else ""
                    rep.add("WARN", "companion", f"companion.item_quest_search:{k}",
                            f"自制道具 {k}({name})没有 item_quest_search 行(获取途径页空白)")
    eii, lvl = view.table(EII), view.table(EII_LEVEL)
    if eii is None or lvl is None:
        rep.notes.append("executable_instant_item(_level) 不在视图里,C8601 检查跳过")
    else:
        for k in sorted(set(eii) - set(lvl)):
            rep.add("ERROR", "companion", f"companion.eii_level:{k}",
                    f"即时道具 {k} 没有 executable_instant_item_level 行(C8601)")



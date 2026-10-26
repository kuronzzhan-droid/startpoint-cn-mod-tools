"""补丁构造的表解析器范围；共享运行时支持不代表各 master 表均能解析。"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

import wfx_registry

# 表范围与解析器 capability 由 wfx_registry.json 的 patch_content_kinds 派生（唯一真源），
# 派生结果与此前的手写表逐项相同，另补 422 盲区（见下）；tests/test_wfx_registry.py 钉住。
#
# kyubi-fever-ratio/patch.py 的唯一 master parser 目标为
# AbilityValues$/parseAt47。Leader/AbilitySoul/Equipment/Ex 都是独立解析器。
# 未列出的构造沿用原校验规则；不要据此扩大其他补丁的支持范围。
# 422 由 client-patch/dash-parameter 只扩 AbilityValues$/parseAt109：队长/魂/武器强化/EX 表写 422
# 实机 C7050（记忆 wf-dash-parameter-leader-table-trap）。此前 422 未登记 ⇒ 对任何表都放行（盲区）。
# 423 另由 client-patch/equipment-rules（R3）扩到 EquipmentEnhancementAbilityValues$/parseAt109
# 与 AbilitySoulValues$/parseAt106；424 没有扩展，装备两表仍 C7050。
PATCH_PARSER_TABLES = wfx_registry.patch_parser_tables()
# 表解析器扩展自身的 capability，与构造的运行时 capability（CLIENT_PATCH_CONTENT_KINDS）并列：
# 1047 客户端已有 gauge-gain-rules-v1，但读到装备两表的 423 仍在上述 parseAt 抛 C7050，
# 必须同时装有 equipment-rules APK 声明的 equipment-gauge-gain-rules-v1。
EQUIPMENT_GAUGE_CAP = "equipment-gauge-gain-rules-v1"
PATCH_PARSER_CAPABILITIES = wfx_registry.patch_parser_capabilities()
_PARSER_CLASSES = {
    "ability": "AbilityValues",
    "leader_ability": "LeaderAbilityValues",
    "ability_soul": "AbilitySoulValues",
    "equipment_enhancement_ability": "EquipmentEnhancementAbilityValues",
    "ex_ability": "ExAbilityValues",
}


def patch_parser_supported(table: str, block: str, value: str) -> bool:
    """已登记的补丁构造必须属于其实际修改的表解析器。"""
    allowed = PATCH_PARSER_TABLES.get((block, value))
    return allowed is None or table in allowed


def patch_parser_scope_problems(
    table: str, row: list[str], blocks: Mapping[str, int], parsed_blocks: Iterable[str],
) -> list[str]:
    """仅检查调用方确认当前触发模式会解析的块；忽略未读取的残值。"""
    problems = []
    for block in parsed_blocks:
        column = int(blocks[block])
        value = (row[column] if column < len(row) else "").strip()
        if patch_parser_supported(table, block, value):
            continue
        parser = _PARSER_CLASSES.get(table, table) + f"$/parseAt{column}"
        allowed = ", ".join(sorted(PATCH_PARSER_TABLES[block, value]))
        problems.append(
            f"{table} c{column} {block}={value}: {parser} 未被当前补丁扩展，"
            f"该构造仅支持表 {allowed}（客户端 C7050）"
        )
    return problems


def patch_parser_capabilities(
    table: str, row: list[str], blocks: Mapping[str, int], parsed_blocks: Iterable[str],
) -> list[str]:
    """解析器扩展要求的 capability；范围同 patch_parser_scope_problems，只看会解析的块。"""
    needed = []
    for block in parsed_blocks:
        column = int(blocks[block])
        value = (row[column] if column < len(row) else "").strip()
        capability = PATCH_PARSER_CAPABILITIES.get((block, value), {}).get(table)
        if capability is not None and capability not in needed:
            needed.append(capability)
    return needed

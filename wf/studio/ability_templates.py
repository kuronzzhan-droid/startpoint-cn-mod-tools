"""Enum-backed row templates: absence of precedent is evidence, not a ban."""
from __future__ import annotations

import wf_describe
import wf_quest_lib as codec
from wf.balance.rows import TABLES, WIDTHS, split_leaf
from wf.rules.catalog import result
from wf.rules.instant_content import fill_instant_content_defaults
from wf.view.layout import col, mode_col


def templates(source, table="ability", block="instant_content", kind=None):
    if table not in WIDTHS:
        raise ValueError("新词条行模板支持 ability / leader_ability")
    groups = {"instant_content": "instant_content", "during_content": "during_content",
              "instant_trigger": "trigger", "during_trigger": "during_trigger",
              "precondition1": "precondition", "precondition2": "precondition", "precondition3": "precondition"}
    if block not in groups:
        raise ValueError(f"不支持的模板区块：{block}")
    options = wf_describe.enum_options()[groups[block]]
    if kind is not None and str(kind) not in options:
        raise ValueError(f"kind {kind} 不属于 {block} 枚举")
    view = getattr(source, "view", source)
    rows_by_kind = {}
    raw, _ = view.read_raw(TABLES[table])
    for key, leaf in codec.parse_node(raw).items():
        for index, row in enumerate(split_leaf(leaf, table)):
            mode = row[mode_col(table)]
            if block.startswith("instant") and mode != "0" or block.startswith("during") and mode != "1":
                continue
            value = row[col(table, block, "kind")]
            rows_by_kind.setdefault(value, []).append((key, index, row))
    selected = [str(kind)] if kind is not None else list(options)
    entries = []
    for value in selected:
        precedents = rows_by_kind.get(value, [])
        if precedents:
            row = list(precedents[0][2])
        else:
            row = [""] * WIDTHS[table]
            row[0] = "new_ability"
            if table == "ability":
                row[1] = "false"
            row[mode_col(table)] = "1" if block.startswith("during") else "0"
            layout = wf_describe.layout(table)
            for name in ("precondition1", "precondition2", "precondition3", "instant_trigger", "instant_content"):
                row[col(table, name, "kind")] = "0"
            row[int(layout["blocks"]["instant_precontent"])] = "(None)"
            row[int(layout["blocks"]["instant_delay"])] = "0"
            row[col(table, block, "kind")] = value
            row = fill_instant_content_defaults(table, row)
        state = "满足" if precedents else "待验证"
        entries.append({"kind": value, **options[value], "status": state, "selectable": True,
                        "defaults": row, "columnSpace": "native", "column_space": "native",
                        "precedentCount": len(precedents),
                        "precedents": [{"key": key, "row": index} for key, index, _ in precedents[:10]],
                        "checks": [result("ability.precedent", state,
                            "默认值来自当前视图先例，需核对引用对象" if precedents else "没有当前视图先例；允许选择，参数和运行时效果待验证")]})
    return {"table": table, "block": block, "column_space": "native", "options": entries,
            "note": "默认值不自动写入草稿；无先例不代表非法，实际行仍执行解析与能力声明规则。"}

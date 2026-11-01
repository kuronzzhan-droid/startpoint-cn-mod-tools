"""Local pasted tables -> asserted ability requests. No fuzzy matching or invented values."""
from __future__ import annotations

import csv
import io
import re
from decimal import Decimal, InvalidOperation

from .ability_engine import describe
from .balance_numeric import numeric_cells, valid_value, candidates
from .drafts import DraftError

FIELDS = ("character", "entry", "row", "column", "before", "after")
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


def parse_table(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 2_000_000:
        raise DraftError("请提供不超过 2 MB 的 TSV / CSV 文本")
    text = text.lstrip("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters="\t,")
    except csv.Error:
        dialect = csv.excel_tab if "\t" in text.splitlines()[0] else csv.excel
    try:
        records = list(csv.reader(io.StringIO(text, newline=""), dialect, strict=True))
    except csv.Error as exc:
        raise DraftError(f"表格格式错误：{exc}") from exc
    headers = [c.strip() for c in records[0]]
    if not all(headers) or len(headers) != len(set(headers)):
        raise DraftError("表头不能为空或重名；请在导出文件中区分列名")
    records = [r for r in records[1:] if any(c.strip() for c in r)]
    if len(records) > 1000:
        raise DraftError("一次最多导入 1000 行")
    return headers, records


def validate_mapping(mapping, headers=None):
    if not isinstance(mapping, dict) or set(mapping) - set(FIELDS):
        raise DraftError("列映射字段不合法")
    if any(not isinstance(v, str) for v in mapping.values()):
        raise DraftError("列映射必须填写列名")
    if headers is not None:
        if any(mapping.get(k) not in headers for k in ("character", "entry", "before", "after")):
            raise DraftError("请映射角色、词条、修改前、修改后四列")
        if any(v and v not in headers for v in mapping.values()):
            raise DraftError("映射引用了不存在的列")
    used = [v for v in mapping.values() if v]
    if len(used) != len(set(used)):
        raise DraftError("不同字段不能映射到同一列")
    return mapping


def _numeric_cells(row, table):
    return numeric_cells(row, table)


def _replacement(row, table, before, after, column):
    allowed = _numeric_cells(row, table)
    if column:
        if not re.fullmatch(r"c?\d+", column):
            raise DraftError("原始列号应为 c51 或 51（原生列空间，从 0 起）")
        col = int(column.removeprefix("c"))
        if col not in allowed or not valid_value(before, allowed[col]) or not valid_value(after, allowed[col]):
            raise DraftError("只支持已知数值字段的精确原始数值替换；枚举、结构或含糊表述需人工")
        if row[col] != before or before == after:
            raise DraftError("旧值不匹配或没有改动")
        return [{"column": col, "old": before, "new": after}]
    if describe(row, table) != before:
        raise DraftError("修改前必须精确匹配当前机器中文描述，或映射原始列号并填写原始旧值")
    old_nums, new_nums = NUMBER.findall(before), NUMBER.findall(after)
    if NUMBER.sub("#", before) != NUMBER.sub("#", after) or len(old_nums) != len(new_nums):
        raise DraftError("只自动转换中文描述中单个数值的替换；结构或文字变化需人工")
    diffs = [(a, b) for a, b in zip(old_nums, new_nums) if a != b]
    if len(diffs) != 1:
        raise DraftError("中文描述必须只有一个明确数值变化")
    a, b = map(Decimal, diffs[0])
    matches = []
    for cells in candidates(row, table, a, b):
        candidate = list(row)
        for cell in cells:
            candidate[cell["column"]] = cell["new"]
        if describe(candidate, table) == after and cells not in matches:
            matches.append(cells)
    if len(matches) != 1:
        raise DraftError("数值无法唯一对应到一个原始字段，需人工指定列号")
    return matches[0]


def convert_row(editor, values, roster):
    who = values["character"]
    if not who or not values["entry"]:
        raise DraftError("角色和词条不能为空；合并单元格续行需人工补齐")
    matches = [c for c in roster if who in {v for v in (c["id"], c.get("name"), c.get("code")) if v}]
    if len(matches) != 1:
        raise DraftError("角色无法唯一精确匹配（使用 ID 可消除同名歧义）")
    cid = matches[0]["id"]
    entries = editor.read(cid)["entries"]
    selector = values["entry"]
    selected = [e for e in entries if e["table"] in {"ability", "leader_ability"} and
                selector in (e["key"], f"能力{e['slot']}" if e["table"] == "ability" else "队长技")]
    if len(selected) != 1:
        raise DraftError("词条无法唯一匹配：支持能力1–6、队长技或精确词条键；技能 DSL 改动需人工")
    entry = selected[0]
    if entry["owners"] != [cid]:
        raise DraftError("词条由多个角色共享，批量入口不授权修改其他角色")
    if values.get("row"):
        if not re.fullmatch(r"[1-9]\d*", values["row"]):
            raise DraftError("词条行号从 1 起，必须为正整数")
        index = int(values["row"]) - 1
    elif len(entry["rows"]) == 1:
        index = 0
    else:
        found = [i for i, d in enumerate(entry["descriptions"]) if d == values["before"]]
        if len(found) != 1:
            raise DraftError("词条含多行，请映射词条行号，或提供唯一的完整修改前中文描述")
        index = found[0]
    if index >= len(entry["rows"]):
        raise DraftError("词条行号超出范围")
    cells = _replacement(entry["rows"][index], entry["table"], values["before"], values["after"], values.get("column", ""))
    operation = {"op": "set_cells", "table": entry["table"], "key": entry["key"], "row": index,
                 "row_count": len(entry["rows"]), "column_space": "native", "cells": cells}
    return cid, {"operations": [operation]}


def preview_rows(editor, text, mapping, roster):
    headers, records = parse_table(text)
    validate_mapping(mapping, headers)
    result, seen = [], {}
    for index, record in enumerate(records, 1):
        item = {"id": index, "source": record, "status": "需人工", "selected": False,
                "characterId": None, "request": None, "changes": [], "checks": [], "reason": ""}
        try:
            if len(record) != len(headers):
                raise DraftError("本行列数与表头不同")
            values = {key: record[headers.index(col)].strip() if col else "" for key, col in mapping.items()}
            cid, request = convert_row(editor, values, roster)
            item.update(characterId=cid, request=request)
            preview = editor.preview(cid, request)
            item.update(changes=[{**c, "row": c["row"] + 1} for c in preview["changes"][-1:]], checks=preview["checks"])
            if any(c.get("blocking") or c.get("status") == "问题" for c in preview["checks"]):
                raise DraftError("现有词条预检未通过，见五态检查")
            op = request["operations"][0]
            target = (cid, op["table"], op["key"], op["row"])
            if target in seen:
                seen[target].update(status="需人工", reason="同一词条行重复出现，需人工合并后重导入")
                raise DraftError("同一词条行重复出现，需人工合并后重导入")
            seen[target] = item
            item["status"] = "可写草稿"
        except (DraftError, ValueError, KeyError, InvalidOperation) as exc:
            item["reason"] = str(exc)
        result.append(item)
    return {"headers": headers, "mapping": mapping, "rows": result, "runtime": "未执行"}

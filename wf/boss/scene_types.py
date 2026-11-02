"""Client/server field types for Advent scene specifications (ParseTools contract)."""
from __future__ import annotations

from datetime import datetime
import re

from .schema import parse_rows

AE = "master/quest/event/advent_event.orderedmap"
AQ = "master/quest/event/advent_event_quest.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
BGM_GROUP = "master/battle/asset/battle_bgm_group.orderedmap"
SHOP = "master/shop/event_item_shop.orderedmap"
ITEM = "master/item/item.orderedmap"
CONTINUE_PREFIX = "continue_cost_"

DATE_COLUMNS = {
    (SHOP, 26): "required",
    (SHOP, 27): "optional",
    (AQ, 5): "required",
    (AQ, 6): "optional",
    (AE, 3): "schedule",
    (AE, 24): "required",
    (AE, 25): "optional",
    (AE, 26): "optional",
    (ITEM, 19): "required",
    (ITEM, 20): "optional",
}
DATE_WINDOWS = {
    SHOP: ((26, 27),),
    AQ: ((5, 6),),
    AE: ((24, 25), (24, 26)),
    ITEM: ((19, 20),),
}
MIN_DATE_COLUMNS = {SHOP: 28, AQ: 7, AE: 27, ITEM: 21}
DATETIME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$")
EVENT_CODE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
INT32_RE = re.compile(r"^(?:0|[1-9][0-9]{0,9})$")
CONTINUE_RE = re.compile(r"^([1-9][0-9]{0,9}):([1-9][0-9]{0,9})$")


def parse_jst_datetime(value, label: str, *, allow_none: bool = False) -> datetime | None:
    if not isinstance(value, str):
        raise ValueError(f"{label} 日期必须是字符串")
    if allow_none and value == "(None)":
        return None
    match = DATETIME_RE.fullmatch(value)
    if not match:
        expected = "YYYY-MM-DD HH:MM:SS 或 (None)" if allow_none else "YYYY-MM-DD HH:MM:SS"
        raise ValueError(f"{label} 日期格式必须为 {expected}：{value!r}")
    year, month, day, hour, minute, second = map(int, match.groups())
    if not 1970 <= year <= 2200:
        raise ValueError(f"{label} 年份必须在 1970–2200 范围内：{value!r}")
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError as exc:
        raise ValueError(f"{label} 日期时间无效：{value!r}") from exc


def validate_date_cell(table: str, column: int, value, label: str = "") -> None:
    mode = DATE_COLUMNS.get((table, column))
    if mode is None:
        return
    tag = label or f"{table} c{column}"
    if not isinstance(value, str):
        raise ValueError(f"{tag} 日期列必须是字符串")
    if mode == "required":
        parse_jst_datetime(value, tag, allow_none=False)
    elif mode == "optional":
        parse_jst_datetime(value, tag, allow_none=True)
    elif mode == "schedule" and value != "":
        for index, part in enumerate(value.split(",")):
            parse_jst_datetime(part, f"{tag}[{index}]", allow_none=True)


def validate_row_dates(logical: str, path, row: list[str]) -> list[str]:
    required_len = MIN_DATE_COLUMNS.get(logical)
    if required_len is None:
        return []
    location = f"{logical} {'/'.join(path)}"
    if len(row) < required_len:
        return [f"{location} 缺少原生日期列（需至少 {required_len} 列，实际 {len(row)} 列）"]
    issues = []
    parsed: dict[int, datetime | None] = {}
    for (table, column), mode in DATE_COLUMNS.items():
        if table != logical:
            continue
        try:
            validate_date_cell(logical, column, row[column], f"{location} c{column}")
            if mode in {"required", "optional"}:
                parsed[column] = parse_jst_datetime(row[column], f"{location} c{column}", allow_none=mode == "optional")
        except ValueError as exc:
            issues.append(str(exc))
    for start_col, end_col in DATE_WINDOWS.get(logical, ()):
        start, end = parsed.get(start_col), parsed.get(end_col)
        if start is not None and end is not None and end < start:
            issues.append(f"{location} c{start_col}..c{end_col} 结束时间早于开始时间")
    return issues


def validate_event_code(value, label: str = "event-code") -> str:
    if not isinstance(value, str) or value == "(None)" or not EVENT_CODE_RE.fullmatch(value):
        raise ValueError(f"{label} 活动代号 c0 必须为非空标识符：{value!r}")
    return value


def validate_event_original(value, label: str = "original") -> str:
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str):
        raise ValueError(f"{label} 活动 original 列 c1 必须为 (None) 或非负整数")
    if value == "(None)":
        return value
    if not INT32_RE.fullmatch(value) or int(value) > 2147483647:
        raise ValueError(f"{label} 活动 original 列 c1 必须为 (None) 或 32 位非负整数：{value!r}")
    return value


def parse_continue_cost(text, label: str = "continue_cost") -> dict[str, int]:
    if not isinstance(text, str):
        raise ValueError(f"{label} 续战消耗必须是字符串")
    rows = parse_rows(text)
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError(f"{label} 续战消耗必须是单列 <道具ID>:<数量>")
    match = CONTINUE_RE.fullmatch(rows[0][0])
    if not match:
        raise ValueError(f"{label} 续战消耗格式必须为 <正整数道具ID>:<正整数数量>：{rows[0][0]!r}")
    item_id, amount = int(match[1]), int(match[2])
    if item_id > 2147483647 or amount > 2147483647:
        raise ValueError(f"{label} 续战消耗超出 32 位正整数范围：{rows[0][0]!r}")
    return {"item_id": item_id, "amount": amount}

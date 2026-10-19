"""Editable shop windows and warnings against the server's pinned clock."""
from datetime import datetime
import re

from wf.rules.catalog import result
from . import schema as s

SERVER_NOW = datetime(2025, 8, 5)


def parse_date(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?", value):
        raise ValueError(f"{field} must be YYYY-MM-DD or YYYY-MM-DD HH:MM:SS")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value}") from exc


def set_availability(state, row, spec, *, adding=False, source=None):
    if adding and s.present(row[26]) and parse_date(row[26], "source availableUntil") < SERVER_NOW:
        checks = getattr(state, "shop_checks", [])
        checks.append(result("boss.shop.availability", "问题",
            f"来源商品 {source} 已于 {row[26]} 下架；服务端时间固定为 2025-08-05。"
            "新增商品使用本次设置的上架窗口（默认 2000-01-01 起，无结束时间）。",
            sourceProduct=source, sourceAvailableUntil=row[26]))
        state.shop_checks = checks
    if adding:
        row[25:27] = ["2000-01-01", "(None)"]
    for field, column in (("availableFrom", 25), ("availableUntil", 26)):
        if field in spec:
            value = spec[field]
            if value is None and field == "availableUntil":
                row[column] = "(None)"
            else:
                parse_date(value, field)
                row[column] = value
    if adding or any(field in spec for field in ("availableFrom", "availableUntil")):
        start = parse_date(row[25], "availableFrom") if s.present(row[25]) else None
        end = parse_date(row[26], "availableUntil") if s.present(row[26]) else None
        if start is not None and end is not None and end < start:
            raise ValueError("availableUntil must not be before availableFrom")

"""修正八个正式角色的第二玛纳板开放日期；纯内存、严格限定行范围。

原生 GeneralCharacterLogic.canManaBoard2Open 使用服务器时间而非设备时间。
2025 年的游戏时钟会隐藏这些曾误写为 2026 年开放的角色 A4–6。这里只
前移已审查的开始日期，不改结束日期、学习门槛、节点或能力数据。
"""
from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import zlib

import wf_mod_tool as core

LOGICAL = "master/mana_board/mana_board2_open_condition.orderedmap"
OPEN_START = "2000-01-01 00:00:00"
TARGET_STARTS = {
    "129998": "2026-08-30 12:00:00",
    "149994": "2026-08-30 12:00:00",
    "159999": "2026-08-30 12:00:00",
    "149993": "2026-08-30 12:00:00",
    "119970": "2026-08-31 00:00:00",
    "129970": "2026-08-31 00:00:00",
    "139970": "2026-08-31 00:00:00",
    "149970": "2026-08-31 00:00:00",
}


def _date(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("开放日期必须是原生日期字符串")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError(f"非法开放日期: {value!r}") from exc
    if parsed.strftime("%Y-%m-%d %H:%M:%S") != value:
        raise ValueError(f"非规范开放日期: {value!r}")
    return parsed


def opening_row(cid: str, row: list[str]) -> list[str]:
    """供候选及后续构建器使用；返回新行，未知角色/新日期拒绝猜测。"""
    if cid not in TARGET_STARTS:
        raise ValueError(f"角色不在本次开放日期修订范围: {cid}")
    if len(row) != 2:
        raise ValueError(f"{cid}: 开放条件必须正好两列")
    if row[0] not in (TARGET_STARTS[cid], OPEN_START):
        raise ValueError(f"{cid}: 开始日期已偏离审查基线: {row[0]!r}")
    if _date(row[1]) < _date(row[0]):
        raise ValueError(f"{cid}: 结束日期早于开始日期")
    return [OPEN_START, row[1]]


def _decode_row(raw: bytes, cid: str) -> list[str]:
    try:
        rows = core.read_csv_lines(zlib.decompress(raw).decode("utf-8"))
    except (zlib.error, UnicodeError) as exc:
        raise ValueError(f"{cid}: 无效压缩 CSV 行") from exc
    if len(rows) != 1:
        raise ValueError(f"{cid}: 开放条件必须只有一行")
    return rows[0]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def patch_table(raw: bytes) -> tuple[bytes, dict]:
    """只替换八个 c0；保留外键顺序及所有非目标压缩行的原始字节。"""
    table = core.read_orderedmap_raw_rows_from_bytes(raw, LOGICAL)
    if len(set(table.keys)) != len(table.keys):
        raise ValueError("开放条件表包含重复角色键")
    missing = set(TARGET_STARTS) - set(table.keys)
    if missing:
        raise ValueError(f"开放条件表缺少目标角色: {sorted(missing)}")
    original_rows = list(table.rows)
    changes = []
    for index, cid in enumerate(table.keys):
        if cid not in TARGET_STARTS:
            continue
        before_raw = original_rows[index]
        before = _decode_row(before_raw, cid)
        after = opening_row(cid, before)
        if after == before:
            continue
        after_raw = zlib.compress(core.write_csv_lines([after]).rstrip("\n").encode("utf-8"))
        table.rows[index] = after_raw
        changes.append({
            "key": cid, "changed_columns": [0], "before": before, "after": after,
            "before_raw_sha256": _sha(before_raw), "after_raw_sha256": _sha(after_raw),
            "before_raw_base64": base64.b64encode(before_raw).decode("ascii"),
            "after_raw_base64": base64.b64encode(after_raw).decode("ascii"),
        })
    output = core.build_orderedmap_raw_rows(table) if changes else raw
    readback = core.read_orderedmap_raw_rows_from_bytes(output, LOGICAL)
    if readback.keys != table.keys or readback.rows != table.rows:
        raise ValueError("开放条件表回读不一致")
    foreign = [(a, b) for key, a, b in zip(table.keys, original_rows, readback.rows)
               if key not in TARGET_STARTS]
    if any(a != b for a, b in foreign):
        raise ValueError("非目标行压缩字节被改动")
    return output, {
        "logical": LOGICAL, "tier": "common",
        "before_sha256": _sha(raw), "after_sha256": _sha(output),
        "changed_keys": [change["key"] for change in changes], "changes": changes,
        "foreign_rows_preserved": len(foreign), "row_count": len(table.keys),
        "key_order_preserved": True,
    }

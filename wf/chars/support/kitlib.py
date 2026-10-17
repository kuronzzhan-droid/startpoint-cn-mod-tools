"""Production primitives extracted from wf_midautumn_kitlib.py (C baseline)."""
from __future__ import annotations
from typing import Any, Callable, Iterable, Mapping, Sequence


import wf_client_legality as L  # noqa: E402


from types import SimpleNamespace
MS = SimpleNamespace(BATCH_DIR="work/character_packs/halloween-20261016", UNIQUE_CONDITION_LOGICAL="master/character/unique_condition.orderedmap")  # noqa: E402


ABILITY = "master/ability/ability.orderedmap"


LEADER = "master/ability/leader_ability.orderedmap"


UNIQUE = MS.UNIQUE_CONDITION_LOGICAL


ACTION = "master/skill/action_skill.orderedmap"


CAS = "master/string/custom_ability_string.orderedmap"


ABILITY_NCOLS = 126


LEADER_NCOLS = 124


class KitError(RuntimeError):
    pass


FORBIDDEN_PANEL_WORDS = (
    "自身为队长时",          # desc_override 禁语（队长技面板已自带标题）
    "觉醒后",                # 「(觉醒后X%)」两列写法禁用
    "生命值100%以下", "生命值 100%以下", "HP100%以下", "HP 100%以下",   # 恒真条件文本
    "null", "(None)",        # 组列空串读成 null 时的漏网文本
    "无上限", "无限叠加", "不设上限", "可无限",                          # 无上限就写到效果为止
)


def panel_problems(text: str, *, skill_flag: bool = False) -> list[str]:
    """面板文案规则检查。``skill_flag=True``：这是「技能强化」条目，不许出现数字与时间。"""
    if not isinstance(text, str):
        return ["panel text is not a string"]
    problems = [f"panel text contains forbidden word {word!r}" for word in FORBIDDEN_PANEL_WORDS
                if word in text]
    if skill_flag:
        if any(ch.isdigit() for ch in text):
            problems.append("skill-flag panel entry must not carry numbers")
        for unit in ("秒", "％", "%"):
            if unit in text:
                problems.append(f"skill-flag panel entry must not carry {unit!r}")
    return problems


def check_panel(text: str, *, skill_flag: bool = False, label: str = "") -> str:
    problems = panel_problems(text, skill_flag=skill_flag)
    if problems:
        raise KitError(f"panel text rejected {label or text!r}: {problems}")
    return text


def _rows(ctx, table: str, source: str) -> dict[str, str]:
    if source == "official":
        return ctx.official_flat(table)
    if source == "package":
        return ctx.pkg_flat(table)
    if source in ("live", "store"):
        return ctx.live_flat(table)
    if source == "template":
        return ctx.template_flat(table)
    raise KitError(f"unknown donor source {source!r}")


def donor_row(ctx, table: str, key: str, index: int = 0, *, source: str = "official") -> list[str]:
    """官方 donor 行（默认取 ``.cdn/cn`` 官方归档，不取 store）。``key`` 支持 ``"2110201#1"``。"""
    if "#" in key:
        key, _, suffix = key.partition("#")
        index = int(suffix)
    rows = _rows(ctx, table, source)
    if key not in rows:
        raise KitError(f"donor {key} missing from {source} {table}")
    lines = ctx.csv_split(rows[key])
    if not 0 <= index < len(lines):
        raise KitError(f"donor {key} has {len(lines)} records; index {index} out of range")
    return list(lines[index])


def apply_cells(row: Sequence[str], cells: Mapping[Any, Any] | None,
                ncols: int | None = None) -> list[str]:
    """donor 行 + 逐格改。``cells`` 的键是列号（int 或数字字符串），值一律转成字符串。

    行短于目标列数时补空串；``ncols`` 给定时结果必须恰好这么长（词条 126 / 队长 124）。
    """
    out = list(row)
    target = ncols if ncols is not None else len(out)
    for col, value in sorted((int(k), v) for k, v in dict(cells or {}).items()):
        if col < 0:
            raise KitError(f"negative column {col}")
        if col >= len(out):
            out.extend([""] * (col + 1 - len(out)))
        out[col] = "" if value is None else str(value)
    if len(out) < target:
        out.extend([""] * (target - len(out)))
    if ncols is not None and len(out) != ncols:
        raise KitError(f"row has {len(out)} columns, expected {ncols}")
    return out


def row_problems(kind: str, row: Sequence[str], element: int | None = None) -> dict[str, list[str]]:
    """逐行 ``wf_client_legality``：合法性 + 声明块字段 + （词条）元素列。"""
    row = list(row)
    problems = {"client_legality": L.client_legality_problems(kind, row),
                "declared_block_fields": L.declared_block_field_problems(kind, row)}
    if kind == "ability" and element is not None:
        problems["element_columns"] = L.ability_element_column_problems(kind, row, element)
    return {name: value for name, value in problems.items() if value}


def capabilities(kind: str, row: Sequence[str]) -> list[str]:
    return L.required_client_capabilities(kind, list(row))


def describe(kind: str, row: Sequence[str]) -> str:
    """``wf_describe`` 渲染回读：面板上真正会显示的中文。"""
    import wf_describe
    return wf_describe.describe_rows([list(row)], kind)[0]


def build_row(ctx, kind: str, donor: str, cells: Mapping[Any, Any] | None = None, *,
              table: str | None = None, source: str = "official", element: int | None = None,
              expect_describe: str | None = None, label: str = "") -> tuple[list[str], dict[str, Any]]:
    """donor + 逐格改 + 合法性 + describe 回读，一步到位；任何问题直接抛错。

    ``kind`` = ``"ability"`` / ``"leader_ability"``；``donor`` 可写 ``"<键>"`` 或 ``"<键>#<记录号>"``。
    ``expect_describe`` 给了就逐字核对（设计稿登记的面板预期文案 ⇒ 行漂移/描述器漂移都会被抓）。
    """
    if kind not in ("ability", "leader_ability"):
        raise KitError(f"build_row supports ability/leader_ability only, got {kind!r}")
    table = table or (ABILITY if kind == "ability" else LEADER)
    ncols = ABILITY_NCOLS if kind == "ability" else LEADER_NCOLS
    row = apply_cells(donor_row(ctx, table, donor, source=source), cells, ncols)
    problems = row_problems(kind, row, element)
    if problems:
        raise KitError(f"{label or donor}: client legality rejected the row: {problems}")
    rendered = describe(kind, row)
    if expect_describe is not None and rendered != expect_describe:
        raise KitError(f"{label or donor}: wf_describe drift\n  got    {rendered!r}\n  expect {expect_describe!r}")
    return row, {"label": label or donor, "kind": kind, "donor": donor, "cells": dict(cells or {}),
                 "describe": rendered, "capabilities": capabilities(kind, row)}


def check_ability_key(rows: Sequence[Sequence[str]], key: str, code: str, slot: int) -> None:
    """一键内多记录的硬约束：c0 = ``<code>_<slot>``，c1（主位限制）与 c2（雕像组）全键一致。"""
    if not rows:
        raise KitError(f"ability {key} has no records")
    for row in rows:
        if row[0] != f"{code}_{slot}":
            raise KitError(f"ability {key}: c0 {row[0]!r} != {code}_{slot}")
    if len({r[1] for r in rows}) != 1 or len({r[2] for r in rows}) != 1:
        raise KitError(f"ability {key}: mixed c1/c2 {[(r[1], r[2]) for r in rows]}")
    if rows[0][2] and rows[0][2] not in L.ABILITY_STATUE_GROUPS:
        raise KitError(f"ability {key}: unknown statue group {rows[0][2]!r}")

# -*- coding: utf-8 -*-
"""wfx_registry.json 的只读加载器与派生表（不依赖任何 store / 其他 mod-tools 模块）。

wf_client_patch_scope、wf_client_legality、wf_wfx、wfx_gate 都从这里取表，
所以这里只允许标准库依赖：被 wf_battle_rules → wf_client_patch_scope 链路在导入期加载。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parent / "wfx_registry.json"
LEVELS = ("crash", "semantic", "cosmetic")


class RegistryError(ValueError):
    """注册表结构不合法。"""


@lru_cache(maxsize=None)
def load(path: str | None = None) -> dict[str, Any]:
    """读取并做结构自检；结果缓存，调用方不得修改返回值。"""
    source = Path(path) if path else REGISTRY_PATH
    data = json.loads(source.read_text(encoding="utf-8"))
    _validate(data)
    return data


def _validate(data: dict[str, Any]) -> None:
    if data.get("schema_version") != 1:
        raise RegistryError("wfx_registry schema_version 必须为 1")
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        raise RegistryError("capabilities 必须是非空对象")
    for name, entry in capabilities.items():
        if entry.get("level") not in LEVELS:
            raise RegistryError(f"capability {name} 的 level 不合法: {entry.get('level')!r}")
        if entry.get("status") not in ("shipped", "planned"):
            raise RegistryError(f"capability {name} 的 status 必须是 shipped/planned")
        for dep in entry.get("depends_on", ()):
            if dep not in capabilities:
                raise RegistryError(f"capability {name} 依赖未登记的 {dep}")
    seen: set[tuple[str, str]] = set()
    for entry in data.get("patch_content_kinds", ()):
        key = (entry["block"], entry["value"])
        if key in seen:
            raise RegistryError(f"patch_content_kinds 重复登记 {key}")
        seen.add(key)
        if entry["capability"] not in capabilities:
            raise RegistryError(f"{key} 的 capability 未登记: {entry['capability']}")
        tables = entry.get("parser_tables")
        if not isinstance(tables, list) or not tables:
            raise RegistryError(f"{key} 必须登记 parser_tables（补丁实际扩展的表解析器）")
        for table, capability in (entry.get("parser_capabilities") or {}).items():
            if table not in tables:
                raise RegistryError(f"{key} 的 parser_capabilities 表 {table} 不在 parser_tables")
            if capability not in capabilities:
                raise RegistryError(f"{key} 的解析器 capability 未登记: {capability}")
    codes: set[int] = set()
    ranges = data.get("effect_code_ranges", ())
    for effect in data.get("effect_codes", ()):
        code = effect.get("code")
        if type(code) is not int or code in codes:
            raise RegistryError(f"效果码重复或不是整数: {code!r}")
        codes.add(code)
        if not any(item["from"] <= code <= item["to"] and item["family"] != "reserved"
                   for item in ranges):
            raise RegistryError(f"效果码 {code} 不在任何已分配的号段")
        if effect.get("capability") not in capabilities:
            raise RegistryError(f"效果码 {code} 的 capability 未登记")
        if effect.get("arg") not in data.get("arg_kinds", {}):
            raise RegistryError(f"效果码 {code} 的 arg 种类未登记: {effect.get('arg')!r}")
        if effect.get("reduce") not in ("sum", "prod", "min", "any"):
            raise RegistryError(f"效果码 {code} 的 reduce 不合法")
        if effect.get("gate") not in ("block", "warn"):
            raise RegistryError(f"效果码 {code} 的 gate 必须是 block/warn")
    for bit, entry in (data.get("flags", {}).get("bits") or {}).items():
        if entry.get("capability") not in capabilities:
            raise RegistryError(f"flags bit{bit} 的 capability 未登记")


def capabilities() -> dict[str, dict[str, Any]]:
    return load()["capabilities"]


def capability_level(name: str) -> str | None:
    entry = capabilities().get(name)
    return entry["level"] if entry else None


def capability_closure(names) -> list[str]:
    """names ∪ 其 depends_on 的传递闭包；保持首次出现顺序。"""
    table = capabilities()
    out: list[str] = []
    stack = list(names)[::-1]
    while stack:
        name = stack.pop()
        if name in out:
            continue
        out.append(name)
        for dep in reversed(table.get(name, {}).get("depends_on", ())):
            if dep not in out:
                stack.append(dep)
    return out


def patch_content_kinds() -> list[dict[str, Any]]:
    return list(load()["patch_content_kinds"])


def patch_parser_tables() -> dict[tuple[str, str], frozenset[str]]:
    """(块, 构造值) → 补丁实际扩展了解析器的表集合。"""
    return {(entry["block"], entry["value"]): frozenset(entry["parser_tables"])
            for entry in patch_content_kinds()}


def patch_parser_capabilities() -> dict[tuple[str, str], dict[str, str]]:
    """(块, 构造值) → {表: 该表解析器扩展自身的 capability}（只列有额外要求的构造）。"""
    return {(entry["block"], entry["value"]): dict(entry["parser_capabilities"])
            for entry in patch_content_kinds() if entry.get("parser_capabilities")}


def client_patch_content_kinds() -> dict[str, dict[str, str]]:
    """{块: {构造值: 运行时 capability}}，块顺序固定 instant_content → during_content。"""
    out: dict[str, dict[str, str]] = {"instant_content": {}, "during_content": {}}
    for entry in patch_content_kinds():
        out.setdefault(entry["block"], {})[entry["value"]] = entry["capability"]
    return out


def patch_kinds_borrowing_uid_column() -> frozenset[tuple[str, str]]:
    """借用 unique_condition_id 列装别的东西（param_id / 规则码）的补丁构造。"""
    return frozenset((entry["block"], entry["value"]) for entry in patch_content_kinds()
                     if entry.get("unique_condition_id_column") not in (None, "unique_condition_id"))


def effect_codes() -> dict[int, dict[str, Any]]:
    return {entry["code"]: entry for entry in load()["effect_codes"]}

# -*- coding: utf-8 -*-
"""扩展词条（WFX）效果状态的 string_id 编解码与校验（注册表驱动的纯函数，不碰 store）。

载体 A（设计稿 4.3）：master/character/unique_condition.orderedmap 的一行，c0 写

    wfx:<code>:<arg>:<value>:<flags>:<label>

- code / arg：十进制非负整数；flags 按效果码规则允许 int32（码28/29含负数）；
- value：十进制数，无指数、无多余的 0（客户端 convert_d）；规范写法由 format_value 产出，
  解码只认规范写法，避免同一效果出现两种 sid；
- label：只为唯一性与可读性，[A-Za-z0-9_]，不含 ':'/','。
效果码、参数位种类、值域、合成规则、capability 全部取自 wfx_registry.json。
码 20 按作者裁决 #2（2026-09-28）并入官方独立乘区池：arg = 池号 + 属性组（damage_pool_arg），
不是码 21–23 的伤害掩码；以 wfx 开头但不是登记前缀的 sid（含首尾空白）一律按写错拒绝。

旧批1码仍为 planned；v35e 已登记效果按固定离线客户端证据检查，不代表设备验证。
"""
from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

pass  # Imports resolve from this checkout/package, not external source copies.
import wfx_registry  # noqa: E402
from wf.wfx_semantics import (effect_arg_problems, flags_rule,
                              hidden_icon_capability, integer_problems, uses_pin)


class WfxError(ValueError):
    """wfx string_id / 行不合法。"""


_UINT_RE = re.compile(r"(?:0|[1-9][0-9]*)")
_VALUE_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?")
_INT32_MAX = 2147483647
PIN_BIT = 1


def _registry() -> dict[str, Any]:
    return wfx_registry.load()


def sid_prefix() -> str:
    return _registry()["sid"]["prefix"]


def classify_sid(sid: str) -> str | None:
    """'effect'（逐字节以 wfx: 开头的效果行）/ 'reserved'（保留前缀，尚无实现）/
    'lookalike'（去掉首尾空白、忽略大小写后以 wfx 开头，但不是上面两种）/ None（与本框架无关）。

    不 strip 原值：客户端 split(":") 的首段必须恰好是 "wfx"，首尾带空白的 sid 在客户端上
    不是效果行，这里判 lookalike。lookalike 在闸门上一律拒绝（wfx 前缀整段保留给本框架，
    WFX:/wfx;/wfx21: 这类多半是写错，放行 = 诅咒静默失效）。"""
    text = sid if isinstance(sid, str) else ""
    spec = _registry()["sid"]
    if text.startswith(spec["prefix"]):
        return "effect"
    if any(text.startswith(prefix) for prefix in spec.get("reserved_prefixes", {})):
        return "reserved"
    if text.strip().lower().startswith(spec["family_prefix"]):
        return "lookalike"
    return None


def format_value(value: Any) -> str:
    """数值 → 规范十进制串（无指数、无尾随 0、无 '-0'）。字符串须已是规范写法。"""
    if isinstance(value, bool):
        raise WfxError("value 不能是布尔值")
    if isinstance(value, str):
        if not _VALUE_RE.fullmatch(value) or value == "-0":
            raise WfxError(f"value={value!r} 不是规范十进制写法（例：-0.5、0.3、15）")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WfxError(f"value={value!r} 不是有限数")
        number = Decimal(repr(value))
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, Decimal):
        if not value.is_finite():
            raise WfxError(f"value={value!r} 不是有限数")
        number = value
    else:
        raise WfxError(f"value 类型不支持: {type(value).__name__}")
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    if not _VALUE_RE.fullmatch(text):
        raise WfxError(f"value={value!r} 无法规范化")
    return text


@dataclass(frozen=True)
class WfxSpec:
    code: int
    arg: int
    value: Decimal
    flags: int
    label: str

    @property
    def value_text(self) -> str:
        return format_value(self.value)

    @property
    def pin(self) -> bool:
        return uses_pin(_registry(), self.code) and bool(self.flags & PIN_BIT)

    @property
    def effect(self) -> dict[str, Any] | None:
        return wfx_registry.effect_codes().get(self.code)

    @property
    def sid(self) -> str:
        return f"{sid_prefix()}{self.code}:{self.arg}:{self.value_text}:{self.flags}:{self.label}"


def _parse_uint(text: str, name: str) -> int:
    if not _UINT_RE.fullmatch(text):
        raise WfxError(f"{name}={text!r} 须为无前导 0 的十进制非负整数")
    value = int(text)
    if value > _INT32_MAX:
        raise WfxError(f"{name}={value} 超出 int32")
    return value


def parse_sid(sid: str) -> WfxSpec:
    """只做语法解析（段数、数字格式）；语义校验见 spec_problems。"""
    text = sid if isinstance(sid, str) else ""
    prefix = sid_prefix()
    if not text.startswith(prefix):
        raise WfxError(f"string_id {sid!r} 不以 {prefix!r} 开头")
    parts = text.split(":")
    names = _registry()["sid"]["segments"]
    if len(parts) != len(names) + 1:
        raise WfxError(
            f"string_id {sid!r} 须为 {prefix}<{'>:<'.join(names)}>（{len(names)} 段），实为 {len(parts) - 1} 段")
    _head, code, arg, value, flags, label = parts
    if not _VALUE_RE.fullmatch(value) or value == "-0":
        raise WfxError(f"value={value!r} 不是规范十进制写法（无指数、无尾随 0）")
    code_value = _parse_uint(code, "code")
    rule = flags_rule(_registry(), code_value)
    if rule is None:
        flag_value = _parse_uint(flags, "flags")
    else:
        if not re.fullmatch(r"0|-?[1-9][0-9]*", flags):
            raise WfxError(f"flags={flags!r} 须为规范十进制整数")
        flag_value = int(flags)
        problems = integer_problems(flag_value, rule, "flags")
        if problems:
            raise WfxError("；".join(problems))
    return WfxSpec(code_value, _parse_uint(arg, "arg"), Decimal(value), flag_value, label)


def _range_of(code: int) -> dict[str, Any] | None:
    for item in _registry()["effect_code_ranges"]:
        if item["from"] <= code <= item["to"]:
            return item
    return None


def damage_mask(types: Iterable[str] = (), elements: Iterable[str] = ()) -> int:
    """码 20–23 的 arg：类型组 OR、属性组 OR，组间 AND；两组都空 = 全部伤害（0）。"""
    spec = _registry()["arg_kinds"]["damage_mask"]
    mask = 0
    for name in types:
        if name not in spec["types"]:
            raise WfxError(f"未知伤害类型: {name!r}（可选 {sorted(spec['types'])}）")
        mask |= spec["types"][name]
    for name in elements:
        if name not in spec["elements"]:
            raise WfxError(f"未知属性: {name!r}（可选 {sorted(spec['elements'])}）")
        mask |= 1 << (spec["element_shift"] + spec["elements"][name])
    return mask


def damage_mask_parts(mask: int) -> tuple[list[str], list[str]]:
    """damage_mask 的逆：(类型名列表, 属性名列表)，按位序。"""
    spec = _registry()["arg_kinds"]["damage_mask"]
    types = [name for name, bit in sorted(spec["types"].items(), key=lambda item: item[1]) if mask & bit]
    elements = [name for name, index in sorted(spec["elements"].items(), key=lambda item: item[1])
                if mask & (1 << (spec["element_shift"] + index))]
    return types, elements


def damage_pool_arg(pool: str, elements: Iterable[str] = ()) -> int:
    """码 20 的 arg（作者裁决 #2：并入官方独立乘区池）：低 8 位池号 + 属性组位。

    pool 取注册表 arg_kinds.damage_pool.pools 的 name：all(723/421)、direct(693/410)、
    skill(694/411)、ability(695/412)、power_flip(696/413)。elements 空 = 不限属性。"""
    spec = _registry()["arg_kinds"]["damage_pool"]
    ids = {entry["name"]: int(number) for number, entry in spec["pools"].items()}
    if pool not in ids:
        raise WfxError(f"未知官方乘区池: {pool!r}（可选 {sorted(ids)}）")
    arg = ids[pool]
    for name in elements:
        if name not in spec["elements"]:
            raise WfxError(f"未知属性: {name!r}（可选 {sorted(spec['elements'])}）")
        arg |= 1 << (spec["element_shift"] + spec["elements"][name])
    return arg


def damage_pool_parts(arg: int) -> tuple[dict[str, Any], list[str]]:
    """damage_pool_arg 的逆：(池条目, 属性名列表)；池号未登记抛 WfxError。"""
    spec = _registry()["arg_kinds"]["damage_pool"]
    pool = spec["pools"].get(str(arg & spec["pool_field_mask"]))
    if pool is None:
        raise WfxError(f"arg={arg} 的池号 {arg & spec['pool_field_mask']} 未登记")
    elements = [name for name, index in sorted(spec["elements"].items(), key=lambda item: item[1])
                if arg & (1 << (spec["element_shift"] + index))]
    return pool, elements


def gauge_arg(gains: Iterable[str], **kwargs: Iterable[str]) -> int:
    """码 30/31 的 arg：与 during 423 规则码同一布局，直接复用 wf_battle_rules.gauge_mask。"""
    import wf_battle_rules
    return wf_battle_rules.gauge_mask(list(gains), **kwargs)


def _arg_problems(kind: str, arg: int) -> list[str]:
    arg_kinds = _registry()["arg_kinds"]
    if kind == "none":
        return [] if arg == 0 else [f"arg={arg}：该效果不用参数位，必须为 0"]
    if kind == "damage_mask":
        spec = arg_kinds["damage_mask"]
        known = spec["type_group_mask"] | spec["element_group_mask"]
        if arg & ~known:
            return [f"arg={arg} 含伤害掩码之外的位（已知位 {known}）"]
        return []
    if kind == "damage_pool":
        spec = arg_kinds["damage_pool"]
        pool = arg & spec["pool_field_mask"]
        problems = []
        if str(pool) not in spec["pools"]:
            names = ", ".join(f"{number}={entry['name']}" for number, entry in spec["pools"].items())
            problems.append(f"arg 低 8 位池号={pool} 未登记（官方独立乘区池只有 {names}）")
        if arg & ~(spec["pool_field_mask"] | spec["element_group_mask"]):
            problems.append(f"arg={arg} 含池号与属性组之外的位（属性组 {spec['element_group_mask']}）")
        return problems
    if kind == "gauge_mask":
        import wf_battle_rules
        try:
            wf_battle_rules.validate_code(423, arg)
        except ValueError as exc:
            return [f"arg={arg} 不是合法的回槽掩码：{exc}"]
        return []
    if kind == "dash_param_id":
        values = arg_kinds["dash_param_id"]["values"]
        return [] if str(arg) in values else [f"arg={arg} 不是冲刺参数号（0–{len(values) - 1}）"]
    return [f"arg 种类 {kind!r} 未实现校验"]


def _value_problems(rule: dict[str, Any], value: Decimal) -> list[str]:
    problems = []
    if rule.get("integer") and value != value.to_integral_value():
        problems.append(f"value={format_value(value)} 须为整数")
    if "min" in rule and value < Decimal(str(rule["min"])):
        problems.append(f"value={format_value(value)} 低于下限 {rule['min']}")
    if "max" in rule:
        limit = Decimal(str(rule["max"]))
        if rule.get("max_exclusive") and value >= limit:
            problems.append(f"value={format_value(value)} 须小于 {rule['max']}")
        elif not rule.get("max_exclusive") and value > limit:
            problems.append(f"value={format_value(value)} 高于上限 {rule['max']}")
    return problems


def spec_problems(spec: WfxSpec) -> list[str]:
    """语义校验：效果码已登记、arg 位合法、值域合法、flags 未用位为 0、label 合法。"""
    registry = _registry()
    effect = wfx_registry.effect_codes().get(spec.code)
    if effect is None:
        band = _range_of(spec.code)
        where = (f"号段 {band['from']}–{band['to']}（{band['label']}，批 {band['batch']}）"
                 if band else "任何号段之外")
        return [f"效果码 {spec.code} 未定义（{where}）"]
    problems = effect_arg_problems(effect, spec.arg)
    if problems is None:
        problems = _arg_problems(effect["arg"], spec.arg)
    problems += _value_problems(effect["value"], spec.value)
    rule = flags_rule(registry, spec.code)
    if rule is not None:
        problems += integer_problems(spec.flags, rule, "flags")
    else:
        known = registry["flags"]["known_mask"]
        if spec.flags & ~known:
            problems.append(f"flags={spec.flags} 含未定义位（只允许 {known}：bit0=pin）")
    if not re.fullmatch(registry["sid"]["label_pattern"], spec.label or ""):
        problems.append(f"label={spec.label!r} 须匹配 {registry['sid']['label_pattern']}")
    return [f"码 {spec.code}（{effect['label']}）：{text}" for text in problems]


def decode_sid(sid: str) -> WfxSpec:
    """解析 + 语义校验；任何问题都抛 WfxError。"""
    spec = parse_sid(sid)
    problems = spec_problems(spec)
    if problems:
        raise WfxError("；".join(problems))
    return spec


def encode_sid(code: int, arg: int, value: Any, flags: int = 0, label: str = "") -> str:
    """生成规范 sid；不合法即抛 WfxError（写盘前的唯一入口）。"""
    for name, number in (("code", code), ("arg", arg)):
        if type(number) is not int or number < 0 or number > _INT32_MAX:
            raise WfxError(f"{name}={number!r} 须为 int32 范围内的非负整数")
    rule = flags_rule(_registry(), code)
    problems = integer_problems(flags, rule or {}, "flags")
    if problems:
        raise WfxError("；".join(problems))
    spec = WfxSpec(code, arg, Decimal(format_value(value)), flags, label)
    problems = spec_problems(spec)
    if problems:
        raise WfxError("；".join(problems))
    return spec.sid


def required_capabilities(spec: WfxSpec) -> list[str]:
    """该效果行生效所需的 capability（含 depends_on 闭包；flags 位各自的 capability）。"""
    names: list[str] = []
    effect = spec.effect
    if effect is not None:
        names.append(effect["capability"])
    registry = _registry()
    if uses_pin(registry, spec.code):
        for bit, entry in registry["flags"]["bits"].items():
            if spec.flags & (1 << int(bit)):
                names.append(entry["capability"])
    hidden = hidden_icon_capability(registry, spec.sid)
    if hidden:
        names.append(hidden)
    return wfx_registry.capability_closure(names)


def apply_target_problems(spec: WfxSpec, target: str | int) -> list[str]:
    """施加行的目标与效果作用侧一致（码 40/50/52 只能给主位 2 或全队 5）。"""
    effect = spec.effect or {}
    allowed = effect.get("apply_targets")
    if allowed and str(target) not in allowed:
        return [f"码 {spec.code}（{effect['label']}）作用于{effect['side']}，施加目标只能是 {allowed}，实为 {target}"]
    return []


# ------------------------------------------------------------------ unique_condition 行

UNIQUE_COLUMNS = 15


def unique_row(sid: str, name: str, icon: str, duration: str, max_acc: str, *, bad: bool,
               cancelable: bool = False, force: bool = True, keep_on_death: bool = True,
               known_icons: Iterable[str] | None = None) -> list[str]:
    """unique_condition 15 列（与 wf_cursed_weapons.unique_row 同列序）+ wfx 约束；不合法即抛。

    icon 传图标短名（battle/common/unique_condition/ 之后的部分）。"""
    prefix = _registry()["unique_condition"]["icon_prefix"]
    row = [sid, name, f"{prefix}{icon}", str(duration), str(max_acc), "(None)", "(None)", "(None)",
           "(None)", "true" if cancelable else "false", "true" if force else "false",
           "1" if bad else "0", "0", "false" if keep_on_death else "true", "(None)"]
    problems = unique_row_problems(row, known_icons=known_icons)
    if problems:
        raise WfxError("；".join(problems))
    return row


def _is_positive_number(text: str) -> bool:
    try:
        return math.isfinite(float(text)) and float(text) > 0
    except ValueError:
        return False


def unique_row_problems(row: list[str], *, known_icons: Iterable[str] | None = None) -> list[str]:
    """wfx 效果行的行级约束（非 wfx 行返回 []）：

    - 15 列；sid 可解析且语义合法；
    - 叠层效果（stack_scaled）c4 必须写整数：(None) = 上限 1，层数全死（记忆 wf-unique-cap-none-trap）；
    - pin 效果 c9 可驱散必须 false；
    - 图标在已有图标集里（给了 known_icons 时），否则 C8004/C8016。
    """
    sid = row[0] if row and isinstance(row[0], str) else ""
    kind = classify_sid(sid)
    if kind is None:
        return []
    if kind == "reserved":
        return [f"string_id {sid!r} 使用保留前缀（{_registry()['sid']['reserved_prefixes']}），尚无客户端实现"]
    if kind == "lookalike":
        why = ("首尾带空白（客户端 split(\":\") 首段不是 wfx）" if sid != sid.strip()
               else f"不是已登记前缀 {sid_prefix()!r}（大小写/分隔符写错？）")
        return [f"string_id {sid!r} 以 wfx 开头但{why}：客户端不会当作效果状态，效果会静默失效；"
                "wfx 前缀整段保留给扩展词条框架"]
    problems: list[str] = []
    if len(row) != UNIQUE_COLUMNS:
        problems.append(f"unique_condition 行须 {UNIQUE_COLUMNS} 列，实为 {len(row)}")
    try:
        spec = parse_sid(sid)
    except WfxError as exc:
        return problems + [str(exc)]
    problems += spec_problems(spec)
    effect = spec.effect

    def cell(index: int) -> str:
        return (row[index] if index < len(row) else "").strip()

    if not cell(1) or any(ch in cell(1) for ch in "\r\n"):
        problems.append("c1 名称为空或含换行")
    icon_prefix = _registry()["unique_condition"]["icon_prefix"]
    icon = cell(2)
    if not icon.startswith(icon_prefix) or icon == icon_prefix:
        problems.append(f"c2 图标={icon!r} 须为 {icon_prefix}<已有图标>")
    elif known_icons is not None and icon[len(icon_prefix):] not in set(known_icons) \
            and icon not in set(known_icons):
        problems.append(f"c2 图标={icon!r} 不在已有图标集里（C8004/C8016）")
    if not _is_positive_number(cell(3)):
        problems.append(f"c3 持续帧={cell(3)!r} 须为正数")
    max_acc = cell(4)
    if max_acc != "(None)" and not (_UINT_RE.fullmatch(max_acc) and int(max_acc) >= 1):
        problems.append(f"c4 最大层={max_acc!r} 须为 (None) 或正整数")
    if effect is not None and effect.get("stack_scaled") and max_acc == "(None)":
        problems.append("c4 最大层=(None) 等于上限 1：叠层效果必须显式写整数上限（无上限写 99）")
    for index, name in ((9, "可驱散"), (10, "强制"), (13, "入棺移除")):
        if cell(index) not in ("true", "false"):
            problems.append(f"c{index} {name}={cell(index)!r} 须为 true/false")
    if cell(11) not in ("0", "1"):
        problems.append(f"c11 方向={cell(11)!r} 须为 0（正面）/1（负面）")
    if spec.pin and cell(9) == "true":
        problems.append("flags 带 pin（防全删）时 c9 可驱散必须为 false")
    return problems


def allocate_uid(existing: Iterable[str | int], start: int | None = None) -> int:
    """公共效果库 uid：从注册表 public_uid_pool_start 起取第一个未被占用的号。"""
    used = {str(item).strip() for item in existing}
    uid = start if start is not None else _registry()["unique_condition"]["public_uid_pool_start"]
    while str(uid) in used:
        uid += 1
    return uid


def uid_problems(uid: str | int, existing: Iterable[str | int]) -> list[str]:
    text = str(uid).strip()
    if not _UINT_RE.fullmatch(text) or int(text) == 0 or int(text) > _INT32_MAX:
        return [f"uid={uid!r} 须为 int32 范围内的正整数"]
    if text in {str(item).strip() for item in existing}:
        return [f"uid={text} 已被占用（撞号）"]
    return []

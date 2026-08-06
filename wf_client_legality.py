#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户端 AbilityValues.parseAt* 硬规则校验(与数据包无关)。

从 wf_gui 摘出来:写盘前的合法性门禁(wf_rogue_rewards._assert_soul_row_legal)
只需要这一个纯函数,但 wf_gui 在模块级解析 TARGET_STORE,导入即要求本机装好
数据包 —— 于是 CI/干净克隆里跑纯 fixture 的单元测试会直接 SystemExit。
本模块只依赖 wf_describe 的布局表,不碰任何 store。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf_describe  # noqa: E402  行级中文描述器(逆向布局+枚举直译)


def client_legality_problems(kind: str, row: list[str]) -> list[str]:
    """客户端 AbilityValues.parseAt* 硬规则(违者 C7050/7101 打开角色页即崩,2026-07-13 实锤):
    枚举列无空串分支,前置1-3/触发/内容 kind 必须数字;instant_precontent 哨兵 '(None)';
    during_accumulation_trigger 哨兵 '(None)';even_if_owner_dead 必须 true/false。"""
    lay = wf_describe.layout(kind)
    B = {k: int(v) for k, v in lay["blocks"].items()}
    tcol = B["precondition1"] - 1

    def cell(i):
        return (row[i] if i < len(row) else "").strip()

    def is_num(v):
        return bool(v) and v.lstrip("-").isdigit()

    probs = []
    tmode = cell(tcol)
    if tmode not in ("0", "1", "2"):
        return [f"c{tcol} 触发模式={tmode!r},须为 0(瞬发)/1(持续)/2(开幕)"]
    for p in ("precondition1", "precondition2", "precondition3"):
        v = cell(B[p])
        if not is_num(v):
            probs.append(f"c{B[p]} {p}.kind={v!r} 须为数字(无条件填 0;空串=客户端C7050)")
    if tmode == "0":
        for name, label in (("instant_trigger", "瞬发触发kind"),
                            ("instant_delay", "延迟"), ("instant_content", "瞬发效果kind")):
            v = cell(B[name])
            if not is_num(v):
                probs.append(f"c{B[name]} {label}={v!r} 须为数字(空串=客户端C7050)")
        v = cell(B["instant_precontent"])
        if v != "(None)" and not is_num(v):
            probs.append(f"c{B['instant_precontent']} instant_precontent={v!r} 须为 '(None)' 或数字")
    elif tmode == "1":
        v = cell(B["during_accumulation_trigger"])
        if v != "(None)" and not is_num(v):
            probs.append(f"c{B['during_accumulation_trigger']} 累积触发={v!r} 须为 '(None)' 或数字")
        v = cell(B["during_trigger"])
        if not is_num(v):
            probs.append(f"c{B['during_trigger']} 持续触发kind={v!r} 须为数字")
        v = cell(B["even_if_owner_dead"])
        if v.lower() not in ("true", "false"):
            probs.append(f"c{B['even_if_owner_dead']} even_if_owner_dead={v!r} 须为 true/false(否则C7101)")
        v = cell(B["during_content"])
        if not is_num(v):
            probs.append(f"c{B['during_content']} 持续效果kind={v!r} 须为数字")
    else:
        v = cell(B["opening"])
        if not is_num(v):
            probs.append(f"c{B['opening']} 开幕kind={v!r} 须为数字")
    return probs

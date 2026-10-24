"""原生说明器已证实的组合限制；不把战斗可执行等同于详情可渲染。"""
from __future__ import annotations

import re

import wf_describe

# InstantAbilitySource.as:3837/4191/4545/4557 均构造 ConditionChangeContent.Unique。
# ConditionChangeContent.as:209 将 Unique 定为 index 31；说明器 :148-149 将其
# multiply-strength 定为 None。仅拦这四种已追到同一 throw 的内容，不泛禁前置效果。
#
# 2026-09-07:instant_content 724 AddFeverPointRatio(客户端补丁 kyubi-fever-ratio-v1)
# **不属于**这一族 —— 它构造的不是 ConditionChangeContent.Unique,强度走普通
# Decimal 通道,说明器分支与 213 AddFeverPoint 同构,没有 Some(max)+None 的组合。
# 它的风险不在说明器而在解析器:未打补丁的客户端读到 724 直接 C7050,登记在
# wf_client_legality.CLIENT_PATCH_CONTENT_KINDS,不在本模块判。
UNIQUE_CONTENT_KINDS = frozenset({"413", "436", "459", "461"})


def _client_limit_is_one(value: str) -> bool:
    # AbilityValues.parseAt44 → Std.parseInt → AS3 int；空串/None 变 0。
    token = re.match(r"^[+-]?(?:0[xX][0-9a-fA-F]+|[0-9]+)", value.strip())
    if token is None:
        return False
    raw = token.group()
    number = int(raw, 16 if "x" in raw.lower() else 10)
    return (number & 0xFFFFFFFF) == 1


def description_compatibility_problems(kind: str, row: list[str]) -> list[str]:
    """覆盖 Unique + 带上限的前置后缀所触发的原生 C10010。"""
    blocks = wf_describe.layout(kind)["blocks"]
    cell = lambda col: (row[int(col)] if int(col) < len(row) else "").strip()
    content_col = int(blocks["instant_content"])
    precontent_col = int(blocks["instant_precontent"])
    if cell(int(blocks["precondition1"]) - 1) != "0":
        return []
    content = cell(content_col)
    if content not in UNIQUE_CONTENT_KINDS:
        return []
    limit_offset = next(int(offset) for offset, field, _ in
                        wf_describe.enum_map()["block_fields"]["instant_precontent"]
                        if field == "limit")
    precontent, limit = cell(precontent_col), cell(precontent_col + limit_offset)
    # Source.resolveInstantPrecontent:6097-6110 与说明器 resolve...Suffix:16220-16304：
    # Combo / ConsumeAll 始终 Some(max)；ConsumeUnique 固定 limit=1，走 None；
    # UniqueCondition 仅 limit=1 走 None。原始 limit 空串或 0 并非 None 后缀。
    suffix = precontent in {"0", "1"} or (precontent == "3" and not _client_limit_is_one(limit))
    if not suffix:
        return []
    # stringfyInstantAbilityContent:9731/9753/9760/9767 →
    # stringfyConditionAccordingToPrecontent:15939-15947，Some(max)+None 必抛。
    return [f"c{content_col} 内容 {content}(Unique) 与 c{precontent_col} "
            f"前置效果 {precontent}(limit={limit!r}) 组合会生成带上限的前置后缀；"
            "原生说明器不支持 Unique 强度乘算，角色详情 C10010"]

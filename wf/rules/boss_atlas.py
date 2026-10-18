"""Read actual three-party sheet dimensions; keep runtime packing uncertain."""
from __future__ import annotations

import struct

from .boss_common import CandidateView
from .catalog import result


def atlas_check(view, context):
    spec = context.get("atlas_budget")
    if not isinstance(spec, dict) or view is None:
        return result("art.atlas-budget", "未执行", "未提供三人队伍图集清单与候选 PNG，未执行组合预算")
    parties = spec.get("parties")
    if not isinstance(parties, list) or len(parties) != 3 or any(not isinstance(p, list) for p in parties):
        raise ValueError("atlas_budget.parties must identify exactly three party sheet lists")
    source, sheets, missing = CandidateView(view), [], []
    limitations = [f"第 {index + 1} 队未提供角色/技能/PF图集清单" for index, party in enumerate(parties) if not party]
    logicals = sorted(set(spec.get("enemy_sheets", [])) | {p for party in parties for p in party})
    if not logicals:
        return result("art.atlas-budget", "未执行", "三人房清单为空，未进行图集预算")
    for logical in logicals:
        raw = source.raw(logical)
        if raw is None or len(raw) < 24 or raw[1:4].lower() != b"png" or raw[12:16] != b"IHDR":
            missing.append(logical)
            continue
        width, height = struct.unpack(">II", raw[16:24])
        sheets.append({"logical": logical, "width": width, "height": height,
                       "padded_pixels": (width + 2) * (height + 2)})
    pixels = sum(sheet["padded_pixels"] for sheet in sheets)
    return result("art.atlas-budget", "待验证",
                  "已按三人组合实际 PNG 尺寸去重估算；未执行运行时装箱/真机，历史约15.2Mpx失败点不是通用硬门槛",
                  padded_pixels=pixels, nominal_capacity=4096 ** 2, sheets=sheets, missing=missing,
                  near_historical_failure=pixels >= 15_200_000, runtime_executed=False,
                  party_coverage_complete=not limitations, limitations=limitations)

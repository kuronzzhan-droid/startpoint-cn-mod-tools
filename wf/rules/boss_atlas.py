"""Read actual three-party sheet dimensions; keep runtime packing uncertain."""
from __future__ import annotations

import struct

from .boss_common import CandidateView
from .catalog import result

HISTORICAL_RANDOM_MAX = 14_610_000
HISTORICAL_FAILURE_START = 15_200_000


def atlas_check(view, context):
    spec = context.get("atlas_budget")
    if not isinstance(spec, dict) or view is None:
        return result("art.atlas-budget", "未执行", "未提供三人队伍图集清单与候选 PNG，未执行组合预算")
    parties = spec.get("parties")
    if not isinstance(parties, list) or len(parties) != 3 or any(not isinstance(p, list) for p in parties):
        raise ValueError("atlas_budget.parties must identify exactly three party sheet lists")
    source, sheets, missing = CandidateView(view), [], []
    party_limitations = [f"第 {index + 1} 队未提供角色/技能/PF图集清单" for index, party in enumerate(parties) if not party]
    limitations = party_limitations + list(spec.get("limitations", []))
    logicals = sorted(set(spec.get("enemy_sheets", [])) | {p for party in parties for p in party})
    if not logicals and not spec.get("enemy_lower_bound"):
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
    overflow = pixels > 4096 ** 2
    source_quest = str(spec.get("source_quest", ""))
    known_heavy_source = source_quest in {"1099031", "boss_battle:1/99/31"}
    message = ("已知图集加边距面积超过4096²，三人房必超容量，阻断交付" if overflow else
               "已按候选PNG估算敌方/队伍图集下界；三人房仍待验证，不能据此判为通过")
    if pixels >= HISTORICAL_RANDOM_MAX or known_heavy_source:
        message += "；警报：达到历史随机三人房最大14.61Mpx，或来源为该记录的五重1099031"
    message += "；历史15.2–16.2Mpx失败区间不是通用硬门槛"
    return result("art.atlas-budget", "问题" if overflow else "待验证", message, blocking=overflow,
                  padded_pixels=pixels, nominal_capacity=4096 ** 2, sheets=sheets, missing=missing,
                  near_historical_failure=pixels >= HISTORICAL_FAILURE_START, runtime_executed=False,
                  near_historical_max=pixels >= HISTORICAL_RANDOM_MAX,
                  historical_reference={"version": "1.4.210", "source_quest": "1099031",
                                        "random_three_party_max_pixels": HISTORICAL_RANDOM_MAX,
                                        "failure_range_pixels": [15_200_000, 16_200_000],
                                        "source": "wf-atlas-budget-1016", "current_runtime_proof": False},
                  source_quest=source_quest, known_heavy_source=known_heavy_source,
                  enemy_lower_bound=bool(spec.get("enemy_lower_bound")),
                  unresolved_programs=spec.get("unresolved_programs", []),
                  party_coverage_complete=not party_limitations, limitations=limitations)

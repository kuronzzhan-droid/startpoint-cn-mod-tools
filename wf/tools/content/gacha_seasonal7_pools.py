# -*- coding: utf-8 -*-
"""七角色季节换装版入池 + 小Boss/上批五人概率与兑换修订（作者 2026-09-17）。

作者原话：

    批5个角色和15个小boss角色在深渊池概率改为0.1%并加入兑换，
    小boss兑换排在mod角色后面官方角色前面；
    这次7个角色加入深渊池概率0.2%且不可兑换；
    这次7个角色加入竞速池概率1%置顶，开启兑换；
    竞速池的15个小boss兑换排序也是mod角色后面官方角色前面。

## 概率口径

显示概率 = 档位% × 角色权重 / 本档权重合计（推导见 `wf_gacha_odds_sync`）。
两个卡池都被设计成「五星档权重合计恒定」：

    990001 深渊  5★ 15.0%，rank-1 合计 150000  ⇒ 显示% = odds / 10000
    990002 竞速  5★ 95.0%，rank-1 合计 950000  ⇒ 显示% = odds / 10000

所以 0.1% = 1000、0.2% = 2000、1% = 10000，**官方角色吃掉余数**（最大余数法），
合计严格不变；这也是本轮唯一会连带变动的一批数值（深渊官方 0.035%→0.039%、
竞速官方 0.220%→0.190%），是固定合计下的必然结果，不是额外改动。

## 排序口径

池内数组顺序同时决定「提供概率」页与兑换列表的顺序。两池统一成：

    [本次7人] → [其余 mod 角色（含 0% 的大 Boss 系列）] → [15 小 Boss] → [官方角色]

深渊池本来就是「mod → 小Boss → 官方」，本轮只把 7 人置顶；
竞速池原本小 Boss 在最前，本轮按同一口径挪到 mod 之后、官方之前。
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction

import wf_content_gacha as rules

ABYSS = "990001"
RACING = "990002"

# 本次七角色（季节换装版），顺序即池内置顶顺序
SEASONAL7 = (139994, 139993, 159998, 159997, 159996, 169992, 129991)
# 上一批五个角色：深渊池里原本 0.25% 且不可兑换
PREV_BATCH = (149990, 119989, 149989, 169989, 149988)
MINIBOSSES = rules.MINIBOSSES

ABYSS_TOTAL = 150000
RACING_TOTAL = 950000
ABYSS_RANK_RATES = [150, 350, 500]
RACING_RANK_RATES = [950, 20, 30]

W_ABYSS_SEASONAL7 = 2000   # 0.2%
W_ABYSS_TENTH = 1000       # 0.1%
W_RACING_PERCENT = 10000   # 1%

# 自制角色 ID 自留段：末四位 >= 9950（与两池现有分组逐行核对过）
CUSTOM_ID_FLOOR = 9950


class PoolRevisionError(ValueError):
    pass


def is_custom(cid: int) -> bool:
    return int(cid) % 10000 >= CUSTOM_ID_FLOOR


def _entries(pool: dict) -> list[dict]:
    return pool["pool"]["1"]


def _by_id(pool: dict) -> dict[int, dict]:
    entries = _entries(pool)
    table = {int(e["id"]): e for e in entries}
    if len(table) != len(entries):
        raise PoolRevisionError("卡池存在重复角色行")
    return table


def _new_entry(cid: int, odds: int, *, exchangeable: bool) -> dict:
    return {
        "id": int(cid),
        "rank": 5,
        "odds": int(odds),
        "isRateUp": True,
        "isLimited": True,
        "isExchangeable": bool(exchangeable),
        "trialReadingForced": False,
    }


def _order(table: dict[int, dict]) -> list[int]:
    """[本次7人] → [其余 mod] → [15 小 Boss] → [官方]，块内保持原相对顺序。"""
    ids = list(table)
    minis = [cid for cid in ids if cid in MINIBOSSES]
    officials = [cid for cid in ids if not is_custom(cid)]
    mods = [cid for cid in ids
            if is_custom(cid) and cid not in MINIBOSSES and cid not in SEASONAL7]
    return list(SEASONAL7) + mods + minis + officials


def _finalize(pool: dict, order: list[int], fixed: dict[int, int], total: int) -> None:
    """按给定顺序重排，固定权重照写，其余（官方）按原相对权重分掉余数。"""
    table = _by_id(pool)
    if sorted(order) != sorted(table):
        raise PoolRevisionError("重排后的角色集合与原集合不一致")
    flexible = {cid: int(e["odds"]) for cid, e in table.items() if cid not in fixed}
    remainder = total - sum(fixed.values())
    if remainder < 0:
        raise PoolRevisionError("固定权重已超出五星档合计")
    weights = rules.allocate(flexible, remainder)
    weights.update(fixed)
    result = []
    for cid in order:
        entry = deepcopy(table[cid])
        entry["odds"] = weights[cid]
        entry["rarity"] = round(weights[cid] * 100 / total, 6)
        result.append(entry)
    if sum(e["odds"] for e in result) != total:
        raise PoolRevisionError("五星档权重合计发生变化")
    pool["pool"]["1"] = result


def _check_baseline(pool: dict, pool_id: str, rank_rates: list[int], total: int) -> None:
    if pool["rankRates"]["normal"] != rank_rates:
        raise PoolRevisionError(f"{pool_id}: 五星档率与基线不符")
    if sum(int(e["odds"]) for e in _entries(pool)) != total:
        raise PoolRevisionError(f"{pool_id}: 五星档权重合计与基线不符")
    table = _by_id(pool)
    if set(SEASONAL7) & set(table):
        raise PoolRevisionError(f"{pool_id}: 七角色已在池中，本工具只负责首次入池")
    if not MINIBOSSES <= set(table):
        raise PoolRevisionError(f"{pool_id}: 缺少 15 个小 Boss 行")
    if any(not is_custom(cid) for cid in MINIBOSSES):
        raise PoolRevisionError("小 Boss 名单落在自制 ID 段之外")


def revise_abyss(pool: dict) -> None:
    _check_baseline(pool, ABYSS, ABYSS_RANK_RATES, ABYSS_TOTAL)
    table = _by_id(pool)
    if set(PREV_BATCH) - set(table):
        raise PoolRevisionError("深渊池缺少上一批五个角色")
    for cid in tuple(PREV_BATCH) + tuple(sorted(MINIBOSSES)):
        table[cid]["isExchangeable"] = True
    for cid in SEASONAL7:
        _entries(pool).append(_new_entry(cid, W_ABYSS_SEASONAL7, exchangeable=False))

    table = _by_id(pool)
    order = _order(table)
    fixed = {cid: W_ABYSS_SEASONAL7 for cid in SEASONAL7}
    fixed.update({cid: W_ABYSS_TENTH for cid in PREV_BATCH})
    fixed.update({cid: W_ABYSS_TENTH for cid in MINIBOSSES})
    # 其余 mod 角色保持各自现有权重（0.1% 的仍 0.1%，0% 的仍 0%）
    fixed.update({cid: int(e["odds"]) for cid, e in table.items()
                  if is_custom(cid) and cid not in fixed})
    _finalize(pool, order, fixed, ABYSS_TOTAL)


def revise_racing(pool: dict) -> None:
    _check_baseline(pool, RACING, RACING_RANK_RATES, RACING_TOTAL)
    for cid in SEASONAL7:
        _entries(pool).append(_new_entry(cid, W_RACING_PERCENT, exchangeable=True))

    table = _by_id(pool)
    order = _order(table)
    fixed = {cid: W_RACING_PERCENT for cid in SEASONAL7}
    # 其余自制角色（含小 Boss 与 0% 大 Boss）保持各自现有权重
    fixed.update({cid: int(e["odds"]) for cid, e in table.items()
                  if is_custom(cid) and cid not in fixed})
    _finalize(pool, order, fixed, RACING_TOTAL)


def probability(pool: dict, cid: int) -> Fraction:
    return rules.probability(pool, cid)


def _assert_block_order(pool: dict, name: str) -> None:
    ids = [int(e["id"]) for e in _entries(pool)]
    index = {cid: i for i, cid in enumerate(ids)}
    first_mini = min(index[cid] for cid in MINIBOSSES)
    last_mini = max(index[cid] for cid in MINIBOSSES)
    last_mod = max(index[cid] for cid in ids if is_custom(cid) and cid not in MINIBOSSES)
    first_official = min(index[cid] for cid in ids if not is_custom(cid))
    if not (last_mod < first_mini and last_mini < first_official):
        raise PoolRevisionError(f"{name}: 小 Boss 未排在 mod 之后、官方之前")
    if ids[:len(SEASONAL7)] != list(SEASONAL7):
        raise PoolRevisionError(f"{name}: 七角色未置顶")


def revise(gacha: dict) -> dict:
    result = deepcopy(gacha)
    revise_abyss(result[ABYSS])
    revise_racing(result[RACING])

    abyss, racing = result[ABYSS], result[RACING]
    for cid in SEASONAL7:
        if probability(abyss, cid) != Fraction(2, 1000):
            raise PoolRevisionError(f"深渊 {cid} 不是 0.2%")
        if probability(racing, cid) != Fraction(1, 100):
            raise PoolRevisionError(f"竞速 {cid} 不是 1%")
    for cid in tuple(PREV_BATCH) + tuple(sorted(MINIBOSSES)):
        if probability(abyss, cid) != Fraction(1, 1000):
            raise PoolRevisionError(f"深渊 {cid} 不是 0.1%")
        if not _by_id(abyss)[cid]["isExchangeable"]:
            raise PoolRevisionError(f"深渊 {cid} 应为可兑换")
    for cid in sorted(MINIBOSSES):
        if probability(racing, cid) != Fraction(1, 100):
            raise PoolRevisionError(f"竞速 {cid} 不再是 1%")
    for cid in SEASONAL7:
        if _by_id(abyss)[cid]["isExchangeable"]:
            raise PoolRevisionError(f"深渊 {cid} 应为不可兑换")
        if not _by_id(racing)[cid]["isExchangeable"]:
            raise PoolRevisionError(f"竞速 {cid} 应为可兑换")
    _assert_block_order(abyss, ABYSS)
    _assert_block_order(racing, RACING)
    if any(result[k] != v for k, v in gacha.items() if k not in (ABYSS, RACING)):
        raise PoolRevisionError("改动外溢到了其他卡池")
    for pool_id in (ABYSS, RACING):
        for key, value in gacha[pool_id].items():
            if key != "pool" and result[pool_id][key] != value:
                raise PoolRevisionError(f"{pool_id}: 卡池头部字段被改动 ({key})")
        for group in ("2", "3"):
            if result[pool_id]["pool"].get(group) != gacha[pool_id]["pool"].get(group):
                raise PoolRevisionError(f"{pool_id}: 四星/三星档被改动")
    return result

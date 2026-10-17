# -*- coding: utf-8 -*-
"""中秋批次 12 个角色入深渊池与竞速池：概率 0%、不可兑换（作者 2026-09-21）。

作者原话：

    这次的角色全部(除了两个水属性的老男人)加入深渊和竞速池概率0%不可兑换

「两个水属性的老男人」＝冈达葛萨 129987、索利兹 129986，**不入池**（见 `WATER_PAIR`）。
其余 12 人名单与顺序取自 `wf_midautumn_specs.SPECS` 的声明序（火→雷→风→光→暗），
在这里冻结成常量，由门禁 `tests/test_gacha_midautumn_pools.py` 反过来核对两者一致。

## 概率口径

沿用 `wf_gacha_seasonal7_pools` 的算术（推导见该模块与 `wf_gacha_odds_sync`）：

    990001 深渊  5★ 15.0%，rank-1 权重合计 150000  ⇒ 显示% = odds / 10000
    990002 竞速  5★ 95.0%，rank-1 权重合计 950000  ⇒ 显示% = odds / 10000

本轮写入的权重是 **0**，所以：

* 五星档权重合计天然不变（0 不占份额），官方行的余数**一格都不用重分**；
* 除这 12 行以外，两池每一行都必须逐字段与改前相同 —— 由 `_verify_pool` 硬断言守住；
* 客户端「提供概率」页显示 `0.000%`（`GachaOddsTools.formatOdds` floor 到 3 位）；
* 服务端真抽取不到：`selectWeightedIndexByRoll` 的 roll 从 1 起、0 权重不推进 offset，
  0 权重行永远轮不到（`src/lib/gacha.ts`）。

## 逐格先例

竞速池里早就有一整批「0% 挂名行」（六荒龙／六精灵兽／七蒸汽机兵等 20 行），
本次新行逐格照抄它们的写法，连键序都一致：

    {"id":119950,"rank":5,"odds":0,"isRateUp":false,"isLimited":true,
     "isExchangeable":false,"rarity":0.0,"trialReadingForced":false}

`isRateUp` 跟着先例写 `false`：0% 的行挂「UP」标是自相矛盾的。
服务端门禁 `src/tests/gacha-exchangeable.test.ts` 也明确放行这一类
（「不可兑换只允许两种来源：tag_boss 角色，或权重 0 的挂名行」），所以 12 行
不可兑换不会把那条测试打红。

## 排序口径

池内数组顺序 ＝「提供概率」页顺序 ＝ 兑换列表顺序。沿用上一批的规则，
把**最新一批**放在最前，其余块保持原相对顺序：

    [本批 12 人] → [其余 mod 角色（含季节 7 人与 0% 大 Boss 系列）] → [15 小 Boss] → [官方]

这 12 行是 0%，页面顶端会出现 12 行 `0.000%`；仍按「最新一批置顶」处理，理由：
①两池的 0% 行并不聚成一块（深渊只有 1 行、竞速那 20 行夹在 mod 块中段），
「放到 0% 系列旁边」没有唯一落点；②不可兑换 ⇒ 它们不会进兑换列表，排序只影响概率页；
③概率页的作用是披露，把最新一批摆在最前、明写 0%，比埋进 287/311 行里更诚实。
要改成不置顶，只需改 `_order()` 里 `MIDAUTUMN12` 的位置（门禁会跟着红，需同步改断言）。
"""
from __future__ import annotations

import math
from copy import deepcopy
from fractions import Fraction

import wf_gacha_seasonal7_pools as s7

ABYSS = s7.ABYSS
RACING = s7.RACING
ABYSS_TOTAL = s7.ABYSS_TOTAL
RACING_TOTAL = s7.RACING_TOTAL
MINIBOSSES = s7.MINIBOSSES
SEASONAL7 = s7.SEASONAL7

# (卡池, 五星档率基线, rank-1 权重合计基线)
POOL_SPECS = (
    (ABYSS, s7.ABYSS_RANK_RATES, ABYSS_TOTAL),
    (RACING, s7.RACING_RANK_RATES, RACING_TOTAL),
)

# 中秋批次 12 人，顺序 = wf_midautumn_specs.SPECS 声明序 = 池内置顶顺序
MIDAUTUMN12 = (
    119992,  # 米娅   tiger_treasure_hunter_moon
    119991,  # 妮可拉 sorceress_teacher_moon
    119990,  # 马格努斯 lion_swordman_moon
    139992,  # 夏琳   artificialeye_sniper_moon
    139991,  # 黑     outlaw_panther_moon
    139990,  # 凯尔   kyle_moon
    149987,  # 芙拉菲 combat_animal_moon
    149986,  # 罗尔夫 black_wolf_knight_moon
    159995,  # 丝缇涅尔 still_obstinator_moon
    159994,  # 索恩   tweyen_light
    169991,  # 蕾贝卡 bearish_darkwitch_moon
    169988,  # 澄波响 psychic_teleport_moon
)
# 作者点名不入池的「两个水属性的老男人」
WATER_PAIR = (129987, 129986)

is_custom = s7.is_custom
probability = s7.probability


class MidautumnPoolError(s7.PoolRevisionError):
    """继承 seasonal7 的异常类型，`except PoolRevisionError` 能一并接住。"""


def _zero_entry(cid: int) -> dict:
    """0% 挂名行：逐格（含键序）照抄竞速池现有的大 Boss 系列写法。"""
    return {
        "id": int(cid),
        "rank": 5,
        "odds": 0,
        "isRateUp": False,
        "isLimited": True,
        "isExchangeable": False,
        "rarity": 0.0,
        "trialReadingForced": False,
    }


def _order(table: dict[int, dict]) -> list[int]:
    """[本批 12 人] → [其余 mod] → [15 小 Boss] → [官方]，块内保持原相对顺序。"""
    ids = list(table)
    minis = [cid for cid in ids if cid in MINIBOSSES]
    officials = [cid for cid in ids if not is_custom(cid)]
    mods = [cid for cid in ids
            if is_custom(cid) and cid not in MINIBOSSES and cid not in MIDAUTUMN12]
    return list(MIDAUTUMN12) + mods + minis + officials


def _check_constants() -> None:
    if len(set(MIDAUTUMN12)) != len(MIDAUTUMN12):
        raise MidautumnPoolError("MIDAUTUMN12 有重复 ID")
    if len(MIDAUTUMN12) != 12:
        raise MidautumnPoolError("MIDAUTUMN12 不是 12 人")
    if set(MIDAUTUMN12) & set(WATER_PAIR):
        raise MidautumnPoolError("两个水属性角色被误列进入池名单")
    for cid in MIDAUTUMN12:
        if not is_custom(cid):
            raise MidautumnPoolError(f"{cid} 不在自制 ID 段内")


def _check_baseline(pool: dict, pool_id: str, rank_rates: list[int], total: int) -> None:
    if pool.get("rankRates", {}).get("normal") != rank_rates:
        raise MidautumnPoolError(f"{pool_id}: 五星档率与基线不符")
    entries = s7._entries(pool)
    if sum(int(e["odds"]) for e in entries) != total:
        raise MidautumnPoolError(f"{pool_id}: 五星档权重合计与基线不符")
    table = s7._by_id(pool)          # 顺带查重复行
    if not MINIBOSSES <= set(table):
        raise MidautumnPoolError(f"{pool_id}: 缺少 15 个小 Boss 行")


def revise_pool(pool: dict, pool_id: str, rank_rates: list[int], total: int) -> int:
    """把 12 人以 0%／不可兑换写进 `pool`（就地改），返回被收回的权重。

    已在池内的角色改成 0／不可兑换，不重复追加 —— 所以本函数幂等。
    """
    _check_constants()
    _check_baseline(pool, pool_id, rank_rates, total)

    table = s7._by_id(pool)
    reclaimed = sum(int(table[cid]["odds"]) for cid in MIDAUTUMN12 if cid in table)
    for cid in MIDAUTUMN12:
        entry = table.get(cid)
        if entry is None:
            s7._entries(pool).append(_zero_entry(cid))
            continue
        entry["odds"] = 0
        entry["rarity"] = 0.0
        entry["isExchangeable"] = False
        entry["isRateUp"] = False      # 0% 行不该挂 UP 标，与 0% 先例一致

    table = s7._by_id(pool)
    # 自制角色一律固定权重（本批 12 人强制 0），只有官方行参与余数分配
    fixed = {cid: int(e["odds"]) for cid, e in table.items() if is_custom(cid)}
    fixed.update({cid: 0 for cid in MIDAUTUMN12})
    s7._finalize(pool, _order(table), fixed, total)
    return reclaimed


def _verify_pool(before: dict, after: dict, pool_id: str, total: int, reclaimed: int) -> None:
    rows_before = {int(e["id"]): e for e in s7._entries(before)}
    rows_after = {int(e["id"]): e for e in s7._entries(after)}

    if sum(int(e["odds"]) for e in rows_after.values()) != total:
        raise MidautumnPoolError(f"{pool_id}: 五星档权重合计发生变化")
    added = set(rows_after) - set(rows_before)
    if added != set(MIDAUTUMN12) - set(rows_before):
        raise MidautumnPoolError(f"{pool_id}: 新增行不等于本批 12 人")
    if set(rows_before) - set(rows_after):
        raise MidautumnPoolError(f"{pool_id}: 有角色被挤出卡池")
    if set(WATER_PAIR) & added:
        raise MidautumnPoolError(f"{pool_id}: 两个水属性角色被写进了卡池")

    for cid in MIDAUTUMN12:
        entry = rows_after[cid]
        if int(entry["odds"]) != 0 or entry["rarity"] != 0.0:
            raise MidautumnPoolError(f"{pool_id}/{cid}: 权重不是 0")
        if probability(after, cid) != Fraction(0):
            raise MidautumnPoolError(f"{pool_id}/{cid}: 实际概率不是 0")
        if entry["isExchangeable"]:
            raise MidautumnPoolError(f"{pool_id}/{cid}: 应为不可兑换")
        if set(entry) != set(_zero_entry(cid)):
            raise MidautumnPoolError(f"{pool_id}/{cid}: 字段集合与 0% 先例不一致")

    keep = [cid for cid in rows_before if cid not in MIDAUTUMN12]
    if reclaimed == 0:
        for cid in keep:                       # 没有权重被收回 ⇒ 其余行必须逐字段不变
            if rows_after[cid] != rows_before[cid]:
                raise MidautumnPoolError(f"{pool_id}/{cid}: 与本次无关的行被改动")
    else:                                      # 收回的权重只准流向官方行
        for cid in keep:
            if is_custom(cid) and rows_after[cid] != rows_before[cid]:
                raise MidautumnPoolError(f"{pool_id}/{cid}: 自制角色行被改动")
        official = [cid for cid in keep if not is_custom(cid)]
        moved = sum(int(rows_after[c]["odds"]) for c in official) \
            - sum(int(rows_before[c]["odds"]) for c in official)
        if moved != reclaimed:
            raise MidautumnPoolError(f"{pool_id}: 收回的权重没有全部流向官方行")

    for key, value in before.items():
        if key != "pool" and after[key] != value:
            raise MidautumnPoolError(f"{pool_id}: 卡池头部字段被改动 ({key})")
    for group in ("2", "3"):
        if after["pool"].get(group) != before["pool"].get(group):
            raise MidautumnPoolError(f"{pool_id}: 四星/三星档被改动")

    _assert_block_order(after, pool_id)


def _assert_block_order(pool: dict, pool_id: str) -> None:
    ids = [int(e["id"]) for e in s7._entries(pool)]
    if ids[:len(MIDAUTUMN12)] != list(MIDAUTUMN12):
        raise MidautumnPoolError(f"{pool_id}: 本批 12 人未置顶")
    index = {cid: i for i, cid in enumerate(ids)}
    first_mini = min(index[cid] for cid in MINIBOSSES)
    last_mini = max(index[cid] for cid in MINIBOSSES)
    last_mod = max(index[cid] for cid in ids if is_custom(cid) and cid not in MINIBOSSES)
    first_official = min(index[cid] for cid in ids if not is_custom(cid))
    if not (last_mod < first_mini and last_mini < first_official):
        raise MidautumnPoolError(f"{pool_id}: 小 Boss 未排在 mod 之后、官方之前")


def revise(gacha: dict) -> dict:
    """纯函数：返回改好的整份 gacha（输入不动）。重复调用结果相同。"""
    _check_constants()
    result = deepcopy(gacha)
    for pool_id, rank_rates, total in POOL_SPECS:
        if pool_id not in result:
            raise MidautumnPoolError(f"gacha 里没有卡池 {pool_id}")
        reclaimed = revise_pool(result[pool_id], pool_id, rank_rates, total)
        _verify_pool(gacha[pool_id], result[pool_id], pool_id, total, reclaimed)
    if any(result[k] != v for k, v in gacha.items() if k not in (ABYSS, RACING)):
        raise MidautumnPoolError("改动外溢到了其他卡池")
    return result


def display_percent(pool: dict, cid: int) -> str:
    """客户端「提供概率」页会显示的串（与 `wf_gacha_odds_sync.fmt_odds` 同一套 floor 规则）。"""
    rank_pct = pool["rankRates"]["normal"][0] / 10.0
    total = sum(int(e["odds"]) for e in s7._entries(pool))
    odds = int(s7._by_id(pool)[int(cid)]["odds"])
    return f"{math.floor(rank_pct * odds / total * 1000 + 2e-10) / 1000:.3f}"

# -*- coding: utf-8 -*-
"""稻穗「秋灯雷华妖狐姬」（139995 fox_oracle_autumn，雷）：2026-09-27 第三轮（成长复核）。

作者原话（主会话 2026-09-27 逐字转述，按时间顺序）：
「部分角色技能都倍率成长也要无限成长,成长条件放到队长技里面带上对应共鸣条件,凯尔的成长降太低了,本身数值就不高,
很多角色成长过于缓慢,也要基于角色本身的其他词条判断,比如部分角色没有基础刃值只能靠成长」／「成长速度砍到1/10不合理,
现在本来就算是正常偏快而已,砍太多了」／「砍到4/5,或者7/10这样吧,很多角色没有成长完全没用了」／「可以砍到2/3」／
「数值尽量取5的倍数比如36就变成35,39就变成40」。

按 live 链尾 1.4.1053 推导：第二批 ``wf_balance_20260927b_inaho``（1.4.1051）把 5 条「余辉」每层队长行 ×1/5；
``wf_balance_20260927b_inaho2``（1.4.1053）把「进 Fever 余辉 +1」从能力1 搬到能力3 末尾（队长行未动）。行号 0 基（``#n``）。

改动（数值表 reeval_full.json 稻穗 L#1 / L#4 / L#5–L#6 / L#9；只改强度 c111/c112，其余逐格保留）：
    #1 雷队 Fever 获得量（during 134 → 18）     8% → 30%  （原 40% × 4/5 = 32，就近取 30，实际 3/4）
    #4 自身强化弹射伤害（→ 23）                32% → 110%（原 160% × 7/10 = 112，就近取 110，实际 0.69 ≥ 2/3）
    #5 雷队攻击力（→ 0）                       32% → 130%（原 160% × 4/5 = 128，就近取 130）
    #6 雷队能力伤害（→ 154）                   32% → 130%（同上）
    #9 自身独立乘区强化弹射伤害（→ 413）        1% → 3.5%（原 5% × 7/10 = 3.5；<10% 按 0.5 取整，口径 D2）
余辉来源（数值表 L#1 触发描述已过期，按 live 更正）：当队长时每次进 Fever = 队长 #10 + 能力3 #8 两源同 unique 相加
（inaho2 搬行后），+2 层不变；本模块只读核对这两行，不改。3 分钟约 16 层（推断）。
不新增共鸣前置（口径 D3；五行本来就带「雷编成≥6」前置 kind 2）。
取整后 #1 实际 3/4，会加快「Fever → 余辉层数」的正反馈（数值表提示作者留意）。

面板 ``desc_override_fox_oracle_autumn``（队长）：末行数值同步 8/32/1/32 → 30/110/3.5/130（数字按行值渲染）= 数值稿；
不写「（可无限累积）」等禁语。技能描述 / character_text / 服务端文本不含这些数值（测试核对）。

面板同条件合并与共鸣省略（作者「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,引擎点火
提供的效果就不用写火属性共鸣,其他角色类似」；主会话合并规则）：
- 共鸣省略：固有「余辉」1399952 的全部获取来源 = 队长 #10、能力3 #8（kind 461，均带「雷编成≥6」前置 kind 2 / Yellow）；
  live 1.4.1054 全部队长/能力表 + 1476 个可枚举 DSL（技能、换形、629、PF）只读扫描无其他来源（与主会话 scan.json
  all_states 一致）⇒ 「余辉」层数/持有提供的效果不写「雷属性共鸣时，」：第 5 行（余辉≥10、非 Fever，强化弹射回
  Fever；数据 = 能力6 #1）、第 6 行（余辉每层；数据 = 队长 #1/#4/#5/#6/#9）删前缀，其余字面逐字不变；数据前置不动。
  第 4 行是「余辉」获取行，保留共鸣。余辉非队长 1 层 / 队长 2 层是作者确认的设计，第 4 行文案不改这层含义。
  依据核查补记（总核对 minor）：store 里另有 629 程序 ``ability_skill/ability_fox_oracle_autumn_fever_growth``，树内
  CreateCondition(ACUnique 1399952) 只在 ``ConditionalsConditionExist(-17, DCUnique 1399952)`` 的成立支里——只在自身
  已有「余辉」时刷新/叠加，不能给出首层；live ability（3525 键）/ leader_ability（588 键）无任何行引用它，平表键
  ``ability_fox_oracle_autumn_fever_growth`` 也已不在 live（V12 包移除，程序文件是 store 里的孤儿）⇒ 不是获取来源，
  省略结论不变；登记在 notes ``panel_merge.resonance_omission_refresh_only``（将来若有行调用它，须重新核查）。
- 同条件合并：队长同条件组 #1/#4/#5/#6/#9 已在同一行（第 6 行）；#0/#7/#8 只有 #0 有文案行；#2（第 2 行）与 #10
  （第 4 行，获取行，后缀「（最多99层）」）后缀不同不并 ⇒ 无可合并组。
- 共鸣写法统一（主会话口径 3：本轮返回的覆盖面板里「X属性共鸣时：」统一成「X属性共鸣时，」，冒号后换行接效果的并成
  一行）：能力6 面板 ``desc_override_fox_oracle_autumn_6`` live 为「雷属性共鸣时：」+ 换行 +
  「FEVER模式中，独立乘区的强化弹射伤害提升30％」⇒ 改为一行「雷属性共鸣时，FEVER模式中，独立乘区的强化弹射伤害提升30％」，
  其余字面逐字不变（数据 = 能力6 #0：雷编成≥6、持续·Fever、自身独立乘区强化弹射伤害 15%→30%，文案按满级写单一数值）。
  能力6 #0/#1 条件不同，无同条件组；#1（余辉门槛、仅队长）的文案在队长面板第 5 行。
- 其他覆盖面板：能力2（两条数据行条件不同、无共鸣前缀）无同条件组、无可省略共鸣，不返回；
  能力3/4/5 是客户端自动生成面板（无覆盖文案），按主会话口径不新建覆盖。
- 强化弹射伤害不补对象（主会话口径 1，暂存前最后一轮扩到同形写法 A：凡「…、强化弹射伤害…」接在带对象的效果后面，一律改
  「，强化弹射伤害…」，不论 kind 55 / during 23 / 413）：第 6 行「雷属性角色的FEVER获得量提升30％、强化弹射伤害提升110％」
  → 「…30％，强化弹射伤害提升110％」（数据 = 队长 #1 kind 18 对象 全队雷、#4 during 23 自身、不补「自身」）。
  其后「、独立乘区的强化弹射伤害提升3.5％」（#9 413）接在同为强化弹射伤害、不带对象的一项后面，「、雷属性角色的…」自带对象，
  都不属 A 的形，保留「、」。只动这一个标点，其余字面逐字不变（:func:`pf_damage_join_problems` 拒绝残留的
  「对象效果、强化弹射伤害」写法；:func:`pf_damage_join_basis_problems` 只读核对数据）。

生成器：这些键没有可重跑的现行生成器（第二批模块已核对历史链全部哈希锁定）；本模块是 ``leader:139995`` 余辉每层 5 行的
强度与 ``desc_override_fox_oracle_autumn`` / ``_6`` 现行的唯一写入源（``_6`` 是 2026-09-09/10 回写的固定文案，
mod-tools 与 work/ 下没有生成它的脚本）。行号漂移影响：本轮不移行，秋水 soriz 的 donor
（``wf_gbf_kit_soriz`` 按内容取 1399951 的 724 行）不受影响。

纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；接口见
``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``（第三轮 c 后缀）。
"""
from __future__ import annotations

from copy import deepcopy
import re

import wf_balance_20260927b_inaho as B2
import wf_client_legality as legality
import wf_midautumn_kitlib as KL

CID = B2.CID                      # "139995"
CODE = B2.CODE                    # "fox_oracle_autumn"
PACKAGES = ["fox_oracle_autumn"]
#: 候选 manifest 现值 0.20260927.2（inaho2 回写）→ 递增。
PACKAGE_VERSION = {"fox_oracle_autumn": "0.20260927.3"}
#: 队长覆盖文案需要 V11 面板覆盖补丁（候选 manifest 已登记，第二批同声明）。
CAPABILITIES = ["kyubi-panel-description-override-v1"]
#: 候选 fox_oracle_autumn 与 live 在本模块读取的键上逐字相同、manifest 零哈希漂移（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}
ELEMENT = B2.ELEMENT              # 2 = 雷（0 基内部元素）

LEADER = CID
ABILITY3 = f"{CID}3"              # 只读：核对余辉第二个来源（inaho2 搬入的末行）
PANEL = B2.PANEL                  # desc_override_fox_oracle_autumn
PANEL6 = PANEL + "_6"             # 能力6 覆盖面板（口径 3：共鸣冒号换行 → 一行）
AFTERGLOW = B2.AFTERGLOW          # 固有「余辉」1399952（上限 99）

#: live 1.4.1053 只读取数（stage_batch.make_read(live_only=True) 同法）；值 = digest(read(kind, key))。
#: leader / cas = 第二批 inaho 输出；ability 1399953 = inaho2 输出（本模块只读）。
BEFORE = {
    ("leader", LEADER): "32f678eefb352cdbefc224e98fffe98186ffbfdc802ac9cd5bf42437898b3e8b",
    ("ability", ABILITY3): "1a10b68b444ea61e4462b94d6c1ea46d05f8e844f4f028c360d233116633dc0b",
    ("cas", PANEL): "651a33fa79240c01ca97f0d3251a65bdd2142b30eb112b8642936c487924b20f",
    # 口径 3 新增（live 1.4.1054 只读取数）：能力6 覆盖面板。
    ("cas", PANEL6): "b8be5fd6ae6949e27c567d8856d31767ea2a19f1e3bfb44d9a8bf2eb03354834",
}

LEADER_NCOLS, ABILITY_NCOLS = B2.LEADER_NCOLS, B2.ABILITY_NCOLS
LEADER_ROWS = 11
ROUNDING_STEP_LARGE, ROUNDING_STEP_SMALL = 5000, 500   # 原值 ≥20% 取 5 的倍数；更小取 0.5 的倍数（口径 D2）

#: 余辉每层队长 during 134 行：0 基行号 → (原值, 第二批 live, 本轮, 档位)。内容 kind/对象/属性沿用 B2.GROWTH。
GROWTH = {
    1: ("40000", "8000", "30000", (4, 5)),      # 雷队 Fever 获得量
    4: ("160000", "32000", "110000", (7, 10)),  # 自身 强化弹射伤害
    5: ("160000", "32000", "130000", (4, 5)),   # 雷队 攻击力
    6: ("160000", "32000", "130000", (4, 5)),   # 雷队 能力伤害
    9: ("5000", "1000", "3500", (7, 10)),       # 自身 独立乘区强化弹射伤害
}
GROWTH_NAMES = {1: "雷队 Fever 获得量", 4: "自身 强化弹射伤害", 5: "雷队 攻击力", 6: "雷队 能力伤害",
                9: "自身 独立乘区强化弹射伤害"}
#: 余辉来源（只读核对）：队长 #10 与能力3 末行（#8）各 +1，同 unique 相加 ⇒ 当队长每次进 Fever +2。
LEADER_GAIN_ROW = 10
A3_GAIN_ROW = 8

#: 面板：第二批输出的 6 行（live），数值稿只换末行，终稿再删「余辉」效果行的共鸣前缀。
OLD_PANEL_LINES = B2.NEW_PANEL_LINES
PANEL_GROWTH_LINE = 5
RESONANCE_TOKEN = "Yellow"
RESONANCE_PREFIX = "雷属性共鸣时，"
#: 共鸣省略：固有状态 → 全部获取来源（全表 + 全部可枚举 DSL 只读扫描，live 1.4.1054）。
RESONANCE_OMISSION = {
    AFTERGLOW: {
        "name": "余辉",
        "resonance": RESONANCE_TOKEN,
        "sources": [f"leader_ability:{LEADER}#10", f"ability:{ABILITY3}#8"],
        "scan": "live 1.4.1054 全部 leader_ability / ability 行 + 1476 个可枚举 DSL（action_skill、switched、629、"
                "power_flip_action）只读扫描；与主会话 scan.json all_states 139995 一致",
    },
}
#: 「只在已有余辉时刷新」的来源（不是获取来源，不影响共鸣省略；总核对 minor 补记）。live 1.4.1054 只读核对。
RESONANCE_REFRESH_ONLY = {
    AFTERGLOW: [{
        "program": "battle/action/skill/action/ability_skill/ability_fox_oracle_autumn_fever_growth"
                   "$ability_fox_oracle_autumn_fever_growth",
        "tree": "ConditionalsConditionExist(-17, DCUnique 1399952) 成立支：Bind(-17, 1399952, DCUnique 1399952, 4, "
                "1000000000.0) + CreateCondition(-17, ACUnique 1399952 ×变量 1399952)；不成立支为空 Block",
        "semantics": "只在自身已有「余辉」时刷新/叠加（按现有层数/4），不能给出首层 ⇒ 不是获取来源",
        "tree_digest": "2ec38c9037c9826c557f3ba0602b07e8f3e821b076f4619d04bd946f19f0bc96",
        "callers": "live ability（3525 键）/ leader_ability（588 键）无任何行引用该程序；平表键 "
                   "ability_fox_oracle_autumn_fever_growth 已不在 live（V12 包移除，程序文件是 store 里的孤儿）",
        "revisit": "将来若有行调用它（或改成无前提授予），须重新核查共鸣省略",
    }],
}
#: 删共鸣前缀的面板行（0 基）→ 该行效果的数据来源（依赖「余辉」的行）。
PREFIX_DROP_LINES = {
    4: [f"ability:{CID}6#1（非Fever 且 余辉≥10 且 队长 → 强化弹射回 Fever 15%）"],
    5: [f"leader_ability:{LEADER}#{i}（持续·余辉每层）" for i in (1, 4, 5, 6, 9)],
}


def pct(value: str) -> str:
    """强度 → 面板数字（1000 = 1%）：30000 → 30、3500 → 3.5。"""
    return f"{int(value) / 1000:g}"


def growth_line(values: dict[int, str]) -> str:
    """余辉每层那一行：数字全部由行值渲染（攻击力与能力伤害合写一个数，两行必须相同）。"""
    if values[5] != values[6]:
        raise ValueError("panel merges team attack and ability damage into one number")
    return (f"雷属性共鸣时，「余辉」每1层：雷属性角色的FEVER获得量提升{pct(values[1])}％、"
            f"强化弹射伤害提升{pct(values[4])}％、独立乘区的强化弹射伤害提升{pct(values[9])}％、"
            f"雷属性角色的攻击力与能力伤害提升{pct(values[5])}％")


if growth_line({i: v[1] for i, v in GROWTH.items()}) != OLD_PANEL_LINES[PANEL_GROWTH_LINE]:
    raise AssertionError("batch-2 panel line is not rendered from the batch-2 values")
#: 数值稿（本轮成长数值，未删共鸣前缀）：面板合并校验（check_merge）的原文。
NUMERIC_PANEL_LINES = OLD_PANEL_LINES[:PANEL_GROWTH_LINE] + (growth_line({i: v[2] for i, v in GROWTH.items()}),)


def drop_resonance(line: str) -> str:
    """只删行首「雷属性共鸣时，」，其余字面逐字保留。"""
    if not line.startswith(RESONANCE_PREFIX):
        raise ValueError(f"line has no resonance prefix: {line}")
    return line[len(RESONANCE_PREFIX):]


#: 口径 1（A）：「、强化弹射伤害」接在带对象的效果后面 → 「，强化弹射伤害」（不补「自身」）。
PF_DAMAGE_JOIN_OLD, PF_DAMAGE_JOIN_NEW = "、强化弹射伤害", "，强化弹射伤害"
#: 0 基面板行 → 该行 A 改动的数据依据（前一效果带对象 / 强化弹射伤害行）。
PF_DAMAGE_JOIN_LINES = {
    PANEL_GROWTH_LINE: f"leader_ability:{LEADER}#1（kind 18 → 全队雷 Fever 获得量）后接 #4（during 23 → 自身 强化弹射伤害）",
}
#: 「、」后面的强化弹射伤害项（含「独立乘区的强化弹射伤害」）。
_PF_ITEM_AFTER_ENUM = re.compile(r"、((?:独立乘区的)?强化弹射伤害)")
#: 不带对象的强化弹射伤害项（前一项也是它时，「、」保留）。
_PF_ITEM_BARE = re.compile(r"(?:独立乘区的)?强化弹射伤害")


def pf_damage_join_problems(text: str) -> list[str]:
    """口径 1（A）：「、强化弹射伤害…」的前一项必须也是不带对象的强化弹射伤害项，否则应写「，」。"""
    problems = []
    for number, line in enumerate(text.split("\n"), start=1):
        for match in _PF_ITEM_AFTER_ENUM.finditer(line):
            start = max(line.rfind(mark, 0, match.start()) for mark in "，；：:。、") + 1
            previous = line[start:match.start()]
            if not _PF_ITEM_BARE.match(previous):
                problems.append(f"line {number}: 「{previous}{match.group(0)}」 joins pf damage to an effect "
                                "with a target by 「、」 (use 「，」)")
    return problems


def join_pf_damage(line: str) -> str:
    """只把「对象效果、强化弹射伤害」的那一个「、」改「，」；其余字面逐字不动。"""
    if line.count(PF_DAMAGE_JOIN_OLD) != 1:
        raise ValueError(f"expected exactly one {PF_DAMAGE_JOIN_OLD!r}: {line}")
    joined = line.replace(PF_DAMAGE_JOIN_OLD, PF_DAMAGE_JOIN_NEW)
    if not pf_damage_join_problems(line) or pf_damage_join_problems(joined):
        raise ValueError(f"line is not the rule-A shape: {line}")
    return joined


#: 共鸣省略后的稿（口径 1 之前）；终稿再按口径 1（A）改第 6 行的一个标点。
DROPPED_PANEL_LINES = tuple(drop_resonance(line) if index in PREFIX_DROP_LINES else line
                            for index, line in enumerate(NUMERIC_PANEL_LINES))
NEW_PANEL_LINES = tuple(join_pf_damage(line) if index in PF_DAMAGE_JOIN_LINES else line
                        for index, line in enumerate(DROPPED_PANEL_LINES))
OLD_PANEL = "\n".join(OLD_PANEL_LINES)
NUMERIC_PANEL = "\n".join(NUMERIC_PANEL_LINES)
NEW_PANEL = "\n".join(NEW_PANEL_LINES)

#: 能力6 覆盖面板（live 两行：共鸣条件单独一行、以「：」结尾）→ 一行，共鸣写「雷属性共鸣时，」（口径 3）；其余字面逐字。
PANEL6_RESONANCE_OLD = "雷属性共鸣时："
PANEL6_EFFECT = "FEVER模式中，独立乘区的强化弹射伤害提升30％"
OLD_PANEL6 = PANEL6_RESONANCE_OLD + "\n" + PANEL6_EFFECT
NEW_PANEL6 = RESONANCE_PREFIX + PANEL6_EFFECT


def normalize_resonance_colon(text: str) -> str:
    """口径 3 规范化：「X属性共鸣时：」后换行接效果的并成一行，其余「X属性共鸣时：」改「，」；其余字面不动。"""
    text = re.sub(r"([火水雷风光暗]属性共鸣时)[：:]\n", r"\1，", text)
    return re.sub(r"([火水雷风光暗]属性共鸣时)[：:]", r"\1，", text)


if normalize_resonance_colon(OLD_PANEL6) != NEW_PANEL6:
    raise AssertionError("ability-6 panel is not the colon-normalized live text")


def rounded_growth(original: str, factor: tuple[int, int]) -> str:
    """口径取整：原值 × 档位，原值 ≥20% 就近取 5% 的倍数，其余就近取 0.5%；不得低于原值的 2/3。"""
    exact = int(original) * factor[0] / factor[1]
    step = ROUNDING_STEP_LARGE if int(original) >= 20000 else ROUNDING_STEP_SMALL
    value = int(exact / step + 0.5) * step
    if value * 3 < int(original) * 2:
        raise ValueError(f"{original} × {factor} rounds to {value}, below 2/3")
    return str(value)


class InahoGrowthError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


digest = B2.digest


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InahoGrowthError(f"{CID} balance 20260927c: {message}")


def _baseline(read) -> dict:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        if value is None or digest(value) != want:
            raise InahoGrowthError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    return inputs


def _growth_cells(index: int, strength: str) -> dict:
    kind, target, token, _old, _new = B2.GROWTH[index]
    return B2._growth_cells(kind, target, token, strength)


# ---------------------------------------------------------------- 队长：余辉每层回调

def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """余辉每层 5 行 c111/c112 第二批值 → 本轮值；其余 6 行逐字保留、顺序不变。"""
    _require(len(rows) == LEADER_ROWS and all(len(row) == LEADER_NCOLS for row in rows),
             f"leader {LEADER} must be {LEADER_ROWS} rows of {LEADER_NCOLS} columns")
    per_layer = [i for i, row in enumerate(rows)
                 if row[3] == "1" and row[95] == "134" and row[102] == AFTERGLOW]
    _require(per_layer == sorted(GROWTH), f"afterglow per-layer leader rows moved: {per_layer}")
    for index, (original, live, new, factor) in GROWTH.items():
        if (B2.GROWTH[index][3], B2.GROWTH[index][4]) != (original, live):
            raise AssertionError(f"leader #{index}: batch-2 values differ from the reviewed table")
        if rounded_growth(original, factor) != new:
            raise AssertionError(f"leader #{index}: {new} is not {original} × {factor} rounded")
        _require(B2._matches(rows[index], LEADER_NCOLS, _growth_cells(index, live)),
                 f"unexpected preimage for leader #{index} (batch-2 {live})")
    gain = rows[LEADER_GAIN_ROW]
    _require((gain[25], gain[45], gain[66], gain[57]) == ("8", "461", AFTERGLOW, "100000"),
             f"leader #{LEADER_GAIN_ROW} is not the Fever-entry afterglow gain")
    _require(rows[7][45] == "722" and rows[7][80] == B2.PF_KEY, "leader 722 dual-PF override row moved")

    out = deepcopy(rows)
    for index, (_original, _live, new, _factor) in GROWTH.items():
        out[index][111] = out[index][112] = new
    for index, (_original, _live, new, _factor) in GROWTH.items():
        if not B2._matches(out[index], LEADER_NCOLS, _growth_cells(index, new)):
            raise AssertionError(f"leader #{index} touched more than c111/c112")
    changed = [i for i, (a, b) in enumerate(zip(rows, out)) if a != b]
    if changed != sorted(GROWTH):
        raise AssertionError(f"leader rows touched: {changed}")
    return out


def afterglow_sources(leader: list[list[str]], a3: list[list[str]]) -> list[str]:
    """余辉 +1 的全部来源（队长行 / 能力3 行）；当队长时两源相加 ⇒ 每次进 Fever +2。"""
    sources = [f"leader#{i}" for i, row in enumerate(leader) if row[45] == "461" and row[66] == AFTERGLOW]
    sources += [f"{ABILITY3}#{i}" for i, row in enumerate(a3) if row[47] == "461" and row[68] == AFTERGLOW]
    return sources


#: 前置块起始列（kind, pulled, pulled_group, 下限, 上限, 属性组, uid）：队长 / 能力。
PRECONDITION_BASES = {"leader": (4, 11, 18), "ability": (6, 13, 20)}


def resonance_tokens(row: list[str], table: str) -> list[str]:
    """该行前置里的属性共鸣（kind 2、编成 600000、不按拉取组计数）的属性组。"""
    out = []
    for base in PRECONDITION_BASES[table]:
        kind, _pulled, pulled_group, low, high, group = row[base:base + 6]
        if kind == "2" and low == "600000" and high in ("600000", "") and group \
                and pulled_group in ("", "0", "(None)"):
            out.append(group)
    return out


def resonance_basis_problems(leader: list[list[str]], a3: list[list[str]]) -> list[str]:
    """共鸣省略依据：「余辉」每个获取来源都带雷共鸣；删前缀的第 6 行数据全部依赖「余辉」。"""
    problems = []
    for label, row, table in ((f"leader#{LEADER_GAIN_ROW}", leader[LEADER_GAIN_ROW], "leader"),
                              (f"{ABILITY3}#{A3_GAIN_ROW}", a3[A3_GAIN_ROW], "ability")):
        if resonance_tokens(row, table) != [RESONANCE_TOKEN]:
            problems.append(f"afterglow source {label} is not gated on thunder resonance; "
                            "the resonance prefix omission no longer holds")
    dependents = [i for i, row in enumerate(leader) if row[102] == AFTERGLOW]
    if dependents != sorted(GROWTH):
        problems.append(f"afterglow per-layer rows moved: {dependents}")
    return problems


# ---------------------------------------------------------------- 面板

def panel_rows(rows: list[list[str]]) -> list[list[str]]:
    _require(rows == [[OLD_PANEL]], f"{PANEL}: unexpected panel text (expected the batch-2 output)")
    return [[NEW_PANEL]]


def panel6_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力6 面板：「雷属性共鸣时：」+ 换行 + 效果 → 一行「雷属性共鸣时，效果」（口径 3，只动标点与换行）。"""
    _require(rows == [[OLD_PANEL6]], f"{PANEL6}: unexpected panel text (expected the live colon + newline form)")
    return [[NEW_PANEL6]]


def panel6_gate_problems(text: str) -> list[str]:
    problems = [f"panel6: {p}" for p in KL.panel_problems(text)]
    for word in ("／", "/", "可无限", "无上限", "自身为队长时", "觉醒后", "生命值100%以下", "共鸣时：", "\n"):
        if word in text:
            problems.append(f"panel6: forbidden {word!r}")
    if not text.startswith(RESONANCE_PREFIX):
        problems.append(f"panel6: must start with {RESONANCE_PREFIX!r}")
    return problems


def panel_gate_problems(text: str) -> list[str]:
    problems = [f"panel: {p}" for p in KL.panel_problems(text)]
    for word in ("／", "/", "可无限", "无上限", "自身为队长时", "觉醒后", "生命值100%以下", "共鸣时："):
        if word in text:
            problems.append(f"panel: forbidden {word!r}")
    for index, line in enumerate(text.split("\n")):
        if index in PREFIX_DROP_LINES:
            if line.startswith(RESONANCE_PREFIX) or not line.startswith("「余辉」"):
                problems.append(f"panel line {index + 1} must be an afterglow effect "
                                f"without the resonance prefix: {line}")
        elif not line.startswith(RESONANCE_PREFIX):
            problems.append(f"panel line without resonance prefix: {line}")
    problems += [f"panel: {p}" for p in pf_damage_join_problems(text)]
    return problems


def pf_damage_join_basis_problems(leader: list[list[str]]) -> list[str]:
    """口径 1（A）的数据依据：第 6 行「，」前是 #1（全队雷 Fever 获得量，带对象），后是 #4（自身 during 23，面板不补对象）。"""
    problems = []
    if (leader[1][107], leader[1][108], leader[1][109]) != ("18", "5", RESONANCE_TOKEN):
        problems.append("leader #1 is no longer the thunder-team Fever gain (the effect before 「，」)")
    if (leader[4][107], leader[4][108], leader[4][109]) != ("23", "", ""):
        problems.append("leader #4 is no longer the self during-23 pf damage (the effect after 「，」)")
    return problems


# ---------------------------------------------------------------- 门禁

def row_problems(kind: str, row: list[str]) -> list[str]:
    return B2.row_problems(kind, row)


def revise(read) -> dict:
    inputs = _baseline(read)
    leader, a3 = inputs["leader", LEADER], inputs["ability", ABILITY3]
    sources = afterglow_sources(leader, a3)
    _require(sources == [f"leader#{LEADER_GAIN_ROW}", f"{ABILITY3}#{A3_GAIN_ROW}"],
             f"afterglow gain sources drift: {sources}")
    new_leader = leader_rows(leader)
    panel = panel_rows(inputs["cas", PANEL])
    panel6 = panel6_rows(inputs["cas", PANEL6])
    problems = [f"leader {LEADER}#{i}: {p}" for i, row in enumerate(new_leader)
                for p in row_problems("leader_ability", row)]
    problems += resonance_basis_problems(new_leader, a3)
    problems += pf_damage_join_basis_problems(new_leader)
    problems += panel_gate_problems(NEW_PANEL)
    problems += panel6_gate_problems(panel6[0][0])
    caps = legality.required_client_capabilities(legality.CUSTOM_ABILITY_STRING_KIND, [PANEL])
    caps += legality.required_client_capabilities(legality.CUSTOM_ABILITY_STRING_KIND, [PANEL6])
    problems += [f"panel needs undeclared capability {cap}" for cap in caps if cap not in CAPABILITIES]
    if problems:
        raise InahoGrowthError("; ".join(problems))

    total = lambda value, layers=16: f"{int(value) * layers / 1000:g}%"   # noqa: E731
    return {
        "ability": {}, "leader": {LEADER: new_leader}, "cas": {PANEL: panel, PANEL6: panel6},
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_inaho.py",
            "spec": "第三轮（成长复核）施工口径 growth_c_spec.md：作者「砍到4/5,或者7/10」「可以砍到2/3」「数值尽量取5的倍数」；"
                    "reeval_full.json table 稻穗 L#1（4/5）、L#4（7/10）、L#5/L#6（4/5）、L#9（7/10）",
            "live_tail": "1.4.1053（第二批 1.4.1051 已 ×1/5；inaho2 1.4.1053 只动能力1/3）；"
                         "1.4.1054（灰服三角色替换）未碰本角色，BEFORE 三项复核逐字相同",
            "changes": {
                f"leader_ability:{LEADER}#{i} c111/c112": f"{live}→{new}：{GROWTH_NAMES[i]} 每层 {pct(live)}%→{pct(new)}%"
                                                          f"（原 {pct(original)}% × {factor[0]}/{factor[1]}）"
                for i, (original, live, new, factor) in GROWTH.items()
            } | {f"custom_ability_string:{PANEL} 末行": [OLD_PANEL_LINES[-1], NEW_PANEL_LINES[-1]],
                 f"custom_ability_string:{PANEL6}": [OLD_PANEL6, NEW_PANEL6]},
            "rounding": {
                f"#{i}": f"{pct(original)}% × {factor[0]}/{factor[1]} = {int(original) * factor[0] / factor[1] / 1000:g}%"
                         f" → {pct(new)}%（实际 {int(new) / int(original):.4g}）"
                for i, (original, _live, new, factor) in GROWTH.items()
            },
            "live_verified": "live 现值（8/32/32/32/1%）与数值表批二值一致，无需重算",
            "afterglow_sources": {
                "rows": sources,
                "table_stale": "数值表 L#1 写「队长 L#10 和能力1#3」已过期：inaho2（1.4.1053）把进 Fever 余辉 +1 移到能力3 末行；"
                               "当队长时每次进 Fever 仍是两源相加 +2 层（本模块只读核对，不改）",
            },
            "three_minutes_16_layers": {
                f"#{i}": {"original": total(original), "batch2": total(live), "batch3": total(new)}
                for i, (original, live, new, _factor) in GROWTH.items()
            },
            "author_attention": "#1 取整后实际 3/4，Fever 获得量回升会加快「Fever → 余辉层数」的正反馈（数值表提示）",
            "kept": ["leader #0/#2/#3/#7/#8/#10 与五行其余列逐字保留", "不新增前置（口径 D3；五行已带雷编成≥6）",
                     "能力1/3/4/6 数据行、双段 PF、技能不动（能力6 只改覆盖面板的共鸣标点与换行）"],
            "panel": {PANEL: "末行数值 8/32/1/32 → 30/110/3.5/130（数值稿）；第 5/6 行删「雷属性共鸣时，」（共鸣省略）；"
                             "第 6 行「FEVER获得量提升30％、强化弹射伤害」→「，强化弹射伤害」（口径 1 扩到同形写法 A）；"
                             "其余 4 行逐字不变；「累积1层」既有偏差照旧不修（非队长 1 层 / 队长 2 层是作者确认的设计）"},
            "panel_merge": {
                "rule": "作者「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,引擎点火提供的效果"
                        "就不用写火属性共鸣,其他角色类似」；主会话合并规则",
                "resonance_omission": RESONANCE_OMISSION,
                "resonance_omission_refresh_only": RESONANCE_REFRESH_ONLY,
                "prefix_dropped_lines": {f"L{index + 1}": {"before": NUMERIC_PANEL_LINES[index],
                                                          "after": NEW_PANEL_LINES[index], "data": data}
                                         for index, data in PREFIX_DROP_LINES.items()},
                "kept_prefix": {"L4": "「余辉」获取行（队长 #10 / 能力3 #8 本身带雷共鸣），保留"},
                "pf_damage_join": {
                    "rule": "主会话口径 1 扩到同形写法（A）：凡「…、强化弹射伤害…」接在带对象的效果后面，一律改「，强化弹射伤害…」"
                            "（不论 kind 55 / during 23 / 413），不补对象",
                    "lines": {f"L{index + 1}": {"before": DROPPED_PANEL_LINES[index], "after": NEW_PANEL_LINES[index],
                                                "data": data}
                              for index, data in PF_DAMAGE_JOIN_LINES.items()},
                    "kept": "「、独立乘区的强化弹射伤害提升3.5％」（#9 413）前一项是不带对象的强化弹射伤害，"
                            "「、雷属性角色的攻击力与能力伤害」自带对象，都不属 A 的形，保留「、」",
                },
                "merged": "无：#1/#4/#5/#6/#9 已在同一行；#2 与 #10 后缀不同（L4「（最多99层）」且为获取行）不并",
                "resonance_colon": {
                    PANEL6: {"before": OLD_PANEL6, "after": NEW_PANEL6,
                             "rule": "主会话口径 3：「X属性共鸣时：」统一成「X属性共鸣时，」，冒号后换行接效果的并成一行",
                             "data": f"ability:{CID}6#0（雷编成≥6、持续·Fever → 自身 独立乘区强化弹射伤害 15%→30%）"},
                    PANEL: "终稿无「共鸣时：」，不涉及",
                },
                "other_panels": {
                    "desc_override_fox_oracle_autumn_2": "两条数据行（强化弹射追击 / Fever 弹射加连击）条件不同，无改动",
                    PANEL6: "#0/#1 条件不同，无同条件组；只做口径 3 的共鸣标点/换行统一（见 resonance_colon）",
                    "ability3/4/5": "自动生成面板（无覆盖文案），不新建",
                },
                "check_merge": ("数值稿先按口径 1（A）在测试里显式规范化第 6 行的一个标点，再与终稿过 "
                                "mod-tools/wf_panel_merge_check.check（prefix_drops = L5、L6 / Yellow）；"
                                f"{PANEL6} 先按口径 3 规范化 live 原文再核（测试写出规范化步骤），见测试"),
            },
            "generators": "无现行生成器；历史链哈希锁定（第二批已核对），本模块是这些格子与面板的唯一写入源",
            "cross_unit": "本轮不移行；wf_gbf_kit_soriz 的 1399951 724 donor 按内容取，不受影响",
            "capabilities": list(CAPABILITIES),
            "runtime_verified": False,
        },
    }

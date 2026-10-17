# -*- coding: utf-8 -*-
'杰拉德「月耀守护」149999 ``white_wolf_gerald``（光）：2026-09-27 第三轮（成长复核）。\n\n注意：杰拉德（149999 光，白狼骑士）≠ 杰拉尔（129992 水，unicorn_lancer_rose）。\n\n作者原话（主会话 2026-09-27 逐字转述，按时间顺序）：\n「部分角色技能都倍率成长也要无限成长,成长条件放到队长技里面带上对应共鸣条件,凯尔的成长降太低了,本身数值就不高,\n很多角色成长过于缓慢,也要基于角色本身的其他词条判断,比如部分角色没有基础刃值只能靠成长」／「成长速度砍到1/10不合理,\n现在本来就算是正常偏快而已,砍太多了」／「砍到4/5,或者7/10这样吧,很多角色没有成长完全没用了」／「可以砍到2/3」／\n「数值尽量取5的倍数比如36就变成35,39就变成40」。\n\n按 live 链尾 1.4.1053 推导：第二批 ``wf_balance_20260927b_gerald_wolf``（1.4.1051）把队长 #6–#8 从 +50% 砍到 +5%\n（×1/10）；``wf_balance_20260927b_gerald2``（1.4.1053）撤回技能封顶、改文案。行号 0 基（``#n``）。\n\n改动（数值表 reeval_full.json 杰拉德 L#6/L#7/L#8，档位 4/5）：\n    队长 #6/#7/#8「光编成≥6：编成直接攻击（trigger 20，puller 7 全队合计，组 White）每满 50 次 → 光队\n    攻击力(32) / 直击伤害(33) / 能力伤害(388)」c49/c50 5000 → 40000（每步 +5% → +40%；原 +50% × 4/5，\n    已是 5 的倍数）。依据：没有任何固定的攻击/直击/能伤加成，这三条是唯一的乘区（「没有基础刃值只能靠成长」）。\n    3 分钟按 60 次（区间 30–200）：原 3000% / 批二 300% / 本轮 2400%（1200–8000%）。\n其余 9 行逐字保留：#9 Fever 眩晕蓄积 50%（第二批 Down）、#11 536 技能强化开关（光共鸣）、#5 每 35 直击造伤等。\n技能撤封顶已在 1.4.1053（gerald2）完成，本模块不读不写技能树（口径「杰拉德本轮只改表里的 L#6–L#8 数值」）。\n不新增共鸣前置（口径 D3；三行本来就带「光编成≥6」前置 kind 2）。\n\n面板：队长面板键 ``desc_override_black_wolf_knight`` 在 live 不存在 ⇒ 客户端按行自动生成（改后显示 40%），\n不写覆盖文案；存在即拒绝（fail closed）。技能描述 / character_text / 服务端文本 / 技能强化与 PF 覆盖串都不含这些数值。\n\n面板同条件合并 + 共鸣省略（作者原话「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,\n引擎点火提供的效果就不用写火属性共鸣,其他角色类似」；主会话合并规则与扫描 ``panel_merge/scan.json``，按本轮数据重核）：\n\n- 本角色唯一的覆盖面板是能力1 ``desc_override_white_wolf_gerald_1``。数据 ``1499991`` #0/#1/#2 同条件（无前置、\n  无触发、c1=true、无 CT/次数上限/后缀，除效果列外逐格相同），但 L2 写「战斗开始时」（#1 kind 211 一次性充能），\n  文案条件不同 ⇒ 只并 L1（#0 弱化无效）+ L3（#2 技能槽最大值）：「自身弱化效果无效、技能槽最大值+50%。」放在 L1 位置，\n  L2、L4（#3 合击位限制，条件不同）逐字保留。能力1 词条行只读（核对合并组）。\n- 队长与能力 2–6 没有覆盖文案（``desc_override_black_wolf_knight`` / ``_1``–``_4`` 在 live 都不存在，且与官方罗尔夫\n  111007 共用 string_id）⇒ 自动面板一律不新建覆盖文案。\n- 共鸣省略不适用：「时之刻印」1499989 只由能力3 #0（光共鸣前置，461）授予，但没有任何覆盖面板行依赖它；\n  「时空裂痕」「时空侵蚀」有不带共鸣的来源（629 / 技能 DSL）；能力1 面板本无「X属性共鸣时，」（:data:`PREFIX_DROPS` 为空）。\n\n技能强化只写在队长技（作者原话「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述\n强化后的效果,规范并简化描述做了吗」；主会话口径 R1–R4）：\n\n- R1：强化 = 队长 #11 kind 536（旗号 1，前置 光≥6 共鸣）打开、两档技能 DSL ``ConditionalsChangeSkillFlag(1)`` 开支里\n  生效的效果——施放成长 ``BindConditionAccumulationVariable``（时空侵蚀 14999903）、``FindNearSubjects`` →\n  ``ConditionalsHealthPointRatioOf(5)`` → ``CreateRatioAttack`` 固定伤害 / 斩杀；关支没有这三种节点\n  （``wf_balance_20260927b_gerald2.execute_branch`` 逐节点核对，本模块读两档 DSL 只读复核）。\n- R3：技能说明（``action_skill`` 两档 c1、``character_text`` c5/c7、服务端 ``assets/cdndata/character_text.json`` [5]/[7]）\n  删去 gerald2 追加的「／强化后：…」整段（连同前导「／」），回到技能本体文字（== gerald2 的 OLD_*_DESC）；\n  character_text / 服务端本体另按数据改三处字面（见下「技能说明本体按数据改字」），其余字面不动。\n- R2：强化条目 ``change_skill_white_wolf_gerald``（队长 #11 c68；队长面板是自动面板，客户端按行拼「光属性共鸣时」前缀）\n  「强化自身技能：…」→「强化『月耀一闪』：…」，点明技能名，其余文字不动（本来就定性、无数字）。\n- R4：只改文字，队长行（除上面 #6–#8 成长）、能力行、DSL 一格不动。\n\n技能说明本体按数据改字（作者原话「杰拉德数据是消除 2 个、全属性是要这个」；上一轮总核对 audit.issues「149999 杰拉德：\ncharacter_text c5/c7 与服务端 [5]/[7]」）：``character_text`` c5/c7 与服务端 [5]/[7] 的本体写「强制消除1个强化效果」\n「赋予累积光属性抗性降低效果」「对领域内全体敌人」，与两档 DSL 关支（技能本体）不符——``DeleteCondition`` 第 3 参（删除条数）\n= 2、``ACToleranceOfElement`` 元素 = 254（全属性）、月牙交叉斩判定 = 场地点 -1 上 1500×2000 矩形（全屏，\n覆盖 1080×1920 战场），「時空領域」判定只在旗号 1 开支里。按数据改成「消除2个强化效果」「赋予累积全属性抗性降低效果」\n「对全体敌人」（:data:`TEXT_DESC_FIXES`），不提强化分支的领域（强化只写在强化条目里）。``action_skill`` 两档 c1 本来就是\n「消除敌人的2个强化效果」「累积全属性抗性降低」「全屏…对全体敌人」，不动（只删「强化后」段）；六处说明的事实由\n:func:`desc_fact_problems` 按两档 DSL 关支逐项核对。其余字面（「展开时之魔法阵」= 关支也有的時空陣演出 ShowEffect）不动。\n\n生成器：这三格没有现行生成器——``wf_gerald_cast_growth.relocate`` 只把能力2/3 的两行追加到队长末尾、既有行原样透传；\n``wf_gerald_percent_skill`` / ``wf_gerald_percent_revision`` 不碰队长表（第二批测试有源码级断言）。\n本模块是 ``leader_ability:149999`` #6–#8 现行的唯一写入源。强化条目的生成器常量 ``wf_gerald_cast_growth.ENHANCEMENT_TEXT``\n已同步为 :data:`NEW_CAS_FLAG_TEXT`；技能说明没有生成器（gerald2 在模块里直接拼接），本模块是它现行的唯一写入源。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写 live store / assets / .cdn / 候选包；\n接口见 ``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``（第三轮 c 后缀）。\n'
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Callable

import wf_balance_20260927b_gerald2 as G2
import wf_balance_20260927b_gerald_wolf as B2
import wf_client_legality as L
import wf_midautumn_kitlib as KL

CID = B2.CID                        # "149999"
CODE = B2.CODE                      # "white_wolf_gerald"
PACKAGES = ["white_wolf_gerald"]
#: 候选 manifest 现值 0.20260927.1（gerald2 回写）→ 递增。
PACKAGE_VERSION = {"white_wolf_gerald": "0.20260927.2"}
#: 只改三行强度，不需要新能力（候选已声明 gauge-gain-rules-v1 / panel-description-override-v2）。
CAPABILITIES: list[str] = []
#: 候选 white_wolf_gerald 与 live 在 leader:149999 上逐字相同、manifest 零哈希漂移（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}
ELEMENT = B2.ELEMENT                # 4 = 光（0 基内部元素）
LEADER_NCOLS = B2.LEADER_NCOLS      # 124
LEADER_ROWS = 12
LEADER_PANEL_KEY = G2.LEADER_PANEL_KEY   # desc_override_black_wolf_knight（不存在 ⇒ 自动生成）

A1_KEY = f"{CID}1"                              # 1499991（面板合并组的数据行，只读）
CAS_A1 = f"desc_override_{CODE}_1"              # desc_override_white_wolf_gerald_1
ABILITY_NCOLS = 126

#: live 1.4.1053 只读取数（stage_batch.make_read(live_only=True) 同法）；值 = digest(read(kind, key))。
#: 队长 = 第二批 ``wf_balance_20260927b_gerald_wolf`` 输出（gerald2 只读未改）。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", CID): "86c7076a2c0aac0ee174ea9bb90f1ec19111357da44600d09f843dd2c2c0bd2f",
    # 面板同条件合并（链尾 1.4.1054 只读取数，与 1.4.1053 及候选 white_wolf_gerald 0.20260927.1 逐字相同）：
    # 能力1 词条行只读（核对合并组数据条件），能力1 覆盖串改写。
    ("ability", A1_KEY): "53c72fb83b0e53752874ee55e18b7478ebb60744bff285b4fa148855c0213f08",
    ("cas", CAS_A1): "613f4cb6ee52974a423ce3fd881193b08e95400b009d5fda89c66221790290df",
    # 技能强化文案（链尾 1.4.1054 只读取数 = gerald2 输出）：强化条目、技能说明四处改写；两档技能 DSL 只读（R1 依据）。
    ("cas", G2.CAS_KEY): "d9e1f4891c912e43ef87a43179c23d2f6b6d58153251844d61c096c2517ceed2",
    ("action", CODE): "259ce07641bec40684b70d421e9d623dd4f7bd00b2b9491154bb67f70fee60ae",
    ("text", CID): "4310627c5f97ee8397c437a3e8e3a4e40c91398c1c249090ae5a63dc7519c343",
    ("server_text", CID): "4310627c5f97ee8397c437a3e8e3a4e40c91398c1c249090ae5a63dc7519c343",
    ("dsl", B2.SKILLS[0]): "0c87b53bf50446be34d3aa257d6dfa7b0b1f7351b78532d67781c1c72026eb9e",
    ("dsl", B2.SKILLS[1]): "915c5bdaba3b1702d247943277913dbb0c9b1fa4dd5fa75b4e9c8792b87bd5e6",
}

# ---------------------------------------------------------------- 成长行 #6–#8

GROWTH_ROWS = B2.GROWTH_ROWS            # {6: "32", 7: "33", 8: "388"}
GROWTH_COLS = B2.GROWTH_COLS            # (49, 50)
GROWTH_ORIGINAL = B2.GROWTH_OLD         # ("50000", "50000")：第二批前 +50%/次
GROWTH_LIVE = B2.GROWTH_NEW             # ("5000", "5000")：第二批 +5%/次（×1/10，live）
GROWTH_FACTOR = (4, 5)                  # 本轮档位 4/5（数值表 suggested_factor）
GROWTH_NEW = ("40000", "40000")         # +40%/次 = 50% × 4/5（已是 5 的倍数）
ROUNDING_STEP_LARGE, ROUNDING_STEP_SMALL = 5000, 500   # ≥20% 取 5 的倍数；<20% 取 0.5 的倍数（口径 D2）


def rounded_growth(original: str, factor: tuple[int, int]) -> str:
    """口径取整：原值 × 档位，≥20%（20000）就近取 5% 的倍数，其余就近取 0.5%；不得低于原值的 2/3。"""
    exact = int(original) * factor[0] / factor[1]
    step = ROUNDING_STEP_LARGE if int(original) >= 20000 else ROUNDING_STEP_SMALL
    value = int(exact / step + 0.5) * step
    if value * 3 < int(original) * 2:
        raise ValueError(f"{original} × {factor} rounds to {value}, below 2/3")
    return str(value)


class GeraldGrowthError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


digest = B2.digest


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GeraldGrowthError(f"{CID} balance 20260927c: {message}")


def _baseline(read: Callable[[str, Any], Any]) -> dict:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        got = digest(value) if value is not None else None
        if got != want:
            raise GeraldGrowthError(f"unreviewed live baseline for {kind}:{key} ({got} != {want})")
        inputs[kind, key] = deepcopy(value)
    try:
        present = read("cas", LEADER_PANEL_KEY) is not None
    except KeyError:
        present = False
    _require(not present, f"{LEADER_PANEL_KEY} exists: leader panel is no longer auto-generated")
    return inputs


def _growth_cells(index: int, values: tuple[str, str]) -> dict[int, str]:
    return B2._growth_cells(index, values)


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 #6–#8 c49/c50 5000 → 40000；其余 9 行（含 #9 眩晕蓄积 50%、#11 536）逐字保留、顺序不变。"""
    _require(len(rows) == LEADER_ROWS and all(len(row) == LEADER_NCOLS for row in rows),
             f"leader_ability:{CID} must be {LEADER_ROWS} rows of {LEADER_NCOLS} columns")
    if GROWTH_NEW != (rounded_growth(GROWTH_ORIGINAL[0], GROWTH_FACTOR),) * 2:
        raise AssertionError("GROWTH_NEW is not the 4/5 tier of the original value")
    for index in GROWTH_ROWS:
        found = B2._hits(rows, _growth_cells(index, GROWTH_LIVE))
        _require(found == [index], f"direct-hit growth row kind {GROWTH_ROWS[index]} (5%/50 hits, (None), CT0) "
                                   f"not found at #{index}: {found}")
    _require(B2._hits(rows, B2._stun_cells(B2.STUN_NEW)) == [B2.STUN_ROW],
             f"Fever Stunify 50% row #{B2.STUN_ROW} drifted")
    _require(B2._hits(rows, B2.KEPT_DAMAGE_CELLS) == [B2.KEPT_DAMAGE_ROW],
             f"35-hit ability-damage row #{B2.KEPT_DAMAGE_ROW} drifted")
    flag = rows[G2.FLAG_ROW]
    _require(all(flag[c] == v for c, v in G2.FLAG_CELLS.items())
             and all(v == "" for c, v in enumerate(flag) if c not in G2.FLAG_CELLS),
             f"leader #{G2.FLAG_ROW} is not the reviewed light-resonance 536 row")

    out = deepcopy(rows)
    for index in GROWTH_ROWS:
        out[index][GROWTH_COLS[0]], out[index][GROWTH_COLS[1]] = GROWTH_NEW

    # 自检：只动了这 6 格。
    for index in GROWTH_ROWS:
        if not B2._matches(out[index], _growth_cells(index, GROWTH_NEW)):
            raise AssertionError(f"leader #{index} touched more than c49/c50")
    changed = [i for i, (a, b) in enumerate(zip(rows, out)) if a != b]
    if changed != sorted(GROWTH_ROWS):
        raise AssertionError(f"leader rows touched: {changed}")
    if B2.stunify_problems(out):
        raise AssertionError(f"Stunify above the B.4 caps: {B2.stunify_problems(out)}")
    return out


# ---------------------------------------------------------------- 面板同条件合并 / 共鸣省略

A1_ROWS = 4
#: 同条件的判据：组内各行除「效果列」外逐格相同（前置三块、触发与参数、CT、次数上限、c1 主位、觉醒列、效果后缀列）。
#: 效果列 = c2 分类 + instant 内容块 kind/对象/对象元素/强度（c47–c52）+ during 内容块同位（c109–c114）。
ABILITY_EFFECT_COLUMNS = frozenset({2}) | frozenset(range(47, 53)) | frozenset(range(109, 115))
OLD_A1_LINES = (
    "自身弱化效果无效。",
    "战斗开始时，自身技能槽+100%。",
    "自身技能槽最大值+50%。",
    "作为合击角色编成时，自身无法因技能或能力效果增加技能槽（战斗开始时除外）。",
)
NEW_A1_LINES = (
    "自身弱化效果无效、技能槽最大值+50%。",
    "战斗开始时，自身技能槽+100%。",
    "作为合击角色编成时，自身无法因技能或能力效果增加技能槽（战斗开始时除外）。",
)
#: 合并组：面板键 → (词条键, 同条件数据行（0 基）, 被合并的面板行（0 基）, 改前整段行, 改后整段行)。
PANEL_MERGES: dict[str, tuple[str, tuple[int, ...], tuple[int, ...], tuple[str, ...], tuple[str, ...]]] = {
    CAS_A1: (A1_KEY, (0, 2), (0, 2), OLD_A1_LINES, NEW_A1_LINES),
}
#: 数据同条件、但文案条件不同而不并的行（扫描 skipped_groups）。
A1_SAME_CONDITION_NOT_MERGED = 1       # #1 kind 211 = L2「战斗开始时」一次性充能
#: 共鸣省略：无。键 = 面板键，值 = 可删「X属性共鸣时，」的面板行号（1 起）。
PREFIX_DROPS: dict[str, tuple[int, ...]] = {}
#: 自动生成的面板（live 无覆盖键）：一律不新建覆盖文案。
AUTO_PANEL_KEYS = ("desc_override_black_wolf_knight", "desc_override_black_wolf_knight_1",
                   "desc_override_black_wolf_knight_2", "desc_override_black_wolf_knight_3",
                   "desc_override_black_wolf_knight_4")
RESONANCE_BASIS = ("时之刻印 1499989：唯一来源能力3 #0（光共鸣前置 + 461）⇒ 全部来源带光共鸣，但没有覆盖面板行依赖它"
                   "（能力3 面板是自动生成）；时空裂痕 1499990（629 time_rift，Fever 条件）、时空侵蚀 14999903（技能 DSL）"
                   "有不带共鸣的来源 ⇒ 不成立；能力1 面板本无「X属性共鸣时，」⇒ 无可省前缀")


def merge_condition_problems(rows: list[list[str]], indexes: tuple[int, ...]) -> list[str]:
    """合并组内各行除效果列外必须逐格相同；返回差异（空 = 数据条件完全相同）。"""
    if any(i >= len(rows) for i in indexes):
        return [f"merge group {indexes} out of range ({len(rows)} rows)"]
    first = rows[indexes[0]]
    problems = []
    for index in indexes[1:]:
        row = rows[index]
        diff = [col for col in range(max(len(first), len(row))) if col not in ABILITY_EFFECT_COLUMNS
                and (first[col] if col < len(first) else None) != (row[col] if col < len(row) else None)]
        if diff:
            problems.append(f"rows #{indexes[0]}/#{index} differ outside the effect columns: {diff}")
    return problems


def ability1_rows_problems(rows: list[list[str]]) -> list[str]:
    """能力1 四行：键头 + 合并组（#0/#2）数据条件逐格相同。"""
    if len(rows) != A1_ROWS or any(len(r) != ABILITY_NCOLS for r in rows):
        return [f"ability {A1_KEY}: expected {A1_ROWS}×{ABILITY_NCOLS} rows"]
    if any((r[0], r[1]) != (f"{CODE}_1", "true") for r in rows):
        return [f"ability {A1_KEY}: key head drifted"]
    return merge_condition_problems(rows, PANEL_MERGES[CAS_A1][1])


def merged_panel(key: str, rows: list[list[str]]) -> list[list[str]]:
    """同条件合并：改前整段逐字核对，合并行放在组首行位置，其余行逐字保留；不接受自身输出（fail closed）。"""
    _ability, _rows, _lines, old, new = PANEL_MERGES[key]
    _require(rows == [["\n".join(old)]], f"{key}: unexpected panel text (expected the live pre-merge text)")
    return [["\n".join(new)]]


def ability1_text(rows: list[list[str]]) -> list[list[str]]:
    return merged_panel(CAS_A1, rows)


def panel_problems(cas: dict[str, list[list[str]]]) -> list[str]:
    """面板规则：逐行过 kitlib 禁词；不许「／」；合并行共鸣只写「X属性共鸣时，」；与复核稿逐字相同。"""
    problems = []
    for key, rows in cas.items():
        text = rows[0][0]
        if "／" in text:
            problems.append(f"{key}: uses 「／」 instead of line breaks")
        if re.search(r"属性共鸣时[：:,]", text):
            problems.append(f"{key}: resonance must be written 「X属性共鸣时，」")
        problems += [f"{key}: {p}" for line in text.split("\n") for p in KL.panel_problems(line)]
        if key in PANEL_MERGES and text != "\n".join(PANEL_MERGES[key][4]):
            problems.append(f"{key}: merged panel differs from the reviewed text")
    return problems


# ---------------------------------------------------------------- 技能强化文案（R1–R4）

SKILL_NAME = "月耀一闪"                          # action_skill c0 / character_text c4（＋档 = 名字 + 「＋」）
CAS_FLAG = G2.CAS_KEY                            # change_skill_white_wolf_gerald（队长 #11 kind 536 c68）
OLD_CAS_FLAG_TEXT = G2.NEW_CAS_TEXT              # live（gerald2 写入）
NEW_CAS_FLAG_TEXT = ("强化『月耀一闪』：追加按敌人当前生命值计算的固定伤害（随技能发动次数提高），"
                     "并斩杀低生命值的敌人")
#: 技能说明里删掉的强化段（gerald2 的 DESC_SEGMENT，连同前导「／」）；删段后 == gerald2 追加前的本体文字。
ENHANCED_SEGMENT = G2.DESC_SEGMENT
OLD_ACTION_DESC, NEW_ACTION_DESC = G2.NEW_ACTION_DESC, G2.OLD_ACTION_DESC
#: character_text / 服务端本体（删段后）与 DSL 关支不符的三处，按数据改字（作者「杰拉德数据是消除 2 个、全属性是要这个」）。
#: (旧字面, 新字面, 依据)；旧字面在本体里各出现恰好一次。
TEXT_DESC_FIXES = (
    ("对领域内全体敌人", "对全体敌人",
     "月牙交叉斩判定 = 场地点 -1 上 1500×2000 矩形（全屏）；時空領域判定只在旗号 1 开支（强化）"),
    ("强制消除1个强化效果", "消除2个强化效果", "DeleteCondition 第 3 参（删除条数上限）= 2"),
    ("赋予累积光属性抗性降低效果", "赋予累积全属性抗性降低效果", "ACToleranceOfElement 元素 = 254（全属性）"),
)
BODY_TEXT_DESC = G2.OLD_TEXT_DESC                # 删「强化后」段后的本体（改字前）


def _fixed_text_desc(body: str) -> str:
    for old, new, _basis in TEXT_DESC_FIXES:
        if body.count(old) != 1:
            raise AssertionError(f"text fix {old!r} must occur exactly once in the body")
        body = body.replace(old, new)
    return body


OLD_TEXT_DESC, NEW_TEXT_DESC = G2.NEW_TEXT_DESC, _fixed_text_desc(BODY_TEXT_DESC)
TEXT_DESC_COLUMNS = G2.TEXT_DESC_COLUMNS         # (5, 7)：技能 / 技能＋ 说明
TEXT_NAME_COLUMNS = (4, 6)
TEXT_NCOLS, ACTION_NCOLS = 12, 24
ACTION_LEVELS = ("1", "2")
#: 技能强化条目的官方格式开头（R2）与禁用写法。
FLAG_ENTRY_HEADS = (f"强化『{SKILL_NAME}』", f"为『{SKILL_NAME}』追加")
FLAG_ENTRY_BANNED = ("强化自身技能", "强化技能", "属性共鸣时", "担任队长", "强化后")
#: 技能说明里不得残留的强化描述（R3）。
DESC_BANNED = ("强化后", "不受此限", "担任队长", "共鸣", "斩杀", "固定伤害")

# ---------------------------------------------------------------- 技能说明本体事实（按 DSL 关支核对）

FIELD_POINT = -1                                 # 场地点主体（-1/-2 = 场地点）
FIELD_SIZE = (1080, 1920)                        # 战场宽×高：矩形判定不小于它 = 全屏
DELETE_TARGET, DELETE_COUNT = 2, 2               # DeleteCondition 第 1 参（命中敌人）/ 第 3 参（删除条数上限）
TOLERANCE_ALL_ELEMENTS = 254                     # ACToleranceOfElement 第 2 参：254 = 全属性
DELETE_KIND = ["DCAll", 2]                       # DeleteCondition 第 2 参：DCAll(2) = 强化（BuffOrDebuff.BUFF=2；3 = 弱化）
DOMAIN_EFFECT = "時空領域"                       # 强化分支的领域判定演出名（ShowEffect 第 1 参前缀）
#: 六处说明（action 两档 c1、text c5/c7、服务端 [5]/[7]）都必须写出的本体事实，与不得出现的旧写法 / 强化分支内容。
DESC_FACTS = (
    ("delete", re.compile(rf"消除(敌人的)?{DELETE_COUNT}个强化效果")),
    ("tolerance", re.compile(r"累积全属性抗性降低效果")),
    ("full_screen", re.compile(r"以全屏月牙交叉斩对全体敌人造成光属性伤害")),
)
DESC_FACT_BANNED = ("领域", "强制消除", "光属性抗性", "1个强化效果")


def _enclosing(paths: list[tuple], path: tuple) -> tuple | None:
    inside = [p for p in paths if path[:len(p)] == p and p != path]
    return max(inside, key=len) if inside else None


def plain_branch_facts(tree) -> dict[str, Any]:
    """两档 DSL 关支（技能本体）的文案事实：删除条数、降抗元素、交叉斩判定是否全屏、领域判定是否只在开支。"""
    _flag_path, enhanced, plain = G2.enhanced_branches(tree)
    deletes = G2._nodes(plain, "DeleteCondition")
    tolerances = [(p, n) for p, n in G2._nodes(plain, "ACToleranceOfElement")]
    areas = G2._nodes(plain, "CreateHitArea")
    area_paths = [p for p, _n in areas]
    facts: dict[str, Any] = {"deletes": [(n[1], n[3]) for _p, n in deletes],
                             "delete_kinds": [n[2] for _p, n in deletes],
                             "tolerance_elements": [n[2] for _p, n in tolerances],
                             "tolerance_lowers": [all(term["max"] < 0 for term in n[3]) for _p, n in tolerances]}
    shells = []
    for path, _node in deletes + tolerances:
        shell = _enclosing(area_paths, path)
        node = B2._at(plain, shell) if shell is not None else None
        if node is None:
            shells.append(None)
            continue
        shape = node[9]
        size = ((shape[1][0]["min"], shape[2][0]["min"]) if shape[0] == "Rectangle"
                and shape[1][0]["min"] == shape[1][0]["max"] and shape[2][0]["min"] == shape[2][0]["max"] else None)
        shells.append((node[2], size))
    facts["strike_areas"] = shells
    effect_names = lambda block: [n[1] for _p, n in G2._nodes(block, "ShowEffect")]   # noqa: E731
    facts["domain_in_plain"] = any(str(name).startswith(DOMAIN_EFFECT) for name in effect_names(plain))
    facts["domain_in_enhanced"] = any(str(name).startswith(DOMAIN_EFFECT) for name in effect_names(enhanced))
    return facts


def desc_fact_problems(trees: dict[str, Any], descs: list[str]) -> list[str]:
    """本体事实 == 两档 DSL 关支：消除 2 个强化效果、全属性降抗、全屏交叉斩对全体敌人；领域只在强化开支。
    ``descs`` 每条都要写出这三项事实，且不得出现旧写法（「领域」「强制消除」「光属性抗性」「1个强化效果」）。"""
    problems = []
    for program in B2.SKILLS:
        try:
            facts = plain_branch_facts(trees[program])
        except (KeyError, ValueError, IndexError, TypeError) as error:
            problems.append(f"{program}: plain branch not verified ({error})")
            continue
        if facts["deletes"] != [(DELETE_TARGET, DELETE_COUNT)]:
            problems.append(f"{program}: plain-branch DeleteCondition {facts['deletes']} != "
                            f"[({DELETE_TARGET}, {DELETE_COUNT})]")
        if facts["delete_kinds"] != [DELETE_KIND]:
            problems.append(f"{program}: plain-branch DeleteCondition kinds {facts['delete_kinds']} != [{DELETE_KIND}]")
        if facts["tolerance_lowers"] != [True]:
            problems.append(f"{program}: plain-branch ACToleranceOfElement is not a reduction")
        if facts["tolerance_elements"] != [TOLERANCE_ALL_ELEMENTS]:
            problems.append(f"{program}: plain-branch ACToleranceOfElement elements {facts['tolerance_elements']} "
                            f"!= [{TOLERANCE_ALL_ELEMENTS}]")
        for shell in facts["strike_areas"]:
            if not (shell and shell[0] == FIELD_POINT and shell[1]
                    and shell[1][0] >= FIELD_SIZE[0] and shell[1][1] >= FIELD_SIZE[1]):
                problems.append(f"{program}: cross-slash area is not full screen: {shell}")
        if facts["domain_in_plain"] or not facts["domain_in_enhanced"]:
            problems.append(f"{program}: {DOMAIN_EFFECT} is not enhanced-branch only")
    for text in descs:
        problems += [f"skill desc: missing {name} fact: {text}" for name, pattern in DESC_FACTS
                     if not pattern.search(text)]
        problems += [f"skill desc: stale wording {w!r}: {text}" for w in DESC_FACT_BANNED if w in text]
    return problems


def skill_flag_basis_problems(leader: list[list[str]], trees: dict[str, Any]) -> list[str]:
    """R1 依据：强化条目挂在队长 #11（536、光≥6 共鸣、c68 = 本串），删掉的「强化后」内容（施放成长、固定伤害 / 斩杀）
    只在两档技能 DSL 的 ``ConditionalsChangeSkillFlag(1)`` 开支里（``G2.execute_branch`` 逐节点核对，关支没有）。"""
    problems = []
    flag = leader[G2.FLAG_ROW] if len(leader) > G2.FLAG_ROW else []
    if not (all(flag[c] == v for c, v in G2.FLAG_CELLS.items())
            and all(v == "" for c, v in enumerate(flag) if c not in G2.FLAG_CELLS)):
        problems.append(f"leader #{G2.FLAG_ROW} is not the light-resonance 536 row pointing at {CAS_FLAG}")
    for program in B2.SKILLS:
        try:
            numbers = G2.skill_numbers(trees[program])
        except (KeyError, ValueError) as error:
            problems.append(f"{program}: enhanced branch not verified ({error})")
            continue
        # 删掉的段落描述的正是这一支（数字 == 树）：起始比例 / 每次增量 / 斩杀阈值。
        if G2.DESC_SEGMENT != (f"／强化后：对最近的敌人追加造成其当前生命值{G2._pct(numbers['base'])}的固定伤害"
                               f"（每次发动技能提高{G2._pct(numbers['per_cast'])}），"
                               f"敌人生命值低于最大生命值{numbers['execute_below']}%时直接斩杀"):
            problems.append(f"{program}: the removed segment does not describe the enhanced branch")
    return problems


def flag_entry_problems(text: str) -> list[str]:
    """R2：强化条目用官方格式、点明技能名、定性无数字（kitlib skill_flag 门）、不写共鸣前缀（客户端按前置拼）。"""
    problems = [f"skill flag: {p}" for p in KL.panel_problems(text, skill_flag=True)]
    if not text.startswith(FLAG_ENTRY_HEADS):
        problems.append(f"skill flag: must start with one of {FLAG_ENTRY_HEADS}: {text}")
    problems += [f"skill flag: banned wording {w!r}" for w in FLAG_ENTRY_BANNED if w in text]
    return problems


def desc_problems(text: str) -> list[str]:
    """R3：技能说明只写技能本体，不留强化描述；删段后不留空括号 / 孤立标点。"""
    problems = [f"skill desc: {p}" for p in KL.panel_problems(text)]
    problems += [f"skill desc: enhanced wording {w!r} left" for w in DESC_BANNED if w in text]
    if re.search(r"（）|\(\)|[／＋、，。]$|／／|^[／，。]", text):
        problems.append(f"skill desc: dangling punctuation: {text}")
    return problems


def skill_text_outputs(inputs: dict) -> dict:
    """R2/R3 改字：live 每处 == 改前（否则拒绝），返回 cas / action / text / server_text 改后值（不改 inputs）。"""
    if not (OLD_ACTION_DESC.endswith(ENHANCED_SEGMENT) and OLD_TEXT_DESC.endswith(ENHANCED_SEGMENT)
            and OLD_ACTION_DESC[:-len(ENHANCED_SEGMENT)] == NEW_ACTION_DESC
            and OLD_TEXT_DESC[:-len(ENHANCED_SEGMENT)] == BODY_TEXT_DESC
            and _fixed_text_desc(BODY_TEXT_DESC) == NEW_TEXT_DESC
            and ENHANCED_SEGMENT.startswith("／强化后：")):
        raise AssertionError("the new descriptions are not the old ones minus the enhanced segment "
                             "(plus the data-backed text fixes)")
    if OLD_CAS_FLAG_TEXT.replace("强化自身技能：", f"强化『{SKILL_NAME}』：", 1) != NEW_CAS_FLAG_TEXT:
        raise AssertionError("the new skill-flag entry is not the old one with the skill named")
    _require(inputs["cas", CAS_FLAG] == [[OLD_CAS_FLAG_TEXT]], f"{CAS_FLAG}: live text differs from the reviewed text")
    actions = []
    levels = [inner for inner, _fields in inputs["action", CODE]]
    _require(levels == list(ACTION_LEVELS), f"action_skill {CODE} levels {levels}")
    for (inner, fields), program, name in zip(inputs["action", CODE], B2.SKILLS, (SKILL_NAME, SKILL_NAME + "＋")):
        fields = list(fields)
        _require(len(fields) == ACTION_NCOLS and fields[0] == name and fields[7] == program
                 and fields[G2.ACTION_DESC_COLUMN] == OLD_ACTION_DESC,
                 f"action_skill {CODE}/{inner}: name/program/c1 differ from the reviewed text")
        fields[G2.ACTION_DESC_COLUMN] = NEW_ACTION_DESC
        actions.append((inner, fields))
    rows_out = {}
    for kind in ("text", "server_text"):
        rows = deepcopy(inputs[kind, CID])
        _require(isinstance(rows, list) and len(rows) == 1 and len(rows[0]) == TEXT_NCOLS,
                 f"{kind}:{CID}: expected one {TEXT_NCOLS}-column row")
        _require([rows[0][c] for c in TEXT_NAME_COLUMNS] == [SKILL_NAME, SKILL_NAME + "＋"],
                 f"{kind}:{CID}: skill names drifted")
        for col in TEXT_DESC_COLUMNS:
            _require(rows[0][col] == OLD_TEXT_DESC, f"{kind}:{CID} c{col}: live description differs from the reviewed text")
            rows[0][col] = NEW_TEXT_DESC
        rows_out[kind] = rows
    return dict(cas={CAS_FLAG: [[NEW_CAS_FLAG_TEXT]]}, action={CODE: actions},
                text={CID: rows_out["text"]}, server_text={CID: rows_out["server_text"]})


def row_problems(row: list[str]) -> list[str]:
    return B2.row_problems(row) + [f"capability {cap}" for cap in
                                   L.required_client_capabilities("leader_ability", row)]


def _pct(value: str) -> str:
    return f"{int(value) / 1000:g}%"


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    leader = inputs["leader", CID]
    new_leader = leader_rows(leader)
    # 面板同条件合并：先按数据核对组内条件逐格相同，再改写面板（能力1 行只读）。
    found = ability1_rows_problems(inputs["ability", A1_KEY])
    _require(not found, f"{CAS_A1}: merge group is not one data condition: {found}")
    cas = {CAS_A1: ability1_text(inputs["cas", CAS_A1])}
    problems = [f"leader #{i}: {p}" for i in GROWTH_ROWS for p in row_problems(new_leader[i])]
    problems += panel_problems(cas)
    # 技能强化文案（R1–R4）：先按数据核对删掉的段落 = 旗号 1 开支，再改强化条目与四处技能说明。
    problems += skill_flag_basis_problems(new_leader, {p: inputs["dsl", p] for p in B2.SKILLS})
    skill_text = skill_text_outputs(inputs)
    cas.update(skill_text["cas"])
    problems += flag_entry_problems(NEW_CAS_FLAG_TEXT)
    descs = ([fields[1] for _inner, fields in skill_text["action"][CODE]]
             + [rows[0][c] for kind in ("text", "server_text") for rows in skill_text[kind].values()
                for c in TEXT_DESC_COLUMNS])
    for text in descs:
        problems += desc_problems(text)
    # 本体事实（消除 2 个 / 全属性 / 全屏全体）按两档 DSL 关支核对，六处说明一致。
    problems += desc_fact_problems({p: inputs["dsl", p] for p in B2.SKILLS}, descs)
    if problems:
        raise GeraldGrowthError("; ".join(problems))

    original, live, new = (_pct(v[0]) for v in (GROWTH_ORIGINAL, GROWTH_LIVE, GROWTH_NEW))
    total = lambda value, times: f"{int(value) * times // 1000}%"   # noqa: E731
    return {
        "ability": {}, "leader": {CID: new_leader}, "cas": cas, "text": skill_text["text"], "table": {},
        "action": skill_text["action"], "dsl": {}, "server_text": skill_text["server_text"], "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_gerald_wolf.py",
            "spec": "第三轮（成长复核）施工口径 growth_c_spec.md：作者「砍到4/5,或者7/10」「可以砍到2/3」「数值尽量取5的倍数」；"
                    "reeval_full.json table 杰拉德 L#6/L#7/L#8（suggested_factor 4/5）",
            "live_tail": "1.4.1053（第二批 1.4.1051 已放缓到 5%；gerald2 1.4.1053 未动队长）",
            "changes": {
                f"leader_ability:{CID}#{i} c49/c50 (kind {kind})": f"{GROWTH_LIVE[0]}→{GROWTH_NEW[0]}："
                f"每 50 次全队直击 光队{name} +{live}→+{new}（原 +{original} × 4/5）"
                for (i, kind), name in zip(GROWTH_ROWS.items(), ("攻击力", "直击伤害", "能力伤害"))
            },
            "factor": {
                "tier": "4/5（数值表：没有任何固定的攻击/直击/能伤加成，这三条是唯一乘区 → 「只能靠成长」取最轻档）",
                "rounding": f"50% × 4/5 = {new}，已是 5 的倍数（口径：≥20% 取 5 的倍数）",
                "live_verified": f"live 现值 {live}（c49/c50 {GROWTH_LIVE[0]}）与数值表批二值一致，无需重算",
            },
            "three_minutes": {
                "trigger": "trigger 20 全队合计、逐段计数（DirectAttackScheduler.as:102 每段 countUp kind3）；"
                           "PF Lv3 附加 6 段直击 ⇒ 3 分钟约 60–200 次（推断）",
                "per_row_at_60": {"original": total(GROWTH_ORIGINAL[0], 60), "batch2": total(GROWTH_LIVE[0], 60),
                                  "batch3": total(GROWTH_NEW[0], 60)},
                "per_row_range_30_200": [total(GROWTH_NEW[0], 30), total(GROWTH_NEW[0], 200)],
                "author_fallback": "数值表：若作者嫌 3 分钟总量上限太高，可退到 7/10（35%）；本模块按表取 4/5",
            },
            "kept": {
                f"leader_ability:{CID}#9": "Fever 光队眩晕蓄积 50%（第二批 Down）不动",
                f"leader_ability:{CID}#11": "536 技能强化开关（光共鸣）不动；技能树撤封顶已由 gerald2（1.4.1053）完成，本模块不读不写",
                f"leader_ability:{CID}#5": "每 35 次直击 15 倍能力伤害（造伤，不是成长）不动",
                "precondition": "三行本来就带「光编成≥6」前置（kind 2），不新增前置（口径 D3）",
            },
            "panel": f"{LEADER_PANEL_KEY} 在 live 不存在 ⇒ 队长面板按行自动生成（改后 {new}），不写覆盖；"
                     "技能描述、character_text、服务端文本不含这些数值",
            "panel_merge": {
                "request": "作者「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,引擎点火提供的效果"
                           "就不用写火属性共鸣,其他角色类似」",
                "rule": "同一面板里数据条件完全相同的行合并（前置/触发/CT/c1/次数上限/后缀列逐格相同）；效果原措辞与数值保留、"
                        "只省略重复对象名；合并行放在组首行位置；文案条件不同（「战斗开始时」）不并",
                "changes": {f"cas:{CAS_A1} L1+L3": ["\n".join(OLD_A1_LINES), "\n".join(NEW_A1_LINES)]},
                "merged": {CAS_A1: f"{A1_KEY} #0（弱化无效）+ #2（技能槽最大值）→ L1；#1（kind 211 一次性充能）数据同条件，"
                                   "但 L2 写「战斗开始时」⇒ 不并；#3（合击位限制）条件不同"},
                "prefix_drops": {},
                "resonance_basis": RESONANCE_BASIS,
                "auto_panels": f"{', '.join(AUTO_PANEL_KEYS)} 在 live 不存在 ⇒ 自动生成，不新建覆盖文案",
            },
            "generators": "无现行生成器：wf_gerald_cast_growth.relocate 只透传既有队长行；percent_skill/percent_revision 不碰队长表；"
                          f"{CAS_A1} 也没有生成器（只在候选包与 live），本模块是它现行的唯一写入源；"
                          f"强化条目生成器常量 wf_gerald_cast_growth.ENHANCEMENT_TEXT == {CAS_FLAG} 新文案；"
                          "技能说明无生成器（gerald2 在模块里拼接），本模块是它现行的唯一写入源",
            "skill_enhancement_text": {
                "request": "作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,"
                           "规范并简化描述做了吗」；主会话口径 R1–R4",
                "basis": f"队长 #{G2.FLAG_ROW} kind 536（前置 光≥6 共鸣）c68 = {CAS_FLAG}；两档技能 DSL "
                         "ConditionalsChangeSkillFlag(1) 开支才有施放成长 Bind（时空侵蚀 14999903）与最近敌人固定伤害 / 斩杀"
                         "（G2.execute_branch 核对关支没有），删掉的段落数字 == 树",
                "changes": {
                    f"custom_ability_string:{CAS_FLAG}（R2）": [OLD_CAS_FLAG_TEXT, NEW_CAS_FLAG_TEXT],
                    f"action_skill:{CODE} 两档 c1（R3）": ["删去末尾「" + ENHANCED_SEGMENT + "」", NEW_ACTION_DESC],
                    f"character_text:{CID} c5/c7 + 服务端 [5]/[7]（R3 + 本体按数据改字）": [
                        "删去末尾「" + ENHANCED_SEGMENT + "」；"
                        + "；".join(f"「{old}」→「{new}」" for old, new, _b in TEXT_DESC_FIXES), NEW_TEXT_DESC],
                },
                "desc_fixes": {
                    "request": "作者「杰拉德数据是消除 2 个、全属性是要这个」（按数据改文字，不改数据与 DSL）",
                    "fixes": [{"old": old, "new": new, "basis": basis} for old, new, basis in TEXT_DESC_FIXES],
                    "action": "action_skill 两档 c1 本体本来就与数据一致（消除敌人的2个强化效果 / 累积全属性抗性降低 / "
                              "全屏…对全体敌人），只删「强化后」段",
                    "verified": "desc_fact_problems：两档 DSL 关支 DeleteCondition(2, DCAll 2, 2)、ACToleranceOfElement 254、"
                                "交叉斩判定 = 场地点 -1 上 1500×2000 矩形（≥1080×1920 全屏）、時空領域只在旗号 1 开支；"
                                "六处说明都写出这三项事实且无旧写法",
                    "kept": "「展开时之魔法阵」（关支也有時空陣演出 ShowEffect）、action 的括注与 text 的其余字面不动",
                },
                "panel": "队长面板自动生成（无覆盖文案），客户端按 536 行前置拼「光属性共鸣时」+ 强化条目",
                "kept": "技能名、其余技能说明字面（除 desc_fixes 三处）、队长行（除 #6–#8 成长）、能力行、DSL 一格不动（R4）",
                "server_text": "服务端镜像 [5]/[7] 与 character_text c5/c7 同值；候选服务端镜像整行替换（gerald2 已记 [6] 旧值刷新）",
            },
            "capabilities": [],
            "runtime_verified": False,
        },
    }

# -*- coding: utf-8 -*-
"""黑 139991 ``outlaw_panther_moon``：2026-09-27 平衡调整第三轮（c：成长复核，只改数值）。

口径 = 主会话施工口径 ``growth_c_spec.md``（作者原话 3–6：「成长速度砍到1/10不合理」「砍到4/5，或者7/10」
「可以砍到2/3」「数值尽量取5的倍数」）＋ 复核表 ``reeval_full.json`` ``table.rows`` 黑 2 行。输入 = 当前 live
（链尾 1.4.1053；与第二批 :mod:`wf_balance_20260927b_kuro` 的 revise() 输出逐字相同）。

第二批把两条无上限成长放缓（×1/10、×1/5）；本轮按「原值」＝第二批前的值重算，取整后落 5 的倍数：

1. ``ability:1399912#3``（前置1 42 仅队长 ＋ 前置2 雷共鸣；第二批从能力2#0「给队长、不限次」拆出）：
   技能每命中 → 自身攻击力 原 50%（批二 5%）→ **35%**（2/3 档：命中极频繁、又有大额固定攻击；
   50×2/3 = 33.3，2/3 档一律向上取 5 的倍数）。c51/c52 5000 → 35000，其余格逐字不动。
2. ``leader_ability:139991#4``（第二批从能力3#1 搬入）：每次进入 Fever → 雷队直击 原 150%（批二 30%）→
   **105%**（7/10 档：快进快出 Fever、又有 Fever 中直击 +400% 固定值；150×7/10 = 105，已是 5 的倍数）。
   c49/c50 30000 → 105000，其余格逐字不动。
3. 队长面板 ``desc_override_outlaw_panther_moon`` 第 5、6 行同步数字（这两行的数据分别在能力2#3、队长#4）。

不动（口径 D3/D4）：能力3#1 封顶版（40%×3）及其面板行；不给队长#4 新增共鸣前置
（复核意见列出的「缺前置共鸣」按 D3 只改数值）。技能 DSL、技能描述、character_text 不改（第 7 节只读核对）。

6. 作者追加（2026-09-27，看平衡预览第 5 版黑卡片「能力2：队长攻击力 {+50%|+2%}，改为最多25次」后原话
   「黑豹能力2改成5刃25次暖满」；「5刃」=5%、「暖满」=叠满，输入法错字）：``ability:1399912#0``（第二批封顶版：
   雷共鸣 技能每命中 → 队长攻击力，最多 25 次）每次 2% → **5%**，次数上限 25 不变，叠满 +50% → **+125%**。
   c51/c52 2000 → 5000，其余格逐字不动（同键 #3 第二批写的正是 5000，行形照官方 1610054#0）。
   该行不再属于上面 D4 的「封顶版不动」。能力2 面板 ``desc_override_outlaw_panther_moon_2`` 第 1 行同步数字，
   第 2 行（豹步）逐字不动；能力2 #0/#1 触发、前置、次数上限各不同 ⇒ 无可并组。

4. 面板同条件合并（作者 2026-09-27「同一个条件的提升能不能写到一起来简化描述」；规则 = 主会话合并规则：
   只并同一面板里数据条件完全相同的行，每个效果原措辞与数值保留，只省略重复的对象名，合并行放组首行位置）：
   - 队长 #0/#1（持续·Fever，赋予全队(雷)，除效果 kind 与数值外逐列相同）：第 1、2 行 →
     「Fever中：赋予雷属性角色直接攻击伤害＋400%、攻击力＋200%」；
   - 能力6 ``1399916`` #0/#1（无条件常驻，赋予全队(雷)，c1=true，除效果 kind 与数值外逐列相同）：第 1、2 行 →
     「雷属性角色免疫麻痹效果、生命值＋25%」（本轮数值不动的面板，一并返回；能力6 行只读核对）。
   能力4 #0/#1、能力5 #0/#1 同条件组本来各在一行；其余面板无可并组。
   共鸣省略：黑的两个固有状态——「骰运」13999101 只由能力3#3 获取（带雷共鸣），但它提供的效果行（能力3 第 5、6 行）
   本来就没写共鸣；「豹步」13999102 由能力2#2 无前置获取 ⇒ 不省略——没有要删前缀的行。

5. 本轮面板统一口径（主会话 2026-09-27 定稿；只作用于本模块返回的面板，能力3 面板为此一并返回，数值不动）：
   - 口径 3：「雷属性共鸣时：」一律写「雷属性共鸣时，」（:func:`normalize_resonance`；「共鸣时：」后换行接效果的并成一行）。
     队长、能力6 面板本来就是逗号写法；能力3 第 4 行（骰运获取行）冒号改逗号。
   - 口径 5：能力3 第 6 行（骰运 6 层翻倍）两处「攻击力／直击伤害」用了禁用的「／」。这里的「／」不是等级分隔，
     是两个抽取奖励并列（技能 DSL 里攻击力、直击伤害两格各自翻倍到＋1000%，持续仍 15 秒）⇒ 拆成分项写
     「攻击力＋1000%、直击伤害＋1000%」「攻击力、直击伤害仍持续15秒」，同一条件（骰运 6 层）仍写在同一行。
   能力4 面板（仍有「雷属性共鸣时：」冒号写法）本轮不返回、不改；能力1 面板因第 7 节返回，一并按口径 3 写逗号。
   第 7 节（R2）删去能力3 第 5、6 行后，口径 5 拆「／」的那一行随之不在面板里（拆分只留作镜像上一稿识别）。

7. 技能强化条目（主会话 2026-09-27 口径 R1–R4；作者原话「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,
   技能里面不要重复描述强化后的效果,规范并简化描述做了吗」；本节只改文字）：
   - R1（:func:`switch_basis`、:func:`skill_flag_basis`，revise() 内 fail closed）：黑唯一的技能开关 = ``ability:1399911#1``
     （kind 536 → 旗号 1，前置 kind 2 雷≥6，c1=true，c70 = ``change_skill_outlaw_panther_moon``）；能力2–6 与队长表没有
     536/704–708 行。两档技能 DSL 各有一个顶层 ``ConditionalsChangeSkillFlag(1)``：开支判定区 = 关支判定区逐节点相同，
     只差寿命 60→180 帧、段数 15→45（两条特效寿命与收碗等待同步）与 ``CreateNormalAttack[8]`` 连击加成 False→True；
     开支另有 6 个等权 ``ConditionalsProbability`` 轮盘（第 2–6 个由 DCUnique「骰运」≥2…6 逐层开门 ⇒ 抽取次数随层数提升；
     每项奖励再由「骰运」≥6 换成 ``wf_kuro_full_dice.doubled`` 翻倍版）。判定区 buffTargetAs（CreateHitArea[24]）两支都是 4
     ⇒「按直接攻击伤害判定」是技能本体（技能描述已写「以直接攻击伤害判定」），不是强化。
   - R2：``change_skill_outlaw_panther_moon`` 改官方格式、点名『博饼·满堂彩』、定性（无数字 / 秒数）：删去「并按直接攻击伤害判定」；
     能力3 面板第 5、6 行（带数值与秒数的「强化技能：」抽取表、骰运 6 层翻倍表）描述的正是旗号 1 开支（不是技能本体）⇒ 定性并入
     强化条目（「释放后随机抽取增益（六项）…抽取次数随「骰运」层数提升，「骰运」达到上限时增益效果提升」），能力3 这两行删除
     （能力3 没有开关行；「骰运」获取行第 4 行保留）。能力1 面板第 2 行「雷属性共鸣时：强化技能——…」= 开关行（雷共鸣前置、
     c1=true 不带主位图标）⇒ 改为「雷属性共鸣时，」＋ 条目原文。
   - R3（:func:`skill_desc_basis`，只读）：技能描述（action_skill c1 两档、character_text c5/c7、服务端 [5]/[7]）三段 =
     判定区持续伤害（两支相同）/ 开关外 FindAllSubjects(33) 直击伤害与追加直击 / 开关外 StopBall 取消后摇，不含强化后效果 ⇒ 不改。
   - R4：数据与 DSL 不动（新增读取的能力1/3/4/5、技能树、技能描述全部只读）。

生成器 ``wf_midautumn_kit_kuro``（LEADER[4] / ABILITY['1399912'][0]、[3] / PANEL_LEADER / PANEL_ABILITY[1]、[2]、[3]、[6] /
CAS_SKILL_FLAG_TEXT）已同步，测试断言生成器装配 == :func:`revise` 输出；设计镜像（design/kuro.json、rework1/panel/kuro.json）由
:func:`sync_mirrors` 幂等同步（本模块不写；主会话 ``python mod-tools/wf_balance_20260927c_kuro.py --write``）。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Callable

import wf_client_legality as L

CID = "139991"
CODE = "outlaw_panther_moon"
PACKAGES = ["ma-kuro"]
#: 候选 manifest 现值 1.0.2（第二批写入）⇒ 下一号。
PACKAGE_VERSION = {"ma-kuro": "1.0.3"}
#: 候选已声明 kyubi-fever-ratio-v1 / panel-description-override-v2；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 ma-kuro 1.0.2 与 live 在本模块读取的 3 项上逐字相同（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 2                          # master/character c3：雷（0 基内部元素）
ELEMENT_TOKEN = "Yellow"
LEADER_KEY = CID
ABILITY1_KEY = f"{CID}1"             # 只读：第 7 节技能开关行（#1 kind 536）
ABILITY2_KEY = f"{CID}2"
ABILITY3_KEY = f"{CID}3"             # 只读：第 7 节（无开关行；#3 = 骰运获取）
ABILITY4_KEY = f"{CID}4"             # 只读：第 7 节（无开关行）
ABILITY5_KEY = f"{CID}5"             # 只读：第 7 节（无开关行）
ABILITY6_KEY = f"{CID}6"             # 只读：面板合并的数据同条件核对；第 7 节（无开关行）
ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
CAS_LEADER = f"desc_override_{CODE}"
CAS_ABILITY1 = f"desc_override_{CODE}_1"
CAS_ABILITY2 = f"desc_override_{CODE}_2"
CAS_ABILITY3 = f"desc_override_{CODE}_3"
CAS_ABILITY6 = f"desc_override_{CODE}_6"
CAS_SWITCH = f"change_skill_{CODE}"  # 能力1#1 kind 536 的 c70（技能强化条目）
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
ACTION_LEVELS = ("1", "2")
#: 两档技能程序（action_skill c7；★5 路径）。
PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in ACTION_LEVELS}

#: live 输入基线（2026-09-27 本地链尾 1.4.1054，stage_batch.make_read(live_only=True) 只读取数；
#: 与第二批 revise() 输出、候选 ma-kuro 1.0.2 逐字相同；1.4.1054 灰服三角色替换不涉及黑）。
#: 任一不符 ⇒ revise() 拒绝（fail closed）。能力6 行与面板是第 4 节（面板合并）加入的；
#: 能力3 面板是第 5 节（口径 3/5）加入的，同样取自链尾 1.4.1054（= 第二批 revise() 输出）；
#: 能力2 面板是第 6 节（作者追加 5%×25）加入的，取自链尾 1.4.1054（= 第二批 revise() 输出）；
#: 能力1/3/4/5 行、强化条目、能力1 面板、两档技能树、技能描述（action / character_text / 服务端）是第 7 节（R1–R4）加入的，
#: 取自链尾 1.4.1054（全部只读）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", LEADER_KEY): "1d04bf96651f59f7c940254b68ea4899c65b4b5733f6e9ed02cac2dc83a342f5",
    ("ability", ABILITY2_KEY): "e301b5d8f93009161bd15464345a4ed3c0e44634ca824acb7a2c0fdad331fde2",
    ("ability", ABILITY6_KEY): "fb22e3908f603938f2b1910209bac3f08682f615df0f68b4d09ad43e29d3c87a",
    ("cas", CAS_LEADER): "4adc957c815af3368dcde7959cd5b5820324c8f960f78c2e26ab28bb322f7648",
    ("cas", CAS_ABILITY3): "667bf7e01f2e039501c8b95afca063b6bd685ff173b6b2514b839f540dbd26ce",
    ("cas", CAS_ABILITY6): "7150a9333055ed9a8740f0bb9d39d349c45127e113d0080a87335050270cf7a0",
    ("cas", CAS_ABILITY2): "8a395e264116316d88ae514ab0e012fd62ded8e09f862143915fc7b2eaaad6bf",
    ("ability", ABILITY1_KEY): "77bde3ca491c8d67ee4ca10554b06d62f74bdfe5f9ba5ac1c5ca741c0058185d",
    ("ability", ABILITY3_KEY): "9ea2b0ae44574b8d0dab1ff24f9572a1943be9ceb6dff05149cf470cacdb9f53",
    ("ability", ABILITY4_KEY): "ff41b9814c85cf2b96c0e4d79ce187c786569df9fbed8d217ddec15f3713c007",
    ("ability", ABILITY5_KEY): "fc37d03fb4cb834bb7c55d7aeb970765696925335a8744d5488372cfe3a29ecb",
    ("cas", CAS_SWITCH): "fa7642641c86935cfd5cf02bbe184452a2ca87fb15899c11aeb66edd2968573d",
    ("cas", CAS_ABILITY1): "cc6e7b280d5df8c70d809fcd8257902f74fe5f60f7b4592e2566c255b65ddef4",
    ("action", CODE): "98590bf116019f6626afe4994f82d262d14ecd8a4595458bcbd33e2f3f7645bb",
    ("text", CID): "06dbf14794437d4347369c1072bebd82b961f1c235e8739ef02d97d22402af51",
    ("server_text", CID): "06dbf14794437d4347369c1072bebd82b961f1c235e8739ef02d97d22402af51",
    ("dsl", PROGRAMS["1"]): "0a779e3456e7c56ce3e09fa4995b70fe979152dbfb337dd02ff574c20c17042c",
    ("dsl", PROGRAMS["2"]): "6b3552523091c4c28cb4e785cba1770c1ea283ab5d6c43e37e0bc26e52af0ebf",
}

# ------------------------------------------------------------------ 取整

#: 取整规则（复核表 summary）：原值 ≥10% ⇒ 5% 的倍数（2/3 档向上取，其余就近）；原值 ≤10% ⇒ 0.5%。
STEP_WIDE, STEP_NARROW, NARROW_BELOW = 5000, 500, 10000


def rescale(original: int, factor: Fraction, *, up: bool = False) -> int:
    step = STEP_WIDE if original >= NARROW_BELOW else STEP_NARROW
    quotient = Fraction(original) * factor / step
    count = math.ceil(quotient) if up else math.floor(quotient + Fraction(1, 2))
    return count * step


# ------------------------------------------------------------------ 词条行

#: 第二批新增的 ``1399912#3``（整行非空格 = 下表；前置1 42 队长 ＋ 前置2 雷共鸣，target 0 自身，不限次）。
HIT_LEADER_ROW = {
    0: f"{CODE}_2", 1: "true", 2: "attack_common", 3: "0", 5: "0", 6: "42", 13: "2", 16: "600000",
    17: "600000", 18: ELEMENT_TOKEN, 20: "0", 27: "107", 28: "0", 30: "100000", 31: "100000",
    34: "(None)", 35: "0", 39: "(None)", 46: "0", 47: "32", 48: "0", 51: "5000", 52: "5000",
}
#: 第二批新增的队长 ``139991#4``（= ['outlaw_panther_moon','0',''] + 1399913#1[5:]，强度 1/5）。
FEVER_LEADER_ROW = {
    0: CODE, 1: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "8", 28: "100000", 29: "100000",
    32: "(None)", 33: "0", 37: "(None)", 44: "0", 45: "33", 46: "5", 47: ELEMENT_TOKEN,
    49: "30000", 50: "30000",
}
HIT_ROW, FEVER_ROW = 3, 4                # 0 基记录号（能力2 / 队长）
ABILITY2_ROWS, LEADER_ROWS = 4, 5

#: 改动：表 → (记录号, 行形, 强度两列, 第二批值, 原值, 第二批系数分母, 本轮档位, 向上取, 新值, 说明)。
#: 互锁：第二批值 == 原值 / 分母；新值 == 取整(原值 × 档位)。
EDITS = {
    "ability": (HIT_ROW, HIT_LEADER_ROW, (51, 52), "5000", 50000, 10, Fraction(2, 3), True, "35000",
                "技能每命中 → 自身攻击力（仅队长 + 雷共鸣）：原 50% / 批二 5% → 35%（2/3 档，33.3 向上取 35）"),
    "leader": (FEVER_ROW, FEVER_LEADER_ROW, (49, 50), "30000", 150000, 5, Fraction(7, 10), False, "105000",
               "每次进入 Fever → 雷队直击：原 150% / 批二 30% → 105%（7/10 档）"),
}

#: 第 6 节：第二批的 ``1399912#0`` 封顶版（整行非空格 = 下表；雷共鸣 前置 kind 2，trigger 107 技能 Hit，
#: target 2 = 队长，kind 32 攻击力，c34 = 25 次）。
CAP_HIT_ROW = {
    0: f"{CODE}_2", 1: "true", 2: "attack_common", 3: "0", 5: "0", 6: "2", 9: "600000", 10: "600000",
    11: ELEMENT_TOKEN, 13: "0", 20: "0", 27: "107", 28: "0", 30: "100000", 31: "100000", 34: "25", 35: "0",
    39: "(None)", 46: "0", 47: "32", 48: "2", 51: "2000", 52: "2000",
}
CAP_ROW = 0
#: 作者原话（逐字，含输入法错字）与解读。
AUTHOR_CAP_REQUEST = "黑豹能力2改成5刃25次暖满"
#: (记录号, 行形, 强度两列, 第二批值, 新值, 次数上限列, 次数上限, 说明)。叠满 = 新值 × 次数上限。
CAP_EDIT = (CAP_ROW, CAP_HIT_ROW, (51, 52), "2000", "5000", 34, "25",
            "雷共鸣 技能每命中 → 队长攻击力：批二 2%×25（叠满 50%）→ 5%×25（叠满 125%）"
            f"（作者追加「{AUTHOR_CAP_REQUEST}」：5刃=5%、暖满=叠满）")

# ------------------------------------------------------------------ 面板

LEADER_PANEL_KEPT = (
    "Fever中：赋予雷属性角色直接攻击伤害＋400%",
    "Fever中：赋予雷属性角色攻击力＋200%",
    "自身Fever持续时间延长＋25%",
    "雷属性共鸣时，非Fever状态下：发动技能，自身Fever槽＋50%",
)
#: 第二批追加的两行（第 5 行数据 = 能力2#3，第 6 行 = 队长#4）。
OLD_LEADER_ADDED_LINES = (
    "雷属性共鸣时，自身技能每命中1次，自身攻击力＋5%",
    "每次进入Fever：雷属性角色直击伤害＋30%",
)
LEADER_ADDED_LINES = (
    "雷属性共鸣时，自身技能每命中1次，自身攻击力＋35%",
    "每次进入Fever：雷属性角色直击伤害＋105%",
)
#: 第 1–3 节数值改后、第 4 节合并前的队长面板（= 合并校验 check_merge 的原文）。
LEADER_PANEL_NUMERIC = LEADER_PANEL_KEPT + LEADER_ADDED_LINES
#: 队长#0/#1 同条件（持续·Fever → 赋予全队(雷)）：第 1、2 行合并，只省略重复的「赋予雷属性角色」。
FEVER_MERGED_LINE = "Fever中：赋予雷属性角色直接攻击伤害＋400%、攻击力＋200%"
#: 本轮最终队长面板（5 行）。
LEADER_PANEL_NEW = (FEVER_MERGED_LINE,) + LEADER_PANEL_KEPT[2:] + LEADER_ADDED_LINES

#: live 能力6 面板（本轮数值不动）与合并后（能力6#0/#1 同条件：无条件常驻 → 赋予全队(雷)）。
OLD_ABILITY6_LINES = ("雷属性角色免疫麻痹效果", "雷属性角色生命值＋25%")
NEW_ABILITY6_LINES = ("雷属性角色免疫麻痹效果、生命值＋25%",)

#: 合并组：面板键 → (原文行 = 合并校验原文, 最终行, {最终行 0 基: 来源原文行 0 基…}, 数据 (表, 键, 行号, 允许不同的列))。
#: 允许不同的列只有效果 kind 与强度两列（前置 / 触发 / CT / 次数上限 / c1 / 对象 / 属性组都必须逐列相同）。
PANEL_MERGES: dict[str, tuple[tuple[str, ...], tuple[str, ...], dict[int, tuple[int, ...]],
                              tuple[str, str, tuple[int, ...], tuple[int, ...]]]] = {
    CAS_LEADER: (LEADER_PANEL_NUMERIC, LEADER_PANEL_NEW, {0: (0, 1)},
                 ("leader", LEADER_KEY, (0, 1), (107, 111, 112))),
    CAS_ABILITY6: (OLD_ABILITY6_LINES, NEW_ABILITY6_LINES, {0: (0, 1)},
                   ("ability", ABILITY6_KEY, (0, 1), (47, 51, 52))),
}
#: 合并行 → 其来源原文行（测试 / 工作区旧 kit-report 反推用）。
MERGED_LINES = {FEVER_MERGED_LINE: LEADER_PANEL_KEPT[:2], NEW_ABILITY6_LINES[0]: OLD_ABILITY6_LINES}
#: 已逐一核对、本轮不返回的覆盖面板（口径 3 只作用于本轮返回的面板：能力4 仍是 live 的「雷属性共鸣时：」写法）。
#: 能力3（#0–#3 触发/前置各不同，无可并组）因第 5 节口径 3 / 第 7 节 R2 返回，见 ABILITY3_FIXES / ABILITY3_R2_DROPS；
#: 能力1 因第 7 节返回，见 ABILITY1_NO_MERGE。
PANELS_REVIEWED_UNCHANGED = {
    f"desc_override_{CODE}_4": "#0/#1 同条件已在同一行",
    f"desc_override_{CODE}_5": "#0/#1 同条件已在同一行",
}

# ------------------------------------------------------------------ 第 6 节：能力2 面板（作者追加 5%×25）

#: live 能力2 面板（第二批写入；能力2 c1=true，不带主位图标）。第 1 行数据 = 能力2#0，第 2 行 = 能力2#1（豹步）。
OLD_ABILITY2_LINES = ("雷属性共鸣时，自身技能每命中1次，队长攻击力＋2%，最多25次",
                      "自身处于「豹步」状态时：雷属性角色攻击力＋250%")
#: 第 1 行只改数字（2% → 5%），「，最多25次」写法与共鸣前缀不变；第 2 行逐字不动。
NEW_ABILITY2_LINES = ("雷属性共鸣时，自身技能每命中1次，队长攻击力＋5%，最多25次", OLD_ABILITY2_LINES[1])
#: 能力2 面板返回了但没有合并组（本轮合并规则逐键核对）。
ABILITY2_NO_MERGE = ("#0（雷共鸣 + 技能Hit，限25次，给队长）/#1（持有豹步，常驻）/#2（技能发动，获取豹步，面板不显示）/"
                     "#3（仅队长 + 雷共鸣，不限次，面板在队长块）触发、前置、对象、次数上限各不同 ⇒ 无可并组")

# ------------------------------------------------------------------ 第 5 节：本轮面板统一口径（口径 3 / 口径 5）

#: 主位限制槽（能力3 整键 c1="false"）每行自带的图标（与 wf_midautumn_kit_kuro.MAIN_ICON 同值）。
MAIN_ICON = " <icon id='main'>  "
#: live 能力3 面板第 6 行（= wf_kuro_full_dice.TEXT 原文，两处「／」）；第 7 节（R2）整行删除。
FULL_DICE_LINE_BEFORE = ("「骰运」达到6层时，上述抽取奖励翻倍（攻击力／直击伤害＋1000%、Fever增加量翻倍、贯穿30秒、"
                         "连击＋1000、队长技能槽＋30%；攻击力／直击伤害仍持续15秒）")
#: 本模块上一稿按口径 5 把「／」拆成分项的第 6 行（设计镜像现状）；本稿第 7 节删行后只用于识别镜像上一稿。
FULL_DICE_LINE_SPLIT = ("「骰运」达到6层时，上述抽取奖励翻倍（攻击力＋1000%、直击伤害＋1000%、Fever增加量翻倍、贯穿30秒、"
                        "连击＋1000、队长技能槽＋30%；攻击力、直击伤害仍持续15秒）")
_A3_LINES_KEPT = (
    "雷属性共鸣时，非Fever状态下：雷属性角色直接攻击合计每达到45次，自身Fever槽＋35%",
    "每次进入Fever：雷属性角色直击伤害＋40%，最多3次",
    "Fever中：雷属性角色每直击20次，自身Fever槽－50%",
)
#: 骰运获取行（能力3#3：雷共鸣 编成直击每 500 次 → 461 骰运 +1）：live 冒号写法 / 口径 3 逗号写法。
_A3_DICE_BEFORE = "雷属性共鸣时：雷属性角色每直击500次，自身「骰运」＋1层，最多6层"
_A3_DICE_AFTER = "雷属性共鸣时，雷属性角色每直击500次，自身「骰运」＋1层，最多6层"
#: live 能力3 面板第 5 行：旗号 1 开支的随机抽取表（带数值与秒数）；第 7 节（R2）整行删除。
_A3_ROULETTE = ("强化技能：释放技能后，从下列效果中随机抽取一项（抽取次数随「骰运」层数提升，最多6次，"
                "每次独立判定，可能抽到重复效果）：攻击力＋500%（持续15秒）、Fever槽大幅上升、"
                "贯穿效果（持续15秒）、直击伤害＋500%（持续15秒）、连击＋500、队长技能槽＋15%")
#: live 能力3 面板（主位限制槽，每行带图标；本轮数值不动）。
OLD_ABILITY3_LINES = tuple(MAIN_ICON + line for line in (
    *_A3_LINES_KEPT,
    _A3_DICE_BEFORE,
    _A3_ROULETTE,
    FULL_DICE_LINE_BEFORE,
))
#: 本轮能力3 面板：第 4 行冒号改逗号（口径 3）；第 5、6 行（旗号 1 开支的抽取表 / 翻倍表）按 R2 删除、定性并入能力1 强化条目
#: （第 7 节）；第 1–3 行逐字不动。
NEW_ABILITY3_LINES = tuple(MAIN_ICON + line for line in (*_A3_LINES_KEPT, _A3_DICE_AFTER))
#: 本模块上一稿（口径 3/5 后、R2 前）的能力3 面板（不带图标）= 设计镜像现状（上一稿已 --write）；只用于镜像识别。
PREVIOUS_ABILITY3_LINES = (*_A3_LINES_KEPT, _A3_DICE_AFTER, _A3_ROULETTE, FULL_DICE_LINE_SPLIT)
#: 能力3 改字的行（live 0 基行号）→ 口径（测试 / 工作区旧 kit-report 反推用）。
ABILITY3_FIXES = {3: "口径 3：「雷属性共鸣时：」→「雷属性共鸣时，」"}
#: 第 7 节 R2 删除的能力3 行：live 0 基行号 →（原文（不带图标），依据）。
ABILITY3_R2_DROPS: dict[int, tuple[str, str]] = {
    4: (_A3_ROULETTE,
        "旗号 1 开支的 6 个等权 ConditionalsProbability 轮盘（关支与开关外零个）：不是技能本体，是强化内容；带数值与秒数、"
        "挂在没有开关行的能力3 ⇒ 删除，定性并入能力1 强化条目（「释放后随机抽取增益（六项），抽取次数随「骰运」层数提升」）"),
    5: (FULL_DICE_LINE_BEFORE,
        "旗号 1 开支里每项奖励由 DCUnique 骰运≥6 换成翻倍版（wf_kuro_full_dice.doubled）：强化内容 ⇒ 删除，定性并入能力1 "
        "强化条目（「「骰运」达到上限时增益效果提升」）；口径 5 拆「／」随整行删除而不再需要"),
}

_RESONANCE_COLON = re.compile(r"([火水雷风光暗](?:或[火水雷风光暗])*属性共鸣时)[：:]")
_RESONANCE_COLON_AT_END = re.compile(r"属性共鸣时[：:]\s*$")
#: 固有状态与共鸣省略判定（主会话规则：全部获取来源都带同一共鸣才省略）。
UID_DICE, UID_STEP = "13999101", "13999102"
STATE_BASIS = {
    UID_DICE: "「骰运」只由能力3#3 获取（461，前置 kind 2 雷≥6）⇒ 可省略，但它提供的效果（技能 DSL 旗号 1 开支；原写在能力3 "
              "第 5、6 行、本来就没写共鸣，第 7 节后定性写在能力1 强化条目，那一行的「雷属性共鸣时，」来自开关行自身的雷共鸣前置）"
              "⇒ 无行可删",
    UID_STEP: "「豹步」由能力2#2 获取（技能发动 → 461，无前置）⇒ 不省略；能力2 第 2 行本来也没写共鸣",
}

# ------------------------------------------------------------------ 第 7 节：技能强化条目（R1–R4）

#: 作者原话（逐字）。
AUTHOR_SKILL_TEXT_REQUEST = ("角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,"
                             "规范并简化描述做了吗")
SKILL_NAME = "博饼·满堂彩"          # action_skill 第 1 档 c0 / character_text c4（＋档 = 名字 +「＋」）
SWITCH_ROW = 1                      # 能力1#1
SWITCH_FLAG = 1                     # kind 536 → 旗号 1
#: 能切技能旗号的全部 kind（536 = 旗号 1，704–708 = 旗号 2–6）；能力表瞬发 c47 / 持续 c109，队长表 c45 / c107。
FLAG_KINDS = ("536", "704", "705", "706", "707", "708")
#: 能力1#1 整行非空格（kind 536；前置 kind 2 雷≥6；c1=true 可上合击位 ⇒ 面板行不带主位图标；c70 = 强化条目键）。
SWITCH_CELLS = {0: f"{CODE}_1", 1: "true", 2: "special", 3: "0", 5: "0", 6: "2", 9: "600000", 10: "600000",
                11: ELEMENT_TOKEN, 13: "0", 20: "0", 27: "0", 39: "(None)", 46: "0", 47: "536", 70: CAS_SWITCH}
RESONANCE_PREFIX = "雷属性共鸣时，"
#: 判定区 buffTargetAs（CreateHitArea 命令列表下标 24）= 4 按直接攻击伤害判定。
HITAREA_BUFF_TARGET_SLOT, DIRECT_ATTRIBUTION = 24, 4
#: 开支判定区相对关支的全部叶子差异（JSON 对 → 次数）：寿命 60→180 ×3（判定区 + 旋转 / 吹雪两条特效）、段数 15→45 ×2
#: （min / max）、CreateNormalAttack[8] 连击加成 false→true、收碗等待 59→179（= wf_midautumn_kit_kuro._enhance_event 的旋钮）。
ENHANCED_KNOBS = Counter({("60", "180"): 3, ("15", "45"): 2, ("false", "true"): 1, ("59", "179"): 1})
#: 骰运上限（能力3 面板「最多6层」）= 轮盘数 = 翻倍门槛。
DICE_MAX = 6
SELF_SUBJECT, TEAM_SELECTOR, LEADER_SELECTOR = -17, 33, 34
#: 每个轮盘 6 项奖励（骰运 < 6 的原值语句）→ 条目里的定性名；顺序 = 轮盘分支顺序。
REWARD_LABELS = ("攻击力提升", "Fever槽上升", "贯穿效果", "直接攻击伤害提升", "连击增加", "队长技能槽上升")
_AC_LABELS = {"ACAttackPoint": REWARD_LABELS[0], "ACPiercing": REWARD_LABELS[2], "ACDirectDamage": REWARD_LABELS[3]}

#: live 强化条目（change_skill_outlaw_panther_moon）。
OLD_SWITCH_TEXT = "强化『博饼·满堂彩』：摇碗的持续时间延长，威力随连击数提升，并按直接攻击伤害判定"
#: 条目各短语 → 旗号 1 开支里的依据（:func:`skill_flag_basis` 逐条核对；条目按序含这些短语）。
SWITCH_PHRASES = (
    ("摇碗的持续时间延长", "判定区寿命 60→180 帧、段数 15→45（两条特效寿命与收碗等待同步）"),
    ("威力随连击数提升", "CreateNormalAttack[8] enablesComboBonus false→true"),
    ("释放后随机抽取增益", "开支判定区之后追加 6 个等权 ConditionalsProbability 轮盘（关支与开关外零个）"),
    ("（" + "、".join(REWARD_LABELS) + "）",
     "每个轮盘 6 项：自身 ACAttackPoint / AddFeverPoint / 自身 ACPiercing / 自身 ACDirectDamage / AddCombo / "
     "选择器 34（队长）AddSkillPoint，数值全为正"),
    ("抽取次数随「骰运」层数提升", "第 2–6 个轮盘由 DCUnique 13999101（骰运）≥2…6 逐层开门 ⇒ 抽取次数 = max(1, 层数)"),
    ("「骰运」达到上限时增益效果提升", "每项奖励由 DCUnique 13999101 ≥6（= 骰运上限）换成翻倍版（wf_kuro_full_dice.doubled）"),
)
#: R2：官方格式「强化『技能名』：定性说明」，不写数字与秒数，不写共鸣 / 队长条件（面板行由开关行前置加前缀）。
NEW_SWITCH_TEXT = (f"强化『{SKILL_NAME}』：摇碗的持续时间延长，威力随连击数提升；释放后随机抽取增益"
                   f"（{'、'.join(REWARD_LABELS)}），抽取次数随「骰运」层数提升，「骰运」达到上限时增益效果提升")
#: 从条目删去的短语 → 依据（两支相同 ⇒ 技能本体，不是强化）。
SWITCH_REMOVED = {"并按直接攻击伤害判定": "CreateHitArea[24] buffTargetAs 开支 / 关支都是 4（技能本体；技能描述已写"
                                         "「以直接攻击伤害判定」）"}
#: 强化条目的官方格式开头与禁用写法（旧式「强化技能」标签、共鸣 / 队长条件、破折号、已删的伤害归属）。
FLAG_ENTRY_HEAD = f"强化『{SKILL_NAME}』："
FLAG_ENTRY_BANNED = ("强化技能", "属性共鸣时", "担任队长", "强化后", "——", "伤害判定")

#: live 能力1 面板（能力1 c1=true，不带图标）：第 1 行 = #0（211 自身技能槽 50%，无前置），第 2 行 = #1（536 开关行）。
OLD_ABILITY1_LINES = ("战斗开始时：自身技能槽＋50%",
                      "雷属性共鸣时：强化技能——技能的持续时间延长，且威力随连击数提升，按直接攻击伤害判定")
#: R2：第 2 行 = 开关行的共鸣前缀（口径 3 逗号）＋ 条目原文；第 1 行逐字。
ABILITY1_SWITCH_LINE = RESONANCE_PREFIX + NEW_SWITCH_TEXT
NEW_ABILITY1_LINES = (OLD_ABILITY1_LINES[0], ABILITY1_SWITCH_LINE)
ABILITY1_NO_MERGE = "#0（无前置，211 自身技能槽）/#1（雷共鸣，536 技能开关）前置与效果各不同 ⇒ 无可并组"

#: 本轮面板行（不带图标）→ 改前原文行（不带图标）：能力1 强化条目行 / 能力3 骰运行（live 其后两行按 R2 删除）。
#: 测试 / 工作区旧 kit-report 反推用（与 MERGED_LINES 同形）。
PANEL_LINE_ORIGINS = {
    ABILITY1_SWITCH_LINE: (OLD_ABILITY1_LINES[1],),
    _A3_DICE_AFTER: (_A3_DICE_BEFORE, _A3_ROULETTE, FULL_DICE_LINE_BEFORE),
}

#: R3：技能描述（action_skill c1 两档 / character_text c5、c7 / 服务端 [5]、[7]）live 原文逐段 → 依据（只读，不改）。
SKILL_DESC_SEGMENTS = (
    ("手托朱漆骰碗原地摇转，对周围的敌人持续造成雷属性伤害（以直接攻击伤害判定）",
     "开支 / 关支都有判定区 CreateHitArea + CreateNormalAttack，buffTargetAs 两支都是 4"),
    ("赋予队伍全员及协力球直接攻击伤害提升与追加直接攻击效果",
     "开关外 FindAllSubjects(33) 的 ACDirectDamage + ACAdditionalDirectAttack"),
    ("释放技能后不再进入硬直，可立即行动", "开关外 StopBall RestoreToSpeedBeforeActionExecution"),
)
SKILL_DESC = "／".join(segment for segment, _why in SKILL_DESC_SEGMENTS)
#: 技能描述里不得出现的强化描述（R3）。
DESC_BANNED = ("强化", "骰运", "随机", "抽取", "连击数", "持续时间延长", "共鸣", "Fever")
TEXT_NCOLS, ACTION_NCOLS = 12, 24
TEXT_NAME_COLUMNS, TEXT_DESC_COLUMNS = (4, 6), (5, 7)


class KuroBalanceCError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _edit(kind: str, rows: list[list[str]], count: int, width: int) -> list[list[str]]:
    index, shape, cols, batch2, original, slow, factor, up, new, _why = EDITS[kind]
    if len(rows) != count or any(len(r) != width for r in rows):
        raise KuroBalanceCError(f"{kind}: expected {count}×{width}")
    if not _matches(rows[index], width, shape):
        raise KuroBalanceCError(f"{kind}#{index}: not the reviewed batch-2 growth row")
    if [rows[index][c] for c in cols] != [batch2, batch2] or original != int(batch2) * slow:
        raise KuroBalanceCError(f"{kind}#{index}: batch-2 value is not original {original} / {slow}")
    value = rescale(original, factor, up=up)
    if str(value) != new:
        raise KuroBalanceCError(f"{kind}#{index}: computed {value} != reviewed {new}")
    out = deepcopy(rows)
    for col in cols:
        out[index][col] = new
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != [index]:
        raise AssertionError(f"{kind}: touched another record")
    return out


def _cap_edit(rows: list[list[str]]) -> list[list[str]]:
    """第 6 节：#0 封顶版每次 2% → 5%，次数上限 25 不变（叠满 50% → 125%）；其余记录逐字保留。"""
    index, shape, cols, batch2, new, cap_col, cap, _why = CAP_EDIT
    if not _matches(rows[index], ABILITY_NCOLS, shape):
        raise KuroBalanceCError(f"ability#{index}: not the reviewed batch-2 capped skill-hit row")
    if [rows[index][c] for c in cols] != [batch2, batch2] or rows[index][cap_col] != cap:
        raise KuroBalanceCError(f"ability#{index}: batch-2 value is not {batch2}×{cap}")
    out = deepcopy(rows)
    for col in cols:
        out[index][col] = new
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != [index]:
        raise AssertionError("ability: cap edit touched another record")
    return out


def ability2_rows(rows: list[list[str]]) -> list[list[str]]:
    """#3 强度 5% → 35%（第 1 节）；#0 封顶版每次 2% → 5%、最多 25 次不变（第 6 节）；#1、#2 逐字保留。"""
    out = _cap_edit(_edit("ability", rows, ABILITY2_ROWS, ABILITY_NCOLS))
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != sorted((CAP_ROW, HIT_ROW)):
        raise AssertionError("ability: touched a record outside #0/#3")
    return out


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """#4 强度 30% → 105%；#0–#3 逐字保留。"""
    return _edit("leader", rows, LEADER_ROWS, LEADER_NCOLS)


#: 合并组里各来源行共用、合并后只写一次的「条件＋对象」前缀（每个效果的原措辞与数值不动）。
MERGE_SHARED_PREFIX = {CAS_LEADER: "Fever中：赋予雷属性角色", CAS_ABILITY6: "雷属性角色"}


def _single_lines(rows: list[list[str]], key: str) -> tuple[str, ...]:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise KuroBalanceCError(f"{key}: expected one single-column row")
    return tuple(rows[0][0].split("\n"))


def merge_lines(key: str) -> tuple[str, ...]:
    """按 PANEL_MERGES 从原文算合并后的各行：合并行 = 首条来源 +「、」+ 其余来源去掉共用前缀；
    合并行放在组首行位置，其余行逐字、保序。结果必须等于登记的最终文案（fail closed）。"""
    before, after, groups, _data = PANEL_MERGES[key]
    shared = MERGE_SHARED_PREFIX[key]
    merged_at = {min(src): (j, src) for j, src in groups.items()}
    absorbed = {i for src in groups.values() for i in src}
    out = []
    for i, line in enumerate(before):
        if i in merged_at:
            _j, src = merged_at[i]
            lines = [before[k] for k in src]
            if not all(s.startswith(shared) and len(s) > len(shared) for s in lines):
                raise KuroBalanceCError(f"{key}: merge sources do not share {shared!r}")
            out.append(lines[0] + "、" + "、".join(s[len(shared):] for s in lines[1:]))
        elif i not in absorbed:
            out.append(line)
    if tuple(out) != after or any(out[j] != after[j] for j in groups):
        raise KuroBalanceCError(f"{key}: merged panel differs from the registered text")
    return tuple(out)


def merge_data_checks(tables: dict[tuple[str, str], list[list[str]]]) -> dict[str, Any]:
    """合并的数据前提：每组来源行除「效果 kind + 强度两列」外逐列相同（前置 / 触发 / CT / 次数上限 / c1 /
    对象 / 属性组 / 分类列都相同）。"""
    report = {}
    for key, (_before, _after, _groups, (kind, outer, indices, free)) in PANEL_MERGES.items():
        rows = tables[kind, outer]
        width = LEADER_NCOLS if kind == "leader" else ABILITY_NCOLS
        picked = [rows[i] for i in indices]
        if any(len(r) != width for r in picked):
            raise KuroBalanceCError(f"{kind}:{outer}: expected {width} columns")
        diff = sorted({c for r in picked[1:] for c in range(width) if r[c] != picked[0][c]})
        if not set(diff) <= set(free):
            raise KuroBalanceCError(f"{key}: merge rows {kind}:{outer}{list(indices)} differ outside the effect "
                                    f"columns: {[c for c in diff if c not in free]}")
        report[key] = dict(rows=[f"{outer}#{i}" for i in indices], differing_columns=diff,
                           kinds=[r[free[0]] for r in picked])
    return report


def step_basis(ability2: list[list[str]]) -> str:
    """「豹步」13999102 的获取行（能力2#2）无前置 ⇒ 不是共鸣隐含状态（不省略）。"""
    grants = [i for i, r in enumerate(ability2) if r[47] == "461" and r[68] == UID_STEP]
    if grants != [2] or any(ability2[2][b] not in ("", "0") for b in (6, 13, 20)):
        raise KuroBalanceCError(f"{ABILITY2_KEY}: 豹步 grant rows drift: {grants}")
    return f"{ABILITY2_KEY}#2（461，无前置）"


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    if _single_lines(rows, CAS_LEADER) != LEADER_PANEL_KEPT + OLD_LEADER_ADDED_LINES:
        raise KuroBalanceCError(f"{CAS_LEADER}: unexpected panel text")
    return [["\n".join(merge_lines(CAS_LEADER))]]


def ability2_line(row: list[str]) -> str:
    """能力2 面板第 1 行由 #0 数据生成（每次强度、次数上限）：写法同第二批「，最多N次」、共鸣前缀「，」。"""
    return f"雷属性共鸣时，自身技能每命中1次，队长攻击力＋{int(row[51]) // 1000}%，最多{row[34]}次"


def ability2_text(rows: list[list[str]]) -> list[list[str]]:
    """第 6 节：能力2 面板第 1 行 2% → 5%，第 2 行（豹步）逐字不动。"""
    if _single_lines(rows, CAS_ABILITY2) != OLD_ABILITY2_LINES:
        raise KuroBalanceCError(f"{CAS_ABILITY2}: unexpected panel text")
    return [["\n".join(NEW_ABILITY2_LINES)]]


def ability6_text(rows: list[list[str]]) -> list[list[str]]:
    if _single_lines(rows, CAS_ABILITY6) != OLD_ABILITY6_LINES:
        raise KuroBalanceCError(f"{CAS_ABILITY6}: unexpected panel text")
    return [["\n".join(merge_lines(CAS_ABILITY6))]]


def normalize_resonance(text: str) -> str:
    """口径 3：「X属性共鸣时：」一律改成「X属性共鸣时，」；行尾是「X属性共鸣时：」、效果写在下一行的，并成一行
    （续行的主位图标去掉，沿用首行的图标状态）。其余逐字不动。"""
    lines = text.split("\n")
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        joined = bool(_RESONANCE_COLON_AT_END.search(line)) and index + 1 < len(lines)
        line = _RESONANCE_COLON.sub(r"\1，", line.rstrip() if joined else line)
        if joined:
            follow = lines[index + 1]
            line += follow[len(MAIN_ICON):] if follow.startswith(MAIN_ICON) else follow.lstrip()
            index += 1
        out.append(line)
        index += 1
    return "\n".join(out)


def ability3_text(rows: list[list[str]]) -> list[list[str]]:
    """能力3 面板（数值不动）：第 7 节 R2 删去第 5、6 行（旗号 1 开支的抽取表 / 翻倍表，逐字核对）→ 口径 3 冒号改逗号。
    结果必须等于登记的 NEW_ABILITY3_LINES。"""
    live = _single_lines(rows, CAS_ABILITY3)
    if live != OLD_ABILITY3_LINES:
        raise KuroBalanceCError(f"{CAS_ABILITY3}: unexpected panel text")
    kept = []
    for index, line in enumerate(live):
        if index in ABILITY3_R2_DROPS:
            if line != MAIN_ICON + ABILITY3_R2_DROPS[index][0]:
                raise KuroBalanceCError(f"{CAS_ABILITY3} L{index + 1}: not the registered skill-enhancement line")
            continue
        kept.append(line)
    lines = tuple(normalize_resonance("\n".join(kept)).split("\n"))
    if lines != NEW_ABILITY3_LINES:
        raise KuroBalanceCError(f"{CAS_ABILITY3}: normalised panel differs from the registered text")
    return [["\n".join(lines)]]


# ------------------------------------------------------------------ 第 7 节：技能强化条目（R1–R4）


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise KuroBalanceCError(message)


def _is_command(node: Any, name: str) -> bool:
    return (isinstance(node, list) and len(node) == 2 and node[0] == "Command"
            and isinstance(node[1], list) and bool(node[1]) and node[1][0] == name)


def _commands(node: Any, name: str) -> list[list]:
    """树里所有 ``["Command", [name, …]]`` 的参数表（先序）。"""
    found: list[list] = []
    if _is_command(node, name):
        found.append(node[1])
    if isinstance(node, list):
        for item in node:
            found += _commands(item, name)
    elif isinstance(node, dict):
        for item in node.values():
            found += _commands(item, name)
    return found


def _leaf_pairs(a: Any, b: Any, where: str) -> list[tuple[str, str]]:
    """两棵子树逐节点比较：形状（列表长度 / 字典键 / 容器类型）必须相同，返回不同叶子的 JSON 对（严格：false ≠ 0）。"""
    if isinstance(a, list) and isinstance(b, list):
        _require(len(a) == len(b), f"{where}: branch shapes differ")
        return [pair for x, y in zip(a, b) for pair in _leaf_pairs(x, y, where)]
    if isinstance(a, dict) and isinstance(b, dict):
        _require(set(a) == set(b), f"{where}: branch shapes differ")
        return [pair for key in a for pair in _leaf_pairs(a[key], b[key], where)]
    _require(not isinstance(a, (list, dict)) and not isinstance(b, (list, dict)), f"{where}: branch shapes differ")
    ja, jb = json.dumps(a), json.dumps(b)
    return [] if ja == jb else [(ja, jb)]


def _numbers(node: Any) -> list:
    """语句里所有 ``{min, max}`` 数值。"""
    if isinstance(node, dict):
        return [v for k, v in node.items() if k in ("min", "max")] + [n for v in node.values() for n in _numbers(v)]
    if isinstance(node, list):
        return [n for item in node for n in _numbers(item)]
    return []


def _reward_label(statement: Any) -> str | None:
    """轮盘一项奖励（原值语句）→ 条目里的定性名；不认识的形状 = None。"""
    if not (isinstance(statement, list) and len(statement) == 2 and statement[0] == "Command"
            and isinstance(statement[1], list) and statement[1]):
        return None
    payload = statement[1]
    if payload[0] == "CreateCondition" and payload[1] == SELF_SUBJECT and len(payload[2]) == 1:
        return _AC_LABELS.get(payload[2][0][0])
    if payload[0] == "AddFeverPoint":
        return REWARD_LABELS[1]
    if payload[0] == "AddCombo":
        return REWARD_LABELS[4]
    if payload[0] == "FindAllSubjects" and payload[2] == LEADER_SELECTOR and len(_commands(payload, "AddSkillPoint")) == 1:
        return REWARD_LABELS[5]
    return None


def _flag_rows(kind: str, rows: list[list[str]]) -> list[int]:
    cols = (47, 109) if kind == "ability" else (45, 107)
    return [i for i, row in enumerate(rows) if any(c < len(row) and row[c] in FLAG_KINDS for c in cols)]


def switch_basis(abilities: dict[str, list[list[str]]], leader: list[list[str]]) -> dict[str, Any]:
    """R1 数据依据（只读、fail closed）：

    1. 黑全部能力键（1–6）与队长表里切技能旗号的行只有能力1#1：kind 536（旗号 1）、前置 kind 2 雷≥6、c1=true、
       c70 = :data:`CAS_SWITCH` ⇒ 强化条目写在能力1 面板、带「雷属性共鸣时，」、不带主位图标；能力3 没有开关行 ⇒
       它面板里的强化描述（抽取表 / 翻倍表）按 R2 删除。
    2. 能力1#0（面板第 1 行「战斗开始时：自身技能槽＋50%」）= 无前置 211 自身 50%，与 #1 前置不同 ⇒ 不并。
    3. 「骰运」13999101 只由能力3#3 获取（能力3 面板第 4 行，「最多6层」= :data:`DICE_MAX`），队长表不授予。
    """
    _require(sorted(abilities) == list(ABILITY_KEYS), f"abilities {sorted(abilities)} != {list(ABILITY_KEYS)}")
    _require(all(len(r) == ABILITY_NCOLS for rows in abilities.values() for r in rows), "ability shape drift")
    _require(all(len(r) == LEADER_NCOLS for r in leader), "leader shape drift")
    switches = [(key, i) for key, rows in sorted(abilities.items()) for i in _flag_rows("ability", rows)]
    switches += [("leader", i) for i in _flag_rows("leader_ability", leader)]
    _require(switches == [(ABILITY1_KEY, SWITCH_ROW)], f"skill-flag switch rows drift: {switches}")
    ability1 = abilities[ABILITY1_KEY]
    _require(len(ability1) == 2 and _matches(ability1[SWITCH_ROW], ABILITY_NCOLS, SWITCH_CELLS),
             f"{ABILITY1_KEY}#{SWITCH_ROW}: not the reviewed 536 switch row pointing at {CAS_SWITCH}")
    gauge = ability1[0]
    _require((gauge[6], gauge[13], gauge[20], gauge[27], gauge[47], gauge[48], gauge[51], gauge[52])
             == ("0", "0", "0", "0", "211", "0", "50000", "50000"),
             f"{ABILITY1_KEY}#0: not the unconditional self skill-gauge 50% row (panel line 1)")
    dice = [(key, i) for key, rows in sorted(abilities.items()) for i, r in enumerate(rows)
            if r[47] == "461" and r[68] == UID_DICE]
    dice += [("leader", i) for i, r in enumerate(leader) if r[45] == "461" and r[66] == UID_DICE]
    _require(dice == [(ABILITY3_KEY, 3)], f"骰运 grant rows drift: {dice}")
    return {"switch": f"ability:{ABILITY1_KEY}#{SWITCH_ROW}（kind 536 → 旗号 {SWITCH_FLAG}，前置 kind 2 雷≥6，c1=true，"
                      f"c70 {CAS_SWITCH}）",
            "no_switch_elsewhere": [f"ability:{key}" for key in ABILITY_KEYS if key != ABILITY1_KEY] + ["leader_ability"],
            "panel_line": f"{CAS_ABILITY1} L2 =「{RESONANCE_PREFIX}」＋ 条目原文（开关行带雷共鸣前置；c1=true 不带主位图标）",
            "dice_source": f"ability:{ABILITY3_KEY}#3（461 → {UID_DICE}，前置 kind 2 雷≥6）"}


def skill_flag_basis(trees: dict[str, Any]) -> dict[str, Any]:
    """R1 DSL 依据（两档技能树逐一核对，fail closed）：

    - 恰好一个顶层 ``ConditionalsChangeSkillFlag(1)``；开支 = [强化判定区, 轮盘…]，关支 = [常态判定区]。
    - 两支判定区逐节点相同，叶子差异恰好 = :data:`ENHANCED_KNOBS`（寿命 / 段数 / 连击加成 / 特效寿命 / 收碗等待）；
      判定区 buffTargetAs 两支都是 4 ⇒「按直接攻击伤害判定」是本体。
    - 开支轮盘 = 6 个等权 ``ConditionalsProbability``，第 2–6 个由 DCUnique 骰运 ≥2…6 逐层开门；每项奖励 =
      DCUnique 骰运 ≥6 ?「``wf_kuro_full_dice.doubled``(原值)」:「原值」，原值依序 = :data:`REWARD_LABELS`、数值全为正。
    - 开关外（技能本体）：StopBall 取消后摇、FindAllSubjects(33) 直击伤害 + 追加直击；没有判定区 / 轮盘。
    """
    import wf_kuro_full_dice as FD
    report = {}
    for level, program in PROGRAMS.items():
        tree = trees[program]
        _require(isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl"
                 and isinstance(tree[11], list) and tree[11][0] == "Block", f"{program}: not an ActionDsl root")
        statements = tree[11][1]
        flags = _commands(tree, "ConditionalsChangeSkillFlag")
        top = [s[1] for s in statements if _is_command(s, "ConditionalsChangeSkillFlag")]
        _require(len(flags) == 1 and len(top) == 1 and top[0] is flags[0] and flags[0][1] == SWITCH_FLAG,
                 f"{program}: expected one top-level ConditionalsChangeSkillFlag({SWITCH_FLAG})")
        on, off = flags[0][2], flags[0][3]
        outside = [s for s in statements if not _is_command(s, "ConditionalsChangeSkillFlag")]
        _require(isinstance(on, list) and isinstance(off, list) and on[0] == off[0] == "Block"
                 and len(off[1]) == 1 and len(on[1]) >= 2,
                 f"{program}: flag branches are not [hit area, roulette…] / [hit area]")
        plain, enhanced, roulette = off[1][0], on[1][0], on[1][1:]

        knobs = Counter(_leaf_pairs(plain, enhanced, program))
        _require(knobs == ENHANCED_KNOBS, f"{program}: enhanced hit area differs beyond the knobs: {dict(knobs)}")
        hits = [_commands(branch, "CreateHitArea") for branch in (plain, enhanced)]
        cnas = [_commands(branch, "CreateNormalAttack") for branch in (plain, enhanced)]
        _require([len(h) for h in hits] == [1, 1] and [len(c) for c in cnas] == [1, 1],
                 f"{program}: each branch must hold one hit area / one normal attack")
        (hit_off,), (hit_on,) = hits
        (cna_off,), (cna_on,) = cnas
        _require(hit_off[13] == ["SpecifyHitAreaLifetimeDirectly", 60]
                 and hit_on[13] == ["SpecifyHitAreaLifetimeDirectly", 180]
                 and hit_off[15] == ["Some", [{"min": 15, "max": 15}]]
                 and hit_on[15] == ["Some", [{"min": 45, "max": 45}]],
                 f"{program}: hit-area lifetime / hit budget is not 60→180 / 15→45")
        _require(cna_off[8] is False and cna_on[8] is True, f"{program}: combo bonus is not off→on")
        _require(hit_off[HITAREA_BUFF_TARGET_SLOT] == hit_on[HITAREA_BUFF_TARGET_SLOT] == DIRECT_ATTRIBUTION,
                 f"{program}: hit-area attribution is not direct-attack in both branches")

        wheels = _commands(roulette, "ConditionalsProbability")
        _require(len(wheels) == DICE_MAX and not _commands(plain, "ConditionalsProbability")
                 and not _commands(outside, "ConditionalsProbability"),
                 f"{program}: expected {DICE_MAX} roulette wheels in the enhanced branch only")
        gates = _commands(roulette, "ConditionalsConditionAccumulationNumber")
        draw_gates = [g for g in gates if _commands(g[3], "ConditionalsProbability")]
        _require([g[2] for g in draw_gates] == list(range(2, DICE_MAX + 1))
                 and all(g[1] == ["DCUnique", int(UID_DICE)] and g[4] == ["Block", []] for g in draw_gates)
                 and len(gates) == len(draw_gates) + DICE_MAX * len(REWARD_LABELS),
                 f"{program}: draw gates are not DCUnique {UID_DICE} ≥2…{DICE_MAX}")
        for index, wheel in enumerate(wheels):
            branches = wheel[1][1] if isinstance(wheel[1], list) and wheel[1][0] == "Block" else []
            labels = []
            for branch in branches:
                _require(isinstance(branch, list) and branch[0] == "Block" and len(branch[1]) == 2
                         and branch[1][0] == ["Command", ["ProbabilityWeight", 1]],
                         f"{program} wheel {index}: options are not equal-weight")
                body = branch[1][1]
                _require(isinstance(body, list) and body[0] == "Block" and len(body[1]) == 1
                         and _is_command(body[1][0], "ConditionalsConditionAccumulationNumber"),
                         f"{program} wheel {index}: option is not gated by the dice count")
                gate = body[1][0][1]
                _require(gate[1] == ["DCUnique", int(UID_DICE)] and gate[2] == DICE_MAX
                         and isinstance(gate[4], list) and gate[4][0] == "Block" and len(gate[4][1]) == 1,
                         f"{program} wheel {index}: doubling gate is not DCUnique {UID_DICE} ≥{DICE_MAX}")
                base = gate[4][1][0]
                try:
                    doubled = FD.doubled(base)
                except (ValueError, TypeError, KeyError, IndexError) as error:
                    raise KuroBalanceCError(f"{program} wheel {index}: reward not doublable ({error})") from error
                _require(gate[3] == ["Block", [doubled]] and doubled != base,
                         f"{program} wheel {index}: the ≥{DICE_MAX} branch is not the doubled reward")
                numbers = _numbers(base)
                _require(bool(numbers) and all(isinstance(n, (int, float)) and not isinstance(n, bool) and n > 0
                                               for n in numbers), f"{program} wheel {index}: reward is not a gain")
                labels.append(_reward_label(base))
            _require(tuple(labels) == REWARD_LABELS,
                     f"{program} wheel {index}: rewards {labels} != {list(REWARD_LABELS)}")

        _require(not _commands(outside, "CreateHitArea"), f"{program}: a hit area sits outside the switch")
        stops = _commands(outside, "StopBall")
        _require(len(stops) == 1 and stops[0][3] == ["RestoreToSpeedBeforeActionExecution"],
                 f"{program}: StopBall outside the switch is not the no-endlag form")
        team = [c for c in _commands(outside, "FindAllSubjects") if c[2] == TEAM_SELECTOR]
        acs = sorted(cc[2][0][0] for t in team for cc in _commands(t, "CreateCondition"))
        _require(len(team) == 1 and acs == ["ACAdditionalDirectAttack", "ACDirectDamage"],
                 f"{program}: team buff outside the switch is not direct damage + additional direct attack: {acs}")
        report[level] = {"flag": f"顶层 ConditionalsChangeSkillFlag({SWITCH_FLAG}) ×1",
                         "knobs": {f"{a}→{b}": n for (a, b), n in sorted(ENHANCED_KNOBS.items())},
                         "attribution_both_branches": DIRECT_ATTRIBUTION,
                         "wheels": len(wheels), "draw_gates": [g[2] for g in draw_gates],
                         "rewards": list(REWARD_LABELS), "doubled_at": DICE_MAX}
    return report


def flag_entry_problems(text: str) -> list[str]:
    """R2：强化条目用官方格式点名技能，定性无数字 / 秒数 / %（kitlib skill_flag 门），不写共鸣 / 队长条件与旧标签；
    条目按序含 :data:`SWITCH_PHRASES` 的每个短语（每个短语在 :func:`skill_flag_basis` 有 DSL 依据）。"""
    import wf_midautumn_kitlib as KL
    problems = [f"skill flag: {p}" for p in KL.panel_problems(text, skill_flag=True)]
    if not text.startswith(FLAG_ENTRY_HEAD):
        problems.append(f"skill flag: must start with {FLAG_ENTRY_HEAD!r}")
    problems += [f"skill flag: banned wording {w!r}" for w in FLAG_ENTRY_BANNED if w in text]
    positions = [text.find(phrase) for phrase, _why in SWITCH_PHRASES]
    if -1 in positions or positions != sorted(positions):
        problems.append("skill flag: entry does not carry every DSL-backed phrase in order")
    problems += [f"skill flag: removed phrase {w!r} still present" for w in SWITCH_REMOVED if w in text]
    return problems


def switch_text(rows: list[list[str]]) -> list[list[str]]:
    """R2：强化条目 live 原文 → 官方格式定性条目；原文必须逐字相符（fail closed）。"""
    _require(_single_lines(rows, CAS_SWITCH) == (OLD_SWITCH_TEXT,), f"{CAS_SWITCH}: unexpected skill-enhancement text")
    problems = flag_entry_problems(NEW_SWITCH_TEXT)
    _require(not problems, "; ".join(problems))
    return [[NEW_SWITCH_TEXT]]


def ability1_text(rows: list[list[str]]) -> list[list[str]]:
    """R2：能力1 面板第 2 行（开关行）=「雷属性共鸣时，」＋ 条目原文；第 1 行逐字。原文必须逐字相符（fail closed）。"""
    _require(_single_lines(rows, CAS_ABILITY1) == OLD_ABILITY1_LINES, f"{CAS_ABILITY1}: unexpected panel text")
    return [["\n".join(NEW_ABILITY1_LINES)]]


def skill_desc_basis(action: list, text: list[list[str]], server_text: list[list[str]]) -> dict[str, Any]:
    """R3（只读、fail closed）：技能描述四处（action_skill c1 两档、character_text c5/c7、服务端 [5]/[7]）逐字 =
    :data:`SKILL_DESC`（三段都是开关外或两支相同的本体，见 :data:`SKILL_DESC_SEGMENTS`），不含强化描述 ⇒ 不改。"""
    levels = [inner for inner, _fields in action]
    _require(levels == list(ACTION_LEVELS), f"action_skill {CODE} levels {levels}")
    for (inner, fields), name in zip(action, (SKILL_NAME, SKILL_NAME + "＋")):
        _require(len(fields) == ACTION_NCOLS and fields[0] == name and fields[7] == PROGRAMS[inner]
                 and fields[1] == SKILL_DESC,
                 f"action_skill {CODE}/{inner}: name / program / c1 differ from the reviewed text")
    for kind, rows in (("text", text), ("server_text", server_text)):
        _require(isinstance(rows, list) and len(rows) == 1 and len(rows[0]) == TEXT_NCOLS,
                 f"{kind}:{CID}: expected one {TEXT_NCOLS}-column row")
        _require([rows[0][c] for c in TEXT_NAME_COLUMNS] == [SKILL_NAME, SKILL_NAME + "＋"],
                 f"{kind}:{CID}: skill names drifted")
        _require(all(rows[0][c] == SKILL_DESC for c in TEXT_DESC_COLUMNS),
                 f"{kind}:{CID}: description differs from action c1")
    leaked = [word for word in DESC_BANNED if word in SKILL_DESC]
    _require(not leaked, f"skill description carries enhanced wording {leaked}")
    return {"where": "action_skill c1 ×2、character_text c5/c7、服务端 cdndata/character_text [5]/[7]",
            "verdict": "逐字相同、只写技能本体（R3 已满足），不改",
            "segments": {segment: why for segment, why in SKILL_DESC_SEGMENTS}}


def panel_rule_problems(key: str, text: str) -> list[str]:
    """本轮返回面板的统一口径：共鸣只写「X属性共鸣时，」（口径 3，且规范化是恒等）、不含「／」（口径 5）。"""
    problems = []
    if _RESONANCE_COLON.search(text) or normalize_resonance(text) != text:
        problems.append(f"{key}: resonance must read 「X属性共鸣时，」")
    if "／" in text:
        problems.append(f"{key}: panel still carries 「／」")
    return problems


def row_problems(kind: str, row: list[str]) -> list[str]:
    return (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
            + L.invoke_skill_string_problems(row, set(), kind=kind)
            + L.ability_element_column_problems(kind, row, ELEMENT))


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        got = digest(value)
        if got != want:
            raise KuroBalanceCError(f"unreviewed live baseline for {kind}:{key} ({got} != {want})")
        inputs[kind, key] = deepcopy(value)

    ability2 = ability2_rows(inputs["ability", ABILITY2_KEY])
    leader = leader_rows(inputs["leader", LEADER_KEY])
    merges = merge_data_checks({("leader", LEADER_KEY): leader,
                                ("ability", ABILITY6_KEY): inputs["ability", ABILITY6_KEY]})
    step = step_basis(inputs["ability", ABILITY2_KEY])
    problems = [f"leader#{i}: {p}" for i, row in enumerate(leader) for p in row_problems("leader_ability", row)]
    problems += [f"{ABILITY2_KEY}#{i}: {p}" for i, row in enumerate(ability2) for p in row_problems("ability", row)]
    if L.required_client_capabilities("leader_ability", leader[FEVER_ROW]) \
            or L.required_client_capabilities("ability", ability2[HIT_ROW]) \
            or L.required_client_capabilities("ability", ability2[CAP_ROW]):
        problems.append("changed rows unexpectedly need client capabilities")
    # 第 7 节（R1–R4）：先按数据 / DSL / 技能描述核对依据（全部只读），再改强化条目与能力1 面板；能力3 面板的 R2 删行在 ability3_text。
    switch = switch_basis({key: inputs["ability", key] for key in ABILITY_KEYS}, inputs["leader", LEADER_KEY])
    flag = skill_flag_basis({program: inputs["dsl", program] for program in PROGRAMS.values()})
    desc = skill_desc_basis(inputs["action", CODE], inputs["text", CID], inputs["server_text", CID])
    cas = {CAS_LEADER: leader_text(inputs["cas", CAS_LEADER]),
           CAS_ABILITY1: ability1_text(inputs["cas", CAS_ABILITY1]),
           CAS_ABILITY2: ability2_text(inputs["cas", CAS_ABILITY2]),
           CAS_ABILITY3: ability3_text(inputs["cas", CAS_ABILITY3]),
           CAS_ABILITY6: ability6_text(inputs["cas", CAS_ABILITY6]),
           CAS_SWITCH: switch_text(inputs["cas", CAS_SWITCH])}
    if ability2_line(ability2[CAP_ROW]) != NEW_ABILITY2_LINES[0] \
            or ability2_line(inputs["ability", ABILITY2_KEY][CAP_ROW]) != OLD_ABILITY2_LINES[0]:
        problems.append(f"{CAS_ABILITY2}: line 1 disagrees with {ABILITY2_KEY}#{CAP_ROW}")
    ability1_lines = cas[CAS_ABILITY1][0][0].split("\n")
    if ability1_lines[1] != RESONANCE_PREFIX + cas[CAS_SWITCH][0][0] or any(line.startswith(MAIN_ICON)
                                                                             for line in ability1_lines):
        problems.append(f"{CAS_ABILITY1}: switch line is not 「{RESONANCE_PREFIX}」 + {CAS_SWITCH} (no main icon, c1=true)")
    if any(text in "\n".join(cas[key][0][0] for key in cas) for text in (_A3_ROULETTE, FULL_DICE_LINE_BEFORE,
                                                                       FULL_DICE_LINE_SPLIT, OLD_SWITCH_TEXT)):
        problems.append("a numeric / old skill-enhancement line is still on a returned panel")
    problems += [p for key, rows in cas.items() for p in panel_rule_problems(key, rows[0][0])]
    if problems:
        raise KuroBalanceCError("; ".join(problems))
    return {
        "ability": {ABILITY2_KEY: ability2},
        "leader": {LEADER_KEY: leader},
        "cas": cas,
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_kuro.py",
            "batch": "2026-09-27 第三轮（成长复核，只改数值；面板同条件合并；面板统一口径 3/5；作者追加能力2 5%×25；"
                     "技能强化条目 R1–R4）",
            "spec": "growth_c_spec.md（作者原话 3–6、D2–D4）；reeval_full.json table.rows 黑 2 行；"
                    f"作者追加原话「{AUTHOR_CAP_REQUEST}」（第 6 节）；主会话口径 R1–R4、作者原话「{AUTHOR_SKILL_TEXT_REQUEST}」"
                    "（第 7 节）",
            "changes": {
                f"ability:{ABILITY2_KEY}#{HIT_ROW}": EDITS["ability"][-1],
                f"leader_ability:{LEADER_KEY}#{FEVER_ROW}": EDITS["leader"][-1],
                f"ability:{ABILITY2_KEY}#{CAP_ROW}": CAP_EDIT[-1],
            },
            "frequency_3min": {
                "skill_hit": "强化技能每发约 15 hit，3 分钟 7–9 发 ⇒ 105–135 次（设计稿，推断）→ 易",
                "fever_entry": "3 分钟 8–12 次（设计稿，推断）→ 中；黑本身设计为快进快出 Fever",
            },
            "growth_3min": {
                "self_attack_120_hits": "原 6000% / 批二 600%+50%（能力2 封顶版）/ 本轮 4200%+125%"
                                        "（封顶版 5%×25 叠满；黑自身为队长时两条都落在自身）",
                "thunder_team_direct_10_fevers": "原 1500% / 批二 300%+120%（能力3 封顶版）/ 本轮 1050%+120%",
            },
            "rounding": "2/3 档一律向上取 5 的倍数（33.3 → 35），7/10 档 105 已是 5 的倍数",
            "kept": [f"ability:{CID}3#1 封顶版 40%×3（D4）",
                     f"leader_ability:{LEADER_KEY}#4 不加共鸣前置（D3，复核意见「缺前置共鸣」只作知情）",
                     f"ability:{ABILITY2_KEY}#{CAP_ROW} 次数上限 25 与其余格（第 6 节只改每次强度）",
                     "技能 DSL 两档、action_skill、character_text、服务端文案逐字不动（第 7 节 R3/R4，只读核对）"],
            "panel": {CAS_LEADER: list(LEADER_ADDED_LINES) + [f"L1+L2 合并：{FEVER_MERGED_LINE}"],
                      CAS_ABILITY1: [f"L2（第 7 节 R2）：{ABILITY1_SWITCH_LINE}"],
                      CAS_ABILITY2: [f"L1（第 6 节）：{NEW_ABILITY2_LINES[0]}"],
                      CAS_ABILITY3: [f"L{i + 1}（{why.split('：')[0]}）：{NEW_ABILITY3_LINES[i].replace(MAIN_ICON, '')}"
                                     for i, why in ABILITY3_FIXES.items()]
                                    + [f"L{i + 1} 删除（第 7 节 R2）：{text}" for i, (text, _why) in ABILITY3_R2_DROPS.items()],
                      CAS_ABILITY6: [f"L1+L2 合并：{NEW_ABILITY6_LINES[0]}"],
                      CAS_SWITCH: [NEW_SWITCH_TEXT]},
            "panel_rules_20260927": {
                "resonance_punctuation": "口径 3：本模块返回的队长 / 能力1 / 能力2 / 能力3 / 能力6 面板里共鸣一律写「雷属性共鸣时，」"
                                         "（队长、能力2、能力6 本来就是；能力1 第 2 行随第 7 节改写、能力3 第 4 行冒号改逗号）；"
                                         "未返回的能力4 面板不动",
                "slash_split": f"{CAS_ABILITY3} 第 6 行（骰运 6 层翻倍表）的两处「／」：第 7 节 R2 整行删除 ⇒ 口径 5 不再适用"
                               "（上一稿拆成的分项写法只留作镜像识别）",
            },
            "skill_enhancement": {
                "rule": "主会话 2026-09-27 口径 R1–R4：R1 技能强化 = 536/704–708 开关行打开、DSL ConditionalsChangeSkillFlag 分支"
                        "生效的效果；R2 强化只写在队长 / 能力强化条目（官方格式「强化『技能名』：定性说明」，点名技能、不写数字秒数；"
                        "面板行在开关行带共鸣前置时加「X属性共鸣时，」、主位开关行加主位图标）；R3 技能描述只写本体；R4 只改文字",
                "switch": switch,
                "dsl": flag,
                "entry": {"from": OLD_SWITCH_TEXT, "to": NEW_SWITCH_TEXT,
                          "phrases": {phrase: why for phrase, why in SWITCH_PHRASES},
                          "removed": SWITCH_REMOVED},
                "panel_ability1": {"from": OLD_ABILITY1_LINES[1], "to": ABILITY1_SWITCH_LINE},
                "panel_ability3_dropped": {f"L{i + 1}": {"text": text, "why": why}
                                           for i, (text, why) in ABILITY3_R2_DROPS.items()},
                "skill_description": desc,
            },
            "panel_merge": {
                "rule": "作者 2026-09-27「同一个条件的提升能不能写到一起来简化描述」；主会话合并规则（只并同一面板里"
                        "数据条件完全相同的行，效果原措辞与数值保留，只省略重复对象名，合并行放组首行位置）",
                "merges": {key: {"from": list(before), "to": list(after)}
                           for key, (before, after, _g, _d) in PANEL_MERGES.items()},
                "data": merges,
                "resonance_drops": "无（" + "；".join(STATE_BASIS.values()) + f"；豹步来源 {step}）",
                "reviewed_unchanged": PANELS_REVIEWED_UNCHANGED,
                "no_merge": {CAS_ABILITY1: ABILITY1_NO_MERGE, CAS_ABILITY2: ABILITY2_NO_MERGE},
                "check_merge": "五块面板过 wf_panel_merge_check.check（队长 / 能力2 原文 = 本轮数值改后文案；能力3 原文 = "
                               "live 删去 R2 两行后经口径 3 规范化；能力1 原文 = live 换上 R2 强化条目行）与 panel_problems",
            },
            "generator": "wf_midautumn_kit_kuro.py（LEADER[4]、ABILITY['1399912'][0]、[3]、PANEL_LEADER、"
                         "PANEL_ABILITY[1]、[2]、[3]、[6]、CAS_SKILL_FLAG_TEXT 已同步）",
            "capabilities": [],
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/kuro.json"
PANEL_REL = BATCH / "rework1/panel/kuro.json"

MIRROR_TAG = "balance_20260927c"
MIRROR_NOTE = ("2026-09-27：作者平衡第三轮（成长复核）——第二批 ×1/10、×1/5 改为按原值分档："
               "能力2#3（仅队长 + 雷共鸣）技能每命中自身攻击力 5%→35%（原 50%，2/3 档向上取 5 的倍数）；"
               "队长#4 每次进入Fever 雷队直击 30%→105%（原 150%，7/10 档）。队长面板第 5、6 行同步；"
               "能力3#1 的封顶版保持第二批。作者追加（「黑豹能力2改成5刃25次暖满」）：能力2#0 封顶版（雷共鸣 技能每命中"
               "→ 队长攻击力）每次 2%→5%，最多 25 次不变（叠满 50%→125%），能力2 面板第 1 行同步。面板同条件合并：队长第 1、2 行（队长#0/#1 持续·Fever）并为"
               "「Fever中：赋予雷属性角色直接攻击伤害＋400%、攻击力＋200%」，能力6 两行（#0/#1 无条件常驻）并为"
               "「雷属性角色免疫麻痹效果、生命值＋25%」；无共鸣前缀可省略。面板统一口径：能力3 第 4 行共鸣前缀写"
               "「雷属性共鸣时，」。技能强化条目（主会话口径 R1–R4，作者「技能里面不要重复描述强化后的效果,规范并简化描述」）："
               "change_skill 条目改官方格式「强化『博饼·满堂彩』：…」（定性，删去两支相同的「并按直接攻击伤害判定」，"
               "并入旗号 1 开支的随机抽取与骰运满层增益提升），能力1 第 2 行＝「雷属性共鸣时，」＋条目；能力3 第 5、6 行"
               "（带数值与秒数的抽取表、骰运 6 层翻倍表，属强化分支）删除；技能说明只写本体、不改。能力3 镜像按生成器整块同步"
               "（顺带补上 09-21/09-23 留下的既有漂移：骰运获取 1000 次 → 500 次）。")
#: 镜像 rework1/panel/kuro.json 能力3 的既有漂移稿（09-21/09-23 两轮修订留下：骰运获取写「每直击1000次」、
#: 缺「骰运6层翻倍」行；第二批只改了第 2 行，见 wf_balance_20260927b_kuro.mirror_updates 注释）。
#: 本轮能力3 面板由本模块返回 ⇒ 镜像能力3 按生成器整块同步；只认这一版旧稿、本模块上一稿（:data:`PREVIOUS_ABILITY3_LINES`，
#: 口径 3/5 后、R2 前，已 --write）或已同步稿，其余一律当漂移拒绝。
MIRROR_ABILITY3_DRIFTED = (
    *_A3_LINES_KEPT,
    "雷属性共鸣时：雷属性角色每直击1000次，自身「骰运」＋1层，最多6层",
    _A3_ROULETTE,
)


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等；第二批的镜像块与注记逐字保留）。"""
    import wf_midautumn_kit_kuro as K
    design, panel = deepcopy(design), deepcopy(panel)

    plan = design["plan"]
    leader = plan["leader_ability"]
    if [row.get("index") for row in leader["rows"]] != list(range(len(K.LEADER))):
        raise ValueError("design leader rows layout drifted")
    donor, cells, expect = K.LEADER[FEVER_ROW]
    row = leader["rows"][FEVER_ROW]
    if row.get("donor") != donor:
        raise ValueError(f"design leader#{FEVER_ROW} donor drifted: {row.get('donor')!r}")
    row.update(desc_expected=expect, cells={str(k): v for k, v in sorted(cells.items())})
    leader[MIRROR_TAG] = "#4「每次进入Fever→雷队直击」30%→105%（原 150%，7/10 档）"

    key = plan["ability"]["keys"][ABILITY2_KEY]
    if [r.get("index") for r in key["records"]] != list(range(len(K.ABILITY[ABILITY2_KEY]))):
        raise ValueError(f"design ability {ABILITY2_KEY} records layout drifted")
    for index in (CAP_ROW, HIT_ROW):
        donor, cells, expect = K.ABILITY[ABILITY2_KEY][index]
        record = key["records"][index]
        if record.get("donor") != donor:
            raise ValueError(f"design ability {ABILITY2_KEY}#{index} donor drifted: {record.get('donor')!r}")
        record.update(desc_expected=expect, cells={str(k): v for k, v in sorted(cells.items())})
    key[MIRROR_TAG] = ("#3 技能每命中→自身攻击力 5%→35%（原 50%，2/3 档向上取）；"
                       "#0 封顶版技能每命中→队长攻击力 2%→5%（最多 25 次不变，作者追加）")

    rows = plan["texts"]["custom_ability_string"]["rows"]
    for text_row in rows:
        if text_row["key"] in K.CAS_TEXTS:
            text_row["text"] = K.CAS_TEXTS[text_row["key"]]
    if {text_row["key"]: text_row["text"] for text_row in rows} != K.CAS_TEXTS:
        raise ValueError("design custom_ability_string still differs from the generator")
    design[MIRROR_TAG] = dict(spec="第三轮成长复核：原值×档位（2/3、7/10），取 5 的倍数；只改数值。"
                                   "作者追加：能力2#0 封顶版 2%×25 → 5%×25。"
                                   "面板同条件合并：队长第 1、2 行、能力6 两行各并一行（数据同条件，措辞与数值不变）。"
                                   "面板统一口径：能力3 第 4 行共鸣写「雷属性共鸣时，」。"
                                   "技能强化条目 R1–R4：change_skill 条目官方格式定性、能力1 第 2 行同文加共鸣前缀、"
                                   "能力3 第 5、6 行（强化分支的抽取表 / 翻倍表）删除；技能说明不改",
                              module="mod-tools/wf_balance_20260927c_kuro.py")

    if tuple(K.PANEL_LEADER) != LEADER_PANEL_NEW:
        raise ValueError("generator PANEL_LEADER differs from the batch-c leader panel")
    if tuple(K.PANEL_ABILITY[2]) != NEW_ABILITY2_LINES:
        raise ValueError("generator PANEL_ABILITY[2] differs from the batch-c ability 2 panel")
    if tuple(K.PANEL_ABILITY[6]) != NEW_ABILITY6_LINES:
        raise ValueError("generator PANEL_ABILITY[6] differs from the batch-c ability 6 panel")
    new_three = tuple(line.replace(MAIN_ICON, "") for line in NEW_ABILITY3_LINES)
    if tuple(K.PANEL_ABILITY[3]) != new_three:
        raise ValueError("generator PANEL_ABILITY[3] differs from the batch-c ability 3 panel")
    if tuple(K.PANEL_ABILITY[1]) != NEW_ABILITY1_LINES:
        raise ValueError("generator PANEL_ABILITY[1] differs from the batch-c ability 1 panel")
    if K.CAS_TEXTS[CAS_SWITCH] != NEW_SWITCH_TEXT or K.CAS_SKILL_FLAG_TEXT != NEW_SWITCH_TEXT:
        raise ValueError("generator skill-enhancement entry differs from the batch-c entry")
    # 队长：第二批镜像（或本轮数值改后、合并前）→ 本轮最终 5 行；能力6：两行 → 合并一行；
    # 能力3：已知漂移稿 / 本模块上一稿 → 生成器整块（口径 3 + R2 删行）；能力2：第 1 行 2% → 5%（第 6 节），第 2 行不动；
    # 能力1：第 2 行 → R2 强化条目行（第 7 节），第 1 行不动。其余能力面板不动。
    leader_texts = tuple(line.get("text") for line in panel["leader"]["lines"])
    if leader_texts in (LEADER_PANEL_KEPT + OLD_LEADER_ADDED_LINES, LEADER_PANEL_NUMERIC):
        panel["leader"]["lines"] = [dict(text=text, status="changed") for text in LEADER_PANEL_NEW]
    elif leader_texts != LEADER_PANEL_NEW:
        raise ValueError("panel mirror leader layout drifted")
    two = next(entry for entry in panel["abilities"] if int(entry["index"]) == 2)
    two_texts = tuple(line.get("text") for line in two["lines"])
    if two_texts == OLD_ABILITY2_LINES:
        two["lines"][0] = dict(two["lines"][0], text=NEW_ABILITY2_LINES[0], status="changed")
    elif two_texts != NEW_ABILITY2_LINES:
        raise ValueError("panel mirror ability 2 layout drifted")
    one = next(entry for entry in panel["abilities"] if int(entry["index"]) == 1)
    one_texts = tuple(line.get("text") for line in one["lines"])
    if one_texts == OLD_ABILITY1_LINES:
        one["lines"][1] = dict(one["lines"][1], text=ABILITY1_SWITCH_LINE, status="changed")
    elif one_texts != NEW_ABILITY1_LINES:
        raise ValueError("panel mirror ability 1 layout drifted")
    three = next(entry for entry in panel["abilities"] if int(entry["index"]) == 3)
    three_texts = tuple(line.get("text") for line in three["lines"])
    if three_texts in (MIRROR_ABILITY3_DRIFTED, PREVIOUS_ABILITY3_LINES):
        three["lines"] = [dict(text=text, status="changed") for text in new_three]
    elif three_texts != new_three:
        raise ValueError("panel mirror ability 3 layout drifted")
    six = next(entry for entry in panel["abilities"] if int(entry["index"]) == 6)
    six_texts = tuple(line.get("text") for line in six["lines"])
    if six_texts == OLD_ABILITY6_LINES:
        six["lines"] = [dict(text=text, status="changed") for text in NEW_ABILITY6_LINES]
    elif six_texts != NEW_ABILITY6_LINES:
        raise ValueError("panel mirror ability 6 layout drifted")
    notes = [note for note in panel.get("notes", []) if not note.startswith("2026-09-27：作者平衡第三轮")]
    panel["notes"] = notes + [MIRROR_NOTE]
    return design, panel


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """保留原文件的缩进、换行风格（本机 CRLF）与末尾有无换行。"""
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    second = raw.split(b"\n", 2)[1]
    indent = len(second) - len(second.lstrip(b" "))
    text = json.dumps(value, ensure_ascii=False, indent=indent or 2)
    if raw.endswith(b"\n"):
        text += "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def sync_mirrors(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回两份设计镜像；返回有变化的相对路径。"""
    root = Path(root)
    rels = (DESIGN_REL, PANEL_REL)
    paths = tuple(root / rel for rel in rels)
    before = [_load(path) for path in paths]
    after = mirror_updates(*before)
    changed = [str(rel) for rel, old, new in zip(rels, before, after) if old != new]
    if write:
        for path, old, new in zip(paths, before, after):
            if old != new:
                _save(path, new)
    return changed


if __name__ == "__main__":
    import sys
    here = Path(__file__).resolve().parent
    pass  # Imports resolve from this checkout/package, not external source copies.
    changed = sync_mirrors(here.parent, write="--write" in sys.argv[1:])
    print(json.dumps({"changed": changed, "write": "--write" in sys.argv[1:]}, ensure_ascii=False))

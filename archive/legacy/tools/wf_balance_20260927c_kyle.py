# -*- coding: utf-8 -*-
"""凯尔 139990 ``kyle_moon``：2026-09-27 平衡调整第三轮（c：成长复核 + 追击段数撤封顶）。

口径 = 主会话施工口径 ``growth_c_spec.md``（作者原话 1–6：成长「砍到 4/5，或者 7/10」「可以砍到 2/3」、
「凯尔的成长降太低了，本身数值就不高」、「数值尽量取 5 的倍数」）＋ 复核表 ``reeval_full.json``
（``table.rows`` 凯尔 7 行、``design.characters`` 凯尔条目、``critique``）。输入 = 当前 live
（链尾 1.4.1053；与第二批 :mod:`wf_balance_20260927b_kyle` 的 revise() 输出逐字相同）。

**A. 队长成长（作者点名，全部取 4/5，按「原值」＝第二批前的值计算）**——第二批 ×1/10（含能力2 搬入部分），
本轮改为 原值 × 4/5，就近取 5 的倍数（原值 ≤10% 的行按 0.5% 取整，口径 D2）：

1. ``leader_ability:139990``（9 行，0 基）原位改强度两列，其余逐字不动：
   #0 月牙每层 → 雷队攻击力 12.5%（批二 1.25%）→ 10%；
   #1 月牙每层 → 自身攻击力 12.5%＋能力2#1 搬入 50%＝62.5%（批二 6.25%）→ 50%；
   #2 月牙每层 → 雷队直击 25%＋能力2#0 搬入 50%＝75%（批二 7.5%）→ 60%；
   #3 月牙每层 → 自身直击 25%（批二 2.5%）→ 20%；
   #6 每获得贯穿 → 雷队攻击力 25%（批二 2.5%）→ 20%；
   #7 每获得贯穿 → 雷队眩晕畏缩特攻（面板原写「追击伤害」，D 节按数据改为特攻写法）5%（批二 0.5%）→ 4%。
   #4/#5 槽上限 / 充能（口径 A6）、#8 特殊强化弹射 722 不动。
2. 能力2 ``1399902`` 的封顶版（限 10 层、雷队直击 10%、自身攻击 16%）保持第二批的值不动（口径 D4），本模块只读
   （C 节共鸣省略核对它仍按「月牙」层数成长），不写。

**B. 追击段数撤封顶（口径 U1）**——629 追击树 ``ability_skill_kyle_moon_pierce``：
``BindConditionAccumulationVariable(-17, 1, DCUnique 13999001, 1, 10)`` 第 5 参 10 → 99（int，
＝第二批前 live 逐字节；＝月牙固有上限 99）。不加旗号：调用方只有 ``1399903#4/#5``，两行都挂前置 42（仅队长）
＋前置2 雷共鸣（:func:`ability3_checks` 只读核对）⇒ 这棵树本来就只在「当队长且雷共鸣」时执行。
作者说过「直击判定次数+N 的角色不改（这个是特色）」。

面板：``desc_override_kyle_moon`` 第 4 行数字（自身 = 全队(雷)行 + 自身行合计）、第 5 行去掉「（最多10层）」、
第 6 行贯穿数字。技能描述 / character_text / 服务端文本不涉及，不改。

**C. 面板同条件合并与共鸣省略**（作者 2026-09-27「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性
共鸣，引擎点火提供的效果就不用写火属性共鸣，其他角色类似」；规则 = 主会话合并规则）：

- 共鸣省略：固有「月牙」13999001 的全部获取来源 = ``1399903#0/#1``（kind 461，都挂前置 kind 2 雷≥6 共鸣；
  live 全部能力/队长表 + 凯尔技能/换形/629/PF DSL 均无其他授予，DSL 只在追击树里 DCUnique 读层数）⇒
  「月牙」提供的效果不写共鸣前缀（D 节后为「雷属性共鸣时，」；数据前置不动）：队长第 4 行（队长#0–#3，dt134 按月牙逐层）、
  队长第 5 行（能力3#4/#5 → 629 追击树按月牙层数绑段数）、能力2 第 1 行（能力2#0/#1，dt134 按月牙逐层，限 10 层）、
  能力3 原第 3 行（D 节拆行后为第 4 行；能力3#3 前置1 187 持有月牙）。「月牙」获取行（能力3 原第 1 行，D 节拆成第 1、2 行）、
  贯穿 / 冲刺 / 充能各行照写。
  依据由 :func:`crescent_resonance_basis` 在 revise() 里逐行核对（fail closed）。
- 同条件合并：凯尔各覆盖面板里数据同条件的组（队长#0–#3、#4/#5、#6/#7，能力2#0/#1，能力4#0/#1）
  本来就各写在同一行；能力5#1–#3 冲刺参数在能力5 面板不出现（队长第 2 行描述）⇒ 没有要合并的行。
  能力1#1/#2 同条件，但 #2 是技能开关行，其强化条目按 E 节单独成行（与 CAS 同文）。
  能力4/5 面板没有「月牙」效果行、也无可并组 ⇒ 不返回；能力6 因 D 节「迟缓」→「冻结」与 E 节删行返回（无省略、无合并）；
  能力1 因 E 节返回。

**D. 本轮面板统一口径**（主会话 2026-09-27 定稿，只作用于本模块返回的五块覆盖面板；在 C 节省略前先做，
结果 = 合并校验 ``wf_panel_merge_check.check`` 的原文）：

- 口径 3：「雷属性共鸣时：」一律写「雷属性共鸣时，」（:func:`normalize_resonance`；凯尔没有「共鸣时：」后换行接效果的行）。
- 口径 4（面板与数据不符 ⇒ 按数据改文字，数据不动；:data:`PANEL_CORRECTIONS`，依据由 :func:`panel_correction_basis`
  / :func:`frozen_slayer_basis` 在 revise() 里逐行核对，fail closed）：
  队长第 2 行「强化自身冲刺」描述的冲刺参数行 ``1399905#1–#4``（kind 422）只挂前置 42（仅队长）、没有雷共鸣 ⇒
  去掉「雷属性共鸣时，」；队长第 6 行「追击伤害＋4%」的数据是 ``leader_ability:139990#7`` kind 53 眩晕畏缩特攻 ⇒
  改写成特攻写法，措辞沿用凯尔能力6 覆盖文案的特攻句式（「对处于“冻结”状态的敌人造成伤害，额外乘区＋15%」）。
- 「迟缓」→「冻结」（主会话追加 C，2026-09-27）：能力6 第 2 行的数据是 ``ability:1399906#0`` kind 119
  FrozenSlayer（冻结特攻 15%），状态本体来自两档技能 DSL 强化档的 ``ACFrozen``（无 ``ACSlow``）⇒ 面板写「冻结」。
  能力6 因此本轮返回，同时按口径 3 冒号改逗号（原第 1 行技能强化行由 E 节删除）。
- 口径 5（主会话扩展 B，2026-09-27）：能力3 第 1 行用「；」挤了两种数据条件——``1399903#0``（触发 23 雷属性角色
  发动技能）与 ``#1``（触发 20 雷属性角色每 100 次直击），前置、内容相同、触发不同 ⇒ 按数据条件拆两行
  （:data:`PANEL_SPLITS`，依据 :func:`panel_split_basis`，fail closed）；两行都是「月牙」获取行 ⇒ 各自照写共鸣前缀。
  返回面板的规则扫描（:func:`panel_rule_problems`）同时拦全角「／」与半角「/」。

**E. 技能强化条目**（主会话 2026-09-27 口径 R1–R3；作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写
就行,技能里面不要重复描述强化后的效果,规范并简化描述」）：

- 凯尔唯一的技能开关 = ``ability:1399901#2``（kind 536 → 旗号 1，前置 kind 2 雷≥6 共鸣，c70 = ``change_skill_kyle_moon``）；
  旗号 1 开支 = 两档技能树的 ``FindAllSubjects(33)`` 追加 ACPiercing / ACDirectDamage / ACSpeedup、``FindNearSubjects``
  最近敌人 DeleteCondition（强化效果）+ ACFrozen，以及 629 天雷树（能力3#6 调起）的强化档。
- 强化条目 ``change_skill_kyle_moon``「进一步强化技能「月华·狼牙连斩」的效果」未用『』点名、也没说强化了什么 ⇒ 改官方格式
  「强化『月华·狼牙连斩』：<定性说明>」（不写数字 / 秒数，:data:`SWITCH_TEXTS`）。
- 能力1 覆盖面板第 2 行把 #1（211 自身技能槽 50%）与 #2（强化开关）挤在一句 ⇒ 拆成数值行 + 强化条目行，两行数据都带雷共鸣
  前置 ⇒ 各自写「雷属性共鸣时，」（口径 3 冒号改逗号）；强化条目行 = 共鸣前缀 + CAS 同文（:data:`PANEL_ENHANCEMENTS`）。
- 能力6 覆盖面板第 1 行「雷属性共鸣时，进一步强化技能…」：能力6 只有 #0（kind 119 冻结特攻），没有任何 536/704–708 行，
  强化条目已在能力1 面板 ⇒ 重复且挂错面板，删除（能力6 面板只剩冻结特攻一行）。
- 技能描述（action_skill / character_text / 服务端）只写技能本体、不含强化后描述 ⇒ 不改。
- 依据由 :func:`switch_basis` 在 revise() 里核对（开关行位置 / 前置 / 文案键、其余能力键与队长表无开关行、技能名），
  开支内容由 :func:`switch_tree_problems` 核对（输入不含技能树 ⇒ 在测试里对第二批输出与 live store 的树跑）。

生成器 ``wf_midautumn_kit_kyle``（CRESCENT_* / PIERCING_GROWTH / EXPECT / PANEL_LEADER / PANEL_ABILITY[1][2][3][6] /
CAS_TEXTS[change_skill_kyle_moon] / PIERCE_VAR_CEIL）已同步，测试断言生成器输出 == :func:`revise` 输出。设计镜像（design/kyle.json、rework1/panel/kyle.json）由
:func:`sync_mirrors` 幂等同步（本模块不写；主会话 ``python mod-tools/wf_balance_20260927c_kyle.py --write``）。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Callable

CID = "139990"
CODE = "kyle_moon"
PACKAGES = ["ma-kyle"]
#: 候选 manifest 现值 1.0.3（第二批写入）⇒ 下一号。
PACKAGE_VERSION = {"ma-kyle": "1.0.4"}
#: 候选已声明 damage-type-rules-v1 / dash-parameter-v1 / panel-description-override-v2；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 ma-kyle 1.0.3 与 live 在本模块读取的 4 项上逐字相同（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 2                              # master/character c3：雷（0 基内部元素）
ELEMENT_TOKEN = "Yellow"
UID_CRESCENT = "13999001"                # 固有「月牙」（unique_condition 上限 99 不动）
CRESCENT_UNIQUE_CAP = 99
LEADER_NCOLS, ABILITY_NCOLS = 124, 126

LEADER_KEY = CID
ABILITY1 = f"{CID}1"                     # 只读：E 节依据（#2 kind 536 技能开关行，#1 同条件的自身技能槽行）
ABILITY2 = f"{CID}2"                     # 只读：能力2 两行仍按「月牙」层数成长（C 节共鸣省略依据）
ABILITY3 = f"{CID}3"                     # 只读：核对追击 629 的调用方仍是「仅队长 + 雷共鸣」、月牙来源仍带雷共鸣
ABILITY4 = f"{CID}4"                     # 只读：E 节依据（无技能开关行）
ABILITY5 = f"{CID}5"                     # 只读：D 节口径 4 依据（冲刺参数行只挂前置 42，无雷共鸣）
ABILITY6 = f"{CID}6"                     # 只读：D 节「迟缓」→「冻结」依据（#0 kind 119 FrozenSlayer）
CAS_LEADER = f"desc_override_{CODE}"
CAS_ABILITY1 = f"desc_override_{CODE}_1"
CAS_ABILITY2 = f"desc_override_{CODE}_2"
CAS_ABILITY3 = f"desc_override_{CODE}_3"
CAS_ABILITY6 = f"desc_override_{CODE}_6"
CAS_SWITCH = f"change_skill_{CODE}"      # E 节：能力1#2 kind 536 的 c70 技能强化条目
CAS_PIERCE = f"ability_skill_{CODE}_pierce"
CAS_THUNDER = f"ability_skill_{CODE}_thunder"
PIERCE_PROGRAM = f"battle/action/skill/action/ability_skill/{CAS_PIERCE}${CAS_PIERCE}"

#: live 输入基线（2026-09-27 本地链尾 1.4.1054，stage_batch.make_read(live_only=True) 只读取数；
#: 与第二批 revise() 输出、候选 ma-kyle 1.0.3 逐字相同；1.4.1054 灰服三角色替换不涉及凯尔）。
#: 任一不符 ⇒ revise() 拒绝（fail closed）。能力2 与两块能力面板是 C 节（面板合并 / 共鸣省略）加入的；
#: 能力5 是 D 节（口径 4 按数据改文字）加入的只读依据，同样取自链尾 1.4.1054；能力6 行（只读依据）与能力6 面板
#: 是本轮暂存前最后一轮（「迟缓」→「冻结」）加入的，同样取自链尾 1.4.1054；能力1/4 行、action_skill、强化条目与能力1 面板
#: 是 E 节（技能强化条目口径，主会话 2026-09-27）加入的，同样取自链尾 1.4.1054（make_read(live_only=True)）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", LEADER_KEY): "fc61eda533543c64413ebc2726dbe4921d70dc4ec046337e3ad89b86f0fec068",
    ("ability", ABILITY1): "c8aaec4ab895ab626cd3707426f4608dc88d3935e0dcf158d877d57d107b290e",
    ("ability", ABILITY4): "19603d698ac0c07eada04488b2c6d87c3fdaab21a33dfddb928a28106e9b3b1d",
    ("action", CODE): "cbf6eb29196475c6b7ac0dc0228345ea83f36beecbc5655ec598de744491812c",
    ("cas", CAS_ABILITY1): "53d062c0ab03dc6d43b033d7a051d994bb51d01b284ad197e431d6fcfd5ab315",
    ("cas", CAS_SWITCH): "0748903060642e3e00c9d71095bf966473a5c3c74157a133e490d2691f53d03c",
    ("ability", ABILITY2): "88dbbaf86856500b44db451592e6e218e1d00b110c8bd4d2f3b96ff69c87d79e",
    ("ability", ABILITY3): "fd274f08504d07afa19e18b9db541f2687659066e04e98fd3c5c22fd38ac85b0",
    ("ability", ABILITY5): "bbed4e86561f348f8ad1fb7798a9c75add1b9da41d3c1fe3322e3cf9ca805f50",
    ("ability", ABILITY6): "fd352f50b7faa14886a4d029ccac0b1e806ae18608f394b60c614877fa60e4c4",
    ("cas", CAS_LEADER): "2a5cb1bae3785b87c15b9c52c5f63d83138e4933c6cbe60a830912532e0a7c1e",
    ("cas", CAS_ABILITY2): "58628e744f1af64d29823ae16dcacb052094044eb67f08a93cbaa48777aaf6e6",
    ("cas", CAS_ABILITY3): "4d88c3f7c9b7fe31552b4fbec5f87724e62f425222bd5f5fd1e27d8726a4bc94",
    ("cas", CAS_ABILITY6): "db014d84ddca4e4f884aa95db94db5847456a50746e2547a8646421a79c93ea9",
    ("dsl", PIERCE_PROGRAM): "cde043ea6f98660e973f0f8f29482ea9d8174a7eee1b330746a2df7513de1e9d",
}

# ---------------------------------------------------------------- A. 队长成长 4/5

#: 档位系数（作者原话 4「砍到4/5」；凯尔被作者点名「成长降太低了，本身数值就不高」⇒ 最轻档）。
FACTOR = Fraction(4, 5)
#: 取整规则（复核表 summary）：原值 ≥10% ⇒ 就近取 5% 的倍数；原值 ≤10% ⇒ 按 0.5% 取整（口径 D2）；
#: 2/3 档向上取（凯尔不用）。100000 = 100%。
STEP_WIDE, STEP_NARROW, NARROW_BELOW = 5000, 500, 10000

_CRESCENT = {3: "1", 95: "134", 96: "0", 98: "100000", 99: "100000", 100: "(None)",
             102: UID_CRESCENT, 106: "false"}
_PIERCING = {3: "0", 25: "51", 28: "100000", 29: "100000", 32: "(None)", 33: "0", 37: "(None)",
             44: "0", 46: "5", 47: ELEMENT_TOKEN}
_LEADER_RESONANCE = {0: CODE, 1: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
                     11: "0", 18: "0"}

#: 记录号 → (识别格, 强度两列, 第二批值(live), 原值分量（第二批前；合并行 = 队长原值 + 能力2 搬入原值）,
#: 新值, 说明)。互锁：第二批值 == Σ原值/10；新值 == 取整(Σ原值 × 4/5)。
LEADER_EDITS: dict[int, tuple[dict[int, str], tuple[int, int], str, tuple[str, ...], str, str]] = {
    0: ({**_CRESCENT, 107: "0", 108: "5", 109: ELEMENT_TOKEN}, (111, 112), "1250", ("12500",), "10000",
        "月牙每层 → 雷队攻击力：原 12.5% / 批二 1.25% → 10%"),
    1: ({**_CRESCENT, 107: "0", 108: "0", 109: ""}, (111, 112), "6250", ("12500", "50000"), "50000",
        "月牙每层 → 自身攻击力（含能力2#1 搬入）：原 12.5%＋50% / 批二 6.25% → 50%"),
    2: ({**_CRESCENT, 107: "1", 108: "5", 109: ELEMENT_TOKEN}, (111, 112), "7500", ("25000", "50000"), "60000",
        "月牙每层 → 雷队直击（含能力2#0 搬入）：原 25%＋50% / 批二 7.5% → 60%"),
    3: ({**_CRESCENT, 107: "1", 108: "0", 109: ""}, (111, 112), "2500", ("25000",), "20000",
        "月牙每层 → 自身直击：原 25% / 批二 2.5% → 20%"),
    6: ({**_PIERCING, 45: "32"}, (49, 50), "2500", ("25000",), "20000",
        "每获得贯穿 → 雷队攻击力：原 25% / 批二 2.5% → 20%"),
    7: ({**_PIERCING, 45: "53"}, (49, 50), "500", ("5000",), "4000",
        "每获得贯穿 → 雷队眩晕畏缩特攻（面板原写「追击伤害」，本轮按数据改为特攻写法）：原 5% / 批二 0.5% → 4%"
        "（原值 ≤10%，按 0.5% 取整）"),
}
#: 不动的队长行：#4 技能槽上限 20%（245）、#5 充能 20%（35）、#8 特殊强化弹射 722。
LEADER_KEPT = {4: "245", 5: "35", 8: "722"}
LEADER_ROWS = 9
BATCH2_SLOW = 10                         # 第二批 ×1/10（互锁用）

# ---------------------------------------------------------------- 面板

#: live（第二批）队长面板。
OLD_LEADER_TEXT = "\n".join((
    "赋予自身特殊强化弹射",
    "雷属性共鸣时：强化自身冲刺",
    "自身冲刺间隔无法进一步缩短",
    "雷属性共鸣时：自身“月牙”每上升1层，自身攻击力＋7.5%、直击伤害＋10%；"
    "除自身外雷属性角色攻击力＋1.25%、直击伤害＋7.5%",
    "雷属性共鸣时：自身“月牙”每上升1层，自身直击判定次数＋1（最多10层）",
    "雷属性共鸣时：自身每获得一次贯穿效果，雷属性角色攻击力＋2.5%、追击伤害＋0.5%",
    "雷属性共鸣时：雷属性角色技能槽最大值＋20%、技能充能速度＋20%",
))
#: A/B 节数值改后的队长面板（D 节口径 3/4 之前；只用于核对取数链）。
#: 自身 = 全队(雷)行 + 自身行：攻击 10 + 50 = 60%、直击 60 + 20 = 80%；除自身外 = 全队(雷)行。
#: 段数行按设计稿去掉「（最多10层）」，写到效果为止（不写「无上限」之类禁语）。
NUMERIC_LEADER_TEXT = "\n".join((
    "赋予自身特殊强化弹射",
    "雷属性共鸣时：强化自身冲刺",
    "自身冲刺间隔无法进一步缩短",
    "雷属性共鸣时：自身“月牙”每上升1层，自身攻击力＋60%、直击伤害＋80%；"
    "除自身外雷属性角色攻击力＋10%、直击伤害＋60%",
    "雷属性共鸣时：自身“月牙”每上升1层，自身直击判定次数＋1",
    "雷属性共鸣时：自身每获得一次贯穿效果，雷属性角色攻击力＋20%、追击伤害＋4%",
    "雷属性共鸣时：雷属性角色技能槽最大值＋20%、技能充能速度＋20%",
))
#: D 节后、C 节省略前的队长面板（= 合并校验 ``wf_panel_merge_check.check`` 的原文）：
#: 口径 3 冒号改逗号；口径 4 第 2 行去掉无数据依据的共鸣前缀、第 6 行「追击伤害」按数据改为眩晕畏缩特攻写法。
PREEDIT_LEADER_TEXT = "\n".join((
    "赋予自身特殊强化弹射",
    "强化自身冲刺",
    "自身冲刺间隔无法进一步缩短",
    "雷属性共鸣时，自身“月牙”每上升1层，自身攻击力＋60%、直击伤害＋80%；"
    "除自身外雷属性角色攻击力＋10%、直击伤害＋60%",
    "雷属性共鸣时，自身“月牙”每上升1层，自身直击判定次数＋1",
    "雷属性共鸣时，自身每获得一次贯穿效果，雷属性角色攻击力＋20%，"
    "对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋4%",
    "雷属性共鸣时，雷属性角色技能槽最大值＋20%、技能充能速度＋20%",
))
#: 本轮最终队长面板：第 4、5 行是「月牙」提供的效果 ⇒ 省略「雷属性共鸣时，」（C 节）；其余行与 PREEDIT 逐字相同。
NEW_LEADER_TEXT = "\n".join((
    "赋予自身特殊强化弹射",
    "强化自身冲刺",
    "自身冲刺间隔无法进一步缩短",
    "自身“月牙”每上升1层，自身攻击力＋60%、直击伤害＋80%；除自身外雷属性角色攻击力＋10%、直击伤害＋60%",
    "自身“月牙”每上升1层，自身直击判定次数＋1",
    "雷属性共鸣时，自身每获得一次贯穿效果，雷属性角色攻击力＋20%，"
    "对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋4%",
    "雷属性共鸣时，雷属性角色技能槽最大值＋20%、技能充能速度＋20%",
))
#: live → 最终有变化的队长面板行（0 基）：第 1 行不动。
CHANGED_PANEL_LINES = (1, 3, 4, 5, 6)

#: 主位限制槽（能力2/3 整键 c1="false"）每行自带的图标（与 wf_midautumn_kit_kyle.MAIN_ICON 同值）。
MAIN_ICON = " <icon id='main'>  "
#: 口径 3 之后的共鸣前缀（C 节省略删的就是它）。
RESONANCE_PREFIX = "雷属性共鸣时，"

#: live 能力2 / 能力3 面板（本轮数值不动，只做 D 节口径 3 与 C 节共鸣省略）。
OLD_ABILITY2_TEXT = MAIN_ICON + "雷属性共鸣时：自身“月牙”每提升1层，自身攻击力＋16%、雷属性角色直击伤害＋10%（最多10层）"
PREEDIT_ABILITY2_TEXT = MAIN_ICON + "雷属性共鸣时，自身“月牙”每提升1层，自身攻击力＋16%、雷属性角色直击伤害＋10%（最多10层）"
NEW_ABILITY2_TEXT = MAIN_ICON + "自身“月牙”每提升1层，自身攻击力＋16%、雷属性角色直击伤害＋10%（最多10层）"
OLD_ABILITY3_TEXT = "\n".join((
    MAIN_ICON + "雷属性共鸣时：雷属性角色发动技能时，自身“月牙”＋1层；雷属性角色每造成100次直击，自身“月牙”＋1层",
    MAIN_ICON + "雷属性共鸣时：自身每获得一次贯穿效果，2秒后自身技能槽＋10%（冷却时间：10秒）",
    MAIN_ICON + "雷属性共鸣时：自身持有“月牙”时，强化雷属性角色的直接攻击为3次，合计伤害额外乘区＋300%",
))
#: 口径 3 之后、口径 5 拆行之前的能力3 第 1 行（「；」前后是两种数据条件）。
ABILITY3_JOINED_LINE = (MAIN_ICON + "雷属性共鸣时，雷属性角色发动技能时，自身“月牙”＋1层；"
                        "雷属性角色每造成100次直击，自身“月牙”＋1层")
#: 口径 5 拆出的两行（两行都是「月牙」获取行 ⇒ 各自照写共鸣前缀）。
ABILITY3_SPLIT_LINES = (
    MAIN_ICON + "雷属性共鸣时，雷属性角色发动技能时，自身“月牙”＋1层",
    MAIN_ICON + "雷属性共鸣时，雷属性角色每造成100次直击，自身“月牙”＋1层",
)
#: D 节后（口径 3 冒号改逗号 + 口径 5 第 1 行拆两行）= 合并校验原文。
PREEDIT_ABILITY3_TEXT = "\n".join((
    *ABILITY3_SPLIT_LINES,
    MAIN_ICON + "雷属性共鸣时，自身每获得一次贯穿效果，2秒后自身技能槽＋10%（冷却时间：10秒）",
    MAIN_ICON + "雷属性共鸣时，自身持有“月牙”时，强化雷属性角色的直接攻击为3次，合计伤害额外乘区＋300%",
))
NEW_ABILITY3_TEXT = "\n".join((
    *ABILITY3_SPLIT_LINES,
    MAIN_ICON + "雷属性共鸣时，自身每获得一次贯穿效果，2秒后自身技能槽＋10%（冷却时间：10秒）",
    MAIN_ICON + "自身持有“月牙”时，强化雷属性角色的直接攻击为3次，合计伤害额外乘区＋300%",
))
#: live 能力6 面板（非主位槽，不带图标）。第 1 行是技能强化行（能力6 没有开关行 ⇒ E 节删除），第 2 行 = 1399906#0 冻结特攻。
OLD_ABILITY6_TEXT = "\n".join((
    "雷属性共鸣时：进一步强化技能「月华·狼牙连斩」的效果",
    "雷属性共鸣时：雷属性角色对处于“迟缓”状态的敌人造成伤害，额外乘区＋15%",
))
#: D 节后（口径 3 冒号改逗号 + 「迟缓」按数据改「冻结」）+ E 节删掉挂错面板的强化行 = 合并校验原文 = 本轮最终文案
#: （无省略、无合并）。
PREEDIT_ABILITY6_TEXT = "雷属性共鸣时，雷属性角色对处于“冻结”状态的敌人造成伤害，额外乘区＋15%"
NEW_ABILITY6_TEXT = PREEDIT_ABILITY6_TEXT

# ---------------------------------------------------------------- E. 技能强化条目

#: 凯尔唯一的技能开关行：能力1#2 kind 536（InstantAbilitySource：536 → 旗号 1）。
SWITCH_ROW = 2
SWITCH_KIND = "536"
#: 能切技能旗号的全部 kind（536 = 旗号 1，704–708 = 旗号 2–6）；能力表瞬发 c47 / 持续 c109，队长表 c45 / c107。
FLAG_KINDS = ("536", "704", "705", "706", "707", "708")
#: 强化条目点名的技能（action_skill kyle_moon 第 1 档 c0，revise() 核对）。
SKILL_NAME = "月华·狼牙连斩"
#: 技能强化条目（口径 R2 官方格式、定性、不写数字与秒数）：旗号 1 开支 = 两档技能树追加队伍贯穿 / 直接攻击伤害提升 / 加速，
#: 最近敌人消除强化效果 + 冻结；629 天雷树（能力3#6 调起）的强化档（:func:`switch_tree_problems`）。
OLD_SWITCH_TEXT = "进一步强化技能「月华·狼牙连斩」的效果"
NEW_SWITCH_TEXT = (f"强化『{SKILL_NAME}』：追加赋予队伍贯穿、直接攻击伤害提升与加速效果，"
                   "消除距离最近的敌人的部分强化效果并赋予其冻结效果，同时强化自身直击召唤的天雷")
SWITCH_TEXTS: dict[str, tuple[str, str]] = {CAS_SWITCH: (OLD_SWITCH_TEXT, NEW_SWITCH_TEXT)}

#: live 能力1 面板（主位限制槽，每行带图标）：第 1 行 = #0（无前置），第 2 行 = #1（211 自身技能槽）+ #2（强化开关）挤在一句。
OLD_ABILITY1_TEXT = "\n".join((
    MAIN_ICON + "战斗开始时：雷属性角色技能槽＋50%",
    MAIN_ICON + "雷属性共鸣时：自身技能槽＋50%，并进一步强化技能「月华·狼牙连斩」的效果",
))
#: E 节：第 2 行拆成数值行 + 强化条目行（两行数据都带雷≥6 共鸣前置 ⇒ 各自写「雷属性共鸣时，」；强化条目 = CAS 同文）。
ABILITY1_SWITCH_LINE = MAIN_ICON + RESONANCE_PREFIX + NEW_SWITCH_TEXT
PREEDIT_ABILITY1_TEXT = "\n".join((
    MAIN_ICON + "战斗开始时：雷属性角色技能槽＋50%",
    MAIN_ICON + "雷属性共鸣时，自身技能槽＋50%",
    ABILITY1_SWITCH_LINE,
))
NEW_ABILITY1_TEXT = PREEDIT_ABILITY1_TEXT

#: E 节：面板键 → {0 基行号（D 节之后）: (原行, 改后各行（空 = 删行）, 依据)}。按原行位置依次展开。
PANEL_ENHANCEMENTS: dict[str, dict[int, tuple[str, tuple[str, ...], str]]] = {
    CAS_ABILITY1: {
        1: (MAIN_ICON + "雷属性共鸣时，自身技能槽＋50%，并进一步强化技能「月华·狼牙连斩」的效果",
            (MAIN_ICON + "雷属性共鸣时，自身技能槽＋50%", ABILITY1_SWITCH_LINE),
            "ability:1399901#1（211 自身技能槽 50%）与 #2（536 旗号 1 开关，c70 change_skill_kyle_moon）挤在一句；"
            "强化条目单独成行、按官方格式点名技能并写出强化内容（与 CAS 同文）；两行都带前置 kind 2 雷≥6 共鸣 ⇒ 各自写"
            "「雷属性共鸣时，」"),
    },
    CAS_ABILITY6: {
        0: ("雷属性共鸣时，进一步强化技能「月华·狼牙连斩」的效果", (),
            "ability:1399906 只有 #0（kind 119 冻结特攻），没有 536/704–708 开关行；凯尔唯一的技能开关 1399901#2 的强化条目"
            "已在能力1 面板 ⇒ 重复且挂错面板，删除"),
    },
}

#: D 节口径 4：面板键 → {0 基行号: (口径 3 之后的原行, 按数据改后的行, 数据依据)}。数据不动。
DASH_KIND = "422"                        # ability c109 冲刺参数（可调）
STUN_WINCE_KIND = "53"                   # leader c45 眩晕畏缩特攻（StunWinceSlayer）
STUN_WINCE_ROW = 7
FROZEN_SLAYER_KIND = "119"               # ability c47 冻结特攻（FrozenSlayer，ability_enum_map）
PANEL_CORRECTIONS: dict[str, dict[int, tuple[str, str, str]]] = {
    CAS_LEADER: {
        1: ("雷属性共鸣时，强化自身冲刺", "强化自身冲刺",
            "ability:1399905#1–#4 冲刺参数（kind 422）只挂前置 42（仅队长），没有雷共鸣前置 ⇒ 去掉共鸣前缀"),
        5: ("雷属性共鸣时，自身每获得一次贯穿效果，雷属性角色攻击力＋20%、追击伤害＋4%",
            "雷属性共鸣时，自身每获得一次贯穿效果，雷属性角色攻击力＋20%，"
            "对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋4%",
            "leader_ability:139990#7 是 kind 53 眩晕畏缩特攻 4%，不是追击伤害 ⇒ 按数据改写；"
            "措辞沿用凯尔能力6 覆盖文案的特攻句式「对处于“冻结”状态的敌人造成伤害，额外乘区＋15%」"),
    },
    CAS_ABILITY6: {
        1: ("雷属性共鸣时，雷属性角色对处于“迟缓”状态的敌人造成伤害，额外乘区＋15%",
            "雷属性共鸣时，雷属性角色对处于“冻结”状态的敌人造成伤害，额外乘区＋15%",
            "ability:1399906#0 是 kind 119 FrozenSlayer（冻结特攻 15%）；状态本体 = 两档技能 DSL 强化档的 ACFrozen"
            "（无 ACSlow）⇒ 「迟缓」按数据改「冻结」（主会话追加 C）"),
    },
}

#: 口径 5（主会话扩展 B）：面板键 → {0 基行号（口径 3/4 之后）: (原行, 拆后各行, 数据依据)}。拆后各行按原行位置依次展开。
PANEL_SPLITS: dict[str, dict[int, tuple[str, tuple[str, ...], str]]] = {
    CAS_ABILITY3: {
        0: (ABILITY3_JOINED_LINE, ABILITY3_SPLIT_LINES,
            "ability:1399903#0（触发 23 雷属性角色发动技能）与 #1（触发 20 雷属性角色每 100 次直击）前置相同"
            "（雷≥6 共鸣）、内容相同（461 → 月牙），触发不同 ⇒ 两种数据条件，拆两行；两行都是「月牙」获取行，各自照写共鸣前缀"),
    },
}

#: C 节共鸣省略：面板键 → {0 基行号（D 节后）: 该行描述的数据行（都按「月牙」生效）}。原文（省略前）见 PANEL_TEXTS。
RESONANCE_DROPS: dict[str, dict[int, str]] = {
    CAS_LEADER: {3: "leader_ability:139990#0–#3（dt134 月牙逐层）",
                 4: "ability:1399903#4/#5 → 629 追击树（BindConditionAccumulationVariable 读月牙层数绑段数）"},
    CAS_ABILITY2: {0: "ability:1399902#0/#1（dt134 月牙逐层，限 10 层）"},
    CAS_ABILITY3: {3: "ability:1399903#3（前置1 187 持有月牙）"},
}
#: 面板键 → (live 原文, 本轮数值改后, D 节后 = 合并校验原文, 本轮最终文案)。
PANEL_TEXTS: dict[str, tuple[str, str, str, str]] = {
    CAS_LEADER: (OLD_LEADER_TEXT, NUMERIC_LEADER_TEXT, PREEDIT_LEADER_TEXT, NEW_LEADER_TEXT),
    CAS_ABILITY1: (OLD_ABILITY1_TEXT, OLD_ABILITY1_TEXT, PREEDIT_ABILITY1_TEXT, NEW_ABILITY1_TEXT),
    CAS_ABILITY2: (OLD_ABILITY2_TEXT, OLD_ABILITY2_TEXT, PREEDIT_ABILITY2_TEXT, NEW_ABILITY2_TEXT),
    CAS_ABILITY3: (OLD_ABILITY3_TEXT, OLD_ABILITY3_TEXT, PREEDIT_ABILITY3_TEXT, NEW_ABILITY3_TEXT),
    CAS_ABILITY6: (OLD_ABILITY6_TEXT, OLD_ABILITY6_TEXT, PREEDIT_ABILITY6_TEXT, NEW_ABILITY6_TEXT),
}
#: 同条件合并组：凯尔没有（数据同条件的组都已各在一行，见模块说明 C 节）。
PANEL_MERGES: dict[str, dict[int, tuple[int, ...]]] = {}
#: 已逐一核对、本轮不返回的覆盖面板（无「月牙」效果行、无可并组、无按数据要改的字、无技能强化条目）。口径 3 只作用于本轮
#: 返回的面板，这两块仍是 live 的「雷属性共鸣时：」冒号写法（未改、未返回）。能力1 面板因 E 节返回。
PANELS_REVIEWED_UNCHANGED = {
    f"desc_override_{CODE}_4": "能力4#0/#1 同条件已在同一行",
    f"desc_override_{CODE}_5": "只描述能力5#0；#1–#5（队长时冲刺参数、冲刺获得贯穿）不在本面板，#1–#3 同条件但是机制行",
}

#: 口径 3：「X属性共鸣时：」（全角或半角冒号）→「X属性共鸣时，」。
_RESONANCE_COLON = re.compile(r"([火水雷风光暗](?:或[火水雷风光暗])*属性共鸣时)[：:]")
_RESONANCE_COLON_AT_END = re.compile(r"属性共鸣时[：:]\s*$")


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


def correct_panel(key: str, text: str) -> str:
    """口径 4：按 :data:`PANEL_CORRECTIONS` 逐行替换（原行必须逐字相符，fail closed）。"""
    lines = text.split("\n")
    for index, (before, after, _why) in PANEL_CORRECTIONS.get(key, {}).items():
        _require(lines[index] == before, f"{key} L{index + 1}: unexpected pre-correction text {lines[index]!r}")
        lines[index] = after
    return "\n".join(lines)


def split_panel(key: str, text: str) -> str:
    """口径 5：按 :data:`PANEL_SPLITS` 把一行按数据条件拆成多行（原行必须逐字相符，fail closed）；其余逐字不动。"""
    lines = text.split("\n")
    for index, (before, after, _why) in sorted(PANEL_SPLITS.get(key, {}).items(), reverse=True):
        _require(index < len(lines) and lines[index] == before,
                 f"{key} L{index + 1}: unexpected pre-split text {lines[index] if index < len(lines) else None!r}")
        _require(len(after) >= 2 and all(line for line in after), f"{key} L{index + 1}: a split needs ≥2 lines")
        lines[index:index + 1] = list(after)
    return "\n".join(lines)


def enhance_panel(key: str, text: str) -> str:
    """E 节：按 :data:`PANEL_ENHANCEMENTS` 把技能强化行改成官方格式条目（拆行）或删掉挂错面板的强化行（原行必须逐字相符，
    fail closed）；其余逐字不动。"""
    lines = text.split("\n")
    for index, (before, after, _why) in sorted(PANEL_ENHANCEMENTS.get(key, {}).items(), reverse=True):
        _require(index < len(lines) and lines[index] == before,
                 f"{key} L{index + 1}: unexpected pre-enhancement text {lines[index] if index < len(lines) else None!r}")
        lines[index:index + 1] = list(after)
    _require(bool(lines), f"{key}: enhancement edits left an empty panel")
    return "\n".join(lines)


def normalized_panel(key: str, numeric: str) -> str:
    """D 节：口径 3（冒号改逗号）→ 口径 4 /「迟缓」→「冻结」（按数据改文字）→ 口径 5（按数据条件拆行）
    → E 节（技能强化条目）。"""
    return enhance_panel(key, split_panel(key, correct_panel(key, normalize_resonance(numeric))))


#: 返回面板不许出现的分隔 / 写法：共鸣冒号（口径 3）、全角「／」与半角「/」（口径 5，主会话扩展 B 起覆盖半角）。
FORBIDDEN_PANEL_MARKS = ("／", "/")


def panel_rule_problems(key: str, text: str) -> list[str]:
    """本轮返回面板的规则扫描：没有「X属性共鸣时：」、没有「／」或「/」、没有「迟缓」（凯尔的冻结写「冻结」）。"""
    problems = [f"{key}: resonance must read 「X属性共鸣时，」"] if _RESONANCE_COLON.search(text) else []
    problems += [f"{key}: slash {mark!r} splits items or levels inside a line" for mark in FORBIDDEN_PANEL_MARKS
                 if mark in text]
    problems += [f"{key}: 「迟缓」 — the data is ACFrozen / FrozenSlayer, write 「冻结」"] if "迟缓" in text else []
    return problems


def drop_resonance(text: str, lines) -> str:
    """把 ``lines``（0 基）各行行首（主位图标之后）的「雷属性共鸣时，」删掉；其余逐字不动。"""
    out = text.split("\n")
    for index in lines:
        line = out[index]
        icon = MAIN_ICON if line.startswith(MAIN_ICON) else ""
        body = line[len(icon):]
        _require(body.startswith(RESONANCE_PREFIX), f"panel line {index} does not start with {RESONANCE_PREFIX}")
        out[index] = icon + body[len(RESONANCE_PREFIX):]
    return "\n".join(out)

# ---------------------------------------------------------------- B. DSL

#: 第 5 参 = 变量上限（客户端 ActionEvaluator case 101：``bind(vid, min(层数 / 第4参, 第5参))``）。
PIERCE_CEIL_SLOT, PIERCE_CEIL_BEFORE, PIERCE_CEIL_AFTER = 5, 10, 99
PIERCE_BIND_BEFORE = ["BindConditionAccumulationVariable", -17, 1, ["DCUnique", int(UID_CRESCENT)], 1,
                      PIERCE_CEIL_BEFORE]
PIERCE_TIMES = [{"min": 1, "max": 1, "vlv": [{"vid": 1, "min": 0, "max": 1}]}]


class KyleBalanceCError(ValueError):
    pass


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise KyleBalanceCError(f"unreviewed live baseline for {kind}:{key} "
                                f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise KyleBalanceCError(message)


def _cells_match(row: list[str], cells: dict[int, str], label: str) -> None:
    got = {col: row[col] for col in cells}
    _require(got == cells, f"{label}: unexpected preimage {got} != {cells}")


def rescale(original: int, factor: Fraction = FACTOR, *, up: bool = False) -> int:
    """原值 × 档位系数，按取整规则落到 5%（原值 ≥10%）或 0.5%（原值 ≤10%）的倍数；``up`` = 2/3 档向上取。"""
    step = STEP_WIDE if original >= NARROW_BELOW else STEP_NARROW
    quotient = Fraction(original) * factor / step
    count = math.ceil(quotient) if up else math.floor(quotient + Fraction(1, 2))
    return count * step


def leader_rows(leader: list[list[str]]) -> list[list[str]]:
    """队长 #0/#1/#2/#3/#6/#7 强度两列改为 原值×4/5；#4/#5/#8 与其余格逐字不动。"""
    out = deepcopy(leader)
    _require(len(out) == LEADER_ROWS and all(len(r) == LEADER_NCOLS for r in out),
             f"leader_ability:{LEADER_KEY} shape drift ({len(out)} rows)")
    for index, kind in LEADER_KEPT.items():
        _require(out[index][45] == kind or out[index][107] == kind,
                 f"leader#{index}: kept row is not kind {kind}")
    for index, (cells, cols, batch2, originals, new, _why) in LEADER_EDITS.items():
        row = out[index]
        _cells_match(row, {**_LEADER_RESONANCE, **cells}, f"leader#{index}")
        _require([row[c] for c in cols] == [batch2, batch2],
                 f"leader#{index}: strength {row[cols[0]]} != reviewed batch-2 value {batch2}")
        original = sum(int(v) for v in originals)
        _require(original % BATCH2_SLOW == 0 and original // BATCH2_SLOW == int(batch2),
                 f"leader#{index}: batch-2 value {batch2} is not the original {original} / {BATCH2_SLOW}")
        value = rescale(original)
        _require(str(value) == new, f"leader#{index}: computed {value} != reviewed {new}")
        for col in cols:
            row[col] = new
    return out


def ability3_checks(rows: list[list[str]]) -> dict[str, Any]:
    """只读核对（U1 不加旗号的前提）：追击 629 只有两行调用，都挂前置 42（仅队长）＋前置2 雷共鸣。"""
    _require(all(len(r) == ABILITY_NCOLS for r in rows), f"ability:{ABILITY3} shape drift")
    pierce = [r for r in rows if r[47] == "629" and (r[70] == CAS_PIERCE or r[71] == PIERCE_PROGRAM)]
    _require(len(pierce) == 2, f"pierce 629 callers drift: {len(pierce)} rows")
    for row in pierce:
        _require((row[70], row[71]) == (CAS_PIERCE, PIERCE_PROGRAM), "pierce 629 row points elsewhere")
        _require(row[6] == "42", "pierce 629 rows must stay leader-only (precondition 42)")
        _require((row[13], row[16], row[17], row[18]) == ("2", "600000", "600000", ELEMENT_TOKEN),
                 "pierce 629 rows must stay thunder-resonance gated (precondition 2 kind 2 ≥6 Yellow)")
    return {"pierce_callers": [f"{ABILITY3}#{rows.index(r)}" for r in pierce],
            "triggers": [r[27] for r in pierce],
            "leader_only_and_thunder_resonance": True}


def _single_text(rows: list[list[str]], key: str) -> str:
    _require(len(rows) == 1 and len(rows[0]) == 1, f"{key}: expected one single-column row")
    return rows[0][0]


def panel_text(key: str, rows: list[list[str]]) -> list[list[str]]:
    """live 覆盖面板 → 本轮文案：先（队长）换数字得 NUMERIC，D 节口径 3（冒号改逗号）＋口径 4 /「迟缓」→「冻结」（按数据改文字）
    ＋口径 5（按数据条件拆行）得 PREEDIT，再按 RESONANCE_DROPS 删「雷属性共鸣时，」（C 节）。每一步都必须重算出登记的常量
    （fail closed）。"""
    old, numeric, preedit, new = PANEL_TEXTS[key]
    _require(_single_text(rows, key) == old, f"{key}: unexpected panel text")
    _require(normalized_panel(key, numeric) == preedit,
             f"{key}: constants disagree with the resonance normalisation / data corrections / splits")
    _require(drop_resonance(preedit, RESONANCE_DROPS.get(key, {})) == new, f"{key}: constants disagree with the drops")
    splits = sum(len(after) - 1 for _before, after, _why in PANEL_SPLITS.get(key, {}).values())
    splits += sum(len(after) - 1 for _before, after, _why in PANEL_ENHANCEMENTS.get(key, {}).values())
    _require(len(new.split("\n")) == len(old.split("\n")) + splits,
             f"{key}: line count changed without a merge / registered split / enhancement edit")
    problems = panel_rule_problems(key, new)
    _require(not problems, "; ".join(problems))
    return [[new]]


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    return panel_text(CAS_LEADER, rows)


def switch_text(key: str, rows: list[list[str]]) -> list[list[str]]:
    """E 节：技能强化条目 live 原文 → 官方格式（点名技能、定性、无数字与秒数）；原文必须逐字相符（fail closed）。"""
    old, new = SWITCH_TEXTS[key]
    _require(_single_text(rows, key) == old, f"{key}: unexpected skill-enhancement text")
    import wf_midautumn_kitlib as KL
    problems = KL.panel_problems(new, skill_flag=True) + panel_rule_problems(key, new)
    _require(new.startswith(f"强化『{SKILL_NAME}』："), f"{key}: the entry must name the skill 『{SKILL_NAME}』")
    _require(not problems, "; ".join(problems))
    return [[new]]


def _flag_rows(kind: str, rows: list[list[str]]) -> list[int]:
    cols = (47, 109) if kind == "ability" else (45, 107)
    return [i for i, row in enumerate(rows) if any(c < len(row) and row[c] in FLAG_KINDS for c in cols)]


def switch_basis(abilities: dict[str, list[list[str]]], leader: list[list[str]],
                 action: list) -> dict[str, Any]:
    """E 节依据（只读、fail closed）：

    1. 凯尔全部能力键（1–6）与队长表里切技能旗号的行只有能力1#2：kind 536（旗号 1）、c70 = :data:`CAS_SWITCH`、
       前置 kind 2 雷≥6 共鸣 ⇒ 强化条目写在能力1 面板、带「雷属性共鸣时，」；能力6 没有开关行 ⇒ 能力6 面板的强化行删除。
    2. 能力1#1（211 自身技能槽 50%）与 #2 前置逐格相同 ⇒ 拆出的两行都写「雷属性共鸣时，」；强度与面板数值行一致。
    3. 强化条目点名的技能 = action_skill 第 1 档 c0。
    """
    _require(sorted(abilities) == [f"{CID}{slot}" for slot in range(1, 7)], f"abilities {sorted(abilities)} != 1–6")
    _require(all(len(r) == ABILITY_NCOLS for rows in abilities.values() for r in rows), "ability shape drift")
    switches = [(key, i) for key, rows in sorted(abilities.items()) for i in _flag_rows("ability", rows)]
    switches += [("leader", i) for i in _flag_rows("leader_ability", leader)]
    _require(switches == [(ABILITY1, SWITCH_ROW)], f"skill-flag switch rows drift: {switches}")
    ability1 = abilities[ABILITY1]
    _require(len(ability1) == 3, f"ability:{ABILITY1} shape drift ({len(ability1)} rows)")
    switch = ability1[SWITCH_ROW]
    _require((switch[3], switch[47], switch[70]) == ("0", SWITCH_KIND, CAS_SWITCH),
             f"ability1#{SWITCH_ROW}: not the instant 536 switch row pointing at {CAS_SWITCH}")
    _require(_thunder_resonance(switch), f"ability1#{SWITCH_ROW}: lost its thunder-resonance precondition")
    gauge = ability1[1]
    _require((gauge[3], gauge[47], gauge[48]) == ("0", "211", "0") and gauge[51] == gauge[52],
             "ability1#1: not the instant self skill-gauge row")
    _require([gauge[c] for c in _ABILITY_PRECONDITION_COLS] == [switch[c] for c in _ABILITY_PRECONDITION_COLS],
             "ability1#1/#2: preconditions differ (the split lines would need different prefixes)")
    _require(f"自身技能槽＋{int(gauge[51]) // 1000}%" in PANEL_ENHANCEMENTS[CAS_ABILITY1][1][1][0],
             "ability1#1: strength differs from the panel")
    _require(not _flag_rows("ability", abilities[ABILITY6]), "ability6 gained a switch row (keep its enhancement line)")
    names = [fields[0] for inner, fields in action if inner == "1"]
    _require(names == [SKILL_NAME], f"skill name drift: {names} != [{SKILL_NAME!r}]")
    return {"switch": f"{ABILITY1}#{SWITCH_ROW}（kind {SWITCH_KIND} → 旗号 1，前置 kind 2 雷≥6，c70 {CAS_SWITCH}）",
            "same_condition": f"{ABILITY1}#1（211 自身技能槽 {int(gauge[51]) // 1000}%）",
            "no_switch_elsewhere": [f"ability:{key}" for key in sorted(abilities) if key != ABILITY1] + ["leader_ability"],
            "skill_name": SKILL_NAME}


#: E 节强化条目的定性内容（旗号 1 开支）：两档技能树与天雷树。键 = 条目里的短语，值 = 开支里必须出现的节点。
SWITCH_TREE_FACTS = {
    "追加赋予队伍贯穿、直接攻击伤害提升与加速效果": ("FindAllSubjects(33)", ("ACPiercing", "ACDirectDamage", "ACSpeedup")),
    "消除距离最近的敌人的部分强化效果并赋予其冻结效果": ("FindNearSubjects(49)", ("DeleteCondition", "ACFrozen")),
    "同时强化自身直击召唤的天雷": ("天雷树 ConditionalsChangeSkillFlag(1)", ()),
}


def _names(node) -> list[str]:
    found: list[str] = []
    if isinstance(node, list):
        if node and isinstance(node[0], str) and (node[0].startswith("AC") or node[0] == "DeleteCondition"):
            found.append(node[0])
        for item in node:
            found += _names(item)
    return found


def _flag_nodes(tree) -> list[list]:
    found: list[list] = []
    if isinstance(tree, list):
        if len(tree) == 2 and tree[0] == "Command" and isinstance(tree[1], list) and tree[1] \
                and tree[1][0] == "ConditionalsChangeSkillFlag":
            found.append(tree[1])
        for item in tree:
            found += _flag_nodes(item)
    return found


def switch_tree_problems(skill_trees: list, thunder_tree) -> list[str]:
    """E 节条目内容的 DSL 依据：两档技能树各有一个 ConditionalsChangeSkillFlag(1)，开支 = FindAllSubjects(selector 33)
    里 ACPiercing / ACDirectDamage / ACSpeedup ＋ FindNearSubjects(selector 49) 里 DeleteCondition ＋ ACFrozen，关支为空；
    629 天雷树有 ConditionalsChangeSkillFlag(1) 两支（强化档 / 常态档）。"""
    problems = []
    for level, tree in enumerate(skill_trees, 1):
        flags = _flag_nodes(tree)
        if len(flags) != 1 or flags[0][1] != 1:
            problems.append(f"skill {level}: expected one ConditionalsChangeSkillFlag(1), got {[f[1] for f in flags]}")
            continue
        on, off = flags[0][2], flags[0][3]
        if off != ["Block", []]:
            problems.append(f"skill {level}: flag-1 off branch is not empty")
        body = on[1] if isinstance(on, list) and len(on) == 2 and on[0] == "Block" else []
        team = [c[1] for c in body if isinstance(c, list) and c[0] == "Command" and c[1][0] == "FindAllSubjects"]
        near = [c[1] for c in body if isinstance(c, list) and c[0] == "Command" and c[1][0] == "FindNearSubjects"]
        if len(team) != 1 or team[0][2] != 33 or sorted(set(_names(team[0]))) != ["ACDirectDamage", "ACPiercing",
                                                                                   "ACSpeedup"]:
            problems.append(f"skill {level}: flag-1 team block is not pierce / direct damage / speedup on selector 33")
        if len(near) != 1 or near[0][3] != 49 or sorted(set(_names(near[0]))) != ["ACFrozen", "DeleteCondition"]:
            problems.append(f"skill {level}: flag-1 enemy block is not dispel + frozen on the nearest enemy")
    flags = _flag_nodes(thunder_tree)
    if len(flags) != 1 or flags[0][1] != 1 or flags[0][2] == flags[0][3]             or not all(_has_command(branch, "CreateNormalAttack") for branch in flags[0][2:4]):
        problems.append("thunder: expected one ConditionalsChangeSkillFlag(1) whose enhanced / normal branches both strike")
    return problems


def _has_command(node, name: str) -> bool:
    if isinstance(node, list):
        if len(node) == 2 and node[0] == "Command" and isinstance(node[1], list) and node[1] and node[1][0] == name:
            return True
        return any(_has_command(item, name) for item in node)
    return False


#: 前置块基址（能力表 c6/c13/c20；块内 +0 kind、+3/+4 阈值、+5 属性组、+6 固有 id）。
_ABILITY_PRE = (6, 13, 20)
_GRANT_KINDS = ("461", "413", "436", "459")      # 授予固有（自身/友方、敌方三种）；+21 列 = 固有 id


def _thunder_resonance(row: list[str]) -> bool:
    return any((row[b], row[b + 3], row[b + 4], row[b + 5]) == ("2", "600000", "600000", ELEMENT_TOKEN)
               for b in _ABILITY_PRE)


def crescent_resonance_basis(ability2: list[list[str]], ability3: list[list[str]],
                             leader: list[list[str]]) -> dict[str, Any]:
    """C 节共鸣省略的数据依据（只读、fail closed）：

    1. 「月牙」在凯尔词条里的获取行只有能力3#0/#1（瞬发 461 → 13999001），都挂前置 kind 2 雷≥6（雷共鸣）；
       能力2 / 队长表不授予「月牙」（live 全表与 DSL 的全量核对在测试里，需要 live store）。
    2. 被省略前缀的面板行描述的数据都按「月牙」生效：队长#0–#3 与能力2#0/#1 = dt134 读 13999001；
       能力3#3 = 前置1 187 持有 13999001；能力3#4/#5 = 629 追击树（:func:`pierce_tree` 核对其 Bind 读 DCUnique 13999001）。
    """
    grants = [(label, i, row) for label, rows in (("ability2", ability2), ("ability3", ability3))
              for i, row in enumerate(rows) if row[47] in _GRANT_KINDS and row[68] == UID_CRESCENT]
    grants += [("leader", i, row) for i, row in enumerate(leader)
               if row[45] in _GRANT_KINDS and row[66] == UID_CRESCENT]
    _require([(label, i) for label, i, _r in grants] == [("ability3", 0), ("ability3", 1)],
             f"crescent grant rows drift: {[(label, i) for label, i, _r in grants]}")
    for _label, i, row in grants:
        _require(row[5] == "0" and row[47] == "461", f"ability3#{i}: crescent grant is not an instant 461 row")
        _require(_thunder_resonance(row), f"ability3#{i}: crescent grant lost its thunder-resonance precondition")
    during = [i for i, row in enumerate(leader) if row[95] == "134" and row[102] == UID_CRESCENT]
    _require(during == [0, 1, 2, 3], f"leader crescent growth rows drift: {during}")
    capped = [i for i, row in enumerate(ability2) if row[97] == "134" and row[104] == UID_CRESCENT]
    _require(capped == [0, 1] and len(ability2) == 2, f"ability2 crescent growth rows drift: {capped}")
    holder = [i for i, row in enumerate(ability3) if row[6] == "187" and row[12] == UID_CRESCENT]
    _require(holder == [3] and ability3[3][47] == "202", f"ability3 crescent-holder rows drift: {holder}")
    return {
        "state": f"{UID_CRESCENT}「月牙」",
        "sources": [f"{ABILITY3}#{i}（461，前置 kind 2 雷≥6）" for _label, i, _r in grants],
        "implied_resonance": ELEMENT_TOKEN,
        "dependents": {"leader": [f"{LEADER_KEY}#{i}" for i in during],
                       "ability2": [f"{ABILITY2}#{i}" for i in capped],
                       "ability3_holder": [f"{ABILITY3}#{i}" for i in holder],
                       "ability3_pierce_629": [f"{ABILITY3}#4", f"{ABILITY3}#5"]},
        "dsl": "凯尔技能 1/2、换形、629 追击/天雷、PF 雷环共 7 棵树无 ACUnique 13999001；追击树只 DCUnique 读层数",
    }


def panel_correction_basis(ability5: list[list[str]], leader: list[list[str]]) -> dict[str, Any]:
    """D 节口径 4 的数据依据（只读、fail closed）：

    1. 队长第 2 行「强化自身冲刺」= 能力5 冲刺参数行（c109 = 422）：只有 #1–#4，全部只挂前置 42（仅队长），
       前置 2/3 为空、任何前置块都不是雷共鸣 ⇒ 面板不写「雷属性共鸣时，」。
    2. 队长第 6 行第二个效果 = 队长#7：c45 = 53 眩晕畏缩特攻（与#6 同触发 51 贯穿、同对象全队(雷)）⇒ 写特攻，不写「追击伤害」。
    """
    _require(all(len(r) == ABILITY_NCOLS for r in ability5), f"ability:{ABILITY5} shape drift")
    dash = [i for i, row in enumerate(ability5) if row[109] == DASH_KIND]
    _require(dash == [1, 2, 3, 4], f"dash-parameter rows drift: {dash}")
    for i in dash:
        row = ability5[i]
        _require(row[6] == "42" and row[13] in ("", "0") and row[20] in ("", "0"),
                 f"ability5#{i}: dash-parameter row is no longer gated by the leader precondition alone")
        _require(not _thunder_resonance(row), f"ability5#{i}: dash-parameter row gained a thunder-resonance gate")
    row = leader[STUN_WINCE_ROW]
    _require((row[25], row[45], row[46], row[47]) == ("51", STUN_WINCE_KIND, "5", ELEMENT_TOKEN),
             f"leader#{STUN_WINCE_ROW}: not the piercing → thunder-team stun/wince slayer row")
    _require(leader[STUN_WINCE_ROW - 1][25] == "51" and leader[STUN_WINCE_ROW - 1][45] == "32",
             f"leader#{STUN_WINCE_ROW - 1}: panel line 6 no longer pairs attack with the slayer row")
    _require(f"额外乘区＋{int(row[49]) / 1000:g}%" in PANEL_CORRECTIONS[CAS_LEADER][5][1],
             f"leader#{STUN_WINCE_ROW}: slayer strength {row[49]} differs from the panel")
    return {
        "dash": {"rows": [f"{ABILITY5}#{i}" for i in dash], "kind": DASH_KIND,
                 "precondition": "42（仅队长），无雷共鸣"},
        "stun_wince": {"row": f"{LEADER_KEY}#{STUN_WINCE_ROW}", "kind": STUN_WINCE_KIND,
                       "strength": row[49]},
    }


def frozen_slayer_basis(ability6: list[list[str]]) -> dict[str, Any]:
    """「迟缓」→「冻结」的数据依据（只读、fail closed）：能力6 只有 #0 一行，瞬发内容 c47 = 119 FrozenSlayer（冻结特攻），
    对象全队(雷)、强度 = 面板「额外乘区＋15%」、带雷共鸣前置（面板照写「雷属性共鸣时，」）。技能 DSL 两档强化档是
    ``ACFrozen``（无 ``ACSlow``）的全量核对在测试里（第二批输出 = live 技能树；live store 可用时再核一次）。"""
    _require(len(ability6) == 1 and len(ability6[0]) == ABILITY_NCOLS, f"ability:{ABILITY6} shape drift")
    row = ability6[0]
    _require((row[3], row[47], row[48], row[49]) == ("0", FROZEN_SLAYER_KIND, "5", ELEMENT_TOKEN),
             f"ability6#0: not the instant thunder-team frozen slayer row "
             f"(c47={row[47]!r} c48={row[48]!r} c49={row[49]!r})")
    _require(_thunder_resonance(row), "ability6#0: lost its thunder-resonance precondition")
    line = PANEL_CORRECTIONS[CAS_ABILITY6][1][1]
    _require(row[51] == row[52] and f"额外乘区＋{int(row[51]) / 1000:g}%" in line and "“冻结”" in line,
             f"ability6#0: slayer strength {row[51]} / state differs from the panel")
    return {"row": f"{ABILITY6}#0", "kind": f"{FROZEN_SLAYER_KIND} FrozenSlayer（冻结特攻）", "strength": row[51],
            "state_source": "技能 DSL 两档强化档 ACFrozen（无 ACSlow）"}


#: 能力表条件列：前置三块 c6–c26（kind / puller / 阈值 / 属性组 / 固有 id）；触发块 c27–c36（种类 / 对象 / 阈值 / CT…）。
_ABILITY_PRECONDITION_COLS = tuple(range(6, 27))
_ABILITY_TRIGGER_COLS = tuple(range(27, 37))
#: 口径 5 拆行依据：能力3 第 1 行的两个获取行 → (行号, 触发种类, 触发对象 c28, 触发阈值 c30, 面板里的触发写法)。
SPLIT_TRIGGERS = ((0, "23", "5", "100000", "雷属性角色发动技能时"),
                  (1, "20", "7", "10000000", "雷属性角色每造成100次直击"))


def panel_split_basis(ability3: list[list[str]]) -> dict[str, Any]:
    """口径 5 拆行的数据依据（只读、fail closed）：能力3#0/#1 的前置（雷≥6 共鸣）与内容（461 → 月牙）逐格相同，
    触发不同（23 雷属性角色发动技能 / 20 雷属性角色直击每 100 次）⇒ 两种数据条件，拆两行；两行都照写共鸣前缀。
    两行条件若相同 ⇒ 应合并而不是拆 ⇒ 拒绝。"""
    _require(all(len(r) == ABILITY_NCOLS for r in ability3), f"ability:{ABILITY3} shape drift")
    rows = [ability3[i] for i, *_x in SPLIT_TRIGGERS]
    for (index, trigger, target, threshold, phrase), row, line in zip(SPLIT_TRIGGERS, rows, ABILITY3_SPLIT_LINES):
        _require((row[47], row[68]) == ("461", UID_CRESCENT), f"ability3#{index}: not a crescent grant row")
        _require(_thunder_resonance(row), f"ability3#{index}: lost its thunder-resonance precondition")
        _require((row[27], row[28], row[29], row[30]) == (trigger, target, ELEMENT_TOKEN, threshold),
                 f"ability3#{index}: trigger drift ({row[27]!r}/{row[28]!r}/{row[30]!r})")
        _require(line.startswith(MAIN_ICON + RESONANCE_PREFIX + phrase), f"ability3#{index}: split line wording drift")
    first, second = rows
    _require([first[c] for c in _ABILITY_PRECONDITION_COLS] == [second[c] for c in _ABILITY_PRECONDITION_COLS],
             "ability3#0/#1: preconditions differ (the split lines would need different prefixes)")
    _require([first[c] for c in range(47, ABILITY_NCOLS)] == [second[c] for c in range(47, ABILITY_NCOLS)],
             "ability3#0/#1: contents differ (not the same crescent grant)")
    _require([first[c] for c in _ABILITY_TRIGGER_COLS] != [second[c] for c in _ABILITY_TRIGGER_COLS],
             "ability3#0/#1 share one data condition: merge instead of splitting")
    return {"rows": [f"{ABILITY3}#{i}" for i, *_x in SPLIT_TRIGGERS],
            "triggers": {f"{ABILITY3}#{i}": f"{trigger}（{phrase}）" for i, trigger, _t, _th, phrase in SPLIT_TRIGGERS},
            "shared": "前置 kind 2 雷≥6 共鸣；内容 461 → 13999001「月牙」"}


def pierce_tree(tree) -> list:
    """段数成长撤封顶：``BindConditionAccumulationVariable`` 第 5 参 10 → 99（int）；其余逐字不动。"""
    out = deepcopy(tree)
    _require(isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl", "pierce root drift")
    block = out[11]
    _require(block[0] == "Block" and len(block[1]) == 2, "pierce body must be [Bind, CreateCondition]")
    bind, condition = block[1][0][1], block[1][1][1]
    _require(bind == PIERCE_BIND_BEFORE, f"pierce bind preimage drift: {bind}")
    _require(condition[0] == "CreateCondition" and condition[1] == -17, "pierce CreateCondition drift")
    ac = condition[2][0]
    _require(ac[0] == "ACAdditionalDirectAttack" and ac[2] == PIERCE_TIMES,
             f"pierce ACAdditionalDirectAttack times drift: {ac[2]}")
    bind[PIERCE_CEIL_SLOT] = PIERCE_CEIL_AFTER
    return out


def dsl_problems(tree) -> list[str]:
    """AMF3 往返 + 四道 DSL 门禁（元素 / 主体绑定 / lookup 作用域 / 判定区目标）。"""
    import wf_client_legality as L
    import wf_dsl
    problems = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    return problems


def row_problems(kind: str, row: list[str]) -> list[str]:
    import wf_client_legality as L
    cas_keys = {CAS_LEADER, CAS_PIERCE, CAS_THUNDER}
    return (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
            + L.invoke_skill_string_problems(row, cas_keys, kind=kind))


# ---------------------------------------------------------------- revise

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {key: _checked(read, *key) for key in BEFORE}
    checks = ability3_checks(inputs["ability", ABILITY3])
    basis = crescent_resonance_basis(inputs["ability", ABILITY2], inputs["ability", ABILITY3],
                                     inputs["leader", LEADER_KEY])
    leader = leader_rows(inputs["leader", LEADER_KEY])
    corrections = panel_correction_basis(inputs["ability", ABILITY5], leader)
    frozen = frozen_slayer_basis(inputs["ability", ABILITY6])
    split = panel_split_basis(inputs["ability", ABILITY3])
    switch = switch_basis({key: inputs["ability", key] for key in (ABILITY1, ABILITY2, ABILITY3, ABILITY4, ABILITY5,
                                                                  ABILITY6)},
                          inputs["leader", LEADER_KEY], inputs["action", CODE])
    pierce = pierce_tree(inputs["dsl", PIERCE_PROGRAM])
    _require(pierce[11][1][0][1][PIERCE_CEIL_SLOT] == CRESCENT_UNIQUE_CAP,
             "pierce ceiling must equal the crescent unique cap")
    _require(pierce[11][1][0][1][3] == ["DCUnique", int(UID_CRESCENT)], "pierce tree no longer reads the crescent")

    problems = [f"leader#{i}: {p}" for i, row in enumerate(leader) for p in row_problems("leader_ability", row)]
    problems += [f"dsl {PIERCE_PROGRAM}: {p}" for p in dsl_problems(pierce)]
    _require(not problems, "; ".join(problems))

    return {
        "ability": {},
        "leader": {LEADER_KEY: leader},
        "cas": {**{key: panel_text(key, inputs["cas", key]) for key in PANEL_TEXTS},
                **{key: switch_text(key, inputs["cas", key]) for key in SWITCH_TEXTS}},
        "text": {}, "table": {}, "action": {}, "dsl": {PIERCE_PROGRAM: pierce}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_kyle.py",
            "batch": "2026-09-27 第三轮（成长复核 4/5 + 追击段数撤封顶 U1）",
            "spec": "growth_c_spec.md（作者原话 1–6、D1–D4、U1）；reeval_full.json table.rows 凯尔 7 行 / "
                    "design.characters 凯尔",
            "generator": "wf_midautumn_kit_kyle.py（CRESCENT_*/PIERCING_GROWTH/EXPECT/PANEL_LEADER/"
                         "_PANEL_ABILITY_LINES[2][3][6]/PIERCE_VAR_CEIL 已同步）",
            "factor": "4/5（作者点名凯尔「成长降太低了，本身数值就不高」；原值 = 第二批前的值，合并行按两部分原值之和）",
            "rounding": "原值 ≥10% 就近取 5% 的倍数；原值 ≤10%（#7 5%）按 0.5% 取整 ⇒ 4%（口径 D2）",
            "leader": {f"leader_ability:{LEADER_KEY}#{i}": why for i, (*_x, why) in LEADER_EDITS.items()},
            "ability2_capped_kept": f"ability:{CID}2 限 10 层弱化版（雷队直击 10%、自身攻击 16%）按口径 D4 保持第二批值",
            "dsl_growth_uncapped": {
                PIERCE_PROGRAM: "BindConditionAccumulationVariable 第5参 10→99（int，= 第二批前 live 逐字节，"
                                "= 月牙固有上限 99）：段数 = 1 + min(月牙层, 99)",
                "no_flag": "调用方只有能力3#4/#5（前置42 仅队长 + 前置2 雷共鸣）⇒ 不加旗号（口径 U1）；"
                           "门控在能力3 行，须能力3 解锁（复核意见）",
                "ability3_checks": checks,
            },
            "growth_3min_leader": {
                "crescent_layers": "60–99 层，偏向 99（撤封顶后正反馈：段数越多直击计数越快，推断）",
                "self_attack": "原 4500–7425% / 批二 450%+160% / 本轮 3600–5940%+160%（能力2 封顶版）",
                "thunder_team_direct": "原 4500–7425% / 批二 450%+100% / 本轮 3600–5940%+100%",
                "thunder_team_attack": "原 750–1237.5% / 批二 75% / 本轮 600–990%",
                "self_direct_extra": "原 1500–2475% / 批二 150% / 本轮 1200–1980%",
                "piercing_45": "雷队攻 原 1125% / 批二 112.5% / 本轮 900%；追击 原 225% / 批二 22.5% / 本轮 180%",
                "direct_hit_segments": "每次直击 1 + min(月牙, 99)：原 61–100 段 / 批二 最多 11 段 / 本轮 61–100 段",
            },
            "author_confirm": [
                "4/5 配合追击恢复 99 后，凯尔当队长时约回到第二批前的 80%（自身攻击含能力2 封顶版约 82%）",
                "代价：99 层时每次直击约 100 段，直击 Down（削韧）按段数放大（第二批封顶时 11 段）",
                "前 10 层自身攻击每层 60%+16% = 76%，略高于原值 75%（能力2 封顶版与队长行叠加）",
            ],
            "kept": {
                f"leader_ability:{LEADER_KEY}#4/#5": "雷共鸣 技能槽上限/充能 +20%——口径 A6",
                f"leader_ability:{LEADER_KEY}#8": "特殊强化弹射 722",
                f"ability:{CID}2": "封顶版不动（D4）",
                "thunder/skill trees": "第二批 Down 改动不动",
            },
            "panel": {CAS_LEADER: "第4行月牙数字（自身60%/80%，除自身外10%/60%）、第5行去掉「（最多10层）」、"
                                  "第6行贯穿数字（20%/4%）；口径 3 共鸣冒号改逗号；口径 4 第2行去掉共鸣前缀、"
                                  "第6行「追击伤害」改为眩晕畏缩特攻写法；第4、5行省略「雷属性共鸣时，」",
                      CAS_ABILITY2: "口径 3 冒号改逗号后，第1行省略「雷属性共鸣时，」（数值不动）",
                      CAS_ABILITY3: "口径 3 冒号改逗号；口径 5 第1行按数据条件（发动技能 / 每100次直击）拆两行，"
                                    "各自照写共鸣前缀；原第3行（现第4行）省略「雷属性共鸣时，」（数值不动）",
                      CAS_ABILITY6: "口径 3 冒号改逗号；第2行「迟缓」按数据（1399906#0 kind 119 冻结特攻、技能 DSL ACFrozen）"
                                    "改「冻结」；第1行技能强化行删除（能力6 无开关行，条目在能力1 面板，E 节）（数值不动）",
                      CAS_ABILITY1: "E 节：第2行（自身技能槽＋50% 与技能强化挤在一句）拆成数值行 + 官方格式强化条目行，"
                                    "两行都写「雷属性共鸣时，」（口径 3 冒号改逗号）；第1行不动",
                      CAS_SWITCH: f"E 节：「{OLD_SWITCH_TEXT}」→「{NEW_SWITCH_TEXT}」（官方格式点名技能、定性、无数字）"},
            "skill_enhancement": {
                "rule": "主会话 2026-09-27 口径 R1–R3：技能强化效果只写在能力 / 队长面板的强化条目里（官方格式「强化『技能名』：…」、"
                        "定性无数字、开关行带共鸣前置则面板行保留「X属性共鸣时，」），技能描述不重复强化后效果",
                "entries": {key: {"from": old, "to": new} for key, (old, new) in SWITCH_TEXTS.items()},
                "panels": {f"{key} L{i + 1}": {"from": before, "to": list(after), "why": why}
                           for key, lines in PANEL_ENHANCEMENTS.items() for i, (before, after, why) in lines.items()},
                "basis": switch,
                "tree_facts": {phrase: f"{where}：{'/'.join(nodes) if nodes else '强化档与常态档两支'}"
                               for phrase, (where, nodes) in SWITCH_TREE_FACTS.items()},
                "skill_description": "技能描述（action_skill / character_text / 服务端）只写技能本体、无强化后描述 ⇒ 不改",
            },
            "panel_rules_20260927": {
                "resonance_punctuation": "口径 3：本模块返回的五块覆盖面板里「雷属性共鸣时：」一律写「雷属性共鸣时，」"
                                         "（凯尔没有「共鸣时：」后换行接效果的行）；未返回的能力4/5 面板不动",
                "data_corrections": {f"{key} L{i + 1}": {"from": before, "to": after, "why": why}
                                     for key, lines in PANEL_CORRECTIONS.items()
                                     for i, (before, after, why) in lines.items()},
                "basis": corrections,
                "frozen_basis": frozen,
                "splits": {f"{key} L{i + 1}": {"from": before, "to": list(after), "why": why}
                           for key, lines in PANEL_SPLITS.items() for i, (before, after, why) in lines.items()},
                "split_basis": split,
                "rule_scan": "返回面板无「X属性共鸣时：」、无全角「／」与半角「/」、无「迟缓」（panel_rule_problems）",
            },
            "panel_merge": {
                "rule": "作者 2026-09-27「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣，"
                        "引擎点火提供的效果就不用写火属性共鸣，其他角色类似」；主会话合并规则（只并数据同条件的行、"
                        "共鸣省略按固有状态全部获取来源判定、数据前置不动）",
                "resonance_drops": {key: {f"L{i + 1}": why for i, why in lines.items()}
                                    for key, lines in RESONANCE_DROPS.items()},
                "resonance_basis": basis,
                "merges": "无：数据同条件的组（队长#0–#3/#4–#5/#6–#7、能力2#0–#1、能力4#0–#1）都已各在一行；"
                          "能力1#1–#2 同条件，但 #2 的技能强化条目按 E 节单独成行（与 CAS 同文）",
                "reviewed_unchanged": PANELS_REVIEWED_UNCHANGED,
                "check_merge": "五块覆盖面板过 wf_panel_merge_check.check（原文 = 数值改后再经口径 3/4/5、"
                               "「迟缓」→「冻结」与 E 节强化条目的文案，prefix_drops = 上表）与 panel_problems",
            },
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/kyle.json"
PANEL_REL = BATCH / "rework1/panel/kyle.json"
MIRROR_KEY = "balance_20260927c"
MIRROR_NOTE = ("2026-09-27 第三轮平衡（成长复核 + 撤封顶）：月牙逐层与贯穿成长改为原值×4/5（第二批 ×1/10 作废）——"
               "月牙每层 雷队攻击 10%、自身攻击 50%（含能力2 搬入）、雷队直击 60%（含能力2 搬入）、自身直击 20%；"
               "贯穿 雷队攻击 20%、眩晕畏缩特攻 4%；629 追击段数 DSL 上限 10→99（Bind 第5参，= 月牙上限，"
               "调用方只在队长且雷共鸣时执行，不加旗号），面板去掉「（最多10层）」。能力2 封顶版保持第二批。"
               "面板合并与共鸣省略：「月牙」只由能力3#0/#1（都带雷共鸣）获取 ⇒ 月牙提供的效果行（队长第4、5行、"
               "能力2第1行、能力3第3行）省略「雷属性共鸣时，」；数据同条件的组本来各在一行，无可合并行。"
               "面板统一口径：队长/能力2/能力3 面板的共鸣前缀写「雷属性共鸣时，」；队长第2行「强化自身冲刺」"
               "去掉共鸣前缀（冲刺参数行只挂队长前置）；队长第6行「追击伤害＋4%」按数据（队长#7 kind 53）改为"
               "「对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋4%」。"
               "暂存前最后一轮：能力3第1行按数据条件拆两行（能力3#0 雷属性角色发动技能 / #1 每100次直击，各自照写共鸣前缀）；"
               "能力6第2行「迟缓」按数据（能力6#0 kind 119 冻结特攻，技能强化档 ACFrozen）改「冻结」，能力6 冒号改逗号。"
               "技能强化条目口径（主会话 2026-09-27）：change_skill_kyle_moon 改官方格式「强化『月华·狼牙连斩』：…」"
               "（定性、无数字）；能力1第2行拆成「雷属性共鸣时，自身技能槽＋50%」与同文强化条目行；能力6第1行"
               "（能力6 无开关行的重复强化行）删除；技能描述不写强化后效果、不改。")


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等；不改第一批 / 第二批的镜像块）。"""
    import wf_midautumn_kit_kyle as K
    design, panel = deepcopy(design), deepcopy(panel)
    mirror = design["plan"]["rework1"]
    mirror[MIRROR_KEY] = dict(
        module="mod-tools/wf_balance_20260927c_kyle.py",
        factor="4/5",
        leader={f"#{i}": why for i, (*_x, why) in LEADER_EDITS.items()},
        leader_values={"crescent": {"team_attack": K.CRESCENT_TEAM_ATTACK, "self_attack": K.CRESCENT_SELF_ATTACK,
                                    "team_direct": K.CRESCENT_TEAM_DIRECT, "self_direct": K.CRESCENT_SELF_DIRECT},
                       "piercing": dict(K.PIERCING_GROWTH)},
        direct_hit_count=f"1 + min(月牙层数, {K.PIERCE_VAR_CEIL})（第二批封顶 10，本轮恢复）",
        kept=["ability:1399902 限 10 层弱化版（口径 D4）",
              "leader_ability:139990 #4/#5 技能槽上限/充能 20%（口径 A6）"],
        panel_resonance_drops={key: [f"L{i + 1}" for i in lines] for key, lines in RESONANCE_DROPS.items()},
        panel_data_corrections={key: {f"L{i + 1}": after for i, (_before, after, _why) in lines.items()}
                                for key, lines in PANEL_CORRECTIONS.items()},
        panel_splits={key: {f"L{i + 1}": [line.replace(MAIN_ICON, "") for line in after]
                            for i, (_before, after, _why) in lines.items()}
                      for key, lines in PANEL_SPLITS.items()},
        skill_enhancement=dict(
            cas={key: new for key, (_old, new) in SWITCH_TEXTS.items()},
            panels={key: {f"L{i + 1}": [line.replace(MAIN_ICON, "") for line in after]
                          for i, (_before, after, _why) in lines.items()}
                    for key, lines in PANEL_ENHANCEMENTS.items()},
        ),
    )
    problems = K._design_problems(design)
    if problems:
        raise KyleBalanceCError(f"design mirror still drifts: {problems}")
    panel["leader"]["lines"] = [dict(text=line, status="changed") for line in K.PANEL_LEADER.split("\n")]
    # 能力面板与第一批 / 第二批 mirror_updates 同一写法（整块按生成器重写），保证它们在本轮之后重跑仍是恒等
    for entry in panel["abilities"]:
        slot = int(entry["index"])
        entry["lines"] = [dict(text=line.replace(K.MAIN_ICON, ""), status="changed")
                          for line in K.PANEL_ABILITY[slot].split("\n")]
    panel[MIRROR_KEY] = dict(note=MIRROR_NOTE, module="mod-tools/wf_balance_20260927c_kyle.py",
                             supersedes="balance_20260927b 的「段数成长封顶 10 层，面板已单列上限」：本轮撤封顶，"
                                        "面板段数行不再写上限")
    return design, panel


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """indent=2、保留原文件换行风格（本机两份镜像是 CRLF）。"""
    newline = "\r\n" if b"\r\n" in path.read_bytes() else "\n"
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def sync_mirrors(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回两份设计镜像；返回有变化的相对路径。"""
    root = Path(root)
    rels = (DESIGN_REL, PANEL_REL)
    before = [_load(root / rel) for rel in rels]
    after = mirror_updates(*before)
    changed = [str(rel) for rel, old, new in zip(rels, before, after) if old != new]
    if write:
        for rel, old, new in zip(rels, before, after):
            if old != new:
                _save(root / rel, new)
    return changed


if __name__ == "__main__":
    import sys
    here = Path(__file__).resolve().parent
    pass  # Imports resolve from this checkout/package, not external source copies.
    changed = sync_mirrors(here.parent, write="--write" in sys.argv[1:])
    print(json.dumps({"changed": changed, "write": "--write" in sys.argv[1:]}, ensure_ascii=False))

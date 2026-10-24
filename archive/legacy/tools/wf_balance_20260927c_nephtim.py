"""校园奈芙提姆 169989 ``ruin_girl_campus``：2026-09-27 平衡调整第三轮（c，成长复核）。

作者口径（主会话逐字转述，施工口径 ``growth_c_spec.md``）：「成长速度砍到1/10不合理……砍太多了」→「砍到4/5，
或者7/10这样吧」→「可以砍到2/3」→「数值尽量取5的倍数」。第二批（``wf_balance_20260927b_nephtim``，1/10）
把队长两处无上限成长砍得过狠；本轮按成长复核表（``reeval_full.json`` table.rows，行号 0 起）回调，只改数值。

规格（队长行号 0 起，与复核表一致；第二批报告按 1 起计写作 #5 / #9、#10）：
1. 队长 L#8 / L#9（T235 Fever 中持有贯穿每累计 2 秒 → 暗队攻击力 I32 / 直击伤害 I33，不限次）：
   c49/c50 1000 → 7000（每次 +1% → +7%）。原值 10%，2/3 档：10×2/3=6.67，向上取 7%（实际 0.7，不低于 2/3 下限；
   原值 ≤10% 的行 5 的倍数只剩 5%/10%，按复核规则取整数）。
2. 队长 L#4（T12 每 35 连击 → 暗队 Fever 获得量 I50，不限次）：c49/c50 2000 → 15000（+2% → +15%）。
   原值 20%，4/5 档：20×4/5=16，就近取 5 的倍数 15%（实际 0.75）。
3. 面板 ``desc_override_ruin_girl_campus`` 两句同步数字（第5行 +2%→+15%；末行 +1%→+7%），其余逐字不动。
4. 面板同条件合并（作者「同一个条件的提升能不能写到一起来简化描述」；主会话合并规则：只合并同一面板里数据条件
   完全相同的行，效果原措辞与数值保留、只省略重复对象名，合并行放在组首行位置）：
   - 队长块：L#2/L#3/L#5（暗共鸣常驻 → 暗队直击 400%、攻击 200%、Fever 时间 100%）与 L#0/L#1 同条件，
     但 L#0（强化弹射覆盖）/L#1（技能形态切换）是机制行，不并；面板第4行（L#2+L#3）与第6行（L#5）并成一行放在第4行；
   - 能力2 ``_2``：#0/#1（暗共鸣常驻 → 贯穿延长 40% / 暗队直击 250%）两行并一行，Fever 中技能槽上限那行不动。
   其余面板：队长 L#8/L#9 与能力3 两组本来就各是一行；能力1/4/5/6 没有同条件组。
5. 共鸣省略（作者「引擎点火的获取带火属性共鸣，引擎点火提供的效果就不用写火属性共鸣，其他角色类似」；主会话统一
   口径 6）：唯一固有状态「星夜茶会」16998901 只能经技能旗号分支获得——技能两档 DSL（switched 语音版指向同两棵树）
   的全部 ACUnique 授予节点都在 ``ConditionalsChangeSkillFlag(1)`` 的开支里，能力 / 队长表和其余被调起的 DSL
   （629 四棵、722 PF 覆盖三档）都没有授予；旗号 1 的唯一来源是队长 L#1（536，暗编成≥6 前置）⇒ 视为「获取带暗
   共鸣」，能力1 ``_1`` 第2、3行（持有星夜茶会时召唤 / 溢出）删「暗属性共鸣时，」。依据在 :func:`revise` 里按
   数据 fail closed（:func:`resonance_omission_problems`）：旗号来源不唯一或不带暗共鸣、授予跑出旗号分支、出现
   表内授予 / 未读的 629 或 PF 覆盖程序 / 认不出的引用 ⇒ 拒绝，面板省略要重审。
6. 共鸣写法（口径 3）：返回的三块面板没有「X属性共鸣时：」，无需规范化（:func:`panel_problems` 拒绝冒号写法）。
7. 技能强化文案（作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,
   规范并简化描述做了吗」；主会话口径 R1–R4）：队长 L#1（536，旗号 1，暗编成≥6）只有一行，面板却拆成第2、3行，第3行
   还写「强化后的技能发动时」⇒ 并成一行 =「暗属性共鸣时，」+ 条目 ``change_skill_ruin_girl_campus_fever`` 原文
   （条目本身已合规，只读不改；:func:`merge_enhancement_text`，8 行 → 7 行）。技能说明本来就只写技能本体，不改。

不改（口径 D3/D4）：能力3 1699893 的封顶版（攻击 +5%、直击 +10%，各最多 10 次）保持第二批值；不给成长行加共鸣前置
（两行本来就带暗共鸣前置 c4=2）；PF / DSL / 主动说明 / character_text 不含这些数值，不动。

生成器：``wf_nephtim_fever_abilities.LEADER_PIERCING_GROWTH_STRENGTH`` 与
``wf_nephtim_fever_leader.FEVER_GAIN_GROWTH_STRENGTH`` 已同步；面板由 ``wf_nephtim_fever_text`` 从这两处真源取数，
测试断言生成器输出 == :func:`revise` 输出。

纯函数：revise(read) 只经 read() 读取 live，返回有变化的键；不写 live store、候选工作区、assets 或 .cdn。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import wf_client_legality as legality
from wf_midautumn_kitlib import panel_problems as kit_panel_problems

CID = "169989"
CODE = "ruin_girl_campus"
# 同第一、二批：第一个是 active owner，第二个是同 package_id 的副本（只镜像目标键）。
PACKAGES = ["nephtim-summon-cap-20260916/ruin_girl_campus", "campus-nephtim-20260911"]
PACKAGE_VERSION = {
    "nephtim-summon-cap-20260916/ruin_girl_campus": "0.2.5",   # 候选现值 0.2.4（第二批）
    "campus-nephtim-20260911": "0.20260927.2",                 # 候选现值 0.20260927.1（日期式，同日第三次修订）
}
# 本轮只回写队长键与队长面板覆盖串；desc_override_* 需要 V14 面板覆盖补丁（两个候选都已声明）。
CAPABILITIES = ["panel-description-override-v2"]
# 两个候选的目标键与 live 逐字相同（第二批回写后 2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

A3 = CID + "3"
TEXT_LEADER = "desc_override_" + CODE
CHANGE_SKILL_STRING_ID = "change_skill_" + CODE + "_fever"
PF_STRING_ID = CODE + "_fever_powerflip"
BALL_HIT_STRING_ID = CODE + "_ball_hit_count"
MAIN_ICON = " <icon id='main'>  "
DARK_ELEMENT = 5                      # master/character c3 内部 ElementKind（暗）

LEADER_KINDS = ["722", "536", "33", "32", "50", "56", "211", "629", "32", "33"]
FEVER_GAIN_INDEX = 4                  # 队长 L#4：每 35 连击 → 暗队 Fever 获得量
PIERCING_INDEXES = (8, 9)             # 队长 L#8/L#9：贯穿每累计 2 秒 → 暗队攻击力 / 直击伤害
STRENGTH_COLUMNS = (49, 50)           # 队长 instant_content 强度两格（能力表 c51/c52 −2）

#: 每处成长：(队长行号, 原值, 第二批值, 本轮值, 档位, 取整说明)。强度单位 1000 = 1%。
GROWTH = (
    (FEVER_GAIN_INDEX, 20_000, 2_000, 15_000, "4/5",
     "20×4/5=16，就近取 5 的倍数 15%（实际 0.75）"),
    (PIERCING_INDEXES[0], 10_000, 1_000, 7_000, "2/3",
     "10×2/3=6.67，向上取 7%（实际 0.7；原值 ≤10%，5 的倍数只剩 5%/10%，改取整数）"),
    (PIERCING_INDEXES[1], 10_000, 1_000, 7_000, "2/3",
     "同 L#8（攻击力与直击伤害同一触发、同一档位）"),
)

_COMMON = {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: "Black", 18: "0",
           37: "(None)", 44: "0", 46: "5", 47: "Black"}
#: 三行改前（= 第二批发布后 live）的全部非空格；本轮只改 c49/c50。
FEVER_GAIN_ROW = {**_COMMON, 11: "0", 25: "12", 28: "3500000", 29: "3500000", 32: "(None)", 33: "0",
                  45: "50", 49: "2000", 50: "2000"}
PIERCING_ROW = {**_COMMON, 11: "12", 25: "235", 28: "100000", 29: "100000", 30: "12000000", 31: "12000000",
                32: "(None)", 33: "0", 49: "1000", 50: "1000"}
#: 能力3 行3/行4（0 基 2/3）封顶版：只读核对（口径 D4 保持第二批值）。
A3_CAPPED = {2: ("32", "10", "5000"), 3: ("33", "10", "10000")}

OLD_FEVER_GAIN_LINE = "暗属性共鸣时，每达成35连击，暗属性角色获得的 Fever 槽上升量+2%。"
NEW_FEVER_GAIN_LINE = "暗属性共鸣时，每达成35连击，暗属性角色获得的 Fever 槽上升量+15%。"
OLD_PIERCING_LINE = ("暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，"
                     "暗属性角色攻击力+1%、直接攻击伤害+1%。")
NEW_PIERCING_LINE = ("暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，"
                     "暗属性角色攻击力+7%、直接攻击伤害+7%。")
LEADER_TEXT_LINES = 9
PIERCING_LINE_INDEX = 8
FORBIDDEN_PANEL_PHRASES = ("自身为队长时", "觉醒后", "生命值100%以下", "／",
                           "无上限", "无限叠加", "不设上限", "可无限", "属性共鸣时：",
                           "强化后")          # 技能强化文案：强化条目写「强化『技能名』：…」，不写「强化后的技能…」

# ---------------------------------------------------------------- 面板同条件合并 / 共鸣省略

A2 = CID + "2"
TEXT_A2 = "desc_override_" + CODE + "_2"
#: 队长块第4行（L#2 直击 400% + L#3 攻击 200%）与第6行（L#5 Fever 时间 100%）：同一数据条件（暗共鸣常驻）。
LEADER_ATTACK_LINE = "暗属性共鸣时，暗属性角色攻击力+200%、直接攻击伤害+400%。"
LEADER_FEVER_TIME_LINE = "暗属性共鸣时，Fever 时间+100%。"
LEADER_MERGED_LINE = "暗属性共鸣时，暗属性角色攻击力+200%、直接攻击伤害+400%，Fever 时间+100%。"
LEADER_MERGE_LINES = (3, 5)           # 面板行（0 基）：合并行放在第4行，第6行删去
LEADER_MERGE_ROWS = (2, 3, 5)         # 队长数据行（0 基）
MERGED_LEADER_TEXT_LINES = 8
#: 技能强化文案（作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,
#: 规范并简化描述做了吗」；主会话口径 R2）：同一条 I536 强化（队长 L#1，暗共鸣）面板拆成第2、3行（第3行还写「强化后的
#: 技能发动时」）⇒ 并成一行 =「暗属性共鸣时，」+ 条目 change_skill_ruin_girl_campus_fever 原文（条目本身已合规，只读不改）。
CHANGE_SKILL_TEXT = ("强化『午后星轨·甜蜜续杯』：额外赋予暗属性角色及协力球攻击力提升效果；"
                     "Fever 模式中发动时，自身获得或刷新「星夜茶会」，并赋予暗属性角色及协力球护盾")
SKILL_NAME = "午后星轨·甜蜜续杯"
ENHANCEMENT_OLD_LINES = (
    "暗属性共鸣时，强化『午后星轨·甜蜜续杯』：额外赋予暗属性角色及协力球攻击力提升效果。",
    "暗属性共鸣时，Fever 模式中，强化后的技能发动时，自身获得或刷新「星夜茶会」，并赋予暗属性角色及协力球护盾。",
)
ENHANCEMENT_LINE = "暗属性共鸣时，" + CHANGE_SKILL_TEXT + "。"
ENHANCEMENT_LINE_INDEX = 1            # 面板第2行（0 基 1）；原第2、3行
FINAL_LEADER_TEXT_LINES = 7
OLD_A2_LINES = (
    "暗属性共鸣时，全队贯穿效果时间+40%。",
    "暗属性共鸣时，暗属性角色直接攻击伤害+250%。",
    "暗属性共鸣时，Fever 模式中，暗属性角色技能槽上限+10%。",
)
NEW_A2_LINES = (
    "暗属性共鸣时，全队贯穿效果时间+40%，暗属性角色直接攻击伤害+250%。",
    "暗属性共鸣时，Fever 模式中，暗属性角色技能槽上限+10%。",
)
A2_MERGE_ROWS = (0, 1)                # 能力2 数据行（0 基）
#: 同条件的判据：组内各行除「效果列」外逐格相同（前置三块、触发与参数、CT、次数上限、c1 主位、觉醒列、效果后缀列）。
#: 效果列 = instant 内容块 kind/对象/对象元素/强度（能力 c47–c52、队长 c45–c50）与 during 内容块同位。
EFFECT_COLUMNS = {"ability": frozenset(range(47, 53)) | frozenset(range(109, 115)),
                  "leader_ability": frozenset(range(45, 51)) | frozenset(range(107, 113))}

# ---------------------------------------------------------------- 共鸣省略（口径 6：星夜茶会只经带暗共鸣的旗号获得）

A1 = CID + "1"
TEXT_A1 = "desc_override_" + CODE + "_1"
ABILITY_KEYS = tuple(CID + str(slot) for slot in range(1, 7))
RESONANCE_PREFIX = "暗属性共鸣时，"
OLD_A1_LINES = (
    MAIN_ICON + "战斗开始时，自身技能槽+50%。",
    MAIN_ICON + "暗属性共鸣时，Fever 模式中，持有「星夜茶会」时，每经过2秒交替召唤1个光、暗属性协力球，各持续25秒且无法回复"
                "生命值，协力球最多同时存在9个；再次发动技能不会延长已有协力球的存在时间。",
    MAIN_ICON + "暗属性共鸣时，Fever 模式中，持有「星夜茶会」时，协力球已达9个时，该次召唤改为自身攻击力+25%，持续20秒，可叠加。",
    MAIN_ICON + "Fever 结束或自身倒下时，「星夜茶会」解除。",
)
NEW_A1_LINES = (
    MAIN_ICON + "战斗开始时，自身技能槽+50%。",
    MAIN_ICON + "Fever 模式中，持有「星夜茶会」时，每经过2秒交替召唤1个光、暗属性协力球，各持续25秒且无法回复"
                "生命值，协力球最多同时存在9个；再次发动技能不会延长已有协力球的存在时间。",
    MAIN_ICON + "Fever 模式中，持有「星夜茶会」时，协力球已达9个时，该次召唤改为自身攻击力+25%，持续20秒，可叠加。",
    MAIN_ICON + "Fever 结束或自身倒下时，「星夜茶会」解除。",
)
#: 键 = 面板键，值 = 删「暗属性共鸣时，」的面板行号（1 起；只删前缀，其余逐字）。
PREFIX_DROPS = {TEXT_A1: (2, 3)}
#: 省略共鸣的面板行 → 数据行（0 基）：两行都是能力1 #1（持有星夜茶会 KeepFrame 触发 232 → 629 fever_spawn；
#: 溢出改攻击力那段在 fever_spawn 树里、同在「持有星夜茶会」分支下）。
OMITTED_ROWS = {TEXT_A1: (("ability", A1, 1),)}

STATE_UID = 16998901                  # 固有「星夜茶会」
STATE_SOURCE_PROGRAMS = tuple(f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in (1, 2))
RESONANCE_CONDITIONAL = "ConditionalsUnifyElement"
SKILL_FLAG = 1                        # 536 = ChangeSkillFlag ⇒ 旗号 1（704–708 ⇒ 旗号 2–6）
SKILL_FLAG_KINDS = ("536", "704", "705", "706", "707", "708")
FLAG_ROW = 1                          # 队长 L#1
#: 队长 L#1 的全部非空格（其余列必须为空）：暗编成≥6（前置块 1：kind 2、600000、Black）、无触发、536 → 换形条目串。
FLAG_CELLS = {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: "Black", 11: "0", 18: "0", 25: "0",
              37: "(None)", 44: "0", 45: "536", 68: CHANGE_SKILL_STRING_ID}
#: 本角色行里调起的 629 程序（能力/队长表 c71/c69）与 722 PF 覆盖（c82/c80）三档——都要读进来查授予点。
INVOKED_PROGRAMS = tuple(f"battle/action/skill/action/ability_skill/{CODE}${CODE}_{name}"
                         for name in ("ball_hit_count", "fever_spawn", "multiball_direct", "multiball_direct_a4"))
SPAWN_PROGRAM = INVOKED_PROGRAMS[1]
PF_OVERRIDE_KEY = CODE + "_fever"
PF_OVERRIDE_PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_OVERRIDE_KEY}${PF_OVERRIDE_KEY}_lv{n}"
                             for n in (1, 2, 3))
BASIS_PROGRAMS = STATE_SOURCE_PROGRAMS + INVOKED_PROGRAMS + PF_OVERRIDE_PROGRAMS
#: 表内列布局（同 wf_balance_20260927c_magnus._LAYOUT）：前置三块、瞬发触发、触发前置、瞬发内容、持续触发/内容。
LAYOUT = {
    "leader": dict(pre=(4, 11, 18), it=25, ipc=37, ic=45, dat=83, dt=95, dc=107),
    "ability": dict(pre=(6, 13, 20), it=27, ipc=39, ic=47, dat=85, dt=97, dc=109),
}
GRANT_KINDS = ("461", "413", "436", "459")           # 付与固有状态
REMOVE_KINDS = ("525", "528")                         # 消耗 / 删除固有状态
PRE_UNIQUE = ("144", "187", "188", "199")             # 前置块按固有状态判定
DT_UNIQUE = ("134", "194", "207", "171", "192")       # 持续触发按固有状态计数
IT_UNIQUE = ("232",)                                  # 瞬发触发：持有固有状态 KeepFrame

#: live 链尾 1.4.1053 输入基线（2026-09-27 只读导出，stage_batch.make_read(live_only=True)）；任一不符 ⇒ 拒绝。
BEFORE = {
    ("leader", CID): "14556aeaeb32cd2651063b9997daf459c0674fcb29a8291cd4b0654930458ec9",
    ("cas", TEXT_LEADER): "2866db0da0dde48ea775e11e4e3537fa0d541237dbd9ef3416ab3e4d4bda489a",
    # 只读：能力3 封顶版（口径 D4 不动）与搬行原像核对。
    ("ability", A3): "9476a36414e97d2da8aac2c64dc976b22446c8c9c1dc3ff05f010d337330027b",
    # 只读：队长 I536 / I722 / I629 行的文案键（门禁要求 live 有同键行），不改。
    ("cas", CHANGE_SKILL_STRING_ID): "0d967429bc2adeef5ed12f67863d6492cfe7e08cd04968475d9ba56e7cbf4ed4",
    ("cas", PF_STRING_ID): "1e23cda7f5c6b06be276398ca7b52891ac751faa11ab75e276cdbe4e95ff05c0",
    ("cas", BALL_HIT_STRING_ID): "ea0d1d398be6943e4e0d4b4a48a1bf7e2860a3b225649a51d6e29d035e18edc1",
    # 面板同条件合并（链尾 1.4.1054 只读取数，与两个候选逐字相同）：能力2 行只读（核对合并组数据条件），面板改写。
    ("ability", A2): "b728e05f72f174a678c3b93d7aa79f4792f0e961e14a77ab2533223d65b7b8ad",
    ("cas", TEXT_A2): "5e940718becb5d56ca85b4f8f0ce85625b95c04ac4bea84f4fe0dc1fb6925251",
    # 共鸣省略（口径 6，链尾 1.4.1054 只读取数）：能力1 面板改写；其余只读——能力 1/4/5/6 行（连同上面的队长、
    # 能力2/3 凑齐全部旗号 / 授予来源）、action_skill（技能两档程序）、技能两档 + 629 四棵 + PF 覆盖三档 DSL。
    ("cas", TEXT_A1): "481126576039d4b991316d7a3187d2b9a2debac80e641c3dfa888413c80083bc",
    ("ability", A1): "8c0dfd7a49da96d8855cde1ed522db406554678281df9f0917cb410fe97e77ad",
    ("ability", CID + "4"): "58abeedf55168c96b3883c60e881b1deaa90fa4106742a9e80970b8ac4fd8caf",
    ("ability", CID + "5"): "a30ce4cadd194a72061a32dfb2625af74e1349364510f78239c374bccf2b6669",
    ("ability", CID + "6"): "3c06d4e30811217d5c7df8f4596d3a01b253199427f87c3d282e5ceea7b08153",
    ("action", CODE): "4daffd5914c0862277a751b3a2abdc4888eef026cc3a1706e6fa296ae5acfaf4",
    ("dsl", STATE_SOURCE_PROGRAMS[0]): "9068168dd7b8fc27734f0d2020bf6d9ab576792bb08b3e5ac8ff2f751ee9c2f7",
    ("dsl", STATE_SOURCE_PROGRAMS[1]): "9068168dd7b8fc27734f0d2020bf6d9ab576792bb08b3e5ac8ff2f751ee9c2f7",
    ("dsl", INVOKED_PROGRAMS[0]): "ccd840bc13cc2dba23fccf9a79546e219a4edf115039a161b2359afeb79010cb",
    ("dsl", INVOKED_PROGRAMS[1]): "726760d4d684498bf27b4e3f5be71f3aa7377746025f3a1c2e1f3ecc349142a5",
    ("dsl", INVOKED_PROGRAMS[2]): "9749cb3588435bee2f4a6519d1557a5d0502fee081d8f87f37a7bb91a28ff23d",
    ("dsl", INVOKED_PROGRAMS[3]): "27b10df833be1a66872210eb0836e8fb1ee907782bfa6633871bd08d07942890",
    ("dsl", PF_OVERRIDE_PROGRAMS[0]): "5f5e2ed2c71120ade12cc006f25d996a2974d8756146b8a53dd5b93267e685b9",
    ("dsl", PF_OVERRIDE_PROGRAMS[1]): "644e2f2b724758a9824ea5ff7abbe80e59511ed3770372935fbc180b0db39751",
    ("dsl", PF_OVERRIDE_PROGRAMS[2]): "5e93b23f34c53121cefab50d9b4c7139b967324095fd0e417ea2930402c5f2a4",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(f"{CID} balance 20260927c: {message}")


def _nonempty(row):
    return {i: v for i, v in enumerate(row) if v != ""}


def _text(rows, key):
    _require(len(rows) == 1 and len(rows[0]) == 1 and isinstance(rows[0][0], str),
             f"{key}: expected one text cell")
    return rows[0][0]


def _preimage(index):
    if index == FEVER_GAIN_INDEX:
        return FEVER_GAIN_ROW
    return {**PIERCING_ROW, 45: LEADER_KINDS[index]}


def check_ability3(rows):
    """口径 D4：能力3 封顶版保持第二批值（攻击 +5%、直击 +10%，各最多 10 次）；只读核对，不返回。"""
    _require(len(rows) == 6 and all(len(row) == 126 for row in rows), "ability3: expected 6x126 rows")
    _require({row[1] for row in rows} == {"false"}, "ability3 must stay main-only")
    for index, (content, limit, strength) in A3_CAPPED.items():
        row = rows[index]
        _require((row[27], row[34], row[47], row[51], row[52]) == ("235", limit, content, strength, strength),
                 f"ability3 row{index + 1}: capped batch-2 values drifted")


def leader_rows(rows, a3_rows):
    """队长十行：L#4 Fever 获得量成长 2%→15%，L#8/L#9 贯穿成长 1%→7%；其余七行与这三行的其余格逐字不动。"""
    _require(isinstance(rows, list) and len(rows) == 10 and all(len(row) == 124 for row in rows),
             "leader: expected 10x124 rows (batch-2 layout)")
    _require([row[45] for row in rows] == LEADER_KINDS, "leader kinds drifted from the batch-2 layout")
    result = deepcopy(rows)
    for index, _original, before, after, _band, _rounding in GROWTH:
        got = _nonempty(rows[index])
        _require(got == _preimage(index), f"unexpected preimage for leader row{index} (L#{index}): {got}")
        result[index][STRENGTH_COLUMNS[0]] = result[index][STRENGTH_COLUMNS[1]] = str(after)
        _require(str(before) == rows[index][STRENGTH_COLUMNS[0]], f"leader row{index}: before strength drift")
    # 搬行一致性：L#8/L#9 仍是能力3 行3/行4 的同形行（[CODE,'0',''] + 能力行[5:]），只差限次与强度。
    for index, a3_index in zip(PIERCING_INDEXES, (2, 3)):
        formula = [CODE, "0", ""] + list(a3_rows[a3_index][5:])
        diff = [c for c in range(124) if formula[c] != result[index][c]]
        _require(diff == [32, 49, 50], f"leader row{index}: no longer the moved copy of ability3 row{a3_index + 1}")
    changed = [(i, c) for i in range(10) for c in range(124) if rows[i][c] != result[i][c]]
    _require(changed == [(i, c) for i, *_rest in sorted(GROWTH) for c in STRENGTH_COLUMNS],
             f"leader_rows touched unexpected cells: {changed}")
    return result


def leader_numbers_text(text):
    """成长复核：第5行与末行只换数字；其余七行逐字不动（合并前的中间态，check_merge 的原文）。"""
    lines = text.split("\n")
    _require(len(lines) == LEADER_TEXT_LINES and lines[FEVER_GAIN_INDEX] == OLD_FEVER_GAIN_LINE
             and lines[PIERCING_LINE_INDEX] == OLD_PIERCING_LINE, "unexpected leader panel lines")
    lines[FEVER_GAIN_INDEX] = NEW_FEVER_GAIN_LINE
    lines[PIERCING_LINE_INDEX] = NEW_PIERCING_LINE
    return "\n".join(lines)


def merge_leader_text(text):
    """同条件合并：第4行（攻击 200%、直击 400%）与第6行（Fever 时间 100%）并成一行放在第4行；其余行逐字不动。"""
    lines = text.split("\n")
    first, second = LEADER_MERGE_LINES
    _require(len(lines) == LEADER_TEXT_LINES and lines[first] == LEADER_ATTACK_LINE
             and lines[second] == LEADER_FEVER_TIME_LINE, "unexpected leader panel lines before the merge")
    lines[first] = LEADER_MERGED_LINE
    del lines[second]
    return "\n".join(lines)


def merge_enhancement_text(text):
    """技能强化文案（R2）：同一条 I536 强化的第2、3行并成一行 =「暗属性共鸣时，」+ 条目原文（8 行 → 7 行）；其余行逐字。"""
    lines = text.split("\n")
    first = ENHANCEMENT_LINE_INDEX
    _require(len(lines) == MERGED_LEADER_TEXT_LINES
             and tuple(lines[first:first + len(ENHANCEMENT_OLD_LINES)]) == ENHANCEMENT_OLD_LINES,
             "unexpected leader panel enhancement lines")
    lines[first:first + len(ENHANCEMENT_OLD_LINES)] = [ENHANCEMENT_LINE]
    return "\n".join(lines)


def leader_text(text):
    """live 队长面板 → 本轮输出：先同步两处数字，再做同条件合并（9 行 → 8 行），最后把同一条 I536 强化的两行
    并成一行（8 行 → 7 行，技能强化文案）。"""
    return merge_enhancement_text(merge_leader_text(leader_numbers_text(text)))


def ability2_text(text):
    """能力2 同条件合并：第1行（贯穿延长 40%）与第2行（暗队直击 250%）并成一行；Fever 中技能槽上限那行不动。"""
    _require(tuple(text.split("\n")) == OLD_A2_LINES, f"{TEXT_A2}: unexpected panel lines")
    return "\n".join(NEW_A2_LINES)


def drop_resonance_prefixes(lines, line_numbers):
    """只删指定行（1 起）行首（主位图标之后）的「暗属性共鸣时，」，其余字面逐字不动。"""
    out = []
    for number, line in enumerate(lines, 1):
        if number in line_numbers:
            body = line[len(MAIN_ICON):] if line.startswith(MAIN_ICON) else line
            _require(body.startswith(RESONANCE_PREFIX), f"line {number} has no resonance prefix to drop: {line!r}")
            line = line[:len(line) - len(body)] + body[len(RESONANCE_PREFIX):]
        out.append(line)
    return tuple(out)


def ability1_text(text):
    """能力1 共鸣省略（口径 6）：第2、3行删「暗属性共鸣时，」；其余逐字（依据见 :func:`resonance_omission_problems`）。"""
    _require(tuple(text.split("\n")) == OLD_A1_LINES, f"{TEXT_A1}: unexpected panel lines")
    _require(drop_resonance_prefixes(OLD_A1_LINES, PREFIX_DROPS[TEXT_A1]) == NEW_A1_LINES,
             f"{TEXT_A1}: NEW_A1_LINES is not OLD_A1_LINES minus the registered prefixes")
    return "\n".join(NEW_A1_LINES)


# ---------------------------------------------------------------- 共鸣省略依据（fail closed）

def _is_uid(value, uid=STATE_UID):
    return type(value) in (int, float) and value == uid


def table_uid_roles(row, table, uid=str(STATE_UID)):
    """该行里写着星夜茶会固有号的每一格：depends（按持有/层数生效）/ remove（消耗、删除）/ grant（付与）/ unknown。"""
    layout = LAYOUT[table]
    roles = []
    for col, value in enumerate(row):
        if value.strip() != uid:
            continue
        if any(col == base + 6 and row[base].strip() in PRE_UNIQUE for base in layout["pre"]):
            role = "depends"
        elif col == layout["it"] + 10 and row[layout["it"]].strip() in IT_UNIQUE:
            role = "depends"
        elif col == layout["dt"] + 7 and row[layout["dt"]].strip() in DT_UNIQUE:
            role = "depends"
        elif col == layout["ic"] + 21 and row[layout["ic"]].strip() in GRANT_KINDS:
            role = "grant"
        elif col == layout["ic"] + 21 and row[layout["ic"]].strip() in REMOVE_KINDS:
            role = "remove"
        else:
            role = "unknown"
        roles.append((col, role))
    return roles


def skill_flag_rows(leader, abilities):
    """本角色全部技能旗号行（536/704–708，瞬发或持续内容）：[(表, 键, 行号)]。"""
    found = []
    for table, key, rows in (("leader", CID, leader), *(("ability", k, abilities.get(k) or []) for k in ABILITY_KEYS)):
        layout = LAYOUT[table]
        found += [(table, key, i) for i, row in enumerate(rows)
                  if row[layout["ic"]] in SKILL_FLAG_KINDS or row[layout["dc"]] in SKILL_FLAG_KINDS]
    return found


def dsl_state_uses(tree, uid=STATE_UID):
    """DSL 里星夜茶会固有号的每处出现：[(role, 祖先链)]。role = grant（ACUnique）/ read（DCUnique）/
    consume（ConsumeUniqueCondition）/ unknown；祖先链 = ((命令名, 参数位, 参数表), …)，外 → 内。"""
    uses = []

    def walk(node, ancestors):
        if isinstance(node, list):
            if (len(node) == 2 and node[0] == "Command" and isinstance(node[1], list) and node[1]
                    and isinstance(node[1][0], str)):
                args = node[1]
                name = args[0]
                consume = name == "ConsumeUniqueCondition" and len(args) > 2 and _is_uid(args[2], uid)
                if consume:
                    uses.append(("consume", tuple(ancestors)))
                for index, arg in enumerate(args[1:], 1):
                    if not (consume and index == 2):
                        walk(arg, ancestors + [(name, index, args)])
                return
            if len(node) >= 2 and node[0] in ("ACUnique", "DCUnique") and _is_uid(node[1], uid):
                uses.append(("grant" if node[0] == "ACUnique" else "read", tuple(ancestors)))
                for item in node[2:]:
                    walk(item, ancestors)
                return
            for item in node:
                walk(item, ancestors)
        elif isinstance(node, dict):
            for item in node.values():
                walk(item, ancestors)
        elif _is_uid(node, uid):
            uses.append(("unknown", tuple(ancestors)))

    walk(tree, [])
    return uses


def _within(ancestors, name, index, test):
    return any(n == name and i == index and test(args) for n, i, args in ancestors)


def in_flag_branch(ancestors):
    """位于 ``ConditionalsChangeSkillFlag(1)`` 的开支（第 2 参）里。"""
    return _within(ancestors, "ConditionalsChangeSkillFlag", 2, lambda args: args[1] == SKILL_FLAG)


def in_holding_branch(ancestors):
    """位于 ``ConditionalsConditionExist(-17, DCUnique 星夜茶会)`` 的「持有」支（第 3 参）里。"""
    return _within(ancestors, "ConditionalsConditionExist", 3,
                   lambda args: args[1] == -17 and args[2] == ["DCUnique", STATE_UID])


def resonance_omission_problems(leader, abilities, action, trees):
    """口径 6 的依据（空 = 成立）：星夜茶会只能经带暗共鸣的技能旗号分支获得。

    1. 旗号来源唯一且带暗共鸣：本角色队长 / 能力 1–6 里的技能旗号行（536/704–708）只有队长 L#1，且逐格是
       「暗编成≥6 → 536」（旗号 1）。
    2. 表内没有授予：各行写着星夜茶会的格只有「按持有生效」「消耗 / 删除」。
    3. 授予点全读到：行里调起的 629 程序都在 :data:`INVOKED_PROGRAMS`，PF 覆盖只有 :data:`PF_OVERRIDE_KEY` 三档，
       技能两档（action_skill c7）= :data:`STATE_SOURCE_PROGRAMS`；fever_spawn 只由能力1 #1 调起。
    4. DSL：授予（ACUnique）只在技能两档、且都在 ``ConditionalsChangeSkillFlag(1)`` 开支里（每档至少一处）；
       ConsumeUniqueCondition 只在「持有星夜茶会」支里；其余只许 DCUnique 读取，认不出的引用一律报错。
    5. 省略共鸣的面板行对应的数据行（:data:`OMITTED_ROWS`）确实按「持有星夜茶会」触发。
    """
    problems = []
    tables = [("leader", CID, leader)] + [("ability", key, abilities.get(key) or []) for key in ABILITY_KEYS]
    flags = skill_flag_rows(leader, abilities)
    if flags != [("leader", CID, FLAG_ROW)]:
        problems.append(f"skill-flag rows {flags} != [leader:{CID}#{FLAG_ROW}] (flag source must be unique)")
    flag_row = leader[FLAG_ROW] if len(leader) > FLAG_ROW else []
    if _nonempty(flag_row) != FLAG_CELLS:
        problems.append(f"leader L#{FLAG_ROW} is not the reviewed dark-resonance 536 row: {_nonempty(flag_row)}")
    invoked = {}
    for table, key, rows in tables:
        layout = LAYOUT[table]
        ic, dc = layout["ic"], layout["dc"]
        for index, row in enumerate(rows):
            label = f"{table}:{key}#{index}"
            for col, role in table_uid_roles(row, table):
                if role not in ("depends", "remove"):
                    problems.append(f"{label} c{col}: 星夜茶会 {role} outside the skill-flag branch")
            if row[ic] == "629":
                invoked.setdefault(row[ic + 24], []).append((table, key, index))
            if row[dc] == "629":
                problems.append(f"{label}: during-content 629 not reviewed")
            for col in (ic + 35, dc + 11):
                if row[col] not in ("", "(None)") and row[col] != PF_OVERRIDE_KEY:
                    problems.append(f"{label}: PF override {row[col]!r} not read")
    unread = sorted(set(invoked) - set(INVOKED_PROGRAMS))
    if unread:
        problems.append(f"629 programs not read: {unread}")
    if invoked.get(SPAWN_PROGRAM) != [("ability", A1, 1)]:
        problems.append(f"fever_spawn callers {invoked.get(SPAWN_PROGRAM)} != [ability:{A1}#1]")
    skill_programs = sorted(fields[7] if len(fields) > 7 else None for _inner, fields in action)
    if skill_programs != sorted(STATE_SOURCE_PROGRAMS):
        problems.append(f"action_skill programs {skill_programs} != reviewed {list(STATE_SOURCE_PROGRAMS)}")
    for program in BASIS_PROGRAMS:
        if program not in trees:
            problems.append(f"{program}: tree not read")
            continue
        uses = dsl_state_uses(trees[program])
        if program in STATE_SOURCE_PROGRAMS and not any(role == "grant" for role, _a in uses):
            problems.append(f"{program}: no 星夜茶会 grant left (acquisition moved; re-review)")
        for role, ancestors in uses:
            chain = [name for name, _i, _args in ancestors if name.startswith("Conditionals")]
            if role == "grant" and not (program in STATE_SOURCE_PROGRAMS and in_flag_branch(ancestors)):
                problems.append(f"{program}: 星夜茶会 granted outside ConditionalsChangeSkillFlag({SKILL_FLAG}) {chain}")
            elif role == "consume" and not in_holding_branch(ancestors):
                problems.append(f"{program}: ConsumeUniqueCondition outside the holding branch {chain}")
            elif role == "unknown":
                problems.append(f"{program}: unrecognised 星夜茶会 reference {chain}")
    for _key, refs in OMITTED_ROWS.items():
        for table, key, index in refs:
            rows = leader if table == "leader" else abilities.get(key) or []
            row = rows[index] if index < len(rows) else None
            layout = LAYOUT[table]
            if (row is None or (layout["it"] + 10, "depends") not in table_uid_roles(row, table)
                    or row[layout["ic"]] != "629" or row[layout["ic"] + 24] != SPAWN_PROGRAM):
                problems.append(f"{table}:{key}#{index}: omitted-resonance line no longer maps to the "
                                f"holding-gated fever_spawn row")
    return problems


def merge_condition_problems(table, rows, indexes):
    """合并组内各行除效果列外必须逐格相同；返回不同的列（空 = 数据条件完全相同）。"""
    effect = EFFECT_COLUMNS[table]
    if any(i >= len(rows) for i in indexes):
        return [f"merge group {indexes} out of range ({len(rows)} rows)"]
    first = rows[indexes[0]]
    problems = []
    for index in indexes[1:]:
        row = rows[index]
        diff = [col for col in range(max(len(first), len(row)))
                if col not in effect and (first[col] if col < len(first) else None)
                != (row[col] if col < len(row) else None)]
        if diff:
            problems.append(f"rows #{indexes[0]}/#{index} differ outside the effect columns: {diff}")
    return problems


def state_grant_chains(tree, uid=STATE_UID):
    """DSL 里给固有 ``uid`` 的 ACUnique 授予节点 → 各自的祖先 Conditionals 名链（共鸣省略依据用）。"""
    chains = []

    def walk(node, ancestors):
        if isinstance(node, list):
            if len(node) > 1 and node[0] == "Command" and isinstance(node[1], list):
                args = node[1]
                name = args[0]
                if name == "CreateCondition" and len(args) > 2 and isinstance(args[2], list):
                    for entry in args[2]:
                        if isinstance(entry, list) and entry and entry[0] == "ACUnique" and int(entry[1]) == uid:
                            chains.append(list(ancestors))
                inner = ancestors + [name] if name.startswith("Conditionals") else ancestors
                for arg in args[1:]:
                    walk(arg, inner)
                return
            for item in node:
                walk(item, ancestors)
        elif isinstance(node, dict):
            for item in node.values():
                walk(item, ancestors)

    walk(tree, [])
    return chains


def _row_problems(row, strings):
    table = "leader_ability"
    problems = (legality.client_legality_problems(table, row)
                + legality.declared_block_field_problems(table, row)
                + legality.ability_element_column_problems(table, row, DARK_ELEMENT)
                + legality.invoke_skill_string_problems(row, strings, table))
    kind = row[45]
    if kind in ("536", "722"):
        key = row[82 if kind == "722" else 68]
        if key not in strings:
            problems.append(f"missing native ability description {key!r}")
    return problems


#: 仅主位的面板（能力1 c1 = false）：每行必须自带主位图标；其余面板一行都不许带。
MAIN_ONLY_TEXTS = (TEXT_A1,)


def panel_problems(key, text):
    problems = [f"{key}: forbidden phrase {p!r}" for p in FORBIDDEN_PANEL_PHRASES if p in text]
    problems += [f"{key}: {p}" for p in kit_panel_problems(text)]
    if "\\n" in text:
        problems.append(f"{key}: literal backslash-n")
    lines = text.split("\n")
    if key in MAIN_ONLY_TEXTS:
        if not all(line.startswith(MAIN_ICON) for line in lines):
            problems.append(f"{key}: main-only panel must carry the main icon on every line")
    elif any(line.startswith(MAIN_ICON) for line in lines):
        problems.append(f"{key}: unrestricted panel must not carry the main icon")
    return problems


def validate(result, strings):
    problems = []
    for key, rows in result["leader"].items():
        for index, row in enumerate(rows):
            problems += [f"leader_ability:{key}#{index} {p}" for p in _row_problems(row, strings)]
    for key, rows in result["cas"].items():
        problems += panel_problems(key, _text(rows, key))
    needed = set()
    for rows in result["leader"].values():
        for row in rows:
            needed |= set(legality.required_client_capabilities("leader_ability", row))
    for key in result["cas"]:
        needed |= set(legality.required_client_capabilities(legality.CUSTOM_ABILITY_STRING_KIND, [key]))
    if needed != set(CAPABILITIES):
        problems.append(f"capabilities {sorted(needed)} != declared {CAPABILITIES}")
    return problems


def revise(read):
    inputs = {}
    for (kind, key), expected in BEFORE.items():
        value = deepcopy(read(kind, key))
        if digest(value) != expected:
            raise ValueError(f"{CID} balance 20260927c: live drift at {kind}:{key}; re-review before revising")
        inputs[kind, key] = value
    a3 = inputs["ability", A3]
    check_ability3(a3)
    leader = leader_rows(inputs["leader", CID], a3)
    # 面板同条件合并：先按数据核对组内条件逐格相同（队长用本轮输出行），再改写面板。
    found = (merge_condition_problems("leader_ability", leader, LEADER_MERGE_ROWS)
             + merge_condition_problems("ability", inputs["ability", A2], A2_MERGE_ROWS))
    _require(not found, f"merge groups are not one data condition: {found}")
    # 共鸣省略（口径 6）：按改后数据核对「星夜茶会只经带暗共鸣的旗号分支获得」，不成立 ⇒ 拒绝。
    basis = resonance_omission_problems(
        leader, {key: inputs["ability", key] for key in ABILITY_KEYS}, inputs["action", CODE],
        {program: inputs["dsl", program] for program in BASIS_PROGRAMS})
    _require(set(PREFIX_DROPS) == {TEXT_A1} and not basis,
             f"resonance-prefix omission basis drifted (re-review): {basis}")
    # 技能强化文案（R2）：条目原文 == 复核稿且合规（官方格式、点明技能名、定性无数字、不写条件）；开关行 = 队长 L#1 的
    # 暗共鸣 536（c68 = 本串，上面 resonance_omission_problems 已逐格核对 FLAG_CELLS）。
    flag_text = _text(inputs["cas", CHANGE_SKILL_STRING_ID], CHANGE_SKILL_STRING_ID)
    _require(flag_text == CHANGE_SKILL_TEXT, f"{CHANGE_SKILL_STRING_ID}: live entry differs from the reviewed text")
    _require(FLAG_CELLS[68] == CHANGE_SKILL_STRING_ID and not kit_panel_problems(flag_text, skill_flag=True)
             and flag_text.startswith(f"强化『{SKILL_NAME}』") and "属性共鸣时" not in flag_text,
             f"{CHANGE_SKILL_STRING_ID}: entry is not in the official qualitative format")
    cas = {TEXT_LEADER: [[leader_text(_text(inputs["cas", TEXT_LEADER], TEXT_LEADER))]],
           TEXT_A2: [[ability2_text(_text(inputs["cas", TEXT_A2], TEXT_A2))]],
           TEXT_A1: [[ability1_text(_text(inputs["cas", TEXT_A1], TEXT_A1))]]}
    result = {"ability": {}, "leader": {CID: leader}, "cas": cas,
              "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
              "new_programs": []}
    strings = {key for kind, key in inputs if kind == "cas"} | set(cas)
    problems = validate(result, strings)
    if problems:
        raise ValueError("; ".join(problems))
    result["notes"] = notes()
    return result


def _pct(strength):
    value = strength / 1000
    return f"{int(value)}%" if float(value).is_integer() else f"{value:g}%"


def notes():
    names = {FEVER_GAIN_INDEX: "每35连击 → 暗队 Fever 获得量(I50)",
             PIERCING_INDEXES[0]: "Fever 中贯穿每累计2秒 → 暗队攻击力(I32)",
             PIERCING_INDEXES[1]: "Fever 中贯穿每累计2秒 → 暗队直击伤害(I33)"}
    return {
        "character": f"{CID} {CODE}（校园奈芙提姆）",
        "scope": "2026-09-27 第三轮（c）成长复核：第二批 1/10 回调到作者新口径（4/5、7/10、2/3 三档，数值取 5 的倍数）",
        "changes": [
            {"where": f"leader_ability:{CID} L#{index}（0 起；第二批报告 #{index + 1}）c49/c50",
             "what": names[index],
             "before": f"{before}（{_pct(before)}/次，第二批 1/10；原值 {_pct(original)}）",
             "after": f"{after}（{_pct(after)}/次，{band} 档：{rounding}）"}
            for index, original, before, after, band, rounding in GROWTH
        ] + [{"where": f"custom_ability_string:{TEXT_LEADER}",
              "before": "第5行 Fever 槽上升量+2%；末行 攻击力+1%、直接攻击伤害+1%",
              "after": "第5行 +15%；末行 攻击力+7%、直接攻击伤害+7%"},
             {"where": f"custom_ability_string:{TEXT_LEADER}（面板同条件合并）",
              "before": [LEADER_ATTACK_LINE, LEADER_FEVER_TIME_LINE],
              "after": LEADER_MERGED_LINE,
              "data_rows": f"leader_ability:{CID} L#2/L#3/L#5（暗共鸣常驻；除效果列外逐格相同）",
              "layout": "合并行放在第4行，原第6行删去：9 行 → 8 行，其余行逐字不动"},
             {"where": f"custom_ability_string:{TEXT_LEADER}（技能强化文案，R2）",
              "before": list(ENHANCEMENT_OLD_LINES),
              "after": ENHANCEMENT_LINE,
              "data_rows": f"leader_ability:{CID} L#{FLAG_ROW}（536，旗号 1，暗编成≥6）c68 = {CHANGE_SKILL_STRING_ID}；"
                           "旗号 1 开支：FindAllSubjects(82/86) 攻击力、Fever 中 ConditionalsConditionExist(16998901) 授予"
                           "「星夜茶会」与护盾",
              "rule": "作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,"
                      "规范并简化描述做了吗」；同一条强化的 CAS 与面板对应行写法一致 ⇒ 面板一行 =「暗属性共鸣时，」+ 条目原文"
                      "（条目本身已合规，不改）；不再写「强化后的技能发动时」",
              "layout": "原第2、3行并成第2行：8 行 → 7 行，其余行逐字不动"},
             {"where": f"custom_ability_string:{TEXT_A2}（面板同条件合并）",
              "before": list(OLD_A2_LINES[:2]),
              "after": NEW_A2_LINES[0],
              "data_rows": f"ability:{A2}#0/#1（暗共鸣常驻；除效果列外逐格相同）",
              "layout": "合并行放在第1行，Fever 中技能槽上限那行逐字不动"},
             {"where": f"custom_ability_string:{TEXT_A1}（共鸣省略，口径 6）",
              "before": [OLD_A1_LINES[i - 1] for i in PREFIX_DROPS[TEXT_A1]],
              "after": [NEW_A1_LINES[i - 1] for i in PREFIX_DROPS[TEXT_A1]],
              "data_rows": f"ability:{A1}#1（持有星夜茶会 KeepFrame 触发 232 → 629 fever_spawn；数据前置仍带暗编成≥6，不改）",
              "layout": "第2、3行只删行首「暗属性共鸣时，」，主位图标与其余字面逐字不动；第1、4行逐字"}],
        "panel_merge": {
            "rule": "同一面板里数据条件完全相同的行合并（前置/触发/CT/c1/次数上限/后缀列逐格相同）；"
                    "效果原措辞与数值保留、只省略重复对象名；合并行放在组首行位置",
            "not_merged": {
                TEXT_LEADER: "L#0（强化弹射覆盖）/L#1（技能形态切换）与第4/6行同条件，但是机制行，不并；"
                             "L#8/L#9 本来就是一行",
                f"desc_override_{CODE}_3": "两组（#0/#1、#2/#3）本来就各是一行",
                "其余": "能力1/能力4/能力5/能力6 没有同条件组",
            },
            "resonance_prefix_drops": {
                "result": {TEXT_A1: list(PREFIX_DROPS[TEXT_A1])},
                "rule": "主会话统一口径 6：星夜茶会只能经技能旗号分支获得，旗号唯一来源是带暗共鸣的队长 536 行 ⇒ "
                        "视为获取带暗共鸣，依赖持有星夜茶会的行删「暗属性共鸣时，」",
                "basis": f"「星夜茶会」{STATE_UID} 的 ACUnique 授予只在技能两档 DSL（action_skill c7；switched 语音版同两棵树）"
                         f"的 ConditionalsChangeSkillFlag({SKILL_FLAG}) 开支里（链 ChangeSkillFlag → FeverMode → "
                         f"ConditionExist，本身无 {RESONANCE_CONDITIONAL}）；旗号 {SKILL_FLAG} 的唯一来源 = 队长 L#{FLAG_ROW}"
                         f"（536，暗编成≥6）；队长 / 能力 1–6 无授予行（只有持有触发、187 前置、528 删除）；629 四棵与 "
                         f"PF 覆盖三档无授予（fever_spawn 的 ConsumeUniqueCondition 在「持有」支里，只增减已有层数）",
                "fail_closed": "revise() 用 resonance_omission_problems 按改后数据逐项核对，任一不成立 ⇒ 拒绝",
                "kept": "能力1 第1、4行、队长块、能力2 的「暗属性共鸣时，」都不是依赖持有星夜茶会的效果行，保留",
            },
            "resonance_punctuation": "口径 3：返回的三块面板没有「X属性共鸣时：」，无需规范化",
        },
        "basis": {
            "author": ["成长速度砍到1/10不合理……砍太多了", "砍到4/5，或者7/10这样吧", "可以砍到2/3",
                       "数值尽量取5的倍数"],
            "table": "reeval_full.json table.rows 奈芙提姆两行（已按复核修正：6.5%→7%，不低于 2/3 下限）",
            "piercing": "触发频繁（3 分钟约 38–63 跳，按 50 跳），常驻基础很厚（队长攻击 +200%、直击 +400% 等）→ 取下限 2/3",
            "fever_gain": "暗队 Fever 获得量没有固定来源，只能靠成长 → 4/5；取整后 15%（按 7/10 也落在 15%）",
        },
        "totals_3min_as_leader": {
            "dark_attack_from_piercing": "50 跳：原 +500% / 第二批 +50%+50%（能力3 封顶）/ 本轮 +350%+50%",
            "dark_direct_from_piercing": "50 跳：原 +500% / 第二批 +50%+100% / 本轮 +350%+100%",
            "dark_fever_gain": "60 次：原 +1200% / 第二批 +120% / 本轮 +900%",
        },
        "early_stack_notice": "能力3 封顶版与队长行在前 10 跳叠加：攻击每跳 7%+5%=12%、直击 7%+10%=17%，都高于原值 10%"
                              "（复核表已列出，作者知情项）",
        "unchanged": ["leader 169989 L#0-L#3、L#5-L#7", "ability 1699893（能力3 封顶版，口径 D4）",
                      f"ability {A2}（只读：核对合并组数据条件）",
                      f"ability {A1}/{CID}4/{CID}5/{CID}6、action_skill {CODE}、技能两档 / 629 四棵 / PF 覆盖三档 DSL"
                      "（只读：共鸣省略依据）",
                      f"{TEXT_LEADER} 第1、6-7行（原第1、7-8行）；第3行（原第4行合并行）只并同条件",
                      f"custom_ability_string:{CHANGE_SKILL_STRING_ID}（强化条目已合规，只读）",
                      "技能说明（action_skill 两档 c1 / character_text c5/c7）本来就只写技能本体",
                      "desc_override_ruin_girl_campus_3/_4/_5/_6（无同条件组、数值未变、无依赖星夜茶会的行）",
                      "PF / DSL / action_skill / character_text（不含这些数值）",
                      "共鸣前置：两行本来就带暗共鸣（c4=2），口径 D3 不新增"],
        "generator_sync": ["mod-tools/wf_nephtim_fever_abilities.py LEADER_PIERCING_GROWTH_STRENGTH 1_000→7_000",
                           "mod-tools/wf_nephtim_fever_leader.py FEVER_GAIN_GROWTH_STRENGTH 2_000→15_000",
                           "mod-tools/wf_nephtim_fever_text.py 从上两处真源取数；队长第4/6行与能力2 第1/2行的"
                           "同条件合并已同步（LEADER_BASE_LINE / A2_DIRECT_CLAUSE / _piercing_clause）；"
                           "能力1 第2/3行删共鸣前缀已同步（_TEXTS['a1']）；技能强化两行并一行已同步"
                           "（ENHANCEMENT_LINES =「暗属性共鸣时，」+ CHANGE_SKILL_DESCRIPTION）"],
        "candidate_notes": ["两个候选回写 leader 169989 与 desc_override_ruin_girl_campus / _1 / _2（三键都已在两个候选"
                            "manifest 认领）；无 DSL、无新程序"],
        "runtime_verified": False,
    }

# -*- coding: utf-8 -*-
"""希尔媞·校园 149989 ``wind_spgirl_campus``：2026-09-27 平衡调整第三轮（c）——成长复核 + 技能倍率撤封顶
+ 面板共鸣省略。

依据（主会话施工口径 growth_c_spec.md，作者原话逐字转述）：
「部分角色技能都倍率成长也要无限成长,成长条件放到队长技里面带上对应共鸣条件」「可以砍到2/3」
「数值尽量取5的倍数比如36就变成35,39就变成40」；默认选择 D1（原 25% 的 2/3 档一律取 20%）、
D3（只改表里列出的行的数值）、D4（能力栏封顶版保持第二批）、U5–U8（旗号 2 = I704，开关行放能力1，
非队长 / 不共鸣时保留第二批 10 层，文案格式）。数值表与撤封顶设计见 ``reeval_full.json``
（table.rows 149989 两行、design.characters 149989、critique 两条 minor）。

输入基线 = 当前 live（本地链尾 1.4.1053，= 第二批 ``wf_balance_20260927b_celtie`` 输出逐字；1.4.1054 灰服三角色替换
未碰本角色，原 8 项在 1.4.1054 复核逐字相同，面板合并新增的 7 项在 1.4.1054 取数）。

改动（其余行、树节点逐字保留）：

1. ``leader_ability:149989`` #6 / #7（第二批从能力3 搬入的「每层星风心得 → 风队能力伤害 / 攻击力」，
   during D134，c100 (None)）：c111/c112 2500 → 20000（每层 2.5% → 20%）。原值 25%，按作者「砍到 2/3」
   25×2/3=16.7，「取 5 的倍数」且不得低于 2/3 下限 ⇒ 20%（实际 4/5；17.5% 不是 5 的倍数，口径 D1 取 20%）。
   3 分钟约 50 层：原 1250% / 第二批 125%(+能力3 80%/50%) / 本轮 1000%(+80%/50%)。
2. ``ability:1499891``（能力1，现有技能强化 I536 所在键）末尾追加 I704 开关行（技能旗号 2；口径 U5/U6）：
   瞬发无触发，前置1 = 42（仅队长），前置2 = 风属性 6 人共鸣，c70 = ``change_skill_wind_spgirl_campus_leader``；
   行级 c1='false'，与该键其余行一致（核对 minor：kitlib.check_ability_key 要求一键内 c1 一致；先例凯尔 1399903#4/#5
   的前置42 行 c1 同为 'false'）。同形 live 先例：罗尔夫中秋 1499866#4（I704 + 前置42 + 风共鸣，只差 c0/c1/c70）。
   不写队长表 704 行（官方 / live 队长表零先例，口径 U6）。
3. 技能 DSL 两档（``rare5/wind_spgirl_campus$wind_spgirl_campus_{1,2}``，两档逐字相同）：
   ConditionalsFeverMode → ConditionalsUnifyElement(4, 6) 共鸣支原为
   ``Block[Bind(-17, 14998905, DCUnique 14998902, 1, 10), Block[Event Wait(fallback), FindNear(Boss)]]``，
   改为 ``Block[ConditionalsChangeSkillFlag(2, 开支, 关支)]``：
   关支 = 原共鸣支 Block 本身（逐字）；开支 = 其深拷贝，只把 Bind 上限 10 → 2147483647.0
   （第二批前的值；写 float：AMF3 29 位整数装不下，gerald2 同法）。
   分支在新的局部环境执行（ActionEvaluator.as case 86），Bind 与引用它的路线整段在同一分支内。
   非共鸣支、非 Fever 支（上限 0）不动。旗号 1 仍是能力1 I536 的技能强化，树里 25 处旗号 1 分支不动。
4. 文案（口径 U8，按第 6 项技能强化文案规范定稿）：
   - 新 CAS ``change_skill_wind_spgirl_campus_leader``「强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升」
     （技能强化条目：点名技能、不写数字、不写共鸣前缀）；
   - ``desc_override_wind_spgirl_campus`` 第 6 行 +2.5%/+2.5% → +20%/+20%，末尾追加第 7 行
     「风属性共鸣时，强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升。」（不写数字）——这是数值稿，
     终稿再按第 5 项删第 5–6 行的共鸣前缀（第 7 行是开关行，共鸣保留）；
   - 技能描述 5 处（action_skill 两档 c1、character_text c5/c7、服务端 character_text [5]/[7]）不改：只写技能本体
     （「风属性共鸣且Fever模式中…每层额外增加10倍（最多10层）。」），旗号 2 的不封顶只写在队长强化条目（第 6 项 R3）。
     text / action / server_text 三份输入仍按 BEFORE 读入锁定，:func:`description_problems` 核对 live 描述不含强化后的效果。
5. 面板同条件合并与共鸣省略（作者「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,
   引擎点火提供的效果就不用写火属性共鸣,其他角色类似」；主会话合并规则）：
   - 共鸣省略依据：固有「星风快门」14998901 / 「星风心得」14998902 只由 629 ``flip_stock``（队长 #4）与
     ``flip_stock_ability``（能力3 #4）授予，「快门消费结算」14998903 / 14998904 只由 ``flip_stock_spent``（队长 #5）
     / ``flip_stock_ability_spent``（能力3 #5）授予；四条调用行都带「风编成≥6」前置（kind 2 / Green）。live 1.4.1054
     全部队长/能力表 + 1476 个可枚举 DSL（技能、换形、629、PF）只读扫描无其他来源（与主会话 scan.json all_states 一致）。
     ⇒ 这些状态层数 / 持有提供的效果不写「风属性共鸣时，」（数据前置不动）：
     队长第 5 行（消耗快门连击 +7，数据 队长 #5）、第 6 行（心得每层，数据 队长 #6/#7）；能力2 第 2 行（每消耗 1 层快门
     Fever 槽 +5%，数据 能力2 #2/#3 依赖 14998903/14998904）；能力3 第 5 行（数据 能力3 #5）、第 7 行（数据 能力3 #6/#7）。
     获取行（队长第 4 行、能力3 第 4 / 6 行）保留共鸣。只删行首前缀，其余字面（含主位图标）逐字不变。
   - 开关行保留共鸣（主会话口径 2：704/536 技能开关行的共鸣是真实条件，同玛格诺斯队长 L6）：队长第 7 行（本轮新增，
     技能倍率随心得层数提升）的数据是能力1 I704 开关行，其前置本身就是「仅队长 + 风属性 6 人共鸣」（技能树旗号 2 分支
     另在 ConditionalsUnifyElement(4, 6) 共鸣支内）⇒ 保留「风属性共鸣时，」，与数值稿逐字相同。
   - 同条件合并：各面板同条件组都已在同一行（队长 #0/#1、#6/#7；能力2 #0/#1；能力3 #6/#7），无可合并组。
   - 能力1 / 4 / 5 / 6 覆盖面板：无同条件组、无依赖上述状态的行（能力1 第 2 行只按第 6 项改写）。
6. 技能强化文案规范（作者原话「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述
   强化后的效果,规范并简化描述」；主会话口径 R1–R4）：强化条目用官方格式、点明技能名、定性不写数字与秒数；开关行
   带共鸣前置 ⇒ 面板行保留「风属性共鸣时，」；CAS 键与面板对应行同文（:func:`text_problems`）：
   - 旗号 1（能力1 I536，前置 风 6 人共鸣）：live ``change_skill_wind_spgirl_campus_fever``「强化技能：全队贯穿、…（均15秒）」
     与能力1 面板第 2 行「风属性共鸣时，强化技能，额外赋予…持续15秒。」→「为『风中快门·十字双空牙』追加「赋予全队贯穿＋
     风属性角色能力伤害提升效果」与「赋予命中的敌人风属性抗性降低效果」」（面板行加共鸣前缀与句末「。」）；
     依据 :func:`fever_entry_problems`（旗号 1 开支只有 97 贯穿 + 33[风] 能力伤害 + 命中块风抗性降低，关支全空）；
   - 旗号 2（能力1 I704）：CAS 与队长第 7 行点名技能；第 7 行去掉「Fever模式中，」（开关行前置只有 42 + 风共鸣，
     Fever 判断在技能 DSL 本体里，技能描述已写「风属性共鸣且Fever模式中」）。

不改：能力3 #6/#7 封顶版（+8%/+5%，最多 10 层，口径 D4）数值；技能描述 5 处（第 4、6 项）；能力1 面板第 1 行。

生成器已同步：``wf_celtie_fever_abilities``（能力1 追加 I704 开关 + 平表 ``change_skill_wind_spgirl_campus_leader``）、
``wf_celtie_fever_leader.GAIN_GROWTH_STRENGTH``（20000）、``wf_celtie_skill_growth.with_leader_uncapped_growth``
（``wf_celtie_fever_skill.build_skill`` 在 Boss 锁定之后调用）、``wf_campus_panel_text._CELTIE``（leader / a1 / a2 / a3 /
active）与 ``native_flat_string_rows``（旗号 1 条目，装配时覆盖 ``wf_celtie_fever_abilities`` 的旧平表文案）；
测试断言生成器输出 == :func:`revise` 输出。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl
import wf_midautumn_kitlib as KL

CID = "149989"
CODE = "wind_spgirl_campus"
#: flow owner（active.json base_package_owners 登记 campus-celtie-20260911）。
PACKAGES = ["campus-celtie-20260911"]
#: 候选 manifest 现值 0.20260927（第二批回写）⇒ 0.20260927.1（数字点分比较只升不降）。
PACKAGE_VERSION = {"campus-celtie-20260911": "0.20260927.1"}
#: 本模块返回的行 / 键所需：两条 desc_override_* 之外没有新依赖（I704 在官方 APK 原生解析）。
CAPABILITIES = ["panel-description-override-v2"]
#: 候选文件与 manifest 哈希一致（2026-09-27 只读打开通过）；1499891 候选内容落后 live 属既有漂移，见 notes。
REVIEWED_DRIFT: dict = {}

ELEMENT = 3                         # 内部元素：风（与 wf_celtie_fever_* 的 legality 调用一致）
ELEMENT_TOKEN = "Green"
ABILITY_KEY = CID + "1"
CAS_LEADER = "desc_override_" + CODE
CAS_SWITCH = "change_skill_" + CODE + "_leader"
PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in ("1", "2")}
LEADER_NCOLS, ABILITY_NCOLS = 124, 126

GAIN_UID = "14998902"               # 固有「星风心得」
GAIN_FLOAT_ID = 14998905            # 技能 DSL 里心得层数的浮点变量

# ------------------------------------------------------------------ 1. 队长 #6/#7

GROWTH_ROWS = {6: "154", 7: "0"}    # 行号 → c107 内容 kind（能力伤害 / 攻击力）
GROWTH_OLD, GROWTH_NEW = "2500", "20000"
#: 表 reeval_full.json 149989 L#6/L#7：原 25% / 批二 2.5% / 建议 20%。
GROWTH_TABLE = {"original": "25000", "batch2": GROWTH_OLD, "suggested": GROWTH_NEW}
#: 队长原 6 行 c45（瞬发内容 kind）；#6/#7 为持续行（c3=1，内容看 c107）。
LEADER_KINDS = ("32", "388", "722", "254", "629", "629")
#: #6/#7 的逐格指纹（全部非空列；其余列必须为空）= 第二批 ``[CODE,'0',''] + 能力3行[5:]``。
_GROWTH_CELLS = {
    0: CODE, 1: "0", 3: "1", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN, 11: "12",
    18: "0", 83: "(None)", 95: "134", 96: "0", 98: "100000", 99: "100000", 100: "(None)",
    102: GAIN_UID, 106: "false", 108: "5", 109: ELEMENT_TOKEN,
}


def growth_cells(content: str, strength: str) -> dict[int, str]:
    return {**_GROWTH_CELLS, 107: content, 111: strength, 112: strength}


# ------------------------------------------------------------------ 2. 能力1 开关

#: 能力1 现有两行：I211 开局技能槽、I536 技能强化（旗号 1）。
ABILITY1_KINDS = ("211", "536")
LEADER_FLAG = 2
FLAG_KIND = "704"                   # ChangeSkillFlag2（InstantAbilitySource.as：704–708 → 旗号 2–6）
#: 新行逐格（其余列为空）。同形 live 先例 1499866#4（c0/c70 之外逐格相同）。
SWITCH_CELLS = {
    0: CODE + "_1", 1: "false", 2: "special", 3: "0", 5: "0",
    6: "42",                                             # 前置1：仅队长
    13: "2", 16: "600000", 17: "600000", 18: ELEMENT_TOKEN,   # 前置2：风属性 6 人共鸣
    20: "0", 27: "0", 39: "(None)", 46: "0", 47: FLAG_KIND, 70: CAS_SWITCH,
}
SWITCH_PRECEDENT = "1499866#4"
#: 读平表文案键的「切换技能旗号」内容 kind（536 = 旗号 1，704–708 = 旗号 2–6）。
SKILL_FLAG_KINDS = ("536", "704", "705", "706", "707", "708")

# ------------------------------------------------------------------ 3. DSL

CAPPED_LAYERS = 10                  # 第二批（口径 A5）：非队长 / 不共鸣时保留（口径 U7）
UNCAPPED_LAYERS = 2147483647.0      # 第二批前的值（固有「星风心得」上限同为 2147483647）
#: live 两档（第二批后）命令计数指纹。
COUNTS_BEFORE = {
    "ConditionalsChangeSkillFlag": 25, "FindAllSubjects": 2, "CreateCondition": 26,
    "ConditionalsFeverMode": 1, "ConditionalsUnifyElement": 1, "BindConditionAccumulationVariable": 3,
    "FindNearSubjects": 6, "MoveBall": 6, "ShowEffect": 84, "HideEffect": 12, "RemoveEvent": 39,
    "StopBall": 12, "HideCharacter": 12, "CreateReferencePoint": 12, "CreateHitArea": 24,
    "CreateNormalAttack": 24,
}

# ------------------------------------------------------------------ 4. 文案

LEADER_LINES_BEFORE = (
    "风属性角色攻击力+200%、能力伤害+400%。",
    "风属性共鸣时，强化弹射变为特殊剑士型，造成风属性伤害，伤害量以能力伤害加成判定。",
    "风属性共鸣时，Fever模式中，强化弹射时，对全场敌人追加10倍风属性能力伤害。",
    "风属性共鸣时，Fever模式中，风属性角色发动技能时，自身获得2层「星风快门」与2层「星风心得」。",
    "风属性共鸣时，Fever模式中，弹射时消耗1层「星风快门」，连击+7。",
    "风属性共鸣时，Fever模式中，每层「星风心得」使风属性角色能力伤害+2.5%、攻击力+2.5%。",
)
LEADER_LINE6_AFTER = "风属性共鸣时，Fever模式中，每层「星风心得」使风属性角色能力伤害+20%、攻击力+20%。"
#: 旗号 2（I704）强化条目：官方格式「强化『<技能名>』：<定性说明>」；面板行 = 开关行真实前置「风属性共鸣时，」+ CAS +「。」。
SKILL_NAME = "风中快门·十字双空牙"
LEADER_LINE_ADDED = "风属性共鸣时，强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升。"
#: 数值稿（本轮成长数值 + 新增第 7 行，未删共鸣前缀）：面板合并校验（wf_panel_merge_check）的原文。
LEADER_LINES_NUMERIC = LEADER_LINES_BEFORE[:5] + (LEADER_LINE6_AFTER, LEADER_LINE_ADDED)

SWITCH_TEXT = "强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升"


class CeltieBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


# ------------------------------------------------------------------ 5. 面板共鸣省略 / 同条件合并

MAIN_ICON = " <icon id='main'>  "
RESONANCE_PREFIX = "风属性共鸣时，"
ABILITY2_KEY, ABILITY3_KEY = CID + "2", CID + "3"
CAS_A2, CAS_A3 = CAS_LEADER + "_2", CAS_LEADER + "_3"
STOCK_UID = "14998901"              # 固有「星风快门」
SPENT_UIDS = ("14998903", "14998904")   # 固有「快门消费结算」（队长 / 能力3 两支）
#: 授予上述状态的 629 程序 → (调用行, 授予的固有状态)；全部状态来源（live 1.4.1054 全表 + 1476 个可枚举 DSL 扫描）。
GRANT_PROGRAMS = {
    f"battle/action/skill/action/ability_skill/{CODE}${CODE}_{name}": (invoker, uids)
    for name, invoker, uids in (
        ("flip_stock", ("leader", CID, 4), (STOCK_UID, GAIN_UID)),
        ("flip_stock_ability", ("ability", ABILITY3_KEY, 4), (STOCK_UID, GAIN_UID)),
        ("flip_stock_spent", ("leader", CID, 5), (SPENT_UIDS[0],)),
        ("flip_stock_ability_spent", ("ability", ABILITY3_KEY, 5), (SPENT_UIDS[1],)),
    )
}
RESONANCE_TOKEN = ELEMENT_TOKEN
RESONANCE_OMISSION = {
    uid: {"name": name, "resonance": RESONANCE_TOKEN,
          "sources": [f"629 {program.rsplit('$', 1)[1]}（{invoker[0]}:{invoker[1]}#{invoker[2]}）"
                      for program, (invoker, uids) in GRANT_PROGRAMS.items() if uid in uids]}
    for uid, name in ((STOCK_UID, "星风快门"), (GAIN_UID, "星风心得"),
                      (SPENT_UIDS[0], "快门消费结算"), (SPENT_UIDS[1], "快门消费结算"))
}
RESONANCE_SCAN = ("live 1.4.1054 全部 leader_ability / ability 行 + 1476 个可枚举 DSL（action_skill、switched、629、"
                  "power_flip_action）只读扫描：上述 4 个固有状态只由这 4 个 629 程序授予；与主会话 scan.json all_states 一致")
#: 删共鸣前缀的面板行（0 基）→ 该行效果依赖的数据（(表, 键, 行号, 依赖列, 固有状态)）。
LEADER_PREFIX_DROPS = {
    4: [("leader", CID, 5, 43, STOCK_UID)],                             # 弹射时消耗 1 层快门，连击 +7
    5: [("leader", CID, 6, 102, GAIN_UID), ("leader", CID, 7, 102, GAIN_UID)],   # 心得每层
}
#: 保留共鸣的开关行（0 基）：队长第 7 行 = 能力1 I704 开关（前置 仅队长 + 风 6 人共鸣），共鸣是真实条件（主会话口径 2）。
LEADER_SWITCH_LINE = 6
A2_PREFIX_DROPS = {
    1: [("ability", ABILITY2_KEY, 2, 37, SPENT_UIDS[0]), ("ability", ABILITY2_KEY, 3, 37, SPENT_UIDS[1])],
}
A3_PREFIX_DROPS = {
    4: [("ability", ABILITY3_KEY, 5, 45, STOCK_UID)],
    6: [("ability", ABILITY3_KEY, 6, 104, GAIN_UID), ("ability", ABILITY3_KEY, 7, 104, GAIN_UID)],
}
A2_LINES_BEFORE = (
    "风属性共鸣时，风属性角色直接攻击分为3次，能力伤害+200%。",
    "风属性共鸣时，Fever模式中，每消耗1层「星风快门」，Fever槽+5%。",
)
A3_LINES_BEFORE = tuple(MAIN_ICON + line for line in (
    "风属性共鸣时，Fever模式中，风属性角色合计每直接攻击35次，对全场敌人造成25倍风属性能力伤害。",
    "风属性共鸣时，非Fever模式中，风属性角色合计每直接攻击35次，Fever槽+15%。",
    "风属性共鸣时，Fever模式中，连击每达到7的倍数，风属性角色攻击力+70%（最大+700%）、技能槽+0.7%（回槽冷却时间：0.7秒）。",
    "风属性共鸣时，Fever模式中，风属性角色发动技能时，自身获得1层「星风快门」。",
    "风属性共鸣时，Fever模式中，弹射时消耗1层「星风快门」，连击+7。",
    "风属性共鸣时，每获得1层「星风快门」，自身获得1层「星风心得」。",
    "风属性共鸣时，Fever模式中，每层「星风心得」使风属性角色能力伤害+8%、攻击力+5%（最多10层）。",
))


def drop_resonance(line: str) -> str:
    """只删行首（主位图标之后）的「风属性共鸣时，」，其余字面逐字保留。"""
    icon = MAIN_ICON if line.startswith(MAIN_ICON) else ""
    body = line[len(icon):]
    if not body.startswith(RESONANCE_PREFIX):
        raise CeltieBalanceError(f"line has no resonance prefix: {line}")
    return icon + body[len(RESONANCE_PREFIX):]


def _dropped(lines: tuple[str, ...], drops) -> tuple[str, ...]:
    return tuple(drop_resonance(line) if index in drops else line for index, line in enumerate(lines))


LEADER_LINES_AFTER = _dropped(LEADER_LINES_NUMERIC, LEADER_PREFIX_DROPS)
A2_LINES_AFTER = _dropped(A2_LINES_BEFORE, A2_PREFIX_DROPS)
A3_LINES_AFTER = _dropped(A3_LINES_BEFORE, A3_PREFIX_DROPS)

# ------------------------------------------------------------------ 6. 旗号 1 强化条目（能力1 I536）

CAS_FEVER = "change_skill_" + CODE + "_fever"
CAS_A1 = CAS_LEADER + "_1"
FEVER_TEXT_BEFORE = "强化技能：全队贯穿、风属性角色能力伤害+100%，命中敌人风属性抗性-25%（均15秒）"
FEVER_TEXT = ("为『风中快门·十字双空牙』追加「赋予全队贯穿＋风属性角色能力伤害提升效果」"
              "与「赋予命中的敌人风属性抗性降低效果」")
A1_LINES_BEFORE = (
    MAIN_ICON + "战斗开始时：自身技能槽+50%。",
    MAIN_ICON + "风属性共鸣时，强化技能，额外赋予全队贯穿、风属性角色能力伤害提升100%、命中敌人风属性抗性降低25%效果，持续15秒。",
)
A1_SWITCH_LINE = 1
A1_LINES_AFTER = (A1_LINES_BEFORE[0], MAIN_ICON + RESONANCE_PREFIX + FEVER_TEXT + "。")
#: 强化条目 CAS ↔ 面板行：(CAS 键, CAS 文本, 面板键, 面板行（改后）)。
SKILL_FLAG_ENTRIES = (
    (CAS_FEVER, FEVER_TEXT, CAS_A1, A1_LINES_AFTER[A1_SWITCH_LINE]),
    (CAS_SWITCH, SWITCH_TEXT, CAS_LEADER, LEADER_LINE_ADDED),
)
#: 旗号 1 开支（live 技能两档）的状态签名：一处 97 贯穿 + 33[风] 能力伤害，其余每处命中块风属性抗性降低；关支全空。
FEVER_BRANCH_SIGNATURES = frozenset({
    (("FindAllSubjects", 97, ()), ("ACPiercing",), ("FindAllSubjects", 33, (4,)), ("ACAbilityDamage",)),
    (("ACToleranceOfElement", 4, "down"),),
})

#: 技能描述（live = 第二批输出，本轮不改）：只写技能本体；「风属性共鸣且Fever模式中」是技能 DSL 自身的
#: ConditionalsFeverMode / ConditionalsUnifyElement(4, 6) 判断（R1 属技能本体），「最多10层」是本体上限（关支）。
#: 旗号 2 开支的不封顶是强化效果，只写在队长强化条目（R3）。
SKILL_DESC = ("向Boss突进并持续朝其释放十字双空牙（无Boss时选择最近敌人），对命中敌人造成基础合计75倍风属性伤害，"
              "伤害量以能力伤害加成判定。风属性共鸣且Fever模式中，技能倍率随「星风心得」成长，每层额外增加10倍（最多10层）。")
TEXT_DESC_COLUMNS = (5, 7)          # character_text 技能说明（觉醒前 / 后）
#: R3：强化后的效果不写在强化条目以外（技能描述、面板其余行）；强化条目不用「强化技能」「强化自身技能」泛称。
ENHANCED_PHRASES = ("不受此限", "强化后", "强化自身技能", "强化技能")


#: 队长 629 行引用的 custom_ability_string 键（live 已有；只用于 invoke 门禁）。
INVOKE_STRING_KEYS = frozenset({
    CODE + "_flip_stock", CODE + "_flip_stock_spent",
    CODE + "_flip_stock_ability", CODE + "_flip_stock_ability_spent",
})

# ------------------------------------------------------------------ 输入基线

#: live 输入基线（2026-09-27 本地链尾 1.4.1053 只读取数，stage_batch.make_read(live_only=True)；1.4.1054 复核逐字相同）。
#: 原 8 项除 1499891 外与第二批 revise() 输出逐字相同；1499891 第二批未触碰。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", CID): "93b48744d698db1af42bf02028d7b4331da81451df6ae733ad48ebbe5b569015",
    ("ability", ABILITY_KEY): "fdf1e5a62a06970e0cc6f891db5a8099d0b879a7f77f8560866d350d647e6ca8",
    ("cas", CAS_LEADER): "d9c9986e907f8de59e448e599074168430abc860e1f70ce9de8d07dd45871215",
    ("text", CID): "5d6414aeddd81af83f87b61b5c349d815146fae1b4105743b971044042872eb7",
    ("action", CODE): "d4aaf1550f604d1714c7eabbbee68eeac97a2b28e2b43991fe955971a2577c13",
    ("dsl", PROGRAMS["1"]): "fa42d09a89d2ffe17b153bfafb341c84c460a636b888ed5ef02797487607110d",
    ("dsl", PROGRAMS["2"]): "fa42d09a89d2ffe17b153bfafb341c84c460a636b888ed5ef02797487607110d",
    ("server_text", CID): "5d6414aeddd81af83f87b61b5c349d815146fae1b4105743b971044042872eb7",
    # 面板共鸣省略新增（live 1.4.1054 只读取数）：两块未改数值的覆盖面板 + 共鸣省略依据（状态来源行与授予程序）。
    ("cas", CAS_A2): "94aef5deb56ee52f5efbbe200eff00d51167282564281ea015956be5c614ff59",
    ("cas", CAS_A3): "e0e3778ee6c98b77429cc44e067c061ac65f06f2254591b52d5b327d01126462",
    ("ability", ABILITY3_KEY): "3fa3546f1154108e78d0d08dd077d7f96ba0a43c93ecaf02087cd4a25544dff0",
    ("dsl", f"battle/action/skill/action/ability_skill/{CODE}${CODE}_flip_stock"):
        "3297d80551651dd8b4199756e81fba4ef9423d796f30b9b087f95d2548b7c0b5",
    ("dsl", f"battle/action/skill/action/ability_skill/{CODE}${CODE}_flip_stock_ability"):
        "e311cc1fd39116bb8b83d7e7a8090d7c978467d70be5168f74e93cd0863741ca",
    ("dsl", f"battle/action/skill/action/ability_skill/{CODE}${CODE}_flip_stock_spent"):
        "45c7163646f738549b736c6a87251563a3d81816d144314040e67ff03becc451",
    ("dsl", f"battle/action/skill/action/ability_skill/{CODE}${CODE}_flip_stock_ability_spent"):
        "63265f98f0b6d177a7817adca6a8b2bf837b31cdb826425be61142cec44c75c6",
    # 技能强化文案规范新增（live 1.4.1054 只读取数）：旗号 1 条目与能力1 面板（第二批未触碰，第一批起 live 原文）。
    ("cas", CAS_FEVER): "05425e58b798f862ae3bdf09e24e7a8176eb571c9e16b505cffed28de1ac6e70",
    ("cas", CAS_A1): "48fe0f1f8007c2ea743a2715483a2eeb7cb2fa302de7c75cf433450ad392426a",
}
#: 新增键：live 必须不存在（read 抛 KeyError 或返回 None），否则视为漂移。
ABSENT: tuple[tuple[str, str], ...] = (("cas", CAS_SWITCH),)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise CeltieBalanceError(f"unreviewed live baseline for {kind}:{key} "
                                 f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _absent(read: Callable[[str, Any], Any], kind: str, key: str) -> None:
    try:
        value = read(kind, key)
    except KeyError:
        return
    if value is not None:
        raise CeltieBalanceError(f"unreviewed live baseline for {kind}:{key} (new key already exists)")


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


# ------------------------------------------------------------------ 词条

def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 #6/#7 c111/c112 2500 → 20000；#0–#5 与两行其余列逐字保留。"""
    if len(rows) != len(LEADER_KINDS) + len(GROWTH_ROWS) or any(len(row) != LEADER_NCOLS for row in rows):
        raise CeltieBalanceError(f"leader_ability {CID}: expected 8×{LEADER_NCOLS} rows")
    if tuple(row[45] for row in rows[:6]) != LEADER_KINDS or any(row[95] for row in rows[:6]):
        raise CeltieBalanceError(f"leader_ability {CID}: rows #0–#5 drifted")
    out = deepcopy(rows)
    for index, content in GROWTH_ROWS.items():
        if not _matches(rows[index], LEADER_NCOLS, growth_cells(content, GROWTH_OLD)):
            raise CeltieBalanceError(f"leader_ability {CID}#{index}: batch-2 insight growth row "
                                     f"(D134, (None), c107={content}, {GROWTH_OLD}) not found")
        out[index][111] = out[index][112] = GROWTH_NEW
        if not _matches(out[index], LEADER_NCOLS, growth_cells(content, GROWTH_NEW)):
            raise AssertionError("leader_rows touched more than c111/c112")
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != sorted(GROWTH_ROWS):
        raise AssertionError("leader_rows touched another record")
    return out


def switch_row() -> list[str]:
    row = [""] * ABILITY_NCOLS
    for column, value in SWITCH_CELLS.items():
        row[column] = value
    return row


def ability1_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力1 原两行逐字保留，末尾追加 I704 开关（旗号 2，仅队长 + 风共鸣）。"""
    if len(rows) != len(ABILITY1_KINDS) or any(len(row) != ABILITY_NCOLS for row in rows):
        raise CeltieBalanceError(f"ability {ABILITY_KEY}: expected {len(ABILITY1_KINDS)}×{ABILITY_NCOLS} rows "
                                 "(or the leader switch is already present)")
    if tuple(row[47] for row in rows) != ABILITY1_KINDS or any(row[5] != "0" for row in rows):
        raise CeltieBalanceError(f"ability {ABILITY_KEY}: content kinds drifted")
    if any(row[0] != CODE + "_1" or row[1] != "false" for row in rows):
        raise CeltieBalanceError(f"ability {ABILITY_KEY}: identity / main-only column drifted")
    if rows[1][6] != "2" or rows[1][70] != "change_skill_" + CODE + "_fever":
        raise CeltieBalanceError(f"ability {ABILITY_KEY}#1: flag-1 enhancement (I536) drifted")
    return deepcopy(rows) + [switch_row()]


def row_gate_problems(table: str, row: list[str]) -> list[str]:
    problems = [f"legality: {p}" for p in L.client_legality_problems(table, row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems(table, row)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems(table, row, ELEMENT)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, INVOKE_STRING_KEYS, kind=table)]
    return problems


def switch_string_problems(rows: list[list[str]], cas_keys) -> list[str]:
    """I536/I704–708 行的 c70 文案键必须在平表里（缺键 = 角色详情 C8601）。"""
    return [f"ability#{i} c70 {row[70]!r} missing from custom_ability_string"
            for i, row in enumerate(rows)
            if row[47] in SKILL_FLAG_KINDS and row[70] not in cas_keys]


def required_capabilities(ability: list[list[str]], leader: list[list[str]], cas_keys) -> list[str]:
    caps = {cap for row in ability for cap in L.required_client_capabilities("ability", row)}
    caps |= {cap for row in leader for cap in L.required_client_capabilities("leader_ability", row)}
    caps |= {cap for key in cas_keys for cap in L.required_client_capabilities("custom_ability_string", [key])}
    return sorted(caps)


# ------------------------------------------------------------------ 文案

def _single_text(rows: list[list[str]], key: str) -> str:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise CeltieBalanceError(f"{key}: expected one single-column row")
    return rows[0][0]


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    """live 6 行 → 数值稿（第 6 行 +20%、追加第 7 行）→ 第 5–7 行删共鸣前缀（共鸣省略）。"""
    if tuple(_single_text(rows, CAS_LEADER).split("\n")) != LEADER_LINES_BEFORE:
        raise CeltieBalanceError(f"{CAS_LEADER}: unexpected panel text")
    return [["\n".join(LEADER_LINES_AFTER)]]


def a2_text(rows: list[list[str]]) -> list[list[str]]:
    """能力2 面板：第 2 行（每消耗 1 层快门 Fever 槽 +5%）删共鸣前缀；数值不变。"""
    if tuple(_single_text(rows, CAS_A2).split("\n")) != A2_LINES_BEFORE:
        raise CeltieBalanceError(f"{CAS_A2}: unexpected panel text")
    return [["\n".join(A2_LINES_AFTER)]]


def a3_text(rows: list[list[str]]) -> list[list[str]]:
    """能力3 面板（主位槽，每行带图标）：第 5 / 7 行删共鸣前缀；数值不变。"""
    if tuple(_single_text(rows, CAS_A3).split("\n")) != A3_LINES_BEFORE:
        raise CeltieBalanceError(f"{CAS_A3}: unexpected panel text")
    return [["\n".join(A3_LINES_AFTER)]]


def a1_text(rows: list[list[str]]) -> list[list[str]]:
    """能力1 面板（主位槽）：第 2 行旗号 1 强化条目改官方格式（点名技能、定性不写数字与秒数），第 1 行逐字。"""
    if tuple(_single_text(rows, CAS_A1).split("\n")) != A1_LINES_BEFORE:
        raise CeltieBalanceError(f"{CAS_A1}: unexpected panel text")
    return [["\n".join(A1_LINES_AFTER)]]


def fever_text(rows: list[list[str]]) -> list[list[str]]:
    """旗号 1 强化条目（能力1 I536 c70）：与能力1 面板第 2 行同文（去共鸣前缀与句末「。」）。"""
    if _single_text(rows, CAS_FEVER) != FEVER_TEXT_BEFORE:
        raise CeltieBalanceError(f"{CAS_FEVER}: unexpected text")
    return [[FEVER_TEXT]]


#: 前置块起始列（kind, pulled, pulled_group, 下限, 上限, 属性组, uid）：队长 / 能力。
PRECONDITION_BASES = {"leader": (4, 11, 18), "ability": (6, 13, 20)}
#: 629 调用行的程序路径列（瞬发内容块 +24）。
INVOKE_PROGRAM_COL = {"leader": 69, "ability": 71}


def resonance_tokens(row: list[str], table: str) -> list[str]:
    """该行前置里的属性共鸣（kind 2、编成 600000、不按拉取组计数）的属性组。"""
    out = []
    for base in PRECONDITION_BASES[table]:
        kind, _pulled, pulled_group, low, high, group = row[base:base + 6]
        if kind == "2" and low == "600000" and high in ("600000", "") and group \
                and pulled_group in ("", "0", "(None)"):
            out.append(group)
    return out


def granted_uniques(tree) -> list[str]:
    """DSL 里 CreateCondition 授予的固有状态（ACUnique）。"""
    return sorted({str(int(cond[1])) for args in _commands(tree) if args[0] == "CreateCondition"
                   for cond in (args[2] if len(args) > 2 and isinstance(args[2], list) else [])
                   if isinstance(cond, list) and cond and cond[0] == "ACUnique"})


def resonance_basis_problems(tables: dict[tuple[str, str], list[list[str]]], trees: dict[str, Any]) -> list[str]:
    """共鸣省略依据（fail closed）：四个状态的授予程序只授予登记的状态，调用行是 629 且带风共鸣；
    删前缀的每一行，其数据行确实依赖对应状态。"""
    problems = []
    for program, ((table, key, index), uids) in GRANT_PROGRAMS.items():
        row = tables[table, key][index]
        name = program.rsplit("$", 1)[1]
        if granted_uniques(trees[program]) != sorted(uids):
            problems.append(f"{name}: grants {granted_uniques(trees[program])}, expected {sorted(uids)}")
        content = 45 if table == "leader" else 47
        if row[content] != "629" or row[INVOKE_PROGRAM_COL[table]] != program:
            problems.append(f"{table}:{key}#{index} no longer invokes {name}")
        if resonance_tokens(row, table) != [RESONANCE_TOKEN]:
            problems.append(f"{table}:{key}#{index} ({name}) is not gated on wind resonance; "
                            "the resonance prefix omission no longer holds")
    for drops in (LEADER_PREFIX_DROPS, A2_PREFIX_DROPS, A3_PREFIX_DROPS):
        for _line, refs in drops.items():
            for table, key, index, col, uid in refs:
                rows = tables.get((table, key))
                if rows is not None and rows[index][col] != uid:
                    problems.append(f"{table}:{key}#{index} c{col} no longer depends on {uid}")
    # 队长第 7 行保留共鸣的依据：其数据行（能力1 末行 I704 开关）前置 = 仅队长 + 风属性 6 人共鸣。
    ability1 = tables.get(("ability", ABILITY_KEY))
    if ability1 is not None:
        switch = ability1[-1]
        if switch[47] != FLAG_KIND or switch[6] != "42" or resonance_tokens(switch, "ability") != [RESONANCE_TOKEN]:
            problems.append(f"ability:{ABILITY_KEY}#{len(ability1) - 1} is not the leader-only wind-resonance I704 "
                            "switch; leader panel L7 keeps 「风属性共鸣时，」 only on that basis")
        # 能力1 面板第 2 行保留共鸣的依据：其数据行（能力1 #1 I536 旗号 1）前置 = 风属性 6 人共鸣，c70 = 旗号 1 条目。
        flag1 = ability1[1]
        if flag1[47] != "536" or flag1[70] != CAS_FEVER or resonance_tokens(flag1, "ability") != [RESONANCE_TOKEN]:
            problems.append(f"ability:{ABILITY_KEY}#1 is not the wind-resonance I536 switch of {CAS_FEVER}; "
                            "ability-1 panel L2 keeps 「风属性共鸣时，」 only on that basis")
    return problems


def _signature(args) -> tuple:
    """旗号 1 开支里一条状态命令的签名（FindAllSubjects 的对象种类 / 属性筛选，CreateCondition 的状态种类）。"""
    if args[0] == "FindAllSubjects":
        return ("FindAllSubjects", args[2], tuple(args[3]))
    conditions = args[2]
    if [c[0] for c in conditions] == ["ACToleranceOfElement"]:
        cond = conditions[0]
        values = {v for term in cond[3] for v in (term["min"], term["max"])}
        return ("ACToleranceOfElement", cond[2], "down" if values and max(values) < 0 else "up")
    return tuple(c[0] for c in conditions)


def fever_entry_problems(tree) -> list[str]:
    """旗号 1 条目「追加「全队贯穿＋风属性角色能力伤害提升」与「命中的敌人风属性抗性降低」」的数据依据（fail closed）：
    live 技能树里每个 ConditionalsChangeSkillFlag(1) 的关支为空、开支状态签名属于 :data:`FEVER_BRANCH_SIGNATURES`，
    且两类签名都出现。"""
    problems: list[str] = []
    seen: set[tuple] = set()
    for args in _commands(tree):
        if args[0] != "ConditionalsChangeSkillFlag" or args[1] != 1:
            continue
        if _commands(args[3]):
            problems.append("flag-1 branch has an off-branch body (the entry only describes additions)")
        signature = tuple(_signature(c) for c in _commands(args[2])
                          if c[0] in ("FindAllSubjects", "CreateCondition"))
        if signature not in FEVER_BRANCH_SIGNATURES:
            problems.append(f"flag-1 branch grants {signature}, not described by {CAS_FEVER}")
        seen.add(signature)
    if seen != set(FEVER_BRANCH_SIGNATURES):
        problems.append(f"flag-1 branches {sorted(seen)} != reviewed {sorted(FEVER_BRANCH_SIGNATURES)}")
    return problems


def description_problems(descriptions: dict[str, str]) -> list[str]:
    """技能描述只写技能本体（R3）：5 处都 == :data:`SKILL_DESC`，不含强化后的效果。"""
    problems = [f"{label}: skill description is not the reviewed skill-body text"
                for label, text in descriptions.items() if text != SKILL_DESC]
    problems += [f"skill description carries {phrase!r}" for phrase in ENHANCED_PHRASES if phrase in SKILL_DESC]
    return problems


def text_problems() -> list[str]:
    problems = []
    for line in (*LEADER_LINES_AFTER, *A2_LINES_AFTER, *A3_LINES_AFTER, *A1_LINES_AFTER, SKILL_DESC):
        problems += [f"{line[:24]}…: {p}" for p in KL.panel_problems(line)]
        if "／" in line:
            problems.append(f"{line[:24]}…: 多条不用「／」")
        if "共鸣时：" in line:
            problems.append(f"{line[:24]}…: 共鸣写「X属性共鸣时，」")
        for phrase in ENHANCED_PHRASES:
            if phrase in line:
                problems.append(f"{line[:24]}…: {phrase!r}（强化条目点名『{SKILL_NAME}』，强化后的效果只写在强化条目里）")
    if any(not line.startswith(MAIN_ICON) for line in (*A3_LINES_AFTER, *A1_LINES_AFTER)):
        problems.append("ability1/3 panel: main-position slot lines keep the main icon")
    # R2：强化条目官方格式、点名技能、不写数字；面板行 = 开关行真实前置「风属性共鸣时，」+ CAS +「。」。
    for cas_key, cas_text, panel_key, panel_line in SKILL_FLAG_ENTRIES:
        problems += [f"{cas_key}: {p}" for p in KL.panel_problems(cas_text, skill_flag=True)]
        problems += [f"{panel_key}: {p}" for p in KL.panel_problems(panel_line.replace(MAIN_ICON, ""), skill_flag=True)]
        if f"『{SKILL_NAME}』" not in cas_text or not cas_text.startswith(("强化『", "为『")):
            problems.append(f"{cas_key}: skill-flag entry must name 『{SKILL_NAME}』 in the official format")
        if panel_line.replace(MAIN_ICON, "") != RESONANCE_PREFIX + cas_text + "。":
            problems.append(f"{panel_key}: panel entry of {cas_key} must read 「{RESONANCE_PREFIX}{cas_text}。」")
    for lines, drops in ((LEADER_LINES_AFTER, LEADER_PREFIX_DROPS), (A2_LINES_AFTER, A2_PREFIX_DROPS),
                         (A3_LINES_AFTER, A3_PREFIX_DROPS)):
        if any(RESONANCE_PREFIX in lines[index] for index in drops):
            problems.append("dropped lines still carry the resonance prefix")
    if LEADER_SWITCH_LINE in LEADER_PREFIX_DROPS \
            or LEADER_LINES_AFTER[LEADER_SWITCH_LINE] != LEADER_LINE_ADDED \
            or not LEADER_LINE_ADDED.startswith(RESONANCE_PREFIX):
        problems.append("leader switch line (I704, leader + wind resonance) must keep 「风属性共鸣时，」")
    for line in (LEADER_LINE_ADDED, SWITCH_TEXT, FEVER_TEXT, A1_LINES_AFTER[A1_SWITCH_LINE]):
        if any(ch.isdigit() for ch in line):
            problems.append(f"{line[:24]}…: 技能强化条目不写数字")
    return problems


# ------------------------------------------------------------------ DSL

def _commands(node, out: list | None = None) -> list[list]:
    out = [] if out is None else out
    if isinstance(node, list):
        if len(node) == 2 and node[0] == "Command" and isinstance(node[1], list) and node[1] \
                and isinstance(node[1][0], str):
            out.append(node[1])
        for child in node:
            _commands(child, out)
    elif isinstance(node, dict):
        for child in node.values():
            _commands(child, out)
    return out


def command_counts(tree) -> dict[str, int]:
    counts: dict[str, int] = {}
    for args in _commands(tree):
        counts[args[0]] = counts.get(args[0], 0) + 1
    return counts


def _bind(block, cap) -> list:
    """Block 首条必须是本角色的心得 Bind，且上限为 ``cap``（值与类型都要对上）。返回其参数数组。"""
    if not (isinstance(block, list) and len(block) == 2 and block[0] == "Block" and block[1]):
        raise CeltieBalanceError(f"not a growth branch: {block!r:.120}")
    command = block[1][0]
    if not (isinstance(command, list) and command[0] == "Command"):
        raise CeltieBalanceError("growth branch does not start with a command")
    args = command[1]
    if args[:5] != ["BindConditionAccumulationVariable", -17, GAIN_FLOAT_ID, ["DCUnique", int(GAIN_UID)], 1] \
            or args[5] != cap or type(args[5]) is not type(cap):
        raise CeltieBalanceError(f"unexpected Starwind binding {args!r:.160}")
    return args


def unify_command(tree) -> list:
    """ConditionalsFeverMode.then 里唯一的 ConditionalsUnifyElement(4, 6, 共鸣支, 非共鸣支)。"""
    top = tree[11]
    if not (isinstance(top, list) and top[0] == "Block" and len(top[1]) == 2):
        raise CeltieBalanceError("unexpected top block")
    fever = top[1][1][1]
    if fever[0] != "ConditionalsFeverMode" or len(fever) != 3:
        raise CeltieBalanceError("second top command must be ConditionalsFeverMode")
    then = fever[1]
    if not (then[0] == "Block" and len(then[1]) == 1 and then[1][0][0] == "Command"):
        raise CeltieBalanceError("Fever branch must hold only ConditionalsUnifyElement")
    unify = then[1][0][1]
    if unify[:3] != ["ConditionalsUnifyElement", 4, 6] or len(unify) != 5:
        raise CeltieBalanceError("Fever branch must gate wind resonance (UnifyElement 4, 6)")
    return unify


def growth_branches(tree) -> dict[str, Any]:
    """改后树的四支：开（旗号 2）/ 关 / 非共鸣 / 非 Fever。"""
    unify = unify_command(tree)
    resonant = unify[3]
    if not (resonant[0] == "Block" and len(resonant[1]) == 1 and resonant[1][0][0] == "Command"):
        raise CeltieBalanceError("resonant branch must hold only the flag-2 switch")
    flag = resonant[1][0][1]
    if flag[:2] != ["ConditionalsChangeSkillFlag", LEADER_FLAG] or len(flag) != 4:
        raise CeltieBalanceError("resonant branch must switch on skill flag 2")
    return {"on": flag[2], "off": flag[3], "plain": unify[4], "calm": tree[11][1][1][1][2]}


def unbound_variable_references(tree) -> list[str]:
    """每个 vlv 引用的变量号，必须在同一块（或外层块）里、位于其前的 Bind 绑定过。

    分支 / 子块各自开局部环境：块内 Bind 只对其后的兄弟及其子孙可见，不外泄（复核意见：
    Bind 挪进分支后分支外看不到该变量；wf_client_legality 的作用域门禁只查主体 lookup，不查 vlv）。
    """
    problems: list[str] = []

    def visit(node, scope, path):
        if isinstance(node, dict):
            for term in node.get("vlv", []) if isinstance(node.get("vlv"), list) else []:
                if isinstance(term, dict) and term.get("vid") not in scope:
                    problems.append(f"{path}: vlv vid {term.get('vid')} not bound in scope")
            for key, child in node.items():
                visit(child, scope, path + (key,))
            return
        if not isinstance(node, list):
            return
        if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
            local = set(scope)
            for index, child in enumerate(node[1]):
                visit(child, frozenset(local), path + (1, index))
                if (isinstance(child, list) and len(child) == 2 and child[0] == "Command"
                        and child[1] and child[1][0] == "BindConditionAccumulationVariable"):
                    local.add(child[1][2])
            return
        for index, child in enumerate(node):
            visit(child, scope, path + (index,))

    visit(tree, frozenset(), ())
    return problems


def revise_tree(tree, level: str) -> tuple[list, dict[str, Any]]:
    """技能树 → 新树（深拷贝）：共鸣∧Fever 支包进 ConditionalsChangeSkillFlag(2, 不封顶, 原支)。"""
    out = deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl"):
        raise CeltieBalanceError(f"skill {level}: unexpected root")
    if command_counts(out) != COUNTS_BEFORE:
        raise CeltieBalanceError(f"skill {level}: command counts drifted (or flag-2 split already applied)")
    unify = unify_command(out)
    capped = unify[3]
    _bind(capped, CAPPED_LAYERS)
    _bind(unify[4], 0)
    _bind(out[11][1][1][1][2], 0)
    if len(capped[1]) != 2 or capped[1][1][0] != "Block":
        raise CeltieBalanceError(f"skill {level}: resonant branch must be [Bind, route block]")
    uncapped = deepcopy(capped)
    uncapped[1][0][1][5] = UNCAPPED_LAYERS
    unify[3] = ["Block", [["Command", ["ConditionalsChangeSkillFlag", LEADER_FLAG, uncapped, capped]]]]

    expected = dict(COUNTS_BEFORE)
    for name, count in command_counts(capped).items():
        expected[name] = expected.get(name, 0) + count
    expected["ConditionalsChangeSkillFlag"] += 1
    if command_counts(out) != expected:
        raise AssertionError("revise_tree changed more than the flag-2 split")
    return out, {"level": level,
                 "node": "ConditionalsFeverMode.then → ConditionalsUnifyElement(4,6).then",
                 "wrap": "ConditionalsChangeSkillFlag(2, Block[Bind(cap=2147483647.0), route], "
                         "Block[Bind(cap=10), route]（关支 = 原共鸣支逐字）)",
                 "cap": {"flag2_on": UNCAPPED_LAYERS, "flag2_off": CAPPED_LAYERS},
                 "untouched_caps": {"not_resonant": 0, "not_fever": 0}}


def dsl_gate_problems(tree) -> list[str]:
    """contract 要求的四道 DSL 门 + AMF3 往返 + vlv 作用域（复核意见）。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    problems += [f"vlv_scope: {p}" for p in unbound_variable_references(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


# ------------------------------------------------------------------ 入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {key: _checked(read, *key) for key in BEFORE}
    for kind, key in ABSENT:
        _absent(read, kind, key)
    problems = text_problems()
    if problems:
        raise CeltieBalanceError(f"panel text rejected: {problems}")

    leader = leader_rows(inputs["leader", CID])
    ability = ability1_rows(inputs["ability", ABILITY_KEY])
    for table, rows in (("ability", ability), ("leader_ability", leader)):
        for index, row in enumerate(rows):
            problems = row_gate_problems(table, row)
            if problems:
                raise CeltieBalanceError(f"{table}#{index} rejected: {problems}")

    problems = resonance_basis_problems(
        {("leader", CID): leader, ("ability", ABILITY3_KEY): inputs["ability", ABILITY3_KEY],
         ("ability", ABILITY_KEY): ability},
        {program: inputs["dsl", program] for program in GRANT_PROGRAMS})
    if problems:
        raise CeltieBalanceError(f"resonance omission basis rejected: {problems}")

    cas = {CAS_LEADER: leader_text(inputs["cas", CAS_LEADER]), CAS_SWITCH: [[SWITCH_TEXT]],
           CAS_A2: a2_text(inputs["cas", CAS_A2]), CAS_A3: a3_text(inputs["cas", CAS_A3]),
           CAS_A1: a1_text(inputs["cas", CAS_A1]), CAS_FEVER: fever_text(inputs["cas", CAS_FEVER])}
    problems = switch_string_problems(ability, set(cas))
    for program in PROGRAMS.values():
        problems += [f"{program}: {p}" for p in fever_entry_problems(inputs["dsl", program])]
    if problems:
        raise CeltieBalanceError(f"flat description rejected: {problems}")
    caps = required_capabilities(ability, leader, cas)
    if caps != sorted(CAPABILITIES):
        raise CeltieBalanceError(f"capabilities {caps} != {CAPABILITIES}")

    # 技能描述 5 处只读核对（R3：只写技能本体，不改、不返回）。
    text = inputs["text", CID]
    if len(text) != 1 or len(text[0]) != 12:
        raise CeltieBalanceError(f"character_text {CID}: expected one 12-column row")
    action = inputs["action", CODE]
    if [inner for inner, _fields in action] != ["1", "2"]:
        raise CeltieBalanceError(f"action_skill {CODE}: inner keys changed")
    for inner, fields in action:
        if fields[7] != PROGRAMS[inner]:
            raise CeltieBalanceError(f"action_skill {CODE}/{inner}: program {fields[7]!r}")
    server = inputs["server_text", CID]
    if len(server) != 1 or len(server[0]) != 12:
        raise CeltieBalanceError(f"server character_text {CID}: expected one 12-column row")
    problems = description_problems({
        **{f"character_text c{col}": text[0][col] for col in TEXT_DESC_COLUMNS},
        **{f"action_skill {inner} c1": fields[1] for inner, fields in action},
        **{f"server character_text [{col}]": server[0][col] for col in TEXT_DESC_COLUMNS}})
    if problems:
        raise CeltieBalanceError(f"skill description rejected: {problems}")

    trees, tree_notes = {}, []
    for level, program in PROGRAMS.items():
        tree, note = revise_tree(inputs["dsl", program], level)
        problems = dsl_gate_problems(tree)
        if problems:
            raise CeltieBalanceError(f"skill {level} rejected: {problems}")
        trees[program] = tree
        tree_notes.append(note)
    if trees[PROGRAMS["1"]] != trees[PROGRAMS["2"]]:
        raise CeltieBalanceError("skill tiers diverged after revision")

    return {
        "ability": {ABILITY_KEY: ability},
        "leader": {CID: leader},
        "cas": cas,
        "text": {},
        "table": {},
        "action": {},
        "dsl": trees,
        "server_text": {},
        "new_programs": [PROGRAMS["1"], PROGRAMS["2"]],
        "notes": _notes(tree_notes),
    }


def _notes(tree_notes: list) -> dict[str, Any]:
    return {
        "character": f"{CID} {CODE} 希尔媞「追逐光影的课后时光」（校园，风）",
        "source": "wf_balance_20260927c_celtie.py",
        "basis": ["growth_c_spec.md（作者原话 1–6；D1、D3、D4、U5–U8）",
                  "reeval_full.json table.rows 149989 两行、design.characters 149989、critique 两条 minor"],
        "changes": {
            f"leader_ability:{CID}#6": "D134 每层星风心得 → 风队能力伤害：c111/c112 2500→20000（2.5%→20%）",
            f"leader_ability:{CID}#7": "D134 每层星风心得 → 风队攻击力：c111/c112 2500→20000（2.5%→20%）",
            f"ability:{ABILITY_KEY}#2": ("新增 I704（技能旗号 2）：瞬发无触发，前置42 仅队长 + 风 6 人共鸣，"
                                        f"c70={CAS_SWITCH}，行级 c1='false'（与键一致）"),
            "dsl": tree_notes,
            CAS_SWITCH: SWITCH_TEXT,
            CAS_LEADER: {"line6": LEADER_LINE6_AFTER, "line7_added": LEADER_LINE_ADDED,
                         "final": "第 5–6 行删「风属性共鸣时，」（共鸣省略，见 panel_merge）；第 7 行开关行保留共鸣"},
            CAS_A2: "第 2 行删「风属性共鸣时，」（共鸣省略），数值不变",
            CAS_A3: "第 5 / 7 行删「风属性共鸣时，」（共鸣省略），主位图标与数值不变",
            CAS_FEVER: f"{FEVER_TEXT_BEFORE} → {FEVER_TEXT}（旗号 1 强化条目官方格式，点名技能、定性不写数字与秒数）",
            CAS_A1: {"L2": f"{A1_LINES_BEFORE[A1_SWITCH_LINE]} → {A1_LINES_AFTER[A1_SWITCH_LINE]}",
                     "L1": "逐字"},
            "skill_description": {"changed": False, "text": SKILL_DESC,
                                  "places": ["action_skill 1/2 c1", "character_text c5/c7",
                                             "server cdndata/character_text.json [5]/[7]"],
                                  "why": "技能描述只写技能本体（R3）；旗号 2 的不封顶只写在队长强化条目，"
                                         "上一版追加的「担任队长且风属性共鸣时不受此限」撤回，5 处保持 live 原文"},
        },
        "skill_flag_text_rule": {
            "author": "角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,"
                      "规范并简化描述做了吗",
            "entries": {cas_key: {"cas": cas_text, "panel": f"{panel_key}: {panel_line}"}
                        for cas_key, cas_text, panel_key, panel_line in SKILL_FLAG_ENTRIES},
            "flag1_basis": "live 技能两档每个 ConditionalsChangeSkillFlag(1)：关支为空；开支 = 一处 FindAllSubjects(97) "
                           "ACPiercing + FindAllSubjects(33, 风) ACAbilityDamage，其余 24 处命中块 ACToleranceOfElement(风) 降低"
                           "（fever_entry_problems）",
            "leader_line7": "去「Fever模式中，」：开关行（能力1 I704）前置只有 42 + 风共鸣；Fever 判断在技能 DSL 本体里，"
                            "技能描述已写「风属性共鸣且Fever模式中」",
            "checked_by": "text_problems（CAS ↔ 面板同文、点名技能、不写数字、ENHANCED_PHRASES）+ description_problems",
        },
        "values": {
            "tier": "2/3 档（作者「可以砍到2/3」）：25×2/3=16.7，按 5 的倍数且不低于 2/3 下限取 20%（实际 4/5）；"
                    "口径 D1 统一取 20%，不用 17.5%",
            "growth_3min_50_layers": {
                "original": "风队能力伤害 / 攻击力各 +1250%（Fever 中）",
                "batch2": "队长 +125% / +125% ＋ 能力3 +80% / +50%（10 层封顶）",
                "batch3": "队长 +1000% / +1000% ＋ 能力3 +80% / +50%",
                "note": "前 10 层每层能伤 20%+8%=28%（高于原 25%），攻击 20%+5%=25%（等于原值）——表中已告知作者",
            },
            "skill_multiplier_50_layers": {"original": 575, "batch2": 175,
                                           "batch3_leader_resonant": 575, "batch3_otherwise": 175},
        },
        "precedents": {
            "switch_row": f"live {SWITCH_PRECEDENT} 罗尔夫中秋 I704 + 前置42 + 风共鸣（c0/c70 之外逐格同形）",
            "mixed_c1_key": "live 16 个能力键行级 c1 混用（如 1299993、1699991）；整键主位只看首行（AbilityLogic.as:124-126）",
            "flag2_branch": "树内 ConditionalsChangeSkillFlag(2) 分支：live 特克托、罗尔夫中秋；官方零先例（官方旗号 2–4 只用 alv 数值项）",
            "event_in_flag_branch": "官方 18 处事件节点在旗号分支内（8 个文件）",
            "same_binding_both_sides": "两侧复用同一主体绑定号：live 杰拉德、黑豹、本树第二批前已有；官方 0/152",
            "float_cap": "gerald2（1.4.1053）同样把 Bind 上限写成 float 2147483647.0",
        },
        "kept": {
            "ability:1499893#6/#7": "能力3 封顶版 +8%/+5%，最多 10 层（口径 D4）",
            "desc_override_wind_spgirl_campus_1 L1": "战斗开始时技能槽行逐字；L2 旗号 1 条目按 R2 改写（见 skill_flag_text_rule）",
            "desc_override_wind_spgirl_campus_4/5/6": "单行，无依赖星风状态的行，不改",
            "dsl_other_caps": "非共鸣支 / 非 Fever 支 Bind 上限 0 不动；旗号 1 的 25 处分支不动",
        },
        "size": "AMF3 20354→26538 字节（共鸣支整段复制一份，约 +30%）",
        "generator": ("wf_celtie_fever_abilities（能力1 I704 开关 + 平表 change_skill_wind_spgirl_campus_leader）、"
                      "wf_celtie_fever_leader.GAIN_GROWTH_STRENGTH=20000、"
                      "wf_celtie_skill_growth.with_leader_uncapped_growth（build_skill 在 Boss 锁定后调用）、"
                      "wf_campus_panel_text._CELTIE leader/a1/a2/a3/active + native_flat_string_rows（旗号 1 条目）；"
                      "生成器输出 == revise() 输出"
                      "（tests/test_balance_20260927c_celtie.py）"),
        "new_programs": "两棵技能树按第二批做法经 new_programs 登记（候选 manifest 已有则幂等）",
        "capabilities": list(CAPABILITIES),
        "panel_merge": {
            "rule": ("作者「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,引擎点火提供的效果"
                     "就不用写火属性共鸣,其他角色类似」；主会话合并规则（只删前缀的行其余字面逐字相同，数据前置不动）"),
            "resonance_omission": RESONANCE_OMISSION,
            "scan": RESONANCE_SCAN,
            "prefix_dropped_lines": {
                key: {f"L{index + 1}": {"before": before[index], "after": after[index],
                                        "data": [f"{t}:{k}#{i} c{c}={u}" for t, k, i, c, u in refs]}
                      for index, refs in drops.items()}
                for key, before, after, drops in (
                    (CAS_LEADER, LEADER_LINES_NUMERIC, LEADER_LINES_AFTER, LEADER_PREFIX_DROPS),
                    (CAS_A2, A2_LINES_BEFORE, A2_LINES_AFTER, A2_PREFIX_DROPS),
                    (CAS_A3, A3_LINES_BEFORE, A3_LINES_AFTER, A3_PREFIX_DROPS))
            },
            "kept_prefix": {
                CAS_LEADER: {
                    "L4": "获取行",
                    f"L{LEADER_SWITCH_LINE + 1}": (
                        "开关行（主会话口径 2：704/536 技能开关行的共鸣是真实条件，同玛格诺斯队长 L6）：数据 = "
                        f"ability:{ABILITY_KEY}#2 I704（前置 仅队长 + 风属性 6 人共鸣），技能树旗号 2 分支在 "
                        "ConditionalsUnifyElement(4, 6) 共鸣支内；上一版曾按心得层数效果删前缀，本轮恢复"),
                },
                CAS_A3: "L4 / L6 获取行", "other": "不依赖星风状态的行"},
            "merged": "无：同条件组都已在同一行（队长 #0/#1、#6/#7；能力2 #0/#1；能力3 #6/#7）",
            "other_panels": "能力1 / 4 / 5 / 6 覆盖面板无同条件组、无依赖星风状态的行（能力1 只按技能强化文案规范改第 2 行）",
            "check_merge": ("数值稿 / live → 终稿过 mod-tools/wf_panel_merge_check.check（prefix_drops 按上表，Green），"
                            "见测试"),
        },
        "candidate_preexisting_drift": {
            f"ability:{ABILITY_KEY}": ("候选仍是初版 2 行（attack_green / 32 行），live 为 fever 版 211+536；"
                                       "暂存整键替换 ⇒ 候选收敛为 live 2 行 + 本轮开关行（同第二批回写队长键的做法）"),
        },
        "device_check": [
            "当队长且风共鸣时：Fever 中叠到 10 层以上，技能倍率继续涨（75+10×层）；不当队长时停在 175 倍",
            "打开角色页 / 能力1 / 队长页不崩（I704 进能力表、新平表键）",
            "能力1 解锁前开关行不生效（能力行承载的代价，口径 U6 已接受）",
        ],
        "runtime_verified": False,
    }

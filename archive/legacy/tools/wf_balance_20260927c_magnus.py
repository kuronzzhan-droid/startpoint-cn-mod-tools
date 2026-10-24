# -*- coding: utf-8 -*-
"""玛格诺斯「疾风同路」119990 ``lion_swordman_moon``（火）：2026-09-27 平衡第三轮（c）——成长复核 + 技能倍率撤封顶。

口径（主会话 ``growth_c_spec.md``：作者原话 1–6、默认选择 D1–D4 / U2 / U6–U9；数值表 ``reeval_full.json``
``table.rows`` 玛格诺斯 6 行、``design.characters`` 玛格诺斯、``critique``）。输入 = 当前 live（链尾 1.4.1053，
= 第二批 ``wf_balance_20260927b_magnus`` 的输出，逐字核对过）。

改动（其余行、其余列、其余树节点逐字保留）：

1. 队长成长行，只改数值（口径 D3：不新增共鸣前置），基数一律是第二批前的原值，按「≥20% 就近取 5 的倍数、
   2/3 档向上取、≤10% 按 0.5 取」重算（:func:`suggested`）：
   - #1 每 3PF 全队(火)技能伤害 20% → 80%（原 100% × 4/5；火队这项只能靠成长）；
   - #2 每 3PF 全队(火)攻击力 10% → 40%（原 50% × 4/5）；
   - #9 每 3PF 自身技能伤害 5% → 20%（原 25% × 7/10 = 17.5，口径 D1 取 20，实际 4/5）；
   - #10/#11 点火每层自身技能伤害/攻击力 5% → 35%（原 50% × 2/3 = 33.3，向上取 35，实际 0.7）；
   - #12 点火每层全队(火)独立乘区技能伤害 0.5% → 4%（原 5% × 4/5）。
   能力栏封顶版（能力 1#2 限 4 次、能力 2 两行 / 能力 3#4 最多 10 层）按口径 D4 保持第二批值，本模块不读不写。
2. 技能倍率撤封顶（口径 U2/U7）：
   - 特殊强化弹射三档 ``pf_skill_lv1/2/3``：只由队长 #6–#8（629，火编成≥6）调起 ⇒ 点火绑定上限 10 → 99（int，
     与第二批前 live 逐字节相同），不加旗号；
   - 技能两档 ``lion_swordman_moon_1/_2`` 与「引擎之炎」追击 ``ability_skill_…_ignite``（能力 3#1 调起，仅主位、
     不要求共鸣）：根块 [点火绑定 … 块尾] 整段包进 ``ConditionalsChangeSkillFlag(2, 开支, 关支)``：
     开支 = 同一段只把绑定上限改回 99（追击保留第二批削韧 p13 0.2），关支 = live 原段（10 层）逐字。
     分支在局部环境执行（ActionEvaluator.as case 86），绑定挪进分支后分支外看不到 ⇒ 整段入支，
     :func:`variable_scope_problems` 机械核对每个 vlv 消费点都在其绑定的作用域内。
3. 旗号 2 开关行（口径 U6）：能力 ``1199901`` 末尾追加 704 行（前置 42 仅队长 + 火编成≥6，瞬发无触发，
   c70 = 新面板串 ``change_skill_lion_swordman_moon_leader``）。旗号 1 已被 1199901#1 的 536 常驻占用
   （不当队长也开着），不能复用。整行与 live 罗尔夫中秋 1499866#4 同形；零先例的「队长表 704 行」不做。
4. 面板（口径 U8）：队长覆盖文案四处数值同步，并在「自身点火逐层」行后插入旗号 2 强化条目
   「火属性共鸣时，强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升（含引擎之炎）」（不写数字）。
   技能描述（action_skill、character_text、服务端 character_text）不含点火层数与上限（第二批也没写），不改。
6. 面板同条件合并 + 共鸣省略（作者原话「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,
   引擎点火提供的效果就不用写火属性共鸣」；规则与扫描 = 主会话 ``panel_merge/scan.json``，按本轮数值重核）：
   - 队长 L4–L7（数据 #1/#2/#3/#4/#9：火编成≥6 + 每 3 次强化弹射，条件签名逐列相同）合并为一行；
   - 「引擎点火」11999001 的全部获取来源（队长 #4、能力 3 #0/#5 三条 461，全部带火编成≥6；技能 / 引擎之炎 /
     特殊 PF / 722 PF 覆盖 9 棵 DSL 只读不授予）都带火属性共鸣 ⇒ 按层数生效的效果不写「火属性共鸣时，」
     （数据前置不动）：队长 L8（#10/#11）删前缀后与 L9（#12）条件相同，合并为一行；能力 2 唯一一行删前缀。
     依据由 :func:`resonance_omission_problems` 在 revise() 里对**改后**数据机械复核（fail closed）；
   - 其余覆盖面板（能力 1/3/5）无可合并组（能力 3 L2/L3 是 629 追击 + 消耗机制行，按扫描 skip_mechanism 不并），
     无依赖引擎点火且带共鸣的行；能力 4/6 是自动面板，不新建覆盖。
   - 「火属性共鸣时，强化『烈焰轰鸣』…」（能力 1#3 的 704 开关行，前置 42 + 火编成≥6）是真实条件 ⇒ 保留共鸣（主会话口径 2）。
7. 面板按数据改文字（主会话口径 4「面板与数据不符的，按数据改文字，不改数据」）：队长面板冲刺两行
   「自身获得冲刺强化效果…」「冲刺间隔缩短效果不会…」的数据在能力 5 #2/#3（during 422 冲刺参数），前置只有 42（队长）、
   没有火编成≥6 ⇒ 删「火属性共鸣时，」；数据不动。:func:`dash_row_problems` 在 revise() 里核对（fail closed）。
5. 口径 U9：旗号 1（536）在数据里只给主斩劈的倍率加 alv 1.75～3.5（光环半径 200/270 来自技能/技能+两档），
   技能强化条目 ``change_skill_lion_swordman_moon`` 与能力 1 覆盖文案第 2 行由「光环的范围扩大」改为实际效果。
8. 技能强化文案规范（作者原话「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述
   强化后的效果,规范并简化描述」；主会话口径 R1–R4）：强化效果只写在队长 / 能力面板的强化条目里，官方格式
   「强化『<技能名>』：<定性说明>」、点明技能名、不写数字；开关行带共鸣前置 ⇒ 面板行保留「火属性共鸣时，」；
   CAS 键与面板对应行同文（:func:`skill_flag_entry_problems`）：
   - 旗号 1（536）：能力 1 第 2 行「强化自身技能：」→「强化『烈焰轰鸣』：」，与 ``change_skill_lion_swordman_moon`` 同文；
   - 旗号 2（704）：队长面板第 6 行「强化自身技能：技能基础倍率…」→「强化『烈焰轰鸣』：技能倍率…（含引擎之炎）」，
     ``change_skill_lion_swordman_moon_leader`` 补「（含引擎之炎）」同文（旗号 2 同时包住技能两档与引擎之炎）；
   - 能力 1 第 4 行点火倍率行只写技能本体：不写旗号 2 的「担任队长且火属性共鸣时不受此限」（强化效果只在队长强化条目），
     并去掉「及特殊强化弹射」（特殊强化弹射三档点火上限 99 不经旗号，删掉「不受此限」后「含特殊强化弹射，最多10层」
     与数据不符）⇒「自身引擎点火每提升1层，技能基础总倍率＋5倍（含引擎之炎，最多10层）」；
   - 特殊强化弹射三档随点火成长（上限 99、不经旗号，是队长强化弹射本体的效果，不属于技能强化）改写在队长面板第 1 行末尾
     「…，威力随引擎点火层数提升」（主会话决定，不写数字）；:func:`special_pf_growth_problems` 核对三档每段倍率都带
     点火逐层加法项、上限 99、不在旗号分支里。

生成器 ``wf_midautumn_kit_magnus`` 已同步（LEADER / PLAN[1] / CAS_TEXTS / ``leader_gate`` / ``pf_ignition_growth`` /
``build_skill_trees``），测试断言生成器输出 == :func:`revise` 输出。设计镜像（design/magnus.json、
rework1/panel/magnus.json）由 :func:`sync_mirrors` 幂等同步——本单元不写 ``work/character_packs/*``，
由主会话执行 ``python -B -X utf8 mod-tools/wf_balance_20260927c_magnus.py --write``。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包，不发布，不 git。
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
import wf_dsl
import wf_midautumn_kitlib as KL

CID = "119990"
CODE = "lion_swordman_moon"
PACKAGES = ["ma-magnus"]
#: 候选 ``work/character_packs/ma-magnus/package/manifest.json`` 现值 1.0.2（第二批已回写）→ 下一号。
PACKAGE_VERSION = {"ma-magnus": "1.0.3"}
#: 704 行与改后各行都不需要新的客户端能力（候选已声明 dash-parameter-v1 / panel-description-override-v2）。
CAPABILITIES: list[str] = []
#: 候选与 live 在本模块读取的 20 项上逐字相同（2026-09-27 只读核对，链尾 1.4.1054，候选 1.0.2 = 第二批回写）。
REVIEWED_DRIFT: dict = {}

UID = "11999001"                   # 固有「引擎点火」（99 层 / 99999999 帧，不动）
IGNITION_VARIABLE = 11999005       # DSL vlv 变量号
ELEMENT = 0                        # 火（0 基内部元素）
ELEMENT_TOKEN = "Red"
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
MAIN_ICON = " <icon id='main'>  "

A1 = f"{CID}1"
A2 = f"{CID}2"
#: 能力 2–6：共鸣省略依据（引擎点火获取来源 / 依赖行）只读；能力 2 另改面板（删共鸣前缀）。
BASIS_ABILITIES = tuple(f"{CID}{slot}" for slot in range(2, 7))
CAS_LEADER = f"desc_override_{CODE}"
CAS_SLOT1 = f"desc_override_{CODE}_1"
CAS_SLOT2 = f"desc_override_{CODE}_2"
CAS_SWITCH = f"change_skill_{CODE}"                 # 旗号 1（536）条目（U9 改文案）
CAS_SWITCH_LEADER = f"change_skill_{CODE}_leader"   # 旗号 2（704）条目（新键）

PROGRAMS = (
    f"battle/action/skill/action/rare5/{CODE}${CODE}_1",
    f"battle/action/skill/action/rare5/{CODE}${CODE}_2",
    f"battle/action/skill/action/ability_skill/ability_skill_{CODE}_ignite$ability_skill_{CODE}_ignite",
    *(f"battle/action/skill/action/ability_skill/{CODE}_pf_skill${CODE}_pf_skill_lv{n}" for n in (1, 2, 3)),
)
GATED_PROGRAMS = PROGRAMS[:3]      # 技能两档 + 引擎之炎：旗号 2 分支
PF_SKILL_PROGRAMS = PROGRAMS[3:]   # 特殊强化弹射三档：直接撤封顶
CHASE_PROGRAM = PROGRAMS[2]
#: 队长 #0 的 722 强化弹射覆盖（power_flip_action ``lion_swordman_moon_pf`` 三档）：共鸣省略依据只读，不改。
PF_OVERRIDE_KEY = f"{CODE}_pf"
PF_OVERRIDE_PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_OVERRIDE_KEY}${PF_OVERRIDE_KEY}_lv{n}"
                             for n in (1, 2, 3))
#: 引擎点火可能的 DSL 授予点全集：技能两档（= 换形 ``_voice_ready`` 两档同路径）、629（引擎之炎 / 特殊 PF 三档）、
#: 722 PF 覆盖三档。行里调起的 629 / 722 必须都在这里（:func:`invoked_program_problems`）。
BASIS_PROGRAMS = PROGRAMS + PF_OVERRIDE_PROGRAMS

#: live 输入基线（2026-09-27 本地链尾 1.4.1054 只读取数，与候选 ma-magnus 1.0.2 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", CID): "f0da86cf6ffc1426f17fe356c8dd526c061d5909ed18ac999d56b06207dc9ced",
    ("ability", A1): "75a0629814d80495835394d55a17acc6ef4c6da80c7e18c1643fcfb8662219f4",
    ("ability", BASIS_ABILITIES[0]): "81542cbc3df91ced658426f1212f29d657bc1ef8eb09243f870ce28b6858f9aa",
    ("ability", BASIS_ABILITIES[1]): "9cb6e5fe3cbe20806a322d378aa99f77eb35b443fc55caa0af308b013b2d6d06",
    ("ability", BASIS_ABILITIES[2]): "8e94991c6b845b714094013d623a3a509f272c94dce78479df98e6d17727ecda",
    ("ability", BASIS_ABILITIES[3]): "f9fe9485b204d4506fcc0f7d6068c929668acfa3eaf975a6eb4809415746f640",
    ("ability", BASIS_ABILITIES[4]): "bcceec84f61c86403c6f9f94c0b984a8a0482f4391d2da3a583b2c4f942a05cf",
    ("cas", CAS_LEADER): "0d3f8a9a74de8c48085fa9b5d858aac01b3f073af4d2f075c08832b26cc3a19c",
    ("cas", CAS_SLOT1): "cc7067ec3b3120e98ea925f49dc38d0d7306c0a916c876b539174b34d5a2aebc",
    ("cas", CAS_SLOT2): "e456e02fda03ba99ebda9ec6ae87feafbdc5bbd67b6f7f8fff2f52766d87509c",
    ("cas", CAS_SWITCH): "db90d1af647ad3e1e4b558be89fdc62782a1a24d70efa2c817d22ec2a0c97572",
    ("dsl", PROGRAMS[0]): "e0f1c5277c2614d531731332ca0b65e15c5d9a034b8cc2400357810d277607be",
    ("dsl", PROGRAMS[1]): "da560c0338ba40ae356e44d2ffc9db5e0de72c8ec511ed9eb404697bd7943ed6",
    ("dsl", PROGRAMS[2]): "41cc356cc8783b76f449180b2b01fedbf20a70c9c95ed529d11bea2976e2e153",
    ("dsl", PROGRAMS[3]): "ecf2d2cf2076bca32c082c521a88382d3142e4213de90f9d36f94ec9f8eba6f1",
    ("dsl", PROGRAMS[4]): "8f28b7c87bc2b0543d76c67783dd9e167babd6cfe2ef17e58942a3219224baf6",
    ("dsl", PROGRAMS[5]): "716ec64bc6fa0b160208105b84bada21f123f9e92ab54d68f29e67142976b979",
    ("dsl", PF_OVERRIDE_PROGRAMS[0]): "52f63f245ba9d8381ea07084554b793768fe0bef0515f704ac0ef5016cec2855",
    ("dsl", PF_OVERRIDE_PROGRAMS[1]): "1d95443767d0e4eda706f4fc47f294c0a2c01669a787a511be51e149705eaec0",
    ("dsl", PF_OVERRIDE_PROGRAMS[2]): "750901af3d43e667e0fcf32f4ee2bb7f3e64b4e8c3defab6d7940eb0e54bf3e5",
}
#: 新键：live 里必须不存在（read 抛 KeyError），存在 ⇒ 拒绝。
ABSENT: tuple[tuple[str, str], ...] = (("cas", CAS_SWITCH_LEADER),)

# ------------------------------------------------------------------ 数值（口径：作者原话 4–6 + D1/D2）

#: 队长成长行：下标 → (强度两列, 第二批前原值, 第二批现值, 本轮新值, 档位系数, 说明)。
#: 第二批现值 = 原值 × 第二批系数（每 3PF ×1/5、点火逐层 ×1/10），:func:`leader_rows` 逐行核对。
LEADER_GROWTH: dict[int, tuple[tuple[int, int], str, str, str, Fraction, str]] = {
    1: ((49, 50), "100000", "20000", "80000", Fraction(4, 5), "每3PF 全队(火)技能伤害"),
    2: ((49, 50), "50000", "10000", "40000", Fraction(4, 5), "每3PF 全队(火)攻击力"),
    9: ((49, 50), "25000", "5000", "20000", Fraction(7, 10), "每3PF 自身技能伤害"),
    10: ((111, 112), "50000", "5000", "35000", Fraction(2, 3), "点火每层 自身技能伤害"),
    11: ((111, 112), "50000", "5000", "35000", Fraction(2, 3), "点火每层 自身攻击力"),
    12: ((111, 112), "5000", "500", "4000", Fraction(4, 5), "点火每层 全队(火)独立乘区技能伤害"),
}
BATCH2_FACTOR = {1: Fraction(1, 5), 2: Fraction(1, 5), 9: Fraction(1, 5),
                 10: Fraction(1, 10), 11: Fraction(1, 10), 12: Fraction(1, 10)}
LEADER_ROWS = 13


def suggested(original: str, factor: Fraction) -> str:
    """表里的取整规则（reeval summary「取整规则」+ 口径 D1/D2）：强度 1000 = 1%。

    - 原值 ≤10%：按 0.5% 取（5 的倍数只剩 5/10，会跳档）；原值 >10%：取 5% 的倍数；
    - 2/3 档一律向上取（不得低于 2/3 下限），其余就近取、恰在中点向上（25×7/10 = 17.5 → 20，口径 D1）。
    """
    value = Fraction(int(original)) * factor
    # 1% = 1000 强度单位 ⇒ 0.5% = 500，5% = 5000；原值 ≤10%（≤10000）按 0.5% 取
    step = Fraction(500) if int(original) <= 10000 else Fraction(5000)
    units = value / step
    count = math.ceil(units) if factor == Fraction(2, 3) else math.floor(units + Fraction(1, 2))
    return str(int(count * step))


# ------------------------------------------------------------------ 行指纹（全部非空列；其余列必须为空）

_FIRE_LEADER = {4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN}
_PF3_LEADER = {0: CODE, 1: "0", 3: "0", **_FIRE_LEADER, 11: "0", 18: "0", 25: "2", 28: "300000",
               29: "300000", 32: "(None)", 33: "0", 37: "(None)", 44: "0"}
_LAYER_LEADER = {0: CODE, 1: "0", 3: "1", 11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0",
                 98: "100000", 99: "100000", 100: "(None)", 102: UID, 106: "false", 108: "0"}
LEADER_BEFORE: dict[int, dict[int, str]] = {
    1: {**_PF3_LEADER, 45: "34", 46: "5", 47: ELEMENT_TOKEN, 49: "20000", 50: "20000"},
    2: {**_PF3_LEADER, 45: "32", 46: "5", 47: ELEMENT_TOKEN, 49: "10000", 50: "10000"},
    9: {**_PF3_LEADER, 45: "34", 46: "0", 49: "5000", 50: "5000"},
    10: {**_LAYER_LEADER, **_FIRE_LEADER, 107: "2", 111: "5000", 112: "5000"},
    11: {**_LAYER_LEADER, **_FIRE_LEADER, 107: "0", 111: "5000", 112: "5000"},
    12: {**_LAYER_LEADER, 4: "0", 107: "411", 108: "5", 109: ELEMENT_TOKEN, 111: "500", 112: "500"},
}
#: 队长 #6–#8：特殊强化弹射三档的 629 调用方（前置 2 火≥6，触发 63/64/65）——撤封顶的依据，逐格核对不改。
PF_CALLERS = {6 + n: {0: CODE, 1: "0", 3: "0", **_FIRE_LEADER, 11: "0", 12: "0", 18: "0", 25: str(63 + n),
                      28: "100000", 29: "100000", 32: "(None)", 33: "0", 37: "(None)", 44: "0", 45: "629",
                      46: "0", 68: f"override_string_{CODE}_pf", 69: PF_SKILL_PROGRAMS[n]}
              for n in range(3)}

_FIRE_ABILITY = {6: "2", 9: "600000", 10: "600000", 11: ELEMENT_TOKEN}
A1_BEFORE: tuple[dict[int, str], ...] = (
    {0: f"{CODE}_1", 1: "true", 2: "action_skill", 3: "0", 5: "0", 6: "0", 13: "0", 20: "0", 27: "0",
     39: "(None)", 46: "0", 47: "211", 48: "0", 51: "50000", 52: "50000"},
    {0: f"{CODE}_1", 1: "true", 2: "action_skill", 3: "0", 5: "0", **_FIRE_ABILITY, 13: "0", 20: "0",
     27: "0", 39: "(None)", 46: "0", 47: "536", 70: CAS_SWITCH},
    {0: f"{CODE}_1", 1: "true", 2: "action_skill", 3: "0", 5: "0", **_FIRE_ABILITY, 13: "0", 20: "0",
     27: "2", 30: "300000", 31: "300000", 34: "4", 35: "0", 39: "(None)", 46: "0", 47: "34", 48: "0",
     51: "25000", 52: "25000"},
)
#: 旗号 2 开关行（口径 U6）：瞬发（c3=0、c5=0）、无触发（c27=0）、前置 1 = 42 队长、前置 2 = 火编成≥6。
SKILL_FLAG = 2
SKILL_FLAG_KIND = "704"
SWITCH_ROW: dict[int, str] = {0: f"{CODE}_1", 1: "true", 2: "action_skill", 3: "0", 5: "0",
                              6: "42", 13: "2", 16: "600000", 17: "600000", 18: ELEMENT_TOKEN, 20: "0",
                              27: "0", 39: "(None)", 46: "0", 47: SKILL_FLAG_KIND, 70: CAS_SWITCH_LEADER}
SWITCH_DESCRIBE = f"队长 且 火·编成≥6 时: 自身 切换技能Flag{SKILL_FLAG}[{CAS_SWITCH_LEADER}]"
SWITCH_PRECEDENT = ("1499866", 4)   # live 罗尔夫中秋：同形 704 + 前置 42 + 风编成≥6

# ------------------------------------------------------------------ DSL

IGNITION_CAP = (10, 99)            # (第二批封顶 = 关支 / 非队长, 第二批前 = 开支 / 特殊 PF)
BIND_HEAD = ["BindConditionAccumulationVariable", -17, IGNITION_VARIABLE, ["DCUnique", int(UID)], 1]
CHASE_DOWN = 0.2                   # 第二批（口径 B3/B6）追击 CreateNormalAttack p13，开关两支都保留

# ------------------------------------------------------------------ 面板（改前 → 改后）

OLD_LEADER_LINES = (
    "火属性共鸣时，自身的强化弹射变为特殊强化弹射，造成的伤害按技能伤害结算",
    "火属性共鸣时，自身获得冲刺强化效果，冲刺冷却时间－30%",
    "火属性共鸣时，冲刺间隔缩短效果不会让自身的冲刺冷却时间进一步缩短",
    "火属性共鸣时，每发动3次强化弹射，火属性角色技能伤害＋20%、攻击力＋10%",
    "火属性共鸣时，每发动3次强化弹射，自身技能伤害＋5%",
    "火属性共鸣时，每发动3次强化弹射，火属性角色技能槽＋5%",
    "火属性共鸣时，每发动3次强化弹射，自身引擎点火＋7层",
    "火属性共鸣时，引擎点火每提升1层，自身技能伤害＋5%、攻击力＋5%",
    "自身引擎点火每提升1层，火属性角色技能伤害额外乘区＋0.5%",
    "自身持有「烈焰光环」期间，每次弹射，连击＋35",
)
#: 旗号 2（704）强化条目：官方格式「强化『<技能名>』：<定性说明>」，与 CAS_SWITCH_LEADER 同文（:func:`skill_flag_entry_problems`）。
SKILL_NAME = "烈焰轰鸣"
LEADER_SKILL_LINE = "火属性共鸣时，强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升（含引擎之炎）"
LEADER_SKILL_LINE_AT = 8           # 插在「自身点火逐层」行（设计稿「第 8 行」）之后（下标指合并前 11 行）
#: 队长第 1 行 = 队长 #0（722 强化弹射覆盖）+ #6–#8（629 调起特殊强化弹射三档，火编成≥6）。三档伤害树每段
#: CreateNormalAttack 的倍率都带引擎点火逐层加法项（vlv 11999005 = min(层数, 绑定上限)，本轮上限 99、不经旗号）
#: ⇒ 威力随点火层数提升是队长强化弹射本体的效果（不属于技能强化 R1），主会话决定写在这一行末尾，不写数字；
#: 数据依据由 :func:`special_pf_growth_problems` 在 revise() 里对改后数据机械复核（fail closed）。
SPECIAL_PF_GROWTH = "，威力随引擎点火层数提升"
SPECIAL_PF_LINE = OLD_LEADER_LINES[0] + SPECIAL_PF_GROWTH
#: 本轮数值、逐效果一行（合并前形态）：面板合并与共鸣省略的来源（check_merge 的 orig）。
UNMERGED_LEADER_LINES = (
    SPECIAL_PF_LINE, OLD_LEADER_LINES[1], OLD_LEADER_LINES[2],
    "火属性共鸣时，每发动3次强化弹射，火属性角色技能伤害＋80%、攻击力＋40%",
    "火属性共鸣时，每发动3次强化弹射，自身技能伤害＋20%",
    OLD_LEADER_LINES[5], OLD_LEADER_LINES[6],
    "火属性共鸣时，引擎点火每提升1层，自身技能伤害＋35%、攻击力＋35%",
    LEADER_SKILL_LINE,
    "自身引擎点火每提升1层，火属性角色技能伤害额外乘区＋4%",
    OLD_LEADER_LINES[9],
)

RESONANCE_PREFIX = "火属性共鸣时，"
#: 队长面板同条件合并组（作者原话「同一个条件的提升能不能写到一起来简化描述」）。
#: ``rows`` = 队长表数据行（0 起），条件签名（:func:`condition_signature`，比较时去掉 ``drop`` 里的共鸣）逐列相同，
#: 且面板里没有别的行同签名；``lines`` = 合并前面板行下标（0 起），合并行放在组首行位置；``omit`` = 删掉
#: 「火属性共鸣时，」的来源行（依据：引擎点火全部获取来源带火共鸣，:func:`resonance_omission_problems`）。
#: 写法「<条件>，<对象A><效果1>＋x%、<效果2>＋y%，<对象B><效果3>＋z%」：效果原措辞与数值保留，只省略重复对象名。
LEADER_MERGE_GROUPS: tuple[dict[str, Any], ...] = (
    dict(rows=(1, 2, 3, 4, 9), drop=(), lines=(3, 4, 5, 6), omit=(),
         text="火属性共鸣时，每发动3次强化弹射，火属性角色技能伤害＋80%、攻击力＋40%、技能槽＋5%，"
              "自身技能伤害＋20%、引擎点火＋7层"),
    # 条件措辞取 scan.json 的「自身引擎点火每提升1层」（L9 原措辞；L8 删前缀后同条件）
    dict(rows=(10, 11, 12), drop=(ELEMENT_TOKEN,), lines=(7, 9), omit=(7,),
         text="自身引擎点火每提升1层，自身技能伤害＋35%、攻击力＋35%，火属性角色技能伤害额外乘区＋4%"),
)


def merged_lines(lines: tuple[str, ...], groups: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    """合并行放在组首行位置，组内其余行去掉；未合并行逐字、原序。"""
    out = list(lines)
    gone: set[int] = set()
    for group in groups:
        first, *rest = group["lines"]
        out[first] = group["text"]
        gone.update(rest)
    return tuple(line for index, line in enumerate(out) if index not in gone)


#: 口径 4（主会话 2026-09-27「面板与数据不符的，按数据改文字，不改数据」）：队长面板冲刺两行（合并前下标 1/2）的数据
#: 在能力 5 #2/#3（during 422 冲刺参数），前置只有 42（队长）、没有火编成≥6 ⇒ 删「火属性共鸣时，」。
A5 = f"{CID}5"
DASH_KIND = "422"
DASH_ROWS = (2, 3)                 # 能力 5 数据行（0 起）
DASH_LINES = (1, 2)                # UNMERGED_LEADER_LINES 下标（0 起）
LEADER_PRECONDITION = "42"


def prefix_dropped(lines: tuple[str, ...], indexes: tuple[int, ...]) -> tuple[str, ...]:
    """把 ``indexes`` 行的「火属性共鸣时，」删掉，其余逐字（行必须真带前缀）。"""
    for index in indexes:
        if not lines[index].startswith(RESONANCE_PREFIX):
            raise ValueError(f"line {index} carries no {RESONANCE_PREFIX!r}: {lines[index]}")
    return tuple(line.removeprefix(RESONANCE_PREFIX) if index in indexes else line
                 for index, line in enumerate(lines))


NEW_LEADER_LINES = merged_lines(prefix_dropped(UNMERGED_LEADER_LINES, DASH_LINES), LEADER_MERGE_GROUPS)
#: 按引擎点火层数生效、已省略共鸣的面板行：(键, 改后行下标) ↔ 依赖该状态的数据行（dt 134 固有 11999001）。
OMITTED_LINES = ((CAS_LEADER, NEW_LEADER_LINES.index(LEADER_MERGE_GROUPS[1]["text"])), (CAS_SLOT2, 0))
OMITTED_ROWS = (("leader", CID, (10, 11)), ("ability", A2, (0, 1)))
#: 口径 4 改过的面板行：(键, 改后行下标) ↔ 能力 5 #2/#3（没有共鸣前置）。
DASH_PANEL_LINES = tuple((CAS_LEADER, NEW_LEADER_LINES.index(UNMERGED_LEADER_LINES[i].removeprefix(RESONANCE_PREFIX)))
                         for i in DASH_LINES)

OLD_SLOT2 = "火属性共鸣时，引擎点火每提升1层，自身技能伤害＋15%、攻击力＋15%（最多10层）"
NEW_SLOT2 = OLD_SLOT2.removeprefix(RESONANCE_PREFIX)

OLD_SLOT1_LINES = (
    "战斗开始时，自身技能槽＋50%",
    "火属性共鸣时，强化自身技能：光环范围扩大",
    "火属性共鸣时，每发动3次强化弹射，自身技能伤害＋25%（最多4次）",
    "自身引擎点火每提升1层，技能基础总倍率＋5倍（含引擎之炎及特殊强化弹射，最多10层）",
)
#: 能力 1 第 2 行 = 旗号 1（536）强化条目（与 CAS_SWITCH 同文）；第 4 行只写技能本体（点火绑定 10 层），
#: 旗号 2 撤封顶只写在队长强化条目（R3），特殊强化弹射三档不经旗号、上限 99 ⇒ 不再写进「最多10层」的括注。
NEW_SLOT1_LINES = (
    OLD_SLOT1_LINES[0],
    "火属性共鸣时，强化『烈焰轰鸣』：斩劈的技能倍率提升",
    OLD_SLOT1_LINES[2],
    "自身引擎点火每提升1层，技能基础总倍率＋5倍（含引擎之炎，最多10层）",
)
SLOT1_SKILL_FLAG_LINE = 1          # 536 条目：不写数字与时间

OLD_SWITCH_TEXT = "强化『烈焰轰鸣』：光环的范围扩大"
NEW_SWITCH_TEXT = "强化『烈焰轰鸣』：斩劈的技能倍率提升"
SWITCH_LEADER_TEXT = "强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升（含引擎之炎）"
SKILL_FLAG_TEXTS = (CAS_SWITCH, CAS_SWITCH_LEADER)
#: 强化条目 CAS ↔ 面板行（R2：同一条强化两处写法一致，面板行 = 开关行真实前置「火属性共鸣时，」+ CAS 原文）。
SKILL_FLAG_PANEL_LINES = ((CAS_SWITCH, CAS_SLOT1, SLOT1_SKILL_FLAG_LINE),
                          (CAS_SWITCH_LEADER, CAS_LEADER, None))
#: R3：强化后的效果不写在强化条目以外（技能描述、面板其余行）。
ENHANCED_PHRASES = ("不受此限", "强化后", "强化自身技能", "强化技能")


class MagnusCBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise MagnusCBalanceError(f"unreviewed live baseline for {kind}:{key} "
                                  f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _absent(read: Callable[[str, Any], Any], kind: str, key: str) -> None:
    try:
        read(kind, key)
    except KeyError:
        return
    raise MagnusCBalanceError(f"{kind}:{key} already exists in live (revision re-applied or key clash)")


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise MagnusCBalanceError(message)


def _changed_cells(before: list[list[str]], after: list[list[str]]) -> set[tuple[int, int]]:
    return {(i, c) for i, (a, b) in enumerate(zip(before, after))
            for c, (x, y) in enumerate(zip(a, b)) if x != y}


def row_from_cells(cells: dict[int, str], width: int) -> list[str]:
    return [cells.get(col, "") for col in range(width)]


# ------------------------------------------------------------------ 队长 / 能力

def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """6 条成长行只改强度两列；#0、#3–#8（含特殊 PF 调用方 #6–#8）逐字不动。"""
    _require(len(rows) == LEADER_ROWS and all(len(r) == LEADER_NCOLS for r in rows),
             f"leader {CID}: expected {LEADER_ROWS}×{LEADER_NCOLS}")
    for index, cells in LEADER_BEFORE.items():
        _require(_matches(rows[index], LEADER_NCOLS, cells), f"leader {CID}#{index} drifted")
    for index, cells in PF_CALLERS.items():
        _require(_matches(rows[index], LEADER_NCOLS, cells),
                 f"leader {CID}#{index} (特殊强化弹射 629 调用方) drifted — 撤封顶依据要重核")
    out = deepcopy(rows)
    expected: set[tuple[int, int]] = set()
    for index, (cols, original, current, new, factor, _label) in LEADER_GROWTH.items():
        _require(Fraction(int(original)) * BATCH2_FACTOR[index] == int(current),
                 f"leader #{index}: batch-2 value {current} is not original {original} × {BATCH2_FACTOR[index]}")
        _require(suggested(original, factor) == new,
                 f"leader #{index}: {new} != rounding rule({original} × {factor})")
        for col in cols:
            _require(out[index][col] == current, f"leader #{index} c{col} preimage {out[index][col]!r}")
            out[index][col] = new
            expected.add((index, col))
    if _changed_cells(rows, out) != expected:
        raise AssertionError(f"leader touched {_changed_cells(rows, out) ^ expected} beyond the growth cells")
    return out


def ability1_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力 1：#0–#2 逐字不动，末尾追加旗号 2 开关行（704）。"""
    _require(len(rows) == len(A1_BEFORE) and all(len(r) == ABILITY_NCOLS for r in rows),
             f"ability {A1}: expected {len(A1_BEFORE)}×{ABILITY_NCOLS}")
    for index, cells in enumerate(A1_BEFORE):
        _require(_matches(rows[index], ABILITY_NCOLS, cells), f"ability {A1}#{index} drifted")
    _require(not [r for r in rows if r[47] in ("704", "705", "706", "707", "708")],
             f"ability {A1} already carries a flag-2+ row")
    return deepcopy(rows) + [row_from_cells(SWITCH_ROW, ABILITY_NCOLS)]


# ------------------------------------------------------------------ 面板

def _single_text(rows: list[list[str]], key: str) -> str:
    _require(len(rows) == 1 and len(rows[0]) == 1, f"{key}: expected one single-column row")
    return rows[0][0]


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    _require(tuple(_single_text(rows, CAS_LEADER).split("\n")) == OLD_LEADER_LINES,
             f"{CAS_LEADER}: unexpected panel text")
    return [["\n".join(NEW_LEADER_LINES)]]


def slot1_text(rows: list[list[str]]) -> list[list[str]]:
    _require(tuple(_single_text(rows, CAS_SLOT1).split("\n")) == OLD_SLOT1_LINES,
             f"{CAS_SLOT1}: unexpected panel text")
    return [["\n".join(NEW_SLOT1_LINES)]]


def switch_text(rows: list[list[str]]) -> list[list[str]]:
    _require(_single_text(rows, CAS_SWITCH) == OLD_SWITCH_TEXT, f"{CAS_SWITCH}: unexpected text")
    return [[NEW_SWITCH_TEXT]]


def slot2_text(rows: list[list[str]]) -> list[list[str]]:
    """能力 2：唯一一行按引擎点火层数生效 ⇒ 删「火属性共鸣时，」，其余逐字。"""
    _require(_single_text(rows, CAS_SLOT2) == OLD_SLOT2, f"{CAS_SLOT2}: unexpected panel text")
    return [[NEW_SLOT2]]


_EFFECT_TOKEN = re.compile(r"[＋－]\d+(?:\.\d+)?(?:%|层|倍)?")


def merge_text_problems(lines: tuple[str, ...], groups: tuple[dict[str, Any], ...]) -> list[str]:
    """合并行自检：效果数值记号多重集合 == 来源行之和；共鸣前缀只在 ``omit`` 行删（删了就不写回），
    其余来源都带前缀时合并行也带；合并行不带「／」与主位图标（逐词核对由测试里的 check_merge 做）。"""
    problems: list[str] = []
    for number, group in enumerate(groups):
        sources = [lines[i] for i in group["lines"]]
        want = Counter(token for line in sources for token in _EFFECT_TOKEN.findall(line))
        got = Counter(_EFFECT_TOKEN.findall(group["text"]))
        if want != got:
            problems.append(f"merge group {number}: effect tokens {dict(got)} != sources {dict(want)}")
        for index in group["omit"]:
            if not lines[index].startswith(RESONANCE_PREFIX):
                problems.append(f"merge group {number}: omit line {index} carries no resonance prefix")
        kept = [lines[i].startswith(RESONANCE_PREFIX) for i in group["lines"] if i not in group["omit"]]
        if group["text"].startswith(RESONANCE_PREFIX) != all(kept):
            problems.append(f"merge group {number}: resonance prefix does not follow its sources")
        if "／" in group["text"] or MAIN_ICON.strip() in group["text"]:
            problems.append(f"merge group {number}: ／ or main icon in the merged line")
    return problems


def panel_problems(texts: dict[str, str]) -> list[str]:
    """面板规则：kitlib 禁语；技能强化条目（536/704 串、能力 1 第 2 行、队长旗号 2 行）不写数字与时间；
    本模块改的面板都不是主位槽 ⇒ 不许带主位图标；不用「／」分行；按引擎点火层数生效的行不写共鸣。"""
    problems: list[str] = []
    for key, text in texts.items():
        if "／" in text:
            problems.append(f"{key}: uses ／ as a line separator")
        for index, line in enumerate(text.split("\n")):
            flag = (key in SKILL_FLAG_TEXTS
                    or (key == CAS_SLOT1 and index == SLOT1_SKILL_FLAG_LINE)
                    or (key == CAS_LEADER and line == LEADER_SKILL_LINE))
            problems += [f"{key}#{index}: {p}" for p in KL.panel_problems(line, skill_flag=flag)]
            if MAIN_ICON.strip() in line:
                problems.append(f"{key}#{index}: main icon on a non-main-only panel")
            if re.search(r"属性共鸣时[：:,]", line):
                problems.append(f"{key}#{index}: resonance must read 「火属性共鸣时，」")
            if (key, index) in OMITTED_LINES and "共鸣" in line:
                problems.append(f"{key}#{index}: ignition-layer effect still names the resonance")
            if (key, index) in DASH_PANEL_LINES and "共鸣" in line:
                problems.append(f"{key}#{index}: dash line names a resonance its data (ability {A5}) does not have")
            for phrase in ENHANCED_PHRASES:
                if phrase in line:
                    problems.append(f"{key}#{index}: {phrase!r} — enhancement entries name the skill "
                                    f"(强化『{SKILL_NAME}』), enhanced effects stay in those entries")
    return problems + skill_flag_entry_problems(texts)


def skill_flag_entry_problems(texts: dict[str, str]) -> list[str]:
    """R2：强化条目用官方格式「强化『烈焰轰鸣』：<定性说明>」；CAS 键与面板对应行同文（面板行 = 「火属性共鸣时，」+ CAS，
    开关行 536/704 都带火编成≥6 前置）。只检查 ``texts`` 里同时给出的键。"""
    problems: list[str] = []
    entry = f"强化『{SKILL_NAME}』："
    for cas_key, panel_key, index in SKILL_FLAG_PANEL_LINES:
        if cas_key not in texts:
            continue
        if not texts[cas_key].startswith(entry):
            problems.append(f"{cas_key}: skill-flag entry must read 「{entry}…」")
        if panel_key not in texts:
            continue
        lines = texts[panel_key].split("\n")
        want = RESONANCE_PREFIX + texts[cas_key]
        found = lines[index] == want if index is not None else want in lines
        if not found:
            problems.append(f"{panel_key}: panel entry of {cas_key} must read 「{want}」")
    return problems


# ------------------------------------------------------------------ 面板合并 / 共鸣省略的数据依据

#: 列布局（与主会话 scan 同口径）：前置三块基址、瞬发触发 it / 触发前置 ipc / 延迟 / 效果块 ic、
#: 持续触发 dat / dt / 死亡、触发类型列、觉醒两列、c1（主位）。
_LAYOUT: dict[str, dict[str, Any]] = {
    "leader": dict(pre=(4, 11, 18), it=25, ipc=37, idelay=44, ic=45, dat=83, dt=95, dead=106, dc=107,
                   trig=3, awake=(1, 2), unison=None),
    "ability": dict(pre=(6, 13, 20), it=27, ipc=39, idelay=46, ic=47, dat=85, dt=97, dead=108, dc=109,
                    trig=5, awake=(3, 4), unison=1),
}
GRANT_KINDS = ("461", "413", "436", "459")           # 付与固有状态（自身/友方、敌方…）
CONSUME_KINDS = ("525",)                              # 消耗固有状态
PRE_UNIQUE = ("144", "187", "188", "199")             # 前置块按固有状态判定
DT_UNIQUE = ("134", "194", "207", "171", "192")       # 持续触发按固有状态计数
#: 引擎点火的全部获取来源（改后数据；逐条都带火编成≥6）。多一条 / 少一条 ⇒ 共鸣省略要重核。
IGNITION_SOURCES = (f"leader:{CID}#4", f"ability:{CID}3#0", f"ability:{CID}3#5")


def _n(value: str) -> str:
    value = (value or "").strip()
    return "" if value in ("(None)", "0", "false") else value


def _trigger(row: list[str], table: str) -> str:
    value = row[_LAYOUT[table]["trig"]].strip()
    return value if value in ("0", "1", "2") else "0"


def preconditions(row: list[str], table: str) -> list[tuple[str, ...]]:
    """前置块（7 格：种类、puller、puller 组、下限、上限、属性组、固有号）；空 / 0 / 1（恒真）不计。"""
    out = []
    for base in _LAYOUT[table]["pre"]:
        kind = row[base].strip()
        if kind in ("", "0", "1", "(None)"):
            continue
        out.append((kind, *(_n(row[base + i]) for i in range(1, 7))))
    return out


def resonance_of(block: tuple[str, ...]) -> str | None:
    """前置块是「X 编成≥6」（共鸣）⇒ 属性组串（如 ``Red``），否则 None。"""
    kind, _puller, puller_group, low, high, group, _uid = block
    if (kind == "2" and low == "600000" and high in ("600000", "") and group and not puller_group
            and all(token in ("Red", "Blue", "Yellow", "Green", "White", "Black") for token in group.split(","))):
        return group
    return None


def condition_signature(row: list[str], table: str, drop: tuple[str, ...] = ()) -> str:
    """数据条件签名：前置（去掉 ``drop`` 里的共鸣）+ 触发类型 + 觉醒 + c1 + 瞬发触发/触发前置/延迟/效果后缀
    或 持续触发/死亡。效果种类、对象、数值不在签名里（合并的正是这些）。"""
    layout = _LAYOUT[table]
    trigger = _trigger(row, table)
    keep = [block for block in preconditions(row, table)
            if resonance_of(block) is None or resonance_of(block) not in drop]
    sig: dict[str, Any] = dict(trig=trigger, pre=sorted(keep),
                               awake=[_n(row[col]) for col in layout["awake"]])
    if layout["unison"] is not None:
        sig["unison"] = row[layout["unison"]].strip()
    if trigger == "0":
        it, ipc, ic = layout["it"], layout["ipc"], layout["ic"]
        sig["it"] = [_n(row[it + i]) for i in range(12)]
        sig["ipc"] = [_n(row[ipc + i]) for i in range(7)]
        sig["delay"] = _n(row[layout["idelay"]])
        sig["suffix"] = [_n(row[ic + i]) for i in (10, 11, 14, 15, 16, 17, 18, 25)]
    elif trigger == "1":
        sig["dat"] = [_n(row[layout["dat"] + i]) for i in range(12)]
        sig["dt"] = [_n(row[layout["dt"] + i]) for i in range(11)]
        sig["dead"] = _n(row[layout["dead"]])
    else:
        sig["opening"] = True
    return json.dumps(sig, ensure_ascii=False, sort_keys=True)


def merge_group_problems(leader: list[list[str]]) -> list[str]:
    """每个合并组：组内数据行条件签名逐列相同，且队长表里没有组外行同签名（组是完整的）。"""
    problems: list[str] = []
    for number, group in enumerate(LEADER_MERGE_GROUPS):
        sigs = {index: condition_signature(leader[index], "leader", group["drop"]) for index in range(len(leader))}
        inside = {sigs[index] for index in group["rows"]}
        if len(inside) != 1:
            problems.append(f"merge group {number}: rows {group['rows']} differ in data conditions")
            continue
        outside = [index for index, sig in sigs.items() if sig in inside and index not in group["rows"]]
        if outside:
            problems.append(f"merge group {number}: rows {outside} share the condition but are not merged")
    return problems


def uid_roles(row: list[str], table: str) -> list[tuple[int, str]]:
    """该行里每个写着引擎点火固有号的格：grant（获取）/ depends（按层数或持有生效）/ consume / unknown。"""
    layout = _LAYOUT[table]
    roles = []
    for col, value in enumerate(row):
        if value.strip() != UID:
            continue
        if any(col == base + 6 and row[base].strip() in PRE_UNIQUE for base in layout["pre"]):
            role = "depends"
        elif col == layout["dt"] + 7 and row[layout["dt"]].strip() in DT_UNIQUE:
            role = "depends"
        elif col in (layout["dat"] + 10, layout["it"] + 10):
            role = "depends"
        elif col == layout["ipc"] + 6 and row[layout["ipc"]].strip() in ("1", "2", "3"):
            role = "depends"
        elif col == layout["ic"] + 21 and row[layout["ic"]].strip() in GRANT_KINDS:
            role = "grant"
        elif col == layout["ic"] + 21 and row[layout["ic"]].strip() in CONSUME_KINDS:
            role = "consume"
        else:
            role = "unknown"
        roles.append((col, role))
    return roles


def dsl_uid_roles(tree) -> list[tuple[tuple, str]]:
    """DSL 里引擎点火固有号的出现处：``["DCUnique", UID]`` = read（点火绑定），``["ACUnique", UID, …]`` = grant，
    其余位置 = unknown。"""
    uid = int(UID)
    out: list[tuple[tuple, str]] = []

    def walk(node, path: tuple) -> None:
        if isinstance(node, list):
            if len(node) >= 2 and node[0] in ("DCUnique", "ACUnique") and node[1] == uid:
                out.append((path, "read" if node[0] == "DCUnique" else "grant"))
                return
            for index, child in enumerate(node):
                walk(child, path + (index,))
        elif isinstance(node, dict):
            for key, child in node.items():
                walk(child, path + (key,))
        elif node in (uid, UID) and not isinstance(node, bool):
            out.append((path, "unknown"))

    walk(tree, ())
    return out


def invoked_program_problems(tables: dict[tuple[str, str], list[list[str]]]) -> list[str]:
    """行里调起的 629 程序 / 722 PF 覆盖必须都在 :data:`BASIS_PROGRAMS` 已读的范围内（否则授予点没查到）。"""
    problems: list[str] = []
    for (table, key), rows in tables.items():
        layout = _LAYOUT[table]
        for index, row in enumerate(rows):
            ic, dc = layout["ic"], layout["dc"]
            if row[ic].strip() == "629" and row[ic + 24] not in BASIS_PROGRAMS:
                problems.append(f"{table}:{key}#{index}: 629 program {row[ic + 24]!r} not read")
            for col in (ic + 35, dc + 11):
                if col < len(row) and row[col] not in ("", "(None)") and row[col] != PF_OVERRIDE_KEY:
                    problems.append(f"{table}:{key}#{index}: PF override {row[col]!r} not read")
    return problems


def resonance_omission_problems(tables: dict[tuple[str, str], list[list[str]]], trees: dict[str, Any]) -> list[str]:
    """共鸣省略依据（作者原话「引擎点火的获取带火属性共鸣,引擎点火提供的效果就不用写火属性共鸣」）：

    引擎点火的**全部**获取来源——队长 / 能力 1–6 的授予行，技能（= 换形）/ 629 / 722 PF 覆盖 DSL 的授予节点——
    都带火编成≥6 前置时才成立。任一行把固有号写在认不出的格、DSL 出现授予或认不出的引用、来源集合变化、
    某来源不带火共鸣 ⇒ 报错（revise() 拒绝，面板省略要重核）。
    """
    problems: list[str] = []
    sources: list[str] = []
    for (table, key), rows in tables.items():
        for index, row in enumerate(rows):
            label = f"{table}:{key}#{index}"
            for col, role in uid_roles(row, table):
                if role == "unknown":
                    problems.append(f"{label} c{col}: ignition id in an unrecognised column")
                elif role == "grant":
                    sources.append(label)
                    resonances = {resonance_of(block) for block in preconditions(row, table)} - {None}
                    if ELEMENT_TOKEN not in resonances:
                        problems.append(f"{label}: grants 引擎点火 without the fire resonance precondition")
    for program, tree in trees.items():
        for path, role in dsl_uid_roles(tree):
            if role != "read":
                problems.append(f"{program} {path}: DSL {role} of 引擎点火 (resonance omission needs review)")
    if tuple(sources) != IGNITION_SOURCES:
        problems.append(f"引擎点火 sources {sources} != reviewed {list(IGNITION_SOURCES)}")
    problems += invoked_program_problems(tables)
    for table, key, indexes in OMITTED_ROWS:
        rows = tables[(table, key)]
        for index in indexes:
            row = rows[index] if index < len(rows) else None
            if (row is None or (_LAYOUT[table]["dt"] + 7, "depends") not in uid_roles(row, table)
                    or ELEMENT_TOKEN not in {resonance_of(b) for b in preconditions(row, table)}):
                problems.append(f"{table}:{key}#{index}: omitted-resonance line no longer maps to a fire-gated "
                                f"ignition-layer row")
    return problems


def dash_row_problems(tables: dict[tuple[str, str], list[list[str]]]) -> list[str]:
    """口径 4 的数据依据：已读各表里的冲刺参数行（422）恰好是能力 5 #2/#3，前置带 42（队长）且没有任何属性共鸣。
    任一行补上共鸣、换了位置或别处多出 422 行 ⇒ 报错（revise() 拒绝，冲刺两行的文案要重核）。"""
    problems: list[str] = []
    found: list[tuple[str, str, int]] = []
    for (table, key), rows in tables.items():
        layout = _LAYOUT[table]
        for index, row in enumerate(rows):
            if DASH_KIND in (row[layout["ic"]].strip(), row[layout["dc"]].strip()):
                found.append((table, key, index))
    if found != [("ability", A5, index) for index in DASH_ROWS]:
        problems.append(f"dash-parameter rows {found} != reviewed ability {A5} #{list(DASH_ROWS)}")
    for table, key, index in found:
        blocks = preconditions(tables[(table, key)][index], table)
        if LEADER_PRECONDITION not in {block[0] for block in blocks}:
            problems.append(f"{table}:{key}#{index}: dash row lost the leader precondition 42")
        resonances = {resonance_of(block) for block in blocks} - {None}
        if resonances:
            problems.append(f"{table}:{key}#{index}: dash row now requires resonance {sorted(resonances)} "
                            f"(panel dropped 「{RESONANCE_PREFIX}」)")
    return problems


def row_gate_problems(kind: str, row: list[str], cas_keys: set[str]) -> list[str]:
    """词条门禁：合法性 / 声明块字段 / 629 文案键 / 元素列 / capability。"""
    table = "leader_ability" if kind == "leader" else "ability"
    problems = [f"legality: {p}" for p in L.client_legality_problems(table, row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems(table, row)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, cas_keys, kind=table)]
    problems += [f"kitlib {name}: {p}" for name, found in KL.row_problems(table, row, ELEMENT).items()
                 for p in found]
    caps = L.required_client_capabilities(table, row)
    if caps and set(caps) - {"dash-parameter-v1"}:
        problems.append(f"capabilities {caps}")
    if (kind == "ability" and row[5] == "0" and row[47] in ("536", "704", "705", "706", "707", "708")
            and row[70] not in cas_keys):
        problems.append(f"skill-flag row c70 {row[70]!r} has no custom_ability_string in this batch")
    return problems


# ------------------------------------------------------------------ DSL

def _binds(tree) -> list[list]:
    return list(wf_dsl.iter_dsl_commands(tree, "BindConditionAccumulationVariable"))


def _flags(tree) -> list[list]:
    return list(wf_dsl.iter_dsl_commands(tree, "ConditionalsChangeSkillFlag"))


def _check_live_tree(tree, program: str) -> None:
    _require(isinstance(tree, list) and tree and tree[0] == "ActionDsl" and tree[10] == 0,
             f"{program}: unexpected root (buffTargetAs must stay 0 = skill damage)")
    _require(tree[11][0] == "Block" and tree[11][1], f"{program}: empty root block")
    _require(_binds(tree) == [[*BIND_HEAD, IGNITION_CAP[0]]],
             f"{program}: ignition binding drifted (want one cap-{IGNITION_CAP[0]} bind): {_binds(tree)}")
    _require(tree[11][1][0] == ["Command", [*BIND_HEAD, IGNITION_CAP[0]]],
             f"{program}: ignition binding is not the root's first command")
    _require(not _flags(tree), f"{program}: already carries a ConditionalsChangeSkillFlag")
    users = [attack[6][0].get("vlv") for attack in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")]
    _require(users and all(v and [x["vid"] for x in v] == [IGNITION_VARIABLE] for v in users),
             f"{program}: every CreateNormalAttack must scale with the ignition variable")
    if program == CHASE_PROGRAM:
        downs = [a[13] for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")]
        _require(downs == [[{"min": CHASE_DOWN, "max": CHASE_DOWN}]],
                 f"{program}: batch-2 chase p13 drifted: {downs}")


def gate_tree(tree) -> list:
    """根块整段 → ``[ConditionalsChangeSkillFlag(2, Block[同段·上限 99], Block[原段])]``。"""
    out = deepcopy(tree)
    body = out[11][1]
    opened = deepcopy(body)
    opened[0][1][5] = IGNITION_CAP[1]
    out[11][1] = [["Command", ["ConditionalsChangeSkillFlag", SKILL_FLAG,
                               ["Block", opened], ["Block", deepcopy(body)]]]]
    return out


def branches(tree) -> tuple[list, list]:
    """``(开支块, 关支块)``；根块不是唯一一条旗号 2 分支 ⇒ 拒绝。"""
    body = tree[11][1]
    _require(len(body) == 1 and body[0][0] == "Command"
             and body[0][1][0] == "ConditionalsChangeSkillFlag" and body[0][1][1] == SKILL_FLAG,
             "root is not a single ConditionalsChangeSkillFlag(2)")
    return body[0][1][2], body[0][1][3]


def revise_tree(tree, program: str) -> list:
    """特殊 PF 三档：绑定上限 10 → 99；技能两档 / 引擎之炎：旗号 2 分支（开支 99 / 关支 10）。"""
    _check_live_tree(tree, program)
    if program in PF_SKILL_PROGRAMS:
        out = deepcopy(tree)
        out[11][1][0][1][5] = IGNITION_CAP[1]
        back = deepcopy(out)
        back[11][1][0][1][5] = IGNITION_CAP[0]
        if back != tree:
            raise AssertionError(f"{program}: touched more than the binding cap")
        return out
    _require(program in GATED_PROGRAMS, f"{program}: not a magnus skill program")
    out = gate_tree(tree)
    opened, closed = branches(out)
    if closed != tree[11]:
        raise AssertionError(f"{program}: closed branch differs from the live root")
    back = deepcopy(opened)
    back[1][0][1][5] = IGNITION_CAP[0]
    if back != tree[11]:
        raise AssertionError(f"{program}: open branch differs from the live root beyond the cap")
    return out


def variable_scope_problems(tree) -> list[str]:
    """vlv 变量作用域（复核意见：作用域门禁只查主体 lookup，不查 vlv 变量号）。

    保守模型：``BindConditionAccumulationVariable`` 只对**同一块里其后的兄弟及其后代**可见；
    分支 / 事件 / 判定区的子块是局部环境，里面绑定的变量不外泄（Environment 只向外层查找）。
    任一 vlv 消费点不在其变量的作用域内 ⇒ 报错（客户端会把该项当 0，点火倍率静默失效）。
    """
    problems: list[str] = []

    def walk(node, scope: frozenset, path: tuple) -> None:
        if isinstance(node, dict):
            for item in node.get("vlv") or ():
                if item.get("vid") not in scope:
                    problems.append(f"vlv vid {item.get('vid')} at {path} is outside its binding scope "
                                    f"(visible: {sorted(scope) or 'none'})")
            for key, child in node.items():
                walk(child, scope, path + (key,))
            return
        if not isinstance(node, list):
            return
        if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
            local = set(scope)
            for index, item in enumerate(node[1]):
                walk(item, frozenset(local), path + (1, index))
                if (isinstance(item, list) and len(item) == 2 and item[0] == "Command"
                        and isinstance(item[1], list) and item[1]
                        and item[1][0] == "BindConditionAccumulationVariable"):
                    local.add(item[1][2])
            return
        for index, child in enumerate(node):
            walk(child, scope, path + (index,))

    walk(tree, frozenset(), ())
    return problems


def dsl_gate_problems(tree) -> list[str]:
    """四道 DSL 门 + vlv 作用域 + AMF3 往返。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    problems += [f"variable: {p}" for p in variable_scope_problems(tree)]
    problems += [f"player_side: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


def special_pf_growth_problems(leader: list[list[str]], trees: dict[str, list]) -> list[str]:
    """队长第 1 行「…，威力随引擎点火层数提升」的数据依据（改后数据）：

    - 队长 #6–#8 逐格 = :data:`PF_CALLERS`（629、火编成≥6，调起 ``pf_skill_lv1/2/3``）；
    - 三档根块首条 = 点火绑定（DCUnique 11999001、除数 1）、上限 99，且根块不是旗号分支（开关两态同上限）；
    - 每段 CreateNormalAttack 倍率都带且只带该变量的加法项、系数 > 0（层数越多倍率越高）。
    """
    problems: list[str] = []
    for index, cells in PF_CALLERS.items():
        if index >= len(leader) or not _matches(leader[index], LEADER_NCOLS, cells):
            problems.append(f"leader {CID}#{index}: special-PF 629 caller drifted")
    for program in PF_SKILL_PROGRAMS:
        tree = trees.get(program)
        if tree is None:
            problems.append(f"{program}: special-PF tree not in this revision")
            continue
        if _flags(tree):
            problems.append(f"{program}: special-PF growth must not depend on a skill flag")
        if tree[11][1][:1] != [["Command", [*BIND_HEAD, IGNITION_CAP[1]]]]:
            problems.append(f"{program}: root does not open with the cap-{IGNITION_CAP[1]} ignition binding")
        attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
        if not attacks:
            problems.append(f"{program}: no CreateNormalAttack")
        for number, attack in enumerate(attacks):
            terms = [term.get("vlv") for term in attack[6]]
            if not (len(terms) == 1 and terms[0] and [x.get("vid") for x in terms[0]] == [IGNITION_VARIABLE]
                    and terms[0][0].get("min") == 0 and terms[0][0].get("max", 0) > 0):
                problems.append(f"{program} CreateNormalAttack[{number}]: multiplier does not grow with "
                                f"ignition layers ({attack[6]})")
    return problems


def layer_cap(tree, *, flag_on: bool) -> int | float:
    """模拟客户端取哪一支：根块是旗号 2 分支时按 ``flag_on`` 取开/关支，否则取根块；返回该支绑定上限。"""
    body = tree[11][1]
    if body and body[0][0] == "Command" and body[0][1][0] == "ConditionalsChangeSkillFlag":
        block = body[0][1][2] if flag_on else body[0][1][3]
    else:
        block = tree[11]
    head = block[1][0]
    _require(head[0] == "Command" and head[1][:5] == BIND_HEAD, "branch does not start with the binding")
    return head[1][5]


# ------------------------------------------------------------------ 入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader = _checked(read, "leader", CID)
    a1 = _checked(read, "ability", A1)
    basis = {key: _checked(read, "ability", key) for key in BASIS_ABILITIES}
    cas = {key: _checked(read, "cas", key) for key in (CAS_LEADER, CAS_SLOT1, CAS_SLOT2, CAS_SWITCH)}
    trees = {program: _checked(read, "dsl", program) for program in PROGRAMS}
    pf_trees = {program: _checked(read, "dsl", program) for program in PF_OVERRIDE_PROGRAMS}
    for kind, key in ABSENT:
        _absent(read, kind, key)

    new_leader = leader_rows(leader)
    ability = {A1: ability1_rows(a1)}
    texts = {CAS_LEADER: leader_text(cas[CAS_LEADER]), CAS_SLOT1: slot1_text(cas[CAS_SLOT1]),
             CAS_SLOT2: slot2_text(cas[CAS_SLOT2]),
             CAS_SWITCH: switch_text(cas[CAS_SWITCH]), CAS_SWITCH_LEADER: [[SWITCH_LEADER_TEXT]]}

    problems = panel_problems({key: rows[0][0] for key, rows in texts.items()})
    problems += merge_text_problems(UNMERGED_LEADER_LINES, LEADER_MERGE_GROUPS)
    problems += merge_group_problems(new_leader)
    cas_keys = {f"override_string_{CODE}_pf", f"ability_skill_{CODE}_ignite", CAS_SWITCH, CAS_SWITCH_LEADER}
    for index, row in enumerate(new_leader):
        problems += [f"leader#{index}: {p}" for p in row_gate_problems("leader", row, cas_keys)]
    for key, rows in ability.items():
        for index, row in enumerate(rows):
            problems += [f"{key}#{index}: {p}" for p in row_gate_problems("ability", row, cas_keys)]
        KL.check_ability_key(rows, key, CODE, 1)
    new_trees = {}
    for program, tree in trees.items():
        new_trees[program] = revise_tree(tree, program)
        problems += [f"{program}: {p}" for p in dsl_gate_problems(new_trees[program])]
    # 共鸣省略依据按**改后**数据复核（本轮新增的 704 行、分支树都算进来源扫描）
    tables = {("leader", CID): new_leader, ("ability", A1): ability[A1],
              **{("ability", key): rows for key, rows in basis.items()}}
    problems += [f"resonance omission: {p}"
                 for p in resonance_omission_problems(tables, {**new_trees, **pf_trees})]
    problems += [f"dash text: {p}" for p in dash_row_problems(tables)]
    if NEW_LEADER_LINES[0] != SPECIAL_PF_LINE:
        problems.append(f"{CAS_LEADER}#0: special-PF line must read 「{SPECIAL_PF_LINE}」")
    problems += [f"special PF growth: {p}" for p in special_pf_growth_problems(new_leader, new_trees)]
    if problems:
        raise MagnusCBalanceError(f"revision rejected: {problems}")

    return {
        "leader": {CID: new_leader},
        "ability": ability,
        "cas": texts,
        "text": {}, "table": {}, "action": {}, "server_text": {},
        "dsl": new_trees,
        "new_programs": [],
        "notes": _notes(),
    }


def _pct(strength: str) -> str:
    value = Fraction(int(strength), 1000)
    return f"{float(value):g}%"


def _notes() -> dict[str, Any]:
    return {
        "source": "wf_balance_20260927c_magnus.py",
        "character": f"{CID} {CODE} 玛格诺斯「疾风同路」（火）",
        "scope": "第三轮 c：队长成长行数值回调（作者原话 3–6，口径 D1–D4）＋ 技能倍率撤封顶（U2/U6/U7）"
                 "＋ 面板（U8）＋ 旗号 1 条目改实际效果（U9）＋ 面板同条件合并 / 引擎点火效果行省略共鸣；"
                 "能力栏封顶版（D4）、充能行、削韧不动",
        "changes": {
            **{f"leader_ability:{CID}#{i} c{cols[0]}/c{cols[1]}":
               f"{cur} → {new}（{label}：原 {_pct(orig)} / 第二批 {_pct(cur)} / 本轮 {_pct(new)}，档位 {factor}）"
               for i, (cols, orig, cur, new, factor, label) in LEADER_GROWTH.items()},
            f"ability:{A1}#3 (新)": f"{SWITCH_DESCRIBE}（704 瞬发无触发；先例 live 1499866#4）",
            f"custom_ability_string:{CAS_SWITCH_LEADER} (新)": SWITCH_LEADER_TEXT,
            f"custom_ability_string:{CAS_SWITCH}": f"{OLD_SWITCH_TEXT} → {NEW_SWITCH_TEXT}（U9）",
            f"custom_ability_string:{CAS_LEADER}": "四处成长数值同步；第 1 行末尾补「，威力随引擎点火层数提升」"
                                                   "（特殊强化弹射三档随点火成长，上限 99 不经旗号）；"
                                                   "第 8 行后插入旗号 2 强化条目「强化『烈焰轰鸣』…」行；"
                                                   "同条件合并两组 + 点火逐层行省略火属性共鸣（10 → 7 行）；"
                                                   "冲刺两行删「火属性共鸣时，」（口径 4：数据在能力 5 #2/#3，"
                                                   "前置只有 42 队长）",
            f"custom_ability_string:{CAS_SLOT2}": f"{OLD_SLOT2} → {NEW_SLOT2}（引擎点火效果行省略共鸣）",
            f"custom_ability_string:{CAS_SLOT1}": "第 2 行 536 条目改实际效果（U9）并点名『烈焰轰鸣』（R2，与 CAS 同文）；"
                                                  "第 4 行只写技能本体：去「及特殊强化弹射」（特殊 PF 上限 99 不经旗号），"
                                                  "不写旗号 2 的「不受此限」（R3，强化效果只在队长强化条目）",
            "skill_flag_text_rule": {
                "author": "角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,"
                          "规范并简化描述做了吗",
                "entries": {CAS_SWITCH: NEW_SWITCH_TEXT, CAS_SWITCH_LEADER: SWITCH_LEADER_TEXT},
                "panel_lines": {f"{CAS_SLOT1}#{SLOT1_SKILL_FLAG_LINE}": NEW_SLOT1_LINES[SLOT1_SKILL_FLAG_LINE],
                                f"{CAS_LEADER}#{NEW_LEADER_LINES.index(LEADER_SKILL_LINE)}": LEADER_SKILL_LINE},
                "slot1_line4": f"{OLD_SLOT1_LINES[3]} → {NEW_SLOT1_LINES[3]}",
                "checked_by": "skill_flag_entry_problems（CAS ↔ 面板同文、点名技能）+ panel_problems（ENHANCED_PHRASES）",
                "special_pf_growth": "特殊强化弹射三档的点火逐层倍率（上限 99，只在火共鸣当队长时出现）不再写进能力 1 第 4 行；"
                                     "主会话决定改写在队长第 1 行末尾：" + SPECIAL_PF_LINE
                                     + "（队长强化弹射本体的效果，不属于技能强化；定性不写数字）",
                "special_pf_basis": "pf_skill_lv1/2/3 根块首条 Bind(-17, 11999005, DCUnique 11999001, 1, 99)，"
                                    "每段 CreateNormalAttack 倍率带 vlv 11999005 加法项（系数 > 0）；调用方 = 队长 #6–#8 "
                                    "（629、火编成≥6）；special_pf_growth_problems 在 revise() 里复核",
            },
            "dsl pf_skill_lv1/2/3 root[0] Bind p5": "10 → 99（与第二批前 live 逐字节相同）",
            "dsl 技能两档 + 引擎之炎 root": "整段包进 ConditionalsChangeSkillFlag(2)：开支 Bind p5 = 99，关支 = live 原段（10）",
        },
        "rounding": "≤10% 按 0.5% 取、>10% 取 5% 的倍数；2/3 档向上取；其余就近（中点向上）。"
                    "#9 7/10 档 17.5 → 20（口径 D1，实际 4/5）；#10/#11 2/3 档 33.3 → 35（实际 0.7）",
        "front_layers": "能力栏封顶版与队长行叠加：#9 前 4 次每次 20%+25% = 45%（原 25%）；"
                        "#10/#11 前 10 层每层 35%+15% = 50% = 原值；#12 前 10 层每层 4%+1% = 5% = 原值（reeval summary 已列，作者知情项）",
        "three_minutes": {
            "#1": "19 次：原 1900% / 第二批 380% / 本轮 1520%",
            "#2": "19 次：原 950% / 第二批 190% / 本轮 760%",
            "#9": "19 次：原 475% / 第二批 95%+100% / 本轮 380%+100% = 480%（复核：略高于原值，D1 已定取 20）",
            "#10/#11": "常驻 40 层：原 2000% / 第二批 200%+150% / 本轮 1400%+150%",
            "#12": "常驻 40 层：原 200% / 第二批 20%+10% / 本轮 160%+10%",
            "skill_multiplier": "40 层额外倍率：原 +200 倍 / 第二批 +50 倍 / 本轮 当队长且火共鸣（能力 1 已解锁）+200 倍、其他 +50 倍",
        },
        "flag": {
            "why_flag_2": "旗号 1 = 1199901#1 的 536（火编成≥6，c1=true），不当队长也开着 ⇒ 不能区分队长；旗号 2–6 空闲",
            "row": f"ability:{A1}#3 = 704、前置 42 队长 + 火编成≥6、瞬发无触发（持续块写旗号 = C2308）",
            "tree": "ConditionalsChangeSkillFlag(2, 开支, 关支)：Resolver 判 hasAbilityPower(2)；分支在局部环境执行",
            "pf_skill": "特殊强化弹射三档只由队长 #6–#8（629，火编成≥6，触发 63/64/65）调起 ⇒ 直接恢复 99，不加旗号",
            "caveat": "开关行在能力 1：能力 1 未解锁时当队长也保持 10 层（设计稿风险 2；凯尔、黑豹先例同）",
        },
        "precedents": {
            "704 + 前置 42 能力行": "live 罗尔夫中秋 1499866#4（同形，只差 c0/c2/c18/c70）；官方 704 能力行 11 行（无前置 42）",
            "整根包进旗号分支": "live 杰拉德 149999 技能根部 ConditionalsChangeSkillFlag(1, [Bind…], […])",
            "树内判旗号 2": "live 特克托（护盾）、罗尔夫中秋；官方树对旗号 2–4 只用 alv2–4 数值项，零分支先例",
            "两侧复用绑定号": "live 杰拉德、黑豹、校园希尔媞；官方 152 例两侧从不复用",
        },
        "panel_merge": {
            "author": ["同一个条件的提升能不能写到一起来简化描述",
                       "引擎点火的获取带火属性共鸣,引擎点火提供的效果就不用写火属性共鸣,其他角色类似"],
            "leader_groups": [
                {"data_rows": f"leader_ability:{CID}#{','.join(map(str, g['rows']))}",
                 "panel_lines_before": [UNMERGED_LEADER_LINES[i] for i in g["lines"]],
                 "resonance_dropped_for_signature": list(g["drop"]),
                 "merged": g["text"]}
                for g in LEADER_MERGE_GROUPS],
            "leader_line_count": f"{len(UNMERGED_LEADER_LINES)} → {len(NEW_LEADER_LINES)}",
            "ability2": f"{OLD_SLOT2} → {NEW_SLOT2}",
            "omission_basis": "引擎点火 11999001 全部获取来源 = " + "、".join(IGNITION_SOURCES)
                              + "（三条 461 全带火编成≥6）；技能两档（= 换形 voice_ready）、引擎之炎、特殊 PF 三档、"
                                "722 PF 覆盖三档共 9 棵 DSL 只有 DCUnique 读取、无 ACUnique 授予；依赖行 = 队长 #10–#12、"
                                "能力 2 #0/#1、能力 3 #1–#4。revise() 对改后数据机械复核（resonance_omission_problems）",
            "kept_resonance": [
                "队长 L4–L7 合并行：条件本身是「火编成≥6 + 每 3 次强化弹射」，不依赖引擎点火 ⇒ 保留",
                "队长「火属性共鸣时，强化『烈焰轰鸣』…」行："
                "数据是能力 1#3 的 704 行（前置 42 队长 + 火编成≥6），共鸣是真实门、不按点火层数生效 ⇒ 保留"
                "（主会话口径 2：704/536 开关行的共鸣是真实条件）",
                "队长 L7「…自身引擎点火＋7层」、能力 3 L1/L6：引擎点火的获取行 ⇒ 保留",
            ],
            "data_text_fix": {
                "rule": "主会话口径 4：面板与数据不符的，按数据改文字，不改数据",
                "lines": [UNMERGED_LEADER_LINES[i] + " → " + UNMERGED_LEADER_LINES[i].removeprefix(RESONANCE_PREFIX)
                          for i in DASH_LINES],
                "data": f"ability:{A5}#{DASH_ROWS[0]}/#{DASH_ROWS[1]}（during 422 冲刺参数 -30% / 疾走抵消 +245%）："
                        "前置只有 42（队长），没有火编成≥6 ⇒ 不共鸣时照样生效；数据不动",
                "checked_by": "dash_row_problems（422 行集合、前置 42、无共鸣；fail closed）",
            },
            "not_merged": [
                "能力 3 L2/L3（同条件：点火≥1 + 敌技能命中 CT0.6 秒）是 629 追击「引擎之炎」与消耗 1 层的机制行，"
                "按扫描 skip_mechanism 不并",
                "能力 1、能力 5：各行数据条件互异；能力 4/6 为自动面板，不新建覆盖文案",
            ],
            "checked_by": "wf_midautumn_kitlib.panel_problems + wf_panel_merge_check.check（测试逐字 + check 通过；"
                          "prefix_drops = 点火逐层行 + 冲刺两行）",
        },
        "deviations": [
            "面板合并：队长 L8+L9 合并行的条件措辞按 scan.json proposed 取「自身引擎点火每提升1层」（L9 原措辞；"
            "主会话转述的示例写「引擎点火每提升1层」，任务注明以 scan 为准核对措辞）",
            "口径 U8「技能描述（action_skill 两档）写（最多N层，担任队长且X属性共鸣时不受此限）」已被作者 2026-09-27"
            "「技能里面不要重复描述强化后的效果」取代（主会话口径 R3）：技能描述、character_text、服务端 character_text "
            "不含点火层数与上限，不改；能力 1 覆盖文案第 4 行只写本体「最多10层」，旗号 2 的不封顶只写在队长强化条目",
            "设计稿「队长覆盖文案第 8 行后插入」按 1 起算解读：插在「火属性共鸣时，引擎点火每提升1层，自身技能伤害…」之后、"
            "火队独立乘区行之前（0 起算第 8 行）",
            "口径 U9 除技能强化条目 change_skill_lion_swordman_moon 外，同步改了能力 1 覆盖文案第 2 行"
            "（desc_override 盖掉自动文案，玩家实际看到的是这一行）",
        ],
        "open_points": [
            "真机：角色详情页 / 能力 1 面板 / 队长页不崩（能力表 704 + 前置 42 新组合、新面板串）",
            "真机：当队长且火共鸣（能力 1 已解锁）叠满 10 层以上，技能与引擎之炎倍率继续涨；不当队长时在 10 层停住",
            "真机：当队长且火共鸣时特殊强化弹射三档倍率随点火继续涨（>10 层）",
            "树内判旗号 2 官方零先例（客户端通用 hasAbilityPower(n)，静态已证实）",
            "真机：队长面板 7 行 / 能力 2 面板显示完整（合并行较长，看是否换行截断）",
        ],
        "capabilities": list(CAPABILITIES),
        "runtime_verified": False,
    }


# ------------------------------------------------------------------ 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/magnus.json"
PANEL_REL = BATCH / "rework1/panel/magnus.json"

MIRROR_TAG = "balance_20260927c"
MIRROR_NOTE_PREFIX = "2026-09-27：平衡第三轮"
MIRROR_NOTE = (MIRROR_NOTE_PREFIX + "（成长复核 + 技能倍率撤封顶）——每3次强化弹射 火队技伤/攻 队长 20%/10%→80%/40%、"
               "自身技伤 5%→20%；引擎点火每层 自身技伤/攻 队长 5%→35%、火队独立乘区 0.5%→4%（能力栏封顶版不动）；"
               "特殊强化弹射三档点火倍率恢复不封顶；技能与引擎之炎在「担任队长且火属性共鸣」时不封顶"
               "（能力1 追加旗号2 开关行），其他情况仍最多10层。能力1 旗号1 条目改为实际效果（斩劈倍率提升）。"
               "技能强化条目统一写「强化『烈焰轰鸣』：…」（队长、能力1 与 CAS 同文），强化后的效果不写在强化条目以外"
               "（能力1 点火倍率行删「担任队长且火属性共鸣时不受此限」与「及特殊强化弹射」）；"
               "特殊强化弹射随引擎点火成长是队长强化弹射本体的效果，写在队长第1行末尾「，威力随引擎点火层数提升」。"
               "面板：队长同条件的提升合并成一行（每3次强化弹射的五项、引擎点火逐层的三项），"
               "按引擎点火层数生效的效果不再写「火属性共鸣时，」（引擎点火的获取都带火属性共鸣；队长、能力2），队长 11→7 行；"
               "队长冲刺两行删「火属性共鸣时，」（数据在能力5 前置42 队长承载行，不要求共鸣；按数据改文字）。")


def _cells_json(cells: dict[int, str]) -> dict[str, str]:
    return {str(col): value for col, value in cells.items()}


def _plan_entry(item, index: int | None, old: dict | None = None) -> dict[str, Any]:
    donor, source, cells, expect = item
    entry = dict(old or {})
    if index is not None:
        entry["index"] = index
    entry.update(donor=donor, source=source, cells=_cells_json(cells), desc_expected=expect)
    return entry


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等）。能力 1 记录数 3 → 4、面板串新增一条。"""
    import wf_midautumn_kit_magnus as K
    design, panel = deepcopy(design), deepcopy(panel)

    plan = design["plan_rework1"]
    block = plan["leader_ability"]
    rows = block["rows"]
    block["rows"] = [_plan_entry(item, index, rows[index] if index < len(rows) else None)
                     for index, item in enumerate(K.LEADER)]
    block["row_count"] = len(K.LEADER)
    for slot in (1, 2, 3):
        records = plan["ability"]["keys"][f"{CID}{slot}"]["records"]
        if len(records) > len(K.PLAN[slot]):
            raise ValueError(f"design mirror {CID}{slot} has more records than the kit")
        plan["ability"]["keys"][f"{CID}{slot}"]["records"] = [
            _plan_entry(item, None if index < len(records) else index,
                        records[index] if index < len(records) else None)
            for index, item in enumerate(K.PLAN[slot])]
    strings = plan["texts"]["custom_ability_string"]["rows"]
    for row in strings:
        if row.get("key") in K.CAS_TEXTS:
            row["text"] = K.CAS_TEXTS[row["key"]]
    present = {row.get("key") for row in strings}
    for key, text in K.CAS_TEXTS.items():
        if key not in present:
            strings.append({"key": key, "text": text})
    plan[MIRROR_TAG] = dict(
        spec="第三轮：队长成长行按原值回调（火队技伤/攻 ×4/5、自身每3PF 技伤 20%、点火逐层自身 ×2/3 取 35%、"
             "火队独立乘区 ×4/5）；特殊强化弹射三档点火上限 10→99；技能两档与引擎之炎根块包进 "
             "ConditionalsChangeSkillFlag(2)（开支 99 / 关支 10），能力1 末行 704（前置 42 队长 + 火编成≥6）开旗号；"
             "旗号1 条目改实际效果",
        changed=["leader#1 全队技伤 20%→80%", "leader#2 全队攻 10%→40%", "leader#9 自身技伤 5%→20%",
                 "leader#10/#11 点火每层 5%→35%", "leader#12 点火每层独立乘区 0.5%→4%",
                 f"{A1}#3 新增 704 旗号2 开关行", "pf_skill_lv1/2/3 点火上限 10→99",
                 "技能两档 + 引擎之炎 旗号2 分支（开支 99 / 关支 10）", "change_skill 条目改实际效果",
                 "队长面板同条件合并（L4–L7、L8+L9）11→7 行", "引擎点火效果行省略火属性共鸣（队长、能力2）",
                 "队长冲刺两行删火属性共鸣（数据 能力5 #2/#3 只有前置 42 队长；按数据改文字）",
                 "队长第1行补「威力随引擎点火层数提升」（特殊强化弹射三档随点火成长，上限 99 不经旗号）"],
        panel_merge=[dict(data_rows=list(g["rows"]), merged=g["text"]) for g in LEADER_MERGE_GROUPS],
        ignition_caps={"closed": K.IGNITION_DSL_CAP, "open": K.IGNITION_LEADER_CAP},
        skill_flag={"flag": K.LEADER_SKILL_FLAG, "kind": K.LEADER_SKILL_FLAG_KIND,
                    "text_key": K.SWITCH_LEADER_STRING},
        module="mod-tools/wf_balance_20260927c_magnus.py",
    )
    problems = K._design_problems(design)
    if problems:
        raise ValueError(f"design mirror still drifts: {problems}")

    panel["leader"]["lines"] = _panel_lines(panel["leader"]["lines"], K.CAS_TEXTS[K.LEADER_OVERRIDE])
    for entry in panel["abilities"]:
        slot = int(entry["index"])
        if slot in (1, 2, 3):
            entry["lines"] = _panel_lines(entry["lines"],
                                          K.CAS_TEXTS[K.SLOT_OVERRIDE[slot]].replace(K.MAIN_ICON, ""))
    notes = [note for note in panel.get("notes", []) if not str(note).startswith(MIRROR_NOTE_PREFIX)]
    panel["notes"] = notes + [MIRROR_NOTE]
    return design, panel


def _panel_lines(old: list[dict], text: str) -> list[dict]:
    """逐行对齐：文字没变的行原样保留（含 status/dev 等附注），变了或新增的行标 changed。"""
    by_text = {line["text"]: line for line in old}
    return [by_text.get(line, dict(text=line, status="changed")) for line in text.split("\n")]


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

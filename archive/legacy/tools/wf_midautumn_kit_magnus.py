# -*- coding: utf-8 -*-
"""玛格诺斯（119990 ``lion_swordman_moon``）：火 · 用强化弹射打技能伤害。

**rework1（2026-09-21）**——目标面板 ``B/rework1/panel/magnus.json``，施工单
``B/rework1/impl/magnus.md``，原语配方 ``B/rework1/research/{A,B,C}``。

- 队长位授予**特殊强化弹射**（722 + ``power_flip_action`` 三档覆盖树，火共鸣门）：
  赛达「锥形」枪体三档 scale 递增、朝球的飞行方向（EF）、命中点爆克拉莉丝末端圆形爆炸；
- 冲刺强化：422 param0 ``-30%`` 常驻 + ``+245%`` 疾走抵消行（**只写 ability 表**，前置 42 队长）；
- 主技能把上一轮的情娅式骑行段换成**魏虎式光圈**（球上长寿命判定区，按技能伤害结算）；
- 「引擎点火」固有改成 **99 层 / 99999999 帧**，靠 during 134 按层给技能伤害、攻击力与独立乘区；
- 自身技能**命中敌人**（触发 136，CT 0.6 秒）→ 629 追击「引擎之炎」并消耗 1 层；629 行排在 525 之前。

面板文案由 5 个 ``desc_override_*`` 接管（队长技 + 槽 1/2/3/5）；槽 4/6 用客户端自动文案。
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import wf_dsl
import wf_magnus_pf_skill as PF_SKILL
from wf_magnus_ignition_growth import with_ignition_growth
import wf_midautumn_kitlib as KL
import wf_midautumn_specs as MS

# ---------------------------------------------------------------- 身份与自有键

CID, CODE = 119990, "lion_swordman_moon"
CID_S = str(CID)
TEMPLATE_ID, TEMPLATE_CODE = 111129, "lion_swordman_playable"
UID = MS.unique_condition_id(CID, 1)                       # "11999001" 引擎点火
UID_AURA = MS.unique_condition_id(CID, 2)                  # "11999002" 烈焰光环（作者追加）

PFA = "master/skill/power_flip_action.orderedmap"
PF_KEY = f"{CODE}_pf"
PF_PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_KEY}${PF_KEY}_lv{n}"
                    for n in (1, 2, 3))
PF_SKILL_PROGRAMS = PF_SKILL.skill_programs(CODE)
SPECIAL_PROGRAMS = {n: f"battle/action/power_flip/action/special$special_lv{n}" for n in (1, 2, 3)}
# 官方 special 底座指纹（2026-09-21 实读 .cdn/cn 官方归档）。漂移 ⇒ 底座换了，倍率要重算。
SPECIAL_SHA = {
    1: "569f2082c4633bae7e71610c296d6ab141cfabe1f3c4e5e0034c46dbf3e22961",
    2: "4ed6440b9ded6d435e2c2fb9a640541b2c3fc43c5c0068de41077bab07ad73f2",
    3: "7bebfdd5fc3ff46f2a789f7d631ac02084afa0cd11f4f19f71037f7faba3447d",
}

CHASE_STRING = f"ability_skill_{CODE}_ignite"
SWITCH_STRING = f"change_skill_{CODE}"
# 2026-09-27 第三轮（wf_balance_20260927c_magnus，口径 U2/U6）：旗号 2（704）开关行的面板串。
# 键名必须以 change_skill_<code> 开头（RevisionCandidate / stage_batch.splice 命名空间）。
SWITCH_LEADER_STRING = f"change_skill_{CODE}_leader"
PF_STRING = f"override_string_{CODE}_pf"
LEADER_OVERRIDE = f"desc_override_{CODE}"
SLOT_OVERRIDE_SLOTS = (1, 2, 3, 5)
SLOT_OVERRIDE = {slot: f"desc_override_{CODE}_{slot}" for slot in SLOT_OVERRIDE_SLOTS}
VOICE_KEY = f"{CODE}_voice_ready"

CHASE_PROGRAM = f"battle/action/skill/action/ability_skill/{CHASE_STRING}${CHASE_STRING}"
UC_ICON_ROW = f"battle/common/unique_condition/unique_{CODE}_ignition"
UC_ICON_LOGICAL = UC_ICON_ROW + ".png"
UC_AURA_ICON_ROW = f"battle/common/unique_condition/unique_{CODE}_aura"
UC_AURA_ICON_LOGICAL = UC_AURA_ICON_ROW + ".png"
UC_ICON_FRAME_DONOR = "battle/common/unique_condition/unique_fire_dragon_zenith.png"

# 母本特效：只引用、不改色 ⇒ 直接引用官方路径，不复制（裁决 §4 / 框架 §10.3）。
DONOR_FX_DIR = f"battle/effect/skill_unique/{TEMPLATE_CODE}"
FLAME = f"{DONOR_FX_DIR}/{TEMPLATE_CODE}_flame"

# 克隆三族（调研卡 C §2）：赛达「锥形」枪体 / 克拉莉丝末端爆炸 / 魏虎光圈
#
# 反馈轮 1（作者原话「泽塔的只要锥形的效果黄色的小方框不要」）：`zeta_lance_hit` / `zeta_lance_end`
# 里那两块实心黄色六边形（实测 atlas rect `zeta_lance_hit/n` 46×53、`zeta_lance_end/k`
# 46×53 纯 #FFFF00，屏上读作「黄色小方框」）＋一颗橙色光球，整族当时都不再克隆。
#
# 反馈轮 2（作者原话「强化弹射的动画效果也会突然消失，能不能补帧」）：锥形被
# 底座的 `HideEffect("オーラ演出")` 在命中那一帧硬删，而 `zeta_lance` 的 timeline 只有
# `start`(pass) + `start_loop`(loop)、没有 `end` 段 ⇒ 客户端终止时无段可跳，直接删。
# 官方赛达 `zeta$zeta_1` 的做法是命中后另起一条 `終わりの演出` 播 `zeta_lance_end`（32 帧）。
# 所以重新克隆回 `zeta_lance_end`，但把**黄/橙六边形那两块 rect 在图集里擦成全透明**
# （LANCE_HEX_LEAVES）——编排保持官方原样，画面上那 26+26 颗小方框一颗都不出现。
#
# 它落在**自己的 `lance_end/` 子目录**而不是回 `lance/`：1.4.965 那版在 `lance/zeta_lance_end.*`
# 发过一次，反馈轮 1 把它从包里删掉后 live store 里那两个文件成了孤儿（没人引用，但路径还占着）。
# 再往同一路径写＝preflight 的 `occupied_without_hash_bound_prior_path_ownership`
# （已实测：对 1.4.978 归档 inspect 会多出 2 条自有键冲突，`can_prepare` 直接 false，
# 而 `flow rebase` 只归位表行、清不掉资产路径冲突）。换新目录＝全新路径，`create` 不撞闸门。
FX_CLONES = (
    ("lance", "battle/effect/skill_unique/zeta", ("zeta_lance",)),
    ("lance_end", "battle/effect/skill_unique/zeta", ("zeta_lance_end",)),
    ("burst", "battle/effect/skill_unique/clarisse", ("clarisse",)),
    ("aura", "battle/effect/skill_unique/anger_investigator", ("anger_investigator_aura",)),
)
LANCE_END_SUBDIR = "lance_end"
FX_ROOT = f"battle/effect/skill_unique/{CODE}"
ZETA_LANCE = f"{FX_ROOT}/lance/zeta_lance"
ZETA_LANCE_END = f"{FX_ROOT}/{LANCE_END_SUBDIR}/zeta_lance_end"
CLARISSE = f"{FX_ROOT}/burst/clarisse"
AURA = f"{FX_ROOT}/aura/anger_investigator_aura"

# 要擦掉的两块 rect（`<base>/<叶名>`）：k = 53×46 纯 #FFFF00 实心六边形（唯一颜色数 1），
# l = 53×47 同形状的橙色版本。两块在官方 parts 里各有 26 个实例（`a[10]=a[11]=26`），
# 就是作者看到的「黄色小方框」雨。擦图不动 parts ⇒ 零结构手术、帧数/容量/编排全不变。
LANCE_HEX_LEAVES = ("zeta_lance_end/k", "zeta_lance_end/l")
LANCE_HEX_SOLID = {"zeta_lance_end/k": (255, 255, 0)}   # 纯色断言（母本漂移就拒绝）
LANCE_FX_NAME = "オーラ演出"                             # 底座给锥形那条 ShowEffect 的标签
LANCE_END_FX_NAME = "終わりの演出"                       # 官方赛达 zeta$zeta_1 用的同名标签
LANCE_END_FRAMES = 32                                   # zeta_lance_end 的 timeline 总帧数

CHASE_DONOR = ("battle/action/skill/action/ability_skill/"
               "ability_skill_fire_dragon_zenith$ability_skill_fire_dragon_zenith")
AURA_DONOR = "battle/action/skill/action/rare5/anger_investigator$anger_investigator_1"

_SKILL_DESC = ("挥舞缠绕着火焰的剑向前方斩劈，对敌人造成火属性伤害／"
               "发动技能后的一段时间内，自身获得光圈效果，对与光圈碰撞到的敌人造成技能伤害／"
               "赋予火属性角色及火属性协力球攻击力提升效果／"
               "强化弹射变为特殊强化弹射时：火焰突进随发动次数分三档逐渐增强，"
               "命中敌人后引爆大范围火焰")

TEXTS = {
    "title": "月下归途的机车骑士",
    "profile": "中秋夜赶着回乡的狮族青年。后座绑着一大包月饼，说是给等门的家人带的。"
               "他把油门拧到底，说这样月亮就追不上他——其实只是怕团圆饭凉了。",
    "leader": "疾风同路",
    "skill1": "烈焰轰鸣",
    "skill2": "烈焰轰鸣＋",
    "desc1": _SKILL_DESC,
    "desc2": _SKILL_DESC,
    "cv": "AI 合成配音",
}

SPEC = {
    "required_capabilities": ("dash-parameter-v1", "panel-description-override-v2"),
    "extra_keys": {
        MS.UNIQUE_CONDITION_LOGICAL: (UID, UID_AURA),
        KL.CAS: (CHASE_STRING, SWITCH_STRING, SWITCH_LEADER_STRING, PF_STRING, LEADER_OVERRIDE,
                 *(SLOT_OVERRIDE[s] for s in SLOT_OVERRIDE_SLOTS)),
        KL.SWITCHED: (VOICE_KEY,),
        PFA: (PF_KEY,),
    },
}

# ---------------------------------------------------------------- 行计划（donor + 逐格改）

# 固有状态：官方 unique_condition[19] unique_fire_dragon_zenith「勇敢之焰」
# c3=99999999 无时间限制 / c4=99 不设上限（作者原话）。c4 写 (None) ＝ 上限 1，叠层机制全死。
UNIQUE_DONOR = "19"
UNIQUE_NAME = "引擎点火"
UNIQUE_FRAMES = "99999999"
UNIQUE_CAP = "99"
UNIQUE_CELLS = {0: f"unique_{CODE}_ignition", 2: UC_ICON_ROW, 3: UNIQUE_FRAMES,
                4: UNIQUE_CAP, 14: CODE}

FIRE_LEADER = {4: "2", 7: "600000", 8: "600000", 9: "Red"}     # leader 前置1 = 火编成≥6
FIRE_ABILITY = {6: "2", 9: "600000", 10: "600000", 11: "Red"}  # ability 前置1 = 火编成≥6

# 「自身持有烈焰光环时」的队长表前置（作者追加行）。
#
# 语义上想要的是前置 187 `ConditionUnique`（「持有某固有状态」），但**官方 leader_ability
# 1107 行里 187 出现 0 次**（用到的前置只有 2/8/38/186/188/205；187 的 7 行全在 ability 表）。
# 队长表零先例的 kind ＝ 角色详情页 C7050 的老坑，所以这一行改用**前置 188
# `ConditionCountUnique` 阈值 ≥1**：官方队长表 6 行先例（`111183#4/#5` 火龙「持有勇敢之焰时」、
# `111165#3/#4`、`131152#2/#3`），其中 `131152#2/#3` 就是把 188 放在 precondition1 的写法。
# 188 数的是固有状态**实例个数**（恒为 1，记忆卡 wf-unique-cap-none-trap）——阈值写 ≥2 永不成立，
# 写 ≥1 就是「持有」，与 187 等价；本 kit 槽 3 的 629/525 对也是同一写法。
HAS_AURA_LEADER = {4: "188", 5: "0", 7: "100000", 8: "100000", 9: "", 10: UID_AURA}

# ---- 2026-09-27 平衡第二批（口径 A：无上限成长移队长并放缓，能力栏换有上限弱化版）----------
# 修订模块 ``wf_balance_20260927b_magnus`` 断言本 kit 的行/面板/DSL 输出 == 其 revise() 输出。
# 放缓倍率按 3 分钟实际次数（口径 A2，不按事件名称）：
#   · 「每 3 次强化弹射」：光环期（技能后 10 秒，约占 50–60% 时间）每次弹射 +35 连击 ⇒ 几乎每次弹射都是
#     Lv3 PF，3 分钟约 45–70 次 PF ⇒ 触发 15–23 次（≤30）⇒ 每步 ×1/5；
#   · 「引擎点火每 1 层」：3 分钟获得约 175–230 层（火技能 +1、每 3PF +10），命中每 0.6 秒消耗 1 层，
#     常驻 20–60 层、PF 密集时顶到 99 ⇒ ≥30 ⇒ 每步 ×1/10（设计稿按「每层属低频事件」取 1/5，
#     与口径 A2「不按事件名称」冲突，本批按实际层数改判）。
# 复核 C06：能力 1#2（每 3PF 自身技伤）与队长行 2（全队技伤）目标不同 ⇒ 不合并，另起自身行。
#
# ---- 2026-09-27 第三轮（修订模块 ``wf_balance_20260927c_magnus``，作者「砍到 4/5 或 7/10」「可以砍到 2/3」
# 「数值尽量取 5 的倍数」）：队长成长行放缓倍率从第二批的 ×1/5、×1/10 回调，基数一律是第二批前的原值：
#   · 全队(火)技伤/攻（火队只能靠这条成长）取 4/5：100% → 80%、50% → 40%；
#   · 每 3PF 自身技伤：7/10 档 25×0.7 = 17.5，按 5 的倍数取 20%（口径 D1，实际 4/5）；
#   · 点火每层自身技伤/攻（层数极多、自身基础充足）取 2/3：50×2/3 = 33.3，向上取 35%（实际 0.7）；
#   · 点火每层全队(火)独立乘区（给全队、只能靠成长）取 4/5：5% → 4%（<10% 按整数取，口径 D2）。
# 能力栏的封顶版（能力 1#2 限 4 次、能力 2 / 能力 3#4 最多 10 层）按口径 D4 保持第二批的值。
PF3_TEAM_SKILL_DAMAGE = "80000"          # 队长行 2：全队(火)技能伤害 原 100% → 80%（×4/5；第二批 20%）
PF3_TEAM_ATTACK = "40000"                # 队长行 3：全队(火)攻击力 原 50% → 40%（×4/5；第二批 10%）
PF3_SELF_SKILL_DAMAGE_LEADER = "20000"   # 能力 1#2 搬入队长：自身技能伤害 原 25% → 20%（第二批 5%）
LAYER_SELF_LEADER = "35000"              # 能力 2 两行搬入队长：每层自身技伤/攻 原 50% → 35%（×2/3 取整；第二批 5%）
LAYER_TEAM_411_LEADER = "4000"           # 能力 3#4 搬入队长：每层全队独立乘区 原 5% → 4%（×4/5；第二批 0.5%）
PF3_SELF_SKILL_DAMAGE_LIMIT = "4"        # 能力 1#2 就地：限 4 次（25%×4 = 100%，设计稿值）
LAYER_ABILITY_LIMIT = "10"               # 能力 2 / 能力 3#4 就地：最多计 10 层（c102，官方 1611231–1611236 同写法）
LAYER_ABILITY_SELF = "15000"             # 能力 2 每层自身技伤/攻 15%（满 150%）
LAYER_ABILITY_TEAM_411 = "1000"          # 能力 3#4 每层全队独立乘区 1%（满 10%）
# 技能 DSL「点火每层 +5 倍」：BindConditionAccumulationVariable 第 5 参是变量上限
# （ActionEvaluator.as case 101：``bindFloatVariable(vid, min(层数 / 第4参, 第5参))``）⇒ 99 → 10，
# 层数对倍率的贡献封顶 10 层；live 先例 wf_gbf_kit_soriz（…, 1, 10）、wf_seasonal7_kit_primula（…, 1, 20）。
# 无上限部分由队长技「点火每层自身技能伤害」承担（口径 A5：队长已有同一层数的逐层成长行 ⇒ 视为已合并）。
IGNITION_DSL_CAP = 10
# ---- 2026-09-27 第三轮（wf_balance_20260927c_magnus，口径 U2/U6/U7：「当队长且共鸣时不封顶，其他情况保留第二批封顶」）：
#   · 特殊强化弹射三档 pf_skill_lv1/2/3 只由队长 #6–#8（火共鸣）的 629 调起 ⇒ 上限直接恢复第二批前的 int 99；
#   · 技能两档与「引擎之炎」追击：根块 [点火绑定 … 块尾] 整段包进 ConditionalsChangeSkillFlag(2, 开支, 关支)，
#     开支 = 同一段只把绑定上限改回 99，关支 = 第二批封顶 10 层原段（:func:`leader_gate`）；
#   · 旗号 2（kind 704）由能力 1 末尾追加的瞬发行打开：前置 42（仅队长）+ 火编成≥6，无触发
#     （live 先例罗尔夫中秋 1499866#4；旗号 1 已被 1199901#1 的 536 常驻占用，不当队长也开着，不能复用）。
# 分支在新的局部环境里执行（ActionEvaluator.as case 86），分支里的 Bind 分支外看不到 ⇒ 绑定起到块尾整段入支。
IGNITION_LEADER_CAP = 99                 # = wf_magnus_ignition_growth.MAX_LAYERS（第二批前逐字，int）
LEADER_SKILL_FLAG = 2                    # ConditionalsChangeSkillFlag 旗号号
LEADER_SKILL_FLAG_KIND = "704"           # 旗号 2 = kind 704（536 = 旗号 1，704–708 = 旗号 2–6）
LEADER_FIRE_ABILITY = {6: "42", 13: "2", 16: "600000", 17: "600000", 18: "Red"}  # 队长 且 火编成≥6
# 2026-09-27 第二批（口径 B3/B6，复核补漏）：「引擎之炎」629 追击 = 能力 3#1 触发 136 自身技能命中、
# CT c35 = 36 帧（0.6 秒 ≤3 秒）⇒ 每次发动单目标削韧必须 ≤1。追击树的爆炸判定区寿命 30 帧、
# CalculatedUsingMaxNumOfHits(5)、p15 None（无每目标硬上限）⇒ 同一个 boss 吃满 5 段。
# 官方母本火龙 ability_skill_fire_dragon_zenith 是 4 段 × 0.25 = 1.0；rework 把段数抬到 5 后变 1.25。
# 口径 B6 只改 CreateNormalAttack p13：0.25 → 0.2 ⇒ 5 × 0.2 = 1.0（回到母本每次总量），
# 段数、倍率、Fever 点（p14）一格不动。疾风同路 PF（队长 #6–#8 的 629，15/20/25 顶格）按口径 B5 保留。
CHASE_DOWN_DONOR = 0.25                  # 母本 CNA p13（漂移即拒绝）
CHASE_DOWN = 0.2                         # 每段削韧；× BURST_MAX_HITS(5) = 每次 1.0
CHASE_DOWN_CAP = 1.0                     # 口径 B3：触发 CT ≤3 秒的 629 每次 ≤1

# 队长技 6 行（面板 7 行：2 条冲刺文案对应的 422 行在词条槽 5，见施工单偏离 D-1）
LEADER: tuple[tuple[str, str, dict[int, str], str], ...] = (
    ("141201#1", "official",
     {0: CODE, **FIRE_LEADER, 45: "722", 80: PF_KEY, 81: "1,2,3", 82: PF_STRING},
     "火·编成≥6 时: 自身 强化弹射覆盖"),
    ("111183#1", "official",
     {0: CODE, **FIRE_LEADER, 32: "(None)", 45: "34", 46: "5", 47: "Red",
      49: PF3_TEAM_SKILL_DAMAGE, 50: PF3_TEAM_SKILL_DAMAGE},
     "火·编成≥6 时: 强化弹射≥3 → 赋予全队(火) 技能伤害 80%"),
    ("111183#1", "official",
     {0: CODE, **FIRE_LEADER, 32: "(None)", 45: "32", 46: "5", 47: "Red",
      49: PF3_TEAM_ATTACK, 50: PF3_TEAM_ATTACK},
     "火·编成≥6 时: 强化弹射≥3 → 赋予全队(火) 攻击力 40%"),
    ("111183#2", "official",
     {0: CODE, 28: "300000", 29: "300000", 46: "5", 47: "Red",
      49: "5000", 50: "5000"},
     "火·编成≥6 时: 强化弹射≥3 → 赋予全队(火) 技能槽 5%"),
    ("111183#3", "official",
     {0: CODE, 25: "2", 26: "", 28: "300000", 29: "300000",
      49: "700000", 50: "700000", 66: UID},
     "火·编成≥6 时: 强化弹射≥3 → 自身 状态固有 700%×1次"),
    # 作者追加（09-21 07:4x）「狮子队长技添加自身持有光环时，弹射时连击+35」。
    # donor ＝ 官方 `131005#4`（雷电剑士，队长表里唯一一族「触发 6 BallFlip → 内容 226 AddCombo」
    # 的现成行，另一条同形是 `221004#2`）。改四组：①c1/c2 去掉 donor 的觉醒标记（本角色其余
    # 5 行都是 c1='0'/c2 空）；②前置 1 换成 HAS_AURA_LEADER；③阈值 5 次 → 1 次、CT 600 → 0；
    # ④强度 6 连击 → 35 连击（连击类 ×100000）。**不加火共鸣门**：作者原话没写属性共鸣。
    ("131005#4", "official",
     {0: CODE, 1: "0", 2: "", **HAS_AURA_LEADER,
      28: "100000", 29: "100000", 33: "0", 49: "3500000", 50: "3500000"},
     f"状态计数固有≥1[固有{UID_AURA}] 时: 弹射≥1 → 自身 追加连击 35"),
)

LEADER += PF_SKILL.leader_plans(CODE, PF_STRING)

# 2026-09-27 第二批：从能力栏搬进队长的无上限部分（行 = [CODE, '0', ''] + 能力行[5:]，能力 c≥5 → 队长 c−2），
# 追加在末尾，已有 9 行的下标不动。donor 只提供形状，逐格改后与转置行逐字相同（修订模块测试断言）。
#   #9  能力 1#2  → 每 3PF 自身技能伤害 5%（官方 111183#1 同形，target 0）
#   #10 能力 2#0  → 点火每层自身技能伤害 5%（官方 161063#3：队长 during 134 → 2 / target 0）
#   #11 能力 2#1  → 点火每层自身攻击力 5%（官方 161063#2：队长 during 134 → 0 / target 0）
#   #12 能力 3#4  → 点火每层全队(火)独立乘区技能伤害 0.5%（形状取官方 161123#0 队长 during 134 → target 5；
#       内容 411 队长表官方 0 行，live 先例特克托 139993 队长 134→411；LeaderAbilityValues.parseAt107
#       原生 case "411" = SeparatedTermSkillDamage{target: parseAt108, strength: parseAt111}）。
#       原能力行无前置（c6=0）⇒ 转置后 c4=0，不加火共鸣门。
LEADER += (
    ("111183#1", "official",
     {0: CODE, **FIRE_LEADER, 32: "(None)", 45: "34", 46: "0", 47: "",
      49: PF3_SELF_SKILL_DAMAGE_LEADER, 50: PF3_SELF_SKILL_DAMAGE_LEADER},
     "火·编成≥6 时: 强化弹射≥3 → 自身 技能伤害 20%"),
    ("161063#3", "official",
     {0: CODE, **FIRE_LEADER, 98: "100000", 99: "100000", 100: "(None)", 102: UID,
      107: "2", 108: "0", 111: LAYER_SELF_LEADER, 112: LAYER_SELF_LEADER},
     f"火·编成≥6 时: 持续·状态累积计数固有≥1[固有{UID}] → 自身 技能伤害 35%"),
    ("161063#2", "official",
     {0: CODE, **FIRE_LEADER, 98: "100000", 99: "100000", 100: "(None)", 102: UID,
      107: "0", 108: "0", 111: LAYER_SELF_LEADER, 112: LAYER_SELF_LEADER},
     f"火·编成≥6 时: 持续·状态累积计数固有≥1[固有{UID}] → 自身 攻击力 35%"),
    ("161123#0", "official",
     {0: CODE, 100: "(None)", 102: UID, 107: "411", 108: "5", 109: "Red",
      111: LAYER_TEAM_411_LEADER, 112: LAYER_TEAM_411_LEADER},
     f"持续·状态累积计数固有≥1[固有{UID}] → 赋予全队(火) 独立乘区技能伤害 4%"),
)

_A = "action_skill"

# 六个词条键。每键 c1（主位限制）与 c2（雕像组）必须全键一致（kitlib.check_ability_key）。
PLAN: dict[int, tuple[tuple[str, str, dict[int, str], str], ...]] = {
    1: (
        ("1111831#0", "official",
         {0: f"{CODE}_1", 1: "true", 2: _A, 6: "0", 11: "", 51: "50000", 52: "50000"},
         "自身 技能槽 50%"),
        ("1111296#0", "official",
         {0: f"{CODE}_1", 1: "true", 2: _A, **FIRE_ABILITY, 70: SWITCH_STRING},
         f"火·编成≥6 时: 自身 切换技能形态[{SWITCH_STRING}]"),
        # 2026-09-27 第二批：限次 (None) → 4（无上限部分已搬进队长 #9，×1/5）。
        ("1111833#1", "official",
         {0: f"{CODE}_1", 1: "true", 2: _A, **FIRE_ABILITY,
          30: "300000", 31: "300000", 34: PF3_SELF_SKILL_DAMAGE_LIMIT, 47: "34",
          51: "25000", 52: "25000"},
         f"火·编成≥6 时: 强化弹射≥3(限{PF3_SELF_SKILL_DAMAGE_LIMIT}次) → 自身 技能伤害 25%"),
        # 2026-09-27 第三轮（口径 U6）：旗号 2 开关行——当队长且火共鸣时技能 / 引擎之炎的点火倍率不封顶。
        # donor = 官方 1111776#0（wirfled_playable_6，瞬发无触发 704，无前置）；逐格补前置 42 队长 + 火编成≥6，
        # 整行与 live 罗尔夫中秋 1499866#4 同形（只换 c0/c2/c18/c70）。零先例的「队长表 704 行」不做。
        ("1111776#0", "official",
         {0: f"{CODE}_1", 1: "true", 2: _A, **LEADER_FIRE_ABILITY, 70: SWITCH_LEADER_STRING},
         f"队长 且 火·编成≥6 时: 自身 切换技能Flag{LEADER_SKILL_FLAG}[{SWITCH_LEADER_STRING}]"),
    ),
    # 2026-09-27 第二批：每层 50%/不限层 → 每层 15%、最多计 10 层（c102 = 官方 donor 原值 10）；
    # 无上限部分已搬进队长 #10/#11（×1/10）。
    2: (
        ("1611232#0", "official",
         {0: f"{CODE}_2", 1: "true", 2: _A, **FIRE_ABILITY,
          102: LAYER_ABILITY_LIMIT, 104: UID, 109: "2", 110: "0",
          113: LAYER_ABILITY_SELF, 114: LAYER_ABILITY_SELF},
         f"火·编成≥6 时: 持续·状态累积计数固有≥1(限{LAYER_ABILITY_LIMIT}次)[固有{UID}] → 自身 技能伤害 15%"),
        ("1611231#1", "official",
         {0: f"{CODE}_2", 1: "true", 2: _A, **FIRE_ABILITY,
          102: LAYER_ABILITY_LIMIT, 104: UID, 109: "0", 110: "0",
          113: LAYER_ABILITY_SELF, 114: LAYER_ABILITY_SELF},
         f"火·编成≥6 时: 持续·状态累积计数固有≥1(限{LAYER_ABILITY_LIMIT}次)[固有{UID}] → 自身 攻击力 15%"),
    ),
    3: (
        ("1111652#0", "official",
         {0: f"{CODE}_3", 1: "false", 2: _A, **FIRE_ABILITY,
          28: "5", 29: "Red", 51: "100000", 52: "100000", 68: UID},
         "火·编成≥6 时: 技能发动≥1 → 自身 状态固有 100%×1次"),
        # 629：字符串键 c70 + 程序路径 c71；必须排在下面的 525 消耗行之前。
        ("1611053#0", "official",
         {0: f"{CODE}_3", 1: "false", 2: _A, 6: "188", 7: "0", 9: "100000", 10: "100000",
          12: UID, 27: "136", 28: "0", 30: "100000", 31: "100000", 34: "(None)", 35: "36",
          70: CHASE_STRING, 71: CHASE_PROGRAM},
         f"状态计数固有≥1[固有{UID}] 时: 任一敌方技能Hit≥1(CT0.6秒) → "
         f"自身 发动技能动作[{CHASE_STRING}]"),
        ("1111652#2", "official",
         {0: f"{CODE}_3", 1: "false", 2: _A, 6: "188", 7: "0", 9: "100000", 10: "100000",
          12: UID, 27: "136", 28: "0", 30: "100000", 31: "100000", 34: "(None)", 35: "36",
          68: UID},
         f"状态计数固有≥1[固有{UID}] 时: 任一敌方技能Hit≥1(CT0.6秒) → 自身 消耗固有状态 100%"),
        ("1310323#3", "official",
         {0: f"{CODE}_3", 1: "false", 2: _A, 6: "0", 7: "", 9: "", 10: "",
          98: "0", 100: "500000", 101: "500000", 102: "1", 104: UID,
          109: "411", 110: "0", 111: "", 113: "25000", 114: "25000"},
         f"持续·状态累积计数固有≥5(限1次)[固有{UID}] → 自身 独立乘区技能伤害 25%"),
        # 2026-09-27 第二批：每层 5%/不限层 → 每层 1%、最多计 10 层；无上限部分已搬进队长 #12（×1/10）。
        ("1310323#2", "official",
         {0: f"{CODE}_3", 1: "false", 2: _A, 6: "0", 7: "", 9: "", 10: "",
          98: "0", 100: "100000", 101: "100000", 102: LAYER_ABILITY_LIMIT, 104: UID,
          109: "411", 110: "5", 111: "Red",
          113: LAYER_ABILITY_TEAM_411, 114: LAYER_ABILITY_TEAM_411},
         f"持续·状态累积计数固有≥1(限{LAYER_ABILITY_LIMIT}次)[固有{UID}] → 赋予全队(火) 独立乘区技能伤害 1%"),
        # number 保持 1，以 initial_multiply=3 累计进同一固有状态；
        # number=3 会改变状态 discrimination key，形成独立图标。
        ("1111652#0", "official",
         {0: f"{CODE}_3", 1: "false", 2: _A, **FIRE_ABILITY,
          27: "2", 28: "0", 29: "", 30: "300000", 31: "300000",
          34: "(None)", 35: "0", 51: "100000", 52: "100000",
          59: "100000", 60: "100000", 68: UID, 74: "3"},
         "火·编成≥6 时: 强化弹射≥3 → 自身 状态固有 100%×1次"),
    ),
    4: (
        ("1111833#1", "official",
         {0: f"{CODE}_4", 1: "true", 2: "attack_common",
          30: "200000", 31: "200000", 47: "32", 51: "30000", 52: "30000"},
         "强化弹射≥2(限10次) → 自身 攻击力 30%"),
        ("1110993#1", "official",
         {0: f"{CODE}_4", 1: "true", 2: "attack_common", 51: "37500", 52: "37500"},
         "强化弹射≥5(限4次) → 自身 技能伤害 37.5%"),
    ),
    5: (
        # kind 694（瞬发独立乘区技能伤害）官方 0 行，只有 live 先例 ⇒ 这一行取 store。
        ("1299925#1", "store",
         {0: f"{CODE}_5", 1: "true", 2: _A, 51: "15000", 52: "15000"},
         "自身 独立乘区技能伤害 15%"),
        ("1110993#2", "official",
         {0: f"{CODE}_5", 1: "true", 2: _A, 30: "300000", 31: "300000", 35: "300",
          51: "5000", 52: "5000"},
         "火·编成≥6 时: 强化弹射≥3(CT5秒) → 自身 技能槽 5%"),
        # 422 冲刺参数：只许 ability 表（队长表写 = C7050），前置 42 Leader ⇒ 只在他当队长时生效。
        # c118 = param_id 必须逐格钉死 "0"：live 里这两个 donor 键各带 4~6 条 422，
        # 记录号会随别的角色改动漂移（2026-09-21 实测 1699885#1 的 param_id 已从 0 漂成 1），
        # 而 describe 回读看不出 param_id ⇒ 只有显式写 0 才不会被别人的改动带偏。
        ("1699885#1", "store",
         {0: f"{CODE}_5", 1: "true", 2: _A, 113: "-30000", 114: "-30000", 118: "0"},
         "队长 时: 持续·HP≤1 → 自身 冲刺参数(可调) -30%"),
        ("1699991#7", "store",
         {0: f"{CODE}_5", 1: "true", 2: _A, 113: "245000", 114: "245000", 118: "0"},
         "队长 时: 持续·状态冲刺 → 自身 冲刺参数(可调) 245%"),
    ),
    6: (
        ("1110996#0", "official",
         {0: f"{CODE}_6", 1: "true", 2: "special", 6: "0", 11: "",
          51: "20000", 52: "20000"},
         "自身 技能槽充能 20%"),
        ("1110013#0", "official",
         {0: f"{CODE}_6", 1: "true", 2: "special", 51: "500000", 52: "500000"},
         "自身 强化弹射连击数↓ 5"),
    ),
}

DASH_PARAM0_BASE = -30000          # 常驻 CD −30%
DASH_PARAM0_SWIFT = 245000         # 3.5 × (1 + (−0.30)) = 2.45 ⇒ Swift 中帧数与非 Swift 相同

MAIN_ICON = " <icon id='main'>  "   # desc_override 会盖掉客户端逐行画的 Ⓜ，主位键必须自带

# 面板字符串（custom_ability_string）。629 / 536 的条目不写数字与时间（裁决 §3）。
CAS_TEXTS = {
    CHASE_STRING: "发动技能「引擎之炎」：在命中点引爆积蓄的引擎火焰，造成火属性伤害（以技能伤害计算）",
    # 2026-09-27 第三轮（口径 U9）：旗号 1（1199901#1 的 536）在数据里只给主斩劈的倍率加 alv 1.75～3.5
    # （技能两档的斩劈 CreateNormalAttack 数值项），光环半径 200/270 来自技能/技能+两档，与旗号无关
    # ⇒ 原文「光环的范围扩大」改成实际效果；536 条目不写数字。
    SWITCH_STRING: "强化『烈焰轰鸣』：斩劈的技能倍率提升",
    # 2026-09-27 第三轮（口径 U2/U6）：旗号 2（704，能力 1 末行，前置 42 队长 + 火共鸣）条目；不写数字。
    # 同轮技能强化文案规范（作者「技能里面不要重复描述强化后的效果,规范并简化描述」）：与队长面板强化条目同文，
    # 补「（含引擎之炎）」（旗号 2 同时包住技能两档与引擎之炎），见 wf_balance_20260927c_magnus.skill_flag_entry_problems。
    SWITCH_LEADER_STRING: "强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升（含引擎之炎）",
    PF_STRING: "强化弹射变为特殊强化弹射时：火焰突进随发动次数分三档逐渐增强，"
               "命中敌人后引爆大范围火焰，按技能伤害结算",
    # 2026-09-27 第二批：第 4 行数值放缓；按复核 C06 拆出「自身技能伤害＋5%」（紧跟同触发的第 4 行）；
    # 引擎点火逐层两行（从能力 2/3 搬入的无上限部分）排在「烈焰光环」行之前，光环行仍是最后一行。
    # 无上限就写到效果为止（不写「可无限」等禁语）。
    # 2026-09-27 第三轮：四处成长数值回调（80/40、20、35/35、4）；「自身点火逐层」行后插入旗号 2 的
    # 强化条目「强化『烈焰轰鸣』：…」（不写数字，与 SWITCH_LEADER_STRING 同文）。光环行仍是最后一行。
    # 同轮面板合并（作者「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,引擎点火提供的效果
    # 就不用写火属性共鸣」）：队长 #1/#2/#3/#4/#9（火编成≥6 + 每 3 次强化弹射）四行并一行；引擎点火的获取来源全带
    # 火共鸣 ⇒ 点火逐层行删「火属性共鸣时，」后与火队独立乘区行（#10–#12 同条件）并一行。11 → 7 行。
    # 逐字与依据见 wf_balance_20260927c_magnus.LEADER_MERGE_GROUPS / resonance_omission_problems。
    # 同轮按数据改文字（主会话口径 4）：冲刺两行的数据是槽 5 的两条 422（前置只有 42 队长、没有火共鸣）
    # ⇒ 删「火属性共鸣时，」；依据见 wf_balance_20260927c_magnus.dash_row_problems。
    # 同轮：特殊强化弹射三档（队长 #6–#8 的 629）每段倍率带引擎点火逐层加法项、上限 99 不经旗号 ⇒ 这是队长强化弹射
    # 本体的效果（不属于技能强化），写在第 1 行末尾「，威力随引擎点火层数提升」（不写数字）；
    # 依据见 wf_balance_20260927c_magnus.special_pf_growth_problems。
    LEADER_OVERRIDE: "\n".join((
        "火属性共鸣时，自身的强化弹射变为特殊强化弹射，造成的伤害按技能伤害结算，威力随引擎点火层数提升",
        "自身获得冲刺强化效果，冲刺冷却时间－30%",
        "冲刺间隔缩短效果不会让自身的冲刺冷却时间进一步缩短",
        "火属性共鸣时，每发动3次强化弹射，火属性角色技能伤害＋80%、攻击力＋40%、技能槽＋5%，"
        "自身技能伤害＋20%、引擎点火＋7层",
        "自身引擎点火每提升1层，自身技能伤害＋35%、攻击力＋35%，火属性角色技能伤害额外乘区＋4%",
        "火属性共鸣时，强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升（含引擎之炎）",
        "自身持有「烈焰光环」期间，每次弹射，连击＋35",
    )),
    # 2026-09-27 第二批：536 条目只留「光环范围扩大」（不写数字）；每 3PF 自身技伤单列并写上限；
    # 技能 DSL 点火倍率封顶 10 层。
    # 2026-09-27 第三轮：536 条目改成实际效果（口径 U9）。同轮技能强化文案规范：强化条目点名『烈焰轰鸣』、与 CAS 同文；
    # 点火倍率行只写技能本体（最多10层），不写旗号 2 的「不受此限」（强化效果只在队长强化条目），并去「及特殊强化弹射」
    # （特殊强化弹射三档点火上限 99、不经旗号）。
    SLOT_OVERRIDE[1]: "\n".join((
        "战斗开始时，自身技能槽＋50%",
        "火属性共鸣时，强化『烈焰轰鸣』：斩劈的技能倍率提升",
        "火属性共鸣时，每发动3次强化弹射，自身技能伤害＋25%（最多4次）",
        "自身引擎点火每提升1层，技能基础总倍率＋5倍（含引擎之炎，最多10层）",
    )),
    # 2026-09-27 第三轮面板合并：按引擎点火层数生效 ⇒ 不写「火属性共鸣时，」（数据前置不动）。
    SLOT_OVERRIDE[2]: "引擎点火每提升1层，自身技能伤害＋15%、攻击力＋15%（最多10层）",
    SLOT_OVERRIDE[3]: "\n".join(MAIN_ICON + line for line in (
        "火属性共鸣时，火属性角色发动技能时，自身引擎点火＋1层",
        "自身处于「引擎点火」期间，自身技能命中敌人时，发动「引擎之炎」：造成技能伤害",
        "自身处于「引擎点火」期间，自身技能命中敌人时，消耗1层「引擎点火」",
        "自身引擎点火在5层以上时：自身技能伤害额外乘区＋25%",
        "自身引擎点火每提升1层，火属性角色技能伤害额外乘区＋1%（最多10层）",
        "火属性共鸣时，每发动3次强化弹射，自身引擎点火＋3层",
    )),
    SLOT_OVERRIDE[5]: "\n".join((
        "自身独立乘区技能伤害＋15%",
        "火属性共鸣时，每发动3次强化弹射，自身技能槽＋5%（冷却时间：5秒）",
    )),
}
SKILL_FLAG_TEXT_KEYS = (CHASE_STRING, SWITCH_STRING, SWITCH_LEADER_STRING)

# action_skill c4/c5/c6（作者放行第 5 条：两档都写 600）
ENERGY = {"1": ("600", "600", "1"), "2": ("600", "600", "1")}

# 语音路由：kind 1 ConditionExist（引擎点火）。kind 3 会因 536 常驻而让 skill_ready 永不播。
VOICE_ROUTE = {"kind": 1, "condition_kind": "28", "condition_id": UID}

# ---- DSL 旋钮 ----------------------------------------------------------------
AURA_FRAMES = 600

# 「烈焰光环」固有状态（作者追加 09-21）：光环本来只是「特效 + 判定区」，没有任何状态可供词条判定。
# 技能树在创建光环的同一处给自身（-17）付一层这个固有，队长技那一行就以「持有它」为前置。
#
# donor 沿用 `unique_condition[19]`（与「引擎点火」同一母本，形状已验证）。逐格改：
#   c3 1200 → AURA_FRAMES（600 帧 ＝ 10 秒，**与光环寿命同源**，不许另写魔数）；
#   c4 3 → "1"（上限 1 层；官方同值先例 unique_ice_dragon/unique_tenjinin/unique_kinin/
#            unique_devil_leader。写 "(None)" 也是上限 1，但 KL.unique_row 直接拒绝它）；
#   c14 'fire_dragon_zenith' → "(None)"（c14 ＝ PF 语音替换角色，这个状态不碰 PF 语音）。
# 保留 donor 的 c9=false（不可驱散）/ c10=true（无视弱体耐性）/ c11='0'（Good 方向，是增益）/
# c12='0'（overwrite_mode）/ c13=true（入棺时移除）。
#
# **重复开技能＝刷新时长，不叠层、不被拒绝**【事实，客户端实读】：
# `ConditionChangeCalculator.as:190` 在 overwrite_mode=0 且 maxAccumulation==1、目标非敌对时
# 选 `ConditionOverwriteStrategy.ChooseOneWithLongerRemainingTime`；
# `ConditionSlot.as:7521` 的 index 0 分支取 `max(剩余帧, 新帧)`，
# 同函数 7601 行 `maxAccumulation > 1` 为假时走 `max(旧强度, 新强度)` ⇒ 层数恒为 1。
AURA_UNIQUE_DONOR = "19"
AURA_UNIQUE_NAME = "烈焰光环"
AURA_UNIQUE_CAP = "1"
AURA_UNIQUE_CELLS = {0: f"unique_{CODE}_aura", 2: UC_AURA_ICON_ROW,
                     3: str(AURA_FRAMES), 4: AURA_UNIQUE_CAP, 14: "(None)"}

# 付与节点的官方 donor：`psycho_reaper_meteor23` 的主技能根层就是一条
# `CreateCondition(-17, [ACUnique(18, 3层)], …, 付与对象种类 3, …)`。
# 全官方基线扫描（953 棵技能树）里「CreateCondition 携带 ACUnique」共 14 条，
# 其中 `subject=-17 / 付与对象种类=3` 的 6 条来自 psycho_reaper_meteor23 与 megumin
# —— 这是「给自身付一个固有状态」的唯一官方形状，直接整条克隆，只换固有 id 与层数。
AURA_MARK_DONOR = ("battle/action/skill/action/rare5/"
                   "psycho_reaper_meteor23$psycho_reaper_meteor23_2")
AURA_MARK_DONOR_UID = 18          # 母本固有「抛掷捧花」；漂移即拒绝
AURA_MARK_TARGET_KIND = 3         # 下标 10 ＝ 付与对象种类；自身/Member 写 3（错配 = 施法 C16102）
AURA_MARK_STACKS = 1              # ACUnique 第二参 ＝ 层数（不是帧数）；上限 1 ⇒ 只能是 1
# 光圈「画出来的环」与「判定圆」必须等大，否则玩家看到环压住敌人却不掉血
# （反馈轮 1 作者原话「光环稍微小一点，而且没有碰撞到的技能伤害」）。
# 实测（`_donor/anger_investigator/*`，脚本见 W/impl/magnus.md「反馈轮 1」）：
#   `anger_investigator_aura` 的 4 张子图最大 rect 宽 68px，parts 矩阵最大线性缩放 1.9517
#   ⇒ 屏上直径 = 68 × 1.9517 × ShowEffect scale = 132.71 × scale。
# 官方魏虎的 scale 3.75 ⇒ 环半径 248.8，而判定只有 Circle 200 —— 外圈 48.8px 是纯装饰。
AURA_RING_PX_PER_SCALE = 68 * 1.9517  # 132.71 px/scale（母本 rect × parts 矩阵，实测）
AURA_RADIUS = {"1": 200, "2": 270}    # 判定圆半径不动（缩的是画面，不是强度）


def aura_scale(radius: int) -> float:
    """把 ShowEffect scale 反算成「环刚好压在判定圆上」，禁止再手写魔数。"""
    return round(2 * radius / AURA_RING_PX_PER_SCALE, 2)


AURA_MULTIPLIER = {"1": 4.0, "2": 5.5}
AURA_TUNING = {                       # 档 → (ShowEffect scale, 判定圆半径, 每跳倍率)
    level: (aura_scale(AURA_RADIUS[level]), AURA_RADIUS[level], AURA_MULTIPLIER[level])
    for level in ("1", "2")
}
# 母本把 p14 写成 CalculatedUsingMaxNumOfHits(10)，客户端据此推出的最小间隔是
# lifetime/(N-0.5) = 600/9.5 ≈ 63 帧 —— 球只是擦过敌人时，第二跳往后几乎全被这道闸吃掉。
# 改成显式 30 帧（live 杰拉德 149999 同族光环用的就是 SpecifyMinHitIntervalDirectly），
# p15 的每目标硬上限仍是 10 跳 ⇒ 单次技能的总伤不变，只是更快打完、看得见。
AURA_HIT_INTERVAL = 30
AURA_MAX_HITS = 10
AURA_BINDS = (10, 11, 12)             # 母本 111129 自己占 0–5
CHASE_MULT = 3.0
BURST_SCALE = 3.25                    # 09-24：爆炸视觉直径减半
BURST_RADIUS = 165                    # 同步将实际爆炸判定半径减半
BURST_MAX_HITS = 5
PF_SCALE = 2.0                        # 含全部命中段：官方 special 合计 6 / 11 / 21 ⇒ 12 / 22 / 42
PF_SUPPRESS = 90                      # 底座 SetPowerFilpSuppress
# 反馈轮 1：三档只留锥形本体，靠 scale 递增表达「逐渐增强」（不再叠 hit/end 的黄色六边形）。
PF_LANCE_SCALE = {1: 1.0, 2: 1.4, 3: 1.8}
# 锥形朝向：官方赛达 `zeta$zeta_1` 就是 `ShowEffect zeta_lance, 主体 -18(球), 坐标系 ["EF"]`；
# `BallImpl.getDirEF()` 直接返回球的飞行角（`getDirCD()` 才是 throw）。底座 special 的
# オーラ演出写的是 AB（绝对坐标、角度恒 0）⇒ 枪体恒定朝上，这就是作者说的「现在恒定朝上」。
PF_LANCE_COORD = ["EF"]

# ---- 反馈轮 2：命中窗口 + 收尾 ------------------------------------------------
#
# 官方三个 722 底座把「命中后的窗口」写成一组联动值（全部相等，Wait 比 suppress 少 2）：
#     special_lv1        suppress 20 / Wait 18 / 参考点 20 / 特殊演出寿命 20
#     special_lv2,lv3    suppress 30 / Wait 28 / 参考点 30 / 特殊演出寿命 30
#     psycho_reaper_23   suppress 40 / Wait 38 / 参考点 40 / 特殊演出寿命 40
# 反馈轮 1 把「特殊演出」换成 79 帧的克拉莉丝末端，却没动这组值 ⇒ 爆炸在第 20/30 帧
# （满强度那一帧，逐帧统计 n≈110 个绘制件）被参考点连坐删掉，而且克拉莉丝 timeline 只有
# 一段 `neutral`(once)、没有 `end` 段 ⇒ 客户端终止时无段可跳 = 立删。这就是「爆炸突然消失」。
#
# 修法照 psycho_reaper 的官方形状把四个值一起抬到 48，并给克拉莉丝切出 `end` 段：
# 寿命 48 落在 `loop` 段中间，终止时跳 `end`（55–79 = 官方原帧 132–156 的消散尾巴，
# 绘制件 136 → 64 → 0），所以无论是寿命到期、参考点到期还是 PF 结束，都有 25 帧过渡。
PF_HIT_WINDOW = 48                    # 命中后 suppress / Wait+2 / 参考点 / 特殊演出寿命
PF_HIT_WINDOW_DONOR = {1: 20, 2: 30, 3: 30}

# 反馈轮 2 复核补漏：克拉莉丝**不止 722 一个使用者**。能力 3「引擎之炎」的 629 追击树
# （`ability_skill_lion_swordman_moon_ignite`）用的是同一个 `burst/clarisse`，反馈轮 1 把它的
# 演出寿命写成了 `CLARISSE_NEW_T`(79)，而它所在的参考点寿命仍是官方火龙母本的 30。
#
# 官方母本 `fire_dragon_zenith` 的这一组是**三个数全相等**（实测官方 CDN 归档）：
#     CreateReferencePoint bind=3 lifetime=30
#       └ ShowEffect  …_special_attack  subject=3  lifetime=30
#       └ CreateHitArea subject=3  Circle 250  lifetime=30  maxHits=4
# 反馈轮 1 只抬了演出寿命（30 → 79）、没动参考点（30）⇒ 与 722 那边一模一样的失配。
# 反馈轮 2 把 722 修成「参考点 == 演出寿命 == 48」之后，这个使用者被漏掉：
#   · 单看寿命 79：1-20(pass) → 21-54(loop) → 回放 21-45 → 到点跳 end 55-79，共 104 帧，
#     而 21-54 这段 loop 是本轮**人为切出来**的（母本从来不是为循环设计的）⇒ 回跳会 pop；
#   · 按参考点 30 先到：第 30 帧就被连坐终止，body 只播 10 帧 loop。
# 两种走法都不是想要的。修法＝把这一组也恢复成官方的「参考点 == 演出寿命」，取值沿用
# 722 的 PF_HIT_WINDOW ⇒ 两处爆炸同形同长（48 帧 body + 25 帧 end 尾巴）。
# **判定区寿命 30 与每目标上限 5 一格不动**（那是伤害节流闸：间隔 = 30/(5-0.5) ≈ 6.7 帧）。
CHASE_BURST_RP_DONOR = 30             # 官方火龙母本的参考点寿命（漂移即拒绝）
CHASE_BURST_HIT_LIFETIME = 30         # 判定区寿命＝伤害闸，跟着母本，不随视觉窗口走

# 克拉莉丝末端裁段（调研卡 C §2.2 落法 A）：母本漂移即拒绝
CLARISSE_TOTAL = 157
CLARISSE_CUT = 78
CLARISSE_ROOT_R = 1073741824
CLARISSE_NEW_R = (1 << 30) | CLARISSE_CUT
CLARISSE_NEW_T = CLARISSE_TOTAL - CLARISSE_CUT
# 反馈轮 2：把单段 `neutral`(once) 切成官方 722 同形的 start/loop/end 三段。
# 首段名保持 `neutral`（官方两种首段名都有先例，保持母本名最稳）。
CLARISSE_SEQUENCES = (
    {"begin": 1, "end": 20, "name": "neutral", "kind": "pass"},
    {"begin": 21, "end": 54, "name": "loop", "kind": "loop"},
    {"begin": 55, "end": CLARISSE_NEW_T, "name": "end", "kind": "once"},
)
# 爆炸音效：母本 `se_clarisse` 实测 5.068s＝304 帧、峰值在第 89 帧（它是克拉莉丝整段
# 157 帧技能的蓄力音，我们却把它按在「爆炸已经发生」的那一帧上）⇒ 听到的轰鸣比画面晚 1.5s、
# 长 4 倍，这就是「音效和动画不匹配」。换成 `se_fire_large_explosion`：2.377s＝143 帧，
# 峰值第 23 帧（正好是火球最大的时候），衰到 10% 在第 89 帧（画面 73 帧结束）。
BURST_SOUND = "sound_effect/fire/se_fire_large_explosion"
BURST_SOUND_DONOR = "sound_effect/unique/se_clarisse"


class KitError(KL.KitError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ignition_growth(tree, expected_hits) -> tuple[Any, dict[str, Any]]:
    """``with_ignition_growth`` ＋ 第二批封顶：把入口绑定的层数上限 99 → :data:`IGNITION_DSL_CAP`。

    只改 ``BindConditionAccumulationVariable`` 第 5 参（变量上限）；vlv 每层增量、段数分摊、
    伤害归属一格不动 ⇒ 点火 ≤10 层时倍率与改前逐层相同，>10 层后不再增长。
    """
    tree, meta = with_ignition_growth(tree, expected_hits)
    head = tree[11][1][0]
    binds = list(wf_dsl.iter_dsl_commands(tree, "BindConditionAccumulationVariable"))
    if (len(binds) != 1 or head[0] != "Command" or head[1] is not binds[0]
            or binds[0][:5] != ["BindConditionAccumulationVariable", -17, 11999005,
                                ["DCUnique", int(UID)], 1] or binds[0][5] != 99):
        raise KitError(f"ignition binding drifted: {binds}")
    binds[0][5] = IGNITION_DSL_CAP
    return tree, dict(meta, max_layers=IGNITION_DSL_CAP)


_IGNITION_BIND_HEAD = ["BindConditionAccumulationVariable", -17, 11999005, ["DCUnique", int(UID)], 1]


def pf_ignition_growth(tree, expected_hits) -> tuple[Any, dict[str, Any]]:
    """特殊强化弹射三档技能树：``with_ignition_growth`` 原样（上限 :data:`IGNITION_LEADER_CAP`）。

    2026-09-27 第三轮（口径 U2）：这三棵树只由队长 #6–#8（火共鸣）的 629 调起，本来就只在「当队长且火共鸣」
    时存在 ⇒ 撤回第二批的 10 层封顶，不加旗号；输出与第二批前 live 逐字节相同。
    """
    tree, meta = with_ignition_growth(tree, expected_hits)
    binds = list(wf_dsl.iter_dsl_commands(tree, "BindConditionAccumulationVariable"))
    if (len(binds) != 1 or tree[11][1][0] != ["Command", binds[0]]
            or binds[0] != [*_IGNITION_BIND_HEAD, IGNITION_LEADER_CAP]):
        raise KitError(f"PF ignition binding drifted: {binds}")
    return tree, dict(meta, max_layers=IGNITION_LEADER_CAP)


def leader_gate(tree) -> tuple[Any, dict[str, Any]]:
    """技能两档 / 引擎之炎：根块整段包进 ``ConditionalsChangeSkillFlag(LEADER_SKILL_FLAG, 开支, 关支)``。

    输入 = :func:`ignition_growth` 的输出（点火绑定在根块首条、上限 :data:`IGNITION_DSL_CAP`，vlv 消费点全在其后）。
    关支 = 输入根块逐字；开支 = 同一段只把绑定上限改回 :data:`IGNITION_LEADER_CAP`（第二批前 int 99）。
    绑定起到块尾整段入支：分支在局部环境执行，分支里的变量分支外看不到（ActionEvaluator.as case 86）。
    两侧复用同一组绑定号（live 先例杰拉德 149999 技能根部同形）；每侧内部仍唯一（:func:`gate_branches` 可取出逐支核对）。
    """
    out = copy.deepcopy(tree)
    if out[0] != "ActionDsl" or out[10] != 0 or out[11][0] != "Block":
        raise KitError("leader gate expects a skill-damage ActionDsl root")
    if list(wf_dsl.iter_dsl_commands(out, "ConditionalsChangeSkillFlag")):
        raise KitError("tree already carries a ConditionalsChangeSkillFlag (leader gate applied twice?)")
    body = out[11][1]
    binds = list(wf_dsl.iter_dsl_commands(out, "BindConditionAccumulationVariable"))
    if (len(binds) != 1 or not body or body[0] != ["Command", binds[0]]
            or binds[0] != [*_IGNITION_BIND_HEAD, IGNITION_DSL_CAP]):
        raise KitError(f"leader gate: ignition binding must be the root's first command capped at "
                       f"{IGNITION_DSL_CAP}: {binds}")
    closed = copy.deepcopy(body)
    opened = copy.deepcopy(body)
    opened[0][1][5] = IGNITION_LEADER_CAP
    out[11][1] = [["Command", ["ConditionalsChangeSkillFlag", LEADER_SKILL_FLAG,
                               ["Block", opened], ["Block", closed]]]]
    return out, {"flag": LEADER_SKILL_FLAG, "flag_kind": LEADER_SKILL_FLAG_KIND,
                 "open_cap": IGNITION_LEADER_CAP, "closed_cap": IGNITION_DSL_CAP,
                 "wrapped_root_commands": len(body)}


def gate_branches(tree) -> list[list]:
    """根块若是唯一一条旗号 2 分支 ⇒ ``[开支块, 关支块]``；否则（第二批及以前的包）⇒ ``[根块]``。"""
    body = tree[11][1]
    if (len(body) == 1 and body[0][0] == "Command"
            and body[0][1][0] == "ConditionalsChangeSkillFlag" and body[0][1][1] == LEADER_SKILL_FLAG):
        return [body[0][1][2], body[0][1][3]]
    return [tree[11]]


# ---------------------------------------------------------------- 设计稿对账

def _design(ctx) -> dict[str, Any] | None:
    path = ctx.pack.batch_dir / "design" / "magnus.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_cells(cells: Any) -> dict[int, str]:
    return {int(k): ("" if v is None else str(v)) for k, v in dict(cells or {}).items()}


def _design_problems(design: dict[str, Any]) -> list[str]:
    """kit 的行计划与设计稿 ``plan_rework1`` 逐项对账（donor / source / cells / 预期面板文案）。"""
    problems: list[str] = []
    plan = design.get("plan_rework1")
    if not plan:
        return ["design/magnus.json lacks the plan_rework1 block"]

    def cmp(label: str, got: tuple[str, str, dict[int, str], str], want: dict[str, Any]) -> None:
        donor, source, cells, expect = got
        if donor != want.get("donor"):
            problems.append(f"{label}: donor {donor!r} != design {want.get('donor')!r}")
        if source != want.get("source"):
            problems.append(f"{label}: source {source!r} != design {want.get('source')!r}")
        if _norm_cells(cells) != _norm_cells(want.get("cells")):
            problems.append(f"{label}: cells differ from design")
        if expect != want.get("desc_expected"):
            problems.append(f"{label}: desc {expect!r} != design {want.get('desc_expected')!r}")

    rows = plan.get("leader_ability", {}).get("rows", [])
    if len(rows) != len(LEADER):
        problems.append(f"leader row count {len(LEADER)} != design {len(rows)}")
    for index, (got, want) in enumerate(zip(LEADER, rows)):
        cmp(f"leader#{index}", got, want)

    keys = plan.get("ability", {}).get("keys", {})
    for slot, records in PLAN.items():
        want_block = keys.get(f"{CID}{slot}")
        if want_block is None:
            problems.append(f"ability {CID}{slot}: missing from design")
            continue
        want_records = want_block.get("records", [])
        if len(want_records) != len(records):
            problems.append(f"ability {CID}{slot}: {len(records)} records != design {len(want_records)}")
        for index, (got, want) in enumerate(zip(records, want_records)):
            cmp(f"ability {CID}{slot}#{index}", got, want)

    add = plan.get("unique_conditions", {}).get("add", [])
    want_unique = ((UID, UNIQUE_DONOR, UNIQUE_NAME, UNIQUE_CELLS),
                   (UID_AURA, AURA_UNIQUE_DONOR, AURA_UNIQUE_NAME, AURA_UNIQUE_CELLS))
    if [a.get("key") for a in add] != [key for key, _d, _n, _c in want_unique]:
        problems.append(f"unique_conditions design block unexpected: {[a.get('key') for a in add]}")
    else:
        for got, (key, donor, name, cells) in zip(add, want_unique):
            if got.get("donor") != donor:
                problems.append(f"unique {key}: donor {got.get('donor')!r} != {donor!r}")
            if got.get("name") != name:
                problems.append(f"unique {key}: name {got.get('name')!r} != {name!r}")
            if _norm_cells(got.get("cells")) != _norm_cells(cells):
                problems.append(f"unique {key}: cells differ from design")

    energy = plan.get("skills", {}).get("energy", {})
    for level in ("1", "2"):
        want = tuple(str(x) for x in energy.get(f"level{level}", ()))
        if want != ENERGY[level]:
            problems.append(f"energy level{level} {ENERGY[level]} != design {want}")

    cas = {row.get("key"): row.get("text")
           for row in plan.get("texts", {}).get("custom_ability_string", {}).get("rows", [])}
    for key, text in CAS_TEXTS.items():
        if cas.get(key) != text:
            problems.append(f"custom_ability_string {key}: text differs from design")

    pf = plan.get("pf_override", {})
    if pf.get("key") != PF_KEY or list(pf.get("programs", ())) != list(PF_PROGRAMS):
        problems.append("power_flip_action design block drift")

    route = design.get("voice", {}).get("route", {})
    if {str(k): str(v) for k, v in route.items()} != {str(k): str(v) for k, v in VOICE_ROUTE.items()}:
        problems.append(f"voice route {VOICE_ROUTE} != design {route}")
    return problems


# ---------------------------------------------------------------- 固有状态 + 图标

def build_unique(ctx) -> dict[str, list[str]]:
    """两个固有状态：「引擎点火」（99 层 / 无时限）与「烈焰光环」（1 层 / 与光环寿命同长）。"""
    key, row = KL.unique_row(ctx, ctx.spec, 1, UNIQUE_DONOR, UNIQUE_CELLS, name=UNIQUE_NAME)
    if key != UID:
        raise KitError(f"unique id {key} != {UID}")
    if row[3] != UNIQUE_FRAMES or row[4] != UNIQUE_CAP:
        raise KitError(f"unique duration/cap unexpected: c3={row[3]!r} c4={row[4]!r}")

    aura_key, aura_row = KL.unique_row(ctx, ctx.spec, 2, AURA_UNIQUE_DONOR, AURA_UNIQUE_CELLS,
                                       name=AURA_UNIQUE_NAME)
    if aura_key != UID_AURA:
        raise KitError(f"aura unique id {aura_key} != {UID_AURA}")
    if aura_row[3] != str(AURA_FRAMES):
        raise KitError(f"aura unique duration c3={aura_row[3]!r} != AURA_FRAMES {AURA_FRAMES}")
    if aura_row[4] != AURA_UNIQUE_CAP or aura_row[4] in ("", "(None)"):
        raise KitError(f"aura unique cap c4={aura_row[4]!r} must be the official '1'")
    if aura_row[11] != "0":
        raise KitError(f"aura unique direction c11={aura_row[11]!r} must be '0' (Good/增益)")
    if aura_row[12] != "0":
        raise KitError(f"aura unique overwrite_mode c12={aura_row[12]!r} must be '0' "
                       "(刷新时长靠 ChooseOneWithLongerRemainingTime)")
    if aura_row[14] != "(None)":
        raise KitError(f"aura unique c14={aura_row[14]!r} must stay '(None)' (不碰 PF 语音)")

    entries = {key: row, aura_key: aura_row}
    KL.write_unique(ctx, ctx.spec, entries)
    return entries


ICON_K = 8                      # 8× 超采样画布（与 seasonal7 同工艺）
ICON_N = 48 * ICON_K


def _icon_plate(K: int, N: int):
    """夜黑圆角底 + 金边，返回 ``(layer, inner_mask)``（本批 48×48 状态图标的统一底座）。"""
    from PIL import Image, ImageDraw
    layer = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    inner = Image.new("L", (N, N), 0)
    ImageDraw.Draw(inner).rounded_rectangle((3 * K, 3 * K, 45 * K - 1, 45 * K - 1),
                                            radius=5 * K, fill=255)
    top, bot = (36, 30, 44), (18, 14, 22)
    grad = Image.new("RGBA", (1, N))
    for y in range(N):
        t = y / (N - 1)
        grad.putpixel((0, y), tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    layer.paste(grad.resize((N, N)), (0, 0), inner)
    gold = (216, 150, 58, 255)
    ImageDraw.Draw(layer).rounded_rectangle((4 * K, 4 * K, 44 * K - 1, 44 * K - 1),
                                            radius=4 * K, outline=gold, width=2 * K)
    return layer, inner


def _icon_finish(frame, layer):
    """LANCZOS 缩回 48×48，并用官方图标的 alpha 当外框（alpha 一格不改，图集门禁才不红）。"""
    from PIL import Image
    small = layer.resize((48, 48), Image.LANCZOS)
    out = Image.new("RGBA", (48, 48), (255, 255, 255, 0))
    fp, op, sp = frame.load(), out.load(), small.load()
    for y in range(48):
        for x in range(48):
            r, g, b, a = sp[x, y]
            fa = fp[x, y][3]
            if a:
                op[x, y] = (round((r * a + 255 * (255 - a)) / 255),
                            round((g * a + 255 * (255 - a)) / 255),
                            round((b * a + 255 * (255 - a)) / 255), fa)
            else:
                op[x, y] = (255, 255, 255, fa)
    return out


def draw_icon(frame):
    """48×48「引擎点火」：夜黑圆角底 + 金边，上弦月剪影，凹侧一簇火苗。"""
    from PIL import Image, ImageDraw
    if frame.size != (48, 48):
        raise KitError(f"icon frame donor must be 48x48, got {frame.size}")
    K, N = ICON_K, ICON_N
    layer, inner = _icon_plate(K, N)
    moon = (242, 212, 121, 255)

    # 上弦月：大圆减去偏右上的小圆，凹侧朝右下
    disc = Image.new("L", (N, N), 0)
    ImageDraw.Draw(disc).ellipse((8.5 * K, 9.5 * K, 31.5 * K, 32.5 * K), fill=255)
    cut = Image.new("L", (N, N), 0)
    ImageDraw.Draw(cut).ellipse((15.0 * K, 6.5 * K, 38.0 * K, 29.5 * K), fill=255)
    crescent = Image.composite(Image.new("L", (N, N), 0), disc, cut)
    layer.paste(Image.new("RGBA", (N, N), moon), (0, 0),
                Image.composite(crescent, Image.new("L", (N, N), 0), inner))

    # 火苗：外焰 #FF8A3C → 内焰 #FFE08A（竖向渐变，走蒙版）
    outer = [(31.0, 20.0), (35.6, 27.2), (36.4, 32.6), (33.6, 37.8), (28.4, 38.4),
             (25.0, 34.6), (25.6, 29.6), (28.4, 25.6), (29.4, 28.2)]
    flame = Image.new("L", (N, N), 0)
    ImageDraw.Draw(flame).polygon([(x * K, y * K) for x, y in outer], fill=255)
    fgrad = Image.new("RGBA", (1, N))
    lo, hi = (255, 138, 60), (255, 224, 138)
    for y in range(N):
        t = max(0.0, min(1.0, (y / (N - 1) - 0.40) / 0.45))
        fgrad.putpixel((0, y), tuple(round(lo[i] + (hi[i] - lo[i]) * (1 - t)) for i in range(3)) + (255,))
    layer.paste(fgrad.resize((N, N)), (0, 0),
                Image.composite(flame, Image.new("L", (N, N), 0), inner))
    core = [(31.0, 27.0), (33.4, 31.4), (31.6, 35.8), (28.6, 34.4), (28.8, 30.4)]
    ImageDraw.Draw(layer).polygon([(x * K, y * K) for x, y in core], fill=(255, 240, 196, 255))
    return _icon_finish(frame, layer)


# 「烈焰光环」图标几何（48 单位坐标系，中心 (24,25)）：一圈火环，外沿是连续的火舌波。
# 外轮廓 r(θ) = 环身半径 + 振幅 × sin(π·u^SKEW)^SHARP，u ＝ 该火舌内的归一化角度。
# SHARP > 1 ⇒ 尖端窄、谷底宽（写 <1 会把火舌拉成齿轮的方牙）；SKEW > 1 ⇒ 峰值后移，
# 每条火舌朝同一侧倾，整圈看起来是在旋转燃烧，而不是一圈对称的齿。
AURA_ICON_CENTER = (24.0, 25.0)
AURA_ICON_R_OUT = 11.0                # 环身外半径（火舌谷底）
AURA_ICON_R_IN = 8.6                  # 环心半径（挖空）
AURA_ICON_TONGUES = 8                 # 火舌数
AURA_ICON_AMP = 6.4                   # 火舌高度（尖端半径 = R_OUT + AMP）
AURA_ICON_SHARP = 3.6                 # 尖端锐度（越大越尖）
AURA_ICON_SKEW = 2.0                  # 火舌倾斜（峰值后移）
AURA_ICON_TILT = 14.0                 # 整圈旋转（度）：避开正上方一根独苗
AURA_ICON_HIGHLIGHT = 9.7             # 内侧高光环半径
AURA_ICON_STEPS = 480                 # 外轮廓采样点数


def draw_aura_icon(frame):
    """48×48「烈焰光环」：同款夜黑底＋金边，中央一圈燃烧的光环。

    与「引擎点火」共用 :func:`_icon_plate` / :func:`_icon_finish` 与同一套火焰渐变，
    所以两枚图标的底座、金边宽度、配色与 alpha 外框完全一致（本批统一风格）。
    """
    import math
    from PIL import Image, ImageDraw
    if frame.size != (48, 48):
        raise KitError(f"icon frame donor must be 48x48, got {frame.size}")
    K, N = ICON_K, ICON_N
    layer, inner = _icon_plate(K, N)
    cx, cy = AURA_ICON_CENTER

    def box(radius):
        return ((cx - radius) * K, (cy - radius) * K, (cx + radius) * K, (cy + radius) * K)

    # 火环本体：带火舌的外轮廓减掉中心圆（画布 y 向下 ⇒ 角度取负 sin）
    points = []
    for step in range(AURA_ICON_STEPS):
        deg = step * 360.0 / AURA_ICON_STEPS
        u = (((deg - AURA_ICON_TILT) * AURA_ICON_TONGUES) % 360.0) / 360.0
        wave = math.sin(math.pi * (u ** AURA_ICON_SKEW)) ** AURA_ICON_SHARP
        radius = AURA_ICON_R_OUT + AURA_ICON_AMP * wave
        rad = math.radians(deg)
        points.append(((cx + radius * math.cos(rad)) * K, (cy - radius * math.sin(rad)) * K))
    ring = Image.new("L", (N, N), 0)
    ImageDraw.Draw(ring).polygon(points, fill=255)
    hole = Image.new("L", (N, N), 0)
    ImageDraw.Draw(hole).ellipse(box(AURA_ICON_R_IN), fill=255)
    mask = Image.composite(Image.new("L", (N, N), 0), ring, hole)

    # 配色与「引擎点火」的火苗同一套渐变：外焰 #FF8A3C → 内焰 #FFE08A
    fgrad = Image.new("RGBA", (1, N))
    lo, hi = (255, 138, 60), (255, 224, 138)
    for y in range(N):
        t = max(0.0, min(1.0, (y / (N - 1) - 0.40) / 0.45))
        fgrad.putpixel((0, y), tuple(round(lo[i] + (hi[i] - lo[i]) * (1 - t)) for i in range(3)) + (255,))
    layer.paste(fgrad.resize((N, N)), (0, 0),
                Image.composite(mask, Image.new("L", (N, N), 0), inner))

    # 内侧高光：一圈细亮环，让 48px 下的环心不糊成一团
    glow = Image.new("L", (N, N), 0)
    ImageDraw.Draw(glow).ellipse(box(AURA_ICON_HIGHLIGHT), outline=255,
                                 width=max(1, round(1.1 * K)))
    layer.paste(Image.new("RGBA", (N, N), (255, 240, 196, 255)), (0, 0),
                Image.composite(glow, Image.new("L", (N, N), 0), inner))
    return _icon_finish(frame, layer)


UNIQUE_ICONS = ((UID, UC_ICON_LOGICAL, "draw_icon"),
                (UID_AURA, UC_AURA_ICON_LOGICAL, "draw_aura_icon"))


def install_unique_icon(ctx) -> dict[str, dict[str, Any]]:
    """两枚 48×48 状态图标：alpha 取同一个官方帧 donor，一格不改。"""
    raw = ctx.official_read(UC_ICON_FRAME_DONOR)
    if raw is None:
        _root, raw, _how = ctx.pack.template_asset(UC_ICON_FRAME_DONOR)
    frame = ctx.png_open(raw)
    out: dict[str, dict[str, Any]] = {}
    for key, logical, painter in UNIQUE_ICONS:
        data = ctx.png_store_bytes(globals()[painter](frame))
        ctx.write_asset("common", logical, data)
        back = ctx.png_open(ctx.pack.pkg_path("common", logical).read_bytes())
        if back.size != (48, 48):
            raise KitError(f"unique_condition icon must stay 48x48, got {back.size}")
        if back.getchannel("A").tobytes() != frame.getchannel("A").tobytes():
            raise KitError(f"{logical}: icon alpha differs from the official frame donor")
        out[key] = {"logical": logical, "frame_donor": UC_ICON_FRAME_DONOR,
                    "painter": painter, "sha256": _sha256(data), "bytes": len(data)}
    if len({v["sha256"] for v in out.values()}) != len(out):
        raise KitError("the two unique_condition icons are pixel-identical")
    return out


# ---------------------------------------------------------------- 词条 / 队长技 / 面板串

def build_rows(ctx) -> dict[str, Any]:
    spec = ctx.spec
    evidence: list[dict[str, Any]] = []
    caps: set[str] = set()

    leader: list[list[str]] = []
    for index, (donor, source, cells, expect) in enumerate(LEADER):
        row, ev = KL.build_row(ctx, "leader_ability", donor, cells, source=source,
                               element=spec.element, expect_describe=expect,
                               label=f"leader#{index}")
        leader.append(row)
        evidence.append(ev)
        caps.update(ev["capabilities"])
    if any(r[0] != CODE for r in leader):
        raise KitError(f"leader c0 must be {CODE}: {[r[0] for r in leader]}")
    _leader_forbidden(leader)

    ability: dict[str, list[list[str]]] = {}
    for slot, records in PLAN.items():
        key = f"{CID}{slot}"
        rows: list[list[str]] = []
        for index, (donor, source, cells, expect) in enumerate(records):
            row, ev = KL.build_row(ctx, "ability", donor, cells, source=source,
                                   element=spec.element, expect_describe=expect,
                                   label=f"{key}#{index}")
            rows.append(row)
            evidence.append(ev)
            caps.update(ev["capabilities"])
        KL.check_ability_key(rows, key, CODE, slot)
        ability[key] = rows

    _order_problems(ability[f"{CID}3"])
    _dash_problems(ability[f"{CID}5"])
    return {"leader": leader, "ability": ability, "evidence": evidence,
            "capabilities": sorted(caps)}


LEADER_FORBIDDEN_KINDS = ("422", "724", "713")


def _leader_forbidden(rows: list[list[str]]) -> None:
    """队长表写 422/724/713 = 角色详情页 C7050（记忆卡 wf-dash-parameter-leader-table-trap）。"""
    bad = [(i, r[45], r[107]) for i, r in enumerate(rows)
           if r[45] in LEADER_FORBIDDEN_KINDS or r[107] in LEADER_FORBIDDEN_KINDS]
    if bad:
        raise KitError(f"leader rows carry a forbidden kind (C7050): {bad}")


def _order_problems(rows: list[list[str]]) -> None:
    """槽 3 的硬顺序契约：629 发动追击必须排在同触发的 525 消耗行之前（记忆卡 R3）。

    顺序反了 ⇒ 最后一层先被吃掉，最后一次强化弹射打不出追击。
    """
    kinds = [row[47] for row in rows]
    if "629" not in kinds or "525" not in kinds:
        raise KitError(f"ability slot 3 lost the 629/525 pair: {kinds}")
    if kinds.index("629") > kinds.index("525"):
        raise KitError(f"629 must precede the 525 consume row, got {kinds}")
    invoke, consume = rows[kinds.index("629")], rows[kinds.index("525")]
    for col, what in ((27, "trigger kind"), (30, "threshold"), (31, "threshold"),
                      (34, "trigger limit"), (35, "cooldown")):
        if invoke[col] != consume[col]:
            raise KitError(f"629/525 {what} differ at c{col}: {invoke[col]!r} vs {consume[col]!r}")
    if invoke[6] != consume[6] or invoke[12] != consume[12]:
        raise KitError("629/525 preconditions differ; both must gate on the same unique condition")


def _dash_problems(rows: list[list[str]]) -> None:
    """422 行契约：前置 42 队长、param_id 显式写 '0'、两条强度就是抵消公式的两端。"""
    dash = [r for r in rows if r[109] == "422"]
    if len(dash) != 2:
        raise KitError(f"slot 5 must carry exactly 2 dash rows, got {len(dash)}")
    for row in dash:
        if row[6] != "42":
            raise KitError(f"422 row must gate on precondition 42 (Leader), got {row[6]!r}")
        if row[118] != "0":
            raise KitError(f"422 param_id must be an explicit '0', got {row[118]!r}")
    strengths = sorted(int(r[113]) for r in dash)
    if strengths != sorted((DASH_PARAM0_BASE, DASH_PARAM0_SWIFT)):
        raise KitError(f"dash strengths {strengths} differ from the offset formula")
    # 3.5 × (1 + s0) —— 非 Swift 90×(1+s0) 帧与 Swift 中 20×(1+s0+m) 帧相等
    want = round(3.5 * (1 + DASH_PARAM0_BASE / 100000) * 100000)
    if DASH_PARAM0_SWIFT != want:
        raise KitError(f"swift offset {DASH_PARAM0_SWIFT} != 3.5×(1+s0) = {want}")


def write_strings(ctx) -> dict[str, str]:
    """custom_ability_string：629 / 536 / 722 条目 + 5 个 desc_override。"""
    declared = set(ctx.spec.extra_keys.get(KL.CAS, ()))
    missing = [key for key in CAS_TEXTS if key not in declared]
    if missing:
        raise KitError(f"custom_ability_string keys not declared in SPEC['extra_keys']: {missing}")
    for key, text in CAS_TEXTS.items():
        for line in text.split("\n"):
            KL.check_panel(line.replace(MAIN_ICON, ""),
                           skill_flag=key in SKILL_FLAG_TEXT_KEYS, label=key)
    for slot in SLOT_OVERRIDE_SLOTS:
        rendered = CAS_TEXTS[SLOT_OVERRIDE[slot]].split("\n")
        wants_icon = PLAN[slot][0][2].get(1) == "false"
        if any(line.startswith(MAIN_ICON) != wants_icon for line in rendered):
            raise KitError(f"slot {slot} desc_override main-position icon does not match c1")
    official = ctx.official_flat(KL.CAS)
    clashes = [key for key in CAS_TEXTS if key in official]
    if clashes:
        raise KitError(f"custom_ability_string keys already exist officially: {clashes}")
    ctx.write_flat(KL.CAS, {key: [[text]] for key, text in CAS_TEXTS.items()})
    return dict(CAS_TEXTS)


# ---------------------------------------------------------------- 语音路由

def write_voice_route(ctx) -> list[str]:
    import wf_seasonal7_voice as V
    cols = KL.voice_route(CODE, VOICE_ROUTE)
    if cols != ["1", "28", UID, "", "", VOICE_KEY, "false", "false"]:
        raise KitError(f"unexpected voice route columns: {cols}")
    row = ctx.csv_split(ctx.pkg_flat(KL.CHARACTER)[CID_S])[0]
    new_row = V.route_character_row(list(row), cols, CODE)
    ctx.write_flat(KL.CHARACTER, {CID_S: [new_row]})
    return cols


# ---------------------------------------------------------------- action_skill

def write_action_skill(ctx) -> dict[str, list[str]]:
    inner = ctx.pkg_nested(CODE)
    if set(inner) != {"1", "2"}:
        raise KitError(f"package action_skill inner keys {sorted(inner)}")
    out: dict[str, list[str]] = {}
    for level, cells in sorted(inner.items()):
        cells = list(cells)
        if len(cells) != 24:
            raise KitError(f"action_skill {level} has {len(cells)} columns, expected 24")
        if cells[7] != ctx.program_path(level):
            raise KitError(f"action_skill {level} program path {cells[7]!r} unexpected")
        if cells[0] != TEXTS[f"skill{level}"] or cells[1] != TEXTS[f"desc{level}"]:
            raise KitError(f"action_skill {level} name/desc differ from TEXTS (rerun tables)")
        if cells[2] != "dynamic/skill/atk_front":
            raise KitError(f"action_skill {level} auto-cast target {cells[2]!r} differs from the template")
        cells[4], cells[5], cells[6] = ENERGY[level]
        out[level] = cells
    ctx.write_nested(KL.ACTION, CODE, {lv: [cells] for lv, cells in out.items()},
                     replace_inner=True)
    return out


# ---------------------------------------------------------------- 特效克隆 + 染色 + parts 手术

def fx_lut_path(ctx) -> Path | None:
    """特效染色 LUT：特效素材代理交付到 ``W/fx/magnus/``；缺文件就不染色，照常克隆。"""
    batch = ctx.pack.batch_dir
    for candidate in (batch / "rework1" / "fx" / "magnus" / "fx_lut.json",
                      batch / "fx" / "magnus" / "fx_lut.json",
                      KL.pixel_dir(ctx) / "fx_lut.json"):
        if candidate.is_file():
            return candidate
    return None


def fx_transforms(ctx) -> tuple[Path | None, dict[str, Any]]:
    """把交付的 LUT 拆成 {donor 族名: png_transform}。

    交付件有两种形状：单族的裸 ``ma-fx-lut/1``（对三族统一套用），或特效代理用的
    ``{"families": {"<donor>": <ma-fx-lut/1>, …}}`` 合集（每族一份）。
    ``KL.png_transform_from_lut`` 只吃文件，所以合集会先拆进 workspace 的 evidence 目录。
    """
    lut = fx_lut_path(ctx)
    if lut is None:
        return None, {}
    data = json.loads(lut.read_text(encoding="utf-8"))
    if data.get("schema") == KL.LUT_SCHEMA:
        shared = KL.png_transform_from_lut(lut)
        return lut, {src.rsplit("/", 1)[-1]: shared for _sub, src, _n in FX_CLONES}
    families = data.get("families")
    if not isinstance(families, dict):
        raise KitError(f"unrecognised fx_lut shape (no schema, no families): {lut}")
    out: dict[str, Any] = {}
    target = ctx.pack.evidence / "fx"
    target.mkdir(parents=True, exist_ok=True)
    for _sub, src_dir, _names in FX_CLONES:
        donor = src_dir.rsplit("/", 1)[-1]
        block = families.get(donor)
        if block is None:
            continue
        split = target / f"fx_lut_{donor}.json"
        split.write_text(json.dumps(block, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
        out[donor] = KL.png_transform_from_lut(split)
    if not out:
        raise KitError(f"fx_lut {lut} carries none of the three donor families")
    return lut, out


def lance_hex_boxes(ctx) -> dict[str, tuple[int, int, int, int]]:
    """官方 zeta 图集里两块六边形 rect 的存图区域（擦图用），带母本漂移断言。

    判据全部从官方 atlas/PNG 现算，不写死坐标：
    - 两个叶名必须都在图集里，且 `zeta_lance_end` 的 parts 确实引用它们；
    - `k` 必须是**单一颜色** #FFFF00（实心黄六边形），形状漂移即拒绝；
    - 两块 rect 不许与本族克隆的其它基名（`zeta_lance` / `zeta_lance_end` 的其余叶子）
      的存图区域相交——相交就说明图集做了去重别名，擦一块会连坐（记忆卡「rect 别名污染」）。
    """
    src_dir = dict((sub, src) for sub, src, _n in FX_CLONES)[LANCE_END_SUBDIR]
    donor = src_dir.rsplit("/", 1)[-1]
    names = dict((sub, names) for sub, _src, names in FX_CLONES)[LANCE_END_SUBDIR]
    # 用 clone_effect_family 同一条取件通路（template_asset：官方优先，缺失回落 live），
    # 否则断言看的是一份、擦的是另一份。
    atlas = ctx.amf_parse(ctx.pack.template_asset(f"{src_dir}/{donor}.atlas.amf3.deflate")[1])
    sheet = ctx.png_open(ctx.pack.template_asset(f"{src_dir}/{donor}.png")[1]).convert("RGBA")
    boxes: dict[str, tuple[int, int, int, int]] = {}
    keep: list[tuple[int, int, int, int]] = []
    for item in atlas:
        if not isinstance(item, dict) or "n" not in item:
            continue
        parts = str(item["n"]).split("/")
        if len(parts) < 2:
            continue
        base, leaf = parts[-2], parts[-1]
        box = (int(item["x"]), int(item["y"]),
               int(item["x"]) + int(item["w"]), int(item["y"]) + int(item["h"]))
        if f"{base}/{leaf}" in LANCE_HEX_LEAVES:
            boxes[f"{base}/{leaf}"] = box
        elif base in names:
            keep.append(box)
    if sorted(boxes) != sorted(LANCE_HEX_LEAVES):
        raise KitError(f"zeta atlas lost the hexagon rects: got {sorted(boxes)}")
    for leaf, want in LANCE_HEX_SOLID.items():
        colours = {p[:3] for p in sheet.crop(boxes[leaf]).getdata() if p[3] > 8}
        if colours != {want}:
            raise KitError(f"{leaf} is no longer the solid #{want} hexagon: {sorted(colours)[:6]}")
    for leaf, box in boxes.items():
        for other in keep:
            if box[0] < other[2] and other[0] < box[2] and box[1] < other[3] and other[1] < box[3]:
                raise KitError(f"{leaf} rect {box} overlaps a kept rect {other} "
                               "(图集去重别名，擦一块会连坐)")
    return boxes


def lance_png_transform(ctx, base_transform):
    """先跑染色 LUT，再把两块六边形 rect 擦成全透明。"""
    boxes = lance_hex_boxes(ctx)

    def transform(image):
        out = base_transform(image) if base_transform is not None else image
        out = out.convert("RGBA").copy()
        for box in boxes.values():
            out.paste((0, 0, 0, 0), box)
        return out

    return transform


def clone_effects(ctx):
    lut, transforms = fx_transforms(ctx)
    families: dict[str, Any] = {}
    for subdir, src_dir, names in FX_CLONES:
        donor = src_dir.rsplit("/", 1)[-1]
        png_transform = transforms.get(donor)
        if subdir == LANCE_END_SUBDIR:
            png_transform = lance_png_transform(ctx, png_transform)
        fam = ctx.clone_effect_family(src_dir, subdir, list(names),
                                      layout="codename",
                                      png_transform=png_transform)
        missing = list(fam.get("missing_effects") or ())
        if missing:
            raise KitError(f"effect family {src_dir} missing bases {missing}")
        if sorted(fam.get("copied_bases") or ()) != sorted(names):
            raise KitError(f"effect family {src_dir} copied {fam.get('copied_bases')} != {names}")
        families[subdir] = fam
    surgery = cut_clarisse_tail(ctx, families["burst"])
    from wf_magnus_fx_cleanup import apply_cloned
    cleanup = apply_cloned(ctx)
    from wf_magnus_pf_orbit import assets
    for logical, data in assets(lambda p: ctx.official_read(p, 'common')).items():
        ctx.write_asset('common', logical, data)
    return {"lut": str(lut) if lut is not None else None,
            "recolored": sorted(transforms),
            "families": {k: {"src_dir": v["src_dir"], "dst_dir": v["dst_dir"],
                             "copied_bases": v["copied_bases"],
                             "files": [f["target"] for f in v["files"]]}
                         for k, v in families.items()},
            "clarisse_tail": surgery, "visual_cleanup": cleanup}, families


def _pkg_amf(ctx, root: str, logical: str):
    return ctx.amf_parse(ctx.pack.pkg_path(root, logical).read_bytes())


def cut_clarisse_tail(ctx, family) -> dict[str, Any]:
    """只留克拉莉丝的末端圆形爆炸（调研卡 C §2.2 落法 A：改 3 个数字，零结构手术）。

    ``clone_effect_family`` 只有 ``png_transform`` 钩子、没有 parts 钩子 ⇒ 手术必须在 clone
    之后重新施加，否则每次 ``--step kit`` 都会被官方母本冲掉（09-16 特克托激光的教训）。
    母本任何一处漂移都直接拒绝。
    """
    dst = family["dst_dir"]
    root = family["files"][0]["root"]
    parts_logical = f"{dst}/clarisse.parts.amf3.deflate"
    timeline_logical = f"{dst}/clarisse.timeline.amf3.deflate"
    parts = _pkg_amf(ctx, root, parts_logical)
    timeline = _pkg_amf(ctx, root, timeline_logical)

    g0 = parts["g"][0]
    keyframe = g0["s"][0]["l"][0]
    if int(keyframe["r"]) != CLARISSE_ROOT_R or int(keyframe["t"]) != CLARISSE_TOTAL:
        raise KitError(f"clarisse root keyframe drift: r={keyframe['r']} t={keyframe['t']}")
    if int(g0["t"]) != CLARISSE_TOTAL or len(g0["s"]) != 1:
        raise KitError(f"clarisse root group drift: t={g0['t']} segments={len(g0['s'])}")
    seq = timeline["sequences"]
    if len(seq) != 1 or seq[0]["begin"] != 1 or int(seq[0]["end"]) != CLARISSE_TOTAL:
        raise KitError(f"clarisse timeline drift: {seq}")

    sounds = timeline.get("sounds") or []
    if len(sounds) != 1 or sounds[0].get("path") != BURST_SOUND_DONOR:
        raise KitError(f"clarisse timeline sounds drift: {sounds}")

    keyframe["r"] = float(CLARISSE_NEW_R)      # kind=1（播一次），起始帧 78
    keyframe["t"] = CLARISSE_NEW_T
    g0["t"] = CLARISSE_NEW_T
    seq[0]["end"] = CLARISSE_NEW_T             # begin 保持 1

    # 反馈轮 2：切出 start/loop/end 三段（官方 722 同形），并换掉对不上画面的爆炸音。
    template = dict(seq[0])
    timeline["sequences"] = [template | dict(s) for s in CLARISSE_SEQUENCES]
    _sequence_problems(timeline["sequences"], CLARISSE_NEW_T)
    sounds[0]["path"] = BURST_SOUND

    for logical, tree in ((parts_logical, parts), (timeline_logical, timeline)):
        data = ctx.amf_bytes(tree)
        ctx.write_asset(root, logical, data)
        if _pkg_amf(ctx, root, logical) != tree:
            raise KitError(f"{logical} readback differs from the written tree")
    return {"start_frame": CLARISSE_CUT, "frames": CLARISSE_NEW_T,
            "r": CLARISSE_NEW_R, "files": [parts_logical, timeline_logical],
            "sequences": [dict(s) for s in timeline["sequences"]],
            "sounds": [dict(s) for s in sounds],
            "show_lifetime": PF_HIT_WINDOW}


def _sequence_problems(sequences, total: int) -> None:
    """序列表必须无缝覆盖 1..total、最后一段是 `end`(once)、寿命落点在 loop 段内。"""
    cursor = 1
    for item in sequences:
        if int(item["begin"]) != cursor:
            raise KitError(f"sequence gap at {item}: expected begin {cursor}")
        if int(item["end"]) < int(item["begin"]):
            raise KitError(f"sequence inverted: {item}")
        cursor = int(item["end"]) + 1
    if cursor != total + 1:
        raise KitError(f"sequences cover 1..{cursor - 1}, parts total is {total}")
    if sequences[-1]["name"] != "end" or sequences[-1]["kind"] != "once":
        raise KitError("last sequence must be the `end`/`once` tail the client jumps to")
    loop = [s for s in sequences if s["kind"] == "loop"]
    if len(loop) != 1:
        raise KitError("exactly one `loop` sequence is required")
    if not int(loop[0]["begin"]) < PF_HIT_WINDOW < int(loop[0]["end"]):
        raise KitError(f"ShowEffect lifetime {PF_HIT_WINDOW} must land strictly inside the loop "
                       f"{loop[0]['begin']}..{loop[0]['end']} (落在边界会多播一次尾巴)")


# ---------------------------------------------------------------- DSL 工具

def _commands(tree, name: str | None = None) -> list[list]:
    return list(wf_dsl.iter_dsl_commands(tree, name) if name
                else wf_dsl.iter_dsl_commands(tree))


def _declared_ids(tree) -> list[int]:
    """树里声明的绑定 id：RP c10、CreateHitArea c19/c21/c22、FindAllSubjects c1。"""
    ids: list[int] = []
    for c in _commands(tree):
        if c[0] == "CreateReferencePoint":
            ids.append(c[10])
        elif c[0] == "CreateHitArea":
            ids.extend((c[19], c[21], c[22]))
        elif c[0] == "FindAllSubjects":
            ids.append(c[1])
    return ids


def _only(items: list, what: str) -> Any:
    if len(items) != 1:
        raise KitError(f"expected exactly 1 {what}, got {len(items)}")
    return items[0]


def _slv(value: float) -> list[dict[str, float]]:
    return [{"min": value, "max": value}]


def _rewrite(ctx, tree, families) -> Any:
    for fam in families.values():
        tree, _info = ctx.rewrite_effect_refs(tree, fam)
    return tree


# ---------------------------------------------------------------- 主技能：魏虎式光圈

def aura_block(ctx, level: str) -> tuple[list[list], dict[str, Any]]:
    """从魏虎 111105 的技能树里摘出「球上光圈 + 长寿命碰撞判定」整块（调研卡 C §2.3）。

    官方原块里的 ``ACToleranceOfElement``（火耐性↓）丢掉——目标面板没有这一条；
    命中特效换引擎内置 ``Fine`` ⇒ 只需克隆 ``_aura`` 一个基名。
    """
    donor = ctx.template_dsl(AURA_DONOR)
    show = _only([c for c in _commands(donor, "ShowEffect")
                  if str(c[2][1]).endswith("_aura")], "anger_investigator aura ShowEffect")
    area = _only([c for c in _commands(donor, "CreateHitArea") if c[2] == -18],
                 "anger_investigator ball hit area")
    if show[3] != -18 or show[6] != ["AB"] or area[3] != ["AB"]:
        raise KitError(f"anger_investigator aura donor drift: subject={show[3]} coord={show[6]}/{area[3]}")
    if (area[19], area[21], area[22]) != (0, 1, 2) or area[24] != 0:
        raise KitError(f"anger_investigator hit-area binds drift: {area[19:25]}")
    # 命中跳数/寿命/跟随球这三格是「碰到就打」的命门：母本漂移就别继续往下改
    if area[7] is not True or area[13] != ["SpecifyHitAreaLifetimeDirectly", 600]:
        raise KitError(f"anger_investigator hit-area tracking/lifetime drift: {area[7]} {area[13]}")
    if area[14][0] != "CalculatedUsingMaxNumOfHits" or area[15][0] != "Some":
        raise KitError(f"anger_investigator hit accounting drift: {area[14]} {area[15]}")

    show, area = copy.deepcopy(show), copy.deepcopy(area)
    scale, radius, mult = AURA_TUNING[level]
    show[1] = "aura_ring"
    show[5] = ["SpecifyEffectLifetimeDirectly", AURA_FRAMES]
    show[12] = ["Some", _slv(scale)]

    area[9] = ["Circle", _slv(radius)]
    area[13] = ["SpecifyHitAreaLifetimeDirectly", AURA_FRAMES]
    # 母本的 CalculatedUsingMaxNumOfHits(10) 会被客户端换算成 600/9.5≈63 帧的最小间隔；
    # 显式写 30 帧，每目标硬上限仍由 p15 管（总跳数不变，见 AURA_HIT_INTERVAL 注释）。
    area[14] = ["SpecifyMinHitIntervalDirectly", AURA_HIT_INTERVAL]
    area[15] = ["Some", _slv(AURA_MAX_HITS)]
    area[19], area[21], area[22] = AURA_BINDS
    body = area[23][1]
    keep = [n for n in body
            if not (n[0] == "Command" and n[1][0] == "CreateCondition")]
    if len(keep) != len(body) - 1:
        raise KitError(f"aura on-hit block shape drift ({len(body)} → {len(keep)})")
    area[23][1][:] = keep
    cna = _only(_commands(area, "CreateNormalAttack"), "aura CreateNormalAttack")
    cna[1] = AURA_BINDS[2]
    cna[6] = _slv(mult)
    cna[15] = ["Fine"]
    if area[24] != 0:
        raise KitError("aura hit area p24 must stay 0")
    if cna[1] != area[22]:
        raise KitError(f"aura CNA target {cna[1]} must be the hit-area p22 bind {area[22]}")
    return ([["Command", show], ["Command", area]],
            {"scale": scale, "radius": radius, "multiplier": mult,
             "ring_diameter_px": round(AURA_RING_PX_PER_SCALE * scale, 1),
             "hit_interval": AURA_HIT_INTERVAL, "max_hits": AURA_MAX_HITS,
             "lifetime": AURA_FRAMES, "binds": list(AURA_BINDS)})


def aura_mark(ctx) -> tuple[list, dict[str, Any]]:
    """把「烈焰光环」固有付给自身：整条克隆官方 ``psycho_reaper_meteor23`` 的根层 CreateCondition。

    只换两格——``ACUnique`` 的固有 id 与层数。母本的付与对象种类（下标 10 ＝ 3）、
    主体（-17 自身）、命中演出、forceApply 一格不动（``ACUnique`` 在场时客户端本来就会
    无条件覆盖 forceApply，改它没有意义）。状态时长**不在这条命令里**：``ACUnique`` 的
    第二参是层数，时长只看 ``unique_condition`` 的 c3（＝ ``AURA_FRAMES``）。
    """
    donor = ctx.template_dsl(AURA_MARK_DONOR)
    hits = [c for c in _commands(donor, "CreateCondition")
            if c[2] and isinstance(c[2][0], list) and c[2][0][0] == "ACUnique"]
    command = copy.deepcopy(_only(hits, f"{AURA_MARK_DONOR} ACUnique CreateCondition"))
    if len(command) != 13:
        raise KitError(f"CreateCondition donor has {len(command) - 1} params, expected 12")
    if command[1] != -17:
        raise KitError(f"aura mark donor subject {command[1]} != -17 (自身)")
    if command[10] != AURA_MARK_TARGET_KIND:
        raise KitError(f"aura mark donor target kind {command[10]} != {AURA_MARK_TARGET_KIND}")
    node = command[2][0]
    if node[1] != AURA_MARK_DONOR_UID:
        raise KitError(f"aura mark donor ACUnique id {node[1]} != {AURA_MARK_DONOR_UID}")
    node[1] = int(UID_AURA)
    node[2] = _slv(AURA_MARK_STACKS)
    return (["Command", command],
            {"unique": UID_AURA, "subject": command[1], "target_kind": command[10],
             "stacks": AURA_MARK_STACKS, "donor": AURA_MARK_DONOR,
             "duration_frames": AURA_FRAMES, "duration_source": "unique_condition c3"})


def build_main_tree(ctx, level: str, families) -> tuple[Any, dict[str, Any]]:
    template_program = ctx.program_path(level).replace(CODE, TEMPLATE_CODE)
    tree = copy.deepcopy(ctx.template_dsl(template_program))
    before = _declared_ids(tree)
    if sorted(before) != [0, 1, 2, 3, 4, 5]:
        raise KitError(f"template {template_program} declares ids {sorted(before)}, expected 0..5")
    if tree[10] != 0:
        raise KitError(f"template root buffTargetAs {tree[10]} != 0 (skill-damage attribution)")

    block, meta = aura_block(ctx, level)
    # 作者追加：光环出现的同一处给自身付「烈焰光环」固有（队长技那一行以它为前置）。
    mark, mark_meta = aura_mark(ctx)
    root = tree[11]
    positions = [i for i, node in enumerate(root[1])
                 if isinstance(node, list) and node[0] == "Command"
                 and node[1][0] == "CreateReferencePoint"]
    if len(positions) != 1:
        raise KitError(f"template root has {len(positions)} CreateReferencePoint commands")
    root[1][positions[0] + 1:positions[0] + 1] = block + [mark]

    ids = _declared_ids(tree)
    if len(ids) != len(set(ids)):
        raise KitError(f"merged tree binding ids not unique: {sorted(ids)}")
    if set(AURA_BINDS) - set(ids):
        raise KitError(f"aura binds lost during the merge: {sorted(ids)}")
    sword = [c for c in _commands(tree, "CreateNormalAttack") if c[6][0].get("max", 0) > 10]
    if len(sword) != 1:
        raise KitError(f"expected exactly 1 main-slash CreateNormalAttack, got {len(sword)}")
    tree = _rewrite(ctx, tree, families)
    if AURA not in _effect_paths(tree):
        raise KitError("main tree lost the cloned aura reference after rewrite_effect_refs")
    marks = [c for c in _commands(tree, "CreateCondition")
             if c[2] and isinstance(c[2][0], list) and c[2][0][0] == "ACUnique"]
    if [c[2][0][1] for c in marks] != [int(UID_AURA)]:
        raise KitError(f"main tree must carry exactly one 烈焰光环 ACUnique, got "
                       f"{[c[2][0][1] for c in marks]}")
    tree, growth = ignition_growth(tree, (1, AURA_MAX_HITS))
    return tree, {"level": level, "aura": meta, "aura_mark": mark_meta, "ignition_growth": growth,
                  "slash": dict(sword[0][6][0]),
                  "root_commands": [n[1][0] if n[0] == "Command" else n[1][0]
                                    for n in tree[11][1]]}


# ---------------------------------------------------------------- 629 追击「引擎之炎」

def build_chase_tree(ctx, families) -> tuple[Any, dict[str, Any]]:
    """官方火龙 ability_skill 原树：球身光环留母本 ``_flame``，命中点爆炸换裁段后的克拉莉丝。

    根头 ``tree[10]=0`` 保持不动：629 以 AbilitySkill 执行 ⇒ 自动按**技能伤害**结算
    （记忆卡 wf-dsl-damage-attribution-bufftargetas）。写 2 会被掰成能力伤害，那是卖点的反面。
    """
    tree = copy.deepcopy(ctx.template_dsl(CHASE_DONOR))
    if tree[10] != 0:
        raise KitError(f"chase donor root buffTargetAs {tree[10]} != 0")
    effects = _commands(tree, "ShowEffect")
    if len(effects) != 2:
        raise KitError(f"chase donor should carry 2 ShowEffect, got {len(effects)}")
    names = []
    burst_subject = None
    for show in effects:
        aura = str(show[2][1]).endswith("_player")
        show[1] = "ignite_aura" if aura else "ignite_burst"
        if aura:
            if show[5] != ["SpecifyEffectLifetimeDirectly", 100]:
                raise KitError(f"chase aura lifetime {show[5]} differs from the donor")
            show[2] = ["SpecifyEffectDirectly", FLAME]     # 母本件，直接引用官方路径
            show[5] = ["PlayOnlyFirstSequence"]            # _flame 是 once/70 帧
        else:
            if show[5] != ["SpecifyEffectLifetimeDirectly", CHASE_BURST_RP_DONOR]:
                raise KitError(f"chase burst lifetime {show[5]} differs from the donor")
            show[2] = ["SpecifyEffectDirectly", CLARISSE]
            # 反馈轮 2 复核补漏：与 722 那边同一个数（见 CHASE_BURST_RP_DONOR 旁的长注释）。
            # 写 CLARISSE_NEW_T(79) 会让寿命跑出本轮切出来的 loop 段（21-54）⇒ 回放 + pop。
            show[5] = ["SpecifyEffectLifetimeDirectly", PF_HIT_WINDOW]
            show[12] = ["Some", _slv(BURST_SCALE)]
            burst_subject = show[3]
        if show[6] not in (["AB"], ["GH"]):
            raise KitError(f"chase ShowEffect coord system {show[6]} must stay AB/GH")
        names.append(show[1])
    if sorted(names) != ["ignite_aura", "ignite_burst"]:
        raise KitError(f"chase effect names unexpected: {names}")
    if burst_subject is None:
        raise KitError("chase tree lost the ignite_burst ShowEffect")
    for hide in _commands(tree, "HideEffect"):
        hide[1] = "ignite_aura"
    cna = _only(_commands(tree, "CreateNormalAttack"), "chase CreateNormalAttack")
    cna[6] = _slv(CHASE_MULT)
    # 2026-09-27 第二批（口径 B3/B6）：每段削韧 0.25 → 0.2，5 段合计 1.0（见 CHASE_DOWN 旁注释）。
    if cna[13] != _slv(CHASE_DOWN_DONOR):
        raise KitError(f"chase donor CreateNormalAttack p13 {cna[13]} != {CHASE_DOWN_DONOR}")
    cna[13] = _slv(CHASE_DOWN)
    if CHASE_DOWN * BURST_MAX_HITS > CHASE_DOWN_CAP:
        raise KitError(f"chase detoughness per activation {CHASE_DOWN * BURST_MAX_HITS} > {CHASE_DOWN_CAP}")
    areas = _commands(tree, "CreateHitArea")
    if len(areas) != 2:
        raise KitError(f"chase donor should carry 2 CreateHitArea, got {len(areas)}")
    burst = _only([a for a in areas if a[9][1][0]["max"] == 250], "chase burst hit area")
    burst[9] = ["Circle", _slv(BURST_RADIUS)]
    if burst[14][0] != "CalculatedUsingMaxNumOfHits":
        raise KitError(f"chase burst hit accounting drift: {burst[14]}")
    burst[14] = ["CalculatedUsingMaxNumOfHits", BURST_MAX_HITS]
    # 伤害闸不随视觉窗口走：判定区寿命必须留在母本的 30（间隔 = 30/(5-0.5) ≈ 6.7 帧）。
    if burst[13] != ["SpecifyHitAreaLifetimeDirectly", CHASE_BURST_HIT_LIFETIME]:
        raise KitError(f"chase burst hit-area lifetime {burst[13]} must stay at the donor "
                       f"{CHASE_BURST_HIT_LIFETIME} (改它就是改伤害节流)")
    rp = _retime_chase_burst_point(tree, burst_subject)
    # 629 追击不创建光环 ⇒ 也不许刷新「烈焰光环」（否则 PF 命中就能无限续时长）。
    if [c for c in _commands(tree, "CreateCondition")
            if c[2] and isinstance(c[2][0], list) and c[2][0][0] == "ACUnique"]:
        raise KitError("chase tree must not apply any unique condition (光环只由技能创建)")
    tree = _rewrite(ctx, tree, families)
    tree, growth = ignition_growth(tree, (BURST_MAX_HITS,))
    return tree, {"multiplier": CHASE_MULT, "burst_scale": BURST_SCALE, "ignition_growth": growth,
                  "burst_radius": BURST_RADIUS, "burst_max_hits": BURST_MAX_HITS,
                  "burst_window": rp,
                  "down": {"per_hit": CHASE_DOWN, "hits": BURST_MAX_HITS,
                           "per_activation": CHASE_DOWN * BURST_MAX_HITS},
                  "hit_areas": [[a[9], a[13], a[14]] for a in _commands(tree, "CreateHitArea")]}


def _retime_chase_burst_point(tree, subject) -> dict[str, Any]:
    """把爆炸所挂参考点的寿命抬到 ``PF_HIT_WINDOW``，恢复官方的「参考点 == 演出寿命」。

    母本漂移（不是唯一一条、绑定号对不上、寿命不是 ``CHASE_BURST_RP_DONOR``）一律拒绝。
    参考点只是锚点：判定区自带 30 帧寿命，先到先死 ⇒ **伤害不变**，变的只是爆炸能播多久。
    """
    points = [p for p in _commands(tree, "CreateReferencePoint") if p[10] == subject]
    point = _only(points, f"chase burst reference point (bind {subject})")
    if point[9] != CHASE_BURST_RP_DONOR:
        raise KitError(f"chase burst reference point lifetime {point[9]} "
                       f"!= donor {CHASE_BURST_RP_DONOR}")
    point[9] = PF_HIT_WINDOW
    return {"bind": subject, "donor": CHASE_BURST_RP_DONOR, "frames": PF_HIT_WINDOW,
            "hit_area": CHASE_BURST_HIT_LIFETIME}


# ---------------------------------------------------------------- 722 特殊强化弹射

def build_pf_tree(ctx, level: int, families) -> tuple[Any, dict[str, Any]]:
    """官方 ``special_lv{n}`` 整树作底座（sha 锁定）+ 赛达锥形三档 + 克拉莉丝爆炸。

    反馈轮 1：不再有「追踪 boss」那一套（Repeat/FindNearSubjects/MoveBall/RemoveEvent），
    弹道完全是官方 special 底座的原生弹道。
    """
    program = SPECIAL_PROGRAMS[level]
    raw = ctx.official_read(wf_dsl.dsl_logical(program))
    if raw is None:
        raise KitError(f"official baseline lacks the special PF base {program}")
    if _sha256(raw) != SPECIAL_SHA[level]:
        raise KitError(f"special lv{level} base drift: {_sha256(raw)}")
    tree = copy.deepcopy(ctx.template_dsl(program))
    if tree[0] != "ActionDsl" or tree[1] != 1 or tree[10] != 0:
        raise KitError(f"special lv{level} head drift: {tree[:2]} bta={tree[10]}")
    suppress = _only(_commands(tree, "SetPowerFilpSuppress")[:1], "SetPowerFilpSuppress")
    if suppress[1] != PF_SUPPRESS:
        raise KitError(f"special lv{level} suppress {suppress[1]} != {PF_SUPPRESS}")
    if not _commands(tree, "NotifyPowerflipEnd"):
        raise KitError(f"special lv{level} lost NotifyPowerflipEnd (PF 会卡死)")

    root_body = tree[11][1]
    aura_at = [n for n, e in enumerate(root_body)
               if e[0] == "Command" and e[1][0] == "ShowEffect" and e[1][1] == LANCE_FX_NAME]
    if len(aura_at) != 1:
        raise KitError(f"special lv{level} {LANCE_FX_NAME} not unique ({len(aura_at)})")
    aura = root_body[aura_at[0]][1]
    if aura[6] != ["AB"] or aura[3] != -18:
        raise KitError(f"special lv{level} aura subject/coord drift: {aura[3]} {aura[6]}")
    aura[2] = ["SpecifyEffectDirectly", ZETA_LANCE]
    aura[12] = ["Some", _slv(PF_LANCE_SCALE[level])]
    # 朝弹射方向：照抄官方赛达 zeta$zeta_1 的 (-18, ["EF"])。AB 是绝对坐标 ⇒ 恒定朝上。
    aura[6] = list(PF_LANCE_COORD)

    # 命中爆炸：克拉莉丝末端 + 判定圆放大
    bursts = [c for c in _commands(tree, "ShowEffect") if c[1] == "特殊演出"]
    if not bursts:
        raise KitError(f"special lv{level} lost the 特殊演出 burst ShowEffect")
    for show in bursts:
        show[2] = ["SpecifyEffectDirectly", CLARISSE]
        # 反馈轮 2：寿命跟命中窗口一起抬到 48（官方三个底座都是「寿命 == 参考点寿命」），
        # 48 落在克拉莉丝 loop 段里 ⇒ 到点跳 end 段，25 帧消散尾巴。
        show[5] = ["SpecifyEffectLifetimeDirectly", PF_HIT_WINDOW]
        show[12] = ["Some", _slv(BURST_SCALE)]
        if show[6] != ["AB"]:
            raise KitError(f"special lv{level} burst coord {show[6]} must stay AB")

    # 反馈轮 2：命中后的窗口（suppress / Wait / 参考点）一起抬到 PF_HIT_WINDOW。
    # 官方 psycho_reaper_meteor23 就是把这一组从 20/30 抬到 40 来放长自己的命中演出。
    hit_window = _retime_hit_window(tree, level)
    # 反馈轮 2：锥形收尾（官方赛达 zeta$zeta_1 的 `終わりの演出` 同写法）。
    lance_end = _add_lance_end(tree, level)
    radii = []
    for area in _commands(tree, "CreateHitArea"):
        if area[24] != 0:
            raise KitError("PF CreateHitArea p24 must stay 0 (4 = 按直击算，整块 PF 乘区被跳过)")
        if area[9][0] != "Circle":
            raise KitError(f"unexpected PF hit-area shape {area[9][0]}")
        radii.append(area[9][1][0]["max"])
        area[9] = ["Circle", _slv(BURST_RADIUS)]

    scaled = []
    for cna in _commands(tree, "CreateNormalAttack"):
        mult = cna[6]
        if len(mult) != 1 or mult[0]["min"] != mult[0]["max"]:
            raise KitError(f"special lv{level} CNA multiplier shape drift: {mult}")
        value = round(mult[0]["min"] * PF_SCALE, 6)
        cna[6] = _slv(value)
        scaled.append(value)
    if not scaled:
        raise KitError(f"special lv{level} carries no CreateNormalAttack")

    # 反馈轮 1：作者要求去掉「强化弹射追踪 boss」⇒ 底座的弹道原样保留，
    # 不再往 root 挂 Repeat/FindNearSubjects/MoveBall，碰撞块里也没有 RemoveEvent 要清。
    # 这里只留底座形状断言：收尾仍然靠 CollisionOfBallAndEnemy + NotifyPowerflipEnd。
    # 底座自己就带一条 RemoveEvent("ヒット判定")，所以判据是「与底座逐条同名同数」，
    # 不是「一条 RemoveEvent 都不许有」。
    collisions = [n for n in root_body
                  if n[0] == "Event" and n[1][0] == "CollisionOfBallAndEnemy"]
    _only(collisions, "root CollisionOfBallAndEnemy")
    base = ctx.template_dsl(program)
    for name in ("MoveBall", "FindNearSubjects", "RemoveEvent", "Repeat"):
        here = len(_commands(tree, name))
        there = len(_commands(base, name))
        if here != there:
            raise KitError(f"PF lv{level} {name} count {here} != official base {there} "
                           "(反馈轮 1 已去掉追踪，弹道必须与底座一致)")
    if any(n[0] == "Event" and n[1][0] == "Repeat" for n in root_body):
        raise KitError(f"PF lv{level} still carries a Repeat steering event")

    ids = _declared_ids(tree)
    if len(ids) != len(set(ids)):
        raise KitError(f"PF lv{level} binding ids not unique: {sorted(ids)}")
    tree = _rewrite(ctx, tree, families)
    from wf_magnus_pf_orbit import attach
    tree = attach(tree)
    return tree, {"level": level, "multipliers": scaled, "total": round(sum(scaled), 6),
                  "lance_scale": PF_LANCE_SCALE[level],
                  "lance_coord": list(PF_LANCE_COORD), "extra_effects": [],
                  "donor_radii": radii, "burst_radius": BURST_RADIUS, "chase": None,
                  "hit_window": hit_window, "lance_end": lance_end}


def _retime_hit_window(tree, level: int) -> dict[str, Any]:
    """把命中后的 suppress / Wait / 参考点三个值一起抬到 ``PF_HIT_WINDOW``。

    底座三处原值必须逐一对上 ``PF_HIT_WINDOW_DONOR[level]``（Wait 比 suppress 少 2），
    漂移就拒绝——这组值一动就会影响 PF 何时归还弹板，不能默默跟着母本走。
    """
    want = PF_HIT_WINDOW_DONOR[level]
    body = _collision_body(tree)
    suppress = [n[1] for n in body if n[0] == "Command" and n[1][0] == "SetPowerFilpSuppress"]
    waits = [n[1] for n in body if n[0] == "Event" and n[1][0] == "Wait"]
    points = [n[1] for n in body if n[0] == "Command" and n[1][0] == "CreateReferencePoint"]
    before = {"suppress": _only(suppress, "post-hit SetPowerFilpSuppress")[1],
              "wait": _only(waits, "post-hit Wait")[1],
              "point": _only(points, "post-hit CreateReferencePoint")[9]}
    if before != {"suppress": want, "wait": want - 2, "point": want}:
        raise KitError(f"special lv{level} post-hit window drift: {before} (want {want})")
    suppress[0][1] = PF_HIT_WINDOW
    waits[0][1] = PF_HIT_WINDOW - 2
    points[0][9] = PF_HIT_WINDOW
    return {"donor": want, "frames": PF_HIT_WINDOW, "wait": PF_HIT_WINDOW - 2}


def _collision_body(tree) -> list:
    root_body = tree[11][1]
    collision = _only([n for n in root_body
                       if n[0] == "Event" and n[1][0] == "CollisionOfBallAndEnemy"],
                      "root CollisionOfBallAndEnemy")
    return collision[1][5][1]


def _add_lance_end(tree, level: int) -> dict[str, Any]:
    """在 ``HideEffect("オーラ演出")`` 后面补一条锥形收尾演出（官方赛达同写法）。

    底座命中那一帧就把锥形硬删（``HideEffect``），而 ``zeta_lance`` 的 timeline 只有
    ``start``/``start_loop`` 两段、没有 ``end`` 段 ⇒ 客户端无段可跳＝立删，这就是作者说的
    「强化弹射的动画效果也会突然消失」。官方 ``zeta$zeta_1`` 的解法是另起一条
    ``ShowEffect("終わりの演出", zeta_lance_end, PlayOnlyFirstSequence, tracking false/false)``；
    tracking 两关＝创建帧快照，所以球没了、PF 结束了，这 32 帧照样播完。
    """
    body = _collision_body(tree)
    hide_at = [n for n, e in enumerate(body)
               if e[0] == "Command" and e[1][0] == "HideEffect" and e[1][1] == LANCE_FX_NAME]
    if len(hide_at) != 1:
        raise KitError(f"PF lv{level} HideEffect({LANCE_FX_NAME}) not unique ({len(hide_at)})")
    command = ["ShowEffect", LANCE_END_FX_NAME,
               ["SpecifyEffectDirectly", ZETA_LANCE_END], -18,
               ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"], list(PF_LANCE_COORD),
               0, 0, 0, False, False, ["Some", _slv(PF_LANCE_SCALE[level])]]
    body.insert(hide_at[0] + 1, ["Command", command])
    return {"effect": ZETA_LANCE_END, "name": LANCE_END_FX_NAME, "after": LANCE_FX_NAME,
            "subject": -18, "coord": list(PF_LANCE_COORD), "tracking": [False, False],
            "lifetime": "PlayOnlyFirstSequence", "frames": LANCE_END_FRAMES,
            "scale": PF_LANCE_SCALE[level]}


# ---------------------------------------------------------------- DSL 闸门与落盘

def _effect_paths(tree) -> set[str]:
    return {v for v in (x for x in _walk_strings(tree)) if v.startswith("battle/effect/")}


def _walk_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for child in node:
            yield from _walk_strings(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _walk_strings(child)


def _dsl_problems(tree) -> None:
    problems = wf_dsl.player_side_dsl_problems(tree)
    if problems:
        raise KitError(f"player-side DSL problems: {problems}")


def _effect_ref_problems(ctx, tree) -> list[str]:
    """DSL 引用的特效必须真的存在：官方归档里有（直接引用），或包里有（本轮克隆）。"""
    missing = []
    for value in sorted(_effect_paths(tree)):
        if any(ctx.official_read(f"{value}.{kind}.amf3.deflate") is not None
               for kind in ("parts", "timeline")):
            continue
        if any(ctx.pack.pkg_path("common", f"{value}.{kind}.amf3.deflate").is_file()
               for kind in ("parts", "timeline")):
            continue
        missing.append(value)
    return missing


def burst_users(tree, stack=(), out=None) -> list[dict[str, Any]]:
    """列出树里所有引用克拉莉丝爆炸的 ShowEffect，连同**包住它的参考点**（绑定号，寿命）。

    反馈轮 2 的复核事故就出在「只改了看得见的三棵 PF 树，漏了第四个使用者」。
    切 `end` 段是**全局**动作（改的是特效素材本身），所以判据也必须是全局的：
    凡是用这份素材的 ShowEffect，寿命都得落在同一个 loop 段里。
    """
    if out is None:
        out = []
    if isinstance(tree, list):
        if len(tree) >= 2 and tree[0] == "Command" and isinstance(tree[1], list) and tree[1]:
            body = tree[1]
            if body[0] == "CreateReferencePoint":
                stack = stack + ((body[10], body[9]),)
            elif body[0] == "ShowEffect":
                src = body[2]
                if isinstance(src, list) and len(src) > 1 and src[1] == CLARISSE:
                    out.append({"name": body[1], "subject": body[3], "lifetime": body[5],
                                "points": [list(p) for p in stack]})
        for child in tree:
            burst_users(child, stack, out)
    return out


def burst_window_problems(program: str, tree) -> None:
    """爆炸素材只有一份 ⇒ 每个使用者的寿命必须都是 ``PF_HIT_WINDOW``，锚点寿命必须跟上。"""
    want = ["SpecifyEffectLifetimeDirectly", PF_HIT_WINDOW]
    for use in burst_users(tree):
        if use["lifetime"] != want:
            raise KitError(
                f"{program}: ShowEffect `{use['name']}` 的克拉莉丝寿命 {use['lifetime']} "
                f"!= {want}；`end` 段是按 PF_HIT_WINDOW 切的，别的值会跑出 loop 段"
                "（多播一遍 loop 或提前被截）")
        subject = use["subject"]
        if not isinstance(subject, int) or subject <= 0:
            continue                       # 内置主体（-18 球等）没有可查的锚点寿命
        anchors = [lt for bind, lt in use["points"] if bind == subject]
        if len(anchors) != 1:
            raise KitError(f"{program}: `{use['name']}` 主体 {subject} 找不到唯一的外层参考点 "
                           f"（找到 {use['points']}）")
        if anchors[0] != PF_HIT_WINDOW:
            raise KitError(
                f"{program}: `{use['name']}` 挂的参考点寿命 {anchors[0]} != {PF_HIT_WINDOW}；"
                "官方母本这一组恒等，失配 ⇒ 爆炸会被锚点连坐提前终止")


def _write_tree(ctx, program: str, tree) -> str:
    _dsl_problems(tree)
    burst_window_problems(program, tree)
    refs = _effect_ref_problems(ctx, tree)
    if refs:
        raise KitError(f"{program} references effects absent from baseline and package: {refs}")
    logical = ctx.write_dsl(program, tree)
    if ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes()) != tree:
        raise KitError(f"{program} readback differs from the written tree")
    return logical


def build_skill_trees(ctx, families) -> list[tuple[str, str, str, Any, dict[str, Any]]]:
    """:func:`write_skills` 落盘的全部 DSL，按落盘顺序：``(类别, 档, 程序路径, 树, meta)``。

    类别：``skill``（技能两档）/ ``ignite``（629 引擎之炎）/ ``pf_skill``（特殊强化弹射三档的 629 伤害树）/
    ``pf``（722 覆盖树）。2026-09-27 第三轮：技能两档与引擎之炎过 :func:`leader_gate`（旗号 2 分支），
    三档伤害树走 :func:`pf_ignition_growth`（撤回 10 层封顶）；修订模块测试断言本函数输出 == revise() 输出。
    """
    out: list[tuple[str, str, str, Any, dict[str, Any]]] = []
    for level in ("1", "2"):
        tree, meta = build_main_tree(ctx, level, families)
        tree, meta["leader_gate"] = leader_gate(tree)
        out.append(("skill", level, ctx.program_path(level), tree, meta))

    tree, meta = build_chase_tree(ctx, families)
    tree, meta["leader_gate"] = leader_gate(tree)
    out.append(("ignite", "ignite", CHASE_PROGRAM, tree, meta))

    for level in (1, 2, 3):
        tree, meta = build_pf_tree(ctx, level, families)
        tree, damage_tree, damage_meta = PF_SKILL.split_tree(tree)
        damage_tree, damage_meta["ignition_growth"] = pf_ignition_growth(
            damage_tree, tuple(damage_meta["hits"]))
        out.append(("pf_skill", str(level), PF_SKILL_PROGRAMS[level - 1], damage_tree, damage_meta))
        out.append(("pf", str(level), PF_PROGRAMS[level - 1], tree, meta))
    return out


def write_skills(ctx, families) -> dict[str, Any]:
    info: dict[str, Any] = {}
    pf: dict[str, Any] = {}
    programs = []
    damage: dict[str, dict[str, Any]] = {}
    for kind, level, program, tree, meta in build_skill_trees(ctx, families):
        logical = _write_tree(ctx, program, tree)
        programs.append(program)
        if kind == "pf_skill":
            meta["logical"] = logical
            damage[level] = meta
            continue
        if kind == "pf":
            meta.update(damage.pop(level))
        meta["logical"] = logical
        meta["sha256"] = _sha256(ctx.pack.pkg_path("common", logical).read_bytes())
        if kind == "pf":
            pf[level] = meta
        else:
            info[level] = meta
    if damage:
        raise KitError(f"PF damage trees without their override tree: {sorted(damage)}")
    ctx.write_flat(PFA, {PF_KEY: [list(PF_PROGRAMS)]})
    return {"skills": info, "power_flip": pf, "programs": programs}


# ---------------------------------------------------------------- 入口

SUMMARY = ("玛格诺斯 rework1：火 · 特殊强化弹射主C"
           "（722 三档锥形 PF → 629「引擎之炎」→ 引擎点火按层堆技能伤害）")

NOTES = [
    "722 带火共鸣门（官方 141201#1 先例）：非共鸣队伍或他不当队长时是原生剑士 PF，面板已写明",
    "422 冲刺两行在词条槽 5（前置 42 队长），队长表写 422 = 角色页 C7050；文案挪到队长技 desc_override",
    "Swift 抵消 +245% 只对非飞行形态精确（飞行基数 60 而非 90）⇒ 面板不写「完全无法获得」",
    "629 触发改成 180（PF 命中敌人）并带 CT 0.6 秒：空挥不触发，多敌时靠 CT 限流；629 排在 525 之前",
    "「引擎点火」固有 99999999 帧 / 99 层：能力 3 每次火属性技能 +1 层、每 3 次 PF +3 层，队长技每 3 次 PF 再 +7 层",
    "引擎点火的「≥5 层」用 during 134 + limit 1 的平坦门槛（前置 188 数实例恒为 1，写 ≥5 永不成立）",
    "三族特效克隆到 skill_unique/lion_swordman_moon/{lance,burst,aura}/，预算 0.44% → 约 2.19%",
    "克拉莉丝只播末端 79 帧（parts 根层 r=(1<<30)|78），手术在 clone 之后施加并带母本漂移断言",
    "像素交付件（sprite_sheet / special_sprite_sheet）若是标准 PNG，装包时由 kitlib 换成 WF 存储态魔数",
    "反馈轮 1：去掉 PF 追踪 boss（Repeat/FindNearSubjects/MoveBall 整块删，弹道回官方 special 原生）",
    "反馈轮 1：赛达只留锥形 zeta_lance（黄色六边形来自 zeta_lance_hit/_end，整族不再克隆），"
    "三档改 scale 1.0/1.4/1.8；坐标系 AB→EF ⇒ 枪体朝球的飞行方向（官方 zeta$zeta_1 同写法）",
    "反馈轮 1：光圈环画出来是 132.71×scale px，scale 3.75 时半径 248.8 却只有 Circle 200 判定 ⇒ "
    "外圈 48.8px 碰到敌人不掉血；scale 改由判定半径反算（3.01/4.07），并把命中间隔从推导的 63 帧改显式 30 帧",
    "反馈轮 2 根因：客户端终止特效时跳名为 `end` 的序列（官方 psycho_reaper 722 的 "
    "se_power_flip_special_lv3_clear 写在第 102 帧、演出寿命只有 40 ⇒ 只能是跳段才播得到），"
    "没有 end 段就是立删。79 帧的克拉莉丝塞进 20/30 帧的参考点 + 没有 end 段 = 满强度那帧凭空消失",
    "反馈轮 2：命中窗口 suppress/Wait+2/参考点/演出寿命 四个数官方恒等，一起抬到 48（官方 "
    "psycho_reaper 是 40）；判定区寿命与每目标上限一格没动 ⇒ 伤害不变，只放长演出",
    "反馈轮 2：克拉莉丝切 neutral(pass)/loop/end 三段，寿命 48 落在 loop 里 ⇒ 终止时跳 end 段 25 帧消散",
    "反馈轮 2：锥形收尾照官方赛达 zeta$zeta_1 的 `終わりの演出` 补一条（tracking false/false ＝ "
    "创建帧快照，球没了也播得完）；黄/橙六边形按 atlas rect 擦成全透明，parts 零结构手术",
    "反馈轮 2：收尾族放 lance_end/ 而不是回 lance/ —— 1.4.965 在旧路径发过，live 里是孤儿，"
    "再写同路径会撞 occupied_without_hash_bound_prior_path_ownership 且 rebase 清不掉（实测）",
    "反馈轮 2：爆炸音 se_clarisse（304 帧、峰值第 89 帧＝克拉莉丝整段技能的蓄力音）换成 "
    "se_fire_large_explosion（143 帧、峰值第 23 帧），实测数据见 impl/magnus.md §9.5",
    "作者追加：新增固有「烈焰光环」11999002（600 帧＝AURA_FRAMES 同源、上限 1 层），"
    "技能树在创建光环的同一处 CreateCondition(-17, ACUnique) 付给自身；629 追击树不付、不刷新",
    "作者追加：队长技第 7 行落在**队长表**（前置 188 固有实例≥1 + 触发 6 BallFlip≥1 + 内容 226 "
    "连击 35）——187 在官方队长表 0 先例，188 有 6 行（111183#4/#5、111165#3/#4、131152#2/#3）",
    "作者追加：这一行**不带火共鸣门**（作者原话没写属性共鸣）；「弹射」＝ BallFlip（弹板弹球），"
    "不是强化弹射，阈值 1 次 / 无次数上限 / 无冷却",
    "2026-09-27 第二批（口径 A，修订模块 wf_balance_20260927b_magnus）：每 3PF 队长全队技伤/攻 "
    "100%/50% → 20%/10%（×1/5）；能力 1#2 自身技伤限 4 次，无上限部分搬队长 #9（5%）；能力 2 两行每层 "
    "50% → 15% 最多 10 层，无上限部分搬队长 #10/#11（每层 5%，×1/10）；能力 3#4 每层全队独立乘区 5% → 1% "
    "最多 10 层，无上限部分搬队长 #12（每层 0.5%）；技能 DSL 点火绑定上限 99 → 10（每层 +5 倍封顶 10 层）",
    "2026-09-27 第二批（口径 B3/B6，复核补漏）：「引擎之炎」629 追击触发 CT 0.6 秒 ≤3 秒 ⇒ 每次削韧 ≤1；"
    "爆炸 5 段 × p13 0.25 = 1.25 → p13 0.2（5 × 0.2 = 1.0，回到官方火龙母本 4 × 0.25 的每次总量），"
    "段数/倍率/Fever 点不动；疾风同路 PF（629 代打 15/20/25 顶格）按口径 B5 保留",
    "2026-09-27 第三轮（修订模块 wf_balance_20260927c_magnus，作者「砍到 4/5 或 7/10」「可以砍到 2/3」「取 5 的倍数」）："
    "队长 #1/#2 每 3PF 火队技伤/攻 20%/10% → 80%/40%（原值 ×4/5）；#9 每 3PF 自身技伤 5% → 20%（口径 D1）；"
    "#10/#11 点火每层自身技伤/攻 5% → 35%（原值 ×2/3 取 5 的倍数）；#12 点火每层火队独立乘区 0.5% → 4%（×4/5）；"
    "能力栏封顶版按口径 D4 不动",
    "2026-09-27 第三轮（口径 U2/U6/U7）：特殊强化弹射三档伤害树点火上限 10 → 99（只由队长 #6–#8 火共鸣调起）；"
    "技能两档与引擎之炎根块包进 ConditionalsChangeSkillFlag(2)：开支上限 99、关支保留第二批 10 层；"
    "旗号 2 由能力 1 末行 704（前置 42 队长 + 火编成≥6，瞬发无触发，先例 live 罗尔夫中秋 1499866#4）打开",
    "2026-09-27 第三轮（口径 U9）：旗号 1（536）实际只给主斩劈倍率加 alv 1.75～3.5，"
    "技能强化条目与能力 1 面板第 2 行由「光环的范围扩大」改为「斩劈的技能倍率提升」",
    "2026-09-27 第三轮（技能强化文案规范后补）：特殊强化弹射三档随引擎点火成长（上限 99、不经旗号）是队长强化弹射"
    "本体的效果，写在队长面板第 1 行末尾「，威力随引擎点火层数提升」（不写数字）",
]

DEVIATIONS = [
    {"want": "队长技面板第 2/3 行「冲刺强化 + CD−30%」「冲刺间隔缩短不再叠加」写在队长表",
     "got": "422 行落在词条槽 5（前置 42 Leader），文案由 desc_override 挪到队长技面板",
     "why": "422 写进队长表 = 角色详情页 C7050（LeaderAbilityValues.parseAt107 没打补丁）；"
            "同澄波响 _deviations 的裁决。"},
    {"want": "「无法获得冲刺间隔缩短效果」",
     "got": "「冲刺间隔缩短效果不会让自身的冲刺冷却时间进一步缩短」+ 422 param0 数值抵消 +245%",
     "why": "引擎没有「拒绝某一个具体增益」的 kind（ACBuffRejection 是拒绝全部）；"
            "Swift 把 CD 基数 90 换成 20，补回 3.5×(1+s0) 即等价。"},
    {"want": "「技能倍率随强化弹射次数提升」",
     "got": "按作者确认的替代方案：引擎点火每层使每次完整技能基础总倍率＋5倍；原有PF次数技伤加成保留",
     "why": "没有直接读取全局PF次数的变量命令；原生BindConditionAccumulationVariable与vlv支持层数倍率。"
            "入口快照层数，斩击与光环合计＋5倍，追击及三档PF技能各自整招＋5倍，按原伤害占比分摊。"},
    {"want": "「引擎点火在5层以上时，自身技能伤害额外乘区＋25%」",
     "got": "during 134 阈值 5 层 + limit 1 的平坦门槛 → 自身独立乘区技能伤害 +25%",
     "why": "前置 188 / during 194 数的是实例个数（461 叠层恒为 1），「≥5 层」永不成立。"},
    {"want": "面板里的「塞达式技能特效」「克拉莉丝式圆形爆炸（范围较原版增大）」",
     "got": "改写成玩家可读的描述（「火焰突进随发动次数分三档逐渐增强」「造成技能伤害」），机制不变",
     "why": "面板是给玩家看的，不能出现其它官方角色的内部代号；已回写 panel/magnus.json 并标 dev:true。"},
    {"want": "面板 skill 第 4 行（特殊强化弹射说明）单独成行",
     "got": "落成 action_skill 描述的第 4 段；722 行自带 override_string_…_pf 说明串",
     "why": "队长技面板被 desc_override 整段接管后，722 行自己的说明串不会显示。"},
    {"want": "能力 1 第 1 行、能力 6 第 1 行保留 donor 的「火·MySelf」前置",
     "got": "去掉该前置（c6=0）",
     "why": "对火属性的玛格诺斯恒真，属裁决 §3 禁止的恒真条件文案；行为完全一致。"},
    {"want": "设计稿先行、kit 与设计稿双向对账",
     "got": "design/magnus.json 的 plan_rework1 由 kit 常量生成，对账退化为漂移探测",
     "why": "额度约束下不重复手写同一份 23 行；仍能抓住事后单边改动，抓不到首次录入的共同错误。"},
    {"want": "魏虎光圈块自带的 ACToleranceOfElement（火耐性↓）与 _shot 命中特效",
     "got": "丢掉耐性行；命中特效换引擎内置 Fine",
     "why": "目标面板没有耐性这一条；命中特效用内置件后特效族只需克隆 _aura 一个基名。"},
    {"want": "像素件（小人 sprite_sheet 等）随 kit 一起装包",
     "got": "B/pixel/magnus/install.json 不存在时自动跳过，包内保持母本像素件",
     "why": "像素/立绘/语音不归本代理；像素代理交付后重跑 kit 即可装入。"},
    {"want": "面板 / 技能描述里的「并可追击敌方boss目标」",
     "got": "整句删除（PF_STRING 与 action_skill 描述第 4 段同步）",
     "why": "反馈轮 1 作者要求去掉强化弹射的追踪，行为没了文案就不能留。"},
    {"want": "赛达三档靠叠加 zeta_lance_hit / zeta_lance_end 表达「逐渐增强」",
     "got": "三档都只用锥形 zeta_lance，靠 scale 1.0/1.4/1.8 递增；两个 hit/end 族不再克隆",
     "why": "作者原话「只要锥形的效果黄色的小方框不要」——实测那两族的主体就是实心黄色六边形。"},
    {"want": "命中后的爆炸按官方底座的 20/30 帧窗口播",
     "got": "suppress / Wait+2 / 参考点 / 演出寿命 四个数一起抬到 48 帧（0.8 秒）",
     "why": "反馈轮 2 作者原话「爆炸会有突然消失」＝79 帧的演出被 20/30 帧的参考点连坐删在满强度那一帧；"
            "官方 psycho_reaper_meteor23 的 722 就是把这一组从 20/30 抬到 40 来放长自己的命中演出。"
            "判定区寿命与每目标上限一格没动，伤害完全不变，代价只是弹板晚 0.3–0.5 秒归还。"},
    {"want": "收尾族放回 `lance/`（和锥形同一目录、共用一张图集）",
     "got": "放在自己的 `lance_end/` 子目录，同一张 zeta sheet 复制第二份（layer0 2.19%→2.74%）",
     "why": "1.4.965 在 `lance/zeta_lance_end.*` 发过一次，反馈轮 1 删掉后 live 里成了孤儿路径；"
            "再写同一路径＝preflight `occupied_without_hash_bound_prior_path_ownership`，"
            "`can_prepare` 直接 false，而 flow rebase 只归位表行、清不掉资产路径冲突（实测）。"},
    {"want": "爆炸继续用克拉莉丝自带的 `se_clarisse`",
     "got": "换成官方 `sound_effect/fire/se_fire_large_explosion`",
     "why": "`se_clarisse` 是她整段 157 帧技能的蓄力音：实测 304 帧、峰值在第 89 帧，"
            "按在「爆炸已经发生」的第 0 帧上，轰鸣比画面晚 1.5 秒、长 10 倍——这就是作者说的"
            "「音效和动画不匹配」。替代件峰值第 23 帧、衰到 10% 在第 89 帧，与 73 帧的画面对齐。"},
    {"want": "光圈「稍微小一点」＝ ShowEffect scale 与判定半径一起按 15–20% 缩",
     "got": "只缩画面（scale 3.75→3.01、5.00→4.07，−19.7%/−18.6%），判定半径 200/270 不动",
     "why": "环和判定本来差 24%（环 248.8 vs 判定 200）——那圈差值就是「碰到了没伤害」的来源；"
            "缩画面到刚好压在判定圆上，既是作者要的更小，也让看得见的部分全部生效，强度不变。"},
    {"want": "「自身持有光环时」用前置 187 ConditionUnique（语义上最直白的「持有某固有状态」）",
     "got": "队长表这一行改用前置 188 ConditionCountUnique，阈值 ≥1（＝固有实例数 1）",
     "why": "官方 leader_ability 1107 行里 187 出现 0 次（用到的前置只有 2/8/38/186/188/205），"
            "队长表零先例 kind ＝ 角色详情页 C7050；188 在队长表有 6 行先例，其中 111183#4/#5 "
            "就是火龙的「持有勇敢之焰时」。上限 1 层的固有，188≥1 与 187 完全等价。"},
    {"want": "光环只是「特效＋判定区」，词条直接判定它",
     "got": "技能创建光环时同步给自身付一个新固有「烈焰光环」（600 帧 ＝ 光环寿命），词条判定这个固有",
     "why": "引擎没有「判定某个判定区还在不在」的前置；状态是唯一可供词条读取的载体。"
            "时长与画面同源（同一个 AURA_FRAMES），所以面板说的「持有期间」和玩家看到的环完全同步。"},
]


def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.cid, spec.code) != (CID, CODE):
        raise KitError(f"kit bound to {CID}/{CODE}, got {spec.cid}/{spec.code}")
    if (spec.template_id, spec.template_code) != (TEMPLATE_ID, TEMPLATE_CODE):
        raise KitError(f"template must stay {TEMPLATE_ID}/{TEMPLATE_CODE}, "
                       f"got {spec.template_id}/{spec.template_code}")
    if spec.element != 0:
        raise KitError(f"magnus stays fire (element 0), got {spec.element}")

    design = _design(ctx)
    design_problems = _design_problems(design) if design else ["design/magnus.json absent"]
    if design and design_problems:
        raise KitError(f"kit drifted from the design document: {design_problems}")

    voice_cols = write_voice_route(ctx)
    uniques = build_unique(ctx)
    icon = install_unique_icon(ctx)

    rows = build_rows(ctx)
    ctx.write_flat(KL.LEADER, {CID_S: rows["leader"]})
    ctx.write_flat(KL.ABILITY, rows["ability"])
    strings = write_strings(ctx)

    action = write_action_skill(ctx)
    fx_report, families = clone_effects(ctx)
    skills = write_skills(ctx, families)
    voice_ready = KL.write_voice_ready(ctx)
    pixel = KL.install_staged_assets(ctx)
    mirrors = ctx.sync_character_mirrors()

    panel = [ev["describe"] for ev in rows["evidence"]] + list(strings.values())
    ctx.evidence_write("kit-rows.json", {
        "leader": rows["leader"], "ability": rows["ability"],
        "unique_condition": {key: list(row) for key, row in uniques.items()},
        "custom_ability_string": strings, "action_skill": action,
        "power_flip_action": {PF_KEY: list(PF_PROGRAMS)},
        "voice_route": voice_cols, "evidence": rows["evidence"], "effects": fx_report,
    })
    return KL.report(
        ctx,
        summary=SUMMARY,
        status=KL.READY,
        panel=panel,
        notes=NOTES + [{"icon": icon, "pixel": pixel, "voice_ready": voice_ready,
                        "mirrors": mirrors, "design_checked": bool(design),
                        "effects": fx_report}],
        programs=skills["programs"],
        unique_condition={key: {"name": row[1], "icon": row[2],
                                "duration_frames": int(row[3]), "cap": int(row[4])}
                          for key, row in uniques.items()},
        required_capabilities=sorted(set(rows["capabilities"])
                                     | set(SPEC["required_capabilities"])),
        deviations=DEVIATIONS,
        extra={"skills_detail": {"trees": skills["skills"],
                                 "power_flip": skills["power_flip"],
                                 "energy": {lv: list(ENERGY[lv]) for lv in ("1", "2")}},
               "effects": fx_report,
               "voice_route": voice_cols},
    )

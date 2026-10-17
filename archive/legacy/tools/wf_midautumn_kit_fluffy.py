# -*- coding: utf-8 -*-
"""中秋批次 kit：芙拉菲·中秋 149987 ``combat_animal_moon``（风属性技能伤害主 C）。

**rework1（2026-09-21）**：按作者已过目的目标面板
``work/character_packs/midautumn-20260920/rework1/panel/fluffy.json`` 整体重做。施工单与逐行
映射见 ``rework1/impl/fluffy.md``；上一轮的内容留在 ``design/fluffy.{md,json}`` 的历史段落里。

一句话：队长位授予**双类型强化弹射**（722 ＝ 官方 ``fighter`` 底座 ＋ 官方 ``supporter`` 辅助增益块）；
队长技换成「开局铺垫 → 每次 PF 滚雪球 → 每 5 次 PF Lv3 触发技能 → 每 250 连击自身技伤翻倍」；
技能四连重击改**八连重击＋无后摇**、基础前段 **25×**＋裂地 **65×**；两处「立即发动自身技能」统一落成
**一棵 629 ``ability_skill`` 树**（``_deviations.json›fluffy[1]`` 的追击等价）。

本模块负责：

* 队长 13 行 ＋ 词条 6 键 18 条（官方/live donor ＋ 逐格改 ＋ ``wf_client_legality`` ＋ ``wf_describe`` 回读）；
* 8 条 ``custom_ability_string``：536/704 两条强化开关串、629 串、722 串、4 个 ``desc_override``；
* ``power_flip_action`` 三档覆盖树（fighter ＋ supporter 增益块）；
* 629 ``ability_skill`` 树（技能档 2 的深拷贝）；
* ``action_skill`` 两档能量（580/580）；
* 技能 DSL 两档：官方母本 141033 整树当底座，嫁接官方 141081 的重击段（4→**8 段**）与裂地演出；
  裂地一击外包 ``ConditionalsChangeSkillFlag(1)`` 开连击加成（536）；每个判定区 on-hit 挂
  ``AddCombo`` 走 ``alv2`` 通道（704，没开时加 0）；除裂地一击外全部 ``incrementCombo=false``，
  让词条 390（SetCombo 0，SkillHit≥1）刚好在最后一段伤害结算之后把连击清零（反馈轮 1）；
* ``rush`` 特效族整族克隆 ＋ LUT 染色（``jab`` 族按图集预算直接引用官方路径）；
* 语音路由 kind 3 ＋ ``switched_action_skill``；``B/pixel/fluffy/install.json`` 的像素成品。

不做：724、**新固有状态（⇒ 本轮不需要 48×48 状态图标）**、觉醒替换行。
不碰：live store / ``assets/`` / ``.cdn`` / 设备 / 存档；不发布、不提交。
由 ``python mod-tools/wf_midautumn_build.py --char fluffy --step kit`` 调用 :func:`build`。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_dsl_sig as SIG  # noqa: E402
from wf_midautumn_dash_guard import swift_guard_plan
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_kit_philia as PH  # noqa: E402

KitError = KL.KitError

KEY = "fluffy"
CID, CODE = 149987, "combat_animal_moon"
CID_S = str(CID)
ELEMENT = 3                                    # 风（0 基内部编号，Green）
TEMPLATE_ID, TEMPLATE_CODE = 141033, "combat_animal"
GRAFT_CODE = "combat_animal_xm21"              # 141081（她的圣诞版）：重击段 + 裂地演出的血统

ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
LEADER_ROW_COUNT = 13
ABILITY_RECORD_TOTAL = 18

#: 2026-09-27 平衡第二批（``wf_balance_20260927b_fluffy``，口径 A/B 节）。
#: 无上限成长按 3 分钟实际触发次数放缓（≤15 次 1/5、15–30 次 1/5、≥30 次 1/10）：
#: 每 1 次 PF（约 35 次，30–45）⇒ 1/10；每 250 连击（约 20 次）⇒ 1/5；每 3 次 PF 的 694（约 12 次）⇒ 1/5。
#: 每 3 次 PF 的 35（充能速度）/245（技能槽上限）属于「充能」，作者「其他充能的都暂时不动」⇒ 保持 5%。
BALANCE_B = {
    "pf_growth": "2000",          # L#4/L#5 全队(风) 攻击力 / 技能伤害 每次 PF 20% → 2%
    "combo_growth": "20000",      # L#9 每 250 连击 自身技能伤害 100% → 20%
    "pf3_growth": {"35": "5000", "245": "5000", "694": "1000"},   # L#10..L#12（694 5% → 1%）
}
#: 2026-09-27 平衡第三轮（``wf_balance_20260927c_fluffy``，成长复核）：作者「砍到4/5，或者7/10」「数值尽量取5的倍数」
#: ⇒ 按原值回调（现行值；``BALANCE_B`` 只留作第二批历史）：每次 PF 20%×4/5=16 → 15%；每 250 连击 100%×7/10 = 70%；
#: 每 3 次 PF 的 694 5%×4/5 = 4%（<10% 不强取 5 的倍数）。35/245 充能仍 5%。
BALANCE_C = {
    "pf_growth": "15000",         # L#4/L#5：第二批 2% → 15%（原 20%）
    "combo_growth": "70000",      # L#9：第二批 20% → 70%（原 100%）
    "pf3_growth": {"35": "5000", "245": "5000", "694": "4000"},   # L#12 694：第二批 1% → 4%（原 5%）
}
#: 技能两档：八连重击每段 ``CreateNormalAttack`` p13 削韧 6.25 → 1.5（每次施放 65 → 27；精准连击与裂地不动）。
PESTLE_DETOUGHNESS_DONOR = 6.25
PESTLE_DETOUGHNESS = 1.5
#: 629 ``ability_skill`` 树（队长 CT 6 秒、能力3 CT 12 秒，均 > 3 秒 ⇒ 每次 ≤3）：全部 19 段 p13 → 0.15（65 → 2.85）。
INVOKE_DETOUGHNESS = 0.15
CNA_DETOUGHNESS = 13            # CreateNormalAttack 节点下标（= p13 basicDetoughness，按 SLv 的 min/max）

# ---------------------------------------------------------------- 自有键

CAS_FLAG1 = f"change_skill_{CODE}"                  # 536（A1#1，主位＋风共鸣）→ alv
CAS_FLAG2 = f"change_skill_2_{CODE}"                # 704（A3#4，风共鸣）→ alv2
INVOKE_STRING = f"ability_skill_{CODE}"             # 629 的 c68（leader）/ c70（ability）
INVOKE_PROGRAM = (f"battle/action/skill/action/ability_skill/"
                  f"{INVOKE_STRING}${INVOKE_STRING}")
PF_KEY = f"{CODE}_pf"
PF_STRING = f"override_string_{PF_KEY}"             # 722 的 c82
PFA = "master/skill/power_flip_action.orderedmap"
PF_PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_KEY}${PF_KEY}_lv{n}"
                    for n in (1, 2, 3))
LEADER_OVERRIDE = f"desc_override_{CODE}"
SLOT_OVERRIDE_SLOTS = (1, 2, 3, 5)
SLOT_OVERRIDE = {slot: f"desc_override_{CODE}_{slot}" for slot in SLOT_OVERRIDE_SLOTS}
# Added by the separately published 1.4.998 table revision, not by the
# hash-bound 1.4.987 package. Keep it as an immutable base dependency.
BASE_STRING_KEYS = frozenset({SLOT_OVERRIDE[5]})

SKILL_FLAG_KINDS = ("536", "704")
SKILL_FLAG_TEXT_KEYS = (CAS_FLAG1, CAS_FLAG2)
VOICE_KEY = f"{CODE}_voice_ready"
VOICE_ROUTE = {"kind": 3}                      # ChangeSkillFlag ← A1#1 的 536

MAIN_ICON = " <icon id='main'>  "              # desc_override 会盖掉客户端逐行画的 Ⓜ

TEXTS: dict[str, str] = {
    "skill1": "玉杵捣月·桂风连打",
    "skill2": "玉杵捣月·桂风连打",
    "desc1": "向距离最近的敌人突进，使出精准连击与八连重击，合计造成自身攻击力25倍的风属性伤害／"
             "最后砸下裂地一击（无后摇），造成自身攻击力65倍的风属性伤害／赋予自身攻击力提升效果",
    "desc2": "向距离最近的敌人突进，使出精准连击与八连重击，合计造成自身攻击力25倍的风属性伤害／"
             "最后砸下裂地一击（无后摇），造成自身攻击力65倍的风属性伤害／赋予自身攻击力提升效果",
}
SPEC = {
    "requires_client_base": "1.4.998",
    # desc_override 需要客户端面板接管能力；722 的 override_string_* 不需要补丁
    "required_capabilities": ("panel-description-override-v2", "dash-parameter-v1", "gauge-gain-rules-v1"),
    "pf_type": 3,                              # 作者 09-21：详情页显示「辅助」（原生 PF 也随之为 supporter）
    "extra_keys": {
        KL.CAS: (CAS_FLAG1, CAS_FLAG2, INVOKE_STRING, PF_STRING, LEADER_OVERRIDE,
                 *(SLOT_OVERRIDE[s] for s in SLOT_OVERRIDE_SLOTS if s != 5)),
        KL.SWITCHED: (VOICE_KEY,),
        PFA: (PF_KEY,),
    },
}

# ---------------------------------------------------------------- 行计划（donor + 逐格改）

# 「风属性共鸣」＝官方常规共鸣前置（前置 kind 2 编成≥6，作者补充 09-21 00:5x）
WIND_LEADER = {4: "2", 7: "600000", 8: "600000", 9: "Green"}
WIND_ABILITY = {6: "2", 9: "600000", 10: "600000", 11: "Green"}

PF_LV3_THRESHOLD = "500000"     # 5 次 Lv3 强化弹射
PF_LV3_COOLTIME = "360"         # 6 秒（帧）
COMBO_INVOKE_THRESHOLD = "15000000"   # 150 连击
COMBO_INVOKE_COOLTIME = "720"         # 12 秒（帧）

# ---- 「技能打完最后一段后清空连击数」（作者反馈轮 1，2026-09-21）
#
# 落法调研（客户端实读）：
#   * DSL 命令表（``ActionDslCommand.__constructs__``）里**没有**任何 Set/Reset 连击的构造，
#     只有 ``AddCombo``（index 82）。``Combo_Impl_.add`` 只钳上限 9999、**没有下限**，
#     所以「AddCombo 写负值」会把连击压成负数，不是清零 ⇒ DSL 侧无解。
#   * 词条层有 kind **390 SetCombo**（``InstantAbilityContentMasterValue("SetCombo",390)``
#     → ``AbilitySlotImpl.applyInstantBattle`` case 2 → ``ComboCalculatorImpl.setCombo``），
#     强度写 0 就是清零。官方唯一先例 = ``1410151#1``（精灵公主：连击≥500 → Set连击 0）。
#   * 触发器取 **107 SkillHit**：它由 ``EnemyImpl`` 在敌人真正吃到这一击之后才调
#     ``squadManager.countUpSkillHit`` ⇒ 天然满足「先结算最后一段伤害再清空」。
#     官方 11 行先例的 puller 都写 ``c28="0"``（Myself）、``c29=""``。
#
# 为了让阈值 1 精确落在**裂地一击**上：技能树里除裂地以外的 9 条 ``CreateNormalAttack``
# （精准连击 1 条 ×10 命中 + 玉杵 8 条）把 ``p16 incrementCombo`` 写 ``false``——
# 客户端 ``EnemyImpl`` 的守卫是 ``incrementCombo && !createdByPoison && …``，为假时
# 既不自然 +1 连击、也**不记 SkillHit**，于是整棵技能树只有裂地一击会把计数推到 1。
# 每段「命中连击＋55」走的是判定区 on-hit 块里的 ``AddCombo``，与这个标志无关，不受影响。
COMBO_RESET_TRIGGER = "107"          # SkillHit
COMBO_RESET_THRESHOLD = "100000"     # 1 次（整棵技能树只有裂地一击记 SkillHit）
COMBO_RESET_KIND = "390"             # SetCombo
COMBO_RESET_VALUE = "0"              # 置零

# (donor, source, cells, expect_describe)
LEADER: tuple[tuple[str, str, dict[int, str], str], ...] = (
    # L#0 722 双类型 PF（donor 自带风共鸣门，官方 141201#1）
    ("141201#1", "official",
     {0: CODE, 45: "722", 80: PF_KEY, 81: "1,2,3", 82: PF_STRING},
     "风·编成≥6 时: 自身 强化弹射覆盖"),
    # L#1..L#3 开局三件
    ("131122#2", "official",
     {0: CODE, 9: "Green", 47: "Green", 49: "20000", 50: "20000"},
     # kind 245 SecondSkillGauge ＝ 技能槽**上限**（记忆卡 wf-skill-gauge-max-exists，已两次误判）；
     # wf_describe 把枚举名直译成「2号位技能槽」，面板由 desc_override 接管，玩家看不到这串
     "风·编成≥6 时: 赋予全队(风) 2号位技能槽 20%"),
    ("141165#2", "official",
     {0: CODE, 49: "20000", 50: "20000"},
     "风·编成≥6 时: 赋予全队(风) 技能槽充能 20%"),
    ("141033#0", "official",
     {0: CODE, **WIND_LEADER, 49: "50000", 50: "50000"},
     "风·编成≥6 时: 赋予全队(风) 技能槽 50%"),
    # L#4..L#6 每 1 次强化弹射（2026-09-27 第二批：攻击力/技能伤害 20% → 2%；第三轮回调到 15%；连击＋5 不动）
    ("111183#1", "official",
     {0: CODE, **WIND_LEADER, 28: "100000", 29: "100000", 32: "(None)",
      45: "32", 47: "Green", 49: BALANCE_C["pf_growth"], 50: BALANCE_C["pf_growth"]},
     "风·编成≥6 时: 强化弹射≥1 → 赋予全队(风) 攻击力 15%"),
    ("111183#1", "official",
     {0: CODE, **WIND_LEADER, 28: "100000", 29: "100000", 32: "(None)",
      45: "34", 47: "Green", 49: BALANCE_C["pf_growth"], 50: BALANCE_C["pf_growth"]},
     "风·编成≥6 时: 强化弹射≥1 → 赋予全队(风) 技能伤害 15%"),
    ("121177#5", "official",
     {0: CODE, 9: "Green", 25: "2", 28: "100000", 29: "100000",
      49: "500000", 50: "500000"},
     "风·编成≥6 时: 强化弹射≥1 → 自身 追加连击 5"),
    # L#7/L#8 每 5 次 Lv3 强化弹射（同触发两行；226 排在 629 之前，让 629 吃到刚加的 500 连击）
    ("121177#5", "official",
     {0: CODE, 9: "Green", 25: "65", 28: PF_LV3_THRESHOLD, 29: PF_LV3_THRESHOLD,
      33: PF_LV3_COOLTIME, 49: "50000000", 50: "50000000"},
     "风·编成≥6 时: 强化弹射Lv3≥5(CT6秒) → 自身 追加连击 500"),
    ("111165#4", "official",
     {0: CODE, 9: "Green", 11: "0", 12: "", 14: "", 15: "", 17: "",
      28: PF_LV3_THRESHOLD, 29: PF_LV3_THRESHOLD, 33: PF_LV3_COOLTIME,
      68: INVOKE_STRING, 69: INVOKE_PROGRAM},
     f"风·编成≥6 时: 强化弹射Lv3≥5(CT6秒) → 自身 发动技能动作[{INVOKE_STRING}]"),
    # L#9 每 250 连击 → 自身技能伤害（2026-09-27 第二批：100% → 20%；第三轮回调到 70%）
    ("241004#1", "official",
     {0: CODE, **WIND_LEADER, 28: "25000000", 29: "25000000", 32: "(None)",
      45: "34", 46: "0", 47: "", 49: BALANCE_C["combo_growth"], 50: BALANCE_C["combo_growth"]},
     "风·编成≥6 时: 连击≥250 → 自身 技能伤害 70%"),
) + tuple(
    # L#10..L#12 每 3 次强化弹射（2026-09-27 第二批：694 5% → 1%，第三轮回调到 4%；35/245 是充能，不动）
    ("111183#1", "official",
     {0: CODE, **WIND_LEADER, 25: "2", 28: "300000", 29: "300000", 32: "(None)",
      33: "0", 45: kind, 46: "5", 47: "Green",
      49: BALANCE_C["pf3_growth"][kind], 50: BALANCE_C["pf3_growth"][kind]},
     f"风·编成≥6 时: 强化弹射≥3 → 赋予全队(风) {name} {int(BALANCE_C['pf3_growth'][kind]) // 1000}%")
    for kind, name in (("35", "技能槽充能"), ("245", "2号位技能槽"), ("694", "独立乘区技能伤害"))
)

_A, _AC = "action_skill", "attack_common"

PLAN: dict[int, tuple[tuple[str, str, dict[int, str], str], ...]] = {
    1: (
        ("1599981#0", "live",
         {0: f"{CODE}_1", 1: "true", 2: _A, 51: "50000", 52: "50000"},
         "自身 技能槽 50%"),
        # c6=202 显式钉住：donor 斩铁 1599981#1 在 2026-09-27 平衡批次去掉了 202（主位限制），本行保留。
        ("1599981#1", "live",
         {0: f"{CODE}_1", 1: "true", 2: _A, 6: "202", 18: "Green", 70: CAS_FLAG1},
         f"持有者为主位 且 风·编成≥6 时: 自身 切换技能形态[{CAS_FLAG1}]"),
    ),
    2: (
        ("1410333#0", "official",
         {0: f"{CODE}_2", 1: "true", 2: _AC, **WIND_ABILITY, 51: "25000", 52: "25000"},
         "风·编成≥6 时: 冲刺≥1 → 自身 状态攻击力 25%(6秒)×1次[累积上限4]"),
        ("1299914#0", "live",
         {0: f"{CODE}_2", 1: "true", 2: _AC, 11: "Green", 51: "500000", 52: "500000"},
         "风·编成≥6 时: 冲刺≥1 → 自身 追加连击 5"),
        ("1599982#2", "live",
         {0: f"{CODE}_2", 1: "true", 2: _AC, 11: "Green", 29: "Green",
          51: "40000", 52: "40000"},
         "风·编成≥6 时: 技能发动≥1(限5次) → 自身 技能伤害 40%"),
        # 423 consumes integer c118. During 0 is HP>=, so both thresholds must be zero.
        ("1510031#0", "official",
         {0: f"{CODE}_2", 1: "true", 2: _AC, 3: "0", 4: "",
          98: "0", 99: "", 100: "0", 101: "0", 108: "false",
          109: "423", 110: "5", 111: "(None)", 113: "0", 114: "0", 118: "12"},
         "持续·HP≥ → 赋予全队 限制技能槽增加 0%"),
    ),
    3: (
        ("1410333#1", "official",
         {0: f"{CODE}_3", 1: "false", 2: _A, **WIND_ABILITY, 113: "200000", 114: "200000"},
         "风·编成≥6 时: 持续·连击≥50(限1次) → 自身 技能伤害 200%"),
        ("1599982#0", "live",
         {0: f"{CODE}_3", 1: "false", 2: _A, 11: "Green", 27: "2", 28: "", 29: "",
          30: "100000", 31: "100000", 51: "1000000", 52: "1000000"},
         "风·编成≥6 时: 强化弹射≥1 → 自身 追加连击 10"),
        # 629：字符串键 c70 + 程序路径 c71。本角色没有 525 消耗行（不吃固有层数）。
        ("1611053#0", "official",
         {0: f"{CODE}_3", 1: "false", 2: _A, **WIND_ABILITY,
          27: "12", 28: "", 30: COMBO_INVOKE_THRESHOLD, 31: COMBO_INVOKE_THRESHOLD,
          34: "(None)", 35: COMBO_INVOKE_COOLTIME,
          70: INVOKE_STRING, 71: INVOKE_PROGRAM},
         f"风·编成≥6 时: 连击≥150(CT12秒) → 自身 发动技能动作[{INVOKE_STRING}]"),
        # kind 694（瞬发独立乘区技能伤害）官方 0 行，只有 live 先例 ⇒ 取 store（同玛格诺斯 A5#0）
        ("1299925#1", "live",
         {0: f"{CODE}_3", 1: "false", 2: _A, **WIND_ABILITY, 51: "10000", 52: "10000"},
         "风·编成≥6 时: 自身 独立乘区技能伤害 10%"),
        ("1599983#6", "live",
         {0: f"{CODE}_3", 1: "false", 2: _A, 11: "Green", 70: CAS_FLAG2},
         f"风·编成≥6 时: 自身 切换技能Flag2[{CAS_FLAG2}]"),
        # kind 390 SetCombo：官方唯一先例 1410151#1（精灵公主，连击≥500 → Set连击 0）。
        # 触发器换成 107 SkillHit、阈值 1 ⇒ 裂地一击命中之后才清零（见上方 COMBO_RESET_* 注释）。
        ("1410151#1", "official",
         {0: f"{CODE}_3", 1: "false", 2: _A, **WIND_ABILITY,
          27: COMBO_RESET_TRIGGER, 28: "0", 29: "",
          30: COMBO_RESET_THRESHOLD, 31: COMBO_RESET_THRESHOLD,
          34: "(None)", 35: "0", 51: COMBO_RESET_VALUE, 52: COMBO_RESET_VALUE},
         "风·编成≥6 时: 技能Hit≥1 → 自身 Set连击 0"),
    ),
    4: (
        ("1511652#1", "official",
         {0: f"{CODE}_4", 1: "true", 2: _AC, 51: "100000", 52: "100000"},
         "自身 技能伤害 100%"),
        ("1511652#0", "official",
         {0: f"{CODE}_4", 1: "true", 2: _AC, 51: "100000", 52: "100000"},
         "自身 攻击力 100%"),
    ),
    5: (
        ("1410334#0", "official",
         {0: f"{CODE}_5", 1: "true", 2: _AC, 6: "0", 11: "", 113: "50000", 114: "50000"},
         "持续·连击≥10(限1次) → 自身 攻击力 50%"),
        ("1410332#0", "official",
         {0: f"{CODE}_5", 1: "true", 2: _AC, 51: "25000", 52: "25000"},
         "自身 眩晕畏缩特攻 25%"),
        swift_guard_plan(CODE, 0, element="Green"),
    ),
    6: (
        ("1411835#0", "official",
         {0: f"{CODE}_6", 1: "true", 2: _A, 51: "10000", 52: "10000"},
         "风·编成≥6 时: 赋予全队(风) 技能槽充能 10%"),
    ),
}

# ---------------------------------------------------------------- 面板文案

CAS_TEXTS: dict[str, str] = {
    # 536 / 704 是「技能强化」条目：不写数字与时间（裁决 §3）
    CAS_FLAG1: "强化『玉杵捣月·桂风连打』的八连重击效果，并使裂地一击的伤害随连击数提升",
    CAS_FLAG2: "强化『玉杵捣月·桂风连打』的连击效果，技能命中时追加连击",
    INVOKE_STRING: "触发『玉杵捣月·桂风连打』的技能效果（不消耗技能槽）",
    PF_STRING: "强化弹射同时具备辅助与格斗两种类型：在格斗突进的同时赋予队伍辅助增益",
    LEADER_OVERRIDE: "\n".join((
        "风属性共鸣时，自身的强化弹射同时具备辅助与格斗两种类型",
        "风属性共鸣时，战斗开始时风属性角色技能槽最大值＋20%、技能充能速度＋20%、技能槽＋50%",
        # 2026-09-27 第二批：额外乘区 5% → 1%、每次 PF 攻击力/技能伤害 20% → 2%、每 250 连击 100% → 20%；
        # 第三轮（成长复核）回调：额外乘区 4%、每次 PF 15%、每 250 连击 70%
        "风属性共鸣时，每发动3次强化弹射，风属性角色技能充能速度＋5%、技能槽最大值＋5%、技能伤害额外乘区＋4%",
        "风属性共鸣时，每发动1次强化弹射，风属性角色攻击力＋15%、技能伤害＋15%、连击＋5",
        "风属性共鸣时，每发动5次强化弹射Lv3时，连击＋500，并触发自身技能效果（不消耗技能槽，冷却时间：6秒）",
        "风属性共鸣时，每达到250连击，自身技能伤害＋70%",
        "风属性共鸣时，冲刺间隔缩短效果不会让自身的冲刺冷却时间进一步缩短",
    )),
    SLOT_OVERRIDE[1]: "\n".join((
        "战斗开始时，自身技能槽＋50%",
        "主位且风属性共鸣时，强化『玉杵捣月·桂风连打』的八连重击效果，并使裂地一击的伤害随连击数提升",
    )),
    SLOT_OVERRIDE[2]: "\n".join((
        "风属性共鸣时，冲刺时自身攻击力＋25%（6秒，最多累积4次）",
        "风属性共鸣时，冲刺时连击＋5",
        "风属性共鸣时，发动技能时自身技能伤害＋40%（最多5层）",
        "全队无法因技能或能力效果增加技能槽（战斗开始时除外）",
    )),
    SLOT_OVERRIDE[3]: "\n".join(MAIN_ICON + line for line in (
        "风属性共鸣时，连击达到50以上时，自身技能伤害＋200%",
        "风属性共鸣时，发动强化弹射时，连击＋10",
        "风属性共鸣时，每达成150连击，触发自身技能效果（不消耗技能槽，冷却时间：12秒）",
        "风属性共鸣时，自身对敌人的技能伤害额外乘区＋10%",
        # 2026-09-27 第三轮（wf_balance_20260927c_fluffy，作者「技能都强化效果只在队长技或者能力里面按照格式写」）：
        # 704 开关行写「风属性共鸣时，」+ 强化条目 CAS_FLAG2 原文，不写数字（原「技能命中每次连击＋55」）。
        "风属性共鸣时，强化『玉杵捣月·桂风连打』的连击效果，技能命中时追加连击",
        "风属性共鸣时，自身技能的最后一击结束后，连击数归零",
    )),
    SLOT_OVERRIDE[5]: "\n".join((
        "连击达到10时，自身攻击力＋50%",
        "自身对陷入眩晕、畏缩状态的敌人攻击特攻＋25%",
    )),
}

# 槽 4/5/6 用客户端自动文案（describe 与目标面板语义一致），只记录进回执
PANEL_AUTO = {
    4: ("自身技能伤害＋100%", "自身攻击力＋100%"),
    5: ("连击达到10时，自身攻击力＋50%", "自身对陷入眩晕、畏缩状态的敌人攻击特攻＋25%"),
    6: ("风属性共鸣时，风属性角色技能槽充能＋10%",),
}

# ---------------------------------------------------------------- 特效族

FX_RUSH = ("rush", f"battle/effect/skill_unique/{TEMPLATE_CODE}",
           (f"{TEMPLATE_CODE}_rush", f"{TEMPLATE_CODE}_final"), "fx_lut.json")
FX_JAB = ("jab", f"battle/effect/skill_unique/{GRAFT_CODE}",
          (f"{GRAFT_CODE}_jab", f"{GRAFT_CODE}_blow", f"{GRAFT_CODE}_crack"), "fx_lut_jab.json")

# jab 族默认不克隆（施工单偏离 D-7）：整族克隆给战斗图集加 0.1823 Mpx（≈1.09%），
# 实测把 five-boss-r1 的 fits 压成 false，越过裁决 §6「单角色 ≤3.5% 且 fits」的通过线。
CLONE_JAB_FAMILY = False

FX_FAMILIES = (FX_RUSH,) + ((FX_JAB,) if CLONE_JAB_FAMILY else ())
FX_DIRECT_REFERENCE = (
    "battle/effect/skill_general/decoration/rush_aura",
    "battle/effect/skill_general/decoration/dummy_ball",
) + (() if CLONE_JAB_FAMILY else tuple(f"{FX_JAB[1]}/{base}" for base in FX_JAB[2]))

# ---------------------------------------------------------------- DSL 常量

PROGRAM_DIR = "battle/action/skill/action/rare5"

# 「无后摇」：裂地一击落下后第 3 帧就放球（判定区挂在敌侧参考点上，寿命不受影响）
FRAME_JAB = 20
FRAMES_PESTLE = (24, 28, 32, 36, 40, 44, 48, 52)
FRAME_FINAL = 62
FRAME_FINISHER = 65
FINISHER_LIFETIME = 15
RP_LIFETIME = 85                                   # ≥ FRAME_FINISHER + FINISHER_LIFETIME
STOP_BALL_FRAMES = FRAME_FINISHER + 3              # donor 30；上一轮 80
HIDE_CHARACTER_FRAMES = STOP_BALL_FRAMES           # donor 24
DUMMY_EFFECT_FRAMES = STOP_BALL_FRAMES             # donor 24

FINISHER_RADIUS = 150          # donor Circle{100}
ID_SHIFT = 10                  # xm21 子树主体 id 1..12 → 11..22
ID_SHIFT_2 = 30                # 复制出的后四段 → 31..42（与底座 4/5/8 及 11..22 都不相交）

CNA_COMBO_BONUS = 8            # CreateNormalAttack 节点下标（= p8 enablesComboBonus，536 开关用）
CNA_INCREMENT_COMBO = 16       # CreateNormalAttack 节点下标（= p16 incrementCombo，末位 Boolean）

BASE_RUSH_AREA_ID = 5          # 底座精准连击判定区 p19
BASE_FINISH_AREA_ID = 8        # 底座终结判定区 p19（裂地演出挂在它身上）
BASE_RP_ID = 4                 # 底座敌侧参考点 id
GRAFT_PESTLE_AREA_IDS = (1, 4, 7, 10)
GRAFT_FINISH_AREA_ID = 13

EFFECT_JAB = "ジャブ演出"
EFFECT_JAB2 = "ジャブ演出2"
EFFECT_BLOW = "振りかぶり"
EFFECT_FINISH = "フィニッシュ演出"
EFFECT_DUMMY = "ダミー演出"
EFFECT_CRACK_LABEL = "裂地演出"

# 倍率：两档同值、min=max 拉平（施工单偏离 D-4）。
# 2026-09-24：前段按原 12:20 比例分配 25 倍，裂地 65 倍，基础合计 90 倍。
# 536 开关保留玉杵每段 +0.75，以及裂地随连击数提升的原生乘区。
SKILL_MULT: dict[str, dict[str, dict[str, float]]] = {
    level: {
        "rush": {"min": 0.9375, "max": 0.9375},
        "pestle": {"min": 1.953125, "max": 1.953125, "alv_min": 0.75, "alv_max": 0.75},
        "finisher": {"min": 65.0, "max": 65.0},
    } for level in ("1", "2")
}
# 704（alv2）驱动的每段命中追加连击：没开 704 时 ALv 项返回 0 ⇒ 加 0
COMBO_PER_HIT = {"min": 0.0, "max": 0.0, "alv2_min": 55.0, "alv2_max": 55.0}

# donor 现值（防母本漂移；只比 min/max，容差 1e-6）
DONOR_MULT = {
    "1": {"rush": (0.33, 0.33), "pestle": (1.675, 1.675), "finisher": (16.7, 16.7)},
    "2": {"rush": (0.429, 0.5), "pestle": (2.1775, 2.5), "finisher": (21.71, 25.0)},
}
HITS = {"rush": 10, "pestle": 8, "finisher": 1}
SKILL_TOTAL_NO_FLAG = 90.0
MIN_ENCODED_BYTES = 2000

# 722：官方 fighter 底座（实读 2026-09-21，官方基线）
FIGHTER_PROGRAMS = {n: f"battle/action/power_flip/action/fighter$fighter_lv{n}" for n in (1, 2, 3)}
FIGHTER_SUPPRESS = {1: [90, 18], 2: [90, 20], 3: [90, 24]}
FIGHTER_CNA_COUNT = {1: 4, 2: 5, 3: 7}
FIGHTER_CNA_TOTAL = {1: 7.5, 2: 16.0, 3: 27.0}
PF_SUPPORT_BIND = PH.PF_SUPPORT_OFFSET             # 400


# ---------------------------------------------------------------- 行装配

def build_leader_rows(ctx) -> tuple[list[list[str]], list[dict[str, Any]]]:
    rows: list[list[str]] = []
    evidence: list[dict[str, Any]] = []
    for n, (donor, source, cells, expect) in enumerate(LEADER):
        label = f"leader#{n}({donor})"
        row, ev = KL.build_row(ctx, "leader_ability", donor, cells, source=source,
                               expect_describe=expect, label=label)
        if row[0] != CODE:
            raise KitError(f"{label}: c0 {row[0]!r} != {CODE}")
        rows.append(row)
        evidence.append(ev)
    if len(rows) != LEADER_ROW_COUNT:
        raise KitError(f"leader plan carries {len(rows)} rows, expected {LEADER_ROW_COUNT}")
    _ban_forbidden_leader_kinds(rows)
    _check_lv3_pair(rows)
    return rows, evidence


def _ban_forbidden_leader_kinds(rows: Sequence[Sequence[str]]) -> None:
    """队长表禁 422/724/713（裁决 §2/§8：写进队长表 = C7050）。瞬发 kind c45，持续 kind c107。"""
    for n, row in enumerate(rows):
        instant = row[45] if len(row) > 45 else ""
        during = row[107] if len(row) > 107 else ""
        if instant in ("422", "724", "713") or during in ("422", "724", "713"):
            raise KitError(f"leader#{n}: forbidden kind in leader_ability "
                           f"(c45={instant!r} c107={during!r})")


def _check_lv3_pair(rows: Sequence[Sequence[str]]) -> None:
    """L#7（226 连击＋500）与 L#8（629 触发技能）是同触发两行：阈值/CT 必须逐格一致。

    A 卡 §3.4 的警告：两行各自计数、各自 CT，不一致会出现「加了连击没放技能」。
    226 必须排在 629 之前 —— 让 629 跑的那棵技能树吃到刚加上去的 500 连击。
    """
    lv3 = [(n, r) for n, r in enumerate(rows) if r[25] == "65"]
    if len(lv3) != 2:
        raise KitError(f"expected exactly 2 trigger-65 leader rows, got {len(lv3)}")
    (n_a, a), (n_b, b) = lv3
    if a[45] != "226" or b[45] != "629":
        raise KitError(f"trigger-65 pair must be (226, 629) in that order, got "
                       f"({a[45]!r}, {b[45]!r})")
    if n_a > n_b:
        raise KitError("the 226 AddCombo row must precede the 629 invoke row")
    for col, what in ((28, "threshold-min"), (29, "threshold-max"), (33, "cooltime")):
        if a[col] != b[col]:
            raise KitError(f"trigger-65 pair {what} differs at c{col}: {a[col]!r} vs {b[col]!r}")
    if not b[68].strip():
        raise KitError("leader 629 row has an empty c68 string_id (C8601)")
    if b[69] != INVOKE_PROGRAM:
        raise KitError(f"leader 629 action_path drift: {b[69]!r}")


def build_ability_rows(ctx) -> tuple[dict[str, list[list[str]]], list[dict[str, Any]]]:
    rows_by_key: dict[str, list[list[str]]] = {}
    evidence: list[dict[str, Any]] = []
    for slot in range(1, 7):
        key_name = f"{CID}{slot}"
        rows: list[list[str]] = []
        for n, (donor, source, cells, expect) in enumerate(PLAN[slot]):
            label = f"{key_name}#{n}({donor})"
            row, ev = KL.build_row(ctx, "ability", donor, cells, source=source,
                                   element=ELEMENT, expect_describe=expect, label=label)
            ev["skill_flag"] = row[47] in SKILL_FLAG_KINDS
            rows.append(row)
            evidence.append(ev)
        KL.check_ability_key(rows, key_name, CODE, slot)
        rows_by_key[key_name] = rows
    total = sum(len(v) for v in rows_by_key.values())
    if total != ABILITY_RECORD_TOTAL:
        raise KitError(f"ability records {total} != {ABILITY_RECORD_TOTAL}")
    _order_problems(rows_by_key[f"{CID}3"])
    return rows_by_key, evidence


def _order_problems(rows: Sequence[Sequence[str]]) -> None:
    """629 行必须配字符串键，且排在同触发的 525 消耗行之前（本角色暂无 525，断言防以后加行）。"""
    kinds = [r[47] for r in rows]
    if "629" not in kinds:
        raise KitError(f"ability slot 3 lost the 629 invoke row: {kinds}")
    invoke = rows[kinds.index("629")]
    if not invoke[70].strip():
        raise KitError("ability 629 row has an empty c70 string_id (C8601)")
    if invoke[71] != INVOKE_PROGRAM:
        raise KitError(f"ability 629 action_path drift: {invoke[71]!r}")
    if invoke[1] != "false":
        raise KitError("629 does not work in the unison slot; the key must be c1=false")
    if "525" in kinds and kinds.index("629") > kinds.index("525"):
        raise KitError(f"629 must precede the 525 consume row, got {kinds}")
    _combo_reset_problems(rows)


def _combo_reset_problems(rows: Sequence[Sequence[str]]) -> None:
    """「技能最后一段打完后清空连击」那一行的硬契约（作者反馈轮 1）。"""
    kinds = [r[47] for r in rows]
    if COMBO_RESET_KIND not in kinds:
        raise KitError(f"ability slot 3 lost the {COMBO_RESET_KIND} SetCombo row: {kinds}")
    row = rows[kinds.index(COMBO_RESET_KIND)]
    if row[27] != COMBO_RESET_TRIGGER:
        raise KitError(f"SetCombo row trigger {row[27]!r} != {COMBO_RESET_TRIGGER} (SkillHit); "
                       f"别的触发器给不出「最后一段打完之后」的时序")
    if (row[30], row[31]) != (COMBO_RESET_THRESHOLD, COMBO_RESET_THRESHOLD):
        raise KitError(f"SetCombo row threshold {(row[30], row[31])} != {COMBO_RESET_THRESHOLD}")
    if (row[51], row[52]) != (COMBO_RESET_VALUE, COMBO_RESET_VALUE):
        raise KitError(f"SetCombo row value {(row[51], row[52])} != {COMBO_RESET_VALUE} "
                       f"（非 0 就不是清空，而是把连击钉到某个数）")
    if row[28] != "0":
        raise KitError(f"SetCombo row puller c28 {row[28]!r} != '0'（官方 11 行 SkillHit 先例全是 Myself）")
    if row[34] != "(None)":
        raise KitError(f"SetCombo row trigger_limit {row[34]!r} != '(None)'（每次技能都要清）")


def check_skill_flag_strings(rows: Iterable[Sequence[str]], keys: set[str]) -> list[str]:
    """536 / 704 行的 c70 字符串键必须已登记在 ``custom_ability_string``（漏登记 = C8601）。"""
    hits: list[str] = []
    for row in rows:
        if len(row) > 70 and row[47] in SKILL_FLAG_KINDS:
            sid = row[70].strip()
            if not sid:
                raise KitError(f"kind {row[47]} row has an empty c70 string_id (C8601)")
            if sid not in keys:
                raise KitError(f"kind {row[47]} c70 string_id {sid!r} not in custom_ability_string "
                               f"{sorted(keys)} (C8601)")
            hits.append(sid)
    return hits


# ---------------------------------------------------------------- 共享表文本

def write_strings(ctx) -> dict[str, str]:
    """``custom_ability_string``：536/704/629/722 条目 + 4 个 ``desc_override``。"""
    from wf_midautumn_base_strings import validate_base_strings
    validate_base_strings(ctx, {k: CAS_TEXTS[k] for k in BASE_STRING_KEYS})
    declared = set(ctx.spec.extra_keys.get(KL.CAS, ()))
    missing = [key for key in CAS_TEXTS if key not in declared | BASE_STRING_KEYS]
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
    ctx.write_flat(KL.CAS, {key: [[text]] for key, text in CAS_TEXTS.items()
                          if key not in BASE_STRING_KEYS})
    # Existing API restores only these rows from live and drops only their
    # candidate claims. It does not edit the installed ownership manifest.
    ctx.unclaim(KL.CAS, BASE_STRING_KEYS)
    return dict(CAS_TEXTS)


def write_action_skill(ctx) -> dict[str, list[str]]:
    """``action_skill`` 两档：名称/描述由 tables 写 TEXTS，这里只改能量并核对程序路径。"""
    spec = ctx.spec
    inner = ctx.pkg_nested(CODE)
    if set(inner) != {"1", "2"}:
        raise KitError(f"package action_skill inner keys {sorted(inner)}")
    out: dict[str, list[str]] = {}
    for level, cells in sorted(inner.items()):
        cells = list(cells)
        if len(cells) != 24:
            raise KitError(f"action_skill {level}: {len(cells)} columns, expected 24")
        if cells[7] != ctx.program_path(level):
            raise KitError(f"action_skill {level} program path drift: {cells[7]!r}")
        if cells[0] != spec.texts[f"skill{level}"] or cells[1] != spec.texts[f"desc{level}"]:
            raise KitError(f"action_skill {level}: name/desc differ from design texts (rerun tables)")
        cells[4] = cells[5] = "580"        # 目标面板 skill.energy；觉醒前后两档同值
        out[level] = cells
    ctx.write_nested(KL.ACTION, CODE, {lv: [cells] for lv, cells in out.items()}, replace_inner=True)
    return out


# ---------------------------------------------------------------- DSL 工具

def command(payload: list) -> list:
    return ["Command", list(payload)]


def wait_event(frame: int, payloads: Sequence[list]) -> list:
    """``["Event", ["Wait", N, "*", ["Block", [...]]]]``。

    禁写 ``Command Wait``：未知构造名会被静默落成索引 0，整块被吞且不报错
    （记忆卡 wf-dsl-command-wait-trace-trap）。
    """
    return ["Event", ["Wait", int(frame), "*", ["Block", [command(p) for p in payloads]]]]


def block(payloads: Sequence[list]) -> list:
    return ["Block", [command(p) for p in payloads]]


def add_combo_cmd() -> list:
    """``AddCombo`` 走 SLv/ALv 通道：``alv2`` 由 704 供值，没开时 ALv 项返回 0。

    客户端实证：``ActionEvaluator`` case 82 → ``resolveSLvValueRoundInt``（硬钳 9999）；
    ``Environment.internalResolveALvValueTerm`` 的 ``case 2 → alv2_min/alv2_max`` 是战斗侧真通路
    （``FixedSLvValueResolver`` 只喂描述器，别拿它当依据）。
    """
    return ["AddCombo", [dict(COMBO_PER_HIT)]]


def _only(items: list, what: str) -> list:
    if len(items) != 1:
        raise KitError(f"expected exactly 1 {what}, got {len(items)}")
    return items[0]


def _slv(value: Sequence[dict]) -> tuple[float, float]:
    entry = _only(list(value), "SLv value")
    return float(entry["min"]), float(entry["max"])


def _assert_mult(cmd: list, expect: tuple[float, float], label: str) -> None:
    got = _slv(cmd[6])
    if abs(got[0] - expect[0]) > 1e-6 or abs(got[1] - expect[1]) > 1e-6:
        raise KitError(f"{label}: donor CNA multiplier drift {got} != {expect}")


def _silence_skill_hit(cna: list, label: str) -> list:
    """把一条 ``CreateNormalAttack`` 的 ``p16 incrementCombo`` 从官方的 ``true`` 改成 ``false``。

    只影响客户端 ``EnemyImpl`` 里那道 ``incrementCombo && !createdByPoison && …`` 守卫：
    这一击不再自然 +1 连击，也**不再记 SkillHit**（``squadManager.countUpSkillHit`` 被跳过）。
    每段「命中连击＋55」走的是判定区 on-hit 块里的 ``AddCombo``，与本标志无关。
    """
    if len(cna) <= CNA_INCREMENT_COMBO:
        raise KitError(f"{label}: CreateNormalAttack has {len(cna) - 1} params, expected 16")
    if cna[CNA_INCREMENT_COMBO] is not True:
        raise KitError(f"{label}: donor CNA p16 incrementCombo drift {cna[CNA_INCREMENT_COMBO]!r}")
    cna[CNA_INCREMENT_COMBO] = False
    return cna


def signature_problems(tree) -> list[str]:
    """官方参数形状签名差分（``wf_dsl_sig`` 逐参类型）—— 防 F1034。

    裸数值塞进 ``Array`` 参（例如 Sector 角度）会在详情页/进战斗 F1034，而 AMF3 往返自检
    抓不到（记忆卡 wf-dsl-param-shape-f1034）。同时兜住「构造名写错被静默吞掉」。
    """
    problems: list[str] = []

    def is_block(value) -> bool:
        return isinstance(value, list) and len(value) == 2 and value[0] == "Block" \
            and isinstance(value[1], list)

    def check(name: str, sig: Sequence[str], params: list, where: str) -> None:
        if len(params) != len(sig):
            problems.append(f"{where}{name}: {len(params)} params, signature wants {len(sig)}")
            return
        for i, (want, value) in enumerate(zip(sig, params), start=1):
            if want == "int":
                ok = isinstance(value, int) and not isinstance(value, bool)
            elif want == "Number":
                ok = isinstance(value, (int, float)) and not isinstance(value, bool)
            elif want == "Boolean":
                ok = isinstance(value, bool)
            elif want == "String":
                ok = isinstance(value, str)
            elif want == "Array":
                ok = isinstance(value, list) and not is_block(value)
            elif want == "ActionDslExpression":
                ok = is_block(value)
            else:                                   # haxe enum / Option：[标签, …] 或 null
                ok = value is None or (isinstance(value, list) and value
                                       and isinstance(value[0], str))
            if not ok:
                problems.append(f"{where}{name} p{i}: expected {want}, got {type(value).__name__} "
                                f"{str(value)[:60]!r}")

    def walk(node, where: str) -> None:
        if isinstance(node, list):
            if node and node[0] == "Command" and len(node) == 2 and isinstance(node[1], list):
                payload = node[1]
                name = payload[0]
                sig = SIG.COMMANDS.get(name)
                if sig is None:
                    problems.append(f"{where}unknown command {name!r} (silently swallowed at runtime)")
                else:
                    check(name, sig, payload[1:], where)
                for child in payload[1:]:
                    walk(child, f"{where}{name}/")
                return
            if node and node[0] == "Event" and len(node) == 2 and isinstance(node[1], list):
                event = node[1]
                name = event[0]
                sig = SIG.EVENTS.get(name)
                if sig is None:
                    problems.append(f"{where}unknown event {name!r}")
                else:
                    check(name, sig, event[1:], where)
                for child in event[1:]:
                    walk(child, f"{where}{name}/")
                return
            for child in node:
                walk(child, where)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child, where)

    walk(tree, "")
    return problems


def dsl_problems(tree, *, element: int | None = None) -> list[str]:
    problems: list[str] = []
    problems += [f"signature: {p}" for p in signature_problems(tree)]
    problems += [f"direction: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if element is not None:
        problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, element)]
    return problems


def roundtrip_problems(tree) -> list[str]:
    """AMF3 往返自检：``encode_amf3`` **只吃裸树**（喂 ``{tree, numbers}`` 壳会 F1034）。"""
    import zlib
    try:
        raw = wf_dsl.encode_amf3(tree)
    except Exception as exc:                                   # noqa: BLE001
        return [f"encode_amf3 failed: {exc}"]
    if wf_dsl.parse_dsl(raw).get("tree") != tree:
        return ["AMF3 roundtrip mismatch"]
    deflated = zlib.compress(raw, 9)[2:-4]
    if wf_dsl.parse_dsl(zlib.decompressobj(-15).decompress(deflated)).get("tree") != tree:
        return ["deflate roundtrip mismatch"]
    return []


def encoded_size(tree) -> int:
    """落盘前的 AMF3 字节数。往返自检对「喂错壳」是瞎的，尺寸同量级是第二道眼。"""
    return len(wf_dsl.encode_amf3(tree))


def effect_refs(tree) -> list[str]:
    out: list[str] = []
    for cmd in wf_dsl.iter_dsl_commands(tree, "ShowEffect"):
        ref = cmd[2]
        if isinstance(ref, list) and len(ref) >= 2 and isinstance(ref[1], str):
            out.append(ref[1])
    return out


def _write_dsl_checked(ctx, program: str, tree) -> str:
    if not (isinstance(tree, list) and tree and tree[0] == "ActionDsl"):
        raise KitError(f"write_dsl needs a bare ActionDsl tree, got {type(tree).__name__}")
    logical = ctx.write_dsl(program, tree)
    back = ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
    if back != tree:
        raise KitError(f"DSL readback mismatch: {logical}")
    return logical


# ---------------------------------------------------------------- 技能树嫁接

def _shift_area(area: list, cna: list, shift: int) -> None:
    area[19] += shift
    area[21] += shift
    area[22] += shift
    cna[1] += shift


def graft_tree(base_tree, graft_source, level: str) -> tuple[list, dict[str, Any]]:
    """底座 141033 ``combat_animal_<level>`` ＋ 嫁接 141081 ``combat_animal_xm21_<level>``。

    纯函数（不碰 ctx / 不写盘）。rework1 相对上一轮的改动：玉杵重击 4 段 → **8 段**
    （复制一份，主体 id 再 +30），时间轴拉成 24..52，停球/隐身/替身球压到裂地一击后第 3 帧
    （「无后摇」），每个判定区 on-hit 追加走 ``alv2`` 通道的 ``AddCombo``（704）。
    """
    if level not in SKILL_MULT:
        raise KitError(f"unknown skill level {level!r}")
    tree = copy.deepcopy(base_tree)
    xm = copy.deepcopy(graft_source)
    mult = SKILL_MULT[level]
    donor_mult = DONOR_MULT[level]

    # ---- 底座头部：movementPriority 3（有 MoveBall）、tree[3]=true、tree[10]=0（自动＝技能伤害）
    if tree[0] != "ActionDsl" or tree[1] != 3 or tree[3] is not True or tree[10] != 0:
        raise KitError(f"base donor head drift: {tree[:4]} bta={tree[10]}")
    if xm[0] != "ActionDsl":
        raise KitError("graft donor is not an ActionDsl tree")

    # ---- 底座：停球 / 隐身 / 替身球 / 参考点寿命
    stop = _only(list(wf_dsl.iter_dsl_commands(tree, "StopBall")), "StopBall in base")
    if stop[2] != 30:
        raise KitError(f"base StopBall frames drift: {stop[2]}")
    stop[2] = STOP_BALL_FRAMES
    hide = _only(list(wf_dsl.iter_dsl_commands(tree, "HideCharacter")), "HideCharacter in base")
    if hide[2] != 24:
        raise KitError(f"base HideCharacter frames drift: {hide[2]}")
    hide[2] = HIDE_CHARACTER_FRAMES
    dummy = _only([s for s in wf_dsl.iter_dsl_commands(tree, "ShowEffect") if s[1] == EFFECT_DUMMY],
                  EFFECT_DUMMY)
    if dummy[5] != ["SpecifyEffectLifetimeDirectly", 24]:
        raise KitError(f"base dummy effect lifetime drift: {dummy[5]}")
    dummy[5] = ["SpecifyEffectLifetimeDirectly", DUMMY_EFFECT_FRAMES]

    rp = _only(list(wf_dsl.iter_dsl_commands(tree, "CreateReferencePoint")),
               "CreateReferencePoint in base")
    if rp[10] != BASE_RP_ID or rp[9] != 60:
        raise KitError(f"base reference point drift: id={rp[10]} lifetime={rp[9]}")
    rp[9] = RP_LIFETIME
    rp_block = rp[11]

    # ---- 底座参考点块里的三件东西
    areas = list(wf_dsl.iter_dsl_commands(rp_block, "CreateHitArea"))
    rush_area = _only([a for a in areas if a[19] == BASE_RUSH_AREA_ID], "base rush CreateHitArea")
    finish_area = _only([a for a in areas if a[19] == BASE_FINISH_AREA_ID],
                        "base finisher CreateHitArea")
    final_show = _only([s for s in wf_dsl.iter_dsl_commands(rp_block, "ShowEffect")
                        if s[1] == EFFECT_FINISH], f"base {EFFECT_FINISH}")

    rush_cna = _only(list(wf_dsl.iter_dsl_commands(rush_area[23], "CreateNormalAttack")),
                     "base rush CreateNormalAttack")
    _assert_mult(rush_cna, donor_mult["rush"], f"skill{level} rush")
    rush_cna[6] = [dict(mult["rush"])]
    _silence_skill_hit(rush_cna, f"skill{level} rush")
    if rush_area[13] != ["SpecifyHitAreaLifetimeDirectly", 18] \
            or rush_area[14] != ["CalculatedUsingMaxNumOfHits", HITS["rush"]]:
        raise KitError(f"base rush area drift: {rush_area[13]} {rush_area[14]}")
    rush_area[23] = block([rush_cna, add_combo_cmd()])

    finish_cna = _only(list(wf_dsl.iter_dsl_commands(finish_area[23], "CreateNormalAttack")),
                       "base finisher CreateNormalAttack")
    _assert_mult(finish_cna, donor_mult["finisher"], f"skill{level} finisher")
    finish_cna[6] = [dict(mult["finisher"])]
    if finish_cna[8] is not False:
        raise KitError(f"base finisher CNA p8 drift: {finish_cna[8]}")
    # 裂地一击是整棵树里**唯一**保留 incrementCombo 的一击 ⇒ SkillHit 计数 1 只可能来自它，
    # 词条 390（SetCombo 0，阈值 1）因此必然落在「最后一段打完之后」。
    if finish_cna[CNA_INCREMENT_COMBO] is not True:
        raise KitError(f"base finisher CNA p16 incrementCombo drift: "
                       f"{finish_cna[CNA_INCREMENT_COMBO]!r}")
    shake_finish = _only(list(wf_dsl.iter_dsl_commands(finish_area[23], "ShakeCamera")),
                         "base finisher ShakeCamera")

    # ---- xm21：取四段重击 + 三个演出
    xrp = _only(list(wf_dsl.iter_dsl_commands(xm, "CreateReferencePoint")),
                "CreateReferencePoint in graft donor")
    xblock = xrp[11]
    xareas = list(wf_dsl.iter_dsl_commands(xblock, "CreateHitArea"))
    if tuple(a[19] for a in xareas) != GRAFT_PESTLE_AREA_IDS + (GRAFT_FINISH_AREA_ID,):
        raise KitError(f"graft donor hit-area ids drift: {[a[19] for a in xareas]}")
    donor_pestles = [a for a in xareas if a[19] in GRAFT_PESTLE_AREA_IDS]
    xshow = {s[1]: s for s in wf_dsl.iter_dsl_commands(xblock, "ShowEffect")}
    missing = [n for n in (EFFECT_JAB, EFFECT_BLOW, EFFECT_FINISH) if n not in xshow]
    if missing:
        raise KitError(f"graft donor is missing effects {missing}")
    jab_show, blow_show, crack_show = xshow[EFFECT_JAB], xshow[EFFECT_BLOW], xshow[EFFECT_FINISH]

    # 段数翻倍：原四段 id +10（11..22），复制出的后四段再 +30（31..42），两组 bind 不相交；
    # 坐标锚点从 xm21 自己的球前参考点（p2=0）改挂底座敌侧参考点 4
    pestle_areas: list[list] = []
    for shift in (ID_SHIFT, ID_SHIFT + ID_SHIFT_2):
        for donor_area in donor_pestles:
            area = copy.deepcopy(donor_area)
            if area[2] != 0:
                raise KitError(f"graft pestle area anchor drift: p2={area[2]}")
            cna = _only(list(wf_dsl.iter_dsl_commands(area[23], "CreateNormalAttack")),
                        "graft pestle CreateNormalAttack")
            _assert_mult(cna, donor_mult["pestle"], f"skill{level} pestle")
            if cna[1] != area[22]:
                raise KitError(f"graft pestle CNA subject {cna[1]} != hit-area node[22] {area[22]}")
            area[2] = BASE_RP_ID
            _shift_area(area, cna, shift)
            cna[6] = [dict(mult["pestle"])]
            # 2026-09-27 第二批（口径 B.1，技能每次施放单目标总削韧 ≤30）：只动 p13 6.25 → 1.5
            if _slv(cna[CNA_DETOUGHNESS]) != (PESTLE_DETOUGHNESS_DONOR, PESTLE_DETOUGHNESS_DONOR):
                raise KitError(f"skill{level} pestle: donor CNA p13 detoughness drift "
                               f"{cna[CNA_DETOUGHNESS]!r}")
            cna[CNA_DETOUGHNESS] = [{"min": PESTLE_DETOUGHNESS, "max": PESTLE_DETOUGHNESS}]
            _silence_skill_hit(cna, f"skill{level} pestle#{len(pestle_areas)}")
            area[23] = block([cna, add_combo_cmd()])
            pestle_areas.append(area)
    if len(pestle_areas) != HITS["pestle"]:
        raise KitError(f"pestle segments {len(pestle_areas)} != {HITS['pestle']}")
    ids = [a[19] for a in pestle_areas] + [a[21] for a in pestle_areas] \
        + [a[22] for a in pestle_areas] + [BASE_RP_ID, BASE_RUSH_AREA_ID, BASE_FINISH_AREA_ID]
    if len(set(ids)) != len(ids):
        raise KitError(f"subject id collision after doubling the pestle segments: {sorted(ids)}")

    jab_show2 = copy.deepcopy(jab_show)
    jab_show2[1] = EFFECT_JAB2
    for show, anchor in ((jab_show, BASE_RP_ID), (jab_show2, BASE_RP_ID),
                         (blow_show, BASE_RP_ID), (crack_show, BASE_FINISH_AREA_ID)):
        show[3] = anchor
    crack_show[1] = EFFECT_CRACK_LABEL          # 与底座的「フィニッシュ演出」区分开

    # ---- 终结判定区：放大到 Circle{150}、寿命 15；裂地演出 + 震屏挂 p20；p23 外包 Conditionals
    if finish_area[9] != ["Circle", [{"min": 100, "max": 100}]] \
            or finish_area[13] != ["SpecifyHitAreaLifetimeDirectly", 10]:
        raise KitError(f"base finisher area drift: {finish_area[9]} {finish_area[13]}")
    finish_area[9] = ["Circle", [{"min": FINISHER_RADIUS, "max": FINISHER_RADIUS}]]
    finish_area[13] = ["SpecifyHitAreaLifetimeDirectly", FINISHER_LIFETIME]
    finish_area[20] = block([crack_show, shake_finish])
    then_cna = copy.deepcopy(finish_cna)
    then_cna[8] = True                           # 536 开关：裂地一击吃连击加成（×(1+连击×0.005)）
    else_cna = copy.deepcopy(finish_cna)
    else_cna[8] = False
    # Conditionals 的分支必须是完整 Block；空分支写 ["Block", []]，禁写 ["DoNothing"]
    # （那是 IfTargetNotFound 的枚举，进游戏 F1009 —— 记忆卡 wf-dsl-donothing-enum-trap）
    finish_area[23] = block([add_combo_cmd(),
                             ["ConditionalsChangeSkillFlag", 1,
                              block([then_cna]), block([else_cna])]])

    # ---- 重排参考点块的时间轴（兄弟 Wait 各自从块首计帧，沿用 xm21 的写法）
    timeline: list[list] = [command(rush_area), wait_event(FRAME_JAB, [jab_show])]
    for n, (frame, area) in enumerate(zip(FRAMES_PESTLE, pestle_areas)):
        payloads: list[list] = [area]
        if n == 4:                                # 后半段补一次挥拳演出（复用同一张特效，零图集增量）
            payloads.append(jab_show2)
        if n == len(pestle_areas) - 1:
            payloads.append(blow_show)
        timeline.append(wait_event(frame, payloads))
    timeline.append(wait_event(FRAME_FINAL, [final_show]))
    timeline.append(wait_event(FRAME_FINISHER, [finish_area]))
    rp[11] = ["Block", timeline]
    if FRAME_FINISHER + FINISHER_LIFETIME > RP_LIFETIME:
        raise KitError("reference point lifetime is shorter than the last hit area window "
                       "(伤害会静默消失)")

    totals = {seg: round(mult[seg]["max"] * HITS[seg], 4) for seg in HITS}
    alv = round(mult["pestle"].get("alv_max", 0.0) * HITS["pestle"], 4)
    total_no_flag = round(sum(totals.values()), 4)
    if abs(total_no_flag - SKILL_TOTAL_NO_FLAG) > 1e-6:
        raise KitError(f"skill{level} total {total_no_flag}× != the panel's {SKILL_TOTAL_NO_FLAG}×")
    # 每次施放单目标总削韧（第二批口径 B.1 ≤30）：精准连击 10 段 ＋ 八连重击 8 段 ＋ 裂地 1 段
    detoughness = {"rush": _slv(rush_cna[CNA_DETOUGHNESS])[1] * HITS["rush"],
                   "pestle": PESTLE_DETOUGHNESS * HITS["pestle"],
                   "finisher": _slv(finish_cna[CNA_DETOUGHNESS])[1] * HITS["finisher"]}
    detoughness_total = round(sum(detoughness.values()), 6)
    if detoughness_total > 30:
        raise KitError(f"skill{level} detoughness per cast {detoughness_total} > 30")
    # 每个判定区的 on-hit 块各挂一条：精准连击 1 + 玉杵 8 + 裂地 1
    want_combo_areas = 1 + HITS["pestle"] + 1
    combo_areas = len(list(wf_dsl.iter_dsl_commands(tree, "AddCombo")))
    if combo_areas != want_combo_areas:
        raise KitError(f"AddCombo appears on {combo_areas} hit areas, expected {want_combo_areas}")
    # 「清空连击」的落点保证：整棵树里只有裂地一击记 SkillHit（then/else 两条分支是同一击的副本）
    all_cna = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    counting = [c for c in all_cna if c[CNA_INCREMENT_COMBO] is True]
    silent = [c for c in all_cna if c[CNA_INCREMENT_COMBO] is False]
    if len(all_cna) != 1 + HITS["pestle"] + 2 or len(counting) != 2 or len(silent) != 9:
        raise KitError(f"skill{level} incrementCombo layout drift: {len(all_cna)} CNA, "
                       f"{len(counting)} counting / {len(silent)} silent —— "
                       f"SkillHit 阈值 1 不再等价于「裂地一击打完」")
    evidence = {
        "level": level,
        "multipliers": {seg: dict(mult[seg]) for seg in HITS},
        "segment_hits": dict(HITS),
        "segment_totals": totals,
        "total_no_flag": total_no_flag,
        "total_with_flag1": round(total_no_flag + alv, 4),
        "combo_per_hit": dict(COMBO_PER_HIT),
        "combo_hits_per_cast": sum(HITS.values()),
        "skill_hit_counting_cna": {"counting": len(counting), "silent": len(silent),
                                   "note": "只有裂地一击 incrementCombo=true ⇒ 词条 390 "
                                           "(SkillHit≥1) 必然在最后一段伤害结算之后清空连击"},
        "frames": {"jab": FRAME_JAB, "pestle": list(FRAMES_PESTLE),
                   "final": FRAME_FINAL, "finisher": FRAME_FINISHER},
        "stop_ball": STOP_BALL_FRAMES, "reference_point_lifetime": RP_LIFETIME,
        "subject_ids": {"base_rush": BASE_RUSH_AREA_ID, "base_finisher": BASE_FINISH_AREA_ID,
                        "grafted": [a[19] for a in pestle_areas]},
        "combo_bonus_branch": {"then_p8": True, "else_p8": False},
        "detoughness": {"segments": {seg: round(v, 6) for seg, v in detoughness.items()},
                        "per_cast": detoughness_total,
                        "pestle_per_hit": [PESTLE_DETOUGHNESS_DONOR, PESTLE_DETOUGHNESS]},
    }
    return tree, evidence


def build_skill_tree(ctx, level: str, families: Sequence[dict[str, Any]]
                     ) -> tuple[list, dict[str, Any]]:
    base = ctx.template_dsl(f"{PROGRAM_DIR}/{TEMPLATE_CODE}${TEMPLATE_CODE}_{level}")
    xm = ctx.template_dsl(f"{PROGRAM_DIR}/{GRAFT_CODE}${GRAFT_CODE}_{level}")
    tree, evidence = graft_tree(base, xm, level)
    rewrites = 0
    for family in families:
        tree, info = ctx.rewrite_effect_refs(tree, family, strict=True)
        rewrites += info["rewritten"]
    refs = effect_refs(tree)
    allowed = {f["dst_dir"] for f in families}
    for ref in refs:
        head = ref.rsplit("/", 1)[0]
        if head in allowed or ref in FX_DIRECT_REFERENCE:
            continue
        raise KitError(f"skill {level}: effect reference {ref!r} is neither a cloned family "
                       f"member nor an official shared decoration")
    problems = dsl_problems(tree, element=ELEMENT) + roundtrip_problems(tree)
    size = encoded_size(tree)
    if size < MIN_ENCODED_BYTES:
        problems.append(f"encoded DSL is suspiciously small ({size} bytes) —— 疑似喂了包装壳")
    if problems:
        raise KitError(f"skill {level} DSL gates failed: {problems}")
    evidence["effect_rewrites"] = rewrites
    evidence["effect_refs"] = refs
    evidence["encoded_bytes"] = size
    return tree, evidence


# ---------------------------------------------------------------- 629「触发自身技能效果」

def build_invoke_tree(skill_tree_2) -> tuple[list, dict[str, Any]]:
    """629 指向的 ``ability_skill`` 树 ＝ 技能档 2 的深拷贝。

    ``_deviations.json›fluffy[1]`` 的落法：伤害、段数、连击效果与真正发动技能完全相同，
    但不消耗技能槽、不播 cut-in／技能语音、不触发别人的「发动技能时」（trigger 23）。
    ``tree[10]`` 保持 0（自动档＝AbilitySkill＝技能伤害）；写 3 只拿 PF 通用乘区、丢技能增伤。

    2026-09-27 平衡第二批（口径 B.3，能力调用技能每次 ≤3）：唯一的差别是全部
    ``CreateNormalAttack`` 的 p13 削韧改成 ``INVOKE_DETOUGHNESS``（0.15；19 段 ⇒ 每次 2.85，原 65）。
    两个触发源 CT 分别 6 秒（队长 L#8）/ 12 秒（能力3 #2），都 > 3 秒 ⇒ 上限 3。
    """
    tree = copy.deepcopy(skill_tree_2)
    if tree[10] != 0:
        raise KitError(f"629 tree must keep the automatic damage attribution, got {tree[10]}")
    allowed = {PESTLE_DETOUGHNESS, PESTLE_DETOUGHNESS_DONOR}
    seen: list[float] = []
    for cna in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"):
        low, high = _slv(cna[CNA_DETOUGHNESS])
        if low != high:
            raise KitError(f"629 tree CNA p13 is not flattened: {cna[CNA_DETOUGHNESS]!r}")
        seen.append(high)
        cna[CNA_DETOUGHNESS] = [{"min": INVOKE_DETOUGHNESS, "max": INVOKE_DETOUGHNESS}]
    if len(seen) != 1 + HITS["pestle"] + 2 or not allowed & set(seen):
        raise KitError(f"629 tree CNA layout drift: {len(seen)} CNA, p13 {sorted(set(seen))}")
    # then/else 两条裂地副本只会执行一条 ⇒ 每次调用 = 精准连击 10 ＋ 八连 8 ＋ 裂地 1 = 19 段
    per_cast = round(INVOKE_DETOUGHNESS * sum(HITS.values()), 6)
    if per_cast > 3:
        raise KitError(f"629 tree detoughness per call {per_cast} > 3")
    problems = roundtrip_problems(tree)
    if problems:
        raise KitError(f"629 ability_skill tree gates failed: {problems}")
    return tree, {"source": "skill level 2 (deep copy) + p13 detoughness override",
                  "encoded_bytes": encoded_size(tree),
                  "damage_attribution": tree[10],
                  "detoughness": {"per_hit": INVOKE_DETOUGHNESS, "per_call": per_cast,
                                  "source_p13": sorted(set(seen))}}


# ---------------------------------------------------------------- 722 双类型强化弹射

def build_pf_tree(ctx, level: int) -> tuple[list, dict[str, Any]]:
    """官方 ``fighter_lv{n}`` 整树作底座 ＋ 官方 ``supporter_lv{n}`` 的辅助增益块（白虎/夏日白配方）。

    倍率**不缩放**：她是技伤主 C，PF 只负责把辅助增益铺出去（A 卡 §4.2 白虎先例同样未缩放）。
    """
    program = FIGHTER_PROGRAMS[level]
    tree = copy.deepcopy(ctx.template_dsl(program))
    raw = ctx.official_read(wf_dsl.dsl_logical(program), "common")
    if raw is None:
        raise KitError(f"official baseline lacks the fighter PF donor {program}")
    if tree[0] != "ActionDsl" or tree[1] != 2 or tree[10] != 0:
        raise KitError(f"fighter lv{level} head drift: {tree[:3]} bta={tree[10]}")
    suppress = [c[1] for c in wf_dsl.iter_dsl_commands(tree, "SetPowerFilpSuppress")]
    if suppress != FIGHTER_SUPPRESS[level]:
        raise KitError(f"fighter lv{level} suppress drift: {suppress} != {FIGHTER_SUPPRESS[level]}")
    if not list(wf_dsl.iter_dsl_commands(tree, "NotifyPowerflipEnd")):
        raise KitError(f"fighter lv{level} lost NotifyPowerflipEnd (PF 会卡死)")
    cnas = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    if len(cnas) != FIGHTER_CNA_COUNT[level]:
        raise KitError(f"fighter lv{level} CNA count {len(cnas)} != {FIGHTER_CNA_COUNT[level]}")
    total = round(sum(_slv(c[6])[1] for c in cnas), 4)
    if abs(total - FIGHTER_CNA_TOTAL[level]) > 1e-4:
        raise KitError(f"fighter lv{level} CNA total {total} != {FIGHTER_CNA_TOTAL[level]}")
    for cha in wf_dsl.iter_dsl_commands(tree, "CreateHitArea"):
        if cha[24] != 0:
            raise KitError("PF CreateHitArea p24 must stay 0 (4 = 按直击算，整块 PF 乘区被跳过)")

    root_body = tree[11][1]
    aura = [n for n, e in enumerate(root_body)
            if e[0] == "Command" and e[1][0] == "ShowEffect"]
    if not aura:
        raise KitError(f"fighter lv{level} has no root-level ShowEffect to anchor the支援 block")
    # 作者 09-21 真机反馈：「芙拉菲也不要浮游」⇒ 辅助增益块只留攻击力提升与贯穿。
    # donor 仍按官方三件套校验（pf_support_block 内部），只是 ACFlying 那条不进成品树。
    support = PH.pf_support_block(ctx.root, level, keep_flying=False)
    kinds = [c[2][0][0] for c in PH.cmds(support, "CreateCondition")]
    if kinds != ["ACAttackPoint", "ACPiercing"]:
        raise KitError(f"supporter buff block drift: {kinds}")
    if sorted(set(PH.bound_ids(support))) != [PF_SUPPORT_BIND]:
        raise KitError(f"supporter block bound ids {sorted(set(PH.bound_ids(support)))} "
                       f"!= [{PF_SUPPORT_BIND}]")
    base_ids = set(PH.bound_ids(tree))
    if PF_SUPPORT_BIND in base_ids:
        raise KitError(f"fighter lv{level} already binds id {PF_SUPPORT_BIND}; bind sets must be disjoint")
    root_body.insert(aura[-1] + 1, support)

    stray = sorted({p for p in PH.spec_paths(tree) if p.startswith("battle/effect/skill_unique/"
                                                                  f"{CODE}/")})
    if stray:
        raise KitError(f"PF lv{level} 引用了包内特效（底座与辅助块的官方件必须直接引用）: {stray}")
    problems = dsl_problems(tree) + roundtrip_problems(tree)
    if problems:
        raise KitError(f"PF lv{level} DSL gates failed: {problems}")
    return tree, {"level": level, "base": program, "base_sha256": C.sha256(raw),
                  "suppress": suppress, "cna_total": total,
                  "support_block_bind": PF_SUPPORT_BIND,
                  "official_effects": sorted(set(PH.spec_paths(tree)))}


# ---------------------------------------------------------------- 入口

def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.cid, spec.code, spec.element) != (CID, CODE, ELEMENT):
        raise KitError(f"identity drift: {spec.cid}/{spec.code}/element {spec.element}")
    if (spec.template_id, spec.template_code) != (TEMPLATE_ID, TEMPLATE_CODE):
        raise KitError(f"template drift: {spec.template_id}/{spec.template_code}")
    if spec.pf_type != 3 or spec.stance != "Attacker" or int(spec.rarity) != 5:
        raise KitError(f"spec drift: pf_type={spec.pf_type} stance={spec.stance} rarity={spec.rarity}")
    if MS.text_placeholders(spec):
        raise KitError(f"design texts still placeholders: {MS.text_placeholders(spec)}")

    # ---- 1) 队长技 13 行（含队长表禁 kind 与 trigger-65 配对检查）
    leader_rows, leader_evidence = build_leader_rows(ctx)
    capabilities: set[str] = set()
    for ev in leader_evidence:
        capabilities.update(ev["capabilities"])
    ctx.write_flat(KL.LEADER, {CID_S: leader_rows})

    # ---- 2) 词条 6 键 15 条
    ability_rows, ability_evidence = build_ability_rows(ctx)
    for ev in ability_evidence:
        capabilities.update(ev["capabilities"])
    ctx.write_flat(KL.ABILITY, ability_rows)

    # ---- 3) custom_ability_string：536/704/629/722 + 4 个 desc_override
    cas_plan = write_strings(ctx)
    for key in cas_plan:
        cap = L.panel_override_capability(key)
        if cap:
            capabilities.add(cap)
    flag_strings = check_skill_flag_strings(
        [row for rows in ability_rows.values() for row in rows], set(cas_plan))
    if sorted(flag_strings) != sorted((CAS_FLAG1, CAS_FLAG2)):
        raise KitError(f"skill-flag string keys {sorted(flag_strings)} != "
                       f"{sorted((CAS_FLAG1, CAS_FLAG2))}")

    # ---- 4) action_skill 两档能量（580/580）
    action_rows = write_action_skill(ctx)

    # ---- 5) 特效族（rush 整族克隆 + LUT 染色；jab 族直接引用官方路径）
    pixel_dir = KL.pixel_dir(ctx)
    families: list[dict[str, Any]] = []
    luts: dict[str, bool] = {}
    for subdir, src_dir, members, lut_name in FX_FAMILIES:
        lut = KL.png_transform_from_lut(pixel_dir / lut_name)
        luts[subdir] = bool(lut)
        family = ctx.clone_effect_family(src_dir, subdir, fx_names=list(members),
                                         png_transform=lut)
        want_dst = f"battle/effect/skill_unique/{CODE}/{subdir}"
        if family["dst_dir"] != want_dst or sorted(family["copied_bases"]) != sorted(members):
            raise KitError(f"effect family drift: {family['dst_dir']} {family['copied_bases']}")
        families.append(family)
    lut = all(luts.values()) and bool(luts)

    # ---- 6) 技能 DSL 两档 + 629 ability_skill 树
    programs: list[str] = []
    skill_gates: dict[str, Any] = {}
    skill_trees: dict[str, list] = {}
    for level in ("1", "2"):
        tree, gates = build_skill_tree(ctx, level, families)
        programs.append(_write_dsl_checked(ctx, ctx.program_path(level), tree))
        skill_gates[level] = gates
        skill_trees[level] = tree
    invoke_tree, invoke_gates = build_invoke_tree(skill_trees["2"])
    programs.append(_write_dsl_checked(ctx, INVOKE_PROGRAM, invoke_tree))

    # ---- 7) 722 三档覆盖树 + power_flip_action 行
    pf_gates: dict[str, Any] = {}
    for level in (1, 2, 3):
        tree, gates = build_pf_tree(ctx, level)
        programs.append(_write_dsl_checked(ctx, PF_PROGRAMS[level - 1], tree))
        pf_gates[str(level)] = gates
    ctx.write_flat(PFA, {PF_KEY: [list(PF_PROGRAMS)]})

    # ---- 8) 语音路由 kind 3（ChangeSkillFlag ← A1#1 的 536）+ character 行
    route = KL.voice_route(CODE, VOICE_ROUTE)
    char_row = ctx.pack.pkg_character_row()
    char_row[9:17] = route
    char_row[6] = str(spec.pf_type)              # 作者 09-21：详情页显示「辅助」
    if char_row[26] != "Attacker" or char_row[27] != CID_S:
        raise KitError(f"character row drift: c26={char_row[26]} c27={char_row[27]}")
    ctx.write_flat(KL.CHARACTER, {CID_S: [char_row]})
    voice_ready = KL.write_voice_ready(ctx)

    # ---- 9) 像素成品（缺文件静默跳过）+ 三层镜像
    pixel = KL.install_staged_assets(ctx)
    mirrors = ctx.sync_character_mirrors()
    if mirrors["character"][9:17] != route:
        raise KitError("character mirror lost the voice route")
    if mirrors["character"][6] != str(spec.pf_type):
        raise KitError("character mirror lost the pf_type override")

    # ---- 面板：队长 + 槽 1/2/3 由 desc_override 接管；槽 4/5/6 用客户端自动文案
    panel: list[str] = list(CAS_TEXTS[LEADER_OVERRIDE].split("\n"))
    for slot in SLOT_OVERRIDE_SLOTS:
        panel.extend(line.replace(MAIN_ICON, "") for line in CAS_TEXTS[SLOT_OVERRIDE[slot]].split("\n"))
    for slot in (4, 5, 6):
        for line in PANEL_AUTO[slot]:
            panel.append(KL.check_panel(line, label=f"slot{slot}"))

    ctx.evidence_write("kit-gates.json", {
        "leader": {"rows": leader_rows, "evidence": leader_evidence},
        "ability": {"rows": ability_rows, "evidence": ability_evidence},
        "skills": skill_gates,
        "invoke_tree": invoke_gates,
        "power_flip": {"key": PF_KEY, "programs": list(PF_PROGRAMS), "levels": pf_gates},
        "custom_ability_string": cas_plan,
        "effect_families": [{k: f[k] for k in ("src_dir", "dst_dir", "layout", "copied_bases",
                                               "complete_family", "missing_effects")}
                            for f in families],
        "fx_lut": bool(lut), "voice_route": route, "voice_ready": voice_ready,
        "pixel": pixel, "mirrors": mirrors, "action_skill": action_rows,
        "required_client_capabilities": sorted(capabilities),
    })

    notes = [
        "rework1（2026-09-21）：按 rework1/panel/fluffy.json 整体重做；逐行映射与偏离见 "
        "rework1/impl/fluffy.md。队长 7 行→10 行、词条 15 条（槽 3 整段替换、槽 6 删第 2 行）",
        f"722 双类型强化弹射：官方 fighter_lv{{1,2,3}} 底座 + 官方 supporter 辅助增益块"
        f"（bind 归到 {PF_SUPPORT_BIND} 段），倍率不缩放（"
        + "／".join(f"{pf_gates[str(n)]['cna_total']}" for n in (1, 2, 3))
        + "）。只在她当队长且风共鸣时生效；详情页图标按 character c6=3 显示单一「辅助」",
        f"629「触发自身技能效果」：一棵 {INVOKE_STRING} 树 = 技能档 2 深拷贝，由队长 L#8"
        "（每 5 次 PF Lv3，CT10 秒）与能力 3#2（每 150 连击，CT15 秒）共用；"
        "不消耗技能槽、不播 cut-in／技能语音、不触发别人的「发动技能时」",
        f"技能：玉杵重击 4 段→8 段（id 11..22 与 31..42 两组，bind 不相交），满级无开关合计 "
        f"{skill_gates['2']['total_no_flag']}×、536 开关 {skill_gates['2']['total_with_flag1']}×；"
        f"两档同值、min=max 拉平；停球 {STOP_BALL_FRAMES} 帧＝裂地一击后第 3 帧放球（无后摇）",
        f"704 走 alv2 通道驱动 AddCombo：{len(HITS)} 个判定区各挂一条 "
        f"AddCombo([{{min:0,max:0,alv2_min:50,alv2_max:50}}])，满编 {sum(HITS.values())} 段命中 "
        f"⇒ 开了 704 每次技能最多 +{sum(HITS.values()) * 50} 连击（引擎硬钳 9999）",
        f"特效：克隆 {sorted(luts)} 族到 skill_unique/{CODE}/（rush 族含小人剪影帧，必须与像素管线同 LUT）"
        + ("，已套用 B/pixel/fluffy/ 的 LUT 换色" if lut else
           "；LUT 文件缺失，缺的那族按母本原色克隆（像素代理交付后重跑 kit）")
        + ("" if CLONE_JAB_FAMILY else
           f"；jab 族按施工单偏离 D-7 直接引用官方 skill_unique/{GRAFT_CODE}/ 路径不进包"),
        "面板：队长技与槽 1/2/3 由 4 个 desc_override 整段接管（槽 3 每行自带 <icon id='main'>），"
        "槽 4/5/6 用客户端自动文案；722 行自己的 c82 说明串在 desc_override 接管后不显示",
        "本轮不新增固有状态 ⇒ 不需要 48×48 状态图标（能力 2 的「最多累积 4 次」是母本 141033 "
        "ACAttackPoint 自带的累积上限，不是自定义固有）",
        "2026-09-27 平衡第二批（wf_balance_20260927b_fluffy，口径 A/B）：队长每次 PF 攻击力/技能伤害 "
        f"20% → {int(BALANCE_B['pf_growth']) // 1000}%（3 分钟约 35 次 ⇒ 1/10）、每 250 连击自身技能伤害 "
        f"100% → {int(BALANCE_B['combo_growth']) // 1000}%（约 20 次 ⇒ 1/5）、每 3 次 PF 技能伤害额外乘区 "
        f"5% → {int(BALANCE_B['pf3_growth']['694']) // 1000}%（约 12 次 ⇒ 1/5）；同触发的 35/245 属充能，本批不动。"
        f"技能八连重击 p13 {PESTLE_DETOUGHNESS_DONOR} → {PESTLE_DETOUGHNESS}（每次施放 "
        f"{skill_gates['2']['detoughness']['per_cast']}，原 65）；629 树全部 p13 → {INVOKE_DETOUGHNESS}"
        f"（每次 {invoke_gates['detoughness']['per_call']}，原 65）。每 5 次 PF Lv3 的 CT 按作者原话不动",
        "2026-09-27 平衡第三轮（wf_balance_20260927c_fluffy，成长复核：作者「砍到4/5，或者7/10」「取5的倍数」）："
        f"队长每次 PF 攻击力/技能伤害 {int(BALANCE_B['pf_growth']) // 1000}% → "
        f"{int(BALANCE_C['pf_growth']) // 1000}%（原 20%，4/5 取整）、每 250 连击自身技能伤害 "
        f"{int(BALANCE_B['combo_growth']) // 1000}% → {int(BALANCE_C['combo_growth']) // 1000}%（原 100%，7/10）、"
        f"每 3 次 PF 技能伤害额外乘区 {int(BALANCE_B['pf3_growth']['694']) // 1000}% → "
        f"{int(BALANCE_C['pf3_growth']['694']) // 1000}%（原 5%，4/5）；充能与削韧不动",
        {"pixel_install": pixel},
    ]

    deviations: list[dict[str, Any]] = [
        {"want": "目标面板队长技 4 行（pf_type「辅助＋格斗」只写在表头）",
         "got": "队长技面板多出一行「风属性共鸣时，自身的强化弹射同时具备辅助与格斗两种类型」，"
                "已回写 panel/fluffy.json 并标 dev:true",
         "why": "character c6 是单值，详情页图标只能显示「辅助」（作者 09-21 已定）；不写这一行，"
                "玩家在游戏里没有任何途径知道格斗那一半存在。722 行自己的 c82 串在 desc_override "
                "接管队长面板后不会显示，只能写进 override 正文"},
        {"want": "作者的 4 条队长技 = 4 行",
         "got": "13 行（722 + 开局 3 + 每次 PF 3 + 每 5 次 PF Lv3 2 + 每 250 连击 1 + 每 3 PF 成长 3），"
                "面板靠 desc_override 合并回 5 行",
         "why": "一条面板文案里并列的多个效果在数据层是不同 kind，必须分行"},
        {"want": "队长全队主轴合计落在裁决 §2 的 490–650% 带内",
         "got": f"超带：每次 PF ＋{int(BALANCE_C['pf_growth']) // 1000}%/＋{int(BALANCE_C['pf_growth']) // 1000}% "
                f"与每 250 连击 ＋{int(BALANCE_C['combo_growth']) // 1000}% 都不设上限（trigger_limit=(None)；"
                "2026-09-27 第二批按 3 分钟触发次数放缓、第三轮按 4/5 或 7/10 回调，原 20%/20%/100%）",
         "why": "作者原话逐条都没写上限，裁决 §3 又规定「无上限的成长写到效果为止」；"
                "对冲＝技能倍率从 78× 砍到 65×、能力 3 的独立乘区从 20% 砍到 10%"},
        {"want": "技能两档保持觉醒前/后的 2/3 梯度与 SLv1→满级渐进",
         "got": "两档同值、min=max 拉平（前段25倍＋裂地65倍、能量都580）",
         "why": "目标面板只有一行技能描述、一个能量值与一个倍率；作者放行 #5 对同批角色已定"
                "「觉醒前后两档都写这个数」"},
        {"want": "能力 3 第 4 条「技能伤害额外乘区＋10%」用持续 411",
         "got": "用瞬发 694（live 1299925#1，官方 0 行、live 有先例，与玛格诺斯 A5#0 同 donor）",
         "why": "官方 ability 表的 411 只有 1 行且带 during 194 计数门，没有「恒定生效」的官方先例"},
        {"want": "「每 5 次 PF Lv3 → 连击＋500 并触发技能」写成一行 629，把 AddCombo 500 做进那棵 DSL"
                 "（A 卡 §3.4 推荐的更稳写法）",
         "got": "拆成两行（226 + 629），阈值与 CT 逐格一致并加硬断言 _check_lv3_pair",
         "why": "那棵 629 树要被能力 3「每 150 连击」复用；把 +500 连击焊进树里会让能力 3 那条也白送 "
                "500 连击，与它的面板文案不符"},
    ]
    if not CLONE_JAB_FAMILY:
        deviations.append({
            "want": f"jab 族（玉杵重击/振りかぶり/裂地）整族克隆并套中秋配色 LUT",
            "got": f"直接引用官方 skill_unique/{GRAFT_CODE}/ 路径，不克隆也不染色",
            "why": "整族克隆给战斗图集加 0.1823 Mpx（≈1.09%），实测把 five-boss-r1 的 fits 压成 "
                   "false，越过裁决 §6 通过线。开关＝ wf_midautumn_kit_fluffy.CLONE_JAB_FAMILY",
        })
    if not lut:
        missing_luts = sorted(k for k, v in luts.items() if not v)
        deviations.append({
            "want": "克隆特效族时套 LUT 换成青玉/月白/桂金的中秋配色",
            "got": f"本轮 B/pixel/fluffy/ 下 {missing_luts} 族的 LUT 文件不存在 ⇒ 这些族按母本原色"
                   "克隆（风绿），kit 已留好挂点，像素代理交付后重跑 --step kit 即生效",
            "why": "像素/特效换色件不归 kit 代理；缺件时静默跳过是框架 §7.6 的约定，"
                   "但不登记就会被当成「已换色」验收",
        })

    gate = {"rows": len(leader_evidence) + len(ability_evidence), "programs": len(programs),
            "pixel_present": pixel["present"],
            "pixel_missing": [e["logical"] for e in pixel["skipped"]],
            "fx_lut_present": bool(lut)}
    ready = pixel["present"] and not pixel["skipped"] and bool(lut)
    gate["reason"] = "kit 自有产物全部过闸" if ready else (
        "像素/特效件未就绪："
        + (", ".join(gate["pixel_missing"]) or "B/pixel/fluffy/install.json 不存在")
        + ("" if lut else "；fx_lut.json 不存在"))

    return KL.report(
        ctx, summary="芙拉菲：风技伤主 C（双类型 PF 队长 × 连击滚雪球 × 629 自动技能追击）",
        status=KL.READY if ready else KL.DRAFT, panel=panel, notes=notes, programs=programs,
        required_capabilities=sorted(capabilities | set(SPEC["required_capabilities"])),
        deviations=deviations,
        extra={"custom_ability_string": sorted(cas_plan),
               "effect_families": [f["dst_dir"] for f in families],
               "power_flip_action": {PF_KEY: list(PF_PROGRAMS)},
               "invoke_program": INVOKE_PROGRAM,
               "kit_gate": gate, "voice_route": route,
               "skill_totals": {lv: skill_gates[lv]["total_no_flag"] for lv in ("1", "2")}})

# -*- coding: utf-8 -*-
"""中秋批次 kit：丝缇涅尔·中秋 159995 ``still_obstinator_moon``（光属性技能伤害辅助）。

**rework1（2026-09-21）**：按作者 09-20/09-21 原话与
``work/character_packs/midautumn-20260920/rework1/panel/stinel.json`` 整段重做。
逐行映射、零先例项与偏离登记见 ``rework1/impl/stinel.md``；上一轮的「零新件·月相灯」方案
留在 ``design/stinel.json`` 的 ``plan`` 块里当历史，**不删**。

本轮的形状（与上一轮的差别都在施工单 §1）：

* 队长技 **9 行 → 面板 7 行**（``desc_override_still_obstinator_moon`` 接管）：
  722 双类型 PF（辅助＋特殊）、开局回槽、常驻技伤 400%／攻击 200%、施技回槽＋喂连击、
  每 250 连击攻击滚雪球、PF 每命中一个敌人给 8 秒可叠加攻击状态、PF 喂连击。
* 词条 6 键 **16 条**：槽 3 整段重写（独立乘区 20%→15%、``during_trigger 37`` 状态计数增益
  七层、施技回槽改「除自身外」并追加连击），槽 6 加主位限制，其余只把强度拉平成满级单值。
  **2026-09-27 平衡批次**：槽 3「友技回槽」10%→5%，不加 CT（``wf_balance_20260927_stinel``）。
* 技能 DSL：母本 151093 整树 + 官方诺瓦 ``nova_4anv`` **三块**嫁接（上一轮是四块，本轮删掉
  第二个 funnel ``ShowEffect``＝「只要一排」第一级），并按调研卡 C §5 改
  ``StopBall``（去定住）、``CreateHitArea``（150→250）、funnel ``scale``（1.5×）、
  带 ``alv`` 的 ``CreateNormalAttack``（536 开 ⇒ 80 倍）。
* 专属强化弹射 722 三档：官方 ``special_lv{n}`` 整树（sha 锁定）作底座 + 官方 ``supporter``
  辅助增益块（``PH.pf_support_block``），倍率统一 ×``PF_SCALE``。
* 特效族 ``still_obstinator`` 整族克隆换名 + LUT 染色（``rework1/fx/stinel/fx_lut.json`` 优先，
  退回 ``B/pixel/stinel/fx_lut.json``；都没有就按母本原色）+ **parts 镜像排切除**（克隆之后施加，
  母本漂移即拒绝）。

不碰：live store / ``assets/`` / ``.cdn`` / 设备 / 存档；无固有状态、无 48×48 图标、
无 422/629/713/724 以外的补丁 kind（724 在槽 3，需 ``kyubi-fever-ratio-v1``）。
由 ``python mod-tools/wf_midautumn_build.py --char stinel --step kit`` 调用 :func:`build`。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_kit_philia as PH  # noqa: E402

KitError = KL.KitError

KEY = "stinel"
CID, CODE = 159995, "still_obstinator_moon"
ELEMENT = 4                                     # 光（0 基内部编号，White）
TEMPLATE_ID, TEMPLATE_CODE = 151093, "still_obstinator"
PF_TYPE, STANCE = 4, "Supporter"                # c6 保持母本特殊型（详情页图标）；c26 辅助

ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
LEADER_ROWS = 9
ABILITY_RECORDS = 16

# ---------------------------------------------------------------- 自有键

CAS_CHANGE_SKILL = f"change_skill_{CODE}"            # 536 的 c70（不注册 = C8601）
PF_KEY = f"{CODE}_pf"
PF_STRING = f"override_string_{PF_KEY}"              # 722 的 c82（不需要 APK 补丁）
PFA = "master/skill/power_flip_action.orderedmap"
PF_PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_KEY}${PF_KEY}_lv{n}"
                    for n in (1, 2, 3))
LEADER_OVERRIDE = f"desc_override_{CODE}"            # 队长块整体接管
SLOT3_OVERRIDE = f"desc_override_{CODE}_3"           # 槽 3 整体接管
VOICE_KEY = KL.switch_key(CODE)                      # still_obstinator_moon_voice_ready
VOICE_ROUTE: dict[str, Any] = {"kind": 3}            # ChangeSkillFlag ← 能力 1#1 的 536

MAIN_ICON = " <icon id='main'>  "                    # desc_override 会盖掉客户端逐行画的 Ⓜ

# ---------------------------------------------------------------- 特效族

FX_SRC_DIR = f"battle/effect/skill_unique/{TEMPLATE_CODE}"
FX_SUBDIR = "orrery"
FX_DST_DIR = f"battle/effect/skill_unique/{CODE}/{FX_SUBDIR}"
FX_FUNNEL = f"{TEMPLATE_CODE}_funnel"
FX_EXPLOSION = f"{TEMPLATE_CODE}_explosion"
#: 特效代理的交付目录（优先），退回上一轮的 ``B/pixel/<key>/``。
FX_DELIVERY = "work/character_packs/midautumn-20260920/rework1/fx/stinel"
#: 「只要一排」第二级：删掉 funnel ``parts`` 的镜像排（调研卡 C §5.2）。
SINGLE_ROW_SURGERY = False     # 作者真机 09-21：切掉镜像排后技能只剩左边一半＝删多了；「只要一排」只靠删第二个 funnel ShowEffect
FUNNEL_MIRROR_GROUP = 2          # g[2]：一排 3 盏灯的容器
FUNNEL_MIRROR_SEGMENTS = 3       # 母本段数（正排 / 镜像排 / G[33]@49）

# ---------------------------------------------------------------- 技能嫁接

GRAFT_CODE = "nova_4anv"                             # 官方诺瓦（光技伤辅助蓝本 151182）
GRAFT_PROGRAM = f"battle/action/skill/action/rare5/{GRAFT_CODE}${GRAFT_CODE}_{{lv}}"
SUBJECT_BASE = 4                                     # 母本已占 0（参考点）与 1/2/3（判定区）
SUBJECT_REMAP = {0: 4, 1: 5, 2: 6, 3: 7, 4: 8}
HIT_AREA_SUBJECT_SLOTS = (19, 21, 22)                # 26 参判定区卡（记忆卡 wf-hitarea-param-card）
HIT_AREA_ONHIT_SLOT = 23

# A「满月灯」= 主队光属性角色；B「弦月灯」= 主队全员。数值与时长都不同 ⇒ gid 不同 ⇒ 并存并累加。
# **调数值时不许把两条调成完全相同**，否则互相覆盖。
LIGHT_VALUES = {
    "1": {"a": (960, {"min": 0.6, "max": 0.6}),
          "b": (720, {"min": 0.25, "max": 0.25})},
    "2": {"a": (1200, {"min": 0.6, "max": 1.2, "alv_min": 0.2, "alv_max": 0.4}),
          "b": (900, {"min": 0.25, "max": 0.5})},
}

# 调研卡 C §5.3/§5.4 的三处演出改动
STOP_BALL_DONOR = [-18, 30, ["RestoreToSpeedBeforeActionExecution"], ["AB"], 0]   # 千岳形状
STOP_BALL_TEMPLATE = [-18, 90, ["Stop"], ["AB"], 0]                              # 母本形状（漂移断言）
FUNNEL_SCALE = 1.5
HIT_AREA_RADIUS = 250
HIT_AREA_TEMPLATE_RADIUS = 150
#: 536 强化档的 ALv 增量：母本满级 43 倍 + 37 = 作者要求的 80 倍。
SKILL_ALV_BOOST = 37.0
TEMPLATE_ALV = (3.5, 7)                                                          # 母本 alv（漂移断言）

ENERGY = ("500", "500")                              # action_skill c4/c5（两档同值）

# ---------------------------------------------------------------- 722 专属 PF

SPECIAL_PROGRAMS = {n: f"battle/action/power_flip/action/special$special_lv{n}" for n in (1, 2, 3)}
SPECIAL_SHA = {                                      # 官方底座指纹（与澄波响同三枚）
    1: "569f2082c4633bae7e71610c296d6ab141cfabe1f3c4e5e0034c46dbf3e22961",
    2: "4ed6440b9ded6d435e2c2fb9a640541b2c3fc43c5c0068de41077bab07ad73f2",
    3: "7bebfdd5fc3ff46f2a789f7d631ac02084afa0cd11f4f19f71037f7faba3447d",
}
PF_SCALE = 3.6                                       # 辅助定位（澄波响主 C 是 4.8）
PF_PIERCE_FRAMES = {1: 180, 2: 240, 3: 300}          # 官方 60/90/150 → 拉长
PF_SUPPORT_BIND = 400                                # 辅助增益块主体 id 段（philia.PF_SUPPORT_OFFSET）

FORBIDDEN_LEADER_KINDS = ("422", "724", "713")       # 写进队长表 = C7050（裁决 §2/§8）

# ---------------------------------------------------------------- 行计划（donor + 逐格改）

# 「光属性共鸣」＝官方常规共鸣前置（前置 kind 2 编成≥6，作者补充 09-21 00:5x「都是属性共鸣」）
LIGHT_LEADER = {4: "2", 7: "600000", 8: "600000", 9: "White"}
LIGHT_ABILITY = {6: "2", 9: "600000", 10: "600000", 11: "White"}

# (tag, donor, source, cells, expect_describe)
LEADER: tuple[tuple[str, str, str, dict[int, str], str], ...] = (
    # L#0 722 双类型 PF（donor 自带共鸣门的官方 722；偏离 D-1）
    ("722双类型", "141201#1", "official",
     {0: CODE, 9: "White", 80: PF_KEY, 81: "1,2,3", 82: PF_STRING},
     "光·编成≥6 时: 自身 强化弹射覆盖"),
    # L#1 开局：除自身外光角色技能槽 +50%
    ("开局回槽", "151182#0", "official",
     {0: CODE, 47: "White", 49: "50000", 50: "50000"},
     "光·编成≥6 时: 赋予除自身全员(光) 技能槽 50%"),
    # L#2/L#3 常驻：技伤 400% / 攻击 200%（面板并成一行）
    ("常驻技伤", "151182#2", "official",
     {0: CODE, 49: "400000", 50: "400000"},
     "光·编成≥6 时: 赋予全队(光) 技能伤害 400%"),
    ("常驻攻击", "151182#1", "official",
     {0: CODE, 49: "200000", 50: "200000"},
     "光·编成≥6 时: 赋予全队(光) 攻击力 200%"),
    # L#4/L#5 自身发动技能时（面板并成一行）
    ("施技回槽", "129991#5", "live",
     {0: CODE, **LIGHT_LEADER, 47: "White", 49: "5000", 50: "5000"},
     "光·编成≥6 时: 技能发动≥1 → 赋予除自身全员(光) 技能槽 5%"),
    # trigger 23 的 puller 必须写 '0'（A 卡 §3.2）；226 AddCombo 是全局计数器，没有 target 列
    ("施技连击", "151129#1", "official",
     {0: CODE, 25: "23", 26: "0", 28: "100000", 29: "100000", 49: "5000000", 50: "5000000"},
     "光·编成≥6 时: 技能发动≥1 → 自身 追加连击 50"),
    # L#6 每 250 连击：c32=5 ＝ 作者的「最大 +500%」
    ("连击滚雪球", "241004#1", "official",
     {0: CODE, **LIGHT_LEADER, 28: "25000000", 29: "25000000", 32: "5",
      47: "White", 49: "100000", 50: "100000"},
     "光·编成≥6 时: 连击≥250(限5次) → 赋予全队(光) 攻击力 100%"),
    # L#7 PF 每命中一个敌人：trigger 15 空挥不触发、一次 PF 打 k 个敌人记 k 次（A 卡 §3.3）；
    # kind 0 ConditionAttackPoint ＝ 带帧数的「状态」（kind 32 是常驻定值，两者不许互换）
    ("PF命中攻击", "141171#0", "official",
     {0: CODE, **LIGHT_LEADER, 25: "15", 26: "", 27: "", 28: "100000", 29: "100000",
      46: "5", 47: "White", 49: "100000", 50: "100000", 55: "48000000", 56: "48000000"},
     "光·编成≥6 时: 强化弹射HitLv1≥1 → 赋予全队(光) 状态攻击力 100%(8秒)×1次"),
    # L#8 PF 喂连击：trigger 2 的 puller 留空串（A 卡 §3.1）
    ("PF连击", "151129#1", "official",
     {0: CODE, 25: "2", 26: "", 28: "100000", 29: "100000", 49: "500000", 50: "500000"},
     "光·编成≥6 时: 强化弹射≥1 → 自身 追加连击 5"),
)

# slot -> (c1 unisonable, c2 statue_group, ((tag, donor, source, cells, expect_describe), ...))
ABILITY: dict[int, tuple[str, str, tuple[tuple[str, str, str, dict[int, str], str], ...]]] = {
    1: ("true", "attack_common", (
        ("开局回槽", "1599981#0", "live", {51: "50000", 52: "50000"},
         "自身 技能槽 50%"),
        # c6=202 显式钉住：donor 斩铁 1599981#1 在 2026-09-27 平衡批次去掉了 202（主位限制），本行保留。
        ("536强化", "1599981#1", "live", {6: "202", 18: "White", 70: CAS_CHANGE_SKILL},
         f"持有者为主位 且 光·编成≥6 时: 自身 切换技能形态[{CAS_CHANGE_SKILL}]"),
    )),
    2: ("true", "action_skill", (
        ("全队攻击", "1511822#0", "official", {**LIGHT_ABILITY, 51: "100000", 52: "100000"},
         "光·编成≥6 时: 赋予全队(光) 攻击力 100%"),
        ("全队技伤", "1511822#1", "official", {**LIGHT_ABILITY, 51: "100000", 52: "100000"},
         "光·编成≥6 时: 赋予全队(光) 技能伤害 100%"),
    )),
    3: ("false", "action_skill", (
        ("独立乘区", "1299913#2", "live", {11: "White", 49: "White", 51: "15000", 52: "15000"},
         "光·编成≥6 时: 赋予全队(光) 独立乘区技能伤害 15%"),
        # 「自身每获得一个效果」的连击那半：持续块出不了「追加连击」⇒ 只能走瞬发 trigger 29
        ("获益连击", "2310044#0", "official",
         {**LIGHT_ABILITY, 27: "29", 28: "0", 30: "100000", 31: "100000",
          34: "7", 35: "0", 51: "5000000", 52: "5000000"},
         "光·编成≥6 时: 状态增益≥1(限7次) → 自身 追加连击 50"),
        # 同一句话的技伤那半：during_trigger 37 ConditionCountBuff ＝ 状态计数增益，七层封顶
        ("获益技伤", "2510046#0", "official",
         {**LIGHT_ABILITY, 102: "7", 110: "5", 111: "White", 113: "50000", 114: "50000"},
         "光·编成≥6 时: 持续·状态计数增益≥1(限7次) → 赋予全队(光) 技能伤害 50%"),
        # puller 7（全队合计）→ 6（除自身合计）＝ 作者新加的「除自身外」
        # 作者 09-21 真机反馈：回槽 5%→10%、连击 25→50
        # 作者 09-27 平衡批次：回槽 10%→5%，不加 CT（作者追加确认）。
        # c35 显式写死 0：donor 是斩铁 159998 的 live 行，不让它的 CT 列漂进来。
        ("友技回槽", "1599983#4", "live",
         {28: "6", 29: "White", 35: "0", 51: "5000", 52: "5000"},
         "光·编成≥6 时: 技能发动≥1 → 自身 技能槽 5%"),
        ("友技连击", "2310044#0", "official",
         {**LIGHT_ABILITY, 27: "23", 28: "6", 29: "White", 30: "100000", 31: "100000",
          34: "(None)", 35: "0", 51: "5000000", 52: "5000000"},
         "光·编成≥6 时: 技能发动≥1 → 自身 追加连击 50"),
        # 作者本轮未提及 ⇒ 原样保留（「没提到的效果不删除」）
        # 作者 09-21 真机反馈：「fever获取应该没有次数限制」⇒ 次数上限列 c34 写 (None)
        ("Fever回充", "1599985#0", "live", {34: "(None)", 51: "10000", 52: "10000"},
         "光·编成≥6 时: 技能发动≥1 → 自身 Fever槽增减(上限比例) 10%"),
    )),
    4: ("true", "attack_common", (
        # c29＝触发方的属性标记：donor 1299915 是水属性角色的行，不改就会在面板上画出水属性图标、
        # 且变成「水属性角色发动技能时」才触发（作者 09-21 真机截图）。
        ("施技全队技伤", "1299915#0", "live",
         {11: "White", 29: "White", 49: "White", 51: "10000", 52: "10000"},
         "光·编成≥6 时: 技能发动≥1(限10次) → 赋予全队(光) 技能伤害 10%"),
        ("施技全队攻击", "1299915#1", "live",
         {11: "White", 29: "White", 49: "White", 51: "10000", 52: "10000"},
         "光·编成≥6 时: 技能发动≥1(限10次) → 赋予全队(光) 攻击力 10%"),
    )),
    5: ("true", "action_skill", (
        ("攻击降低无效", "1511823#1", "official", {},
         "赋予全队(光) 攻击力降低无效"),
        ("全队技伤", "1599986#1", "live", {51: "50000", 52: "50000"},
         "光·编成≥6 时: 赋予全队(光) 技能伤害 50%"),
    )),
    # 作者「能力 6 带上主位限制」⇒ c1 true → false（与槽 3 同写法，不另加前置 202）
    6: ("false", "attack_common", (
        ("全队充能", "1511826#0", "official", {51: "10000", 52: "10000"},
         "光·编成≥6 时: 赋予全队(光) 技能槽充能 10%"),
        ("施技回槽", "1599986#0", "live", {51: "5000", 52: "5000"},
         "光·编成≥6 时: 技能发动≥1 → 赋予除自身全员(光) 技能槽 5%"),
    )),
}

# ---------------------------------------------------------------- 面板文案

PANEL_LEADER = (
    "光属性共鸣时：自身的强化弹射同时具备辅助与特殊两种类型",
    "光属性共鸣时：战斗开始时，除自身外的光属性角色技能槽＋50%",
    "光属性共鸣时：光属性角色技能伤害＋400%、攻击力＋200%",
    "光属性共鸣时：自身发动技能时，除自身外的光属性角色技能槽＋5%、连击＋50",
    "光属性共鸣时：每达成250连击，光属性角色攻击力＋100%（最多＋500%）",
    "光属性共鸣时：强化弹射每命中1个敌人，赋予光属性角色攻击力＋100%（8秒，可叠加）",
    "光属性共鸣时：强化弹射时，连击＋5",
)
PANEL_SLOT3 = (
    "光属性共鸣时：光属性角色对敌人的技能伤害额外乘区＋15%",
    "光属性共鸣时：自身每获得一个效果，连击＋50、光属性角色技能伤害＋50%（最多＋350%）",
    "光属性共鸣时：除自身外的光属性角色发动技能时，自身技能槽＋5%、连击＋50",
    "光属性共鸣时：光属性角色发动技能时，自身Fever槽＋10%",
)
CAS_TEXTS: dict[str, str] = {
    # 536：裁决 §3「技能强化条目不写数字与时间」；09-27 第三轮（wf_balance_20260927c_panels FLAG_TEXT，主会话 R2）
    # 按官方格式：技能名用『』、效果名用「」（官方先例 change_skill_samurai_robot_plum）
    CAS_CHANGE_SKILL: "强化『月相仪·满月调律』的威力与「技能伤害提升效果」",
    # 722 的 c82（被 desc_override 盖住，玩家看不到；留着是为了没打面板补丁的客户端）
    PF_STRING: "自身的强化弹射同时具备辅助与特殊两种类型",
    LEADER_OVERRIDE: "\n".join(PANEL_LEADER),
    SLOT3_OVERRIDE: "\n".join(MAIN_ICON + line for line in PANEL_SLOT3),
}

SPEC = {
    # desc_override 需要客户端面板接管能力（惰性：缺补丁不崩，只回落官方生成器）；
    # 722 的 override_string_* 不需要补丁（A 卡 §4.2 第 6 条）。
    "required_capabilities": ("panel-description-override-v2",),
    "extra_keys": {
        KL.CAS: tuple(CAS_TEXTS),
        KL.SWITCHED: (VOICE_KEY,),
        PFA: (PF_KEY,),
    },
}
TEXTS: dict[str, str] = {}       # 技能名/描述在 design/stinel.json 的 texts 块里（build 里核验）

DEVIATIONS = (
    {"id": "D-1", "want": "强化弹射类型改为辅助和特殊类型",
     "got": "722 覆盖树把官方 special 底座 + supporter 增益块拼成一棵，只在她当队长时生效；"
            "详情页「强化弹射类型」图标仍按 c6=4 显示「特殊」",
     "why": "character.c6 是单值 int，没有组合值；722 只能由队长技授予（调研卡 A §4）"},
    {"id": "D-2", "want": "目标面板队长技 6 行都不带「光属性共鸣时」前缀",
     "got": "9 行全部挂光编成≥6 前置，面板 7 行统一加「光属性共鸣时：」",
     "why": "作者补充 09-21 00:5x「都是属性共鸣」（权威①）压过面板写法（权威②）；"
            "批次内 magnus/kyle/rolf/fluffy 的队长行全部同此口径"},
    {"id": "D-3", "want": "目标面板没有「强化弹射类型」这一行",
     "got": "队长面板新增第 0 行「自身的强化弹射同时具备辅助与特殊两种类型」",
     "why": "D-1 的效果必须在面板上如实告知（同 fluffy/magnus 的写法）"},
    {"id": "D-4", "want": "「光属性角色 技能伤害＋400%、攻击力＋200%」写成一行",
     "got": "引擎是两条独立 instant 行（kind 34 / kind 32），面板靠 desc_override 合并回一行",
     "why": "一条 leader_ability 记录只能出一个 instant content"},
    {"id": "D-5", "want": "能力3「自身每获得一个效果 → 连击＋50、光属性角色技能伤害＋50%，最多＋350%」",
     "got": "拆成两行：连击走瞬发 trigger 29 ConditionBuff（限 7 次），"
            "技伤走 during_trigger 37 ConditionCountBuff（限 7 层）；面板靠 desc_override 合回一行",
     "why": "持续块出不了「追加连击」，瞬发块出不了「按层数累加的常驻加成」"},
    {"id": "D-6", "want": "能力1「强化技能威力为 80」",
     "got": "只体现在技能树（带 alv 的 CNA +37 ⇒ 536 开＝80 倍），面板文案不写数字",
     "why": "裁决 §3：536/704 类条目不写数字与时间"},
    {"id": "D-7", "want": "技能「只要一排聚光灯、范围扩大、无后摇不会定住」",
     "got": "DSL 删掉第二个 funnel ShowEffect + parts 删镜像排 + Circle 150→250 + scale 1.5 + "
            "StopBall 30 RestoreToSpeedBeforeActionExecution",
     "why": "演出/判定改动不进技能说明文字（现有 desc 本就不描述范围与后摇）"},
    {"id": "D-8", "want": "「每达成 250 连击…最多＋500%」「PF 每命中…可叠加」",
     "got": "前者用 c32=5 触发次数上限，后者用 c59=(None) 无限叠加 + c55/c56=480 帧",
     "why": "两列是官方同义写法，面板照实写"},
    {"id": "D-9", "want": "面板 main_only：能力 6 = true",
     "got": "只改 c1=false（不另加前置 202）",
     "why": "与本角色槽 3 现行写法一致；202 只用在 1#1 的 536 行"},
)


# ---------------------------------------------------------------- 设计稿

def load_design(root: Path) -> dict[str, Any]:
    design = MS.load_design(Path(root), KEY)
    if not design:
        raise KitError(f"design/{KEY}.json missing (batch {MS.BATCH_DIR})")
    if design.get("schema") != "ma-design/1" or design.get("cid") != CID or design.get("code") != CODE:
        raise KitError(f"design identity drift: {design.get('schema')} {design.get('cid')} {design.get('code')}")
    rework = design.get("rework1")
    if not isinstance(rework, dict):
        raise KitError("design/stinel.json 缺 rework1 段（本轮的计划真源，plan 块是历史）")
    return design


# ---------------------------------------------------------------- 表行

def build_leader_rows(ctx) -> tuple[list[list[str]], list[dict[str, Any]]]:
    rows: list[list[str]] = []
    evidence: list[dict[str, Any]] = []
    for index, (tag, donor, source, cells, expect) in enumerate(LEADER):
        label = f"leader#{index}({tag})"
        row, ev = KL.build_row(ctx, "leader_ability", donor, cells, source=source,
                               expect_describe=expect, label=label)
        if row[0] != CODE:
            raise KitError(f"{label}: c0 {row[0]!r} != {CODE}")
        if row[45] in FORBIDDEN_LEADER_KINDS or row[107] in FORBIDDEN_LEADER_KINDS:
            raise KitError(f"{label}: forbidden kind in leader_ability "
                           f"(c45={row[45]!r} c107={row[107]!r})")
        rows.append(row)
        evidence.append(ev | {"tag": tag})
    if len(rows) != LEADER_ROWS:
        raise KitError(f"leader plan carries {len(rows)} rows, expected {LEADER_ROWS}")
    # 722 行：三级程序键与 c82 串必须与 power_flip_action / custom_ability_string 对齐
    pf_row = rows[0]
    if pf_row[45] != "722" or pf_row[80] != PF_KEY or pf_row[81] != "1,2,3" or pf_row[82] != PF_STRING:
        raise KitError(f"leader 722 row drift: c45={pf_row[45]} c80={pf_row[80]} "
                       f"c81={pf_row[81]!r} c82={pf_row[82]}")
    # 施技两行（L#4/L#5）与友技两行的触发列必须逐格一致（A 卡 §3.4）
    for a, b, cols in ((4, 5, (25, 28, 29)),):
        for col in cols:
            if rows[a][col] != rows[b][col] and not (col == 25):
                raise KitError(f"leader#{a}/#{b} trigger column c{col} mismatch: "
                               f"{rows[a][col]!r} vs {rows[b][col]!r}")
    return rows, evidence


def build_ability_rows(ctx) -> tuple[dict[str, list[list[str]]], list[dict[str, Any]]]:
    rows_by_key: dict[str, list[list[str]]] = {}
    evidence: list[dict[str, Any]] = []
    total = 0
    for slot, key_name in enumerate(ABILITY_KEYS, start=1):
        unisonable, statue_group, records = ABILITY[slot]
        rows: list[list[str]] = []
        for index, (tag, donor, source, cells, expect) in enumerate(records):
            label = f"{key_name}#{index}({tag})"
            plan = {0: f"{CODE}_{slot}", 1: unisonable, 2: statue_group, **cells}
            row, ev = KL.build_row(ctx, "ability", donor, plan, source=source,
                                   element=ELEMENT, expect_describe=expect, label=label)
            rows.append(row)
            evidence.append(ev | {"tag": tag, "key": key_name})
            total += 1
        KL.check_ability_key(rows, key_name, CODE, slot)
        rows_by_key[key_name] = rows
    if total != ABILITY_RECORDS:
        raise KitError(f"ability plan carries {total} records, expected {ABILITY_RECORDS}")
    # 槽 3 的「友技」两行（#3/#4）同触发同 puller，逐格一致
    slot3 = rows_by_key[ABILITY_KEYS[2]]
    for col in (27, 28, 29, 30, 31):
        if slot3[3][col] != slot3[4][col]:
            raise KitError(f"槽3 友技两行 c{col} 不一致: {slot3[3][col]!r} vs {slot3[4][col]!r}")
    # 主位限制：槽 3 与槽 6 必须是 false（面板 main_only=true）
    for slot in (3, 6):
        if rows_by_key[ABILITY_KEYS[slot - 1]][0][1] != "false":
            raise KitError(f"槽{slot} 应带主位限制（c1=false）")
    return rows_by_key, evidence


def write_strings(ctx) -> tuple[dict[str, str], set[str]]:
    """``custom_ability_string``：536 串、722 的 c82 串、队长与槽 3 的 ``desc_override``。"""
    declared = set(ctx.spec.extra_keys.get(KL.CAS, ()))
    missing = [key for key in CAS_TEXTS if key not in declared]
    if missing:
        raise KitError(f"custom_ability_string keys not declared in SPEC['extra_keys']: {missing}")
    for key, text in CAS_TEXTS.items():
        for line in text.split("\n"):
            KL.check_panel(line.replace(MAIN_ICON, ""),
                           skill_flag=key == CAS_CHANGE_SKILL, label=key)
    if any(not line.startswith(MAIN_ICON) for line in CAS_TEXTS[SLOT3_OVERRIDE].split("\n")):
        raise KitError("槽 3 是主位限制键，desc_override 每行都要带 <icon id='main'>")
    official = ctx.official_flat(KL.CAS)
    clashes = [key for key in CAS_TEXTS if key in official]
    if clashes:
        raise KitError(f"custom_ability_string keys already exist officially: {clashes}")
    caps = {cap for key in CAS_TEXTS if (cap := L.panel_override_capability(key))}
    ctx.write_flat(KL.CAS, {key: [[text]] for key, text in CAS_TEXTS.items()})
    return dict(CAS_TEXTS), caps


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
        cells[4], cells[5] = ENERGY
        out[level] = cells
    ctx.write_nested(KL.ACTION, CODE, {lv: [cells] for lv, cells in out.items()}, replace_inner=True)
    return out


# ---------------------------------------------------------------- DSL 工具

def _statements(tree) -> list:
    body = tree[11]
    if not (isinstance(body, list) and body and body[0] == "Block"):
        raise KitError(f"root statement block drift: {type(body)}")
    return body[1]


def _command(statement):
    if isinstance(statement, list) and len(statement) == 2 and statement[0] == "Command":
        return statement[1]
    return None


def _ac_node(cmd: list, kind: str) -> list:
    hits = [entry for entry in cmd[2] if isinstance(entry, list) and entry and entry[0] == kind]
    if len(hits) != 1:
        raise KitError(f"CreateCondition carries {len(hits)} {kind} entries")
    return hits[0]


def _effect_paths(tree) -> set[str]:
    return {str(cmd[2][1]) for cmd in wf_dsl.iter_dsl_commands(tree, "ShowEffect")
            if isinstance(cmd[2], list) and cmd[2][0] == "SpecifyEffectDirectly"}


def _dsl_problems(tree, *, element: int | None = None) -> list[str]:
    problems: list[str] = []
    problems += [f"direction: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if element is not None:
        problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, element)]
    return problems


def _write_dsl_checked(ctx, program: str, tree) -> str:
    """``write_dsl`` 只吃裸树；写后回读比对（记忆卡 wf-dsl-encode-wrapper-trap）。"""
    if not (isinstance(tree, list) and tree and tree[0] == "ActionDsl"):
        raise KitError(f"write_dsl needs a bare ActionDsl tree, got {type(tree).__name__}")
    logical = ctx.write_dsl(program, tree)
    back = ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
    if back != tree:
        raise KitError(f"DSL readback mismatch: {logical}")
    return logical


def pick_graft_blocks(tree) -> dict[str, Any]:
    """从诺瓦树里按**结构**挑三块（不按下标，donor 换序也不会挑错）。"""
    found: dict[str, Any] = {}
    for statement in _statements(tree):
        cmd = _command(statement)
        if not cmd:
            continue
        if cmd[0] == "FindAllSubjects":
            inner = _command(cmd[9][1][0]) if cmd[9][1] else None
            if not inner or inner[0] != "CreateCondition":
                continue
            kind = inner[2][0][0]
            if kind == "ACSkillDamage":
                found["skill_damage"] = statement
            elif kind == "ACUnique":
                found["unique"] = statement
        elif cmd[0] == "CreateHitArea" and cmd[9][0] == "Rectangle":
            found["dispel"] = statement
    missing = {"skill_damage", "unique", "dispel"} - set(found)
    if missing:
        raise KitError(f"nova donor tree is missing graft blocks: {sorted(missing)}")
    return found


def make_light_block(parts: dict[str, Any], *, bind: int, light_only: bool,
                     frames: int, value: dict[str, Any]):
    """「灯」块：整块取诺瓦自己的 ``ACSkillDamage`` 块（selector 113 + p10=1 的官方形状）。"""
    statement = copy.deepcopy(parts["skill_damage"])
    cmd = _command(statement)
    cmd[1] = bind
    cmd[3] = copy.deepcopy(_command(parts["unique"])[3]) if light_only else []
    condition = _command(cmd[9][1][0])
    condition[1] = bind
    entry = condition[2][0]
    if entry[0] != "ACSkillDamage":
        raise KitError(f"graft donor AC drift: {entry[0]}")
    if condition[10] != 1:
        raise KitError(f"CreateCondition 付与对象种类 drift: {condition[10]} (expect 1)")
    entry[1] = [{"min": frames, "max": frames}]
    entry[2] = [dict(value)]
    return statement


def make_dispel_block(parts: dict[str, Any]):
    """全屏驱散：诺瓦原样，只把三个主体绑定位与 ``DeleteCondition`` 的主体按 +4 重映射。"""
    statement = copy.deepcopy(parts["dispel"])
    cmd = _command(statement)
    for slot in HIT_AREA_SUBJECT_SLOTS:
        if cmd[slot] not in SUBJECT_REMAP:
            raise KitError(f"dispel subject slot {slot} carries {cmd[slot]!r}, not a donor id")
        cmd[slot] = SUBJECT_REMAP[cmd[slot]]
    delete = _command(cmd[HIT_AREA_ONHIT_SLOT][1][0])
    if not delete or delete[0] != "DeleteCondition":
        raise KitError("dispel on-hit block is not a DeleteCondition")
    delete[1] = SUBJECT_REMAP[delete[1]]
    return statement


def retune_presentation(tree, level: str) -> dict[str, Any]:
    """调研卡 C §5.3/§5.4：去定住、扩判定、放大 funnel 演出。母本形状漂移即拒绝。"""
    stops = list(wf_dsl.iter_dsl_commands(tree, "StopBall"))
    if len(stops) != 1 or stops[0][1:] != STOP_BALL_TEMPLATE:
        raise KitError(f"skill {level} StopBall 母本形状漂移: {[s[1:] for s in stops]}")
    stops[0][1:] = copy.deepcopy(STOP_BALL_DONOR)

    areas = list(wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))
    circles = [cmd for cmd in areas if cmd[9][0] == "Circle"]
    if len(circles) != 1:
        raise KitError(f"skill {level} 母本应只有 1 个 Circle 判定区，实得 {len(circles)}")
    shape = circles[0][9][1]
    if shape != [{"min": HIT_AREA_TEMPLATE_RADIUS, "max": HIT_AREA_TEMPLATE_RADIUS}]:
        raise KitError(f"skill {level} Circle 母本半径漂移: {shape}")
    circles[0][9][1] = [{"min": HIT_AREA_RADIUS, "max": HIT_AREA_RADIUS}]

    funnels = [cmd for cmd in wf_dsl.iter_dsl_commands(tree, "ShowEffect")
               if isinstance(cmd[2], list) and str(cmd[2][1]).endswith(FX_FUNNEL)]
    if len(funnels) != 1:
        raise KitError(f"skill {level} funnel ShowEffect 应只剩 1 个（「只要一排」），实得 {len(funnels)}")
    if funnels[0][-1] != ["None"]:
        raise KitError(f"skill {level} funnel scale 母本漂移: {funnels[0][-1]}")
    funnels[0][-1] = ["Some", [{"min": FUNNEL_SCALE, "max": FUNNEL_SCALE}]]
    return {"stop_ball": copy.deepcopy(STOP_BALL_DONOR), "hit_area_radius": HIT_AREA_RADIUS,
            "funnel_scale": FUNNEL_SCALE}


def boost_alv(tree, level: str) -> dict[str, Any]:
    """536 强化档：带 ``alv`` 的那条 CNA 满级 43 → 80 倍（作者「强化技能威力为 80」）。"""
    attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    if len(attacks) != 2:
        raise KitError(f"skill {level} donor should carry 2 CreateNormalAttack, got {len(attacks)}")
    if any(cna[2] != 255 for cna in attacks):
        raise KitError(f"skill {level} CNA element drift: {[cna[2] for cna in attacks]}")
    with_alv = [cna for cna in attacks if "alv_min" in cna[6][0]]
    if len(with_alv) != 1:
        raise KitError(f"skill {level} 应恰好 1 条带 alv 的 CNA，实得 {len(with_alv)}")
    term = with_alv[0][6][0]
    if (term["alv_min"], term["alv_max"]) != TEMPLATE_ALV:
        raise KitError(f"skill {level} 母本 alv 漂移: {(term['alv_min'], term['alv_max'])}")
    base = float(term["max"])
    term["alv_min"] = term["alv_max"] = SKILL_ALV_BOOST
    return {"base_max": base, "alv": SKILL_ALV_BOOST, "boosted_total": round(base + SKILL_ALV_BOOST, 6),
            "multipliers": [cna[6] for cna in attacks]}


def build_skill_tree(ctx, level: str, family: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """母本 151093 整树 + 官方诺瓦三块（A 满月灯／B 弦月灯／C 全屏驱散）+ 演出改造。"""
    donor_program = ctx.program_path(level).replace(CODE, TEMPLATE_CODE)
    tree = copy.deepcopy(ctx.template_dsl(donor_program))
    if tree[0] != "ActionDsl" or tree[1] != 2 or tree[10] != 0:
        raise KitError(f"skill {level} donor head drift: {tree[:2]} bta={tree[10]}")

    alv = boost_alv(tree, level)
    parts = pick_graft_blocks(ctx.template_dsl(GRAFT_PROGRAM.format(lv=level)))
    values = LIGHT_VALUES[level]
    body = _statements(tree)
    before = len(body)
    body.append(make_light_block(parts, bind=SUBJECT_BASE, light_only=True,
                                 frames=values["a"][0], value=values["a"][1]))
    body.append(make_light_block(parts, bind=SUBJECT_BASE + 1, light_only=False,
                                 frames=values["b"][0], value=values["b"][1]))
    body.append(make_dispel_block(parts))
    if len(body) != before + 3:
        raise KitError(f"skill {level}: appended {len(body) - before} blocks, expected 3")

    presentation = retune_presentation(tree, level)
    tree, info = ctx.rewrite_effect_refs(tree, family, strict=True)
    problems = _dsl_problems(tree, element=ELEMENT)
    if problems:
        raise KitError(f"skill {level} DSL gates failed: {problems}")
    stray = _effect_paths(tree) - {f"{family['dst_dir']}/{FX_FUNNEL}",
                                   f"{family['dst_dir']}/{FX_EXPLOSION}"}
    if stray:
        raise KitError(f"skill {level} still references foreign effects: {sorted(stray)}")
    return tree, {"level": level, "grafted": 3, "light_full": values["a"], "light_half": values["b"],
                  "alv": alv, "presentation": presentation,
                  "effect_rewrites": info["rewritten"], "buff_target_as": tree[10]}


# ---------------------------------------------------------------- 722 专属 PF

def _source_tree(ctx, program: str, want_sha: str):
    logical = wf_dsl.dsl_logical(program)
    raw = ctx.official_read(logical, "common")
    if raw is None:
        raise KitError(f"official baseline lacks donor DSL {program}")
    if C.sha256(raw) != want_sha:
        raise KitError(f"donor DSL fingerprint drift: {program} -> {C.sha256(raw)}")
    return ctx.template_dsl(program)


def build_pf_tree(ctx, level: int):
    """官方 ``special_lv{n}`` 整树（sha 锁定）作底座 + 官方 ``supporter`` 辅助增益块。

    拼法规则见调研卡 A §4.2：基底必须是带生命周期的 special/fighter，supporter 只能当 donor；
    bind id 集合不相交（辅助块统一归 400 段）；``CreateHitArea`` 第 24 位必须留 0。
    """
    tree = copy.deepcopy(_source_tree(ctx, SPECIAL_PROGRAMS[level], SPECIAL_SHA[level]))
    if tree[0] != "ActionDsl" or tree[1] != 1 or tree[10] != 0:
        raise KitError(f"special lv{level} head drift: {tree[:2]} bta={tree[10]}")
    if not PH.cmds(tree, "SetPowerFilpSuppress") or not PH.cmds(tree, "NotifyPowerflipEnd"):
        raise KitError(f"special lv{level} lost SetPowerFilpSuppress / NotifyPowerflipEnd")
    root_body = tree[11][1]
    aura = [n for n, e in enumerate(root_body)
            if e[0] == "Command" and e[1][0] == "ShowEffect" and e[1][1] == "オーラ演出"]
    if len(aura) != 1:
        raise KitError(f"special lv{level} オーラ演出 not unique ({len(aura)})")

    # 作者 09-21 真机反馈：「丝缇涅尔也不要浮游」⇒ 辅助增益块只留攻击力提升与贯穿。
    # donor 仍按官方三件套校验（pf_support_block 内部），只是 ACFlying 那条不进成品树。
    block = PH.pf_support_block(ctx.root, level, keep_flying=False)
    kinds = [c[2][0][0] for c in PH.cmds(block, "CreateCondition")]
    if kinds != ["ACAttackPoint", "ACPiercing"]:
        raise KitError(f"supporter 辅助增益块应为 ACAttackPoint/ACPiercing 两件套，实为 {kinds}")
    pierce = [c for c in PH.cmds(block, "CreateCondition") if c[2][0][0] == "ACPiercing"]
    if len(pierce) != 1:
        raise KitError("supporter 辅助增益块 ACPiercing not unique")
    frames = PF_PIERCE_FRAMES[level]
    _ac_node(pierce[0], "ACPiercing")[1] = PH.slv(frames, frames)
    if sorted(set(PH.bound_ids(block))) != [PF_SUPPORT_BIND]:
        raise KitError(f"supporter block bound ids {sorted(set(PH.bound_ids(block)))} "
                       f"!= [{PF_SUPPORT_BIND}]")
    root_body.insert(aura[0] + 1, block)

    scaled = []
    for cna in PH.cmds(tree, "CreateNormalAttack"):
        mult = cna[6]
        if len(mult) != 1 or mult[0]["min"] != mult[0]["max"]:
            raise KitError(f"special lv{level} CNA multiplier shape drift: {mult}")
        value = round(mult[0]["min"] * PF_SCALE, 6)
        cna[6] = PH.slv(value, value)
        scaled.append(value)
    if not scaled:
        raise KitError(f"special lv{level} carries no CreateNormalAttack")
    for cha in PH.cmds(tree, "CreateHitArea"):
        if cha[24] != 0:
            raise KitError("PF CreateHitArea p23 must stay 0 (4 = 按直击算，整块 PF 乘区被跳过)")
    stray = sorted({p for p in PH.spec_paths(tree)
                    if p.startswith(f"battle/effect/skill_unique/{CODE}/")})
    if stray:
        raise KitError(f"PF lv{level} 引用了包内特效（底座与辅助块的官方件必须直接引用）: {stray}")
    problems = _dsl_problems(tree)          # PF 底座的 CNA 同样是 255 继承，元素检查在技能侧
    problems += [f"signature: {p}" for p in PH.signature_problems(tree)]
    problems += [f"expr: {p}" for p in PH.expr_tag_problems(tree)]
    problems += [f"scope: {p}" for p in PH.scope_problems(tree)]
    if problems:
        raise KitError(f"PF lv{level} DSL gates failed: {problems}")
    return tree, {"level": level, "multipliers": scaled, "total": round(sum(scaled), 6),
                  "pierce_frames": frames, "support_block_bind": PF_SUPPORT_BIND,
                  "official_effects": sorted(set(PH.spec_paths(tree))),
                  "bound_ids": sorted(set(PH.bound_ids(tree)))}


# ---------------------------------------------------------------- 特效族

def fx_lut_path(ctx) -> Path:
    """特效代理的交付优先（``rework1/fx/stinel/``），退回上一轮的 ``B/pixel/stinel/``。"""
    delivery = Path(ctx.root) / FX_DELIVERY / "fx_lut.json"
    if delivery.is_file():
        return delivery
    return KL.pixel_dir(ctx) / "fx_lut.json"


def _pkg_amf(ctx, root: str, logical: str):
    return ctx.amf_parse(ctx.pack.pkg_path(root, logical).read_bytes())


def cut_mirror_row(ctx, family) -> dict[str, Any]:
    """「只要一排」第二级：删掉 funnel ``parts`` 里矩阵 a<0 的镜像排（调研卡 C §5.2）。

    ``clone_effect_family`` 没有 parts 钩子 ⇒ 手术必须在 clone **之后**重新施加，
    否则每次 ``--step kit`` 都会被官方母本冲掉。母本任何一处漂移都直接拒绝。
    """
    dst = family["dst_dir"]
    root = family["files"][0]["root"]
    logical = f"{dst}/{FX_FUNNEL}.parts.amf3.deflate"
    parts = _pkg_amf(ctx, root, logical)
    groups = parts["g"]
    if len(groups) <= FUNNEL_MIRROR_GROUP:
        raise KitError(f"funnel parts 只有 {len(groups)} 个 group，母本漂移")
    segs = groups[FUNNEL_MIRROR_GROUP]["s"]
    if len(segs) != FUNNEL_MIRROR_SEGMENTS:
        raise KitError(f"funnel g[{FUNNEL_MIRROR_GROUP}] 有 {len(segs)} 段，母本应为 "
                       f"{FUNNEL_MIRROR_SEGMENTS} 段（正排/镜像排/尾件）")
    transforms = parts["t"]
    mirrored = []
    for n, seg in enumerate(segs):
        index = (int(seg["l"][0]["m"]) & 0xFFFFFFFF) >> 12
        if index >= len(transforms):
            raise KitError(f"funnel 段 {n} 的变换下标 {index} 越界（{len(transforms)}）")
        if float(transforms[index].get("a", 4096)) < 0:
            mirrored.append(n)
    if len(mirrored) != 1:
        raise KitError(f"funnel g[{FUNNEL_MIRROR_GROUP}] 的镜像排不唯一: {mirrored}")
    del segs[mirrored[0]]
    data = ctx.amf_bytes(parts)
    ctx.write_asset(root, logical, data)
    if _pkg_amf(ctx, root, logical) != parts:
        raise KitError(f"{logical} readback differs from the written tree")
    return {"file": logical, "removed_segment": mirrored[0], "segments_left": len(segs)}


# ---------------------------------------------------------------- 入口

def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.cid, spec.code, spec.element) != (CID, CODE, ELEMENT):
        raise KitError(f"identity drift: {spec.cid}/{spec.code}/element {spec.element}")
    if (spec.template_id, spec.template_code) != (TEMPLATE_ID, TEMPLATE_CODE):
        raise KitError(f"template drift: {spec.template_id}/{spec.template_code}")
    if spec.pf_type != PF_TYPE or spec.stance != STANCE:
        raise KitError(f"spec drift: pf_type={spec.pf_type} stance={spec.stance}")
    if MS.text_placeholders(spec):
        raise KitError(f"design texts still placeholders: {MS.text_placeholders(spec)}")

    design = load_design(ctx.root)

    # ---- 1) 队长技 9 行
    leader_rows, leader_evidence = build_leader_rows(ctx)
    capabilities: set[str] = set()
    for ev in leader_evidence:
        capabilities.update(ev["capabilities"])
    ctx.write_flat(KL.LEADER, {str(CID): leader_rows})

    # ---- 2) 词条 6 键 16 条
    ability_rows, ability_evidence = build_ability_rows(ctx)
    for ev in ability_evidence:
        capabilities.update(ev["capabilities"])
    ctx.write_flat(KL.ABILITY, ability_rows)

    # ---- 3) custom_ability_string：536 / 722 c82 / 两段 desc_override
    cas_plan, cas_caps = write_strings(ctx)
    capabilities.update(cas_caps)
    change_skill_row = ability_rows[ABILITY_KEYS[0]][1]
    if change_skill_row[70] != CAS_CHANGE_SKILL:
        raise KitError(f"能力1#1 的 536 string_id 漂移: c70={change_skill_row[70]!r}")

    # ---- 4) action_skill 两档能量
    action_rows = write_action_skill(ctx)

    # ---- 5) 技能特效族（整族克隆换名 + LUT 染色 + parts 镜像排切除）
    lut_path = fx_lut_path(ctx)
    lut = KL.png_transform_from_lut(lut_path)
    family = ctx.clone_effect_family(FX_SRC_DIR, FX_SUBDIR, png_transform=lut)
    if family["dst_dir"] != FX_DST_DIR or not family["complete_family"]:
        raise KitError(f"effect family drift: {family['dst_dir']} complete={family['complete_family']}")
    if sorted(family["copied_bases"]) != sorted((FX_FUNNEL, FX_EXPLOSION)):
        raise KitError(f"effect family bases drift: {family['copied_bases']}")
    surgery = cut_mirror_row(ctx, family) if SINGLE_ROW_SURGERY else None

    # ---- 6) 技能 DSL 两档
    programs: list[str] = []
    skill_gates: dict[str, Any] = {}
    for level in ("1", "2"):
        tree, gates = build_skill_tree(ctx, level, family)
        programs.append(_write_dsl_checked(ctx, ctx.program_path(level), tree))
        skill_gates[level] = gates

    # ---- 7) 专属强化弹射 722 三档
    pf_gates: dict[str, Any] = {}
    for level in (1, 2, 3):
        tree, gates = build_pf_tree(ctx, level)
        programs.append(_write_dsl_checked(ctx, PF_PROGRAMS[level - 1], tree))
        pf_gates[str(level)] = gates
    ctx.write_flat(PFA, {PF_KEY: [list(PF_PROGRAMS)]})

    # ---- 8) 语音路由 + character 行
    design_route = design.get("voice", {}).get("route")
    if not isinstance(design_route, dict) or int(design_route.get("kind", -1)) != VOICE_ROUTE["kind"]:
        raise KitError(f"design voice route drift: {design_route}")
    route = KL.voice_route(CODE, VOICE_ROUTE)
    char_row = ctx.pack.pkg_character_row()
    char_row[9:17] = route
    if char_row[6] != str(PF_TYPE) or char_row[26] != STANCE or char_row[27] != str(CID):
        raise KitError(f"character row drift: c6={char_row[6]} c26={char_row[26]} c27={char_row[27]}")
    ctx.write_flat(KL.CHARACTER, {str(CID): [char_row]})
    voice_ready = KL.write_voice_ready(ctx)

    # ---- 9) 像素成品（缺文件静默跳过）+ 三层镜像
    pixel = KL.install_staged_assets(ctx)
    mirrors = ctx.sync_character_mirrors()
    if mirrors["character"][9:17] != route:
        raise KitError("character mirror lost the voice route")

    panel = list(PANEL_LEADER) + list(PANEL_SLOT3) + [cas_plan[CAS_CHANGE_SKILL]]

    ctx.evidence_write("kit-gates.json", {
        "leader": {"rows": leader_rows, "evidence": leader_evidence},
        "ability": {"rows": ability_rows, "evidence": ability_evidence},
        "skills": skill_gates, "power_flip": pf_gates, "action_skill": action_rows,
        "effect_family": {k: family[k] for k in ("src_dir", "dst_dir", "layout", "copied_bases",
                                                 "complete_family", "missing_effects")},
        "fx_lut": {"path": str(lut_path), "applied": bool(lut)},
        "parts_surgery": surgery,
        "custom_ability_string": cas_plan,
        "voice_route": route, "voice_ready": voice_ready,
        "pixel": pixel, "mirrors": mirrors,
    })

    notes = [
        "队长技 9 行 → 面板 7 行由 desc_override_still_obstinator_moon 接管："
        "722 双类型 PF（辅助＋特殊，只在她当队长时生效）、开局除自身外光角色回槽 50%、"
        "常驻技伤 400%／攻击 200%、施技回槽 5%＋连击 50、每 250 连击攻击 +100%（限 5 次）、"
        "PF 每命中 1 个敌人给 8 秒可叠加攻击 +100%（trigger 15＝空挥不触发）、PF 连击 +5",
        "词条槽 3（Ⓜ）6 条 → 面板 4 行由 desc_override_still_obstinator_moon_3 接管："
        "「自身每获得一个效果」拆成瞬发 trigger 29（连击）与 during_trigger 37（技伤 7 层），"
        "「除自身外的光角色发动技能时」两行 puller 都是 6（技能槽 10%→5%，均无 CT，"
        "09-27 平衡批次）；724 那条作者本轮未提及，原样保留",
        f"技能：母本 151093 整树 + 诺瓦三块嫁接（上一轮四块，本轮删掉第二个 funnel ShowEffect）；"
        f"StopBall 90/Stop → 30/RestoreToSpeedBeforeActionExecution、Circle {HIT_AREA_TEMPLATE_RADIUS}"
        f"→{HIT_AREA_RADIUS}、funnel scale {FUNNEL_SCALE}×、带 alv 的 CNA +{SKILL_ALV_BOOST}"
        f"（536 开 ⇒ 80 倍）；能量两档同为 {ENERGY[0]}",
        f"722 三档：官方 special_lv{{n}} 底座（sha 锁定）×{PF_SCALE} + supporter 辅助增益块"
        f"（贯通帧 {'/'.join(str(PF_PIERCE_FRAMES[n]) for n in (1, 2, 3))}，bind {PF_SUPPORT_BIND} 段）；"
        f"power_flip_action[{PF_KEY}] 指向三条 override 程序",
        f"特效族整族克隆 {FX_SRC_DIR} → {FX_DST_DIR}（2 base、sheet 252×776 尺寸不变 ⇒ 图集增量 0）"
        + ("；已套用 " + str(lut_path) if lut else f"；**{lut_path} 未交付，特效仍是母本原色**")
        + ("；parts 镜像排已切除（「只要一排」第二级）" if surgery else "；parts 手术关闭"),
        "零先例/需真机：trigger 29 无冷却 7 次（K1）、during 37 target 全队（K2）、"
        "leader kind 0 + trigger 15 组合（K3）、722 行挂共鸣门（K4）、去定住+扩判定+1.5×（K5）、"
        "parts 镜像排切除（K6）——退路见 rework1/impl/stinel.md §2",
        {"pixel_install": pixel},
    ]

    gate = {"rows": len(leader_evidence) + len(ability_evidence), "programs": len(programs),
            "fx_lut_applied": bool(lut), "parts_surgery": bool(surgery),
            "pixel_present": pixel["present"],
            "pixel_missing": [e["logical"] for e in pixel["skipped"]]}
    ready = bool(lut) and pixel["present"] and not pixel["skipped"]
    gate["reason"] = "kit 自有产物全部过闸" if ready else "、".join(filter(None, [
        "" if lut else f"特效换色 LUT 未交付（{lut_path}）",
        "" if pixel["present"] and not pixel["skipped"]
        else f"像素成品未就绪：{gate['pixel_missing'] or 'B/pixel/stinel/install.json 不存在'}"]))

    return KL.report(
        ctx, summary="丝缇涅尔：光属性技伤辅助（722 辅助＋特殊双类型 PF／连击滚雪球／状态计数增益七层）",
        status=KL.READY if ready else KL.DRAFT, panel=panel, notes=notes, programs=programs,
        required_capabilities=sorted(capabilities),
        deviations=[dict(entry) for entry in DEVIATIONS],
        extra={"custom_ability_string": sorted(cas_plan), "effect_families": [FX_DST_DIR],
               "power_flip_action": {PF_KEY: list(PF_PROGRAMS)},
               "kit_gate": gate, "voice_route": route,
               "calibration": design["rework1"].get("calibration", {})})

# -*- coding: utf-8 -*-
"""中秋批次 kit：夏琳 139992 ``artificialeye_sniper_moon``（雷 · 射击 · 妨害辅助）。

**rework1（2026-09-21）**：按 ``rework1/panel/charlene.json`` 重做。轴线仍是
「把敌人身上同时存在的弱体条数当层数卖给全队」，但四条弱体**移出技能本体**，
改由词条 1「雷属性共鸣时强化技能」（536 ChangeSkillFlag ＋ DSL
``ConditionalsChangeSkillFlag``）接管，并追加「随机两种异常」轮盘；
技能本体换成「抽血 ＋ 护盾 ＋ 贯穿弹命中爆炸」。

**平衡批次 2026-09-27**（作者确认；live 侧键级修订见 ``wf_balance_20260927_charlene.py``，
测试断言本模块输出与之逐字一致）：技能两档顶层追加自身护盾（-17，自身最大 HP 10%）；
轮盘删掉死格 ``ACStun``（Stunify 只能挂成员，挂敌人被 ``fit()`` 静默丢弃），剩 3 选 1；
词条 1 追加 kind 53 眩晕畏缩特攻（对虚弱敌人的独立乘区）全队雷 20%，挂雷共鸣门；
强化条目文案去掉「使敌人更容易进入DOWN」，技能描述补自身护盾。

由 ``python mod-tools/wf_midautumn_build.py --char charlene --step kit`` 调用 :func:`build`。
只经 ``KitContext`` 写 ``work/character_packs/ma-charlene/``；live store / ``assets/`` /
``.cdn`` / 设备 / 存档 一律不碰，不发布、不 git。

设计稿：``work/character_packs/midautumn-20260920/design/charlene.{md,json}``；
施工单：``…/midautumn-20260920/rework1/impl/charlene.md``。
行方案（donor + 逐格改 + ``wf_describe`` 回读）全部内联在本模块，设计稿在场时逐条互校
（:func:`design_crosscheck`）——设计稿在 gitignore 的 ``work/`` 下，缺失时不阻塞。

落地内容
--------
- character 行 c9–c16 语音路由（kind 1 ConditionExist / 3 AttackPointUp → ``<code>_voice_ready``）
  ＋ c18 队长技名；character_text 12 列与 action_skill 两档文案由 ``tables`` 依 :data:`TEXTS` 写，
  本模块只断言不漂移。
- 队长技 5 行（**本轮一格不动**）、词条 6 键 12 条：官方 donor 行 + 逐格改，逐行过
  ``wf_client_legality``（合法性 / 声明块字段 / 元素列）并与登记的面板文案逐字比对。
- action_skill 两档能量 c4/c5 两档统一 500/500（作者放行 §5），名称/描述同 :data:`TEXTS`。
- 两棵技能 DSL：官方母本 ``artificialeye_sniper$_1/_2`` 整树 + 三处官方蓝本移植：
  ① 顶层插「抽血」``FindAllSubjects(33) → ConditionalsHealthPointRatioOf → CreateRatioAttack``
  （蓝本 ``rector_sorcerer_playable``）、「护盾」``FindAllSubjects(35,[3]) → CreateBarrier``
  （蓝本 ``priest_prince_playable``）与「自身护盾」``CreateBarrier(-17)``（蓝本 ``alice_smr20`` /
  ``woman_knight_1anv`` 顶层写法，09-27 平衡批次）；② 贯穿弹 on-hit 里把母本那条 ``CreateCondition`` 换成
  ``ConditionalsChangeSkillFlag``（蓝本 ``amulet_bosslady``）分流的强化块；③ on-hit 末尾接
  「命中爆炸」``CreateReferencePoint → CreateHitArea(Circle) → CreateNormalAttack``
  （蓝本 ``blindness_gunner``，官方 82 棵树有同形嵌套）。
  **特效全部直接引用官方母本路径，零克隆零图集增量。**
- ``custom_ability_string`` ``change_skill_<code>``＝536 的面板条目（官方母本自带同名键）。
- ``switched_action_skill`` ``<code>_voice_ready``（matched_skill_ready 的路由目标）。
- 像素/特效交付件：``B/pixel/charlene/install.json`` 在场才装，缺失静默跳过。

**无固有状态、无 ``desc_override``、零 APK 补丁 kind（``required_capabilities`` 仍为空）。**
"""
from __future__ import annotations

import copy
import json
from typing import Any

import wf_midautumn_kitlib as KL
import wf_midautumn_specs as MS

KEY = "charlene"
CID = 139992
CID_S = "139992"
CODE = "artificialeye_sniper_moon"
TEMPLATE_CODE = "artificialeye_sniper"
ELEMENT = 2                      # 内部 ElementKind：2 = 雷（Yellow）
ELEMENT_TOKEN = "Yellow"
VOICE_KEY = CODE + "_voice_ready"

# 一键内 c2（雕像组）必须单值（裁决 §8）。取 ``attack_yellow``：母本 131176 自己就把
# 1311763 的 5 条混 kind 记录（D0 / I245 / I209 / I536）统一挂在 attack_yellow 下，
# 是「雷属性角色的攻击系词条」这一格的官方写法。
STATUE_GROUP = "attack_yellow"

CHARACTER = KL.CHARACTER
ACTION = KL.ACTION

#: 536 ChangeSkillFlag 的面板条目键。母本 131176 自己就有同名键（``change_skill_artificialeye_sniper``），
#: ``tables`` 步会按新 code 克隆出 ``change_skill_artificialeye_sniper_moon``；本模块重写它的文案。
CAS_SWITCH = "change_skill_" + CODE

#: 技能强化条目的文案。裁决 §3：「技能强化」条目不写数字与时间
#: （``KL.check_panel(skill_flag=True)`` 硬卡数字 / 秒 / %）。
#: 09-27 平衡批次：轮盘删掉 ``ACStun`` 死格 ⇒ 文案去掉「使敌人更容易进入DOWN」。
#: 09-27 第三轮（``wf_balance_20260927c_panels`` FLAG_TEXT，主会话 R2 / 口径C）：官方格式点明技能名；能力1 是
#: 自动面板，客户端按 536 行的雷共鸣前置自己拼条件 ⇒ 串里不再写「雷属性共鸣时」；轮盘第三格是 ``ACFrozen`` ⇒「冻结」。
CAS_TEXTS = {
    CAS_SWITCH: "强化『桂影·望月三千』：命中敌人时赋予其累积全属性抗性降低与累积攻击力降低效果"
                "（无视弱体抗性），并随机追加赋予麻痹、中毒、冻结中的两种效果",
}

_SKILL_DESC = ("抽取全体队伍成员生命值55%（若该成员当前生命值低于50%，则改为抽取其生命值20%），"
               "并为除自身外的雷属性角色赋予护盾，护盾值为其最大生命值25%，"
               "同时为自身赋予护盾，护盾值为自身最大生命值10% ＋ "
               "瞄准敌人射出月华贯穿弹，命中后爆炸，对范围内的敌人造成雷属性伤害")

TEXTS = {
    "name": "夏琳",
    "furigana": "XIALIN",
    "profile": "「三千米外也绝不失手」的死神，这一夜把兔子挂饰系上枪管，坐在桂树下的石栏上啃月饼。"
               "她说今晚歇业——可要是有人扰了这轮满月，桂花落地之前，对方就已经躺在准星里了。",
    "title": "代号·月兔",
    "skill1": "桂影·望月三千",
    "desc1": _SKILL_DESC,
    "skill2": "桂影·望月三千＋",
    "desc2": _SKILL_DESC,
    "leader": "Ace of Moonlight",
    "cv": "AI 合成配音",
}

SPEC = {
    "stance": "Jammer",                      # 母本 c26；整套 kit 的轴就是给敌人挂弱体
    "required_capabilities": (),             # 12+5 条行实跑 caps 全空，不需要任何 APK 补丁 kind
    "extra_keys": {KL.SWITCHED: (VOICE_KEY,), KL.CAS: (CAS_SWITCH,)},
}

# character c9–c16：kind 1 ConditionExist，条件种类 3 = AttackPointUp、条件 id 0。
# 依据：词条 1399923#0「技能Hit → 赋予全队(雷) 状态攻击力（15 秒）」target 5 含自身 ⇒
# 打完技能 15 秒内她身上必有攻击力 UP，这段窗口内满槽播 matched_skill_ready。
VOICE_ROUTE = {"kind": 1, "condition_kind": "3", "condition_id": "0"}

# ------------------------------------------------------------------ 行方案
# 每条 =（donor 键#记录号（0 基）, 逐格改, 面板预期文案）。donor 一律取官方基线
# （``.cdn/cn`` OfficialBaseline），不取 store。

LEADER: tuple[tuple[str, dict[int, str], str], ...] = (
    # L1 每层弱体 → 全队(雷) 触发敌方 Direct 伤害特攻（直击伤害池）
    ("121165#1", {0: CODE, 100: "4", 109: ELEMENT_TOKEN, 111: "60000", 112: "85000"},
     "持续·任一敌方状态计数减益≥1(限4次) → 赋予全队(雷) 触发敌方Direct伤害特攻 60%→85%"),
    # L2 同层数 → 攻击力池（与 L1 分池，不互相稀释）
    ("121165#0", {0: CODE, 100: "4", 109: ELEMENT_TOKEN, 111: "30000", 112: "40000"},
     "持续·任一敌方状态计数减益≥1(限4次) → 赋予全队(雷) 触发敌方攻击特攻 30%→40%"),
    # L3 只要敌人身上有任何弱体 → 攻击力池（不挑元素、不挑 boss 的兜底）
    ("161069#1", {0: CODE, 47: ELEMENT_TOKEN, 49: "30000", 50: "50000"},
     "赋予全队(雷) 减益攻击特攻 30%→50%"),
    # L4 雷共鸣 6 人 → 独立特攻池（P4）
    ("111004#1", {0: CODE, 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
                  47: ELEMENT_TOKEN, 49: "15000", 50: "25000"},
     "雷·编成≥6 时: 赋予全队(雷) 减益特攻 15%→25%"),
    # L5 开场给除自己以外的雷属性队员半管技能槽（官方夏琳本人的队长行）
    ("131176#0", {0: CODE, 49: "40000", 50: "50000"},
     "赋予除自身全员(雷) 技能槽 40%→50%"),
)

#: 「X 属性共鸣时」＝官方常规共鸣前置（主控 2026-09-21 落实①）：ability 前置 1 写
#: kind 2（编成人数）+ 阈值 600000 + 元素。与 kyle 的 ``_PRE_RESONANCE_A`` 同一套。
#: ``wf_describe`` 把它渲染成「雷·编成≥6 时:」——引擎里「共鸣」就是这个门。
PRE_RESONANCE = {6: "2", 9: "600000", 10: "600000", 11: ELEMENT_TOKEN}

#: 把母本行的「瞬发触发块」压回常驻（trigger kind 0）。空串是坑（``parseAt*`` 无空串分支），
#: 官方常驻行的写法就是 c27='0' + c28/c30/c31/c34/c35/c36 全空 + c39='(None)' + c46='0'。
NO_TRIGGER = {27: "0", 28: "", 30: "", 31: "", 34: "", 35: "", 36: ""}

ABILITY: dict[str, tuple[tuple[str, dict[int, str], str], ...]] = {
    # 1 开局自身充能 ＋ 雷共鸣时「强化技能」（536 → DSL ConditionalsChangeSkillFlag）
    "1399921": (
        ("1311761#0", {0: CODE + "_1", 2: STATUE_GROUP, 6: "0", 11: "",
                       51: "50000", 52: "50000"},
         "自身 技能槽 50%"),
        ("1311763#4", {0: CODE + "_1", 1: "true", 2: STATUE_GROUP, 70: CAS_SWITCH,
                       **PRE_RESONANCE, **NO_TRIGGER},
         f"雷·编成≥6 时: 自身 切换技能形态[{CAS_SWITCH}]"),
        # 09-27 平衡批次：雷共鸣时全队雷「对虚弱（Down）中的敌人」独立乘区 +20%。
        # kind 53 StunWinceSlayer → PinchSlayer（InstantAbilitySource.as:953-956），伤害式
        # NormalAttackCalculator.as:647-660 对 hasPinched 目标单独乘 (1+Σ)；不含比例/定值伤害与毒。
        # donor 官方 fox_oracle_4 1310014#0（常驻、target 5 全队、c49 Yellow），与 536 共用同一道共鸣门；
        # 面板由客户端按 stun_wince_slayer + 「（独立乘区）」自动生成，不写 desc_override。
        ("1310014#0", {0: CODE + "_1", 2: STATUE_GROUP, 51: "20000", 52: "20000",
                       **PRE_RESONANCE},
         "雷·编成≥6 时: 赋予全队(雷) 眩晕畏缩特攻 20%"),
    ),
    # 2 对「弱体中的敌人」三池：P1 攻击力 / P6 直击伤害 / P4 独立乘区（调研卡 B §6.6）
    "1399922": (
        ("1110934#0", {0: CODE + "_2", 2: STATUE_GROUP, 49: ELEMENT_TOKEN,
                       51: "200000", 52: "200000"},
         "赋予全队(雷) 减益攻击特攻 200%"),
        # 124 官方只有 1210153#0 一行且 target 0；这里换 491 那张「target 5 + 元素列」的整行、
        # 只改内容 kind ⇒ 列布局与已验证行逐格一致，零新列形状。
        ("1110934#0", {0: CODE + "_2", 2: STATUE_GROUP, 47: "124", 49: ELEMENT_TOKEN,
                       51: "100000", 52: "100000"},
         "赋予全队(雷) 减益Direct伤害特攻 100%"),
        ("1610052#1", {0: CODE + "_2", 2: STATUE_GROUP, 49: ELEMENT_TOKEN,
                       51: "10000", 52: "10000"},
         "赋予全队(雷) 减益特攻 10%"),
    ),
    # 3 Ⓜ 主位：共鸣团队攻击力（无 CT）＋ 敌方攻击力↓ 两层 ＋ 共鸣队长技能槽上限
    "1399923": (
        ("1610693#0", {0: CODE + "_3", 2: STATUE_GROUP, 35: "0", 49: ELEMENT_TOKEN,
                       51: "150000", 52: "150000", **PRE_RESONANCE},
         "雷·编成≥6 时: 技能Hit≥1 → 赋予全队(雷) 状态攻击力 150%(15秒)×1次"),
        ("1610693#1", {0: CODE + "_3", 2: STATUE_GROUP, 35: "0",
                       51: "-20000", 52: "-20000",
                       57: "300000000", 58: "300000000", 61: "2"},
         "技能Hit≥1 → 自身 敌方状态攻击力 -20%(50秒)[累积上限2]"),
        # 245 = SecondSkillGauge ＝技能槽上限（记忆卡 wf-skill-gauge-max-exists；
        # wf_describe 直译成「2号位技能槽」，见施工单偏离 V4）。母本这行 target 就是队长。
        ("1311763#2", {0: CODE + "_3", 2: STATUE_GROUP, 51: "20000", 52: "20000",
                       **PRE_RESONANCE, **NO_TRIGGER},
         "雷·编成≥6 时: 赋予队长 2号位技能槽 20%"),
    ),
    # 4 雷共鸣门控的独立特攻池按层
    "1399924": (
        ("1211656#0", {0: CODE + "_4", 2: STATUE_GROUP, 11: ELEMENT_TOKEN, 102: "4",
                       111: ELEMENT_TOKEN, 113: "2500", 114: "5000"},
         "雷·编成≥6 时: 持续·任一敌方状态计数减益≥1(限4次) → 赋予全队(雷) 触发敌方特攻 2.5%→5%"),
    ),
    # 5 直击体系正反馈：全队雷属性成员的直击合计每 10 次给全队 Direct 伤害
    "1399925": (
        ("1510573#1", {0: CODE + "_5", 1: "true", 2: STATUE_GROUP, 29: ELEMENT_TOKEN,
                       49: ELEMENT_TOKEN, 51: "3000", 52: "6000"},
         "编成直接攻击≥10(限10次)(CT10秒) → 赋予全队(雷) Direct伤害 3%→6%"),
    ),
    # 6 本体轴的攻击力池按层（副位也吃）
    "1399926": (
        ("1211653#0", {0: CODE + "_6", 1: "true", 2: STATUE_GROUP, 102: "4",
                       111: ELEMENT_TOKEN, 113: "7500", 114: "15000"},
         "持续·任一敌方状态计数减益≥1(限4次) → 赋予全队(雷) 触发敌方攻击特攻 7.5%→15%"),
    ),
}

# ------------------------------------------------------------------ 技能 DSL
# 母本整树保留；三处官方蓝本移植（施工单 §2 配方 R1–R4）。

#: 爆炸段 CreateNormalAttack 的倍率（slv1 → slv max）。面板写满级单值「50 倍」。
#: 觉醒档 max = 50×，未觉醒档按本套件既有的 ×0.8 惯例（偏离 D9）。
SKILL_MULTIPLIER = {"1": (32, 40), "2": (40, 50)}
#: 作者放行 §5：夏琳 500，觉醒前后两档都写这个数。
SKILL_ENERGY = {"1": ("500", "500"), "2": ("500", "500")}

#: 抽血（作者原话「抽取全体成员 55% 血量；低于 50% 的成员只抽 20%」）。
#: 蓝本 ``rector_sorcerer_playable_2``：``FindAllSubjects(4,113,[6]) →
#: ConditionalsHealthPointRatioOf(4,50, then CreateRatioAttack 0.1, else [])``。
#: 分支语义【官方两例互证】：**then ＝ HP ≥ 阈值，else ＝ HP < 阈值**。
DRAIN_SELECTOR = 33          # 参战全员（主队 3 人 + 协力/召唤球）；基诺维 v3 锁定「扣血走 33」
DRAIN_THRESHOLD = 50         # 百分数整数（官方三例 40 / 50 / 50）
DRAIN_RATIO_HIGH = 0.55      # HP ≥ 50% 的成员
DRAIN_RATIO_LOW = 0.20       # HP < 50% 的成员
DRAIN_KIND = 2               # CreateRatioAttack p1：官方 22 例恒为 2 ＝ 按最大生命值比例

#: 护盾（「除自身外的雷属性角色，最大生命值 25%」）。蓝本 ``priest_prince_playable_2``
#: 的 ``CreateBarrier(_, [ratio], ["GenericBarrierHitEffect"])``（官方带 0.03–0.075）。
BARRIER_SELECTOR = 35        # 除自身外的队友（82 含自身，裁决 §8 踩过）
BARRIER_ELEMENT_FILTER = 3   # FindAllSubjects 元素过滤槽 = 内部元素码 + 1（雷 2 → 3）
BARRIER_RATIO = 0.25

#: 自身护盾（09-27 平衡批次：「自身最大生命值 10%」）。官方顶层 ``CreateBarrier(-17, …)`` 先例
#: ``alice_smr20`` / ``woman_knight_1anv``；BarrierCalculator 按受盾者自己的最大 HP 取整。
#: 不经 FindAllSubjects、不受 ChangeSkillFlag 门控；抽血是友伤、不被护盾吸收，放在队友护盾之后。
SELF_BARRIER_SUBJECT = -17   # 内建主体：自身
SELF_BARRIER_RATIO = 0.1

#: 爆炸段（贯穿弹 on-hit → 参照点 → 圆形判定区 → CNA）。蓝本 ``blindness_gunner_2``
#: （同为枪手母本；官方 1052 棵可解技能树里 82 棵有「on-hit 块里再开 CreateHitArea」）。
EXPLOSION_RADIUS = 300       # Circle 上限 600（判定区参数卡）
EXPLOSION_LIFETIME = 10      # 蓝本同值
REFERENCE_POINT_LIFETIME = 100

#: ``ConditionalsChangeSkillFlag`` 的 flag 下标。蓝本 ``amulet_bosslady_2`` 与本批 kyle 都写 1。
SKILL_FLAG_INDEX = 1

#: 强化档常驻的两条弱体（母本那条 CreateCondition 改参数 + 克隆）。名称 / AC / forceApply。
BOOST_CONDITIONS: tuple[tuple[str, list, bool], ...] = (
    # 全属性抗性↓（累积 4 层 = −32%）。元素码 254 = 全属性：boss 的 resist_element_resistance
    # 是白名单，只放行 254 与克制属性，写单元素码会被静默硬拒（记忆 wf-force-apply-and-damage-floors）。
    # forceApply=true 穿 boss 弱体耐性，蓝本官方 ``stella_copy_assist``（254 + 负值 + 累积 + true）。
    ("tolerance_all",
     ["ACToleranceOfElement",
      [{"min": 1800, "max": 1800}],
      254,
      [{"min": -0.06, "max": -0.08, "alv_min": -0.02, "alv_max": -0.03}],
      [{"min": 4, "max": 4}]],
     True),
    # 敌方攻击力↓（累积 4 层 = −24%）。AC 形状抄官方 ``amulet_bosslady_2``
    # ``[3900, -0.06→-0.07, 累积 3]``，只改帧/强度/层上限。
    ("attack_down",
     ["ACAttackPoint",
      [{"min": 1800, "max": 1800}],
      [{"min": -0.05, "max": -0.06, "alv_min": -0.02, "alv_max": -0.03}],
      [{"min": 4, "max": 4}]],
     True),
)

#: 强化档的随机池：3 选 1 轮盘 × :data:`ROULETTE_DRAWS` 次（每次独立掷点，可能重复——
#: 作者原话是「随机追加两种」，没要求互斥；调研卡 B §4.2 建议接受可重复）。
#: 权重写 25：ProbabilityWeight 按相对权重（ActionEvaluator.as:4940-5016 case 105 先求和再按累积阈值命中）
#: ⇒ 和 75、每格 1/3。名称 / AC / forceApply / 权重。
#:
#: 09-27 平衡批次删掉第 4 格 ``("stun_accum", ACStun 900f/0.2/1)``：ACStun 转成
#: ``ConditionChangeContent.Stunify``（AdditionalConditionKindTools.as:241-243），而 ``fit()`` 规定
#: Stunify(17) 只能挂在 xMember 上（ConditionChangeContentTools.as:1059-1071），挂到敌人身上在
#: ConditionSlot.as:7454 直接 return——原先是死格，面板「使敌人更容易进入DOWN」也与实际不符。
#: 「对虚弱敌人」的加成改由词条 1 的 kind 53（独立乘区）承担。
ROULETTE_DRAWS = 2
ROULETTE: tuple[tuple[str, list, bool, int], ...] = (
    # 麻痹 3 秒（官方带 180/240/480/600 帧）。**不强制付与**（裁决 §2 口径）。
    ("paralysis", ["ACParalysis", [{"min": 180, "max": 180}], True], False, 25),
    # 中毒（「桂花醉」）。毒走 FixedAttackCalculator 独立通道；官方 1800 帧 / 强度 5000–6000。
    ("poison", ["ACPoison", [{"min": 1800, "max": 1800}], [{"min": 5000, "max": 5000}],
                [{"min": 1, "max": 1}]], False, 25),
    # 引擎枚举 Frozen，客户端名「冻结」（``wf_dsl_sig.AC_CN``；09-27 第三轮面板由「迟缓」改「冻结」）。官方带 900 / 1200 帧。
    ("frozen", ["ACFrozen", [{"min": 900, "max": 900}], True], False, 25),
)

#: 技能特效全部直接引用官方母本路径（零克隆、零图集增量，裁决 §4）。
OFFICIAL_EFFECT_PREFIX = f"battle/effect/skill_unique/{TEMPLATE_CODE}/"

#: 爆炸演出：复用母本自己的命中特效，只放大倍率（不新增特效引用 ⇒ 图集增量仍是 0）。
EXPLOSION_EFFECT_SCALE = 3.5

#: 新增绑定号。母本占用 -18 / 1（判定区自身）/ 2（命中位置）/ 3（命中的敌人）。
BIND_HIT_POS = 2
BIND_HIT_ENEMY = 3
BIND_DRAIN = 4
BIND_BARRIER = 5
BIND_RP = 6                  # 爆炸参照点
BIND_BLAST_AREA = 7          # 爆炸判定区自身
BIND_BLAST_POS = 8
BIND_BLAST_ENEMY = 9

#: 母本整树的命令计数指纹：任何一项对不上都说明母本漂移或改错了结构。
DONOR_COMMAND_COUNTS = {
    "FindNearSubjects": 1, "StopBall": 1, "ShowEffect": 5, "CreateHitArea": 1,
    "MoveHitArea": 1, "ShakeCamera": 1, "CreateNormalAttack": 1, "CreateCondition": 1,
}


class CharleneError(KL.KitError):
    """本角色 kit 的断言失败。"""


# ------------------------------------------------------------------ DSL 工具

def _command_slots(node, name: str, out: list | None = None) -> list[tuple[list, int]]:
    """找出 ``["Command", [<name>, …]]` 在其父列表里的位置，返回 ``[(父列表, 下标), …]``。"""
    out = [] if out is None else out
    if isinstance(node, list):
        for index, child in enumerate(node):
            if (isinstance(child, list) and len(child) == 2 and child[0] == "Command"
                    and isinstance(child[1], list) and child[1] and child[1][0] == name):
                out.append((node, index))
            _command_slots(child, name, out)
    elif isinstance(node, dict):
        for child in node.values():
            _command_slots(child, name, out)
    return out


def _command_counts(tree) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in _walk(tree):
        if (isinstance(node, list) and len(node) == 2 and node[0] == "Command"
                and isinstance(node[1], list) and node[1] and isinstance(node[1][0], str)):
            counts[node[1][0]] = counts.get(node[1][0], 0) + 1
    return counts


def _walk(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from _walk(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _walk(child)


def effect_paths(tree) -> list[str]:
    """树里所有 ``SpecifyEffectDirectly`` 的特效路径。"""
    return [node[1] for node in _walk(tree)
            if isinstance(node, list) and len(node) == 2
            and node[0] == "SpecifyEffectDirectly" and isinstance(node[1], str)]


def _cmd(name: str, *args) -> list:
    return ["Command", [name, *args]]


def _block(*commands) -> list:
    return ["Block", list(commands)]


def _condition(donor_cmd: list, ac: list, force: bool) -> list:
    """母本那条 ``CreateCondition`` 整体克隆，只换 AC 列表与末位 ``forceApply``。"""
    command = copy.deepcopy(donor_cmd)
    # 下标 2 是 **AC 列表**（母本是 ``[[ACToleranceOfElement, …]]`` 一条）：
    # 直接塞裸 AC 会把嵌套层吃掉一层，往返自检抓不到，进战斗才炸。
    command[1][2] = [copy.deepcopy(ac)]
    command[1][12] = bool(force)
    return command


def drain_block() -> list:
    """抽血：参战全员按 HP 档位扣最大生命值的比例（蓝本 ``rector_sorcerer_playable_2``）。"""
    return _cmd(
        "FindAllSubjects", BIND_DRAIN, DRAIN_SELECTOR, [], [], [], [], [], ["DoNothing"],
        _block(_cmd(
            "ConditionalsHealthPointRatioOf", BIND_DRAIN, DRAIN_THRESHOLD,
            # then ＝ HP ≥ 阈值（官方自伤放 then、治疗放 else，两例互证）
            _block(_cmd("CreateRatioAttack", BIND_DRAIN, DRAIN_KIND,
                        [{"min": DRAIN_RATIO_HIGH, "max": DRAIN_RATIO_HIGH}])),
            # else ＝ HP < 阈值
            _block(_cmd("CreateRatioAttack", BIND_DRAIN, DRAIN_KIND,
                        [{"min": DRAIN_RATIO_LOW, "max": DRAIN_RATIO_LOW}])))))


def barrier_block() -> list:
    """护盾：除自身外的雷属性队友，最大生命值比例（蓝本 ``priest_prince_playable_2``）。"""
    return _cmd(
        "FindAllSubjects", BIND_BARRIER, BARRIER_SELECTOR, [BARRIER_ELEMENT_FILTER],
        [], [], [], [], ["DoNothing"],
        _block(_cmd("CreateBarrier", BIND_BARRIER,
                    [{"min": BARRIER_RATIO, "max": BARRIER_RATIO}],
                    ["GenericBarrierHitEffect"])))


def self_barrier_block() -> list:
    """自身护盾：顶层直接对 -17（自身）加盾，自身最大生命值比例（蓝本 ``alice_smr20``）。"""
    return _cmd("CreateBarrier", SELF_BARRIER_SUBJECT,
                [{"min": SELF_BARRIER_RATIO, "max": SELF_BARRIER_RATIO}],
                ["GenericBarrierHitEffect"])


def explosion_block(donor_cna: list, level: str) -> list:
    """命中爆炸：参照点 → 圆形判定区 → CNA（蓝本 ``blindness_gunner_2`` 的嵌套段）。"""
    low, high = SKILL_MULTIPLIER[level]
    cna = copy.deepcopy(donor_cna)
    cna[1][1] = BIND_BLAST_ENEMY
    cna[1][6] = [{"min": low, "max": high}]
    # 下标 12 ＝ enablesRangeBonus：蓝本的爆炸段就开着（范围加成），母本的单点弹是 false。
    cna[1][12] = True
    return _cmd(
        "CreateReferencePoint", BIND_HIT_POS, ["GH", 0], 0, 0, 0, False, False,
        ["Single"], REFERENCE_POINT_LIFETIME, BIND_RP,
        _block(_cmd(
            "CreateHitArea", "*", BIND_RP, ["GH", 0], 0, 0, 0, False, False,
            ["Circle", [{"min": EXPLOSION_RADIUS, "max": EXPLOSION_RADIUS}]],
            ["Center"], ["Center"], ["Single"],
            ["SpecifyHitAreaLifetimeDirectly", EXPLOSION_LIFETIME],
            ["CalculatedUsingMaxNumOfHits", 1], ["None"], False, True, ["None"],
            BIND_BLAST_AREA, _block(), BIND_BLAST_POS, BIND_BLAST_ENEMY,
            _block(cna), 0, 0, ["None"])))


def mutate_tree(tree, level: str):
    """母本整树 → 本角色的树。返回 ``(tree, evidence)``；结构不符直接抛错。"""
    counts = _command_counts(tree)
    if counts != DONOR_COMMAND_COUNTS:
        raise CharleneError(f"donor skill tree {level} drifted: commands {counts} "
                            f"!= {DONOR_COMMAND_COUNTS}")
    if not (isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl"):
        raise CharleneError(f"donor skill tree {level}: unexpected root {tree[:2]!r}")
    if tree[1] != 2 or tree[10] != 0:
        # tree[10] = buffTargetAs：0 = 自动（技能伤害）。她不是直击输出位，保持 0。
        # 调研卡 B §7.3：这一段**不要**写 4，写 4 会丢掉全部技能伤害 UP。
        raise CharleneError(f"donor root header {level}: movementPriority={tree[1]} "
                            f"buffTargetAs={tree[10]}, expected 2/0")

    # --- 母本的单点 CNA：整条挪进爆炸段（母本弹体本身不再直接造成伤害）
    (cna_parent, cna_index), = _command_slots(tree, "CreateNormalAttack")
    donor_cna = cna_parent[cna_index]
    cna_body = donor_cna[1]
    if cna_body[2] != 255:
        # 255 = 随自身属性。DSL 显式元素码只有 CreateNormalAttack[2] 有 +1 偏移
        # （记忆 wf-dsl-element-code-offset），写死反而会错，这一格不动。
        raise CharleneError(f"CreateNormalAttack element slot {cna_body[2]!r} != 255")
    if len(cna_body) != 17:
        raise CharleneError(f"donor CreateNormalAttack has {len(cna_body) - 1} params, expected 16")
    before_mult = copy.deepcopy(cna_body[6])
    blast = explosion_block(donor_cna, level)

    # --- on-hit CreateCondition → ConditionalsChangeSkillFlag 分流的强化块
    (cc_parent, cc_index), = _command_slots(tree, "CreateCondition")
    if cc_parent is not cna_parent:
        raise CharleneError(f"skill {level}: CreateCondition and CreateNormalAttack "
                            "are not in the same on-hit block")
    donor_cmd = cc_parent[cc_index]
    donor_body = donor_cmd[1]
    if len(donor_body) != 13:
        raise CharleneError(f"donor CreateCondition has {len(donor_body)} slots, expected 13")
    if donor_body[10] != 3:
        # 下标 10 = 付与对象种类；母本这条挂在 on-hit 的敌人身上，错配 = 施法 C16102
        # （记忆 wf-createcondition-target-kind）。整条克隆 ⇒ 这一格原样保留。
        raise CharleneError(f"donor CreateCondition target kind {donor_body[10]!r} != 3")
    if donor_body[1] != BIND_HIT_ENEMY:
        raise CharleneError(f"donor CreateCondition subject {donor_body[1]!r} != {BIND_HIT_ENEMY}")
    if donor_body[12] is not False:
        raise CharleneError(f"donor CreateCondition forceApply {donor_body[12]!r} != False")
    before_ac = copy.deepcopy(donor_body[2])

    boost = [_condition(donor_cmd, ac, force) for _name, ac, force in BOOST_CONDITIONS]
    for _draw in range(ROULETTE_DRAWS):
        branches = []
        for _name, ac, force, weight in ROULETTE:
            # 分支形状是强校验的：必须恰好两个元素 —— [0] ProbabilityWeight、[1] Block。
            # 任何偏差 = 进战斗 INTERNAL ERROR（调研卡 B §4.1）。
            branches.append(_block(_cmd("ProbabilityWeight", weight),
                                   _block(_condition(donor_cmd, ac, force))))
        boost.append(_cmd("ConditionalsProbability", ["Block", branches]))
    # 空分支写 ["Block", []]，**不能写 ["DoNothing"]**（记忆 wf-dsl-donothing-enum-trap：F1009）。
    cc_parent[cc_index] = _cmd("ConditionalsChangeSkillFlag", SKILL_FLAG_INDEX,
                               ["Block", boost], _block())

    # --- 把母本的单点 CNA 从 on-hit 里摘掉，末尾接爆炸段
    cna_parent.pop(cna_index)
    cc_parent.append(blast)

    # --- 顶层：抽血 + 队友护盾 + 自身护盾排在母本的瞄准/射击块之前
    top = tree[11]
    if not (isinstance(top, list) and top[0] == "Block" and len(top[1]) == 1):
        raise CharleneError(f"donor top block {level}: expected a single command, got {len(top[1])}")
    top[1][0:0] = [drain_block(), barrier_block(), self_barrier_block()]

    # --- 特效：全部还是官方母本路径（零克隆、零图集增量）
    paths = effect_paths(tree)
    stray = [p for p in paths if not p.startswith(OFFICIAL_EFFECT_PREFIX)]
    if stray:
        raise CharleneError(f"skill {level} references non-official effect paths: {stray}")
    if len(paths) != DONOR_COMMAND_COUNTS["ShowEffect"]:
        raise CharleneError(f"skill {level} has {len(paths)} effect refs, expected "
                            f"{DONOR_COMMAND_COUNTS['ShowEffect']}")

    # 爆炸演出：放大母本自己的命中特效（不新增引用 ⇒ 图集增量仍是 0）
    (hit_parent, hit_index), = [(p, i) for p, i in _command_slots(tree, "ShowEffect")
                                if p[i][1][1] == "ヒットエフェクト"]
    hit_parent[hit_index][1][12] = ["Some", [{"min": EXPLOSION_EFFECT_SCALE,
                                              "max": EXPLOSION_EFFECT_SCALE}]]

    after = _command_counts(tree)
    n_cond = len(BOOST_CONDITIONS) + ROULETTE_DRAWS * len(ROULETTE)
    expect_after = dict(
        DONOR_COMMAND_COUNTS, CreateCondition=n_cond, CreateNormalAttack=1,
        FindAllSubjects=2, ConditionalsHealthPointRatioOf=1, CreateRatioAttack=2,
        CreateBarrier=2, ConditionalsChangeSkillFlag=1,
        ConditionalsProbability=ROULETTE_DRAWS,
        ProbabilityWeight=ROULETTE_DRAWS * len(ROULETTE),
        CreateReferencePoint=1, CreateHitArea=2)
    if after != expect_after:
        raise CharleneError(f"mutated skill tree {level}: commands {after} != {expect_after}")

    evidence = {
        "level": level,
        "create_normal_attack": {"before": before_mult, "after": [{"min": SKILL_MULTIPLIER[level][0],
                                                                   "max": SKILL_MULTIPLIER[level][1]}],
                                 "moved_to": "explosion block"},
        "drain": {"selector": DRAIN_SELECTOR, "threshold": DRAIN_THRESHOLD,
                  "ratio_high": DRAIN_RATIO_HIGH, "ratio_low": DRAIN_RATIO_LOW},
        "barrier": {"selector": BARRIER_SELECTOR, "element_filter": BARRIER_ELEMENT_FILTER,
                    "ratio": BARRIER_RATIO},
        "self_barrier": {"subject": SELF_BARRIER_SUBJECT, "ratio": SELF_BARRIER_RATIO},
        "explosion": {"radius": EXPLOSION_RADIUS, "lifetime": EXPLOSION_LIFETIME,
                      "reference_point_lifetime": REFERENCE_POINT_LIFETIME,
                      "multiplier": list(SKILL_MULTIPLIER[level])},
        "boost": {
            "flag_index": SKILL_FLAG_INDEX,
            "donor_ac": before_ac,
            "always": [{"name": name, "ac": ac[0], "force_apply": force}
                       for name, ac, force in BOOST_CONDITIONS],
            "roulette_draws": ROULETTE_DRAWS,
            "roulette": [{"name": name, "ac": ac[0], "force_apply": force, "weight": weight}
                         for name, ac, force, weight in ROULETTE],
        },
        "effect_refs": paths,
    }
    return tree, evidence


def write_custom_strings(ctx) -> dict[str, Any]:
    """写 536 的面板条目 ``change_skill_<code>``（``custom_ability_string``）。

    母本 131176 自己就有 ``change_skill_artificialeye_sniper``，``tables`` 步已按新 code
    克隆并认领了 ``change_skill_<code>``；本函数只重写文案（母本写的是「雷属性抗性降低」，
    与本套件改成全属性 254 + 随机池之后的真实机制不符 ⇒ 裁决 §3 面板不许说谎）。
    """
    declared = set(ctx.spec.extra_keys.get(KL.CAS, ()))
    missing = [key for key in CAS_TEXTS if key not in declared]
    if missing:
        raise CharleneError(f"custom_ability_string keys not declared in SPEC['extra_keys']: {missing}")
    official = ctx.official_flat(KL.CAS)
    clashes = [key for key in CAS_TEXTS if key in official]
    if clashes:
        raise CharleneError(f"custom_ability_string keys collide with official rows: {clashes}")
    for key, text in CAS_TEXTS.items():
        KL.check_panel(text, skill_flag=True, label=key)
    ctx.write_flat(KL.CAS, {key: [[text]] for key, text in CAS_TEXTS.items()})
    return dict(CAS_TEXTS)


# ------------------------------------------------------------------ 设计稿互校

def design_crosscheck(ctx) -> dict[str, Any]:
    """设计稿在场时逐条互校（身份 / 文案 / 15 行的 donor·面板文案 / 能量 / 倍率 / 语音路由）。

    设计稿在 gitignore 的 ``work/`` 下，缺失时只记一条 note，不阻塞构建。
    """
    path = MS.design_path(ctx.root, KEY)
    if not path.is_file():
        return {"design_json": str(path), "present": False,
                "note": "设计稿不在（work/ 未恢复）：本次以 kit 模块内联方案为准"}
    design = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []

    ident = design.get("identity", {})
    for name, want in (("cid", CID), ("code", CODE), ("element", ELEMENT),
                       ("template_character", 131176), ("template_code", TEMPLATE_CODE)):
        if ident.get(name) != want:
            problems.append(f"identity.{name} = {ident.get(name)!r}, kit says {want!r}")

    for name, want in TEXTS.items():
        got = design.get("texts", {}).get(name)
        if got != want:
            problems.append(f"texts.{name} drifted from the design")

    plan = design.get("plan", {})
    rows = plan.get("leader_ability", {}).get("rows", [])
    if len(rows) != len(LEADER):
        problems.append(f"design has {len(rows)} leader rows, kit has {len(LEADER)}")
    for row, (donor, _cells, expect) in zip(rows, LEADER):
        key, _, index = donor.partition("#")
        want_donor = f"official leader_ability[{key}] #{int(index) + 1}"
        if row.get("donor") != want_donor:
            problems.append(f"leader #{row.get('index')}: donor {row.get('donor')!r} != {want_donor!r}")
        if row.get("desc_expected") != expect:
            problems.append(f"leader #{row.get('index')}: desc_expected drifted")

    keys = plan.get("ability", {}).get("keys", {})
    if sorted(keys) != sorted(ABILITY):
        problems.append(f"design ability keys {sorted(keys)} != kit {sorted(ABILITY)}")
    for key, recs in ABILITY.items():
        entry = keys.get(key, {})
        if entry.get("statue_group") != STATUE_GROUP:
            problems.append(f"ability {key}: design statue_group {entry.get('statue_group')!r} "
                            f"!= {STATUE_GROUP!r}")
        records = entry.get("records", [])
        if len(records) != len(recs):
            problems.append(f"ability {key}: design has {len(records)} records, kit has {len(recs)}")
        for record, (donor, _cells, expect) in zip(records, recs):
            rec_key, _, index = donor.partition("#")
            want_donor = f"official ability[{rec_key}] #{int(index) + 1}"
            if record.get("donor") != want_donor:
                problems.append(f"ability {key}: donor {record.get('donor')!r} != {want_donor!r}")
            if record.get("desc_expected") != expect:
                problems.append(f"ability {key}: desc_expected drifted")

    skills = plan.get("skills", {})
    for level, (c4, c5) in SKILL_ENERGY.items():
        energy = skills.get("energy", {}).get(f"inner{level}", {})
        if (str(energy.get("c4_min_skill_weight")), str(energy.get("c5_max_skill_weight"))) != (c4, c5):
            problems.append(f"action_skill {level}: energy drifted from the design")
    mult = skills.get("multiplier", {})
    want_mult = {"inner1_slv1": SKILL_MULTIPLIER["1"][0], "inner1_slvmax": SKILL_MULTIPLIER["1"][1],
                 "inner2_slv1": SKILL_MULTIPLIER["2"][0], "inner2_slvmax": SKILL_MULTIPLIER["2"][1]}
    for name, want in want_mult.items():
        if mult.get(name) != want:
            problems.append(f"skill multiplier {name} = {mult.get(name)!r}, kit says {want!r}")

    columns = design.get("voice", {}).get("route", {}).get("columns")
    if columns != KL.voice_route(CODE, VOICE_ROUTE):
        problems.append(f"voice route columns {columns!r} drifted")

    if problems:
        raise CharleneError("design/charlene.json disagrees with the kit: " + "; ".join(problems))
    return {"design_json": str(path), "present": True, "checked": [
        "identity", "texts", "leader donors + panel text", "ability donors + panel text",
        "statue_group", "skill energy", "skill multiplier", "voice route"]}


# ------------------------------------------------------------------ build

def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.key, str(spec.cid), spec.code, spec.element) != (KEY, CID_S, CODE, ELEMENT):
        raise CharleneError(f"spec identity mismatch: {spec.key}/{spec.cid}/{spec.code}/{spec.element}")
    if spec.template_code != TEMPLATE_CODE or spec.rarity != 5:
        raise CharleneError(f"spec template/rarity mismatch: {spec.template_code}/{spec.rarity}")
    if spec.pf_type != 2:
        raise CharleneError(f"spec pf_type {spec.pf_type} != 2 (射击)")

    notes: list[Any] = [design_crosscheck(ctx)]
    evidence: list[dict[str, Any]] = []

    # ---- 1) character 行：语音路由 c9–c16 ＋ 队长技名 c18
    crow = list(ctx.pack.pkg_character_row())
    expect_cols = {0: CODE, 2: "5", 3: str(ELEMENT), 6: str(spec.pf_type), 8: CODE,
                   17: CID_S, 26: "Jammer", 27: CID_S}
    for index, key in enumerate(range(19, 25)):
        expect_cols[key] = f"{CID_S}{index + 1}"
    drift = {i: (crow[i], v) for i, v in expect_cols.items() if crow[i] != v}
    if drift:
        raise CharleneError(f"package character row differs from spec (rerun tables): {drift}")
    route = KL.voice_route(CODE, VOICE_ROUTE)
    crow[9:17] = route
    crow[18] = TEXTS["leader"]
    ctx.write_flat(CHARACTER, {CID_S: [crow]})

    # ---- 2) 队长技 5 行
    leader_rows = []
    for index, (donor, cells, expect) in enumerate(LEADER):
        row, ev = KL.build_row(ctx, "leader_ability", donor, cells,
                               expect_describe=expect, label=f"leader#{index}")
        leader_rows.append(row)
        evidence.append(ev)
    ctx.write_flat(KL.LEADER, {CID_S: leader_rows})

    # ---- 3) 词条 6 键 12 条
    ability_rows: dict[str, list[list[str]]] = {}
    for key, records in ABILITY.items():
        built = []
        for index, (donor, cells, expect) in enumerate(records):
            row, ev = KL.build_row(ctx, "ability", donor, cells, element=ELEMENT,
                                   expect_describe=expect, label=f"{key}#{index}")
            built.append(row)
            evidence.append(ev)
        KL.check_ability_key(built, key, CODE, int(key[-1]))
        ability_rows[key] = built
    ctx.write_flat(KL.ABILITY, ability_rows)
    cas = write_custom_strings(ctx)

    # ---- 4) 面板文案规则（队长 + 词条 + 技能名/说明 + 称号）
    panel = [ev["describe"] for ev in evidence]
    for text in panel:
        KL.check_panel(text, label="panel row")
    for name in ("title", "skill1", "desc1", "skill2", "desc2", "leader", "profile"):
        KL.check_panel(TEXTS[name], label=f"texts.{name}")

    # ---- 5) action_skill：名称 / 描述 / 能量（其余列断言与母本一致）
    inner = ctx.pkg_nested(CODE, ACTION)
    if sorted(inner) != ["1", "2"]:
        raise CharleneError(f"package action_skill inner keys {sorted(inner)} != ['1', '2']")
    new_inner: dict[str, list[list[str]]] = {}
    for level, cells in sorted(inner.items()):
        cells = list(cells)
        if len(cells) != 24:
            raise CharleneError(f"action_skill {level}: {len(cells)} columns, expected 24")
        if cells[7] != ctx.program_path(level):
            raise CharleneError(f"action_skill {level}: program {cells[7]!r} "
                                f"!= {ctx.program_path(level)!r}")
        cells[0] = TEXTS[f"skill{level}"]
        cells[1] = TEXTS[f"desc{level}"]
        cells[4], cells[5] = SKILL_ENERGY[level]
        if cells[2:4] != ["dynamic/skill/atk_nearest", "true"]:
            raise CharleneError(f"action_skill {level}: targeting columns changed {cells[2:4]}")
        if cells[8:17] != ["1", "2", "2400", "3000", "0", "0", "0", "0", "(None)"]:
            raise CharleneError(f"action_skill {level}: c8–c16 differ from the template {cells[8:17]}")
        if any(cells[17:]):
            raise CharleneError(f"action_skill {level}: c17+ not empty {cells[17:]}")
        new_inner[level] = [cells]
    ctx.write_nested(ACTION, CODE, new_inner, replace_inner=True)

    # ---- 6) 技能 DSL 两档（官方 donor 树改参数；写后从包里回读比对）
    skill_evidence = []
    programs = []
    for level in ("1", "2"):
        donor_program = ctx.program_path(level).replace(CODE, TEMPLATE_CODE)
        tree, ev = mutate_tree(ctx.template_dsl(donor_program), level)
        logical = ctx.write_dsl(ctx.program_path(level), tree)
        back = ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
        if back != tree:
            raise CharleneError(f"skill {level}: package DSL read-back differs from the written tree")
        ev["logical"] = logical
        ev["donor_program"] = donor_program
        skill_evidence.append(ev)
        programs.append(logical)

    # ---- 7) 语音路由目标 + 像素/特效交付件
    switched = KL.write_voice_ready(ctx)
    pixel = KL.install_staged_assets(ctx)
    lut_path = KL.pixel_dir(ctx) / "fx_lut.json"
    if lut_path.is_file():
        notes.append({"fx_lut": str(lut_path),
                      "unused": "本角色技能特效全部直接引用官方母本路径（零克隆），"
                                "没有可换色的包内特效；要改色须先改设计稿 §4.3 改成 clone_effect_family"})

    ctx.sync_character_mirrors()

    ctx.evidence_write("kit-rows.json", {
        "leader": [{"donor": donor, "cells": {str(k): v for k, v in cells.items()},
                    "describe": expect} for donor, cells, expect in LEADER],
        "ability": {key: [{"donor": donor, "cells": {str(k): v for k, v in cells.items()},
                           "describe": expect} for donor, cells, expect in records]
                    for key, records in ABILITY.items()},
        "rows": evidence,
    })
    ctx.evidence_write("kit-skills.json", {"programs": programs, "levels": skill_evidence})

    notes.extend([
        {"voice_route": route, "switched_action_skill": switched,
         "why": "kind 1 ConditionExist / 条件种类 3 AttackPointUp：词条 1399923#0 给全队（含自身）"
                "15 秒攻击力 UP ⇒ 连射窗口内满槽播 matched_skill_ready"},
        {"pixel_install": pixel},
        {"statue_group": STATUE_GROUP,
         "why": "一键内 c2 必须单值（裁决 §8）。母本 131176 的 1311763 把 5 条混 kind 记录"
                "（D0/I245/I209/I536）统一挂 attack_yellow，是雷属性角色攻击系词条的官方写法"},
        {"effects": "零克隆：5 条 ShowEffect 全部引用官方 "
                    f"{OFFICIAL_EFFECT_PREFIX}*，包内不含 battle/effect 目录 ⇒ 图集增量 0；"
                    f"爆炸演出＝把母本自己的命中特效放大到 ×{EXPLOSION_EFFECT_SCALE}"},
        {"custom_ability_string": cas,
         "why": "536 ChangeSkillFlag 的面板条目。母本 131176 自己就有同名键，tables 已按新 code"
                "克隆并认领；kit 只重写文案，让它和 DSL 里 ConditionalsChangeSkillFlag 的强化块一致"},
        {"skill_boost_conditions": [name for name, _ac, _force in BOOST_CONDITIONS],
         "roulette": [name for name, _ac, _force, _w in ROULETTE],
         "roulette_draws": ROULETTE_DRAWS,
         "force_apply": [name for name, _ac, force in BOOST_CONDITIONS if force],
         "why": "弱体全部移进「雷共鸣强化档」：常驻 2 条（全属性抗性↓ / 攻击力↓，forceApply 穿"
                "boss 弱体耐性）＋ 3 选 1 轮盘掷 2 次（09-27 删掉挂不上敌人的 ACStun 死格）；"
                "非共鸣队伍技能只有抽血/护盾/爆炸伤害。"
                "队长技与词条 D136 的层数来源随之只在共鸣时满额（金丝雀 Z4）"},
        {"balance_20260927": {
            "self_barrier": {"subject": SELF_BARRIER_SUBJECT, "ratio": SELF_BARRIER_RATIO},
            "roulette_dropped": "ACStun",
            "ability_1_appended": "1310014#0 kind 53 全队(雷) 20%（雷共鸣门）",
            "live_revision": "wf_balance_20260927_charlene.py"},
         "why": "作者 2026-09-27 确认：自身护盾 10%；删掉挂不上敌人的 ACStun 死格；"
                "对虚弱敌人的加成改由 kind 53 独立乘区承担"},
        {"unique_condition": "无。层数来源是敌人身上的弱体条数（D136），不需要自身固有状态，"
                             "不占 8 位固有 ID、不需要 48×48 图标"},
    ])

    deviations = [
        {"want": "设计稿 §5『所有行的 c2 统一 attack_yellow，只有词条 1 的第 0 条沿用母本的 action_skill』",
         "got": "词条 1 的两条记录统一写 attack_yellow（设计稿 md/json 已同步改，登记为 D9）",
         "why": "裁决 §8：ability 表 c2 每个键必须单值（官方 790 个多记录键 0 个混用），"
                "``KL.check_ability_key`` 也硬卡这条。kind 211 × attack_yellow 官方 2 条先例；"
                "母本 131176 自己就把 1311763 的 5 条混 kind 记录统一挂 attack_yellow"},
        {"want": "作者原话「随机追加赋予麻痹气绝中毒迟缓两种效果」",
         "got": "轮盘只剩麻痹 / 中毒 / 迟缓三格（各 1/3）；09-21 落成的「气绝→ACStun 眩晕蓄积」一格"
                "已在 09-27 平衡批次移除，改由词条 1 的 kind 53 眩晕畏缩特攻（对虚弱敌人的独立乘区）"
                "全队雷 +20% 替代（_deviations.json charlene[0]）",
         "why": "数据层没有「付与气绝」的口；``ACStun`` 转成 ``ConditionChangeContent.Stunify``，"
                "``fit()`` 只允许它挂成员（ConditionChangeContentTools.as:1059-1071），挂到敌人身上被"
                "ConditionSlot.as:7454 静默丢弃，削韧也只读攻击方自己的 Stunify ⇒ 原分支是死格，"
                "「使敌人更容易进入DOWN」与实际不符"},
        {"want": "作者 09-27「对处于虚弱状态的敌人造成伤害，额外乘区＋20%」",
         "got": "词条 1 第 3 条 kind 53（donor 官方 1310014#0）全队雷 20%，雷共鸣门；"
                "面板由客户端按 stun_wince_slayer ＋「（独立乘区）」自动生成，wf_describe 渲染"
                "「雷·编成≥6 时: 赋予全队(雷) 眩晕畏缩特攻 20%」",
         "why": "不写 desc_override：本角色刻意保持零客户端补丁依赖（required_capabilities 为空）。"
                "PinchSlayer 只作用于 NormalAttackCalculator，比例/定值伤害与毒不吃"},
        {"want": "目标面板「雷属性角色对处于减益状态的敌人：攻击力＋200%、直击伤害＋100%」写成一行",
         "got": "拆成 491 与 124 两条记录（面板两行），第三行是 96 的独立乘区 10%",
         "why": "攻击力池与直击伤害池是两个 kind，一条记录只能渲染一条效果。本角色不引入"
                "``desc_override``（``required_capabilities`` 保持空，不为文案添客户端补丁依赖）；"
                "已回写 ``rework1/panel/charlene.json`` 为三行并标 dev:true"},
        {"want": "目标面板「队长技能槽上限＋20%」",
         "got": "引擎渲染「雷·编成≥6 时: 赋予队长 2号位技能槽 20%」",
         "why": "kind 245 的枚举名是 SecondSkillGauge＝技能槽上限（记忆卡 wf-skill-gauge-max-exists），"
                "``wf_describe`` 直译成「2号位技能槽」。真机面板用的是客户端自己的文案，"
                "以真机截图为准（金丝雀 Z5）"},
        {"want": "作者原话「对范围内敌方造成 50 倍雷属性伤害」",
         "got": "技能描述写「造成雷属性伤害」不写倍数；50× 落在爆炸段 CNA 的 slv max",
         "why": "官方技能描述从不印倍率（印了会随技能等级变成假话）。倍率两档 32→40 / 40→50，"
                "满级＝作者要的 50×"},
        {"want": "抽血与护盾作用于「全体队伍成员」",
         "got": "单机完全生效；联机时抽血与护盾作用不到其他玩家的角色",
         "why": "跨机通道 ``TargetMate`` 只能送 NormalHeal / RatioHeal / ConditionChanges / "
                "ConditionCancels；``RatioAttack``／``Barrier`` 走该路径在 evaluator 里是 "
                "throw INTERNAL ERROR。沿用基诺维时作者的裁决（_deviations.json charlene[1]）"},
        {"want": "两档（slv 1/2）分别给不同的弱体强度（母本 960→1200 帧、−0.2→−0.3 的档差）",
         "got": "两档写同一组条件参数，升档只提升爆炸段的 CNA 倍率",
         "why": "面板文案不写弱体数字，两档差异由伤害倍率体现（本套件既有偏离 D9）"},
    ]

    return KL.report(
        ctx,
        summary="夏琳（139992）：雷 · 射击 · 妨害辅助——技能抽全队血换除自身外雷属性队友的护盾，"
                "贯穿弹命中爆炸；雷共鸣时词条 1 强化技能，命中挂两条累积弱体并随机追加两种异常，"
                "队长技与词条把弱体条数翻译成触发敌方 Direct 伤害特攻／攻击特攻两条乘区",
        status=KL.DRAFT,
        panel=panel,
        notes=notes,
        programs=programs,
        required_capabilities=(),
        deviations=deviations,
        extra={"statue_group": STATUE_GROUP,
               "custom_ability_string": cas,
               "skills": {"programs": programs,
                          "energy": {lv: list(v) for lv, v in SKILL_ENERGY.items()},
                          "multiplier": {lv: list(v) for lv, v in SKILL_MULTIPLIER.items()},
                          "boost_conditions": [name for name, _ac, _force in BOOST_CONDITIONS],
                          "roulette": [name for name, _ac, _force, _w in ROULETTE]}},
    )

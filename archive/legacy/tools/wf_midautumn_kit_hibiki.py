# -*- coding: utf-8 -*-
"中秋批次 kit：澄波响 169988 ``psychic_teleport_moon``（暗 · 特殊型 PF 主 C）—— rework1。\n\n作者 2026-09-20/21 把她的队长技与能力 2/3/5 重写（``rework1/author-request.md`` 第 30 行\n＋ 09-21 答复），目标面板 = ``rework1/panel/hibiki.json``，引擎落法 = ``rework1/panel/_deviations.json``，\n逐行映射与零先例退路见施工单 ``rework1/impl/hibiki.md``。本轮三条轴线：\n\n- **贯通循环**（沿用）：722 专属 PF → 全队长贯通 → 贯通中 PF 大幅增伤 → 再 PF。\n- **回响成长**（本轮放开）：固有「回响」上限 5 → **99**（作者「不设置上限」的官方写法）；\n  每层给自身 PF 伤害 ＋25%（槽 3）与自身攻击力 ＋25%（槽 4，见偏离 D-13），\n  独立乘区 ＋5%／层（封顶 5 层，作者原话「最大 25%」）与全队暗攻 ＋15%／层（封顶 5 层）不变。\n- **PF 追击**（本轮新增）：「暗属性角色发动技能时」与「冲刺时（CT 1.5 秒）」各挂一行队长 629，\n  指向新建的 ``ability_skill_psychic_teleport_moon_pf`` 树 —— 官方 ``special_lv3`` 的命中块\n  整块搬出（去掉 ``SetPowerFilpSuppress`` / ``NotifyPowerflipEnd`` 两条 PF 生命周期命令，\n  斩铁 ``samurai_robot_plum`` 的现成做法），根头 ``tree[10]=3`` ⇒ **通用伤害池**取\n  「强化弹射伤害 ＋X%」而不是「技能伤害 ＋X%」。引擎能做到的边界见 :data:`INVOKE_BTA`。\n\n面板：队长块与 6 个能力槽**全部**由 ``desc_override_*`` 接管（凯尔／罗尔夫 rework1 同款），\n逐行对齐 ``rework1/panel/hibiki.json``；作者要求「能力 5 的词条写在队长技里」＝冲刺 422 行\n物理留在能力表（写进队长表 ＝ C7050），文案挪进队长块。\n\n反馈轮 1（作者 09-21 真机）：「能力 3 没带主位限制」。槽 3 的 c1 一直是 ``false``（整键单值，\nlive 1.4.974 已是如此），缺的是**面板那个 Ⓜ**：``desc_override`` 会盖掉客户端逐行画的主位图标，\n所以主位键必须自己在每行前面写 ``MAIN_ICON``（本批 magnus / fluffy / kuro / stinel 同款做法，\nlive 先例 ``desc_override_ginovi_3``）。本轮把 ``MAIN_ONLY_SLOTS`` 做成 c1 与图标的唯一真源。\n\n反馈轮 3（作者 09-21 真机，「澄波响去掉浮游效果」）：撤浮游 ＝ 引擎里的状态 ``ACFlying``，\n只出现在 722 三档共用的 P1 supporter 辅助增益块（借道 :func:`wf_seasonal7_kit_philia.pf_support_block`，\n菲莉亚同一批反馈也在改这个函数，本模块不碰那个文件）里的一条 ``CreateCondition``。\n``build_pf_tree`` 接受该块的两种合法形态：donor 仍是官方原始三件套时用 :func:`strip_ac_flying`\n自己删 1 条；共享函数已经在源头删过时（两件套）不重复删——两条路径终态相同，\n``ACAttackPoint`` / ``ACPiercing`` 原样保留、绑定与参数不动，形态漂移（既非三件套也非两件套）\n当场炸。技能两档、629 追击树本来就不含 ACFlying，:func:`build` 里做了一次全包汇总断言兜底。\n文案同步：``PANEL_LEADER`` 第 1 行与 ``CAS_TEXTS[CAS_PF]`` 删掉「、浮游」；\n队长/词条行数据本轮零变化（row_diff 应为空）。\n\n2026-09-27 第二批平衡（``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md`` A/B 节，\n修订模块 ``wf_balance_20260927b_hibiki.py``，本文件与它逐格一致）：\n\n- 回响每层的两条无上限成长（槽 3 #1 PF 伤害、槽 4 #2 攻击力，c102=99＝固有上限 99）按口径 A.3\n  搬进队长（队长 10 → 12 行，``[CODE,'0',''] + 能力行[5:]``），3 分钟回响约 99 层 ⇒ ≥30 次 ⇒ ×1/10：\n  每层 25% → 2.5%；能力原位换成封顶 10 层的弱化版（PF 伤害 10%/层、攻击力 5%/层）。\n- 队长 #6（下方注释的 L7：全等级 PF 累计命中每 4 次自身攻击）3 分钟约 30–75 次 ⇒ ×1/10：50% → 5%，仍不限次。\n- 629 PF 追击树（冲刺 CT 1.5 秒 / 暗属性角色发动技能无 CT ⇒ 口径 B.3「CT ≤3 秒每次 ≤1」）：\n  两段 ``CreateNormalAttack`` 的 p13 6.25 → 0.25（3 + 1 段 ＝ 每次 1）。\n- 跨角色 donor：队长 L0（722）的 live donor 菲莉亚 ``159996#3`` 被同批 ``wf_balance_20260927b_philia``\n  改 c49/c50 50000 → 7000；L0 已按 live 值钉死 donor 全部非空列，本行输出不变、不再随菲莉亚漂移。\n\n2026-09-27 第三轮平衡（成长复核，修订模块 ``wf_balance_20260927c_hibiki.py``，本文件与它逐格一致）：\n作者「砍到4/5，或者7/10」「可以砍到2/3」「数值尽量取5的倍数」⇒ 按原值 ×2/3 向上取 5 的倍数回调：\n队长 #6 累计命中每 4 次自身攻击 5% → 35%（原 50%）；队长两条回响每层 2.5% → 20%（原 25%）。\n能力槽 3/槽 4 的封顶版（10%/5% × 10 层）不动。\n\n落地内容\n    - ``unique_condition[16998801]``「回响」（donor 官方 ``7``「加热」；c4 上限 **99**，禁 ``(None)``）\n      与它的 48×48 图标（alpha 取官方图标外框）；\n    - 队长 9 行、词条 6 键 18 条：官方/live donor + 逐格改，每行过 ``wf_client_legality`` 三件套\n      并与本模块登记的 ``wf_describe`` 回读逐字核对；\n    - ``custom_ability_string`` 10 键：722 的 c82 串、两条 629 的条目串、队长块 + 6 槽面板接管；\n    - ``action_skill`` 两档（名称/描述由 tables 写 TEXTS，这里改图标 c2 与能量 c4/c5/c6）；\n    - 技能 DSL 两档（本轮未改）、722 三档、**新增 1 棵 629 PF 追击树**；\n    - character c9–c16 语音路由与 ``switched_action_skill[psychic_teleport_moon_voice_ready]``；\n    - ``B/pixel/hibiki/install.json`` 里的像素/特效成品（缺文件静默跳过）。\n\n不碰：立绘、像素成品 PNG、语音音频、live store / ``assets/`` / ``.cdn`` / 设备 / 存档。\n由 ``python mod-tools/wf_midautumn_build.py --char hibiki --step kit`` 调用 :func:`build`。\n"
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
from wf_midautumn_dash_guard import swift_guard_plan
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
# 只读复用菲莉亚（159996，live 在线）的 DSL 工具与官方 supporter 辅助增益块 —— 裁决：
# 「复用菲莉亚已上线的 build_pf_tree 代码路径」。本模块不修改 wf_seasonal7_* 任何文件。
import wf_seasonal7_kit_philia as PH  # noqa: E402

KitError = KL.KitError

KEY = "hibiki"
CID, CODE = 169988, "psychic_teleport_moon"
ELEMENT = 5                                   # 暗（0 基内部编号）
ELEMENT_TOKEN = "Black"
TEMPLATE_ID, TEMPLATE_CODE = 161183, "psychic_teleport_playable"

UID = MS.unique_condition_id(CID, 1)          # "16998801"
UNIQUE_DONOR = "7"                            # 官方 unique_condition[7]「加热」
UNIQUE_STRING_ID = f"unique_{CODE}_echo"
UNIQUE_NAME = "回响"
UNIQUE_ICON_ROW = f"battle/common/unique_condition/{UNIQUE_STRING_ID}"
UNIQUE_ICON_LOGICAL = UNIQUE_ICON_ROW + ".png"
UNIQUE_ICON_FRAME = "battle/common/unique_condition/unique_combat_animal_xm21.png"
#: rework1：作者「不设置上限」⇒ 官方写法 99（禁 ``(None)``，那是上限 1 层，按层加成全死）。
UNIQUE_CAP = "99"
UNIQUE_FRAMES = "99999999"                    # 无时间限制

PFA = "master/skill/power_flip_action.orderedmap"
PF_KEY = f"{CODE}_pf"
PF_PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_KEY}${PF_KEY}_lv{n}"
                    for n in (1, 2, 3))
SPECIAL_PROGRAMS = {n: f"battle/action/power_flip/action/special$special_lv{n}" for n in (1, 2, 3)}
# 官方 special 底座指纹（2026-09-20 实读 .cdn/cn 官方归档；漂移就说明底座换了，必须重新核算倍率）
SPECIAL_SHA = {
    1: "569f2082c4633bae7e71610c296d6ab141cfabe1f3c4e5e0034c46dbf3e22961",
    2: "4ed6440b9ded6d435e2c2fb9a640541b2c3fc43c5c0068de41077bab07ad73f2",
    3: "7bebfdd5fc3ff46f2a789f7d631ac02084afa0cd11f4f19f71037f7faba3447d",
}
PF_SCALE = 4.8                                # 三档统一的唯一缩放旋钮（设计 §5.2）
PF_PIERCE_FRAMES = {1: 240, 2: 300, 3: 360}   # 官方 60/90/150 → 拉长（贯通是整套循环的命门）
PF_SUPPORT_BIND = 400                         # 辅助增益块主体 id 段（philia.PF_SUPPORT_OFFSET）

# ---------------------------------------------------------------- 自有字符串键
CAS_PF = f"override_string_{CODE}_pf"                  # 722 的 c82 串（缺键 = C8601）
CAS_INVOKE_SKILL = f"ability_skill_{CODE}_pf_skill"    # 队长 629（暗属性角色发动技能时）
CAS_INVOKE_DASH = f"ability_skill_{CODE}_pf_dash"      # 队长 629（冲刺时 CT1.5s）
CAS_LEADER = f"desc_override_{CODE}"                   # 队长块整体接管
CAS_ABILITY = {slot: f"desc_override_{CODE}_{slot}" for slot in range(1, 7)}

#: 629 PF 追击树（官方 special_lv3 命中块整块搬出）。一棵树两行共用。
INVOKE_BASE = f"ability_skill_{CODE}_pf"
INVOKE_PROGRAM = f"battle/action/skill/action/ability_skill/{INVOKE_BASE}${INVOKE_BASE}"
#: 作者 2026-09-24：冲刺/施技追加与本体 PF3 同倍率 62.4×。
INVOKE_SCALE = PF_SCALE
#: 629 载荷每段削韧（``CreateNormalAttack`` p13）。官方 special_lv3 命中块原值 6.25/段，3 + 1 段 ＝ 25
#: ＝ 一次完整 PF3；2026-09-27 第二批平衡口径 B.3：触发 CT ≤3 秒的 629 每次 ≤1（冲刺行 CT 1.5 秒、
#: 暗属性角色发动技能行无 CT）⇒ 0.25/段，4 段 ＝ 每次 1。722 本体三档不动（15/20/25）。
INVOKE_DOWN_SOURCE = 6.25
INVOKE_DOWN = 0.25
#: 629 载荷的伤害归属开关 ＝ **ActionDsl 根头 params[9]**（树里 ``tree[10]``）。
#:
#: 逐行读客户端（反馈轮 4，作者真机「怎么是技能伤害」）确认的完整判定链：
#:
#: 1. ``MemberImpl.as:8158``（``applyInstantAbility`` case 19 ＝ 内容 kind 629）把 ActionKind
#:    **硬编码**成 ``ActionKind.AbilitySkill``（``ActionKind.as:__constructs__`` index **4**）；
#:    能产出 ``ActionKind.PowerFlip``（index 5）的只有 ``MemberImpl.as:1038``，它唯一的调用链是
#:    ``BallImpl.as:846 → SquadImpl.as:387/419 → MemberImpl.startPowerFlip``＝球真的打在弹板上。
#:    **没有任何数据通路能让 629 载荷变成 PF 上下文。**
#: 2. ``ActionEvaluator.as:2443-2456``：ActionKind index 1/2/3/**4** 一律把
#:    ``createdByMainSkillAction`` 置 true（originMemberKind 0/2；1 ＝ Unison）；
#:    ``as:2773`` ``createdByPowerFlipAction = kind.index == 5`` ⇒ 对 629 恒 **false**；
#:    ``as:2709-2721`` ``powerFlipChargeLv`` 对 index 4 恒 **0**。
#: 3. 根头的值确实送得到攻击参数：``ActionManagerImpl.as:179`` → ``ActionEvaluationResolver.as:138``
#:    ``buffTargetAs = int(dsl.params[9])`` → ``as:151 createGlobalEnvironment``；判定区那一层
#:    （``ActionEvaluator.as:3470`` 把 ``params[23]`` 读进 ``_loc17_``，``as:3498``
#:    ``Environment.createLocalEnvironmentDetail(param2, …, _loc17_, …)``）
#:    与命中块那一层（``as:1467-1474 resolveCollisionOfHitArea``）都只是**子环境**，
#:    ``Environment.as:735-752 getBuffTargetAs`` 遇 0 顺着 ``outerEnvironment`` 往上找
#:    ⇒ 判定区留 0 不会挡住根头的 3，最后在 ``as:2877`` 写进 ``CreateNormalAttack`` 的攻击参数。
#: 4. ``NormalAttackCalculator`` 的四个伤害池**各自一条独立 if**，不是互斥分支：
#:    ``as:422`` 强化弹射池 ``buffTargetAs == 3 || (== 0 && createdByPowerFlipAction)`` ⇒ **进**
#:    （池里读的是 ``as:424 getStatModifierPowerFlipDamage()`` ＝ during kind **23**）；
#:    ``as:477`` 技能池 ``buffTargetAs == 1 || (== 0 && createdByMainSkillAction)`` ⇒ **不进**。
#:    但 ``as:446``（PF 分档乘区，``as:457`` 的独立乘区 kind **413** 也挂在这个 if 的
#:    switch ``case 1/2/3`` 里）、``as:467``（PF 场效果独立乘区）、``as:593``（PF 耐性）
#:    只看 ``createdByPowerFlipAction``；``as:499``（技能独立乘区
#:    ``getStatModifierSeparatedTermSkillDamage``）、``as:521``（技能场效果独立乘区
#:    ``getModifierSeparatedTerm2ndSkillDamage``）、``as:611``（技能耐性）
#:    只看 ``createdByMainSkillAction`` ⇒ 这六项对 629 载荷**写什么都改不了**。
#:    注意 ``as:446`` 的 if 对 629 **整块跳过**（``createdByPowerFlipAction`` 恒 false），
#:    所以 ``as:448`` 的 switch 根本到不了；``powerFlipChargeLv`` 对 index 4 恒 0 是另一条
#:    独立事实（``ActionEvaluator.as:2706`` switch，``case 4`` 在 ``as:2720-2721`` 取 0），
#:    即便进了 switch 也只会落 ``case 0`` ⇒ 加成置 0 后 break。两条都成立，别合并成一句。
#: 5. 作者看到的「技能伤害」是**显示层**：``EnemyImpl.as:5807`` 把
#:    ``createdBySkillAction = createdByMainSkillAction`` 直接喂给 ``showDamageFont``，
#:    ``EffectManagerImpl.as:693-707 addTotalDamage`` 据此选 ``TotalSkillDamage``／
#:    ``TotalPowerFlipDamage``，``DamageIndicatorManager.as:85-121`` 同源。
#:    显示层**完全不读** ``buffTargetAs`` ⇒ 数值已经走 PF 池，弹出的标签仍然是技能。数据层无解。
#:
#: 官方全量正向对照（可重跑，脚本
#: ``work/character_packs/ma-hibiki/evidence/scan_official_buff_target_as.py``，
#: 2026-09-21 复核实跑）。语料 ＝ ``.cdn/cn/archive-common-full`` 的 322 个 1.4.0 全量 zip
#: ∩ ``弹国服/restored/_manifest.csv`` 里 ``.action.dsl.amf3.deflate`` 的行；
#: **按 hash_path 去重**（不是 logical_path），不含任何 charpkg／增量包／overlay／分享包。
#: 账本里 7096 个 action.dsl hash_path，这批 zip 覆盖 **7051 棵**（玩家侧 **1119** ＋
#: 敌侧 5932，另 45 行在该归档里没有对应边）：根头 params[9] **100% 是 0**，
#: 三棵官方 ``ability_skill/`` 树（629 载荷 ＝ ``estateguild_leader`` /
#: ``fire_dragon_zenith`` / ``resistance_princess_3halfanv``）也全是 0 ⇒ 写 3 是零先例。
#: 同机制的**已验收**先例是值 2（深渊之兽改能力伤害，记忆卡 wf-dsl-damage-attribution-bufftargetas）
#: 与判定区位的值 4（本批罗尔夫/凯尔技能写 ``params[23]=4``，真机确认按直击结算）。
# The native limitations documented above describe the pre-patch baseline.
# battle-rules-v1 converts category flags, independent buffs and PF level together.
INVOKE_BTA = 133

#: 判定区那一位（``CreateHitArea`` node[24] ＝ params[23]）保持 **0 ＝ 不覆盖**。
#: 0 会顺着环境链落到根头的 :data:`INVOKE_BTA`（见上 §3），所以它**不是**这里的开关；
#: 同一次扫描里官方 **1731** 个玩家侧判定区，这一位只出现过 0（**1721** 个）与 4
#: （10 个，分布在 8 棵技能树的直击段），值 3 零先例，
#: 且写进去与留 0 的运行时效果逐字相同 ⇒ 不写。
INVOKE_HITAREA_BTA = 0

VOICE_KEY = f"{CODE}_voice_ready"
VOICE_ROUTE = {"kind": 1, "condition_kind": "28", "condition_id": UID}

SKILL_ICON = "dynamic/skill/atk_surround"     # 母本 skill_str_up → 威隆同类技能的官方图标
SKILL_DONORS = {
    "template": f"battle/action/skill/action/rare5/{TEMPLATE_CODE}${TEMPLATE_CODE}_2",
    "field": "battle/action/skill/action/rare5/veteran_hunter_3anv$veteran_hunter_3anv_2",
    "team": "battle/action/skill/action/rare4/herbalist_xm22$herbalist_xm22_2",
}
FX_SRC_DIR = f"battle/effect/skill_unique/{TEMPLATE_CODE}"
FX_SUBDIR = "song"
FX_BACK = f"{TEMPLATE_CODE}_back"
FX_EF = f"{TEMPLATE_CODE}_ef"
FX_DST_DIR = f"battle/effect/skill_unique/{CODE}/{FX_SUBDIR}"
FORBIDDEN_FX_PREFIXES = ("battle/effect/skill_unique/veteran_hunter_3anv/",
                         "battle/effect/skill_unique/herbalist_xm22/")

FIELD_WAIT = 30                               # 母本 Event Wait(44) → 30
FIELD_SUBJECT_BASE = 100                      # 音场块主体 id 段
TEAM_SUBJECT_BASE = 200                       # 队伍块主体 id 段
TEAM_PFDMG_FRAMES = 1200                      # 队伍 PF 伤害帧 900 → 1200

# 两档的倍率/强度（设计 §4.2，单位 1.0 = 100%）。rework1 未改技能。
SKILL_PARAMS = {
    "1": {"field": (2.4, 2.4), "self_atk": (1.2, 1.2), "team_pfdmg": (1.0, 1.0), "pierce": (720, 720)},
    "2": {"field": (2.6, 3.0), "self_atk": (1.5, 1.5), "team_pfdmg": (1.2, 1.2), "pierce": (810, 810)},
}
#: 两档技能能量（本轮不改；面板固定显示第一列 550）。
SKILL_ENERGY = {"1": {"c4": 550, "c5": 550, "c6": 1},
                "2": {"c4": 550, "c5": 500, "c6": 1}}

# ---------------------------------------------------------------- 面板文案
# 逐行抄 rework1/panel/hibiki.json（作者已过目的那一版）。分行用 "\n"：
# live 已上线的队长块接管（desc_override_ginovi / _white_tiger_summer / _*_campus）全是 "\n"。

#: 仅主位（c1 unisonable = false）的槽 —— 整键单值，`_UNISONABLE` 由它派生。
#: 能力侧回响仅槽 3 产出；队长侧另有每 3 PF +2，均不让合击位单独产层。
MAIN_ONLY_SLOTS = (3,)
#: desc_override 会盖掉客户端逐行画的 Ⓜ ⇒ 主位键的每一行必须自带图标。
#: 字符串形状照 live 先例（desc_override_ginovi_3 / _white_tiger_summer_1/_3 / _*_campus_*）。
MAIN_ICON = " <icon id='main'>  "

PANEL_LEADER = "\n".join((
    # rework1 反馈轮 3（作者 09-21）：撤掉浮游效果，树里的 ACFlying 一并删（见 build_pf_tree）。
    "赋予自身特殊强化弹射",
    "强化自身冲刺",
    "自身冲刺间隔无法进一步缩短",
    # 2026-09-27 第三轮（wf_balance_20260927c_hibiki）主会话统一口径：强化弹射伤害（战场级）不补对象，
    # 与前一个带对象的效果用「，」隔开；原第5行「；」前后是两种数据条件（#3 常驻｜#5/#8 发动技能）⇒ 拆成两行。
    "持有贯穿效果时，暗属性角色攻击力＋300%，强化弹射伤害＋200%",
    "暗属性共鸣时，贯穿效果持续时间＋30%",
    "暗属性共鸣时，暗属性角色发动技能时，自身立即获得强化弹射效果",
    "每发动3次强化弹射（含额外触发），自身“回响”＋2层",
    # 2026-09-27 第二批平衡：累计命中成长 50% → 5%；能力里回响每层的无上限成长搬进队长（每层 2.5%）。
    # 第三轮平衡（成长复核）：累计命中 5% → 35%，回响每层 2.5% → 20%。
    # 无上限按裁决 §3 写到效果为止（不写「最多99层」「可无限」）。
    "强化弹射每累计命中4次，自身攻击力＋35%",
    "每1层“回响”，自身强化弹射伤害＋20%、攻击力＋20%",
    "冲刺时，立即获得强化弹射效果（冷却时间：1.5秒）",
))

PANEL_ABILITY = {
    1: "\n".join(("战斗开始时，自身技能槽＋100%",
                  "持有贯穿效果期间，自身直接攻击变为3次")),
    # 2026-09-27 第三轮（wf_balance_20260927c_hibiki）面板同条件合并：#0/#1 数据条件逐格相同 ⇒ 两行并一行。
    # 强化弹射伤害（战场级）原文不带对象 ⇒ 与「自身攻击力」之间用「，」（主会话统一口径 1）。
    2: "持有贯穿效果时，每发动1次强化弹射，自身攻击力＋8%，强化弹射伤害＋12%（最多25次）",
    # 2026-09-27 第二批平衡：槽 3/槽 4 的回响成长换成封顶 10 层的弱化版；攻击力那条随行落在槽 4
    # （原偏离 D-13 把它的文案挂在槽 3，封顶后两条数值不同，各自回到行所在的槽）。
    3: "\n".join(("暗属性共鸣时，每发动1次强化弹射，自身获得1层“回响”",
                  "每1层“回响”，自身强化弹射伤害＋10%（最多10层）",
                  "每1层“回响”，强化弹射伤害额外乘区＋5%（最多5层）")),
    # 第三轮面板同条件合并：#0/#1（持续·持有贯穿）两行并一行，回响那行不动。
    4: "\n".join(("持有贯穿效果期间，自身攻击力＋200%，强化弹射伤害＋150%",
                  "每1层“回响”，自身攻击力＋5%（最多10层）")),
    5: "强化弹射伤害额外乘区＋30%",
    6: "\n".join(("持有贯穿效果期间，暗属性角色攻击力＋50%",
                  "暗属性角色技能充能速度＋10%",
                  "每1层“回响”，暗属性角色攻击力＋15%（最多5层）")),
}


def slot_override_text(slot: int) -> str:
    """槽的 ``desc_override`` 正文：仅主位的槽每行自带 Ⓜ（`PANEL_ABILITY` 保持作者原文）。"""
    prefix = MAIN_ICON if slot in MAIN_ONLY_SLOTS else ""
    return "\n".join(prefix + line for line in PANEL_ABILITY[slot].split("\n"))


CAS_TEXTS = {
    CAS_PF: "赋予自身特殊强化弹射",
    CAS_INVOKE_SKILL: "立即获得强化弹射效果",
    CAS_INVOKE_DASH: "立即获得强化弹射效果（冷却时间：1.5秒）",
    CAS_LEADER: PANEL_LEADER,
    **{CAS_ABILITY[slot]: slot_override_text(slot) for slot in range(1, 7)},
}

SPEC = {
    "required_capabilities": ("dash-parameter-v1", "panel-description-override-v2", "damage-type-rules-v1"),
    "extra_keys": {
        MS.UNIQUE_CONDITION_LOGICAL: (UID,),
        PFA: (PF_KEY,),
        KL.CAS: tuple(CAS_TEXTS),
        KL.SWITCHED: (VOICE_KEY,),
    },
}

# ---------------------------------------------------------------- 行计划
# 形状：(donor 地址, donor 来源, {列号: 值}, 预期 wf_describe 回读)。列号与 ``#N`` 都是 0 基。
# leader 124 列 / ability 126 列。describe 是「机器渲染回读」，面板上真正显示的是
# PANEL_LEADER / PANEL_ABILITY（desc_override 接管），两者不必一致。

_PRE_RES_L = {4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN}   # leader 前置 1：暗共鸣
#: donor 自带的前置块残值（组列会留下别人的元素 token）一律清干净。
_CLR_PRE_A = {6: "0", 9: "", 10: "", 11: "", 13: "0", 20: "0"}

# ---- 2026-09-27 第二批平衡（口径 A.2/A.3/A.7）：回响每层成长
#: 队长侧每层强度：第二批 3 分钟回响约 99 层（≥30 次）⇒ 原 25%/层 ×1/10 ＝ 2.5%/层；
#: 第三轮（``wf_balance_20260927c_hibiki``）按 2/3 回调：25×2/3=16.7 → 不低于 2/3 的 5 的倍数 20%/层（PF 伤害与攻击力同精度）。
ECHO_LEADER_STEP = "20000"
#: 队长 L7「全等级 PF 累计命中每 4 次 → 自身攻击力」：第二批 50% → 5%，第三轮按 2/3 回调 50×2/3=33.3 → 35%。
HIT_ATTACK_STEP = "35000"
#: 能力侧封顶版的层数上限（during 134 c102）；槽 3 PF 伤害 10%/层、槽 4 攻击力 5%/层。
ECHO_ABILITY_CAP = "10"
#: 能力行 ``[CODE, '0', ''] + 能力行[5:]``（能力列 c≥5 → 队长 c−2）搬进队长后的 during-134 公共格：
#: 无前置、puller 0 = 自身、阈值 1 层、上限照抄 99（＝固有上限）、计数源 = 回响。
_ECHO_GROWTH_L = {0: CODE, 1: "0", 3: "1", 4: "0", 11: "0", 18: "0", 83: "(None)",
                  95: "134", 96: "0", 98: "100000", 99: "100000", 100: UNIQUE_CAP, 102: UID,
                  106: "false", 108: "0"}

LEADER: tuple[tuple[str, str, dict[int, str], str | None], ...] = (
    # L0 722 专属强化弹射（无前置：挂门 = 群友报的「PF 没实装」）
    # 2026-09-27 第二批平衡：donor 菲莉亚 159996#3 本批 c49/c50 50000 → 7000
    # （wf_balance_20260927b_philia）。这里把 donor 的全部非空列都按当前 live 值钉死
    # （c7/c8/c9 是 c4=0 关掉的前置块残值，c28/c29/c32/c33 是触发块残值，c49/c50 是本行 722 的 50%），
    # 让本行只从 donor 取列宽，不再跟 donor 漂移；输出与 live 逐字相同。
    ("159996#3", "live",
     {0: CODE, 1: "0", 3: "0", 4: "0", 7: "600000", 8: "600000", 9: "White", 11: "0", 18: "0",
      25: "0", 28: "100000", 29: "100000", 32: "(None)", 33: "0", 37: "(None)", 44: "0",
      45: "722", 49: "50000", 50: "50000", 80: PF_KEY, 81: "1,2,3", 82: CAS_PF},
     "开局≥1 → 自身 强化弹射覆盖 50%"),
    # L1 贯通中 → 全队(暗) 攻击力 300%
    ("161153#0", "official",
     {0: CODE, 1: "0", 3: "1", 4: "0", 11: "0", 18: "0", 83: "(None)", 95: "30",
      106: "false", 107: "0", 108: "5", 109: ELEMENT_TOKEN, 111: "300000", 112: "300000"},
     "持续·状态贯通 → 赋予全队(暗) 攻击力 300%"),
    # L2 贯通中 → 自身 PF 伤害 200%
    ("161153#1", "official",
     {0: CODE, 1: "0", 3: "1", 4: "0", 11: "0", 18: "0", 83: "(None)", 95: "30",
      106: "false", 107: "23", 111: "200000", 112: "200000"},
     "持续·状态贯通 → 自身 强化弹射伤害 200%"),
    # L3 暗共鸣 → 贯通延长 30%
    ("161153#2", "official",
     {0: CODE, 1: "0", 3: "0", 4: "0", 11: "2", 14: "600000", 15: "600000",
      16: ELEMENT_TOKEN, 18: "0", 25: "0", 37: "(None)", 44: "0", 45: "190",
      49: "30000", 50: "30000"},
     "暗·编成≥6 时: 自身 贯通延长 30%"),
    # 每 3 次 PF → 同一回响计数 +2。number=1、initial_multiply=2，避免分裂成两枚图标。
    ("111183#3", "official",
     {0: CODE, 1: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "2", 26: "0",
      28: "300000", 29: "300000", 32: "(None)", 33: "0", 37: "(None)", 44: "0",
      45: "461", 46: "0", 49: "100000", 50: "100000", 57: "100000", 58: "100000",
      66: UID, 72: "2", 73: "0"},
     "强化弹射≥3 → 自身 状态固有 100%×1次"),
    # ---------------- rework1 新增 ----------------
    # L6 暗共鸣 + 暗属性角色发动技能时 → 629 PF 追击（官方同形 141111#1：trig23 / puller5 / 组）
    ("169999#4", "live",
     {0: CODE, 1: "0", 2: "0", 3: "0", **_PRE_RES_L, 11: "0", 18: "0", 25: "23",
      26: "5", 27: ELEMENT_TOKEN, 28: "100000", 29: "100000", 32: "(None)", 33: "0",
      37: "(None)", 44: "0", 45: "629", 46: "0", 68: CAS_INVOKE_SKILL, 69: INVOKE_PROGRAM},
     "暗·编成≥6 时: 技能发动≥1 → 自身 发动技能动作[%s]" % CAS_INVOKE_SKILL),
    # L7 同一全等级 PF 命中池，每累计4次 → 自身攻击力。仍不限次（c32=(None)）。
    # 2026-09-27 第二批平衡：3 分钟约 30–75 次（≥30）⇒ ×1/10：50% → 5%；第三轮按 2/3 回调到 35%。
    ("131182#1", "official",
     {0: CODE, 1: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "15", 28: "400000",
      29: "400000", 32: "(None)", 33: "0", 37: "(None)", 44: "0", 45: "32", 46: "0",
      47: "", 49: HIT_ATTACK_STEP, 50: HIT_ATTACK_STEP},
     f"强化弹射HitLv1≥4 → 自身 攻击力 {int(HIT_ATTACK_STEP) // 1000}%"),
    # L8 冲刺时（CT 1.5 秒）→ 629 PF 追击（donor 原样就是 trig4+CT，只改 CT 与字符串键）
    ("169999#4", "live",
     {0: CODE, 1: "0", 2: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "4", 26: "0",
      28: "100000", 29: "100000", 32: "(None)", 33: "90", 37: "(None)", 44: "0",
      45: "629", 46: "0", 68: CAS_INVOKE_DASH, 69: INVOKE_PROGRAM},
     "冲刺≥1(CT1.5秒) → 自身 发动技能动作[%s]" % CAS_INVOKE_DASH),
    # 与两条 629 的门槛/拉取目标/冷却完全相同，每次追加只向公共 PF 次数池加 1。
    # 原生 248 -> CountUp(0)；trigger2 读取 Count(0)，不是多段命中的 trigger15。
    ("141147#1", "official",
     {0: CODE, 1: "0", 2: "0", 3: "0", **_PRE_RES_L, 11: "0", 18: "0", 25: "23",
      26: "5", 27: ELEMENT_TOKEN, 28: "100000", 29: "100000", 32: "(None)", 33: "0",
      37: "(None)", 44: "0", 45: "248", 49: "100000", 50: "100000"},
     "暗·编成≥6 时: 技能发动≥1 → 自身 计数+强化弹射 100%"),
    ("141147#1", "official",
     {0: CODE, 1: "0", 2: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "4", 26: "0",
      28: "100000", 29: "100000", 32: "(None)", 33: "90", 37: "(None)", 44: "0",
      45: "248", 49: "100000", 50: "100000"},
     "冲刺≥1(CT1.5秒) → 自身 计数+强化弹射 100%"),
    # ---------------- 2026-09-27 第二批平衡：回响每层的无上限成长（原槽 3 #1 / 槽 4 #2）搬进队长 ----------------
    # 格子 ＝ 原能力行 [5:] 左移 2 列（口径 A.3），只把强度 25% 降到 2.5%（第三轮回调到 20%，见 ECHO_LEADER_STEP）。
    # donor 取官方 veteran_hunter_3anv 的
    # during 行 161153#1（L2 已用同一 donor，其非空列全部被覆盖）；队长 during 134 官方 7 行先例（161063#2 = 134 → kind 0 自身），
    # kind 23 官方 5 行 / live 稻穗 139995#4、丝缇涅尔 169995#6 在 134 上有先例，不属于零先例。
    # 队长里原本没有 during 134 行 ⇒ 无可合并对象，新起两行。
    ("161153#1", "official",
     {**_ECHO_GROWTH_L, 107: "23", 111: ECHO_LEADER_STEP, 112: ECHO_LEADER_STEP},
     f"持续·状态累积计数固有≥1(限99次)[固有16998801] → 自身 强化弹射伤害 {int(ECHO_LEADER_STEP) / 1000:g}%"),
    ("161153#1", "official",
     {**_ECHO_GROWTH_L, 107: "0", 111: ECHO_LEADER_STEP, 112: ECHO_LEADER_STEP},
     f"持续·状态累积计数固有≥1(限99次)[固有16998801] → 自身 攻击力 {int(ECHO_LEADER_STEP) / 1000:g}%"),
)
LEADER_ROWS = len(LEADER)

#: 每槽的 c1 主位限制与 c2 雕像组（一键单值；c2 只喂 ability_statue_group 的颜色/图标/形象三列）。
#: c1 由 `MAIN_ONLY_SLOTS` 派生 ⇒ 整键单值，不会出现「有的行限、有的行不限」。
_UNISONABLE = {slot: ("false" if slot in MAIN_ONLY_SLOTS else "true") for slot in range(1, 7)}
_STATUE = {1: "action_skill", 2: "power_flip", 3: "power_flip",
           4: "attack_common", 5: "attack_common", 6: "attack_black"}

PLAN: dict[int, tuple[tuple[str, str, dict[int, str], str | None], ...]] = {
    1: (("1611533#0", "official",
         {3: "0", 5: "0", **_CLR_PRE_A, 27: "0", 39: "(None)", 46: "0", 47: "211", 48: "0",
          51: "100000", 52: "100000"},
         "自身 技能槽 100%"),
        ("1611533#1", "official",
         {3: "0", 5: "1", **_CLR_PRE_A, 85: "(None)", 97: "30", 108: "false", 109: "46",
          110: "0", 113: "0", 114: "0"},
         "持续·状态贯通 → 自身 DirectAttack3 0%")),
    # rework1：作者「能力 2 的数值翻倍」4%→8% / 6%→12%
    2: (("1611532#0", "official",
         {3: "0", 5: "0", 6: "38", 13: "0", 20: "0", 27: "2", 30: "100000", 31: "100000",
          34: "25", 35: "0", 39: "(None)", 46: "0", 47: "32", 48: "0",
          51: "8000", 52: "8000"},
         "状态贯通 时: 强化弹射≥1(限25次) → 自身 攻击力 8%"),
        ("1611532#1", "official",
         {3: "0", 5: "0", 6: "38", 13: "0", 20: "0", 27: "2", 30: "100000", 31: "100000",
          34: "25", 35: "0", 39: "(None)", 46: "0", 47: "55",
          51: "12000", 52: "12000"},
         "状态贯通 时: 强化弹射≥1(限25次) → 自身 强化弹射伤害 12%")),
    # rework1：461 挂暗共鸣门；每层 PF 伤害的层数上限 5 → 99
    # 2026-09-27 第二批平衡：#1 换成封顶版（10 层 × 10% ＝ ＋100%），无上限部分在队长（每层 2.5%）
    3: (("1410813#0", "official",
         {3: "0", 5: "0", 6: "2", 9: "600000", 10: "600000", 11: ELEMENT_TOKEN, 13: "0",
          20: "0", 27: "2", 30: "100000", 31: "100000", 34: "(None)", 35: "0",
          39: "(None)", 46: "0", 47: "461", 48: "0", 51: "100000", 52: "100000",
          59: "100000", 60: "100000", 68: UID, 74: "1", 75: "0"},
         "暗·编成≥6 时: 强化弹射≥1 → 自身 状态固有 100%×1次"),
        ("1699942#0", "live",
         {3: "0", 5: "1", **_CLR_PRE_A, 85: "(None)", 97: "134", 98: "0", 100: "100000",
          101: "100000", 102: ECHO_ABILITY_CAP, 104: UID, 108: "false", 109: "23", 110: "0",
          113: "10000", 114: "10000"},
         "持续·状态累积计数固有≥1(限10次)[固有16998801] → 自身 强化弹射伤害 10%"),
        ("1599971#4", "live",
         {3: "0", 5: "1", **_CLR_PRE_A, 85: "(None)", 97: "134", 98: "0", 100: "100000",
          101: "100000", 102: "5", 104: UID, 108: "false", 109: "413",
          113: "5000", 114: "5000"},
         "持续·状态累积计数固有≥1(限5次)[固有16998801] → 自身 独立乘区强化弹射伤害 5%")),
    # rework1 新增第 3 条：每层回响 → 自身攻击力 25%（面板文案挂在槽 3，行落槽 4，见偏离 D-13）
    # 2026-09-27 第二批平衡：#2 换成封顶版（10 层 × 5% ＝ ＋50%），文案回到槽 4；无上限部分在队长（每层 2.5%）
    4: (("1611531#0", "official",
         {3: "0", 5: "1", **_CLR_PRE_A, 85: "(None)", 97: "30", 108: "false", 109: "0",
          110: "0", 113: "200000", 114: "200000"},
         "持续·状态贯通 → 自身 攻击力 200%"),
        ("1611531#1", "official",
         {3: "0", 5: "1", **_CLR_PRE_A, 85: "(None)", 97: "30", 108: "false", 109: "23",
          113: "150000", 114: "150000"},
         "持续·状态贯通 → 自身 强化弹射伤害 150%"),
        ("1699942#0", "live",
         {3: "0", 5: "1", **_CLR_PRE_A, 85: "(None)", 97: "134", 98: "0", 100: "100000",
          101: "100000", 102: ECHO_ABILITY_CAP, 104: UID, 108: "false", 109: "0", 110: "0",
          111: "", 113: "5000", 114: "5000"},
         "持续·状态累积计数固有≥1(限10次)[固有16998801] → 自身 攻击力 5%")),
    # rework1：新增常驻 413（＝作者「能力 5 替换为强化弹射伤害额外乘区 +30%」）；
    # 原 4 条 422 冲刺参数行保留（效果不变），文案移进队长块。
    5: (("1699991#2", "live",
         {3: "0", 5: "1", **_CLR_PRE_A, 85: "(None)", 97: "1", 98: "0", 100: "100000",
          101: "100000", 108: "false", 109: "413", 110: "0", 113: "30000", 114: "30000",
          118: ""},
         "持续·HP≤1 → 自身 独立乘区强化弹射伤害 30%"),
        ("1699991#2", "live",
         {3: "0", 5: "1", 6: "42", 13: "0", 20: "0", 85: "(None)", 97: "1", 98: "0",
          100: "100000", 101: "100000", 108: "false", 109: "422", 110: "0",
          113: "100000", 114: "100000", 118: "1"},
         "队长 时: 持续·HP≤1 → 自身 冲刺参数(可调) 100%"),
        ("1699991#6", "live",
         {3: "0", 5: "1", 6: "42", 13: "0", 20: "0", 85: "(None)", 97: "1", 98: "0",
          100: "100000", 101: "100000", 108: "false", 109: "422", 110: "0",
          113: "-30000", 114: "-30000", 118: "0"},
         "队长 时: 持续·HP≤1 → 自身 冲刺参数(可调) -30%"),
        ("1699991#4", "live",
         {3: "0", 5: "1", 6: "42", 13: "0", 20: "0", 85: "(None)", 97: "1", 98: "0",
          100: "100000", 101: "100000", 108: "false", 109: "422", 110: "0",
          113: "-35000", 114: "-35000", 118: "3"},
         "队长 时: 持续·HP≤1 → 自身 冲刺参数(可调) -35%"),
        ("1699991#3", "live",
         {3: "0", 5: "1", 6: "42", 13: "0", 20: "0", 85: "(None)", 97: "1", 98: "0",
          100: "100000", 101: "100000", 108: "false", 109: "422", 110: "0",
          113: "40000", 114: "40000", 118: "6"},
         "队长 时: 持续·HP≤1 → 自身 冲刺参数(可调) 40%"),
        swift_guard_plan(CODE, -30000, metadata=False)),
    6: (("1611472#0", "official",
         {3: "0", 5: "1", **_CLR_PRE_A, 85: "(None)", 97: "30", 108: "false", 109: "0",
          110: "5", 111: ELEMENT_TOKEN, 113: "50000", 114: "50000"},
         "持续·状态贯通 → 赋予全队(暗) 攻击力 50%"),
        ("2110026#0", "official",
         {3: "0", 5: "0", **_CLR_PRE_A, 27: "0", 39: "(None)", 46: "0", 47: "35",
          48: "5", 49: ELEMENT_TOKEN, 51: "10000", 52: "10000"},
         "赋予全队(暗) 技能槽充能 10%"),
        ("1699942#1", "live",
         {3: "0", 5: "1", **_CLR_PRE_A, 85: "(None)", 97: "134", 98: "0", 100: "100000",
          101: "100000", 102: "5", 104: UID, 108: "false", 109: "0", 110: "5",
          111: ELEMENT_TOKEN, 113: "15000", 114: "15000"},
         "持续·状态累积计数固有≥1(限5次)[固有16998801] → 赋予全队(暗) 攻击力 15%")),
}
ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
ABILITY_RECORDS = sum(len(rows) for rows in PLAN.values())

# ---------------------------------------------------------------- 行自检常量
#: 写进队长表 = 角色页 C7050（记忆 wf-dash-parameter-leader-table-trap）。
FORBIDDEN_LEADER_KINDS = ("422", "724", "713")
#: 前置 kind 白名单（裁决 §8）：2 = 元素编成、38 = 状态贯通、42 = Leader。
ALLOWED_PRECONDITION_KINDS = ("", "0", "2", "38", "42")
LEADER_INSTANT_KIND, LEADER_DURING_KIND = 45, 107
LEADER_DURING_TRIGGER, LEADER_DURING_PULLER = 95, 96
LEADER_STRING_ID, LEADER_ACTION_PATH = 68, 69
ABILITY_INSTANT_KIND, ABILITY_DURING_KIND = 47, 109
ABILITY_DURING_TRIGGER, ABILITY_DURING_PULLER = 97, 98
ABILITY_STRING_ID, ABILITY_ACTION_PATH = 70, 71


# ---------------------------------------------------------------- 设计稿镜像

def load_design(root: Path) -> dict[str, Any]:
    design = MS.load_design(Path(root), KEY)
    if not design:
        raise KitError(f"design/{KEY}.json missing (batch {MS.BATCH_DIR})")
    if design.get("schema") != "ma-design/1" or design.get("cid") != CID or design.get("code") != CODE:
        raise KitError(f"design identity drift: {design.get('schema')} {design.get('cid')} {design.get('code')}")
    return design


def design_problems(design: dict[str, Any]) -> list[str]:
    """设计稿的 ``plan_rework1`` 必须镜像本模块的计划（漂移当场报）。"""
    plan = design.get("plan_rework1")
    if not isinstance(plan, dict):
        return ["design has no plan_rework1 block"]
    problems: list[str] = []
    if int(plan.get("leader_rows", -1)) != LEADER_ROWS:
        problems.append(f"leader row count mirror drift: {plan.get('leader_rows')}")
    if int(plan.get("ability_records", -1)) != ABILITY_RECORDS:
        problems.append(f"ability record count mirror drift: {plan.get('ability_records')}")
    want_slots = {str(slot): len(PLAN[slot]) for slot in range(1, 7)}
    if {str(k): int(v) for k, v in (plan.get("ability_rows_by_slot") or {}).items()} != want_slots:
        problems.append(f"per-slot mirror drift: {plan.get('ability_rows_by_slot')}")
    if sorted(plan.get("custom_ability_string") or []) != sorted(CAS_TEXTS):
        problems.append(f"custom_ability_string mirror drift: {plan.get('custom_ability_string')}")
    if sorted(plan.get("ability_skill_programs") or []) != [INVOKE_PROGRAM]:
        problems.append(f"ability_skill program mirror drift: {plan.get('ability_skill_programs')}")
    unique = plan.get("unique_conditions") or {}
    if str(unique.get("key")) != UID or str(unique.get("cap")) != UNIQUE_CAP:
        problems.append(f"unique_condition mirror drift: {unique}")
    if sorted(plan.get("required_capabilities") or []) != sorted(SPEC["required_capabilities"]):
        problems.append(f"capability mirror drift: {plan.get('required_capabilities')}")
    energy = plan.get("skills", {}).get("energy") or {}
    if {k: dict(v) for k, v in energy.items()} != SKILL_ENERGY:
        problems.append(f"skill energy mirror drift: {energy}")
    return problems


# ---------------------------------------------------------------- 树工具（philia 的纯函数 + 本地补洞）

#: philia 的 ``SUBJECT_SLOTS`` 没收录 DeleteCondition（它不出现在光剑树里）；
#: 荷莉的队伍块靠它解弱体，漏重映射会留下悬空主体 id。
EXTRA_SUBJECT_SLOTS = {"DeleteCondition": (1,)}


def remap_subjects(node, mapping) -> None:
    PH.remap_subjects(node, mapping)
    for name, slots in EXTRA_SUBJECT_SLOTS.items():
        for cmd in PH.cmds(node, name):
            for i in slots:
                value = cmd[i]
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    cmd[i] = mapping(value)


def one_cmd(node, name: str) -> list:
    hits = PH.cmds(node, name)
    if len(hits) != 1:
        raise KitError(f"expected exactly one {name}, got {len(hits)}")
    return hits[0]


def ac_node(cmd: list, kind: str) -> list:
    """``CreateCondition`` 第 2 参里的 AdditionalCondition 节点。"""
    hits = [entry for entry in cmd[2] if isinstance(entry, list) and entry and entry[0] == kind]
    if len(hits) != 1:
        raise KitError(f"CreateCondition carries {len(hits)} {kind} entries")
    return hits[0]


def conditional_names(node, out: set[str] | None = None) -> set[str]:
    out = set() if out is None else out
    if isinstance(node, list):
        if node and isinstance(node[0], str) and node[0].startswith("Conditionals"):
            out.add(node[0])
        for child in node:
            conditional_names(child, out)
    return out


def count_ac_flying(node) -> int:
    """树里还剩几条 ``ACFlying`` 的 ``CreateCondition``（rework1 反馈轮 3：作者要求撤浮游后的全包核对）。"""
    return len([c for c in PH.cmds(node, "CreateCondition") if c[2] and c[2][0][0] == "ACFlying"])


def dsl_problems(tree, *, element: int | None = ELEMENT) -> list[str]:
    """DSL 门禁：客户端合法性三件套 + 参数形状 + 表达式外壳 + 严格作用域 + 主体 id 不重复。"""
    problems: list[str] = []
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if element is not None:
        problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, element)]
    problems += [f"signature: {p}" for p in PH.signature_problems(tree)]
    problems += [f"expr: {p}" for p in PH.expr_tag_problems(tree)]
    problems += [f"scope: {p}" for p in PH.scope_problems(tree)]
    ids = PH.bound_ids(tree)
    if len(ids) != len(set(ids)):
        problems.append(f"duplicate bound subject ids: {sorted(i for i in set(ids) if ids.count(i) > 1)}")
    bad = sorted(n for n in conditional_names(tree) if n.startswith("ConditionalsNumExecutions"))
    if bad:
        problems.append(f"ConditionalsNumExecutions* must not appear: {bad}")
    return problems


def source_tree(ctx, program: str, want_sha: str | None = None):
    logical = wf_dsl.dsl_logical(program)
    raw = ctx.official_read(logical, "common")
    if raw is None:
        raise KitError(f"official baseline lacks donor DSL {program}")
    if want_sha is not None and C.sha256(raw) != want_sha:
        raise KitError(f"donor DSL fingerprint drift: {program} -> {C.sha256(raw)}")
    return ctx.template_dsl(program)


def write_dsl_checked(ctx, program: str, tree) -> str:
    """``write_dsl`` 只吃裸树；写后回读比对（记忆卡 wf-dsl-encode-wrapper-trap：喂包装壳 = 进战斗 F1034）。"""
    if not (isinstance(tree, list) and tree and tree[0] == "ActionDsl"):
        raise KitError(f"write_dsl needs a bare ActionDsl tree, got {type(tree).__name__}")
    logical = ctx.write_dsl(program, tree)
    back = C.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
    if back != tree:
        raise KitError(f"DSL readback mismatch: {logical}")
    return logical


# ---------------------------------------------------------------- 固有状态图标

def draw_icon(frame):
    """48×48「回响」图标：深紫圆角底 + 白紫音符 + 两圈同心声波弧 + 右上月牙缺口。

    8× 画布绘制后 LANCZOS 缩回 48×48；alpha 取官方图标外框（与上批 unique_condition 图标同工艺）。
    """
    from PIL import Image, ImageDraw
    if frame.size != (48, 48):
        raise KitError(f"icon frame donor must be 48x48, got {frame.size}")
    K, N = 8, 48 * 8
    layer = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    top, bot = (35, 28, 58), (20, 15, 38)                 # #231C3A → 更深的紫
    grad = Image.new("RGBA", (1, N))
    for y in range(N):
        t = y / (N - 1)
        grad.putpixel((0, y), tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    grad = grad.resize((N, N))
    inner = Image.new("L", (N, N), 0)
    ImageDraw.Draw(inner).rounded_rectangle((3 * K, 3 * K, 45 * K - 1, 45 * K - 1), radius=6 * K, fill=255)
    layer.paste(grad, (0, 0), inner)
    d = ImageDraw.Draw(layer)
    arc_far, arc_near = (167, 123, 255, 255), (231, 216, 255, 255)
    note, gold = (247, 242, 255, 255), (231, 196, 106, 255)

    # 两圈同心声波弧（左下 → 右上开口），外圈更淡
    for radius, color, width in ((17.0, arc_far, 2.0), (12.0, arc_near, 2.0)):
        box = ((24 - radius) * K, (25 - radius) * K, (24 + radius) * K, (25 + radius) * K)
        d.arc(box, start=205, end=335, fill=color, width=int(width * K))
    # 中心音符：符头 + 符干 + 符尾
    d.ellipse((15.0 * K, 28.0 * K, 24.0 * K, 35.0 * K), fill=note)
    d.line(((23.0 * K, 31.5 * K), (23.0 * K, 12.5 * K)), fill=note, width=int(2.2 * K))
    d.line(((23.0 * K, 12.5 * K), (32.5 * K, 17.0 * K), (32.5 * K, 22.0 * K)),
           fill=note, width=int(2.2 * K), joint="curve")
    # 右上小月牙缺口
    d.ellipse((33.0 * K, 7.0 * K, 43.0 * K, 17.0 * K), fill=gold)
    d.ellipse((35.4 * K, 6.2 * K, 45.4 * K, 16.2 * K), fill=(0, 0, 0, 0))

    small = layer.resize((48, 48), Image.LANCZOS)
    out = Image.new("RGBA", (48, 48), (255, 255, 255, 0))
    fp, op, sp = frame.load(), out.load(), small.load()
    for y in range(48):
        for x in range(48):
            r, g, b, a = sp[x, y]
            fa = fp[x, y][3]
            if a:
                op[x, y] = (round((r * a + 255 * (255 - a)) / 255), round((g * a + 255 * (255 - a)) / 255),
                            round((b * a + 255 * (255 - a)) / 255), fa)
            else:
                op[x, y] = (255, 255, 255, fa)
    return out


def install_unique_icon(ctx) -> dict[str, Any]:
    frame_raw = ctx.official_read(UNIQUE_ICON_FRAME)
    if frame_raw is None:
        _root, frame_raw, _how = ctx.pack.template_asset(UNIQUE_ICON_FRAME)
    frame = ctx.png_open(frame_raw)
    data = ctx.png_store_bytes(draw_icon(frame))
    ctx.write_asset("common", UNIQUE_ICON_LOGICAL, data)
    back = ctx.png_open(ctx.pack.pkg_path("common", UNIQUE_ICON_LOGICAL).read_bytes())
    if back.size != (48, 48) or back.getchannel("A").tobytes() != frame.getchannel("A").tobytes():
        raise KitError("unique_condition icon size/alpha differ from the official frame donor")
    return {"logical": UNIQUE_ICON_LOGICAL, "frame_donor": UNIQUE_ICON_FRAME,
            "size": list(back.size), "sha256": C.sha256(data), "bytes": len(data)}


# ---------------------------------------------------------------- 技能 DSL

def build_skill_tree(ctx, level: str, family: dict[str, Any]):
    """三个官方母本拼一棵：骨架/演出/回响（母本）+ 音场判定区与自身攻击（威隆）+ 队伍块（荷莉）。"""
    params = SKILL_PARAMS[level]
    tpl = copy.deepcopy(source_tree(ctx, SKILL_DONORS["template"]))
    field_src = source_tree(ctx, SKILL_DONORS["field"])
    team_src = source_tree(ctx, SKILL_DONORS["team"])
    for name, tree in (("template", tpl), ("field", field_src), ("team", team_src)):
        if tree[0] != "ActionDsl" or tree[10] != 0:
            raise KitError(f"{name} donor head drift: {tree[:2]} bta={tree[10]}")
    body = tpl[11][1]
    if tpl[1] != 1:
        raise KitError(f"template movementPriority drift: {tpl[1]}")

    # --- 0/1/2：停球 + 背景演出 + 前景演出（原样）
    stop = PH.find_one(body, PH.is_cmd("StopBall"), "母本 StopBall")
    shows = [e for e in body if e[0] == "Command" and e[1][0] == "ShowEffect"]
    if len(shows) != 2:
        raise KitError(f"template root carries {len(shows)} ShowEffect (want 背景演出 + EF演出)")
    show_back, show_ef = (copy.deepcopy(e) for e in shows)
    for node, base in ((show_back, FX_BACK), (show_ef, FX_EF)):
        path = node[1][2]
        if path[0] != "SpecifyEffectDirectly" or path[1] != f"{FX_SRC_DIR}/{base}":
            raise KitError(f"template ShowEffect path drift: {path}")

    # --- 3：月光音场（唯一伤害块）
    field = PH.find_one(field_src[11][1],
                        lambda e: e[0] == "Event" and e[1][0] == "Wait" and e[1][1] == 44,
                        "威隆 Event Wait(44) 音场块")
    field[1][1] = FIELD_WAIT
    cha = one_cmd(field, "CreateHitArea")
    if cha[2] != -18 or cha[24] != 0:
        raise KitError(f"音场 CreateHitArea drift: p1={cha[2]} p23={cha[24]}")
    remap_subjects(field, {7: FIELD_SUBJECT_BASE, 8: FIELD_SUBJECT_BASE + 1,
                           9: FIELD_SUBJECT_BASE + 2}.__getitem__)
    aura = one_cmd(field, "ShowEffect")
    # 领域演出复用母本 _back（威隆族不克隆，省 0.161 Mpx 战斗图集 —— 设计 D-7）
    aura[2] = ["SpecifyEffectDirectly", f"{FX_SRC_DIR}/{FX_BACK}"]
    cna = one_cmd(field, "CreateNormalAttack")
    if cna[2] != 255:
        raise KitError(f"音场 CNA 显式元素 {cna[2]}（应保留 255 继承角色属性）")
    cna[6] = PH.slv(*params["field"])
    cna[15] = ["Fine"]                       # 命中演出 → 官方枚举（同树炸弹段原值）

    # --- 4：自身攻击力
    self_atk = PH.find_one(field_src[11][1], PH.is_cmd("CreateCondition"), "威隆 自身攻击力 CreateCondition")
    cc = self_atk[1]
    if cc[1] != -17:
        raise KitError(f"自身攻击力 CreateCondition 主体 {cc[1]}（应为 -17）")
    ac_node(cc, "ACAttackPoint")[2] = PH.slv(*params["self_atk"])

    # --- 5：队伍块（PF 伤害 + 贯穿 + 两段解弱体）
    team = PH.find_one(team_src[11][1], PH.is_find_all(97), "荷莉 FindAllSubjects(97) 队伍块")
    remap_subjects(team, {0: TEAM_SUBJECT_BASE, 1: TEAM_SUBJECT_BASE + 1,
                          2: TEAM_SUBJECT_BASE + 2}.__getitem__)
    pfdmg = next(c for c in PH.cmds(team, "CreateCondition") if c[2][0][0] == "ACPowerFlipDamage")
    pierce = next(c for c in PH.cmds(team, "CreateCondition") if c[2][0][0] == "ACPiercing")
    for cmd in (pfdmg, pierce):
        if cmd[10] != 2:                     # 97 = 球 ⇒ 付与对象种类写 2（记忆卡 wf-createcondition-target-kind）
            raise KitError(f"队伍块 CreateCondition 付与对象种类 {cmd[10]}（应为 2）")
    node = ac_node(pfdmg, "ACPowerFlipDamage")
    node[1] = PH.slv(TEAM_PFDMG_FRAMES, TEAM_PFDMG_FRAMES)
    node[2] = PH.slv(*params["team_pfdmg"])
    ac_node(pierce, "ACPiercing")[1] = PH.slv(*params["pierce"])
    if len(PH.cmds(team, "DeleteCondition")) != 2:
        raise KitError("队伍块解弱体段数漂移（应为两段 DeleteCondition(DCAll,3)）")

    # --- 6：回响 +1 层（拆出 CreateCondition，丢掉外层 FindAllSubjects(1,114) 选择器）
    echo_src = PH.find_one(body, PH.is_find_all(114), "母本 FindAllSubjects(114) 回响块")
    echo = copy.deepcopy(one_cmd(echo_src, "CreateCondition"))
    if echo[10] != 3:                        # 自身/Member ⇒ 付与对象种类写 3
        raise KitError(f"回响 CreateCondition 付与对象种类 {echo[10]}（应为 3）")
    echo[1] = -17
    unique = ac_node(echo, "ACUnique")
    if unique[1] != 16:
        raise KitError(f"回响 donor ACUnique id {unique[1]}（母本应为 16）")
    unique[1] = int(UID)

    tpl[11][1] = [stop, show_back, show_ef, field, self_atk, team, ["Command", echo]]
    tree, info = ctx.rewrite_effect_refs(tpl, family, strict=True)
    paths = sorted(set(PH.spec_paths(tree)))
    stray = [p for p in paths if not p.startswith(FX_DST_DIR + "/")]
    if stray:
        raise KitError(f"skill {level}: 特效引用不在克隆族内: {stray}")
    problems = dsl_problems(tree)
    if problems:
        raise KitError(f"skill {level} DSL gates failed: {problems}")
    # rework1 反馈轮 3 全包核对：技能树母本（161183/veteran_hunter_3anv/herbalist_xm22）不带 ACFlying。
    skill_fly = count_ac_flying(tree)
    if skill_fly:
        raise KitError(f"skill {level}: 树里残留 {skill_fly} 条 ACFlying（浮游已撤，不该再出现）")
    return tree, {"level": level, "fx_paths": paths, "effect_rewrites": info["rewritten"],
                  "bound_ids": sorted(set(PH.bound_ids(tree))),
                  "n_attacks": len(PH.cmds(tree, "CreateNormalAttack")),
                  "ac_flying_count": skill_fly,
                  "multipliers": {k: list(v) for k, v in params.items()}}


# ---------------------------------------------------------------- 专属强化弹射（722）

def strip_ac_flying(block: list) -> int:
    """从 P1 辅助增益块删掉浮游那条 ``CreateCondition``（rework1 反馈轮 3：作者 09-21 要求撤浮游）。

    调用方必须先核对 donor 是「``FindAllSubjects(33)`` 包着恰好 ``ACAttackPoint / ACPiercing /
    ACFlying`` 三条 ``CreateCondition``」的原形态（``build_pf_tree`` 里的 ``kinds_before`` 门禁，
    以及 ``PH.pf_support_block`` 自带的同款校验）——donor 漂移必须在那一步就炸，不能在这里悄悄放行。
    这里只做单一动作：摘掉 ``ACFlying`` 那一条，``ACAttackPoint`` / ``ACPiercing`` 原样保留、
    绑定 id 与参数都不碰。返回删掉的条数（恒为 1，供上层写进 gates 报告）。
    """
    find_all = block[1]
    if find_all[0] != "FindAllSubjects" or find_all[2] != 33:
        raise KitError(f"supporter 辅助增益块外层漂移: {find_all[:3]}")
    body_wrap = find_all[9]
    if not (isinstance(body_wrap, list) and body_wrap and body_wrap[0] == "Block"):
        raise KitError(f"supporter 辅助增益块 body 漂移: {body_wrap}")
    body = body_wrap[1]

    def is_flying(entry) -> bool:
        return (isinstance(entry, list) and len(entry) == 2 and entry[0] == "Command"
                and entry[1][0] == "CreateCondition" and entry[1][2]
                and entry[1][2][0][0] == "ACFlying")

    hits = [entry for entry in body if is_flying(entry)]
    if len(hits) != 1:
        raise KitError(f"supporter 辅助增益块 ACFlying 条数 {len(hits)}（应恰好 1 条）")
    body[:] = [entry for entry in body if not is_flying(entry)]
    return len(hits)


def build_pf_tree(ctx, level: int):
    """官方 ``special_lv{n}`` 整树作底座（sha 锁定）+ 官方 supporter 辅助增益块；倍率统一 ×``PF_SCALE``。

    rework1 反馈轮 3（作者 09-21「澄波响去掉浮游效果」）：辅助增益块里的 ``ACFlying`` 那条
    ``CreateCondition`` 整条删掉，``ACAttackPoint`` / ``ACPiercing`` 原样保留、绑定/参数不动。
    ``PH.pf_support_block`` 是与菲莉亚共用的读代码（同一批反馈、同一处理点，本模块不改那个文件）：
    它若已经在源头删掉 ACFlying（两件套），这里就不重复删；若还没删（官方三件套原样），
    本模块自己用 :func:`strip_ac_flying` 删。两条路径终态相同，三档都过 ``kinds_after``/
    ``count_ac_flying`` 兜底校验。
    """
    tree = copy.deepcopy(source_tree(ctx, SPECIAL_PROGRAMS[level], SPECIAL_SHA[level]))
    if tree[0] != "ActionDsl" or tree[1] != 1 or tree[10] != 0:
        raise KitError(f"special lv{level} head drift: {tree[:2]} bta={tree[10]}")
    if not PH.cmds(tree, "SetPowerFilpSuppress") or not PH.cmds(tree, "NotifyPowerflipEnd"):
        raise KitError(f"special lv{level} lost SetPowerFilpSuppress / NotifyPowerflipEnd")
    root_body = tree[11][1]
    aura = [n for n, e in enumerate(root_body)
            if e[0] == "Command" and e[1][0] == "ShowEffect" and e[1][1] == "オーラ演出"]
    if len(aura) != 1:
        raise KitError(f"special lv{level} オーラ演出 not unique ({len(aura)})")

    block = PH.pf_support_block(ctx.root, level)
    # 形态校验：只认两种合法形态，别的都是漂移，当场炸——不能在下游悄悄用错的块。
    #   1) 官方三件套原样（ACAttackPoint/ACPiercing/ACFlying）：本模块自己删 ACFlying。
    #   2) 已经是删后的两件套：共享 ``wf_seasonal7_kit_philia.pf_support_block`` 本轮
    #      （反馈轮 3，菲莉亚同一处理点）已经在源头把 ACFlying 摘掉，这里不重复删、只confirm 形态。
    # 两条路径的终态相同（``kinds_after`` 必须是两件套），且都不碰共享库文件本身。
    kinds_before = [c[2][0][0] for c in PH.cmds(block, "CreateCondition")]
    if kinds_before == ["ACAttackPoint", "ACPiercing", "ACFlying"]:
        ac_flying_removed = strip_ac_flying(block)
    elif kinds_before == ["ACAttackPoint", "ACPiercing"]:
        ac_flying_removed = 0     # 共享 pf_support_block 已经删过，这里不重复删
    else:
        raise KitError(f"supporter 辅助增益块形态漂移: {kinds_before}（应为官方三件套 "
                       "ACAttackPoint/ACPiercing/ACFlying，或共享 pf_support_block 已删浮游后的"
                       "ACAttackPoint/ACPiercing 两件套；两者都不是，需要人工核查 donor 或共享库）")
    pierce = [c for c in PH.cmds(block, "CreateCondition") if c[2][0][0] == "ACPiercing"]
    if len(pierce) != 1:
        raise KitError("supporter 辅助增益块 ACPiercing not unique")
    frames = PF_PIERCE_FRAMES[level]
    ac_node(pierce[0], "ACPiercing")[1] = PH.slv(frames, frames)
    if sorted(set(PH.bound_ids(block))) != [PF_SUPPORT_BIND]:
        raise KitError(f"supporter block bound ids {sorted(set(PH.bound_ids(block)))} != [{PF_SUPPORT_BIND}]")
    # 删后形态校验：只剩 ACAttackPoint/ACPiercing，且顺序不变（rework1 反馈轮 3）。
    kinds_after = [c[2][0][0] for c in PH.cmds(block, "CreateCondition")]
    if kinds_after != ["ACAttackPoint", "ACPiercing"]:
        raise KitError(f"supporter 辅助增益块删除浮游后形态漂移: {kinds_after}")
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
    stray = sorted({p for p in PH.spec_paths(tree) if p.startswith(f"battle/effect/skill_unique/{CODE}/")})
    if stray:
        raise KitError(f"PF lv{level} 引用了包内特效（底座与辅助块的官方件必须直接引用）: {stray}")
    problems = dsl_problems(tree, element=None)   # PF 底座的 CNA 同样是 255 继承，元素检查在技能侧
    if problems:
        raise KitError(f"PF lv{level} DSL gates failed: {problems}")
    # 全树核对：special 底座本身不带 ACFlying，删完之后整棵树（不只是辅助增益块）也不该再剩。
    tree_fly = count_ac_flying(tree)
    if tree_fly:
        raise KitError(f"PF lv{level}: 整树仍残留 {tree_fly} 条 ACFlying（浮游未删干净）")
    return tree, {"level": level, "multipliers": scaled, "total": round(sum(scaled), 6),
                  "pierce_frames": frames, "support_block_bind": PF_SUPPORT_BIND,
                  "ac_flying_removed": ac_flying_removed,
                  "ac_flying_count": tree_fly,
                  "support_block_kinds": kinds_after,
                  "official_effects": sorted(set(PH.spec_paths(tree))),
                  "bound_ids": sorted(set(PH.bound_ids(tree)))}


# ---------------------------------------------------------------- 629 PF 追击树（rework1 新增）

def build_invoke_tree(ctx):
    """队长两行 629 共用的「PF 载荷树」。

    做法照斩铁 ``samurai_robot_plum``（作者 09-21 指定「沿用斩铁那一行的写法」）：官方 PF 底座里
    **只留命中块**，把两条 PF 生命周期命令留在外面 —— ``SetPowerFilpSuppress`` 会压掉玩家真正的
    拍板，``NotifyPowerflipEnd`` 在非 PF 上下文不计数（ActionEvaluator.as:5064-5078）。
    这里的命中块 = 官方 ``special_lv3`` 里 ``CollisionOfBallAndEnemy`` 分支的 ``CreateReferencePoint``
    整块（特殊演出 + 两段 ``CreateHitArea``，官方倍率 4 + 9 = 13×，锚 ``-18`` 球、坐标系 ``AB``）。

    2026-09-24：根头 133 由 damage-type-rules-v1 按 PF3 完整结算，保留原生 413 乘区。
    判定区那一位一律留 :data:`INVOKE_HITAREA_BTA` ``= 0``（它会回落到根头，不是开关）。
    作者 2026-09-24 指定倍率同本体 PF3，统一 ×4.8。两条队长 248 与 629 同门槛、同冷却，每次追加只计一次公共 PF 发动，
    不按此树的多段命中重复计数，也不伪造分档拍板事件（trigger65）。
    2026-09-27 第二批平衡：两段 ``CreateNormalAttack`` 的 p13（削韧/段）:data:`INVOKE_DOWN_SOURCE` →
    :data:`INVOKE_DOWN`（3 + 1 段 ＝ 每次 1；口径 B.3 触发 CT ≤3 秒的 629 每次 ≤1），其余节点逐字不动。
    """
    base = copy.deepcopy(source_tree(ctx, SPECIAL_PROGRAMS[3], SPECIAL_SHA[3]))
    body = base[11][1]
    collision = body[3]
    if not (collision[0] == "Event" and collision[1][0] == "CollisionOfBallAndEnemy"):
        raise KitError(f"special lv3 body[3] is not CollisionOfBallAndEnemy: {collision[:2]}")
    inner = collision[1][5][1]
    ref = inner[4]
    if not (ref[0] == "Command" and ref[1][0] == "CreateReferencePoint"):
        raise KitError(f"special lv3 hit block drift: {ref[0]}/{ref[1][0] if ref[0] == 'Command' else ''}")
    if ref[1][1] != -18 or ref[1][2] != ["AB"]:
        raise KitError(f"hit block anchor drift: subject={ref[1][1]} coordsys={ref[1][2]}")

    tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False,
            INVOKE_BTA, ["Block", [ref]]]
    for name in ("SetPowerFilpSuppress", "NotifyPowerflipEnd", "RemoveEvent", "HideEffect"):
        if PH.cmds(tree, name):
            raise KitError(f"629 载荷树残留 PF 生命周期命令 {name}")
    scaled = []
    for cna in PH.cmds(tree, "CreateNormalAttack"):
        mult = cna[6]
        if len(mult) != 1 or mult[0]["min"] != mult[0]["max"]:
            raise KitError(f"invoke CNA multiplier shape drift: {mult}")
        if cna[2] != 255:
            raise KitError(f"invoke CNA 显式元素 {cna[2]}（应保留 255 继承角色属性）")
        value = round(mult[0]["min"] * INVOKE_SCALE, 6)
        cna[6] = PH.slv(value, value)
        scaled.append(value)
        # 2026-09-27 第二批平衡（口径 B.3/B.6）：只改 p13（削韧/段），SLv 的 min/max 一起改。
        if cna[13] != PH.slv(INVOKE_DOWN_SOURCE, INVOKE_DOWN_SOURCE):
            raise KitError(f"invoke CNA p13 drift: {cna[13]} (official special_lv3 = {INVOKE_DOWN_SOURCE})")
        cna[13] = PH.slv(INVOKE_DOWN, INVOKE_DOWN)
    if len(scaled) != 2:
        raise KitError(f"invoke tree carries {len(scaled)} CreateNormalAttack (want 2)")
    segments = []
    for cha in PH.cmds(tree, "CreateHitArea"):
        mode = cha[14]
        if not (isinstance(mode, list) and len(mode) == 2 and mode[0] == "CalculatedUsingMaxNumOfHits"):
            raise KitError(f"invoke CreateHitArea hit-count drift: {mode}")
        segments.append(mode[1])
    down_total = round(sum(segments) * INVOKE_DOWN, 6)
    if segments != [3, 1] or down_total > 1:
        raise KitError(f"invoke detoughness per call {down_total} over {segments} segments (want ≤1 over [3, 1])")
    # 判定区归属位（node[24] ＝ params[23]）：0 ＝ 不覆盖，顺环境链回落到根头的 INVOKE_BTA
    # （Environment.as:735-752）。写 4 会把这一下变成直击（官方仅有的非 0 先例，本批罗尔夫/凯尔
    # 真机确认）；写 3 与留 0 运行时逐字相同且官方零先例 ⇒ 这里钉死 INVOKE_HITAREA_BTA。
    # donor 换版或有人手改命中块时这条会炸（唯一能真正失败的归属门禁：根头是本函数自己拼的，
    # 断言它等于 INVOKE_BTA 只是同义反复，所以根头的钉死放在测试与成品包校验里）。
    hit_area_bta = [cha[24] for cha in PH.cmds(tree, "CreateHitArea")]
    if any(v != INVOKE_HITAREA_BTA for v in hit_area_bta):
        raise KitError(f"invoke CreateHitArea p23 must stay {INVOKE_HITAREA_BTA} "
                       f"(不覆盖，回落到根头 buffTargetAs={INVOKE_BTA}), got {hit_area_bta}")
    paths = sorted(set(PH.spec_paths(tree)))
    stray = [p for p in paths if p.startswith("battle/effect/skill_unique/")]
    if stray:
        raise KitError(f"629 载荷树引用了角色特效（只许引用官方 powerflip 族）: {stray}")
    problems = dsl_problems(tree, element=None)
    if problems:
        raise KitError(f"invoke tree DSL gates failed: {problems}")
    # rework1 反馈轮 3 全包核对：这棵树只搬了命中块（CollisionOfBallAndEnemy 的 CreateReferencePoint），
    # 不含 supporter 辅助增益块，本来就不该带 ACFlying —— 这里显式钉死，不留隐性假设。
    invoke_fly = count_ac_flying(tree)
    if invoke_fly:
        raise KitError(f"629 载荷树残留 {invoke_fly} 条 ACFlying（浮游已撤，不该再出现）")
    return tree, {"program": INVOKE_PROGRAM, "buff_target_as": INVOKE_BTA,
                  "hit_area_buff_target_as": hit_area_bta,
                  # 需已声明的 damage-type-rules-v1；公共发动次数由队长248配对行提供。
                  "damage_pools": {"power_flip_general": True, "skill_general": False,
                                   "power_flip_charge_tier": True,
                                   "power_flip_separated_term": True,
                                   "power_flip_resistance": True,
                                   "skill_separated_term": False,
                                   "skill_resistance": False,
                                   "counts_as_power_flip_for_triggers": True,
                                   "damage_label": "power_flip"},
                  "multipliers": scaled, "total": round(sum(scaled), 6),
                  "detoughness": {"per_segment": INVOKE_DOWN, "segments": segments,
                                  "per_call": down_total,
                                  "official_per_segment": INVOKE_DOWN_SOURCE},
                  "scale": INVOKE_SCALE, "official_effects": paths,
                  "ac_flying_count": invoke_fly,
                  "bound_ids": sorted(set(PH.bound_ids(tree)))}


# ---------------------------------------------------------------- 行装配与自检

def _pre_kinds(kind: str) -> tuple[int, ...]:
    return (4, 11, 18) if kind == "leader_ability" else (6, 13, 20)


def _row_self_check(kind: str, rows: list[list[str]], label: str) -> None:
    """内容 kind 黑名单 + 前置白名单 + 629 / 422 / during puller 的硬规矩。"""
    instant_col = LEADER_INSTANT_KIND if kind == "leader_ability" else ABILITY_INSTANT_KIND
    during_col = LEADER_DURING_KIND if kind == "leader_ability" else ABILITY_DURING_KIND
    trig_col = LEADER_DURING_TRIGGER if kind == "leader_ability" else ABILITY_DURING_TRIGGER
    pull_col = LEADER_DURING_PULLER if kind == "leader_ability" else ABILITY_DURING_PULLER
    sid_col = LEADER_STRING_ID if kind == "leader_ability" else ABILITY_STRING_ID
    path_col = LEADER_ACTION_PATH if kind == "leader_ability" else ABILITY_ACTION_PATH
    mode_col = 3 if kind == "leader_ability" else 5
    for index, row in enumerate(rows):
        tag = f"{label}#{index}"
        for col in _pre_kinds(kind):
            if row[col] not in ALLOWED_PRECONDITION_KINDS:
                raise KitError(f"{tag}: 前置 kind c{col}={row[col]!r} 不在白名单 {ALLOWED_PRECONDITION_KINDS}")
        if kind == "leader_ability":
            for col in (instant_col, during_col):
                if row[col] in FORBIDDEN_LEADER_KINDS:
                    raise KitError(f"{tag}: 队长表禁止 c{col}={row[col]}（= C7050）")
        if row[instant_col] == "629":
            if not row[sid_col] or not row[path_col]:
                raise KitError(f"{tag}: 629 行缺字符串键/动作路径（= 详情页 C8601）")
            if row[mode_col] != "0":
                raise KitError(f"{tag}: 629 只解析瞬发块，c{mode_col} 必须是 0")
        elif row[sid_col] and row[instant_col] not in ("536", "704", "722"):
            raise KitError(f"{tag}: 悬空字符串键 c{sid_col}={row[sid_col]!r}")
        if row[mode_col] == "1":
            # during 134 / during 1 的 puller 写 '0'；during 30 必须留空。写反 = 点「角色」C7050
            want = "0" if row[trig_col] in ("134", "1") else ""
            if row[pull_col] != want:
                raise KitError(f"{tag}: during {row[trig_col]} puller c{pull_col}={row[pull_col]!r} "
                               f"must be {want!r}")
        if kind == "ability" and row[during_col] == "422" and row[6] != "42":
            raise KitError(f"{tag}: 422 行必须挂前置 42（队长），否则与基诺维/泽赫尔的 422 相加")


def statue_group_report(ctx, rows_by_key: dict[str, list[list[str]]]) -> list[dict[str, Any]]:
    """c2 雕像组 × kind 的官方先例统计（裁决 §8 的自查，**记录而非阻断**）。

    c2 只喂 ``ability_statue_group`` 的颜色/图标/形象三列，与 kind 的解析无关；本角色明知的
    零先例项写在施工单「偏离」一节（422 是官方全表 0 行的补丁 kind，413×attack_common 零先例）。
    """
    instant: dict[tuple[str, str], int] = {}
    during: dict[tuple[str, str], int] = {}
    for blob in ctx.official_flat(KL.ABILITY).values():
        for raw in ctx.csv_split(blob):
            row = list(raw) + [""] * (KL.ABILITY_NCOLS - len(raw))
            if row[ABILITY_INSTANT_KIND]:
                pair = (row[2], row[ABILITY_INSTANT_KIND])
                instant[pair] = instant.get(pair, 0) + 1
            if row[ABILITY_DURING_KIND]:
                pair = (row[2], row[ABILITY_DURING_KIND])
                during[pair] = during.get(pair, 0) + 1
    report = []
    for key, rows in rows_by_key.items():
        group = rows[0][2]
        for n, row in enumerate(rows):
            for kind_col, table, tag in ((ABILITY_INSTANT_KIND, instant, "instant"),
                                         (ABILITY_DURING_KIND, during, "during")):
                value = row[kind_col]
                if not value:
                    continue
                report.append({"key": key, "record": n, "group": group, "trigger": tag,
                               "kind": value, "official_rows": table.get((group, value), 0)})
    return report


def build_rows(ctx) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    caps: set[str] = set()

    leader_rows: list[list[str]] = []
    for index, (addr, source, cells, expect) in enumerate(LEADER):
        label = f"leader#{index}"
        row, ev = KL.build_row(ctx, "leader_ability", addr, cells, source=source,
                               expect_describe=expect, label=label)
        if row[0] != CODE:
            raise KitError(f"{label}: c0 {row[0]!r} != {CODE}")
        leader_rows.append(row)
        evidence.append(ev)
        caps.update(ev["capabilities"])
    if len(leader_rows) != LEADER_ROWS:
        raise KitError(f"leader plan carries {len(leader_rows)} rows, expected {LEADER_ROWS}")
    _row_self_check("leader_ability", leader_rows, "leader")
    # 722 行：三级程序键与 c82 串必须与 power_flip_action / custom_ability_string 对齐，且不许挂门
    pf_row = leader_rows[0]
    if pf_row[45] != "722" or pf_row[80] != PF_KEY or pf_row[82] != CAS_PF or pf_row[81] != "1,2,3":
        raise KitError(f"leader 722 row drift: c45={pf_row[45]} c80={pf_row[80]} "
                       f"c81={pf_row[81]} c82={pf_row[82]}")
    if any(pf_row[col] not in ("", "0") for col in (4, 11, 18)):
        raise KitError("leader 722 row must carry no precondition（挂门＝群友报的「PF 没实装」）")

    ability: dict[str, list[list[str]]] = {}
    total = 0
    for slot in range(1, 7):
        key = f"{CID}{slot}"
        rows: list[list[str]] = []
        for index, (addr, source, cells, expect) in enumerate(PLAN[slot]):
            merged = {0: f"{CODE}_{slot}", 1: _UNISONABLE[slot], 2: _STATUE[slot], **cells}
            label = f"{key}#{index}"
            row, ev = KL.build_row(ctx, "ability", addr, merged, source=source, element=ELEMENT,
                                   expect_describe=expect, label=label)
            rows.append(row)
            evidence.append(ev)
            caps.update(ev["capabilities"])
            total += 1
        KL.check_ability_key(rows, key, CODE, slot)
        _row_self_check("ability", rows, key)
        ability[key] = rows
    if total != ABILITY_RECORDS:
        raise KitError(f"ability plan carries {total} records, expected {ABILITY_RECORDS}")

    missing = sorted(caps - set(ctx.spec.required_capabilities))
    if missing:
        raise KitError(f"rows need client capabilities {missing} that SPEC does not declare")
    return {"leader": leader_rows, "ability": ability, "evidence": evidence,
            "capabilities": sorted(caps)}


def write_strings(ctx) -> dict[str, str]:
    """``custom_ability_string``：722 条目 + 两条 629 条目 + 队长块与 6 槽的面板接管。"""
    declared = set(ctx.spec.extra_keys.get(KL.CAS, ()))
    missing = [key for key in CAS_TEXTS if key not in declared]
    if missing:
        raise KitError(f"custom_ability_string keys not declared in SPEC['extra_keys']: {missing}")
    official = ctx.official_flat(KL.CAS)
    clashes = [key for key in CAS_TEXTS if key in official]
    if clashes:
        raise KitError(f"custom_ability_string keys already exist officially: {clashes}")
    for key, text in CAS_TEXTS.items():
        KL.check_panel(text.replace(MAIN_ICON, ""), label=key)
        if key.startswith(L.PANEL_OVERRIDE_KEY_PREFIX) \
                and L.panel_override_capability(key) not in ctx.spec.required_capabilities:
            raise KitError(f"{key} needs a panel-override capability that SPEC does not declare")
    # 主位图标必须与 c1 一致：override 盖掉客户端逐行画的 Ⓜ，少一行都会让面板看着不限主位
    for slot in range(1, 7):
        wants_icon = _UNISONABLE[slot] == "false"
        for line in CAS_TEXTS[CAS_ABILITY[slot]].split("\n"):
            if line.startswith(MAIN_ICON) != wants_icon:
                raise KitError(f"slot {slot} desc_override main-position icon does not match c1"
                               f" (c1={_UNISONABLE[slot]}): {line!r}")
    ctx.write_flat(KL.CAS, {key: [[text]] for key, text in CAS_TEXTS.items()})
    back = ctx.pack.pkg_flat(KL.CAS)
    for key, text in CAS_TEXTS.items():
        if ctx.csv_split(back[key])[0][0] != text:
            raise KitError(f"custom_ability_string readback mismatch: {key}")
    return dict(CAS_TEXTS)


def write_action_skill(ctx) -> dict[str, list[str]]:
    """两档能量（本轮不改）；名称/描述由 tables 写 TEXTS，这里只改图标 c2 与能量 c4/c5/c6。"""
    spec = ctx.spec
    out: dict[str, list[str]] = {}
    for level, raw in sorted(ctx.pkg_nested(CODE, KL.ACTION).items()):
        if len(raw) != 24:
            raise KitError(f"action_skill {level}: {len(raw)} columns, expected 24")
        cells = list(raw)
        block = SKILL_ENERGY[level]
        cells[2] = SKILL_ICON
        cells[4], cells[5], cells[6] = str(block["c4"]), str(block["c5"]), str(block["c6"])
        cells[7] = ctx.program_path(level)
        if cells[0] != spec.texts[f"skill{level}"] or cells[1] != spec.texts[f"desc{level}"]:
            raise KitError(f"action_skill {level}: name/desc drift from design texts")
        out[level] = cells
    if sorted(out) != ["1", "2"]:
        raise KitError(f"action_skill levels {sorted(out)}")
    ctx.write_nested(KL.ACTION, CODE, {lv: [cells] for lv, cells in out.items()},
                     replace_inner=True)
    return out


# ---------------------------------------------------------------- build

def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.cid, spec.code, spec.element) != (CID, CODE, ELEMENT):
        raise KitError(f"identity drift: {spec.cid}/{spec.code}/element {spec.element}")
    if (spec.template_id, spec.template_code) != (TEMPLATE_ID, TEMPLATE_CODE):
        raise KitError(f"template drift: {spec.template_id}/{spec.template_code}")
    if spec.pf_type != 3 or spec.stance != "Attacker":
        raise KitError(f"spec drift: pf_type={spec.pf_type} stance={spec.stance}")
    if MS.text_placeholders(spec):
        raise KitError(f"design texts still placeholders: {MS.text_placeholders(spec)}")

    design = load_design(ctx.root)
    problems = design_problems(design)
    if problems:
        raise KitError(f"design mirror rejected: {problems}")

    # ---- 1) 固有状态「回响」（rework1：上限 99）+ 48×48 图标
    key, row = KL.unique_row(ctx, spec, 1, donor=UNIQUE_DONOR,
                             cells={0: UNIQUE_STRING_ID, 3: UNIQUE_FRAMES, 4: UNIQUE_CAP,
                                    9: "false", 10: "false", 13: "true"},
                             name=UNIQUE_NAME, icon=UNIQUE_ICON_ROW)
    KL.write_unique(ctx, spec, {key: row})
    icon = install_unique_icon(ctx)

    # ---- 2) 队长 9 行 + 词条 6 键 18 条
    rows = build_rows(ctx)
    ctx.write_flat(KL.LEADER, {str(CID): rows["leader"]})
    ctx.write_flat(KL.ABILITY, rows["ability"])
    statue = statue_group_report(ctx, rows["ability"])

    # ---- 3) custom_ability_string：722 / 两条 629 / 队长块 + 6 槽面板接管
    strings = write_strings(ctx)
    panel = [PANEL_LEADER] + [PANEL_ABILITY[slot] for slot in range(1, 7)]

    # ---- 4) action_skill 两档
    action_rows = write_action_skill(ctx)

    # ---- 5) 技能特效族（只克隆 1 族）与两档技能 DSL
    lut = KL.png_transform_from_lut(KL.pixel_dir(ctx) / "fx_lut.json")
    family = ctx.clone_effect_family(FX_SRC_DIR, FX_SUBDIR, fx_names=[FX_BACK, FX_EF],
                                     png_transform=lut)
    if family["dst_dir"] != FX_DST_DIR or sorted(family["copied_bases"]) != sorted([FX_BACK, FX_EF]):
        raise KitError(f"effect family drift: {family['dst_dir']} {family['copied_bases']}")
    programs: list[str] = []
    skill_gates = {}
    for level in ("1", "2"):
        tree, gates = build_skill_tree(ctx, level, family)
        for path in PH.spec_paths(tree):
            if path.startswith(FORBIDDEN_FX_PREFIXES):
                raise KitError(f"skill {level}: 残留兄弟目录特效前缀 {path}")
        programs.append(write_dsl_checked(ctx, ctx.program_path(level), tree))
        skill_gates[level] = gates

    # ---- 6) 专属强化弹射 722 三档
    pf_gates = {}
    for level in (1, 2, 3):
        tree, gates = build_pf_tree(ctx, level)
        programs.append(write_dsl_checked(ctx, PF_PROGRAMS[level - 1], tree))
        pf_gates[str(level)] = gates
    ctx.write_flat(PFA, {PF_KEY: [list(PF_PROGRAMS)]})

    # ---- 7) rework1 新增：629 PF 追击树（队长两行共用）
    invoke_tree, invoke_gates = build_invoke_tree(ctx)
    programs.append(write_dsl_checked(ctx, INVOKE_PROGRAM, invoke_tree))
    for n, leader_row in enumerate(rows["leader"]):
        if leader_row[LEADER_INSTANT_KIND] == "629" and leader_row[LEADER_ACTION_PATH] != INVOKE_PROGRAM:
            raise KitError(f"leader#{n}: 629 action_path {leader_row[LEADER_ACTION_PATH]!r} "
                           f"!= {INVOKE_PROGRAM!r}")

    # rework1 反馈轮 3（作者 09-21「澄波响去掉浮游效果」）全包核对：722 三档最终都不该带 ACFlying。
    # ``ac_flying_removed`` 是 1 还是 0 取决于共享 ``PH.pf_support_block``（与菲莉亚同一处理点，
    # 本模块不改那个文件）当前是否已经在源头删过——三档必须整齐划一（同为 1 或同为 0），
    # 一半删了一半没删才是真漂移；技能两档与 629 追击树本来就是 0 条。
    ac_flying_report = {
        "power_flip": {lv: pf_gates[lv]["ac_flying_removed"] for lv in ("1", "2", "3")},
        "power_flip_final_count": {lv: pf_gates[lv]["ac_flying_count"] for lv in ("1", "2", "3")},
        "skills": {lv: skill_gates[lv]["ac_flying_count"] for lv in ("1", "2")},
        "invoke": invoke_gates["ac_flying_count"],
    }
    if len(set(ac_flying_report["power_flip"].values())) != 1:
        raise KitError(f"ACFlying removal count is inconsistent across PF levels (should be all-1 or "
                       f"all-0, not a mix): {ac_flying_report['power_flip']}")
    if any(ac_flying_report["power_flip_final_count"].values()) \
            or any(ac_flying_report["skills"].values()) or ac_flying_report["invoke"]:
        raise KitError(f"ACFlying still present somewhere after the build: {ac_flying_report}")

    # ---- 8) 语音路由（kind 1 ConditionExist ← 固有 16998801）+ switched_action_skill
    route = KL.voice_route(CODE, VOICE_ROUTE)
    design_route = design["voice"]["route"]
    if (design_route["kind"], str(design_route["condition_kind"]), str(design_route["condition_id"])) \
            != (VOICE_ROUTE["kind"], VOICE_ROUTE["condition_kind"], VOICE_ROUTE["condition_id"]):
        raise KitError(f"design voice route drift: {design_route}")
    char_row = ctx.pack.pkg_character_row()
    char_row[9:17] = route
    if char_row[6] != "3" or char_row[26] != "Attacker" or char_row[27] != str(CID):
        raise KitError(f"character row drift: c6={char_row[6]} c26={char_row[26]} c27={char_row[27]}")
    ctx.write_flat(KL.CHARACTER, {str(CID): [char_row]})
    voice = KL.write_voice_ready(ctx)

    # ---- 9) 像素/特效成品（缺文件静默跳过）+ 三层镜像
    pixel = KL.install_staged_assets(ctx)
    mirrors = ctx.sync_character_mirrors()
    if mirrors["character"][9:17] != route:
        raise KitError("character mirror lost the voice route")

    ctx.evidence_write("kit-gates.json", {
        "rows": rows["evidence"], "skills": skill_gates, "power_flip": pf_gates,
        "invoke": invoke_gates, "statue_group_precedent": statue,
        "unique_condition": {key: {"row": row, "icon": icon}},
        "custom_ability_string": sorted(strings),
        "action_skill": action_rows,
        "effect_family": {k: family[k] for k in ("src_dir", "dst_dir", "layout", "copied_bases",
                                                 "complete_family", "missing_effects")},
        "fx_lut": bool(lut), "voice": voice, "pixel": pixel, "mirrors": mirrors})

    notes = [
        "rework1（作者 09-20/21）：队长 6→9 行（新增 暗共鸣+暗属性角色发动技能时 629 / "
        "全等级PF累计命中每4次自身攻击+50%（无上限）/ 冲刺 629 CT1.5秒）；词条 15→18 条"
        "（能力2 数值翻倍、能力3 加暗共鸣门且层数上限 5→99、能力4 新增每层回响自身攻击+25%、"
        "能力5 新增常驻独立乘区 +30%）；固有「回响」上限 5→99",
        f"629 PF 追击：官方 special_lv3 命中块 ×{INVOKE_SCALE} ＝ {invoke_gates['total']}×，"
        f"tree[10]={INVOKE_BTA}、判定区 params[23]={INVOKE_HITAREA_BTA}，"
        "由 damage-type-rules-v1 按 PF3 结算；保留原生413乘区。"
        "两条队长248与629配对，每次追加计1次公共PF发动；不按命中数重复计数，"
        "不触发分档拍板事件；每3次PF给同一回响计数+2层。",
        "2026-09-27 第二批平衡：回响每层的无上限成长（PF伤害/攻击力 25%）搬进队长并放缓到 2.5%/层"
        f"（队长 10→{LEADER_ROWS} 行），能力槽3/槽4 原位换成封顶 {ECHO_ABILITY_CAP} 层的 10%/5%；"
        "队长累计命中每4次自身攻击 50%→5%；629 追击树每段削韧 "
        f"{INVOKE_DOWN_SOURCE}→{INVOKE_DOWN}（每次 {invoke_gates['detoughness']['per_call']}）。",
        "2026-09-27 第三轮平衡（成长复核，作者「砍到4/5，或者7/10」「可以砍到2/3」「取5的倍数」）："
        f"队长回响每层 2.5%→{int(ECHO_LEADER_STEP) / 1000:g}%（原 25%）、累计命中每4次自身攻击 "
        f"5%→{int(HIT_ATTACK_STEP) // 1000}%（原 50%）；能力槽3/槽4 封顶版不动。",
        f"技能（未改）：内层1 {skill_gates['1']['multipliers']['field'][0]}×18＝"
        f"{round(skill_gates['1']['multipliers']['field'][0] * 18, 2)}×，"
        f"内层2 满级 {skill_gates['2']['multipliers']['field'][1]}×18＝"
        f"{round(skill_gates['2']['multipliers']['field'][1] * 18, 2)}×；tree[10]=0（技能伤害归属，D-1）",
        f"722（未改）：官方 special 底座 ×{PF_SCALE} ＝ "
        + " / ".join(f"lv{n} {pf_gates[str(n)]['total']}×" for n in (1, 2, 3))
        + "；辅助增益块贯通帧 " + "/".join(str(PF_PIERCE_FRAMES[n]) for n in (1, 2, 3)),
        "面板：队长块与 6 槽全部走 desc_override_*，逐行对齐 rework1/panel/hibiki.json；"
        "冲刺 422 行留在能力 5（写队长表 = C7050），文案在队长块第 10 行",
        f"rework1 反馈轮 3（作者 09-21 真机反馈，要求撤掉专属PF的一项赋予状态）：722 三档辅助增益块"
        f"最终都不带 ACFlying CreateCondition 了（本模块自删 {ac_flying_report['power_flip']['1']} 条/档，"
        "或已经由共享 pf_support_block 在源头删过，两种情况整齐一致；ACAttackPoint/ACPiercing 原样"
        "保留、绑定/参数不动）；技能两档与 629 追击树全包核对确认 0 条；面板 c82 串与队长块文案同步"
        "收窄为「攻击力提升、贯穿效果」，行数据（队长/词条）零变化",
        {"ac_flying_removal": ac_flying_report},
        {"statue_group_zero_precedent":
            [f"{e['key']}#{e['record']} {e['group']}×{e['trigger']}{e['kind']}"
             for e in statue if e["official_rows"] == 0]},
        {"pixel_install": pixel},
    ]
    deviations = [{"want": item["intended"], "got": item["actual"], "why": item["reason"]}
                  for item in design.get("deviations", ())]
    gate = {"rows": len(rows["evidence"]), "programs": len(programs),
            "pixel_present": pixel["present"], "pixel_missing": [e["logical"] for e in pixel["skipped"]]}
    ready = pixel["present"] and not pixel["skipped"]
    gate["reason"] = "kit 自有产物全部过闸" if ready else \
        f"像素/特效成品未就绪：{gate['pixel_missing'] or 'B/pixel/hibiki/install.json 不存在'}"
    return KL.report(
        ctx, summary="澄波响 rework1：暗属性 PF 主 C —— 722 专属 PF ＋ 回响（上限 99）"
                     "＋ 两行 629 PF 追击 ＋ 冲刺改造",
        status=KL.READY if ready else KL.DRAFT, panel=panel, notes=notes, programs=programs,
        unique_condition={key: {"name": UNIQUE_NAME, "cap": UNIQUE_CAP, "icon": UNIQUE_ICON_LOGICAL}},
        required_capabilities=sorted(set(rows["capabilities"]) | set(SPEC["required_capabilities"])),
        deviations=deviations,
        extra={"power_flip_action": {PF_KEY: list(PF_PROGRAMS)},
               "custom_ability_string": sorted(strings),
               "ability_skill_programs": [INVOKE_PROGRAM],
               "effect_families": [FX_DST_DIR], "kit_gate": gate})

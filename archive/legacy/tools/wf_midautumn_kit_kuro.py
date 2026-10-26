# -*- coding: utf-8 -*-
"""中秋批次 kit：黑 139991 ``outlaw_panther_moon``（雷 · 拳 · 直击辅助）· **rework1**。

轴线（`rework1/impl/kuro.md`）：**摇骰子**——三条线咬合。

- **强化技能线**：雷共鸣 → ``IC 536 ChangeSkillFlag`` 开强化档；技能 DSL 里
  ``ConditionalsChangeSkillFlag`` 两分支，强化档判定区寿命 60→180 帧、段数 15→45、
  ``CreateNormalAttack[8] = enablesComboBonus = true``（威力随连击成长）。
- **骰运轮盘线**：雷属性角色每 500 次直击 → 固有「骰运」+1（上限 6）；强化分支末尾 6 个
  ``ConditionalsProbability`` 轮盘，第 n 个由 ``ConditionalsConditionAccumulationNumber``
  按骰运层数开门 ⇒ 抽取次数 = ``max(1, 层数)``，最多 6 次，每次独立掷点。
- **Fever 收支线**：非 Fever 每 45 次直击 +35% 槽（724 正）／Fever 中每 20 次直击 −50% 槽
  （724 负）／每次进入 Fever 全队(雷) 直击伤害 +40%（最多 3 次；2026-09-27 平衡第二批，
  无上限部分进队长 L5，第三轮成长复核后每次 +105%）。

技能本体演出不变（4 条 ``ShowEffect`` 全部引用官方母本路径，**零克隆零图集增量**），
只做参数手术：取消后摇（``StopBall`` 换千岳式 ``RestoreToSpeedBeforeActionExecution``）、
强化档寿命/段数、强化档连击加成。

面板 7 块（队长技 ＋ 6 个词条槽）**全部走 ``desc_override_*`` 整块接管**，逐行等于
``rework1/panel/kuro.json``。

由 ``python mod-tools/wf_midautumn_build.py --char kuro --step kit`` 调用 :func:`build`。
只经 ``KitContext`` 写 ``work/character_packs/ma-kuro/``；live store / ``assets/`` / ``.cdn`` /
设备 / 存档一律不碰，不发布、不 git。

APK 依赖：``kyubi-fever-ratio-v1``（724，**只许 ability 表**，写队长表 = C7050）＋
``panel-description-override-v2``（V14，``desc_override_*`` 惰性生效，缺补丁不崩）。
"""
from __future__ import annotations

import copy
import json
from typing import Any

import wf_client_legality as L
import wf_midautumn_kitlib as KL
import wf_midautumn_specs as MS
import wf_kuro_full_dice as full_dice

KEY = "kuro"
CID = 139991
CID_S = "139991"
CODE = "outlaw_panther_moon"
TEMPLATE_ID = 231069
TEMPLATE_CODE = "outlaw_panther_ny22"
ELEMENT = 2                      # 内部 ElementKind：2 = 雷（Yellow）
ELEMENT_TOKEN = "Yellow"
PF_TYPE = 1                      # 拳
STANCE = "Supporter"

UID_DICE = MS.unique_condition_id(CID, 1)      # "13999101" 骰运（上限 6，常驻）
UID_STEP = MS.unique_condition_id(CID, 2)      # "13999102" 豹步（上限 1，15 秒）
VOICE_KEY = CODE + "_voice_ready"

CHARACTER = KL.CHARACTER
ACTION = KL.ACTION

TEXTS = {
    "name": "黑",
    "furigana": "HEI",
    "title": "月下博饼的黑豹",
    "profile": "中秋夜的长街上，黑支起一张矮几，摆出朱漆骰碗，招呼路过的人来赌一把月饼。"
               "这位看似只顾摇骰起哄的猫族长老，却在每次开碗时数清了场上有几个人在笑——"
               "他想改变的世界，就是这样一个谁都能笑着掷一次骰子的地方。",
    # 第三段对应 panel/kuro.json › skill.lines[1]（status "changed"）：S1 取消后摇。
    "skill1": "博饼·满堂彩",
    "desc1": "手托朱漆骰碗原地摇转，对周围的敌人持续造成雷属性伤害（以直接攻击伤害判定）"
             "／赋予队伍全员及协力球直接攻击伤害提升与追加直接攻击效果"
             "／释放技能后不再进入硬直，可立即行动",
    "skill2": "博饼·满堂彩＋",
    "desc2": "手托朱漆骰碗原地摇转，对周围的敌人持续造成雷属性伤害（以直接攻击伤害判定）"
             "／赋予队伍全员及协力球直接攻击伤害提升与追加直接攻击效果"
             "／释放技能后不再进入硬直，可立即行动",
    "leader": "今宵手气正旺",
    "cv": "AI 合成配音",
}

# ------------------------------------------------------------------ 面板字符串键

CAS_CHANGE_SKILL = f"change_skill_{CODE}"              # 536 的 c70
CAS_LEADER = f"desc_override_{CODE}"                   # 队长块整体接管
CAS_ABILITY = {slot: f"desc_override_{CODE}_{slot}" for slot in range(1, 7)}

SPEC = {
    # 724 = kyubi-fever-ratio-v1；desc_override_* 行要生效需要 V14（缺补丁不崩，面板回落）
    "required_capabilities": ("kyubi-fever-ratio-v1", L.PANEL_OVERRIDE_V2),
    "extra_keys": {
        KL.UNIQUE: (UID_DICE, UID_STEP),
        KL.CAS: (CAS_CHANGE_SKILL, CAS_LEADER, *(CAS_ABILITY[s] for s in range(1, 7))),
        KL.SWITCHED: (VOICE_KEY,),
    },
}

#: character c9–c16：kind 1 ConditionExist，条件种类 **28**（固有状态）、条件 id = 骰运。
#: 骰运一旦获得就常驻（c3 = 99999999）⇒ 开局与开局后各听得到一种「技能准备好」台词。
#: kind 3 ChangeSkillFlag 不能用：536 在共鸣队里常驻，会让 skill_ready 永不播（magnus 先例）。
VOICE_ROUTE = {"kind": 1, "condition_kind": "28", "condition_id": UID_DICE}


class KuroError(KL.KitError):
    """本角色 kit 的断言失败。"""


# ------------------------------------------------------------------ 固有状态

#: 官方 ``unique_condition[11]`` ``unique_blackflower_wiz_smr22``「能量吸取」整行，
#: 只改 c0/c1/c2/c3/c4；其余列逐列相同（不可驱散、入棺不清除）。
UNIQUE_DONOR = "11"

#: 骰运：**上限 6**（博饼六颗骰子）、无时间限制。写 ``(None)``／空 = 上限 1，会把 461 叠层、
#: during 134、DSL 的 ``ConditionalsConditionAccumulationNumber`` 全部弄死
#: （记忆 ``wf-unique-cap-none-trap``）；``KL.unique_row`` 也硬拒。
DICE_NAME = "骰运"
DICE_CAP = "6"
DICE_FRAMES = "99999999"
DICE_ICON = f"battle/common/unique_condition/unique_{CODE}_dice_luck"

#: 豹步：技能发动即付与、**15 秒**（900 帧）、上限 1 的二值状态。
#: 上限 1 ⇒ ``shouldDisplayNumber = 上限 > 1`` 为假，图标右下不画层数（正确）。
STEP_NAME = "豹步"
STEP_CAP = "1"
STEP_FRAMES = "900"
STEP_ICON = f"battle/common/unique_condition/unique_{CODE}_panther_step"

#: 取 alpha 与尺寸的官方画框 donor（就是固有状态行的 donor 自己的图标）。
#: manifest 门禁要求「被表引用的资产必须在 roots.common 里声明」⇒ 图标**必须进包**，
#: 引用官方路径当回落是过不了的（实测：`validate_manifest: referenced asset is not declared`）。
UNIQUE_ICON_FRAME = "battle/common/unique_condition/unique_blackflower_wiz_smr22.png"

#: 图标配色：夜靛底 ＋ 金边（与引擎点火／月牙／回响／桂灯同一套）。
ICON_INK = (0x22, 0x1E, 0x1A)          # 夜靛
ICON_GOLD = (0xBA, 0x9E, 0x46)         # 金边 / 骰身
ICON_GOLD_LIGHT = (0xD8, 0xBC, 0x66)   # 受光面
ICON_GOLD_DARK = (0x7E, 0x68, 0x2C)    # 背光面
ICON_PIP = (0xFF, 0xF4, 0xC0)          # 骰点 / 月牙 / 爪印高光
ICON_SCALE = 8                         # PIL 8× 画 + LANCZOS 缩


# ------------------------------------------------------------------ 行方案
# 每条 =（donor 键#记录号（0 基）, 逐格改, 面板预期文案（wf_describe 回读））。
# donor 默认取官方基线（``.cdn/cn`` OfficialBaseline），``live:`` 前缀才取 live store
# （只有 724 那两条：补丁 kind 在官方全表零行，唯一可抄的形状是自制 149989 希尔媞·校园）。
#
# 面板上真正显示的是 ``desc_override_*``（:data:`CAS_TEXTS`）；这里登记的 describe
# 是**行装配的回读判据**（donor 漂移 / 改错列都会在 build 时当场炸）。

LEADER: tuple[tuple[str, dict[int, str], str], ...] = (
    # L1 Fever 中 → 全队(雷) 直击伤害 400%（裁决 §2「直击队长全队直击 300–400%」带顶）
    ('151171#1', {0: CODE, 1: '0', 3: '1', 4: '0', 11: '0', 18: '0', 83: '(None)', 95: '4',
                  106: 'false', 107: '1', 108: '5', 109: ELEMENT_TOKEN, 111: '400000', 112: '400000'},
     '持续·Fever → 赋予全队(雷) Direct伤害 400%'),
    # L2 同一个 Fever 门下的全队攻击力 200%（L1+L2 = 600%，落在主轴合计 490–650% 内）
    ('151171#0', {0: CODE, 1: '0', 3: '1', 4: '0', 11: '0', 18: '0', 83: '(None)', 95: '4',
                  106: 'false', 107: '0', 108: '5', 109: ELEMENT_TOKEN, 111: '200000', 112: '200000'},
     '持续·Fever → 赋予全队(雷) 攻击力 200%'),
    # L3 把 L1/L2 的门自己延长：官方 ★3 黑本人的队长行，数值不动
    ('331004#1', {0: CODE, 1: '0', 3: '0', 4: '0', 11: '0', 18: '0', 25: '0', 37: '(None)',
                  44: '0', 45: '56', 49: '25000', 50: '25000'},
     '自身 Fever时间延长 25%'),
    # L4 Fever 引擎：雷共鸣且非 Fever 时任一雷属性角色发动技能 → 追加 Fever 点
    #    724 不能进队长表（= C7050），队长层的 Fever 回转只能用官方 213
    ('131164#3', {0: CODE, 1: '0', 3: '0', 4: '2', 7: '600000', 8: '600000', 9: ELEMENT_TOKEN,
                  11: '186', 18: '0', 25: '23', 26: '7', 27: ELEMENT_TOKEN, 28: '100000',
                  29: '100000', 32: '(None)', 33: '0', 37: '(None)', 44: '0', 45: '213',
                  49: '5000000', 50: '5000000'},
     '雷·编成≥6 且 非Fever 时: 技能发动≥1 → 自身 追加Fever点 5000%'),
    # L5 2026-09-27 平衡第二批（wf_balance_20260927b_kuro）：能力3「每次进入 Fever → 雷队直击」的无上限部分
    #    搬进队长（= [c0,'0',''] + 1399913#1[5:]），150% → 30%（3 分钟约 8–12 次 ⇒ 1/5）。
    #    donor 官方 131164#1（trigger 8 → 瞬发 32 target 5 Yellow，同触发同目标、kind 不同）；队长 trigger 8
    #    官方 24 行、瞬发 kind 33 target 5 官方 14 行，但 trigger 8 → kind 33 组合在官方队长/能力表都是 0 行
    #    （只有 live 能力行 1399913#1 在线）⇒ 两列各有先例、风险低，上线前真机开角色页/队长页确认。
    #    队长 L1 是持续 Fever → 直击，触发不同，不合并。
    #    2026-09-27 第三轮（wf_balance_20260927c_kuro，成长复核）：30% → 原值 150% × 7/10 = 105%。
    ('131164#1', {0: CODE, 1: '0', 3: '0', 4: '0', 11: '0', 18: '0', 25: '8', 28: '100000',
                  29: '100000', 32: '(None)', 33: '0', 37: '(None)', 44: '0', 45: '33', 46: '5',
                  47: ELEMENT_TOKEN, 49: '105000', 50: '105000'},
     'Fever≥1 → 赋予全队(雷) Direct伤害 105%'),
)

#: 一键内 c2（雕像组）必须单值（裁决 §8）。选组规则＝**该键用到的每个 kind 在官方基线上
#: 都有这一组的先例**，多候选取「最小先例数最大」的。本轮实扫（官方 ability 表）：
#:
#: ======== ================= ====================================================
#: 键       kinds             候选（最小先例数）→ 取
#: ======== ================= ====================================================
#: 1399911  I211 I536         special(21) / action_skill(7) / attack_common(2) → special
#: 1399912  I32×2 I461        attack_common(2) / attack_yellow(1) / special(1)  → attack_common
#: 1399913  I724×2 I33 I461   attack_common（724 官方零行，不约束）             → attack_common
#: 1399914  I211 I226         special(18) / attack_common(7) / action_skill(4)  → special
#: 1399915  I211 I226         同上                                              → special
#: 1399916  I69 I205          condition(3) / special(2) / action_skill(1)       → condition
#: ======== ================= ====================================================
STATUE_GROUPS = {'1399911': 'special', '1399912': 'attack_common', '1399913': 'attack_common',
                 '1399914': 'special', '1399915': 'special', '1399916': 'condition'}

_A = {slot: f"{CODE}_{slot}" for slot in range(1, 7)}

ABILITY: dict[str, tuple[tuple[str, dict[int, str], str], ...]] = {
    # 1 自充 ＋ 共鸣时开强化档（效果全在 DSL 的 ConditionalsChangeSkillFlag 强化分支里）
    '1399911': (
        ('2310694#0', {0: _A[1], 1: 'true', 2: 'special', 3: '0', 5: '0', 6: '0', 13: '0',
                       20: '0', 27: '0', 39: '(None)', 46: '0', 47: '211', 48: '0',
                       51: '50000', 52: '50000'},
         '自身 技能槽 50%'),
        ('1411113#0', {0: _A[1], 1: 'true', 2: 'special', 3: '0', 5: '0', 6: '2',
                       9: '600000', 10: '600000', 11: ELEMENT_TOKEN, 13: '0', 20: '0',
                       27: '0', 39: '(None)', 46: '0', 47: '536', 70: CAS_CHANGE_SKILL},
         f'雷·编成≥6 时: 自身 切换技能形态[{CAS_CHANGE_SKILL}]'),
    ),
    # 2 技能命中喂队长 ＋ 豹步门下的全队攻击（第三条是豹步的获取行，面板不显示）
    #   2026-09-27 平衡第二批（wf_balance_20260927b_kuro）：#0 不限次 50% → 最多 25 次 × 2%
    #   （官方 trigger 107 先例 1610054#0 +1% × 50）；其无上限部分 trigger 107 在队长表零先例 ⇒
    #   末尾 #3 = 前置1 42（持有者为队长）＋ 前置2 雷共鸣，每 hit 自身攻击力 +5%（3 分钟 105–135 hit ⇒ 1/10），
    #   行形照 live 凯尔 1399903#4/#5；文案写进队长面板（PANEL_LEADER 第 5 行）。
    #   2026-09-27 第三轮作者追加（wf_balance_20260927c_kuro 第 6 节，原话「黑豹能力2改成5刃25次暖满」）：
    #   #0 每次 2% → 5%，最多 25 次不变（叠满 50% → 125%）。
    '1399912': (
        ('1610054#0', {0: _A[2], 1: 'true', 2: 'attack_common', 3: '0', 5: '0', 6: '2',
                       9: '600000', 10: '600000', 11: ELEMENT_TOKEN, 13: '0', 20: '0',
                       27: '107', 28: '0', 30: '100000', 31: '100000', 34: '25', 35: '0',
                       39: '(None)', 46: '0', 47: '32', 48: '2', 51: '5000', 52: '5000'},
         '雷·编成≥6 时: 技能Hit≥1(限25次) → 赋予队长 攻击力 5%'),
        # 前置块 6–12 / 13–19 / 20–26 三段列偏移完全相同（1611831#L1 与 1411413#L1 互证）
        # ⇒ 把 donor 的前置2（187 + puller '0' + 固有 id）整段搬到前置1，前置2 清成 '0' 哨兵。
        ('1411413#0', {0: _A[2], 1: 'true', 2: 'attack_common', 3: '0', 5: '0',
                       6: '187', 7: '0', 8: '', 9: '', 10: '', 11: '', 12: UID_STEP,
                       13: '0', 14: '', 19: '', 20: '0', 27: '0', 39: '(None)', 46: '0',
                       47: '32', 48: '5', 49: ELEMENT_TOKEN, 51: '250000', 52: '250000'},
         f'状态固有[固有{UID_STEP}] 时: 赋予全队(雷) 攻击力 250%'),
        ('1611231#0', {0: _A[2], 1: 'true', 2: 'attack_common', 3: '0', 5: '0', 6: '0',
                       13: '0', 20: '0', 27: '23', 28: '0', 30: '100000', 31: '100000',
                       34: '(None)', 35: '0', 39: '(None)', 46: '0', 47: '461', 48: '0',
                       51: '100000', 52: '100000', 59: '100000', 60: '100000', 68: UID_STEP,
                       74: '1', 75: '0'},
         '技能发动≥1 → 自身 状态固有 100%×1次'),
        # 2026-09-27 第三轮（wf_balance_20260927c_kuro，成长复核）：5% → 原值 50% × 2/3 = 33.3，向上取 35%。
        ('1610054#0', {0: _A[2], 1: 'true', 2: 'attack_common', 3: '0', 5: '0', 6: '42',
                       13: '2', 16: '600000', 17: '600000', 18: ELEMENT_TOKEN, 20: '0',
                       27: '107', 28: '0', 30: '100000', 31: '100000', 34: '(None)', 35: '0',
                       39: '(None)', 46: '0', 47: '32', 48: '0', 51: '35000', 52: '35000'},
         '队长 且 雷·编成≥6 时: 技能Hit≥1 → 自身 攻击力 35%'),
    ),
    # 3 Ⓜ 主位核心：Fever 收支三条 ＋ 骰运获取（轮盘本体在技能 DSL 里，零行）
    '1399913': (
        ('live:1499893#1', {0: _A[3], 1: 'false', 2: 'attack_common', 3: '0', 5: '0',
                            6: '2', 9: '600000', 10: '600000', 11: ELEMENT_TOKEN, 13: '186',
                            20: '0', 27: '20', 28: '7', 29: ELEMENT_TOKEN, 30: '4500000',
                            31: '4500000', 34: '(None)', 35: '0', 39: '(None)', 46: '0',
                            47: '724', 51: '35000', 52: '35000'},
         '雷·编成≥6 且 非Fever 时: 编成直接攻击≥45 → 自身 Fever槽增减(上限比例) 35%'),
        # 2026-09-27 平衡第二批：不限次 150% → 最多 3 次 × 40%（官方能力 trigger 8 限 3 族），
        # 无上限部分进队长 L5（第二批每次 +30%，第三轮 +105%）。
        ('1310011#0', {0: _A[3], 1: 'false', 2: 'attack_common', 3: '0', 5: '0', 6: '0',
                       13: '0', 20: '0', 27: '8', 30: '100000', 31: '100000', 34: '3',
                       35: '0', 39: '(None)', 46: '0', 47: '33', 48: '5', 49: ELEMENT_TOKEN,
                       51: '40000', 52: '40000'},
         'Fever≥1(限3次) → 赋予全队(雷) Direct伤害 40%'),
        # 前置 12 Fever 只填 kind 列（照官方 1310012#L1 的 186 写法）
        ('live:1499893#1', {0: _A[3], 1: 'false', 2: 'attack_common', 3: '0', 5: '0',
                            6: '12', 9: '', 10: '', 11: '', 13: '0', 20: '0', 27: '20',
                            28: '7', 29: ELEMENT_TOKEN, 30: '2000000', 31: '2000000',
                            34: '(None)', 35: '0', 39: '(None)', 46: '0', 47: '724',
                            51: '-50000', 52: '-50000'},
         'Fever 时: 编成直接攻击≥20 → 自身 Fever槽增减(上限比例) -50%'),
        ('1611231#0', {0: _A[3], 1: 'false', 2: 'attack_common', 3: '0', 5: '0', 6: '2',
                       9: '600000', 10: '600000', 11: ELEMENT_TOKEN, 13: '0', 20: '0',
                       27: '20', 28: '7', 29: ELEMENT_TOKEN, 30: '50000000', 31: '50000000',
                       34: '(None)', 35: '0', 39: '(None)', 46: '0', 47: '461', 48: '0',
                       51: '100000', 52: '100000', 59: '100000', 60: '100000', 68: UID_DICE,
                       74: '1', 75: '0'},
         '雷·编成≥6 时: 编成直接攻击≥500 → 自身 状态固有 100%×1次'),
    ),
    # 4 每次获得贯穿 → 自充 ＋ 连击（IT 51 = 每被付与一次贯通就 countUp 一次）
    # 反馈轮 2：c35（CT 列）加 180 帧 = 3 秒（作者原话「黑的能力4带上ct3s」）。
    '1399914': (
        ('2110012#0', {0: _A[4], 1: 'true', 2: 'special', 3: '0', 5: '0', 6: '2',
                       9: '600000', 10: '600000', 11: ELEMENT_TOKEN, 13: '0', 20: '0',
                       27: '51', 30: '100000', 31: '100000', 34: '(None)', 35: '180',
                       39: '(None)', 46: '0', 47: '211', 48: '0', 51: '5000', 52: '5000'},
         '雷·编成≥6 时: 状态贯通≥1(CT3秒) → 自身 技能槽 5%'),
        ('2110012#0', {0: _A[4], 1: 'true', 2: 'special', 3: '0', 5: '0', 6: '2',
                       9: '600000', 10: '600000', 11: ELEMENT_TOKEN, 13: '0', 20: '0',
                       27: '51', 30: '100000', 31: '100000', 34: '(None)', 35: '180',
                       39: '(None)', 46: '0', 47: '226', 48: '', 51: '5000000', 52: '5000000'},
         '雷·编成≥6 时: 状态贯通≥1(CT3秒) → 自身 追加连击 50'),
    ),
    # 5 击杀回馈（技能槽给全队(雷)，连击是全局量 ⇒ target 列官方留空）
    '1399915': (
        ('1110033#0', {0: _A[5], 1: 'true', 2: 'special', 3: '0', 5: '0', 6: '0', 13: '0',
                       20: '0', 27: '10', 30: '100000', 31: '100000', 34: '(None)', 35: '0',
                       39: '(None)', 46: '0', 47: '211', 48: '5', 49: ELEMENT_TOKEN,
                       51: '25000', 52: '25000'},
         '击杀敌人≥1 → 赋予全队(雷) 技能槽 25%'),
        ('1110033#0', {0: _A[5], 1: 'true', 2: 'special', 3: '0', 5: '0', 6: '0', 13: '0',
                       20: '0', 27: '10', 30: '100000', 31: '100000', 34: '(None)', 35: '0',
                       39: '(None)', 46: '0', 47: '226', 48: '', 49: '', 51: '5000000',
                       52: '5000000'},
         '击杀敌人≥1 → 自身 追加连击 50'),
    ),
    # 6 副位友好档：全队麻痹无效（麻痹中的成员不产生直击 ⇒ 对直击队是真收益）＋ 全队体力
    '1399916': (
        ('1411833#3', {0: _A[6], 1: 'true', 2: 'condition', 3: '0', 5: '0', 6: '0',
                       13: '0', 20: '0', 27: '0', 30: '', 31: '', 34: '', 36: '',
                       39: '(None)', 46: '0', 47: '69', 48: '5', 49: ELEMENT_TOKEN},
         '赋予全队(雷) 麻痹无效'),
        ('1410021#0', {0: _A[6], 1: 'true', 2: 'condition', 3: '0', 5: '0', 6: '0',
                       13: '0', 20: '0', 27: '0', 39: '(None)', 46: '0', 47: '205',
                       48: '5', 49: ELEMENT_TOKEN, 51: '25000', 52: '25000'},
         '赋予全队(雷) HP 25%'),
    ),
}

#: 这两个 kind 写进队长表 = C7050（裁决 §2、框架 §10.3）。只许出现在 ability 表。
ABILITY_ONLY_KINDS = ("422", "724", "713")
#: 瞬发常驻型段数/取最大值类 kind，与「取最大值类 × 连击触发同键」会撞 C2308
#: （记忆 ``wf-direct-attack-and-buffcount-kinds``）。本套件段数统一走技能 DSL，词条层零行。
C2308_KINDS = ("201", "202", "521")

#: 队长／词条的 kind 列（layout 见设计稿 plan.*.layout）。
LEADER_KIND_COLUMNS = (25, 45, 95, 107)
ABILITY_KIND_COLUMNS = (27, 47, 97, 109)


# ------------------------------------------------------------------ 面板文案
# 逐行 = rework1/panel/kuro.json（作者已过目）。desc_override 会盖掉客户端逐行画的 Ⓜ，
# 主位限制的键（槽 3，c1 = 'false'）必须每行自带 <icon id='main'>。

MAIN_ICON = " <icon id='main'>  "

PANEL_LEADER = (
    # 2026-09-27 第三轮面板同条件合并（作者「同一个条件的提升能不能写到一起来简化描述」）：队长#0/#1
    # 同为持续·Fever → 赋予全队(雷)，原第 1、2 行并为一行，只省略重复的对象名（wf_balance_20260927c_kuro）。
    "Fever中：赋予雷属性角色直接攻击伤害＋400%、攻击力＋200%",
    "自身Fever持续时间延长＋25%",
    "雷属性共鸣时，非Fever状态下：发动技能，自身Fever槽＋50%",
    # 2026-09-27 平衡第二批：第 5 行 = 能力2 #3（前置 42 仅队长时，trigger 107 队长表零先例的承载行）；
    # 第 6 行 = 队长 L5。无上限成长按作者裁决写到效果为止，不跟「可无限累积」。
    # 共鸣前缀按第二批口径 D 写「雷属性共鸣时，」。
    # 2026-09-27 第三轮（wf_balance_20260927c_kuro）：两行数字 5% → 35%、30% → 105%。
    "雷属性共鸣时，自身技能每命中1次，自身攻击力＋35%",
    "每次进入Fever：雷属性角色直击伤害＋105%",
)

#: 536「技能强化」条目：按裁决 §3 不写数字与时间。
#: 2026-09-27 第三轮技能强化条目口径 R1–R4（wf_balance_20260927c_kuro 第 7 节；作者「技能里面不要重复描述强化后的效果,
#: 规范并简化描述」）：官方格式点名技能、定性；删去两支相同的「并按直接攻击伤害判定」（判定区 buffTargetAs 两支都是 4，
#: 技能本体，技能说明已写）；原写在能力3 面板第 5、6 行、带数值与秒数的随机抽取表与骰运 6 层翻倍表属于旗号 1 开支
#: （build_roulette / full_dice.apply 只进强化分支）⇒ 定性并入本条目，能力3 那两行删除。
CAS_SKILL_FLAG_TEXT = ("强化『博饼·满堂彩』：摇碗的持续时间延长，威力随连击数提升；释放后随机抽取增益"
                       "（攻击力提升、Fever槽上升、贯穿效果、直接攻击伤害提升、连击增加、队长技能槽上升），"
                       "抽取次数随「骰运」层数提升，「骰运」达到上限时增益效果提升")

PANEL_ABILITY: dict[int, tuple[str, ...]] = {
    1: (
        "战斗开始时：自身技能槽＋50%",
        # 2026-09-27 第三轮 R2（wf_balance_20260927c_kuro 第 7 节）：开关行 1399911#1 带雷共鸣前置、c1=true
        # ⇒ 面板行 =「雷属性共鸣时，」＋ 强化条目原文（不带主位图标）。
        "雷属性共鸣时，" + CAS_SKILL_FLAG_TEXT,
    ),
    2: (
        # 2026-09-27 第二批：50% 不限次 → 2% × 25；上限按本角色骰运行写法「，最多N次」，共鸣前缀按口径 D 用「，」
        # 2026-09-27 第三轮作者追加（wf_balance_20260927c_kuro 第 6 节）：2% × 25 → 5% × 25
        "雷属性共鸣时，自身技能每命中1次，队长攻击力＋5%，最多25次",
        "自身处于「豹步」状态时：雷属性角色攻击力＋250%",
    ),
    3: (
        "雷属性共鸣时，非Fever状态下：雷属性角色直接攻击合计每达到45次，自身Fever槽＋35%",
        "每次进入Fever：雷属性角色直击伤害＋40%，最多3次",               # 2026-09-27 第二批：150% 不限次 → 40% × 3
        "Fever中：雷属性角色每直击20次，自身Fever槽－50%",
        # 2026-09-27 第三轮面板统一口径 3（wf_balance_20260927c_kuro）：共鸣前缀写「雷属性共鸣时，」
        # 2026-09-27 第三轮 R2（同模块第 7 节）：原第 5、6 行（强化分支的抽取表、骰运 6 层翻倍表）删除，定性并入强化条目。
        "雷属性共鸣时，雷属性角色每直击500次，自身「骰运」＋1层，最多6层",
    ),
    4: ("雷属性共鸣时：每次获得贯穿效果，自身技能槽＋5%、连击＋50（冷却时间：3秒）",),
    5: ("击败敌人时：雷属性角色技能槽＋25%、连击＋50",),
    # 2026-09-27 第三轮面板同条件合并：能力6 #0/#1 同为无条件常驻 → 赋予全队(雷)，两行并一行。
    6: ("雷属性角色免疫麻痹效果、生命值＋25%",),
}


def ability_key(slot: int) -> str:
    """词条键 = ``<cid><槽号>``（1399911 … 1399916）。"""
    return f"{CID_S}{slot}"


def _main_only(slot: int) -> bool:
    """该槽是否 Ⓜ 主位限制（ability c1 = ``'false'`` ＝不可上合击位）。"""
    return ABILITY[ability_key(slot)][0][1].get(1) == "false"


def _override_text(slot: int) -> str:
    prefix = MAIN_ICON if _main_only(slot) else ""
    return "\n".join(prefix + line for line in PANEL_ABILITY[slot])


CAS_TEXTS = {
    CAS_CHANGE_SKILL: CAS_SKILL_FLAG_TEXT,
    CAS_LEADER: "\n".join(PANEL_LEADER),
    **{CAS_ABILITY[slot]: _override_text(slot) for slot in range(1, 7)},
}
SKILL_FLAG_TEXT_KEYS = (CAS_CHANGE_SKILL,)


# ------------------------------------------------------------------ 技能

#: ``action_skill`` c4/c5：作者放行第 5 条「黑 550 —— 觉醒前后两档都写这个数」。
#: 母本原值是 490/490 与 490/440。
SKILL_ENERGY = {"1": ("550", "550"), "2": ("550", "550")}

#: ``CreateNormalAttack`` 下标 6（倍率）：旧 → 新。15 段 × 2.7 = 40.5 倍（裁决 §2「辅助技能 36–50×」）。
SKILL_MULTIPLIER = {
    "1": ([{"min": 0.5333333333333333, "max": 0.5333333333333333}], [{"min": 1.8, "max": 1.8}]),
    "2": ([{"min": 0.6933333333333334, "max": 0.8}], [{"min": 2.34, "max": 2.7}]),
}

#: ``FindAllSubjects(33)`` 下 ``CreateCondition`` 的 AC 列表：旧（母本 PF 伤害）→ 新（直击伤害）。
SKILL_DIRECT_AC = {
    "1": (["ACPowerFlipDamage", [{"min": 720, "max": 720}], [{"min": 0.3, "max": 0.3}],
           [{"min": 1, "max": 1}]],
          ["ACDirectDamage", [{"min": 900, "max": 900}], [{"min": 1.0, "max": 1.0}],
           [{"min": 1, "max": 1}]]),
    "2": (["ACPowerFlipDamage", [{"min": 900, "max": 900}], [{"min": 0.4, "max": 0.5}],
           [{"min": 1, "max": 1}]],
          ["ACDirectDamage", [{"min": 1200, "max": 1200}], [{"min": 1.2, "max": 1.5}],
           [{"min": 1, "max": 1}]]),
}

#: 追加的第二条 ``CreateCondition`` 的 AC：全队＋协力球 **3 段**追加直接攻击。
#: 跨角色段数取优不相加（卡 B §1.1）：凯尔 +300% ＞ 罗尔夫 +200% ＞ 黑 +80%/+100%，
#: 黑是辅助，% 最低 ⇒ 同队时被主 C 顶掉，不会把主 C 拉低。
SKILL_ADDITIONAL_AC = {
    "1": ["ACAdditionalDirectAttack", [{"min": 900, "max": 900}], [{"min": 3, "max": 3}],
          [{"min": 0.8, "max": 0.8}], [{"min": 1, "max": 1}]],
    "2": ["ACAdditionalDirectAttack", [{"min": 1200, "max": 1200}], [{"min": 3, "max": 3}],
          [{"min": 0.85, "max": 1.0}], [{"min": 1, "max": 1}]],
}

#: ``CreateHitArea`` 命令列表下标 24（= params[23] buffTargetAs）：0 自动 → **4 按直接攻击伤害判定**。
HITAREA_BUFF_TARGET_SLOT = 24
HITAREA_BUFF_TARGET_AS = 4

#: S1 取消后摇：母本 ``[-18, 75, ["Stop"], ["AB"], 0]`` → 官方千岳 ``psychic_tohru`` 的非定住形。
STOPBALL_BEFORE = [-18, 75, ["Stop"], ["AB"], 0]
STOPBALL_AFTER = [-18, 30, ["RestoreToSpeedBeforeActionExecution"], ["AB"], 0]

#: 强化分支的判定区旋钮（常态 → 强化）。每段间隔由 ``CalculatedUsingMaxNumOfHits`` 自动算
#: ⇒ 180/45 仍是 4 帧一跳，只是打得更久（总倍率 ×3），手感不变。
HITAREA_LIFETIME = (60, 180)
HITAREA_MAX_HITS = (15, 45)
CLOSE_WAIT = (59, 179)
EFFECT_LIFETIME = (60, 180)

#: 骰运轮盘旋钮。
ROULETTE_SLOTS = 6                 # 骰运上限 6 ⇒ 最多 6 个轮盘
ROULETTE_BIND_BASE = 20            # 母本只用了绑定 id 3；20–25 不会撞
ROULETTE_FRAMES = 900              # 15 秒
ROULETTE_ATTACK = 5.0              # 攻击力 +500%
ROULETTE_DIRECT = 5.0              # 直击伤害 +500%
ROULETTE_FEVER_POINT = 250         # 官方最高档（AddFeverPoint 只能加点数，不能按槽比例）
ROULETTE_COMBO = 500               # 连击 +500
ROULETTE_LEADER_SKILL = 0.15       # 队长技能槽 +15%（选择器 34 = 队长）
LEADER_SELECTOR = 34               # 官方 student_gunsmith_2（夏·丝丝）实读
CREATE_CONDITION_TARGET_KIND = 3   # subject -17 下官方 277 处都是 3；错配 = 施法 C16102

#: 母本整树的命令计数指纹：任何一项对不上都说明母本漂移或改错了结构。
DONOR_COMMAND_COUNTS = {
    "StopBall": 1, "ShowEffect": 4, "CreateHitArea": 1, "ShakeCamera": 1,
    "CreateNormalAttack": 1, "FindAllSubjects": 1, "CreateCondition": 1,
}
#: 改完之后应有的命令计数（两档相同）。
MUTATED_COMMAND_COUNTS = {
    "StopBall": 1,
    "ShowEffect": 7,                     # 开碗 1 ＋（旋转/吹雪/收碗）×2 分支
    "CreateHitArea": 2,
    "ShakeCamera": 2,
    "CreateNormalAttack": 2,
    "FindAllSubjects": 1 + ROULETTE_SLOTS,
    "CreateCondition": 2 + 3 * ROULETTE_SLOTS,
    "ConditionalsChangeSkillFlag": 1,
    "ConditionalsProbability": ROULETTE_SLOTS,
    "ProbabilityWeight": 6 * ROULETTE_SLOTS,
    "ConditionalsConditionAccumulationNumber": ROULETTE_SLOTS - 1,
    "AddFeverPoint": ROULETTE_SLOTS,
    "AddCombo": ROULETTE_SLOTS,
    "AddSkillPoint": ROULETTE_SLOTS,
}

OFFICIAL_EFFECT_PREFIX = f"battle/effect/skill_unique/{TEMPLATE_CODE}/"


# ------------------------------------------------------------------ DSL 工具

def _walk(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from _walk(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _walk(child)


def _command_slots(node, name: str, out: list | None = None) -> list[tuple[list, int]]:
    """找出 ``["Command", [<name>, …]]`` 在其父列表里的位置，返回 ``[(父列表, 下标), …]``。"""
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


def effect_paths(tree) -> list[str]:
    """树里所有 ``SpecifyEffectDirectly`` 的特效路径。"""
    return [node[1] for node in _walk(tree)
            if isinstance(node, list) and len(node) == 2
            and node[0] == "SpecifyEffectDirectly" and isinstance(node[1], str)]


def _cmd(*payload) -> list:
    return ["Command", list(payload)]


def _create_condition(subject: int, ac: list) -> list:
    """``CreateCondition`` 12 参，形状逐格照抄母本（下标 10 = 付与对象种类）。"""
    return _cmd("CreateCondition", subject, [ac], [{"min": 1, "max": 1}],
                ["GenericConditionHitEffect"], True, False, "", None, False,
                CREATE_CONDITION_TARGET_KIND, [{"min": 1, "max": 1}], False)


def _roulette_effects(bind: int) -> list[list]:
    """一个轮盘的 6 个分支体（各是一条语句）。顺序 = 面板文案顺序。"""
    frames = [{"min": ROULETTE_FRAMES, "max": ROULETTE_FRAMES}]
    one = [{"min": 1, "max": 1}]
    return [
        # ① 攻击力 +500%（15 秒）
        _create_condition(-17, ["ACAttackPoint", frames,
                                [{"min": ROULETTE_ATTACK, "max": ROULETTE_ATTACK}], one]),
        # ② Fever 槽大幅上升（DSL 只能加固定点数，官方最高档 250 —— _deviations kuro #1）
        _cmd("AddFeverPoint", [{"min": ROULETTE_FEVER_POINT, "max": ROULETTE_FEVER_POINT}]),
        # ③ 贯穿效果（15 秒）
        _create_condition(-17, ["ACPiercing", frames]),
        # ④ 直击伤害 +500%（15 秒）
        _create_condition(-17, ["ACDirectDamage", frames,
                                [{"min": ROULETTE_DIRECT, "max": ROULETTE_DIRECT}], one]),
        # ⑤ 连击 +500
        _cmd("AddCombo", [{"min": ROULETTE_COMBO, "max": ROULETTE_COMBO}]),
        # ⑥ 队长技能槽 +15%（选择器 34 = 队长，官方 student_gunsmith_2 实读）
        _cmd("FindAllSubjects", bind, LEADER_SELECTOR, [], [], [], [], [], ["DoNothing"],
             ["Block", [_cmd("AddSkillPoint", bind,
                             [{"min": ROULETTE_LEADER_SKILL, "max": ROULETTE_LEADER_SKILL}])]]),
    ]


def _wheel(index: int) -> list:
    """一个等权 6 选 1 轮盘。

    ``ConditionalsProbability`` 的分支形状是强校验的：每个分支**恰好两个元素**，
    ``[0]`` 是 ``Command(ProbabilityWeight w)``、``[1]`` 是 ``Block``；偏差直接
    ``throw INTERNAL ERROR`` ＝进战斗崩（官方先例 ``dryad_hw23_2``，权重 5/95）。
    """
    branches = [["Block", [_cmd("ProbabilityWeight", 1), ["Block", [effect]]]]
                for effect in _roulette_effects(ROULETTE_BIND_BASE + index)]
    return _cmd("ConditionalsProbability", ["Block", branches])


def build_roulette() -> list[list]:
    """骰运门链：抽取次数 = ``max(1, 骰运层数)``，上限 6。返回**语句列表**。

    ``ConditionalsConditionAccumulationNumber`` 唯一官方先例 ``combat_soldier_smr22_2``：
    ``[["DCUnique", <uid>], <阈值>, <成立分支>, <否则分支>]``；空分支写 ``["Block", []]``，
    **不能写 ``["DoNothing"]``**（那是 IfTargetNotFound 枚举，进游戏 F1009）。
    """
    node = ["Block", [_wheel(ROULETTE_SLOTS - 1)]]
    for level in range(ROULETTE_SLOTS, 1, -1):
        gate = _cmd("ConditionalsConditionAccumulationNumber", ["DCUnique", int(UID_DICE)],
                    level, node, ["Block", []])
        node = ["Block", [_wheel(level - 2), gate]]
    return list(node[1])


def _enhance_event(event: list) -> None:
    """强化分支的 ``Event Wait 10`` 就地改：判定区寿命／段数／连击加成／特效寿命／收碗等待。"""
    if not (isinstance(event, list) and len(event) == 2 and event[0] == "Event"
            and isinstance(event[1], list) and event[1][0] == "Wait"):
        raise KuroError(f"enhanced branch expects the donor Wait event, got {event[:1]!r}")
    inner = event[1][3]
    if not (isinstance(inner, list) and inner[0] == "Block" and len(inner[1]) == 2):
        raise KuroError("donor Wait event body drifted (expected 2 statements)")
    hit_area = inner[1][0][1]
    close_event = inner[1][1]

    if hit_area[13] != ["SpecifyHitAreaLifetimeDirectly", HITAREA_LIFETIME[0]]:
        raise KuroError(f"donor hit-area lifetime drifted: {hit_area[13]!r}")
    hit_area[13] = ["SpecifyHitAreaLifetimeDirectly", HITAREA_LIFETIME[1]]
    if hit_area[15] != ["Some", [{"min": HITAREA_MAX_HITS[0], "max": HITAREA_MAX_HITS[0]}]]:
        raise KuroError(f"donor hit-area max hits drifted: {hit_area[15]!r}")
    hit_area[15] = ["Some", [{"min": HITAREA_MAX_HITS[1], "max": HITAREA_MAX_HITS[1]}]]

    # 判定区里的两条 ShowEffect（旋转／吹雪）跟着加长，否则演出与判定脱节
    for statement in hit_area[20][1]:
        show = statement[1]
        if show[5] != ["SpecifyEffectLifetimeDirectly", EFFECT_LIFETIME[0]]:
            raise KuroError(f"donor effect lifetime drifted: {show[5]!r}")
        show[5] = ["SpecifyEffectLifetimeDirectly", EFFECT_LIFETIME[1]]

    # CreateNormalAttack 下标 8 = enablesComboBonus（×(1 + 连击 × 0.005)，无上限）
    cna = hit_area[23][1][1][1]
    if cna[0] != "CreateNormalAttack" or cna[8] is not False:
        raise KuroError(f"donor CreateNormalAttack combo flag drifted: {cna[:1]!r} {cna[8]!r}")
    cna[8] = True

    if close_event[1][1] != CLOSE_WAIT[0]:
        raise KuroError(f"donor close-effect wait drifted: {close_event[1][1]!r}")
    close_event[1][1] = CLOSE_WAIT[1]


def mutate_tree(tree, level: str):
    """母本整树 → 本角色的树（S1–S6）。返回 ``(tree, evidence)``；结构不符直接抛错。"""
    counts = _command_counts(tree)
    if counts != DONOR_COMMAND_COUNTS:
        raise KuroError(f"donor skill tree {level} drifted: commands {counts} "
                        f"!= {DONOR_COMMAND_COUNTS}")
    if not (isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl"):
        raise KuroError(f"donor skill tree {level}: unexpected root {tree[:2]!r}")
    if tree[1] != 2 or tree[10] != 0:
        # tree[10] = buffTargetAs（记忆 ``wf-dsl-damage-attribution-bufftargetas``）：
        # 0 = 自动。伤害归属由判定区那一格（S2）决定，根头保持 0。
        raise KuroError(f"donor root header {level}: movementPriority={tree[1]} "
                        f"buffTargetAs={tree[10]}, expected 2/0")

    # --- S1 取消后摇：StopBall 换官方千岳的非定住形
    (sb_parent, sb_index), = _command_slots(tree, "StopBall")
    stop_ball = sb_parent[sb_index][1]
    if stop_ball[1:] != STOPBALL_BEFORE:
        raise KuroError(f"donor StopBall drifted: {stop_ball[1:]!r} != {STOPBALL_BEFORE!r}")
    stop_ball[1:] = copy.deepcopy(STOPBALL_AFTER)

    # --- S2 CreateHitArea params[23] buffTargetAs：0 → 4（按直接攻击伤害判定）
    (ha_parent, ha_index), = _command_slots(tree, "CreateHitArea")
    hit_area = ha_parent[ha_index][1]
    if len(hit_area) != 27:
        raise KuroError(f"donor CreateHitArea has {len(hit_area)} slots, expected 27")
    if hit_area[HITAREA_BUFF_TARGET_SLOT] != 0:
        raise KuroError(f"donor CreateHitArea[{HITAREA_BUFF_TARGET_SLOT}] "
                        f"{hit_area[HITAREA_BUFF_TARGET_SLOT]!r} != 0")
    if hit_area[14] != ["CalculatedUsingMaxNumOfHits", HITAREA_MAX_HITS[0]]:
        raise KuroError(f"donor CreateHitArea hit budget drifted: {hit_area[14]!r}")
    hit_area[HITAREA_BUFF_TARGET_SLOT] = HITAREA_BUFF_TARGET_AS

    # --- S3 CreateNormalAttack 下标 6（倍率）
    (cna_parent, cna_index), = _command_slots(tree, "CreateNormalAttack")
    cna = cna_parent[cna_index][1]
    if cna[2] != 255:
        # 255 = 随自身属性。DSL 显式元素码只有 CreateNormalAttack[2] 有 +1 偏移
        # （记忆 ``wf-dsl-element-code-offset``），255 是哨兵，这一格不动。
        raise KuroError(f"CreateNormalAttack element slot {cna[2]!r} != 255")
    before_mult, after_mult = SKILL_MULTIPLIER[level]
    if cna[6] != before_mult:
        raise KuroError(f"CreateNormalAttack multiplier {cna[6]!r} != donor {before_mult!r}")
    cna[6] = copy.deepcopy(after_mult)

    # --- S4 FindAllSubjects(33) 下 CreateCondition 的 AC 列表：PF 伤害 → 直击伤害
    (fas_parent, fas_index), = _command_slots(tree, "FindAllSubjects")
    find_all = fas_parent[fas_index][1]
    if find_all[1] != 3 or find_all[2] != 33:
        raise KuroError(f"donor FindAllSubjects binding/selector {find_all[1:3]!r} != [3, 33]")
    (cc_parent, cc_index), = _command_slots(tree, "CreateCondition")
    donor_cmd = cc_parent[cc_index]
    body = donor_cmd[1]
    if len(body) != 13:
        raise KuroError(f"donor CreateCondition has {len(body)} slots, expected 13")
    if body[1] != find_all[1]:
        # CHA p1 必须 = 所在 FindAll 的绑定 id（记忆 ``wf-dsl-subject-lookup-map``）
        raise KuroError(f"CreateCondition subject {body[1]!r} != FindAllSubjects binding {find_all[1]!r}")
    if body[10] != CREATE_CONDITION_TARGET_KIND:
        # 下标 10 = 付与对象种类：选择器 33/82 写 3（记忆 ``wf-createcondition-target-kind``）；
        # 错配 = 施法 C16102。母本这条已经是 3，整条克隆 ⇒ 原样保留。
        raise KuroError(f"donor CreateCondition target kind {body[10]!r} != 3")
    if body[12] is not False:
        raise KuroError(f"donor CreateCondition forceApply {body[12]!r} != False")
    before_ac, after_ac = SKILL_DIRECT_AC[level]
    if body[2] != [before_ac]:
        raise KuroError(f"CreateCondition AC {body[2]!r} != donor [{before_ac!r}]")
    # 下标 2 是 **AC 列表**（母本是 ``[[ACPowerFlipDamage, …]]`` 一条）：直接塞裸 AC
    # 会把嵌套层吃掉一层，往返自检抓不到，进战斗才炸。
    body[2] = [copy.deepcopy(after_ac)]

    # --- S5 同一个 Block 内追加第二条 CreateCondition（3 段追加直接攻击）
    extra = copy.deepcopy(donor_cmd)
    extra[1][2] = [copy.deepcopy(SKILL_ADDITIONAL_AC[level])]
    cc_parent.insert(cc_index + 1, extra)

    # --- S6 把「Wait 10 → 判定区」整段包进 ConditionalsChangeSkillFlag 两分支
    statements = tree[11][1]
    event_index = next(i for i, node in enumerate(statements)
                       if isinstance(node, list) and node and node[0] == "Event")
    plain_event = statements[event_index]
    enhanced_event = copy.deepcopy(plain_event)
    _enhance_event(enhanced_event)
    roulette = build_roulette()
    statements[event_index] = _cmd(
        "ConditionalsChangeSkillFlag", 1,
        ["Block", [enhanced_event, *roulette]],     # 强化档（雷共鸣时由 IC 536 打开）
        ["Block", [plain_event]])                   # 常态档

    # --- 特效：全部还是官方母本路径（零克隆、零图集增量）
    paths = effect_paths(tree)
    stray = [p for p in paths if not p.startswith(OFFICIAL_EFFECT_PREFIX)]
    if stray:
        raise KuroError(f"skill {level} references non-official effect paths: {stray}")
    if len(paths) != MUTATED_COMMAND_COUNTS["ShowEffect"]:
        raise KuroError(f"skill {level} has {len(paths)} effect refs, expected "
                        f"{MUTATED_COMMAND_COUNTS['ShowEffect']}")
    if len(set(paths)) != DONOR_COMMAND_COUNTS["ShowEffect"]:
        raise KuroError(f"skill {level} effect path set drifted: {sorted(set(paths))}")

    after = _command_counts(tree)
    if after != MUTATED_COMMAND_COUNTS:
        raise KuroError(f"mutated skill tree {level}: commands {after} != {MUTATED_COMMAND_COUNTS}")

    evidence = {
        "level": level,
        "stop_ball": {"before": STOPBALL_BEFORE, "after": STOPBALL_AFTER,
                      "why": "取消后摇：官方千岳 psychic_tohru 的非定住形（卡 C §5.4）"},
        "hit_area_buff_target_as": {"before": 0, "after": HITAREA_BUFF_TARGET_AS,
                                    "slot": HITAREA_BUFF_TARGET_SLOT},
        "create_normal_attack": {"before": before_mult, "after": copy.deepcopy(cna[6])},
        "create_condition": {"direct": {"before": before_ac, "after": after_ac},
                             "additional": copy.deepcopy(SKILL_ADDITIONAL_AC[level]),
                             "target_kind": body[10], "subject": body[1]},
        "change_skill_flag": {"enhanced": {"hit_area_lifetime": HITAREA_LIFETIME[1],
                                           "max_hits": HITAREA_MAX_HITS[1],
                                           "enables_combo_bonus": True},
                              "plain": {"hit_area_lifetime": HITAREA_LIFETIME[0],
                                        "max_hits": HITAREA_MAX_HITS[0],
                                        "enables_combo_bonus": False}},
        "roulette": {"wheels": ROULETTE_SLOTS, "unique": UID_DICE,
                     "binds": [ROULETTE_BIND_BASE + i for i in range(ROULETTE_SLOTS)],
                     "effects": ["ACAttackPoint", "AddFeverPoint", "ACPiercing",
                                 "ACDirectDamage", "AddCombo", "AddSkillPoint(选择器34=队长)"]},
        "effect_refs": sorted(set(paths)),
    }
    return tree, evidence


def donor_program(ctx, level: str) -> str:
    """母本技能程序路径：母本是 ★4 ⇒ ``rare4/``（``program_path`` 用的是本角色的 ★5）。"""
    import wf_seasonal7_common as S7C
    row = S7C.csv_split(ctx.official_flat(CHARACTER)[str(TEMPLATE_ID)])[0]
    rarity = row[2]
    if rarity != "4":
        raise KuroError(f"template {TEMPLATE_ID} rarity {rarity!r} != '4' (donor path would drift)")
    return f"battle/action/skill/action/rare{rarity}/{TEMPLATE_CODE}${TEMPLATE_CODE}_{level}"


# ------------------------------------------------------------------ 固有状态图标

def _canvas():
    from PIL import Image, ImageDraw
    size = 48 * ICON_SCALE
    canvas = Image.new("RGB", (size, size), ICON_INK)
    draw = ImageDraw.Draw(canvas)

    def box(x0, y0, x1, y1):
        return [x0 * ICON_SCALE, y0 * ICON_SCALE, x1 * ICON_SCALE, y1 * ICON_SCALE]

    draw.rounded_rectangle(box(0, 0, 47.9, 47.9), radius=10 * ICON_SCALE,
                           outline=ICON_GOLD, width=2 * ICON_SCALE)
    return canvas, draw, box


def _finish(canvas, frame):
    from PIL import Image
    out = canvas.resize((48, 48), Image.LANCZOS).convert("RGBA")
    out.putalpha(frame.getchannel("A"))
    return out


def draw_dice_icon(frame):
    """48×48「骰运」图标：夜靛底 ＋ 金边 ＋ 立体金骰子（五点面）＋ 极细月牙。

    8× 画 + LANCZOS 缩，**alpha 一格不改**（沿用官方画框 donor）。
    """
    if frame.size != (48, 48):
        raise KuroError(f"unique_condition icon frame is {frame.size}, expected (48, 48)")
    canvas, draw, box = _canvas()
    # 月牙：整圆挖掉一个偏移的圆 ⇒ 极细的一弯，压在骰子左上、由骰子盖住一角
    draw.ellipse(box(3.5, 3.0, 15.0, 14.5), fill=ICON_PIP)
    draw.ellipse(box(5.9, 1.4, 17.4, 12.9), fill=ICON_INK)
    # 骰子：背光面（偏移一点的暗金）→ 骰身 → 受光面
    draw.rounded_rectangle(box(14.2, 14.6, 36.0, 36.4), radius=5 * ICON_SCALE, fill=ICON_GOLD_DARK)
    draw.rounded_rectangle(box(13.0, 13.4, 34.8, 35.2), radius=5 * ICON_SCALE, fill=ICON_GOLD)
    draw.rounded_rectangle(box(14.4, 14.8, 33.4, 24.0), radius=3 * ICON_SCALE, fill=ICON_GOLD_LIGHT)
    # 五点面：四角 + 正中
    for cx, cy in ((18.4, 18.8), (29.4, 18.8), (23.9, 24.3), (18.4, 29.8), (29.4, 29.8)):
        draw.ellipse(box(cx - 2.1, cy - 2.1, cx + 2.1, cy + 2.1), fill=ICON_PIP)
    return _finish(canvas, frame)


def draw_step_icon(frame):
    """48×48「豹步」图标：夜靛底 ＋ 金边 ＋ 金色猫爪印 ＋ 三道速度线。

    与骰运/引擎点火/月牙/回响同一套（夜底＋金边，外框取官方图标的 alpha）。
    """
    if frame.size != (48, 48):
        raise KuroError(f"unique_condition icon frame is {frame.size}, expected (48, 48)")
    canvas, draw, box = _canvas()
    # 速度线（左侧三道，暗金／亮金交替，表示「正在移动」）
    for index, (y, x0, x1) in enumerate(((16.0, 5.5, 13.5), (23.0, 4.5, 12.0),
                                         (30.0, 5.5, 13.5))):
        color = ICON_GOLD_LIGHT if index == 1 else ICON_GOLD_DARK
        draw.rounded_rectangle(box(x0, y - 1.2, x1, y + 1.2),
                               radius=1.2 * ICON_SCALE, fill=color)
    # 掌垫：上宽下窄的圆角块 ＋ 顶缘一道受光
    draw.rounded_rectangle(box(19.5, 25.5, 40.5, 38.5), radius=6.0 * ICON_SCALE, fill=ICON_GOLD_DARK)
    draw.rounded_rectangle(box(18.5, 24.5, 39.5, 37.5), radius=6.0 * ICON_SCALE, fill=ICON_GOLD)
    draw.rounded_rectangle(box(21.0, 26.0, 37.0, 30.5), radius=2.2 * ICON_SCALE,
                           fill=ICON_GOLD_LIGHT)
    # 四个趾垫：沿掌垫上缘排成一道弧，彼此留 1.5px 以上空隙（缩到 48×48 后才分得开）
    for cx, cy in ((18.5, 20.0), (25.5, 16.5), (32.5, 16.5), (39.5, 20.0)):
        draw.ellipse(box(cx - 2.6, cy - 3.3, cx + 2.6, cy + 3.3), fill=ICON_GOLD)
        draw.ellipse(box(cx - 1.3, cy - 2.4, cx + 1.3, cy - 0.2), fill=ICON_GOLD_LIGHT)
    return _finish(canvas, frame)


UNIQUE_ICONS = {
    UID_DICE: (DICE_ICON + ".png", draw_dice_icon),
    UID_STEP: (STEP_ICON + ".png", draw_step_icon),
}


def install_unique_icons(ctx) -> dict[str, Any]:
    """把两张固有状态图标写进包。像素代理已经交付同路径的件时原样保留，不覆盖。

    manifest 门禁要求被表引用的资产在 ``roots.common`` 里声明 ⇒ 这两张图必须进包
    （引用官方路径当回落过不了门禁）。
    """
    import hashlib

    raw = ctx.official_read(UNIQUE_ICON_FRAME)
    if raw is None:
        raise KuroError(f"official baseline lacks the icon frame donor {UNIQUE_ICON_FRAME}")
    frame = ctx.png_open(raw)
    notes: dict[str, Any] = {}
    for key, (logical, painter) in UNIQUE_ICONS.items():
        staged = ctx.pack.pkg_path("common", logical)
        owner = (ctx.pack.owned_record("common", logical) or {}).get("owner")
        if staged.is_file() and owner == "pixel":
            data = staged.read_bytes()
            notes[key] = {"logical": logical, "source": "pixel", "owner": owner,
                          "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            continue
        data = ctx.png_store_bytes(painter(frame))
        ctx.write_asset("common", logical, data)
        back = ctx.png_open(staged.read_bytes())
        if back.size != (48, 48):
            raise KuroError(f"unique_condition icon {logical} is {back.size}, expected (48, 48)")
        if back.getchannel("A").tobytes() != frame.getchannel("A").tobytes():
            raise KuroError(f"unique_condition icon {logical} alpha differs from the frame donor")
        notes[key] = {"logical": logical, "source": "kit", "frame_donor": UNIQUE_ICON_FRAME,
                      "size": list(back.size), "sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data)}
    return notes


# ------------------------------------------------------------------ 面板字符串

def write_strings(ctx) -> dict[str, str]:
    """``custom_ability_string``：536 的条目串 ＋ 队长与 6 个词条槽的面板接管。"""
    declared = set(ctx.spec.extra_keys.get(KL.CAS, ()))
    missing = [key for key in CAS_TEXTS if key not in declared]
    if missing:
        raise KuroError(f"custom_ability_string keys not declared in SPEC['extra_keys']: {missing}")
    for key, text in CAS_TEXTS.items():
        for line in text.split("\n"):
            KL.check_panel(line.replace(MAIN_ICON, ""),
                           skill_flag=key in SKILL_FLAG_TEXT_KEYS, label=key)
    # desc_override 的键名 = "desc_override_" + 该块第 0 行的 string_id（c0）
    if CAS_LEADER != L.PANEL_OVERRIDE_KEY_PREFIX + LEADER[0][1][0]:
        raise KuroError(f"leader override key {CAS_LEADER!r} does not match the leader c0")
    for slot in range(1, 7):
        want = L.PANEL_OVERRIDE_KEY_PREFIX + ABILITY[ability_key(slot)][0][1][0]
        if CAS_ABILITY[slot] != want:
            raise KuroError(f"slot {slot} override key {CAS_ABILITY[slot]!r} != {want!r}")
        # 覆盖串会盖掉客户端逐行画的 Ⓜ ⇒ 主位键每行必须自带图标
        for line in CAS_TEXTS[CAS_ABILITY[slot]].split("\n"):
            if line.startswith(MAIN_ICON) != _main_only(slot):
                raise KuroError(f"slot {slot} desc_override main-position icon does not match c1")
    official = ctx.official_flat(KL.CAS)
    clashes = [key for key in CAS_TEXTS if key in official]
    if clashes:
        raise KuroError(f"custom_ability_string keys already exist officially: {clashes}")
    ctx.write_flat(KL.CAS, {key: [[text]] for key, text in CAS_TEXTS.items()})
    return dict(CAS_TEXTS)


# ------------------------------------------------------------------ 自查断言

def guard_rows(leader_rows, ability_rows) -> dict[str, Any]:
    """裁决 §8 / 设计稿 §14 的硬自查：724 只在 ability 表；词条里没有 201/202/521。"""
    for index, row in enumerate(leader_rows):
        hit = [row[col] for col in LEADER_KIND_COLUMNS if row[col] in ABILITY_ONLY_KINDS]
        if hit:
            raise KuroError(f"leader#{index}: kind {hit} 只许写 ability 表，写进队长表 = C7050")
    for key, rows in ability_rows.items():
        for index, row in enumerate(rows):
            hit = [row[col] for col in ABILITY_KIND_COLUMNS if row[col] in C2308_KINDS]
            if hit:
                raise KuroError(f"ability {key}#{index}: kind {hit} 会与取最大值类撞 C2308")
    patch_rows = [f"{key}#{index}" for key, rows in ability_rows.items()
                  for index, row in enumerate(rows)
                  if any(row[col] == "724" for col in ABILITY_KIND_COLUMNS)]
    if patch_rows != ["1399913#0", "1399913#2"]:
        raise KuroError(f"724 rows {patch_rows} != ['1399913#0', '1399913#2']")
    return {"ability_only_kinds": list(ABILITY_ONLY_KINDS), "leader_clean": True,
            "c2308_kinds_absent": list(C2308_KINDS), "kind_724_rows": patch_rows}


# ------------------------------------------------------------------ 设计稿互校

def _norm_donor(text: str) -> str:
    """设计稿的 donor 写法（``151171#L2`` / ``live 1499893#L2`` / ``… + …``）→ kit 写法。"""
    text = text.strip()
    prefix = ""
    if text.startswith("live "):
        prefix, text = "live:", text[5:].strip()
    text = text.split(" +")[0].strip()
    key, _, suffix = text.partition("#")
    if suffix.startswith("L"):
        suffix = str(int(suffix[1:]) - 1)
    return prefix + (f"{key}#{suffix}" if suffix else key)


def design_crosscheck(ctx) -> dict[str, Any]:
    """设计稿在场时逐条互校（身份 / 文案 / 行 donor·面板文案 / 雕像组 / 能量 / 面板串 / 语音路由）。

    设计稿在 gitignore 的 ``work/`` 下，缺失时只记一条 note，不阻塞构建。
    """
    path = MS.design_path(ctx.root, KEY)
    if not path.is_file():
        return {"design_json": str(path), "present": False,
                "note": "设计稿不在（work/ 未恢复）：本次以 kit 模块内联方案为准"}
    design = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []

    for name, want in (("key", KEY), ("cid", CID), ("code", CODE)):
        if design.get(name) != want:
            problems.append(f"{name} = {design.get(name)!r}, kit says {want!r}")
    for name, want in TEXTS.items():
        if design.get("texts", {}).get(name) != want:
            problems.append(f"texts.{name} drifted from the design")

    plan = design.get("plan", {})

    add = {entry.get("key"): entry for entry in plan.get("unique_conditions", {}).get("add", [])}
    if sorted(add) != sorted(UNIQUE_ICONS):
        problems.append(f"design unique_conditions {sorted(add)} != {sorted(UNIQUE_ICONS)}")
    else:
        for key, cap in ((UID_DICE, DICE_CAP), (UID_STEP, STEP_CAP)):
            if add[key].get("row", [None] * 5)[4] != cap:
                problems.append(f"design unique {key} cap {add[key]['row'][4]!r} != {cap!r}")

    rows = plan.get("leader_ability", {}).get("rows", [])
    if len(rows) != len(LEADER):
        problems.append(f"design has {len(rows)} leader rows, kit has {len(LEADER)}")
    for row, (donor, _cells, expect) in zip(rows, LEADER):
        if _norm_donor(str(row.get("donor"))) != donor:
            problems.append(f"leader #{row.get('index')}: donor {row.get('donor')!r} != {donor!r}")
        if row.get("desc_expected") != expect:
            problems.append(f"leader #{row.get('index')}: desc_expected drifted")

    keys = plan.get("ability", {}).get("keys", {})
    if sorted(keys) != sorted(ABILITY):
        problems.append(f"design ability keys {sorted(keys)} != kit {sorted(ABILITY)}")
    for key, records in ABILITY.items():
        entry = keys.get(key, {})
        if entry.get("statue_group") != STATUE_GROUPS[key]:
            problems.append(f"ability {key}: design statue_group {entry.get('statue_group')!r} "
                            f"!= {STATUE_GROUPS[key]!r}")
        designed = entry.get("records", [])
        if len(designed) != len(records):
            problems.append(f"ability {key}: design has {len(designed)} records, "
                            f"kit has {len(records)}")
        for record, (donor, _cells, expect) in zip(designed, records):
            if _norm_donor(str(record.get("donor"))) != donor:
                problems.append(f"ability {key}#{record.get('index')}: "
                                f"donor {record.get('donor')!r} != {donor!r}")
            if record.get("desc_expected") != expect:
                problems.append(f"ability {key}#{record.get('index')}: desc_expected drifted")

    strings = {row.get("key"): row.get("text")
               for row in plan.get("texts", {}).get("custom_ability_string", {}).get("rows", [])}
    if strings != CAS_TEXTS:
        drift = sorted(set(strings) ^ set(CAS_TEXTS)) or \
            [k for k in CAS_TEXTS if strings.get(k) != CAS_TEXTS[k]]
        problems.append(f"custom_ability_string drifted from the design: {drift}")

    skills = plan.get("skills", {})
    for level, (c4, c5) in SKILL_ENERGY.items():
        energy = skills.get("energy", {}).get(level, {})
        if (str(energy.get("c4")), str(energy.get("c5"))) != (c4, c5):
            problems.append(f"action_skill {level}: energy {energy!r} != {(c4, c5)!r}")
    changes = {change.get("id"): change for change in skills.get("changes", [])}
    if changes.get("S1", {}).get("new") != STOPBALL_AFTER:
        problems.append("skill S1 (StopBall) drifted from the design")
    if changes.get("S2", {}).get("new") != HITAREA_BUFF_TARGET_AS:
        problems.append(f"skill S2 new {changes.get('S2', {}).get('new')!r} "
                        f"!= {HITAREA_BUFF_TARGET_AS!r}")
    for level in ("1", "2"):
        want_old, want_new = SKILL_MULTIPLIER[level]
        got = changes.get("S3", {})
        if got.get("old", {}).get(level) != want_old or got.get("new", {}).get(level) != want_new:
            problems.append(f"skill S3 level {level}: multiplier drifted from the design")
        want_old_ac, want_new_ac = SKILL_DIRECT_AC[level]
        got = changes.get("S4", {})
        if got.get("old", {}).get(level) != want_old_ac or got.get("new", {}).get(level) != want_new_ac:
            problems.append(f"skill S4 level {level}: AC drifted from the design")
        got = changes.get("S5", {}).get("new", {}).get(level)
        if got != SKILL_ADDITIONAL_AC[level]:
            problems.append(f"skill S5 level {level}: AC drifted from the design")
    s6 = changes.get("S6", {}).get("new", {})
    if (s6.get("hit_area_lifetime"), s6.get("max_hits"), s6.get("roulette_wheels")) != \
            (HITAREA_LIFETIME[1], HITAREA_MAX_HITS[1], ROULETTE_SLOTS):
        problems.append(f"skill S6 (ConditionalsChangeSkillFlag) drifted from the design: {s6!r}")

    route = design.get("voice", {}).get("route", {})
    if {k: str(v) for k, v in route.items()} != {k: str(v) for k, v in VOICE_ROUTE.items()}:
        problems.append(f"voice route {route!r} != {VOICE_ROUTE!r}")

    if problems:
        raise KuroError("design/kuro.json disagrees with the kit: " + "; ".join(problems))
    return {"design_json": str(path), "present": True, "checked": [
        "identity", "texts", "unique_condition", "leader donors + panel text",
        "ability donors + panel text", "statue_group", "custom_ability_string",
        "skill energy", "skill S1–S6", "voice route"]}


# ------------------------------------------------------------------ build

def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.key, str(spec.cid), spec.code, spec.element) != (KEY, CID_S, CODE, ELEMENT):
        raise KuroError(f"spec identity mismatch: {spec.key}/{spec.cid}/{spec.code}/{spec.element}")
    if spec.template_code != TEMPLATE_CODE or str(spec.template_id) != str(TEMPLATE_ID):
        raise KuroError(f"spec template mismatch: {spec.template_id}/{spec.template_code}")
    if spec.rarity != 5 or spec.pf_type != PF_TYPE or spec.stance != STANCE:
        raise KuroError(f"spec rarity/pf/stance mismatch: "
                        f"{spec.rarity}/{spec.pf_type}/{spec.stance}")
    for index, uid in enumerate((UID_DICE, UID_STEP), start=1):
        if uid != f"{CID}0{index}" or len(uid) != 8:
            raise KuroError(f"unique_condition id {uid!r} must be 8 digits cid*100+n")

    notes: list[Any] = [design_crosscheck(ctx)]
    evidence: list[dict[str, Any]] = []

    # ---- 1) 像素/特效交付件（先装：固有状态图标要不要回落取决于它）
    pixel = KL.install_staged_assets(ctx)

    # ---- 2) 固有状态两条（图标先进包：manifest 门禁要求被引用的资产在 roots.common 里）
    icon_notes = install_unique_icons(ctx)
    unique_entries: dict[str, list[str]] = {}
    for n, (name, icon, frames, cap) in enumerate(
            ((DICE_NAME, DICE_ICON, DICE_FRAMES, DICE_CAP),
             (STEP_NAME, STEP_ICON, STEP_FRAMES, STEP_CAP)), start=1):
        code_suffix = icon.rsplit("/", 1)[-1]
        key, row = KL.unique_row(ctx, spec, n, donor=UNIQUE_DONOR,
                                 cells={0: code_suffix, 3: frames, 4: cap},
                                 name=name, icon=icon)
        unique_entries[key] = row
    if sorted(unique_entries) != sorted((UID_DICE, UID_STEP)):
        raise KuroError(f"unique keys {sorted(unique_entries)} != {sorted((UID_DICE, UID_STEP))}")
    KL.write_unique(ctx, spec, unique_entries)

    # ---- 3) character 行：语音路由 c9–c16 ＋ 队长技名 c18
    crow = list(ctx.pack.pkg_character_row())
    expect_cols = {0: CODE, 2: "5", 3: str(ELEMENT), 6: str(PF_TYPE), 8: CODE,
                   17: CID_S, 26: STANCE, 27: CID_S}
    for index, col in enumerate(range(19, 25)):
        expect_cols[col] = f"{CID_S}{index + 1}"
    drift = {i: (crow[i], v) for i, v in expect_cols.items() if crow[i] != v}
    if drift:
        raise KuroError(f"package character row differs from spec (rerun tables): {drift}")
    route = KL.voice_route(CODE, VOICE_ROUTE)
    crow[9:17] = route
    crow[18] = TEXTS["leader"]
    ctx.write_flat(CHARACTER, {CID_S: [crow]})

    # ---- 4) 队长技 5 行（2026-09-27 平衡第二批 +L5）
    leader_rows = []
    for index, (donor, cells, expect) in enumerate(LEADER):
        row, ev = KL.build_row(ctx, "leader_ability", donor, cells,
                               expect_describe=expect, label=f"leader#{index}")
        leader_rows.append(row)
        evidence.append(ev)

    # ---- 5) 词条 6 键 16 条（2026-09-27 平衡第二批 +1399912#3）
    ability_rows: dict[str, list[list[str]]] = {}
    for key, records in ABILITY.items():
        built = []
        for index, (donor, cells, expect) in enumerate(records):
            source, _, donor_key = donor.partition("live:")
            source, donor_key = ("live", donor_key) if donor_key else ("official", source)
            row, ev = KL.build_row(ctx, "ability", donor_key, cells, source=source,
                                   element=ELEMENT, expect_describe=expect,
                                   label=f"{key}#{index}")
            ev["source"] = source
            built.append(row)
            evidence.append(ev)
        KL.check_ability_key(built, key, CODE, int(key[-1]))
        if built[0][2] != STATUE_GROUPS[key]:
            raise KuroError(f"ability {key}: c2 {built[0][2]!r} != {STATUE_GROUPS[key]!r}")
        ability_rows[key] = built

    guards = guard_rows(leader_rows, ability_rows)
    ctx.write_flat(KL.LEADER, {CID_S: leader_rows})
    ctx.write_flat(KL.ABILITY, ability_rows)

    # ---- 6) 面板文案（desc_override 整块接管；逐行 = rework1/panel/kuro.json）
    strings = write_strings(ctx)
    panel = [line.replace(MAIN_ICON, "") for key in (CAS_LEADER, *CAS_ABILITY.values())
             for line in strings[key].split("\n")]
    for text in panel:
        KL.check_panel(text, label="panel row")
    for name in ("title", "skill1", "desc1", "skill2", "desc2", "leader", "profile"):
        KL.check_panel(TEXTS[name], label=f"texts.{name}")

    # ---- 7) action_skill：名称 / 描述 / 能量（其余列断言与母本一致）
    inner = ctx.pkg_nested(CODE, ACTION)
    if sorted(inner) != ["1", "2"]:
        raise KuroError(f"package action_skill inner keys {sorted(inner)} != ['1', '2']")
    new_inner: dict[str, list[list[str]]] = {}
    for level, cells in sorted(inner.items()):
        cells = list(cells)
        if len(cells) != 24:
            raise KuroError(f"action_skill {level}: {len(cells)} columns, expected 24")
        if cells[7] != ctx.program_path(level):
            raise KuroError(f"action_skill {level}: program {cells[7]!r} "
                            f"!= {ctx.program_path(level)!r}")
        if cells[2:4] != ["dynamic/skill/atk_surround", "true"]:
            raise KuroError(f"action_skill {level}: targeting columns changed {cells[2:4]}")
        if cells[8:17] != ["1", "0", "270", "", "0", "0", "", "", "(None)"]:
            raise KuroError(f"action_skill {level}: c8–c16 differ from the template {cells[8:17]}")
        if any(cells[17:]):
            raise KuroError(f"action_skill {level}: c17+ not empty {cells[17:]}")
        cells[0] = TEXTS[f"skill{level}"]
        cells[1] = TEXTS[f"desc{level}"]
        cells[4], cells[5] = SKILL_ENERGY[level]
        if cells[6] != "1":
            raise KuroError(f"action_skill {level}: c6 {cells[6]!r} != '1'")
        new_inner[level] = [cells]
    ctx.write_nested(ACTION, CODE, new_inner, replace_inner=True)

    # ---- 8) 技能 DSL 两档（官方 donor 树改参数；写后从包里回读比对）
    skill_evidence = []
    programs = []
    for level in ("1", "2"):
        source = donor_program(ctx, level)
        tree, ev = mutate_tree(ctx.template_dsl(source), level)
        tree = full_dice.apply(tree)
        ev['full_dice_rewards'] = 'six rewards doubled at six layers; same six draws'
        logical = ctx.write_dsl(ctx.program_path(level), tree)
        back = ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
        if back != tree:
            raise KuroError(f"skill {level}: package DSL read-back differs from the written tree")
        ev["logical"] = logical
        ev["donor_program"] = source
        skill_evidence.append(ev)
        programs.append(logical)

    # ---- 9) 语音路由目标
    switched = KL.write_voice_ready(ctx)
    lut_path = KL.pixel_dir(ctx) / "fx_lut.json"
    if lut_path.is_file():
        notes.append({"fx_lut": str(lut_path),
                      "unused": "本角色技能特效全部直接引用官方母本路径（零克隆），包内没有可换色的"
                                "特效件；要改色须先改设计稿改成 clone_effect_family 并重跑图集预检"})

    ctx.sync_character_mirrors()

    ctx.evidence_write("kit-rows.json", {
        "leader": [{"donor": donor, "cells": {str(k): v for k, v in cells.items()},
                    "describe": expect} for donor, cells, expect in LEADER],
        "ability": {key: {"statue_group": STATUE_GROUPS[key],
                          "records": [{"donor": donor,
                                       "cells": {str(k): v for k, v in cells.items()},
                                       "describe": expect}
                                      for donor, cells, expect in records]}
                    for key, records in ABILITY.items()},
        "unique_condition": unique_entries,
        "custom_ability_string": strings,
        "guards": guards,
        "rows": evidence,
    })
    ctx.evidence_write("kit-skills.json", {"programs": programs, "levels": skill_evidence})

    capabilities = {cap for ev in evidence for cap in ev.get("capabilities", ())}

    notes.extend([
        {"voice_route": route, "switched_action_skill": switched,
         "why": f"kind 1 ConditionExist / 条件种类 28（固有状态）/ 条件 id {UID_DICE}「骰运」："
                "骰运一旦获得就常驻 ⇒ 开局与开局后各听得到一种「技能准备好」台词。"
                "kind 3 ChangeSkillFlag 不能用：536 在共鸣队里常驻，会让 skill_ready 永不播"},
        {"unique_condition": {key: {"row": unique_entries[key], **icon_notes[key]}
                              for key in unique_entries}},
        {"pixel_install": pixel},
        {"statue_group": STATUE_GROUPS,
         "why": "裁决 §8：一键内 c2 必须单值。选组规则＝该键每个 kind 在官方基线上都有这一组的"
                "先例，多候选取「最小先例数最大」的（实扫见模块常量表）"},
        {"guards": guards,
         "why": "422/724/713 写进队长表 = C7050（裁决 §2、框架 §10.3）；词条里没有 201/202/521 "
                "⇒ 不会撞 C2308（段数统一走技能 DSL）"},
        {"effects": "零克隆：ShowEffect 全部引用官方 "
                    f"{OFFICIAL_EFFECT_PREFIX}*（开碗/摇碗旋转/金纸吹雪/收碗），"
                    "包内不含 battle/effect 目录 ⇒ 图集增量 0；"
                    "特效集合与上一版完全相同 ⇒ wf_offline_content 的位置表无需改"},
        {"skill_no_recovery": {"before": STOPBALL_BEFORE, "after": STOPBALL_AFTER},
         "why": "作者原话「黑的技能取消后摇释放技能不停下」。官方非定住先例＝千岳 psychic_tohru "
                "的 [-18, 30, RestoreToSpeedBeforeActionExecution, AB, 0]（卡 C §5.4）。"
                "不整条删除：Wait 10 与判定区都挂在 -18 上，完全不停会让判定圈跟着球飞走。"
                "属结构手术 ⇒ 预览器不可信，必须真机看一眼"},
        {"skill_enhanced_branch": {"gate": f"IC 536 [{CAS_CHANGE_SKILL}]（1399911#1，前置 2 雷共鸣）",
                                   "hit_area_lifetime": list(HITAREA_LIFETIME),
                                   "max_hits": list(HITAREA_MAX_HITS),
                                   "enables_combo_bonus": [False, True]},
         "why": "强化条目「摇碗的持续时间延长，威力随连击数提升」。每段间隔由 "
                "CalculatedUsingMaxNumOfHits 自动算 ⇒ 180/45 仍是 4 帧一跳，只是打得更久"},
        {"skill_roulette": {"wheels": ROULETTE_SLOTS, "gate": f"DCUnique {UID_DICE}（骰运）",
                            "draws": "max(1, 层数)，上限 6，每次独立掷点（无互斥原语）",
                            "leader_selector": LEADER_SELECTOR},
         "why": "随机只存在于 DSL（卡 B §4）。ConditionalsProbability 官方先例 dryad_hw23、"
                "ConditionalsConditionAccumulationNumber 官方先例 combat_soldier_smr22；"
                "「队长技能槽」用选择器 34（官方 student_gunsmith_2 夏·丝丝，09-21 作者纠正）"},
        {"skill_damage_type": "CreateHitArea params[23] = 4：按直接攻击伤害判定 ⇒ "
                              "吃直击伤害 UP／攻击力／雷耐性降低，不吃技能伤害 UP 与 410",
         "precedent": "live 169992 blackflower_wiz_yukata 两档各两处判定区实读 = 4"},
        {"skill_team_buff": {"direct_damage_up": {lv: SKILL_DIRECT_AC[lv][1][1:] for lv in ("1", "2")},
                             "additional_direct_attack": {lv: SKILL_ADDITIONAL_AC[lv][1:]
                                                          for lv in ("1", "2")}},
         "why": "选择器 33 = 队伍全员及协力球，是词条 t5 够不到的覆盖面；跨角色段数取优不相加 ⇒ "
                "本批统一 3 段，黑（辅助）合计 +80%/+100% 低于凯尔 +300%、罗尔夫 +200%"},
        {"patch_kinds": {"724": ["1399913#0（+35%）", "1399913#2（-50%）"],
                         "desc_override": sorted(k for k in strings
                                                 if k.startswith(L.PANEL_OVERRIDE_KEY_PREFIX))},
         "why": "724 是 APK 补丁 kind（官方全表零行，donor 取 live 1499893#1）且只许 ability 表；"
                "desc_override_* 需要 V14（panel-description-override-v2），缺补丁不崩、"
                "只是面板回落到客户端自动文案"},
    ])

    deviations = [
        {"want": "「自身处于连击效果期间」直接当词条门",
         "got": "新固有「豹步」（13999102，15 秒、上限 1）当门：技能发动即付与"
                "（1399912#2，IT 23 → IC 461），词条挂前置 187（1399912#1）",
         "why": "_deviations.json kuro 第 3 条已裁定：DT 185 ConditionComboBoost 与 IT 55 官方各 0 行，"
                "ACComboBoost 也没有时间维度。落成「技能发动即付与」而不是在 DSL 里塞 ACUnique —— "
                "IT 23 → IC 461 有现成官方 donor（1611231#0），少一处结构手术"},
        {"want": "随机池里的「Fever 槽 +50%」",
         "got": "「Fever 槽大幅上升」＝ DSL AddFeverPoint 250（官方最高档）",
         "why": "_deviations.json kuro 第 1 条：技能树只能加固定 Fever 点数，"
                "按槽上限比例加只有词条 724，而 724 进不了 DSL"},
        {"want": "「最多同时抽 6 个」互斥抽取",
         "got": "按骰运层数掷 max(1, 层数) 次，每次独立、可能重复",
         "why": "_deviations.json kuro 第 2 条：引擎没有互斥原语；面板原写「每次独立判定，可能抽到重复效果」，"
                "2026-09-27 第三轮 R2 抽取表并入能力1 强化条目，定性写「释放后随机抽取增益…抽取次数随「骰运」层数提升」"},
        {"want": "能力 3 ⑤的随机池受主位限制约束",
         "got": "开关是能力 1 的 536（非主位限制），随机池写在技能 DSL 的强化分支里",
         "why": "一个角色只能有一份 ChangeSkillFlag，「持续时间延长」与「随机池」共用同一个强化档。"
                "无实际差异：合击位角色不发动技能，随机池本来就不会跑"},
        {"want": "技能能量 550 只改一档",
         "got": "两档 c4/c5 都写 550（母本 490/490 与 490/440）",
         "why": "作者放行第 5 条逐字：「玛格诺斯 600、黑 550、夏琳 500——觉醒前后两档都写这个数」"},
        {"want": "面板按 wf_describe 自动渲染",
         "got": f"队长技 ＋ 6 个词条槽全部 desc_override（{1 + 6} 个键），逐行 = rework1/panel/kuro.json",
         "why": "自动文案会写成「持续·Fever → 赋予全队(雷) Direct伤害 400%」这类引擎术语，"
                "与作者已过目的面板逐行对不上。代价＝required_capabilities 多一项 "
                f"{L.PANEL_OVERRIDE_V2}（惰性，缺补丁不崩）"},
        {"want": "技能说明只保留原来两段（panel note 把「不再进入硬直」当备注）",
         "got": "action_skill c1 两档追加第三段「／释放技能后不再进入硬直，可立即行动」",
         "why": "panel/kuro.json 的 skill.lines[1] 标的是 status:\"changed\"，作者看过预览页后回「开做」"
                "⇒ 面板要逐行对齐就必须写进技能说明（技能说明是单串，只能追加段落）"},
        {"want": "队长技按本轮重写",
         "got": "4 行一格不动（2026-09-27 平衡第二批另追加 L5：能力3 进 Fever 直击的无上限部分）",
         "why": "panel/kuro.json 四行全是 status:\"same\"；作者本轮原话没提黑的队长技；"
                "L4 的前置 1 已经是 kind 2 阈值 6 ＝官方共鸣写法，符合 09-21 补充①"},
    ]

    # ---- 10) 放行闸：kit 自有产物（21 行 / 2 个固有 / 2 张图标 / 8 个面板串 / 2 棵 DSL /
    #          语音路由）全部就绪后，只等像素代理的小人件。
    gate = {"rows": len(evidence), "programs": len(programs),
            "unique_conditions": sorted(unique_entries),
            "unique_icons": {k: v["source"] for k, v in icon_notes.items()},
            "custom_ability_string": sorted(strings),
            "pixel_present": pixel["present"],
            "pixel_missing": [entry["logical"] for entry in pixel["skipped"]]}
    ready = bool(pixel["present"]) and not pixel["skipped"]
    gate["reason"] = "kit 自有产物全部过闸" if ready else (
        f"像素成品未就绪：{gate['pixel_missing'] or 'B/pixel/kuro/install.json 不存在'}"
        "（行/固有/图标/面板串/DSL/语音路由已全部就绪，像素件一落地重跑 kit 即 ready-for-review）")
    notes.append({"gate": gate})

    return KL.report(
        ctx,
        summary="黑（139991）：雷 · 拳 · 直击辅助 rework1——雷共鸣开强化档（摇碗更久、威力随连击成长），"
                "骰运层数决定技能后掷几次轮盘；Fever 收支三条（+35% / −50% / 进入 Fever 全队直击 +40%×3）",
        status=KL.READY if ready else KL.DRAFT,
        panel=panel,
        notes=notes,
        programs=programs,
        unique_condition={key: icon_notes[key] for key in unique_entries},
        required_capabilities=sorted(capabilities | set(SPEC["required_capabilities"])),
        deviations=deviations,
        extra={"statue_group": STATUE_GROUPS,
               "guards": guards,
               "gate": gate,
               "custom_ability_string": sorted(strings),
               "skills": {"programs": programs,
                          "energy": {lv: list(v) for lv, v in SKILL_ENERGY.items()},
                          "multiplier": {lv: SKILL_MULTIPLIER[lv][1] for lv in SKILL_MULTIPLIER},
                          "hit_area_buff_target_as": HITAREA_BUFF_TARGET_AS,
                          "enhanced": {"hit_area_lifetime": HITAREA_LIFETIME[1],
                                       "max_hits": HITAREA_MAX_HITS[1],
                                       "enables_combo_bonus": True},
                          "roulette": {"wheels": ROULETTE_SLOTS, "unique": UID_DICE},
                          "team_conditions": ["ACDirectDamage", "ACAdditionalDirectAttack"]}},
    )

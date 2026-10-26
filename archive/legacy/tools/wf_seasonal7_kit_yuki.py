# -*- coding: utf-8 -*-
"""季节换装七角色 · 见岛勇希·泳装 129991 ``psychic_yuki_swim`` 套件（kit）。

按定稿设计 ``work/character_packs/seasonal7-20260916/design/yuki.json``（status=final）
+ 作者 20260916 两轮改版方案落地（现行锁：``…/revision2-20260916/yuki/plan.json``；
首轮 ``…/revision-20260916/yuki/plan.json`` 只留作历史证据）：

- 队长 7 行 + 词条 6 键 15 条：donor 行 + 声明列编辑重建，逐行 sha256 锁定到改版成品行
  （live donor 漂移时回落改版方案成品行并记 note；两者都对不上直接报错）。
  donor 全部在角色自身键之外，发布前后重跑得到同一批行；
- ``custom_ability_string`` 新键 ``change_skill_psychic_yuki_swim``（536 ChangeSkillFlag 行 c70 引用，
  缺键 = C8601）。power_up 表不写：同形在线先例 1299923 / 1699891 / 1499891 / 1499901 的 536 串都只在主表，
  客户端缺 power_up 键按等级 1 处理、等级≤1 不读 power_up 表（roster.md §1 读码依据，门禁复核）；
- character_text / TEXTS、character 行 c9–c16 语音路由（kind 3 ChangeSkillFlag）、三层镜像；
- action_skill 两档（名称/描述/图标/能量 c4–c6/程序 c7/自动施放 c8–c10）；
- 两棵技能 DSL：全部从官方基线按设计块拼装（不读设计 composed_tree 当输入，只拿来逐节点对照），
  再施加改版算子 ``apply_skill_edits``（一轮 R18/R19/R20/R21：结界弹 Formation Single→NWay(6, π/3)、
  MaxNumOfHits None→Some(1) 保住「合计 24/34 倍」口径、判定区范围扩大、
  「攻撃演出」搬进判定区块使 6 个方向都可见；二轮 R25「雪花偏离角色太多」：生成偏移 −50→0、
  逐段外扩速度 20/10/5→6/3/1（外扩 710px→202px）、判定区长度 160→400 折回覆盖面；
  三轮 R26「六个方向的结界能不能缓慢旋转并打出高额连击」：``apply_orbit_edits`` 新建旋转参照点
  （``CreateReferencePoint(-18, AB, tp/td=false, bind 14)`` + ``RotateHitArea(14, 0.03, None)``），
  6 个结界改用 ``Formation.Circle(6, 200)`` 挂上去、坐标系 CD + trackingPos ⇒ 整环公转；
  删掉与公转互斥的 MoveHitArea 链，命中节流改 ``CalculatedUsingMaxNumOfHits(24)`` + ``Some(20)`` + p24=1
  ⇒ 每敌 20 次命中（连击 2→21），每击倍率/削韧/Fever 同步 ÷20 ⇒ **面板合计三项与线上逐值相同**）；
- 两个特效族克隆（sibling 形态 ``skill_unique/psychic_yuki_swim_{wave,barrier}/``）+ 引用改写；
  若 ``seasonal7-20260916/fx/yuki/out/manifest.json`` 存在，按其 {源逻辑路径 → 染色 PNG} 替换 sheet，
  否则用本模块的保守回退染色（保留 alpha 与尺寸）；
- ``switched_action_skill`` ``psychic_yuki_swim_voice_ready`` 两档 = action_skill c7–c23
  （与 ``wf_seasonal7_voice.switched_rows`` 列约定一致）；
- 离线静态门禁（行合法性 / DSL 签名差分 / 作用域 / 元素码 / 方向 / 判定区目标 / DoNothing /
  AMF3 往返 / 特效引用解析 / wf_describe 渲染 / capability 一致 / 包内 PNG 存储魔数），结果写
  ``evidence/kit-gates.json``；全部通过才报 ``ready-for-review``。

Integrate 辅助（build 不调用）：``install_pixel_sheets(ctx)`` 把 ``pixel/yuki/out`` 两张标准魔数 PNG
转成 WF 存储魔数（小写 ``\\x89png``）后装包并登记 owner=pixel。

一轮新增/改写的词条见 ``revision-20260916/yuki/requirements.md`` R1–R23（技能说明按 R22 压缩）；
二轮（``revision2-20260916/yuki/``）只动三处：R24 能力 6 的 PF Lv3 屏障加 CT 20 秒（c35=1200）、
R25 结界弹外扩距离收回、文案按《文案规则-补充.md》两条规则重写（536 串去数字与秒数）。
三轮（``revision3-20260916/yuki/orbit-plan.json``，实现复核 ``verify.md``）只动结界那一条判定区
与技能说明首句，词条/队长/语音/美术/特效素材一格未动。
四轮（``revision4-20260917/yuki/fx-timing.md``，作者真机：「中间的圈比周围旋转的提前消失、
周围旋转的延展到最长时突然消失或缩短重新延长」）只动**观感与寿命**：
给 ``psychic_yuki_ny23_attack`` 的 timeline 补 start/loop/end、给中心圈 ``psychic_yuki_ny23_player``
的 parts 补 alpha 渐隐尾 + timeline 补 end（``repair_fx_lifecycle``），
DSL 侧把「攻撃演出」改回单发 ``UntilTargetTerminates``、三个中心特效寿命 102→132
（``apply_fx_lifecycle_edits``）。伤害/段数/连击/倍率/环寿命/节流/上限一格未动。
没有 PF 覆盖（722）、没有 422/724、没有 desc_override、没有 unique_condition（设计 §0/§3，改版未引入）。
只写 ``work/character_packs/s7-yuki/``；不发布、不写 live store / assets / .cdn / src。
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import wf_assets
import wf_mod_tool as core

KEY = "yuki"
CID = "129991"
CODE = "psychic_yuki_swim"
TEMPLATE_CODE = "psychic_yuki_ny23"
ELEMENT = 1                                   # 内部 0 基：水
BATCH = "work/character_packs/seasonal7-20260916"
DESIGN_REL = f"{BATCH}/design/yuki.json"
REVISION1_REL = f"{BATCH}/revision-20260916/yuki/plan.json"   # 作者 20260916 首轮改版方案（历史证据）
REVISION_REL = f"{BATCH}/revision2-20260916/yuki/plan.json"   # 作者 20260916 二轮改版方案（锁定成品行 + 536 串文案）
# 三轮 R26：技能说明首句随「旋转结界」改动同步更新，只覆盖 action_skill c1 / character_text c5,c7
# 这三格；成品行与 536 串仍锁在二轮 plan.json（改一份文案不该让 22 条行锁失效）。
REVISION3_REL = f"{BATCH}/revision3-20260916/yuki/text.json"
# 五轮 R28/R29/R30：三条行的口径修正。plan.json 是二轮的外部方案、不改，
# 被覆盖的三个 row_sha256 记在这份行锁里（只记被覆盖的，其余 19 条仍以 plan.json 为准）。
REVISION5_REL = f"{BATCH}/revision5-20260917/yuki/rows.json"
FX_MANIFEST_REL = f"{BATCH}/fx/{KEY}/out/manifest.json"

AB = "master/ability/ability.orderedmap"
LD = "master/ability/leader_ability.orderedmap"
CHAR = "master/character/character.orderedmap"
TEXT = "master/character/character_text.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
ACTION = core.ACTION_SKILL_LOGICAL
SWITCHED = core.SWITCHED_ACTION_SKILL_LOGICAL
VOICE_READY_KEY = f"{CODE}_voice_ready"
CHANGE_SKILL_KEY = f"change_skill_{CODE}"
RARE5 = "battle/action/skill/action/rare5"

SKILL_NAME_1 = "浪花雪晶·多重结界"
SKILL_NAME_2 = "浪花雪晶·多重结界＋"
# 改版 R22「技能描述不再写太复杂省略一下」：~120 字压到 78 字，去掉共鸣强化整句（由能力 1 的 536 串承担）。
# 不写「向自身周围」：判定区锚在停球点的参照点（结界本体，DSL 主体 -18=球），不是角色立绘位置。
#
# 改版 R26（三轮）：结界由「向 6 个方向直线飞出」改成「6 个结界绕锚点缓慢公转」，说明同步改成
# 「展开6个旋转结界」——**比改前还短 1 个字**（77 → 76），且逐句与实机一致：
#   6 个（Formation.Circle 第 2 参）/ 旋转（RotateHitArea 0.03 rad/帧，一圈 3.5 秒）/
#   纵向冲击（第二块判定区，本轮未动）/ 合计 24(34) 倍（每击 ÷20 × 实得 20 次 + 冲击，与线上逐值相同）/
#   提升连击数（AddCombo 8(12→15) + 每次命中 +1，本轮从每敌 2 涨到 21）。
# 不写「每次命中 0.6 倍、最多 20 次」：官方多段技一律只写合计（tsundere_bountyhunter_vt22 / gold_ship 同形），
# 写了反而与全服口径不一致；20 次是内部节流值，不是玩家要背的数字。
# 也不写转速/秒数：运动方式是观感不是数值，官方同类环形技（wind_dragon）与扫描技（super_robot）都不写。
_DESC = ("展开6个旋转结界并追加纵向冲击，造成合计{mult}倍水属性伤害【连击数越高威力越高】"
         "／提升连击数／赋予队伍技能伤害提升"
         "／赋予水属性角色及协力球屏障与全属性抗性")
SKILL_DESC_1 = _DESC.format(mult=24)
SKILL_DESC_2 = _DESC.format(mult=34)

TEXTS = {
    "name": "见岛勇希",
    "furigana": "JIANDAOYONGXI",
    "title": "碧海雪华",
    "profile": ("为了暑假的海滩之行，见岛勇希换上蓝白泳装，披着白色防晒外套。她用结界把拍岸的浪花凝成细碎雪晶，"
                "替大家挡开烈日与暑气。本想坐在礁石边安静看书、摆出很酷的样子，却总被突然涌来的海浪弄得手忙脚乱。"),
    "leader": "我们的夏日结界",
    "skill1": SKILL_NAME_1, "desc1": SKILL_DESC_1,
    "skill2": SKILL_NAME_2, "desc2": SKILL_DESC_2,
    "cv": "AI 合成配音",
}

SPEC = {
    "extra_keys": {
        CAS: (CHANGE_SKILL_KEY,),
        SWITCHED: (VOICE_READY_KEY,),
    },
}

# 二轮文案规则 2（``revision2-20260916/文案规则-补充.md``）：「技能强化」条目只写强化了什么，不写数字与秒数。
# 官方同形先例：change_skill_tsundere_bountyhunter_vt22「为『白葡萄甘纳许』追加「赋予自身连击效果」」。
CHANGE_SKILL_TEXT = f"为『{SKILL_NAME_1}』追加「赋予队伍连击加成效果」"
# 1.4.874 上线时写进 live 的旧文本：占用判定要认它是「本角色自己的键」，而不是别人占用
CHANGE_SKILL_TEXT_PUBLISHED = ("强化技能：追加赋予队伍连击加成效果（之后3次弹射，每次弹射连击数+5）",)

# ---------------------------------------------------------------- 面板文案规则（作者 20260916 二轮补充）
CAP_WORDING_BANNED = ("无上限", "无限叠加", "可无限", "不封顶", "无次数限制")
SKILL_FLAG_KINDS = frozenset({"536", "704", "705", "706", "707", "708"})   # 规则 2 的适用 kind
# 本角色**全部**玩家可见文案（character_text c0/c2/c3/c4/c5/c6/c7/c10 与 action_skill c0/c1 同源；
# 无 desc_override、无 unique_condition，词条面板其余行由客户端按行数据自动生成）
PANEL_TEXTS = {
    "NAME": TEXTS["name"], "TITLE": TEXTS["title"], "PROFILE": TEXTS["profile"],
    "LEADER_NAME": TEXTS["leader"], "SKILL_NAME_1": SKILL_NAME_1, "SKILL_NAME_2": SKILL_NAME_2,
    "SKILL_DESC_1": SKILL_DESC_1, "SKILL_DESC_2": SKILL_DESC_2, "CAS_TEXT": CHANGE_SKILL_TEXT,
}
# 规则 2 适用的条目（本角色唯一的 ChangeSkillFlag 536 串）
SKILL_FLAG_TEXT_NAMES = ("CAS_TEXT",)
# character c9–c16：kind 3 ChangeSkillFlag（wf_seasonal7_voice.normalize_route 的规范形）
VOICE_ROUTE = ["3", "", "", "", "", VOICE_READY_KEY, "false", "false"]
ENERGY = {"1": ("550", "550", "1"), "2": ("550", "500", "1")}
SKILL_ICON = "dynamic/skill/atk_nearest"
AUTO_CAST = ("1", "0", "650")                 # c8–c10：新春版原值

# ---------------------------------------------------------------- 行配方（donor + 声明列编辑 + 成品行 sha256 锁）
# (来源 store|official, donor 键, donor 行号, {列: 新值}, 成品行 CSV sha256)
LEADER_RECIPE = (
    ('store', '129992', 2, {0: CODE, 49: '200000', 50: '200000'},
     'de099f1723e3cd0b70ea430f97e1945224ad2c94a8488b43db21a75f7a0c71b7'),  # L0 水共鸣 全队水攻击 200%
    ('store', '129992', 3, {0: CODE},
     '8edf4b09e2f7ba7ccd22383ef19bdb7d21bd9f88d2574c21c034594e93c31c9b'),  # L1 水共鸣 全队水技伤 300%
    ('store', '129992', 1, {0: CODE, 28: '15000000', 29: '15000000', 32: '5', 46: '5', 47: 'Blue'},
     '9ecd109696868668a791c10e633c7dd1827dafb22bfaf7741aeb2bd9d45af885'),  # L2 R2 每150连击(限5次) 全队水技伤 100%
    # 五轮 R28（作者 2026-09-17「队长技自身拥有护盾期间应该是水属性角色攻击力+500%」）：
    # during_content c107 从 2 SkillDamage 改成 0 AttackPoint；72 屏障触发 / target 5 / 组 Blue / 强度都不动。
    ('store', '129970', 7, {0: CODE, 107: '0', 111: '500000', 112: '500000'},
     'd03445e084daf9a6a6dbaf42fb9ada38761a5fce3d17fc6a3a35cb4cb6ad775a'),  # L3 R3/R28 自身屏障中 全队水攻击 500%
    ('official', '121117', 2, {0: CODE, 4: '2', 7: '600000', 8: '600000', 9: 'Blue', 26: '0', 27: '',
                               49: '15000000', 50: '15000000'},
     '9dc7c53103513d07a39bb22237595546c00d4c2352533b7ffd14c50ae79ba588'),  # L4 R4 水共鸣 自身施技 连击加成150×2弹射
    ('store', '129992', 8, {0: CODE},
     '386a986b9fc1f7a6c0d0857fd55812cef854f31731a95e172f87121ad16e539f'),  # L5 自身施技 除自身水技能槽 10%
    ('store', '129992', 8, {0: CODE, 45: '226', 46: '', 47: '', 49: '1000000', 50: '1000000'},
     'bf109ef741f145770d8e54f9c9a9cafe04f23703bf3e9ffee9a7c9b1d4396d85'),  # L6 R6 自身施技 连击+10（本轮新增）
)
ABILITY_RECIPE = {
    1: (
        ('store', '1299921', 1, {0: f'{CODE}_1', 2: 'action_skill', 51: '50000', 52: '50000'},
         'be4d6f0cb0bea6273b00c968aa284c44f56faec717ca72f8434f47c1c6112bfb'),  # R7 战斗开始 自身技能槽 50%
        ('store', '1299923', 0, {0: f'{CODE}_1', 1: 'true', 2: 'action_skill', 6: '202', 9: '', 10: '', 11: '',
                                 13: '2', 16: '600000', 17: '600000', 18: 'Blue', 70: CHANGE_SKILL_KEY},
         '28ec9293187a1996e9cf7219a85e7c525accecf0ced12292c9c61212dc705d9c'),  # R1/R8 Ⓜ主位+水共鸣 强化技能（从槽3搬来）
        # 五轮 R31（作者 2026-09-17：「和达到多少连击赋予攻击力技能槽那些差不多，达到多少连击加连击」）：
        # 阈值型触发只能落在词条行上——技能 DSL 侧的 ACComboBoost 既没有时间维度
        # （resolveTime case 32 恒返回永续），也只按弹射次数结算，做不出「每达成 N 连击」。
        # instant_trigger 12 Combo 的判据是 ThresholdComboListener：floor(prev/N) < floor(now/N) 时
        # **每跨过一个整数倍就触发一次**（跨多个就循环触发多次）⇒ 字面就是「每达成 75 连击」。
        # 加的连击自身只贡献 15/75 = 20% 的额外进度，收敛，不会自激。
        # 数值按本角色同族口径：能力2 是「每 75 连击 → 全队水技能槽 5%」，这里取同一个 75。
        # 官方先例 instant 12 + content 226 共 5 行（2410015#1 / 2410045#1 / 2430015#1 /
        # 3410013#1 觉醒 / 1599973#5 泽赫尔）；226 全表 74 行 target 列留空、3 行写 0 ——
        # 连击是全局计数器，没有「给谁」之分，所以不写 target/组。
        ('official', '2410015', 1, {0: f'{CODE}_1', 1: 'true', 2: 'action_skill', 6: '2', 9: '600000',
                                    10: '600000', 11: 'Blue', 30: '7500000', 31: '7500000',
                                    34: '(None)', 51: '1500000', 52: '1500000'},
         'd6e077ad27601164eab687f257c847c42104a05f32b141414fbc325805a449aa'),  # R31 水共鸣 每75连击 连击+15
    ),
    2: (
        ('store', '1299922', 2, {0: f'{CODE}_2', 6: '2', 9: '600000', 10: '600000', 11: 'Blue',
                                 51: '1000000', 52: '1000000'},
         'e792173fd6f4678230d088e4511ec6a1b249e6985b72e8c3d53418180474eb40'),  # R10 水共鸣 水属性施技 连击+10
        ('official', '2410016', 0, {0: f'{CODE}_2', 2: 'action_skill', 6: '2', 9: '600000', 10: '600000',
                                    11: 'Blue', 30: '7500000', 31: '7500000', 34: '(None)', 47: '211',
                                    49: 'Blue', 51: '5000', 52: '5000'},   # 五轮 R29：3% → 5%
         '615fb88637dba7f305e624537df0a5ca66f99e2c01616f3ba7ffce71cf42eff0'),  # R11/R29 水共鸣 每75连击(c34 触发次数上限=(None)) 全队水技能槽 5%
    ),
    # 槽 3 整键 c1 保持 live 的 'false'（官方槽3=主位身份槽惯例；把 536 搬去槽 1 并不强制翻转本槽 unisonable）。
    # c1=false 已经是「仅主位」，所以 R12 不再写 202 前置——同键双写会画双 Ⓜ（wf-unison-slot-mechanics）。
    3: (
        ('store', '2610893', 3, {0: f'{CODE}_3', 1: 'false', 6: '2', 9: '600000', 10: '600000', 11: 'Blue',
                                 47: '223', 49: 'Blue', 51: '100000', 52: '100000',
                                 57: '90000000', 58: '90000000'},
         'baad84dab1fb967f80d95424931101a09bc850395973ba8936daa9a75c6f9e5b'),  # R12 水共鸣 施技 全队水 直击2段(15秒)
        # 五轮 R30（作者 2026-09-17「能力3 的共鸣时每当直击应该是水属性角色合计直击50次不是只有自身」）：
        # 触发 puller c28 从 0 Myself 改回 donor 自己的 7 TotalOfParty + c29=Blue ⇒ 真按「水属性角色合计」数。
        # 这条改前是**面板说谎**：wf_describe 对 trigger 20 一律渲染「编成直接攻击」，与 puller 无关，
        # 所以面板写着「编成」而机制只数自身。官方 trigger20 + puller7 共 17 行，donor 1510573#1 本身就是这形状
        # （parseAt28 case "7" = TotalOfParty{character_groups: c29}）。
        ('official', '1510573', 1, {0: f'{CODE}_3', 1: 'false', 2: 'special', 6: '2', 9: '600000', 10: '600000',
                                    11: 'Blue', 28: '7', 29: 'Blue', 30: '5000000', 31: '5000000', 34: '(None)',
                                    35: '0', 47: '226', 48: '', 49: '', 51: '5000000', 52: '5000000'},
         'b0d6f6df9b406724b6e4232dec61dddbb36a8b8102b92fd7ef75e657d172fc0d'),  # R13/R30 水共鸣 水属性合计直击每50次 连击+50
        ('store', '2610896', 0, {0: f'{CODE}_3', 1: 'false', 11: 'Blue', 49: 'Blue', 51: '15000', 52: '15000'},
         'c24e1f894c607ec16d865516efd98487ae34f1be7b4d8024d9524e538549c37f'),  # R14 水共鸣 全队水 694 独立乘区 15%
        ('official', '1211893', 0, {0: f'{CODE}_3', 1: 'false', 2: 'special', 6: '2', 9: '600000', 10: '600000',
                                    11: 'Blue', 113: '3000', 114: '3000'},
         '8d7b62b4b5b42c09e6fbc96c1d9c9dda69b21ba185fd4c46806d0c26ed455169'),  # R15 水共鸣 队伍总HP每1% 全队水攻击 3%
        ('official', '1211893', 1, {0: f'{CODE}_3', 1: 'false', 2: 'special', 6: '2', 9: '600000', 10: '600000',
                                    11: 'Blue', 113: '3000', 114: '3000'},
         'dcea7cd2d539e162845e33df52f19e247f23acbfb6532bcb7539b95ace5d7de8'),  # R16 水共鸣 队伍总HP每1% 全队水技伤 3%
    ),
    4: (
        ('store', '1399951', 1, {0: f'{CODE}_4', 2: 'attack_blue', 6: '2', 9: '600000', 10: '600000',
                                 11: 'Blue', 51: '300000'},
         'c5eca3ab1283aded2d05b7e666f1313a6d2ce0232d81d04b165f9fb220808a0f'),  # R17 水共鸣 冲刺 连击 +3→5
        ('store', '1299926', 1, {0: f'{CODE}_4', 2: 'attack_blue', 6: '2', 9: '600000', 10: '600000', 11: 'Blue'},
         'de98e6dc15001d340661d34c457c83ebdd24ae35b1e8c0a4f95ee2968edf81f0'),  # R17 水共鸣 全队水技能槽充能 10→20%
    ),
    5: (
        ('store', '1199896', 0, {0: f'{CODE}_5', 2: 'attack_blue', 6: '2', 9: '600000', 10: '600000',
                                 11: 'Blue', 29: 'Blue', 47: '34', 49: 'Blue'},
         '369c9fa8b532ae4d1f2448c6126cfe4088715c53c5c916d0d6fbc4b9d51d8a5f'),  # R17 水共鸣 水属性施技(限10) 全队水技伤 10%
        ('store', '1199896', 1, {0: f'{CODE}_5', 2: 'attack_blue', 6: '2', 9: '600000', 10: '600000',
                                 11: 'Blue', 13: '0', 29: 'Blue', 49: 'Blue'},
         '919d9585b9a7a8fada20c17c2968a2fba3cd72302c02d1047d47829a5f1db119'),  # R17 同触发 全队水攻击 10%
    ),
    6: (
        # 二轮 R24（作者「能力6赋予的护盾ct20s」）：c35 冷却 0 → 1200 帧（instant_trigger@27 + 块内偏移 8，单位=原始帧，60帧/秒）
        ('store', '1499882', 0, {0: f'{CODE}_6', 2: 'defense_blue', 6: '2', 9: '600000', 10: '600000',
                                 11: 'Blue', 35: '1200', 51: '5000'},
         'b03ebc2d9ff389a508d324be2f4e0bc9e444a31264f3ddd812cc7e63904abef7'),  # R17/R24 水共鸣 PF Lv3(CT20秒) 全队屏障 5→10%
        ('store', '1299921', 0, {0: f'{CODE}_6', 2: 'defense_blue', 6: '2', 9: '600000', 10: '600000',
                                 11: 'Blue', 51: '50000', 52: '100000'},
         '53ae436c102653fd56b7e11d039b40ad98e1b097219c347357a3db5f53be0ec3'),  # R17 水共鸣 全队水攻击 50→100%
    ),
}

# ---------------------------------------------------------------- 技能树计划（设计 §4.2）
FX_WAVE = dict(src_dir="battle/effect/skill_unique/psychic_yuki_ny23", subdir="wave",
               fx_names=["psychic_yuki_ny23_attack", "psychic_yuki_ny23_hit", "psychic_yuki_ny23_player",
                         "psychic_yuki_ny23_character_back", "psychic_yuki_ny23_character_front"])
FX_BARRIER = dict(src_dir="battle/effect/skill_unique/psychic_yuki", subdir="barrier",
                  fx_names=["psychic_yuki_all", "psychic_yuki_barrier"])
PLAN = {
    "1": dict(cna=(12, 12), addcombo=(8, 8), d_sd_time=(720, 720), d_sd_value=(0.3, 0.3)),
    "2": dict(cna=(15, 17), addcombo=(12, 15), d_sd_time=(900, 900), d_sd_value=(0.3, 0.5)),
}
COMBOBOOST = dict(flips=3, combo=5)
EXPECTED_MULT = {"1": (24, 24), "2": (30, 34)}

# 改版 R18/R19/R20/R21（revision-20260916/yuki/plan.json §skills）：结界弹改成朝结界本体周围 6 个方向、
# 范围扩大、「攻撃演出」搬进判定区块 ⇒ 6 个方向各自可见。formation 取官方 paralysis_hedgehog_1/2 逐字同值。
#
# ⚠ R21 引擎口径（20260916 复审纠正，旧结论「NWay 共用 group 级 MaxNumOfHits 预算」是误读）：
#   p14 ``CalculatedUsingMaxNumOfHits 1`` 只把 minHitInterval 折成 Option.None，而 minHitInterval 的计数键
#   ``gidForMinHitInterval`` 由 p25 决定（ActionHitArea.as:176-257：p25=0 ⇒ Address.ActionHitArea = **每个子区一份**，
#   p25=1 才是 group 级）；真正的 group 级封顶在 ActionHitAreaGroup.as:704-712，但
#   ``switch(maxNumOfHits.index) case 0`` 只有 p15=Some(N) 才走，p15=["None"] 直接落 default 什么都不做。
#   ⇒ NWay(6) + p15=None + p25=0 = 同一敌人被 6 个子区各打一次（官方散射技 arisa / crybaby_shooter / bee_girl 就是这一形）。
#   本角色面板写「合计24(34)倍」，必须把每个敌人的整组命中封到 1 次：p15 = Some(1)。
#   官方逐字先例：ice_dragon_1/2、doctor_pirate_1/2（NWay + p14=CalculatedUsingMaxNumOfHits 1 + p15=Some(1) + p25=0）；
#   NWay(6, π/3) 的母本 paralysis_hedgehog_1/2 同样靠 p15=Some(3) 封顶，而不是靠 NWay 自己不叠。
#
# 二轮（作者 20260916 晚「雪花偏离角色太多」）：外扩距离收回来，改法与量见
# ``revision2-20260916/yuki/offsets.md``。引擎口径（``ActionHitArea.as``）：
#   - NWay 的 6 个子区**起点相同**（``ActionHitAreaGroup.as`` case 6：u/v 都取 p3/p4，只有方向 w 各差 π/3），
#     所以「离角色多远」完全由 ``MoveHitArea`` 的逐段速度累积决定；
#   - ``move()`` 每帧 ``offsetX += vx``，``applyMovement`` 里 vx = 速度 × cos(getDirCD()+w−π/2)
#     ⇒ ``MoveHitArea`` 第 4 参是**每帧像素速度**，段距 = 速度 × 该段 Wait 帧数。
# 母本（ny23 单发直线弹）三段 20/10/5 × 20/20/22 帧 = 外扩 710px；NWay(6) 之后就成了半径 710 的一圈，
# 在 1080×1920 战场上离结界本体（= 演出里的角色）超过半个屏宽 —— 这正是作者看到的「雪花一圈、离本体太远」。
# 收法：三段速度 6/3/1 ⇒ 外扩 202px；生成偏移 −50 回正到 0（让环心正落在结界本体上）；
# 判定区长度 160→400 把缩掉的行程折回覆盖面，避免把一轮的「范围扩大」抵消成纯削弱
# （宽度 320 与寿命 102 帧都不动）。有效半径 790→402px，可见环半径 710→202px。
SKILL_FORMATION = ["NWay", 6, 1.0471975511965976]                                   # 6 方向 × 60°
SKILL_MAXHITS_BARRIER = ["Some", [{"min": 1, "max": 1}]]                            # 每个敌人整组只吃 1 次
SKILL_SHAPE_BARRIER = ["Rectangle", [{"min": 320, "max": 320}], [{"min": 400, "max": 400}]]   # 结界弹 200×100 →
SKILL_SHAPE_COLUMN = ["Rectangle", [{"min": 320, "max": 320}], [{"min": 800, "max": 800}]]    # 纵向冲击 200×800 →
SKILL_SPAWN_OFFSET_Y = 0                       # CreateHitArea p4：−50 → 0（环心落在结界本体上）
SKILL_MOVE_SPEEDS = (6, 3, 1, 0)               # MoveHitArea p3 逐段每帧速度（配 Wait 20/20/22 = 外扩 202px）
SKILL_MOVE_WAITS = (20, 20, 22)                # 三段持续帧数（母本原值，本轮不动；只用于算外扩距离）
PANE_EFFECT_SCALE = 1.4                                                             # 每方向特效缩放（原参照点块 2）
SKILL_EDIT_BEFORE = {"show_effect_subject": 1, "formation": ["Single"], "maxhits_barrier": ["None"],
                     "shape_barrier": ["Rectangle", [{"min": 200, "max": 200}], [{"min": 100, "max": 100}]],
                     "shape_column": ["Rectangle", [{"min": 200, "max": 200}], [{"min": 800, "max": 800}]],
                     "spawn_offset_y": -50, "move_speeds": (20, 10, 5, 0)}


def outward_reach(speeds=SKILL_MOVE_SPEEDS, waits=SKILL_MOVE_WAITS) -> int:
    """逐段速度 × 段帧数 = 结界弹中心的外扩距离（px）。母本 710、本轮 202。"""
    return sum(int(v) * int(w) for v, w in zip(speeds, waits))


# ---------------------------------------------------------------- 改版 R26（作者 20260916 三轮：缓慢旋转 + 高额连击）
#
# 作者原话「夏勇希的六个方向的结界能不能缓慢旋转并打出高额连击」。方案锁
# ``revision3-20260916/yuki/orbit-plan.json``，全部数字的复算入口 ``revision3-20260916/yuki/orbit_probe.py``
# （→ ``orbit-probe.json``，passed=true）；本轮实现与复核见 ``revision3-20260916/yuki/verify.md``。
#
# **正解不是「转判定区」而是「转锚点」**（引擎口径逐行核过反编译源）：
#   - ``RotateHitArea(subject, radPerFrame, tween)``（``ActionEvaluator`` case 26 → ``ActionHitArea.applyRotation``）
#     只写 subject 的角速度 ``vr``，每帧 ``move()`` 执行 ``r += vr``；``moveShape`` 用 r 旋转 pivot，
#     而 pivot 由形状 + HAlign/VAlign 推出 ⇒ **Center/Center 的判定区 pivot=0，转了不位移**。
#   - 公转的通道是子对象：``move()`` 里 ``trackingPos=true`` 每帧 ``stepPos()``，
#     ``x = u*cos(calcDir) - v*sin(calcDir) + target.getPosX()``；坐标系 ``CD`` ⇒ ``calcDir() = 锚点的 r``
#     ⇒ 锚点 r 在涨，(u,v) 就绕锚点公转，半径 = sqrt(u²+v²)。
#   - 参照点可以被旋转：``CreateReferencePoint`` 内部就是 ``ActionHitAreaGroup(Shape.Circle(10), Center, Center)``，
#     进 hitAreaManager 吃 movementPhase；``ActionHitArea.isActionRejected()`` 恒 false ⇒ 对它发 RotateHitArea
#     不会 C16103。
#   - ⚠ **被旋转的参照点 ``trackingDir`` 必须 false**：``move()`` 里 ``stepDir()`` 先把 r 重写成
#     ``dir.w + calcDir()``，再 ``r += vr`` ⇒ td=true 时旋转每帧被抹掉，**不崩不报错、只是环不转**
#     （orbit-plan §risks R2；``orbit_problems`` 带负控门禁）。
#   - ⚠ ``MoveHitArea`` 累加的是世界坐标 ``offsetX/offsetY``，``stepPos()`` 只重算 x 不重算 offset
#     ⇒ **径向外扩与公转互斥**：R25 的三段 MoveHitArea 链必须整条删除，半径改由 ``Formation.Circle`` 给
#     （留着会变成一边公转一边被恒定世界速度拖走的螺旋，飞出屏幕）。
#   - ``NWay`` 的 n 个子区 ``u/v`` 完全相同（``ActionHitAreaGroup`` case 6 偏移项恒 0，只有朝向 w 差）
#     ⇒ **NWay 根本给不出环**；R25 那一圈是 MoveHitArea 推出来的。官方的环一律 ``Formation.Circle``。
#
# 官方先例：``RotateHitArea`` 在 1091 棵玩家程序里只有 ``super_robot$1/$2``
# （0.09599310885968812 rad/帧 = 5.5°/帧、td=false、tween 100% ``["None"]``）；
# ``Formation.Circle`` 35 处，``wind_dragon$1/$2`` = ``["Circle", 6, 200]`` 逐字同值；
# 整组节流 p24=1 有 ``waste_armor`` / ``ice_dragon``（官方分布 {0: 1686, 1: 8}）。
# **「旋转的 Circle 环」是本项目首例：零件全部有先例，组合没有**（orbit-plan §risks R1，必须真机验一次）。
#
# 命中节流口径（``ActionHitAreaGroup.as:112-124 / :704-770``）：
#   ``CalculatedUsingMaxNumOfHits(N)`` 折成 间隔 = 寿命/(N−0.5) = 132/23.5 = 5.617 帧；
#   放行条件是 ``getOrDefault(key,0) < 1``、放行时置 ``余量 + 间隔``，管理器每帧 −1、<=0 才删键
#   ⇒ **小数余量进位累加**，真实节拍在 5/6 帧之间摆动、均值 5.617，132 帧内 **24 次机会**
#   （逐帧模拟 :func:`orbit_hit_schedule_exact`；保守的 ceil 模型给 22 次，是下界不是真值）。
#   计数键 ``gidForMinHitInterval`` 由 p24 决定（1 = 整组一份 ⇒ 6 个子区共用一条冷却，同帧最多 1 次）。
#   ``MaxNumOfHits Some(M)`` 恒按整组 GID + 目标累计 ⇒ 24（保守 22）次机会被 Some(20) 咬死
#   = **确定 20 次**（两个模型都 ≥ 20，结论不依赖哪个模型）。
# 伤害口径：结界弹每击的 倍率/削韧/Fever/**固定伤害 p5** 全部 ÷20，纵向冲击一格不动
#   ⇒ 面板合计倍率 24 /(30→34)、削韧合计 24、Fever 合计 12、固定项合计 200 与线上**完全相同**，涨的只有连击
#   （每敌每次施技 2 → 21）。官方多段技同样摊薄（tsundere_bountyhunter_vt22 / gold_ship / lady_android）。
ORBIT_SPIN_BIND = 14                    # 旋转参照点绑定 id（现行树用掉 0..13，14 空闲）
ORBIT_SPIN_LIFETIME = 138               # 旋转参照点寿命 = 环寿命 132 + 6 帧余量（子区 tp=true ⇒ 锚点先死子区跟着死）
ORBIT_OMEGA = 0.03                      # RotateHitArea p1：每帧弧度 = 1.719°/帧 = 一圈 3.49 秒（官方 super_robot 的 31%）
ORBIT_RING_LIFETIME = 132               # 结界环寿命（R26 当时取 3 × 44；R27 留着不动：它是命中次数的分母）
ORBIT_RING_RADIUS = 200                 # Formation.Circle p2 环半径（wind_dragon 逐字同值）
ORBIT_BARRIER_RADIUS = 220              # 单个结界判定圆半径（> 环半径 ⇒ 环心也被覆盖，boss 站环心不会漏）
ORBIT_RING_N = 6                        # 结界个数（作者要的「六个方向」原样保留）
ORBIT_THROTTLE_N = 24                   # p13 CalculatedUsingMaxNumOfHits(N)：N∈23..26 都得 6 帧，取 24 离两端最远
ORBIT_HIT_CAP = 20                      # p14 MaxNumOfHits Some(M)：每个敌人整组硬上限
ORBIT_GID_GROUP = 1                     # p24：节流键从「每个子区一份」改成「整组一份」（同一帧最多跳 1 个伤害数字）
# ⚠ 下面两个常量是 **R26 的历史参数**，已被 R27 推翻（见本文件 R27 段）：
#   「第 44–100 帧面片数为 0」是误测，离线逐帧渲染实测第 1–141 帧每一帧都有图。
#   它们现在只用来（1）在 ``apply_fx_lifecycle_edits`` 里断言「改动前确实是 R26 那个形」、
#   （2）做负控（写回 44 帧必须被门禁判红）。**不要再拿它们当作素材事实引用。**
ORBIT_FX_WINDOW = 44                    # R26 的重发拍长（历史值）
ORBIT_FX_REISSUES = (0, 44, 88)         # R26 的重发时刻（历史值；正是它造成了作者说的「缩短重新延长」）
ORBIT_COORDSYS = ["CD"]                 # 子判定区坐标系：公转的唯一开关（写 AB 就是官方那种静止环）
ORBIT_FORMATION = ["Circle", ORBIT_RING_N, ORBIT_RING_RADIUS]
ORBIT_SHAPE_BARRIER = ["Circle", [{"min": ORBIT_BARRIER_RADIUS, "max": ORBIT_BARRIER_RADIUS}]]
ORBIT_RING_MULT = {"1": (0.6, 0.6), "2": (0.75, 0.85)}      # 每击倍率 = 线上总倍率 ÷ ORBIT_HIT_CAP
ORBIT_RING_TOUGH = (0.6, 0.6)                               # 每击削韧 = 12 ÷ 20
ORBIT_RING_FEVER = (0.3, 0.3)                               # 每击 Fever = 6 ÷ 20
# ⚠ 对抗审查 20260917 抓到的漏摊薄项：``CreateNormalAttack`` p5 **flatDamage**（母本/线上都是 100）
# 是**每次命中都加一遍的固定伤害项**（``NormalAttackCalculator`` 基础式 = 随机加数 + p5 + 攻击力×p6，
# ``FloatInt_Impl_`` 恒等映射 ⇒ 100 就是 100 点伤害）。只摊薄倍率/削韧/Fever 而把 p5 留在 100，
# 一次施技的固定项就从 100 变成 20×100 = 2000（低攻时相对涨幅可达 ~8%），
# 与「面板三项合计与线上逐值相同」的口径自相矛盾。官方多段技同样把 p5 摊到每击
# （cursed_girl N=16/cap12 p5=8、lady_android N=32/cap26 p5=6、rem N=8 p5=3），
# 所以这里按同一个 ÷20 规则写 5（100/20，整除；官方 p5=5 有 89 处先例）。
# 残留不可消项：随机加数 ``RANDOM_ADDEND = 3``（每击 0..2，20 击平均 +19 点），量级可忽略且引擎写死。
ORBIT_RING_FLAT = 5                                         # 每击固定伤害 = 100 ÷ 20
ORBIT_COLUMN_COMBO = 1                                      # 纵向冲击每敌 1 次命中（p14 = ["None"]、单块矩形）
ORBIT_EXPECTED_TOUGH_FEVER = (24.0, 12.0)                   # 线上合计削韧 / Fever（本轮必须一格不动）
ORBIT_EXPECTED_FLAT = 200                                   # 线上合计固定伤害（结界 100 + 纵向冲击 100）
# 改动前（= R25 施加完的形），任一格漂了就报错而不是硬改
ORBIT_EDIT_BEFORE = {"formation": SKILL_FORMATION, "shape": SKILL_SHAPE_BARRIER, "subject_is_crp_bind": True,
                     "lifetime": ["SpecifyHitAreaLifetimeDirectly", 102],
                     "min_hit_interval": ["CalculatedUsingMaxNumOfHits", 1],
                     "max_num_of_hits": SKILL_MAXHITS_BARRIER,
                     "gid_scope": 0, "tracking_pos": True, "tracking_dir": False,
                     "halign": ["Center"], "valign": ["Center"]}


def orbit_rotation(omega: float = ORBIT_OMEGA, lifetime: int = ORBIT_RING_LIFETIME) -> dict[str, float]:
    """角速度的人话换算（60 帧/秒）。"""
    import math
    return {"rad_per_frame": omega, "deg_per_frame": round(math.degrees(omega), 4),
            "frames_per_revolution": round(2 * math.pi / omega, 1),
            "seconds_per_revolution": round(2 * math.pi / omega / 60.0, 2),
            "degrees_over_lifetime": round(math.degrees(omega * lifetime), 1),
            "frames_per_symmetry_step": round(math.radians(360.0 / ORBIT_RING_N) / omega, 1)}


def orbit_hit_schedule(lifetime: int = ORBIT_RING_LIFETIME, throttle_n: int = ORBIT_THROTTLE_N,
                       cap: int = ORBIT_HIT_CAP) -> dict:
    """命中节拍的**保守模型**：间隔 = 寿命/(N−0.5)，节拍按 ``ceil(间隔)`` 取整。

    ⚠ 这是**机会数的下界**，不是引擎逐帧真值：``ActionHitAreaGroup.resolveCollision`` 放行条件是
    ``getOrDefault(key,0) < 1``（不是 ``<= 0``）且新值 ``= 余量 + 间隔`` —— 小数余量会进位累加，
    真实节拍在 5/6 帧之间摆动、均值 = 间隔。真值走 :func:`orbit_hit_schedule_exact`。
    这里保留 ceil 模型是因为它**只会低估机会数**，用它锁门禁不会把「其实打不满」说成「打得满」。
    """
    import math
    interval = lifetime / (throttle_n - 0.5)
    step = math.ceil(interval)
    frames = list(range(0, lifetime, step))
    return {"interval_float": round(interval, 4), "step_frames": step, "opportunities": len(frames),
            "realized": min(cap, len(frames)), "hit_frames": frames[:cap], "last_hit_frame": frames[:cap][-1],
            "hits_per_second": round(60.0 / step, 2), "model": "conservative-ceil"}


def orbit_hit_schedule_exact(lifetime: int = ORBIT_RING_LIFETIME, throttle_n: int = ORBIT_THROTTLE_N,
                             cap: int = ORBIT_HIT_CAP) -> dict:
    """逐帧模拟引擎的最小命中间隔状态机（``ActionHitAreaGroup.as:735-760`` + ``…MinHitIntervalManager.as:34-67``）。

    每帧两件事：碰撞判定 ``v < 1 ⇒ 放行并置 v = max(v,0) + 间隔``；``updatePhase`` 令 ``v -= 1``，
    ``<= 0`` 即从表里删掉（下次读回默认 0）。两件事在一帧内的先后顺序取决于战斗主循环，
    差异最多 1 次机会 ⇒ 这里两种顺序都跑，取**较少**的那个作为结论。
    """
    interval = lifetime / (throttle_n - 0.5)

    def sim(update_first: bool) -> list[int]:
        v, hits = 0.0, []
        for f in range(lifetime):
            if update_first:
                v = 0.0 if v - 1 <= 0 else v - 1
            if v < 1:
                hits.append(f)
                v = max(v, 0.0) + interval
            if not update_first:
                v = 0.0 if v - 1 <= 0 else v - 1
        return hits

    runs = {"update_first": sim(True), "collide_first": sim(False)}
    worst = min(runs.values(), key=len)
    steps = sorted({b - a for a, b in zip(worst, worst[1:])})
    return {"interval_float": round(interval, 4), "opportunities": len(worst),
            "realized": min(cap, len(worst)), "hit_frames": worst[:cap],
            "last_hit_frame": worst[:cap][-1], "step_frames_observed": steps,
            "opportunities_by_order": {k: len(v) for k, v in runs.items()}, "model": "exact-carry"}


def orbit_coverage(radius: int = ORBIT_RING_RADIUS, shape_r: int = ORBIT_BARRIER_RADIUS,
                   n: int = ORBIT_RING_N) -> dict:
    """环的几何：相邻中心距 / 保证覆盖半径 / 最远触及 / 环心是否被覆盖。"""
    import math
    half = math.pi / n
    inner = shape_r ** 2 - (radius * math.sin(half)) ** 2
    solid = radius * math.cos(half) + math.sqrt(inner) if inner > 0 else 0.0
    return {"ring_radius": radius, "barrier_radius": shape_r,
            "adjacent_centre_gap_px": round(2 * radius * math.sin(half), 1),
            "solid_cover_radius_px": round(solid, 1), "max_reach_px": radius + shape_r,
            "centre_covered": shape_r > radius}


def is_orbit_applied(tree) -> bool:
    """R26 是否已施加（树里有 RotateHitArea 即是）。"""
    return any(c[0] == "RotateHitArea" for c in walk_cmds(tree))


def skill_totals(tree, level: str) -> dict:
    """一次施技对**一个**敌人的合计：倍率 / 削韧 / Fever / 连击（面板口径的复算来源）。"""
    _near, _crp, _body, cha1, cha2 = locate_hit_areas(tree)
    ring = _find_root(cha1[23][1], "CreateNormalAttack")[1]
    column = _find_root(cha2[23][1], "CreateNormalAttack")[1]
    hits = orbit_hit_schedule(cha1[13][1], cha1[14][1], cha1[15][1][0]["min"]) if is_orbit_applied(tree) else None
    n = hits["realized"] if hits else 1
    out = {"ring_hits": n, "column_hits": ORBIT_COLUMN_COMBO,
           "ring_per_hit": {"mult": [ring[6][0]["min"], ring[6][0]["max"]],
                            "toughness": ring[13][0]["min"], "fever": ring[14][0]["min"],
                            "flat": ring[5]},
           "column_per_hit": {"mult": [column[6][0]["min"], column[6][0]["max"]],
                              "toughness": column[13][0]["min"], "fever": column[14][0]["min"],
                              "flat": column[5]},
           "mult": [round(n * ring[6][0]["min"] + column[6][0]["min"], 6),
                    round(n * ring[6][0]["max"] + column[6][0]["max"], 6)],
           "toughness": round(n * ring[13][0]["min"] + column[13][0]["min"], 6),
           "fever": round(n * ring[14][0]["min"] + column[14][0]["min"], 6),
           # p5 flatDamage 也是**逐次命中**加的固定项，摊薄口径必须与倍率/削韧/Fever 一致
           "flat": n * ring[5] + ORBIT_COLUMN_COMBO * column[5],
           "combo_per_enemy": n + ORBIT_COLUMN_COMBO,
           "expected_mult": list(EXPECTED_MULT[level])}
    return out


def locate_orbit(tree) -> dict:
    """定位 R26 的三个作用点：旋转参照点 / RotateHitArea / 结界环判定区（未施加时报错）。"""
    _near, crp, body, cha1, cha2 = locate_hit_areas(tree)
    spins = [n for n in body if cmd(n) and cmd(n)[0] == "CreateReferencePoint"]
    if len(spins) != 1:
        raise AssertionError(f"参照点块内旋转参照点数量 {len(spins)}（R26 未施加？）")
    spin = spins[0][1]
    rots = [n for n in spin[11][1] if cmd(n) and cmd(n)[0] == "RotateHitArea"]
    if len(rots) != 1:
        raise AssertionError(f"旋转参照点块内 RotateHitArea 数量 {len(rots)}")
    return {"crp": crp, "spin": spin, "rotate": rots[0][1], "ring": cha1, "column": cha2}


def apply_orbit_edits(tree, level: str):
    """就地施加 R26 算子（必须在 ``apply_skill_edits`` 之后跑），返回改动记录。

    把 R25 的「NWay 直线弹 + MoveHitArea 外扩」整条换成「旋转参照点 + Formation.Circle 环」：
    新建 ``CreateReferencePoint(-18, AB, 0/0/0, tp=false, td=false, Single, 138, bind 14)``，
    块首发 ``RotateHitArea(14, 0.03, None)``，6 个结界以 ``Circle(6, 200)`` 挂在它身上、坐标系 CD、
    ``trackingPos=true`` ⇒ 每帧按锚点的 r 重算位置 = 整环公转。

    R25 的几何算子仍然照跑（它断言的是**官方母本**没漂），本轮只是把它的产物整条替换掉。
    幂等保护：施加后参照点块里已没有 CreateHitArea（换成了 CreateReferencePoint），重复调用直接报错。
    """
    _near, crp, body, cha1, _cha2 = locate_hit_areas(tree)
    if is_orbit_applied(tree):
        raise AssertionError("树里已有 RotateHitArea（R26 改动已施加过？）")
    idx = [i for i, n in enumerate(body) if cmd(n) and cmd(n)[0] == "CreateHitArea"]
    if len(idx) != 1:
        raise AssertionError(f"参照点块内 CreateHitArea 数量 {len(idx)}（R26 已施加或母本漂移）")
    before = {"formation": cha1[12], "shape": cha1[9], "subject_is_crp_bind": cha1[2] == crp[10],
              "lifetime": cha1[13], "min_hit_interval": cha1[14], "max_num_of_hits": cha1[15],
              "gid_scope": cha1[25], "tracking_pos": cha1[7], "tracking_dir": cha1[8],
              "halign": cha1[10], "valign": cha1[11]}
    if before != ORBIT_EDIT_BEFORE:
        raise AssertionError(f"结界弹判定区改动前 {before!r} != 预期 {ORBIT_EDIT_BEFORE!r}（R25 产物漂移）")
    moves = [c for c in walk_cmds(cha1[20]) if c[0] == "MoveHitArea"]
    if tuple(c[4] for c in moves) != SKILL_MOVE_SPEEDS:      # 4 段速度 + 3 段 Wait（末段速度 0 = 停住）
        raise AssertionError(f"结界弹 MoveHitArea 逐段速度 {[c[4] for c in moves]} != {list(SKILL_MOVE_SPEEDS)}"
                             "（R25 产物漂移）")

    ops = [{"op": "derived", "node": "结界弹形态",
            "old": f"NWay({ORBIT_RING_N}) 直线弹 + MoveHitArea 外扩 {outward_reach()}px",
            "new": f"旋转参照点 + Formation.Circle({ORBIT_RING_N}, {ORBIT_RING_RADIUS}) 公转"}]
    cha = copy.deepcopy(cha1)
    cha[2] = ORBIT_SPIN_BIND                                    # p1 subject → 旋转参照点（lookup 位，必须跟着改）
    cha[3] = copy.deepcopy(ORBIT_COORDSYS)                      # p2 坐标系：CD 才让 calcDir() 读锚点的 r
    cha[4] = cha[5] = cha[6] = 0                                # p3/p4 生成偏移、p5 环的初相
    cha[7] = True                                               # p6 trackingPos：公转必须每帧 stepPos()
    cha[8] = True                                               # p7 trackingDir：结界随环转保持朝外（法阵观感）
    cha[9] = copy.deepcopy(ORBIT_SHAPE_BARRIER)                 # p8 形状：圆在旋转下各向同性
    cha[12] = copy.deepcopy(ORBIT_FORMATION)                    # p11 Formation
    cha[13] = ["SpecifyHitAreaLifetimeDirectly", ORBIT_RING_LIFETIME]      # p12 寿命
    cha[14] = ["CalculatedUsingMaxNumOfHits", ORBIT_THROTTLE_N]            # p13 节流
    cha[15] = ["Some", slv(ORBIT_HIT_CAP, ORBIT_HIT_CAP)]                  # p14 每敌整组硬上限
    cha[25] = ORBIT_GID_GROUP                                              # p24 节流作用域 → 整组
    for label, i in (("p1 subject", 2), ("p8 形状", 9), ("p11 Formation", 12), ("p12 寿命", 13),
                     ("p13 节流", 14), ("p14 命中上限", 15), ("p24 节流作用域", 25)):
        ops.append({"op": "set", "node": f"CreateHitArea#1(结界环).{label}",
                    "old": copy.deepcopy(cha1[i]), "new": copy.deepcopy(cha[i])})

    # onCreate：删掉 MoveHitArea 链（世界坐标位移与公转互斥），改成「攻撃演出」按可见窗口三次重发
    show = None
    for c in walk_cmds(cha[20]):
        if c[0] == "ShowEffect" and c[1] == "攻撃演出":
            show = copy.deepcopy(c)
            break
    if show is None:
        raise AssertionError("结界弹 onCreate 里没有「攻撃演出」ShowEffect（R18 算子没跑？）")
    if show[3] != cha[19]:
        raise AssertionError(f"「攻撃演出」p2 主体 {show[3]!r} != 判定区绑定 id {cha[19]!r}")
    show[5] = ["SpecifyEffectLifetimeDirectly", ORBIT_FX_WINDOW]           # p4 寿命：一拍一换，同族永不叠加
    block = ["Block", [["Command", copy.deepcopy(show)]]]
    tail = block[1]
    for _ in ORBIT_FX_REISSUES[1:]:
        inner = ["Block", [["Command", copy.deepcopy(show)]]]
        tail.append(["Event", ["Wait", ORBIT_FX_WINDOW, "*", inner]])
        tail = inner[1]
    ops.append({"op": "replace", "node": "CreateHitArea#1(结界环).p19 onCreate 块",
                "old": f"ShowEffect(UntilTargetTerminates) + MoveHitArea×{len(moves)}",
                "new": f"ShowEffect(SpecifyEffectLifetimeDirectly {ORBIT_FX_WINDOW}) ×{len(ORBIT_FX_REISSUES)} "
                       f"（t = {'/'.join(str(f) for f in ORBIT_FX_REISSUES)}）"})
    cha[20] = block

    # onHit：倍率 / 削韧 / Fever 按命中次数摊薄 ⇒ 面板三项合计与线上完全相同
    for c in walk_cmds(cha[23]):
        if c[0] != "CreateNormalAttack":
            continue
        old = {"mult": copy.deepcopy(c[6]), "toughness": copy.deepcopy(c[13]), "fever": copy.deepcopy(c[14]),
               "flat": c[5]}
        if c[5] % ORBIT_HIT_CAP:
            raise AssertionError(f"结界弹 flatDamage {c[5]} 不能被命中数 {ORBIT_HIT_CAP} 整除（摊薄会漂）")
        if c[5] // ORBIT_HIT_CAP != ORBIT_RING_FLAT:
            raise AssertionError(f"结界弹 flatDamage {c[5]}/{ORBIT_HIT_CAP} != {ORBIT_RING_FLAT}（母本漂移）")
        c[5] = ORBIT_RING_FLAT
        c[6] = slv(*ORBIT_RING_MULT[level])
        c[13] = slv(*ORBIT_RING_TOUGH)
        c[14] = slv(*ORBIT_RING_FEVER)
        ops.append({"op": "set",
                    "node": "CreateHitArea#1(结界环).p22 onHit CreateNormalAttack 固定伤害/倍率/削韧/Fever",
                    "old": old, "new": {"mult": copy.deepcopy(c[6]), "toughness": copy.deepcopy(c[13]),
                                        "fever": copy.deepcopy(c[14]), "flat": c[5]}})

    body[idx[0]] = ["Command", ["CreateReferencePoint", SKILL_ANCHOR_SUBJECT, ["AB"],
                                *SKILL_ANCHOR_OFFSET, False, False, ["Single"],
                                ORBIT_SPIN_LIFETIME, ORBIT_SPIN_BIND,
                                ["Block", [["Command", ["RotateHitArea", ORBIT_SPIN_BIND, ORBIT_OMEGA, ["None"]]],
                                           ["Command", cha]]]]]
    ops.append({"op": "insert", "node": "CreateReferencePoint(旋转参照点) + RotateHitArea",
                "old": None, "new": {"subject": SKILL_ANCHOR_SUBJECT, "coord": ["AB"],
                                     "tracking": [False, False], "lifetime": ORBIT_SPIN_LIFETIME,
                                     "bind": ORBIT_SPIN_BIND, "omega_rad_per_frame": ORBIT_OMEGA}})
    return ops


def orbit_problems(tree, level: str) -> list[str]:
    """R26 七条专用门禁（orbit-plan §gates_to_add）。官方母本树不适用，别放进 ``tree_gates``。"""
    probs: list[str] = []
    try:
        loc = locate_orbit(tree)
    except AssertionError as exc:
        return [f"orbit 结构定位失败：{exc}"]
    spin, rot, ring, column, crp = loc["spin"], loc["rotate"], loc["ring"], loc["column"], loc["crp"]

    # 1 旋转通路：全树恰好一条 RotateHitArea，点名旋转参照点；该参照点 tp/td 都必须 false
    rots = [c for c in walk_cmds(tree) if c[0] == "RotateHitArea"]
    if len(rots) != 1:
        probs.append(f"RotateHitArea 数量 {len(rots)} != 1")
    if rot[1] != spin[10]:
        probs.append(f"RotateHitArea subject {rot[1]!r} != 旋转参照点 bind {spin[10]!r}")
    if rot[2] != ORBIT_OMEGA:
        probs.append(f"角速度 {rot[2]!r} != {ORBIT_OMEGA}（「缓慢旋转」的锁定值）")
    if rot[3] != ["None"]:
        probs.append(f"RotateHitArea tween {rot[3]!r} != ['None']（官方 100% None）")
    if spin[6] is not False:
        probs.append(f"旋转参照点 trackingPos {spin[6]!r} != False（球恢复运动时会把整环带走）")
    if spin[7] is not False:
        probs.append(f"旋转参照点 trackingDir {spin[7]!r} != False：stepDir 每帧把 r 重写 ⇒ 旋转静默失效")
    if spin[1] != SKILL_ANCHOR_SUBJECT or (spin[3], spin[4], spin[5]) != SKILL_ANCHOR_OFFSET:
        probs.append(f"旋转参照点锚点 {spin[1]!r}{(spin[3], spin[4], spin[5])!r} != -18 球停点零偏移")
    if not isinstance(spin[9], int) or spin[9] < ORBIT_RING_LIFETIME:
        probs.append(f"旋转参照点寿命 {spin[9]!r} < 环寿命 {ORBIT_RING_LIFETIME}（子判定区会提前消失）")

    # 2 环几何：公转的三个开关 + 命中节流 + 覆盖面
    if ring[2] != spin[10]:
        probs.append(f"结界环 p1 subject {ring[2]!r} 没挂在旋转参照点 bind {spin[10]!r} 上 ⇒ 不会转")
    if ring[3] != ORBIT_COORDSYS:
        probs.append(f"结界环 p2 坐标系 {ring[3]!r} != {ORBIT_COORDSYS}（写 AB 就是官方那种静止环）")
    if ring[7] is not True:
        probs.append(f"结界环 p6 trackingPos {ring[7]!r} != True（不每帧 stepPos 就只摆位一次）")
    if ring[12] != ORBIT_FORMATION:
        probs.append(f"结界环 p11 Formation {ring[12]!r} != {ORBIT_FORMATION}")
    if ring[9] != ORBIT_SHAPE_BARRIER:
        probs.append(f"结界环 p8 形状 {ring[9]!r} != {ORBIT_SHAPE_BARRIER}")
    if (ring[10], ring[11]) != (["Center"], ["Center"]):
        probs.append(f"结界环 HAlign/VAlign {(ring[10], ring[11])!r} != Center/Center（pivot≠0 会自转位移）")
    if ring[13] != ["SpecifyHitAreaLifetimeDirectly", ORBIT_RING_LIFETIME]:
        probs.append(f"结界环寿命 {ring[13]!r} != {ORBIT_RING_LIFETIME} 帧")
    if ring[14] != ["CalculatedUsingMaxNumOfHits", ORBIT_THROTTLE_N]:
        probs.append(f"结界环 p13 节流 {ring[14]!r} != CalculatedUsingMaxNumOfHits({ORBIT_THROTTLE_N})")
    if ring[15] != ["Some", slv(ORBIT_HIT_CAP, ORBIT_HIT_CAP)]:
        probs.append(f"结界环 p14 命中上限 {ring[15]!r} != Some({ORBIT_HIT_CAP})")
    if ring[25] != ORBIT_GID_GROUP:
        probs.append(f"结界环 p24 节流作用域 {ring[25]!r} != {ORBIT_GID_GROUP}（整组共用一条冷却）")
    if ring[12][:1] == ["Circle"] and ring[9][:1] == ["Circle"]:
        cov = orbit_coverage(ring[12][2], ring[9][1][0]["min"], ring[12][1])
        if not cov["centre_covered"]:
            probs.append(f"判定圆半径 {cov['barrier_radius']} <= 环半径 {cov['ring_radius']}：环心是空洞，"
                         "站在球停点的 boss 打不到")

    # 3 MoveHitArea 与公转互斥
    n_moves = len([c for c in walk_cmds(ring[20]) if c[0] == "MoveHitArea"])
    if n_moves:
        probs.append(f"结界环 onCreate 里还有 {n_moves} 条 MoveHitArea：世界坐标位移 + 公转 = 螺旋飞出屏幕")

    # 4 纵向冲击不能跟着转
    rotating = {c[1] for c in walk_cmds(tree) if c[0] == "RotateHitArea"}
    if column[2] in rotating:
        probs.append(f"纵向冲击 p1 subject {column[2]!r} 挂在被旋转的 subject 上 ⇒ 冲击会转到脚底下")
    if crp[10] in rotating:
        probs.append(f"球停点参照点 bind {crp[10]!r} 被旋转 ⇒ 整棵树（含纵向冲击）跟着转")

    # 5 命中节拍复算：保守模型锁住不漂，逐帧真值确认「机会数确实够 20 次」（两个模型都必须够）
    sch = orbit_hit_schedule(ring[13][1], ring[14][1], ring[15][1][0]["min"])
    if (sch["step_frames"], sch["realized"], sch["last_hit_frame"]) != (6, ORBIT_HIT_CAP, 114):
        probs.append(f"命中节拍保守复算 {sch} != 6 帧 / {ORBIT_HIT_CAP} 次 / 末次 114 帧")
    exact = orbit_hit_schedule_exact(ring[13][1], ring[14][1], ring[15][1][0]["min"])
    for name, s in (("保守", sch), ("逐帧", exact)):
        if s["opportunities"] < ORBIT_HIT_CAP:
            probs.append(f"{name}模型机会数 {s['opportunities']} < 命中上限 {ORBIT_HIT_CAP}"
                         "：环寿命内打不满，面板合计倍率就是假的")
        if s["realized"] != ORBIT_HIT_CAP:
            probs.append(f"{name}模型实得命中 {s['realized']} != {ORBIT_HIT_CAP}")

    # 6 面板三项合计不动
    tot = skill_totals(tree, level)
    if tot["mult"] != list(EXPECTED_MULT[level]):
        probs.append(f"合计倍率 {tot['mult']} != 面板 {list(EXPECTED_MULT[level])}")
    if (tot["toughness"], tot["fever"]) != ORBIT_EXPECTED_TOUGH_FEVER:
        probs.append(f"合计削韧/Fever {(tot['toughness'], tot['fever'])} != 线上 {ORBIT_EXPECTED_TOUGH_FEVER}")
    if tot["flat"] != ORBIT_EXPECTED_FLAT:
        probs.append(f"合计固定伤害 {tot['flat']} != 线上 {ORBIT_EXPECTED_FLAT}"
                     "（p5 flatDamage 逐击都加，漏摊薄 = 20 倍固定项）")

    # 7 特效生命周期：R26 的「44 帧一拍 ×3 重发」已被 R27 推翻（44 帧窗口是误测，见 R27 块的逐帧证据），
    #   现在的判据是「单发 + UntilTargetTerminates + 中心特效与环同寿命」⇒ 委给 :func:`fx_lifecycle_problems`
    probs += fx_lifecycle_problems(tree, ring)
    return probs


# ---------------------------------------------------------------- 改版 R27（作者第四轮 20260917：结界寿命与消失动画）
#
# 作者原话：「夏勇希的技能中间的圈会比周围旋转的提前消失，周围旋转的延展到最长时会突然消失或者缩短重新延长，
# 我想要的效果的中心的圈和最外层时间一样并且保留消失动画，外圈延长到最长后保持并转圈」。
# 逐帧证据 + 改前改后连拍在 ``work/character_packs/seasonal7-20260916/revision4-20260917/yuki/fx-timing.md``
# （渲染器 ``…/revision4-20260917/yuki/fx/{parts_render,playback_sim,column_probe}.py``）。
#
# **R26 的「44 帧可见窗口」是误测**：离线逐帧渲染 ``psychic_yuki_ny23_attack``（143 帧）实测
# 第 1–141 帧**每一帧都有图**（墨量 2614 → 46942 → 426），第 44–100 帧根本不是空的。
# 真实分段（``column_probe.json``，按「行墨量 ≥ 40 的最上一行」测结界柱上沿，排除飞屑）：
#   * 第 1–71 帧 = **展开**：柱上沿从 −104 单调长到 −407（每帧约 4px），六段六角结界逐段叠上去；
#   * 第 72–89 帧 = **完全展开**：上沿恒定在 −407…−411（±4px），墨量 39525→40683（±1.6%）；
#   * 第 90 帧起 = **收尾**：timeline 自带 ``se_ice_break_echo`` 碎冰音正在这一帧，
#     第 91–101 帧外层辉光收束（墨量 −11%），第 102 帧整柱炸成冰屑，第 141 帧散尽，142–143 空。
# ⇒ R26 的「44 帧一拍重发」把特效切在**展开途中**再从头播 ⇒ 作者看到的
# 「延展到最长时突然消失 / 缩短重新延长」；且母本只有一条 ``('neutral','once',1,143)``，
# 没有 ``end`` 段 ⇒ ``ActionEffect.fade()`` 走 else 分支 ``ttl=0`` 当帧删除 = 没有消失动画。
#
# 修法（素材层补段 + DSL 回到 1.4.889 的挂法）：
#   1. ``psychic_yuki_ny23_attack.timeline`` 补成官方最常见的三段式
#      ``start(pass) / loop(loop) / end(once)``（官方 battle/effect 全库 **94 处**逐字同形，
#      例 ``enemy_shot_arc_guardian_thunder``）。loop 右端取 **89** 而不是 101：
#      ``Playhead.playSoundWhenExists`` 在**每次帧号变化**时按新帧查 soundFrameMap，
#      把第 90 帧的 ``se_ice_break_echo`` 圈进 loop = 每圈重播一次碎冰音（0.3 秒一次）；
#      而且第 91–101 帧外层辉光在收束，圈进 loop 会出现「变细→突然变粗」= 作者抱怨的同一个观感。
#   2. 「攻撃演出」``ShowEffect`` p4 寿命从 R26 的 ``SpecifyEffectLifetimeDirectly(44)`` ×3
#      **改回 1.4.889 的 ``["UntilTargetTerminates"]`` 且只发一次**：结界环判定区终止时
#      ``update()`` 里 ``(tp||td) && target.hasTerminated()`` ⇒ ``fade()`` ⇒ ``gotoAndPlay("end")``
#      ⇒ 自然播完 54 帧碎裂消散（``ActionEffect.as`` fade/EffectLifetime index 3）。
#   3. 中心圈 = ``psychic_yuki_ny23_player``（「チャージ演出」，挂球停点参照点 bind 1、
#      包围盒 ±225px 正好填满 Circle(6,200) 环心；``psychic_yuki_barrier`` 挂 −17 是角色身上的屏障球，
#      不在这个同心画面里）。它母本只有 ``('loop','loop',1,45)``、没有 ``end`` ⇒ 到寿命当帧删。
#      给它 **parts 补一段 alpha 渐隐尾 + timeline 补 ``end`` 段**，构造与**同族官方**
#      ``psychic_yuki_ny23_character_back`` 的 end 段逐位相同（补间位域 ``(63<<18)|(2<<16)|时长``、
#      末帧 alpha 12、末尾一帧空），只有时长不同。
#   4. 三个中心特效（バック/フロント/チャージ）寿命 102 → **132 = 结界环寿命**：
#      R26 把环从 102 拉到 132 却没动它们，正是「中间的圈提前消失」的根因（1.4.889 里两者都是 102，是对齐的）。
#      ⇒ 第 132 帧「结界解除」，三件套同时开始消散，中心圈的渐隐尾长度 = 外圈碎裂长度 54 帧
#      ⇒ **两者同一帧散尽（第 186 帧）**。
#
# 不动：环寿命 132、节流 24、上限 20、p24=1、每击倍率/削韧/Fever/固定伤害、AddCombo、
# 角速度 0.03、Circle(6,200)、判定圆 220、纵向冲击、任何词条/队长/文案/贴图字节。
# ⇒ 每敌仍 21 连击（环 20 + 冲击 1），面板合计 24/(30→34) 倍、削韧 24、Fever 12、固定 200 逐值不变。
FX_WAVE_DIR = f"battle/effect/skill_unique/{CODE}_wave"          # clone layout="sibling" 的落点
FX_ATTACK_BASE = f"{TEMPLATE_CODE}_attack"                       # psychic_yuki_ny23_attack（外圈结界本体）
FX_PLAYER_BASE = f"{TEMPLATE_CODE}_player"                       # psychic_yuki_ny23_player（中心圈）
FX_ATTACK_TIMELINE_REL = f"{FX_WAVE_DIR}/{FX_ATTACK_BASE}.timeline.amf3.deflate"
FX_PLAYER_PARTS_REL = f"{FX_WAVE_DIR}/{FX_PLAYER_BASE}.parts.amf3.deflate"
FX_PLAYER_TIMELINE_REL = f"{FX_WAVE_DIR}/{FX_PLAYER_BASE}.timeline.amf3.deflate"

FX_ATTACK_TOTAL = 143                                            # parts g[0].t == 母本 timeline 的唯一序列 end
FX_ATTACK_EXPAND_END = 71                                        # 展开段末帧（第 72 帧起柱高恒定）
FX_ATTACK_LOOP = (72, 89)                                        # 保持段：柱高恒定、墨量 ±1.6%、不含第 90 帧碎冰音
FX_ATTACK_END = (90, FX_ATTACK_TOTAL)                            # 收尾段：碎冰音 + 收束 + 碎裂 + 散尽
FX_ATTACK_SEQ_BEFORE = [{"begin": 1, "end": FX_ATTACK_TOTAL, "name": "neutral", "kind": "once"}]
FX_ATTACK_SEQUENCES = [
    {"begin": 1, "end": FX_ATTACK_EXPAND_END, "name": "start", "kind": "pass"},
    {"begin": FX_ATTACK_LOOP[0], "end": FX_ATTACK_LOOP[1], "name": "loop", "kind": "loop"},
    {"begin": FX_ATTACK_END[0], "end": FX_ATTACK_END[1], "name": "end", "kind": "once"},
]
FX_ATTACK_END_FRAMES = FX_ATTACK_END[1] - FX_ATTACK_END[0] + 1   # 54 = fade() 写回的 ttl（getSequenceTotalFrames）
FX_ATTACK_SOUND_FRAMES = (2, 3, 90)                              # 母本三条 SE 的 begin（第 90 帧必须落在 end 段）

FX_PLAYER_LOOP_END = 45                                          # 母本 ('loop','loop',1,45)；周期 15 帧 × 3
FX_PLAYER_FADE_FRAMES = FX_ATTACK_END_FRAMES                     # 54：与外圈碎裂等长 ⇒ 中心圈与最外层同帧散尽
FX_PLAYER_TWEEN_BITS = (63 << 18) | (2 << 16)                    # 官方 character_back 的线性补间位域（ev-63=0）
FX_PLAYER_FADE_ALPHA = 12                                        # 官方 character_back end 段末帧 alpha
FX_PLAYER_SEQ_BEFORE = [{"begin": 1, "end": FX_PLAYER_LOOP_END, "name": "loop", "kind": "loop"}]
FX_PLAYER_END_BEGIN = FX_PLAYER_LOOP_END + 1                     # 46
FX_PLAYER_END_END = FX_PLAYER_LOOP_END + FX_PLAYER_FADE_FRAMES   # 99
FX_PLAYER_SEQUENCES = [
    {"begin": 1, "end": FX_PLAYER_LOOP_END, "name": "loop", "kind": "loop"},
    {"begin": FX_PLAYER_END_BEGIN, "end": FX_PLAYER_END_END, "name": "end", "kind": "once"},
]

R4_CENTER_FX_NAMES = ("バック演出", "フロント演出", "チャージ演出")   # 三个挂球停点参照点 bind 1 的中心特效
R4_CENTER_LIFETIME_BEFORE = 102                                  # 1.4.889/1.4.893 线上值（= R26 之前的环寿命）
R4_CENTER_LIFETIME = ORBIT_RING_LIFETIME                         # 132：与结界环同一刻解除


def fx_attack_timeline_patch(tl: dict) -> dict:
    """``psychic_yuki_ny23_attack.timeline``：一条 neutral once → start/loop/end 三段（就地改 sequences）。

    幂等：已是三段就原样返回。母本 sequences 不是预期那一条则报错（不静默改）。
    """
    seqs = tl["sequences"]
    if [(s["name"], s["kind"]) for s in seqs] == [(s["name"], s["kind"]) for s in FX_ATTACK_SEQUENCES]:
        if seqs != FX_ATTACK_SEQUENCES:
            raise AssertionError(f"attack timeline 已是三段但边界不同：{seqs!r}")
        return tl
    if seqs != FX_ATTACK_SEQ_BEFORE:
        raise AssertionError(f"attack timeline 母本 sequences {seqs!r} != {FX_ATTACK_SEQ_BEFORE!r}")
    sounds = tuple(int(s["begin"]) for s in tl.get("sounds") or ())
    if sounds != FX_ATTACK_SOUND_FRAMES:
        raise AssertionError(f"attack timeline SE 帧号 {sounds} != {FX_ATTACK_SOUND_FRAMES}（母本漂移）")
    tl["sequences"] = copy.deepcopy(FX_ATTACK_SEQUENCES)
    return tl


def fx_player_parts_patch(parts: dict) -> dict:
    """``psychic_yuki_ny23_player.parts``：根图层尾部补一段 alpha 渐隐（就地改 g[0]）。

    母本 ``g[0] = {"t": 45, "s": [{"s": 0x80000000, "i": 1, "l": [{"m": 255, "t": 45, "r": 0x80000000}]}]}``
    （``s`` 高两位 = kind 2 graphics、低 30 位 = 起始帧 0；``r`` 高两位 = GraphicsLoopKind 2 取模、
    低 30 位 = 起始子帧 0 ⇒ 子图层 g[1] 按 (0+i)%45 循环）。
    补两条关键帧，与同族官方 ``character_back`` 的 end 段逐位同构：
      * 补间帧：``{"m": 255, "t": (63<<18)|(2<<16)|(F-2), "r": 0x80000000}``——线性补到下一帧的 alpha；
      * 末帧：  ``{"m": 12, "r": 0x80000000}``——无 ``t`` ⇒ 停留 1 帧。
    ``g[0].t`` 同步抬到 45 + F（末 1 帧留空，和母本 character_back 的 21–22 帧同形）。
    """
    g0 = parts["g"][0]
    total = int(g0["t"])
    if total == FX_PLAYER_END_END:
        return parts                                     # 幂等
    if total != FX_PLAYER_LOOP_END:
        raise AssertionError(f"player parts g[0].t {total} != 母本 {FX_PLAYER_LOOP_END}")
    if len(g0["s"]) != 1:
        raise AssertionError(f"player parts g[0] 有 {len(g0['s'])} 条 strip（母本 1 条）")
    strip = g0["s"][0]
    kfs = strip["l"]
    if len(kfs) != 1 or int(kfs[0]["m"]) != 255 or int(kfs[0]["t"]) != FX_PLAYER_LOOP_END:
        raise AssertionError(f"player parts 根关键帧 {kfs!r} != 母本单帧 m=255 t={FX_PLAYER_LOOP_END}")
    ref = kfs[0]["r"]
    tween_frames = FX_PLAYER_FADE_FRAMES - 2             # 末帧 1 帧 + 末尾 1 帧空
    if tween_frames < 1 or tween_frames > 0xFFFF:
        raise AssertionError(f"渐隐补间帧数 {tween_frames} 越界")
    kfs.append({"m": 255, "t": FX_PLAYER_TWEEN_BITS | tween_frames, "r": ref})
    kfs.append({"m": FX_PLAYER_FADE_ALPHA, "r": ref})
    g0["t"] = FX_PLAYER_END_END
    return parts


def fx_player_timeline_patch(tl: dict) -> dict:
    """``psychic_yuki_ny23_player.timeline``：loop 一条 → loop + end 两段（官方 19 处先例）。"""
    seqs = tl["sequences"]
    if [(s["name"], s["kind"]) for s in seqs] == [(s["name"], s["kind"]) for s in FX_PLAYER_SEQUENCES]:
        if seqs != FX_PLAYER_SEQUENCES:
            raise AssertionError(f"player timeline 已是两段但边界不同：{seqs!r}")
        return tl
    if seqs != FX_PLAYER_SEQ_BEFORE:
        raise AssertionError(f"player timeline 母本 sequences {seqs!r} != {FX_PLAYER_SEQ_BEFORE!r}")
    if tl.get("sounds"):
        raise AssertionError("player timeline 母本本来没有 SE，补 end 段前先确认没把 SE 圈进 loop")
    tl["sequences"] = copy.deepcopy(FX_PLAYER_SEQUENCES)
    return tl


def fx_timeline_problems(attack_tl: dict, player_tl: dict, player_parts: dict) -> list[str]:
    """素材层三份产物的门禁（读包内字节复核，不读 kit 的中间结论）。"""
    probs: list[str] = []
    seqs = attack_tl.get("sequences")
    if seqs != FX_ATTACK_SEQUENCES:
        probs.append(f"attack timeline sequences {seqs!r} != {FX_ATTACK_SEQUENCES!r}")
    else:
        # 段必须首尾相接、覆盖 1..总帧数，且第 90 帧碎冰音落在 end 段（圈进 loop = 每圈重播）
        if seqs[0]["begin"] != 1 or seqs[-1]["end"] != FX_ATTACK_TOTAL:
            probs.append(f"attack timeline 段没覆盖 1..{FX_ATTACK_TOTAL}")
        for a, b in zip(seqs, seqs[1:]):
            if int(b["begin"]) != int(a["end"]) + 1:
                probs.append(f"attack timeline 段不连续：{a!r} -> {b!r}")
    lo, hi = FX_ATTACK_LOOP
    for s in attack_tl.get("sounds") or ():
        if lo <= int(s["begin"]) <= hi:
            probs.append(f"attack timeline SE {s['path']} 的第 {s['begin']} 帧落在 loop 段 {lo}..{hi}"
                         "：每圈都会重播（Playhead.playSoundWhenExists 按帧号变化触发）")
    if player_tl.get("sequences") != FX_PLAYER_SEQUENCES:
        probs.append(f"player timeline sequences {player_tl.get('sequences')!r} != {FX_PLAYER_SEQUENCES!r}")
    g0 = player_parts["g"][0]
    if int(g0["t"]) != FX_PLAYER_END_END:
        probs.append(f"player parts g[0].t {g0['t']} != {FX_PLAYER_END_END}（timeline 末段 end 会落空）")
    kfs = g0["s"][0]["l"]
    if len(kfs) != 3:
        probs.append(f"player parts 根关键帧 {len(kfs)} 条 != 3（保持 + 补间 + 末帧）")
    else:
        want_t = FX_PLAYER_TWEEN_BITS | (FX_PLAYER_FADE_FRAMES - 2)
        if int(kfs[1]["t"]) != want_t:
            probs.append(f"player parts 补间帧 t {kfs[1]['t']} != {want_t}")
        if int(kfs[1]["m"]) != 255 or int(kfs[2]["m"]) != FX_PLAYER_FADE_ALPHA:
            probs.append(f"player parts 渐隐 alpha {int(kfs[1]['m'])}->{int(kfs[2]['m'])} "
                         f"!= 255->{FX_PLAYER_FADE_ALPHA}")
        if kfs[2].get("t"):
            probs.append("player parts 末帧带了 t（bit16-17 非 0 会让补间去读越界的下一帧）")
    span = sum((int(k.get("t") or 0) & 0xFFFF) or 1 for k in kfs)
    if span > int(g0["t"]):
        probs.append(f"player parts 根 strip 跨度 {span} > g[0].t {g0['t']}（客户端 #1125 越界）")
    return probs


def fx_lifecycle_problems(tree, ring=None) -> list[str]:
    """R27 的 DSL 侧门禁：外圈只发一次且跟随判定区；三个中心特效寿命 = 环寿命。"""
    probs: list[str] = []
    if ring is None:
        try:
            ring = locate_orbit(tree)["ring"]
        except AssertionError as exc:
            return [f"orbit 结构定位失败：{exc}"]
    shows = [c for c in walk_cmds(ring[20]) if c[0] == "ShowEffect" and c[1] == "攻撃演出"]
    waits = [c for c in walk_cmds(ring[20]) if c[0] == "Wait"]
    if len(shows) != 1:
        probs.append(f"「攻撃演出」在结界环 onCreate 里出现 {len(shows)} 次 != 1"
                     "（重发 = 每拍从第 1 帧重播展开 = 作者说的「缩短重新延长」）")
    if waits:
        probs.append(f"结界环 onCreate 里还有 {len(waits)} 条 Wait（R26 的重发链没删干净）")
    for i, s in enumerate(shows):
        if s[5] != ["UntilTargetTerminates"]:
            probs.append(f"「攻撃演出」#{i} p4 寿命 {s[5]!r} != ['UntilTargetTerminates']"
                         "（不跟判定区就播不到 end 段 = 没有消失动画）")
        if s[3] != ring[19]:
            probs.append(f"「攻撃演出」#{i} p2 主体 {s[3]!r} != 结界环绑定 id {ring[19]!r}")
        if s[11] is not True or s[10] is not True:
            probs.append(f"「攻撃演出」#{i} tracking {(s[10], s[11])!r} 必须都是 True"
                         "（fade 由 (tp||td) && target.hasTerminated() 触发）")
    centre = {c[1]: c for c in walk_cmds(tree) if c[0] == "ShowEffect" and c[1] in R4_CENTER_FX_NAMES}
    if sorted(centre) != sorted(R4_CENTER_FX_NAMES):
        probs.append(f"中心特效只找到 {sorted(centre)} != {sorted(R4_CENTER_FX_NAMES)}")
    for name, c in sorted(centre.items()):
        if c[5] != ["SpecifyEffectLifetimeDirectly", R4_CENTER_LIFETIME]:
            probs.append(f"中心特效「{name}」寿命 {c[5]!r} != {R4_CENTER_LIFETIME} 帧"
                         "（与结界环寿命不同 = 作者说的「中间的圈提前消失」）")
    return probs


def repair_fx_lifecycle(ctx, pack) -> dict[str, Any]:
    """特效族克隆之后**必须**跑：给外圈结界族补 start/loop/end，给中心圈补 alpha 渐隐尾 + end 段。

    框架的 ``clone_effect_family`` 只有 ``png_transform`` 钩子、没有 parts/timeline 钩子
    （记忆卡 wf-flatomo-animation-format「框架缺口」），所以 ``--step kit`` 每次重新克隆都会把
    母本原样盖回来 ⇒ 这一步必须由 kit 在克隆之后重做，否则每次构建都退回「没有消失动画」。
    写完立刻从包里读回逐条复核（负控 = 不接这个钩子，下面第一条必红）。
    """
    out: dict[str, Any] = {"patched": [], "unchanged": []}
    plan = ((FX_ATTACK_TIMELINE_REL, fx_attack_timeline_patch),
            (FX_PLAYER_PARTS_REL, fx_player_parts_patch),
            (FX_PLAYER_TIMELINE_REL, fx_player_timeline_patch))
    for logical, patch in plan:
        path = pack.pkg_path("common", logical)
        if not path.is_file():
            raise AssertionError(f"包内缺少 {logical}（特效族克隆失败？）")
        before = path.read_bytes()
        tree = patch(ctx.amf_parse(before))
        after = ctx.amf_bytes(tree)
        entry = {"logical": logical, "sha256_before": hashlib.sha256(before).hexdigest(),
                 "sha256_after": hashlib.sha256(after).hexdigest()}
        if after == before:
            out["unchanged"].append(entry)
            continue
        ctx.write_asset("common", logical, after, owner="effects")
        out["patched"].append(entry)
    # ---- 门禁：从包里重新解码复核（不复用上面的内存树）
    attack_tl = ctx.amf_parse(pack.pkg_path("common", FX_ATTACK_TIMELINE_REL).read_bytes())
    player_tl = ctx.amf_parse(pack.pkg_path("common", FX_PLAYER_TIMELINE_REL).read_bytes())
    player_parts = ctx.amf_parse(pack.pkg_path("common", FX_PLAYER_PARTS_REL).read_bytes())
    probs = fx_timeline_problems(attack_tl, player_tl, player_parts)
    if probs:
        raise AssertionError("特效生命周期补段未生效：" + "; ".join(probs))
    out["attack_sequences"] = attack_tl["sequences"]
    out["player_sequences"] = player_tl["sequences"]
    out["player_root_keyframes"] = player_parts["g"][0]["s"][0]["l"]
    out["player_root_total_frames"] = player_parts["g"][0]["t"]
    out["why"] = ("母本 attack 只有一条 neutral once ⇒ 没有 end 段、fade() 当帧删除；"
                  "母本 player 只有 loop 一条 ⇒ 同样当帧删除。补段后判定区终止即自然播消失动画。")
    return out


def apply_fx_lifecycle_edits(tree):
    """就地施加 R27 算子（必须在 ``apply_orbit_edits`` 之后跑），返回改动记录。

    ① 结界环 onCreate：R26 的「44 帧一拍 × 3 次重发」整条换回**单发 + UntilTargetTerminates**；
    ② 三个中心特效寿命 102 → 132（= 结界环寿命）。
    幂等保护：已经是单发形态就报错而不是叠加。
    """
    loc = locate_orbit(tree)
    ring = loc["ring"]
    shows = [c for c in walk_cmds(ring[20]) if c[0] == "ShowEffect" and c[1] == "攻撃演出"]
    if len(shows) != len(ORBIT_FX_REISSUES):
        raise AssertionError(f"结界环 onCreate 里「攻撃演出」{len(shows)} 次 != R26 的 "
                             f"{len(ORBIT_FX_REISSUES)}（R27 已施加过？）")
    show = copy.deepcopy(shows[0])
    if show[5] != ["SpecifyEffectLifetimeDirectly", ORBIT_FX_WINDOW]:
        raise AssertionError(f"「攻撃演出」改动前寿命 {show[5]!r} != R26 的 {ORBIT_FX_WINDOW} 帧")
    show[5] = ["UntilTargetTerminates"]
    ring[20] = ["Block", [["Command", show]]]
    ops = [{"op": "replace", "node": "CreateHitArea#1(结界环).p19 onCreate 块",
            "old": f"ShowEffect(SpecifyEffectLifetimeDirectly {ORBIT_FX_WINDOW}) x{len(ORBIT_FX_REISSUES)}"
                   f"（t = {'/'.join(str(f) for f in ORBIT_FX_REISSUES)}）",
            "new": "ShowEffect(UntilTargetTerminates) x1（判定区终止 ⇒ fade() ⇒ 播 end 段 "
                   f"{FX_ATTACK_END[0]}–{FX_ATTACK_END[1]} 共 {FX_ATTACK_END_FRAMES} 帧碎裂消散）"}]
    seen = []
    for c in walk_cmds(tree):
        if c[0] != "ShowEffect" or c[1] not in R4_CENTER_FX_NAMES:
            continue
        if c[5] != ["SpecifyEffectLifetimeDirectly", R4_CENTER_LIFETIME_BEFORE]:
            raise AssertionError(f"中心特效「{c[1]}」改动前寿命 {c[5]!r} != {R4_CENTER_LIFETIME_BEFORE}")
        c[5] = ["SpecifyEffectLifetimeDirectly", R4_CENTER_LIFETIME]
        seen.append(c[1])
        ops.append({"op": "set", "node": f"ShowEffect「{c[1]}」p4 寿命",
                    "old": R4_CENTER_LIFETIME_BEFORE, "new": R4_CENTER_LIFETIME})
    if sorted(seen) != sorted(R4_CENTER_FX_NAMES):
        raise AssertionError(f"中心特效只改到 {sorted(seen)} != {sorted(R4_CENTER_FX_NAMES)}")
    return ops


# ---------------------------------------------------------------- 结界弹锚点（显式钉住，本轮不动）
#
# **这一环之前只在注释里带过一句，现在钉成常量 + 门禁**（二轮复审 F1）：
# 结界环不是锚在角色身上，而是锚在 ``StopBall`` 之后建立的**球停点**参照点上——
#   ``FindNearSubjects(-18=球, bind 1, selector 49) → StopBall(-18) → CreateReferencePoint(-18, 偏移 0,0,0, bind 1)``
#   ⇒ 6 个子判定区与其「攻撃演出」全部挂在这个参照点（``CreateHitArea.p1 == crp bind``）。
# 记忆卡 ``wf-dsl-builtin-subjects``：-17 = 自身（角色），-18 = 球。本树里挂 -17 的只有
# ``psychic_yuki_swim_barrier/psychic_yuki_barrier``（角色身上的屏障光环），判定区一个都不挂 -17。
#
# **-18 正是官方对「自身周围」的编码方式**，不是本套件走偏了。官方全库普查（live ``action_skill`` 1202 棵可解树）：
#   ``CreateReferencePoint`` p0 = -18 共 **691** 处、= -17 只有 **6** 处；
#   ``CreateHitArea`` p1 直接挂 -18 共 **1129** 处、挂 -17 只有 **25** 处。
#   再取说明里写「自身周围」的 52 个官方技能（Lv1）：**47 个锚在 -18**（37 个直接挂球、10 个经 -18 的参照点），
#   **0 个锚在 -17**。
# ⇒ 球停点就是技能在屏上的发动原点；引擎/文案口径里的「自身周围」= 球停点周围。
# 所以 R25 收「环相对球停点的半径」（710→202px）**就是**「雪花偏离角色太多」在数据侧的正确杠杆。
#
# 反过来说：把 p0 改成 -17 是**官方 6/691 的边缘写法**，还会让判定区离开
# ``FindNearSubjects(49)`` 选中的那批敌人 —— 除非作者明确要求，否则不要动这一位。
SKILL_ANCHOR_SUBJECT = -18                     # CreateReferencePoint p0：球（停球点），不是 -17=角色
SKILL_ANCHOR_OFFSET = (0, 0, 0)                # CreateReferencePoint p2/p3/p4：相对球停点零偏移


def barrier_anchor(tree) -> dict:
    """回读结界弹判定区的**锚点事实**（供门禁与单测钉住，不做任何修改）。

    返回 ``{"subject", "offset", "bind", "hit_area_parent", "attached", "spin_bind", "spin_subject",
    "spin_offset"}``：``subject`` = 球停点 ``CreateReferencePoint`` 的 p0（应为 ``SKILL_ANCHOR_SUBJECT`` = -18 球）、
    ``offset`` = p2/p3/p4、``bind`` = p9 绑定 id、``hit_area_parent`` = 结界判定区 ``CreateHitArea`` 的 p1，
    ``attached`` = 判定区是否确实挂在（R26 后：经旋转参照点挂在）这个锚点上。

    R26 之后锚链是 ``StopBall(-18) → 球停点 CRP(-18, bind 1) → 旋转 CRP(-18, bind 14) → 结界环``：
    旋转参照点自己也锚在 -18 零偏移，所以「环锚在球停点」这条事实**没有**被 R26 改动。
    """
    _near, crp, body, cha1, _cha2 = locate_hit_areas(tree)
    spins = [n[1] for n in body if cmd(n) and cmd(n)[0] == "CreateReferencePoint"]
    spin = spins[0] if len(spins) == 1 else None
    parent_bind = spin[10] if spin is not None else crp[10]
    out = {"subject": crp[1], "offset": (crp[3], crp[4], crp[5]), "bind": crp[10],
           "hit_area_parent": cha1[2], "attached": cha1[2] == parent_bind,
           "spin_bind": None if spin is None else spin[10],
           "spin_subject": None if spin is None else spin[1],
           "spin_offset": None if spin is None else (spin[3], spin[4], spin[5])}
    return out


def anchor_problems(tree) -> list[str]:
    """锚点未被本轮改动的断言（改了要么是有意的、要么是事故，两种都必须显形）。"""
    a = barrier_anchor(tree)
    probs = []
    if a["subject"] != SKILL_ANCHOR_SUBJECT:
        probs.append(f"CreateReferencePoint p0 = {a['subject']!r} != {SKILL_ANCHOR_SUBJECT}（锚点被改；"
                     "-17=角色 是机制改动，须作者授权）")
    if a["offset"] != SKILL_ANCHOR_OFFSET:
        probs.append(f"CreateReferencePoint 偏移 {a['offset']!r} != {SKILL_ANCHOR_OFFSET}")
    if not a["attached"]:
        probs.append(f"结界弹 CreateHitArea p1 = {a['hit_area_parent']!r} 没挂在参照点 bind "
                     f"{a['spin_bind'] if a['spin_bind'] is not None else a['bind']!r} 上")
    if a["spin_bind"] is not None:                    # R26：旋转参照点必须同样锚在球停点零偏移
        if a["spin_subject"] != SKILL_ANCHOR_SUBJECT:
            probs.append(f"旋转参照点 p0 = {a['spin_subject']!r} != {SKILL_ANCHOR_SUBJECT}（锚点被改；"
                         "-17=角色 是机制改动，须作者授权）")
        if a["spin_offset"] != SKILL_ANCHOR_OFFSET:
            probs.append(f"旋转参照点偏移 {a['spin_offset']!r} != {SKILL_ANCHOR_OFFSET}")
    return probs


# ================================================================ 纯函数（门禁脚本复用）

def slv(a, b):
    return [{"min": a, "max": b}]


def cmd(node):
    return node[1] if (isinstance(node, list) and len(node) == 2 and node[0] in ("Command", "Event")
                       and isinstance(node[1], list)) else None


def walk_cmds(node, out=None):
    out = [] if out is None else out
    if isinstance(node, list):
        c = cmd(node)
        if c:
            out.append(c)
        for x in node:
            walk_cmds(x, out)
    elif isinstance(node, dict):
        for x in node.values():
            walk_cmds(x, out)
    return out


def _find_root(children, name, pred=lambda c: True):
    hits = [n for n in children if cmd(n) and cmd(n)[0] == name and pred(cmd(n))]
    if len(hits) != 1:
        raise AssertionError(f"expected exactly one root {name}, got {len(hits)}")
    return hits[0]


def row_sha(row: list[str]) -> str:
    return hashlib.sha256(core.write_csv_lines([row]).rstrip("\n").encode("utf-8")).hexdigest()


def panel_text_problems(texts: dict[str, str] | None = None,
                        flag_names: Iterable[str] = SKILL_FLAG_TEXT_NAMES) -> list[str]:
    """面板文案两条规则（作者 20260916 二轮补充，``revision2-20260916/文案规则-补充.md``）。

    规则 1：面板不出现「无上限」三个字——没有上限的成长写到效果为止，后面什么都不跟；
    「可无限叠加」「不封顶」等替代说法同禁；**有上限的才写上限**。
    规则 2：「技能强化」（``ChangeSkillFlag`` 536 等）条目只写强化了什么，不写具体数字与持续秒数。

    规则 2 的适用面按 ``flag_names`` 点名（本角色唯一的 536 串 ``CAS_TEXT``），不靠句式猜：
    「为『X』追加「Y」」与「强化『X』的「Y」」是同一类条目，只按「强化『」句式匹配会漏掉前者。
    技能说明（``action_skill`` c1）本身照常写清效果，只受规则 1 约束。
    """
    import re
    t = PANEL_TEXTS if texts is None else texts
    names = tuple(flag_names)
    probs: list[str] = []
    for name, text in t.items():
        text = text or ""
        for w in CAP_WORDING_BANNED:
            if w in text:
                probs.append(f"{name} 含无上限措辞 {w!r}（规则 1：没有上限就写到效果为止，后面什么都不跟）")
        if name not in names:
            continue
        if re.search(r"[0-9０-９一二三四五六七八九十]", text):
            probs.append(f"{name} 是技能强化条目却写了数字（规则 2：只写强化了什么）：{text!r}")
        if re.search(r"秒|帧", text):
            probs.append(f"{name} 是技能强化条目却写了时间（规则 2：只写强化了什么）：{text!r}")
    return probs


# ---------------------------------------------------------------- 技能树拼装（全部官方基线）

def locate_hit_areas(tree):
    """定位改版 R18–R26 的作用点，返回 ``(near, crp, body, cha1, cha2)``。

    ``near`` = 唯一 ``FindNearSubjects(49)`` 根；``crp`` = 停球点上的 CreateReferencePoint（结界本体，
    即「自身周围」的锚点）；``body`` = 参照点块；``cha1`` = 结界（环）判定区；``cha2`` = Wait 块内的纵向冲击判定区。
    三种 body 形状都接受：

    - 设计定稿（未施加算子）：``[CRPV, ShowEffect, ShowEffect, CreateHitArea, Wait]``；
    - R18–R25 施加后：``[CRPV, ShowEffect, CreateHitArea, Wait]``（「攻撃演出」已搬进 cha1 的 p19 块）；
    - R26 施加后：``[CRPV, ShowEffect, CreateReferencePoint, Wait]``——结界环挂进了**旋转参照点**，
      ``cha1`` 从那个参照点的块里取（``locate_orbit`` 给旋转通路的完整三元组）。
    """
    near = _find_root(tree[11][1], "FindNearSubjects", lambda c: c[3] == 49)
    blk = near[1][6]
    names = [cmd(x)[0] for x in blk[1] if cmd(x)]
    if names != ["StopBall", "CreateReferencePoint"]:
        raise AssertionError(f"结界 B block shape {names}")
    crp = blk[1][1][1]
    body = crp[11][1]
    names = [cmd(x)[0] for x in body if cmd(x)]
    if names not in (["ConditionalsRelativePositionVertical", "ShowEffect", "ShowEffect", "CreateHitArea", "Wait"],
                     ["ConditionalsRelativePositionVertical", "ShowEffect", "CreateHitArea", "Wait"],
                     ["ConditionalsRelativePositionVertical", "ShowEffect", "CreateReferencePoint", "Wait"]):
        raise AssertionError(f"参照点块 shape {names}")
    if "CreateHitArea" in names:
        cha1 = body[names.index("CreateHitArea")][1]
    else:                                            # R26：结界环在旋转参照点的块里
        spin = body[names.index("CreateReferencePoint")][1]
        cha1 = _find_root(spin[11][1], "CreateHitArea")[1]
    cha2 = body[-1][1][3][1][0][1]
    if cha2[0] != "CreateHitArea":
        raise AssertionError(f"纵向冲击节点是 {cha2[0]}")
    return near, crp, body, cha1, cha2


def apply_skill_edits(tree):
    """就地施加两轮改版算子，返回改动记录。

    一轮 R18/R19/R20/R21：朝结界本体周围 6 方向 + 判定区范围扩大 + 每方向各一份「攻撃演出」+ 整组封顶 1 次命中。
    二轮 R25（作者「雪花偏离角色太多」）：生成偏移 −50→0、逐段外扩速度 20/10/5→6/3/1、判定区长度 160→400。

    幂等保护：改动后参照点块里已没有「攻撃演出」，且逐段速度已不是母本值，重复调用会直接报错而不是叠加。
    """
    _near, _crp, body, cha1, cha2 = locate_hit_areas(tree)
    ops = []
    idx = [i for i, n in enumerate(body) if cmd(n) and cmd(n)[0] == "ShowEffect" and cmd(n)[1] == "攻撃演出"]
    if len(idx) != 1:
        raise AssertionError(f"参照点块内「攻撃演出」ShowEffect 数量 {len(idx)}（改动已施加过？）")
    se_node = body[idx[0]]
    se = se_node[1]
    if se[3] != SKILL_EDIT_BEFORE["show_effect_subject"]:
        raise AssertionError(f"「攻撃演出」p2 主体 {se[3]!r} != 参照点 1")
    bind = cha1[19]                                  # CreateHitArea p18 createdHitAreaBindId
    if not isinstance(bind, int) or isinstance(bind, bool):
        raise AssertionError(f"结界弹判定区 p18 绑定 id {bind!r} 不是整数")
    old_se = copy.deepcopy(se)
    se[3] = bind                                     # p2 lookup：参照点 1 → 判定区绑定 id
    se[5] = ["UntilTargetTerminates"]                # p4 寿命：跟随判定区（官方「針の演出」同形）
    se[11] = True                                    # p10 跟随目标
    se[12] = ["Some", [{"min": PANE_EFFECT_SCALE, "max": PANE_EFFECT_SCALE}]]      # p11 缩放
    body.pop(idx[0])
    cha1[20][1].insert(0, se_node)                   # 搬进判定区 p19 块首位（MoveHitArea 之前）
    ops.append({"op": "move+edit", "node": "ShowEffect 攻撃演出", "from": "CreateReferencePoint.p10块",
                "to": "CreateHitArea#1.p19块[0]", "old": old_se, "new": copy.deepcopy(se)})
    for node, index, key, value, label in (
            (cha1, 12, "formation", SKILL_FORMATION, "CreateHitArea#1(结界弹).p11 Formation"),
            (cha1, 15, "maxhits_barrier", SKILL_MAXHITS_BARRIER, "CreateHitArea#1(结界弹).p14 MaxNumOfHits"),
            (cha1, 9, "shape_barrier", SKILL_SHAPE_BARRIER, "CreateHitArea#1(结界弹).p8 Shape"),
            (cha1, 5, "spawn_offset_y", SKILL_SPAWN_OFFSET_Y, "CreateHitArea#1(结界弹).p4 生成偏移Y"),
            (cha2, 9, "shape_column", SKILL_SHAPE_COLUMN, "CreateHitArea#2(纵向冲击).p8 Shape")):
        if node[index] != SKILL_EDIT_BEFORE[key]:
            raise AssertionError(f"{label} 改动前是 {node[index]!r}，母本已漂移")
        ops.append({"op": "set", "node": label, "old": copy.deepcopy(node[index]), "new": copy.deepcopy(value)})
        node[index] = copy.deepcopy(value)
    # 二轮：逐段外扩速度收回（母本 20/10/5/0 → 6/3/1/0，外扩 710px → 202px）
    moves = [c for c in walk_cmds(cha1[20]) if c[0] == "MoveHitArea"]
    if tuple(c[4] for c in moves) != SKILL_EDIT_BEFORE["move_speeds"]:
        raise AssertionError(f"结界弹 MoveHitArea 逐段速度 {[c[4] for c in moves]} "
                             f"!= 母本 {list(SKILL_EDIT_BEFORE['move_speeds'])}（母本漂移或已施加过）")
    for i, (c, value) in enumerate(zip(moves, SKILL_MOVE_SPEEDS)):
        ops.append({"op": "set", "node": f"CreateHitArea#1.p19块 MoveHitArea[{i}].p3 速度",
                    "old": c[4], "new": value})
        c[4] = value
    ops.append({"op": "derived", "node": "结界弹外扩距离(px)",
                "old": outward_reach(SKILL_EDIT_BEFORE["move_speeds"]), "new": outward_reach()})
    return ops


def compose_tree(read_dsl, level: str, *, apply_revision: bool = True, apply_orbit: bool = True,
                 apply_fx_lifecycle: bool = True):
    """按设计 §4.2 拼装一档技能树（特效路径仍是官方路径，由调用方 rewrite_effect_refs）。

    ``read_dsl(program_path) -> tree`` 必须返回官方基线树（KitContext.template_dsl）。
    ``apply_revision=False`` 返回**改版算子施加前**的设计定稿树，供方案侧脚本做双录对照；
    ``apply_orbit=False`` 停在 R18–R25（1.4.882 的形），``apply_fx_lifecycle=False`` 停在 R26
    （1.4.893 的形），只给对照脚本用。
    """
    plan = PLAN[level]
    ny = read_dsl(f"{RARE5}/psychic_yuki_ny23$psychic_yuki_ny23_{level}")
    yk = read_dsl(f"{RARE5}/psychic_yuki$psychic_yuki_{level}")
    pp = read_dsl(f"{RARE5}/psychic_projection_smr23$psychic_projection_smr23_2")
    sa = read_dsl(f"{RARE5}/sing_android_2halfanv$sing_android_2halfanv_{level}")
    if not (isinstance(ny, list) and ny[0] == "ActionDsl" and ny[1] == 2 and ny[10] == 0):
        raise AssertionError(f"ny23_{level} header unexpected: {ny[:11]}")
    ny_root, yk_root = ny[11][1], yk[11][1]
    # A 全屏雪花 + 屏障演出（121070）
    fx_all = copy.deepcopy(_find_root(yk_root, "ShowEffect", lambda c: c[1] == "全体演出"))
    fx_bar = copy.deepcopy(_find_root(yk_root, "ShowEffect", lambda c: c[1] == "バリア演出"))
    # B 结界弹 + 纵向冲击（121147 根#0）
    near = copy.deepcopy(_find_root(ny_root, "FindNearSubjects", lambda c: c[3] == 49))
    cnas = [c for c in walk_cmds(near) if c[0] == "CreateNormalAttack"]
    if len(cnas) != 2:
        raise AssertionError(f"ny23 B block CNA count {len(cnas)}")
    for c in cnas:
        c[6] = slv(*plan["cna"])                 # p5 攻击倍率
        if c[8] is not False:
            raise AssertionError("ny23 CNA p7 enablesComboBonus expected false")
        c[8] = True                              # p7 enablesComboBonus
    # C 分属性技伤 + 协力（121147 根#1..#6 原样）
    tiers = [copy.deepcopy(n) for n in ny_root if cmd(n) and (
        cmd(n)[0] in ("FindAllSubjects", "TargetMate")
        or (cmd(n)[0] == "CreateCondition" and cmd(n)[1] in (10, 11)))]
    if [cmd(n)[0] for n in tiers] != ["FindAllSubjects", "FindAllSubjects", "TargetMate", "CreateCondition",
                                      "TargetMate", "CreateCondition"]:
        raise AssertionError(f"ny23 C block shape {[cmd(n)[0] for n in tiers]}")
    # D 屏障 + 全属性耐性 + 全队技伤（121070 FindAll(0,33,[2])，绑定 0→12）
    fa = copy.deepcopy(_find_root(yk_root, "FindAllSubjects", lambda c: c[2] == 33))
    body = fa[1][9][1]
    if [cmd(n)[0] for n in body] != ["CreateCondition", "CreateCondition", "CreateBarrier"]:
        raise AssertionError(f"121070 D block shape {[cmd(n)[0] for n in body]}")
    sd = cmd(body[0])[2][0]
    if sd[0] != "ACSkillDamage" or cmd(body[1])[2][0][0] != "ACToleranceOfElement":
        raise AssertionError("121070 D block condition kinds unexpected")
    sd[1] = slv(*plan["d_sd_time"])
    sd[2] = slv(*plan["d_sd_value"])
    fa[1][1] = 12
    for n in body:
        if cmd(n)[1] != 0:
            raise AssertionError("121070 D block subject expected 0")
        cmd(n)[1] = 12
    # E1 施技加连击（sing_android_2halfanv）
    add = copy.deepcopy(_find_root(sa[11][1], "AddCombo"))
    cmd(add)[1] = slv(*plan["addcombo"])
    # E2 水共鸣 flag 分支内 ACComboBoost 挂球（psychic_projection_smr23_2）
    gate = _find_root(pp[11][1], "FindAllSubjects", lambda c: c[2] == 34)
    boost_fa = copy.deepcopy(gate[1][9][1][0])
    if not (cmd(boost_fa)[0] == "FindAllSubjects" and cmd(boost_fa)[2] == 97):
        raise AssertionError("smr23 E2 selector shape unexpected")
    boost_fa[1][1] = 13
    cc = cmd(boost_fa[1][9][1][0])
    if not (cc[0] == "CreateCondition" and cc[1] == 6 and cc[10] == 2 and cc[2][0][0] == "ACComboBoost"):
        raise AssertionError("smr23 E2 CreateCondition shape unexpected")
    cc[1] = 13
    cc[2][0][1] = slv(COMBOBOOST["flips"], COMBOBOOST["flips"])   # ballFlipLimit
    cc[2][0][2] = slv(COMBOBOOST["combo"], COMBOBOOST["combo"])   # 每次弹射回填连击
    flag = ["Command", ["ConditionalsChangeSkillFlag", 1, ["Block", [boost_fa]], ["Block", []]]]
    root = [fx_all, fx_bar, near] + tiers + [fa, add, flag]
    tree = copy.deepcopy(ny[:11]) + [["Block", root]]
    if apply_revision:
        apply_skill_edits(tree)                      # 改版 R18/R19/R20/R21（CNA 倍率不动，靠 p15 封顶维持合计口径）
        if apply_orbit:
            apply_orbit_edits(tree, level)           # 改版 R26（旋转参照点 + Circle 环 + 命中节流 + 倍率摊薄）
            if apply_fx_lifecycle:
                apply_fx_lifecycle_edits(tree)       # 改版 R27（外圈单发跟随判定区 + 中心圈同寿命）
    return tree


# ---------------------------------------------------------------- DSL 静态门禁

def _kindof(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, dict):
        return "DICT"
    if isinstance(v, list):
        if not v:
            return "list"
        if isinstance(v[0], dict):
            return "slv"
        if isinstance(v[0], str):
            return "enum:" + v[0]
        return "list"
    return type(v).__name__


def signature_set(tree, acc=None):
    """(构造名, 参数位) -> {kind}；含 CreateCondition 内 AC 条目（F1034 签名差分口径）。"""
    acc = defaultdict(set) if acc is None else acc
    for c in walk_cmds(tree):
        for i, p in enumerate(c[1:]):
            acc[(c[0], i)].add(_kindof(p))
        if c[0] == "CreateCondition" and len(c) > 2 and isinstance(c[2], list):
            for ac in c[2]:
                if isinstance(ac, list) and ac and isinstance(ac[0], str):
                    for i, p in enumerate(ac[1:]):
                        acc[(ac[0], i)].add(_kindof(p))
    return acc


def signature_diff(tree, official: dict) -> list[str]:
    mine = signature_set(tree)
    out = []
    for (name, idx), kinds in sorted(mine.items()):
        extra = kinds - set(official.get(f"{name}#{idx}", ()))
        if extra:
            out.append(f"{name} p{idx} kinds {sorted(extra)} not seen in official skill DSL")
    return out


def arity_problems(tree) -> list[str]:
    import wf_dsl_sig
    probs = []
    for c in walk_cmds(tree):
        sig = wf_dsl_sig.COMMANDS.get(c[0]) or wf_dsl_sig.EVENTS.get(c[0])
        if sig is None:
            probs.append(f"unknown construct {c[0]}")
            continue
        if len(c) - 1 != len(sig):
            probs.append(f"{c[0]} arity {len(c) - 1} != {len(sig)}")
        for i, t in enumerate(sig):
            if i + 1 < len(c) and t == "Array" and not isinstance(c[i + 1], list):
                probs.append(f"{c[0]} p{i} expects Array, got {type(c[i + 1]).__name__}")
    return probs


# 比 wf_client_legality.action_dsl_subject_binding_problems 多查的 lookup 位
# （记忆卡 wf-dsl-subject-lookup-map：ShowEffect p2 / FindNearSubjects p0 / CreateReferencePoint p0 /
#  CreateHitArea p1 / ["GH",n]）。
_EXTRA_LOOKUPS = {"ShowEffect": (3,), "FindNearSubjects": (1,), "CreateReferencePoint": (1,),
                  "CreateHitArea": (2,)}


def scope_problems(tree) -> list[str]:
    import wf_client_legality as LEG
    consumers = {k: tuple(v) for k, v in LEG.DSL_SUBJECT_CONSUMERS.items()}
    for k, v in _EXTRA_LOOKUPS.items():
        consumers[k] = tuple(sorted(set(consumers.get(k, ())) | set(v)))
    builtin = LEG.DSL_BUILTIN_SUBJECTS
    probs: list[str] = []

    def gh_refs(value, out):
        if isinstance(value, list):
            if value and value[0] in ("Block", "Command", "Event"):
                return
            if len(value) == 2 and value[0] == "GH" and isinstance(value[1], int):
                out.append(value[1])
                return
            for x in value:
                gh_refs(x, out)

    def check(name, idx, v, bound):
        if isinstance(v, int) and not isinstance(v, bool) and v not in bound and v not in builtin:
            probs.append(f"{name}[{idx}]={v} unbound (bound={sorted(bound)})")

    def walk(node, bound: frozenset):
        if isinstance(node, list) and node and isinstance(node[0], str) and node[0] not in ("Block", "Command", "Event"):
            name = node[0]
            for idx in consumers.get(name, ()):
                if idx < len(node):
                    check(name, idx, node[idx], bound)
            refs: list[int] = []
            binders = LEG.DSL_SUBJECT_BINDERS.get(name) or ()
            handled = {blk for _, blk in binders}
            for i, p in enumerate(node[1:], 1):
                if i not in handled:
                    gh_refs(p, refs)
            for r in refs:
                check(f"{name}.GH", "coord", r, bound)
            if binders:
                for ids, blk in binders:
                    if blk < len(node):
                        walk(node[blk], bound | {node[i] for i in ids if i < len(node) and isinstance(node[i], int)})
                for i, child in enumerate(node[1:], 1):
                    if i not in handled:
                        walk(child, bound)
                return
            for child in node[1:]:
                walk(child, bound)
            return
        if isinstance(node, list):
            scope = set(bound)
            for child in node:
                walk(child, frozenset(scope))
                c = cmd(child)
                if c and c[0] in LEG.DSL_STATEMENT_BINDERS:
                    slot = LEG.DSL_STATEMENT_BINDERS[c[0]]
                    if slot < len(c) and isinstance(c[slot], int):
                        scope.add(c[slot])
        elif isinstance(node, dict):
            for child in node.values():
                walk(child, bound)

    walk(tree, frozenset())
    return probs


def donothing_branch_problems(tree) -> list[str]:
    """Conditionals* 分支写 ["DoNothing"] = 进战斗 F1009（记忆卡 wf-dsl-donothing-enum-trap）。"""
    probs = []
    for c in walk_cmds(tree):
        if c[0].startswith("Conditionals"):
            for i, p in enumerate(c[1:]):
                if isinstance(p, list) and p == ["DoNothing"]:
                    probs.append(f"{c[0]} p{i} is ['DoNothing'] (use ['Block', []])")
    return probs


def acskilldamage_gid_problems(tree) -> tuple[list[str], dict]:
    """同技能多条本地 ACSkillDamage：同时长下数值区间必须互不重合（含完全相等）。

    条件 gid = 派生/命中率/时长/层上限/内容数值/…（ConditionId_Impl_.as:23-80），时长与数值都相同
    的两条会互相覆盖而不是相加。TargetMate 送给联机参战者的条件不落在本地单位上，不参与比较。
    """
    mates = {c[1] for c in walk_cmds(tree) if c[0] == "TargetMate"}
    local: list[tuple] = []
    detail: dict[tuple, list] = {}
    for c in walk_cmds(tree):
        if c[0] == "CreateCondition" and isinstance(c[2], list) and c[2] and c[2][0][0] == "ACSkillDamage":
            t, v = c[2][0][1][0], c[2][0][2][0]
            detail.setdefault((t["min"], t["max"]), []).append((v["min"], v["max"]))
            if c[1] not in mates:
                local.append(((t["min"], t["max"]), (v["min"], v["max"]), c[1]))
    probs = []
    for i in range(len(local)):
        for j in range(i + 1, len(local)):
            (ta, (a0, a1), sa), (tb, (b0, b1), sb) = local[i], local[j]
            if ta != tb:
                continue
            if not (max(a0, a1) < min(b0, b1) or max(b0, b1) < min(a0, a1)):
                probs.append(f"ACSkillDamage subject {sa} {(a0, a1)} vs subject {sb} {(b0, b1)} overlap at duration {ta}")
    return probs, {f"{k[0]}f": sorted(set(v)) for k, v in detail.items()}


def hit_area_budget_problems(tree) -> tuple[list[str], list[dict]]:
    """多子判定区（Formation != Single）必须显式封顶每个敌人的命中次数，否则实伤是面板的 n 倍。

    引擎口径（``ActionHitAreaGroup.as`` / ``ActionHitArea.as``，20260916 复审实证）：

    - p14 ``CalculatedUsingMaxNumOfHits(1)`` 只把 ``minHitInterval`` 折成 ``Option.None``；
    - ``minHitInterval`` 的计数键 ``gidForMinHitInterval`` 由 **p25** 决定：0 ⇒ ``Address.ActionHitArea``
      （每个子区一份，互不影响）、1 ⇒ ``Address.ActionHitAreaGroup``（整组共用）；
    - 唯一的 group 级命中预算在 ``resolveCollision`` 的 ``switch(maxNumOfHits.index) case 0``，
      **只有 p15=Some(N) 才走**；p15=["None"] 落 default 不做任何事。

    ⇒ ``Formation != Single`` + ``p15=["None"]`` + ``p25=0`` = 每个子区对同一敌人各结算一次。
    官方这一形全是「每发各自结算」的散射技（arisa / crybaby_shooter / bee_girl）；
    要保「整组只打 N 次」的官方写法是 p15=Some(N)（paralysis_hedgehog / ice_dragon / doctor_pirate）
    或 p25=1（waste_armor / ice_dragon）。

    ⚠ 这条**不是**「官方全绿」型检查器：官方散射技（arisa / crybaby_shooter / bee_girl）本来就要每发各自结算，
    拿它们当正控会红，那是正确判红而不是误报。它的适用面是「面板写了『合计 N 倍』的技能」。
    正/反对照证据见 ``impl/yuki/hit_area_budget_controls.json``。
    """
    probs, info = [], []
    for c in walk_cmds(tree):
        if c[0] != "CreateHitArea" or len(c) < 27:
            continue
        formation = c[12][0] if isinstance(c[12], list) and c[12] else str(c[12])
        capped = (isinstance(c[15], list) and c[15] and c[15][0] == "Some") or c[25] == 1
        subareas = c[12][1] if formation in ("NWay", "Circle", "Line", "AShaped") and len(c[12]) > 1 else 1
        info.append({"name": c[1], "formation": c[12], "min_hit_interval": c[14],
                     "max_num_of_hits": c[15], "min_hit_interval_scope": "group" if c[25] == 1 else "per-sub-area",
                     "capped": capped})
        if formation != "Single" and not capped:
            probs.append(f"CreateHitArea {c[1]!r} {formation}({subareas}) has p15=['None'] and p25=0: "
                         f"每个子区各打一次 ⇒ 实伤 ×{subareas}（要整组封顶请写 p15=Some(N) 或 p25=1）")
    return probs, info


def effect_strings(tree) -> list[str]:
    return sorted({s for s in _walk_strings(tree) if s.startswith("battle/effect/")})


def _walk_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for x in node:
            yield from _walk_strings(x)
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(k)
            yield from _walk_strings(v)


def tree_gates(tree, official_signatures: dict | None) -> dict[str, Any]:
    import wf_client_legality as LEG
    import wf_dsl
    enc = wf_dsl.encode_amf3(tree)
    gid, gid_detail = acskilldamage_gid_problems(tree)
    budget, budget_detail = hit_area_budget_problems(tree)
    mult = [c[6][0] for c in walk_cmds(tree) if c[0] == "CreateNormalAttack"]
    return {
        "bare_tree_root": [] if (isinstance(tree, list) and tree and tree[0] == "ActionDsl")
        else ["tree root is not a bare ActionDsl list (wrapper-shell trap)"],
        "amf3_roundtrip": [] if wf_dsl.parse_dsl(enc)["tree"] == tree else ["encode/parse roundtrip differs"],
        "signature_arity": arity_problems(tree),
        "signature_diff_vs_official": (signature_diff(tree, official_signatures)
                                       if official_signatures is not None else ["official signature set unavailable"]),
        "scope": scope_problems(tree),
        "subject_binding": LEG.action_dsl_subject_binding_problems(tree),
        "element_code": LEG.action_dsl_element_problems(tree, ELEMENT),
        "direction": wf_dsl.player_side_dsl_problems(tree),
        "hit_area_target": LEG.action_dsl_hit_area_target_problems(tree),
        "donothing_branch": donothing_branch_problems(tree),
        "acskilldamage_gid": gid,
        "hit_area_budget": budget,
        "_info": {"encoded_size": len(enc), "tree1_movementPriority": tree[1], "tree10_buffTargetAs": tree[10],
                  "cna_multipliers": mult, "acskilldamage_values": gid_detail, "hit_areas": budget_detail},
    }


def official_signature_set(ctx, cache_path: Path | None = None) -> dict[str, list[str]]:
    """官方基线 action_skill 全部技能 DSL 的签名集（按官方表 sha256 缓存）。"""
    import wf_dsl
    raw = ctx.official_read(ACTION, "common")
    if raw is None:
        raise FileNotFoundError("official action_skill table unavailable")
    digest = hashlib.sha256(raw).hexdigest()
    if cache_path is not None and cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("action_skill_sha256") == digest:
                return cached["signatures"]
        except (OSError, ValueError, KeyError):
            pass
    nested = core.load_nested_table_bytes(raw, ACTION)
    acc: defaultdict = defaultdict(set)
    count = 0
    for inner in nested.rows.values():
        for text in inner.text_rows().values():
            rows = core.read_csv_lines(text)
            if not rows or len(rows[0]) < 8 or not rows[0][7]:
                continue
            dsl_raw = ctx.official_read(wf_dsl.dsl_logical(rows[0][7]), "common")
            if dsl_raw is None:
                continue
            try:
                tree = wf_dsl.parse_dsl(zlib.decompress(dsl_raw, -15))["tree"]
            except Exception:
                continue
            signature_set(tree, acc)
            count += 1
    signatures = {f"{name}#{idx}": sorted(kinds) for (name, idx), kinds in sorted(acc.items())}
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"action_skill_sha256": digest, "programs": count,
                                          "signatures": signatures}, ensure_ascii=False, indent=0),
                              encoding="utf-8")
    return signatures


# ---------------------------------------------------------------- 行门禁 / 渲染

def row_gates(kind: str, row: list[str]) -> dict[str, list[str]]:
    import wf_client_legality as LEG
    return {"client_legality": LEG.client_legality_problems(kind, row),
            "declared_block_field": LEG.declared_block_field_problems(kind, row),
            "element_column": LEG.ability_element_column_problems(kind, row, ELEMENT),
            "required_capabilities": LEG.required_client_capabilities(kind, row)}


def package_row_report(ctx) -> dict[str, Any]:
    """对包内本角色全部 ability/leader 行跑合法性 + wf_describe 渲染（读包内候选表，不读内存）。"""
    import wf_describe
    out: dict[str, Any] = {"rows": [], "problems": [], "required_capabilities": []}
    tables = ((LD, "leader_ability", [CID]), (AB, "ability", [f"{CID}{s}" for s in range(1, 7)]))
    for logical, kind, keys in tables:
        flat = ctx.pkg_flat(logical)
        for key in keys:
            if key not in flat:
                out["problems"].append(f"{logical}#{key} missing in package")
                continue
            for li, row in enumerate(core.read_csv_lines(flat[key])):
                gates = row_gates(kind, row)
                entry = {"table": kind, "key": key, "line": li, "describe": wf_describe.describe_line(row, kind),
                         "cells": len(row), **{k: v for k, v in gates.items()}}
                out["rows"].append(entry)
                for gk in ("client_legality", "declared_block_field", "element_column"):
                    out["problems"].extend(f"{kind} {key}#{li} {gk}: {p}" for p in gates[gk])
                for cap in gates["required_capabilities"]:
                    if cap not in out["required_capabilities"]:
                        out["required_capabilities"].append(cap)
    cas = ctx.pkg_flat(CAS) if ctx.pack.pkg_has("common", CAS) else {}
    import wf_client_legality as LEG
    for key in sorted(k for k in cas if CODE in k):
        for cap in LEG.required_client_capabilities(LEG.CUSTOM_ABILITY_STRING_KIND, [key]):
            if cap not in out["required_capabilities"]:
                out["required_capabilities"].append(cap)
    return out


# ---------------------------------------------------------------- 特效资源解析

def resolve_effect_refs(ctx, trees: dict[str, Any]) -> dict[str, Any]:
    """DSL 里每条 battle/effect 引用：parts/timeline 与所在目录 sheet/atlas 在包内或 live 可解析；
    克隆 timeline 内嵌 SE：包内 / live 可解析，否则须有官方同 timeline 原文先例（APK 内置 SE）。"""
    import wf_assets
    pack = ctx.pack
    problems, resolved, sounds = [], [], []

    def where(logical: str) -> str | None:
        for root in ("common", "medium", "android"):
            if pack.pkg_has(root, logical):
                return f"package:{root}"
        return "live" if wf_assets.locate(ctx.store, logical) else None

    for label, tree in trees.items():
        for ref in effect_strings(tree):
            if "/.gen/" in ref:
                continue
            parts = where(f"{ref}.parts.amf3.deflate")
            timeline = where(f"{ref}.timeline.amf3.deflate")
            dir_ = ref.rsplit("/", 1)[0]
            dname = dir_.rsplit("/", 1)[-1]
            sheet, atlas = where(f"{dir_}/{dname}.png"), where(f"{dir_}/{dname}.atlas.amf3.deflate")
            entry = {"tree": label, "ref": ref, "parts": parts, "timeline": timeline, "sheet": sheet, "atlas": atlas}
            resolved.append(entry)
            if not (parts or timeline):
                problems.append(f"{label}: effect {ref} has neither parts nor timeline in package/live")
            if parts and not (sheet and atlas):
                problems.append(f"{label}: effect {ref} sheet/atlas {dir_}/{dname}.png|atlas unresolved")
    # 克隆 timeline 的 SE
    families = pack.read_evidence("effect-families.json", {}) or {}
    for dst_dir, fam in sorted(families.items()):
        for eff in fam.get("effects", []):
            logical = f"{eff['target']}.timeline.amf3.deflate"
            if not pack.pkg_has("common", logical):
                continue
            tl = ctx.amf_parse(pack.pkg_path("common", logical).read_bytes())
            for s in sorted({x for x in _walk_strings(tl) if x.startswith("sound_effect/")}):
                loc = where(s + ".mp3")
                entry = {"timeline": eff["target"], "sound": s, "resolved": loc}
                if loc is None:
                    src_raw = ctx.official_read(f"{eff['source']}.timeline.amf3.deflate", "common")
                    precedent = bool(src_raw) and s in set(_walk_strings(ctx.amf_parse(src_raw)))
                    entry["official_timeline_precedent"] = precedent
                    if not precedent:
                        problems.append(f"timeline {eff['target']} sound {s} unresolved and no official precedent")
                sounds.append(entry)
    return {"problems": problems, "refs": resolved, "sounds": sounds}


# ---------------------------------------------------------------- 染色：fx manifest 钩子 + 保守回退

def _load_fx_manifest(root: Path) -> tuple[dict[str, Path], str | None]:
    path = root / FX_MANIFEST_REL
    if not path.is_file():
        return {}, None
    data = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    pairs: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for field in ("sheets", "files", "map", "png"):
            if isinstance(data.get(field), dict):
                pairs.extend((str(k), str(v)) for k, v in data[field].items())
            elif isinstance(data.get(field), list):
                data.setdefault("_list", []).extend(data[field])
        pairs.extend((k, v) for k, v in data.items() if isinstance(v, str) and k.endswith(".png"))
        items = data.get("_list", [])
    else:
        items = data if isinstance(data, list) else []
    for item in items:
        if isinstance(item, dict):
            src = item.get("source") or item.get("src") or item.get("logical")
            png = item.get("png") or item.get("file") or item.get("path") or item.get("output")
            if src and png:
                pairs.append((str(src), str(png)))
    mapping = {}
    for src, png in pairs:
        p = Path(png)
        mapping[src] = p if p.is_absolute() else base / p
    return mapping, str(path)


def _rgb_to_hsv(rgb):
    import numpy as np
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    nz = d > 1e-6
    rm = nz & (mx == r)
    gm = nz & (mx == g) & ~rm
    bm = nz & ~rm & ~gm
    h[rm] = ((g - b)[rm] / d[rm]) % 6
    h[gm] = (b - r)[gm] / d[gm] + 2
    h[bm] = (r - g)[bm] / d[bm] + 4
    h = h * 60.0
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0)
    return h, s, mx


def _hsv_to_rgb(h, s, v):
    import numpy as np
    c = v * s
    hp = (h % 360) / 60.0
    x = c * (1 - np.abs(hp % 2 - 1))
    z = np.zeros_like(h)
    conds = [(hp < 1), (hp < 2), (hp < 3), (hp < 4), (hp < 5), (hp >= 5)]
    rgbs = [(c, x, z), (x, c, z), (z, c, x), (z, x, c), (x, z, c), (c, z, x)]
    r = np.select(conds, [t[0] for t in rgbs])
    g = np.select(conds, [t[1] for t in rgbs])
    b = np.select(conds, [t[2] for t in rgbs])
    m = v - c
    return np.stack([r + m, g + m, b + m], -1)


def _hue_band_remap(img, src_lo, src_hi, dst_lo, dst_hi, sat_mul=1.0):
    import numpy as np
    from PIL import Image
    arr = np.asarray(img.convert("RGBA")).astype(np.float64)
    rgb = arr[..., :3] / 255.0
    alpha = arr[..., 3]
    h, s, v = _rgb_to_hsv(rgb)
    band = (alpha > 0) & (s > 0.08) & (h >= src_lo) & (h <= src_hi)
    nh = np.where(band, dst_lo + (h - src_lo) / (src_hi - src_lo) * (dst_hi - dst_lo), h)
    ns = np.where(band, np.clip(s * sat_mul, 0, 1), s)
    out = np.where(band[..., None], _hsv_to_rgb(nh, ns, v), rgb)
    arr[..., :3] = np.clip(np.round(out * 255.0), 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA").copy()   # fromarray 共享内存 = 只读


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _apply_lut_rect(img, rect, lut: dict[str, str], tol: int = 10):
    """小人贴图：按身体 LUT 近邻换色（设计 §6 / effects.clone[0].special_tiles）。"""
    px = img.load()
    x0, y0, w, h = rect
    table = [(_hex(k), _hex(v)) for k, v in lut.items()]
    changed = 0
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            best = min(table, key=lambda kv: abs(kv[0][0] - r) + abs(kv[0][1] - g) + abs(kv[0][2] - b))
            dist = max(abs(best[0][0] - r), abs(best[0][1] - g), abs(best[0][2] - b))
            if dist <= tol and best[0] != best[1]:
                px[x, y] = (*best[1], a)
                changed += 1
    return changed


def _atlas_rects(ctx, src_dir: str, needles: tuple[str, ...]) -> list[tuple[int, int, int, int]]:
    donor = src_dir.rsplit("/", 1)[-1]
    _root, raw, _src = ctx.pack.template_asset(f"{src_dir}/{donor}.atlas.amf3.deflate")
    # Starling atlas：x/y/w/h 就是图内存储矩形；r=True 只表示图块顺时针存放，宽高不用对调
    # （wf_pixelart_vfx.restore_frame 同口径；对调会越出 sheet 边界）
    return [(int(item["x"]), int(item["y"]), int(item["w"]), int(item["h"]))
            for item in ctx.amf_parse(raw)
            if isinstance(item, dict) and any(n in str(item.get("n", "")) for n in needles)]


def make_png_transform(ctx, family: dict, fx_map: dict[str, Path], log: list[dict], body_lut: dict[str, str]):
    """优先 fx manifest 替换 sheet（尺寸必须一致）；否则保守回退染色。"""
    src_dir = family["src_dir"]
    donor = src_dir.rsplit("/", 1)[-1]
    sheet_logical = f"{src_dir}/{donor}.png"
    dst_dir = f"battle/effect/skill_unique/{CODE}_{family['subdir']}"
    dst_logical = f"{dst_dir}/{CODE}_{family['subdir']}.png"
    replacement = fx_map.get(sheet_logical) or fx_map.get(dst_logical)

    def transform(img):
        if replacement is not None:
            raw = Path(replacement).read_bytes()
            new = ctx.png_open(raw).convert("RGBA")
            if new.size != img.size:
                raise ValueError(f"fx manifest sheet {replacement} size {new.size} != source {img.size}")
            import numpy as np
            a0, a1 = np.asarray(img.convert("RGBA"))[..., 3], np.asarray(new)[..., 3]
            log.append({"sheet": sheet_logical, "dst_sheet": dst_logical, "mode": "fx-manifest",
                        "file": str(replacement), "sha256": hashlib.sha256(raw).hexdigest(),
                        "alpha_identical": bool((a0 == a1).all()),
                        "alpha_zero_preserved": bool(((a0 == 0) == (a1 == 0)).all())})
            return new
        if family["subdir"] == "wave":
            # 小人贴图只走身体 LUT（先从原图取块换色，色相映射后贴回，避免被水色映射先染偏）
            base = img.convert("RGBA").copy()
            tiles, changed = [], 0
            for rect in _atlas_rects(ctx, src_dir, ("_character_back/a", "_character_front/a")):
                changed += _apply_lut_rect(base, rect, body_lut)
                x, y, w, h = rect
                tiles.append(((x, y), base.crop((x, y, x + w, y + h))))
            out = _hue_band_remap(img, 150.0, 192.0, 196.0, 212.0, sat_mul=0.92)
            for pos, tile in tiles:
                out.paste(tile, pos)
            log.append({"sheet": sheet_logical, "dst_sheet": dst_logical, "mode": "kit-fallback",
                        "recipe": "hue 150-192 -> 196-212 (sat x0.92); character_back/front/a body LUT",
                        "lut_pixels": changed})
            return out
        out = _hue_band_remap(img, 170.0, 215.0, 196.0, 210.0, sat_mul=1.05)
        log.append({"sheet": sheet_logical, "dst_sheet": dst_logical, "mode": "kit-fallback",
                    "recipe": "hue 170-215 -> 196-210 (sat x1.05)"})
        return out

    return transform


def fx_recolor_problems(ctx, fx_map: dict[str, Path], fx_manifest: str | None,
                        recolor_log: list[dict]) -> list[str]:
    """fx manifest 存在时：两族 sheet 都必须由它替换（不许与回退染色混用）、alpha==0 位置不变、
    包内落盘 sheet 与染色 PNG 逐像素相同（包内是 WF 小写魔数的存储态，解码后比较）。"""
    if fx_manifest is None:
        return []
    import numpy as np
    problems = []
    for entry in recolor_log:
        if entry["mode"] != "fx-manifest":
            problems.append(f"fx manifest present but {entry['sheet']} used {entry['mode']}")
            continue
        if not entry["alpha_zero_preserved"]:
            problems.append(f"fx sheet {entry['file']} changes alpha==0 coverage of {entry['sheet']}")
        want = np.asarray(ctx.png_open(Path(entry["file"]).read_bytes()).convert("RGBA"))
        got = np.asarray(ctx.png_open(ctx.pack.pkg_path("common", entry["dst_sheet"]).read_bytes()).convert("RGBA"))
        if want.shape != got.shape or not bool((want == got).all()):
            problems.append(f"package sheet {entry['dst_sheet']} pixels != fx manifest PNG {entry['file']}")
    if len(recolor_log) != 2:
        problems.append(f"expected 2 recolored sheets, got {len(recolor_log)}")
    return problems


# ---------------------------------------------------------------- PNG 存储态魔数：包级门禁 + Integrate 装像素 sheet

WF_PNG_MAGIC = wf_assets.PNG_FAKE             # 包 / store / CDN 存储态 b"\x89png\r\n\x1a\n"
STD_PNG_MAGIC = wf_assets.PNG_REAL            # 标准 PNG b"\x89PNG\r\n\x1a\n"（PIL/像素工具产物）
PACKAGE_PNG_ROOTS = ("common", "medium", "android")   # = wf_character_pack.CLIENT_ROOTS
PIXEL_DIR = f"character/{CODE}/pixelart"
PIXEL_SHEET_NAMES = ("sprite_sheet", "special_sprite_sheet")
PIXEL_OUT_REL = f"{BATCH}/pixel/{KEY}/out"


def package_png_storage_problems(package_dir: Path) -> tuple[list[str], int]:
    """包内三个客户端根下每个 .png 的前 8 字节都必须是 WF 存储态魔数。

    flow preflight（``wf_character_pack.validate_manifest``，production + require_referenced_assets）
    只在 manifest 重建后才拒标准魔数；本门禁在 kit / run_gates 阶段就报，且覆盖尚未进 manifest 的文件。
    返回 (problems, 检查的 PNG 数)。"""
    problems, count = [], 0
    for root in PACKAGE_PNG_ROOTS:
        base = Path(package_dir) / "roots" / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() != ".png":
                continue
            count += 1
            with path.open("rb") as fh:
                head = fh.read(len(WF_PNG_MAGIC))
            if head != WF_PNG_MAGIC:
                kind = "standard PNG magic" if head == STD_PNG_MAGIC else f"magic {head!r}"
                problems.append(f"{root}:{path.relative_to(base).as_posix()} has {kind}; package PNGs must be "
                                "WF storage form (wf_assets.png_encode)")
    return problems, count


def _png_rgba(raw: bytes):
    import io
    from PIL import Image
    return Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA")


def pixel_sheet_store_bytes(raw: bytes, native_raw: bytes,
                            atlas_rects: Iterable[tuple[int, int, int, int]] = ()) -> tuple[bytes, dict[str, Any]]:
    """像素产物 PNG → 包内存储态字节。只换前 8 字节魔数，不重编码像素数据；同时做装包前核对：

    - 输入是标准 PNG（``png_encode``）或已是存储态（原样）；其他魔数报错；
    - 尺寸 == 包内现有 sheet（atlas 坐标绑定这个尺寸），atlas 每个矩形都落在图内；
    - 存在 alpha==0 像素（图集 alpha 硬门禁）；
    - 输出前 8 字节 == WF 存储魔数，解码后与输入逐像素相同。"""
    import numpy as np
    head = raw[:len(STD_PNG_MAGIC)]
    if head == STD_PNG_MAGIC:
        out, magic_in = wf_assets.png_encode(raw), "standard"
    elif head == WF_PNG_MAGIC:
        out, magic_in = raw, "wf-storage"
    else:
        raise ValueError(f"pixel sheet is not a PNG (magic {head!r})")
    img, native = _png_rgba(raw), _png_rgba(native_raw)
    if img.size != native.size:
        raise ValueError(f"pixel sheet size {img.size} != package sheet {native.size} (atlas is bound to it)")
    rects = list(atlas_rects)
    outside = [r for r in rects if r[0] < 0 or r[1] < 0 or r[0] + r[2] > img.width or r[1] + r[3] > img.height]
    if outside:
        raise ValueError(f"{len(outside)} atlas rects fall outside {img.size}: {outside[:3]}")
    src = np.asarray(img)
    alpha0 = int((src[..., 3] == 0).sum())
    if alpha0 == 0:
        raise ValueError("pixel sheet has no alpha==0 pixels (opaque background)")
    if out[:len(WF_PNG_MAGIC)] != WF_PNG_MAGIC:
        raise AssertionError("store bytes lack WF storage magic")
    got = np.asarray(_png_rgba(out))
    if got.shape != src.shape or not bool((got == src).all()):
        raise AssertionError("store bytes decode to different pixels")
    return out, {"magic_in": magic_in, "size": list(img.size), "alpha0_pixels": alpha0, "atlas_rects": len(rects),
                 "sha256_in": hashlib.sha256(raw).hexdigest(), "sha256_out": hashlib.sha256(out).hexdigest()}


def pixel_atlas_rects(ctx, name: str) -> list[tuple[int, int, int, int]]:
    raw = ctx.pack.pkg_path("common", f"{PIXEL_DIR}/{name}.atlas.amf3.deflate").read_bytes()
    return [(int(i["x"]), int(i["y"]), int(i["w"]), int(i["h"])) for i in ctx.amf_parse(raw) if isinstance(i, dict)]


def install_pixel_sheets(ctx, src_dir: Path | None = None, *, write: bool = True) -> list[dict[str, Any]]:
    """Integrate 阶段装像素小人 2 张 sheet（kit ``build`` 不调用，像素仍在修复轮）。

    用法::

        import wf_seasonal7_build as B, wf_seasonal7_common as C, wf_seasonal7_specs as S
        K.install_pixel_sheets(B.KitContext(C.S7Pack(S.get_spec("yuki"))))

    两张先全部核对（``pixel_sheet_store_bytes``）再写，不会只装一半；写入走 ``write_asset(owner="pixel")``
    （同时登记 sha），回读确认存储魔数。atlas / frame / timeline 元数据不动。
    装完重跑 ``--step manifest,status,inspect`` 与 impl/yuki/run_gates.py。``write=False`` 只核对不落盘。"""
    src = Path(src_dir) if src_dir is not None else ctx.root / PIXEL_OUT_REL
    staged: list[tuple[str, bytes, dict[str, Any]]] = []
    for name in PIXEL_SHEET_NAMES:
        logical = f"{PIXEL_DIR}/{name}.png"
        source = src / f"{name}.png"
        data, info = pixel_sheet_store_bytes(source.read_bytes(), ctx.pack.pkg_path("common", logical).read_bytes(),
                                             pixel_atlas_rects(ctx, name))
        staged.append((logical, data, {"logical": logical, "source": str(source), **info}))
    log = []
    for logical, data, entry in staged:
        if write:
            ctx.write_asset("common", logical, data, owner="pixel")
            back = ctx.pack.pkg_path("common", logical).read_bytes()
            if back != data or back[:len(WF_PNG_MAGIC)] != WF_PNG_MAGIC:
                raise AssertionError(f"pixel sheet readback mismatch: {logical}")
            entry["written"] = True
        log.append(entry)
    return log


def template_provenance_problems(ctx) -> list[str]:
    """技能树母本必须来自官方基线（template_dsl 缺官方件时会静默回落 live，框架 §8.8）。"""
    sources = ctx.pack.read_evidence("template_sources.json", {}) or {}
    problems = []
    for program in (f"{RARE5}/psychic_yuki_ny23$psychic_yuki_ny23_1", f"{RARE5}/psychic_yuki_ny23$psychic_yuki_ny23_2",
                    f"{RARE5}/psychic_yuki$psychic_yuki_1", f"{RARE5}/psychic_yuki$psychic_yuki_2",
                    f"{RARE5}/psychic_projection_smr23$psychic_projection_smr23_2",
                    f"{RARE5}/sing_android_2halfanv$sing_android_2halfanv_1",
                    f"{RARE5}/sing_android_2halfanv$sing_android_2halfanv_2"):
        src = (sources.get(f"{program}.action.dsl.amf3.deflate") or {}).get("source")
        if src != "official":
            problems.append(f"template DSL {program} source={src!r} (must be official baseline)")
    return problems


# ================================================================ build

def _design(ctx) -> dict | None:
    path = ctx.root / DESIGN_REL
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _revision(ctx) -> dict | None:
    """作者 20260916 改版方案。缺文件时只失去「donor 漂移回落成品行」这层兜底，配方 sha 锁仍然生效。"""
    path = ctx.root / REVISION_REL
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _revision3(ctx) -> dict | None:
    """三轮 R26 的文案锁（只覆盖技能说明三格）。缺文件时回落二轮 plan.json。"""
    path = ctx.root / REVISION3_REL
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def skill_desc_lock(revision: dict | None, revision3: dict | None) -> dict[str, str] | None:
    """现行技能说明锁：``{"1": c1, "2": c1, "c5": …, "c7": …}``；两份方案都缺时返回 None。"""
    if revision3 is not None:
        return {"1": revision3["action_skill"]["1"]["c1"], "2": revision3["action_skill"]["2"]["c1"],
                "c5": revision3["character_text"]["c5"], "c7": revision3["character_text"]["c7"]}
    if revision is not None:
        return {"1": revision["text"]["action_skill"]["1"]["c1"],
                "2": revision["text"]["action_skill"]["2"]["c1"],
                "c5": revision["text"]["character_text"]["c5"], "c7": revision["text"]["character_text"]["c7"]}
    return None


def _revision5(ctx) -> dict | None:
    """五轮 R28/R29/R30 的行锁（只覆盖三条 row_sha256）。缺文件时全部回落二轮 plan.json。"""
    path = ctx.root / REVISION5_REL
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def row_sha_lock(revision: dict | None, revision5: dict | None) -> dict[str, list[str]] | None:
    """现行成品行 sha 锁：``{"leader": [...], "<cid><slot>": [...]}``；二轮方案缺失时返回 None。

    先取二轮 plan.json 的 22 条，再按五轮行锁逐条覆盖。覆盖项必须同时给出
    ``row_sha256_before``（= plan 里那条）与 ``row_sha256``，对不上就报错——
    防止 plan 被人改过却静默沿用旧覆盖。
    """
    if revision is None:
        return None
    out = {"leader": [r["row_sha256"] for r in revision["leader"]["records"]]}
    out.update({key: [r["row_sha256"] for r in recs]
                for key, recs in revision["abilities"]["keys"].items()})
    if revision5 is None:
        return out
    for ov in revision5["overrides"]:
        bucket = "leader" if ov["table"] == LD else ov["key"]
        idx = ov["index"]
        if out[bucket][idx] != ov["row_sha256_before"]:
            raise AssertionError(f"revision5 override {ov['id']}: plan sha {out[bucket][idx][:12]} "
                                 f"!= row_sha256_before {ov['row_sha256_before'][:12]}")
        out[bucket][idx] = ov["row_sha256"]
    for add in revision5.get("adds", ()):          # 追加行只能接在该键末尾，索引必须连号
        bucket = "leader" if add["table"] == LD else add["key"]
        if add["index"] != len(out[bucket]):
            raise AssertionError(f"revision5 add {add['id']}: index {add['index']} "
                                 f"!= 该键现有记录数 {len(out[bucket])}（新行只能追加在末尾）")
        out[bucket].append(add["row_sha256"])
    return out


def record_counts_lock(revision: dict, revision5: dict | None) -> dict[str, int]:
    """现行记录数：二轮 plan 的 {leader, <键>: n} 加上五轮追加的行。"""
    counts = {"leader": revision["record_counts"]["leader"],
              **{k: v for k, v in revision["record_counts"]["abilities"].items()}}
    for add in (revision5 or {}).get("adds", ()):
        bucket = "leader" if add["table"] == LD else add["key"]
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _override_cells(ov: dict) -> list[tuple[int, str, str]]:
    """行锁覆盖项 → [(列, 改前, 改后)]；``col``/``before``/``after`` 允许单值或等长列表。"""
    cols = ov["col"] if isinstance(ov["col"], list) else [ov["col"]]
    def spread(value):
        return value if isinstance(value, list) else [value] * len(cols)
    before, after = spread(ov["before"]), spread(ov["after"])
    if not (len(cols) == len(before) == len(after)):
        raise AssertionError(f"revision5 override {ov['id']}: col/before/after 长度不一致")
    return list(zip(cols, before, after))


def _locked_rows(revision: dict | None, revision5: dict | None = None) -> dict[str, list[list[str]]]:
    """二轮 plan.json 的成品行，按五轮行锁逐格打补丁。

    每条覆盖都带 ``before`` 与 ``row_sha256``：plan 里那格对不上 ``before`` 就报错，
    打完补丁的行 sha 对不上 ``row_sha256`` 也报错 —— 与配方里的 sha 锁互为独立证据。
    """
    if revision is None:
        return {}
    out = {"leader": [r["row"] for r in revision["leader"]["records"]]}
    out.update({key: [r["row"] for r in recs] for key, recs in revision["abilities"]["keys"].items()})
    for ov in (revision5 or {}).get("overrides", ()):
        bucket = "leader" if ov["table"] == LD else ov["key"]
        row = list(out[bucket][ov["index"]])
        for col, before, after in _override_cells(ov):
            if row[col] != before:
                raise AssertionError(f"revision5 override {ov['id']}: plan c{col}={row[col]!r} "
                                     f"!= before {before!r}")
            row[col] = after
        if row_sha(row) != ov["row_sha256"]:
            raise AssertionError(f"revision5 override {ov['id']}: 打补丁后的 plan 行 sha "
                                 f"{row_sha(row)[:12]} != row_sha256 {ov['row_sha256'][:12]}")
        out[bucket][ov["index"]] = row
    # 追加行 plan 里没有成品行可打补丁 ⇒ donor 漂移时没有兜底，只能靠配方的 sha 锁（build 会报错）
    for add in (revision5 or {}).get("adds", ()):
        bucket = "leader" if add["table"] == LD else add["key"]
        if add["index"] != len(out[bucket]):
            raise AssertionError(f"revision5 add {add['id']}: index {add['index']} "
                                 f"!= 该键现有记录数 {len(out[bucket])}（新行只能追加在末尾）")
        out[bucket].append(None)
    return out


def _build_rows(ctx, locked: dict[str, list[list[str]]], notes: list) -> tuple[list[list[str]],
                                                                               dict[str, list[list[str]]]]:
    """donor + 声明列编辑 → 成品行 sha 锁；donor 漂移时回落改版方案里的锁定成品行。

    本轮改版后所有 donor 都在角色自身键之外（自身 live 行发布后会变成本方案的结果，
    拿它当 donor 会让重跑不再自洽），因此发布前后重跑都得到同一批行。
    """
    live = {AB: ctx.live_flat(AB), LD: ctx.live_flat(LD)}
    official = {AB: ctx.official_flat(AB), LD: ctx.official_flat(LD)}

    def build(recipe, table, locked_rows):
        out = []
        for i, (src, key, idx, edits, sha) in enumerate(recipe):
            rows = core.read_csv_lines((live if src == "store" else official)[table][key])
            row = list(rows[idx])
            for col, value in edits.items():
                row[col] = value
            if row_sha(row) == sha:
                out.append(row)
                continue
            fallback = locked_rows[i] if locked_rows and i < len(locked_rows) else None
            # 五轮追加的行 plan 里没有成品行（占位 None）⇒ donor 漂移时没有兜底，直接报错
            if fallback is not None and row_sha(fallback) == sha:
                notes.append(f"donor drift {src}:{key}#{idx}; used locked revision row (sha {sha[:12]})")
                out.append(list(fallback))
                continue
            raise AssertionError(f"row recipe {table} {src}:{key}#{idx} no longer matches locked sha {sha[:12]}")
        return out

    leader = build(LEADER_RECIPE, LD, locked.get("leader"))
    abilities = {f"{CID}{slot}": build(recipe, AB, locked.get(f"{CID}{slot}"))
                 for slot, recipe in ABILITY_RECIPE.items()}
    return leader, abilities


def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.cid_s, spec.code, spec.template_code) != (CID, CODE, TEMPLATE_CODE):
        raise AssertionError(f"kit bound to {CID}/{CODE}, spec is {spec.cid_s}/{spec.code}")
    notes: list[str] = []
    design = _design(ctx)
    if design is not None and design.get("status") != "final":
        raise AssertionError(f"design status {design.get('status')!r} != final")
    revision = _revision(ctx)
    if revision is not None and (revision.get("key"), revision.get("cid")) != (KEY, CID):
        raise AssertionError(f"revision plan is for {revision.get('key')}/{revision.get('cid')}")
    if revision is None:
        notes.append(f"{REVISION_REL} 缺失：donor 漂移无成品行兜底（配方 sha 锁仍生效）")
    revision3 = _revision3(ctx)
    if revision3 is not None and (revision3.get("key"), revision3.get("cid")) != (KEY, CID):
        raise AssertionError(f"revision3 text lock is for {revision3.get('key')}/{revision3.get('cid')}")
    desc_lock = skill_desc_lock(revision, revision3)
    if revision3 is None:
        notes.append(f"{REVISION3_REL} 缺失：技能说明锁回落二轮 plan.json")
    revision5 = _revision5(ctx)
    if revision5 is not None and (revision5.get("key"), revision5.get("cid")) != (KEY, CID):
        raise AssertionError(f"revision5 row lock is for {revision5.get('key')}/{revision5.get('cid')}")
    sha_lock = row_sha_lock(revision, revision5)
    if sha_lock is not None:                      # 配方 sha 必须等于「二轮 plan + 五轮覆盖」
        want = [r[4] for r in LEADER_RECIPE]
        if want != sha_lock["leader"]:
            raise AssertionError("leader recipe sha != plan+revision5 lock")
        for slot, recipe in ABILITY_RECIPE.items():
            if [r[4] for r in recipe] != sha_lock[f"{CID}{slot}"]:
                raise AssertionError(f"ability {slot} recipe sha != plan+revision5 lock")
    if revision5 is None:
        notes.append(f"{REVISION5_REL} 缺失：五轮三条行的 sha 覆盖无外部锁（配方 sha 仍生效）")

    # ---- 1 词条 / 队长
    leader, abilities = _build_rows(ctx, _locked_rows(revision, revision5), notes)
    from wf_water_balance_20260924 import yuki_rows
    abilities[f"{CID}2"] = yuki_rows(abilities[f"{CID}2"])
    ctx.write_flat(LD, {CID: leader})
    ctx.write_flat(AB, abilities)

    # ---- 2 custom_ability_string（536 行 c70 键；主表必须有）
    ctx.write_flat(CAS, {CHANGE_SKILL_KEY: [[CHANGE_SKILL_TEXT]]})
    if design is not None:
        # 键仍对设计定稿；**文本**归二轮改版方案（规则 2 重写，见 revision2-20260916/文案规则-补充.md）
        want = {e["key"]: e["text"] for e in design.get("custom_strings", [])}
        if sorted(want) != [CHANGE_SKILL_KEY]:
            raise AssertionError(f"custom string plan keys differ from design: {sorted(want)}")
    if revision is not None and CHANGE_SKILL_TEXT != revision["text"]["custom_ability_string"]["text"]:
        raise AssertionError("custom_ability_string text differs from revision plan")
    if panel_text_problems():
        raise AssertionError(f"panel text rules: {panel_text_problems()}")
    # 框架自动克隆但无人引用的 change_skill/desc_override 键（勇希母本无，按通用规则撤）
    referenced = {cell for key in abilities for row in abilities[key] for cell in row}
    for claim in ctx.pack.load_claims():
        if claim["logical_path"] == CAS and claim["root"] == "common":
            stale = [k for k in claim["outer_keys"] if k != CHANGE_SKILL_KEY and k not in referenced]
            if stale:
                ctx.unclaim(CAS, stale)
                notes.append(f"unclaimed unused custom_ability_string keys {stale}")

    # ---- 3 action_skill 两档
    current = ctx.pkg_nested(CODE)
    if set(current) != {"1", "2"}:
        raise AssertionError(f"package action_skill {CODE} levels {sorted(current)}")
    template_nested = core.load_nested_table_bytes(ctx.pack.template_table_bytes(ACTION), ACTION)
    template_inner = {k: core.read_csv_lines(v)[0]
                      for k, v in template_nested.rows[TEMPLATE_CODE].text_rows().items()}
    action_rows = {}
    for level, name, desc in (("1", SKILL_NAME_1, SKILL_DESC_1), ("2", SKILL_NAME_2, SKILL_DESC_2)):
        cells = list(template_inner[level])
        if len(cells) != 24:
            raise AssertionError(f"template action_skill row width {len(cells)} != 24")
        cells[0], cells[1], cells[2], cells[3] = name, desc, SKILL_ICON, "true"
        cells[4:7] = list(ENERGY[level])
        cells[7] = ctx.program_path(level)
        cells[8:11] = list(AUTO_CAST)
        action_rows[level] = cells
        if design is not None:
            plan = design["skills"]["action_skill_rows"][level]
            # c1（技能说明）本轮按 R22 压缩，改对改版方案；其余列仍对设计定稿
            for col, key in ((0, "c0"), (2, "c2"), (3, "c3"), (7, "c7")):
                if cells[col] != plan[key]:
                    raise AssertionError(f"action_skill {level} c{col} differs from design")
            # ⚠ 对抗审查 20260917：这两条原本写在下面 `raise` 之后 ⇒ **永远执行不到**（死代码），
            # 「自动施放三列」与「能量三列」的设计定稿比对实际上一直没生效。移回 design 分支里。
            if cells[8:11] != plan["c8_c10"]:
                raise AssertionError(f"action_skill {level} c8-c10 {cells[8:11]} differs from design "
                                     f"{plan['c8_c10']}")
            energy = design["skills"]["energy"][level]
            if cells[4:7] != [str(energy["c4"]), str(energy["c5"]), str(energy["c6"])]:
                raise AssertionError(f"action_skill {level} energy {cells[4:7]} differs from design")
        if desc_lock is not None and cells[1] != desc_lock[level]:
            raise AssertionError(f"action_skill {level} c1 differs from revision text lock")
    ctx.write_nested(ACTION, CODE, {lv: [cells] for lv, cells in action_rows.items()}, replace_inner=True)

    # ---- 4 switched_action_skill（语音 kind 3 路由）= action_skill c7–c23
    switched = {lv: cells[7:24] for lv, cells in action_rows.items()}
    ctx.write_nested(SWITCHED, VOICE_READY_KEY, {lv: [cells] for lv, cells in switched.items()},
                     replace_inner=True)

    # ---- 5 character / character_text / 三层镜像
    crow = ctx.pack.pkg_character_row()
    expected_fixed = {0: CODE, 2: "5", 3: str(ELEMENT), 6: "4", 8: CODE, 17: CID, 26: "Supporter", 27: CID,
                      36: "6,6,6,6,6,6"}
    for col, value in expected_fixed.items():
        if crow[col] != value:
            raise AssertionError(f"character c{col}={crow[col]!r} expected {value!r}")
    crow = list(crow)
    crow[9:17] = VOICE_ROUTE
    crow[18] = TEXTS["leader"]
    crow[19:25] = [f"{CID}{s}" for s in range(1, 7)]
    if design is not None:
        edits = design["identity"]["character_row_edits_vs_121147"]
        if crow[9:17] != edits["9..16"] or crow[18] != edits["18"] or crow[19:25] != edits["19..24"]:
            raise AssertionError("character row edits differ from design")
        if design["voice"]["route"]["character_c9_c16"] != VOICE_ROUTE:
            raise AssertionError("voice route differs from design")
    ctx.write_flat(CHAR, {CID: [crow]})
    trow = [TEXTS["name"], TEXTS["furigana"], TEXTS["profile"], TEXTS["title"],
            SKILL_NAME_1, SKILL_DESC_1, SKILL_NAME_2, SKILL_DESC_2, "(None)", "(None)", TEXTS["leader"], TEXTS["cv"]]
    if design is not None:
        want = list(design["text"]["character_text_row"])
        want[5], want[7] = SKILL_DESC_1, SKILL_DESC_2       # R22：技能说明压缩，其余 10 格仍对设计定稿
        if want != trow:
            raise AssertionError("character_text row differs from design (c5/c7 已按改版方案放行)")
    if desc_lock is not None and [trow[5], trow[7]] != [desc_lock["c5"], desc_lock["c7"]]:
        raise AssertionError("character_text c5/c7 differ from revision text lock")
    ctx.write_flat(TEXT, {CID: [trow]})
    mirrors = ctx.sync_character_mirrors()

    # ---- 6 特效族克隆（sibling）+ 染色
    fx_map, fx_manifest = _load_fx_manifest(ctx.root)
    body_lut = (design or {}).get("pixel_palette", {}).get("body_lut") or {}
    recolor_log: list[dict] = []
    families = {}
    for fam in (FX_WAVE, FX_BARRIER):
        families[fam["subdir"]] = ctx.clone_effect_family(
            fam["src_dir"], fam["subdir"], fx_names=fam["fx_names"], layout="sibling",
            png_transform=make_png_transform(ctx, fam, fx_map, recolor_log, body_lut))
        missing = families[fam["subdir"]]["missing_effects"]
        if missing:
            raise AssertionError(f"effect family {fam['src_dir']} missing {missing}")
    # R27（第四轮）：克隆之后立刻补 timeline/parts 的 start-loop-end（不接这一步，每次 --step kit 都会还原成母本）
    fx_lifecycle = repair_fx_lifecycle(ctx, ctx.pack)
    notes.append(f"特效生命周期补段（R27）：改写 {len(fx_lifecycle['patched'])} 份"
                 f"（attack timeline start/loop/end、player parts 渐隐尾 + timeline end）")

    # ---- 7 两棵技能树
    official_sig_cache = ctx.root / BATCH / "impl" / KEY / "official_dsl_signatures.json"
    try:
        official_signatures = official_signature_set(ctx, official_sig_cache)
    except Exception as exc:                          # 基线不可用时门禁判失败，不静默通过
        official_signatures = None
        notes.append(f"official signature set unavailable: {type(exc).__name__}: {exc}")
    trees, tree_reports = {}, {}
    for level in ("1", "2"):
        tree = compose_tree(ctx.template_dsl, level)
        rewrites = {}
        for sub, fam in families.items():
            tree, info = ctx.rewrite_effect_refs(tree, fam, strict=True)
            rewrites[sub] = info
        if design is not None:
            want = copy.deepcopy(design["skills"][f"tree_plan_{level}"]["composed_tree"])
            apply_skill_edits(want)                       # 设计定稿树 + R18/R19/R20/R21 + R25 算子
            apply_orbit_edits(want, level)                # + R26 旋转环算子
            apply_fx_lifecycle_edits(want)                # + R27 特效生命周期算子 = 本轮成品
            for sub_name, fam in families.items():
                want, _ = ctx.rewrite_effect_refs(want, fam, strict=True)
            if tree != want:
                raise AssertionError(f"composed tree {level} differs from design composed_tree + revision ops")
        from wf_yuki_leader_anchor import revise_skill as leader_anchor
        tree = leader_anchor(tree)
        ctx.write_dsl(ctx.program_path(level), tree)
        logical = f"{ctx.program_path(level)}.action.dsl.amf3.deflate"
        back = ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
        report = tree_gates(tree, official_signatures)
        report["package_readback_equal"] = [] if back == tree else ["package DSL bytes do not parse back to tree"]
        # 锚点断言只对本角色的树成立（tree_gates 会被官方母本树当正控复用，不能放进去）
        report["barrier_anchor"] = anchor_problems(tree)
        report["_info"]["barrier_anchor"] = barrier_anchor(tree)
        # R26：结界环每击倍率已按命中次数摊薄，面板合计 = 环每击 × 实得命中数 + 纵向冲击
        report["orbit"] = orbit_problems(tree, level)
        # R27：特效生命周期（外圈单发跟随判定区 + 中心圈同寿命）另开一条，失败原因才不会被 orbit 那一堆淹掉
        report["fx_lifecycle"] = fx_lifecycle_problems(tree)
        totals = skill_totals(tree, level)
        report["_info"]["skill_totals"] = totals
        report["_info"]["orbit"] = {"rotation": orbit_rotation(), "hit_schedule": orbit_hit_schedule(),
                                    "coverage": orbit_coverage()}
        lo, hi = EXPECTED_MULT[level]
        if totals["mult"] != [lo, hi]:
            report["multiplier_plan"] = [f"合计倍率 {totals['mult']}（环 {totals['ring_per_hit']['mult']} × "
                                         f"{totals['ring_hits']} + 冲击 {totals['column_per_hit']['mult']}）"
                                         f" != 面板 {lo}/{hi}"]
        else:
            report["multiplier_plan"] = []
        report["_info"]["effect_rewrites"] = rewrites
        trees[f"skill_{level}"] = tree
        tree_reports[f"skill_{level}"] = report

    # ---- 8 门禁
    rows_report = package_row_report(ctx)
    effects = resolve_effect_refs(ctx, trees)
    recolor_problems = fx_recolor_problems(ctx, fx_map, fx_manifest, recolor_log)
    provenance_problems = template_provenance_problems(ctx)
    png_storage_problems, png_checked = package_png_storage_problems(ctx.pack.package)
    gate_failures = (list(rows_report["problems"]) + list(effects["problems"])
                     + recolor_problems + provenance_problems + png_storage_problems)
    for label, rep in tree_reports.items():
        for gk, value in rep.items():
            if not gk.startswith("_") and value:
                gate_failures.extend(f"{label} {gk}: {p}" for p in value)
    if rows_report["required_capabilities"]:
        gate_failures.append(f"rows need client capabilities {rows_report['required_capabilities']} "
                             "but design declares none")
    if rows_report["required_capabilities"] != list(spec.required_capabilities):
        gate_failures.append(f"spec.required_capabilities {list(spec.required_capabilities)} != rows "
                             f"{rows_report['required_capabilities']}")
    if revision is not None:
        want_counts = record_counts_lock(revision, revision5)
        want_counts[f"{CID}2"] += 1
        got_counts = {"leader": len(leader), **{k: len(v) for k, v in abilities.items()}}
        if got_counts != want_counts:
            gate_failures.append(f"record counts {got_counts} != revision plan {want_counts}")
        locked = _locked_rows(revision, revision5)
        locked[f"{CID}2"] = yuki_rows(locked[f"{CID}2"])
        drift = ([f"leader#{i}" for i, r in enumerate(leader)
                  if locked["leader"][i] is not None and r != locked["leader"][i]]
                 + [f"{k}#{i}" for k, rows in abilities.items()
                    for i, r in enumerate(rows)
                    if locked[k][i] is not None and r != locked[k][i]])
        if drift:
            gate_failures.append(f"rows differ from revision plan locked rows: {drift[:6]}")
    fx_manifest_sha = (hashlib.sha256(Path(fx_manifest).read_bytes()).hexdigest() if fx_manifest else None)
    gates = {"kit_static": {"passed": not gate_failures, "failures": gate_failures},
             "rows": rows_report, "trees": tree_reports, "effects": effects,
             "recolor": recolor_log, "recolor_problems": recolor_problems,
             "template_provenance_problems": provenance_problems,
             "png_storage_signature": {"checked": png_checked, "problems": png_storage_problems},
             "fx_manifest": fx_manifest, "fx_manifest_sha256": fx_manifest_sha,
             "fx_lifecycle": fx_lifecycle}
    ctx.evidence_write("kit-gates.json", gates)
    ctx.evidence_write("kit-rows-describe.json",
                       [{k: r[k] for k in ("table", "key", "line", "describe")} for r in rows_report["rows"]])

    programs = sorted(f"{ctx.program_path(lv)}.action.dsl.amf3.deflate" for lv in ("1", "2"))
    status = "ready-for-review" if not gate_failures else "draft"
    ctx.report({
        "summary": ("见岛勇希·泳装 129991 kit（20260916 改版）：队长 7 行 + 词条 15 条、结界弹朝周围 6 方向+纵向冲击"
                    "两档（24×/34×，连击增伤）、水共鸣 ChangeSkillFlag 连击加成分支与语音路由、两个冰蓝特效族克隆"),
        "status": status,
        "skills": {"programs": programs},
        "unique_condition": {},
        "required_capabilities": rows_report["required_capabilities"],
        "panel": [f"{r['table']} {r['key']}#{r['line']}: {r['describe']}" for r in rows_report["rows"]],
        "notes": notes + [
            "PF 覆盖/422/724/desc_override/unique_condition：设计不使用",
            ("custom_ability_power_up_string：不写。CustomAbilityPowerUpStringTools.resolveDescriptionPowerLevel "
             "缺键返回 1，AbilityDescriptionStringfier_Impl_.addChangeSkillAbilityPower 在等级≤1 时不读 power_up 表；"
             "536 面板正文只取主表（AbilityDescriptionGenerator.as:8531）。在线 536 先例 1299923/1699891/1499891/1499901 同样只写主表（1199891 另有 power_up 键）"),
            f"特效染色：{'fx manifest ' + fx_manifest if fx_manifest else 'kit 保守回退染色（待 Effects 阶段 fx/yuki/out/manifest.json 覆盖）'}",
            ("像素小人 sheet 与语音不在 kit 范围（Integrate 阶段装包）。像素 sheet 用 install_pixel_sheets(ctx) 装："
             "标准魔数转 WF 存储魔数、尺寸/atlas/alpha 核对、登记 owner=pixel；包内 PNG 存储魔数由 kit 门禁 "
             "png_storage_signature 复核（flow preflight 另有 validate_manifest 同口径拦截）"),
            "见 evidence/kit-gates.json；包级 master_reference 以 --step inspect 为准",
        ],
        "gate_failures": gate_failures,
    })
    return {"status": status, "gate_failures": gate_failures[:20], "notes": notes,
            "rows": {"leader": len(leader), "abilities": sum(len(v) for v in abilities.values())},
            "programs": programs, "effect_families": {k: v["dst_dir"] for k, v in families.items()},
            "recolor": recolor_log, "mirror_character_c9_16": mirrors["character"][9:17]}

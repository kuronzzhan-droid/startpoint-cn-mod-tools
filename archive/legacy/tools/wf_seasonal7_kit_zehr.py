# -*- coding: utf-8 -*-
"""季节换装七角色 kit：泽赫尔·灯火酒馆 159997 ``guildknight_leader_tavern``（设计定稿 design/zehr.json）。

由 ``python mod-tools/wf_seasonal7_build.py --char zehr --step kit`` 调用 :func:`build`。
只写 ``work/character_packs/s7-zehr/``（经 KitContext）；live store / assets / .cdn / src / APK 只读。

2026-09-27 平衡调整第二批：:func:`build` 在 09-17 灯火修订（``wf_zehr_lamp_revision`` 纯函数）之后再套
``wf_balance_20260927b_zehr.balance_rows`` / ``panel_texts``（队长 #3 #4 放缓、灯芯 / 灯火正旺成长搬进队长
#6–#8、能力1/3 限次；队长覆盖文案以 09-17 ``wf_seasonal_pf_revision.ZEHR_LEADER_TEXT`` 为底稿），
重建不回退该批改动。随后套第三轮 ``wf_balance_20260927c_zehr.leader_rows`` / ``leader_text``（队长 #3 #4 #6 #7 #8
成长回调到原值 2/3–7/10，队长覆盖文案四处数字同步；L1 / L7 按主会话口径 1 把「、强化弹射伤害」改「，强化弹射伤害」）
与 ``ability6_text``（能力6 两行同条件合并为一行）。
下方各轮常量与门禁仍描述改版计划那一层，不含 09-17 之后的收口。

2026-09-16 第四轮作者改版（revision3-20260916 续）：作者原话「能力 3 的 50% 降到 30%、灯芯每层 5% 降到 3%」
（= 上一轮 ``timing.md``「如果要收一点」的第 1、2 档）。声明式增量见 :data:`REV4_VALUE_ROWS` /
:data:`REV4_KEEP_ROWS` / :data:`REV4_TEXT_REWRITES` 一段注释：能力3#0/#3 的数值列 50000→30000、
能力1#5（灯芯乘区）113/114 列 5000→3000、面板两处数字随之改写（百分数由数值列常量推出）。
节奏（CT 5 秒 / 灯火正旺 12 秒）与机制一格未动。

2026-09-16 第三轮作者改版（revision3-20260916）：作者原话「灯火正旺效果延长到12s,ct改为5s」。声明式增量见
:data:`UC_LAMP_FRAMES` / :data:`CT_LAMP_FRAMES` / :data:`REV3_CT_ROWS` / :data:`REV3_TEXT_REWRITES` 一段注释：
固有 159997「灯火正旺」600→720 帧、本角色全部四行 CT600（能力1#3/#4 发放行 + 能力3#0/#3 受益行）600→300 帧、
面板两处节奏文案随之改写（秒数由帧常量推出，不会与表脱节）。机制副作用（叠层翻倍 / 状态可常驻）另见
``revision3-20260916/zehr/timing.md``。

2026-09-16 第二轮作者改版（revision2-20260916）叠在第一轮之上，声明式增量见 :data:`REV2_MAIN_SLOT_SLOTS` /
:data:`REV2_TEXT_REWRITES` 一段注释：**能力 1/3/5 主位限制**（整键 c1='false'，不加前置 202 以免双 Ⓜ；
有覆盖文案的键逐行补 ``<icon id='main'>``，能力 5 无覆盖文案由客户端自动画）＋**文案规则①②**
（面板不再出现「无上限」；能力里的「技能强化」条目只写强化了什么，不写数值与秒数）。规则原文见
``revision2-20260916/文案规则-补充.md``；机制一格未动。

2026-09-16 作者改版（真机试玩后）：行 / 覆盖文案 / 固有状态 / 技能 ALv 通道以
``work/character_packs/seasonal7-20260916/revision-20260916/zehr/plan.json`` 为唯一来源；
``design/zehr.json`` 降级为「上一轮基线」，仍提供语音路由、技能能量、两棵技能定稿树、三棵 PF 定稿树、
722 文案与不变的 power_up 字节。技能树先合成到与上一轮定稿树逐节点相同，再落改版的两处 ALv 编辑。

落地内容（以改版计划 + 设计 JSON 为准，逐项断言；主控拍板的覆盖见 ``OVERRIDES``）：
- character 行 c9–c16 语音路由（ConditionExist + Unique 159997）、c18 队长名；character_text 12 列
  （c5/c7 换成改版后的短技能说明）；三层镜像；
- 队长 6 行、词条 6 键 20 条：donor（官方基线 / live；live 行号会被别的单元改掉的钉成冻结行，
  见 :data:`FROZEN_DONORS`）+ 声明编辑重建，与计划 ``row`` 逐格核对；
  「无上限」一律写字面量 ``(None)``（空串会被 Std.parseInt 吃成 0 次）；
- unique_condition 159997「灯火正旺」+ 1599971「灯芯」（99 层永续）+ 两张 48×48 官方风固有图标
  （kit 绘制，WF 小写魔数）；
- custom_ability_string 7 键（队长 + 能力 1/2/3/6 覆盖文案、536 强化说明、722 说明）
  + custom_ability_power_up_string 1 键（官方原行字节）；
- action_skill 两档（名称/改版后的短描述/能量 c4–c6/DSL 路径）；两棵技能 DSL（官方 151069 骨架 + 助战技 5 发光弹 +
  浮游/全队 PF 伤害，移植 design/_tmp/zehr/c8_final_build.py），与设计定稿树逐节点严格比对后再落改版 ALv 编辑
  （ACAttackPoint / ACPowerFlipDamage 的 alv_min/alv_max，使 536 强化态合计 250%）；
- 722 双形态 PF：power_flip_action 新键 + 三档 DSL（APK 内官方 knight/supporter 经
  ``wf_gerald_native_pf_dsl.compose`` 组合），**每段倍率恢复官方 3.25/4.75/6.3**，寿命/命中/Notify ×3，
  suppress 保持官方；在 spin 之外叠一层新演出（官方火光族 ``master_knight_blaze`` 克隆到
  ``skill_unique/<code>/pf_blaze/``，染暖金暗红，timeline sounds 清空；与 Effects 阶段推荐族一致）；
  满命中预算（剑士段恰为官方 3 倍，Lv3 含辅助全屏合计约 2.77 倍；削韧约 1.5 倍、Fever 持平）写入报告；
  程序路径用 ``override/<code>_pf$<code>_pf_lvN``（设计长路径在框架 inspect 副本里超 MAX_PATH），键不变；
- 4 个特效族克隆（layout=codename）+ kit 默认染色；若 ``seasonal7-20260916/fx/zehr/out/manifest.json`` 存在，
  按其 {源 sheet 逻辑路径 → 染色 PNG} 替换对应 sheet；
- switched_action_skill ``guildknight_leader_tavern_voice_ready`` 两档（= action_skill c7–c23，
  与 ``wf_seasonal7_voice.switched_rows`` 同约定）。
- 像素小人（Integrate）：``seasonal7-20260916/pixel/zehr/out/{sprite_sheet,special_sprite_sheet}.png``
  在 report 门禁全过、``pixel/_review/verify_all.json`` 复核全过且 sha 一致时，以存储态写入
  ``character/<code>/pixelart/``（owner=pixel），写后核对尺寸/alpha = 母本、元数据 = 母本（仅路径前缀）；
  未就绪时 pending、保持母本原色。语音由 ``wf_seasonal7_voice pack`` + ``impl/zehr/voice_merge.py`` 装包，
  kit 只读 ``voice_state``；像素 / 语音字节计入 kit 指纹（换了必须重跑门禁）。

kit-report 的 ``status``：只有 ``impl/zehr/gates.json`` 全过且其 ``kit_fingerprint`` 与本次产物指纹一致时
才写 ``ready-for-review``，否则 ``draft``（门禁脚本 ``impl/zehr/gates.py``）。

未跟踪输入（``work/`` 被 gitignore；build 开头由 :func:`required_input_problems` 统一核对并报清单）：
``design/zehr.json``、``revision-20260916/zehr/plan.json``、
``design/_tmp/zehr/final_skill_{1,2}.json``、``final_pf_lv{1,2,3}.json``、
官方 DSL 参数形状表 ``official_sig.json``（``impl/zehr/`` 自有副本优先，``research/_tmp/`` 原件回退，均按 sha 锁定）。
DSL 静态校验 ``blueprint_check_with_sig`` 移植自 ``research/_tmp/blueprint_build.py``，运行时不再 import 研究目录。
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import sys
import zipfile
import zlib
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

KEY = "zehr"
CID = "159997"
CODE = "guildknight_leader_tavern"
TEMPLATE_CODE = "guildknight_leader"
ELEMENT = 4
BATCH = "work/character_packs/seasonal7-20260916"
DESIGN_REL = f"{BATCH}/design/zehr.json"
DESIGN_TMP_REL = f"{BATCH}/design/_tmp/zehr"
FX_MANIFEST_REL = f"{BATCH}/fx/zehr/out/manifest.json"
GATES_REL = f"{BATCH}/impl/zehr/gates.json"
# 官方全库 DSL 参数形状表（research/_tmp/official_sig.py 生成，751 条）。kit 自有副本放 impl/zehr/，
# 研究目录原件只作回退；两处都按 sha 锁定，缺失/漂移时报清单而不是在深处 ImportError。
OFFICIAL_SIG_PIN = "2383feedc25dde84a19fc19ac2c89a0847768098bd261277ccaced73bdc094c5"
OFFICIAL_SIG_CANDIDATES = (f"{BATCH}/impl/zehr/official_sig.json", f"{BATCH}/research/_tmp/official_sig.json")
DESIGN_BLUEPRINT_REL = f"{BATCH}/research/_tmp/blueprint_build.py"      # 只供单测做移植等价核对，运行时不 import

CHAR = "master/character/character.orderedmap"
TEXT = "master/character/character_text.orderedmap"
ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
CAPS = "master/string/custom_ability_power_up_string.orderedmap"
UC = "master/character/unique_condition.orderedmap"
PFA = "master/skill/power_flip_action.orderedmap"
ACTION = "master/skill/action_skill.orderedmap"
SW = "master/skill/switched_action_skill.orderedmap"

VOICE_KEY = f"{CODE}_voice_ready"
PF_KEY = f"override_{CODE}_dual_pf"
PF_STRING_KEY = f"override_string_{CODE}_dual_pf"
CHANGE_SKILL_KEY = f"change_skill_{CODE}"
LEADER_OVERRIDE_KEY = f"desc_override_{CODE}"
OVERRIDE_SLOTS = (1, 2, 3, 6)                       # 改版后有覆盖文案的词条槽
SLOT_OVERRIDE_KEYS = tuple(f"desc_override_{CODE}_{s}" for s in OVERRIDE_SLOTS)
SLOT3_OVERRIDE_KEY = f"desc_override_{CODE}_3"
CAS_KEYS = (PF_STRING_KEY, CHANGE_SKILL_KEY, LEADER_OVERRIDE_KEY) + SLOT_OVERRIDE_KEYS
UC_ID = "159997"                                    # 「灯火正旺」（第三轮改为 12 秒 / 1 层）
UC_ID2 = "1599971"                                  # 「灯芯」（永续 / 99 层，改版新增，承载可成长的 PF 独立乘区）
UC_ICON = f"battle/common/unique_condition/unique_{CODE}_lamp.png"
UC2_ICON = f"battle/common/unique_condition/unique_{CODE}_wick.png"
UC_IDS = (UC_ID, UC_ID2)
UC_ICONS = {UC_ID: UC_ICON, UC_ID2: UC2_ICON}
FPS = 60                                            # 战斗帧率：面板秒数 = 帧 / 60
CT_LAMP_FRAMES_REV2 = 600                           # 上一轮：「≥50 连击弹射」四行 CT = 10 秒
CT_LAMP_FRAMES = 300                                # 第三轮（作者「ct改为5s」）：同四行 CT = 5 秒
UC_LAMP_FRAMES_REV2 = 600                           # 上一轮：「灯火正旺」10 秒
UC_LAMP_FRAMES = 720                                # 第三轮（作者「灯火正旺效果延长到12s」）：12 秒
CT_SECONDS = CT_LAMP_FRAMES // FPS                  # 5
LAMP_SECONDS = UC_LAMP_FRAMES // FPS                # 12
# 第四轮（作者「能力 3 的 50% 降到 30%、灯芯每层 5% 降到 3%」）：数值列与面板百分数同源，
# 面板写的数字由这几个常量除以刻度推出来，改了表面板必须跟着改（反之残留旧数字当场报红）。
PCT_SCALE = 1000                                    # 词条数值列的百分比刻度：50000 = 50%
A3_LAMP_GAIN_REV3 = 50000                           # 上一轮：能力3「每获得1次灯火正旺」两行各 +50%
A3_LAMP_GAIN = 30000                                # 第四轮：+30%
A1_WICK_MULT_REV3 = 5000                            # 上一轮：能力1「每 1 层灯芯」PF 独立乘区 +5%
A1_WICK_MULT = 3000                                 # 第四轮：+3%
A3_LAMP_GAIN_PCT = A3_LAMP_GAIN // PCT_SCALE                # 30
A3_LAMP_GAIN_PCT_REV3 = A3_LAMP_GAIN_REV3 // PCT_SCALE      # 50
A1_WICK_MULT_PCT = A1_WICK_MULT // PCT_SCALE                # 3
A1_WICK_MULT_PCT_REV3 = A1_WICK_MULT_REV3 // PCT_SCALE      # 5
CAPABILITIES = ("dash-parameter-v1", "panel-description-override-v2")
# 覆盖文案禁词（记忆卡 wf-leader-override-text-rules / wf-no-hplow-text-discipline
# + 作者 2026-09-16 晚文案规则①：面板不再出现「无上限」，也不许换成「可无限叠加」之类的替代说法）
FORBIDDEN_PANEL_WORDS = ("自身为队长时", "觉醒后", "生命值100%以下", "HP100%以下", "null",
                         "无上限", "无限叠加", "不设上限", "可无限")

# ---- 2026-09-16 审查修复轮的三条锁（详见 revision-20260916/zehr/fix-log.md）
# R1：作者原文这一段只在能力2 写了「自身为队长时」。50 连击触发的四行不许再带 pre42（队长门），
#     否则面板（不写队长条件）与数据不一致，且能力1 在合击位上会有三行是死行。
NO_LEADER_GATE_ROWS = ((f"{CID}1", 3), (f"{CID}1", 4), (f"{CID}3", 0), (f"{CID}3", 3))
LEADER_GATE_ROWS = ((f"{CID}2", 0), (f"{CID}2", 1))
# R3：CT（每 N 秒 1 次）与「灯芯」99 层封顶是**真上限**，必须写进面板（文案规则①：有上限的才写上限）。
# 第三轮：秒数由 CT_LAMP_FRAMES / UC_LAMP_FRAMES 推出来，面板与表里的帧数不可能各说各话。
# 第四轮：两处百分数同样由数值列常量推出来（A3_LAMP_GAIN / A1_WICK_MULT ÷ PCT_SCALE）。
PANEL_REQUIRED_PHRASES = {
    f"desc_override_{CODE}_1": (f"（每{CT_SECONDS}秒1次）", "最多99层", f"「灯火正旺」{LAMP_SECONDS}秒",
                                f"强化弹射伤害额外乘区＋{A1_WICK_MULT_PCT}%"),
    f"desc_override_{CODE}_3": (f"每{CT_SECONDS}秒1次",
                                f"光属性角色攻击力＋{A3_LAMP_GAIN_PCT}%、"
                                f"强化弹射伤害＋{A3_LAMP_GAIN_PCT}%"),
}
# R6：kind 55 / 696 / 413 是战斗（小队）级，不读 target 列，面板不许写成「自身强化弹射伤害」。
#     2026-09-27 第三轮（主会话口径 1）：也不许用「、」把它接在带对象的效果后面（会读成同一对象），写「，强化弹射伤害」。
#     队长覆盖文案的这把锁在 ``wf_balance_20260927c_zehr.problems``（第三轮收口送检）；改版计划层的队长底稿仍是
#     「、」写法，由 ``leader_text`` 在第三轮改掉，所以不放进下面的 PANEL_FORBIDDEN_PHRASES（那里检的是计划层文本）。
# 第三轮：两条覆盖文案里不许再留上一轮的节奏（10 秒）——CT 与状态时长都变了。
# 第四轮：这两条覆盖文案里不许再留上一轮的强度数字。**只按键禁**：别的键里的「＋50%」是别的效果
#        （能力1#1 开局技能槽、能力2 / 能力6 / 队长的强化弹射伤害），一刀切全局禁会误伤。
REV3_STALE_TIMING = ("10秒",)
REV4_STALE_NUMBERS = {
    f"desc_override_{CODE}_1": (f"强化弹射伤害额外乘区＋{A1_WICK_MULT_PCT_REV3}%",),
    f"desc_override_{CODE}_3": (f"光属性角色攻击力＋{A3_LAMP_GAIN_PCT_REV3}%",
                                f"强化弹射伤害＋{A3_LAMP_GAIN_PCT_REV3}%"),
}
PANEL_FORBIDDEN_PHRASES = {
    f"desc_override_{CODE}": ("自身强化弹射伤害",),
    f"desc_override_{CODE}_1": REV3_STALE_TIMING + REV4_STALE_NUMBERS[f"desc_override_{CODE}_1"],
    f"desc_override_{CODE}_3": REV3_STALE_TIMING + REV4_STALE_NUMBERS[f"desc_override_{CODE}_3"],
}
# R5：技能说明精简后仍须提到能力1 面板里点名的「攻击力提升效果」。
SKILL_DESC_REQUIRED = ("攻击力提升效果", "强化弹射伤害提升效果")

# ─────────── 第二轮作者改版（2026-09-16 晚，revision2-20260916）：声明式增量叠在 plan.json 上 ───────────
#
# plan.json 在第一轮证据目录 revision-20260916/ 下，本轮不可写，所以第二轮的改动写成增量：
# 先照常「donor + edits 重放 == plan row」，再叠下面两处，且只准改到声明的那一列 / 那几段文字。
#
# T1 作者原话「泽赫尔的能力1和3和5带上主位限制」：主位限制 = 整键 values[0] 的 c1='false'
#    （``AbilityLogic.get_unisonable()`` 只读 values[0]；本 kit 另要求同键 c1 一致 ⇒ 键内每条同改）。
#    **不加前置 202**：c1=false 与 202 同键双写会画两个 Ⓜ（记忆卡 wf-unison-slot-mechanics）；
#    护栏查 ``ABILITY_PRECONDITION_BLOCKS`` 三个前置槽（c6/c13/c20），不是只查 precondition1。
#    能力3 上一轮就是 false（422 冲刺行本来就是主位），本轮它只补面板 Ⓜ；能力1/5 是本轮新加。
#    面板 Ⓜ 本由客户端逐行画（``AbilityDescriptionTools.stringfyUnisonable`` →
#    ``ability_description_not_unisonable_icon``），但 desc_override 把整段文字换掉了 ⇒ **有覆盖文案的
#    主位键必须把 ``<icon id='main'>`` 写进文本**（官方同写法：``wf_featured_main_ability.main_description``、
#    live 先例 scutum_valentine / *_campus）。能力5 没有覆盖文案，Ⓜ 由客户端自动画。
# T2 文案规则（``revision2-20260916/文案规则-补充.md``，优先级高于此前写法）：
#    ① 没有上限就什么都不写——删掉「（无上限）」，句子写到效果为止，也不换成「可无限叠加」之类说法；
#       机制不动（灯芯仍是 99 层、触发上限仍是 (None)）。**有上限的照写上限**：CT「每10秒1次」、
#       「灯芯」99 层封顶都是真上限，保留（PANEL_REQUIRED_PHRASES 钉死）。
#    ② 能力里的「技能强化」条目（ChangeSkillFlag 536/704）只写强化了什么，不写数值与秒数：
#       能力1 第 3 行改成与 ``change_skill_*`` 主文案同形的「强化『<技能名>』的「<效果名>」…」。
REVISION2_DIR = f"{BATCH}/revision2-20260916/zehr"
REVISION2_RULES_REL = f"{BATCH}/revision2-20260916/文案规则-补充.md"
MAIN_ICON = " <icon id='main'>  "
REV2_MAIN_SLOT_SLOTS = (1, 3, 5)                    # 主位限制的词条槽（3 是上一轮就有的，1/5 本轮新加）
REV2_MAIN_SLOT_KEYS = tuple(f"{CID}{s}" for s in REV2_MAIN_SLOT_SLOTS)
SLOT_CAS_KEY = {s: f"desc_override_{CODE}_{s}" for s in OVERRIDE_SLOTS}
REV2_MAIN_ICON_KEYS = tuple(SLOT_CAS_KEY[s] for s in REV2_MAIN_SLOT_SLOTS if s in SLOT_CAS_KEY)
REV2_TEXT_DROPS = ("（无上限）",)                     # 规则①：整段删掉，不替换成别的说法
REV2_TEXT_REWRITES = {                              # 先做改写再做删除（第 3 槽那段两条规则都沾）
    SLOT3_OVERRIDE_KEY: (("（每10秒1次，无上限）", "（每10秒1次）"),),
    f"desc_override_{CODE}_1": (
        ("光属性共鸣时，强化「白银一闪·打烊时刻」：攻击力提升效果＋250%、强化弹射伤害提升效果＋250%",
         "光属性共鸣时，强化『白银一闪·打烊时刻』的「攻击力提升效果」与「强化弹射伤害提升效果」"),),
}
# ability 布局的**三个**前置槽 kind 列（mod-tools/ability_enum_map.json:layouts.ability.blocks）。
# 只盯 precondition1 会漏：live 全库确有 202 落在 c13 / c20 的写法，而「c1=false 不加 202」是本轮 T1
# 防双 Ⓜ 的唯一护栏，三个槽必须一起查（审查复现修复，2026-09-16 晚）。
ABILITY_PRECONDITION_BLOCKS = (6, 13, 20)
PRE_OWNER_IS_MAIN = "202"                           # AbilityPrecondition OwnerIsMain（主位限制的前置写法）
SKILL_FLAG_KINDS = ("536", "704")                   # ChangeSkillFlag：规则②针对的「技能强化」条目
ENHANCE_TEXT_MARK = "强化『"                          # 技能强化条目的句式标记（技能名用 『』 括）
ENHANCE_TEXT_FORBIDDEN = tuple("0123456789０１２３４５６７８９") + ("秒", "%", "％", "倍")

# ─────────── 第三轮作者改版（2026-09-16 夜，revision3-20260916）：节奏调整，再叠一层增量 ───────────
#
# 作者原话：「灯火正旺效果延长到12s,ct改为5s」。落成两处数值 + 随之而来的面板文案：
#  T3-a 固有 159997「灯火正旺」duration_frame（unique_condition c3）600 → 720 帧（10 → 12 秒）。
#  T3-b 面板写「（每10秒1次）」的那些行 = 本角色**全部** c35=600 的词条行（``REV3_CT_ROWS`` 四行）→ 300 帧（5 秒）。
#       这四行同触发（kind 13 弹射 + 连击≥50，c30/c31=5000000），CT 各自独立计时但条件相同，
#       只改其中一部分会让「发放灯火正旺 / 累积灯芯」与能力3 的两条收益行**错拍**
#       （当时那两条是 +50%，第四轮已降到 +30%，节奏仍同拍），所以必须整组改。
#       其余 c35 取值：能力2 两行、能力3#5、能力5#1 都是 ``'0'``（无 CT，不属于作者说的那组）；
#       队长表 CT 列 c33/c91 全为空或 '0'（``LEADER_CT_BLOCKS`` 扫描钉死），本轮不动。
#       ``apply_rev3_cooldown`` 对**不在名单里却写着 600** 的行直接报错 ⇒ 将来有人加 CT 行必须重新逐条判断。
#  T3-c 文案：规则①②不变，只把节奏数字改对——能力1「…「灯火正旺」12秒…（每5秒1次）」、
#       能力3「…（每5秒1次）」；``PANEL_REQUIRED_PHRASES`` / ``REV3_STALE_TIMING`` 两头钉死，
#       面板秒数与帧数常量同源，不会再各说各话。
#  副作用（叠层速度翻倍 / 灯火正旺可常驻）写在 ``revision3-20260916/zehr/timing.md``，供作者判断强度。
REVISION3_DIR = f"{BATCH}/revision3-20260916/zehr"
REV3_CT_ROWS = ((f"{CID}1", 3), (f"{CID}1", 4), (f"{CID}3", 0), (f"{CID}3", 3))
LEADER_CT_BLOCKS = (33, 91)                         # leader_ability 的 CT 列（记忆卡 wf-kit-round2-20260909）
REV3_TEXT_REWRITES = {                              # 在 REV2 改写之后执行（第 3 槽那段两轮都沾）
    f"desc_override_{CODE}_1": (
        ("弹射时连击达到50以上，赋予自身「灯火正旺」10秒，并累积1层「灯芯」（每10秒1次）",
         f"弹射时连击达到50以上，赋予自身「灯火正旺」{LAMP_SECONDS}秒，"
         f"并累积1层「灯芯」（每{CT_SECONDS}秒1次）"),),
    SLOT3_OVERRIDE_KEY: (("（每10秒1次）", f"（每{CT_SECONDS}秒1次）"),),
}

# ─────────── 第四轮作者改版（2026-09-16 夜，revision3-20260916 续）：强度回调，再叠一层增量 ───────────
#
# 作者原话：「能力 3 的 50% 降到 30%、灯芯每层 5% 降到 3%」——正好是上一轮 timing.md「如果要收一点」
# 列出的第 1、2 档。落成三行的数值列 + 两处面板数字，节奏（CT 5 秒 / 灯火正旺 12 秒）与机制一格未动。
#
#  T4-a 能力3#0（kind 32，赋予全队(光)攻击力）与 #3（kind 55，强化弹射伤害）的瞬发数值列 c51/c52：
#       50000 → 30000。这两行是面板「每获得1次「灯火正旺」，…攻击力＋50%、强化弹射伤害＋50%」同一句
#       文案的两半，同触发（弹射·连击≥50，CT 5 秒），必须同改。
#  T4-b 能力1#5（during kind 413，灯芯层数 → PF 独立乘区）的持续数值列 c113/c114：5000 → 3000。
#  T4-c 面板：能力3 那句两个数字 50→30、能力1 末行 5%→3%；百分数由上面的数值常量推出。
#
# **两列同步**：c51/c52（瞬发）与 c113/c114（持续）是「词条等级低级列 / 满级列」，本角色这三行
# 原本就两列拉平（50000/50000、5000/5000），所以按满级列的缩放比例同步换算后依然拉平
# （记忆卡 wf-leader-override-text-rules：固定覆盖文案只写单值，行必须拉平，面板才不会前后不一致）。
# ``rev4_scaled_pair`` 用 Fraction 按比例缩放并要求结果是整数——将来若有人把某行写成不拉平的两列，
# 比例照旧保持，除不尽则直接报错而不是悄悄取整。
#
# **名单之外同量级的行必须显式留证**：能力1#1（kind 211「战斗开始时自身技能槽＋50%」）也是 50000，
# 但不是作者说的「能力3 的 50%」，也不是灯芯乘区 ⇒ 记在 ``REV4_KEEP_ROWS`` 里，附不动的理由；
# ``rev4_value_scan`` 每次构建重扫能力1/3 两键的四个数值列，扫出来的同量级格必须恰好等于
# 「改的三行 + 留的一行」，多一格少一格都红。
REV4_VALUE_COLS_INSTANT = (51, 52)                  # 瞬发内容 值（低级列, 满级列）
REV4_VALUE_COLS_DURING = (113, 114)                 # 持续内容 值（低级列, 满级列）
REV4_VALUE_ROWS = {
    (f"{CID}3", 0): (REV4_VALUE_COLS_INSTANT, A3_LAMP_GAIN_REV3, A3_LAMP_GAIN),
    (f"{CID}3", 3): (REV4_VALUE_COLS_INSTANT, A3_LAMP_GAIN_REV3, A3_LAMP_GAIN),
    (f"{CID}1", 5): (REV4_VALUE_COLS_DURING, A1_WICK_MULT_REV3, A1_WICK_MULT),
}
REV4_KEEP_ROWS = {
    (f"{CID}1", 1): "能力1#1 kind 211「战斗开始时，自身技能槽＋50%」：同为 50000，但它是开局技能槽，"
                    "既不是作者说的「能力3 的 50%」也不是「灯芯每层 5%」——不动",
}
REV4_SCAN_KEYS = (f"{CID}1", f"{CID}3")             # 作者点名的两键：能力1 / 能力3
REV4_SCAN_COLS = REV4_VALUE_COLS_INSTANT + REV4_VALUE_COLS_DURING
REV4_SCAN_MAGNITUDES = (str(A3_LAMP_GAIN_REV3), str(A1_WICK_MULT_REV3))
# 面板数字 ⇄ 成品行数值列的绑定：面板上写的百分数必须等于**装包那一行**的满级列 ÷ PCT_SCALE，
# 不是等于某个常量。常量写错、行改了文案没改（或反过来）都会在 ``panel_matches_row_values`` 里红。
PANEL_VALUE_BINDINGS = {
    (f"{CID}3", 0): (SLOT3_OVERRIDE_KEY, "光属性角色攻击力＋{pct}%"),
    (f"{CID}3", 3): (SLOT3_OVERRIDE_KEY, "强化弹射伤害＋{pct}%"),
    (f"{CID}1", 5): (f"desc_override_{CODE}_1", "强化弹射伤害额外乘区＋{pct}%"),
}
REV4_TEXT_REWRITES = {                              # 在 REV3 改写之后执行
    f"desc_override_{CODE}_1": (
        (f"强化弹射伤害额外乘区＋{A1_WICK_MULT_PCT_REV3}%",
         f"强化弹射伤害额外乘区＋{A1_WICK_MULT_PCT}%"),),
    SLOT3_OVERRIDE_KEY: (
        (f"光属性角色攻击力＋{A3_LAMP_GAIN_PCT_REV3}%、强化弹射伤害＋{A3_LAMP_GAIN_PCT_REV3}%",
         f"光属性角色攻击力＋{A3_LAMP_GAIN_PCT}%、强化弹射伤害＋{A3_LAMP_GAIN_PCT}%"),),
}

# 2026-09-16 作者改版（真机试玩后）：行 / 文案 / 技能 DSL 的 ALv 通道以本计划为准，
# 设计定稿 design/zehr.json 仍是「上一轮基线」，只用于 donor 回放之外的不变部分（语音路由、能量、PF 树、特效）。
REVISION_REL = f"{BATCH}/revision-20260916/zehr/plan.json"
REVISION_SCHEMA = "s7-revision-plan/1"

# 722 PF 程序路径与 power_flip_action 键解耦（live 先例：键 wind_spgirl_campus_fever → campus_celtie_fever/…）。
# 设计路径 override/<键>$<键>_lvN 在框架 inspect 副本（_inspect/zehr-<pid>/s7-zehr/…）里全长 263–265 字符，
# 超过 Windows MAX_PATH，copytree 失败；程序名改用 <code>_pf（与 149990 white_tiger_summer_pf 同形），
# 键 / 文案键 / 队长行 c80 仍按设计。
PF_PROGRAM_DIR = "battle/action/power_flip/action/override"
PF_PROGRAM_NAME = f"{CODE}_pf"
DESIGN_PF_PROGRAM = PF_PROGRAM_DIR + "/{key}${key}_lv{level}"
WIN_MAX_PATH = 259                      # MAX_PATH 260 含结尾 NUL
INSPECT_PID_DIGITS = 7                  # 框架副本目录 <key>-<pid>：按 7 位 PID 留余量


def pf_program(level: int | str) -> str:
    return f"{PF_PROGRAM_DIR}/{PF_PROGRAM_NAME}${PF_PROGRAM_NAME}_lv{level}"


def design_pf_program(level: int | str) -> str:
    return DESIGN_PF_PROGRAM.format(key=PF_KEY, level=level)
SKILL_SOURCES = {
    "guildknight_leader_1": ("battle/action/skill/action/rare5/guildknight_leader$guildknight_leader_1",
                             "32b61cfd5fec339cdf3ca07701562a49e1c03541c11ac1302601806682439ad9"),
    "guildknight_leader_2": ("battle/action/skill/action/rare5/guildknight_leader$guildknight_leader_2",
                             "268f7e6d3cb6e10d5bebd3d98f2d086f8acf873040d098b41514ea35536be903"),
    "assist": ("battle/action/skill/action/skill_invoker/zehheru_assist_skill_invoker",
               "d32ef7ea97e82206a32d039d285df8d7deb3666821b2d1b4fad6420aee9ec63a"),
    "spry_sailor_hw21_2": ("battle/action/skill/action/rare4/spry_sailor_hw21$spry_sailor_hw21_2",
                           "6679dd3701dab5387f2f2e9cf47feec4dffe52a7bbcb15d245d0ba6d337a9bcf"),
    "minamoto_sakura_2": ("battle/action/skill/action/rare5/minamoto_sakura$minamoto_sakura_2",
                          "1a7f32aa4a6d1a8085912fddbd3c89a813117e9a23d6307d6e3e105ac5b3f394"),
}

# ---- 主控拍板的覆盖（优先于设计文件）
PF_SEGMENT_MULTIPLIER = {1: 3.25, 2: 4.75, 3: 6.3}        # 官方 knight 三档每段倍率（设计原值 2.0/3.0/4.0）
DESIGN_PF_SEGMENT_MULTIPLIER = {1: 2.0, 2: 3.0, 3: 4.0}
TEXT_DROPPED_BY_OVERRIDE = "（每段伤害降低）"
# blaze loop 包围盒半宽 90px：scale 2.1/2.5/5.6 → 189/225/504px，约为 spin 2.8/3.2/5.6 屏上半宽 213/253/566px 的 0.9×
PF_BLAZE_SCALE = {1: 2.1, 2: 2.5, 3: 5.6}
PF_BLAZE_LABEL = "灯火炎光演出"
PF_BLAZE_BASE = "master_knight_blaze"
OVERRIDES = {
    "pf_segment_multiplier": "PF 三档每段倍率恢复官方 3.25/4.75/6.3；寿命/命中/NotifyPowerflipEnd ×3 与 suppress 70/90/110 保持设计",
    "pf_blaze_layer": "PF DSL 在 spin 之外叠一层 master_knight_blaze 火光（克隆到 skill_unique/<code>/pf_blaze，暖金暗红，sounds 清空，AB 不随球向旋转）",
    "texts": f"覆盖文案与 722 文案删去「{TEXT_DROPPED_BY_OVERRIDE}」（倍率已恢复官方）",
}

# PF 三档（设计 pf_override.compose.post_edits_per_level；倍率走 PF_SEGMENT_MULTIPLIER）
PF_LEVELS = {1: dict(life=210, hits=9, supp=70, wait=209, det=0.75, fev=2, atk_dur=150, pf_dur=90),
             2: dict(life=270, hits=12, supp=90, wait=269, det=1.0, fev=2, atk_dur=180, pf_dur=150),
             3: dict(life=330, hits=15, supp=110, wait=329, det=1.5, fev=3, atk_dur=240, pf_dur=240)}
PF_OFFICIAL = {1: dict(supp=70, life=70, hits=3, wait=69, mult=3.25, det=1.5, fev=6),
               2: dict(supp=90, life=90, hits=4, wait=89, mult=4.75, det=2, fev=6),
               3: dict(supp=110, life=110, hits=5, wait=109, mult=6.3, det=3, fev=8)}

# 技能两档（设计 tree_plan_1/2）
SKILL_LEVELS = {1: dict(pierce=(630, 630), fly=(630, 630), pfd_dur=(900, 900), pfd=(0.65, 0.65),
                        combo=(15, 15), slash=(24, 24), orb=(3.0, 3.0)),
                2: dict(pierce=(720, 810), fly=(720, 810), pfd_dur=(1200, 1200), pfd=(0.85, 1.0),
                        combo=(20, 25), slash=(30, 36), orb=(3.2, 3.8))}

# 特效族：(源目录, 目标子目录, 基名)
EFFECT_FAMILIES = (
    ("battle/effect/skill_unique/guildknight_leader", "skill",
     ("guildknight_leader_black", "guildknight_leader_dash", "guildknight_leader_slash",
      "guildknight_leader_hit", "guildknight_leader_hit_damage", "assist_skill")),
    ("battle/effect/powerflip/effect_powerflip_attack_spin", "pf_spin",
     ("powerflip_attack_spin_one", "powerflip_attack_spin_two", "powerflip_attack_spin_three")),
    ("battle/effect/powerflip/effect_powerflip_attack_support", "pf_support",
     ("powerflip_enhancing_support_one", "powerflip_enhancing_support_two", "powerflip_attack_support_three")),
    ("battle/effect/skill_unique/master_knight", "pf_blaze", (PF_BLAZE_BASE,)),
)
SILENT_TIMELINE_FAMILIES = ("pf_blaze",)

# 同键多记录的 c1/c2 不要求一致：官方 790 个多记录键虽无混写，live 1161 个多记录键里有 152 个混写
# （含已上线 1499993 杰拉德 special/attack_common/power_flip/attack_white、1699991 基诺维 c1 true/false），
# c2 只需属于 ability_statue_group 25 键（wf_client_legality 已查）。行一律按设计逐格落地，混写只记入报告。

TEXTS = {
    "name": "泽赫尔",
    "furigana": "ZEHEER",
    "title": "灯火酒馆的团长",
    "profile": "公会骑士团团长泽赫尔难得的休假之夜。卸下铠甲，只穿一件敞开的白衬衣、围上暗红领巾，提着灯走进常去的酒馆。"
               "嘴上说着今晚不谈工作，那把金蓝长剑却始终靠在手边。",
    "leader": "今晚由团长买单",
    "skill1": "白银一闪·打烊时刻",
    # 改版：作者要求「角色技能描述不再写太复杂省略一下」，两档同文压到 70 字（texts.action_skill_desc.new）。
    # 审查修复轮补回「赋予自身攻击力提升效果」：能力1 面板写「攻击力提升效果＋250%」，技能说明不提它玩家无从对应。
    "desc1": "对最近的敌人使出白银闪击，随后放出5发灯火光弹，造成光属性伤害／赋予自身攻击力提升效果／"
             "赋予己方贯穿、浮游和强化弹射伤害提升效果／增加连击数",
    "skill2": "白银一闪·打烊时刻＋",
    "desc2": "对最近的敌人使出白银闪击，随后放出5发灯火光弹，造成光属性伤害／赋予自身攻击力提升效果／"
             "赋予己方贯穿、浮游和强化弹射伤害提升效果／增加连击数",
    "cv": "AI 合成配音",
}
# 上一轮（design/zehr.json）的技能描述：check_texts_constant 用它确认设计文件仍是改版前的基线
DESIGN_SKILL_DESC = ("向距离最近的敌人使出白银闪击，对接触到的敌人造成光属性伤害／赋予自身攻击力提升效果／"
                     "赋予己方贯穿、浮游、强化弹射伤害提升效果／增加连击数／随后5次对距离最近的敌人放出灯火光弹，"
                     "造成光属性伤害")

SPEC = {
    "required_capabilities": CAPABILITIES,
    "extra_keys": {
        CAS: CAS_KEYS,
        CAPS: (CHANGE_SKILL_KEY,),
        UC: UC_IDS,
        PFA: (PF_KEY,),
        SW: (VOICE_KEY,),
    },
}


class KitError(RuntimeError):
    pass


# ---------------------------------------------------------------- 通用小工具

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def slv(a, b=None, *, alv_min=None, alv_max=None) -> list[dict]:
    """SLv 值数组。``alv_min/alv_max`` 是 ChangeSkillFlag(536) 槽 1 的强化增量，与基值**相加**
    （FixedSLvValueResolver.as:75-118、:369）；两者要么都给要么都不给（官方写法）。"""
    cell = {"min": a, "max": a if b is None else b}
    if (alv_min is None) != (alv_max is None):
        raise KitError("slv: alv_min/alv_max must be given together")
    if alv_min is not None:
        cell["alv_min"] = alv_min
        cell["alv_max"] = alv_max
    return [cell]


def num_equal(a: Any, b: Any) -> bool:
    """数值宽松比较（JSON 1 vs DSL 1.0），结构逐层相同。"""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(num_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(num_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def cmd(node):
    return node[1]


def strict_equal(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(strict_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    return a == b


def first_difference(a: Any, b: Any, path: str = "$") -> str | None:
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} != {type(b).__name__} ({str(a)[:80]} vs {str(b)[:80]})"
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return f"{path}: keys {sorted(a)} != {sorted(b)}"
        for k in a:
            d = first_difference(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: len {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_difference(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if a == b else f"{path}: {a!r} != {b!r}"


def iter_commands(node, name: str | None = None):
    if isinstance(node, list):
        if len(node) == 2 and node[0] == "Command" and isinstance(node[1], list) and node[1]:
            if name is None or node[1][0] == name:
                yield node[1]
        for child in node:
            yield from iter_commands(child, name)


def find_cmd(node, name: str):
    return next(iter_commands(node, name), None)


def panel_text_problems(text: str, key: str | None = None) -> list[str]:
    probs = [f"panel text contains forbidden word {w!r}" for w in FORBIDDEN_PANEL_WORDS if w in text]
    if key is not None:
        # R3：CT / 层数封顶 / 状态秒数必须写出来（不能只写「无上限」）；
        # R6：战斗级 PF 伤害不许写「自身」；第三轮：不许留上一轮的节奏（10 秒）。
        probs += [f"{key}: panel text must mention {w!r}" for w in PANEL_REQUIRED_PHRASES.get(key, ())
                  if w not in text]
        probs += [f"{key}: panel text must not say {w!r}"
                  for w in PANEL_FORBIDDEN_PHRASES.get(key, ()) if w in text]
    return probs


def _rewrite_once(key: str, text: str, rewrites: dict, label: str) -> str:
    for old, new in rewrites.get(key, ()):
        if text.count(old) != 1:
            raise KitError(f"{key}: {label} rewrite source appears {text.count(old)} times: {old!r}")
        text = text.replace(old, new)
    return text


def rev4_panel_text(key: str, text: str) -> str:
    """plan 文案 → 包里文案（累积到第四轮）：第二轮规则①/②的改写与删除、第三轮的节奏改写、
    第四轮的强度数字改写，最后给主位键逐行补 ``<icon id='main'>``（已有则不重复）。

    改写段必须**恰好出现一次**（否则 plan 漂了或已经改过），删除段允许 0..n 次；空行不加图标。
    顺序要紧：第三轮第 3 槽的改写源「（每10秒1次）」是第二轮改写的产物；第四轮只碰数字，
    与前两轮的改写段不重叠；图标必须最后加（它顶在行首）。"""
    text = _rewrite_once(key, text, REV2_TEXT_REWRITES, "revision2")
    text = _rewrite_once(key, text, REV3_TEXT_REWRITES, "revision3")
    text = _rewrite_once(key, text, REV4_TEXT_REWRITES, "revision4")
    for drop in REV2_TEXT_DROPS:
        text = text.replace(drop, "")
    if key in REV2_MAIN_ICON_KEYS:
        text = "\n".join(line if not line.strip() or MAIN_ICON in line else MAIN_ICON + line
                         for line in text.split("\n"))
    return text


def rev3_text_problems(texts: dict[str, str]) -> list[str]:
    """第三轮收口：面板上不许再出现上一轮的节奏（10 秒），也不许有人只改了一半。"""
    return [f"{k}: 面板仍写着上一轮的节奏 {w!r}（CT 已改 {CT_SECONDS} 秒 / 「灯火正旺」已改 {LAMP_SECONDS} 秒）"
            for k, t in sorted(texts.items()) for w in REV3_STALE_TIMING if w in t]


def rev4_text_problems(texts: dict[str, str]) -> list[str]:
    """第四轮收口：能力1/3 的覆盖文案必须写新数字、不许留旧数字。

    **按键查**，不做全局禁词：别的键里的「＋50%」是别的效果（能力1#1 开局技能槽、能力2 / 能力6 /
    队长的强化弹射伤害），作者这次没让改，一刀切会误伤。"""
    probs = []
    for key, stale in sorted(REV4_STALE_NUMBERS.items()):
        text = texts.get(key)
        if text is None:
            probs.append(f"{key}: 覆盖文案缺失，无法核对第四轮强度数字")
            continue
        probs += [f"{key}: 面板仍写着上一轮的强度 {w!r}（已改 {A3_LAMP_GAIN_PCT}% / {A1_WICK_MULT_PCT}%）"
                  for w in stale if w in text]
        probs += [f"{key}: 面板缺少第四轮的强度写法 {w!r}"
                  for w in PANEL_REQUIRED_PHRASES.get(key, ()) if w not in text]
    return probs


def rev2_enhance_text_problems(texts: dict[str, str]) -> list[str]:
    """规则②：「技能强化」条目只写强化了什么，不写数值与时间（数字 / 秒 / 百分号 / 倍都不许）。"""
    probs = []
    for key, text in sorted(texts.items()):
        for line in text.split("\n"):
            if ENHANCE_TEXT_MARK not in line:
                continue
            bad = sorted({ch for ch in line if ch in ENHANCE_TEXT_FORBIDDEN})
            if bad:
                probs.append(f"{key}: 技能强化条目不写数值与时间（规则②），出现 {bad}：{line.strip()}")
    return probs


def rev2_skill_flag_problems(ability_rows: dict[str, list[list[str]]], texts: dict[str, str]) -> list[str]:
    """规则②的正向对照：本角色确实有 ChangeSkillFlag(536) 行，它的文案必须是「强化『…』」句式。

    将来若有人加/删这类行，这里会直接红——规则②对本角色不是空过条款。"""
    flag_rows = [(key, i) for key, lines in sorted(ability_rows.items()) for i, row in enumerate(lines)
                 if row[47] in SKILL_FLAG_KINDS or (len(row) > 109 and row[109] in SKILL_FLAG_KINDS)]
    probs = []
    if len(flag_rows) != 1:
        probs.append(f"expected exactly one ChangeSkillFlag(536/704) row, got {flag_rows}")
    for key, i in flag_rows:
        row = ability_rows[key][i]
        if row[70] != CHANGE_SKILL_KEY:
            probs.append(f"ability {key}#{i} ChangeSkillFlag string_id {row[70]!r} != {CHANGE_SKILL_KEY}")
    for key in (CHANGE_SKILL_KEY, f"desc_override_{CODE}_1"):
        if ENHANCE_TEXT_MARK not in texts.get(key, ""):
            probs.append(f"{key}: 技能强化条目缺少「{ENHANCE_TEXT_MARK}…」句式（规则②）")
    return probs + rev2_enhance_text_problems(texts)


def apply_main_slot_only(key: str, row: list[str], label: str) -> list[str]:
    """第二轮 T1：主位限制 = 整键 c1='false'；非主位键必须保持 ``true``（防误伤合击位）。"""
    want = "false" if key in REV2_MAIN_SLOT_KEYS else "true"
    if row[1] not in ("true", "false"):
        raise KitError(f"{label} c1={row[1]!r} is not a boolean")
    if want == "true" and row[1] != "true":
        raise KitError(f"{label} c1={row[1]!r}: {key} 不在主位限制名单里，不许变成主位专用")
    pre202 = [b for b in ABILITY_PRECONDITION_BLOCKS if len(row) > b and row[b] == PRE_OWNER_IS_MAIN]
    if pre202:
        raise KitError(f"{label} carries pre202 (OwnerIsMain) at c{pre202}："
                       f"与 c1=false 同键双写会画两个 Ⓜ")
    out = list(row)
    out[1] = want
    return out


def apply_rev3_cooldown(key: str, index: int, row: list[str], label: str) -> list[str]:
    """第三轮 T3-b：``REV3_CT_ROWS`` 四行的 CT（c35）600 → 300 帧。

    名单外的行若也写着 600，直接报错——作者说的「那个每 10 秒 1 次」只有这一组，
    将来多出来的 CT 行必须重新逐条判断，不许被这层增量顺手改掉（也不许悄悄留着两种节奏）。"""
    out = list(row)
    if (key, index) in REV3_CT_ROWS:
        if out[35] != str(CT_LAMP_FRAMES_REV2):
            raise KitError(f"{label} c35={out[35]!r} != 上一轮的 {CT_LAMP_FRAMES_REV2}（plan 漂了？）")
        out[35] = str(CT_LAMP_FRAMES)
    elif out[35] == str(CT_LAMP_FRAMES_REV2):
        raise KitError(f"{label} 也写着 CT {CT_LAMP_FRAMES_REV2}，却不在第三轮名单 REV3_CT_ROWS 里："
                       f"请先逐条判断它是不是作者说的「每 10 秒 1 次」")
    return out


def panel_matches_row_values(ability_rows: dict[str, list[list[str]]], texts: dict[str, str]) -> list[str]:
    """面板上写的百分数 = 成品行数值列 ÷ 1000，逐条对。

    比「文案里有没有这串字」更硬：拿的是真正要装包的行。另要求这几行两列拉平——
    ``desc_override`` 是固定文案、不跟词条等级走，两列不平面板就会和实际收益对不上
    （记忆卡 wf-leader-override-text-rules）。"""
    probs = []
    for (key, idx), (cas_key, shape) in sorted(PANEL_VALUE_BINDINGS.items()):
        lines = ability_rows.get(key, [])
        if len(lines) <= idx:
            probs.append(f"ability {key}#{idx} missing，面板数字无从核对")
            continue
        cols = REV4_VALUE_ROWS[(key, idx)][0]
        low, high = (lines[idx][c] for c in cols)
        if low != high:
            probs.append(f"ability {key}#{idx} 数值列 c{cols[0]}/c{cols[1]} = {low}/{high} 未拉平："
                         f"固定覆盖文案只写一个数字，两列不平面板会与实际收益不符")
        if not high.isdigit() or int(high) % PCT_SCALE:
            probs.append(f"ability {key}#{idx} 满级列 {high!r} 不是整数百分比（刻度 {PCT_SCALE}）")
            continue
        want = shape.format(pct=int(high) // PCT_SCALE)
        text = texts.get(cas_key, "")
        if want not in text:
            probs.append(f"{cas_key}: 面板缺少与 ability {key}#{idx} 数值列对应的写法 {want!r}")
    return probs


def rev4_scaled_pair(pair: list[str], old_ref: int, new_ref: int, label: str) -> list[str]:
    """按满级列的缩放比例同步「低级列 / 满级列」两列，保持该行原本的 低级:满级 关系。

    用 ``Fraction`` 而不是浮点：除不尽就报错，绝不静默取整（词条数值列是整数千分比，
    50000 = 50%）。本角色这三行两列本来就拉平，缩放后仍拉平。"""
    if len(pair) != 2:
        raise KitError(f"{label} 数值列应为（低级, 满级）两列，实际 {pair!r}")
    if pair[1] != str(old_ref):
        raise KitError(f"{label} 满级列 {pair[1]!r} != 上一轮的 {old_ref}（plan 漂了？）")
    ratio = Fraction(new_ref, old_ref)
    out = []
    for value in pair:
        if not (value.lstrip("-").isdigit()):
            raise KitError(f"{label} 数值列 {value!r} 不是整数，无法按比例缩放")
        scaled = Fraction(int(value)) * ratio
        if scaled.denominator != 1:
            raise KitError(f"{label} 数值列 {value!r} 按 {new_ref}/{old_ref} 缩放后不是整数：{scaled}")
        out.append(str(scaled.numerator))
    return out


def apply_rev4_values(key: str, index: int, row: list[str], label: str) -> list[str]:
    """第四轮 T4-a/T4-b：``REV4_VALUE_ROWS`` 三行的数值列按作者给的新强度缩放（两列同步）。

    名单外的行不动；同量级（50000 / 5000）却既不在改名单也不在 ``REV4_KEEP_ROWS`` 的行直接报错——
    将来有人往能力1/3 里加 50% 的行，必须重新逐条判断它是不是作者说的那两处。"""
    out = list(row)
    spec = REV4_VALUE_ROWS.get((key, index))
    if spec is not None:
        cols, old_ref, new_ref = spec
        for col, value in zip(cols, rev4_scaled_pair([out[c] for c in cols], old_ref, new_ref, label)):
            out[col] = value
        return out
    if key in REV4_SCAN_KEYS and (key, index) not in REV4_KEEP_ROWS:
        hit = [c for c in REV4_SCAN_COLS if len(out) > c and out[c] in REV4_SCAN_MAGNITUDES]
        if hit:
            raise KitError(f"{label} 的数值列 c{hit} 也写着 {REV4_SCAN_MAGNITUDES} 量级，"
                           f"却既不在 REV4_VALUE_ROWS 也不在 REV4_KEEP_ROWS："
                           f"请先逐条判断它是不是作者说的「能力3 的 50%」/「灯芯每层 5%」")
    return out


def rev4_value_scan(plan: dict) -> dict:
    """「先把能力1/3 里含 50% / 5% 的行逐条列出来」的机器版：扫两键全部记录的四个数值列。

    瞬发值 = c51/c52（``AbilityValues`` instant_content 块），持续值 = c113/c114（during_content 块）。
    扫出来的同量级行必须恰好等于「改的三行（``REV4_VALUE_ROWS``）+ 留的一行（``REV4_KEEP_ROWS``，附理由）」。
    """
    found = {}
    for key in REV4_SCAN_KEYS:
        for i, entry in enumerate(plan["tables"]["ability"]["keys"][key]):
            row = entry["row"]
            cells = {f"c{c}": row[c] for c in REV4_SCAN_COLS if len(row) > c and row[c] in REV4_SCAN_MAGNITUDES}
            if cells:
                found[(key, i)] = {"row": f"{key}#{i}", "cells": cells, "kind_instant": row[47],
                                   "kind_during": row[109] if len(row) > 109 else "",
                                   "note": entry.get("note"), "describe": entry.get("describe")}
    changed, kept, probs = [], [], []
    for ref, info in sorted(found.items()):
        if ref in REV4_VALUE_ROWS:
            cols, old_ref, new_ref = REV4_VALUE_ROWS[ref]
            changed.append(dict(info, cols=list(cols), old=old_ref, new=new_ref))
        elif ref in REV4_KEEP_ROWS:
            kept.append(dict(info, reason=REV4_KEEP_ROWS[ref]))
        else:
            probs.append(f"ability {info['row']} 的数值列 {info['cells']} 同为 "
                         f"{REV4_SCAN_MAGNITUDES} 量级，却不在第四轮的改 / 留名单里：请先逐条判断")
    missing = [f"{k}#{i}" for k, i in REV4_VALUE_ROWS if (k, i) not in found]
    if missing:
        probs.append(f"第四轮要改的行在 plan 里没有上一轮的数值：{missing}（plan 漂了？）")
    stale_keep = [f"{k}#{i}" for k, i in REV4_KEEP_ROWS if (k, i) not in found]
    if stale_keep:
        probs.append(f"REV4_KEEP_ROWS 里的行已不再是同量级：{stale_keep}（名单该清了）")
    return {"changed": changed, "kept": kept, "problems": probs,
            "scanned_keys": list(REV4_SCAN_KEYS), "scanned_cols": list(REV4_SCAN_COLS),
            "magnitudes": list(REV4_SCAN_MAGNITUDES)}


def rev3_cooldown_scan(plan: dict) -> dict:
    """「先把本角色所有 c35=600 的行列出来」的机器版：扫计划里每一行的 CT 列。

    词条表 CT = c35（``AbilityValues.parseAt35``，during 块无 CT）；队长表 CT = c33 / c91
    （记忆卡 wf-kit-round2-20260909）。扫描结果进 kit-report，与名单不符就报错。"""
    ability = [(key, i) for key, records in plan["tables"]["ability"]["keys"].items()
               for i, e in enumerate(records) if e["row"][35] == str(CT_LAMP_FRAMES_REV2)]
    leader = [(i, c) for i, e in enumerate(plan["tables"]["leader_ability"]["records"])
              for c in LEADER_CT_BLOCKS if e["row"][c] == str(CT_LAMP_FRAMES_REV2)]
    other = sorted({e["row"][35] for records in plan["tables"]["ability"]["keys"].values() for e in records}
                   - {str(CT_LAMP_FRAMES_REV2)})
    probs = []
    if sorted(ability) != sorted(REV3_CT_ROWS):
        probs.append(f"plan 里 CT{CT_LAMP_FRAMES_REV2} 的行是 {sorted(ability)}，名单是 {sorted(REV3_CT_ROWS)}")
    if leader:
        probs.append(f"leader_ability 也有 CT{CT_LAMP_FRAMES_REV2} 的格 {leader}：本轮未判断，先别改")
    return {"ability_rows": [f"{k}#{i}" for k, i in sorted(ability)],
            "leader_cells": [f"L{i}c{c}" for i, c in leader],
            "other_ability_c35_values": other, "problems": probs}


def rev4_expected_ability_rows(plan: dict) -> dict[str, list[list[str]]]:
    """plan.json 的行 + 第二轮 T1（主位限制）+ 第三轮 T3-b（CT 5 秒）+ 第四轮 T4-a/b（强度回调）
    = 包里应有的词条行（门禁 / 单测与 kit 用同一个真源）。"""
    out = {}
    for slot in range(1, 7):
        key = f"{CID}{slot}"
        records = plan["tables"]["ability"]["keys"].get(key)
        if not records:
            raise KitError(f"plan has no ability records for {key}")
        rows = []
        for i, e in enumerate(records):
            label = f"ability {key}#{i}"
            row = apply_main_slot_only(key, list(e["row"]), label)
            row = apply_rev3_cooldown(key, i, row, label)
            rows.append(apply_rev4_values(key, i, row, label))
        out[key] = rows
    return out


def rev4_row_changes(plan: dict, ability_rows: dict[str, list[list[str]]]) -> dict:
    """成品行 vs plan 行的逐格差异：只准差在 c1（第二轮主位限制）、c35（第三轮 CT）与
    第四轮声明的数值列，且只准差在各自声明的键 / 行上。

    返回 ``{"c1": …, "ct": …, "values": …, "problems": […]}``（每项是 {键: [记录号]}）。"""
    c1_changes, ct_changes, value_changes, probs = {}, {}, {}, []
    for key, lines in sorted(ability_rows.items()):
        planned = [e["row"] for e in plan["tables"]["ability"]["keys"][key]]
        if len(lines) != len(planned):
            probs.append(f"ability {key} record count {len(lines)} != plan {len(planned)}")
            continue
        for i, (built, want) in enumerate(zip(lines, planned)):
            diff = [c for c, (a, b) in enumerate(zip(built, want)) if a != b]
            value_spec = REV4_VALUE_ROWS.get((key, i))
            for col in diff:
                if col == 1 and (built[1], want[1]) == ("false", "true") and key in REV2_MAIN_SLOT_KEYS:
                    c1_changes.setdefault(key, []).append(i)
                elif col == 35 and (key, i) in REV3_CT_ROWS and \
                        (built[35], want[35]) == (str(CT_LAMP_FRAMES), str(CT_LAMP_FRAMES_REV2)):
                    ct_changes.setdefault(key, []).append(i)
                elif value_spec is not None and col in value_spec[0] and \
                        [built[c] for c in value_spec[0]] == \
                        rev4_scaled_pair([want[c] for c in value_spec[0]], value_spec[1], value_spec[2],
                                         f"ability {key}#{i}"):
                    if i not in value_changes.setdefault(key, []):
                        value_changes[key].append(i)
                else:
                    probs.append(f"ability {key}#{i}: 只准改 c1（主位限制）/ c35（CT）/ "
                                 f"第四轮声明的数值列，实际差异列 {diff}")
                    break
        if len({r[1] for r in lines}) != 1:
            probs.append(f"ability {key}: c1 在同键内不一致 {[r[1] for r in lines]}（get_unisonable 只读 values[0]）")
    missing = [f"{k}#{i}" for k, i in REV3_CT_ROWS if i not in ct_changes.get(k, ())]
    if missing:
        probs.append(f"第三轮 CT 未落到这些行：{missing}")
    missing_values = [f"{k}#{i}" for k, i in REV4_VALUE_ROWS if i not in value_changes.get(k, ())]
    if missing_values:
        probs.append(f"第四轮强度未落到这些行：{missing_values}")
    return {"c1": c1_changes, "ct": ct_changes, "values": value_changes, "problems": probs}


def rev3_unique_row(uid: str, row: list[str]) -> list[str]:
    """第三轮 T3-a：固有 159997「灯火正旺」的 duration_frame（c3）600 → 720 帧（10 → 12 秒）。

    「灯芯」1599971 是永续状态（99999999 帧），不在本轮改动范围；名单外的行若写着 600 帧同样报错。"""
    out = list(row)
    if uid == UC_ID:
        if out[3] != str(UC_LAMP_FRAMES_REV2):
            raise KitError(f"unique {uid} duration {out[3]!r} != 上一轮的 {UC_LAMP_FRAMES_REV2}（plan 漂了？）")
        out[3] = str(UC_LAMP_FRAMES)
    elif out[3] == str(UC_LAMP_FRAMES_REV2):
        raise KitError(f"unique {uid} 也是 {UC_LAMP_FRAMES_REV2} 帧，却不在第三轮名单里：请先逐条判断")
    return out


def main_slot_panel_problems(ability_rows: dict[str, list[list[str]]], texts: dict[str, str]) -> list[str]:
    """词条键的 c1（主位限制）与它的覆盖文案是否一致：c1=false ⇔ 覆盖文案每行都带 ``<icon id='main'>``。

    面板 Ⓜ 本由客户端逐行画，但 desc_override 把整段文字换掉了，所以图标要写进文本；
    两边错位 = 面板上「有 Ⓜ 没限制」或「有限制没 Ⓜ」。没有覆盖文案的槽（4/5）由客户端自动画，跳过文本检查。"""
    probs = []
    for slot in range(1, 7):
        key = f"{CID}{slot}"
        lines = ability_rows.get(key)
        if not lines:
            probs.append(f"ability {key} missing")
            continue
        main_only = lines[0][1] == "false"
        want = slot in REV2_MAIN_SLOT_SLOTS
        if main_only != want:
            probs.append(f"ability {key} c1={lines[0][1]!r} but revision2 expects main_only={want}")
        cas_key = SLOT_CAS_KEY.get(slot)
        if cas_key is None:
            continue
        if cas_key not in texts:
            probs.append(f"{cas_key} missing")
            continue
        text_lines = [ln for ln in texts[cas_key].split("\n") if ln.strip()]
        tagged = [ln.startswith(MAIN_ICON) for ln in text_lines]
        if main_only and not all(tagged):
            probs.append(f"{cas_key}: main-slot ability but {tagged.count(False)} line(s) lack {MAIN_ICON!r}")
        if not main_only and any(tagged):
            probs.append(f"{cas_key}: not a main-slot ability but carries {MAIN_ICON!r}")
    return probs


def load_design(root: Path) -> dict:
    design = json.loads((root / DESIGN_REL).read_text(encoding="utf-8"))
    if design.get("status") != "final" or design.get("key") != KEY:
        raise KitError(f"design {DESIGN_REL} is not final zehr design")
    ident = design["identity"]
    if (ident["cid"], ident["code"], int(ident["element"])) != (CID, CODE, ELEMENT):
        raise KitError(f"design identity mismatch {ident}")
    return design


def load_revision(root: Path) -> dict:
    """2026-09-16 作者改版计划（revision-20260916/zehr/plan.json）：行 / 文案 / 技能 ALv 的唯一来源。"""
    plan = json.loads((root / REVISION_REL).read_text(encoding="utf-8"))
    if plan.get("schema") != REVISION_SCHEMA or plan.get("key") != KEY:
        raise KitError(f"revision {REVISION_REL} schema/key unexpected: {plan.get('schema')} {plan.get('key')}")
    if (plan.get("cid"), plan.get("code")) != (CID, CODE):
        raise KitError(f"revision identity mismatch {plan.get('cid')} {plan.get('code')}")
    if sorted(plan.get("required_capabilities") or []) != sorted(CAPABILITIES):
        raise KitError(f"revision required_capabilities {plan.get('required_capabilities')}")
    return plan


def character_text_row(design: dict) -> list[str]:
    """改版后的 character_text 行 = 设计行，只换两档技能描述（c5/c7）。"""
    row = list(design["text"]["character_text_row"])
    if (row[5], row[7]) != (DESIGN_SKILL_DESC, DESIGN_SKILL_DESC):
        raise KitError("design character_text c5/c7 is not the pre-revision skill description")
    row[5], row[7] = TEXTS["desc1"], TEXTS["desc2"]
    return row


def check_texts_constant(design: dict, plan: dict | None = None) -> list[str]:
    """TEXTS 与设计定稿逐项核对；技能描述两档按改版计划改写（其余文本仍必须等于设计）。"""
    t = design["text"]
    want = {"name": t["name"], "furigana": t["furigana"], "title": t["nickname"],
            "profile": t["character_text_row"][2], "leader": t["leader_skill_name"],
            "skill1": t["skill_name_1"], "skill2": t["skill_name_2"], "cv": t["cv"]}
    probs = [f"TEXTS[{k}] != design" for k, v in want.items() if TEXTS.get(k) != v]
    if (t["skill_desc_1"], t["skill_desc_2"]) != (DESIGN_SKILL_DESC, DESIGN_SKILL_DESC):
        probs.append("design skill_desc_1/2 != pre-revision baseline (design file changed?)")
    if TEXTS["desc1"] != TEXTS["desc2"]:
        probs.append("TEXTS desc1 != desc2 (两档同文)")
    # R5：面板点名「攻击力提升效果＋250%」/「强化弹射伤害提升效果＋250%」，技能说明必须提到这两个效果名，
    # 否则玩家在技能说明里找不到 536 强化的对象。
    probs += [f"TEXTS[desc1] must mention {w!r}" for w in SKILL_DESC_REQUIRED if w not in TEXTS["desc1"]]
    if plan is not None:
        desc = plan["texts"]["action_skill_desc"]
        if desc["old"] != DESIGN_SKILL_DESC:
            probs.append("revision action_skill_desc.old != design skill description")
        if desc["new"] != TEXTS["desc1"]:
            probs.append("TEXTS[desc1] != revision action_skill_desc.new")
    row = t["character_text_row"]
    expect_row = [TEXTS["name"], TEXTS["furigana"], TEXTS["profile"], TEXTS["title"], TEXTS["skill1"],
                  DESIGN_SKILL_DESC, TEXTS["skill2"], DESIGN_SKILL_DESC, "(None)", "(None)",
                  TEXTS["leader"], TEXTS["cv"]]
    if row != expect_row:
        probs.append("design character_text_row != TEXTS-derived row")
    return probs


def power_up_blob(blob: bytes, plan: dict) -> bytes:
    """审查修复轮 R4：536 ChangeSkillFlag 的「强化」后缀真源是 ``custom_ability_power_up_string``。

    【事实】``InstantAbilitySource.as:5018`` 把 536 的 ``string_id`` 交给
    ``CustomAbilityPowerUpStringTools.resolveDescriptionPowerLevel``；面板由
    ``AbilityDescriptionStringfier_Impl_.as:1699`` / ``AbilityDescriptionTools.as:3077`` 读
    ``CustomAbilityPowerUpStringTable``。``custom_ability_string`` 那个同名键是**主文案**
    （``AbilityDescriptionGenerator.as:8531`` case 15），两张表都读、都要改。
    官方同形：``change_skill_combat_animal_xm21``「攻击力提升效果强化/技能伤害提升效果强化」。
    """
    import wf_seasonal7_tables as T
    item = plan["texts"]["custom_ability_power_up_string"][CHANGE_SKILL_KEY]
    if item["action"] == "unchanged":
        return blob
    if item["action"] != "rewrite":
        raise KitError(f"power_up string unknown action {item['action']!r}")
    old, new = item["old"], item["value"]
    levels = [str(i) for i in range(2, 7)]
    if sorted(old) != levels or sorted(new) != levels:
        raise KitError(f"power_up levels {sorted(old)}/{sorted(new)} != {levels}")
    got = T.decode_blob(blob)
    if got != old:
        raise KitError(f"power_up donor text {got} != plan old {old}")
    src, dst = set(old.values()), set(new.values())
    if len(src) != 1 or len(dst) != 1:
        raise KitError(f"power_up rewrite must be one text for all 5 levels: {sorted(src)} -> {sorted(dst)}")
    src, dst = src.pop(), dst.pop()
    if src == dst:
        raise KitError("power_up rewrite is a no-op")
    out = T.clone_blob(blob, lambda cell: dst if cell == src else cell)          # 层键 '2'..'6' 不会命中
    back = T.decode_blob(out)
    if back != new:
        raise KitError(f"power_up rewrite roundtrip {back} != plan {new}")
    return out


def apply_text_override(text: str, label: str) -> str:
    if TEXT_DROPPED_BY_OVERRIDE not in text:
        raise KitError(f"{label}: override phrase {TEXT_DROPPED_BY_OVERRIDE!r} not found (design changed?)")
    return text.replace(TEXT_DROPPED_BY_OVERRIDE, "")


# ---------------------------------------------------------------- 行构建

# 2026-09-27 冻结 donor（稻穗 139995 第二批追加 wf_balance_20260927b_inaho2）：plan.json
# /tables/ability/keys/1599975[1]（A5#1「PF Lv3 → 全队(光)技能槽 5%」）的 donor 是稻穗能力1 在 live 的第 2 行。
# 该单元发布后 1399951 从 6 行删到 4 行，第 2 行换成 724 行 ⇒ 按行号取，old_values 对不上（KitError）；
# 原行搬去的 1399953 第 7 行加了雷共鸣，c0/c6/c9–c11/c13 都变了，也不能改指。plan.json 是第一轮证据
# （不改写，其 sha 进 kit_fingerprint），所以在 kit 里把这个 donor 钉成发布前的 live 行：回放不读 live，
# 按下表还原整行并核对 sha256（= csv 单行文本），发布前后回放结果逐字相同。
# 键 = donor 字符串拆出的 (表, 来源, 键, 行号)；值只列非空格。
FROZEN_DONORS: dict[tuple[str, str, str, int], dict[str, Any]] = {
    ("ability", "LIVE", "1399951", 2): {
        "frozen_from": "live 1.4.1051，稻穗 inaho2 发布前",
        "width": 126,
        "cells": {0: "fox_oracle_autumn_1", 1: "true", 2: "attack_yellow", 3: "0", 5: "0", 6: "12",
                  13: "0", 20: "0", 27: "65", 30: "100000", 31: "100000", 34: "(None)", 35: "0",
                  39: "(None)", 46: "0", 47: "211", 48: "5", 49: "Yellow", 51: "2500", 52: "5000"},
        "sha256": "9b03a6b2f90c96d49384c5965f02ef00e7fdfb1d4362428a522480635c7f9fbf",
    },
}


def parse_donor(donor: str) -> tuple[str, str, str, int]:
    """``"<table> <来源>:<key>#<i>"`` → (table, 来源, key, i)。"""
    table, rest = donor.split(" ", 1)
    source, key_idx = rest.split(":", 1)
    key, idx = key_idx.split("#", 1)
    return table, source, key, int(idx)


def frozen_donor_row(spec: dict[str, Any], donor: str) -> list[str]:
    """由 :data:`FROZEN_DONORS` 的一项还原整行；sha256 不符即 KitError（冻结行被改动）。"""
    import wf_mod_tool as core
    row = [""] * spec["width"]
    for col, value in spec["cells"].items():
        row[col] = value
    got = sha256(core.write_csv_lines([row]).rstrip("\n").encode("utf-8"))
    if got != spec["sha256"]:
        raise KitError(f"frozen donor {donor} sha256 {got} != pin {spec['sha256']}")
    return row


def donor_evidence(donor: str) -> dict[str, str]:
    """证据里标明冻结 donor（donor 字符串仍写 plan 原文）。"""
    spec = FROZEN_DONORS.get(parse_donor(donor))
    return {"donor_frozen": f"{spec['frozen_from']}，sha256 {spec['sha256']}"} if spec else {}


def donor_row(ctx, donor: str, index: int) -> tuple[list[str], str]:
    """design donor 写法 ``"<table> OFF:<key>#<i>"`` / ``"<table> LIVE:<key>#<i>"``；
    :data:`FROZEN_DONORS` 里登记的 donor 不读表，用冻结行。"""
    table, source, key, idx = parse_donor(donor)
    if idx != index:
        raise KitError(f"donor index mismatch {donor} vs row_index {index}")
    frozen = FROZEN_DONORS.get((table, source, key, idx))
    if frozen is not None:
        return frozen_donor_row(frozen, donor), table
    logical = f"master/ability/{table}.orderedmap"
    if source == "OFF":
        rows = ctx.official_flat(logical)
    elif source == "LIVE":
        rows = ctx.live_flat(logical)
    else:
        raise KitError(f"unknown donor source {donor}")
    if key not in rows:
        raise KitError(f"donor {donor} missing")
    lines = ctx.csv_split(rows[key])
    return list(lines[index]), table


def row_checks(kind: str, row: list[str]) -> dict[str, Any]:
    import wf_client_legality as L
    import wf_describe
    return {
        "describe": wf_describe.describe_rows([row], kind)[0],
        "client_legality_problems": L.client_legality_problems(kind, row),
        "declared_block_field_problems": L.declared_block_field_problems(kind, row),
        "ability_element_column_problems": (L.ability_element_column_problems(kind, row, ELEMENT)
                                            if kind == "ability" else []),
        "capabilities": L.required_client_capabilities(kind, row),
    }


def replay_row(ctx, entry: dict, table_hint: str, label: str, index: int) -> list[str]:
    """donor 原行 + 声明编辑 → 与计划成品行逐格核对。"""
    if entry["target_record"] != index:
        raise KitError(f"{label} record order {entry['target_record']} != {index}")
    row, table = donor_row(ctx, entry["donor"], entry["row_index"])
    if table != table_hint:
        raise KitError(f"{label} donor table {table} != {table_hint}")
    for col, val in entry["edits"].items():
        if row[int(col)] != entry["old_values"][col]:
            raise KitError(f"{label} donor c{col}={row[int(col)]!r} != plan old {entry['old_values'][col]!r}")
        row[int(col)] = val
    if row != entry["row"]:
        diff = {c: (a, b) for c, (a, b) in enumerate(zip(row, entry["row"])) if a != b}
        raise KitError(f"{label} donor+edits != plan row: {diff}")
    return row


def trigger_limit_problems(kind: str, row: list[str]) -> list[str]:
    """「无上限」必须写字面量 ``(None)``：空串会被 Std.parseInt 吃成 0 = 永不触发
    （AbilityValues.parseAt34 / LeaderAbilityValues.parseAt32）。有瞬发触发（kind 非空且非 0）就必须有上限列。"""
    trig, lim = (27, 34) if kind == "ability" else (25, 32)
    if row[trig] not in ("", "0") and row[lim] == "":
        return [f"instant trigger {row[trig]} has empty trigger_limit (= 0 次, never fires)"]
    return []


def leader_gate_problems(ability_rows: dict[str, list[list[str]]]) -> list[str]:
    """审查修复轮 R1：pre42（自身为队长）只准出现在作者原文点名的能力2 两行上。

    作者 2026-09-16 原文这一段只在「能力2,自身为队长时强化弹射伤害随连击数提升」写了队长条件；
    50 连击触发的四行（能力1 两条发放行 + 能力3 两条受益行）没有队长条件，面板文案也不写，
    带着 pre42 就是「面板承诺 ≠ 实际生效」，并且能力1 可上合击位（c1=true）时那三行全是死行。
    422 冲刺两行（1599973#1/#2）的 pre42 是上一轮就有的、作者要求「特殊冲刺不变」，不在此列。
    """
    probs = []
    for key, idx in NO_LEADER_GATE_ROWS:
        row = ability_rows.get(key, [])
        if len(row) <= idx:
            probs.append(f"{key}#{idx} missing")
        elif row[idx][6] == "42":
            probs.append(f"{key}#{idx} still carries pre42")
    for key, idx in LEADER_GATE_ROWS:
        row = ability_rows.get(key, [])
        if len(row) <= idx:
            probs.append(f"{key}#{idx} missing")
        elif row[idx][6] != "42":
            probs.append(f"{key}#{idx} lost pre42 (作者原文「自身为队长时」)")
    return probs


def build_rows(ctx, plan: dict) -> tuple[dict, list[dict]]:
    """按改版计划 plan.json 重放 6 条队长行与 6 键 20 条词条行（donor + edits，逐格核对成品行）。"""
    evidence: list[dict] = []
    leader_rows: list[list[str]] = []
    leader_block = plan["tables"]["leader_ability"]
    if leader_block["key"] != CID or leader_block["logical_path"] != LEADER:
        raise KitError(f"plan leader block {leader_block['key']} {leader_block['logical_path']}")
    for i, entry in enumerate(leader_block["records"]):
        row = replay_row(ctx, entry, "leader_ability", f"leader#{i}", i)
        if row[0] != CODE:
            raise KitError(f"leader#{i} c0 {row[0]}")
        leader_rows.append(row)
        evidence.append({"table": "leader_ability", "key": CID, "record": i, "donor": entry["donor"], "row": row,
                         **donor_evidence(entry["donor"])})
    ability_block = plan["tables"]["ability"]
    if ability_block["logical_path"] != ABILITY:
        raise KitError(f"plan ability logical_path {ability_block['logical_path']}")
    ability_rows: dict[str, list[list[str]]] = {}
    for slot in range(1, 7):
        key = f"{CID}{slot}"
        records = ability_block["keys"].get(key)
        if not records:
            raise KitError(f"plan has no ability records for {key}")
        lines = []
        for j, entry in enumerate(records):
            row = replay_row(ctx, entry, "ability", f"ability {key}#{j}", j)
            if row[0] != f"{CODE}_{slot}":
                raise KitError(f"ability {key} c0 {row[0]}")
            row = apply_main_slot_only(key, row, f"ability {key}#{j}")      # 第二轮 T1：能力 1/3/5 主位限制
            row = apply_rev3_cooldown(key, j, row, f"ability {key}#{j}")    # 第三轮 T3-b：CT 10 秒 → 5 秒
            row = apply_rev4_values(key, j, row, f"ability {key}#{j}")      # 第四轮 T4-a/b：50%→30% / 5%→3%
            lines.append(row)
            evidence.append({"table": "ability", "key": key, "record": j, "donor": entry["donor"], "row": row,
                             **donor_evidence(entry["donor"])})
        ability_rows[key] = lines
    total = sum(len(v) for v in ability_rows.values())
    if total != ability_block["record_count"] or len(leader_rows) != leader_block["record_count"]:
        raise KitError(f"row counts ability={total} leader={len(leader_rows)} plan="
                       f"{ability_block['record_count']}/{leader_block['record_count']}")
    for probs in (leader_gate_problems(ability_rows),):
        if probs:
            raise KitError(f"leader gate (pre42) placement: {probs}")
    scan = rev3_cooldown_scan(plan)                 # 「所有 c35=600 的行」与名单必须一致
    if scan["problems"]:
        raise KitError(f"revision3 cooldown scan: {scan['problems']}")
    value_scan = rev4_value_scan(plan)              # 「能力1/3 里所有 50000 / 5000 的格」与名单必须一致
    if value_scan["problems"]:
        raise KitError(f"revision4 value scan: {value_scan['problems']}")
    if rev4_expected_ability_rows(plan) != ability_rows:
        raise KitError("ability rows != plan rows + revision2 main-slot + revision3 cooldown + revision4 values")
    changes = rev4_row_changes(plan, ability_rows)
    if changes["problems"]:
        raise KitError(f"revision2/3/4 row edits: {changes['problems']}")
    for item in evidence:
        if item["table"] != "ability":
            continue
        if item["record"] in changes["c1"].get(item["key"], ()):
            item["revision2"] = "c1 true -> false（主位限制）"
        if item["record"] in changes["ct"].get(item["key"], ()):
            item["revision3"] = (f"c35 {CT_LAMP_FRAMES_REV2} -> {CT_LAMP_FRAMES}"
                                 f"（CT 10 秒 -> {CT_SECONDS} 秒）")
        if item["record"] in changes["values"].get(item["key"], ()):
            cols, old_ref, new_ref = REV4_VALUE_ROWS[(item["key"], item["record"])]
            item["revision4"] = (f"c{cols[0]}/c{cols[1]} {old_ref} -> {new_ref}"
                                 f"（{old_ref // PCT_SCALE}% -> {new_ref // PCT_SCALE}%）")
    for item in evidence:
        item.update(row_checks(item["table"], item["row"]))
        item["trigger_limit_problems"] = trigger_limit_problems(item["table"], item["row"])
    return {"leader": leader_rows, "ability": ability_rows}, evidence


def mixed_c1_c2(ability_rows: dict[str, list[list[str]]]) -> dict[str, list[tuple[str, str]]]:
    """同键多记录 c1/c2 混写清单（仅信息，不是缺陷）。"""
    return {key: [(r[1], r[2]) for r in lines] for key, lines in ability_rows.items()
            if len({r[1] for r in lines}) > 1 or len({r[2] for r in lines}) > 1}


# ---------------------------------------------------------------- 固有状态图标

ICON_SUPERSAMPLE = 8


def _icon_base(glow_box=(12, 13, 36, 37), glow_color=(255, 179, 71, 150)):
    """两个固有图标共用的底：白色圆角外框 + 暗红渐变内底 + 一团暖光（8× 超采样，未缩小）。"""
    from PIL import Image, ImageDraw, ImageFilter
    k = ICON_SUPERSAMPLE
    size = 48 * k
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=7 * k, fill=(255, 255, 255, 255))
    grad = Image.new("RGBA", (size, size))
    top, bottom = (170, 52, 60), (98, 22, 32)
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / (size - 1)
        gd.line([(0, y), (size, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)) + (255,))
    inner = Image.new("L", (size, size), 0)
    ImageDraw.Draw(inner).rounded_rectangle([3 * k, 3 * k, size - 1 - 3 * k, size - 1 - 3 * k], radius=5 * k, fill=255)
    base.paste(grad, (0, 0), inner)
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([glow_box[0] * k, glow_box[1] * k, glow_box[2] * k, glow_box[3] * k], fill=glow_color)
    glow = glow.filter(ImageFilter.GaussianBlur(4 * k))
    glow_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(glow_mask).rounded_rectangle([3 * k, 3 * k, size - 1 - 3 * k, size - 1 - 3 * k],
                                                radius=5 * k, fill=255)
    clipped = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    clipped.paste(glow, (0, 0), glow_mask)
    return Image.alpha_composite(base, clipped)


def draw_lamp_icon():
    """48×48 官方风固有状态图标「灯火正旺」：白色圆角框 + 暗红渐变底 + 白色提灯 + 金色灯芯火苗（8× 超采样）。"""
    from PIL import Image, ImageDraw
    k = ICON_SUPERSAMPLE
    size = 48 * k
    base = _icon_base()
    d = ImageDraw.Draw(base)
    white = (255, 255, 255, 255)
    s = k
    d.arc([19 * s, 6 * s, 29 * s, 16 * s], start=180, end=360, fill=white, width=int(2 * s))       # 提环
    d.polygon([(17 * s, 15 * s), (31 * s, 15 * s), (28 * s, 12 * s), (20 * s, 12 * s)], fill=white)  # 顶盖
    d.rounded_rectangle([16 * s, 15 * s, 32 * s, 35 * s], radius=3 * s, outline=white, width=int(2.2 * s))  # 灯罩
    d.line([(24 * s, 15 * s), (24 * s, 18 * s)], fill=white, width=int(1.5 * s))
    d.polygon([(17 * s, 35 * s), (31 * s, 35 * s), (29 * s, 39 * s), (19 * s, 39 * s)], fill=white)   # 底座
    d.polygon([(24 * s, 18.5 * s), (28.2 * s, 27 * s), (27.6 * s, 30.5 * s), (24 * s, 33 * s),
               (20.4 * s, 30.5 * s), (19.8 * s, 27 * s)], fill=(255, 211, 106, 255))                   # 火苗
    d.polygon([(24 * s, 23 * s), (26.2 * s, 28 * s), (24 * s, 31.2 * s), (21.8 * s, 28 * s)],
              fill=(255, 246, 224, 255))
    return base.resize((48, 48), Image.Resampling.LANCZOS)


def draw_wick_icon():
    """48×48 官方风固有状态图标「灯芯」：同族白框暗红底 + 裸灯芯火苗 + 向上细光柱 + 白色芯线。

    与「灯火正旺」的提灯轮廓刻意拉开（方盒 vs 竖向光柱），两者会同屏出现；
    右下角留白给客户端自绘层数数字（accumulatable=true 时才画）。"""
    from PIL import Image, ImageDraw, ImageFilter
    k = ICON_SUPERSAMPLE
    size = 48 * k
    s = k
    base = _icon_base(glow_box=(9, 12, 33, 36), glow_color=(255, 196, 96, 160))
    inner_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(inner_mask).rounded_rectangle([3 * k, 3 * k, size - 1 - 3 * k, size - 1 - 3 * k],
                                                 radius=5 * k, fill=255)
    beam = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(beam).polygon([(19.9 * s, 4.5 * s), (22.1 * s, 4.5 * s), (26.4 * s, 25 * s), (15.6 * s, 25 * s)],
                                 fill=(255, 232, 168, 105))                                        # 向上细光柱
    beam = beam.filter(ImageFilter.GaussianBlur(1.2 * k))
    clipped = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    clipped.paste(beam, (0, 0), inner_mask)
    base = Image.alpha_composite(base, clipped)
    d = ImageDraw.Draw(base)
    white = (255, 255, 255, 255)
    d.line([(21 * s, 30 * s), (21 * s, 40 * s)], fill=white, width=int(2.4 * s))                   # 芯线
    d.line([(21 * s, 40 * s), (17.4 * s, 42.6 * s)], fill=white, width=int(2.2 * s))               # 芯线末端弯钩
    d.polygon([(21 * s, 11.5 * s), (25.9 * s, 23.5 * s), (25.2 * s, 28.6 * s), (21 * s, 31.6 * s),
               (16.8 * s, 28.6 * s), (16.1 * s, 23.5 * s)], fill=(255, 211, 106, 255))             # 火苗
    d.polygon([(21 * s, 17 * s), (23.5 * s, 23.4 * s), (21 * s, 27.8 * s), (18.5 * s, 23.4 * s)],
              fill=(255, 246, 224, 255))                                                           # 焰心
    return base.resize((48, 48), Image.Resampling.LANCZOS)


# ---------------------------------------------------------------- 特效染色

def _hex(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _grad(stops, t):
    import numpy as np
    pos = np.array([p for p, _ in stops], dtype=np.float32)
    cols = np.array([_hex(c) for _, c in stops], dtype=np.float32)
    t = np.clip(t, pos[0], pos[-1])
    out = np.empty(t.shape + (3,), dtype=np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(t, pos, cols[:, ch])
    return out


def _hsv(rgb):
    import numpy as np
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    delta = np.maximum(mx - mn, 1e-6)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    hue = np.where(mx == r, ((g - b) / delta) % 6, np.where(mx == g, (b - r) / delta + 2, (r - g) / delta + 4)) * 60
    return hue, sat, mx


def _hue_in(hue, lo, hi):
    return (hue >= lo) & (hue <= hi) if lo <= hi else (hue >= lo) | (hue <= hi)


# 规则：hue=(lo,hi) 或 None；sat/val 闭区间；lum=(lo,hi) 把亮度线性拉到 0..1 再查渐变；alpha_scale 仅该类像素
PALETTES: dict[str, list[dict]] = {
    "skill_blade": [   # 青白风刃/冲刺环 → 暖白金；橙黑爆炸 → 琥珀+暗红烟；白 → 微暖
        {"hue": (150, 265), "sat": (0.10, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#4A2A14"), (0.35, "#C99A4A"), (0.72, "#F2D48A"), (1.0, "#FFF3D6")]},
        {"hue": (330, 75), "sat": (0.25, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#3A0E12"), (0.3, "#8E2A2F"), (0.55, "#D9563A"), (0.75, "#FFB94A"), (1.0, "#FFE27A")]},
        {"hue": None, "sat": (0, 0.25), "val": (0, 0.40), "lum": (0.0, 0.40),
         "stops": [(0.0, "#1E0609"), (1.0, "#5E1820")]},
        {"hue": None, "sat": (0, 0.10), "val": (0.40, 1), "lum": (0.40, 1.0),
         "stops": [(0.0, "#B8A58A"), (1.0, "#FFF8EE")]},
    ],
    "skill_orb": [     # 光弹蓝环 → 金灯芯 + 暗红晕，中心暖白
        {"hue": (150, 265), "sat": (0.10, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#3A0E12"), (0.3, "#A8323C"), (0.65, "#FFD36A"), (1.0, "#FFF6E0")]},
        {"hue": (330, 75), "sat": (0.25, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#5E1820"), (0.5, "#FF8A3C"), (1.0, "#FFE27A")]},
        {"hue": None, "sat": (0, 0.10), "val": (0.40, 1), "lum": (0.40, 1.0),
         "stops": [(0.0, "#D9B98A"), (1.0, "#FFF6E0")]},
    ],
    "pf_spin_core": [  # 白核刀弧 → 暖白/金；青/黄绿弧 → 琥珀；黄辉光 → 提灯暖橙；蓝黑爆芒 → 暗红黑 + 金边
        {"hue": (275, 345), "sat": (0.25, 1), "lum": "stripe",
         "stops": [(0.0, "#3A0E12"), (0.33, "#8E2430"), (0.66, "#C2413F"), (1.0, "#F2B09A")]},
        {"hue": (40, 75), "sat": (0.20, 1), "lum": (0.45, 1.0),
         "stops": [(0.0, "#E07A2A"), (0.6, "#FFB347"), (1.0, "#FFF1C1")]},
        {"hue": (75, 200), "sat": (0.15, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#4A1208"), (0.4, "#9A3A1E"), (0.7, "#E3A33A"), (1.0, "#FFE8A0")]},
        {"hue": (200, 275), "sat": (0.15, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#2A0609"), (0.35, "#8E2430"), (0.7, "#C2413F"), (1.0, "#E8B84A")]},
        {"hue": None, "sat": (0, 0.15), "val": (0.35, 1), "lum": (0.35, 1.0),
         "stops": [(0.0, "#6B5A4A"), (0.55, "#D8CFC2"), (0.85, "#FFE3A0"), (1.0, "#FFF6E0")]},
    ],
    "pf_support": [    # 青绿 → 金；深蓝 → 暗红；橙红 → 灯火橙；黄绿 → 琥珀；白保持
        {"hue": (140, 190), "sat": (0.20, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#6A4A16"), (0.6, "#FFD36A"), (1.0, "#FFF3C8")]},
        {"hue": (190, 270), "sat": (0.20, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#1A0406"), (0.3, "#5E1820"), (1.0, "#C2413F")]},
        {"hue": (340, 30), "sat": (0.40, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#6E1A10"), (0.5, "#FF8A3C"), (1.0, "#FFD0A0")]},
        {"hue": (30, 140), "sat": (0.20, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#7A4A14"), (0.6, "#F2B84B"), (1.0, "#FFE27A")]},
    ],
    "pf_blaze": [      # 橙黄火焰/光球 → 暗红底 + 暖金亮部；褐烟 → 暗红烟；白保持微暖（Effects 未产出时的兜底）
        {"hue": (330, 75), "sat": (0.20, 1), "lum": (0.0, 1.0),
         "stops": [(0.0, "#2A0609"), (0.3, "#8E2430"), (0.52, "#D9563A"), (0.72, "#F2B84B"),
                   (0.9, "#FFD36A"), (1.0, "#FFF1C1")]},
        {"hue": None, "sat": (0, 0.12), "val": (0.40, 1), "lum": (0.40, 1.0),
         "stops": [(0.0, "#D9B98A"), (1.0, "#FFF6E0")]},
        {"hue": None, "sat": (0, 1), "val": (0, 0.45), "lum": (0.0, 0.45),
         "stops": [(0.0, "#1E0609"), (1.0, "#6E1A24")]},
    ],
}


def region_masks(shape, atlas: list[dict], groups: dict[str, Callable[[str], bool]]):
    import numpy as np
    h, w = shape
    masks = {name: np.zeros((h, w), dtype=bool) for name in groups}
    for entry in atlas:
        if not isinstance(entry, dict) or "n" not in entry:
            continue
        base = entry["n"].split("/.gen/", 1)[-1].split("/", 1)[0]
        for name, pred in groups.items():
            if pred(base):
                masks[name][entry["y"]:entry["y"] + entry["h"], entry["x"]:entry["x"] + entry["w"]] = True
                break
    return masks


def apply_palette(arr, rules: list[dict], region, *, alpha_scale_mask=None, alpha_scale: float = 1.0):
    """按 hue/sat/val 分类、亮度查渐变换色；alpha 逐字节保留（alpha_scale_mask 内的条纹除外，且非零不降到 0）。"""
    import numpy as np
    rgb = arr[..., :3].astype(np.float32) / 255.0
    alpha = arr[..., 3]
    hue, sat, val = _hsv(rgb)
    lum = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
    out = arr.copy()
    assigned = np.zeros(alpha.shape, dtype=bool)
    counts = []
    visible = (alpha > 0) & region
    for rule in rules:
        m = visible & ~assigned
        if rule.get("hue") is not None:
            m &= _hue_in(hue, *rule["hue"])
        lo, hi = rule.get("sat", (0, 1))
        m &= (sat >= lo) & (sat <= hi)
        if "val" in rule:
            vlo, vhi = rule["val"]
            m &= (val >= vlo) & (val <= vhi)
        n = int(m.sum())
        counts.append(n)
        if not n:
            continue
        spec = rule["lum"]
        if spec in ("stripe", "family"):
            top = float(lum[m].max()) or 1.0
            t = lum / top
        else:
            llo, lhi = spec
            t = (lum - llo) / max(lhi - llo, 1e-6)
        new = _grad(rule["stops"], t)
        out[..., :3][m] = np.clip(np.rint(new[m] * 255), 0, 255).astype(np.uint8)
        assigned |= m
        if spec == "stripe" and alpha_scale_mask is not None and alpha_scale != 1.0:
            sm = m & alpha_scale_mask
            scaled = np.maximum(1, np.rint(alpha[sm].astype(np.float32) * alpha_scale)).astype(np.uint8)
            out[..., 3][sm] = scaled
    return out, counts


def family_recolor(name: str, atlas: list[dict]) -> Callable:
    import numpy as np
    from PIL import Image

    def transform(img):
        arr = np.array(img.convert("RGBA"))
        full = np.ones(arr.shape[:2], dtype=bool)
        stats: dict[str, Any] = {}
        if name == "skill":
            masks = region_masks(arr.shape[:2], atlas, {
                "black": lambda b: b == "guildknight_leader_black",
                "orb": lambda b: b == "assist_skill",
                "blade": lambda b: True})
            arr, stats["blade"] = apply_palette(arr, PALETTES["skill_blade"], masks["blade"])
            arr, stats["orb"] = apply_palette(arr, PALETTES["skill_orb"], masks["orb"])
            stats["black_kept_px"] = int(masks["black"].sum())
        elif name == "pf_spin":
            masks = region_masks(arr.shape[:2], atlas, {
                "outer": lambda b: b in ("powerflip_attack_spin_two", "powerflip_attack_spin_three")})
            arr, stats["spin"] = apply_palette(arr, PALETTES["pf_spin_core"], full,
                                               alpha_scale_mask=masks["outer"], alpha_scale=0.8)
        elif name == "pf_support":
            arr, stats["support"] = apply_palette(arr, PALETTES["pf_support"], full)
        elif name == "pf_blaze":
            arr, stats["blaze"] = apply_palette(arr, PALETTES["pf_blaze"], full)
        else:
            raise KitError(f"no palette for family {name}")
        transform.stats = stats
        return Image.fromarray(arr, "RGBA")

    transform.stats = {}
    return transform


def load_fx_manifest(root: Path) -> tuple[dict[str, Path], dict | None]:
    """``fx/zehr/out/manifest.json`` → {源 sheet 逻辑路径: 染色 PNG 文件}；不存在返回 ({}, None)。

    兼容：顶层平铺 ``{logical: path}``；``{"sheets"|"recolor"|"png"|"pngs"|"files"|"outputs": {…}}``；
    ``{"sheets": [{"source"|"src"|"logical_path": …, "png"|"file"|"path"|"output": …}]}``。
    相对路径先按 manifest 所在目录，再按批目录、仓库根解析。
    """
    path = root / FX_MANIFEST_REL
    if not path.is_file():
        return {}, None
    data = json.loads(path.read_text(encoding="utf-8"))
    table: Any = data
    if isinstance(data, dict):
        for name in ("sheets", "recolor", "png", "pngs", "files", "outputs"):
            if name in data:
                table = data[name]
                break
    pairs: list[tuple[str, str]] = []
    if isinstance(table, dict):
        pairs = [(k, v) for k, v in table.items() if isinstance(k, str) and isinstance(v, str)]
    elif isinstance(table, list):
        for item in table:
            if isinstance(item, dict):
                src = item.get("source") or item.get("src") or item.get("logical_path")
                png = item.get("png") or item.get("file") or item.get("path") or item.get("output")
                if isinstance(src, str) and isinstance(png, str):
                    pairs.append((src, png))
    out: dict[str, Path] = {}
    for src, png in pairs:
        if not (src.startswith("battle/effect/") and src.endswith(".png")):
            continue
        cand = Path(png)
        if not cand.is_absolute():
            for base in (path.parent, root / BATCH, root):
                if (base / cand).is_file():
                    cand = base / cand
                    break
        if not cand.is_file():
            raise KitError(f"fx manifest PNG missing for {src}: {png}")
        out[src] = cand
    return out, {"path": FX_MANIFEST_REL, "sha256": sha256(path.read_bytes()), "entries": len(out)}


def clone_families(ctx) -> tuple[dict[str, dict], list[dict], dict | None]:
    fx_map, fx_info = load_fx_manifest(ctx.root)
    recolor_log: list[dict] = []
    families: dict[str, dict] = {}
    known = set()
    for src_dir, sub, bases in EFFECT_FAMILIES:
        donor = src_dir.rsplit("/", 1)[-1]
        sheet = f"{src_dir}/{donor}.png"
        known.add(sheet)
        _root, atlas_raw, _src = ctx.pack.template_asset(f"{src_dir}/{donor}.atlas.amf3.deflate")
        atlas = ctx.amf_parse(atlas_raw)
        target = fx_map.get(sheet)
        if target is not None:
            def transform(img, target=target, sheet=sheet):
                raw = target.read_bytes()
                new = ctx.png_open(raw)
                if new.size != img.size:
                    raise KitError(f"fx manifest sheet size {new.size} != donor {img.size}: {target}")
                recolor_log.append({"sheet": sheet, "mode": "fx-manifest", "png": str(target),
                                    "png_sha256": sha256(raw)})
                return new
            fam = ctx.clone_effect_family(src_dir, sub, fx_names=list(bases), layout="codename",
                                          png_transform=transform)
        else:
            transform = family_recolor(sub, atlas)
            fam = ctx.clone_effect_family(src_dir, sub, fx_names=list(bases), layout="codename",
                                          png_transform=transform)
            recolor_log.append({"sheet": sheet, "mode": "kit-palette", "family": sub,
                                "pixels_per_rule": transform.stats})
        if fam["missing_effects"] or sorted(fam["copied_bases"]) != sorted(bases):
            raise KitError(f"effect family {src_dir} incomplete: missing={fam['missing_effects']}")
        if fam["dst_dir"] != f"battle/effect/skill_unique/{CODE}/{sub}":
            raise KitError(f"unexpected effect dst {fam['dst_dir']}")
        if sub in SILENT_TIMELINE_FAMILIES:
            fam["silenced_timelines"] = silence_timelines(ctx, fam)
        families[sub] = fam
    unknown = sorted(set(fx_map) - known)
    if unknown:
        raise KitError(f"fx manifest names sheets outside zehr families: {unknown}")
    return families, recolor_log, fx_info


def silence_timelines(ctx, fam: dict) -> list[dict]:
    """新演出层：timeline sounds 清空（避免怪音），sequences 等其余字段原样。"""
    done = []
    for item in fam["files"]:
        target = item["target"]
        if not target.endswith(".timeline.amf3.deflate"):
            continue
        path = ctx.pack.pkg_path(item["root"], target)
        tree = ctx.amf_parse(path.read_bytes())
        before = list(tree.get("sounds") or [])
        if before:
            tree = dict(tree)
            tree["sounds"] = []
            ctx.write_asset(item["root"], target, ctx.amf_bytes(tree), owner="effects")
        done.append({"timeline": target, "sounds_removed": [s.get("path") for s in before],
                     "sequences": tree.get("sequences")})
    return done


# ---------------------------------------------------------------- 技能 DSL

def load_program(ctx, name: str) -> tuple[Any, dict]:
    import wf_dsl
    program, expect = SKILL_SOURCES[name]
    logical = wf_dsl.dsl_logical(program)
    raw = ctx.official_read(logical, "common")
    source = "official"
    if raw is None:
        raw = ctx.live_read(logical)
        source = "live"
    if sha256(raw) != expect:
        raise KitError(f"source DSL fingerprint drift {name} ({source}): {sha256(raw)} != {expect}")
    return ctx.amf_parse(raw), {"program": program, "source": source, "sha256": expect}


def compose_skill(ctx, level: int, sources: dict) -> tuple[list, dict]:
    """移植 design/_tmp/zehr/c8_final_build.py（特效改写换成 rewrite_effect_refs 在调用方做）。"""
    P = SKILL_LEVELS[level]
    tree = copy.deepcopy(sources[f"guildknight_leader_{level}"])
    HW, MS, AS = sources["spry_sailor_hw21_2"], sources["minamoto_sakura_2"], sources["assist"]
    blk = tree[11][1]
    if not (tree[1] == 3 and tree[10] == 0):
        raise KitError("skill head unexpected")
    fa = cmd(blk[0])
    if not (fa[0] == "FindAllSubjects" and fa[1] == 0 and fa[2] == 33):
        raise KitError("skill block0 not FindAllSubjects(0,33)")
    body = fa[9][1]
    if not (cmd(body[0])[0] == "CreateCondition" and cmd(body[0])[2][0][0] == "ACPiercing"):
        raise KitError("skill block0 body[0] not ACPiercing")
    cmd(body[0])[2][0][1] = slv(*P["pierce"])
    fly = copy.deepcopy(cmd(HW[11][1][1])[9][1][1])
    if not (cmd(fly)[2][0][0] == "ACFlying" and cmd(fly)[1] == 3):
        raise KitError("spry_sailor ACFlying donor moved")
    cmd(fly)[1] = 0
    cmd(fly)[2][0][1] = slv(*P["fly"])
    body.append(fly)
    pfd = copy.deepcopy(cmd(MS[11][1][4])[9][1][0])
    if not (cmd(pfd)[2][0][0] == "ACPowerFlipDamage" and cmd(pfd)[1] == 4):
        raise KitError("minamoto_sakura ACPowerFlipDamage donor moved")
    cmd(pfd)[1] = 0
    cmd(pfd)[2][0][1] = slv(*P["pfd_dur"])
    cmd(pfd)[2][0][2] = slv(*P["pfd"])
    body.append(pfd)
    atk = cmd(blk[1])
    if not (atk[0] == "CreateCondition" and atk[1] == -17 and atk[2][0][0] == "ACAttackPoint"):
        raise KitError("skill block1 not self ACAttackPoint")
    ac = cmd(blk[2])
    if ac[0] != "AddCombo":
        raise KitError("skill block2 not AddCombo")
    ac[1] = slv(*P["combo"])
    fn = cmd(blk[4])
    if not (fn[0] == "FindNearSubjects" and fn[3] == 49):
        raise KitError("skill block4 not FindNearSubjects(49)")
    cha = cmd(fn[6][1][0])
    if not (cha[0] == "CreateHitArea" and cha[24] == 0):
        raise KitError("skill dash hit area unexpected")
    cna = find_cmd(cha[23], "CreateNormalAttack")
    if cna[6][0]["max"] not in (13.3, 20):
        raise KitError(f"skill dash multiplier unexpected {cna[6]}")
    cna[6] = slv(*P["slash"])
    cna_tpl = copy.deepcopy(cna)
    for ev in AS[11][1]:
        e = copy.deepcopy(ev)
        w = e[1]
        if w[0] != "Wait":
            raise KitError("assist block not Wait")
        f = cmd(w[3][1][0])
        if not (f[0] == "FindNearSubjects" and f[3] == 51 and f[1] == -17):
            raise KitError("assist FindNearSubjects unexpected")
        f[3] = 49
        bind = f[5]
        f[5] = bind + 100
        h = cmd(f[6][1][0])
        if not (h[0] == "CreateHitArea" and h[2] == bind and h[24] == 0):
            raise KitError("assist hit area unexpected")
        h[2] += 100
        h[19] += 100
        h[21] += 100
        h[22] += 100
        h[4] = 0
        h[5] = 0
        se = cmd(h[20][1][0])
        if not (se[0] == "ShowEffect" and se[3] == h[19] - 100):
            raise KitError("assist ShowEffect subject unexpected")
        se[3] = h[19]
        hit = h[23][1]
        ra = cmd(hit[0])
        if not (ra[0] == "CreateRatioAttack" and ra[1] == h[22] - 100):
            raise KitError("assist CreateRatioAttack unexpected")
        new = copy.deepcopy(cna_tpl)
        new[1] = h[22]
        new[5] = 0
        new[6] = slv(*P["orb"])
        new[13] = slv(2)
        new[14] = slv(2)
        hit[0] = ["Command", new]
        cmd(hit[1])[1] = 1
        blk.append(e)
    total = (P["slash"][0] + 5 * P["orb"][0], P["slash"][1] + 5 * P["orb"][1])
    return tree, {"multiplier_estimate": total}


SKILL_ENHANCED_TOTAL = 2.5      # 强化态（ChangeSkillFlag 536 生效）合计：基值 + alv = 250%
REVISION_SKILL_NODES = {"atk_alv": "ACAttackPoint", "pfd_alv": "ACPowerFlipDamage"}


def revision_value(cell: dict, label: str) -> list[dict]:
    """把计划里的值单元还原成 SLv 值数组（键序与官方一致：min/max/alv_min/alv_max）。"""
    keys = set(cell)
    if keys not in ({"min", "max"}, {"min", "max", "alv_min", "alv_max"}):
        raise KitError(f"{label}: unexpected slv keys {sorted(keys)}")
    return slv(cell["min"], cell["max"], alv_min=cell.get("alv_min"), alv_max=cell.get("alv_max"))


def skill_revision_targets(tree) -> dict[str, list]:
    """改版要改的两个 CreateCondition 值数组（返回可原地改写的 list 引用）。"""
    blk = tree[11][1]
    atk = cmd(blk[1])
    if not (atk[0] == "CreateCondition" and atk[1] == -17 and len(atk[2]) == 1
            and atk[2][0][0] == "ACAttackPoint"):
        raise KitError("skill revision: blk[1] is not self CreateCondition(ACAttackPoint)")
    fa = cmd(blk[0])
    if not (fa[0] == "FindAllSubjects" and fa[2] == 33):
        raise KitError("skill revision: blk[0] is not FindAllSubjects(33)")
    pfd = [cmd(n) for n in fa[9][1]
           if cmd(n)[0] == "CreateCondition" and cmd(n)[2][0][0] == "ACPowerFlipDamage"]
    if len(pfd) != 1:
        raise KitError(f"skill revision: {len(pfd)} ACPowerFlipDamage nodes in FindAllSubjects body")
    return {"atk_alv": atk[2][0], "pfd_alv": pfd[0][2][0]}


def apply_skill_revision(tree, level: int, plan: dict) -> list[dict]:
    """按 plan.json ``skill_dsl.edits`` 改两处 ALv 通道：强化态合计 250%（作者「攻击力提升效果+250%」
    「强化弹射提升效果+250%」）。伤害倍率、块序、判定区、光弹、特效路径一概不动。"""
    targets = skill_revision_targets(tree)
    applied = []
    for edit in plan["skill_dsl"]["edits"]:
        eid = edit["id"]
        if eid not in targets:
            raise KitError(f"skill revision: unknown edit id {eid}")
        node = targets[eid]
        if node[0] != REVISION_SKILL_NODES[eid]:
            raise KitError(f"skill revision {eid}: node is {node[0]}")
        lv = edit[f"lv{level}"]
        old, new = lv["old"], lv["new"]
        if not num_equal(node[2], old):
            raise KitError(f"skill revision {eid} lv{level}: value {node[2]} != plan old {old}")
        built = revision_value(new[0], f"{eid} lv{level}") if len(new) == 1 else None
        if built is None or not num_equal(built, new):
            raise KitError(f"skill revision {eid} lv{level}: rebuilt {built} != plan new {new}")
        cell = built[0]
        if "alv_min" not in cell:
            raise KitError(f"skill revision {eid} lv{level}: new value has no ALv channel: {cell}")
        if float(cell["min"]) + float(cell["alv_min"]) != SKILL_ENHANCED_TOTAL or \
                float(cell["max"]) + float(cell["alv_max"]) != SKILL_ENHANCED_TOTAL:
            raise KitError(f"skill revision {eid} lv{level}: enhanced total != {SKILL_ENHANCED_TOTAL}: {cell}")
        node[2] = built
        applied.append({"id": eid, "node": node[0], "old": old, "new": built,
                        "enhanced_total": SKILL_ENHANCED_TOTAL})
    if len(applied) != 2:
        raise KitError(f"skill revision: expected 2 edits, applied {len(applied)}")
    return applied


def skill_revision_state(tree) -> dict[str, list[dict]]:
    """从成品树回读两个值数组（门禁用）。"""
    return {eid: node[2] for eid, node in skill_revision_targets(tree).items()}


# ---------------------------------------------------------------- PF DSL

def apk_pf_sources(root: Path) -> tuple[dict[str, bytes], str]:
    """APK assets/bundle.zip 内官方 knight/supporter lv1-3（按 wf_gerald_native_pf_dsl.SOURCE_HASHES 验指纹）。"""
    import wf_dsl
    import wf_gerald_native_pf_dsl as gpf
    import wf_mod_tool as core
    want = {}
    for level in (1, 2, 3):
        for kind in ("knight", "supporter"):
            d = core.sha1_path(wf_dsl.dsl_logical(f"battle/action/power_flip/action/{kind}${kind}_lv{level}"))
            want[f"{kind}_lv{level}"] = d[:2] + "/" + d[2:]
    apks = sorted((root / "弹国服").glob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True)
    for apk in apks:
        with zipfile.ZipFile(apk) as z:
            if "assets/bundle.zip" not in z.namelist():
                continue
            inner = zipfile.ZipFile(io.BytesIO(z.read("assets/bundle.zip")))
            names = [n for n in inner.namelist() if not n.endswith("/")]
            found = {}
            for label, tail in want.items():
                hits = [n for n in names if n.endswith(tail)]
                for hit in hits:
                    raw = inner.read(hit)
                    if sha256(raw) == gpf.SOURCE_HASHES[label]:
                        found[label] = raw
                        break
            if len(found) == len(want):
                return found, apk.name
    raise KitError("no APK bundle provides the fingerprinted official knight/supporter PF DSLs")


def compose_pf(level: int, sources: dict[str, bytes]) -> tuple[list, dict]:
    import wf_gerald_native_pf_dsl as gpf
    tree = gpf.compose(sources[f"knight_lv{level}"], sources[f"supporter_lv{level}"], level)
    sp, off = PF_LEVELS[level], PF_OFFICIAL[level]
    blk = tree[11][1]
    if not (tree[1] == 1 and tree[10] == 0):
        raise KitError("PF head unexpected")
    sup = cmd(blk[0])
    if sup[0] != "SetPowerFilpSuppress" or sup[1] != off["supp"]:
        raise KitError(f"PF lv{level} suppress {sup}")
    sup[1] = sp["supp"]
    h = cmd(blk[1])
    if not (h[0] == "CreateHitArea" and h[2] == -18 and h[24] == 0):
        raise KitError("PF knight hit area unexpected")
    if (h[13][1], h[14][1]) != (off["life"], off["hits"]):
        raise KitError(f"PF lv{level} life/hits {(h[13], h[14])}")
    h[13][1] = sp["life"]
    h[14][1] = sp["hits"]
    cna = cmd(h[23][1][0])
    if cna[0] != "CreateNormalAttack" or (cna[6][0]["max"], cna[13][0]["max"], cna[14][0]["max"]) != \
            (off["mult"], off["det"], off["fev"]):
        raise KitError(f"PF lv{level} knight attack unexpected {cna}")
    cna[6] = slv(PF_SEGMENT_MULTIPLIER[level])
    cna[13] = slv(sp["det"])
    cna[14] = slv(sp["fev"])
    w = blk[2][1]
    if not (w[0] == "Wait" and cmd(w[3][1][0])[0] == "NotifyPowerflipEnd" and w[1] == off["wait"]):
        raise KitError("PF Wait→NotifyPowerflipEnd unexpected")
    w[1] = sp["wait"]
    buffs = []
    for node in iter_commands(blk[3:], "CreateCondition"):
        acn = node[2][0]
        buffs.append((acn[0], acn[1][0]["max"]))
        if acn[0] == "ACAttackPoint":
            acn[1] = slv(sp["atk_dur"])
        elif acn[0] in ("ACPiercing", "ACFlying"):
            acn[1] = slv(sp["pf_dur"])
    return tree, {"official": off, "new": dict(sp, mult=PF_SEGMENT_MULTIPLIER[level]), "support_buffs_before": buffs}


def _slv_max(value) -> float:
    if not (isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict)):
        raise KitError(f"expected single-level value, got {str(value)[:60]}")
    return float(value[0]["max"])


def pf_attack_budget(tree) -> list[dict]:
    """树内每个 CreateHitArea 的 CreateNormalAttack 按满命中计：倍率/削韧(p13)/Fever 点(p14) × 最大命中数。
    判定区按出现顺序；PF 树第一个即剑士回旋斩（blk[1]，subject -18）。"""
    out: list[dict] = []

    def rec(node, area):
        if not isinstance(node, list):
            return
        if len(node) == 2 and node[0] == "Command" and isinstance(node[1], list) and node[1]:
            c = node[1]
            if c[0] == "CreateHitArea":
                hits = c[14]
                if not (isinstance(hits, list) and hits[0] == "CalculatedUsingMaxNumOfHits"):
                    raise KitError(f"hit area {c[1]!r} hit count form {hits}")
                entry = {"area": c[1], "subject": c[2], "hits": int(hits[1]), "attacks": []}
                out.append(entry)
                for child in c[1:]:
                    rec(child, entry)
                return
            if c[0] in ("CreateRatioAttack", "CreateFixedAttack"):
                raise KitError(f"PF budget does not model {c[0]}")
            if c[0] == "CreateNormalAttack":
                if area is None:
                    raise KitError("CreateNormalAttack outside a hit area")
                area["attacks"].append({"mult": _slv_max(c[6]), "break": _slv_max(c[13]),
                                        "fever": _slv_max(c[14])})
        for child in node:
            rec(child, area)

    rec(tree, None)
    for entry in out:
        n = entry["hits"]
        entry["damage"] = round(sum(a["mult"] for a in entry["attacks"]) * n, 6)
        entry["break"] = round(sum(a["break"] for a in entry["attacks"]) * n, 6)
        entry["fever"] = round(sum(a["fever"] for a in entry["attacks"]) * n, 6)
    return [e for e in out if e["attacks"]]


def pf_budget_report(level: int, tree, sources: dict[str, bytes]) -> dict:
    """包内 PF 与官方剑士 + 官方辅助（同档）满命中预算对比。剑士段总伤必须恰为官方 3 倍（主控覆盖）。"""
    import wf_dsl
    new = pf_attack_budget(tree)
    knight = pf_attack_budget(wf_dsl.parse_dsl(zlib.decompress(sources[f"knight_lv{level}"], -15))["tree"])
    support = pf_attack_budget(wf_dsl.parse_dsl(zlib.decompress(sources[f"supporter_lv{level}"], -15))["tree"])
    if len(knight) != 1 or not new or new[0]["subject"] != -18:
        raise KitError(f"PF lv{level} budget shape unexpected: new={new} knight={knight}")

    def total(entries, field):
        return round(sum(e[field] for e in entries), 6)

    official_all = knight + support
    rep = {
        "knight": {"new": {f: new[0][f] for f in ("hits", "damage", "break", "fever")},
                   "official": {f: knight[0][f] for f in ("hits", "damage", "break", "fever")}},
        "total": {"new": {f: total(new, f) for f in ("damage", "break", "fever")},
                  "official": {f: total(official_all, f) for f in ("damage", "break", "fever")}},
        "support_attacks": {"new": [e["damage"] for e in new[1:]], "official": [e["damage"] for e in support]},
    }
    rep["ratio"] = {
        "knight_damage": round(rep["knight"]["new"]["damage"] / rep["knight"]["official"]["damage"], 4),
        "total_damage": round(rep["total"]["new"]["damage"] / rep["total"]["official"]["damage"], 4),
        "total_break": round(rep["total"]["new"]["break"] / rep["total"]["official"]["break"], 4),
        "total_fever": round(rep["total"]["new"]["fever"] / rep["total"]["official"]["fever"], 4),
    }
    if abs(rep["knight"]["new"]["damage"] - 3 * rep["knight"]["official"]["damage"]) > 1e-6:
        raise KitError(f"PF lv{level} knight segment damage {rep['knight']} is not 3× official")
    return rep


def pf_budget_note(budgets: dict[int, dict]) -> str:
    def seq(fn):
        return "/".join(fn(budgets[lv]) for lv in (1, 2, 3))

    def num(x):
        return f"{x:g}"
    return ("PF 满命中预算（Lv1/2/3，对比官方剑士＋同档官方辅助）：剑士回旋斩总伤 "
            f"{seq(lambda b: num(b['knight']['new']['damage']))}×＝官方 {seq(lambda b: num(b['knight']['official']['damage']))}× 的 3 倍；"
            f"含辅助段合计 {seq(lambda b: num(b['total']['new']['damage']))}×（官方 {seq(lambda b: num(b['total']['official']['damage']))}×，"
            f"{seq(lambda b: format(b['ratio']['total_damage'], '.2f'))} 倍，Lv3 辅助全屏 4× 未乘 3）；"
            f"削韧 {seq(lambda b: num(b['total']['new']['break']))}（官方 {seq(lambda b: num(b['total']['official']['break']))}，"
            f"约 {seq(lambda b: format(b['ratio']['total_break'], '.2f'))} 倍）；"
            f"Fever 点 {seq(lambda b: num(b['total']['new']['fever']))}（官方 {seq(lambda b: num(b['total']['official']['fever']))}，"
            f"{seq(lambda b: format(b['ratio']['total_fever'], '.2f'))} 倍）。实战按命中率打折，不是恒定 3 倍")


def add_blaze_layer(tree: list, level: int, blaze_family: dict) -> list:
    """在 knight 判定区 onCreate 块里、spin 之前插入新演出层（同 subject / UntilTargetTerminates；
    坐标系改 AB：火焰朝屏幕上方，不随球向旋转；先插入的层画在 spin 之下）。"""
    blk = tree[11][1]
    h = cmd(blk[1])
    on_create = h[20][1]
    spins = [n for n in on_create if n[0] == "Command" and n[1][0] == "ShowEffect"]
    if len(spins) != 1:
        raise KitError("PF knight onCreate must hold exactly one spin ShowEffect")
    spin = spins[0][1]
    if spin[5] != ["UntilTargetTerminates"] or spin[3] != h[19]:
        raise KitError(f"spin ShowEffect not bound to hit area: {spin}")
    layer = blaze_node(spin, f"{blaze_family['src_dir']}/{PF_BLAZE_BASE}", level)
    on_create.insert(0, ["Command", layer])
    return tree


def blaze_node(spin: list, path: str, level: int) -> list:
    layer = copy.deepcopy(spin)
    layer[1] = PF_BLAZE_LABEL
    layer[2] = ["SpecifyEffectDirectly", path]
    layer[6] = ["AB"]
    layer[12] = ["Some", slv(PF_BLAZE_SCALE[level])]
    return layer


def expected_pf_tree(root: Path, level: int, blaze_dst: str) -> list:
    """设计定稿 PF 树 + 主控覆盖（倍率恢复官方、叠加 blaze 层）= 期望树。"""
    design = json.loads((root / DESIGN_TMP_REL / f"final_pf_lv{level}.json").read_text(encoding="utf-8"))
    h = cmd(design[11][1][1])
    cna = cmd(h[23][1][0])
    if cna[6] != slv(DESIGN_PF_SEGMENT_MULTIPLIER[level]):
        raise KitError(f"design PF lv{level} multiplier {cna[6]} != {DESIGN_PF_SEGMENT_MULTIPLIER[level]}")
    cna[6] = slv(PF_SEGMENT_MULTIPLIER[level])
    h[20][1].insert(0, ["Command", blaze_node(h[20][1][0][1], f"{blaze_dst}/{PF_BLAZE_BASE}", level)])
    return design


# ---------------------------------------------------------------- 校验（kit 内即时断言；完整门禁在 impl/zehr/gates.py）

# 移植自 research/_tmp/blueprint_build.py 的 check（问题文本逐字相同；单测对原模块做等价核对）。
# 不再运行时 import 研究目录、不换 sys.stdout、不改 cwd。
_BP_LOOKUP = {"StopBall": [1], "ShowEffect": [3], "AddSkillPoint": [1], "CreateCondition": [1], "CreateHitArea": [2],
              "CreateNormalAttack": [1], "CreateRatioAttack": [1], "CreateFixedAttack": [1], "CreateRatioHeal": [1],
              "FindNearSubjects": [1], "CreateReferencePoint": [1], "MoveHitArea": [1], "RotateHitArea": [1]}
_BP_BUILTIN = {-1, -2, -17, -18, -33}
_OFFICIAL_SIG_CACHE: dict[str, tuple[dict[str, list[str]], str]] = {}


def official_sig_problems(root: Path) -> list[str]:
    """两处候选都缺或 sha 都不等于 pin 时返回原因清单（空 = 可用）。"""
    probs = []
    for rel in OFFICIAL_SIG_CANDIDATES:
        path = root / rel
        if not path.is_file():
            probs.append(f"{rel}: missing")
            continue
        got = sha256(path.read_bytes())
        if got == OFFICIAL_SIG_PIN:
            return []
        probs.append(f"{rel}: sha256 {got} != pin {OFFICIAL_SIG_PIN}")
    return probs


def load_official_sig(root: Path) -> tuple[dict[str, list[str]], str]:
    """按 OFFICIAL_SIG_CANDIDATES 顺序取第一份 sha 等于 pin 的签名表；都不可用时 KitError（带清单与再生方法）。"""
    key = str(root)
    if key not in _OFFICIAL_SIG_CACHE:
        for rel in OFFICIAL_SIG_CANDIDATES:
            path = root / rel
            if path.is_file():
                raw = path.read_bytes()
                if sha256(raw) == OFFICIAL_SIG_PIN:
                    _OFFICIAL_SIG_CACHE[key] = (json.loads(raw.decode("utf-8")), rel)
                    break
        else:
            raise KitError("official DSL signature table unavailable: " + "; ".join(official_sig_problems(root))
                           + f"（work/ 被 gitignore；从 {OFFICIAL_SIG_CANDIDATES[1]} 复制到 {OFFICIAL_SIG_CANDIDATES[0]}，"
                             "或用 research/_tmp/official_sig.py 重新生成后核对差异并更新 OFFICIAL_SIG_PIN）")
    return _OFFICIAL_SIG_CACHE[key]


def _bp_tag(v):
    return v[0] if isinstance(v, list) and v and isinstance(v[0], str) else None


def _bp_kind(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "num"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        if v and all(isinstance(x, dict) for x in v):
            return "slv"
        t = _bp_tag(v)
        if t in ("Block", "Command", "Event"):
            return "expr"
        if t is not None:
            return "enum:" + t
        return "list"
    return "dict"


def blueprint_check_with_sig(tree, off: dict[str, list[str]]) -> tuple[list[str], int, bool]:
    """官方签名差分 / 参数个数 / 作用域 C16103 / GH / CD 挂 -17/-18 / Rectangle 三元组 / 绑定 id 重复 /
    AMF3 往返 / 我方方向。"""
    import wf_dsl
    import wf_dsl_sig as SIG
    probs: list[str] = []
    ids_seen: dict[Any, int] = {}

    def seen(x):
        ids_seen[x] = ids_seen.get(x, 0) + 1

    def walk(n, scope):
        t = _bp_tag(n)
        if t == "Block":
            for x in n[1]:
                walk(x, scope)
            return
        if t == "Event":
            ev = n[1]
            if ev[0] not in SIG.EVENTS:
                probs.append("未知事件 " + ev[0])
            elif len(ev) - 1 != len(SIG.EVENTS[ev[0]]):
                probs.append(f"事件参数数 {ev[0]} {len(ev) - 1}")
            for x in ev[1:]:
                if _bp_tag(x) in ("Block", "Command", "Event"):
                    walk(x, scope)
            return
        if t == "Command":
            c = n[1]
            nm = c[0]
            if nm not in SIG.COMMANDS:
                probs.append("未知命令 " + nm)
                return
            if len(c) - 1 != len(SIG.COMMANDS[nm]):
                probs.append(f"参数数 {nm} {len(c) - 1}!={len(SIG.COMMANDS[nm])}")
            for i, p in enumerate(c[1:], 1):
                k = _bp_kind(p)
                official = set(off.get(f"{nm}#{i}", []))
                kk = "enum" if k.startswith("enum:") else k
                offk = {("enum" if x.startswith("enum:") else x) for x in official}
                if official and kk not in offk:
                    probs.append(f"形状 {nm} p{i} kind={k} 官方={sorted(official)}")
                if k.startswith("enum:"):
                    en = p[0]
                    for j, q in enumerate(p[1:], 1):
                        o2 = set(off.get(f"{nm}#{i}>{en}#{j}", [])) or set(off.get(f"{en}#{j}", []))
                        if o2 and _bp_kind(q) not in o2:
                            probs.append(f"形状 {nm} p{i} {en}#{j} kind={_bp_kind(q)} 官方={sorted(o2)}")
            for i in _BP_LOOKUP.get(nm, []):
                if isinstance(c[i], int) and c[i] not in _BP_BUILTIN and c[i] not in scope:
                    probs.append(f"C16103风险 {nm} p{i}={c[i]} 不在作用域 {sorted(scope)}")
            for p in c[1:]:
                if _bp_tag(p) == "GH" and p[1] not in _BP_BUILTIN and p[1] not in scope:
                    probs.append(f"GH({p[1]}) 不在作用域")
                if _bp_tag(p) == "CD" and nm in _BP_LOOKUP and c[_BP_LOOKUP[nm][0]] in (-17, -18):
                    probs.append(f"{nm} CD 挂在 {c[_BP_LOOKUP[nm][0]]} 必 throw")
            if nm == "FindAllSubjects":
                walk(c[9], scope | {c[1]})
                seen(c[1])
            elif nm == "FindNearSubjects":
                walk(c[6], scope | {c[5]})
                seen(c[5])
            elif nm == "CreateReferencePoint":
                walk(c[11], scope | {c[10]})
                seen(c[10])
            elif nm == "CreateReferencePointAtSpecifiedPosition":
                walk(c[5], scope | {c[4]})
            elif nm == "CreateHitArea":
                walk(c[20], scope | {c[19]})
                walk(c[23], scope | {c[21], c[22]})
                for x in (c[19], c[21], c[22]):
                    seen(x)
                sh = c[9]
                if _bp_tag(sh) == "Rectangle" and len(sh) != 3:
                    probs.append("Rectangle 非三元组(F1009)")
            else:
                for x in c[1:]:
                    if _bp_tag(x) in ("Block", "Command", "Event"):
                        walk(x, scope)
            return
        probs.append("非法节点 " + json.dumps(n, ensure_ascii=False)[:60])

    if tree[0] != "ActionDsl" or len(tree) != 12:
        probs.append("根头形状不对")
    walk(tree[11], set())
    dup = [k for k, v in ids_seen.items() if v > 1]
    if dup:
        probs.append(f"绑定 id 重复 {dup}")
    enc = wf_dsl.encode_amf3(tree)
    rt = wf_dsl.parse_dsl(enc)["tree"] == tree
    probs += wf_dsl.player_side_dsl_problems(tree)
    return probs, len(enc), rt


def required_input_problems(root: Path) -> list[str]:
    """kit 依赖的未跟踪输入（work/ 被 gitignore）。fx manifest 与 gates.json 允许缺（只影响染色来源 / status）。"""
    probs = []
    for rel, use in ((DESIGN_REL, "上一轮设计定稿：语音路由 / 能量 / PF 与技能定稿树 / 不变字符串的来源"),
                     (REVISION_REL, "2026-09-16 作者改版计划：队长/词条行、固有状态、覆盖文案、技能 ALv 的唯一来源"),
                     *((f"{DESIGN_TMP_REL}/final_skill_{lv}.json", f"技能 {lv} 定稿树（逐节点比对）") for lv in (1, 2)),
                     *((f"{DESIGN_TMP_REL}/final_pf_lv{lv}.json", f"PF Lv{lv} 定稿树（逐节点比对）") for lv in (1, 2, 3))):
        if not (root / rel).is_file():
            probs.append(f"{rel} missing（{use}）")
    probs += [f"official_sig: {p}" for p in official_sig_problems(root)]
    return probs


def workspace_path_budget(workspace: Path, batch_dir: Path, key: str = KEY, *,
                          extra_rel: tuple[str, ...] = (), exclude_rel: tuple[str, ...] = ()) -> dict[str, Any]:
    """框架 --step inspect 把 workspace 复制到 <batch>/_inspect/<key>-<pid>/<ws 名>/ 下：
    按 7 位 PID 估副本全长，返回最长条目与余量（负数 = copytree 必然 MAX_PATH 失败）。
    ``extra_rel`` 计入即将写入的条目，``exclude_rel`` 排除即将删除的条目（相对 workspace 的 posix 路径）。"""
    ws = Path(os.path.normpath(workspace))
    copy_prefix = len(str(Path(os.path.normpath(batch_dir)) / "_inspect" / f"{key}-{'9' * INSPECT_PID_DIGITS}" / ws.name))
    rels = [p.relative_to(ws).as_posix() for p in ws.rglob("*")] if ws.is_dir() else []
    rels = [r for r in rels if r not in set(exclude_rel)] + list(extra_rel)
    longest = max(rels, key=len) if rels else ""
    copy_len = copy_prefix + 1 + len(longest) if longest else copy_prefix
    return {"copy_prefix": copy_prefix, "longest_rel": longest, "real_len": len(str(ws)) + 1 + len(longest),
            "copy_len": copy_len, "limit": WIN_MAX_PATH, "headroom": WIN_MAX_PATH - copy_len}


def typed_signature_problems(tree) -> list[str]:
    """wf_dsl_sig 类型表逐参数核对「Array 参必须是数组、表达式参必须是表达式、枚举构造名属于该枚举」（F1034/F1009）。"""
    import wf_dsl_sig as SIG
    probs: list[str] = []
    exprs = ("Block", "Command", "Event")

    def check_value(typ: str, value, where: str) -> None:
        # 官方 1052 棵技能树正向对照：null 只出现在对象型参数（枚举 HitCountCheckTargetKind 1452 处、
        # CreateSummonsMultiball 表达式 49 处），Array/数值/布尔参从不为 null。
        if value is None and typ not in ("Array", "int", "Number", "Boolean"):
            return
        if typ == "Array":
            if not isinstance(value, list):
                probs.append(f"{where}: Array param got {type(value).__name__}")
            elif value and isinstance(value[0], str) and value[0] in exprs:
                probs.append(f"{where}: Array param got expression")
        elif typ == "ActionDslExpression":
            if not (isinstance(value, list) and value and value[0] in exprs):
                probs.append(f"{where}: expression param got {str(value)[:40]}")
            else:
                walk_expr(value)
        elif typ in SIG.ENUMS:
            if not (isinstance(value, list) and value and isinstance(value[0], str)):
                probs.append(f"{where}: enum {typ} got {str(value)[:40]}")
                return
            ctors = SIG.ENUMS[typ]
            if value[0] not in ctors:
                probs.append(f"{where}: {value[0]} is not a {typ} constructor")
                return
            args = ctors[value[0]]
            if len(value) - 1 != len(args):
                probs.append(f"{where}: {typ}.{value[0]} arity {len(value) - 1} != {len(args)}")
            for j, (t2, v2) in enumerate(zip(args, value[1:]), 1):
                check_value(t2, v2, f"{where}>{value[0]}#{j}")
        elif typ in ("int", "Number"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                probs.append(f"{where}: {typ} got {type(value).__name__}")
        elif typ == "Boolean":
            if not isinstance(value, bool):
                probs.append(f"{where}: Boolean got {type(value).__name__}")
        elif typ == "String":
            if not isinstance(value, str):
                probs.append(f"{where}: String got {type(value).__name__}")

    def walk_expr(node) -> None:
        if not (isinstance(node, list) and node):
            probs.append(f"bad expression {str(node)[:40]}")
            return
        if node[0] == "Block":
            for item in node[1]:
                walk_expr(item)
            return
        if node[0] in ("Command", "Event"):
            registry = SIG.COMMANDS if node[0] == "Command" else SIG.EVENTS
            c = node[1]
            if c[0] not in registry:
                probs.append(f"unknown {node[0]} {c[0]}")
                return
            sig = registry[c[0]]
            if len(c) - 1 != len(sig):
                probs.append(f"{c[0]} arity {len(c) - 1} != {len(sig)}")
            for i, (typ, value) in enumerate(zip(sig, c[1:]), 1):
                check_value(typ, value, f"{c[0]}#{i}")
            return
        probs.append(f"not an expression: {str(node)[:40]}")

    if not (isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl"):
        return ["root is not a bare ActionDsl tree"]
    walk_expr(tree[11])
    return probs


def dsl_problems(root: Path, tree) -> dict[str, Any]:
    import wf_client_legality as L
    import wf_dsl
    off, _sig_source = load_official_sig(root)
    bp, size, rt = blueprint_check_with_sig(tree, off)
    enc = wf_dsl.encode_amf3(tree)
    rt2 = strict_equal(wf_dsl.parse_dsl(enc)["tree"], tree)
    donothing = [c[0] for c in iter_commands(tree) for p in c[1:]
                 if isinstance(p, list) and p and p[0] == "Block" and ["DoNothing"] in p[1]]
    probs = {
        "blueprint_check": list(bp),
        "typed_signature": typed_signature_problems(tree),
        "element": L.action_dsl_element_problems(tree, ELEMENT),
        "subject_binding": L.action_dsl_subject_binding_problems(tree),
        "hit_area_target": L.action_dsl_hit_area_target_problems(tree),
        "player_side_direction": wf_dsl.player_side_dsl_problems(tree),
        "donothing_in_block": donothing,
    }
    return {"problems": probs, "all_empty": not any(probs.values()), "amf3_bytes": size,
            "roundtrip": bool(rt and rt2)}


def effect_ref_problems(ctx, tree) -> list[str]:
    import wf_assets
    probs = []
    for c in iter_commands(tree):
        for p in c[1:]:
            refs = []
            if isinstance(p, list) and len(p) == 2 and p[0] == "SpecifyEffectDirectly":
                refs.append(p[1])
            elif isinstance(p, list) and p and p[0] == "SpecifyHitEffectDirectly":
                inner = p[1]
                if isinstance(inner, list) and len(inner) == 2 and inner[0] == "SpecifyEffectDirectly":
                    refs.append(inner[1])
            for path in refs:
                for kind in ("parts", "timeline"):
                    logical = f"{path}.{kind}.amf3.deflate"
                    if not (ctx.pack.pkg_has("common", logical) or wf_assets.locate(ctx.store, logical)):
                        probs.append(f"unresolved {c[0]} {logical}")
    return probs


def drop_stale_pf_programs(ctx) -> list[str]:
    """删掉旧 kit 按设计长路径写入的三档 PF DSL（已被 pf_program 短路径取代），并撤销其 kit 登记。
    只动登记为 kit（或未登记）的文件；manifest 重扫 roots 时自然不再声明它们。"""
    import wf_dsl
    import wf_seasonal7_common as C
    removed = []
    owned = ctx.pack._owned_raw()
    for level in (1, 2, 3):
        old = wf_dsl.dsl_logical(design_pf_program(level))
        if old == wf_dsl.dsl_logical(pf_program(level)):
            continue
        record = owned.get(f"common:{old}")
        if record is not None and record.get("owner") != "kit":
            raise KitError(f"stale PF program {old} is owned by {record.get('owner')}, not kit")
        path = ctx.pack.pkg_path("common", old)
        if path.is_file():
            path.unlink()
            removed.append(old)
        owned.pop(f"common:{old}", None)
    if removed or any(f"common:{wf_dsl.dsl_logical(design_pf_program(lv))}" in ctx.pack._owned_raw()
                      for lv in (1, 2, 3)):
        ctx.pack.write_evidence(C.OWNED_FILE, dict(sorted(owned.items())))
    return removed


# ---------------------------------------------------------------- 像素小人 / 语音（Integrate 阶段）

PIXEL_DIR_REL = f"{BATCH}/pixel/zehr"
PIXEL_VERIFY_REL = f"{BATCH}/pixel/_review/verify_all.json"
# sheet 基名 → 同组元数据（atlas / frame / timeline）；元数据保持母本，只有 character/<母本>/ 前缀由 assets 改写
PIXEL_SHEETS = {
    "sprite_sheet": ("sprite_sheet.atlas.amf3.deflate", "pixelart.frame.amf3.deflate",
                     "pixelart.timeline.amf3.deflate"),
    "special_sprite_sheet": ("special_sprite_sheet.atlas.amf3.deflate", "special.frame.amf3.deflate",
                             "special.timeline.amf3.deflate"),
}
SPEECH = "master/character/character_speech.orderedmap"


def pixel_inputs(root: Path) -> tuple[dict[str, Path], list[str]]:
    """像素染色产物是否可装包（与 philia / regis kit 同一判据）：``pixel/zehr/report.json`` 门禁全过、
    ``pixel/_review/verify_all.json`` 的 zehr 复核全过（REVIEW.md §5 修复轮），两者记录的 sha256 =
    ``out/<sheet>.png`` 当前字节。返回 ({sheet 基名: PNG 路径}, problems)；problems 非空 = pending（不装包）。"""
    probs: list[str] = []
    base = root / PIXEL_DIR_REL
    report_path, verify_path = base / "report.json", root / PIXEL_VERIFY_REL
    if not report_path.is_file():
        return {}, [f"pixel report absent: {PIXEL_DIR_REL}/report.json"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("key") != KEY or report.get("gates_passed") is not True:
        probs.append(f"pixel report gates_passed={report.get('gates_passed')} key={report.get('key')}")
    failed = sorted(k for k, v in (report.get("gates") or {}).items() if not (isinstance(v, dict) and v.get("ok")))
    if failed:
        probs.append(f"pixel report gates failed: {failed}")
    verify = json.loads(verify_path.read_text(encoding="utf-8")).get(KEY) if verify_path.is_file() else None
    if not verify:
        probs.append(f"pixel review verdict absent: {PIXEL_VERIFY_REL}")
    else:
        hard_bad = sorted(k for k, v in (verify.get("hard") or {}).items() if not v.get("ok"))
        if verify.get("pass") is not True or hard_bad:
            probs.append(f"pixel review failed: pass={verify.get('pass')} hard={hard_bad}")
    out: dict[str, Path] = {}
    reviewed = (((verify or {}).get("hard") or {}).get("H8_png_roundtrip") or {}).get("detail") or {}
    for name in PIXEL_SHEETS:
        png = base / "out" / f"{name}.png"
        if not png.is_file():
            probs.append(f"pixel output missing: {png.name}")
            continue
        digest = sha256(png.read_bytes())
        rep_sha = ((report.get("outputs") or {}).get(name) or {}).get("sha256")
        if rep_sha != digest:
            probs.append(f"{name}.png sha256 != pixel report outputs ({rep_sha})")
        if (reviewed.get(name) or {}).get("sha256") != digest:
            probs.append(f"{name}.png sha256 != reviewed verify_all H8 sha")
        out[name] = png
    return out, probs


def pixel_problems(ctx, *, check_owner: bool = True) -> list[str]:
    """包内像素小人核对（不写盘）：sheet 为存储态（小写魔数）且解码字节 = 染色 PNG 原字节；尺寸 / alpha = 母本；
    染色所据母本 sha = 当前母本；atlas/frame/timeline = 母本树（仅 character/<母本>/ 前缀改写）；
    归属 owner=pixel 且登记 sha = 盘上字节。"""
    import wf_assets
    spec = ctx.spec
    pngs, probs = pixel_inputs(ctx.root)
    if probs:
        return [f"pixel inputs not ready: {p}" for p in probs]
    report = json.loads((ctx.root / PIXEL_DIR_REL / "report.json").read_text(encoding="utf-8"))
    sources = report.get("source_files") or {}
    prefix = {f"character/{spec.template_code}/": f"character/{spec.code}/"}
    for name, metas in PIXEL_SHEETS.items():
        logical = f"character/{CODE}/pixelart/{name}.png"
        tpl_logical = f"character/{spec.template_code}/pixelart/{name}.png"
        if not ctx.pack.pkg_has("common", logical):
            probs.append(f"package pixel sheet missing {logical}")
            continue
        raw = ctx.pack.pkg_path("common", logical).read_bytes()
        if raw[:8] != wf_assets.PNG_FAKE:
            probs.append(f"{logical} lacks store PNG magic")
            continue
        if wf_assets.png_decode(raw) != pngs[name].read_bytes():
            probs.append(f"{logical} != {PIXEL_DIR_REL}/out/{name}.png (store form)")
        _r, donor_raw, _src = ctx.pack.template_asset(tpl_logical)
        if (sources.get(tpl_logical) or {}).get("sha256") != sha256(donor_raw):
            probs.append(f"{tpl_logical}: template bytes != pixel report source_files sha (recolor base drift)")
        pkg_img, donor = ctx.png_open(raw), ctx.png_open(donor_raw)
        if pkg_img.size != donor.size:
            probs.append(f"{logical} size {pkg_img.size} != donor {donor.size}")
        elif pkg_img.getchannel("A").tobytes() != donor.getchannel("A").tobytes():
            probs.append(f"{logical} alpha differs from donor {tpl_logical}")
        if check_owner:
            record = ctx.pack.owned_record("common", logical) or {}
            if record.get("owner") != "pixel" or record.get("sha256") != sha256(raw):
                probs.append(f"{logical} owner record {record} (expected pixel + current sha)")
        for meta in metas:
            pkg_meta = f"character/{CODE}/pixelart/{meta}"
            if not ctx.pack.pkg_has("common", pkg_meta):
                probs.append(f"package pixel metadata missing {pkg_meta}")
                continue
            _r, tpl_raw, _src = ctx.pack.template_asset(f"character/{spec.template_code}/pixelart/{meta}")
            if (sources.get(f"character/{spec.template_code}/pixelart/{meta}") or {}).get("sha256") not in (None, sha256(tpl_raw)):
                probs.append(f"{meta}: template bytes != pixel report source_files sha")
            want = ctx.replace_strings(ctx.amf_parse(tpl_raw), prefix)
            if ctx.amf_parse(ctx.pack.pkg_path("common", pkg_meta).read_bytes()) != want:
                probs.append(f"{pkg_meta} differs from donor metadata (only path prefix may change)")
    return probs


def install_pixel(ctx) -> dict[str, Any]:
    """把复核通过的像素染色 sheet 以存储态（``wf_assets.png_encode``：只换小写魔数，PNG 字节不重编码）写进包，
    owner=pixel。重跑幂等：字节相同不改盘，登记 sha 不变。产物未就绪时不写、返回 pending（包内保持母本原色）。"""
    import wf_assets
    pngs, probs = pixel_inputs(ctx.root)
    if probs:
        return {"status": "pending", "problems": probs}
    written = {}
    for name, png in pngs.items():
        logical = f"character/{CODE}/pixelart/{name}.png"
        raw = png.read_bytes()
        data = wf_assets.png_encode(raw)
        if data[:8] != wf_assets.PNG_FAKE or wf_assets.png_decode(data) != raw:
            raise KitError(f"pixel store-form roundtrip failed: {png}")
        ctx.write_asset("common", logical, data, owner="pixel")
        written[logical] = {"source": f"{PIXEL_DIR_REL}/out/{png.name}", "decoded_sha256": sha256(raw),
                            "store_sha256": sha256(data), "size": list(ctx.png_open(data).size)}
    after = pixel_problems(ctx)
    if after:
        raise KitError(f"pixel sheets did not land in the package: {after}")
    return {"status": "installed", "sheets": written, "problems": []}


def voice_state(ctx) -> dict[str, Any]:
    """只读：语音是否已由 ``wf_seasonal7_voice pack`` + ``impl/zehr/voice_merge.py`` 装包（22 槽文件在包内、
    归属 voice 且登记 sha = 盘上字节；speech 8 行引用新槽；无多余旧母本语音；character_text c11 = AI 合成配音）。"""
    import wf_seasonal7_voice as V
    missing = [s for s in V.SLOTS if not ctx.pack.pkg_has("common", f"character/{CODE}/voice/{s}.mp3")]
    not_voice_owned = []
    for s in V.SLOTS:
        logical = f"character/{CODE}/voice/{s}.mp3"
        if s in missing:
            continue
        record = ctx.pack.owned_record("common", logical) or {}
        if record.get("owner") != "voice" or record.get("sha256") != sha256(ctx.pack.pkg_path("common", logical).read_bytes()):
            not_voice_owned.append(s)
    speech_flat = ctx.pkg_flat(SPEECH) if ctx.pack.pkg_has("common", SPEECH) else {}
    speech = ctx.csv_split(speech_flat[CID]) if speech_flat.get(CID) else []
    refs = [cells[4] for cells in speech if len(cells) == 5]
    want_refs = [*V.HOME_SLOTS, "ally/join", "ally/evolution"]
    base = ctx.pack.package / "roots" / "common" / "character" / CODE / "voice"
    extra = sorted(p.relative_to(base).as_posix() for p in base.rglob("*")
                   if p.is_file() and p.relative_to(base).with_suffix("").as_posix() not in V.SLOTS) \
        if base.is_dir() else []
    cv = ctx.pack.pkg_character_text_row()[11]
    packed = not missing and not not_voice_owned and refs == want_refs and not extra and cv == V.VOICE_ACTOR
    return {"packed": packed, "missing_slots": missing, "not_voice_owned": not_voice_owned,
            "speech_refs": refs, "extra_voice_files": extra, "cv": cv}


def media_fingerprint_parts(ctx) -> dict[str, Any]:
    """像素 sheet 与语音（文件 / speech 行）字节摘要：媒体换了，门禁必须重跑才能回到 ready-for-review。"""
    pixel = {}
    for name in PIXEL_SHEETS:
        logical = f"character/{CODE}/pixelart/{name}.png"
        path = ctx.pack.pkg_path("common", logical)
        pixel[logical] = sha256(path.read_bytes()) if path.is_file() else None
    base_root = ctx.pack.package / "roots" / "common"
    voice_dir = base_root / "character" / CODE / "voice"
    voice = {p.relative_to(base_root).as_posix(): sha256(p.read_bytes())
             for p in sorted(voice_dir.rglob("*")) if p.is_file()} if voice_dir.is_dir() else {}
    speech_flat = ctx.pkg_flat(SPEECH) if ctx.pack.pkg_has("common", SPEECH) else {}
    return {"pixel": pixel, "voice_files": voice, "speech": speech_flat.get(CID)}


# ---------------------------------------------------------------- 指纹 / 门禁状态

def kit_fingerprint(ctx) -> tuple[str, dict]:
    """kit 自有产物指纹（表行、字符串、固有图标、5 棵 DSL、4 个特效族全部文件字节）。"""
    import wf_dsl
    parts: dict[str, Any] = {}
    parts["character_c9_18"] = ctx.pack.pkg_character_row()[9:19]
    parts["character_text"] = ctx.pack.pkg_character_text_row()
    ab = ctx.pkg_flat(ABILITY)
    parts["ability"] = {k: ab[k] for k in [f"{CID}{i}" for i in range(1, 7)]}
    parts["leader"] = ctx.pkg_flat(LEADER)[CID]
    cas = ctx.pkg_flat(CAS)
    parts["custom_ability_string"] = {k: cas[k] for k in CAS_KEYS}
    import wf_mod_tool as core
    caps_om = core.read_orderedmap_raw_rows_from_bytes(ctx.pack.pkg_path("common", CAPS).read_bytes(), CAPS)
    parts["custom_ability_power_up_string"] = sha256(dict(zip(caps_om.keys, caps_om.rows))[CHANGE_SKILL_KEY])
    uc_flat = ctx.pkg_flat(UC)
    parts["unique_condition"] = {uid: uc_flat[uid] for uid in UC_IDS}
    parts["unique_icon"] = {uid: sha256(ctx.pack.pkg_path("common", UC_ICONS[uid]).read_bytes()) for uid in UC_IDS}
    parts["power_flip_action"] = ctx.pkg_flat(PFA)[PF_KEY]
    parts["action_skill"] = ctx.pkg_nested(CODE)
    parts["switched_action_skill"] = ctx.pkg_nested(VOICE_KEY, SW)
    progs = {}
    for logical in program_logicals(ctx):
        progs[logical] = sha256(ctx.pack.pkg_path("common", logical).read_bytes())
    parts["dsl"] = progs
    fx = {}
    base_root = ctx.pack.package / "roots" / "common"
    for _src, sub, _bases in EFFECT_FAMILIES:
        base = base_root / "battle" / "effect" / "skill_unique" / CODE / sub
        for p in sorted(base.rglob("*")):
            if p.is_file():
                rel = p.relative_to(base_root).as_posix()
                fx[rel] = sha256(p.read_bytes())          # 含 PNG：换色后必须重跑门禁（alpha/区域检查）
    parts["effects"] = fx
    parts["media"] = media_fingerprint_parts(ctx)       # 像素 / 语音：Integrate 阶段装包后必须重跑门禁
    parts["required_capabilities"] = sorted(CAPABILITIES)
    parts["overrides"] = OVERRIDES
    parts["official_sig_pin"] = OFFICIAL_SIG_PIN          # 校验依据变了也要重跑门禁
    parts["revision_plan"] = sha256((ctx.root / REVISION_REL).read_bytes())   # 改版计划换了必须重跑门禁
    blob = json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(blob), parts


def program_logicals(ctx) -> list[str]:
    import wf_dsl
    out = [wf_dsl.dsl_logical(ctx.program_path(lv)) for lv in ("1", "2")]
    out += [wf_dsl.dsl_logical(pf_program(lv)) for lv in (1, 2, 3)]
    return out


def gates_status(root: Path, fingerprint: str) -> tuple[str, str]:
    path = root / GATES_REL
    if not path.is_file():
        return "draft", "impl/zehr/gates.json 不存在（门禁未跑）"
    try:
        gates = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return "draft", "gates.json 无法解析"
    if not gates.get("all_pass"):
        return "draft", "gates.json all_pass=false"
    if gates.get("kit_fingerprint") != fingerprint:
        return "draft", "gates.json kit_fingerprint 与当前产物不一致（需重跑门禁）"
    return "ready-for-review", f"gates.json all_pass @ {gates.get('generated_at')}"


# ---------------------------------------------------------------- 主流程

def build(ctx) -> dict[str, Any]:
    import wf_client_legality as L
    import wf_dsl
    import wf_seasonal7_voice as V
    spec = ctx.spec
    if (spec.key, spec.cid_s, spec.code, spec.element) != (KEY, CID, CODE, ELEMENT):
        raise KitError(f"spec identity mismatch {spec.key}/{spec.cid}/{spec.code}")
    missing_inputs = required_input_problems(ctx.root)
    if missing_inputs:
        raise KitError(f"kit inputs unavailable: {missing_inputs}")
    design = load_design(ctx.root)
    plan = load_revision(ctx.root)
    text_probs = check_texts_constant(design, plan)
    if text_probs:
        raise KitError(f"TEXTS constant drifted from design/revision: {text_probs}")
    notes: list[str] = []

    # ---- character 行：spec 列断言 + c9–c16 语音路由 + c18 队长名
    crow = ctx.pack.pkg_character_row()
    edits = design["character_row"]["edits"]
    route_cols = V.normalize_route(design["voice"]["route"], CODE)
    if route_cols != [edits[str(i)] for i in range(9, 17)]:
        raise KitError(f"voice route {route_cols} != design character c9-16")
    new_crow = list(crow)
    new_crow[9:17] = route_cols
    new_crow[18] = TEXTS["leader"]
    for col, val in edits.items():
        if new_crow[int(col)] != val:
            raise KitError(f"character c{col}={new_crow[int(col)]!r} != design {val!r} (rerun tables?)")
    V.route_character_row(new_crow, route_cols, CODE)
    ctx.write_flat(CHAR, {CID: [new_crow]})
    text_row = character_text_row(design)
    ctx.write_flat(TEXT, {CID: [text_row]})

    # ---- 词条 / 队长（按改版计划重放）
    rows, row_evidence = build_rows(ctx, plan)
    bad = {f"{e['table']}#{e['key']}#{e['record']}": {k: e[k] for k in
           ("client_legality_problems", "declared_block_field_problems", "ability_element_column_problems",
            "trigger_limit_problems") if e[k]}
           for e in row_evidence if e["client_legality_problems"] or e["declared_block_field_problems"]
           or e["ability_element_column_problems"] or e["trigger_limit_problems"]}
    if bad:
        raise KitError(f"row legality problems: {bad}")
    ctx.write_flat(LEADER, {CID: rows["leader"]})
    ctx.write_flat(ABILITY, rows["ability"])

    # ---- 固有状态：159997「灯火正旺」（不变）+ 1599971「灯芯」（改版新增）+ 两张图标
    uc_plan = plan["tables"]["unique_condition"]
    if uc_plan["logical_path"] != UC or sorted(uc_plan["rows"]) != sorted(UC_IDS):
        raise KitError(f"revision unique_condition rows {sorted(uc_plan['rows'])}")
    design_uc = design["unique_conditions"][0]
    if design_uc["id"] != UC_ID or design_uc["table"] != UC or design_uc["row"] != uc_plan["rows"][UC_ID]["row"]:
        raise KitError("revision keeps 159997 row but it differs from the design row")
    uc_rows = {}
    for uid in UC_IDS:
        row = rev3_unique_row(uid, uc_plan["rows"][uid]["row"])      # 第三轮 T3-a：灯火正旺 10 秒 → 12 秒
        if len(row) != len(uc_plan["columns"]):
            raise KitError(f"unique_condition {uid} width {len(row)}")
        if row[4] in ("", "(None)"):
            raise KitError(f"unique_condition {uid} max stack must not be (None) (wf-unique-cap-none-trap)")
        if row[2] + ".png" != UC_ICONS[uid]:
            raise KitError(f"unique_condition {uid} icon path {row[2]}")
        uc_rows[uid] = [row]
    if uc_rows[UC_ID2][0][4] != "99":
        raise KitError(f"「灯芯」max_accumulation must be 99, got {uc_rows[UC_ID2][0][4]!r}")
    if uc_rows[UC_ID][0][3] != str(UC_LAMP_FRAMES):
        raise KitError(f"「灯火正旺」duration must be {UC_LAMP_FRAMES}, got {uc_rows[UC_ID][0][3]!r}")
    if UC_LAMP_FRAMES <= CT_LAMP_FRAMES:            # 第三轮的立意：12 秒 > 5 秒 ⇒ 状态可常驻
        raise KitError(f"「灯火正旺」{UC_LAMP_FRAMES} 帧 <= CT {CT_LAMP_FRAMES} 帧：状态会出现空档")
    ctx.write_flat(UC, uc_rows)
    for uid, draw in ((UC_ID, draw_lamp_icon), (UC_ID2, draw_wick_icon)):
        icon_bytes = ctx.png_store_bytes(draw())
        if icon_bytes[:8] != b"\x89png\r\n\x1a\n":
            raise KitError(f"unique icon {uid} lacks WF storage signature")
        ctx.write_asset("common", UC_ICONS[uid], icon_bytes)
    grants = {uid: [(k, i) for k, lines in rows["ability"].items() for i, r in enumerate(lines)
                    if r[47] == "461" and r[68] == uid] for uid in UC_IDS}
    if any(len(v) != 1 for v in grants.values()):
        raise KitError(f"each unique condition needs exactly one 461 grant row: {grants}")

    # ---- 字符串（改版：7 个 CAS 键，只有 722 说明沿用设计值）
    strings = {(item["table"], item["key"]): item for item in design["custom_strings"]}
    if [k for t, k in strings if t == CAPS] != [CHANGE_SKILL_KEY]:
        raise KitError(f"design custom_strings keys unexpected: {sorted(strings)}")
    plan_cas = plan["texts"]["custom_ability_string"]
    if sorted(plan_cas) != sorted(CAS_KEYS):
        raise KitError(f"revision custom_ability_string keys {sorted(plan_cas)} != {sorted(CAS_KEYS)}")
    cas_rows = {}
    rev2_text_changes = {}
    for key in CAS_KEYS:
        item = plan_cas[key]
        if item["action"] == "unchanged":
            if key != PF_STRING_KEY:
                raise KitError(f"revision marks {key} unchanged but it is not the 722 string")
            value = apply_text_override(strings[(CAS, key)]["value"], key)
        else:
            if item["action"] not in ("new", "rewrite"):
                raise KitError(f"{key}: unknown revision action {item['action']!r}")
            value = item["value"]
            if TEXT_DROPPED_BY_OVERRIDE in value:
                raise KitError(f"{key}: revision text still says {TEXT_DROPPED_BY_OVERRIDE}")
        before = value
        # 第二轮 T2 文案规则①②＋主位键 Ⓜ；第三轮 T3-c 节奏；第四轮 T4-c 强度数字
        value = rev4_panel_text(key, value)
        if value != before:
            rev2_text_changes[key] = {"rewrites": [o for o, _ in REV2_TEXT_REWRITES.get(key, ()) if o in before],
                                      "revision3_rewrites": [o for o, _ in REV3_TEXT_REWRITES.get(key, ())],
                                      "revision4_rewrites": [o for o, _ in REV4_TEXT_REWRITES.get(key, ())],
                                      "dropped": [d for d in REV2_TEXT_DROPS if d in before],
                                      "main_icon": key in REV2_MAIN_ICON_KEYS}
        if key.startswith("desc_override_"):
            probs = panel_text_problems(value, key)
            if probs:
                raise KitError(f"{key}: {probs}")
            if L.panel_override_capability(key) != "panel-description-override-v2":
                raise KitError(f"{key} panel capability mismatch")
        cas_rows[key] = [[value]]
    if design["abilities"]["slot3"].get("desc_override_key") != SLOT3_OVERRIDE_KEY:
        raise KitError("slot3 desc_override key mismatch")
    string_ids = {rows["leader"][0][0]} | {lines[0][0] for lines in rows["ability"].values()}
    for key in (LEADER_OVERRIDE_KEY,) + SLOT_OVERRIDE_KEYS:
        if key[len("desc_override_"):] not in string_ids:
            raise KitError(f"{key} matches no row string id {sorted(string_ids)}")
    refs = {r[70] for lines in rows["ability"].values() for r in lines if len(r) > 70 and r[70]}
    refs |= {r[82] for r in rows["leader"] if r[82]}
    if not {PF_STRING_KEY, CHANGE_SKILL_KEY} <= refs:
        raise KitError(f"string keys not referenced by rows: {refs}")
    # 第二轮 T1/T2 的收口：Ⓜ 与 c1 对齐、技能强化条目按规则②写（正向对照钉死本角色确有 536 行）；
    # 第三轮收节奏、第四轮收强度数字（面板与数值列同源，谁改了一半都红）
    cas_texts = {k: v[0][0] for k, v in cas_rows.items()}
    panel_probs = main_slot_panel_problems(rows["ability"], cas_texts) \
        + rev2_skill_flag_problems(rows["ability"], cas_texts) \
        + rev3_text_problems(cas_texts) + rev4_text_problems(cas_texts) \
        + panel_matches_row_values(rows["ability"], cas_texts)
    if panel_probs:
        raise KitError(f"revision2/3/4 main-slot / skill-enhancement / timing / strength wording: {panel_probs}")
    ctx.write_flat(CAS, cas_rows)
    # 2026-09-17 作者修订在历史基线门禁之后收口，避免重建恢复旧灯火。
    from wf_zehr_lamp_revision import revise_rows as lamp_rows, revise_unique, revise_text
    rows["ability"][CID+'1'], rows["ability"][CID+'3'] = lamp_rows(
        rows["ability"][CID+'1'], rows["ability"][CID+'3'])
    uc_rows[UC_ID] = revise_unique(uc_rows[UC_ID])
    for slot in (1, 3):
        key = f'desc_override_{CODE}_{slot}'
        cas_rows[key] = [[revise_text(slot, cas_rows[key][0][0])]]
    # 2026-09-27 平衡调整第二批（wf_balance_20260927b_zehr）同样在灯火修订之后收口：队长 #3 #4 放缓、
    # 灯芯 / 灯火正旺成长搬进队长 #6–#8、能力1/3 限次，三条覆盖文案同步。队长覆盖文案的底稿是 09-17
    # wf_seasonal_pf_revision 写进包里的那一版（该脚本改完 kit 产物后被能力3 sha 锁住、不可重跑），在此一并收口。
    import wf_balance_20260927b_zehr as balance_b
    from wf_seasonal_pf_revision import ZEHR_LEADER_TEXT
    rows["leader"], rows["ability"][CID+'1'], rows["ability"][CID+'3'] = balance_b.balance_rows(
        rows["leader"], rows["ability"][CID+'1'], rows["ability"][CID+'3'])
    balance_texts = balance_b.panel_texts({
        balance_b.CAS_LEADER: ZEHR_LEADER_TEXT,
        **{key: cas_rows[key][0][0] for key in (balance_b.CAS_A1, balance_b.CAS_A3)}})
    balance_probs = (balance_b.row_problems("leader_ability", rows["leader"])
                     + balance_b.row_problems("ability", rows["ability"][CID+'1'] + rows["ability"][CID+'3'])
                     + balance_b.panel_problems(balance_texts))
    if balance_probs:
        raise KitError(f"2026-09-27 balance batch 2: {balance_probs}")
    # 2026-09-27 平衡第三轮（wf_balance_20260927c_zehr）接在第二批之后：队长 #3 #4 #6 #7 #8 成长回调到
    # 原值 2/3–7/10，队长覆盖文案四处数字同步、L1 / L7「、强化弹射伤害」→「，」（口径 1，R6 续）；能力1/3 封顶版与其文案不动。
    import wf_balance_20260927c_zehr as balance_c
    rows["leader"] = balance_c.leader_rows(rows["leader"])
    balance_texts[balance_c.CAS_LEADER] = balance_c.leader_text(balance_texts[balance_c.CAS_LEADER])
    balance_probs = balance_c.problems(rows["leader"], balance_texts[balance_c.CAS_LEADER])
    # 第三轮面板同条件合并：能力6 两行（光共鸣、无触发，数据条件逐格相同）并为一行；kind 55 战斗级 ⇒ 不补「自身」（R6）。
    balance_texts[balance_c.CAS_A6] = balance_c.ability6_text(cas_rows[balance_c.CAS_A6][0][0])
    balance_probs += balance_c.ability6_problems(rows["ability"][balance_c.A6], balance_texts[balance_c.CAS_A6])
    balance_probs += panel_text_problems(balance_texts[balance_c.CAS_A6], balance_c.CAS_A6)
    if balance_probs:
        raise KitError(f"2026-09-27 balance round 3: {balance_probs}")
    for key, text in balance_texts.items():
        cas_rows[key] = [[text]]
    ctx.write_flat(LEADER, {CID: rows["leader"]})
    ctx.write_flat(ABILITY, {CID+'1': rows['ability'][CID+'1'], CID+'3': rows['ability'][CID+'3']})
    ctx.write_flat(UC, {UC_ID: uc_rows[UC_ID]})
    ctx.write_flat(CAS, {key: cas_rows[key] for key in (balance_b.CAS_LEADER, balance_b.CAS_A1, balance_b.CAS_A3)})
    ctx.write_flat(CAS, {balance_c.CAS_A6: cas_rows[balance_c.CAS_A6]})       # 第三轮能力6 同条件合并行
    import wf_seasonal7_tables as T
    caps_blob = ctx.pack.template_raw(CAPS)[f"change_skill_{TEMPLATE_CODE}"]     # 官方原行字节（5 档文本不含技能名）
    if T.decode_blob(caps_blob) != strings[(CAPS, CHANGE_SKILL_KEY)]["value"]:
        raise KitError("official power_up row != design value")
    caps_blob = power_up_blob(caps_blob, plan)                                   # R4：536 的「强化」后缀真源
    ctx.write_raw_outer(CAPS, {CHANGE_SKILL_KEY: caps_blob})

    # ---- 撤销框架自动克隆但本 kit 不用的字符串键
    unclaimed = []
    for claim in ctx.pack.load_claims():
        if (claim["root"], claim["logical_path"]) == ("common", CAS):
            extra = sorted(set(claim["outer_keys"]) - set(CAS_KEYS))
            if extra:
                ctx.unclaim(CAS, extra)
                unclaimed.extend(extra)

    # ---- action_skill：名称 / 描述 / 能量 / DSL 路径
    inner = ctx.pkg_nested(CODE)
    if set(inner) != {"1", "2"}:
        raise KitError(f"package action_skill inner keys {sorted(inner)}")
    import wf_mod_tool as core
    official_action = core.load_nested_table_bytes(
        ctx.official_read(ACTION, "common"), ACTION).rows[TEMPLATE_CODE].text_rows()
    energy = design["skills"]["energy"]
    names = {"1": (TEXTS["skill1"], TEXTS["desc1"]), "2": (TEXTS["skill2"], TEXTS["desc2"])}
    new_inner = {}
    for level in ("1", "2"):
        off = ctx.csv_split(official_action[level])[0]
        cells = list(off)
        if len(cells) != 24:
            raise KitError("action_skill schema unexpected")
        cells[0], cells[1] = names[level]
        e = energy[level]
        cells[4], cells[5], cells[6] = str(e["c4"]), str(e["c5"]), str(e["c6"])
        cells[7] = ctx.program_path(level)
        if cells[7] != design["skills"]["action_skill_rows"]["edits"]["c7"][int(level) - 1]:
            raise KitError("action_skill program path != design")
        new_inner[level] = [cells]
    ctx.write_nested(ACTION, CODE, new_inner, replace_inner=True)

    # ---- 特效族（克隆 + 染色 / fx manifest）
    families, recolor_log, fx_info = clone_families(ctx)

    # ---- 技能 DSL
    sources, source_info = {}, {}
    for name in SKILL_SOURCES:
        sources[name], source_info[name] = load_program(ctx, name)
    skills_report = {}
    for level in (1, 2):
        tree, info = compose_skill(ctx, level, sources)
        tree, refinfo = ctx.rewrite_effect_refs(tree, families["skill"], strict=True)
        design_tree = json.loads((ctx.root / DESIGN_TMP_REL / f"final_skill_{level}.json").read_text(encoding="utf-8"))
        diff = first_difference(tree, design_tree)
        if diff:
            raise KitError(f"composed skill {level} differs from design final tree: {diff}")
        # 改版：两处 ALv 通道（强化态合计 250%）；先证明合成结果仍等于上一轮定稿树，再落改版编辑
        revision_edits = apply_skill_revision(tree, level, plan)
        info["revision_edits"] = revision_edits
        from wf_zehr_skill_feel import revise_skill
        tree = revise_skill(tree)
        checks = dsl_problems(ctx.root, tree)
        if not checks["all_empty"] or not checks["roundtrip"]:
            raise KitError(f"skill {level} static checks failed: {checks}")
        ref_probs = effect_ref_problems(ctx, tree)
        if ref_probs:
            raise KitError(f"skill {level} effect refs unresolved: {ref_probs}")
        logical = ctx.write_dsl(ctx.program_path(str(level)), tree)
        info.update(checks=checks, effect_refs=refinfo, logical=logical,
                    equals_design_tree_before_revision=True,
                    sha256=sha256(ctx.pack.pkg_path("common", logical).read_bytes()))
        skills_report[str(level)] = info

    # ---- 722 双形态 PF
    pf_sources, apk_name = apk_pf_sources(ctx.root)
    design_pf_row = design["pf_override"]["power_flip_action_row"]
    if design["pf_override"]["power_flip_action_key"] != PF_KEY or \
            design_pf_row != [design_pf_program(lv) for lv in (1, 2, 3)]:
        raise KitError("power_flip_action design row unexpected")
    pf_row = [pf_program(lv) for lv in (1, 2, 3)]                  # 路径缩短（见 PF_PROGRAM_NAME 注释），键不变
    pre_budget = workspace_path_budget(
        ctx.workspace, ctx.pack.batch_dir,
        extra_rel=tuple(f"package/roots/common/{wf_dsl.dsl_logical(p)}" for p in pf_row),
        exclude_rel=tuple(f"package/roots/common/{wf_dsl.dsl_logical(p)}" for p in design_pf_row))
    if pre_budget["headroom"] < 0:
        raise KitError(f"workspace path too long for framework inspect copy: {pre_budget}")
    leader_pf = rows["leader"][design["pf_override"]["leader_row"]["target_record"]]
    if (leader_pf[45], leader_pf[80], leader_pf[81], leader_pf[82]) != ("722", PF_KEY, "1,2,3", PF_STRING_KEY):
        raise KitError(f"leader 722 row columns unexpected {leader_pf[45]} {leader_pf[80:83]}")
    pf_report, pf_budgets = {}, {}
    for level in (1, 2, 3):
        tree, info = compose_pf(level, pf_sources)
        tree = add_blaze_layer(tree, level, families["pf_blaze"])
        refinfo = {}
        for sub in ("pf_spin", "pf_support", "pf_blaze"):
            tree, refinfo[sub] = ctx.rewrite_effect_refs(tree, families[sub], strict=True)
        expect = expected_pf_tree(ctx.root, level, families["pf_blaze"]["dst_dir"])
        diff = first_difference(tree, expect)
        if diff:
            raise KitError(f"composed PF lv{level} differs from design+override tree: {diff}")
        checks = dsl_problems(ctx.root, tree)
        if not checks["all_empty"] or not checks["roundtrip"]:
            raise KitError(f"PF lv{level} static checks failed: {checks}")
        ref_probs = effect_ref_problems(ctx, tree)
        if ref_probs:
            raise KitError(f"PF lv{level} effect refs unresolved: {ref_probs}")
        pf_budgets[level] = pf_budget_report(level, tree, pf_sources)
        logical = ctx.write_dsl(pf_row[level - 1], tree)
        info.update(checks=checks, effect_refs=refinfo, logical=logical,
                    equals_design_plus_override=True, sha256=sha256(ctx.pack.pkg_path("common", logical).read_bytes()),
                    blaze_scale=PF_BLAZE_SCALE[level], budget=pf_budgets[level])
        pf_report[str(level)] = info
    ctx.write_flat(PFA, {PF_KEY: [pf_row]})
    removed_programs = drop_stale_pf_programs(ctx)
    budget = workspace_path_budget(ctx.workspace, ctx.pack.batch_dir)
    if budget["headroom"] < 0:
        raise KitError(f"workspace path too long for framework inspect copy: {budget}")

    # ---- switched_action_skill（语音 matched_skill_ready 路由的目标技能）
    switched = V.switched_rows({lv: list(c) for lv, c in ctx.pkg_nested(CODE).items()})
    ctx.write_nested(SW, VOICE_KEY, {lv: [cells] for lv, cells in switched.items()}, replace_inner=True)

    # ---- 三层镜像
    mirrors = ctx.sync_character_mirrors()

    # ---- 像素小人（复核通过才装，owner=pixel）；语音只读状态（由 wf_seasonal7_voice pack + impl/zehr/voice_merge.py 装）
    pixel = install_pixel(ctx)
    voice = voice_state(ctx)
    ctx.evidence_write("pixel-report.json", {       # manifest 读 summary/status 进 snapshot
        "summary": (f"像素小人染色 sheet 已装包（{PIXEL_DIR_REL}/out，存储态，owner=pixel）"
                    if pixel["status"] == "installed" else "像素小人 pending（母本原色占位）"),
        **pixel})

    # ---- 能力声明一致性
    row_caps = sorted({c for e in row_evidence for c in e["capabilities"]}
                      | {cap for k in CAS_KEYS for cap in [L.panel_override_capability(k)] if cap})
    if row_caps != sorted(CAPABILITIES) or sorted(spec.required_capabilities) != sorted(CAPABILITIES) \
            or sorted(design["required_capabilities"]) != sorted(CAPABILITIES):
        raise KitError(f"capabilities rows={row_caps} spec={spec.required_capabilities}")

    fingerprint, _parts = kit_fingerprint(ctx)
    status, status_reason = gates_status(ctx.root, fingerprint)
    programs = program_logicals(ctx)
    panel = [f"{e['table']} {e['key']}#{e['record']}: {e['describe']}" for e in row_evidence]
    if fx_info is None:
        notes.append("特效 sheet 为 kit 默认调色板染色（fx/zehr/out/manifest.json 未产出；Effects 阶段产出后重跑 kit 即替换）")
    else:
        notes.append(f"特效 sheet 按 fx manifest 替换 {sum(1 for r in recolor_log if r['mode'] == 'fx-manifest')} 张")
    notes += [
        "主控覆盖①：PF 每段倍率恢复官方 3.25/4.75/6.3（寿命/命中/Notify ×3、suppress 70/90/110 保持）；"
        "每段削韧 0.75/1.0/1.5、Fever 点 2/2/3 仍取设计值（覆盖未提及）",
        pf_budget_note(pf_budgets),
        (f"PF 程序路径缩短为 override/{PF_PROGRAM_NAME}$…_lv1/2/3（设计 override/{PF_KEY}$…；框架 inspect 副本路径超 "
         f"Windows MAX_PATH）；power_flip_action 键 / 队长行 c80 / 文案键仍按设计；副本最长 {budget['copy_len']}"
         f"（上限 {WIN_MAX_PATH}，余量 {budget['headroom']}）"),
        "主控覆盖②：PF 判定区 onCreate 在 spin 之前叠 master_knight_blaze 火光层（pf_blaze 族，Effects 阶段推荐族，"
        "暖金暗红，timeline sounds 清空，AB 坐标，scale 2.1/2.5/5.6≈spin 屏上半宽 0.9×）；blaze 无 end 段，判定区结束即消失；"
        "叠层观感/帧率需真机金丝雀",
        "覆盖文案与 722 文案删去「（每段伤害降低）」",
        ("spin 条纹 B 层（设计『仅 alpha×0.8』）：kit 兜底调色板在 sheet 条纹像素上做 alpha×0.8；"
         "fx manifest 替换 sheet 时以 Effects 产物为准（其 alpha 逐字节保留，即未做 B）；两种情况都不动 .parts c 字段"),
        ("词条行按设计逐格落地；同键 c1/c2 混写只作信息（live 多记录键 152 个混写，含已上线 1499993 / 1699991）："
         f"{mixed_c1_c2(rows['ability']) or '无'}"),
        "unique_condition 两张图标均为 kit 程序绘制（159997「灯火正旺」提灯 / 1599971「灯芯」光柱火苗，"
        "同族暗红底白框，轮廓刻意拉开），需作者目检",
        ("语音已装包（22 槽 AI 合成，speech 8 行引用新槽，旧母本语音已清，c11=AI 合成配音）；"
         "c9–c16 ConditionExist(28)+Unique 159997 路由与 switched_action_skill 已写" if voice["packed"]
         else f"语音未装齐：missing={voice['missing_slots'][:3]} not_voice_owned={voice['not_voice_owned'][:3]} "
              f"extra={voice['extra_voice_files'][:3]}；须跑 wf_seasonal7_voice pack + impl/zehr/voice_merge.py"),
        (f"像素小人已装包（{PIXEL_DIR_REL}/out 存储态，owner=pixel，report 门禁 + verify_all 修复轮复核通过）"
         if pixel["status"] == "installed" else f"像素小人 pending（母本原色）：{pixel['problems'][:3]}"),
        "skill_preview 沿用母本 905、upskill 沿用母本（common_attack/piercing/combo/condition_attack）；设计未要求改",
        "待作者拍板项取设计默认：c27=自身 cid、冲刺方案 A（斜下 45°）、语音参考 A（官方声纹）",
        ("2026-09-16 作者改版已落地（plan.json）：队长 6 行数值改 4 行（全队光攻 400%、每 35 连击 PF 伤害 50% 不封顶、"
         "每 1 次 PF 全队光攻 35% 不封顶、每 3 次 PF 连击加成 +9 持续 6 次）；词条 6 键 20 条记录（原 14）；"
         "新增固有 1599971「灯芯」（99 层永续）+ 新图标；5 条覆盖文案（原 2 条）；技能两档 ALv 改成强化态合计 250%；"
         "技能说明压到 54 字（两档同文）"),
        ("「光属性角色强化弹射伤害」在引擎里是战斗（小队）级参数，词条行 target 列不读"
         "（InstantAbilitySource kind 28/55/696/712、DuringAbilitySource kind 413）；"
         "本 kit 按引擎真实行为实现为战斗级增伤（作者要求的超集），面板文案相应写「强化弹射伤害＋N%」"),
        ("2026-09-16 第二轮作者改版：能力 1/3/5 主位限制（整键 c1='false'，不加前置 202 以免双 Ⓜ；能力 3 上一轮"
         "就是主位键，本轮只补面板 Ⓜ）；能力 1/3 的覆盖文案逐行加 <icon id='main'>，能力 5 无覆盖文案由客户端自动画 Ⓜ；"
         f"文案按规则①删「（无上限）」共 {sum(len(v['dropped']) for v in rev2_text_changes.values())} 处、"
         "按规则②把能力1 的技能强化条目改成「强化『白银一闪·打烊时刻』的「攻击力提升效果」与「强化弹射伤害提升效果」」"
         "（不写数值与秒数）；机制一格未动（灯芯仍 99 层、触发上限仍 (None)）"),
        ("能力 1/5 变主位专用后，泽赫尔放在合击位时这两键整键不进能力池（自身攻击力 150%、开局技能槽 50%、"
         "536 技能强化、灯火正旺 / 灯芯发放、全队光攻 100%、PF Lv3 全队技能槽 5% 都不再喂给主位携带者）——"
         "这是作者要的效果，但合击位收益确实变小，真机验收时请注意"),
        ("2026-09-16 第三轮作者改版（「灯火正旺效果延长到12s,ct改为5s」）：固有 159997 时长 "
         f"{UC_LAMP_FRAMES_REV2}→{UC_LAMP_FRAMES} 帧（10→{LAMP_SECONDS} 秒）；「≥50 连击弹射」四行 CT "
         f"{CT_LAMP_FRAMES_REV2}→{CT_LAMP_FRAMES} 帧（10→{CT_SECONDS} 秒，能力1#3/#4 + 能力3#0/#3，"
         "本角色全部 c35=600 的行就这四行，其余 CT 列为空或 0）；面板两处节奏文案随之改写"),
        (f"第三轮副作用（详算见 {REVISION3_DIR}/timing.md）：「灯芯」叠层与能力3「每获得 1 次灯火正旺」的收益"
         f"速度**翻倍**（最快 10 秒 1 层 → {CT_SECONDS} 秒 1 层；99 层由 990 秒缩到 495 秒）；"
         f"「灯火正旺」{LAMP_SECONDS} 秒 > CT {CT_SECONDS} 秒 ⇒ 只要连击保持 50 以上，状态可**常驻**（不再有空档），"
         "能力3 的 +40% 独立乘区与「每 15 连击 +5 连击」也随之常驻，技能语音路由（ConditionExist 159997）"
         "几乎恒走 voice_ready 那条。强度是否过头请作者判断"),
        ("作者未给、本设计拍板的 7 条（plan.judgements J1-J7）：≥50 连击弹射四行 CT=600 帧"
         "（第三轮已按作者要求改为 300 帧）、能力2 上限 10 次、"
         f"灯芯每层 +5% 独立乘区（第四轮已按作者要求改为 +{A1_WICK_MULT_PCT}%）、新状态命名/ID、"
         "删除原能力3「每 3 次 PF 自身攻击力 +60%」、"
         "灯芯乘区行不加光共鸣前置、能力6 rec#0 的 c2 变为 action_skill（玛纳板雕像组随之变化，验收要看）"),
        ("2026-09-16 第四轮作者改版（「能力 3 的 50% 降到 30%、灯芯每层 5% 降到 3%」= 上一轮 timing.md "
         f"「如果要收一点」的第 1、2 档）：能力3#0（全队光攻）与 #3（强化弹射伤害）c51/c52 "
         f"{A3_LAMP_GAIN_REV3}→{A3_LAMP_GAIN}（{A3_LAMP_GAIN_PCT_REV3}%→{A3_LAMP_GAIN_PCT}%）、"
         f"能力1#5（灯芯层数→PF 独立乘区）c113/c114 {A1_WICK_MULT_REV3}→{A1_WICK_MULT}"
         f"（{A1_WICK_MULT_PCT_REV3}%→{A1_WICK_MULT_PCT}%）；面板两处数字随之改写。"
         "节奏（CT 5 秒 / 灯火正旺 12 秒）、触发、上限、机制一格未动"),
        ("第四轮**没动**的同量级行：能力1#1「战斗开始时自身技能槽＋50%」（kind 211，也是 50000）"
         "不是作者说的那两处；能力2 / 能力6 / 队长 L3 的「强化弹射伤害＋50%」与能力5#1「技能槽＋5%」"
         "不在作者点名的能力1/3 里。四处都留在原值，面板一个字没改"),
        (f"第四轮强度（详算见 {REVISION3_DIR}/timing.md，模型与上一版同一套假设）：三个桶里跟 N 走的系数"
         "各降 40%（攻击桶 50%→30%、强化弹射桶 50%→30%、独立乘区每层 5%→3%）。"
         "PF 一发相对第三轮定稿 ×0.70（60 秒）→ ×0.46（300 秒）；"
         "相对线上 1.4.886 从 1.69–2.85 倍收到 **1.19–1.31 倍**，技能/普通伤害 1.03–1.08 倍。"
         "节奏红利（可常驻、叠层翻倍）留着，超额伤害收回"),
    ]
    if unclaimed:
        notes.append(f"已撤销框架自动克隆但未使用的字符串键 {unclaimed}")
    report = {
        "summary": f"泽赫尔·灯火酒馆 kit（2026-09-16 作者改版，第四轮：能力3 {A3_LAMP_GAIN_PCT}% / "
                   f"灯芯每层 {A1_WICK_MULT_PCT}%，节奏仍是灯火正旺 {LAMP_SECONDS} 秒 / CT {CT_SECONDS} 秒）："
                   "6 队长行 / 20 词条行 / 固有「灯火正旺」+「灯芯」/ "
                   "7 字符串 + power_up / 两档技能（ALv 强化态 250%）/ "
                   "722 双形态 PF（官方每段倍率、剑士段寿命/命中×3 + 火光新层）/ 4 特效族 / 语音路由",
        "status": status,
        "status_reason": status_reason,
        "kit_fingerprint": fingerprint,
        "design": {"path": DESIGN_REL, "sha256": sha256((ctx.root / DESIGN_REL).read_bytes())},
        "revision": {"path": REVISION_REL, "sha256": sha256((ctx.root / REVISION_REL).read_bytes()),
                     "schema": plan["schema"], "generated": plan.get("generated"),
                     "judgements": [{k: j[k] for k in ("id", "item", "value")} for j in plan.get("judgements") or []],
                     "open_items": plan.get("open_items") or [],
                     "skill_desc": {"old": DESIGN_SKILL_DESC, "new": TEXTS["desc1"]},
                     "record_counts": {"leader": len(rows["leader"]),
                                       "ability": sum(len(v) for v in rows["ability"].values())}},
        "revision2": {"rules": REVISION2_RULES_REL, "dir": REVISION2_DIR,
                      "main_slot_ability_keys": {k: "c1=false" for k in REV2_MAIN_SLOT_KEYS},
                      "main_slot_c1_flipped_records": rev4_row_changes(plan, rows["ability"])["c1"],
                      "main_icon_cas_keys": list(REV2_MAIN_ICON_KEYS),
                      "panel_text_changes": rev2_text_changes,
                      "unisonable_by_key": {f"{CID}{s}": rows["ability"][f"{CID}{s}"][0][1] for s in range(1, 7)}},
        "revision3": {"dir": REVISION3_DIR,
                      "request": "灯火正旺效果延长到12s,ct改为5s",
                      "unique_duration_frames": {UC_ID: [UC_LAMP_FRAMES_REV2, UC_LAMP_FRAMES],
                                                 UC_ID2: [uc_rows[UC_ID2][0][3], uc_rows[UC_ID2][0][3]]},
                      "cooldown_frames": [CT_LAMP_FRAMES_REV2, CT_LAMP_FRAMES],
                      "cooldown_rows": [f"{k}#{i}" for k, i in REV3_CT_ROWS],
                      "cooldown_records": rev4_row_changes(plan, rows["ability"])["ct"],
                      "cooldown_scan": rev3_cooldown_scan(plan),
                      "panel_seconds": {"lamp": LAMP_SECONDS, "cooldown": CT_SECONDS},
                      "timing_note": f"{REVISION3_DIR}/timing.md"},
        "revision4": {"dir": REVISION3_DIR,
                      "request": "能力 3 的 50% 降到 30%、灯芯每层 5% 降到 3%",
                      "value_rows": {f"{k}#{i}": {"cols": list(cols), "old": old, "new": new,
                                                  "percent": [old // PCT_SCALE, new // PCT_SCALE],
                                                  "built": [rows["ability"][k][i][c] for c in cols]}
                                     for (k, i), (cols, old, new) in sorted(REV4_VALUE_ROWS.items())},
                      "value_records": rev4_row_changes(plan, rows["ability"])["values"],
                      "value_scan": rev4_value_scan(plan),
                      "panel_percent": {"a3_lamp_gain": A3_LAMP_GAIN_PCT, "a1_wick_mult": A1_WICK_MULT_PCT},
                      "panel_bindings": {f"{k}#{i}": shape.format(pct=REV4_VALUE_ROWS[(k, i)][2] // PCT_SCALE)
                                         for (k, i), (_cas, shape) in sorted(PANEL_VALUE_BINDINGS.items())},
                      "unchanged": "节奏（CT / 灯火正旺时长）、机制、触发、上限、别的键的 50% 一格未动",
                      "timing_note": f"{REVISION3_DIR}/timing.md"},
        "overrides": OVERRIDES,
        "skills": {"programs": programs},
        "unique_condition": {uid: {"icon": UC_ICONS[uid], "row": uc_rows[uid][0]} for uid in UC_IDS},
        "required_capabilities": list(CAPABILITIES),
        "panel": panel,
        "notes": notes,
        "rows": row_evidence,
        "skill_sources": source_info,
        "skill_trees": skills_report,
        "pf": {"apk": apk_name, "power_flip_action": {PF_KEY: pf_row}, "design_programs": design_pf_row,
               "removed_stale_programs": removed_programs, "path_budget": budget, "levels": pf_report},
        "rows_mixed_c1_c2": mixed_c1_c2(rows["ability"]),
        "official_sig": {"source": load_official_sig(ctx.root)[1], "sha256": OFFICIAL_SIG_PIN},
        "effects": {"families": [{k: f[k] for k in ("src_dir", "dst_dir", "copied_bases", "missing_effects")}
                                 | {"files": len(f["files"]), "silenced_timelines": f.get("silenced_timelines")}
                                 for f in families.values()],
                    "fx_manifest": fx_info, "recolor": recolor_log},
        "switched_action_skill": {VOICE_KEY: switched},
        "pixel": pixel,
        "voice": voice,
        "character_route": route_cols,
        "unclaimed": unclaimed,
        "mirrors": {"server_character": mirrors["server_character"]},
    }
    ctx.report(report)
    return {"status": status, "status_reason": status_reason, "kit_fingerprint": fingerprint,
            "rows": {"leader": len(rows["leader"]), "ability_records": sum(len(v) for v in rows["ability"].values())},
            "skills": {lv: {"bytes": s["checks"]["amf3_bytes"], "estimate": s["multiplier_estimate"]}
                       for lv, s in skills_report.items()},
            "pf": {lv: {"bytes": p["checks"]["amf3_bytes"], "blaze_scale": p["blaze_scale"],
                        "ratio": p["budget"]["ratio"]} for lv, p in pf_report.items()},
            "removed_stale_programs": removed_programs, "path_budget": budget,
            "effects": [f["dst_dir"] for f in families.values()], "unclaimed": unclaimed,
            "pixel": pixel["status"], "voice_packed": voice["packed"]}

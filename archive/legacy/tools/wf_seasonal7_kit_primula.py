# -*- coding: utf-8 -*-
"""普莉姆拉·浴衣 169992 ``blackflower_wiz_yukata`` 套件（季节换装七角色 kit）。

设计定稿（改版）：``work/character_packs/seasonal7-20260916/revision-20260916/primula/``
（``requirements.md`` 逐条拆解、``plan.json`` 施工单、``primula.json`` / ``primula_tree_{1,2}.json`` /
``ability_skill_tree.json`` 交叉校验件）。上一轮 ``design/primula.json`` 只读留档，不再作为断言源。
本模块按设计落地：

- character 行语音路由 c9–c16、character_text（设计全文）；
- 队长 6 行、词条 6 键 13 条：一律取**官方基线** donor 行，逐列断言旧值后改写（``LEADER_PLAN``/``ABILITY_PLAN``），
  设计 JSON 在场时再断言成品行与设计逐字相同；
- 固有状态「夜百合」``16999201``（官方 11 同构，上限 20）＋ 48×48 图标（官方外框 alpha，程序绘制百合/团扇/新月）；
- action_skill 两档（161069 inner 行为底）、两棵技能 DSL（从官方 DSL 按 f3_tree.py 逐参数断言拼装，裸树编码）；
- 能力1#3 的 ``629 InvokeSkill`` 行 + 它调用的 ``ability_skill_<code>`` DSL（``compose_ability_skill_tree``）：
  暗共鸣前置、技能发动触发，给暗属性角色与协力球发直击伤害提升与贯穿（贯穿时长随夜百合层数），
  ≥5 层追加暗主队最大速度固定。c70 的文案键写进 ``custom_ability_string``（缺键＝详情页 C8601）；
- 两个特效族（sibling 形态）克隆与 DSL 特效引用改写；预留 Effects 阶段染色 sheet 钩子
  （``fx/primula/out/manifest.json``）；
- switched_action_skill ``<code>_voice_ready``（与 ``wf_seasonal7_voice.pack_voice`` 同列约定：action_skill c7..c23）。

不做：722 PF 覆盖、422 冲刺参数、724、desc_override。

改版 2（2026-09-16 晚，``revision2-20260916/文案规则-补充.md``）：本角色**无机制改动**，只把两条面板文案规则
（规则 1 不写「无上限」、规则 2 技能强化条目不写数字与时间）做成常驻检查器 ``panel_text_problems``，
静态门禁与离线门禁各挂一处。复核结论：本角色文案原本就零处「无上限」、且一行 ``ChangeSkillFlag`` 都没有
（规则 2 无适用条目），所以本轮文案一个字未改；证据见 ``revision2-20260916/primula/verify.md``。

改版 3（2026-09-16 夜，作者原话「夜百合的能力3加成给到暗属性角色全体和协力球而不是自身」）：
能力3 的两条「每层夜百合」加成改受益面，获取夜百合的两条瞬发行（自身叠层）不动。

- 每层攻击力 +50%：保留 target 5+``Black``（暗属性角色全体），**并列新增一条 target 8 Multiball**——
  CN 客户端 ``ui_string`` 把 Multiball 直译作「协力球」，协力角色本身就是
  ``createSummonsMultiball`` 生成的非 primary 小队，官方正形 1110063#L2（持续 → 赋予多球 攻击力）。
- 每层独立乘区直击伤害 +10%：target 0 自身 → 5+``Black`` 暗属性角色全体。
  **协力球够不到**：``MemberImpl.getStatModifierSeparatedTermDirectAttackDamage()`` 只读自身
  ``abilityTotalizer + conditionSlot``，不查任何 multiball 合计器；DSL 的 ``ACSeparatedTermDirectDamage``
  官方零先例。所以这一条按退路②只覆盖暗属性角色全体，并如实登记，不写会说谎的死行。
常驻门禁 ``lily_layer_target_problems``（静态 + 离线各挂一处）锁住这三件事；
对照表与强度影响见 ``revision3-20260916/primula/target.md``，回读核对见同目录 ``verify.md``。

离线门禁（manifest/status/inspect 之后）::

    python mod-tools/wf_seasonal7_kit_primula.py gates

写 ``seasonal7-20260916/impl/primula/gates.json``；全过时把 ``evidence/kit-report.json`` 的 status 升为
``ready-for-review``。kit 重跑时只有「静态门禁全过且 gates.json 通过且 kit 产物摘要未变」才保持 ready-for-review。

克隆特效 timeline 内嵌 SE（``sounds[].path``）是战斗预载引用：kit 静态门禁与离线门禁都要求每条可在包内或 live
解析到 ``<path>.mp3``，否则记失败（写错前缀＝进战斗「数据不足」）。

``ready-for-review`` / ``all_pass`` 只覆盖 kit 范围。语音 22 条、speech 8 行、像素 2 张由 Integrate 阶段装包；
gates.json 的 ``integration_pending.clear`` 与 ``release_ready_after_integration`` 为 true 之前不得发布。
``publish_blockers`` / ``needs_rebase_before_publish`` 是 kit 范围之外的发布前置：包内共享表持有别人角色的陈旧行时
（键在、内容旧；串行发布第二包起的常态），``release_ready_after_integration`` 强制为 false，只有 ``release_ready_after_rebase``
为 true —— 必须先按 ``wf-flow-serial-publish-order`` 走 ``preflight 封存 → flow rebase → preflight → publish``。

Integrate 阶段（媒体整合）：

- 特效：染色 sheet 除经 ``png_transform`` 钩子外，克隆后再以**染色 PNG 的存储态原字节**
  （``wf_assets.png_encode``，不经 PIL 重编码）覆盖包内 sheet（owner=effects），包内 sha = 存储态 sha；
  ``fx_sheet_problems`` 在 kit 与离线门禁里核对字节、尺寸与 alpha = 母本。
- 像素小人：``pixel/primula/report.json`` 门禁全过、``pixel/_review/verify_all.json`` primula 复核
  （hard + 声明 D1）全过、REVIEW.md 修复轮复核判 PASS、三处 sha 一致时，``install_pixel`` 把
  ``out/{sprite_sheet,special_sprite_sheet}.png`` 以存储态写入 ``character/<code>/pixelart/``（owner=pixel），
  写后核对尺寸/alpha = 母本、atlas/frame/timeline = 母本树（仅 ``character/<母本>/`` 前缀）；未就绪不写。
- 语音：由 ``impl/primula/voice_merge.py`` 在 ``wf_seasonal7_voice pack`` 之后并账（不在 kit 内）；
  ``integration_pending.voice.clear`` 另要求包内不再残留母本占位语音。
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

CID = "169992"
CODE = "blackflower_wiz_yukata"
UID = "16999201"
UID_INT = 16999201
ELEMENT = 5                                    # Black（0 基）
BATCH = "work/character_packs/seasonal7-20260916"
# 改版（2026-09-16）：设计件改指 revision-20260916/primula/（上一轮 design/ 只读留档，不改）
REVISION = f"{BATCH}/revision-20260916/primula"
DESIGN_JSON = f"{REVISION}/primula.json"
DESIGN_TREES = {"1": f"{REVISION}/primula_tree_1.json", "2": f"{REVISION}/primula_tree_2.json"}
DESIGN_AS_TREE = f"{REVISION}/ability_skill_tree.json"
OFFICIAL_SIG = f"{BATCH}/research/_tmp/official_sig.json"
FX_MANIFEST = f"{BATCH}/fx/primula/out/manifest.json"
IMPL_DIR = f"{BATCH}/impl/primula"
GATES_FILE = f"{IMPL_DIR}/gates.json"

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
CHAR = "master/character/character.orderedmap"
TEXT = "master/character/character_text.orderedmap"
UNIQUE = "master/character/unique_condition.orderedmap"
ACTION = "master/skill/action_skill.orderedmap"
SWITCHED = "master/skill/switched_action_skill.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
VOICE_READY = f"{CODE}_voice_ready"
ICON_ROW_PATH = f"battle/common/unique_condition/unique_{CODE}_lily_night"
ICON_LOGICAL = ICON_ROW_PATH + ".png"
ICON_FRAME_DONOR = "battle/common/unique_condition/unique_blackflower_wiz_smr22.png"

# 固有状态「夜百合」的名字与**真实上限**（UNIQUE_EDITS 与 DSL 的 BindConditionAccumulationVariable 都用它）。
# 提到这里是因为文案要引用上限：rev2 文案规则 1 第三条「有上限的才写上限」，
# 夜百合是真有上限（unique_condition c4 = 20，DSL 里同样硬钳 20），所以面板必须把 20 写出来。
UNIQUE_NAME = "夜百合"
UNIQUE_MAX = "20"
CAP_PHRASE = f"最多{UNIQUE_MAX}层"

SKILL_NAME_1 = "紫百合·烟花扇舞"
SKILL_NAME_2 = "紫百合·烟花扇舞＋"
# 改版（revision-20260916 R12）：赋予类效果已迁到能力1 的 ability_skill，说明只讲伤害；149 字 → 77 字。
SKILL_DESC = ("在距离最近的敌人处开出紫百合花园，持续造成暗属性伤害并降低其暗属性抗性，"
              "消散时绽放烟花追加伤害（威力随“夜百合”层数提升）／花园与烟花均按直接攻击伤害判定")
PROFILE = ("夏日祭典之夜，普莉姆拉换上绣满紫百合的浴衣，握着团扇怯生生地走进人群。"
           "烟花升空的刹那，她轻摇扇面，让曾被人畏惧的黑百合魔力在夜空中绽成紫花——"
           "今晚，她想让同伴看见这份力量温柔的一面。")
LEADER_NAME = "夏夜绽放的紫百合"
CV = "AI 合成配音"

TEXTS = {"name": "普莉姆拉", "furigana": "PULIMULA", "title": "夏夜扇舞的百合魔女", "profile": PROFILE,
         "leader": LEADER_NAME, "skill1": SKILL_NAME_1, "desc1": SKILL_DESC,
         "skill2": SKILL_NAME_2, "desc2": SKILL_DESC, "cv": CV}

# 改版 R1/R3/R13：能力1#3 的 629 InvokeSkill 行。c70 文案键必须存在于 custom_ability_string，
# 否则详情页 MasterStringMap.get 抛 C8601（wf_client_legality.invoke_skill_string_problems）。
CAS_KEY = f"ability_skill_{CODE}"
# 详情页渲染顺序是「合击标记 ＋ 前置/触发串 ＋ CAS 正文」（AbilityGroupingDescriptionGenerator.as:313-325），
# 所以 CAS 正文**只写效果**：前置（暗共鸣）与触发（技能发动）由行的列自己渲染，写进正文＝重复一遍。
# live 74 行 629 的正文全是纯效果（复核脚本 revision-20260916/primula/_fix/f2_verify_claims.py）。
# 改版 2 审查第 2 条：夜百合的逐层成长**有上限**（20 层，DSL BindConditionAccumulationVariable 第 5 参
# 与 unique_condition c4 同为 20），而 629 行的面板没有累积计数子句可渲染上限（合击标记＋前置/触发串＋
# CAS 正文，上限只在 DSL 里），所以按规则 1 第三条由 CAS 正文自己写出 —— 不写玩家无从得知封顶。
CAS_TEXT = ("赋予暗属性角色与协力球 直接攻击伤害提升125%与20秒贯穿效果，"
            f"每层“{UNIQUE_NAME}”追加+10%伤害与+2秒贯穿（{CAP_PHRASE}）；"
            f"“{UNIQUE_NAME}”达5层以上时，追加赋予暗属性角色最大速度固定效果")
# 正文里不许出现的前置/触发措辞（客户端已经渲染过一遍）
CAS_FORBIDDEN = ("共鸣时", "编成", "发动技能时", "自身为队长时", "自身为主位时", "Fever 时")
AS_PROGRAM = f"battle/action/skill/action/ability_skill/{CAS_KEY}${CAS_KEY}"

SPEC = {"extra_keys": {UNIQUE: (UID,), SWITCHED: (VOICE_READY,), CAS: (CAS_KEY,)}}

# 语音路由（设计 §10.1，阵容审查 R6）：ConditionExist(1) + Piercing(31)，c11 写 0（客户端不读，过构建器数字校验）
ROUTE_COLS = ["1", "31", "0", "", "", VOICE_READY, "false", "false"]

# ---------------------------------------------------------------- 行方案（官方 donor + 逐列 旧值→新值）
# (表, donor 键, donor 行号(1 基), {列: (旧, 新)})
LEADER_PLAN = [
    ("leader_ability", "161135", 1, {0: ("wind_spgirl_hw22", CODE), 111: ("230000", "300000"), 112: ("300000", "300000")}),
    ("leader_ability", "161177", 1, {0: ("ruin_girl_3halfanv", CODE), 49: ("40000", "50000"), 50: ("50000", "50000")}),
    ("leader_ability", "161123", 1, {0: ("blackflower_wiz_smr22", CODE), 100: ("10", "20"), 102: ("11", UID),
                                      107: ("0", "1"), 111: ("11500", "15000"), 112: ("15000", "15000")}),
    ("leader_ability", "161123", 4, {0: ("blackflower_wiz_smr22", CODE), 49: ("100000", "300000"),
                                      50: ("100000", "300000"), 66: ("11", UID)}),
    ("leader_ability", "161069", 2, {0: ("blackflower_wiz", CODE), 49: ("60000", "100000"), 50: ("80000", "100000")}),
    ("leader_ability", "161123", 2, {0: ("blackflower_wiz_smr22", CODE), 100: ("10", "20"), 102: ("11", UID),
                                      111: ("750", "1000"), 112: ("1000", "1000")}),
]
# 暗属性共鸣前置（precondition1 = kind 2 Member，阈值 100000 = 1 人 ⇒ 6 人 = 600000）
RESONANCE = {6: ("0", "2"), 9: ("", "600000"), 10: ("", "600000"), 11: ("", "Black")}
# 主位限制（precondition1 = 202 OwnerIsMain，无参；202/203 的 puller 等列**留空才是官方写法**，
# 见 wf-precondition-puller-c7050 的反例段）。共鸣是编成条件，与主位/副位正交，挡不住副位装配，
# 所以要主位限制必须另写 202（或让整键 values[0]=false）。
MAIN_ONLY = {6: ("0", "202")}
# 202 占了 precondition1 时，暗共鸣挪到 precondition2（块起点 c13，块内偏移同 precondition1：
# 0=kind 1=puller 2=puller组 3=阈值 4=阈值满级 5=角色组 6=固有ID）。
# 同批正形：zantetsu 1599981#2（629）、tekuto 1399931#1 / philia 1599961#2 / yuki 1299911#1（536）。
RESONANCE2 = {13: ("0", "2"), 16: ("", "600000"), 17: ("", "600000"), 18: ("", "Black")}

# ---- 改版 3（2026-09-16 夜，作者原话：「夜百合的能力3加成给到暗属性角色全体和协力球而不是自身」）----
# 受益面两个落点（during_content 目标列 c110 / 目标角色组列 c111）：
#   * 暗属性角色全体 = target 5 Party + c111=Black。客户端 forEachPartyTotalizer 只遍历 primary 三格，
#     不排除自身（Party 的 exceptMyself=false）⇒ 普莉姆拉本人照吃。
#   * 协力球 = target 8 Multiball。**CN 客户端自己的文案就叫「协力球」**：
#     ui_string `ability_description_target_multiball` = 「协力球」、`…_multiball_constraint` = 「::constraint::的协力球」；
#     引擎侧 MemberImpl.isMultiball() = !squad.isPrimary()，而协力角色由
#     BattleQuestBaseImpl.convertAssistCharacterToMultiballSource → AssistCharacterFactory.createSummonsMultiball
#     生成，就是一支非 primary 小队 ⇒ target 8 命中协力球。c111 对 target 8 不读（parseAt110 的 "8" 分支无参），
#     官方 4 条 during target 8 行的 c111 也全是空。
#   ⚠ target 6 UnisonParty **不是**协力：它渲染成「已被选为合击角色」，且 forEachUnisonParty 仍然只走 primary 三格。
LILY_PARTY_TARGET = "5"
LILY_PARTY_GROUPS = "Black"
LILY_ASSIST_TARGET = "8"
LAYER_TRIGGER = "134"                          # during_trigger 134 ConditionCountUnique = 「每层夜百合」
# 哪些 during 效果 kind 真能被协力球读到——判据是**客户端的读取函数有没有查 multiball 合计器**，
# 不是目标列能不能写（目标列什么都能写，写错只是静默失效，面板却照样写「协力球」）：
#   * kind 0 AttackPoint：MemberImpl._getStatModifierAttackPoint 里 `if(isMultiball())` 分支
#     逐个加 squadManager.commonMultiballAbilityTotalizer / specific / characterGroup 三种合计器 ⇒ 读得到。
#   * kind 410 SeparatedTermDirectDamage：MemberImpl.getStatModifierSeparatedTermDirectAttackDamage() 全文是
#     `abilityTotalizer.getTotalSeparatedTermDirectDamage() + conditionSlot.getTotalSeparatedTermDirectDamage()`，
#     一个 multiball 合计器都不查 ⇒ 写 target 8/14 是死行。DSL 侧的 ACSeparatedTermDirectDamage 全库官方零先例
#     （p10_direct_scan 扫 1200+ 棵技能树 0 命中），按「无先例命令禁用」也不走 ⇒ 独立乘区只给暗属性角色全体。
LILY_MULTIBALL_READABLE = frozenset({"0"})
LILY_MULTIBALL_UNREADABLE = frozenset({"410"})
# (队长行数, 词条行数)：改版 3 把 A3 从 4 行加到 5 行（每层攻击力多一条发给协力球）
ROW_COUNTS = (6, 14)

ABILITY_PLAN = {
    # A1#1 改版 R4：开局自身技能槽 100% → 50%
    1: [("ability", "1610691", 1, {0: ("blackflower_wiz_1", f"{CODE}_1"), 51: ("25000", "50000"), 52: ("50000", "50000")}),
        ("ability", "1611111", 1, {0: ("mirror_witch_1", f"{CODE}_1"), 109: ("1", "3"), 113: ("60000", "15000"),
                                   114: ("120000", "15000")}),
        # A1#3 改版 R1/R2/R3/R13：新增 629 InvokeSkill，承接原技能 B4（全队直击UP＋贯穿）与 B6（≥5 层最大速度固定）；
        # 触发改「技能发动」(c27=23)，延迟 c35 归零。
        # 改版 2 审查第 1 条：1699921 的 values[0]=true（整键进合击池），629 行原来只有暗共鸣前置，
        # 副位时会并入主位角色的能力池、由主位的技能发动拉起 —— 629 演出者硬绑主位，官方零副位先例
        # （官方 ability 表全表只有 1 行 629：1611053#0，正是本行 donor，且它所在键 values[0]=false）。
        # 正形照同批 zantetsu：precondition1 = 202 主位门，暗共鸣退到 precondition2；
        # c1 保持 true，面板才只画一个 Ⓜ（c1=false 与 202 同写＝双 Ⓜ，wf-unison-slot-mechanics）。
        ("ability", "1611053", 1, {0: ("estateguild_leader_3", f"{CODE}_1"), 1: ("false", "true"),
                                   2: ("special", "action_skill"), **MAIN_ONLY, **RESONANCE2,
                                   27: ("139", "23"), 35: ("300", "0"),
                                   70: ("ability_skill_estateguild_leader", CAS_KEY),
                                   71: ("battle/action/skill/action/ability_skill/ability_skill_estateguild_leader"
                                        "$ability_skill_estateguild_leader", AS_PROGRAM)})],
    2: [("ability", "1611111", 1, {0: ("mirror_witch_1", f"{CODE}_2"), 113: ("60000", "150000"), 114: ("120000", "150000")}),
        ("ability", "1610692", 2, {0: ("blackflower_wiz_2", f"{CODE}_2"), 51: ("10000", "50000"), 52: ("20000", "50000")})],
    # A3#1/#2 改版 R10：夜百合两个获取来源加暗共鸣前置
    3: [("ability", "1611231", 1, {0: ("blackflower_wiz_smr22_1", f"{CODE}_3"), 1: ("true", "false"), **RESONANCE,
                                   68: ("11", UID)}),
        ("ability", "1611231", 1, {0: ("blackflower_wiz_smr22_1", f"{CODE}_3"), 1: ("true", "false"), **RESONANCE,
                                   27: ("23", "20"), 28: ("0", "7"), 29: ("", "Black"),
                                   30: ("100000", "5000000"), 31: ("100000", "5000000"),
                                   51: ("200000", "100000"), 52: ("200000", "100000"), 68: ("11", UID)}),
        # A3#3 改版 R5/R7：每层全队暗攻击 10% → 50%，次上限 10 → 20
        ("ability", "1611233", 3, {0: ("blackflower_wiz_smr22_3", f"{CODE}_3"), 102: ("10", "20"), 104: ("11", UID),
                                   110: ("0", LILY_PARTY_TARGET), 111: ("", LILY_PARTY_GROUPS),
                                   113: ("10000", "50000"), 114: ("20000", "50000")}),
        # A3#4 改版 3：同一条「每层攻击力」再发一份给协力球（target 8 Multiball，客户端文案原文就是「协力球」）。
        # 与 A3#3 是同触发同强度的孪生行，只有目标列不同；官方正形 1110063#L2（持续·多球≥2 → 赋予多球 攻击力）。
        ("ability", "1611233", 3, {0: ("blackflower_wiz_smr22_3", f"{CODE}_3"), 102: ("10", "20"), 104: ("11", UID),
                                   110: ("0", LILY_ASSIST_TARGET), 113: ("10000", "50000"),
                                   114: ("20000", "50000")}),
        # A3#5 改版 R9 新增、改版 3 改受益面：每层夜百合 独立乘区直击伤害 +10%，自身 → 暗属性角色全体。
        # 协力球够不到：见 LILY_MULTIBALL_UNREADABLE 的注释（引擎读取路径不含 multiball 合计器）。
        ("ability", "1611233", 3, {0: ("blackflower_wiz_smr22_3", f"{CODE}_3"), 102: ("10", "20"), 104: ("11", UID),
                                   109: ("0", "410"), 110: ("0", LILY_PARTY_TARGET), 111: ("", LILY_PARTY_GROUPS),
                                   113: ("10000", "10000"), 114: ("20000", "10000")})],
    4: [("ability", "1611113", 1, {0: ("mirror_witch_3", f"{CODE}_4"), 1: ("false", "true"), 113: ("5000", "20000"),
                                   114: ("10000", "20000")}),
        ("ability", "1610693", 2, {0: ("blackflower_wiz_3", f"{CODE}_4"), 1: ("false", "true"), 51: ("-10000", "-20000"),
                                   52: ("-20000", "-20000")})],
    5: [("ability", "1610693", 1, {0: ("blackflower_wiz_3", f"{CODE}_5"), 1: ("false", "true"), 51: ("50000", "100000"),
                                   52: ("100000", "100000")})],
    6: [("ability", "1610696", 1, {0: ("blackflower_wiz_6", f"{CODE}_6"), 51: ("12500", "40000"), 52: ("25000", "40000")})],
}
# 固有状态：官方 11（能量吸取）donor；改版 R7/R11：名字统一「夜百合」、c4 上限 10 → 20
# （上限列必须是整数，写 (None) = 上限 1，叠层全死，wf-unique-cap-none-trap）
UNIQUE_DONOR = "11"                            # UNIQUE_NAME / UNIQUE_MAX 在文件头（文案要引用上限）
UNIQUE_EDITS = {0: ("unique_blackflower_wiz_smr22", f"unique_{CODE}_lily_night"),
                1: (None, UNIQUE_NAME),
                2: ("battle/common/unique_condition/unique_blackflower_wiz_smr22", ICON_ROW_PATH),
                4: ("10", UNIQUE_MAX)}

# ---- 面板文案规则（rev2，见 panel_text_problems 的注释）--------------------------------
# 「无上限」及其替代说法一律不写；有上限的才写上限。禁词表只作用于**本 kit 自己写的文案**，
# 客户端自动生成的那半句由数据列决定（ui_string 全表零处「无上限」，客户端不会自己造这三个字）。
# 改版 2 审查第 3 条：禁词表原来只有 5 个词，「不设上限」「没有上限」「上限无」三种写法漏网
# （变异测试实测全绿），而 impl/primula/rev2_text_audit.py 另写了一份含「上限无」的表 —— 两表不一致。
# 现在这里是唯一真源，审计脚本直接 import 本常量。
CAP_WORDING_BANNED = ("无上限", "无限叠加", "可无限", "不封顶", "无次数限制",
                      "不设上限", "没有上限", "上限无", "无叠加上限", "没有次数限制")
# ChangeSkillFlag 族（规则 2 的适用范围）；本角色零行，检查器只用于防回归
SKILL_FLAG_KINDS = frozenset({"536", "704", "705", "706", "707", "708"})
# 本角色全部玩家可见文案（character_text 的 c2/c3/c4/c6/c10 与 action_skill c0/c1 同源）
PANEL_TEXTS = {"SKILL_NAME_1": SKILL_NAME_1, "SKILL_NAME_2": SKILL_NAME_2, "SKILL_DESC": SKILL_DESC,
               "PROFILE": PROFILE, "LEADER_NAME": LEADER_NAME, "TITLE": TEXTS["title"],
               "UNIQUE_NAME": UNIQUE_NAME, "CAS_TEXT": CAS_TEXT}

# action_skill：161069 blackflower_wiz inner 行为底（c2 图标 atk_nearest、c8-c23 自动施放区域原样）
ACTION_DONOR = "blackflower_wiz"
ACTION_EDITS = {
    "1": {0: ("毁灭怒放", SKILL_NAME_1), 4: ("580", "540"), 5: ("580", "540"), 6: ("1", "1"),
          7: ("battle/action/skill/action/rare5/blackflower_wiz$blackflower_wiz_1",
              f"battle/action/skill/action/rare5/{CODE}${CODE}_1")},
    "2": {0: ("毁灭怒放＋", SKILL_NAME_2), 4: ("580", "540"), 5: ("530", "490"), 6: ("1", "1"),
          7: ("battle/action/skill/action/rare5/blackflower_wiz$blackflower_wiz_2",
              f"battle/action/skill/action/rare5/{CODE}${CODE}_2")},
}

# 特效族（设计 effects.clone，sibling 形态）
EFFECT_FAMILIES = (
    {"src_dir": "battle/effect/skill_unique/blackflower_wiz", "dst_subdir": "garden", "layout": "sibling",
     "fx_names": ["blackflower_wiz_flower_back", "blackflower_wiz_flower", "blackflower_wiz_hit"]},
    {"src_dir": "battle/effect/skill_unique/blackflower_wiz_smr22", "dst_subdir": "hanabi", "layout": "sibling",
     "fx_names": ["blackflower_wiz_smr22_flower", "blackflower_wiz_smr22_heart"]},
)

# 技能树参数（设计 §6.1 / f3_tree.py V）
HEART_NAME = "`自身のハート"
# 固定区分键（带 vlv 的 CreateCondition 必须有非空键，否则不同层数会叠加）；R11 统一叫「夜百合」
KEY_DD = "夜百合直撃バフ"
KEY_FS = "夜百合最大速度固定"
KEY_PC = "夜百合貫通"
UNIQUE_CAP = int(UNIQUE_MAX)


def _slv(a, b=None, vlv=None):
    d = {"min": a, "max": a if b is None else b}
    if vlv:
        d["vlv"] = vlv
    return [d]


TREE_VALUES = {
    "1": dict(garden_mul=_slv(2.0), fin_mul=_slv(6.7, vlv=[{"vid": 2, "min": 0, "max": 0.6}])),
    "2": dict(garden_mul=_slv(2.6, 3.0), fin_mul=_slv(8.7, 10, vlv=[{"vid": 2, "min": 0, "max": 0.6}])),
}
# 2026-09-27 平衡第二批（口径 B.1 技能单目标总削韧 ≤30）：烟花 CNA p12（削韧，数组下标 13）
# 官方 smr22 继承值 20 → 14，花园 8 段×2 不动 ⇒ 36 → 30。两档同值；== wf_balance_20260927b_primula。
FINALE_DETOUGHNESS = (_slv(20), _slv(14))

# ---------------------------------------------------------------- 迁移源（R1「移动」的原块）
#
# 审查第 1/3 条换来的门禁：R1 是「把技能赋予的强化效果**移动**到能力1」，不是重新设计，
# 所以 ability_skill 的参数必须能与**上一轮 live（归档包 1.4.873）技能树 Wait(1) 容器里的原块**逐项对齐，
# 差异只允许出现在 MIGRATION_DIFF 白名单里。下面是那三块的逐字快照（两档分开记）：
# 复核脚本 revision-20260916/primula/_fix/f1_archive_block.py 直接从归档包字节解出同样的值；
# 测试 ``test_ability_skill_values_match_migrated_live_block`` 在归档包在场时用实际字节复核这份快照。
#
# **取哪一档**：``ability_skill`` 是一份 DSL，不随技能等级分档，所以整套取「＋」档（skill_2，满技能等级形态），
# 即玩家在真机上实际体验到的强度。lv1 档的数值一并记下来只为留证，不参与断言。
MIGRATION_ARCHIVE = "s7-primula-20260916-1.4.873"
MIGRATION_LEVEL = "2"
MIGRATION_SOURCE = {
    # lv1 档（blackflower_wiz_yukata_1）——留证，不是迁移基准
    "1": {"ACDirectDamage": [[{"min": 1200, "max": 1200}],
                             [{"min": 0.8, "max": 0.8, "vlv": [{"vid": 1, "min": 0, "max": 0.1}]}],
                             [{"min": 1, "max": 1}]],
          "ACPiercing": [[{"min": 1080, "max": 1080}]],
          "ACFixedSpeed": [[{"min": 720, "max": 720}], [{"min": 1, "max": 1}],
                           [{"min": 0, "max": 0}], [{"min": 1, "max": 1}]]},
    # 「＋」档（blackflower_wiz_yukata_2）——迁移基准
    "2": {"ACDirectDamage": [[{"min": 1200, "max": 1200}],
                             [{"min": 1.0, "max": 1.25, "vlv": [{"vid": 1, "min": 0, "max": 0.1}]}],
                             [{"min": 1, "max": 1}]],
          "ACPiercing": [[{"min": 1200, "max": 1200}]],
          "ACFixedSpeed": [[{"min": 900, "max": 900}], [{"min": 1, "max": 1}],
                           [{"min": 0, "max": 0}], [{"min": 1, "max": 1}]]},
}
# 允许与迁移源不同的项：(AC 名, 参数序号) -> (**写死的新值**, 理由)。
# 白名单登记的是「改成什么」，不是「这一项随便改」—— 其它任何取值照样判红。
MIGRATION_DIFF = {
    ("ACDirectDamage", 1): ([{"min": 1.25, "max": 1.25, "vlv": [{"vid": 1, "min": 0, "max": 0.1}]}],
                            "SLv(1.0→1.25) 折成 ALv 常量，取「＋」档满值 1.25；"
                            "每层 +0.1 的 vlv 逐字保留（0 层 +125%，20 层 +325%）"),
    ("ACPiercing", 0): ([{"min": 1200, "max": 1200, "vlv": [{"vid": 1, "min": 0, "max": 120}]}],
                        "R8 新增 vlv：每层夜百合 +120 帧（= 基础 1200 帧的 10%）；基础时长 1200 帧不变，"
                        "20 层 = 3600 帧 = 60 秒"),
}

# 能力1 的 ability_skill（629 调用）参数。629 的 SLv 走 ALv（MemberImpl.as:8154），不是技能等级，
# 所以全部 min == max，避免按能力等级插值产生歧义（plan.json dsl.new_program.slv_note）。
# 直击增伤与贯穿时长各挂一条 vlv：value = min + (max-min) × 变量，变量 = min(夜百合层数/1, 20)
# ⇒ 直击 1.25 + 0.1/层（20 层 = +325%）、贯穿 1200 帧 + 120 帧/层（20 层 = 3600 帧 = 60 秒，改版 R8）。
AS_VALUES = dict(dd_time=_slv(1200), dd=_slv(1.25, vlv=[{"vid": 1, "min": 0, "max": 0.1}]), dd_count=_slv(1),
                 pierce=_slv(1200, vlv=[{"vid": 1, "min": 0, "max": 120}]),
                 fs_time=_slv(900), fs_speed=_slv(1), fs_charge=_slv(0))
# ACFixedSpeed 的第 4 参在 compose 里是常量（层数 1），迁移源比对时补上
FS_STACK = [{"min": 1, "max": 1}]


def ac_payloads(tree, names) -> dict[str, list[list]]:
    """树里每个 AdditionalCondition 的参数载荷，按 AC 名归组（同名可能出现多处）。"""
    out: dict[str, list[list]] = {}
    def walk(n):
        if isinstance(n, list):
            if n and isinstance(n[0], str) and n[0] in names:
                out.setdefault(n[0], []).append(copy.deepcopy(list(n[1:])))
            for x in n:
                walk(x)
    walk(tree)
    return out


def migration_problems(tree=None, values: dict | None = None, source: dict | None = None,
                       level: str = MIGRATION_LEVEL) -> list[str]:
    """R1「移动」的忠实度门禁：新块参数 vs 迁移源，差异只允许在 MIGRATION_DIFF 白名单里。

    给 ``tree`` 就从成品树里取（run_gates 用包内字节），否则从 ``AS_VALUES`` 取（静态门禁用）。
    负向用例正是审查的第 1 条（直击增伤丢掉逐层成长 vlv）与第 3 条（基础时长换成别的档位）。
    """
    src = (MIGRATION_SOURCE if source is None else source)[level]
    probs: list[str] = []
    if tree is not None:
        found = ac_payloads(tree, set(src))
        got = {}
        for ac in src:
            occ = found.get(ac) or []
            if not occ:
                probs.append(f"{ac}: 成品树里找不到")
                continue
            if any(o != occ[0] for o in occ[1:]):
                probs.append(f"{ac}: 树里 {len(occ)} 处载荷不一致")
            got[ac] = occ[0]
    else:
        v = AS_VALUES if values is None else values
        got = {"ACDirectDamage": [v["dd_time"], v["dd"], v["dd_count"]],
               "ACPiercing": [v["pierce"]],
               "ACFixedSpeed": [v["fs_time"], v["fs_speed"], v["fs_charge"], FS_STACK]}
    for ac, want in src.items():
        mine = got.get(ac)
        if mine is None:
            continue
        if len(mine) != len(want):
            probs.append(f"{ac}: 参数个数 {len(mine)} != 迁移源 {len(want)}")
            continue
        for i, (a, b) in enumerate(zip(mine, want)):
            allowed = MIGRATION_DIFF.get((ac, i))
            if allowed is not None:
                # 白名单登记的是**必须改成的样子**，不是「这一项随便改」：改少了、改多了都判红
                if a != allowed[0]:
                    probs.append(f"{ac}[{i}] 必须等于白名单登记的新值 {allowed[0]!r}"
                                 f"（登记理由：{allowed[1]}）；实际 {a!r}，迁移源是 {b!r}")
                continue
            if a == b:
                continue
            if any(isinstance(d, dict) and "vlv" in d for d in b) \
                    and not any(isinstance(d, dict) and "vlv" in d for d in a):
                probs.append(f"{ac}[{i}] 迁移源带 vlv（逐层成长），新值把它丢了：{a!r}")
                continue
            probs.append(f"{ac}[{i}] 与迁移源不同且不在白名单：{a!r} != 迁移源 {b!r}")
    return probs


def cas_text_problems(text: str = None) -> list[str]:
    """629 行的 CAS 正文不得复述前置/触发（客户端已经渲染过一遍，会重复显示）。"""
    t = CAS_TEXT if text is None else text
    return [f"CAS 正文含前置/触发措辞 {w!r}（详情页会重复渲染一遍）" for w in CAS_FORBIDDEN if w in t]


# 规则 2 的「技能强化」条目识别：正序「强化『技能名』…」与倒装「『技能名』…强化」都要认出来
# （改版 2 审查第 3 条：原来只有正序一支，语序一换就漏）。
_QUOTED = r"[「『“\"][^」』”\"]+[」』”\"]"
SKILL_ENHANCE_CLAUSE = re.compile(rf"强化\s*{_QUOTED}|{_QUOTED}[^；;。\n]*强化")
# 中文数字也算「写了数字」（规则 2 的负向用例「持续十五秒」）
_CN_NUM = r"[零一二两三四五六七八九十百千]"


def panel_text_problems(texts: dict[str, str] | None = None) -> list[str]:
    """面板文案两条规则（作者 2026-09-16 晚补充，``revision2-20260916/文案规则-补充.md``）。

    规则 1：面板不出现「无上限」三个字——没有上限的成长写到效果为止，后面什么都不跟
    （替代说法「可无限叠加」「不封顶」「不设上限」「没有上限」同样禁）；**有上限的才写上限**，
    所以写了「每层“夜百合”…」逐层成长的文案必须带 ``CAP_PHRASE``（夜百合真上限 20 层，
    上限只存在于 DSL 的 BindConditionAccumulationVariable 第 5 参，面板不写玩家无从得知）。
    规则 2：「技能强化」（``ChangeSkillFlag`` 536/704…）条目只写强化了什么，不写数字与持续秒数。

    本角色 2026-09-16 二轮复核：一行 ChangeSkillFlag 都没有 ⇒ 规则 2 无适用条目，检查器留着防回归；
    规则 1 的上限句在改版 2 按审查第 2 条补进 ``CAS_TEXT``。
    """
    t = PANEL_TEXTS if texts is None else texts
    probs: list[str] = []
    for name, text in t.items():
        text = text or ""
        for w in CAP_WORDING_BANNED:
            if w in text:
                probs.append(f"{name} 含无上限措辞 {w!r}（规则 1：没有上限就写到效果为止，后面什么都不跟）")
        # 规则 1 第三条：有上限就得写出来
        if re.search(rf"每层\s*[「『“\"]?{re.escape(UNIQUE_NAME)}", text) and CAP_PHRASE not in text:
            probs.append(f"{name} 写了“{UNIQUE_NAME}”逐层成长却没写上限"
                         f"（规则 1：有上限的才写上限，应含 {CAP_PHRASE!r}）")
        # 规则 2 只管「强化『技能名』」这类条目；「强化弹射」不带引号，不会误判
        for clause in re.split(r"[；;。\n]", text):
            if not SKILL_ENHANCE_CLAUSE.search(clause):
                continue
            if re.search(r"[0-9０-９]", clause) or re.search(rf"{_CN_NUM}+(?:%|％|秒|帧|次|层|段)", clause):
                probs.append(f"{name} 的技能强化条目写了数字（规则 2：只写强化了什么）：{clause.strip()!r}")
            if re.search(r"秒|帧", clause):
                probs.append(f"{name} 的技能强化条目写了时间（规则 2：只写强化了什么）：{clause.strip()!r}")
    return probs


def unison_lock_problems(rows_by_key: dict[str, list[list[str]]]) -> list[str]:
    """629 InvokeSkill 行必须主位绑定（改版 2 审查第 1 条换来的常驻门禁）。

    629 的演出者硬绑主位、官方零副位先例（官方 ability 全表唯一一行 629 = 1611053#0，正是本角色的
    donor，它所在键 values[0]=false）。共鸣前置是**编成条件**，与主位/副位正交，挡不住副位装配：
    副位行整体并入主位角色能力池，会由主位的技能发动拉起（wf-unison-slot-mechanics）。
    判据二选一：整键 ``values[0]``（= record0 的 c1）为 ``false``，或该行三个 precondition 块含 202。
    """
    probs: list[str] = []
    for key in sorted(rows_by_key):
        rows = rows_by_key[key]
        if not rows:
            continue
        values0 = rows[0][1] if len(rows[0]) > 1 else ""
        for i, row in enumerate(rows):
            if len(row) <= 47 or row[47] != "629":
                continue
            pre_kinds = [row[c] for c in (6, 13, 20) if c < len(row)]
            if values0 == "false" or "202" in pre_kinds:
                continue
            probs.append(f"{key}#{i} 是 629 InvokeSkill，但整键 values[0]={values0!r} 可进合击池"
                         f"、且前置 {pre_kinds} 里没有 202 OwnerIsMain ⇒ 副位会把它并进主位能力池"
                         f"（官方零副位先例；正形＝202 主位门 + c1 保持 true）")
    return probs


def lily_layer_rows(rows_by_key: dict[str, list[list[str]]]) -> list[tuple[str, int, list[str]]]:
    """全部「每层“夜百合” → …」的持续行：during 行（c5=1）+ during_trigger 134 + 固有 ID = 本角色的。"""
    out = []
    for key in sorted(rows_by_key):
        for i, row in enumerate(rows_by_key[key]):
            if len(row) > 118 and row[5] == "1" and row[97] == LAYER_TRIGGER and row[104] == UID:
                out.append((key, i, row))
    return out


def lily_layer_target_problems(rows_by_key: dict[str, list[list[str]]]) -> list[str]:
    """「每层夜百合」的加成必须落在作者指定的受益面上（改版 3 换来的常驻门禁）。

    三条判据，缺一条这门禁就成摆设：
      1. 目标只准是 ``5``+``Black``（暗属性角色全体）或 ``8``（协力球）；留 ``0`` 自身＝回归到改版 3 之前。
      2. 协力球读不到的效果 kind（``LILY_MULTIBALL_UNREADABLE``）**不准**配 target 8：
         客户端的读取函数根本不查 multiball 合计器，行是死的，面板却会照写「协力球」＝面板说谎。
      3. 协力球读得到的效果 kind（``LILY_MULTIBALL_READABLE``）必须**两个目标各一条**，
         少一条就是「给了暗属性全体没给协力球」或反过来，都没做到作者要求。
    """
    probs: list[str] = []
    seen: dict[str, set[str]] = {}
    for key, i, row in lily_layer_rows(rows_by_key):
        kind, target, groups = row[109], row[110], row[111]
        seen.setdefault(kind, set()).add(target)
        if target == LILY_PARTY_TARGET:
            if groups != LILY_PARTY_GROUPS:
                probs.append(f"{key}#{i} 每层夜百合给全队但目标角色组是 {groups!r}，应为 {LILY_PARTY_GROUPS!r}"
                             f"（空串＝谁都不匹配的死值，wf-character-groups-semantics）")
        elif target == LILY_ASSIST_TARGET:
            if kind in LILY_MULTIBALL_UNREADABLE:
                probs.append(f"{key}#{i} 把 during kind {kind} 发给协力球(target 8)，但客户端读取路径不查 "
                             f"multiball 合计器 ⇒ 死行、面板却写「协力球」")
        else:
            probs.append(f"{key}#{i} 每层夜百合的目标是 {target!r}（改版 3 只许 "
                         f"{LILY_PARTY_TARGET}+{LILY_PARTY_GROUPS} 暗属性角色全体 或 {LILY_ASSIST_TARGET} 协力球）")
    for kind, targets in sorted(seen.items()):
        want = {LILY_PARTY_TARGET, LILY_ASSIST_TARGET} if kind in LILY_MULTIBALL_READABLE else {LILY_PARTY_TARGET}
        if targets != want:
            probs.append(f"每层夜百合 during kind {kind} 的受益面是 {sorted(targets)}，应为 {sorted(want)}"
                         f"（协力球可达的 kind 必须暗属性全体与协力球各一条）")
    return probs


# ---- 改版 2 与上一轮设计件的差异登记 -----------------------------------------------------
# 设计件 ``revision-20260916/primula/primula.json`` 是上一轮的**只读证据**，本轮不改它；
# 审查换来的两处改动因此与设计件不同，逐项登记在下面。比对时先把设计件补到改版 2 形态，
# **未登记的任何差异照样判红** —— 登记的是「必须改成什么」，不是「这里随便改」。
#   审查第 1 条：629 行 precondition1 改 202 主位门、暗共鸣退到 precondition2；
#   审查第 2 条：CAS 正文插入上限句（夜百合真上限 20 层，面板不写玩家看不到）。
REV2_ROW_DELTA = {(f"{CID}1", 2): {6: "202", 9: "", 10: "", 11: "",
                                   13: "2", 16: "600000", 17: "600000", 18: "Black"}}
REV2_CAS_INSERT = f"（{CAP_PHRASE}）"


def rev2_design_rows(slot_key: str, rows: list[list[str]]) -> list[list[str]]:
    """设计件里某一槽的行 → 改版 2 期望形态（只改 ``REV2_ROW_DELTA`` 登记过的列）。"""
    out: list[list[str]] = []
    for i, row in enumerate(rows):
        r = list(row)
        for col, val in (REV2_ROW_DELTA.get((slot_key, i)) or {}).items():
            r[col] = val
        out.append(r)
    return out


def rev2_design_cas() -> str:
    """改版 2 的 CAS 正文去掉上限句 = 设计件里的原文（唯一允许的差异就是这一句）。"""
    return CAS_TEXT.replace(REV2_CAS_INSERT, "")


# ---- 改版 3 与设计件的差异登记（同 REV2：登记的是「必须改成什么」，未登记的差异照样判红）------------
#   作者要求：夜百合的能力3 加成给到暗属性角色全体和协力球，而不是自身。
#   A3#4（设计件 slot3 index 3，独立乘区直击）目标列 0 自身 → 5+Black 暗属性角色全体。
REV3_ROW_DELTA = {(f"{CID}3", 3): {110: LILY_PARTY_TARGET, 111: LILY_PARTY_GROUPS}}
#   设计件里没有的新行：(槽键, 插入位置) -> (照抄 delta 后的哪一行, 该行基础上要改的列)。
#   每层攻击力那条再发一份给协力球；源行下标必须小于插入位置（目前只有一条，多条时需自行核对下标位移）。
REV3_ROW_INSERT = {(f"{CID}3", 3): (2, {110: LILY_ASSIST_TARGET, 111: ""})}


def rev3_design_rows(slot_key: str, rows: list[list[str]]) -> list[list[str]]:
    """改版 2 形态的设计行 → 改版 3 期望形态（先改登记过的列，再插入登记过的新行）。"""
    out = [list(row) for row in rows]
    for i, row in enumerate(out):
        for col, val in (REV3_ROW_DELTA.get((slot_key, i)) or {}).items():
            row[col] = val
    for (key, pos), (src, edits) in sorted(REV3_ROW_INSERT.items(), key=lambda kv: kv[0][1]):
        if key != slot_key:
            continue
        if not src < pos <= len(out):
            raise KitError(f"REV3_ROW_INSERT {key}@{pos}: 源行下标 {src} 必须小于插入位置且位置在范围内")
        row = list(out[src])
        for col, val in edits.items():
            row[col] = val
        out.insert(pos, row)
    return out


def design_rows_expected(slot_key: str, rows: list[list[str]]) -> list[list[str]]:
    """设计件原行 → 当前改版期望的成品行（rev2 列 delta → rev3 列 delta + 新行）。"""
    return rev3_design_rows(slot_key, rev2_design_rows(slot_key, rows))

class KitError(RuntimeError):
    pass


# ---------------------------------------------------------------- 行构建

def _donor_row(ctx_or_pack, table: str, key: str, line: int) -> list[str]:
    import wf_seasonal7_common as C
    import wf_mod_tool as core
    logical = f"master/ability/{table}.orderedmap"
    pack = getattr(ctx_or_pack, "pack", ctx_or_pack)
    raw = pack.official_read(logical, "common")
    if raw is None:
        raise KitError(f"official baseline lacks {logical}; donors must be official")
    rows = core.read_orderedmap_file_from_bytes(raw)
    if key not in rows:
        raise KitError(f"official donor missing: {table}:{key}")
    lines = C.csv_split(rows[key])
    if not 1 <= line <= len(lines):
        raise KitError(f"official donor {table}:{key} has {len(lines)} lines, want #{line}")
    return list(lines[line - 1])


def _apply_edits(row: list[str], edits: dict[int, tuple], label: str) -> list[str]:
    out = list(row)
    for col, (old, new) in edits.items():
        if col >= len(out):
            raise KitError(f"{label}: column {col} out of range {len(out)}")
        if old is not None and out[col] != old:
            raise KitError(f"{label}: c{col} expected {old!r}, found {out[col]!r}")
        out[col] = new
    return out


def build_leader_rows(pack) -> list[list[str]]:
    return [_apply_edits(_donor_row(pack, t, k, n), e, f"leader#{i + 1} <= {t}:{k}#L{n}")
            for i, (t, k, n, e) in enumerate(LEADER_PLAN)]


def build_ability_rows(pack) -> dict[str, list[list[str]]]:
    out = {}
    for slot, plan in ABILITY_PLAN.items():
        out[f"{CID}{slot}"] = [_apply_edits(_donor_row(pack, t, k, n), e, f"A{slot}#{i + 1} <= {t}:{k}#L{n}")
                               for i, (t, k, n, e) in enumerate(plan)]
    return out


def build_unique_row(pack) -> list[str]:
    import wf_seasonal7_common as C
    import wf_mod_tool as core
    raw = pack.official_read(UNIQUE, "common")
    if raw is None:
        raise KitError("official baseline lacks unique_condition table")
    donor = C.csv_split(core.read_orderedmap_file_from_bytes(raw)[UNIQUE_DONOR])[0]
    row = _apply_edits(donor, UNIQUE_EDITS, f"unique_condition:{UNIQUE_DONOR}")
    if row[4] in ("", "(None)") or int(row[4]) != int(UNIQUE_MAX):
        raise KitError(f"unique max_accumulation must be {UNIQUE_MAX}, got {row[4]!r}")
    return row


def build_action_rows(pack) -> dict[str, list[str]]:
    import wf_seasonal7_common as C
    import wf_mod_tool as core
    raw = pack.official_read(ACTION, "common")
    if raw is None:
        raise KitError("official baseline lacks action_skill table")
    inner = core.load_nested_table_bytes(raw, ACTION).rows[ACTION_DONOR].text_rows()
    out = {}
    for level, edits in ACTION_EDITS.items():
        row = _apply_edits(C.csv_split(inner[level])[0], edits, f"action_skill:{ACTION_DONOR}/{level}")
        row[1] = SKILL_DESC
        if len(row) != 24:
            raise KitError(f"action_skill row length {len(row)} != 24")
        out[level] = row
    return out


def text_row() -> list[str]:
    return [TEXTS["name"], TEXTS["furigana"], PROFILE, TEXTS["title"], SKILL_NAME_1, SKILL_DESC,
            SKILL_NAME_2, SKILL_DESC, "(None)", "(None)", LEADER_NAME, CV]


# ---------------------------------------------------------------- 技能树拼装（移植 design/_tmp/primula/final/f3_tree.py）

def _cmd(node):
    if not (isinstance(node, list) and node and node[0] in ("Command", "Event")):
        raise KitError(f"not a Command/Event node: {str(node)[:80]}")
    return node[1]


def _get(tree, path):
    node = tree
    for k in path:
        node = node[k]
    return node


class _Log:
    def __init__(self):
        self.items: list[dict] = []

    def setp(self, block, node, i, old, new):
        arr = _cmd(node)
        if arr[i + 1] != old:
            raise KitError(f"{block}: {arr[0]} p{i} expected {old!r}, found {arr[i + 1]!r}")
        arr[i + 1] = new
        self.items.append(dict(block=block, command=arr[0], param=f"p{i}", old=old, new=new))

    def expect(self, block, node, i, old):
        arr = _cmd(node)
        if arr[i + 1] != old:
            raise KitError(f"{block}: {arr[0]} p{i} expected {old!r}, found {arr[i + 1]!r}")

    def note(self, block, command, param, old, new):
        self.items.append(dict(block=block, command=command, param=param, old=old, new=new))


def _program(pack, code: str, level: str) -> str:
    import wf_seasonal7_common as C
    import wf_mod_tool as core
    raw = pack.official_read(ACTION, "common")
    table = core.load_nested_table_bytes(raw if raw is not None else pack.live_table_bytes(ACTION), ACTION)
    if code not in table.rows:
        table = core.load_nested_table_bytes(pack.live_table_bytes(ACTION), ACTION)
    return C.csv_split(table.rows[code].text_rows()[level])[0][7]


def compose_tree(pack, level: str) -> tuple[list, list[dict]]:
    """按设计块清单从官方 DSL 拼装（特效路径保持官方，稍后由 rewrite_effect_refs 改到克隆目录）。"""
    log = _Log()
    W = pack.template_dsl(_program(pack, "blackflower_wiz", level))
    S2 = pack.template_dsl(_program(pack, "blackflower_wiz_smr22", level))
    v = TREE_VALUES[level]
    root = []
    # B0 扇舞（smr22 heart，挂 -17）
    fan = copy.deepcopy(_get(S2, [11, 1, 1]))
    if _cmd(fan)[0] != "ShowEffect":
        raise KitError("B0 source is not ShowEffect")
    log.setp("B0_fan", fan, 0, HEART_NAME, "扇舞")
    log.expect("B0_fan", fan, 1, ["SpecifyEffectDirectly",
                                  "battle/effect/skill_unique/blackflower_wiz_smr22/blackflower_wiz_smr22_heart"])
    log.setp("B0_fan", fan, 7, -300, 0)
    root.append(fan)
    # B2 花园（161069 整棵 FindNear 子树）
    g = copy.deepcopy(_get(W, [11, 1, 0]))
    if _cmd(g)[0] != "FindNearSubjects":
        raise KitError("B2 source is not FindNearSubjects")
    log.setp("B2_garden", g, 4, 0, 10)
    rp = _get(g, [1, 6, 1, 0])
    if _cmd(rp)[0] != "CreateReferencePoint":
        raise KitError("B2 RP missing")
    log.setp("B2_garden.RP", rp, 0, 0, 10)
    log.setp("B2_garden.RP", rp, 8, 200, 280)
    log.setp("B2_garden.RP", rp, 9, 1, 11)
    rpb = _get(rp, [1, 11, 1])
    back, front, wait15 = rpb[0], rpb[1], rpb[2]
    log.expect("B2_garden.fx_back", back, 1,
               ["SpecifyEffectDirectly", "battle/effect/skill_unique/blackflower_wiz/blackflower_wiz_flower_back"])
    log.setp("B2_garden.fx_back", back, 2, 1, 11)
    log.expect("B2_garden.fx_front", front, 1,
               ["SpecifyEffectDirectly", "battle/effect/skill_unique/blackflower_wiz/blackflower_wiz_flower"])
    log.setp("B2_garden.fx_front", front, 2, 1, 11)
    if not (_cmd(wait15)[0] == "Wait" and _cmd(wait15)[1] == 15):
        raise KitError("B2 Wait 15 missing")
    w15b = _get(wait15, [1, 3, 1])
    ha_a, ha_b = w15b
    if _cmd(ha_b)[0] != "CreateHitArea":
        raise KitError("B2 HA_B missing")
    w15b[:] = [ha_a]
    log.note("B2_garden.wait15", "Wait", "p2 body", "[HA_A, HA_B self regen]", "[HA_A]")
    log.setp("B2_garden.HA_A", ha_a, 1, 1, 11)
    for i, (o, n) in zip((18, 20, 21), ((2, 12), (3, 13), (4, 14))):
        log.setp("B2_garden.HA_A", ha_a, i, o, n)
    log.setp("B2_garden.HA_A", ha_a, 23, 0, 4)
    onhit = _get(ha_a, [1, 23, 1])
    cna = onhit[1]
    if _cmd(cna)[0] != "CreateNormalAttack":
        raise KitError("B2 HA_A CNA missing")
    log.setp("B2_garden.HA_A.CNA", cna, 0, 4, 14)
    log.setp("B2_garden.HA_A.CNA", cna, 4, 13, 20)
    log.setp("B2_garden.HA_A.CNA", cna, 5, _cmd(cna)[6], v["garden_mul"])
    log.expect("B2_garden.HA_A.CNA", cna, 14,
               ["SpecifyHitEffectDirectly", ["SpecifyEffectDirectly",
                                             "battle/effect/skill_unique/blackflower_wiz/blackflower_wiz_hit"], False])
    tol = onhit[2]
    if not (_cmd(tol)[0] == "CreateCondition" and _cmd(tol)[2][0][0] == "ACToleranceOfElement"):
        raise KitError("B2 tolerance CC missing")
    log.setp("B2_garden.HA_A.tolerance", tol, 0, 4, 14)
    # B3 烟花：smr22 Wait38 特效 → Wait150；Wait60 绑定+判定区 → Wait172
    w38 = copy.deepcopy(_get(S2, [11, 1, 2, 1, 11, 1, 0]))
    if _cmd(w38)[0] != "Wait":
        raise KitError("B3 Wait38 missing")
    log.setp("B3_hanabi.wait_fx", w38, 0, 38, 150)
    eff = _get(w38, [1, 3, 1, 0])
    log.setp("B3_hanabi.fx_burst", eff, 0, "攻撃", "烟花")
    log.expect("B3_hanabi.fx_burst", eff, 1,
               ["SpecifyEffectDirectly", "battle/effect/skill_unique/blackflower_wiz_smr22/blackflower_wiz_smr22_flower"])
    log.setp("B3_hanabi.fx_burst", eff, 2, 0, 11)
    w60 = copy.deepcopy(_get(S2, [11, 1, 2, 1, 11, 1, 2]))
    if _cmd(w60)[0] != "Wait":
        raise KitError("B3 Wait60 missing")
    log.setp("B3_hanabi.wait_hit", w60, 0, 60, 172)
    w60b = _get(w60, [1, 3, 1])
    bind2, ha_f, leader = w60b[0], w60b[1], w60b[2]
    if _cmd(leader)[0] != "IfThisCharacterIsLeader":
        raise KitError("B3 leader heal block missing")
    log.setp("B3_hanabi.bind_vid2", bind2, 2, ["DCUnique", 11], ["DCUnique", UID_INT])
    # 改版 R7：烟花倍率变量的上限必须跟随夜百合新上限，漏改就停在 10 层
    log.setp("B3_hanabi.bind_vid2", bind2, 4, 10, UNIQUE_CAP)
    log.setp("B3_hanabi.HA_F", ha_f, 1, 0, 11)
    log.setp("B3_hanabi.HA_F", ha_f, 8, ["Circle", [{"min": 250, "max": 250}]], ["Circle", [{"min": 300, "max": 300}]])
    for i, (o, n) in zip((18, 20, 21), ((3, 18), (4, 19), (5, 20))):
        log.setp("B3_hanabi.HA_F", ha_f, i, o, n)
    log.setp("B3_hanabi.HA_F", ha_f, 23, 0, 4)
    fcna = _get(ha_f, [1, 23, 1, 0])
    if _cmd(fcna)[0] != "CreateNormalAttack":
        raise KitError("B3 HA_F CNA missing")
    log.setp("B3_hanabi.HA_F.CNA", fcna, 0, 5, 20)
    log.setp("B3_hanabi.HA_F.CNA", fcna, 4, 167, 100)
    log.setp("B3_hanabi.HA_F.CNA", fcna, 5, _cmd(fcna)[6], v["fin_mul"])
    log.setp("B3_hanabi.HA_F.CNA", fcna, 12, *FINALE_DETOUGHNESS)     # 2026-09-27 第二批：削韧 20→14
    w60b[:] = [bind2, ha_f]
    log.note("B3_hanabi.wait_hit", "Wait", "p2 body", "[Bind vid2, HA, IfThisCharacterIsLeader(heal)]", "[Bind vid2, HA]")
    rpb.extend([w38, w60])
    root.append(g)
    # 改版 R1/R13：原根部 Wait 1 容器（Bind vid1 + B4 全队增益 + B6 ≥5 层速度固定）整块迁到
    # 能力1 的 ability_skill DSL（compose_ability_skill_tree），技能树只留 [B0 扇舞, B2 花园(含 B3 烟花)]。
    log.note("W1", "Wait", "root block", "[Bind vid1, B4 team buffs, B6 fixed speed]",
             "removed → ability_skill_" + CODE)
    tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", root]]
    if W[:11] != tree[:11]:
        raise KitError(f"root head differs from 161069 source: {W[:11]}")
    if len(root) != 2:
        raise KitError(f"skill tree root must hold 2 blocks after the revision, got {len(root)}")
    return tree, log.items


def compose_ability_skill_tree(pack) -> tuple[list, list[dict]]:
    """能力1#3（629 InvokeSkill）调用的 ability_skill DSL（改版 R1/R2/R3/R8/R13）。

    块序：Bind vid1（夜百合层数，cap 20）→ FindAll(33,[6]) 暗属性角色 → FindAll(145,[]) 协力球 → ≥5 层速度固定。
    每块里 CreateCondition 挂 ACDirectDamage（+125% ＋ 10%/层，1200 帧）与 ACPiercing（1200 帧 ＋ 120 帧/层）；
    两块用同一组固定区分键，重复赋予只刷新不叠加。

    参数不是新设计的：整套取自上一轮 live 技能树被搬走的那三块（``MIGRATION_SOURCE["2"]``，「＋」档），
    差异由 ``MIGRATION_DIFF`` 白名单列明，``migration_problems()`` 逐项守住。
    """
    log = _Log()
    S2 = pack.template_dsl(_program(pack, "blackflower_wiz_smr22", "2"))
    SA = pack.template_dsl(_program(pack, "sing_android_hw20", "2"))
    MW = pack.template_dsl(_program(pack, "mirror_witch", "2"))
    SW = pack.template_dsl(_program(pack, "special_week", "2"))
    AS = pack.template_dsl("battle/action/skill/action/ability_skill/"
                           "ability_skill_estateguild_leader$ability_skill_estateguild_leader")
    v = AS_VALUES

    # B1 Bind vid1 = min(夜百合层数 / 1, 20)（官方 smr22 Wait 1 容器里的绑定）
    w1b = _get(copy.deepcopy(_get(S2, [11, 1, 2, 1, 11, 1, 1])), [1, 3, 1])
    b1 = w1b[0]
    if _cmd(b1)[0] != "BindConditionAccumulationVariable":
        raise KitError("AS Bind vid1 missing")
    log.setp("AS.bind_vid1", b1, 2, ["DCUnique", 11], ["DCUnique", UID_INT])
    log.setp("AS.bind_vid1", b1, 4, 10, UNIQUE_CAP)
    log.expect("AS.bind_vid1", b1, 0, -17)
    log.expect("AS.bind_vid1", b1, 1, 1)
    log.expect("AS.bind_vid1", b1, 3, 1)

    def team_block(label: str, bind_id: int, selector: int, filt: list[int]):
        """sing_android_hw20 的 FindAllSubjects(33) 壳 + mirror_witch 的 ACPiercing。"""
        fa = copy.deepcopy(_get(SA, [11, 1, 4]))
        if not (_cmd(fa)[0] == "FindAllSubjects" and _cmd(fa)[2] == 33):
            raise KitError(f"{label}: donor FindAll(33) missing")
        log.expect(label, fa, 7, ["DoNothing"])          # IfTargetNotFound 枚举位，不是表达式位
        if bind_id != 0:
            log.setp(label, fa, 0, 0, bind_id)
        if selector != 33:
            log.setp(label, fa, 1, 33, selector)
        if filt:
            log.setp(label, fa, 2, [], list(filt))
        body = _get(fa, [1, 9, 1])
        dd = body[1]
        if _cmd(dd)[2][0][0] != "ACDirectDamage":
            raise KitError(f"{label}: donor ACDirectDamage missing")
        if bind_id != 0:
            log.setp(label + ".ACDirectDamage", dd, 0, 0, bind_id)
        # 两块共用同一份 AS_VALUES：deepcopy 出来，避免两棵子树共享同一个 SLv 列表对象
        log.setp(label + ".ACDirectDamage", dd, 1, _cmd(dd)[2],
                 [["ACDirectDamage", copy.deepcopy(v["dd_time"]), copy.deepcopy(v["dd"]),
                   copy.deepcopy(v["dd_count"])]])
        log.setp(label + ".ACDirectDamage", dd, 6, "", KEY_DD)
        pc = copy.deepcopy(_get(MW, [11, 1, 3, 1, 9, 1, 0]))
        if _cmd(pc)[2][0][0] != "ACPiercing":
            raise KitError(f"{label}: donor ACPiercing missing")
        if bind_id != 0:
            log.setp(label + ".ACPiercing", pc, 0, 0, bind_id)
        log.setp(label + ".ACPiercing", pc, 1, _cmd(pc)[2], [["ACPiercing", copy.deepcopy(v["pierce"])]])
        log.setp(label + ".ACPiercing", pc, 6, "", KEY_PC)
        body[:] = [dd, pc]
        log.note(label, "FindAllSubjects", "p8 body", "[CC ACAttackPoint, CC ACDirectDamage]",
                 "[CC ACDirectDamage(fixed key), CC ACPiercing(vlv vid1, fixed key)]")
        return fa

    # B2 暗属性角色（33 = 主小队 + 存活多球小队成员；过滤数组是 1 基属性码，[6] = 暗）
    team_dark = team_block("AS.team_dark", 0, 33, [6])
    # B3 协力球（145 = 全部多球小队成员，不过滤属性）
    team_ball = team_block("AS.team_ball", 1, 145, [])

    # B4 ≥5 层 → 暗主队最大速度固定（special_week_2 块形状原样搬入）
    fs = copy.deepcopy(_get(SW, [11, 1, 4, 1, 1, 1, 0]))
    if not (_cmd(fs)[0] == "FindAllSubjects" and _cmd(fs)[2] == 82):
        raise KitError("AS FindAll(82) missing")
    log.setp("AS.layers5.f82", fs, 0, 1, 2)
    log.setp("AS.layers5.f82", fs, 2, [], [6])
    fcc = _get(fs, [1, 9, 1, 0])
    if not (_cmd(fcc)[2][0][0] == "ACFixedSpeed" and _cmd(fcc)[10] == 3):
        raise KitError("AS ACFixedSpeed (target kind 3) missing")
    log.setp("AS.layers5.ACFixedSpeed", fcc, 0, 1, 2)
    log.setp("AS.layers5.ACFixedSpeed", fcc, 1, _cmd(fcc)[2],
             [["ACFixedSpeed", v["fs_time"], v["fs_speed"], v["fs_charge"], [{"min": 1, "max": 1}]]])
    log.setp("AS.layers5.ACFixedSpeed", fcc, 6, "スペシャルウィーク最大速度固定", KEY_FS)
    # 否分支必须是 ["Block", []]；写 ["DoNothing"] 进游戏 F1009（wf-dsl-donothing-enum-trap）
    cond = ["Command", ["ConditionalsConditionAccumulationNumber", ["DCUnique", UID_INT], 5,
                        ["Block", [fs]], ["Block", []]]]
    log.note("AS.layers5", "ConditionalsConditionAccumulationNumber", "new node", "special_week_2 shape",
             f"[DCUnique {UID}],5,Block[FindAll(2,82,[6]) ACFixedSpeed],Block[]")

    root = [b1, team_dark, team_ball, cond]
    tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", root]]
    if AS[:11] != tree[:11]:
        raise KitError(f"root head differs from official ability_skill source: {AS[:11]}")
    log.note("AS", "ActionDsl", "root", "battle/action/skill/action/ability_skill/ability_skill_estateguild_leader",
             AS_PROGRAM)
    return tree, log.items


# ---------------------------------------------------------------- 静态校验（树）

def _tag(v):
    return v[0] if isinstance(v, list) and v and isinstance(v[0], str) else None


def _kind(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "num"
    if isinstance(v, str):
        return "str"
    if isinstance(v, dict):
        return "dict"
    if isinstance(v, list):
        if v and all(isinstance(x, dict) for x in v):
            return "slv"
        t = _tag(v)
        if t in ("Block", "Command", "Event"):
            return "expr"
        if t is not None:
            return "enum:" + t
        return "list"
    return type(v).__name__


def _typed(v):
    """带类型的规范形（AMF3 int/double 区分）。"""
    if isinstance(v, bool):
        return ["b", v]
    if isinstance(v, int):
        return ["i", v]
    if isinstance(v, float):
        return ["f", v]
    if isinstance(v, list):
        return ["l", [_typed(x) for x in v]]
    if isinstance(v, dict):
        return ["d", {k: _typed(x) for k, x in v.items()}]
    return ["s", v]


def signature_problems(tree, sig: dict | None) -> list[str]:
    """官方语料参数种类（official_sig.json）+ wf_dsl_sig 参数个数/嵌套枚举（审查 r6_tree.py）
    + ActionDslExpression 位必须是 Block/Command/Event（["DoNothing"] 放在表达式位 = F1009）。"""
    import wf_dsl_sig as SIG
    probs: list[str] = []

    def walk(n):
        if isinstance(n, list):
            t = _tag(n)
            if t in ("Command", "Event") and isinstance(n[1], list):
                c = n[1]
                exp = SIG.COMMANDS.get(c[0]) or SIG.EVENTS.get(c[0])
                if exp is None:
                    probs.append(f"unknown command {c[0]}")
                elif len(c) - 1 != len(exp):
                    probs.append(f"arity {c[0]} {len(c) - 1} != {len(exp)}")
                for i, p in enumerate(c[1:], 1):
                    k = _kind(p)
                    if exp is not None and i - 1 < len(exp) and exp[i - 1] == "ActionDslExpression" \
                            and _tag(p) not in ("Block", "Command", "Event"):
                        probs.append(f"{c[0]}#{i} expression slot holds {str(p)[:40]} (F1009)")
                    if sig is None:
                        continue
                    o = sig.get(f"{c[0]}#{i}")
                    if o is None:
                        probs.append(f"{c[0]}#{i} absent from official corpus")
                    elif k not in o and not (k == "list" and p == []):
                        probs.append(f"{c[0]}#{i} kind {k} not in official {o}")
                    if k.startswith("enum:"):
                        for j, q in enumerate(p[1:], 1):
                            o2 = sig.get(f"{c[0]}#{i}>{p[0]}#{j}")
                            if o2 is None:
                                probs.append(f"{c[0]}#{i}>{p[0]}#{j} absent from official corpus")
                            elif _kind(q) not in o2:
                                probs.append(f"{c[0]}#{i}>{p[0]}#{j} kind {_kind(q)} not in {o2}")
                    if k == "list":
                        for q in p:
                            if _tag(q) and _tag(q) not in ("Block", "Command", "Event"):
                                for j, r in enumerate(q[1:], 1):
                                    o3 = sig.get(f"{q[0]}#{j}")
                                    if o3 is None or _kind(r) not in o3:
                                        probs.append(f"{c[0]}>{q[0]}#{j} kind {_kind(r)} not in {o3}")
            for x in n:
                walk(x)
        elif isinstance(n, dict):
            for x in n.values():
                walk(x)
    walk(tree)
    return sorted(set(probs))


def effect_paths(tree) -> list[str]:
    out = set()

    def walk(n):
        if isinstance(n, list):
            if len(n) == 2 and n[0] == "SpecifyEffectDirectly" and isinstance(n[1], str):
                out.add(n[1])
            for x in n:
                walk(x)
        elif isinstance(n, dict):
            for x in n.values():
                walk(x)
    walk(tree)
    return sorted(out)


def create_conditions(tree) -> list[dict]:
    out = []

    def walk(n):
        if isinstance(n, list):
            if _tag(n) == "Command" and isinstance(n[1], list) and n[1][0] == "CreateCondition":
                c = n[1]
                out.append(dict(subject=c[1], ac=c[2][0][0], key=c[7], target_kind=c[10], force=c[12],
                                vlv="vlv" in json.dumps(c[2])))
            for x in n:
                walk(x)
    walk(tree)
    return out


def tree_checks(tree, sig: dict | None) -> dict[str, Any]:
    import wf_client_legality as LG
    import wf_dsl
    import wf_seasonal7_common as C
    import zlib
    result: dict[str, Any] = {}
    wrapper = isinstance(tree, dict) or not (isinstance(tree, list) and tree and tree[0] == "ActionDsl")
    result["bare_tree"] = not wrapper
    try:
        raw = C.amf_bytes(tree)
        back = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        result["roundtrip"] = _typed(back) == _typed(tree)
        result["deflated_bytes"] = len(raw)
    except Exception as exc:                       # noqa: BLE001
        result["roundtrip"] = False
        result["roundtrip_error"] = f"{type(exc).__name__}: {exc}"
    result["element"] = LG.action_dsl_element_problems(tree, ELEMENT)
    result["subject_binding"] = LG.action_dsl_subject_binding_problems(tree)
    result["hit_area_target"] = LG.action_dsl_hit_area_target_problems(tree)
    result["player_side"] = wf_dsl.player_side_dsl_problems(tree)
    result["signature"] = signature_problems(tree, sig)
    result["official_sig_loaded"] = sig is not None
    result["root_head"] = {"movementPriority": tree[1], "buffTargetAs": tree[10]}
    result["create_conditions"] = create_conditions(tree)
    result["effect_paths"] = effect_paths(tree)
    ok = (result["bare_tree"] and result["roundtrip"] and sig is not None
          and not any(result[k] for k in ("element", "subject_binding", "hit_area_target", "player_side", "signature")))
    # 固定区分键（审查 #1）：vlv CreateCondition 必须带非空键
    vlv_nokey = [c for c in result["create_conditions"] if c["vlv"] and not c["key"]]
    result["vlv_without_key"] = vlv_nokey
    result["ok"] = bool(ok and not vlv_nokey)
    return result


def _load_json(root: Path, rel: str):
    path = root / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


# ---------------------------------------------------------------- 特效 timeline 内嵌 SE（预载引用）

def timeline_sound_report(timeline, locate) -> tuple[dict[str, bool], list[str]]:
    """timeline 的 ``sounds[].path`` 是战斗预载引用：写错前缀＝进战斗「数据不足」（1.4.529 魔王热修先例）。

    ``locate(logical) -> truthy`` 按 ``<path>.mp3`` 解析（包内或 live）。返回 ``({path: 是否解析}, problems)``；
    解析失败、条目不是对象、缺 path、``sounds`` 不是列表都记 problem。没有 SE 的 timeline 返回空。
    """
    resolved: dict[str, bool] = {}
    problems: list[str] = []
    if not isinstance(timeline, dict):
        return resolved, [f"timeline is {type(timeline).__name__}, not an object"]
    sounds = timeline.get("sounds")
    if sounds is None:
        return resolved, problems
    if not isinstance(sounds, list):
        return resolved, [f"sounds is {type(sounds).__name__}, not a list"]
    for i, entry in enumerate(sounds):
        path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(path, str) or not path:
            problems.append(f"sounds[{i}] has no path: {entry!r}")
            continue
        ok = bool(locate(path + ".mp3"))
        resolved[path] = resolved.get(path, True) and ok
        if not ok:
            problems.append(f"sound unresolved: {path}.mp3")
    return resolved, problems


def sound_locator(pack):
    """SE 解析：包内任一客户端根，或 live store。"""
    import wf_seasonal7_common as C
    return lambda logical: any(pack.pkg_has(r, logical) for r in C.CLIENT_ROOTS) \
        or pack.live_locate(logical) is not None


def effect_timeline_gate(pack, families: dict[str, dict]) -> tuple[dict[str, dict], list[str]]:
    """kit 声明的特效族必须按 ``EFFECT_FAMILIES`` 复制齐；每个复制基名的 timeline 在包内且 SE 全部可解析。"""
    import wf_seasonal7_common as C
    problems: list[str] = []
    for fam in EFFECT_FAMILIES:
        dst = f"battle/effect/skill_unique/{CODE}_{fam['dst_subdir']}"
        got = sorted((families.get(dst) or {}).get("copied_bases") or [])
        if got != sorted(fam["fx_names"]):
            problems.append(f"effect family {dst} copied_bases {got} != {sorted(fam['fx_names'])}")
    locate = sound_locator(pack)
    report: dict[str, dict] = {}
    for dst_dir, fam in families.items():
        for base in fam.get("copied_bases") or []:
            tl = f"{dst_dir}/{base}.timeline.amf3.deflate"
            if not pack.pkg_has("common", tl):
                problems.append(f"effect timeline missing in package: {tl}")
                continue
            resolved, probs = timeline_sound_report(C.amf_parse(pack.pkg_path("common", tl).read_bytes()), locate)
            report[tl] = resolved
            problems += [f"{tl}: {p}" for p in probs]
    return report, problems


# ---------------------------------------------------------------- 集成待办（语音/像素，Integrate 阶段）

SPEECH = "master/character/character_speech.orderedmap"
PIXEL_SHEETS = (f"character/{CODE}/pixelart/sprite_sheet.png", f"character/{CODE}/pixelart/special_sprite_sheet.png")


def integration_pending(speech_rows: list[list[str]], owners: dict[str, str], files,
                        pixel_content_problems: list[str] | None = None) -> dict[str, Any]:
    """kit 范围之外、发布前必须由 Integrate 装好的内容（只报告，不计入 kit 门禁 ``all_pass``）。

    - 语音：``wf_seasonal7_voice.SLOTS`` 22 条 ``character/<code>/voice/<slot>.mp3`` 全在包内且登记 owner=voice；
      speech 表 8 行、voice_path（c4）全部落在 home_0..5/ally 规划槽内（母本占位名如 ``home/a_au_konokakko`` 不算）；
      包内 voice 目录不再残留规划槽之外的文件（母本旧语音已删除）。
    - 像素：两张 sheet 在包内且登记 owner=pixel；给出 ``pixel_content_problems``（``pixel_problems`` 结果）时还须为空。
    ``owners``：``{"common:<logical>": owner}``；``files``：包内 common 根 ``character/<code>/`` 下的逻辑路径集合。
    """
    import wf_seasonal7_voice as V
    files = set(files)
    voice_logical = {slot: f"character/{CODE}/voice/{slot}.mp3" for slot in V.SLOTS}
    missing = [s for s, lg in voice_logical.items() if lg not in files]
    not_owned = [s for s, lg in voice_logical.items() if lg in files and owners.get(f"common:{lg}") != "voice"]
    planned_speech = set(V.SUBTITLE_SLOTS)
    outside = [r[4] if len(r) > 4 else repr(r) for r in speech_rows if len(r) <= 4 or r[4] not in planned_speech]
    left = sorted(lg for lg in files if lg.startswith(f"character/{CODE}/voice/")
                  and lg not in set(voice_logical.values()))
    voice = {"slots_expected": len(voice_logical), "slots_missing": missing, "slots_not_voice_owned": not_owned,
             "speech_rows": len(speech_rows), "speech_paths_outside_plan": outside,
             "template_voice_files_left": left}
    voice["clear"] = not missing and not not_owned and not outside and not left \
        and len(speech_rows) == len(planned_speech)
    pixel = {"sheets": {lg: (owners.get(f"common:{lg}") if lg in files else None) for lg in PIXEL_SHEETS}}
    if pixel_content_problems is not None:
        pixel["content_problems"] = list(pixel_content_problems)
    pixel["clear"] = all(o == "pixel" for o in pixel["sheets"].values()) and not pixel_content_problems
    return {"voice": voice, "pixel": pixel, "clear": voice["clear"] and pixel["clear"],
            "note": "kit 门禁 all_pass 只覆盖 kit 范围；clear=false 时包内仍有母本语音/speech/像素占位，不得发布"}


def package_integration_pending(pack) -> dict[str, Any]:
    import wf_seasonal7_common as C
    speech = C.csv_split(pack.pkg_flat(SPEECH).get(CID) or "") if pack.pkg_has("common", SPEECH) else []
    base = pack.pkg_path("common", f"character/{CODE}")
    common = (pack.package / "roots" / "common").resolve()
    files = {p.relative_to(common).as_posix() for p in base.rglob("*") if p.is_file()} if base.is_dir() else set()
    return integration_pending(speech, pack.owned_outputs(), files, pixel_problems(pack, pack.root))


# ---------------------------------------------------------------- 像素小人（Integrate 阶段）

PIXEL_DIR = f"{BATCH}/pixel/primula"
PIXEL_REVIEW_JSON = f"{BATCH}/pixel/_review/verify_all.json"
PIXEL_REVIEW_MD = f"{BATCH}/pixel/REVIEW.md"
# sheet 基名 → 同组元数据（atlas / frame / timeline），元数据保持母本（仅 character/<母本>/ 前缀由 assets 改写）
PIXEL_GROUPS = {
    "sprite_sheet": ("sprite_sheet.atlas.amf3.deflate", "pixelart.frame.amf3.deflate",
                     "pixelart.timeline.amf3.deflate"),
    "special_sprite_sheet": ("special_sprite_sheet.atlas.amf3.deflate", "special.frame.amf3.deflate",
                             "special.timeline.amf3.deflate"),
}


def _review_md_verdict(text: str) -> str | None:
    """REVIEW.md「修复轮复核」段里 ``#### primula …`` 标题的判定（PASS/FAIL…）；段或标题缺失返回 None。"""
    head = text.find("修复轮复核")
    if head < 0:
        return None
    for line in text[head:].splitlines():
        if line.startswith("#### ") and "primula" in line:
            return "PASS" if "PASS" in line and "FAIL" not in line else "FAIL"
    return None


def pixel_inputs(root: Path) -> tuple[dict[str, Path], list[str]]:
    """像素染色产物能否装包：report 门禁全过；verify_all primula ``pass`` 且 hard/declared 全过；
    REVIEW.md 修复轮复核判 PASS；``out/<sheet>.png`` 为真 PNG 且 sha = report outputs = 复核 H8 sha。

    返回 ``({sheet 基名: PNG 路径}, problems)``；problems 非空 = pending（不装包）。"""
    import wf_assets
    probs: list[str] = []
    base = root / PIXEL_DIR
    report_path, review_path, md_path = base / "report.json", root / PIXEL_REVIEW_JSON, root / PIXEL_REVIEW_MD
    if not report_path.is_file():
        return {}, [f"pixel report absent: {PIXEL_DIR}/report.json"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("key") != "primula" or report.get("gates_passed") is not True:
        probs.append(f"pixel report key={report.get('key')} gates_passed={report.get('gates_passed')}")
    failed = sorted(k for k, v in (report.get("gates") or {}).items() if not (isinstance(v, dict) and v.get("ok")))
    if failed or not report.get("gates"):
        probs.append(f"pixel report gates failed/absent: {failed}")
    review = json.loads(review_path.read_text(encoding="utf-8")).get("primula") if review_path.is_file() else None
    if not review:
        probs.append(f"pixel review verdict absent: {PIXEL_REVIEW_JSON}")
    else:
        hard_bad = sorted(k for k, v in (review.get("hard") or {}).items() if not v.get("ok"))
        decl_bad = sorted(k for k, v in (review.get("declared") or {}).items() if not v.get("ok"))
        if review.get("pass") is not True or hard_bad or decl_bad or not review.get("hard"):
            probs.append(f"pixel review failed: pass={review.get('pass')} hard={hard_bad} declared={decl_bad}")
    verdict = _review_md_verdict(md_path.read_text(encoding="utf-8")) if md_path.is_file() else None
    if verdict != "PASS":
        probs.append(f"REVIEW.md 修复轮复核 primula verdict={verdict}")
    reviewed = ((((review or {}).get("hard") or {}).get("H8_png_roundtrip") or {}).get("detail") or {})
    out: dict[str, Path] = {}
    for name in PIXEL_GROUPS:
        png = base / "out" / f"{name}.png"
        if not png.is_file():
            probs.append(f"pixel output missing: out/{name}.png")
            continue
        raw = png.read_bytes()
        if raw[:8] != wf_assets.PNG_REAL:
            probs.append(f"out/{name}.png is not a real PNG (magic {raw[:8].hex()})")
        digest = hashlib.sha256(raw).hexdigest()
        if ((report.get("outputs") or {}).get(name) or {}).get("sha256") != digest:
            probs.append(f"out/{name}.png sha256 != pixel report outputs")
        if (reviewed.get(name) or {}).get("sha256") != digest:
            probs.append(f"out/{name}.png sha256 != reviewed verify_all H8 sha")
        out[name] = png
    return out, probs


def pixel_problems(pack, root: Path, sheet_bytes: dict[str, bytes] | None = None) -> list[str]:
    """包内像素小人核对（只读）：sheet = 染色 PNG 的存储态原字节；尺寸/alpha = 母本 sheet；
    atlas/frame/timeline = 母本树（仅 ``character/<母本>/``→``character/<code>/``）；owner=pixel。"""
    import wf_assets
    import wf_seasonal7_common as C
    spec = pack.spec
    pngs, probs = pixel_inputs(root)
    if probs:
        return [f"pixel inputs not ready: {p}" for p in probs]
    prefix = C.dir_prefix_map(spec.template_code, spec.code)
    for name, metas in PIXEL_GROUPS.items():
        logical = f"character/{CODE}/pixelart/{name}.png"
        if sheet_bytes is not None and logical in sheet_bytes:
            raw = sheet_bytes[logical]
        elif pack.pkg_has("common", logical):
            raw = pack.pkg_path("common", logical).read_bytes()
        else:
            probs.append(f"package pixel sheet missing {logical}")
            continue
        if raw != wf_assets.png_encode(pngs[name].read_bytes()):
            probs.append(f"{logical} != store form of {PIXEL_DIR}/out/{name}.png")
        _r, donor_raw, _s = pack.template_asset(f"character/{spec.template_code}/pixelart/{name}.png")
        img, donor = C.png_open(raw), C.png_open(donor_raw)
        if img.size != donor.size:
            probs.append(f"{logical} size {img.size} != template {donor.size}")
        elif img.getchannel("A").tobytes() != donor.getchannel("A").tobytes():
            probs.append(f"{logical} alpha differs from template sheet")
        elif img.tobytes() == donor.tobytes():
            probs.append(f"{logical} still template colours")
        if sheet_bytes is None and pack.owner_of("common", logical) != "pixel":
            probs.append(f"{logical} owner={pack.owner_of('common', logical)} (expected pixel)")
        for meta in metas:
            pkg_meta = f"character/{CODE}/pixelart/{meta}"
            if not pack.pkg_has("common", pkg_meta):
                probs.append(f"package pixel metadata missing {pkg_meta}")
                continue
            _r, tpl_raw, _s = pack.template_asset(f"character/{spec.template_code}/pixelart/{meta}")
            want = C.replace_strings(C.amf_parse(tpl_raw), prefix)
            got = C.amf_parse(pack.pkg_path("common", pkg_meta).read_bytes())
            if got != want:
                probs.append(f"{pkg_meta} differs from template metadata (only character/ prefix may change)")
            if f"character/{spec.template_code}/" in repr(got):
                probs.append(f"{pkg_meta} still references character/{spec.template_code}/")
    return probs


def install_pixel(ctx) -> dict[str, Any]:
    """复核通过的像素 sheet 以存储态（小写魔数，PNG 字节不重编码）写入包，owner=pixel。

    幂等：字节相同 ``write_pkg`` 不改盘；产物未就绪时不写、返回 pending。写后 ``pixel_problems`` 非空即报错。"""
    import wf_assets
    pngs, probs = pixel_inputs(ctx.root)
    if probs:
        return {"status": "pending", "problems": probs, "sheets": {}}
    sheets = {}
    for name, png in pngs.items():
        logical = f"character/{CODE}/pixelart/{name}.png"
        raw = png.read_bytes()
        data = wf_assets.png_encode(raw)
        ctx.write_asset("common", logical, data, owner="pixel")
        sheets[logical] = {"source": f"{PIXEL_DIR}/out/{name}.png", "source_sha256": hashlib.sha256(raw).hexdigest(),
                           "store_sha256": hashlib.sha256(data).hexdigest()}
    after = pixel_problems(ctx.pack, ctx.root)
    if after:
        raise KitError(f"pixel sheets did not land in the package: {after}")
    return {"status": "installed", "problems": [], "sheets": sheets}


# ---------------------------------------------------------------- 图标

def draw_icon(frame) -> Any:
    """48×48：沿用官方固有图标外框 alpha 与白边，内底夜空渐变，白色百合 + 金团扇 + 金新月。

    改版 R6（revision-20260916）：底色比上一版更暗（#1E1442 → #5A3A96）以托住白百合；百合左上加一弯
    金色新月（压在花瓣下层）点出「夜」；花瓣外缘加 1px 淡藤描边，避免纯白在浅色格子里糊成一团。
    不画数字——右下层数、右上永续由客户端绘制。
    """
    from PIL import Image, ImageDraw
    if frame.size != (48, 48):
        raise KitError(f"icon frame donor must be 48x48, got {frame.size}")
    K = 8
    N = 48 * K
    layer = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    top, bot = (30, 20, 66), (90, 58, 150)
    grad = Image.new("RGBA", (1, N))
    for y in range(N):
        t = y / (N - 1)
        grad.putpixel((0, y), tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    grad = grad.resize((N, N))
    inner = Image.new("L", (N, N), 0)
    ImageDraw.Draw(inner).rounded_rectangle((3 * K, 3 * K, 45 * K - 1, 45 * K - 1), radius=5 * K, fill=255)
    layer.paste(grad, (0, 0), inner)
    d = ImageDraw.Draw(layer)
    gold, gold_dk = (236, 192, 90, 255), (170, 118, 38, 255)
    # 新月（画在百合之下：先画，后面的花瓣会压住右下缘）
    mcx, mcy, mr = 11.0 * K, 12.5 * K, 5.2 * K
    moon = Image.new("L", (N, N), 0)
    md = ImageDraw.Draw(moon)
    md.ellipse((mcx - mr, mcy - mr, mcx + mr, mcy + mr), fill=255)
    md.ellipse((mcx - mr + 2.8 * K, mcy - mr - 1.1 * K, mcx + mr + 2.8 * K, mcy + mr - 1.1 * K), fill=0)
    layer.paste(Image.new("RGBA", (N, N), gold), (0, 0), moon)
    fcx, fcy, fr = 32.0 * K, 21.5 * K, 10.0 * K
    hx, hy = fcx - 2.5 * K, fcy + fr - 1.5 * K
    d.line((hx, hy, fcx - 6.0 * K, fcy + fr + 9.5 * K), fill=gold_dk, width=int(2.4 * K))
    d.ellipse((fcx - fr, fcy - fr, fcx + fr, fcy + fr), fill=gold)
    for a in range(-160, -10, 30):
        ang = math.radians(a)
        d.line((hx, hy, fcx + fr * 0.9 * math.cos(ang), fcy + fr * 0.9 * math.sin(ang)),
               fill=gold_dk, width=int(1.1 * K))
    d.ellipse((fcx - fr, fcy - fr, fcx + fr, fcy + fr), outline=gold_dk, width=int(1.2 * K))
    lcx, lcy = 18.0 * K, 27.0 * K
    white, vein = (255, 255, 255, 255), (196, 168, 242, 255)
    for i in range(6):
        ang = math.radians(-90 + i * 60 + 10)
        length, width = 16.0 * K, 5.2 * K
        pts = [(s / 40 * length, width * math.sin(math.pi * s / 40) ** 0.8 * (1 - 0.35 * s / 40))
               for s in range(41)]
        poly = pts + [(x, -y) for x, y in reversed(pts)]
        ca, sa = math.cos(ang), math.sin(ang)
        d.polygon([(lcx + x * ca - y * sa, lcy + x * sa + y * ca) for x, y in poly],
                  fill=white, outline=vein, width=int(1.0 * K))
    for i in range(6):
        ang = math.radians(-90 + i * 60 + 10)
        d.line((lcx + 3.5 * K * math.cos(ang), lcy + 3.5 * K * math.sin(ang),
                lcx + 11.0 * K * math.cos(ang), lcy + 11.0 * K * math.sin(ang)), fill=vein, width=int(1.4 * K))
    for i in range(3):
        ang = math.radians(-50 + i * 50)
        sx, sy = lcx + 4.6 * K * math.cos(ang), lcy + 4.6 * K * math.sin(ang)
        d.line((lcx, lcy, sx, sy), fill=gold_dk, width=int(0.9 * K))
        d.ellipse((sx - 1.5 * K, sy - 1.5 * K, sx + 1.5 * K, sy + 1.5 * K), fill=gold)
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


# ---------------------------------------------------------------- 特效 sheet 钩子（Effects 阶段）

def fx_sheet_overrides(root: Path) -> dict[str, Path]:
    """``fx/primula/out/manifest.json`` → {源（或目标）sheet 逻辑路径: 染色 PNG 文件}。

    接受 ``{logical: file}``、``{"sheets": {...}}``、``[{"source"/"logical": …, "png"/"file"/"path": …}]``；
    文件路径可为绝对、相对 manifest 目录或相对仓库根。不存在返回 {}。
    """
    path = root / FX_MANIFEST
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("sheets"), (dict, list)):
        data = data["sheets"]
    pairs: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                v = v.get("png") or v.get("file") or v.get("path")
            if isinstance(k, str) and k.endswith(".png") and isinstance(v, str):
                pairs.append((k, v))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                k = item.get("source") or item.get("logical") or item.get("src")
                v = item.get("png") or item.get("file") or item.get("path")
                if isinstance(k, str) and k.endswith(".png") and isinstance(v, str):
                    pairs.append((k, v))
    out: dict[str, Path] = {}
    for logical, file in pairs:
        cand = [Path(file), path.parent / file, root / file]
        hit = next((c for c in cand if c.is_absolute() and c.is_file()), None) \
            or next((c for c in cand[1:] if c.is_file()), None)
        if hit is None:
            raise KitError(f"fx manifest sheet file missing: {logical} -> {file}")
        out[logical] = hit
    return out


def fx_store_bytes(file: Path) -> bytes:
    """染色 PNG 的存储态原字节：真 PNG → 小写魔数（不经 PIL 重编码）；已是存储态原样返回。"""
    import wf_assets
    raw = file.read_bytes()
    if raw[:8] == wf_assets.PNG_FAKE:
        return raw
    if raw[:8] != wf_assets.PNG_REAL:
        raise KitError(f"fx override is not a PNG: {file} (magic {raw[:8].hex()})")
    return wf_assets.png_encode(raw)


def family_sheets() -> dict[str, str]:
    """{母本 sheet 逻辑路径: 包内克隆 sheet 逻辑路径}（sibling 形态）。"""
    out = {}
    for fam in EFFECT_FAMILIES:
        donor = fam["src_dir"].rsplit("/", 1)[-1]
        dst_dir = f"battle/effect/skill_unique/{CODE}_{fam['dst_subdir']}"
        out[f"{fam['src_dir']}/{donor}.png"] = f"{dst_dir}/{dst_dir.rsplit('/', 1)[-1]}.png"
    return out


def fx_sheet_problems(pack, root: Path, sheet_bytes: dict[str, bytes] | None = None) -> list[str]:
    """fx manifest 存在时：每张克隆 sheet 字节 = 对应染色 PNG 存储态；尺寸/alpha = 母本 sheet；owner=effects。
    manifest 不存在返回 ``[]``（克隆 sheet 保持官方原色是合法草稿态）；manifest 未覆盖某张 sheet 记问题。"""
    import wf_seasonal7_common as C
    overrides = fx_sheet_overrides(root)
    if not overrides:
        return []
    probs = []
    for src, dst in family_sheets().items():
        file = overrides.get(src) or overrides.get(dst)
        if file is None:
            probs.append(f"fx manifest does not cover {src}")
            continue
        if sheet_bytes is not None and dst in sheet_bytes:
            raw = sheet_bytes[dst]
        elif pack.pkg_has("common", dst):
            raw = pack.pkg_path("common", dst).read_bytes()
        else:
            probs.append(f"package effect sheet missing {dst}")
            continue
        if raw != fx_store_bytes(file):
            same_px = C.png_open(raw).tobytes() == C.png_open(fx_store_bytes(file)).tobytes()
            probs.append(f"{dst} bytes != store form of {file.name}" + (" (pixels equal: re-encoded)" if same_px else ""))
        _r, donor_raw, _s = pack.template_asset(src)
        img, donor = C.png_open(raw), C.png_open(donor_raw)
        if img.size != donor.size or img.getchannel("A").tobytes() != donor.getchannel("A").tobytes():
            probs.append(f"{dst} size/alpha differs from donor {src}")
        if sheet_bytes is None and pack.owner_of("common", dst) != "effects":
            probs.append(f"{dst} owner={pack.owner_of('common', dst)} (expected effects)")
    return probs


def _override_transform(file: Path, label: str):
    from PIL import Image
    import wf_assets

    def transform(img):
        raw = file.read_bytes()
        new = Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA")
        if new.size != img.size:
            raise KitError(f"fx override {label} size {new.size} != source sheet {img.size} (atlas rects)")
        src_clear = img.getchannel("A").histogram()[0]
        new_clear = new.getchannel("A").histogram()[0]
        if src_clear and new_clear * 2 < src_clear:
            raise KitError(f"fx override {label} lost transparency: alpha==0 pixels {new_clear} vs source {src_clear}")
        return new
    return transform


# ---------------------------------------------------------------- 摘要（kit 产物是否变化）

def kit_digest(pack) -> str:
    import wf_mod_tool as core
    import wf_seasonal7_common as C
    parts: dict[str, Any] = {}

    def flat(logical, keys):
        if not pack.pkg_has("common", logical):
            return None
        rows = pack.pkg_flat(logical)
        return {k: rows.get(k) for k in keys}

    parts["ability"] = flat(ABILITY, [f"{CID}{i}" for i in range(1, 7)])
    parts["leader"] = flat(LEADER, [CID])
    parts["unique"] = flat(UNIQUE, [UID])
    parts["text"] = flat(TEXT, [CID])
    parts["custom_ability_string"] = flat(CAS, [CAS_KEY])       # 629 文案改了要触发摘要变化
    char = flat(CHAR, [CID])
    parts["route"] = C.csv_split(char[CID])[0][9:17] if char and char.get(CID) else None
    for logical, outer in ((ACTION, CODE), (SWITCHED, VOICE_READY)):
        if pack.pkg_has("common", logical):
            nested = core.load_nested_table_bytes(pack.pkg_path("common", logical).read_bytes(), logical)
            parts[logical] = nested.rows[outer].text_rows() if outer in nested.rows else None
    owned = {}
    for key, rec in sorted(pack._owned_raw().items()):
        if rec.get("owner") in ("kit", "effects"):
            root, logical = key.split(":", 1)
            if rec.get("owner") == "effects" and logical.endswith(".png"):
                continue        # 染色 sheet 只换像素（尺寸/透明度由钩子断言），不影响结构门禁
            path = pack.pkg_path(root, logical)
            owned[key] = C.sha256(path.read_bytes()) if path.is_file() else None
    parts["files"] = owned
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 行门禁

def row_gates(kind: str, rows: list[list[str]]) -> dict[str, Any]:
    import wf_client_legality as LG
    import wf_describe
    lines = []
    caps: list[str] = []
    ok = True
    descs = wf_describe.describe_rows(rows, kind)
    for row, desc in zip(rows, descs):
        probs = LG.client_legality_problems(kind, row) + LG.declared_block_field_problems(kind, row)
        elem = LG.ability_element_column_problems(kind, row, ELEMENT) if kind == "ability" else []
        need = LG.required_client_capabilities(kind, row)
        # 629 行的 c70 文案键必须在 custom_ability_string 里（kit 自己写的 CAS_KEY 算已存在）
        inv = LG.invoke_skill_string_problems(row, frozenset({CAS_KEY}), kind)
        ok &= not probs and not elem and not inv
        caps += [c for c in need if c not in caps]
        lines.append({"describe": desc, "legality": probs, "element": elem, "invoke_skill_string": inv,
                      "required_capabilities": need, "ncols": len(row), "c0": row[0]})
    return {"ok": ok, "rows": lines, "required_capabilities": caps}


# ---------------------------------------------------------------- build

def build(ctx) -> dict[str, Any]:
    import wf_seasonal7_common as C
    import wf_mod_tool as core
    spec = ctx.spec
    pack = ctx.pack
    if (spec.cid_s, spec.code) != (CID, CODE):
        raise KitError(f"kit bound to {CID}/{CODE}, spec is {spec.cid_s}/{spec.code}")
    root = ctx.root
    design = _load_json(root, DESIGN_JSON)
    notes: list[str] = []
    problems: list[str] = []

    # ---- 行
    leader_rows = build_leader_rows(pack)
    ability_rows = build_ability_rows(pack)
    unique_row = build_unique_row(pack)
    action_rows = build_action_rows(pack)
    trow = text_row()
    if design is not None:
        want_leader = [r["row"] for r in design["leader"]]
        if leader_rows != want_leader:
            problems.append("leader rows differ from design")
        for slot in range(1, 7):
            key = f"{CID}{slot}"
            want = design_rows_expected(key, [r["row"] for r in design["abilities"][f"slot{slot}"]])
            if ability_rows[key] != want:
                problems.append(f"ability slot{slot} rows differ from design(+rev2/rev3 delta)")
        if unique_row != design["unique_conditions"][0]["row"]:
            problems.append("unique_condition row differs from design")
        if trow != design["text"]["character_text_row"]:
            problems.append("character_text row differs from design")
        for level, edits in (("1", design["skills"]["action_skill_edits"]["inner1"]),
                             ("2", design["skills"]["action_skill_edits"]["inner2"])):
            for col, val in edits.items():
                if action_rows[level][int(col)] != val:
                    problems.append(f"action_skill {level} c{col} differs from design")
        if design["identity"]["character_row_edits"] and \
                [design["identity"]["character_row_edits"][str(c)] for c in range(9, 17)] != ROUTE_COLS:
            problems.append("voice route differs from design")
        want_cas = {c["key"]: c["text"] for c in design.get("custom_strings") or []}
        # 改版 2 唯一允许的 CAS 差异 = 插入的上限句；其余一个字都不能变
        if want_cas != {CAS_KEY: rev2_design_cas()}:
            problems.append("custom_ability_string differs from design beyond the rev2 cap clause")
    else:
        notes.append("design JSON absent: rows not cross-checked against design")

    leader_gate = row_gates("leader_ability", leader_rows)
    ability_gate = row_gates("ability", [r for key in sorted(ability_rows) for r in ability_rows[key]])
    if not leader_gate["ok"] or not ability_gate["ok"]:
        problems.append("row legality problems (see kit-gates evidence)")

    ctx.write_flat(LEADER, {CID: leader_rows})
    ctx.write_flat(ABILITY, ability_rows)
    ctx.write_flat(UNIQUE, {UID: [unique_row]})
    ctx.write_flat(TEXT, {CID: [trow]})
    # 629 行 c70 引用的文案键：必须先写进 custom_ability_string，否则详情页 C8601
    ctx.write_flat(CAS, {CAS_KEY: [[CAS_TEXT]]})
    if ctx.pkg_flat(CAS).get(CAS_KEY) != CAS_TEXT:
        raise KitError("custom_ability_string roundtrip failed for " + CAS_KEY)
    crow = list(pack.pkg_character_row())
    if crow[9] not in ("(None)",) and crow[9:17] != ROUTE_COLS:
        raise KitError(f"character c9-c16 holds an unrelated skill switch: {crow[9:17]}")
    crow[9:17] = ROUTE_COLS
    ctx.write_flat(CHAR, {CID: [crow]})

    # ---- 图标
    frame_loc = pack.live_locate(ICON_FRAME_DONOR)
    frame_raw = pack.official_read(ICON_FRAME_DONOR) or (frame_loc[1].read_bytes() if frame_loc else None)
    if frame_raw is None:
        raise KitError(f"icon frame donor missing: {ICON_FRAME_DONOR}")
    icon = draw_icon(C.png_open(frame_raw))
    icon_bytes = C.png_store_bytes(icon)
    ctx.write_asset("common", ICON_LOGICAL, icon_bytes)

    # ---- 特效族
    overrides = fx_sheet_overrides(root)
    families = []
    fx_applied = {}
    for fam in EFFECT_FAMILIES:
        donor = fam["src_dir"].rsplit("/", 1)[-1]
        src_sheet = f"{fam['src_dir']}/{donor}.png"
        dst_dir = f"battle/effect/skill_unique/{CODE}_{fam['dst_subdir']}"
        dst_sheet = f"{dst_dir}/{dst_dir.rsplit('/', 1)[-1]}.png"
        file = overrides.get(src_sheet) or overrides.get(dst_sheet)
        transform = _override_transform(file, src_sheet) if file is not None else None
        if file is not None:
            fx_applied[src_sheet] = {"file": str(file), "sha256": C.sha256(file.read_bytes())}
        result = ctx.clone_effect_family(fam["src_dir"], fam["dst_subdir"], fam["fx_names"],
                                         layout=fam["layout"], png_transform=transform)
        if result["missing_effects"]:
            raise KitError(f"effect family {donor} missing effects {result['missing_effects']}")
        if sorted(result["copied_bases"]) != sorted(fam["fx_names"]):
            raise KitError(f"effect family {donor} copied {result['copied_bases']} != {fam['fx_names']}")
        if file is not None:
            # 框架 clone 经 png_store_bytes 以 PIL 重编码写 sheet（逐像素等于染色 PNG，但字节不同）；
            # 这里改写为染色 PNG 的存储态原字节，使包内 sha = 复核过的产物存储态 sha。
            sheet_root = next(f["root"] for f in result["files"] if f["target"] == dst_sheet)
            exact = fx_store_bytes(file)
            if C.png_open(exact).tobytes() != C.png_open(pack.pkg_path(sheet_root, dst_sheet).read_bytes()).tobytes():
                raise KitError(f"fx store bytes decode differently from png_transform output: {dst_sheet}")
            ctx.write_asset(sheet_root, dst_sheet, exact, owner="effects")
            fx_applied[src_sheet].update({"target": dst_sheet, "root": sheet_root, "store_sha256": C.sha256(exact)})
        families.append(result)
    if not overrides:
        notes.append("fx/primula/out/manifest.json 不存在：特效 sheet 仍为官方原色（Effects 阶段染色后重跑 kit）")
    else:
        unused = sorted(set(overrides) - set(fx_applied) - set(family_sheets().values()))
        if unused:
            notes.append(f"fx manifest entries not matching any cloned sheet: {unused}")
    fx_problems_sheets = fx_sheet_problems(pack, root)
    if fx_problems_sheets:
        problems.append(f"effect sheet problems: {fx_problems_sheets}")

    # ---- 像素小人（复核通过的染色 sheet，owner=pixel；未就绪时不写，报 pending）
    pixel = install_pixel(ctx)
    ctx.evidence_write("pixel-report.json", {
        "summary": ("像素小人染色 sheet 2 张已按存储态装包（owner=pixel，atlas/frame/timeline 保持母本）"
                    if pixel["status"] == "installed" else "像素小人仍为母本原色（染色产物未就绪）"),
        "status": pixel["status"], "mode": "recolor-lut (seasonal7 pixel/primula)", **pixel})

    # ---- 技能树
    sig = _load_json(root, OFFICIAL_SIG)
    programs, tree_reports = [], {}
    for level in ("1", "2"):
        tree, log = compose_tree(pack, level)
        refs_total = {}
        for fam in families:
            tree, refs = ctx.rewrite_effect_refs(tree, fam, strict=True)
            refs_total[fam["dst_dir"]] = refs
        checks = tree_checks(tree, sig)
        want = _load_json(root, DESIGN_TREES[level])
        checks["equals_design_prototype"] = None if want is None else want == tree
        checks["equals_design_prototype_typed"] = None if want is None else _typed(want) == _typed(tree)
        if want is not None and want != tree:
            problems.append(f"skill tree {level} differs from design prototype")
        if not checks["ok"]:
            problems.append(f"skill tree {level} static checks failed")
        logical = ctx.write_dsl(ctx.program_path(level), tree)
        programs.append(logical)
        tree_reports[level] = {"logical": logical, "edits": len(log), "effect_refs": refs_total,
                               "checks": checks, "edit_log": log}

    # ---- 能力1#3（629）调用的 ability_skill DSL（无特效引用，不走 rewrite_effect_refs）
    as_tree, as_log = compose_ability_skill_tree(pack)
    as_checks = tree_checks(as_tree, sig)
    as_want = _load_json(root, DESIGN_AS_TREE)
    as_checks["equals_design_prototype"] = None if as_want is None else as_want == as_tree
    as_checks["equals_design_prototype_typed"] = None if as_want is None else _typed(as_want) == _typed(as_tree)
    if as_want is not None and as_want != as_tree:
        problems.append("ability_skill tree differs from design prototype")
    if not as_checks["ok"]:
        problems.append("ability_skill tree static checks failed")
    # R1「移动」忠实度：成品树的三块参数 vs 归档/live 迁移源（审查第 1/3 条）
    as_checks["migration_source"] = {"archive": MIGRATION_ARCHIVE, "level": MIGRATION_LEVEL,
                                     "diff_whitelist": {f"{a}[{i}]": {"new": nv, "why": why}
                                                        for (a, i), (nv, why) in MIGRATION_DIFF.items()},
                                     "problems": migration_problems(as_tree)}
    if as_checks["migration_source"]["problems"]:
        problems.append(f"ability_skill drifted from the migrated live block: "
                        f"{as_checks['migration_source']['problems'][:4]}")
    as_logical = ctx.write_dsl(AS_PROGRAM, as_tree)
    programs.append(as_logical)
    tree_reports["ability_skill"] = {"logical": as_logical, "edits": len(as_log), "effect_refs": {},
                                     "checks": as_checks, "edit_log": as_log}

    # ---- action_skill / switched_action_skill
    ctx.write_nested(ACTION, CODE, {lv: [row] for lv, row in action_rows.items()}, replace_inner=True)
    switched = {lv: [row[7:24]] for lv, row in action_rows.items()}
    if any(len(r[0]) != 17 for r in switched.values()):
        raise KitError("switched_action_skill rows must be 17 cells (action_skill c7..c23)")
    ctx.write_nested(SWITCHED, VOICE_READY, switched, replace_inner=True)

    # ---- 未使用的框架克隆键（custom_ability_string）；kit 自己写的 CAS_KEY 被 629 行 c70 引用，永不撤销
    unclaimed = []
    claims = pack.load_claims()
    cas_claim = next((c for c in claims if (c["root"], c["logical_path"]) == ("common", CAS)), None)
    if cas_claim:
        referenced = {cell for rows in ability_rows.values() for r in rows for cell in r} \
            | {cell for r in leader_rows for cell in r} | {CAS_KEY}
        stale = [k for k in cas_claim["outer_keys"] if k not in referenced]
        if stale:
            unclaimed.append(ctx.unclaim(CAS, stale))
    pkg_cas = ctx.pkg_flat(CAS) if pack.pkg_has("common", CAS) else {}
    if pkg_cas.get(CAS_KEY) != CAS_TEXT:
        raise KitError(f"custom_ability_string lost {CAS_KEY} after unclaim pass")

    mirrors = ctx.sync_character_mirrors()
    if mirrors["character"][9:17] != ROUTE_COLS:
        raise KitError("character mirror lost voice route")

    # ---- 引用可解析（包内或 live）
    ref_problems = []
    for level, rep in tree_reports.items():
        for p in rep["checks"]["effect_paths"]:
            for ext in (".parts.amf3.deflate", ".timeline.amf3.deflate"):
                lg = p + ext
                if not any(pack.pkg_has(r, lg) for r in C.CLIENT_ROOTS) and pack.live_locate(lg) is None:
                    ref_problems.append(lg)
    for level, row in action_rows.items():
        if not pack.pkg_has("common", C.wf_dsl.dsl_logical(row[7])):
            ref_problems.append(f"action_skill {level} program not in package: {row[7]}")
    if not pack.pkg_has("common", ICON_LOGICAL):
        ref_problems.append(ICON_LOGICAL)
    # 629 行 c70 文案键 / c71 动作路径：键缺＝详情页 C8601，DSL 缺＝进战斗「数据不足」
    invoke_rows = [r for rows in ability_rows.values() for r in rows if r[47] == "629"]
    if len(invoke_rows) != 1:
        problems.append(f"expected exactly one InvokeSkill(629) ability row, found {len(invoke_rows)}")
    # 改版 2 审查第 1 条：629 行必须主位绑定（共鸣是编成条件，挡不住副位装配）
    unison_lock = unison_lock_problems(ability_rows)
    if unison_lock:
        problems.append(f"InvokeSkill unison lock: {unison_lock}")
    # 改版 3：每层夜百合的受益面 = 暗属性角色全体 + 协力球（协力球读不到的 kind 不准挂协力球目标）
    lily_target = lily_layer_target_problems(ability_rows)
    if lily_target:
        problems.append(f"lily layer targets: {lily_target}")
    cas_style = cas_text_problems(pkg_cas.get(CAS_KEY) or CAS_TEXT)
    if cas_style:
        problems.append(f"custom_ability_string style: {cas_style}")
    # 面板文案两条规则（rev2）：成品文案取包内值，缺键时回退 kit 常量
    text_style = panel_text_problems(dict(PANEL_TEXTS, CAS_TEXT=pkg_cas.get(CAS_KEY) or CAS_TEXT))
    if text_style:
        problems.append(f"panel text rules: {text_style}")
    for r in invoke_rows:
        if r[70] != CAS_KEY or pkg_cas.get(CAS_KEY) != CAS_TEXT:
            ref_problems.append(f"InvokeSkill string key {r[70]!r} not written to {CAS}")
        if r[71] != AS_PROGRAM:
            ref_problems.append(f"InvokeSkill action path {r[71]!r} != {AS_PROGRAM}")
        if not pack.pkg_has("common", C.wf_dsl.dsl_logical(r[71])):
            ref_problems.append(f"ability_skill program not in package: {r[71]}")
    if ref_problems:
        problems.append(f"unresolved references: {ref_problems[:10]}")
    # 克隆特效 timeline 内嵌 SE（预载引用）
    fx_sounds, fx_problems = effect_timeline_gate(pack, {f["dst_dir"]: f for f in families})
    if fx_problems:
        problems.append(f"effect timeline problems: {fx_problems[:10]}")

    # 集成待办（kit 范围外，只进 kit-gates/gates 证据与步骤输出；不写 kit-report notes，
    # 否则 Integrate 装完后 manifest snapshot 会带着过期提示被封存）
    integration = package_integration_pending(pack)

    caps = sorted(set(leader_gate["required_capabilities"]) | set(ability_gate["required_capabilities"]))
    static_ok = not problems
    digest = kit_digest(pack)
    gates = _load_json(root, GATES_FILE)
    gates_ok = bool(isinstance(gates, dict) and gates.get("all_pass") and gates.get("kit_digest") == digest)
    status = "ready-for-review" if static_ok and gates_ok else "draft"
    if static_ok and not gates_ok:
        notes.append("静态门禁通过；等待离线门禁（python mod-tools/wf_seasonal7_kit_primula.py gates）")

    kit_gates = {"leader": leader_gate, "ability": ability_gate, "trees": tree_reports,
                 "unresolved_references": ref_problems, "problems": problems, "static_ok": static_ok,
                 "kit_digest": digest, "fx_sheet_overrides": fx_applied, "unclaimed": unclaimed,
                 "effect_timeline_sounds": fx_sounds, "effect_timeline_problems": fx_problems,
                 "effect_sheet_problems": fx_problems_sheets, "pixel": pixel,
                 "integration_pending": integration}
    ctx.evidence_write("kit-gates.json", kit_gates)
    panel = [f"队长{i + 1}：{r['describe']}" for i, r in enumerate(leader_gate["rows"])]
    idx = 0
    for slot in range(1, 7):
        for n in range(len(ability_rows[f"{CID}{slot}"])):
            panel.append(f"能力{slot}#{n + 1}：{ability_gate['rows'][idx]['describe']}")
            idx += 1
    ctx.report({
        "summary": ("普莉姆拉·浴衣 kit（改版 20260916）：官方 donor 行 6+13、夜百合固有 16999201（上限 20）、"
                    "两棵技能树 + 能力1#3 的 ability_skill DSL、两个 sibling 特效族、贯通语音路由"),
        "status": status,
        "skills": {"programs": programs},
        "unique_condition": {UID: {"icon": ICON_LOGICAL, "name": UNIQUE_NAME,
                                   "max_accumulation": int(UNIQUE_MAX)}},
        "required_capabilities": caps,
        "panel": panel,
        "notes": notes + [f"problem: {p}" for p in problems],
        "kit_digest": digest,
    })
    return {"status": status, "static_ok": static_ok, "problems": problems, "programs": programs,
            "required_capabilities": caps, "kit_digest": digest, "fx_overrides": sorted(fx_applied),
            "effect_dirs": [f["dst_dir"] for f in families], "unclaimed": unclaimed,
            "effect_timeline_problems": fx_problems, "effect_sheet_problems": fx_problems_sheets,
            "pixel": pixel["status"], "pixel_problems": pixel["problems"],
            "integration_clear": integration["clear"]}


# ---------------------------------------------------------------- 离线门禁（manifest/status/inspect 之后）

def split_preflight_conflicts(conflicts: list[dict], claims: list[dict]) -> tuple[list[dict], list[dict]]:
    """把 flow preflight 的 ``conflicts`` 分成「落在本包认领的键上」和「跨角色共享表漂移」。

    conflict 的 ``claim`` 形如 ``<logical_path>:<outer>`` 或 ``<logical_path>:<outer>/<inner>``。
    本包认领的键出现冲突＝真问题（必须判红）；别的角色已发布、本包全表载荷还是旧的＝串行发布的预期漂移，
    由主控在发布前 ``flow rebase`` 收口（记忆卡 wf-flow-serial-publish-order），门禁只记 info。
    """
    owned: dict[str, set[str]] = {}
    for c in claims:
        owned.setdefault(c["logical_path"], set()).update(c["outer_keys"])
    own, foreign = [], []
    for conflict in conflicts:
        path, _, key = str(conflict.get("claim", "")).partition(":")
        (own if key.split("/")[0] in owned.get(path, ()) else foreign).append(conflict)
    return own, foreign


def publish_blockers_for(foreign: list[dict]) -> list[str]:
    """kit 范围之外、但必须挡在「可发布」前面的前置（审查第 4 条）。

    跨角色共享表漂移不算本角色的缺陷，但共享表是**整文件投递**：包内那些键**在、内容是旧的**
    （逐字节比对实证 removed=[]，不是缺键），直接发就把别人已发布的新内容回滚掉。
    所以它不能只记 info 和 ``all_pass=true`` 同屏 —— 单列成 blocker，
    并把 ``release_ready_after_integration`` 压成 false。
    """
    if not foreign:
        return []
    paths = sorted({str(c.get("claim", "")).partition(":")[0] for c in foreign})
    return [f"需要 flow rebase：包内共享表持有 {len(foreign)} 处别人角色的**陈旧**行"
            f"（键在、内容是旧的；整文件投递会把他们已发布的新内容回滚掉）；"
            f"涉及 {len(paths)} 张表 {paths[:6]}；按记忆卡 wf-flow-serial-publish-order 走"
            f" preflight 封存 → flow rebase → preflight → publish，禁止用 force 绕过 can_prepare=false"]


def run_gates(write_status: bool = True) -> dict[str, Any]:
    import wf_client_legality as LG
    import wf_describe
    import wf_dsl
    import wf_mod_tool as core
    import wf_seasonal7_common as C
    import wf_seasonal7_specs as S
    import wf_seasonal7_voice as V
    spec = S.get_spec("primula")
    pack = C.S7Pack(spec)
    root = pack.root
    gates: dict[str, Any] = {"character": "primula", "cid": CID, "code": CODE}
    failures: list[str] = []

    # 包内全部本角色 ability/leader 行（从包字节读）
    abil = pack.pkg_flat(ABILITY)
    lead = pack.pkg_flat(LEADER)
    ability_rows = [r for i in range(1, 7) for r in C.csv_split(abil[f"{CID}{i}"])]
    leader_rows = C.csv_split(lead[CID])
    ag, lg_ = row_gates("ability", ability_rows), row_gates("leader_ability", leader_rows)
    gates["rows"] = {"ability": ag, "leader_ability": lg_,
                     "counts": {"leader": len(leader_rows), "ability": len(ability_rows)}}
    if not (ag["ok"] and lg_["ok"]):
        failures.append("row legality")
    if (len(leader_rows), len(ability_rows)) != ROW_COUNTS:
        failures.append(f"row counts {len(leader_rows)}/{len(ability_rows)} != "
                        f"{ROW_COUNTS[0]}/{ROW_COUNTS[1]}")
    # 对照 kit 方案（官方 donor 重建）
    if leader_rows != build_leader_rows(pack):
        failures.append("package leader rows != kit plan")
    plan = build_ability_rows(pack)
    if [r for k in sorted(plan) for r in plan[k]] != ability_rows:
        failures.append("package ability rows != kit plan")
    uniq = C.csv_split(pack.pkg_flat(UNIQUE)[UID])[0]
    gates["unique_condition"] = {"row": uniq, "name": uniq[1], "max_accumulation": uniq[4]}
    if uniq != build_unique_row(pack):
        failures.append("unique_condition row != kit plan")
    if uniq[4] != UNIQUE_MAX or uniq[1] != UNIQUE_NAME:
        failures.append(f"unique_condition name/cap {uniq[1]!r}/{uniq[4]!r} != {UNIQUE_NAME!r}/{UNIQUE_MAX!r}")

    # 技能树（从包字节读）
    sig = _load_json(root, OFFICIAL_SIG)
    gates["trees"] = {}
    for level in ("1", "2"):
        logical = wf_dsl.dsl_logical(f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}")
        tree = C.amf_parse(pack.pkg_path("common", logical).read_bytes())
        checks = tree_checks(tree, sig)
        want = _load_json(root, DESIGN_TREES[level])
        checks["equals_design_prototype"] = None if want is None else (want == tree)
        resolved = {}
        for p in checks["effect_paths"]:
            for ext in (".parts.amf3.deflate", ".timeline.amf3.deflate"):
                lgc = p + ext
                where = next((r for r in C.CLIENT_ROOTS if pack.pkg_has(r, lgc)), None)
                resolved[lgc] = f"package:{where}" if where else ("live" if pack.live_locate(lgc) else None)
        checks["effect_resolution"] = resolved
        gates["trees"][level] = checks
        if not checks["ok"] or checks["equals_design_prototype"] is False or not all(resolved.values()):
            failures.append(f"tree {level}")

    # 能力1#3（629）调用的 ability_skill DSL：从包字节读回、静态校验、与设计原型逐字相同
    as_logical = wf_dsl.dsl_logical(AS_PROGRAM)
    if not pack.pkg_has("common", as_logical):
        failures.append(f"ability_skill program missing from package: {as_logical}")
        gates["trees"]["ability_skill"] = {"logical": as_logical, "ok": False, "missing": True}
    else:
        as_tree = C.amf_parse(pack.pkg_path("common", as_logical).read_bytes())
        as_checks = tree_checks(as_tree, sig)
        want = _load_json(root, DESIGN_AS_TREE)
        as_checks["equals_design_prototype"] = None if want is None else (want == as_tree)
        as_checks["equals_kit_plan"] = as_tree == compose_ability_skill_tree(pack)[0]
        as_checks["logical"] = as_logical
        # R1「移动」忠实度：包内成品字节 vs 归档/live 迁移源（审查第 1/3 条）。
        # 交叉校验源是**被迁移的原块**，不是 plan.json —— plan.json 与 kit 同源，对规格级错误免疫。
        as_checks["migration_source"] = {"archive": MIGRATION_ARCHIVE, "level": MIGRATION_LEVEL,
                                         "diff_whitelist": {f"{a}[{i}]": {"new": nv, "why": why}
                                                            for (a, i), (nv, why) in MIGRATION_DIFF.items()},
                                         "problems": migration_problems(as_tree)}
        gates["trees"]["ability_skill"] = as_checks
        if not as_checks["ok"] or as_checks["equals_design_prototype"] is False \
                or not as_checks["equals_kit_plan"]:
            failures.append("tree ability_skill")
        if as_checks["migration_source"]["problems"]:
            failures.append(f"ability_skill vs migrated live block: "
                            f"{as_checks['migration_source']['problems'][:4]}")

    # custom_ability_string：629 行 c70 的文案键必须在包内且被认领（漏认领会在 rebase 时静默回滚）
    cas_rows = pack.pkg_flat(CAS) if pack.pkg_has("common", CAS) else {}
    cas_claim = next((c for c in pack.load_claims()
                      if (c["root"], c["logical_path"]) == ("common", CAS)), None)
    invoke_rows = [r for r in ability_rows if r[47] == "629"]
    # 改版 2 审查第 1 条：从包字节按键复核 629 行的主位绑定
    unison_lock = unison_lock_problems({f"{CID}{i}": C.csv_split(abil[f"{CID}{i}"]) for i in range(1, 7)})
    gates["unison_lock"] = {"problems": unison_lock,
                            "keys": {f"{CID}{i}": C.csv_split(abil[f"{CID}{i}"])[0][1] for i in range(1, 7)},
                            "invoke_rows": [[r[0], r[1], r[6], r[13], r[20]] for r in invoke_rows]}
    if unison_lock:
        failures.append(f"InvokeSkill unison lock: {unison_lock}")
    # 改版 3：从包字节复核「每层夜百合」的受益面（暗属性角色全体 + 协力球）
    by_key = {f"{CID}{i}": C.csv_split(abil[f"{CID}{i}"]) for i in range(1, 7)}
    lily_target = lily_layer_target_problems(by_key)
    gates["lily_layer_targets"] = {
        "problems": lily_target,
        "party_target": [LILY_PARTY_TARGET, LILY_PARTY_GROUPS], "assist_target": LILY_ASSIST_TARGET,
        "multiball_readable_kinds": sorted(LILY_MULTIBALL_READABLE),
        "multiball_unreadable_kinds": sorted(LILY_MULTIBALL_UNREADABLE),
        "rows": [{"key": k, "line": i, "during_kind": r[109], "target": r[110], "target_groups": r[111],
                  "per_stack": r[113], "per_stack_max_level": r[114], "stack_cap": r[102]}
                 for k, i, r in lily_layer_rows(by_key)]}
    if lily_target:
        failures.append(f"lily layer targets: {lily_target}")
    cas_style = cas_text_problems(cas_rows.get(CAS_KEY) or CAS_TEXT)
    gates["custom_ability_string"] = {"key": CAS_KEY, "in_package": CAS_KEY in cas_rows,
                                      "claimed": bool(cas_claim and CAS_KEY in cas_claim["outer_keys"]),
                                      "text_equals_kit": cas_rows.get(CAS_KEY) == CAS_TEXT,
                                      "text": cas_rows.get(CAS_KEY), "style_problems": cas_style,
                                      "invoke_rows": [[r[0], r[70], r[71]] for r in invoke_rows]}
    if cas_rows.get(CAS_KEY) != CAS_TEXT:
        failures.append("custom_ability_string row != kit plan")
    if cas_style:
        failures.append(f"custom_ability_string style: {cas_style}")
    if not (cas_claim and CAS_KEY in cas_claim["outer_keys"]):
        failures.append("custom_ability_string key not claimed")

    # 面板文案两条规则（rev2 文案规则-补充.md）：文案全集 + 包内 CAS 正文
    pkg_texts = dict(PANEL_TEXTS, CAS_TEXT=cas_rows.get(CAS_KEY) or CAS_TEXT)
    text_style = panel_text_problems(pkg_texts)
    flag_rows = [r[0] for r in ability_rows if SKILL_FLAG_KINDS & set(r)]
    gates["panel_text"] = {"texts": pkg_texts, "problems": text_style,
                           "banned_words": list(CAP_WORDING_BANNED),
                           "wushangxian_count": sum(t.count("无上限") for t in pkg_texts.values()),
                           "change_skill_flag_rows": flag_rows,
                           "rule2_applicable": bool(flag_rows)}
    if text_style:
        failures.append(f"panel text rules: {text_style}")
    if len(invoke_rows) != 1:
        failures.append(f"InvokeSkill(629) ability rows = {len(invoke_rows)}, want 1")
    for r in invoke_rows:
        if r[70] != CAS_KEY or r[71] != AS_PROGRAM:
            failures.append(f"InvokeSkill row references {r[70]!r}/{r[71]!r}")

    # 特效 timeline 内嵌 SE（预载引用，解析失败＝数据不足）/ parts 纹理
    fams = pack.read_evidence("effect-families.json", {}) or {}
    fx, fx_problems = effect_timeline_gate(pack, fams)
    gates["effect_timeline_sounds"] = fx
    gates["effect_timeline_problems"] = fx_problems
    failures += [f"effect timeline: {p}" for p in fx_problems]
    sheets = {}
    for dst_dir, fam in fams.items():
        name = dst_dir.rsplit("/", 1)[-1]
        sheet = f"{dst_dir}/{name}.png"
        donor = f"{fam['src_dir']}/{fam['donor']}.png"
        if not pack.pkg_has("common", sheet):
            failures.append(f"effect sheet missing {sheet}")
            continue
        new = C.png_open(pack.pkg_path("common", sheet).read_bytes())
        _r, src_raw, _s = pack.template_asset(donor)
        src = C.png_open(src_raw)
        clear = (new.getchannel("A").histogram()[0], src.getchannel("A").histogram()[0])
        sheets[sheet] = {"size": list(new.size), "donor_size": list(src.size), "alpha0": clear[0],
                         "donor_alpha0": clear[1], "sha256": C.sha256(pack.pkg_path("common", sheet).read_bytes()),
                         "recolored": new.tobytes() != src.tobytes()}
        if new.size != src.size or (clear[1] and clear[0] * 2 < clear[1]):
            failures.append(f"effect sheet shape/alpha {sheet}")
    gates["effect_sheets"] = sheets
    fx_manifest_present = bool(fx_sheet_overrides(root))
    sheet_probs = fx_sheet_problems(pack, root)
    gates["effect_sheet_recolor"] = {"fx_manifest": FX_MANIFEST if fx_manifest_present else None,
                                     "store_bytes_equal": fx_manifest_present and not sheet_probs,
                                     "problems": sheet_probs}
    failures += [f"effect sheet: {p}" for p in sheet_probs]
    icon_raw = pack.pkg_path("common", ICON_LOGICAL).read_bytes() if pack.pkg_has("common", ICON_LOGICAL) else b""
    icon_ok = False
    if icon_raw[:4] == b"\x89png":
        icon = C.png_open(icon_raw)
        frame = C.png_open(pack.official_read(ICON_FRAME_DONOR) or pack.live_read(ICON_FRAME_DONOR))
        icon_ok = icon.size == (48, 48) and icon.getchannel("A").tobytes() == frame.getchannel("A").tobytes()
    gates["unique_icon"] = {"logical": ICON_LOGICAL, "store_magic": icon_raw[:4].hex(), "ok": icon_ok,
                            "sha256": C.sha256(icon_raw) if icon_raw else None}
    if not icon_ok:
        failures.append("unique_condition icon")

    # action_skill / switched / 路由 / 文本
    action = core.load_nested_table_bytes(pack.pkg_path("common", ACTION).read_bytes(), ACTION).rows[CODE].text_rows()
    action = {k: C.csv_split(v)[0] for k, v in action.items()}
    switched = core.load_nested_table_bytes(pack.pkg_path("common", SWITCHED).read_bytes(), SWITCHED) \
        .rows[VOICE_READY].text_rows()
    switched = {k: C.csv_split(v)[0] for k, v in switched.items()}
    crow = pack.pkg_character_row()
    trow = pack.pkg_character_text_row()
    route = V.normalize_route(ROUTE_COLS, CODE)
    gates["action_skill"] = {"rows": action, "switched": switched, "route": crow[9:17]}
    if action != build_action_rows(pack):
        failures.append("action_skill rows != kit plan")
    if switched != V.switched_rows(action):
        failures.append("switched_action_skill rows != voice tool convention")
    if crow[9:17] != route:
        failures.append("character c9-c16 != voice route")
    if trow != text_row():
        failures.append("character_text row != design")
    server = json.loads(pack.pkg_path("server", "cdndata/character.json").read_bytes())[CID][0]
    if server != crow:
        failures.append("server cdndata/character.json mirror != package character row")

    # describe 全部行存档
    gates["describe"] = {
        "leader_ability": wf_describe.describe_rows(leader_rows, "leader_ability"),
        "ability": {f"{CID}{i}": wf_describe.describe_rows(C.csv_split(abil[f'{CID}{i}']), "ability")
                    for i in range(1, 7)},
    }

    # manifest / status / inspect
    manifest = json.loads((pack.package / "manifest.json").read_text(encoding="utf-8"))
    needed = sorted(set(ag["required_capabilities"]) | set(lg_["required_capabilities"]))
    declared = sorted(manifest.get("required_capabilities") or [])
    gates["capabilities"] = {"needed_by_rows": needed, "manifest": declared}
    if declared != needed:
        failures.append(f"manifest required_capabilities {declared} != rows {needed}")
    m_uniq = manifest.get("unique_condition", {}).get(UID, {})
    if m_uniq.get("icon") != ICON_LOGICAL:
        failures.append("manifest unique_condition icon missing")
    if m_uniq.get("name") != UNIQUE_NAME or m_uniq.get("max_accumulation") != int(UNIQUE_MAX):
        failures.append(f"manifest unique_condition {m_uniq.get('name')!r}/"
                        f"{m_uniq.get('max_accumulation')!r} != {UNIQUE_NAME!r}/{UNIQUE_MAX}")
    if as_logical not in (manifest.get("skills") or {}).get("programs", []):
        failures.append(f"manifest skills.programs missing {as_logical}")
    mrep = pack.read_evidence("manifest_report.json", {}) or {}
    gates["manifest_report"] = {k: mrep.get(k) for k in ("validate_manifest", "reconcile", "required",
                                                          "missing_required", "manifest_errors",
                                                          "three_layer_claim_status", "manifest_sha256")}
    if mrep.get("validate_manifest") or any((mrep.get("reconcile") or {}).values()) \
            or mrep.get("missing_required") or mrep.get("manifest_errors"):
        failures.append("manifest report")
    status = pack.read_evidence("flow-status.json", {}) or {}
    gates["flow_status"] = {"ok": status.get("ok"), "errors": status.get("errors")}
    if status.get("ok") is False or status.get("errors"):
        failures.append("flow status")
    inspect = (pack.read_evidence("flow-inspect.json", {}) or {}).get("summary") or {}
    master = inspect.get("master_reference") or {}
    conflicts = ((inspect.get("preflight") or {}).get("conflicts")) or []
    own, foreign = split_preflight_conflicts(conflicts, pack.load_claims())
    gates["inspect"] = {"returncode": inspect.get("returncode"), "structurally_ready": inspect.get("structurally_ready"),
                        "master_reference": master, "preflight": inspect.get("preflight"),
                        "chain": inspect.get("chain"),
                        "conflicts_own_claims": own, "conflicts_foreign_live_drift": foreign,
                        "conflicts_note": ("本角色自己认领的键才判红；跨角色共享表漂移（别人角色已发布、本包的全表载荷还是旧的）"
                                           "是串行发布第二包起的预期状态，由主控在发布前 flow rebase 收口"
                                           "（记忆卡 wf-flow-serial-publish-order）")}
    if master.get("problems") != [] or master.get("missing") not in ([], None):
        failures.append("inspect master_reference")
    if own:
        failures.append(f"inspect conflicts on own claims: {own[:5]}")
    # rc!=0 只允许「仅剩跨角色漂移」这一种；其余（缺资产、认领不一致、引用缺失）照样判红
    if not inspect.get("structurally_ready") and not (foreign and not own and not master.get("problems")
                                                      and inspect.get("missing_required") in ([], None)
                                                      and (inspect.get("three_layer_claim_status") or {}).get("consistent")):
        failures.append("inspect structural readiness")

    digest = kit_digest(pack)
    kit_report = pack.read_evidence("kit-report.json", {}) or {}
    kit_gates = pack.read_evidence("kit-gates.json", {}) or {}
    if kit_gates.get("kit_digest") != digest or kit_report.get("kit_digest") != digest:
        failures.append("kit evidence stale (kit_digest changed since kit step)")
    if not kit_gates.get("static_ok"):
        failures.append("kit static gates")
    # manifest 须是当前盘面（kit/像素/语音写盘后必须重跑 manifest）
    import wf_seasonal7_manifest as M
    disk = {name: {e["logical_path"]: e["sha256"] for e in entries} for name, entries in M.scan_roots(pack).items()}
    listed = {name: {e["logical_path"]: e["sha256"] for e in (manifest.get("roots") or {}).get(name, [])}
              for name in disk}
    stale = sorted(f"{n}:{lg}" for n in disk for lg in set(disk[n]) | set(listed[n])
                   if disk[n].get(lg) != listed[n].get(lg))
    gates["manifest_roots_current"] = {"ok": not stale, "stale": stale[:20], "files": sum(map(len, disk.values()))}
    if stale:
        failures.append(f"manifest roots stale vs disk ({len(stale)}): rerun --step manifest")

    # 集成待办（语音 22 条 + speech 8 行 + 像素 2 张）：只报告，不计入 all_pass；发布前必须 clear
    integration = package_integration_pending(pack)
    gates["integration_pending"] = integration
    # 语音装包回执（impl/primula/voice_merge.py 写 evidence/voice-report.json）
    vrep = pack.read_evidence("voice-report.json", {}) or {}
    planned_voice = {f"character/{CODE}/voice/{s}.mp3" for s in V.SLOTS}
    vprobs = []
    if vrep.get("status") != "packed":
        vprobs.append(f"voice-report status={vrep.get('status')}")
    rep_assets = {a.get("logical_path"): a.get("sha256") for a in vrep.get("assets") or []}
    if set(rep_assets) != planned_voice:
        vprobs.append("voice-report assets != 22 planned slots")
    for lg, want in sorted(rep_assets.items()):
        if not pack.pkg_has("common", lg) or C.sha256(pack.pkg_path("common", lg).read_bytes()) != want:
            vprobs.append(f"voice file drifted from voice-report: {lg}")
    manifest_voice = sorted(lg for lg in listed.get("common", {}) if lg.startswith(f"character/{CODE}/voice/"))
    if manifest_voice != sorted(planned_voice):
        vprobs.append(f"manifest voice entries != 22 planned slots: {sorted(set(manifest_voice) ^ planned_voice)[:8]}")
    if trow[11] != V.VOICE_ACTOR:
        vprobs.append(f"character_text c11={trow[11]!r} != {V.VOICE_ACTOR}")
    gates["voice_report"] = {"status": vrep.get("status"), "run": vrep.get("run"), "problems": vprobs}
    # 发布前置：包内共享表是整文件投递，缺别人角色的键 = 把他们从 live 抹掉。
    # 跨角色漂移不算本角色的缺陷（串行发布第二包起的预期状态），但**绝不能和「可发布」同屏**：
    # 单列成 publish_blockers，并把 release_ready_after_integration 压成 false（审查第 4 条）。
    publish_blockers = publish_blockers_for(foreign)
    gates["publish_blockers"] = publish_blockers
    gates["needs_rebase_before_publish"] = bool(foreign)
    kit_scope_ready = bool(not failures and integration["clear"] and not vprobs)
    gates.update({"kit_digest": digest, "failures": failures, "all_pass": not failures,
                  "kit_scope_ready": kit_scope_ready,
                  "release_ready_after_rebase": kit_scope_ready,
                  "release_ready_after_integration": bool(kit_scope_ready and not publish_blockers)})
    out = root / GATES_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(gates, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if write_status and kit_report:
        kit_report["status"] = "ready-for-review" if not failures else "draft"
        pack.write_evidence("kit-report.json", kit_report)
    return {"all_pass": not failures, "failures": failures, "gates_file": str(out),
            "kit_status": kit_report.get("status"), "integration_clear": integration["clear"],
            "pixel_clear": integration["pixel"]["clear"], "voice_clear": integration["voice"]["clear"],
            "voice_report_problems": vprobs,
            "needs_rebase_before_publish": gates["needs_rebase_before_publish"],
            "publish_blockers": publish_blockers,
            "release_ready_after_rebase": gates["release_ready_after_rebase"],
            "release_ready_after_integration": gates["release_ready_after_integration"]}


# ---------------------------------------------------------------- 框架缺口规避：发布后的 inspect
#
# 角色已上线（active 账本里已有本包的 ownership hash）后，``flow preflight`` 必须拿到 installed manifest，
# 否则直接报 ``active ownership hash exists but installed manifest was not supplied``（rc=2）。
# ``wf_seasonal7_build.step_inspect`` 不传 ``--installed-package-dir``，所以框架的 ``--step inspect``
# 在改版重建包时必然失败。这里在 kit 内补上该参数，其余（复制到临时副本、只在副本里封存、
# 回写 evidence/flow-inspect.json）与框架一致。不改框架公共文件。

PKG_ARCHIVE_DIRNAME = "pkgarchive"                # <仓库父目录>/pkgarchive/<package_id>-<链号>/


def installed_package_candidates(root: Path, pkg_id: str) -> list[Path]:
    """已发布包的归档目录（链号新→旧）。"""
    import re
    base = root.parent / PKG_ARCHIVE_DIRNAME
    if not base.is_dir():
        return []

    def version_key(path: Path):
        return [int(x) for x in re.findall(r"\d+", path.name[len(pkg_id) + 1:])] or [0]

    found = [d for d in base.iterdir()
             if d.is_dir() and d.name.startswith(pkg_id + "-") and (d / "manifest.json").is_file()]
    return sorted(found, key=version_key, reverse=True)


def run_inspect(installed_dir: str | None = None) -> dict[str, Any]:
    """``--step inspect`` 的替代：在 workspace 副本上跑 flow preflight，并补上 ``--installed-package-dir``。"""
    import os
    import shutil
    import wf_seasonal7_build as B
    import wf_seasonal7_common as C
    import wf_seasonal7_specs as S
    pack = C.S7Pack(S.get_spec("primula"))
    pack.check_identity()
    root = pack.root
    candidates = ([Path(installed_dir)] if installed_dir
                  else installed_package_candidates(root, pack.spec.pkg_id))
    guarded = [pack.package / "manifest.json", pack.evidence / "status.json", pack.evidence / "hash-cache.json"]
    before = {str(f): (f.read_bytes() if f.is_file() else None) for f in guarded}
    base = pack.batch_dir / B.INSPECT_DIR
    attempts: list[dict[str, Any]] = []
    rc, payload, used, workspace_copy = None, None, None, None
    for candidate in candidates or [None]:
        copy_root = base / f"primula-{os.getpid()}"
        if copy_root.exists():
            shutil.rmtree(copy_root)
        try:
            copy_root.mkdir(parents=True)
            workspace_copy = copy_root / pack.workspace.name
            shutil.copytree(pack.workspace, workspace_copy)
            extra = ["--profile", "cn"]
            if candidate is not None:
                extra += ["--installed-package-dir", str(candidate)]
            rc, payload = B._flow("preflight", workspace_copy, root, extra)
        finally:
            shutil.rmtree(copy_root, ignore_errors=True)
            try:
                base.rmdir()
            except OSError:
                pass
        errors = payload.get("errors") or []
        attempts.append({"installed_package_dir": None if candidate is None else str(candidate),
                         "returncode": rc, "errors": errors})
        used = candidate
        if not any("not hash-bound" in e or "different package_id" in e for e in errors):
            break
    after = {str(f): (f.read_bytes() if f.is_file() else None) for f in guarded}
    if after != before:
        raise KitError("inspect modified the real workspace")
    text = json.dumps(payload, ensure_ascii=False)
    for old in (workspace_copy, None if workspace_copy is None else workspace_copy.resolve()):
        if old is not None:
            text = text.replace(json.dumps(str(old))[1:-1], json.dumps(str(pack.workspace))[1:-1])
    payload = json.loads(text)
    ready, reason = B.kit_readiness(pack)
    result = B._preflight_summary(rc, payload, pack, pack.workspace)
    own, foreign = split_preflight_conflicts((result.get("preflight") or {}).get("conflicts") or [],
                                             pack.load_claims())
    # rc=3「尚未达到发布条件」只要全部堵点都是跨角色共享表漂移，就是串行发布第二包起的预期状态：
    # 由主控在发布前 flow rebase 收口，不是本角色的缺陷（记忆卡 wf-flow-serial-publish-order）。
    drift_only = bool(rc == 3 and foreign and not own and not result.get("missing_required")
                      and (result.get("master_reference") or {}).get("problems") == []
                      and (result.get("three_layer_claim_status") or {}).get("consistent"))
    result.update({"sealed_real_workspace": False, "sealed_copy_only": True, "kit_ready": ready,
                   "kit_reason": reason, "structurally_ready": rc == 0 or drift_only,
                   "flow_returncode": rc,
                   "conflicts_own_claims": own, "conflicts_foreign_live_drift": foreign,
                   "blocked_only_by_foreign_live_drift": drift_only,
                   "needs_rebase_before_publish": bool(foreign),
                   "flow_next_command": result.get("next_command"),
                   "installed_package_dir": None if used is None else str(used),
                   "installed_package_attempts": attempts,
                   "framework_gap": "wf_seasonal7_build.step_inspect 不传 --installed-package-dir，"
                                    "角色上线后（active 账本已有 ownership hash）必然 rc=2；"
                                    "本 kit 的 inspect 子命令补上该参数，其余与框架一致"})
    pack.write_evidence("flow-inspect.json", {"summary": result, "payload": payload})
    if rc != 0 and not drift_only:
        raise KitError(f"flow preflight (inspect copy) rc={rc}: {payload.get('errors')}; own_conflicts={own[:5]}")
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["inspect"]:
        if len(args) > 2:
            print("usage: python mod-tools/wf_seasonal7_kit_primula.py gates|inspect [<installed package dir>]")
            return 2
        print(json.dumps(run_inspect(args[1] if len(args) == 2 else None), ensure_ascii=False, indent=1))
        return 0
    if args[:1] != ["gates"]:
        print(__doc__)
        return 0
    result = run_gates()
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

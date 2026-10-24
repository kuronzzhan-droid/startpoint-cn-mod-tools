# -*- coding: utf-8 -*-
"""PARADOX（5920001）：作者 2026-09-28 设计的单件武器生成器。

纯函数：读 live 模板行 → 输出 flat / nested / dsl / server 增量（与 ``wf_cursed_weapons`` 共用装配件与校验）。
效果（写在 ability_soul，觉醒 1→5 数值不变）：

- 自身攻击力 +550%；直接攻击 / 技能 / 强化弹射 / 能力伤害各 +550%；
- 独立乘区（全伤害 723 / 直击 693 / 技能 694 / 能力 695 / 强化弹射 696）各 +10%；
- 自身直接攻击判定额外 +5（629 → ACAdditionalDirectAttack 共 6 段；引擎把一次直击的伤害均分到各段，
  段数本身不加总伤，加的是连击与命中次数）；
- 每次弹射连击 +35；自身技能充能速度 +20%；技能槽上限 +50%；
- 自身弱体无效（58 DebuffPrevent = ConditionPrevent(All(Bad))：毒/麻痹/冻结/沉默/回复无效/增益无效与各类数值降低全挡，
  不用 57——它是 All(Both)，连增益也挡）；自身攻击力再加上 100% 合击角色攻击力（717）；
- 自身为基诺维 / 杰拉德 / 凯尔时攻击力再 +150%。角色组只认属性/类型/性别/种族/角色标签，
  所以新增 3 个角色标签（character_tag）并写进这三人 character 表 c5（逗号列表，保留原有标签）。
  赛瑞斯按作者 0928 要求移出（之后重做）；生成器会把不在名单里的 tag_paradox_* 从角色行与标签表清掉。

强化（作者 0928：「觉醒 120 级满级属性、数值高一点、添加诅咒」）：照诅咒武器的强化体系——强化类目 6「诅咒武器·觉醒」、
五重决战材料 6 阶、需满破；1→119 线性成长 + 120 级补足到终值（攻击/四类伤害 800%、独立乘区 20%、直击 8 段、弹射连击 50、
充能 30%、槽上限 100%、合击攻击 150%、三人专属 250%）。120 级解放诅咒（作者 0928 定稿）：自身以外的角色攻击力 -800%
（引擎攻击加成总和下限 -50%：实际 = 抹掉其攻击增益并减半）、技能充能速度 -40%；「自身以外的角色无法获得能力与装备的技能槽增加」
走客户端补丁 equipment-rules R3（423 扩到装备强化表 parseAt109）：持续 423 目标 ExceptMyself、规则码 8（只拦「能力」类回槽，
技能直接回槽 / 移动 / 开局 / PF 与协力球照常；开局触发的 629 DSL 加槽不拦，作者已接受），触发 = 自身持有固有状态「诅咒」
（134），由同为 120 级的开局 461 给自己刻上（永续、不可驱散、强制付与：c10=true 短路 ConditionPrevent，自身弱体无效挡不住）。
不用 HpHigh 0 恒真触发——面板会显示「生命值0%以上时」。423 行在未打补丁的客户端 = C7050，全员装上补丁 APK 后才能上 live：
``build`` 默认按 1047 基线（client_capabilities）把 423 行报成缺 equipment-gauge-gain-rules-v1 的 problems，调用方显式声明后才放行。
攻击 / 充能两条诅咒是数值不是状态，自身弱体无效同样挡不住。

衰减（作者要求「每多装备一件武器/魂珠效果衰减 25%」）：客户端补丁 client-patch/equipment-rules 在开战装配时数同队其他
武器/魂珠件数 n，n=1..3 把本体魂与强化词条换成分档键 ID+1000·n（75/50/25%），n≥4 整件失效（诅咒一起失效，作者已接受）。
分档键由本生成器产出：增益按比例缩放（离散的段数/连击四舍五入），弱体无效保留，**诅咒不缩放**（代价不随衰减减轻，
含 R3 的 423 行与刻「诅咒」的 461 行）；分档键不进 equipment/item 表。装备详情页仍显示满档，规则写进装备说明 c7。

技能回响（作者 0928：「放技能时额外放一次 25% 效果、不耗槽」无通用原语 → 只给三人做专属复刻）：三人各一行
「自身发动技能时 + 自身是该角色」→ 629 调用 assets/paradox/echo/<code>.json（由同目录 derive_echo.py 从 live
＋版技能推导：数值 ×0.25 满级常数、删状态机/吞噬/扣血/贯穿/冻结等、显式属性码、零特效、削韧 0、开头 Wait 60/90/100 帧）。
629 不计「技能发动」，不会自触发；回响状态与本体来源不同、数值相加不覆盖。回响行在各衰减分档里原样保留。

装备详情覆盖（作者 0928：「攻击与全部伤害类型、全部独立乘区写在一起」，生成文案做不到）：custom_ability_string 三键
desc_override_equipment_<ID> / _enhancement_<ID> / _enhancement_<ID>_final，由 override_texts() 按出行用的同一批数值常量
渲染、"\\n" 分行；客户端补丁 client-patch/equipment-description-override（capability equipment-description-override-v1）
命中即整段替换本体说明与两个强化块。行为型：未装补丁的客户端不读这些键、照旧显示生成文案，不崩，所以只报 capability、
不进 problems，数据可先于 APK 上线。分档 ID 不出覆盖键（详情页永远拿满档对象）。

强化 Lv200（作者 0928 定稿，设计稿 ${WF_ROOT}/out/PARADOX-20260928/lv200-frame/设计.md 方案甲）：强化主表 c0 = 200；
名字 / 图标 / 说明 / 框仍在 120 级切换（c1 / c3 / c5 / c7 = 120）。成长项的 120 级补足行从 learn 120 / max 120 改成
learn 120 / max 200：power1 不动（Lv120 数值与 live 逐字节相同），first_max 抬到 Lv200 合计（攻击与四类伤害 1000%、
独立乘区 30%、充能 50%、合击攻击 200%、三人专属 350%；槽上限已顶 +100% 钳制不涨）。直击段数、弹射连击与诅咒四行不动
（learn = max = 120）。强化数值表加 200 键（缺它 Lv121+ 空引用崩）。商店第 7–10 阶（159 / 160 / 199 / 200）只收
新材料「矛盾结晶」「悖论之核」（暂无掉落来源）。这些常量是 PARADOX 专属副本，不动 wf_cursed_weapons 的共用
ENH_STAGES / ENH_STATUS_ROWS / growth_pair（它们服务 29 把诅咒武器）。
200 级外观走 custom_ability_string 三键（行为型：未装补丁 = 仍显示 lv120 图标 + 粉框）：
``enhanced_pixelart_tier2_<lv120 图标>`` = "200,<lv200 图标>"（第二图标档）、``enhanced_frame_override_<lv200 图标>`` = 蓝金框底图
（这两键 capability equipment-enhanced-look-v1）；``enhanced_party_frame_override_<lv200 图标>`` = 编成装备槽蓝金框
（72×72 圆角 RGBA，独立 capability equipment-enhanced-party-frame-v1：只装 v1 的客户端编成槽仍是粉框）。
"""
from __future__ import annotations

import json
import re
import zlib
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

import wf_client_legality as L
import wf_client_patch_scope as S
import wf_cursed_weapons as W
import wf_describe
import wf_dsl
from wf_cursed_weapons import Eff

ITEM, EQUIPMENT, EQUIPMENT_STATUS, SOUL, CAS = W.ITEM, W.EQUIPMENT, W.EQUIPMENT_STATUS, W.SOUL, W.CAS
ENH, EA, ENH_STATUS, ENH_SHOP, UNIQUE = W.ENH, W.EA, W.ENH_STATUS, W.ENH_SHOP, W.UNIQUE
CHARACTER = "master/character/character.orderedmap"
CHARACTER_TAG = "master/character/character_tag.orderedmap"
FLAT_TABLES = (ITEM, EQUIPMENT, SOUL, ENH, EA, ENH_SHOP, UNIQUE, CAS, CHARACTER_TAG, CHARACTER)

ID = "5920001"
NAME = "PARADOX"
SLUG = "paradox"
CATEGORY = "剑"                                  # 服务端 equipment_lookup 类别
ICON = "item/equipment/mod/paradox/paradox"
ICON120 = "item/equipment/mod/paradox/paradox_lv120"
#: Lv200 图标（第二图标档，经 enhanced_pixelart_tier2_ 键由补丁切换；c3/c4 仍是 120 / lv120）、蓝金强化框底图
#: 与编成装备槽蓝金框（官方 party_equipment_rainbow_enhanced 同一套换色，α 照抄官方圆角）
ICON200 = "item/equipment/mod/paradox/paradox_lv200"
FRAME_BLUEGOLD = "item/equipment/mod/paradox/paradox_frame_bluegold"
PARTY_FRAME_BLUEGOLD = "item/equipment/mod/paradox/paradox_party_frame_bluegold"
NAME120 = f"{NAME}·终式"
#: 类别称呼（作者 0928「武器PARADOX归类为悖论武器，除了武器名字，其他地方都不要英文的，写悖论」）：英文只留在
#: 武器名 NAME / 强化名 NAME120（魂珠名「<武器名>魂珠」同属名字），其余玩家可见文案写它；build 里有门禁。
CLASS_NAME = "悖论武器"
#: 面板上 423 只显示 battle-rules 的通用文字「限制技能槽增加」，作者原话写进强化说明（≤54 字）。
ENH_DESCRIPTION = "强化至120级进入终式：数值全面提升并解放诅咒，除自身外的角色无法获得能力和装备的技能槽增加效果。"
DSL_DIR = "battle/action/skill/action/ability_skill/paradox"
HITS = f"{DSL_DIR}$hits"
HITS_TEXT = "自身的直接攻击判定额外+5次（共6段）"
HITS_FINAL = f"{DSL_DIR}$hits_final"
HITS_FINAL_TEXT = "自身的直接攻击判定额外+7次（共8段）"
FLAVOR = "莫比乌斯环扭成的双色长剑。握着它的人越是孤身一人，就越是无可匹敌。"
#: 衰减规则（装备详情页与「发动可能能力」弹窗仍显示满档，玩家只能从说明里看到）；n≥4 = 其他武器/魂珠 4 件及以上。
DECAY_RULE = "同队每多1件其他武器或魂珠效果-25%，4件失效"
EQUIPMENT_STATUS_ROWS = {"1": "330,148", "5": "495,221"}
#: 固有状态 ID = 59200000 +（ID−5920000）×10 + k，照诅咒武器 59100000 + 行号×10 + k 的形状另起一段：
#: 诅咒段 5910101–5910199 的固有状态最多到 59100999，衰减段 5920001–5920999 落在 59200010–59209999，互不相交。
UNIQUE_BASE = 59200000
CURSE_UID = str(UNIQUE_BASE + (int(ID) - 5920000) * 10 + 1)       # 59200011「诅咒」
CURSE_UNIQUE_NAME = "诅咒"
#: 「诅咒」专属状态图标（48×48，源 assets/paradox/paradox_curse.png → battle/common/unique_condition/paradox_curse.png）
CURSE_ICON = "paradox_curse"
CURSE_ICON_SRC = Path(__file__).resolve().parents[3] / "assets/paradox/paradox_curse.png"
#: R3 规则码：只拦「能力」类回槽（8；连击触发 24、施技触发 40 同样命中），来源不限。
GAUGE_MASK = W.GAUGE_MASK
#: 客户端 capability 门禁：R3 的 423 行在未装 equipment-rules 的客户端 = C7050（EA parseAt109 / 魂 parseAt106）。
#: 基线 = 1047 客户端已有能力（与 client-patch/equipment-rules/rules.py INHERITED_CAPABILITIES 同步，测试互证）；
#: 补丁 APK 再加 R1/R2 的 equipment-rules-v1 与 R3 的 equipment-gauge-gain-rules-v1（package_apk.py 写进 candidate_capabilities）。
EQUIPMENT_RULES_CAP = W.EQUIPMENT_RULES_CAP
BASE_CLIENT_CAPABILITIES = W.BASE_CLIENT_CAPABILITIES
PATCHED_CLIENT_CAPABILITIES = W.PATCHED_CLIENT_CAPABILITIES
TAG_COLUMN = 5                                  # character 表 c5 = 角色标签列表（逗号分隔）
PRE_MY_SELF = "3"                                # 前置 MySelf：自身属于角色组
TAG_PREFIX = "tag_paradox_"
ECHO_DIR = Path(__file__).resolve().parents[3] / "assets/paradox/echo"
#: (角色 ID, 技能 code, 回响说明)。说明进 custom_ability_string（629 缺键=C8601）；只用全角标点。
ECHOES = (
    ("169999", "ginovi", "「掠影协奏」回响：1秒后以25%的效果再次施放（不吞噬协力球、不消耗生命值、不附加贯穿与固有状态）"),
    ("149999", "white_wolf_gerald",
     "「月耀一闪」回响：1.5秒后以25%的效果再次施放（不突进、不驱散、不附加贯穿／浮游／速度固定与时空侵蚀）"),
    ("139990", "kyle_moon",
     "「月华·狼牙连斩」回响：约1.7秒后以25%的效果斩向最近的敌人（不冲刺、不驱散、不冻结、不附加贯穿／加速与月狼·觉）"),
)

#: (角色 ID, 标签, 标签显示名)。标签显示名进词条说明「自身为…时」。
TAGS = (
    ("169999", "tag_paradox_ginovi", "基诺维"),
    ("149999", "tag_paradox_gerald", "杰拉德"),
    ("139990", "tag_paradox_kyle", "凯尔"),
)
#: 回响技能短名（装备详情覆盖文案用；回响延迟从 DSL 根 Wait 帧读，不手抄）。
ECHO_SKILL = {"ginovi": "掠影协奏", "white_wolf_gerald": "月耀一闪", "kyle_moon": "月华·狼牙连斩"}
ECHO_PERCENT = 25                                 # 回响效果比例 = derive_echo.SCALE（测试互证）

# 数值单一来源（设计值，%）：abilities() / enhancement_abilities() 按它们出行，override_texts() 按它们出装备详情覆盖文案，
# 改一个数 = 行与文案一起变（测试另按行重新求和核对文案里的每个数字）。
#: 攻击力 32 与直击 33 / 技能 34 / 强化弹射 55 / 能力 388 伤害；元组顺序 = 已发布行的 slot 顺序，不许改
DAMAGE_KINDS = ("32", "33", "34", "55", "388")
#: 独立乘区：全伤害 723 / 直击 693 / 技能 694 / 能力 695 / 强化弹射 696
MULT_KINDS = ("723", "693", "694", "695", "696")
#: 强化弹射两行是队伍级（target 留空）：行不写目标，文案不许写「自身」
TEAM_KINDS = frozenset({"55", "696"})
DAMAGE_LABEL = {"32": "攻击力", "33": "直接攻击伤害", "34": "技能伤害", "55": "强化弹射伤害", "388": "能力伤害"}
MULT_LABEL = {"723": "全伤害", "693": "直接攻击伤害", "694": "技能伤害", "695": "能力伤害", "696": "强化弹射伤害"}
#: 覆盖文案「全部伤害类型（…）」括号里的顺序
DAMAGE_TYPE_TEXT = (("33", "直接攻击"), ("34", "技能"), ("388", "能力"), ("55", "强化弹射"))
# *_TOTAL = 强化 Lv120（终式）合计，与 live 1.4.1064 起逐字节一致；*_TOTAL200 = 强化 Lv200 合计（作者 0928 方案甲）。
ATK_BASE, ATK_TOTAL, ATK_TOTAL200 = 550, 800, 1000             # 攻击力与四类伤害
MULT_BASE, MULT_TOTAL, MULT_TOTAL200 = 10, 20, 30              # 独立乘区
CHARGE_BASE, CHARGE_TOTAL, CHARGE_TOTAL200 = 20, 30, 50        # 35 技能充能速度（全员来源合计钳 [-100%, +100%]）
GAUGE_BASE, GAUGE_TOTAL = 50, 100                              # 245 技能槽上限（已顶 +100% 钳制，Lv200 不涨）
UNISON_BASE, UNISON_TOTAL, UNISON_TOTAL200 = 100, 150, 200     # 717 攻击力追加合击角色攻击力
CHOSEN_BASE, CHOSEN_TOTAL, CHOSEN_TOTAL200 = 150, 250, 350     # 32 + 三人标签前置
HITS_EXTRA_BASE, HITS_EXTRA_FINAL = 5, 7          # 直接攻击判定额外次数（629 段数 = 1 + 额外）
COMBO_BASE, COMBO_TOTAL = 35, 50                  # 226 每次弹射连击（120 级补 COMBO_TOTAL − COMBO_BASE）
CURSE_ATK, CURSE_CHARGE = -800, -40               # 120 级诅咒：自身以外的角色攻击力 / 技能充能速度
FINAL_LEVEL = 120                                 # 终式 / 诅咒解放；W.growth_pair 的成长行 1→119、补足行 learn 120（测试互证）
MAX_LEVEL = 200                                   # 强化满级（强化主表 c0）；补足行 max_power_level 续到这里

#: 新材料（作者 0928：暂无掉落来源，只能后台发放）。ID 避开五重 v2 正在用的 10000143–10000147 一带与
#: event_item_shop 的 100002xx 商品键：客户端 item 表、服务端 item_ids / item_lookup / item_sale 与全仓都未引用。
SHARD = "10000301"                                # 矛盾结晶（逐级）
PARADOX_CORE = "10000302"                         # 悖论之核（突破）
ASSET_DIR = Path(__file__).resolve().parents[3] / "assets/paradox"
#: 两件材料的图由「武器觉醒与新掉落」图标单元重画（assets/weapon-awaken/build_icons.py 生成，manifest.json 记像素 sha；
#: 设计 ${WF_ROOT}/out/武器觉醒与新掉落-20260928/设计.md §6.3/§6.4，作者 0928 确认预览）。本生成器直接取那里的源图，
#: 不再用 assets/paradox 下的旧图（旧图描边近黑、矛盾结晶杂色超标）——否则下一次暂存会把道具行改回旧图。
AWAKEN_ICON_DIR = Path(__file__).resolve().parents[3] / "assets/weapon-awaken/icons"
#: (道具 ID, 克隆模板, 名, 说明, c3 缩略图（独立 PNG，异步 setTexture）, 源图, c4 小图标)。
#: c3 用重画版新逻辑名 *_v2（旧名 contradiction_crystal / paradox_core 的独立 PNG 已在 live，留作孤儿，不原位覆盖）。
#: c4 是图集 item_icon/sprite_sheet 里的 PARADOX 专属子纹理，由 wf_weapon_awaken 边 E1 追加（图集整文件替换只归那一条边，
#: 本生成器不写图集）。c4 只能是已加载图集的子纹理：子纹理没上线就让道具行指过去，掉落展示 / 图鉴 getImage 当场 C8004
#: （memory wf-c8004-small-icon-atlas-rule）。所以改指在 build 里硬门控（与 wf_weapon_awaken 边 E2 的 _icon_ready 同口径）：
#: 只有调用方传入 live 图集子纹理名（build(atlas_names=atlas_names_from_raw(<ATLAS_MAP 原始字节>))）且含该 c4 时才改指；
#: 否则沿用 live 行现有的 c3/c4（live 无该行时沿用模板五重材料行的），连带不出该件的 c3 图，并记进输出的 icons_deferred。
MATERIAL_ATLAS_MAP = "item_icon/sprite_sheet.atlas.amf3.deflate"   # 与 wf_weapon_awaken.ATLAS_MAP 同一逻辑路径
MATERIALS = (
    (SHARD, "10000145", "矛盾结晶", f"光与影在同一晶面上互相否定而凝成的结晶。用于将{CLASS_NAME}强化至121级以上。",
     "item/materials/mod/paradox/contradiction_crystal_v2", AWAKEN_ICON_DIR / "contradiction_crystal.png",
     "item_icon/materials/mod/paradox/contradiction_crystal"),
    (PARADOX_CORE, "10000147", "悖论之核", f"首尾相接、永无终点的悖论之环的核心。用于突破{CLASS_NAME}的强化上限。",
     "item/materials/mod/paradox/paradox_core_v2", AWAKEN_ICON_DIR / "paradox_core.png",
     "item_icon/materials/mod/paradox/paradox_core"),
)
MATERIAL_DESC_LIMIT = 57                          # 与装备说明同一详情框量级；官方 item c5 p90 = 43 字
#: 强化商店 10 阶（阶段上限, [(材料, 数量), ...]），每份 = 1 级。1–6 阶是 wf_cursed_weapons.ENH_STAGES 在 live 1.4.1063
#: 的副本（不引用：共用常量改了不许连带改 PARADOX）；7–10 阶只收新材料，形状照 1–6 阶：逐级阶每级少量，突破阶一次大额。
#: 全程新材料合计：矛盾结晶 39×3 + 10 + 39×5 = 322、悖论之核 1 + 3 = 4。
PARADOX_ENH_STAGES = (
    (69, ((W.CRYSTAL, 1),)),
    (70, ((W.CRYSTAL, 10), (W.CORE, 1))),
    (98, ((W.CRYSTAL, 2),)),
    (99, ((W.CRYSTAL, 10), (W.CORE, 2))),
    (119, ((W.CRYSTAL, 3), (W.CORE, 1))),
    (120, ((W.CORE, 3), (W.BLUEPRINT, 2))),
    (159, ((SHARD, 3),)),
    (160, ((SHARD, 10), (PARADOX_CORE, 1))),
    (199, ((SHARD, 5),)),
    (MAX_LEVEL, ((PARADOX_CORE, 3),)),
)
#: 强化数值表（HP, ATK）：照官方 120 级武器的 {98, 99, 120}，另加 200 键——客户端按等级精确取最后一个键，
#: 缺 200 键时 Lv121–200 取到 null 空引用崩（EquipmentEnhancementStatusLogic.getParameterAt）。121 → 51/11、200 → 100/40。
PARADOX_ENH_STATUS_ROWS = {"98": "0,0", "99": "50,10", "120": "50,10", str(MAX_LEVEL): "100,40"}
#: 商店行模板：诅咒武器同款的 5900110<阶>（官方只有 1–6 阶；7–10 阶用第 6 阶，被覆写的列以外六行逐格相同）
SHOP_TEMPLATE_STAGES = 6

# 200 级外观（行为型：未装补丁不读、不崩）。补丁在缩略图 / 编成槽里只拿得到图标路径，拿不到等级，所以三键都按图标路径派生。
# 前两键 = client-patch/equipment-enhanced-look（equipment-enhanced-look-v1）；
# 编成槽框 = client-patch/equipment-enhanced-party-frame（equipment-enhanced-party-frame-v1，叠在 v1 APK 上的独立补丁）。
LOOK_TIER2_PREFIX = "enhanced_pixelart_tier2_"
LOOK_FRAME_PREFIX = "enhanced_frame_override_"
LOOK_PARTY_FRAME_PREFIX = "enhanced_party_frame_override_"
LOOK_TIER2_KEY = LOOK_TIER2_PREFIX + ICON120      # 值 = "<等级>,<图标>"：强化 ≥ 该等级时把 lv120 图标换成 lv200
LOOK_FRAME_KEY = LOOK_FRAME_PREFIX + ICON200      # 值 = 框底图路径：显示 lv200 图标的强化态缩略图换蓝金底
LOOK_PARTY_FRAME_KEY = LOOK_PARTY_FRAME_PREFIX + ICON200   # 值 = 编成槽框图路径：编成装备槽显示 lv200 图标的强化态换蓝金框
LOOK_KEYS = (LOOK_TIER2_KEY, LOOK_FRAME_KEY, LOOK_PARTY_FRAME_KEY)
LOOK_PREFIXES = (LOOK_TIER2_PREFIX, LOOK_FRAME_PREFIX, LOOK_PARTY_FRAME_PREFIX)
ENHANCED_LOOK_CAP = L.EQUIPMENT_ENHANCED_LOOK
PARTY_FRAME_CAP = L.EQUIPMENT_ENHANCED_PARTY_FRAME
#: 每个外观键需要的 capability（编成槽框单独一个：只装 v1 的接收端读不到它）
LOOK_CAPS = {LOOK_TIER2_KEY: ENHANCED_LOOK_CAP, LOOK_FRAME_KEY: ENHANCED_LOOK_CAP, LOOK_PARTY_FRAME_KEY: PARTY_FRAME_CAP}

#: 本武器全部图片（逻辑路径 → 源图、尺寸、是否必需）。蓝金框由另一执行者在画：缺图时暂存跳过它与框键，不报错。
ASSET_FILES = (
    (ICON + ".png", ASSET_DIR / "paradox.png", (20, 20), True),
    (ICON120 + ".png", ASSET_DIR / "paradox_lv120.png", (20, 20), True),
    (ICON200 + ".png", ASSET_DIR / "paradox_lv200.png", (20, 20), True),
    (FRAME_BLUEGOLD + ".png", ASSET_DIR / "paradox_frame_bluegold.png", (144, 144), False),
    (PARTY_FRAME_BLUEGOLD + ".png", ASSET_DIR / "paradox_party_frame_bluegold.png", (72, 72), True),
    ("battle/common/unique_condition/" + CURSE_ICON + ".png", CURSE_ICON_SRC, (48, 48), True),
    *((thumb + ".png", src, (20, 20), True) for _, _, _, _, thumb, src, _ in MATERIALS),
)

# 装备详情覆盖（client-patch/equipment-description-override，capability equipment-description-override-v1）：
# 键由装备 ID 派生，补丁在 AbilitySoulAbilityLogic 与 EquipmentEnhancementAbilityLogic 的详情方法前置查表，
# 命中即按 "\n" 分行显示、整段替换生成文案；键缺 / 空串 / 未装补丁 = 原文案、不崩（行为型，不进 problems）。
# 强化成长键是开关，_final 键可缺；衰减分档 ID（5921001 起）只在战斗装配出现，不得有覆盖键。
OVERRIDE_BASE = f"desc_override_equipment_{ID}"
OVERRIDE_GROWTH = f"desc_override_equipment_enhancement_{ID}"
OVERRIDE_FINAL = f"{OVERRIDE_GROWTH}_final"
OVERRIDE_KEYS = (OVERRIDE_BASE, OVERRIDE_GROWTH, OVERRIDE_FINAL)
OVERRIDE_SEPARATOR = "\n"
#: 单行字数上限：覆盖文案与装备说明 c7 显示在同一详情框，单行不超过官方 c7 实测最长（57 字）
OVERRIDE_LINE_LIMIT = W.DESC_LIMITS["equipment"]
OVERRIDE_FORBIDDEN = (
    (re.compile(r"生命值[^\n]*(?:以上|以下)"), "HP 恒真文本（生命值…以上/以下）"),
    (re.compile(r"自身为队长时"), "「自身为队长时」（覆盖文案禁写）"),
    (re.compile(r"自身[^\n]*强化弹射|强化弹射[^\n]*自身"), "「自身」修饰强化弹射（55/696 是队伍级）"),
)


TIER_STRIDE = 1000
TIERS = {1: 0.75, 2: 0.5, 3: 0.25}          # 同队其他武器/魂珠件数 n → 效果比例


def _count(n: int) -> str:
    return W.times(n)


def _half_up(x: float) -> int:
    return int(x + 0.5)


def tier_id(n: int) -> str:
    return str(int(ID) + TIER_STRIDE * n)


def _suffix(n: int) -> str:
    return f"_t{n}" if n else ""


def hits_program(n: int, final: bool) -> str:
    return f"{HITS_FINAL if final else HITS}{_suffix(n)}"


def hits_segments(n: int, final: bool) -> int:
    extra = HITS_EXTRA_FINAL if final else HITS_EXTRA_BASE
    return 1 + _half_up(extra * TIERS[n]) if n else 1 + extra


def hits_text(n: int, final: bool) -> str:
    seg = hits_segments(n, final)
    return f"自身的直接攻击判定额外+{seg - 1}次（共{seg}段）"


def hits_key(n: int, final: bool) -> str:
    return ("paradox_hits_final" if final else "paradox_hits") + _suffix(n)


def echo_program(code: str) -> str:
    return f"{DSL_DIR}$echo_{code}"


def echo_tree(code: str) -> list:
    return json.loads((ECHO_DIR / f"{code}.json").read_text(encoding="utf-8"))


def echo_rows() -> list[Eff]:
    tag_of = {cid: tag for cid, tag, _ in TAGS}
    return [Eff("0", W.invoke(f"paradox_echo_{code}", echo_program(code)),
                trig=W.trig(W.IT_SKILL, trigger_puller=W.P_SELF),
                pre=((PRE_MY_SELF, {"character_groups": tag_of[cid]}),),
                note=f"自身为 {cid} 时，发动技能后以 25% 效果回响一次")
            for cid, code, _ in ECHOES]


def _target(kind: str) -> str | None:
    return None if kind in TEAM_KINDS else W.T_SELF


def _who(kind: str) -> str:
    return "" if kind in TEAM_KINDS else "自身"


def abilities(n: int = 0) -> list[Eff]:
    """本体词条；n=1..3 为衰减分档（比例 TIERS[n]），行形状与满档逐行一致，只换数值与段数 DSL。"""
    self_ = W.T_SELF
    r = TIERS[n] if n else 1.0
    chosen = (PRE_MY_SELF, {"character_groups": ",".join(tag for _, tag, _ in TAGS)})
    combo = _half_up(COMBO_BASE * r)
    seg = hits_segments(0, False)
    return [
        *(Eff("0", W.stat(k, _target(k), ATK_BASE * r), note=f"{_who(k)}{DAMAGE_LABEL[k]} +{ATK_BASE}%")
          for k in DAMAGE_KINDS),
        *(Eff("0", W.stat(k, _target(k), MULT_BASE * r), note=f"{_who(k)}{MULT_LABEL[k]}独立乘区 +{MULT_BASE}%")
          for k in MULT_KINDS),
        Eff("0", W.invoke(hits_key(n, False), hits_program(n, False)),
            note=f"开局：自身直接攻击变为 {seg} 段（判定额外 +{seg - 1}）"),
        Eff("0", ("226", {"strength": (_count(combo), _count(combo))}), trig=W.trig("6", threshold=_count(1)),
            note=f"每次弹射连击 +{COMBO_BASE}"),
        Eff("0", W.stat("35", self_, CHARGE_BASE * r), note=f"自身技能充能速度 +{CHARGE_BASE}%"),
        Eff("0", W.stat("245", self_, GAUGE_BASE * r), note=f"自身技能槽上限 +{GAUGE_BASE}%"),
        Eff("0", ("58", {"target": self_}), note="自身弱体无效（异常状态与数值降低全部无效）"),
        Eff("0", W.stat("717", self_, UNISON_BASE * r), note=f"自身攻击力再加上 {UNISON_BASE}% 合击角色攻击力"),
        Eff("0", W.stat("32", self_, CHOSEN_BASE * r), pre=(chosen,),
            note=f"自身为基诺维/杰拉德/凯尔时攻击力再 +{CHOSEN_BASE}%"),
        *echo_rows(),                                          # 回响固定 25%，不随衰减分档缩放
    ]


def hits_dsl(segments: int = 6) -> list:
    """自身直接攻击 N 段、伤害修正 0（总伤害不变，均分到各段）；永续、不可驱散。同类状态段数多者胜（isBetterThan），
    120 级的 8 段会盖过本体的 6 段。"""
    return W.dsl_root(W.give(-17, [["ACAdditionalDirectAttack", W.P(9999999), W.P(segments), W.P(0.0), W.P(1)]],
                             "paradox_hits", cancelable=False))


def _growth_pair(kind: str, target: str | None, total: float, base: float, *, lift: float | None = None,
                 **kw) -> list[Eff]:
    """PARADOX 本体是满额（不走诅咒武器的 BASE_SCALE 弱化）。W.growth_pair 自 d63896fd 起按「设计值 × BASE_SCALE」
    扣本体实际值，这里把本体实际值折回设计值，使成长 + 补足 = 终值 − 本体（与 live 1.4.1064 一致：攻击 1→119 成长到
    +230%、120 级补足 +20%，加本体 550% = 800%）。

    lift = Lv200 合计 − Lv120 合计（%）：补足行续成 learn 120 → max MAX_LEVEL 的成长，power1 原样（Lv120 取 power1，
    与 live 逐字节相同），first_max = power1 + lift（整数存储值相加，分档缩放后不引入二次取整）。None = 不续（槽上限）。
    共用的 W.growth_pair 不改：它写死 119/120，同时服务 29 把诅咒武器。"""
    grow, top = W.growth_pair(kind, target, total, base / W.BASE_SCALE, **kw)
    if lift is None:
        return [grow, top]
    W._require(lift >= 0, f"{kind}: Lv200 合计低于 Lv120 合计（lift={lift}）")
    content_kind, given = top.content
    lo, _ = given["strength"]
    hi = str(int(lo) + int(W.pct(lift)))
    note = f"{top.note}；Lv{FINAL_LEVEL}→{MAX_LEVEL} 再 +{lift:g}%"
    return [grow, replace(top, content=(content_kind, {**given, "strength": (lo, hi)}), maxlvl=MAX_LEVEL, note=note)]


def _continues(eff: Eff) -> bool:
    return eff.learn == FINAL_LEVEL and eff.maxlvl == MAX_LEVEL


def ea_row(slot: int, eff: Eff) -> list[str]:
    """强化词条行。续涨的补足行战力列照成长行形状写（power1 48 → first_max 96）：战力按 learn→c0 插值，
    Lv120 仍取 48（面板战力不变），Lv200 翻倍；只影响面板战力，不影响战斗。"""
    row = W.build_row(W.EA_T, slot, eff)
    if _continues(eff):
        row[3], row[4] = "48", "96"
    return row


def curse_unique_row() -> list[str]:
    """「诅咒」：永续、坏状态、不可驱散、强制付与（短路自身 58 弱体无效）、阵亡不移除。

    叠层上限写 2：持续触发 134 按层数读，上限 1 时 Condition.get_accumulatable() 为 false、层数恒 0，
    R3 的 423 行永远不生效（1.4.1067 首发即如此）。每场只刻 1 层，134 limit=1，不会翻倍。"""
    return W.unique_row(f"paradox_curse_{CURSE_UID}", CURSE_UNIQUE_NAME, CURSE_ICON, "99999999", "2", bad=True)


def unique_ref_problems(table: str, row: list[str], unique_keys: set[str]) -> list[str]:
    """词条行（含分档）引用的固有状态必须存在：461 付与看瞬发内容列、134 持有门控看持续触发列。
    423 的同名列（unique_condition_id）装的是规则码，不是固有状态，不查。"""
    refs = []
    if row[W._col(table, "instant_content", "kind")] == "461":
        refs.append(row[W._col(table, "instant_content", "unique_condition_id")])
    if row[W._col(table, "during_trigger", "kind")] == W.DT_UNIQUE:
        refs.append(row[W._col(table, "during_trigger", "unique_condition_id")])
    return [f"固有状态 {u} 不存在" for u in refs if u not in unique_keys]


def row_capabilities(table: str, row: list[str]) -> list[str]:
    """该行在客户端不 C7050 所需的 capability = 构造运行时（L.required_client_capabilities）∪ 表解析器扩展
    （S.patch_parser_capabilities，只看当前触发模式会解析的块）。wf_client_legality 尚未合并后者：装备两表的 423
    它只报 1047 已有的 gauge-gain-rules-v1、漏掉 equipment-gauge-gain-rules-v1，这里补齐；接线后去重，结果不变。"""
    blocks = wf_describe.layout(table)["blocks"]
    mode_col = int(blocks["precondition1"]) - 1
    mode = (row[mode_col] if mode_col < len(row) else "").strip()
    needed = list(L.required_client_capabilities(table, row))
    for capability in S.patch_parser_capabilities(table, row, blocks, L.TRIGGER_MODE_BLOCKS.get(mode, ())):
        if capability not in needed:
            needed.append(capability)
    return needed


def enhancement_abilities(n: int = 0) -> list[Eff]:
    """强化词条：1→119 成长 + 120 补足到终值，补足行再续涨到 Lv200 合计（槽上限除外）；
    120 级再加直击 8 段、弹射连击 +15（合计 50）与诅咒（这些 learn = max = 120，不续）。
    n=1..3 为衰减分档：增益按比例缩放（含续涨量），诅咒四行原样（代价不随衰减减轻）。"""
    self_ = W.T_SELF
    r = TIERS[n] if n else 1.0
    chosen = (PRE_MY_SELF, {"character_groups": ",".join(tag for _, tag, _ in TAGS)})
    rows: list[Eff] = []
    for kind, total, total200, base in ((*((k, ATK_TOTAL, ATK_TOTAL200, ATK_BASE) for k in DAMAGE_KINDS),
                                         *((k, MULT_TOTAL, MULT_TOTAL200, MULT_BASE) for k in MULT_KINDS),
                                         ("35", CHARGE_TOTAL, CHARGE_TOTAL200, CHARGE_BASE),
                                         ("245", GAUGE_TOTAL, None, GAUGE_BASE),
                                         ("717", UNISON_TOTAL, UNISON_TOTAL200, UNISON_BASE))):
        lift = None if total200 is None else (total200 - total) * r
        rows += _growth_pair(kind, _target(kind), total * r, base * r, lift=lift)
    rows += _growth_pair("32", self_, CHOSEN_TOTAL * r, CHOSEN_BASE * r, lift=(CHOSEN_TOTAL200 - CHOSEN_TOTAL) * r,
                         pre=(chosen,))
    final = dict(learn=FINAL_LEVEL, maxlvl=FINAL_LEVEL)
    topup = COMBO_TOTAL - COMBO_BASE
    combo = _half_up(topup * r)
    seg = hits_segments(0, True)
    rows += [
        Eff("0", W.invoke(hits_key(n, True), hits_program(n, True)), **final,
            note=f"{FINAL_LEVEL} 级：直接攻击变为 {seg} 段（判定额外 +{seg - 1}）"),
        Eff("0", ("226", {"strength": (_count(combo), _count(combo))}), trig=W.trig("6", threshold=_count(1)), **final,
            note=f"{FINAL_LEVEL} 级：每次弹射连击再 +{topup}（合计 +{COMBO_TOTAL}）"),
        Eff("0", W.stat("32", W.T_EXCEPT, CURSE_ATK), **final,
            note=f"【诅咒】自身以外的角色攻击力 {CURSE_ATK}%（引擎下限 -50%）"),
        Eff("0", W.stat("35", W.T_EXCEPT, CURSE_CHARGE), **final, note=f"【诅咒】自身以外的角色技能充能速度 {CURSE_CHARGE}%"),
        # R3（equipment-rules）：开局刻「诅咒」→ 持有期间 423 拦掉自身以外角色的能力类回槽；新行只追加在末尾，已发布行的 slot 不动
        Eff("0", W.unique(CURSE_UID), **final, note="【诅咒】120 级：开局给自身刻上「诅咒」（永续、不可驱散）"),
        Eff("1", ("423", {"target": W.T_EXCEPT, "unique_condition_id": str(GAUGE_MASK)}), trig=W.gate_unique(CURSE_UID),
            **final, note="【诅咒】自身持有「诅咒」时，自身以外的角色无法获得能力和装备的技能槽增加效果（423，规则码 8）"),
    ]
    return rows


def description() -> str:
    return f"{FLAVOR}{DECAY_RULE}"


def _num(x: float) -> str:
    """文案数字：去掉浮点尾巴（230.0 → 230、9.25 → 9.25、-800 → -800）。"""
    return format(round(float(x), 3), "g")


def grow_value(total: float, base: float) -> float:
    """强化成长行在 Lv119 的满值：与 _growth_pair 写进行里的是同一算式（W.growth_pair 以 base/BASE_SCALE 调 W._grow）。"""
    return W._grow(total, base / W.BASE_SCALE)


def echo_delay_frames(code: str) -> int:
    """回响 DSL 根 = 单个 Event Wait(N 帧)（derive_echo 的形状）；覆盖文案里的延迟从这里读。"""
    tree = echo_tree(code)
    top = tree[11][1] if len(tree) == 12 and isinstance(tree[11], list) else []
    W._require(len(top) == 1 and top[0][0] == "Event" and top[0][1][0] == "Wait", f"回响 DSL 根形状漂移：{code}")
    return int(top[0][1][1])


def seconds_text(frame_count: int) -> str:
    """60 帧 = 1 秒；整 0.5 秒写准数（60 → 1秒、90 → 1.5秒），否则「约」+ 一位小数（100 → 约1.7秒）。"""
    if frame_count % 30 == 0:
        return f"{frame_count / 60:g}秒"
    return f"约{frame_count / 60:.1f}秒"


def override_texts() -> dict[str, str]:
    """装备详情覆盖三段文案（本体 / 强化成长 / 终式），数字全部取自出行用的同一批常量与 DSL，不手抄。
    本体段 = 满破魂（觉醒 1→5 不变）；成长段 = 强化 Lv119 时成长行的满值（静态，取代原生逐级数字）+ Lv120 终式与
    Lv121→200 续涨的说明；终式段（补丁放在「强化Lv<c0>」块下，c0 = MAX_LEVEL）= 本体 + 强化 Lv200 的合计与诅咒。
    衰减规则只在装备说明 c7（风味文字）里，不在这里重复。"""
    who = "／".join(label for _, _, label in TAGS)
    label_of = {cid: label for cid, _, label in TAGS}
    types = "／".join(text for _, text in DAMAGE_TYPE_TEXT)
    seg, seg_final = hits_segments(0, False), hits_segments(0, True)
    base = [
        f"攻击力与全部伤害类型（{types}）+{_num(ATK_BASE)}%＆全部独立乘区+{_num(MULT_BASE)}%",
        f"直接攻击判定额外+{seg - 1}次（共{seg}段）",
        f"每次弹射时连击数+{_num(COMBO_BASE)}",
        f"技能充能速度+{_num(CHARGE_BASE)}%＆技能槽上限+{_num(GAUGE_BASE)}%",
        "弱体无效（异常状态与数值降低全部无效）",
        f"攻击力追加合击角色攻击力的{_num(UNISON_BASE)}%",
        f"自身为{who}时攻击力再+{_num(CHOSEN_BASE)}%",
        *(f"自身为{label_of[cid]}时：发动技能{seconds_text(echo_delay_frames(code))}后"
          f"以{ECHO_PERCENT}%的效果回响「{ECHO_SKILL[code]}」" for cid, code, _ in ECHOES),
    ]
    growth = [
        f"强化Lv1→{FINAL_LEVEL - 1}逐级提升，强化Lv{FINAL_LEVEL - 1}时追加：",
        f"攻击力与全部伤害类型+{_num(grow_value(ATK_TOTAL, ATK_BASE))}%"
        f"＆全部独立乘区+{_num(grow_value(MULT_TOTAL, MULT_BASE))}%",
        f"技能充能速度+{_num(grow_value(CHARGE_TOTAL, CHARGE_BASE))}%"
        f"＆技能槽上限+{_num(grow_value(GAUGE_TOTAL, GAUGE_BASE))}%",
        f"合击角色攻击力的追加比例+{_num(grow_value(UNISON_TOTAL, UNISON_BASE))}%",
        f"自身为{who}时攻击力再+{_num(grow_value(CHOSEN_TOTAL, CHOSEN_BASE))}%",
        f"强化Lv{FINAL_LEVEL}进入终式：数值补足、直接攻击共{seg_final}段、"
        f"每次弹射连击合计+{_num(COMBO_TOTAL)}，并解放【诅咒】",
        f"强化Lv{FINAL_LEVEL + 1}→{MAX_LEVEL}继续逐级提升，强化Lv{MAX_LEVEL}时达到下方合计值",
    ]
    final = [
        f"终式合计（含本体）：攻击力与全部伤害类型+{_num(ATK_TOTAL200)}%＆全部独立乘区+{_num(MULT_TOTAL200)}%",
        f"直接攻击判定额外+{seg_final - 1}次（共{seg_final}段）",
        f"每次弹射时连击数合计+{_num(COMBO_TOTAL)}",
        f"技能充能速度合计+{_num(CHARGE_TOTAL200)}%＆技能槽上限合计+{_num(GAUGE_TOTAL)}%",
        f"攻击力追加合击角色攻击力的{_num(UNISON_TOTAL200)}%",
        f"自身为{who}时攻击力合计+{_num(CHOSEN_TOTAL200)}%",
        f"【诅咒·Lv{FINAL_LEVEL}起】自身以外的角色攻击力{_num(CURSE_ATK)}%＆技能充能速度{_num(CURSE_CHARGE)}%",
        # 「战斗开始时」会让这行 58 字超出 57 字上限，用「开局」
        f"【诅咒·Lv{FINAL_LEVEL}起】开局自身获得「{CURSE_UNIQUE_NAME}」（永续、无法驱散）："
        "自身以外的角色无法获得能力和装备的技能槽增加效果",
    ]
    return {OVERRIDE_BASE: OVERRIDE_SEPARATOR.join(base), OVERRIDE_GROWTH: OVERRIDE_SEPARATOR.join(growth),
            OVERRIDE_FINAL: OVERRIDE_SEPARATOR.join(final)}


_OVERRIDE_ID = re.compile(r"desc_override_equipment_(?:enhancement_)?([0-9]+)(?:_final)?")


def override_text_problems(texts: dict[str, str], equipment_row: list[str]) -> list[str]:
    """装备详情覆盖的数据门禁（与 629 说明的「无换行」门禁分开：这里 "\\n" 是行分隔符）。"""
    probs: list[str] = []
    if len(equipment_row) <= 10 or equipment_row[10] != ID:
        probs.append(f"equipment[{ID}] c10（ability_soul_id）须等于 {ID}：本体覆盖键按魂 ID 派生")
    tiers = {tier_id(n) for n in (*TIERS, 4)}
    for key, text in texts.items():
        probs += [f"{key}: {p}" for p in L.equipment_desc_override_key_problems(key)]
        match = _OVERRIDE_ID.fullmatch(key)
        if match and match.group(1) in tiers:
            probs.append(f"{key}: 衰减分档 ID 不得有覆盖键（分档只在战斗装配出现）")
        elif key not in OVERRIDE_KEYS:
            probs.append(f"{key}: 不是 PARADOX 的覆盖键 {OVERRIDE_KEYS}")
        if not isinstance(text, str) or not text:
            probs.append(f"{key}: 文案为空（客户端按未覆盖处理）")
            continue
        for bad, label in ((",", "半角逗号（CSV 分列）"), ("\r", "回车符")):
            if bad in text:
                probs.append(f"{key}: 含{label}")
        lines = text.split(OVERRIDE_SEPARATOR)
        for index, line in enumerate(lines, start=1):
            if not line.strip() or line != line.strip():
                probs.append(f"{key} 第{index}行: 空行或首尾空白")
            if len(line) > OVERRIDE_LINE_LIMIT:
                probs.append(f"{key} 第{index}行: {len(line)} 字超过 {OVERRIDE_LINE_LIMIT}")
            for pattern, label in OVERRIDE_FORBIDDEN:
                if pattern.search(line):
                    probs.append(f"{key} 第{index}行: 含{label}")
    return probs


#: 允许出现英文武器名的格：(表, 列) = 装备名 c1、强化名 c2、魂珠名 c2（「<武器名>魂珠」）。
NAME_CELLS = frozenset({(EQUIPMENT, 1), (ENH, 2), (ITEM, 2)})


def english_name_problems(flat: dict[str, dict[str, list[list[str]]]]) -> list[str]:
    """作者 0928「除了武器名字，其他地方都不要英文的，写悖论」：本生成器产出的格里，英文武器名 NAME 只许出现在
    NAME_CELLS（名字格），说明 / 覆盖文案 / 标签 / 固有状态名等其余格一律写 CLASS_NAME。逻辑路径与 string_id 是小写
    paradox，不受影响。"""
    return [f"{logical.rsplit('/', 1)[-1]}[{key}] c{col}: 名字以外写了英文「{NAME}」，应写「{CLASS_NAME}」：{cell[:40]}"
            for logical, rows_by_key in flat.items() for key, rows in rows_by_key.items() for row in rows
            for col, cell in enumerate(row) if NAME in cell and (logical, col) not in NAME_CELLS]


def retag(row: list[str], tag: str | None) -> list[str]:
    """c5 去掉所有 tag_paradox_*，再按名单补上本角色的标签（保留其它标签与顺序）。"""
    out = list(row)
    tags = [t for t in out[TAG_COLUMN].split(",") if t and not t.startswith(TAG_PREFIX)]
    out[TAG_COLUMN] = ",".join(tags + ([tag] if tag else []))
    return out


def look_texts() -> dict[str, str]:
    """200 级外观三键：第二图标档（"<等级>,<图标>"，单元格内的半角逗号由 CSV 引号包住，客户端 format.csv.Reader
    按引号读成一格——live 的覆盖文案已靠同一机制在单元格里带换行）、蓝金框底图路径与编成槽蓝金框路径。"""
    return {LOOK_TIER2_KEY: f"{MAX_LEVEL},{ICON200}", LOOK_FRAME_KEY: FRAME_BLUEGOLD,
            LOOK_PARTY_FRAME_KEY: PARTY_FRAME_BLUEGOLD}


def look_problems(texts: dict[str, str], enh_row: list[str], files: Iterable[str]) -> list[str]:
    """外观键数据门禁：键由图标路径派生（第二档键挂在强化主表 c4 的图标上）；第二档等级须高于 c3 且不超过 c0；
    值里的路径不带扩展名、不含换行，且对应 PNG 由本武器产出。"""
    probs: list[str] = []
    files = set(files)
    if set(texts) != set(LOOK_KEYS):
        probs.append(f"外观键应恰为 {LOOK_KEYS}，实际 {sorted(texts)}")
    if LOOK_TIER2_KEY != LOOK_TIER2_PREFIX + enh_row[4]:
        probs.append(f"{LOOK_TIER2_KEY}: 键须按强化主表 c4 图标 {enh_row[4]} 派生")
    for key, text in texts.items():
        if not isinstance(text, str) or not text or text != text.strip() or "\n" in text or "\r" in text:
            probs.append(f"{key}: 值为空、带首尾空白或换行")
            continue
        if key.startswith(LOOK_TIER2_PREFIX):
            level, _, path = text.partition(",")
            if not level.isdigit() or not int(enh_row[3]) < int(level) <= int(enh_row[0]):
                probs.append(f"{key}: 第二图标档等级 {level!r} 须在 (c3={enh_row[3]}, c0={enh_row[0]}] 内")
        else:
            path = text
            if "," in path:
                probs.append(f"{key}: 框底图路径含半角逗号")
        if path.endswith(".png") or path + ".png" not in files:
            probs.append(f"{key}: 路径 {path!r} 不是本武器产出的 PNG（逻辑路径不带 .png）")
    tier2_icon = texts.get(LOOK_TIER2_KEY, ",").partition(",")[2]
    if LOOK_FRAME_KEY != LOOK_FRAME_PREFIX + tier2_icon:
        probs.append(f"{LOOK_FRAME_KEY}: 框键须挂在第二档图标上（补丁按缩略图的图标路径查）")
    if LOOK_PARTY_FRAME_KEY != LOOK_PARTY_FRAME_PREFIX + tier2_icon:
        probs.append(f"{LOOK_PARTY_FRAME_KEY}: 编成槽框键须挂在第二档图标上（补丁按编成槽 imagePath 查）")
    if texts.get(LOOK_PARTY_FRAME_KEY) == texts.get(LOOK_FRAME_KEY):
        probs.append(f"{LOOK_PARTY_FRAME_KEY}: 编成槽框须用圆角 72×72 的专用图，不能复用列表框底图（方角不透明）")
    return probs


def atlas_names_from_raw(raw: bytes | None) -> frozenset[str]:
    """``MATERIAL_ATLAS_MAP``（raw deflate 的 AMF3 条目数组，与 wf_weapon_awaken.decode_atlas 同格式）→ 子纹理名集合；
    缺文件 = 空集（任何 c4 都不算已上线）。"""
    if raw is None:
        return frozenset()
    return frozenset(str(entry["n"]) for entry in wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"])


def material_rows(read: W.LiveReader, atlas_names: Iterable[str] | None = None
                  ) -> tuple[dict[str, list[list[str]]], dict[str, str], list[str]]:
    """新材料道具行：克隆五重材料行（10000145 / 10000147），换 c0–c5 与开始时间；c14 类目、c16 售价、c17 稀有度照模板。

    c3/c4 改指 MATERIALS 的重画版只在 c4 已在 live 图集（atlas_names 含它）时做；否则沿用 live 行现有的 c3/c4
    （已上线的行原样，不回退、也不提前指向未上线的子纹理），live 无该行时沿用模板行的（五重材料，已上线）。
    -> (行, {暂缓改指的道具 ID: 原因}, problems)。给了 atlas_names 时，出行的每个 c4 都必须在其中（否则 C8004）。"""
    W._require(not isinstance(atlas_names, (str, bytes)), "atlas_names 须是子纹理名的集合，不是单个字符串")
    ready = None if atlas_names is None else frozenset(atlas_names)
    live_items = read.flat(ITEM)
    out: dict[str, list[list[str]]] = {}
    deferred: dict[str, str] = {}
    problems: list[str] = []
    for iid, template, name, text, thumb, _src, small in MATERIALS:
        W._require(len(text) <= MATERIAL_DESC_LIMIT and "," not in text and "\n" not in text, f"{name} 说明超长或含逗号/换行")
        row = W._template(read, ITEM, template, 23)
        W._require(row[6] == "1" and row[14] == "9", f"item[{template}] 模板列义漂移（c6 强化素材 / c14 类目 9）")
        c3, c4 = thumb, small
        if ready is None or small not in ready:
            current = live_items.get(iid)
            if current:
                W._require(len(current[0]) == 23, f"live item[{iid}] 形状漂移（{len(current[0])} 列 != 23）")
            source = current[0] if current else row
            c3, c4 = source[3], source[4]
            deferred[iid] = ("未提供 live 图集子纹理名（atlas_names）" if ready is None
                             else f"子纹理 {small} 不在 live 图集（先发 wf_weapon_awaken 边 E1）") + \
                ("，沿用 live 行的 c3/c4" if current else f"，沿用模板 item[{template}] 的 c3/c4")
        if ready is not None and c4 not in ready:
            problems.append(f"item[{iid}] c4 {c4} 不在 live 图集 item_icon/sprite_sheet（掉落展示 / 图鉴 C8004）")
        row[0:6] = [f"mod_{SLUG}_{iid}", iid, name, c3, c4, text]
        row[19] = W.START_TIME
        out[iid] = [row]
    return out, deferred, problems


def build(read: W.LiveReader, *, allow_existing: bool = False,
          client_capabilities: Iterable[str] = BASE_CLIENT_CAPABILITIES,
          atlas_names: Iterable[str] | None = None) -> dict[str, Any]:
    """allow_existing=True 供补丁边同步暂存：自有键（5920001 / paradox_hits / tag_paradox_*）已在 live 时不算撞键。

    atlas_names = live item_icon/sprite_sheet 的子纹理名（atlas_names_from_raw）。两件材料的 c3/c4 只在其 c4 已在其中时
    改指重画版；None / 不含 = 沿用 live 行（见 material_rows），该件 c3 图也不出，icons_deferred 列出原因。

    client_capabilities = 接收这批数据的**全部**客户端共有的 capability。默认 1047 基线（未装 equipment-rules）：
    R3 的 423 行（满档与三个分档各一行）报缺 equipment-gauge-gain-rules-v1 进 problems，暂存脚本的 problems == [] 断言即拦下；
    确认所有接收端（含灰服、分享包）都装上补丁 APK 后才传 PATCHED_CLIENT_CAPABILITIES。输出 capabilities = 全部行的需求并集，
    含装备详情覆盖三键的 equipment-description-override-v1（行为型：缺它只是显示原文案，永不进 problems）。"""
    W._require(not isinstance(client_capabilities, str), "client_capabilities 须是 capability 名的集合，不是单个字符串")
    have = frozenset(client_capabilities)
    flat: dict[str, dict[str, list[list[str]]]] = {t: {} for t in FLAT_TABLES}
    problems: list[str] = []
    capabilities: list[str] = []
    text = description()
    W._require(len(text) <= W.DESC_LIMITS["equipment"] and "," not in text and "\n" not in text, "装备说明超长或含逗号/换行")
    W._require(GAUGE_MASK == 8, f"R3 规则码应为 8（只拦能力类回槽），实际 {GAUGE_MASK}")
    W._require(not W.UNIQUE_BASE <= int(CURSE_UID) < W.UNIQUE_BASE + 1000, f"「诅咒」固有状态 {CURSE_UID} 落进诅咒武器段")
    flat[UNIQUE][CURSE_UID] = [curse_unique_row()]

    row = W._template(read, ITEM, "8000101", 23)
    row[0], row[1], row[2], row[3] = f"mod_{SLUG}_{ID}", ID, f"{NAME}魂珠", ICON
    flat[ITEM][ID] = [row]
    row = W._template(read, EQUIPMENT, "8000101", 16)
    W._require(row[2] == "0" and row[8] == "5" and row[11] == "5", "equipment 模板列义漂移")
    row[0], row[1], row[6], row[7], row[9], row[10] = f"mod_{SLUG}", NAME, ICON, text, "false", ID
    flat[EQUIPMENT][ID] = [row]
    materials, icons_deferred, material_problems = material_rows(read, atlas_names)
    flat[ITEM].update(materials)
    problems += material_problems

    # 强化：c0 = 200；名/图/描述/框仍在 120 级切换（200 级图标与蓝金框走下面的外观两键）；强化 status 加 200 键；
    # 商店 10 阶挂诅咒武器类目 6：1–6 阶五重材料、7–10 阶新材料（作者 0928「悖论武器不单独开强化商店」「强化正常有」）
    W._require(len(ENH_DESCRIPTION) <= W.DESC_LIMITS["enhancement"] and "," not in ENH_DESCRIPTION, "强化说明超长或含逗号")
    row = W._template(read, ENH, "5900101", 9)
    row[0:9] = [str(MAX_LEVEL), str(FINAL_LEVEL), NAME120, str(FINAL_LEVEL), ICON120, str(FINAL_LEVEL), ENH_DESCRIPTION,
                str(FINAL_LEVEL), W.START_TIME]
    flat[ENH][ID] = [row]
    caps = [cap for cap, _ in PARADOX_ENH_STAGES]
    W._require(caps == sorted(set(caps)) and caps[-1] == MAX_LEVEL and FINAL_LEVEL in caps,
               f"商店阶段上限须严格递增、含 {FINAL_LEVEL}、末阶 = c0 {MAX_LEVEL}：{caps}")
    W._require(max(map(int, PARADOX_ENH_STATUS_ROWS)) == MAX_LEVEL, "强化数值表缺 c0 键（Lv121+ 空引用崩）")
    for stage, (cap, costs) in enumerate(PARADOX_ENH_STAGES, start=1):
        row = W._template(read, ENH_SHOP, f"5900110{min(stage, SHOP_TEMPLATE_STAGES)}", 50)
        row[0], row[2], row[3] = W.ENH_CATEGORY_KEY, ID, str(stage)
        row[14:22] = W._cost_cells(costs)
        row[22], row[23], row[29], row[30], row[31] = W.START_TIME, "(None)", ID, str(cap), str(W.REQUIRE_AWAKENING)
        flat[ENH_SHOP][f"{ID}{stage:02d}"] = [row]

    effs = abilities()
    soul_rows = [W.build_row(W.SOUL_T, slot, eff) for slot, eff in enumerate(effs)]
    enh = enhancement_abilities()
    ea_rows = [ea_row(slot, eff) for slot, eff in enumerate(enh)]
    for table, rows in ((W.SOUL_T, soul_rows), (W.EA_T, ea_rows)):
        for index, r in enumerate(rows):
            problems += [f"{table}#{index}: {p}" for p in L.client_legality_problems(table, r)]
    flat[SOUL][ID] = soul_rows
    flat[EA][ID] = ea_rows
    for n in (0, *TIERS):
        for final in (False, True):
            flat[CAS][hits_key(n, final)] = [[hits_text(n, final)]]
    for _, code, text in ECHOES:
        W._require("," not in text and "\n" not in text, f"回响说明含半角逗号/换行：{code}")
        flat[CAS][f"paradox_echo_{code}"] = [[text]]
    # 装备详情覆盖三键（本体 / 强化成长 / 终式）；只按满档 ID 出，分档 ID 不出
    overrides = override_texts()
    bad = override_text_problems(overrides, flat[EQUIPMENT][ID][0])
    W._require(not bad, "装备详情覆盖文案不合规：" + "；".join(bad))
    for key, text in overrides.items():
        flat[CAS][key] = [[text]]
    # 200 级外观三键（第二图标档 / 蓝金框 / 编成槽蓝金框）：键按图标路径派生，值指向本武器产出的 PNG
    files = {logical: {"src": str(src), "size": list(size), "required": required}
             for logical, src, size, required in ASSET_FILES}
    for logical, info in files.items():
        W._require(not info["required"] or Path(info["src"]).is_file(), f"缺源图 {info['src']}（{logical}）")
    # 暂缓改指的材料不出它的 c3 图：图与改指同一条边（E2 口径），也不绕过 E1 的作者预览门先写一张没人引用的图
    for iid, *_, thumb, _src, _small in MATERIALS:
        if iid in icons_deferred:
            files.pop(thumb + ".png")
    looks = look_texts()
    bad = look_problems(looks, flat[ENH][ID][0], files)
    W._require(not bad, "200 级外观键不合规：" + "；".join(bad))
    for key, text in looks.items():
        flat[CAS][key] = [[text]]
    # 衰减分档键（补丁按 ID+1000·n 选档）：与满档逐行同构，只换数值 / 629 段数
    for n in TIERS:
        tid = tier_id(n)
        flat[SOUL][tid] = [W.build_row(W.SOUL_T, slot, eff) for slot, eff in enumerate(abilities(n))]
        flat[EA][tid] = [ea_row(slot, eff) for slot, eff in enumerate(enhancement_abilities(n))]
        for table, rows in ((W.SOUL_T, flat[SOUL][tid]), (W.EA_T, flat[EA][tid])):
            for index, r in enumerate(rows):
                problems += [f"{table}[{tid}]#{index}: {p}" for p in L.client_legality_problems(table, r)]
    cas_keys = set(read.flat(CAS)) | set(flat[CAS])
    unique_keys = set(read.flat(UNIQUE)) | set(flat[UNIQUE])
    for table, logical in ((W.SOUL_T, SOUL), (W.EA_T, EA)):
        for key, rows in flat[logical].items():
            for index, r in enumerate(rows):
                problems += [f"{table}[{key}]#{index}: {p}" for p in L.invoke_skill_string_problems(r, cas_keys, table)]
                problems += [f"{table}[{key}]#{index}: {p}" for p in unique_ref_problems(table, r, unique_keys)]
                # capability 门禁：legality 放行装备表 423 后，只有这里挡住它流向未打补丁的客户端
                needed = row_capabilities(table, r)
                capabilities += [c for c in needed if c not in capabilities]
                problems += [f"{table}[{key}]#{index}: 目标客户端缺 capability {c}（未打补丁读到即 C7050）"
                             for c in needed if c not in have]
    # 装备详情覆盖与 200 级外观都是行为型：未装补丁的客户端不读这些键、照旧显示生成文案 / lv120 图标 + 粉框、不崩 ——
    # 只报 capability，不对照 have、不进 problems
    for key in flat[CAS]:
        needed = list(L.required_client_capabilities(L.CUSTOM_ABILITY_STRING_KIND, [key]))
        look = key.startswith(LOOK_PREFIXES)
        W._require(not look or needed == [LOOK_CAPS.get(key)], f"legality 未把外观键 {key} 判为 {LOOK_CAPS.get(key)}")
        for c in needed:
            W._require(c == (LOOK_CAPS.get(key) if look else L.EQUIPMENT_DESC_OVERRIDE),
                       f"custom_ability_string {key} 落进 {c}（本生成器只出装备覆盖与 200 级外观）")
            if c not in capabilities:
                capabilities.append(c)

    live_tags = read.flat(CHARACTER_TAG)
    live_chars = read.flat(CHARACTER)
    designated = {cid: tag for cid, tag, _ in TAGS}
    for cid, tag, label in TAGS:
        flat[CHARACTER_TAG][tag] = [[label]]
        W._require(cid in live_chars, f"character 表缺 {cid}")
    for cid, rows in live_chars.items():
        row = rows[0]
        if cid in designated or any(t.startswith(TAG_PREFIX) for t in row[TAG_COLUMN].split(",")):
            flat[CHARACTER][cid] = [retag(row, designated.get(cid))]
    delete = {CHARACTER_TAG: sorted(k for k in live_tags if k.startswith(TAG_PREFIX) and k not in flat[CHARACTER_TAG])}

    problems += english_name_problems(flat)

    dsl = {hits_program(n, final): hits_dsl(hits_segments(n, final)) for n in (0, *TIERS) for final in (False, True)}
    dsl.update({echo_program(code): echo_tree(code) for _, code, _ in ECHOES})
    programs = {r[W._col(t, "instant_content", "action_path")] for t, logical in ((W.SOUL_T, SOUL), (W.EA_T, EA))
                for rows in flat[logical].values() for r in rows if r[W._col(t, "instant_content", "kind")] == "629"}
    W._require(programs == set(dsl), f"629 行引用的 DSL 与生成的 DSL 不一致：{programs ^ set(dsl)}")
    # 叠层上限门禁（同诅咒武器）：按层数读的本批固有 c4 必须 >1，否则门控静默失效
    acc_rows = [(f"{table}[{key}]#{i}", table, r) for table, logical in ((W.SOUL_T, SOUL), (W.EA_T, EA))
                for key, rows in flat[logical].items() for i, r in enumerate(rows)]
    problems += [p for _, p in W.unique_accumulation_problems(acc_rows, dsl, flat[UNIQUE])]
    tiers = {tier_id(n) for n in TIERS}
    W._require(not tiers & (set(flat[EQUIPMENT]) | set(flat[ITEM])), "分档键不得进 equipment/item 表")
    # C2324：同一 slot 内多行时「成长行后面还有更高 learn」会抛；PARADOX 每个 slot 只一行，续涨也只改行内 max
    for key, rows in flat[EA].items():
        slots = [r[0] for r in rows]
        W._require(slots == [str(i) for i in range(len(rows))], f"{EA}[{key}] slot 须 0..n-1 各一行：{slots}")
        W._require(all(int(r[1]) <= int(r[2]) <= MAX_LEVEL for r in rows), f"{EA}[{key}] learn/max 越界")
    for program, tree in dsl.items():
        for check in (W.dsl_signature_problems, W.colorless_hit_effect_problems, L.action_dsl_element_problems,
                      L.action_dsl_subject_binding_problems, L.action_dsl_lookup_scope_problems,
                      L.action_dsl_hit_area_target_problems):
            problems += [f"DSL {program}: {p}" for p in check(tree)]

    if not allow_existing:
        for logical in (ITEM, EQUIPMENT, SOUL, ENH, EA, ENH_SHOP, UNIQUE, CAS, CHARACTER_TAG):
            clash = sorted(set(flat[logical]) & set(read.flat(logical)))
            W._require(not clash, f"{logical} 键已存在：{clash}")
        for logical in (EQUIPMENT_STATUS, ENH_STATUS):
            W._require(ID not in read.nested(logical), f"{logical} 键已存在：{ID}")

    return {
        "flat": flat,
        "nested": {EQUIPMENT_STATUS: {ID: dict(EQUIPMENT_STATUS_ROWS)}, ENH_STATUS: {ID: dict(PARADOX_ENH_STATUS_ROWS)}},
        "dsl": dsl,
        "files": files,
        # 材料改指重画版所需的图集子纹理（wf_weapon_awaken 边 E1 追加）；不在 atlas_names 里的那件已在 build 内暂缓改指
        "atlas_requires": sorted(small for *_, small in MATERIALS),
        "icons_deferred": icons_deferred,
        "server": _server_delta(flat),
        "delete": delete,
        "problems": problems,
        "capabilities": sorted(capabilities),
        "abilities": effs,
        "enhancement": enh,
    }


def _server_delta(flat: dict) -> dict[str, Any]:
    shop = {}
    for key, rows in flat[ENH_SHOP].items():
        r = rows[0]
        costs = [{"id": int(r[i]), "amount": int(r[i + 1])} for i in (14, 16, 18, 20) if r[i] not in ("", "(None)")]
        shop[key] = {"availableFrom": W.START_TIME, "availableUntil": None, "costs": costs,
                     "enhancementMaxLevel": int(r[30]), "equipmentId": int(r[29]), "groupId": int(r[2]),
                     "requireAwakeningLevel": int(r[31]), "rewards": [], "shopCategoryId": int(r[0]),
                     "stage": int(r[3]), "stock": -1}
    materials = {iid: flat[ITEM][iid][0] for iid, *_ in MATERIALS}
    return {
        "equipment_enhancement_shop.json": shop,
        "equipment_ids.json": [int(ID)],
        "equipment_lookup.json": {ID: {"name": NAME, "rarity": "5", "category": CATEGORY}},
        "equipment_max_level.json": {ID: 5},
        "equipment_element.json": {ID: -1},
        "item_ids.json": [int(ID), *(int(iid) for iid in materials)],
        "item_lookup.json": {iid: r[2] for iid, r in materials.items()},
        # 材料照客户端行：c14 类目、c16 售价、c21 可出售（与五重材料 10000145 / 10000147 的服务端行同形）
        "item_sale.json": {ID: {"category": 5, "sale_price": 500, "sellable": True},
                           **{iid: {"category": int(r[14]), "sale_price": int(r[16]), "sellable": r[21] == "true"}
                              for iid, r in materials.items()}},
    }

# -*- coding: utf-8 -*-
"""季节换装 · 特克托·燕尾礼服（139993 ``super_robot_tailcoat``）套件 kit。

按 ``work/character_packs/seasonal7-20260916/design/tekuto.json``（status=final）落地：

- character 行 c9–c16 语音路由（ChangeSkillFlag → ``<code>_voice_ready``）+ 三层镜像；
- character_text / 技能名与描述（``TEXTS``，tables 重跑同样生效）；
- 队长 6 行、词条 6 键 10 条（设计行逐字写入；同时按 donor+列编辑复算核对）；
- custom_ability_string ``change_skill_super_robot_tailcoat``（ability 1399933#1 c70）与
  custom_ability_power_up_string 同键（潜能 2–6「伤害强化」，克隆官方 change_skill_super_robot）；
  撤掉框架自动克隆、本套件不引用的 ``change_skill_2_super_robot_tailcoat``；
- action_skill 两档（名称/描述/图标/能量/程序/AUTO）与 switched_action_skill ``<code>_voice_ready``
  （= action_skill c7–c23，与 ``wf_seasonal7_voice.switched_rows`` 同列约定）；
- 两棵技能 DSL：按设计 f07 定稿蓝图用官方母本路径拼装 → ``rewrite_effect_refs`` 改写到克隆族 →
  与设计 ``composed_tree`` 类型严格比对 → 母本派生节点核对 → 客户端合法性检查 → 裸树 encode；
- 5 个特效族克隆（codename 布局：cannon / laser_s / laser_l / laser_ll / laser_lll）；
  若 ``fx/tekuto/out/manifest.json`` 存在，按其 {源逻辑路径 → 染色 PNG} 在 png_transform 中换 sheet；
- 详情页技能预览 ``config.end_frame`` 350 → 600（owner=kit）；
- 像素小人（Integrate）：``pixel/REVIEW.md`` 修复轮复核判 tekuto PASS、``pixel/tekuto/{verify,report}.json``
  门禁全过且产物 sha 与 report 一致时，把 ``pixel/tekuto/out/{sprite_sheet,special_sprite_sheet}.png``
  原字节转存储态（仅换小写魔数）写入 ``character/<code>/pixelart/``（owner=pixel）；校验尺寸/alpha/透明像素
  RGBA 与母本一致，atlas/frame/timeline 仍等于母本改前缀后的树（不写元数据）。未通过时保持母本原色（pending）。

语音装包不在 kit 内：由 ``impl/tekuto/voice_merge.py`` 调 ``wf_seasonal7_voice.py pack`` 完成；kit 只在报告里读状态。
不写 live store / assets / .cdn / src；不发布。``evidence/kit-report.json`` 只有在
``impl/tekuto/gates.json`` 全过且指纹与当前包内 kit 产物一致时才写 ``ready-for-review``。

2026-09-16 改版（作者真机试玩后）——**行方案、固有状态、技能树、技能说明改由
``revision-20260916/tekuto/plan.json`` 定**，``design/tekuto.json`` 只再提供身份 / 语音路由 /
能量 / 预览 / 母本基线（design/ 不在本轮可写范围，所以不回写设计稿）。本轮落地：

- 固有状态两个新键：13999301「引擎启动」（上限 99 = 无上限口径）、13999302「重炮展开」（360 帧、1 层）
  + 两张 48×48 图标（PIL 8× 画 + LANCZOS，alpha 沿用官方图标外框）；
- 队长 6 行整体替换（during 134 按「引擎启动」层数给全队雷攻击/技伤，411 自身独立乘区，
  461 刷新「重炮展开」= 延长激光，34 限 6 次，35 全队充能）；
- 词条：能力1#0 技能槽 50%、#1 改 536 开关槽1（锁定 debuff）；能力3#1 改 704 开关槽2
  （扫描范围 + 过载终幕）、新增 #2（461 叠「引擎启动」）与 #3（245 技能槽最大值）；能力 2/4/5/6 不动；
- 技能 DSL：炮台由 ReferencePoint 改挂球（-18 + ["GH",0]）跟随移动、雷达扇形 30°→90°（共鸣 135°）、
  开头 RemoveEventFromOwner/HideEffectFromOwner 做「再次发动=替换不叠加」、终幕 f300→f332 消闪烁、
  收炮 f330→f362 且只在真收炮时放、追加 5 个由「重炮展开」开门的延长槽、
  每段按「引擎启动」层数用 BindConditionAccumulationVariable + vlv 提升倍率（65.0× / 每层 +15.0×）；
- 技能说明精简；custom_ability_string 两个键（槽1 重写、槽2 新增）。

2026-09-16 审查修复轮（11 条：5 major + 6 minor，逐条复现记录在
``revision-20260916/tekuto/fix-log.md``）：

- R-M1 槽2 潜能文案由克隆官方「伤害强化」改为自建「扫描锁定的范围扩大」（与 alv2 的实际落点一致）；
- R-M2 雷达基础半径 400→500，alv2 由 ``{0,200}/{0,0.7854}`` 改为 ``{50,100}/{0.2618,0.7854}``
  （潜能1 就有加成；潜能 1→6 = 550/105° → 600/135°）；
- R-M3 技能说明由「刷新激光的持续时间」改成与行为一致的「以新的一发替换当前激光」；
- R-M4 技能 DSL 根块补 ``ACUnique 13999301``：发动技能 = 引擎启动 +1（倍率成长与队长技的非零基线）；
- R-M5 队长行3/行4 补前置 ``188 ConditionCountUnique(Myself, ≥1, 13999302)``，断开「队友技能 ↔ 重炮展开」自持环；
- R-m6 终幕去掉开关槽2 门 ⇒ 65×/每层 15× 无条件成立（顺带删掉零先例的 ``ConditionalsChangeSkillFlag(2,…)``）；
- R-m7 队长「并提升威力」去掉自加的 6 次上限（改 ``(None)``）；
- R-m8 队长 during 行 ``trigger_limit`` 99 → ``(None)``（固有 c4 仍是 99）；
- R-m9 保留队长 during 411，写进真机验收清单（open_item O10）；
- R-m10 延长槽 392… → 372…、判定寿命 60→70 ⇒ 相邻段重叠 10 帧（消同贴图硬边界闪烁）；
- R-m11 能力1#1 加前置 ``202 OwnerIsMain``，堵住「特克托进合击位点亮主位角色槽1」的串扰。

2026-09-16 第二轮（作者真机再试后，只动本角色，判定区/倍率/段数/图标一个没动）：

- **S14 大激光闪烁修掉**：根因是 ``ActionEffect.fade()`` 让旧光柱再演 ``end`` 序列 17 帧、
  而 ``ActionEffectManager.show()`` 从不按名字去重 ⇒ 上一轮「终幕挪到 f332 > LLL 判定区 f330」
  并没有错开，f332–f347 仍有两根 lll 同屏，延长槽更是每 60 帧重叠 27 帧。
  改法：大激光整段只放**一个**光束实例（挂球 -18 + ``["GH",0]`` + π，寿命 412 帧），
  终幕改成过载闪光（``charge``，非激光族），收炮与延长槽 else 分支用 ``HideEffectFromOwner`` 收一次。
  新门禁 ``beam_overlap_problems``：任一帧同族光柱同屏即红。证据与真机判据见
  ``revision2-20260916/tekuto/flicker.md``；
- 固有「引擎启动」c3 1200 → **99999999**（作者：引擎启动无时间限制）；c4 上限仍 99；
- 文案按 ``revision2-20260916/文案规则-补充.md`` 重写：面板不出现「无上限」，
  「技能强化」条目不写数字与时长（``REV2_TEXT_FIXES``，kit 内带原值断言覆盖 plan）。

2026-09-16 第三轮（作者第三次真机反馈：大激光仍然闪烁 + 「特效缺失」；另附数据改动 D1–D4）：

- **特效 A（闪烁）**：根因**不是**同族两根光柱同屏（第二轮结论），而是官方母本 ``laser_lll``
  的 ``.parts`` 动画层 ``g[2]`` 块 idx 9–11 只画 y∈[153,345]、整根光柱上段 153 单位（×s=6 = 918 px）
  缺图元，而 timeline 的 loop 正好把它圈进循环 ⇒ 412 帧寿命里 102 帧（24.8%、5 Hz）掉炮口。
  修法＝拿同族块 idx 15–17 整体替换（零新素材），由 ``repair_lll_head()`` 在特效族克隆之后调用
  ``lll_repair_tree()``（``--step kit`` 每次都重新克隆，不接进 kit 就会被冲掉）；
- **特效 B（「特效缺失」）**：终幕「过载闪光」用的 ``charge`` 是**空心光环**（parts 矩阵已先铺成
  750×750，亮环只在 r=20–90），``FINALE_FLASH_SCALE = 9`` 的注释把 80px 贴图框当成成品尺寸，
  实际是横跨全屏、**中心全黑**的巨环 ⇒ 炮口那一点上什么都没有。收回官方同素材的档位
  （27 处引用只用 1.0/1.5/2.0）：终幕 9 → 2.0、三段 charge_core 3/4/5 → 1.0/1.5/2.0；
  证据（逐帧渲染 / 播放头展开 / 战场比例对照）见 ``revision3-20260916/fx/forensics.md``；
- **数据 D1**：队长「引擎启动」每层 攻击力 50% → **100%**、技能伤害 100% → **200%**（独立乘区 5% 不变）；
- **数据 D2**：队长「除自身外的雷属性角色发动技能 → 赋予重炮展开(461)」整条**移到能力3**
  （列形按 ability 布局重映射，触发 puller 仍是 ``4 OneOfExceptMyself`` + ``Yellow``）；
  固有「重炮展开」c3 360 → **720**（12 s）；
- **数据 D3**：队长新增两行——自身持有「重炮展开」期间（during ``194 ConditionCountUnique``）
  → 除自身外雷属性角色 技能槽充能速度 +50% / 技能槽最大值 +50%；
- **数据 D4**：队长新增两行——「引擎启动」每层（during ``134``，与 D1 同一计数器）
  → 自身 技能槽充能速度 +5% / 技能槽最大值 +5%。
  ⚠ 作者原话是「自身技能槽 +5%」；**持续侧没有「立即充入(211)」这一 kind**
  （``CommonAbilityContentMasterValue`` 的技能槽族只有 ``3 SkillGaugeCharging`` 与
  ``124 SecondSkillGauge``；瞬发 211 也没有按固有层数倍增的通道——``multiply_trigger``
  只有 None/PowerFlip/SkillInvoke/Fever），故取同族最接近的 ``3``，并在 verify.md 列为待作者确认项。
  全部 rev3 行改动落在 ``REV3_*`` 常量 + ``apply_rev3_*``，与 plan.json 的原值逐格断言。

2026-09-17 第三轮复审修复（审查 6 条，2 major / 4 minor）：

- **R3-M1（major）**：D2 的 12 s 把 5 个延长槽从「基本不触发」变成**每次必定全触发**——
  技能自己在 f0 就刻 1 层「重炮展开」，720 帧覆盖 f372/432/492/552/612 全部门。
  上一轮 verify.md 只把这件事写成「手感」。新增 ``damage_census()`` + S17 门禁，**从树上算**段数与倍率：
  档2 上界 命中 30 → **60 段**、总倍率 **65.0× → 134.0×**、每层「引擎启动」**15.0× → 31.5×**
  （档1 52.0→107.2 / 12.0→25.2）。自校验：census 的「无条件」那一堆逐值等于 plan 声明的 totals。
  同一件事的另一面：f362 的收炮 else 分支（``HideEffectFromOwner`` + ``cannon_cooldown`` 余晖）
  在 720 帧下**恒不执行**，S17 会因此要求 ``laser_200px_end`` 必须在别处上屏；
- **R3-M2（major）**：「技能槽充能速度上限 50%」不是代码事实，客户端常量是 **100%**
  （见 ``REV3_LEADER_NEW`` 上方注释）。按 100% 算 D4 每层 +5% 一路到第 11 层才顶格 ⇒ **不要**按
  「一层就顶格」的结论去改 D4；
- **R3-m3（minor）**：D4 落地成「技能槽**充能速度** +5%」与作者原话「技能槽 +5%」的面板文案不同，
  是需要作者点头的实质偏离，不是纯性能取舍；
- **R3-m4（minor）**：``laser_lll`` 修复逻辑原来 import 自未被 git 跟踪的
  ``work/**/revision3-20260916/fx/lll_head_patch.py``（``.gitignore:56 /work/``）⇒ 那个目录一冻结/归档，
  ``--step kit`` 直接 KitError、整包重建不了。现已把纯函数内联到本文件，
  ``lll_patch_forensic_drift()`` 只在取证副本存在时逐常量比对；
- **R3-m5（minor）**：终幕过载闪光收到 scale 2.0 之后，与第三段 ``charge_core`` 变成同素材、
  同 subject(-18)+同锚点(``AB``)、同 scale、只隔 2 帧 ⇒ 作者报的「特效缺失」很可能第四次复现。
  两处一起改：第三段 charge_core 2.0 → **1.5**（2.0 留给终幕独占，终幕成为全树唯一的最大档）、
  charge_core 寿命 60 → **40**（官方同素材 15–40 帧，顺带收口 O-R3-6，终幕前空出 22 帧全黑）。
  一并把 R3-M1 指出的死码收回来：``cannon_cooldown`` 余晖补到大激光真正结束的
  **f682**，与 f362 的提前收炮**条件相反** ⇒ 一次发动恰好播一次。
  （曾试过给终幕加一层 ``laser_200px_end`` 当炮口爆闪，离线渲染实测它是 252×≥600 的**竖直光柱尾焰**、
  ×7.6 ≈ 1923×≥3600，压在还在开火的大激光上就是又一根同语言光柱同屏 —— 已撤回，见
  ``revision3-20260916/tekuto/final_render.py``。）新增 S16 门禁钉死这些；
- **R3-m6（minor）**：``gates.json`` 的 ``all_pass`` 不含 flow preflight，
  ``impl/tekuto/gates.py`` 现在另出一段 ``publishable``（``can_prepare`` / inspect 是否过期 /
  别家影子键数 / 链锚警告），stdout 也打出来，防止「全绿」被读成「可以发」。

2026-09-17 第四轮（作者真机反馈，落在 ``REV4_*`` + ``revision4-20260917/tekuto/``）：

- **T1**：队长那条「除自身外的雷属性角色发动技能 → 自身技能伤害 +50%」旁边**补一条同触发的
  「自身攻击力 +50%」**，两条都封 **500% 上限**。上限落在触发次数列（leader ``c32``）：
  50% × **10 次** = 500%；面板由客户端自动渲染 ``ability_description_instant_max_strength``
  =「[最大 ::max_strength::&nbsp;]」⇒ 写 10 面板就出「**[最大 + 500 % ]**」，
  满足作者文案规则「有上限就写上限」（取证 ``revision4-20260917/tekuto/review/panel_cap.json``）。
  新行是源行的逐格副本、**只改 content kind 34(SkillDamage) → 32(AttackPoint)**，
  所以「同触发」是结构保证而不是口头承诺。
- **T2**：能力3 里那条 461「赋予自身重炮展开」的前置写反了——上一轮从队长搬过来时带着
  「自身已持有**重炮展开**」（自持环，冷启动后永远开不了），与作者描述不符。
  改成「自身处于**引擎启动**状态时」：**只把前置 uid ``c19`` 换成 13999301**，
  前置 kind 仍是 188 ``ConditionCountUnique``（≥1 实例 = 持有），列形与官方 3 行先例逐格相同
  （``['188','0','','100000','100000','']``），零 C7050 风险。
  能力面板文案由客户端按行自动生成（本角色没有 ``desc_override_*``），行改完文案同步改完。

2026-09-17 第五轮（作者：「能力2改为，自身对引擎启动每上升1，自身攻击力+50%，技能伤害+50%，
不设置上限」，落在 ``REV5_*``）：

- **T3**：能力2 从两条**瞬发**行（技能发动限 3 次 → 自身攻击力 50%→100% 最大 300%、
  技能伤害 25%→50% 最大 150%）整键换成两条**持续**行，按「引擎启动」层数成长、不封上限。
  必须用 during_trigger **134**：194 ``ConditionCountUnique`` 数的是固有**实例个数**
  （461 叠层固有恒为 1）⇒ 只能做「持有就给固定值」；134 才按层数算
  （记忆卡 ``wf-unique-cap-none-trap``）。
  供体 = live ``ability[1399943]#3/#4``（本批雷吉斯能力3，1.4.883 起在线，同样是
  「134 + 自身固有 uid + target 0 Myself + 次数上限 ``(None)``」），本行只改
  ``c0/c1/c2``（同键头部）、``c104``（uid）、``c109``（内容 kind）、``c113/c114``（强度）。
- **顺带修掉一个潜伏 bug**：``_fill_sentinels`` 原来两张表都读 ``c3`` 当触发模式，但
  ability 的模式列是 ``c5``（``c3`` 是 awake_kind）。到第四轮为止本 kit 只产瞬发行
  （``c3`` 与 ``c5`` 同为 ``'0'``）所以一直没暴露；第五轮的 during 行 ``c3='0'`` 而 ``c5='1'``，
  照旧读 ``c3`` 会把哨兵补到 ``c39`` 而不是 ``c85``，出一个 live 里零先例的行形。

2026-09-27 第七轮（平衡第三批，``wf_balance_20260927c_tekuto``；落在 ``BALANCE_C_*``）：

- 成长复核：队长引擎逐层行从第二批的 1/10 改回 4/5（#0 雷队攻 80%、#1 雷队技伤 160%）、
  2/3（#2 独立乘区 3.5%、#10/#11 自身攻/技伤 35%）、7/10（#8 半血持重炮每 120 帧 70%）；
- 技能倍率撤封顶（担任队长且雷共鸣时）：能力1 追加旗号 3 开关行（kind 705，前置 42 仅队长 + 雷≥6，
  c70 = ``CHANGE_SKILL_LEADER_KEY``）；两档技能树 11 处「Bind 起到块尾」整段包进
  ``ConditionalsChangeSkillFlag(3, 开支 Bind 上限 99, 关支 = 第二批原段)``（:func:`balance_c_skill_tree`，
  叠在 ``final_tree`` 之后）；强化条目 ``CHANGE_SKILL_LEADER_TEXT`` 点名『多重爆破·礼装重炮』。技能说明保持第二批
  「（最多10层）」（主会话 2026-09-27 口径：强化后的效果只写在强化条目里，技能说明不重复）。
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import zlib
from pathlib import Path
from typing import Any

import wf_seasonal7_specs as S

KEY = "tekuto"
CID = "139993"
CODE = "super_robot_tailcoat"
TEMPLATE_CODE = "super_robot"
ELEMENT = 2

CHAR = "master/character/character.orderedmap"
TEXT = "master/character/character_text.orderedmap"
ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
ACTION = "master/skill/action_skill.orderedmap"
SWITCHED = "master/skill/switched_action_skill.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
CAPS = "master/string/custom_ability_power_up_string.orderedmap"
PREVIEW = f"character/{CODE}/battle/character_detail_skill_preview.battle.amf3.deflate"
TEMPLATE_PREVIEW = f"character/{TEMPLATE_CODE}/battle/character_detail_skill_preview.battle.amf3.deflate"

CHANGE_SKILL_KEY = f"change_skill_{CODE}"                 # 开关槽 1（能力1 kind 536）＝锁定 debuff
CHANGE_SKILL2_KEY = f"change_skill_2_{CODE}"              # 开关槽 2（能力3 kind 704）＝扫描范围 + 过载终幕
# 2026-09-27 平衡第三批：开关槽 3（能力1 kind 705，仅队长 + 雷共鸣）＝技能倍率的「引擎启动」层数不封顶。
# 键名必须以 change_skill_<code> 开头（批次暂存脚本 splice 的命名空间断言），所以不用 change_skill_3_<code>。
CHANGE_SKILL_LEADER_KEY = f"change_skill_{CODE}_leader"
CHANGE_SKILL_LEADER_TEXT = "强化『多重爆破·礼装重炮』：威力随「引擎启动」层数持续提升"
# 潜能 2–6 文案：槽1 的潜能插值吃在雷抗/技伤抗性降低上 ⇒ 用官方 change_skill_2_super_robot
# 「对敌人的雷属性抗性降低效果强化」；槽2 追加的是过载终幕伤害 ⇒ 用官方 change_skill_super_robot「伤害强化」。
# 槽1 的潜能插值（alv_）全落在雷抗降低 / 技伤抗性降低的时长与强度上 ⇒ 克隆官方 change_skill_2_super_robot 的原行字节。
# 槽2（审查 R-M1 修复）：alv2 只落在雷达 Sector 的半径与角度上，官方 37 个潜能文案里没有「范围」类，
# 所以自建 5 级同文案的内层 orderedmap（先例 = live change_skill_lady_summoner_campus_dragon 也是自建行）。
# 第二轮文案规则（``revision2-20260916/文案规则-补充.md``，优先级最高）：
# ① 没有上限就什么都不写（面板不许出现「无上限」，也不许写「可无限叠加」「可累计」之类替代说法）；
# ② 由 ChangeSkillFlag(536/704) 驱动的「技能强化」条目只写强化了什么，不写数字、不写秒数。
# plan.json 不在本轮可写范围 ⇒ 在 kit 里对 plan 的 ``texts.custom_ability_string[].new`` 做带原值断言的覆盖。
REV2_TEXT_FIXES = {
    CHANGE_SKILL_KEY: {
        "plan": "强化『多重爆破·礼装重炮』：对扫描锁定的敌人赋予可累计的雷属性抗性降低与技能伤害抗性降低",
        "fixed": "强化『多重爆破·礼装重炮』：对扫描锁定的敌人追加「雷属性抗性降低」与「技能伤害抗性降低」效果",
        "reason": "规则①：「可累计的」是「可无限叠加」的同义替代，去掉；规则②：只说强化了什么，无数字无时长",
    },
}
POWER_UP_SOURCES = {CHANGE_SKILL_KEY: f"change_skill_2_{TEMPLATE_CODE}"}
POWER_UP_TEXTS = {CHANGE_SKILL_KEY: "对敌人的雷属性抗性降低效果强化"}
POWER_UP_CUSTOM = {CHANGE_SKILL2_KEY: "扫描锁定的范围扩大"}
POWER_UP_LEVELS = ("2", "3", "4", "5", "6")
VOICE_READY_KEY = f"{CODE}_voice_ready"
PREVIEW_END_FRAME = 600

UNIQUE = "master/character/unique_condition.orderedmap"
UNIQUE_DONOR = "1"                                        # 官方 unique_wind_spgirl_1anv「神速剑技」(自身增益叠层)
UID_ENGINE = "13999301"
UID_CANNON = "13999302"
UNIQUE_ICON_DIR = "battle/common/unique_condition"
UNIQUE_ICON_FRAME_DONOR = f"{UNIQUE_ICON_DIR}/unique_wind_spgirl_1anv.png"
UNIQUE_META = {
    UID_ENGINE: {"string_id": f"unique_{CODE}_engine", "name": "引擎启动", "duration": "99999999", "max": "99"},
    UID_CANNON: {"string_id": f"unique_{CODE}_cannon", "name": "重炮展开", "duration": "720", "max": "1"},
}
# 第二轮（作者：「引擎启动无时间限制」）：plan.json 写的是 1200 帧（20s），改永续。
# c3=持续帧，官方 112 行里 99999999 是压倒性众数（67 行，含本行 donor `1` 神速剑技），
# 客户端对 ≥99999 画右上「∞」永续徽标（记忆卡 wf-unique-cap-none-trap）；c4 上限仍是 99
# （写 (None) 会被读成 1 层，整套叠层机制塌方）。plan 不在本轮可写范围 ⇒ 在 kit 里做带原值断言的覆盖。
REV2_UNIQUE_FIXES = {
    UID_ENGINE: {"col": 3, "plan": "1200", "fixed": "99999999",
                 "reason": "作者第二轮：引擎启动无时间限制 ⇒ 永续（c4 上限保持 99）"},
}
# 第三轮 D2：「重炮展开」6 s → 12 s。c4 上限仍 1（开关型固有，只要「在不在」不要层数）。
REV3_UNIQUE_FIXES = {
    UID_CANNON: {"col": 3, "plan": "360", "fixed": "720",
                 "reason": "作者第三轮 D2：重炮展开持续时间提升到 12 s（720 帧）"},
}
UNIQUE_FIXES = {**REV2_UNIQUE_FIXES, **REV3_UNIQUE_FIXES}
if set(REV2_UNIQUE_FIXES) & set(REV3_UNIQUE_FIXES):                    # 同一 uid 两轮都改 ⇒ 必须手工合并
    raise RuntimeError("REV2/REV3 unique fixes overlap; merge them explicitly")
UNIQUE_ICON = {uid: f"{UNIQUE_ICON_DIR}/{meta['string_id']}.png" for uid, meta in UNIQUE_META.items()}

DESIGN_REL = f"{S.BATCH_DIR}/design/{KEY}.json"
REVISION_DIR = f"{S.BATCH_DIR}/revision-20260916/{KEY}"
REVISION_REL = f"{REVISION_DIR}/plan.json"
REVISION2_DIR = f"{S.BATCH_DIR}/revision2-20260916/{KEY}"
REVISION3_DIR = f"{S.BATCH_DIR}/revision3-20260916"
REV3_FX_DIR = f"{REVISION3_DIR}/fx"                       # forensics.md / lll_head_patch.py 落点
REV3_LLL_PARTS = f"battle/effect/skill_unique/{CODE}/laser_lll/enemy_shot_laser_lll_yellow.parts.amf3.deflate"
# 第二轮定稿树落在 revision2 目录：revision-20260916/ 是上一轮（live 1.4.877）的历史证据，保持原样，
# 正好给 S14 的负向对照当「修复前」样本（见 flicker.md §证据3）。
FINAL_TREE_REL = REVISION2_DIR + "/final_" + CODE + "_{level}.json"
FX_MANIFEST_REL = f"{S.BATCH_DIR}/fx/{KEY}/out/manifest.json"
GATES_REL = f"{S.BATCH_DIR}/impl/{KEY}/gates.json"
PIXEL_REL = f"{S.BATCH_DIR}/pixel/{KEY}"
PIXEL_REVIEW_REL = f"{S.BATCH_DIR}/pixel/REVIEW.md"
PIXEL_REVIEW_HEADING = "修复轮复核"
# sheet → (atlas, 该 sheet 的 frame/timeline)；只写 sheet，元数据保持 assets 复制的母本（前缀已改写）
PIXEL_SHEETS = {
    "sprite_sheet": ("sprite_sheet.atlas.amf3.deflate", ("pixelart.frame.amf3.deflate", "pixelart.timeline.amf3.deflate")),
    "special_sprite_sheet": ("special_sprite_sheet.atlas.amf3.deflate",
                             ("special.frame.amf3.deflate", "special.timeline.amf3.deflate")),
}
VOICE_RUN = "take1"
KIT_SOURCE = Path(__file__).resolve()

# ---- 文案（tables 读 TEXTS 重写 character_text 与 action_skill c0/c1）
# 设计稿原描述（128 字）；作者改版要求「技能描述不再写太复杂省略一下」⇒ _DESC 为改版短文，
# build 时断言设计稿里仍是 _DESIGN_DESC（防止设计稿被别人改了却没人发现）。
_DESIGN_DESC = ("锁定距离最近的敌人，在施放位置架设重炮（炮台固定在原地，发射期间可照常弹射）：赋予自身技能伤害提升效果；"
                "对炮口前方射线上的敌人赋予雷属性抗性降低效果，雷达扫描到炮台附近的敌人时发射导弹追击；"
                "随后朝锁定方向持续发射充能激光炮，光束分4段逐渐变粗，对命中的敌人造成雷属性伤害")
_R1_DESC = ("扫描并锁定周围的敌人，架设跟随自身移动的重炮，朝锁定方向持续发射充能激光，"
            "光束分4段逐渐变粗；再次发动技能会刷新激光的持续时间")
# 审查 R-M3：上一行（改版第一轮）写「刷新激光的持续时间」，实际行为是杀掉旧发全部段后从第 1 段重排
# ⇒ 已打到 LLL 的光柱会被换回 S 档，是净 DPS 损失，与字面承诺相反。改成与行为一致的说法，
# 并补上 R-M4 新增的「发动即引擎启动 +1」（伤害倍率的真来源，玩家必须知道）。
_DESC = ("锁定周围的敌人，架起跟随自身移动的重炮，朝锁定方向发射逐段变粗的充能激光；"
         "发动时「引擎启动」+1，威力随其层数提升；再次发动会以新的一发替换当前激光")
# S18（作者 2026-09-21「取消技能释放后的后摇」）：根块的 StopBall 已整条删掉 ⇒ 面板追加一句。
# 与本批黑 `outlaw_panther_moon` 的 live 文案逐字同一句，只是本角色整条说明用「；」分隔。
# plan.json（revision-20260916/tekuto）不在本轮可写范围 ⇒ 沿用本 kit 既有做法：
# 对 plan 的 `texts.action_skill_desc.new` 仍按 `_DESC` 断言，落表时用下面这条带后缀的。
REV7_NO_ENDLAG_SUFFIX = "；释放技能后不再进入硬直，可立即行动"
_DESC_NO_ENDLAG = _DESC + REV7_NO_ENDLAG_SUFFIX
# 2026-09-27 平衡第二批：技能 DSL 的「引擎启动」层数贡献封顶 10 层（下方 ENGINE_CAP）⇒ 说明写出上限
# （seasonal7 第二轮文案规则 1 第三条「有上限的才写上限」；第二批口径 D「上限写（最多N层）」）。
# _DESC_NO_ENDLAG 保留为改前文案（wf_tekuto_no_endlag_revision 的对照锚点）；落表用 _DESC_BALANCE_B。
BALANCE_B_DESC_ANCHOR = "威力随其层数提升"
BALANCE_B_DESC_CAP = "（最多10层）"
if _DESC_NO_ENDLAG.count(BALANCE_B_DESC_ANCHOR) != 1:        # 锚点必须唯一，替换才不会漏/叠
    raise RuntimeError("tekuto skill description anchor for the batch-b cap clause is not unique")
_DESC_BALANCE_B = _DESC_NO_ENDLAG.replace(BALANCE_B_DESC_ANCHOR, BALANCE_B_DESC_ANCHOR + BALANCE_B_DESC_CAP)
# 2026-09-27 平衡第三批（U8）：担任队长且雷共鸣时技能倍率不封顶（旗号 3 分支，见 balance_c_skill_tree）。
# 主会话 2026-09-27 技能强化文案口径（作者「技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述
# 强化后的效果」）：强化后的不封顶只写在强化条目 CHANGE_SKILL_LEADER_TEXT（能力 1 面板），技能说明只写技能本体
# ⇒ 第三批落表文案 == 第二批 _DESC_BALANCE_B（本体上限「（最多10层）」照写）。_DESC_BALANCE_C 保留为落表入口名。
if _DESC_BALANCE_B.count(BALANCE_B_DESC_CAP) != 1:
    raise RuntimeError("tekuto skill description cap clause is not unique")
_DESC_BALANCE_C = _DESC_BALANCE_B
TEXTS = {
    "profile": ("被朋友们拉去参加舞会的机人青年，换上了黑黄配色的燕尾礼服，胸前别着系黄丝带的白玫瑰。"
                "为了保护大家，他把重炮和导航无人机也带进了会场——虽然大家都说那样一点都不优雅。"),
    "skill1": "多重爆破·礼装重炮",
    "desc1": _DESC_BALANCE_C,
    "skill2": "多重爆破·礼装重炮＋",
    "desc2": _DESC_BALANCE_C,
    "cv": "AI 合成配音",
}
SPEC = {
    "extra_keys": {
        CAS: (CHANGE_SKILL_KEY, CHANGE_SKILL2_KEY, CHANGE_SKILL_LEADER_KEY),
        CAPS: (CHANGE_SKILL_KEY, CHANGE_SKILL2_KEY),
        SWITCHED: (VOICE_READY_KEY,),
        UNIQUE: (UID_ENGINE, UID_CANNON),
    },
}

# ---- 特效族（design.effects.clone；codename 布局）
CANNON_SRC = "battle/effect/skill_unique/super_robot"
CANNON_FX = ["super_robot_radar", "super_robot_radar_hit", "super_robot_missile", "super_robot_missile_hit",
             "super_robot_laser_100px", "super_robot_laser_100px_end", "super_robot_laser_200px",
             "super_robot_laser_200px_end"]
LASER_FAMS = ("s", "l", "ll", "lll")


def laser_src(fam: str) -> str:
    return f"battle/effect/enemy_general/enemy_shot_laser_{fam}/enemy_shot_laser_{fam}_yellow"


FAMILIES = [(CANNON_SRC, "cannon", CANNON_FX)] + [
    (laser_src(f), f"laser_{f}", [f"enemy_shot_laser_{f}_yellow"]) for f in LASER_FAMS]


class KitError(RuntimeError):
    pass


# ================================================================ 改版方案（plan.json）

PLAN_CACHE: dict[str, Any] = {}


def load_revision_plan(root: Path) -> dict:
    """``revision-20260916/tekuto/plan.json``：本轮行方案 / 固有状态 / 技能树参数的唯一真源。

    设计稿 ``design/tekuto.json`` 仍然是身份、语音路由、能量、预览与母本基线的来源，但队长/词条/
    技能树/技能说明按本方案覆盖（``design/`` 不在本轮可写范围，不回写设计稿）。
    """
    path = root / REVISION_REL
    plan = json.loads(path.read_text(encoding="utf-8"))
    if (plan.get("key"), str(plan.get("cid")), plan.get("code")) != (KEY, CID, CODE):
        raise KitError(f"revision plan identity mismatch: {plan.get('key')}/{plan.get('cid')}/{plan.get('code')}")
    if plan.get("schema") != "s7-revision-plan/1":
        raise KitError(f"revision plan schema unexpected: {plan.get('schema')}")
    PLAN_CACHE["plan"] = plan
    PLAN_CACHE["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return plan


# ================================================================ 技能树（设计 f07 定稿蓝图，母本路径）

PI = math.pi
SR_SRC = f"{CANNON_SRC}/super_robot_"                       # 官方 cannon 族（rewrite 后 → <code>/cannon/）
NOTICE = "battle/effect/enemy_unique/enemy_laser_notice/laser_notice"   # 直引，不克隆
CHARGE = "battle/effect/skill_general/decoration/charge"                # ResolveByElement 直引

# ---- 收炮余晖宽度（审查 minor 修复，2026-09-16）
# 官方 super_robot_2：laser_100px(_end) 与 laser_200px(_end) 是同一组贴图，parts 根 s=1；
# 主光柱层 g10 = 106px 宽贴图 'e' 纵向镜像平铺（s=1 时宽约 107px），DSL 配对为
# Some(1)↔Rect100、Some(2)↔Rect200，即 Some(k) ≈ 100k px（200px 变体只把火花层 g12 预缩 0.5）。
# 设计把 200px_end 的 Some(1) 当成 200px，写成 Some(3.8)，实际约 406px，只有 LLL 光束 Rect760 的一半；
# 设计本意是「≈760 宽收炮余晖」，按官方 k = Rect/100 取 7.6（约 812px，与官方 107/100 同比例外扩）。
LLL_RECT_WIDTH = 760
COOLDOWN_SCALE = 7.6
# 设计 JSON 不在 kit 写入范围；这里对设计 composed_tree 做单节点、带原值断言的修正（设计同步为 7.6 后自动变 no-op）
DESIGN_TREE_FIXES = (
    {"id": "review-minor-cannon-cooldown-width", "command": "ShowEffect", "label": "cannon_cooldown", "arg": 12,
     "design": ["Some", [{"min": 3.8, "max": 3.8}]], "fixed": ["Some", [{"min": COOLDOWN_SCALE, "max": COOLDOWN_SCALE}]],
     "reason": "laser_200px_end Some(k)≈100k px（官方 Some(1)↔Rect100 / Some(2)↔Rect200）；3.8≈406px 只有 LLL Rect760 一半，"
               "改 7.6 与设计本意「≈760 宽」一致"},
)
E = 0                                   # FindNearSubjects 的绑定 id（最近敌人）
BALL = -18                              # 炮台改挂球：跟随自身移动（改版 A1）
GH = ["GH", E]                          # 朝 FindNearSubjects 命中的敌人（球上不能用 CD，getDirCD 会 throw）

# 自身技能伤害（母本原值，template_derivation_problems 逐值核对；改版未动）
SELF_SD = {"2": (600, 0.85, 1.0), "1": (480, 0.65, 0.65)}

# ---- S18「取消后摇」（作者 2026-09-21）：本树不许有任何把球固定住的命令。
#: 官方母本 ``super_robot_{1,2}`` 根块那条 StopBall 的原形态（140 帧 + ``Stop``＝球停住不再恢复，
#: 且母本根头 ``tree[1]=2`` STOP 还会抢走球的移动权）。只作对照与漂移核对，**不再抄进我们的树**。
TEMPLATE_STOPBALL = [-18, 140, ["Stop"], ["AB"], 0]
#: 会把球固定住的 DSL 命令名；``ball_hold_problems`` 见到任意一条就红。
BALL_HOLD_COMMANDS = ("StopBall", "SuppressBallActivity")

# 事件名 / 特效名（改版 S9）：同名才能被 RemoveEventFromOwner / HideEffectFromOwner 一次清掉
EV_CANNON = "tekuto_cannon"
FX_BEAM = "tekuto_beam"                 # S/L/LL 三段：每段自己的光束，挂各自判定区（官方 dark_matter 写法）
FX_BEAM_MAIN = "tekuto_beam_lll"        # 大激光：整段只有这一个实例（第二轮 S14 消闪烁）
FX_FINALE = "tekuto_finale"
EV_KEEP = ("missile_cancel", "missile_event")
# 官方 enemy_shot_laser_* 的 timeline（克隆逐字节同源）：start/loop/end 三序列，
# `end` 是 `once`，寿命由 ActionEffect.fade() 设为 getSequenceTotalFrames("end")。
# 判定区一终止 → fade()，贴图还要再演这么多帧才消失——这就是第二轮闪烁的根因载体。
#   laser_s   : start 1-5 / loop 6-18 / end 19-26 ⇒ end 8 帧
#   laser_l/ll/lll: start 1-6 / loop 7-18 / end 19-35 ⇒ end 17 帧
# 复算命令见 revision2-20260916/tekuto/flicker.md §证据1（gates 里按包内 timeline 实测复核）。
LASER_END_FRAMES = {"s": 8, "l": 17, "ll": 17, "lll": 17}

# 段名 → (帧, 光束宽, 判定绑定 id, laser 族, charge_core 缩放, 震屏)
# 第三轮（forensics.md §3）：charge 是**空心光环**——parts 根 s=1，两张 80×80 射线贴图被 parts
# 矩阵先铺成 750×750，真正不透明的只有 r=20–90 那一圈，中心全透明。所以 scale 不是「80px×k」，
# 而是「750px×k」；旧值 3/4/5/9 分别是 2250/3000/3750/6754 px 的包围盒，炮口那一点上什么都没有。
# 收回官方同素材用过的全部档位（1.0/1.5/2.0），逐段递增。
STAGES = (("s", 90, 100, (30, 31, 32), "s", None, 2),
          ("l", 150, 320, (33, 34, 35), "l", 1.0, 2),
          ("ll", 210, 490, (36, 37, 38), "ll", 1.5, 2),
          ("lll", 270, LLL_RECT_WIDTH, (39, 40, 41), "lll", 1.5, 3))
# 审查 R3-m5（2026-09-17）：第三段 charge_core 原本也是 scale 2.0、同素材、同 subject(-18)+同锚点["AB"]、
# 同角度，与终幕只隔 2 帧（f270+60=330 → 终幕 f332）⇒ 终幕在屏幕上就是「第三段的环又接着演了一会儿」，
# 作者报的「特效缺失」有很大概率第四次复现。三处一起改，让终幕成为**唯一**可区分的那一下：
#   ① 第三段 charge_core 2.0 → 1.5（档位仍在官方 1.0/1.5/2.0 内，且 1.0→1.5→1.5 仍单调不降）；
#   ② charge_core 寿命 60 → CHARGE_CORE_LIFETIME=40（官方同素材 15–40 帧，顺带收口 O-R3-6），
#      第三段 f270–310 ⇒ 终幕前有 22 帧全黑空档，不再首尾相接；
#   ③ 终幕不再加第二层：试过 ``super_robot_laser_200px_end``，离线渲染实测它是 252×≥600 的
#      **竖直光柱尾焰**（×7.6 ≈ 1923×≥3600），压在还在开火的大激光上 = 又一根同语言光柱同屏，
#      已撤回；它改到 f682（大激光真正结束）当收炮余晖，那才是它的设计用途（R3-M1 的死码一并收回）。
CHARGE_CORE_LIFETIME = 40
OFFICIAL_CHARGE_LIFETIME_MAX = 40   # forensics §3.3：官方同素材 27 处引用寿命 15–40 帧
FINALE_FRAME, FINALE_WIDTH, FINALE_IDS, FINALE_LIFETIME = 332, 900, (42, 43, 44), 30
# 第二轮 S14：终幕不再放第二根 lll 光柱（同贴图叠在还在 fade 的 LLL 上＝拍频闪烁），
# 改成挂球的过载闪光（ResolveByElement charge，与光束不同族）＋原有震屏；判定区/倍率/段数一个没动。
# 第三轮：9 → 2.0（= 官方同素材 27 处引用里的最大值，13 处先例）；作者报的「特效缺失」就是这一条。
FINALE_FLASH_SCALE = 2.0
# 官方 all_action_scan：同素材 charge 共 27 处引用，scale ∈ {2.0×13, 1.5×10, 1.0×4}，最大 2.0。
OFFICIAL_CHARGE_SCALE_MAX = 2.0
OFFICIAL_CHARGE_SCALES = (1.0, 1.5, 2.0)
# plan.json / 第二轮的原值（带原值断言的覆盖：plan 改了就报错，不静默漂移）
REV3_CHARGE_SCALE_FIXES = {
    "charge_core:l": {"plan": 3, "fixed": 1.0},
    "charge_core:ll": {"plan": 4, "fixed": 1.5},
    "charge_core:lll": {"plan": 5, "fixed": 1.5},     # 审查 R3-m5：2.0 → 1.5，把 2.0 留给终幕独占
    "tekuto_finale": {"plan": 9, "fixed": FINALE_FLASH_SCALE},
}


def charge_scale_problems(plan: dict) -> list[str]:
    """第三轮 §3.3：charge 系 scale 必须落在官方同素材档位，且与 plan 的原值可追溯。"""
    probs = []
    for (name, _frame, _w, _ids, _fam, scale, _shake) in STAGES:
        if scale is None:
            continue
        if scale not in OFFICIAL_CHARGE_SCALES:
            probs.append(f"charge_core[{name}] scale {scale} 不在官方同素材档位 {OFFICIAL_CHARGE_SCALES}")
    if FINALE_FLASH_SCALE not in OFFICIAL_CHARGE_SCALES or FINALE_FLASH_SCALE > OFFICIAL_CHARGE_SCALE_MAX:
        probs.append(f"终幕 charge scale {FINALE_FLASH_SCALE} 超出官方档位 {OFFICIAL_CHARGE_SCALES}")
    plan_ha = {h["id"]: h for h in plan["skill_dsl"]["hitareas"]}
    for name, fix in REV3_CHARGE_SCALE_FIXES.items():
        if not name.startswith("charge_core:"):
            continue
        got = plan_ha.get(f"HA_{name.split(':', 1)[1]}", {}).get("charge_core_scale")
        if got not in (fix["plan"], fix["fixed"]):
            probs.append(f"plan {name} charge_core_scale {got!r} 既不是原值 {fix['plan']!r} 也不是修正值 "
                         f"{fix['fixed']!r}；方案被改过，先核对再改 kit")
    stage_scales = {name: scale for (name, _f, _w, _i, _fam, scale, _s) in STAGES if scale is not None}
    for name, fix in REV3_CHARGE_SCALE_FIXES.items():
        if name.startswith("charge_core:") and stage_scales.get(name.split(":", 1)[1]) != fix["fixed"]:
            probs.append(f"STAGES {name} scale {stage_scales.get(name.split(':', 1)[1])!r} != rev3 {fix['fixed']!r}")
    if FINALE_FLASH_SCALE != REV3_CHARGE_SCALE_FIXES["tekuto_finale"]["fixed"]:
        probs.append("FINALE_FLASH_SCALE 与 REV3_CHARGE_SCALE_FIXES 不一致")
    # 审查 R3-m5：终幕必须是**全树唯一**的最大档，且严格大于所有 charge_core
    if any(scale >= FINALE_FLASH_SCALE for scale in stage_scales.values()):
        probs.append(f"终幕 scale {FINALE_FLASH_SCALE} 未严格大于 charge_core {stage_scales} "
                     f"—— 同素材同锚点同大小，终幕在屏幕上读不出来（R3-m5）")
    if CHARGE_CORE_LIFETIME > OFFICIAL_CHARGE_LIFETIME_MAX:
        probs.append(f"charge_core 寿命 {CHARGE_CORE_LIFETIME} > 官方同素材上限 {OFFICIAL_CHARGE_LIFETIME_MAX}")
    return probs
COOLDOWN_FRAME = 362
# 审查 R-m10：上一轮 5 个延长槽帧距 60 == 判定寿命 60 ⇒ 段段首尾相接，判定区一结束特效就 fade
# （ActionEffect.as:216-222），同一张 lll 贴图最多 6 处硬边界，作者报的闪烁会在延长段复现。
# 改为寿命 70 / 帧距 60 ⇒ 相邻段重叠 10 帧；命中上限仍 Some(6)、最小命中间隔 10 ⇒ 伤害不变。
# 首槽 392→372：仍 > 「重炮展开」基础 360 帧（12 帧余量 ⇒ 无队友续能时一次都不触发），
# 同时把终幕收尾 f362 与延长段之间的空档从 30 帧压到 10 帧。
EXT_FRAMES = (372, 432, 492, 552, 612)
EXT_LIFETIME = 70
EXT_IDS_BASE = (50, 53, 56, 59, 62)
BEAM_LIFETIME = 60                                        # 四段光束判定寿命（母本口径，未改）
# 第二轮 S14：大激光（LLL 段 + 终幕 + 5 个延长槽）共用**一个**光束实例，挂球 -18 + ["GH",0]
# （与挂 LLL 判定区 CD+π 逐帧同角同位，见 flicker.md §修法1），寿命写死到最后一个延长槽结束那一帧；
# 提前收炮由 `HideEffectFromOwner(FX_BEAM_MAIN)` 在「重炮展开」已消失的 else 分支里做（只 fade 一次）。
BIG_BEAM_FRAME = STAGES[3][1]                             # 270：LLL 段起点＝大激光起点
BIG_BEAM_LIFETIME = EXT_FRAMES[-1] + EXT_LIFETIME - BIG_BEAM_FRAME   # 612+70-270 = 412
BEAM_END_FRAME = BIG_BEAM_FRAME + BIG_BEAM_LIFETIME                  # 682：大激光真正消失那一帧
VID_ENGINE = 1                          # vlv 变量号（BindConditionAccumulationVariable 绑「引擎启动」层数）
# 2026-09-27 平衡第二批（作者口径 A5「技能程序里随层数无上限增长的倍率 → 带上限的弱化版，一般 10 层」）：
# 第 5 参 99 → 10 ⇒ var = min(层数/1, 10)，技能倍率的层数贡献封顶 10 层（客户端 ActionEvaluator case 101：
# ``Math.min(count / params[3], params[4])``）。官方同构先例 ``blackflower_wiz_smr22_1/_2``
# ``Bind(-17, 2, [DCUnique, 11], 1, 10)``。固有「引擎启动」本身仍叠到 99（unique_condition c4 不动），
# 无上限的逐层部分由队长 during-134 行承担（已有同一层数的逐层行 ⇒ 视为已合并）。
ENGINE_DIVISOR, ENGINE_CAP = 1, 10      # var = min(层数/1, 10)；改前 99（= unique_condition c4）
ENGINE_CAP_BEFORE_BALANCE_B = 99
# 2026-09-27 平衡第三批（U4/U7）：担任队长且雷共鸣时（能力1 kind 705 开旗号 3）走开支，Bind 上限回到第二批前的
# int 99（= 固有「引擎启动」c4 叠层上限）；其余情况走关支，仍是上面的 ENGINE_CAP=10。旗号 1/2 已被 536/704 占用。
LEADER_SKILL_FLAG = 3
ENGINE_CAP_LEADER = ENGINE_CAP_BEFORE_BALANCE_B
# 2026-09-27 平衡第二批（作者口径 B1「技能每次施放单目标总削韧 ≤30」）：四段光束 + 5 个延长槽共 9 组
# 判定区（寿命 60/70、最小命中间隔 10、上限 Some(6)）的 CNA p13 1 → 0.3；导弹 p13=2、终幕 p13=4 不动。
# 单目标满打：基础 4×2 + 24×1 + 4 = 36 → 4×2 + 24×0.3 + 4 = 19.2；带「重炮展开」再 +30 → +9，66 → 28.2。
BEAM_BREAK = 0.3
BEAM_BREAK_BEFORE_BALANCE_B = 1


def _slv(a, b=None, alv=None):
    d = {"min": a, "max": a if b is None else b}
    if alv:
        d["alv_min"], d["alv_max"] = alv
    return [d]


def _C(name, *p):
    return ["Command", [name, *p]]


def _B(*items):
    return ["Block", list(items)]


def _W(n, name, *items):
    return ["Event", ["Wait", n, name, _B(*items)]]


def _FX(label, eff, subj, lifetime, coord, ang, scale=None, tp=True, td=False, layer="ForesideOfCharacter"):
    return _C("ShowEffect", label, eff, subj, [layer], lifetime, _coord(coord), 0, 0, ang, tp, td,
              ["None"] if scale is None else ["Some", _slv(scale)])


def _coord(coord):
    """坐标系参数：字符串 → ["AB"]；已经是列表（如 ["GH", 0]）则原样。"""
    return list(coord) if isinstance(coord, list) else [coord]


def _D(path):
    return ["SpecifyEffectDirectly", path]


def _CNA(tgt, flat, mul, brk, fev, hit):
    return _C("CreateNormalAttack", tgt, 255, [], [], flat, mul, _slv(0), False, False, False, False, False,
              _slv(brk), _slv(fev), [hit], True)


def _HA(subj, coord, ang, shape, va, life, interval, cap, ids, on_create, on_hit, tp=True, td=False, u=0, v=0):
    cid, hid, tid = ids
    return _C("CreateHitArea", "*", subj, _coord(coord), u, v, ang, tp, td, shape, ["Center"], [va], ["Single"],
              ["SpecifyHitAreaLifetimeDirectly", life], interval,
              ["Some", _slv(cap)] if cap else ["None"], False, True, ["None"],
              cid, _B(*on_create), hid, tid, _B(*on_hit), 0, 0, ["None"])


def _bind_engine():
    """每段开火前重新取「引擎启动」层数 ⇒ var[1] = min(层数/1, ENGINE_CAP=10)；CNA p6 的 vlv 读它（改版 A6；
    2026-09-27 平衡第二批把封顶从 99 收到 10）。

    官方玩家侧先例 ``blackflower_wiz_smr22_1/_2``：``Bind(-17, 2, [DCUnique, 11], 1, 10)`` 配
    ``CreateNormalAttack p6 = [{"min":…,"max":…,"vlv":[{"vid":2,"min":0,"max":2.5}]}]``。
    """
    return _C("BindConditionAccumulationVariable", -17, VID_ENGINE, ["DCUnique", int(UID_ENGINE)],
              ENGINE_DIVISOR, ENGINE_CAP)


def _bind_engine_leader():
    """平衡第三批：旗号 3 开支里的同一条 Bind，只有上限是 ENGINE_CAP_LEADER（int 99）。"""
    return _C("BindConditionAccumulationVariable", -17, VID_ENGINE, ["DCUnique", int(UID_ENGINE)],
              ENGINE_DIVISOR, ENGINE_CAP_LEADER)


def _if_cannon(then_items, else_items):
    """「重炮展开」还在 ⇒ then，否则 else（官方 rare5 先例 combat_soldier_smr22_1/_2）。

    空分支必须写 ``["Block", []]``——写 ``["DoNothing"]`` 进游戏 F1009（记忆卡 wf-dsl-donothing-enum-trap）。
    """
    return _C("ConditionalsConditionAccumulationNumber", ["DCUnique", int(UID_CANNON)], 1,
              _B(*then_items), _B(*else_items))


def _RECT(w, h=2400):
    return ["Rectangle", _slv(w), _slv(h)]


def donor_tree(level: str, plan: dict | None = None) -> list:
    """改版技能树（``revision-20260916/tekuto/plan.json`` 逐条落地）；特效引用先写官方母本路径，
    之后由 ``rewrite_effect_refs`` 改写到克隆族。

    与上一轮的结构差异（对应 plan ``skill_dsl.structural_changes`` S1–S10）：

    - S1/S2 根块最前两条 ``RemoveEventFromOwner("tekuto_cannon")`` /
      ``HideEffectFromOwner("tekuto_beam")``：杀掉上一发登记的全部段与贴图 ⇒ 再次发动是替换不叠加；
    - S3 ``CreateCondition(-17, ACUnique 13999302)`` 刻「重炮展开」1 层（时长由表 c3=360 决定）；
    - S4 删掉 ``CreateReferencePoint`` 炮台，整块上提到 ``FindNearSubjects`` 里，所有节点改挂球
      ``-18`` + ``["GH", 0]``（官方 ``rec_android_1anv_2`` 逐参同形）；
    - S5/S6 终幕 f300→f332、收炮 f330→f362（消除同族贴图重叠造成的闪烁）；
    - S7 追加 5 个由「重炮展开」开门的延长槽（Wait 在外、Conditionals 在内，条件必须在该帧才求值）；
    - S8 收炮余晖只在「重炮展开」已消失时放；
    - S9 段名统一（四段 ``tekuto_beam``、终幕 ``tekuto_finale``、各段 Wait 事件名 ``tekuto_cannon``）；
    - S10 删掉射线标记，debuff 改回雷达 onHit（官方母本写法），并改由开关槽 1 的 ``alv_*`` 驱动。

    审查修复轮（2026-09-16）追加：

    - S11（R-M4）根块补 ``CreateCondition(-17, ACUnique 13999301, 1层)``：发动技能 = 引擎启动 +1，
      让「伤害倍率随引擎启动次数提升」和队长 during134 三行在任何编成下都有非零基线；
    - S12（R-m6）终幕去掉 ``ConditionalsChangeSkillFlag(2, …)`` 外壳 ⇒ 65.0×/每层 +15.0× 无条件成立，
      开关槽 2 的全部效果只剩雷达 ``Sector`` 的 ``alv2_*``；
    - S13（R-m10）延长槽 392/452/512/572/632 → 372/432/492/552/612、判定寿命 60 → 70 ⇒ 相邻段重叠 10 帧。

    第二轮（作者第二次报「大激光还是闪烁」，2026-09-16 夜）：

    - S14 大激光（LLL 段 + 终幕 + 5 延长槽）由「每段各放一根 lll 光柱」改成**整段只有一个光束实例**：
      f270 挂球 ``-18 + ["GH",0] + π``、``SpecifyEffectLifetimeDirectly(412)``，名 ``tekuto_beam_lll``；
      LLL 段 / 延长槽的判定区 on_create 不再放光束，终幕改放过载闪光（charge，非激光族）；
      收炮与每个延长槽的 else 分支用 ``HideEffectFromOwner`` 收光束（只 fade 一次）。
      根因：``ActionEffect.fade()`` 会把贴图留到 ``end`` 序列播完（lll = 17 帧），而
      ``ActionEffectManager.show()`` 从不按名字去重 ⇒ 旧光柱在收、新光柱在起，同贴图叠 15~27 帧＝拍频闪烁。
      **判定区帧号 / 寿命 / 命中上限 / 倍率一个都没动 ⇒ 伤害与上一轮逐值相同。**
    """
    plan = plan if plan is not None else PLAN_CACHE.get("plan")
    if plan is None:
        raise KitError("donor_tree needs the revision plan (call load_revision_plan(root) first)")
    sk = plan["skill_dsl"]
    mult = sk["multipliers"]["blocks"]
    p6_key = "lv2_p6" if level == "2" else "lv1_p6"

    def m(block: str):
        """CNA 倍率项：plan 的 ``{min,max,vlv:[{vid,min,max}]}`` 原样（每层「引擎启动」加成走 vlv）。"""
        term = copy.deepcopy(mult[block][p6_key])
        if [v["vid"] for v in term["vlv"]] != [VID_ENGINE]:
            raise KitError(f"plan multiplier {block}.{p6_key} vlv vid != {VID_ENGINE}")
        return [term]

    radar = sk["hitareas"][0]
    if radar["id"] != "HA_radar":
        raise KitError("plan hitareas[0] is not HA_radar")
    rp = radar["params"]
    debuffs = [copy.deepcopy(c["command"]) for c in sk["conditions_on_hit"]]
    if [c["subject_binding"] for c in sk["conditions_on_hit"]] != [22, 22]:
        raise KitError("plan conditions_on_hit must both bind the radar hit target (22)")

    # ---- 雷达 onHit：命中特效 → 两条 debuff（开关槽 1 的 alv_*，没开时恒 0）→ 取消导弹取消 → 导弹链
    radar_hit_block = [
        _FX("radar_hit", _D(SR_SRC + "radar_hit"), 22, ["PlayOnlyFirstSequence"], "AB", 0, tp=True, td=False),
        *[_C(*cmd) for cmd in debuffs],
        _C("RemoveEvent", "missile_cancel"),
        _W(80, EV_CANNON, _C("CreateReferencePoint", 22, ["AB"], 0, 0, 0, False, False, ["Single"], 65, 23, _B(
            _FX("missile_drop", _D(SR_SRC + "missile_hit"), 23, ["PlayOnlyFirstSequence"], "AB", 0, tp=False, td=False),
            _W(9, EV_CANNON, _bind_engine(),
               _HA(23, "AB", 0, ["Circle", _slv(50)], "Center", 15, ["CalculatedUsingMaxNumOfHits", 4], None,
                   (24, 25, 26), [], [_C("ShakeCamera", 1), _CNA(26, 16, m("missile"), 2, 1, "Fine")])),
        ))),
    ]
    # 雷达判定区：半径/角度写 {min,max,alv2_*}，共鸣（开关槽 2）满潜能时 400/90° → 600/135°
    radar_ha = _HA(BALL, GH, rp["p6_angle"], copy.deepcopy(rp["p9_shape"]), "Center",
                   rp["p13_lifetime"][1], list(rp["p14_interval"]), 1, (20, 21, 22),
                   [_C(*radar["on_create"][0])], radar_hit_block,
                   tp=rp["p7_trackingPos"], td=rp["p8_trackingDir"], u=rp["p4_u"], v=rp["p5_v"])

    def laser(fam, cid, scale=None, label=FX_BEAM):
        return _FX(label, _D(f"{laser_src(fam)}/enemy_shot_laser_{fam}_yellow"), cid,
                   ["UntilTargetTerminates"], "CD", PI, scale=scale, tp=True, td=True)

    def main_beam():
        """大激光唯一实例：挂球 -18 + ["GH",0] + π，寿命写死 412 帧（f270→f682）。

        与「挂 LLL 判定区 + CD + π」在屏幕上完全等价：判定区自己也是 ``-18 + ["GH",0] + 角度 0``、
        trackingDir=false，所以 ``ActionEffect.calcDir()`` 的 CD 分支（``target.getDirCD()``）与 GH 分支
        （``atan2(敌−球)+π/2``）在同一帧创建时取到同一个角，之后两者都冻结 ⇒ 位置/朝向逐帧一致。
        同形先例：本树的 ``aim_line``（laser_notice，官方 174 处都是 CD，我们挂球用 GH）。
        """
        return _FX(FX_BEAM_MAIN, _D(f"{laser_src('lll')}/enemy_shot_laser_lll_yellow"), BALL,
                   ["SpecifyEffectLifetimeDirectly", BIG_BEAM_LIFETIME], GH, PI, tp=True, td=False)

    def beam_ha(width, ids, fam, shake, cap, life, interval, mul, brk, fev, hit, label=FX_BEAM,
                fx_scale=None, fx=None):
        """判定区 + 其 on_create 演出。``fx=[]`` ⇒ 这段不自带光束（大激光已由 main_beam 连续演出）。"""
        on_create = [laser(fam, ids[0], scale=fx_scale, label=label)] if fx is None else list(fx)
        return _HA(BALL, GH, 0, _RECT(width), "Bottom", life, interval, cap, ids,
                   [*on_create, _C("ShakeCamera", shake)],
                   [_CNA(ids[2], 10 if label == FX_BEAM else 33, mul, brk, fev, hit)], v=-50)

    def stage(name, frame, width, ids, fam, charge_scale, shake):
        body = [_bind_engine()]
        if charge_scale:
            body.append(_FX("charge_core", ["ResolveByElement", CHARGE, 255], BALL,
                            ["SpecifyEffectLifetimeDirectly", CHARGE_CORE_LIFETIME], "AB", 0,
                            scale=charge_scale, tp=True, td=False))
        big = name == "lll"
        if big:
            body.append(main_beam())
        body.append(beam_ha(width, ids, fam, shake, 6, BEAM_LIFETIME, ["SpecifyMinHitIntervalDirectly", 10],
                            m(name), BEAM_BREAK, 0.6, "ThunderSmall", fx=[] if big else None))
        return _W(frame, EV_CANNON, *body)

    body_items = [
        _FX("aim_line", _D(NOTICE), BALL, ["SpecifyEffectLifetimeDirectly", 90], GH, PI, tp=True, td=False),
        _FX("radar", _D(SR_SRC + "radar"), BALL, ["PlayOnlyFirstSequence"], GH, 0, scale=8, tp=True, td=False),
        _W(5, EV_CANNON, radar_ha),
        _W(23, "missile_cancel", _C("RemoveEvent", "missile_event")),
        _W(24, "missile_event", _FX("missile_launch", _D(SR_SRC + "missile"), BALL, ["PlayOnlyFirstSequence"], GH, 0,
                                    tp=True, td=False)),
        _W(20, EV_CANNON, _FX("charge_S", _D(SR_SRC + "laser_100px"), BALL, ["SpecifyEffectLifetimeDirectly", 70],
                              GH, 0, scale=1, tp=True, td=False)),
        *[stage(name, frame, width, ids, fam, charge, shake)
          for name, frame, width, ids, fam, charge, shake in STAGES],
        # 过载终幕（改版 S12 / 审查 R-m6）：不再挂 ConditionalsChangeSkillFlag(2)。
        # 挂着时没开关槽2 的编成只有 54.0×/每层 12.6×，作者给的 65×/15× 变成「满级+共鸣+能力3+吃满」的最好情况；
        # 改成无条件段后 65.0×/每层 +15.0× 在任何编成都成立，顺带删掉 DSL 里零先例的 ConditionalsChangeSkillFlag(2,…)。
        # 第二轮 S14：终幕不再放第二根 lll 光柱（上一轮以为「f332 > LLL 判定区 f330」就错开了，
        # 但 fade() 会让 LLL 贴图再演 17 帧 end 序列到 f347 ⇒ f332-347 场上有两根同贴图光柱）。
        # 现在终幕只出一团过载闪光 + 震屏，大激光本体由 main_beam 一路演到 f362 才收。
        _W(FINALE_FRAME, EV_CANNON, _bind_engine(),
           beam_ha(FINALE_WIDTH, FINALE_IDS, "lll", 3, 1, FINALE_LIFETIME,
                   ["CalculatedUsingMaxNumOfHits", 1], m("finale"), 4, 2, "ThunderLight",
                   label=FX_FINALE,
                   fx=[_FX(FX_FINALE, ["ResolveByElement", CHARGE, 255], BALL,
                           ["SpecifyEffectLifetimeDirectly", FINALE_LIFETIME], "AB", 0,
                           scale=FINALE_FLASH_SCALE, tp=True, td=False)])),
        # 收炮：只有「重炮展开」已消失（没有队友续能）时才收——收大激光（唯一一次 fade）+ 放余晖
        _W(COOLDOWN_FRAME, EV_CANNON, _if_cannon([], [
            _C("HideEffectFromOwner", FX_BEAM_MAIN),
            _FX("cannon_cooldown", _D(SR_SRC + "laser_200px_end"), BALL, ["PlayOnlyFirstSequence"], GH, 0,
                scale=COOLDOWN_SCALE, tp=False, td=False)])),
        # 大激光真正打完那一帧（f682 = 270+412）收炮：与上面 f362 的提前收炮**条件相反**
        # ⇒ 一次发动恰好播一次余晖。审查 R3-M1：D2 把「重炮展开」提到 720 帧之后，
        # f362 那条 else 恒不执行（362 < 720），余晖与 laser_200px_end 一起变成死码；
        # 而作者这一轮报的正是「特效缺失」。这里补回它本来的设计位置 —— 激光收尾的尾焰。
        # Wait 是挂在 owner 上的具名事件（再次发动时由根块 RemoveEventFromOwner(EV_CANNON) 清掉），
        # 不随 action 结束而丢：本树 f612 的延长槽与寿命 412 帧的大激光本来就依赖这一点。
        _W(BEAM_END_FRAME, EV_CANNON, _if_cannon(
            [_FX("cannon_cooldown", _D(SR_SRC + "laser_200px_end"), BALL, ["PlayOnlyFirstSequence"], GH, 0,
                 scale=COOLDOWN_SCALE, tp=False, td=False)], [])),
        # 延长槽 ×5：队长 461 刷新「重炮展开」时才继续开火（Wait 在外，条件在该帧求值）。
        # 光束不再每槽重放（那是 60 帧一次的硬边界＝闪烁），只补判定区；条件掉了就在 else 收光束。
        *[_W(frame, EV_CANNON, _if_cannon(
            [_bind_engine(),
             beam_ha(LLL_RECT_WIDTH, (base, base + 1, base + 2), "lll", 3, 6, EXT_LIFETIME,
                     ["SpecifyMinHitIntervalDirectly", 10], m("lll"), BEAM_BREAK, 0.6, "ThunderSmall", fx=[])],
            [_C("HideEffectFromOwner", FX_BEAM_MAIN)]))
          for frame, base in zip(EXT_FRAMES, EXT_IDS_BASE)],
    ]
    sd = SELF_SD[level]
    body = _B(
        _C("RemoveEventFromOwner", EV_CANNON),
        _C("HideEffectFromOwner", FX_BEAM),
        _C("HideEffectFromOwner", FX_BEAM_MAIN),   # 第二轮 S14：大激光独立命名，再次发动一样要先收掉
        # S18（作者 2026-09-21「取消技能释放后的后摇……去掉固定的这一段」）：根块**不再有 StopBall**。
        # 首发写的是 `StopBall(-18, 10, RestoreToSpeedBeforeActionExecution, ["EF"], 0)`，
        # 已经比母本 TEMPLATE_STOPBALL（140 帧 + Stop，球停住不再恢复）轻得多，这一轮整条删掉 ⇒
        # DSL 侧一帧都不定住球，顺带少掉 10 帧 suppressDirectAttack 与 10 帧「全队按不出技能」
        # （BallImpl.applyMovement 第 7 参对 StopBall 恒 true；_canInvokeActionSkill 在 SkillMoving 期间恒 false）。
        #
        # **别把这当成「取消了固定」**：玩家感知到的定住只从 70 帧降到 60 帧（-14%）。客户端在本树
        # 开跑之前先冻 60 帧技能 cut-in（SquadManagerImpl.as:734-735，见 wf_tekuto_no_endlag_revision
        # 的 lock_report），而 BallImpl 状态机 case 7 要等 stateFrame == 60 才 `innovation.invoke()`
        # 启动本树 ⇒ 60 帧 cut-in 与本树 f0 的停球是**先后**关系、不重叠，删掉的是后面那 10 帧。
        #
        # 演出影响（**不可写成「位置不变」**）：本树 12 个 CreateHitArea 里 11 个主体是球 -18、
        # 第 7 参 trackingPos=True、坐标系 ["GH", 0]（朝 f0 用 FindNearSubjects 锁定的那名敌人），
        # trackingDir=false 只是把**朝向数值**冻在各自创建的那一帧。球不再被钉住 10 帧 ⇒ 此后每一帧
        # 球都比原来多飞 10 帧的行程，f90/150/210/270/332 以及 5 个延长槽的**发射原点**（连带由原点
        # 算出的那个角度数值）都会落在与原来不同的地方。不变的是：伤害倍率、段数、帧号时序，以及
        # 「从球出发、指向 f0 锁定的那名敌人」这条语义。这是「不定住球」的应有后果，不是缺陷，
        # 但它不能当免检牌用。（第 12 个判定区 = f94 导弹落点，挂参照点 23、两个跟随位都 false，
        # 锚在锁定目标上 ⇒ 完全不受球位移影响。）
        # 门禁 `ball_hold_problems()`（在 dsl_quick_problems 里调用）盯死它不许回来；
        # 节点级改版工具与逐节点对照测试见 `wf_tekuto_no_endlag_revision.py`。
        _C("CreateCondition", -17, [["ACSkillDamage", _slv(sd[0]), _slv(sd[1], sd[2]), _slv(1)]], _slv(1),
           ["GenericConditionHitEffect"], True, False, "", None, False, 3, _slv(1), False),
        _C("CreateCondition", -17, [["ACUnique", int(UID_CANNON), _slv(1)]], _slv(1),
           ["GenericConditionHitEffect"], True, False, "", None, False, 3, _slv(1), False),
        # S11 / 审查 R-M4：特克托自己启动引擎 = 发动技能 ⇒ 「引擎启动」+1。
        # 上一轮全包只有 ability 1399933#2 一处产出 13999301，而那条同时要「雷共鸣 + 主位 + 自身已有重炮展开
        # + 雷队友发动技能」⇒ 非共鸣/副位时倍率成长恒为 0，队长 during134 三行开局也恒为 0。
        _C("CreateCondition", -17, [["ACUnique", int(UID_ENGINE), _slv(1)]], _slv(1),
           ["GenericConditionHitEffect"], True, False, "", None, False, 3, _slv(1), False),
        _C("FindNearSubjects", -18, 1, 49, ["CreateImaginaryTarget", -100000], E, _B(*body_items)),
    )
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, body]


# ================================================================ 纯函数校验

def strict_diff(a, b, path="$", out=None, limit=20):
    """类型敏感的树比较（int≠float≠bool；AMF3 编码按类型区分）。返回差异路径列表。"""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if type(a) is not type(b):
        out.append(f"{path}: type {type(a).__name__} != {type(b).__name__} ({a!r} vs {b!r})")
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            strict_diff(x, y, f"{path}[{i}]", out, limit)
    elif isinstance(a, dict):
        if list(a) != list(b):
            out.append(f"{path}: keys {list(a)} != {list(b)}")
        for k in a:
            if k in b:
                strict_diff(a[k], b[k], f"{path}.{k}", out, limit)
    elif a != b:
        out.append(f"{path}: {a!r} != {b!r}")
    return out


def _iter_lists(node):
    if isinstance(node, list):
        yield node
        for x in node:
            yield from _iter_lists(x)
    elif isinstance(node, dict):
        for x in node.values():
            yield from _iter_lists(x)


def _command_nodes(tree, name: str, label: str | None = None) -> list[list]:
    return [n for n in _iter_lists(tree) if n and n[0] == name and (label is None or (len(n) > 1 and n[1] == label))]


def apply_design_tree_fixes(composed: list, fixes=DESIGN_TREE_FIXES) -> tuple[list, list[dict]]:
    """对设计 composed_tree 的副本做审查修正。每条修正必须恰好命中一个节点，且原值严格等于记录的设计值
    （改为 applied）或已等于修正值（设计已同步，记 already-in-design）；其他值一律报错，不静默放过。"""
    tree = copy.deepcopy(composed)
    applied = []
    for fix in fixes:
        nodes = _command_nodes(tree, fix["command"], fix["label"])
        if len(nodes) != 1 or len(nodes[0]) <= fix["arg"]:
            raise KitError(f"design tree fix {fix['id']}: expected exactly 1 {fix['command']} {fix['label']!r}, "
                           f"found {len(nodes)}")
        node = nodes[0]
        current = node[fix["arg"]]
        if not strict_diff(current, fix["design"]):
            node[fix["arg"]] = copy.deepcopy(fix["fixed"])
            state = "applied"
        elif not strict_diff(current, fix["fixed"]):
            state = "already-in-design"
        else:
            raise KitError(f"design tree fix {fix['id']}: design value {current!r} is neither "
                           f"{fix['design']!r} nor {fix['fixed']!r}; re-check the design")
        applied.append({"id": fix["id"], "label": fix["label"], "arg": fix["arg"], "state": state,
                        "design": fix["design"], "fixed": fix["fixed"], "reason": fix["reason"]})
    return tree, applied


def design_composed_tree(design: dict, level: str) -> tuple[list, list[dict]]:
    return apply_design_tree_fixes(design["skills"][f"tree_plan_{level}"]["composed_tree"])


def cooldown_width_problems(tree) -> list[str]:
    """收炮余晖宽度与 LLL 光束配对：laser_200px_end 的 Some(k) 应满足 k×100 == LLL Rect 宽（官方配对口径）。"""
    probs = []
    fx = _command_nodes(tree, "ShowEffect", "cannon_cooldown")
    # 审查 R3-M1：余晖现在有两处 —— f362 提前收炮（else 分支）与 f682 大激光打完（then 分支），
    # 两条门条件相反 ⇒ 一次发动恰好播一次。两处的素材与 scale 必须完全一致。
    if len(fx) != 2:
        return [f"cannon_cooldown ShowEffect count {len(fx)} != 2（提前收炮 + 打完收炮）"]
    if strict_diff(fx[0][2], fx[1][2]) or strict_diff(fx[0][12], fx[1][12]):
        probs.append(f"两处 cannon_cooldown 的素材/scale 不一致: {fx[0][2]!r}@{fx[0][12]!r} vs {fx[1][2]!r}@{fx[1][12]!r}")
    eff = fx[0][2]
    if not (isinstance(eff, list) and len(eff) > 1 and str(eff[1]).endswith("/super_robot_laser_200px_end")):
        probs.append(f"cannon_cooldown effect is not super_robot_laser_200px_end: {eff!r}")
    scale = fx[0][12]
    if not (isinstance(scale, list) and scale[0] == "Some" and len(scale[1]) == 1
            and scale[1][0].get("min") == scale[1][0].get("max")):
        return probs + [f"cannon_cooldown scale shape unexpected: {scale!r}"]
    k = scale[1][0]["min"]
    widths = []
    for ev in _command_nodes(tree, "Wait"):
        if len(ev) > 3 and ev[1] == 270:
            for ha in _command_nodes(ev[3], "CreateHitArea"):
                if isinstance(ha[9], list) and ha[9][0] == "Rectangle":
                    widths.append(ha[9][1][0]["min"])
    if widths != [LLL_RECT_WIDTH]:
        probs.append(f"LLL stage (Wait 270) Rectangle widths {widths} != [{LLL_RECT_WIDTH}]")
    elif abs(k * 100 - widths[0]) > 1e-9:
        probs.append(f"cannon_cooldown Some({k}) ≈ {k * 100:g}px does not match LLL Rect {widths[0]} (expect Some({widths[0] / 100:g}))")
    return probs


def _tag(v):
    return v[0] if isinstance(v, list) and v and isinstance(v[0], str) else None


def laser_beam_census(tree) -> list[dict]:
    """把树里每一根 ``enemy_shot_laser_*`` 光柱按帧摊开：``{fam, start, hitarea_end, gone}``。

    ``gone`` = 贴图真正从屏幕上消失的帧 = 特效寿命结束 + ``end`` 序列长度
    （``ActionEffect.fade()``：``ttl = getSequenceTotalFrames("end")``，见 ``LASER_END_FRAMES``）。
    寿命三态：``UntilTargetTerminates`` 跟所挂判定区（组 ``willRemove()``＝``frameCount >= lifetime``）、
    ``SpecifyEffectLifetimeDirectly(N)`` 自己数 N、``PlayOnlyFirstSequence`` 只播首序列。
    口径保守：不计 ``HideEffectFromOwner`` 的提前收，算的是**最长**可见窗口。
    """
    out: list[dict] = []

    def visit(node, t: int, ha_life: int | None):
        if isinstance(node, list):
            if _tag(node) == "Event" and isinstance(node[1], list) and node[1] and node[1][0] == "Wait":
                visit(node[1][3], t + int(node[1][1]), ha_life)
                return
            if _tag(node) == "Command" and isinstance(node[1], list) and node[1]:
                c = node[1]
                if c[0] == "CreateHitArea":
                    life = c[13][1] if isinstance(c[13], list) and len(c[13]) > 1 else None
                    visit(c[20], t, life if isinstance(life, int) else None)
                    visit(c[23], t, life if isinstance(life, int) else None)
                    return
                if c[0] == "ShowEffect":
                    path = c[2][1] if isinstance(c[2], list) and len(c[2]) > 1 else None
                    fam = None
                    if isinstance(path, str):
                        for f in LASER_FAMS:
                            if path.endswith(f"/enemy_shot_laser_{f}_yellow"):
                                fam = f
                    if fam is not None:
                        spec = c[5]
                        tag = _tag(spec)
                        if tag == "SpecifyEffectLifetimeDirectly":
                            end = t + int(spec[1])
                        elif tag == "UntilTargetTerminates":
                            end = t + (ha_life if ha_life is not None else 0)
                        elif tag == "PlayOnlyFirstSequence":
                            end = t + 6
                        else:
                            end = t
                        out.append({"label": c[1], "fam": fam, "start": t, "end": end,
                                    "gone": end + LASER_END_FRAMES[fam],
                                    "on_hitarea": tag == "UntilTargetTerminates"})
                        return
            for child in node:
                visit(child, t, ha_life)
        elif isinstance(node, dict):
            for child in node.values():
                visit(child, t, ha_life)

    visit(tree, 0, None)
    return sorted(out, key=lambda e: (e["start"], e["fam"]))


def beam_overlap_problems(tree) -> list[str]:
    """S14 消闪烁的判据：**任一帧，同一个激光族不能有两根光柱同时在屏幕上**。

    判定区一终止只是 ``fade()``，贴图还要再演 ``end`` 序列（lll = 17 帧）；上一轮把终幕从 f300 挪到 f332
    时按「LLL 判定区 f330 结束」算，漏了这 17 帧 ⇒ f332–f347 两根 lll 同屏，作者看到的就是这个。
    负向对照：把 ``main_beam()`` 换回每段各放一根，这里必须变红。
    """
    probs = []
    census = laser_beam_census(tree)
    for i, a in enumerate(census):
        for b in census[i + 1:]:
            if a["fam"] == b["fam"] and a["start"] < b["gone"] and b["start"] < a["gone"]:
                probs.append(f"同族光柱重叠: {a['fam']} {a['label']}[{a['start']}→{a['gone']}) "
                             f"与 {b['label']}[{b['start']}→{b['gone']}) 重叠 "
                             f"{min(a['gone'], b['gone']) - max(a['start'], b['start'])} 帧")
    return probs


def donothing_problems(tree) -> list[str]:
    """F1009 陷阱：Conditionals* 的分支必须是 Block/Command/Event，不能是 ["DoNothing"] 等枚举。"""
    probs = []

    def rec(node):
        if isinstance(node, list):
            if _tag(node) == "Command" and isinstance(node[1], list) and str(node[1][0]).startswith("Conditionals"):
                for i, p in enumerate(node[1][1:], 1):
                    if isinstance(p, list) and _tag(p) not in (None, "Block", "Command", "Event") \
                            and _tag(p) in ("DoNothing",):
                        probs.append(f"{node[1][0]} p{i} 是枚举 {_tag(p)}（F1009，空分支须写 [\"Block\", []]）")
            if node == ["DoNothing"]:
                probs.append("树中出现 [\"DoNothing\"] 节点（F1009）")
            for child in node:
                rec(child)
        elif isinstance(node, dict):
            for child in node.values():
                rec(child)
    rec(tree)
    return probs


def template_derivation_problems(ours: list, template: list, level: str) -> tuple[list[str], dict]:
    """母本（官方 ``super_robot_<lv>``）派生节点核对。

    改版**刻意偏离**母本的三处不再比对，改为记录事实供 verify 对账：雷达扇形（30°→90°/共鸣 135°）、
    雷达寿命（22→30）与旋转速度（0.09599×22→0.05236×30）、判定区主体（RP→球 -18）。
    仍必须与母本逐值相同的是：根头、自身技能伤害、导弹圆判定与导弹 CNA 的削韧/Fever/命中特效、雷达特效缩放。
    """
    import wf_seasonal7_common as C
    probs, facts = [], {}
    if template[0] != "ActionDsl" or template[2:11] != ours[2:11] or ours[1] != 1 or template[1] != 2:
        probs.append(f"根头与母本不符: ours={ours[:11]} template={template[:11]}")
    facts["header_template"] = template[:11]

    def self_sd(tree):
        return [c for c in C.commands(tree, "CreateCondition")
                if c[1] == -17 and c[2] and c[2][0][0] == "ACSkillDamage"]
    t_sd, o_sd = self_sd(template), self_sd(ours)
    if len(t_sd) != 1 or len(o_sd) != 1 or t_sd[0][1:] != o_sd[0][1:]:
        probs.append(f"ACSkillDamage 与母本原值不符: ours={o_sd} template={t_sd}")
    facts["self_skill_damage"] = t_sd[0][2] if t_sd else None

    def sector(tree):
        return [c for c in C.commands(tree, "CreateHitArea") if _tag(c[9]) == "Sector"]
    t_sec, o_sec = sector(template), sector(ours)
    if len(t_sec) != 1 or len(o_sec) != 1:
        probs.append("雷达扇形判定区数量异常")
    else:
        t, o = t_sec[0], o_sec[0]
        t_rot = C.commands(t, "RotateHitArea")
        o_rot = C.commands(o, "RotateHitArea")
        if t[14] != o[14] or t[15] != o[15]:
            probs.append(f"雷达命中节流/每敌上限与母本不符: {o[14]}/{o[15]} vs {t[14]}/{t[15]}")
        if not t_rot or not o_rot:
            probs.append("雷达 RotateHitArea 缺失")
        facts["radar_deliberate_changes"] = {
            "subject": [t[2], o[2]], "coord": [t[3], o[3]], "angle": [t[6], o[6]],
            "shape": [t[9], o[9]], "lifetime": [t[13], o[13]],
            "rotate_speed": [t_rot[0][2] if t_rot else None, o_rot[0][2] if o_rot else None],
            "rotate_bind_id": [t_rot[0][1] if t_rot else None, o_rot[0][1] if o_rot else None],
        }
    circle_t = [c for c in C.commands(template, "CreateHitArea") if _tag(c[9]) == "Circle"]
    circle_o = [c for c in C.commands(ours, "CreateHitArea") if _tag(c[9]) == "Circle"]
    if len(circle_t) != 1 or len(circle_o) != 1 or circle_t[0][9] != circle_o[0][9] or circle_t[0][14] != circle_o[0][14]:
        probs.append("导弹圆判定与母本不符")
    t_mis = [c for c in C.commands(template, "CreateNormalAttack") if c[5] == 16]
    o_mis = [c for c in C.commands(ours, "CreateNormalAttack") if c[5] == 16]
    if len(t_mis) != 1 or len(o_mis) != 1 or [t_mis[0][i] for i in (13, 14, 15)] != [o_mis[0][i] for i in (13, 14, 15)]:
        probs.append("导弹 CNA 削韧/Fever/命中特效与母本不符")
    radar_fx_t = [c for c in C.commands(template, "ShowEffect") if str(c[2][1]).endswith("super_robot_radar")]
    radar_fx_o = [c for c in C.commands(ours, "ShowEffect") if str(c[2][1]).endswith("super_robot_radar")]
    if not radar_fx_t or not radar_fx_o or radar_fx_t[0][12] != radar_fx_o[0][12]:
        probs.append("雷达特效缩放与母本不符")
    facts["level"] = level
    return probs, facts


def _counter(values) -> dict:
    out: dict[Any, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def revision_tree_problems(tree: list, level: str, plan: dict) -> tuple[list[str], dict]:
    """改版逐条对账：把 ``plan.json`` 的结构改动 / 判定区 / debuff / 时间轴 / 倍率重新读回树里核对。

    plan.json 是设计阶段的产出、kit 只是实现方，所以这是真正的外部对账：任何一条没落地或数值漂了都会报出来。
    """
    import wf_seasonal7_common as C
    sk = plan["skill_dsl"]
    probs: list[str] = []
    facts: dict[str, Any] = {"level": level}

    def add(cond, msg):
        if not cond:
            probs.append(msg)

    # ---- S1/S2：根块最前两条（必须排在任何 Wait 注册之前）
    root = tree[11][1]
    head = [n[1][:2] for n in root[:2] if _tag(n) == "Command"]
    add(head == [["RemoveEventFromOwner", EV_CANNON], ["HideEffectFromOwner", FX_BEAM]],
        f"S1/S2 根块最前两条不是 RemoveEventFromOwner/HideEffectFromOwner: {head}")
    head3 = root[2][1][:2] if len(root) > 2 and _tag(root[2]) == "Command" else None
    add(head3 == ["HideEffectFromOwner", FX_BEAM_MAIN],
        f"S14 根块第三条必须收掉上一发的大激光 HideEffectFromOwner({FX_BEAM_MAIN}): {head3}")
    # ---- S3：ACUnique 刻「重炮展开」
    cannon = [c for c in C.commands(tree, "CreateCondition")
              if c[1] == -17 and c[2] and c[2][0][0] == "ACUnique" and c[2][0][1] == int(UID_CANNON)]
    add(len(cannon) == 1 and cannon[0][2][0][2] == [{"min": 1, "max": 1}],
        f"S3 ACUnique {UID_CANNON} 1 层缺失或形状不对: {cannon}")
    # ---- S11（R-M4）：技能自身刻「引擎启动」1 层，且与 S3 逐参同形（只差 uid）
    engine = [c for c in C.commands(tree, "CreateCondition")
              if c[1] == -17 and c[2] and c[2][0][0] == "ACUnique" and c[2][0][1] == int(UID_ENGINE)]
    add(len(engine) == 1 and engine[0][2][0][2] == [{"min": 1, "max": 1}],
        f"S11 ACUnique {UID_ENGINE} 1 层缺失或形状不对: {engine}")
    if len(engine) == 1 and len(cannon) == 1:
        a, b = list(engine[0]), list(cannon[0])
        a[2] = b[2] = None
        add(not strict_diff(a, b), "S11 引擎启动 CreateCondition 与 S3 重炮展开不同形")
    want_s11 = next((s for s in sk["structural_changes"] if s["id"] == "S11"), None)
    add(want_s11 is not None and len(engine) == 1 and not strict_diff(engine[0], want_s11["command"]),
        "S11 CreateCondition 与 plan.structural_changes[S11].command 不一致")
    # ---- S4：炮台 ReferencePoint 删掉，只剩导弹落点那一个；主体全改挂球
    rps = C.commands(tree, "CreateReferencePoint")
    add(len(rps) == 1 and rps[0][1] == 22,
        f"S4 CreateReferencePoint 应只剩导弹落点(主体22)，实得 {[r[1] for r in rps]}")
    ball_ha = [c for c in C.commands(tree, "CreateHitArea") if c[2] == BALL]
    want_ball = 1 + len(STAGES) + 1 + len(EXT_FRAMES)
    add(len(ball_ha) == want_ball, f"S4 挂球判定区数 {len(ball_ha)} != {want_ball}(雷达+四段+终幕+5延长)")
    add(all(c[3] == GH for c in ball_ha), "S4 挂球判定区坐标系必须是 GH(0)")
    # ---- S9：事件名与特效名
    ev_names = sorted({n[1][2] for n in C.walk(tree)
                       if isinstance(n, list) and _tag(n) == "Event" and n[1][0] == "Wait"})
    add(set(ev_names) <= {EV_CANNON, *EV_KEEP}, f"S9 Wait 事件名超出白名单: {ev_names}")
    fx_labels = _counter([c[1] for c in C.commands(tree, "ShowEffect")])
    add(fx_labels.get(FX_BEAM) == len(STAGES) - 1,
        f"S9/S14 {FX_BEAM} 光束贴图数 {fx_labels.get(FX_BEAM)} != {len(STAGES) - 1}(只剩 S/L/LL 三段)")
    add(fx_labels.get(FX_BEAM_MAIN) == 1, f"S14 {FX_BEAM_MAIN} 大激光应恰好 1 个实例")
    add(fx_labels.get(FX_FINALE) == 1, f"S9 {FX_FINALE} 应恰好 1 个")
    facts["effect_labels"] = dict(sorted(fx_labels.items()))
    # ---- S10：射线标记已删（Rect 800 判定区不复存在）
    add(not [c for c in C.commands(tree, "CreateHitArea")
             if _tag(c[9]) == "Rectangle" and c[9][1][0]["min"] == 800], "S10 射线标记(Rect800) 仍在树里")

    # ---- 雷达判定区逐参（plan.hitareas[0]）
    rp = sk["hitareas"][0]["params"]
    radar = [c for c in C.commands(tree, "CreateHitArea") if _tag(c[9]) == "Sector"]
    add(len(radar) == 1, "雷达扇形判定区应恰好 1 个")
    if len(radar) == 1:
        r = radar[0]
        want = {2: BALL, 3: GH, 4: rp["p4_u"], 5: rp["p5_v"], 6: rp["p6_angle"],
                7: rp["p7_trackingPos"], 8: rp["p8_trackingDir"], 9: rp["p9_shape"],
                13: ["SpecifyHitAreaLifetimeDirectly", rp["p13_lifetime"][1]], 14: rp["p14_interval"],
                15: rp["p15_per_target_cap"], 19: rp["p19_id_oncreate"], 21: rp["p21_id"], 22: rp["p22_id_target"]}
        for idx, value in want.items():
            if strict_diff(r[idx], value):
                probs.append(f"雷达 p{idx} {r[idx]!r} != plan {value!r}")
        rot = C.commands(r, "RotateHitArea")
        add(len(rot) == 1 and rot[0] == sk["hitareas"][0]["on_create"][0],
            f"雷达 RotateHitArea != plan {sk['hitareas'][0]['on_create'][0]}")
        facts["radar"] = {"shape": r[9], "lifetime": r[13], "rotate": rot[0] if rot else None}
    # ---- 两条 debuff（开关槽 1 的 alv_*；plan 逐参）
    for entry in sk["conditions_on_hit"]:
        want_cmd = entry["command"]
        got = [c for c in C.commands(tree, "CreateCondition")
               if c[1] == entry["subject_binding"] and c[2] and c[2][0][0] == want_cmd[2][0][0]]
        add(len(got) == 1 and not strict_diff(got[0], want_cmd),
            f"{entry['id']} CreateCondition 与 plan 不一致: {got}")
    # ---- 时间轴：段 / 终幕 / 收炮 / 延长槽的帧号
    frames = sorted(n[1][1] for n in C.walk(tree)
                    if isinstance(n, list) and _tag(n) == "Event" and n[1][0] == "Wait" and n[1][2] == EV_CANNON)
    want_frames = sorted([5, 9, 20, 80] + [s[1] for s in STAGES]
                         + [FINALE_FRAME, COOLDOWN_FRAME, *EXT_FRAMES, BEAM_END_FRAME])
    add(frames == want_frames, f"时间轴帧号 {frames} != {want_frames}")
    facts["frames"] = frames
    # ---- 延长槽：每个都必须被「重炮展开」门包住；收炮走 else 分支
    slots = C.commands(tree, "ConditionalsConditionAccumulationNumber")
    add(len(slots) == len(EXT_FRAMES) + 2,
        f"ConditionalsConditionAccumulationNumber 数 {len(slots)} != {len(EXT_FRAMES) + 2}"
        f"（延长槽 {len(EXT_FRAMES)} + 提前收炮 1 + 打完收炮 1）")
    add(all(g[1] == ["DCUnique", int(UID_CANNON)] and g[2] == 1 for g in slots),
        "延长槽/收炮门的 DCUnique 或阈值不对")
    cooldown_gate = [g for g in slots if not g[3][1]]
    add(len(cooldown_gate) == 1 and [n[1][0] for n in cooldown_gate[0][4][1]]
        == ["HideEffectFromOwner", "ShowEffect"],
        "S14 提前收炮 else 分支必须是 [HideEffectFromOwner(大激光), 余晖 ShowEffect]、then 为空 Block")
    # 审查 R3-M1：f682（大激光真正结束）那条与 f362 条件相反 ⇒ 一次发动恰好播一次余晖
    end_gate = [g for g in slots if g[3][1] and not g[4][1]
                and [n[1][:2] for n in g[3][1]] == [["ShowEffect", "cannon_cooldown"]]]
    add(len(end_gate) == 1,
        "S14 f682 打完收炮门必须是 then=[余晖 ShowEffect]、else 为空 Block（与 f362 互补）")
    ext_gates = [g for g in slots if g[3][1] and g not in end_gate]
    add(len(ext_gates) == len(EXT_FRAMES)
        and all([n[1][:2] for n in g[4][1]] == [["HideEffectFromOwner", FX_BEAM_MAIN]] for g in ext_gates),
        "S14 每个延长槽的 else 分支必须收掉大激光")
    glow = [c for c in C.commands(tree, "ShowEffect") if c[1] == "cannon_cooldown"]
    add(len(glow) == 2, f"S14 收炮余晖应有 2 处（f{COOLDOWN_FRAME} 提前 + f{BEAM_END_FRAME} 打完），实得 {len(glow)}")
    # ---- S12（R-m6）：终幕无条件，树里不再有任何 ConditionalsChangeSkillFlag
    flags = C.commands(tree, "ConditionalsChangeSkillFlag")
    add(not flags, f"S12 终幕应无条件，树里不该再有 ConditionalsChangeSkillFlag: {[f[1] for f in flags]}")
    fin_plan = next(h for h in sk["hitareas"] if h["id"] == "HA_finale")
    add("gate" not in fin_plan, "plan HA_finale 仍带 gate（方案与实现不一致）")
    # ---- S13（R-m10）：延长段判定寿命必须 > 帧距，相邻段重叠
    ext_plan = next(h for h in sk["hitareas"] if h["id"] == "HA_ext")
    add(list(ext_plan["frames"]) == list(EXT_FRAMES) and ext_plan["lifetime"] == EXT_LIFETIME,
        f"S13 plan 延长槽 {ext_plan.get('frames')}/{ext_plan.get('lifetime')} != kit {list(EXT_FRAMES)}/{EXT_LIFETIME}")
    # 第三轮 D2 把「重炮展开」从 360 帧（6 s）提到 720 帧（12 s）⇒ 语义反转：
    # 原来「首槽必须晚于基础时长」保证无队友续能时一次都不触发；现在基础时长覆盖整条延长链，
    # 判据改成「整条延长链必须落在基础时长以内」（否则又出现自己发一次就断掉的空档）。
    # 延长槽本身仍被 DCUnique 门包住（上面 slots 已逐个断言），队友续能只是把 12 s 再刷满。
    cannon_frames = int(UNIQUE_META[UID_CANNON]["duration"])
    ext_end = EXT_FRAMES[-1] + EXT_LIFETIME
    add(ext_end <= cannon_frames,
        f"S13 延长链结束帧 {ext_end} 必须 ≤「重炮展开」基础时长 {cannon_frames}（作者第三轮 D2：12 s）")
    gaps = [b - a for a, b in zip(EXT_FRAMES, EXT_FRAMES[1:])]
    add(all(EXT_LIFETIME - g >= 5 for g in gaps),
        f"S13 延长段判定区重叠不足 5 帧（寿命 {EXT_LIFETIME}, 帧距 {gaps}）—— 会在段与段之间漏掉伤害窗口")
    ext_has = [c for c in C.commands(tree, "CreateHitArea")
               if _tag(c[9]) == "Rectangle" and c[9][1][0]["min"] == LLL_RECT_WIDTH
               and c[13] == ["SpecifyHitAreaLifetimeDirectly", EXT_LIFETIME]]
    add(len(ext_has) == len(EXT_FRAMES), f"S13 寿命 {EXT_LIFETIME} 的 LLL 判定区数 {len(ext_has)} != {len(EXT_FRAMES)}")
    facts["extension"] = {"frames": list(EXT_FRAMES), "lifetime": EXT_LIFETIME,
                          "overlap_frames": [EXT_LIFETIME - g for g in gaps],
                          "finale_end": FINALE_FRAME + FINALE_LIFETIME,
                          "cannon_handle_frames": int(UNIQUE_META[UID_CANNON]["duration"])}

    # ---- S14（第二轮）：大激光整段只有一个光束实例，且没有任何同族光柱同屏
    main = [c for c in C.commands(tree, "ShowEffect") if c[1] == FX_BEAM_MAIN]
    add(len(main) == 1, f"S14 {FX_BEAM_MAIN} 应恰好 1 条 ShowEffect，实得 {len(main)}")
    if len(main) == 1:
        mb = main[0]
        want_mb = {3: BALL, 5: ["SpecifyEffectLifetimeDirectly", BIG_BEAM_LIFETIME], 6: GH,
                   9: PI, 10: True, 11: False, 12: ["None"]}
        for idx, value in want_mb.items():
            if strict_diff(mb[idx], value):
                probs.append(f"S14 大激光 ShowEffect p{idx} {mb[idx]!r} != {value!r}")
        add(str(mb[2][1]).endswith("/enemy_shot_laser_lll_yellow"),
            f"S14 大激光贴图应是 lll 族: {mb[2][1]!r}")
    add(BIG_BEAM_LIFETIME == EXT_FRAMES[-1] + EXT_LIFETIME - BIG_BEAM_FRAME,
        f"S14 大激光寿命 {BIG_BEAM_LIFETIME} != 最后一个延长槽结束帧 {EXT_FRAMES[-1] + EXT_LIFETIME} - {BIG_BEAM_FRAME}")
    hides = [c for c in C.commands(tree, "HideEffectFromOwner") if c[1] == FX_BEAM_MAIN]
    add(len(hides) == 2 + len(EXT_FRAMES),
        f"S14 HideEffectFromOwner({FX_BEAM_MAIN}) 应有 {2 + len(EXT_FRAMES)} 处"
        f"（根块 1 + 收炮 1 + 延长槽 {len(EXT_FRAMES)}），实得 {len(hides)}")
    # 终幕不再用激光族贴图（同贴图叠在还在 fade 的 LLL 上＝拍频）。
    # 审查 R2-m4：终幕形态是本轮顺带的观感改动（上一轮是与大激光同宽的光柱），且 scale 9 高于官方
    # 同素材 27 处引用的最大值 2.0 ⇒ 把素材 / 寿命 / scale 一起钉死，防止以后无声漂移；
    # 作者若要改回光柱终幕，见 verify.md open item O10（起始帧必须 ≥ 大激光 gone 帧）。
    fin_fx = [c for c in C.commands(tree, "ShowEffect") if c[1] == FX_FINALE]
    add(len(fin_fx) == 1 and _tag(fin_fx[0][2]) == "ResolveByElement",
        f"S14 终幕演出应是 ResolveByElement 过载闪光而非激光族: {fin_fx}")
    if len(fin_fx) == 1:
        want_fin = {2: ["ResolveByElement", CHARGE, 255], 3: BALL,
                    5: ["SpecifyEffectLifetimeDirectly", FINALE_LIFETIME], 6: ["AB"],
                    12: ["Some", [{"min": FINALE_FLASH_SCALE, "max": FINALE_FLASH_SCALE}]]}
        for idx, value in want_fin.items():
            if strict_diff(fin_fx[0][idx], value):
                probs.append(f"S14 终幕 ShowEffect p{idx} {fin_fx[0][idx]!r} != {value!r}")
    facts["finale_fx"] = {"asset": CHARGE, "lifetime": FINALE_LIFETIME, "scale": FINALE_FLASH_SCALE,
                          "official_scale_max": OFFICIAL_CHARGE_SCALE_MAX}
    # ---- S15（第三轮 §3.3）：charge 系 scale 必须落在官方同素材档位，并与 plan 原值可追溯
    probs.extend(charge_scale_problems(plan))
    # 树里实际写进去的 charge scale（防「常量改了、树没跟着改」）
    charge_fx = {c[1]: c[12] for c in C.commands(tree, "ShowEffect")
                 if _tag(c[2]) == "ResolveByElement" and c[2][1] == CHARGE}
    want_charge = {"charge_core": [s for (_n, _f, _w, _i, _fam, s, _sh) in STAGES if s is not None],
                   FX_FINALE: [FINALE_FLASH_SCALE]}
    for label, scales in want_charge.items():
        got = [c[12] for c in C.commands(tree, "ShowEffect")
               if c[1] == label and _tag(c[2]) == "ResolveByElement" and c[2][1] == CHARGE]
        want = [["Some", [{"min": s, "max": s}]] for s in scales]
        add(not strict_diff(got, want), f"S15 {label} 的 charge scale {got!r} != {want!r}")
    facts["charge_scales"] = {"stages": [s for (_n, _f, _w, _i, _fam, s, _sh) in STAGES],
                              "finale": FINALE_FLASH_SCALE, "official": list(OFFICIAL_CHARGE_SCALES),
                              "tree_last": charge_fx.get(FX_FINALE)}
    census = laser_beam_census(tree)
    overlaps = beam_overlap_problems(tree)
    add(not overlaps, "S14 " + "; ".join(overlaps))
    facts["beam_census"] = census
    facts["beam_overlaps"] = overlaps
    facts["laser_end_frames"] = dict(LASER_END_FRAMES)
    # ---- 倍率：每段 CNA p6 == plan（含每层 vlv），且带 vlv 的 CNA 都有对应的 Bind
    p6_key = "lv2_p6" if level == "2" else "lv1_p6"
    blocks = sk["multipliers"]["blocks"]
    got_terms: dict[str, int] = {}
    for c in C.commands(tree, "CreateNormalAttack"):
        for name, block in blocks.items():
            if not strict_diff(c[6], [block[p6_key]]):
                got_terms[name] = got_terms.get(name, 0) + 1
    want_counts = {"missile": 1, "s": 1, "l": 1, "ll": 1, "lll": 1 + len(EXT_FRAMES), "finale": 1}
    add(got_terms == want_counts, f"倍率项计数 {got_terms} != {want_counts}")
    binds = C.commands(tree, "BindConditionAccumulationVariable")
    add(len(binds) == sum(want_counts.values()),
        f"Bind 数 {len(binds)} != 带 vlv 的 CNA 数 {sum(want_counts.values())}")
    add(all(b[1:] == [-17, VID_ENGINE, ["DCUnique", int(UID_ENGINE)], ENGINE_DIVISOR, ENGINE_CAP] for b in binds),
        "Bind 参数与「引擎启动」不符")
    facts["multiplier_totals"] = sk["multipliers"]["totals"]

    # ---- S16（审查 R3-m5）：终幕必须与第三段 charge_core 在屏幕上可区分
    core_fx = [c for c in C.commands(tree, "ShowEffect") if c[1] == "charge_core"]
    bad_life = [c[5] for c in core_fx if c[5] != ["SpecifyEffectLifetimeDirectly", CHARGE_CORE_LIFETIME]]
    add(not bad_life, f"S16 charge_core 寿命 {bad_life} != {CHARGE_CORE_LIFETIME}（官方同素材 15–40 帧）")
    last_core_frame = STAGES[-1][1]
    core_gap = FINALE_FRAME - (last_core_frame + CHARGE_CORE_LIFETIME)
    add(core_gap >= 15,
        f"S16 第三段 charge_core 结束帧 {last_core_frame + CHARGE_CORE_LIFETIME} 与终幕 f{FINALE_FRAME} "
        f"只隔 {core_gap} 帧（需 ≥15）—— 同素材紧挨着放，终幕读不出来")
    # 终幕是全树唯一的最大档 charge（charge_scale_problems 已断言严格大于）；这里再钉一次树里的实际值
    fin_scale = [c[12] for c in C.commands(tree, "ShowEffect") if c[1] == FX_FINALE]
    core_scales = [c[12][1][0]["max"] for c in core_fx]
    add(fin_scale == [["Some", [{"min": FINALE_FLASH_SCALE, "max": FINALE_FLASH_SCALE}]]]
        and all(v < FINALE_FLASH_SCALE for v in core_scales),
        f"S16 终幕 scale {fin_scale} 必须严格大于全部 charge_core {core_scales}")
    facts["finale_layers"] = {
        "ring": {"label": FX_FINALE, "asset": CHARGE, "scale": FINALE_FLASH_SCALE,
                 "frame": FINALE_FRAME, "lifetime": FINALE_LIFETIME},
        "last_charge_core": {"frame": last_core_frame, "scale": STAGES[-1][5],
                             "lifetime": CHARGE_CORE_LIFETIME, "gap_to_finale": core_gap},
        "cooldown_glow": {"label": "cannon_cooldown", "asset": SR_SRC + "laser_200px_end",
                          "scale": COOLDOWN_SCALE,
                          "early_frame": COOLDOWN_FRAME, "beam_end_frame": BEAM_END_FRAME,
                          "gates": "两条门条件相反 ⇒ 一次发动恰好播一次"}}

    # ---- S17（审查 R3-M1）：D2 让延长链默认全触发，段数/伤害量级必须算出来，不能只写「手感」
    dmg = damage_census(tree)
    facts["damage_census"] = dmg
    # 自校验：census 的「无条件」那一堆必须逐值等于 plan 声明的总倍率 —— plan 的口径就是
    # 「导弹 4 跳 + 四段各 6 跳 + 终幕 1 跳」，不含延长链。对得上才说明段数/倍率的算法没走偏。
    tot = sk["multipliers"]["totals"]
    want_pair = ({"mult": tot["lv2_full_with_missile"], "stack": tot["per_stack_lv2"]} if level == "2"
                 else {"mult": tot["lv1_with_missile"], "stack": tot["per_stack_lv1"]})
    add(abs(dmg["ungated"]["mult_max"] - want_pair["mult"]) < 1e-6
        and abs(dmg["ungated"]["per_stack_max"] - want_pair["stack"]) < 1e-6,
        f"S17 census 无条件总倍率 {dmg['ungated']} != plan totals {want_pair}")
    add(abs(dmg["gated_by_cannon"]["mult_max"]
            - tot["extension_slot_lv2_max"] * len(EXT_FRAMES)) < 1e-6 or level != "2",
        f"S17 census 延长链总倍率 {dmg['gated_by_cannon']['mult_max']} "
        f"!= plan extension_slot_lv2_max × {len(EXT_FRAMES)}")
    add(dmg["gate_always_open_without_ally"] == (EXT_FRAMES[-1] + EXT_LIFETIME <= cannon_frames),
        f"S17 延长链门可达性 {dmg['gate_always_open_without_ally']} 与 S13 判据不自洽")
    add(dmg["cooldown_branch_reachable"] == (COOLDOWN_FRAME >= cannon_frames),
        "S17 收炮 else 分支可达性与「重炮展开」时长不自洽")
    # 收炮余晖那条 else 分支在 720 帧下恒不执行（f362 < 720）⇒ 素材必须在别处被用到，
    # 否则作者又会在同一轮里看到「少了一个特效」（R3-m5 的第二层正是为此加的）。
    cooldown_uses = [c for c in C.commands(tree, "ShowEffect")
                     if _tag(c[2]) == "SpecifyEffectDirectly" and str(c[2][1]).endswith("laser_200px_end")]
    add(dmg["cooldown_branch_reachable"] or len(cooldown_uses) >= 2,
        f"S17 提前收炮 else 分支不可达（重炮展开 {cannon_frames} 帧 > 收炮帧 {COOLDOWN_FRAME}），"
        f"而 laser_200px_end 只在那条死分支里被引用 {len(cooldown_uses)} 次 —— 该素材永远不上屏")
    # f682 那条必须落在「重炮展开」窗口内，否则它也会变成死码
    add(BEAM_END_FRAME < cannon_frames,
        f"S17 打完收炮帧 {BEAM_END_FRAME} 必须 < 重炮展开时长 {cannon_frames}，"
        f"否则 f{COOLDOWN_FRAME} 与 f{BEAM_END_FRAME} 两条余晖门会同时关上 —— 余晖一次都不播")
    return probs, facts


def hitarea_max_hits(lifetime, interval, cap) -> int:
    """一个判定区在自身寿命内最多能打出的段数（单体、全程贴脸的上界）。

    ``CalculatedUsingMaxNumOfHits(n)`` ⇒ 客户端把间隔算成 lifetime/n，段数就是 n；
    ``SpecifyMinHitIntervalDirectly(iv)`` ⇒ 命中帧 t = 0, iv, 2iv, … < lifetime，
    共 ``floor((lifetime-1)/iv)+1`` 段，再被 ``Some(cap)`` 的最大命中数钳一次。
    """
    if _tag(interval) == "CalculatedUsingMaxNumOfHits":
        n = int(interval[1])
        return min(n, cap) if cap else n
    if _tag(interval) == "SpecifyMinHitIntervalDirectly":
        iv = int(interval[1])
        n = ((int(lifetime) - 1) // iv) + 1 if iv > 0 else 1
        return min(n, cap) if cap else n
    raise KitError(f"未知的命中间隔构造 {interval!r}")


def _direct_commands(node, name: str) -> list[list]:
    """在 ``node`` 子树里找 ``name`` 命令，但**不下潜进嵌套的 CreateHitArea**。

    判定区的 on_hit 里可以再建判定区（雷达 → 导弹），那一层有自己的段数与倍率，
    不能算进外层；``damage_census`` 靠这条边界把每个判定区的倍率分干净。
    """
    out: list[list] = []

    def walk(n):
        if not isinstance(n, list):
            return
        if _tag(n) == "Command" and isinstance(n[1], list) and n[1]:
            c = n[1]
            if c[0] == "CreateHitArea":
                return
            if c[0] == name:
                out.append(c)
                return
        for child in n:
            walk(child)

    walk(node)
    return out


def damage_census(tree) -> dict[str, Any]:
    """按帧摊开每个判定区的**最大**段数与倍率，并分成「无条件」与「被重炮展开门包住」两堆。

    审查 R3-M1（2026-09-17）：第三轮 D2 把「重炮展开」从 360 帧提到 720 帧，而技能自己在 f0 就
    ``CreateCondition -17 ACUnique 13999302``（层数 1，时长只看 ``unique_condition`` c3，
    记忆卡 wf-acunique-value-is-stack-count）⇒ 5 个延长槽的门 f372/432/492/552/612 全部落在
    窗口内，**不需要队友续能就必定全触发**。上一轮（360 帧）首槽 f372 > 360 ⇒ 一段都不触发。
    也就是说 D2 不只是「持续时间 6 s → 12 s」，它同时把技能的 DSL 侧伤害上界翻了一倍多。
    这个函数把量级算出来放进 gates 的 facts，作者据此拍板，不用再靠形容词。

    口径与 ``plan.json`` 的 ``multipliers.totals`` 一致：档 2 满级、单体、每个判定区吃满最大命中数。
    ``per_stack`` = 每层「引擎启动」的增量（CNA p6 的 ``vlv[vid=1].max``）。
    """
    rows: list[dict[str, Any]] = []

    def visit(node, t: int, gated: bool):
        if not isinstance(node, list):
            return
        tag = _tag(node)
        if tag == "Event" and isinstance(node[1], list) and node[1] and node[1][0] == "Wait":
            visit(node[1][3], t + int(node[1][1]), gated)
            return
        if tag == "Command" and isinstance(node[1], list) and node[1]:
            c = node[1]
            if c[0] == "ConditionalsConditionAccumulationNumber":
                visit(c[3], t, True)          # then = 「重炮展开」还在
                visit(c[4], t, gated)         # else = 已消失（收炮路径）
                return
            if c[0] == "CreateHitArea":
                life = c[13][1] if isinstance(c[13], list) and len(c[13]) > 1 else None
                cap = None
                if _tag(c[15]) == "Some":
                    cap = int(c[15][1][0]["max"])
                hits = hitarea_max_hits(life, c[14], cap)
                # 只收**直属**本判定区 on_hit 的 CNA：遇到嵌套 CreateHitArea 就停，
                # 否则雷达会把嵌在它 on_hit 里的导弹倍率算到自己头上（导弹有自己的判定区和段数）。
                mult = per_stack = 0.0
                for n in _direct_commands(c[23], "CreateNormalAttack"):
                    for term in n[6]:
                        mult += float(term["max"])
                        for v in term.get("vlv", []):
                            if int(v["vid"]) == VID_ENGINE:
                                per_stack += float(v["max"])
                rows.append({"frame": t, "gated": gated, "shape": _tag(c[9]),
                             "width": c[9][1][0]["max"] if len(c[9]) > 1 and isinstance(c[9][1], list) else None,
                             "lifetime": life, "cap": cap, "max_hits": hits,
                             "mult_per_hit": round(mult, 4),
                             "mult_max": round(mult * hits, 4),
                             "per_stack_max": round(per_stack * hits, 4)})
                visit(c[20], t, gated)       # on_create
                visit(c[23], t, gated)       # on_hit：导弹判定区嵌在雷达的 on_hit 里
                return
        for child in node:
            visit(child, t, gated)

    visit(tree, 0, False)
    rows.sort(key=lambda r: (r["frame"], r["gated"]))

    def total(sel):
        picked = [r for r in rows if sel(r)]
        return {"hitareas": len(picked), "hits": sum(r["max_hits"] for r in picked),
                "mult_max": round(sum(r["mult_max"] for r in picked), 4),
                "per_stack_max": round(sum(r["per_stack_max"] for r in picked), 4)}

    base = total(lambda r: not r["gated"])
    gate = total(lambda r: r["gated"])
    both = total(lambda r: True)
    cannon_frames = int(UNIQUE_META[UID_CANNON]["duration"])
    gate_frames = [r["frame"] for r in rows if r["gated"]]
    # 技能自己在 f0 刻 1 层「重炮展开」⇒ 门在 [0, cannon_frames) 内恒开；晚于它才需要队友续能
    always_open = bool(gate_frames) and max(gate_frames) < cannon_frames
    return {"rows": rows, "ungated": base, "gated_by_cannon": gate, "if_gate_open": both,
            "cannon_condition_frames": cannon_frames,
            "gate_frames": sorted(set(gate_frames)),
            "gate_always_open_without_ally": always_open,
            "cooldown_branch_reachable": COOLDOWN_FRAME >= cannon_frames,
            "note": "口径 = 档2 满级 + 单体全程吃满每个判定区最大命中数；"
                    "ungated = 一定打出来的，gated_by_cannon = 被「重炮展开」门包住的延长链，"
                    "gate_always_open_without_ally=true 表示无队友续能也全触发（D2 的直接后果）"}


def ball_hold_problems(tree) -> list[str]:
    """S18 门禁：树里不许有任何把球固定住的命令（``StopBall`` / ``SuppressBallActivity``）。

    作者 2026-09-21「取消技能释放后的后摇……去掉固定的这一段」。首发 kit 写过一条 10 帧的
    ``StopBall``，已整条删掉；这条门禁保证重跑 ``--step kit`` / 改蓝图时带不回来。
    根头 ``tree[1]`` 也必须是 1(NONE)——2/3(STOP/MOVE) 会通过 ``updateMovementId`` 抢走球的
    移动权，即使没有 StopBall 也会互相打断队友的位移技能。
    """
    import wf_seasonal7_common as C
    probs = [f"S18 树里仍有 {name}: {[c[1:] for c in C.commands(tree, name)]}"
             for name in BALL_HOLD_COMMANDS if C.commands(tree, name)]
    if isinstance(tree, list) and len(tree) > 1 and tree[1] != 1:
        probs.append(f"S18 根头 movementPriority {tree[1]} != 1(NONE)")
    return probs


def template_stopball_drift(template) -> list[str]:
    """母本 ``super_robot_<lv>`` 的 StopBall 原形态核对（只读对照，不改我们的树）。

    我们的树已经没有 StopBall，所以 ``template_derivation_problems`` 没法再逐值比它；
    这条单独保留，免得母本某天变了而我们毫无察觉。
    """
    import wf_seasonal7_common as C
    stops = [c[1:] for c in C.commands(template, "StopBall")]
    if stops != [TEMPLATE_STOPBALL]:
        return [f"母本 StopBall {stops} != {TEMPLATE_STOPBALL}"]
    return []


def dsl_quick_problems(tree) -> list[str]:
    """kit 内快速门禁（完整签名差分在 impl/tekuto/gates.py）。"""
    import wf_client_legality as LG
    import wf_dsl
    probs = []
    probs += LG.action_dsl_element_problems(tree, ELEMENT)
    probs += LG.action_dsl_subject_binding_problems(tree)
    probs += LG.action_dsl_hit_area_target_problems(tree)
    probs += wf_dsl.player_side_dsl_problems(tree)
    probs += donothing_problems(tree)
    probs += ball_hold_problems(tree)
    return probs


# ================================================================ laser_lll「无头块」修复（第三轮 A）
# 审查 R3-m4（2026-09-17）：这段修复逻辑原本 import 自
# ``revision3-20260916/fx/lll_head_patch.py``——那个目录被 ``.gitignore:56 /work/`` 忽略，
# ``git ls-files work/`` = 0。被 git 跟踪的生产 kit 依赖未跟踪、且放在带日期 revision 目录里的
# 可执行代码 ⇒ 该目录一旦按项目惯例冻结/归档/清理，``--step kit`` 直接 KitError（整包重建不了、
# 闪烁修复一并丢失），单元测试也变成 error 而不是 skip。
# 现在纯函数全部内联到 kit；``fx/lll_head_patch.py`` 保留为取证副本，
# ``lll_patch_forensic_drift()`` 在它存在时逐常量比对，缺失时返回 present=False 而不报错。

LLL_ANIM_GRAPHICS = 2          # g[2] = 动画层（g[0] 场景 → g[1] 正/镜像两份 → g[2]）
LLL_BLOCK_LEN = 3
LLL_BAD_START = 9              # 坏块在 g[2] 里的起始帧索引（0-based）
LLL_DEFAULT_DONOR = 15         # idx 15–17：与相邻 12–14 同宽（x∈[-87,0]），接续最平
LLL_BAD_IMAGES = ("o", "p", "q", "r")             # 坏块独占的图（修复后成为未引用项，无害）
LLL_MIRROR = 2                 # g[1] 把 g[2] 画两份（正 + 镜像）


class LllPatchError(KitError):
    pass


def _lll_u32(v) -> int:
    return int(v) & 0xFFFFFFFF


def _lll_strip_start(strip: dict) -> int:
    return _lll_u32(strip["s"]) & 0x3FFFFFFF


def _lll_strip_kind(strip: dict) -> int:
    return _lll_u32(strip["s"]) >> 30


def _lll_span(strip: dict) -> int:
    total = 0
    for kf in strip["l"]:
        t = kf.get("t")
        total += (int(t) & 0xFFFF) if t else 1
    return total


def lll_block_strips(strips: list[dict], start: int) -> list[int]:
    return [i for i, s in enumerate(strips) if _lll_strip_kind(s) == 0 and _lll_strip_start(s) == start]


def lll_is_patched(tree: dict) -> bool:
    """坏块已被换掉 ⇒ 块内不再出现 o/p/q/r 这四张图。"""
    g = tree["g"][LLL_ANIM_GRAPHICS]
    names = {tree["i"][int(s["i"])]["p"].rsplit("/", 1)[-1]
             for s in g["s"] if _lll_strip_start(s) == LLL_BAD_START and _lll_strip_kind(s) == 0}
    return not (names & set(LLL_BAD_IMAGES))


def lll_repair_tree(tree: dict, donor_start: int = LLL_DEFAULT_DONOR) -> tuple[dict, dict[str, Any]]:
    """把 g[2] 的坏块（起始帧 9）换成 ``donor_start`` 块的副本。幂等；带硬断言。

    根因见 ``revision3-20260916/fx/forensics.md`` §1：官方母本 ``enemy_shot_laser_lll_yellow.parts``
    的动画层 g[2]（33 帧）是 11 个 3 帧翻页块，其中块 idx 9–11（图 o/p/q/r/p）**只覆盖 y∈[153,345]**，
    没有任何 y<153 的图元；timeline 的 ``loop`` = 播放头 7–18 正好把它圈进循环 ⇒ 每 12 帧掉 3 帧
    光柱上段 153 单位（×ShowEffect 根 s=6 = 918 px）。
    """
    tree = copy.deepcopy(tree)
    g = tree["g"][LLL_ANIM_GRAPHICS]
    strips: list[dict] = g["s"]
    report: dict[str, Any] = {"donor_start": donor_start, "graphics": LLL_ANIM_GRAPHICS}

    if lll_is_patched(tree):
        report["status"] = "already-patched"
        return tree, report

    bad = lll_block_strips(strips, LLL_BAD_START)
    donor = lll_block_strips(strips, donor_start)
    if not bad:
        raise LllPatchError(f"no image strips start at frame {LLL_BAD_START}")
    if not donor:
        raise LllPatchError(f"no donor strips start at frame {donor_start}")
    bad_names = [tree["i"][int(strips[i]["i"])]["p"].rsplit("/", 1)[-1] for i in bad]
    if sorted(set(bad_names)) != sorted(set(LLL_BAD_IMAGES)):
        raise LllPatchError(f"bad block images changed, refusing: {bad_names}")
    for i in donor:
        if _lll_span(strips[i]) != LLL_BLOCK_LEN:
            raise LllPatchError(f"donor strip {i} span {_lll_span(strips[i])} != {LLL_BLOCK_LEN}")

    new_strips = [copy.deepcopy(strips[i]) for i in donor]
    for st in new_strips:
        st["s"] = LLL_BAD_START                  # kind 0 ⇒ s 就是起始帧（高 2 位为 0）
    bad_set, first = set(bad), min(bad)
    rebuilt: list[dict] = []
    for j, st in enumerate(strips):              # 保持「同帧内的绘制顺序 = strip 顺序」
        if j == first:
            rebuilt.extend(new_strips)
        if j not in bad_set:
            rebuilt.append(st)
    g["s"] = rebuilt

    # ---- 断言：段内不越界；每张图的同帧最大并发不超过 imageMaxNumbers
    for st in g["s"]:
        if _lll_strip_kind(st) == 0 and _lll_strip_start(st) + _lll_span(st) > int(g["t"]):
            raise LllPatchError(f"image strip overflows segment: start={_lll_strip_start(st)} "
                                f"span={_lll_span(st)} total={g['t']}")
    per_frame: dict[int, dict[int, int]] = {}
    for st in g["s"]:
        if _lll_strip_kind(st) != 0:
            continue
        for f in range(_lll_strip_start(st), _lll_strip_start(st) + _lll_span(st)):
            per_frame.setdefault(f, {}).setdefault(int(st["i"]), 0)
            per_frame[f][int(st["i"])] += 1
    caps = tree["a"]
    over = []
    for f, counts in per_frame.items():
        for idx, n in counts.items():
            if n * LLL_MIRROR > int(caps[idx]):
                over.append({"frame": f, "image": idx, "need": n * LLL_MIRROR, "cap": int(caps[idx])})
    if over:
        raise LllPatchError(f"imageMaxNumbers exceeded: {over[:5]}")

    report.update(status="patched", replaced_strips=len(bad), inserted_strips=len(new_strips),
                  replaced_images=sorted(set(bad_names)),
                  donor_images=[tree["i"][int(st["i"])]["p"].rsplit("/", 1)[-1] for st in new_strips])
    return tree, report


_LLL_FORENSIC_CONSTS = {"ANIM_GRAPHICS": "LLL_ANIM_GRAPHICS", "BLOCK_LEN": "LLL_BLOCK_LEN",
                        "BAD_START": "LLL_BAD_START", "DEFAULT_DONOR": "LLL_DEFAULT_DONOR"}


def lll_patch_forensic_drift(root: Path) -> dict[str, Any]:
    """取证副本 ``fx/lll_head_patch.py`` 若在本机，逐常量比对；不在则 present=False（不报错）。

    kit 不再 import 它 —— 这里只做「两份说法是否还一致」的单向核对，
    免得以后只改其中一份，留下互相矛盾的证据。
    """
    import re
    path = root / REV3_FX_DIR / "lll_head_patch.py"
    info: dict[str, Any] = {"path": str(path), "present": path.is_file(), "drift": []}
    if not info["present"]:
        return info
    text = path.read_text(encoding="utf-8")
    here = globals()
    for name, kit_name in _LLL_FORENSIC_CONSTS.items():
        m = re.search(r"^" + name + r"\s*=\s*(\d+)", text, re.M)
        if m is None:
            info["drift"].append(f"取证副本缺常量 {name}")
        elif int(m.group(1)) != here[kit_name]:
            info["drift"].append(f"取证副本 {name}={m.group(1)} != kit {here[kit_name]}")
    m = re.search(r"^BAD_IMAGES\s*=\s*\(([^)]*)\)", text, re.M)
    if m is None:
        info["drift"].append("取证副本缺 BAD_IMAGES")
    else:
        got = tuple(x.strip().strip("'" + chr(34)) for x in m.group(1).split(",") if x.strip())
        if got != LLL_BAD_IMAGES:
            info["drift"].append(f"取证副本 BAD_IMAGES={got} != kit {LLL_BAD_IMAGES}")
    return info


def _lll_block_images(tree, start: int) -> list[str]:
    g = tree["g"][LLL_ANIM_GRAPHICS]
    return [tree["i"][int(g["s"][i]["i"])]["p"].rsplit("/", 1)[-1]
            for i in lll_block_strips(g["s"], start)]


def repair_lll_head(ctx, pack) -> dict[str, Any]:
    """特效族克隆之后必须跑：官方母本 ``laser_lll`` 的块 idx 9–11 缺整根光柱上段 153 单位，
    而 timeline 的 loop 正好圈住它 ⇒ 412 帧寿命掉 102 帧（5 Hz 闪）。用同族块 idx 15–17 整体替换。

    ``--step kit`` 每次都重新克隆特效族（框架只有 png_transform 钩子、没有 parts 钩子），
    所以这个修复**必须**由 kit 在克隆之后重做一遍，否则每次构建都被还原（forensics.md §2.5）。
    """
    path = pack.pkg_path("common", REV3_LLL_PARTS)
    if not path.is_file():
        raise KitError(f"包内缺少 {REV3_LLL_PARTS}（特效族克隆失败？）")
    before_raw = path.read_bytes()
    tree = ctx.amf_parse(before_raw)
    before_bad = _lll_block_images(tree, LLL_BAD_START)
    fixed, report = lll_repair_tree(tree)
    wrote = False
    if report["status"] == "patched":
        ctx.write_asset("common", REV3_LLL_PARTS, ctx.amf_bytes(fixed), owner="effects")
        wrote = True
    # ---- 门禁：写回后逐条复核（负向对照 = 不接这个钩子，下面第一条必红）
    check = ctx.amf_parse(pack.pkg_path("common", REV3_LLL_PARTS).read_bytes())
    if not lll_is_patched(check):
        raise KitError("laser_lll 无头块修复未生效：坏块里仍有 o/p/q/r")
    got = _lll_block_images(check, LLL_BAD_START)
    donor = _lll_block_images(check, LLL_DEFAULT_DONOR)
    if got != donor:
        raise KitError(f"laser_lll 坏块 {got} != 供体块 {donor}（供体块 idx {LLL_DEFAULT_DONOR}）")
    g = check["g"][LLL_ANIM_GRAPHICS]
    over = [i for i, st in enumerate(g["s"])
            if _lll_strip_kind(st) == 0 and _lll_strip_start(st) + _lll_span(st) > int(g["t"])]
    if over:
        raise KitError(f"laser_lll 修复后有 image strip 越段（客户端 #1125）: {over}")
    forensic = lll_patch_forensic_drift(ctx.root)
    if forensic["drift"]:
        raise KitError("laser_lll 取证副本与 kit 常量漂移: " + "; ".join(forensic["drift"]))
    return {"logical": REV3_LLL_PARTS, "status": report["status"], "wrote": wrote,
            "bad_block_before": before_bad, "bad_block_after": got, "donor_block": donor,
            "donor_start": LLL_DEFAULT_DONOR, "report": report, "forensic_copy": forensic,
            "sha256_before": hashlib.sha256(before_raw).hexdigest(),
            "sha256_after": hashlib.sha256(pack.pkg_path("common", REV3_LLL_PARTS).read_bytes()).hexdigest(),
            "why": "官方母本缺陷：块 idx 9–11 只覆盖 y∈[153,345]，loop 每 12 帧掉 3 帧炮口"}


# ================================================================ 特效染色钩子

def load_fx_manifest(root: Path) -> tuple[dict[str, Path], dict]:
    """``fx/tekuto/out/manifest.json`` → {源 sheet 逻辑路径: 染色 PNG 文件}；不存在返回 ({}, info)。

    接受形态：顶层 ``{src: file}``，或 ``{"sheets"|"map"|"recolor"|"files": {...}}``，或列表
    ``[{"source"|"src"|"logical": ..., "png"|"file"|"path"|"target": ...}]``。键可以是 sheet
    逻辑路径（``…/<donor>.png``）或族目录（自动补 ``/<donor>.png``）。相对文件路径按 manifest 所在目录解析。
    """
    path = root / FX_MANIFEST_REL
    info: dict[str, Any] = {"manifest": str(path), "present": path.is_file()}
    if not path.is_file():
        return {}, info
    data = json.loads(path.read_text(encoding="utf-8"))
    info["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    entries: list[tuple[str, str]] = []
    container = data
    if isinstance(data, dict):
        for name in ("sheets", "map", "recolor", "files", "mapping"):
            if isinstance(data.get(name), (dict, list)):
                container = data[name]
                break
    if isinstance(container, dict):
        for k, v in container.items():
            if isinstance(v, dict):
                v = v.get("png") or v.get("file") or v.get("path") or v.get("target")
            if isinstance(k, str) and isinstance(v, str) and (k.startswith("battle/effect/")):
                entries.append((k, v))
    elif isinstance(container, list):
        for item in container:
            if not isinstance(item, dict):
                continue
            src = item.get("source") or item.get("src") or item.get("logical") or item.get("source_logical")
            dst = item.get("png") or item.get("file") or item.get("path") or item.get("target")
            if isinstance(src, str) and isinstance(dst, str):
                entries.append((src, dst))
    known_dirs = {src for src, _sub, _fx in FAMILIES}
    mapping: dict[str, Path] = {}
    unknown = []
    for src, file in entries:
        src = src.rstrip("/")
        if not src.endswith(".png"):
            src = f"{src}/{src.rsplit('/', 1)[-1]}.png"
        family_dir = src.rsplit("/", 1)[0]
        if family_dir not in known_dirs or src != f"{family_dir}/{family_dir.rsplit('/', 1)[-1]}.png":
            unknown.append(src)
            continue
        fp = Path(file)
        if not fp.is_absolute():
            fp = path.parent / fp
        if not fp.is_file():
            raise KitError(f"fx manifest points at missing PNG for {src}: {fp}")
        mapping[src] = fp
    if unknown:
        raise KitError(f"fx manifest entries do not match any cloned tekuto family sheet: {unknown}")
    info["entries"] = {k: str(v) for k, v in sorted(mapping.items())}
    return mapping, info


def make_png_transform(sheet_logical: str, png_file: Path, stats: dict):
    import wf_assets
    from PIL import Image, ImageChops

    def transform(img):
        raw = png_file.read_bytes()
        dyed = Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA")
        if dyed.size != img.size:
            raise KitError(f"recolored sheet size {dyed.size} != source {img.size}: {sheet_logical}")
        alpha_diff = ImageChops.difference(dyed.getchannel("A"), img.getchannel("A")).getbbox()
        stats[sheet_logical] = {"file": str(png_file), "sha256": hashlib.sha256(raw).hexdigest(),
                                "size": list(dyed.size), "alpha_changed_bbox": list(alpha_diff) if alpha_diff else None}
        return dyed
    return transform


# ================================================================ 像素小人（Integrate）

def pixel_review_verdict(text: str, key: str = KEY) -> tuple[bool, str]:
    """``pixel/REVIEW.md`` 末尾「修复轮复核」段的结论表里 ``| <key> …`` 行是否判 **PASS**。

    只认该段（初审段已被修复轮取代）；段缺失 / 行缺失 / 非 PASS 一律返回 False 与原因。"""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith("## ") and PIXEL_REVIEW_HEADING in ln), None)
    if start is None:
        return False, f"REVIEW.md 尚无「{PIXEL_REVIEW_HEADING}」段"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    rows = [ln for ln in lines[start:end] if ln.lstrip().startswith("|")
            and ln.strip().strip("|").strip().split(" ")[0] == key]
    if not rows:
        return False, f"「{PIXEL_REVIEW_HEADING}」段没有 {key} 结论行"
    row = rows[0]
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    if not any(c.startswith("**PASS") for c in cells):
        return False, f"{key} 修复轮复核未判 PASS: {row.strip()}"
    return True, row.strip()


def pixel_gate_state(root: Path) -> dict[str, Any]:
    """像素产物是否可装包：复核 PASS + verify.json all_ok + report 门禁全过 + 产物 sha 与 report 一致。"""
    base = root / PIXEL_REL
    state: dict[str, Any] = {"pass": False, "reasons": []}
    review = root / PIXEL_REVIEW_REL
    if review.is_file():
        ok, detail = pixel_review_verdict(review.read_text(encoding="utf-8"))
        state["review"] = detail
        if not ok:
            state["reasons"].append(detail)
    else:
        state["reasons"].append("pixel/REVIEW.md 不存在")
    verify = base / "verify.json"
    report = base / "report.json"
    if not verify.is_file() or not report.is_file():
        state["reasons"].append("pixel verify.json/report.json 缺失")
        return state
    v = json.loads(verify.read_text(encoding="utf-8"))
    r = json.loads(report.read_text(encoding="utf-8"))
    state["verify_all_ok"] = v.get("all_ok") is True
    bad_gates = sorted(k for k, g in (r.get("gates") or {}).items() if not (isinstance(g, dict) and g.get("ok") is True))
    state["report_gates_passed"] = r.get("gates_passed") is True and not bad_gates and bool(r.get("gates"))
    if not state["verify_all_ok"]:
        state["reasons"].append("pixel verify.json all_ok != true")
    if not state["report_gates_passed"]:
        state["reasons"].append(f"pixel report gates not all ok: {bad_gates or r.get('gates_passed')}")
    if r.get("key") != KEY or r.get("code") != TEMPLATE_CODE:
        state["reasons"].append(f"pixel report identity {r.get('key')}/{r.get('code')} != {KEY}/{TEMPLATE_CODE}")
    outputs, sources = {}, {}
    for name in PIXEL_SHEETS:
        file = base / "out" / f"{name}.png"
        rec = (r.get("outputs") or {}).get(name) or {}
        if not file.is_file():
            state["reasons"].append(f"pixel out 缺 {name}.png")
            continue
        sha = hashlib.sha256(file.read_bytes()).hexdigest()
        if sha != rec.get("sha256"):
            state["reasons"].append(f"pixel out {name}.png sha {sha[:12]} != report {str(rec.get('sha256'))[:12]}")
        outputs[name] = {"file": str(file), "sha256": sha}
        src = (r.get("source_files") or {}).get(f"character/{TEMPLATE_CODE}/pixelart/{name}.png") or {}
        sources[name] = src.get("sha256")
    state["outputs"], state["source_sha256"] = outputs, sources
    state["pass"] = not state["reasons"]
    return state


def pixel_sheet_problems(dyed, template) -> list[str]:
    """dyed/template 为 RGBA ndarray：尺寸相同、alpha 逐字节相同、alpha==0 像素 RGBA 逐字节相同。"""
    import numpy as np
    if dyed.shape != template.shape:
        return [f"size {dyed.shape} != template {template.shape}"]
    probs = []
    if not (dyed[..., 3] == template[..., 3]).all():
        probs.append(f"alpha differs at {int((dyed[..., 3] != template[..., 3]).sum())} px")
    clear = template[..., 3] == 0
    if not (dyed[clear] == template[clear]).all():
        probs.append(f"alpha==0 RGBA differs at {int(np.any(dyed[clear] != template[clear], axis=-1).sum())} px")
    return probs


def atlas_bounds_problems(atlas, size: tuple[int, int]) -> list[str]:
    """atlas 条目 x/y/w/h 为 sheet 空间矩形（``r`` 旋转不交换 w/h，母本实测），须落在 sheet 内。"""
    width, height = size
    probs = []
    for item in atlas:
        if not isinstance(item, dict) or "n" not in item:
            probs.append(f"atlas entry malformed: {item!r}"[:120])
            continue
        if item["x"] < 0 or item["y"] < 0 or item["x"] + item["w"] > width or item["y"] + item["h"] > height:
            probs.append(f"atlas rect outside sheet: {item['n']} ({item['x']},{item['y']},{item['w']},{item['h']})")
    return probs


def integrate_pixel(ctx) -> dict[str, Any]:
    """门禁通过时写 2 张染色 sheet（存储态，owner=pixel），重跑幂等；否则 pending 不动包。"""
    import numpy as np
    import wf_assets
    import wf_seasonal7_common as C
    pack = ctx.pack
    state = pixel_gate_state(ctx.root)
    result: dict[str, Any] = {"status": "pending", "gate": state, "sheets": {}}
    if not state["pass"]:
        return result
    subs = C.dir_prefix_map(TEMPLATE_CODE, CODE)
    for name, (atlas_name, meta_names) in PIXEL_SHEETS.items():
        out_raw = Path(state["outputs"][name]["file"]).read_bytes()
        tpl_logical = f"character/{TEMPLATE_CODE}/pixelart/{name}.png"
        _root, tpl_raw, tpl_source = pack.template_asset(tpl_logical)
        tpl_sha = hashlib.sha256(tpl_raw).hexdigest()
        if state["source_sha256"].get(name) not in (None, tpl_sha):
            raise KitError(f"pixel {name}: dyed against template sha {state['source_sha256'][name][:12]}, "
                           f"current template {tpl_sha[:12]}")
        dyed = np.asarray(ctx.png_open(out_raw))
        template = np.asarray(ctx.png_open(tpl_raw))
        probs = pixel_sheet_problems(dyed, template)
        if probs:
            raise KitError(f"pixel {name}: {probs}")
        store = wf_assets.png_encode(out_raw)
        if wf_assets.png_decode(store) != out_raw or store[1:4] != b"png":
            raise KitError(f"pixel {name}: store-form roundtrip failed")
        logical = f"character/{CODE}/pixelart/{name}.png"
        before = pack.pkg_path("common", logical).read_bytes() if pack.pkg_has("common", logical) else None
        ctx.write_asset("common", logical, store, owner="pixel")
        if pack.pkg_path("common", logical).read_bytes() != store:
            raise KitError(f"pixel {name}: readback mismatch")
        height, width = dyed.shape[:2]
        meta: dict[str, Any] = {}
        for meta_name in (atlas_name, *meta_names):
            tpl_meta = f"character/{TEMPLATE_CODE}/pixelart/{meta_name}"
            pkg_meta = f"character/{CODE}/pixelart/{meta_name}"
            expect = ctx.replace_strings(ctx.amf_parse(pack.template_asset(tpl_meta)[1]), subs)
            if f"character/{TEMPLATE_CODE}/" in repr(expect):
                raise KitError(f"pixel {meta_name}: template prefix survived rewrite")
            if meta_name == atlas_name:
                bprobs = atlas_bounds_problems(expect, (width, height))
                if bprobs:
                    raise KitError(f"pixel {meta_name}: {bprobs[:3]}")
            if pack.pkg_has("common", pkg_meta):
                owner = pack.owner_of("common", pkg_meta)
                if owner not in (None, "assets"):
                    raise KitError(f"pixel metadata {pkg_meta} owned by {owner}; metadata must stay template copy")
                if ctx.amf_parse(pack.pkg_path("common", pkg_meta).read_bytes()) != expect:
                    raise KitError(f"pixel metadata {pkg_meta} differs from template (prefix-rewritten)")
                meta[meta_name] = "equal template (prefix rewritten)"
            else:
                meta[meta_name] = "absent (assets will copy template)"
        result["sheets"][name] = {
            "logical": logical, "source_file": state["outputs"][name]["file"],
            "source_sha256": state["outputs"][name]["sha256"], "store_sha256": hashlib.sha256(store).hexdigest(),
            "template": {"logical": tpl_logical, "source": tpl_source, "sha256": tpl_sha},
            "size": [width, height], "changed_rgb_px": int(np.any(dyed[..., :3] != template[..., :3], axis=-1).sum()),
            "previous_package_sha256": None if before is None else hashlib.sha256(before).hexdigest(),
            "metadata": meta,
        }
    result["status"] = "integrated"
    return result


def voice_state(pack) -> dict[str, Any]:
    """语音装包状态（只读）：speech 行引用 22 槽且全部在包内、owner=voice、语音目录无多余文件。"""
    import wf_seasonal7_voice as V
    import wf_seasonal7_common as C
    info: dict[str, Any] = {"status": "pending"}
    speech_logical = "master/character/character_speech.orderedmap"
    refs = []
    if pack.pkg_has("common", speech_logical):
        rows = pack.pkg_flat(speech_logical)
        refs = [cells[4] for cells in C.csv_split(rows[CID])] if CID in rows else []
    info["speech_refs"] = refs
    voice_dir = pack.pkg_path("common", f"character/{CODE}/voice")
    files = sorted(p.relative_to(voice_dir).as_posix() for p in voice_dir.rglob("*") if p.is_file()) \
        if voice_dir.is_dir() else []
    planned = {f"{slot}.mp3" for slot in V.SLOTS}
    info["extra_files"] = sorted(set(files) - planned)
    info["missing_slots"] = sorted(planned - set(files))
    not_voice = sorted(f for f in planned & set(files)
                       if pack.owner_of("common", f"character/{CODE}/voice/{f}") != "voice")
    info["not_owned_by_voice"] = not_voice
    speech_ok = sorted(refs) == sorted([*V.HOME_SLOTS, "ally/join", "ally/evolution"])
    info["speech_rows_generated"] = speech_ok
    if speech_ok and not info["extra_files"] and not info["missing_slots"] and not not_voice:
        info["status"] = "packed"
    return info


# ================================================================ 设计读取

def load_design(root: Path) -> dict:
    path = root / DESIGN_REL
    design = json.loads(path.read_text(encoding="utf-8"))
    ident = design.get("identity", {})
    if design.get("status") != "final" or design.get("key") != KEY:
        raise KitError(f"design not final/{KEY}: status={design.get('status')} key={design.get('key')}")
    if str(ident.get("cid")) != CID or ident.get("code") != CODE or int(ident.get("element")) != ELEMENT:
        raise KitError(f"design identity mismatch: {ident.get('cid')}/{ident.get('code')}/{ident.get('element')}")
    if design.get("pf_override") is not None or design.get("dash") is not None:
        raise KitError("tekuto design declares pf_override/dash; kit does not implement them")
    if design.get("unique_conditions"):
        raise KitError("tekuto design declares unique_conditions; kit does not implement them")
    return design


def design_ability_rows(design: dict) -> dict[str, list[list[str]]]:
    out = {}
    for slot in range(1, 7):
        key = design["ability_keys"][f"slot{slot}"]["key"]
        out[key] = [list(rec["row"]) for rec in design["abilities"][f"slot{slot}"]]
    return out


def design_leader_rows(design: dict) -> list[list[str]]:
    return [list(rec["row"]) for rec in design["leader"]]


def donor_reconstruction(ctx, design: dict) -> list[dict]:
    """按设计 donor + edits 从官方/live 复算每一行，与设计定稿行比对（live donor 漂移时仅记录）。"""
    results = []
    live_cache: dict[str, dict] = {}

    def donor_row(spec: str, table: str):
        src, rest = spec.split(":", 1)
        key = rest.split("[", 1)[1].split("]", 1)[0]
        idx = int(rest.rsplit("#", 1)[1])
        logical = f"master/ability/{table}.orderedmap"
        if src == "official":
            rows = ctx.official_rows(table, key)
        else:
            if logical not in live_cache:
                live_cache[logical] = ctx.live_flat(logical)
            rows = ctx.csv_split(live_cache[logical][key])
        return list(rows[idx])

    groups = [("leader_ability", f"leader#{i}", rec, None) for i, rec in enumerate(design["leader"])]
    for slot in range(1, 7):
        recs = design["abilities"][f"slot{slot}"]
        for i, rec in enumerate(recs):
            groups.append(("ability", f"slot{slot}#{i}", rec, recs[0]["row"][1] if i > 0 else None))
    for table, label, rec, unison in groups:
        row = donor_row(rec["donor"], table)
        before = {k: row[int(k)] for k in rec["edits"]}
        for col, value in rec["edits"].items():
            row[int(col)] = value
        if unison is not None:
            row[1] = unison
        diff = [i for i, (a, b) in enumerate(zip(row, rec["row"])) if a != b]
        results.append({"row": label, "donor": rec["donor"], "match": row == rec["row"] and len(row) == len(rec["row"]),
                        "diff_cols": diff, "donor_before": before})
    return results


# ================================================================ 改版行（plan.json → 表行）

# 块入口的官方哨兵：写空串会被客户端 parseAt 读成 NaN / C7050。
# 统计口径（live 全表）：leader 瞬发行 c37='(None)'、持续行 c83='(None)'；瞬发无次数上限 c32='(None)'；
# ability 全部行 c39='(None)'（4404 行），瞬发无次数上限 c34='(None)'（351 行）。plan 的 cells 只列了
# 业务列，这里按行的触发模式补齐哨兵——补齐规则写死在下面，不允许覆盖 plan 已经给出的值。
SENTINELS = {
    "leader_ability": {"0": {37: "(None)"}, "1": {83: "(None)"}},
    "ability": {"0": {39: "(None)"}, "1": {85: "(None)"}},
}
TRIGGER_LIMIT_COL = {"leader_ability": (25, 32), "ability": (27, 34)}
# 触发模式列（0=瞬发 / 1=持续）两表不同号：leader ``c3``、ability ``c5``——ability 的 ``c3``
# 是 awake_kind。取法与 ``wf_seasonal7_kit_zantetsu.row_gate`` 一致 = precondition1 块基址 − 1
# （leader 4−1、ability 6−1）。live 实测（2026-09-17 全表）：
#   ability c5='0' → c39='(None)'、c85=''（4358 行）；c5='1' → c39=''、c85='(None)'（1076 行）
#   leader  c3='0' → c37='(None)'、c83=''（1305 行）；c3='1' → 反过来（275 行）
# 本 kit 到第四轮为止只产瞬发行（c3 与 c5 同为 '0'），所以原来两表都读 c3 也算对；
# 第五轮的 during 行 c3='0'、c5='1'，读错列会把哨兵补到 c39，出 live 零先例的行形。
MODE_COL = {"leader_ability": 3, "ability": 5}


def _fill_sentinels(row: list[str], table: str) -> list[str]:
    mode = row[MODE_COL[table]]
    for col, value in SENTINELS[table].get(mode, {}).items():
        if not row[col]:
            row[col] = value
    trig_col, limit_col = TRIGGER_LIMIT_COL[table]
    if mode == "0" and row[trig_col] not in ("", "0") and not row[limit_col]:
        row[limit_col] = "(None)"          # 有触发事件但不限次数 = 官方 '(None)'，不是空串
    return row


def revision_row(cells: dict, table: str) -> list[str]:
    """plan 的稀疏 ``cells``（只列非空列）→ 整行；其余列写空串，再补官方哨兵。"""
    ncols = 124 if table == "leader_ability" else 126
    row = [""] * ncols
    for col, value in cells.items():
        row[int(col)] = value
    return _fill_sentinels(row, table)


# ================================================================ 第三轮行改动（D1–D4）
#
# 作者原话（2026-09-16 第三次真机反馈）：
#   「队长技的引擎启动的每级攻击力提升+100%,技能伤害+200%,乘区+5%,除自身外的雷属性角色发动技能
#     赋予的重炮展开移动到能力3里面并且持续时间提升到12s,队长技添加,自身处于重炮展开时,除自身外
#     雷属性角色技能槽充能速度+50%,技能槽最大值+50%,自身的引擎启动等级每提升1,自身技能槽+5%,
#     技能槽最大值+5%」
#
# plan.json（revision-20260916）是第一轮的外部方案、不在本轮可写范围 ⇒ 全部改动放这里，
# 对 plan 的原值做逐格断言（plan 被改过 ⇒ 报错，不静默漂移），并且 build 与 gates.py
# 走的是同一组函数（``revision_leader_rows`` / ``revision_ability_rows``），两边算出同一张表。

# ---- D1：队长「引擎启动」每层的强度（leader during 强度列 c111/c112；独立乘区 5% 不动）
REV3_LEADER_STRENGTH = {
    0: {"cols": (111, 112), "plan": "50000", "fixed": "100000", "what": "每层 攻击力 50% → 100%"},
    1: {"cols": (111, 112), "plan": "100000", "fixed": "200000", "what": "每层 技能伤害 100% → 200%"},
}

# ---- D2：plan leader#3（461 赋予「重炮展开」）整条移到能力3；队长侧删除
REV3_LEADER_MOVED = 3
REV3_MOVED_ABILITY_KEY = f"{CID}3"
# leader(124 列) → ability(126 列) 列映射。块基址差：pre1 4/6、pre2 11/13、pre3 18/20、
# instant_trigger 25/27、instant_delay 44/46、instant_content 45/47（块内偏移两表相同）。
# 头三列按 ability 语义另写（c0 文本键带槽号 / c1 unisonable / c2 词条类别 / c3 awake_kind / c5 trigger）；
# 哨兵列（leader c32,c37 → ability c34,c39）由 ``_fill_sentinels`` 统一补，不参与映射。
REV3_MOVE_COLMAP = {
    4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12,             # precondition1：雷·编成≥6
    11: 13, 12: 14, 13: 15, 14: 16, 15: 17, 16: 18, 17: 19,   # precondition2：188 自身持有「重炮展开」≥1
    18: 20, 19: 21, 20: 22, 21: 23, 22: 24, 23: 25, 24: 26,   # precondition3（哨兵 0）
    25: 27, 26: 28, 27: 29, 28: 30, 29: 31, 30: 32, 31: 33,   # instant_trigger：技能发动 / puller 4 除自身任一·雷
    33: 35, 34: 36, 35: 37, 36: 38,                           # …（32 = trigger_limit 哨兵，见下）
    38: 40, 39: 41, 40: 42, 41: 43, 42: 44, 43: 45,           # instant_precontent（37 = kind 哨兵）
    44: 46,                                                    # instant_delay
    45: 47, 46: 48, 47: 49, 48: 50, 49: 51, 50: 52, 51: 53, 52: 54, 53: 55, 54: 56,
    55: 57, 56: 58, 57: 59, 58: 60, 59: 61, 60: 62, 61: 63, 62: 64, 63: 65, 64: 66,
    65: 67, 66: 68, 67: 69, 68: 70, 69: 71, 70: 72, 71: 73, 72: 74, 73: 75, 74: 76,
    75: 77, 76: 78, 77: 79, 78: 80, 79: 81, 80: 82, 81: 83, 82: 84,   # instant_content（461 的 uid c66→c68）
}
REV3_MOVE_SENTINEL_COLS = {32: 34, 37: 39}                     # 两表同义的哨兵列，交给 _fill_sentinels
# ability 侧头部：与同键其它记录逐列同形（c1/c2 取该键既有值，见 apply_rev3_ability 的断言）
REV3_MOVE_HEAD = {"0": f"{CODE}_3", "3": "0", "5": "0"}
# 先例（live store 2026-09-16 实测，脚本见 verify.md §证据）：
#   · ability instant_trigger kind 23 + puller 4(OneOfExceptMyself) + 元素组：1510141#0(White)、
#     1499955#1/#2(Green)，c27–c38 逐列与本行同形；同组合（不限元素组）共 19 行。
#   · ability instant_content 461：169 行，其中 target 0(Myself) 135 行。
#   · ability precondition2 kind 188：13 行，列形 ['188','0','','100000','100000','','<uid>'] 与本行逐格相同。

# ---- D3/D4：队长新增四行（两表的 during 块 kind 枚举同一套；本角色 during 行统一带 pre1 雷·编成≥6）
_REV3_LEADER_HEAD = {"0": CODE, "1": "0", "3": "1",
                     "4": "2", "7": "600000", "8": "600000", "9": "Yellow",
                     "11": "0", "18": "0"}


def _rev3_during(trigger: str, uid: str, limit: str, kind: str, target: str,
                 groups: str | None, strength: str) -> dict:
    cells = dict(_REV3_LEADER_HEAD)
    cells.update({"95": trigger, "96": "0", "98": "100000", "99": "100000", "100": limit,
                  "102": uid, "106": "false", "107": kind, "108": target,
                  "111": strength, "112": strength})
    if groups:
        cells["109"] = groups
    return cells


# 技能槽族在**持续**侧只有 3 SkillGaugeCharging / 124 SecondSkillGauge（瞬发侧才有 211 SkillGauge，
# 且 multiply_trigger 只有 None/PowerFlip/SkillInvoke/Fever ⇒ 瞬发没有「按固有层数倍增」的通道）。
# 所以作者的「技能槽 +5%」取同族最接近的 3（充能速度），列为 verify.md 待确认项。
# ⚠ 审查 R3-m3（2026-09-17）：这是**面板文案会与作者原话不同**的实质偏离（面板出「技能槽充能速度」
#   而不是「技能槽」），要作者点头，不能默认通过。
# ⚠ 审查 R3-M2（2026-09-17）：别再引用「充能速度上限 50%」当硬事实。客户端常量是 **100%** ——
#   ``boot_ffc6.as:9209-9210`` 把 ``MIN_STAT_MODIFIER_SKILL_GAUGE_CHARGING = fromFloat(-1)``、
#   ``MAX_STAT_MIDIFIER_SKILL_GAUGE_CHARGING = fromFloat(1)``，``MemberImpl.as:3385-3392`` 就用这两个钳；
#   同函数 3393/3475 的 ``stats.maxStatModifierSkillGaugeCharging`` 是「记录见过的最大值」（3475 行
#   直接 ``= _loc8_``），不是第二道钳位。记忆卡 wf-skill-gauge-max-exists 里的「上限 50%」
#   自己就标着「用户真机实测；反编译常量 MAX=1.0 是 100%」——那是**一次未复核的实测**，不是代码事实。
#   按 100% 算，自身 35%（队长 #8 的 25% + 能力6 满级 10%；2026-09-27 平衡批次由 20% 下调，原合计 45%）
#   + 每层 5% 一路到第 13 层才顶格，D4 是有效的。
#   真机顺手测一次（自身 35%+1 层 vs +3 层 的充能速度差）再决定要不要改写法。
REV3_LEADER_NEW = (
    {"id": "D4_charge", "req": "D4",
     "donor": "live leader_ability[139993] #0（during 134 同形）改 during_content 3 + target 0",
     "desc_expected": "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999301] → 自身 技能槽充能 5%",
     "cells": _rev3_during("134", UID_ENGINE, "(None)", "3", "0", None, "5000")},
    {"id": "D4_max", "req": "D4",
     "donor": "live leader_ability[149999] #2（during 124 SecondSkillGauge，杰拉德 1.4.251 起在线）",
     "desc_expected": "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999301] → 自身 2号位技能槽 5%",
     "cells": _rev3_during("134", UID_ENGINE, "(None)", "124", "0", None, "5000")},
    {"id": "D3_charge", "req": "D3",
     "donor": "live leader_ability[129999] #2（during 194 + during_content 3，逐列同形，只改 target/组/强度）",
     "desc_expected": "雷·编成≥6 时: 持续·状态计数固有≥1(限1次)[固有13999302] → 赋予除自身全员(雷) 技能槽充能 50%",
     "cells": _rev3_during("194", UID_CANNON, "1", "3", "1", "Yellow", "50000")},
    {"id": "D3_max", "req": "D3",
     "donor": "live leader_ability[129999] #2 的 during 块 + during_content 124（leader 124 先例 2 行）",
     "desc_expected": "雷·编成≥6 时: 持续·状态计数固有≥1(限1次)[固有13999302] → 赋予除自身全员(雷) 2号位技能槽 50%",
     "cells": _rev3_during("194", UID_CANNON, "1", "124", "1", "Yellow", "50000")},
)

# ================================================================ 第四轮行改动（T1 / T2）
#
# 作者原话（2026-09-17 第四次真机反馈）：
#   「特克托队长技的除自身外雷属性角色发动技能时自身技能伤害+50%,添加一个攻击力+50%上限都是500%,
#     能力3的描述有点奇怪,应该是自身引擎启动状态时,除自身外雷属性角色发动技能赋予自身重炮展开」
#
# ---- T1：队长瞬发行（plan#4）加一条同触发的「自身攻击力 +50%」，两条都封 500% 上限
#
# 上限落在**触发次数列** leader ``c32``：本角色这两行 c49=c50=50000（低级/满级拉平），
# 50% × 10 次 = 500%。面板由客户端自动渲染，不需要也不允许自己写字符串。
# ⚠ 渲染通道**不是**「（上限 N 次）」那条（2026-09-17 复核纠正，取证 review/panel_cap.json）：
#   · ``ability_description_instant_trigger_limit_n_times``「（上限 ::count:: 次）」只由
#     ``AbilityDescriptionStringfier_Impl_.addTriggerLimitPrefix*`` 产出，而
#     ``InstantAbilityDescriptionGenerator.stringfyInstantAbilityContent`` 的 **case 2 = Common**
#     （:9651）**没套**这个前缀 —— 32 AttackPoint / 34 SkillDamage 都属 Common 家族；
#     ``AbilityDescriptionTools.stringfyConjuctionTriggerLimit`` 取的是 ``..._conjunction_...`` 三键，
#     live 里三支都是「时，」，跟上限无关。
#   · 真正写出上限的是 ``AbilityDescriptionGenerator.stringfyCommonCharacterContent``
#     case 0(AttackPoint):4527 / case 2(SkillDamage):4651 末尾的 ``addMaxStrengthPercent(..., true, 强度)``：
#     ``calculateLimit`` = triggerLimit × maxTriggerPullerNumber（本行触发不是 Battle 支、
#     前置 puller 也不是 OneOfParty ⇒ 系数 1），渲染 ``ability_description_instant_max_strength``
#     =「[最大 ::max_strength::&nbsp;]」。⇒ 写 "10" 面板就出「[最大 + 500 % ]」，字面就是作者要的 500%。
#   · 反推：改前 c32='(None)' 时 ``calculateLimit`` 返回 null ⇒ 无上限段，与作者「看不到上限」一致。
# 先例（``revision4-20260917/tekuto/precedents.json``，官方 CDN 归档 1.4.54 基线）：
#   · leader 瞬发 content kind **32 AttackPoint**：官方 397 行；与 34 SkillDamage 同键共存 34 个键；
#   · leader 瞬发 trigger_limit = "10"：官方 38 行（该列取值直方图里 "(None)" 79 / "10" 38 / "6" 33 …）；
#   · puller 4 OneOfExceptMyself 在 leader 侧官方零先例（本角色 1.4.869 起自制、已真机在线），
#     但 ability 侧官方有 puller 4 + 有限次的行 ⇒ 次数计数器与 puller 无关，是逐记录的执行计数。
REV4_LEADER_SOURCE = 4                # plan#4 =「技能发动(除自身任一·雷) → 自身 技能伤害 50%」
REV4_SKILL_KIND = "34"                # InstantAbilityContentMasterValue 34 = SkillDamage（源行）
REV4_ATTACK_KIND = "32"               # 32 = AttackPoint（新行唯一改动的列）
REV4_LIMIT_PLAN = "(None)"            # 改前：无次数上限
REV4_TRIGGER_LIMIT = "10"             # 改后：50% × 10 = 500%
REV4_ATTACK_ID = "T1_attack"
REV4_LEADER_NEW = (
    {"id": REV4_ATTACK_ID, "req": "T1",
     "donor": f"live leader_ability[{CID}] #7（本角色现行瞬发行；逐格复制，只改 content kind 34→32）",
     "desc_expected": "雷·编成≥6 且 状态计数固有≥1[固有13999302] 时: 技能发动≥1(限10次) → 自身 攻击力 50%",
     "derived_from_plan_row": REV4_LEADER_SOURCE},
)

# ---- T2：能力3 的 461 行前置 uid 从「重炮展开」改成「引擎启动」
# 只换 uid（ability pre2 uid 列 c19 = leader c17 的映射落点），前置 kind / puller / 阈值列不动：
# 188 ConditionCountUnique 数的是**实例个数**（461 叠层的固有恒为 1）⇒「≥1 = 持有」，
# 正是作者说的「自身引擎启动状态时」。官方 ability 侧 188 共 3 行，列形全是
# ['188','0','','100000','100000',''] + uid，与本行逐格相同（记忆卡 wf-precondition-puller-c7050：
# 改前置 kind 就必须整块照抄官方同 kind 行——这里 kind 没动，所以只换 uid 是安全的最小改动）。
REV4_MOVED_PRE_UID_COL = 19           # ability precondition2 的 unique id 列
REV4_MOVED_PRE_UID = UID_ENGINE       # 13999301「引擎启动」
REV4_MOVED_PRE_UID_PLAN = UID_CANNON  # 改前值（= plan leader#3 的 c17）

# 面板可读性：同一触发文案的行相邻 ⇒ 五条 during-134 在前、两条 during-194 次之、三条瞬发行殿后；
# 瞬发里 T1 的攻击力行排在技能伤害行之前，与 during 侧「攻击力 → 技能伤害」的顺序一致。
# 本轮队长 6 − 1 + 4 + 1 = 10 条（官方一键最多 8 条、live 自制键已有 10/11/13/15 条 —— 见
# precedents.json P1）。**「一键最多 10 条」是普查观测值不是客户端硬上限**（记忆卡
# wf-ability-multirecord-rows 2026-08-26 纠偏：MasterArray/AbilityLogic 全量遍历，无行数上限；
# ability 表只读 values[0] 的仅 c1 unisonable 与 c2 statue_group_id）⇒ 下一轮要加行不必先删行，
# 但**新行仍不得动 rec#0**，且同键的「只读 values[0]」列必须自洽
# （leader 的 c1/c2 是 awake_kind/awake_level，骨架与 ability 不同；本键 leader c1 全 '0'、c2 全空，
#  ability 每键 c1/c2 也各自一致，已核 —— review/rv_order.py）。
LEADER_ORDER = (("plan", 0), ("plan", 1), ("plan", 2),
                ("new", "D4_charge"), ("new", "D4_max"),
                ("new", "D3_charge"), ("new", "D3_max"),
                ("new", REV4_ATTACK_ID), ("plan", REV4_LEADER_SOURCE), ("plan", 5))
REV3_LEADER_ORDER = LEADER_ORDER      # 兼容旧名（第三轮的九行顺序已被 T1 插入一行）
LEADER_NEW_SPECS = REV3_LEADER_NEW + REV4_LEADER_NEW


def plan_leader_rows(plan: dict) -> list[list[str]]:
    """plan.json 声明的 6 行（第三轮之前的形态）——rev3 的输入与断言基准。"""
    block = plan["leader_ability"]
    if block["table"] != LEADER or block["key"] != CID or block["op"] != "replace_all_rows":
        raise KitError(f"revision leader block unexpected: {block.get('table')}/{block.get('key')}/{block.get('op')}")
    rows = [revision_row(rec["cells"], "leader_ability") for rec in sorted(block["rows"], key=lambda r: r["index"])]
    if len(rows) != block["new_row_count"] or [r["index"] for r in block["rows"]] != list(range(len(rows))):
        raise KitError(f"revision leader row count/index mismatch: {len(rows)} vs {block['new_row_count']}")
    return rows


def apply_rev4_t1(rows: list[list[str]]) -> list[str]:
    """T1：给源行（plan#4）封 500% 上限（就地改 ``rows``），并复制出同触发的「攻击力 +50%」行。

    新行是源行的**逐格副本**，唯一差异 = content kind 34 SkillDamage → 32 AttackPoint，
    所以「同触发、同前置、同强度」由结构保证。幂等：源行已是 "10" 时原样放行。
    """
    src = rows[REV4_LEADER_SOURCE]
    shape = (src[3], src[25], src[26], src[27], src[45], src[46], src[49], src[50])
    want = ("0", "23", "4", "Yellow", REV4_SKILL_KIND, "0", "50000", "50000")
    if shape != want:
        raise KitError(f"rev4 T1: plan#{REV4_LEADER_SOURCE} 不是「除自身外雷·技能发动 → 自身技能伤害 50%」"
                       f"那条（c3/c25-27/c45/c46/c49/c50 = {shape}，期望 {want}）")
    cur = src[32]
    if cur == REV4_LIMIT_PLAN:
        src[32] = REV4_TRIGGER_LIMIT
    elif cur != REV4_TRIGGER_LIMIT:                        # 幂等：已是新值放行；第三种值 ⇒ plan 被改过
        raise KitError(f"rev4 T1: leader plan#{REV4_LEADER_SOURCE} c32 现值 {cur!r} "
                       f"既不是 plan 原值 {REV4_LIMIT_PLAN!r} 也不是修正值 {REV4_TRIGGER_LIMIT!r}")
    attack = list(src)
    attack[45] = REV4_ATTACK_KIND
    return attack


def apply_rev3_leader(plan_rows: list[list[str]]) -> list[list[str]]:
    """D1 改强度 + D2 删掉被移走的那条 + D3/D4 新增四行 + T1 补攻击力行与 500% 上限，按 LEADER_ORDER 排序。"""
    used = {ref for kind, ref in LEADER_ORDER if kind == "plan"}
    if used | {REV3_LEADER_MOVED} != set(range(len(plan_rows))):
        raise KitError(f"rev3 leader order covers {sorted(used)} + moved {REV3_LEADER_MOVED}, "
                       f"plan has {len(plan_rows)} rows")
    rows = [list(r) for r in plan_rows]
    for idx, fix in REV3_LEADER_STRENGTH.items():
        for col in fix["cols"]:
            cur = rows[idx][col]
            if cur == fix["plan"]:
                rows[idx][col] = fix["fixed"]
            elif cur != fix["fixed"]:                      # 幂等：已是新值放行；第三种值 ⇒ plan 被改过
                raise KitError(f"rev3 leader#{idx} c{col} 现值 {cur!r} 既不是 plan 原值 {fix['plan']!r} "
                               f"也不是修正值 {fix['fixed']!r}")
    new_rows = {spec["id"]: revision_row(dict(spec["cells"]), "leader_ability") for spec in REV3_LEADER_NEW}
    new_rows[REV4_ATTACK_ID] = apply_rev4_t1(rows)         # 第四轮 T1（会就地给源行写上次数上限）
    if sorted(new_rows) != sorted(spec["id"] for spec in LEADER_NEW_SPECS):
        raise KitError("leader new rows have duplicate ids")
    out = [rows[ref] if kind == "plan" else new_rows[ref] for kind, ref in LEADER_ORDER]
    if len(out) > 10:                                      # 一键最多 10 条（leader 侧实测上限）
        raise KitError(f"leader {CID}: {len(out)} records > 10")
    return out


def build_moved_ability_row(plan: dict, head: dict[str, str]) -> list[str]:
    """D2：把 plan leader#3（461 赋予「重炮展开」）按列映射搬成 ability 行。"""
    src = plan_leader_rows(plan)[REV3_LEADER_MOVED]
    if (src[45], src[46], src[66], src[25], src[26], src[27], src[11], src[17]) != \
            ("461", "0", UID_CANNON, "23", "4", "Yellow", "188", UID_CANNON):
        raise KitError(f"rev3 moved leader row is not the 461/「重炮展开」row: "
                       f"content={src[45]}/{src[46]}/{src[66]} trigger={src[25]}/{src[26]}/{src[27]} "
                       f"pre2={src[11]}/{src[17]}")
    cells: dict[str, str] = dict(head)
    for col, value in enumerate(src):
        if not value or col in (0, 1, 3):                  # 头部列按 ability 语义另写
            continue
        if col in REV3_MOVE_SENTINEL_COLS:                 # 哨兵：两表同义，交给 _fill_sentinels
            continue
        if col not in REV3_MOVE_COLMAP:
            raise KitError(f"rev3 move: leader c{col}={value!r} 没有列映射（表布局变了？）")
        cells[str(REV3_MOVE_COLMAP[col])] = value
    row = revision_row(cells, "ability")
    for col, dst in REV3_MOVE_SENTINEL_COLS.items():       # 哨兵必须补上且与源同值
        if row[dst] != src[col]:
            raise KitError(f"rev3 move: 哨兵列 ability c{dst}={row[dst]!r} != leader c{col}={src[col]!r}")
    # ---- 第四轮 T2：前置从「自身持有重炮展开」（自持环）改成「自身持有引擎启动」；只换 uid，kind/puller/阈值不动
    cur = row[REV4_MOVED_PRE_UID_COL]
    if cur == REV4_MOVED_PRE_UID_PLAN:
        row[REV4_MOVED_PRE_UID_COL] = REV4_MOVED_PRE_UID
    elif cur != REV4_MOVED_PRE_UID:                        # 幂等：已是新值放行；第三种值 ⇒ plan 被改过
        raise KitError(f"rev4 T2: ability c{REV4_MOVED_PRE_UID_COL} 现值 {cur!r} 既不是 plan 原值 "
                       f"{REV4_MOVED_PRE_UID_PLAN!r} 也不是修正值 {REV4_MOVED_PRE_UID!r}")
    if row[13] != "188" or row[14] != "0" or [row[16], row[17]] != ["100000", "100000"]:
        raise KitError(f"rev4 T2: 前置2 列形被动过（期望 188/0/100000/100000）: {row[13:20]}")
    return row


def _rev3_move_guard(rows: list[list[str]]) -> None:
    """能力3 里不许已经存在一条 461 给「重炮展开」的记录——否则 D2 会搬第二份进去。

    ``revision_ability_rows`` 每次都从 plan 重建记录 0–3，所以正常重跑不会触发；
    这道闸是给「plan.json 以后自己也加了这条」的未来准备的（届时必须手工收口，不能双写）。
    """
    dup = [i for i, r in enumerate(rows) if r[47] == "461" and r[68] == UID_CANNON]
    if dup:
        raise KitError(f"rev3 move: {REV3_MOVED_ABILITY_KEY} 里已经有 461/{UID_CANNON} 记录 {dup}（重复搬运？）")


# ================================================================ 第五轮行改动（T3）
#
# 作者原话（2026-09-17）：
#   「特克托的能力2改为,自身对引擎启动每上升1,自身攻击力+50%,技能伤害+50%,不设置上限」
#
# plan.json 里 1399932 是 ``op: no_change``（第一轮那两条瞬发行照抄 live）。本轮整键换成
# 两条 during 行，所以不走 plan 的 edits/add，而是在 ``revision_ability_rows`` 末尾单独收口，
# 对被换掉的两条瞬发行做逐格断言（plan/live 被别人动过 ⇒ 报错，不静默漂移）。
#
# ability during 块列位（live 全表 151 条 134 行实测）：
#   c97 kind / c98 puller / c100,c101 阈值 / c102 次数上限 / c104 固有 uid /
#   c108 'false' / c109 内容 kind / c110 target / c111 元素组 / c113,c114 强度(低级,满级)
# 与 leader 的 95/96/98,99/100/102/106/107/108/109/111,112 逐列 +2（两表 during kind 枚举同一套，
# 记忆卡 wf-leader-ability-layout）。134 的 puller 写 '0'：
# 供体与官方 134 行全是 '0'，且 134 不在 zantetsu kit 的 ``PULLER_EMPTY_DURING`` 里。
#
# 「不设置上限」= c102 ``'(None)'``：live 该列 8 行是 ``'(None)'``（含供体两行），
# 写数字会让客户端 ``calculateLimit`` 算出上限并渲染「[最大 +N%]」——第四轮 T1 就是靠这个写出 500%。
# 反过来这里要的是后面什么都不跟，正好是作者的文案规则①。
REV5_ABILITY_KEY = f"{CID}2"
REV5_DONOR = ("live ability[1399943]#3/#4（本批雷吉斯能力3：134 + 自身固有 uid + "
              "target 0 Myself + 次数上限 (None)，1.4.883 起在线）")
# 被换掉的两条瞬发行：(c27 触发, c34 次数上限, c47 内容 kind, c51 低级强度, c52 满级强度)
REV5_REPLACED_SHAPE = (("23", "3", "32", "50000", "100000"),
                       ("23", "3", "34", "25000", "50000"))
REV5_ATTACK_KIND = "0"        # DuringAbilityContentMasterValue 0 = AttackPoint
REV5_SKILL_KIND = "2"         # 2 = SkillDamage
REV5_STRENGTH = "50000"       # +50%，低级/满级拉平（固定文案单值，记忆卡 wf-leader-override-text-rules）
REV5_NO_CAP = "(None)"
REV5_ROWS = (
    {"id": "T3_attack", "kind": REV5_ATTACK_KIND,
     "desc_expected": "持续·状态累积计数固有≥1[固有13999301] → 自身 攻击力 50%"},
    {"id": "T3_skill", "kind": REV5_SKILL_KIND,
     "desc_expected": "持续·状态累积计数固有≥1[固有13999301] → 自身 技能伤害 50%"},
)


def _rev5_during_cells(head: dict[str, str], kind: str) -> dict[str, str]:
    cells = dict(head)
    cells.update({"3": "0", "5": "1", "6": "0", "13": "0", "20": "0",
                  "97": "134", "98": "0", "100": "100000", "101": "100000",
                  "102": REV5_NO_CAP, "104": UID_ENGINE, "108": "false",
                  "109": kind, "110": "0", "113": REV5_STRENGTH, "114": REV5_STRENGTH})
    return cells


def rev5_ability2_rows(head: dict[str, str]) -> list[list[str]]:
    return [revision_row(_rev5_during_cells(head, spec["kind"]), "ability") for spec in REV5_ROWS]


def apply_rev5_ability2(rows: list[list[str]]) -> list[list[str]]:
    """T3：能力2 的两条瞬发行 → 两条按「引擎启动」层数成长、无上限的 during 行（幂等）。"""
    if len(rows) != 2:
        raise KitError(f"rev5 T3: {REV5_ABILITY_KEY} 期望 2 条记录，实际 {len(rows)}")
    if rows[0][1] != rows[1][1] or rows[0][2] != rows[1][2]:
        raise KitError(f"rev5 T3: {REV5_ABILITY_KEY} 的整键列 c1/c2 同键不自洽："
                       f"{rows[0][1:3]} vs {rows[1][1:3]}")
    head = {"0": f"{CODE}_2", "1": rows[0][1], "2": rows[0][2]}
    built = rev5_ability2_rows(head)
    if [list(r) for r in rows] == built:                   # 幂等：已经是新形（kit 重跑 / 包已回写）
        return built
    # 2026-09-27 平衡第二批回写候选后，包内是第二批的封顶行（c102=10、16%/15%）：认出来并交回第五轮形态，
    # 由 build() 末尾的 apply_balance_b 再统一改到第二批 ⇒ 重跑 kit 结果不变、也不会叠改两次。
    if [list(r) for r in rows] == balance_b_ability2_rows(built):
        return built
    shape = tuple((r[27], r[34], r[47], r[51], r[52]) for r in rows)
    if shape != REV5_REPLACED_SHAPE:
        raise KitError(f"rev5 T3: {REV5_ABILITY_KEY} 现行两条既不是改版前的瞬发行也不是改后的 during 行"
                       f"（c27/c34/c47/c51/c52 = {shape}，期望 {REV5_REPLACED_SHAPE}）")
    return built


def revision_leader_rows(plan: dict) -> list[list[str]]:
    return apply_rev3_leader(plan_leader_rows(plan))


def revision_ability_rows(plan: dict, current: dict[str, list[list[str]]]) -> tuple[dict[str, list[list[str]]], list[dict]]:
    """``current``（包内现行行）+ plan 的 edits/add → 新行；每条 edit 的 ``old`` 必须与现行值逐字相同。"""
    block = plan["ability"]
    if block["table"] != ABILITY:
        raise KitError(f"revision ability table {block['table']}")
    out: dict[str, list[list[str]]] = {}
    trace: list[dict] = []
    for key, spec in block["keys"].items():
        if key not in current:
            raise KitError(f"revision ability key {key} not in package")
        rows = [list(r) for r in current[key]]
        if spec.get("op") == "no_change":
            out[key] = rows
            trace.append({"key": key, "op": "no_change", "records": len(rows)})
            continue
        built: list[list[str]] = []
        for rec in spec["records"]:
            if rec["op"] == "add":
                built.append(revision_row(rec["cells"], "ability"))
                trace.append({"key": key, "record": rec["index"], "op": "add", "req": rec.get("req")})
                continue
            if rec["index"] >= len(rows):
                raise KitError(f"revision ability {key}#{rec['index']} missing in package")
            row = list(rows[rec["index"]])
            mismatched, already = {}, []
            for col, edit in rec.get("edits", {}).items():
                cell = row[int(col)]
                if cell == edit["new"] != edit["old"]:
                    already.append(int(col))          # kit 重跑：上一轮已经改过，幂等
                elif cell != edit["old"]:
                    mismatched[col] = [cell, edit["old"], edit["new"]]
                row[int(col)] = edit["new"]
            if mismatched:
                raise KitError(f"revision ability {key}#{rec['index']} current value is neither "
                               f"plan.old nor plan.new: {mismatched}")
            built.append(_fill_sentinels(row, "ability"))
            trace.append({"key": key, "record": rec["index"], "op": rec["op"],
                          "cols": sorted(int(c) for c in rec.get("edits", {})),
                          "already_applied_cols": sorted(already)})
        want = spec.get("record_count", {}).get("new", len(built))
        if len(built) != want:
            raise KitError(f"revision ability {key} produced {len(built)} records, plan says {want}")
        out[key] = built
    if sorted(out) != [f"{CID}{i}" for i in range(1, 7)]:
        raise KitError(f"revision ability keys {sorted(out)}")
    # ---- 第三轮 D2：把队长那条 461「赋予重炮展开」追加到能力3（列形按 ability 布局重映射）
    target = out[REV3_MOVED_ABILITY_KEY]
    if not target:
        raise KitError(f"rev3 move: {REV3_MOVED_ABILITY_KEY} 无记录")
    head = dict(REV3_MOVE_HEAD)
    head["1"], head["2"] = target[0][1], target[0][2]       # unisonable / 词条类别与同键其它记录一致
    moved = build_moved_ability_row(plan, head)
    _rev3_move_guard(target)                               # plan 自己若也加了 461/重炮展开 ⇒ 拒绝重复搬运
    target.append(moved)
    trace.append({"key": REV3_MOVED_ABILITY_KEY, "record": len(target) - 1, "op": "add",
                  "req": "D2", "from": f"leader#{REV3_LEADER_MOVED}", "colmap": "REV3_MOVE_COLMAP"})
    if len(target) > 9:                                    # 一键最多 9/10 条（记忆卡 wf-ability-multirecord-rows）
        raise KitError(f"{REV3_MOVED_ABILITY_KEY}: {len(target)} records > 9")
    # ---- 第五轮 T3：能力2 整键换成两条按「引擎启动」层数成长、无上限的 during 行
    out[REV5_ABILITY_KEY] = apply_rev5_ability2(out[REV5_ABILITY_KEY])
    trace.append({"key": REV5_ABILITY_KEY, "op": "replace_all_rows", "req": "T3",
                  "records": len(out[REV5_ABILITY_KEY]), "donor": REV5_DONOR,
                  "rows": [spec["id"] for spec in REV5_ROWS]})
    return out, trace


# ================================================================ 第六轮（2026-09-27 平衡第二批）
#
# 作者 2026-09-27 口径（${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md）A 节：
#   「无上限成长全部移到队长技并大幅放缓；能力栏给正常的、有上限的数值」；放缓倍率按 3 分钟实际触发次数
#   （≤15 次 ×1/5；≥30 次 ×1/10；之间取 1/5）；充能（kind 3/35）与技能槽上限（124/245）的成长行本批不动。
# 修订模块 ``wf_balance_20260927b_tekuto`` 对 live 做同一组改动；本段让重跑 kit 得到同一张表（测试断言相等）。
# 叠在第五轮 + wf_tekuto_low_hp 之后（build() 里 low_hp.revise_rows 之后调用），不改前几轮的常量与断言。
#
# 频率（3 分钟，特克托当队长 = 主位，Ⓜ能力3 生效；口径 A2 按实际次数、不按事件名称）：引擎层数 ≈
# 自身技能 11–14 发 × (DSL +1，间隔 <15 秒〔重炮 900 帧〕时能力3#2 再 +1) + 持重炮时 2 名雷队友技能 20–28 次 × 1
# ≈ 40–55 层；HP≤50%（背水玩法）队长行每发再 +2 ⇒ 60–80 层（设计稿保守估计也有 20–25 / 半血 35–45）⇒ ≥30 ⇒
# 引擎逐层行每步 ×1/10（与同批 kyle/celtie/hibiki/magnus 按层数取 1/10 一致；设计稿按「低频」标签的 1/5 不采用）；
# 半血持重炮每 120 帧一跳 ≈ 20–60 跳（按 40）⇒ ≥30 取 1/10。
BALANCE_B_LEADER_SCALE = (
    # (选择器 {列: 值}, 强度列, 旧, 新, 说明)
    ({3: "1", 95: "134", 102: UID_ENGINE, 107: "0", 108: "5"}, (111, 112), "100000", "10000",
     "引擎每层 雷队攻击力 100% → 10%（1/10）"),
    ({3: "1", 95: "134", 102: UID_ENGINE, 107: "2", 108: "5"}, (111, 112), "200000", "20000",
     "引擎每层 雷队技能伤害 200% → 20%（1/10）"),
    ({3: "1", 95: "134", 102: UID_ENGINE, 107: "411", 108: "0"}, (111, 112), "5000", "500",
     "引擎每层 自身独立乘区技能伤害 5% → 0.5%（1/10；与 magnus 411 同精度，口径 A7）"),
    ({3: "0", 25: "77", 45: "34", 46: "0"}, (49, 50), "100000", "10000",
     "雷共鸣＋持重炮＋HP≤50%：每 120 帧 自身技能伤害 100% → 10%（1/10）"),
)
#: 口径 A6：引擎每层的充能（during 3）/ 技能槽上限（during 124）行本批不动（锁在这里，防止误改）。
BALANCE_B_LEADER_UNTOUCHED_KINDS = ("3", "124")
#: 能力2（非Ⓜ、无共鸣）原位换成有上限的弱化版：引擎每层 攻 +16% / 技伤 +15%，最多 10 层
#: （满层 160% / 150% = 官方自身攻持续 160% / 自身技伤 150%）。c102 写数字 = TriggerLimitTools.limit 钳层数，
#: 官方 ability during-134 共 24 行全部带数字上限（如 1611231–1611236 限 10）。
BALANCE_B_ABILITY2_CAP = "10"
BALANCE_B_ABILITY2_STRENGTH = {REV5_ATTACK_KIND: "16000", REV5_SKILL_KIND: "15000"}
#: 能力2 的无上限部分搬进队长（行 = [c0, '0', ''] + 能力行[5:]，能力 c≥5 → 队长 c−2），每层 50% → 5%（1/10）。
#: 队长 #0/#1 是全队(雷)＋雷共鸣前置，目标与前置都不同 ⇒ 不合并，新起两行（队长 10 → 12 行）。
BALANCE_B_LEADER_FROM_ABILITY2 = "5000"


def _balance_b_match(row: list[str], selector: dict[int, str]) -> bool:
    return all(row[col] == value for col, value in selector.items())


def balance_b_ability2_rows(rev5_rows: list[list[str]]) -> list[list[str]]:
    """第五轮的两条无上限 during-134 行 → 第二批封顶版（c102 (None)→10；强度 50% → 16% / 15%）。"""
    out = [list(r) for r in rev5_rows]
    if [r[109] for r in out] != [REV5_ATTACK_KIND, REV5_SKILL_KIND]:
        raise KitError(f"balance-b: {REV5_ABILITY_KEY} 内容 kind {[r[109] for r in out]} 不是第五轮的 0/2")
    for row in out:
        if (row[97], row[102], row[104], row[113], row[114]) != \
                ("134", REV5_NO_CAP, UID_ENGINE, REV5_STRENGTH, REV5_STRENGTH):
            raise KitError(f"balance-b: {REV5_ABILITY_KEY} 行不是第五轮形态 "
                           f"{(row[97], row[102], row[104], row[113], row[114])}")
        row[102] = BALANCE_B_ABILITY2_CAP
        row[113] = row[114] = BALANCE_B_ABILITY2_STRENGTH[row[109]]
    return out


def balance_b_moved_leader_rows(rev5_rows: list[list[str]]) -> list[list[str]]:
    """能力2 第五轮两行的无上限部分 → 队长两行（列号能力 c≥5 → 队长 c−2，强度 1/10）。"""
    out = []
    for row in rev5_rows:
        if len(row) != 126 or row[5] != "1" or row[102] != REV5_NO_CAP:
            raise KitError("balance-b: 搬进队长的必须是第五轮的无上限 during 行")
        moved = [CODE, "0", ""] + list(row[5:])
        if len(moved) != 124:
            raise KitError(f"balance-b: moved leader row width {len(moved)}")
        moved[111] = moved[112] = BALANCE_B_LEADER_FROM_ABILITY2
        out.append(moved)
    return out


def apply_balance_b(leader_rows: list[list[str]], ability2_rows: list[list[str]]
                    ) -> tuple[list[list[str]], list[list[str]], list[dict]]:
    """第六轮：队长 4 处放缓 + 能力2 两行封顶 + 能力2 无上限部分搬进队长。输入是第五轮/low_hp 之后的行。"""
    import wf_client_legality as LG
    leader = [list(r) for r in leader_rows]
    trace: list[dict] = []
    for selector, cols, old, new, what in BALANCE_B_LEADER_SCALE:
        hits = [i for i, row in enumerate(leader) if _balance_b_match(row, selector)]
        if len(hits) != 1:
            raise KitError(f"balance-b: 队长行选择器 {selector} 命中 {hits}（期望恰好 1 行）")
        row = leader[hits[0]]
        if [row[c] for c in cols] != [old] * len(cols):
            raise KitError(f"balance-b: 队长#{hits[0]} c{cols} 现值 {[row[c] for c in cols]} != 改前 {old}")
        for col in cols:
            row[col] = new
        trace.append({"leader": hits[0], "cols": list(cols), "old": old, "new": new, "what": what})
    kept = [row for row in leader if row[3] == "1" and row[95] == "134"
            and row[107] in BALANCE_B_LEADER_UNTOUCHED_KINDS]
    if [(r[107], r[111], r[112]) for r in kept] != [("3", "5000", "5000"), ("124", "5000", "5000")]:
        raise KitError("balance-b: 引擎每层的充能/技能槽上限行不是改前形态（口径 A6：本批不动）")
    ability2 = balance_b_ability2_rows(ability2_rows)
    moved = balance_b_moved_leader_rows(ability2_rows)
    leader.extend(moved)
    trace.append({"leader_appended": [len(leader) - 2, len(leader) - 1],
                  "from": f"ability:{REV5_ABILITY_KEY}（第五轮两行）", "strength": BALANCE_B_LEADER_FROM_ABILITY2})
    trace.append({"ability": REV5_ABILITY_KEY, "cap": BALANCE_B_ABILITY2_CAP,
                  "strength": dict(BALANCE_B_ABILITY2_STRENGTH)})
    problems = []
    for i, row in enumerate(leader):
        problems += [f"leader#{i}: {p}" for p in LG.client_legality_problems("leader_ability", row)
                     + LG.declared_block_field_problems("leader_ability", row)
                     + LG.ability_element_column_problems("leader_ability", row, ELEMENT)]
    for i, row in enumerate(ability2):
        problems += [f"{REV5_ABILITY_KEY}#{i}: {p}" for p in LG.client_legality_problems("ability", row)
                     + LG.declared_block_field_problems("ability", row)
                     + LG.ability_element_column_problems("ability", row, ELEMENT)]
    if problems:
        raise KitError(f"balance-b rows rejected: {problems}")
    return leader, ability2, trace


# ================================================================ 第七轮（2026-09-27 平衡第三批）
#
# 主会话口径 growth_c_spec.md（作者原话：「成长速度砍到1/10不合理」「砍到4/5，或者7/10这样吧」「可以砍到2/3」
# 「数值尽量取5的倍数」；「部分角色技能都倍率成长也要无限成长,成长条件放到队长技里面带上对应共鸣条件」）。
# 修订模块 ``wf_balance_20260927c_tekuto`` 对 live 做同一组改动；本段让重跑 kit 得到同一张表/同一棵树（测试断言相等）。
# 叠在第六轮之后（build() 里 apply_balance_b 之后调用行、final_tree 之后调用树），不改前几轮的常量与断言。
#
# 档位（原值 × 档位，原值 ≥20% 取 5 的倍数、≤10% 取 0.5 的倍数，2/3 档向上取）：
BALANCE_C_LEADER_SCALE = (
    # (选择器 {列: 值}, 强度列, 第二批值, 第三批值, 说明)
    ({3: "1", 95: "134", 102: UID_ENGINE, 107: "0", 108: "5"}, (111, 112), "10000", "80000",
     "引擎每层 雷队攻击力 原 100% ×4/5 → 80%"),
    ({3: "1", 95: "134", 102: UID_ENGINE, 107: "2", 108: "5"}, (111, 112), "20000", "160000",
     "引擎每层 雷队技能伤害 原 200% ×4/5 → 160%"),
    ({3: "1", 95: "134", 102: UID_ENGINE, 107: "411", 108: "0"}, (111, 112), "500", "3500",
     "引擎每层 自身独立乘区技能伤害 原 5% ×2/3 = 3.33 → 3.5%"),
    ({3: "0", 25: "77", 45: "34", 46: "0"}, (49, 50), "10000", "70000",
     "雷共鸣＋持重炮＋HP≤50%：每 120 帧 自身技能伤害 原 100% ×7/10 → 70%"),
    ({3: "1", 4: "0", 95: "134", 102: UID_ENGINE, 107: "0", 108: "0"}, (111, 112), "5000", "35000",
     "引擎每层 自身攻击力（第二批自能力2 搬入）原 50% ×2/3 = 33.3 → 35%"),
    ({3: "1", 4: "0", 95: "134", 102: UID_ENGINE, 107: "2", 108: "0"}, (111, 112), "5000", "35000",
     "引擎每层 自身技能伤害（第二批自能力2 搬入）原 50% ×2/3 = 33.3 → 35%"),
)
#: 旗号 3 开关行落点（U6：技能强化所在的能力 1，c1='true'；零先例的队长表 705 行不做）。
BALANCE_C_SWITCH_ABILITY_KEY = f"{CID}1"
BALANCE_C_SWITCH_KIND = "705"                 # 切换技能旗号 3（InstantAbilitySource 704–708 → 旗号 2–6）
BALANCE_C_LEADER_ONLY = "42"                  # 前置 1 kind 42 = 仅队长（live 先例 罗尔夫中秋 1499866#4）
BALANCE_C_SEGMENTS = 11                       # 每档技能树里「Bind 起到块尾」的段数


def balance_c_switch_row(flag1_row: list[str]) -> list[str]:
    """能力1 的 536 开关行（前置 202 主位 + 雷≥6）→ 旗号 3 开关行：只换 c6 202→42、c47 536→705、c70。"""
    if (len(flag1_row), flag1_row[6], flag1_row[47], flag1_row[70]) != (126, "202", "536", CHANGE_SKILL_KEY):
        raise KitError(f"balance-c: {BALANCE_C_SWITCH_ABILITY_KEY} 的 536 开关行不是改版形态")
    row = list(flag1_row)
    row[6], row[47], row[70] = BALANCE_C_LEADER_ONLY, BALANCE_C_SWITCH_KIND, CHANGE_SKILL_LEADER_KEY
    return row


def apply_balance_c(leader_rows: list[list[str]], ability1_rows: list[list[str]]
                    ) -> tuple[list[list[str]], list[list[str]], list[dict]]:
    """第七轮：队长 6 行按第三批档位改强度 + 能力1 追加旗号 3 开关行。输入是第六轮（apply_balance_b）之后的行。"""
    import wf_client_legality as LG
    leader = [list(r) for r in leader_rows]
    trace: list[dict] = []
    for selector, cols, old, new, what in BALANCE_C_LEADER_SCALE:
        hits = [i for i, row in enumerate(leader) if _balance_b_match(row, selector)]
        if len(hits) != 1:
            raise KitError(f"balance-c: 队长行选择器 {selector} 命中 {hits}（期望恰好 1 行）")
        row = leader[hits[0]]
        if [row[c] for c in cols] != [old] * len(cols):
            raise KitError(f"balance-c: 队长#{hits[0]} c{cols} 现值 {[row[c] for c in cols]} != 第二批 {old}")
        for col in cols:
            row[col] = new
        trace.append({"leader": hits[0], "cols": list(cols), "old": old, "new": new, "what": what})
    kept = [row for row in leader if row[3] == "1" and row[95] == "134"
            and row[107] in BALANCE_B_LEADER_UNTOUCHED_KINDS]
    if [(r[107], r[111], r[112]) for r in kept] != [("3", "5000", "5000"), ("124", "5000", "5000")]:
        raise KitError("balance-c: 引擎每层的充能/技能槽上限行不是改前形态（本批不动）")
    ability1 = [list(r) for r in ability1_rows]
    if len(ability1) != 2 or ability1[1][47] != "536":
        raise KitError(f"balance-c: {BALANCE_C_SWITCH_ABILITY_KEY} 期望 2 条（211 + 536），实际 "
                       f"{[r[47] for r in ability1]}")
    switch = balance_c_switch_row(ability1[1])
    ability1.append(switch)
    trace.append({"ability": BALANCE_C_SWITCH_ABILITY_KEY, "appended": len(ability1) - 1,
                  "kind": BALANCE_C_SWITCH_KIND, "flag": LEADER_SKILL_FLAG,
                  "precondition": BALANCE_C_LEADER_ONLY, "string": CHANGE_SKILL_LEADER_KEY})
    problems = []
    for i, row in enumerate(leader):
        problems += [f"leader#{i}: {p}" for p in LG.client_legality_problems("leader_ability", row)
                     + LG.declared_block_field_problems("leader_ability", row)
                     + LG.ability_element_column_problems("leader_ability", row, ELEMENT)]
    for i, row in enumerate(ability1):
        problems += [f"{BALANCE_C_SWITCH_ABILITY_KEY}#{i}: {p}" for p in LG.client_legality_problems("ability", row)
                     + LG.declared_block_field_problems("ability", row)
                     + LG.invoke_skill_string_problems(row, {CHANGE_SKILL_LEADER_KEY}, kind="ability")
                     + LG.ability_element_column_problems("ability", row, ELEMENT)
                     + LG.required_client_capabilities("ability", row)]
    if any(ch.isdigit() for ch in CHANGE_SKILL_LEADER_TEXT) or any(w in CHANGE_SKILL_LEADER_TEXT
                                                                   for w in ("秒", "%", "％", "无上限")):
        problems.append(f"{CHANGE_SKILL_LEADER_KEY}: 技能强化条目不写数字/时长/无上限")
    if problems:
        raise KitError(f"balance-c rows rejected: {problems}")
    return leader, ability1, trace


def _statement_blocks(node, out: list | None = None) -> list[list]:
    """树里所有 ``["Block", [语句…]]`` 节点本身。"""
    out = [] if out is None else out
    if isinstance(node, list):
        if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
            out.append(node)
        for child in node:
            _statement_blocks(child, out)
    elif isinstance(node, dict):
        for child in node.values():
            _statement_blocks(child, out)
    return out


def balance_c_vid_scope_problems(tree) -> list[str]:
    """vlv 读的变量号必须被同一 Block 里排在前面的 Bind（或外层 Block 的 Bind）绑定过。

    ConditionalsChangeSkillFlag 的分支在新的局部环境执行（ActionEvaluator.as:4509-4526），局部环境只向外查找
    ⇒ 包进分支的 Bind 只对同一分支里它后面的判定区可见；wf_client_legality 的四道门只查主体 lookup，不查 vlv。
    """
    problems: list[str] = []

    def walk(node, visible: frozenset):
        if isinstance(node, dict):
            for term in node.get("vlv") or []:
                if term.get("vid") not in visible:
                    problems.append(f"vlv vid {term.get('vid')} unbound")
            for child in node.values():
                walk(child, visible)
        elif isinstance(node, list):
            if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
                bound = set(visible)
                for statement in node[1]:
                    walk(statement, frozenset(bound))
                    if (isinstance(statement, list) and len(statement) == 2 and statement[0] == "Command"
                            and statement[1][:1] == ["BindConditionAccumulationVariable"]):
                        bound.add(statement[1][2])
                return
            for child in node:
                walk(child, visible)

    walk(tree, frozenset())
    return problems


def balance_c_dup_bound_ids(tree) -> list[int]:
    """按分支判断的「绑定号唯一」：旗号分支两侧互斥，同一绑定号两侧各一份不算重复。"""
    from collections import Counter
    slots = {"FindAllSubjects": (1,), "FindNearSubjects": (5,), "CreateReferencePoint": (10,),
             "CreateHitArea": (19, 21, 22)}

    def count(node) -> Counter:
        found: Counter = Counter()
        if isinstance(node, dict):
            for child in node.values():
                found += count(child)
        elif isinstance(node, list):
            if len(node) == 2 and node[0] == "Command" and isinstance(node[1], list) and node[1]:
                c = node[1]
                if c[0] == "ConditionalsChangeSkillFlag":
                    return count(c[2]) | count(c[3])
                for slot in slots.get(c[0], ()):
                    found[c[slot]] += 1
                for child in c[1:]:
                    found += count(child)
                return found
            for child in node:
                found += count(child)
        return found

    return sorted(i for i, n in count(tree).items() if n > 1)


def balance_c_tree_problems(tree) -> list[str]:
    """包裹之后的门禁：fast_release.final_tree 用的 philia 门禁（绑定号唯一改为按分支判断）+ kit 快速门禁
    + lookup 作用域 + vlv 作用域。"""
    import wf_client_legality as LG
    import wf_seasonal7_kit_philia as PH
    problems = [f for f in PH.dsl_gate_failures(PH.dsl_gates(tree, element=ELEMENT))
                if not f.startswith("dup_bind_ids=")]
    problems += dsl_quick_problems(tree)
    problems += LG.action_dsl_lookup_scope_problems(tree)
    problems += balance_c_vid_scope_problems(tree)
    problems += [f"dup bind id {i} on one execution path" for i in balance_c_dup_bound_ids(tree)]
    return problems


def balance_c_skill_tree(tree: list) -> list:
    """第七轮：每处「Bind 起到块尾」整段 → ConditionalsChangeSkillFlag(3, 开支 Bind 上限 99, 关支 原段)。

    本树 11 个 Bind 都是所在 Block 的第 0 句（导弹落点、四段光束、终幕、5 个延长槽），整块语句表就是这一段；
    关支逐字保留第六轮（第二批）的段 ⇒ 非队长/不共鸣时与第二批完全相同；开支只把 Bind[5] 换成 int 99。
    事件名 / RemoveEventFromOwner / HideEffectFromOwner 用的名字都在分支外，根部旗号 2 护盾分支不动。
    """
    out = copy.deepcopy(tree)
    if [c for c in _command_nodes(out, "ConditionalsChangeSkillFlag") if c[1] == LEADER_SKILL_FLAG]:
        raise KitError("balance-c: 树里已经有旗号 3 分支（不可重复包裹）")
    capped = _bind_engine()
    blocks = _statement_blocks(out)
    targets = [b for b in blocks if b[1] and b[1][0] == capped]
    stray = [b for b in blocks for st in b[1][1:] if isinstance(st, list) and st[:1] == ["Command"]
             and st[1][:1] == ["BindConditionAccumulationVariable"]]
    if len(targets) != BALANCE_C_SEGMENTS or stray:
        raise KitError(f"balance-c: 期望 {BALANCE_C_SEGMENTS} 段以封顶 Bind 开头的块，实际 {len(targets)}"
                       f"（块中段 Bind {len(stray)} 个）")
    for block in targets:
        closed = copy.deepcopy(block[1])
        opened = [_bind_engine_leader(), *copy.deepcopy(block[1][1:])]
        block[1] = [_C("ConditionalsChangeSkillFlag", LEADER_SKILL_FLAG, _B(*opened), _B(*closed))]
    problems = balance_c_tree_problems(out)
    if problems:
        raise KitError(f"balance-c skill tree rejected: {problems[:5]}")
    return out


def revision_record_counts(rows: dict[str, list[list[str]]], leader: list[list[str]]) -> dict[str, int]:
    return {"leader": len(leader), "abilities": sum(len(v) for v in rows.values())}


def revision_donor_check(ctx, plan: dict, leader: list[list[str]]) -> list[dict]:
    """队长行与 plan 声明的 donor 逐列比对（donor 只作来源说明，不参与生成）；漂移只记录不阻塞。"""
    import re
    out = []
    live_cache: dict[str, dict] = {}

    def donor_row(spec: str):
        # 形如 "live leader_ability[169996] simoun_dark #3" / "live leader_ability[139993] #0 改 kind 35"
        # / "live leader_ability[139993] #0（during 134 同形）…" —— 序号后面可能紧跟中文括号，
        # 旧写法 ``split()[0]`` 会把「0（during」整串喂给 int() 而静默变成 error 项，用正则取数字。
        key = spec.split("[", 1)[1].split("]", 1)[0]
        match = re.search(r"#(\d+)", spec)
        if match is None:
            raise ValueError(f"donor spec 没有 #<序号>: {spec!r}")
        idx = int(match.group(1))
        if LEADER not in live_cache:
            live_cache[LEADER] = ctx.live_flat(LEADER)
        return list(ctx.csv_split(live_cache[LEADER][key])[idx])

    # 第三/四轮：队长行顺序按 LEADER_ORDER 重排、删了一行又加了五行 ⇒ 按 order 逐位取 donor 声明。
    plan_recs = {rec["index"]: rec for rec in plan["leader_ability"]["rows"]}
    new_specs = {spec["id"]: spec for spec in LEADER_NEW_SPECS}
    if len(leader) != len(LEADER_ORDER):
        raise KitError(f"leader donor check: {len(leader)} 行 != order {len(LEADER_ORDER)}")
    for pos, ((kind, ref), row) in enumerate(zip(LEADER_ORDER, leader)):
        rec = plan_recs[ref] if kind == "plan" else new_specs[ref]
        label = f"leader#{pos}" + (f"（plan#{ref}）" if kind == "plan" else f"（new {ref}）")
        try:
            donor = donor_row(rec["donor"])
        except (KeyError, IndexError, ValueError) as exc:
            out.append({"row": label, "donor": rec["donor"], "error": str(exc)})
            continue
        diff = {i: [donor[i], row[i]] for i in range(len(row)) if donor[i] != row[i]}
        out.append({"row": label, "req": rec.get("req"), "donor": rec["donor"], "source": kind,
                    "diff_cols": sorted(diff), "diff": diff})
    return out


# ================================================================ 固有状态与图标

def accumulation_cap_problems(ability_rows: dict[str, list[list[str]]], leader_rows: list[list[str]],
                              unique_rows: dict[str, list[str]]) -> list[str]:
    """被 during 134 按层数计数的固有，叠层上限 ``c4`` 必须是 >1 的整数。

    客户端 ``Condition.get_accumulatable() = maxAccumulation > 1``（``Condition.as:291-294``），
    为 false 时 ``_getConditionAccumulationCount`` 根本不计层 ⇒ 整条词条静默零收益，
    而面板照样渲染「…等级每提升 1 级时…」= 会骗人的面板。
    这是第五轮把能力2 改成 during-134 之后**新增**的失效面：旧的瞬发 SkillInvoke 行不读固有层数，
    所以现有门禁一条都覆盖不到它。本 kit 不写的固有（别家角色的）跳过，交给对方的 kit 自证。
    """
    counted = {str(row[104]) for rows in ability_rows.values() for row in rows
               if row[97] == "134" and row[104] and row[104] != "(None)"}
    counted |= {str(row[102]) for row in leader_rows if row[95] == "134" and row[102]}
    problems = []
    for uid in sorted(counted & set(unique_rows)):
        cap = unique_rows[uid][4]
        if not (cap.isdigit() and int(cap) > 1):
            problems.append(f"unique {uid} 被 during-134 按层数计数，但叠层上限 c4={cap!r} 不是 >1 的整数 "
                            "⇒ get_accumulatable() 为 false，层数永远不计，词条静默失效")
    return problems


def build_unique_rows(ctx, plan: dict) -> dict[str, list[str]]:
    """两个新固有状态：官方 donor ``1``（神速剑技，自身增益叠层）+ plan 声明列，与 plan 的整行逐格核对。

    ``c4`` 上限必须是整数：写 ``(None)`` 会被读成 1 层（记忆卡 wf-unique-cap-none-trap），
    「引擎启动·无上限」按官方口径取 99。
    """
    block = plan["unique_conditions"]
    if block["table"] != UNIQUE:
        raise KitError(f"revision unique table {block['table']}")
    donor = list(ctx.csv_split(ctx.official_flat(UNIQUE)[UNIQUE_DONOR])[0])
    if len(donor) != 15:
        raise KitError(f"official unique_condition donor has {len(donor)} columns")
    rows: dict[str, list[str]] = {}
    for entry in block["add"]:
        uid = entry["key"]
        meta = UNIQUE_META.get(uid)
        if meta is None or entry["op"] != "add":
            raise KitError(f"unexpected unique_condition entry {uid}/{entry.get('op')}")
        row = list(donor)
        row[0], row[1] = meta["string_id"], meta["name"]
        row[2] = f"{UNIQUE_ICON_DIR}/{meta['string_id']}"
        row[3], row[4] = meta["duration"], meta["max"]
        want = list(entry["row"])
        fix = UNIQUE_FIXES.get(uid)
        if fix is not None:
            col, cur = fix["col"], want[fix["col"]]
            if cur == fix["plan"]:
                want[col] = fix["fixed"]
            elif cur != fix["fixed"]:
                raise KitError(f"unique_condition {uid} c{col} plan value {cur!r} is neither "
                               f"{fix['plan']!r} nor {fix['fixed']!r}; re-check the revision plan")
        if row != want:
            diff = {i: [a, b] for i, (a, b) in enumerate(zip(row, want)) if a != b}
            raise KitError(f"unique_condition {uid} donor+meta != plan row(+rev2 fixes): {diff}")
        if row[4] in ("", "(None)") or not row[4].isdigit():
            raise KitError(f"unique_condition {uid} max_accumulation must be an integer, got {row[4]!r}")
        if entry["icon"]["logical"] != UNIQUE_ICON[uid] or tuple(entry["icon"]["size"]) != (48, 48):
            raise KitError(f"unique_condition {uid} icon path/size differs from plan")
        rows[uid] = row
    if sorted(rows) != sorted(UNIQUE_META):
        raise KitError(f"unique_condition keys {sorted(rows)} != {sorted(UNIQUE_META)}")
    return rows


def _icon_canvas(top: tuple, bottom: tuple):
    """48×48 固有状态图标的底：8× 画布 + 圆角内底的竖向渐变（官方风格 = 饱和底色 + 纯白剪影 glyph）。

    官方 108 张 unique_condition 图标的统计口径：圆角方底 + 白描边（alpha 由 donor 提供），
    底色是一块饱和色（雷/增益系多为橙琥珀，蓝系用于展开/装填类），glyph 一律是单色白剪影，
    需要第二层信息时用「把底色抠回来」的负形，而不是再加一种颜色。
    """
    from PIL import Image, ImageDraw
    k, n = 8, 48 * 8
    layer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    inner = Image.new("L", (n, n), 0)
    ImageDraw.Draw(inner).rounded_rectangle((3 * k, 3 * k, 45 * k - 1, 45 * k - 1), radius=5 * k, fill=255)
    grad = Image.new("RGBA", (1, n))
    for y in range(n):
        t = y / (n - 1)
        grad.putpixel((0, y), tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    layer.paste(grad.resize((n, n)), (0, 0), inner)
    return layer, inner, k, n


def _paint_glyph(layer, inner, glyph, color=(255, 255, 255, 255)):
    """把 glyph 掩膜（255=上色）按纯色刷到底上，并裁进圆角内底。"""
    from PIL import Image
    n = layer.size[0]
    mask = Image.new("L", (n, n), 0)
    mask.paste(glyph, (0, 0), inner)
    layer.paste(Image.new("RGBA", (n, n), color), (0, 0), mask)
    return layer


def _icon_finish(layer, frame):
    """缩回 48×48，颜色按自身 alpha 预合成到白底，再套官方图标外框的 alpha（形状/白边一致）。"""
    from PIL import Image
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


def draw_engine_icon(frame):
    """「引擎启动」：琥珀橙底 + 白色齿轮环，环心一道白色闪电（雷属性 / 引擎转速），

    闪电与齿轮之间留一圈底色负形缝，48px 下两个形状仍分得开。
    """
    from PIL import Image, ImageDraw
    layer, inner, k, n = _icon_canvas((255, 184, 56), (233, 118, 22))
    glyph = Image.new("L", (n, n), 0)
    g = ImageDraw.Draw(glyph)
    cx = cy = 24.0
    teeth, r_out, r_in, r_hole = 8, 17.6, 13.6, 9.2
    poly = []
    for i in range(teeth * 2):
        a = math.pi * i / teeth - math.pi / 2
        r = r_out if i % 2 == 0 else r_in
        half = (math.pi / teeth) * (0.34 if i % 2 == 0 else 0.50)
        for da in (-half, half):
            poly.append(((cx + r * math.cos(a + da)) * k, (cy + r * math.sin(a + da)) * k))
    g.polygon(poly, fill=255)
    g.ellipse(((cx - r_hole) * k, (cy - r_hole) * k, (cx + r_hole) * k, (cy + r_hole) * k), fill=0)
    bolt = [(26.8, 8.0), (17.4, 24.6), (22.8, 24.6), (20.4, 40.0), (31.0, 22.4), (25.0, 22.4), (29.4, 8.0)]
    pts = [(x * k, y * k) for x, y in bolt]
    g.line(pts + [pts[0]], fill=0, width=int(3.0 * k), joint="curve")   # 负形缝：先描粗再挖空
    g.polygon(pts, fill=255)
    _paint_glyph(layer, inner, glyph)
    return _icon_finish(layer, frame)


def draw_cannon_icon(frame):
    """「重炮展开」：钴蓝底 + 白色重炮剪影（炮口法兰 + 炮管）+ 上方三道白光柱。"""
    from PIL import Image, ImageDraw
    layer, inner, k, n = _icon_canvas((86, 164, 255), (34, 78, 186))
    glyph = Image.new("L", (n, n), 0)
    g = ImageDraw.Draw(glyph)

    def poly(points, fill=255):
        g.polygon([(x * k, y * k) for x, y in points], fill=fill)

    poly([(9.5, 5.0), (38.5, 5.0), (31.2, 23.4), (16.8, 23.4)])          # 光柱整体（上宽下窄）
    poly([(18.2, 5.0), (21.2, 5.0), (22.5, 23.4), (20.9, 23.4)], 0)      # 负形缝 1
    poly([(26.8, 5.0), (29.8, 5.0), (27.1, 23.4), (25.5, 23.4)], 0)      # 负形缝 2
    g.rounded_rectangle((12.4 * k, 24.0 * k, 35.6 * k, 30.0 * k), radius=int(1.6 * k), fill=255)   # 炮口法兰
    poly([(17.4, 30.0), (30.6, 30.0), (29.4, 42.0), (18.6, 42.0)])       # 炮管
    poly([(18.3, 33.6), (29.7, 33.6), (29.4, 36.0), (18.6, 36.0)], 0)    # 炮管接缝（负形）
    _paint_glyph(layer, inner, glyph)
    return _icon_finish(layer, frame)


ICON_PAINTERS = {UID_ENGINE: draw_engine_icon, UID_CANNON: draw_cannon_icon}


def install_unique_icons(ctx) -> dict[str, Any]:
    """画两张 48×48 图标并写入包（存储态 PNG，小写魔数）；alpha 必须等于官方图标外框。"""
    frame_raw = ctx.official_read(UNIQUE_ICON_FRAME_DONOR)
    if frame_raw is None:
        _root, frame_raw, _how = ctx.pack.template_asset(UNIQUE_ICON_FRAME_DONOR)
    frame = ctx.png_open(frame_raw)
    if frame.size != (48, 48):
        raise KitError(f"icon frame donor must be 48x48, got {frame.size}")
    out = {}
    for uid, painter in ICON_PAINTERS.items():
        logical = UNIQUE_ICON[uid]
        data = ctx.png_store_bytes(painter(frame))
        ctx.write_asset("common", logical, data, owner="kit")
        back = ctx.png_open(ctx.pack.pkg_path("common", logical).read_bytes())
        if back.size != (48, 48) or back.getchannel("A").tobytes() != frame.getchannel("A").tobytes():
            raise KitError(f"unique_condition icon {uid} size/alpha differ from the official frame donor")
        if back.getchannel("R").tobytes() == frame.getchannel("R").tobytes():
            raise KitError(f"unique_condition icon {uid} RGB unchanged vs the frame donor (not drawn?)")
        out[uid] = {"logical": logical, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                    "frame_donor": UNIQUE_ICON_FRAME_DONOR}
    return out


# ================================================================ 指纹（kit 产物 → gates 绑定）

def owned_table_rows(pack) -> dict[str, Any]:
    import wf_mod_tool as core
    import wf_seasonal7_common as C
    out: dict[str, Any] = {}
    flat = {CHAR: [CID], TEXT: [CID], LEADER: [CID], ABILITY: [f"{CID}{i}" for i in range(1, 7)],
            CAS: [CHANGE_SKILL_KEY, CHANGE_SKILL2_KEY], UNIQUE: sorted(UNIQUE_META)}
    for logical, keys in flat.items():
        rows = pack.pkg_flat(logical) if pack.pkg_has("common", logical) else {}
        out[logical] = {k: rows.get(k) for k in keys}
    for logical, key in ((ACTION, CODE), (SWITCHED, VOICE_READY_KEY)):
        if pack.pkg_has("common", logical):
            nested = core.load_nested_table_bytes(pack.pkg_path("common", logical).read_bytes(), logical)
            out[logical] = {key: nested.rows[key].text_rows() if key in nested.rows else None}
        else:
            out[logical] = {key: None}
    caps_keys = (CHANGE_SKILL_KEY, CHANGE_SKILL2_KEY)
    if pack.pkg_has("common", CAPS):
        om = core.read_orderedmap_raw_rows_from_bytes(pack.pkg_path("common", CAPS).read_bytes(), CAPS)
        blobs = dict(zip(om.keys, om.rows))
        out[CAPS] = {k: None if blobs.get(k) is None else C.sha256(blobs[k]) for k in caps_keys}
    else:
        out[CAPS] = {k: None for k in caps_keys}
    return out


def kit_fingerprint(pack) -> dict[str, Any]:
    """kit 产物指纹：设计 JSON、kit 源码、kit/effects/pixel 登记的文件字节与 kit 自有表行。"""
    import wf_seasonal7_common as C
    files = {}
    for entry, record in sorted(pack._owned_raw().items()):
        if record.get("owner") not in ("kit", "effects", "pixel"):
            continue
        root, logical = entry.split(":", 1)
        path = pack.pkg_path(root, logical)
        files[entry] = C.sha256(path.read_bytes()) if path.is_file() else None
    payload = {
        "design_sha256": C.sha256((pack.root / DESIGN_REL).read_bytes()),
        "kit_source_sha256": C.sha256(KIT_SOURCE.read_bytes()),
        "files": files,
        "rows": owned_table_rows(pack),
    }
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {"sha256": digest, "file_count": len(files)}


# ================================================================ build

def build(ctx) -> dict[str, Any]:
    import wf_client_legality as LG
    import wf_describe
    import wf_mod_tool as core
    import wf_seasonal7_voice as V
    spec, pack = ctx.spec, ctx.pack
    if (spec.key, spec.cid_s, spec.code, spec.template_code, spec.element) != (KEY, CID, CODE, TEMPLATE_CODE, ELEMENT):
        raise KitError(f"spec mismatch for tekuto kit: {spec.key}/{spec.cid}/{spec.code}")
    design = load_design(ctx.root)
    plan = load_revision_plan(ctx.root)
    notes: list[str] = []
    derivation: dict[str, Any] = {"revision_plan": {"path": REVISION_REL, "sha256": PLAN_CACHE["sha256"]}}

    # ---- 文案一致性：身份文案沿用设计稿；技能说明按改版短文覆盖（设计稿不在本轮可写范围）
    text_row = list(design["text"]["character_text_row"])
    plan_desc = plan["texts"]["action_skill_desc"]
    if (plan_desc["old"], plan_desc.get("r1_new"), plan_desc["new"], plan_desc["column"]) \
            != (_DESIGN_DESC, _R1_DESC, _DESC, "c1"):
        raise KitError("revision plan action_skill_desc does not match the kit's _DESIGN_DESC/_R1_DESC/_DESC")
    if [text_row[5], text_row[7]] != [_DESIGN_DESC, _DESIGN_DESC]:
        raise KitError("design character_text desc columns are no longer the pre-revision text")
    # 改版：技能说明压到 60 字（作者要求 D8）；S18 再追加「不再进入硬直」一句（2026-09-21）；
    # 2026-09-27 平衡第二批再写出技能倍率的层数上限「（最多10层）」；第三批不在技能说明里写强化后的不封顶（只写在强化条目）
    text_row[5] = text_row[7] = _DESC_BALANCE_C
    want = {"profile": text_row[2], "skill1": text_row[4], "desc1": text_row[5], "skill2": text_row[6],
            "desc2": text_row[7], "cv": text_row[11]}
    for name, value in want.items():
        if spec.texts.get(name) != value:
            raise KitError(f"TEXTS[{name}] differs from the revised text row")
    for name, idx in (("name", 0), ("furigana", 1), ("title", 3), ("leader", 10)):
        if spec.texts.get(name) != text_row[idx]:
            raise KitError(f"spec texts[{name}]={spec.texts.get(name)!r} != design {text_row[idx]!r}")

    # ---- 队长 / 词条：plan 行（队长整体替换、词条按 old→new 编辑或新增）+ 合法性
    leader_rows = revision_leader_rows(plan)
    current_ability = {key: [list(r) for r in ctx.csv_split(text)]
                       for key, text in ctx.pkg_flat(ABILITY).items() if key.startswith(CID)}
    if sorted(current_ability) != [f"{CID}{i}" for i in range(1, 7)]:
        raise KitError(f"package ability keys {sorted(current_ability)} (rerun tables?)")
    ability_rows, ability_trace = revision_ability_rows(plan, current_ability)
    derivation["revision_ability_edits"] = ability_trace
    derivation["revision_leader_vs_donor"] = revision_donor_check(ctx, plan, leader_rows)
    derivation["record_counts"] = revision_record_counts(ability_rows, leader_rows)
    legality: dict[str, list[str]] = {}
    for i, row in enumerate(leader_rows):
        probs = (LG.client_legality_problems("leader_ability", row)
                 + LG.declared_block_field_problems("leader_ability", row)
                 + LG.ability_element_column_problems("leader_ability", row, ELEMENT))
        if len(row) != 124 or row[0] != CODE:
            probs.append(f"leader row shape/id: len={len(row)} c0={row[0]}")
        legality[f"leader#{i}"] = probs
    for key, rows in ability_rows.items():
        if len(rows) > 9:                                  # 一键最多 9/10 条（记忆卡 wf-ability-multirecord-rows）
            raise KitError(f"{key}: more than 9 records")
        for i, row in enumerate(rows):
            probs = (LG.client_legality_problems("ability", row)
                     + LG.declared_block_field_problems("ability", row)
                     + LG.ability_element_column_problems("ability", row, ELEMENT))
            if len(row) != 126 or row[0] != f"{CODE}_{key[-1]}":
                probs.append(f"ability row shape/id: len={len(row)} c0={row[0]}")
            if row[1] != rows[0][1]:
                probs.append("c1 unisonable differs within key")
            legality[f"{key}#{i}"] = probs
    bad = {k: v for k, v in legality.items() if v}
    if bad:
        raise KitError(f"row legality problems: {bad}")
    caps = sorted({cap for row in leader_rows for cap in LG.required_client_capabilities("leader_ability", row)}
                  | {cap for rows in ability_rows.values() for row in rows
                     for cap in LG.required_client_capabilities("ability", row)})
    if caps:
        raise KitError(f"tekuto rows unexpectedly need client capabilities {caps} (plan: none)")
    import wf_tekuto_low_hp as low_hp
    leader_rows, ability_rows[CID+'3'] = low_hp.revise_rows(leader_rows, ability_rows[CID+'3'])
    # 第六轮（2026-09-27 平衡第二批）：叠在 low_hp 之后；与 wf_balance_20260927b_tekuto.revise() 同表
    leader_rows, ability_rows[REV5_ABILITY_KEY], balance_b_trace = apply_balance_b(
        leader_rows, ability_rows[REV5_ABILITY_KEY])
    derivation["balance_20260927b"] = balance_b_trace
    # 第七轮（2026-09-27 平衡第三批）：叠在第六轮之后；与 wf_balance_20260927c_tekuto.revise() 同表
    leader_rows, ability_rows[BALANCE_C_SWITCH_ABILITY_KEY], balance_c_trace = apply_balance_c(
        leader_rows, ability_rows[BALANCE_C_SWITCH_ABILITY_KEY])
    derivation["balance_20260927c"] = balance_c_trace
    ctx.write_flat(LEADER, {CID: leader_rows})
    ctx.write_flat(ABILITY, ability_rows)

    # ---- 固有状态两键 + 两张 48×48 图标
    unique_rows = build_unique_rows(ctx, plan)
    unique_rows[UID_CANNON] = low_hp.revise_unique([unique_rows[UID_CANNON]])[0]
    ctx.write_flat(UNIQUE, {uid: [row] for uid, row in unique_rows.items()})
    icons = install_unique_icons(ctx)
    derivation["unique_condition"] = {uid: {"row": row, "icon": icons[uid]} for uid, row in unique_rows.items()}
    derivation["rev2_unique_fixes"] = REV2_UNIQUE_FIXES
    derivation["rev3_unique_fixes"] = REV3_UNIQUE_FIXES
    # 固有 id 的引用面：leader 前置 c102 / 瞬发 461 的 c66；ability 前置 c19 / 瞬发 461 的 c68 /
    # **持续 134 的 c104**（第五轮 T3 的引用落点，普查漏了它就等于少一份证据）
    referenced_uids = {str(row[102]) for row in leader_rows if row[102]} | {str(row[66]) for row in leader_rows if row[66]}
    for rows in ability_rows.values():
        referenced_uids |= {str(row[19]) for row in rows if row[19] and row[19] != "(None)"}
        referenced_uids |= {str(row[68]) for row in rows if row[68]}
        referenced_uids |= {str(row[104]) for row in rows if row[104] and row[104] != "(None)"}
    if not set(UNIQUE_META) <= referenced_uids:
        raise KitError(f"rows reference unique ids {sorted(referenced_uids)}; both {sorted(UNIQUE_META)} must be used")
    for problem in accumulation_cap_problems(ability_rows, leader_rows, unique_rows):
        raise KitError(problem)

    # ---- 字符串：两个开关槽的 custom_ability_string + 各自的潜能 2–6 文案
    cas_plan = plan["texts"]["custom_ability_string"]
    if cas_plan["table"] != CAS:
        raise KitError(f"revision custom_ability_string table {cas_plan['table']}")
    cas_rows, cas_slots, cas_fixes = {}, {}, []
    for entry in cas_plan["rows"]:
        text = entry["new"]
        fix = REV2_TEXT_FIXES.get(entry["key"])
        if fix is not None:
            if text == fix["plan"]:
                text, state = fix["fixed"], "applied"
            elif text == fix["fixed"]:
                state = "already-in-plan"
            else:
                raise KitError(f"custom_ability_string {entry['key']} plan.new is neither the recorded "
                               f"plan text nor the rev2 text; re-check the revision plan")
            cas_fixes.append({"key": entry["key"], "state": state, "plan": fix["plan"],
                              "fixed": fix["fixed"], "reason": fix["reason"]})
        cas_rows[entry["key"]] = text
        cas_slots[entry["key"]] = entry["slot"]
        current = ctx.pkg_flat(CAS).get(entry["key"])
        if entry["op"] == "edit" and current not in (entry["old"], entry["new"], text, low_hp.SHIELD_TEXT):
            raise KitError(f"custom_ability_string {entry['key']} current text is neither plan.old/new nor rev2")
    banned = [(k, w) for k, v in cas_rows.items() for w in ("无上限", "可无限", "可累计") if w in v]
    if banned:
        raise KitError(f"custom_ability_string 违反第二轮文案规则①: {banned}")
    if any(ch.isdigit() for v in cas_rows.values() for ch in v) or any("秒" in v for v in cas_rows.values()):
        raise KitError(f"custom_ability_string 违反第二轮文案规则②（技能强化条目不写数字/秒）: {cas_rows}")
    if sorted(cas_rows) != sorted((CHANGE_SKILL_KEY, CHANGE_SKILL2_KEY)) \
            or cas_slots != {CHANGE_SKILL_KEY: 1, CHANGE_SKILL2_KEY: 2}:
        raise KitError(f"revision custom_strings unexpected: {cas_slots}")
    # 开关槽 → 词条内容 kind：536=槽1、704=槽2（InstantAbilitySource.as:5015/5880；两表列足迹同为 parseAt70）
    slot_kind = {"536": 1, "704": 2}
    referenced = {row[70]: slot_kind[row[47]] for rows in ability_rows.values() for row in rows
                  if row[47] in slot_kind}
    extra = {row[70] for rows in ability_rows.values() for row in rows if row[47] in ("629", "722")}
    if referenced != cas_slots or extra:
        raise KitError(f"ability string refs {referenced} (+{extra}) != plan slots {cas_slots}")
    cas_rows[CHANGE_SKILL2_KEY] = low_hp.SHIELD_TEXT
    # 第七轮：旗号 3（705）开关行的「技能强化」条目（不写数字/共鸣前缀；特克托无 desc_override，显示在能力 1 面板）
    switch_refs = [row[70] for rows in ability_rows.values() for row in rows if row[47] == BALANCE_C_SWITCH_KIND]
    if switch_refs != [CHANGE_SKILL_LEADER_KEY]:
        raise KitError(f"705 switch rows reference {switch_refs}, expected [{CHANGE_SKILL_LEADER_KEY}]")
    cas_rows[CHANGE_SKILL_LEADER_KEY] = CHANGE_SKILL_LEADER_TEXT
    ctx.write_flat(CAS, cas_rows)
    derivation["rev2_text_fixes"] = cas_fixes
    unclaimed: list[str] = []
    live_caps = core.read_orderedmap_raw_rows_from_bytes(core.table_path(ctx.store, CAPS).read_bytes(), CAPS)
    live_caps_map = dict(zip(live_caps.keys, live_caps.rows))
    official_caps_raw = ctx.official_read(CAPS, "common")
    off_map = {}
    if official_caps_raw is not None:
        off = core.read_orderedmap_raw_rows_from_bytes(official_caps_raw, CAPS)
        off_map = dict(zip(off.keys, off.rows))
    caps_blobs, power_up_info = {}, {}
    for key, source in POWER_UP_SOURCES.items():
        blob = live_caps_map.get(source)
        basis = "official baseline missing"
        if off_map:
            basis = "live==official" if off_map.get(source) == blob else "live differs from official; official used"
            if off_map.get(source) is not None:
                blob = off_map[source]
        if blob is None:
            raise KitError(f"power_up source key missing: {source}")
        inner = core.read_orderedmap_raw_rows_from_bytes(blob, "levels")
        levels = {k: zlib.decompress(r).decode("utf-8") for k, r in zip(inner.keys, inner.rows)}
        if set(levels) != {"2", "3", "4", "5", "6"} or set(levels.values()) != {POWER_UP_TEXTS[key]}:
            raise KitError(f"unexpected official power_up text for {source}: {levels}")
        caps_blobs[key] = blob
        power_up_info[key] = {"op": "clone_official", "source": source, "levels": levels, "basis": basis}
    # 审查 R-M1：槽2 的潜能插值只落在雷达 Sector 的半径/角度上，官方 37 个潜能文案里没有「范围」类 ⇒ 自建。
    # 先例 = live change_skill_lady_summoner_campus_dragon（自建行，core.build_orderedmap 对它逐字节往返一致）。
    for key, text in POWER_UP_CUSTOM.items():
        blob = core.build_orderedmap(core.OrderedMap(
            "levels", list(POWER_UP_LEVELS), [text.encode("utf-8")] * len(POWER_UP_LEVELS), Path("levels")))
        back = core.read_orderedmap_raw_rows_from_bytes(blob, "levels")
        levels = {k: zlib.decompress(r).decode("utf-8") for k, r in zip(back.keys, back.rows)}
        if list(back.keys) != list(POWER_UP_LEVELS) or set(levels.values()) != {text}:
            raise KitError(f"custom power_up blob roundtrip failed for {key}: {levels}")
        caps_blobs[key] = blob
        power_up_info[key] = {"op": "build_custom", "levels": levels,
                              "basis": "self-built (no official 范围 wording); roundtrip verified"}
    caps_plan = plan["texts"].get("custom_ability_power_up_string")
    want_caps = {r["key"]: (r["op"], r["text"]) for r in (caps_plan or {}).get("rows", [])}
    got_caps = {k: (v["op"], sorted(set(v["levels"].values()))[0]) for k, v in power_up_info.items()}
    if want_caps != got_caps:
        raise KitError(f"power_up rows {got_caps} != plan {want_caps}")
    if sorted(caps_blobs) != sorted((CHANGE_SKILL_KEY, CHANGE_SKILL2_KEY)):
        raise KitError(f"power_up keys {sorted(caps_blobs)}")
    ctx.write_raw_outer(CAPS, caps_blobs)
    derivation["power_up_string"] = power_up_info

    # ---- action_skill 两档 + switched_action_skill（语音路由）
    placeholder = ctx.pkg_nested(CODE)
    action_rows = {lv: list(cells) for lv, cells in design["skills"]["action_skill_rows"].items()}
    if set(action_rows) != {"1", "2"} or set(placeholder) != {"1", "2"}:
        raise KitError("action_skill levels must be 1/2")
    if sorted(plan_desc["apply_to_levels"]) != ["1", "2"]:
        raise KitError("revision plan action_skill_desc must apply to both levels")
    for lv, cells in action_rows.items():
        if cells[1] != _DESIGN_DESC:
            raise KitError(f"design action_skill row {lv} c1 is no longer the pre-revision text")
        cells[1] = _DESC                                   # 改版 D8：技能说明真源 = action_skill c1
        if len(cells) != 24 or cells[7] != ctx.program_path(lv):
            raise KitError(f"action_skill row {lv} shape/program mismatch")
        energy = design["skills"]["energy"][lv]
        if (cells[4], cells[5], cells[6]) != (energy["c4"], energy["c5"], energy["c6"]):
            raise KitError(f"action_skill row {lv} energy mismatch")
        if (cells[0], cells[1]) != (spec.texts[f"skill{lv}"], spec.texts[f"desc{lv}"]):
            raise KitError(f"action_skill row {lv} text differs from TEXTS")
        changed = [i for i, (a, b) in enumerate(zip(placeholder[lv], cells)) if a != b]
        if not set(changed) <= {0, 1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16}:
            raise KitError(f"action_skill row {lv} changes unexpected columns vs template placeholder: {changed}")
        derivation.setdefault("action_skill_changed_cols", {})[lv] = changed
    ctx.write_nested(ACTION, CODE, {lv: [cells] for lv, cells in action_rows.items()})
    route = design["voice"]["route"]
    route_cols = V.normalize_route(route["c9_16"], CODE)
    switched = V.switched_rows(action_rows)
    design_switched = route["switched_action_skill"]
    if design_switched["key"] != VOICE_READY_KEY or design_switched["inner"] != switched:
        raise KitError("design switched_action_skill inner rows differ from action_skill c7-c23")
    ctx.write_nested(SWITCHED, VOICE_READY_KEY, {lv: [cells] for lv, cells in switched.items()}, replace_inner=True)

    # ---- character 行：c9–c16 路由；其余 spec 列核对设计
    crow = pack.pkg_character_row()
    edits = design["identity"]["character_row_edits_vs_131092"]
    checks = {0: CODE, 8: CODE, 17: CID, 18: edits["18"], 26: edits["26"], 27: edits["27"], 36: edits["36"],
              6: str(design["identity"]["pf_type"]), 3: str(ELEMENT), 2: "5"}
    for col, value in checks.items():
        if crow[col] != value:
            raise KitError(f"character c{col}={crow[col]!r} != design {value!r} (rerun tables?)")
    if crow[19:25] != edits["19..24"]:
        raise KitError("character c19-c24 ability keys differ from design")
    if list(edits["9..16"]) != route_cols:
        raise KitError("design c9-16 differs from voice route")
    crow = V.route_character_row(crow, route_cols, CODE)
    ctx.write_flat(CHAR, {CID: [crow]})
    trow = pack.pkg_character_text_row()
    if trow != text_row:
        # tables 按 TEXTS 生成；仍不同说明 tables 未带改版 TEXTS 重跑，这里按改版行写并提示
        notes.append("character_text 行与改版文案不一致，已按改版写入（tables 重跑会得到同样的行）")
        ctx.write_flat(TEXT, {CID: [text_row]})
    mirrors = ctx.sync_character_mirrors()

    # ---- 特效族克隆（染色钩子）
    fx_map, fx_info = load_fx_manifest(ctx.root)
    recolor_stats: dict[str, Any] = {}
    families = []
    for src_dir, sub, fx_names in FAMILIES:
        donor = src_dir.rsplit("/", 1)[-1]
        sheet = f"{src_dir}/{donor}.png"
        transform = make_png_transform(sheet, fx_map[sheet], recolor_stats) if sheet in fx_map else None
        fam = ctx.clone_effect_family(src_dir, sub, fx_names=fx_names, layout="codename", png_transform=transform)
        if fam["missing_effects"] or sorted(fam["copied_bases"]) != sorted(fx_names):
            raise KitError(f"effect family {sub} incomplete: missing={fam['missing_effects']}")
        families.append(fam)
    unused_fx = sorted(set(fx_map) - set(recolor_stats))
    if unused_fx:
        raise KitError(f"fx manifest sheets not applied: {unused_fx}")
    # 第三轮 A：克隆之后立刻补 laser_lll 的「无头块」（不接这一步，每次 --step kit 都会还原成母本）
    lll_fix = repair_lll_head(ctx, pack)
    derivation["lll_head_patch"] = lll_fix
    notes.append(f"laser_lll 无头块修复（第三轮 A，forensics.md §2）：{lll_fix['status']}，"
                 f"坏块 {lll_fix['bad_block_before']} → {lll_fix['bad_block_after']}")
    fx_sheets = {}
    for fam in families:
        sheet_logical = f"{fam['dst_dir']}/{fam['dst_dir'].rsplit('/', 1)[-1]}.png"
        src_sheet = f"{fam['src_dir']}/{fam['src_dir'].rsplit('/', 1)[-1]}.png"
        pkg_raw = pack.pkg_path("common", sheet_logical).read_bytes()
        entry = {"logical": sheet_logical, "package_sha256": hashlib.sha256(pkg_raw).hexdigest(),
                 "owner": pack.owner_of("common", sheet_logical)}
        if src_sheet in fx_map:
            dyed_raw = fx_map[src_sheet].read_bytes()
            want = ctx.png_store_bytes(ctx.png_open(dyed_raw))   # 框架存储态（PIL optimize 重编码 + 小写魔数）
            entry.update(dyed_file=str(fx_map[src_sheet]), dyed_sha256=hashlib.sha256(dyed_raw).hexdigest(),
                         framework_store_sha256=hashlib.sha256(want).hexdigest(),
                         package_equals_framework_store=pkg_raw == want)
            if pkg_raw != want:
                raise KitError(f"recolored sheet not applied byte-exact (framework store form): {sheet_logical}")
        fx_sheets[fam["dst_dir"].rsplit("/", 1)[-1]] = entry

    # ---- 像素小人（门禁通过才写；否则保持母本原色）
    pixel = integrate_pixel(ctx)

    # ---- 技能 DSL
    dsl_report: dict[str, Any] = {}
    programs = []
    for lv in ("1", "2"):
        tree = donor_tree(lv, plan)
        kept_all: set[str] = set()
        rewritten = 0
        for fam in families:
            tree, info = ctx.rewrite_effect_refs(tree, fam)
            rewritten += info["rewritten"]
            kept_all |= set(info["kept_donor"])
        leftover = sorted(v for v in ctx.walk(tree) if isinstance(v, str)
                          and (v.startswith(CANNON_SRC + "/") or "enemy_shot_laser_" in v and "/enemy_general/" in v))
        if leftover:
            raise KitError(f"level {lv}: donor effect refs not rewritten: {leftover[:5]}")
        # 改版逐条对账（plan.json 是外部方案，kit 只是实现方）
        rprobs, rfacts = revision_tree_problems(tree, lv, plan)
        if rprobs:
            raise KitError(f"level {lv}: revision plan not satisfied: {rprobs[:5]}")
        wprobs = cooldown_width_problems(tree)
        if wprobs:
            raise KitError(f"level {lv}: cooldown effect width problems: {wprobs}")
        bprobs = beam_overlap_problems(tree)
        if bprobs:
            raise KitError(f"level {lv}: S14 同族光柱同屏（闪烁）: {bprobs}")
        template = ctx.template_dsl(f"battle/action/skill/action/rare5/{TEMPLATE_CODE}${TEMPLATE_CODE}_{lv}")
        tprobs, tfacts = template_derivation_problems(tree, template, lv)
        if tprobs:
            raise KitError(f"level {lv}: template derivation problems: {tprobs}")
        tree = low_hp.revise_skill(tree)
        qprobs = dsl_quick_problems(tree)
        if qprobs:
            raise KitError(f"level {lv}: DSL problems: {qprobs}")
        # 作者 2026-09-21 确认 A+B；先验证原蓝图，再应用已验证的时间轴变换。
        # 候选修订与重跑 kit 共用此入口，防止下一次构建带回 90 帧前摇。
        from wf_tekuto_fast_release import final_tree
        tree = final_tree(tree)
        # 第七轮（2026-09-27 平衡第三批）：担任队长且雷共鸣（旗号 3）时 Bind 上限回到 99；必须在 final_tree 之后
        # （final_tree 的 philia 门禁按全树判绑定号唯一，分支两侧各一份会被它拦下；这里改为按分支判断）。
        tree = balance_c_skill_tree(tree)
        logical = ctx.write_dsl(ctx.program_path(lv), tree)
        programs.append(logical)
        # 定稿树落盘到 revision 目录（gates 的漂移对照；只写 revision 目录，不进包）
        final_path = ctx.root / FINAL_TREE_REL.format(level=lv)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_text(json.dumps(tree, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        # 上一轮设计树的结构差异（只做证据，不做门禁——改版就是要偏离它）
        old_tree, _fixes = design_composed_tree(design, lv)
        dsl_report[lv] = {"logical": logical, "rewritten_refs": rewritten,
                          "revision_facts": rfacts, "revision_problems": rprobs,
                          "final_tree_json": FINAL_TREE_REL.format(level=lv),
                          "diff_vs_previous_design": len(strict_diff(tree, old_tree, limit=10000)),
                          "cooldown_width_problems": wprobs, "beam_overlap_problems": bprobs,
                          "template_derivation": tfacts, "quick_problems": qprobs,
                          "final_windup_frames": 36, "extra_ball_hold_frames": 0,
                          "leader_uncap_flag": {"flag": LEADER_SKILL_FLAG, "segments": BALANCE_C_SEGMENTS,
                                                "cap_closed": ENGINE_CAP, "cap_open": ENGINE_CAP_LEADER}}

    # ---- 详情页技能预览 end_frame
    _root, template_raw, source = pack.template_asset(TEMPLATE_PREVIEW)
    preview = ctx.amf_parse(template_raw)
    before = copy.deepcopy(preview)
    edit = design["skills"]["preview_edit"]
    if edit["logical"] != PREVIEW or edit["edits"] != {"config.end_frame": PREVIEW_END_FRAME}:
        raise KitError("design preview_edit changed; update kit")
    if preview["config"]["end_frame"] != 350 or preview["config"]["start_frame"] != 90:
        raise KitError(f"template preview config unexpected: {preview['config']}")
    preview["config"]["end_frame"] = PREVIEW_END_FRAME
    ctx.write_asset("common", PREVIEW, ctx.amf_bytes(preview), owner="kit")
    derivation["preview"] = {"source": source, "before": before["config"], "after": preview["config"],
                             "log_parts": preview["log_parts"]}

    # ---- 面板（wf_describe）
    panel = []
    for line in wf_describe.describe_rows(leader_rows, "leader_ability"):
        panel.append("队长：" + line)
    for key, rows in ability_rows.items():
        for line in wf_describe.describe_rows(rows, "ability"):
            panel.append(f"能力{key[-1]}（{'Ⓜ' if rows[0][1] == 'false' else '—'}）：{line}")

    evidence = {
        "design": DESIGN_REL, "design_sha256": hashlib.sha256((ctx.root / DESIGN_REL).read_bytes()).hexdigest(),
        "revision": REVISION_REL, "revision_sha256": PLAN_CACHE["sha256"],
        "derivation": derivation, "legality": legality, "required_capabilities": caps,
        "unclaimed": unclaimed, "effects": [{k: f[k] for k in ("src_dir", "dst_dir", "copied_bases")} for f in families],
        "fx_manifest": fx_info, "recolor": recolor_stats, "fx_sheets": fx_sheets, "pixel": pixel,
        "voice": voice_state(pack), "dsl": dsl_report,
        "voice_route": route_cols, "mirrors": {"server_character": mirrors["server_character"]},
        "notes": notes,
    }
    ctx.evidence_write("kit-derivation.json", evidence)

    fingerprint = kit_fingerprint(pack)
    gates_path = ctx.root / GATES_REL
    status, gate_state = "draft", "gates.json missing"
    if gates_path.is_file():
        gates = json.loads(gates_path.read_text(encoding="utf-8"))
        if not gates.get("all_pass"):
            gate_state = "gates.json present but not all_pass"
        elif gates.get("kit_fingerprint", {}).get("sha256") != fingerprint["sha256"]:
            gate_state = "gates.json fingerprint stale (kit outputs changed since gates ran)"
        else:
            status, gate_state = "ready-for-review", "gates all_pass, fingerprint matches"
    risks = [o["text"] for o in plan.get("open_items", [])]
    voice = evidence["voice"]
    totals = plan["skill_dsl"]["multipliers"]["totals"]
    report_notes = [
        f"gate: {gate_state}",
        (f"改版 2026-09-16（plan.json {PLAN_CACHE['sha256'][:12]} + REV3_*/REV4_*/REV5_*）："
         f"队长 {derivation['record_counts']['leader']} 行整体替换（134 按「引擎启动」层数，第三轮 D1 提到 100%/200%；"
         "D3/D4 新增 194/134 两组技能槽行；D2 把 461 那条移到能力3；第四轮 T1 补瞬发攻击力行并封 500%），"
         f"词条 {derivation['record_counts']['abilities']} 条（能力1#1 → 开关槽1 536、能力3#1 → 开关槽2 704、"
         "能力3 新增 461/245 两条并把 461 前置改成「自身持有引擎启动」（T2）、"
         "**能力2 两条瞬发行整键换成按引擎启动层数成长且无上限的 during-134 行（T3）**，能力 4/5/6 未动），新增固有状态 "
         f"{UID_ENGINE}「引擎启动」(上限 99)/{UID_CANNON}「重炮展开」({UNIQUE_META[UID_CANNON]['duration']} 帧) 与两张 48×48 图标"),
        (f"技能倍率口径（审查 R-m6 后无条件成立）：档2 满级 + 单体吃满 = {totals['lv2_full_with_missile']}×，"
         f"每层「引擎启动」+{totals['per_stack_lv2']}×；档1 = {totals['lv1_with_missile']}×。"
         "R-M4 之后技能自身刻 1 层引擎启动 ⇒ 首次发动实际 80×"),
        ("技能树改版：炮台改挂球(-18 + GH(0))跟随移动；开头 RemoveEventFromOwner/HideEffectFromOwner ⇒ "
         "再次发动替换不叠加（技能说明已改成与行为一致的措辞）；雷达 半径400/30° → 半径500/90°"
         "（共鸣+能力3：潜能1 550/105°、潜能6 600/135°）；终幕 f300→f332 且不再挂开关槽2；收炮 f330→f362；"
         f"{len(EXT_FRAMES)} 个由「重炮展开」开门的延长槽 {list(EXT_FRAMES)}（寿命 {EXT_LIFETIME}，相邻重叠 10 帧）"),
        ("voice: 22 槽 AI 合成语音已装包（run=take1，owner=voice，speech 8 行引用 home_0..5/join/evolution，"
         "母本旧 home 语音已移除）；route c9-16=ChangeSkillFlag" if voice["status"] == "packed" else
         "voice route c9-16=ChangeSkillFlag 已写；22 条语音待 Integrate 装包（impl/tekuto/voice_merge.py）"
         f"（现状: missing={len(voice['missing_slots'])} extra={voice['extra_files']} "
         f"not_owned_by_voice={len(voice['not_owned_by_voice'])}）"),
        ("pixel: 染色 sprite_sheet/special_sprite_sheet 已装包（owner=pixel，存储态=out 原字节换小写魔数；"
         "alpha/透明像素/尺寸与母本一致，atlas/frame/timeline 未改）" if pixel["status"] == "integrated" else
         f"pixel sheet 仍为母本原色（pending: {pixel['gate']['reasons']}）"),
        ("effects recolor applied from fx manifest（包内 5 张 sheet == 染色 PNG 的框架存储态）" if recolor_stats
         else "effects cloned with official colors (fx/tekuto/out/manifest.json 不存在)"),
        (f"custom_ability_power_up_string：槽1 {CHANGE_SKILL_KEY} 潜能 2–6 用官方 "
         f"{POWER_UP_SOURCES[CHANGE_SKILL_KEY]}「{POWER_UP_TEXTS[CHANGE_SKILL_KEY]}」（槽1 的潜能插值就落在雷抗/"
         f"技伤抗性降低上）；槽2 {CHANGE_SKILL2_KEY} 自建「{POWER_UP_CUSTOM[CHANGE_SKILL2_KEY]}」"
         "（审查 R-M1：槽2 的 alv2 只落在雷达半径/角度上，原来的官方「伤害强化」与数据对不上）"),
        (f"技能说明按作者要求精简到 {len(_DESC)} 字，并与实际行为对齐（action_skill c1 是真源，"
         "character_text c5/c7 与三层镜像同步）：" + _DESC),
        *notes,
        *[f"open_item {o['id']}（{o['req']}）：{o['text']}" for o in plan.get("open_items", [])],
    ]
    ctx.report({
        "summary": (f"tekuto kit（改版至第五轮 T3，2026-09-17）: 队长{derivation['record_counts']['leader']}行/"
                    f"词条{derivation['record_counts']['abilities']}条/"
                    "固有状态2键+2图标/两档技能DSL(跟随球的重炮+延长槽)/5特效族克隆(染色)/预览600/语音路由"
                    f"；pixel={pixel['status']}；voice={voice['status']}"),
        "status": status,
        "skills": {"programs": programs},
        "unique_condition": {uid: {"icon": icons[uid]["logical"], "icon_sha256": icons[uid]["sha256"],
                                   "name": UNIQUE_META[uid]["name"], "max_accumulation": int(row[4]),
                                   "duration_frame": int(row[3]), "row": row}
                             for uid, row in unique_rows.items()},
        "required_capabilities": [],
        "panel": panel,
        "notes": report_notes,
        "kit_fingerprint": fingerprint,
    })
    return {"status": status, "gate_state": gate_state, "programs": programs, "fingerprint": fingerprint["sha256"],
            "unclaimed": unclaimed, "recolored": sorted(recolor_stats), "pixel": pixel["status"],
            "voice": voice["status"], "unique_condition": sorted(unique_rows),
            "record_counts": derivation["record_counts"], "notes": notes}


# ======================================================================== 框架缺口规避：发布后的 inspect
#
# 角色已上线（1.4.872，active 账本里已有本包的 ownership hash）后，``flow preflight`` 必须拿到
# installed manifest，否则直接报 ``active ownership hash exists but installed manifest was not supplied``
# （rc=2）。``wf_seasonal7_build.step_inspect`` 不传 ``--installed-package-dir``，所以框架的
# ``--step inspect`` 在改版重建包时必然失败。这里在 kit 内补上该参数（不改框架公共文件），
# 其余（复制到临时副本、只在副本里封存、回写 evidence/flow-inspect.json）与框架一致。
# 同批 philia / zantetsu / primula 三个 kit 已用同一写法（本 kit 逐字沿用）。

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
    spec = S.get_spec(KEY)
    pack = C.S7Pack(spec)
    pack.check_identity()
    root = pack.root
    candidates = ([Path(installed_dir)] if installed_dir
                  else installed_package_candidates(root, spec.pkg_id))
    guarded = [pack.package / "manifest.json", pack.evidence / "status.json", pack.evidence / "hash-cache.json"]
    before = {str(f): (f.read_bytes() if f.is_file() else None) for f in guarded}
    base = pack.batch_dir / B.INSPECT_DIR
    attempts: list[dict[str, Any]] = []
    rc, payload, used, workspace_copy = None, None, None, None
    for candidate in candidates or [None]:
        copy_root = base / f"{KEY}-{os.getpid()}"
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
    if workspace_copy is not None:
        for old in (workspace_copy, workspace_copy.resolve()):
            text = text.replace(json.dumps(str(old))[1:-1], json.dumps(str(pack.workspace))[1:-1])
    payload = json.loads(text)
    ready, reason = B.kit_readiness(pack)
    result = B._preflight_summary(rc, payload, pack, pack.workspace)
    result.update({"sealed_real_workspace": False, "sealed_copy_only": True, "kit_ready": ready,
                   "kit_reason": reason, "structurally_ready": rc == 0,
                   "flow_next_command": result.get("next_command"),
                   "installed_package_dir": None if used is None else str(used),
                   "installed_package_attempts": attempts,
                   "framework_gap": "wf_seasonal7_build.step_inspect 不传 --installed-package-dir，"
                                    "角色上线后（active ledger 已有 ownership hash）必然 rc=2；"
                                    "本 kit 的 inspect 子命令补上该参数，其余与框架一致",
                   "foreign_shadow_conflicts": foreign_shadow_conflicts(pack, result),
                   # 审查 R3-m6：让 gates 能判断这份 inspect 是不是针对当前包内容跑的。
                   # 不能用 input_digest 比 —— flow preflight 的 digest 在 workspace 副本上算，
                   # 与 wf_seasonal7_build --step status 的 digest 是两套算法，两个数从来不相等；
                   # 也不能用 mtime —— write_evidence 内容未变时不重写文件，mtime 会停在上一次。
                   "kit_fingerprint": kit_fingerprint(pack)["sha256"]})
    pack.write_evidence("flow-inspect.json", {"summary": result, "payload": payload})
    if rc == 2:                                   # rc=3 = 预检未达发布条件（本批串行发布的 live 漂移），由主控 rebase 处理
        raise KitError(f"flow preflight (inspect copy) rc={rc}: {payload.get('errors')}")
    return result


def owned_claim_keys(pack) -> dict[str, set[str]]:
    """{logical_path: 本包认领的 outer key 集合}（认领表按 logical_path 归并，忽略 root）。"""
    out: dict[str, set[str]] = {}
    for claim in pack.load_claims():
        keys = out.setdefault(claim["logical_path"], set())
        keys.update(claim.get("outer_keys") or [])
        for inner in claim.get("inner_keys") or []:
            if inner.get("outer_key"):
                keys.add(inner["outer_key"])
    return out


def foreign_shadow_conflicts(pack, summary: dict) -> dict[str, Any]:
    """把 preflight conflicts 分成「别家键的共享表影子漂移」与「碰到自家键」两堆。

    本批 7 个角色串行发布：tekuto 的包在 1.4.869 建好，之后 zantetsu/zehr/philia/primula/yuki 又发了 870-875，
    于是 tekuto 包里的共享表全表载荷在**别家键**上落后于 live，preflight 报 ``unclaimed_change``。
    这是主控 publish 前 ``flow rebase`` 负责的事（wf-flow-serial-publish-order / wf-package-shadow-table-refresh），
    不是本角色的缺陷；但只要有一条 conflict 碰到自家键，就必须变红。
    """
    conflicts = ((summary.get("preflight") or {}).get("conflicts") or [])
    claimed = owned_claim_keys(pack)
    own, foreign = [], []
    for item in conflicts:
        path, _, key = str(item.get("claim", "")).partition(":")
        outer = key.split("/", 1)[0]
        mine = (pack.spec.cid_s in key or CODE in key
                or outer in claimed.get(path, set()) or key in claimed.get(path, set()))
        (own if mine else foreign).append(item)
    return {"total": len(conflicts), "foreign": len(foreign), "own": own,
            "all_unclaimed_change": all(c.get("kind") == "unclaimed_change" for c in conflicts),
            "foreign_keys": sorted({str(c.get("claim", "")).partition(":")[2] for c in foreign})}


def main(argv: list[str] | None = None) -> int:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] != ["inspect"] or len(args) > 2:
        print("usage: python mod-tools/wf_seasonal7_kit_tekuto.py inspect [<installed package dir>]")
        return 2
    result = run_inspect(args[1] if len(args) == 2 else None)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

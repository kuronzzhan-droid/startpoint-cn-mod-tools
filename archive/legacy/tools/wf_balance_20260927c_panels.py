# -*- coding: utf-8 -*-
"""2026-09-27 平衡调整第三轮（c）：非第三轮角色的 28 块覆盖面板（24 名角色，多角色模块）+ 索恩技能文字「迟缓」→「冻结」
+ 技能强化文案 R1–R4（八条 change_skill 强化串官方格式、面板开关行与强化串同文、冰雪罗尔夫技能说明删强化段）。

作者原话（主会话逐字转述，均为作者本会话直接发出）：
  -「同一个条件的提升能不能写到一起来简化描述」（附图：玛格诺斯队长面板三行「火属性共鸣时，每发动3次强化弹射，…」）
  -「引擎点火的获取带火属性共鸣,引擎点火提供的效果就不用写火属性共鸣,其他角色类似」
  - 159994 能力4 二选一，作者选「合成一句并改冻结」：「光属性角色对处于麻痹、气绝、冻结状态的敌人造成的伤害，额外乘区＋15%」，
    能力1 的「迟缓」也改成「冻结」。

主会话追加（暂存前最后一轮）：
  C.「迟缓」统一按数据改「冻结」：索恩技能强化条目 ``change_skill_tweyen_light``、技能说明（``action_skill`` 两档 c1、
     ``character_text`` c5/c7、服务端 ``assets/cdndata/character_text.json`` 镜像 [5]/[7]）；先核实数据确是冻结
     （:func:`skill_text_problems`：两档技能 DSL 命中块挂的恰是 ACParalysis / ACFrozen / ACToleranceOfElement、尾巴
     FindAllSubjects 挂 ACSkillDamage；ACFrozen 的客户端名是「冻结」＝ ``wf_dsl_sig.AC_CN``）。
  F. 本轮新返回的面板键加进返回与 BEFORE；索恩能力2 冒号一并统一（口径3）。

技能强化文案（作者原话逐字：「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,
规范并简化描述做了吗」；主会话口径 R1–R4），本模块负责 129987 / 119991 / 159994 / 119989 四人：
  R1 技能强化 = 536 / 704–708 开关行打开、在技能 DSL 的 ConditionalsChangeSkillFlag 分支（或经 alv）生效的效果；
     不是开关行的面板行不写「强化技能」（索恩能力3 第3行去掉该标签）。
  R2 强化条目（开关行 c70 的 ``change_skill_*`` 串）用官方格式「强化『<技能名>』的「<效果>」」/「强化『<技能名>』：<定性>」，
     点明技能名、不写数字与秒数、不写开关条件；覆盖面板里开关那一行 == 主位图标 + 开关行共鸣前置的「X属性共鸣时，」+
     同一串（句末「。」随该面板惯例）——:data:`FLAG_TEXT`、:func:`flag_problems`。冈达葛萨的串删去「并强化「独立乘区
     伤害提升效果」」（旗号开支只把 ACAttackPoint / ACPowerFlipDamage 1.5→2.5；独立乘区＋91.7% 是能力6 #1 的 421 数值行，
     面板第2行另写）。
  R3 四人的技能说明（action_skill 两档 c1、character_text c5/c7、服务端镜像）只写技能本体，现状已合规，不改。
  R4 只改文字；战斗行与 DSL 一格不动。
  另 4 人（本轮调整过、此前没有 panels unit，新增 unit；强化槽都是客户端自动面板，``panel=None``）：
    129992 杰拉尔「为『誓约之枪·连突』追加「…」」（去「20秒」）、139992 夏琳「强化『桂影·望月三千』：…」（去串里的
    「雷属性共鸣时」、「迟缓」→「冻结」＝数据 ACFrozen）、159995 丝缇涅尔「强化『月相仪·满月调律』的威力与「技能伤害
    提升效果」」（『』/「」格式）、179999 冰雪罗尔夫「强化『炉心颂歌』：Fever状态中发动时增加Fever槽并触发超级Fever，…」；
    R3：冰雪罗尔夫技能说明五处删掉旗号开支那一段「／火属性共鸣时，自身在主位且于Fever状态中使用：Fever槽增加200，…」
    （:data:`DESC_TRIM`、:func:`desc_trim_problems`）——删掉的「Fever槽增加200」（AddFeverPoint 只在旗号开支）按 R2
    定性写进强化串「增加Fever槽」（总核对 major 的修正，不写 200）。
    ``flag_problems`` 的 branch 依据为此加了四个可选登记：``nodes``（旗号节点数，杰拉尔 5 处）、``carriers``（两支只差
    alv 增量时，带 alv 的构造 == 登记，丝缇涅尔）、``within``（旗号节点外层的 Conditionals*，冰雪罗尔夫 = Fever 分支）、
    ``commands``（开支独有的非状态效果命令 == 登记且各有措辞，冰雪罗尔夫 AddFeverPoint「增加Fever槽」/ CreateRatioHeal
    「回复生命值」）。

合并规则（主会话定稿，扫描与复核见 scratchpad panel_merge/scan.json、panel_merge_results.json）：
  1. 只合并同一面板里**数据条件完全相同**的行：除效果列（种类 / 对象 / 对象组 / 强度两端 / 特攻 uid，
     能力表另加分类列 c2）外逐格相同——触发方式、前置、触发、CT、次数上限、主位 c1、觉醒列、效果后缀全部一致；
     「战斗开始时」一次性效果与常驻效果文案条件不同，不并。
  2. 写法「<条件>，<对象A><效果1>＋x%、<效果2>＋y%，<对象B><效果3>＋z%」：每个效果原措辞与数值保留，只省略
     重复的对象名；后缀限定不同不合并；主位图标前缀 " <icon id='main'>  " 保留，有图标与无图标不合并；
     合并行放在组首行位置，其余行逐字不动、行序不变。
  3. 共鸣省略：某固有状态**全部**获取来源（词条 / 队长行 + 技能、629 的 DSL 授予节点）都带同一 X 共鸣时，
     该状态层数 / 持有提供的效果不写「X属性共鸣时，」；数据前置一格不动。
  4. 禁写「自身为队长时」「(觉醒后X%)」「生命值100%以下」；多条分行不用「／」；共鸣写「X属性共鸣时，」。

主会话统一口径（第三轮收尾，本模块照做）：
  口径1 强化弹射伤害（kind 55，战场级）不补对象：原文没写对象的不加「自身」，与前一个带对象的效果用「，」隔开；
  口径3 返回的覆盖面板里「X属性共鸣时：」一律写「X属性共鸣时，」，「X属性共鸣时：」后换行接效果的并成一行
        （:func:`normalize_resonance`，校验前先施加到原文，再逐字核对）；
  口径5 「／」分隔的按等级拆成分行（:func:`expand_split`：同位替换展开、每行一个数据条件）；
  口径7 面板校验器用仓库里的 ``wf_panel_merge_check.check``（本模块 ``merge_check`` 即它，不再另行移植）。

落点（改 custom_ability_string 的 28 个 ``desc_override_*`` 键，全部 live 只有 1 行 1 列；另外八个
``change_skill_*`` 强化串（:data:`FLAG_TEXT`）、索恩 / 冰雪罗尔夫 character_text / action_skill / 服务端镜像的技能说明
（见 :data:`SKILL_TEXT` / :data:`DESC_TRIM`）；战斗行与 DSL 一格不动）：

======  ============  ======  ================================  =============================================
角色    名字          面板    处理的数据行（0 基）               说明
======  ============  ======  ================================  =============================================
119989  碧安卡        能力1   —（#1 = 536 开关，火共鸣）         R2：L2 强化条目改官方格式、去「20%」「15秒」
119989  碧安卡        能力3   #2 / #5（持续·Fever，154 / 412）  L3+L4 并行，省略「火属性共鸣时，」（焰域研修）
119991  妮可拉        能力3   #6 / #7 / #8（503 / 550 / 694）    L3+L4 并行；L2 省略共鸣（月讲）；L1 冒号→逗号（口径3）
119992  米娅          队长    #0 / #1 / #2（32 / 55 / 200）       L1–L3 并行（自身两项接「自身」后）
119993  红蝮蛇        队长    #0–#3                              四行并一行
119994  哈宁红Z       队长    #0–#3                              全队三项 + 自身一项
119995  炎枪见习兵    队长    #0–#2                              #3 技能发动触发不并
129987  冈达葛萨      队长    #0 / #1（32 / 55）                   L1+L2 并行，强化弹射伤害不补对象（口径1）
129987  冈达葛萨      能力4   #0 / #1 / #2（51 / 53 / 118）        去「的」
129987  冈达葛萨      能力6   —（#0 = 536 开关，无前置）          R2：L1 补上强化内容，与强化串同文
129993  冰冻虎鲸      队长    #0–#3                              四行并一行
129994  哈宁蓝Z       队长    #0–#3                              四行并一行
129995  彷徨铠甲·水   队长    #0–#3                              四行并一行
129996  蓝色海妖      队长    #0–#3                              四行并一行
129998  水灵幽魂      队长    #0–#3                              四行并一行
139996  机枪魔块·雷   队长    #0–#3（#4 = 722 机制行不并）        全队三项 + 自身一项
149991  疾风狂熊      队长    #0–#3                              四行并一行
149992  彷徨铠甲·风   队长    #0 / #2 / #3（#1 持续·浮游不并）    全队两项 + 自身一项
149993  哈宁绿        队长    #0–#3（#4 = 722）                   四行并一行
149994  风暴恶魔拉比  队长    #0–#3                              全队三项 + 自身一项
149994  风暴恶魔拉比  能力3   #0 / #1 / #2 / #3+#4               「／」按等级拆 3 行 + 贯穿行（口径5）；「、强化弹射伤害」→「，」（口径1）
159994  索恩          能力1   —（#0 开战 211 与 #2 常驻不并）      「迟缓」→「冻结」（作者）；L2 冒号→逗号（口径3）；
                                                                  L2 强化条目点明『星之猎手』（R2）
159994  索恩          能力2   —（#0 = 136→258，光共鸣真实前置）    冒号→逗号（口径3，主会话 F）
159994  索恩          能力3   #1 / #2（34 / 35，同触发同限 10）   L2+L3 并行；L4/L5 冒号→逗号（口径3）；
                                                                  L4 去「强化技能，」（R1：能力3 无开关行）
159994  索恩          能力4   #0 / #1 / #2（118 / 53 / 119）       作者定稿一句，同值 ＋15% 只写一次；「迟缓」→「冻结」
159999  Sec-2600Li    队长    #0–#3（#4 = 722）                   四行并一行
169993  黑之下忍      队长    #0–#3                              四行并一行
169993  黑之下忍      能力1   #0 / #1 / #2 / #3                  「／」按等级拆 3 行 + 技能行（口径5）
======  ============  ======  ================================  =============================================

每块面板的合法性在 :func:`revise` 里运行时核对（任一不符即拒绝，fail closed）：
  - 输入基线 BEFORE（digest 逐项）；live 覆盖文案 == 改前文字；
  - 数据锁 :func:`check_rows`：每组数据行除效果列外逐格相同、效果种类 == 登记值；拆行面板各行数据条件两两不同、
    等级行的触发 == 该等级强化弹射、「获得N层」== 461 强度；共用数值的组强度逐行相同；
  - 文字锁 :func:`text_problems`：合并 / 改字面板 ``merge_check(check_orig(panel), after, drops)`` 无错（原文先施加
    已定改字 ``pre_edits`` 与口径3 规范化）；拆行面板 after == :func:`expand_split` 的机械展开；全面板不含「／」、
    禁写与「X属性共鸣时：」；
  - 共鸣省略的两块面板（119989 / 119991）现场普查固有状态全部来源（七个词条 / 队长键 + 技能与 629 的 DSL）；
  - 159994 能力1 与技能强化条目「麻痹效果、冻结效果持续时间大幅延长」：两档技能 DSL 的 ConditionalsChangeSkillFlag(1)
    开支恰挂 ACParalysis / ACFrozen 且时长都长于关支，536 开关行带光共鸣、c70 = 该串（:func:`skill_status_problems`）；
  - 159994 技能说明「＋赋予其麻痹效果＋冻结效果＋累积全属性抗性降低效果」：两档 DSL 命中块状态集合逐项对上，
    live 四处（text c5/c7、action 两档 c1、服务端 [5]/[7]）== 改前文字，改后 == 改前恰一处「迟缓」→「冻结」
    （:func:`skill_text_problems` / :func:`skill_text_outputs`）；全部返回文字不含「迟缓」；
  - R2 强化条目（:func:`flag_problems`）：开关行是 536（c70 == 串）且是该键唯一的 536 / 704–708 行；live 串 == 登记改前
    （索恩 == 主会话 C 的「冻结」稿）；技能名 == character_text c4；改后以「强化『<技能名>』」起头、过
    ``panel_problems(skill_flag=True)``、不含「强化技能」与开关条件词；覆盖面板对应行 == 图标 + 共鸣前缀 + 同一串
    （+「。」）；DSL 依据：旗号开支 / 关支的状态差异 == 登记（冈达葛萨 ACAttackPoint / ACPowerFlipDamage 加强且别无结构差异、
    碧安卡开支新增 ACAbilityDamageResistance、索恩 ACParalysis / ACFrozen 加长），妮可拉无旗号节点、带 alv 的构造 ==
    CreateNormalAttack（威力）/ ACSkillDamage；冰雪罗尔夫开支独有的非状态命令 == AddFeverPoint / CreateRatioHeal 且串里
    写了「增加Fever槽」「回复生命值」；返回的面板行凡含「强化『」必须是登记的强化条目，全部返回文字不含「强化技能」；
  - 口径3 的「X属性共鸣时，」行（改字面板）：该行数据确带 X 共鸣前置（:func:`check_rows`）；
  - ``wf_midautumn_kitlib.panel_problems``；主位图标与整键 c1 一致；
  - 生成器输出 == 本次输出：小 Boss 队长面板 ``wf_miniboss_package._leader_text`` 从战斗行现算、能力面板
    ``wf_miniboss_text.ability_panel_text``。

生成器 / 镜像（已同步，测试断言生成器输出 == :func:`revise` 输出）：
  - 119989：``wf_campus_panel_text._BIANCA["a1"] / ["a3"]`` 与 ``native_flat_string_rows``（强化串）；
  - 129987：``design/ghandagoza.json`` 的 change_skill_ghandagoza 与 desc_override_ghandagoza_6（kit 读，:func:`sync_mirrors`）；
  - 119991：``design/nicola.json`` 的 change_skill_sorceress_teacher_moon（kit 读）与 ``rework1/panel/nicola.json`` 能力1 第2行；
  - 159994：``wf_midautumn_kit_thorn.PANEL_ABILITY[1] / [2] / [3] / [4]`` 与 ``CHANGE_SKILL_TEXT``（``design/thorn.json``
    的 plan.texts.custom_ability_string 与 ``rework1/panel/thorn.json`` 为镜像）；技能说明的生成器是
    ``design/thorn.json`` 顶层 texts.desc1 / desc2（``wf_midautumn_specs`` 并进 spec.texts，tables 步写 character_text
    c5/c7 与 action_skill c1，kit 核对、服务端镜像随 character_text 同步），plan.texts.action_skill_desc.value 与
    rework1 skill.lines 为镜像；
  - 119991 / 119992 / 129987：kit 读 ``work/character_packs/midautumn-20260920/design/{nicola,mia,ghandagoza}.json``
    的 texts（nicola 另有 ``rework1/panel/nicola.json``）——由 :func:`sync_mirrors` 幂等同步；
  - 15 名小 Boss：队长 ``wf_miniboss_package._leader_text``（合并同条件行）；149994 能力3 / 169993 能力1
    ``wf_miniboss_text.TEXTS``（多行，主位槽逐行带图标）。
  - 139992：``wf_midautumn_kit_charlene.CAS_TEXTS``（``design/charlene.json`` 与 ``rework1/panel/charlene.json`` 能力1 第2行
    为镜像，:func:`sync_mirrors`）；159995：``wf_midautumn_kit_stinel.CAS_TEXTS``（``design/stinel.json`` 与
    ``rework1/panel/stinel.json`` 能力1 第2行为镜像）；129992：``wf_gerald_r2_data.ABILITY3``（``ability3()``）；
    179999：无生成器（第一批 ``wf_balance_20260927_rolfwt26`` 已注明技能树由一次性装配脚本落盘）。

候选（flow 包，active.json 引用；``stage_batch.Plan.splice`` 按 ``desc_override_<code>`` 前缀自动补认领）：
  - 119989 → ``campus-bianca-20260911``（照第二批 wf_balance_20260927b_bianca；8 个同 package_id 工作区的 manifest
    当前都与 active owner 哈希不符，唯一相符的是 audit-followup-20260917/backup 里的备份，见 notes）；
  - 119991 ``ma-nicola``、119992 ``ma-mia``、129987 ``gbf-ghandagoza-20260919``、159994 ``ma-thorn``；
  - 15 名小 Boss → 顶层 ``work/character_packs/<package_id>``（同第一 / 二批；genin 的包名是 ``genin``）。
  其中 13 名小 Boss 与 119995 / 169993 的候选原本没认领队长覆盖键，本次由暂存脚本补认领；119989 候选没认领 _3，同样补上。
  - 129992 ``unicorn_lancer_rose``、139992 ``ma-charlene``、159995 ``ma-stinel``、179999 ``black_wolf_knight_wt26``
    （change_skill 串、character_text、action_skill 与服务端镜像都已认领）。

纯函数：revise(read) 只经 read() 读取 live，返回有变化的键；不写 live store、候选工作区、assets 或 .cdn。
``python mod-tools/wf_balance_20260927c_panels.py [--write]`` 只同步上面三份设计镜像（work/，gitignored）。
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from functools import partial
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

import wf_client_legality as legality
from wf_midautumn_kitlib import panel_problems as kit_panel_problems
from wf_miniboss_roster import BY_ID as MINIBOSS
import wf_panel_merge_check as PMC
from wf_panel_merge_check import EL_CN as _EL_CN, FORBIDDEN, check as merge_check

SOURCE = "mod-tools/wf_balance_20260927c_panels.py"
MODULE_TAG = "balance_20260927c_panels"
CAS = "master/string/custom_ability_string.orderedmap"
MAIN_ICON = " <icon id='main'>  "
PANEL_CAPABILITY = legality.PANEL_OVERRIDE_V2          # panel-description-override-v2

__all__ = ["merge_check", "FORBIDDEN", "UNITS", "PANELS", "PANELS_BY_CAS", "BEFORE", "normalize_resonance",
           "expand_split", "check_orig", "check_rows", "text_problems", "SKILL_TEXT", "skill_text_problems",
           "skill_text_outputs", "FLAG_TEXT", "flag_problems", "cas_changes", "DESC_TRIM", "desc_trim_problems",
           "desc_trim_outputs", "auto_panel_problems"]


class PanelMergeError(ValueError):
    pass


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


# ====================================================================== 口径3 / 口径5 文字变换

_RES = r"([火水雷风光暗](?:或[火水雷风光暗])*属性共鸣时)"
_RES_BREAK_RE = re.compile(_RES + r"[：:]\n(?:\s*<icon id='main'>\s*)?")
_RES_COLON_RE = re.compile(_RES + r"[：:]")
_RES_HEAD_RE = re.compile(r"([火水雷风光暗])属性共鸣时，")


def normalize_resonance(text: str) -> str:
    """口径3：「X属性共鸣时：」→「X属性共鸣时，」；「X属性共鸣时：」后换行接效果的并成一行（后一行的主位图标随之去掉）。"""
    return _RES_COLON_RE.sub(r"\1，", _RES_BREAK_RE.sub(r"\1，", text))


#: 「／」同位替换的一串候选：ASCII 字母数字（Lv1／Lv2／Lv3、1／2／3）；中文候选不支持（展开后仍有「／」即拒绝）。
_ALT_RE = re.compile(r"[A-Za-z0-9.]+(?:／[A-Za-z0-9.]+)+")


def expand_split(line: str, rewrites=()) -> list[str]:
    """口径5：一行按「；」分句，含「／」的分句按位次同位展开成 n 行（各串候选数须相同），其余分句各成一行；
    每行沿用原行的主位图标与句末「。」。``rewrites`` = ((old, new), ...)，只施加在展开出的行上、每行恰一次，
    ``new`` 里的 ``{n}`` 是位次（1 起）。"""
    icon = MAIN_ICON if line.startswith(MAIN_ICON) else ""
    body = line[len(icon):]
    end = "。" if body.endswith("。") else ""
    body = body[:len(body) - len(end)]
    out = []
    for clause in body.split("；"):
        runs = list(_ALT_RE.finditer(clause))
        if not runs:
            out.append(clause)
            continue
        alts = [m.group(0).split("／") for m in runs]
        arity = {len(a) for a in alts}
        if len(arity) != 1:
            raise PanelMergeError(f"uneven 「／」 alternatives in {clause!r}")
        for k in range(arity.pop()):
            text = clause
            for m, a in reversed(list(zip(runs, alts))):
                text = text[:m.start()] + a[k] + text[m.end():]
            for old, new in rewrites:
                if text.count(old) != 1:
                    raise PanelMergeError(f"split rewrite {old!r} not found once in {text!r}")
                text = text.replace(old, new.format(n=k + 1))
            out.append(text)
    lines = [icon + text + end for text in out]
    if any("／" in text for text in lines):
        raise PanelMergeError(f"「／」 left after the split: {lines}")
    return lines


# ====================================================================== 表布局

#: kind → (触发方式列, 前置块基址, 瞬发内容基址, 持续内容基址, 行宽)。
LAYOUT = {
    "leader": dict(trig=3, pre=(4, 11, 18), ic=45, dc=107, ncols=124),
    "ability": dict(trig=5, pre=(6, 13, 20), ic=47, dc=109, ncols=126),
}
#: 效果身份列（其余列逐格相同 = 数据条件相同）：瞬发内容 +0 种类 / +1 对象 / +2 对象组 / +4,+5 强度 / +21 特攻 uid，
#: 持续内容 +0 / +1 / +2 / +4 / +5；能力表另加 c2 分类。与 ``wf_miniboss_package.LEADER_EFFECT_COLS`` 同口径。
EFFECT_COLS = {
    kind: frozenset({lay["ic"] + i for i in (0, 1, 2, 4, 5, 21)} | {lay["dc"] + i for i in (0, 1, 2, 4, 5)}
                    | ({2} if kind == "ability" else set()))
    for kind, lay in LAYOUT.items()
}
GRANT_KINDS = frozenset({"461", "413", "436", "459"})      # 瞬发内容授予固有状态（uid 在 +21）
UNIQUE_GRANT_KIND = "461"                                  # 强度 = 层数 × 100000
INVOKE_KIND = "629"                                        # 程序路径在 +24
PF_OVERRIDE_KIND = "722"
SKILL_SWITCH_KIND = "536"                                  # 技能形态开关（c70 = change_skill_* 串）


def _content_base(kind: str, row: list[str]) -> int:
    lay = LAYOUT[kind]
    return lay["dc"] if row[lay["trig"]] == "1" else lay["ic"]


def effect_kind(kind: str, row: list[str]) -> str:
    return row[_content_base(kind, row)]


def effect_strength(kind: str, row: list[str]) -> tuple[str, str]:
    base = _content_base(kind, row)
    return row[base + 4], row[base + 5]


def condition_cells(kind: str, row: list[str]) -> tuple:
    return tuple(value for col, value in enumerate(row) if col not in EFFECT_COLS[kind])


def resonance_tokens(kind: str, row: list[str]) -> list[str]:
    """前置块里的「X属性共鸣」（kind 2，编成 ≥600000，组 = 元素 token，无 puller 组）。"""
    out = []
    for b in LAYOUT[kind]["pre"]:
        if (row[b] == "2" and row[b + 3] == "600000" and row[b + 4] in ("600000", "")
                and row[b + 5] in _EL_CN and row[b + 2] in ("", "0", "(None)")):
            out.append(row[b + 5])
    return out


# ====================================================================== 面板登记


def _panel(cid, panel, key, cas, *, before, after, groups=(), kinds=(), drops=(), pre_edits=(), nrows,
           mode="merge", shared=(), rewrites=()):
    """mode：merge（同条件合并）/ edit（不合并，只施加已定改字与口径3）/ split（口径5 拆行，groups = 每个新行的数据行）。
    pre_edits = ((原文行号, old, new), ...)：主会话 / 作者已定的改字，校验前先施加到原文。
    shared = ((新文案行号, 数值记号), ...)：作者定稿的「同值只写一次」（该行各来源的这个数值合写一次，数据强度须逐行相同）。
    rewrites：拆行时施加在展开行上的措辞调整（见 :func:`expand_split`）。"""
    return dict(cid=cid, panel=panel, kind="leader" if panel == "leader" else "ability", key=key, cas=cas,
                before=tuple(before), after=tuple(after), groups=tuple(map(tuple, groups)),
                kinds=tuple(map(tuple, kinds)), drops=tuple(drops), pre_edits=tuple(pre_edits), nrows=nrows,
                mode=mode, shared=tuple(shared), rewrites=tuple(rewrites))


PANELS: tuple[dict, ...] = (
    # R2（技能强化文案）：第2行 = #1（536 开关，火共鸣前置，c70 = change_skill_lady_summoner_campus_dragon）⇒
    # 「火属性共鸣时，」+ 强化串同文（句末「。」沿用本面板）。第3行描述 #2 / #3（同触发、#3 另有 15 秒持续列），
    # 改字面板不合并，只登记首行。
    _panel(
        "119989", "ability1", "1199891", "desc_override_lady_summoner_campus_1", nrows=4, mode="edit",
        groups=[(0,), (1,), (2,)], kinds=[("211",), ("536",), ("211",)],
        pre_edits=[(2, "强化幼龙吐息，赋予全场敌人能力伤害抗性降低20%效果，持续15秒",
                    "强化『绯焰实习·幼龙点名』：幼龙吐息降低全场敌人的能力伤害抗性")],
        before=(
            " <icon id='main'>  战斗开始时：自身技能槽+50%。",
            " <icon id='main'>  火属性共鸣时，强化幼龙吐息，赋予全场敌人能力伤害抗性降低20%效果，持续15秒。",
            " <icon id='main'>  火属性共鸣时，每次获得「幼龙吐息」，自身技能槽+20%，赋予队长攻击力提升200%效果，持续15秒。",
        ),
        after=(
            " <icon id='main'>  战斗开始时：自身技能槽+50%。",
            " <icon id='main'>  火属性共鸣时，强化『绯焰实习·幼龙点名』：幼龙吐息降低全场敌人的能力伤害抗性。",
            " <icon id='main'>  火属性共鸣时，每次获得「幼龙吐息」，自身技能槽+20%，赋予队长攻击力提升200%效果，持续15秒。",
        ),
    ),
    _panel(
        "119989", "ability3", "1199893", "desc_override_lady_summoner_campus_3", nrows=6,
        groups=[(2, 5)], kinds=[("154", "412")], drops=[(3, "Red"), (4, "Red")],
        before=(
            " <icon id='main'>  火属性共鸣时，Fever模式中，火属性角色技能槽上限+20%。",
            " <icon id='main'>  火属性共鸣时，Fever模式中，每经过2秒，队长技能槽+5%，自身获得1层「焰域研修」。",
            " <icon id='main'>  火属性共鸣时，Fever模式中，每层「焰域研修」使火属性角色能力伤害+50%。",
            " <icon id='main'>  火属性共鸣时，Fever模式中，每层「焰域研修」使火属性角色能力伤害额外乘区+1%。",
            " <icon id='main'>  Fever结束或自身倒下时，「焰域研修」清空。",
        ),
        after=(
            " <icon id='main'>  火属性共鸣时，Fever模式中，火属性角色技能槽上限+20%。",
            " <icon id='main'>  火属性共鸣时，Fever模式中，每经过2秒，队长技能槽+5%，自身获得1层「焰域研修」。",
            " <icon id='main'>  Fever模式中，每层「焰域研修」使火属性角色能力伤害+50%、能力伤害额外乘区+1%。",
            " <icon id='main'>  Fever结束或自身倒下时，「焰域研修」清空。",
        ),
    ),
    _panel(
        "119991", "ability3", "1199913", "desc_override_sorceress_teacher_moon_3", nrows=9,
        groups=[(6, 7, 8)], kinds=[("503", "550", "694")], drops=[(2, "Red")],
        before=(
            " <icon id='main'>  火属性共鸣时：自身技能槽每达到100%，自身获得1层「月讲」状态",
            " <icon id='main'>  火属性共鸣时：除自身外的火属性角色发动技能时，消耗1层「月讲」，使该角色技能槽＋10%、"
            "攻击力＋50%，同时自身技能槽上限＋5%、技能充能速度＋5%（可叠加）",
            " <icon id='main'>  火属性共鸣时：火属性角色对处于抗性降低状态的敌人，攻击力＋300%、技能伤害＋300%",
            " <icon id='main'>  火属性共鸣时：火属性角色对敌人的技能额外伤害乘区＋15%",
        ),
        after=(
            " <icon id='main'>  火属性共鸣时，自身技能槽每达到100%，自身获得1层「月讲」状态",
            " <icon id='main'>  除自身外的火属性角色发动技能时，消耗1层「月讲」，使该角色技能槽＋10%、攻击力＋50%，"
            "同时自身技能槽上限＋5%、技能充能速度＋5%（可叠加）",
            " <icon id='main'>  火属性共鸣时，火属性角色对处于抗性降低状态的敌人，攻击力＋300%、技能伤害＋300%，"
            "对敌人的技能额外伤害乘区＋15%",
        ),
    ),
    _panel(
        "119992", "leader", "119992", "desc_override_tiger_treasure_hunter_moon", nrows=8,
        groups=[(0, 1, 2)], kinds=[("32", "55", "200")],
        before=(
            "火属性共鸣时，火属性角色攻击力＋250%",
            "火属性共鸣时，自身强化弹射伤害＋200%",
            "火属性共鸣时，强化弹射所需连击数－6",
            "火属性共鸣时，每次弹射追加6连击",
            "火属性共鸣时，每发动2次强化弹射，赋予自身「连击加成」：弹射时连击＋10（持续3次弹射）",
            "每发动1次强化弹射Lv3，火属性角色攻击力＋10%（最多10次）",
            "火属性共鸣时，持有「桂灯」的状态下每发动3次强化弹射，消耗3盏「桂灯」并放出追击『开匣·月华』，"
            "对周围的敌人造成火属性伤害（以强化弹射伤害计算）",
        ),
        after=(
            "火属性共鸣时，火属性角色攻击力＋250%，自身强化弹射伤害＋200%、强化弹射所需连击数－6",
            "火属性共鸣时，每次弹射追加6连击",
            "火属性共鸣时，每发动2次强化弹射，赋予自身「连击加成」：弹射时连击＋10（持续3次弹射）",
            "每发动1次强化弹射Lv3，火属性角色攻击力＋10%（最多10次）",
            "火属性共鸣时，持有「桂灯」的状态下每发动3次强化弹射，消耗3盏「桂灯」并放出追击『开匣·月华』，"
            "对周围的敌人造成火属性伤害（以强化弹射伤害计算）",
        ),
    ),
    _panel(
        "119993", "leader", "119993", "desc_override_cobra_playable", nrows=4,
        groups=[(0, 1, 2, 3)], kinds=[("32", "491", "34", "205")],
        before=(
            "赋予全队(火) 攻击力 80%。",
            "赋予全队(火) 减益攻击特攻 60%。",
            "赋予全队(火) 技能伤害 100%。",
            "赋予全队(火) HP 15%。",
        ),
        after=(
            "赋予全队(火) 攻击力 80%、减益攻击特攻 60%、技能伤害 100%、HP 15%。",
        ),
    ),
    _panel(
        "119994", "leader", "119994", "desc_override_haniwa_playable", nrows=4,
        groups=[(0, 1, 2, 3)], kinds=[("32", "33", "55", "205")],
        before=(
            "赋予全队(火) 攻击力 80%。",
            "赋予全队(火) 直接攻击伤害 140%。",
            "自身 强化弹射伤害 80%。",
            "赋予全队(火) HP 15%。",
        ),
        after=(
            "赋予全队(火) 攻击力 80%、直接攻击伤害 140%、HP 15%，自身 强化弹射伤害 80%。",
        ),
    ),
    _panel(
        "119995", "leader", "119995", "desc_override_dog_soldier_playable", nrows=4,
        groups=[(0, 1, 2)], kinds=[("32", "55", "205")],
        before=(
            "赋予全队(火) 攻击力 100%。",
            "自身 强化弹射伤害 120%。",
            "赋予全队(火) HP 20%。",
            "技能发动≥1 → 自身 追加连击 5。",
        ),
        after=(
            "赋予全队(火) 攻击力 100%、HP 20%，自身 强化弹射伤害 120%。",
            "技能发动≥1 → 自身 追加连击 5。",
        ),
    ),
    # 口径1：原文第2行「强化弹射伤害＋300%」没写对象（kind 55 战场级）⇒ 合并后不补「自身」，与前一项用「，」隔开。
    _panel(
        "129987", "leader", "129987", "desc_override_ghandagoza", nrows=4,
        groups=[(0, 1)], kinds=[("32", "55")],
        before=(
            "水属性角色攻击力＋300%",
            "强化弹射伤害＋300%",
            "水属性共鸣时，水属性角色获得治疗量＋10%；战斗开始时，水属性角色技能槽＋100%",
        ),
        after=(
            "水属性角色攻击力＋300%，强化弹射伤害＋300%",
            "水属性共鸣时，水属性角色获得治疗量＋10%；战斗开始时，水属性角色技能槽＋100%",
        ),
    ),
    _panel(
        "129987", "ability4", "1299874", "desc_override_ghandagoza_4", nrows=3,
        groups=[(0, 1, 2)], kinds=[("51", "53", "118")],
        pre_edits=[(1, "水属性角色的气绝蓄积", "水属性角色气绝蓄积")],
        before=(
            "水属性角色的气绝蓄积＋50%",
            "水属性角色对气绝中的敌人伤害＋10%、对麻痹中的敌人伤害＋10%",
        ),
        after=(
            "水属性角色气绝蓄积＋50%、对气绝中的敌人伤害＋10%、对麻痹中的敌人伤害＋10%",
        ),
    ),
    # R2（技能强化文案）：第1行 = #0（536 开关，无前置，c70 = change_skill_ghandagoza）⇒ 与强化串同文（原文只写
    # 「强化『炎天呑舟正拳突击』」，没说强化什么）。第2行 = #1（持续 421，「破海」期间独立乘区＋91.7%）是数值行，不动。
    _panel(
        "129987", "ability6", "1299876", "desc_override_ghandagoza_6", nrows=2, mode="edit",
        groups=[(0,), (1,)], kinds=[("536",), ("421",)],
        pre_edits=[(1, "强化『炎天呑舟正拳突击』", "强化『炎天呑舟正拳突击』的「攻击力提升＋强化弹射伤害提升效果」")],
        before=(
            " <icon id='main'>  强化『炎天呑舟正拳突击』",
            " <icon id='main'>  『炎天呑舟正拳突击』生效期间，水属性角色的独立乘区伤害进一步＋91.7%",
        ),
        after=(
            " <icon id='main'>  强化『炎天呑舟正拳突击』的「攻击力提升＋强化弹射伤害提升效果」",
            " <icon id='main'>  『炎天呑舟正拳突击』生效期间，水属性角色的独立乘区伤害进一步＋91.7%",
        ),
    ),
    _panel(
        "129993", "leader", "129993", "desc_override_killer_whale_playable", nrows=4,
        groups=[(0, 1, 2, 3)], kinds=[("32", "34", "119", "211")],
        before=(
            "赋予全队(水) 攻击力 80%。",
            "赋予全队(水) 技能伤害 100%。",
            "赋予全队(水) 冻结特攻 30%。",
            "赋予全队(水) 技能槽 30%。",
        ),
        after=(
            "赋予全队(水) 攻击力 80%、技能伤害 100%、冻结特攻 30%、技能槽 30%。",
        ),
    ),
    _panel(
        "129994", "leader", "129994", "desc_override_haniwa_blue_playable", nrows=4,
        groups=[(0, 1, 2, 3)], kinds=[("32", "33", "157", "211")],
        before=(
            "赋予全队(水) 攻击力 80%。",
            "赋予全队(水) 直接攻击伤害 100%。",
            "赋予全队(水) 攻击力↑延长 20%。",
            "赋予全队(水) 技能槽 30%。",
        ),
        after=(
            "赋予全队(水) 攻击力 80%、直接攻击伤害 100%、攻击力↑延长 20%、技能槽 30%。",
        ),
    ),
    _panel(
        "129995", "leader", "129995", "desc_override_wander_armor_water_playable", nrows=4,
        groups=[(0, 1, 2, 3)], kinds=[("32", "34", "37", "205")],
        before=(
            "赋予全队(水) 攻击力 80%。",
            "赋予全队(水) 技能伤害 80%。",
            "赋予全队(水) 抗性火 20%。",
            "赋予全队(水) HP 20%。",
        ),
        after=(
            "赋予全队(水) 攻击力 80%、技能伤害 80%、抗性火 20%、HP 20%。",
        ),
    ),
    _panel(
        "129996", "leader", "129996", "desc_override_clione_playable", nrows=4,
        groups=[(0, 1, 2, 3)], kinds=[("32", "33", "195", "205")],
        before=(
            "赋予全队(水) 攻击力 80%。",
            "赋予全队(水) 直接攻击伤害 120%。",
            "赋予全队(水) 获得的治疗量 15%。",
            "赋予全队(水) HP 20%。",
        ),
        after=(
            "赋予全队(水) 攻击力 80%、直接攻击伤害 120%、获得的治疗量 15%、HP 20%。",
        ),
    ),
    _panel(
        "129998", "leader", "129998", "desc_override_ghost_girl_playable", nrows=4,
        groups=[(0, 1, 2, 3)], kinds=[("32", "34", "211", "119")],
        before=(
            "赋予全队(水) 攻击力 100%。",
            "赋予全队(水) 技能伤害 120%。",
            "赋予全队(水) 技能槽 30%。",
            "赋予全队(水) 冻结特攻 30%。",
        ),
        after=(
            "赋予全队(水) 攻击力 100%、技能伤害 120%、技能槽 30%、冻结特攻 30%。",
        ),
    ),
    _panel(
        "139996", "leader", "139996", "desc_override_cube_boss_playable", nrows=5,
        groups=[(0, 1, 2, 3)], kinds=[("32", "55", "565", "211")],
        before=(
            "赋予全队(雷) 攻击力 100%。",
            "自身 强化弹射伤害 120%。",
            "赋予全队(雷) 固有技能特攻 60%。",
            "赋予全队(雷) 技能槽 30%。",
            "强化弹射替换为角色专属形态。",
        ),
        after=(
            "赋予全队(雷) 攻击力 100%、固有技能特攻 60%、技能槽 30%，自身 强化弹射伤害 120%。",
            "强化弹射替换为角色专属形态。",
        ),
    ),
    _panel(
        "149991", "leader", "149991", "desc_override_big_bear_monster_playable", nrows=4,
        groups=[(0, 1, 2, 3)], kinds=[("32", "33", "157", "205")],
        before=(
            "赋予全队(风) 攻击力 100%。",
            "赋予全队(风) 直接攻击伤害 100%。",
            "赋予全队(风) 攻击力↑延长 20%。",
            "赋予全队(风) HP 15%。",
        ),
        after=(
            "赋予全队(风) 攻击力 100%、直接攻击伤害 100%、攻击力↑延长 20%、HP 15%。",
        ),
    ),
    _panel(
        "149992", "leader", "149992", "desc_override_wander_armor_wind_playable", nrows=4,
        groups=[(0, 2, 3)], kinds=[("32", "191", "211")],
        before=(
            "赋予全队(风) 攻击力 80%。",
            "持续·状态浮游 → 赋予全队(风) 直接攻击伤害 140%。",
            "自身 浮游延长 20%。",
            "赋予全队(风) 技能槽 30%。",
        ),
        after=(
            "赋予全队(风) 攻击力 80%、技能槽 30%，自身 浮游延长 20%。",
            "持续·状态浮游 → 赋予全队(风) 直接攻击伤害 140%。",
        ),
    ),
    _panel(
        "149993", "leader", "149993", "desc_override_haniwa_green_playable", nrows=5,
        groups=[(0, 1, 2, 3)], kinds=[("32", "34", "205", "36")],
        before=(
            "赋予全队(风) 攻击力 80%。",
            "赋予全队(风) 技能伤害 100%。",
            "赋予全队(风) HP 25%。",
            "赋予全队(风) 抗性全属性 10%。",
            "强化弹射替换为角色专属形态。",
        ),
        after=(
            "赋予全队(风) 攻击力 80%、技能伤害 100%、HP 25%、抗性全属性 10%。",
            "强化弹射替换为角色专属形态。",
        ),
    ),
    _panel(
        "149994", "leader", "149994", "desc_override_one_eyed_rabbit_playable", nrows=4,
        groups=[(0, 1, 2, 3)], kinds=[("32", "33", "190", "211")],
        before=(
            "赋予全队(风) 攻击力 100%。",
            "赋予全队(风) 直接攻击伤害 140%。",
            "自身 贯穿延长 20%。",
            "赋予全队(风) 技能槽 30%。",
        ),
        after=(
            "赋予全队(风) 攻击力 100%、直接攻击伤害 140%、技能槽 30%，自身 贯穿延长 20%。",
        ),
    ),
    # 口径5：Lv1／Lv2／Lv3 三条 629 追击（触发 63 / 64 / 65）按等级拆行；贯穿中的两条持续行（410 全队风独立乘区直击、
    # 23 强化弹射伤害）同条件，仍写一行。口径1：「强化弹射伤害」原文没写对象，与前一项「风属性角色…」改用「，」隔开。
    _panel(
        "149994", "ability3", "1499943", "desc_override_one_eyed_rabbit_playable_3", nrows=5, mode="split",
        groups=[(0,), (1,), (2,), (3, 4)], kinds=[("629",), ("629",), ("629",), ("410", "23")],
        pre_edits=[(1, "（独立乘区）、强化弹射伤害", "（独立乘区），强化弹射伤害")],
        rewrites=[("对应等级的", "Lv{n}")],
        before=(
            " <icon id='main'>  Lv1／Lv2／Lv3强化弹射时，追加对应等级的爪刃追击；贯穿效果中，"
            "风属性角色直接攻击造成的伤害+15%（独立乘区）、强化弹射伤害+100%。",
        ),
        after=(
            " <icon id='main'>  Lv1强化弹射时，追加Lv1爪刃追击。",
            " <icon id='main'>  Lv2强化弹射时，追加Lv2爪刃追击。",
            " <icon id='main'>  Lv3强化弹射时，追加Lv3爪刃追击。",
            " <icon id='main'>  贯穿效果中，风属性角色直接攻击造成的伤害+15%（独立乘区），强化弹射伤害+100%。",
        ),
    ),
    # 作者：能力1「迟缓」改「冻结」（DSL 是 ACFrozen，见 SKILL_STATUS）。#0（211 开战）与 #2（538 常驻）数据同条件，
    # 但「战斗开始时」一次性效果与常驻效果文案条件不同，按定稿不并；#1 是 536 技能开关，光共鸣是真实条件（口径2）保留。
    # R2（技能强化文案）：第2行「强化技能，自身技能赋予的…」点明技能名，与强化串 change_skill_tweyen_light 同文。
    _panel(
        "159994", "ability1", "1599941", "desc_override_tweyen_light_1", nrows=3, mode="edit",
        groups=[(0,), (1,), (2,)], kinds=[("211",), ("536",), ("538",)],
        pre_edits=[(2, "迟缓效果", "冻结效果"), (2, "强化技能，自身技能赋予的", "强化『星之猎手』：赋予的")],
        before=(
            "战斗开始时：自身技能槽立即＋50%",
            "光属性共鸣时：强化技能，自身技能赋予的麻痹效果、迟缓效果持续时间大幅延长",
            "光属性角色减益技能特攻＋40%",
        ),
        after=(
            "战斗开始时：自身技能槽立即＋50%",
            "光属性共鸣时，强化『星之猎手』：赋予的麻痹效果、冻结效果持续时间大幅延长",
            "光属性角色减益技能特攻＋40%",
        ),
    ),
    # 主会话 F：本轮一并统一冒号（口径3）。#0（持续 136 敌方弱体数 → 258 全队(光)触发敌方攻击特攻）的光共鸣是真实数据前置、
    # 不是固有状态派生，保留（check_rows 核对该行确带光共鸣）。
    _panel(
        "159994", "ability2", "1599942", "desc_override_tweyen_light_2", nrows=1, mode="edit",
        groups=[(0,)], kinds=[("258",)],
        before=(
            "光属性共鸣时：敌人身上每有1个弱体效果，光属性角色对该敌人的攻击力＋100%",
        ),
        after=(
            "光属性共鸣时，敌人身上每有1个弱体效果，光属性角色对该敌人的攻击力＋100%",
        ),
    ),
    # R1（技能强化文案）：能力3（#0–#6）没有 536 / 704–708 开关行，第4行描述的是普通能力行（#3 持续 136→技能伤害、
    # #6 技能发动→连击），「强化技能，」是误导标签 ⇒ 去掉，数值与其余文字不动。
    _panel(
        "159994", "ability3", "1599943", "desc_override_tweyen_light_3", nrows=7,
        groups=[(1, 2)], kinds=[("34", "35")],
        pre_edits=[(4, "强化技能，", "")],
        before=(
            " <icon id='main'>  自身发动技能时：光属性角色状态技能伤害＋200%（持续10秒，可叠加）",
            " <icon id='main'>  自身发动技能时：自身技能伤害＋20%（最多叠加10次）",
            " <icon id='main'>  自身发动技能时：光属性角色技能充能速度＋1.5%（最多叠加10次）",
            " <icon id='main'>  光属性共鸣时：强化技能，敌方每有1个弱体效果，自身技能伤害＋40%，且连击＋50",
            " <icon id='main'>  光属性共鸣时：光属性角色发动技能时，光属性角色技能伤害＋50%（最多＋350%）、"
            "攻击力＋50%（最多＋350%）",
        ),
        after=(
            " <icon id='main'>  自身发动技能时：光属性角色状态技能伤害＋200%（持续10秒，可叠加）",
            " <icon id='main'>  自身发动技能时：自身技能伤害＋20%，光属性角色技能充能速度＋1.5%（最多叠加10次）",
            " <icon id='main'>  光属性共鸣时，敌方每有1个弱体效果，自身技能伤害＋40%，且连击＋50",
            " <icon id='main'>  光属性共鸣时，光属性角色发动技能时，光属性角色技能伤害＋50%（最多＋350%）、"
            "攻击力＋50%（最多＋350%）",
        ),
    ),
    # 作者二选一定稿「合成一句并改冻结」：三条独立乘区特攻（118 麻痹 / 53 眩晕畏缩 = 气绝 / 119 冻结）数据同条件、
    # 强度同为 15%，合写一次「＋15%」。
    _panel(
        "159994", "ability4", "1599944", "desc_override_tweyen_light_4", nrows=3,
        groups=[(0, 1, 2)], kinds=[("118", "53", "119")], shared=[(1, "15%")],
        pre_edits=[(2, "迟缓状态", "冻结状态")],
        before=(
            "光属性角色对处于麻痹、气绝状态的敌人造成的伤害，额外乘区＋15%",
            "光属性角色对处于迟缓状态的敌人造成的伤害，额外乘区＋15%",
        ),
        after=(
            "光属性角色对处于麻痹、气绝、冻结状态的敌人造成的伤害，额外乘区＋15%",
        ),
    ),
    _panel(
        "159999", "leader", "159999", "desc_override_security_robot_playable", nrows=5,
        groups=[(0, 1, 2, 3)], kinds=[("32", "34", "53", "205")],
        before=(
            "赋予全队(光) 攻击力 100%。",
            "赋予全队(光) 技能伤害 120%。",
            "赋予全队(光) 眩晕畏缩特攻 30%。",
            "赋予全队(光) HP 20%。",
            "强化弹射替换为角色专属形态。",
        ),
        after=(
            "赋予全队(光) 攻击力 100%、技能伤害 120%、眩晕畏缩特攻 30%、HP 20%。",
            "强化弹射替换为角色专属形态。",
        ),
    ),
    _panel(
        "169993", "leader", "169993", "desc_override_genin_playable", nrows=4,
        groups=[(0, 1, 2, 3)], kinds=[("32", "34", "117", "211")],
        before=(
            "赋予全队(暗) 攻击力 100%。",
            "赋予全队(暗) 技能伤害 120%。",
            "赋予全队(暗) 中毒特攻 30%。",
            "赋予全队(暗) 技能槽 30%。",
        ),
        after=(
            "赋予全队(暗) 攻击力 100%、技能伤害 120%、中毒特攻 30%、技能槽 30%。",
        ),
    ),
    # 口径5：Lv1／Lv2／Lv3 三条 461（触发 63 / 64 / 65，强度 1 / 2 / 3 层）按等级拆行，「分别」随之去掉；技能行不动。
    _panel(
        "169993", "ability1", "1699931", "desc_override_genin_playable_1", nrows=4, mode="split",
        groups=[(0,), (1,), (2,), (3,)], kinds=[("461",), ("461",), ("461",), ("461",)],
        rewrites=[("分别获得", "获得")],
        before=(
            "Lv1／Lv2／Lv3强化弹射时，分别获得1／2／3层影；自身发动技能时，获得2层影（最大5层）。",
        ),
        after=(
            "Lv1强化弹射时，获得1层影。",
            "Lv2强化弹射时，获得2层影。",
            "Lv3强化弹射时，获得3层影。",
            "自身发动技能时，获得2层影（最大5层）。",
        ),
    ),
)
PANELS_BY_CAS = {p["cas"]: p for p in PANELS}

#: 共鸣省略的固有状态普查：{角色: (uid, 名称, 元素 token, 技能程序, 629 程序)}。
#: 全部来源（本角色 7 个词条 / 队长键里 461 等授予行、调用会授予该 uid 的 629 程序的行，以及技能 DSL）都必须带该共鸣；
#: 换形 voice_ready 的两档程序与技能同路径（scan 已核）。
_R5 = "battle/action/skill/action/rare5/"
CENSUS = {
    "119989": dict(uid="11998903", name="焰域研修", element="Red",
                   skills=(f"{_R5}lady_summoner_campus$lady_summoner_campus_1",
                           f"{_R5}lady_summoner_campus$lady_summoner_campus_2"),
                   invokes=("battle/action/skill/action/ability_skill/lady_summoner_campus$lady_summoner_campus_fever_tick",)),
    "119991": dict(uid="11999101", name="月讲", element="Red",
                   skills=(f"{_R5}sorceress_teacher_moon$sorceress_teacher_moon_1",
                           f"{_R5}sorceress_teacher_moon$sorceress_teacher_moon_2"),
                   invokes=()),
}

#: 面板 / 强化串写「强化『星之猎手』：赋予的<状态>效果持续时间大幅延长」的依据：技能开关行（536，带共鸣）+ 两档技能 DSL 的
#: ``ConditionalsChangeSkillFlag(flag)`` 开支挂的异常状态恰为 ``statuses``，且每个都比关支长（开支最短 > 关支最长）。
SKILL_STATUS = {
    "159994": dict(cas="desc_override_tweyen_light_1", key="1599941", switch_row=1, element="White",
                   string="change_skill_tweyen_light", flag=1, statuses=("ACParalysis", "ACFrozen"),
                   skills=(f"{_R5}tweyen_light$tweyen_light_1", f"{_R5}tweyen_light$tweyen_light_2")),
}

#: 主会话 C：「迟缓」统一按数据改「冻结」（面板以外的技能文字）。每处 live == 改前、改后 == 改前恰一处 old → new。
#:   cas          技能强化条目（536 c70 串；依据 :data:`SKILL_STATUS` 的开关分支普查）；
#:   desc         技能说明：character_text c5 / c7、action_skill 各档 c1、服务端 cdndata/character_text.json [5] / [7]；
#:   hit_statuses 两档技能 DSL 命中块（CreateHitArea 第 23 参）内 CreateCondition 的状态集合 ⇔ 说明里 hit_phrase 的三项；
#:   ally_statuses 命中块以外（尾巴 FindAllSubjects 33 + [5] 光属性过滤）的状态集合 ⇔ ally_phrase。
SKILL_TEXT = {
    "159994": dict(
        old="迟缓", new="冻结",
        cas={"change_skill_tweyen_light": ("强化技能：自身技能赋予的麻痹效果、迟缓效果持续时间大幅延长",
                                            "强化技能：自身技能赋予的麻痹效果、冻结效果持续时间大幅延长")},
        desc=("向距离最近的敌人降下光矢之雨，对命中的敌人及其周围造成光属性伤害【对麻痹效果下的敌人伤害提升】"
              "＋赋予其麻痹效果＋迟缓效果＋累积全属性抗性降低效果／赋予光属性角色技能伤害提升效果",
              "向距离最近的敌人降下光矢之雨，对命中的敌人及其周围造成光属性伤害【对麻痹效果下的敌人伤害提升】"
              "＋赋予其麻痹效果＋冻结效果＋累积全属性抗性降低效果／赋予光属性角色技能伤害提升效果"),
        text_columns=(5, 7), levels=("1", "2"),
        hit_statuses=("ACParalysis", "ACFrozen", "ACToleranceOfElement"),
        hit_phrase="赋予其麻痹效果＋冻结效果＋累积全属性抗性降低效果",
        ally_statuses=("ACSkillDamage",), ally_phrase="赋予光属性角色技能伤害提升效果",
    ),
}
HIT_AREA_ONHIT = 23                                        # CreateHitArea 的命中块参数位（args[0] = 构造名）
TEXT_NCOLS = 12                                            # character_text / 服务端镜像每行列数
ACTION_NCOLS = 24

#: 技能强化文案 R2（作者 2026-09-27「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,…规范并简化描述」）。
#: 每条 = 能力键 ``key`` 里第 ``switch_row`` 行（536，c70 = ``string``）打开的技能强化：
#:   before / after  强化串改前（live；索恩 = 主会话 C「迟缓」→「冻结」之后）/ 改后（官方格式，点明技能名，定性）；
#:   skill           技能名（== character_text c4）；
#:   panel / line    覆盖面板里开关那一行（1 起；None = 该槽走客户端自动面板，只改串）；
#:   programs        两档技能程序；evidence = DSL 依据：
#:                   branch：每档恰一个 ConditionalsChangeSkillFlag(flag)，开 / 关支的 AC 差异 == changes
#:                           （added = 只在开支，stronger = 数值更大 / 时长更长）；没有 added 时两支别无结构差异；
#:                           可选 nodes = 每档旗号节点数（各节点差异并起来 == changes）、carriers = 两支抹掉 alv 后
#:                           比较（只差 alv 增量）且全树带 alv 的构造 == carriers、within = 旗号节点外层的 Conditionals*、
#:                           commands = {开支独有的非状态效果命令: 强化串里对应的定性措辞}（开支独有命令去掉 Find* 与
#:                           :data:`FLAG_NEUTRAL_COMMANDS` 后 == 登记，且每个措辞都在 after 里）；
#:                   alv：技能树无旗号节点，旗号经 alv 生效，带 alv 的构造 == carriers。
FLAG_TEXT = {
    "119989": dict(
        string="change_skill_lady_summoner_campus_dragon", key="1199891", switch_row=1, skill="绯焰实习·幼龙点名",
        before="强化幼龙吐息：降低全场敌人的能力伤害抗性",
        after="强化『绯焰实习·幼龙点名』：幼龙吐息降低全场敌人的能力伤害抗性",
        panel="desc_override_lady_summoner_campus_1", line=2,
        programs=(f"{_R5}lady_summoner_campus$lady_summoner_campus_1",
                  f"{_R5}lady_summoner_campus$lady_summoner_campus_2"),
        evidence=dict(mode="branch", flag=1, changes={"ACAbilityDamageResistance": "added"})),
    "119991": dict(
        string="change_skill_sorceress_teacher_moon", key="1199911", switch_row=1, skill="月相夜讲",
        before="强化技能：提升三相月讲的威力，并加强对火属性角色的技能伤害提升效果",
        after="强化『月相夜讲』的威力与「火属性角色技能伤害提升效果」",
        panel=None, line=None,                                   # 能力1 走客户端自动面板（前置 202 主位 + 火共鸣由客户端拼）
        programs=(f"{_R5}sorceress_teacher_moon$sorceress_teacher_moon_1",
                  f"{_R5}sorceress_teacher_moon$sorceress_teacher_moon_2"),
        evidence=dict(mode="alv", carriers=("CreateNormalAttack", "ACSkillDamage"))),
    # 旗号开支只把技能的 ACAttackPoint / ACPowerFlipDamage 1.5→2.5；「独立乘区＋91.7%」是能力6 #1（持续 421）的数值行，
    # 面板第2行另写 ⇒ 强化串删去「，并强化「独立乘区伤害提升效果」」。
    "129987": dict(
        string="change_skill_ghandagoza", key="1299876", switch_row=0, skill="炎天呑舟正拳突击",
        before="强化『炎天呑舟正拳突击』的「攻击力提升＋强化弹射伤害提升效果」，并强化「独立乘区伤害提升效果」",
        after="强化『炎天呑舟正拳突击』的「攻击力提升＋强化弹射伤害提升效果」",
        panel="desc_override_ghandagoza_6", line=1,
        programs=(f"{_R5}ghandagoza$ghandagoza_1", f"{_R5}ghandagoza$ghandagoza_2"),
        evidence=dict(mode="branch", flag=1, changes={"ACAttackPoint": "stronger", "ACPowerFlipDamage": "stronger"})),
    "159994": dict(
        string="change_skill_tweyen_light", key="1599941", switch_row=1, skill="星之猎手",
        before="强化技能：自身技能赋予的麻痹效果、冻结效果持续时间大幅延长",
        after="强化『星之猎手』：赋予的麻痹效果、冻结效果持续时间大幅延长",
        panel="desc_override_tweyen_light_1", line=2,
        programs=(f"{_R5}tweyen_light$tweyen_light_1", f"{_R5}tweyen_light$tweyen_light_2"),
        evidence=dict(mode="branch", flag=1, changes={"ACParalysis": "stronger", "ACFrozen": "stronger"})),
    # —— 以下 4 人此前没有 panels unit（本轮调整过、强化条目不合 R2）；强化槽都没有 desc_override（:func:`flag_problems`
    #    现场核对），走客户端自动面板（客户端按开关行前置自己拼共鸣 / 主位条件）⇒ panel=None，串里不写开关条件。
    # 杰拉尔：能力3 #0（536，水共鸣）。旗号 1 开支（两档各 5 处）：命中块 3 处 ACUnique 129992「对决」、FindAllSubjects(33)
    # ACPiercing ＋ 自身 ACFlying、FindAllSubjects(33) ACSkillDamage ⇒「己方贯穿＋队伍技能伤害提升＋自身浮游效果」＋「对决」；
    # 现文未点技能名、带「20秒」。
    "129992": dict(
        string="change_skill_unicorn_lancer_rose", key="1299923", switch_row=0, skill="誓约之枪·连突",
        before="技能追加：己方贯穿、队伍技能伤害提升、自身浮游20秒；命中时强制赋予敌人不可消除的「对决」。",
        after="为『誓约之枪·连突』追加「己方贯穿＋队伍技能伤害提升＋自身浮游效果」，命中时强制赋予敌人不可消除的「对决」",
        panel=None, line=None,
        programs=(f"{_R5}unicorn_lancer_rose$unicorn_lancer_rose_1", f"{_R5}unicorn_lancer_rose$unicorn_lancer_rose_2"),
        evidence=dict(mode="branch", flag=1, nodes=5,
                      changes={"ACFlying": "added", "ACPiercing": "added", "ACSkillDamage": "added",
                               "ACUnique": "added"})),
    # 夏琳：能力1 #1（536，雷共鸣）。旗号 1 开支（命中块）：累积 ACToleranceOfElement(254 全属性) / ACAttackPoint，两轮
    # ConditionalsProbability 各在 ACParalysis / ACPoison / ACFrozen 中取一 ⇒ 数据是冻结（主会话口径 C「迟缓」→「冻结」）；
    # 现文把「雷属性共鸣时」写进串、未点技能名。
    "139992": dict(
        string="change_skill_artificialeye_sniper_moon", key="1399921", switch_row=1, skill="桂影·望月三千",
        before="雷属性共鸣时强化技能：命中敌人时赋予其累积全属性抗性降低与累积攻击力降低效果（无视弱体抗性），"
               "并随机追加赋予麻痹、中毒、迟缓中的两种效果",
        after="强化『桂影·望月三千』：命中敌人时赋予其累积全属性抗性降低与累积攻击力降低效果（无视弱体抗性），"
              "并随机追加赋予麻痹、中毒、冻结中的两种效果",
        panel=None, line=None,
        programs=(f"{_R5}artificialeye_sniper_moon$artificialeye_sniper_moon_1",
                  f"{_R5}artificialeye_sniper_moon$artificialeye_sniper_moon_2"),
        evidence=dict(mode="branch", flag=1,
                      changes={"ACAttackPoint": "added", "ACFrozen": "added", "ACParalysis": "added",
                               "ACPoison": "added", "ACToleranceOfElement": "added"})),
    # 丝缇涅尔：能力1 #1（536，主位 202 ＋ 光共鸣）。旗号 1 节点两支只差 CreateNormalAttack 的 alv（28.7 / 43 倍 ＋37 ⇒
    # 「威力」），第2档光属性角色的 ACSkillDamage 另带 alv（0.6–1.2 ＋0.2–0.4 ⇒「技能伤害提升效果」）；技能名改用『』、
    # 效果名加「」（官方先例 change_skill_samurai_robot_plum「强化『…』的威力与「…效果」」）。
    "159995": dict(
        string="change_skill_still_obstinator_moon", key="1599951", switch_row=1, skill="月相仪·满月调律",
        before="强化「月相仪·满月调律」的威力与技能伤害提升效果",
        after="强化『月相仪·满月调律』的威力与「技能伤害提升效果」",
        panel=None, line=None,
        programs=(f"{_R5}still_obstinator_moon$still_obstinator_moon_1",
                  f"{_R5}still_obstinator_moon$still_obstinator_moon_2"),
        evidence=dict(mode="branch", flag=1, changes={}, carriers=("CreateNormalAttack", "ACSkillDamage"))),
    # 冰雪罗尔夫：能力3 #4（536，主位 202 ＋ 火共鸣）。旗号 1 节点在 ConditionalsFeverMode 的 Fever 分支里，开支 =
    # AddFeverPoint ＋ 全队五项 350%（超级Fever）＋ ChangeFieldAssets ＋ CreateRatioHeal ＋ ACRegeneration，关支空 ⇒
    # 「Fever状态中发动时增加Fever槽并触发超级Fever，…回复生命值、赋予再生效果」；现文未点技能名、没写加 Fever 槽。
    # 技能说明里的同一段删掉（:data:`DESC_TRIM`，含「Fever槽增加200」）⇒ AddFeverPoint 只能在这里定性写「增加Fever槽」
    # （总核对 major：删段后这项哪里都没写）；commands 把开支的非状态效果命令逐个对上措辞。
    "179999": dict(
        string="change_skill_black_wolf_knight_wt26", key="1799993", switch_row=4, skill="炉心颂歌",
        before="Fever状态中发动技能时，触发超级Fever：队伍全体的攻击力、强化弹射伤害、技能伤害、直接攻击伤害、"
               "能力伤害提升，同时为队伍全体回复生命值并赋予再生效果",
        after="强化『炉心颂歌』：Fever状态中发动时增加Fever槽并触发超级Fever，提升队伍全体的攻击力、强化弹射伤害、"
              "技能伤害、直接攻击伤害、能力伤害，并为队伍全体回复生命值、赋予再生效果",
        panel=None, line=None,
        programs=(f"{_R5}black_wolf_knight_wt26$black_wolf_knight_wt26_1",
                  f"{_R5}black_wolf_knight_wt26$black_wolf_knight_wt26_2"),
        evidence=dict(mode="branch", flag=1, within=("ConditionalsFeverMode",),
                      changes={"ACAbilityDamage": "added", "ACAttackPoint": "added", "ACDirectDamage": "added",
                               "ACPowerFlipDamage": "added", "ACRegeneration": "added", "ACSkillDamage": "added"},
                      commands={"AddFeverPoint": "增加Fever槽", "CreateRatioHeal": "回复生命值"})),
}
#: ``commands`` 依据里不算「效果」的开支命令：取对象（``Find*``）、状态（CreateCondition，由 changes 比）、场地演出。
FLAG_NEUTRAL_COMMANDS = frozenset({"CreateCondition", "ChangeFieldAssets"})
#: 技能强化开关（R1）：536 与 704–708。
SWITCH_KINDS = frozenset({SKILL_SWITCH_KIND, "704", "705", "706", "707", "708"})
#: 强化串 / 面板里不许出现的写法（R2：点明技能名；开关条件由面板前缀 / 客户端自动拼，不进串；不写强化后的描述）。
FLAG_BANNED = ("强化技能", "强化自身技能", "共鸣", "队长", "主位", "强化后", "不受此限")
#: 返回的全部面板不许再写的笼统标签（R2）。
R2_BANNED = ("强化技能", "强化自身技能")
#: R2 之前（第三轮面板合并稿）的面板改后文字：设计镜像可能停在这一版（本模块上一轮 ``--write``），同步时接受并改成现稿；
#: 与现稿只差登记的强化条目行（测试核对）。
PREVIOUS_AFTER = {
    "desc_override_tweyen_light_1": (
        "战斗开始时：自身技能槽立即＋50%",
        "光属性共鸣时，强化技能，自身技能赋予的麻痹效果、冻结效果持续时间大幅延长",
        "光属性角色减益技能特攻＋40%",
    ),
    "desc_override_tweyen_light_3": (
        " <icon id='main'>  自身发动技能时：光属性角色状态技能伤害＋200%（持续10秒，可叠加）",
        " <icon id='main'>  自身发动技能时：自身技能伤害＋20%，光属性角色技能充能速度＋1.5%（最多叠加10次）",
        " <icon id='main'>  光属性共鸣时，强化技能，敌方每有1个弱体效果，自身技能伤害＋40%，且连击＋50",
        " <icon id='main'>  光属性共鸣时，光属性角色发动技能时，光属性角色技能伤害＋50%（最多＋350%）、"
        "攻击力＋50%（最多＋350%）",
    ),
}
#: 妮可拉能力1 是客户端自动面板；``rework1/panel/nicola.json`` 能力1 第2行是它的设计镜像（改前 → 改后，前缀照旧）。
NICOLA_PANEL_LINE = (
    "持有者为主位且火属性共鸣时：自身技能形态切换为强化版——提升三相月讲的威力，并加强对火属性角色的技能伤害提升效果",
    "持有者为主位且火属性共鸣时：强化『月相夜讲』的威力与「火属性角色技能伤害提升效果」",
)

#: R3（技能说明只写本体）：冰雪罗尔夫 179999 的技能说明（action_skill 两档 c1、character_text c5/c7、服务端镜像 [5]/[7]，
#: 五处同文）把旗号 1 开支的强化效果整段写进了说明 ⇒ 删掉这一段（连同前导「／」），强化内容只留在强化条目
#: ``change_skill_black_wolf_knight_wt26``（:data:`FLAG_TEXT`，定性写：「Fever槽增加200」→「增加Fever槽」、350% / 10秒 /
#: 5% 不写数字；加 Fever 槽 / 比例回复两项由 FLAG_TEXT evidence.commands 核对措辞）。依据（:func:`desc_trim_problems`，两档逐项）：删掉那段的
#: 措辞都从旗号开支现算——开关行前置（火共鸣 ＋ 主位）与外层 ConditionalsFeverMode ⇒「火属性共鸣时，自身在主位且于
#: Fever状态中使用」、AddFeverPoint ⇒「Fever槽增加200」、全队五项 3.5 / 600 帧 ⇒「提升350%(10秒)」、CreateRatioHeal 0.05
#: ⇒「最大生命值5%」、ACRegeneration 600 帧 ⇒「再生效果(10秒)」；留下的「提升150%」「贯通(12.5秒)」来自分支外的
#: ACSkillDamage / ACPiercing。其余措辞与「 ※技能无后摇」逐字不动。
_WT26_DESC = ("赋予队长护盾、体力最低角色再生／火属性和风属性角色的技能伤害与强化弹射伤害提升150%／队伍全体贯通(12.5秒)"
              "／火属性共鸣时，自身在主位且于Fever状态中使用：Fever槽增加200，并触发超级Fever"
              "（队伍全体的攻击力、强化弹射伤害、技能伤害、直接攻击伤害、能力伤害提升350%(10秒)），"
              "同时为队伍全体回复最大生命值5%的生命值并赋予再生效果(10秒) ※技能无后摇")
_WT26_REMOVED = ("／火属性共鸣时，自身在主位且于Fever状态中使用：Fever槽增加200，并触发超级Fever"
                 "（队伍全体的攻击力、强化弹射伤害、技能伤害、直接攻击伤害、能力伤害提升350%(10秒)），"
                 "同时为队伍全体回复最大生命值5%的生命值并赋予再生效果(10秒)")
DESC_TRIM = {
    "179999": dict(
        removed=_WT26_REMOVED, desc=(_WT26_DESC, _WT26_DESC.replace(_WT26_REMOVED, "")),
        text_columns=(5, 7), levels=("1", "2"),
        buffs=("ACAbilityDamage", "ACAttackPoint", "ACDirectDamage", "ACPowerFlipDamage", "ACSkillDamage"),
        kept=("提升150%", "贯通(12.5秒)"),
    ),
}
#: 删完后的技能说明不许再出现的强化后写法（开关条件 / Fever 强化 / 上限豁免）与残留标点。
TRIM_MARKERS = ("共鸣", "主位", "队长时", "Fever", "超级", "强化后", "不受此限")
DANGLING_RE = re.compile(r"（）|\(\)|／／|^／|／$|／\s*※|，，|、、|，。|[：，、]$")

# ====================================================================== 角色 / 候选

#: 非小 Boss 角色：(code, 名字, 候选工作区, 本次 package_version)。版本 = 候选 manifest 现值 +1（只升不降）。
_OTHERS = {
    "119989": ("lady_summoner_campus", "碧安卡", "campus-bianca-20260911", "0.1.2"),      # 现 0.1.1（第二批）
    "119991": ("sorceress_teacher_moon", "妮可拉", "ma-nicola", "1.0.2"),                 # 现 1.0.1（第二批）
    "119992": ("tiger_treasure_hunter_moon", "米娅", "ma-mia", "1.0.1"),                  # 现 1.0.0
    "129987": ("ghandagoza", "冈达葛萨", "gbf-ghandagoza-20260919", "1.0.2"),             # 现 1.0.1（第二批）
    "159994": ("tweyen_light", "索恩", "ma-thorn", "1.0.2"),                              # 现 1.0.1（第二批）
    # 技能强化条目规范（R2 / R3）新增的 4 人。
    "129992": ("unicorn_lancer_rose", "杰拉尔", "unicorn_lancer_rose", "0.1.16"),          # 现 0.1.15（第二批）
    "139992": ("artificialeye_sniper_moon", "夏琳", "ma-charlene", "1.0.2"),              # 现 1.0.1（第一批）
    "159995": ("still_obstinator_moon", "丝缇涅尔", "ma-stinel", "1.0.2"),                 # 现 1.0.1（第一批）
    "179999": ("black_wolf_knight_wt26", "罗尔夫", "black_wolf_knight_wt26", "0.1.3"),    # 现 0.1.2（第一批）
}
#: 小 Boss 候选现值（第一 / 二批回写后）→ 本次 +1。
_MINIBOSS_VERSION = {
    "119993": "1.0.2", "119994": "1.0.2", "119995": "1.0.3", "129993": "1.0.2", "129994": "1.0.2",
    "129995": "1.0.2", "129996": "1.0.2", "129998": "1.0.3", "139996": "1.0.3", "149991": "1.0.2",
    "149992": "1.0.2", "149993": "1.0.2", "149994": "1.0.3", "159999": "1.0.3", "169993": "1.0.2",
}
UNIT_ORDER = ("119989", "119991", "119992", "119993", "119994", "119995", "129987", "129992", "129993",
              "129994", "129995", "129996", "129998", "139992", "139996", "149991", "149992", "149993", "149994",
              "159994", "159995", "159999", "169993", "179999")


def identity(cid: str) -> tuple[str, str, str, str]:
    """→ (code, 名字, 候选工作区, package_version)。"""
    if cid in _OTHERS:
        return _OTHERS[cid]
    char = MINIBOSS[cid]
    return char.code, char.name, char.package_id, _MINIBOSS_VERSION[cid]


#: extra5 stage_batch 的快照键；暂存回写后候选 manifest.snapshot[STAGE_SNAPSHOT].source == :data:`SOURCE`。
STAGE_SNAPSHOT = "revision_20260927d"


def staged_version(manifest: dict, package: str) -> str | None:
    """候选 manifest 已由本模块暂存回写时返回本次 package_version，否则 None（供早批测试识别「已再升一版」）。"""
    if (manifest.get("snapshot", {}).get(STAGE_SNAPSHOT) or {}).get("source") != SOURCE:
        return None
    versions = {identity(cid)[2]: identity(cid)[3] for cid in UNIT_ORDER}
    return versions.get(package)


def unit_panels(cid: str) -> tuple[dict, ...]:
    return tuple(p for p in PANELS if p["cid"] == cid)


def unit_inputs(cid: str) -> tuple[tuple[str, str], ...]:
    """本角色 revise() 读取的全部输入（顺序固定）。"""
    items = []
    for p in unit_panels(cid):
        items += [("cas", p["cas"]), (p["kind"], p["key"])]
    if cid in CENSUS:
        census = CENSUS[cid]
        items += [("leader", cid)] + [("ability", f"{cid}{n}") for n in range(1, 7)]
        items += [("action", identity(cid)[0])]
        items += [("dsl", path) for path in (*census["skills"], *census["invokes"])]
    if cid in SKILL_STATUS:
        items += [("action", identity(cid)[0])] + [("dsl", path) for path in SKILL_STATUS[cid]["skills"]]
    if cid in SKILL_TEXT:
        items += [("cas", key) for key in SKILL_TEXT[cid]["cas"]] + [("text", cid), ("server_text", cid)]
    if cid in FLAG_TEXT:
        spec = FLAG_TEXT[cid]
        items += [("cas", spec["string"]), ("ability", spec["key"]), ("text", cid), ("action", identity(cid)[0])]
        items += [("dsl", path) for path in spec["programs"]]
    if cid in DESC_TRIM:
        items += [("text", cid), ("server_text", cid), ("action", identity(cid)[0])]
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


#: live 输入基线（2026-09-27 本地链尾 1.4.1054，extra5 ``stage_batch.make_read(live_only=True)`` 只读取数，
#: 快照 tests/fixtures/balance_20260927c_panels.json）。值 = :func:`digest` (read(kind, key))；任一不符 ⇒ 拒绝。
BEFORE: dict[tuple[str, str], str] = {
    # R2（技能强化文案）新增输入：碧安卡能力1 面板 + 强化串 + 技能名（character_text）。
    ("cas", "desc_override_lady_summoner_campus_1"): "b3299a8bed8488c68b557b6e32ab0332465a309b7b8bb8dc8a735d07a6a57742",
    ("cas", "change_skill_lady_summoner_campus_dragon"):
        "567c4d22f341de2174e3be979d05caea42bf4e0cfe44c95776d007af15b67f7f",
    ("text", "119989"): "bcf2bb7f495715b2c9c2de9c090edc75c566ce7430610c48c5565e8627b83644",
    ("cas", "desc_override_lady_summoner_campus_3"): "574fa438ffb158610c2e05f207b5e21a2d1aedcd9ebd82b1d10eb822ad24b61c",
    ("ability", "1199893"): "14b978a86e7ad4e2fa026c43455514905300c8a075eec9712a60f543fe986b07",
    ("leader", "119989"): "efe0605142e2c5d91ad363f2c93699adb12971270d02be18ddda3a8b370a10c9",
    ("ability", "1199891"): "8630a5b8426a2f01da3a561354ab431305fe02d8b4d2db645dd5e1d5e36df5f1",
    ("ability", "1199892"): "b037f1c58ebe57223c85c6a0bbdc9693811002bd08c1c5774d96ff341e732a72",
    ("ability", "1199894"): "724505707615ab24369d4f81526d9d8d2341a8dc7aecfe7338f2c503ad407a14",
    ("ability", "1199895"): "860672ac2e838670202b281a500946c426f2e35d840f162242be662036945e13",
    ("ability", "1199896"): "315dda35910fccc4d5a9cbcae99fcb29cadd16765f9b525bf8e1d5abf56fb9d7",
    ("action", "lady_summoner_campus"): "aa04c0da4bbcfd3b968c547321ad6181f09486714ed0f4c31caf4ae2ac05390f",
    ("dsl", "battle/action/skill/action/rare5/lady_summoner_campus$lady_summoner_campus_1"):
        "7268b173ba49b8d67c4d7194f7da8d2bd5bc24382cf1fd25b4946472598c6bfc",
    ("dsl", "battle/action/skill/action/rare5/lady_summoner_campus$lady_summoner_campus_2"):
        "7268b173ba49b8d67c4d7194f7da8d2bd5bc24382cf1fd25b4946472598c6bfc",
    ("dsl", "battle/action/skill/action/ability_skill/lady_summoner_campus$lady_summoner_campus_fever_tick"):
        "3589c64732e4b37e3221c36650befa703a613604c85754d7667971f10d39bd9d",
    ("cas", "desc_override_sorceress_teacher_moon_3"): "5eec3f7ca0db6dc2e1c95b2a057af298742f293b6afc0ec969035c1da8c67299",
    ("ability", "1199913"): "cb91a9f576c1d879204a637a1eaca89049d95ad6f640ef83179cf2da6912098b",
    ("leader", "119991"): "7281dff694b656f5ada8b069d739d854280083e347f5fa4eee96a2812e0f6947",
    ("ability", "1199911"): "e1187d4407cc780ced8d9c26553198255cbf1c535e754981bb7f3abaf51b0319",
    ("ability", "1199912"): "4211c86fa71518d3abcff53bf56dfa51b4bd1e669de1b435786a912dcd0cfe20",
    ("ability", "1199914"): "58fbc1fe4e885a21d35ac40cbf7f17374579ece7067801f9c649673157e3c7bc",
    ("ability", "1199915"): "87fa7dbc7ab9253e2dbe281691b4d33f5cfcd36a0ab184e8407c7c83b9063a65",
    ("ability", "1199916"): "a98b8f87ae5a833f7a9700a35636f70509f0c17dc91acb03aa69f1efe4666c7b",
    ("action", "sorceress_teacher_moon"): "bafed9a1d52e2c6c37428575ef766e2199ecec8da819687b28d7f4885595207f",
    ("dsl", "battle/action/skill/action/rare5/sorceress_teacher_moon$sorceress_teacher_moon_1"):
        "51e0227e36216ab1caea7f198e0628a7ca80c0354d849bb837d9445cb5330214",
    ("dsl", "battle/action/skill/action/rare5/sorceress_teacher_moon$sorceress_teacher_moon_2"):
        "810b82e0fa5926531c46d8bb1c84df292f5f96937633d8d7fb2ac105411bc3f8",
    ("cas", "change_skill_sorceress_teacher_moon"): "5c19046f87bcd0d75564fb1394da79025d8eaf4fa9c30566e8c317002bdd1e67",
    ("text", "119991"): "d98d41ccb82565364b7082d081d5ccdca9d3dec1ca3b2eaa64cf0a8aa3359997",
    ("cas", "desc_override_tiger_treasure_hunter_moon"): "236482179eead53ebaaaa83f7996e398c9d21ebddf379edeb38b286a531f4fcb",
    ("leader", "119992"): "f3c20b225db79513d60cb14319e2725aca681b4fbc5f693720dbbfdb54e87aa5",
    ("cas", "desc_override_cobra_playable"): "d329afe4ddbc0921ad4ce7ee3ce16dd86d53acc0768ed461df8f2ae232a75fb2",
    ("leader", "119993"): "2d14c88754490c880179939e494c3c66c66141f9c38b15c5a09967e15897168a",
    ("cas", "desc_override_haniwa_playable"): "db94f09d7b184430da5268f7685494e3bc9d83636edfebb9a3efd1d5674956ef",
    ("leader", "119994"): "f6c7801eb9ab99beff085e6ffb284f73a1de19f64be4807457d622f384ec36fd",
    ("cas", "desc_override_dog_soldier_playable"): "c2ced04f3efe70408436484e1908ad9c9fe64c4d8ee5ab4309ab7e753816f973",
    ("leader", "119995"): "fb7131f099cdbe072b9d07dcb2392a4aa9ba76e50cc0c639f9999df2987a6c5e",
    ("cas", "desc_override_ghandagoza"): "148df300b5f48426c23c738c4c5e17248e7dd2cb27a9876ac64b12b5b2cdfb22",
    ("leader", "129987"): "b90a10e13f8f53f96806f860b1119bc91cdd862fb149299d82d3520d66e33de4",
    ("cas", "desc_override_ghandagoza_4"): "79128e65fd75c85e5bfe9bcb16822241ecce4f40b31c95cdfa5e26e8df330b64",
    ("ability", "1299874"): "81bd5ad49a41a53bd463748e61a4d6fa0563c1c04aff8b8610e68a1b645c848e",
    ("cas", "desc_override_ghandagoza_6"): "1136e50ddb07a2cad3f3a2116929df652f3a5cb5efd13da5075101425a580b12",
    ("ability", "1299876"): "2d40509555989f294845a087266b4fbe2dff2380af3cb9da83daa6c0f453da5a",
    ("cas", "change_skill_ghandagoza"): "9fb371659ae41f5fc0c56600f9c8b4075b7b00d813ac79363241eb8853b7c0a2",
    ("text", "129987"): "531e24eb0324981bf80ae886c2f37a04c512dadf8d307f0a69ab3b8a1251d72b",
    ("action", "ghandagoza"): "d0dc04b41772b042ee18a0400e27963641532b0423bf41b35bdefc65a8d43742",
    ("dsl", "battle/action/skill/action/rare5/ghandagoza$ghandagoza_1"):
        "b37c17b2f7e41b9fc154dec81a9e974e6b45743bb7053757f832e165afa6ef36",
    ("dsl", "battle/action/skill/action/rare5/ghandagoza$ghandagoza_2"):
        "b37c17b2f7e41b9fc154dec81a9e974e6b45743bb7053757f832e165afa6ef36",
    ("cas", "desc_override_killer_whale_playable"): "67366f37e41868675d2dcbb587f7c0ce7d1e4dbbd58096165144f7def4cbb39b",
    ("leader", "129993"): "e7f8170f932027cdc7aefc04a73ae392e061c6027ce213ca3c74db7cc5135629",
    ("cas", "desc_override_haniwa_blue_playable"): "5595a589007940f68fd50c9b0209be911754377e004732cf1c4e0b348c1cb4c7",
    ("leader", "129994"): "d15f4ed9f20e473fb128a13260989c09fc05ffd0d16eb161767488bf8aa969e9",
    ("cas", "desc_override_wander_armor_water_playable"):
        "5457330316af42b6f230a673de1d432fa419cbde780b2dbcfe0fdc63ea4bd9b8",
    ("leader", "129995"): "c5aaba3eb700611cec1a417b5a9439922651f8d39be23237b77a625772236be0",
    ("cas", "desc_override_clione_playable"): "1b6ed5fbc42a813a23b919149890c3601080f608423d75fd982d84f5b03472a7",
    ("leader", "129996"): "a95c981708ddd9549ce05e11727603090bc76587e9a3ea25a9d21a7adcf49a89",
    ("cas", "desc_override_ghost_girl_playable"): "09d566d993907cc93772b4f2189014ad6dcc95dba1d94243ccea55e4e73481c1",
    ("leader", "129998"): "d182a47c51b2f94c46726e84bcf0df16cc2ce3c8cd69315ba73d6c842bd521db",
    ("cas", "desc_override_cube_boss_playable"): "0c13dee08ab92e352c485ba30a0cd5abc4367e667ab8d427fdb2108203906cd3",
    ("leader", "139996"): "b7d9ed4a7d0a539bad2311fb4ed7a89af4549489c11d487980bbd12ea440fef1",
    ("cas", "desc_override_big_bear_monster_playable"): "934dc1d99bda50f3da0e50b3a95ff38bfac6b5c5a60f54edae6dd9ec64e90c8f",
    ("leader", "149991"): "73dbca9ab2f2da0bc61d4849c1f73b089112a588d410e59e22f998f57f3d88ad",
    ("cas", "desc_override_wander_armor_wind_playable"): "55c01c142c98bf0ae87b2924eee1668b02df688bf460fae8710deee3c379b955",
    ("leader", "149992"): "7e726b8e437cbd6ca5fe91786361eae4039af03bf4e9bcff07bf098f8c2072ff",
    ("cas", "desc_override_haniwa_green_playable"): "628e56d5a7c5dc293804d2146fb2b63906c58930adbcd8423d5065435ab330f9",
    ("leader", "149993"): "285cbf39e0123faa1abd0dba22f0c6dae1061faa8b2649c91388269fcaf74e64",
    ("cas", "desc_override_one_eyed_rabbit_playable"): "d39c5eaec28346248558d24ca053122a9c9fd393332930618aa650f686c1f3ba",
    ("leader", "149994"): "3026022473b143c0c5bf875c54d0180a72757ce1bbaae054ea9cddf79b58e395",
    ("cas", "desc_override_one_eyed_rabbit_playable_3"):
        "b1676545b5e12da21ec69d2081a2565ce0333ac8336be376412de3b0c587e56f",
    ("ability", "1499943"): "8ec0e91df9a9b7c1233ae08cf3392eb345e5e0ecb98442ba24e4577b81269373",
    ("cas", "desc_override_tweyen_light_1"): "b528f20e7fcbf986ebe5738bfdb77113e55f79e87c4200ca8424143217d84ef1",
    ("ability", "1599941"): "df321a18b53bdd0e12874654e11cb256f2c2f4f89647e3f097412d36f3e08531",
    ("cas", "desc_override_tweyen_light_2"): "f8c33a8e7ae14dff0e2570ce3f8bfe18082232b59bf0c7f6e0c150eac7b55ceb",
    ("ability", "1599942"): "88c59f9f26b53a06916a2444161ebe800b58e6bc5bcf25b238bdc123a6da87fd",
    ("cas", "desc_override_tweyen_light_3"): "7ccc77effbd34b3ebd8db2945eb5815fe10d3910fc2c9ca810f6df5b51b2bde6",
    ("ability", "1599943"): "e4017a4a7fc48cb16a8e960259ecc1a4acb8ba45aa407add1939b6119fe25ac5",
    ("cas", "desc_override_tweyen_light_4"): "3b0bd1b21393b85e5db9935002ef9a728bd99b880c95b8239cd9c7462247e74e",
    ("ability", "1599944"): "5088ef6c21e50649176e6e03a90f633a0193aa3539385cd55f489ddf71b6c150",
    ("action", "tweyen_light"): "9ebc6d797dcf0144613ba94b95282a0cfaa8f48dae01ee25c8cdafa7b9733eec",
    ("dsl", "battle/action/skill/action/rare5/tweyen_light$tweyen_light_1"):
        "128f30b2c270c62ab6a133784579d53052be8090fc5f1f92206d99ba9debf12f",
    ("dsl", "battle/action/skill/action/rare5/tweyen_light$tweyen_light_2"):
        "9b3e717066543e833913dc190392bab612ea6ef260b6cb76b62eabab62a9775f",
    # 主会话 C（索恩技能文字「迟缓」→「冻结」）；character_text 与服务端镜像同值 ⇒ 同一摘要。
    ("cas", "change_skill_tweyen_light"): "b02c740a9082f39824958772e64f340fb1362aead29e7a8dcba264d3f7ce22fe",
    ("text", "159994"): "967510daba4b270d05ad86e6c3a579448d5e8bd588d7f675511095615127c1fa",
    ("server_text", "159994"): "967510daba4b270d05ad86e6c3a579448d5e8bd588d7f675511095615127c1fa",
    ("cas", "desc_override_security_robot_playable"): "f7a8be18676d27f4b46bafdcf8e05ce75fd84d08765b49519c6d5c09d43921db",
    ("leader", "159999"): "7de6d16aab6a9b719468bf59effc7421111938b956abb0bed4d1bf4d00aa3c7e",
    ("cas", "desc_override_genin_playable"): "b163ef29578621a4045495803b7edf5f6a6482ff036434cce5d6f34a3c8d5e41",
    ("leader", "169993"): "25469667aadfe1c40ed679aaf71d8ac07aea497252b6aeabba4dc1b51937ef25",
    ("cas", "desc_override_genin_playable_1"): "37723885facbd632019b23189a22ca85d4e1fdffeac884ddcbe5a4c102f257fe",
    ("ability", "1699931"): "7e3ebdf67b37c8f31a530cb7213dd26496cc00abc10c594d46d897687abe227f",
    # 技能强化条目规范新增 4 人（:data:`FLAG_TEXT` 129992 / 139992 / 159995 / 179999，:data:`DESC_TRIM` 179999）：
    # 强化串、开关行所在能力键、技能名（character_text）、两档技能（action_skill + DSL）；冰雪罗尔夫另读服务端镜像。
    ("cas", "change_skill_unicorn_lancer_rose"): "e2825632e56b38d205626ad3df35cf3920f07efaacb4617c07da8ca16fb9be36",
    ("ability", "1299923"): "373f32614c660a31ddc0ccc867846c8d21d37586638e52d81ad1a3892a8de519",
    ("text", "129992"): "05aa2c0e06a7238b53b5d8c1603a5fb4aa3a264de80969a47efe601f62d0f822",
    ("action", "unicorn_lancer_rose"): "7d8ae4069a1c4ecb7490872ca566932e2e127311b068d1bcec1e89e383c1fe6a",
    ("dsl", "battle/action/skill/action/rare5/unicorn_lancer_rose$unicorn_lancer_rose_1"):
        "1f0fac6312da1786e115b83038ba813798e5d8556838a03758f323a9c2c45d67",
    ("dsl", "battle/action/skill/action/rare5/unicorn_lancer_rose$unicorn_lancer_rose_2"):
        "d119405ffcc6e793e29c53efd47bcdfd4ba6d25dba44d473b1681e85a5bdf3be",
    ("cas", "change_skill_artificialeye_sniper_moon"):
        "1d3a9b4beb45ef33472a2ddae090919b24d6ed86a47b6f1d8d4725b942b1174a",
    ("ability", "1399921"): "3e913a09272b7d31f8cdd24ab08a4ce951f5390d2f35ebd0860c07f80e75b94c",
    ("text", "139992"): "5ee4d3ffdefd438091ac8e1a2a6b831452dbd593fa59c92aa3a7141ed5e3f3bd",
    ("action", "artificialeye_sniper_moon"): "fbf1bbda97b1203fc50ec5cec20ab9230855e9fd3a0e5dd209702bea16217a0c",
    ("dsl", "battle/action/skill/action/rare5/artificialeye_sniper_moon$artificialeye_sniper_moon_1"):
        "cc9b50a5afb1524efbba5dfffa7c20a7833bfbb0688f4ac2fe23a83dc0bed469",
    ("dsl", "battle/action/skill/action/rare5/artificialeye_sniper_moon$artificialeye_sniper_moon_2"):
        "a1f91677505e3e8200d5d158aea9baa8a2db587580f10c9f07f77db68e1e25e5",
    ("cas", "change_skill_still_obstinator_moon"): "4df741bd504813852a10a885dfb72509dc5cab8d045b2ef71197bbcc820abe60",
    ("ability", "1599951"): "3d078548fb9d0c640250f66e0d0f8f53db4e740116f7adbfab14676ab095ca28",
    ("text", "159995"): "9f881febd0afd5539c34043540b518d5f6b08cb804f1206996282e0621a9c31f",
    ("action", "still_obstinator_moon"): "c8113a05fdf212748c7f25054f6d54371e51d937b6078deceda30234bd29e949",
    ("dsl", "battle/action/skill/action/rare5/still_obstinator_moon$still_obstinator_moon_1"):
        "ded33b9255bb2cde6fb9835b937bccc76a379700fb5844594e864952ac1f40e2",
    ("dsl", "battle/action/skill/action/rare5/still_obstinator_moon$still_obstinator_moon_2"):
        "e091f4d56c4115c16f963d0b08299f917b6d278c66d5440112a63c2f59f44ef1",
    ("cas", "change_skill_black_wolf_knight_wt26"): "ae814f9d937c7b38376c9d693e6d759ba848cb47fd4991bf3fc19da07babc3a8",
    ("ability", "1799993"): "7b265e76b3b8962e50e1a4a5fedfbfca5c6ebf43f2f321afe67fdc79d57ace9d",
    ("text", "179999"): "0f846839fffcbda191c6d097f50d24e4c24b842716b825c8591431ba96100ff5",
    ("action", "black_wolf_knight_wt26"): "59e43a5ba23b01a393d450d3faa3f1ef48a951dde863600ea07a8e073e7e7f09",
    ("dsl", "battle/action/skill/action/rare5/black_wolf_knight_wt26$black_wolf_knight_wt26_1"):
        "a07abc4c9e46f1edcc03b2295c77f5c0725916f3a22cf9286e67f5d4d5778242",
    ("dsl", "battle/action/skill/action/rare5/black_wolf_knight_wt26$black_wolf_knight_wt26_2"):
        "a07abc4c9e46f1edcc03b2295c77f5c0725916f3a22cf9286e67f5d4d5778242",
    ("server_text", "179999"): "0f846839fffcbda191c6d097f50d24e4c24b842716b825c8591431ba96100ff5",
}

# ====================================================================== 校验


def _baseline(cid: str, read: Callable[[str, Any], Any]) -> dict:
    inputs = {}
    for kind, key in unit_inputs(cid):
        value = read(kind, key)
        want = BEFORE.get((kind, key))
        if value is None or want is None or digest(value) != want:
            raise PanelMergeError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    return inputs


def _single_text(rows, key: str) -> str:
    if not (isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], list) and len(rows[0]) == 1):
        raise PanelMergeError(f"{key}: live override is not a single 1×1 cell")
    return rows[0][0]


def _pf_level(line: str) -> int | None:
    m = re.match(r"Lv(\d)强化弹射时", line[len(MAIN_ICON):] if line.startswith(MAIN_ICON) else line)
    return int(m.group(1)) if m else None


def _split_row_problems(panel: dict, rows: list[list[str]]) -> list[str]:
    """拆行面板：每行一个数据条件（行间两两不同、覆盖全部数据行各一次）；「LvN强化弹射时」行的数据触发 == 强化弹射 LvN；
    461 行的「获得N层」== 强度 / 100000。"""
    from wf_describe import describe_line
    kind, problems = panel["kind"], []
    covered = sorted(i for group in panel["groups"] for i in group)
    if covered != list(range(len(rows))) or len(panel["groups"]) != len(panel["after"]):
        problems.append(f"{panel['cas']}: split groups {panel['groups']} must cover rows 0..{len(rows) - 1} once, "
                        f"one group per line")
        return problems
    heads = [condition_cells(kind, rows[g[0]]) for g in panel["groups"]]
    if len(set(heads)) != len(heads):
        problems.append(f"{panel['cas']}: split lines share a data condition (should be merged, not split)")
    for line, group in zip(panel["after"], panel["groups"]):
        level = _pf_level(line)
        for i in group:
            described = describe_line(rows[i], "ability" if kind == "ability" else "leader_ability")
            levels = set(re.findall(r"强化弹射Lv(\d)≥", described))
            if level is not None and levels != {str(level)}:
                problems.append(f"{panel['cas']}: line {line!r} is Lv{level} but row #{i} triggers on {described!r}")
            if level is None and levels:
                problems.append(f"{panel['cas']}: row #{i} ({described!r}) is level-triggered but its line is not")
            base = _content_base(kind, rows[i])
            if rows[i][base] == UNIQUE_GRANT_KIND:
                low, high = effect_strength(kind, rows[i])
                if low != high or int(low) % 100000 or f"获得{int(low) // 100000}层" not in line:
                    problems.append(f"{panel['cas']}: row #{i} grants {low}/{high} but line says {line!r}")
    return problems


def check_rows(panel: dict, rows: list[list[str]]) -> list[str]:
    """数据锁：每组数据行除效果列外逐格相同，效果种类 == 登记值；非 722 行；共用数值的组强度逐行相同；拆行面板见
    :func:`_split_row_problems`。"""
    kind, problems = panel["kind"], []
    if len(rows) != panel["nrows"] or any(len(r) != LAYOUT[kind]["ncols"] for r in rows):
        return [f"{kind}:{panel['key']}: expected {panel['nrows']} rows × {LAYOUT[kind]['ncols']} cols"]
    if len(panel["groups"]) != len(panel["kinds"]):
        return [f"{panel['cas']}: groups / kinds registration differs in length"]
    for group, kinds in zip(panel["groups"], panel["kinds"]):
        got = tuple(effect_kind(kind, rows[i]) for i in group)
        if got != kinds:
            problems.append(f"{kind}:{panel['key']} group {group}: effect kinds {got} != {kinds}")
        if PF_OVERRIDE_KIND in got:
            problems.append(f"{kind}:{panel['key']} group {group}: mechanism row inside a merge group")
        conditions = {condition_cells(kind, rows[i]) for i in group}
        if len(conditions) != 1:
            head = condition_cells(kind, rows[group[0]])
            diff = sorted({c for i in group for c, v in enumerate(condition_cells(kind, rows[i])) if v != head[c]})
            problems.append(f"{kind}:{panel['key']} group {group}: conditions differ (non-effect cells {diff})")
        if panel["shared"] and len({effect_strength(kind, rows[i]) for i in group}) != 1:
            problems.append(f"{kind}:{panel['key']} group {group}: shared value but strengths differ")
    if panel["mode"] == "split":
        problems += _split_row_problems(panel, rows)
    if panel["mode"] == "edit":                  # 改字面板逐行对数据行：行首写「X属性共鸣时，」的，数据须带 X 共鸣前置
        for line, group in zip(panel["after"], panel["groups"]):
            m = _RES_HEAD_RE.match(_strip_icon(line))
            if m is None:
                continue
            token = next(t for t, cn in _EL_CN.items() if cn == m.group(1))
            for i in group:
                if token not in resonance_tokens(kind, rows[i]):
                    problems.append(f"{panel['cas']}: line {line!r} says {m.group(0)} but row #{i} lacks {token} "
                                    f"resonance")
    if kind == "ability":
        mains = {row[1] for row in rows}
        icons = {line.startswith(MAIN_ICON) for line in panel["after"]}
        if mains == {"false"} and icons != {True} or mains == {"true"} and icons != {False}:
            problems.append(f"{panel['cas']}: main-slot icon differs from c1 {sorted(mains)}")
    return problems


def dsl_grants(tree) -> set[str]:
    """DSL 里 CreateCondition 的 ACUnique 授予的 uid 集合。"""
    found: set[str] = set()

    def walk(node):
        if isinstance(node, list):
            if node and node[0] == "Command" and len(node) > 1 and isinstance(node[1], list):
                args = node[1]
                if args and args[0] == "CreateCondition" and len(args) > 2 and isinstance(args[2], list):
                    for cond in args[2]:
                        if isinstance(cond, list) and cond and cond[0] == "ACUnique" and len(cond) > 1:
                            found.add(str(int(cond[1])))
                for child in args[1:]:
                    walk(child)
                return
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(tree)
    return found


def state_sources(cid: str, inputs: dict) -> list[dict]:
    """普查固有状态的全部获取来源；来源不带共鸣或技能 DSL 自授予即报错。"""
    census = CENSUS[cid]
    uid, token = census["uid"], census["element"]
    actions = inputs["action", identity(cid)[0]]
    skills = tuple(fields[7] for _, fields in actions)
    if tuple(sorted(skills)) != tuple(sorted(census["skills"])):
        raise PanelMergeError(f"{cid}: skill programs drifted: {skills}")
    for path in census["skills"]:
        if uid in dsl_grants(inputs["dsl", path]):
            raise PanelMergeError(f"{cid}: skill program grants {uid} without a resonance gate: {path}")
    sources, invoked = [], set()
    for kind, key in [("leader", cid)] + [("ability", f"{cid}{n}") for n in range(1, 7)]:
        lay = LAYOUT[kind]
        for index, row in enumerate(inputs[kind, key]):
            if row[lay["trig"]] not in ("0", ""):
                continue
            content = row[lay["ic"]]
            via = None
            if content in GRANT_KINDS and row[lay["ic"] + 21] == uid:
                via = f"{content}"
            elif content == INVOKE_KIND:
                program = row[lay["ic"] + 24]
                invoked.add(program)
                if ("dsl", program) not in inputs:
                    raise PanelMergeError(f"{cid}: unreviewed 629 program {program}")
                if uid in dsl_grants(inputs["dsl", program]):
                    via = f"629 {program.rsplit('$', 1)[-1]}"
            if via is None:
                continue
            resonance = resonance_tokens(kind, row)
            if token not in resonance:
                raise PanelMergeError(f"{cid}: source {kind}:{key}#{index} ({via}) lacks {token} resonance")
            sources.append(dict(table=kind, key=key, row=index, via=via, resonance=resonance))
    if invoked != set(census["invokes"]):
        raise PanelMergeError(f"{cid}: 629 programs drifted: {sorted(invoked)}")
    if not sources:
        raise PanelMergeError(f"{cid}: no source grants {uid}")
    return sources


def change_skill_statuses(tree, flag: int) -> list[tuple[dict, dict]]:
    """每个 ``ConditionalsChangeSkillFlag(flag)`` 节点 → (开支 {状态: (最短, 最长)}, 关支 {…})，状态 = CreateCondition 的 AC*。"""
    def statuses(block) -> dict:
        found: dict[str, tuple[int, int]] = {}

        def walk(node):
            if isinstance(node, list):
                if node and node[0] == "Command" and len(node) > 1 and isinstance(node[1], list):
                    args = node[1]
                    if args and args[0] == "CreateCondition" and len(args) > 2 and isinstance(args[2], list):
                        for cond in args[2]:
                            if (isinstance(cond, list) and len(cond) > 1 and isinstance(cond[1], list) and cond[1]
                                    and isinstance(cond[1][0], dict)):
                                span = (int(cond[1][0]["min"]), int(cond[1][0]["max"]))
                                if cond[0] in found and found[cond[0]] != span:
                                    raise PanelMergeError(f"{cond[0]} has two durations in one branch")
                                found[cond[0]] = span
                for child in node:
                    walk(child)
            elif isinstance(node, dict):
                for child in node.values():
                    walk(child)

        walk(block)
        return found

    out = []

    def walk(node):
        if isinstance(node, list):
            if len(node) >= 4 and node[0] == "ConditionalsChangeSkillFlag" and node[1] == flag:
                out.append((statuses(node[2]), statuses(node[3])))
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(tree)
    return out


def skill_status_problems(cid: str, inputs: dict) -> tuple[list[str], dict]:
    """面板 / 强化串「强化『星之猎手』：赋予的<状态>效果持续时间大幅延长」的数据依据（见 :data:`SKILL_STATUS`）。"""
    spec, problems, evidence = SKILL_STATUS[cid], [], {}
    row = inputs["ability", spec["key"]][spec["switch_row"]]
    lay = LAYOUT["ability"]
    if (row[lay["trig"]] != "0" or row[lay["ic"]] != SKILL_SWITCH_KIND or row[lay["ic"] + 23] != spec["string"]
            or resonance_tokens("ability", row) != [spec["element"]]):
        problems.append(f"{spec['key']}#{spec['switch_row']}: not the {spec['element']}-resonance 536 switch "
                        f"to {spec['string']}")
    skills = tuple(fields[7] for _, fields in inputs["action", identity(cid)[0]])
    if tuple(sorted(skills)) != tuple(sorted(spec["skills"])):
        problems.append(f"{cid}: skill programs drifted: {skills}")
    for path in spec["skills"]:
        nodes = change_skill_statuses(inputs["dsl", path], spec["flag"])
        if len(nodes) != 1:
            problems.append(f"{path}: expected one ConditionalsChangeSkillFlag({spec['flag']}), got {len(nodes)}")
            continue
        on, off = nodes[0]
        if set(on) != set(spec["statuses"]) or set(off) != set(spec["statuses"]):
            problems.append(f"{path}: switch branches carry {sorted(on)} / {sorted(off)}, "
                            f"panel names {list(spec['statuses'])}")
            continue
        for status in spec["statuses"]:
            if on[status][0] <= off[status][1]:
                problems.append(f"{path}: {status} on-branch {on[status]} is not longer than off-branch {off[status]}")
        evidence[path.rsplit("$", 1)[-1]] = {s: dict(on=list(on[s]), off=list(off[s])) for s in spec["statuses"]}
    return problems, evidence


def skill_conditions(tree) -> dict[str, set[str]]:
    """技能 DSL 的 CreateCondition 状态（AC* 构造名）：``hit`` = 判定区命中块（CreateHitArea 第 23 参）内，``other`` = 其余。"""
    out: dict[str, set[str]] = {"hit": set(), "other": set()}

    def walk(node, where):
        if isinstance(node, list):
            if node and node[0] == "Command" and len(node) > 1 and isinstance(node[1], list):
                args = node[1]
                if args and args[0] == "CreateCondition" and len(args) > 2 and isinstance(args[2], list):
                    out[where].update(c[0] for c in args[2] if isinstance(c, list) and c and isinstance(c[0], str))
                if args and args[0] == "CreateHitArea":
                    for index, child in enumerate(args):
                        walk(child, "hit" if index == HIT_AREA_ONHIT else where)
                    return
            for child in node:
                walk(child, where)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child, where)

    walk(tree, "other")
    return out


def skill_text_problems(cid: str, inputs: dict) -> tuple[list[str], dict]:
    """主会话 C 的数据依据（见 :data:`SKILL_TEXT`）：技能说明里的「麻痹效果＋冻结效果＋累积全属性抗性降低效果」恰是两档
    DSL 命中块的状态集合、「赋予光属性角色技能伤害提升效果」恰是命中块外的状态集合；ACFrozen / ACParalysis 的客户端名
    （``wf_dsl_sig.AC_CN``）== 改后用词；每处改后 == 改前恰一处 old → new。强化条目的开关分支依据见 :func:`skill_status_problems`。"""
    from wf_dsl_sig import AC_CN
    spec, problems, evidence = SKILL_TEXT[cid], [], {}
    status = SKILL_STATUS.get(cid)
    if status is None or set(spec["cas"]) != {status["string"]}:
        problems.append(f"{cid}: skill-flag string {sorted(spec['cas'])} is not backed by SKILL_STATUS")
    named = f"{AC_CN['ACParalysis']}效果＋{AC_CN['ACFrozen']}效果"
    if AC_CN.get("ACFrozen") != spec["new"] or named not in spec["hit_phrase"]:
        problems.append(f"{cid}: ACFrozen/ACParalysis client names {AC_CN.get('ACFrozen')}/{AC_CN.get('ACParalysis')} "
                        f"do not read {spec['hit_phrase']!r}")
    old, new = spec["old"], spec["new"]
    for label, (before, after) in [("desc", spec["desc"]), *spec["cas"].items()]:
        if before.count(old) != 1 or before.replace(old, new) != after or old in after:
            problems.append(f"{label}: after must be before with exactly one {old!r} → {new!r}")
    desc = spec["desc"][1]
    if spec["hit_phrase"] not in desc or spec["ally_phrase"] not in desc:
        problems.append(f"{cid}: skill description lacks {spec['hit_phrase']!r} / {spec['ally_phrase']!r}")
    actions = inputs["action", identity(cid)[0]]
    if [inner for inner, _ in actions] != list(spec["levels"]):
        problems.append(f"{cid}: action_skill levels {[inner for inner, _ in actions]} != {list(spec['levels'])}")
    for inner, fields in actions:
        path = fields[7]
        if status is None or path not in status["skills"]:
            problems.append(f"{cid}: action_skill {inner} runs an unreviewed program {path}")
            continue
        got = skill_conditions(inputs["dsl", path])
        if got["hit"] != set(spec["hit_statuses"]) or got["other"] != set(spec["ally_statuses"]):
            problems.append(f"{path}: statuses hit={sorted(got['hit'])} other={sorted(got['other'])}, "
                            f"description names "
                            f"{list(spec['hit_statuses'])} + {list(spec['ally_statuses'])}")
        evidence[inner] = {where: sorted(names) for where, names in got.items()}
    return problems, evidence


def skill_text_outputs(cid: str, inputs: dict) -> dict:
    """主会话 C 的改字：live 每处 == 改前（否则拒绝），返回 cas / text / action / server_text 四类改后值（不改 inputs）。"""
    spec, code = SKILL_TEXT[cid], identity(cid)[0]
    before, after = spec["desc"]
    cas = {}
    for key, (old_text, new_text) in spec["cas"].items():
        if _single_text(inputs["cas", key], key) != old_text:
            raise PanelMergeError(f"{key}: live text differs from the reviewed text")
        cas[key] = [[new_text]]
    rows_out = {}
    for kind in ("text", "server_text"):
        rows = deepcopy(inputs[kind, cid])
        if not (isinstance(rows, list) and len(rows) == 1 and len(rows[0]) == TEXT_NCOLS):
            raise PanelMergeError(f"{kind}:{cid}: expected one {TEXT_NCOLS}-column row")
        for col in spec["text_columns"]:
            if rows[0][col] != before:
                raise PanelMergeError(f"{kind}:{cid} c{col}: live skill description differs from the reviewed text")
            rows[0][col] = after
        rows_out[kind] = rows
    actions = []
    for inner, fields in inputs["action", code]:
        fields = list(fields)
        if len(fields) != ACTION_NCOLS or fields[1] != before:
            raise PanelMergeError(f"action:{code}/{inner}: live c1 differs from the reviewed text")
        fields[1] = after
        actions.append((inner, fields))
    return dict(cas=cas, text={cid: rows_out["text"]}, action={code: actions},
                server_text={cid: rows_out["server_text"]})


# ---------------------------------------------------------------------- R2 技能强化条目


def _is_ac(node) -> bool:
    return isinstance(node, list) and bool(node) and isinstance(node[0], str) and node[0].startswith("AC")


def _conditions(block) -> list[list]:
    """块内 CreateCondition 的 AC 条目（按出现顺序）。"""
    found: list[list] = []

    def walk(node):
        if isinstance(node, list):
            if node and node[0] == "Command" and len(node) > 1 and isinstance(node[1], list):
                args = node[1]
                if args and args[0] == "CreateCondition" and len(args) > 2 and isinstance(args[2], list):
                    found.extend(cond for cond in args[2] if _is_ac(cond))
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(block)
    return found


def _mask_conditions(node):
    """CreateCondition 里每个 AC 条目只留构造名（抹掉参数）：用来比较两支除状态参数以外的结构。"""
    if isinstance(node, list):
        if node and node[0] == "Command" and len(node) > 1 and isinstance(node[1], list):
            args = node[1]
            if args and args[0] == "CreateCondition" and len(args) > 2 and isinstance(args[2], list):
                conds = [[c[0]] if _is_ac(c) else _mask_conditions(c) for c in args[2]]
                args = [args[0], _mask_conditions(args[1]), conds, *(_mask_conditions(a) for a in args[3:])]
                return ["Command", args, *(_mask_conditions(x) for x in node[2:])]
        return [_mask_conditions(child) for child in node]
    if isinstance(node, dict):
        return {key: _mask_conditions(value) for key, value in node.items()}
    return node


def _numeric_diffs(a, b, out: list) -> None:
    """同形两棵参数树的数值差异 (a, b)；形状不同或非数值不同记 None。"""
    if isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys():
        for key in a:
            _numeric_diffs(a[key], b[key], out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for x, y in zip(a, b):
            _numeric_diffs(x, y, out)
    elif (isinstance(a, (int, float)) and isinstance(b, (int, float))
          and not isinstance(a, bool) and not isinstance(b, bool)):
        if a != b:
            out.append((a, b))
    elif a != b:
        out.append(None)


def branch_changes(on, off) -> tuple[dict[str, str], bool]:
    """旗号开 / 关支的状态差异 {AC 构造名: added / removed / stronger / weaker / mixed}（stronger = 每个不同的数值
    绝对值都不小于关支），以及抹掉状态参数后两支是否仍有结构差异。"""
    sides = []
    for block in (on, off):
        entries: dict[str, list] = {}
        for cond in _conditions(block):
            entries.setdefault(cond[0], []).append(cond[1:])
        sides.append(entries)
    e_on, e_off = sides
    changes = {}
    for name in sorted(set(e_on) | set(e_off)):
        if name not in e_off:
            changes[name] = "added"
        elif name not in e_on:
            changes[name] = "removed"
        elif e_on[name] != e_off[name]:
            diffs: list = []
            _numeric_diffs(e_on[name], e_off[name], diffs)
            if not diffs or None in diffs:
                changes[name] = "mixed"
            elif all(abs(a) >= abs(b) for a, b in diffs):
                changes[name] = "stronger"
            elif all(abs(a) <= abs(b) for a, b in diffs):
                changes[name] = "weaker"
            else:
                changes[name] = "mixed"
    return changes, _mask_conditions(on) != _mask_conditions(off)


def flag_nodes(tree, flag: int | None = None) -> list[list]:
    """``ConditionalsChangeSkillFlag`` 节点（flag=None ⇒ 任意开关号）。"""
    out: list[list] = []

    def walk(node):
        if isinstance(node, list):
            if (len(node) >= 4 and node[0] == "ConditionalsChangeSkillFlag"
                    and (flag is None or node[1] == flag)):
                out.append(node)
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(tree)
    return out


def alv_carriers(tree) -> set[str]:
    """带 ``alv_min`` / ``alv_max`` 的数值所在的构造（最近一层以 AC / Create 开头的构造名；找不到记 "?"）。"""
    found: set[str] = set()

    def walk(node, owner):
        if isinstance(node, dict):
            if "alv_min" in node or "alv_max" in node:
                found.add(owner or "?")
            for value in node.values():
                walk(value, owner)
        elif isinstance(node, list):
            if node and isinstance(node[0], str) and node[0].startswith(("AC", "Create")):
                owner = node[0]
            for child in node:
                walk(child, owner)

    walk(tree, None)
    return found


def flag_problems(cid: str, inputs: dict, current: str) -> tuple[list[str], dict]:
    """R2 强化条目的格式与数据锁（见 :data:`FLAG_TEXT`）。``current`` = 本模块此前各步之后的强化串（索恩 = 主会话 C 的
    「冻结」稿，其余 = live）；≠ 登记改前即拒绝。返回 (问题, 依据)。"""
    spec, problems = FLAG_TEXT[cid], []
    if current != spec["before"]:
        raise PanelMergeError(f"{spec['string']}: live text differs from the reviewed text")
    lay = LAYOUT["ability"]
    rows = inputs["ability", spec["key"]]
    row = rows[spec["switch_row"]]
    if row[lay["trig"]] != "0" or row[lay["ic"]] != SKILL_SWITCH_KIND or row[lay["ic"] + 23] != spec["string"]:
        problems.append(f"{spec['key']}#{spec['switch_row']}: not the 536 switch to {spec['string']}")
    switches = [i for i, r in enumerate(rows) if r[lay["trig"]] == "0" and r[lay["ic"]] in SWITCH_KINDS]
    if switches != [spec["switch_row"]]:
        problems.append(f"{spec['key']}: skill switches at rows {switches}, registered [{spec['switch_row']}]")
    text = inputs["text", cid][0]
    if text[4] != spec["skill"] or text[6] not in (spec["skill"], spec["skill"] + "＋"):
        problems.append(f"{cid}: skill name {text[4]!r} / {text[6]!r} is not 『{spec['skill']}』")
    after = spec["after"]
    if not after.startswith((f"强化『{spec['skill']}』", f"为『{spec['skill']}』追加")):
        problems.append(f"{spec['string']}: {after!r} does not open with 强化『{spec['skill']}』")
    problems += [f"{spec['string']}: {p}" for p in kit_panel_problems(after, skill_flag=True)]
    problems += [f"{spec['string']}: must not write {word!r}" for word in FLAG_BANNED if word in after]
    tokens = resonance_tokens("ability", row)
    if spec["panel"] is not None:
        panel = PANELS_BY_CAS.get(spec["panel"])
        if panel is None or panel["cid"] != cid or panel["key"] != spec["key"]:
            problems.append(f"{spec['panel']}: not a registered panel of ability:{spec['key']}")
        else:
            pre = [row[b] for b in lay["pre"] if row[b] not in ("0", "")]
            if len(pre) != len(tokens):
                problems.append(f"{spec['key']}#{spec['switch_row']}: switch preconditions {pre} are not "
                                f"resonance-only; the panel prefix cannot say them")
            want = ((MAIN_ICON if row[1] == "false" else "")
                    + "".join(f"{_EL_CN[t]}属性共鸣时，" for t in tokens) + after)
            line = panel["after"][spec["line"] - 1]
            if line not in (want, want + "。"):
                problems.append(f"{spec['panel']} line {spec['line']}: {line!r} is not {want!r}(。)")
            if panel["groups"][spec["line"] - 1] != (spec["switch_row"],):
                problems.append(f"{spec['panel']} line {spec['line']}: registered rows "
                                f"{panel['groups'][spec['line'] - 1]} are not the switch row")
    evidence = dict(switch=f"ability:{spec['key']}#{spec['switch_row']}", resonance=tokens,
                    precondition_kinds=[row[b] for b in lay["pre"]], skill=spec["skill"], dsl={})
    actions = inputs["action", identity(cid)[0]]
    paths = tuple(fields[7] for _, fields in actions)
    if tuple(sorted(paths)) != tuple(sorted(spec["programs"])):
        problems.append(f"{cid}: skill programs drifted: {paths}")
        return problems, evidence
    rule = spec["evidence"]
    for inner, fields in actions:
        tree = inputs["dsl", fields[7]]
        if rule["mode"] == "branch":
            nodes = flag_nodes(tree, rule["flag"])
            if len(nodes) != rule.get("nodes", 1):
                problems.append(f"{fields[7]}: expected {rule.get('nodes', 1)} ConditionalsChangeSkillFlag"
                                f"({rule['flag']}), got {len(nodes)}")
                continue
            # 可选 carriers：两支只差 alv 增量（丝缇涅尔）⇒ 抹掉 alv 再比；可选 nodes：各节点差异并起来比。
            strip = strip_alv if "carriers" in rule else (lambda node: node)
            changes, structural = {}, False
            for node in nodes:
                part, differs = branch_changes(strip(node[2]), strip(node[3]))
                for name, change in part.items():
                    changes[name] = change if changes.get(name, change) == change else "mixed"
                structural = structural or differs
            changes = dict(sorted(changes.items()))
            if changes != rule["changes"]:
                problems.append(f"{fields[7]}: switch branches change {changes}, the text names {rule['changes']}")
            if structural and not {"added", "removed"} & set(changes.values()):
                problems.append(f"{fields[7]}: switch branches differ beyond the named status values")
            evidence["dsl"][inner] = dict(changes=changes, structural=structural)
            if "within" in rule:                  # 旗号节点外层的 Conditionals*（冰雪罗尔夫 = Fever 分支）
                contexts = sorted(set(flag_contexts(tree, rule["flag"])))
                if contexts != [tuple(rule["within"])]:
                    problems.append(f"{fields[7]}: switch nodes sit in {contexts}, registered {rule['within']}")
                evidence["dsl"][inner]["within"] = [list(c) for c in contexts]
            if "carriers" in rule:
                evidence["dsl"][inner]["alv"] = sorted(alv_carriers(tree))
            if "commands" in rule:                # 开支独有的非状态效果命令（冰雪罗尔夫 = 加 Fever 槽 / 比例回复）
                names = [{c[0] for node in nodes for c in _commands_in(node[side])} for side in (2, 3)]
                effects = sorted(name for name in names[0] - names[1]
                                 if not name.startswith("Find") and name not in FLAG_NEUTRAL_COMMANDS)
                if effects != sorted(rule["commands"]):
                    problems.append(f"{fields[7]}: switch branch adds commands {effects}, "
                                    f"the text names {sorted(rule['commands'])}")
                evidence["dsl"][inner]["commands"] = effects
        else:
            if flag_nodes(tree):
                problems.append(f"{fields[7]}: has ConditionalsChangeSkillFlag; registered as alv-only")
            evidence["dsl"][inner] = dict(alv=sorted(alv_carriers(tree)))
    if "carriers" in rule:
        carriers = {name for level in evidence["dsl"].values() for name in level.get("alv", ())}
        if carriers != set(rule["carriers"]):
            problems.append(f"{cid}: alv carriers {sorted(carriers)} != {list(rule['carriers'])}")
    problems += [f"{spec['string']}: switch-branch {name} is not written as {phrase!r}"
                 for name, phrase in rule.get("commands", {}).items() if phrase not in after]
    return problems, evidence


def strip_alv(node):
    """抹掉 ``alv_min`` / ``alv_max``（旗号经 alv 生效的增量）：比较开 / 关两支除 alv 以外是否同形。"""
    if isinstance(node, dict):
        return {key: strip_alv(value) for key, value in node.items() if key not in ("alv_min", "alv_max")}
    if isinstance(node, list):
        return [strip_alv(child) for child in node]
    return node


def flag_contexts(tree, flag: int) -> list[tuple[str, ...]]:
    """每个 ``ConditionalsChangeSkillFlag(flag)`` 节点外层的 Conditionals* 构造名（由外到内）。"""
    out: list[tuple[str, ...]] = []

    def walk(node, stack):
        if isinstance(node, list):
            if len(node) >= 4 and node[0] == "ConditionalsChangeSkillFlag" and node[1] == flag:
                out.append(tuple(stack))
                return
            head = node[0] if node and isinstance(node[0], str) and node[0].startswith("Conditionals") else None
            for child in node:
                walk(child, stack + [head] if head else stack)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child, stack)

    walk(tree, [])
    return out


def auto_panel_problems(cid: str, read: Callable[[str, Any], Any]) -> list[str]:
    """``panel=None`` 的强化条目：该槽确实没有 ``desc_override_<code>_<槽>``（客户端自动面板，按开关行前置自己拼条件，
    所以串里不写开关条件）；有覆盖键就该登记 panel / line。"""
    spec = FLAG_TEXT.get(cid)
    if spec is None or spec["panel"] is not None:
        return []
    key = f"desc_override_{identity(cid)[0]}_{spec['key'][len(cid):]}"
    try:
        value = read("cas", key)
    except KeyError:
        return []
    return [] if value is None else [f"{key}: override exists; register it as panel / line of {spec['string']}"]


def _commands_in(node, out: list | None = None) -> list[list]:
    """深度优先收集 ``["Command", [name, …]]`` 的参数数组（原对象，可按 id 比较）。"""
    out = [] if out is None else out
    if isinstance(node, list):
        if len(node) == 2 and node[0] == "Command" and isinstance(node[1], list) and node[1] \
                and isinstance(node[1][0], str):
            out.append(node[1])
        for child in node:
            _commands_in(child, out)
    elif isinstance(node, dict):
        for child in node.values():
            _commands_in(child, out)
    return out


def _peak(cell) -> float:
    """SLv 数值 ``[{min, max}, …]`` → 首档 max。"""
    return cell[0]["max"]


def desc_trim_problems(cid: str, inputs: dict) -> tuple[list[str], dict]:
    """R3 删段的依据（见 :data:`DESC_TRIM`）：删掉那段的措辞全部由旗号开支现算得出，留下的数值全部来自分支外；
    改后 == 改前恰删一段、无强化后写法与残留标点。"""
    spec, flag, problems, evidence = DESC_TRIM[cid], FLAG_TEXT[cid], [], {}
    before, after = spec["desc"]
    if before.count(spec["removed"]) != 1 or before.replace(spec["removed"], "") != after:
        problems.append(f"{cid}: after must be before with the registered segment removed once")
    problems += [f"{cid}: description still writes {word!r}: {after}" for word in TRIM_MARKERS if word in after]
    if DANGLING_RE.search(after):
        problems.append(f"{cid}: dangling punctuation left in {after!r}")
    problems += [f"{cid}: {p}" for p in kit_panel_problems(after)]
    lay = LAYOUT["ability"]
    row = inputs["ability", flag["key"]][flag["switch_row"]]
    gate = ("".join(f"{_EL_CN[t]}属性共鸣时，" for t in resonance_tokens("ability", row))
            + ("自身在主位且" if any(row[b] == "202" for b in lay["pre"]) else "")
            + ("于Fever状态中使用" if "ConditionalsFeverMode" in flag["evidence"].get("within", ()) else ""))
    for inner, fields in inputs["action", identity(cid)[0]]:
        tree = inputs["dsl", fields[7]]
        found = flag_nodes(tree, flag["evidence"]["flag"])
        if len(found) != 1:
            problems.append(f"{fields[7]}: expected one ConditionalsChangeSkillFlag, got {len(found)}")
            continue
        on, off = _commands_in(found[0][2]), _commands_in(found[0][3])
        inside = {id(c) for c in on + off}
        base = [c for c in _commands_in(tree) if id(c) not in inside]
        conds = [cond for c in on if c[0] == "CreateCondition" for cond in c[2] if _is_ac(cond)]
        buffs = {cond[0]: (_peak(cond[1]), _peak(cond[2])) for cond in conds if cond[0] in spec["buffs"]}
        fever = [c for c in on if c[0] == "AddFeverPoint"]
        heal = [c for c in on if c[0] == "CreateRatioHeal"]
        regen = [cond for cond in conds if cond[0] == "ACRegeneration"]
        if (off or len(fever) != 1 or len(heal) != 1 or len(regen) != 1 or set(buffs) != set(spec["buffs"])
                or len(set(buffs.values())) != 1 or len(conds) != len(spec["buffs"]) + 1):
            problems.append(f"{fields[7]}: switch branch is not the registered super-Fever shape")
            continue
        frames, value = next(iter(buffs.values()))
        removed = [gate, f"Fever槽增加{_peak(fever[0][1]):g}", f"提升{value * 100:g}%({frames / 60:g}秒)",
                   f"最大生命值{_peak(heal[0][3]) * 100:g}%", f"再生效果({_peak(regen[0][1]) / 60:g}秒)"]
        base_conds = {cond[0]: cond for c in base if c[0] == "CreateCondition" for cond in c[2] if _is_ac(cond)}
        kept = []
        if "ACSkillDamage" in base_conds:
            kept.append(f"提升{_peak(base_conds['ACSkillDamage'][2]) * 100:g}%")
        if "ACPiercing" in base_conds:
            kept.append(f"贯通({_peak(base_conds['ACPiercing'][1]) / 60:g}秒)")
        problems += [f"{fields[7]}: removed segment lacks {p!r} (switch branch)" for p in removed
                     if p not in spec["removed"]]
        if tuple(kept) != spec["kept"] or any(p not in after for p in kept):
            problems.append(f"{fields[7]}: kept wording {kept} is not {list(spec['kept'])} from outside the switch")
        evidence[inner] = dict(removed_from_switch_branch=removed, kept_from_base=kept)
    return problems, evidence


def desc_trim_outputs(cid: str, inputs: dict) -> dict:
    """R3 删段：live 五处 == 改前（否则拒绝）；返回 text / action / server_text 改后值（不改 inputs）。"""
    spec, code = DESC_TRIM[cid], identity(cid)[0]
    before, after = spec["desc"]
    rows_out = {}
    for kind in ("text", "server_text"):
        rows = deepcopy(inputs[kind, cid])
        if not (isinstance(rows, list) and len(rows) == 1 and len(rows[0]) == TEXT_NCOLS):
            raise PanelMergeError(f"{kind}:{cid}: expected one {TEXT_NCOLS}-column row")
        for col in spec["text_columns"]:
            if rows[0][col] != before:
                raise PanelMergeError(f"{kind}:{cid} c{col}: live skill description differs from the reviewed text")
            rows[0][col] = after
        rows_out[kind] = rows
    actions = []
    for inner, fields in inputs["action", code]:
        fields = list(fields)
        if len(fields) != ACTION_NCOLS or fields[1] != before:
            raise PanelMergeError(f"action:{code}/{inner}: live c1 differs from the reviewed text")
        fields[1] = after
        actions.append((inner, fields))
    if [inner for inner, _ in actions] != list(spec["levels"]):
        raise PanelMergeError(f"action:{code}: levels {[inner for inner, _ in actions]} != {list(spec['levels'])}")
    return dict(text={cid: rows_out["text"]}, action={code: actions}, server_text={cid: rows_out["server_text"]})


def cas_changes(cid: str) -> dict[str, tuple[str, str]]:
    """本模块改的强化串：{键: (live 改前, 最终改后)}（主会话 C「迟缓」→「冻结」与 R2 串联）。"""
    out = {key: pair for key, pair in SKILL_TEXT.get(cid, {}).get("cas", {}).items()}
    if cid in FLAG_TEXT:
        spec = FLAG_TEXT[cid]
        before = out[spec["string"]][0] if spec["string"] in out else spec["before"]
        out[spec["string"]] = (before, spec["after"])
    return out


def _pre_edited(panel: dict) -> str:
    lines = list(panel["before"])
    for line_no, old, new in panel["pre_edits"]:
        if lines[line_no - 1].count(old) != 1:
            raise PanelMergeError(f"{panel['cas']}: pre-edit {old!r} not found once on line {line_no}")
        lines[line_no - 1] = lines[line_no - 1].replace(old, new)
    return "\n".join(lines)


def check_orig(panel: dict) -> str:
    """校验用原文：改前文字 → 已定改字（pre_edits）→ 口径3 规范化。"""
    return normalize_resonance(_pre_edited(panel))


def _drops(panel: dict) -> list[dict]:
    return [dict(line=line, resonance=token) for line, token in panel["drops"]]


def _shared_problems(panel: dict, orig: str, result: dict) -> tuple[list[str], set[str]]:
    """作者定稿的同值合写：该新行的数值 = 各来源同一数值合写一次（其余数值逐一保留）。返回 (问题, 允许的 check 报错)。"""
    problems, allowed = [], set()
    if not panel["shared"]:
        return problems, allowed
    column = result["columns"][0]
    lines = [PMC._core(line) for line in PMC._split(orig)]
    merged = [PMC._core(line) for line in panel["after"]]
    for line_no, token in panel["shared"]:
        sources = [i for i, j in column["mapping"].items() if j == line_no]
        want = sum((PMC._signed(lines[i - 1]) for i in sources), Counter())
        got = PMC._signed(merged[line_no - 1])
        if len(sources) < 2 or got[token] != 1 or want[token] != len(sources) \
                or any(PMC._signed(lines[i - 1])[token] != 1 for i in sources) \
                or +(want - Counter({token: want[token]})) != +(got - Counter({token: 1})):
            problems.append(f"shared value {token} on line {line_no}: sources {sources} want {dict(want)} "
                            f"got {dict(got)}")
        allowed.add(f"[列1] 新文案第{line_no}行效果数值多重集合不一致：应 {dict(want)} 实 {dict(got)}")
    allowed.add("[列1] 全文效果数值多重集合改变")
    return problems, allowed


def text_problems(panel: dict) -> list[str]:
    before, after = "\n".join(panel["before"]), "\n".join(panel["after"])
    orig = check_orig(panel)
    problems = []
    if panel["mode"] == "split":
        expected = [line for source in orig.split("\n") for line in expand_split(source, panel["rewrites"])]
        if list(panel["after"]) != expected:
            problems.append(f"split: after != mechanical expansion {expected}")
        if len(panel["after"]) <= len(panel["before"]):
            problems.append("split: nothing split")
    else:
        result = merge_check(orig, after, _drops(panel))
        shared, allowed = _shared_problems(panel, orig, result)
        problems += shared + [f"merge: {e}" for e in result["errors"] if e not in allowed]
        kinds = set(result["columns"][0]["kinds"].values()) if result["columns"] else set()
        if panel["mode"] == "merge" and ("merge" not in kinds or len(panel["after"]) >= len(panel["before"])):
            problems.append("nothing merged")
        if panel["mode"] == "edit" and (after != orig or "merge" in kinds):
            problems.append("edit panel must equal the pre-edited, normalised original line for line")
    if after == before:
        problems.append("nothing changed")
    problems += [f"panel: {p}" for p in kit_panel_problems(after)]
    problems += [f"forbidden {w!r}" for w in FORBIDDEN if w in after]
    if "迟缓" in after:                     # 作者 2026-09-27：索恩「迟缓」改「冻结」（客户端与数据都叫冻结）
        problems.append("「迟缓」 must read 「冻结」")
    problems += [f"R2: {word!r} must name the skill" for word in R2_BANNED if word in after]
    if re.search(r"属性共鸣时[：:]", after):
        problems.append("口径3: 「X属性共鸣时：」 must read 「X属性共鸣时，」")
    for line in panel["after"]:
        if "<icon" in line and not line.startswith(MAIN_ICON):
            problems.append(f"icon prefix must be exactly {MAIN_ICON!r}: {line}")
    return problems


def generator_text(cid: str, panel: dict, rows: list[list[str]]) -> str | None:
    """代码生成器现算的面板（小 Boss：队长面板从战斗行现算、能力面板取 ``wf_miniboss_text.TEXTS``）；
    其余角色由测试核对 kit / 设计镜像。"""
    if cid not in MINIBOSS:
        return None
    if panel["kind"] == "leader":
        from wf_miniboss_package import _leader_text
        return _leader_text(rows)
    from wf_miniboss_text import ability_panel_text
    return ability_panel_text(cid, int(panel["key"][len(cid):]))


def line_mapping(panel: dict) -> dict[int, list[int]]:
    """新文案行号 → 原文行号（1 起）。拆行面板按展开位次反推。"""
    if panel["mode"] == "split":
        out, j = {}, 1
        for i, source in enumerate(check_orig(panel).split("\n"), 1):
            for _ in expand_split(source, panel["rewrites"]):
                out[j] = [i]
                j += 1
        return out
    mapping = merge_check(check_orig(panel), "\n".join(panel["after"]), _drops(panel))["columns"][0]["mapping"]
    return {j: sorted(i for i, jj in mapping.items() if jj == j) for j in sorted(set(mapping.values()))}


# ====================================================================== 修订


def revise_unit(cid: str, read: Callable[[str, Any], Any]) -> dict:
    inputs = _baseline(cid, read)
    code, name, package, version = identity(cid)
    cas, notes, problems = {}, [], []
    census = state_sources(cid, inputs) if cid in CENSUS else None
    status_evidence = None
    if cid in SKILL_STATUS:
        found, status_evidence = skill_status_problems(cid, inputs)
        problems += [f"{SKILL_STATUS[cid]['cas']}: {p}" for p in found]
    skill_text, text_evidence, desc_texts = {}, None, []
    if cid in SKILL_TEXT:                       # 主会话 C：技能强化条目 + 技能说明「迟缓」→「冻结」
        found, text_evidence = skill_text_problems(cid, inputs)
        problems += [f"skill text: {p}" for p in found]
        skill_text = skill_text_outputs(cid, inputs)
        cas.update(skill_text["cas"])
        columns = SKILL_TEXT[cid]["text_columns"]
        desc_texts = ([rows[0][c] for rows in skill_text["text"].values() for c in columns]
                      + [rows[0][c] for rows in skill_text["server_text"].values() for c in columns]
                      + [fields[1] for actions in skill_text["action"].values() for _, fields in actions])
    flag_evidence = None
    if cid in FLAG_TEXT:                        # R2：强化串改官方格式（索恩接在主会话 C 的「冻结」稿之后）
        spec = FLAG_TEXT[cid]
        key = spec["string"]
        current = cas[key][0][0] if key in cas else _single_text(inputs["cas", key], key)
        found, flag_evidence = flag_problems(cid, inputs, current)
        problems += [f"skill flag: {p}" for p in found + auto_panel_problems(cid, read)]
        cas[key] = [[spec["after"]]]
    trim, trim_evidence = {}, None
    if cid in DESC_TRIM:                        # R3：技能说明删掉旗号开支那一段（冰雪罗尔夫）
        found, trim_evidence = desc_trim_problems(cid, inputs)
        problems += [f"skill description: {p}" for p in found]
        trim = desc_trim_outputs(cid, inputs)
        columns = DESC_TRIM[cid]["text_columns"]
        desc_texts += ([rows[0][c] for rows in trim["text"].values() for c in columns]
                       + [rows[0][c] for rows in trim["server_text"].values() for c in columns]
                       + [fields[1] for actions in trim["action"].values() for _, fields in actions])
    flag_keys = set(cas_changes(cid))
    if not flag_keys <= set(cas):
        raise PanelMergeError(f"{cid}: skill-flag strings {sorted(flag_keys - set(cas))} were not produced")
    flag_texts = [cas[key][0][0] for key in sorted(flag_keys)]
    for text in flag_texts:
        problems += [f"skill flag: {p}" for p in kit_panel_problems(text, skill_flag=True)]
        problems += [f"skill flag: {word!r} must name the skill: {text}" for word in R2_BANNED if word in text]
    for text in flag_texts + desc_texts:
        problems += [f"skill text: {p}" for p in kit_panel_problems(text)]
        if cid in SKILL_TEXT and SKILL_TEXT[cid]["old"] in text:
            problems.append(f"skill text: 「{SKILL_TEXT[cid]['old']}」 must read 「{SKILL_TEXT[cid]['new']}」: {text}")
    for panel in unit_panels(cid):
        live = _single_text(inputs["cas", panel["cas"]], panel["cas"])
        if live != "\n".join(panel["before"]):
            raise PanelMergeError(f"{panel['cas']}: live panel differs from the reviewed text")
        rows = inputs[panel["kind"], panel["key"]]
        if rows[0][0] != panel["cas"][len("desc_override_"):]:
            raise PanelMergeError(f"{panel['cas']}: key is not desc_override_ + first-row string_id {rows[0][0]}")
        problems += [f"{panel['cas']}: {p}" for p in check_rows(panel, rows) + text_problems(panel)]
        for number, line in enumerate(panel["after"], 1):          # R2：强化条目只能是登记过、与强化串同文的那一行
            if "强化『" in line or ("为『" in line and "追加" in line):
                spec = FLAG_TEXT.get(cid)
                if spec is None or (spec["panel"], spec["line"]) != (panel["cas"], number):
                    problems.append(f"{panel['cas']} line {number}: skill-enhancement line is not registered "
                                    f"in FLAG_TEXT: {line}")
        after = "\n".join(panel["after"])
        generated = generator_text(cid, panel, rows)
        if generated is not None and generated != after:
            problems.append(f"{panel['cas']}: miniboss generator differs from the revision")
        cas[panel["cas"]] = [[after]]
        warnings = ([] if panel["mode"] == "split"
                    else merge_check(check_orig(panel), after, _drops(panel))["warnings"])
        notes.append(dict(
            key=panel["cas"], panel=panel["panel"], table=f"{panel['kind']}:{panel['key']}", mode=panel["mode"],
            row_groups=[list(g) for g in panel["groups"]], effect_kinds=[list(k) for k in panel["kinds"]],
            line_mapping={str(k): v for k, v in line_mapping(panel).items()},
            resonance_dropped_lines=[line for line, _ in panel["drops"]],
            pre_edits=[dict(line=line, old=old, new=new) for line, old, new in panel["pre_edits"]],
            resonance_colon_normalised=_pre_edited(panel) != check_orig(panel),
            shared_values=[dict(line=line, value=token) for line, token in panel["shared"]],
            split_rewrites=[dict(old=old, new=new) for old, new in panel["rewrites"]],
            before=list(panel["before"]), after=list(panel["after"]),
            existing_warnings=warnings))
    if problems:
        raise PanelMergeError("; ".join(problems))
    for key in cas:
        flag = key.startswith("change_skill_" + code) and key in flag_keys
        if not (key.startswith("desc_override_" + code) or flag):
            raise PanelMergeError(f"{key}: outside the candidate namespace desc_override_{code} / change_skill_{code}")
        want = [] if flag else [PANEL_CAPABILITY]
        if legality.required_client_capabilities(legality.CUSTOM_ABILITY_STRING_KIND, [key]) != want:
            raise PanelMergeError(f"{key}: unexpected capability requirement")
    return {
        "ability": {}, "leader": {}, "cas": cas, "text": {**skill_text.get("text", {}), **trim.get("text", {})},
        "table": {}, "action": {**skill_text.get("action", {}), **trim.get("action", {})}, "dsl": {},
        "server_text": {**skill_text.get("server_text", {}), **trim.get("server_text", {})}, "new_programs": [],
        "notes": {
            "source": SOURCE, "character": f"{cid} {code} {name}",
            "spec": ("作者 2026-09-27：同一条件的提升写到一起；状态获取带 X 共鸣时其提供的效果不再写 X 共鸣；"
                     "索恩能力4 合成一句并改冻结、能力1 迟缓改冻结。主会话口径1/3/5/7；主会话 C 索恩技能文字迟缓→冻结、"
                     "F 索恩能力2 冒号；作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要"
                     "重复描述强化后的效果,规范并简化描述」⇒ 主会话口径 R1–R4（强化条目官方格式、面板行与强化串同文；"
                     "技能说明只写本体，冰雪罗尔夫删强化段）"),
            "panels": notes,
            "state_census": census,
            "skill_status": status_evidence,
            "skill_flag": None if cid not in FLAG_TEXT else dict(
                string=FLAG_TEXT[cid]["string"], before=cas_changes(cid)[FLAG_TEXT[cid]["string"]][0],
                after=FLAG_TEXT[cid]["after"], panel=FLAG_TEXT[cid]["panel"], line=FLAG_TEXT[cid]["line"],
                evidence=flag_evidence,
                skill_description=("R3：技能说明五处删掉旗号开支那一段，见 desc_trim" if cid in DESC_TRIM else
                                   "R3：技能说明（action c1 / character_text c5·c7 / 服务端镜像）没有强化后的描述，"
                                   "R2 不动它（索恩的「迟缓」→「冻结」见 skill_text）")),
            "desc_trim": None if cid not in DESC_TRIM else dict(
                removed=DESC_TRIM[cid]["removed"], before=DESC_TRIM[cid]["desc"][0], after=DESC_TRIM[cid]["desc"][1],
                text_columns=list(DESC_TRIM[cid]["text_columns"]), action_levels=list(DESC_TRIM[cid]["levels"]),
                evidence=trim_evidence),
            "skill_text": None if cid not in SKILL_TEXT else dict(
                old=SKILL_TEXT[cid]["old"], new=SKILL_TEXT[cid]["new"],
                cas=sorted(skill_text["cas"]), text_columns=list(SKILL_TEXT[cid]["text_columns"]),
                action_levels=list(SKILL_TEXT[cid]["levels"]), dsl_statuses=text_evidence,
                before=SKILL_TEXT[cid]["desc"][0], after=SKILL_TEXT[cid]["desc"][1]),
            "combat_rows_modified": False,
            "server_text": ("技能说明 [5]/[7]「迟缓」→「冻结」，与 character_text c5/c7、action_skill 两档 c1 同值"
                            if cid in SKILL_TEXT else
                            "技能说明 [5]/[7] 删掉旗号开支那一段，与 character_text c5/c7、action_skill 两档 c1 同值"
                            if cid in DESC_TRIM else
                            "assets/cdndata/character_text.json 只有名称/简介/技能等 12 列，无面板文案，不改"),
            "generator": GENERATOR_NOTE.get(cid, "wf_miniboss_package._leader_text（同条件合并）== revise()"),
            "candidate": (f"work/character_packs/{package} → {version}；desc_override 键由 stage_batch.Plan.splice "
                          "按 desc_override_<code> 前缀自动补认领"
                          + ("；change_skill 串、character_text、action_skill 候选已认领，服务端镜像走 "
                             "Plan.server_text" if cid in SKILL_TEXT or cid in DESC_TRIM else "")
                          + ("；change_skill 串已认领或按 change_skill_<code> 前缀自动认领"
                             if cid in FLAG_TEXT and cid not in SKILL_TEXT and cid not in DESC_TRIM else "")),
            "capabilities": unit_capabilities(cid),
            "runtime_verified": False,
        },
    }


GENERATOR_NOTE = {
    "119989": ("wf_campus_panel_text._BIANCA['a1'] / ['a3'] + native_flat_string_rows"
               "（change_skill_lady_summoner_campus_dragon）== revise()"),
    "119991": ("design/nicola.json texts（含 change_skill_sorceress_teacher_moon）+ rework1/panel/nicola.json"
               "（能力1 第2行、能力3；sync_mirrors）== revise()"),
    "119992": "design/mia.json texts + leader_ability.desc_override（sync_mirrors）== revise()",
    "129987": ("design/ghandagoza.json texts（含 change_skill_ghandagoza、desc_override_ghandagoza_6；sync_mirrors）"
               "== revise()"),
    "149994": "wf_miniboss_package._leader_text（同条件合并）+ wf_miniboss_text.TEXTS 能力3（口径5 拆行）== revise()",
    "159994": ("wf_midautumn_kit_thorn.PANEL_ABILITY[1]/[2]/[3]/[4] + CHANGE_SKILL_TEXT（R2 稿）+ design/thorn.json"
               "（plan.texts 与顶层 texts.desc1/desc2 → spec.texts → tables 步写 character_text c5/c7、action_skill c1）"
               " + rework1/panel/thorn.json == revise()"),
    "169993": "wf_miniboss_package._leader_text（同条件合并）+ wf_miniboss_text.TEXTS 能力1（口径5 拆行）== revise()",
    "129992": "wf_gerald_r2_data.ABILITY3（ability3() 接受 live 改前稿、输出 R2 稿）== revise()",
    "139992": ("wf_midautumn_kit_charlene.CAS_TEXTS + design/charlene.json（plan.texts）与 rework1/panel/charlene.json"
               "（能力1 第2行；sync_mirrors）== revise()"),
    "159995": ("wf_midautumn_kit_stinel.CAS_TEXTS + design/stinel.json（plan.texts）与 rework1/panel/stinel.json"
               "（能力1 第2行，自动面板前缀照旧；sync_mirrors）== revise()"),
    "179999": ("无生成器（wf_balance_20260927_rolfwt26 注明技能树与文案由一次性装配落盘）；"
               "强化串与技能说明以本模块为准"),
}


def unit_capabilities(cid: str) -> list[str]:
    """覆盖面板键需要面板补丁能力；只改 change_skill 串 / 技能说明的角色不需要任何 capability。"""
    return [PANEL_CAPABILITY] if unit_panels(cid) else []

# ====================================================================== 设计镜像（work/，gitignored）

BATCH = Path("work/character_packs/midautumn-20260920")
MIRRORS = {
    "nicola_design": BATCH / "design/nicola.json",
    "nicola_panel": BATCH / "rework1/panel/nicola.json",
    "mia_design": BATCH / "design/mia.json",
    "thorn_design": BATCH / "design/thorn.json",
    "thorn_panel": BATCH / "rework1/panel/thorn.json",
    "ghandagoza_design": BATCH / "design/ghandagoza.json",
    "charlene_design": BATCH / "design/charlene.json",
    "charlene_panel": BATCH / "rework1/panel/charlene.json",
    "stinel_design": BATCH / "design/stinel.json",
    "stinel_panel": BATCH / "rework1/panel/stinel.json",
}
#: 技能强化条目规范新增角色的设计镜像：{名: (角色, 面板镜像里开关那一行所在的能力槽, 该行前缀)}。
#: 设计稿 plan.texts.custom_ability_string 的强化串 == kit ``CAS_TEXTS``；面板镜像那一行保留各自原有写法——夏琳原本就是
#: 强化串原文（无前缀），丝缇涅尔是「持有者为主位且光属性共鸣时：」+ 强化串（自动面板预览）。
FLAG_MIRRORS = {
    "charlene": ("139992", 1, ""),
    "stinel": ("159995", 1, "持有者为主位且光属性共鸣时："),
}
FLAG_MIRROR_BLOCK = dict(
    spec="作者 2026-09-27「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,…规范并简化描述」"
         "⇒ 主会话 R2：技能强化条目官方格式、点明技能名、不写开关条件与数字",
    module=SOURCE,
)
MIRROR_BLOCK = dict(
    spec="作者 2026-09-27：同一个条件的提升写到一起；状态获取带 X 共鸣时其提供的效果不写 X 共鸣（第三轮面板合并）",
    module=SOURCE,
)
#: 索恩三块面板在镜像里的改动说明。
THORN_CHANGES = {
    "desc_override_tweyen_light_1": ("第2行「迟缓」→「冻结」（作者）、「光属性共鸣时：」→「，」（口径3）；"
                                     "第2行强化条目点明『星之猎手』，与 change_skill_tweyen_light 同文（R2）"),
    "desc_override_tweyen_light_2": "「光属性共鸣时：」→「，」（口径3，主会话 F；光共鸣是真实数据前置，保留）",
    "desc_override_tweyen_light_3": ("第2、3行合并（同触发、同限 10 次）；第4、5行「光属性共鸣时：」→「，」（口径3）；"
                                     "第4行去「强化技能，」（R1：能力3 没有开关行）"),
    "desc_override_tweyen_light_4": "两行合成一句并改冻结（作者二选一定稿，同值＋15%只写一次）",
}
#: 索恩面板以外的改字（主会话 C，见 :data:`SKILL_TEXT`）在镜像里的说明。
THORN_TEXT_CHANGES = (
    "change_skill_tweyen_light：「迟缓效果」→「冻结效果」（主会话 C；技能 DSL 开关分支是 ACFrozen），再改官方格式"
    "「强化『星之猎手』：赋予的麻痹效果、冻结效果持续时间大幅延长」（R2）",
    "技能说明 texts.desc1 / desc2（→ character_text c5/c7、action_skill 两档 c1、服务端镜像）与 "
    "plan.texts.action_skill_desc.value：「＋迟缓效果＋」→「＋冻结效果＋」（主会话 C；命中块 ACFrozen）",
)


def _strip_icon(line: str) -> str:
    return line[len(MAIN_ICON):] if line.startswith(MAIN_ICON) else line


def _set_cas_text(design: dict, key: str, text: str) -> None:
    rows = [row for row in design["plan"]["texts"]["custom_ability_string"]["rows"] if row["key"] == key]
    if len(rows) != 1:
        raise PanelMergeError(f"design mirror lacks {key}")
    rows[0]["text"] = text


def _merge_panel_lines(entry: dict, panel: dict) -> None:
    """rework1/panel/*.json 的一个能力块：按登记的行映射把 lines 变成改后的样子（保留每行其余字段）。"""
    old = [line["text"] for line in entry["lines"]]
    new = [_strip_icon(line) for line in panel["after"]]
    if old == new:
        return
    # 上一版合并稿（口径3 之前 / R2 之前，:data:`PREVIOUS_AFTER`）：与现稿行数相同，逐行改成现稿。
    previous = [_strip_icon(line) for line in PREVIOUS_AFTER.get(panel["cas"], panel["after"])]
    if len(previous) == len(new) and [normalize_resonance(text) for text in old] in (previous, new):
        for line, text in zip(entry["lines"], new):
            line["text"] = text
        return
    if old != [_strip_icon(line) for line in panel["before"]]:
        raise PanelMergeError(f"panel mirror for {panel['cas']} differs from the live panel")
    lines = []
    for new_index, sources in sorted(line_mapping(panel).items()):
        text = panel["after"][new_index - 1]
        line = deepcopy(entry["lines"][sources[0] - 1])
        line["text"] = _strip_icon(text)
        if len(sources) > 1:
            line[MODULE_TAG] = f"原第{'、'.join(map(str, sources))}行同条件合并"
        lines.append(line)
    entry["lines"] = lines


def _reword(text: str, before: str, after: str, label: str, *, also: tuple[str, ...] = ()) -> str:
    """镜像里的一段文字：== 改前（或 ``also`` 里登记的中间稿）或已 == 改后 ⇒ 改后；其余（被别处改过）拒绝。"""
    if text in (before, after, *also):
        return after
    raise PanelMergeError(f"{label}: mirror text differs from both the live and the revised text: {text!r}")


def _flag_mirror_text(design: dict, cid: str, label: str) -> None:
    """设计镜像里的强化串（plan.texts.custom_ability_string）：live / 中间稿（主会话 C）/ 现稿 ⇒ 现稿。"""
    for key, (before, after) in cas_changes(cid).items():
        rows = [row for row in design["plan"]["texts"]["custom_ability_string"]["rows"] if row["key"] == key]
        if len(rows) != 1:
            raise PanelMergeError(f"{label} design mirror lacks {key}")
        middle = tuple(pair[1] for k, pair in SKILL_TEXT.get(cid, {}).get("cas", {}).items() if k == key)
        rows[0]["text"] = _reword(rows[0]["text"], before, after, f"{label} design {key}", also=middle)


def _thorn_skill_text(design: dict, panel_doc: dict) -> None:
    """主会话 C：design/thorn.json 的技能说明生成源（顶层 texts.desc1 / desc2）、plan.texts.action_skill_desc.value、
    change_skill 串（再接 R2 官方格式），以及 rework1/panel/thorn.json 技能块的状态那一行。"""
    spec = SKILL_TEXT["159994"]
    before, after = spec["desc"]
    for name in ("desc1", "desc2"):
        design["texts"][name] = _reword(design["texts"][name], before, after, f"thorn design texts.{name}")
    block = design["plan"]["texts"]["action_skill_desc"]
    block["value"] = _reword(block["value"], before, after, "thorn design plan.texts.action_skill_desc")
    _flag_mirror_text(design, "159994", "thorn")
    old_phrase = spec["hit_phrase"].replace(spec["new"], spec["old"])
    lines = [line for line in panel_doc["skill"]["lines"] if line["text"] in (old_phrase, spec["hit_phrase"])]
    if len(lines) != 1:
        raise PanelMergeError("thorn panel mirror skill block lacks the status line")
    lines[0]["text"] = spec["hit_phrase"]


def _panel_entry(doc: dict, index: int, label: str) -> dict:
    entry = [e for e in doc["abilities"] if int(e["index"]) == index]
    if len(entry) != 1:
        raise PanelMergeError(f"{label} panel mirror lacks ability {index}")
    return entry[0]


def mirror_updates(docs: dict) -> dict:
    """按本轮改动重算设计镜像（纯函数、幂等）；docs 键见 :data:`MIRRORS`。"""
    docs = deepcopy(docs)
    nicola = PANELS_BY_CAS["desc_override_sorceress_teacher_moon_3"]
    mia = PANELS_BY_CAS["desc_override_tiger_treasure_hunter_moon"]
    thorn = [PANELS_BY_CAS[key] for key in THORN_CHANGES]
    ghand = (PANELS_BY_CAS["desc_override_ghandagoza"], PANELS_BY_CAS["desc_override_ghandagoza_4"],
             PANELS_BY_CAS["desc_override_ghandagoza_6"])
    nicola_flag = FLAG_TEXT["119991"]["string"]
    ghand_flag = FLAG_TEXT["129987"]["string"]

    design = docs["nicola_design"]
    plain = "\n".join(_strip_icon(line) for line in nicola["after"])
    _set_cas_text(design, nicola["cas"], plain)
    override = design["plan"]["texts"].get("desc_override", {}).get("value")
    if isinstance(override, dict) and nicola["cas"] in override:
        override[nicola["cas"]] = plain
    _flag_mirror_text(design, "119991", "nicola")
    design[MODULE_TAG] = dict(MIRROR_BLOCK, changed=[
        f"{nicola['cas']}：第3、4行合并；第2行省略火属性共鸣（月讲）；第1行冒号→逗号",
        f"{nicola_flag}：点明『月相夜讲』，改官方格式（R2）"])
    _merge_panel_lines(_panel_entry(docs["nicola_panel"], 3, "nicola"), nicola)
    lines = [line for line in _panel_entry(docs["nicola_panel"], 1, "nicola")["lines"]
             if line["text"] in NICOLA_PANEL_LINE]
    if len(lines) != 1:
        raise PanelMergeError("nicola panel mirror ability 1 lacks the skill-switch line")
    lines[0]["text"] = NICOLA_PANEL_LINE[1]
    docs["nicola_panel"][MODULE_TAG] = dict(MIRROR_BLOCK, changed=[
        "能力3：第3、4行合并；第2行省略火属性共鸣；第1行冒号→逗号",
        f"能力1：第2行（客户端自动面板的镜像）强化内容 = {nicola_flag}（R2）"])

    design = docs["mia_design"]
    text = "\n".join(mia["after"])
    _set_cas_text(design, mia["cas"], text)
    block = design["plan"].get("leader_ability", {}).get("desc_override")
    if isinstance(block, dict) and "value" in block:
        block["value"] = text
    design[MODULE_TAG] = dict(MIRROR_BLOCK, changed=[f"{mia['cas']}：第1–3行合并"])

    design = docs["thorn_design"]
    for panel in thorn:
        _set_cas_text(design, panel["cas"], "\n".join(panel["after"]))
        _merge_panel_lines(_panel_entry(docs["thorn_panel"], int(panel["key"][-1]), "thorn"), panel)
    _thorn_skill_text(design, docs["thorn_panel"])
    design[MODULE_TAG] = dict(MIRROR_BLOCK, changed=[f"{key}：{why}" for key, why in THORN_CHANGES.items()]
                              + list(THORN_TEXT_CHANGES))
    docs["thorn_panel"][MODULE_TAG] = dict(MIRROR_BLOCK, changed=[
        f"能力{key[-1]}：{why}" for key, why in THORN_CHANGES.items()] + list(THORN_TEXT_CHANGES))

    design = docs["ghandagoza_design"]
    for panel in ghand:
        _set_cas_text(design, panel["cas"], "\n".join(panel["after"]))
    _flag_mirror_text(design, "129987", "ghandagoza")
    design[MODULE_TAG] = dict(MIRROR_BLOCK, changed=[
        "desc_override_ghandagoza：第1、2行合并（强化弹射伤害不补对象，与前项用「，」隔开，口径1）",
        "desc_override_ghandagoza_4：两行合并，去「的」",
        "desc_override_ghandagoza_6：第1行强化条目补上强化内容，与强化串同文（R2）",
        f"{ghand_flag}：删「，并强化「独立乘区伤害提升效果」」（R2：旗号只强化攻击力 / 强化弹射伤害，"
        "独立乘区＋91.7% 是能力6 #1 的数值行，面板第2行另写）"])

    for name, (cid, slot, prefix) in FLAG_MIRRORS.items():
        spec = FLAG_TEXT[cid]
        design, panel_doc = docs[f"{name}_design"], docs[f"{name}_panel"]
        _flag_mirror_text(design, cid, name)
        lines = [line for line in _panel_entry(panel_doc, slot, name)["lines"]
                 if line["text"] in (prefix + spec["before"], prefix + spec["after"])]
        if len(lines) != 1:
            raise PanelMergeError(f"{name} panel mirror ability {slot} lacks the skill-switch line")
        lines[0]["text"] = prefix + spec["after"]
        change = f"{spec['string']}：官方格式，点明『{spec['skill']}』，不写开关条件与数字（R2）"
        design[MODULE_TAG] = dict(FLAG_MIRROR_BLOCK, changed=[change])
        panel_doc[MODULE_TAG] = dict(FLAG_MIRROR_BLOCK, changed=[f"能力{slot}：第2行（自动面板的镜像）{change}"])
    return docs


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """保留原文件的缩进、换行风格与末尾有无换行。"""
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    second = raw.split(b"\n", 2)[1]
    indent = len(second) - len(second.lstrip(b" "))
    text = json.dumps(value, ensure_ascii=False, indent=indent or 2)
    if raw.endswith(b"\n"):
        text += "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def sync_mirrors(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回设计镜像；返回有变化的相对路径。"""
    root = Path(root)
    before = {name: _load(root / rel) for name, rel in MIRRORS.items()}
    after = mirror_updates(before)
    changed = [MIRRORS[name].as_posix() for name in MIRRORS if before[name] != after[name]]
    if write:
        for name in MIRRORS:
            if before[name] != after[name]:
                _save(root / MIRRORS[name], after[name])
    return changed


# ====================================================================== 导出

UNITS = [dict(CID=cid, CODE=identity(cid)[0], NAME=identity(cid)[1],
              PACKAGES=[identity(cid)[2]], PACKAGE_VERSION={identity(cid)[2]: identity(cid)[3]},
              CAPABILITIES=unit_capabilities(cid), REVIEWED_DRIFT={},
              BEFORE={item: BEFORE[item] for item in unit_inputs(cid) if item in BEFORE},
              revise=partial(revise_unit, cid))
         for cid in UNIT_ORDER]


if __name__ == "__main__":
    import sys
    here = Path(__file__).resolve().parent
    pass  # Imports resolve from this checkout/package, not external source copies.
    changed = sync_mirrors(here.parent, write="--write" in sys.argv[1:])
    print(json.dumps({"changed": changed, "write": "--write" in sys.argv[1:]}, ensure_ascii=False))

# -*- coding: utf-8 -*-
"""2026-09-27 第三轮面板（wf_balance_20260927c_panels）：非第三轮角色 28 块覆盖面板（同条件合并 / 口径1·3·5 / 索恩作者定稿）
+ 索恩技能文字「迟缓」→「冻结」（主会话 C：技能强化条目、character_text c5/c7、action_skill 两档 c1、服务端镜像）
+ 技能强化文案 R1–R4（作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的
效果,规范并简化描述」）：四条 change_skill 强化串改官方格式、覆盖面板开关行与强化串同文、索恩能力3 去「强化技能，」。

fixture = live 输入快照（``fixtures/balance_20260927c_panels.json``，extra5 stage_batch.make_read(live_only=True)，
链尾 1.4.1054）。断言：每块面板逐字（独立写在本文件）、仓库校验器 ``wf_panel_merge_check.check`` 全绿（原文先按
本文件**显式写出**的已定改字与口径3 规范化处理）、拆行面板 == 同位展开、BEFORE 漂移逐项拒绝、不改输入、未合并行逐字
不变、数据同条件锁 / 拆行锁 / 同值合写锁与共鸣省略、技能状态普查（正反例）、索恩技能文字逐字 + DSL 状态集合依据（正反例）、
生成器一致（小 Boss ``_leader_text`` 与 ``ability_panel_text`` / 校园面板 / 索恩 kit 与 tables 步 / 设计镜像）、
候选命名空间与干跑（缺 work/ 时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927c_panels as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_panel_merge_check as PMC  # noqa: E402
from wf_panel_merge_check import check  # noqa: E402
from wf_midautumn_kitlib import panel_problems  # noqa: E402
from wf_miniboss_roster import BY_ID as MINIBOSS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927c_panels.json"
ICON = " <icon id='main'>  "

#: 改后面板逐字（主会话合并稿 + 已定小项 + 口径1/3/5 + 索恩作者定稿）。
EXPECTED = {
    "desc_override_lady_summoner_campus_1":                             # R2：第2行 = 火共鸣前缀 + 强化串 + 「。」
        f"{ICON}战斗开始时：自身技能槽+50%。\n"
        f"{ICON}火属性共鸣时，强化『绯焰实习·幼龙点名』：幼龙吐息降低全场敌人的能力伤害抗性。\n"
        f"{ICON}火属性共鸣时，每次获得「幼龙吐息」，自身技能槽+20%，赋予队长攻击力提升200%效果，持续15秒。",
    "desc_override_lady_summoner_campus_3":
        f"{ICON}火属性共鸣时，Fever模式中，火属性角色技能槽上限+20%。\n"
        f"{ICON}火属性共鸣时，Fever模式中，每经过2秒，队长技能槽+5%，自身获得1层「焰域研修」。\n"
        f"{ICON}Fever模式中，每层「焰域研修」使火属性角色能力伤害+50%、能力伤害额外乘区+1%。\n"
        f"{ICON}Fever结束或自身倒下时，「焰域研修」清空。",
    "desc_override_sorceress_teacher_moon_3":
        f"{ICON}火属性共鸣时，自身技能槽每达到100%，自身获得1层「月讲」状态\n"
        f"{ICON}除自身外的火属性角色发动技能时，消耗1层「月讲」，使该角色技能槽＋10%、攻击力＋50%，"
        "同时自身技能槽上限＋5%、技能充能速度＋5%（可叠加）\n"
        f"{ICON}火属性共鸣时，火属性角色对处于抗性降低状态的敌人，攻击力＋300%、技能伤害＋300%，"
        "对敌人的技能额外伤害乘区＋15%",
    "desc_override_tiger_treasure_hunter_moon":
        "火属性共鸣时，火属性角色攻击力＋250%，自身强化弹射伤害＋200%、强化弹射所需连击数－6\n"
        "火属性共鸣时，每次弹射追加6连击\n"
        "火属性共鸣时，每发动2次强化弹射，赋予自身「连击加成」：弹射时连击＋10（持续3次弹射）\n"
        "每发动1次强化弹射Lv3，火属性角色攻击力＋10%（最多10次）\n"
        "火属性共鸣时，持有「桂灯」的状态下每发动3次强化弹射，消耗3盏「桂灯」并放出追击『开匣·月华』，"
        "对周围的敌人造成火属性伤害（以强化弹射伤害计算）",
    "desc_override_cobra_playable": "赋予全队(火) 攻击力 80%、减益攻击特攻 60%、技能伤害 100%、HP 15%。",
    "desc_override_haniwa_playable": "赋予全队(火) 攻击力 80%、直接攻击伤害 140%、HP 15%，自身 强化弹射伤害 80%。",
    "desc_override_dog_soldier_playable":
        "赋予全队(火) 攻击力 100%、HP 20%，自身 强化弹射伤害 120%。\n技能发动≥1 → 自身 追加连击 5。",
    "desc_override_ghandagoza":
        "水属性角色攻击力＋300%，强化弹射伤害＋300%\n"
        "水属性共鸣时，水属性角色获得治疗量＋10%；战斗开始时，水属性角色技能槽＋100%",
    "desc_override_ghandagoza_4": "水属性角色气绝蓄积＋50%、对气绝中的敌人伤害＋10%、对麻痹中的敌人伤害＋10%",
    "desc_override_ghandagoza_6":                                       # R2：第1行 = 强化串（无前置）
        f"{ICON}强化『炎天呑舟正拳突击』的「攻击力提升＋强化弹射伤害提升效果」\n"
        f"{ICON}『炎天呑舟正拳突击』生效期间，水属性角色的独立乘区伤害进一步＋91.7%",
    "desc_override_killer_whale_playable": "赋予全队(水) 攻击力 80%、技能伤害 100%、冻结特攻 30%、技能槽 30%。",
    "desc_override_haniwa_blue_playable":
        "赋予全队(水) 攻击力 80%、直接攻击伤害 100%、攻击力↑延长 20%、技能槽 30%。",
    "desc_override_wander_armor_water_playable": "赋予全队(水) 攻击力 80%、技能伤害 80%、抗性火 20%、HP 20%。",
    "desc_override_clione_playable": "赋予全队(水) 攻击力 80%、直接攻击伤害 120%、获得的治疗量 15%、HP 20%。",
    "desc_override_ghost_girl_playable": "赋予全队(水) 攻击力 100%、技能伤害 120%、技能槽 30%、冻结特攻 30%。",
    "desc_override_cube_boss_playable":
        "赋予全队(雷) 攻击力 100%、固有技能特攻 60%、技能槽 30%，自身 强化弹射伤害 120%。\n强化弹射替换为角色专属形态。",
    "desc_override_big_bear_monster_playable":
        "赋予全队(风) 攻击力 100%、直接攻击伤害 100%、攻击力↑延长 20%、HP 15%。",
    "desc_override_wander_armor_wind_playable":
        "赋予全队(风) 攻击力 80%、技能槽 30%，自身 浮游延长 20%。\n持续·状态浮游 → 赋予全队(风) 直接攻击伤害 140%。",
    "desc_override_haniwa_green_playable":
        "赋予全队(风) 攻击力 80%、技能伤害 100%、HP 25%、抗性全属性 10%。\n强化弹射替换为角色专属形态。",
    "desc_override_one_eyed_rabbit_playable":
        "赋予全队(风) 攻击力 100%、直接攻击伤害 140%、技能槽 30%，自身 贯穿延长 20%。",
    "desc_override_one_eyed_rabbit_playable_3":
        f"{ICON}Lv1强化弹射时，追加Lv1爪刃追击。\n"
        f"{ICON}Lv2强化弹射时，追加Lv2爪刃追击。\n"
        f"{ICON}Lv3强化弹射时，追加Lv3爪刃追击。\n"
        f"{ICON}贯穿效果中，风属性角色直接攻击造成的伤害+15%（独立乘区），强化弹射伤害+100%。",
    "desc_override_tweyen_light_1":
        "战斗开始时：自身技能槽立即＋50%\n"
        "光属性共鸣时，强化『星之猎手』：赋予的麻痹效果、冻结效果持续时间大幅延长\n"
        "光属性角色减益技能特攻＋40%",
    "desc_override_tweyen_light_2": "光属性共鸣时，敌人身上每有1个弱体效果，光属性角色对该敌人的攻击力＋100%",
    "desc_override_tweyen_light_3":
        f"{ICON}自身发动技能时：光属性角色状态技能伤害＋200%（持续10秒，可叠加）\n"
        f"{ICON}自身发动技能时：自身技能伤害＋20%，光属性角色技能充能速度＋1.5%（最多叠加10次）\n"
        f"{ICON}光属性共鸣时，敌方每有1个弱体效果，自身技能伤害＋40%，且连击＋50\n"
        f"{ICON}光属性共鸣时，光属性角色发动技能时，光属性角色技能伤害＋50%（最多＋350%）、攻击力＋50%（最多＋350%）",
    "desc_override_tweyen_light_4": "光属性角色对处于麻痹、气绝、冻结状态的敌人造成的伤害，额外乘区＋15%",
    "desc_override_security_robot_playable":
        "赋予全队(光) 攻击力 100%、技能伤害 120%、眩晕畏缩特攻 30%、HP 20%。\n强化弹射替换为角色专属形态。",
    "desc_override_genin_playable": "赋予全队(暗) 攻击力 100%、技能伤害 120%、中毒特攻 30%、技能槽 30%。",
    "desc_override_genin_playable_1":
        "Lv1强化弹射时，获得1层影。\n"
        "Lv2强化弹射时，获得2层影。\n"
        "Lv3强化弹射时，获得3层影。\n"
        "自身发动技能时，获得2层影（最大5层）。",
}
#: 角色 → (code, 候选工作区, 本次 package_version)。
IDENTITY = {
    "119989": ("lady_summoner_campus", "campus-bianca-20260911", "0.1.2"),
    "119991": ("sorceress_teacher_moon", "ma-nicola", "1.0.2"),
    "119992": ("tiger_treasure_hunter_moon", "ma-mia", "1.0.1"),
    "119993": ("cobra_playable", "cobra_playable", "1.0.2"),
    "119994": ("haniwa_playable", "haniwa_playable", "1.0.2"),
    "119995": ("dog_soldier_playable", "dog_soldier_playable", "1.0.3"),
    "129987": ("ghandagoza", "gbf-ghandagoza-20260919", "1.0.2"),
    "129992": ("unicorn_lancer_rose", "unicorn_lancer_rose", "0.1.16"),
    "129993": ("killer_whale_playable", "killer_whale_playable", "1.0.2"),
    "129994": ("haniwa_blue_playable", "haniwa_blue_playable", "1.0.2"),
    "129995": ("wander_armor_water_playable", "wander_armor_water_playable", "1.0.2"),
    "129996": ("clione_playable", "clione_playable", "1.0.2"),
    "129998": ("ghost_girl_playable", "ghost_girl_playable", "1.0.3"),
    "139992": ("artificialeye_sniper_moon", "ma-charlene", "1.0.2"),
    "139996": ("cube_boss_playable", "cube_boss_playable", "1.0.3"),
    "149991": ("big_bear_monster_playable", "big_bear_monster_playable", "1.0.2"),
    "149992": ("wander_armor_wind_playable", "wander_armor_wind_playable", "1.0.2"),
    "149993": ("haniwa_green_playable", "haniwa_green_playable", "1.0.2"),
    "149994": ("one_eyed_rabbit_playable", "one_eyed_rabbit_playable", "1.0.3"),
    "159994": ("tweyen_light", "ma-thorn", "1.0.2"),
    "159995": ("still_obstinator_moon", "ma-stinel", "1.0.2"),
    "159999": ("security_robot_playable", "security_robot_playable", "1.0.3"),
    "169993": ("genin_playable", "genin", "1.0.2"),
    "179999": ("black_wolf_knight_wt26", "black_wolf_knight_wt26", "0.1.3"),
}
SNAPSHOT = "revision_20260927d"          # extra5 stage_batch.SNAPSHOT
#: 主会话 C：索恩技能文字（面板以外）改前 / 改后逐字。
THORN_FLAG = "change_skill_tweyen_light"
THORN_FLAG_TEXT = ("强化技能：自身技能赋予的麻痹效果、迟缓效果持续时间大幅延长",
                   "强化技能：自身技能赋予的麻痹效果、冻结效果持续时间大幅延长")
THORN_DESC = ("向距离最近的敌人降下光矢之雨，对命中的敌人及其周围造成光属性伤害【对麻痹效果下的敌人伤害提升】"
              "＋赋予其麻痹效果＋迟缓效果＋累积全属性抗性降低效果／赋予光属性角色技能伤害提升效果",
              "向距离最近的敌人降下光矢之雨，对命中的敌人及其周围造成光属性伤害【对麻痹效果下的敌人伤害提升】"
              "＋赋予其麻痹效果＋冻结效果＋累积全属性抗性降低效果／赋予光属性角色技能伤害提升效果")
THORN_PROGRAMS = {"1": "battle/action/skill/action/rare5/tweyen_light$tweyen_light_1",
                  "2": "battle/action/skill/action/rare5/tweyen_light$tweyen_light_2"}
#: R2（技能强化文案）：强化串 live → 最终逐字。索恩 live 先经主会话 C（THORN_FLAG_TEXT）再改官方格式。
THORN_FLAG_FINAL = "强化『星之猎手』：赋予的麻痹效果、冻结效果持续时间大幅延长"
FLAG_STRINGS = {
    "change_skill_lady_summoner_campus_dragon": (
        "强化幼龙吐息：降低全场敌人的能力伤害抗性",
        "强化『绯焰实习·幼龙点名』：幼龙吐息降低全场敌人的能力伤害抗性"),
    "change_skill_sorceress_teacher_moon": (
        "强化技能：提升三相月讲的威力，并加强对火属性角色的技能伤害提升效果",
        "强化『月相夜讲』的威力与「火属性角色技能伤害提升效果」"),
    "change_skill_ghandagoza": (
        "强化『炎天呑舟正拳突击』的「攻击力提升＋强化弹射伤害提升效果」，并强化「独立乘区伤害提升效果」",
        "强化『炎天呑舟正拳突击』的「攻击力提升＋强化弹射伤害提升效果」"),
    THORN_FLAG: (THORN_FLAG_TEXT[0], THORN_FLAG_FINAL),
    # 本轮新增的 4 人（此前没有 panels unit；强化槽都是客户端自动面板）。
    "change_skill_unicorn_lancer_rose": (
        "技能追加：己方贯穿、队伍技能伤害提升、自身浮游20秒；命中时强制赋予敌人不可消除的「对决」。",
        "为『誓约之枪·连突』追加「己方贯穿＋队伍技能伤害提升＋自身浮游效果」，命中时强制赋予敌人不可消除的「对决」"),
    "change_skill_artificialeye_sniper_moon": (
        "雷属性共鸣时强化技能：命中敌人时赋予其累积全属性抗性降低与累积攻击力降低效果（无视弱体抗性），"
        "并随机追加赋予麻痹、中毒、迟缓中的两种效果",
        "强化『桂影·望月三千』：命中敌人时赋予其累积全属性抗性降低与累积攻击力降低效果（无视弱体抗性），"
        "并随机追加赋予麻痹、中毒、冻结中的两种效果"),
    "change_skill_still_obstinator_moon": (
        "强化「月相仪·满月调律」的威力与技能伤害提升效果",
        "强化『月相仪·满月调律』的威力与「技能伤害提升效果」"),
    "change_skill_black_wolf_knight_wt26": (
        "Fever状态中发动技能时，触发超级Fever：队伍全体的攻击力、强化弹射伤害、技能伤害、直接攻击伤害、"
        "能力伤害提升，同时为队伍全体回复生命值并赋予再生效果",
        "强化『炉心颂歌』：Fever状态中发动时增加Fever槽并触发超级Fever，提升队伍全体的攻击力、强化弹射伤害、"
        "技能伤害、直接攻击伤害、能力伤害，并为队伍全体回复生命值、赋予再生效果"),
}
#: 强化串 → (角色, 技能名, 覆盖面板, 面板行号)；None = 走客户端自动面板。
FLAG_OWNER = {
    "change_skill_lady_summoner_campus_dragon": ("119989", "绯焰实习·幼龙点名", "desc_override_lady_summoner_campus_1", 2),
    "change_skill_sorceress_teacher_moon": ("119991", "月相夜讲", None, None),
    "change_skill_ghandagoza": ("129987", "炎天呑舟正拳突击", "desc_override_ghandagoza_6", 1),
    THORN_FLAG: ("159994", "星之猎手", "desc_override_tweyen_light_1", 2),
    "change_skill_unicorn_lancer_rose": ("129992", "誓约之枪·连突", None, None),
    "change_skill_artificialeye_sniper_moon": ("139992", "桂影·望月三千", None, None),
    "change_skill_still_obstinator_moon": ("159995", "月相仪·满月调律", None, None),
    "change_skill_black_wolf_knight_wt26": ("179999", "炉心颂歌", None, None),
}
#: 自动面板的强化条目：开关行前置（客户端拼的条件）= (前置 1..3 的 kind, 共鸣 token)；串里一概不写这些条件。
AUTO_PANEL_GATES = {
    "119991": (("202", "2", "0"), ["Red"]),
    "129992": (("2", "0", "0"), ["Blue"]),
    "139992": (("2", "0", "0"), ["Yellow"]),
    "159995": (("202", "2", "0"), ["White"]),
    "179999": (("202", "2", "0"), ["Red"]),
}
#: R3：冰雪罗尔夫技能说明（action_skill 两档 c1、character_text c5/c7、服务端 [5]/[7]）改前 / 改后逐字。
WT26_DESC = ("赋予队长护盾、体力最低角色再生／火属性和风属性角色的技能伤害与强化弹射伤害提升150%／队伍全体贯通(12.5秒)"
             "／火属性共鸣时，自身在主位且于Fever状态中使用：Fever槽增加200，并触发超级Fever"
             "（队伍全体的攻击力、强化弹射伤害、技能伤害、直接攻击伤害、能力伤害提升350%(10秒)），"
             "同时为队伍全体回复最大生命值5%的生命值并赋予再生效果(10秒) ※技能无后摇",
             "赋予队长护盾、体力最低角色再生／火属性和风属性角色的技能伤害与强化弹射伤害提升150%／队伍全体贯通(12.5秒)"
             " ※技能无后摇")
WT26_PROGRAMS = {"1": "battle/action/skill/action/rare5/black_wolf_knight_wt26$black_wolf_knight_wt26_1",
                 "2": "battle/action/skill/action/rare5/black_wolf_knight_wt26$black_wolf_knight_wt26_2"}
#: 有技能说明输出的角色：索恩（主会话 C）与冰雪罗尔夫（R3 删段）。
DESC_OUT = {"159994": "tweyen_light", "179999": "black_wolf_knight_wt26"}
SPLIT = {"desc_override_one_eyed_rabbit_playable_3", "desc_override_genin_playable_1"}
EDIT = {"desc_override_tweyen_light_1", "desc_override_tweyen_light_2", "desc_override_lady_summoner_campus_1",
        "desc_override_ghandagoza_6"}
SHARED = {"desc_override_tweyen_light_4"}
#: 已定改字（主会话 / 作者），逐条写明；口径3 冒号不在此列（见 normalize_resonance）。
PRE_EDITS = {
    "desc_override_lady_summoner_campus_1":                                                # R2：强化条目官方格式
        ((2, "强化幼龙吐息，赋予全场敌人能力伤害抗性降低20%效果，持续15秒",
          "强化『绯焰实习·幼龙点名』：幼龙吐息降低全场敌人的能力伤害抗性"),),
    "desc_override_ghandagoza_4": ((1, "水属性角色的气绝蓄积", "水属性角色气绝蓄积"),),       # 主会话：去「的」
    "desc_override_ghandagoza_6":                                                          # R2：补上强化内容
        ((1, "强化『炎天呑舟正拳突击』", "强化『炎天呑舟正拳突击』的「攻击力提升＋强化弹射伤害提升效果」"),),
    "desc_override_one_eyed_rabbit_playable_3":                                            # 口径1
        ((1, "（独立乘区）、强化弹射伤害", "（独立乘区），强化弹射伤害"),),
    "desc_override_tweyen_light_1": ((2, "迟缓效果", "冻结效果"),                            # 作者：迟缓改冻结
                                     (2, "强化技能，自身技能赋予的", "强化『星之猎手』：赋予的")),   # R2：点明技能名
    "desc_override_tweyen_light_3": ((4, "强化技能，", ""),),                                 # R1：能力3 无开关行
    "desc_override_tweyen_light_4": ((2, "迟缓状态", "冻结状态"),),                          # 作者：合成一句并改冻结
}
#: 原文里带「X属性共鸣时：」、校验前须按口径3 规范化的面板。
COLON_NORMALISED = {"desc_override_sorceress_teacher_moon_3", "desc_override_tweyen_light_1",
                    "desc_override_tweyen_light_2", "desc_override_tweyen_light_3"}


def normalize_resonance(text: str) -> str:
    """口径3（主会话 2026-09-27）的显式规范化步骤：先把「X属性共鸣时：」后换行接效果的并成一行（后一行的主位图标
    随之去掉），再把其余「X属性共鸣时：」改成「X属性共鸣时，」。"""
    res = r"([火水雷风光暗](?:或[火水雷风光暗])*属性共鸣时)"
    text = re.sub(res + r"[：:]\n(?:\s*<icon id='main'>\s*)?", r"\1，", text)
    return re.sub(res + r"[：:]", r"\1，", text)


def pre_edited(panel: dict) -> str:
    """已定改字：原文第 N 行里的 old 恰出现一次，换成 new。"""
    lines = list(panel["before"])
    for line_no, old, new in PRE_EDITS.get(panel["cas"], ()):
        assert lines[line_no - 1].count(old) == 1, (panel["cas"], old)
        lines[line_no - 1] = lines[line_no - 1].replace(old, new)
    return "\n".join(lines)


def check_orig(panel: dict) -> str:
    """check 的原文 = 改前文字 → 已定改字 → 口径3 规范化。"""
    return normalize_resonance(pre_edited(panel))


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["inputs"]


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def unit(cid: str) -> dict:
    return next(u for u in M.UNITS if u["CID"] == cid)


def drops(panel: dict) -> list[dict]:
    return [dict(line=line, resonance=token) for line, token in panel["drops"]]


def flat(data: dict) -> dict:
    """fixture 嵌套 {kind: {key: value}} → revise 内部的 {(kind, key): value}。"""
    return {(kind, key): value for kind, values in data.items() for key, value in values.items()}


def version(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in text.split("."))


def with_panel(key: str, **changes) -> dict:
    panel = deepcopy(M.PANELS_BY_CAS[key])
    panel.update(changes)
    return panel


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.pristine = deepcopy(cls.live)
        cls.outs = {u["CID"]: u["revise"](reader(cls.live)) for u in M.UNITS}

    def cas_out(self) -> dict:
        return {k: v for out in self.outs.values() for k, v in out["cas"].items()}


class ContractTests(Base):
    def test_units_identity_packages_and_capabilities(self):
        self.assertEqual([u["CID"] for u in M.UNITS], list(IDENTITY))
        for u in M.UNITS:
            code, package, ver = IDENTITY[u["CID"]]
            self.assertEqual((u["CODE"], u["PACKAGES"], u["PACKAGE_VERSION"]), (code, [package], {package: ver}))
            self.assertEqual(u["REVIEWED_DRIFT"], {})
            keys = [p["cas"] for p in M.unit_panels(u["CID"])]
            wanted = sorted({c for key in keys
                             for c in L.required_client_capabilities(L.CUSTOM_ABILITY_STRING_KIND, [key])})
            self.assertEqual(u["CAPABILITIES"], wanted, u["CID"])
            if u["CID"] in MINIBOSS:
                self.assertEqual(package, MINIBOSS[u["CID"]].package_id)

    def test_exactly_the_28_override_panels_and_nothing_else(self):
        self.assertEqual(len(M.PANELS), 28)
        self.assertEqual(set(self.cas_out()), set(EXPECTED) | set(FLAG_STRINGS))
        self.assertEqual({p["cas"] for p in M.PANELS if p["mode"] == "split"}, SPLIT)
        self.assertEqual({p["cas"] for p in M.PANELS if p["mode"] == "edit"}, EDIT)
        self.assertEqual({p["cas"] for p in M.PANELS if p["shared"]}, SHARED)
        self.assertEqual(set(M.SKILL_TEXT), {"159994"})
        self.assertEqual(set(M.FLAG_TEXT), {owner[0] for owner in FLAG_OWNER.values()})
        self.assertEqual(set(M.DESC_TRIM), {"179999"})
        for cid, out in self.outs.items():
            flags = {key for key, owner in FLAG_OWNER.items() if owner[0] == cid}
            self.assertEqual({k for k, v in out.items() if v and k != "notes"},
                             {"cas", "text", "action", "server_text"} if cid in DESC_OUT else {"cas"}, cid)
            self.assertEqual(set(out["cas"]), {p["cas"] for p in M.unit_panels(cid)} | flags, cid)
            json.dumps(out["notes"], ensure_ascii=False)
        for cid, code in DESC_OUT.items():
            out = self.outs[cid]
            self.assertEqual((set(out["text"]), set(out["action"]), set(out["server_text"])), ({cid}, {code}, {cid}))
        # 新增的 4 人只改强化串（冰雪罗尔夫另删技能说明一段），没有覆盖面板。
        for cid in ("129992", "139992", "159995", "179999"):
            self.assertEqual(M.unit_panels(cid), (), cid)

    def test_every_panel_verbatim(self):
        for key, text in EXPECTED.items():
            self.assertEqual(self.cas_out()[key], [[text]], key)
            self.assertEqual("\n".join(M.PANELS_BY_CAS[key]["after"]), text, key)
        for key, (_before, after) in FLAG_STRINGS.items():
            self.assertEqual(self.cas_out()[key], [[after]], key)
        self.assertEqual(self.cas_out()[THORN_FLAG], [[THORN_FLAG_FINAL]])

    def test_before_is_the_live_text_and_every_input_is_locked(self):
        self.assertEqual(set(M.BEFORE), {item for cid in M.UNIT_ORDER for item in M.unit_inputs(cid)})
        for (kind, key), value in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), value, (kind, key))
        for panel in M.PANELS:
            self.assertEqual(self.live["cas"][panel["cas"]], [["\n".join(panel["before"])]], panel["cas"])
        for u in M.UNITS:
            self.assertEqual(u["BEFORE"], {i: M.BEFORE[i] for i in M.unit_inputs(u["CID"])})

    def test_candidate_namespace_and_plan_splice_auto_claim(self):
        """stage_batch.Plan.splice：键已认领，或以 cid / code / desc_override_<code> / change_skill_<code> 开头 ⇒ 自动认领。"""
        for u in M.UNITS:
            for key in self.outs[u["CID"]]["cas"]:
                flag = key in FLAG_STRINGS and FLAG_OWNER[key][0] == u["CID"]
                prefix = ("change_skill_" if flag else "desc_override_") + u["CODE"]
                self.assertTrue(key.startswith(prefix), key)
                self.assertTrue(key.startswith((u["CID"], u["CODE"], "desc_override_" + u["CODE"],
                                                "change_skill_" + u["CODE"])), key)
                self.assertEqual(L.required_client_capabilities(L.CUSTOM_ABILITY_STRING_KIND, [key]),
                                 [] if flag else [L.PANEL_OVERRIDE_V2], key)


class DriftAndPurityTests(Base):
    def test_every_input_drift_is_rejected(self):
        for u in M.UNITS:
            for kind, key in M.unit_inputs(u["CID"]):
                data = deepcopy(self.live)
                value = data[kind][key]
                if kind == "cas":
                    value[0][0] += "。"
                elif kind in ("ability", "leader"):
                    value[-1][34] = value[-1][34] + "9"
                elif kind == "action":
                    value[0][1][0] = value[0][1][0] + "x"
                else:
                    value.append("drift")
                with self.assertRaises(M.PanelMergeError, msg=f"{kind}:{key}"):
                    u["revise"](reader(data))

    def test_missing_input_is_rejected(self):
        for key in ("desc_override_genin_playable", "desc_override_genin_playable_1"):
            data = deepcopy(self.live)
            del data["cas"][key]
            with self.assertRaises((M.PanelMergeError, KeyError)):
                unit("169993")["revise"](reader(data))

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        outs = [u["revise"](reader(data)) for u in M.UNITS]
        self.assertEqual(data, self.pristine)
        outs[0]["cas"]["desc_override_lady_summoner_campus_3"][0][0] = "mutated"
        outs[0]["cas"]["change_skill_lady_summoner_campus_dragon"][0][0] = "mutated"
        self.assertEqual(data, self.pristine)
        flag = "change_skill_lady_summoner_campus_dragon"
        self.assertEqual(unit("119989")["revise"](reader(data))["cas"],
                         {key: [[EXPECTED[key]]] for key in ("desc_override_lady_summoner_campus_1",
                                                              "desc_override_lady_summoner_campus_3")}
                         | {flag: [[FLAG_STRINGS[flag][1]]]})

    def test_rerun_on_own_output_is_rejected(self):
        data = deepcopy(self.live)
        data["cas"].update(deepcopy(self.cas_out()))
        for u in M.UNITS:
            with self.assertRaises(M.PanelMergeError, msg=u["CID"]):
                u["revise"](reader(data))


class CheckerTests(unittest.TestCase):
    """口径7：校验器是仓库里的 wf_panel_merge_check（硬依赖）；本模块不再另行移植。"""

    def test_module_uses_the_in_repo_checker(self):
        self.assertIs(M.merge_check, PMC.check)
        self.assertIs(M.merge_check, check)
        self.assertEqual(M.FORBIDDEN, PMC.FORBIDDEN)

    def test_explicit_normalisation_matches_the_module(self):
        for panel in M.PANELS:
            self.assertEqual(M.check_orig(panel), check_orig(panel), panel["cas"])
            self.assertEqual(tuple(panel["pre_edits"]), PRE_EDITS.get(panel["cas"], ()), panel["cas"])
        self.assertEqual({p["cas"] for p in M.PANELS if normalize_resonance(pre_edited(p)) != pre_edited(p)},
                         COLON_NORMALISED)

    def test_resonance_normalisation_both_shapes(self):
        self.assertEqual(normalize_resonance("雷属性共鸣时：\nFEVER模式中，独立乘区的强化弹射伤害提升30％"),
                         "雷属性共鸣时，FEVER模式中，独立乘区的强化弹射伤害提升30％")
        self.assertEqual(normalize_resonance(f"{ICON}火属性共鸣时：\n{ICON}自身技能槽＋5%\n{ICON}光属性共鸣时：连击＋5"),
                         f"{ICON}火属性共鸣时，自身技能槽＋5%\n{ICON}光属性共鸣时，连击＋5")
        self.assertEqual(normalize_resonance("自身发动技能时：自身技能伤害＋20%"), "自身发动技能时：自身技能伤害＋20%")
        for text in ("雷属性共鸣时：\nFEVER模式中，提升30％", "光或暗属性共鸣时：攻击力＋5%", "风属性共鸣时:x"):
            self.assertEqual(M.normalize_resonance(text), normalize_resonance(text), text)


class MergeRuleTests(Base):
    def test_check_is_clean_for_every_merge_and_edit_panel(self):
        for panel in M.PANELS:
            if panel["mode"] == "split":
                continue
            result = check(check_orig(panel), "\n".join(panel["after"]), drops(panel))
            kinds = set(result["columns"][0]["kinds"].values())
            if panel["cas"] in SHARED:
                # 作者定稿的同值合写：三条 15% 写一次 ⇒ check 只报数值多重集合（2 → 1），别无他错。
                self.assertEqual(result["errors"], [
                    "[列1] 新文案第1行效果数值多重集合不一致：应 {'15%': 2} 实 {'15%': 1}",
                    "[列1] 全文效果数值多重集合改变"])
            else:
                self.assertTrue(result["ok"], (panel["cas"], result["errors"]))
            if panel["mode"] == "merge":
                self.assertIn("merge", kinds, panel["cas"])
            else:
                self.assertEqual(kinds, {"verbatim"}, panel["cas"])
                self.assertEqual("\n".join(panel["after"]), check_orig(panel), panel["cas"])
            self.assertEqual(M.text_problems(panel), [], panel["cas"])

    def test_raw_text_needs_only_the_registered_normalisation(self):
        """不做已定改字与口径3 规范化时：原文带「X属性共鸣时：」的面板必报错（冒号改写不是合并）；
        没有登记改字 / 规范化的面板原文直接过 check。"""
        for panel in M.PANELS:
            if panel["mode"] == "split" or panel["cas"] in SHARED:
                continue
            raw = check("\n".join(panel["before"]), "\n".join(panel["after"]), drops(panel))
            if panel["cas"] in COLON_NORMALISED:
                self.assertTrue(raw["errors"], panel["cas"])
            elif panel["cas"] not in PRE_EDITS:
                self.assertEqual(raw["errors"], [], panel["cas"])

    def test_split_panels_are_the_mechanical_expansion(self):
        for key in SPLIT:
            panel = M.PANELS_BY_CAS[key]
            [line] = check_orig(panel).split("\n")
            self.assertEqual(M.expand_split(line, panel["rewrites"]), list(panel["after"]), key)
            self.assertEqual(M.text_problems(panel), [], key)
            self.assertEqual(M.line_mapping(panel), {j: [1] for j in range(1, len(panel["after"]) + 1)})
        self.assertEqual(M.expand_split("Lv1／Lv2／Lv3强化弹射时，分别获得1／2／3层影；自身，获得2层影。", [("分别获得", "获得")]),
                         ["Lv1强化弹射时，获得1层影。", "Lv2强化弹射时，获得2层影。", "Lv3强化弹射时，获得3层影。",
                          "自身，获得2层影。"])

    def test_split_negative_controls(self):
        with self.assertRaisesRegex(M.PanelMergeError, "uneven"):
            M.expand_split("Lv1／Lv2／Lv3强化弹射时，分别获得1／2层影")
        with self.assertRaisesRegex(M.PanelMergeError, "left after the split"):
            M.expand_split("分别发动「小雷爪」／「大横扫」")
        with self.assertRaisesRegex(M.PanelMergeError, "not found once"):
            M.expand_split("Lv1／Lv2强化弹射时，追加爪刃追击", [("对应等级的", "Lv{n}")])
        rabbit = M.PANELS_BY_CAS["desc_override_one_eyed_rabbit_playable_3"]
        bad = [
            rabbit["after"][:3] + (rabbit["after"][3].replace("），强化", "）、强化"),),        # 口径1 回退
            (rabbit["after"][1], rabbit["after"][0]) + rabbit["after"][2:],                    # 行序
            rabbit["after"][:2] + rabbit["after"][3:],                                         # 漏行
            tuple(line.replace("+100%", "+150%") for line in rabbit["after"]),                  # 改数
        ]
        for after in bad:
            self.assertTrue(M.text_problems(with_panel(rabbit["cas"], after=tuple(after))), after)

    def test_negative_controls_are_caught(self):
        panel = M.PANELS_BY_CAS["desc_override_haniwa_playable"]
        before = "\n".join(panel["before"])
        bad = [
            "赋予全队(火) 攻击力 80%、直接攻击伤害 140%、HP 20%，自身 强化弹射伤害 80%。",      # 改数值
            "赋予全队(火) 攻击力 80%、直接攻击伤害 140%，自身 强化弹射伤害 80%。",              # 漏效果
            "赋予全队(火) 攻击力 80%／直接攻击伤害 140%／HP 15%，自身 强化弹射伤害 80%。",      # 「／」
        ]
        for text in bad:
            self.assertFalse(check(before, text)["ok"], text)
        bianca = M.PANELS_BY_CAS["desc_override_lady_summoner_campus_3"]
        self.assertFalse(check("\n".join(bianca["before"]), "\n".join(bianca["after"]))["ok"])   # 未授权删共鸣
        nicola = M.PANELS_BY_CAS["desc_override_sorceress_teacher_moon_3"]
        colon = [line.replace("火属性共鸣时，", "火属性共鸣时：") for line in nicola["after"]]
        self.assertFalse(check(check_orig(nicola), "\n".join(colon), drops(nicola))["ok"])
        self.assertTrue(M.text_problems(with_panel(nicola["cas"], after=tuple(colon))))
        thorn3 = M.PANELS_BY_CAS["desc_override_tweyen_light_3"]
        colon = tuple(line.replace("光属性共鸣时，", "光属性共鸣时：") for line in thorn3["after"])
        self.assertTrue(M.text_problems(with_panel(thorn3["cas"], after=colon)))         # 未合并行留冒号也拒绝
        thorn1 = M.PANELS_BY_CAS["desc_override_tweyen_light_1"]
        slow = tuple(line.replace("冻结效果", "迟缓效果") for line in thorn1["after"])
        self.assertTrue(M.text_problems(with_panel(thorn1["cas"], after=slow)))
        thorn4 = M.PANELS_BY_CAS["desc_override_tweyen_light_4"]
        for after in (("光属性角色对处于麻痹、气绝、冻结状态的敌人造成的伤害，额外乘区＋20%",),
                      ("光属性角色对处于麻痹、气绝、冻结状态的敌人造成的伤害，额外乘区＋15%、＋15%",),
                      ("光属性角色对处于麻痹、气绝、迟缓状态的敌人造成的伤害，额外乘区＋15%",)):
            self.assertTrue(M.text_problems(with_panel(thorn4["cas"], after=after)), after)
        self.assertTrue(M.text_problems(with_panel(thorn4["cas"], shared=())))          # 未登记同值合写 ⇒ 数值报错
        ghand = M.PANELS_BY_CAS["desc_override_ghandagoza"]
        self.assertEqual(M.text_problems(with_panel(ghand["cas"], after=(
            "水属性角色攻击力＋300%，自身强化弹射伤害＋300%", ghand["after"][1]))), [])   # check 本身不管对象，口径1 由逐字锁

    def test_unmerged_lines_are_verbatim_and_in_order(self):
        for panel in M.PANELS:
            if panel["mode"] == "split":
                continue
            result = check(check_orig(panel), "\n".join(panel["after"]), drops(panel))["columns"][0]
            mapping, kinds = result["mapping"], result["kinds"]
            touched = ({line for line, _ in panel["drops"]} | {line for line, *_ in PRE_EDITS.get(panel["cas"], ())}
                       | {i for i, (a, b) in enumerate(zip(panel["before"], check_orig(panel).split("\n")), 1)
                          if a != b})
            for old, new in mapping.items():
                sources = [o for o, n in mapping.items() if n == new]
                if len(sources) == 1 and old not in touched:
                    self.assertEqual(kinds[new], "verbatim", (panel["cas"], old))
                    self.assertEqual(panel["after"][new - 1], panel["before"][old - 1], (panel["cas"], old))
            firsts = [min(o for o, n in mapping.items() if n == j) for j in sorted(set(mapping.values()))]
            self.assertEqual(firsts, sorted(firsts), panel["cas"])          # 合并行在组首行位置，其余行序不变

    def test_panel_rules(self):
        for key, [[text]] in self.cas_out().items():
            self.assertEqual(panel_problems(text), [], key)
            self.assertNotIn("\\n", text)
            for word in M.FORBIDDEN:
                self.assertNotIn(word, text, key)
            self.assertNotRegex(text, r"属性共鸣时[：:]", key)                 # 口径3：返回的面板一律「，」
            for line in text.split("\n"):
                self.assertNotRegex(line, r"^\s*$")
                if "<icon" in line:
                    self.assertTrue(line.startswith(ICON), line)

    def test_pf_damage_is_not_given_an_object(self):
        """口径1：原文没写对象的「强化弹射伤害」不补「自身」，与前一个带对象的效果用「，」隔开。"""
        ghand = self.cas_out()["desc_override_ghandagoza"][0][0].split("\n")[0]
        self.assertEqual(ghand, "水属性角色攻击力＋300%，强化弹射伤害＋300%")
        rabbit = self.cas_out()["desc_override_one_eyed_rabbit_playable_3"][0][0].split("\n")[-1]
        self.assertIn("（独立乘区），强化弹射伤害+100%", rabbit)
        self.assertNotIn("、强化弹射伤害", rabbit)

    def test_resonance_is_dropped_only_where_the_state_implies_it(self):
        bianca = self.outs["119989"]["cas"]["desc_override_lady_summoner_campus_3"][0][0].split("\n")
        self.assertTrue(bianca[0].startswith(ICON + "火属性共鸣时，") and bianca[1].startswith(ICON + "火属性共鸣时，"))
        self.assertTrue(bianca[2].startswith(ICON + "Fever模式中，每层「焰域研修」"))
        nicola = self.outs["119991"]["cas"]["desc_override_sorceress_teacher_moon_3"][0][0].split("\n")
        self.assertTrue(nicola[1].startswith(ICON + "除自身外的火属性角色发动技能时，消耗1层「月讲」"))
        self.assertTrue(nicola[0].startswith(ICON + "火属性共鸣时，") and nicola[2].startswith(ICON + "火属性共鸣时，"))
        mia = self.outs["119992"]["cas"]["desc_override_tiger_treasure_hunter_moon"][0][0].split("\n")
        self.assertTrue(mia[-1].startswith("火属性共鸣时，持有「桂灯」"))      # 桂灯有不带共鸣的来源 ⇒ 保留
        thorn = self.outs["159994"]["cas"]["desc_override_tweyen_light_1"][0][0].split("\n")
        self.assertTrue(thorn[1].startswith("光属性共鸣时，强化『星之猎手』："))  # 口径2：536 开关的共鸣是真实条件
        thorn2 = self.outs["159994"]["cas"]["desc_override_tweyen_light_2"][0][0]
        self.assertTrue(thorn2.startswith("光属性共鸣时，敌人身上"))              # 主会话 F：只改冒号，光共鸣是真实前置
        self.assertEqual(M.resonance_tokens("ability", self.live["ability"]["1599942"][0]), ["White"])

    def test_edit_panel_resonance_line_needs_the_resonance_row(self):
        thorn2 = M.PANELS_BY_CAS["desc_override_tweyen_light_2"]
        rows = deepcopy(self.live["ability"]["1599942"])
        self.assertEqual(M.check_rows(thorn2, rows), [])
        rows[0][6] = "0"                                                  # 去掉光共鸣前置 ⇒ 面板「光属性共鸣时，」无据
        self.assertTrue(any("lacks White resonance" in p for p in M.check_rows(thorn2, rows)))
        thorn1 = M.PANELS_BY_CAS["desc_override_tweyen_light_1"]
        rows = deepcopy(self.live["ability"]["1599941"])
        rows[1][6] = "0"
        self.assertTrue(any("lacks White resonance" in p for p in M.check_rows(thorn1, rows)))


class DataLockTests(Base):
    def test_groups_share_every_non_effect_cell(self):
        for panel in M.PANELS:
            rows = self.live[panel["kind"]][panel["key"]]
            self.assertEqual(M.check_rows(panel, rows), [], panel["cas"])
            for group in panel["groups"]:
                cells = {M.condition_cells(panel["kind"], rows[i]) for i in group}
                self.assertEqual(len(cells), 1, panel["cas"])

    def test_condition_or_kind_drift_breaks_the_lock(self):
        for panel in M.PANELS:
            lay = M.LAYOUT[panel["kind"]]
            for group in panel["groups"]:
                index = group[-1]
                if len(group) > 1:
                    rows = deepcopy(self.live[panel["kind"]][panel["key"]])
                    rows[index][34] = rows[index][34] + "1"                 # 次数上限列（非效果列）
                    self.assertTrue(M.check_rows(panel, rows), (panel["cas"], group))
                rows = deepcopy(self.live[panel["kind"]][panel["key"]])
                col = lay["dc"] if rows[index][lay["trig"]] == "1" else lay["ic"]
                rows[index][col] = "999"
                self.assertTrue(M.check_rows(panel, rows), (panel["cas"], group))

    def test_effect_cells_may_differ(self):
        panel = M.PANELS_BY_CAS["desc_override_haniwa_playable"]
        rows = self.live["leader"][panel["key"]]
        self.assertNotEqual(rows[0][45:51], rows[2][45:51])             # 32 全队(火) vs 55 自身
        self.assertEqual(M.check_rows(panel, rows), [])

    def test_split_lock(self):
        rabbit = M.PANELS_BY_CAS["desc_override_one_eyed_rabbit_playable_3"]
        rows = self.live["ability"]["1499943"]
        swapped = with_panel(rabbit["cas"], after=(rabbit["after"][1], rabbit["after"][0]) + rabbit["after"][2:])
        self.assertTrue(any("Lv2" in p for p in M.check_rows(swapped, rows)))      # 等级行对错数据行
        same = deepcopy(rows)
        same[1] = deepcopy(same[0])                                                 # Lv2 行抄成 Lv1 行 ⇒ 两行同条件
        self.assertTrue(any("share a data condition" in p for p in M.check_rows(rabbit, same)))
        self.assertTrue(M.check_rows(with_panel(rabbit["cas"], groups=((0,), (1,), (2, 3), (4,)),
                                                kinds=(("629",), ("629",), ("629", "410"), ("23",))), rows))
        genin = M.PANELS_BY_CAS["desc_override_genin_playable_1"]
        rows = deepcopy(self.live["ability"]["1699931"])
        rows[1][51] = rows[1][52] = "300000"                                        # Lv2 改授 3 层 ⇒ 面板「2层」不符
        self.assertTrue(any("grants" in p for p in M.check_rows(genin, rows)))

    def test_shared_value_needs_equal_strengths(self):
        thorn4 = M.PANELS_BY_CAS["desc_override_tweyen_light_4"]
        rows = deepcopy(self.live["ability"]["1599944"])
        self.assertEqual({M.effect_strength("ability", r) for r in rows}, {("15000", "15000")})
        rows[2][51] = rows[2][52] = "20000"
        self.assertTrue(any("shared value" in p for p in M.check_rows(thorn4, rows)))

    def test_state_census_backs_every_resonance_drop(self):
        want = {"119989": [("ability", "1199893", 1, "629 lady_summoner_campus_fever_tick")],
                "119991": [("ability", "1199913", 0, "461")]}
        for cid, sources in want.items():
            got = M.state_sources(cid, flat(self.live))
            self.assertEqual([(s["table"], s["key"], s["row"], s["via"]) for s in got], sources)
            self.assertTrue(all(s["resonance"] == ["Red"] for s in got))
            self.assertEqual(self.outs[cid]["notes"]["state_census"], got)
        self.assertEqual(M.dsl_grants(self.live["dsl"][M.CENSUS["119989"]["invokes"][0]]), {"11998903"})
        for path in M.CENSUS["119989"]["skills"]:
            self.assertEqual(M.dsl_grants(self.live["dsl"][path]), {"11998901", "11998902"})

    def test_census_rejects_an_ungated_source(self):
        data = deepcopy(self.live)
        data["ability"]["1199913"][0][6] = "0"                           # 月讲来源去掉火共鸣
        with self.assertRaisesRegex(M.PanelMergeError, "lacks Red resonance"):
            M.state_sources("119991", flat(data))
        data = deepcopy(self.live)
        skill = data["dsl"][M.CENSUS["119991"]["skills"][0]]
        skill.append(["Command", ["CreateCondition", -17, [["ACUnique", 11999101, 1]]]])
        with self.assertRaisesRegex(M.PanelMergeError, "skill program grants"):
            M.state_sources("119991", flat(data))
        data = deepcopy(self.live)
        data["ability"]["1199896"][0][47], data["ability"]["1199896"][0][68] = "461", "11998903"
        data["ability"]["1199896"][0][5] = "0"
        data["ability"]["1199896"][0][6] = "0"
        with self.assertRaisesRegex(M.PanelMergeError, "lacks Red resonance"):
            M.state_sources("119989", flat(data))

    def test_thorn_skill_status_backs_the_frozen_wording(self):
        problems, evidence = M.skill_status_problems("159994", flat(self.live))
        self.assertEqual(problems, [])
        self.assertEqual(evidence, {
            "tweyen_light_1": {"ACParalysis": {"on": [900, 900], "off": [300, 300]},
                               "ACFrozen": {"on": [1200, 1200], "off": [600, 600]}},
            "tweyen_light_2": {"ACParalysis": {"on": [1080, 1200], "off": [360, 480]},
                               "ACFrozen": {"on": [1650, 1800], "off": [750, 900]}}})
        self.assertEqual(self.outs["159994"]["notes"]["skill_status"], evidence)

    def test_thorn_skill_status_negative_controls(self):
        path = M.SKILL_STATUS["159994"]["skills"][0]

        def switch(tree):
            found = []

            def walk(node):
                if isinstance(node, list):
                    if len(node) >= 4 and node[0] == "ConditionalsChangeSkillFlag":
                        found.append(node)
                    for child in node:
                        walk(child)
            walk(tree)
            return found[0]

        data = deepcopy(self.live)
        on = switch(data["dsl"][path])[2][1]
        del on[1]                                                        # 开支去掉 ACFrozen
        self.assertTrue(M.skill_status_problems("159994", flat(data))[0])
        data = deepcopy(self.live)
        on = switch(data["dsl"][path])[2][1]
        on[1][1][2][0][1][0]["min"] = 600                                # 开支冻结不再长于关支
        self.assertTrue(any("not longer" in p for p in M.skill_status_problems("159994", flat(data))[0]))
        data = deepcopy(self.live)
        data["ability"]["1599941"][1][6] = "0"                           # 536 开关去掉光共鸣
        self.assertTrue(M.skill_status_problems("159994", flat(data))[0])
        with self.assertRaises(M.PanelMergeError):
            unit("159994")["revise"](reader(data))


class ThornSkillTextTests(Base):
    """主会话 C：索恩「迟缓」统一按数据改「冻结」——技能强化条目、技能说明四处（text c5/c7、action 两档 c1、服务端 [5]/[7]）。"""

    def test_registration_is_the_explicit_text(self):
        spec = M.SKILL_TEXT["159994"]
        self.assertEqual((spec["old"], spec["new"]), ("迟缓", "冻结"))
        self.assertEqual(spec["cas"], {THORN_FLAG: THORN_FLAG_TEXT})
        self.assertEqual(spec["desc"], THORN_DESC)
        for before, after in (THORN_FLAG_TEXT, THORN_DESC):
            self.assertEqual(before.count("迟缓"), 1)
            self.assertEqual(before.replace("迟缓", "冻结"), after)
            self.assertNotIn("迟缓", after)

    def test_live_is_the_before_text(self):
        self.assertEqual(self.live["cas"][THORN_FLAG], [[THORN_FLAG_TEXT[0]]])
        for kind in ("text", "server_text"):
            row = self.live[kind]["159994"][0]
            self.assertEqual((row[5], row[7]), (THORN_DESC[0], THORN_DESC[0]), kind)
        self.assertEqual(self.live["text"]["159994"], self.live["server_text"]["159994"])
        self.assertEqual([(inner, fields[1], fields[7]) for inner, fields in self.live["action"]["tweyen_light"]],
                         [(level, THORN_DESC[0], path) for level, path in THORN_PROGRAMS.items()])

    def test_outputs_change_only_the_one_word(self):
        out = self.outs["159994"]
        self.assertEqual(out["cas"][THORN_FLAG], [[THORN_FLAG_FINAL]])              # 主会话 C 稿再经 R2 改格式
        self.assertEqual(THORN_FLAG_FINAL, "强化『星之猎手』：" + THORN_FLAG_TEXT[1][len("强化技能：自身技能"):])
        for kind in ("text", "server_text"):
            want = deepcopy(self.live[kind]["159994"])
            want[0][5] = want[0][7] = THORN_DESC[1]
            self.assertEqual(out[kind]["159994"], want, kind)
        want = [(inner, [THORN_DESC[1] if col == 1 else cell for col, cell in enumerate(fields)])
                for inner, fields in self.live["action"]["tweyen_light"]]
        self.assertEqual([(inner, list(fields)) for inner, fields in out["action"]["tweyen_light"]], want)
        texts = [out["cas"][THORN_FLAG][0][0],
                 *(out[k]["159994"][0][c] for k in ("text", "server_text") for c in (5, 7)),
                 *(fields[1] for _, fields in out["action"]["tweyen_light"])]
        for text in texts:
            self.assertNotIn("迟缓", text)
            self.assertIn("冻结效果", text)
            self.assertEqual(panel_problems(text), [], text)
        self.assertEqual(panel_problems(THORN_FLAG_TEXT[1], skill_flag=True), [])     # 技能强化条目不写数字与时间
        for key, [[text]] in out["cas"].items():
            self.assertNotIn("迟缓", text, key)
        notes = out["notes"]["skill_text"]
        self.assertEqual((notes["before"], notes["after"], notes["cas"]), (*THORN_DESC, [THORN_FLAG]))

    def test_dsl_backs_every_status_in_the_description(self):
        from wf_dsl_sig import AC_CN
        self.assertEqual((AC_CN["ACFrozen"], AC_CN["ACParalysis"]), ("冻结", "麻痹"))    # 客户端名：ACFrozen = 冻结
        problems, evidence = M.skill_text_problems("159994", flat(self.live))
        self.assertEqual(problems, [])
        want = {"hit": ["ACFrozen", "ACParalysis", "ACToleranceOfElement"], "other": ["ACSkillDamage"]}
        self.assertEqual(evidence, {"1": want, "2": want})
        self.assertEqual(self.outs["159994"]["notes"]["skill_text"]["dsl_statuses"], evidence)
        for path in THORN_PROGRAMS.values():
            self.assertEqual({k: sorted(v) for k, v in M.skill_conditions(self.live["dsl"][path]).items()}, want)
        # 技能强化条目的开关分支（536 开 ⇒ 长时长）同样只挂麻痹 / 冻结。
        self.assertEqual(M.SKILL_STATUS["159994"]["statuses"], ("ACParalysis", "ACFrozen"))
        self.assertEqual(M.SKILL_STATUS["159994"]["string"], THORN_FLAG)

    def test_dsl_negative_controls(self):
        def conditions(tree):
            found = []

            def walk(node):
                if isinstance(node, list):
                    if (len(node) > 1 and node[0] == "Command" and isinstance(node[1], list) and node[1]
                            and node[1][0] == "CreateCondition"):
                        found.append(node[1])
                    for child in node:
                        walk(child)
            walk(tree)
            return found

        for ac in ("ACFrozen", "ACToleranceOfElement"):                  # 命中块里换掉冻结 / 抗性↓ ⇒ 说明无据
            data = deepcopy(self.live)
            for cond in conditions(data["dsl"][THORN_PROGRAMS["2"]]):
                if cond[2][0][0] == ac:
                    cond[2][0][0] = "ACPoison"
            self.assertTrue(M.skill_text_problems("159994", flat(data))[0], ac)
        data = deepcopy(self.live)
        for cond in conditions(data["dsl"][THORN_PROGRAMS["1"]]):
            if cond[2][0][0] == "ACSkillDamage":
                cond[2][0][0] = "ACAttackPoint"                              # 尾巴不再是技能伤害提升
        self.assertTrue(M.skill_text_problems("159994", flat(data))[0])
        data = deepcopy(self.live)
        data["action"]["tweyen_light"][0][1][7] = THORN_PROGRAMS["2"] + "x"     # 技能程序漂移
        self.assertTrue(M.skill_text_problems("159994", flat(data))[0])
        with self.assertRaises(M.PanelMergeError):
            unit("159994")["revise"](reader(data))

    def test_text_negative_controls(self):
        for kind, mutate in (("text", lambda rows: rows[0].__setitem__(5, THORN_DESC[1])),      # 已改过 / 被别处改过
                             ("server_text", lambda rows: rows[0].__setitem__(7, THORN_DESC[1])),
                             ("action", lambda rows: rows[1][1].__setitem__(1, THORN_DESC[1])),
                             ("cas", lambda rows: rows[0].__setitem__(0, THORN_FLAG_TEXT[1]))):
            data = deepcopy(self.live)
            key = {"text": "159994", "server_text": "159994", "action": "tweyen_light", "cas": THORN_FLAG}[kind]
            mutate(data[kind][key])
            with self.assertRaises(M.PanelMergeError, msg=kind):
                M.skill_text_outputs("159994", flat(data))
            with self.assertRaises(M.PanelMergeError, msg=kind):
                unit("159994")["revise"](reader(data))
        spec = deepcopy(M.SKILL_TEXT["159994"])
        try:
            M.SKILL_TEXT["159994"]["desc"] = (THORN_DESC[0], THORN_DESC[1].replace("麻痹效果＋", "麻痹效果、"))
            self.assertTrue(M.skill_text_problems("159994", flat(self.live))[0])      # 改后多动了别的字
            M.SKILL_TEXT["159994"]["desc"] = (THORN_DESC[0], THORN_DESC[0])
            self.assertTrue(M.skill_text_problems("159994", flat(self.live))[0])      # 没改
        finally:
            M.SKILL_TEXT["159994"] = spec

    def test_outputs_are_detached_from_the_input(self):
        data = deepcopy(self.live)
        out = unit("159994")["revise"](reader(data))
        self.assertEqual(data, self.pristine)
        out["text"]["159994"][0][5] = "x"
        out["action"]["tweyen_light"][0][1][1] = "x"
        self.assertEqual(data, self.pristine)


def _commands(tree, name: str) -> list[list]:
    """DSL 里 ``["Command", [name, ...]]`` 的参数表（原地引用，可改）。"""
    found = []

    def walk(node):
        if isinstance(node, list):
            if len(node) > 1 and node[0] == "Command" and isinstance(node[1], list) and node[1] and node[1][0] == name:
                found.append(node[1])
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(tree)
    return found


class SkillFlagTests(Base):
    """技能强化文案 R1–R4：强化串官方格式（点明技能名、定性、不写条件），覆盖面板开关行 == 共鸣前缀 + 同一串，
    DSL 依据（旗号开 / 关支差异、alv 载体）正反例，技能说明不写强化后的效果。"""

    def flag(self, cid: str, data=None, current=None) -> list[str]:
        spec = M.FLAG_TEXT[cid]
        text = current or (THORN_FLAG_TEXT[1] if cid == "159994" else spec["before"])
        return M.flag_problems(cid, flat(self.live if data is None else data), text)[0]

    def test_registration_is_the_explicit_text(self):
        for key, (before, after) in FLAG_STRINGS.items():
            cid, skill, panel, line = FLAG_OWNER[key]
            spec = M.FLAG_TEXT[cid]
            self.assertEqual((spec["string"], spec["after"], spec["skill"], spec["panel"], spec["line"]),
                             (key, after, skill, panel, line))
            self.assertEqual(M.cas_changes(cid)[key], (before, after))
            self.assertEqual(self.live["cas"][key], [[before]], key)
            notes = self.outs[cid]["notes"]["skill_flag"]
            self.assertEqual((notes["string"], notes["before"], notes["after"]), (key, before, after))
        self.assertEqual(M.FLAG_TEXT["159994"]["before"], THORN_FLAG_TEXT[1])      # 接在主会话 C 的「冻结」稿之后
        for cid in ("119989", "119991", "129987"):
            self.assertEqual(M.FLAG_TEXT[cid]["before"], FLAG_STRINGS[M.FLAG_TEXT[cid]["string"]][0])

    def test_strings_follow_the_official_format(self):
        for key, (_before, after) in FLAG_STRINGS.items():
            cid, skill, _panel, _line = FLAG_OWNER[key]
            # 官方两种起头：「强化『<技能名>』…」/「为『<技能名>』追加「…」」（杰拉尔）。
            self.assertTrue(after.startswith((f"强化『{skill}』", f"为『{skill}』追加「")), key)
            self.assertEqual(self.live["text"][cid][0][4], skill, key)              # 技能名 == character_text c4
            self.assertEqual(panel_problems(after, skill_flag=True), [], key)
            self.assertNotRegex(after, r"[0-9%％秒]", key)
            for word in ("强化技能", "强化自身技能", "共鸣", "队长", "主位", "强化后", "不受此限"):
                self.assertNotIn(word, after, key)
        # 冈达葛萨：独立乘区＋91.7% 是能力6 #1（持续 421）的数值行，不是旗号 ⇒ 强化串不写它，面板第2行照写。
        self.assertNotIn("独立乘区", FLAG_STRINGS["change_skill_ghandagoza"][1])
        row = self.live["ability"]["1299876"][1]
        self.assertEqual((row[5], row[109], row[113], row[114]), ("1", "421", "91700", "91700"))
        self.assertIn("独立乘区伤害进一步＋91.7%", EXPECTED["desc_override_ghandagoza_6"])

    def test_panel_switch_line_is_the_string(self):
        prefix = {"119989": "火属性共鸣时，", "129987": "", "159994": "光属性共鸣时，"}
        for key, (_before, after) in FLAG_STRINGS.items():
            cid, _skill, panel, line = FLAG_OWNER[key]
            spec = M.FLAG_TEXT[cid]
            row = self.live["ability"][spec["key"]][spec["switch_row"]]
            self.assertEqual((row[5], row[47], row[70]), ("0", "536", key))
            if panel is None:                                  # 自动面板：开关行前置（主位 / 共鸣）由客户端拼
                self.assertNotIn(spec["key"], {p["key"] for p in M.PANELS})
                kinds, tokens = AUTO_PANEL_GATES[cid]
                self.assertEqual((tuple(row[b] or "0" for b in (6, 13, 20)), M.resonance_tokens("ability", row)),
                                 (kinds, tokens), cid)
                slot_key = f"desc_override_{M.identity(cid)[0]}_{spec['key'][len(cid):]}"
                self.assertNotIn(slot_key, self.live["cas"], cid)             # 该槽没有覆盖文案
                self.assertEqual(M.auto_panel_problems(cid, reader(self.live)), [], cid)
                continue
            icon = ICON if row[1] == "false" else ""
            got = EXPECTED[panel].split("\n")[line - 1]
            self.assertIn(got, (icon + prefix[cid] + after, icon + prefix[cid] + after + "。"), key)

    def test_no_generic_enhancement_label_is_returned(self):
        for key, [[text]] in self.cas_out().items():
            for word in ("强化技能", "强化自身技能"):
                self.assertNotIn(word, text, key)
        # R1：索恩能力3 没有开关行 ⇒ 第3行只删「强化技能，」标签，其余逐字。
        rows = self.live["ability"]["1599943"]
        self.assertFalse([r for r in rows if r[5] == "0" and r[47] in M.SWITCH_KINDS])
        self.assertEqual(EXPECTED["desc_override_tweyen_light_3"].split("\n")[2],
                         M.PANELS_BY_CAS["desc_override_tweyen_light_3"]["before"][3]
                         .replace("光属性共鸣时：强化技能，", "光属性共鸣时，"))
        registered = {(owner[2], owner[3]) for owner in FLAG_OWNER.values() if owner[2]}
        found = {(key, n) for key, text in EXPECTED.items() for n, line in enumerate(text.split("\n"), 1)
                 if "强化『" in line}
        self.assertEqual(found, registered)                    # 返回面板里凡含「强化『」的行都是登记的开关行
        for key in M.PREVIOUS_AFTER:
            self.assertTrue(any(p.startswith("R2") for p in
                                M.text_problems(with_panel(key, after=M.PREVIOUS_AFTER[key]))), key)

    def test_previous_round_differs_only_on_the_registered_lines(self):
        want = {"desc_override_tweyen_light_1": {2}, "desc_override_tweyen_light_3": {3}}
        self.assertEqual(set(M.PREVIOUS_AFTER), set(want))
        for key, lines in want.items():
            previous, after = M.PREVIOUS_AFTER[key], M.PANELS_BY_CAS[key]["after"]
            self.assertEqual(len(previous), len(after))
            self.assertEqual({n for n, (a, b) in enumerate(zip(previous, after), 1) if a != b}, lines, key)
            for n in lines:
                self.assertIn("强化技能，", previous[n - 1])

    def test_dsl_backs_every_string(self):
        both = ("1", "2")
        want = {
            "119989": {lv: dict(changes={"ACAbilityDamageResistance": "added"}, structural=True) for lv in both},
            "119991": {"1": dict(alv=[]), "2": dict(alv=["ACSkillDamage", "CreateNormalAttack"])},
            "129987": {lv: dict(changes={"ACAttackPoint": "stronger", "ACPowerFlipDamage": "stronger"},
                                structural=False) for lv in both},
            "159994": {lv: dict(changes={"ACFrozen": "stronger", "ACParalysis": "stronger"}, structural=False)
                       for lv in both},
            # 杰拉尔：5 个旗号节点的开支差异并起来（命中块 3 处「对决」＋贯穿 / 浮游＋技能伤害提升）。
            "129992": {lv: dict(changes={"ACFlying": "added", "ACPiercing": "added", "ACSkillDamage": "added",
                                         "ACUnique": "added"}, structural=True) for lv in both},
            # 夏琳：命中块开支 = 累积全属性抗性↓ / 攻击力↓ ＋ 麻痹 / 中毒 / 冻结轮盘。
            "139992": {lv: dict(changes={"ACAttackPoint": "added", "ACFrozen": "added", "ACParalysis": "added",
                                         "ACPoison": "added", "ACToleranceOfElement": "added"}, structural=True)
                       for lv in both},
            # 丝缇涅尔：两支抹掉 alv 后同形；威力 = CreateNormalAttack 的 alv，技能伤害提升 = 第2档 ACSkillDamage 的 alv。
            "159995": {"1": dict(changes={}, structural=False, alv=["CreateNormalAttack"]),
                       "2": dict(changes={}, structural=False, alv=["ACSkillDamage", "CreateNormalAttack"])},
            # 冰雪罗尔夫：旗号节点在 Fever 分支里，开支 = 超级Fever 五项 ＋ 再生，另有非状态命令 AddFeverPoint（加 Fever 槽）
            # / CreateRatioHeal（回复）——commands 依据逐个对上强化串措辞。
            "179999": {lv: dict(changes={"ACAbilityDamage": "added", "ACAttackPoint": "added",
                                         "ACDirectDamage": "added", "ACPowerFlipDamage": "added",
                                         "ACRegeneration": "added", "ACSkillDamage": "added"}, structural=True,
                                within=[["ConditionalsFeverMode"]], commands=["AddFeverPoint", "CreateRatioHeal"])
                       for lv in both},
        }
        self.assertEqual(set(want), set(M.FLAG_TEXT))
        for cid, dsl in want.items():
            spec = M.FLAG_TEXT[cid]
            current = THORN_FLAG_TEXT[1] if cid == "159994" else self.live["cas"][spec["string"]][0][0]
            problems, evidence = M.flag_problems(cid, flat(self.live), current)
            self.assertEqual(problems, [], cid)
            self.assertEqual(evidence["dsl"], dsl, cid)
            self.assertEqual(self.outs[cid]["notes"]["skill_flag"]["evidence"], evidence, cid)

    def test_negative_controls(self):
        with self.assertRaises(M.PanelMergeError):             # live 串已不是登记改前（例如重跑自己的输出）
            M.flag_problems("129987", flat(self.live), FLAG_STRINGS["change_skill_ghandagoza"][1])
        data = deepcopy(self.live)
        data["ability"]["1299876"][0][70] = "change_skill_other"          # 开关行指向别的串
        self.assertTrue(self.flag("129987", data))
        data = deepcopy(self.live)
        data["ability"]["1199891"][2][47] = "704"                          # 同键多出一行开关
        self.assertTrue(any("switches" in p for p in self.flag("119989", data)))
        data = deepcopy(self.live)
        data["text"]["119991"][0][4] = "月相讲义"                           # 技能名对不上
        self.assertTrue(self.flag("119991", data))
        data = deepcopy(self.live)
        data["ability"]["1299876"][0][13] = "202"                          # 开关行多了非共鸣前置 ⇒ 面板前缀说不清
        self.assertTrue(any("resonance-only" in p for p in self.flag("129987", data)))
        # 冈达葛萨：开支连「逆境」也加强 / 开支屏障另有差异 ⇒ 强化串与数据不符。
        path = M.FLAG_TEXT["129987"]["programs"][0]
        data = deepcopy(self.live)
        on = M.flag_nodes(data["dsl"][path], 1)[0][2]
        for cond in M._conditions(on):
            if cond[0] == "ACAdversity":
                cond[2][0]["min"] = cond[2][0]["max"] = 0.9
        self.assertTrue(any("ACAdversity" in p for p in self.flag("129987", data)))
        data = deepcopy(self.live)
        on = M.flag_nodes(data["dsl"][path], 1)[0][2]
        [barrier] = _commands(on, "CreateBarrier")
        barrier[2][0]["min"] = barrier[2][0]["max"] = 0.5
        self.assertTrue(any("beyond" in p for p in self.flag("129987", data)))
        # 碧安卡：开支不再降能力伤害抗性。
        path = M.FLAG_TEXT["119989"]["programs"][1]
        data = deepcopy(self.live)
        M.flag_nodes(data["dsl"][path], 1)[0][2] = ["Block", []]
        self.assertTrue(self.flag("119989", data))
        node = M.flag_nodes(data["dsl"][path], 1)[0]
        self.assertEqual(M.branch_changes(node[2], node[3]), ({}, False))
        # 索恩：开支冻结短于关支 ⇒ 不是强化。
        path = M.FLAG_TEXT["159994"]["programs"][0]
        data = deepcopy(self.live)
        on = M.flag_nodes(data["dsl"][path], 1)[0][2]
        for cond in M._conditions(on):
            if cond[0] == "ACFrozen":
                cond[1][0]["min"] = cond[1][0]["max"] = 60
        self.assertTrue(any("ACFrozen" in p for p in self.flag("159994", data)))
        # 妮可拉：alv 挂到别的构造上 / 技能树里出现旗号节点。
        path = M.FLAG_TEXT["119991"]["programs"][1]
        data = deepcopy(self.live)
        other = next(cond for cond in M._conditions(data["dsl"][path])
                     if cond[0] != "ACSkillDamage" and len(cond) > 2 and isinstance(cond[2], list) and cond[2]
                     and isinstance(cond[2][0], dict))
        other[2][0]["alv_min"] = other[2][0]["alv_max"] = 0.1
        self.assertTrue(any("alv carriers" in p for p in self.flag("119991", data)))
        data = deepcopy(self.live)
        data["dsl"][path].append(["ConditionalsChangeSkillFlag", 1, ["Block", []], ["Block", []]])
        self.assertTrue(any("alv-only" in p for p in self.flag("119991", data)))
        with self.assertRaises(M.PanelMergeError):
            unit("119991")["revise"](reader(data))
        # 串的写法：面板开关行不同文 / 没点技能名、带数字 / 写了开关条件。
        spec = deepcopy(M.FLAG_TEXT["119989"])
        try:
            M.FLAG_TEXT["119989"]["after"] = "强化『绯焰实习·幼龙点名』：幼龙吐息降低全场敌人的攻击力"
            self.assertTrue(any("line 2" in p for p in self.flag("119989")))
            M.FLAG_TEXT["119989"]["after"] = "强化技能：降低全场敌人的能力伤害抗性20%"
            got = self.flag("119989")
            self.assertTrue(any("does not open" in p for p in got) and any("numbers" in p for p in got), got)
            M.FLAG_TEXT["119989"]["after"] = "强化『绯焰实习·幼龙点名』：火属性共鸣时降低全场敌人的能力伤害抗性"
            self.assertTrue(any("共鸣" in p for p in self.flag("119989")))
        finally:
            M.FLAG_TEXT["119989"] = spec
        # 面板里含「强化『」的行必须是登记的开关行。
        spec = deepcopy(M.FLAG_TEXT["129987"])
        try:
            M.FLAG_TEXT["129987"]["line"] = 2
            with self.assertRaisesRegex(M.PanelMergeError, "not registered"):
                unit("129987")["revise"](reader(self.live))
        finally:
            M.FLAG_TEXT["129987"] = spec
        self.assertEqual(unit("129987")["revise"](reader(self.live))["cas"], self.outs["129987"]["cas"])

    def test_skill_descriptions_carry_no_enhanced_effects(self):
        """R3：四人的技能说明（character_text c5/c7、action_skill 两档 c1）只写技能本体，不写强化后的效果。"""
        markers = ("强化后", "不受此限", "担任队长", "共鸣且", "共鸣时", "强化技能", "强化时", "主位", "超级Fever")
        for key, owner in FLAG_OWNER.items():
            cid = owner[0]
            code = M.identity(cid)[0]
            # 有技能说明输出的（索恩 / 冰雪罗尔夫）看改后五处，其余看 live（本轮不改）。
            out = self.outs[cid] if cid in DESC_OUT else {"text": self.live["text"], "action": self.live["action"],
                                                         "server_text": {}}
            texts = [out["text"][cid][0][c] for c in (5, 7)]
            texts += [fields[1] for _, fields in out["action"][code]]
            texts += [out["server_text"][cid][0][c] for c in (5, 7)] if out["server_text"] else []
            for text in texts:
                for marker in markers:
                    self.assertNotIn(marker, text, (cid, marker))


class NewFlagUnitTests(Base):
    """技能强化条目规范新增的 4 人（129992 / 139992 / 159995 / 179999）：强化串逐字、flag_problems 的三个可选依据
    （nodes / carriers / within）正反例、自动面板（该槽无覆盖键）、冰雪罗尔夫技能说明删段（R3）与生成器 / 镜像。"""
    NEW = ("129992", "139992", "159995", "179999")

    def flag(self, cid: str, data) -> list[str]:
        return M.flag_problems(cid, flat(data), M.FLAG_TEXT[cid]["before"])[0]

    def test_outputs_are_exactly_the_strings(self):
        for cid in self.NEW:
            key = next(k for k, owner in FLAG_OWNER.items() if owner[0] == cid)
            self.assertEqual(self.outs[cid]["cas"], {key: [[FLAG_STRINGS[key][1]]]}, cid)
            self.assertEqual(self.live["cas"][key], [[FLAG_STRINGS[key][0]]], cid)
            self.assertEqual(M.unit_capabilities(cid), [], cid)
            notes = self.outs[cid]["notes"]
            self.assertEqual((notes["capabilities"], notes["combat_rows_modified"]), ([], False), cid)
        # 夏琳：串里不再写「雷属性共鸣时」，「迟缓」按数据（ACFrozen）改「冻结」。
        charlene = FLAG_STRINGS["change_skill_artificialeye_sniper_moon"]
        self.assertEqual(charlene[0].replace("雷属性共鸣时强化技能：", "强化『桂影·望月三千』：").replace("迟缓", "冻结"),
                         charlene[1])
        # 丝缇涅尔：只换格式（『』/「」），内容不变。
        stinel = FLAG_STRINGS["change_skill_still_obstinator_moon"]
        self.assertEqual(re.sub(r"[「」『』]", "", stinel[0]), re.sub(r"[「」『』]", "", stinel[1]))

    def test_wt26_description_drops_only_the_enhanced_segment(self):
        out = self.outs["179999"]
        self.assertEqual(M.DESC_TRIM["179999"]["desc"], WT26_DESC)
        for kind in ("text", "server_text"):
            self.assertEqual((self.live[kind]["179999"][0][5], self.live[kind]["179999"][0][7]), (WT26_DESC[0],) * 2)
            want = deepcopy(self.live[kind]["179999"])
            want[0][5] = want[0][7] = WT26_DESC[1]
            self.assertEqual(out[kind]["179999"], want, kind)
        want = [(inner, [WT26_DESC[1] if col == 1 else cell for col, cell in enumerate(fields)])
                for inner, fields in self.live["action"]["black_wolf_knight_wt26"]]
        self.assertEqual([(inner, list(fields)) for inner, fields in out["action"]["black_wolf_knight_wt26"]], want)
        self.assertEqual([fields[7] for _, fields in out["action"]["black_wolf_knight_wt26"]],
                         list(WT26_PROGRAMS.values()))
        self.assertEqual(WT26_DESC[0].replace(M.DESC_TRIM["179999"]["removed"], ""), WT26_DESC[1])
        self.assertTrue(M.DESC_TRIM["179999"]["removed"].startswith("／火属性共鸣时，自身在主位且于Fever状态中使用："))
        self.assertTrue(WT26_DESC[1].endswith("队伍全体贯通(12.5秒) ※技能无后摇"))       # 不留孤立「／」
        self.assertEqual(panel_problems(WT26_DESC[1]), [])
        problems, evidence = M.desc_trim_problems("179999", flat(self.live))
        self.assertEqual(problems, [])
        removed = ["火属性共鸣时，自身在主位且于Fever状态中使用", "Fever槽增加200", "提升350%(10秒)",
                   "最大生命值5%", "再生效果(10秒)"]
        self.assertEqual(evidence, {lv: dict(removed_from_switch_branch=removed,
                                             kept_from_base=["提升150%", "贯通(12.5秒)"]) for lv in ("1", "2")})
        self.assertEqual(self.outs["179999"]["notes"]["desc_trim"]["evidence"], evidence)

    def test_wt26_description_negative_controls(self):
        for kind, mutate in (("text", lambda rows: rows[0].__setitem__(5, WT26_DESC[1])),    # 已改过 / 被别处改过
                             ("server_text", lambda rows: rows[0].__setitem__(7, WT26_DESC[1])),
                             ("action", lambda rows: rows[1][1].__setitem__(1, WT26_DESC[1]))):
            data = deepcopy(self.live)
            mutate(data[kind]["black_wolf_knight_wt26" if kind == "action" else "179999"])
            with self.assertRaises(M.PanelMergeError, msg=kind):
                M.desc_trim_outputs("179999", flat(data))
            with self.assertRaises(M.PanelMergeError, msg=kind):
                unit("179999")["revise"](reader(data))
        path = WT26_PROGRAMS["1"]
        data = deepcopy(self.live)                                   # 开支 Fever 槽改 300 ⇒ 删掉的「200」无据
        _commands(M.flag_nodes(data["dsl"][path], 1)[0][2], "AddFeverPoint")[0][1][0]["max"] = 300.0
        self.assertTrue(any("Fever槽增加300" in p for p in M.desc_trim_problems("179999", flat(data))[0]))
        data = deepcopy(self.live)                                   # 分支外贯通改 15 秒 ⇒ 留下的「12.5秒」无据
        for cond in M._conditions(data["dsl"][path]):
            if cond[0] == "ACPiercing":
                cond[1][0]["min"] = cond[1][0]["max"] = 900.0
        self.assertTrue(any("kept wording" in p for p in M.desc_trim_problems("179999", flat(data))[0]))
        spec = deepcopy(M.DESC_TRIM["179999"])
        try:                                                         # 删段后留了强化写法 / 孤立标点
            for after in (WT26_DESC[1] + "／火属性共鸣时强化", "／" + WT26_DESC[1], WT26_DESC[1].replace(" ※", "／ ※")):
                M.DESC_TRIM["179999"]["desc"] = (WT26_DESC[0], after)
                self.assertTrue(M.desc_trim_problems("179999", flat(self.live))[0], after)
        finally:
            M.DESC_TRIM["179999"] = spec

    def test_flag_extensions_negative_controls(self):
        # nodes：杰拉尔 5 个旗号节点少一个 ⇒ 拒绝；开支少了「对决」⇒ 差异不符。
        path = M.FLAG_TEXT["129992"]["programs"][0]
        data = deepcopy(self.live)
        node = M.flag_nodes(data["dsl"][path], 1)[0]
        node[0] = "ConditionalsSomethingElse"
        self.assertTrue(any("expected 5" in p for p in self.flag("129992", data)))
        data = deepcopy(self.live)
        for node in M.flag_nodes(data["dsl"][path], 1):
            for cmd in _commands(node[2], "CreateCondition"):
                cmd[2] = [cond for cond in cmd[2] if cond[0] != "ACUnique"] or [["ACFlying", [{"min": 1, "max": 1}]]]
        self.assertTrue(any("switch branches change" in p for p in self.flag("129992", data)))
        # 夏琳：轮盘冻结换成中毒 ⇒ 「冻结」无据。
        path = M.FLAG_TEXT["139992"]["programs"][1]
        data = deepcopy(self.live)
        for cond in M._conditions(M.flag_nodes(data["dsl"][path], 1)[0][2]):
            if cond[0] == "ACFrozen":
                cond[0] = "ACPoison"
        self.assertTrue(any("ACFrozen" in p for p in self.flag("139992", data)))
        # carriers：丝缇涅尔开支除 alv 外另有差异 ⇒ 拒绝；alv 挂到别的构造 ⇒ 拒绝。
        path = M.FLAG_TEXT["159995"]["programs"][0]
        data = deepcopy(self.live)
        [attack] = _commands(M.flag_nodes(data["dsl"][path], 1)[0][2], "CreateNormalAttack")
        attack[6][0]["max"] = 99.0
        self.assertTrue(any("beyond" in p for p in self.flag("159995", data)))
        other = M.FLAG_TEXT["159995"]["programs"][1]
        data = deepcopy(self.live)
        [attack] = _commands(M.flag_nodes(data["dsl"][path], 1)[0][3], "CreateNormalAttack")
        attack[5] = 999                                              # 关支结构另变 ⇒ 不只是 alv 差异
        self.assertTrue(self.flag("159995", data))
        data = deepcopy(self.live)
        for cond in M._conditions(data["dsl"][other]):
            if cond[0] == "ACSkillDamage":
                cond[2][0].pop("alv_min", None), cond[2][0].pop("alv_max", None)
        self.assertTrue(any("alv carriers" in p for p in self.flag("159995", data)))   # 技能伤害提升不再被强化
        # within：冰雪罗尔夫的旗号节点挪出 Fever 分支 ⇒「Fever状态中发动时」无据。
        path = WT26_PROGRAMS["2"]
        data = deepcopy(self.live)
        [fever] = _commands(data["dsl"][path], "ConditionalsFeverMode")
        fever[0] = "ConditionalsHealthPointRatioOf"
        self.assertTrue(any("sit in" in p for p in self.flag("179999", data)))

    def test_wt26_string_names_the_fever_gauge(self):
        """总核对 major：技能说明删掉的「Fever槽增加200」（AddFeverPoint 只在 Fever 分支内旗号 1 开支）按 R2 定性写进
        强化串「增加Fever槽」，不写 200；只比上一稿多这一处。"""
        before, after = FLAG_STRINGS["change_skill_black_wolf_knight_wt26"]
        previous = ("强化『炉心颂歌』：Fever状态中发动时触发超级Fever，提升队伍全体的攻击力、强化弹射伤害、技能伤害、"
                    "直接攻击伤害、能力伤害，并为队伍全体回复生命值、赋予再生效果")
        self.assertEqual(M.FLAG_TEXT["179999"]["after"], after)
        self.assertEqual(previous.replace("发动时触发", "发动时增加Fever槽并触发"), after)
        self.assertIn("Fever槽增加200", M.DESC_TRIM["179999"]["removed"])
        self.assertIn("增加Fever槽", after)
        self.assertIsNone(re.search(r"\d", after))                        # R2：定性，不写数字 / 秒数
        self.assertEqual(panel_problems(after, skill_flag=True), [])
        self.assertEqual(self.outs["179999"]["cas"], {"change_skill_black_wolf_knight_wt26": [[after]]})
        self.assertEqual(self.outs["179999"]["notes"]["skill_flag"]["after"], after)
        self.assertEqual(self.live["cas"]["change_skill_black_wolf_knight_wt26"], [[before]])
        self.assertEqual(M.FLAG_TEXT["179999"]["evidence"]["commands"],
                         {"AddFeverPoint": "增加Fever槽", "CreateRatioHeal": "回复生命值"})

    def test_wt26_commands_negative_controls(self):
        # 两档任一档开支去掉 AddFeverPoint ⇒「增加Fever槽」无据。
        for level, path in WT26_PROGRAMS.items():
            data = deepcopy(self.live)
            on = M.flag_nodes(data["dsl"][path], 1)[0][2]
            for command in _commands(on, "AddFeverPoint"):
                command[0] = "ChangeFieldAssets"
            self.assertTrue(any("adds commands" in p for p in self.flag("179999", data)), level)
        # 开支多出一个未登记的效果命令 ⇒ 串没写它，拒绝。
        path = WT26_PROGRAMS["1"]
        data = deepcopy(self.live)
        on = M.flag_nodes(data["dsl"][path], 1)[0][2]
        _commands(on, "CreateRatioHeal")[0][0] = "CreateRatioAttack"
        self.assertTrue(any("adds commands" in p for p in self.flag("179999", data)))
        # 关支也加 Fever 槽 ⇒ 不再是强化独有，拒绝。
        data = deepcopy(self.live)
        node = M.flag_nodes(data["dsl"][path], 1)[0]
        node[3] = deepcopy(node[2])
        self.assertTrue(any("adds commands" in p for p in self.flag("179999", data)))
        # 强化串漏写「增加Fever槽」（上一稿）⇒ 拒绝，整单元也拒绝。
        spec = deepcopy(M.FLAG_TEXT["179999"])
        try:
            M.FLAG_TEXT["179999"]["after"] = spec["after"].replace("增加Fever槽并", "")
            self.assertTrue(any("AddFeverPoint" in p for p in self.flag("179999", self.live)))
            with self.assertRaisesRegex(M.PanelMergeError, "AddFeverPoint"):
                unit("179999")["revise"](reader(self.live))
        finally:
            M.FLAG_TEXT["179999"] = spec
        self.assertEqual(self.flag("179999", self.live), [])

    def test_auto_panel_slot_must_have_no_override(self):
        for cid in self.NEW:
            self.assertEqual(M.auto_panel_problems(cid, reader(self.live)), [], cid)
            spec = M.FLAG_TEXT[cid]
            key = f"desc_override_{M.identity(cid)[0]}_{spec['key'][len(cid):]}"
            data = deepcopy(self.live)
            data["cas"][key] = [["强化条目"]]
            self.assertTrue(M.auto_panel_problems(cid, reader(data)), cid)
            with self.assertRaisesRegex(M.PanelMergeError, "override exists", msg=cid):
                unit(cid)["revise"](reader(data))

    def test_generators_equal_the_revision(self):
        import wf_gerald_r2_data as GR
        import wf_midautumn_kit_charlene as KC
        import wf_midautumn_kit_stinel as KS
        rose, sniper, still, wt26 = (FLAG_STRINGS[k] for k in (
            "change_skill_unicorn_lancer_rose", "change_skill_artificialeye_sniper_moon",
            "change_skill_still_obstinator_moon", "change_skill_black_wolf_knight_wt26"))
        self.assertEqual((GR.ability3(rose[0]), GR.ability3(rose[1]), GR.ABILITY3, GR.R2_ABILITY3),
                         (rose[1], rose[1], rose[1], rose[0]))
        self.assertEqual(KC.CAS_TEXTS, {KC.CAS_SWITCH: sniper[1]})
        self.assertEqual(KC.CAS_SWITCH, "change_skill_artificialeye_sniper_moon")
        self.assertEqual(KS.CAS_TEXTS[KS.CAS_CHANGE_SKILL], still[1])
        self.assertEqual(KS.CAS_CHANGE_SKILL, "change_skill_still_obstinator_moon")
        for text in (rose[1], sniper[1], still[1], wt26[1]):
            self.assertEqual(panel_problems(text, skill_flag=True), [], text)
        # 冰雪罗尔夫没有生成器：第一批模块的改后值正是本轮的改前（链式一致）。
        import wf_balance_20260927_rolfwt26 as RW
        self.assertEqual((RW.NEW_CAS_TEXT, RW.NEW_DESC, RW.CAS_KEY), (wt26[0], WT26_DESC[0], M.FLAG_TEXT["179999"]["string"]))

    @unittest.skipUnless(all((ROOT / rel).is_file() for rel in M.MIRRORS.values()), "midautumn design mirrors missing")
    def test_new_mirrors_accept_live_and_reject_foreign(self):
        docs = {name: json.loads((ROOT / rel).read_text(encoding="utf-8")) for name, rel in M.MIRRORS.items()}
        want = M.mirror_updates(docs)
        for name, (cid, slot, prefix) in M.FLAG_MIRRORS.items():
            key, (before, _after) = next((k, v) for k, v in FLAG_STRINGS.items() if FLAG_OWNER[k][0] == cid)
            trial = deepcopy(docs)                                   # 镜像是 live 形态 ⇒ 收敛到现稿
            next(r for r in trial[f"{name}_design"]["plan"]["texts"]["custom_ability_string"]["rows"]
                 if r["key"] == key)["text"] = before
            next(e for e in trial[f"{name}_panel"]["abilities"] if int(e["index"]) == slot)["lines"][1]["text"] = \
                prefix + before
            self.assertEqual(M.mirror_updates(trial), want, name)
            for mutate in (lambda d: next(r for r in d[f"{name}_design"]["plan"]["texts"]["custom_ability_string"]
                                          ["rows"] if r["key"] == key).__setitem__("text", "别的"),
                           lambda d: next(e for e in d[f"{name}_panel"]["abilities"]
                                          if int(e["index"]) == slot)["lines"][1].__setitem__("text", "别的")):
                trial = deepcopy(docs)
                mutate(trial)
                with self.assertRaises(M.PanelMergeError, msg=name):
                    M.mirror_updates(trial)


class GeneratorTests(Base):
    def test_miniboss_leader_generator_equals_revise_output(self):
        from wf_miniboss_package import _leader_text
        for cid in M.UNIT_ORDER:
            if cid not in MINIBOSS:
                continue
            key = "desc_override_" + MINIBOSS[cid].code
            self.assertEqual(_leader_text(self.live["leader"][cid]), EXPECTED[key], cid)

    def test_miniboss_ability_generator_equals_revise_output(self):
        from wf_miniboss_text import MAIN, TEXTS, ability_panel_rows, ability_panel_text
        self.assertEqual(MAIN, ICON)
        self.assertEqual(ability_panel_text("149994", 3), EXPECTED["desc_override_one_eyed_rabbit_playable_3"])
        self.assertEqual(ability_panel_text("169993", 1), EXPECTED["desc_override_genin_playable_1"])
        rows = {f"169993{s}": [[f"genin_playable_{s}"]] for s in range(1, 7)}
        self.assertEqual(ability_panel_rows("169993", rows)["desc_override_genin_playable_1"],
                         [[EXPECTED["desc_override_genin_playable_1"]]])
        # 生成器里多行的面板只有本轮拆行的两块，且都已不含「／」。
        multi = {(cid, slot): text for cid, texts in TEXTS.items() for slot, text in enumerate(texts, 1)
                 if "\n" in text}
        self.assertEqual(set(multi), {("149994", 3), ("169993", 1)})
        for text in multi.values():
            self.assertNotIn("／", text)

    def test_miniboss_generator_keeps_different_conditions_apart(self):
        from wf_miniboss_package import _leader_text
        rows = deepcopy(self.live["leader"]["119994"])
        rows[2][34] = "3"                                               # 自身强化弹射伤害行改成限 3 次
        lines = _leader_text(rows).split("\n")
        self.assertEqual(lines, ["赋予全队(火) 攻击力 80%、直接攻击伤害 140%、HP 15%。", lines[1]])
        self.assertIn("自身 强化弹射伤害 80%", lines[1])
        conditional = deepcopy(self.live["leader"]["119995"][3])
        second = deepcopy(conditional)
        second[45], second[46], second[47], second[49], second[50] = "32", "5", "Red", "50000", "50000"
        self.assertEqual(_leader_text([conditional, second]),
                         "技能发动≥1 → 自身 追加连击 5，赋予全队(火) 攻击力 50%。")

    def test_campus_panel_generator(self):
        import wf_campus_panel_text as T
        self.assertEqual(T.panel_descriptions("119989")["a3"], EXPECTED["desc_override_lady_summoner_campus_3"])
        self.assertEqual(T.panel_descriptions("119989")["a1"], EXPECTED["desc_override_lady_summoner_campus_1"])
        flag = "change_skill_lady_summoner_campus_dragon"
        self.assertEqual(T.native_flat_string_rows("119989")[flag], [[FLAG_STRINGS[flag][1]]])

    def test_thorn_kit_generator(self):
        import wf_midautumn_kit_thorn as K
        self.assertEqual(K.override_text(1, "true"), EXPECTED["desc_override_tweyen_light_1"])
        self.assertEqual(K.override_text(2, "true"), EXPECTED["desc_override_tweyen_light_2"])
        self.assertEqual(K.override_text(3, "false"), EXPECTED["desc_override_tweyen_light_3"])
        self.assertEqual(K.override_text(4, "true"), EXPECTED["desc_override_tweyen_light_4"])
        rows = {slot: self.live["ability"][f"159994{slot}"] for slot in (1, 2, 3, 4)}
        for slot, table in rows.items():
            self.assertEqual({r[1] for r in table}, {"false" if slot == 3 else "true"}, slot)
        self.assertEqual((K.CAS_CHANGE_SKILL, K.CHANGE_SKILL_TEXT), (THORN_FLAG, THORN_FLAG_FINAL))
        self.assertEqual(K.CAS_TEXTS, {THORN_FLAG: THORN_FLAG_FINAL})

    @unittest.skipUnless(all((ROOT / rel).is_file() for rel in M.MIRRORS.values()), "midautumn design mirrors missing")
    def test_thorn_skill_description_generator(self):
        """技能说明的生成器 = design/thorn.json 顶层 texts（spec.texts）→ tables 步：character_text 整行由
        ``character_text_row`` 现算、action_skill 各档 c1 = spec.texts[desc<档>]；服务端镜像随 character_text 同步。"""
        from types import SimpleNamespace
        import wf_midautumn_specs as MS
        import wf_seasonal7_tables as T
        spec = MS.get_spec("thorn")
        out = self.outs["159994"]
        self.assertEqual((spec.texts["desc1"], spec.texts["desc2"]), (THORN_DESC[1], THORN_DESC[1]))
        skills = {level: (spec.texts[f"skill{level}"], spec.texts[f"desc{level}"]) for level in ("1", "2")}
        row = T.character_text_row(SimpleNamespace(spec=spec), self.live["text"]["159994"][0], skills,
                                   existing=self.live["text"]["159994"][0])
        self.assertEqual([row], out["text"]["159994"])
        self.assertEqual(out["server_text"]["159994"], out["text"]["159994"])
        self.assertEqual({inner: fields[1] for inner, fields in out["action"]["tweyen_light"]},
                         {level: spec.texts[f"desc{level}"] for level in ("1", "2")})

    @unittest.skipUnless(all((ROOT / rel).is_file() for rel in M.MIRRORS.values()), "midautumn design mirrors missing")
    def test_design_mirrors_are_synced_and_drive_the_kits(self):
        self.assertEqual(M.sync_mirrors(ROOT, write=False), [])
        docs = {name: json.loads((ROOT / rel).read_text(encoding="utf-8")) for name, rel in M.MIRRORS.items()}

        def texts(name):
            return {r["key"]: r["text"] for r in docs[name]["plan"]["texts"]["custom_ability_string"]["rows"]}

        import wf_midautumn_kit_nicola as KN
        nicola = "desc_override_sorceress_teacher_moon_3"
        self.assertEqual(KN._apply_main_icon(texts("nicola_design")[nicola]), EXPECTED[nicola])
        self.assertEqual(docs["nicola_design"]["plan"]["texts"]["desc_override"]["value"][nicola],
                         texts("nicola_design")[nicola])
        mia = "desc_override_tiger_treasure_hunter_moon"
        self.assertEqual(texts("mia_design")[mia], EXPECTED[mia])
        self.assertEqual(docs["mia_design"]["plan"]["leader_ability"]["desc_override"]["value"], EXPECTED[mia])
        for slot in (1, 2, 3, 4):
            key = f"desc_override_tweyen_light_{slot}"
            self.assertEqual(texts("thorn_design")[key], EXPECTED[key])
        self.assertEqual(texts("thorn_design")[THORN_FLAG], THORN_FLAG_FINAL)
        # R2：妮可拉 / 冈达葛萨的强化串与冈达葛萨能力6 面板（kit 读 design json）；妮可拉能力1 自动面板镜像行。
        for name, key in (("nicola_design", "change_skill_sorceress_teacher_moon"),
                          ("ghandagoza_design", "change_skill_ghandagoza")):
            self.assertEqual(texts(name)[key], FLAG_STRINGS[key][1], key)
        self.assertEqual(texts("ghandagoza_design")["desc_override_ghandagoza_6"], EXPECTED["desc_override_ghandagoza_6"])
        nicola1 = next(e for e in docs["nicola_panel"]["abilities"] if int(e["index"]) == 1)
        self.assertEqual(nicola1["lines"][1]["text"],
                         "持有者为主位且火属性共鸣时：" + FLAG_STRINGS["change_skill_sorceress_teacher_moon"][1])
        self.assertEqual(M.NICOLA_PANEL_LINE[1], nicola1["lines"][1]["text"])
        thorn = docs["thorn_design"]
        self.assertEqual((thorn["texts"]["desc1"], thorn["texts"]["desc2"],
                          thorn["plan"]["texts"]["action_skill_desc"]["value"]), (THORN_DESC[1],) * 3)
        skill_lines = [line["text"] for line in docs["thorn_panel"]["skill"]["lines"]]
        self.assertIn("赋予其麻痹效果＋冻结效果＋累积全属性抗性降低效果", skill_lines)
        self.assertFalse([line for line in skill_lines if "迟缓" in line])
        for key in ("desc_override_ghandagoza", "desc_override_ghandagoza_4", "desc_override_ghandagoza_6"):
            self.assertEqual(texts("ghandagoza_design")[key], EXPECTED[key])
        for name, index, key in (("nicola_panel", 3, nicola), ("thorn_panel", 1, "desc_override_tweyen_light_1"),
                                 ("thorn_panel", 2, "desc_override_tweyen_light_2"),
                                 ("thorn_panel", 3, "desc_override_tweyen_light_3"),
                                 ("thorn_panel", 4, "desc_override_tweyen_light_4")):
            entry = next(e for e in docs[name]["abilities"] if int(e["index"]) == index)
            self.assertEqual([line["text"] for line in entry["lines"]],
                             [M._strip_icon(line) for line in EXPECTED[key].split("\n")], (name, index))
        # 技能强化条目规范新增：夏琳 / 丝缇涅尔的设计稿强化串 == kit CAS_TEXTS == revise()；面板镜像能力1 第2行
        # 保留各自原有写法（夏琳 = 强化串原文，丝缇涅尔 = 自动面板前缀 + 强化串）。
        import wf_midautumn_kit_charlene as KC
        import wf_midautumn_kit_stinel as KS
        for name, key, kit, prefix in (("charlene", "change_skill_artificialeye_sniper_moon", KC.CAS_TEXTS, ""),
                                       ("stinel", "change_skill_still_obstinator_moon", KS.CAS_TEXTS,
                                        "持有者为主位且光属性共鸣时：")):
            after = FLAG_STRINGS[key][1]
            self.assertEqual((texts(f"{name}_design")[key], kit[key]), (after, after), name)
            line = next(e for e in docs[f"{name}_panel"]["abilities"] if int(e["index"]) == 1)["lines"][1]
            self.assertEqual(line["text"], prefix + after, name)
        for name in M.MIRRORS:
            self.assertEqual(docs[name][M.MODULE_TAG]["module"], M.SOURCE)

    @unittest.skipUnless(all((ROOT / rel).is_file() for rel in M.MIRRORS.values()), "midautumn design mirrors missing")
    def test_mirror_update_is_idempotent_pure_and_keeps_earlier_batches(self):
        import wf_balance_20260927b_nicola as BN
        import wf_balance_20260927b_thorn as BT
        docs = {name: json.loads((ROOT / rel).read_text(encoding="utf-8")) for name, rel in M.MIRRORS.items()}
        before = deepcopy(docs)
        once = M.mirror_updates(docs)
        self.assertEqual(docs, before)
        self.assertEqual(M.mirror_updates(once), once)
        # 第二批的镜像同步在本轮稿上仍是恒等（面板两种形态都接受）
        self.assertEqual(BN.sync_mirrors(ROOT, write=False), [])
        self.assertEqual(BT.sync_mirrors(ROOT, write=False), [])
        # 第一批夏琳 / 丝缇涅尔的镜像同步同样恒等（夏琳第一批接受并保留本轮强化串；丝缇涅尔第一批不碰强化串）。
        import wf_balance_20260927_charlene as AC
        import wf_balance_20260927_stinel as AS
        self.assertEqual(AC.sync_mirrors(ROOT, write=False), [])
        self.assertEqual(AS.sync_mirrors(ROOT, write=False), [])

    @unittest.skipUnless(all((ROOT / rel).is_file() for rel in M.MIRRORS.values()), "midautumn design mirrors missing")
    def test_mirror_update_accepts_live_and_previous_round_panel_lines(self):
        docs = {name: json.loads((ROOT / rel).read_text(encoding="utf-8")) for name, rel in M.MIRRORS.items()}
        want = M.mirror_updates(docs)
        for index in (1, 2, 3, 4):
            panel = M.PANELS_BY_CAS[f"desc_override_tweyen_light_{index}"]
            previous = M.PREVIOUS_AFTER.get(panel["cas"], panel["after"])                    # R2 之前的合并稿
            for shape in (panel["before"],                                                   # live（改前）
                          tuple(line.replace("光属性共鸣时，", "光属性共鸣时：") for line in panel["after"]),
                          previous,
                          tuple(line.replace("光属性共鸣时，", "光属性共鸣时：") for line in previous)):
                trial = deepcopy(docs)
                entry = next(e for e in trial["thorn_panel"]["abilities"] if int(e["index"]) == index)
                base = entry["lines"][0]
                entry["lines"] = [dict(base, text=M._strip_icon(line)) for line in shape]
                got = next(e for e in M.mirror_updates(trial)["thorn_panel"]["abilities"] if int(e["index"]) == index)
                self.assertEqual([line["text"] for line in got["lines"]],
                                 [line["text"] for line in next(e for e in want["thorn_panel"]["abilities"]
                                                                if int(e["index"]) == index)["lines"]], index)
        trial = deepcopy(docs)
        entry = next(e for e in trial["thorn_panel"]["abilities"] if int(e["index"]) == 4)
        entry["lines"] = [dict(entry["lines"][0], text="别的文字")]
        with self.assertRaises(M.PanelMergeError):
            M.mirror_updates(trial)
        # 技能文字（主会话 C）：镜像是 live 形态（迟缓）⇒ 改成冻结；被别处改过 ⇒ 拒绝。
        trial = deepcopy(docs)
        trial["thorn_design"]["texts"]["desc1"] = THORN_DESC[0]
        trial["thorn_design"]["plan"]["texts"]["action_skill_desc"]["value"] = THORN_DESC[0]
        next(r for r in trial["thorn_design"]["plan"]["texts"]["custom_ability_string"]["rows"]
             if r["key"] == THORN_FLAG)["text"] = THORN_FLAG_TEXT[0]
        next(line for line in trial["thorn_panel"]["skill"]["lines"] if "冻结效果" in line["text"])["text"] = \
            "赋予其麻痹效果＋迟缓效果＋累积全属性抗性降低效果"
        got = M.mirror_updates(trial)
        self.assertEqual((got["thorn_design"], got["thorn_panel"]), (want["thorn_design"], want["thorn_panel"]))
        # R2：强化串镜像是 live 或主会话 C 中间稿（索恩）⇒ 改成现稿；妮可拉能力1 自动面板镜像行是 live ⇒ 改成现稿。
        trial = deepcopy(docs)
        for name, key, text in (("thorn_design", THORN_FLAG, THORN_FLAG_TEXT[1]),
                                ("nicola_design", "change_skill_sorceress_teacher_moon",
                                 FLAG_STRINGS["change_skill_sorceress_teacher_moon"][0]),
                                ("ghandagoza_design", "change_skill_ghandagoza",
                                 FLAG_STRINGS["change_skill_ghandagoza"][0])):
            next(r for r in trial[name]["plan"]["texts"]["custom_ability_string"]["rows"] if r["key"] == key)["text"] = text
        next(r for r in trial["ghandagoza_design"]["plan"]["texts"]["custom_ability_string"]["rows"]
             if r["key"] == "desc_override_ghandagoza_6")["text"] = "\n".join(
            M.PANELS_BY_CAS["desc_override_ghandagoza_6"]["before"])
        next(e for e in trial["nicola_panel"]["abilities"] if int(e["index"]) == 1)["lines"][1]["text"] = \
            M.NICOLA_PANEL_LINE[0]
        self.assertEqual(M.mirror_updates(trial), want)
        for mutate in (lambda d: next(r for r in d["nicola_design"]["plan"]["texts"]["custom_ability_string"]["rows"]
                                      if r["key"] == "change_skill_sorceress_teacher_moon").__setitem__("text", "别的"),
                       lambda d: next(r for r in d["ghandagoza_design"]["plan"]["texts"]["custom_ability_string"]["rows"]
                                      if r["key"] == "change_skill_ghandagoza").__setitem__("text", "别的"),
                       lambda d: next(e for e in d["nicola_panel"]["abilities"]
                                      if int(e["index"]) == 1)["lines"][1].__setitem__("text", "别的")):
            trial = deepcopy(docs)
            mutate(trial)
            with self.assertRaises(M.PanelMergeError):
                M.mirror_updates(trial)
        for mutate in (lambda d: d["thorn_design"]["texts"].__setitem__("desc2", "别的说明"),
                       lambda d: d["thorn_design"]["plan"]["texts"]["action_skill_desc"].__setitem__("value", "别的"),
                       lambda d: next(r for r in d["thorn_design"]["plan"]["texts"]["custom_ability_string"]["rows"]
                                      if r["key"] == THORN_FLAG).__setitem__("text", "别的"),
                       lambda d: d["thorn_panel"]["skill"].__setitem__("lines", [])):
            trial = deepcopy(docs)
            mutate(trial)
            with self.assertRaises(M.PanelMergeError):
                M.mirror_updates(trial)


@unittest.skipUnless((ROOT / "mod-tools/profiles.json").is_file()
                     and (ROOT / ".cdn/cn/character-releases/active.json").is_file(), "local workspaces required")
class CandidateTests(Base):
    def test_packages_are_active_flow_owners(self):
        active = json.loads((ROOT / ".cdn/cn/character-releases/active.json").read_text(encoding="utf-8"))
        owners = {package_id for package_id, _sha in active["base_package_owners"]}
        for u in M.UNITS:
            manifest = ROOT / "work/character_packs" / u["PACKAGES"][0] / "package/manifest.json"
            if not manifest.is_file():
                self.skipTest(f"candidate workspace missing: {u['PACKAGES'][0]}")
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual((str(data["character_id"]), data["code_name"]), (u["CID"], u["CODE"]))
            self.assertIn(data["package_id"], owners, u["CID"])

    def test_candidates_accept_the_revision_dry(self):
        """候选无漂移（REVIEWED_DRIFT={}）；按 stage_batch.Plan.splice 同法在内存里拼接并补认领，finish(apply=False) 不落盘。
        暂存回写后（manifest.snapshot.revision_20260927d.source == 本模块）改为核对候选 == 本次输出。"""
        from wf_character_revision import RevisionCandidate
        import wf_mod_tool as core
        import wf_share_update_codec as X
        text_table, action_table, server_json = ("master/character/character_text.orderedmap",
                                                 "master/skill/action_skill.orderedmap", "cdndata/character_text.json")
        for u in M.UNITS:
            workspace = ROOT / "work/character_packs" / u["PACKAGES"][0]
            manifest_path = workspace / "package/manifest.json"
            if not manifest_path.is_file():
                self.skipTest(f"candidate workspace missing: {u['PACKAGES'][0]}")
            raw = manifest_path.read_bytes()
            current = json.loads(raw)
            ver = u["PACKAGE_VERSION"][u["PACKAGES"][0]]
            cid, code = u["CID"], u["CODE"]
            candidate = RevisionCandidate(ROOT, workspace, character_id=cid, code_name=code,
                                          package_version=ver, snapshot_key=SNAPSHOT,
                                          baseline_factory=lambda *a, **k: None,
                                          reviewed_input_drift=u["REVIEWED_DRIFT"])
            full = self.outs[cid]
            out = full["cas"]
            before = {key: ("\n".join(M.PANELS_BY_CAS[key]["before"]) if key in M.PANELS_BY_CAS
                            else FLAG_STRINGS[key][0]) for key in out}
            table = X.unpack(candidate.read("common", M.CAS))
            texts = X.unpack(candidate.read("common", text_table)) if full["text"] else {}
            actions = X.unpack(candidate.read("common", action_table)) if full["action"] else {}
            server = json.loads(candidate.read("server", server_json)) if full["server_text"] else {}

            def action_of(key):
                return [(inner, list(fields)) for inner, fields in core.decode_action_skill_row(actions[key])]

            staged = (current.get("snapshot", {}).get(SNAPSHOT) or {}).get("source") == M.SOURCE
            want = full if staged else {"text": {k: self.live["text"][k] for k in full["text"]},
                                        "action": {k: self.live["action"][k] for k in full["action"]},
                                        "server_text": {k: self.live["server_text"][k] for k in full["server_text"]}}
            for key, rows in want["text"].items():
                self.assertEqual(X.csv_read(texts[key]), rows, key)
            for key, rows in want["action"].items():
                self.assertEqual(action_of(key), [(inner, list(fields)) for inner, fields in rows], key)
            for key, value in want["server_text"].items():
                self.assertEqual(server[key], value, key)
            if staged:
                self.assertEqual(current["package_version"], ver, cid)
                for key, rows in out.items():
                    self.assertEqual(X.csv_read(table[key]), rows, key)
                continue
            self.assertGreater(version(ver), version(current["package_version"]), cid)
            self.assertEqual(version(ver)[:-1], version(current["package_version"])[:-1], cid)
            self.assertEqual(version(ver)[-1], version(current["package_version"])[-1] + 1, cid)
            for key in out:
                if key in table:                                        # 候选缺键时由暂存拼入
                    self.assertEqual(X.csv_read(table[key]), [[before[key]]], key)
            claims = {t["logical_path"]: t for t in candidate.manifest["tables"] if t["root"] == "common"}
            claim = claims.get(M.CAS)
            owned = set(claim["outer_keys"]) if claim else set()
            for key in out:
                self.assertTrue(key in owned or key.startswith(("desc_override_" + code, "change_skill_" + code)), key)
            table.update({k: X.csv_write(v) for k, v in out.items()})
            candidate.emit("common", M.CAS, X.pack(table))
            if claim is None:
                claim = dict(root="common", logical_path=M.CAS, codec_id="flat", outer_keys=[],
                             inner_keys=[], semantic_claims=[])
                candidate.manifest["tables"].append(claim)
            claim["outer_keys"] = sorted(owned | set(out))
            changed = {("common", M.CAS)}
            if full["text"]:                                            # stage_batch.Plan.splice 同法（候选已认领）
                self.assertTrue(set(full["text"]) <= set(claims[text_table]["outer_keys"]))
                texts.update({k: X.csv_write(v) for k, v in full["text"].items()})
                candidate.emit("common", text_table, X.pack(texts))
                changed.add(("common", text_table))
            if full["action"]:
                self.assertTrue(set(full["action"]) <= set(claims[action_table]["outer_keys"]))
                actions.update({k: core.encode_action_skill_row(v) for k, v in full["action"].items()})
                candidate.emit("common", action_table, X.pack(actions))
                changed.add(("common", action_table))
            for key, value in full["server_text"].items():               # stage_batch.Plan.server_text
                self.assertEqual(key, cid)
                candidate.server_character_row(server_json, value)
                changed.add(("server", server_json))
            candidate.manifest["required_capabilities"] = sorted(
                set(candidate.manifest.get("required_capabilities", [])) | set(u["CAPABILITIES"]))
            evidence = candidate.finish({"dry_run": True}, apply=False)
            self.assertFalse(evidence["applied"])
            self.assertEqual({(f["root"], f["logical_path"]) for f in evidence["changed_files"]}, changed, cid)
            if full["text"]:
                self.assertEqual(X.csv_read(X.unpack(candidate.read("common", text_table))[cid]), full["text"][cid])
                self.assertEqual(json.loads(candidate.read("server", server_json))[cid], full["server_text"][cid])
                actions = X.unpack(candidate.read("common", action_table))
                self.assertEqual(action_of(code), [(i, list(f)) for i, f in full["action"][code]])
            self.assertEqual(raw, manifest_path.read_bytes(), cid)


if __name__ == "__main__":
    unittest.main()

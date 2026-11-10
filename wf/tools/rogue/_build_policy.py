# Source section of rogue_build; loaded in its shared module namespace.
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""wf_rogue_build.py — 生成自制 rush 活动 700099「深渊连战」(M1:每轮不同 boss)。

②层(模板全部克隆自 700007 狂热激战,零新资产):
  rush_event[700099]              事件行(常开 2000→2099,banner/背景复用 combat_diver)
  rush_event_quest_folder[700099] folder 1「深渊连战」(quest_kind=1)
  rush_event_quest[700099]        round 1..N,每轮独立 quest:
                                  c98 战场 = 连战塔素材池(wf_chain_build.build_pool)随机层,
                                  c9-13 view_condition 链住上一轮(§9.3 硬约束),
                                  c67 体力=0,c95 敌等级 80(塔场地×rush 已真机验证),
                                  general boss HP 写入克隆 boss_level.c2；c86 恒 1
                                  (standard 仅允许 ±10% 微调)，atk/tp 仍写 c89-94
  event_list[700099]              kind 11 入口

服务端(静态 import,改后须重启服务端):
  assets/rush_event_quest.json        += 700099001..N
  assets/rush_event_quest_folder.json += 700099 folder 奖励

硬门禁(2026-07-26,关13 water_sphere / 关11 steampunk_wind 两起崩溃后加):
  1. 引用完整性:楼层候选(塔池+全部来源池)须全链可解析
     (quest c98→field_data→zone→boss/zako 代号∈general_boss∪standard_boss∪
     general_zako 三表并集),悬空即剔除;构建产物写入前再复核一遍,断链拒绝产出。
  2. 等级覆盖:standard boss 的等级数据是 standard_boss 内层键,客户端取
     "≥敌等级 c95 的最小键",不存在即 U_50fc52「値 N に対応するキー…」;
     Standard 要求 max(内层键) ≥ enemy_level；General 则先在
     general_boss_variable 取 ≤enemy_level 的档 k，再要求 general_boss
     存在 ≥k 的变体档，两步不得混成直接拿 enemy_level 查后表。
  3. 发布完整性:发布清单从本次实际落盘清单派生;--publish 后核对每个文件
     在 CDN diff 链最新版的字节与 store 一致,缺失/旧字节即报错退出。

用法(项目根,默认 dry-run):
  python mod-tools/wf_rogue_build.py --rounds 10 --seed 20260713
  python mod-tools/wf_rogue_build.py --rounds 10 --write --publish
  python mod-tools/wf_rogue_build.py --check                  # 校验现网 700099 解析链
  python mod-tools/wf_rogue_build.py --check --check-quest-path <bak>   # 校验备份
重摇 boss 阵容 = 换 --seed 重跑(--write --publish),轮数不变时服务端 json 不变可不重启。
"""
import argparse
import copy
import csv
import hashlib
import io
import json
import math
import os
import random
import re
import statistics
import struct
import subprocess
import sys
import zipfile
import zlib
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path

MOD_DIR = os.fspath(Path(__file__).resolve().parents[3])
ROOT = MOD_DIR
from wf.paths import configured_path

def rogue_config_path(name):
    """Read explicit config, local authored config, then reviewed package data."""
    override = configured_path(name.removesuffix(".json"))
    if override is not None:
        return override
    # Preserve explicit legacy caller overrides (including private fixtures).
    checkout = Path(__file__).resolve().parents[3]
    if Path(MOD_DIR).resolve() != checkout:
        return Path(MOD_DIR) / name
    authored = checkout / "work" / "rogue-config" / name
    if authored.is_file():
        return authored
    return Path(__file__).parent / "data" / name


def rogue_config_output_path(name):
    """Return a local authoring destination; never edit package defaults."""
    override = configured_path(name.removesuffix(".json"))
    if override is not None:
        return override
    checkout = Path(__file__).resolve().parents[3]
    if Path(MOD_DIR).resolve() != checkout:
        return Path(MOD_DIR) / name
    return checkout / "work" / "rogue-config" / name


def load_server_asset(name):
    """Read one configured local mirror input without creating directories."""
    with (core.resolve_server_dir() / "assets" / name).open(encoding="utf-8-sig") as stream:
        return json.load(stream)


import wf_mod_tool as core        # noqa: E402
import wf_quest_lib as q          # noqa: E402
import wf_chain_build as cb       # noqa: E402
import wf_dsl                     # noqa: E402
import wf_dsl_sig                 # noqa: E402
from wf.tools.rogue import rogue_bundle as rbb      # noqa: E402
import wf_apk_paths               # noqa: E402
from wf.tools.rogue import orochi_ex as wf_orochi_ex               # noqa: E402
from wf.tools.rogue import abyss_quest_details as quest_details  # noqa: E402
from wf.tools.rogue import abyss_modes as abyss_modes  # noqa: E402
from wf.tools.rogue import abyss_ex as abyss_ex  # noqa: E402

BUILD_MODE = "legacy"
PRIVATE_PREFIX = "mod_rogue_"

def first_boss_round() -> int:
    return 1 if BUILD_MODE == "ex" else 2

EVENT_ID = "700099"
GAUNTLET_HUB_EVENT_IDS = ("700098", "700099", "700100")
GAUNTLET_MIN_PLAYER_RANK = "130"
TOKEN_ID = "2370099"
EVENT_STRING_ID = f"{PRIVATE_PREFIX}gauntlet"
EVENT_NAME = "深渊连战"
Q_EVENT = "master/quest/event/rush_event.orderedmap"
Q_FOLDER = "master/quest/event/rush_event_quest_folder.orderedmap"
Q_QUEST = "master/quest/event/rush_event_quest.orderedmap"
Q_LIST = "master/quest/event/event_list.orderedmap"
Q_CORR = "master/quest/event/rush_event_battle_quest_correction.orderedmap"
TEMPLATE_EVENT = "700007"
ENDLESS_KEY = "99"          # 无尽 quest 内层键/id 尾号(避开 round 键位)


def enforce_gauntlet_player_rank(row: list) -> list:
    """Keep every generated single-player gauntlet quest at rank 130."""
    row[48] = GAUNTLET_MIN_PLAYER_RANK
    return row


def enforce_gauntlet_hub_event_list(event_list: dict) -> dict:
    """The shared EventFolder is authoritative; direct event entries must stay absent."""
    for hub_event_id in GAUNTLET_HUB_EVENT_IDS:
        event_list.pop(hub_event_id, None)
    return event_list


# ---- C8016 素材池黑名单(2026-07-19 真机崩溃实证)----
# 大恶魔(arch_evil)家族:召唤 kit(诅咒之眼/使魔)在运行时出现预载集合之外的
# 元素色替——旧 roll 第10轮(arch_evil_single_tower·暗,c69=5)真机实测 funnel-zako
# 弹幕解析出 enemy_shot_wiry_yellow(雷),而预载端 ActionDslAssetResolver:683 对
# SpawnFunnel 恒用 questsElement 静态解析,黄色变体不在本场清单 → C8016
# 「时间轴数据尚未加载」。数据层无法兜底(单人战 *_multi 槽不预载、zako 无固定
# 元素列),只能整族排除;后续再有 C8016 按服务端 [CRASH] 日志定位楼层加名单。
C8016_BLOCKED_BOSS_PREFIXES = ("arch_evil",)

# ---- 通用随机池的 HP 专用通道排除(2026-08-03 玩家实锤)----
# orochi_ex 的主要血量**不在 boss_level**,而是写死在自己的专用表:
#   phase1_health_point(c24)=75,000,000 / phase3_health_point(c25)=120,000,000
#   (列名由客户端 OrochiExValues:334-335 实锤)。
# 关键在于**这两段相位血完全不吃 quest 的血量修正**:OrochiExSource:54-57 只把它们
# 乘上单人 boss 战折扣 _loc14_,压根没碰 battle_hp_correction_value_boss(那个只作用于
# EnemySourceBase:324 的中段血条);而 rush_event 的 SingleBattleIdKind index=20,
# QuestIdBattleKindTools.isSinglePlayBossBattle 在 case 20 直接 return false
# ⇒ 塔里连 0.55 的单人折扣都吃不到,相位血就是原封不动的 7500万 / 1.2亿。
# 第19关实际血量结构 ≈ 7500万(相位1) + 235,207(中段,唯一吃修正) + 1.2亿(相位3)
#   ≈ 1.95 亿,其中 **99.88% 与塔的任何倍率无关** ⇒ 归一化对它是**零效力**,
#   不是"效力不够"。把 c86 压到下限 0.1 也只减掉 22 万。
# 10 张专用表全扫过,只有 orochi_ex 这一只把血量写死在表里,其余(kraken/五元素球/
# 指挥者/东亚奇廉)都老实走 boss_level,不受影响;普通八岐大蛇 orochi_all_head_*
# 也走 boss_level,照常在池。
# ⇒ 通用评估/替换已由 wf_orochi_ex 同时处理专用表和 boss_level；
#   floor_native_hp 也会把它拆成三段，只给中段应用 quest HP 修正。
#   完整 parent+六子体闭包只通过 native special 专场进入塔；这里仍把它排除出
#   通用随机/移植池，防止绕过专用闭包门禁而只克隆一个 kind=4 父代号。
# 注:玩家同时报的 U_1d93f4 图集崩**证据不支持记在它头上** —— 日志里唯一一次
#   (logs/start-cn-detached.log:747)questId=700099020 是第20关,且发生在 2026-07-30,
#   而含 orochi_ex 的这座塔 2026-08-02 才摇出来;第19关当天连打两次都没崩。
HP_BLOCKED_BOSSES = ("orochi_ex",)
# 练习木桩没有正常攻击行为；它们恰因超大代理 HP 排在候选榜首，绝不能让
# PROXY_CURVE 的假绝对值把它们重排进塔。前缀覆盖普通/无色/炮台/攻击八个变体。
HP_BLOCKED_BOSS_PREFIXES = ("practice_waraboss_tough",)

# 严格模式的重抽政策也进入机器可读验收回执。这样“当前明确不支持”不会只藏在
# 候选池实现里：离线校验器会拒绝删除或放宽这些项目的收据。
STRICT_HP_EXCLUSION_POLICY = (
    {
        "match": "prefix",
        "value": "practice_waraboss_tough",
        "reason": "HP_PROXY_ONLY",
        "action": "reroll",
    },
)
STRICT_HP_NATIVE_SPECIAL_POLICY = (
    {
        "match": "constructor",
        "value": "kraken",
        "family": "kraken",
        "channel": "special_bundle",
        "field_policy": "native_only",
        "closure": "one_victory_bar+two_tentacle_funnels+action_identity",
    },
    {
        "match": "exact",
        "value": "orochi_ex",
        "family": "orochi_ex",
        "channel": "special_bundle",
        "field_policy": "native_only",
        "closure": (
            "parent+six_children+three_hp_phases+"
            "signed_int32_threshold_icon"
        ),
    },
    {
        "match": "constructor",
        "value": "conductor",
        "family": "conductor",
        "channel": "special_bundle",
        "field_policy": "native_only",
        "closure": "one_victory_bar+derived_weapon_durability+action_identity",
    },
    {
        "match": "constructor",
        "value": "touyakiren_ceo",
        "family": "touyakiren_ceo",
        "channel": "special_bundle",
        "field_policy": "native_only",
        "closure": "one_victory_bar+derived_weapon_durability+action_identity",
    },
    {
        "match": "constructor", "value": "water_sphere",
        "family": "water_sphere", "channel": "special_bundle",
        "field_policy": "native_only",
        "closure": "four_phase_parent+two_mandatory_phase1_crystals+four_scaled_phase3_conduits+phase_budget",
    },
    {
        "match": "constructor", "value": "holy_sphere",
        "family": "holy_sphere", "channel": "special_bundle",
        "field_policy": "native_only",
        "closure": "four_phase_parent+two_mandatory_phase1_crystals+five_scaled_phase3_conduits+phase_budget",
    },
    {
        "match": "constructor", "value": "wind_sphere",
        "family": "wind_sphere", "channel": "special_bundle",
        "field_policy": "native_only",
        "closure": "four_phase_parent+three_phase2_mechanic_crystals+one_scaled_phase3_crystal+three_scaled_phase3_micronuclei+phase_budget",
    },
    {
        "match": "constructor", "value": "thunder_sphere",
        "family": "thunder_sphere", "channel": "special_bundle",
        "field_policy": "native_only",
        "closure": (
            "four_phase_parent+three_scaled_phase2_micronuclei+"
            "two_phase3_auxiliaries+three_scaled_phase4_crystals+phase_budgets"),
    },
    {
        "match": "constructor", "value": "fire_sphere",
        "family": "fire_sphere", "channel": "special_bundle",
        "field_policy": "native_only",
        "closure": "four_phase_parent+three_mandatory_phase1_crystals+four_scaled_phase4_conduits+one_full_revival+eight_occurrences+raw_hit_overdamage",
    },
)


def _c8016_safe(bosses: list[str]) -> bool:
    return not any(b.startswith(p) for p in C8016_BLOCKED_BOSS_PREFIXES for b in bosses)


def _hp_scale_safe(bosses: list[str]) -> bool:
    """需 native special 闭包或仍无安全 HP 通道 → 排除通用随机池。"""
    return not any(
        b in HP_BLOCKED_BOSSES
        or any(str(b).startswith(prefix) for prefix in HP_BLOCKED_BOSS_PREFIXES)
        for b in bosses)


def _pool_safe(bosses: list[str]) -> bool:
    """通用候选池总闸，排除崩溃、不可击杀及未闭合的特殊 Boss。"""
    if "shark_score_event" in bosses:
        return False
    return _c8016_safe(bosses) and _hp_scale_safe(bosses)


# ---- 楼层黑名单(2026-07-29 用户真机反馈:第7战抽到宝物域)----
# 宝物域(treasure_cave_area)是采集向关卡:zone 里挂的 owl_multi/treant_single
# 只是布景,没有 boss 战流程,抽到就是一层白给。整族排除出**候选池**;
# 门禁不拦,手动钉选(工坊/布局)仍可用。
FIELD_BLOCKED_PREFIXES = ("treasure_cave",)


def field_blocked(field_id: str) -> bool:
    """候选池黑名单命中?(非 boss 战场地;只影响随机抽取,不影响手动钉选)"""
    return any(str(field_id).startswith(p) for p in FIELD_BLOCKED_PREFIXES)


# boss 元素机制(2026-07-13 逆向实锤):
# general_boss 行 c0 = 元素 kind:0=Inherit(继承 quest)、1火2水3雷4风5光6暗、7=Colorless。
# 客户端 BattleQuestBaseImpl:2416 把 quest 的 battle_recommended_element(c69)作为
# questsElement 传进 ZoneSource → Inherit/Standard boss 的战斗元素 = c69!
# ⇒ c69 策略(2026-07-19 修订,C8016 根因):boss kit(召唤物/特效色替)只在**官方
#   源 quest 的元素配置**下自洽,任意换元素会让运行时色替超出预载集合。因此
#   c69 优先抄官方源 quest 的 battle_recommended_element;查不到再用固定元素
#   boss 查表;都没有才随机。各表列位(客户端生成解析器 parseAtNN 实锤)见
#   _ELEM_COL / field_official_elem_map。
GENERAL_BOSS = "master/battle/boss/general_boss.orderedmap"
STANDARD_BOSS = "master/battle/boss/standard_boss.orderedmap"
GENERAL_ZAKO = "master/battle/zako/general_zako.orderedmap"
FIELD_DATA_T = "master/battle/field_data.orderedmap"
ZONE_T = "master/battle/zone.orderedmap"
BOSS_LEVEL = "master/battle/boss/boss_level.orderedmap"
GENERAL_BOSS_VARIABLE = "master/battle/boss/general_boss_variable.orderedmap"
GENERAL_BOSS_STATE = "master/battle/boss/general_boss_state.orderedmap"
ZAKO_LEVEL = "master/battle/zako/zako_level.orderedmap"
OROCHI = "master/battle/boss/orochi.orderedmap"
OROCHI_EX = wf_orochi_ex.OROCHI_EX_LOGICAL
OROCHI_EX_HEAD = "master/battle/boss/orochi_ex_head.orderedmap"
OROCHI_EX_CHILD_COLUMNS = (34, 35, 36, 105, 106, 107)
OROCHI_EX_CANONICAL_HEADS = (
    "orochi_ex_phase1_left",
    "orochi_ex_phase1_center",
    "orochi_ex_phase1_right",
    "orochi_ex_phase3_left",
    "orochi_ex_phase3_center",
    "orochi_ex_phase3_right",
)
OROCHI_EX_PHASE_CAPACITY_SCHEMA = "wf-orochi-ex-phase-damage-capacity/v1"
OROCHI_EX_PHASE_CARRIER_COVERAGE_RATIO = 1.01
OROCHI_EX_PHASE_CARRIER_FORMAT_MARGIN = 1e-6
STANDARD_FUNNEL = "master/battle/boss/funnel/standard_funnel.orderedmap"

# Client constructor audit (2026-08-25): these families instantiate one
# EnemySourceBase/BossHealthPointGauge from boss_level.  Conductor/CEO weapons
# are derived durability parts, not victory bars.  Kraken's two tentacles are
# funnel enemies, but Kraken.enterDeadState annihilates them, so the parent is
# still the only victory HP bar; both funnel table/level dependencies are
# explicitly checked below.
# Exact row widths and a fully parseable, identity-independent action closure
# are rechecked before admission, so a future schema drift fails closed.
SINGLE_BAR_SPECIAL_SPECS = {
    "kraken": {
        "kind": 2,
        "logical": "master/battle/boss/kraken.orderedmap",
        "columns": 56,
        "label": "克拉肯",
        "auxiliary": "two tentacle funnels annihilated on parent death",
        "funnel_ref_columns": (44, 45),
    },
    "conductor": {
        "kind": 6,
        "logical": "master/battle/boss/conductor.orderedmap",
        "columns": 119,
        "label": "指挥者",
        "auxiliary": "weapon durability scales from source.hp",
    },
    "touyakiren_ceo": {
        "kind": 7,
        "logical": "master/battle/boss/touyakiren_ceo.orderedmap",
        "columns": 122,
        "label": "东亚奇廉 CEO",
        "auxiliary": "weapon durability scales from source.hp",
    },
}
KRAKEN_TENTACLE = "master/battle/boss/funnel/tentacle.orderedmap"
KRAKEN_FUNNEL_LEVEL = "master/battle/boss/funnel_level.orderedmap"

# Sphere constructor proof (client 1.8.1): every family has one final parent
# death condition. Water/Holy/Fire additionally gate phase 1 behind crystals.
# Damage conduits do not add a second victory bar.  Their own HP is either a
# hard transfer budget (Thunder rejects overdamage) or a lower bound whose raw
# hit can be forwarded in full (Water/Holy/Wind/Fire accept overdamage).  Every
# conduit HP row must nevertheless scale with the parent: this preserves the
# native durability ratio and, for capped transfers, prevents a phase deadlock.
# Fire's four phase-4 micronuclei each restore to max HP once; its contract thus
# records eight actual HP-bar occurrences instead of deduplicating by code.
SPHERE_SPECS = {
    "water_sphere": {
        "kind": 9, "canonical": "water_sphere_single",
        "logical": "master/battle/boss/water_sphere.orderedmap",
        "columns": 373, "label": "水之球体",
        "embedded": (
            {"phase": "phase[1].crystal", "level_columns": (167, 167),
             "role": "mandatory_gate", "victory": True},
        ),
        "aux_groups": (
            {"table": "water_sphere_micronucleus", "columns": 62,
             "id_columns": (306, 307, 308, 309), "level_parent_column": 298,
             "phase": "phase[3].micronucleus", "role": "damage_conduit",
             "scale_with_parent": True},
        ),
        # Sphere accepts micronucleus damage only in phase 3.  c29/c30 are the
        # 90%/50% entry/exit thresholds; four native 10% micronuclei exactly
        # cover the transition even without relying on raw-hit overdamage.
        "phase_contracts": (
            {"phase": "phase[3].micronucleus", "entry_column": 29,
             "exit_column": 30, "expected_entities": 4,
             "expected_completion_count": 4, "overdamage": True},
        ),
        "lifecycle_contracts": (
            {"source_phase": 1, "target_phase": 2,
             "trigger": "mandatory_gate_clear",
             "member_phases": ("phase[1].crystal",),
             "expected_entities": 2, "expected_completion_count": 2},
            {"source_phase": 2, "target_phase": 3,
             "trigger": "parent_hp_threshold", "threshold_column": 29},
            {"source_phase": 3, "target_phase": 4,
             "trigger": "child_damage_threshold",
             "budget_phase": "phase[3].micronucleus"},
            {"source_phase": 4, "target_phase": None,
             "trigger": "parent_hp_depleted"},
        ),
    },
    "holy_sphere": {
        "kind": 10, "canonical": "holy_sphere_single",
        "logical": "master/battle/boss/holy_sphere.orderedmap",
        "columns": 393, "label": "圣之球体",
        "embedded": (
            {"phase": "phase[1].crystal", "level_columns": (184, 184),
             "role": "mandatory_gate", "victory": True},
        ),
        "aux_groups": (
            {"table": "water_sphere_micronucleus", "columns": 62,
             "id_columns": (326, 327, 328, 329, 330),
             "level_parent_column": 317,
             "phase": "phase[3].micronucleus", "role": "damage_conduit",
             "scale_with_parent": True},
        ),
        # Holy uses the same shared micronucleus level channel.  Its five 10%
        # children exactly cover the c29=90% -> c30=40% phase-3 transition.
        "phase_contracts": (
            {"phase": "phase[3].micronucleus", "entry_column": 29,
             "exit_column": 30, "expected_entities": 5,
             "expected_completion_count": 5, "overdamage": True},
        ),
        "lifecycle_contracts": (
            {"source_phase": 1, "target_phase": 2,
             "trigger": "mandatory_gate_clear",
             "member_phases": ("phase[1].crystal",),
             "expected_entities": 2, "expected_completion_count": 2},
            {"source_phase": 2, "target_phase": 3,
             "trigger": "parent_hp_threshold", "threshold_column": 29},
            {"source_phase": 3, "target_phase": 4,
             "trigger": "child_damage_threshold",
             "budget_phase": "phase[3].micronucleus"},
            {"source_phase": 4, "target_phase": None,
             "trigger": "parent_hp_depleted"},
        ),
    },
    "wind_sphere": {
        "kind": 11, "canonical": "wind_sphere",
        "logical": "master/battle/boss/wind_sphere.orderedmap",
        "columns": 422, "label": "风之球体",
        "embedded": (
            {"phase": "phase[2].crystal", "level_columns": (187, 226, 265),
             # Sphere.canAcceptCrystalDamage is false in phase 2.  These three
             # crystals are attack/weak-point mechanics, not parent conduits.
             "role": "mechanic_auxiliary", "victory": False},
            {"phase": "phase[3].crystal", "level_columns": (337,),
             "role": "damage_conduit", "victory": False,
             "scale_with_parent": True},
        ),
        "aux_groups": (
            {"table": "wind_sphere_micronucleus", "columns": 79,
             "id_columns": (329, 330, 331), "level_column": 5,
             "phase": "phase[3].micronucleus", "role": "damage_conduit",
             "scale_with_parent": True},
        ),
        # Phase 3 accepts both child kinds.  Three 10% micronuclei reach the
        # c30=60% -> c31=30% boundary; the concurrently present 5% crystal is
        # retained as a fourth conduit occurrence and scales by the same ratio.
        "phase_contracts": (
            {"phase": "phase[3].damage_conduits",
             "member_phases": (
                 "phase[3].crystal", "phase[3].micronucleus"),
             "entry_column": 30, "exit_column": 31,
             "expected_entities": 4, "expected_completion_count": 3,
             "overdamage": True},
        ),
        "lifecycle_contracts": (
            {"source_phase": 1, "target_phase": 2,
             "trigger": "parent_hp_threshold", "threshold_column": 29},
            {"source_phase": 2, "target_phase": 3,
             "trigger": "parent_hp_threshold", "threshold_column": 30},
            {"source_phase": 3, "target_phase": 4,
             "trigger": "child_damage_threshold",
             "budget_phase": "phase[3].damage_conduits"},
            {"source_phase": 4, "target_phase": None,
             "trigger": "parent_hp_depleted"},
        ),
    },
    "thunder_sphere": {
        "kind": 12, "canonical": "thunder_sphere",
        "logical": "master/battle/boss/thunder_sphere.orderedmap",
        "columns": 221, "label": "雷之球体", "embedded": (),
        "aux_groups": (
            {"table": "thunder_sphere_micronucleus", "columns": 139,
             "id_columns": (123, 124, 125), "level_column": 5,
             "phase": "phase[2].micronucleus", "role": "damage_conduit",
             "scale_with_parent": True},
            {"table": "thunder_sphere_phase3_crystal", "columns": 28,
             "id_columns": (205, 206), "level_column": 5,
             "phase": "phase[3].crystal", "role": "mechanic_auxiliary"},
            {"table": "thunder_sphere_phase4_crystal", "columns": 58,
             "id_columns": (217, 218, 219), "level_column": 5,
             "phase": "phase[4].crystal", "role": "damage_conduit",
             "scale_with_parent": True},
        ),
        # ThunderSphere/Sphere client proof:
        #   phase 2 accepts only micronucleus damage, rejects overdamage, and
        #   advances at parent ratio c31 after entering at c30.  The three
        #   native children are 4% each, so all three are required.
        #   phase 4 accepts crystal damage, also rejects overdamage, and begins
        #   at c32.  Each native crystal is 30%, so two of three kill the parent.
        "phase_contracts": (
            {"phase": "phase[2].micronucleus", "entry_column": 30,
             "exit_column": 31, "expected_entities": 3,
             "expected_completion_count": 3, "overdamage": False},
            {"phase": "phase[4].crystal", "entry_column": 32,
             "exit_ratio": 0.0, "expected_entities": 3,
             "expected_completion_count": 2, "overdamage": False},
        ),
        "lifecycle_contracts": (
            {"source_phase": 1, "target_phase": 2,
             "trigger": "parent_hp_threshold", "threshold_column": 30},
            {"source_phase": 2, "target_phase": 3,
             "trigger": "child_damage_threshold",
             "budget_phase": "phase[2].micronucleus"},
            {"source_phase": 3, "target_phase": 4,
             "trigger": "parent_hp_threshold", "threshold_column": 32},
            {"source_phase": 4, "target_phase": None,
             "trigger": "child_damage_threshold",
             "budget_phase": "phase[4].crystal"},
        ),
    },
    "fire_sphere": {
        "kind": 13, "canonical": "fire_sphere",
        "logical": "master/battle/boss/fire_sphere.orderedmap",
        "columns": 380, "label": "火之球体", "embedded": (),
        "aux_groups": (
            {"table": "fire_sphere_phase1_crystal", "columns": 104,
             "id_columns": (53, 54, 55), "level_column": 5,
             "phase": "phase[1].crystal", "role": "mandatory_gate",
             "victory": True},
            {"table": "fire_sphere_phase4_micronucleus", "columns": 130,
             "id_columns": (376, 377, 378, 379), "level_column": 5,
             "phase": "phase[4].micronucleus", "role": "damage_conduit",
             "scale_with_parent": True},
        ),
        # Phase4Neutral waits for all four active micronuclei to reach inactive,
        # then Phase4Revive restores every bar to max exactly once.  The parent
        # accepts the full raw hit, so native child HP is not a hard transfer
        # ceiling; preserving all eight occurrence ratios is the safe invariant.
        "phase_contracts": (
            {"phase": "phase[4].micronucleus", "entry_column": 30,
             "exit_ratio": 0.0, "expected_entities": 4,
             "occurrences_per_entity": 2,
             "expected_completion_count": None, "overdamage": True,
             "budget_model": "raw_hit_overdamage"},
        ),
        "lifecycle_contracts": (
            {"source_phase": 1, "target_phase": 2,
             "trigger": "mandatory_gate_clear",
             "member_phases": ("phase[1].crystal",),
             "expected_entities": 3, "expected_completion_count": 3},
            {"source_phase": 2, "target_phase": 3,
             "trigger": "parent_hp_threshold", "threshold_column": 29},
            {"source_phase": 3, "target_phase": 4,
             "trigger": "parent_hp_threshold", "threshold_column": 30},
            {"source_phase": 4, "target_phase": None,
             "trigger": "child_damage_threshold",
             "budget_phase": "phase[4].micronucleus"},
        ),
    },
}
SPHERE_HP_CURSE_FORBIDDEN_FAMILIES = frozenset(SPHERE_SPECS)
SPHERE_AUX_LOGICALS = {
    name: f"master/battle/boss/{name}.orderedmap"
    for name in sorted({
        group["table"]
        for spec in SPHERE_SPECS.values()
        for group in spec["aux_groups"]
    })
}

# ---- 专用表 boss = 第四类合法来源(2026-07-29 八岐大蛇实验通过后放行)----
# 少数官方大型 boss 不在 general/standard/zako 三表,而是各有一张专用表,
# 等级数据也在自己表里(顶层键=boss 代号,内层键=等级档)。zone 里被引用的
# 共 20 个代号,分布在下面 10 张表;orochi_ex_head 那类"子头"只在运行时由
# boss 自己生成、zone 从不直接引用,故不列入。
#
# 放行条件不是"官方能打",而是**等级档位**——两次真机实证卡出了分界线:
#   ① orochi_ex(专用表仅 100 档)@敌等级 100 → 通关(1.4.234 第3战实验);
#   ② water_sphere_single(同样仅 100 档)@敌等级 90 → U_50fc52 崩(关13,2026-07-26)。
# 二者数据形态完全一致(都只在 boss_level + 自己的专用表、内层都只有 100),
# 差别只有敌等级 ⇒ 专用表 boss 走 **general 路径的下取整规则**:
# 必须存在 ≤敌等级的档位。只有 100 档的 boss 因此只在敌等级 ≥100 时放行,
# 正好复现 90 崩 / 100 通;kraken(49/100)、orochi_all_head_multi(49/100)
# 这类有低档的则低等级也能出场。判定实现见 boss_level_ok 的 special 段。
SPECIAL_BOSS_TABLES = (
    "master/battle/boss/orochi.orderedmap",
    "master/battle/boss/orochi_ex.orderedmap",
    "master/battle/boss/kraken.orderedmap",
    "master/battle/boss/conductor.orderedmap",
    "master/battle/boss/touyakiren_ceo.orderedmap",
    "master/battle/boss/fire_sphere.orderedmap",
    "master/battle/boss/water_sphere.orderedmap",
    "master/battle/boss/thunder_sphere.orderedmap",
    "master/battle/boss/wind_sphere.orderedmap",
    "master/battle/boss/holy_sphere.orderedmap",
)

_SPECIAL_LV: dict | None = None


def special_boss_levels() -> dict:
    """专用表 boss → 等级档表({code: {等级键: 行}})。进程内缓存。

    这些表是纯官方只读数据(mod 工具从不写它们),所以不必像 gb/sb 那样把
    构建中的内存态透传进来,直接读 store 即可。表缺失静默跳过。"""
    global _SPECIAL_LV
    if _SPECIAL_LV is None:
        out: dict = {}
        for logical in SPECIAL_BOSS_TABLES:
            try:
                tbl = q.load_table(logical)
            except Exception:
                continue
            for code, node in tbl.items():
                if isinstance(node, dict):
                    out[code] = node
        _SPECIAL_LV = out
    return _SPECIAL_LV


_SPECIAL_KIND: dict | None = None


def special_boss_kinds() -> dict:
    """专用表 boss 代号 → BossKind(rbb.KIND_TABLES 反查)。进程内缓存。

    general/standard(kind 0/1/8)不进这张表——它们要读构建中的内存态,
    由 zone_boss_kind_fixer 直接查 gb_t/sb_t。"""
    global _SPECIAL_KIND
    if _SPECIAL_KIND is None:
        out: dict = {}
        for kind, name in rbb.KIND_TABLES.items():
            if kind in (0, 1, 8):
                continue
            logical = rbb.TABLE_LOGICALS.get(name)
            if not logical:
                continue
            try:
                tbl = q.load_table(logical)
            except Exception:
                continue
            for code in tbl:
                out.setdefault(str(code), kind)
        _SPECIAL_KIND = out
    return _SPECIAL_KIND


def zone_boss_kind_fixer(gb_t, sb_t):
    """生成 boss 代号换列时同步校正 BossKind 列的回调。

    zone 每个 boss 槽是 4 列(单人 kind/code + 多人 kind/code,见
    rbb.SLOT_COLUMNS),客户端先读 kind 决定用哪个构造子、再拿 code 去
    **那张表**查行。`--mix` 拼接层把 donor 的 boss 代号换进地形老家的
    zone 行时,历史上只换 code 列、不动 kind 列:一只 general boss 因此
    会坐进 kraken/orochi/*_sphere 的槽里,客户端按 kind 去专表找它必然落空。

    86e27250 新增的 KIND_CODE_MISMATCH 门禁把这条暴露成硬失败——实测
    `--rounds 30 --mix` 八个种子有三个直接 `[ERR] 解析链断裂,拒绝产出`
    (kraken / orochi / water_sphere 各一),而 reroll 收到非零退出码就
    `中止(进度未动)`,表现为「一键重开点了没反应，要点好久才成一次」。

    返回 None = 现有 kind 已经自洽,别动(kind 8 ConcertedBoss 也走
    general_boss 表,不能无脑压成 1)。"""
    special = special_boss_kinds()

    def kind_of(code: str, current_kind) -> int | None:
        code = str(code)
        try:
            cur = int(str(current_kind).strip())
        except (TypeError, ValueError):
            cur = None
        if cur is not None:
            if cur in (1, 8) and code in gb_t:
                return None
            if cur == 0 and code in sb_t:
                return None
            if special.get(code) == cur:
                return None
        if code in gb_t:
            return 1
        if code in sb_t:
            return 0
        return special.get(code)

    return kind_of


# ---- 引用完整性门禁(2026-07-26 关13 water_sphere 真机崩溃根因)----
# 完整解析链:quest 行 c98 → field_data[键] c2 → zone[键] 各 wave 行敌方代号列。
# 客户端 ZoneSourceValues.resolveGeneralBosssAction → GeneralEnemySourceHelper.
# getSurjectivity 逐个解析代号,任一代号查无此表即 U_50fc52 进本崩溃
# (实证:water_sphere 的 boss water_sphere_single 只在 boss_level 有等级数据,
# 三张敌方表全缺 → 崩)。
# ⚠ 官方 boss 分散在 general_boss 和 standard_boss 两张表(steampunk_*_multi /
#   epuration_boss_highest_single / abyss_cloud* / chapter12_boss_story 都在
#   standard_boss),只查 general_boss 会把 7 个正常楼层误判悬空——必须
#   general_boss ∪ standard_boss ∪ general_zako 三表并集判断。
# 列位:boss 槽 = c24-c34 偶数列(单人 24/28/32 + 多人 26/30/34,一并检查),
#   zako 槽 = c2-c20 偶数列(代号只可能在 general_zako);空串/"(None)"=未用。


def check_field_chain(field_id: str, fd: dict, zone: dict,
                      enemies: set[str], zakos: set[str],
                      level: int | None = None,
                      lv_ceil: dict | None = None,
                      lv_floor: dict | None = None,
                      lv_gb: dict | None = None,
                      validation_tables: dict | None = None) -> dict:
    """单 field 全链解析检查(表由调用方注入:store 现状或构建中的内存态)。

    返回 {"ok","field","zone","bosses","zakos","errors"};errors 空 = 全链可解析。

    level 给出时追加 boss 等级覆盖检查(2026-07-26 关11/关16 双实锤,规则不对称):
      standard 路径(lv_ceil=standard_boss 嵌套表):内层键须有 ≥c95 的
        (resolveStandardBosssAction 取≥请求的最小键;关11 wind@90 崩/@80 通);
      general 路径(lv_floor=gv 表 + lv_gb=general_boss 嵌套表)两步:
        ①k = gv 内层键中 ≤c95 的最大者,不存在即崩(关16 gv[100]@90「値 90」);
        ②general_boss[code] 内层须有 ≥k 的键(变体按 k 向上取,关16 gv 取 100
          而 gb 只有 80 →「値 100」;悲魔 k=49/gb[100] 通、水龙 k=80/gb[80] 通)。
        无 gv 条目的 general boss 无实证,不拦。
    违规即 U_50fc52/U_3be147「値 N に対応するキーが見つかりません」。
    """
    out: dict = {"ok": False, "field": field_id, "zone": None,
                 "bosses": [], "zakos": [], "errors": []}
    if not field_id or field_id == "(None)":
        out["errors"].append("quest 未填 field(c98 空)")
        return out
    frow = fd.get(field_id)
    if frow is None:
        out["errors"].append(f"field_data[{field_id}] 缺失")
        return out
    if isinstance(frow, dict):
        out["errors"].append(f"field_data[{field_id}] 是嵌套 map(应为平行)")
        return out
    fc = cells(frow)
    if len(fc) < 3:
        out["errors"].append(f"field_data[{field_id}] 行不足 3 列(缺 zone 键)")
        return out
    zkey = fc[2]
    out["zone"] = zkey
    zn = zone.get(zkey)
    if not isinstance(zn, dict):
        out["errors"].append(
            f"zone[{zkey}] " + ("缺失" if zn is None else "不是嵌套 map"))
        return out
    for wk, wrow in zn.items():
        if isinstance(wrow, dict):
            out["errors"].append(f"zone[{zkey}] wave {wk} 异形嵌套")
            continue
        wc = cells(wrow)
        for i in range(24, min(35, len(wc)), 2):
            code = wc[i]
            if code in ("", "(None)"):
                continue
            out["bosses"].append(code)
            if validation_tables is not None:
                kind_text = wc[i - 1] if i else ""
                try:
                    kind = int(kind_text)
                except (TypeError, ValueError):
                    out["errors"].append(
                        f"zone[{zkey}] wave {wk} c{i - 1} BossKind 非法:{kind_text}")
                    continue
                ref = rbb.BossRef(kind, code)
                if level is None:
                    table_name = rbb.KIND_TABLES.get(kind)
                    table = validation_tables.get(table_name, {}) if table_name else {}
                    if (table_name is None or kind == 5
                            or not isinstance(table, dict) or code not in table):
                        out["errors"].append(
                            f"zone[{zkey}] wave {wk} kind={kind} c{i} boss 无精确来源:{code}")
                else:
                    result = rbb.validate_boss_ref(ref, level, validation_tables)
                    if not result.ok:
                        out["errors"].append(
                            f"zone[{zkey}] wave {wk} kind={kind} c{i} boss {code} "
                            f"在敌等级 {level} 下无法解析:"
                            f"{result.reason or 'UNKNOWN'} {result.detail}".rstrip())
            elif code not in enemies and code not in special_boss_levels():
                out["errors"].append(
                    f"zone[{zkey}] wave {wk} c{i} boss 代号悬空:{code}"
                    "(不在 general_boss/standard_boss/general_zako,也无专用表)")
            elif level is not None and not boss_level_ok(code, level, lv_ceil,
                                                         lv_floor, lv_gb):
                # Legacy callers without the exact BossKind bundle retain the
                # historical code-only gate.  Final build validation injects
                # ``validation_tables`` and never consults the store cache.
                out["errors"].append(
                    f"boss {code} 在敌等级 {level} 下无法解析"
                    "(standard 需 sb 键≥c95;general 需 gv 有 <100 的低档基准、"
                    "有≤c95 的键、且 gb 变体覆盖该键;专用表需有≤c95 的档;"
                    "技能召的 funnel 需有≥c95 的档)")
        for i in range(2, min(22, len(wc)), 2):
            code = wc[i]
            if code in ("", "(None)"):
                continue
            out["zakos"].append(code)
            if code not in zakos:
                out["errors"].append(
                    f"zone[{zkey}] wave {wk} c{i} zako 代号悬空:{code}(不在 general_zako)")
    out["bosses"] = sorted(set(out["bosses"]))
    out["zakos"] = sorted(set(out["zakos"]))
    out["errors"] = list(dict.fromkeys(out["errors"]))
    out["ok"] = not out["errors"]
    return out


# ---- 第六根因:技能召唤物(funnel)的等级覆盖(2026-07-29 关14 真机 U_3be147)----
# 堆栈是 GeneralEnemySourceHelper.getSurjectivity ← ActionDslHandler.resolveActionDsl,
# 即崩在**技能 DSL 里的召唤物**,不是 zone 里的 boss 本体 —— 前五个根因全在查
# boss/zako 表,这条完全在门禁视野外。
# 实证:advent_event_discarded_dragon_dark_4 的 boss `discarded_dragon_dark`
# gv/gb 都有 100 档、门禁全绿,但它召的 `discarded_dragon_dark_funnel` 在
# general_funnel 只有 [20,40,60,80] → 请求 100 时「値 100 に対応するキーが
# 見つかりません」,紧接着 C8013 general_funnel 主表未加载。
# 规则:funnel 走 **ceil**(要有 ≥敌等级的键),与 standard_boss 同款、与 general 相反。
# 归属靠命名约定:funnel 键以 boss 代号打头(discarded_dragon_dark →
# discarded_dragon_dark_funnel / _another / _tower…);查不到关联 funnel 就不拦。
# 全库普查命中 3 个 boss,都封顶 80:discarded_dragon_dark / desert_bonds_middle_boss
# (哈里达尔)/ arc_guardian。
FUNNEL_TABLES = (
    "master/battle/boss/funnel/general_funnel.orderedmap",
    "master/battle/boss/funnel/standard_funnel.orderedmap",
)

_FUNNEL_LV: dict | None = None


def funnel_levels() -> dict[str, list[int]]:
    """funnel 代号 → 等级档(升序);纯官方只读表,进程内缓存。"""
    global _FUNNEL_LV
    if _FUNNEL_LV is None:
        out: dict[str, list[int]] = {}
        for logical in FUNNEL_TABLES:
            try:
                tbl = q.load_table(logical)
            except Exception:
                continue
            for code, node in tbl.items():
                if not isinstance(node, dict):
                    continue
                keys = sorted(int(k) for k in node if str(k).isdigit())
                if keys:
                    out.setdefault(code, keys)
        _FUNNEL_LV = out
    return _FUNNEL_LV


def boss_funnel_ok(code: str, level: int) -> bool:
    """boss 技能召的 funnel 在该敌等级下能否解析(ceil:须有 ≥level 的键)。"""
    for fcode, keys in funnel_levels().items():
        if fcode.startswith(code) and not any(k >= level for k in keys):
            return False
    return True


def boss_level_ok(code: str, level: int,
                  lv_ceil: dict | None, lv_floor: dict | None,
                  lv_gb: dict | None, *, funnel_ok_fn=None,
                  special_levels: dict | None = None) -> bool:
    """单 boss 在指定敌等级下能否解析(规则同 check_field_chain 的等级段)。"""
    # 召唤物先判:本体三表全绿也可能被自己的 funnel 拖崩(关14 实锤)
    funnel_check = funnel_ok_fn if callable(funnel_ok_fn) else boss_funnel_ok
    if not funnel_check(code, level):
        return False
    # 专用表 boss(orochi/kraken/*_sphere/…)优先判定:它们不在三表并集里,
    # 等级档在自己表内,取"≤敌等级的最大档"(general 同款下取整)。
    # 只有 100 档的 boss ⇒ 敌等级须 ≥100(water_sphere@90 崩 / orochi_ex@100 通)。
    special_index = (special_levels if special_levels is not None
                     else special_boss_levels())
    sp_entry = special_index.get(code)
    if isinstance(sp_entry, dict):
        sp_keys = [int(k) for k in sp_entry if str(k).isdigit()]
        return any(k <= level for k in sp_keys) if sp_keys else True
    ceil_entry = (lv_ceil or {}).get(code)
    if isinstance(ceil_entry, dict):
        keys = [int(k) for k in ceil_entry if str(k).isdigit()]
        return not keys or max(keys) >= level
    floor_entry = (lv_floor or {}).get(code)
    if isinstance(floor_entry, dict):
        keys = [int(k) for k in floor_entry if str(k).isdigit()]
        # gv 只有 100 单档 = 客户端缺低档基准,任何等级都崩「値 100 …キーが見つかりません」
        # (2026-07-29 关25 火废龙实锤;风废龙同型。对照:水/雷龙 gv[80] 单档通过、
        #  暗/光龙 gv[20,40,60,80,100] 通过 —— 判据是"最低档是否 <100")
        if keys and min(keys) >= 100:
            return False
        usable = [k for k in keys if k <= level]
        if keys and not usable:
            return False
        if usable:
            gb_entry = (lv_gb or {}).get(code)
            if isinstance(gb_entry, dict):
                gb_keys = [int(x) for x in gb_entry if str(x).isdigit()]
                if gb_keys and max(gb_keys) < max(usable):
                    return False
    return True


# ---- 怪物基础数值归一化(2026-07-29 用户「有些副本数值显著低于其他副本」)----
# `boss_level` 行:c1=hp基数曲线 c2=基数 c3=倍率 c4=**hp修正曲线名**
#                 c7=atk基数曲线 c8=基数 c9=倍率 c10=**atk修正曲线名**
# ⚠ 基数只在**同一条修正曲线内**可比(曲线本身是另一套嵌套容器格式,没解;
#   但 hp 只有 4 条曲线、atk 4 条,组内归一已经能吃掉绝大部分方差)。
# 实测同一条 `hit_hp_boss` 曲线内 230 个 boss:min 17 / 中位 2246 / max 263250,
# **极差 15485×** —— 白虎(460)和闪火必杀巨土俑(114000)差 250 倍,同样的轮次倍率
# 打起来一个是纸一个是墙,这就是"有些副本数值显著低"的根。
# 做法:按 `基数×倍率` 相对**同曲线组中位数**反向补偿,再**夹在 clamp 区间内**
#   —— 不夹的话低端会被放大上千倍,把设计上就该速杀的小体量 boss 变成怪物。
# ---- 敌方成长曲线容器(2026-07-29 逆向成功)----
# `master/battle/enemy/{hp,atk,tp}/*_curve.orderedmap` 用的是和 quest 表**不同**的封装,
# `wf_quest_lib.parse_node` 不认。格式:
#   中间节点 = [4字节 LE 长度][zlib(索引)];**叶子 = 裸 zlib 流**(长度由区间给出,无前缀)
#   索引     = <I count> + count×<II 累积名长, 累积数据长> + 名字拼接
#   子区间基准 = 本节点块的结束位置;第 i 项 = [base+前一项累积, base+本项累积)
# 实证(hit_hp_correction_curve,856B):顶层 3 条曲线 → 每条 11 个等级档 → 叶子是数值字符串。
#   hit_hp_boss lv100 = 78.271875 / non_element = 31.656625 / funnel = 12.808125(差 6 倍)
# `hit_hp_correction_normal` / `_practice` 不在下载表，但它们并非
# “客户端不可见的魔法常量”：安卓与 iOS 都从 APK bundle 中的
# `*_iosbundled` 基表加载。内置快照与冲突门禁见下方。
CURVE_TABLES = {
    "hp": "master/battle/enemy/hp/hit_hp_correction_curve.orderedmap",
    "hp_fix": "master/battle/enemy/hp/fix_hp_basic_curve.orderedmap",
    "atk": "master/battle/enemy/atk/atk_correction_curve.orderedmap",
}
# Three client-default Hit HP correction curves are deliberately absent from
# the downloadable table.  They live in APK ``assets/bundle.zip`` under the
# historical ``*_iosbundled`` logical name on both Android and iOS.  Without
# this base table, 240 ordinary bosses are only comparable through a proxy and
# their absolute HP cannot be audited.
BUNDLED_CURVE_TABLES = {
    "hp": "master/battle/enemy/hp/hit_hp_correction_curve_iosbundled.orderedmap",
}
# 2026-08-26 从 22 份相互独立的 Android/iOS 兼容客户端基线交叉回读：
# 逻辑成员字节均为 786 bytes，SHA-256 完全一致。这份小型快照让
# 无本地 APK 的 CI/dry-run 也能按客户端公式审计 Kraken 和 normal Hit 族。
# 如果显式/自动找到的客户端含有该成员但哈希不同，不会静默
# 相信旧快照，而是 fail-closed，要求先重新提取和审计。
CLIENT_BUNDLED_CURVE_SCHEMA = "wf-client-bundled-curve-baseline/v1"
CLIENT_BUNDLED_HP_CURVE_MEMBER_SHA256 = (
    "713007008fc91f55555eefe72e913380a29664e23b8e0ac2cfdca95e450f5370")
CLIENT_BUNDLED_CURVE_BASELINE = {
    "hp": {
        "hit_hp_correction_funnel": {
            "9": 1.0, "19": 1.155, "29": 1.221, "39": 1.344,
            "49": 1.7556, "59": 4.175797725, "69": 4.982664225,
            "79": 6.47213952, "89": 7.9464, "100": 9.62676,
        },
        "hit_hp_correction_normal": {
            "9": 1.1, "19": 1.3552, "29": 1.5318, "39": 1.8816,
            "49": 2.962575, "59": 8.243889885, "69": 9.669571065,
            "79": 17.24699977, "89": 23.8392, "100": 31.26519,
        },
        "hit_hp_correction_practice": {
            "9": 1.1, "19": 1.3552, "29": 1.5318, "39": 1.8816,
            "49": 2.962575, "59": 8.243889885, "69": 9.669571065,
            "79": 11.45626482, "89": 13.491646245, "100": 17.406576,
        },
    },
}
_CURVES: dict | None = None
_BUNDLED_CURVES: dict | None = None


def client_bundled_curve_baseline_receipt() -> dict:
    """Stable provenance embedded in strict HP audit documents."""
    curves = CLIENT_BUNDLED_CURVE_BASELINE["hp"]
    return {
        "schema": CLIENT_BUNDLED_CURVE_SCHEMA,
        "logical": BUNDLED_CURVE_TABLES["hp"],
        "member_sha256": CLIENT_BUNDLED_HP_CURVE_MEMBER_SHA256,
        "member_size": 786,
        "cross_checked_client_baselines": 22,
        "curves": {
            name: sorted(int(level) for level in levels)
            for name, levels in sorted(curves.items())
        },
    }


def _curve_tree_floats(tree) -> dict:
    """Normalize a parsed ``curve -> level -> value`` tree to floats."""
    if not isinstance(tree, dict):
        return {}
    out: dict = {}
    for curve, levels in tree.items():
        if not isinstance(levels, dict):
            continue
        converted = {}
        for level, value in levels.items():
            try:
                converted[str(level)] = float(value)
            except (TypeError, ValueError):
                continue
        if converted:
            out[str(curve)] = converted
    return out


def _bundled_curve_source() -> Path | None:
    """Locate the configured APK (or a directly extracted ``bundle.zip``)."""
    configured = wf_apk_paths.resolve_explicit_apk(os.environ)
    if configured is not None:
        return configured
    try:
        server_root = core.resolve_server_dir()
    except (FileNotFoundError, ValueError):
        return None
    bundle_dir = server_root / "弹国服"
    direct = bundle_dir / "bundle.zip"
    candidates = list(bundle_dir.glob("*.apk")) if bundle_dir.is_dir() else []
    if direct.is_file():
        candidates.append(direct)
    return (max(candidates, key=lambda path: path.stat().st_mtime)
            if candidates else None)


def _bundle_member_bytes(source: Path, logical: str) -> bytes | None:
    """Read one hashed Android bundle member from an APK or ``bundle.zip``."""
    try:
        with zipfile.ZipFile(source) as outer:
            names = set(outer.namelist())
            if "assets/bundle.zip" in names:
                inner_blob = outer.read("assets/bundle.zip")
                archive = zipfile.ZipFile(io.BytesIO(inner_blob))
            else:
                archive = zipfile.ZipFile(source)
            with archive:
                relative = q.hashed_rel(logical).replace("\\", "/")
                suffix = "/" + relative
                preferred = (
                    f"production/android_bundle/{relative}",
                    f"production/bundle/{relative}",
                    f"production/medium_bundle/{relative}",
                )
                hit = next((name for name in preferred
                            if name in archive.namelist()), None)
                if hit is None:
                    hit = next((name for name in archive.namelist()
                                if name.endswith(suffix)), None)
                return archive.read(hit) if hit is not None else None
    except (OSError, KeyError, zipfile.BadZipFile):
        return None


def bundled_growth_curves() -> dict:
    """Return the audited client base; reject a conflicting local client.

    The downloadable master tables overlay this base in ``growth_curves``.
    Missing APK is safe because the exact member is pinned above; an APK that
    actually carries a different member is not safe and stops the build.
    """
    global _BUNDLED_CURVES
    if _BUNDLED_CURVES is not None:
        return _BUNDLED_CURVES
    source = _bundled_curve_source()
    out = copy.deepcopy(CLIENT_BUNDLED_CURVE_BASELINE)
    if source is not None:
        for kind, logical in BUNDLED_CURVE_TABLES.items():
            raw = _bundle_member_bytes(source, logical)
            if raw is None:
                continue
            digest = hashlib.sha256(raw).hexdigest()
            if digest != CLIENT_BUNDLED_HP_CURVE_MEMBER_SHA256:
                raise ValueError(
                    "CLIENT_BUNDLED_CURVE_CONFLICT "
                    f"{source}:{logical}:sha256={digest},"
                    f"expected={CLIENT_BUNDLED_HP_CURVE_MEMBER_SHA256}")
            try:
                parsed = _curve_tree_floats(q.parse_node(raw))
            except (TypeError, ValueError, zlib.error) as exc:
                raise ValueError(
                    f"CLIENT_BUNDLED_CURVE_PARSE_FAILED {source}:{logical}") from exc
            if parsed != CLIENT_BUNDLED_CURVE_BASELINE.get(kind):
                raise ValueError(
                    "CLIENT_BUNDLED_CURVE_CONTENT_CONFLICT "
                    f"{source}:{logical}")
    _BUNDLED_CURVES = out
    return _BUNDLED_CURVES


def growth_curves() -> dict:
    """{'hp'|'atk': {曲线名: {等级: 值}}};表缺失或解析失败返回空 dict。"""
    global _CURVES
    if _CURVES is not None:
        return _CURVES

    def unpack_idx(buf: bytes):
        cnt = struct.unpack("<I", buf[:4])[0]
        ents = [struct.unpack("<II", buf[4 + i * 8:12 + i * 8]) for i in range(cnt)]
        blob = buf[4 + cnt * 8:].decode("utf-8")
        names, prev = [], 0
        for cum, _e in ents:
            names.append(blob[prev:cum])
            prev = cum
        return names, [e[1] for e in ents]

    def node(raw: bytes, a: int, b: int):
        seg = raw[a:b]
        try:                                    # 中间节点:带 4 字节长度前缀
            n = struct.unpack("<I", seg[:4])[0]
            names, ends = unpack_idx(zlib.decompress(seg[4:4 + n]))
            base, out, prev = a + 4 + n, {}, 0
            for nm, e in zip(names, ends):
                out[nm] = node(raw, base + prev, base + e)
                prev = e
            return out
        except Exception:
            pass
        try:                                    # 叶子:裸 zlib
            return float(zlib.decompress(seg))
        except Exception:
            return None

    bundled = bundled_growth_curves()
    out: dict = {}
    for key, logical in CURVE_TABLES.items():
        merged = {
            curve: dict(levels)
            for curve, levels in bundled.get(key, {}).items()
            if isinstance(levels, dict)
        }
        try:
            raw = q.read_raw(logical)
            tree = node(raw, 0, len(raw))
            # Downloaded rows take precedence over the APK base table, matching
            # the client's MasterTable overlay behavior.
            merged.update(_curve_tree_floats(tree))
        except Exception:
            pass
        out[key] = merged
    _CURVES = out
    return _CURVES


def curve_value(kind: str, name: str, level: int) -> float | None:
    """曲线在指定等级的值:取**第一个 ≥level 的档**(上取整),查不到返回 None。

    ⚠ 2026-08-04 修正:原实现取 ≤level 的最大档(下取整),方向是反的。
    客户端权威实现 GeneralEnemySourceHelper.getSurjectivity:14-30 —— 遍历键,
    `if(key >= level) return table.get(key)`,一个都不满足就
    `throw "値 N に対応するキーが見つかりません"`(=进本崩 U_50fc52,正是
    boss_level_ok 在防的那条)。所以「查不到」对应 throw,返回 None 交调用方处理。

    两条独立反证:①`hit_hp_basic_normal` 最小键 9、`fix_hp_maou_org` 最小键 60,
    下取整语义下 lv<9 / lv<60 会一个键都取不到,而这些曲线明明服务全等级;
    ②方向反了会让归一化补偿虚高——hit_hp_boss 79档=17.247 / 89档=52.391 /
    99档=67.702,lv80 层旧实现读 17.247 而客户端用 52.391(虚高 3.038×)、
    lv90 层虚高 1.292×,正好把 hell 预设 0.9→4.0 的爬坡抵消掉,
    实测三段中位 204M/147M/227M —— 难度曲线**根本没生效**。
    """
    tbl = growth_curves().get(kind, {}).get(name)
    if not isinstance(tbl, dict):
        return None
    keys = sorted((int(k) for k in tbl if str(k).isdigit()))
    usable = [k for k in keys if k >= level]
    if not usable:
        return None
    v = tbl.get(str(usable[0]))
    return float(v) if isinstance(v, (int, float)) else None


_BASE_STATS: dict | None = None


def boss_base_stats(boss_level: dict | None = None) -> dict:
    """boss 代号 → {hp, atk, hpc, atkc};hp/atk = 基数×倍率,hpc/atkc = 修正曲线名。

    只认 `boss_level` 里能解析的行(511/543);standard 系等没有条目的返回缺省,
    归一化时按"无数据不动"处理。"""
    global _BASE_STATS
    use_cache = boss_level is None
    if not use_cache or _BASE_STATS is None:
        out: dict = {}
        if boss_level is not None:
            bl = boss_level
        else:
            try:
                bl = q.load_table("master/battle/boss/boss_level.orderedmap")
            except Exception:
                bl = {}
        for code, leaf in bl.items():
            if isinstance(leaf, dict):
                continue
            cs = cells(leaf)
            if len(cs) < 13:
                continue
            try:
                if cs[0] == "0":
                    hp = float(cs[2]) * float(cs[3])
                    hpc = cs[4]
                    hp_mode = "hit"
                elif cs[0] == "1":
                    # BossLevelValues: EnemyHpCurveKind.Fix(c1,c5,c6)。这里的
                    # c5×c6 已是绝对固定血量，不能再乘 Hit 路径的 K。
                    hp = float(cs[5]) * float(cs[6])
                    hpc = cs[1]
                    hp_mode = "fix"
                else:
                    continue
                out[code] = {"hp": hp, "hpc": hpc, "hp_mode": hp_mode,
                             "atk": float(cs[8]) * float(cs[9]), "atkc": cs[10]}
            except ValueError:
                continue
        if use_cache:
            _BASE_STATS = out
        else:
            return out
    return _BASE_STATS or {}


def true_stat(code: str, kind: str, level: int = 100,
              boss_level: dict | None = None) -> tuple[float, str] | None:
    """(该 boss 在 level 级的真实数值, 归一化分组键)。

    曲线**已知**(hit_hp_boss / _non_element / _funnel、atk_single/multi/...)时
    返回 `基数 × 曲线[level]`,分组键统一为 "*" —— 这批可以**跨曲线组直接比**。
    曲线未知（目前主要是 `atk_correction_normal`）时返回裸基数,
    分组键取曲线名 —— 只能组内相对归一。
    """
    s = boss_base_stats(boss_level).get(code)
    if not s:
        return None
    base = s["hp"] if kind == "hp" else s["atk"]
    cname = s["hpc"] if kind == "hp" else s["atkc"]
    if base <= 0:
        return None
    if kind == "hp" and s.get("hp_mode") == "fix":
        mul = curve_value("hp_fix", cname, level)
        # 客户端 bundled 表中这两条都只有 key100→1；下载表只列两个随等级
        # 变化的例外。曲线 ID 本身钉死语义，不能把“下载表查不到”误当未知。
        if mul is None and cname in {"fix_hp_always_multiple_one",
                                     "fix_hp_basic_normal"}:
            mul = 1.0
        scale = GENERAL_HP_LEVEL_SCALE.get(int(level))
        if mul is None or not scale:
            return None
        # 对外仍保持 true_stat×K=c86 前原生 HP 的既有公式；Fix 值先除 K
        # 只是在统一坐标中表示，floor_native_hp 随即乘回，不会重复放大。
        return base * mul / scale, "*"
    mul = curve_value(kind, cname, level)
    if mul:
        return base * mul, "*"
    # 曲线未知(客户端内置默认):拿**同类里最常见的已知曲线**当代理,把它拉进同一个
    # 可比空间。⚠ 这是个**假设**,不是实锤——但不代理的话两组各用各的锚(一个是真实
    # 血量、一个是裸基数),单位都不一样,残差 379× 纯属构造出来的,比假设更糟。
    proxy = curve_value(kind, PROXY_CURVE[kind], level)
    return (base * proxy, "*") if proxy else (base, cname)


# `standard_boss` 的 master 行只有名字和资源路径；真正 HP 写在 enemy DSL。
# CommonLogicAssetContainer.getEnemyDsl(path) 会追加 `.esdl`，打包逻辑名再追加
# `.amf3.deflate`。TypePackerResource2 的稳定短键为：EnemyDsl.forms=`au`、
# Form.terminationCondition=`d`、TerminationCondition.Health=`T1`。
# StandardEnemySource.as:523-538 只累加 Health.params[0]，最终一次性乘运行任务
# 类型提供的 battle HP scale 和 quest c86 后 floor。真正的单人 Boss 战是 0.55；
# Rush Event 不属于该 battle kind，运行倍率是 1.0。调用方必须显式带入对应语义，
# 不能把单人 Boss 战折扣硬编码成所有 Standard Enemy 的共同规则。
STANDARD_BOSS_BATTLE_HP_SCALE = 0.55
RUSH_EVENT_STANDARD_HP_SCALE = 1.0
_STANDARD_HP_CACHE: dict[str, dict] = {}

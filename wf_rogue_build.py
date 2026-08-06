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
     门禁要求 max(内层键) ≥ enemy_level(general 路径实证宽容,不设限)。
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
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 本脚本所在目录:主仓 = ROOT/mod-tools,平铺导出仓 = 仓根。工具自带的数据文件
# (rogue_*.json / work/)一律以此为基准,两种布局都能找到。
MOD_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOD_DIR)
import wf_quest_lib as q          # noqa: E402
import wf_chain_build as cb       # noqa: E402
import wf_dsl                     # noqa: E402
import wf_dsl_sig                 # noqa: E402
import wf_rogue_bundle as rbb      # noqa: E402

EVENT_ID = "700099"
TOKEN_ID = "2370099"
EVENT_STRING_ID = "mod_rogue_gauntlet"
EVENT_NAME = "深渊连战"
Q_EVENT = "master/quest/event/rush_event.orderedmap"
Q_FOLDER = "master/quest/event/rush_event_quest_folder.orderedmap"
Q_QUEST = "master/quest/event/rush_event_quest.orderedmap"
Q_LIST = "master/quest/event/event_list.orderedmap"
Q_CORR = "master/quest/event/rush_event_battle_quest_correction.orderedmap"
TEMPLATE_EVENT = "700007"
ENDLESS_KEY = "99"          # 无尽 quest 内层键/id 尾号(避开 round 键位)

# ---- C8016 素材池黑名单(2026-07-19 真机崩溃实证)----
# 大恶魔(arch_evil)家族:召唤 kit(诅咒之眼/使魔)在运行时出现预载集合之外的
# 元素色替——旧 roll 第10轮(arch_evil_single_tower·暗,c69=5)真机实测 funnel-zako
# 弹幕解析出 enemy_shot_wiry_yellow(雷),而预载端 ActionDslAssetResolver:683 对
# SpawnFunnel 恒用 questsElement 静态解析,黄色变体不在本场清单 → C8016
# 「时间轴数据尚未加载」。数据层无法兜底(单人战 *_multi 槽不预载、zako 无固定
# 元素列),只能整族排除;后续再有 C8016 按服务端 [CRASH] 日志定位楼层加名单。
C8016_BLOCKED_BOSS_PREFIXES = ("arch_evil",)

# ---- 血量不可缩放黑名单(2026-08-03 玩家「八岐大蛇打不死」实锤)----
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
# ⇒ 现阶段整只排除。**可修但需要新通道**:相位血是绝对值、不吃曲线,直接写目标值即可;
#   客户端零代号硬编码(boss 种类由 zone 的 kind 列 c23/c25='4' 决定),克隆专用表条目安全,
#   代价是要新写"克隆 orochi_ex 专用表 + 换 zone 代号"这条路。想恢复它就实现这条。
# 注:玩家同时报的 U_1d93f4 图集崩**证据不支持记在它头上** —— 日志里唯一一次
#   (logs/start-cn-detached.log:747)questId=700099020 是第20关,且发生在 2026-07-30,
#   而含 orochi_ex 的这座塔 2026-08-02 才摇出来;第19关当天连打两次都没崩。
HP_BLOCKED_BOSSES = ("orochi_ex",)
# 练习木桩没有正常攻击行为；它们恰因超大代理 HP 排在候选榜首，绝不能让
# PROXY_CURVE 的假绝对值把它们重排进塔。前缀覆盖普通/无色/炮台/攻击八个变体。
HP_BLOCKED_BOSS_PREFIXES = ("practice_waraboss_tough",)


def _c8016_safe(bosses: list[str]) -> bool:
    return not any(b.startswith(p) for p in C8016_BLOCKED_BOSS_PREFIXES for b in bosses)


def _hp_scale_safe(bosses: list[str]) -> bool:
    """血量级别与 boss_level 不符 → 归一化失效,排除出候选池。"""
    return not any(
        b in HP_BLOCKED_BOSSES
        or any(str(b).startswith(prefix) for prefix in HP_BLOCKED_BOSS_PREFIXES)
        for b in bosses)


def _pool_safe(bosses: list[str]) -> bool:
    """候选池 boss 级黑名单总闸(C8016 崩 + 血量级别错配)。"""
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
STANDARD_FUNNEL = "master/battle/boss/funnel/standard_funnel.orderedmap"

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
# ⚠ `hit_hp_correction_normal`(240 boss)、`_practice`(14)、`atk_correction_normal`(254)
#   **不在任何曲线表里** —— 是客户端内置默认,读不到;这些只能组内相对归一。
CURVE_TABLES = {
    "hp": "master/battle/enemy/hp/hit_hp_correction_curve.orderedmap",
    "hp_fix": "master/battle/enemy/hp/fix_hp_basic_curve.orderedmap",
    "atk": "master/battle/enemy/atk/atk_correction_curve.orderedmap",
}
_CURVES: dict | None = None


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

    out: dict = {}
    for key, logical in CURVE_TABLES.items():
        try:
            raw = q.store_path(logical).read_bytes()
            tree = node(raw, 0, len(raw))
            out[key] = {k: v for k, v in tree.items() if isinstance(v, dict)}
        except Exception:
            out[key] = {}
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
    曲线未知(`hit_hp_correction_normal` 240 个、`_practice` 14 个、
    `atk_correction_normal` 254 个;客户端内置默认,读不到)时返回裸基数,
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
# StandardEnemySource.as:523-538 只累加 Health.params[0]，最终一次性乘单人折扣 0.55
# 和 quest c86 后 floor。这里严格照消费点读，不做“全树搜数字”式猜测。
STANDARD_BOSS_BATTLE_HP_SCALE = 0.55
_STANDARD_HP_CACHE: dict[str, dict] = {}


def standard_enemy_hp_base(tree: dict) -> dict:
    """从已解析的 standard enemy DSL 返回可审计 HP 基数证据。

    未知 union tag、缺字段、非有限值均 fail closed；T2=Defeat 是合法的非血量
    termination condition，按客户端 switch case 1 忽略。
    """
    forms = tree.get("au") if isinstance(tree, dict) else None
    if not isinstance(forms, list) or not forms:
        raise ValueError("standard enemy DSL 缺少非空 forms(短键 au)")
    terms: list[float] = []
    for index, form in enumerate(forms):
        term = form.get("d") if isinstance(form, dict) else None
        if not isinstance(term, list) or not term or not isinstance(term[0], str):
            raise ValueError(f"standard enemy form[{index}] terminationCondition(d) 非法")
        tag = term[0]
        if tag == "T2":                         # Defeat(index 1)，不贡献 HP
            continue
        if tag != "T1" or len(term) < 2:         # 未知构造必须响亮失败
            raise ValueError(f"standard enemy form[{index}] 未知 termination tag:{tag!r}")
        try:
            value = float(term[1])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"standard enemy form[{index}] Health 参数不是数值") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"standard enemy form[{index}] Health 参数非法:{value!r}")
        terms.append(value)
    if not terms:
        raise ValueError("standard enemy DSL 没有 Health(T1) termination form")
    return {"form_count": len(forms), "health_terms": tuple(terms),
            "base_hp": math.fsum(terms)}


def standard_boss_hp_evidence(code: str, level: int,
                              standard_boss: dict | None = None) -> dict:
    """解析一只 standard boss 在运行等级所选资源的 HP 基数。

    等级选择照 GeneralEnemySourceHelper.getSurjectivity：首个 ``>= level`` 的档。
    返回资源逻辑名、所选档和 forms 证据，供 dry-run 报告逐只回代。
    """
    table = standard_boss if standard_boss is not None else q.load_table(STANDARD_BOSS)
    node = table.get(code)
    if not isinstance(node, dict):
        raise ValueError(f"{code} 不在 standard_boss 或节点不是等级表")
    levels = sorted(int(k) for k in node if str(k).isdigit() and int(k) >= int(level))
    if not levels:
        raise ValueError(f"{code} standard_boss 无 >=lv{level} 的资源档")
    selected = levels[0]
    row = cells(node[str(selected)])
    if len(row) < 2 or not row[1].strip():
        raise ValueError(f"{code}@{selected} standard_boss 缺资源路径")
    base_path = row[1].strip()
    logical = (base_path if base_path.endswith(".esdl.amf3.deflate")
               else base_path + ".esdl.amf3.deflate")
    cached = _STANDARD_HP_CACHE.get(logical)
    if cached is None:
        raw = q.store_path(logical).read_bytes()
        try:
            unpacked = zlib.decompress(raw, -15)
        except zlib.error as exc:
            raise ValueError(f"{logical} 不是 raw-deflate enemy DSL") from exc
        parsed = wf_dsl.parse_dsl(unpacked).get("tree")
        cached = standard_enemy_hp_base(parsed)
        _STANDARD_HP_CACHE[logical] = cached
    return dict(cached, code=code, selected_level=selected, logical=logical)


# 用户给定的 event_quest 真血量换算档；只接受已逆向确认的六个运行等级。
# 真血量(general/special 且走 boss_level) = true_stat(...)[0] × K[level] × c86。
GENERAL_HP_LEVEL_SCALE = {
    79: 2250.0, 80: 2250.0,
    89: 2362.5, 90: 2362.5,
    99: 2475.0, 100: 2475.0,
}


def floor_native_hp(bosses, level: int, standard_boss: dict | None = None,
                    boss_level: dict | None = None) -> dict:
    """返回该层所有实际 boss 实例在 c86 前的 HP 及证据。

    调用方必须传单人战实际槽(c24/28/32)；镜像消歧在 `_zone_pick` 完成。
    此处不按 code 去重：跨 wave / 不同实体槽允许同代号真实出场两次，须逐只相加。
    任一实例不可解析就把整层标成 unverifiable，绝不拿部分和冒充总血量。
    """
    table = standard_boss if standard_boss is not None else q.load_table(STANDARD_BOSS)
    components: list[dict] = []
    reasons: list[str] = []
    for code in map(str, bosses):
        if code in table:
            try:
                evidence = standard_boss_hp_evidence(str(code), int(level), table)
                components.append({"code": str(code), "kind": "standard",
                                   "evidence_kind": "absolute",
                                   "native_hp": round(
                                       float(evidence["base_hp"])
                                       * STANDARD_BOSS_BATTLE_HP_SCALE, 6),
                                   "evidence": evidence})
            except (FileNotFoundError, KeyError, TypeError, ValueError, zlib.error) as exc:
                components.append({"code": str(code), "kind": "standard",
                                   "native_hp": None, "error": str(exc)})
                reasons.append(f"{code}:{exc}")
            continue
        stat = true_stat(str(code), "hp", int(level), boss_level)
        scale = GENERAL_HP_LEVEL_SCALE.get(int(level))
        if stat is None or scale is None:
            why = ("boss_level/曲线不可解析" if stat is None
                   else f"lv{level} 的 K 未经确认")
            components.append({"code": str(code), "kind": "unknown",
                               "native_hp": None, "error": why})
            reasons.append(f"{code}:{why}")
            continue
        stat_source = boss_base_stats(boss_level).get(str(code), {})
        hp_curve_kind = str(stat_source.get("hp_mode") or "hit")
        # Hit 的 correction 曲线查不到时，true_stat 会按既有 PROXY_CURVE 代理；
        # 这只能用于同组相对排序，绝不能在报告里冒充绝对血量证据。
        evidence_kind = "absolute"
        if (hp_curve_kind == "hit"
                and curve_value("hp", str(stat_source.get("hpc") or ""),
                                int(level)) is None):
            evidence_kind = "proxy"
        components.append({"code": str(code), "kind": "general",
                           "hp_curve_kind": hp_curve_kind,
                           "evidence_kind": evidence_kind,
                           # 数据层是十进制；消掉二进制浮点乘 K 后的
                           # 58_939_649.99999999 之类伪差，便于审计逐项对账。
                           "native_hp": round(float(stat[0]) * scale, 6),
                           "true_stat": float(stat[0]), "k": scale})
    verified = bool(components) and not reasons
    total = (math.fsum(float(c["native_hp"]) for c in components)
             if verified else None)
    return {"native_hp": total, "components": components, "verified": verified,
            "absolute_verified": (verified and all(
                c.get("evidence_kind") == "absolute" for c in components)),
            "reason": "; ".join(reasons) if reasons else None}


def _true_hp_at_c86(native: dict, c86: float) -> float:
    """用客户端各族的取整位置回代真 HP。"""
    total = 0.0
    for component in native.get("components") or []:
        hp = float(component["native_hp"]) * float(c86)
        total += (float(math.floor(hp))
                  if (component.get("kind") == "standard"
                      or component.get("hp_curve_kind") == "fix") else hp)
    return total


def solve_floor_hp_record(r: int, n: int, native: dict, *,
                          base_duration_s: float, duration_s: float,
                          curse_hp: float, raw_c86: float,
                          family: str, target: float | None = None) -> dict:
    """分别审计无诅咒基线与最终实战 HP，血量/时限诅咒绝不被反解抵消。

    baseline_c86 只由几何目标和 quest 原始时限反解；落表 c86 再乘
    curse_hp。最终时限只用于 realized_dps，不能回头缩放 c86。
    """
    if not native.get("verified") or native.get("native_hp") is None:
        raise ValueError(f"第{r}战原生 HP 未验证:{native.get('reason') or 'unknown'}")
    base_duration = float(base_duration_s)
    duration = float(duration_s)
    hp_mult = float(curse_hp)
    if not all(math.isfinite(v) and v > 0
               for v in (base_duration, duration, hp_mult)):
        raise ValueError(
            f"第{r}战 HP 审计输入非法:base={base_duration_s},"
            f"time={duration_s},curse_hp={curse_hp}")
    target = target_dps(r, n) if target is None else float(target)
    if not math.isfinite(target) or target <= 0:
        raise ValueError(f"第{r}战目标 DPS 非法:{target!r}")
    baseline_c86 = float(fmt(solve_hp_correction(
        target, base_duration, float(native["native_hp"]))))
    # 任务 A 的乘法陷阱在这里封口：攻击组件降档后只要 curse_hp 不变，
    # 最终 c86 / 真 HP / 实战 DPS 就逐项不变。
    c86 = float(fmt(baseline_c86 * hp_mult))
    baseline_true_hp = _true_hp_at_c86(native, baseline_c86)
    true_hp = _true_hp_at_c86(native, c86)
    raw = float(raw_c86)
    if not math.isfinite(raw) or raw <= 0:
        raise ValueError(f"第{r}战原始 c86 非法:{raw_c86}")
    return {"r": r, "family": family, "verified": True,
            "absolute_verified": bool(native.get("absolute_verified")), "native": native,
            "base_duration_s": base_duration, "duration_s": duration,
            "target_dps": target, "curse_hp": hp_mult,
            "baseline_c86": baseline_c86, "c86": c86,
            "baseline_true_hp": baseline_true_hp, "true_hp": true_hp,
            "baseline_dps": baseline_true_hp / base_duration,
            "realized_dps": true_hp / duration,
            "raw_c86": raw, "family_scale": baseline_c86 / raw}


# 未知曲线的代理:hp 用 boss 档(230 个 boss 在用,与 normal 同为 boss 侧修正),
# atk 用 single 档。假设,可调。
PROXY_CURVE = {"hp": "hit_hp_boss", "atk": "atk_single"}


def curve_medians(codes, level: int = 100) -> tuple[dict, dict]:
    """给一批 boss 代号 → 每个归一化分组的中位数(目标锚)。

    曲线已知的全部归入 "*" 组(真实数值可比);未知的按曲线名各自成组。
    """
    hp_g: dict[str, list] = {}
    atk_g: dict[str, list] = {}
    for c in codes:
        for kind, g in (("hp", hp_g), ("atk", atk_g)):
            t = true_stat(c, kind, level)
            if t:
                g.setdefault(t[1], []).append(t[0])
    med = lambda xs: sorted(xs)[len(xs) // 2]        # noqa: E731
    return ({k: med(v) for k, v in hp_g.items()},
            {k: med(v) for k, v in atk_g.items()})


COMPRESS_DEFAULT = {"hp": 1.0, "atk": 0.55}


def stat_normalize(bosses, hp_med: dict, atk_med: dict,
                   lo: float, hi: float, level: int = 100,
                   compress: dict | None = None,
                   hi_by_kind: dict | None = None) -> tuple[float, float]:
    """一层的 (hp 补偿, atk 补偿)。同曲线组中位数 ÷ 本层基数,夹在 [lo, hi]。

    一层多个 boss 时取**基数最大的那个**当代表(血最厚的决定这层的手感)。
    查不到基数(standard 系/专用表)返回 (1.0, 1.0) —— 无数据不瞎补。
    """
    compress = compress or COMPRESS_DEFAULT
    hi_by_kind = hi_by_kind or {}
    fh = fa = 1.0
    for kind, med in (("hp", hp_med), ("atk", atk_med)):
        vals = [t for t in (true_stat(c, kind, level) for c in bosses) if t]
        if not vals:
            continue
        val, grp = max(vals, key=lambda t: t[0])     # 一层多 boss:按最厚的算
        anchor = med.get(grp)
        if not anchor:
            continue
        # **压缩而不是抹平**:指数 1.0 = 完全拉平,0 = 完全不动。
        # 血量可以拉平(极差 2846× 纯属噪声),但**伤害要留高低差**——
        # 全池 atk 极差 86×,一刀切归一会把 134 个削、118 个抬,只剩 15 个没动,
        # boss 之间的"这个打得疼"手感就没了(2026-07-29 用户:不要太高或太低,可以高低有别)。
        # 残余跨度 ≈ 原极差^(1-指数):atk 86^0.4 ≈ 6× 的区间,有别但不致命。
        k = compress[kind]
        f = (anchor / val) ** k if k else 1.0
        f = min(float(hi_by_kind.get(kind, hi)), max(lo, f))
        if kind == "hp":
            fh = f
        else:
            fa = f
    return fh, fa


def stat_anchor(bosses, med: dict, kind: str, level: int) -> tuple[float, float] | None:
    """该层的 (原生数值, 同曲线组中位锚);查不到基数返回 None。

    None = standard 表 boss(无 boss_level 条目)——归一化对它们**无效**,拿到的
    是裸曲线值,原生数值不在审计视野内。返回值有两个用途:
      · None → 走 NOBASE_ATK_CAP + 禁攻击类诅咒
      · 非 None → 真伤指数闸(原生 atk 高的 boss,col 合规也可能每跳爆表)
    与 stat_normalize 同口径:一层多 boss 取基数最大的那个。"""
    best = None
    for c in bosses:
        t = true_stat(c, kind, level)
        if t and med.get(t[1]) and (best is None or t[0] > best[0]):
            best = (t[0], med[t[1]])
    return best


def solve_atk(rec: dict, atk_base: float, atk_growth: float,
              scale: float = 1.0) -> float:
    """只计算曲线×攻击来源×攻击诅咒的真实乘积，不静默夹值。

    ``st_mult`` 只服务 HP/档位；攻击超标由 ``enforce_atk_band`` 显式降档。
    """
    factors = {
        "atk_base": atk_base,
        "atk_growth": atk_growth,
        "scale": scale,
        "ba": rec.get("ba"),
        "curse.atk": (rec.get("curse") or {}).get("atk"),
    }
    for name, raw in factors.items():
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"第{rec.get('r')}战攻击因子 {name} 非数值:{raw!r}") from exc
        if not math.isfinite(value) or value <= 0:
            raise RuntimeError(f"第{rec.get('r')}战攻击因子 {name} 必须为有限正数:{raw!r}")
    try:
        value = (float(atk_base) * (float(atk_growth) ** (int(rec["r"]) - 1))
                 * float(rec["ba"]) * float(scale)
                 * float(rec["curse"]["atk"]))
    except (OverflowError, TypeError, ValueError) as exc:
        raise RuntimeError(f"第{rec.get('r')}战攻击乘积不可计算") from exc
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError(f"第{rec.get('r')}战攻击乘积必须为有限正数:{value!r}")
    return value


def band_stats(cols: list[float]) -> dict:
    """col 分布的三个受检分位(P90 = 最近秩)。闸门与体检读数**共用**这一个口径,
    否则会出现"闸门说过了、体检说超了"的自相矛盾。"""
    s = sorted(cols)
    return {"median": statistics.median(s), "max": s[-1],
            "p90": s[min(len(s) - 1, math.ceil(0.9 * len(s)) - 1)]}


def band_violation(cols: list[float]) -> tuple[str, float] | None:
    """全塔 col 分布是否落进目标带 → (超标项, 实测值) 或 None。"""
    if not cols:
        return None
    got = band_stats(cols)
    for key in ("max", "p90", "median"):
        if got[key] > BAND_TARGET[key] + 1e-9:
            return key, got[key]
    return None


def enforce_atk_band(recs: list[dict], atk_base: float, atk_growth: float,
                     n: int) -> tuple[float, list[str]]:
    """全塔攻击硬闸：先降攻击诅咒，再显式降低该层攻击来源 ``ba``。"""
    if n <= 0:
        raise RuntimeError(f"塔层数必须为正数:{n}")
    scale, log = 1.0, []

    def recalc() -> None:
        for rec in recs:
            rec["atk"] = solve_atk(rec, atk_base, atk_growth, scale)

    def explicit_limit(rec: dict) -> float:
        limit = BAND_TARGET["max"]
        if rec.get("anchor"):
            native, med = map(float, rec["anchor"])
            if (not math.isfinite(native) or not math.isfinite(med)
                    or native <= 0 or med <= 0):
                raise RuntimeError(
                    f"第{rec.get('r')}战真伤锚必须为有限正数:{rec.get('anchor')!r}")
            limit = min(limit, TRUE_DMG_CAP * med / native)
        if not math.isfinite(limit) or limit <= 0:
            raise RuntimeError(f"第{rec.get('r')}战攻击上限非法:{limit!r}")
        return limit

    def downgrade(rec: dict, limit: float, reason: str) -> None:
        if rec["atk"] <= limit + 1e-9:
            return
        note = downgrade_atk_curse(rec["curse"])
        if note is None:
            old_ba = float(rec["ba"])
            rec["ba"] = old_ba * limit / rec["atk"]
            if (not math.isfinite(float(rec["ba"])) or float(rec["ba"]) <= 0
                    or not float(rec["ba"]) < old_ba):
                raise RuntimeError(
                    f"第{rec.get('r')}战攻击来源降档无进展:{old_ba!r}→{rec['ba']!r}")
            note = (f"攻击来源×{old_ba:g}→×{rec['ba']:g}"
                    f"（{reason}目标×{limit:g}）")
        log.append(f"[分位闸] 第{rec['r']}战 {note}")
        recalc()

    recalc()
    for _ in range(600):
        hard = [rec for rec in recs
                if rec["atk"] > explicit_limit(rec) + 1e-9]
        if hard:
            top = max(hard,
                      key=lambda rec: (rec["atk"] / explicit_limit(rec), rec["r"]))
            limit = explicit_limit(top)
            reason = ("原生攻击尖峰" if limit < BAND_TARGET["max"] - 1e-12
                      else "全塔硬上限")
            downgrade(top, limit, reason)
            continue
        bad = band_violation([rec["atk"] for rec in recs])
        if bad:
            key, got = bad
            limit = BAND_TARGET[key]
            hot = max((rec for rec in recs if rec["atk"] > limit + 1e-9),
                      key=lambda rec: (rec["atk"], rec["r"]), default=None)
            if hot is None:
                raise RuntimeError(f"攻击分位 {key}={got:g} 超标但找不到可降档楼层")
            downgrade(hot, limit, f"{key}={got:g}")
            continue
        break
    else:
        raise RuntimeError("攻击分位闸未在 600 步内收敛")
    for rec in recs:
        limit = explicit_limit(rec)
        if rec["atk"] > limit + 1e-9:
            raise RuntimeError(
                f"第{rec['r']}战攻击×{rec['atk']:g}仍超过硬上限×{limit:g}")
    bad = band_violation([rec["atk"] for rec in recs])
    if bad:
        raise RuntimeError(f"攻击分位闸后置复核失败:{bad[0]}={bad[1]:g}")
    return scale, log


def resolve_level(bosses, want: int, lv_ceil: dict | None,
                  lv_floor: dict | None, lv_gb: dict | None,
                  prefer_max: bool = False) -> int | None:
    """给一组 boss 找可行敌等级;都不行返回 None。

    候选 = 三张等级表里出现过的键(20/49/50/70/79/80/100…)+ want。
    prefer_max=False:取离 want 最近(同距优先高),终始之龙在 90 级塔自动落 80。
    prefer_max=True(「最强」模式,2026-07-28 用户需求):取全 boss 都可行的
    **最高档**,即每个 boss 都以自己数据里的最强形态出场
    (白虎/水机兵Hard→100、终始之龙/风机兵→80)。"""
    if not bosses:
        return want
    table_keys: set[int] = set()
    for code in bosses:
        for table in (lv_ceil, lv_floor, lv_gb, special_boss_levels()):
            entry = (table or {}).get(code)
            if isinstance(entry, dict):
                table_keys |= {int(k) for k in entry if str(k).isdigit()}
    if prefer_max:
        # 只在数据里真实存在的档位中选;无等级表的 boss 用 want 兜底
        order = sorted(table_keys, reverse=True) or [int(want)]
    else:
        order = sorted(table_keys | {int(want)}, key=lambda x: (abs(x - want), -x))
    for level in order:
        if all(boss_level_ok(code, level, lv_ceil, lv_floor, lv_gb) for code in bosses):
            return level
    return None


def validate_built_rows(rows: dict[str, list[str]], fd: dict, zone: dict,
                        enemies: set[str], zakos: set[str],
                        lv_ceil: dict | None = None,
                        lv_floor: dict | None = None,
                        lv_gb: dict | None = None,
                        validation_tables: dict | None = None) -> list[dict]:
    """构建产物(round → quest 行)逐关链检查;写入前调用,悬空即拒绝产出。

    lv_ceil=standard_boss / lv_floor=gv / lv_gb=general_boss,按每行 c95 查等级覆盖。"""
    reports = []
    for rk, row in rows.items():
        if len(row) > 98:
            level = int(row[95]) if len(row) > 95 and str(row[95]).isdigit() else None
            rep = check_field_chain(row[98], fd, zone, enemies, zakos, level=level,
                                    lv_ceil=lv_ceil, lv_floor=lv_floor, lv_gb=lv_gb,
                                    validation_tables=validation_tables)
        else:
            rep = {"ok": False, "field": None, "zone": None, "bosses": [],
                   "zakos": [], "errors": ["quest 行不足 99 列(缺 c98 field)"]}
        rep["round"] = rk
        rep["quest_id"] = row[0] if row else ""
        reports.append(rep)
    return reports


def validate_event_chain(event_id: str, *, qt: dict | None = None,
                         fd: dict | None = None, zone: dict | None = None,
                         enemies: set[str] | None = None,
                         zakos: set[str] | None = None,
                         lv_ceil: dict | None = None,
                         lv_floor: dict | None = None,
                         lv_gb: dict | None = None,
                         validation_tables: dict | None = None,
                         quest_path: "Path | None" = None) -> list[dict]:
    """事件全部关卡的解析链报告(输入 event_id,输出每关状态)。

    表参数缺省时读 store 现状;quest_path 可指定 quest 表备份文件回溯历史
    (复现 .bak-wfmod-rush99field 里关 13 的 water_sphere 悬空)。
    """
    if qt is None:
        qt = q.load_table(Q_QUEST, path=quest_path)
    if fd is None:
        fd = q.load_table(FIELD_DATA_T)
    if zone is None:
        zone = q.load_table(ZONE_T)
    if zakos is None:
        zakos = set(q.load_table(GENERAL_ZAKO))
    if enemies is None:
        sb = q.load_table(STANDARD_BOSS)
        gb = q.load_table(GENERAL_BOSS)
        enemies = set(gb) | set(sb) | zakos
        if lv_ceil is None:
            lv_ceil = sb
        if lv_floor is None:
            lv_floor = q.load_table("master/battle/boss/general_boss_variable.orderedmap")
        if lv_gb is None:
            lv_gb = gb
    ev = qt.get(str(event_id))
    if not isinstance(ev, dict):
        return [{"ok": False, "round": None, "quest_id": None, "field": None,
                 "zone": None, "bosses": [], "zakos": [],
                 "errors": [f"rush_event_quest[{event_id}] 缺失或不是嵌套 map"]}]
    rows: dict[str, list[str]] = {}
    for rk, leaf in ev.items():
        if isinstance(leaf, dict):
            rows[rk] = []
        else:
            rows[rk] = cells(leaf)
    return validate_built_rows(rows, fd, zone, enemies, zakos,
                               lv_ceil=lv_ceil, lv_floor=lv_floor, lv_gb=lv_gb,
                               validation_tables=validation_tables)


def print_chain_reports(reports: list[dict]) -> int:
    """打印每关状态,返回悬空关数。"""
    bad = 0
    for rep in reports:
        boss_disp = ",".join(rep["bosses"]) or "-"
        if rep["ok"]:
            print(f"  关{rep['round']}: field={rep['field']} boss={boss_disp} OK")
        else:
            bad += 1
            print(f"  关{rep['round']}: field={rep['field']} boss={boss_disp} ✗")
            for e in rep["errors"]:
                print(f"      {e}")
    return bad


# zone 的 boss 槽 = 三对列,每对 (单人战代号, 多人战代号)。客户端
# ZoneSourceValues.get_bossN() 按 isSingleBattle 二选一读其中**一列**
# (single→c24/28/32,multi→c26/30/34),所以两列必须始终指向同一只 boss;
# 只改半边 = 换 boss 在一种战斗模式下静默失效(2026-07-30 法阵克隆实锤,见
# gimmick_field)。
ZONE_BOSS_SLOTS = ((24, 26), (28, 30), (32, 34))


def _legacy_active_boss_slots(zn) -> tuple[rbb.ActiveBossSlot, ...]:
    """Adapt a bare zone node through the new active-slot parser.

    Older callers do not carry a field/terrain identity.  For that legacy-only
    boundary, each well-formed zone row is represented by a synthetic terrain
    layer, then parsed by :func:`rbb.active_boss_slots`; production field reads
    must use the real terrain path via ``_zone_pick``.  Missing BossKind is never
    inferred from the mirror side: malformed legacy rows fail closed too.
    """
    if not isinstance(zn, dict):
        return ()
    normalized: dict[str, str] = {}
    layers: list[dict] = []
    for layer, leaf in zn.items():
        if isinstance(leaf, dict) or not str(layer).isdigit():
            continue
        try:
            row = cells(leaf)
        except (TypeError, ValueError, csv.Error, StopIteration):
            continue
        if len(row) <= 34:
            continue
        normalized[str(layer)] = join(row, isinstance(leaf, (bytes, bytearray)))
        layers.append({"type": "objectgroup", "name": str(layer), "objects": []})
    if not normalized:
        return ()
    try:
        return rbb.active_boss_slots(
            "__legacy__",
            {"__legacy__": "__legacy__,terrain/__legacy__,__legacy_zone__"},
            {"__legacy_zone__": normalized},
            terrain_loader=lambda _logical: {"layers": layers},
        )
    except rbb.TerrainGateError:
        return ()


def zone_boss_slots(zn) -> list[set[str]]:
    """zone 嵌套 dict → 每个**已占用** boss 槽的代号集合(单人/多人列合并)。

    返回长度 = 该 zone 实际会出场的 boss 实体数(跨波次累加)。
    """
    out: list[set[str]] = []
    for slot in _legacy_active_boss_slots(zn):
        codes = {ref.code for ref in (slot.single, slot.multi) if ref is not None}
        if codes:
            out.append(codes)
    return out


def zone_single_bosses(zn) -> list[str]:
    """从已解析/内存克隆 zone 读单人战实际 boss 实体列表。

    这是 `_zone_pick` 的内存态版；Task C `--mix` 会在还没落盘时克隆
    field/zone，继续读 store 旧表会把 donor 的未出场部分也算进 HP。
    """
    return [slot.single.code for slot in _legacy_active_boss_slots(zn)
            if slot.single is not None]


def apply_boss_swap(wc: list[str], old: str, new: str) -> list[str]:
    """把 zone wave 行里的 boss 代号 old 换成 new——**单人 + 多人两列都换**。

    客户端 ZoneSourceValues.get_bossN() 按 isSingleBattle 二选一读
    (single→c24/28/32,multi→c26/30/34),只换半边的话另一种战斗模式仍指向
    原 boss:法阵载体克隆静默失效,成对 boss 变成「克隆 + 原体」各打各的。
    2026-07-30 修(swap_zone_bosses 六列全换,gimmick_field 这条路漏了三列)。
    """
    for a, b in ZONE_BOSS_SLOTS:
        for i in (a, b):
            if len(wc) > i and wc[i] == old:
                wc[i] = new
    return wc


def swap_zone_bosses(zn: dict, bosses: list[str]) -> dict:
    """zone 嵌套 dict 的 boss 槽(单人 c24/28/32 + 多人 c26/30/34)按序循环换成 bosses。

    zako 槽(c2-20)与其余列原样保留——zako 出生锚点属于地形,跨地形移植会静默失败,
    boss 槽则全 boss 场地形通用(gimmick_field boss_swap 同机制,已真机验证)。
    """
    out = {}
    bi = 0
    for wk, wrow in zn.items():
        wc = cells(wrow)
        for single_i, multi_i in ZONE_BOSS_SLOTS:
            occupied = [i for i in (single_i, multi_i)
                        if len(wc) > i and wc[i] not in ("", "(None)")]
            if not occupied:
                continue
            code = bosses[bi % len(bosses)]
            for i in occupied:
                wc[i] = code
            bi += 1
        out[wk] = join(wc, isinstance(wrow, (bytes, bytearray)))
    return out


_PHASE_LINKED: frozenset[str] | None = None


def phase_linked_bosses(zone_t: dict | None = None,
                        fd_t: dict | None = None,
                        bbq_t: dict | None = None) -> frozenset[str]:
    """**数据驱动**的「成对 / 分阶段」boss 名单(不硬编码任何名字)。

    两路信号并集:
      A. 官方成对出场——boss 在**官方任一 zone 的同一波次**里与别的 boss 实体
         共存(青之女王 form1/form2、深渊之兽云 cloud/p3、机工神兵 multi/foom2、
         风神/雷神…)。
      B. 官方阶段链——boss 出现在 `boss_battle_quest`(三层嵌套 章→战斗→阶段,
         c109=field)同一场**战斗**的多个阶段里,且各阶段 boss 组互不相同
         (维·索拉斯 不死王→猫头鹰 是典型:zone 各自单实体,只有 A 抓不到)。

    这类 boss 的击杀/转场联动按**代号**串联,法阵载体克隆只换得动其中一只
    (make_caster_boss 只克隆首只 general boss),联动一断就表现为「打不死」
    (2026-07-30 玩家实测)。进程内缓存。
    """
    global _PHASE_LINKED
    if _PHASE_LINKED is not None and zone_t is None and fd_t is None and bbq_t is None:
        return _PHASE_LINKED
    zone = zone_t if zone_t is not None else _tbl(ZONE_T)
    fd = fd_t if fd_t is not None else _tbl(FIELD_DATA_T)
    try:
        bbq = bbq_t if bbq_t is not None else _tbl("master/quest/boss_battle_quest.orderedmap")
    except Exception:
        bbq = {}
    flagged: set[str] = set()
    # ---- A:同 wave 多实体 ----
    for zk, zv in zone.items():
        if str(zk).startswith("mod_rogue"):
            continue                    # 自家克隆层不当判据(否则越滚越大)
        slots = zone_boss_slots(zv)
        if len(slots) > 1:
            for s in slots:
                flagged |= s
    # ---- B:boss_battle_quest 阶段链 ----
    def _field_bosses(fid: str) -> set[str]:
        frow = fd.get(fid)
        if frow is None or isinstance(frow, dict):
            return set()
        fc = cells(frow)
        if len(fc) < 3:
            return set()
        out: set[str] = set()
        for s in zone_boss_slots(zone.get(fc[2])):
            out |= s
        return out

    for chv in bbq.values():
        if not isinstance(chv, dict):
            continue
        for btv in chv.values():
            if not isinstance(btv, dict):
                continue
            per_phase = []
            for row in btv.values():
                if isinstance(row, dict):
                    continue
                c = cells(row)
                fid = c[109] if len(c) > 109 else ""
                if fid and fid != "(None)":
                    bs = _field_bosses(fid)
                    if bs:
                        per_phase.append(frozenset(bs))
            if len({s for s in per_phase}) > 1:      # 同一场战斗出现 ≥2 组不同 boss
                for s in per_phase:
                    flagged |= set(s)
    result = frozenset(flagged)
    if zone_t is None and fd_t is None and bbq_t is None:
        _PHASE_LINKED = result
    return result


# general_boss 的 subroutine_change2/3/4 = c45-51 / c52-58 / c59-65,
# 每段的 kind 列 = c48 / c55 / c62(客户端 GeneralBossValues:866-916 实锤):
#   "0"=Normal、"1"=Withstand(状态ID)、"2"=WithstandState —— 1/2 都是**转阶段无敌**。
# ⚠ 只作诊断用,**不要拿它当门禁判据**(2026-08-03 已证伪):无敌的解除是
# GeneralBossOrFunnel.exitUniqueState:496-513 —— boss 离开 invincible_end_state
# 指名的那个 unique state 时清标志位,而该态的 termination_condition 是纯帧计数
# (shark phase2_change=Time(120)、haniwa phase2_move1=Move(15)/phase3_neutral1=Time(10)),
# 与伤害/韧性/眩晕完全解耦;官方 182 条 Withstand 相位条目里终止条件为无限的**零命中**。
# 眩晕更不可能是解除前提:stunIfPossible 自带 `!isInvincible()` 前置(EnemyImpl:1070),
# 那样会构成死锁。
WITHSTAND_KIND_COLS = (48, 55, 62)


def withstand_phase_boss(code: str, gb_t: dict | None = None) -> bool:
    """该 boss 是否带「转阶段无敌」(Withstand / WithstandState)。**仅诊断用**,见上方注释。"""
    gb = gb_t if gb_t is not None else _tbl(GENERAL_BOSS)
    node = gb.get(code)
    if node is None:
        return False
    leaf = node
    while isinstance(leaf, dict):
        leaf = leaf[next(iter(leaf))]
    if not isinstance(leaf, str):
        leaf = leaf.decode("utf-8", "replace")
    c = cells(leaf)
    return any(len(c) > i and c[i] in ("1", "2") for i in WITHSTAND_KIND_COLS)


# ---- 「按 boss 代号的外部引用」集合(2026-08-03 玩家实锤的真凶)----
# 法阵载体克隆改的是 **zone 里的 boss 代号**(shark → mod_rogue_boss10)。客户端里
# boss 代号除了自己那三张表(general_boss/boss_level/general_boss_variable,都已随克隆复制),
# 还被**别的实体反向按字符串引用**,这些引用克隆覆盖不到,改名即静默断链(不崩不报):
#
#   ① damage_share —— general_funnel 的 c32 = damage_share_target_boss_id
#      (GeneralFunnelValues:808)。绑定判据是「随从的该列 == boss 的 generalEnemyWatchSelfId
#      (就是 boss 代号)」(GeneralEnemy:1977-1990),绑上后打随从会**额外给 boss 压一条同额伤害**
#      (ImpactCalculator:536/563)。绑不上只是把 damageShareTarget 留成 null(GeneralEnemy:3434)。
#      → shark_blue/red/brown 的 c32 = 'shark';turretA~D 的 c32 = 'haniwa_great_wind'。
#        shark 本体的 subroutine 1 只有一个 neutral 挂血态,战斗内容全在三条鳍上,
#        断链后**打鳍完全白打**;旋风巨土俑四个炮台合计是本体血的 2.9 倍,官方杀法就是
#        砸炮台带穿本体,断链后只能硬啃本体 ⇒ 玩家报的「血量下不去」。
#   ② general_enemy_watch —— 表形状 [自身实体种类][selfCode][selfRoutine][对方实体种类][partnerCode]…,
#      ⚠ 第一层是**实体种类**(1=general boss / 2=funnel / 3=breakable block),
#      **不是** GeneralEnemyWatchKind 那个 9 值枚举(StateMatched/HpRatio/Winced/… 在叶子行的列里)。
#      实测顶层只有 "1"/"2";"2" 的 84 个 self 键与 general_boss 交集为 0(全是 funnel_*),
#      所以只取 "1" 两侧是完整的,不是拍脑袋。
#      self 侧和 partner 侧**都按代号索引**(GeneralEnemyWatchTable:24-30、
#      GeneralEnemyWatchTableTools.getSelfData/getPartnerValues,全 Maybe 容错、查不到静默返回 null)。
#      partner 侧(别人 watch 我)克隆无解;self 侧(我 watch 别人)理论上可以补克隆该表,
#      但要连发布清单一起改,先一并硬拦,后续想拿回落点再做。
#   ③ next_state 的 test kind 15 = GeneralBossAlive(bossId)(GeneralBossStateValues:677-717)。
#      全库只有 raijin/hujin 互引,已被「多 boss 槽/成对族」两条覆盖,这里一并纳入判据兜底。
#
# 判别力(本轮 7 个法阵载体实测):shark、haniwa_great_wind **2/2 命中**;
# lich_wind_single、dark_matter_single、guardian_golem_another_light_single、
# treant_single、security_armour_single **5/5 放过**(它们在全库只出现在被克隆的三张表里)。
# 对比之下「带 Withstand 就禁」误杀 14 只无人引用的 boss —— 第4关的 dark_matter_single
# 正是被克隆的 Withstand 载体且玩家零反馈,现成反证。
GENERAL_FUNNEL = "master/battle/boss/funnel/general_funnel.orderedmap"
ENEMY_WATCH = "master/battle/boss/general_enemy_watch.orderedmap"
FUNNEL_DMGSHARE_COL = 32            # GeneralFunnelValues.as:808-809
BOSS_ALIVE_TEST, BOSS_ALIVE_ID_COL = "15", 30   # GeneralBossStateValues.as:677-717
_CODE_REFS: dict[str, frozenset[str]] | None = None


def code_referenced_bosses(gb_t: dict | None = None) -> dict:
    """按「能不能靠克隆补救」把代号引用分成两档,外加一个 degraded 失败标志。

      hard —— **补不了**,克隆改名即断链:damage_share(别人指着我的代号)、
              enemy_watch partner 侧(别人的 watch 行按我的代号索引)、
              状态机 GeneralBossAlive(bossId)。这三类要改就得连别人的行一起克隆。
      soft —— **能补**:enemy_watch 的 self 侧(我自己的观察表),整棵子树挂到新代号下即可
              (make_caster_boss 已实现)。补齐后这类可以正常当法阵载体。
      degraded —— 任一来源没扫成。**必须 fail-closed**:名单只会偏小 = 漏拦,
              而漏拦的后果是线上 boss 打不死(实测 shark 与 haniwa_great_wind
              只靠 ① damage_share 这一路才认得出来,①塌了它们立刻回到候选池)。
              所以 degraded 时一律不发法阵,宁可这轮少几个落点。
    """
    global _CODE_REFS
    if _CODE_REFS is not None and gb_t is None:
        return _CODE_REFS
    hard: set[str] = set()
    soft: set[str] = set()
    degraded = False

    def _leaf(n):
        while isinstance(n, dict):
            n = n[next(iter(n))]
        return n if isinstance(n, str) else n.decode("utf-8", "replace")

    try:
        gb = gb_t if gb_t is not None else _tbl(GENERAL_BOSS)
    except Exception as e:      # 没有 store 的环境(CI / 上游 fork / 别人的克隆)
        print(f"[WARN] general_boss 读不到({e});本轮不发深渊法阵")
        return {"hard": frozenset(), "soft": frozenset(), "degraded": True}
    # ① damage_share:general_funnel c32
    try:
        for v in _tbl(GENERAL_FUNNEL).values():
            c = cells(_leaf(v))
            if len(c) > FUNNEL_DMGSHARE_COL and c[FUNNEL_DMGSHARE_COL] not in ("", "(None)"):
                hard.add(c[FUNNEL_DMGSHARE_COL])
    except Exception as e:
        print(f"[WARN] damage_share 扫描失败({e});本轮不发深渊法阵")
        degraded = True
    # ② general_enemy_watch:partner(实体种类=1)键 → hard;self 键 → soft
    try:
        ew = _tbl(ENEMY_WATCH)
        soft |= set(ew.get("1", {}))

        def _partner(node, depth=0):
            if not isinstance(node, dict):
                return
            for k, v in node.items():
                if depth == 3:
                    if str(k) == "1" and isinstance(v, dict):
                        hard.update(v.keys())
                else:
                    _partner(v, depth + 1)
        _partner(ew)
    except Exception as e:
        print(f"[WARN] enemy_watch 扫描失败({e});本轮不发深渊法阵")
        degraded = True
    # ③ 状态机 next_state test kind 15 = GeneralBossAlive(bossId)
    try:
        def _scan_states(node):
            if isinstance(node, dict):
                for v in node.values():
                    _scan_states(v)
                return
            c = cells(_leaf(node))
            if len(c) > BOSS_ALIVE_ID_COL and c[29] == BOSS_ALIVE_TEST:
                if c[BOSS_ALIVE_ID_COL] not in ("", "(None)"):
                    hard.add(c[BOSS_ALIVE_ID_COL])
        _scan_states(_tbl("master/battle/boss/general_boss_state.orderedmap"))
    except Exception as e:
        print(f"[WARN] BossAlive 扫描失败({e});本轮不发深渊法阵")
        degraded = True
    codes = set(gb)
    result = {"hard": frozenset(hard & codes),
              "soft": frozenset((soft - hard) & codes),
              "degraded": degraded}
    if gb_t is None:
        _CODE_REFS = result
    return result


def identity_locked_boss_reason(
        bosses, *, code_references: dict | None = None) -> str | None:
    """Return why an identity-changing operation must not touch ``bosses``.

    The authoritative identity-lock set is exactly
    ``code_referenced_bosses()["hard"]``: these ids are referenced by another
    runtime object and renaming them silently breaks damage sharing, partner
    watches, or phase-alive checks.  A degraded scan is fail-closed because its
    hard set is known to be incomplete.
    """
    codes = sorted({str(code) for code in bosses if str(code)})
    if not codes:
        return None
    refs = (code_referenced_bosses() if code_references is None
            else code_references)
    if refs.get("degraded"):
        return (f"identity-locked 判据扫描降级，拒绝改名/异地搬运:"
                f"{','.join(codes)}")
    hard = frozenset(map(str, refs.get("hard") or ()))
    hits = sorted(set(codes) & hard)
    if not hits:
        return None
    return (f"identity-locked boss {','.join(hits)} 被外部实体按代号引用"
            "(damage_share/enemy_watch partner/BossAlive)，master id 必须保持不变")


def identity_locked_mix_reason(
        bosses, source_field: str, target_field: str, *,
        code_references: dict | None = None) -> str | None:
    """Reject relocating an identity-locked boss away from its native field."""
    if str(source_field) == str(target_field):
        return None
    why = identity_locked_boss_reason(
        bosses, code_references=code_references)
    if why is None:
        return None
    return (f"{why}; 原生 field={source_field}，异地 terrain={target_field}"
            " 不允许拼接")


def caster_carrier_block(field_id: str, bosses: list[str],
                         fd_t: dict, zone_t: dict,
                         phase_set: frozenset[str] | None = None,
                         gb_t: dict | None = None,
                         refs: dict | None = None) -> str | None:
    """「深渊法阵」载体门禁:返回拒绝理由(None = 可以当载体)。

    法阵的施法载体 = 克隆该轮首只 general boss 并给它追加官方场程序
    (make_caster_boss)。三种情况必须拒发:
      ① 该层 zone 有 **多个 boss 实体** —— 只换得动一只,余下的仍指向原代号,
         成对 boss 从此各打各的;
      ② 该层 boss 属于官方**成对/分阶段族**(phase_linked_bosses)—— 即便这层
         只摆了一只,它的阶段转场仍按代号找同伴,克隆即断链;
      ③ 该层 boss **被外部实体按代号引用且补不回来**(code_referenced_bosses 的 hard:
         damage_share / enemy_watch partner 侧 / GeneralBossAlive)—— ①②只认 zone 里
         摆得出来的联动,这类"随从按字符串认爹"的引用整个漏在缝里。2026-08-03 玩家实锤:
         shark(背鳍三兄弟)与 haniwa_great_wind(旋风巨土俑)"血量下不去",
         正是它们的随从(三条鳍 / 四个炮台)靠 damage_share 把伤害转给本体,
         克隆改名后转账链断掉、静默降级 ⇒ 打随从等于白打。
    三条都是数据判据,不认名字(索拉斯/女王/机工神兵一视同仁)。

    refs = code_referenced_bosses(...) 的结果。调用方应当**只算一次**再逐层传进来
    (它要遍历 general_boss_state 4.4MB,每层重算会白烧十几秒)。省略则内部自己算。
    refs["degraded"] 为真时一律拒发 —— 引用名单不完整,放行就是赌命。
    """
    frow = fd_t.get(field_id)
    if isinstance(frow, (str, bytes, bytearray)):
        fc = cells(frow)
        if len(fc) > 2:
            slots = zone_boss_slots(zone_t.get(fc[2]))
            if len(slots) > 1:
                return f"zone 有 {len(slots)} 个 boss 实体(法阵只换得动一只)"
    linked = phase_set if phase_set is not None else phase_linked_bosses()
    hit = {b for b in bosses if b in linked}     # bosses 可能含单人/多人同码重复
    if hit:
        return f"{','.join(sorted(hit))} 属官方成对/分阶段族"
    if refs is None:
        refs = code_referenced_bosses(gb_t)
    if refs.get("degraded"):
        return "代号引用名单扫描降级(见上方 WARN),本轮一律不发法阵"
    ref_hit = sorted({b for b in bosses if b in refs["hard"]})
    if ref_hit:
        return (f"{','.join(ref_hit)} 被外部实体按代号引用"
                "(damage_share/enemy_watch partner/BossAlive),克隆改名即断链")
    return None


def live_forged_dsl_logicals(gb: dict | None = None) -> list[str]:
    """store 现网 general_boss 的 mod_rogue_boss* 克隆引用的锻造 DSL 逻辑路径。

    锻造变体(wf_field_catalog.forge)只存在于 store,不发布客户端就会
    「因为有不足的数据 返回标题画面进行下载」死循环(2026-07-26 关15 实锤)。
    发布 rush 内容时必须把这些文件一并上链。
    """
    if gb is None:
        gb = q.load_table(GENERAL_BOSS)
    out = set()
    for code, node in gb.items():
        if not str(code).startswith("mod_rogue"):
            continue
        leaf = node[next(iter(node))] if isinstance(node, dict) else node
        s = leaf if isinstance(leaf, str) else leaf.decode("utf-8")
        for m in re.finditer(r"battle/action/enemy/action/mod_rogue/[^,\"\n]+", s):
            out.add(m.group(0) + ".action.dsl.amf3.deflate")
    return sorted(out)


def store_chain_ctx(fresh: bool = False):
    """store 现状的链检查上下文 (fd, zone, enemies, zakos, lv_ceil, lv_floor)。

    fresh=False 用 _tbl 进程内缓存(GUI 候选池等只读场景);fresh=True 每次重读
    (写入流程/长驻进程里 store 可能已被其它步骤改过)。lv_ceil=standard_boss、
    lv_floor=general_boss_variable、lv_gb=general_boss,配合
    check_field_chain(level=) 查等级覆盖(v4 两步规则)。"""
    load = q.load_table if fresh else _tbl
    fd = load(FIELD_DATA_T)
    zone = load(ZONE_T)
    gz = load(GENERAL_ZAKO)
    sb = load(STANDARD_BOSS)
    gb = load(GENERAL_BOSS)
    gv = load("master/battle/boss/general_boss_variable.orderedmap")
    enemies = set(gb) | set(sb) | set(gz)
    return fd, zone, enemies, set(gz), sb, gv, gb


def verify_cdn_chain(logicals: list[str],
                     cdn_diff: "Path | None" = None) -> list[tuple[str, str]]:
    """发布完整性自检:每个逻辑路径的 store 现字节须等于 CDN diff 链最新版包内字节。

    C8601「key=mod_rogue_f9 不存在」事故根因:表写进了 store 却没进发布清单,
    quest 引用链在客户端侧断裂。发布成功后调用;返回 [(逻辑路径, 问题)] 清单
    (空 = 通过)。同一版本边可能拆多包(序号 N),同版本任一包字节一致即通过。
    """
    if cdn_diff is None:
        import wf_publish as pub
        cdn_diff = pub.CDN_DIFF
    cdn_diff = Path(cdn_diff)
    ver_re = re.compile(r"pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-\d+-")
    wanted = {f"production/upload/{q.hashed_rel(logical)}": logical
              for logical in logicals}
    best: dict[str, tuple[tuple[int, ...], list[Path]]] = {}
    for zp in sorted(cdn_diff.glob("*.zip")):
        m = ver_re.match(zp.name)
        if not m:
            continue
        ver = tuple(int(x) for x in m.group(2).split("."))
        try:
            with zipfile.ZipFile(zp) as zf:
                names = set(zf.namelist())
        except Exception:
            continue        # 坏包按不含处理:只会把问题报出来,不会漏报
        for member in wanted:
            if member not in names:
                continue
            cur = best.get(member)
            if cur is None or ver > cur[0]:
                best[member] = (ver, [zp])
            elif ver == cur[0]:
                cur[1].append(zp)
    problems: list[tuple[str, str]] = []
    for member, logical in wanted.items():
        sp = q.store_path(logical)
        if not sp.is_file():
            problems.append((logical, f"store 文件缺失({sp})"))
            continue
        want_hash = hashlib.sha256(sp.read_bytes()).hexdigest()
        hit = best.get(member)
        if hit is None:
            problems.append((logical, "不在 CDN diff 链任何包里(未发布)"))
            continue
        ver, zips = hit
        ok = False
        for zp in zips:
            try:
                with zipfile.ZipFile(zp) as zf:
                    if hashlib.sha256(zf.read(member)).hexdigest() == want_hash:
                        ok = True
                        break
            except Exception:
                continue
        if not ok:
            problems.append((
                logical,
                f"CDN 链最新版 {'.'.join(map(str, ver))}"
                f"({zips[0].name}) 字节与 store 不一致(链上是旧内容)"))
    return problems


# ⚠ 两张表的元素枚举**不一样**(2026-07-29 测绘实锤,以前一直按同一套换算):
#   general_boss c0(boss 固定元素 kind):0=Inherit 1火 2水 3雷 4风 5光 6暗
#   quest c69(battle_recommended_element):**0风 1火 2水 3雷 4暗 5光**
# 后者由 advent 六属性精灵兽/六属性废龙两族交叉验证(火1/水2/雷3/风0/光5/暗4),
# 并与 ranking 五元素试炼、carnival 六色土俑、solo_time_attack 六色试炼、
# expert_single(不死王=风0/废墟魔像=火1/寄居蟹=水2)四张表全部自洽。
# c69 写的是 quest 枚举,所以固定元素 boss 必须按下表换算,不能沿用 kind-1。
GB_KIND_TO_QUEST_ELEM = {1: 1, 2: 2, 3: 3, 4: 0, 5: 5, 6: 4}
# quest 枚举 → 中文(下标即 c69 取值)
QUEST_ELEM_CN = ["风", "火", "水", "雷", "暗", "光"]


def boss_element_map() -> dict[str, int | None]:
    """boss code → 固定元素(**quest c69 枚举**)或 None(=Inherit,元素随 c69)。

    只读 general_boss(c0=元素kind);standard_boss 表无元素列 = 恒继承 quest 元素。
    返回值直接可写 c69 —— 换算表见 GB_KIND_TO_QUEST_ELEM。
    """
    out: dict[str, int | None] = {}
    table = q.load_table(GENERAL_BOSS)
    for code, node in table.items():
        leaf = node
        if isinstance(node, dict):
            leaf = node[next(iter(node))]
        s = leaf.decode("utf-8") if isinstance(leaf, bytes) else leaf
        kind = cb._cols(s.split("\n")[0])[0]
        out[code] = GB_KIND_TO_QUEST_ELEM.get(int(kind)) if kind.isdigit() else None
    return out


# ---- 跨副本楼层来源(v7,2026-07-19 用户设计:随 rounds 自适应)----
# 固定锚:第1轮(rounds≥8 时含第2轮)=小怪房热身;**末轮恒=主线终 boss 终始之龙**,
# 末轮-1=无幻之宴守门(rounds≥5)。比例锚(按 rounds 百分比落位,撞位向后找空,
# 塞不下放弃):领主战20% / 机兵40% / 降临讨伐55% / 女帝歼灭者70%。其余轮=连战塔池。
# 简单来源叠难度补偿(小怪房/领主战/浅层塔),见 SRC_BOOST / tower_area_boost。
import wf_boss as wb              # noqa: E402


_TBL_CACHE: dict[str, dict] = {}


def _tbl(logical: str) -> dict:
    if logical not in _TBL_CACHE:
        _TBL_CACHE[logical] = q.load_table(logical)
    return _TBL_CACHE[logical]


def boss_ref_validation_tables(*, standard_boss: dict | None = None,
                               general_boss: dict | None = None,
                               general_boss_variable: dict | None = None,
                               special_tables: dict | None = None,
                               funnel_ok=None) -> dict:
    """Build the sole BossKind validation bundle consumed by ``wf_rogue_bundle``.

    The model module must not import this builder.  We therefore inject the
    already-proven level/funnel semantics as callbacks and return the *selected
    numeric tier*, not a boolean.  Kinds 0/1/8 fail closed without this bundle.
    Explicit empty dicts are honored for isolated tests; ``None`` loads the
    configured store read-only.
    """
    sb = standard_boss if standard_boss is not None else _tbl(STANDARD_BOSS)
    gb = general_boss if general_boss is not None else _tbl(GENERAL_BOSS)
    gv_logical = "master/battle/boss/general_boss_variable.orderedmap"
    gv = (general_boss_variable if general_boss_variable is not None
          else _tbl(gv_logical))
    tables: dict = {"standard_boss": sb, "general_boss": gb}
    if special_tables is None:
        for logical in SPECIAL_BOSS_TABLES:
            name = Path(logical).name.removesuffix(".orderedmap")
            tables[name] = _tbl(logical)
    else:
        for name, table in special_tables.items():
            short = Path(str(name)).name.removesuffix(".orderedmap")
            tables[short] = table

    effective_funnel_ok = funnel_ok if funnel_ok is not None else boss_funnel_ok

    def selected_level(ref: rbb.BossRef, enemy_level: int, _tables: dict):
        if ref.kind == 0:
            return select_surjective_level(sb.get(ref.code), enemy_level)
        if ref.kind in (1, 8):
            if not boss_level_ok(
                    ref.code, enemy_level, {}, gv, gb,
                    funnel_ok_fn=effective_funnel_ok,
                    special_levels={}):
                return None
            return select_surjective_level(gb.get(ref.code), enemy_level)
        return None

    tables["__level_validator__"] = selected_level
    tables["__funnel_ok__"] = effective_funnel_ok
    return tables


def validate_spawned_ref(
        source_kind: str, code: str, enemy_level: int, *,
        validation_tables: dict,
        general_zako: dict,
        general_funnel: dict,
        standard_funnel: dict,
        ) -> rbb.GateResult:
    """Validate an action/state dependency against its exact client source.

    The three minion tables and GeneralBoss use getSurjectivity, so a numeric
    tier at or above the battle level must exist. SpawnAlterEgo constructs a
    GeneralBossAlterEgoSource and GeneralBossAlive names a GeneralBoss; a
    same-code StandardBoss or Zako row must never satisfy either dependency.
    Same-layer membership for GeneralBossAlive is checked by the closure walker,
    which owns the necessary layer context.
    """

    try:
        level = int(enemy_level)
    except (TypeError, ValueError):
        return rbb.GateResult(False, "LEVEL",
                              detail=f"invalid spawned-ref level:{enemy_level!r}")

    table_by_kind = {
        "Funnel": (general_funnel, "general_funnel"),
        "StandardFunnel": (standard_funnel, "standard_funnel"),
        "Zako": (general_zako, "general_zako"),
    }
    if source_kind in table_by_kind:
        table, label = table_by_kind[source_kind]
        node = table.get(code) if isinstance(table, dict) else None
        selected = select_surjective_level(node, level)
        if selected is None:
            reason = "FUNNEL_LEVEL" if source_kind != "Zako" else "LEVEL"
            return rbb.GateResult(
                False, reason, source_table=label,
                detail=f"{label} has no tier >= {level}:{code}")
        return rbb.GateResult(
            True, selected_level=selected, source_table=label)

    if source_kind in ("AlterEgo", "GeneralBoss"):
        return rbb.validate_boss_ref(
            rbb.BossRef(1, code), level, validation_tables)
    return rbb.GateResult(
        False, "REFERENCE",
        detail=f"unknown spawned reference kind:{source_kind}")


def build_native_bundle_catalog(
        enemy_level: int = 100, *,
        fd: dict | None = None,
        zone: dict | None = None,
        sb: dict | None = None,
        gb: dict | None = None,
        gv: dict | None = None,
        bl: dict | None = None,
        gz: dict | None = None,
        special_tables: dict | None = None,
        general_boss_state: dict | None = None,
        general_funnel: dict | None = None,
        standard_funnel: dict | None = None,
        general_enemy_watch: dict | None = None,
        funnel_ok=None,
        terrain_loader=None,
        action_loader=None,
        esdl_loader=None,
        code_references: dict | None = None,
        display_names: dict[str, str] | None = None,
        metadata_of=None,
        ) -> rbb.BundleCatalog:
    """Build the read-only post-gate catalog from every official active field.

    `cb.build_pool()` is deliberately absent: it may provide UI metadata later,
    but never decides boss identity or eligibility.  Live `mod_rogue_*` clones
    are provenance-filtered even when this API is called outside main's stale
    purge path, so a previous dry-run/write cannot add extra family tickets.
    """
    level = int(enemy_level)
    # A fully injected factory call is an isolated snapshot contract.  Optional
    # Task3 tables/resources that were not supplied must make portability
    # native-only; they must never fall through to the live store behind the
    # caller's back (the existing factory test pins this boundary).
    fully_injected = all(value is not None for value in (
        fd, zone, sb, gb, gv, bl, gz, special_tables))
    # The builder later purges stale ``mod_rogue_*`` rows in memory.  Keep this
    # factory uncached and accept those sanitized tables explicitly; otherwise
    # a same-process rebuild can silently reuse the pre-purge catalog.  The
    # no-argument path remains a read-only audit helper against the live store.
    fd = fd if fd is not None else q.load_table(FIELD_DATA_T)
    zone = zone if zone is not None else q.load_table(ZONE_T)
    sb = sb if sb is not None else q.load_table(STANDARD_BOSS)
    gb = gb if gb is not None else q.load_table(GENERAL_BOSS)
    gv = (gv if gv is not None else
          q.load_table("master/battle/boss/general_boss_variable.orderedmap"))
    bl = (bl if bl is not None else
          q.load_table("master/battle/boss/boss_level.orderedmap"))
    gz = gz if gz is not None else q.load_table(GENERAL_ZAKO)
    boss_states = (general_boss_state if general_boss_state is not None else
                   {} if fully_injected else
                   q.load_table("master/battle/boss/general_boss_state.orderedmap"))
    general_funnels = (general_funnel if general_funnel is not None else
                       {} if fully_injected else q.load_table(GENERAL_FUNNEL))
    standard_funnels = (standard_funnel if standard_funnel is not None else
                        {} if fully_injected else q.load_table(
                            "master/battle/boss/funnel/standard_funnel.orderedmap"))
    if general_enemy_watch is not None:
        enemy_watch = general_enemy_watch
    elif fully_injected:
        enemy_watch = None
    else:
        try:
            enemy_watch = q.load_table(ENEMY_WATCH)
        except Exception:
            # ``code_referenced_bosses`` will mark the matching scan degraded;
            # keep this snapshot missing so the special HP gate cannot pretend
            # that a required self-watch subtree is cloneable.
            enemy_watch = None
    validation = boss_ref_validation_tables(
        standard_boss=sb, general_boss=gb, general_boss_variable=gv,
        special_tables=special_tables, funnel_ok=funnel_ok)
    names = dict(display_names) if display_names is not None else wb.boss_names()

    def selected_leaf(ref: rbb.BossRef, selected: int | None):
        table_name = rbb.KIND_TABLES.get(ref.kind)
        table = validation.get(table_name, {}) if table_name else {}
        node = table.get(ref.code) if isinstance(table, dict) else None
        if isinstance(node, dict):
            if selected is not None and str(selected) in node:
                return node[str(selected)]
            for key in node:
                if str(key).isdigit():
                    return node[key]
            return None
        return node

    def identity_of(ref: rbb.BossRef, selected: int | None) -> dict:
        leaf = selected_leaf(ref, selected)
        text = (leaf.decode("utf-8", "replace") if isinstance(leaf, bytes)
                else leaf if isinstance(leaf, str) else "")
        model = ""
        roots: set[str] = set()
        for line in text.splitlines() or (text,):
            for value in cells(line) if line else ():
                if value.startswith("battle/boss/") and "general_16dots" not in value:
                    parts = value.split("/")
                    if len(parts) > 2 and not model:
                        model = parts[2]
                elif value.startswith("battle/enemy/boss/"):
                    parts = value.split("/")
                    if len(parts) > 3 and not model:
                        model = parts[3].split("$")[0]
                    roots.add(value)
                if value.startswith("battle/action"):
                    roots.add(value)
        return {
            "display": names.get(ref.code) or "",
            "model": model or ref.code,
            "actions": tuple(sorted(roots)),
        }

    def reference_gate(_field_id: str, slots: tuple[rbb.ActiveBossSlot, ...],
                       selected_levels: tuple[tuple[str, int, int], ...],
                       _level: int):
        # Task 2 proves the exact active single slot, its selected source leaf,
        # standard ESDL path / general boss_level row, and active zako refs.
        # External hard/soft code references and recursive action/spawn closure
        # are deliberately not claimed here; the portability gate below owns
        # that transitive proof without changing native eligibility.
        selected = {(layer, slot): tier for layer, slot, tier in selected_levels}
        for slot in slots:
            ref = slot.single
            if ref is None:
                continue
            result = rbb.validate_boss_ref(ref, _level, validation)
            if not result.ok:
                return rbb.GateResult(False, result.reason or "REFERENCE",
                                      detail=result.detail)
            if result.selected_level is not None:
                if selected.get((slot.layer, slot.slot)) != result.selected_level:
                    return rbb.GateResult(
                        False, "REFERENCE",
                        detail=f"slot {slot.layer}/{slot.slot} selected tier drift")
            if ref.kind == 0:
                leaf = selected_leaf(ref, result.selected_level)
                if not isinstance(leaf, (str, bytes, bytearray)):
                    return rbb.GateResult(False, "REFERENCE",
                                          detail=f"standard source leaf missing:{ref.code}")
                row = cells(leaf)
                if len(row) < 2 or not row[1]:
                    return rbb.GateResult(False, "REFERENCE",
                                          detail=f"standard ESDL path missing:{ref.code}")
                logical = (row[1] if row[1].endswith(".esdl.amf3.deflate")
                           else row[1] + ".esdl.amf3.deflate")
                if not q.store_path(logical).is_file():
                    return rbb.GateResult(False, "REFERENCE",
                                          detail=f"standard ESDL file missing:{logical}")
            elif ref.code not in bl:
                return rbb.GateResult(False, "REFERENCE",
                                      detail=f"boss_level missing:{ref.code}")
        return rbb.GateResult(True)

    def hp_gate(slots: tuple[rbb.ActiveBossSlot, ...], _level: int):
        refs = [slot.single for slot in slots if slot.single is not None]
        if any(ref.kind not in (0, 1, 8) for ref in refs):
            return rbb.GateResult(False, "SPECIAL_HP_CHANNEL_UNSUPPORTED")
        # Preserve BossKind through HP dispatch.  ``floor_native_hp`` has a
        # legacy code-membership branch; forcing the exact source prevents a
        # future code that exists in both tables from turning kind 1 into a
        # standard ESDL read (or kind 0 into boss_level math).
        failures = []
        for ref in refs:
            if ref.kind == 0:
                evidence = floor_native_hp(
                    [ref.code], _level, standard_boss=sb, boss_level={})
            else:  # kinds 1/8 are both verified GeneralBoss source paths
                evidence = floor_native_hp(
                    [ref.code], _level, standard_boss={}, boss_level=bl)
            if not evidence.get("verified"):
                failures.append(
                    f"kind={ref.kind} code={ref.code}:"
                    f"{evidence.get('reason') or 'unknown HP'}")
        if failures:
            return rbb.GateResult(False, "HP_UNVERIFIED", detail="; ".join(failures))
        return rbb.GateResult(True)

    def bundle_hp_gate(bundle: rbb.NativeBossBundle, _level: int):
        expanded = expand_bundle_hp_members(bundle, _level, {
            "orochi": validation.get("orochi", {}),
            "general_boss": gb,
            "general_boss_variable": gv,
            "boss_level": bl,
        })
        if not expanded.ok:
            return rbb.GateResult(
                False, expanded.reason or "SPECIAL_HP_CHANNEL_UNSUPPORTED",
                detail=expanded.detail)
        ref_error = _orochi_clone_reference_error(
            expanded, code_refs, enemy_watch)
        if ref_error:
            return rbb.GateResult(
                False, "SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=ref_error)
        return rbb.GateResult(
            True, selected_level=expanded.selected_parent_level,
            source_table="orochi")

    if code_references is not None:
        code_refs = code_references
    elif fully_injected:
        code_refs = {"hard": frozenset(), "soft": frozenset(), "degraded": True}
    else:
        code_refs = code_referenced_bosses(gb)

    def missing_resource(kind: str):
        def load(logical: str):
            raise FileNotFoundError(
                f"{kind} loader not injected for isolated catalog:{logical}")
        return load

    effective_action_loader = (
        action_loader if action_loader is not None else
        missing_resource("action") if fully_injected else rbb.load_store_action)
    effective_esdl_loader = (
        esdl_loader if esdl_loader is not None else
        missing_resource("ESDL") if fully_injected else rbb.load_store_esdl)

    def spawned_ref_gate(source_kind: str, code: str, _level: int):
        return validate_spawned_ref(
            source_kind, code, _level,
            validation_tables=validation,
            general_zako=gz,
            general_funnel=general_funnels,
            standard_funnel=standard_funnels)

    requirement_cache: dict[tuple, rbb.RequirementResult] = {}

    def portability_gate(bundle: rbb.NativeBossBundle) -> rbb.RequirementResult:
        active_codes = tuple(sorted(
            slot.single.code for slot in bundle.slots if slot.single is not None))
        if code_refs.get("degraded"):
            return rbb.RequirementResult(
                False, reason="ACTION_CLOSURE_UNAUDITED",
                detail="external boss-code reference scan degraded")
        hard = sorted(set(active_codes) & set(code_refs.get("hard", ())))
        if hard:
            return rbb.RequirementResult(
                False, reason="ACTION_CLOSURE_UNAUDITED",
                detail="external hard boss-code references:" + ",".join(hard))
        key = (
            tuple((slot.layer, slot.slot,
                   None if slot.single is None else slot.single.kind,
                   None if slot.single is None else slot.single.code)
                  for slot in bundle.slots),
            bundle.selected_levels,
            bundle.active_layers,
        )
        if key not in requirement_cache:
            requirement_cache[key] = rbb.boss_terrain_requirements(
                bundle, level, {
                    "general_boss": gb,
                    "standard_boss": sb,
                    "general_boss_state": boss_states,
                    "action_loader": effective_action_loader,
                    "esdl_loader": effective_esdl_loader,
                    "spawned_ref_gate": spawned_ref_gate,
                })
        return requirement_cache[key]

    metadata_provider = metadata_of
    if metadata_provider is None:
        thumbnails = field_thumbnail_map()
        metadata_index: dict[str, set[tuple[str, str, str]]] = {}
        field_levels: dict[str, int] = {}
        field_ids = set(fd)

        # Official floor rows are the strongest field-local BGM source:
        # ``field,bgm,floor_thumbnail``.  They also cover tower/challenge
        # quests whose quest row references a floor key instead of each field.
        try:
            floor_table = q.load_table("master/battle/floor.orderedmap")
        except (FileNotFoundError, KeyError, TypeError, ValueError, zlib.error):
            floor_table = {}
        floor_bgm: dict[str, set[str]] = {}
        floor_thumb: dict[str, set[str]] = {}
        for node in floor_table.values():
            if isinstance(node, dict):
                continue
            text = (node.decode("utf-8", "replace")
                    if isinstance(node, (bytes, bytearray)) else str(node))
            for line in text.splitlines():
                values = cells(line)
                if not values or values[0] not in field_ids:
                    continue
                field_id = values[0]
                bgm = values[1] if len(values) > 1 else ""
                thumbnail = values[2] if len(values) > 2 else ""
                if bgm not in ("", "(None)"):
                    floor_bgm.setdefault(field_id, set()).add(bgm)
                if thumbnail not in ("", "(None)"):
                    floor_thumb.setdefault(field_id, set()).add(thumbnail)
                metadata_index.setdefault(field_id, set()).add(
                    ("floor", "" if bgm == "(None)" else bgm,
                     "" if thumbnail == "(None)" else thumbnail))

        # Verified CN schemas where the BGM token is immediately after the
        # field cell.  challenge_dungeon uses field+1 as a frame limit and
        # skill_preview ends at the field, so neither is guessed here.
        direct_bgm_categories = {
            "boss_battle", "main", "ex", "practice", "advent", "raid",
            "rush", "hard_multi", "expert_single", "ranking",
            "score_attack", "solo_time_attack", "carnival", "story_event",
            "world_story", "world_story_boss",
        }
        for category, _label, logical, _group, _icon in wb.QUEST_CATS:
            try:
                quest_table = wb._load(logical)
            except (FileNotFoundError, KeyError, TypeError, ValueError, zlib.error):
                continue
            for _path, row in wb._leaves(quest_table):
                if not isinstance(row, str):
                    continue
                values = cells(row)
                referenced = [(index, value) for index, value in enumerate(values)
                              if value in field_ids]
                if not referenced:
                    continue
                quest_thumbnail = next(
                    (value for value in values if "/thumbnail/" in value), "")
                for index, field_id in referenced:
                    source_level = quest_level_of(values, index)
                    if source_level:
                        field_levels[field_id] = max(
                            field_levels.get(field_id, 0), int(source_level))
                    direct_bgm = (values[index + 1]
                                  if category in direct_bgm_categories
                                  and index + 1 < len(values) else "")
                    if direct_bgm in ("", "(None)"):
                        direct_bgm = next(iter(sorted(floor_bgm.get(field_id, ()))), "")
                    thumbnail = (quest_thumbnail
                                 or thumbnails.get(field_id, "")
                                 or next(iter(sorted(floor_thumb.get(field_id, ()))), ""))
                    metadata_index.setdefault(field_id, set()).add(
                        (category, direct_bgm, thumbnail))

        def metadata_provider(field_id: str) -> dict:
            aliases = tuple(sorted(
                metadata_index.get(field_id, set()),
                key=lambda alias: (alias[0] == "floor", alias)))
            if aliases:
                category, bgm, thumbnail = aliases[0]
            else:
                category, bgm, thumbnail = "official", "", thumbnails.get(field_id, "")
            return {"category": category, "bgm": bgm, "thumbnail": thumbnail,
                    "aliases": aliases, "level": field_levels.get(field_id, 0)}

    return rbb.build_native_bundle_catalog(
        fd, zone, terrain_loader or rbb.load_store_terrain,
        enemy_level=level,
        validation_tables=validation,
        display_names=names,
        identity_of=identity_of,
        hp_gate=hp_gate,
        bundle_hp_gate=bundle_hp_gate,
        reference_gate=reference_gate,
        zako_codes=set(gz),
        portability_gate=portability_gate,
        official_field=lambda field_id: not field_id.startswith("mod_rogue_"),
        metadata_of=metadata_provider,
        c8016_prefixes=C8016_BLOCKED_BOSS_PREFIXES,
    )


def choose_endless_native_bundle(rng, enemy_level: int = 100) \
        -> rbb.NativeBossBundle:
    """从正式构建器的 fresh post-gate catalog 选一个原生安全 bundle。"""
    level = int(enemy_level)
    if level <= 0:
        raise ValueError(f"无尽层敌等级非法:{enemy_level!r}")
    catalog = build_native_bundle_catalog(enemy_level=level)
    gated = []
    for bundles in catalog.bundles.values():
        for bundle in bundles:
            bosses = list(native_bundle_bosses(bundle))
            requirements = bundle.terrain_requirements
            if (bundle.portable and bundle.terrain_requirements is not None
                    and set(requirements.action_roots).issubset(
                        requirements.action_closure)
                    and not field_blocked(bundle.source_field)
                    and _pool_safe(bosses)):
                gated.append(bundle)
    safe_catalog = rbb.catalog_from_bundles(gated)
    if not safe_catalog.family_ids:
        raise RuntimeError(f"敌等级 {level} 没有通过完整门禁的原生 boss bundle")
    selected = rbb.choose_family_variant_bundle(
        safe_catalog, rng, policy=None).bundle
    if selected.source_field not in safe_catalog.eligible_source_fields:
        raise RuntimeError(
            f"无尽层 selector 返回了非 post-gate 场地:{selected.source_field}")
    return selected


def native_bundle_bosses(bundle: rbb.NativeBossBundle) -> tuple[str, ...]:
    """按 active slot 顺序返回单人侧实体代号，并保留真实重复实例。"""
    return tuple(slot.single.code for slot in bundle.slots
                 if slot.single is not None)


def patch_quest_boss_fields(
        row: list[str], *, field: str, bosses, thumbnail: str | None,
        bgm: str | None, enemy_level: int, rng,
        play_field: str | None = None,
        field_elements: dict[str, int] | None = None,
        boss_elements: dict[str, int | None] | None = None,
        require_bgm: bool = False) -> tuple[int, str]:
    """同步正式塔路径的 c5/c69/c95/c98/c99 boss 场地字段。"""
    if len(row) <= 99:
        raise ValueError(f"rush quest 行过短:{len(row)} < 100")
    source_field = str(field)
    target_field = str(play_field or source_field)
    if not source_field or not target_field:
        raise ValueError("无尽层 bundle 缺 field")
    level = int(enemy_level)
    if level <= 0:
        raise ValueError(f"无尽层敌等级非法:{enemy_level!r}")
    if require_bgm and bgm in (None, "", "(None)"):
        raise ValueError(f"无尽层 bundle 缺 BGM:{source_field}")

    fields = field_official_elem_map() if field_elements is None else field_elements
    boss_map = boss_element_map() if boss_elements is None else boss_elements
    official = fields.get(source_field)
    fixed = next((boss_map[code] for code in bosses
                  if boss_map.get(code) is not None), None)
    if official is not None:
        element, tag = int(official), "(官方)"
    elif fixed is not None:
        element, tag = int(fixed), ""
    else:
        element, tag = int(rng.randrange(6)), "(随机)"
    if not 0 <= element < 6:
        raise ValueError(f"无尽层推荐元素非法:{element}")

    if thumbnail not in (None, "", "(None)"):
        row[5] = str(thumbnail)
    row[69] = str(element)
    row[95] = str(level)
    row[98] = target_field
    if bgm not in (None, "", "(None)"):
        row[99] = str(bgm)
    return element, tag


def endless_bundle_publish_logicals(bundle: rbb.NativeBossBundle) -> tuple[str, ...]:
    """返回原生 bundle 与 quest 写回组成的 dependency-first 发布闭包。"""
    logicals: list[str] = []

    def add(logical: str | None) -> None:
        if logical and logical not in logicals:
            logicals.append(logical)

    add(bundle.terrain_logical)
    requirements = bundle.terrain_requirements
    if requirements is not None:
        for action in requirements.action_closure:
            add(action if action.endswith(".action.dsl.amf3.deflate")
                else action + ".action.dsl.amf3.deflate")

    kinds = {slot.single.kind for slot in bundle.slots
             if slot.single is not None}
    for kind in sorted(kinds):
        table_name = rbb.KIND_TABLES.get(kind)
        add(rbb.TABLE_LOGICALS.get(table_name))
    add(BOSS_LEVEL)
    add(GENERAL_ZAKO)
    add(ZAKO_LEVEL)

    spawned_kinds = {
        ref.source_kind
        for layer in (() if requirements is None else requirements.layers)
        for ref in layer.spawned_refs
    }
    has_funnels = bool(requirements and any(
        layer.funnels for layer in requirements.layers))
    if kinds & {1, 3, 8} or spawned_kinds & {"AlterEgo", "GeneralBoss"}:
        add(GENERAL_BOSS)
        add(GENERAL_BOSS_VARIABLE)
        add(GENERAL_BOSS_STATE)
        add(ENEMY_WATCH)
    if has_funnels or "Funnel" in spawned_kinds:
        add(GENERAL_FUNNEL)
    if "StandardFunnel" in spawned_kinds:
        add(STANDARD_FUNNEL)

    add(ZONE_T)
    add(FIELD_DATA_T)
    add(Q_QUEST)
    return tuple(logicals)


def _zone_pick(fdid: str) -> tuple[list[str], list[str]]:
    """field → 单人战实际 (boss codes, zako codes)，只读 terrain 激活层。

    boss 每实体槽是 `(single,multi)` 镜像对。塔是单人 event quest，客户端只读
    c24/c28/c32；即使 c26/c30/c34 写了不同代号也不能当成第二只实体。
    zone 中未被 terrain ``objectgroup.name`` 激活的 row 必须忽略；解析失败时
    fail closed 返回空，不回退到扫描整个 zone。数据列号使用 0-based。
    """
    fd = _tbl("master/battle/field_data.orderedmap")
    zone = _tbl("master/battle/zone.orderedmap")
    frow = fd.get(fdid)
    if not frow:
        return [], []
    try:
        caps = rbb.load_terrain_layer_caps(fdid, fd, zone, rbb.load_store_terrain)
        slots = rbb.active_boss_slots(fdid, fd, zone, rbb.load_store_terrain)
    except (FileNotFoundError, rbb.TerrainGateError):
        return [], []
    fc = cells(frow)
    zn = zone.get(fc[2])
    bosses = [slot.single.code for slot in slots if slot.single is not None]
    zakos: list[str] = []
    if isinstance(zn, dict):
        for cap in caps:
            wc = cells(zn[cap.layer])
            zakos.extend(wc[i] for i in range(2, min(22, len(wc)), 2)
                         if wc[i] not in ("(None)", ""))
    return bosses, zakos


# 难度分级:master/quest/quest_rank.orderedmap —— 难度由敌等级(c95)决定,
# quest 名里的 ::quest_rank:: 占位符由客户端按此表替换。
QUEST_RANKS = ((100, "地狱级"), (90, "超级+"), (80, "超级"),
               (70, "高级+"), (40, "高级"), (20, "中级"), (1, "初级"))

# 来源池难度下限(2026-07-29 用户需求「全部取最难的版本,超级最低」)。
# 80 = 超级;≥90 超级+;100 地狱级。只作用于副本来源池,塔池(崩坏域)的难度
# 由 --enemy-level / 轮次曲线另行决定,不受此门槛影响。
MIN_QUEST_LEVEL = 80
# 不吃难度门槛的来源池:主线 boss 是手挑名单,主线关卡的官方敌等级本来就低,
# 难度由 resolve_level 取 boss 最强档 + 轮次曲线决定,按官方档位刷会全军覆没。
NO_LEVEL_FLOOR = {"主线boss"}


def rank_of(level) -> str:
    """敌等级 → 难度名(客户端 ::quest_rank:: 的显示值)。"""
    try:
        value = int(level)
    except (TypeError, ValueError):
        return ""
    for floor, name in QUEST_RANKS:
        if value >= floor:
            return name
    return ""


# 敌等级列 = field 列 − 3。2026-07-29 全库实测:15 个有效 quest 类别 2903 行
# 100% 命中(boss_battle c109→c106、main c109→c106、advent c115→c112、
# hard_multi c110→c107、rush c98→c95、skill_preview c30→c27…)。
# 旧代码硬编码 cs[95],只对 rush schema 成立:领主战表 c95 是 HP 修正,
# 于是索拉斯场地被读成「lv1560 · 地狱级」。用相对列位替代按类别登记列表,
# 新 schema 也自动跟上。
def quest_level_of(cs: list[str], fidx: int) -> str:
    """quest 行 + field 所在列 → 敌等级字符串;越界/非 1-100 返回 ""。"""
    idx = fidx - 3
    if idx < 0 or idx >= len(cs):
        return ""
    val = str(cs[idx]).strip()
    return val if val.isdigit() and 1 <= int(val) <= 100 else ""


def quest_pool(cat: str, name_eq: str | None = None, require_boss: bool = True) -> list[dict]:
    """副本类别 → [{field,bosses,thumb,name,level,rank}](按 field 去重)。

    ⚠ 同一个 field 常有多行难度档,**取敌等级最高的那一行**(2026-07-29 用户需求
    「全部取最难的版本」)。分档有两种形态,这里都覆盖:
      ① 多 field 分档:`steampunk_fire_1..4`(中级/高级/高级+/超级)——尾号即档位;
      ② **单 field 多行分档**:`steampunk_another`(机工神兵菲诺梅那)一个场地
         挂 20/50/70/80/100 五行,难度只由行里的敌等级决定。
    旧代码按 field 首行去重,②型副本一律读成最低档 —— 菲诺梅那因此一直显示
    「lv20 中级」,实际有地狱级。
    """
    logical = next(x[2] for x in wb.QUEST_CATS if x[0] == cat)
    tree = wb._load(logical)
    fd_keys = set(_tbl("master/battle/field_data.orderedmap").keys())
    best: dict[str, tuple[int, dict]] = {}
    order: list[str] = []
    for _path, row in wb._leaves(tree):
        cs = row.split(",")
        name = next((x for x in cs[1:7] if x and wb._CJK.search(x)), "")
        name = name.replace("::quest_rank::", "").strip()
        if name_eq and name != name_eq:
            continue
        fidx = next((i for i, x in enumerate(cs) if x in fd_keys), None)
        if fidx is None:
            continue
        fdid = cs[fidx]
        bosses, zakos = _zone_pick(fdid)
        if require_boss and not bosses:
            continue
        thumb = next((x for x in cs if "/thumbnail/" in x), "")
        level = quest_level_of(cs, fidx)
        entry = {"field": fdid, "bosses": bosses, "zakos": zakos, "thumb": thumb,
                 "name": name.replace("::quest_rank::", rank_of(level)).strip(),
                 "level": level, "rank": rank_of(level), "cat": cat}
        lv = int(level) if level else 0
        if fdid not in best:
            order.append(fdid)
            best[fdid] = (lv, entry)
        elif lv > best[fdid][0]:
            best[fdid] = (lv, entry)
    return [best[f][1] for f in order]


def zako_room_pool() -> list[dict]:
    """主线里的纯小怪房(zone 无 boss、有小怪)。"""
    out = []
    for entry in quest_pool("main", require_boss=False):
        if not entry["bosses"] and entry["zakos"]:
            out.append(entry)
    return out


# ---- 主线/EX 手挑名单(2026-07-29,从普查出的 47 个候选里选 22 个)----
# 取「真 boss」里★强烈建议+○建议;主动排除三类:
#   ① 16 个杂兵提拔族 —— 它们归第 2 战杂鱼层,进主池就是白给;
#   ② 5 个杂鱼感偏强的(红发老战士/五行·水善/人鱼老人/魔族男性/自动贩卖机);
#   ③ 诅咒弧魔艾基尔三形态 —— arch_evil 在 C8016 黑名单里,加了也会被门禁剔掉。
MAIN_STORY_BOSSES = (
    # 歼灭者全家的主线剧情版(advent 那 4 个另在降临池)
    "epuration_boss_single",             # 歼灭者
    "epuration_boss_another_single",     # 再战歼灭者
    "high_epuration_boss_single",        # 上位歼灭者个体
    "epuration_boss_variant_ver_single",  # 异形歼灭者(精灵/机械/龙)
    "epuration_boss_highest_main",       # 咒剑
    "epuration_boss_dragon_main",        # 吞噬星辰之物(⚠ 只有 80 档)
    # 龙
    "eye_dragon_boss", "eye_dragon_boss_ch12",   # 始龙之眼 / 祝星版
    # 其他真 boss
    "maou2",                    # 魔王
    "rec_android_boss_single",  # 雷克·雷吉斯塔
    "light_guardian_single",    # 精灵守护像
    "admin_human",              # 管理者(人型)
    "benzaiten",                # 形似弁天的魔物
    "guardian_totem_another",   # 诅咒图腾
    "devil_commander", "devil_commander_evil",   # 伊尔比斯 / 诅咒伊尔比斯
    "shiro",                    # 白虎兽人
    "wolf_assassin",            # 克劳斯
    # 联动「龙与言灵」
    "psychic_projection", "psychic_tomboygirl",
    "psychic_shouta", "psychic_shouta_sequel",
)


def boss_model(code: str) -> str:
    """boss 代号 → 模型族(资源路径里的族名);取不到返回 ""。

    两种路径形态都认:general_boss 的 `battle/boss/<族>/…`、
    standard_boss 的 `battle/enemy/boss/<族>…`。"""
    node = _tbl(GENERAL_BOSS).get(code) or _tbl(STANDARD_BOSS).get(code)
    leaves = list(node.values()) if isinstance(node, dict) else ([node] if node else [])
    for leaf in leaves:
        if isinstance(leaf, dict):
            continue
        text = leaf if isinstance(leaf, str) else leaf.decode("utf-8")
        for ln in text.split("\n"):
            for c in cells(ln):
                if "general_16dots" in c:
                    continue
                if c.startswith("battle/boss/"):
                    return c.split("/")[2]
                if c.startswith("battle/enemy/boss/"):
                    return c.split("/")[3]
        break
    return ""


# 「已有加强版」的来源池(2026-07-29 用户需求):追忆试炼/单人挑战、极时试炼
# 给的是同一个 boss 的 expert/EX 强化档,主线版留在池里只会白占一个位。
UPGRADED_SRC_CATS = ("expert_single", "solo_time_attack")


def main_story_boss_pool() -> list[dict]:
    """主线/EX 里手挑的 boss 层(名单见 MAIN_STORY_BOSSES)。

    同一个 field 在 `main_quest` 与 `ex_quest` 两张表都有,ex 是高难镜像
    (同场地敌等级更高)——两表合并后**按 field 取敌等级更高的一条**,
    自然落到 EX 版。⚠ 这个池不吃 MIN_QUEST_LEVEL 门槛:主线关卡的官方
    敌等级本来就低,难度由 resolve_level 取 boss 最强档 + 轮次曲线决定。

    **剔除在追忆试炼/极时试炼里已有加强版的 boss**:判据取「显示名 ∪ 模型族」——
    强化版换了攻击程序签名,`_family()` 那套去重认不出它俩是同一个角色
    (实测命中「管理者」:主线人型版 admin_human vs 追忆 administrator_light_expert)。
    """
    names = wb.boss_names()
    upgraded_names: set[str] = set()
    upgraded_models: set[str] = set()
    for cat in UPGRADED_SRC_CATS:
        for e in quest_pool(cat):
            for b in e["bosses"]:
                nm = str(names.get(b, "")).split("/")[0]
                if nm:
                    upgraded_names.add(nm)
                model = boss_model(b)
                if model:
                    upgraded_models.add(model)

    best: dict[str, dict] = {}
    for cat in ("main", "ex"):
        for e in quest_pool(cat):
            picked = [b for b in e["bosses"] if b in MAIN_STORY_BOSSES]
            if not picked:
                continue
            if any(str(names.get(b, "")).split("/")[0] in upgraded_names
                   or (boss_model(b) and boss_model(b) in upgraded_models)
                   for b in picked):
                continue
            lv = int(e["level"]) if str(e["level"]).isdigit() else 0
            cur = best.get(e["field"])
            cur_lv = int(cur["level"]) if cur and str(cur["level"]).isdigit() else -1
            if lv > cur_lv:
                best[e["field"]] = e
    return list(best.values())


def minion_boss_pool() -> list[dict]:
    """杂鱼 boss 层(2026-07-29 用户需求:第1战小怪房、**第2战打杂鱼 boss**)。

    = 主线里 zone boss **全部**命中杂兵提拔族判据的场地(is_minion_boss:真 boss
    从不出现在 general_zako,有同族前缀的即小怪提拔上来的)。比纯小怪房多一条
    boss 血条,又不至于第 2 战就上硬仗;这批 boss 也正是"最难版本"过滤会
    整体刷掉的那 16 个族,放在这里刚好各得其所。"""
    zk = set(q.load_table(GENERAL_ZAKO))
    out = []
    for entry in quest_pool("main"):
        bosses = entry["bosses"]
        if bosses and all(is_minion_boss(b, zk) for b in bosses):
            out.append(entry)
    return out


# ---- 深渊诅咒 v2(2026-07-19 用户需求:大胆增益减益,取代 v6 随机场地效果)----
# 可用旋钮(均有官方先例,零客户端改动):
#   battle_enemy_condition_1..5(c71-80):kind 0能力/1直击/2弹射/3技能=伤害耐性
#     (正=敌减伤,负=敌易伤,官方超3用过 -4),kind 4=敌方减益免疫;枚举仅此 5 种
#     (InitialEnemyCondition 反编译实锤,无隐藏项)。
#   c94 boss 韧性修正:官方 700007 无尽档用到 ×9。
#   c97 FEVER 槽上限:官方标准 400,无尽档 1000(越高 fever 越难攒)。
#   c100 战斗时限帧:官方恒 54000(15分),压低=倒计时压力。
# 诅咒 = 具名效果包,按 --curse 档位(standard/abyss/hell)取三档强度;
# 深度排程:≤15% 无 / ≤45% 1个 / ≤75% 2个 / >75% 2个(hell 3个)。
# 反编译实锤(InitialEnemyCondition.as):0=AbilityDamage 1=DirectAttackDamage
# 2=PowerFlipDamage(**强化弹射**,非普通球撞) 3=SkillDamage 4=Debuff。
# ⚠ 普通弹射(球接触伤害)没有对应免疫项,枚举里不存在 —— 标签必须写"强化弹射",
# 写成"弹射"会让人以为球撞也免疫(2026-07-28 用户实测反馈)。
COND_KIND_CN = {0: "能力", 1: "直击", 2: "强化弹射", 3: "技能"}
CURSE_TIERS = ("standard", "abyss", "hell")

# ---- 深渊法阵:官方场程序菜单(2026-07-19 全库扫描精选)----
# 施法载体=克隆 curse_eye 的"祭坛"zako,c30(enemy_action101)指向现成官方场程序,
# 塞进克隆 zone 的空 zako 槽。参数(数值/时长/目标)烤死在程序二进制里,只选不调。
# 预载安全实锤:resolver case 80(StartBuffField)/84(StartModifierField)/65(CreateFlood)
# 都有完整资产解析(buff_field 动画/field_text 动态字牌/boss_flood)。
FIELD_MENU = [
    ("圣蟹充能阵", "battle/action/enemy/action/boss_hermit_crab_another_light_ex/boss_hermit_crab_another_light_ex$skill_charge_field1", "充能加速领域", "加成"),
    ("连击法阵", "battle/action/enemy/action/boss_smr21_middle_boss/smr21_middle_boss$difficulity10_field_buf2", "连击加成领域", "加成"),
    ("封连领域", "battle/action/enemy/action/boss_haniwa_great_dark/boss_haniwa_great_dark$pf_field", "连击限制", "诅咒"),
    ("禁疗领域", "battle/action/enemy/action/boss_epuration_highest/boss_epuration_highest$field_debuff", "治疗禁止", "诅咒"),
    ("禁益领域", "battle/action/enemy/action/boss_chapter12_boss/boss_chapter12_boss$field_start1", "增益禁止", "诅咒"),
    ("血滑领域", "battle/action/enemy/action/boss_reine_rouge/boss_reine_rouge_form1$field_effect_expansion", "滑行损血", "诅咒"),
    ("深渊之水", "battle/action/enemy/action/boss_spirit_beast_water/boss_spirit_beast_water$drown_buf", "全场淹水", "场地"),
    ("元素统一场", "battle/action/enemy/action/boss_epuration_highest/boss_epuration_highest$element_field", "歼灭者元素场", "场地"),
    ("元素结界", "battle/action/enemy/action/boss_administrator_another_dark_ex/boss_administrator_another_dark_ex$field_pf", "元素耐性结界", "领域"),
    ("炎兽领域", "battle/action/enemy/action/boss_spirit_beast_fire/boss_spirit_beast_fire$spirit_beast_field_effect", "耐性+攻击领域", "领域"),
]

# 允许进**随机**法阵抽取的分类。
# 「环境」= CreateWindAttack / CreateGravitationalField 两个 2026-07-29 新放行的命令,
# 共 73 项。**真机实验已通过**(1.4.238 钉选第3战刮风/第4战重力,用户实测两层效果
# 都正常出现;第5战淹水=已验证对照组),据此放开随机池。
# 放行依据(三条都查过,不是只看那两个样本):
#   ① 73 项全是**单命令**(46 重力 + 27 刮风),零"复合"夹带;
#   ② **零资产路径参数** ⇒ 不存在"引用超出预载集合"的 C8016 路径;
#   ③ 重力的定位是**语义锚**(Top×76/Left×71/Center×36/Right×5)+ 相对偏移(±250/±420),
#      不是烤死的地形坐标 ⇒ 不踩 C14102 位移炸弹。
# ⚠ 真机只覆盖了 Center 锚(gravity_pf)与中段强度刮风(1,0.5,600);其余变体靠上面
#   三条结构判据外推。剩余风险是**观感**(重力井位置/刮风过强)而非崩溃。
# ⚠ CreateTornado 仍不放行:它带绝对坐标 + 外部特效路径,本次实验的结论**不迁移**
#   (刮风/重力没有资产引用,证明不了 resolver 会走 tornado 的字符串参数)。
FIELD_RANDOM_CATS = {"加成", "诅咒", "场地", "领域", "环境"}

_FIELD_MENU_ALL: list | None = None


def field_menu_all() -> list[tuple[str, str, str]]:
    """完整领域菜单 = 内置精选 + wf_field_catalog 全量净场目录(签名去重)。

    目录由 `python mod-tools/wf_field_catalog.py --write` 生成(131 程序/57 签名,
    AMF3 全解析);缺文件时回退内置 10 项。"""
    global _FIELD_MENU_ALL
    if _FIELD_MENU_ALL is None:
        menu = list(FIELD_MENU)
        try:
            cat = json.load(open(os.path.join(MOD_DIR, "rogue_field_menu.json"),
                                 encoding="utf-8"))
            have = {m[1] for m in menu}
            for c in cat:
                if c.get("dup") or c["program"] in have:
                    continue
                menu.append((c["label"], c["program"], c["note"], c.get("cat", "领域")))
                have.add(c["program"])
        except Exception:
            pass
        _FIELD_MENU_ALL = menu
    return _FIELD_MENU_ALL


PLAN_TIERS = {"easy": ("off", 0.85), "normal": ("standard", 1.0),
              "elite": ("abyss", 1.0), "hell": ("hell", 1.15)}

# ---- 特殊 boss 原味保护名单(2026-07-26 用户需求)----
# rogue_special_bosses.json 的 authentic 名单:这些 boss 被随机抽中时**保持原场地
# 原机制**(mix 不拆解拼接),诅咒/等级修正照常叠加。general 系特殊 boss 的深渊法阵
# 仍可落(克隆自身追加程序=原样+机制);standard 系(菲诺梅那/终始之龙等)无 action
# 列可挂,法阵落不上(两条克隆路 2026-07-26 均已探明不通)。
SPECIAL_BOSSES_PATH = os.path.join(MOD_DIR, "rogue_special_bosses.json")


def load_special_bosses() -> tuple[set[str], tuple[str, ...]]:
    """返回 (精确代号集, 前缀元组)。命中任一即原味保护。

    authentic_prefixes 用于整族保护(如 guardian_golem 全变体带突击位移,
    dark_matter 带变身位移——位移锚点烤在老家地形,异地拼接必 C14102)。"""
    try:
        data = json.load(open(SPECIAL_BOSSES_PATH, encoding="utf-8"))
        exact = set(map(str, data.get("authentic", [])))
        exact |= set(map(str, data.get("authentic_movement", [])))
        prefixes = tuple(map(str, data.get("authentic_prefixes", [])))
        # 插座族(嵌入场地的 boss:管理者/火力压制)双向危险:boss 出走=原味保护,
        # 老巢当拼接容器=地形侧排除(mix_pick 处理)
        prefixes += tuple(map(str, data.get("socket_families", [])))
        return exact, prefixes
    except Exception:
        return set(), ()


def load_high_threat_rules(
        path: str | os.PathLike[str] = SPECIAL_BOSSES_PATH
        ) -> tuple[tuple[str, ...], frozenset[str]]:
    """读取作者维护的高威胁前缀/精确代号；配置错误必须响亮失败。"""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if "high_threat" not in data:
        raise ValueError(f"{path} 缺少 high_threat 键")
    raw = data["high_threat"]
    if not isinstance(raw, dict):
        raise TypeError("high_threat 必须是对象")
    for key in ("prefixes", "exact"):
        if key not in raw:
            raise ValueError(f"high_threat 缺少 {key} 键")
        if not isinstance(raw[key], list):
            raise TypeError(f"high_threat.{key} 必须是字符串数组")

    def clean(key: str) -> tuple[str, ...]:
        values: list[str] = []
        for index, value in enumerate(raw[key]):
            if not isinstance(value, str):
                raise TypeError(f"high_threat.{key}[{index}] 必须是字符串")
            value = value.strip()
            if not value:
                raise ValueError(f"high_threat.{key}[{index}] 不得为空字符串")
            if value not in values:
                values.append(value)
        return tuple(values)

    return clean("prefixes"), frozenset(clean("exact"))


def is_high_threat_bosses(bosses, prefixes: tuple[str, ...],
                          exact: frozenset[str]) -> bool:
    """HP 重排完成、mod clone 改名前，对实际 boss 代号匹配高威胁规则。"""
    return any(str(code) in exact
               or any(str(code).startswith(prefix) for prefix in prefixes)
               for code in bosses)


def prefer_non_threat_candidates(candidates: list, r: int | None, n: int,
                                 bosses_of, prefixes: tuple[str, ...],
                                 exact: frozenset[str]) -> list:
    """前 20% 楼层有普通合格项时回避高威胁；耗尽时保留原候选。"""
    if r is None or n <= 0 or r / n > 0.2:
        return candidates
    ordinary = [candidate for candidate in candidates
                if not is_high_threat_bosses(
                    bosses_of(candidate), prefixes, exact)]
    return ordinary or candidates


# ---- 精选 boss 加权(2026-07-29 用户需求:高价值 boss 出场率太低)----
# rogue_special_bosses.json 的 featured_bosses(前缀匹配,代号本身也是自己的前缀)
# + featured_weight(默认 4)。抽取时命中的候选按权重重复进候选表 = 权重 ×N,
# 不是硬钉:池子照常随机,只是天平往稀有 boss 倾斜。与全塔配额去重、
# prefer_fresh 历史降权叠加使用(先去重→再降权→最后加权)。
FEATURED_DEFAULT_WEIGHT = 4


def load_featured_bosses() -> tuple[tuple[str, ...], int]:
    """(精选前缀元组, 权重倍数);配置缺失返回空名单=不加权。"""
    try:
        data = json.load(open(SPECIAL_BOSSES_PATH, encoding="utf-8"))
        prefixes = tuple(map(str, data.get("featured_bosses", [])))
        weight = int(data.get("featured_weight", FEATURED_DEFAULT_WEIGHT))
        return prefixes, max(1, weight)
    except Exception:
        return (), FEATURED_DEFAULT_WEIGHT


def is_featured(bosses, prefixes: tuple[str, ...]) -> bool:
    return any(str(b).startswith(p) for p in prefixes for b in bosses)


def load_socket_families() -> tuple[str, ...]:
    try:
        data = json.load(open(SPECIAL_BOSSES_PATH, encoding="utf-8"))
        return tuple(map(str, data.get("socket_families", [])))
    except Exception:
        return ()


def load_transplant_policy() -> tuple[bool, set[str]]:
    """白名单制(2026-07-28 三崩后默认):True 时仅 transplant_safe 可被移植,其余原味。"""
    try:
        data = json.load(open(SPECIAL_BOSSES_PATH, encoding="utf-8"))
        return (bool(data.get("strict_transplant", True)),
                set(map(str, data.get("transplant_safe", []))))
    except Exception:
        return True, set()


def is_special_boss(code: str, special: tuple[set[str], tuple[str, ...]]) -> bool:
    exact, prefixes = special
    return code in exact or any(str(code).startswith(p) for p in prefixes)


# ---- boss 出场历史(2026-07-26 用户需求:出现过的 boss 降低再出现概率)----
# work/rogue_boss_history.json = 最近 3 座塔的 boss 名单;抽取时 80% 概率
# 优先从"最近两座塔没出过"的候选里挑,新面孔优先但不绝对禁止(池子小不至于枯竭)。
BOSS_HISTORY_PATH = os.path.join(MOD_DIR, "work", "rogue_boss_history.json")


def load_boss_history() -> list[list[str]]:
    try:
        data = json.load(open(BOSS_HISTORY_PATH, encoding="utf-8"))
        return [list(map(str, tower)) for tower in data.get("recent", [])][:3]
    except Exception:
        return []


def save_boss_history(bosses: list[str]) -> None:
    recent = [sorted(set(bosses))] + load_boss_history()
    os.makedirs(os.path.dirname(BOSS_HISTORY_PATH), exist_ok=True)
    with open(BOSS_HISTORY_PATH, "w", encoding="utf-8") as fh:
        json.dump({"recent": recent[:3]}, fh, ensure_ascii=False, indent=1)


# ---- 全塔难度预设(2026-07-26 用户需求:任意层数 + 三种难度类型)----
# 成长曲线改端点式:起点/终点倍率固定,growth = (end/start)^(1/(n-1)) 按层数自适应,
# 8 层和 33 层都是同样的起终点难度,不会指数爆炸。tier=None(gradient)= 按深度
# off→standard→abyss→hell 四段递进。
# 2026-07-29 起点上调(用户真机反馈:玛格诺斯/泽古拉/元素球「都太弱」):
# 端点式曲线的**起点**决定前中段体感,原 gradient 起点 0.4 让第 9 战只有 hp×1.44。
# 只抬起点+略抬终点,曲线形状不变(层数自适应仍成立)。
# 对照(30 层 gradient):第9战 hp 1.44→2.62、第15战 2.9→5.2、末战 25→30。
# ⚠ **atk 端点已按官方参照带压回**(2026-07-29,用户「不要太高或者太低」)。
# 反编译列位实锤(`弹国服/scripts/pinball/master/generated/*QuestValues.as`:
# field 列 f 起算 f-10=hp_boss、f-7=atk_boss、f-3=enemy_level,20 张表一致)后统计
# **官方 3393 行**:
#   · lv100 的 atk_boss —— 中位 **1.0**、p90 1.215、**max 6.63**(全库唯一离群点,第二名 1.8)
#   · **全库没有任何一行 atk 修正 > 10**
#   · 官方**不靠 quest HP 修正抬难度**；rush 110 个 c86 样本全是 1.0，
#     真血量来自 boss_level / standard 战斗资源，而不是 quest c86
# 旧值 atk 终点 18.0 配上玻璃深渊 ×3.0 与 PLAN_TIERS ×1.15,末层写进 c89-91 的倍率
# 达 **62.1**,实测线上塔 atk 中位 8.92 / 最高 80.09,**比官方天花板高一个数量级**。
# 新端点把典型攻击值拉回官方带内；旧 HP 端点现只保留难度同比缩放/热身代理，
# general boss 的最终真血量由绝对 DPS 目标反解进 clone boss_level.c2。
# ⚠ **hp 端点同样压回**(用户指定参照:无幻之宴 / 机工神兵菲诺梅那)。
# 查官方原值 —— 这两个在 lv100 的修正是 **全 1.0**(菲诺梅那在降临讨伐甚至 0.7),
# 难度完全来自 enemy_level=100 + 它们自带的数值。而我们这座塔给**同一场战斗**写的是
# 菲诺梅那 hp 22.28/atk 4.64、无幻之宴 hp 40.02/atk 16.29 —— 把官方战斗做成了 40 倍血。
# 这两个都是 standard 系(无 boss_level 基数、**不参与归一**),拿到的就是裸曲线值,
# 所以曲线端点本身必须压。
# 新口径:**×1.0 ≈ 无幻之宴/菲诺梅那 那一档**,曲线只负责深度推进(首层 0.6× → 末层 3×);
# boss 之间的强弱差由归一化补偿承担,不再靠曲线堆。
# ⚠ **2026-07-30 二次压回:刀→血**(玩家「连战 boss 伤害过高」审计)。
# 上一轮把 atk 终点从 18.0 压到 2.5 之后,实测中后段 col 中位仍有 4.03 —— 因为
# 终点只管曲线,真正落表的是 曲线×来源补偿×归一化×**攻击诅咒**。烈狱档 16/30 层
# 带攻击诅咒且顶格,叠在塔尾自身已达 2.4-3.3 的曲线上。
# 端点扫描(3 seed × 5 档,scratchpad/sweep_endpoint.py):atk 终点 2.5 时分位闸要
# 出手 20 次、把中后段攻击诅咒**全部摘光**才进带;终点 1.7 时只出手 6 次(多为降档
# 而非摘除),中后段仍有 6/20 层保留攻击诅咒 —— 闸门回到"兜底"而不是"主力"。
# atk **起点不动**(0.8):玩家反馈「前10关都不算强」,前段本就不该再削。
# 2026-08-05 真机裁定覆盖旧“放大 c86”方案：官方 rush c86 无 >1 先例，
# general 血量主伸缩必须改写克隆 boss_level.c2，quest c86 固定 1.0。
DIFF_PRESETS = {
    #            hp起  hp终   atk起 atk终  诅咒档
    "easy":     (0.3,  1.2,   0.3,  0.9,  "off"),
    "normal":   (0.5,  2.2,   0.5,  1.3,  "abyss"),
    "hell":     (0.9,  4.0,   1.1,  1.1,  "hell"),
    "gradient": (0.5,  2.6,   0.6,  1.5,  None),
}

# ---- atk 落表值的**显式构建期硬闸**(2026-08-05 定档)----
# solve_atk 只报告真实乘积；enforce_atk_band 先降攻击诅咒，再降低该层 ba，
# 每次变更后完整重算并写日志。以下兼容常量统一表达最终 c89/c91 硬上限。
ATK_MULT_CEILING = 1.5
ATK_COMBO_CAP = 1.5
NOBASE_ATK_CAP = 1.5
# 真伤指数 = boss 原生 atk(该层等级)× 落表 col ÷ 同曲线组中位锚。
# col 合规 ≠ 真伤合规:第6战青之女王 col 只有 1.90,但原生 atk ≈ 中位 3 倍,
# 0.55 幂压缩没压平 → 真伤指数 5.62 = 全塔第一(隐形尖峰)。这条直接封每跳伤害。
TRUE_DMG_CAP = 4.0
# 带 funnel 的层:炮台弹幕同吃 boss 列倍率(第18战巫妖 4.68/第29战深渊之云 4.81),
# 玩家会把它算进"boss 伤害"。c90 相对 c91 降档。
FUNNEL_ATK_SCALE = 0.6
# 报告仍保留前/中后段切片；实际分位硬闸与 max=1.5 覆盖全塔。
BAND_FROM = 1 / 3
BAND_TARGET = {"median": 1.1, "p90": 1.35, "max": 1.5}
# 敌等级爬坡三段(--enemy-level ramp,默认)。官方 enemy_level 分布:lv80 是主流
# 难档(662 行 21.9%),lv100 只有 127 行(4.2%);atk_correction_curve 实解
# lv79=1.898 / lv89=1.992 / lv99=2.505 / lv100=3.267 —— lv100 是曲线悬崖顶,
# 全塔平坦 lv100 等于把 96% 官方内容不敢站的位置站满 30 层。
LEVEL_RAMP = (80, 90, 100)

# 任务 D（2026-08-05 真机裁定）：默认不是“逐层爬坡”，而是除第 1 战小怪
# 热身外，全程都站在多人决战的单人目标带。旧 60 万→2500 万几何线只由
# 显式 --ramp 恢复；不得再让首尾比门禁反过来判平坦模式违规。
TARGET_DPS_FIRST = 25_000_000.0
TARGET_DPS_LAST = 25_000_000.0
TARGET_DPS_LAST_BAND = (21_940_625.0, 30_716_875.0)
RAMP_TARGET_DPS_FIRST = 600_000.0
RAMP_TARGET_DPS_LAST = 25_000_000.0
WARMUP_TARGET_DPS = 600_000.0
MAX_DPS_DOWN_JITTER = 0.15
STANDARD_C86_LIMITS = (0.9, 1.1)

# 30 层塔的深层硬锚。正式池经“只留最高 quest rank”后仅剩 eye + 妄羊3/4，
# 不足 6 个安全 general_boss 领域载体；全库约束匹配证明最小扩池是再纳入：
#   - score_event_shark（独立 score-event 来源，但放进塔后仍由 event_quest logic 驱动）；
#   - 妄羊1/2 的低 quest-rank field（boss_level 在塔内 lv100 可完整解析）。
# 六层均为已知曲线/绝对 HP 证据、代号互异，c86 解落在 3.90~7.07。c36=true
# 只会禁属性免疫，不会禁普通 StartBuffField 领域；载体门禁仍在 main 内逐层复核。
DEEP_HP_ANCHOR_FIELDS_30 = (
    "score_event_shark",
    "eye_dragon_multibattle",
    "raid_alter_sheep_materia1",
    "raid_alter_sheep_materia2",
    "raid_alter_sheep_materia3",
    "raid_alter_sheep_materia4",
)

# r16~24 的领域/血量联合锚。九层均经正式来源表、单人 zone、等级 ramp、
# general/standard 原生 HP 解析链和 caster_carrier_block 逐项复核；所需 c86
# 为 12.43~18.55，落在用户裁定的中段官方窗口 0.1~30。它们的实际 general_boss
# c36=true，因此普通领域可挂、属性免疫会由现有 c36 门禁拒绝并重抽。
MID_HP_ANCHOR_FIELDS_30 = (
    "multi_normal_1_10_4",
    "multi_normal_1_3_3",
    "raid_yokai_emaki_middle_boss",
    "multi_normal_1_6_4",
    "yokai_emaki_01_big_boss_multi",
    "big_boss_anv1_multi",
    "advent_z_collabo",
    "desert_bonds_big_boss_multi_ex",
    "summer_2020_boss_multi",
)

# 早段动态重排的保底候选。它们不是固定排程：正常随机结果只要原生 HP 能让
# 基线 c86 命中窗口就原样保留；只有异构池抽到过薄/过厚 boss 时，才与正式来源池
# 一起参与候补。此清单保证 r2~15 至少存在一组已复算可行解，避免算法因某次池变动
# 无候选而靠放宽窗口蒙混过关。
EARLY_HP_FALLBACK_FIELDS_30 = (
    "solo_time_attack_green1",
    "halfanv3",
    "anv3",
    "haniwa_carnival_dark_direct",
    "multi_normal_1_19_4",
    "haniwa_carnival_dark",
    "anv3_hell",
    "advent_spirit_beast_thunder_4",
    "mechanic_dragon_eater_multi_80",
    "advent_r_collabo",
    "advent_xm22",
    "haniwa_carnival_dark_pf",
    "advent_s_collabo1",
    "steampunk_another",
)


def target_dps(r: int, n: int, *, ramp: bool = False) -> float:
    """第 r 关 HP 预算；默认全程 2500 万，``ramp`` 才走旧几何线。"""
    if n < 2 or not 1 <= r <= n:
        raise ValueError(f"DPS 曲线轮次越界:r={r},n={n}")
    if not ramp:
        return TARGET_DPS_LAST
    progress = (r - 1) / (n - 1)
    return RAMP_TARGET_DPS_FIRST * (
        (RAMP_TARGET_DPS_LAST / RAMP_TARGET_DPS_FIRST) ** progress)


def configured_target_dps(r: int, n: int, hp_base: float, hp_growth: float,
                          stage_multiplier: float = 1.0, *,
                          ramp: bool = False) -> float:
    """把旧 HP 难度端点映射到选定的 flat/ramp 绝对 DPS profile。

    选中的 flat/ramp profile 是 hell 默认锚；`--difficulty` / `--hp-base` /
    `--hp-growth` 仍通过“当前旧曲线 ÷ hell 旧曲线”等比缩放它。
    工坊阶段乘区只乘基线目标；血量/时限诅咒仍在随后的
    realized 层生效，不能被这个函数抵消。

    来源 `bh` 与旧 HP normalize 不再二次乘入：它们原本是在原生
    HP 不可见时的代理，现在已由 general/standard 真 HP 反解取代。
    """
    if n < 2 or not 1 <= r <= n:
        raise ValueError(f"DPS 曲线轮次越界:r={r},n={n}")
    vals = (float(hp_base), float(hp_growth), float(stage_multiplier))
    if not all(math.isfinite(v) and v > 0 for v in vals):
        raise ValueError(
            f"HP 目标缩放必须为有限正数:base={hp_base},"
            f"growth={hp_growth},stage={stage_multiplier}")
    hell_base, hell_end = DIFF_PRESETS["hell"][:2]
    hell_growth = (hell_end / hell_base) ** (1 / (n - 1))
    configured = vals[0] * (vals[1] ** (r - 1))
    canonical = hell_base * (hell_growth ** (r - 1))
    return target_dps(r, n, ramp=ramp) * configured / canonical * vals[2]


def deep_hp_anchor_field(r: int, n: int) -> str | None:
    """返回 30 层成品塔 r25~30 的绝对 HP / 领域载体锚；其它塔高不强套。"""
    if n != 30:
        return None
    first = 25
    return DEEP_HP_ANCHOR_FIELDS_30[r - first] if first <= r <= 30 else None


def mid_hp_anchor_field(r: int, n: int) -> str | None:
    """返回 30 层成品塔 r16~24 的绝对 HP / 单领域载体锚。"""
    if n != 30:
        return None
    first = 16
    return MID_HP_ANCHOR_FIELDS_30[r - first] if first <= r <= 24 else None


def hp_correction_limits(r: int, n: int) -> tuple[float, float]:
    """最终 quest c86 窗口；中段放宽，深层重新收紧。"""
    if not 1 <= r <= n:
        raise ValueError(f"HP 修正窗口轮次越界:r={r},n={n}")
    if n == 30 and 16 <= r <= 24:
        return (0.1, 30.0)
    return (0.1, 10.0)


def solve_hp_correction(dps: float, duration_s: float, native_hp: float) -> float:
    """由目标 DPS、实战时长和 c86 前原生 HP 反解 quest HP 修正。"""
    vals = (float(dps), float(duration_s), float(native_hp))
    if not all(math.isfinite(v) and v > 0 for v in vals):
        raise ValueError(f"HP 修正输入必须为有限正数:dps={dps},time={duration_s},hp={native_hp}")
    value = vals[0] * vals[1] / vals[2]
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"HP 修正解非法:{value}")
    return value


def hp_curve_errors(records: list[dict], n: int,
                    last_band: tuple[float, float] = TARGET_DPS_LAST_BAND, *,
                    ramp: bool = False) -> list[str]:
    """flat/ramp 两套互斥 HP profile 门禁；返回空列表即通过。

    `verified` 只影响报告覆盖率，不允许把不可验层静默当成 0；门禁仍读取它的
    显式估算 DPS，使首尾/相邻趋势至少有可审计数字。
    """
    errors: list[str] = []
    rows = sorted((rec for rec in records if rec.get("baseline_dps") is not None),
                  key=lambda rec: int(rec["r"]))
    if not rows:
        return ["没有可审计的 DPS 记录"]
    if not ramp:
        by_round = {int(rec["r"]): rec for rec in rows}
        warmup = by_round.get(1)
        if warmup is not None and not warmup.get("warmup"):
            errors.append("第1关未标记为唯一小怪热身豁免层")
        missing = [r for r in range(2, n + 1) if r not in by_round]
        if missing:
            errors.append("缺少 boss 层 DPS 记录:" + ",".join(map(str, missing)))
        lo, hi = map(float, last_band)
        for r in range(2, n + 1):
            rec = by_round.get(r)
            if rec is None:
                continue
            dps = float(rec["baseline_dps"])
            if not lo <= dps <= hi:
                errors.append(f"第{r}关基线 DPS {dps:.0f} 未进全程目标带 {lo:.0f}~{hi:.0f}")
        return errors
    for prev, cur in zip(rows, rows[1:]):
        if (float(cur["baseline_dps"]) + 1e-9
                < float(prev["baseline_dps"]) * (1 - MAX_DPS_DOWN_JITTER)):
            errors.append(
                f"第{cur['r']}关基线 DPS 下跌超过15%:"
                f"{prev['baseline_dps']:.0f}→{cur['baseline_dps']:.0f}")
    first = next((rec for rec in rows if int(rec["r"]) == 1), None)
    last = next((rec for rec in rows if int(rec["r"]) == n), None)
    if first is None or last is None:
        errors.append(f"首尾记录不完整:round1={first is not None},round{n}={last is not None}")
        return errors
    last_dps = float(last["baseline_dps"])
    if not float(last_band[0]) <= last_dps <= float(last_band[1]):
        errors.append(f"第{n}关 DPS {last_dps:.0f} 未进末层目标带")
    ratio = last_dps / float(first["baseline_dps"])
    if not 35.0 <= ratio <= 50.0:
        errors.append(f"首尾 DPS 比 {ratio:.2f}× 不在 35~50×")
    return errors


def hp_short_time_errors(records: list[dict]) -> list[str]:
    """任意层若短于 300 秒且实战需求超过 2000 万/s，直接拒绝。"""
    errors: list[str] = []
    for rec in records:
        try:
            duration = float(rec["duration_s"])
            dps = float(rec["realized_dps"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"第{rec.get('r', '?')}战短时限审计字段不完整")
            continue
        if duration < 300.0 and dps > 20_000_000.0:
            errors.append(
                f"第{rec['r']}战短时限与高血量同时命中:"
                f"{duration:.0f}s/{dps:.0f} DPS")
    return errors


def hp_correction_errors(records: list[dict], n: int) -> list[str]:
    """最终 c86 按 HP 主通道验收；只报错，不做静默 clamp。"""
    errors: list[str] = []
    for rec in records:
        try:
            r = int(rec["r"])
            c86 = float(rec["c86"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"第{rec.get('r', '?')}战 c86 审计字段不完整")
            continue
        family = str(rec.get("family") or "")
        if family == "no-boss" and rec.get("warmup"):
            continue
        if family == "general":
            if not math.isclose(c86, 1.0, rel_tol=0.0, abs_tol=1e-12):
                errors.append(f"第{r}战 general 最终 c86={c86:g}（必须恒为 1）")
            continue
        if family in {"standard", "identity-locked"}:
            lo, hi = STANDARD_C86_LIMITS
            if not lo <= c86 <= hi:
                errors.append(
                    f"第{r}战 {family} 最终 c86={c86:g} "
                    f"超出微调窗口 {lo:g}~{hi:g}")
            continue
        errors.append(f"第{r}战 HP 族/通道不可审计:{family or '(missing)'}")
    return errors


def native_hp_coverage_errors(floor_records: list[dict]) -> list[str]:
    """A 路径覆盖门禁：有 boss 的层不得退成无证据代理。

    纯小怪热身没有 boss 血条，不在用户给定的 29 层 boss 公式内；它是唯一允许
    `verified=false` 的结构性例外。新 boss 类型一旦读不到，必须显式扩解析器或拒绝。
    """
    errors = []
    for rec in floor_records:
        bosses = list((rec.get("pick") or {}).get("bosses") or [])
        native = rec.get("native_hp") or {}
        if bosses and not native.get("verified"):
            errors.append(
                f"第{rec.get('r')}战 boss HP 无绝对证据:"
                f"{','.join(map(str, bosses))} ({native.get('reason') or 'unknown'})")
    return errors


def difficulty_curve(diff: str, n: int) -> tuple[float, float, float, float]:
    """难度预设 → (hp_base, hp_growth, atk_base, atk_growth),端点式按层数求增长率。"""
    hp0, hp1, atk0, atk1, _tier = DIFF_PRESETS[diff]
    steps = max(1, n - 1)
    return (hp0, (hp1 / hp0) ** (1 / steps), atk0, (atk1 / atk0) ** (1 / steps))


def tier_for_round(diff: str, r: int, n: int) -> str:
    """难度预设 → 该层诅咒档位。gradient = 按深度四段递进(从简单到难)。"""
    tier = DIFF_PRESETS[diff][4]
    if tier is not None:
        return tier
    d = r / n
    if d <= 0.25:
        return "off"
    if d <= 0.5:
        return "standard"
    if d <= 0.75:
        return "abyss"
    return "hell"


def is_minion_boss(code: str, zako_keys: set[str]) -> bool:
    """杂兵提拔族判定(2026-07-28 用户强度调查):真 boss 从不出现在 general_zako,
    小怪表里有同族前缀的"boss"=杂兵提拔(地鼠/镰鼬/警备机/枪兵…),观感弱。
    规则:过 1/3 进度后只出真 boss。"""
    parts = str(code).split('_')
    for n in range(len(parts), 0, -1):
        if '_'.join(parts[:n]) in zako_keys:
            return True
    return False


def floor_tier(field: str) -> int:
    """楼层强度档 1(最浅)~5(最深),按塔区编号;非塔场地(幽玄域单人本等)=2
    (2026-07-27 用户反馈:默认 3 会让简单 boss 漏进后半程)。

    伪随机排布用:深关只从高档抽,杜绝"后期撞见简单小 boss"。"""
    m = re.match(r"tower_dungeon_+(low_)?area_(\d+)_", field)
    if not m:
        return 2
    if m.group(1):                      # low_area = 入门塔
        return 1
    area = int(m.group(2))
    if area <= 3:
        return 1
    if area <= 6:
        return 2
    if area <= 8:
        return 3
    return 4 if area == 9 else 5


def collapse_grades(entries: list[dict], name_of) -> list[dict]:
    """难度分级去重:同 boss(按显示名集合)只保留最高难度版本。

    分级副本(高级/超级/超级+)在池里是同前缀不同尾号的多个 field
    (multi_normal_1_16_1..4 / empress_wind_1..5),boss 相同强度不同——
    只留最难的一个。

    2026-07-29 起**先比敌等级、再比尾号**:等级列在 quest_level_of 修好之前
    不可信,只能拿尾号当代理;现在等级是权威档位,尾号退为同级时的兜底
    (empress_wind_1..5 这类同为 80 级的靠尾号分先后)。"""
    best: dict[frozenset, tuple[tuple[int, int], dict]] = {}
    order: list[frozenset] = []
    for e in entries:
        key = frozenset(name_of(e["bosses"]))
        m = re.match(r"^(.*?)_(\d+)$", e["field"])
        rank = (int(e["level"]) if str(e.get("level", "")).isdigit() else 0,
                int(m.group(2)) if m else 0)
        cur = best.get(key)
        if cur is None:
            order.append(key)
            best[key] = (rank, e)
        elif rank > cur[0]:
            best[key] = (rank, e)
    return [best[k][1] for k in order]


def build_schedule(n: int, rng) -> dict[int, str]:
    """楼层计划 v8(任意层数自适应,2~98 层):
    第 1 战恒=小怪房热身(n≥3;n=2 时首战直接进塔层,给奖励测试用);
    第 2 战 20% 概率再来一间小怪房;末战恒=终始之龙;
    末战-1=无幻之宴守门(n≥5);比例锚 领主战20%/机兵40%/降临讨伐55%/女帝歼灭者70%
    (撞位向后找空、再向前,塞不下放弃);其余全部=塔池(--mix 时为拼接层)。

    v9(2026-07-29):**领主战多位**。领主战池有 143 个场地(索拉斯双阶段八套、
    八岐大蛇各档都在里面),却只给 1 个位 → 单座塔抽中某个特定 boss ≈5.6%,
    用户「打了这么久没见过」。改成大塔多开位:<15 层 1 个、15-24 层 2 个、
    ≥25 层 3 个(全塔配额去重保证不会重样)。"""
    sched = {n: "终始之龙"}
    if n >= 3:
        sched[1] = "小怪房"
    if n >= 4:
        # v11(2026-07-29 用户需求):第2战固定"杂鱼 boss"(杂兵提拔族),
        # 替掉原来 20% 概率再来一间小怪房——热身两层的节奏改成 小怪→杂鱼boss。
        sched[2] = "杂鱼boss"
    if n >= 5:
        sched[n - 1] = "无幻之宴"
    if n >= 7:
        # 机工神兵菲诺梅那(steampunk_another 地狱级,双 boss 本体+foom2)
        # 与终始之龙同等待遇=常驻固定位,不参与随机。
        # 位置=**塔腰**(2026-07-29 用户指定:15层→7、30层→15、50层→25),
        # 不放末尾——末尾已经是 无幻之宴+终始之龙 的双守门。
        sched[max(3, n // 2)] = "机工神兵"
    anchors = [("领主战", 0.2), ("世界剧情", 0.3), ("机兵", 0.4),
               ("剧情活动", 0.48), ("降临讨伐", 0.55), ("女帝歼灭者", 0.7)]
    if n >= 17:
        anchors.append(("领主战", 0.62))
    if n >= 24:
        anchors.append(("领主战", 0.85))
    # v10(2026-07-29 全类别普查):6 类高价值来源以前整类抽不到,按塔高逐个开位。
    # 门槛按**容量**排——每个新来源多占一层,开太早会把塔池层挤光
    # (实测 10 层塔在门槛 0.34 时锚位吃满 1..10,一层崩坏域都不剩)。
    # 土俑嘉年华开 **3 个位**(2026-07-29 用户:一座塔最多来 3 个不同的土俑)——
    # 全塔配额去重保证三次抽到的是不同伤害体系的变体,不会重样。
    for label, frac, need in (("战阵之宴", 0.34, 16), ("单人挑战", 0.44, 18),
                              ("主线boss", 0.5, 19), ("极时试炼", 0.58, 20),
                              ("剧情boss", 0.66, 22), ("元素试炼", 0.76, 25),
                              ("土俑嘉年华", 0.28, 26), ("土俑嘉年华", 0.62, 28),
                              ("土俑嘉年华", 0.88, 30)):
        if n >= need:
            anchors.append((label, frac))
    # 锚位预算:塔池(崩坏域)是这个玩法的底色,**至少留 1/5 楼层**给塔层/拼接层。
    # 预算 = 总层数 − 固定位 − 保留位;超出的锚位按 anchors 先后顺序放弃。
    reserve = max(1, round(n * 0.2))
    budget = max(0, n - len(sched) - reserve)
    for label, frac in anchors[:budget]:
        t = max(2, min(n - 2, round(n * frac)))
        slot = next((s for s in list(range(t, n - 1)) + list(range(t - 1, 1, -1))
                     if s not in sched), None)
        if slot is not None:
            sched[slot] = label
    return sched


def layout_plan() -> dict:
    """连战工坊布局计划(GUI 写 mod-tools/rogue_layout_plan.json):
    {"stages": [{"from":1,"to":2,"tier":"easy|normal|elite|hell"}],
     "floors": {"5": {"curses": ["深渊重甲"], "field": "battle/…program"}}}
    stages 决定该层诅咒档位+难度乘区(PLAN_TIERS);floors 显式指定优先于随机。"""
    try:
        return json.load(open(os.path.join(MOD_DIR, "rogue_layout_plan.json"),
                              encoding="utf-8"))
    except Exception:
        return {}


def plan_tier_for(plan: dict, r: int, default_tier: str) -> tuple[str, float]:
    for st in plan.get("stages") or []:
        try:
            if int(st["from"]) <= r <= int(st["to"]):
                return PLAN_TIERS.get(str(st.get("tier")), (default_tier, 1.0))
        except (KeyError, ValueError, TypeError):
            continue
    return (default_tier, 1.0)


def field_tuning() -> dict:
    """领域数值调整配置(GUI 写 mod-tools/rogue_field_tuning.json):
    {"global": {"加成": 1.0, "诅咒": 1.0, "场地": 1.0, "领域": 1.0},
     "per": {program: 倍率}}。倍率≠1 时构建期锻造缩放变体(wf_field_catalog.forge)。"""
    try:
        return json.load(open(os.path.join(MOD_DIR, "rogue_field_tuning.json"),
                              encoding="utf-8"))
    except Exception:
        return {}


def pick_field_program(menu: list, rng):
    """法阵程序抽取:**全目录均匀**,每个条目一票。

    ⚠ 2026-07-29 曾按 √条目数 在分类间加权,理由是"刮风/重力的 73 项只是数值变体、
    观感上就两种效果"——**用户当场纠正:观感不一样**。实测参数跨度也支持这点:
    刮风强度 0.05→1.0(20 倍)、时长 280→3000 帧(4.7 秒→50 秒,10 倍);
    重力四种锚点(Top/Left/Center/Right)+ 94 种数值组合。那是 73 种不同体验。
    所以回到均匀,不替玩家做"这些看起来都一样"的判断。
    真正的问题是**标签分不出变体**,已在 wf_field_catalog.label_of 把强度/时长/
    锚点编进 note(「狂风领域·强风10秒·方向1」),而不是靠压低出场率来回避。
    """
    return menu[rng.randrange(len(menu))]


def log(message: str) -> None:
    """构建期审计日志。独立成函数,测试可截获“拒绝并重抽”而不吞输出。"""
    print(message)


# CreateCondition 的 AdditionalConditionKind 构造名。这里故意不用数字索引:
# 未知构造名在 validates=false 时会静默下落成索引 0,不崩不报、效果却像不存在。
DAMAGE_RESISTANCE_AC = {
    0: "ACAbilityDamageResistance",
    1: "ACDirectAttackDamageResistance",
    2: "ACPowerFlipDamageResistance",
    3: "ACSkillDamageResistance",
}
ELEMENT_DATA_CN = {1: "火", 2: "水", 3: "雷", 4: "风", 5: "光", 6: "暗"}
ELEMENT_CURSE_SPECS = {
    # 按随机排程强度排序；元素正抗性走 damage/(1+r)，不是伤害类型的 damage*(1-r)。
    "元素滞钝": (1, 1.0),
    "三相封界": (3, 9.0),
    "元素禁壁": (1, 99.0),
    "五相绝域": (5, 999.0),
}
MIXED_ELEMENT_CURSE_NAME = "混相禁域"
ELEMENT_CURSE_NAMES = (*tuple(ELEMENT_CURSE_SPECS), MIXED_ELEMENT_CURSE_NAME)
ELEMENT_RESISTANCE_STRENGTHS = (1.0, 9.0, 99.0, 999.0)
ELEMENT_LOCK_THRESHOLD = 99.0
STACKED_DAMAGE_STRENGTH = 0.01
STACKED_DEBUFF_STRENGTH = 1.0
STACKED_MAX_ACCUMULATION = 99
STACKED_DURATION_FRAMES = 9_999_999
STACKED_CURSE_NAMES = ("层叠龙鳞", "不屈龙心")
STACKED_DAMAGE_AC_KIND = {name: kind for kind, name in DAMAGE_RESISTANCE_AC.items()}


def element_immunity_requested(forced: dict | None) -> bool:
    """工坊是否明确要求本层保留属性免疫载体。"""
    names = list((forced or {}).get("curses") or [])
    return any(name in ELEMENT_CURSE_NAMES for name in names)


def hard_condition_carrier_requested(forced: dict | None) -> bool:
    """工坊是否钉了必须通过 general_boss c109 才能落地的词条。"""
    names = set(map(str, (forced or {}).get("curses") or []))
    return bool(names & (set(ELEMENT_CURSE_NAMES)
                         | set(DAMAGE_HARD_CURSE_NAMES)
                         | set(STACKED_CURSE_NAMES)))


def prefer_element_immunity_hp_candidates(ranked: list[tuple]) -> tuple[list[tuple], bool]:
    """HP 重排先用可挂属性免疫的候选；耗尽时显式回退原候选。

    每项最后一个元素是 metrics dict，其中 ``element_immunity_block=None``
    表示实际 general_boss 档、c36 与载体引用门禁均通过。返回值第二项为
    是否发生了“无合格载体，只能降级”的事实，调用方必须记录日志。
    """
    eligible = [item for item in ranked
                if item and isinstance(item[-1], dict)
                and item[-1].get("element_immunity_block") is None]
    return (eligible, False) if eligible else (ranked, bool(ranked))


DAMAGE_HARD_CURSE_NAMES = ("深渊壁垒", "绝对壁垒", "三重壁垒")
PRE_ACTION_CURSE_NAMES = DAMAGE_HARD_CURSE_NAMES + STACKED_CURSE_NAMES
HIGH_ONE_SHOT_CURSE_NAMES = (
    "绝对壁垒", "三重壁垒",
    *(name for name, (_count, strength) in ELEMENT_CURSE_SPECS.items()
      if strength >= ELEMENT_LOCK_THRESHOLD),
)
IMMUNITY_DURATION_FRAMES = 999_999


def stacked_resistance_layers_for_depth(r: int, n: int) -> int:
    """官方式累计层排程：前20% 20层，中段50层，最后20% 90层。"""
    if n <= 0 or not 1 <= r <= n:
        raise ValueError(f"轮次越界:r={r},n={n}")
    if r / n <= 0.2:
        return 20
    return 90 if r / n > 0.8 else 50


def stacked_resistance_entry(name: str, constructor: str,
                             strength: float, layers: int) -> dict:
    """构造一条叠层词条；文案只由真实单层强度与层数推导。"""
    strength = float(strength)
    layers = int(layers)
    if constructor not in (*STACKED_DAMAGE_AC_KIND, "ACToleranceOfDebuff"):
        raise ValueError(f"叠层抗性不支持构造 {constructor}")
    if not math.isfinite(strength) or strength <= 0:
        raise ValueError(f"叠层抗性单层强度非法:{strength}")
    if not 1 <= layers <= STACKED_MAX_ACCUMULATION:
        raise ValueError(f"叠层抗性层数必须为1~{STACKED_MAX_ACCUMULATION}:{layers}")
    if constructor == "ACToleranceOfDebuff":
        # ConditionChangeCalculator: 普通减益命中率 = hitRate - debuffResistance；
        # 随机数包含 0，所以 r=1 / hitRate=1 仍约十万分之一漏过；forceApply 始终绕过。
        text = (f"减益耐性×{layers}层（普通减益几乎无法命中；"
                "强制赋予除外）")
    else:
        kind = STACKED_DAMAGE_AC_KIND[constructor]
        reduction = strength * layers
        if reduction >= 1.0:
            label = "完全免疫"
        else:
            label = f"减{reduction * 100:.6g}%"
        text = f"{COND_KIND_CN[kind]}抗性×{layers}层（{label}）"
    return {"name": str(name),
            "stacked_resistance": [(constructor, strength, layers)],
            "text": text}


def _merged_stacked_resistance(picks: list[dict]) -> list[tuple[str, float, int]]:
    """合并同构造/强度的层数；超过官方 99 层上限即拒绝。"""
    layers_by_card: dict[tuple[str, float], int] = {}
    order: list[tuple[str, float]] = []
    for pick in picks:
        for constructor, strength, layers in pick.get("stacked_resistance", []):
            constructor = str(constructor)
            strength = float(strength)
            layers = int(layers)
            # 复用公开构造器做完整参数校验；这里只取其规范化结果。
            stacked_resistance_entry("_validate", constructor, strength, layers)
            key = (constructor, strength)
            if key not in layers_by_card:
                order.append(key)
            layers_by_card[key] = layers_by_card.get(key, 0) + layers
            if layers_by_card[key] > STACKED_MAX_ACCUMULATION:
                raise ValueError(
                    f"{constructor} 同参数累计 {layers_by_card[key]} 层>"
                    f"{STACKED_MAX_ACCUMULATION}，客户端会静默封顶")
    return [(constructor, strength, layers_by_card[(constructor, strength)])
            for constructor, strength in order]


def _stacked_resistance_totals(picks: list[dict]) -> dict[str, float]:
    """按客户端 strength×magnification 汇总叠层条件，不改变可见层 DSL。"""
    totals: dict[str, float] = {}
    for constructor, strength, layers in _merged_stacked_resistance(picks):
        totals[constructor] = totals.get(constructor, 0.0) + strength * layers
    return totals


def _normalize_resistance_atom(atom, key: str) -> tuple[int, float, bool]:
    """把旧二元耐性与新三元耐性统一为(target,value,cancelable)。

    `CreateCondition.params[4]` 是整条命令共用的可驱散标记。属性
    r>=99 与伤害类型 r>=1 是硬墙，即使调用者请求 true 也强制改为
    false；旧二元调用始终按 false 兼容。
    """
    if key not in {"damage_resistance", "element_resistance"}:
        raise ValueError(f"未知耐性通道:{key}")
    if not isinstance(atom, (list, tuple)) or len(atom) not in (2, 3):
        raise ValueError(f"{key} 耐性原子必须是二元/三元组:{atom!r}")
    raw_target, raw_value = atom[:2]
    if isinstance(raw_target, bool):
        raise ValueError(f"{key} 目标不能是 bool:{raw_target!r}")
    target, value = int(raw_target), float(raw_value)
    if key == "damage_resistance" and target not in DAMAGE_RESISTANCE_AC:
        raise ValueError(f"未知伤害类型 {target};只接受 0..3")
    if key == "element_resistance" and target not in ELEMENT_DATA_CN:
        raise ValueError(f"属性数据码 {target} 非法;只接受 1..6")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{key} 耐性强度必须是有限正数,收到 {value}")
    cancelable = False
    if len(atom) == 3:
        cancelable = atom[2]
        if not isinstance(cancelable, bool):
            raise ValueError(f"{key} cancelable 必须是 bool:{cancelable!r}")
    threshold = (ELEMENT_LOCK_THRESHOLD if key == "element_resistance" else 1.0)
    if value >= threshold - 1e-12:
        cancelable = False
    return target, value, cancelable


def _merged_resistance(picks: list[dict], key: str) -> list[tuple[int, float, bool]]:
    """跨诅咒按(target,cancelable)合并，保留命令级可驱散语义。

    属性轴与客户端一样累加 strength；伤害类型在同组内沿用取最强
    策略以防同组自行叠出负伤害。不同可驱散组必须分开落树；客户端最终
    依然会跨组累加，所以可解性由 `_resistance_totals_by_target` 再求和。
    """
    values: dict[tuple[int, bool], float] = {}
    order: list[tuple[int, bool]] = []
    for pick in picks:
        for raw in pick.get(key, []):
            target, value, cancelable = _normalize_resistance_atom(raw, key)
            group = (target, cancelable)
            if group not in values:
                order.append(group)
                values[group] = value
            elif key == "element_resistance":
                values[group] += value
            elif abs(value) > abs(values[group]):
                values[group] = value

    # 多张软卡在同 true 组合并后也可能跨过硬墙阈值。最终程序不允许
    # “高墙整体可驱散”，因此把该组迁入 false 后再合并。
    threshold = ELEMENT_LOCK_THRESHOLD if key == "element_resistance" else 1.0
    for group in list(order):
        target, cancelable = group
        if not cancelable or values[group] < threshold - 1e-12:
            continue
        hard_group = (target, False)
        value = values.pop(group)
        order.remove(group)
        if hard_group not in values:
            order.append(hard_group)
            values[hard_group] = value
        elif key == "element_resistance":
            values[hard_group] += value
        elif abs(value) > abs(values[hard_group]):
            values[hard_group] = value
    return [(target, values[(target, cancelable)], cancelable)
            for target, cancelable in order]


def _resistance_totals_by_target(picks: list[dict], key: str) -> dict[int, float]:
    """按客户端消费语义跨 cancelable false/true 两组求和。"""
    totals: dict[int, float] = {}
    for target, value, _cancelable in _merged_resistance(picks, key):
        totals[target] = totals.get(target, 0.0) + float(value)
    return totals


def immunity_axes(picks: list[dict]) -> tuple[set[str], set[int]]:
    """返回跨诅咒合并后的(完全免疫伤害类型,高阻断属性)。

    旧 c71 条目也纳入伤害轴,让迁移期/工坊旧计划同样过硬闸；新硬通道分别来自
    damage_resistance / element_resistance。伤害类型 r=1 走 ``*(1-r)``，确为免疫；
    元素 r>0 走 ``/(1+r)``，只把 r>=99（伤害至多 1%）视作封锁一条普通属性路。

    FixedAttackCalculator / RatioAttackCalculator 的 elementResistanceRate 与
    specificDamageResistance 均固定为 0，能绕过两轴；这些集合服务于 NormalAttack
    常规输出路的设计门禁，不宣称战斗在机制上绝对无解。
    """
    damage_total = _resistance_totals_by_target(picks, "damage_resistance")
    for constructor, value in _stacked_resistance_totals(picks).items():
        kind = STACKED_DAMAGE_AC_KIND.get(constructor)
        if kind is not None:
            # 两种条件的 ID 不同，但 ConditionSlot 的四个 resistance getter 会把
            # 它们相加；必须跨“一次性/叠层”后再判是否封死该伤害类型。
            damage_total[kind] = damage_total.get(kind, 0.0) + float(value)
    damage = {str(kind) for kind, value in damage_total.items()
              if value >= 1.0 - 1e-12}
    for kind, value in merge_conds(picks):
        if kind not in {"0", "1", "2", "3"}:
            continue
        try:
            if float(value) >= 1.0 - 1e-12:
                damage.add(kind)
        except (TypeError, ValueError):
            pass
    elements = {int(element) for element, value in
                _resistance_totals_by_target(picks, "element_resistance").items()
                if 1 <= int(element) <= 6
                and float(value) >= ELEMENT_LOCK_THRESHOLD - 1e-12}
    return damage, elements


def _slv(value: int | float) -> list[dict]:
    return [{"min": value, "max": value}]


def resistance_label(value: float) -> str:
    """按元素公式 ``damage/(1+r)`` 生成不夸大的玩家文案。"""
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"属性耐性强度必须是有限正数,收到 {value}")
    denominator = 1.0 + value
    if math.isclose(denominator, 2.0, rel_tol=0.0, abs_tol=1e-12):
        return "伤害减半"
    nearest = round(denominator)
    if (denominator <= 10.0
            and math.isclose(denominator, nearest, rel_tol=0.0, abs_tol=1e-12)):
        return f"伤害降至1/{nearest}"
    percent = 100.0 / denominator
    return f"伤害降至{percent:.6g}%"


def element_strengths_for_depth(r: int, n: int) -> tuple[float, ...]:
    """混相禁域的逐属性强度池：20%/50%/80% 三个深度分界。"""
    if n <= 0 or not 1 <= r <= n:
        raise ValueError(f"轮次越界:r={r},n={n}")
    d = r / n
    count = 1 if d <= 0.2 else (2 if d <= 0.5 else (3 if d <= 0.8 else 4))
    return ELEMENT_RESISTANCE_STRENGTHS[:count]


def _card_resistance_atoms(rng, key: str, pairs) -> list[tuple[int, float, bool]]:
    """一张逻辑软卡只抽一次可驱散性，硬原子始终回落 false。"""
    base = [_normalize_resistance_atom((target, value, False), key)
            for target, value in pairs]
    threshold = ELEMENT_LOCK_THRESHOLD if key == "element_resistance" else 1.0
    has_soft = any(value < threshold - 1e-12 for _target, value, _ in base)
    soft_cancelable = bool(has_soft and rng.randrange(4) == 0)
    return [(target, value,
             soft_cancelable if value < threshold - 1e-12 else False)
            for target, value, _old in base]


def mixed_element_entry(rng, strengths, forced=None,
                        name: str = MIXED_ELEMENT_CURSE_NAME) -> dict:
    """生成每个属性独立强度的混相卡。

    forced 在任何 RNG 调用前完整校验，工坊钉选因此不消耗这张
    卡自身的属性数/属性/强度/可驱散抽签。作者钉选样例明确落成
    不可驱散；随机软卡才按 3:1 混入可驱散版。
    """
    try:
        allowed = tuple(float(value) for value in strengths)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"混相强度池非法:{strengths!r}") from exc
    if (not allowed or any(value not in ELEMENT_RESISTANCE_STRENGTHS
                           for value in allowed)
            or len(set(allowed)) != len(allowed)):
        raise ValueError(f"混相强度池必须是 1/9/99/999 的非空唯一子集:{allowed}")

    if forced is not None:
        if not isinstance(forced, list) or not 1 <= len(forced) <= 5:
            raise ValueError("工坊 element_mix 必须是 1~5 项列表")
        parsed: list[tuple[int, float, bool]] = []
        seen: set[int] = set()
        for item in forced:
            if not isinstance(item, dict) or set(item) != {"element", "strength"}:
                raise ValueError(f"element_mix 每项必须只含 element/strength:{item!r}")
            element, strength = item["element"], item["strength"]
            if (isinstance(element, bool) or not isinstance(element, int)
                    or element not in ELEMENT_DATA_CN):
                raise ValueError(f"element_mix 属性必须是数据层 1..6:{element!r}")
            if (isinstance(strength, bool)
                    or not isinstance(strength, (int, float))
                    or float(strength) not in ELEMENT_RESISTANCE_STRENGTHS):
                raise ValueError(f"element_mix 强度只允许 1/9/99/999:{strength!r}")
            if element in seen:
                raise ValueError(f"element_mix 属性重复:{element}")
            seen.add(element)
            parsed.append((element, float(strength), False))
        atoms = sorted(parsed)
    else:
        count = rng.randrange(5) + 1
        elements = sorted(rng.sample(range(1, 7), count))
        raw = [(element, allowed[rng.randrange(len(allowed))])
               for element in elements]
        atoms = _card_resistance_atoms(rng, "element_resistance", raw)
    text = "·".join(ELEMENT_DATA_CN[element] + resistance_label(value)
                    for element, value, _cancelable in atoms)
    return {"name": str(name), "element_resistance": atoms, "text": text}


def build_immunity_dsl_tree(
        damage_resistance: list[tuple],
        element_resistance: list[tuple],
        stacked_resistance: list[tuple[str, float, int]] | None = None) -> list:
    """耐性 action DSL 树(CreateCondition → 自身 conditionSlot)。

    ⚠ 元素码必须写数据层 ToleranceOfElementTarget 的 1-based 编码:
      1火/2水/3雷/4风/5光/6暗；客户端内部虽 remap 为 0=全属性、1..6=六属性,
      这里绝不能写内部编码 0,也不接受 254=ALL / 255=OWNER。
    """
    damage = _merged_resistance(
        [{"damage_resistance": damage_resistance}], "damage_resistance")
    elements = _merged_resistance(
        [{"element_resistance": element_resistance}], "element_resistance")
    grouped: dict[bool, list] = {False: [], True: []}
    for kind, value, cancelable in damage:
        name = DAMAGE_RESISTANCE_AC[kind]
        if name not in wf_dsl_sig.ENUMS["AdditionalConditionKind"]:
            raise RuntimeError(f"DSL 签名表缺少构造 {name},拒绝静默下落")
        grouped[cancelable].append(
            [name, _slv(IMMUNITY_DURATION_FRAMES), _slv(value), _slv(1)])
    for element, value, cancelable in elements:
        name = "ACToleranceOfElement"
        if name not in wf_dsl_sig.ENUMS["AdditionalConditionKind"]:
            raise RuntimeError(f"DSL 签名表缺少构造 {name},拒绝静默下落")
        grouped[cancelable].append(
            [name, _slv(IMMUNITY_DURATION_FRAMES), element, _slv(value), _slv(1)])
    if "CreateCondition" not in wf_dsl_sig.COMMANDS:
        raise RuntimeError("DSL 签名表缺少 CreateCondition,拒绝静默下落")
    if "GenericConditionHitEffect" not in wf_dsl_sig.ENUMS["ConditionHitEffect"]:
        raise RuntimeError("DSL 签名表缺少 GenericConditionHitEffect")
    commands: list[list] = []
    # params[4] 是整条 CreateCondition 共用布尔；必须先 false 后 true
    # 分成至多两条命令，不能把原子级语义塞进不存在的参数位。
    for cancelable in (False, True):
        acs = grouped[cancelable]
        if not acs:
            continue
        commands.append(["Command", [
            "CreateCondition", -17, acs, _slv(1), ["GenericConditionHitEffect"],
            cancelable,
            False, "", None, False,
            3,                     # 目标种类必填 3
            _slv(1), False,
        ]])

    stacked = [(str(constructor), float(strength), int(layers))
               for constructor, strength, layers in (stacked_resistance or [])]
    # 同参数卡超过 maxAccumulation 时客户端会静默封顶；产出前必须拒绝。
    _stacked_resistance_totals([{"stacked_resistance": stacked}])
    for constructor, strength, layers in stacked:
        if constructor not in wf_dsl_sig.ENUMS["AdditionalConditionKind"]:
            raise ValueError(f"DSL 签名表缺少叠层构造 {constructor},拒绝静默下落")
        if constructor == "ACToleranceOfDebuff":
            ac = [constructor, _slv(STACKED_DURATION_FRAMES),
                  _slv(strength), _slv(STACKED_MAX_ACCUMULATION)]
        else:
            if constructor not in STACKED_DAMAGE_AC_KIND:
                raise ValueError(f"叠层抗性不支持构造 {constructor}")
            ac = [constructor, _slv(STACKED_DURATION_FRAMES),
                  _slv(strength), _slv(STACKED_MAX_ACCUMULATION)]
        # 终始之龙的层数不是写进 maxAccumulation，而是重复同 GID 条件：每次
        # outer magnification=1，同 ID 重放后逐层累计，99 只是上限。
        for _ in range(layers):
            commands.append(["Command", [
                "CreateCondition", -17, [copy.deepcopy(ac)], _slv(1), ["None"],
                False,             # 官方素材同样不可驱散
                True,              # 跳过同帧 hash 去重；否则重复命令只落第一层
                "", None, False,
                3, _slv(1), False,
            ]])
    if not commands:
        raise ValueError("空免疫 DSL 没有可执行词条")
    # general_boss c109/c111-160 引用的 3382 个可解析 enemy action 全部是 ActionDsl v1。
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False,
            False, 0, ["Block", commands]]


def build_immunity_dsl_blob(tree: list) -> bytes:
    """AMF3 + raw-deflate 往返自校验；构造名/参数树有任何漂移就拒绝产出。"""
    raw = wf_dsl.encode_amf3(tree)
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    blob = co.compress(raw) + co.flush()
    parsed = wf_dsl.parse_dsl(zlib.decompress(blob, -15))["tree"]
    if parsed != tree:
        raise RuntimeError("属性免疫 DSL build→parse 往返不等价")
    return blob


def immunity_program(
        damage_resistance: list[tuple],
        element_resistance: list[tuple],
        stacked_resistance: list[tuple[str, float, int]] | None = None) -> tuple[str, list]:
    """同一耐性参数签名复用同一 action 文件,避免每层重复锻造。"""
    damage = sorted(_merged_resistance(
        [{"damage_resistance": damage_resistance}], "damage_resistance"))
    elements = sorted(_merged_resistance(
        [{"element_resistance": element_resistance}], "element_resistance"))
    stacked = sorted((str(k), float(v), int(n))
                     for k, v, n in (stacked_resistance or []))
    tree = build_immunity_dsl_tree(damage, elements, stacked)
    signature = json.dumps([damage, elements, stacked],
                           ensure_ascii=True, separators=(",", ":"))
    tag = hashlib.sha1(signature.encode("ascii")).hexdigest()[:12]
    return f"battle/action/enemy/action/mod_rogue/immunity_{tag}", tree


def rewrite_boss_carrier_node(node, action_program: str | None = None,
                              pre_action_program: str | None = None,
                              action_programs=()):
    """克隆 general_boss 节点并追加普通 action / c109 pre_action。

    c109 不能覆盖官方已有 pre_action；c110=true 保证续战重跑。字段用 csv.reader/writer
    处理,包含逗号的程序数组仍保持一格。多个领域共用**同一个** boss 克隆和 action
    槽；按程序 ID 去重，避免双领域把同一程序重复执行。
    """
    programs = ([action_program] if action_program else []) + list(action_programs or ())
    programs = list(dict.fromkeys(str(p) for p in programs if str(p)))
    if not programs and not pre_action_program:
        raise ValueError("载体克隆至少需要一个 action 程序")

    def append(cell: str, program: str) -> str:
        existing = [] if cell in ("", "(None)") else cell.split(",")
        return ",".join(existing if program in existing else existing + [program])

    def rewrite(value):
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        row = cells(value)
        while len(row) < 162:
            row.append("")
        if pre_action_program:
            row[109] = append(row[109], pre_action_program)
            row[110] = "true"
        if programs:
            for i in range(111, 161):
                if row[i] not in ("", "(None)"):
                    for program in programs:
                        row[i] = append(row[i], program)
                    break
            else:
                row[111] = ",".join(programs)
        return join(row, isinstance(value, (bytes, bytearray)))

    return rewrite(node)


def curse_conflict(picks: list[dict]) -> str | None:
    """这组诅咒能不能同层?返回冲突原因;None = 可以。

    2026-07-29「三重壁垒」上线后实测:深层烈狱 20000 次采样里
      · 绝对壁垒 + 三重壁垒 同层 5.9%
      · **四系伤害全免疫 = 无解层 1.26%**(绝对壁垒免疫的那系,正好是三重壁垒放行的那系)
      · 条件槽被填满 30.3%(超出的被 `conds[:5]` **静默截断**,配的效果白配)
    全塔烈狱会把这两个概率放大,所以按硬规则拦在抽取环节。
    """
    # ① 同一 kind 同时有正值(抗性/免疫)和负值(易伤)= 自相矛盾。
    #    ⚠ 判据必须看**符号**,不能只看"是不是 1.0"——2026-07-29 第一版只拦
    #    「完全免疫 1.0 + 易伤」,漏掉了 0.3/0.4/0.5 三档抗性配易伤;全库两两普查:
    #      深渊壁垒+深渊逆鳞 **16/16 恒冲突**(壁垒盖全四系,逆鳞必然踩上)
    #      亡者不屈+深渊逆鳞 4/16、深渊逆鳞+绝对壁垒 4/16、深渊重甲+深渊逆鳞 4/16
    try:
        _stacked_resistance_totals(picks)
    except (TypeError, ValueError) as exc:
        return f"叠层抗性参数非法:{exc}"
    signs: dict[str, set] = {}
    for p in picks:
        for k, v in p.get("cond", []):
            if k == "4":
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            signs.setdefault(k, set()).add("+" if fv > 0 else "-")
        for atom in p.get("damage_resistance", []):
            try:
                k, fv, _cancelable = _normalize_resistance_atom(
                    atom, "damage_resistance")
            except (TypeError, ValueError):
                continue
            signs.setdefault(str(k), set()).add("+" if fv > 0 else "-")
        for constructor, strength, _layers in p.get("stacked_resistance", []):
            kind = STACKED_DAMAGE_AC_KIND.get(str(constructor))
            if kind is not None:
                signs.setdefault(str(kind), set()).add(
                    "+" if float(strength) > 0 else "-")
    bad = sorted(k for k, s in signs.items() if len(s) > 1)
    if bad:
        return f"kind {bad} 同时有抗性/免疫和易伤(自相矛盾)"
    # ② 槽位与无解层判定都按**合并后**的条件算(同 kind 同号会被 merge_conds 收成一条)
    merged = merge_conds(picks)
    if len(merged) > 5:
        return "条件槽超 5(超出的会被静默截断)"
    damage_immune, element_immune = immunity_axes(picks)
    if damage_immune >= {"0", "1", "2", "3"}:
        return "四种伤害类型全免疫(无解层)"
    affected_elements = {
        int(element) for element, value in
        _resistance_totals_by_target(picks, "element_resistance").items()
        if float(value) > 0
    }
    if affected_elements >= {1, 2, 3, 4, 5, 6}:
        # FixedAttackCalculator / RatioAttackCalculator 不吃属性耐性，因此这是
        # NormalAttack 普通属性伤害必须留一条完全不受影响路径的产品闸，
        # 不宣称机制上绝对无解。
        return ("六属性均受正抗性影响，未留至少一个完全不受影响"
                "的普通属性伤害出口（定值/比例伤害仍可绕过）")
    if element_immune >= {1, 2, 3, 4, 5, 6}:
        return (f"六属性均达高阻断阈值(r≥{fmt(ELEMENT_LOCK_THRESHOLD)};"
                "普通属性伤害出口封死，定值/比例伤害仍可绕过)")
    return None


def curse_runtime_conflict(picks: list[dict], *, baseline_c86: float,
                           c86_limits: tuple[float, float],
                           baseline_dps: float,
                           base_duration_s: float,
                           hp_channel: str = "c86") -> str | None:
    """组合落表前的数值硬闸；违规组合必须拒绝并重抽，不能截断。

    standard/no-boss 的血量乘数走 c86；general 的血量诅咒折进 clone
    boss_level.c2，c86 恒为 1。短时限始终按最终实战 DPS 跨诅咒合并后判。
    """
    base_c86 = float(baseline_c86)
    base_dps = float(baseline_dps)
    base_time = float(base_duration_s)
    lo, hi = map(float, c86_limits)
    if not all(math.isfinite(v) and v > 0
               for v in (base_c86, base_dps, base_time, lo, hi)) or hi < lo:
        raise ValueError(
            f"诅咒数值门禁输入非法:c86={baseline_c86},limits={c86_limits},"
            f"dps={baseline_dps},time={base_duration_s}")
    hp_mult = math.prod(float(c.get("hp", 1.0)) for c in picks)
    if hp_channel not in {"c86", "boss_level"}:
        raise ValueError(f"未知 HP 通道:{hp_channel}")
    final_c86 = (base_c86 if hp_channel == "boss_level"
                 else float(fmt(base_c86 * hp_mult)))
    if not lo <= final_c86 <= hi:
        return (f"最终 c86={final_c86:g} 超出本层窗口 {lo:g}~{hi:g}"
                f"(基线 {base_c86:g}×诅咒血量 {hp_mult:g})")
    frames = [float(c["time"]) for c in picks if c.get("time") is not None]
    duration = min(frames) / 60.0 if frames else base_time
    realized_dps = base_dps * hp_mult * base_time / duration
    if duration < 300.0 and realized_dps > 20_000_000.0:
        return (f"短时限高血量无解:{duration:.0f}s/"
                f"{realized_dps:.0f} DPS>20000000")
    return None


def high_threat_curse_conflict(picks: list[dict]) -> str | None:
    """高威胁 boss 的统一降难门禁；独立于是否有 HP 基线参数。"""
    if any(c.get("time") is not None for c in picks):
        return "高威胁 boss 禁止时限诅咒"
    high_elements = [(element, value) for element, value in
                     _resistance_totals_by_target(
                         picks, "element_resistance").items()
                     if float(value) >= ELEMENT_LOCK_THRESHOLD - 1e-12]
    if high_elements:
        return ("高威胁 boss 禁止高档属性墙(r≥"
                f"{fmt(ELEMENT_LOCK_THRESHOLD)}):{high_elements}")
    hp_mult = math.prod(float(c.get("hp", 1.0)) for c in picks)
    if not math.isfinite(hp_mult) or hp_mult > 1.5 + 1e-12:
        return f"高威胁 boss 诅咒血量×{hp_mult:g} 超过基准 1.5 倍"
    return None


def merge_conds(picks: list[dict]) -> list[tuple[str, str]]:
    """多个诅咒的条件槽合并:同 kind 的**同号**值取绝对值最大的一条。

    同 kind 重复会白占 5 个槽里的名额(弱的被强的盖住,语义上没意义),合并后
    能多塞一个诅咒。全库普查里这种"冗余重复"有 6 对,例如
    深渊壁垒(四系0.3) + 亡者不屈(能力0.5) → 能力只留 0.5。
    kind4(减益免疫)没有强度,去重保留一条即可。
    ⚠ 同 kind **异号**不在这里合并 —— 那是硬冲突,由 curse_conflict 拒掉,
      不能悄悄合成一个值糊弄过去。
    """
    best: dict[str, float] = {}
    order: list[str] = []
    has_debuff = False
    for p in picks:
        for k, v in p.get("cond", []):
            if k == "4":
                has_debuff = True
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if k not in best:
                order.append(k)
                best[k] = fv
            elif abs(fv) > abs(best[k]):
                best[k] = fv
    out: list[tuple[str, str]] = [("4", "")] if has_debuff else []
    out += [(k, fmt(best[k])) for k in order]
    return out


# ---- 诅咒组合(2026-07-29 用户需求「设计组合一下随机效果」)----
# 纯独立随机在 3 诅咒档位下经常出"三个不相干的数值"——有强度没主题。
# 组合 = 手工搭的成套方案,每套有明确玩法身份;抽中组合时整套落地,
# 剩余名额再用独立随机补。`field_cat` 指定该组合里「深渊法阵」从哪一类场效果抽。
CURSE_COMBOS = (
    {"name": "单通道", "curses": ("三重壁垒", "深渊逆鳞"),
     "note": "只剩一系能打,而那一系还易伤——逼构筑但留了出口"},
    {"name": "铁壁", "curses": ("深渊壁垒", "血肉高墙", "深渊重甲"),
     "note": "全系抗性+血厚+韧性,纯耐久战"},
    {"name": "速攻", "curses": ("玻璃深渊", "时之枷锁"),
     "note": "敌攻爆表血减半+限时,抢杀或被杀"},
    {"name": "枯竭", "curses": ("魔力枯竭", "亡者不屈", "深渊法阵"), "field_cat": "诅咒",
     "note": "攒不了 FEVER、上不了减益、场地还在削你"},
    {"name": "绞肉机", "curses": ("血肉高墙", "嗜血狂潮", "深渊重甲"),
     "note": "血厚攻高韧性高,长期拉锯"},
    {"name": "孤注", "curses": ("绝对壁垒", "深渊法阵"), "field_cat": "加成",
     "note": "一系完全免疫,但场地反过来给你增益"},
    {"name": "风暴", "curses": ("深渊法阵", "深渊逆鳞"), "field_cat": "环境",
     "note": "刮风/重力搅局,配一系易伤当补偿"},
    {"name": "凋零", "curses": ("时之枷锁", "深渊法阵", "血肉高墙"), "field_cat": "诅咒",
     "note": "限时+血厚+场地持续削,DPS 检定"},
)
COMBO_RATE = 0.55        # 名额 ≥2 时走组合的概率,其余走独立随机

# ---- 攻击类诅咒分档表(2026-07-30 降档)----
# 旧值 (1.4,1.7,2.0)/(1.5,1.8,2.2)/(2.2,2.6,3.0),烈狱档顶格叠在塔尾自身已达
# 2.4-3.3 的基础曲线上 → col>4 的层全是这三个。新烈狱端点 1.7/1.8/2.6
# (2026-07-30 用户指定),低档按同比例下调保持单调阶梯——阶梯本身也是**降档闸**
# 的台阶(超标层 tier 2→1→0→摘除,逐级重算,desc 跟着改,落表值与文案永不脱节)。
ATK_CURSE_TIERS = {
    "嗜血狂潮": (1.05, 1.10, 1.15),
    "深渊逆鳞": (1.10, 1.20, 1.30),
    "玻璃深渊": (1.20, 1.30, 1.40),
}


def atk_curse_entry(name: str, t: int, weak: int = 0) -> dict:
    """攻击类诅咒在档位 t 的完整条目。降档闸复用同一入口 → 数值与 text 恒一致。"""
    mult = ATK_CURSE_TIERS[name][t]
    if name == "嗜血狂潮":
        return {"name": name, "atk": mult, "hp": 0.85, "atk_tier": t,
                "text": f"敌攻×{mult}·血-15%"}
    if name == "玻璃深渊":
        return {"name": name, "atk": mult, "hp": 0.5, "atk_tier": t,
                "text": f"敌攻×{mult}·血-50%"}
    w = (0.3, 0.4, 0.5)[t]                       # 深渊逆鳞:易伤系绑三重壁垒放行系
    return {"name": name, "atk": mult, "atk_tier": t, "weak": weak,
            "cond": [(str(weak), fmt(-w))],
            "text": f"敌攻×{mult}·{COND_KIND_CN[weak]}易伤{int(w * 100)}%"}


def _curse_pool(t: int, rng, *, stack_layers: int = 50,
                mixed_strengths=ELEMENT_RESISTANCE_STRENGTHS,
                forced_element_mix=None) -> list[dict]:
    """t = 档位索引 0/1/2。硬通道耐性键单列,不再占 quest c71-80。"""
    wall = rng.randrange(4)   # 绝对壁垒的免疫系随机
    wall_open = rng.randrange(4)                             # 三重壁垒放行的那一系
    wall3 = [k for k in range(4) if k != wall_open]           # 其余三系全免
    # 属性诅咒族:1/3/1/5 属性四档；最强一档仍明确留下 1 个属性出口。
    # 文案统一从 damage/(1+r) 反推，绝不能再把 r=1 写成“完全免疫”。
    # 每条独立抽样,跨条目叠加后的出口由 curse_conflict 再做全组合硬闸。
    element_sets = {name: sorted(rng.sample(range(1, 7), count))
                    for name, (count, _strength) in ELEMENT_CURSE_SPECS.items()}
    _stacked_constructors = tuple(DAMAGE_RESISTANCE_AC.values())
    stacked_damage_constructor = _stacked_constructors[
        rng.randrange(len(_stacked_constructors))]
    stacked_damage = stacked_resistance_entry(
        "层叠龙鳞", stacked_damage_constructor,
        STACKED_DAMAGE_STRENGTH, stack_layers)
    stacked_debuff = stacked_resistance_entry(
        "不屈龙心", "ACToleranceOfDebuff",
        STACKED_DEBUFF_STRENGTH, stack_layers)
    mixed_element = mixed_element_entry(
        rng, mixed_strengths, forced=forced_element_mix)

    def element_entry(name: str) -> dict:
        blocked = element_sets[name]
        _count, strength = ELEMENT_CURSE_SPECS[name]
        open_elements = [e for e in range(1, 7) if e not in blocked]
        text = ("·".join(ELEMENT_DATA_CN[e] for e in blocked)
                + "属性" + resistance_label(strength))
        if len(open_elements) <= 3:
            text += "(只留" + "·".join(ELEMENT_DATA_CN[e] for e in open_elements) + ")"
        return {"name": name,
                "element_resistance": _card_resistance_atoms(
                    rng, "element_resistance", [(e, strength) for e in blocked]),
                "text": text}
    # ⚠ 逆鳞的易伤系**绑定到三重壁垒放行的那一系**,不再独立随机:
    # 【单通道】= 三重壁垒 + 深渊逆鳞,承诺"只剩一系能打、而那一系还易伤"。
    # 独立随机时易伤经常落在已经免疫的系上(实测 1.4.241 第15战:三系免疫 + 能力易伤,
    # 而能力正是被免疫的那个)——组合的承诺落空,同一 kind 还同时挂免疫和易伤。
    # 绑定后单通道恒自洽;逆鳞单独出现时 wall_open 本身就是随机的,不影响随机性。
    weak = wall_open
    # 随机法阵只从"已验证安全"的分类里抽;「环境」类要工坊钉选(见 FIELD_RANDOM_CATS)
    _menu = [m for m in field_menu_all() if (m[3] if len(m) > 3 else "领域") in FIELD_RANDOM_CATS]
    _menu = _menu or field_menu_all()
    fm = pick_field_program(_menu, rng)     # 分类间 √ 加权,分类内均匀
    return [
        {"name": "深渊重甲", "tp": (3, 6, 9)[t], "cond": [("2", fmt((0.2, 0.3, 0.4)[t]))],
         "text": f"韧性×{(3, 6, 9)[t]}·弹耐{int((0.2, 0.3, 0.4)[t] * 100)}%"},
        {"name": "魔力枯竭", "fever": (600, 800, 1200)[t],
         "text": f"FEVER需求×{(1.5, 2, 3)[t]}"},
        {"name": "时之枷锁", "time": (21600, 14400, 10800)[t],
         "text": f"限时{(6, 4, 3)[t]}分"},
        atk_curse_entry("嗜血狂潮", t),
        {"name": "深渊壁垒",
         "damage_resistance": _card_resistance_atoms(
             rng, "damage_resistance",
             [(k, (0.2, 0.25, 0.3)[t]) for k in range(4)]),
         "text": f"全系耐性{int((0.2, 0.25, 0.3)[t] * 100)}%"},
        {"name": "亡者不屈", "cond": [("4", ""), ("0", fmt((0.3, 0.4, 0.5)[t]))],
         "text": f"减益免疫·能耐{int((0.3, 0.4, 0.5)[t] * 100)}%"},
        {"name": "血肉高墙", "hp": (1.6, 2.0, 2.5)[t],
         "text": f"敌血×{(1.6, 2.0, 2.5)[t]}"},
        atk_curse_entry("深渊逆鳞", t, weak),
        # 绝对壁垒:随机一系伤害极高耐性,炼狱=完全免疫(强度1.0=伤害×0),逼构筑切换
        {"name": "绝对壁垒", "damage_resistance": _card_resistance_atoms(
             rng, "damage_resistance", [(wall, (0.7, 0.85, 1.0)[t])]),
         "text": f"{COND_KIND_CN[wall]}{'完全免疫' if t == 2 else '耐性' + str(int((0.7, 0.85, 1.0)[t] * 100)) + '%'}"},
        # 三重壁垒(2026-07-29 用户需求「免疫可以不止一种,比如三种」):
        # 四系里随机去掉一系,剩下三系同时高耐性/炼狱档完全免疫 —— 只留一条输出路,
        # 逼队伍必须带对那一系。条件槽有 5 个,三条 cond 塞得下。
        {"name": "三重壁垒",
         "damage_resistance": _card_resistance_atoms(
             rng, "damage_resistance", [(k, (0.5, 0.7, 1.0)[t]) for k in wall3]),
         "text": ("·".join(COND_KIND_CN[k] for k in wall3)
                   + ('三重免疫' if t == 2 else f"三重耐性{int((0.5, 0.7, 1.0)[t] * 100)}%")
                   + f"(只剩{COND_KIND_CN[wall_open]}能打)")},
        element_entry("元素滞钝"),
        element_entry("三相封界"),
        element_entry("元素禁壁"),
        element_entry("五相绝域"),
        mixed_element,
        stacked_damage,
        stacked_debuff,
        # 玻璃深渊:攻击爆表但血量减半,速杀或被杀
        atk_curse_entry("玻璃深渊", t),
        # 深渊法阵:克隆 boss 追加官方场程序(领域/淹水/结界,详见 FIELD_MENU)。
        # 2026-07-20 真机验证通过(白虎战「连击加成领域效果发动」)。
        # ⚠「乱流机关」已除名:c36/37 只是预载清单不控板子渲染皮肤(真机 falsified),
        # 无板子地形又缺锚点——两个卖点全死,勿复活。
        {"name": "深渊法阵", "caster": fm, "text": f"{fm[0]}·{fm[2]}"},
    ]


def apply_picks(out: dict, picks: list[dict], combo: str | None = None) -> dict:
    """把一组诅咒条目合成效果包。**降档闸改了 picks 之后重算走同一条路**,
    保证 hp/atk/conds/desc 永远与 picks 一致(不会出现"文案写×2.6、落表 1.4")。"""
    out.update({"conds": [], "damage_resistance": [], "element_resistance": [],
                "stacked_resistance": [],
                "hp": 1.0, "atk": 1.0, "tp": None, "fever": None,
                "time": None, "gimmick": False, "caster": None, "casters": [],
                "picks": picks, "combo": combo})
    names = []
    caster_ids: set[str] = set()
    for c in picks:
        out["hp"] *= c.get("hp", 1.0)
        out["atk"] *= c.get("atk", 1.0)
        out["gimmick"] = out["gimmick"] or c.get("gimmick", False)
        caster = c.get("caster")
        if caster:
            program = str(caster[1])
            if program not in caster_ids:
                caster_ids.add(program)
                out["casters"].append(caster)
        if "tp" in c:
            out["tp"] = max(out["tp"] or 0, c["tp"])
        if "fever" in c:
            out["fever"] = max(out["fever"] or 0, c["fever"])
        if "time" in c:
            out["time"] = min(out["time"] or 10 ** 9, c["time"])
        names.append(f"「{c['name']}」{c['text']}")
    out["conds"] = merge_conds(picks)[:5]
    out["damage_resistance"] = _merged_resistance(picks, "damage_resistance")
    out["element_resistance"] = _merged_resistance(picks, "element_resistance")
    out["stacked_resistance"] = _merged_stacked_resistance(picks)
    out["caster"] = out["casters"][0] if out["casters"] else None  # 旧调用方兼容视图
    out["desc"] = (f"【{combo}】" if combo else "") + " ".join(names)
    return out


def downgrade_atk_curse(curse: dict) -> str | None:
    """把该层的攻击类诅咒降一档；最低档只摘攻击组件,HP 组件原样保留。

    分位硬闸的**唯一收敛手段**:每调用一次 atk 严格下降,最多 4 步(2→1→0→摘)
    就回到无攻击诅咒的裸曲线,故循环必然终止。"""
    picks = list(curse.get("picks") or [])
    i = next((i for i, c in enumerate(picks)
              if c.get("name") in ATK_CURSE_TIERS and "atk_tier" in c), None)
    if i is None:
        return None
    c = picks[i]
    t = int(c.get("atk_tier", 0))
    if t > 0:
        picks[i] = atk_curse_entry(c["name"], t - 1, int(c.get("weak", 0)))
        note = f"「{c['name']}」×{c['atk']}→×{picks[i]['atk']}"
        combo = curse.get("combo")
    else:
        hp_mult = float(c.get("hp", 1.0))
        if abs(hp_mult - 1.0) > 1e-12:
            # 攻击与血量是同一条诅咒的两个组件。分位闸只获准摘攻击；留下显式、
            # 可重算的 HP 残响条目,避免 apply_picks 把 0.5/0.85 重置成 1.0。
            pct = int(round(abs(1.0 - hp_mult) * 100))
            direction = "-" if hp_mult < 1.0 else "+"
            picks[i] = {"name": f"{c['name']}·残响", "hp": hp_mult,
                        "text": f"敌血{direction}{pct}%（攻击增幅已摘）"}
        else:
            picks.pop(i)
        note = f"摘除「{c['name']}」攻击组件"
        # 组合的承诺(【速攻】=敌攻爆表+限时)已经不成立,标签一并摘掉,别骗玩家
        combo = None
    hp_before = float(curse.get("hp", 1.0))
    apply_picks(curse, picks, combo)
    if not math.isclose(float(curse["hp"]), hp_before, rel_tol=0.0, abs_tol=1e-12):
        raise AssertionError(f"降档误改血量乘数:{hp_before}→{curse['hp']}")
    if t == 0:
        # dry-run 的分位闸日志直接留下同 seed 的前后不变量证据，不只靠测试内断言。
        note += f"（血量×{fmt(hp_before)}保持）"
    return note


def is_deep_round(r: int, n: int) -> bool:
    """最后 20%（30 层塔即第 25~30 战）。"""
    if n <= 0 or not 1 <= r <= n:
        raise ValueError(f"轮次越界:r={r},n={n}")
    return r / n > 0.8


def element_curse_names_for_depth(r: int, n: int,
                                  tier: str = "hell") -> set[str]:
    """属性耐性族随机候选：浅层低阻、深层高阻；显式钉选不走这道软筛选。

    30 层 hell 对应 1~6 滞钝、7~15 滞钝/三相、16~24 三相/禁壁、
    25~30 禁壁/五相。standard 最高滞钝，abyss 最高三相。
    """
    if n <= 0 or not 1 <= r <= n:
        raise ValueError(f"轮次越界:r={r},n={n}")
    d = r / n
    stage = 0 if d <= 0.2 else (1 if d <= 0.5 else (2 if d <= 0.8 else 3))
    cap = {"standard": 0, "abyss": 1, "hell": 3}.get(tier, 0)
    stage = min(stage, cap)
    return (
        {"元素滞钝"},
        {"元素滞钝", "三相封界"},
        {"三相封界", "元素禁壁"},
        {"元素禁壁", "五相绝域"},
    )[stage] | {MIXED_ELEMENT_CURSE_NAME}


def hell_curse_slots(r: int, n: int) -> int:
    """烈狱诅咒名额：≤20% 1、≤50% 2、其余 3，最后 20% 4。"""
    if is_deep_round(r, n):
        return 4
    d = r / n
    return 1 if d <= 0.2 else (2 if d <= 0.5 else 3)


def required_field_slots(r: int, n: int) -> int:
    """领域保底：过半程 1 个，最后 20% 2 个。无载体时由调用方显式记欠配。"""
    if is_deep_round(r, n):
        return 2
    return 1 if r / n > 0.5 else 0


def _has_dragon_heart(picks: list[dict]) -> bool:
    return any(str(constructor) == "ACToleranceOfDebuff"
               for pick in picks
               for constructor, _strength, _layers in
               pick.get("stacked_resistance", []))


def _safe_non_boon_fields(picks: list[dict], menu) -> list[tuple]:
    used = {str(pick["caster"][1]) for pick in picks if pick.get("caster")}
    unique: dict[str, tuple] = {}
    for item in menu:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        category = item[3] if len(item) > 3 else "领域"
        program = str(item[1])
        if (category == "加成" or category not in FIELD_RANDOM_CATS
                or program in used):
            continue
        unique.setdefault(program, tuple(item))
    return list(unique.values())


def dragon_heart_companion_block(picks: list[dict], can_carry: bool,
                                 menu) -> str | None:
    """不屈龙心在 finalize 前的可实现性预检，供 redraw 路径记录原因。"""
    if not _has_dragon_heart(picks):
        return None
    if not can_carry:
        return "不屈龙心缺少 general_boss c109 载体"
    fields = [pick for pick in picks if pick.get("caster")]
    if any((pick["caster"][3] if len(pick["caster"]) > 3 else "领域") != "加成"
           for pick in fields):
        return None
    if not _safe_non_boon_fields(picks, menu):
        return "不屈龙心非加成可见领域候选耗尽"
    return None


def ensure_dragon_heart_companion(picks: list[dict], rng, can_carry: bool,
                                  menu) -> list[dict]:
    """为不屈龙心保底一个对普通队伍可见的非“加成”场机制。

    已有非加成 field 时复用；只有加成 field 时原位替换一个；无 field
    时追加恰好一个，不占普通诅咒名额。可行性问题必须在正常抽取时
    由 `dragon_heart_companion_block` 转成 log+redraw；直接调用则响亮失败。
    """
    picks = list(picks)
    why = dragon_heart_companion_block(picks, can_carry, menu)
    if why:
        raise RuntimeError(why)
    if not _has_dragon_heart(picks):
        return picks
    fields = [(i, pick) for i, pick in enumerate(picks) if pick.get("caster")]
    if any((pick["caster"][3] if len(pick["caster"]) > 3 else "领域") != "加成"
           for _i, pick in fields):
        return picks
    candidates = _safe_non_boon_fields(picks, menu)
    chosen = candidates[rng.randrange(len(candidates))]
    companion = {"name": "深渊法阵", "caster": chosen,
                 "text": f"{chosen[0]}·{chosen[2]}"}
    if fields:
        picks[fields[0][0]] = companion
    else:
        picks.append(companion)
    return picks


def abyss_curses(r: int, n: int, rng, tier: str, caps: dict | None = None,
                 forced: dict | None = None, no_base: bool = False, *,
                 baseline_c86: float | None = None,
                  c86_limits: tuple[float, float] | None = None,
                  baseline_dps: float | None = None,
                  base_duration_s: float | None = None,
                  hp_channel: str = "c86",
                  high_threat: bool = False) -> dict:
    """轮次诅咒包:{conds,hp,atk,tp,fever,time,gimmick,caster,desc,picks,combo}。

    caps = 地形能力 {"spawn": 有SPAWNn锚点, "panel": 官方板子配对地形}——
    祭坛/板子诅咒只在能生效的地形掉落(2026-07-20 真机实证:歼灭者类 boss 擂台
    只有 FUNNEL_SPAWN 锚点,zone-zako 出生静默失败)。
    no_base = 该层 boss 查不到基数(standard 表)→ 归一化不生效、真实伤害无上界
    保证,**禁掉攻击类诅咒**(2026-07-30 伤害审计:第15/18/26/29/30 战都是这种)。
    """
    out = {"conds": [], "damage_resistance": [], "element_resistance": [],
           "stacked_resistance": [],
           "hp": 1.0, "atk": 1.0, "tp": None, "fever": None,
           "time": None, "gimmick": False, "caster": None, "casters": [], "desc": "",
           "field_requested": 0, "field_applied": 0, "field_deficit": 0,
           "field_deficit_reason": None,
           "picks": [], "combo": None}
    has_forced = bool(forced and (forced.get("curses") or forced.get("field")))
    forced_names = list((forced or {}).get("curses") or [])
    has_element_mix = bool(forced is not None and "element_mix" in forced
                           and forced.get("element_mix") is not None)
    if has_element_mix and MIXED_ELEMENT_CURSE_NAME not in forced_names:
        raise ValueError("element_mix 只能与工坊钉选「混相禁域」同时提供")
    if tier == "off" and not has_forced:
        return out
    t = CURSE_TIERS.index(tier) if tier in CURSE_TIERS else 1
    d = r / n
    # 诅咒名额。**全塔烈狱**(2026-07-29 用户主推)时没有白板层:最浅也给 1 个,
    # 30% 起 2 个,60% 起 3 个(3 是条件槽能装下的上限,见 curse_conflict)。
    # 其余档位维持原节奏:≤15% 白板 / ≤45% 1 个 / 其余 2 个。
    if tier == "hell":
        count = hell_curse_slots(r, n)
    else:
        if d <= 0.15 and not has_forced:
            return out
        count = 1 if d <= 0.45 else 2
    caps = caps or {}
    field_requested = required_field_slots(r, n) if tier == "hell" else 0
    raw_pool = _curse_pool(
        t, rng, stack_layers=stacked_resistance_layers_for_depth(r, n),
        mixed_strengths=element_strengths_for_depth(r, n),
        forced_element_mix=((forced or {}).get("element_mix")
                            if has_element_mix else None))
    safe_pool = list(raw_pool)
    if is_deep_round(r, n):
        # 深层血量锚已到多人决战量级；180/240 秒会把需求 DPS 再抬 3.75~5×。
        # 随机、组合、工坊强制三条路共用同一份过滤，后面 finalize 还有最终断言。
        safe_pool = [c for c in safe_pool if "time" not in c]
    if no_base:
        # 无基数层:归一化返回 1.0,裸曲线值 + 顶格攻击诅咒 = 第26战 6.58 的成因
        safe_pool = [c for c in safe_pool if c["name"] not in ATK_CURSE_TIERS]
    if not caps.get("element"):
        if "c36" in str(caps.get("element_reason") or ""):
            log(f"[curse] round={r} reject=属性免疫族 reason={caps['element_reason']}; redraw")
        safe_pool = [c for c in safe_pool if c["name"] not in ELEMENT_CURSE_NAMES]
    if not caps.get("boss"):
        safe_pool = [c for c in safe_pool if c["name"] not in PRE_ACTION_CURSE_NAMES]
    if high_threat:
        # 时限/高档属性墙是单条即可判定的硬禁项；HP 上限必须等组合后按净乘数判，
        # 不能在这里错杀 2.5×0.5=1.25 这类合法搭配。
        safe_pool = [c for c in safe_pool
                     if c.get("time") is None
                     and not any(float(value) >= ELEMENT_LOCK_THRESHOLD - 1e-12
                                 for value in _resistance_totals_by_target(
                                     [c], "element_resistance").values())]
    # 深度只是随机排程软约束。工坊钉选从 safe_pool 查名，仍必须通过载体/c36/
    # 可解性硬闸；随机、组合与 redraw 补位只从按层过滤后的 pool 取。
    allowed_elements = element_curse_names_for_depth(r, n, tier)
    pool = [c for c in safe_pool
            if c["name"] not in ELEMENT_CURSE_NAMES or c["name"] in allowed_elements]
    if not is_deep_round(r, n):
        # 一次性高 r 是硬墙；随机排程只在最后20%与可见叠层混用。
        # 工坊钉选仍从 safe_pool 取，保留显式越档能力（高威胁硬闸除外）。
        pool = [c for c in pool if c["name"] not in HIGH_ONE_SHOT_CURSE_NAMES]
    runtime_args = (baseline_c86, c86_limits, baseline_dps, base_duration_s)
    if any(v is not None for v in runtime_args) and not all(v is not None for v in runtime_args):
        raise ValueError(f"第{r}战诅咒数值门禁参数必须成套提供")

    def conflict(picks: list[dict]) -> str | None:
        why = curse_conflict(picks)
        if not why and high_threat:
            why = high_threat_curse_conflict(picks)
        if not why:
            why = dragon_heart_companion_block(
                picks, bool(caps.get("boss")), field_menu_all())
        if why or baseline_c86 is None:
            return why
        return curse_runtime_conflict(
            picks, baseline_c86=float(baseline_c86),
            c86_limits=c86_limits, baseline_dps=float(baseline_dps),
            base_duration_s=float(base_duration_s), hp_channel=hp_channel)

    def pick_key(c: dict):
        caster = c.get("caster")
        return ("field", str(caster[1])) if caster else ("curse", c.get("name"))

    def new_field_entries(current: list[dict], needed: int) -> list[dict]:
        """从完整安全菜单抽互异程序；领域是重复类别，但同一 program 不可重复。"""
        used = {str(c["caster"][1]) for c in current if c.get("caster")}
        menu = [m for m in field_menu_all()
                if (m[3] if len(m) > 3 else "领域") in FIELD_RANDOM_CATS
                and str(m[1]) not in used]
        unique = {}
        for item in menu:
            unique.setdefault(str(item[1]), item)
        order = rng.sample(list(unique.values()), len(unique)) if unique else []
        return [{"name": "深渊法阵", "caster": fm, "text": f"{fm[0]}·{fm[2]}"}
                for fm in order[:needed]]

    def refill_picks(current: list[dict], target_count: int,
                      prefer_caster: bool = False) -> list[dict]:
        """用完整冲突闸补满名额；耗尽时硬失败，绝不把 redraw 退化成少发。"""
        current = list(current)
        atk_used = any(c.get("atk", 1.0) > 1.0 for c in current)
        if caps.get("boss") and field_requested:
            present = len({str(c["caster"][1]) for c in current if c.get("caster")})
            add = min(max(0, target_count - len(current)), max(0, field_requested - present))
            for c in new_field_entries(current, add):
                if conflict(current + [c]) is None:
                    current.append(c)
            present = len({str(c["caster"][1]) for c in current if c.get("caster")})
            if present < min(field_requested, target_count):
                raise RuntimeError(
                    f"第{r}战领域候选耗尽:{present}/{min(field_requested, target_count)}")
        order = rng.sample(pool, len(pool))
        # 深渊法阵(场程序)出场加权(2026-07-29 用户「场地效果可以再多一点」):
        # 平权时 1/12≈8%,这里 45% 概率把它提到队首 → 实际约四成楼层带场地效果。
        if prefer_caster and caps.get("boss") and rng.random() < 0.45:
            caster = next((c for c in order if c.get("caster")), None)
            if caster is not None:
                order.remove(caster)
                order.insert(0, caster)
        for c in order:
            if len(current) >= target_count:
                break
            if c.get("gimmick") and not caps.get("panel"):
                continue
            if c.get("caster") and not caps.get("boss"):
                continue
            # 中后段保底已经填到目标数后，不再随机塞第 3 个领域；前段仍保留旧的
            # 45% 随机法阵手感。去重按 program ID，不按统一显示名“深渊法阵”。
            if c.get("caster") and field_requested and sum(
                    bool(p.get("caster")) for p in current) >= field_requested:
                continue
            if any(pick_key(c) == pick_key(p) for p in current):
                continue
            is_atk = c.get("atk", 1.0) > 1.0
            if is_atk and atk_used:
                continue
            why = conflict(current + [c])
            if why:
                log(f"[curse] round={r} reject=「{c['name']}」"
                    f" with={','.join(p['name'] for p in current) or '(none)'}"
                    f" reason={why}; redraw")
                continue
            current.append(c)
            atk_used = atk_used or is_atk
        if len(current) < target_count:
            # “拒绝并重抽”不能退化成少发几条的静默截断；候选耗尽说明池/冲突规则坏了。
            raise RuntimeError(
                f"第{r}战诅咒重抽耗尽:{len(current)}/{target_count},拒绝落表")
        return current

    def finalize(picks: list[dict], combo_name: str | None = None) -> dict:
        picks = ensure_dragon_heart_companion(
            picks, rng, bool(caps.get("boss")), field_menu_all())
        why = conflict(picks)
        if why:
            raise RuntimeError(f"第{r}战诅咒最终组合未过门禁:{why}")
        result = apply_picks(out, picks, combo_name)
        applied = len(result.get("casters") or [])
        effective_field_requested = max(
            field_requested, 1 if _has_dragon_heart(picks) else 0)
        result["field_requested"] = effective_field_requested
        result["field_applied"] = applied
        result["field_deficit"] = max(0, effective_field_requested - applied)
        if result["field_deficit"]:
            result["field_deficit_reason"] = (caps.get("carrier_reason")
                                               or caps.get("element_reason")
                                               or "没有可用的 general_boss 领域载体")
        if is_deep_round(r, n) and (result.get("time") is not None
                                    or any("time" in c for c in picks)):
            raise AssertionError(f"第{r}战深层仍残留时限诅咒")
        if high_threat:
            why = high_threat_curse_conflict(picks)
            if why:
                raise AssertionError(f"第{r}战高威胁最终组合越闸:{why}")
        return result

    # 显式指定(工坊拖拽):有效钉选优先；被门禁拒绝的名额随机补齐到原指定数量。
    if forced and (forced.get("curses") or forced.get("field")):
        forced_curses = list(forced.get("curses") or [])
        # 深层的“第 4 个”是硬规格，不是工坊可绕过的下限。
        # 即使计划误填 5+ 个，也只保留前四个可解条目再重抽；
        # 领域另算 2 个硬通道，不占普通诅咒名额。
        curse_target = (count if is_deep_round(r, n)
                        else max(count, len(forced_curses)))
        if is_deep_round(r, n) and len(forced_curses) > curse_target:
            for nm in forced_curses[curse_target:]:
                log(f"[curse] round={r} reject=工坊额外「{nm}」 "
                    f"reason=深层普通诅咒固定 {curse_target} 个; redraw")
            forced_curses = forced_curses[:curse_target]
        field_target = (field_requested if caps.get("boss") else 0)
        if not field_target and forced.get("field") and caps.get("boss"):
            field_target = 1
        # 领域不占“第4个诅咒”的名额；深层是 4 个普通诅咒 + 2 个领域。
        target_count = curse_target + field_target
        picks = [c for nm in forced_curses
                 for c in safe_pool if c["name"] == nm and not c.get("caster")]
        for nm in forced_curses:
            if is_deep_round(r, n) and nm == "时之枷锁":
                log(f"[curse] round={r} reject=「{nm}」 reason=深层禁时限; redraw")
            if no_base and nm in ATK_CURSE_TIERS:
                print(f"[WARN] 工坊钉选第{r}战:剔除「{nm}」(该层 boss 无基数,"
                      "归一化不生效,攻击类诅咒会失控)")
            if nm in ELEMENT_CURSE_NAMES and not caps.get("element"):
                why = caps.get("element_reason") or "本层没有可用的 general_boss 硬通道载体"
                log(f"[curse] round={r} reject=「{nm}」 reason={why}; redraw")
            if nm in DAMAGE_HARD_CURSE_NAMES and not caps.get("boss"):
                log(f"[curse] round={r} reject=「{nm}」 reason=本层没有可用的"
                    " general_boss 硬通道载体; redraw")
            if nm in STACKED_CURSE_NAMES and not caps.get("boss"):
                log(f"[curse] round={r} reject=「{nm}」 reason=本层没有可用的"
                    " general_boss c109 叠层载体; redraw")
            if high_threat:
                original = next((c for c in raw_pool if c["name"] == nm), None)
                if original:
                    # HP 只能在完整组合上判；这里仅解释为何单条硬禁项没进 safe_pool。
                    threat_probe = dict(original)
                    threat_probe.pop("hp", None)
                    why = high_threat_curse_conflict([threat_probe])
                    if why:
                        log(f"[curse] round={r} reject=「{nm}」 reason={why}; redraw")
        if forced.get("field"):
            fm_forced = next((m for m in field_menu_all() if m[1] == forced["field"]), None)
            if fm_forced and caps.get("boss"):
                picks.append({"name": "深渊法阵", "caster": fm_forced,
                              "text": f"{fm_forced[0]}·{fm_forced[2]}"})
            else:
                log(f"[curse] round={r} reject=工坊法阵「{forced['field']}」"
                    " reason=本层没有可用的 general_boss 硬通道载体; redraw")
        # 钉选也要过冲突闸:手动钉出"四系全免疫"照样是无解层,发出去就卡死玩家
        if high_threat:
            # 净 HP 乘数与输入顺序无关，但逐条 kept 检查会看到中间态；先处理减血项，
            # 让 [高墙,玻璃] 与 [玻璃,高墙] 都按最终 1.25 倍作同一裁定。
            picks = [c for _i, c in sorted(
                enumerate(picks),
                key=lambda pair: (float(pair[1].get("hp", 1.0)) > 1.0, pair[0]))]
        kept: list[dict] = []
        for c in picks:
            why = conflict(kept + [c])
            if why:
                log(f"[curse] round={r} reject=「{c['name']}」 reason={why}; redraw")
                continue
            kept.append(c)
        if caps.get("boss") and field_requested:
            max_non_fields = curse_target
            non_fields = [c for c in kept if not c.get("caster")]
            if len(non_fields) > max_non_fields:
                rejected_ids = {id(c) for c in non_fields[max_non_fields:]}
                for c in kept:
                    if id(c) in rejected_ids:
                        log(f"[curse] round={r} reject=「{c['name']}」"
                            " reason=领域保底需预留名额; redraw")
                kept = [c for c in kept if id(c) not in rejected_ids]
        # 被 c36/载体/跨诅咒冲突拒掉的名额必须真正换成别的诅咒；补不满就拒绝落表。
        return finalize(refill_picks(kept, target_count))
    # 攻击类诅咒(嗜血/逆鳞/玻璃)每轮至多 1 个——双叠=一击秒杀墙,是恶心不是大胆
    picks = []
    combo_name = None
    # ---- 先试组合(2026-07-29):名额 ≥2 时 55% 概率整套落地,剩余名额再独立随机补 ----
    if count >= 2 and rng.random() < COMBO_RATE:
        cands = [cb_ for cb_ in CURSE_COMBOS if len(cb_["curses"]) <= count]
        if is_deep_round(r, n):
            cands = [cb_ for cb_ in cands if "时之枷锁" not in cb_["curses"]]
        # 需要 boss 载体的组合(带深渊法阵)在 standard/专用表 boss 层落不上,先剔掉
        if not caps.get("boss"):
            cands = [cb_ for cb_ in cands if "深渊法阵" not in cb_["curses"]]
        while cands:
            cb_ = cands.pop(rng.randrange(len(cands)))
            got = []
            for nm in cb_["curses"]:
                if nm == "深渊法阵":
                    sub = [m for m in field_menu_all()
                           if (m[3] if len(m) > 3 else "领域") == cb_.get("field_cat")]
                    sub = sub or [m for m in field_menu_all()
                                  if (m[3] if len(m) > 3 else "领域") in FIELD_RANDOM_CATS]
                    fm2 = sub[rng.randrange(len(sub))]
                    got.append({"name": "深渊法阵", "caster": fm2,
                                "text": f"{fm2[0]}·{fm2[2]}"})
                else:
                    c = next((x for x in pool if x["name"] == nm), None)
                    if c:
                        got.append(c)
            why = conflict(got) if len(got) == len(cb_["curses"]) else None
            if len(got) == len(cb_["curses"]) and not why:
                picks, combo_name = got, cb_["name"]
                break
            if why:
                log(f"[curse] round={r} reject=【{cb_['name']}】"
                    f"({','.join(c['name'] for c in got)}) reason={why}; redraw")
    total_count = count + (field_requested if caps.get("boss") else 0)
    return finalize(refill_picks(picks, total_count, prefer_caster=True), combo_name)


def _leaf_rows(node):
    """任意深度嵌套表 → 逐个 leaf CSV 行。"""
    if isinstance(node, dict):
        for v in node.values():
            yield from _leaf_rows(v)
    else:
        s = node.decode("utf-8") if isinstance(node, bytes) else node
        for ln in s.split("\n"):
            if ln.strip():
                yield ln


# 直引 field 的源表 → battle_recommended_element 列位(0-based 元素枚举)
# 2026-07-29 补全:以前只登记 5 张表,而 src 池里的 world_story/story_event 以及
# 本次新增的 6 类都没登记 → c69 落到"随机元素",正是 C8016 的触发路径。
# 列位测绘法:先找该表的 field 列号,元素列 = field 列 − 固定偏移,偏移只有两族
# (长行 37 / 短行 29,ranking 是唯一的 24);逐表用"全行取值必须落在 0-6"验证,
# 并抽样对过语义(闪火试炼=火、haniwa_carnival_water=水、寄居蟹船长=水)。
# ⚠ score_attack/practice 三个偏移都能过 0-6 校验但语义互相矛盾,没有确证前
#   不登记(它们也不在 src 池里);登记错列比不登记更危险。
_ELEM_COL = {
    "master/quest/boss_battle_quest.orderedmap": 72,
    "master/quest/main_quest.orderedmap": 72,
    "master/quest/event/hard_multi_event_quest.orderedmap": 73,
    "master/quest/event/advent_event_quest.orderedmap": 78,
    "master/quest/event/raid_event_quest.orderedmap": 70,
    "master/quest/event/world_story_event_quest.orderedmap": 73,
    "master/quest/event/world_story_event_boss_battle_quest.orderedmap": 72,
    "master/quest/event/story_event_single_quest.orderedmap": 74,
    "master/quest/event/expert_single_event_quest.orderedmap": 75,
    "master/quest/event/solo_time_attack_event_quest.orderedmap": 72,
    "master/quest/event/ranking_event_single_quest.orderedmap": 68,
    "master/quest/event/carnival_event_quest.orderedmap": 69,
}


def field_official_elem_map() -> dict[str, int]:
    """field_data id → 官方源 quest 的 battle_recommended_element。

    塔层/挑战层经 floor 表间接(宿主表元素列 70/73,floor 键列 99/110);
    直引 field 的表按 _ELEM_COL 扫行、按 field_data 键匹配单元格。
    """
    fd_keys = set(_tbl("master/battle/field_data.orderedmap").keys())
    out: dict[str, int] = {}

    floor = q.load_table("master/battle/floor.orderedmap")
    fkey_fields: dict[str, list[str]] = {}
    for k, v in floor.items():
        if isinstance(v, dict):
            continue
        s = v.decode("utf-8") if isinstance(v, bytes) else v
        fkey_fields[k] = [cb._cols(ln)[0] for ln in s.split("\n")
                          if cb._cols(ln) and cb._cols(ln)[0] not in ("", "(None)")]
    for logical, elem_col, floor_col in [
        ("master/quest/event/tower_dungeon_event_quest.orderedmap", 70, 99),
        ("master/quest/event/challenge_dungeon_event_quest.orderedmap", 73, 110),
    ]:
        try:
            table = q.load_table(logical)
        except Exception:
            continue
        for ln in _leaf_rows(table):
            row = cb._cols(ln)
            if len(row) <= max(elem_col, floor_col):
                continue
            fkey, ev = row[floor_col], row[elem_col]
            if fkey in ("", "(None)") or ev not in ("0", "1", "2", "3", "4", "5", "6"):
                continue
            for field in fkey_fields.get(fkey, []):
                out.setdefault(field, int(ev))

    for logical, elem_col in _ELEM_COL.items():
        try:
            table = q.load_table(logical)
        except Exception:
            continue
        for ln in _leaf_rows(table):
            row = cb._cols(ln)
            if len(row) <= elem_col:
                continue
            ev = row[elem_col]
            if ev not in ("0", "1", "2", "3", "4", "5", "6"):
                continue
            field = next((x for x in row if x in fd_keys), "")
            if field:
                out.setdefault(field, int(ev))
    return out


# ---- 元素变体系列(2026-07-29 用户需求「XX系列收到一起」)----
# 这几族的六元素变体招式完全相同,只有属性/换色不同 —— 一座塔出两个就是重复内容
# (实测 1.4.237 同塔出了雷龟+暗凤两只精灵兽、1.4.236 出了苍机兵+闪机兵)。
# 归并成一个去重键后,全塔按 SERIES_CAPS 配额限次(不是只出一次,见 series_cap)。
#
# ⚠ 为什么用**显式名单**而不是"从模型名里剥元素词":
#   ① 要合并的这几族,元素在**目录名**里(battle/boss/spirit_beast_fire/…),
#      所以模型名天然带元素 → 现状各自成键;
#   ② 八岐大蛇正相反,模型名本来就是 `orochi`(元素/头在**文件名**里),各头靠
#      progs 签名区分 —— 剥元素词对它无效,但通用规则容易误伤,显式名单最可控;
#   ③ 机兵/女王/废龙的多数变体在 standard_boss(无模型路径、boss_names 也查不到名),
#      `_model_and_progs` 回落到"代号即模型",元素同样在代号里。
# ⚠ 机工神兵菲诺梅那(steampunk_another)排除在外:它是决战级独立 boss(塔腰常驻位),
#   跟六元素机兵不是一回事,并进去会让常驻位和机兵锚位互相顶掉。
BOSS_SERIES = (
    ("精灵兽", "spirit_beast", ()),
    ("女王", "variant_empress", ()),
    ("荒龙", "discarded_dragon", ()),
    ("机兵", "steampunk", ("steampunk_another",)),
)

# 每系列在**一座 30 层塔**里允许出现几次(2026-07-29 用户指定:女王2/机兵3/精灵兽2;
# 荒龙没点名,跟女王/精灵兽同档给 2)。别的 boss 一律 1 次。
# 「都可以根据层数动态调整」⇒ 实际配额按层数线性缩放,见 series_cap()。
SERIES_CAPS = {"精灵兽": 2, "女王": 2, "荒龙": 2, "机兵": 3}
SERIES_CAP_BASE_ROUNDS = 30


def series_cap(series: str, rounds: int) -> int:
    """系列在 rounds 层塔里的出场配额(以 30 层为基准线性缩放,至少 1)。

    30 层 = 用户给的原始数(女王2/机兵3/精灵兽2/荒龙2);
    15 层减半(机兵 2、其余 1),60 层翻倍(机兵 6、其余 4)。
    """
    base = SERIES_CAPS.get(series, 1)
    return max(1, round(base * rounds / SERIES_CAP_BASE_ROUNDS))


def boss_series_of(code: str, model: str = "") -> str | None:
    """boss 代号/模型 → 所属元素变体系列名;不属于任何系列返回 None。"""
    for name, prefix, excludes in BOSS_SERIES:
        if any(str(code).startswith(x) for x in excludes):
            continue
        if str(code).startswith(prefix) or str(model).startswith(prefix):
            return name
    return None


def field_thumbnail_map() -> dict[str, str]:
    """field_data id → 宿主 quest 的战斗缩略图(240×188 正规 quest/thumbnail)。

    floor 行第 3 列是塔层 31×31 小图标,放 quest 预览位显示空白(1.4.120 实锤)。
    正确素材 = 引用该 floor 的幽玄域/深层域宿主 quest 的 thumbnail(c3);
    floor 键→quest 缩略图,再经 floor 行摊开到每个 field。
    """
    floor = q.load_table("master/battle/floor.orderedmap")
    fkey_fields: dict[str, list[str]] = {}
    for k, v in floor.items():
        if isinstance(v, dict):
            continue
        s = v.decode("utf-8") if isinstance(v, bytes) else v
        fkey_fields[k] = [cb._cols(ln)[0] for ln in s.split("\n")
                          if cb._cols(ln) and cb._cols(ln)[0] not in ("", "(None)")]
    out: dict[str, str] = {}
    for logical, floor_col in [
        ("master/quest/event/tower_dungeon_event_quest.orderedmap", 99),
        ("master/quest/event/challenge_dungeon_event_quest.orderedmap", 110),
    ]:
        try:
            table = q.load_table(logical)
        except Exception:
            continue
        for ln in _leaf_rows(table):
            row = cb._cols(ln)
            if len(row) <= floor_col:
                continue
            fkey = row[floor_col]
            thumb = row[3]
            if not fkey or fkey in ("(None)",) or not thumb or thumb == "(None)":
                continue
            for field in fkey_fields.get(fkey, []):
                out.setdefault(field, thumb)
    return out

START = "2000-01-01 12:00:00"
END = "2099-12-29 23:59:59"
RESULT_END = "2099-12-30 12:00:00"
EXCHANGE_END = "2099-12-31 11:59:59"


def cells(leaf) -> list[str]:
    line = leaf.decode("utf-8") if isinstance(leaf, bytes) else leaf
    return next(csv.reader(io.StringIO(line)))


def join(row: list[str], as_bytes: bool):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(row)
    s = buf.getvalue()
    return s.encode("utf-8") if as_bytes else s


def fmt(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s or "0"


def select_surjective_level(node: dict, enemy_level: int) -> int | None:
    """客户端 getSurjectivity：返回第一个 ``>= enemy_level`` 的数字档。"""
    if not isinstance(node, dict):
        return None
    try:
        level = int(enemy_level)
    except (TypeError, ValueError):
        return None
    keys = sorted(int(k) for k in node if str(k).isdigit())
    return next((key for key in keys if key >= level), None)


def clone_hit_boss_level_c2(source_leaf, scale: float):
    """重建一条 Hit-HP boss_level 叶，只缩放 c2，绝不改原叶或 c3/c4。"""
    as_bytes = isinstance(source_leaf, (bytes, bytearray))
    source = bytes(source_leaf) if isinstance(source_leaf, bytearray) else source_leaf
    if not isinstance(source, (str, bytes)):
        raise ValueError(f"boss_level leaf 类型非法:{type(source_leaf).__name__}")
    row = cells(source)
    if len(row) < 13:
        raise ValueError(f"boss_level 行列数={len(row)}(<13)")
    if row[0] != "0":
        raise ValueError("仅 Hit HP(kind=0) 可通过 boss_level.c2 伸缩；Fix HP 必须拒绝")
    try:
        old_c2 = float(row[2])
        c3 = float(row[3])
        factor = float(scale)
    except (TypeError, ValueError) as exc:
        raise ValueError("boss_level c2/c3 或伸缩倍率不是数字") from exc
    if not all(math.isfinite(v) and v > 0 for v in (old_c2, c3, factor)):
        raise ValueError(f"boss_level c2/c3/倍率必须为有限正数:{old_c2},{c3},{factor}")
    new_c2 = old_c2 * factor
    if not math.isfinite(new_c2) or new_c2 <= 0:
        raise ValueError(f"boss_level.c2 伸缩结果非法:{new_c2}")
    row[2] = fmt(new_c2)
    return join(row, as_bytes)


@dataclass(frozen=True)
class HpMember:
    """One reachable HP-bearing entity occurrence in a native bundle."""

    code: str
    kind: int
    role: str
    ordinal: int
    selected_level: int
    raw_hp: float


@dataclass(frozen=True)
class HpExpansionResult:
    ok: bool
    members: tuple[HpMember, ...] = ()
    total_hp: float | None = None
    selected_parent_level: int | None = None
    reason: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class OrochiCloneResult:
    ok: bool
    parent_code: str | None = None
    head_codes: tuple[str, ...] = ()
    clone_map: tuple[tuple[rbb.BossRef, rbb.BossRef], ...] = ()
    bundle: rbb.NativeBossBundle | None = None
    expanded: HpExpansionResult | None = None
    touched_tables: tuple[str, ...] = ()
    reason: str | None = None
    detail: str = ""


def _special_hp_failure(detail: str,
                        selected_level: int | None = None) -> HpExpansionResult:
    return HpExpansionResult(
        False, selected_parent_level=selected_level,
        reason="SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=detail)


def _orochi_parent_ref(bundle: rbb.NativeBossBundle) -> rbb.BossRef | None:
    refs = [slot.single for slot in bundle.slots if slot.single is not None]
    if len(refs) != 1:
        return None
    ref = refs[0]
    if (ref.kind != 3
            or (ref.code not in rbb.OROCHI_PARENT_VARIANTS
                and not ref.code.startswith("mod_rogue_orochi"))):
        return None
    return ref


def expand_bundle_hp_members(bundle: rbb.NativeBossBundle, enemy_level: int,
                             tables: dict) -> HpExpansionResult:
    """Expand an Orochi parent into one parent plus eight ordered head instances.

    ``total_hp`` is the raw :func:`true_stat` sum before the event-level K/c86
    multipliers.  The parent c24 list is occurrence-based: duplicate head codes
    remain duplicate members and are never collapsed into a set.
    """
    parent_ref = _orochi_parent_ref(bundle)
    if parent_ref is None:
        return _special_hp_failure("bundle is not one proved kind=3 Orochi parent")
    oro = tables.get("orochi")
    gb = tables.get("general_boss")
    gv = tables.get("general_boss_variable")
    bl = tables.get("boss_level")
    if not all(isinstance(table, dict) for table in (oro, gb, gv, bl)):
        return _special_hp_failure("Orochi HP expansion is missing one of oro/gb/gv/bl")
    parent_node = oro.get(parent_ref.code)
    selected = select_surjective_level(parent_node, enemy_level)
    if selected is None:
        return _special_hp_failure(
            f"{parent_ref.code} has no first tier >= lv{enemy_level}")
    parent_leaf = parent_node.get(str(selected)) if isinstance(parent_node, dict) else None
    if not isinstance(parent_leaf, (str, bytes, bytearray)):
        return _special_hp_failure(
            f"{parent_ref.code}@{selected} parent row is missing", selected)
    try:
        parent_row = cells(parent_leaf)
    except (TypeError, ValueError, UnicodeError) as exc:
        return _special_hp_failure(
            f"{parent_ref.code}@{selected} parent row cannot be parsed:{exc}", selected)
    if len(parent_row) < 25:
        return _special_hp_failure(
            f"{parent_ref.code}@{selected} parent row has {len(parent_row)} columns", selected)
    heads = tuple(code.strip() for code in parent_row[24].split(",")
                  if code.strip() and code.strip() != "(None)")
    if len(heads) != 8:
        return _special_hp_failure(
            f"{parent_ref.code}@{selected} c24 has {len(heads)} heads instead of 8",
            selected)

    specs = ((parent_ref.code, 3, "parent", 0),) + tuple(
        (code, 1, "head", ordinal)
        for ordinal, code in enumerate(heads, start=1))
    members: list[HpMember] = []
    for code, kind, role, ordinal in specs:
        leaf = bl.get(code)
        if not isinstance(leaf, (str, bytes, bytearray)):
            return _special_hp_failure(f"boss_level leaf missing:{code}", selected)
        try:
            hp_row = cells(leaf)
        except (TypeError, ValueError, UnicodeError) as exc:
            return _special_hp_failure(f"boss_level malformed:{code}:{exc}", selected)
        if len(hp_row) < 13 or hp_row[0] != "0":
            return _special_hp_failure(
                f"boss_level is not finite positive Hit HP:{code}", selected)
        try:
            c2 = float(hp_row[2])
            c3 = float(hp_row[3])
        except (TypeError, ValueError) as exc:
            return _special_hp_failure(f"boss_level malformed:{code}:{exc}", selected)
        if not all(math.isfinite(value) and value > 0 for value in (c2, c3)):
            return _special_hp_failure(
                f"boss_level is not finite positive Hit HP:{code}", selected)
        # ``true_stat`` intentionally proxies unknown curves for relative pool
        # ranking.  Orochi cloning needs an absolute nine-member readback, so
        # that fallback is forbidden here: an unknown/non-positive curve would
        # turn a guessed value into the c2 scaling baseline.
        curve_name = hp_row[4]
        curve = curve_value("hp", curve_name, selected)
        if curve is None or not math.isfinite(curve) or curve <= 0:
            return _special_hp_failure(
                f"unknown or invalid Hit HP curve:{code}:{curve_name}@{selected}",
                selected)
        if role == "head":
            gb_node = gb.get(code)
            gv_node = gv.get(code)
            if not isinstance(gb_node, dict) or not isinstance(gv_node, dict):
                return _special_hp_failure(f"head gb/gv dependency missing:{code}", selected)
            # Heads are dependencies of the selected parent row.  Prove that
            # exact tier directly; do not apply the ordinary standalone-general
            # "gv must have a low tier" rule (multi_plus intentionally has [100]).
            if (select_surjective_level(gb_node, selected) != selected
                    or select_surjective_level(gv_node, selected) != selected):
                return _special_hp_failure(
                    f"head does not cover parent-selected tier {selected}:{code}", selected)
        stat = true_stat(code, "hp", selected, bl)
        raw_hp = float(stat[0]) if stat is not None else float("nan")
        if not math.isfinite(raw_hp) or raw_hp <= 0:
            return _special_hp_failure(f"raw HP cannot be proved:{code}", selected)
        members.append(HpMember(
            code=code, kind=kind, role=role, ordinal=ordinal,
            selected_level=selected, raw_hp=raw_hp))
    return HpExpansionResult(
        True, members=tuple(members), total_hp=math.fsum(
            member.raw_hp for member in members),
        selected_parent_level=selected)


def _clone_result_failure(detail: str) -> OrochiCloneResult:
    return OrochiCloneResult(
        False, reason="SPECIAL_HP_CHANNEL_UNSUPPORTED", detail=detail)


def _orochi_clone_reference_error(
        expanded: HpExpansionResult, code_refs: dict,
        enemy_watch: dict | None) -> str | None:
    """Return why an expanded nine-entity graph cannot survive code renaming.

    ``hard`` references cannot be rewritten locally.  ``soft`` means the head
    owns a ``general_enemy_watch`` self subtree, which is cloneable only when
    the exact source row exists in the injected snapshot.  This helper is
    shared by catalog eligibility and realization so a bundle cannot enter the
    selector and then deterministically fail the same static precondition.
    """
    if code_refs.get("degraded"):
        return "external boss-code reference scan degraded"
    heads = tuple(member.code for member in expanded.members
                  if member.role == "head")
    hard = sorted(set(heads) & set(code_refs.get("hard", ())))
    if hard:
        return "head has uncloneable external code references:" + ",".join(hard)
    soft = sorted(set(heads) & set(code_refs.get("soft", ())))
    if soft:
        ew_self = enemy_watch.get("1") if isinstance(enemy_watch, dict) else None
        missing = [code for code in soft
                   if not isinstance(ew_self, dict) or code not in ew_self]
        if missing:
            return "required general_enemy_watch self row missing:" + ",".join(missing)
    return None


def clone_orochi_parent_bundle(bundle: rbb.NativeBossBundle, round_no: int,
                               scale: float, tables: dict) -> OrochiCloneResult:
    """Clone an Orochi parent and all eight heads through an off-table overlay.

    Expected validation failures return a structured result.  No caller-owned
    table is mutated until the overlay has been re-expanded successfully.
    """
    parent_ref = _orochi_parent_ref(bundle)
    if parent_ref is None:
        return _clone_result_failure("bundle is not one proved Orochi parent")
    try:
        round_value = int(round_no)
        factor = float(scale)
    except (TypeError, ValueError) as exc:
        return _clone_result_failure(f"round/scale is not numeric:{exc}")
    if round_value <= 0 or not math.isfinite(factor) or factor <= 0:
        return _clone_result_failure(
            f"round and scale must be finite positive:{round_no},{scale}")
    selected_values = {
        int(tier) for layer, slot, tier in bundle.selected_levels
        if any(item.layer == layer and item.slot == slot and item.single == parent_ref
               for item in bundle.slots)
    }
    if len(selected_values) != 1:
        return _clone_result_failure(
            f"bundle has no unique selected parent tier:{sorted(selected_values)}")
    selected_level = next(iter(selected_values))
    source = expand_bundle_hp_members(bundle, selected_level, tables)
    if not source.ok or source.total_hp is None:
        return _clone_result_failure(source.detail or "source HP expansion failed")

    required = ("orochi", "general_boss", "general_boss_variable", "boss_level")
    if not all(isinstance(tables.get(name), dict) for name in required):
        return _clone_result_failure("clone tables are missing or not mutable maps")
    oro = tables["orochi"]
    gb = tables["general_boss"]
    gv = tables["general_boss_variable"]
    bl = tables["boss_level"]
    ew = tables.get("general_enemy_watch")
    if ew is not None and not isinstance(ew, dict):
        return _clone_result_failure("general_enemy_watch is not a map")

    code_refs = tables.get("__code_references__")
    if not isinstance(code_refs, dict):
        code_refs = code_referenced_bosses(gb)
    ref_error = _orochi_clone_reference_error(source, code_refs, ew)
    if ref_error:
        return _clone_result_failure(ref_error)
    source_heads = tuple(member.code for member in source.members
                         if member.role == "head")

    parent_code = f"mod_rogue_orochi{round_value}"
    head_codes = tuple(
        f"{parent_code}_head{ordinal}" for ordinal in range(1, 9))
    target_codes = (parent_code,) + head_codes
    ew_self = ew.get("1", {}) if isinstance(ew, dict) else {}
    for code in target_codes:
        occupied = [name for name, table in (
            ("orochi", oro), ("general_boss", gb),
            ("general_boss_variable", gv), ("boss_level", bl))
                    if code in table]
        if isinstance(ew_self, dict) and code in ew_self:
            occupied.append("general_enemy_watch")
        if occupied:
            return _clone_result_failure(
                f"target key conflict:{code} in {','.join(occupied)}")

    # Shallow-copy top-level maps and deep-copy only new dependency rows.  This
    # is an off-table overlay: no nested source node is edited in place.
    overlay = {
        "orochi": dict(oro),
        "general_boss": dict(gb),
        "general_boss_variable": dict(gv),
        "boss_level": dict(bl),
    }
    if isinstance(ew, dict):
        overlay_ew = dict(ew)
        overlay_ew["1"] = dict(ew_self) if isinstance(ew_self, dict) else {}
        overlay["general_enemy_watch"] = overlay_ew

    parent_node = oro[parent_ref.code]
    parent_leaf = parent_node[str(selected_level)]
    parent_row = cells(parent_leaf)
    parent_row[24] = ",".join(head_codes)
    overlay["orochi"][parent_code] = {
        str(selected_level): join(
            parent_row, isinstance(parent_leaf, (bytes, bytearray)))
    }
    try:
        overlay["boss_level"][parent_code] = clone_hit_boss_level_c2(
            bl[parent_ref.code], factor)
        for source_code, target_code in zip(source_heads, head_codes):
            overlay["general_boss"][target_code] = copy.deepcopy(gb[source_code])
            overlay["general_boss_variable"][target_code] = copy.deepcopy(
                gv[source_code])
            overlay["boss_level"][target_code] = clone_hit_boss_level_c2(
                bl[source_code], factor)
            if ("general_enemy_watch" in overlay
                    and isinstance(ew_self, dict) and source_code in ew_self):
                overlay["general_enemy_watch"]["1"][target_code] = copy.deepcopy(
                    ew_self[source_code])
    except (KeyError, TypeError, ValueError) as exc:
        return _clone_result_failure(f"dependency staging failed:{exc}")

    cloned_slots = []
    for slot in bundle.slots:
        single = (rbb.BossRef(3, parent_code)
                  if slot.single == parent_ref else slot.single)
        multi = (rbb.BossRef(3, parent_code)
                 if slot.multi == parent_ref else slot.multi)
        cloned_slots.append(replace(slot, single=single, multi=multi))
    cloned_selected = tuple(
        (layer, slot, tier) for layer, slot, tier in bundle.selected_levels)
    cloned_bundle = replace(
        bundle, slots=tuple(cloned_slots), selected_levels=cloned_selected)
    readback = expand_bundle_hp_members(cloned_bundle, selected_level, overlay)
    expected_total = source.total_hp * factor
    if (not readback.ok or readback.total_hp is None
            or not math.isclose(readback.total_hp, expected_total,
                                rel_tol=1e-9, abs_tol=1.0)):
        return _clone_result_failure(
            "overlay HP readback failed:"
            f"{readback.detail or readback.total_hp} expected={expected_total}")

    # Commit additions only after the complete nine-entity readback succeeds.
    oro[parent_code] = overlay["orochi"][parent_code]
    bl[parent_code] = overlay["boss_level"][parent_code]
    for target_code in head_codes:
        gb[target_code] = overlay["general_boss"][target_code]
        gv[target_code] = overlay["general_boss_variable"][target_code]
        bl[target_code] = overlay["boss_level"][target_code]
        if (isinstance(ew, dict)
                and target_code in overlay.get("general_enemy_watch", {}).get("1", {})):
            ew.setdefault("1", {})[target_code] = \
                overlay["general_enemy_watch"]["1"][target_code]

    clone_map = ((parent_ref, rbb.BossRef(3, parent_code)),) + tuple(
        (rbb.BossRef(1, source_code), rbb.BossRef(1, target_code))
        for source_code, target_code in zip(source_heads, head_codes))
    touched = ["orochi", "general_boss", "general_boss_variable", "boss_level"]
    if isinstance(ew, dict) and any(
            target_code in ew.get("1", {}) for target_code in head_codes):
        touched.append("general_enemy_watch")
    return OrochiCloneResult(
        True, parent_code=parent_code, head_codes=head_codes,
        clone_map=clone_map, bundle=cloned_bundle, expanded=readback,
        touched_tables=tuple(touched))


def purge_orochi_clones(tables: dict) -> tuple[str, ...]:
    """Purge only the dedicated ``mod_rogue_orochi*`` clone namespace."""
    touched: list[str] = []
    for name in ("orochi", "general_boss", "general_boss_variable", "boss_level"):
        table = tables.get(name)
        if not isinstance(table, dict):
            continue
        keys = [key for key in table if str(key).startswith("mod_rogue_orochi")]
        for key in keys:
            table.pop(key, None)
        if keys:
            touched.append(name)
    ew = tables.get("general_enemy_watch")
    ew_self = ew.get("1") if isinstance(ew, dict) else None
    if isinstance(ew_self, dict):
        keys = [key for key in ew_self
                if str(key).startswith("mod_rogue_orochi")]
        for key in keys:
            ew_self.pop(key, None)
        if keys:
            touched.append("general_enemy_watch")
    return tuple(touched)


def rogue_battle_write_plan(*, gimmick_dirty: bool, caster_dirty: bool,
                            orochi_dirty: bool,
                            enemy_watch_available: bool) -> tuple[str, ...]:
    """Return dependency-first battle-table writes for a tower build."""
    out: list[str] = []
    if caster_dirty:
        out.extend((GENERAL_ZAKO, ZAKO_LEVEL))
    if caster_dirty or orochi_dirty:
        out.extend((GENERAL_BOSS, BOSS_LEVEL, GENERAL_BOSS_VARIABLE))
        if enemy_watch_available:
            out.append(ENEMY_WATCH)
    if orochi_dirty:
        out.append(OROCHI)
    if gimmick_dirty:
        # field_data.c2 dereferences the zone key, so the dependency must be
        # durable first if the later per-file save fails.  This is still not a
        # cross-table transaction; it merely avoids the dangling direction.
        out.extend((ZONE_T, FIELD_DATA_T))
    return tuple(dict.fromkeys(out))


def general_hp_scale_plan(bosses: list[str], native: dict,
                          general_boss: dict, boss_level: dict,
                          enemy_level: int, *, target_hp: float,
                          curse_hp: float,
                          code_references: dict | None = None) -> dict:
    """为纯 general 层生成逐 code 的 baseline/final c2 叶与可复核 HP 证据。

    当前 ``boss_level`` 数据形态是 ``code -> CSV leaf``，没有等级内层；等级
    getSurjectivity 只发生在 ``general_boss``。这里把选中的 general 档记进计划，
    克隆后必须再次选档并逐项相等，防止代码与 boss_level 叶错配。
    """
    components = list(native.get("components") or [])
    if not native.get("verified") or not components:
        raise ValueError(f"general HP 伸缩缺原生 HP 证据:{native.get('reason') or 'unknown'}")
    if any(component.get("kind") != "general" for component in components):
        raise ValueError("general/standard 混合族不能用单一 c86/c2 通道，必须换 boss")
    ordered_codes = list(dict.fromkeys(map(str, bosses)))
    identity_block = identity_locked_boss_reason(
        ordered_codes, code_references=code_references)
    if identity_block:
        # Defense in depth: candidate selection should have routed this layer
        # through same-id c86 already.  Keeping the check in the c2 plan means
        # a future caller cannot silently reintroduce a pure HP rename clone.
        raise ValueError(f"纯 HP clone 拒绝:{identity_block}")
    component_codes = [str(component.get("code")) for component in components]
    if not ordered_codes or set(component_codes) != set(ordered_codes):
        raise ValueError(
            f"general HP 实体与证据代号不一致:bosses={ordered_codes},components={component_codes}")
    try:
        wanted_hp = float(target_hp)
        hp_mult = float(curse_hp)
        native_hp = math.fsum(float(component["native_hp"]) for component in components)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("general HP 伸缩输入含非数字") from exc
    if not all(math.isfinite(v) and v > 0 for v in (wanted_hp, hp_mult, native_hp)):
        raise ValueError(
            f"general HP 伸缩输入必须为有限正数:target={target_hp},curse={curse_hp},native={native_hp}")
    baseline_scale = wanted_hp / native_hp
    final_scale = baseline_scale * hp_mult
    selected_levels: dict[str, int] = {}
    baseline_leaves: dict[str, str | bytes] = {}
    final_leaves: dict[str, str | bytes] = {}
    baseline_factors: dict[str, float] = {}
    final_factors: dict[str, float] = {}
    for code in ordered_codes:
        selected = select_surjective_level(general_boss.get(code), int(enemy_level))
        if selected is None:
            raise ValueError(f"general_boss[{code}] 无 >=lv{enemy_level} 的运行档")
        source_leaf = boss_level.get(code)
        if source_leaf is None:
            raise ValueError(f"boss_level[{code}] 缺失")
        baseline_leaf = clone_hit_boss_level_c2(source_leaf, baseline_scale)
        final_leaf = clone_hit_boss_level_c2(source_leaf, final_scale)
        old_c2 = float(cells(source_leaf)[2])
        selected_levels[code] = selected
        baseline_leaves[code] = baseline_leaf
        final_leaves[code] = final_leaf
        baseline_factors[code] = float(cells(baseline_leaf)[2]) / old_c2
        final_factors[code] = float(cells(final_leaf)[2]) / old_c2
    baseline_true_hp = math.fsum(
        float(component["native_hp"]) * baseline_factors[str(component["code"])]
        for component in components)
    true_hp = math.fsum(
        float(component["native_hp"]) * final_factors[str(component["code"])]
        for component in components)
    return {
        "family": "general", "c86": 1.0, "curse_hp": hp_mult,
        "selected_levels": selected_levels,
        "baseline_scale": baseline_scale, "final_scale": final_scale,
        "baseline_factors": baseline_factors, "final_factors": final_factors,
        "baseline_leaves": baseline_leaves, "final_leaves": final_leaves,
        "baseline_true_hp": baseline_true_hp, "true_hp": true_hp,
    }


def floor_hp_scaling_strategy(bosses: list[str], native: dict,
                              general_boss: dict, boss_level: dict,
                              enemy_level: int, *, required_c86: float,
                              deep: bool,
                              code_references: dict | None = None) -> dict:
    """选择该层 HP 主通道；不可实现的族组合直接抛错供调用方重抽。"""
    components = list(native.get("components") or [])
    if not native.get("verified") or not components:
        raise ValueError(f"HP 主通道缺原生证据:{native.get('reason') or 'unknown'}")
    families = {str(component.get("kind")) for component in components}
    try:
        needed = float(required_c86)
        native_hp = float(native["native_hp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("HP 主通道 required_c86/native_hp 非数字") from exc
    if not all(math.isfinite(v) and v > 0 for v in (needed, native_hp)):
        raise ValueError(f"HP 主通道输入非法:c86={required_c86},native={native_hp}")
    if families == {"general"}:
        identity_block = identity_locked_boss_reason(
            bosses, code_references=code_references)
        if identity_block:
            lo, hi = STANDARD_C86_LIMITS
            if not lo <= needed <= hi:
                raise ValueError(
                    f"{identity_block}; 保持原 id 仅可用 c86 微调窗口 "
                    f"{lo:g}~{hi:g}，需要 {needed:g}，拒绝候选并重抽")
            return {
                "channel": "c86", "family": "identity-locked",
                "baseline_c86": needed, "baseline_scale": 1.0,
                "selected_levels": {},
            }
        plan = general_hp_scale_plan(
            list(map(str, bosses)), native, general_boss, boss_level,
            int(enemy_level), target_hp=native_hp * needed, curse_hp=1.0,
            code_references=code_references)
        return {
            "channel": "boss_level", "family": "general",
            "baseline_c86": 1.0,
            "baseline_scale": plan["baseline_scale"],
            "selected_levels": plan["selected_levels"],
        }
    if families == {"standard"}:
        if deep:
            raise ValueError("深层必须使用可伸缩 general boss，standard 不适用")
        lo, hi = STANDARD_C86_LIMITS
        if not lo <= needed <= hi:
            raise ValueError(
                f"standard 基线 c86={needed:g} 超出微调窗口 {lo:g}~{hi:g}")
        return {"channel": "c86", "family": "standard",
                "baseline_c86": needed, "baseline_scale": 1.0,
                "selected_levels": {}}
    raise ValueError(f"HP 主通道不支持混合/未知族:{sorted(families)}")


GB_RESIST_ELEMENT_RESISTANCE_COL = 36
_GB_BOOL_TRUE = {"true", "True", "TRUE"}
_GB_BOOL_FALSE = {"false", "False", "FALSE"}


def general_boss_element_immunity_block(general_boss: dict, code: str,
                                        enemy_level: int | None = None,
                                        general_boss_variable: dict | None = None) -> str | None:
    """实际 general_boss 代号能否承载属性免疫；返回阻断原因或 None。

    `resist_element_resistance` 已由 GeneralBossValues.as:725-754 钉死为 c36。
    必须先按本层 enemy level 选中最终/克隆后的实际档,再检查该档的全部 leaf；
    该档任一运行变体为真都会吞掉 ElementResistance。
    客户端只接受六种大小写布尔字面量,缺行/短行/未知值一律 fail closed。
    """
    node = general_boss.get(code)
    if node is None:
        return f"actual boss {code} 不在 general_boss"
    # GeneralBossSource.as:88 直接对 GeneralBossTable[code] 调 getSurjectivity(level):
    # 取第一个 ≥敌等级的 general_boss 行。general_boss_variable 在 :96-99 另行解析,
    # **不参与 values/c36 选行**。只看 gv 会把 gb[79]=false / gb[100]=true 的
    # lv80/90 boss 错放；这里保留形参只为调用兼容,明确不使用。
    _ = general_boss_variable
    if isinstance(node, dict):
        gb_levels = sorted(int(k) for k in node if str(k).isdigit())
        if enemy_level is not None:
            selected_level = select_surjective_level(node, int(enemy_level))
        elif len(gb_levels) == 1:
            selected_level = gb_levels[0]
        else:
            selected_level = None
        if selected_level is None:
            return (f"actual boss {code} 无 ≥lv{enemy_level} 的克隆后实际"
                    " general_boss 行,fail closed")
        node = node[str(selected_level)]
        row_where = f"gb[{selected_level}]"
    else:
        row_where = "gb[leaf]"
    seen = 0
    for leaf in _leaf_rows(node):
        row = cells(leaf)
        if len(row) != 162:
            return (f"actual boss {code} {row_where} 行列数={len(row)}"
                    "(应为162),fail closed")
        raw = row[GB_RESIST_ELEMENT_RESISTANCE_COL]
        if raw in _GB_BOOL_TRUE:
            return f"actual boss {code} {row_where} c36=true(resist_element_resistance)"
        if raw not in _GB_BOOL_FALSE:
            return (f"actual boss {code} {row_where} c36={raw!r}"
                    " 非客户端合法布尔字面量,fail closed")
        seen += 1
    return None if seen else f"actual boss {code} {row_where} 没有可解析 leaf,fail closed"


def assert_element_immunity_runtime_safe(quest_logical: str, enemy_level: int) -> None:
    """防 autoHighLevel 将整族属性免疫静默吃掉。

    EnemySourceBase params[13]=autoHighLevel 且 level>=80 时会把
    resistElementResistance 强制置 true；isAutoHighLevelBoss() 仅在
    ScoreAttackEventBattleQuestLogic override 为 true,普通 event_quest 基类恒 false。
    当前 Rush 塔因此安全；未来若迁到 score_attack 且仍是 lv80/90/100,构建必须硬停。
    """
    path = str(quest_logical).replace("\\", "/").lower()
    if enemy_level >= 80 and "score_attack" in path:
        raise RuntimeError(
            f"属性免疫拒绝用于 score_attack lv{enemy_level}:autoHighLevel 会静默抵消效果")
    if "/quest/event/" not in path:
        raise RuntimeError(f"属性免疫 quest logic 未确证为 event_quest:{quest_logical}")


def patch_event_metadata(row: list[str]) -> list[str]:
    """只把深渊 Rush Event 的兑换代币改为深渊代币。"""
    row[10] = TOKEN_ID
    return row


def build_event_metadata_leaf(
    template_leaf: bytes | str,
    current_leaf: bytes | str,
) -> bytes | str:
    """Rebuild 700099 from the canonical template, preserving only banner art."""
    template = cells(template_leaf)
    current = cells(current_leaf)
    if len(template) < 18:
        raise ValueError(f"rush_event[{TEMPLATE_EVENT}] must have at least 18 columns")
    if len(current) < 5:
        raise ValueError(f"rush_event[{EVENT_ID}] must have at least 5 columns")

    row = list(template)
    row[0] = EVENT_STRING_ID
    row[1] = EVENT_NAME
    row[2] = f"{START},{END},{RESULT_END},{EXCHANGE_END}"
    row[3:5] = current[3:5]
    row[10] = TOKEN_ID
    row[15] = START
    row[16] = END
    row[17] = EXCHANGE_END
    return join(row, isinstance(current_leaf, bytes))


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 700099 深渊连战")
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--seed", type=int, default=int(date.today().strftime("%Y%m%d")))
    ap.add_argument("--difficulty", choices=tuple(DIFF_PRESETS), default="hell",
                    help="全塔难度预设(**默认 hell=全塔烈狱**,2026-07-29 用户主推):"
                         "easy=全简单 / normal / hell=全炼狱 / gradient=从简单到难;"
                         "接管成长曲线(端点式,层数自适应)与诅咒档,"
                         "显式 --hp-*/--atk-*/--curse 可单项覆盖")
    ap.add_argument("--ramp", action="store_true",
                    help="显式恢复旧 DPS 几何爬坡(60万→2500万)。默认关闭，"
                         "默认 HP profile 为除第1战热身外全程决战级；"
                         "此开关与 --enemy-level ramp 的敌等级爬坡无关。")
    ap.add_argument("--no-normalize", dest="normalize", action="store_false",
                    help="关闭旧基数归一(现主要影响 ATK)。Task C 的 boss HP"
                         "已改为 general/standard 真 HP 直接反解，不再依赖旧 HP 代理。")
    ap.add_argument("--normalize-hp", type=float, default=1.0,
                    help="旧 HP 分组归一指数(仅保留 raw/诊断兼容)；Task C boss"
                         "层由绝对 HP 目标取代，默认 1.0。")
    ap.add_argument("--normalize-atk", type=float, default=0.55,
                    help="伤害归一**压缩指数**(默认 0.55=只压一半,保留「高低有别」)。"
                         "残余跨度≈原极差^(1-指数);全池 atk 极差 86× → 约 6×")
    ap.add_argument("--normalize-min", type=float, default=0.1,
                    help="归一补偿下限(默认 0.1×)。实测线上塔层间真实血量极差:不归一 80× / 0.25–4 → 8× / **0.1–10 → 3×** / 0.05–20 → 2×")
    ap.add_argument("--normalize-max", type=float, default=100.0,
                    help="旧 HP raw 归一上限(任务 C 依规格放开到 100×)；"
                         "仅保留选池诊断兼容，general 最终改缩 boss_level.c2。")
    ap.add_argument("--normalize-atk-max", type=float, default=10.0,
                    help="攻击归一补偿上限(默认仍为 10×，不随 HP 窗口放大)")
    ap.add_argument("--hp-base", type=float, default=None)
    ap.add_argument("--hp-growth", type=float, default=None)
    ap.add_argument("--atk-base", type=float, default=None)
    ap.add_argument("--atk-growth", type=float, default=None)
    ap.add_argument("--enemy-level", default="ramp",
                    help="敌等级:ramp=按深度爬坡(**默认**,前1/3 lv80→中段 lv90→"
                         "尾段 lv100,见 LEVEL_RAMP)/ 数字(如 90)/ "
                         "max=每层取该 boss 数据里的最高档。"
                         "⚠ 官方 96%% 内容停在 lv80 以下,lv100 是曲线悬崖顶"
                         "(atk_single lv99→100 单档 ×1.30、lv80→100 ×1.72),"
                         "全塔平坦 lv100 = 每层都站在悬崖上")
    ap.add_argument("--curse", choices=("off",) + CURSE_TIERS, default=None,
                    help="深渊诅咒档位(默认随 --difficulty;无预设时 abyss;off=关闭)")
    ap.add_argument("--mix", action="store_true",
                    help="模块化拼接:塔楼层的地形与 boss 独立随机组合(克隆 zone 换 boss 槽,"
                         "元素跟 boss 老家楼层走),领域/诅咒照常叠加。"
                         "若安全白名单+HP窗口令实际拼接为0层，构建明确失败。")
    ap.add_argument("--test-field", type=int, default=0, metavar="R",
                    help="强制第 R 轮附加「深渊法阵」(真机验证用)")
    ap.add_argument("--dump-immunity-dsl", action="store_true",
                    help="dry-run 同时打印本轮生成的属性/伤害耐性 DSL 树(构造自查)")
    ap.add_argument("--ignore-plan", action="store_true",
                    help="忽略连战工坊布局计划(rogue_layout_plan.json)")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="只校验解析链不生成:逐关检查 quest c98→field→zone→boss/zako")
    ap.add_argument("--check-event", default=EVENT_ID, metavar="ID",
                    help="--check 的事件 id(默认 700099)")
    ap.add_argument("--check-quest-path", metavar="FILE",
                    help="--check 用指定 quest 表文件(如 .bak 备份)代替 store 现状")
    args = ap.parse_args()

    if args.normalize and (args.normalize_min <= 0
                           or args.normalize_max < args.normalize_min
                           or args.normalize_atk_max < args.normalize_min):
        print("[ERR] normalize 窗口必须为正，且两个上限都不得小于 --normalize-min")
        return 1

    if args.check:
        src_disp = args.check_quest_path or "store 现状"
        print(f"[CHECK] rush_event_quest[{args.check_event}] 解析链({src_disp}):")
        reports = validate_event_chain(
            args.check_event,
            quest_path=Path(args.check_quest_path) if args.check_quest_path else None)
        bad = print_chain_reports(reports)
        if bad:
            print(f"[ERR] {bad}/{len(reports)} 关引用悬空(进本必崩)")
            return 1
        print(f"[OK] 全部 {len(reports)} 关解析链完整")
        return 0

    # 敌等级:max = 逐层取该 boss 支持的最高档;ramp = 按深度爬坡(默认)
    _lvarg = str(args.enemy_level).strip().lower()
    want_max = _lvarg in ("max", "最强", "-1")
    want_ramp = _lvarg in ("ramp", "爬坡")
    # 素材池门禁仍按最高档试算(resolve_level 找不到可行档才判悬空),爬坡是**逐层**的
    args.enemy_level = 100 if (want_max or want_ramp) else int(args.enemy_level)

    def want_level(r: int) -> int:
        """该层的目标敌等级。resolve_level 再按 boss 实际支持的档位就近落。"""
        if not want_ramp:
            return args.enemy_level
        d = r / max(1, args.rounds)
        return LEVEL_RAMP[0] if d <= 1 / 3 else (LEVEL_RAMP[1] if d <= 2 / 3
                                                 else LEVEL_RAMP[2])

    rng = random.Random(args.seed)

    # ---- 难度预设解析:显式 CLI 参数 > 预设 > 旧默认(向后兼容) ----
    if args.difficulty:
        hp0, hpg, atk0, atkg = difficulty_curve(args.difficulty, args.rounds)
    else:
        hp0, hpg, atk0, atkg = 0.6, 1.2, 0.4, 1.145
    hp_base = args.hp_base if args.hp_base is not None else hp0
    hp_growth = args.hp_growth if args.hp_growth is not None else hpg
    atk_base = args.atk_base if args.atk_base is not None else atk0
    atk_growth = args.atk_growth if args.atk_growth is not None else atkg

    def round_tier(r: int) -> str:
        if args.curse:
            return args.curse
        if args.difficulty:
            return tier_for_round(args.difficulty, r, args.rounds)
        return "abyss"

    # ---- 战场链表载入(引用完整性门禁 + 后文克隆注入共用同一份内存态)----
    fd_t = q.load_table(FIELD_DATA_T)
    zone_t = q.load_table(ZONE_T)
    gz_t = q.load_table(GENERAL_ZAKO)
    zl_t = q.load_table(ZAKO_LEVEL)
    gb_t = q.load_table(GENERAL_BOSS)
    bl_t = q.load_table(BOSS_LEVEL)
    gv_t = q.load_table(GENERAL_BOSS_VARIABLE)
    oro_t = q.load_table(OROCHI)
    # general_enemy_watch:法阵载体克隆要连它的 **self 侧**条目一起复制,否则
    # 「我 watch 别人」那套联动(如旋风巨土俑「buff 炮台死光→换阶段」)随改名一起丢。
    # 表的顶层键是**实体种类**(1=general boss / 2=funnel / 3=breakable block,
    # 对应客户端 GeneralBossSource:92 / FunnelSource:86 / BreakableBlockSource:76),
    # **不是** GeneralEnemyWatchKind 那个 9 值枚举——那个在叶子行的列里,与这层无关。
    # 读不到 / 读出空表 → ew_t=None,degraded 生效,本轮一律不发法阵。
    # ⚠ 空表必须当读不到:否则下面 save() 会把一张空表写回 store 并上链,
    #   等于把官方 163 个 watch 条目整个抹掉。
    try:
        ew_t = q.load_table(ENEMY_WATCH) or None
    except Exception as _e:
        ew_t = None
        print(f"[WARN] general_enemy_watch 读不到({_e})")
    if ew_t is None:
        print("[WARN] general_enemy_watch 不可用;本轮一律不发深渊法阵")
    sb_t = q.load_table(STANDARD_BOSS)      # 只读:门禁三表并集用
    stale = ([k for k in fd_t if str(k).startswith("mod_rogue_f")]
             + [k for k in zone_t if str(k).startswith("mod_rogue_z")])
    stale_c = ([k for k in gz_t if str(k).startswith("mod_rogue_caster")]
               + [k for k in zl_t if str(k).startswith("mod_rogue_caster")]
               + [k for k in gb_t if str(k).startswith("mod_rogue_boss")]
               + [k for k in bl_t if str(k).startswith("mod_rogue_boss")]
               + [k for k in gv_t if str(k).startswith("mod_rogue_boss")]
               + ([k for k in (ew_t or {}).get("1", {})
                   if str(k).startswith("mod_rogue_boss")] if ew_t else []))
    for k in stale:
        fd_t.pop(k, None)
        zone_t.pop(k, None)
    for k in stale_c:
        gz_t.pop(k, None)
        zl_t.pop(k, None)
        gb_t.pop(k, None)
        bl_t.pop(k, None)
        gv_t.pop(k, None)
        if ew_t is not None:
            ew_t.get("1", {}).pop(k, None)
    orochi_purged_tables = purge_orochi_clones({
        "orochi": oro_t,
        "general_boss": gb_t,
        "general_boss_variable": gv_t,
        "boss_level": bl_t,
        "general_enemy_watch": ew_t,
    })
    gim_dirty = bool(stale)
    caster_dirty = bool(stale_c)
    # Task 5 will also set this after a successful per-round clone.  Purge-only
    # runs are dirty too: otherwise old parent/head keys survive in store.
    orochi_dirty = bool(orochi_purged_tables)

    def field_gate(field_id: str) -> dict:
        """引用完整性门禁 + 等级可行性(2026-07-28 改:只要该层存在可行等级即放行,
        具体等级在写入时按层自适应 —— 避免一层封顶拖垮整塔构建)。"""
        report = check_field_chain(field_id, fd_t, zone_t,
                                   set(gb_t) | set(sb_t) | set(gz_t), set(gz_t))
        if not report["ok"]:
            return report
        level = resolve_level(report["bosses"], args.enemy_level, sb_t, gv_t, gb_t,
                              prefer_max=want_max)
        if level is None:
            report["ok"] = False
            report["errors"] = [f"没有任何敌等级能让 {','.join(report['bosses'])} 正常解析"]
        else:
            report["level"] = level
        return report

    # wf_chain_build 的通用池会把 single/multi 镜像六列全扫进 bosses；本塔是单人
    # event quest，数值审计与重排都必须只携带 c24/28/32 的实际实体，否则 anv3
    # 这类镜像代号不同的场地会被静默算成双 boss、HP 翻倍。
    tower_all = [(field, line, _zone_pick(field)[0])
                 for field, line, _legacy_bosses in cb.build_pool()]
    blocked = [e for e in tower_all if field_blocked(e[0])]
    if blocked:
        tower_all = [e for e in tower_all if not field_blocked(e[0])]
        print(f"[黑名单] 塔素材池剔除 {len(blocked)} 层非 boss 战场地:"
              + ",".join(e[0] for e in blocked))
    resolvable, dangling = [], []
    for e in tower_all:
        rep = field_gate(e[0])
        (resolvable if rep["ok"] else dangling).append((e, rep))
    if dangling:
        print(f"[门禁] 塔素材池剔除 {len(dangling)} 层引用悬空(进本必崩 U_50fc52):")
        for (fdk, _ln, _b), rep in dangling:
            print(f"    {fdk}: {rep['errors'][0]}")
    gated = [e for e, _rep in resolvable]
    tower = [e for e in gated if _pool_safe(e[2])]
    if len(tower) < len(gated):
        print(f"[黑名单] 塔素材池剔除 {len(gated) - len(tower)} 层"
              f"(C8016:{','.join(C8016_BLOCKED_BOSS_PREFIXES)} / "
              f"血量级别错配:{','.join(HP_BLOCKED_BOSSES)})")
    if len(tower) < args.rounds + 1:
        print(f"[ERR] 塔素材池只有 {len(tower)} 层 < {args.rounds}+1 轮")
        return 1
    tower_master = list(tower)          # 钉选(工坊 boss/terrain)查询用,不随消费缩水

    # ---- boss 出场历史降权:最近两座塔出过的 boss,80% 概率让位给新面孔 ----
    special_bosses = load_special_bosses()
    if special_bosses[0] or special_bosses[1]:
        print(f"[原味] 特殊 boss 保护:精确 {len(special_bosses[0])} 个 + "
              f"前缀 {len(special_bosses[1])} 族(抽中即原场地原机制,不拆解)")
    try:
        high_threat_prefixes, high_threat_exact = load_high_threat_rules()
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERR] 高威胁 boss 名单不可用:{exc}")
        return 1
    if high_threat_prefixes or high_threat_exact:
        print("[高威胁] 降难规则:prefixes=" + ",".join(high_threat_prefixes)
              + " exact=" + ",".join(sorted(high_threat_exact)))
    _boss_names = wb.boss_names()

    def _model_and_progs(code: str) -> tuple[str, frozenset]:
        """(模型族, 攻击程序签名)。程序签名取 general_boss 行里引用的 action 名集合。"""
        node = gb_t.get(code) or sb_t.get(code)
        model = ""
        progs: set[str] = set()
        if isinstance(node, dict):
            for leaf in node.values():
                if isinstance(leaf, dict):
                    continue
                text = leaf if isinstance(leaf, str) else (
                    leaf.decode("utf-8") if isinstance(leaf, bytes) else "")
                for ln in text.split(chr(10)):
                    for c in cells(ln):
                        if not model and c.startswith("battle/boss/") \
                                and "general_16dots" not in c:
                            model = c.split("/")[2]
                        if "battle/action" in c:
                            for part in c.split(","):
                                if part.startswith("battle/action"):
                                    progs.add(part.split("$")[-1])
                break
        return model or str(_boss_names.get(code, code)), frozenset(progs)

    def _family(code: str) -> str:
        """去重键 = 模型族 + 攻击程序签名(2026-07-29 用户需求)。

        纯换色同招式的变体仍算同一个(管理者族连出问题);而八岐大蛇三头
        (beam/fire/funnel 程序各异)、猩红巨熊各版本这类**攻击模式不同的变体**
        视为不同 boss,可在同一座塔共存 —— 以前一律按模型族压成 1 个,
        24 个大蛇变体只剩 1 个候选,用户「打了这么久没见过」。"""
        model, progs = _model_and_progs(code)
        return f"{model}#{hash(progs) & 0xffffff:06x}" if progs else model

    def _series_key(code: str) -> str:
        """全塔去重键 = 元素变体系列(精灵兽/女王/荒龙/机兵)压成一个,其余同 _family。

        2026-07-29 用户「XX系列收到一起」:六元素招式一模一样、只换色换属性,
        同塔出两个是重复内容(实测同塔出过雷龟+暗凤、苍机兵+闪机兵)。"""
        model, _progs = _model_and_progs(code)
        series = boss_series_of(code, model)
        return f"系列:{series}" if series else _family(code)

    def name_keys(bosses) -> set[str]:
        """**全塔去重**用系列键。系列有**配额**(见 SERIES_CAPS/series_cap),
        普通 boss 配额恒 1。"""
        return {_series_key(str(b)) for b in bosses}

    def key_cap(key: str) -> int:
        """该去重键在本塔的出场配额:系列按层数缩放,其余恒 1。"""
        return series_cap(key[3:], args.rounds) if key.startswith("系列:") else 1

    def grade_keys(bosses) -> set[str]:
        """**分级收敛**(collapse_grades)用细粒度键。

        ⚠ 这两件事必须用不同的键:分级收敛是"同一个 boss 只留最高难度版本",
        如果也按系列压,六元素会在**池子层面**只剩 1 条 —— 实测机兵池 6→1,
        等于以后永远只出红机兵。要的是"一座塔只出一个",不是"整个池只留一个"。"""
        return {_family(str(b)) for b in bosses}

    # 全塔去重**计数**(2026-07-29 从"用过就禁"改成"配额制"):普通 boss 配额 1
    # (等级/单多人变体同名同灭),元素变体系列按 SERIES_CAPS × 层数给多个名额。
    used_counts: dict[str, int] = {}
    future_anchor_counts: dict[str, int] = {}

    def _quota_left(key: str) -> bool:
        return (used_counts.get(key, 0) + future_anchor_counts.get(key, 0)
                < key_cap(key))

    def unused_only(entries, bosses_of):
        kept = [e for e in entries
                if all(_quota_left(k) for k in name_keys(bosses_of(e)))]
        return kept or entries          # 池子枯竭才允许重复(打印于挑选处)

    recent_bosses = set(sum(load_boss_history()[:2], []))
    if recent_bosses:
        print(f"[历史] 最近两座塔出过 {len(recent_bosses)} 个 boss,抽取时降权(80% 偏好新面孔)")

    def prefer_fresh(entries, bosses_of):
        if not recent_bosses:
            return entries
        fresh = [e for e in entries if not (set(bosses_of(e)) & recent_bosses)]
        if fresh and rng.random() < 0.8:
            return fresh
        return entries

    featured_pref, featured_w = load_featured_bosses()
    if featured_pref:
        print(f"[精选] {len(featured_pref)} 个 boss 前缀权重 ×{featured_w}:"
              + ",".join(featured_pref))

    def weight_featured(entries, bosses_of):
        """精选 boss 的候选项重复 featured_w 份 = 抽中概率 ×N(不是硬钉)。"""
        if not featured_pref:
            return entries
        out = list(entries)
        for e in entries:
            if is_featured(bosses_of(e), featured_pref):
                out.extend([e] * (featured_w - 1))
        return out

    # ---- 楼层来源池(v5)----
    def gate_src(label: str, entries: list[dict]) -> list[dict]:
        kept = []
        for e in entries:
            if field_blocked(e["field"]):
                print(f"[黑名单] 来源池「{label}」剔除 {e['field']}(非 boss 战场地)")
                continue
            rep = field_gate(e["field"])
            if rep["ok"]:
                kept.append(e)
            else:
                print(f"[门禁] 来源池「{label}」剔除 {e['field']}: {rep['errors'][0]}")
        return kept

    zako_lst = gate_src("小怪房", zako_room_pool())
    minion_lst = gate_src("杂鱼boss", minion_boss_pool())
    src = {
        "领主战": quest_pool("boss_battle"),
        "机兵": quest_pool("hard_multi"),
        "降临讨伐": quest_pool("advent"),
        # 2026-07-29 补全:联动/活动 boss(C·F·奇迹、超人泽古拉、基因巨龙、DAN 警卫、
        # 噬星兽等)只挂在世界剧情/剧情活动下,以前整类没进池 —— 用户「打了这么久
        # 没见过联动 boss」的根因
        "世界剧情": quest_pool("world_story"),
        "剧情活动": quest_pool("story_event"),
        "女帝歼灭者": quest_pool("advent", name_eq="女帝歼灭者"),
        "无幻之宴": quest_pool("raid", name_eq="无幻之宴"),
        # 2026-07-29 全类别普查补全:GUI 手选池覆盖 16 类,生成器随机却只抽 7 类,
        # 下面 6 类整类抽不到(合计 ~90 个 boss 摸不着)。类别↔中文对照:
        #   战阵之宴 = raid(黑龙/基因巨龙/异质魔晶羊;无幻之宴另有守门固定位)
        #   单人挑战 = expert_single_event[1]「单人挑战 讨伐战斗」
        #              + [2]「追忆试炼」(同表:诅咒弧魔六档/白虎/管理者/不死王/寄居蟹船长)
        #   极时试炼 = solo_time_attack(时与X之试炼,六个 *_ex 强化版)
        #   剧情boss = world_story_boss(玛格诺斯/噬龙者/星辰破坏者/统领AI/SecMk2)
        #   元素试炼 = ranking(云水/奔雷/旋风/溢光/闪火 = 五元素球本体)
        #   土俑嘉年华 = carnival(6 元素 × 土机/直击/强振/必杀 4 套伤害体系 = 24 个
        #              独立去重键,用户明确要求全量,不做同族收敛)
        "战阵之宴": [e for e in quest_pool("raid") if e["name"] != "无幻之宴"],
        "单人挑战": quest_pool("expert_single"),
        "极时试炼": quest_pool("solo_time_attack"),
        "剧情boss": quest_pool("world_story_boss"),
        "元素试炼": quest_pool("ranking"),
        "土俑嘉年华": quest_pool("carnival"),
        "主线boss": main_story_boss_pool(),
    }
    for label in src:
        gated_pool = gate_src(label, src[label])
        kept = [e for e in gated_pool if _pool_safe(e["bosses"])]
        if len(kept) < len(gated_pool):
            print(f"[黑名单] 来源池「{label}」剔除 {len(gated_pool) - len(kept)} 个场地")
        top = collapse_grades(kept, grade_keys)   # 细粒度:六元素都要留在池里
        if len(top) < len(kept):
            print(f"[分级] 来源池「{label}」{len(kept)} → {len(top)}(同 boss 只留最高难度版本)")
        # 「超级起步」硬门槛(2026-07-29 用户需求:简单档一律不看)。
        # collapse_grades 已把每个 boss 收敛到它最难的一版,所以这里刷掉的是
        # **本身最高也只有高级/中级**的 boss —— 它们要么在塔池里另有高难变体,
        # 要么就该待在杂鱼层。全刷空时保留原池(宁可低档也别让排程塌掉)。
        hard = ([] if label in NO_LEVEL_FLOOR else
                [e for e in top if str(e.get("level", "")).isdigit()
                 and int(e["level"]) >= MIN_QUEST_LEVEL])
        if label in NO_LEVEL_FLOOR:
            pass                      # 主线boss:手挑名单,官方等级本就低,不设门槛
        elif hard and len(hard) < len(top):
            print(f"[难度] 来源池「{label}」{len(top)} → {len(hard)}"
                  f"(只留 ≥{MIN_QUEST_LEVEL} 级=超级及以上)")
            top = hard
        elif not hard:
            print(f"[难度] 来源池「{label}」无 ≥{MIN_QUEST_LEVEL} 级场地,保留原池 {len(top)} 个")
        src[label] = top
    # 终始之龙(2026-07-20 换回主线正版):NPC 协力/剧情强制是 quest 侧列,只引用
    # field 不会带过来;「buff 重置」压制(buff_reset1..4)在 boss kit 里=原汁机制。
    # boss=chapter12_boss_story(standard,官方元素=暗),1 wave,专属 12 章擂台。
    DRAGON_FIELD = "main_12_10_01"
    DRAGON_THUMB = "quest/thumbnail/world_12/battle_12_5"
    dragon_rep = field_gate(DRAGON_FIELD)
    if not dragon_rep["ok"]:
        print(f"[ERR] 末轮固定楼层「终始之龙」({DRAGON_FIELD}) 引用悬空:"
              + "; ".join(dragon_rep["errors"]))
        return 1
    # 机工神兵菲诺梅那(2026-07-29 用户需求:与终始之龙同等待遇的常驻 boss)。
    # steampunk_another 一个 field 挂 5 个难度行(20/50/70/80/100),取地狱级;
    # zone 里是**双 boss**:本体 steampunk_another_multi + 二形态 _foom2_multi,
    # 两者都在 standard_boss。原味保护名单里已有这两个代号,不会被 mix 拆解。
    PHENO_FIELD = "steampunk_another"
    pheno_src = next((e for e in quest_pool("boss_battle")
                      if e["field"] == PHENO_FIELD), None)
    PHENO_THUMB = (pheno_src or {}).get("thumb", "")
    pheno_rep = field_gate(PHENO_FIELD)
    if not pheno_rep["ok"]:
        print(f"[ERR] 常驻楼层「机工神兵菲诺梅那」({PHENO_FIELD}) 引用悬空:"
              + "; ".join(pheno_rep["errors"]))
        return 1
    # 始龙之眼(多人版)下放到领主战池当普通 boss 候选
    EYE_FIELD = "eye_dragon_multibattle"
    EYE_THUMB = "quest/thumbnail/world_10/thumbnail1"
    eye_rep = field_gate(EYE_FIELD)
    if eye_rep["ok"]:
        src["领主战"].append({"field": EYE_FIELD, "bosses": ["eye_dragon_multibattle_boss"],
                              "thumb": EYE_THUMB, "name": "始龙之眼"})
    else:
        print(f"[门禁] 固定候选「始龙之眼」({EYE_FIELD}) 引用悬空,弃用:"
              + "; ".join(eye_rep["errors"]))
    for label, lst in ([("小怪房", zako_lst), ("杂鱼boss", minion_lst)]
                       + list(src.items())):
        if not lst:
            print(f"[ERR] 来源池「{label}」为空")
            return 1
        print(f"来源池 {label}: {len(lst)} 个场地")

    # quest 名在池内不唯一时(24 个土俑嘉年华全叫「土俑嘉年华」、演武全叫「XX演武」),
    # 计划表打印退回 boss 名,否则一眼看不出抽到的是哪个伤害体系的变体。
    _dup_names: dict[str, set] = {}
    for _lab, _lst in src.items():
        _cnt: dict[str, int] = {}
        for _e in _lst:
            _cnt[_e["name"]] = _cnt.get(_e["name"], 0) + 1
        _dup_names[_lab] = {n for n, c in _cnt.items() if c > 1}

    def src_pick(label: str) -> dict:
        cand = unused_only(src[label], lambda e: e["bosses"])
        cand = prefer_fresh(cand, lambda e: e["bosses"])
        cand = weight_featured(cand, lambda e: e["bosses"])
        e = cand[rng.randrange(len(cand))]
        disp = e["name"]
        # 主线boss 是"按 boss 挑"的池,关卡名(「破除诅咒1」)看不出打的是谁,恒显示 boss 名
        if not disp or label == "主线boss" or disp in _dup_names.get(label, ()):
            disp = "、".join(dict.fromkeys(
                str(_boss_names.get(b, b)).split("/")[0] for b in e["bosses"])) or e["field"]
        return {"field": e["field"], "bosses": e["bosses"], "thumb": e["thumb"],
                "bgm": None, "label": f"{label}·{disp}"}

    def dragon_pick() -> dict:
        bosses, _ = _zone_pick(DRAGON_FIELD)
        return {"field": DRAGON_FIELD, "bosses": bosses, "thumb": DRAGON_THUMB,
                "bgm": None, "label": "终始之龙·主线终章正版"}

    def zako_pick() -> dict:
        e = zako_lst.pop(rng.randrange(len(zako_lst)))
        return {"field": e["field"], "bosses": [], "thumb": e["thumb"],
                "bgm": None, "label": f"小怪房·{e['name']}"}

    def phenomena_pick() -> dict:
        bosses, _ = _zone_pick(PHENO_FIELD)
        return {"field": PHENO_FIELD, "bosses": bosses, "thumb": PHENO_THUMB,
                "bgm": None, "label": "机工神兵·菲诺梅那 地狱级"}

    def minion_pick() -> dict:
        cand = unused_only(minion_lst, lambda e: e["bosses"])
        cand = prefer_fresh(cand, lambda e: e["bosses"])
        e = cand[rng.randrange(len(cand))]
        minion_lst.remove(e)
        disp = "、".join(dict.fromkeys(
            str(_boss_names.get(b, b)).split("/")[0] for b in e["bosses"])) or e["name"]
        return {"field": e["field"], "bosses": e["bosses"], "thumb": e["thumb"],
                "bgm": None, "label": f"杂鱼boss·{disp}"}

    # ---- ② rush_event 行 ----
    # ⚠ 列语义(RushEventValues 实锤):c2=banner_schedule(横幅轮播排期,不是活动期!)
    # c15=start_time c16=playable_end_time c17=exchangeable_end_time。
    # 700099 行已存在时以现有行为基底(保留 wf_rogue_banner 换过的横幅列 c3/c4)。
    ev = q.load_table(Q_EVENT)
    template_leaf = ev[TEMPLATE_EVENT]
    current_leaf = ev.get(EVENT_ID) or template_leaf
    event_leaf = build_event_metadata_leaf(template_leaf, current_leaf)
    ev_row = cells(event_leaf)
    ev_bytes = isinstance(event_leaf, bytes)

    # ---- ② folder 行(连战=700007 超级 folder 3 模板;无尽=folder 4 模板)----
    fo = q.load_table(Q_FOLDER)
    tmpl_fo = cells(fo[TEMPLATE_EVENT]["3"])
    fo_bytes = isinstance(fo[TEMPLATE_EVENT]["3"], bytes)
    fo_row = list(tmpl_fo)
    fo_row[0] = "1"           # display_order
    fo_row[1] = "1"           # quest_kind = rush folder
    fo_row[2] = EVENT_NAME
    fo_endless = list(cells(fo[TEMPLATE_EVENT]["4"]))
    fo_endless[0] = "100"
    fo_endless[1] = "2"       # quest_kind = endless(缺它 = 点∞按钮 C3442)
    fo_endless[2] = "无尽战斗"

    # ---- ② quest 行 ----
    qt = q.load_table(Q_QUEST)
    tmpl_r1 = cells(qt[TEMPLATE_EVENT]["1"])
    tmpl_rn = cells(qt[TEMPLATE_EVENT]["2"])
    tmpl_endless = cells(qt[TEMPLATE_EVENT]["8"])
    qt_bytes = isinstance(qt[TEMPLATE_EVENT]["1"], bytes)
    ELEM_CN = QUEST_ELEM_CN      # c69 是 quest 枚举(0风1火2水3雷4暗5光),别用 boss 那套

    thumb_map = field_thumbnail_map()
    belem_map = boss_element_map()
    elem_map = field_official_elem_map()

    # ---- 乱流机关:zone/field 克隆注入(诅咒「乱流机关」)----
    # 机关列语义:c36 冲刺板 / c37 旋转桨,全游戏同族机制仅皮肤不同(塔层实际用
    # 海遗迹皮),跨地形通用;地形无锚点时安静空转,无崩溃面。克隆行前缀
    # mod_rogue_z/f,每次构建先清旧克隆防膨胀。
    GIM_DASH = "battle/field_object/world_advent/steampunk_area/yakumono/dash_panel"
    GIM_ROT = ("battle/field_object/world_advent/steampunk_area/"
               "rotation_panel/steampunk_area_rotation_panel")
    # fd_t/zone_t/gz_t/zl_t/gb_t/bl_t/gv_t 已在 main 顶部载入并清过旧克隆(门禁共用)

    # ---- terrain 能力表(2026-07-20:锚点决定祭坛/板子能否生效)----
    # 板子能力 = 数据驱动:官方存在"zone 挂 c36 板子"配对的 terrain 集合;
    # 出生点能力 = terrain(Tiled) 二进制含 SPAWNn 标记(排除 FUNNEL_SPAWNn)。
    # 成对/分阶段 boss 名单(数据驱动,进程内算一次)+ 被门禁挡下的层的理由
    phase_linked = phase_linked_bosses(zone_t, fd_t)
    # 代号引用名单只算一次(要遍历 general_boss_state 4.4MB);逐层重算 = 白烧十几秒。
    code_refs = code_referenced_bosses(gb_t)
    if ew_t is None and not code_refs["degraded"]:
        # 表读得到才有 self 侧可补;读不到时上面的 WARN 已把 degraded 置真,这里兜底。
        code_refs = dict(code_refs, degraded=True)
    caster_blocked: dict[str, str] = {}
    clone_sources: dict[str, str] = {}
    panel_terrains: set[str] = set()
    for fk, fv in fd_t.items():
        if not isinstance(fv, (str, bytes, bytearray)):
            continue
        fc0 = cells(fv)
        if len(fc0) < 3:
            continue
        zn0 = zone_t.get(fc0[2])
        if not isinstance(zn0, dict):
            continue
        for wrow0 in zn0.values():
            if isinstance(wrow0, dict):
                continue
            wc0 = cells(wrow0)
            if len(wc0) > 36 and wc0[36] not in ("", "(None)"):
                panel_terrains.add(fc0[1])
                break

    def carrier_status(field_id: str, bosses: list[str],
                       enemy_level: int | None = None, *,
                       record: bool = False) -> dict:
        """无副作用计算硬通道/属性免疫资格；仅 ``record`` 时登记最终场地理由。"""
        target = next((b for b in bosses if b in belem_map), None)
        carrier = target is not None
        carrier_why = None
        if carrier:
            # 成对/分阶段 boss 层禁发法阵(2026-07-30 玩家「打不死」实锤);
            # 被外部按代号引用的 boss 同禁(2026-08-03 鲨鱼三兄弟/旋风巨土俑实锤)
            why = caster_carrier_block(field_id, bosses, fd_t, zone_t,
                                       phase_linked, gb_t, refs=code_refs)
            if why:
                if record:
                    caster_blocked[field_id] = why
                carrier = False
                carrier_why = why
        element_reason = carrier_why or (
            general_boss_element_immunity_block(gb_t, target, enemy_level, gv_t)
            if target else "没有 general_boss 实际代号")
        return {"boss": carrier,
                "element": carrier and element_reason is None,
                "element_target": target,
                "element_reason": element_reason,
                "carrier_reason": (carrier_why or (
                    "没有 general_boss 实际代号" if target is None else None))}

    def field_caps(field_id: str, bosses: list[str], enemy_level: int | None = None) -> dict:
        """能力表:boss=有 general boss 可当法阵载体(2026-07-20 实证:zone-zako
        emitter 需地形 SPAWN 物件定位,95% 楼层没有,'*spawn-point*' 是"生成点"
        注册名而非地形标记查找——zako 祭坛路线弃);panel=官方板子配对地形。"""
        frow = fd_t.get(field_id)
        panel = False
        if isinstance(frow, (str, bytes, bytearray)):
            fc = cells(frow)
            panel = len(fc) > 2 and fc[1] in panel_terrains
        status = carrier_status(field_id, bosses, enemy_level, record=True)
        status["panel"] = panel
        return status

    def make_caster_boss(r: int, boss_code: str, action_program: str | None = None,
                         action_programs=(),
                         pre_action_program: str | None = None,
                         requires_element_resistance: bool = False,
                         enemy_level: int | None = None,
                         clone_code: str | None = None,
                         boss_level_leaf=None,
                         expected_selected_level: int | None = None):
        """克隆 general boss 当 HP/硬效果载体。

        法阵追加到第一条现役 action(c111-160)；耐性条件追加到 c109
        pre_action 且 c110=true。两者可共用同一克隆,定位天然有效。
        附表(boss_level/general_boss_variable/general_enemy_watch 的 self 侧)按 code
        同步克隆;routine 经 routine_id 引用原状态组,零克隆。

        ⚠ general_enemy_watch 的 self 条目**必须**跟着克隆(2026-08-03):客户端按
        [实体种类=1][boss 代号][routine_id] 取自身观察数据(GeneralBossSource:92 →
        GeneralEnemyWatchTableTools.getSelfData),查不到静默返回 null。routine_id 随行
        克隆时没变,所以整棵子树原样挂到新代号下即可。partner 侧(别人 watch 我)按代号
        索引、改不动,那类 boss 由 caster_carrier_block 硬拦,不走这里。"""
        nonlocal caster_dirty
        if boss_code not in gb_t:
            return None
        identity_block = identity_locked_boss_reason(
            [boss_code], code_references=code_refs)
        if identity_block:
            # Must precede every table mutation below.  Candidate/strategy
            # gates normally make this unreachable; this last guard prevents a
            # future direct caller from leaving a renamed half-clone behind.
            raise RuntimeError(f"第{r}战 general boss clone 拒绝:{identity_block}")
        code = clone_code or f"mod_rogue_boss{r}"

        if action_program or action_programs or pre_action_program:
            gb_t[code] = rewrite_boss_carrier_node(
                gb_t[boss_code], action_program=action_program,
                action_programs=action_programs,
                pre_action_program=pre_action_program)
        else:
            # 纯 HP clone 不追加 action，但仍必须拥有独立 general_boss 子树；
            # 未来若再改 clone 行，不能反向污染官方源代号。
            gb_t[code] = copy.deepcopy(gb_t[boss_code])
        if boss_level_leaf is not None:
            # boss_level 在当前表形态是 code→CSV leaf（没有等级内层）。只接受
            # general_hp_scale_plan 已重建的 Hit 行；Fix/短行会在这里再次 fail closed。
            check = cells(boss_level_leaf)
            if len(check) < 13 or check[0] != "0":
                raise RuntimeError(f"第{r}战 {boss_code} 的 clone boss_level 不是 Hit HP 行")
            bl_t[code] = boss_level_leaf
        elif boss_code in bl_t:
            bl_t[code] = bl_t[boss_code]
        if boss_code in gv_t:
            gv_t[code] = gv_t[boss_code]
        if requires_element_resistance:
            # 最终判据必须读“克隆后实际落表行”的 c36,不是原型名。预筛本应让它
            # 永远为 false；若克隆逻辑未来改坏继承关系,在文案落表前硬停。
            blocked = general_boss_element_immunity_block(gb_t, code, enemy_level, gv_t)
            if blocked:
                raise RuntimeError(f"第{r}战属性免疫载体复核失败:{blocked}")
        if enemy_level is not None:
            source_selected = select_surjective_level(gb_t.get(boss_code), enemy_level)
            clone_selected = select_surjective_level(gb_t.get(code), enemy_level)
            expected = (source_selected if expected_selected_level is None
                        else int(expected_selected_level))
            if source_selected != expected or clone_selected != expected:
                raise RuntimeError(
                    f"第{r}战 boss clone 选档漂移:{boss_code}@{source_selected} -> "
                    f"{code}@{clone_selected}, expected={expected}")
            if code not in bl_t:
                raise RuntimeError(f"第{r}战 boss clone {code} 缺 boss_level 叶")
        if ew_t is not None and boss_code in ew_t.get("1", {}):
            ew_t.setdefault("1", {})[code] = ew_t["1"][boss_code]
        clone_sources[code] = boss_code
        caster_dirty = True
        return code

    def gimmick_field(orig_field: str, r: int, panels: bool = False,
                      boss_swap: tuple[str, str] | None = None,
                      boss_swaps=()):
        """克隆 orig_field 的 field+zone:按需注入机兵皮机关 / 把单人 boss 槽
        (c24/c28/c32)换成施法克隆 boss。返回新 field 键(失败 None)。"""
        nonlocal gim_dirty
        frow = fd_t.get(orig_field)
        if frow is None:
            return None
        fc = cells(frow)
        zn = zone_t.get(fc[2])
        if not isinstance(zn, dict):
            return None
        zkey, fkey = f"mod_rogue_z{r}", f"mod_rogue_f{r}"
        swaps = list(boss_swaps or ())
        if boss_swap:
            swaps.append(boss_swap)
        nz = {}
        for wk, wrow in zn.items():
            if isinstance(wrow, dict):
                return None                       # 异形嵌套 zone,不折腾
            wc = cells(wrow)
            while len(wc) < 41:
                wc.append("")
            if panels:
                wc[36], wc[37] = GIM_DASH, GIM_ROT
            for old_code, new_code in swaps:
                apply_boss_swap(wc, old_code, new_code)
            nz[wk] = join(wc, isinstance(wrow, (bytes, bytearray)))
        zone_t[zkey] = nz
        nf = list(fc)
        nf[2] = zkey
        fd_t[fkey] = join(nf, isinstance(frow, (bytes, bytearray)))
        gim_dirty = True
        return fkey

    def tier_band(r: int) -> set[int]:
        """该关允许的楼层强度档:深度映射到 1..5,允许 ±1 浮动(伪随机的设计感)。"""
        t = 1 + round((r / args.rounds) * 4)
        return {max(1, t - 1), min(5, max(1, t)), min(5, t + 1)}

    def tower_pick(r: int | None = None) -> dict:
        pool_v = tower
        # 前 2 关允许杂兵热身,第 3 关起只出真 boss(2026-07-29:1/3 阈值让
        # 30 层塔的第 9 关还在打小怪)
        if r is not None and r >= 3:
            zkeys = set(map(str, gz_t))
            true_b = [e for e in tower
                      if not any(is_minion_boss(b, zkeys) for b in e[2])]
            if true_b:
                pool_v = true_b
        if r is not None:
            banded = [e for e in pool_v if floor_tier(e[0]) in tier_band(r)]
            if banded:
                pool_v = banded
            elif r / args.rounds > 0.5:
                hard = [e for e in pool_v if floor_tier(e[0]) >= 3]
                if hard:
                    pool_v = hard           # 过半程绝不回落到低档(简单 boss 禁入后段)
        pool_v = unused_only(pool_v, lambda e: e[2])
        pool_v = prefer_non_threat_candidates(
            pool_v, r, args.rounds, lambda e: e[2],
            high_threat_prefixes, high_threat_exact)
        cand = prefer_fresh(pool_v, lambda e: e[2])
        cand = weight_featured(cand, lambda e: e[2])
        e = cand[rng.randrange(len(cand))]
        tower.remove(e)
        f, line, bosses = e
        fc = cb._cols(line)
        return {"field": f, "bosses": bosses, "thumb": thumb_map.get(f, ""),
                "bgm": fc[1], "label": "塔·" + ",".join(bosses)}

    def mix_pick(r: int, pin_terrain: str | None = None,
                 pin_boss: str | None = None) -> dict | None:
        """模块化拼接层:地形楼层 × 另一楼层的 boss 组,独立随机。

        c69 恒跟 boss 老家元素(官方源 quest 或固定元素 boss,C8016 铁律);
        老家元素不可知的 boss 源直接不进拼接池(fail-closed)。地形的 zako/机关/
        BGM 保留,boss 槽整组换血;克隆层照旧过写入前链路复核。
        pin_terrain/pin_boss = 工坊按关钉选(floors.{N}.terrain / .boss);
        钉 boss 允许与其它关重复(用户显式指定),钉选不到返回 None 由外层报错。
        """
        nonlocal gim_dirty
        # Identity-lock rejection occurs after resolving both source and target,
        # but before any field/zone write.  Keep the pool snapshot so an
        # explicit incompatible pin is a real transaction failure rather than
        # a failure that quietly consumed one or two future candidates.
        pool_before = list(tower)
        if pin_terrain:
            terrain = next((e for e in tower if e[0] == pin_terrain), None)
            if terrain is None:
                terrain = next((e for e in tower_master if e[0] == pin_terrain), None)
            if terrain is None and pin_terrain in fd_t and field_gate(pin_terrain)["ok"]:
                terrain = (pin_terrain, None, [])       # 任意过门禁的场地都可当地形
            if terrain is None:
                print(f"[ERR] 第{r}战钉选地形 {pin_terrain} 不存在或没过门禁")
                return None
            if terrain in tower:
                tower.remove(terrain)
        else:
            sockets = load_socket_families()
            donors = [e for e in tower
                      if not any(str(b).startswith(sockets) for b in e[2])] if sockets else tower
            if not donors:
                donors = tower
            terrain = donors[rng.randrange(len(donors))]
            tower.remove(terrain)
        _terrain_row = fd_t.get(terrain[0])
        _terrain_cells = (cells(_terrain_row)
                          if isinstance(_terrain_row, (str, bytes, bytearray)) else [])
        _terrain_zone = (zone_t.get(_terrain_cells[2])
                         if len(_terrain_cells) > 2 else None)
        terrain_slot_count = len(zone_single_bosses(_terrain_zone))
        if terrain_slot_count <= 0:
            if terrain in tower_master and terrain not in tower:
                tower.append(terrain)
            print(f"[ERR] 第{r}战混搭地形 {terrain[0]} 没有单人 boss 实体槽")
            return None
        if pin_boss:
            src_e = next((e for e in tower_master if pin_boss in e[2]), None)
            if src_e is None:                           # 塔池没有 → 搜全部来源池
                for lst in src.values():
                    hit = next((d for d in lst if pin_boss in d["bosses"]), None)
                    if hit is not None:
                        src_e = (hit["field"], None, hit["bosses"])
                        break
            if src_e is None:
                print(f"[ERR] 第{r}战钉选 boss {pin_boss} 不在任何门禁通过的池里")
                if not pin_terrain:
                    tower.append(terrain)
                return None
            if src_e in tower:
                tower.remove(src_e)
        else:
            cands = [e for e in tower
                     if len(e[2]) == terrain_slot_count
                     and (elem_map.get(e[0]) is not None
                          or any(belem_map.get(b) is not None for b in e[2]))]
            if not cands:
                tower.append(terrain)
                return None
            # strict_transplant 的语义是“只有白名单 donor 真能拼”。旧实现却先在
            # 全池随机，抽到非白名单就整场退回原味；30 层一次都没抽中安全 donor
            # 时 --mix 最终必失败。先在同一实体槽数内优先安全 donor，不放宽名单。
            strict, safe_set = load_transplant_policy()
            portable = [e for e in cands
                        if (not strict or all(b in safe_set for b in e[2]))
                        and not any(is_special_boss(b, special_bosses) for b in e[2])]
            if portable:
                cands = portable
            if r >= 3:
                zkeys = set(map(str, gz_t))
                true_b = [e for e in cands
                          if not any(is_minion_boss(b, zkeys) for b in e[2])]
                if true_b:
                    cands = true_b
            banded = [e for e in cands if floor_tier(e[0]) in tier_band(r)]
            if banded:
                cands = banded                  # 深关只抽高档 boss(设计感排布)
            elif r / args.rounds > 0.5:
                hard = [e for e in cands if floor_tier(e[0]) >= 3]
                if hard:
                    cands = hard
            cands = unused_only(cands, lambda e: e[2])
            cands = prefer_non_threat_candidates(
                cands, r, args.rounds, lambda e: e[2],
                high_threat_prefixes, high_threat_exact)
            cands = prefer_fresh(cands, lambda e: e[2])
            src_e = cands[rng.randrange(len(cands))]
            tower.remove(src_e)
        tf, tline, _tb = terrain
        sf, _sline, sbosses = src_e
        identity_block = identity_locked_boss_reason(
            sbosses, code_references=code_refs)
        identity_move_block = identity_locked_mix_reason(
            sbosses, sf, tf, code_references=code_refs)
        if identity_block:
            # Never synthesize mod_rogue_f/z for a hard-ref boss, even when the
            # selected terrain happens to be its own: preserve the native
            # field, zone, master id, actions, and funnel anchors as one unit.
            tower[:] = pool_before
            if identity_move_block and pin_terrain:
                print(f"[ERR] 第{r}战钉选组合拒绝:{identity_move_block}; "
                      "未创建 field/zone，塔池已回滚")
                return None
            if not pin_boss and src_e in tower:
                tower.remove(src_e)
            log(f"[身份锁] round={r} {identity_block}; 随机混搭回退原味 {sf}")
            return {"field": sf, "bosses": list(sbosses),
                    "thumb": thumb_map.get(sf, ""),
                    "bgm": (cb._cols(_sline)[1] if _sline else None),
                    "label": "原味·" + ",".join(sorted(set(sbosses)))}
        strict, safe_set = load_transplant_policy()
        unsafe = strict and not all(b in safe_set for b in sbosses)
        if (unsafe or any(is_special_boss(b, special_bosses) for b in sbosses))                 and not pin_terrain:
            # 原味保护:名单 boss 不拆解,整层直用它的老家场地(诅咒照常在外层叠加)
            if not pin_boss:
                tower.append(terrain)               # 地形没用上,归还池子
            return {"field": sf, "bosses": sbosses, "thumb": thumb_map.get(sf, ""),
                    "bgm": (cb._cols(_sline)[1] if _sline else None),
                    "label": "原味·" + ",".join(sorted(set(sbosses)))}
        if len(sbosses) != terrain_slot_count:
            if not pin_terrain and terrain not in tower:
                tower.append(terrain)
            if not pin_boss and src_e not in tower:
                tower.append(src_e)
            print(f"[ERR] 第{r}战混搭实体数不匹配:"
                  f"地形{terrain_slot_count}槽 / donor {len(sbosses)}只")
            return None
        frow = fd_t[tf]
        fc = cells(frow)
        zkey, fkey = f"mod_rogue_z{r}", f"mod_rogue_f{r}"
        zone_t[zkey] = swap_zone_bosses(zone_t[fc[2]], sbosses)
        realized_bosses = zone_single_bosses(zone_t[zkey])
        if realized_bosses != list(sbosses):
            raise RuntimeError(
                f"第{r}战混搭 boss 实体不一致:donor={sbosses},realized={realized_bosses}")
        nf = list(fc)
        nf[2] = zkey
        fd_t[fkey] = join(nf, isinstance(frow, (bytes, bytearray)))
        gim_dirty = True
        elem = elem_map.get(sf)
        if elem is None:
            elem = next((belem_map[b] for b in sbosses if belem_map.get(b) is not None), None)
        return {"field": fkey, "bosses": realized_bosses,
                "thumb": thumb_map.get(tf, ""),
                "bgm": (cb._cols(tline)[1] if tline else None),
                "elem_override": elem, "boost_field": tf,
                "label": f"拼·{','.join(sbosses)} @ {tf}",
                # 供任务 C 重排时原地更换 donor，不丢失 --mix 语义。
                "_mix_terrain_entry": terrain, "_mix_boss_entry": src_e,
                "_mix_slot_count": terrain_slot_count}

    # ---- 楼层计划 v8(module 级 build_schedule):任意层数自适应 ----
    if args.rounds < 2:
        print("[ERR] rounds 最少 2(1 层塔 + 末层始龙)")
        return 1
    if args.rounds > 98:
        print("[ERR] rounds 最多 98(99 是无尽档专用键)")
        return 1
    schedule = build_schedule(args.rounds, rng)
    PICKERS = {"小怪房": zako_pick, "终始之龙": dragon_pick,
               "杂鱼boss": minion_pick, "机工神兵": phenomena_pick,
               "领主战": lambda: src_pick("领主战"), "机兵": lambda: src_pick("机兵"),
               "降临讨伐": lambda: src_pick("降临讨伐"),
               "女帝歼灭者": lambda: src_pick("女帝歼灭者"),
               "世界剧情": lambda: src_pick("世界剧情"),
               "剧情活动": lambda: src_pick("剧情活动"),
               "无幻之宴": lambda: src_pick("无幻之宴"),
               "战阵之宴": lambda: src_pick("战阵之宴"),
               "单人挑战": lambda: src_pick("单人挑战"),
               "极时试炼": lambda: src_pick("极时试炼"),
               "剧情boss": lambda: src_pick("剧情boss"),
               "元素试炼": lambda: src_pick("元素试炼"),
               "土俑嘉年华": lambda: src_pick("土俑嘉年华"),
               "主线boss": lambda: src_pick("主线boss")}

    # ---- 简单来源难度补偿(叠乘在轮次曲线上)----
    # 小怪房/主线领主战是低等级内容,只吃轮次曲线会白给;塔层按区域深浅补
    # (区域≤6 浅层显著补,7-8 轻补,9-10 本就是高难不补)。
    # 杂鱼boss:主线小怪提拔族,基础数值比正经 boss 低一档,补偿介于小怪房与领主战之间
    SRC_BOOST = {"小怪房": (2.5, 1.6), "杂鱼boss": (2.2, 1.5), "领主战": (1.8, 1.4)}
    # 归一化锚点:用**本塔实际用到的全部 boss**算每条修正曲线的基数中位数
    _all_codes = {b for e in tower_master for b in e[2]}
    for _lst in list(src.values()) + [zako_lst, minion_lst]:
        for _e in _lst:
            _all_codes |= set(_e.get("bosses") or [])
    _hp_med, _atk_med = curve_medians(_all_codes)
    if args.normalize:
        print(f"[归一] 基数中位锚 hp={ {k: round(v) for k, v in _hp_med.items()} } "
              f"HP clamp {args.normalize_min}–{args.normalize_max}× / "
              f"ATK clamp {args.normalize_min}–{args.normalize_atk_max}×"
              f"(standard 系无 boss_level 条目,不参与)")

    def tower_area_boost(field: str) -> tuple[float, float]:
        m = re.match(r"tower_dungeon_+area_(\d+)_", field)
        if not m:
            return (1.0, 1.0)
        area = int(m.group(1))
        if area <= 6:
            return (1.6, 1.3)
        if area <= 8:
            return (1.3, 1.15)
        return (1.0, 1.0)

    def patch_common(row: list[str], name: str, pick: dict) -> str:
        row[4] = name
        row[7] = START
        row[8] = END
        row[67] = "0"                                    # 体力
        # 楼层等级在循环里按爬坡档已经算好(pick["level"]);无尽档等走老路。
        level = (pick.get("level")
                 or resolve_level(pick["bosses"], args.enemy_level, sb_t, gv_t,
                                  gb_t, prefer_max=want_max)
                 or args.enemy_level)
        source_elements = dict(elem_map)
        if pick.get("elem_override") is not None:
            source_elements[pick["field"]] = int(pick["elem_override"])
        elem, tag = patch_quest_boss_fields(
            row,
            field=pick["field"],
            play_field=pick.get("play_field"),
            bosses=pick["bosses"],
            thumbnail=pick.get("thumb"),
            bgm=pick.get("bgm"),
            enemy_level=int(level),
            rng=rng,
            field_elements=source_elements,
            boss_elements=belem_map,
        )
        return f" 属性:{ELEM_CN[elem] if elem < 6 else '无'}{tag}"

    _hp_fit_cache: dict[tuple[str, int, float], dict | None] = {}
    _hp_fit_rejects: dict[tuple[str, int, float], str] = {}

    def hp_pick_metrics(pick: dict, r: int, target: float) -> dict | None:
        """按真实等级决定候选的 HP 主通道；不可缩放即不进候补。"""
        field = str(pick["field"])
        key = (field, r, round(float(target), 6))
        if key in _hp_fit_cache:
            return _hp_fit_cache[key]
        bosses = list(pick.get("bosses") or _zone_pick(field)[0])
        if not bosses:
            _hp_fit_cache[key] = None
            return None
        level = int(resolve_level(bosses, want_level(r), sb_t, gv_t, gb_t,
                                  prefer_max=want_max) or want_level(r))
        native = floor_native_hp(bosses, level, sb_t)
        if not native.get("verified") or native.get("native_hp") is None:
            _hp_fit_cache[key] = None
            return None
        required_c86 = float(fmt(solve_hp_correction(
            target, float(tmpl_rn[100]) / 60.0,
            float(native["native_hp"]))))
        try:
            strategy = floor_hp_scaling_strategy(
                bosses, native, gb_t, bl_t, level,
                required_c86=required_c86,
                deep=is_deep_round(r, args.rounds),
                code_references=code_refs)
        except ValueError as exc:
            _hp_fit_rejects[key] = str(exc)
            _hp_fit_cache[key] = None
            return None
        metrics = {
            "level": level, "native": native,
            "required_c86": required_c86,
            "baseline_c86": float(strategy["baseline_c86"]),
            "baseline_scale": float(strategy["baseline_scale"]),
            "hp_channel": strategy["channel"],
            "hp_family": strategy["family"],
            "selected_levels": strategy["selected_levels"],
        }
        _hp_fit_cache[key] = metrics
        return metrics

    def hp_curve_fit_pick(current: dict, r: int, target: float,
                          field_needed: int = 0, *,
                          element_required: bool = False,
                          carrier_required: bool = False,
                          pinned_boss: str | None = None,
                          pinned_terrain: bool = False) -> dict:
        """数值/领域不合规时重排，并优先保住可挂属性免疫的实际载体。"""
        current_metrics = hp_pick_metrics(current, r, target)
        current_key = (str(current["field"]), r, round(float(target), 6))
        current_hp_reject = _hp_fit_rejects.get(current_key)
        if current_hp_reject and "identity-locked" in current_hp_reject:
            log(f"[HP重排] round={r} reject="
                f"{','.join(map(str, current.get('bosses') or []))} "
                f"reason={current_hp_reject}")
        def carrier_ok(pick: dict, *, preserve_mix: bool = True) -> bool:
            bosses = list(pick.get("bosses") or [])
            target = next((b for b in bosses if b in belem_map), None)
            if target is None:
                return False
            # 候选扫描只读判据，不写 caster_blocked；真正选中后 field_caps()
            # 会登记门禁理由。否则扫描几百个候选会把未使用场地污染进最终报告。
            return caster_carrier_block(
                (current["field"] if (preserve_mix
                                      and current.get("_mix_terrain_entry"))
                 else pick["field"]),
                bosses, fd_t, zone_t, phase_linked, gb_t,
                refs=code_refs) is None

        def element_carrier_block(pick: dict, metrics: dict | None, *,
                                  preserve_mix: bool = True) -> str | None:
            if metrics is None:
                return "没有可审计的 HP/等级证据"
            bosses = list(pick.get("bosses") or [])
            field_id = (current["field"] if (preserve_mix
                                              and current.get("_mix_terrain_entry"))
                        else pick["field"])
            status = carrier_status(
                field_id, bosses, int(metrics["level"]), record=False)
            return None if status["element"] else str(status["element_reason"])

        def acceptable(pick: dict, metrics: dict | None, *,
                       preserve_mix: bool = True) -> bool:
            if metrics is None:
                return False
            if ((field_needed or carrier_required)
                    and not carrier_ok(pick, preserve_mix=preserve_mix)):
                return False
            if preserve_mix and current.get("_mix_terrain_entry"):
                # HP 重排不得把混搭层偷换回原场地；候补 boss
                # 也必须通过原有移植白名单，否则会把专用骨架塞进通用场地。
                strict, safe_set = load_transplant_policy()
                bosses = list(pick.get("bosses") or [])
                # c86-window 内的 identity-locked general 仍是合格的原味
                # 候选，但绝不能借 HP donor 重排进入已克隆的异地 zone。
                # Whole-field fallback (preserve_mix=False) remains legal.
                identity_block = identity_locked_boss_reason(
                    bosses, code_references=code_refs)
                if (identity_block
                        or len(bosses) != int(current.get("_mix_slot_count") or 0)
                        or (strict and not all(b in safe_set for b in bosses))
                        or any(is_special_boss(b, special_bosses) for b in bosses)):
                    return False
            if (args.rounds == 30 and is_deep_round(r, args.rounds)
                    and not metrics["native"].get("absolute_verified")):
                return False
            return True

        current_ok = acceptable(current, current_metrics)
        current_element_block = (element_carrier_block(current, current_metrics)
                                 if element_required else None)
        if current_ok:
            if not element_required or current_element_block is None:
                return current
            if pinned_boss:
                raise RuntimeError(
                    f"第{r}战钉选 boss {pinned_boss} 与属性免疫冲突:"
                    f"{current_element_block}; 显式 boss/诅咒均不允许静默改派")
            log(f"[HP重排] round={r} 工坊属性免疫要求保留载体，"
                f"当前 {current['field']} 不适用({current_element_block}); 搜索替代 boss")
        elif pinned_boss:
            # 显式 boss 是工坊硬约束；不能为满足平坦 HP 或领域槽而暗换成另一只。
            # 若还同时钉了属性免疫，优先把真实载体阻断理由报给作者。
            if current_hp_reject and "identity-locked" in current_hp_reject:
                raise RuntimeError(
                    f"第{r}战钉选 boss {pinned_boss} HP 无法实现:"
                    f"{current_hp_reject}; 显式 pin 不允许暗换 boss")
            why = (current_element_block
                   or ("该 boss 没有 general_boss c109 条件载体"
                       if carrier_required else "该 boss 无法满足本层 HP/领域硬闸"))
            raise RuntimeError(
                f"第{r}战钉选 boss {pinned_boss} 与属性免疫冲突:{why}; "
                "显式 boss/诅咒均不允许静默改派")

        registry: dict[str, dict] = {}

        def add(field: str, label: str, thumb: str = "", bgm=None) -> None:
            if field in registry:
                return
            bosses, _ = _zone_pick(field)
            if not bosses or not _pool_safe(bosses):
                return
            rep = field_gate(field)
            if not rep["ok"]:
                return
            disp = "、".join(dict.fromkeys(
                str(_boss_names.get(b, b)).split("/")[0] for b in bosses))
            registry[field] = {
                "field": field, "bosses": bosses,
                "thumb": thumb or thumb_map.get(field, ""), "bgm": bgm,
                "label": f"HP重排·{label}·{disp or field}",
            }

        for source_label, entries in src.items():
            for entry in entries:
                add(str(entry["field"]), source_label,
                    str(entry.get("thumb") or ""), None)
        for field, line, _bosses in tower_master:
            fc = cb._cols(line)
            add(str(field), "塔", thumb_map.get(field, ""),
                fc[1] if len(fc) > 1 else None)
        if args.rounds == 30:
            for field in (EARLY_HP_FALLBACK_FIELDS_30
                          + MID_HP_ANCHOR_FIELDS_30
                          + DEEP_HP_ANCHOR_FIELDS_30):
                add(field, "血量保底")

        zkeys = set(map(str, gz_t))
        def collect_ranked(*, allow_quota_reuse: bool = False,
                           preserve_mix: bool = True,
                           element_only: bool = False) -> list[tuple]:
            found: list[tuple] = []
            for candidate in registry.values():
                bosses = candidate["bosses"]
                if r >= 3 and any(is_minion_boss(b, zkeys) for b in bosses):
                    continue
                if (not allow_quota_reuse
                        and not all(_quota_left(k) for k in name_keys(bosses))):
                    continue
                metrics = hp_pick_metrics(candidate, r, target)
                if not acceptable(candidate, metrics, preserve_mix=preserve_mix):
                    continue
                metrics = dict(metrics)
                metrics["element_immunity_block"] = element_carrier_block(
                    candidate, metrics, preserve_mix=preserve_mix)
                scale = (float(metrics["baseline_scale"])
                         if metrics["hp_channel"] == "boss_level"
                         else float(metrics["baseline_c86"]))
                # general c2 通道优先；其次绝对证据/新面孔/较小的伸缩幅度。
                score = (
                    0 if metrics["hp_channel"] == "boss_level" else 1,
                    0 if metrics["native"].get("absolute_verified") else 1,
                    1 if set(bosses) & recent_bosses else 0,
                    abs(math.log(scale)),
                    candidate["field"],
                )
                found.append((score, candidate, metrics))
            if element_only:
                preferred, downgraded = prefer_element_immunity_hp_candidates(found)
                found = [] if downgraded else preferred
            return prefer_non_threat_candidates(
                found, r, args.rounds, lambda item: item[1]["bosses"],
                high_threat_prefixes, high_threat_exact)

        def collect_pipeline(*, element_only: bool) -> tuple[list[tuple], bool, str | None]:
            """完整跑一次严格/mix/短塔配额管线；元素优先失败后才跑普通管线。"""
            found = collect_ranked(element_only=element_only)
            whole_field_fallback = False
            quota_reuse_scope = None
            if (not found and current.get("_mix_terrain_entry")
                    and not pinned_terrain):
                # 严格移植白名单没有 donor 时，完整尝试安全原场地；元素池与
                # 普通池各自跑完这条链，不能看见一个不合格 donor 就提前降级。
                found = collect_ranked(
                    preserve_mix=False, element_only=element_only)
                if not found:
                    found = collect_ranked(
                        allow_quota_reuse=True, preserve_mix=False,
                        element_only=element_only)
                whole_field_fallback = bool(found)
            if not found and (args.rounds != 30 or args.mix):
                # 任意塔高的旧行为是“池子枯竭才允许重复”。30 层成品塔
                # 候选足够，仍严格保持配额；短塔不因固定锦标预留而无解。
                found = collect_ranked(
                    allow_quota_reuse=True, element_only=element_only)
                if found:
                    quota_reuse_scope = "混搭池" if args.mix else "短塔"
            return found, whole_field_fallback, quota_reuse_scope

        # HP 确需重排时，随机诅咒也优先获得可挂属性免疫的载体；工坊钉选则
        # 额外让“HP 已合格但载体不合格”的当前 boss 进入同一条搜索链。
        prefer_element = element_required or not carrier_required
        ranked, mix_whole_field_fallback, quota_reuse_scope = collect_pipeline(
            element_only=prefer_element)
        if not ranked:
            scope = ("工坊钉选属性免疫" if element_required else
                     ("工坊钉选 c109 条件" if carrier_required else
                      "随机属性免疫软约束"))
            if current_ok and element_required:
                # 用户规格明确要求软约束耗尽后回退原逻辑，但必须留痕；显式
                # pinned_boss 的冲突已在上方硬失败，不会走到这里吞掉两份 pin。
                why = current_element_block or "候选池没有实际 c109/c36 合格载体"
                log(f"[HP重排] round={r} {scope}无合格载体候选，"
                    f"已保留当前 boss；后续诅咒门禁将明确 redraw({why})")
                return current
            ranked, mix_whole_field_fallback, quota_reuse_scope = collect_pipeline(
                element_only=False)
            log(f"[HP重排] round={r} {scope}无合格载体候选，已降级为普通 HP 重排；"
                "后续诅咒门禁将 redraw")
        if not ranked:
            got = ("无原生 HP 证据" if current_metrics is None
                   else (f"boss_level×{current_metrics['baseline_scale']:g}"
                         if current_metrics["hp_channel"] == "boss_level"
                         else f"standard c86={current_metrics['baseline_c86']:g}"))
            raise RuntimeError(
                f"第{r}战当前候选{got}且正式池没有可伸缩 general / "
                f"c86 {STANDARD_C86_LIMITS[0]:g}~{STANDARD_C86_LIMITS[1]:g} 的 standard 替代 boss")
        if quota_reuse_scope:
            log(f"[HP重排] round={r} 唯一配额候选耗尽，"
                f"按旧池规则允许{quota_reuse_scope}重用")
        ranked.sort(key=lambda item: item[0])
        # 在同等优质的前八项中保留 seed 随机性；窗口、证据、去重仍是硬条件。
        _score, chosen, chosen_metrics = ranked[rng.randrange(min(8, len(ranked)))]
        old = ("无证据" if current_metrics is None
               else (f"boss_level×{current_metrics['baseline_scale']:g}"
                     if current_metrics["hp_channel"] == "boss_level"
                     else f"c86={current_metrics['baseline_c86']:g}"))
        new = (f"boss_level×{chosen_metrics['baseline_scale']:g}"
               if chosen_metrics["hp_channel"] == "boss_level"
               else f"c86={chosen_metrics['baseline_c86']:g}")
        log(f"[HP重排] round={r} {current['field']}({old}) -> "
            f"{chosen['field']}({new})")
        if current.get("_mix_terrain_entry") and not mix_whole_field_fallback:
            # 保留已选地形，只把混搭 zone 的 boss donor 换成可行候选。
            # 原 donor 之前已从 tower 移除；现在没用上就必须归还，
            # 否则一次重排会吞三个池条目并留下孤儿克隆。
            frow = fd_t.get(current["field"])
            fc = cells(frow) if isinstance(frow, (str, bytes, bytearray)) else []
            if len(fc) <= 2 or not isinstance(zone_t.get(fc[2]), dict):
                raise RuntimeError(f"第{r}战混搭 HP 重排找不到已克隆 zone")
            zone_t[fc[2]] = swap_zone_bosses(zone_t[fc[2]], chosen["bosses"])
            realized_bosses = zone_single_bosses(zone_t[fc[2]])
            if realized_bosses != list(chosen["bosses"]):
                raise RuntimeError(
                    f"第{r}战混搭 HP 重排实体不一致:"
                    f"donor={chosen['bosses']},realized={realized_bosses}")
            old_donor = current.get("_mix_boss_entry")
            if (isinstance(old_donor, tuple) and old_donor not in tower
                    and old_donor[0] != chosen["field"]):
                tower.append(old_donor)
            current["bosses"] = realized_bosses
            current["elem_override"] = (
                elem_map.get(chosen["field"])
                if elem_map.get(chosen["field"]) is not None else
                next((belem_map.get(b) for b in chosen["bosses"]
                      if belem_map.get(b) is not None), None))
            current["label"] = (
                f"拼·{','.join(chosen['bosses'])} @ {current.get('boost_field')}"
                f"（HP重排:{chosen['field']}）")
            current["_mix_boss_entry"] = next(
                (e for e in tower if e[0] == chosen["field"]), None)
            for entry in list(tower):
                if entry[0] == chosen["field"]:
                    tower.remove(entry)
                    break
            return current
        if current.get("_mix_terrain_entry") and mix_whole_field_fallback:
            frow = fd_t.pop(current["field"], None)
            fc = cells(frow) if isinstance(frow, (str, bytes, bytearray)) else []
            if len(fc) > 2:
                zone_t.pop(fc[2], None)
            for released in (current.get("_mix_terrain_entry"),
                             current.get("_mix_boss_entry")):
                if isinstance(released, tuple) and released not in tower:
                    tower.append(released)
            log(f"[HP重排] round={r} --mix 无兼容的安全 HP donor，"
                f"撤销克隆并退回原场地 {chosen['field']}")
        for entry in list(tower):
            if entry[0] == chosen["field"]:
                tower.remove(entry)
                break
        return chosen

    quest_rows: dict[str, list[str]] = {}
    forged_pubs: set[str] = set()
    immunity_programs: dict[str, list] = {}
    plan = {} if args.ignore_plan else layout_plan()
    if plan.get("stages") or plan.get("floors"):
        print(f"[工坊] 布局计划生效:阶段 {len(plan.get('stages') or [])} 段,"
              f"显式指定 {len(plan.get('floors') or {})} 层")
    plan_lines = []
    if args.mix and len(tower) < args.rounds * 2 + 1:
        print(f"[ERR] --mix 每层耗两个塔楼层,塔池 {len(tower)} < {args.rounds}×2+1")
        return 1
    # ---- 固定位 boss 预登记配额(2026-07-29 交叉核查抓到的真 bug)----
    # 楼层按 r 升序生成、`used_counts` 在**选完之后**才写,所以塔腰固定位(菲诺梅那)
    # 之前的锚位取候选时它还没占配额 —— 而 `steampunk_another` 本身**仍是领主战(44)
    # 和降临讨伐(36)两个池的成员**(lv100,四道筛子全刷不掉它),于是 30 层塔的
    # 第 6 战领主战锚位可以把它抽走,和第 15 战固定位撞成同一个 boss 出两次
    # (1.4.238 实际发生过;seed 20260812+4 可复现)。
    # 修法:固定位的 boss 在循环**开始前**就登记配额,让随机锚位天然避开。
    for _fixed_field, _lab in ((PHENO_FIELD, "机工神兵"), (DRAGON_FIELD, "终始之龙")):
        _live_fixed = [rr for rr, lab in schedule.items()
                       if lab == _lab]
        if _live_fixed:
            _fb, _ = _zone_pick(_fixed_field)
            for _k in name_keys(_fb):
                used_counts[_k] = used_counts.get(_k, 0) + 1
    # 中段/深层锚进入独立“未来预留”，防止浅层提前抽走；到映射轮次先释放，
    # 只有实际选中才进入 used_counts。不能直接预加 used_counts，否则未采用/被 pin
    # 绕开的锚会形成幽灵占用，实际锚还会被重复计数。
    for _rr in range(1, args.rounds + 1):
        _af = (mid_hp_anchor_field(_rr, args.rounds)
               or deep_hp_anchor_field(_rr, args.rounds))
        if _af:
            _ab, _ = _zone_pick(_af)
            for _k in name_keys(_ab):
                future_anchor_counts[_k] = future_anchor_counts.get(_k, 0) + 1

    tower_bosses: list[str] = []
    floor_recs: list[dict] = []
    mix_applied_rounds: list[int] = []
    for r in range(1, args.rounds + 1):
        label = schedule.get(r)
        forced = (((plan.get("floors") or {}).get(str(r))) or {}) if not args.ignore_plan else {}
        pin_t, pin_b = forced.get("terrain"), forced.get("boss")
        mapped_anchor = (mid_hp_anchor_field(r, args.rounds)
                         or deep_hp_anchor_field(r, args.rounds))
        if mapped_anchor:
            _mapped_bosses, _ = _zone_pick(mapped_anchor)
            for _k in name_keys(_mapped_bosses):
                left = future_anchor_counts.get(_k, 0) - 1
                if left > 0:
                    future_anchor_counts[_k] = left
                else:
                    future_anchor_counts.pop(_k, None)
        st_tier, st_mult = plan_tier_for(plan, r, round_tier(r))
        _target_dps = configured_target_dps(
            r, args.rounds, hp_base, hp_growth, st_mult, ramp=args.ramp)
        if r == 1 and not args.ramp:
            _target_dps = WARMUP_TARGET_DPS
        field_needed = required_field_slots(r, args.rounds) if st_tier == "hell" else 0
        if label and not (pin_t or pin_b):
            pick = PICKERS[label]()
        elif args.mix or pin_t or pin_b:
            pick = mix_pick(r, pin_t, pin_b)
            if pick is None and (pin_t or pin_b):
                print(f"[ERR] 第{r}战钉选失败(terrain={pin_t} boss={pin_b}),拒绝产出")
                return 1
            pick = pick or tower_pick(r)
        else:
            pick = tower_pick(r)
        _element_required = element_immunity_requested(forced)
        _carrier_required = hard_condition_carrier_requested(forced)
        # 钉地形只锁地形，不锁 donor：仍走 HP/属性载体重排，并在混搭 zone 内
        # 原地换 boss。钉 boss 则保持硬约束；与钉选属性免疫冲突时明确失败，
        # 绝不能成功产出后把「元素禁壁」随机替换掉。
        if r > 1 and (not pin_b or _element_required or _carrier_required):
            try:
                pick = hp_curve_fit_pick(
                    pick, r, _target_dps, field_needed,
                    element_required=_element_required,
                    carrier_required=_carrier_required,
                    pinned_boss=(str(pin_b) if pin_b else None),
                    pinned_terrain=bool(pin_t))
            except RuntimeError as exc:
                print(f"[ERR] {exc}")
                return 1
        if args.test_field == r and label is None:
            tries = 0
            while not field_caps(pick["field"], pick["bosses"])["boss"] and tower and tries < 30:
                pick = tower_pick(r)
                tries += 1
        _high_threat = is_high_threat_bosses(
            pick.get("bosses") or [], high_threat_prefixes, high_threat_exact)
        pick["high_threat"] = _high_threat
        if _high_threat:
            log(f"[高威胁] round={r} bosses={','.join(pick.get('bosses') or [])} "
                "禁时限/禁高档属性墙/诅咒HP≤1.5")
        tower_bosses += pick["bosses"]
        for _k in name_keys(pick["bosses"]):
            used_counts[_k] = used_counts.get(_k, 0) + 1
        row = list(tmpl_r1 if r == 1 else tmpl_rn)
        row[0] = str(700099000 + r)
        row[1] = "1"
        row[2] = str(r)
        if r > 1:
            row[9] = "16"
            row[10] = EVENT_ID
            row[11] = ""
            row[12] = str(r - 1)
            row[13] = str(700099000 + r - 1)
        bh, ba = (SRC_BOOST.get(label, (1.0, 1.0)) if label
                  else tower_area_boost(pick.get("boost_field") or pick["field"]))
        _lv = int(resolve_level(pick["bosses"], want_level(r), sb_t, gv_t,
                                gb_t, prefer_max=want_max) or want_level(r))
        pick["level"] = _lv
        # 该层有没有可归一的基数?standard 表 boss 查不到 → 归一化不生效,
        # 拿到的是裸曲线值,真实伤害无上界保证(2026-07-30 审计盲区实锤)
        _anchor = stat_anchor(pick["bosses"], _atk_med, "atk", _lv)
        _hp_anchor = stat_anchor(pick["bosses"], _hp_med, "hp", _lv)
        # HP 按族分治：general 必须是全层纯 Hit-HP general，主伸缩落 clone
        # boss_level.c2；standard 只允许 c86±10% 微调；混族/Fix 一律重抽。
        _native_hp = floor_native_hp(pick["bosses"], _lv, sb_t)
        try:
            _base_duration_s = float(row[100]) / 60.0
        except (TypeError, ValueError):
            print(f"[ERR] 第{r}战模板 c100 时限不可解析:{row[100]}")
            return 1
        if not math.isfinite(_base_duration_s) or _base_duration_s <= 0:
            print(f"[ERR] 第{r}战模板时限非法:{_base_duration_s}s")
            return 1
        # 基础数值归一:按 boss 基数相对同曲线组中位数反向补偿(2026-07-29 用户需求)
        if args.normalize:
            nh, na = stat_normalize(pick["bosses"], _hp_med, _atk_med,
                                    args.normalize_min, args.normalize_max, _lv,
                                    {"hp": args.normalize_hp, "atk": args.normalize_atk},
                                    {"atk": args.normalize_atk_max})
            bh, ba = bh * nh, ba * na
            pick["norm"] = (nh, na)
        caps = field_caps(pick["field"], pick["bosses"], _lv)
        _runtime_kwargs = {}
        _hp_strategy = None
        if _native_hp.get("verified"):
            _required_c86 = float(fmt(solve_hp_correction(
                _target_dps, _base_duration_s,
                float(_native_hp["native_hp"]))))
            try:
                _hp_strategy = floor_hp_scaling_strategy(
                    pick["bosses"], _native_hp, gb_t, bl_t, _lv,
                    required_c86=_required_c86,
                    deep=is_deep_round(r, args.rounds),
                    code_references=code_refs)
            except ValueError as exc:
                print(f"[ERR] 第{r}战 HP 主通道不可实现:{exc}")
                return 1
            _baseline_c86 = float(_hp_strategy["baseline_c86"])
            _baseline_true_hp = (_target_dps * _base_duration_s
                                 if _hp_strategy["channel"] == "boss_level"
                                 else _true_hp_at_c86(_native_hp, _baseline_c86))
            _runtime_kwargs = {
                "baseline_c86": _baseline_c86,
                "c86_limits": ((1.0, 1.0)
                               if _hp_strategy["channel"] == "boss_level"
                               else STANDARD_C86_LIMITS),
                "baseline_dps": _baseline_true_hp / _base_duration_s,
                "base_duration_s": _base_duration_s,
                "hp_channel": _hp_strategy["channel"],
            }
        elif not pick["bosses"]:
            # 第 1 战是唯一无 boss 血条的结构性例外，无法用相邻 boss 的反解比例
            # 事后放大 c86；否则抽到高墙时可能在诅咒已定案后才越窗，失去重抽机会。
            # 直接用它自己的旧曲线 c86 作透明代理，并在抽取阶段照常过最终窗口/时限闸。
            _proxy_baseline_c86 = float(fmt(
                hp_base * (hp_growth ** (r - 1)) * bh * st_mult))
            _runtime_kwargs = {
                "baseline_c86": _proxy_baseline_c86,
                "c86_limits": hp_correction_limits(r, args.rounds),
                "baseline_dps": _target_dps,
                "base_duration_s": _base_duration_s,
            }
            _hp_strategy = {
                "channel": "c86", "family": "no-boss",
                "baseline_c86": _proxy_baseline_c86, "baseline_scale": 1.0,
                "selected_levels": {},
            }
        _hp_family = (_hp_strategy["family"] if _hp_strategy else "unknown")
        try:
            curse = abyss_curses(
                r, args.rounds, rng, st_tier, caps, forced,
                no_base=_anchor is None, high_threat=_high_threat,
                **_runtime_kwargs)
        except (RuntimeError, ValueError) as exc:
            print(f"[ERR] 第{r}战诅咒组合无法满足硬闸:{exc}")
            return 1
        if _high_threat:
            _threat_why = high_threat_curse_conflict(curse.get("picks") or [])
            if _threat_why:
                print(f"[ERR] 第{r}战高威胁诅咒后置复核失败:{_threat_why}")
                return 1
        hard_damage = curse.get("damage_resistance") or []
        hard_elements = curse.get("element_resistance") or []
        hard_stacked = curse.get("stacked_resistance") or []
        hard_program = None
        if hard_damage or hard_elements or hard_stacked:
            if hard_elements:
                assert_element_immunity_runtime_safe(Q_QUEST, _lv)
            hard_program, hard_tree = immunity_program(
                hard_damage, hard_elements, hard_stacked)
            build_immunity_dsl_blob(hard_tree)       # dry-run 也做 AMF3/raw-deflate 往返门禁
            immunity_programs.setdefault(hard_program, hard_tree)
            forged_pubs.add(hard_program + ".action.dsl.amf3.deflate")
            if args.dump_immunity_dsl:
                print(f"[DSL] 第{r}战 {hard_program}")
                print(json.dumps(hard_tree, ensure_ascii=False, separators=(",", ":")))
        if args.test_field == r and not curse["casters"]:
            if caps["boss"]:
                _menu = field_menu_all()
                fm = _menu[rng.randrange(len(_menu))]
                apply_picks(curse, (curse.get("picks") or [])
                            + [{"name": "深渊法阵", "caster": fm,
                                "text": f"{fm[0]}·{fm[2]}"}], curse.get("combo"))
            else:
                why = caster_blocked.get(pick["field"])
                print(f"[WARN] 第{r}战无 general boss 载体,--test-field 落不了法阵"
                      + (f"(门禁:{why})" if why else ""))
        # test-field 会在 abyss_curses.finalize 之后补条目，重新给领域覆盖率记账。
        if curse.get("field_requested"):
            curse["field_applied"] = len(curse.get("casters") or [])
            curse["field_deficit"] = max(
                0, int(curse["field_requested"]) - int(curse["field_applied"]))
        if curse.get("field_deficit"):
            why = curse.get("field_deficit_reason") or caps.get("carrier_reason") \
                or "没有可用的 general_boss 领域载体"
            curse["field_deficit_reason"] = why
            log(f"[curse] round={r} field-underfill="
                f"{curse['field_applied']}/{curse['field_requested']} reason={why}")
            print(f"[ERR] 第{r}战领域保底欠配:"
                  f"{curse['field_applied']}/{curse['field_requested']} ({why})")
            return 1
        _hp_plan = None
        if _hp_strategy and _hp_strategy["channel"] == "boss_level":
            try:
                _hp_plan = general_hp_scale_plan(
                    pick["bosses"], _native_hp, gb_t, bl_t, _lv,
                    target_hp=_target_dps * _base_duration_s,
                    curse_hp=float(curse["hp"]),
                    code_references=code_refs)
            except ValueError as exc:
                print(f"[ERR] 第{r}战 boss_level.c2 伸缩计划失败:{exc}")
                return 1
        _final_native_hp = _native_hp
        if curse["gimmick"] or curse["casters"] or hard_program or _hp_plan:
            swaps: list[tuple[str, str]] = []
            action_programs: list[str] = []
            fields_tuned = False
            for fm_ in list(curse.get("casters") or []):
                action_program = str(fm_[1])
                fcat = fm_[3] if len(fm_) > 3 else "领域"
                tun = field_tuning()
                factor = float(tun.get("per", {}).get(action_program)
                               or tun.get("global", {}).get(fcat, 1) or 1)
                if abs(factor - 1.0) > 1e-9:
                    # 缩放标注挂在法阵条目自己的 text 上,降档闸重渲 desc 时不会丢
                    for _c in curse.get("picks") or []:
                        if (_c.get("caster")
                                and str(_c["caster"][1]) == str(fm_[1])):
                            _c["text"] += f"×{factor:g}"
                    fields_tuned = True
                    if args.write:
                        import wf_field_catalog as wfc
                        action_program = wfc.forge(action_program, scale=factor)
                if action_program.startswith("battle/action/enemy/action/mod_rogue/"):
                    forged_pubs.add(action_program + ".action.dsl.amf3.deflate")
                if action_program not in action_programs:
                    action_programs.append(action_program)
            if fields_tuned:
                apply_picks(curse, curse.get("picks") or [], curse.get("combo"))
            target = caps.get("element_target") if (action_programs or hard_program) else None
            carrier_clone = None
            if _hp_plan:
                source_codes = list(_hp_plan["final_leaves"])
                if target in source_codes:
                    source_codes.remove(target)
                    source_codes.insert(0, target)
                for index, source_code in enumerate(source_codes):
                    clone_code = (f"mod_rogue_boss{r}" if index == 0
                                  else f"mod_rogue_boss{r}_{index + 1}")
                    is_carrier = source_code == target
                    clone = make_caster_boss(
                        r, source_code,
                        action_programs=(action_programs if is_carrier else ()),
                        pre_action_program=(hard_program if is_carrier else None),
                        requires_element_resistance=(bool(hard_elements) and is_carrier),
                        enemy_level=_lv, clone_code=clone_code,
                        boss_level_leaf=_hp_plan["final_leaves"][source_code],
                        expected_selected_level=_hp_plan["selected_levels"][source_code])
                    if not clone:
                        print(f"[ERR] 第{r}战 general HP clone 失败:{source_code}")
                        return 1
                    swaps.append((source_code, clone))
                    if is_carrier:
                        carrier_clone = clone
            elif action_programs or hard_program:
                carrier_clone = (make_caster_boss(
                    r, target, action_programs=action_programs,
                    pre_action_program=hard_program,
                    requires_element_resistance=bool(hard_elements),
                    enemy_level=_lv) if target else None)
                if carrier_clone:
                    swaps.append((target, carrier_clone))
            play_field = gimmick_field(pick["field"], r,
                                       panels=curse["gimmick"], boss_swaps=swaps)
            if ((action_programs or hard_program) and not carrier_clone) or not play_field:
                print(f"[ERR] 第{r}战硬通道载体/field 克隆失败,拒绝保留虚假诅咒文案")
                return 1
            pick["play_field"] = play_field
            _play_row = fd_t.get(play_field)
            _play_cells = (cells(_play_row)
                           if isinstance(_play_row, (str, bytes, bytearray)) else [])
            _play_zone = zone_t.get(_play_cells[2]) if len(_play_cells) > 2 else None
            runtime_bosses = zone_single_bosses(_play_zone)
            swap_map = dict(swaps)
            expected_bosses = [swap_map.get(code, code) for code in pick["bosses"]]
            if runtime_bosses != expected_bosses:
                print(f"[ERR] 第{r}战最终 boss swap 不一致:"
                      f"expected={expected_bosses},actual={runtime_bosses}")
                return 1
            pick["runtime_bosses"] = runtime_bosses
            if hard_elements:
                # 最终实际 code = field 成功换入的 clone；再读一次克隆后 c36。
                actual_code = carrier_clone if play_field else target
                blocked = general_boss_element_immunity_block(gb_t, actual_code, _lv, gv_t)
                if blocked:
                    print(f"[ERR] 第{r}战属性免疫最终载体复核失败:{blocked}")
                    return 1
            if _hp_plan:
                _final_native_hp = floor_native_hp(runtime_bosses, _lv, sb_t, bl_t)
                if not _final_native_hp.get("verified"):
                    print(f"[ERR] 第{r}战最终 clone HP 不可审计:"
                          f"{_final_native_hp.get('reason') or 'unknown'}")
                    return 1
                actual_hp = _true_hp_at_c86(_final_native_hp, 1.0)
                if not math.isclose(actual_hp, float(_hp_plan["true_hp"]),
                                    rel_tol=1e-9, abs_tol=1.0):
                    print(f"[ERR] 第{r}战 clone c2 回读不一致:"
                          f"plan={_hp_plan['true_hp']},actual={actual_hp}")
                    return 1
        note = patch_common(row, f"{EVENT_NAME} 第{r}战", pick)
        quest_rows[str(r)] = row
        # ⚠ 数值列**不在这里落**:分位硬闸要看到全塔分布才能决定哪层降档,
        # 降档又会改回 hp/诅咒词条/副标题。所以先攒 record,闸门跑完再统一写。
        floor_recs.append({
            "r": r, "row": row, "pick": pick, "note": note, "bh": bh, "ba": ba,
            "curse": curse, "st_mult": st_mult, "no_base": _anchor is None,
            "anchor": _anchor, "hp_anchor": _hp_anchor,
            "hp_family": _hp_family, "native_hp": _native_hp,
            "final_native_hp": _final_native_hp,
            "hp_strategy": _hp_strategy, "hp_plan": _hp_plan,
            "target_dps": _target_dps,
            "base_duration_s": _base_duration_s,
            "funnel": any(fc.startswith(b) for b in pick["bosses"]
                          for fc in funnel_levels()),
        })
        if args.mix and pick.get("_mix_terrain_entry"):
            mix_applied_rounds.append(r)

    if args.mix:
        if not mix_applied_rounds:
            print("[ERR] --mix 实际拼接 0 层：严格 transplant_safe 白名单"
                  "与当前 HP/c86 窗口无交集，拒绝以全部原场地冒充混搭成功")
            return 1
        print(f"[MIX] 实际拼接 {len(mix_applied_rounds)} 层:"
              + ",".join(map(str, mix_applied_rounds)))

    # ---- 分位硬闸 + 数值列落表(2026-07-30)----
    curve_scale, band_log = enforce_atk_band(floor_recs, atk_base, atk_growth,
                                             args.rounds)

    native_errors = native_hp_coverage_errors(floor_recs)
    if native_errors:
        for error in native_errors:
            print(f"[ERR] {error}")
        return 1

    # ---- 任务 D：普通 general 真 HP 折进 clone boss_level.c2；quest c86 恒 1 ----
    # identity-locked general 与 standard 都只允许同 id 的 c86 0.9~1.1 微调；
    # 第1战无 boss 是唯一代理。
    hp_audits: list[dict] = []
    unresolved_hp: list[tuple[dict, float, float]] = []
    for frec in floor_recs:
        raw_c86 = float(fmt(hp_base * (hp_growth ** (frec["r"] - 1))
                            * frec["bh"] * frec["st_mult"]))
        frames = frec["curse"].get("time") or frec["row"][100]
        try:
            duration_s = float(frames) / 60.0
        except (TypeError, ValueError):
            print(f"[ERR] 第{frec['r']}战 c100 时限不可解析:{frames}")
            return 1
        if not math.isfinite(duration_s) or duration_s <= 0:
            print(f"[ERR] 第{frec['r']}战时限非法:{duration_s}s")
            return 1
        if frec.get("hp_plan"):
            plan = frec["hp_plan"]
            final_native = frec["final_native_hp"]
            baseline_true_hp = float(plan["baseline_true_hp"])
            true_hp = _true_hp_at_c86(final_native, 1.0)
            c2_evidence = {}
            for code in plan["final_leaves"]:
                c2_evidence[code] = {
                    "source": float(cells(bl_t[code])[2]),
                    "baseline": float(cells(plan["baseline_leaves"][code])[2]),
                    "final": float(cells(plan["final_leaves"][code])[2]),
                    "selected_general_level": plan["selected_levels"][code],
                }
            audit = {
                "r": frec["r"], "family": "general", "verified": True,
                "absolute_verified": bool(frec["native_hp"].get("absolute_verified")),
                "native": frec["native_hp"], "final_native": final_native,
                "base_duration_s": float(frec["base_duration_s"]),
                "duration_s": duration_s,
                "target_dps": float(frec["target_dps"]),
                "curse_hp": float(frec["curse"]["hp"]),
                "baseline_c86": 1.0, "c86": 1.0,
                "baseline_true_hp": baseline_true_hp, "true_hp": true_hp,
                "baseline_dps": baseline_true_hp / float(frec["base_duration_s"]),
                "realized_dps": true_hp / duration_s,
                "raw_c86": raw_c86,
                "family_scale": float(plan["baseline_scale"]),
                "boss_level_c2": c2_evidence,
            }
            frec["hp_audit"] = audit
            hp_audits.append(audit)
        elif frec["native_hp"].get("verified"):
            audit = solve_floor_hp_record(
                frec["r"], args.rounds, frec["native_hp"],
                base_duration_s=frec["base_duration_s"],
                duration_s=duration_s, curse_hp=frec["curse"]["hp"],
                raw_c86=raw_c86,
                family=frec["hp_family"], target=frec["target_dps"])
            frec["hp_audit"] = audit
            hp_audits.append(audit)
        else:
            unresolved_hp.append((frec, raw_c86, duration_s))

    # 第 1 战固定为纯小怪房，没有 boss 血条；用户给定公式只覆盖 29 个 boss 层。
    # 对这类层保留可见的旧曲线代理，并在抽诅咒时就用同一个值过窗口门禁；
    # DPS 只记为目标估算、verified=false，报告不得冒充绝对血量验收。
    for frec, raw_c86, duration_s in unresolved_hp:
        baseline_c86 = raw_c86
        curse_hp = float(frec["curse"]["hp"])
        c86 = float(fmt(baseline_c86 * curse_hp))
        target = float(frec["target_dps"])
        baseline_true_hp = target * float(frec["base_duration_s"])
        true_hp = baseline_true_hp * curse_hp
        audit = {
            "r": frec["r"], "family": frec["hp_family"], "verified": False,
            "absolute_verified": False,
            "native": frec["native_hp"],
            "base_duration_s": float(frec["base_duration_s"]),
            "duration_s": duration_s, "target_dps": target,
            "curse_hp": curse_hp,
            "baseline_c86": baseline_c86, "c86": c86,
            "baseline_true_hp": baseline_true_hp, "true_hp": true_hp,
            "baseline_dps": target, "realized_dps": true_hp / duration_s,
            "raw_c86": raw_c86, "family_scale": 1.0,
            "proxy_round": None, "warmup": frec["r"] == 1,
        }
        frec["hp_audit"] = audit
        hp_audits.append(audit)

    # 作者末层带是 hell 默认的验收锚；显式改 --hp-* /
    # 其它难度时按同比缩放该带，不让“参数已生效”反被 hell 闸拒绝。
    _canonical_hp = (args.difficulty == "hell"
                     and args.hp_base is None and args.hp_growth is None)
    _last_target = next(a["target_dps"] for a in hp_audits
                        if a["r"] == args.rounds)
    _last_target_scale = float(_last_target) / TARGET_DPS_LAST
    _hp_last_band = (TARGET_DPS_LAST_BAND if _canonical_hp else
                     tuple(v * _last_target_scale for v in TARGET_DPS_LAST_BAND))
    hp_errors = hp_curve_errors(
        hp_audits, args.rounds, _hp_last_band, ramp=args.ramp)
    hp_errors += hp_short_time_errors(hp_audits)
    hp_errors += hp_correction_errors(hp_audits, args.rounds)
    if hp_errors:
        for error in hp_errors:
            print(f"[ERR] HP 曲线门禁:{error}")
        return 1

    for frec in floor_recs:
        r, row, curse = frec["r"], frec["row"], frec["curse"]
        audit = frec["hp_audit"]
        hp = fmt(audit["c86"])
        atk = fmt(frec["atk"])
        row[86], row[87], row[88] = hp, hp, hp           # hp 小怪/炮台/boss(小怪房也吃曲线)
        row[89], row[91] = atk, atk                      # atk 小怪/boss
        # 带 funnel 的层:炮台弹幕同吃 boss 倍率,观感全算在"boss 伤害"头上 → 单独降档
        row[90] = fmt(frec["atk"] * FUNNEL_ATK_SCALE) if frec["funnel"] else atk
        row[92] = row[93] = "1"                          # tp 小怪/炮台
        row[94] = str(curse["tp"]) if curse["tp"] else "1"   # boss 韧性(官方无尽先例×9)
        row[97] = str(curse["fever"]) if curse["fever"] else row[97]
        row[100] = str(curse["time"]) if curse["time"] else row[100]
        # 诅咒词条:battle_enemy_condition_1..5(c71-80)+ 副标题(c3)
        for slot in range(5):
            kind, strength = curse["conds"][slot] if slot < len(curse["conds"]) else ("(None)", "")
            row[71 + slot * 2] = kind
            row[72 + slot * 2] = strength
        row[3] = curse["desc"] if curse["desc"] else "(None)"
        pick = frec["pick"]
        eff = f" | {curse['desc']}" if curse["desc"] else ""
        # boss 层的 HP 已由 boss_level.c2（general）或反解 c86（standard）
        # 精确落表；旧 bh/HP normalize 只剩 raw 诊断量，不能再打印成“补偿”误导。
        if audit["family"] == "no-boss":
            boost = (f" 补偿hp×{frec['bh']:.2f}/atk×{frec['ba']:.2f}"
                     if (frec["bh"], frec["ba"]) != (1.0, 1.0) else "")
        else:
            boost = (f" 补偿atk×{frec['ba']:.2f}"
                     if frec["ba"] != 1.0 else "")
        if pick.get("norm") and pick["norm"] != (1.0, 1.0):
            if audit["family"] == "no-boss":
                boost += f"(含归一 ×{pick['norm'][0]:.2f}/×{pick['norm'][1]:.2f})"
            else:
                boost += (f"(HP归一raw×{pick['norm'][0]:.2f}未落表;"
                          f"ATK归一×{pick['norm'][1]:.2f})")
        fdisp = pick["field"] + (f"→{pick['play_field']}" if pick.get("play_field") else "")
        fun = f" 炮台atk×{row[90]}" if frec["funnel"] else ""
        hp_mark = ("绝对" if audit.get("absolute_verified") else
                   ("代理" if audit["verified"] else "估算/无boss"))
        plan_lines.append(f"  第{r}战 [{pick['label']}] lv{pick.get('level')} "
                          f"field={fdisp} hp×{hp} atk×{atk}{fun}{boost}"
                          f" 基线(c86={audit['baseline_c86']:g},"
                          f"HP={audit['baseline_true_hp'] / 1e8:.2f}亿,"
                          f"DPS={audit['baseline_dps']:,.0f}/s)"
                          f" 实战(HP={audit['true_hp'] / 1e8:.2f}亿,"
                          f"DPS={audit['realized_dps']:,.0f}/s,"
                          f"{audit['duration_s']:.0f}s,血咒×{audit['curse_hp']:g})"
                          f"[{hp_mark}]"
                          f"{frec['note']}{eff}")
    if band_log:
        plan_lines.append(f"  ---- 分位硬闸动作 {len(band_log)} 次 ----")
        plan_lines += [f"  {ln}" for ln in band_log]
    # ---- 数值带体检(发布前一眼看穿这座塔热不热)----
    _late = sorted(f["atk"] for f in floor_recs if f["r"] / args.rounds > BAND_FROM)
    _early = sorted(f["atk"] for f in floor_recs if f["r"] / args.rounds <= BAND_FROM)
    _hp = sorted(float(f["row"][88]) for f in floor_recs)
    _true_hp = sorted(float(f["hp_audit"]["true_hp"]) for f in floor_recs)
    _tdi = [f["anchor"][0] * f["atk"] / f["anchor"][1]
            for f in floor_recs if f["anchor"]]
    _lv = {}
    for f in floor_recs:
        _lv[f["pick"].get("level")] = _lv.get(f["pick"].get("level"), 0) + 1
    _bs = band_stats(_late)
    plan_lines.append(
        f"  [数值带] 中后段 col 中位 {_bs['median']:.2f}"
        f"/P90 {_bs['p90']:.2f}/max {_bs['max']:.2f}"
        f"(带 ≤{BAND_TARGET['median']}/≤{BAND_TARGET['p90']}/≤{BAND_TARGET['max']})"
        f" · 前段中位 {statistics.median(_early):.2f}"
        f" · hp col 中位 {statistics.median(_hp):.2f}/max {_hp[-1]:.2f}"
        f" · 真HP中位 {statistics.median(_true_hp) / 1e8:.2f}亿"
        + (f" · 真伤指数 max {max(_tdi):.2f}(闸 {TRUE_DMG_CAP})" if _tdi else "")
        + (f" · 曲线缩放 ×{curve_scale:.3f}" if curve_scale != 1.0 else ""))
    plan_lines.append("  [数值带] 敌等级:"
                      + " ".join(f"lv{k}×{v}" for k, v in sorted(_lv.items(),
                                                                 key=lambda kv: kv[0] or 0)))
    _verified_hp = [a for a in hp_audits if a["verified"]]
    _absolute_hp = [a for a in _verified_hp if a.get("absolute_verified")]
    _proxy_hp = [a for a in _verified_hp if not a.get("absolute_verified")]
    _general_audits = [a for a in _verified_hp if a["family"] == "general"]
    _identity_audits = [
        a for a in _verified_hp if a["family"] == "identity-locked"]
    _standard_audits = [a for a in _verified_hp if a["family"] == "standard"]
    _general_scale = [a["family_scale"] for a in _general_audits]
    _identity_c86 = [float(a["c86"]) for a in _identity_audits]
    _standard_c86 = [float(a["c86"]) for a in _standard_audits]
    _hp_first = next(a for a in hp_audits if a["r"] == 1)
    _hp_last = next(a for a in hp_audits if a["r"] == args.rounds)
    # “真 HP 占比”的分子分母都只用绝对证据；代理曲线层
    # 另报覆盖率，不得混进分母把“估算”写成“真 HP”。
    _std_hp = sum(a["true_hp"] for a in _absolute_hp
                  if a["family"] == "standard")
    _all_absolute_hp = sum(a["true_hp"] for a in _absolute_hp)
    if args.ramp:
        _hp_gate_summary = (
            f"基线首尾 DPS {_hp_first['baseline_dps']:,.0f}→"
            f"{_hp_last['baseline_dps']:,.0f} "
            f"({_hp_last['baseline_dps'] / _hp_first['baseline_dps']:.2f}×) · "
            f"第{args.rounds}战命中目标带 {_hp_last_band[0]:,.0f}~"
            f"{_hp_last_band[1]:,.0f}/s")
    else:
        _hp_gate_summary = (
            f"第1战热身 {_hp_first['baseline_dps']:,.0f}/s · "
            f"boss层 2~{args.rounds} 全部命中 {_hp_last_band[0]:,.0f}~"
            f"{_hp_last_band[1]:,.0f}/s")
    plan_lines.append(
        f"  [真HP门禁] 绝对 {len(_absolute_hp)} 层 / 代理 {len(_proxy_hp)} 层 / "
        f"无boss估算 {len(hp_audits) - len(_verified_hp)} 层 · "
        f"{_hp_gate_summary}")
    _std_c86_summary = (
        f"standard c86={min(_standard_c86):g}~{max(_standard_c86):g}"
        f"（门禁 {STANDARD_C86_LIMITS[0]:g}~{STANDARD_C86_LIMITS[1]:g}）"
        if _standard_c86 else "standard 0层")
    _identity_c86_summary = (
        f"identity-locked c86={min(_identity_c86):g}~{max(_identity_c86):g}"
        f"（门禁 {STANDARD_C86_LIMITS[0]:g}~{STANDARD_C86_LIMITS[1]:g}）"
        if _identity_c86 else "identity-locked 0层")
    plan_lines.append(
        f"  [实战诅咒] DPS "
        f"{min(a['realized_dps'] for a in hp_audits):,.0f}~"
        f"{max(a['realized_dps'] for a in hp_audits):,.0f}/s · "
        f"短时限高血量 0 层 · general c86=1"
        f"（boss_level.c2 主伸缩）· {_identity_c86_summary} · {_std_c86_summary}")
    plan_lines.append(
        f"  [按族分治] general {len(_general_audits)} 层 / "
        f"identity-locked {len(_identity_audits)} 层 / "
        f"standard {len(_standard_audits)} 层 · "
        + (f"general boss_level.c2 基线伸缩中位 ×"
           f"{statistics.median(_general_scale):.3f}"
           if _general_scale else "general 无可验层")
        + " · "
        + (_identity_c86_summary if _identity_c86
           else "identity-locked 无可验层")
        + " · "
        + (_std_c86_summary if _standard_c86 else "standard 无可验层")
        + (f" · standard 绝对真HP占比 {_std_hp / _all_absolute_hp:.1%}"
           if _all_absolute_hp else ""))
    _field_requested = sum(int(f["curse"].get("field_requested") or 0)
                           for f in floor_recs)
    _field_total = sum(int(f["curse"].get("field_applied") or 0)
                       for f in floor_recs)
    _field_quota_applied = sum(
        min(int(f["curse"].get("field_applied") or 0),
            int(f["curse"].get("field_requested") or 0))
        for f in floor_recs)
    _field_deficit_floors = [f for f in floor_recs
                             if f["curse"].get("field_deficit")]
    _deep_time = [f["r"] for f in floor_recs
                  if is_deep_round(f["r"], args.rounds)
                  and f["curse"].get("time") is not None]
    plan_lines.append(
        f"  [领域/时限] 领域保底完成 {_field_quota_applied}/{_field_requested} 个"
        f"（全塔实际 {_field_total} 个）· "
        f"欠配 {len(_field_deficit_floors)} 层"
        + ("(" + ",".join(str(f["r"]) for f in _field_deficit_floors) + ")"
           if _field_deficit_floors else "")
        + f" · 深层时限诅咒 {len(_deep_time)} 层")

    # 无尽档:folder 2 / round 0,修正曲线接管难度(quest 行修正=round-0 锚点)
    endless_pick = tower_pick()
    tower_bosses += endless_pick["bosses"]
    for _k in name_keys(endless_pick["bosses"]):
        used_counts[_k] = used_counts.get(_k, 0) + 1
    endless_row = list(tmpl_endless)
    endless_row[0] = str(700099000 + int(ENDLESS_KEY))
    endless_row[1] = "2"
    endless_row[2] = "0"
    rec = patch_common(endless_row, f"{EVENT_NAME} 无尽", endless_pick)
    quest_rows[ENDLESS_KEY] = endless_row
    plan_lines.append(f"  无尽 [{endless_pick['label']}] field={endless_pick['field']}{rec}(曲线抄 700007 现值)")

    _profile = "ramp" if args.ramp else "flat"
    _target_summary = (
        f"{_hp_first['target_dps']:,.0f}→{_hp_last['target_dps']:,.0f}"
        if args.ramp else
        f"boss层={_hp_last['target_dps']:,.0f};第1战热身={_hp_first['target_dps']:,.0f}")
    print(f"seed={args.seed} rounds={args.rounds} profile={_profile} "
          f"difficulty={args.difficulty or '(旧默认)'} curse={args.curse or '(随难度)'} "
          f"hp(raw)={fmt(hp_base)}×{fmt(hp_growth)}^r "
          f"targetDPS={_target_summary} "
          f"atk={fmt(atk_base)}×{fmt(atk_growth)}^r")
    print("\n".join(plan_lines))

    # ---- 硬门禁复核:构建产物(含克隆场/法阵 boss)全链可解析,任一悬空拒绝产出 ----
    # The final chain must see this build's in-memory Orochi clones.  A cached
    # store-wide code union can both miss a fresh parent and let the wrong
    # constructor table satisfy a duplicate code, so inject every exact special
    # table and validate the zone's (BossKind, code) pair.
    final_special_tables: dict[str, dict] = {}
    for logical in SPECIAL_BOSS_TABLES:
        short = Path(logical).name.removesuffix(".orderedmap")
        if logical == OROCHI:
            final_special_tables[short] = oro_t
            continue
        try:
            final_special_tables[short] = q.load_table(logical)
        except Exception:
            final_special_tables[short] = {}
    identity_clone_errors = [
        (clone, source, identity_locked_boss_reason(
            [source], code_references=code_refs))
        for clone, source in sorted(clone_sources.items())
        if identity_locked_boss_reason(
            [source], code_references=code_refs) is not None
    ]
    if identity_clone_errors:
        for clone, source, why in identity_clone_errors:
            print(f"[ERR] identity-locked source clone:{source}->{clone}: {why}")
        print("[ERR] identity-locked source 被写成 mod_rogue_boss*,拒绝产出")
        return 1
    print("[门禁] identity-locked source clone 0"
          f"（本轮审计 {len(clone_sources)} 个 mod_rogue_boss* 映射）")

    final_validation = boss_ref_validation_tables(
        standard_boss=sb_t, general_boss=gb_t,
        general_boss_variable=gv_t,
        special_tables=final_special_tables)
    reports = validate_built_rows(
        quest_rows, fd_t, zone_t,
        set(gb_t) | set(sb_t) | set(gz_t), set(gz_t),
        lv_ceil=sb_t, lv_floor=gv_t, lv_gb=gb_t,
        validation_tables=final_validation)
    broken = [r for r in reports if not r["ok"]]
    if broken:
        for r in broken:
            print(f"[ERR] 第{r['round']}战 field={r['field']} 引用悬空:"
                  + "; ".join(r["errors"]))
        print(f"[ERR] {len(broken)}/{len(reports)} 关解析链断裂,拒绝产出(未写入任何表)")
        return 1
    print(f"[门禁] {len(reports)} 关解析链复核通过(quest→field→zone→boss/zako 全可解析)")
    if caster_blocked:
        print(f"[门禁] 成对/分阶段 · 被代号引用的 boss 层已禁发深渊法阵"
              f"({len(caster_blocked)} 个场地):")
        for _f, _why in sorted(caster_blocked.items()):
            print(f"        {_f} — {_why}")

    if not args.write:
        print("[DRY-RUN] 未写入。加 --write 生效,--publish 顺带发 CDN。")
        return 0

    # 写 ② 层(save_table 自动备份)。written = 本次实际落盘的逻辑路径清单,
    # 发布清单/发布自检直接从它派生——"写了没发布"(C8601 key=mod_rogue_f9)从结构上封死。
    written: list[str] = []

    def save(logical: str, tree: dict) -> None:
        q.save_table(logical, tree)
        written.append(logical)

    # 先落未被任何表引用的 action 文件；全部成功后才写 general_boss/quest。
    # 临时文件与目标同目录,os.replace 原子切换,避免中断留下半截 deflate。
    for program, tree in sorted(immunity_programs.items()):
        logical = program + ".action.dsl.amf3.deflate"
        dst = q.store_path(logical)
        dst.parent.mkdir(parents=True, exist_ok=True)
        blob = build_immunity_dsl_blob(tree)
        tmp = dst.with_name(dst.name + ".tmp-wf-rogue-immunity")
        tmp.write_bytes(blob)
        os.replace(tmp, dst)
    if immunity_programs:
        print(f"[OK] 耐性 DSL 已写入 {len(immunity_programs)} 个 action")

    # Dependency-first save order: head rows before Orochi parent, then the
    # field/zone that references that parent, and only then quest rows.  Each
    # save_table is still a per-file operation; this is reference-safe ordering,
    # not a claim of cross-table disk transactionality.
    battle_values = {
        GENERAL_ZAKO: gz_t,
        ZAKO_LEVEL: zl_t,
        GENERAL_BOSS: gb_t,
        BOSS_LEVEL: bl_t,
        GENERAL_BOSS_VARIABLE: gv_t,
        ENEMY_WATCH: ew_t,
        OROCHI: oro_t,
        FIELD_DATA_T: fd_t,
        ZONE_T: zone_t,
    }
    battle_plan = rogue_battle_write_plan(
        gimmick_dirty=gim_dirty, caster_dirty=caster_dirty,
        orochi_dirty=orochi_dirty,
        enemy_watch_available=ew_t is not None)
    for logical in battle_plan:
        tree = battle_values.get(logical)
        if not isinstance(tree, dict):
            raise RuntimeError(f"battle write plan 缺内存表:{logical}")
        save(logical, tree)
    if caster_dirty:
        print("[OK] 法阵载体依赖已写入(zako + general boss 附表)")
    if orochi_dirty:
        print("[OK] 八岐父体整包已写入(head 依赖 → orochi parent)")
    if gim_dirty:
        print("[OK] 场地克隆已写入(field_data / zone)")

    ev[EVENT_ID] = join(ev_row, ev_bytes)
    save(Q_EVENT, ev)
    fo[EVENT_ID] = {"1": join(fo_row, fo_bytes), "2": join(fo_endless, fo_bytes)}
    save(Q_FOLDER, fo)
    qt[EVENT_ID] = {k: join(v, qt_bytes) for k, v in quest_rows.items()}
    save(Q_QUEST, qt)
    el = q.load_table(Q_LIST)
    el_bytes = isinstance(el[TEMPLATE_EVENT], bytes)
    el[EVENT_ID] = join(["11", EVENT_ID, EVENT_ID], el_bytes)
    save(Q_LIST, el)
    # 无尽修正曲线:抄 700007 无尽当前值(已是缓坡)→ [700099][2][99]
    corr = q.load_table(Q_CORR)
    src_curve = corr[TEMPLATE_EVENT]["4"]["8"]
    corr[EVENT_ID] = {"2": {ENDLESS_KEY: dict(src_curve)}}
    save(Q_CORR, corr)
    print("[OK] ②层五表已写入(rush_event / folder / quest / event_list / correction)")

    # 服务端 json
    quest_json_path = os.path.join(ROOT, "assets", "rush_event_quest.json")
    with open(quest_json_path, encoding="utf-8") as fh:
        quest_json = json.load(fh)
    tmpl_entry = quest_json[f"{TEMPLATE_EVENT}001"]
    for r in range(1, args.rounds + 1):
        entry = dict(tmpl_entry)
        entry["rushEventId"] = int(EVENT_ID)
        entry["rushEventFolderId"] = 1
        entry["rushEventRound"] = r
        quest_json[str(700099000 + r)] = entry
    endless_entry = dict(tmpl_entry)
    endless_entry["rushEventId"] = int(EVENT_ID)
    endless_entry["rushEventFolderId"] = 2
    endless_entry["rushEventRound"] = 0
    quest_json[str(700099000 + int(ENDLESS_KEY))] = endless_entry
    # 清掉多余轮(rounds 缩小时;99=无尽键不在范围内,rounds 上限 98)
    for r in range(args.rounds + 1, 99):
        quest_json.pop(str(700099000 + r), None)
    with open(quest_json_path, "w", encoding="utf-8") as fh:
        json.dump(quest_json, fh, ensure_ascii=False, indent=1)

    folder_json_path = os.path.join(ROOT, "assets", "rush_event_quest_folder.json")
    with open(folder_json_path, encoding="utf-8") as fh:
        folder_json = json.load(fh)
    # 保留自定义通关奖励(2026-07-28 起服务端 json 的 700099 奖励由用户定制,
    # 重摇只在条目缺失时才从模板补种)
    folder_json.setdefault(EVENT_ID, {"1": folder_json[TEMPLATE_EVENT]["1"]})
    with open(folder_json_path, "w", encoding="utf-8") as fh:
        json.dump(folder_json, fh, ensure_ascii=False, indent=1)
    print("[OK] 服务端 json 已写入(rush_event_quest / rush_event_quest_folder)——静态 import,须重启服务端")
    save_boss_history(tower_bosses)
    print(f"[历史] 本塔 {len(set(tower_bosses))} 个 boss 已记账(近 3 座塔降权去重)")

    # 发布清单 = 本次落盘清单 + 锻造 DSL,全部用完整逻辑路径(不依赖别名)
    pub_items = written + sorted(forged_pubs)
    pub_tables = ",".join(pub_items)
    if args.publish:
        r = subprocess.run([sys.executable, os.path.join(MOD_DIR, "wf_publish.py"),
                            "--tables", pub_tables],
                           cwd=ROOT)
        print(f"[PUBLISH] wf_publish 退出码 {r.returncode}")
        if r.returncode != 0:
            print("[ERR] 发布失败:表已写入 store 但 CDN 未更新,勿清进度/勿重启客户端,"
                  f"修复后补发:python mod-tools/wf_publish.py --tables {pub_tables}")
            return r.returncode
        problems = verify_cdn_chain(pub_items)
        if problems:
            for logical, why in problems:
                print(f"[ERR] 发布自检:{logical}: {why}")
            print(f"[ERR] 发布不完整({len(problems)}/{len(pub_items)} 个文件未上链),"
                  f"补发:python mod-tools/wf_publish.py --tables {pub_tables}")
            return 1
        print(f"[OK] 发布自检通过:{len(pub_items)} 个文件全部在 CDN 链上且字节一致")
    else:
        print(f"记得发布:python mod-tools/wf_publish.py --tables {pub_tables}")
    return 0


if __name__ == "__main__":
    # 塔名/日文 boss 标签含 GBK 不可编码字符；构建器也可被人工直接调用，
    # 不能只依赖服务端父进程的 `-X utf8`。
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

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
                                  c86-94 修正 = 缓坡(hp 0.5×1.185^r / atk 0.35×1.13^r)
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
from datetime import date
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 本脚本所在目录:主仓 = ROOT/mod-tools,平铺导出仓 = 仓根。工具自带的数据文件
# (rogue_*.json / work/)一律以此为基准,两种布局都能找到。
MOD_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MOD_DIR)
import wf_quest_lib as q          # noqa: E402
import wf_chain_build as cb       # noqa: E402

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


def _c8016_safe(bosses: list[str]) -> bool:
    return not any(b.startswith(p) for p in C8016_BLOCKED_BOSS_PREFIXES for b in bosses)


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
                      lv_gb: dict | None = None) -> dict:
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
            if code not in enemies and code not in special_boss_levels():
                out["errors"].append(
                    f"zone[{zkey}] wave {wk} c{i} boss 代号悬空:{code}"
                    "(不在 general_boss/standard_boss/general_zako,也无专用表)")
            elif level is not None and not boss_level_ok(code, level, lv_ceil,
                                                         lv_floor, lv_gb):
                # 等级可行性判定统一走 boss_level_ok(单一事实源,避免两处规则分叉;
                # 2026-07-29 关25 火废龙即因内联副本漏掉 gv 单档 100 规则而漏网)
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
                  lv_gb: dict | None) -> bool:
    """单 boss 在指定敌等级下能否解析(规则同 check_field_chain 的等级段)。"""
    # 召唤物先判:本体三表全绿也可能被自己的 funnel 拖崩(关14 实锤)
    if not boss_funnel_ok(code, level):
        return False
    # 专用表 boss(orochi/kraken/*_sphere/…)优先判定:它们不在三表并集里,
    # 等级档在自己表内,取"≤敌等级的最大档"(general 同款下取整)。
    # 只有 100 档的 boss ⇒ 敌等级须 ≥100(water_sphere@90 崩 / orochi_ex@100 通)。
    sp_entry = special_boss_levels().get(code)
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
    """曲线在指定等级的值;取 ≤level 的最大档(与客户端下取整一致)。查不到返回 None。"""
    tbl = growth_curves().get(kind, {}).get(name)
    if not isinstance(tbl, dict):
        return None
    keys = sorted((int(k) for k in tbl if str(k).isdigit()))
    usable = [k for k in keys if k <= level]
    if not usable:
        return None
    v = tbl.get(str(usable[-1]))
    return float(v) if isinstance(v, (int, float)) else None


_BASE_STATS: dict | None = None


def boss_base_stats() -> dict:
    """boss 代号 → {hp, atk, hpc, atkc};hp/atk = 基数×倍率,hpc/atkc = 修正曲线名。

    只认 `boss_level` 里能解析的行(511/543);standard 系等没有条目的返回缺省,
    归一化时按"无数据不动"处理。"""
    global _BASE_STATS
    if _BASE_STATS is None:
        out: dict = {}
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
                out[code] = {"hp": float(cs[2]) * float(cs[3]), "hpc": cs[4],
                             "atk": float(cs[8]) * float(cs[9]), "atkc": cs[10]}
            except ValueError:
                continue
        _BASE_STATS = out
    return _BASE_STATS


def true_stat(code: str, kind: str, level: int = 100) -> tuple[float, str] | None:
    """(该 boss 在 level 级的真实数值, 归一化分组键)。

    曲线**已知**(hit_hp_boss / _non_element / _funnel、atk_single/multi/...)时
    返回 `基数 × 曲线[level]`,分组键统一为 "*" —— 这批可以**跨曲线组直接比**。
    曲线未知(`hit_hp_correction_normal` 240 个、`_practice` 14 个、
    `atk_correction_normal` 254 个;客户端内置默认,读不到)时返回裸基数,
    分组键取曲线名 —— 只能组内相对归一。
    """
    s = boss_base_stats().get(code)
    if not s:
        return None
    base = s["hp"] if kind == "hp" else s["atk"]
    cname = s["hpc"] if kind == "hp" else s["atkc"]
    if base <= 0:
        return None
    mul = curve_value(kind, cname, level)
    if mul:
        return base * mul, "*"
    # 曲线未知(客户端内置默认):拿**同类里最常见的已知曲线**当代理,把它拉进同一个
    # 可比空间。⚠ 这是个**假设**,不是实锤——但不代理的话两组各用各的锚(一个是真实
    # 血量、一个是裸基数),单位都不一样,残差 379× 纯属构造出来的,比假设更糟。
    proxy = curve_value(kind, PROXY_CURVE[kind], level)
    return (base * proxy, "*") if proxy else (base, cname)


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
                   compress: dict | None = None) -> tuple[float, float]:
    """一层的 (hp 补偿, atk 补偿)。同曲线组中位数 ÷ 本层基数,夹在 [lo, hi]。

    一层多个 boss 时取**基数最大的那个**当代表(血最厚的决定这层的手感)。
    查不到基数(standard 系/专用表)返回 (1.0, 1.0) —— 无数据不瞎补。
    """
    compress = compress or COMPRESS_DEFAULT
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
        f = min(hi, max(lo, f))
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
    """一层写进 c89-91 的 atk 修正 —— 四道构建期硬闸依次夹。

    rec = {r, ba, curse, st_mult, no_base, anchor, hard_cap?}。
    纯函数:降档闸改完 curse 后原样重算即可,不留隐藏状态。"""
    curve = atk_base * (atk_growth ** (rec["r"] - 1)) * rec["ba"] * scale
    # ① 组合上限:曲线×来源补偿×攻击诅咒。单项不越界、乘起来越界的层靠这条压住
    cap = NOBASE_ATK_CAP if rec["no_base"] else ATK_COMBO_CAP
    val = min(curve * rec["curse"]["atk"], cap)
    val *= rec["st_mult"]                       # 工坊阶段乘区(hell ×1.15)
    # ② 真伤指数闸:原生 atk 高的 boss(青之女王≈中位 3 倍)col 合规≠每跳合规
    if rec["anchor"]:
        native, med = rec["anchor"]
        val = min(val, TRUE_DMG_CAP * med / native)
    # ③ 分位闸的逐层夹子(见 enforce_atk_band)
    val = min(val, rec.get("hard_cap", float("inf")))
    # ④ 全局兜底
    return min(val, ATK_MULT_CEILING)


def band_stats(cols: list[float]) -> dict:
    """col 分布的三个受检分位(P90 = 最近秩)。闸门与体检读数**共用**这一个口径,
    否则会出现"闸门说过了、体检说超了"的自相矛盾。"""
    s = sorted(cols)
    return {"median": statistics.median(s), "max": s[-1],
            "p90": s[min(len(s) - 1, math.ceil(0.9 * len(s)) - 1)]}


def band_violation(cols: list[float]) -> tuple[str, float] | None:
    """中后段 col 分布是否落进官方带 → (超标项, 实测值) 或 None。"""
    if not cols:
        return None
    got = band_stats(cols)
    for key in ("max", "p90", "median"):
        if got[key] > BAND_TARGET[key] + 1e-9:
            return key, got[key]
    return None


def enforce_atk_band(recs: list[dict], atk_base: float, atk_growth: float,
                     n: int) -> tuple[float, list[str]]:
    """全塔 col 分位硬闸 → (全局曲线缩放, 逐条降档日志)。

    ⚠ 这是**对任意 seed 的保证**,不是对某个 roll 手调:烈狱档 40% 层起 3 诅咒,
    重摇方差极大——交接文档对标时那一 roll 中位 1.46,下一 roll 就 2.91。
    收敛手段按治本程度:
      ① 最热层的攻击类诅咒降一档(2→1→0→摘除),desc 同步改,文案不骗人
      ② max 超标且该层已无攻击诅咒 → 只夹这一层(单点离群不该拖累全塔)
      ③ 中位/P90 超标且中后段已无攻击诅咒可降 → 说明**基础曲线本身太热**,
         全塔等比缩放(几何收敛),并在日志里提示该回头调 DIFF_PRESETS 端点
    """
    scale, log = 1.0, []

    def recalc() -> None:
        for rec in recs:
            rec["atk"] = solve_atk(rec, atk_base, atk_growth, scale)

    def has_atk(rec: dict) -> bool:
        return any(c.get("name") in ATK_CURSE_TIERS
                   for c in rec["curse"].get("picks") or [])

    recalc()
    for _ in range(600):
        late = [rec for rec in recs if rec["r"] / n > BAND_FROM]
        bad = band_violation([rec["atk"] for rec in late])
        if not bad:
            break
        key, got = bad
        top = max(late, key=lambda rec: (rec["atk"], rec["r"]))
        if key == "max":
            note = downgrade_atk_curse(top["curse"]) if has_atk(top) else None
            if note is None:
                top["hard_cap"] = BAND_TARGET["max"]
                note = f"无攻击诅咒可降 → 单层夹到 ×{BAND_TARGET['max']}"
            log.append(f"[分位闸] max={got:.2f} → 第{top['r']}战 {note}")
        else:
            hot = max((rec for rec in late if has_atk(rec)),
                      key=lambda rec: (rec["atk"], rec["r"]), default=None)
            if hot is not None:
                log.append(f"[分位闸] {key}={got:.2f} → 第{hot['r']}战 "
                           f"{downgrade_atk_curse(hot['curse'])}")
            else:
                scale *= 0.95
                log.append(f"[分位闸] {key}={got:.2f} 且中后段已无攻击诅咒可降 "
                           f"→ 全塔曲线 ×{scale:.3f}(该调 DIFF_PRESETS atk 端点了)")
        recalc()
    else:
        # 600 步还没收敛只可能是闸门写错了,宁可硬夹也不许把越界值发出去
        for rec in recs:
            if rec["r"] / n > BAND_FROM:
                rec["hard_cap"] = min(rec.get("hard_cap", float("inf")),
                                      BAND_TARGET["median"])
        recalc()
        log.append("[分位闸] ⚠ 未在 600 步内收敛,中后段全部硬夹到 "
                   f"×{BAND_TARGET['median']}(闸门逻辑有 bug,去查)")
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
                        lv_gb: dict | None = None) -> list[dict]:
    """构建产物(round → quest 行)逐关链检查;写入前调用,悬空即拒绝产出。

    lv_ceil=standard_boss / lv_floor=gv / lv_gb=general_boss,按每行 c95 查等级覆盖。"""
    reports = []
    for rk, row in rows.items():
        if len(row) > 98:
            level = int(row[95]) if len(row) > 95 and str(row[95]).isdigit() else None
            rep = check_field_chain(row[98], fd, zone, enemies, zakos, level=level,
                                    lv_ceil=lv_ceil, lv_floor=lv_floor, lv_gb=lv_gb)
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
                               lv_ceil=lv_ceil, lv_floor=lv_floor, lv_gb=lv_gb)


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


def zone_boss_slots(zn) -> list[set[str]]:
    """zone 嵌套 dict → 每个**已占用** boss 槽的代号集合(单人/多人列合并)。

    返回长度 = 该 zone 实际会出场的 boss 实体数(跨波次累加)。
    """
    out: list[set[str]] = []
    if not isinstance(zn, dict):
        return out
    for wrow in zn.values():
        if isinstance(wrow, dict):
            continue                    # 异形嵌套 zone,交给上层拒绝
        wc = cells(wrow)
        for a, b in ZONE_BOSS_SLOTS:
            codes = {wc[i] for i in (a, b)
                     if len(wc) > i and wc[i] not in ("", "(None)")}
            if codes:
                out.append(codes)
    return out


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
        for i in (24, 26, 28, 30, 32, 34):
            if len(wc) > i and wc[i] not in ("", "(None)"):
                wc[i] = bosses[bi % len(bosses)]
                if i in (24, 28, 32):
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


def caster_carrier_block(field_id: str, bosses: list[str],
                         fd_t: dict, zone_t: dict,
                         phase_set: frozenset[str] | None = None) -> str | None:
    """「深渊法阵」载体门禁:返回拒绝理由(None = 可以当载体)。

    法阵的施法载体 = 克隆该轮首只 general boss 并给它追加官方场程序
    (make_caster_boss)。两种情况必须拒发:
      ① 该层 zone 有 **多个 boss 实体** —— 只换得动一只,余下的仍指向原代号,
         成对 boss 从此各打各的;
      ② 该层 boss 属于官方**成对/分阶段族**(phase_linked_bosses)—— 即便这层
         只摆了一只,它的阶段转场仍按代号找同伴,克隆即断链。
    两条都是数据判据,不认名字(索拉斯/女王/机工神兵一视同仁)。
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


def _zone_pick(fdid: str) -> tuple[list[str], list[str]]:
    """field → (boss codes, zako codes),按 zone 波次列直读(不依赖名字表)。"""
    fd = _tbl("master/battle/field_data.orderedmap")
    zone = _tbl("master/battle/zone.orderedmap")
    frow = fd.get(fdid)
    if not frow:
        return [], []
    zn = zone.get(cb._cols(frow)[2])
    bosses, zakos = [], []
    if isinstance(zn, dict):
        for wrow in zn.values():
            wc = cb._cols(wrow)
            bosses += [wc[i + 1] for i in range(23, min(35, len(wc)), 2)
                       if wc[i] not in ("(None)", "") and wc[i + 1] not in ("(None)", "")]
            zakos += [wc[i] for i in range(2, min(22, len(wc)), 2)
                      if wc[i] not in ("(None)", "")]
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
#   · 官方**不靠 quest 修正抬难度**:各档中位数全是 1.0,难度压在 enemy_level 曲线上
#   · 最接近的官方连战(rush):**hp 修正堆到 100×,atk 只在 0.2–1.95** —— 堆血不堆刀
# 旧值 atk 终点 18.0 配上玻璃深渊 ×3.0 与 PLAN_TIERS ×1.15,末层写进 c89-91 的倍率
# 达 **62.1**,实测线上塔 atk 中位 8.92 / 最高 80.09,**比官方天花板高一个数量级**。
# 新端点把典型值拉回官方带内;血量端点不动(hp 侧我们中位 4.41/max 66.5 本来就在官方
# 带内,官方 lv100 max 133、官方 rush max 100)。
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
# hp 端点上调作难度补偿(用户 2026-07-30 授权「按官方 rush 把难度转向 hp/机制」):
# 官方 rush **hp 堆到 100×、atk 只在 0.2-1.95**,我们 hp max 才 12 左右,空间很大。
DIFF_PRESETS = {
    #            hp起  hp终   atk起 atk终  诅咒档
    "easy":     (0.3,  1.2,   0.3,  0.9,  "off"),
    "normal":   (0.5,  2.2,   0.5,  1.3,  "abyss"),
    "hell":     (0.9,  4.0,   0.8,  1.7,  "hell"),
    "gradient": (0.5,  2.6,   0.6,  1.5,  None),
}

# ---- atk 落表值的**构建期硬闸**(2026-07-30 玩家「连战 boss 伤害过高」审计后落地)----
# 审计实测(现役 249 塔):col 中位 2.91、中后段中位 4.03、20/30 层超官方全库第二名
# 1.8;同 field 锚点(白虎/圣诞魔像/菲诺梅那)= 把官方原版战斗做成 4.7~6.8 倍每跳。
# 上一轮只调 ceiling 的思路被证伪:ceiling 从未触发(最高 6.58 < 8.0),削不到中位。
# 所以闸门分四层,从治本到兜底:
#   ① 攻击类诅咒降档(ATK_CURSE_TIERS)—— 病灶:col>4 的层**全部**是攻击诅咒层
#   ② 组合上限:曲线×来源补偿×攻击诅咒 的乘积封顶(单层不许"基础高 + 诅咒顶格"双叠)
#   ③ 无基数层单独限幅 + 真伤指数闸(见 NOBASE_ATK_CAP / TRUE_DMG_CAP)
#   ④ 全塔分位硬闸(见 BAND_TARGET)——保证**任意 seed** 合规,不是对某个 roll 手调
# 写进 c89-91 的 atk 修正**硬上限**。官方全库最大 6.63(且是孤例,第二名 1.8)。
ATK_MULT_CEILING = 6.6
# 「曲线×来源补偿×归一化 × 攻击诅咒」的组合上限。单项都不越界、乘起来越界的层
# (第26战 基础2.99×逆鳞2.2=6.58)靠这条压住。
ATK_COMBO_CAP = 4.0
# standard 表 boss 无 boss_level 基数 → stat_normalize 返回 1.0(归一化不生效),
# 它们拿到的是**裸曲线值**,而原生数值不在审计视野内,真实伤害无上界保证。
# 这类层单独限幅,并禁掉攻击类诅咒(见 abyss_curses 的 no_base 参数)。
NOBASE_ATK_CAP = 1.5
# 真伤指数 = boss 原生 atk(该层等级)× 落表 col ÷ 同曲线组中位锚。
# col 合规 ≠ 真伤合规:第6战青之女王 col 只有 1.90,但原生 atk ≈ 中位 3 倍,
# 0.55 幂压缩没压平 → 真伤指数 5.62 = 全塔第一(隐形尖峰)。这条直接封每跳伤害。
TRUE_DMG_CAP = 4.0
# 带 funnel 的层:炮台弹幕同吃 boss 列倍率(第18战巫妖 4.68/第29战深渊之云 4.81),
# 玩家会把它算进"boss 伤害"。c90 相对 c91 降档。
FUNNEL_ATK_SCALE = 0.6
# 全塔 col 分位硬闸(中后段 = 进度 > BAND_FROM)。官方坐标系:lv100 档中位 1.0/
# P90 1.2/max 6.63(孤例)。超标即逐层降档重算,直到任意 seed 都落进带内。
BAND_FROM = 1 / 3
BAND_TARGET = {"median": 2.0, "p90": 3.0, "max": 6.0}
# 敌等级爬坡三段(--enemy-level ramp,默认)。官方 enemy_level 分布:lv80 是主流
# 难档(662 行 21.9%),lv100 只有 127 行(4.2%);atk_correction_curve 实解
# lv79=1.898 / lv89=1.992 / lv99=2.505 / lv100=3.267 —— lv100 是曲线悬崖顶,
# 全塔平坦 lv100 等于把 96% 官方内容不敢站的位置站满 30 层。
LEVEL_RAMP = (80, 90, 100)


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
    bad = sorted(k for k, s in signs.items() if len(s) > 1)
    if bad:
        return f"kind {bad} 同时有抗性/免疫和易伤(自相矛盾)"
    # ② 槽位与无解层判定都按**合并后**的条件算(同 kind 同号会被 merge_conds 收成一条)
    merged = merge_conds(picks)
    if len(merged) > 5:
        return "条件槽超 5(超出的会被静默截断)"
    immune = {k for k, v in merged if str(v) in ("1", "1.0")}
    if immune >= {"0", "1", "2", "3"}:
        return "四系伤害全免疫(无解层)"
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
    "嗜血狂潮": (1.3, 1.5, 1.7),
    "深渊逆鳞": (1.4, 1.6, 1.8),
    "玻璃深渊": (2.0, 2.3, 2.6),
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


def _curse_pool(t: int, rng) -> list[dict]:
    """t = 档位索引 0/1/2。每项:name + 效果键(cond/hp/atk/tp/fever/time/text)。"""
    wall = rng.randrange(4)   # 绝对壁垒的免疫系随机
    wall_open = rng.randrange(4)                             # 三重壁垒放行的那一系
    wall3 = [k for k in range(4) if k != wall_open]           # 其余三系全免
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
        {"name": "深渊壁垒", "cond": [(str(k), fmt((0.2, 0.25, 0.3)[t])) for k in range(4)],
         "text": f"全系耐性{int((0.2, 0.25, 0.3)[t] * 100)}%"},
        {"name": "亡者不屈", "cond": [("4", ""), ("0", fmt((0.3, 0.4, 0.5)[t]))],
         "text": f"减益免疫·能耐{int((0.3, 0.4, 0.5)[t] * 100)}%"},
        {"name": "血肉高墙", "hp": (1.6, 2.0, 2.5)[t],
         "text": f"敌血×{(1.6, 2.0, 2.5)[t]}"},
        atk_curse_entry("深渊逆鳞", t, weak),
        # 绝对壁垒:随机一系伤害极高耐性,炼狱=完全免疫(强度1.0=伤害×0),逼构筑切换
        {"name": "绝对壁垒", "cond": [(str(wall), fmt((0.7, 0.85, 1.0)[t]))],
         "text": f"{COND_KIND_CN[wall]}{'完全免疫' if t == 2 else '耐性' + str(int((0.7, 0.85, 1.0)[t] * 100)) + '%'}"},
        # 三重壁垒(2026-07-29 用户需求「免疫可以不止一种,比如三种」):
        # 四系里随机去掉一系,剩下三系同时高耐性/炼狱档完全免疫 —— 只留一条输出路,
        # 逼队伍必须带对那一系。条件槽有 5 个,三条 cond 塞得下。
        {"name": "三重壁垒",
         "cond": [(str(k), fmt((0.5, 0.7, 1.0)[t])) for k in wall3],
         "text": ("·".join(COND_KIND_CN[k] for k in wall3)
                  + ('三重免疫' if t == 2 else f"三重耐性{int((0.5, 0.7, 1.0)[t] * 100)}%")
                  + f"(只剩{COND_KIND_CN[wall_open]}能打)")},
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
    out.update({"conds": [], "hp": 1.0, "atk": 1.0, "tp": None, "fever": None,
                "time": None, "gimmick": False, "caster": None,
                "picks": picks, "combo": combo})
    names = []
    for c in picks:
        out["hp"] *= c.get("hp", 1.0)
        out["atk"] *= c.get("atk", 1.0)
        out["gimmick"] = out["gimmick"] or c.get("gimmick", False)
        out["caster"] = out["caster"] or c.get("caster")
        if "tp" in c:
            out["tp"] = max(out["tp"] or 0, c["tp"])
        if "fever" in c:
            out["fever"] = max(out["fever"] or 0, c["fever"])
        if "time" in c:
            out["time"] = min(out["time"] or 10 ** 9, c["time"])
        names.append(f"「{c['name']}」{c['text']}")
    out["conds"] = merge_conds(picks)[:5]
    out["desc"] = (f"【{combo}】" if combo else "") + " ".join(names)
    return out


def downgrade_atk_curse(curse: dict) -> str | None:
    """把该层的攻击类诅咒降一档;已在最低档则整条摘掉。返回变更说明,无可降 → None。

    分位硬闸的**唯一收敛手段**:每调用一次 atk 严格下降,最多 4 步(2→1→0→摘)
    就回到无攻击诅咒的裸曲线,故循环必然终止。"""
    picks = list(curse.get("picks") or [])
    i = next((i for i, c in enumerate(picks) if c.get("name") in ATK_CURSE_TIERS), None)
    if i is None:
        return None
    c = picks[i]
    t = int(c.get("atk_tier", 0))
    if t > 0:
        picks[i] = atk_curse_entry(c["name"], t - 1, int(c.get("weak", 0)))
        note = f"「{c['name']}」×{c['atk']}→×{picks[i]['atk']}"
        combo = curse.get("combo")
    else:
        picks.pop(i)
        note = f"摘除「{c['name']}」"
        # 组合的承诺(【速攻】=敌攻爆表+限时)已经不成立,标签一并摘掉,别骗玩家
        combo = None
    apply_picks(curse, picks, combo)
    return note


def abyss_curses(r: int, n: int, rng, tier: str, caps: dict | None = None,
                 forced: dict | None = None, no_base: bool = False) -> dict:
    """轮次诅咒包:{conds,hp,atk,tp,fever,time,gimmick,caster,desc,picks,combo}。

    caps = 地形能力 {"spawn": 有SPAWNn锚点, "panel": 官方板子配对地形}——
    祭坛/板子诅咒只在能生效的地形掉落(2026-07-20 真机实证:歼灭者类 boss 擂台
    只有 FUNNEL_SPAWN 锚点,zone-zako 出生静默失败)。
    no_base = 该层 boss 查不到基数(standard 表)→ 归一化不生效、真实伤害无上界
    保证,**禁掉攻击类诅咒**(2026-07-30 伤害审计:第15/18/26/29/30 战都是这种)。
    """
    out = {"conds": [], "hp": 1.0, "atk": 1.0, "tp": None, "fever": None,
           "time": None, "gimmick": False, "caster": None, "desc": "",
           "picks": [], "combo": None}
    has_forced = bool(forced and (forced.get("curses") or forced.get("field")))
    if tier == "off" and not has_forced:
        return out
    t = CURSE_TIERS.index(tier) if tier in CURSE_TIERS else 1
    d = r / n
    # 诅咒名额。**全塔烈狱**(2026-07-29 用户主推)时没有白板层:最浅也给 1 个,
    # 30% 起 2 个,60% 起 3 个(3 是条件槽能装下的上限,见 curse_conflict)。
    # 其余档位维持原节奏:≤15% 白板 / ≤45% 1 个 / 其余 2 个。
    if tier == "hell":
        # ⚠ 3 名额的门槛压在 40% 而不是 60%:名额只有 2 时,8 套组合里只有 4 套
        # (双诅咒的)有资格,【单通道】这类会被过度抽中(实测 30 层里出了 7 次)。
        count = 1 if d <= 0.15 else (2 if d <= 0.4 else 3)
    else:
        if d <= 0.15 and not has_forced:
            return out
        count = 1 if d <= 0.45 else 2
    caps = caps or {}
    pool = _curse_pool(t, rng)
    if no_base:
        # 无基数层:归一化返回 1.0,裸曲线值 + 顶格攻击诅咒 = 第26战 6.58 的成因
        pool = [c for c in pool if c["name"] not in ATK_CURSE_TIERS]
    # 显式指定(工坊拖拽):按名取该档位数值,数量=指定数,跳过随机
    if forced and (forced.get("curses") or forced.get("field")):
        picks = [c for nm in (forced.get("curses") or [])
                 for c in pool if c["name"] == nm and not c.get("caster")]
        for nm in (forced.get("curses") or []):
            if no_base and nm in ATK_CURSE_TIERS:
                print(f"[WARN] 工坊钉选第{r}战:剔除「{nm}」(该层 boss 无基数,"
                      "归一化不生效,攻击类诅咒会失控)")
        if forced.get("field"):
            fm_forced = next((m for m in field_menu_all() if m[1] == forced["field"]), None)
            if fm_forced and caps.get("boss"):
                picks.append({"name": "深渊法阵", "caster": fm_forced,
                              "text": f"{fm_forced[0]}·{fm_forced[2]}"})
        # 钉选也要过冲突闸:手动钉出"四系全免疫"照样是无解层,发出去就卡死玩家
        kept: list[dict] = []
        for c in picks:
            why = curse_conflict(kept + [c])
            if why:
                print(f"[WARN] 工坊钉选第{r}战:剔除「{c['name']}」({why})")
                continue
            kept.append(c)
        return apply_picks(out, kept)
    # 攻击类诅咒(嗜血/逆鳞/玻璃)每轮至多 1 个——双叠=一击秒杀墙,是恶心不是大胆
    picks, atk_used = [], False
    combo_name = None
    # ---- 先试组合(2026-07-29):名额 ≥2 时 55% 概率整套落地,剩余名额再独立随机补 ----
    if count >= 2 and rng.random() < COMBO_RATE:
        cands = [cb_ for cb_ in CURSE_COMBOS if len(cb_["curses"]) <= count]
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
            if len(got) == len(cb_["curses"]) and not curse_conflict(got):
                picks, combo_name = got, cb_["name"]
                atk_used = any(c.get("atk", 1.0) > 1.0 for c in got)
                break
    order = rng.sample(pool, len(pool))
    # 深渊法阵(场程序)出场加权(2026-07-29 用户「场地效果可以再多一点」):
    # 平权时 1/12≈8%,这里 45% 概率把它提到队首 → 实际约四成楼层带场地效果。
    if caps.get("boss") and rng.random() < 0.45:
        caster = next((c for c in order if c.get("caster")), None)
        if caster is not None:
            order.remove(caster)
            order.insert(0, caster)
    for c in order:
        if len(picks) >= count:
            break
        if c.get("gimmick") and not caps.get("panel"):
            continue
        if c.get("caster") and not caps.get("boss"):
            continue
        if any(c["name"] == p["name"] for p in picks):
            continue                              # 组合已带了同名的,别重复
        is_atk = c.get("atk", 1.0) > 1.0
        if is_atk and atk_used:
            continue
        if curse_conflict(picks + [c]):
            continue                              # 全免疫死锁 / 条件槽超 5
        picks.append(c)
        atk_used = atk_used or is_atk
    return apply_picks(out, picks, combo_name)


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
    ap.add_argument("--no-normalize", dest="normalize", action="store_false",
                    help="关闭怪物基础数值归一化(默认开)。开启时按 boss 基数相对"
                         "同修正曲线组中位数反向补偿,拉平「有些副本数值显著低」")
    ap.add_argument("--normalize-hp", type=float, default=1.0,
                    help="血量归一**压缩指数**(1=完全拉平,0=不动;默认 1.0)")
    ap.add_argument("--normalize-atk", type=float, default=0.55,
                    help="伤害归一**压缩指数**(默认 0.55=只压一半,保留「高低有别」)。"
                         "残余跨度≈原极差^(1-指数);全池 atk 极差 86× → 约 6×")
    ap.add_argument("--normalize-min", type=float, default=0.1,
                    help="归一补偿下限(默认 0.1×)。实测线上塔层间真实血量极差:不归一 80× / 0.25–4 → 8× / **0.1–10 → 3×** / 0.05–20 → 2×")
    ap.add_argument("--normalize-max", type=float, default=10.0,
                    help="归一补偿上限(默认 10×)。窗口越大越平但倍率越极端;想完全拉平用 --normalize-min 0.05 --normalize-max 20")
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
                         "元素跟 boss 老家楼层走),领域/诅咒照常叠加")
    ap.add_argument("--test-field", type=int, default=0, metavar="R",
                    help="强制第 R 轮附加「深渊法阵」(真机验证用)")
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
    zl_t = q.load_table("master/battle/zako/zako_level.orderedmap")
    gb_t = q.load_table(GENERAL_BOSS)
    bl_t = q.load_table("master/battle/boss/boss_level.orderedmap")
    gv_t = q.load_table("master/battle/boss/general_boss_variable.orderedmap")
    sb_t = q.load_table(STANDARD_BOSS)      # 只读:门禁三表并集用
    stale = ([k for k in fd_t if str(k).startswith("mod_rogue_f")]
             + [k for k in zone_t if str(k).startswith("mod_rogue_z")])
    stale_c = ([k for k in gz_t if str(k).startswith("mod_rogue_caster")]
               + [k for k in zl_t if str(k).startswith("mod_rogue_caster")]
               + [k for k in gb_t if str(k).startswith("mod_rogue_boss")]
               + [k for k in bl_t if str(k).startswith("mod_rogue_boss")]
               + [k for k in gv_t if str(k).startswith("mod_rogue_boss")])
    for k in stale:
        fd_t.pop(k, None)
        zone_t.pop(k, None)
    for k in stale_c:
        gz_t.pop(k, None)
        zl_t.pop(k, None)
        gb_t.pop(k, None)
        bl_t.pop(k, None)
        gv_t.pop(k, None)
    gim_dirty = bool(stale)
    caster_dirty = bool(stale_c)

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

    tower_all = cb.build_pool()
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
    tower = [e for e in gated if _c8016_safe(e[2])]
    if len(tower) < len(gated):
        print(f"[C8016] 塔素材池剔除 {len(gated) - len(tower)} 层(黑名单:{','.join(C8016_BLOCKED_BOSS_PREFIXES)})")
    if len(tower) < args.rounds + 1:
        print(f"[ERR] 塔素材池只有 {len(tower)} 层 < {args.rounds}+1 轮")
        return 1
    tower_master = list(tower)          # 钉选(工坊 boss/terrain)查询用,不随消费缩水

    # ---- boss 出场历史降权:最近两座塔出过的 boss,80% 概率让位给新面孔 ----
    special_bosses = load_special_bosses()
    if special_bosses[0] or special_bosses[1]:
        print(f"[原味] 特殊 boss 保护:精确 {len(special_bosses[0])} 个 + "
              f"前缀 {len(special_bosses[1])} 族(抽中即原场地原机制,不拆解)")
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

    def _quota_left(key: str) -> bool:
        return used_counts.get(key, 0) < key_cap(key)

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
        kept = [e for e in gated_pool if _c8016_safe(e["bosses"])]
        if len(kept) < len(gated_pool):
            print(f"[C8016] 来源池「{label}」剔除 {len(gated_pool) - len(kept)} 个场地")
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
    caster_blocked: dict[str, str] = {}
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

    def field_caps(field_id: str, bosses: list[str]) -> dict:
        """能力表:boss=有 general boss 可当法阵载体(2026-07-20 实证:zone-zako
        emitter 需地形 SPAWN 物件定位,95% 楼层没有,'*spawn-point*' 是"生成点"
        注册名而非地形标记查找——zako 祭坛路线弃);panel=官方板子配对地形。"""
        frow = fd_t.get(field_id)
        panel = False
        if isinstance(frow, (str, bytes, bytearray)):
            fc = cells(frow)
            panel = len(fc) > 2 and fc[1] in panel_terrains
        carrier = any(b in belem_map for b in bosses)
        if carrier:
            # 成对/分阶段 boss 层禁发法阵(2026-07-30 玩家「打不死」实锤)
            why = caster_carrier_block(field_id, bosses, fd_t, zone_t, phase_linked)
            if why:
                caster_blocked[field_id] = why
                carrier = False
        return {"boss": carrier, "panel": panel}

    def make_caster_boss(r: int, boss_code: str, program: str):
        """克隆 general boss 当法阵载体:第一条现役 action 列(c111-160,逗号数组)
        追加官方场程序——boss 做那个动作时顺带施法,定位天然有效,全楼层通用。
        附表(boss_level/general_boss_variable)按 code 同步克隆;routine 经
        routine_id 引用原状态组,零克隆。"""
        nonlocal caster_dirty
        if boss_code not in gb_t:
            return None
        code = f"mod_rogue_boss{r}"

        def rewrite(node):
            if isinstance(node, dict):
                return {k: rewrite(v) for k, v in node.items()}
            row = cells(node)
            for i in range(111, min(161, len(row))):
                if row[i] not in ("", "(None)"):
                    row[i] = row[i] + "," + program
                    break
            else:
                while len(row) < 112:
                    row.append("")
                row[111] = program
            return join(row, isinstance(node, (bytes, bytearray)))

        gb_t[code] = rewrite(gb_t[boss_code])
        if boss_code in bl_t:
            bl_t[code] = bl_t[boss_code]
        if boss_code in gv_t:
            gv_t[code] = gv_t[boss_code]
        caster_dirty = True
        return code

    def gimmick_field(orig_field: str, r: int, panels: bool = False,
                      boss_swap: tuple[str, str] | None = None):
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
        nz = {}
        for wk, wrow in zn.items():
            if isinstance(wrow, dict):
                return None                       # 异形嵌套 zone,不折腾
            wc = cells(wrow)
            while len(wc) < 41:
                wc.append("")
            if panels:
                wc[36], wc[37] = GIM_DASH, GIM_ROT
            if boss_swap:
                apply_boss_swap(wc, boss_swap[0], boss_swap[1])
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
                     if elem_map.get(e[0]) is not None
                     or any(belem_map.get(b) is not None for b in e[2])]
            if not cands:
                tower.append(terrain)
                return None
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
            cands = prefer_fresh(cands, lambda e: e[2])
            src_e = cands[rng.randrange(len(cands))]
            tower.remove(src_e)
        tf, tline, _tb = terrain
        sf, _sline, sbosses = src_e
        strict, safe_set = load_transplant_policy()
        unsafe = strict and not all(b in safe_set for b in sbosses)
        if (unsafe or any(is_special_boss(b, special_bosses) for b in sbosses))                 and not pin_terrain:
            # 原味保护:名单 boss 不拆解,整层直用它的老家场地(诅咒照常在外层叠加)
            if not pin_boss:
                tower.append(terrain)               # 地形没用上,归还池子
            return {"field": sf, "bosses": sbosses, "thumb": thumb_map.get(sf, ""),
                    "bgm": (cb._cols(_sline)[1] if _sline else None),
                    "label": "原味·" + ",".join(sorted(set(sbosses)))}
        frow = fd_t[tf]
        fc = cells(frow)
        zkey, fkey = f"mod_rogue_z{r}", f"mod_rogue_f{r}"
        zone_t[zkey] = swap_zone_bosses(zone_t[fc[2]], sbosses)
        nf = list(fc)
        nf[2] = zkey
        fd_t[fkey] = join(nf, isinstance(frow, (bytes, bytearray)))
        gim_dirty = True
        elem = elem_map.get(sf)
        if elem is None:
            elem = next((belem_map[b] for b in sbosses if belem_map.get(b) is not None), None)
        return {"field": fkey, "bosses": sbosses, "thumb": thumb_map.get(tf, ""),
                "bgm": (cb._cols(tline)[1] if tline else None),
                "elem_override": elem, "boost_field": tf,
                "label": f"拼·{','.join(sbosses)} @ {tf}"}

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
              f"clamp {args.normalize_min}–{args.normalize_max}×"
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
        thumb = pick.get("thumb") or ""
        if thumb:
            row[5] = thumb                               # 来源副本的正规预览图
        row[7] = START
        row[8] = END
        row[67] = "0"                                    # 体力
        # c69 优先=官方源 quest 推荐元素(kit 色替只在官方配置下自洽,C8016 根因);
        # 次选=固定元素 boss 查表;都查不到才随机。拼接层带 elem_override
        # (= boss 老家楼层元素),优先级最高。
        official = pick.get("elem_override")
        if official is None:
            official = elem_map.get(pick["field"])
        fixed = next((belem_map[c] for c in pick["bosses"] if belem_map.get(c) is not None), None)
        if official is not None:
            elem, tag = official, "(官方)"
        elif fixed is not None:
            elem, tag = fixed, ""
        else:
            elem, tag = rng.randrange(6), "(随机)"
        row[69] = str(elem)
        # 楼层等级在循环里按爬坡档已经算好(pick["level"]);无尽档等走老路
        row[95] = str(pick.get("level")
                      or resolve_level(pick["bosses"], args.enemy_level, sb_t, gv_t,
                                       gb_t, prefer_max=want_max)
                      or args.enemy_level)
        row[98] = pick.get("play_field") or pick["field"]   # 乱流机关=克隆场
        if pick.get("bgm"):
            row[99] = pick["bgm"]                        # 塔层带专属 BGM;来源副本保持模板
        return f" 属性:{ELEM_CN[elem] if elem < 6 else '无'}{tag}"

    quest_rows: dict[str, list[str]] = {}
    forged_pubs: set[str] = set()
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
        if _lab in schedule.values():
            _fb, _ = _zone_pick(_fixed_field)
            for _k in name_keys(_fb):
                used_counts[_k] = used_counts.get(_k, 0) + 1

    tower_bosses: list[str] = []
    floor_recs: list[dict] = []
    for r in range(1, args.rounds + 1):
        label = schedule.get(r)
        forced = (((plan.get("floors") or {}).get(str(r))) or {}) if not args.ignore_plan else {}
        pin_t, pin_b = forced.get("terrain"), forced.get("boss")
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
        tower_bosses += pick["bosses"]
        for _k in name_keys(pick["bosses"]):
            used_counts[_k] = used_counts.get(_k, 0) + 1
        if args.test_field == r and label is None:
            tries = 0
            while not field_caps(pick["field"], pick["bosses"])["boss"] and tower and tries < 30:
                pick = tower_pick(r)
                tries += 1
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
        # 基础数值归一:按 boss 基数相对同曲线组中位数反向补偿(2026-07-29 用户需求)
        if args.normalize:
            nh, na = stat_normalize(pick["bosses"], _hp_med, _atk_med,
                                    args.normalize_min, args.normalize_max, _lv,
                                    {"hp": args.normalize_hp, "atk": args.normalize_atk})
            bh, ba = bh * nh, ba * na
            pick["norm"] = (nh, na)
        caps = field_caps(pick["field"], pick["bosses"])
        st_tier, st_mult = plan_tier_for(plan, r, round_tier(r))
        curse = abyss_curses(r, args.rounds, rng, st_tier, caps, forced,
                             no_base=_anchor is None)
        if args.test_field == r and not curse["caster"]:
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
        if curse["gimmick"] or curse["caster"]:
            swap = None
            if curse["caster"]:
                fm_ = curse["caster"]
                program = fm_[1]
                fcat = fm_[3] if len(fm_) > 3 else "领域"
                tun = field_tuning()
                factor = float(tun.get("per", {}).get(program)
                               or tun.get("global", {}).get(fcat, 1) or 1)
                if abs(factor - 1.0) > 1e-9:
                    # 缩放标注挂在法阵条目自己的 text 上,降档闸重渲 desc 时不会丢
                    for _c in curse.get("picks") or []:
                        if _c.get("caster") is fm_:
                            _c["text"] += f"×{factor:g}"
                    apply_picks(curse, curse.get("picks") or [], curse.get("combo"))
                    if args.write:
                        import wf_field_catalog as wfc
                        program = wfc.forge(program, scale=factor)
                if program.startswith("battle/action/enemy/action/mod_rogue/"):
                    forged_pubs.add(program + ".action.dsl.amf3.deflate")
                target = next((b for b in pick["bosses"] if b in belem_map), None)
                clone = make_caster_boss(r, target, program) if target else None
                swap = (target, clone) if clone else None
            pick["play_field"] = gimmick_field(pick["field"], r,
                                               panels=curse["gimmick"], boss_swap=swap)
        note = patch_common(row, f"{EVENT_NAME} 第{r}战", pick)
        quest_rows[str(r)] = row
        # ⚠ 数值列**不在这里落**:分位硬闸要看到全塔分布才能决定哪层降档,
        # 降档又会改回 hp/诅咒词条/副标题。所以先攒 record,闸门跑完再统一写。
        floor_recs.append({
            "r": r, "row": row, "pick": pick, "note": note, "bh": bh, "ba": ba,
            "curse": curse, "st_mult": st_mult, "no_base": _anchor is None,
            "anchor": _anchor,
            "funnel": any(fc.startswith(b) for b in pick["bosses"]
                          for fc in funnel_levels()),
        })

    # ---- 分位硬闸 + 数值列落表(2026-07-30)----
    curve_scale, band_log = enforce_atk_band(floor_recs, atk_base, atk_growth,
                                             args.rounds)
    for frec in floor_recs:
        r, row, curse = frec["r"], frec["row"], frec["curse"]
        hp = fmt(hp_base * (hp_growth ** (r - 1)) * frec["bh"] * curse["hp"]
                 * frec["st_mult"])
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
        boost = (f" 补偿hp×{frec['bh']:.2f}/atk×{frec['ba']:.2f}"
                 if (frec["bh"], frec["ba"]) != (1.0, 1.0) else "")
        if pick.get("norm") and pick["norm"] != (1.0, 1.0):
            boost += f"(含归一 ×{pick['norm'][0]:.2f}/×{pick['norm'][1]:.2f})"
        fdisp = pick["field"] + (f"→{pick['play_field']}" if pick.get("play_field") else "")
        fun = f" 炮台atk×{row[90]}" if frec["funnel"] else ""
        plan_lines.append(f"  第{r}战 [{pick['label']}] lv{pick.get('level')} "
                          f"field={fdisp} hp×{hp} atk×{atk}{fun}{boost}"
                          f"{frec['note']}{eff}")
    if band_log:
        plan_lines.append(f"  ---- 分位硬闸动作 {len(band_log)} 次 ----")
        plan_lines += [f"  {ln}" for ln in band_log]
    # ---- 数值带体检(发布前一眼看穿这座塔热不热)----
    _late = sorted(f["atk"] for f in floor_recs if f["r"] / args.rounds > BAND_FROM)
    _early = sorted(f["atk"] for f in floor_recs if f["r"] / args.rounds <= BAND_FROM)
    _hp = sorted(float(f["row"][88]) for f in floor_recs)
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
        f" · hp 中位 {statistics.median(_hp):.2f}/max {_hp[-1]:.2f}"
        f"(官方 rush max 100)"
        + (f" · 真伤指数 max {max(_tdi):.2f}(闸 {TRUE_DMG_CAP})" if _tdi else "")
        + (f" · 曲线缩放 ×{curve_scale:.3f}" if curve_scale != 1.0 else ""))
    plan_lines.append("  [数值带] 敌等级:"
                      + " ".join(f"lv{k}×{v}" for k, v in sorted(_lv.items(),
                                                                 key=lambda kv: kv[0] or 0)))

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

    print(f"seed={args.seed} rounds={args.rounds} "
          f"difficulty={args.difficulty or '(旧默认)'} curse={args.curse or '(随难度)'} "
          f"hp={fmt(hp_base)}×{fmt(hp_growth)}^r atk={fmt(atk_base)}×{fmt(atk_growth)}^r")
    print("\n".join(plan_lines))

    # ---- 硬门禁复核:构建产物(含克隆场/法阵 boss)全链可解析,任一悬空拒绝产出 ----
    reports = validate_built_rows(quest_rows, fd_t, zone_t,
                                  set(gb_t) | set(sb_t) | set(gz_t), set(gz_t),
                                  lv_ceil=sb_t, lv_floor=gv_t, lv_gb=gb_t)
    broken = [r for r in reports if not r["ok"]]
    if broken:
        for r in broken:
            print(f"[ERR] 第{r['round']}战 field={r['field']} 引用悬空:"
                  + "; ".join(r["errors"]))
        print(f"[ERR] {len(broken)}/{len(reports)} 关解析链断裂,拒绝产出(未写入任何表)")
        return 1
    print(f"[门禁] {len(reports)} 关解析链复核通过(quest→field→zone→boss/zako 全可解析)")
    if caster_blocked:
        print(f"[门禁] 成对/分阶段 boss 层已禁发深渊法阵({len(caster_blocked)} 个场地):")
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
    if gim_dirty:
        save(FIELD_DATA_T, fd_t)
        save(ZONE_T, zone_t)
        print("[OK] 场地克隆已写入(field_data / zone)")
    if caster_dirty:
        save(GENERAL_ZAKO, gz_t)
        save("master/battle/zako/zako_level.orderedmap", zl_t)
        save(GENERAL_BOSS, gb_t)
        save("master/battle/boss/boss_level.orderedmap", bl_t)
        save("master/battle/boss/general_boss_variable.orderedmap", gv_t)
        print("[OK] 法阵载体已写入(general_boss / boss_level / boss_variable + zako 清理)")

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
    sys.exit(main())

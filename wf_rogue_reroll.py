#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""wf_rogue_reroll.py — 深渊连战(700099)一键重开。

重摇爬塔全部内容(楼层/boss 属性/场地效果,随机种子)+ 清爬塔进度 + 发布 CDN + 重启游戏,
= GUI 工具箱「深渊连战·一键重开」按钮的后端。

流程(--apply):
  1. wf_rogue_build --seed S --write --publish:重摇全部轮次的楼层(小怪房/领主战/机兵/
     降临讨伐/女帝/无幻之宴/塔层/终始之龙)+ boss 元素(c69)+ 场地效果(c71-80+副标题)
     并打 CDN 增量包(此步游戏可开着,发布只影响下次启动的下载)
  2. force-stop 游戏(防止局内继续打把旧进度写回;--no-restart 跳过)
  3. 清爬塔进度:players_rush_events / *_played_parties / *_cleared_folders
     按 event_id 精确删(默认全部存档,--player 限定单档;武器/角色/道具/编队与
     官方 700007 的进度一概不动;无尽最佳纪录属于本活动行,会一并清零)
  4. 拉起游戏(启动时增量下载新数据)

用法(项目根,默认 dry-run 只预览):
  python mod-tools/wf_rogue_reroll.py                       # 预览:新阵容 + 将清的进度
  python mod-tools/wf_rogue_reroll.py --apply               # 一键重开(随机种子)
  python mod-tools/wf_rogue_reroll.py --seed 12345 --apply  # 复现指定种子
注意:--rounds 与线上部署不同时服务端 json 内容变化,发布后须重启服务端(start-cn.bat)。
"""
import argparse
import json
import os
import random
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "mod-tools"))
import wf_rogue_save as rsave     # noqa: E402  (mumu_sh / WF_PACKAGE / WF_ACTIVITY / DB_PATH)

BUILD = os.path.join(ROOT, "mod-tools", "wf_rogue_build.py")
PROGRESS_TABLES = (
    "players_rush_events",
    "players_rush_events_played_parties",
    "players_rush_events_cleared_folders",
)


def deployed_rounds(event: str) -> int:
    """线上已部署的爬塔轮数(数服务端 json 里 folder 1 的 quest 条目)。"""
    path = os.path.join(ROOT, "assets", "rush_event_quest.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError:
        return 0
    return sum(1 for v in data.values()
               if v.get("rushEventId") == int(event) and v.get("rushEventFolderId") == 1)


def progress_counts(db: sqlite3.Connection, event: str, player: int | None) -> dict[str, int]:
    out = {}
    for table in PROGRESS_TABLES:
        sql = f"SELECT COUNT(*) FROM {table} WHERE event_id=?"
        params: tuple = (int(event),)
        if player is not None:
            sql += " AND player_id=?"
            params += (player,)
        out[table] = db.execute(sql, params).fetchone()[0]
    return out


def clear_progress(db: sqlite3.Connection, event: str, player: int | None) -> None:
    with db:
        for table in PROGRESS_TABLES:
            sql = f"DELETE FROM {table} WHERE event_id=?"
            params: tuple = (int(event),)
            if player is not None:
                sql += " AND player_id=?"
                params += (player,)
            n = db.execute(sql, params).rowcount
            print(f"  {table}: 删 {n} 行", flush=True)


def build_command(args, seed: int) -> list[str]:
    """构造 wf_rogue_build 命令；默认不传 --ramp，即全程决战级。"""
    # 服务端虽用 `python -X utf8 wf_rogue_reroll.py`，该 flag 不会自动传给
    # 子 Python；显式补上，避免 boss 日文标签在 Windows GBK 下打印即崩。
    cmd = [sys.executable, "-X", "utf8", "-u", BUILD,
           "--rounds", str(args.rounds), "--seed", str(seed),
           "--enemy-level", str(args.enemy_level)]
    if args.curse:
        cmd += ["--curse", args.curse]
    if args.mix:
        cmd += ["--mix"]
    if args.difficulty:
        cmd += ["--difficulty", args.difficulty]
    if args.ramp:
        cmd += ["--ramp"]
    if args.apply:
        cmd += ["--write", "--publish"]
    return cmd


def main() -> int:
    ap = argparse.ArgumentParser(description="深渊连战一键重开(重摇+清进度+发布+重启游戏)")
    ap.add_argument("--rounds", type=int, default=30,
                    help="爬塔轮数(与线上不同须重启服务端)。默认 30 = 线上部署轮数,"
                         "与 rushEvent.ts 重摇钩子的 `cfg.rounds ?? 30` 对齐;"
                         "2026-08-07 前是 15,GUI 两个入口都不显式传值,"
                         "于是每次一键重开都把 30 层塔换成 15 层")
    ap.add_argument("--seed", type=int, help="留空=每次随机;填数字可复现同一座塔")
    ap.add_argument("--enemy-level", default="ramp",
                    help="敌等级:ramp=按深度爬坡(**默认**,前1/3 lv80→中段 lv90→"
                         "尾段 lv100)/ 数字 / max=每层取该 boss 最高档。"
                         "⚠ 2026-07-30 前默认是 max,全塔平坦 lv100 站在曲线悬崖顶"
                         "(官方只有 4.2%% 内容上 lv100),是 boss 伤害过高的结构成因之一")
    ap.add_argument("--event", default="700099", help="rush 活动 id(默认深渊连战)")
    ap.add_argument("--player", type=int, help="只清指定存档的进度(默认全部存档)")
    ap.add_argument("--keep-progress", action="store_true",
                    help="不清进度只换楼层(旧进度会接在新楼层上,一般不建议)")
    ap.add_argument("--no-restart", action="store_true",
                    help="不自动 force-stop/拉起游戏(自己手动重启生效)。"
                         "⚠ 游戏若正在局内,残局结算会写进清空后的新进度(幽灵行,"
                         "2026-07-27 卡第1关实锤),确保没在打再用")
    ap.add_argument("--curse", choices=("off", "standard", "abyss", "hell"),
                    help="深渊诅咒档位(缺省=wf_rogue_build 默认 abyss)")
    ap.add_argument("--mix", action="store_true",
                    help="模块化拼接:塔层地形与 boss 独立随机组合(透传 wf_rogue_build)")
    ap.add_argument("--difficulty", choices=("easy", "normal", "hell", "gradient"),
                    help="全塔难度预设:easy 全简单/hell 全炼狱/gradient 从简单到难"
                         "(透传 wf_rogue_build,层数自适应)")
    ap.add_argument("--ramp", action="store_true",
                    help="显式恢复旧 DPS 几何爬坡(60万→2500万)；默认关闭，"
                         "即第1战热身外全程决战级。与 --enemy-level ramp 无关")
    ap.add_argument("--apply", action="store_true", help="真执行(默认 dry-run 预览)")
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 10 ** 8)
    print(f"种子 = {seed}(复现同一座塔:--seed {seed})", flush=True)

    dep = deployed_rounds(args.event)
    if dep and dep != args.rounds:
        print(f"[WARN] 轮数 {dep} → {args.rounds}:服务端 json 内容会变,"
              "发布后须重启服务端(start-cn.bat)", flush=True)

    db = sqlite3.connect(rsave.DB_PATH, timeout=15)
    db.execute("PRAGMA busy_timeout=15000")
    try:
        counts = progress_counts(db, args.event, args.player)
        scope = f"存档 {args.player}" if args.player is not None else "全部存档"
        total = sum(counts.values())
        if args.keep_progress:
            print(f"进度({scope}):保留不清(--keep-progress)", flush=True)
        else:
            print(f"将清 {args.event} 爬塔进度({scope},共 {total} 行):"
                  + " ".join(f"{t.split('players_rush_events')[-1] or '主行'}={n}"
                             for t, n in counts.items()), flush=True)

        # 1. 重摇 + 发布(dry-run 时不带 --write,只打印新阵容)
        cmd = build_command(args, seed)
        rc = subprocess.run(cmd, cwd=ROOT).returncode
        if rc != 0:
            print(f"[ERR] wf_rogue_build 退出码 {rc},中止(进度未动)", flush=True)
            return rc

        if not args.apply:
            print("[DRY-RUN] 未写入/未清进度/未动游戏。加 --apply 一键重开。", flush=True)
            return 0

        # 2. 关游戏 → 3. 清进度 → 4. 拉起
        if not args.no_restart:
            print("[GAME] force-stop …", flush=True)
            rsave.mumu_sh(f"am force-stop {rsave.WF_PACKAGE}")
        if not args.keep_progress:
            print(f"清 {args.event} 爬塔进度({scope}):", flush=True)
            clear_progress(db, args.event, args.player)
        if not args.no_restart:
            print("[GAME] 拉起游戏 …", flush=True)
            rsave.mumu_sh(f"am start -n {rsave.WF_ACTIVITY}")
            print("[OK] 一键重开完成:游戏启动后增量下载新数据,进活动即新塔。", flush=True)
        else:
            print("[OK] 重摇+清进度完成:手动重启游戏生效。", flush=True)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    # 手工从 Windows PowerShell 启动时同样不能依赖活动 code page。
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

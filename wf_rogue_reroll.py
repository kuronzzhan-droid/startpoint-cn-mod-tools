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
  3b.排行榜**结算 + 换期**:回调服务端 `POST /api/rush-leaderboard/<event>/season/rollover`
     (--keep-season 跳过;--offline-season 退回只写 SQL 的逃生口)
  4. 拉起游戏(启动时增量下载新数据)

排行榜换期(2026-08-28 作者裁定「每次重 roll 塔,排行榜结算,新塔是新榜」)
------------------------------------------------------------------
「战斗用时榜」只列**当期**成绩(`src/data/domains/rushLeaderboard.ts`
`getRushFullRunLeaderboardSync` 的 season 参数),所以重摇塔必须把期号推进一格,
否则新塔上还挂着旧塔的排行。

为什么这一步写在这个工具里而不是靠服务端自己发现:GUI 的「一键重开」和命令行都是
**直接拉起本脚本**,全程不碰 8001;服务端那个换期钩子
(`src/routes/api/rushEvent.ts` 的 reroll 钩子)只在**游戏内**按整段重置时才走到。
指纹兜底(folder→轮数)在默认 `--rounds 30` 下重摇前后都是 `1:30`,也不会触发。
⇒ 不在这里喊一声,作者重摇一百次塔期号也还是第 1 期。

**但换期动作本身不在这里做。** 第一版是直接 UPDATE `rush_event_seasons`,
那样**只换期、不发奖**:服务端的结算只能结算「台账里当前那一期」,期号一旦被推走,
上一期的名次冻结和奖励邮件就永远补不回来。20260828 收口改成回调后台那个端点,
由服务端在**一个事务里**先冻结名次 + 发奖邮件,再把期号 +1
(见 `src/lib/rush-settlement-service.ts::settleThenRolloverRushSeason`)。

回调失败(8001 没起 / token 不对 / 结算真炸了)时**不回落到写 SQL**:
「塔换了榜没换期」可恢复(到后台点一下就补上),「换了期没结算」不可恢复。
这时脚本以退出码 3(EXIT_SEASON_HANDOFF_FAILED)结束并打印补救步骤 ——
不是 1,因为重摇本身成功了,报失败会诱使操作者再重摇一次。

服务端钩子拉起本脚本时会显式传 `--keep-season`(它那一侧自己会做结算+换期),
避免同一次重摇换两期。

用法(项目根,默认 dry-run 只预览):
  python mod-tools/wf_rogue_reroll.py                       # 预览:新阵容 + 将清的进度
  python mod-tools/wf_rogue_reroll.py --apply               # 一键重开(随机种子)
  python mod-tools/wf_rogue_reroll.py --seed 12345 --apply  # 复现指定种子
注意:--rounds 与线上部署不同时服务端 json 内容变化,发布后须重启服务端(start-cn.bat)。
"""
import argparse
import json
import os
import json as _json
import random
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(__file__))
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_rogue_save as rsave     # noqa: E402  (mumu_sh / WF_PACKAGE / WF_ACTIVITY / DB_PATH)
import wf_mod_tool as core
import wf_server_auth             # noqa: E402  (resolve_server_url / admin_bearer_headers)

BUILD = os.path.join(ROOT, "wf_rogue_build.py")
PROGRESS_TABLES = (
    "players_rush_events",
    "players_rush_events_played_parties",
    "players_rush_events_cleared_folders",
)

# 「塔换了,但榜没换期」的专用退出码。
# 不能用 0(GUI 会显示绿色成功,没人会去补那一刀),也不能用 1
# ——重摇本身是成功的(塔已重建、进度已清),报失败会诱使操作者**再重摇一次**。
EXIT_SEASON_HANDOFF_FAILED = 3


def now_ms() -> int:
    """真实墙钟(ms)。与服务端计时同源:后台的「时间控制」平移的是 getServerDate,
    排行榜台账一律用 Date.now(),这里对齐。"""
    return int(time.time() * 1000)


def deployed_rounds(event: str) -> int:
    """线上已部署的爬塔轮数(数服务端 json 里 folder 1 的 quest 条目)。"""
    path = core.resolve_server_dir() / "assets" / "rush_event_quest.json"
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


def season_fingerprint(event: str) -> str:
    """塔指纹,必须与服务端 computeRushSeasonFingerprint() 逐字一致。

    服务端算法(`src/lib/assets.ts::getRushEventFolderMaxRounds` +
    `src/lib/rush-leaderboard.ts::computeRushSeasonFingerprint`):
    扫 rush_event_quest.json,对该事件按 folder 取 rushEventRound 的最大值,
    按 folder 升序拼成 `folder:max,folder:max`。注意 `round > (map[folder] ?? 0)`
    —— 全 0 轮的 folder(无尽)根本不会进 map,别自作主张补 `2:0`。

    读不到表就返回空串:空指纹和服务端「表为空」算出来的一样,
    最坏结果是服务端下次 ensureRushSeason 再换一期,不会写坏数据。
    """
    path = core.resolve_server_dir() / "assets" / "rush_event_quest.json"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return ""
    folders: dict[int, int] = {}
    for row in data.values():
        try:
            if int(row.get("rushEventId", 0)) != int(event):
                continue
            folder = int(row["rushEventFolderId"])
            rnd = int(row["rushEventRound"])
        except (TypeError, ValueError, KeyError):
            continue
        if rnd > folders.get(folder, 0):
            folders[folder] = rnd
    return ",".join(f"{f}:{folders[f]}" for f in sorted(folders))


def unsettled_season(db: sqlite3.Connection, event: str) -> int | None:
    """当前这一期结算过没有?**只给 `--offline-season` 那条逃生口用。**

    ⚠ `--offline-season` **只换期不发奖**:服务端的 `settleRushSeasonNow()` 只能结算
    「台账里当前的那一期」(冻结名次要现读榜,旧期的榜早就被后来的成绩改写了)。
    一旦从那条路换了期,上一期的名次冻结和奖励邮件就**永远补不回来** ——
    `rush_season_results` 里那一期是空的,后台「结算结果」页对它永远查不到东西。
    所以走逃生口之前先看一眼,没结算就喊出来。
    默认那条路(`rollover_via_server`)由服务端先结算再换期,不需要这条提醒。

    :returns: 未结算的期号;已结算(或压根查不出来)返回 None。
    """
    try:
        row = db.execute(
            "SELECT season FROM rush_event_seasons WHERE event_id = ?", (int(event),)
        ).fetchone()
        if row is None:
            return None
        season = int(row[0])
        done = db.execute(
            "SELECT 1 FROM rush_season_results WHERE event_id = ? AND season = ? LIMIT 1",
            (int(event), season),
        ).fetchone()
        return None if done else season
    except sqlite3.Error:
        # 老库没有 rush_season_results 表就当查不出来,不因为一句提示中止重摇。
        return None


def note_season_baseline(event: str, season, source: str) -> None:
    """换期成功之后,把「现在这座塔」记成新一期的基线(GUI 判据用)。

    ⚠ 这一步不能省:GUI 的两条发布入口靠「和当前这一期开张时那座塔比,变了多少层」
    来分辨「真换塔」和「只改了一层 boss」。这里不刷新的话,先用一键重开换了期、
    再去 ⑥ 面板改一层,GUI 会拿**重摇之前**那座塔当基线,把单层小修误判成真换塔,
    白清一张榜。

    整段吞异常:它只是个本地判据缓存,写不进去最坏是 GUI 下次判「不确定」(= 不换期),
    绝不能因此让一次重摇失败。
    """
    try:
        import wf_rogue_season
        wf_rogue_season.note_rollover(str(event), season, source)
    except Exception as exc:
        print(f"[WARN] 换期基线没记上({type(exc).__name__}: {exc});"
              "GUI 下次发布会判「不确定」而不换期,不影响本次重摇。", flush=True)


def rollover_via_server(event: str, source: str = "reroll-cli",
                        server: str | None = None, timeout: int = 30) -> dict:
    """**默认换期通道**:回调服务端「结算并开启新一期」,由它在一个事务里
    先冻结名次 + 发奖邮件,再把期号 +1。

    ── 为什么不在本脚本里直接写 SQL(20260828 收口)────────────────────
    结算逻辑在 TS 里(读两张榜 / 按名次配奖 / 写 `rush_season_results` /
    插 `players_mails` / 授称号 / 顺延排期,全在一个 SQLite 事务里)。
    在 Python 侧重写一遍 = 两份实现迟早分叉,而分叉的表现是**静默少发奖**。
    本脚本本来就跑在服务端同一台机器上(它要 force-stop 模拟器、直连
    `.database/wdfp_data.db`),8001 就在旁边 ⇒ 走 HTTP 复用那一份实现最省事。

    ── 失败了怎么办 ──────────────────────────────────────────────
    **不回落到写 SQL。** 只换期不结算 = 上一期的名次和奖励永远补不回来;
    而「塔换了、榜还没换期」是可恢复的(到后台点一下「结算并开启新一期」)。
    所以这里失败就如实报出来,让 `main()` 用
    {@link EXIT_SEASON_HANDOFF_FAILED} 退出。

    :param event: rush 活动 id。
    :param source: 写进台账的来源标记。
    :param server: 服务端地址;缺省按 WF_SERVER_URL → .env → 127.0.0.1:8001 解析。
    :param timeout: 单次请求超时(秒)。结算要读榜+发邮件,给宽一点。
    :returns: {"ok": bool, "status": int|None, "body": dict|None, "error": str|None}
    """
    server_root = core.resolve_server_dir()
    base = (server or wf_server_auth.resolve_server_url(server_root)).rstrip("/")
    url = f"{base}/api/rush-leaderboard/{int(event)}/season/rollover?source={source}"
    # ⚠ 必须**显式**带 Content-Type: application/json + 一个合法的 JSON 体。
    # 病因不是「没有 Content-Type」——urllib 在 `data=` 非 None 时会自己补一个
    # (`AbstractHTTPHandler.do_request_`:`if not request.has_header('Content-type'):
    #  add_unredirected_header('Content-type', 'application/x-www-form-urlencoded')`),
    # 而 Fastify 5 **没有 x-www-form-urlencoded 的 parser** ⇒ 415
    # FST_ERR_CTP_INVALID_MEDIA_TYPE(20260828 起了个裸 Fastify 实测)。
    # 也就是说:不显式覆盖,这条回调**每次**都失败,而失败是静默的
    # (只在重摇日志里留一行 WARN)。
    # 端点本身不读 body(来源走查询串),这里给个 `{}` 纯粹是喂饱内容类型解析器。
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **wf_server_auth.admin_bearer_headers(server_root),
    }
    request = urllib.request.Request(url, data=b"{}", method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = _json.loads(response.read().decode("utf-8") or "{}")
            return {"ok": True, "status": response.status, "body": body, "error": None}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = _json.loads(raw or "{}")
        except ValueError:
            body = None
        message = (body or {}).get("error") or raw.strip() or f"HTTP {exc.code}"
        return {"ok": False, "status": exc.code, "body": body, "error": message}
    except Exception as exc:                       # URLError / socket.timeout / JSON 坏了
        return {"ok": False, "status": None, "body": None,
                "error": f"{type(exc).__name__}: {exc}"}


def current_season_via_server(event: str, server: str | None = None,
                              timeout: int = 10) -> dict:
    """服务端**此刻**台账里的期号。给 GUI 判据做「基线还新鲜吗」的交叉核对。

    ── 为什么需要它(20260828 三轮复核的 blocker)────────────────────────
    `mod-tools/work/rogue_tower_season.json` 那份判据基线**只有 Python 侧会写**,
    而服务端有五条通道会换期,一条都不碰它:游戏内重摇钩子(它给子进程传
    `--keep-season`,换期在服务端进程里做)、后台「结算并开启新一期」、后台
    「立即结算」(结算事务里自带换期)、到点自动结算的调度器、指纹兜底。
    只要走过其中任何一条,基线就停在**换期之前**那座塔上;再用 ⑥ 面板改一层
    boss 发布,GUI 会数出「30/30 层都变了」⇒ 判真换塔 ⇒ 主动发起一次**不该发生**
    的结算 + 换期:把仍在进行中的一期提前结算发奖、清空当期榜、作废所有进行中的
    run,而换期不可逆。判据的方向必须是「宁可漏判」——漏判只是少换一期(后台点
    一下就补上),误判不可恢复。

    ⇒ 逐条去补 `note_season_baseline` 补不干净(后台按钮和调度器根本不经过
    Python),正解是在用基线之前先问服务端一句「你现在第几期」,和基线里记的那个
    期号对不上就一律不换期(见 `wf_rogue_season.sync`)。

    :param event: rush 活动 id。
    :param server: 服务端地址;缺省按 WF_SERVER_URL → .env → 127.0.0.1:8001 解析。
    :param timeout: 单次请求超时(秒)。这是个纯读端点,不用给太宽。
    :returns: {"ok": bool, "season": int|None, "error": str|None}。
              `ok=True, season=None` = 服务端答了、但台账里还没有这个事件
              (没人开过第 1 关);`ok=False` = 没问到(服务端没起 / token 不对)。
    """
    server_root = core.resolve_server_dir()
    base = (server or wf_server_auth.resolve_server_url(server_root)).rstrip("/")
    url = f"{base}/api/rush-leaderboard/{int(event)}/settlement"
    headers = {
        "Accept": "application/json",
        **wf_server_auth.admin_bearer_headers(server_root),
    }
    request = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = _json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        return {"ok": False, "season": None,
                "error": raw.strip() or f"HTTP {exc.code}"}
    except Exception as exc:                       # URLError / socket.timeout / JSON 坏了
        return {"ok": False, "season": None, "error": f"{type(exc).__name__}: {exc}"}
    season = body.get("currentSeason") if isinstance(body, dict) else None
    if season is None:
        return {"ok": True, "season": None, "error": None}
    try:
        return {"ok": True, "season": int(season), "error": None}
    except (TypeError, ValueError):
        return {"ok": False, "season": None, "error": f"期号不是整数:{season!r}"}


def rollover_season(db: sqlite3.Connection, event: str, now: int) -> tuple[int, int]:
    """**逃生口**:直接写 SQL 换期(期号 +1 + 作废进行中的 run)。

    与服务端 `rolloverRushSeason()` 同语义。幂等性说明:它**不是**幂等的
    (每调一次期号加一),这是刻意的 —— 一次重摇 = 一座新塔 = 一期,
    调用方负责只在真的重摇了之后调一次。

    ⚠ 这里**只换期,不结算**(见 `unsettled_season` 的说明),所以它
    **不再是默认路径** —— 只有显式 `--offline-season` 才走到,
    留给「8001 没在跑但还是得重摇」的场合。

    :returns: (新期号, 被作废的进行中 run 行数)
    """
    fingerprint = season_fingerprint(event)
    with db:
        row = db.execute(
            "SELECT season FROM rush_event_seasons WHERE event_id = ?", (int(event),)
        ).fetchone()
        nxt = (int(row[0]) if row else 0) + 1
        db.execute(
            """INSERT INTO rush_event_seasons
                   (event_id, season, started_at_ms, fingerprint, source)
               VALUES (?, ?, ?, ?, 'reroll-cli')
               ON CONFLICT (event_id) DO UPDATE SET
                   season = excluded.season,
                   started_at_ms = excluded.started_at_ms,
                   fingerprint = excluded.fingerprint,
                   source = excluded.source""",
            (int(event), nxt, now, fingerprint),
        )
        abandoned = db.execute(
            """UPDATE players_rush_event_runs
               SET status = 'abandoned', ended_at_ms = ?
               WHERE event_id = ? AND status = 'active'""",
            (now, int(event)),
        ).rowcount
    return nxt, abandoned


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
    ap.add_argument("--keep-season", action="store_true",
                    help="不推进排行榜期号(默认推进 = 新塔新榜)。"
                         "服务端 /rush_event/reset 的重摇钩子会带上它 —— 那条路上"
                         "服务端已经自己换过期了,再换一次就是一次重摇跳两期")
    ap.add_argument("--offline-season", action="store_true",
                    help="逃生口:8001 没在跑时直接写 SQL 换期。"
                         "⚠ **只换期不发奖**,而且换完之后上一期再也结算不了。"
                         "默认走服务端「结算并开启新一期」端点(先结算再换期)")
    ap.add_argument("--server",
                    help="服务端地址(默认 WF_SERVER_URL → .env → 127.0.0.1:8001)。"
                         "换期回调打到它的 /api/rush-leaderboard/<event>/season/rollover")
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

    server_root = core.resolve_server_dir()
    if args.apply:
        core.resolve_cdn_root()
    database_path = rsave.DB_PATH or os.fspath(rsave.resolve_database_path(server_root=server_root))

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 10 ** 8)
    print(f"种子 = {seed}(复现同一座塔:--seed {seed})", flush=True)

    dep = deployed_rounds(args.event)
    if dep and dep != args.rounds:
        print(f"[WARN] 轮数 {dep} → {args.rounds}:服务端 json 内容会变,"
              "发布后须重启服务端(start-cn.bat)", flush=True)

    db = sqlite3.connect(database_path, timeout=15)
    db.execute("PRAGMA busy_timeout=15000")
    try:
        # 预检放在**任何破坏性动作之前**,这样这条提示还来得及按 Ctrl+C。
        # 只有逃生口才需要它:默认那条路由服务端先结算再换期,不会丢奖。
        if args.apply and not args.keep_season and args.offline_season:
            pending = unsettled_season(db, args.event)
            if pending is not None:
                print(f"⚠ 第 {pending} 期还没结算过,而 --offline-season 只换期、**不发奖**;"
                      "换期之后上一期再也结算不了(服务端只能结算台账里当前那一期)"
                      "⇒ 这一期的排行奖励就永远发不出去了。", flush=True)
                print("  要发奖:现在按 Ctrl+C 中止,把 8001 起起来后去掉 --offline-season 重来"
                      "(默认那条路会先结算再换期)。", flush=True)
                print("  不在乎奖励就无视这条,3 秒后继续。", flush=True)
                time.sleep(3)

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
        # 换期放在 build 之后:--rounds 变过时指纹要按**新**的 rush_event_quest.json 算,
        # 否则服务端下一次 ensureRushSeason 会因指纹不符再白换一期。
        season_handoff_failed = False
        if args.keep_season:
            # 期号不由本进程推,但**基线要记**:这条路(服务端重摇钩子)上塔确实
            # 被重建了,不记的话 GUI 下次拿的是重摇**之前**那座塔当基线。
            # season 传 None —— 换期是服务端在子进程退出之后才做的,这里问不到新期号;
            # 判据看的是 digest,而期号不符会被 `wf_rogue_season.sync()` 的交叉核对
            # 当成「基线不新鲜」⇒ 那一次不换期、只重记基线,正是想要的保守方向。
            note_season_baseline(args.event, None, "reroll-hook")
            print("排行榜期号:保持不变(--keep-season;换期由服务端在本进程退出后做)",
                  flush=True)
        elif args.offline_season:
            season, abandoned = rollover_season(db, args.event, now_ms())
            note_season_baseline(args.event, season, "reroll-cli-offline")
            print(f"排行榜换期(--offline-season,**只换期不发奖**):进入第 {season} 期"
                  f"(作废进行中的 run {abandoned} 条)。"
                  "旧成绩留在库里但不再上当期榜;想给新塔灌 bot 用 "
                  "`python mod-tools/wf_rush_bots.py add`", flush=True)
        else:
            # 默认:回调服务端「结算并开启新一期」—— 结算 + 换期是那边的一个事务。
            result = rollover_via_server(args.event, "reroll-cli", args.server)
            if result["ok"]:
                body = result["body"] or {}
                note_season_baseline(args.event, body.get("season"), "reroll-cli")
                settled = "已结算并发奖" if body.get("settled") else \
                    f"未结算({body.get('settleReason') or '原因未知'})"
                mails = ((body.get("settlement") or {}) or {}).get("mailCount")
                print(f"排行榜换期:进入第 {body.get('season')} 期;{settled}"
                      + (f",发出 {mails} 封奖励邮件" if mails else "")
                      + "。旧成绩留在库里但不再上当期榜;想给新塔灌 bot 用 "
                      "`python mod-tools/wf_rush_bots.py add`", flush=True)
            else:
                season_handoff_failed = True
                print(f"[WARN] 塔已重摇,但**排行榜没换期**:{result['error']}", flush=True)
                print("  期号一格没动 —— 这是刻意的:只换期不结算的话,"
                      "上一期的名次和奖励就永远补不回来了。", flush=True)
                print("  现在榜上还是上一座塔的成绩。补救二选一:", flush=True)
                print("    · 起好 8001,到后台排行榜页点「结算并开启新一期」(推荐,会发奖);",
                      flush=True)
                print("    · 确实不要奖励:`--keep-progress --offline-season` 单跑一次,"
                      "或直接重跑本命令加 --offline-season。", flush=True)
        if not args.no_restart:
            print("[GAME] 拉起游戏 …", flush=True)
            rsave.mumu_sh(f"am start -n {rsave.WF_ACTIVITY}")
            print("[OK] 一键重开完成:游戏启动后增量下载新数据,进活动即新塔。", flush=True)
        else:
            print("[OK] 重摇+清进度完成:手动重启游戏生效。", flush=True)
        # 重摇本身成功了(塔已重建、进度已清),所以不报 1;但换期没做成必须
        # 让调用方看得见 —— GUI 按这个码把绿色成功改成醒目的警告。
        return EXIT_SEASON_HANDOFF_FAILED if season_handoff_failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    # 手工从 Windows PowerShell 启动时同样不能依赖活动 code page。
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

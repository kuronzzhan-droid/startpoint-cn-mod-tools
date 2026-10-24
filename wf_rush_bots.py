#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""深渊连战排行榜「机器人」成绩管理器。

单人自用服的榜上只有作者自己的几个存档,看起来很空。这个工具往榜里灌一批
**假玩家**(bot)的完整成绩,让两张榜(战斗用时榜 / 当轮首通榜)有足够的行数,
也能顺带压测客户端原生列表的滚动与分页。

设计要点
--------
* bot 存档挂在**独立账号**下(`accounts.idp_code = 'rushbot'`),不会混进作者
  自己的账号 —— 否则它们会出现在游戏内的「切换存档」列表里。
* 成绩行必须满足战斗用时榜的三个条件才算数:
  `status='completed'`、`tracked_from_round=1`、`battle_ms > 0`
  (见 `src/data/domains/rushLeaderboard.ts::getRushFullRunLeaderboardSync`;
  排序键 2026-08-28 起是 `battle_ms`,`duration_ms` 只作陪衬)。
* 榜上每行的三个头像来自成绩行里的 `character_id_1..3`,所以队伍必须是
  **可下发角色**:排除助战段 700000..700099,且必须在主表里存在
  (`isShippableCharacterId`,发不可下发的会让客户端抛 ClientError 8013)。
* 默认**不会超过作者当前的最好成绩** —— bot 只填在他后面,除非显式
  `--allow-faster`。
* **每个 bot 还要有一支编队行**(`players_party_groups` + `players_parties`)。
  2026-08-28 起榜行的三个头像优先画「个人资料里的前三个角色」= 该存档
  `party_slot` 指的那一队(`src/lib/rush-leaderboard-agreement.ts::resolveRowMains`);
  bot 没有编队行时会退回成绩快照,榜行仍是三个头像,**但点进去的资料页只剩一个**
  (`buildProfileFavoriteParty` 一路退到 leader 兜底)—— 两屏不一致会被反复当 bug 排查。
  所以 `add` 顺手把编队写上,存量 bot 用 `backfill-parties` 一次性补齐。

用法
----
    python mod-tools/wf_rush_bots.py list
    python mod-tools/wf_rush_bots.py add --count 14
    python mod-tools/wf_rush_bots.py add --count 5 --allow-faster
    python mod-tools/wf_rush_bots.py backfill-parties            # 预览
    python mod-tools/wf_rush_bots.py backfill-parties --apply    # 真写(先自动备份)
    python mod-tools/wf_rush_bots.py clear --confirm CLEAR_RUSH_BOTS

服务端**不用重启**:它和本工具读写同一个 SQLite 文件,榜是每次请求现查的。
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / ".database" / "wdfp_data.db"
CHARACTER_JSON = ROOT / "assets" / "character.json"
RANK_TABLE_JSON = ROOT / "assets" / "cdndata" / "player_rank_full.json"

BOT_IDP_CODE = "rushbot"
BOT_ACCOUNT_APP_ID = "wf_cn"

DEFAULT_EVENT_ID = 700099
SUPPORT_ID_MIN, SUPPORT_ID_MAX = 700000, 700099

#: bot 编队落在哪一格。服务端解码 `players.party_slot` 的方式是
#: group = floor((slot-1)/10)+1、槽位 = ((slot-1)%10)+1
#: (`src/routes/api/profile.ts` 与 `rush-leaderboard-agreement.ts::loadRowFacets`
#: 逐字一致),而 bot 的 party_slot 建出来就是 1 ⇒ group 1 / slot 1。
BOT_PARTY_GROUP_ID = 1
BOT_PARTY_SLOT = 1
#: 编队组的颜色。官方新建存档给的就是 15,照抄免得后台页显示成一个无效色。
BOT_PARTY_COLOR_ID = 15
BOT_PARTY_NAME = "队伍1"

#: 净战斗用时占全程用时的比例。真实成绩里关间整备大约吃掉两成多,
#: 现有 6 条种子成绩实测 0.78 ± 0.001,这里沿用同一口径。
#:
#: 注意方向:**采样的主值是净战斗用时(30 关结算时间之和)**,全程用时由它
#: 反推。因为作者裁定(2026-08-28)榜上排的就是净战斗用时,主值必须是被排的
#: 那个量,否则 bot 之间的差距会被这个固定比例抹成等距。
BATTLE_RATIO = 0.78

NAME_POOL = [
    "夜刃", "琉璃盏", "无月之樱", "空之轨迹", "白露未晞", "苍岚", "拾柒",
    "折戟沉沙", "银河渡口", "冬眠的猫", "雾隐之岚", "半盏流年", "北极星",
    "潮汐观测者", "赤羽", "南风知我意", "深蓝褪色", "剑走偏锋", "落日弧线",
    "青雀", "旧梦拾遗", "沙罗双树", "光之尽头", "雪原行者", "长夜未央",
    "橘子汽水", "第七封印", "白鸦", "锈色黎明", "群青", "拂晓之刃",
    "山海不可平", "静默星轨", "碎冰蓝", "风起时", "无声告白", "黑猫警长",
    "十万伏特", "月下独酌", "远行客",
]


def now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise SystemExit(f"找不到数据库: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rank_point_for_degree(degree: int) -> int:
    """给定想要显示的 RANK,返回刚好够到它的 rank_point。"""
    table = json.loads(RANK_TABLE_JSON.read_text(encoding="utf-8"))
    thresholds = {int(k): int(v[0][1]) for k, v in table.items()}
    if degree in thresholds:
        return thresholds[degree]
    # 表里没有这一级就退到不超过它的最大一级
    lower = [d for d in sorted(thresholds) if d <= degree]
    return thresholds[lower[-1]] if lower else 0


def playable_pool() -> list[int]:
    """可下发的 5★ 角色 ID(排除助战段)。"""
    data = json.loads(CHARACTER_JSON.read_text(encoding="utf-8"))
    ids = []
    for key, row in data.items():
        try:
            cid = int(key)
        except ValueError:
            continue
        if cid < 100000:
            continue
        if SUPPORT_ID_MIN <= cid <= SUPPORT_ID_MAX:
            continue
        if int(row.get("rarity", 0)) != 5:
            continue
        ids.append(cid)
    ids.sort()
    if len(ids) < 3:
        raise SystemExit("可用 5★ 角色不足 3 个,无法组队")
    return ids


def bot_account_id(conn: sqlite3.Connection, create: bool = False) -> int | None:
    row = conn.execute(
        "SELECT id FROM accounts WHERE idp_code = ? ORDER BY id LIMIT 1", (BOT_IDP_CODE,)
    ).fetchone()
    if row is not None:
        return int(row["id"])
    if not create:
        return None
    stamp = iso_now()
    cur = conn.execute(
        """INSERT INTO accounts
           (app_id, first_login_time, idp_alias, idp_code, idp_id, reg_time,
            last_login_time, status, username, password_hash)
           VALUES (?, ?, '', ?, '', ?, ?, 'normal', NULL, NULL)""",
        (BOT_ACCOUNT_APP_ID, stamp, BOT_IDP_CODE, stamp, stamp),
    )
    return int(cur.lastrowid)


def backup_db(tag: str) -> Path:
    """写库前先做一份一致的联机备份,返回备份路径。

    用 sqlite3 的联机备份 API 而不是 `shutil.copy`:服务端可能正开着这个库
    (WAL 模式下裸拷贝会拿到一份缺 -wal 的残本)。
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = DB_PATH.with_name(f"{DB_PATH.name}.bak-{tag}-{stamp}")
    src = sqlite3.connect(str(DB_PATH), timeout=15)
    dst = sqlite3.connect(str(dest))
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dest


def write_bot_party(
    conn: sqlite3.Connection, player_id: int, party: list[int]
) -> bool:
    """给一个 bot 存档写上编队行(**幂等**:已经有就原样不动)。

    `INSERT OR IGNORE` 而不是 upsert —— 存量 bot 万一已经被手工改过编队,
    这里不许把它覆盖回去。两张表的主键分别是
    (id, player_id, category) 与 (slot, player_id, group_id, category)。

    :returns: 这次是否真的插进了一行 players_parties。
    """
    conn.execute(
        """INSERT OR IGNORE INTO players_party_groups (id, color_id, player_id, category)
           VALUES (?, ?, ?, 1)""",
        (BOT_PARTY_GROUP_ID, BOT_PARTY_COLOR_ID, player_id),
    )
    cur = conn.execute(
        """INSERT OR IGNORE INTO players_parties
               (slot, name, character_id_1, character_id_2, character_id_3,
                unison_character_1, unison_character_2, unison_character_3,
                equipment_1, equipment_2, equipment_3,
                ability_soul_1, ability_soul_2, ability_soul_3,
                edited, current_battle_power, before_battle_power,
                player_id, group_id, category)
           VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL,
                   NULL, NULL, NULL, 0, 0, 0, ?, ?, 1)""",
        (BOT_PARTY_SLOT, BOT_PARTY_NAME, party[0], party[1], party[2],
         player_id, BOT_PARTY_GROUP_ID),
    )
    return cur.rowcount > 0


def bot_run_party(conn: sqlite3.Connection, player_id: int) -> list[int] | None:
    """存量 bot 的编队从**它自己那条成绩行**里取(最新一条)。

    这样「榜行(快照兜底)」和「资料页(编队)」画的是同一支队伍,
    补编队不会让榜面上任何一个头像发生变化。
    """
    row = conn.execute(
        """SELECT character_id_1, character_id_2, character_id_3
           FROM players_rush_event_runs
           WHERE player_id = ? AND character_id_1 IS NOT NULL
           ORDER BY id DESC LIMIT 1""",
        (player_id,),
    ).fetchone()
    if row is None:
        return None
    return [row[0], row[1], row[2]]


def bot_player_ids(conn: sqlite3.Connection) -> list[int]:
    acc = bot_account_id(conn)
    if acc is None:
        return []
    return [int(r["id"]) for r in conn.execute(
        "SELECT id FROM players WHERE account_id = ? ORDER BY id", (acc,)
    )]


def current_season(conn: sqlite3.Connection, event_id: int) -> int:
    row = conn.execute(
        "SELECT MAX(season) AS s FROM rush_event_seasons WHERE event_id = ?", (event_id,)
    ).fetchone()
    return int(row["s"]) if row and row["s"] is not None else 1


def season_started_at(conn: sqlite3.Connection, event_id: int, season: int) -> int:
    row = conn.execute(
        "SELECT started_at_ms FROM rush_event_seasons WHERE event_id = ? AND season = ?",
        (event_id, season),
    ).fetchone()
    return int(row["started_at_ms"]) if row else now_ms() - 7 * 86_400_000


def default_folder(conn: sqlite3.Connection, event_id: int) -> int:
    row = conn.execute(
        "SELECT folder_id FROM rush_settlement_config WHERE event_id = ? LIMIT 1", (event_id,)
    ).fetchone()
    if row is not None:
        return int(row["folder_id"])
    row = conn.execute(
        "SELECT folder_id FROM players_rush_event_runs WHERE event_id = ? ORDER BY id DESC LIMIT 1",
        (event_id,),
    ).fetchone()
    return int(row["folder_id"]) if row is not None else 1


def total_rounds(conn: sqlite3.Connection, event_id: int, folder_id: int) -> int:
    row = conn.execute(
        """SELECT total_rounds FROM players_rush_event_runs
           WHERE event_id = ? AND folder_id = ? AND total_rounds > 0
           ORDER BY id DESC LIMIT 1""",
        (event_id, folder_id),
    ).fetchone()
    return int(row["total_rounds"]) if row is not None else 30


def human_ms(ms: int | None) -> str:
    if ms is None:
        return "--:--.--"
    total_cs = ms // 10
    return f"{total_cs // 6000:02d}:{(total_cs // 100) % 60:02d}.{total_cs % 100:02d}"


def cmd_list(args: argparse.Namespace) -> int:
    conn = connect()
    event_id = args.event
    folder_id = args.folder if args.folder is not None else default_folder(conn, event_id)
    bots = set(bot_player_ids(conn))
    print(f"事件 {event_id} / folder {folder_id} / 当前期 {current_season(conn, event_id)}")
    print(f"bot 存档 {len(bots)} 个\n")
    # 排序口径 = 30 关结算时间之和(battle_ms),与作者 2026-08-28 的裁定一致。
    print("排行榜(按存档去重,每档只留最好的一次;排序 = 30 关结算时间之和):")
    rows = conn.execute(
        """SELECT r.player_id, r.player_name, p.name AS live_name, r.duration_ms, r.battle_ms,
                  r.rounds_cleared, r.season, MIN(r.battle_ms) AS best
           FROM players_rush_event_runs r
           LEFT JOIN players p ON p.id = r.player_id
           WHERE r.event_id = ? AND r.folder_id = ?
             AND r.status = 'completed' AND r.tracked_from_round = 1
             AND r.battle_ms > 0
           GROUP BY r.player_id
           ORDER BY best ASC""",
        (event_id, folder_id),
    ).fetchall()
    for i, r in enumerate(rows, 1):
        tag = "bot" if r["player_id"] in bots else "   "
        name = r["live_name"] or r["player_name"] or f"存档{r['player_id']}"
        print(f"  {i:3d}位 {tag} {name:26s} 30关总和 {human_ms(r['best'])}"
              f"  (墙钟 {human_ms(r['duration_ms'])})  {r['rounds_cleared']}战  第{r['season']}期")
    print(f"\n合计 {len(rows)} 行(其中 bot {sum(1 for r in rows if r['player_id'] in bots)} 行)")
    conn.close()
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    conn = connect()
    event_id = args.event
    folder_id = args.folder if args.folder is not None else default_folder(conn, event_id)
    season = args.season if args.season is not None else current_season(conn, event_id)
    rounds = args.rounds if args.rounds is not None else total_rounds(conn, event_id, folder_id)

    row = conn.execute(
        """SELECT MIN(battle_ms) AS best FROM players_rush_event_runs
           WHERE event_id = ? AND folder_id = ? AND status = 'completed'
             AND tracked_from_round = 1 AND battle_ms > 0""",
        (event_id, folder_id),
    ).fetchone()
    best = int(row["best"]) if row and row["best"] is not None else None

    lo = args.min_ms
    hi = args.max_ms
    if lo is None:
        # 默认不抢作者的名次:最快的 bot 的**净战斗用时**也比现有最好成绩慢 5 秒
        lo = 3 * 60_000 if best is None else (best + 5_000)
        if args.allow_faster and best is not None:
            lo = max(45_000, best - 45_000)
    if hi is None:
        hi = lo + 225_000
    if hi <= lo:
        raise SystemExit(f"--max-ms({hi}) 必须大于 --min-ms({lo})")

    used_names = {r["name"] for r in conn.execute("SELECT name FROM players")}
    free_names = [n for n in NAME_POOL if n not in used_names]
    if len(free_names) < args.count:
        raise SystemExit(f"名字池只剩 {len(free_names)} 个可用,少于要建的 {args.count} 个")

    pool = playable_pool()
    acc = bot_account_id(conn, create=True)
    season_start = season_started_at(conn, event_id, season)
    latest = now_ms()

    created = []
    with conn:
        for i in range(args.count):
            name = free_names[i]
            rng = random.Random(f"{name}|{event_id}|{folder_id}|{season}")
            degree = rng.randint(args.min_rank, args.max_rank)
            # 主值 = 净战斗用时(榜上排的那个);全程用时由它反推,只作陪衬。
            battle = lo + int((hi - lo) * ((i + 0.5) / args.count)) + rng.randint(-4_000, 4_000)
            battle = max(45_000, battle)
            duration = int(battle / BATTLE_RATIO) + rng.randint(-3_000, 3_000)
            duration = max(battle + 1_000, duration)
            finished = rng.randint(season_start + 60_000, max(season_start + 120_000, latest - 60_000))
            started = finished - duration
            if started < season_start:
                started = season_start
                finished = started + duration
            party = rng.sample(pool, 3)

            cur = conn.execute(
                """INSERT INTO players (stamina, stamina_heal_time, boost_point, boss_boost_point,
                        transition_state, role, name, last_login_time, comment, vmoney, free_vmoney,
                        rank_point, star_crumb, bond_token, exp_pool, exp_pooled_time,
                        leader_character_id, party_slot, degree_id, birth, free_mana, paid_mana,
                        enable_auto_3x, account_id, tutorial_step, tutorial_skip_flag)
                   VALUES (125, 0, 0, 0, 0, 1, ?, ?, '', 0, 0, ?, 0, 0, 0, 0, ?, 1, 1, 0, 0, 0, 0, ?, 6, 1)""",
                (name, iso_now(), rank_point_for_degree(degree), party[0], acc),
            )
            player_id = int(cur.lastrowid)
            # 编队行:榜行头像优先画「个人资料里的前三个角色」,不写这一行的话
            # bot 的榜行(快照兜底)和资料页(leader 兜底)会画出两支不同的队伍。
            write_bot_party(conn, player_id, party)
            conn.execute(
                """INSERT INTO players_rush_event_runs
                   (player_id, player_name, event_id, folder_id, season, status,
                    started_at_ms, finished_at_ms, ended_at_ms, duration_ms, battle_ms,
                    rounds_cleared, total_rounds, tracked_from_round,
                    character_id_1, character_id_2, character_id_3,
                    unison_character_id_1, unison_character_id_2, unison_character_id_3)
                   VALUES (?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, NULL, NULL, NULL)""",
                (player_id, name, event_id, folder_id, season, started, finished, finished,
                 duration, battle, rounds, rounds, party[0], party[1], party[2]),
            )
            created.append((player_id, name, degree, duration, battle, party))

    print(f"已新建 {len(created)} 个 bot 存档 + 成绩(账号 #{acc},事件 {event_id}/folder {folder_id}/第{season}期):")
    for player_id, name, degree, duration, battle, party in created:
        print(f"  存档#{player_id:<5d} {name:12s} RANK{degree:<4d} 30关总和 {human_ms(battle)}"
              f"  (墙钟 {human_ms(duration)})  队伍 {party}")
    conn.close()
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    if args.confirm != "CLEAR_RUSH_BOTS":
        raise SystemExit("需要 --confirm CLEAR_RUSH_BOTS 才会真的删除")
    conn = connect()
    ids = bot_player_ids(conn)
    if not ids:
        print("没有 bot 存档,无事可做")
        conn.close()
        return 0
    marks = ",".join("?" * len(ids))
    with conn:
        runs = conn.execute(
            f"DELETE FROM players_rush_event_runs WHERE player_id IN ({marks})", ids
        ).rowcount
        conn.execute(f"DELETE FROM players_rush_events WHERE player_id IN ({marks})", ids)
        conn.execute(f"DELETE FROM players_rush_events_played_parties WHERE player_id IN ({marks})", ids)
        conn.execute(f"DELETE FROM players_rush_events_cleared_folders WHERE player_id IN ({marks})", ids)
        # 编队两张表都挂了 players 的 ON DELETE CASCADE,但本进程开了
        # `PRAGMA foreign_keys = ON` 才有级联 —— 显式删一次,别把清理押在 pragma 上。
        conn.execute(f"DELETE FROM players_parties WHERE player_id IN ({marks})", ids)
        conn.execute(f"DELETE FROM players_party_groups WHERE player_id IN ({marks})", ids)
        conn.execute(f"DELETE FROM players WHERE id IN ({marks})", ids)
        acc = bot_account_id(conn)
        if acc is not None:
            left = conn.execute("SELECT COUNT(*) AS n FROM players WHERE account_id = ?", (acc,)).fetchone()
            if int(left["n"]) == 0:
                conn.execute("DELETE FROM accounts WHERE id = ?", (acc,))
    print(f"已删除 {len(ids)} 个 bot 存档、{runs} 条成绩")
    conn.close()
    return 0


def cmd_backfill_parties(args: argparse.Namespace) -> int:
    """给**存量** bot 补编队行。

    只碰 `accounts.idp_code = 'rushbot'` 名下的存档,只 INSERT OR IGNORE,
    真写之前先做一份联机备份。刻意**不用** clear+add 重建 —— 那会把 bot 的
    名次和用时全部重摇一遍,榜面当场变样。
    """
    conn = connect()
    try:
        ids = bot_player_ids(conn)
        if not ids:
            print("没有 bot 存档(accounts.idp_code='rushbot'),无事可做")
            return 0

        # 判据是「该存档有没有**任意** category=1 编队」,不是「group1/slot1 有没有」。
        # 这一条要和服务端 `rush-leaderboard-agreement.ts::pickParty` 对齐:那边是
        # 「先按 party_slot 精确取,取不到就用最小 group 的最小 slot」(和个人资料页
        # 逐条相同)。⇒ 只要该存档有任意一支普通编队,榜行和资料页画的就是同一支,
        # 补不补 group1/slot1 都不会出现两屏不一致。改那边的兜底就要回来改这里。
        marks = ",".join("?" * len(ids))
        have = {int(r["player_id"]) for r in conn.execute(
            f"SELECT DISTINCT player_id FROM players_parties "
            f"WHERE player_id IN ({marks}) AND category = 1", ids)}
        todo = []
        skipped = []
        for player_id in ids:
            if player_id in have:
                skipped.append(player_id)
                continue
            party = bot_run_party(conn, player_id)
            if party is None:
                print(f"  存档#{player_id}: 没有带队伍的成绩行,跳过")
                continue
            todo.append((player_id, party))

        print(f"bot 存档 {len(ids)} 个:已有编队 {len(skipped)} 个,待补 {len(todo)} 个")
        for player_id, party in todo:
            print(f"  存档#{player_id:<5d} → 编队 {party}")

        if not args.apply:
            print("[DRY-RUN] 未写库。加 --apply 真写(会先自动备份)。")
            return 0
        if not todo:
            print("没有要补的行,不写库、不备份。")
            return 0

        backup = backup_db("rushbot-parties")
        print(f"已备份数据库 → {backup}")
        written = 0
        with conn:
            for player_id, party in todo:
                if write_bot_party(conn, player_id, party):
                    written += 1
        print(f"补齐 {written} 个 bot 的编队行(幂等:再跑一次是 0 行)")
        return 0
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("list", "add", "clear", "backfill-parties"):
        child = sub.add_parser(name)
        child.add_argument("--event", type=int, default=DEFAULT_EVENT_ID)
        child.add_argument("--folder", type=int, default=None)
        if name == "backfill-parties":
            child.add_argument("--apply", action="store_true",
                               help="真写库(默认只预览)。写之前会自动做一份联机备份")
        if name == "add":
            child.add_argument("--count", type=int, default=14)
            child.add_argument("--season", type=int, default=None)
            child.add_argument("--rounds", type=int, default=None)
            child.add_argument("--min-ms", type=int, default=None,
                               help="最快 bot 的净战斗用时(毫秒,榜上排的那个);默认比现有最好成绩慢 5 秒")
            child.add_argument("--max-ms", type=int, default=None)
            child.add_argument("--allow-faster", action="store_true",
                               help="允许 bot 快过现有最好成绩(默认不允许)")
            child.add_argument("--min-rank", type=int, default=150)
            child.add_argument("--max-rank", type=int, default=250)
        if name == "clear":
            child.add_argument("--confirm", default="")

    args = parser.parse_args(argv)
    return {
        "list": cmd_list,
        "add": cmd_add,
        "clear": cmd_clear,
        "backfill-parties": cmd_backfill_parties,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

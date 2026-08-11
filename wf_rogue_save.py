#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""wf_rogue_save.py — 生成 Roguelike 专用存档(独立武器池)。

克隆指定存档 → 清空全部武器(players_equipment)+ 清空魂珠道具
(players_items 中 item.category==5 的 436 键,清单 assets/soul_item_ids.json;
魂珠持有判定读道具背包,OwnedAbilitySoulRepository 实证)+ 洗掉编队里的装备/魂珠引用
(players_parties.equipment_1..3 / ability_soul_1..3)→ 角色/练度/其余道具全保留。
配合 assets/rogue_event.json 的每轮掉落:开局武器栏为空,掉什么用什么 = 独立武器池。

用法(项目根运行):
  python mod-tools/wf_rogue_save.py --source 8              # dry-run 预览
  python mod-tools/wf_rogue_save.py --source 8 --apply      # 执行
  python mod-tools/wf_rogue_save.py --reset 10 --apply      # 重置一局:清武器/魂珠/rush进度
  python mod-tools/wf_rogue_save.py --reset 10 --random-boss --restart-game --apply
      # 一条命令整局重开:杀游戏→清状态→随机换无尽boss战场(发布)→拉起游戏
选项:
  --name <存档名>    默认 肉鸽空武器
  --server <url>     默认 WF_SERVER_URL,再读项目 .env,最后回退 127.0.0.1:8001
  --keep-active      克隆后默认存档留在新档(默认会切回原存档,防止误登)
  --reset <id>       不克隆,直接重置指定存档的 run 状态(装备/魂珠道具/编队引用/
                     rush 活动进度与已用队伍全清,角色练度与其余道具保留);改后重启游戏生效

注意:cloneSave 接口会把账号默认存档切到新克隆,本工具默认随后切回 --source;
开一局 run = admin 后台把默认存档切到肉鸽档 → 重启游戏。
"""
import argparse
import csv
import io
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Mapping
from pathlib import Path

import wf_server_auth
import wf_database_paths
import wf_device_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _explicit_path(environment: Mapping[str, str], key: str) -> Path | None:
    raw = environment.get(key)
    if raw is None:
        return None
    if not raw.strip():
        raise ValueError(f"{key} must be a non-empty path")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise ValueError(f"{key} must be an absolute path: {raw}")
    return candidate.resolve()


def resolve_database_path(
        environment: Mapping[str, str] = os.environ,
        *, server_root: Path | str = ROOT) -> Path:
    return wf_database_paths.resolve_database_path(
        environment,
        server_root=server_root,
    )


def resolve_mumu_manager(
        environment: Mapping[str, str] = os.environ,
        *, finder=shutil.which) -> Path | None:
    """Resolve optional MuMuManager without assuming a maintainer workspace."""
    return wf_device_paths.find_mumu_manager(environment, finder=finder)


DB_PATH = os.fspath(resolve_database_path())
WF_PACKAGE = "com.leiting.wf"
WF_ACTIVITY = "com.leiting.wf/com.leiting.sdk.activity.PrivacyActivity"
RUSH_QUEST_LOGICAL = "master/quest/event/rush_event_quest.orderedmap"
ENDLESS_EVENT = "700099"
ENDLESS_QUEST_NO = "99"


def validate_endless_target(event: str, quest_no: str) -> None:
    """随机 boss 仅允许自制 700099 的无尽层 99。"""
    if str(event) != ENDLESS_EVENT or str(quest_no) != ENDLESS_QUEST_NO:
        raise ValueError(
            f"无尽重摇只允许 {ENDLESS_EVENT}/{ENDLESS_QUEST_NO},"
            f"拒绝目标 {event}/{quest_no}")


def api_post(server: str, path: str, query: str = "", body: dict | None = None) -> dict:
    url = f"{server}{path}" + (f"?{query}" if query else "")
    data = json.dumps(body).encode("utf-8") if body is not None else b""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **wf_server_auth.admin_bearer_headers(Path(ROOT)),
    }
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_soul_ids() -> list[int]:
    soul_json = os.path.join(ROOT, "assets", "soul_item_ids.json")
    try:
        with open(soul_json, encoding="utf-8") as fh:
            return [int(x) for x in json.load(fh)]
    except OSError:
        print(f"[WARN] {soul_json} 不存在,跳过魂珠清理(魂珠会全解锁!)")
        return []


def mumu_sh(cmd: str) -> None:
    manager = resolve_mumu_manager()
    if manager is None:
        raise RuntimeError(
            "MuMuManager was not found; set WF_MUMU_MANAGER to an absolute executable path"
        )
    subprocess.run([os.fspath(manager), "sh", "-v", "1", "-c", cmd], capture_output=True)


def _publish_command(logicals: tuple[str, ...], *, list_only: bool = False) \
        -> list[str]:
    if not logicals or logicals[-1] != RUSH_QUEST_LOGICAL:
        raise ValueError("无尽层发布闭包必须 dependency-first 且 rush quest 最后")
    command = [
        sys.executable, os.path.join(ROOT, "mod-tools", "wf_publish.py"),
        "--tables", ",".join(logicals),
    ]
    if list_only:
        command.append("--list")
    return command


def _restore_exact_bytes(path: Path, original: bytes) -> None:
    """同目录原子恢复 store 原字节，并复读确认。"""
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".reroll-rollback", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if path.read_bytes() != original:
            raise RuntimeError(f"无尽层 store 回滚复读不一致:{path}")
    finally:
        temporary.unlink(missing_ok=True)


def reroll_endless_field(event: str, quest_no: str, apply: bool) -> None:
    """把 700099/99 投影到正式构建器筛后的原生 boss bundle。"""
    validate_endless_target(event, quest_no)

    sys.path.insert(0, os.path.join(ROOT, "mod-tools"))
    import wf_quest_lib as q
    import wf_rogue_build as rb

    quest_path = q.store_path(RUSH_QUEST_LOGICAL)
    original_bytes = quest_path.read_bytes()
    tree = q.load_table(RUSH_QUEST_LOGICAL, path=quest_path)
    if q.parse_node(original_bytes) != tree:
        raise RuntimeError("rush quest 加载结果与写前原字节不一致")
    try:
        leaf = tree[ENDLESS_EVENT][ENDLESS_QUEST_NO]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"rush quest 缺目标 {ENDLESS_EVENT}/{ENDLESS_QUEST_NO}") from exc
    was_bytes = isinstance(leaf, bytes)
    line = leaf.decode("utf-8") if was_bytes else leaf
    row = next(csv.reader(io.StringIO(line)))
    if len(row) <= 99:
        raise ValueError(f"rush quest {ENDLESS_EVENT}/{ENDLESS_QUEST_NO} 行过短:{len(row)}")
    try:
        enemy_level = int(row[95])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"rush quest {ENDLESS_EVENT}/{ENDLESS_QUEST_NO} c95 敌等级非法:"
            f"{row[95]!r}") from exc

    bundle = rb.choose_endless_native_bundle(random, enemy_level=enemy_level)
    bosses = rb.native_bundle_bosses(bundle)
    if not bosses:
        raise RuntimeError(f"筛后 bundle 没有 active single boss:{bundle.source_field}")
    before = {index: row[index] for index in (5, 69, 95, 98, 99)}
    rb.patch_quest_boss_fields(
        row,
        field=bundle.source_field,
        bosses=bosses,
        thumbnail=bundle.thumbnail,
        bgm=bundle.bgm,
        enemy_level=enemy_level,
        rng=random,
        require_bgm=True,
    )
    print(f"随机战场: {before[98]} -> {row[98]}"
          f"(BGM {row[99]};boss: {','.join(bosses)};lv{row[95]})")
    if not apply:
        return
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(row)
    tree[ENDLESS_EVENT][ENDLESS_QUEST_NO] = (
        buf.getvalue().encode("utf-8") if was_bytes else buf.getvalue())
    publish_items = rb.endless_bundle_publish_logicals(bundle)
    intended_bytes = q.build_node(tree)
    if q.parse_node(intended_bytes) != tree:
        raise RuntimeError("rush quest 拟写字节 build→parse 不等价")

    publish_env = dict(os.environ)
    publish_env["WF_TARGET_STORE"] = str(quest_path.parent.parent.resolve())
    preflight = subprocess.run(
        _publish_command(publish_items, list_only=True), cwd=ROOT,
        env=publish_env)
    print(f"[PREFLIGHT] wf_publish --list 退出码 {preflight.returncode}")
    if preflight.returncode != 0:
        raise RuntimeError(
            f"无尽层发布预检失败:wf_publish --list 退出码 {preflight.returncode}")

    try:
        out = q.save_table(RUSH_QUEST_LOGICAL, tree, path=quest_path)
        if Path(out).read_bytes() != intended_bytes:
            raise RuntimeError(f"rush quest 写后复读与拟写字节不一致:{out}")
        print(f"[OK] 已写入 {out}")
        published = subprocess.run(
            _publish_command(publish_items), cwd=ROOT, env=publish_env)
        print(f"[PUBLISH] wf_publish 退出码 {published.returncode}")
        if published.returncode != 0:
            raise RuntimeError(
                f"无尽层发布失败:wf_publish 退出码 {published.returncode}")
    except Exception as exc:
        try:
            _restore_exact_bytes(quest_path, original_bytes)
        except Exception as rollback_exc:
            raise RuntimeError(
                f"无尽层写入/发布失败({exc});store 回滚失败:{rollback_exc}") \
                from exc
        raise


def reset_run(db: sqlite3.Connection, player_id: int, apply: bool) -> int:
    row = db.execute("SELECT id, name FROM players WHERE id=?", (player_id,)).fetchone()
    if row is None:
        print(f"[ERR] 存档 player_id={player_id} 不存在")
        return 1
    soul_ids = load_soul_ids()
    n_equip = db.execute("SELECT COUNT(*) FROM players_equipment WHERE player_id=?", (player_id,)).fetchone()[0]
    n_rush = db.execute("SELECT COUNT(*) FROM players_rush_events WHERE player_id=?", (player_id,)).fetchone()[0]
    n_played = db.execute("SELECT COUNT(*) FROM players_rush_events_played_parties WHERE player_id=?", (player_id,)).fetchone()[0]
    print(f"重置目标: id={player_id} 名={row[1]} — 装备{n_equip} rush状态{n_rush} 已用队伍{n_played}")
    print("⚠ 先关闭游戏再重置!局内继续打会把掉落/进度重新写回(force-stop: "
          'MuMuManager.exe sh -v 1 -c "am force-stop com.leiting.wf")')
    if not apply:
        print("[DRY-RUN] 未执行。加 --apply 生效。")
        return 0
    with db:
        db.execute("DELETE FROM players_equipment WHERE player_id=?", (player_id,))
        if soul_ids:
            placeholders = ",".join("?" * len(soul_ids))
            db.execute(f"DELETE FROM players_items WHERE player_id=? AND id IN ({placeholders})", (player_id, *soul_ids))
        db.execute(
            "UPDATE players_parties SET equipment_1=NULL, equipment_2=NULL, equipment_3=NULL,"
            " ability_soul_1=NULL, ability_soul_2=NULL, ability_soul_3=NULL WHERE player_id=?",
            (player_id,),
        )
        db.execute("DELETE FROM players_rush_events WHERE player_id=?", (player_id,))
        db.execute("DELETE FROM players_rush_events_played_parties WHERE player_id=?", (player_id,))
        db.execute("DELETE FROM players_rush_events_cleared_folders WHERE player_id=?", (player_id,))
    print("[OK] run 已重置(装备/魂珠/编队引用/rush 进度全清)。重启游戏生效。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="生成/重置 Roguelike 空武器存档")
    ap.add_argument("--source", type=int, help="源存档 player_id(克隆模式)")
    ap.add_argument("--reset", type=int, help="重置指定存档的 run 状态(不克隆)")
    ap.add_argument("--random-boss", action="store_true",
                    help="重置时随机换无尽战场(连战塔素材池重摇+发布)= 每局随机 boss")
    ap.add_argument("--restart-game", action="store_true",
                    help="重置前 force-stop 游戏、重置后自动拉起(MuMuManager 通道)")
    ap.add_argument("--event", default=ENDLESS_EVENT, help="rush 活动 id(--random-boss 固定 700099)")
    ap.add_argument("--quest-no", default=ENDLESS_QUEST_NO,
                    help="无尽 quest 在活动内的序号键(--random-boss 固定 99)")
    ap.add_argument("--name", default="肉鸽空武器", help="新存档名")
    ap.add_argument("--server", default=wf_server_auth.resolve_server_url(Path(ROOT)))
    ap.add_argument("--apply", action="store_true", help="真执行(默认 dry-run)")
    ap.add_argument("--keep-active", action="store_true", help="默认存档留在新档")
    args = ap.parse_args()

    if args.random_boss:
        validate_endless_target(args.event, args.quest_no)

    if args.reset is not None:
        if args.restart_game and args.apply:
            print("[GAME] force-stop …")
            mumu_sh(f"am force-stop {WF_PACKAGE}")
        db = sqlite3.connect(DB_PATH, timeout=15)
        db.execute("PRAGMA busy_timeout=15000")
        try:
            code = reset_run(db, args.reset, args.apply)
        finally:
            db.close()
        if code == 0 and args.random_boss:
            reroll_endless_field(args.event, args.quest_no, args.apply)
        if code == 0 and args.restart_game and args.apply:
            print("[GAME] 拉起游戏 …")
            mumu_sh(f"am start -n {WF_ACTIVITY}")
        return code

    if args.source is None:
        ap.error("--source 或 --reset 必须给一个")

    db = sqlite3.connect(DB_PATH, timeout=15)
    db.execute("PRAGMA busy_timeout=15000")
    try:
        row = db.execute(
            "SELECT id, account_id, name FROM players WHERE id=?", (args.source,)
        ).fetchone()
        if row is None:
            print(f"[ERR] 源存档 player_id={args.source} 不存在")
            return 1
        pid, account_id, name = row
        n_equip = db.execute(
            "SELECT COUNT(*) FROM players_equipment WHERE player_id=?", (pid,)
        ).fetchone()[0]
        n_char = db.execute(
            "SELECT COUNT(*) FROM players_characters WHERE player_id=?", (pid,)
        ).fetchone()[0]
        n_party = db.execute(
            "SELECT COUNT(*) FROM players_parties WHERE player_id=?", (pid,)
        ).fetchone()[0]
        print(f"源存档: id={pid} 名={name} 账号={account_id} 角色={n_char} 装备={n_equip} 编队行={n_party}")
        print(f"计划: 克隆 → 新档清空 {n_equip} 件装备 + 洗 {n_party} 行编队装备/魂珠引用 → 改名「{args.name}」"
              + ("(默认存档留在新档)" if args.keep_active else f" → 默认存档切回 {pid}"))

        if not args.apply:
            print("[DRY-RUN] 未执行。加 --apply 生效。")
            return 0

        # 1. 克隆(服务端接口,完整复制;副作用=默认存档切到新档)
        r = api_post(args.server, "/api/server/cloneSave", f"playerId={pid}&accountId={account_id}")
        if not r.get("ok"):
            print(f"[ERR] cloneSave 失败: {r}")
            return 1
        new_id = int(r["newPlayerId"])
        print(f"[OK] 克隆完成 → 新存档 player_id={new_id}")

        # 2. 清装备 + 清魂珠道具 + 洗编队引用(短事务,WAL 下与运行中的服务端共存)
        soul_ids = load_soul_ids()
        with db:
            deleted = db.execute(
                "DELETE FROM players_equipment WHERE player_id=?", (new_id,)
            ).rowcount
            souls_deleted = 0
            if soul_ids:
                placeholders = ",".join("?" * len(soul_ids))
                souls_deleted = db.execute(
                    f"DELETE FROM players_items WHERE player_id=? AND id IN ({placeholders})",
                    (new_id, *soul_ids),
                ).rowcount
            scrubbed = db.execute(
                "UPDATE players_parties SET equipment_1=NULL, equipment_2=NULL, equipment_3=NULL,"
                " ability_soul_1=NULL, ability_soul_2=NULL, ability_soul_3=NULL WHERE player_id=?",
                (new_id,),
            ).rowcount
        print(f"[OK] 清空装备 {deleted} 件;清空魂珠道具 {souls_deleted} 个;编队洗引用 {scrubbed} 行")

        # 3. 改名
        r = api_post(args.server, "/api/server/renameSave", body={"playerId": new_id, "name": args.name})
        print(f"[OK] 改名 → {args.name}" if r.get("ok") else f"[WARN] 改名失败: {r}")

        # 4. 默认存档切回源(除非 --keep-active)
        if not args.keep_active:
            r = api_post(args.server, "/api/server/activateSave", f"playerId={pid}")
            print(f"[OK] 默认存档切回 {pid}" if r.get("ok") else f"[WARN] 切回失败: {r}")

        print()
        print("=== 开一局 run ===")
        print(f"1. admin 后台(/admin)账号页把默认存档切到「{args.name}」(id={new_id}),重启游戏;")
        print("2. 进狂热激战(rogue_event.json 已配掉落),武器栏为空,掉什么用什么;")
        print(f"3. run 结束后默认存档切回 {pid},重启游戏。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

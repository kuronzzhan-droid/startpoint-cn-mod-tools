# -*- coding: utf-8 -*-
"""深渊连战排行榜两个工具侧改动的测试(2026-08-28)。

覆盖的是「不做就静默不生效」的那两件事:

1. **重摇塔要换期**(`wf_rogue_reroll.py`)。
   作者惯用的重摇入口是 GUI「一键重开」/ 命令行,两条路都**绕开 8001**
   (`mod-tools/wf_gui.py:7766` 直接拉子进程),所以服务端 `/rush_event/reset`
   上那个换期钩子永远不触发;指纹兜底在默认 `--rounds 30` 下也不变。
   期号不推进 = 战斗用时榜(只列当期)永远挂着旧塔的排行。

2. **bot 要有编队行**(`wf_rush_bots.py`)。
   榜行头像优先画「个人资料里的前三个角色」,bot 没编队时榜行靠快照兜底还是
   三个头像,但点进资料页只剩一个 —— 两屏不一致。
"""
from __future__ import annotations

import argparse
import io
import json
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_rogue_reroll as reroll  # noqa: E402
import wf_rush_bots as bots  # noqa: E402


def make_db(path: Path) -> sqlite3.Connection:
    """建一个只含本测试要用的那几张表的库(列定义抄 src/data/initializers)。"""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE rush_event_seasons (
            event_id INTEGER PRIMARY KEY,
            season INTEGER NOT NULL,
            started_at_ms INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            source TEXT NOT NULL
        );
        CREATE TABLE players_rush_event_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            ended_at_ms INTEGER,
            character_id_1 INTEGER,
            character_id_2 INTEGER,
            character_id_3 INTEGER
        );
        CREATE TABLE players_rush_events (
            player_id INTEGER NOT NULL, event_id INTEGER NOT NULL
        );
        CREATE TABLE players_rush_events_played_parties (
            player_id INTEGER NOT NULL, event_id INTEGER NOT NULL
        );
        CREATE TABLE players_rush_events_cleared_folders (
            player_id INTEGER NOT NULL, event_id INTEGER NOT NULL
        );
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idp_code TEXT NOT NULL
        );
        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            account_id INTEGER NOT NULL
        );
        CREATE TABLE players_party_groups (
            id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            category INTEGER NOT NULL,
            PRIMARY KEY (id, player_id, category)
        );
        CREATE TABLE players_parties (
            slot INTEGER NOT NULL,
            name TEXT NOT NULL,
            character_id_1 INTEGER,
            character_id_2 INTEGER,
            character_id_3 INTEGER,
            unison_character_1 INTEGER,
            unison_character_2 INTEGER,
            unison_character_3 INTEGER,
            equipment_1 INTEGER,
            equipment_2 INTEGER,
            equipment_3 INTEGER,
            ability_soul_1 INTEGER,
            ability_soul_2 INTEGER,
            ability_soul_3 INTEGER,
            edited INTEGER NOT NULL,
            current_battle_power INTEGER NOT NULL DEFAULT 0,
            before_battle_power INTEGER NOT NULL DEFAULT 0,
            player_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            category INTEGER NOT NULL,
            PRIMARY KEY (slot, player_id, group_id, category)
        );
        """
    )
    conn.commit()
    return conn


class RerollSeasonTest(unittest.TestCase):
    """`wf_rogue_reroll.rollover_season` —— 重摇塔换期。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = make_db(Path(self.tmp.name) / "t.db")

    def tearDown(self) -> None:
        self.db.close()
        self.tmp.cleanup()

    def test_first_rollover_creates_season_1(self) -> None:
        season, abandoned = reroll.rollover_season(self.db, "700099", 1000)
        self.assertEqual(season, 1)
        self.assertEqual(abandoned, 0)
        row = self.db.execute(
            "SELECT * FROM rush_event_seasons WHERE event_id = 700099").fetchone()
        self.assertEqual(row["season"], 1)
        self.assertEqual(row["started_at_ms"], 1000)
        self.assertEqual(row["source"], "reroll-cli")

    def test_rollover_increments_and_abandons_active_runs(self) -> None:
        """期号 +1 且作废进行中的 run —— 与服务端 rolloverRushSeason() 同语义。"""
        self.db.execute(
            "INSERT INTO rush_event_seasons VALUES (700099, 4, 1, 'x', 'admin-manual')")
        self.db.execute(
            "INSERT INTO players_rush_event_runs (player_id, event_id, status) "
            "VALUES (1, 700099, 'active')")
        self.db.execute(
            "INSERT INTO players_rush_event_runs (player_id, event_id, status) "
            "VALUES (2, 700099, 'completed')")
        # 另一个事件的进行中 run 不许被误伤
        self.db.execute(
            "INSERT INTO players_rush_event_runs (player_id, event_id, status) "
            "VALUES (3, 700007, 'active')")
        self.db.commit()

        season, abandoned = reroll.rollover_season(self.db, "700099", 9999)
        self.assertEqual(season, 5)
        self.assertEqual(abandoned, 1, "只作废本事件下进行中的那一条")
        rows = {r["player_id"]: r["status"] for r in
                self.db.execute("SELECT player_id, status FROM players_rush_event_runs")}
        self.assertEqual(rows, {1: "abandoned", 2: "completed", 3: "active"})

    def test_fingerprint_matches_server_algorithm(self) -> None:
        """指纹算法必须和 computeRushSeasonFingerprint 逐字一致。

        写错的后果不是崩,是**服务端下一次 ensureRushSeason 认为塔又变了、
        再白换一期** —— 一次重摇跳两期,中间那一期永远是空榜。
        """
        from external_sources import server_source
        quest = server_source("assets/rush_event_quest.json")
        data = json.loads(quest.read_text(encoding="utf-8"))
        expect: dict[int, int] = {}
        for row in data.values():
            if int(row.get("rushEventId", 0)) != 700099:
                continue
            folder = int(row["rushEventFolderId"])
            # 服务端是 `if (round > (map[folder] ?? 0))` —— 全 0 轮的 folder
            # 根本不会进 map,所以这里也不能给它补一个 0。
            if int(row["rushEventRound"]) > expect.get(folder, 0):
                expect[folder] = int(row["rushEventRound"])
        wanted = ",".join(f"{f}:{expect[f]}" for f in sorted(expect))
        self.assertEqual(reroll.season_fingerprint("700099"), wanted)
        self.assertTrue(wanted, "700099 至少要有一个多轮 folder,否则这条断言是空的")

    def test_fingerprint_of_unknown_event_is_empty(self) -> None:
        self.assertEqual(reroll.season_fingerprint("123456"), "")

    def _run_main(self, argv: list[str], *, server=None, expect_rc: int = 0) -> str:
        """跑一遍 `wf_rogue_reroll.main()`,只把子进程、DB 路径和换期回调换掉。

        `main()` 才是真正的接线点:`rollover_season` 单测全绿、而 main 里根本
        没调它 —— 这正是本轮变异复审抓到的洞(重摇一百次期号纹丝不动)。

        :param server: 替 `rollover_via_server` 的桩;None = 装一个「成功换到第 2 期」
            的默认桩(测试进程里绝不允许真发 HTTP)。
        :param expect_rc: 期望的退出码(3 = 塔重摇了但换期没做成)。
        """
        db_path = str(Path(self.tmp.name) / "t.db")
        out = io.StringIO()
        stub = server if server is not None else mock.Mock(return_value={
            "ok": True, "status": 200, "error": None,
            "body": {"season": 2, "settled": True, "settlement": {"mailCount": 1}},
        })
        # `note_season_baseline` 会往 mod-tools/work/rogue_tower_season.json 写
        # 作者真实工作区的判据基线 —— 测试绝不能碰它(写进去会用一个假期号
        # 污染 GUI 的「真换塔 vs 只动一层」基线)。
        with mock.patch.object(reroll.rsave, "DB_PATH", db_path), \
                mock.patch.object(reroll.subprocess, "run",
                                  return_value=mock.Mock(returncode=0)), \
                mock.patch.object(reroll, "rollover_via_server", stub), \
                mock.patch.object(reroll, "note_season_baseline", mock.Mock()) \
                as baseline_stub, \
                mock.patch.object(sys, "argv", ["wf_rogue_reroll.py", *argv]), \
                redirect_stdout(out):
            self.assertEqual(reroll.main(), expect_rc)
        self._last_baseline_stub = baseline_stub
        self._last_server_stub = stub
        return out.getvalue()

    def _season(self) -> int | None:
        conn = sqlite3.connect(str(Path(self.tmp.name) / "t.db"))
        try:
            row = conn.execute(
                "SELECT season FROM rush_event_seasons WHERE event_id = 700099").fetchone()
        finally:
            conn.close()
        return None if row is None else int(row[0])

    def test_apply_hands_the_season_off_to_the_server(self) -> None:
        """`--apply` 默认把换期交给服务端「结算并开启新一期」端点。

        为什么不是本脚本自己写 SQL:那样**只换期不发奖** —— 服务端只能结算
        「台账里当前那一期」,期号一被推走,上一期的名次冻结和奖励邮件就永远
        补不回来。所以这里必须能看到:① 回调发生了,带对了事件号和来源;
        ② 本脚本**一行 SQL 都没往 rush_event_seasons 写**。
        """
        self.db.close()   # main() 自己开库
        self.assertIsNone(self._season())
        log = self._run_main(["--apply", "--no-restart", "--seed", "1"])

        stub = self._last_server_stub
        self.assertEqual(stub.call_count, 1, "换期回调必须真的发出去")
        self.assertEqual(stub.call_args.args[0], "700099")
        self.assertEqual(stub.call_args.args[1], "reroll-cli", "来源要写进台账备查")
        self.assertIn("排行榜换期", log)
        self.assertIn("已结算并发奖", log)
        self.assertIsNone(self._season(),
                          "本脚本不再自己写 rush_event_seasons —— 期号是服务端在"
                          "结算事务里推的")
        # 换期成功之后必须刷新 GUI 的判据基线,否则「先一键重开、再用⑥改一层」
        # 会拿重摇之前那座塔当基线,把单层小修误判成真换塔、白清一张榜。
        self.assertEqual(self._last_baseline_stub.call_count, 1)
        self.assertEqual(self._last_baseline_stub.call_args.args[1], 2,
                         "记的是服务端刚开的那一期")

    def test_server_handoff_failure_never_falls_back_to_sql(self) -> None:
        """回调失败时**不许**退回写 SQL,而且要用退出码 3 喊出来。

        「塔换了、榜没换期」可恢复(后台点一下「结算并开启新一期」就补上);
        「换了期没结算」不可恢复。所以宁可停在前者。
        退出码用 3 而不是 1:重摇本身成功了(塔已重建、进度已清),
        报 1 会诱使操作者**再重摇一次**。
        """
        self.db.close()
        failing = mock.Mock(return_value={
            "ok": False, "status": None, "body": None,
            "error": "URLError: [WinError 10061] 连接被拒绝",
        })
        log = self._run_main(["--apply", "--no-restart", "--seed", "1"],
                             server=failing,
                             expect_rc=reroll.EXIT_SEASON_HANDOFF_FAILED)
        self.assertIsNone(self._season(), "失败了也一行 SQL 都不许写")
        self.assertIn("排行榜没换期", log)
        self.assertIn("结算并开启新一期", log, "日志里要给出补救步骤")

    def test_offline_season_is_the_only_sql_path(self) -> None:
        """`--offline-season` 是逃生口:直接写 SQL,并明说「不发奖」。"""
        self.db.close()
        never = mock.Mock(side_effect=AssertionError("逃生口不许发 HTTP"))
        log = self._run_main(["--apply", "--no-restart", "--offline-season", "--seed", "1"],
                             server=never)
        self.assertEqual(self._season(), 1)
        self.assertIn("只换期不发奖", log)
        self.assertEqual(never.call_count, 0)

        self._run_main(["--apply", "--no-restart", "--offline-season", "--seed", "1"],
                       server=never)
        self.assertEqual(self._season(), 2, "再重摇一次就是第 2 期")

    def test_keep_season_skips_the_rollover(self) -> None:
        """服务端钩子那条路已经自己换过期了,子进程不能再换一次。"""
        self.db.close()
        never = mock.Mock(side_effect=AssertionError("--keep-season 时不许回调服务端"))
        log = self._run_main(["--apply", "--no-restart", "--keep-season", "--seed", "1"],
                             server=never)
        self.assertIsNone(self._season(), "--keep-season 时一行都不许写")
        self.assertIn("保持不变", log)
        self.assertEqual(never.call_count, 0)

    def test_keep_season_still_records_the_gui_baseline(self) -> None:
        """**本轮 blocker 的另一半**:期号不推,但判据基线要记。

        这条路是服务端重摇钩子(游戏内整段重置)拉起来的,塔确实被重建了。
        不记基线的话,GUI 下次拿的是重摇**之前**那座塔,改一层 boss 就会被数成
        「30/30 层都变了」⇒ 误判真换塔 ⇒ 主动发起一次不该发生的结算 + 换期。
        (期号传 None:换期是服务端在本进程退出之后才做的,这里问不到新期号;
         期号对不上会被 `wf_rogue_season.sync()` 的交叉核对当成「基线不新鲜」,
         那一次不换期 —— 正是想要的保守方向。)
        """
        self.db.close()
        never = mock.Mock(side_effect=AssertionError("--keep-season 时不许回调服务端"))
        self._run_main(["--apply", "--no-restart", "--keep-season", "--seed", "1"],
                       server=never)
        stub = self._last_baseline_stub
        self.assertEqual(stub.call_count, 1, "塔换了就必须记基线")
        self.assertEqual(stub.call_args.args[0], "700099")
        self.assertIsNone(stub.call_args.args[1], "期号问不到,记 None(digest 才是判据)")
        self.assertEqual(stub.call_args.args[2], "reroll-hook")

    def test_current_season_via_server_reads_the_settlement_endpoint(self) -> None:
        """期号交叉核对必须打在**只读**的结算概览端点上,并带 admin token。

        打错端点(比如打到 POST 那个换期端点)= 一问期号就白换一期;
        少带 token = 401 ⇒ 核对不了 ⇒ GUI 从此再也不换期(静默退化)。
        """
        seen = {}

        class _Resp:
            status = 200

            def read(self):
                return b'{"eventId": 700099, "currentSeason": 6}'

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def _fake_urlopen(request, timeout=None):
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            seen["headers"] = dict(request.header_items())
            return _Resp()

        with mock.patch.object(reroll.urllib.request, "urlopen", _fake_urlopen), \
                mock.patch.object(reroll.wf_server_auth, "admin_bearer_headers",
                                  return_value={"Authorization": "Bearer T"}):
            result = reroll.current_season_via_server("700099",
                                                     server="http://127.0.0.1:8001/")

        self.assertEqual(result, {"ok": True, "season": 6, "error": None})
        self.assertEqual(seen["method"], "GET", "核对期号不许有副作用")
        self.assertEqual(seen["url"],
                         "http://127.0.0.1:8001/api/rush-leaderboard/700099/settlement")
        self.assertEqual(seen["headers"].get("Authorization"), "Bearer T")

    def test_current_season_of_a_fresh_ledger_is_none_but_ok(self) -> None:
        """服务端答了「还没有这个事件的台账」≠ 没问到 —— 两者的处置不同。"""

        class _Resp:
            status = 200

            def read(self):
                return b'{"currentSeason": null}'

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        with mock.patch.object(reroll.urllib.request, "urlopen",
                               lambda request, timeout=None: _Resp()), \
                mock.patch.object(reroll.wf_server_auth, "admin_bearer_headers",
                                  return_value={}):
            self.assertEqual(reroll.current_season_via_server("700099", server="http://x"),
                             {"ok": True, "season": None, "error": None})

    def test_current_season_swallows_transport_errors(self) -> None:
        """8001 没起时不许抛 —— 调用方靠 ok=False 判「核对不了 ⇒ 不换期」。"""
        with mock.patch.object(reroll.urllib.request, "urlopen",
                               mock.Mock(side_effect=urllib.error.URLError("拒绝"))), \
                mock.patch.object(reroll.wf_server_auth, "admin_bearer_headers",
                                  return_value={}):
            result = reroll.current_season_via_server("700099", server="http://x")
        self.assertFalse(result["ok"])
        self.assertIsNone(result["season"])
        self.assertIn("URLError", result["error"])

    def test_dry_run_never_touches_the_season(self) -> None:
        """不加 `--apply` 是纯预览:不清进度、不换期、不回调。"""
        self.db.close()
        never = mock.Mock(side_effect=AssertionError("dry-run 不许回调服务端"))
        self._run_main(["--seed", "1"], server=never)
        self.assertIsNone(self._season())
        self.assertEqual(never.call_count, 0)

    def test_rollover_via_server_targets_the_settle_then_rollover_endpoint(self) -> None:
        """回调必须打在**先结算再换期**那个端点上,而且带 admin token。

        打错端点(比如打到只结算的 `/settlement/run`)= 塔换了榜没换期;
        少带 token = 401,而 401 在 `--offline-season` 之外没有兜底。
        """
        seen = {}

        class _Resp:
            status = 200

            def read(self):
                return b'{"season": 7, "settled": true}'

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def _fake_urlopen(request, timeout=None):
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            seen["headers"] = dict(request.header_items())
            return _Resp()

        with mock.patch.object(reroll.urllib.request, "urlopen", _fake_urlopen), \
                mock.patch.object(reroll.wf_server_auth, "admin_bearer_headers",
                                  return_value={"Authorization": "Bearer T"}):
            result = reroll.rollover_via_server("700099", "reroll-cli",
                                                server="http://127.0.0.1:8001/")

        self.assertTrue(result["ok"])
        self.assertEqual(result["body"]["season"], 7)
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(
            seen["url"],
            "http://127.0.0.1:8001/api/rush-leaderboard/700099/season/rollover"
            "?source=reroll-cli")
        self.assertEqual(seen["headers"].get("Authorization"), "Bearer T")

    def test_rollover_via_server_reports_the_servers_refusal(self) -> None:
        """服务端按裁定拒绝换期(409)时,原因要原样带回来。"""
        payload = io.BytesIO(
            '{"error": "结算失败,已按裁定拒绝换期(期号未动):库炸了"}'.encode("utf-8"))
        error = urllib.error.HTTPError("http://x", 409, "Conflict", {}, payload)
        try:
            with mock.patch.object(reroll.urllib.request, "urlopen", side_effect=error):
                result = reroll.rollover_via_server("700099")
        finally:
            error.close()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 409)
        self.assertIn("拒绝换期", result["error"])

    def test_keep_season_is_a_two_sided_contract(self) -> None:
        """`--keep-season` 是**跨文件契约**,两边必须同时在。

        服务端 /rush_event/reset 的重摇钩子自己已经调过 noteRushSeasonRollover,
        它拉起本脚本时必须带 `--keep-season`,否则一次重摇换两期、
        中间那一期永远是空榜。反过来,脚本这边把 flag 改名/删掉,
        子进程会直接 argparse 报错退出,整个重摇失败(而且没人会看子进程 stderr ——
        它是 `stdio: "ignore"` detached spawn 的)。
        """
        script = Path(reroll.__file__).read_text(encoding="utf-8")
        self.assertIn('"--keep-season"', script, "脚本这边的 flag 没了")

        hook = __import__("external_sources").server_source("src/routes/api/rushEvent.ts").read_text(
            encoding="utf-8")
        self.assertIn('"--keep-season"', hook,
                      "服务端重摇钩子没带 --keep-season ⇒ 一次重摇会换两期")
        self.assertIn("wf_rogue_reroll.py", hook)


class BotPartyTest(unittest.TestCase):
    """`wf_rush_bots.write_bot_party` —— bot 的编队行。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = make_db(Path(self.tmp.name) / "t.db")

    def tearDown(self) -> None:
        self.db.close()
        self.tmp.cleanup()

    def test_write_bot_party_lands_on_slot_the_server_decodes(self) -> None:
        """写进去的必须正好是服务端按 `party_slot=1` 解出来的那一格。

        服务端解码:group = floor((slot-1)/10)+1、槽位 = ((slot-1)%10)+1
        ⇒ party_slot=1 对应 group 1 / slot 1。写到别的格子上等于没写:
        资料页和榜行都会退回兜底,而且**一点报错都不会有**。
        """
        self.assertTrue(bots.write_bot_party(self.db, 13, [129999, 169995, 149995]))
        party = self.db.execute(
            "SELECT * FROM players_parties WHERE player_id = 13").fetchone()
        self.assertEqual(party["group_id"], 1)
        self.assertEqual(party["slot"], 1)
        self.assertEqual(party["category"], 1, "普通编队 = PartyCategory.NORMAL = 1")
        self.assertEqual(
            [party["character_id_1"], party["character_id_2"], party["character_id_3"]],
            [129999, 169995, 149995])
        group = self.db.execute(
            "SELECT * FROM players_party_groups WHERE player_id = 13").fetchone()
        self.assertEqual((group["id"], group["category"]), (1, 1))

    def test_write_bot_party_is_idempotent(self) -> None:
        """跑第二遍不许改动已有的编队 —— 回填脚本要能反复跑。"""
        bots.write_bot_party(self.db, 13, [1, 2, 3])
        self.assertFalse(
            bots.write_bot_party(self.db, 13, [9, 9, 9]),
            "第二次不该再插一行")
        party = self.db.execute(
            "SELECT * FROM players_parties WHERE player_id = 13").fetchone()
        self.assertEqual(party["character_id_1"], 1,
            "已有编队不许被覆盖(作者可能手工改过)")
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) c FROM players_parties WHERE player_id = 13"
            ).fetchone()["c"], 1)

    def _seed_bots(self) -> None:
        """两个 bot(挂 idp_code='rushbot')+ 一个真人存档,各带一条成绩行。"""
        self.db.execute("INSERT INTO accounts (id, idp_code) VALUES (26, 'rushbot')")
        self.db.execute("INSERT INTO accounts (id, idp_code) VALUES (1, '')")
        self.db.execute("INSERT INTO players (id, name, account_id) VALUES (13, '夜刃', 26)")
        self.db.execute("INSERT INTO players (id, name, account_id) VALUES (14, '青雀', 26)")
        self.db.execute("INSERT INTO players (id, name, account_id) VALUES (8, '作者', 1)")
        for player_id, party in ((13, (11, 12, 13)), (14, (21, 22, 23)), (8, (31, 32, 33))):
            self.db.execute(
                "INSERT INTO players_rush_event_runs "
                "(player_id, event_id, status, character_id_1, character_id_2, character_id_3) "
                "VALUES (?, 700099, 'completed', ?, ?, ?)", (player_id, *party))
        self.db.commit()

    def _backfill(self, apply: bool) -> str:
        args = argparse.Namespace(event=700099, folder=None, apply=apply)
        out = io.StringIO()
        with mock.patch.object(bots, "DB_PATH", Path(self.tmp.name) / "t.db"), \
                redirect_stdout(out):
            self.assertEqual(bots.cmd_backfill_parties(args), 0)
        return out.getvalue()

    def _party_owners(self) -> set[int]:
        return {int(r["player_id"]) for r in
                self.db.execute("SELECT DISTINCT player_id FROM players_parties")}

    def test_backfill_only_touches_rushbot_saves(self) -> None:
        """回填只碰 `accounts.idp_code='rushbot'` 名下的存档 —— 真人存档一行都不许动。

        这条是硬纪律:作者的编队是他自己在游戏里排的,脚本写进去就等于覆盖。
        """
        self._seed_bots()
        self._backfill(apply=True)
        self.assertEqual(self._party_owners(), {13, 14},
                         "真人存档 8 不许被写进任何编队行")
        party = self.db.execute(
            "SELECT * FROM players_parties WHERE player_id = 14").fetchone()
        self.assertEqual(
            [party["character_id_1"], party["character_id_2"], party["character_id_3"]],
            [21, 22, 23], "编队取自它自己那条成绩行,榜面上的头像不会变")

    def test_backfill_dry_run_writes_nothing(self) -> None:
        self._seed_bots()
        log = self._backfill(apply=False)
        self.assertEqual(self._party_owners(), set())
        self.assertIn("DRY-RUN", log)

    def test_backfill_is_idempotent(self) -> None:
        """反复跑不叠行、不覆盖 —— 作者可能会连点两次。"""
        self._seed_bots()
        self._backfill(apply=True)
        self.db.execute(
            "UPDATE players_parties SET character_id_1 = 999 WHERE player_id = 13")
        self.db.commit()

        log = self._backfill(apply=True)
        self.assertIn("待补 0 个", log)
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) c FROM players_parties").fetchone()["c"], 2)
        self.assertEqual(
            self.db.execute(
                "SELECT character_id_1 FROM players_parties WHERE player_id = 13"
            ).fetchone()[0], 999, "第二次不许把手工改过的编队冲掉")

    def test_bot_run_party_reads_the_latest_result_row(self) -> None:
        """编队取自 bot 自己的成绩行 —— 补编队不该让榜面上任何头像发生变化。"""
        self.db.execute(
            "INSERT INTO players_rush_event_runs "
            "(player_id, event_id, status, character_id_1, character_id_2, character_id_3) "
            "VALUES (13, 700099, 'completed', 11, 12, 13)")
        self.db.execute(
            "INSERT INTO players_rush_event_runs "
            "(player_id, event_id, status, character_id_1, character_id_2, character_id_3) "
            "VALUES (13, 700099, 'completed', 21, 22, 23)")
        self.db.commit()
        self.assertEqual(bots.bot_run_party(self.db, 13), [21, 22, 23])
        self.assertIsNone(bots.bot_run_party(self.db, 999))


if __name__ == "__main__":
    unittest.main()

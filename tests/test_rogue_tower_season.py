# -*- coding: utf-8 -*-
"""`wf_rogue_season` —— 「真换塔 vs 只动一层」判据 + GUI 换期接线(2026-08-28)。

为什么需要判据:GUI 有两条会重建并发布整座塔的入口(①难度曲线/重摇的「应用+发布」、
⑥面板的「📤 发布」),走完楼层/boss/场地全换了,榜上却还留着旧塔的成绩。
但 ⑥ **也用来改单层 boss** —— 每次发布都换期会造出一串没人打过的空榜,
而换期不可逆(换掉之后上一期再也结算不了)。

所以这里钉三样:
  1. 判据本身(纯函数 `classify`)的阈值和边界;
  2. 判据在**真实历史数据**上的表现(store 里 90 多份 `.bak-wfquest-*`);
  3. `sync()` 的接线:只有 `new-tower` 才回调服务端换期,其余一律不换。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_rogue_season as season  # noqa: E402


def tower(rounds: int, salt: str = "a") -> dict[str, str]:
    return {str(i): f"{salt}{i}" for i in range(1, rounds + 1)}


class ClassifyTest(unittest.TestCase):
    """纯判据。阈值 = max(2, ceil(总层数/2))。"""

    def test_no_baseline_is_unknown(self) -> None:
        """没有基线时判「不确定」⇒ 调用方不换期(拿不准一律不动)。"""
        self.assertEqual(season.classify(None, tower(30))["verdict"], "unknown")
        self.assertEqual(season.classify({}, tower(30))["verdict"], "unknown")

    def test_unreadable_current_is_unknown(self) -> None:
        self.assertEqual(season.classify(tower(30), {})["verdict"], "unknown")

    def test_identical_towers_are_unchanged(self) -> None:
        self.assertEqual(season.classify(tower(30), tower(30))["verdict"], "unchanged")

    def test_single_floor_edit_is_minor(self) -> None:
        """⑥ 面板改一层 boss —— 最常见的那种改动,绝不能换期。"""
        after = tower(30)
        after["7"] = "changed"
        result = season.classify(tower(30), after)
        self.assertEqual(result["verdict"], "minor-edit")
        self.assertEqual(result["changed"], 1)
        self.assertEqual(result["rounds"], ["7"])

    def test_full_rebuild_is_a_new_tower(self) -> None:
        result = season.classify(tower(30), tower(30, salt="b"))
        self.assertEqual(result["verdict"], "new-tower")
        self.assertEqual(result["changed"], 30)

    def test_threshold_is_exactly_half(self) -> None:
        """30 层塔:14 层 = 小修,15 层 = 真换塔。改阈值必须先改这条。"""
        below = tower(30)
        for i in range(1, 15):
            below[str(i)] = "x"
        self.assertEqual(season.classify(tower(30), below)["verdict"], "minor-edit")

        at = tower(30)
        for i in range(1, 16):
            at[str(i)] = "x"
        self.assertEqual(season.classify(tower(30), at)["verdict"], "new-tower")

    def test_tiny_tower_needs_two_floors(self) -> None:
        """3 层塔的一半是 2 —— 但改一层仍是小修,靠 max(2, …) 兜底。"""
        after = tower(3)
        after["1"] = "x"
        self.assertEqual(season.classify(tower(3), after)["verdict"], "minor-edit")
        after["2"] = "x"
        self.assertEqual(season.classify(tower(3), after)["verdict"], "new-tower")

    def test_round_count_change_is_always_a_new_tower(self) -> None:
        """--rounds 改过 ⇒ 一定是新塔,哪怕留下的那些层内容一模一样。"""
        base = tower(30)
        shorter = {k: v for k, v in base.items() if int(k) <= 15}
        result = season.classify(base, shorter)
        self.assertEqual(result["verdict"], "new-tower")
        self.assertIn("层数从", result["why"])


class RealHistoryTest(unittest.TestCase):
    """拿 store 里的真实历史版本跑一遍判据 —— 阈值不是拍脑袋定的。

    `wf_quest_lib.save_table` 每次写盘都留一份 `.bak-wfquest-<时间戳>`,
    于是 store 里躺着作者 2026-07 → 08 真实操作留下的几十座塔:
    整轮重摇的、手改一两层的、改轮数的,都在里面。
    """

    LOGICAL_DIR_HINT = "rush_event_quest 的 store 目录"

    def _versions(self) -> list[Path]:
        import wf_quest_lib as qlib
        from external_sources import require_live_store
        require_live_store()
        live = qlib.store_path(season.QUEST_LOGICAL)
        if not live.exists():
            return []
        baks = sorted(live.parent.glob(live.name + ".bak-*"),
                      key=lambda p: p.stat().st_mtime)
        return baks + [live]

    def test_criterion_separates_rebuilds_from_hand_edits(self) -> None:
        versions = self._versions()
        if len(versions) < 20:
            self.skipTest("本机 store 里没有足够的历史版本(该判据的实证依赖它)")

        digests = []
        for path in versions:
            try:
                digest = season.tower_digest(season.ROGUE_EVENT_ID, path)
            except Exception:
                continue
            if digest:
                digests.append(digest)

        rebuild_ratios: list[float] = []
        minor_ratios: list[float] = []
        for before, after in zip(digests, digests[1:]):
            result = season.classify(before, after)
            if result["total"] == 0:
                continue
            ratio = result["changed"] / result["total"]
            if result["verdict"] == "new-tower":
                rebuild_ratios.append(ratio)
            elif result["verdict"] == "minor-edit":
                minor_ratios.append(ratio)

        self.assertGreaterEqual(len(rebuild_ratios), 20,
                                "历史里应当有几十次整轮重摇")
        self.assertGreaterEqual(len(minor_ratios), 5,
                                "历史里也应当有若干次手改一两层")
        # 关键实证:两类之间有一条**空带**,50% 这条线落在带子里,不是擦边过的。
        self.assertLess(max(minor_ratios), 0.5,
                        "有一次手改被判成了真换塔 —— 那会白清一张榜")
        self.assertGreater(min(rebuild_ratios), max(minor_ratios),
                           "两类分布重叠了,阈值不再可靠")
        self.assertGreaterEqual(min(rebuild_ratios), 0.6,
                                "真换塔那一类的最小变化占比塌到 60% 以下,"
                                "说明 build 的随机性变了,阈值要重估")


class SyncWiringTest(unittest.TestCase):
    """`sync()` 的接线:谁会触发换期回调,谁不会。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "rogue_tower_season.json"
        self._patch = mock.patch.object(season, "STATE_PATH", self.state)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self.tmp.cleanup()

    def _sync(self, baseline, current, rollover, live=None, baseline_season=4):
        """跑一次 sync,把「读 store」「问期号」「回调服务端」三样都换成桩。

        :param live: `current_season_via_server` 的返回;缺省 = 服务端期号和基线
            里记的那个一致(基线新鲜),这样测的就是判据本身。
        """
        if baseline is not None:
            season.save_baseline(season.ROGUE_EVENT_ID, baseline, baseline_season, "test")
        fake_reroll = mock.Mock()
        fake_reroll.rollover_via_server = rollover
        fake_reroll.current_season_via_server = mock.Mock(return_value=live or {
            "ok": True, "season": baseline_season, "error": None})
        self._last_reroll = fake_reroll
        with mock.patch.object(season, "tower_digest", return_value=current), \
                mock.patch.dict(sys.modules, {"wf_rogue_reroll": fake_reroll}):
            return season.sync(season.ROGUE_EVENT_ID, "gui-publish")

    @staticmethod
    def _ok_rollover(season_no: int = 5):
        return mock.Mock(return_value={
            "ok": True, "status": 200, "error": None,
            "body": {"season": season_no, "settled": True,
                     "settlement": {"mailCount": 2}},
        })

    def test_new_tower_rolls_the_season_and_rebases(self) -> None:
        rollover = self._ok_rollover()
        result = self._sync(tower(30), tower(30, "b"), rollover)

        self.assertEqual(result["verdict"], "new-tower")
        self.assertTrue(result["rolled"])
        self.assertEqual(result["season"], 5)
        self.assertEqual(rollover.call_count, 1)
        self.assertEqual(rollover.call_args.args[1], "gui-publish",
                         "来源要写进台账,排障时才知道是哪条入口换的期")
        # 换完必须把新塔记成基线,否则下一次改一层会拿旧塔比 ⇒ 又判真换塔
        saved = season.load_state()[season.ROGUE_EVENT_ID]
        self.assertEqual(saved["digest"], tower(30, "b"))
        self.assertEqual(saved["season"], 5)

    def test_minor_edit_never_rolls(self) -> None:
        after = tower(30)
        after["9"] = "x"
        rollover = mock.Mock(side_effect=AssertionError("小修不许换期"))
        result = self._sync(tower(30), after, rollover)

        self.assertEqual(result["verdict"], "minor-edit")
        self.assertFalse(result["rolled"])
        self.assertEqual(rollover.call_count, 0)
        self.assertEqual(season.load_state()[season.ROGUE_EVENT_ID]["digest"], tower(30),
                         "基线不动 —— 单层小修攒够半座塔时仍然会被判成新塔")
        self.assertEqual(self._last_reroll.current_season_via_server.call_count, 0,
                         "本来就不换期的一档不必去问服务端期号 —— 8001 没起时"
                         "那一问只会白添一行吓人的警告")

    def test_unchanged_never_rolls(self) -> None:
        rollover = mock.Mock(side_effect=AssertionError("没变不许换期"))
        result = self._sync(tower(30), tower(30), rollover)
        self.assertEqual(result["verdict"], "unchanged")
        self.assertFalse(result["rolled"])

    def test_no_baseline_bootstraps_without_rolling(self) -> None:
        """第一次用(或台账被删):不换期,只把当前这座塔记成基线。"""
        rollover = mock.Mock(side_effect=AssertionError("没有基线时不许换期"))
        result = self._sync(None, tower(30), rollover)

        self.assertEqual(result["verdict"], "unknown")
        self.assertFalse(result["rolled"])
        self.assertEqual(rollover.call_count, 0)
        self.assertEqual(season.load_state()[season.ROGUE_EVENT_ID]["digest"], tower(30))

    def test_stale_baseline_never_rolls_the_season(self) -> None:
        """**本轮 blocker**:服务端换过期之后,基线不新鲜 ⇒ 一律不换期。

        基线只有 Python 侧会写,而服务端有五条换期通道一条都不碰它(游戏内重摇钩子、
        后台「结算并开启新一期」、后台「立即结算」、到点结算的调度器、指纹兜底)。
        走过任何一条之后,再用 ⑥ 面板改一层 boss 发布,判据会数出「30/30 层都变了」
        ⇒ 判真换塔 ⇒ **主动发起一次不该发生的结算 + 换期**:把仍在进行中的一期提前
        结算发奖、清空当期榜、作废所有进行中的 run,而换期不可逆。
        """
        rollover = mock.Mock(side_effect=AssertionError("基线不新鲜时绝不许换期"))
        # 基线记的是第 4 期,服务端已经在第 6 期了(中间被别的通道换过两次)。
        result = self._sync(tower(30), tower(30, "b"), rollover,
                            live={"ok": True, "season": 6, "error": None})

        self.assertEqual(result["verdict"], "stale-baseline")
        self.assertFalse(result["rolled"])
        self.assertEqual(rollover.call_count, 0)
        self.assertEqual(result["season"], 6)
        # 重记基线:下一次发布就能正常判了(否则每次都判「不新鲜」,永远换不了期)
        saved = season.load_state()[season.ROGUE_EVENT_ID]
        self.assertEqual(saved["digest"], tower(30, "b"))
        self.assertEqual(saved["season"], 6)

    def test_rebased_baseline_judges_the_next_edit_correctly(self) -> None:
        """重记基线之后必须收敛:再改一层要判成小修,而不是又一次「不新鲜」。"""
        self._sync(tower(30), tower(30, "b"),
                   mock.Mock(side_effect=AssertionError("不许换期")),
                   live={"ok": True, "season": 6, "error": None})

        after = tower(30, "b")
        after["7"] = "changed"
        fake_reroll = mock.Mock()
        fake_reroll.rollover_via_server = mock.Mock(side_effect=AssertionError("小修不许换期"))
        fake_reroll.current_season_via_server = mock.Mock(
            return_value={"ok": True, "season": 6, "error": None})
        with mock.patch.object(season, "tower_digest", return_value=after), \
                mock.patch.dict(sys.modules, {"wf_rogue_reroll": fake_reroll}):
            result = season.sync(season.ROGUE_EVENT_ID, "gui-layout")

        self.assertEqual(result["verdict"], "minor-edit")
        self.assertFalse(result["rolled"])

    def test_unreachable_server_never_rolls_and_keeps_the_baseline(self) -> None:
        """问不到期号 = 核对不了基线新鲜度 ⇒ 不换期,而且**基线不许动**。

        基线一动就等于「认下」这座塔,下次真换塔时反而判不出来。
        反正服务端没起的话换期回调本来也发不出去。
        """
        rollover = mock.Mock(side_effect=AssertionError("核对不了期号时不许换期"))
        result = self._sync(tower(30), tower(30, "b"), rollover,
                            live={"ok": False, "season": None,
                                  "error": "URLError: 连接被拒绝"})

        self.assertEqual(result["verdict"], "stale-baseline")
        self.assertFalse(result["rolled"])
        self.assertEqual(rollover.call_count, 0)
        self.assertIn("连接被拒绝", result["message"])
        self.assertEqual(season.load_state()[season.ROGUE_EVENT_ID]["digest"], tower(30),
                         "基线还是旧塔 ⇒ 8001 起好之后再发布一次仍然判得出真换塔")

    def test_bootstrap_adopts_the_server_season(self) -> None:
        """第一次用:基线要记**服务端当前那一期**,否则下次必然判「不新鲜」。"""
        rollover = mock.Mock(side_effect=AssertionError("没有基线时不许换期"))
        self._sync(None, tower(30), rollover, live={"ok": True, "season": 9, "error": None})
        self.assertEqual(season.load_state()[season.ROGUE_EVENT_ID]["season"], 9)

    def test_unreadable_store_does_not_wipe_a_good_baseline(self) -> None:
        """读不出当前这座塔时不许拿空 digest 覆盖基线 —— 那会冲掉一份好基线。"""
        rollover = mock.Mock(side_effect=AssertionError("读不出塔时不许换期"))
        result = self._sync(tower(30), {}, rollover)
        self.assertEqual(result["verdict"], "unknown")
        self.assertEqual(season.load_state()[season.ROGUE_EVENT_ID]["digest"], tower(30))

    def test_rollover_failure_keeps_the_old_baseline(self) -> None:
        """回调失败 ⇒ 期没换 ⇒ 基线不许刷新,否则这次换塔就再也判不出来了。"""
        rollover = mock.Mock(return_value={
            "ok": False, "status": None, "body": None, "error": "连接被拒绝"})
        result = self._sync(tower(30), tower(30, "b"), rollover)

        self.assertEqual(result["verdict"], "new-tower")
        self.assertFalse(result["rolled"])
        self.assertIn("结算并开启新一期", result["message"])
        self.assertEqual(season.load_state()[season.ROGUE_EVENT_ID]["digest"], tower(30),
                         "基线还是旧塔 ⇒ 下次发布还会再判一次真换塔,不会漏掉")


class GuiWiringTest(unittest.TestCase):
    """GUI 那两条发布入口真的接上了判据(不是只写在注释里)。"""

    def test_both_publish_paths_call_the_season_sync(self) -> None:
        source = (Path(season.__file__).resolve().parent / "wf_gui.py").read_text(encoding="utf-8")
        self.assertIn('_rogue_season_sync("gui-build")', source,
                      "①难度曲线/重摇的「应用+发布」没接换期判定")
        self.assertIn('_rogue_season_sync("gui-publish")', source,
                      "⑥面板的「📤 发布」没接换期判定")
        self.assertIn('_rogue_season_sync("gui-layout")', source,
                      "⑥面板逐层编辑器自带的「写入并发布」没接换期判定")
        self.assertNotIn("ROGUE_NO_SEASON_NOTICE", source,
                         "旧的「本入口不换期」提示还留着 = 两边说法打架")

    def test_reroll_cli_refreshes_the_baseline(self) -> None:
        """CLI 换期之后必须刷新基线,否则 GUI 会拿重摇前的塔当基线误判。"""
        source = (Path(season.__file__).resolve().parent / "wf_rogue_reroll.py").read_text(
            encoding="utf-8")
        self.assertIn("note_season_baseline", source)
        self.assertIn("wf_rogue_season", source)

    def test_sync_cross_checks_the_season_before_trusting_the_baseline(self) -> None:
        """基线新鲜度这道闸必须**在** classify 判定之前生效(源码级防回归)。

        行为断言在 `SyncWiringTest.test_stale_baseline_never_rolls_the_season`;
        这一条盯的是「别哪天把交叉核对挪到 new-tower 分支之后」——
        挪过去就等于没有这道闸。
        """
        source = (Path(season.__file__).resolve().parent / "wf_rogue_season.py").read_text(
            encoding="utf-8")
        gate = source.index('if state.get("season") != live["season"]:')
        rollover = source.index("result = reroll.rollover_via_server")
        self.assertLess(gate, rollover, "期号交叉核对必须发生在换期回调之前")


if __name__ == "__main__":
    unittest.main()

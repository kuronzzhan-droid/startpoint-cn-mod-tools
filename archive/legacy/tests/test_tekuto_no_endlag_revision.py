# -*- coding: utf-8 -*-
"""wf_tekuto_no_endlag_revision：真树正向（删净/其余不动/幂等）＋ 合成树负向（基线漂移抛错）。"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import sys
import unittest
import zlib
from collections import Counter
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_kit_philia as PH  # noqa: E402
import wf_seasonal7_kit_tekuto as K  # noqa: E402
import wf_tekuto_no_endlag_revision as R  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "work/character_packs/s7-tekuto/package"
FIXTURE = Path(__file__).resolve().parent / "fixtures/tekuto_no_endlag_before.json"
LOGICALS = tuple(wf_dsl.dsl_logical(p) for p in R.SKILL_PROGRAMS)
#: 2026-09-27 平衡第二批暂存脚本（${WF_ROOT}/out/平衡调整批次-20260927/batch2/stage_batch.py SNAPSHOT）回写候选时的快照键。
BALANCE_B_SNAPSHOT = "revision_20260927b"


def _store() -> Path:
    profile = json.loads((ROOT / "mod-tools/profiles.json").read_bytes())["profiles"]["cn"]
    store = Path(profile["store"])
    return store if store.is_absolute() else ROOT / store


def _read(path: Path):
    return wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]


def _current(logical: str):
    """当前那棵树：先 workspace 候选，缺了再 live store。"""
    for path in (PACKAGE / "roots/common" / logical, core.table_path(_store(), logical)):
        if path.is_file():
            return _read(path)
    return None


def _restore_hold(tree, entry: dict):
    """按 fixture 把那条 StopBall 塞回根语句表的原位置，重建改动前的真树。"""
    before = copy.deepcopy(tree)
    before[11][1].insert(entry["root_index"], copy.deepcopy(entry["statement"]))
    return before


def _pair(logical: str, entry: dict):
    """(改动前的真树, 删完的真树)。候选/live 还没改时直接用它，改完了就按 fixture 复原。"""
    current = _current(logical)
    if current is None:
        return None
    if R.hold_statements(current):
        return current, R.strip_ball_hold(current)
    return _restore_hold(current, entry), current


BASELINE = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else {}
PAIRS = {logical: pair for logical in LOGICALS if logical in BASELINE
         for pair in [_pair(logical, BASELINE[logical])] if pair is not None}
TREES = {logical: pair[0] for logical, pair in PAIRS.items()}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _shallow(command) -> str:
    """一条命令**自身参数**的快照：内嵌 ``Block`` 子块挖空，免得父命令因子块变化被当成「被改写」。"""
    def blank(value):
        if isinstance(value, list):
            if len(value) == 2 and value[0] == "Block" and isinstance(value[1], list):
                return ["Block", "<block>"]
            return [blank(item) for item in value]
        return value
    return json.dumps(blank(command), ensure_ascii=False, sort_keys=True)


def _flat_commands(tree) -> list:
    return [_shallow(c) for c in PH.cmds(tree)]


class RealTrees(unittest.TestCase):
    """正向：两棵真树各删 1 条 StopBall，删后 0 条，其余命令逐节点不变，重复调用幂等。"""

    @classmethod
    def setUpClass(cls):
        if len(TREES) != len(LOGICALS):
            raise unittest.SkipTest("tekuto DSL sources absent (no candidate package, no live store)")

    def test_each_tree_has_exactly_one_hold_before_and_none_after(self):
        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                before = R.hold_statements(tree)
                self.assertEqual(len(before), R.EXPECTED_HOLDS, logical)
                self.assertEqual([st[1][0] for st in before], ["StopBall"])
                self.assertEqual([st[1][1:] for st in before], [R.STOPBALL_BASELINE])
                self.assertEqual(R.hold_statements(R.strip_ball_hold(tree)), [])

    def test_only_the_stopball_disappears(self):
        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                after = R.strip_ball_hold(tree)
                before_cmds, after_cmds = _flat_commands(tree), _flat_commands(after)
                removed = Counter(before_cmds) - Counter(after_cmds)
                self.assertEqual(Counter(after_cmds) - Counter(before_cmds), Counter(),
                                 "没有任何命令可以被新增或改写")
                self.assertEqual(sorted(json.loads(c)[0] for c in removed.elements()), ["StopBall"])
                # 剩下的命令序列与原树逐节点一致，顺序也一致
                dropped = dict(removed)
                survivors = []
                for cmd in before_cmds:
                    if dropped.get(cmd):
                        dropped[cmd] -= 1
                    else:
                        survivors.append(cmd)
                self.assertEqual(after_cmds, survivors)
                self.assertEqual(after[:11], tree[:11])          # 头部（含 movementPriority/buffTargetAs）不动
                self.assertEqual(len(after[11][1]), len(tree[11][1]) - 1)
                self.assertNotIn("StopBall", json.dumps(after, ensure_ascii=False))

    def test_performance_and_damage_nodes_all_survive(self):
        """瞄准（雷达/aim_line）与发射（四段 + 终幕 + 5 延长槽）全部照常：节点计数与时间轴不变。"""
        def wait_frames(tree):
            found = []

            def walk(node):
                if isinstance(node, list):
                    if len(node) == 2 and node[0] == "Event" and isinstance(node[1], list) \
                            and node[1][0] == "Wait":
                        found.append(node[1][1])
                    for child in node:
                        walk(child)
            walk(tree)
            return sorted(found)

        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                after = R.strip_ball_hold(tree)
                for name in ("CreateHitArea", "CreateNormalAttack", "ShowEffect",
                             "CreateReferencePoint", "RotateHitArea", "CreateCondition",
                             "ConditionalsConditionAccumulationNumber",
                             "BindConditionAccumulationVariable"):
                    self.assertEqual(len(PH.cmds(after, name)), len(PH.cmds(tree, name)), name)
                self.assertEqual(wait_frames(after), wait_frames(tree))
                self.assertTrue(wait_frames(after))

    def test_lock_report_counts_the_frames(self):
        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                before, after = R.lock_report(tree), R.lock_report(R.strip_ball_hold(tree))
                self.assertEqual(before["dsl_stop_frames"], R.STOPBALL_BASELINE[1])
                self.assertEqual(after["dsl_stop_frames"], 0)
                self.assertEqual(before["movement_priority"], R.MOVEMENT_PRIORITY_NONE)
                self.assertEqual(after["total_locked_frames"], R.SKILL_CUTIN_FRAMES)

    def test_perceived_lock_is_70_to_60_not_a_full_removal(self):
        """交付口径：玩家感知到的定住 = DSL 停球 + 客户端 cut-in，两段串行 ⇒ 70 → 60（-14%）。

        复核判定的第 2 条：摘要不许以「整段去掉」领头。这条测试把那个数字钉死，
        任何人改小 SKILL_CUTIN_FRAMES 或者改回「总数=0」都会红。
        """
        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                before, after = R.lock_report(tree), R.lock_report(R.strip_ball_hold(tree))
                self.assertEqual(before["total_locked_frames"], 70)
                self.assertEqual(after["total_locked_frames"], 60)
                self.assertGreater(after["total_locked_frames"], 0,
                                   "删掉 DSL 停球之后仍有 60 帧客户端 cut-in，不是「整段去掉」")
                # 任务书的退路口径「≤约 12–15 帧」按**感知帧数**并没有达到，必须如实说。
                self.assertGreater(after["total_locked_frames"], 15)
                self.assertLess((before["total_locked_frames"] - after["total_locked_frames"])
                                / before["total_locked_frames"], 0.20)

    def test_lock_report_cites_the_right_client_source(self):
        """复核判定第 5 条：剩余 60 帧的出处是 SquadManagerImpl:734-735，不是 MemberImpl:2593。"""
        note = R.lock_report(TREES[LOGICALS[0]])["note"]
        self.assertIn("SquadManagerImpl.as:734-735", note)
        self.assertIn("startToSkillCutin", note)
        self.assertIn("SquadManagerImpl.as:734-735", R.CLIENT_CUTIN_SOURCE)
        # 错误引文只允许以「别引这条」的形式出现，且必须和纠正说明同时出现。
        if "MemberImpl" in note:
            self.assertIn("SummonsMultiball", note)
            self.assertIn("跳过", note)

    def test_beam_origin_follows_the_ball(self):
        """复核判定第 4 条：判定区挂球 -18 且 trackingPos=True ⇒ 原点随球位移，不是「位置不变」。"""
        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                anchors = R.beam_anchors(R.strip_ball_hold(tree))
                self.assertTrue(anchors["origin_follows_ball"])
                self.assertGreaterEqual(anchors["anchored_to_ball_and_tracking_pos"], 11)
                self.assertIn("随球位移", anchors["claim"])
                self.assertIn("不可写成", anchors["claim"])   # 「位置不变」只许以禁令的形式出现
                # 逐条复核：挂球的判定区第 7 参必须真的是 True（不是 1、不是 "true"）
                for area in R.commands(tree, "CreateHitArea"):
                    if area[R.HIT_AREA_SUBJECT] == R.BALL_SUBJECT:
                        self.assertIs(area[R.HIT_AREA_TRACKING_POS], True)

    def test_idempotent_and_encodable_and_passes_native_gates(self):
        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                after = R.strip_ball_hold(tree)
                self.assertEqual(R.strip_ball_hold(after), after)
                self.assertEqual(R.strip_ball_hold(after, expected=None), after)
                # 平衡第三批（wf_balance_20260927c_tekuto）回写后，树里 11 个旗号 3 分支两侧各带一份同一判定区
                # 绑定号（只会走其中一侧）；全树计数的 dup_bind_ids 改为按分支判断，其余 philia 门禁照旧必须为空。
                failures = PH.dsl_gate_failures(PH.dsl_gates(after, element=K.ELEMENT))
                self.assertEqual([f for f in failures if not f.startswith("dup_bind_ids=")], [])
                self.assertEqual(K.balance_c_dup_bound_ids(after), [])
                self.assertEqual(K.dsl_quick_problems(after), [])
                encode_tree(after)

    def test_source_trees_are_untouched(self):
        snapshot = copy.deepcopy(TREES)
        for tree in TREES.values():
            R.strip_ball_hold(tree)
        self.assertEqual(TREES, snapshot)

    def test_bytes_match_the_recorded_live_baseline_and_candidate(self):
        """复原出来的「改动前」逐字节等于 1.4.920 的 live 存储，删完逐字节等于候选包。"""
        for logical, (before, after) in PAIRS.items():
            entry = BASELINE[logical]
            with self.subTest(logical=logical):
                self.assertEqual(_sha(encode_tree(before)), entry["before_sha256"])
                self.assertEqual(_sha(encode_tree(R.strip_ball_hold(before))), entry["after_sha256"])
                self.assertEqual(R.strip_ball_hold(before), after)
                self.assertEqual([len(before[11][1]), len(after[11][1])], entry["root_statements"])

    def test_peer_characters_still_hold_30_frames_so_tekuto_must_feel_shorter(self):
        """复核判定第 1 条：黑／丝缇涅尔 live 仍各带 30 帧停球 ⇒ 真机对比时特克托应当**更短**。

        device_check 写的是「特克托应当比黑快约 30 帧；两边一致＝没生效」。那条判据只有在
        对照角色确实还是 60+30=90 帧时才成立，所以在这里对 live 逐棵复核；
        哪天它们也被改短，这条会红，判据必须跟着改，而不是让作者去对一个不存在的差。
        """
        store = _store()
        for code in R.PEER_CODES:
            for level in (1, 2):
                logical = wf_dsl.dsl_logical(
                    f"battle/action/skill/action/rare5/{code}${code}_{level}")
                path = core.table_path(store, logical)
                if not path.is_file():
                    self.skipTest(f"{code} absent on this machine")
                with self.subTest(code=code, level=level):
                    peer = _read(path)
                    self.assertEqual(R.peer_drift(code, peer), [])
                    self.assertEqual(R.lock_report(peer)["total_locked_frames"],
                                     R.PEER_STOPBALL[1] + R.SKILL_CUTIN_FRAMES)
        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                mine = R.lock_report(R.strip_ball_hold(tree))["total_locked_frames"]
                self.assertEqual(R.PEER_STOPBALL[1] + R.SKILL_CUTIN_FRAMES - mine,
                                 R.PEER_STOPBALL[1], "特克托应当比黑短整整 30 帧")

    def test_official_donor_still_carries_the_long_hold(self):
        """母本官方特克托仍是 tree[1]=2(STOP) + StopBall 140 帧 Stop —— 本次改动的对照系。"""
        logical = wf_dsl.dsl_logical(K.TEMPLATE_CODE and
                                     f"battle/action/skill/action/rare5/"
                                     f"{K.TEMPLATE_CODE}${K.TEMPLATE_CODE}_1")
        path = core.table_path(_store(), logical)
        if not path.is_file():
            self.skipTest("official donor absent on this machine")
        donor = _read(path)
        self.assertEqual(donor[1], 2)
        self.assertEqual([st[1][1:] for st in R.hold_statements(donor)], [K.TEMPLATE_STOPBALL])


class SyntheticNegatives(unittest.TestCase):
    """负向：合成树制造基线漂移，必须抛 NoEndlagError。"""

    def _stop(self, params=None):
        return ["Command", ["StopBall", *(params if params is not None else R.STOPBALL_BASELINE)]]

    def _noop(self, label="x"):
        return ["Command", ["RemoveEventFromOwner", label]]

    def _tree(self, statements, priority=R.MOVEMENT_PRIORITY_NONE):
        return ["ActionDsl", priority, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", statements]]

    def test_unexpected_count_is_rejected(self):
        tree = self._tree([self._stop(), self._stop(), self._noop()])
        with self.assertRaises(R.NoEndlagError):
            R.strip_ball_hold(tree)
        self.assertEqual(R.hold_statements(R.strip_ball_hold(tree, expected=2)), [])

    def test_drifted_stopball_params_are_rejected(self):
        for params in ([-18, 75, ["Stop"], ["AB"], 0],
                       [-18, 30, ["RestoreToSpeedBeforeActionExecution"], ["EF"], 0],
                       [-17, 10, ["RestoreToSpeedBeforeActionExecution"], ["EF"], 0]):
            with self.subTest(params=params):
                with self.assertRaises(R.NoEndlagError):
                    R.strip_ball_hold(self._tree([self._stop(params), self._noop()]))

    def test_stop_or_move_priority_is_rejected(self):
        for priority in (2, 3, 17):
            with self.subTest(priority=priority):
                with self.assertRaises(R.NoEndlagError):
                    R.strip_ball_hold(self._tree([self._stop(), self._noop()], priority=priority))

    def test_emptying_a_block_is_rejected(self):
        with self.assertRaises(R.NoEndlagError):
            R.strip_ball_hold(self._tree([self._stop()]))

    def test_suppress_ball_activity_also_counts_as_a_hold(self):
        tree = self._tree([["Command", ["SuppressBallActivity", -18, 90]], self._noop()])
        self.assertEqual(len(R.hold_statements(tree)), 1)
        self.assertEqual(R.hold_frames(tree), 0)             # 只有 StopBall 计帧
        self.assertEqual(R.hold_statements(R.strip_ball_hold(tree)), [])

    def test_tree_without_hold_is_returned_unchanged_as_a_copy(self):
        tree = self._tree([self._noop()])
        self.assertEqual(R.strip_ball_hold(tree), tree)
        self.assertIsNot(R.strip_ball_hold(tree), tree)


class WindupRealTrees(unittest.TestCase):
    """方案 B 正向（真树）：前摇压到 N，第一段激光之后逐节点不动，伤害节点逐格相等。

    源树 = **live + 方案 A**（B 是叠在 A 上发的），所以这里先 ``strip_ball_hold`` 再压。
    """

    @classmethod
    def setUpClass(cls):
        if len(TREES) != len(LOGICALS):
            raise unittest.SkipTest("tekuto DSL sources absent (no candidate package, no live store)")
        cls.bases = {logical: R.strip_ball_hold(tree) for logical, tree in TREES.items()}

    def test_baseline_matches_the_pinned_windup_timeline(self):
        for logical, base in self.bases.items():
            with self.subTest(logical=logical):
                self.assertEqual(R.windup_drift(base), [])
                self.assertEqual(sorted(R.wait_frames(base)),
                                 sorted(R.WINDUP_WAIT_BASELINE))

    def test_first_beam_lands_exactly_on_the_requested_frame(self):
        for n in R.WINDUP_TIERS:
            for logical, base in self.bases.items():
                with self.subTest(n=n, logical=logical):
                    after = R.compress_windup(base, first_beam_frame=n)
                    frames = sorted(R.wait_frames(after))
                    beam = R.windup_plan(n)["wait_frames"][R.FIRST_BEAM_FRAME]
                    self.assertEqual(beam, n)
                    self.assertIn(n, frames)
                    # 第一段激光的判定区确实建在第 n 帧
                    rows = [r for r in R.timeline(after)
                            if r["kind"] == "Command" and r["name"] == "CreateHitArea"
                            and r["shape"] == "Rectangle"]
                    self.assertEqual(min(r["frame"] for r in rows), n)

    def test_everything_after_the_first_beam_keeps_its_relative_timing(self):
        for n in R.WINDUP_TIERS:
            plan = R.windup_plan(n)
            for old, new in plan["wait_frames"].items():
                if old < R.FIRST_BEAM_FRAME:
                    continue
                with self.subTest(n=n, old=old):
                    self.assertEqual(new - n, old - R.FIRST_BEAM_FRAME)
            self.assertEqual(plan["shift_after_first_beam"], R.FIRST_BEAM_FRAME - n)

    @staticmethod
    def _undo(after, n):
        """把压完的树按 plan 逐格**还原**：Wait 帧号退回基线 + 三个被改的参数退回原值。

        还原之后必须与源树**深度相等** —— 这是比逐命令比对更强的判据：
        它同时证明「只动了这四类东西」和「一个别的字节都没碰」。
        """
        plan = R.windup_plan(n)
        undone = copy.deepcopy(after)
        R._rewrite(undone[11], 0, 0, {new: old for old, new in plan["wait_frames"].items()})
        next(c for c in R.commands(undone, "ShowEffect")
             if c[1] == R.AIM_LINE_LABEL)[5] = ["SpecifyEffectLifetimeDirectly",
                                                R.AIM_LINE_LIFETIME]
        next(c for c in R.commands(undone, "CreateHitArea")
             if c[9][0] == "Sector")[13] = ["SpecifyHitAreaLifetimeDirectly", R.SECTOR_LIFETIME]
        R.commands(undone, "RotateHitArea")[0][2] = R.SECTOR_ROTATION
        return undone

    def test_damage_nodes_are_identical_cell_by_cell(self):
        """伤害节点逐格相等：把四类改动还原回去，整棵树必须与源树深度相等。"""
        for n in R.WINDUP_TIERS:
            for logical, base in self.bases.items():
                after = R.compress_windup(base, first_beam_frame=n)
                with self.subTest(n=n, logical=logical):
                    self.assertEqual(R.commands(after, "CreateNormalAttack"),
                                     R.commands(base, "CreateNormalAttack"))
                    self.assertEqual(R.commands(after, "CreateCondition"),
                                     R.commands(base, "CreateCondition"))
                    self.assertEqual(R.commands(after, "CreateBarrier"),
                                     R.commands(base, "CreateBarrier"))
                    self.assertEqual(R.commands(after, "BindConditionAccumulationVariable"),
                                     R.commands(base, "BindConditionAccumulationVariable"))
                    self.assertEqual(after[:11], base[:11])
                    self.assertEqual(self._undo(after, n), base)

    def test_the_undo_probe_really_bites(self):
        """上一条的还原判据必须是活的：随便改一个伤害倍率，还原后就该对不上。"""
        n = R.RECOMMENDED_WINDUP
        base = next(iter(self.bases.values()))
        tampered = R.compress_windup(base, first_beam_frame=n)
        R.commands(tampered, "CreateNormalAttack")[0][6][0]["max"] += 1
        self.assertNotEqual(self._undo(tampered, n), base)

    def test_only_the_aim_line_lifetime_and_the_radar_change(self):
        for n in R.WINDUP_TIERS:
            for logical, base in self.bases.items():
                after = R.compress_windup(base, first_beam_frame=n)
                plan = R.windup_plan(n)
                with self.subTest(n=n, logical=logical):
                    for old_fx, new_fx in zip(R.commands(base, "ShowEffect"),
                                              R.commands(after, "ShowEffect")):
                        if old_fx[1] == R.AIM_LINE_LABEL:
                            self.assertEqual(new_fx[5], ["SpecifyEffectLifetimeDirectly", n])
                            self.assertEqual(old_fx[:5] + old_fx[6:], new_fx[:5] + new_fx[6:])
                        else:
                            self.assertEqual(old_fx, new_fx)
                    for old_ha, new_ha in zip(R.commands(base, "CreateHitArea"),
                                              R.commands(after, "CreateHitArea")):
                        if old_ha[9][0] != "Sector":
                            self.assertEqual(old_ha, new_ha)     # 12 个判定区里 11 个一字不动
                            continue
                        self.assertEqual(new_ha[13], ["SpecifyHitAreaLifetimeDirectly",
                                                      plan["radar"]["lifetime"]])
                        self.assertEqual(old_ha[:13], new_ha[:13])     # 含半径/开角/朝向/主体
                        self.assertEqual(old_ha[14:20], new_ha[14:20])
                        # 命中块里除了那条嵌套的 Wait（参照点链，随整体平移）没有别的变化
                        self.assertEqual([st[1][0] if st[0] == "Command" else st[1][2]
                                          for st in old_ha[23][1]],
                                         [st[1][0] if st[0] == "Command" else st[1][2]
                                          for st in new_ha[23][1]])
                        self.assertEqual([st for st in old_ha[23][1] if st[0] == "Command"],
                                         [st for st in new_ha[23][1] if st[0] == "Command"])
                    self.assertEqual(R.commands(after, "RotateHitArea")[0][2],
                                     plan["radar"]["radians_per_frame"])

    def test_charge_effect_is_pinned_because_its_thunder_is_baked_at_frame_67(self):
        """蓄力整条不动：雷鸣钉在特效自身第 67 帧，压寿命＝这一声彻底不响。"""
        for n in R.WINDUP_TIERS:
            plan = R.windup_plan(n)
            self.assertEqual(plan["wait_frames"][R.CHARGE_FRAME], R.CHARGE_FRAME)
            self.assertTrue(plan["charge"]["pinned"])
            self.assertGreaterEqual(R.CHARGE_LIFETIME, R.CHARGE_SOUND_FRAME)
            for logical, base in self.bases.items():
                after = R.compress_windup(base, first_beam_frame=n)
                with self.subTest(n=n, logical=logical):
                    charge = [c for c in R.commands(after, "ShowEffect")
                              if c[1] == R.CHARGE_LABEL]
                    self.assertEqual(len(charge), 1)
                    self.assertEqual(charge[0][5],
                                     ["SpecifyEffectLifetimeDirectly", R.CHARGE_LIFETIME])
                    row = next(r for r in R.timeline(after)
                               if r.get("label") == R.CHARGE_LABEL)
                    self.assertEqual(row["frame"], R.CHARGE_FRAME)

    def test_radar_keeps_its_total_sweep_and_cannot_tunnel(self):
        """扇形寿命按比例压、角速度按 1/比例放 ⇒ 总扫掠角恒 90°，取消线之前的扫掠角 ±5% 内。"""
        for n in R.WINDUP_TIERS:
            radar = R.windup_plan(n)["radar"]
            with self.subTest(n=n):
                self.assertAlmostEqual(radar["total_sweep_rad"], R.SECTOR_SWEEP, places=3)
                self.assertLess(abs(radar["sweep_before_missile_cancel_rad"]
                                    - radar["baseline_sweep_before_missile_cancel_rad"]),
                                0.05 * radar["baseline_sweep_before_missile_cancel_rad"])
                # 每帧步进必须远小于扇形开角，否则会「转太快跳过目标」
                self.assertLess(radar["radians_per_frame"], R.SECTOR_APERTURE / 5)
                self.assertGreaterEqual(radar["frames_before_missile_cancel"], 3)

    def test_missile_event_stays_strictly_after_missile_cancel(self):
        """按比例压缩会把 23/24 压到同一帧；撞帧＝雷达标中了也不放导弹。"""
        for n in R.WINDUP_TIERS:
            plan = R.windup_plan(n)
            with self.subTest(n=n):
                self.assertGreaterEqual(plan["missile"]["launch"] - plan["missile"]["cancel"],
                                        R.MISSILE_EVENT_MIN_GAP)
                self.assertGreater(plan["missile"]["cancel"], plan["radar"]["frame"])
                # 导弹落地仍然比第一段激光晚 4 帧（live 是 f94 vs f90）
                self.assertEqual(plan["missile"]["impact_after_first_beam"], 94 - R.FIRST_BEAM_FRAME)
        for logical, base in self.bases.items():
            after = R.compress_windup(base, first_beam_frame=R.RECOMMENDED_WINDUP)
            names = R.wait_frames(after)
            cancel = min(f for f, name in names.items() if name == "missile_cancel")
            launch = min(f for f, name in names.items() if name == "missile_event")
            with self.subTest(logical=logical):
                self.assertGreater(launch, cancel)

    def test_idempotent_encodable_and_passes_native_gates_and_scope(self):
        for n in R.WINDUP_TIERS:
            for logical, base in self.bases.items():
                after = R.compress_windup(base, first_beam_frame=n)
                with self.subTest(n=n, logical=logical):
                    self.assertEqual(R.compress_windup(after, first_beam_frame=n), after)
                    gates = PH.dsl_gates(after, element=K.ELEMENT)
                    self.assertEqual(PH.dsl_gate_failures(gates), [])
                    self.assertEqual(gates["scope_strict"], [])   # lookup-scope 零问题
                    self.assertTrue(gates["roundtrip"])
                    self.assertEqual(K.dsl_quick_problems(after), [])
                    encode_tree(after)

    def test_source_trees_are_untouched(self):
        snapshot = copy.deepcopy(self.bases)
        for base in self.bases.values():
            R.compress_windup(base, first_beam_frame=R.RECOMMENDED_WINDUP)
        self.assertEqual(self.bases, snapshot)

    def test_the_only_numeric_spillover_is_the_f0_self_buff_window(self):
        """根块 f0 的 ACSkillDamage 不随激光平移 ⇒ 会多吃几跳。必须算得出、且只多不少。"""
        for n in R.WINDUP_TIERS:
            for logical, base in self.bases.items():
                after = R.compress_windup(base, first_beam_frame=n)
                report = R.windup_report(base, after, R.windup_plan(n))
                with self.subTest(n=n, logical=logical):
                    window = report["self_buff_window"]
                    self.assertEqual(window["before"]["buff_frames"],
                                     window["after"]["buff_frames"])
                    self.assertGreater(window["extra_hits_inside"], 0)
                    self.assertGreater(window["extra_multiplier"], 0)
                    self.assertTrue(report["unchanged"]["multipliers"])
                    self.assertTrue(report["unchanged"]["relative_timing_after_first_beam"])
                    self.assertEqual(report["perceived_wait_frames"]["after"],
                                     R.SKILL_CUTIN_FRAMES + n)

    def test_recommended_tier_is_the_only_one_that_lets_the_radar_finish(self):
        """推荐 36 的硬理由：雷达盘自身动画 32 帧，只有 36 档能在开火前放完。"""
        finishes = {n: R.windup_plan(n)["radar"]["effect_finishes_before_first_beam"]
                    for n in R.WINDUP_TIERS}
        self.assertTrue(finishes[R.RECOMMENDED_WINDUP])
        self.assertEqual([n for n, ok in finishes.items() if ok], [R.RECOMMENDED_WINDUP])
        self.assertGreaterEqual(R.RECOMMENDED_WINDUP, R.RADAR_EFFECT_FRAMES)


class WindupSyntheticNegatives(unittest.TestCase):
    """方案 B 负向：基线漂移 / 参数越界必须抛 ``WindupError``。"""

    def _base(self):
        if len(TREES) != len(LOGICALS):
            raise unittest.SkipTest("tekuto DSL sources absent")
        return R.strip_ball_hold(TREES[LOGICALS[0]])

    def test_out_of_range_windup_is_rejected(self):
        for n in (0, 12, 23, 20, 90, 120, -5):
            with self.subTest(n=n):
                with self.assertRaises(R.WindupError):
                    R.windup_plan(n)

    def test_a_drifted_wait_frame_is_rejected(self):
        moved = copy.deepcopy(self._base())
        holder = next(st[1][6][1] for st in moved[11][1]
                      if st[0] == "Command" and st[1][0] == "FindNearSubjects")
        wait = next(st for st in holder
                    if st[0] == "Event" and st[1][0] == "Wait"
                    and st[1][1] == R.FIRST_BEAM_FRAME)
        wait[1][1] = R.FIRST_BEAM_FRAME + 1
        self.assertTrue(R.windup_drift(moved))
        with self.assertRaises(R.WindupError):
            R.compress_windup(moved, first_beam_frame=R.RECOMMENDED_WINDUP)

    def test_a_drifted_aim_line_lifetime_is_rejected(self):
        tree = copy.deepcopy(self._base())
        R.commands(tree, "ShowEffect")
        aim = next(c for c in R.commands(tree, "ShowEffect") if c[1] == R.AIM_LINE_LABEL)
        aim[5] = ["SpecifyEffectLifetimeDirectly", 88]
        self.assertTrue(R.windup_drift(tree))
        with self.assertRaises(R.WindupError):
            R.compress_windup(tree, first_beam_frame=R.RECOMMENDED_WINDUP)

    def test_a_drifted_radar_rotation_or_lifetime_is_rejected(self):
        for mutate in (lambda t: R.commands(t, "RotateHitArea")[0].__setitem__(2, 0.1),
                       lambda t: next(c for c in R.commands(t, "CreateHitArea")
                                      if c[9][0] == "Sector").__setitem__(
                           13, ["SpecifyHitAreaLifetimeDirectly", 45])):
            tree = copy.deepcopy(self._base())
            mutate(tree)
            with self.subTest(mutation=repr(mutate)):
                self.assertTrue(R.windup_drift(tree))
                with self.assertRaises(R.WindupError):
                    R.compress_windup(tree, first_beam_frame=R.RECOMMENDED_WINDUP)

    def test_a_drifted_charge_lifetime_is_rejected(self):
        tree = copy.deepcopy(self._base())
        charge = next(c for c in R.commands(tree, "ShowEffect") if c[1] == R.CHARGE_LABEL)
        charge[5] = ["SpecifyEffectLifetimeDirectly", 30]
        self.assertTrue(R.windup_drift(tree))
        with self.assertRaises(R.WindupError):
            R.compress_windup(tree, first_beam_frame=R.RECOMMENDED_WINDUP)

    def test_two_waits_on_the_same_absolute_frame_are_rejected(self):
        tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", [["Event", ["Wait", 7, "a", ["Block", [["Command", ["ShakeCamera", 1]]]]]],
                           ["Event", ["Wait", 7, "b", ["Block", [["Command", ["ShakeCamera", 1]]]]]]]]]
        with self.assertRaises(R.WindupError):
            R.wait_frames(tree)
        self.assertTrue(R.windup_drift(tree))

    def test_compressing_an_already_compressed_tree_to_another_tier_is_rejected(self):
        """压过一次的树再压到别的档 = 在没核对过的基线上改帧号，必须红（不许链式压缩）。"""
        base = self._base()
        thirty = R.compress_windup(base, first_beam_frame=30)
        with self.assertRaises(R.WindupError):
            R.compress_windup(thirty, first_beam_frame=36)
        self.assertEqual(R.compress_windup(thirty, first_beam_frame=30), thirty)   # 同档仍幂等

    def test_a_synthetic_tree_without_the_baseline_is_rejected(self):
        tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", [["Command", ["RemoveEventFromOwner", "x"]]]]]
        self.assertTrue(R.windup_drift(tree))
        with self.assertRaises(R.WindupError):
            R.compress_windup(tree, first_beam_frame=R.RECOMMENDED_WINDUP)


class OptionAIsUnaffectedByOptionB(unittest.TestCase):
    """方案 B 默认关闭：不给 ``--windup-frames`` 时，A 的候选与 plan 一个字节都不变。"""

    def test_apply_candidate_never_compresses_the_windup(self):
        if len(TREES) != len(LOGICALS) or not (PACKAGE / "manifest.json").is_file():
            self.skipTest("tekuto workspace/live sources absent")
        try:
            evidence = R.apply_candidate(ROOT, apply=False)
        except Exception as exc:                                   # noqa: BLE001
            self.skipTest(f"plan cannot be built here: {exc}")
        for item in evidence["plan"]["dsl"]:
            self.assertEqual(item["lock_after"]["total_locked_frames"], R.SKILL_CUTIN_FRAMES)
        for logical, tree in TREES.items():
            self.assertEqual(sorted(R.wait_frames(R.strip_ball_hold(tree))),
                             sorted(R.WINDUP_WAIT_BASELINE), logical)

    def test_cli_refuses_to_write_the_candidate_with_option_b(self):
        with io.StringIO() as noise, contextlib.redirect_stderr(noise):
            with self.assertRaises(SystemExit):
                R.main(["--write-candidate", "--windup-frames", "30"])
            self.assertIn("不允许与 --write-candidate 同用", noise.getvalue())

    def test_option_b_constants_are_self_consistent(self):
        self.assertIn(R.RECOMMENDED_WINDUP, R.WINDUP_TIERS)
        self.assertEqual(min(R.WINDUP_TIERS), R.MIN_WINDUP_FRAMES)
        self.assertEqual(R.SECTOR_SWEEP, round(R.SECTOR_LIFETIME * R.SECTOR_ROTATION, 5))
        self.assertAlmostEqual(R.SECTOR_SWEEP, R.SECTOR_APERTURE, places=4)
        self.assertEqual(R.OPTION_B_REL, R.REVISION_DIR + "/option-b")
        self.assertNotIn(R.WORKSPACE_REL, R.OPTION_B_REL)


class Texts(unittest.TestCase):
    def test_clause_is_appended_once_and_is_idempotent(self):
        after = R.skill_description(R.SKILL_DESC_BEFORE)
        self.assertEqual(after, R.SKILL_DESC_AFTER)
        self.assertEqual(R.skill_description(after), after)
        self.assertTrue(after.startswith(R.SKILL_DESC_BEFORE))
        self.assertTrue(after.endswith(R.SEPARATOR + R.NO_ENDLAG_CLAUSE))
        self.assertEqual(len(after) - len(R.SKILL_DESC_BEFORE),
                         len(R.SEPARATOR) + len(R.NO_ENDLAG_CLAUSE))

    def test_clause_is_word_for_word_the_batch_wording(self):
        """与本批黑 ``outlaw_panther_moon`` 的 live 技能说明同一句（只换分隔符）。"""
        table = core.table_path(_store(), K.ACTION)
        if not table.is_file():
            self.skipTest("live store not available")
        nested = core.load_nested_table_bytes(table.read_bytes(), K.ACTION)
        if "outlaw_panther_moon" not in nested.rows:
            self.skipTest("kuro row not on this machine")
        for text in dict(nested.rows["outlaw_panther_moon"].text_rows()).values():
            self.assertTrue(core.read_csv_lines(text)[0][1].endswith("／" + R.NO_ENDLAG_CLAUSE))

    def test_unknown_text_is_rejected(self):
        with self.assertRaises(R.NoEndlagError):
            R.skill_description("别的技能说明")

    def test_kit_generator_produces_the_same_final_text(self):
        """重跑 kit 不会把文案退回改前（也不会把这句话叠两遍）。

        2026-09-27 平衡第二批（第一批输出 + 第二批覆盖）：kit 落表文案在本工具的 ``SKILL_DESC_AFTER``
        之上再写出技能倍率的层数上限「（最多10层）」（``wf_balance_20260927b_tekuto``），
        「不再进入硬直」一句仍只出现一次、仍在句尾。
        平衡第三批（``wf_balance_20260927c_tekuto``）不再改技能说明：强化后的不封顶只写在强化条目里
        （主会话 2026-09-27 口径），落表文案 == 第二批。
        """
        want_b = R.SKILL_DESC_AFTER.replace(K.BALANCE_B_DESC_ANCHOR,
                                            K.BALANCE_B_DESC_ANCHOR + K.BALANCE_B_DESC_CAP)
        want = want_b
        self.assertNotEqual(want, R.SKILL_DESC_AFTER)
        self.assertEqual(K._DESC_BALANCE_B, want_b)
        self.assertEqual(K._DESC_BALANCE_C, want_b)
        self.assertNotIn("不受此限", want)
        self.assertEqual(K.TEXTS["desc1"], want)
        self.assertEqual(K.TEXTS["desc2"], want)
        self.assertEqual(K._DESC_NO_ENDLAG, R.SKILL_DESC_AFTER)
        self.assertEqual(R.text_problems("skill", want), [])
        self.assertEqual(K._DESC, R.SKILL_DESC_BEFORE)
        self.assertEqual(K.REV7_NO_ENDLAG_SUFFIX, R.SEPARATOR + R.NO_ENDLAG_CLAUSE)

    def test_shipped_text_passes_the_separator_and_panel_gates(self):
        self.assertEqual(R.text_problems("skill", R.SKILL_DESC_AFTER), [])

    def test_gate_catches_duplicates_and_dangling_separators(self):
        self.assertTrue(R.text_problems("x", R.SKILL_DESC_AFTER + R.SEPARATOR + R.NO_ENDLAG_CLAUSE))
        self.assertTrue(R.text_problems("x", R.SKILL_DESC_AFTER + R.SEPARATOR))
        self.assertTrue(R.text_problems("x", "甲" + R.SEPARATOR * 2 + R.NO_ENDLAG_CLAUSE))


class KitGenerator(unittest.TestCase):
    """首发 kit 的生成源同步：重跑 ``--step kit`` 带不回后摇。"""

    @classmethod
    def setUpClass(cls):
        try:
            cls.plan = K.load_revision_plan(ROOT)
        except Exception as exc:                                  # noqa: BLE001
            raise unittest.SkipTest(f"revision plan absent: {exc}")

    def test_blueprint_has_no_ball_hold_and_the_gate_catches_a_regression(self):
        for level in ("1", "2"):
            with self.subTest(level=level):
                tree = K.donor_tree(level, self.plan)
                self.assertEqual(R.hold_statements(tree), [])
                self.assertEqual(K.ball_hold_problems(tree), [])
                regressed = copy.deepcopy(tree)
                regressed[11][1].insert(3, ["Command", ["StopBall", *K.TEMPLATE_STOPBALL]])
                self.assertTrue(K.ball_hold_problems(regressed))
                self.assertTrue([p for p in K.dsl_quick_problems(regressed) if "StopBall" in p])

    def test_donor_shape_is_still_verified_against_the_official_tree(self):
        logical = wf_dsl.dsl_logical(
            f"battle/action/skill/action/rare5/{K.TEMPLATE_CODE}${K.TEMPLATE_CODE}_1")
        path = core.table_path(_store(), logical)
        if not path.is_file():
            self.skipTest("official donor absent on this machine")
        self.assertEqual(K.template_stopball_drift(_read(path)), [])
        broken = _read(path)
        next(st for st in broken[11][1] if R._is_hold_statement(st))[1][2] = 999
        self.assertTrue(K.template_stopball_drift(broken))


class CandidatePackage(unittest.TestCase):
    """--write-candidate 之后：候选包里零 StopBall，两处文案与常量逐字一致。"""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((PACKAGE / "manifest.json").read_bytes())
        if R.SNAPSHOT_KEY not in cls.manifest.get("snapshot", {}):
            raise unittest.SkipTest("no-endlag revision has not been written to the candidate yet")

    def test_candidate_dsl_has_no_ball_hold(self):
        for logical in LOGICALS:
            tree = _read(PACKAGE / "roots/common" / logical)
            self.assertEqual(R.hold_statements(tree), [], logical)
            self.assertEqual(tree[1], R.MOVEMENT_PRIORITY_NONE, logical)

    def _want_desc(self) -> str:
        """2026-09-27 平衡第二批（第一批输出 + 第二批覆盖）：批次暂存脚本回写候选后 manifest 带
        ``revision_20260927b`` 快照，技能说明在本工具的 SKILL_DESC_AFTER 之上多了「（最多10层）」。
        平衡第三批回写后 package_version 升到 ``wf_balance_20260927c_tekuto.PACKAGE_VERSION``（快照键由第三批
        暂存脚本定，这里按版本号判断），技能说明不变（_DESC_BALANCE_C == _DESC_BALANCE_B，强化后效果只写在强化条目）。"""
        import wf_balance_20260927c_tekuto as balance_c
        as_tuple = lambda v: tuple(int(x) for x in str(v).split("."))        # noqa: E731
        if as_tuple(self.manifest.get("package_version", "0")) >= as_tuple(balance_c.PACKAGE_VERSION[balance_c.PACKAGES[0]]):
            return K._DESC_BALANCE_C
        if BALANCE_B_SNAPSHOT in self.manifest.get("snapshot", {}):
            return K._DESC_BALANCE_B
        return R.SKILL_DESC_AFTER

    def test_candidate_texts_match_the_pinned_strings(self):
        if not self.manifest["snapshot"][R.SNAPSHOT_KEY]["texts"]["applied"]:
            self.skipTest("candidate was written with --no-text")
        want = self._want_desc()
        action = core.load_nested_table_bytes(
            (PACKAGE / "roots/common" / K.ACTION).read_bytes(), K.ACTION).rows[R.CODE]
        for level, text in action.text_rows().items():
            self.assertEqual(core.read_csv_lines(text)[0][1], want, level)
        rows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(
            (PACKAGE / "roots/common" / K.TEXT).read_bytes())[R.CID])
        self.assertEqual([rows[0][5], rows[0][7]], [want] * 2)

    def test_candidate_server_mirror_follows_character_text(self):
        if not self.manifest["snapshot"][R.SNAPSHOT_KEY]["texts"]["applied"]:
            self.skipTest("candidate was written with --no-text")
        mirror = json.loads((PACKAGE / "roots/server/cdndata/character_text.json").read_bytes())
        self.assertEqual([mirror[R.CID][0][5], mirror[R.CID][0][7]], [self._want_desc()] * 2)

    def test_gameplay_rows_are_untouched_by_this_revision(self):
        """本轮不动 ability / leader / unique —— 候选包里这三张表仍与 live 逐字节相同。"""
        for logical in (K.ABILITY, K.LEADER, K.UNIQUE):
            live = core.table_path(_store(), logical)
            if not live.is_file():
                self.skipTest("live store not available")
            live_rows = core.read_orderedmap_file_from_bytes(live.read_bytes())
            cand_rows = core.read_orderedmap_file_from_bytes(
                (PACKAGE / "roots/common" / logical).read_bytes())
            keys = [k for k in cand_rows if k.startswith(R.CID)]
            self.assertTrue(keys, logical)
            for key in keys:
                self.assertEqual(cand_rows[key], live_rows.get(key), f"{logical}:{key}")


class PlanDocument(unittest.TestCase):
    """交付口径：plan.json 必须先报 70→60，主假设排第一，判据不许写成「和黑一致」。"""

    @classmethod
    def setUpClass(cls):
        if len(TREES) != len(LOGICALS) or not (PACKAGE / "manifest.json").is_file():
            raise unittest.SkipTest("tekuto workspace/live sources absent")
        try:
            cls.doc = R.plan_document(R.apply_candidate(ROOT, apply=False))
        except Exception as exc:                                   # noqa: BLE001
            raise unittest.SkipTest(f"plan cannot be built here: {exc}")

    def test_headline_reports_the_perceived_frames_not_a_full_removal(self):
        headline = self.doc["headline"]
        self.assertIn("70", headline)
        self.assertIn("60", headline)
        self.assertIn("14%", headline)
        self.assertIn("整段去掉", headline)          # 只允许以「不要用整段去掉交差」的形式出现
        self.assertIn("不要", headline)
        self.assertNotIn("整段去掉固定，", self.doc["change"])
        self.assertIn("70", self.doc["change"])

    def test_primary_hypothesis_leads_the_findings(self):
        first = self.doc["findings"][0]
        self.assertIn("主假设", first)
        self.assertIn("90", first)                  # f90 第一段激光 / 1.5 s 前摇
        self.assertIn("1.5", first)
        self.assertIn("拍板", first + self.doc["publish"]["gate"])
        self.assertIn("author_question", self.doc)
        self.assertIn("1.5", self.doc["author_question"])

    def test_no_finding_repeats_the_wrong_client_citation(self):
        blob = json.dumps(self.doc, ensure_ascii=False)
        self.assertIn("SquadManagerImpl.as:734-735", blob)
        self.assertNotIn("invokeActionSkillIfPossible", blob)
        for text in self.doc["findings"]:
            if "MemberImpl" in text:
                self.assertIn("SummonsMultiball", text)
                self.assertIn("跳过", text)

    def test_device_checks_say_shorter_than_kuro_never_identical(self):
        checks = self.doc["device_checks"]
        joined = "".join(checks)
        self.assertIn("更跟手", joined)
        self.assertIn("30", joined)
        self.assertIn("没生效", joined)
        self.assertNotIn("完全一致", joined.replace("手感完全一致，说明这次改动没生效", ""))
        # 演出判据必须承认发射原点会变，不能宣称位置一致
        self.assertIn("发射原点", joined)

    def test_plan_carries_the_beam_anchor_evidence(self):
        for item in self.doc["dsl"]:
            self.assertTrue(item["beam_anchors"]["origin_follows_ball"])
            self.assertGreaterEqual(item["beam_anchors"]["anchored_to_ball_and_tracking_pos"], 11)
            self.assertEqual(item["lock_before"]["total_locked_frames"], 70)
            self.assertEqual(item["lock_after"]["total_locked_frames"], 60)


class SourceClaims(unittest.TestCase):
    """两份源码里被复核判定为「事实性夸大／引文错误」的句子不许回来。"""

    SOURCES = {
        "wf_tekuto_no_endlag_revision.py": Path(R.__file__),
        "wf_seasonal7_kit_tekuto.py": Path(K.__file__),
    }

    #: 出现这些词的那一行，说明作者是在**引用并纠正**旧说法，而不是在主张它。
    CORRECTION_MARKERS = ("更正", "夸大", "不可写成", "不能写成", "上一版", "别写成", "禁")

    def test_no_source_claims_the_positions_are_unchanged(self):
        """旧说法「删掉停球不改变任何一段的位置」只允许以被纠正的形式出现，不许当主张写。"""
        for name, path in self.SOURCES.items():
            with self.subTest(source=name):
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if "不改变任何一段的位置" not in line and "位置不变" not in line:
                        continue
                    self.assertTrue(any(mark in line for mark in self.CORRECTION_MARKERS),
                                    f"{name}:{number} 把「位置不变」当成主张写了：{line.strip()}")

    def test_no_source_cites_memberimpl_as_the_cutin_owner(self):
        for name, path in self.SOURCES.items():
            with self.subTest(source=name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("MemberImpl.invokeActionSkillIfPossible", text)
                if "MemberImpl.as:2593" in text:
                    self.assertIn("SummonsMultiball", text)

    def test_both_sources_name_the_real_cutin_owner(self):
        for name, path in self.SOURCES.items():
            with self.subTest(source=name):
                self.assertIn("SquadManagerImpl.as:734-735", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

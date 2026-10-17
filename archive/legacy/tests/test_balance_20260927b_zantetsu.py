# -*- coding: utf-8 -*-
"""斩铁·白梅 159998 · 2026-09-27 平衡调整第二批（成长 + 629 Down）修订模块回归。

fixture = live 1.4.1049 只读快照（1.5 批之后，与候选 s7-zantetsu 1.0.2 逐字相同）。逐项断言：
能力3 三条 250 连击成长的限次 / 强度、队长 #7–#9 由能力行派生且逐步 ×1/5、629 剑 PF 树只改 p13
（5 段 15 → 2.5）、其余行与节点逐字保留（含 1.5 批的格）、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、
合法性与 DSL 门禁为空、AMF3 往返，以及生成器链「kit → 09-17 → 1.5 批 → 第二批」== revise()。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_zantetsu as M15  # noqa: E402
import wf_balance_20260927b_zantetsu as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_dsl  # noqa: E402
import wf_seasonal7_kit_zantetsu as K  # noqa: E402
import wf_zantetsu_fever_revision as F  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_zantetsu.json'
FIXTURE_15 = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927_zantetsu.json'
STRINGS = {M.CAS_CHANGE_SKILL, M.CAS_PF}
MIDAUTUMN_DESIGN = ROOT / "work/character_packs/midautumn-20260920/design"


def load() -> dict:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {(kind, key): value for kind, key, value in fx["reads"]}


def reader(data):
    return lambda kind, key: data[kind, key]


def diff_cells(a: list[str], b: list[str]) -> dict[int, tuple[str, str]]:
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


def tree_diff(a, b, path="$") -> list[str]:
    if type(a) is not type(b):
        return [path]
    if isinstance(a, list):
        if len(a) != len(b):
            return [path]
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in tree_diff(x, y, f"{path}[{i}]")]
    if isinstance(a, dict):
        if set(a) != set(b):
            return [path]
        return [p for k in a for p in tree_diff(a[k], b[k], f"{path}.{k}")]
    return [] if a == b else [path]


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(set(self.data), set(M.BEFORE))
        for key, want in M.BEFORE.items():
            self.assertEqual(M.digest(self.data[key]), want, key)

    def test_ability3_growth_rows_capped_in_place(self):
        before, after = self.live("ability", M.A3), self.out["ability"][M.A3]
        self.assertEqual(len(after), 7)
        want = {
            1: {34: ("(None)", "4"), 51: ("50000", "12500"), 52: ("100000", "25000")},
            2: {34: ("(None)", "4"), 51: ("50000", "12500"), 52: ("100000", "25000")},
            3: {34: ("(None)", "5"), 51: ("5000", "1000"), 52: ("10000", "2000")},
        }
        for i, (old, new) in enumerate(zip(before, after)):
            self.assertEqual(diff_cells(old, new), want.get(i, {}), i)
        for i in (1, 2, 3):                      # 触发 / 光共鸣前置 / 主位整键不变
            row = after[i]
            self.assertEqual(row[27:32], ["12", "", "", "25000000", "25000000"])
            self.assertEqual((row[6], row[9], row[10], row[11], row[35]), ("2", "600000", "600000", "White", "0"))
        self.assertEqual({r[1] for r in after}, {"false"})
        # 满叠落在官方带内：攻/技伤 50→100%、独立乘区 5→10%
        for i, (low, high) in ((1, (50, 100)), (2, (50, 100)), (3, (5, 10))):
            cap = int(after[i][34])
            self.assertEqual((cap * int(after[i][51]) / 1000, cap * int(after[i][52]) / 1000), (low, high))

    def test_batch_15_cells_are_preserved(self):
        leader, a3 = self.out["leader"][M.CID], self.out["ability"][M.A3]
        self.assertEqual((leader[3][25], leader[3][26], leader[3][27]), ("23", "6", "White"))
        self.assertEqual((a3[4][28], a3[5][28], a3[5][51], a3[5][52]), ("6", "6", "5000000", "5000000"))
        self.assertNotIn(M.A1, self.out["ability"])                      # 能力1（1.5 批去 202）不碰

    def test_leader_growth_rows_are_derived_and_slowed(self):
        before, after = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual(len(after), 10)
        self.assertEqual(after[:7], before)                               # 原 7 行逐字保留
        a3 = self.live("ability", M.A3)
        for li, ai in M.LEADER_SOURCE.items():
            derived = M.leader_row_from_ability(a3[ai])
            self.assertEqual(diff_cells(derived, after[li]),
                             {49: (a3[ai][51], M.LEADER_GROWTH[ai][0]), 50: (a3[ai][52], M.LEADER_GROWTH[ai][1])})
            # 逐步 ×1/5（250 连击 3 分钟典型 6 次 ≤15），低/满 1:2 保持
            self.assertEqual(int(after[li][49]) * 5, int(a3[ai][51]))
            self.assertEqual(int(after[li][50]) * 5, int(a3[ai][52]))
            self.assertEqual(after[li], M._row(M.LEADER_NCOLS, M.LEADER_NEW[li]))
        # 队长原有行里没有同触发同 kind 可合并的行
        self.assertFalse([r for r in before if r[25] == "12" and r[28] == M.COMBO_250])

    def test_describe_after(self):
        got = {f"leader_ability:{M.CID}#{i}": D.describe_line(self.out["leader"][M.CID][i], "leader_ability")
               for i in (7, 8, 9)}
        got.update({f"ability:{M.A3}#{i}": D.describe_line(self.out["ability"][M.A3][i], "ability")
                    for i in (1, 2, 3)})
        self.assertEqual(got, M.DESCRIBE_AFTER)
        self.assertEqual(self.out["notes"]["describe_after"], M.DESCRIBE_AFTER)

    def test_pf_tree_only_p13_changes(self):
        before, after = self.live("dsl", M.PF_PROGRAM), self.out["dsl"][M.PF_PROGRAM]
        paths = tree_diff(before, after)
        self.assertEqual(len(paths), 2, paths)                            # p13 的 min / max
        self.assertTrue(all(p.endswith(("[13][0].min", "[13][0].max")) for p in paths), paths)
        (attack,) = M._cmds(after, "CreateNormalAttack")
        self.assertEqual(attack[13], [{"min": 0.5, "max": 0.5}])
        self.assertEqual((M.down_per_invoke(before), M.down_per_invoke(after)), (15, 2.5))
        self.assertLessEqual(M.down_per_invoke(after), M.DOWN_CAP_PER_INVOKE)
        self.assertEqual(attack[6], [{"min": 6.3, "max": 6.3}])         # 倍率 / 元素 / 连击加成不动
        self.assertEqual((attack[2], attack[8]), (M.ELEMENT + 1, True))

    def test_pf_tree_amf3_roundtrip_and_dsl_gates(self):
        tree = self.out["dsl"][M.PF_PROGRAM]
        raw = wf_dsl.encode_amf3(tree)
        back = wf_dsl.parse_dsl(raw)["tree"]
        self.assertEqual(back, tree)
        (attack,) = M._cmds(back, "CreateNormalAttack")
        self.assertIsInstance(attack[13][0]["min"], float)
        self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [])
        self.assertEqual(L.action_dsl_subject_binding_problems(tree), [])
        self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])
        self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [])
        self.assertEqual(wf_dsl.player_side_dsl_problems(tree), [])
        self.assertEqual(K.sig_problems(tree), [])
        self.assertEqual(K.lookup_scope_problems(tree), [])
        self.assertEqual(M.dsl_problems(tree), [])

    def test_invoke_trigger_is_skill_cast_not_high_frequency(self):
        row = self.live("ability", M.A1)[M.A1_INVOKE_INDEX]
        self.assertEqual((row[27], row[28], row[35], row[47], row[71]), ("23", "0", "0", "629", M.PF_PROGRAM))
        M._invoke_guard(self.live("ability", M.A1))
        for col, value in ((35, "60"), (27, "4"), (71, "x")):
            rows = self.live("ability", M.A1)
            rows[M.A1_INVOKE_INDEX][col] = value
            with self.assertRaises(ValueError, msg=col):
                M._invoke_guard(rows)

    def test_row_legality_and_kit_gates(self):
        rows = [("leader_ability", r) for r in self.out["leader"][M.CID]]
        rows += [("ability", r) for r in self.out["ability"][M.A3]]
        for kind, row in rows:
            self.assertEqual(L.client_legality_problems(kind, row), [], row)
            self.assertEqual(L.declared_block_field_problems(kind, row), [], row)
            self.assertEqual(L.invoke_skill_string_problems(row, frozenset(STRINGS), kind), [], row)
            self.assertEqual(L.ability_element_column_problems(kind, row, M.ELEMENT), [], row)
            gate = K.row_gate(kind, row, set(STRINGS))
            self.assertFalse(K._row_gate_failed(gate), gate)

    def test_no_new_client_capabilities(self):
        self.assertEqual(M.capability_set("leader_ability", self.out["leader"][M.CID]),
                         M.capability_set("leader_ability", self.live("leader", M.CID)))
        self.assertEqual(M.capability_set("ability", self.out["ability"][M.A3]),
                         M.capability_set("ability", self.live("ability", M.A3)))

    def test_only_changed_keys_are_returned(self):
        self.assertEqual(set(self.out["leader"]), {M.CID})
        self.assertEqual(set(self.out["ability"]), {M.A3})
        self.assertEqual(set(self.out["dsl"]), {M.PF_PROGRAM})
        for kind in ("cas", "text", "table", "action", "server_text", "new_programs"):
            self.assertFalse(self.out[kind], kind)
        self.assertEqual((M.PACKAGES, M.PACKAGE_VERSION, M.CAPABILITIES, M.REVIEWED_DRIFT),
                         (["s7-zantetsu"], {"s7-zantetsu": "1.0.3"}, [], {}))
        self.assertIs(self.out["notes"]["runtime_verified"], False)
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_baseline_drift_is_rejected_and_inputs_are_not_mutated(self):
        saved = deepcopy(self.data)
        M.revise(reader(self.data))
        self.assertEqual(self.data, saved)
        for kind, key in M.BEFORE:
            data = deepcopy(self.data)
            value = data[kind, key]
            if kind == "dsl":
                value[1] = 2
            else:
                value[0][0] = value[0][0] + "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_rerun_on_own_output_is_rejected(self):
        data = deepcopy(self.data)
        data["leader", M.CID] = self.out["leader"][M.CID]
        data["ability", M.A3] = self.out["ability"][M.A3]
        data["dsl", M.PF_PROGRAM] = self.out["dsl"][M.PF_PROGRAM]
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))

    def test_transforms_are_idempotent_and_reject_unreviewed_shapes(self):
        leader, a3 = self.out["leader"][M.CID], self.out["ability"][M.A3]
        pf = self.out["dsl"][M.PF_PROGRAM]
        self.assertEqual(M.balance_rows(leader, a3), (leader, a3))
        self.assertEqual(M.pf_tree(pf), pf)
        cases = [
            (M.ability3_rows, self.live("ability", M.A3), 1, 30, "20000000"),     # 阈值漂移
            (M.ability3_rows, self.live("ability", M.A3), 2, 51, "60000"),        # 强度漂移
            (M.ability3_rows, self.live("ability", M.A3), 3, 34, "5"),            # 已限次但强度未改（半成品）
            (M.ability3_rows, self.live("ability", M.A3), 1, 48, "5"),            # 目标漂移
        ]
        for fn, rows, index, col, value in cases:
            rows[index][col] = value
            with self.assertRaises(ValueError, msg=(fn.__name__, index, col)):
                fn(rows)
        with self.assertRaises(ValueError):
            M.ability3_rows(self.live("ability", M.A3)[:-1])
        with self.assertRaises(ValueError):                                     # 队长行数不对
            M.leader_rows(self.live("leader", M.CID)[:-1])
        tampered = deepcopy(leader)
        tampered[8][49] = "20000"
        with self.assertRaises(ValueError):                                     # 追加行被改过
            M.leader_rows(tampered)
        doubled = self.live("leader", M.CID)
        doubled[0][28] = M.COMBO_250                                            # 原有行混入同阈值
        with self.assertRaises(ValueError):
            M.leader_rows(doubled)
        tree = self.live("dsl", M.PF_PROGRAM)
        M._cmds(tree, "CreateNormalAttack")[0][13] = [{"min": 2, "max": 2}]
        with self.assertRaises(ValueError):
            M.pf_tree(tree)
        tree = self.live("dsl", M.PF_PROGRAM)
        M._cmds(tree, "CreateNormalAttack")[0][6] = [{"min": 7, "max": 7}]      # 非 p13 节点漂移
        with self.assertRaises(ValueError):
            M.pf_tree(tree)
        tree = self.live("dsl", M.PF_PROGRAM)
        M._cmds(tree, "CreateHitArea")[0][14] = ["CalculatedUsingMaxNumOfHits", 6]
        with self.assertRaises(ValueError):
            M.pf_tree(tree)


class GeneratorConsistencyTest(unittest.TestCase):
    """生成器链：kit 改版回放 → 09-17 Fever 修订 → 1.5 批 → 第二批，产物必须 == revise()。"""

    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))
        fx = json.loads(FIXTURE_15.read_text(encoding="utf-8"))
        cls.kit = fx["kit_rows"]
        cls.data15 = {(kind, key): value for kind, key, value in fx["reads"]}

    def test_batch_15_output_is_this_batch_input(self):
        out15 = M15.revise(lambda kind, key: deepcopy(self.data15[kind, key]))
        self.assertEqual(out15["leader"][M.CID], self.data["leader", M.CID])
        self.assertEqual(out15["ability"][M.A3], self.data["ability", M.A3])
        self.assertEqual(out15["ability"][M.A1], self.data["ability", M.A1])

    def test_kit_fever_15_b_chain_matches_revise(self):
        leader, third = F.revise_rows(deepcopy(self.kit["leader"]), deepcopy(self.kit[M.A3]))
        leader, _first, third = M15.balance_rows(leader, deepcopy(self.kit[M.A1]), third)
        leader, third = M.balance_rows(leader, third)
        self.assertEqual(leader, self.out["leader"][M.CID])
        self.assertEqual(third, self.out["ability"][M.A3])

    def test_fever_apply_candidate_runs_batch2_last(self):
        src = inspect.getsource(F.apply_candidate)
        self.assertLess(src.index("revise_rows("), src.index("balance.balance_rows("))
        self.assertLess(src.index("balance.balance_rows("), src.index("balance_b.balance_rows("))
        self.assertLess(src.index("balance_b.balance_rows("), src.index("candidate.splice(LEADER"))
        # 第三轮（wf_balance_20260927c_zantetsu）接在本批之后时，候选版本号取第三轮的。
        self.assertTrue(any(f"{m}.PACKAGE_VERSION['s7-zantetsu']" in src for m in ("balance_b", "balance_c")))
        self.assertIn("balance_b.pf_tree(", src)
        self.assertIn("wf_balance_20260927b_zantetsu", F.__doc__)

    def test_fever_apply_candidate_end_to_end_equals_revise(self):
        """替身候选：表行喂 kit 产物，两档技能树用替身（09-17 revise_tree 另有单测），PF 树喂 kit 产物（= live 改前）。"""
        from unittest import mock
        tables = {F.LEADER: {M.CID: self.kit["leader"]},
                  F.ABILITY: {M.A1: self.kit[M.A1], M.A3: self.kit[M.A3]}}
        pf_logical = wf_dsl.dsl_logical(M.PF_PROGRAM)
        stub = self.data["dsl", M.PF_PROGRAM]                  # 过门禁的真实树，当作两档技能树的替身

        def deflate(tree):
            return F.encode_tree(tree)

        raw = {pf_logical: deflate(self.data["dsl", M.PF_PROGRAM])}
        levels = {}
        for level in (1, 2):
            logical = f"battle/action/skill/action/rare5/{M.CODE}${M.CODE}_{level}.action.dsl.amf3.deflate"
            raw[logical] = deflate(stub)
            levels[level] = hashlib.sha256(raw[logical]).hexdigest()
        spliced, emitted, created, finished = {}, {}, {}, {}

        class FakeCandidate:
            def __init__(self, *args, **kwargs):
                created.update(kwargs)

            def read(self, tier, logical):
                return logical if logical in tables else raw[logical]

            def splice(self, logical, replacements, **kwargs):
                spliced.setdefault(logical, {}).update(deepcopy(replacements))

            def emit(self, tier, logical, data):
                emitted[logical] = data

            def finish(self, metadata, apply=False):
                finished.update(metadata=metadata, apply=apply)
                return metadata

        def fake_orderedmap(key):
            return {k: F.core.write_csv_lines(rows) for k, rows in tables[key].items()}

        with mock.patch.object(F, "RevisionCandidate", FakeCandidate), \
                mock.patch.object(F.core, "read_orderedmap_file_from_bytes", fake_orderedmap), \
                mock.patch.object(F, "TREE_SHA", levels), \
                mock.patch.object(F, "revise_tree", lambda tree: tree):
            F.apply_candidate(ROOT, ROOT / "work/character_packs/s7-zantetsu")
        # 第三轮只再改队长 250 连击三行（链尾 == c 的断言在 test_balance_20260927c_zantetsu）：兼容 b / b→c 两种状态。
        import wf_balance_20260927c_zantetsu as MC
        self.assertIn(created["package_version"], (M.PACKAGE_VERSION["s7-zantetsu"], MC.PACKAGE_VERSION["s7-zantetsu"]))
        self.assertEqual(set(spliced[F.LEADER]), {M.CID})
        self.assertIn(spliced[F.LEADER][M.CID], (self.out["leader"][M.CID], MC.leader_rows(self.out["leader"][M.CID])))
        self.assertEqual(spliced[F.ABILITY][M.A3], self.out["ability"][M.A3])
        self.assertEqual(spliced[F.ABILITY][M.A1], self.data["ability", M.A1])   # 1.5 批产物，本批不动
        pf = wf_dsl.parse_dsl(zlib.decompress(emitted[pf_logical], -15))["tree"]
        self.assertEqual(pf, self.out["dsl"][M.PF_PROGRAM])
        self.assertEqual(finished["metadata"]["balance_20260927b"]["pf_down_per_invoke"], 2.5)
        self.assertIs(finished["apply"], False)

    def test_kit_source_is_untouched(self):
        # kit 源码不引用第二批，链路只写在 Fever 修订模块（kit 已钉冻结 donor 1499963#1（FROZEN_DONORS），
        # gates.json 的 kit_source_sha256 登记为已知过期、待按步序重跑）。
        self.assertNotIn("wf_balance_20260927b_zantetsu", inspect.getsource(K))
        self.assertEqual((K.CID, K.CODE, K.ELEMENT, K.PF_PROGRAM), (M.CID, M.CODE, M.ELEMENT, M.PF_PROGRAM))

    @unittest.skipUnless((ROOT / K.REVISION_REL).is_file() and (ROOT / K.PF_DONOR_REL).is_file(),
                         "seasonal7 revision plan / knight_lv3 donor (gitignored work/) absent")
    def test_kit_pf_tree_then_batch2_equals_revise(self):
        plan = K.load_revision(ROOT)
        tree = K.build_pf_action_tree(ROOT, plan)
        self.assertEqual(tree, self.data["dsl", M.PF_PROGRAM])            # kit 产物 = live 改前
        self.assertEqual(M.pf_tree(tree), self.out["dsl"][M.PF_PROGRAM])


class DonorTest(unittest.TestCase):
    """跨角色 donor：没有别的 kit / 设计稿借本批改的 1599983#1–#3（1 基 #L2–#L4）或队长新增行。"""

    CHANGED = ("1599983#1", "1599983#2", "1599983#3", "1599983#L2", "1599983#L3", "1599983#L4",
               "159998#7", "159998#8", "159998#9", "159998#L8", "159998#L9", "159998#L10")

    def _hits(self, text: str) -> list[str]:
        return [ref for ref in self.CHANGED
                if any(f"{ref}{end}" in text for end in ('"', "'", ",", " ", ")"))]

    def test_mod_tools_sources(self):
        own = {"wf_balance_20260927b_zantetsu.py"}
        hits = {p.name: self._hits(p.read_text(encoding="utf-8"))
                for p in (ROOT / "mod-tools").glob("*.py") if p.name not in own}
        self.assertEqual({k: v for k, v in hits.items() if v}, {})
        # 正向对照：同一扫描能看到别的 kit 借斩铁未改行（丝缇涅尔「友技回槽」借 1599983#4）
        stinel = (ROOT / "mod-tools/wf_midautumn_kit_stinel.py").read_text(encoding="utf-8")
        self.assertIn('"1599983#4"', stinel)

    @unittest.skipUnless(MIDAUTUMN_DESIGN.is_dir(), "midautumn designs (gitignored work/) absent")
    def test_midautumn_designs(self):
        hits = {p.name: self._hits(p.read_text(encoding="utf-8")) for p in MIDAUTUMN_DESIGN.glob("*.json")}
        self.assertEqual({k: v for k, v in hits.items() if v}, {})


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""斩铁·白梅 159998 · 2026-09-27 平衡第三轮（成长复核）修订模块回归。

fixture = live 1.4.1053 只读快照（= 第二批产物，与候选 s7-zantetsu 1.0.3 逐字相同）。逐项断言：队长 250 连击
三行 c49/c50 = 能力行原值 ×4/5（40→80% / 40→80% / 4→8%）、其余格与原 7 行逐字保留、能力 3 封顶版与 629 剑
PF 树不动（D4）、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁为空，以及生成器链
「kit → 09-17 → 1.5 批 → 第二批 → 第三轮」（``wf_zantetsu_fever_revision.apply_candidate``）== revise()。
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
import wf_balance_20260927b_zantetsu as B  # noqa: E402
import wf_balance_20260927c_zantetsu as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_dsl  # noqa: E402
import wf_seasonal7_kit_zantetsu as K  # noqa: E402
import wf_zantetsu_fever_revision as F  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURE = HERE / "fixtures/balance_20260927c_zantetsu.json"
FIXTURE_B = HERE / "fixtures/balance_20260927b_zantetsu.json"
FIXTURE_15 = HERE / "fixtures/balance_20260927_zantetsu.json"


def _load(path):
    fx = json.loads(path.read_text(encoding="utf-8"))
    return {(kind, key): value for kind, key, value in fx["reads"]}, fx


def load():
    return _load(FIXTURE)[0]


def reader(data):
    return lambda kind, key: data[kind, key]


def diff_cells(a, b):
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))
        cls.b_data = _load(FIXTURE_B)[0]
        cls.b_out = B.revise(reader(cls.b_data))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(set(self.data), set(M.BEFORE))
        for key, want in M.BEFORE.items():
            self.assertEqual(M.digest(self.data[key]), want, key)

    def test_input_is_the_batch2_output(self):
        self.assertEqual(self.b_out["leader"][M.CID], self.data["leader", M.CID])

    def test_only_the_three_growth_rows_change(self):
        before, after = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual((10, 10), (len(before), len(after)))
        want = {7: {49: ("10000", "40000"), 50: ("20000", "80000")},
                8: {49: ("10000", "40000"), 50: ("20000", "80000")},
                9: {49: ("1000", "4000"), 50: ("2000", "8000")}}
        for i, (old, new) in enumerate(zip(before, after)):
            self.assertEqual(diff_cells(old, new), want.get(i, {}), i)
        for i in want:                                   # 触发 250 连击 / 光共鸣前置 / 自身 / 不限次不变
            row = after[i]
            self.assertEqual((row[4], row[9], row[25], row[28], row[32], row[46]),
                             ("2", "White", "12", B.COMBO_250, "(None)", "0"))

    def test_values_are_original_times_four_fifths(self):
        a3 = self.b_data["ability", B.A3]                       # 第二批之前的能力 3 源行 = 原值
        after = self.out["leader"][M.CID]
        num, den = M.FACTOR
        for li, ai in B.LEADER_SOURCE.items():
            orig = (int(a3[ai][51]), int(a3[ai][52]))
            self.assertEqual(orig, M.ORIGINAL[li])
            self.assertEqual((int(after[li][49]), int(after[li][50])), (orig[0] * num // den, orig[1] * num // den))
            self.assertEqual(int(after[li][50]), 2 * int(after[li][49]))   # 低 / 满 1:2 保持
        self.assertEqual((num, den), (4, 5))

    def test_describe_after(self):
        rows = self.out["leader"][M.CID]
        self.assertEqual({i: D.describe_line(rows[i], "leader_ability") for i in M.DESCRIBE_AFTER}, M.DESCRIBE_AFTER)

    def test_row_legality_and_kit_gates(self):
        for row in self.out["leader"][M.CID]:
            self.assertEqual(L.client_legality_problems("leader_ability", row), [], row)
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [], row)
            self.assertEqual(L.invoke_skill_string_problems(row, M.STRINGS, "leader_ability"), [], row)
            self.assertEqual(L.ability_element_column_problems("leader_ability", row, M.ELEMENT), [], row)
            gate = K.row_gate("leader_ability", row, set(M.STRINGS))
            self.assertFalse(K._row_gate_failed(gate), gate)

    def test_no_new_client_capabilities(self):
        self.assertEqual(B.capability_set("leader_ability", self.out["leader"][M.CID]),
                         B.capability_set("leader_ability", self.live("leader", M.CID)))

    def test_only_changed_keys_are_returned(self):
        self.assertEqual(set(self.out["leader"]), {M.CID})
        # 技能强化文案（R2）：只改强化条目一串；能力3 行与两档 DSL 只读
        self.assertEqual(self.out["cas"], {M.FEVER_TEXT: [[M.NEW_FEVER_TEXT]]})
        for kind in ("ability", "text", "table", "action", "dsl", "server_text", "new_programs"):
            self.assertFalse(self.out[kind], kind)       # 能力 3 封顶版（D4）/ 629 剑 PF 树 / 技能说明都不动
        self.assertEqual((M.PACKAGES, M.PACKAGE_VERSION, M.CAPABILITIES, M.REVIEWED_DRIFT),
                         (["s7-zantetsu"], {"s7-zantetsu": "1.0.4"}, [], {}))
        self.assertEqual((M.CID, M.CODE), (B.CID, B.CODE))
        self.assertIs(self.out["notes"]["runtime_verified"], False)
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_baseline_drift_is_rejected_and_inputs_are_not_mutated(self):
        saved = deepcopy(self.data)
        M.revise(reader(self.data))
        self.assertEqual(self.data, saved)
        for kind, key in M.BEFORE:
            data = deepcopy(self.data)
            if kind == "dsl":
                data[kind, key].append("x")                  # DSL 树：根上多一个节点
            else:
                data[kind, key][0][0] += "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_rerun_on_own_output_is_rejected_but_transform_is_idempotent(self):
        data = deepcopy(self.data)
        data["leader", M.CID] = self.out["leader"][M.CID]
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))
        self.assertEqual(M.leader_rows(self.out["leader"][M.CID]), self.out["leader"][M.CID])

    def test_unreviewed_shapes_are_rejected(self):
        for index, col, value in ((7, 49, "20000"), (8, 45, "32"), (9, 28, "20000000"), (8, 32, "4")):
            rows = self.live("leader", M.CID)
            rows[index][col] = value
            with self.assertRaises(ValueError, msg=(index, col)):
                M.leader_rows(rows)
        with self.assertRaises(ValueError):
            M.leader_rows(self.live("leader", M.CID)[:7])                   # 第二批之前的 7 行形态
        doubled = self.live("leader", M.CID)
        doubled[0][28] = B.COMBO_250                                        # 原有行混入同阈值
        with self.assertRaises(ValueError):
            M.leader_rows(doubled)


class SkillEnhancementTextTest(unittest.TestCase):
    """作者「技能都强化效果只在队长技或者能力里面按照格式写,技能里面不要重复描述强化后的效果」（主会话口径 R1–R4）。"""

    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))

    def test_flag_entry_uses_the_official_format(self):
        self.assertEqual(self.data["cas", M.FEVER_TEXT],
                         [["Fever模式中，强化『超振动斩铁剑·寒梅一闪』，追加随连击数提升的威力，并赋予贯穿效果"]])
        self.assertEqual(self.out["cas"][M.FEVER_TEXT],
                         [["强化『超振动斩铁剑·寒梅一闪』：Fever模式中追加随连击数提升的威力，并赋予自身贯穿效果"]])
        self.assertEqual(M.flag_entry_problems(M.NEW_FEVER_TEXT), [])
        self.assertTrue(M.flag_entry_problems(M.OLD_FEVER_TEXT))                     # 旧写法开头不合格式
        self.assertNotIn("共鸣", M.NEW_FEVER_TEXT)
        # 另一条条目本来就合规（能力1 536，第二批已写），本轮不动
        self.assertEqual(M.flag_entry_problems("强化『超振动斩铁剑·寒梅一闪』的威力与「光属性抗性降低效果」"), [])

    def test_basis_rows_and_dsl(self):
        a3 = self.data["ability", B.A3]
        trees = {program: self.data["dsl", program] for program in M.SKILLS}
        self.assertEqual(M.flag_basis_problems(a3, trees), [])
        row = a3[M.FLAG2_ROW]
        self.assertEqual((row[47], row[70], row[6], row[9], row[11]), ("704", M.FEVER_TEXT, "2", "600000", "White"))
        self.assertEqual(D.describe_line(row, "ability"), f"光·编成≥6 时: 自身 切换技能Flag2[{M.FEVER_TEXT}]")
        # 变异：贯穿对象改全队 / 连击加成在 Fever else 支也开 / 开关行去共鸣 ⇒ 依据不成立
        for program in M.SKILLS:
            tree = deepcopy(trees[program])
            piercing = [args for chain, args in M._commands(tree) if args[0] == "CreateCondition"
                        and any(isinstance(c, list) and c and c[0] == "ACPiercing" for c in args[2])]
            piercing[0][1] = 11
            self.assertTrue(M.flag_basis_problems(a3, {**trees, program: tree}))
            tree = deepcopy(trees[program])
            attacks = [args for chain, args in M._commands(tree) if args[0] == "CreateNormalAttack"
                       and M._under(chain, "ConditionalsChangeSkillFlag", 2, 2)
                       and not M._under(chain, "ConditionalsFeverMode", 1)]
            attacks[0][M.NA_COMBO_ARG] = True
            self.assertTrue(M.flag_basis_problems(a3, {**trees, program: tree}))
        rows = deepcopy(a3)
        rows[M.FLAG2_ROW][6] = "0"
        self.assertTrue(M.flag_basis_problems(rows, trees))

    def test_reapply_is_rejected(self):
        with self.assertRaises(ValueError):
            M.fever_text(self.out["cas"][M.FEVER_TEXT])
        data = deepcopy(self.data)
        data["cas", M.FEVER_TEXT] = self.out["cas"][M.FEVER_TEXT]
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))


class GeneratorConsistencyTest(unittest.TestCase):
    """生成器链：kit 改版回放 → 09-17 Fever 修订 → 1.5 批 → 第二批 → 第三轮，产物必须 == revise()。"""

    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))
        cls.b_data = _load(FIXTURE_B)[0]
        cls.b_out = B.revise(reader(cls.b_data))
        _d15, fx15 = _load(FIXTURE_15)
        cls.kit = fx15["kit_rows"]

    def test_kit_fever_15_b_c_chain_matches_revise(self):
        leader, third = F.revise_rows(deepcopy(self.kit["leader"]), deepcopy(self.kit[B.A3]))
        leader, _first, third = M15.balance_rows(leader, deepcopy(self.kit[B.A1]), third)
        leader, third = B.balance_rows(leader, third)
        self.assertEqual(leader, self.data["leader", M.CID])                # 本轮输入 == 链上第二批产物
        self.assertEqual(M.leader_rows(leader), self.out["leader"][M.CID])
        self.assertEqual(third, self.b_out["ability"][B.A3])                  # 能力 3 停在第二批

    def test_fever_apply_candidate_runs_round3_last(self):
        src = inspect.getsource(F.apply_candidate)
        order = ["balance.balance_rows(", "balance_b.balance_rows(", "balance_c.leader_rows(lead)",
                 "candidate.splice(LEADER"]
        self.assertEqual(sorted(src.index(s) for s in order), [src.index(s) for s in order])
        self.assertIn("package_version=balance_c.PACKAGE_VERSION['s7-zantetsu']", src)
        self.assertIn("import wf_balance_20260927c_zantetsu as balance_c", src)
        self.assertIn("wf_balance_20260927c_zantetsu", F.__doc__)

    def test_fever_apply_candidate_end_to_end_equals_revise(self):
        """替身候选（同第二批测试）：表行喂 kit 产物，两档技能树用替身，PF 树喂 kit 产物（= 第二批改前）。"""
        from unittest import mock
        tables = {F.LEADER: {M.CID: self.kit["leader"]},
                  F.ABILITY: {B.A1: self.kit[B.A1], B.A3: self.kit[B.A3]}}
        pf_logical = wf_dsl.dsl_logical(B.PF_PROGRAM)
        stub = self.b_data["dsl", B.PF_PROGRAM]
        raw = {pf_logical: F.encode_tree(self.b_data["dsl", B.PF_PROGRAM])}
        levels = {}
        for level in (1, 2):
            logical = f"battle/action/skill/action/rare5/{M.CODE}${M.CODE}_{level}.action.dsl.amf3.deflate"
            raw[logical] = F.encode_tree(stub)
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
        self.assertEqual(created["package_version"], M.PACKAGE_VERSION["s7-zantetsu"])
        self.assertEqual(spliced[F.LEADER], self.out["leader"])
        self.assertEqual(spliced[F.CAS], self.out["cas"])                         # 强化条目 = 第三轮输出
        self.assertEqual(spliced[F.ABILITY][B.A3], self.b_out["ability"][B.A3])   # 能力 3 = 第二批
        self.assertEqual(spliced[F.ABILITY][B.A1], self.b_data["ability", B.A1])  # 能力 1 = 1.5 批
        pf = wf_dsl.parse_dsl(zlib.decompress(emitted[pf_logical], -15))["tree"]
        self.assertEqual(pf, self.b_out["dsl"][B.PF_PROGRAM])                     # PF 树 = 第二批
        meta = finished["metadata"]["balance_20260927c"]
        self.assertEqual(meta["module"], "wf_balance_20260927c_zantetsu")
        self.assertEqual(meta["combo250_leader_steps"], {str(i): list(v) for i, v in M.C_VALUES.items()})
        json.dumps(finished["metadata"], ensure_ascii=False)
        self.assertIs(finished["apply"], False)

    def test_kit_source_is_untouched(self):
        self.assertNotIn("wf_balance_20260927c_zantetsu", inspect.getsource(K))
        self.assertEqual((K.CID, K.CODE, K.ELEMENT), (M.CID, M.CODE, M.ELEMENT))


if __name__ == "__main__":
    unittest.main()

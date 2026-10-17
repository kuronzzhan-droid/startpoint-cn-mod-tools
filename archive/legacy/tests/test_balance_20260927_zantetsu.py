# -*- coding: utf-8 -*-
"""斩铁·白梅 159998 · 2026-09-27 平衡批次（第二批）修订模块回归。

fixture = live 1.4.1048 只读快照（与候选 s7-zantetsu 1.0.1 逐字相同）+ kit 改版施工单回放行
（09-17 Fever 修订之前）。逐项断言：6 格改动、其余逐字保留、BEFORE 漂移拒绝、不改输入、
合法性门禁为空、生成器链「kit → Fever 修订 → 本批」== revise()，以及三个借用斩铁 live 行做
donor 的 kit（丝缇涅尔 / 芙拉菲 / 妮可拉）钉住 c6=202 后产物不随本批漂移。
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_zantetsu as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_seasonal7_kit_zantetsu as K  # noqa: E402
import wf_zantetsu_fever_revision as F  # noqa: E402
import wf_balance_20260927b_zantetsu as MB  # noqa: E402  （第二批：Fever 修订链尾追加）

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURE = HERE / "fixtures/balance_20260927_zantetsu.json"
NICOLA_DESIGN = ROOT / "work/character_packs/midautumn-20260920/design/nicola.json"
STRINGS = {M.CAS_CHANGE_SKILL, M.CAS_PF}


def load():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {(kind, key): value for kind, key, value in fx["reads"]}, fx["kit_rows"]


def reader(data):
    return lambda kind, key: data[kind, key]


def diff_cells(a: list[str], b: list[str]) -> dict[int, tuple[str, str]]:
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.kit = load()
        cls.out = M.revise(reader(cls.data))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def test_leader_friend_gauge_row_only_changes_puller(self):
        before, after = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual(len(after), 7)
        for i, (old, new) in enumerate(zip(before, after)):
            want = {26: ("7", "6")} if i == 3 else {}
            self.assertEqual(diff_cells(old, new), want, i)
        row = after[3]
        self.assertEqual((row[25], row[26], row[27]), ("23", "6", "White"))     # 除自身外的光属性角色发动技能
        self.assertEqual((row[28], row[29], row[33]), ("100000", "100000", "0"))
        self.assertEqual((row[45], row[46], row[49], row[50]), ("211", "0", "2500", "5000"))   # 自身技能槽 2.5→5%
        self.assertEqual((row[4], row[7], row[8], row[9]), ("2", "600000", "600000", "White"))  # 光共鸣前置不变

    def test_ability3_friend_rows_puller_and_combo(self):
        before, after = self.live("ability", M.A3), self.out["ability"][M.A3]
        self.assertEqual(len(after), 7)
        want = {4: {28: ("7", "6")},
                5: {28: ("7", "6"), 51: ("2500000", "5000000"), 52: ("2500000", "5000000")}}
        for i, (old, new) in enumerate(zip(before, after)):
            self.assertEqual(diff_cells(old, new), want.get(i, {}), i)
        gauge, combo = after[4], after[5]
        for row in (gauge, combo):
            self.assertEqual(row[27:32], ["23", "6", "White", "100000", "100000"])
            self.assertEqual((row[6], row[9], row[10], row[11]), ("2", "600000", "600000", "White"))
            self.assertEqual(row[35], "0")
        self.assertEqual((gauge[47], gauge[48], gauge[51], gauge[52]), ("211", "0", "5000", "5000"))
        self.assertEqual((combo[47], combo[48], combo[51], combo[52]), ("226", "0", "5000000", "5000000"))
        self.assertEqual({r[1] for r in after}, {"false"})                     # 能力3 整键主位限制不动

    def test_ability1_main_slot_gate_removed_in_place(self):
        before, after = self.live("ability", M.A1), self.out["ability"][M.A1]
        self.assertEqual(len(after), 3)
        for i, (old, new) in enumerate(zip(before, after)):
            self.assertEqual(diff_cells(old, new), {6: ("202", "0")} if i in (1, 2) else {}, i)
        for row in after:
            self.assertEqual(row[1], "true")
            self.assertEqual([row[c] for c in (6, 13, 20)].count("202"), 0)
        for row in after[1:]:                                                  # 前置2 光共鸣原位保留、不留空串
            self.assertEqual(row[6:13], ["0", "", "", "", "", "", ""])
            self.assertEqual(row[13:19], ["2", "", "", "600000", "600000", "White"])
        self.assertEqual((after[1][47], after[1][70]), ("536", M.CAS_CHANGE_SKILL))
        self.assertEqual((after[2][47], after[2][70], after[2][71]), ("629", M.CAS_PF, M.PF_PROGRAM))
        self.assertTrue(D.describe_line(before[1], "ability").startswith("持有者为主位 且 "))
        self.assertFalse(any(D.describe_line(r, "ability").startswith("持有者为主位") for r in after))

    def test_describe_after(self):
        got = {f"leader_ability:{M.CID}#3": D.describe_line(self.out["leader"][M.CID][3], "leader_ability")}
        for key, index in ((M.A1, 1), (M.A1, 2), (M.A3, 4), (M.A3, 5)):
            got[f"ability:{key}#{index}"] = D.describe_line(self.out["ability"][key][index], "ability")
        self.assertEqual(got, M.DESCRIBE_AFTER)
        self.assertEqual(self.out["notes"]["describe_after"], M.DESCRIBE_AFTER)

    def test_only_changed_keys_are_returned(self):
        self.assertEqual(set(self.out["leader"]), {M.CID})
        self.assertEqual(set(self.out["ability"]), {M.A1, M.A3})
        for kind in ("cas", "text", "table", "action", "dsl", "server_text", "new_programs"):
            self.assertFalse(self.out[kind], kind)
        self.assertEqual((M.PACKAGES, M.PACKAGE_VERSION, M.CAPABILITIES, M.REVIEWED_DRIFT),
                         (["s7-zantetsu"], {"s7-zantetsu": "1.0.2"}, [], {}))
        self.assertIs(self.out["notes"]["runtime_verified"], False)

    def test_row_legality_and_kit_gates(self):
        rows = [("leader_ability", r) for r in self.out["leader"][M.CID]]
        rows += [("ability", r) for key in (M.A1, M.A3) for r in self.out["ability"][key]]
        for kind, row in rows:
            self.assertEqual(L.client_legality_problems(kind, row), [], row)
            self.assertEqual(L.declared_block_field_problems(kind, row), [], row)
            self.assertEqual(L.invoke_skill_string_problems(row, frozenset(STRINGS), kind), [], row)
            self.assertEqual(L.ability_element_column_problems(kind, row, M.ELEMENT), [], row)
            gate = K.row_gate(kind, row, set(STRINGS))
            self.assertFalse(K._row_gate_failed(gate), gate)
        # 629 行缺文案键必须被门禁抓住（阴性对照）
        self.assertTrue(L.invoke_skill_string_problems(self.out["ability"][M.A1][2], frozenset(), "ability"))

    def test_no_new_client_capabilities(self):
        for kind, key in (("leader_ability", M.CID), ("ability", M.A1), ("ability", M.A3)):
            table = "leader" if kind == "leader_ability" else "ability"
            self.assertEqual(M.capability_set(kind, self.out[table][key]),
                             M.capability_set(kind, self.live(table, key)), key)

    def test_baseline_drift_is_rejected_and_inputs_are_not_mutated(self):
        saved = deepcopy(self.data)
        M.revise(reader(self.data))
        self.assertEqual(self.data, saved)
        for kind, key in M.BEFORE:
            data = deepcopy(self.data)
            value = data[kind, key]
            value[0][0] = value[0][0] + "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
        self.assertEqual(M.digest(self.data["leader", M.CID]), M.BEFORE["leader", M.CID])

    def test_transforms_are_idempotent_and_reject_unreviewed_shapes(self):
        leader, a1, a3 = self.out["leader"][M.CID], self.out["ability"][M.A1], self.out["ability"][M.A3]
        self.assertEqual(M.balance_rows(leader, a1, a3), (leader, a1, a3))
        cases = [
            (M.leader_rows, self.live("leader", M.CID), 3, 49, "3000"),        # 强度漂移
            (M.leader_rows, self.live("leader", M.CID), 3, 33, "300"),         # CT 漂移
            (M.ability1_rows, self.live("ability", M.A1), 1, 6, "203"),        # 前置换成仅副位
            (M.ability1_rows, self.live("ability", M.A1), 2, 18, "Black"),     # 共鸣组漂移
            (M.ability3_rows, self.live("ability", M.A3), 5, 51, "3000000"),   # 连击基线漂移
            (M.ability3_rows, self.live("ability", M.A3), 4, 28, "4"),         # 未审 puller
        ]
        for fn, rows, index, col, value in cases:
            rows[index][col] = value
            with self.assertRaises(ValueError, msg=(fn.__name__, index, col)):
                fn(rows)
        rows = self.live("ability", M.A1)
        rows[0][1] = "false"
        with self.assertRaises(ValueError):
            M.ability1_rows(rows)
        with self.assertRaises(ValueError):
            M.ability3_rows(self.live("ability", M.A3)[:-1])
        with self.assertRaises(ValueError):
            M.leader_rows(self.live("leader", M.CID) + [self.live("leader", M.CID)[0]])


class GeneratorConsistencyTest(unittest.TestCase):
    """生成器链：kit 改版施工单回放 → 09-17 Fever 修订 → 本批，产物必须 == revise()。"""

    @classmethod
    def setUpClass(cls):
        cls.data, cls.kit = load()
        cls.out = M.revise(reader(cls.data))

    def test_kit_then_fever_reproduces_live_before_balance(self):
        leader, third = F.revise_rows(deepcopy(self.kit["leader"]), deepcopy(self.kit[M.A3]))
        self.assertEqual(leader, self.data["leader", M.CID])
        self.assertEqual(third, self.data["ability", M.A3])
        self.assertEqual(self.kit[M.A1], self.data["ability", M.A1])    # Fever 修订不碰能力1

    def test_kit_fever_balance_chain_matches_revise(self):
        leader, third = F.revise_rows(deepcopy(self.kit["leader"]), deepcopy(self.kit[M.A3]))
        leader, first, third = M.balance_rows(leader, deepcopy(self.kit[M.A1]), third)
        self.assertEqual(leader, self.out["leader"][M.CID])
        self.assertEqual({M.A1: first, M.A3: third}, self.out["ability"])

    def test_fever_apply_candidate_runs_balance_after_its_revision(self):
        src = inspect.getsource(F.apply_candidate)
        self.assertLess(src.index("revise_rows("), src.index("balance.balance_rows("))
        # 第二批（wf_balance_20260927b_zantetsu）接在本批之后，候选版本号取第二批的（第三轮接上后取第三轮的）。
        self.assertTrue(any(f"{m}.PACKAGE_VERSION['s7-zantetsu']" in src for m in ("balance_b", "balance_c")))
        self.assertLess(src.index("balance.balance_rows("), src.index("balance_b.balance_rows("))
        self.assertIn("{CID+'1': first, CID+'3': ab}", src)
        self.assertIn("balance.row_problems(", src)
        self.assertLess(src.index("balance.balance_rows("), src.index("candidate.splice(LEADER"))

    def test_fever_apply_candidate_splices_equal_revise(self):
        """功能性回放 apply_candidate 的表行部分（替身候选只喂 kit 产物，读到 DSL 时截停）。"""
        from unittest import mock
        tables = {F.LEADER: {M.CID: self.kit["leader"]},
                  F.ABILITY: {M.A1: self.kit[M.A1], M.A3: self.kit[M.A3]}}
        spliced: dict = {}
        created: dict = {}

        class Stop(Exception):
            pass

        class FakeCandidate:
            def __init__(self, *args, **kwargs):
                created.update(kwargs)

            def read(self, tier, logical):
                if logical in tables:
                    return logical
                raise Stop(logical)

            def splice(self, logical, replacements, **kwargs):
                spliced.setdefault(logical, {}).update(deepcopy(replacements))

        def fake_orderedmap(raw):
            return {key: F.core.write_csv_lines(rows) for key, rows in tables[raw].items()}

        with mock.patch.object(F, "RevisionCandidate", FakeCandidate), \
                mock.patch.object(F.core, "read_orderedmap_file_from_bytes", fake_orderedmap):
            with self.assertRaises(Stop):
                F.apply_candidate(ROOT, ROOT / "work/character_packs/s7-zantetsu")
        # 第二批接在本批之后：期望 = 本批输出 + 第二批覆盖（队长追加 #7–#9、能力3 #1–#3 限次；能力1 不动）。
        # 第三轮（wf_balance_20260927c_zantetsu）只再改队长 250 连击三行：兼容 b / b→c 两种状态。
        import wf_balance_20260927c_zantetsu as MC
        self.assertIn(created["package_version"], (MB.PACKAGE_VERSION["s7-zantetsu"], MC.PACKAGE_VERSION["s7-zantetsu"]))
        leader_b, third_b = MB.balance_rows(self.out["leader"][M.CID], self.out["ability"][M.A3])
        self.assertIn(spliced[F.LEADER], ({M.CID: leader_b}, {M.CID: MC.leader_rows(leader_b)}))
        self.assertEqual(spliced[F.ABILITY], {M.A1: self.out["ability"][M.A1], M.A3: third_b})
        self.assertEqual(set(spliced[F.CAS]), {F.FEVER_TEXT})

    def test_fever_revision_docstring_names_the_chain(self):
        # 链路说明只写在 Fever 修订模块：kit 源码不引用本批（kit 已钉冻结 donor 1499963#1（FROZEN_DONORS），
        # gates.json 的 kit_source_sha256 登记为已知过期、待按步序重跑）。
        self.assertIn("wf_seasonal7_kit_zantetsu", F.__doc__)
        self.assertIn("wf_balance_20260927_zantetsu.balance_rows", F.__doc__)
        self.assertNotIn("wf_balance_20260927_zantetsu", inspect.getsource(K))
        self.assertEqual((K.CID, K.CODE, K.ELEMENT), (M.CID, M.CODE, M.ELEMENT))
        self.assertEqual((F.CID, F.CODE), (M.CID, M.CODE))
        self.assertEqual(set(K.CAS_KEYS), STRINGS)

    def test_kit_rows_fixture_matches_live_kit_replay(self):
        try:
            pass  # Imports resolve from this checkout/package, not external source copies.
            import test_seasonal7_kit_zantetsu as T
            ctx = T._context()
        except unittest.SkipTest:
            raise
        except Exception as exc:                                     # 没有 live profile / 官方基线的机器
            self.skipTest(f"live store / official baseline unavailable: {exc}")
        if not (ctx.root / K.REVISION_REL).is_file():
            self.skipTest("seasonal7 revision plan (gitignored work/) absent")
        _design, plan = K.load_revised_design(ctx.root)
        rows = K.revision_rows(ctx, plan)
        self.assertEqual(rows["leader"], self.kit["leader"])
        self.assertEqual(rows["abilities"][M.A1], self.kit[M.A1])
        self.assertEqual(rows["abilities"][M.A3], self.kit[M.A3])


class DonorPinTest(unittest.TestCase):
    """丝缇涅尔 / 芙拉菲 / 妮可拉以 live 1599981#1 为 donor 回放 536 行：钉住 c6=202 后与本批无关。"""

    @classmethod
    def setUpClass(cls):
        cls.data, _ = load()
        cls.old_donor = cls.data["ability", M.A1][1]
        cls.new_donor = M.revise(reader(cls.data))["ability"][M.A1][1]

    def assert_pinned(self, cells, expect):
        old = KL.apply_cells(self.old_donor, cells, KL.ABILITY_NCOLS)
        new = KL.apply_cells(self.new_donor, cells, KL.ABILITY_NCOLS)
        self.assertEqual(old, new)
        self.assertEqual(D.describe_line(new, "ability"), expect)
        unpinned = {k: v for k, v in cells.items() if int(k) != 6}
        self.assertNotEqual(KL.apply_cells(self.new_donor, unpinned, KL.ABILITY_NCOLS), old)   # 不钉就会漂

    def test_stinel_536_row(self):
        import wf_midautumn_kit_stinel as S
        (entry,) = [e for e in S.ABILITY[1][2] if e[1] == "1599981#1"]
        _tag, _donor, source, cells, expect = entry
        self.assertEqual((source, cells[6]), ("live", "202"))
        unisonable, statue, _ = S.ABILITY[1]
        self.assert_pinned({0: f"{S.CODE}_1", 1: unisonable, 2: statue, **cells}, expect)

    def test_fluffy_536_row(self):
        import wf_midautumn_kit_fluffy as FL
        (entry,) = [e for e in FL.PLAN[1] if e[0] == "1599981#1"]
        _donor, source, cells, expect = entry
        self.assertEqual((source, cells[6]), ("live", "202"))
        self.assert_pinned(cells, expect)

    @unittest.skipUnless(NICOLA_DESIGN.is_file(), "midautumn design (gitignored work/) absent")
    def test_nicola_536_row(self):
        design = json.loads(NICOLA_DESIGN.read_text(encoding="utf-8"))
        entries = [e for block in design["plan"]["ability"]["keys"].values() for e in block["records"]
                   if e["donor"] == "live:ability:1599981#L2"]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["cells"].get("6"), "202")
        self.assert_pinned(entry["cells"], entry["desc_expected"])
        self.assertEqual(KL.apply_cells(self.new_donor, entry["cells"], KL.ABILITY_NCOLS),
                         [str(x) for x in entry["row_final"]])


if __name__ == "__main__":
    unittest.main()

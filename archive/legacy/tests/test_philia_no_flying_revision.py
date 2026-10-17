# -*- coding: utf-8 -*-
"""wf_philia_no_flying_revision：真树正向（删净/其余不动/幂等）＋ 合成树负向（基线漂移抛错）。"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
import zlib
from collections import Counter
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_kit_philia as K  # noqa: E402
import wf_philia_no_flying_revision as R  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "work/character_packs/s7-philia/package"
FIXTURE = Path(__file__).resolve().parent / "fixtures/philia_no_flying_before.json"
LOGICALS = tuple(wf_dsl.dsl_logical(p) for p in R.SKILL_PROGRAMS + R.PF_PROGRAMS)


def _store() -> Path:
    profile = json.loads((ROOT / "mod-tools/profiles.json").read_bytes())["profiles"]["cn"]
    store = Path(profile["store"])
    return store if store.is_absolute() else ROOT / store


def _read(path: Path):
    return wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]


def _current(logical: str):
    """当前那棵树：先 workspace 候选，缺了再 live store。

    2026-09-27 平衡第二批（``wf_balance_20260927b_philia``）在去浮游之后又改了这五棵树的 CNA p13；
    暂存/发布后先按其精确逆变换还原成本修订的产物再比（暂存前原样返回）。
    """
    import wf_balance_20260927b_philia as B2
    for path in (PACKAGE / "roots/common" / logical, core.table_path(_store(), logical)):
        if path.is_file():
            return B2.before_batch2(BASELINE[logical]["program"], _read(path))
    return None


def _restore_flying(tree, entry: dict):
    """按 fixture 把那条 ACFlying 语句塞回去，重建改动前的真树。

    ``pruned_search=True``（技能两档）：整条 ``FindAllSubjects`` 连块一起插回根语句表；
    否则（PF 三档）：只把语句插回现有搜索块的原位置。
    """
    before = copy.deepcopy(tree)
    statement = copy.deepcopy(entry["statement"])
    if entry["pruned_search"]:
        search = copy.deepcopy(entry["search_shell"])
        search[1][9][1].insert(entry["inner_index"], statement)
        before[11][1].insert(entry["root_index"], search)
    else:
        search = before[11][1][entry["root_index"]]
        assert search[1][0] == "FindAllSubjects", entry["program"]
        search[1][9][1].insert(entry["inner_index"], statement)
    return before


def _pair(logical: str, entry: dict):
    """(改动前的真树, 删完的真树)。候选/live 还没改时直接用它，改完了就按 fixture 复原。"""
    current = _current(logical)
    if current is None:
        return None
    if R.flying_statements(current):
        return current, R.strip_flying(current)
    return _restore_flying(current, entry), current


BASELINE = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else {}
PAIRS = {logical: pair for logical in LOGICALS if logical in BASELINE
         for pair in [_pair(logical, BASELINE[logical])] if pair is not None}
TREES = {logical: pair[0] for logical, pair in PAIRS.items()}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _shallow(command) -> str:
    """一条命令**自身参数**的快照：内嵌 ``Block`` 子块挖空，免得父命令因子块变化被当成「被改写」。

    PF 树有上千条命令，用序列化字符串比对，别用嵌套 list 的 O(n²) 相等。
    """
    def blank(value):
        if isinstance(value, list):
            if len(value) == 2 and value[0] == "Block" and isinstance(value[1], list):
                return ["Block", "<block>"]
            return [blank(item) for item in value]
        return value
    return json.dumps(blank(command), ensure_ascii=False, sort_keys=True)


def _flat_commands(tree) -> list:
    return [_shallow(c) for c in K.cmds(tree)]


class RealTrees(unittest.TestCase):
    """正向：五棵真树各删 1 条，删后 0 条，其余命令逐节点不变，重复调用幂等。"""

    @classmethod
    def setUpClass(cls):
        if len(TREES) != len(LOGICALS):
            raise unittest.SkipTest("philia DSL sources absent (no candidate package, no live store)")

    def test_each_tree_has_exactly_one_flying_before_and_none_after(self):
        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                before = R.flying_statements(tree)
                self.assertEqual(len(before), R.EXPECTED_FLYING, logical)
                self.assertEqual([[k[0] for k in st[1][2]] for st in before], [["ACFlying"]])
                after = R.strip_flying(tree)
                self.assertEqual(R.flying_statements(after), [])

    def test_only_the_flying_statement_and_its_emptied_search_disappear(self):
        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                after = R.strip_flying(tree)
                before_cmds, after_cmds = _flat_commands(tree), _flat_commands(after)
                removed = Counter(before_cmds) - Counter(after_cmds)
                self.assertEqual(Counter(after_cmds) - Counter(before_cmds), Counter(),
                                 "没有任何命令可以被新增或改写")
                kinds = sorted(json.loads(c)[0] for c in removed.elements())
                self.assertIn(kinds, (["CreateCondition"], ["CreateCondition", "FindAllSubjects"]))
                # 剩下的命令序列与原树逐节点一致，顺序也一致
                dropped = dict(removed)
                survivors = []
                for cmd in before_cmds:
                    if dropped.get(cmd):
                        dropped[cmd] -= 1
                    else:
                        survivors.append(cmd)
                self.assertEqual(after_cmds, survivors)
                self.assertEqual(after[:11], tree[:11])          # 头部（含 buffTargetAs）不动
                self.assertNotIn("ACFlying", json.dumps(after, ensure_ascii=False))

    def test_skill_prunes_the_emptied_support_search_and_pf_keeps_its_two_buffs(self):
        for program in R.SKILL_PROGRAMS:
            after = R.strip_flying(TREES[wf_dsl.dsl_logical(program)])
            self.assertEqual([c for c in K.cmds(after, "FindAllSubjects") if c[2] == 33], [])
        for program in R.PF_PROGRAMS:
            tree = TREES[wf_dsl.dsl_logical(program)]
            after = R.strip_flying(tree)
            block = K.find_one(after[11][1], K.is_find_all(33), "pf supporter block")
            self.assertEqual([c[2][0][0] for c in K.cmds(block, "CreateCondition")],
                             ["ACAttackPoint", "ACPiercing"])
            self.assertEqual(len(after[11][1]), len(tree[11][1]))   # PF 根语句数不变

    def test_idempotent_and_encodable_and_passes_native_gates(self):
        for logical, tree in TREES.items():
            with self.subTest(logical=logical):
                after = R.strip_flying(tree)
                self.assertEqual(R.strip_flying(after), after)
                self.assertEqual(R.strip_flying(after, expected=None), after)
                self.assertEqual(K.dsl_gate_failures(K.dsl_gates(after)), [])
                encode_tree(after)

    def test_source_trees_are_untouched(self):
        snapshot = copy.deepcopy(TREES)
        for tree in TREES.values():
            R.strip_flying(tree)
        self.assertEqual(TREES, snapshot)

    def test_bytes_match_the_recorded_live_baseline_and_candidate(self):
        """复原出来的「改动前」逐字节等于 1.4.926 的 live 存储，删完逐字节等于候选包。"""
        for logical, (before, after) in PAIRS.items():
            entry = BASELINE[logical]
            with self.subTest(logical=logical):
                self.assertEqual(_sha(encode_tree(before)), entry["before_sha256"])
                self.assertEqual(_sha(encode_tree(R.strip_flying(before))), entry["after_sha256"])
                self.assertEqual(R.strip_flying(before), after)


class SyntheticNegatives(unittest.TestCase):
    """负向：合成树制造基线漂移，必须抛 NoFlyingError。"""

    def _cc(self, bind, kinds):
        return ["Command", ["CreateCondition", bind, kinds, [{"min": 1, "max": 1}], ["None"],
                            True, False, "", None, False, 3, [{"min": 1, "max": 1}], False]]

    def _tree(self, statements):
        return ["ActionDsl", 2, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", statements]]

    def _search(self, bind, body):
        return ["Command", ["FindAllSubjects", bind, 33, [], [], [], [], [], ["DoNothing"],
                            ["Block", body]]]

    def test_unexpected_count_is_rejected(self):
        tree = self._tree([self._search(110, [self._cc(110, [["ACFlying", [{"min": 1, "max": 1}]]])]),
                           self._search(111, [self._cc(111, [["ACFlying", [{"min": 1, "max": 1}]]])])])
        with self.assertRaises(R.NoFlyingError):
            R.strip_flying(tree)
        self.assertEqual(R.flying_statements(R.strip_flying(tree, expected=2)), [])

    def test_bundled_condition_is_rejected_instead_of_deleting_siblings(self):
        tree = self._tree([self._search(110, [self._cc(110, [["ACPiercing", [{"min": 60, "max": 60}]],
                                                             ["ACFlying", [{"min": 60, "max": 60}]]])])])
        with self.assertRaises(R.NoFlyingError):
            R.strip_flying(tree)

    def test_still_referenced_binding_blocks_the_prune(self):
        body = [self._cc(110, [["ACFlying", [{"min": 1, "max": 1}]]])]
        tree = self._tree([self._search(110, body),
                           ["Command", ["ShowEffect", "x", ["SpecifyEffectDirectly", "a/b"], 110,
                                        0, 0, ["AB"], 0, 0, 0.0, 1.0, 1.0, False, False, 0]]])
        with self.assertRaises(R.NoFlyingError):
            R.strip_flying(tree)

    def test_tree_without_flying_is_returned_unchanged(self):
        tree = self._tree([self._search(110, [self._cc(110, [["ACPiercing", [{"min": 1, "max": 1}]]])])])
        self.assertEqual(R.strip_flying(tree), tree)
        self.assertIsNot(R.strip_flying(tree), tree)


class Texts(unittest.TestCase):
    def test_skill_description_drops_the_whole_clause_and_is_idempotent(self):
        after = R.skill_description(R.SKILL_DESC_BEFORE)
        self.assertEqual(after, R.SKILL_DESC_AFTER)
        self.assertEqual(R.skill_description(after), after)
        self.assertNotIn("浮游", after)
        self.assertIn("恢复队伍角色与协力球的生命值／提升队伍强化弹射伤害", after)
        self.assertEqual(len(R.SKILL_DESC_BEFORE) - len(after), len(R.SKILL_FLY_CLAUSE))

    def test_pf_override_keeps_piercing_and_is_idempotent(self):
        after = R.pf_override_text(R.PF_TEXT_BEFORE)
        self.assertEqual(after, R.PF_TEXT_AFTER)
        self.assertEqual(R.pf_override_text(after), after)
        self.assertTrue(after.endswith("提升参战角色攻击力并赋予贯穿效果"))

    def test_unknown_text_is_rejected(self):
        for fn in (R.skill_description, R.pf_override_text):
            with self.assertRaises(R.NoFlyingError):
                fn("赋予参战者浮游效果／别的说明")

    def test_shipped_texts_pass_the_separator_and_panel_gates(self):
        for where, text in (("skill", R.SKILL_DESC_AFTER), ("pf", R.PF_TEXT_AFTER)):
            self.assertEqual(R.text_problems(where, text), [], where)

    def test_gate_catches_leftovers_and_dangling_separators(self):
        self.assertTrue(R.text_problems("x", "赋予浮游效果"))
        self.assertTrue(R.text_problems("x", "甲／／乙"))
        self.assertTrue(R.text_problems("x", "甲／乙／"))


@unittest.skipUnless((PACKAGE / "manifest.json").is_file(), "candidate package absent")
class Ability4(unittest.TestCase):
    """作者 2026-09-21：能力 4 的条件由「浮游效果中」换成「持有贯穿效果期间」（c97 31 → 30）。"""

    @staticmethod
    def _row(during="31"):
        row = [""] * 126
        row[0], row[1], row[2] = "wind_oracle_yukata_4", "true", "attack_white"
        row[R.DURING_COL] = during
        for col, value in R.ABILITY4_SHAPE.items():
            row[col] = value
        return row

    def test_flying_gate_becomes_piercing_and_nothing_else_moves(self):
        before = [self._row()]
        after = R.ability4_rows(before)
        self.assertEqual(after[0][R.DURING_COL], R.DURING_PIERCING)
        self.assertEqual([c for c in range(126) if before[0][c] != after[0][c]], [R.DURING_COL])
        self.assertEqual(before[0][R.DURING_COL], R.DURING_FLYING)       # 入参不被原地改

    def test_idempotent(self):
        once = R.ability4_rows([self._row()])
        self.assertEqual(R.ability4_rows(once), once)

    def test_unknown_gate_or_shape_is_rejected(self):
        with self.assertRaises(R.NoFlyingError):
            R.ability4_rows([self._row(during="134")])
        drifted = self._row()
        drifted[113] = "99999"
        with self.assertRaises(R.NoFlyingError):
            R.ability4_rows([drifted])
        with self.assertRaises(R.NoFlyingError):
            R.ability4_rows([])
        with self.assertRaises(R.NoFlyingError):
            R.ability4_rows([self._row(), self._row()])                  # 第二条还挂着浮游门

    def test_live_twin_row_has_the_same_shape(self):
        """同形先例：澄波响 live 行 1699886#0（持有贯穿效果期间，暗属性角色攻击力＋50%）。"""
        table = core.table_path(_store(), K.ABILITY)
        if not table.is_file():
            self.skipTest("live store not available")
        rows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(table.read_bytes()).get("1699886", ""))
        if not rows:
            self.skipTest("hibiki row not on this machine")
        twin = rows[0]
        self.assertEqual(twin[R.DURING_COL], R.DURING_PIERCING)
        for col, value in R.ABILITY4_SHAPE.items():
            if col != 111:                                               # 属性标记不同（Black / White）
                self.assertEqual(twin[col], value, col)
        self.assertEqual(twin[98], "")                                   # puller 列同样留空


class CandidatePackage(unittest.TestCase):
    """--write-candidate 之后：候选包里零 ACFlying、零「浮游」，三处文案与常量逐字一致。"""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((PACKAGE / "manifest.json").read_bytes())
        if R.SNAPSHOT_KEY not in cls.manifest.get("snapshot", {}):
            raise unittest.SkipTest("no-flying revision has not been written to the candidate yet")

    def test_candidate_ability4_reads_the_piercing_gate(self):
        raw = (PACKAGE / "roots/common" / K.ABILITY).read_bytes()
        rows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(raw)[R.CID + R.ABILITY4_SLOT])
        self.assertEqual(rows[0][R.DURING_COL], R.DURING_PIERCING)
        self.assertNotIn(R.DURING_FLYING, [row[R.DURING_COL] for row in rows])

    def test_candidate_dsl_has_no_flying(self):
        for logical in LOGICALS:
            raw = (PACKAGE / "roots/common" / logical).read_bytes()
            tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            self.assertEqual(R.flying_statements(tree), [], logical)

    def test_candidate_texts_match_the_pinned_strings(self):
        action = core.load_nested_table_bytes(
            (PACKAGE / "roots/common" / K.ACTION).read_bytes(), K.ACTION).rows[R.CODE]
        for level, text in action.text_rows().items():
            self.assertEqual(core.read_csv_lines(text)[0][1], R.SKILL_DESC_AFTER, level)
        rows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(
            (PACKAGE / "roots/common" / K.TEXT).read_bytes())[R.CID])
        self.assertEqual([rows[0][5], rows[0][7]], [R.SKILL_DESC_AFTER] * 2)
        cas = core.read_orderedmap_file_from_bytes(
            (PACKAGE / "roots/common" / K.CAS).read_bytes())[K.CAS_PF_OVERRIDE]
        self.assertEqual(core.read_csv_lines(cas)[0][0], R.PF_TEXT_AFTER)

    def test_no_visible_flying_left_in_any_claimed_string(self):
        hits = []
        for claim in self.manifest["tables"]:
            path = PACKAGE / "roots" / claim["root"] / claim["logical_path"]
            if not path.is_file() or claim["codec_id"] != "flat":
                continue
            table = core.read_orderedmap_file_from_bytes(path.read_bytes())
            for key in claim["outer_keys"]:
                if key in table and "浮游" in table[key]:
                    hits.append(f"{claim['logical_path']}:{key}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()

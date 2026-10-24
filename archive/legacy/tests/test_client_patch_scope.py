"""补丁枚举必须由当前表的解析器支持，不能只看共享枚举或 capability。"""
import ast
import importlib.util
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import test_client_legality as fixture
import wf_client_legality as legality
import wf_client_patch_scope as scope
import wf_describe

PARSERS = {
    "ability": "AbilityValues$/parseAt47",
    "leader_ability": "LeaderAbilityValues$/parseAt45",
    "ability_soul": "AbilitySoulValues$/parseAt44",
    "equipment_enhancement_ability": "EquipmentEnhancementAbilityValues$/parseAt47",
    "ex_ability": "ExAbilityValues$/parseAt46",
}

# Published 1.4.834 leader 169989 row 1: the device threw in parseAt45.
# Keep this row independent of the generator that the hotfix is changing.
REJECTED_NEPHTIM_LEADER = (
    "ruin_girl_campus,0,,0,2,,,600000,600000,Black,,0,,,,,,,0,,,,,,,"
    "20,7,Black,5000000,5000000,,,(None),0,,,,(None),,,,,,,0,724,,,,5000,5000"
    ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,"
).split(",")


def row_for(table, mode="0", content="724"):
    row = fixture._base_row(table, mode)
    column = wf_describe.layout(table)["blocks"]["instant_content"]
    row[column] = content
    row[column + 4:column + 6] = ["5000", "5000"]
    return row


class ClientPatchScopeTests(unittest.TestCase):
    def test_real_nephtim_leader_is_rejected_at_the_unpatched_parser(self):
        self.assertEqual(124, len(REJECTED_NEPHTIM_LEADER))
        self.assertEqual("724", REJECTED_NEPHTIM_LEADER[45])
        problems = legality.client_legality_problems("leader_ability", REJECTED_NEPHTIM_LEADER)
        self.assertTrue(any("leader_ability" in p and "c45" in p and "724" in p
                            and "LeaderAbilityValues$/parseAt45" in p for p in problems), problems)

    def test_active_ratio_content_is_supported_only_by_the_ability_parser(self):
        for table, parser in PARSERS.items():
            with self.subTest(table=table):
                problems = legality.client_legality_problems(table, row_for(table))
                if table == "ability":
                    self.assertEqual([], problems)
                else:
                    self.assertTrue(any(parser in p and "724" in p for p in problems), problems)

    def test_old_capability_is_not_reported_as_a_cure_for_unsupported_tables(self):
        for table in PARSERS:
            with self.subTest(table=table):
                expected = ["kyubi-fever-ratio-v1"] if table == "ability" else []
                self.assertEqual(expected, legality.required_client_capabilities(table, row_for(table)))

    def test_official_absolute_fever_content_remains_legal_on_all_five_tables(self):
        for table in PARSERS:
            with self.subTest(table=table):
                row = row_for(table, content="213")
                self.assertEqual([], legality.client_legality_problems(table, row))
                self.assertEqual([], legality.required_client_capabilities(table, row))

    def test_unparsed_instant_residue_in_during_and_opening_rows_stays_ignored(self):
        for table in PARSERS:
            for mode in ("1", "2"):
                with self.subTest(table=table, mode=mode):
                    row = row_for(table, mode)
                    self.assertEqual([], legality.client_legality_problems(table, row))
                    self.assertEqual([], legality.required_client_capabilities(table, row))

    def test_accepted_table_set_matches_the_actual_fever_patch_parser_targets(self):
        patch = Path(__file__).resolve().parents[2] / "client-patch/kyubi-fever-ratio/patch.py"
        syntax = ast.parse(patch.read_text(encoding="utf-8"))
        targets = next(ast.literal_eval(node.value) for node in syntax.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(name, ast.Name) and name.id == "TARGETS"
                               for name in node.targets))
        patched_parsers = {name for name in targets if "Values$/parseAt" in name}
        self.assertEqual({"AbilityValues$/parseAt47"}, patched_parsers)
        supported = {table for table, parser in PARSERS.items() if parser in patched_parsers}
        accepted = {table for table in PARSERS
                    if not legality.client_legality_problems(table, row_for(table))}
        self.assertEqual(supported, accepted)

    def test_gauge_rule_tables_match_the_equipment_rules_parser_targets(self):
        """423 的表范围、列号与 capability 以 equipment-rules 补丁自己的常量为准。"""
        path = Path(__file__).resolve().parents[2] / "client-patch/equipment-rules/rules.py"
        name = "_equipment_rules_for_scope_test"
        spec = importlib.util.spec_from_file_location(name, path)
        rules = importlib.util.module_from_spec(spec)
        sys.modules[name] = rules  # dataclass 注解解析需要模块已登记
        try:
            spec.loader.exec_module(rules)
        finally:
            sys.modules.pop(name, None)
        self.assertEqual(scope.EQUIPMENT_GAUGE_CAP, rules.CAPABILITY_GAUGE)
        self.assertEqual({"ability", *rules.GAUGE_PARSERS},
                         set(scope.PATCH_PARSER_TABLES["during_content", "423"]))
        self.assertEqual({"ability"}, set(scope.PATCH_PARSER_TABLES["during_content", "424"]))
        for table, (parser, _cls, target, code) in rules.GAUGE_PARSERS.items():
            with self.subTest(table=table):
                base = wf_describe.layout(table)["blocks"]["during_content"]
                self.assertEqual(f"{PARSERS[table].split('$')[0]}$/parseAt{base}", parser)
                self.assertEqual((base + 1, base + 9), (target, code))
                self.assertEqual(rules.CAPABILITY_GAUGE,
                                 scope.PATCH_PARSER_CAPABILITIES["during_content", "423"][table])


if __name__ == "__main__":
    unittest.main()

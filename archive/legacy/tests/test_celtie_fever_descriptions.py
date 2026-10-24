"""装配前拒绝缺少原生必读说明索引的角色包。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
from test_celtie_fever_abilities import official_sources
import test_celtie_fever_leader as leader_fixture
import wf_celtie_fever as build
import wf_celtie_fever_abilities as abilities
import wf_celtie_fever_leader as leader


class CeltieDescriptionDependenciesTest(unittest.TestCase):
    def setUp(self):
        self.abilities = abilities.ability_rows(official_sources())
        fixture = leader_fixture.CeltieFeverLeaderTest()
        fixture.setUp()
        self.leaders = fixture.rows
        self.strings = {**abilities.flat_string_rows(), **leader.flat_string_rows()}

    def test_complete_generated_kit_resolves_every_description(self):
        build.validate_descriptions(self.abilities, self.leaders, self.strings)

    def test_each_missing_custom_description_is_rejected(self):
        for key in self.strings:
            with self.subTest(key=key):
                broken = deepcopy(self.strings)
                del broken[key]
                with self.assertRaisesRegex(ValueError, "missing flat description: " + key):
                    build.validate_descriptions(self.abilities, self.leaders, broken)

    def test_empty_description_is_rejected(self):
        broken = deepcopy(self.strings)
        broken[leader.PF_STRING_ID] = [[""]]
        with self.assertRaisesRegex(ValueError, leader.PF_STRING_ID):
            build.validate_descriptions(self.abilities, self.leaders, broken)

    def test_native_revision_removes_retired_patch_and_preserves_fever_capability(self):
        self.assertEqual(["kyubi-fever-ratio-v1", "panel-description-override-v2"],
                         build.required_capabilities())
        self.assertEqual(["kyubi-fever-ratio-v1", "other-existing-feature",
                          "panel-description-override-v2"],
                         build.required_capabilities(["celtie-ability-actions-v1",
                             "kyubi-fever-ratio-v1", "other-existing-feature"]))
        self.assertIn("风属性伤害，伤害量以能力伤害加成判定", build.DESCRIPTION)
        self.assertIn("基础合计75倍", build.DESCRIPTION)
        self.assertIn("风属性共鸣且Fever模式中", build.DESCRIPTION)
        self.assertIn("随「星风心得」成长", build.DESCRIPTION)
        self.assertNotIn("能力3", build.DESCRIPTION)
        self.assertIn("每层额外增加10倍", build.DESCRIPTION)


if __name__ == "__main__":
    unittest.main()

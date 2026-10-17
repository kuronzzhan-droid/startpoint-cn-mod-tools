"""整组面板文字只能写本角色7个固定键，不能扩展到其他表或角色。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wf_mod_tool as core
from wf_character_revision import RevisionCandidate


class MemoryCandidate(RevisionCandidate):
    def __init__(self):
        self.cid = "149989"
        self.code = "wind_spgirl_campus"
        self.manifest = {"tables": []}
        self.outputs = {}

    def read(self, tier, logical):
        return core.build_orderedmap_raw_rows(core.OrderedMap(
            logical_path=logical, source_path=Path("<memory>"), keys=[], rows=[]))

    def emit(self, tier, logical, raw):
        self.outputs[tier, logical] = raw


class CharacterRevisionNamespaceTest(unittest.TestCase):
    def test_only_seven_owned_flat_description_keys_can_be_added(self):
        candidate = MemoryCandidate()
        logical = "master/string/custom_ability_string.orderedmap"
        keys = ["desc_override_wind_spgirl_campus"] + [
            f"desc_override_wind_spgirl_campus_{slot}" for slot in range(1, 7)]
        candidate.splice(logical, {key: [["简洁说明"]] for key in keys})
        data = core.read_orderedmap_raw_rows_from_bytes(
            candidate.outputs["common", logical], logical)
        self.assertEqual(set(data.keys), set(keys))

    def test_foreign_or_unknown_group_and_wrong_table_are_rejected(self):
        logical = "master/string/custom_ability_string.orderedmap"
        for key in ("desc_override_lady_summoner_campus_1",
                    "desc_override_wind_spgirl_campus_7",
                    "desc_override_wind_spgirl_campus_other"):
            with self.assertRaisesRegex(ValueError, "outside the assigned"):
                MemoryCandidate().splice(logical, {key: [["拒绝"]]})
        with self.assertRaisesRegex(ValueError, "outside the assigned"):
            MemoryCandidate().splice("master/ability/ability.orderedmap", {
                "desc_override_wind_spgirl_campus": [["拒绝"]]})


if __name__ == "__main__":
    unittest.main()

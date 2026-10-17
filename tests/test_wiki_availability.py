"""Availability must be explicit, CN-specific and mapped to the exact variant."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_availability import availability_from_role, enrich_availability
from wf_wiki_legacy import enrich_legacy_reference
from wf_wiki_public import public_catalog


def character(**updates):
    return {"id": "111009", "code": "tiger_treasure_hunter_smr20", "name": "米娅",
            "origin": "官方原版", "elementId": "0", **updates}


def role(**updates):
    return {"id": 99, "showOrder": 111009, "codeName": "tiger_treasure_hunter_smr20",
            "nameCn": "米娅", "property": 0, "wayCn": '["2022 夏日限定卡池"]', **updates}


class AvailabilityTests(unittest.TestCase):
    def test_explicit_cn_pool_and_permanent_are_distinguished(self):
        self.assertIs(availability_from_role(character(), role())["limited"], True)
        self.assertIs(availability_from_role(character(), role(wayCn='["常驻池"]'))["limited"], False)
        self.assertIn("不代表", availability_from_role(character(), role())["availabilityNote"])

    def test_costume_name_japanese_pool_and_time_limited_gift_are_not_evidence(self):
        for cn in (None, "", "[]", '["限时剧情活动赠送"]', '["非限定卡池"]', '["夏日活动"]'):
            with self.subTest(cn=cn):
                self.assertEqual(availability_from_role(character(), role(wayCn=cn, way='["限定卡池"]')), {})

    def test_conflicts_and_malformed_records_stay_unmarked(self):
        for cn in ('["限定卡池", "常驻池"]', '{"限定卡池":true}', '[null]', 'broken'):
            self.assertEqual(availability_from_role(character(), role(wayCn=cn)), {})

    def test_identity_uses_unique_code_game_order_and_element_not_database_id(self):
        self.assertIs(availability_from_role(character(), role(id=111999, nameCn="旧译名"))["limited"], True)
        for wrong in (role(showOrder=111010), role(property=1), role(codeName="tiger_treasure_hunter")):
            self.assertEqual(availability_from_role(character(), wrong), {})
        self.assertEqual(availability_from_role(character(id="99"), role()), {})

    def test_template_mods_never_inherit_official_limited(self):
        for origin in ("新增MOD", "灰服独立角色资料"):
            self.assertEqual(availability_from_role(character(origin=origin), role()), {})
        self.assertIs(availability_from_role(character(origin="改版官方"), role())["limited"], True)

    def test_duplicate_code_is_ambiguous_and_input_reference_is_immutable(self):
        catalog = {"meta": {}, "characters": [character()]}
        records = [role(), role(showOrder=111010)]
        before = deepcopy(records)
        counts = enrich_availability(catalog, records)
        self.assertEqual(counts, {"limited": 0, "permanent": 0, "unmarked": 1})
        self.assertNotIn("limited", catalog["characters"][0])
        self.assertEqual(records, before)

    def test_legacy_integration_public_flag_has_no_source_ids(self):
        catalog = {"meta": {}, "characters": [character()]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "localApi.json"
            path.write_text(json.dumps({"roleData": [role()]}), encoding="utf-8")
            enrich_legacy_reference(catalog, path)
        self.assertEqual(catalog["meta"]["availability"]["limited"], 1)
        public = public_catalog(catalog)
        self.assertIs(public["characters"][0]["limited"], True)
        encoded = json.dumps(public)
        self.assertNotIn("111009", encoded)
        self.assertNotIn("tiger_treasure_hunter", encoded)
        self.assertNotIn("wayCn", encoded)
        self.assertNotIn("showOrder", encoded)


if __name__ == "__main__":
    unittest.main()

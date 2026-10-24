import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_community_catalog import build_catalog


class CommunityCatalogTests(unittest.TestCase):
    def snapshot(self):
        return {"meta": {"version": "1.4.1111", "private": "ignored"},
                "characters": [{"id": "c0123456789ab", "element": "火", "name": "玛丽安", "theme": "圣诞",
                                "rawId": "private", "secret": "ignored"}],
                "equipment": [{"id": "w0123456789ab", "soul": {"available": True}, "raw": "ignored"}]}

    def test_only_public_validation_fields_survive(self):
        catalog = build_catalog(self.snapshot())
        self.assertEqual(catalog["characters"], {"c0123456789ab": {"element": "火", "name": "玛丽安", "variant": "圣诞"}})
        self.assertEqual(catalog["equipment"], {"w0123456789ab": {"soul": True}})
        self.assertNotIn("private", catalog)

    def test_old_snapshot_without_names_remains_compatible(self):
        data = self.snapshot()
        data["characters"][0].pop("name")
        data["characters"][0].pop("theme")
        self.assertEqual(build_catalog(data)["characters"]["c0123456789ab"],
                         {"element": "火", "name": "", "variant": ""})

    def test_raw_ids_duplicates_and_unknown_elements_fail_closed(self):
        for field, value in [("id", "119990"), ("element", "unknown"), ("name", []), ("theme", None)]:
            data = self.snapshot()
            data["characters"][0][field] = value
            with self.assertRaises(ValueError):
                build_catalog(data)
        data = self.snapshot()
        data["characters"].append(data["characters"][0])
        with self.assertRaises(ValueError):
            build_catalog(data)


if __name__ == "__main__":
    unittest.main()

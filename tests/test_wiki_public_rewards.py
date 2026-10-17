"""Reward packaging must not include private sources or unresolved Wiki links."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_public_rewards import INDEX, reward_plan


class RewardPublicPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = {"equipment": [{"id": "w123456789abc"}], "characters": []}
        self.value = {"schemaVersion": 1,
                      "source": {"label": "灰服快照", "status": "gray-snapshot", "checkedAt": "2026-09-30T00:00:00Z"},
                      "dungeons": {"boss-1-99": {"quests": [], "shopIds": ["five-boss"], "notes": []}},
                      "shops": [{"id": "five-boss", "title": "五重兑换", "dungeonIds": ["boss-1-99"], "notes": [],
                                 "items": [{"rewards": [{"kind": "equipment", "name": "武器", "amountText": "1", "equipmentId": "w123456789abc"}],
                                            "costs": [], "stock": -1, "availableFrom": None, "availableUntil": None, "notes": []}]}]}

    def write(self, value=None):
        (self.root / INDEX).write_text("window.WF_WIKI_REWARDS=" + json.dumps(value or self.value) + ";", encoding="utf8")

    def plan(self):
        return reward_plan(self.root, self.data, {"boss-1-99"})

    def test_only_valid_public_script_is_planned_without_writes(self):
        self.write()
        private = self.root / "rewards-manifest.json"
        private.write_text("private snapshot provenance", encoding="utf8")
        before = (self.root / INDEX).read_bytes()
        files, watched, audit = self.plan()
        self.assertEqual([x["path"] for x in files], [INDEX])
        self.assertEqual(list(watched), [INDEX])
        self.assertEqual(audit["products"], 1)
        self.assertTrue(audit["privateSourcesExcluded"] and audit["linksVerified"])
        self.assertEqual((self.root / INDEX).read_bytes(), before)

    def test_unavailable_equipment_and_dungeon_links_fail_closed(self):
        self.write()
        self.data["equipment"] = []
        with self.assertRaisesRegex(ValueError, "absent"):
            self.plan()
        self.data["equipment"] = [{"id": "w123456789abc"}]
        with self.assertRaisesRegex(ValueError, "Unknown dungeon"):
            reward_plan(self.root, self.data, set())

    def test_private_fields_script_suffix_and_links_are_rejected(self):
        value = copy.deepcopy(self.value)
        value["privatePath"] = "C:/server/assets"
        self.write(value)
        with self.assertRaises(ValueError):
            self.plan()
        self.write()
        with (self.root / INDEX).open("a", encoding="utf8") as target:
            target.write("fetch('/secret');")
        with self.assertRaises(ValueError):
            self.plan()
        self.write()
        with patch.object(Path, "is_symlink", lambda p: p.name == INDEX):
            with self.assertRaises(ValueError):
                self.plan()


if __name__ == "__main__":
    unittest.main()

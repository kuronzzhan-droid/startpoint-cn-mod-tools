"""Actual gray quest snapshots replace stale lookup provenance without claiming playtests."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_dungeons import export_dungeons
from wf_wiki_dungeons_gray import gray_quest_lookup, verify_gray_quests_unchanged
from wf_wiki_dungeons_schema import BOSS_QUEST, NODE_TABLE, QUEST_CATEGORIES, quest_table
from test_wiki_dungeons import csv_row, store_file
import wf_quest_lib as qlib


def snapshot(directory):
    directory.mkdir()
    files = {quest_table(kind).rsplit("/", 1)[1].replace(".orderedmap", ".json") for kind in QUEST_CATEGORIES}
    files.add("boss_battle_quest_cnmod.json")
    for name in files:
        (directory / name).write_text("{}", encoding="utf-8")
    return directory


class ActualGrayQuestTests(unittest.TestCase):
    def test_categories_and_cn_override_are_resolved_before_indexing(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = snapshot(Path(tmp) / "gray")
            for name, label in (("boss_battle_quest.json", "旧首领"),
                                ("boss_battle_quest_cnmod.json", "灰服新首领"),
                                ("advent_event_quest.json", "降临关卡")):
                (directory / name).write_text(json.dumps({"1001": {"name": label}}), encoding="utf-8")
            lookup, hashes = gray_quest_lookup(directory)
            self.assertEqual(lookup, {"2_1001": "灰服新首领", "7_1001": "降临关卡", "8_1001": "降临关卡"})
            self.assertEqual(len(hashes), len(QUEST_CATEGORIES) + 1)

    def test_missing_or_duplicate_source_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = snapshot(Path(tmp) / "gray")
            path = directory / "boss_battle_quest.json"
            path.write_text('{"1":{},"1":{}}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "重复"):
                gray_quest_lookup(directory)
            path.unlink()
            with self.assertRaisesRegex(ValueError, "缺失"):
                gray_quest_lookup(directory)

    def test_snapshot_mutation_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = snapshot(Path(tmp) / "gray")
            _, hashes = gray_quest_lookup(directory)
            verify_gray_quests_unchanged(directory, hashes)
            (directory / "raid_event_quest.json").write_text('{"1":{}}', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "发生变化"):
                verify_gray_quests_unchanged(directory, hashes)

    def test_actual_files_override_old_lookup_and_keep_private_receipts_out_of_site_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gray = snapshot(root / "gray")
            (gray / "boss_battle_quest.json").write_text('{"1099001":{"name":""}}', encoding="utf-8")
            store, site, repo = root / "game" / "upload", root / "site", root / "repo"
            store.mkdir(parents=True); repo.mkdir()
            store_file(store, NODE_TABLE, qlib.build_node({"1": {"99": csv_row(["模式", "五重决战"])}}))
            store_file(store, BOSS_QUEST, qlib.build_node({"1": {"99": {"1": "1099001,1,决战"}}}))
            old = root / "old-lookup.json"
            old.write_text("{}", encoding="utf-8")
            receipt = export_dungeons(repo, site, store=store, gray_lookup=old, gray_quest_assets=gray)
            raw = (site / "dungeons-data.js").read_text(encoding="utf-8")
            payload = json.loads(raw.split("=", 1)[1].strip().rstrip(";"))
            source = payload["items"][0]["source"]
            self.assertEqual(payload["items"][0]["id"], "boss-1-99")
            self.assertEqual(source["questLookup"]["matched"], 1)
            self.assertIn("灰服当前关卡配置已对应 1/1", source["label"])
            self.assertIn("游戏内开放状态未实测", source["label"])
            self.assertNotIn("灰服后台", source["label"])
            self.assertNotIn("boss_battle_quest.json", raw)
            self.assertEqual(receipt["questLookup"]["origin"], "gray-quest-assets")
            self.assertIn("boss_battle_quest.json", receipt["questLookup"]["files"])


if __name__ == "__main__":
    unittest.main()

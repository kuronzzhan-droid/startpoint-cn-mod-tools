"""Dungeon provenance, native schema and standalone export contracts."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_quest_lib as qlib
import wf_wiki_dungeons as exporter
import wf_wiki_dungeons_schema as schema
from wf_wiki_dungeons_sources import DungeonSources


def csv_row(values):
    import csv
    stream = io.StringIO()
    csv.writer(stream, lineterminator="").writerow(values)
    return stream.getvalue()


def store_file(store, logical, raw):
    path = store / qlib.hashed_rel(logical)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def picture(size=(1000, 184)):
    stream = io.BytesIO()
    Image.new("RGBA", size, (42, 125, 180, 255)).save(stream, "PNG")
    return stream.getvalue()


class DungeonTests(unittest.TestCase):
    def test_quest_rank_and_element_use_native_columns_and_keep_blank_story_fields(self):
        row = [""] * 130
        row[2], row[72], row[106], row[107] = "领主 ::quest_rank::", "0", "80", "8"
        ranks = {"4": "super,超级,80,89", "8": "final,决战级,(None),"}
        self.assertEqual(schema.quest_details(csv_row(row), "boss", ranks), [
            {"name": "领主", "difficulty": "决战级", "element": "风"}])
        row[107] = ""
        self.assertEqual(schema.quest_details(csv_row(row), "boss", ranks)[0]["difficulty"], "超级")
        story = ["", "", "序章"]
        self.assertEqual(schema.quest_details(csv_row(story), "advent", ranks), [
            {"name": "序章", "difficulty": "", "element": ""}])

    def test_hidden_elements_and_repeated_difficulties(self):
        row = [""] * 130
        row[2], row[78], row[79], row[113] = "试炼", "4", "true", "4"
        node = {"1": csv_row(row), "2": csv_row(row)}
        result = schema.quest_details(node, "advent", {"4": "super,超级,80,89"})
        self.assertEqual(result, [{"name": "试炼", "difficulty": "超级", "element": ""}])

    def test_static_image_paths_reject_animations_traversal_and_external_urls(self):
        value = "quest/event/banner/a,(None),quest/event/banner/a,quest/event/animation_background/a,https://host/a,quest/../bad"
        self.assertEqual(schema.image_paths(value), ["quest/event/banner/a.png"])

    def test_export_preserves_game_store_and_other_media_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, site, repo = root / "game" / "upload", root / "site", root / "repo"
            store.mkdir(parents=True); site.mkdir(); repo.mkdir()
            (site / "media-manifest.json").write_text('{"keep":true}', encoding="utf-8")
            row = ["领主战", "维·索拉斯", "1", "", "", "", "", "", "", "", "",
                   "quest/thumbnail/owl", "quest/boss_battle/background/owl"]
            store_file(store, schema.NODE_TABLE, qlib.build_node({"1": {"1": csv_row(row)}}))
            store_file(store, schema.BOSS_QUEST, qlib.build_node({"1": {"1": {"1": "1,1,试炼 ::quest_rank::"}}}))
            store_file(store, "quest/thumbnail/owl.png", picture((250, 160)))
            store_file(store, "quest/boss_battle/background/owl.png", picture())
            before = {p: p.read_bytes() for p in store.rglob("*") if p.is_file()}
            with patch.object(DungeonSources, "_remote", side_effect=AssertionError("local export made network call")):
                receipt = exporter.export_dungeons(repo, site, store=store, community_catalog=root / "ids.mjs")
            raw = (site / "dungeons-data.js").read_text(encoding="utf-8")
            payload = json.loads(raw.removeprefix("window.WF_WIKI_DUNGEONS=").removesuffix(";\n"))
            self.assertEqual(receipt["items"], 1)
            self.assertEqual(payload["source"]["status"], "local-snapshot")
            self.assertIn("未核验", payload["source"]["label"])
            self.assertEqual(payload["items"][0]["id"], "boss-1-1")
            community = (root / "ids.mjs").read_text(encoding="utf-8")
            self.assertIn('export default {"items":[{"id":"boss-1-1","title":"维·索拉斯"}]}', community)
            self.assertNotIn("quest/thumbnail", community)
            self.assertEqual((site / "media-manifest.json").read_text(), '{"keep":true}')
            self.assertEqual(before, {p: p.read_bytes() for p in store.rglob("*") if p.is_file()})
            banner_entry = receipt["media"]["quest/boss_battle/background/owl.png"]
            self.assertEqual((banner_entry["width"], banner_entry["height"]), (1000, 184))

    def test_modes_are_entries_and_five_boss_retains_legacy_guide(self):
        class Source:
            def prefetch(self, paths):
                pass
            def table(self, path):
                if path == schema.event_table("rush"):
                    return {"700099": "mod_rogue,深渊连战"}
                if path == schema.NODE_TABLE:
                    return {"1": {"99": "五重决战,五王连战"}}
                return {}
        rows = exporter.build_items(Source())
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["category"] for row in rows], ["模式", "模式"])
        self.assertEqual(rows[-1]["legacyGuide"], "five-boss")
        self.assertNotIn("enabled", rows[0])

    def test_placeholder_title_uses_matching_quest_name(self):
        class Source:
            def prefetch(self, paths):
                pass
            def table(self, path):
                if path == schema.event_table("raid"):
                    return {"1": "raid_event_01,活动名"}
                if path == schema.quest_table("raid"):
                    return {"1": {"1": "1001,,,1,护像之宴 ::quest_rank::"}}
                return {}
        self.assertEqual(exporter.build_items(Source())[0]["title"], "护像之宴")

    def test_site_cannot_be_game_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                exporter.export_dungeons(root / "repo", root / "store", store=root / "store")

    def test_gray_lookup_checks_exact_category_and_retains_master_name(self):
        from collections import Counter
        audit = Counter(total=0, matched=0, sameName=0, differentName=0)
        result = schema.quest_details("1001,1,元表名称", "boss", {},
                                      {"7_1001": "错误分类", "2_1001": "后台别称"}, audit)
        self.assertEqual(result[0]["name"], "元表名称")
        self.assertEqual(dict(audit), {"total": 1, "matched": 1, "sameName": 0, "differentName": 1})

    def test_community_identifier_length_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            exporter.validate_catalog({"items": [{"id": "a" * 81}]}, Path(tmp))


if __name__ == "__main__":
    unittest.main()

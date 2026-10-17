"""Partition/reconstruction contracts without accessing live sources or media."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_wiki_data as data
from wf_wiki_public import catalog_order, public_catalog, public_id


def catalog():
    return public_catalog({"meta": {"version": "1.4.1111"}, "characters": [{
        "id": "111135", "name": "黛妲莉亚", "title": "魔像部部长", "element": "火", "rarity": 5,
        "type": "辅助", "origin": "官方原版", "category": "官方原版", "aliases": ["魔像"],
        "icon": "media/avatar.webp", "avatars": {"before": "media/avatar.webp", "after": "media/awakened.webp"},
        "portraits": [{"url": "media/portrait.webp"}],
        "leader": {"name": "队长技", "description": "全队攻击+100%", "rows": [{"description": "原始分项"}]},
        "abilities": [{"name": "能力1", "slot": 1, "description": "主位攻击+50%", "rows": [{
            "description": "只在此条有效", "restrictions": {"operator": "AND", "items": [{"kind": "main", "label": "仅主位"}]}}]}],
        "skills": [{"name": "魔像启动", "numericDetails": {"rows": [{"values": [{"label": "倍率", "value": "12倍"}]}]}}],
        "voices": [{"zh": "这是只有台词才包含的文字", "ja": "音声です", "audio": "media/voice.mp3"}],
        "officialComparison": {"summary": "官方原版无修改"}, "nameplates": [{"name": "信赖铭牌"}],
    }], "equipment": [{"id": "5920001", "name": "悖论", "enhancement": {"forms": [{"level": 120}, {"level": 200}]}}],
        "equipmentMeta": {"partyRules": {"说明": "保留规则"}}, "bossGuide": {"notes": ["保留五重资料"]}})


class WikiDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.catalog = catalog()
        (self.output / "data.json").write_bytes(data.compact(self.catalog))

    def test_full_reconstruction_preserves_detail_voice_numeric_and_equipment(self):
        before = deepcopy(self.catalog)
        report = data.write_split_public(self.output, self.catalog)
        self.assertEqual(data.read_split_catalog(self.output), self.catalog)
        self.assertEqual(report["chunks"], 4)
        self.assertEqual(self.catalog, before)
        bootstrap, _ = data.split_catalog(self.catalog)
        index = bootstrap["characters"][0]
        self.assertFalse(set(index) & {"leader", "abilities", "voices", "skills", "nameplates", "officialComparison"})
        self.assertEqual(index["portraits"], [{"url": "media/portrait.webp"}])
        self.assertEqual(index["catalogOrder"], 1)
        self.assertEqual(index["avatars"], self.catalog["characters"][0]["avatars"])

    def test_portrait_index_contains_only_public_image_labels_and_urls(self):
        character = deepcopy(self.catalog["characters"][0])
        character["portraits"] = [{"label": "觉醒后", "url": "media/full.webp", "extra": "不进首页"}]
        index = data.index_character(character)
        self.assertEqual(index["portraits"], [{"label": "觉醒后", "url": "media/full.webp"}])
        self.assertEqual(character["portraits"][0]["extra"], "不进首页")

    def test_search_includes_all_player_text_and_numbers_but_no_media_paths(self):
        content = data.search_text(self.catalog["characters"][0])
        for term in ("只有台词", "音声です", "12倍", "魔像启动", "全队攻击+100%", "主位攻击+50%", "仅主位", "无修改", "信赖铭牌", "5"):
            self.assertIn(term, content)
        self.assertNotIn("media/", content)
        self.assertEqual(data.search_text(["重复", "重复", True, 1.5]), "重复\ntrue\n1.5")

    def test_legacy_index_remains_readable_but_cannot_smuggle_changed_effects(self):
        data.write_split_public(self.output, self.catalog)
        bootstrap, _ = data.split_catalog(self.catalog)
        bootstrap["characters"] = [data.index_character(c, legacy_effects=True) for c in self.catalog["characters"]]
        self.assertEqual(data.read_split_catalog(self.output, bootstrap), self.catalog)
        bootstrap["characters"][0]["leader"]["description"] = "错误旧正文"
        with self.assertRaisesRegex(ValueError, "摘要与详情"):
            data.read_split_catalog(self.output, bootstrap)

    def test_chunk_parser_does_not_execute_or_accept_appended_code(self):
        bootstrap, files = data.split_catalog(self.catalog)
        key, entry = next(iter(bootstrap["dataManifest"]["chunks"].items()))
        raw = files[entry["url"]]
        self.assertEqual(data.chunk_payload(raw, key), self.catalog["characters"][0])
        with self.assertRaises(ValueError):
            data.chunk_payload(raw + b"alert(1);", key)
        with self.assertRaises(ValueError):
            data.chunk_payload(raw, "character:c000000000000")

    def test_missing_corrupt_and_misdirected_chunks_fail_closed(self):
        data.write_split_public(self.output, self.catalog)
        bootstrap, _ = data.split_catalog(self.catalog)
        key, entry = next(iter(bootstrap["dataManifest"]["chunks"].items()))
        path = self.output / entry["url"]
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "哈希或大小"):
            data.read_split_catalog(self.output)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            data.read_split_catalog(self.output)
        bootstrap["dataManifest"]["chunks"][key]["url"] = "../outside.js"
        with self.assertRaisesRegex(ValueError, "路径越界"):
            data.read_split_catalog(self.output, bootstrap)

    def test_index_and_search_must_correspond_to_full_data(self):
        data.write_split_public(self.output, self.catalog)
        bootstrap, _ = data.split_catalog(self.catalog)
        bootstrap["characters"][0]["name"] = "错误摘要"
        with self.assertRaisesRegex(ValueError, "摘要与详情"):
            data.read_split_catalog(self.output, bootstrap)
        bootstrap, _ = data.split_catalog(self.catalog)
        bootstrap["dataManifest"]["chunks"].pop("search")
        with self.assertRaisesRegex(ValueError, "缺项"):
            data.read_split_catalog(self.output, bootstrap)

    def test_public_boundary_hidden_ids_paths_and_unknown_top_level(self):
        for mutate in (
            lambda c: c["characters"][0].update(id="111135"),
            lambda c: c["characters"][0].update(code="golemclub_captain"),
            lambda c: c["characters"][0].update(id=public_id("c", "129990")),
            lambda c: c["characters"][0].update(profile="来源 C:/private/data"),
            lambda c: c.update(unknownTopLevel={"important": "不得丢失"}),
        ):
            changed = deepcopy(self.catalog)
            mutate(changed)
            with self.assertRaises(ValueError):
                data.split_catalog(changed)

    def test_resplit_requires_complete_receipt_and_never_rewrites_media(self):
        marker = self.output / ".wf-wiki-export.json"
        marker.write_text('{"generator":"wf_wiki","complete":false}', encoding="utf-8")
        with self.assertRaises(ValueError):
            data.resplit_existing(self.output)
        marker.write_text(json.dumps({"generator": "wf_wiki", "complete": True,
            "version": "1.4.1111", "characters": 1}), encoding="utf-8")
        media = self.output / "media"
        media.mkdir()
        asset = media / "unrelated-existing.bin"
        asset.write_bytes(b"unchanged media bytes")
        before = asset.read_bytes(), asset.stat().st_mtime_ns
        first = data.resplit_existing(self.output)
        paths = set((self.output / "data").iterdir())
        second = data.resplit_existing(self.output)
        self.assertEqual(first, second)
        self.assertEqual(set((self.output / "data").iterdir()), paths)
        self.assertEqual((asset.read_bytes(), asset.stat().st_mtime_ns), before)

    def test_native_order_is_numeric_and_public_only_receives_continuous_rank(self):
        identifiers = ["111135", "90", "1000"]
        order = catalog_order(identifiers)
        self.assertEqual([order[public_id("c", value)] for value in identifiers], [3, 1, 2])
        result = public_catalog({"meta": {}, "characters": [{"id": value} for value in identifiers]})
        self.assertEqual([c["catalogOrder"] for c in result["characters"]], [3, 1, 2])
        encoded = json.dumps(result)
        self.assertNotIn('"111135"', encoded)
        with self.assertRaises(ValueError):
            catalog_order(["90", "90"])

    def test_output_links_are_rejected_before_replacing_index(self):
        elsewhere = self.output / "outside"
        elsewhere.mkdir()
        try:
            (self.output / "data").symlink_to(elsewhere, target_is_directory=True)
        except OSError:
            self.skipTest("host does not permit symlinks")
        with self.assertRaises(ValueError):
            data.write_split_public(self.output, self.catalog)
        self.assertEqual(list(elsewhere.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

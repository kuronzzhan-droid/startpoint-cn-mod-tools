"""The public dungeon package excludes source paths, executable script and orphan art."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_pixel_output import digest
from wf_wiki_public_dungeons import INDEX, MANIFEST, SERIES_VARIANTS, dungeon_plan
from wf_wiki_dungeon_groups import GROUPS


class DungeonPublicPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "media").mkdir()
        self.url = self.image()
        source = {"label": "灰服资源快照；开放状态未核验", "status": "gray-snapshot", "checkedAt": "2026-09-30T00:00:00+00:00"}
        item = {"id": "boss-1-99", "title": "五重决战", "category": "模式", "summary": "五重决战 · 1 项关卡资料",
                "quests": [{"name": "决战", "difficulty": "超级", "element": "火"}], "banner": self.url,
                "entryImage": self.url, "previewImages": [self.url], "source": copy.deepcopy(source), "legacyGuide": "five-boss"}
        item["source"]["questLookup"] = {"total": 2, "matched": 1, "sameName": 1, "differentName": 0}
        self.value = {"schemaVersion": 1, "source": source, "items": [item]}
        self.write()

    def image(self, size=(20, 10), format="WEBP", animated=False):
        stream = io.BytesIO()
        image = Image.new("RGB", size, (100, 50, 30))
        kwargs = {"save_all": True, "append_images": [Image.new("RGB", size, "blue")], "duration": 100} if animated else {}
        image.save(stream, format, **kwargs)
        raw = stream.getvalue()
        url = f"media/{digest(raw)}.webp"
        (self.root / url).write_bytes(raw)
        return url

    def write(self, value=None):
        raw = json.dumps(value or self.value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        (self.root / INDEX).write_text("window.WF_WIKI_DUNGEONS=" + raw + ";\n", encoding="utf-8")

    def test_exact_plan_deduplicates_references_without_reading_private_manifest_or_writing(self):
        (self.root / MANIFEST).write_text("this private file is not even valid JSON", encoding="utf-8")
        orphan = self.root / "media" / ("a" * 64 + ".webp")
        orphan.write_bytes(b"never publish")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        plan, watched, audit = dungeon_plan(self.root)
        self.assertEqual({row["path"] for row in plan}, {INDEX, self.url})
        self.assertEqual(set(watched), {INDEX, self.url})
        self.assertEqual((audit["items"], audit["images"], audit["quests"]), (1, 1, 1))
        self.assertEqual(audit["categories"], {"模式": 1})
        self.assertEqual(audit["questLookup"]["matched"], 1)
        self.assertTrue(audit["manifestExcluded"] and audit["mediaHashVerified"])
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_extra_code_wrong_assignment_duplicate_keys_non_json_and_unknown_version_are_rejected(self):
        good = (self.root / INDEX).read_text(encoding="utf-8")
        scripts = [good + "fetch('/private');", good.replace("WF_WIKI_DUNGEONS", "OTHER"),
                   good.replace('"schemaVersion":1', '"schemaVersion":2'),
                   good.replace('"schemaVersion":1', '"schemaVersion":true'),
                   good.replace('"schemaVersion":1', '"schemaVersion":NaN'),
                   good.replace('"schemaVersion":1', '"schemaVersion":1,"schemaVersion":1'),
                   "window.WF_WIKI_DUNGEONS=(()=>({}))();"]
        for script in scripts:
            with self.subTest(script=script[:100]):
                (self.root / INDEX).write_text(script, encoding="utf-8")
                with self.assertRaises(ValueError):
                    dungeon_plan(self.root)

    def test_private_and_unknown_fields_at_each_depth_are_rejected(self):
        paths = [(), ("source",), ("items", 0), ("items", 0, "source"), ("items", 0, "quests", 0),
                 ("items", 0, "source", "questLookup")]
        for path in paths:
            with self.subTest(path=path):
                value = copy.deepcopy(self.value); target = value
                for key in path:
                    target = target[key]
                target["logicalPath"] = "master/private-table.orderedmap"
                self.write(value)
                with self.assertRaisesRegex(ValueError, "非公开字段"):
                    dungeon_plan(self.root)

    def test_media_hash_missing_files_paths_format_animation_and_dimensions_are_checked(self):
        media = self.root / self.url
        raw = media.read_bytes(); media.write_bytes(raw + b"tampered")
        with self.assertRaisesRegex(ValueError, "哈希"):
            dungeon_plan(self.root)
        media.unlink()
        with self.assertRaisesRegex(ValueError, "缺失"):
            dungeon_plan(self.root)
        media.write_bytes(raw)
        for unsafe in ["media/../private.webp", "https://example.test/image.webp", MANIFEST, "media/pixels/" + "a" * 64 + ".webp", ""]:
            value = copy.deepcopy(self.value); value["items"][0]["banner"] = unsafe; self.write(value)
            with self.assertRaisesRegex(ValueError, "白名单"):
                dungeon_plan(self.root)
        for bad_image in [self.image(format="PNG"), self.image(size=(1201, 1)), self.image(size=(1, 1601)), self.image(animated=True)]:
            value = copy.deepcopy(self.value); value["items"][0]["banner"] = bad_image; self.write(value)
            with self.assertRaisesRegex(ValueError, "静态 WebP|尺寸超限"):
                dungeon_plan(self.root)

    def test_source_lookup_stats_time_status_and_types_must_be_valid(self):
        for stats in [{"total": 1, "matched": 2, "sameName": 2, "differentName": 0},
                      {"total": 2, "matched": 1, "sameName": 0, "differentName": 0},
                      {"total": 2, "matched": True, "sameName": 1, "differentName": 0},
                      {"total": -1, "matched": 0, "sameName": 0, "differentName": 0}]:
            value = copy.deepcopy(self.value); value["items"][0]["source"]["questLookup"] = stats; self.write(value)
            with self.assertRaisesRegex(ValueError, "统计"):
                dungeon_plan(self.root)
        for key, wrong in [("status", "live"), ("status", {}), ("checkedAt", "2026-09-30"), ("checkedAt", "not a date")]:
            value = copy.deepcopy(self.value); value["source"][key] = wrong; self.write(value)
            with self.assertRaises(ValueError):
                dungeon_plan(self.root)

    def test_unique_bounded_ids_categories_legacy_links_and_elements_fail_closed(self):
        for key, wrong in [("id", "../bad"), ("id", "A"), ("id", "a" * 81), ("category", "extra"), ("category", {}),
                           ("legacyGuide", "../../private"), ("previewImages", [self.url, self.url]), ("title", "")]:
            value = copy.deepcopy(self.value); value["items"][0][key] = wrong; self.write(value)
            with self.assertRaises(ValueError):
                dungeon_plan(self.root)
        value = copy.deepcopy(self.value); value["items"].append(copy.deepcopy(value["items"][0])); self.write(value)
        with self.assertRaisesRegex(ValueError, "重复"):
            dungeon_plan(self.root)
        value = copy.deepcopy(self.value); value["items"][0]["quests"][0]["element"] = []; self.write(value)
        with self.assertRaisesRegex(ValueError, "属性"):
            dungeon_plan(self.root)

    def test_local_fallback_without_images_or_lookup_is_valid_but_links_are_not_followed(self):
        value = copy.deepcopy(self.value); item = value["items"][0]
        value["source"]["status"] = item["source"]["status"] = "local-snapshot"
        item["banner"] = item["entryImage"] = None; item["previewImages"] = []
        del item["source"]["questLookup"]
        self.write(value)
        plan, _, audit = dungeon_plan(self.root)
        self.assertEqual([row["path"] for row in plan], [INDEX])
        self.assertEqual(audit["questLookupItems"], 0)
        with patch.object(Path, "is_symlink", lambda p: p.name == INDEX):
            with self.assertRaisesRegex(ValueError, "链接"):
                dungeon_plan(self.root)
        self.write()
        with patch("wf_wiki_pixel_output.is_junction", side_effect=lambda p: p.name == "media"):
            with self.assertRaisesRegex(ValueError, "链接"):
                dungeon_plan(self.root)

    def test_series_pairs_allow_only_frozen_variants_and_are_included_in_audit(self):
        value = copy.deepcopy(self.value); item = value["items"][0]
        del item["legacyGuide"]
        for identifier, variants in SERIES_VARIANTS.items():
            for variant in variants:
                with self.subTest(identifier=identifier, variant=variant):
                    item.update(seriesId=identifier, variantLabel=variant, seriesTitle=GROUPS[identifier][0])
                    self.write(value)
                    _, _, audit = dungeon_plan(self.root)
                    self.assertEqual(audit["series"], {identifier: 1})
                    self.assertEqual(audit["seriesVariants"], {identifier: {variant: 1}})

    def test_series_fields_are_optional_but_must_be_paired_and_fail_closed(self):
        _, _, audit = dungeon_plan(self.root)
        self.assertEqual(audit["series"], {})
        invalid = [
            {"seriesTitle": "任意分组"},
            {"seriesId": "series-side-stories", "variantLabel": "幻彩摩天楼"},
            {"seriesId": "series-haniwa", "variantLabel": "闪火土机巨土俑", "seriesTitle": "其他玩法"},
            {"seriesId": "series-machina"}, {"variantLabel": "火"},
            {"seriesId": None, "variantLabel": None},
            {"seriesId": {}, "variantLabel": "火"},
            {"seriesId": "series-machina", "variantLabel": []},
            {"seriesId": "series-new", "variantLabel": "火"},
            {"seriesId": "series-spirit-beasts", "variantLabel": "无属性"},
            {"seriesId": "series-gauntlets", "variantLabel": "EX深渊"},
            {"seriesId": "series-gauntlets", "variantLabel": "无尽"},
            {"seriesId": "series-gauntlets", "variantLabel": "深渊连战EX无尽"},
            {"seriesId": "series-machina", "variantLabel": "火", "category": "未知"},
            {"seriesId": "series-gauntlets", "variantLabel": "幻想连战", "category": "活动"},
        ]
        for fields in invalid:
            with self.subTest(fields=fields):
                value = copy.deepcopy(self.value); value["items"][0].update(fields)
                self.write(value)
                with self.assertRaises(ValueError):
                    dungeon_plan(self.root)


if __name__ == "__main__":
    unittest.main()

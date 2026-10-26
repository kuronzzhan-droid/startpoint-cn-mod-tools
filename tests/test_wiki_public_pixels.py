"""Publishing allows only a complete, verified visible-roster pixel asset closure."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_wiki_pixel_render import fixture
from wf_wiki_categories import HIDDEN_CHARACTER_IDS
from wf_wiki_pixel_output import digest
from wf_wiki_pixel_render import render_actions, webp
from wf_wiki_pixels import NOTE
from wf_wiki_public import public_id
from wf_wiki_public_pixels import INDEX, JSON_INDEX, pixel_plan


class PublicPixelPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        (self.source / "data").mkdir()
        (self.source / "media/pixels").mkdir(parents=True)
        self.cid = public_id("c", "101")
        self.catalog = {"meta": {"version": "1.4.54"}, "characters": [{"id": self.cid}]}
        actions = render_actions(fixture(), self.save)
        self.record = {"sourceRevision": "a" * 64, "poster": actions[0]["poster"],
                       "actions": actions, "unavailable": [], "note": NOTE}
        self.index = {"format": 1, "version": "1.4.54", "catalogVersion": "1.4.54",
                      "characters": {self.cid: self.record}}
        self.write()

    def save(self, raw):
        url = f"media/pixels/{digest(raw)}.webp"
        (self.source / url).write_bytes(raw)
        return url

    def write(self, index=None):
        index = index or self.index
        rows = index["characters"]
        index["revision"] = digest(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode())
        urls = {media["url"] for row in rows.values() for action in row["actions"] for media in (action, action["poster"])}
        index["summary"] = {"characters": len(rows), "actions": sum(len(r["actions"]) for r in rows.values()),
                            "files": len(urls), "bytes": sum((self.source / url).stat().st_size for url in urls if (self.source / url).is_file()),
                            "unavailableActions": [{"characterId": cid, **item} for cid, row in rows.items() for item in row["unavailable"]]}
        raw = json.dumps(index, ensure_ascii=False)
        (self.source / JSON_INDEX).write_text(raw, encoding="utf-8")
        (self.source / INDEX).write_text("window.WF_PIXEL_PREVIEWS=" + raw + ";\n", encoding="utf-8")

    def test_plan_only_contains_index_and_referenced_hash_media_without_writes(self):
        orphan = self.source / "media/pixels" / ("b" * 64 + ".webp")
        orphan.write_bytes(b"must not publish")
        old_chunk = self.source / "data/old-character.js"
        old_chunk.write_text("private old record", encoding="utf-8")
        before = {p: p.read_bytes() for p in self.source.rglob("*") if p.is_file()}
        plan, watched, audit = pixel_plan(self.source, self.catalog)
        paths = {entry["path"] for entry in plan}
        self.assertEqual(len(plan), audit["files"] + 1)
        self.assertIn(INDEX, paths)
        self.assertNotIn(JSON_INDEX, paths)
        self.assertNotIn(old_chunk.relative_to(self.source).as_posix(), paths)
        self.assertNotIn(orphan.relative_to(self.source).as_posix(), paths)
        self.assertEqual(set(watched), {INDEX, JSON_INDEX})
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_hidden_extra_and_missing_roster_entries_are_rejected(self):
        hidden = public_id("c", next(iter(HIDDEN_CHARACTER_IDS)))
        for cid, catalog_ids in ((hidden, [self.cid]), (hidden, [hidden]), (self.cid, [public_id("c", "102")])):
            with self.subTest(cid=cid, catalog_ids=catalog_ids):
                altered = copy.deepcopy(self.index)
                altered["characters"] = {cid: copy.deepcopy(self.record)}
                self.write(altered)
                catalog = {"meta": self.catalog["meta"], "characters": [{"id": x} for x in catalog_ids]}
                with self.assertRaisesRegex(ValueError, "白名单|隐藏角色"):
                    pixel_plan(self.source, catalog)

    def test_json_script_mismatch_and_appended_script_are_rejected(self):
        for script in ("window.WF_PIXEL_PREVIEWS={};", (self.source / INDEX).read_text(encoding="utf-8") + "alert('x');"):
            (self.source / INDEX).write_text(script, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "索引不同|额外代码"):
                pixel_plan(self.source, self.catalog)

    def test_tampered_missing_and_unsafe_media_are_rejected(self):
        path = self.source / self.record["actions"][0]["url"]
        original = path.read_bytes()
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "媒体哈希"):
            pixel_plan(self.source, self.catalog)
        path.unlink()
        with self.assertRaisesRegex(ValueError, "媒体哈希"):
            pixel_plan(self.source, self.catalog)
        path.write_bytes(original)
        self.record["actions"][0]["url"] = "media/pixels/../../private.webp"
        self.write()
        with self.assertRaisesRegex(ValueError, "媒体哈希"):
            pixel_plan(self.source, self.catalog)

    def test_wrong_poster_dimensions_animation_and_private_fields_are_rejected(self):
        from PIL import Image
        wrong = self.save(webp([Image.new("RGBA", (8, 8), (255, 0, 0, 255))]))
        for change in (lambda r: r.update(code="internal-code"),
                       lambda r: r["actions"][0].update(animated=not r["actions"][0]["animated"]),
                       lambda r: r["actions"][0]["poster"].update(url=wrong)):
            altered = copy.deepcopy(self.index)
            change(altered["characters"][self.cid])
            self.write(altered)
            with self.assertRaises(ValueError):
                pixel_plan(self.source, self.catalog)

    def test_index_revision_and_summary_counts_cannot_be_forged(self):
        for key, value in (("revision", "b" * 64), ("summary", {}), ("version", "1.4.999")):
            self.write()
            altered = copy.deepcopy(self.index)
            altered[key] = value
            raw = json.dumps(altered)
            (self.source / JSON_INDEX).write_text(raw, encoding="utf-8")
            (self.source / INDEX).write_text("window.WF_PIXEL_PREVIEWS=" + raw + ";", encoding="utf-8")
            with self.assertRaises(ValueError):
                pixel_plan(self.source, self.catalog)

    def test_invisible_rgb_difference_does_not_reject_matching_first_frame(self):
        from PIL import Image
        urls = []
        for color in ((255, 0, 0, 0), (0, 0, 255, 0)):
            frame = Image.new("RGBA", (8, 8), color)
            frame.putpixel((4, 4), (30, 100, 200, 255))
            urls.append(self.save(webp([frame])))
        for action in self.record["actions"]:
            action.update(url=urls[0], poster={"url": urls[1], "width": 8, "height": 8},
                          width=8, height=8, animated=False)
        self.record["poster"] = self.record["actions"][0]["poster"]
        self.write()
        self.assertTrue(pixel_plan(self.source, self.catalog)[2]["mediaHashVerified"])

    def test_symlink_pixel_directory_is_rejected(self):
        with patch.object(Path, "is_symlink", lambda p: p.name == "pixels"):
            with self.assertRaisesRegex(ValueError, "链接"):
                pixel_plan(self.source, self.catalog)


if __name__ == "__main__":
    unittest.main()

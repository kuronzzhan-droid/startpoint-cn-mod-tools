"""Incremental pixel export path, source and cache integrity checks."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_wiki_pixel_render import fixture, packed
import wf_mod_tool as core
from wf_wiki_categories import HIDDEN_CHARACTER_IDS
from wf_wiki_pixel_output import PixelOutput, digest
from wf_wiki_pixel_sources import PixelSources
from wf_wiki_external_character import CHARACTER_ID, CODE, PACKAGE_ID
from wf_wiki_public import public_id
import wf_wiki_pixels as pixels


class WikiPixelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo, self.output = self.base / "repo", self.base / "site"
        self.store = self.repo / "game/upload"
        self.store.mkdir(parents=True)
        self.output.mkdir()
        (self.output / ".wf-wiki-export.json").write_text('{"generator":"wf_wiki","complete":true}')
        self.cid = public_id("c", "101")
        self.catalog = {"meta": {"version": "1.4.54"}, "characters": [{"id": self.cid}]}
        self.table = {"101": [["secret-code"]]}
        self.source_patch = patch("wf_wiki_pixel_sources.WikiSource")
        self.mock_source = self.source_patch.start()
        self.addCleanup(self.source_patch.stop)
        self.mock_source.return_value.table.return_value = self.table
        self.paths = {}
        for name, raw in fixture().items():
            path = core.table_path(self.store, "character/secret-code/pixelart/" + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.paths[name] = path

    def export(self, **kwargs):
        return pixels.export_pixels(self.repo, self.output, catalog=self.catalog, store=self.store, **kwargs)

    def test_json_offline_js_match_and_public_assets_are_hash_addressed(self):
        result = self.export()
        raw = (self.output / "data/pixel-previews.json").read_text(encoding="utf-8")
        script = (self.output / "data/pixel-previews.js").read_text(encoding="utf-8")
        self.assertEqual(json.loads(script.removeprefix("window.WF_PIXEL_PREVIEWS=").strip().removesuffix(";")), result)
        self.assertEqual(json.loads(raw), result)
        self.assertEqual(result["summary"]["actions"], 4)
        self.assertNotIn("secret-code", raw)
        self.assertNotIn("timeline", raw)
        for path in (self.output / "media/pixels").iterdir():
            self.assertEqual(path.stem, digest(path.read_bytes()))
        self.assertTrue(json.loads((self.output / ".wf-wiki-export.json").read_bytes())["complete"])

    def test_cache_reuses_verified_files_and_preserves_mtime(self):
        first = self.export()
        before = {p: p.stat().st_mtime_ns for p in self.output.rglob("*") if p.is_file()}
        with patch.object(pixels, "render_actions", side_effect=AssertionError("cache must avoid rendering")):
            self.assertEqual(self.export(), first)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})

    def test_corrupt_media_is_regenerated_and_bad_cache_url_never_followed(self):
        first = self.export()
        path = self.output / first["characters"][self.cid]["actions"][0]["url"]
        expected = path.read_bytes()
        path.write_bytes(b"broken")
        self.export()
        self.assertEqual(path.read_bytes(), expected)
        index = self.output / "data/pixel-previews.json"
        altered = json.loads(index.read_bytes())
        altered["characters"][self.cid]["poster"]["url"] = "../../important.txt"
        index.write_text(json.dumps(altered), encoding="utf-8")
        self.assertEqual(self.export(), first)
        self.assertFalse((self.base / "important.txt").exists())

    def test_changed_sources_invalidate_cache_and_drift_preserves_old_index(self):
        first = self.export()
        self.paths["pixelart.frame.amf3.deflate"].write_bytes(packed(dict(name="private-character-code/animation", scale=3)))
        second = self.export()
        self.assertNotEqual(first["revision"], second["revision"])
        previous = (self.output / "data/pixel-previews.json").read_bytes()
        original = pixels.render_actions
        def changing(raw, save, unavailable):
            answer = original(raw, save, unavailable)
            self.paths["sprite_sheet.png"].write_bytes(b"drift")
            return answer
        self.paths["pixelart.frame.amf3.deflate"].write_bytes(packed(dict(name="private-character-code/animation", scale=4)))
        with patch.object(pixels, "render_actions", changing), self.assertRaisesRegex(RuntimeError, "发生变化"):
            self.export()
        self.assertEqual((self.output / "data/pixel-previews.json").read_bytes(), previous)

    def test_hidden_or_unmapped_public_ids_are_rejected(self):
        hidden = next(iter(HIDDEN_CHARACTER_IDS))
        self.table[hidden] = [["secret-code"]]
        for value in (public_id("c", hidden), public_id("c", "99999999")):
            self.catalog["characters"] = [{"id": value}]
            with self.assertRaisesRegex(ValueError, "可信"):
                self.export()

    def test_source_resolution_changes_are_detected(self):
        source = PixelSources(self.repo, self.store, self.output)
        source.read(self.cid)
        path = core.table_path(self.store, "character/secret-code/pixelart/special_sprite_sheet.png")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"new optional source")
        with self.assertRaisesRegex(RuntimeError, "路径发生变化"):
            source.verify()

    def test_output_and_source_identifiers_fail_closed(self):
        for output in (self.repo, self.base, self.store / "wiki", self.repo / "src"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                PixelOutput(output, self.repo, self.store)
        with patch.object(Path, "is_symlink", lambda p: p.name == "pixels"), self.assertRaisesRegex(ValueError, "链接"):
            PixelOutput(self.output, self.repo, self.store)
        for rows in ([{"id": "101"}], [{"id": self.cid}, {"id": self.cid}]):
            self.catalog["characters"] = rows
            with self.assertRaises(ValueError):
                self.export()

    def test_catalog_file_is_checked_again_before_publication(self):
        path = self.output / "data.json"
        path.write_text(json.dumps(self.catalog), encoding="utf-8")
        self.mock_source.return_value.verify_unchanged.side_effect = lambda: path.write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "角色目录发生变化"):
            pixels.export_pixels(self.repo, self.output, store=self.store)
        self.assertFalse((self.output / "data/pixel-previews.json").exists())

    def test_external_moon_fox_uses_only_identity_and_manifest_verified_resources(self):
        package = self.base / "moon-fox"
        entries = []
        for filename, raw in fixture().items():
            logical = f"character/{CODE}/pixelart/{filename}"
            path = package / "roots/common" / logical
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            entries.append({"logical_path": logical, "sha256": digest(raw)})
        manifest = {"character_id": CHARACTER_ID, "code_name": CODE, "package_id": PACKAGE_ID,
                    "roots": {"common": entries}}
        (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.catalog["characters"] = [{"id": public_id("c", CHARACTER_ID)}]
        result = self.export(external_package=package)
        self.assertEqual(result["summary"]["characters"], 1)
        path.write_bytes(b"not declared content")
        with self.assertRaisesRegex(ValueError, "清单校验值"):
            self.export(external_package=package)

    def test_optional_failure_is_reported_without_losing_basics_and_reuses_cache(self):
        for filename, raw in fixture(True).items():
            path = core.table_path(self.store, "character/secret-code/pixelart/" + filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        result = self.export()
        self.assertEqual(result["summary"]["actions"], 4)
        self.assertEqual(result["summary"]["unavailableActions"][0]["characterId"], self.cid)
        with patch.object(pixels, "render_actions", side_effect=AssertionError("should reuse")):
            self.assertEqual(self.export(), result)


if __name__ == "__main__":
    unittest.main()

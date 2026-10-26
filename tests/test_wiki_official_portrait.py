"""A precise Wiki-only exception for a confirmed reskinned official portrait."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wf_assets
import wf_mod_tool as core
import wf_wiki_catalog as catalog
from wf_enhancement_policy import BaselineUnavailable
from wf_wiki_media import WikiMedia, digest
from wf_wiki_public import public_catalog, public_id
from test_wiki_catalog import MemorySource, character

PORTRAIT = "character/pirates_girl/ui/full_shot_1440_1920_0.png"


def png(color):
    from PIL import Image
    stream = io.BytesIO()
    Image.new("RGBA", (16, 20), color).save(stream, "PNG")
    return wf_assets.png_encode(stream.getvalue())


class OfficialImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.media = WikiMedia(root / "store", root / "site")
        self.official = png((230, 20, 20, 255))
        self.live = png((20, 20, 230, 255))
        path = core.table_path(self.media.store, PORTRAIT)
        path.parent.mkdir(parents=True)
        path.write_bytes(self.live)
        self.baseline = Mock(official_tail="1.4.54", get=Mock(return_value=self.official))

    def test_official_bytes_replace_cached_live_image_with_hash_address_and_provenance(self):
        from PIL import Image
        polluted = self.media.image(PORTRAIT)
        self.media._previous = dict(self.media.entries)
        with patch.object(self.media, "_read", side_effect=AssertionError("no live fallback")):
            url = self.media.official_image(PORTRAIT, self.baseline)
        hashed = core.sha1_path(PORTRAIT)
        self.baseline.get.assert_called_once_with("medium", hashed[:2] + "/" + hashed[2:])
        self.assertNotEqual(url, polluted)
        self.assertRegex(url, r"^media/[0-9a-f]{64}\.webp$")
        entry = self.media.entries[PORTRAIT]
        self.assertEqual(entry["sourceSha256"], digest(self.official))
        self.assertEqual((entry["sourceKind"], entry["sourceRoot"], entry["officialTail"]),
                         ("official-baseline", "medium", "1.4.54"))
        with Image.open(self.media.output / url) as image:
            red, _, blue = image.convert("RGB").getpixel((8, 10))
            self.assertGreater(red, blue + 150)
        self.assertTrue((self.media.output / polluted).exists())

    def test_missing_broken_or_unavailable_official_never_reuses_live(self):
        for value in (None, BaselineUnavailable("unavailable"), OSError("missing archive"),
                      zipfile.BadZipFile("broken archive"), b"broken PNG"):
            with self.subTest(value=type(value).__name__):
                polluted = self.media.image(PORTRAIT)
                self.media._previous = dict(self.media.entries)
                baseline = Mock(official_tail="1.4.54")
                if isinstance(value, Exception):
                    baseline.get.side_effect = value
                else:
                    baseline.get.return_value = value
                with patch.object(self.media, "_read", side_effect=AssertionError("no live fallback")):
                    self.assertIsNone(self.media.official_image(PORTRAIT, baseline))
                self.assertNotIn(PORTRAIT, self.media.entries)
                self.assertTrue(self.media.errors)
                self.assertTrue((self.media.output / polluted).exists())

    def test_reused_correct_image_gains_provenance_without_mutating_previous_manifest(self):
        core.table_path(self.media.store, PORTRAIT).write_bytes(self.official)
        url = self.media.image(PORTRAIT)
        manifest = self.media.output / "media-manifest.json"
        manifest.write_text(json.dumps(self.media.entries), encoding="utf-8")
        media = WikiMedia(self.media.store, self.media.output)
        previous = dict(media._previous[PORTRAIT])
        with patch.object(media, "_save", side_effect=AssertionError("must reuse verified image")):
            self.assertEqual(media.official_image(PORTRAIT, self.baseline), url)
        self.assertEqual(media._previous[PORTRAIT], previous)
        self.assertEqual(media.entries[PORTRAIT]["sourceKind"], "official-baseline")


class CatalogPortraitTests(unittest.TestCase):
    def fixture(self):
        source = MemorySource()
        source.live["character"]["111002"] = source.base["character"]["111002"] = [character("pirates_girl")]
        source.live["text"] = {"111002": [["玛丽娜"]]}
        source.baseline = object()
        image = lambda path: "media/" + hashlib.sha256(path.encode()).hexdigest() + ".webp"
        media = Mock(image=Mock(side_effect=image), official_image=Mock(return_value="media/" + "a" * 64 + ".webp"))
        return source, media

    def test_only_confirmed_before_portrait_uses_official_and_public_data_hides_code(self):
        source, media = self.fixture()
        entry = catalog.character_entry(source, "111002", None, media)
        media.official_image.assert_called_once_with(PORTRAIT, source.baseline)
        self.assertNotIn(PORTRAIT, [call.args[0] for call in media.image.call_args_list])
        after = PORTRAIT.replace("_0.png", "_1.png")
        self.assertIn(after, [call.args[0] for call in media.image.call_args_list])
        self.assertEqual([p["label"] for p in entry["portraits"]], ["觉醒前", "觉醒后"])
        public = public_catalog({"meta": {}, "characters": [entry]})
        self.assertEqual(public["characters"][0]["id"], public_id("c", "111002"))
        self.assertNotIn("pirates_girl", json.dumps(public))
        self.assertNotIn("officialTail", json.dumps(public))
        media.official_image.reset_mock()
        catalog.character_entry(source, "10", None, media)
        media.official_image.assert_not_called()

    def test_missing_before_has_explicit_warning_without_replacing_after(self):
        source, media = self.fixture()
        media.official_image.return_value = None
        entry = catalog.character_entry(source, "111002", None, media)
        self.assertEqual([p["label"] for p in entry["portraits"]], ["觉醒后"])
        self.assertIn("觉醒前官方立绘暂不可用，已隐藏错误图片", entry["warnings"])
        self.assertNotIn(PORTRAIT, [call.args[0] for call in media.image.call_args_list])

    def test_exception_does_not_restore_hidden_mod_characters_or_export_their_images(self):
        source, media = self.fixture()
        hidden = {"119998": "resistance_princess_canary2", "119999": "kyle_wolf_knight"}
        source.live["character"].update({cid: [character(code)] for cid, code in hidden.items()})
        source.fingerprints, source.live_hashes, source.missing = {}, {}, set()
        source.verify_unchanged = Mock()
        media.store = Path("unused")
        with patch.object(catalog, "WikiSource", return_value=source), patch.object(
                catalog, "version_at", return_value="1.4.1111"):
            result = catalog.build_catalog(Path("unused"), media)
        self.assertTrue(set(hidden).isdisjoint(c["id"] for c in result["characters"]))
        requests = [call.args[0] for call in media.image.call_args_list + media.official_image.call_args_list]
        self.assertFalse(any(f"character/{code}/" in path for code in hidden.values() for path in requests))
        self.assertIn("111002", [c["id"] for c in result["characters"]])


if __name__ == "__main__":
    unittest.main()

"""Real codec and output boundary checks for portable wiki exports."""
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wf_assets
import wf_mod_tool as core
from wf_wiki import prepare_output, validate_catalog, verify_table_sources
from wf_wiki_media import WikiMedia


class WikiExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.store = self.repo / "game/upload"
        self.store.mkdir(parents=True)
        self.media = WikiMedia(self.store, self.base / "site")

    def put(self, logical, raw):
        path = core.table_path(self.store, logical)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def test_audio_converts_every_frame_and_deduplicates(self):
        frame = bytes.fromhex("fffb7400") + bytes(284)
        stored = wf_assets.mp3_encode(frame * 8)
        self.put("character/a/voice/home/home_0.mp3", stored)
        self.put("character/b/voice/home/home_0.mp3", stored)
        first = self.media.audio("character/a/voice/home/home_0.mp3")
        second = self.media.audio("character/b/voice/home/home_0.mp3")
        self.assertEqual(first, second)
        self.assertEqual((self.media.output / first).read_bytes(), frame * 8)
        self.assertEqual(self.media.summary()["files"], 1)

    def test_corrupt_audio_does_not_get_play_button(self):
        self.put("broken.mp3", b"broken audio")
        self.assertIsNone(self.media.audio("broken.mp3"))
        self.assertEqual(len(self.media.errors), 1)

    def test_truncated_final_audio_frame_is_rejected(self):
        self.put("truncated.mp3", bytes.fromhex("7ffb7400") + bytes(30))
        self.assertIsNone(self.media.audio("truncated.mp3"))

    def test_image_decode_preserves_alpha(self):
        from PIL import Image
        original = Image.new("RGBA", (32, 32), (30, 40, 50, 0))
        original.putpixel((16, 16), (50, 100, 200, 255))
        stream = io.BytesIO()
        original.save(stream, "PNG")
        self.put("picture.png", wf_assets.png_encode(stream.getvalue()))
        result = self.media.image("picture.png")
        with Image.open(self.media.output / result) as exported:
            self.assertEqual(exported.getpixel((0, 0))[3], 0)
            self.assertEqual(exported.getpixel((16, 16))[3], 255)

    def test_source_drift_is_rejected(self):
        path = self.put("bad.mp3", b"one")
        self.media.audio("bad.mp3")
        path.write_bytes(b"two")
        with self.assertRaisesRegex(RuntimeError, "发生变化"):
            self.media.verify_sources()

    def test_missing_media_is_explicit(self):
        self.assertIsNone(self.media.image("missing.png"))
        self.assertEqual(self.media.errors[0]["reason"], "资源缺失")

    def test_output_cannot_overwrite_source(self):
        for path in (self.repo, self.base, self.repo / "src/new", self.store / "wiki"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                prepare_output(path, self.repo, self.store)

    def test_output_cannot_overwrite_unrelated_artifacts(self):
        output = self.base / "existing"
        output.mkdir()
        (output / "important.txt").write_text("keep")
        with self.assertRaises(ValueError):
            prepare_output(output, self.repo, self.store)
        self.assertEqual((output / "important.txt").read_text(), "keep")

    def test_owned_export_can_be_refreshed(self):
        output = self.base / "site"
        prepare_output(output, self.repo, self.store)
        self.assertEqual(prepare_output(output, self.repo, self.store), output)

    def test_catalog_rejects_duplicate_ids_and_missing_media(self):
        for characters in ([{"id": "1"}, {"id": "1"}],
                           [{"id": "1", "icon": "media/not-here.webp"}],
                           [{"id": "1", "icon": "../secret.png"}]):
            with self.subTest(characters=characters), self.assertRaises(ValueError):
                validate_catalog({"characters": characters}, self.base / "site")

    def test_late_source_creation_is_rejected(self):
        self.put("master/example.orderedmap", b"changed")
        with self.assertRaises(RuntimeError):
            verify_table_sources({"sourceMissing": ["master/example.orderedmap"]}, {}, self.store)

    def test_marker_must_identify_this_generator(self):
        output = self.base / "site"
        output.mkdir()
        (output / ".wf-wiki-export.json").write_text('{"generator":"unrelated"}')
        with self.assertRaises(ValueError):
            prepare_output(output, self.repo, self.store)

    def test_existing_link_cannot_redirect_output(self):
        output = prepare_output(self.base / "site", self.repo, self.store)
        target = self.base / "keep.txt"
        target.write_text("keep")
        try:
            (output / "data.js").symlink_to(target)
        except OSError:
            self.skipTest("host does not permit symlinks")
        with self.assertRaises(ValueError):
            prepare_output(output, self.repo, self.store)
        self.assertEqual(target.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()

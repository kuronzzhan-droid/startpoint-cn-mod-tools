"""Native avatar source selection, missing-form fallback and package isolation."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_avatars import character_avatars
from wf_wiki_external_source import PackageMedia
from wf_wiki_media import WikiMedia


class AvatarTests(unittest.TestCase):
    def media(self, paths):
        return SimpleNamespace(has=lambda path: path in paths,
                               image=Mock(side_effect=lambda path: paths.get(path)))

    def test_both_forms_use_native_squares_without_illustration_crop(self):
        media = self.media({"character/example/ui/square_0.png": "media/first.webp",
                            "character/example/ui/square_1.png": "media/second.webp"})
        self.assertEqual(character_avatars("example", media),
                         {"before": "media/first.webp", "after": "media/second.webp"})
        self.assertEqual(media.image.call_count, 2)

    def test_thumbnail_is_only_used_for_the_same_form(self):
        media = self.media({"character/example/ui/square_0.png": "media/first.webp",
                            "character/example/ui/thumbnail_1.png": "media/second.webp"})
        self.assertEqual(character_avatars("example", media)["after"], "media/second.webp")
        self.assertEqual(media.image.call_args.args[0], "character/example/ui/thumbnail_1.png")

    def test_missing_awakened_avatar_remains_explicitly_absent(self):
        media = self.media({"character/example/ui/square_0.png": "media/first.webp"})
        self.assertEqual(character_avatars("example", media), {"before": "media/first.webp"})
        self.assertEqual(media.image.call_count, 1)

    def test_missing_optional_forms_do_not_read_or_report_missing_media(self):
        media = WikiMedia(Path("unused"), Path("unused-output"))
        with patch("wf_wiki_media.wf_assets.locate", return_value=None):
            self.assertEqual(character_avatars("example", media), {})
        self.assertFalse(media.errors)

    def test_external_package_variants_never_fall_back_to_live_store(self):
        parent = WikiMedia(Path("unused"), Path("unused-output"))
        logical = "character/example/ui/square_1.png"
        media = PackageMedia(parent, SimpleNamespace(entries={("medium", logical): {}}))
        with patch("wf_wiki_media.wf_assets.locate", side_effect=AssertionError("live lookup")):
            self.assertTrue(media.has(logical))
            self.assertFalse(media.has("character/example/ui/square_0.png"))


if __name__ == "__main__":
    unittest.main()

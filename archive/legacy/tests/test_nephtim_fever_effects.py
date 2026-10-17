"""从真实官方资源装配，验证技能引用、atlas 图块和透明状态图标。"""

from wf.paths import root_path
from io import BytesIO
from pathlib import Path
import os
import sys
import unittest
import zlib

from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_nephtim_fever_effects as effects
import wf_nephtim_fever_skill as skill
from wf_character_requirements import MasterAssetReference, required_asset_paths
from wf_assets import PNG_FAKE, png_decode
from wf_enhancement_policy import OfficialBaseline
from wf_nephtim_fever_powerflip import with_bundle_fallback
from wf_quest_lib import hashed_rel

CDN = Path(os.environ.get("WF_CDN_ROOT", ('${WF_ROOT}/startpoint-cn/.cdn/cn'.replace("${WF_ROOT}", str(root_path())))))
BUNDLE = Path(os.environ.get("WF_BUNDLE", ('${WF_ROOT}/startpoint-cn/弹国服/bundle.zip'.replace("${WF_ROOT}", str(root_path())))))
GENERAL = "battle/effect/skill_general/multiball/multiball_general_effect/multiball_general_effect"


def decode(raw):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def values(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from values(child)
    elif isinstance(node, dict):
        for key, child in node.items():
            yield key
            yield from values(child)


class NephtimEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CDN.is_dir() or not BUNDLE.is_file():
            raise unittest.SkipTest("official CDN and local bundle fixture unavailable")
        official = OfficialBaseline(CDN, write_cache=False)
        cls.cdn = staticmethod(lambda path: official.get("common", hashed_rel(path)))
        cls.files = effects.assets(cls.cdn)

    def test_missing_cdn_disappearance_uses_original_bundle_bytes(self):
        path = GENERAL + ".png"
        self.assertIsNone(self.cdn(path), "fixture must exercise the real missing CDN asset")
        original = with_bundle_fallback(self.cdn, BUNDLE)(path)
        target = skill.LIGHT_FADE_FX.rsplit("/", 1)[0] + "/" + skill.CODE + "_light_fade.png"
        self.assertEqual(self.files["common", target], original)
        with Image.open(BytesIO(png_decode(original))) as sheet:
            sheet.load()
            self.assertGreater(sheet.width, 0)

    def test_every_active_and_summon_effect_has_both_animation_files(self):
        trees = [skill.build_skill(1), skill.build_skill(2), skill.build_spawn()]
        references = {item[1] for tree in trees for item in values(tree)
                      if isinstance(item, list) and item and item[0] == "SpecifyEffectDirectly"}
        self.assertEqual(len(references), 13)
        for path in references:
            self.assertIn(skill.CODE, path)
            for suffix in (".parts.amf3.deflate", ".timeline.amf3.deflate"):
                self.assertIn(("common", path + suffix), self.files)

    def test_every_part_resolves_to_one_private_atlas_and_sheet(self):
        images = {}
        atlases = 0
        for (tier, path), raw in self.files.items():
            self.assertEqual(tier, "common")
            self.assertIn(skill.CODE, path)
            if not path.endswith(".atlas.amf3.deflate"):
                continue
            atlases += 1
            sheet_path = path.removesuffix(".atlas.amf3.deflate") + ".png"
            with Image.open(BytesIO(png_decode(self.files[tier, sheet_path]))) as sheet:
                sheet.load()
            for item in decode(raw):
                self.assertNotIn(item["n"], images, "ambiguous atlas image reference")
                images[item["n"]] = sheet_path
        self.assertEqual(atlases, 4)
        parts = 0
        for (_, path), raw in self.files.items():
            if path.endswith(".parts.amf3.deflate"):
                parts += 1
                for item in decode(raw)["i"]:
                    self.assertFalse(item["s"], "unexpected nested animation needs explicit closure")
                    self.assertIn(item["p"], images, (path, item["p"]))
        self.assertEqual(parts, 13)

    def test_each_animation_uses_its_directory_default_atlas(self):
        # The client loads one atlas named after the animation's directory;
        # finding a texture in a different packaged atlas is insufficient.
        checked = 0
        for (_, path), raw in self.files.items():
            if not path.endswith(".parts.amf3.deflate"):
                continue
            effect = path.removesuffix(".parts.amf3.deflate")
            required = required_asset_paths(MasterAssetReference("skill_effect", effect, path))
            for dependency in required:
                self.assertIn(("common", dependency), self.files, (effect, dependency))
            atlas = decode(self.files["common", required[3]])
            loaded = {item["n"] for item in atlas}
            referenced = {item["p"] for item in decode(raw)["i"]}
            self.assertFalse(referenced - loaded, (effect, sorted(referenced - loaded)))
            checked += 1
        self.assertEqual(checked, 13)

    def test_all_amf_roundtrips_and_contains_no_official_effect_path(self):
        old_paths = ("battle/effect/skill_unique/ruin_girl_halfanv/",
                     "battle/effect/skill_unique/ruin_girl/",
                     "battle/effect/skill_unique/ruin_girl_3halfanv/",
                     "battle/effect/skill_general/multiball/")
        for (_, path), raw in self.files.items():
            if not path.endswith(".amf3.deflate"):
                continue
            tree = decode(raw)
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
            for item in values(tree):
                if isinstance(item, str):
                    self.assertFalse(item.startswith(old_paths), (path, item))

    def test_native_timeline_sounds_and_animation_are_preserved(self):
        source = "battle/effect/skill_unique/ruin_girl_halfanv/ruin_girl_halfanv_all.timeline.amf3.deflate"
        target = skill.SKILL_FX + skill.CODE + "_fever_all.timeline.amf3.deflate"
        self.assertEqual(decode(self.files["common", target]), decode(self.cdn(source)))

    def test_state_icon_matches_unique_rows_and_has_real_alpha(self):
        expected = {row[0][2] + ".png" for row in skill.unique_rows().values()}
        self.assertEqual(expected, {skill.STATE_ICON + ".png"})
        raw = self.files["common", skill.STATE_ICON + ".png"]
        self.assertTrue(raw.startswith(PNG_FAKE))
        self.assertEqual(png_decode(raw), effects.ICON_PATH.read_bytes())
        with Image.open(BytesIO(png_decode(raw))) as icon:
            icon.load()
            self.assertEqual(icon.size, (48, 48))
            self.assertEqual(icon.mode, "RGBA")
            self.assertEqual(icon.getextrema()[3], (0, 255))
            self.assertTrue(all(icon.getpixel(point)[3] == 0
                                for point in ((0, 0), (47, 0), (0, 47), (47, 47))))


if __name__ == "__main__":
    unittest.main()

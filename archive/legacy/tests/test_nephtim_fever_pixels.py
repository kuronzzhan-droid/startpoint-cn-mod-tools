"""真实官方素材逐帧校验：主体保护、动作别名、光效来源及生产形状。"""
from functools import lru_cache
import io
from pathlib import Path
import sys
import tempfile
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

from PIL import Image

import wf_assets
import wf_character_pack as pack
import wf_client_legality as legality
from wf_enhancement_policy import OfficialBaseline
import wf_mod_tool as core
import wf_nephtim_fever_pixels as pixels


class NephtimFeverPixelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[2]
        if repo.parent.name == ".worktrees":
            repo = repo.parents[1]
        if not (repo / ".cdn/cn").is_dir():
            raise unittest.SkipTest("official CDN pixel fixture unavailable")
        baseline = OfficialBaseline(repo / ".cdn/cn", cache_dir=repo / "mod-tools/work/official-baseline", write_cache=False)

        @lru_cache(None)
        def read(logical):
            digest = core.sha1_path(logical)
            raw = baseline.get("common", digest[:2] + "/" + digest[2:])
            if raw is None:
                raise ValueError("missing official fixture: " + logical)
            return raw

        cls.read = staticmethod(read)
        cls.files = pixels.assets(read)
        cls.source, cls.result = {}, {}
        for kind in pixels.STEMS:
            cls.source[kind] = pixels._load(read, pixels.SOURCE, kind)
            cls.result[kind] = pixels._load(lambda path: cls.files["common", path], pixels.CODE, kind)

    def test_dark_and_light_donors_have_verified_official_identities(self):
        rows = core.read_orderedmap_file_from_bytes(self.read("master/character/character.orderedmap"))
        for cid, code, element in (("161177", pixels.SOURCE, "5"),
                                   ("151001", pixels.LIGHT_BASE, "4"),
                                   ("151009", pixels.LIGHT_FESTIVAL, "4"),
                                   ("151063", pixels.LIGHT_SUMMER, "4")):
            row = core.read_csv_lines(rows[cid])[0]
            self.assertEqual((row[0], row[3]), (code, element))

    def test_only_eight_private_pixel_assets_are_returned(self):
        self.assertEqual(len(self.files), 8)
        self.assertTrue(all(tier == "common" and path.startswith("character/ruin_girl_campus/pixelart/")
                            for tier, path in self.files))
        self.assertFalse(pixels.metadata()["ui_portraits_voice_changed"])

    def test_all_original_endpoints_geometry_and_timeline_are_preserved(self):
        for kind, source in self.source.items():
            originals, ends, frame, timeline = source
            output, new_ends, new_frame, new_timeline = self.result[kind]
            self.assertTrue(set(ends) <= set(new_ends), kind)
            self.assertEqual(len(originals), len(output))
            self.assertEqual(new_frame, pixels._remap(frame))
            self.assertEqual(new_timeline, pixels._remap(timeline))
            self.assertTrue(all(a.size == b.size == (256, 256) for a, b in zip(originals, output)))
        self.assertEqual(len(self.result["pixelart"][0]), 428)
        self.assertEqual(len(self.result["special"][0]), 174)

    def test_every_original_body_texel_survives_every_tick(self):
        checked = 0
        for kind, (originals, _, _, timeline) in self.source.items():
            output = self.result[kind][0]
            active = set()
            for sequence in timeline["sequences"]:
                if sequence["name"] in pixels.metadata()["fx_actions"][kind]:
                    active.update(range(sequence["begin"], sequence["end"] + 1))
            for tick, (before, after) in enumerate(zip(originals, output), 1):
                if tick not in active:
                    self.assertEqual(pixels.recolor(before).tobytes(), after.tobytes(), (kind, tick))
                    continue
                box = before.getbbox()
                if not box:
                    continue
                for old, new in zip(before.crop(box).get_flattened_data(), after.crop(box).get_flattened_data()):
                    if not old[3] or old[:3] in pixels.DARK_FLAME:
                        continue
                    expected = (*pixels.PALETTE.get(old[:3], old[:3]), old[3])
                    self.assertEqual(new, expected, (kind, tick, old))
                    checked += 1
        self.assertGreater(checked, 30000)

    def test_light_layers_never_import_faces_or_non_effect_colors(self):
        for code, allowed in pixels.FX_COLORS.items():
            frames, _, _, _ = pixels._load(self.read, code)
            neutral_colors = {pixel[:3] for pixel in frames[0].get_flattened_data() if pixel[3]}
            self.assertFalse(neutral_colors & allowed)
            imported = 0
            for frame in frames[50:110]:
                layer = pixels.light_layer(frame, code)
                self.assertIsNone(layer.crop((110, 104, 146, 148)).getbbox())
                for pixel in layer.get_flattened_data():
                    if pixel[3]:
                        self.assertIn(pixel[:3], allowed)
                        imported += 1
            self.assertGreater(imported, 0)

    def test_effects_end_cleanly_and_idle_has_no_extra_particles(self):
        for kind, (originals, _, _, timeline) in self.source.items():
            actual = self.result[kind][0]
            for sequence in timeline["sequences"]:
                if sequence["name"] in pixels.metadata()["fx_actions"][kind]:
                    for tick in (sequence["begin"], sequence["end"]):
                        expected = pixels.recolor(originals[tick - 1], remove_flame=True)
                        self.assertEqual(expected.tobytes(), actual[tick - 1].tobytes())
        for tick in range(1, 51):
            expected = pixels.recolor(self.source["pixelart"][0][tick - 1])
            self.assertEqual(expected.tobytes(), self.result["pixelart"][0][tick - 1].tobytes())

    def test_production_shape_and_pixel_visibility_accept_real_outputs(self):
        frames, _, _, timeline = self.result["pixelart"]
        self.assertEqual(legality.pixelart_timeline_problems(timeline), [])
        counts = {tick: sum(alpha > 127 for alpha in frame.getchannel("A").get_flattened_data())
                  for tick, frame in enumerate(frames, 1)}
        self.assertEqual(legality.pixelart_visibility_problems(timeline, counts), [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            declared = []
            for (tier, logical), raw in self.files.items():
                path = root / "roots" / tier / logical
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                declared.append((tier, logical, path))
            self.assertEqual(pack._client_asset_shape_errors({}, root, declared), [])

    def test_png_game_decode_and_reencode_preserve_true_rgba(self):
        for (tier, path), raw in self.files.items():
            if path.endswith(".png"):
                image = Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA")
                roundtrip = Image.open(io.BytesIO(wf_assets.png_decode(pixels._png(image)))).convert("RGBA")
                self.assertEqual(image.tobytes(), roundtrip.tobytes())
                self.assertLessEqual(max(image.size), 2048)


if __name__ == "__main__":
    unittest.main()

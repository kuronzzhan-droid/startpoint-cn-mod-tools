"""官方两种球逐帧克隆与新演员必要序列验证。"""
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
import wf_nephtim_fever_ball_pixels as balls
from wf_nephtim_fever_pixels import _decode
from wf_pixelart_vfx import entry_for_frame, frame_index, restore_frame


class NephtimBallPixelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[2]
        if repo.parent.name == ".worktrees":
            repo = repo.parents[1]
        if not (repo / ".cdn/cn").is_dir():
            raise unittest.SkipTest("official pixel fixture unavailable")
        baseline = OfficialBaseline(repo / ".cdn/cn", cache_dir=repo / "mod-tools/work/official-baseline", write_cache=False)

        def read(logical):
            digest = core.sha1_path(logical)
            raw = baseline.get("common", digest[:2] + "/" + digest[2:])
            if raw is None:
                raise ValueError("missing source: " + logical)
            return raw

        cls.read = staticmethod(read)
        cls.files = balls.assets(read)

    def test_only_private_actor_assets_and_no_bomb_or_combat_logic(self):
        self.assertEqual(len(self.files), 8)
        for tier, logical in self.files:
            self.assertEqual(tier, "common")
            self.assertTrue(any(logical.startswith(f"character/{code}/pixelart/")
                                for code in (balls.DARK_CODE, balls.LIGHT_CODE)))
            self.assertNotIn("action", logical)
        self.assertFalse(balls.metadata()["battle_logic_included"])

    def test_all_source_texels_endpoints_and_five_sequences_stay_identical(self):
        for source, target in ((balls.DARK_SOURCE, balls.DARK_CODE), (balls.LIGHT_SOURCE, balls.LIGHT_CODE)):
            old_prefix, new_prefix = (f"character/{code}/pixelart/" for code in (source, target))
            self.assertEqual(self.read(old_prefix + "sprite_sheet.png"), self.files["common", new_prefix + "sprite_sheet.png"])
            old_atlas = _decode(self.read(old_prefix + "sprite_sheet.atlas.amf3.deflate"))
            new_atlas = _decode(self.files["common", new_prefix + "sprite_sheet.atlas.amf3.deflate"])
            self.assertEqual(balls._remap(old_atlas, source, target), new_atlas[:len(old_atlas)])
            old_timeline = _decode(self.read(old_prefix + "pixelart.timeline.amf3.deflate"))
            new_timeline = _decode(self.files["common", new_prefix + "pixelart.timeline.amf3.deflate"])
            self.assertEqual(old_timeline["sequences"], new_timeline["sequences"][:5])
            image = Image.open(io.BytesIO(wf_assets.png_decode(self.read(old_prefix + "sprite_sheet.png"))))
            old_index, new_index = frame_index(old_atlas, old_prefix + "pixelart"), frame_index(new_atlas, new_prefix + "pixelart")
            for tick in range(1, old_index[0][-1] + 1):
                self.assertEqual(restore_frame(image, entry_for_frame(old_index, tick)).tobytes(),
                                 restore_frame(image, entry_for_frame(new_index, tick)).tobytes())
            neutral = restore_frame(image, entry_for_frame(old_index, 1))
            for tick in range(old_index[0][-1] + 1, new_index[0][-1] + 1):
                self.assertEqual(neutral.tobytes(), restore_frame(image, entry_for_frame(new_index, tick)).tobytes())

    def test_production_shape_and_visibility_cover_both_new_actors(self):
        for target in (balls.DARK_CODE, balls.LIGHT_CODE):
            prefix = f"character/{target}/pixelart/"
            timeline = _decode(self.files["common", prefix + "pixelart.timeline.amf3.deflate"])
            self.assertEqual(legality.pixelart_timeline_problems(timeline), [])
            self.assertEqual(len(timeline["sequences"]), 9)
            atlas = _decode(self.files["common", prefix + "sprite_sheet.atlas.amf3.deflate"])
            index = frame_index(atlas, prefix + "pixelart")
            image = Image.open(io.BytesIO(wf_assets.png_decode(self.files["common", prefix + "sprite_sheet.png"])))
            counts = {tick: sum(alpha > 127 for alpha in restore_frame(image, entry_for_frame(index, tick)).getchannel("A").get_flattened_data())
                      for tick in range(1, index[0][-1] + 1)}
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


if __name__ == "__main__":
    unittest.main()

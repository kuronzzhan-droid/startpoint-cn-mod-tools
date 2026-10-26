"""双形态资源回归：缺序列、旧碰撞标记、帧号/图集和参考漂移。"""
import json
from pathlib import Path
import tempfile
import unittest
import sys

pass  # Imports resolve from this checkout/package, not external source copies.

from PIL import Image
import wf_client_legality as legality
import wf_seasonal7_common as C
import wf_seris_rework_pixel as P
import wf_pixelart_vfx as VFX


class SerisPixelTests(unittest.TestCase):
    def clips(self):
        im = Image.new("RGBA", (32, 32))
        im.paste((34, 62, 148, 255), (8, 10, 23, 27))
        return {name: [(im.copy(), 6), (im.copy(), 8)] for name in (*P.REGULAR, *P.EXTRA)}

    def test_both_forms_have_native_sequences_and_markers(self):
        for dragon, stem in ((False, "pixelart"), (True, "special")):
            with self.subTest(dragon=dragon):
                _, _, meta = P.compile_family(self.clips(), "seris_dragon_king", dragon)
                timeline = meta[stem + ".timeline"]
                self.assertEqual([], legality.pixelart_timeline_problems(timeline))
                self.assertEqual(12, len(timeline["sequences"]))
                self.assertEqual(set(P.REGULAR + P.EXTRA), {s["name"] for s in timeline["sequences"]})
                for tree in meta.values():
                    self.assertEqual(tree, C.amf_parse(C.amf_bytes(tree)))

    def test_every_atlas_frame_is_in_its_sequence_and_sheet(self):
        name, sheet, meta = P.compile_family(self.clips(), "seris_dragon_king")
        atlas = meta[name + ".atlas"]
        sequences = meta["pixelart.timeline"]["sequences"]
        self.assertEqual(24, len(atlas))
        for entry in atlas:
            frame = int(entry["n"].rsplit("pixelart", 1)[-1])
            self.assertEqual(1, sum(s["begin"] <= frame <= s["end"] for s in sequences))
            self.assertLessEqual(entry["x"] + entry["w"], sheet.width)
            self.assertLessEqual(entry["y"] + entry["h"], sheet.height)
            self.assertEqual(-112, entry["fx"])
            self.assertEqual(-101, entry["fy"])
        self.assertEqual("once", sequences[-1]["kind"])

    def test_missing_dragon_walk_is_rejected(self):
        clips = self.clips()
        del clips["walk_back"]
        with self.assertRaisesRegex(ValueError, "12 action slots"):
            P.compile_family(clips, "seris_dragon_king", True)

    def test_atlas_suffix_is_hold_end_so_actions_cannot_bleed(self):
        clips = self.clips()
        last = Image.new("RGBA", (32, 32), (128, 22, 22, 255))
        clips["neutral"][1] = (last, 8)
        name, sheet, meta = P.compile_family(clips, "seris_dragon_king")
        prefix = "character/seris_dragon_king/pixelart/pixelart"
        index = VFX.frame_index(meta[name + ".atlas"], prefix)
        self.assertEqual([6, 14], index[0][:2])
        for frame in range(1, 15):
            item = VFX.entry_for_frame(index, frame)
            tile = sheet.crop((item["x"], item["y"], item["x"] + 32, item["y"] + 32))
            expected = clips["neutral"][0][0] if frame <= 6 else last
            self.assertEqual(expected.tobytes(), tile.tobytes())
        self.assertEqual(meta["pixelart.timeline"]["sequences"][-1]["end"], index[0][-1])

    def test_short_hold_would_cross_collision_start_and_is_rejected(self):
        clips = self.clips()
        clips["neutral"][0] = (clips["neutral"][0][0], 1)
        with self.assertRaisesRegex(ValueError, "invalid frame/hold"):
            P.compile_family(clips, "seris_dragon_king")

    def test_exact_reference_idle_survives_compilation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "refs").mkdir()
            source = self.clips()["neutral"][0][0]
            source.putpixel((14, 11), (27, 137, 210, 255))
            source.save(root / "refs/front.png")
            clips, paths = P.load_clips(root, "neutral", False)
            self.assertEqual(source.tobytes(), clips[0][0].tobytes())
            self.assertEqual(source.tobytes(), clips[-1][0].tobytes())
            self.assertEqual([root / "refs/front.png"], paths)
            all_clips = self.clips(); all_clips["neutral"] = clips
            _, sheet, _ = P.compile_family(all_clips, "seris_dragon_king")
            self.assertEqual(source.tobytes(), sheet.crop((0, 0, 32, 32)).tobytes())

    def test_pending_api_job_cannot_become_finished_animation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); job = root / "jobs/dragon_walk_front"; job.mkdir(parents=True)
            (job / "status.json").write_text(json.dumps({"status": "processing"}))
            with self.assertRaisesRegex(ValueError, "unfinished animation"):
                P.load_clips(root, "walk_front", True)

    def test_large_human_motion_keeps_pixel_palette_and_ground(self):
        im = Image.new("RGBA", (32, 32)); im.paste((20, 70, 160, 255), (9, 4, 23, 27))
        out = P.bounded_frame(im, human=True, name="walk_front")
        self.assertEqual((9, 11, 23, 27), out.getchannel("A").getbbox())
        colors = lambda image: {image.getpixel((x, y)) for x in range(32) for y in range(32)}
        self.assertTrue(colors(out).issubset(colors(im)))
        self.assertEqual(im.tobytes(), P.bounded_frame(im, human=False, name="walk_front").tobytes())


if __name__ == "__main__":
    unittest.main()

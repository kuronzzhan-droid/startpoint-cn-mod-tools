"""Native held-frame timing, pixel integrity and optional-action boundaries."""
import io
from pathlib import Path
import sys
import unittest
import zlib
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_dsl import encode_amf3
import wf_wiki_pixel_render as render


def packed(value):
    encoder = zlib.compressobj(wbits=-15)
    return encoder.compress(encode_amf3(value)) + encoder.flush()


def fixture(special=False):
    image = Image.new("RGBA", (2, 1))
    image.putdata([(255, 0, 0, 255), (0, 255, 0, 128)])
    stream = io.BytesIO()
    image.save(stream, "PNG")
    prefix = "private-character-code/animation"
    entries = [dict(n=prefix + "0002", x=0, y=0, w=1, h=1, fw=8, fh=8, fx=-2, fy=-3),
               dict(n=prefix + "0005", x=1, y=0, w=1, h=1, fw=8, fh=8, fx=-4, fy=-3)]
    sequences = [dict(name=name, begin=start, end=end, kind=kind) for name, start, end, kind in
                 (("neutral", 1, 5, "loop"), ("walk_front", 3, 5, "loop"),
                  ("skill_ready", 1, 5, "once"), ("kachidoki", 1, 2, "loop"),
                  ("revive", 1, 9, "once"))]  # Unselected bad source range must not block previews.
    result = {"sprite_sheet.png": stream.getvalue(), "sprite_sheet.atlas.amf3.deflate": packed(entries),
              "pixelart.frame.amf3.deflate": packed(dict(name=prefix, x=-4, y=-4, scale=6)),
              "pixelart.timeline.amf3.deflate": packed({"sequences": sequences})}
    if special:
        result.update({"special_sprite_sheet.png": stream.getvalue(),
                       "special_sprite_sheet.atlas.amf3.deflate": packed(entries),
                       "special.frame.amf3.deflate": packed(dict(name=prefix)),
                       "special.timeline.amf3.deflate": packed({"sequences": [dict(name="special_pose", begin=1, end=99, kind="loop")]})})
    return result


class PixelRenderTests(unittest.TestCase):
    def test_sparse_endpoints_preserve_60hz_timing_and_trim_alignment(self):
        image, index, sequences = render.family(fixture())
        frames, durations = render.sequence_frames(image, index, sequences[0])
        self.assertEqual(durations, [33, 50])
        self.assertEqual([f.size for f in frames], [(7, 5), (7, 5)])
        self.assertEqual(frames[0].getpixel((2, 2)), (255, 0, 0, 255))
        self.assertEqual(frames[1].getpixel((4, 2)), (0, 255, 0, 128))
        self.assertEqual(frames[1].getpixel((2, 2))[3], 0)
        clipped, duration = render.sequence_frames(image, index, sequences[1])
        self.assertEqual(duration, [50])
        self.assertEqual(clipped[0].getpixel((2, 2)), (0, 255, 0, 128))

    def test_webp_roundtrip_is_lossless_with_native_once_and_loop(self):
        saved = {}
        def save(raw):
            key = str(len(saved)); saved[key] = raw; return key
        actions = render.render_actions(fixture(), save)
        self.assertEqual([a["kind"] for a in actions], ["idle", "move", "skill_ready", "victory"])
        for action in actions:
            with Image.open(io.BytesIO(saved[action["poster"]["url"]])) as poster:
                self.assertEqual(poster.n_frames, 1)
                self.assertEqual(poster.size, (action["width"], action["height"]))
            with Image.open(io.BytesIO(saved[action["url"]])) as image:
                self.assertEqual(image.n_frames > 1, action["animated"])
                if action["animated"]:
                    self.assertEqual(image.info["loop"], 0 if action["loop"] else 1)
                    duration = 0
                    for frame in range(image.n_frames):
                        image.seek(frame); image.load()
                        duration += image.info["duration"]
                    self.assertEqual(duration, action["durationMs"])
                    image.seek(1); image.load()
                    self.assertEqual(image.convert("RGBA").getpixel((4, 2)), (0, 255, 0, 128))
        self.assertNotIn("private-character", str(actions))

    def test_bad_optional_special_keeps_all_four_basic_actions(self):
        unavailable = []
        actions = render.render_actions(fixture(True), lambda raw: "saved", unavailable)
        self.assertEqual(len(actions), 4)
        self.assertEqual(unavailable, [{"kind": "special_pose", "label": "特殊姿势", "reason": "动作资源暂不能完整预览"}])

    def test_required_out_of_range_sequence_fails(self):
        source = fixture()
        timeline = render.tree(source["pixelart.timeline.amf3.deflate"])
        timeline["sequences"][0]["end"] = 99
        source["pixelart.timeline.amf3.deflate"] = packed(timeline)
        with self.assertRaisesRegex(ValueError, "超出"):
            render.render_actions(source, lambda raw: "saved")

    def test_explicit_skill_sequence_is_separate_from_skill_preparation(self):
        source = fixture()
        timeline = render.tree(source["pixelart.timeline.amf3.deflate"])
        timeline["sequences"].append(dict(name="skill", begin=1, end=5, kind="once"))
        source["pixelart.timeline.amf3.deflate"] = packed(timeline)
        actions = render.render_actions(source, lambda raw: "saved")
        self.assertEqual([(a["kind"], a["label"]) for a in actions[-2:]], [("victory", "胜利"), ("skill", "技能动作")])

    def test_compressed_metadata_rejects_truncation_and_trailing_data(self):
        raw = packed({"a": 1})
        for invalid in (raw[:-1], raw + b"extra"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                render.tree(invalid)


if __name__ == "__main__":
    unittest.main()

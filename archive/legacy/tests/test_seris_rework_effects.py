"""新效果的时间长度、透明帧与仅视觉DSL替换约束。"""
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
from PIL import Image
import wf_seris_rework_effects as E
import wf_seasonal7_common as C


class SerisEffectTests(unittest.TestCase):
    def test_uneven_frame_holds_keep_exact_old_duration(self):
        frames = [Image.new("RGBA", (16, 16)) for _ in range(9)]
        for i, image in enumerate(frames):
            image.putpixel((i, 8), (20, 180, 255, 255))
        for total, kind in ((32, "once"), (36, "once"), (60, "once"), (32, "loop")):
            _, atlas, parts, timeline = E.compile_frames(frames, "test", total, kind, (1, 0, 0, 1, -8, -8))
            segments = parts["g"][0]["s"]
            self.assertEqual(total, sum(x["l"][0]["t"] for x in segments))
            self.assertEqual(total, segments[-1]["s"] + segments[-1]["l"][0]["t"])
            self.assertEqual(total, timeline["sequences"][0]["end"])
            self.assertEqual(9, len(atlas))
            for tree in (atlas, parts, timeline):
                self.assertEqual(tree, C.amf_parse(C.amf_bytes(tree)))

    def test_visual_swap_keeps_every_gameplay_command(self):
        path = next(iter(E.OLD))
        tree = [["EventWait", 40], ["ShowEffect", "ring", ["SpecifyEffectDirectly", path]],
                ["ActionDamage", 0, ["DamageElementWater"], 40], ["CreateCondition", "Unique22", 1500]]
        out, count = E.replace_visual_paths(tree)
        self.assertEqual(1, count)
        self.assertEqual(tree[0], out[0]); self.assertEqual(tree[2:], out[2:])
        self.assertEqual(path, tree[1][2][1])
        self.assertEqual((out, 0), E.replace_visual_paths(out))

    def test_opaque_generated_background_is_rejected(self):
        frames = [Image.new("RGBA", (16, 16), (1, 2, 3, 255)) for _ in range(4)]
        with self.assertRaisesRegex(ValueError, "transparent RGBA"):
            E.compile_frames(frames, "test", 16, "once", (1, 0, 0, 1, 0, 0))


if __name__ == "__main__":
    unittest.main()

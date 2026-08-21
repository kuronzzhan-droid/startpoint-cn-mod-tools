import hashlib
import io
import tempfile
import unittest
import zlib
from pathlib import Path

from PIL import Image

import wf_assets
import wf_dsl

try:
    from wf_pixelart_special_compile import (
        SPECIAL_TICKS,
        compile_special,
    )
except ImportError:
    SPECIAL_TICKS = None
    compile_special = None


TARGET = "character/cnmod_thunder_dragon_ascendant/pixelart"


class SpecialPixelArtCompileTests(unittest.TestCase):
    def _require_module(self):
        if compile_special is None:
            self.fail("wf_pixelart_special_compile is missing")

    def _write_cels(self, root):
        paths = []
        for index in range(34):
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            width = 12 + index % 9
            height = 10 + index % 7
            left = 2 + index % 5
            top = 3 + index % 4
            color = (30 + index, 90 + index, 150 + index, 255)
            for y in range(top, top + height):
                for x in range(left, left + width):
                    image.putpixel((x, y), color)
            path = root / f"special_{index:02d}.png"
            image.save(path, format="PNG", optimize=False)
            paths.append(path)
        return paths

    def test_compiles_four_special_assets_with_exact_204_tick_contract(self):
        self._require_module()
        with tempfile.TemporaryDirectory() as temporary_name:
            cels = self._write_cels(Path(temporary_name))
            expected_images = [Image.open(path).convert("RGBA") for path in cels]
            files, report = compile_special(cels, target_prefix=TARGET)
            files_again, report_again = compile_special(cels, target_prefix=TARGET)

        self.assertEqual(files, files_again)
        self.assertEqual(report, report_again)
        self.assertFalse(report["writes_live"])
        self.assertTrue(report["package_manifest_eligible"])
        self.assertEqual(34, report["key_cel_count"])
        self.assertEqual(204, report["timeline_ticks"])
        self.assertEqual(0, report["donor_passthrough_frames"])
        self.assertEqual(0, report["official_passthrough_atlas_records"])
        self.assertEqual(34, report["unique_input_sha256"])
        self.assertEqual([512, 256], report["sheet_size"])

        expected_logicals = {
            f"{TARGET}/special_sprite_sheet.png",
            f"{TARGET}/special_sprite_sheet.atlas.amf3.deflate",
            f"{TARGET}/special.frame.amf3.deflate",
            f"{TARGET}/special.timeline.amf3.deflate",
        }
        self.assertEqual(expected_logicals, set(files))
        self.assertEqual(sorted(expected_logicals), report["roots"]["common"])

        decoded_png = wf_assets.png_decode(files[f"{TARGET}/special_sprite_sheet.png"])
        with Image.open(io.BytesIO(decoded_png)) as opened:
            sheet = opened.convert("RGBA")
        self.assertEqual((512, 256), sheet.size)

        atlas = wf_dsl.parse_dsl(
            zlib.decompress(
                files[f"{TARGET}/special_sprite_sheet.atlas.amf3.deflate"], -15
            )
        )["tree"]
        self.assertEqual(34, len(atlas))
        self.assertEqual(34, len({entry["n"] for entry in atlas}))
        self.assertEqual(
            [f"{TARGET}/special{tick:04d}" for tick in SPECIAL_TICKS],
            [entry["n"] for entry in atlas],
        )
        for expected, entry in zip(expected_images, atlas, strict=True):
            rebuilt = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            crop = sheet.crop(
                (entry["x"], entry["y"], entry["x"] + entry["w"], entry["y"] + entry["h"])
            )
            rebuilt.alpha_composite(crop, (-entry["fx"], -entry["fy"]))
            centered = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            centered.alpha_composite(expected, (96, 96))
            self.assertEqual(centered.tobytes(), rebuilt.tobytes())

        frame = wf_dsl.parse_dsl(
            zlib.decompress(files[f"{TARGET}/special.frame.amf3.deflate"], -15)
        )["tree"]
        self.assertEqual(
            {
                "name": f"{TARGET}/special",
                "x": -128,
                "y": -128,
                "scale": 6,
                "smoothing": False,
            },
            frame,
        )
        timeline = wf_dsl.parse_dsl(
            zlib.decompress(files[f"{TARGET}/special.timeline.amf3.deflate"], -15)
        )["tree"]
        self.assertEqual(
            [
                {"name": "special_land", "kind": "pass", "begin": 1, "end": 159},
                {"name": "special_pose", "kind": "once", "begin": 160, "end": 204},
            ],
            timeline["sequences"],
        )
        self.assertEqual([], timeline["circles"])
        self.assertEqual([], timeline["points"])
        self.assertEqual([], timeline["sounds"])

    def test_rejects_count_size_alpha_hash_and_prefix_drift(self):
        self._require_module()
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            cels = self._write_cels(root)
            with self.assertRaisesRegex(ValueError, "exactly 34"):
                compile_special(cels[:-1], target_prefix=TARGET)

            Image.new("RGBA", (63, 64), (1, 2, 3, 255)).save(cels[0])
            with self.assertRaisesRegex(ValueError, "64x64"):
                compile_special(cels, target_prefix=TARGET)

            cels = self._write_cels(root)
            image = Image.open(cels[0]).convert("RGBA")
            image.putpixel((0, 0), (255, 255, 255, 128))
            image.save(cels[0])
            with self.assertRaisesRegex(ValueError, "binary alpha"):
                compile_special(cels, target_prefix=TARGET)

            cels = self._write_cels(root)
            hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in cels]
            hashes[0] = "0" * 64
            with self.assertRaisesRegex(ValueError, "locked SHA-256"):
                compile_special(cels, target_prefix=TARGET, expected_sha256=hashes)

            with self.assertRaisesRegex(ValueError, "target_prefix"):
                compile_special(cels, target_prefix="../outside")


if __name__ == "__main__":
    unittest.main()

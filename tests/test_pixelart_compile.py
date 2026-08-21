import io
import hashlib
import tempfile
import unittest
import zlib
from pathlib import Path

from PIL import Image

import wf_assets
import wf_dsl

try:
    from wf_pixelart_compile import (
        SUMMER_THUNDER_TEMPLATE_SHA256,
        compile_skill_ready_canary,
        compile_summer_thunder_dragon_skill_ready_canary,
    )
except ImportError:
    SUMMER_THUNDER_TEMPLATE_SHA256 = None
    compile_skill_ready_canary = None
    compile_summer_thunder_dragon_skill_ready_canary = None


SOURCE = "character/thunder_dragon/pixelart"
TARGET = "character/cnmod_thunder_dragon_ascendant/pixelart"


def _raw_deflate(tree):
    compressor = zlib.compressobj(level=9, wbits=-15)
    encoded = wf_dsl.encode_amf3(tree)
    return compressor.compress(encoded) + compressor.flush()


def _stored_png(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    return wf_assets.png_encode(stream.getvalue())


def _template_files():
    sheet = Image.new("RGBA", (190, 58), (0, 0, 0, 0))
    sheet.putpixel((0, 0), (255, 255, 255, 255))
    ticks = [tick for tick in range(1, 134) if tick != 51]
    atlas = [
        {
            "n": f"{SOURCE}/pixelart{tick:04d}",
            "w": 1,
            "h": 1,
            "x": 0,
            "y": 0,
            "fx": -128,
            "fy": -128,
            "fw": 256,
            "fh": 256,
        }
        for tick in ticks
    ]
    frame = {
        "name": f"{SOURCE}/pixelart",
        "x": -128,
        "y": -128,
        "scale": 6,
        "smoothing": False,
    }
    sequences = [
        ("neutral", "loop", 1, 2),
        ("walk_back", "loop", 3, 26),
        ("walk_front", "loop", 27, 50),
        ("skill_ready", "once", 51, 110),
        ("kachidoki", "loop", 111, 158),
        ("into_coffin", "pass", 159, 200),
        ("ghost_raise", "pass", 201, 225),
        ("ghost_neutral", "loop", 226, 386),
        ("revive", "once", 387, 428),
    ]
    timeline = {
        "sequences": [
            {"name": name, "kind": kind, "begin": begin, "end": end}
            for name, kind, begin, end in sequences
        ],
        "circles": [{"path": "unit_body", "frames": []}],
        "points": [{"path": "hp_gauge", "frames": []}],
        "sounds": [],
    }
    return {
        f"{SOURCE}/sprite_sheet.png": _stored_png(sheet),
        f"{SOURCE}/sprite_sheet.atlas.amf3.deflate": _raw_deflate(atlas),
        f"{SOURCE}/pixelart.frame.amf3.deflate": _raw_deflate(frame),
        f"{SOURCE}/pixelart.timeline.amf3.deflate": _raw_deflate(timeline),
    }, timeline


class PixelArtCompileTests(unittest.TestCase):
    def _require_module(self):
        if compile_skill_ready_canary is None:
            self.fail("wf_pixelart_compile is missing")

    def _write_cels(self, root):
        sizes = [(17, 17), (37, 37), (48, 48), (52, 52), (52, 52),
                 (52, 52), (48, 48), (37, 37), (17, 17)]
        paths = []
        for index, (width, height) in enumerate(sizes):
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            left = (64 - width) // 2
            top = (64 - height) // 2
            color = (20 + index, 100, 200, 255)
            for y in range(top, top + height):
                for x in range(left, left + width):
                    image.putpixel((x, y), color)
            path = root / f"cel_{index}.png"
            image.save(path)
            paths.append(path)
        return paths

    def test_canary_builds_exact_four_file_133_record_sprite(self):
        self._require_module()
        template, expected_timeline = _template_files()
        with tempfile.TemporaryDirectory() as temporary_name:
            cels = self._write_cels(Path(temporary_name))
            files, report = compile_skill_ready_canary(
                template,
                cels,
                source_prefix=SOURCE,
                target_prefix=TARGET,
            )
            files_again, report_again = compile_skill_ready_canary(
                template,
                cels,
                source_prefix=SOURCE,
                target_prefix=TARGET,
            )
            sources = [Image.open(path).convert("RGBA") for path in cels]

        self.assertEqual(files, files_again)
        self.assertEqual(report, report_again)
        self.assertEqual(
            {
                f"{TARGET}/sprite_sheet.png",
                f"{TARGET}/sprite_sheet.atlas.amf3.deflate",
                f"{TARGET}/pixelart.frame.amf3.deflate",
                f"{TARGET}/pixelart.timeline.amf3.deflate",
            },
            set(files),
        )
        self.assertFalse(report["writes_live"])
        self.assertFalse(report["package_manifest_eligible"])
        self.assertEqual(122, report["official_passthrough_atlas_records"])
        self.assertEqual(8, len(report["official_passthrough_actions"]))

        for logical, payload in files.items():
            if not logical.endswith(".amf3.deflate"):
                continue
            decompressor = zlib.decompressobj(-15)
            decompressor.decompress(payload)
            decompressor.flush()
            self.assertTrue(decompressor.eof, logical)
            self.assertEqual(b"", decompressor.unused_data, logical)
            self.assertEqual(b"", decompressor.unconsumed_tail, logical)

        decoded_png = wf_assets.png_decode(files[f"{TARGET}/sprite_sheet.png"])
        self.assertEqual((256, 166), wf_assets.png_dims(decoded_png))
        with Image.open(io.BytesIO(decoded_png)) as opened:
            sheet = opened.convert("RGBA")

        atlas = wf_dsl.parse_dsl(zlib.decompress(
            files[f"{TARGET}/sprite_sheet.atlas.amf3.deflate"], -15
        ))["tree"]
        self.assertEqual(133, len(atlas))
        self.assertEqual(133, len({entry["n"] for entry in atlas}))
        self.assertTrue(all(entry["n"].startswith(TARGET + "/") for entry in atlas))
        ticks = [int(entry["n"].rsplit("pixelart", 1)[1]) for entry in atlas]
        self.assertEqual(sorted(ticks), ticks)

        expected_positions = {
            51: (1, 59), 56: (20, 59), 62: (59, 59), 68: (109, 59),
            74: (163, 59), 80: (1, 113), 86: (55, 113),
            92: (105, 113), 98: (144, 113), 104: (144, 113),
            110: (144, 113),
        }
        by_tick = {int(entry["n"].rsplit("pixelart", 1)[1]): entry for entry in atlas}
        for tick, position in expected_positions.items():
            self.assertEqual(position, (by_tick[tick]["x"], by_tick[tick]["y"]))
            self.assertEqual((256, 256), (by_tick[tick]["fw"], by_tick[tick]["fh"]))
            self.assertLessEqual(by_tick[tick]["x"] + by_tick[tick]["w"], sheet.width)
            self.assertLessEqual(by_tick[tick]["y"] + by_tick[tick]["h"], sheet.height)

        for index, tick in enumerate((51, 56, 62, 68, 74, 80, 86, 92, 98)):
            entry = by_tick[tick]
            rebuilt = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            crop = sheet.crop((entry["x"], entry["y"],
                               entry["x"] + entry["w"], entry["y"] + entry["h"]))
            rebuilt.alpha_composite(crop, (-entry["fx"], -entry["fy"]))
            expected = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            expected.alpha_composite(sources[index], (96, 96))
            self.assertEqual(expected.tobytes(), rebuilt.tobytes(), tick)

        frame = wf_dsl.parse_dsl(zlib.decompress(
            files[f"{TARGET}/pixelart.frame.amf3.deflate"], -15
        ))["tree"]
        self.assertEqual(
            {"name": f"{TARGET}/pixelart", "x": -128, "y": -128,
             "scale": 6, "smoothing": False},
            frame,
        )
        timeline = wf_dsl.parse_dsl(zlib.decompress(
            files[f"{TARGET}/pixelart.timeline.amf3.deflate"], -15
        ))["tree"]
        self.assertEqual(expected_timeline, timeline)

    def test_rejects_wrong_count_size_soft_alpha_and_locked_hash_drift(self):
        self._require_module()
        template, _ = _template_files()
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            cels = self._write_cels(root)
            with self.assertRaisesRegex(ValueError, "exactly 9"):
                compile_skill_ready_canary(
                    template, cels[:8], source_prefix=SOURCE, target_prefix=TARGET
                )
            Image.new("RGBA", (63, 64), (1, 2, 3, 255)).save(cels[0])
            with self.assertRaisesRegex(ValueError, "64x64"):
                compile_skill_ready_canary(
                    template, cels, source_prefix=SOURCE, target_prefix=TARGET
                )
            cels = self._write_cels(root)
            image = Image.open(cels[0]).convert("RGBA")
            image.putpixel((0, 0), (255, 255, 255, 128))
            image.save(cels[0])
            with self.assertRaisesRegex(ValueError, "binary alpha"):
                compile_skill_ready_canary(
                    template, cels, source_prefix=SOURCE, target_prefix=TARGET
                )
            cels = self._write_cels(root)
            with self.assertRaisesRegex(ValueError, "locked SHA-256"):
                compile_summer_thunder_dragon_skill_ready_canary(template, cels)

    def test_locks_template_identity_and_rejects_passthrough_out_of_bounds(self):
        self._require_module()
        expected_locked_hashes = {
            f"{SOURCE}/sprite_sheet.png": (
                "578f26226ae4681d51719e3d00640cad01b7a24b0c03222c51643bcd6b79cf28"
            ),
            f"{SOURCE}/sprite_sheet.atlas.amf3.deflate": (
                "76ca593252886f19ac8f8c9cd086d06ed4291eddd557a7a3fc6924fded395939"
            ),
            f"{SOURCE}/pixelart.frame.amf3.deflate": (
                "d2e6a74036fec03f04948b539a11adb742b9a848012fbf0251ad746c351adc1e"
            ),
            f"{SOURCE}/pixelart.timeline.amf3.deflate": (
                "23bee417315db0b49fa4bd87d62af39682a3ce9dd07b1409e01bf1c813232d8b"
            ),
        }
        self.assertEqual(expected_locked_hashes, SUMMER_THUNDER_TEMPLATE_SHA256)

        template, _ = _template_files()
        synthetic_hashes = {
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in template.items()
        }
        with tempfile.TemporaryDirectory() as temporary_name:
            cels = self._write_cels(Path(temporary_name))
            compile_skill_ready_canary(
                template,
                cels,
                source_prefix=SOURCE,
                target_prefix=TARGET,
                expected_template_sha256=synthetic_hashes,
            )

            drifted = dict(template)
            changed_sheet = Image.new("RGBA", (190, 58), (0, 0, 0, 0))
            changed_sheet.putpixel((1, 0), (255, 255, 255, 255))
            drifted[f"{SOURCE}/sprite_sheet.png"] = _stored_png(changed_sheet)
            with self.assertRaisesRegex(ValueError, "locked SHA-256"):
                compile_skill_ready_canary(
                    drifted,
                    cels,
                    source_prefix=SOURCE,
                    target_prefix=TARGET,
                    expected_template_sha256=synthetic_hashes,
                )

            invalid = dict(template)
            atlas_logical = f"{SOURCE}/sprite_sheet.atlas.amf3.deflate"
            atlas = wf_dsl.parse_dsl(zlib.decompress(invalid[atlas_logical], -15))["tree"]
            atlas[0]["x"] = 9999
            invalid[atlas_logical] = _raw_deflate(atlas)
            with self.assertRaisesRegex(ValueError, "out of bounds"):
                compile_skill_ready_canary(
                    invalid,
                    cels,
                    source_prefix=SOURCE,
                    target_prefix=TARGET,
                )


if __name__ == "__main__":
    unittest.main()

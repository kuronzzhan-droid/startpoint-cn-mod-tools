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
    from wf_pixelart_normal_compile import (
        FULL_NORMAL_SLOT_SIZES,
        TEMPLATE_TICKS,
        compile_full_normal,
    )
except ImportError:
    FULL_NORMAL_SLOT_SIZES = None
    TEMPLATE_TICKS = None
    compile_full_normal = None


SOURCE = "character/thunder_dragon/pixelart"
TARGET = "character/cnmod_thunder_dragon_ascendant/pixelart"
SEQUENCES = (
    ("neutral", "loop", 1, 2),
    ("walk_back", "loop", 3, 26),
    ("walk_front", "loop", 27, 50),
    ("skill_ready", "once", 51, 110),
    ("kachidoki", "loop", 111, 158),
    ("into_coffin", "pass", 159, 200),
    ("ghost_raise", "pass", 201, 225),
    ("ghost_neutral", "loop", 226, 386),
    ("revive", "once", 387, 428),
)


def _raw_deflate(tree):
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush()


def _stored_png(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    return wf_assets.png_encode(stream.getvalue())


def _template_files():
    sheet = Image.new("RGBA", (190, 58), (0, 0, 0, 0))
    sheet.putpixel((0, 0), (255, 0, 0, 255))
    atlas = []
    for tick in TEMPLATE_TICKS:
        entry = {
            "n": f"{SOURCE}/pixelart{tick:04d}",
            "w": 3,
            "h": 3,
            "x": 0,
            "y": 0,
            "fx": -128,
            "fy": -128,
            "fw": 256,
            "fh": 256,
        }
        if tick in {2, 8, 14, 20, 26, 32, 38, 44, 50}:
            entry["fx"] = -120
            entry["fy"] = -112 + (tick % 2)
        atlas.append(entry)
    frame = {
        "name": f"{SOURCE}/pixelart",
        "x": -128,
        "y": -128,
        "scale": 6,
        "smoothing": False,
    }
    timeline = {
        "sequences": [
            {"name": name, "kind": kind, "begin": begin, "end": end}
            for name, kind, begin, end in SEQUENCES
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


class FullNormalPixelArtCompileTests(unittest.TestCase):
    def _require_module(self):
        if compile_full_normal is None:
            self.fail("wf_pixelart_normal_compile is missing")

    def _write_cels(self, root):
        paths = {}
        for index, (slot, size) in enumerate(FULL_NORMAL_SLOT_SIZES.items()):
            image = Image.new("RGBA", size, (0, 0, 0, 0))
            left = size[0] // 2 - 1
            top = size[1] // 2 - 1
            color = (10 + index, 80 + index, 150 + index, 255)
            for y in range(top, top + 3):
                for x in range(left, left + 3):
                    image.putpixel((x, y), color)
            path = root / f"{slot}.png"
            image.save(path, format="PNG", optimize=False)
            paths[slot] = path
        return paths

    def test_compiles_all_nine_actions_without_template_pixel_passthrough(self):
        self._require_module()
        template, expected_timeline = _template_files()
        with tempfile.TemporaryDirectory() as temporary_name:
            cels = self._write_cels(Path(temporary_name))
            files, report = compile_full_normal(
                template,
                cels,
                source_prefix=SOURCE,
                target_prefix=TARGET,
            )
            files_again, report_again = compile_full_normal(
                template,
                cels,
                source_prefix=SOURCE,
                target_prefix=TARGET,
            )
            expected_bases = {
                2: Image.open(cels["base_0002"]).convert("RGBA"),
                8: Image.open(cels["base_0008"]).convert("RGBA"),
            }

        self.assertEqual(files, files_again)
        self.assertEqual(report, report_again)
        self.assertFalse(report["writes_live"])
        self.assertTrue(report["package_manifest_eligible"])
        self.assertEqual([], report["official_passthrough_actions"])
        self.assertEqual(0, report["official_passthrough_atlas_records"])
        self.assertEqual(9, report["sequence_count"])
        self.assertEqual(428, report["timeline_ticks"])
        self.assertEqual(134, report["atlas_records"])
        self.assertEqual(set(FULL_NORMAL_SLOT_SIZES), set(report["input_sha256"]))

        png_logical = f"{TARGET}/sprite_sheet.png"
        decoded_png = wf_assets.png_decode(files[png_logical])
        with Image.open(io.BytesIO(decoded_png)) as opened:
            sheet = opened.convert("RGBA")
        self.assertNotIn((255, 0, 0, 255), set(sheet.get_flattened_data()))

        atlas = wf_dsl.parse_dsl(
            zlib.decompress(files[f"{TARGET}/sprite_sheet.atlas.amf3.deflate"], -15)
        )["tree"]
        self.assertEqual(134, len(atlas))
        self.assertEqual(134, len({entry["n"] for entry in atlas}))
        self.assertTrue(all(entry["n"].startswith(TARGET + "/") for entry in atlas))
        ticks = [int(entry["n"].rsplit("pixelart", 1)[1]) for entry in atlas]
        self.assertEqual(sorted((*TEMPLATE_TICKS, 51, 111)), ticks)

        by_tick = {int(entry["n"].rsplit("pixelart", 1)[1]): entry for entry in atlas}
        template_atlas = wf_dsl.parse_dsl(
            zlib.decompress(template[f"{SOURCE}/sprite_sheet.atlas.amf3.deflate"], -15)
        )["tree"]
        template_by_tick = {
            int(entry["n"].rsplit("pixelart", 1)[1]): entry for entry in template_atlas
        }
        for tick, expected_base in expected_bases.items():
            entry = by_tick[tick]
            rebuilt = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            crop = sheet.crop(
                (
                    entry["x"],
                    entry["y"],
                    entry["x"] + entry["w"],
                    entry["y"] + entry["h"],
                )
            )
            rebuilt.alpha_composite(crop, (-entry["fx"], -entry["fy"]))
            expected = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            donor = template_by_tick[tick]
            expected.alpha_composite(
                expected_base.crop(expected_base.getchannel("A").getbbox()),
                (-donor["fx"], -donor["fy"]),
            )
            self.assertEqual(expected.tobytes(), rebuilt.tobytes(), f"tick {tick}")

        self.assertEqual(9, report["official_anchor_records"])
        self.assertEqual("base_0002", report["atlas_tick_slots"]["32"])
        for tick in (2, 8, 14, 20, 26, 32, 38, 44, 50):
            self.assertEqual(template_by_tick[tick]["fx"], by_tick[tick]["fx"])
            self.assertEqual(template_by_tick[tick]["fy"], by_tick[tick]["fy"])

        frame = wf_dsl.parse_dsl(
            zlib.decompress(files[f"{TARGET}/pixelart.frame.amf3.deflate"], -15)
        )["tree"]
        self.assertEqual(f"{TARGET}/pixelart", frame["name"])
        timeline = wf_dsl.parse_dsl(
            zlib.decompress(files[f"{TARGET}/pixelart.timeline.amf3.deflate"], -15)
        )["tree"]
        self.assertEqual(expected_timeline, timeline)

    def test_rejects_slot_size_alpha_hash_and_template_tick_drift(self):
        self._require_module()
        template, _ = _template_files()
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            cels = self._write_cels(root)
            missing = dict(cels)
            missing.pop("ghost_2")
            with self.assertRaisesRegex(ValueError, "slot contract"):
                compile_full_normal(
                    template, missing, source_prefix=SOURCE, target_prefix=TARGET
                )

            Image.new("RGBA", (31, 32), (1, 2, 3, 255)).save(cels["ghost_2"])
            with self.assertRaisesRegex(ValueError, "must be 32x32"):
                compile_full_normal(
                    template, cels, source_prefix=SOURCE, target_prefix=TARGET
                )

            cels = self._write_cels(root)
            image = Image.open(cels["ghost_2"]).convert("RGBA")
            image.putpixel((0, 0), (255, 255, 255, 128))
            image.save(cels["ghost_2"])
            with self.assertRaisesRegex(ValueError, "alpha contract"):
                compile_full_normal(
                    template, cels, source_prefix=SOURCE, target_prefix=TARGET
                )

            cels = self._write_cels(root)
            hashes = {slot: hashlib.sha256(path.read_bytes()).hexdigest() for slot, path in cels.items()}
            hashes["ghost_2"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "locked SHA-256"):
                compile_full_normal(
                    template,
                    cels,
                    source_prefix=SOURCE,
                    target_prefix=TARGET,
                    expected_sha256=hashes,
                )

            drifted = dict(template)
            atlas_logical = f"{SOURCE}/sprite_sheet.atlas.amf3.deflate"
            atlas = wf_dsl.parse_dsl(zlib.decompress(drifted[atlas_logical], -15))["tree"]
            atlas.pop()
            drifted[atlas_logical] = _raw_deflate(atlas)
            with self.assertRaisesRegex(ValueError, "132 records"):
                compile_full_normal(
                    drifted, cels, source_prefix=SOURCE, target_prefix=TARGET
                )


if __name__ == "__main__":
    unittest.main()

import hashlib
import io
import unittest
import zlib

from PIL import Image

import wf_assets
import wf_dsl
from wf_pixelart_compile import _encode_png, _raw_deflate

try:
    import wf_pixelart_special_compat_compile as compat_compile
except ImportError:
    compat_compile = None

compile_special_compatibility = (
    getattr(compat_compile, "compile_special_compatibility", None)
    if compat_compile is not None
    else None
)
compile_summer_thunder_dragon_special_compatibility = (
    getattr(compat_compile, "compile_summer_thunder_dragon_special_compatibility", None)
    if compat_compile is not None
    else None
)


TARGET = "character/cnmod_thunder_dragon_ascendant/pixelart"
NORMAL_TICKS = (
    2, 8, 14, 20, 26, 32, 38, 44, 50,
    51, 56, 62, 68, 74, 80, 86, 92, 98, 104, 110,
    111, 116, 122, 152, 158,
    *range(159, 219),
    225, 255, 275, 285, 305, 335, 355, 386,
    *range(387, 427),
    428,
)
def _decode_amf(payload):
    return wf_dsl.parse_dsl(zlib.decompress(payload, -15))["tree"]


class SpecialCompatibilityCompileTests(unittest.TestCase):
    def _require_module(self):
        if compile_special_compatibility is None:
            self.fail("wf_pixelart_special_compat_compile is missing")

    def _normal_files(self):
        self.assertEqual(134, len(NORMAL_TICKS))
        sheet = Image.new("RGBA", (256, 4), (0, 0, 0, 0))
        atlas = []
        for index, tick in enumerate(NORMAL_TICKS):
            sheet.putpixel((index, 0), ((index * 13 + 1) % 256, 70, 180, 255))
            atlas.append(
                {
                    "n": f"{TARGET}/pixelart{tick:04d}",
                    "x": index,
                    "y": 0,
                    "w": 1,
                    "h": 1,
                    "fx": -127,
                    "fy": -127,
                    "fw": 256,
                    "fh": 256,
                }
            )
        timeline = {
            "sequences": [
                {"name": "skill_ready", "kind": "once", "begin": 51, "end": 110},
                {"name": "kachidoki", "kind": "once", "begin": 111, "end": 158},
            ],
            "circles": [],
            "points": [],
            "sounds": [],
        }
        files = {
            f"{TARGET}/sprite_sheet.png": _encode_png(sheet),
            f"{TARGET}/sprite_sheet.atlas.amf3.deflate": _raw_deflate(
                wf_dsl.encode_amf3(atlas)
            ),
            f"{TARGET}/pixelart.frame.amf3.deflate": _raw_deflate(
                wf_dsl.encode_amf3(
                    {
                        "name": f"{TARGET}/pixelart",
                        "x": -128,
                        "y": -128,
                        "scale": 6,
                        "smoothing": False,
                    }
                )
            ),
            f"{TARGET}/pixelart.timeline.amf3.deflate": _raw_deflate(
                wf_dsl.encode_amf3(timeline)
            ),
        }
        return files, atlas

    def test_aliases_every_normal_atlas_record_into_real_special_contract(self):
        self._require_module()
        normal_files, normal_atlas = self._normal_files()
        expected_sha256 = {
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in normal_files.items()
        }

        files, report = compile_special_compatibility(
            normal_files,
            target_prefix=TARGET,
            expected_normal_sha256=expected_sha256,
        )
        files_again, report_again = compile_special_compatibility(
            normal_files,
            target_prefix=TARGET,
            expected_normal_sha256=expected_sha256,
        )

        self.assertEqual(files, files_again)
        self.assertEqual(report, report_again)
        self.assertEqual(
            normal_files[f"{TARGET}/sprite_sheet.png"],
            files[f"{TARGET}/special_sprite_sheet.png"],
        )
        self.assertEqual(0, report["new_art_pixels"])
        self.assertTrue(report["png_byte_identical_to_normal"])
        self.assertTrue(report["all_atlas_geometry_from_normal"])
        self.assertFalse(report["writes_live"])
        self.assertFalse(report["package_manifest_eligible"])
        self.assertFalse(report["locked_summer_thunder_normal_v3"])
        self.assertEqual(len(NORMAL_TICKS), report["atlas_records"])
        self.assertEqual(158, report["timeline_ticks"])

        atlas = _decode_amf(
            files[f"{TARGET}/special_sprite_sheet.atlas.amf3.deflate"]
        )
        self.assertEqual(
            [f"{TARGET}/special{tick:04d}" for tick in NORMAL_TICKS],
            [entry["n"] for entry in atlas],
        )
        self.assertFalse(any("/pixelart" in entry["n"].rsplit("/", 1)[-1] for entry in atlas))
        by_tick = {
            int(entry["n"].rsplit("pixelart", 1)[1]): entry
            for entry in normal_atlas
        }
        self.assertEqual(
            list(NORMAL_TICKS),
            [row["source_normal_tick"] for row in report["special_key_mappings"]],
        )
        for special_entry, mapping in zip(atlas, report["special_key_mappings"], strict=True):
            source = by_tick[mapping["source_normal_tick"]]
            self.assertEqual(
                {key: source[key] for key in ("x", "y", "w", "h", "fx", "fy", "fw", "fh")},
                {key: special_entry[key] for key in ("x", "y", "w", "h", "fx", "fy", "fw", "fh")},
            )
            self.assertEqual("identity", mapping["transform"])
            self.assertRegex(mapping["source_crop_pixel_sha256"], r"^[0-9a-f]{64}$")

        frame = _decode_amf(files[f"{TARGET}/special.frame.amf3.deflate"])
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
        timeline = _decode_amf(files[f"{TARGET}/special.timeline.amf3.deflate"])
        self.assertEqual(
            [
                {"name": "special_land", "kind": "pass", "begin": 51, "end": 110},
                {"name": "special_pose", "kind": "once", "begin": 111, "end": 158},
            ],
            timeline["sequences"],
        )
        self.assertNotIn("skill_ready", {row["name"] for row in timeline["sequences"]})
        self.assertNotIn("kachidoki", {row["name"] for row in timeline["sequences"]})

        decoded_normal = wf_assets.png_decode(normal_files[f"{TARGET}/sprite_sheet.png"])
        decoded_special = wf_assets.png_decode(files[f"{TARGET}/special_sprite_sheet.png"])
        self.assertEqual(decoded_normal, decoded_special)

    def test_rejects_hash_sequence_and_source_key_drift(self):
        self._require_module()
        normal_files, _ = self._normal_files()
        expected_sha256 = {
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in normal_files.items()
        }
        with self.assertRaisesRegex(ValueError, "normal SHA-256 lock is required"):
            compile_special_compatibility(normal_files, target_prefix=TARGET)

        expected_sha256[f"{TARGET}/sprite_sheet.png"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "normal SHA-256"):
            compile_special_compatibility(
                normal_files,
                target_prefix=TARGET,
                expected_normal_sha256=expected_sha256,
            )

        timeline_logical = f"{TARGET}/pixelart.timeline.amf3.deflate"
        bad_timeline = {
            "sequences": [
                {"name": "skill_ready", "kind": "once", "begin": 51, "end": 109},
                {"name": "kachidoki", "kind": "once", "begin": 111, "end": 158},
            ],
            "circles": [],
            "points": [],
            "sounds": [],
        }
        normal_files[timeline_logical] = _raw_deflate(wf_dsl.encode_amf3(bad_timeline))
        expected_sha256 = {
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in normal_files.items()
        }
        with self.assertRaisesRegex(ValueError, "skill_ready.*51..110"):
            compile_special_compatibility(
                normal_files,
                target_prefix=TARGET,
                expected_normal_sha256=expected_sha256,
            )

        normal_files, normal_atlas = self._normal_files()
        atlas_logical = f"{TARGET}/sprite_sheet.atlas.amf3.deflate"
        normal_files[atlas_logical] = _raw_deflate(wf_dsl.encode_amf3(normal_atlas[:-1]))
        expected_sha256 = {
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in normal_files.items()
        }
        with self.assertRaisesRegex(ValueError, "exactly 134"):
            compile_special_compatibility(
                normal_files,
                target_prefix=TARGET,
                expected_normal_sha256=expected_sha256,
            )

    def test_production_wrapper_rejects_non_locked_synthetic_normal(self):
        self._require_module()
        if compile_summer_thunder_dragon_special_compatibility is None:
            self.fail("production hash-locked summer thunder compatibility wrapper is missing")
        normal_files, _ = self._normal_files()
        with self.assertRaisesRegex(ValueError, "normal SHA-256 drift"):
            compile_summer_thunder_dragon_special_compatibility(normal_files)


if __name__ == "__main__":
    unittest.main()

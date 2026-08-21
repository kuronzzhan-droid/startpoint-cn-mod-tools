import hashlib
import io
import unittest
import zlib
from pathlib import Path
from unittest import mock

from PIL import Image, ImageChops, ImageDraw

import wf_assets
import wf_atf
import wf_dsl
import wf_character_ui_compile as ui_compile
from wf_character_ui_compile import (
    SUMMER_THUNDER_CROP_BOXES,
    SUMMER_THUNDER_MASTER_SHA256,
    SUMMER_THUNDER_SHAPE_MASK_SHA256,
    compile_cutin_atf_assets,
    compile_summer_thunder_dragon_ui_assets,
    compile_ui_png_assets,
)


SOURCE = "character/thunder_dragon"
TARGET = "character/cnmod_thunder_dragon_ascendant"
ACCEPTED_PORTRAIT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "work"
    / "builds"
    / "cnmod_thunder_dragon_ascendant"
    / "art"
    / "portraits"
    / "accepted_v1"
)
ACCEPTED_PORTRAIT_PATHS = {
    0: ACCEPTED_PORTRAIT_ROOT / "summer_thunder_dragon_unawakened.png",
    1: ACCEPTED_PORTRAIT_ROOT / "summer_thunder_dragon_awakened.png",
}
HAS_LOCAL_ACCEPTED_PORTRAITS = all(
    path.is_file() for path in ACCEPTED_PORTRAIT_PATHS.values()
)

ASSET_KEYS = (
    "skill_cutin",
    "square_212",
    "square_132",
    "round_95",
    "round_136",
    "level_up",
    "party_main",
    "party_unison",
    "control_board",
    "member_status",
    "chain",
)


def _png_bytes(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    return stream.getvalue()


def _raw_deflate(tree):
    compressor = zlib.compressobj(level=9, wbits=-15)
    encoded = wf_dsl.encode_amf3(tree)
    return compressor.compress(encoded) + compressor.flush()


def _masters():
    output = {}
    for form, color in ((0, (255, 80, 20, 255)), (1, (20, 160, 255, 255))):
        image = Image.new("RGBA", (16, 20), (0, 0, 0, 0))
        for y in range(2, 19):
            for x in range(2 + form, 15):
                image.putpixel((x, y), color)
        output[form] = _png_bytes(image)
    return output


def _boxes():
    dimensions = {
        "skill_cutin": (12, 6),
        "square_212": (8, 8),
        "square_132": (8, 8),
        "round_95": (8, 8),
        "round_136": (8, 8),
        "level_up": (6, 8),
        "party_main": (4, 8),
        "party_unison": (6, 8),
        "control_board": (4, 8),
        "member_status": (6, 6),
        "chain": (6, 8),
    }
    output = {}
    for form in (0, 1):
        output[form] = {}
        for key, (width, height) in dimensions.items():
            left = 2 + form
            top = 2
            output[form][key] = (left, top, left + width, top + height)
    return output


def _sizes():
    return {
        "skill_cutin": (8, 4),
        "square_212": (6, 6),
        "square_132": (6, 6),
        "round_95": (6, 6),
        "round_136": (6, 6),
        "level_up": (6, 8),
        "party_main": (4, 8),
        "party_unison": (6, 8),
        "control_board": (4, 8),
        "member_status": (4, 4),
        "chain": (6, 8),
    }


def _donor_atlas():
    return _raw_deflate([
        {
            "n": f"{SOURCE}/ui/full_shot_illustration_setting_0",
            "w": 6,
            "h": 5,
            "x": 0,
            "y": 0,
            "fx": -1,
            "fy": -1,
            "fw": 8,
            "fh": 8,
        },
        {
            "n": f"{SOURCE}/ui/full_shot_illustration_setting_1",
            "w": 6,
            "h": 5,
            "x": 0,
            "y": 6,
            "fx": -1,
            "fy": -1,
            "fw": 8,
            "fh": 8,
        },
    ])


def _shape_masks():
    output = {}
    for key in (
        "round_95", "round_136", "level_up", "party_main", "party_unison",
        "control_board", "member_status", "chain",
    ):
        image = Image.new("RGBA", _sizes()[key], (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        width, height = image.size
        if key in {
            "round_95", "round_136", "level_up", "party_main",
            "party_unison", "member_status",
        }:
            draw.rounded_rectangle(
                (1, 1, width - 2, height - 2),
                radius=max(1, min(width, height) // 4),
                fill=(255, 255, 255, 255),
            )
        else:
            draw.polygon(
                ((width // 2, 0), (width - 1, height // 4),
                 (width - 2, height - 2), (1, height - 2),
                 (0, height // 4)),
                fill=(255, 255, 255, 255),
            )
        output[key] = wf_assets.png_encode(_png_bytes(image))
    return output


def _accepted_masters():
    missing = [
        str(path)
        for path in ACCEPTED_PORTRAIT_PATHS.values()
        if not path.is_file()
    ]
    if missing:
        raise AssertionError(f"locked accepted portraits are missing: {missing}")
    return {
        form: path.read_bytes()
        for form, path in ACCEPTED_PORTRAIT_PATHS.items()
    }


def _opaque_shape_masks(sizes):
    return {
        key: wf_assets.png_encode(
            _png_bytes(Image.new("RGBA", sizes[key], (255, 255, 255, 255)))
        )
        for key in (
            "round_95", "round_136", "level_up", "party_main",
            "party_unison", "control_board", "member_status", "chain",
        )
    }


def _stub_cutin_atfs(_png_files, _donor_atfs, *, target_prefix, **_kwargs):
    files = {
        f"{target_prefix}/ui/skill_cutin_{form}.atf.deflate": b"test-atf"
        for form in (0, 1)
    }
    return files, {
        "schema_version": 1,
        "writes_live": False,
        "package_manifest_eligible": False,
        "target_prefix": target_prefix,
        "atf_count": 2,
    }


class CharacterUiCompileTests(unittest.TestCase):
    def _require_module(self):
        self.assertTrue(callable(compile_ui_png_assets))

    def test_compiles_26_png_and_atlas_assets_with_per_form_boxes(self):
        self._require_module()
        shape_masks = _shape_masks()
        files, report = compile_ui_png_assets(
            _masters(),
            _boxes(),
            _sizes(),
            _donor_atlas(),
            shape_masks=shape_masks,
            source_prefix=SOURCE,
            target_prefix=TARGET,
        )
        self.assertEqual(files, compile_ui_png_assets(
            _masters(), _boxes(), _sizes(), _donor_atlas(),
            shape_masks=_shape_masks(),
            source_prefix=SOURCE, target_prefix=TARGET,
        )[0])
        self.assertEqual(26, len(files))
        self.assertFalse(report["writes_live"])
        self.assertFalse(report["package_manifest_eligible"])
        self.assertEqual(25, report["png_count"])

        expected_pngs = {
            f"{TARGET}/ui/full_shot_1440_1920_{form}.png"
            for form in (0, 1)
        }
        for form in (0, 1):
            expected_pngs.update({
                f"{TARGET}/ui/{name}_{form}.png"
                for name in (
                    "skill_cutin", "square", "square_132_132",
                    "square_round_95_95", "square_round_136_136",
                    "thumb_level_up", "thumb_party_main",
                    "thumb_party_unison", "battle_control_board",
                    "battle_member_status", "cutin_skill_chain",
                )
            })
        expected_pngs.add(
            f"{TARGET}/ui/illustration_setting_sprite_sheet.png"
        )
        self.assertEqual(expected_pngs, {
            logical for logical in files if logical.endswith(".png")
        })

        for logical in expected_pngs:
            self.assertEqual(wf_assets.PNG_FAKE, files[logical][:8], logical)
        for form in (0, 1):
            logical = f"{TARGET}/ui/full_shot_1440_1920_{form}.png"
            with Image.open(io.BytesIO(wf_assets.png_decode(files[logical]))) as image:
                self.assertEqual((16, 20), image.size)
            cutin = f"{TARGET}/ui/skill_cutin_{form}.png"
            self.assertEqual((8, 4), wf_assets.png_dims(files[cutin]))

        sheet_logical = f"{TARGET}/ui/illustration_setting_sprite_sheet.png"
        self.assertEqual((6, 11), wf_assets.png_dims(files[sheet_logical]))
        atlas_logical = (
            f"{TARGET}/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"
        )
        self.assertEqual(sorted(expected_pngs), report["roots"]["medium"])
        self.assertEqual([atlas_logical], report["roots"]["common"])
        self.assertEqual([], report["roots"]["android"])
        atlas = wf_dsl.parse_dsl(zlib.decompress(files[atlas_logical], -15))["tree"]
        self.assertEqual(2, len(atlas))
        self.assertTrue(all(entry["n"].startswith(TARGET + "/") for entry in atlas))
        self.assertFalse(any(SOURCE in entry["n"] for entry in atlas))

        with Image.open(
            io.BytesIO(wf_assets.png_decode(files[sheet_logical]))
        ) as opened:
            sheet = opened.convert("RGBA")
        masters = _masters()
        boxes = _boxes()
        for form, entry in enumerate(atlas):
            with Image.open(io.BytesIO(masters[form])) as opened:
                source = opened.convert("RGBA")
            full_frame = source.crop(boxes[form]["square_212"]).resize(
                (entry["fw"], entry["fh"]), Image.Resampling.LANCZOS
            )
            expected_cell = full_frame.crop(
                (
                    -entry["fx"],
                    -entry["fy"],
                    -entry["fx"] + entry["w"],
                    -entry["fy"] + entry["h"],
                )
            )
            actual_cell = sheet.crop(
                (
                    entry["x"],
                    entry["y"],
                    entry["x"] + entry["w"],
                    entry["y"] + entry["h"],
                )
            )
            self.assertEqual(expected_cell.tobytes(), actual_cell.tobytes())

        masked_names = {
            "round_95": "square_round_95_95",
            "round_136": "square_round_136_136",
            "level_up": "thumb_level_up",
            "party_main": "thumb_party_main",
            "party_unison": "thumb_party_unison",
            "control_board": "battle_control_board",
            "member_status": "battle_member_status",
            "chain": "cutin_skill_chain",
        }
        decoded_masks = {}
        for key, payload in shape_masks.items():
            with Image.open(io.BytesIO(wf_assets.png_decode(payload))) as opened:
                decoded_masks[key] = opened.convert("RGBA").getchannel("A")
        for form in (0, 1):
            for key, name in masked_names.items():
                logical = f"{TARGET}/ui/{name}_{form}.png"
                with Image.open(io.BytesIO(wf_assets.png_decode(files[logical]))) as image:
                    rgba = image.convert("RGBA")
                self.assertIsNone(
                    ImageChops.subtract(
                        rgba.getchannel("A"), decoded_masks[key]
                    ).getbbox(),
                    logical,
                )
                self.assertEqual(0, rgba.getpixel((0, 0))[3], logical)
                center = rgba.getpixel((rgba.width // 2, rgba.height // 2))
                self.assertEqual(255, center[3], logical)
                self.assertNotEqual((255, 255, 255), center[:3], logical)
                for red, green, blue, alpha in rgba.get_flattened_data():
                    if alpha == 0:
                        self.assertEqual((0, 0, 0), (red, green, blue), logical)

    def test_builds_two_parseable_cutin_atfs(self):
        self._require_module()
        png_files, _ = compile_ui_png_assets(
            _masters(), _boxes(), _sizes(), _donor_atlas(),
            shape_masks=_shape_masks(),
            source_prefix=SOURCE, target_prefix=TARGET,
        )
        references = {}
        for form in (0, 1):
            logical = f"{TARGET}/ui/skill_cutin_{form}.png"
            standard_png = wf_assets.png_decode(png_files[logical])
            references[form] = wf_atf.deflate(wf_atf.build_cutin_atf(standard_png))
        files, report = compile_cutin_atf_assets(
            png_files, references, target_prefix=TARGET
        )
        self.assertEqual(2, len(files))
        self.assertEqual(2, report["atf_count"])
        for form in (0, 1):
            logical = f"{TARGET}/ui/skill_cutin_{form}.atf.deflate"
            parsed = wf_atf.parse_atf(zlib.decompress(files[logical], -15))
            self.assertEqual((8, 4, 4), (parsed["w"], parsed["h"], parsed["mips"]))

    def test_locked_wrapper_threads_every_identity_hash_and_rejects_mask_drift(self):
        self._require_module()
        masters = _masters()
        donor_atlas = _donor_atlas()
        shape_masks = _shape_masks()
        donor_atfs = {}
        for form, color in ((0, (255, 80, 20, 255)), (1, (20, 160, 255, 255))):
            reference_png = _png_bytes(Image.new("RGBA", (8, 4), color))
            donor_atfs[form] = wf_atf.deflate(
                wf_atf.build_cutin_atf(reference_png)
            )
        master_hashes = {
            form: hashlib.sha256(payload).hexdigest()
            for form, payload in masters.items()
        }
        mask_hashes = {
            key: hashlib.sha256(payload).hexdigest()
            for key, payload in shape_masks.items()
        }
        atf_hashes = {
            form: hashlib.sha256(payload).hexdigest()
            for form, payload in donor_atfs.items()
        }
        locks = (
            mock.patch.object(ui_compile, "SUMMER_THUNDER_CROP_BOXES", _boxes()),
            mock.patch.object(ui_compile, "SUMMER_THUNDER_UI_SIZES", _sizes()),
            mock.patch.object(ui_compile, "SUMMER_THUNDER_MASTER_SHA256", master_hashes),
            mock.patch.object(
                ui_compile,
                "SUMMER_THUNDER_DONOR_ATLAS_SHA256",
                hashlib.sha256(donor_atlas).hexdigest(),
            ),
            mock.patch.object(ui_compile, "SUMMER_THUNDER_DONOR_ATF_SHA256", atf_hashes),
            mock.patch.object(ui_compile, "SUMMER_THUNDER_SHAPE_MASK_SHA256", mask_hashes),
        )
        with locks[0], locks[1], locks[2], locks[3], locks[4], locks[5]:
            files, report = compile_summer_thunder_dragon_ui_assets(
                masters, donor_atlas, donor_atfs, shape_masks
            )
            self.assertEqual(28, len(files))
            self.assertFalse(report["writes_live"])
            drifted = dict(shape_masks)
            drifted["round_95"] += b"\x00"
            with self.assertRaisesRegex(ValueError, "does not match locked SHA-256"):
                compile_summer_thunder_dragon_ui_assets(
                    masters, donor_atlas, donor_atfs, drifted
                )

    def test_locked_identity_and_asset_specific_crop_contract(self):
        self._require_module()
        self.assertIsNotNone(compile_summer_thunder_dragon_ui_assets)
        self.assertEqual(
            {
                0: "ab842d15fb2a9e70162a86f2291a4cda5191456be276aeabfd59f65e75b27dac",
                1: "cb553428246fe1cd12b11b0bbba7523360ff06ea9f976b3e1d97492a03ca8eed",
            },
            SUMMER_THUNDER_MASTER_SHA256,
        )
        self.assertEqual(
            {
                "round_95": "08905639407af0a17d5f19ae995b2541e2aff2b95471f0444278de1247a08d4d",
                "round_136": "11e9cd99bb90d787ccdb9eac1098b0b4888cea6976d6384e04234f5e9ba0d388",
                "level_up": "561b9524b1960ce07723cc8ca326ae0a6444e2c1de18a9b0b676d620edb2a32a",
                "party_main": "0b1ef1f70d5412c634237bea233dc667f9d08847c1dd2243961719357e90bd70",
                "party_unison": "92cf558b0bd9f4359ddd3e44e379d67ef341c2f47a445d72c6a7104727e15904",
                "control_board": "45b06451e25f05fb7858a03b4d160903f283bb9d058bac3a19ddffb4a6bbcb9c",
                "member_status": "b8bf0ab68310373479181a720100c75553623773d9e46bdf95d5e751f7d25814",
                "chain": "a7abab2acd2dbff5d5e480e87234dd5cea6ca9cf6630f41a545f8fc1bade6f28",
            },
            SUMMER_THUNDER_SHAPE_MASK_SHA256,
        )
        self.assertEqual((250, 0, 1070, 410), SUMMER_THUNDER_CROP_BOXES[0]["skill_cutin"])
        self.assertEqual((430, 20, 709, 608), SUMMER_THUNDER_CROP_BOXES[0]["party_main"])
        self.assertEqual((0, 220, 1080, 760), SUMMER_THUNDER_CROP_BOXES[1]["skill_cutin"])
        self.assertEqual((245, 270, 524, 858), SUMMER_THUNDER_CROP_BOXES[1]["party_main"])
        self.assertNotEqual(
            SUMMER_THUNDER_CROP_BOXES[0]["square_212"],
            SUMMER_THUNDER_CROP_BOXES[0]["skill_cutin"],
        )

        invalid_boxes = _boxes()
        invalid_boxes[1] = dict(invalid_boxes[1])
        invalid_boxes[1]["member_status"] = (0, 0, 99, 99)
        with self.assertRaisesRegex(ValueError, "outside master"):
            compile_ui_png_assets(
                _masters(), invalid_boxes, _sizes(), _donor_atlas(),
                shape_masks=_shape_masks(),
                source_prefix=SOURCE, target_prefix=TARGET,
            )

    def test_cutin_renderer_applies_premultiplied_lanczos_and_edge_gain(self):
        source = Image.new("RGBA", (6, 4), (255, 0, 0, 0))
        for y in range(4):
            for x in range(2, 6):
                source.putpixel((x, y), (0, 128, 255, 255))
        rendered = ui_compile._render_skill_cutin(
            source, (0, 0, 6, 4), (12, 8)
        )
        self.assertEqual((12, 8), rendered.size)
        self.assertEqual(
            "7cd999562705f1ff8e668dcf13ab625874647d9adc8df8acd960e7ac4e32a8b9",
            hashlib.sha256(rendered.tobytes()).hexdigest(),
        )
        alpha = rendered.getchannel("A")
        self.assertEqual(
            "2b27670228e6099d95c37fd0a73c91ac212fa524b6f4c7a16189c2f2b76ff36e",
            hashlib.sha256(alpha.tobytes()).hexdigest(),
        )
        edge = (
            [alpha.getpixel((x, 0)) for x in range(12)]
            + [alpha.getpixel((x, 7)) for x in range(12)]
            + [alpha.getpixel((0, y)) for y in range(8)]
            + [alpha.getpixel((11, y)) for y in range(8)]
        )
        self.assertLessEqual(max(edge), 223)
        self.assertNotIn(255, edge)
        for red, green, blue, alpha_value in rendered.get_flattened_data():
            if alpha_value == 0:
                self.assertEqual((0, 0, 0), (red, green, blue))

    @unittest.skipUnless(
        HAS_LOCAL_ACCEPTED_PORTRAITS,
        "local evidence requires gitignored work/.../portraits/accepted_v1",
    )
    def test_local_locked_cutin_wrapper_matches_accepted_portraits(self):
        self._require_module()
        expected = {
            0: {
                "crop": (250, 0, 1070, 410),
                "source_face": (565, 260),
                "target_face": (393, 325),
                "bbox": (0, 1, 888, 512),
                "coverage": 0.487560,
                "alpha_sha256": "d73c03c840cb6cec48bdc5b419c3196815f81fe7d069d648399c13c7acd1d71a",
            },
            1: {
                "crop": (0, 220, 1080, 760),
                "source_face": (385, 485),
                "target_face": (365, 251),
                "bbox": (38, 0, 992, 512),
                "coverage": 0.622202,
                "alpha_sha256": "e5608d5f45677ec7b4b6f2b98aa213ad89b3441d142827f7c70a0c6d93d4728a",
            },
        }
        masters = _accepted_masters()
        donor_atlas = _donor_atlas()
        shape_masks = _opaque_shape_masks(ui_compile.SUMMER_THUNDER_UI_SIZES)
        mask_hashes = {
            key: hashlib.sha256(payload).hexdigest()
            for key, payload in shape_masks.items()
        }
        with (
            mock.patch.object(
                ui_compile,
                "SUMMER_THUNDER_DONOR_ATLAS_SHA256",
                hashlib.sha256(donor_atlas).hexdigest(),
            ),
            mock.patch.object(
                ui_compile, "SUMMER_THUNDER_SHAPE_MASK_SHA256", mask_hashes
            ),
            mock.patch.object(
                ui_compile, "compile_cutin_atf_assets", _stub_cutin_atfs
            ),
        ):
            files, _report = compile_summer_thunder_dragon_ui_assets(
                masters, donor_atlas, {}, shape_masks
            )
        alpha_payloads = []
        for form in (0, 1):
            contract = expected[form]
            self.assertEqual(
                contract["crop"],
                SUMMER_THUNDER_CROP_BOXES[form]["skill_cutin"],
            )
            left, top, right, bottom = contract["crop"]
            source_face_x, source_face_y = contract["source_face"]
            mapped_face = (
                (source_face_x - left) * 1024 / (right - left),
                (source_face_y - top) * 512 / (bottom - top),
            )
            self.assertLessEqual(abs(mapped_face[0] - contract["target_face"][0]), 2)
            self.assertLessEqual(abs(mapped_face[1] - contract["target_face"][1]), 2)

            logical = f"{TARGET}/ui/skill_cutin_{form}.png"
            with Image.open(io.BytesIO(wf_assets.png_decode(files[logical]))) as opened:
                rendered = opened.convert("RGBA")
            alpha = rendered.getchannel("A")
            alpha_payload = alpha.tobytes()
            alpha_payloads.append(alpha_payload)
            corners = (
                alpha.getpixel((0, 0)),
                alpha.getpixel((1023, 0)),
                alpha.getpixel((0, 511)),
                alpha.getpixel((1023, 511)),
            )
            self.assertEqual((0, 0, 0, 0), corners)
            edge = (
                [alpha.getpixel((x, 0)) for x in range(1024)]
                + [alpha.getpixel((x, 511)) for x in range(1024)]
                + [alpha.getpixel((0, y)) for y in range(512)]
                + [alpha.getpixel((1023, y)) for y in range(512)]
            )
            self.assertLessEqual(max(edge), 223)
            self.assertNotIn(255, edge)
            occupied = alpha.point(lambda value: 255 if value > 1 else 0)
            actual_bbox = occupied.getbbox()
            self.assertIsNotNone(actual_bbox)
            for actual, wanted in zip(actual_bbox, contract["bbox"]):
                self.assertLessEqual(abs(actual - wanted), 1)
            coverage = sum(value > 1 for value in alpha_payload) / len(alpha_payload)
            self.assertLessEqual(abs(coverage - contract["coverage"]), 0.001)
            self.assertEqual(
                contract["alpha_sha256"], hashlib.sha256(alpha_payload).hexdigest()
            )
            for red, green, blue, alpha_value in rendered.get_flattened_data():
                if alpha_value == 0:
                    self.assertEqual((0, 0, 0), (red, green, blue))
        self.assertNotEqual(alpha_payloads[0], alpha_payloads[1])


if __name__ == "__main__":
    unittest.main()

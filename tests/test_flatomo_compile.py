import io
import tempfile
import unittest
import zlib
from pathlib import Path

from PIL import Image

import wf_assets
import wf_dsl

try:
    from wf_flatomo_compile import (
        compile_flipbook_effect,
        compile_travelling_wave_effect,
    )
except ImportError:
    compile_flipbook_effect = None
    compile_travelling_wave_effect = None


class FlatomoCompileTests(unittest.TestCase):
    def test_compile_flipbook_effect_rejects_absolute_logical_root(self):
        if compile_flipbook_effect is None:
            self.fail("wf_flatomo_compile.compile_flipbook_effect is missing")

        with tempfile.TemporaryDirectory() as temporary_name:
            path = Path(temporary_name) / "frame.png"
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            image.putpixel((32, 32), (255, 255, 255, 255))
            image.save(path)
            with self.assertRaisesRegex(ValueError, "relative logical path"):
                compile_flipbook_effect(
                    [path],
                    effect_root="/battle/effect/test",
                    texture_name="texture",
                    effect_name="effect",
                )

    def test_compile_flipbook_effect_rejects_unsafe_logical_components(self):
        if compile_flipbook_effect is None:
            self.fail("wf_flatomo_compile.compile_flipbook_effect is missing")

        with tempfile.TemporaryDirectory() as temporary_name:
            path = Path(temporary_name) / "frame.png"
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            image.putpixel((32, 32), (255, 255, 255, 255))
            image.save(path)
            for field, value in (
                ("effect_root", "battle/effect/bad\nroot"),
                ("texture_name", "C:"),
                ("effect_name", "effect "),
            ):
                arguments = {
                    "effect_root": "battle/effect/test",
                    "texture_name": "texture",
                    "effect_name": "effect",
                }
                arguments[field] = value
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, "logical"):
                        compile_flipbook_effect([path], **arguments)

    def test_compile_flipbook_effect_rejects_fully_transparent_frame(self):
        if compile_flipbook_effect is None:
            self.fail("wf_flatomo_compile.compile_flipbook_effect is missing")

        with tempfile.TemporaryDirectory() as temporary_name:
            path = Path(temporary_name) / "empty.png"
            Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(path)
            with self.assertRaisesRegex(ValueError, "fully transparent"):
                compile_flipbook_effect(
                    [path],
                    effect_root="battle/effect/test",
                    texture_name="texture",
                    effect_name="effect",
                )

    def test_compile_flipbook_effect_builds_closed_four_file_asset(self):
        if compile_travelling_wave_effect is None:
            self.fail("wf_flatomo_compile.compile_travelling_wave_effect is missing")

        with tempfile.TemporaryDirectory() as temporary_name:
            temporary = Path(temporary_name)
            frames = []
            for index in range(10):
                path = temporary / f"frame_{index:02d}.png"
                image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                image.putpixel((index + 1, 32), (255, index, 200, 255))
                image.save(path)
                frames.append(path)

            root = "battle/effect/skill_unique/cnmod_thunder_dragon_ascendant/fan_lightning"
            files = compile_travelling_wave_effect(frames)
            files_again = compile_travelling_wave_effect(frames)

        expected_keys = {
            f"{root}/fan_lightning.png",
            f"{root}/fan_lightning.atlas.amf3.deflate",
            f"{root}/fan_lightning_wave.parts.amf3.deflate",
            f"{root}/fan_lightning_wave.timeline.amf3.deflate",
        }
        self.assertEqual(expected_keys, set(files))
        self.assertEqual(files, files_again)
        self.assertEqual(
            wf_assets.PNG_FAKE,
            files[f"{root}/fan_lightning.png"][:8],
        )

        for logical, payload in files.items():
            if not logical.endswith(".amf3.deflate"):
                continue
            decompressor = zlib.decompressobj(-15)
            decompressor.decompress(payload)
            decompressor.flush()
            self.assertTrue(decompressor.eof, logical)
            self.assertEqual(b"", decompressor.unused_data, logical)
            self.assertEqual(b"", decompressor.unconsumed_tail, logical)

        sheet = wf_assets.png_decode(files[f"{root}/fan_lightning.png"])
        self.assertEqual((330, 132), wf_assets.png_dims(sheet))
        with Image.open(io.BytesIO(sheet)) as decoded_sheet:
            alpha = decoded_sheet.convert("RGBA").getchannel("A")
            for x in range(decoded_sheet.width):
                if x % 66 in {0, 65}:
                    self.assertIsNone(alpha.crop((x, 0, x + 1, 132)).getbbox())
            for y in range(decoded_sheet.height):
                if y % 66 in {0, 65}:
                    self.assertIsNone(alpha.crop((0, y, 330, y + 1)).getbbox())

        atlas = wf_dsl.parse_dsl(
            zlib.decompress(files[f"{root}/fan_lightning.atlas.amf3.deflate"], -15)
        )["tree"]
        self.assertEqual(10, len(atlas))
        self.assertEqual(
            f"{root}/.gen/fan_lightning_wave/f00",
            atlas[0]["n"],
        )
        self.assertEqual(
            {"w": 64, "h": 64, "x": 1, "y": 1},
            {key: atlas[0][key] for key in ("w", "h", "x", "y")},
        )
        self.assertEqual(
            {"w": 64, "h": 64, "x": 1, "y": 67},
            {key: atlas[5][key] for key in ("w", "h", "x", "y")},
        )

        parts = wf_dsl.parse_dsl(
            zlib.decompress(files[f"{root}/fan_lightning_wave.parts.amf3.deflate"], -15)
        )["tree"]
        self.assertEqual(10, len(parts["i"]))
        self.assertEqual(
            [f"{root}/.gen/fan_lightning_wave/f{index:02d}" for index in range(10)],
            [entry["p"] for entry in parts["i"]],
        )
        self.assertEqual(
            {entry["n"] for entry in atlas},
            {entry["p"] for entry in parts["i"]},
        )
        self.assertEqual([1] * 10, parts["a"])
        self.assertEqual(2, len(parts["g"]))
        self.assertEqual(111, parts["g"][0]["t"])
        root_segments = parts["g"][0]["s"]
        self.assertEqual(11, len(root_segments))
        self.assertEqual(
            [-2147483648.0 + start for start in range(0, 101, 10)],
            [segment["s"] for segment in root_segments],
        )
        self.assertEqual([1] * 11, [segment["i"] for segment in root_segments])
        self.assertTrue(
            all(
                segment["l"] == [{"m": 255, "t": 11, "r": 1073741824.0}]
                for segment in root_segments
            )
        )

        wave = parts["g"][1]
        self.assertEqual(11, wave["t"])
        self.assertEqual(list(range(10)), [segment["s"] for segment in wave["s"]])
        self.assertEqual(list(range(10)), [segment["i"] for segment in wave["s"]])
        self.assertTrue(all(segment["l"] == [{"m": 4351}] for segment in wave["s"]))
        self.assertEqual(
            [
                {"a": 4096, "b": 0, "c": 0, "d": 4096, "x": 0, "y": 0},
                {"a": 4096, "b": 0, "c": 0, "d": 4096, "x": -32768, "y": -131072},
            ],
            parts["t"],
        )

        timeline = wf_dsl.parse_dsl(
            zlib.decompress(files[f"{root}/fan_lightning_wave.timeline.amf3.deflate"], -15)
        )["tree"]
        self.assertEqual(
            [{"begin": 1, "end": 111, "name": "neutral", "kind": "once"}],
            timeline["sequences"],
        )
        self.assertEqual([], timeline["sounds"])


if __name__ == "__main__":
    unittest.main()

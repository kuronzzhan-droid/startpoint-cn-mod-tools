"""原生状态表的图标路径必须有可解码、独立且尺寸正确的资源。"""
import sys
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_bianca_dragon as assembly
import wf_bianca_dragon_bridge as bridge
import wf_bianca_dragon_icons as icons
from wf_assets import PNG_FAKE, png_decode


class StatusIconContractTest(unittest.TestCase):
    def test_all_native_paths_have_distinct_decodable_icons(self):
        assets = icons.build_icon_assets()
        expected = {row[0][2] + ".png" for row in bridge.unique_condition_rows().values()}
        expected.add("battle/common/unique_condition/lady_summoner_campus_fever_stack.png")
        self.assertEqual(set(assets), expected)
        pixels = []
        for raw in assets.values():
            self.assertTrue(raw.startswith(PNG_FAKE))
            with Image.open(BytesIO(png_decode(raw))) as icon:
                icon.load()
                self.assertEqual(icon.size, (48, 48))
                self.assertEqual(icon.mode, "RGBA")
                self.assertEqual(icon.getextrema()[3], (0, 255))
                pixels.append(icon.tobytes())
        self.assertEqual(len(set(pixels)), 3)

    def test_skill_description_keeps_mechanics_without_numbers(self):
        self.assertNotRegex(assembly.DESCRIPTION, r"\d|[%％]")
        for phrase in ("协力球", "向下吐息", "能力伤害", "火属性抗性", "FEVER槽",
                       "自身获得「幼龙回应」", "自身获得「幼龙吐息」"):
            self.assertIn(phrase, assembly.DESCRIPTION)


if __name__ == "__main__":
    unittest.main()

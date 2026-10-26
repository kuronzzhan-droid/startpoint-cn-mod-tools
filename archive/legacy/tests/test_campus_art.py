"""立绘装配保护地面、拒绝假透明源、只更新自有定位键。"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_campus_art as art
import wf_campus_art_images as images
import wf_mod_tool as core
import wf_quest_lib as tables


class CampusArtTests(unittest.TestCase):
    def test_transparent_icons_preserve_art_alpha_and_native_shape(self):
        source = Image.new("RGBA", (900, 1200))
        ImageDraw.Draw(source).rectangle((310, 160, 370, 400), fill=(210, 50, 20, 255))
        mark = dict(face=[340, 190], eyes=[340, 180], square_height=240, head_height=180,
                    transparent_icon_background=True,
                    icon_anchors={"thumb_party_main": [.5, .29]})
        masks = {}
        for slot in images.gate.SHAPE_SLOTS:
            width, height = images.gate.OFFICIAL_ICON_SIZES[slot]
            mask = np.full((height, width), 255, np.uint8)
            mask[:3] = 0
            masks[slot] = mask
        icons = images.make_icons(source, mark, masks, "celtie", headshots=True)
        for slot, icon in icons.items():
            pixels = np.asarray(icon)
            self.assertGreater(float((pixels[:, :, 3] == 0).mean()), .3, slot)
            solid = pixels[pixels[:, :, 3] == 255, :3]
            self.assertGreater(len(solid), 10, slot)
            # Lanczos creates edge ringing; the interior colour must remain intact.
            np.testing.assert_array_equal(np.median(solid, axis=0), [210, 50, 20])
            self.assertTrue(np.all(solid[:, 0].astype(float) > solid[:, 1] * 3), slot)
            if slot in masks:
                self.assertTrue(np.all(pixels[:, :, 3] <= masks[slot]), slot)
        mark.pop("transparent_icon_background")
        opaque = images.make_icons(source, mark, masks, "celtie", headshots=True)
        self.assertEqual(opaque["square"].getchannel("A").getextrema(), (255, 255))

    def test_skill_button_anchor_moves_face_up_without_changing_other_icons(self):
        source = Image.new("RGBA", (900, 1200))
        ImageDraw.Draw(source).rectangle((310, 160, 370, 220), fill="red")
        mark = dict(face=[340, 190], eyes=[340, 180], square_height=240, head_height=180)
        masks = {slot: np.full((height, width), 255, np.uint8)
                 for slot, (width, height) in images.gate.OFFICIAL_ICON_SIZES.items()
                 if slot in images.gate.SHAPE_SLOTS}
        before = images.make_icons(source, mark, masks, "celtie", headshots=True)
        mark["icon_anchors"] = {"battle_control_board": [.5, .31]}
        after = images.make_icons(source, mark, masks, "celtie", headshots=True)
        for slot, icon in after.items():
            if slot != "battle_control_board":
                self.assertEqual(icon.tobytes(), before[slot].tobytes(), slot)
                continue
            pixels = np.asarray(icon)
            yy, xx = np.where((pixels[:, :, 0] > 220) & (pixels[:, :, 1] < 20)
                              & (pixels[:, :, 2] < 20) & (pixels[:, :, 3] > 220))
            self.assertGreater(len(xx), 10)
            self.assertAlmostEqual(float(xx.mean()) / icon.width, .5, delta=.02)
            self.assertAlmostEqual(float(yy.mean()) / icon.height, .31, delta=.02)
            self.assertEqual(icon.size, before[slot].size)
            np.testing.assert_array_equal(pixels[:, :, 3], np.asarray(before[slot])[:, :, 3])
        for anchor in ([.5, 1.1], [True, .31], [float("nan"), .31], [.5], "center"):
            mark["icon_anchors"]["battle_control_board"] = anchor
            with self.assertRaises(ValueError):
                images.make_icons(source, mark, masks, "celtie", headshots=True)

    def test_headshots_keep_off_center_face_centered_in_every_native_slot(self):
        source = Image.new("RGBA", (900, 1200))
        draw = ImageDraw.Draw(source)
        draw.rectangle((310, 160, 370, 220), fill="red")
        mark = dict(face=[340, 190], eyes=[340, 180], square_height=240, head_height=180)
        masks = {slot: np.full((height, width), 255, np.uint8)
                 for slot, (width, height) in images.gate.OFFICIAL_ICON_SIZES.items()
                 if slot in images.gate.SHAPE_SLOTS}
        icons = images.make_icons(source, mark, masks, "celtie", headshots=True)
        # A per-form override must reproduce the headshot layout even when the
        # other form keeps the default composition; cut-in framing is independent.
        per_form = images.make_icons(source, dict(mark, headshot_icons=True), masks, "celtie")
        self.assertEqual({k: v.tobytes() for k, v in icons.items()},
                         {k: v.tobytes() for k, v in per_form.items()})
        icons["skill_cutin"] = images.make_cutin(source, mark, headshots=True)
        for slot, icon in icons.items():
            pixels = np.asarray(icon)
            yy, xx = np.where((pixels[:, :, 0] > 220) & (pixels[:, :, 1] < 20)
                              & (pixels[:, :, 2] < 20) & (pixels[:, :, 3] > 220))
            self.assertGreater(len(xx), 10, slot)
            self.assertAlmostEqual(float(xx.mean()) / icon.width, .5, delta=.02, msg=slot)
            self.assertAlmostEqual(float(yy.mean()) / icon.height, .5, delta=.02, msg=slot)
            self.assertEqual(icon.size, images.gate.OFFICIAL_ICON_SIZES[slot])

    def test_fullshot_keeps_bottom_scene_and_stays_in_native_canvas(self):
        source = Image.new("RGBA", (1000, 1500))
        draw = ImageDraw.Draw(source)
        draw.rectangle((200, 50, 750, 1400), fill="white")
        draw.rectangle((25, 1350, 950, 1490), fill="red")
        full, geometry = images.full_shot(source, (500, 180))
        self.assertEqual(geometry["source_alpha_bbox"], [25, 50, 951, 1491])
        self.assertTrue(geometry["crop_removes_only_fully_transparent_pixels"])
        self.assertLessEqual(geometry["x"] + full.width, 2000)
        self.assertLessEqual(geometry["y"] + full.height, 2000)
        # 红色底座在最终PNG最底行仍完整可见，不能为放大头部切掉地面。
        bottom = np.asarray(full)[-1]
        self.assertGreater(((bottom[:, 0] > 200) & (bottom[:, 1] < 20) & (bottom[:, 3] > 200)).mean(), .95)

    def test_rejects_rgb_or_opaque_grid_even_if_extension_png(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.png"
            mark = dict(face=[5, 5], eyes=[5, 4])
            for mode in ("RGB", "RGBA"):
                Image.new(mode, (10, 10), "white").save(path)
                with self.assertRaises(ValueError):
                    images.load_master(path, mark)

    def test_hash_bound_source_landmarks(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.png"
            source = Image.new("RGBA", (100, 100))
            ImageDraw.Draw(source).rectangle((20, 20, 80, 99), fill="white")
            source.save(path)
            with self.assertRaises(ValueError):
                images.load_master(path, dict(face=[50, 40], eyes=[50, 35], sha256="0" * 64))
            _, report = images.load_master(path, dict(face=[50, 40], eyes=[50, 35]))
            self.assertEqual(report["sha256"], images.sha(path.read_bytes()))

    def test_geometry_patch_preserves_all_foreign_raw_rows(self):
        cid, code = art.CHARACTERS["bianca"]
        ui = f"character/{code}/ui/"
        geometry = [dict(x=250, y=300, width=1200, height=1600)] * 2
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder)
            for logical, source in (
                ("master/generated/character_image.orderedmap", {"1": {"0": "1,2,3,4"}, cid: {"0": "0,0,1,1", "1": "0,0,1,1"}}),
                ("master/character/full_shot_image_attribute.orderedmap", {"1": {"0": "1,2,3,4,5"}, cid: {"0": "0,0,1,0,0", "1": "0,0,1,0,0"}}),
                ("master/generated/trimmed_image.orderedmap", {"foreign": "1,2,3,4", **{
                    ui + f"{name}_{n}": "0,0,1,1" for name in ("full_shot_1440_1920", "skill_cutin") for n in (0, 1)}}),
            ):
                path = package / "roots/common" / logical
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(tables.build_node(source))
            result = art.patch_tables(package, cid, ui, geometry)
            for relative, raw in result.items():
                logical = relative.split("/", 1)[1]
                before = core.read_orderedmap_file_raw_rows(package / "roots" / relative, logical)
                after = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
                changed = {k for k, a, b in zip(before.keys, before.rows, after.rows) if a != b}
                self.assertTrue(changed)
                self.assertTrue(all(k == cid or k.startswith(ui) for k in changed))


if __name__ == "__main__":
    unittest.main()

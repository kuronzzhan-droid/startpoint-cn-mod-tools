#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exact package-level skill-follow ActionDSL and Flatomo gates."""

from __future__ import annotations

import copy
import math
import tempfile
import unittest
import zlib
from pathlib import Path

from PIL import Image

import wf_action_skill_compile as action_compile
import wf_dsl
import wf_flatomo_compile as flatomo_compile
import wf_summer_thunder_package_skill_gate as module
from wf_summer_thunder_package_contract import PackageAssemblyError


def _effect_files() -> dict[str, bytes]:
    with tempfile.TemporaryDirectory() as temporary_name:
        root = Path(temporary_name)
        frames = []
        boxes = (
            (3, 27, 14, 38), (6, 27, 17, 38), (9, 21, 24, 45),
            (14, 21, 29, 45), (12, 14, 38, 51), (18, 14, 44, 51),
            (24, 14, 50, 51), (38, 11, 54, 55), (46, 22, 57, 44),
            (51, 22, 62, 44),
        )
        for index, box in enumerate(boxes):
            path = root / f"frame-{index}.png"
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            color = (255, 220, 30, 255) if index % 2 == 0 else (30, 220, 255, 255)
            for y in range(box[1], box[3]):
                for x in range(box[0], box[2]):
                    image.putpixel((x, y), color)
            image.save(path)
            frames.append(path)
        return flatomo_compile.compile_travelling_wave_effect(frames)


def _encode_tree(tree: list) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    raw = wf_dsl.encode_amf3(tree)
    return compressor.compress(raw) + compressor.flush()


def _commands(value):
    if isinstance(value, list):
        if len(value) == 2 and value[0] == "Command":
            yield value[1]
        for item in value:
            yield from _commands(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _commands(item)


class ExactSkillFollowGateTests(unittest.TestCase):
    def test_real_payloads_close_exact_follow_and_flatomo_contract(self):
        action = action_compile.compile_summer_thunder_dragon_action_skills()
        effect = _effect_files()
        gate = module.build_skill_follow_gate(action, effect)
        self.assertTrue(gate["package_manifest_eligible"])
        self.assertEqual("accepted_exact_runtime_follow_contract", gate["status"])
        self.assertEqual(-math.pi / 2, gate["action"]["show_effect"]["rotation"])
        self.assertEqual(0.0, gate["action"]["hit_area"]["rotation"])
        self.assertEqual([3, 11, 62, 55], gate["flatomo"]["union_bbox"])
        self.assertEqual(351.0, gate["flatomo"]["forward_scaled_max"])
        self.assertEqual(110, gate["flatomo"]["visible_ticks"])
        self.assertEqual(111, gate["flatomo"]["timeline_end_exclusive"])
        self.assertEqual(gate, module.validate_skill_follow_gate(gate))

    def test_hit_area_rotated_with_visual_is_rejected_semantically(self):
        tree = copy.deepcopy(action_compile.build_summer_thunder_dragon_skill_tree())
        hit = next(command for command in _commands(tree) if command[0] == "CreateHitArea")
        hit[6] = -math.pi / 2
        payload = _encode_tree(tree)
        action = {
            logical: payload
            for logical in action_compile.compile_summer_thunder_dragon_action_skills()
        }
        with self.assertRaisesRegex(PackageAssemblyError, "HitArea rotation"):
            module.build_skill_follow_gate(action, _effect_files())

    def test_double_applied_flatomo_anchor_is_rejected(self):
        action = action_compile.compile_summer_thunder_dragon_action_skills()
        effect = _effect_files()
        parts_logical = next(
            logical for logical in effect if logical.endswith(".parts.amf3.deflate")
        )
        parts = wf_dsl.parse_dsl(
            zlib.decompress(effect[parts_logical], -15)
        )["tree"]
        parts["t"] = [parts["t"][1]]
        for segment in parts["g"][1]["s"]:
            segment["l"] = [{"m": 255}]
        effect[parts_logical] = _encode_tree(parts)
        with self.assertRaisesRegex(PackageAssemblyError, "transform"):
            module.build_skill_follow_gate(action, effect)

    def test_every_tracking_geometry_and_flatomo_boundary_is_fail_closed(self):
        action = action_compile.compile_summer_thunder_dragon_action_skills()
        effect = _effect_files()
        valid = module.build_skill_follow_gate(action, effect)
        for path, value in (
            (("action", "show_effect", "tracking_direction"), True),
            (("action", "hit_area", "tracking_position"), False),
            (("action", "hit_area", "sector_radius"), 399),
            (("action", "hit_area", "max_hits"), 54),
            (("flatomo", "origin"), [32, 32]),
            (("flatomo", "alpha_values"), [0, 128, 255]),
            (("flatomo", "gutter_pixels"), 0),
            (("flatomo", "timeline_end_exclusive"), 110),
        ):
            altered = copy.deepcopy(valid)
            target = altered
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path):
                with self.assertRaisesRegex(PackageAssemblyError, "exact contract"):
                    module.validate_skill_follow_gate(altered)

    def test_pending_and_generic_eligible_claims_cannot_unlock(self):
        for gate in (
            None,
            module.pending_skill_follow_gate(),
            {"package_manifest_eligible": True, "writes_live": False},
        ):
            with self.subTest(gate=gate):
                with self.assertRaises(PackageAssemblyError):
                    module.validate_skill_follow_gate(gate)


if __name__ == "__main__":
    unittest.main()

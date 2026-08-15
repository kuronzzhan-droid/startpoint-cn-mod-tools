#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure payload-level regression tests for the thunder-dragon 1.1.1 hotfix."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
import zlib
from pathlib import Path

import wf_dsl
import wf_mod_tool as core
import tests.test_pixelart_normal_compile as normal_fixture
from tests.test_abyss_gacha_compile import _decode_flat, _sources
from wf_abyss_gacha_compile import compile_abyss_limited_gacha
from wf_abyss_gacha_contract import GACHA_KEY, GACHA_MASTER_LOGICAL, START_DATE
from wf_flatomo_compile import compile_travelling_wave_effect
from wf_pixelart_normal_compile import compile_full_normal
from wf_pixelart_special_compat_compile import compile_special_compatibility


SOURCE = normal_fixture.SOURCE
TARGET = normal_fixture.TARGET

try:
    from wf_thunder_hotfix_payloads import (
        repair_gacha_schedule,
        repair_normal_and_special,
        repair_travelling_wave_effect,
    )
except ImportError:
    repair_gacha_schedule = None
    repair_normal_and_special = None
    repair_travelling_wave_effect = None


def _amf(raw: bytes):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def _deflate(tree) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush()


def _json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


class ThunderHotfixPayloadTests(unittest.TestCase):
    def _require_module(self):
        if any(value is None for value in (
            repair_gacha_schedule,
            repair_normal_and_special,
            repair_travelling_wave_effect,
        )):
            self.fail("wf_thunder_hotfix_payloads is missing")

    def test_repairs_normal_pivots_and_regenerates_special_alias_only(self):
        self._require_module()
        template, _timeline = normal_fixture._template_files()
        helper = normal_fixture.FullNormalPixelArtCompileTests()
        with tempfile.TemporaryDirectory() as temporary_name:
            cels = helper._write_cels(Path(temporary_name))
            fixed_normal, _report = compile_full_normal(
                template, cels, source_prefix=SOURCE, target_prefix=TARGET
            )

        atlas_logical = f"{TARGET}/sprite_sheet.atlas.amf3.deflate"
        broken_normal = dict(fixed_normal)
        atlas = copy.deepcopy(_amf(broken_normal[atlas_logical]))
        by_tick = {
            int(entry["n"].rsplit("pixelart", 1)[1]): entry for entry in atlas
        }
        for tick in (2, 8, 14, 20, 26, 32, 38, 44, 50):
            by_tick[tick]["fx"] = -127
            by_tick[tick]["fy"] = -127
        for field in ("x", "y", "w", "h"):
            by_tick[32][field] = by_tick[26][field]
        broken_normal[atlas_logical] = _deflate(atlas)

        broken_hashes = {
            logical: __import__("hashlib").sha256(raw).hexdigest()
            for logical, raw in broken_normal.items()
        }
        broken_special, _broken_report = compile_special_compatibility(
            broken_normal,
            target_prefix=TARGET,
            expected_normal_sha256=broken_hashes,
        )
        repaired_normal, repaired_special, report = repair_normal_and_special(
            broken_normal,
            broken_special,
            template,
            source_prefix=SOURCE,
            target_prefix=TARGET,
            expected_normal_sha256=broken_hashes,
        )
        fixed_hashes = {
            logical: __import__("hashlib").sha256(raw).hexdigest()
            for logical, raw in fixed_normal.items()
        }
        fixed_special, _fixed_report = compile_special_compatibility(
            fixed_normal,
            target_prefix=TARGET,
            expected_normal_sha256=fixed_hashes,
        )

        self.assertEqual(fixed_normal, repaired_normal)
        self.assertEqual(fixed_special, repaired_special)
        self.assertEqual(9, report["official_anchor_records"])
        self.assertEqual("base_0002", report["tick_32_source"])
        self.assertFalse(report["writes_live"])

        drifted = dict(broken_normal)
        drifted[atlas_logical] += b"drift"
        with self.assertRaisesRegex(ValueError, "normal SHA-256 drift"):
            repair_normal_and_special(
                drifted,
                broken_special,
                template,
                source_prefix=SOURCE,
                target_prefix=TARGET,
                expected_normal_sha256=broken_hashes,
            )

    def test_repairs_double_applied_flatomo_anchor_without_touching_texture(self):
        self._require_module()
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            paths = []
            from PIL import Image

            for index in range(10):
                path = root / f"frame-{index}.png"
                image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                image.putpixel((index + 2, 32), (255, 220, 20, 255))
                image.save(path)
                paths.append(path)
            fixed = compile_travelling_wave_effect(paths)

        parts_logical = next(
            logical for logical in fixed if logical.endswith(".parts.amf3.deflate")
        )
        broken = dict(fixed)
        parts = copy.deepcopy(_amf(fixed[parts_logical]))
        parts["t"] = [parts["t"][1]]
        for segment in parts["g"][1]["s"]:
            segment["l"] = [{"m": 255}]
        broken[parts_logical] = _deflate(parts)
        expected = {
            logical: __import__("hashlib").sha256(raw).hexdigest()
            for logical, raw in broken.items()
        }

        repaired, report = repair_travelling_wave_effect(
            broken, expected_sha256=expected
        )
        self.assertEqual(fixed, repaired)
        self.assertEqual(10, report["child_anchor_layers"])
        self.assertEqual(1, report["root_identity_transform"])
        self.assertFalse(report["writes_live"])

    def test_repairs_all_three_schedule_mirrors_and_nothing_else(self):
        self._require_module()
        common, server = _sources()
        compiled = compile_abyss_limited_gacha(
            common, server, existing_common_paths=set(common)
        )["files"]
        broken = dict(compiled)
        old_date = "2026-08-15 00:00:00"

        rows = _decode_flat(broken[GACHA_MASTER_LOGICAL], GACHA_MASTER_LOGICAL)
        row = core.read_csv_lines(rows[GACHA_KEY].decode("utf-8"))[0]
        row[29] = old_date
        rows[GACHA_KEY] = core.write_csv_lines([row]).encode("utf-8")
        broken[GACHA_MASTER_LOGICAL] = core.build_orderedmap(core.OrderedMap(
            GACHA_MASTER_LOGICAL,
            list(rows),
            list(rows.values()),
            Path("<fixture>"),
        ))

        runtime = json.loads(broken["gacha.json"])
        runtime[GACHA_KEY]["startDate"] = old_date
        broken["gacha.json"] = _json(runtime)
        cdndata = json.loads(broken["cdndata/gacha.json"])
        cdndata[GACHA_KEY][0][29] = old_date
        broken["cdndata/gacha.json"] = _json(cdndata)

        repaired, report = repair_gacha_schedule(
            broken, expected_start_date=old_date
        )
        self.assertEqual(compiled, repaired)
        self.assertEqual(START_DATE, report["start_date"])
        self.assertEqual(3, report["changed_payload_count"])
        self.assertFalse(report["writes_live"])

        already_fixed = dict(compiled)
        with self.assertRaisesRegex(ValueError, "source start date drift"):
            repair_gacha_schedule(
                already_fixed, expected_start_date=old_date
            )


if __name__ == "__main__":
    unittest.main()

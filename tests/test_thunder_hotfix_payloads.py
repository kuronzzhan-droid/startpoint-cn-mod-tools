#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure payload-level regression tests for the thunder-dragon 1.1.6 hotfix."""

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
import wf_abyss_gacha_contract as gacha_contract
from wf_abyss_gacha_contract import GACHA_KEY, GACHA_MASTER_LOGICAL, START_DATE
from wf_flatomo_compile import compile_travelling_wave_effect
from wf_pixelart_normal_compile import compile_full_normal
from wf_pixelart_special_compat_compile import compile_special_compatibility


SOURCE = normal_fixture.SOURCE
TARGET = normal_fixture.TARGET

try:
    from wf_thunder_hotfix_gacha import SEALED_SOURCE_CHARACTER_IDS
    from wf_thunder_hotfix_payloads import (
        repair_gacha_contract,
        repair_normal_and_special,
        repair_travelling_wave_effect,
    )
except ImportError:
    SEALED_SOURCE_CHARACTER_IDS = ()
    repair_gacha_contract = None
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


def _raw_deflate(raw: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(raw) + compressor.flush()


_OLD_RICH_TEXT = b"""<!DOCTYPE html/>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>\xe6\xb7\xb1\xe6\xb8\x8a\xe9\x99\x90\xe5\xae\x9a\xe6\x89\xad\xe8\x9b\x8b\xe6\xb3\xa8\xe6\x84\x8f\xe4\xba\x8b\xe9\xa1\xb9</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body class="body" style_id="1">
  <div class="container">
    <p>\xe3\x83\xbb\xe6\x9c\xac\xe6\x89\xad\xe8\x9b\x8b\xe4\xbb\x85\xe5\x8f\xaf\xe4\xbd\xbf\xe7\x94\xa8\xe6\xb7\xb1\xe6\xb8\x8a\xe5\x8d\x95\xe6\x8a\xbd\xe5\x88\xb8\xe6\x88\x96\xe6\xb7\xb1\xe6\xb8\x8a\xe5\x8d\x81\xe8\xbf\x9e\xe5\x88\xb8\xe3\x80\x82</p><br/>
    <p>\xe3\x83\xbb\xe6\x9c\xac\xe6\x89\xad\xe8\x9b\x8b\xe4\xb8\x8d\xe6\x8e\xa5\xe5\x8f\x97\xe6\x98\x9f\xe5\xaf\xbc\xe7\x9f\xb3\xef\xbc\x8c\xe4\xb9\x9f\xe4\xb8\x8d\xe6\x8e\xa5\xe5\x8f\x97\xe9\x80\x9a\xe7\x94\xa8\xe8\xa7\x92\xe8\x89\xb2\xe6\x89\xad\xe8\x9b\x8b\xe5\x88\xb8\xe3\x80\x82</p><br/>
    <p>\xe3\x83\xbb\xe5\x8d\xa1\xe6\xb1\xa0\xe4\xbb\x85\xe5\x8c\x85\xe5\x90\xab\xe6\x8c\x87\xe5\xae\x9a\xe7\x9a\x848\xe5\x90\x8d\xe9\x99\x90\xe5\xae\x9a\xe2\x98\x855\xe8\xa7\x92\xe8\x89\xb2\xef\xbc\x8c\xe6\xaf\x8f\xe5\x90\x8d\xe8\xa7\x92\xe8\x89\xb2\xe7\x9a\x84\xe8\x8e\xb7\xe5\xbe\x97\xe6\xa6\x82\xe7\x8e\x87\xe5\x9d\x87\xe4\xb8\xba12.5%\xe3\x80\x82</p><br/>
    <p>\xe3\x83\xbb\xe4\xbd\xbf\xe7\x94\xa81\xe5\xbc\xa0\xe6\xb7\xb1\xe6\xb8\x8a\xe5\x8d\x95\xe6\x8a\xbd\xe5\x88\xb8\xe5\x8f\xaf\xe6\x8a\xbd\xe5\x8f\x961\xe6\xac\xa1\xef\xbc\x9b\xe4\xbd\xbf\xe7\x94\xa81\xe5\xbc\xa0\xe6\xb7\xb1\xe6\xb8\x8a\xe5\x8d\x81\xe8\xbf\x9e\xe5\x88\xb8\xe5\x8f\xaf\xe8\xbf\x9e\xe7\xbb\xad\xe6\x8a\xbd\xe5\x8f\x9610\xe6\xac\xa1\xe3\x80\x82</p><br/>
    <p>\xe3\x83\xbb\xe9\x87\x8d\xe5\xa4\x8d\xe8\x8e\xb7\xe5\xbe\x97\xe5\xb7\xb2\xe6\x9c\x89\xe8\xa7\x92\xe8\x89\xb2\xe6\x97\xb6\xef\xbc\x8c\xe6\x8c\x89\xe6\xb8\xb8\xe6\x88\x8f\xe7\x8e\xb0\xe6\x9c\x89\xe8\xa7\x92\xe8\x89\xb2\xe9\x87\x8d\xe5\xa4\x8d\xe8\x8e\xb7\xe5\xbe\x97\xe8\xa7\x84\xe5\x88\x99\xe5\xa4\x84\xe7\x90\x86\xe3\x80\x82</p>
  </div>
</body>
</html>
"""


def _old_contract_fixture(compiled: dict[str, bytes], old_date: str) -> dict[str, bytes]:
    broken = dict(compiled)
    rows = _decode_flat(broken[GACHA_MASTER_LOGICAL], GACHA_MASTER_LOGICAL)
    row = core.read_csv_lines(rows[GACHA_KEY].decode("utf-8"))[0]
    row[4] = "2"
    row[5:9] = ["", "", "", ""]
    row[10] = "5"
    row[29] = old_date
    row[44] = "false"
    rows[GACHA_KEY] = core.write_csv_lines([row]).encode("utf-8")
    broken[GACHA_MASTER_LOGICAL] = core.build_orderedmap(core.OrderedMap(
        GACHA_MASTER_LOGICAL, list(rows), list(rows.values()), Path("<fixture>"),
    ))

    old_pool = {
        "1": [{
            "id": value, "rank": 5, "odds": 100,
            "isRateUp": True, "isLimited": True, "isExchangeable": False,
            "rarity": 125.0, "trialReadingForced": False,
        } for value in SEALED_SOURCE_CHARACTER_IDS],
        "2": [], "3": [],
    }
    runtime = json.loads(broken["gacha.json"])
    runtime[GACHA_KEY].update({
        "pageKind": 2,
        "guaranteeRarity": 5,
        "rankRates": {"normal": [1000, 0, 0], "multiGuarantee": [1000, 0]},
        "startDate": old_date,
        "pool": old_pool,
    })
    broken["gacha.json"] = _json(runtime)
    cdndata = json.loads(broken["cdndata/gacha.json"])
    cdndata[GACHA_KEY][0][4] = "2"
    cdndata[GACHA_KEY][0][5:9] = ["", "", "", ""]
    cdndata[GACHA_KEY][0][10] = "5"
    cdndata[GACHA_KEY][0][29] = old_date
    cdndata[GACHA_KEY][0][44] = "false"
    broken["cdndata/gacha.json"] = _json(cdndata)
    broken[gacha_contract.RARITY_ODDS_LOGICAL] = (
        __import__("wf_abyss_gacha_compile")._new_nested(
            gacha_contract.RARITY_ODDS_LOGICAL,
            gacha_contract.RARITY_ODDS_ID,
            {"0": "5,100", "1": "4,0", "2": "3,0"},
        )
    )
    broken[gacha_contract.CHARACTER_3_ODDS_LOGICAL] = (
        __import__("wf_abyss_gacha_compile")._new_nested(
            gacha_contract.CHARACTER_3_ODDS_LOGICAL,
            gacha_contract.CHARACTER_3_ODDS_ID, {},
        )
    )
    broken[gacha_contract.CHARACTER_4_ODDS_LOGICAL] = (
        __import__("wf_abyss_gacha_compile")._new_nested(
            gacha_contract.CHARACTER_4_ODDS_LOGICAL,
            gacha_contract.CHARACTER_4_ODDS_ID, {},
        )
    )
    old_five = {
        str(index): f"{value},5,100,true,true,false,false"
        for index, value in enumerate(SEALED_SOURCE_CHARACTER_IDS)
    }
    broken[gacha_contract.CHARACTER_5_ODDS_LOGICAL] = (
        __import__("wf_abyss_gacha_compile")._new_nested(
            gacha_contract.CHARACTER_5_ODDS_LOGICAL,
            gacha_contract.CHARACTER_5_ODDS_ID, old_five,
        )
    )
    broken[gacha_contract.RICH_TEXT_BODY_LOGICAL] = _raw_deflate(_OLD_RICH_TEXT)
    return broken


class ThunderHotfixPayloadTests(unittest.TestCase):
    def _require_module(self):
        if any(value is None for value in (
            repair_gacha_contract,
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

    def test_sealed_source_pickup_list_never_tracks_the_live_contract(self):
        self._require_module()
        self.assertEqual(
            (129999, 139998, 139999, 149998, 149999, 169998, 169999, 179999),
            SEALED_SOURCE_CHARACTER_IDS,
        )
        self.assertNotIn(139997, SEALED_SOURCE_CHARACTER_IDS)
        self.assertEqual(9, len(gacha_contract.CHARACTER_IDS))

    def test_repairs_standard_pool_exchange_and_schedule_in_eight_payloads(self):
        self._require_module()
        common, server = _sources()
        compiled = compile_abyss_limited_gacha(
            common, server, existing_common_paths=set(common)
        )["files"]
        old_date = "2026-08-15 00:00:00"
        broken = _old_contract_fixture(compiled, old_date)
        repaired, report = repair_gacha_contract(
            broken, expected_start_date=old_date
        )
        self.assertEqual(compiled, repaired)
        pickups = [
            entry
            for entry in json.loads(repaired["gacha.json"])[GACHA_KEY]["pool"]["1"]
            if entry["isLimited"]
        ]
        self.assertEqual(
            list(gacha_contract.CHARACTER_IDS),
            [entry["id"] for entry in pickups],
        )
        self.assertEqual(
            [139997],
            [entry["id"] for entry in pickups if not entry["isExchangeable"]],
        )
        self.assertEqual(START_DATE, report["start_date"])
        self.assertEqual(8, report["changed_payload_count"])
        self.assertEqual([50, 250, 700], report["rank_rates"])
        self.assertEqual(
            {"limited": 250, "standard": 250},
            report["exchange_required_points"],
        )
        self.assertEqual(8, report["exchangeable_limited_count"])
        self.assertEqual(4, report["exchangeable_standard_count"])
        self.assertEqual(9, report["limited_pickup_count"])
        self.assertEqual(1, report["non_exchangeable_limited_count"])
        self.assertEqual([139997], report["non_exchangeable_limited_ids"])
        self.assertEqual([1, 100], report["limited_rate_total_ratio"])
        self.assertEqual([1, 900], report["limited_rate_each_ratio"])
        self.assertEqual(2, report["page_kind"])
        self.assertEqual({"single": 3, "ten": 4}, report["ticket_exec_types"])
        self.assertFalse(report["writes_live"])

        already_fixed = dict(compiled)
        with self.assertRaisesRegex(ValueError, "source gacha contract drift"):
            repair_gacha_contract(
                already_fixed, expected_start_date=old_date
            )


if __name__ == "__main__":
    unittest.main()

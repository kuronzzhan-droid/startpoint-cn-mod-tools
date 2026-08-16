#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sealed-source and whole-image tests for thunder-dragon hotfix 1.1.6."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
import zlib
import io
from fractions import Fraction
from pathlib import Path

from PIL import Image

import wf_assets
import wf_abyss_gacha_contract as gacha_contract
import wf_abyss_gacha_pool as pool_contract
import wf_mod_tool as core
from wf_summer_thunder_ability_compile import build_summer_thunder_ability_rows

try:
    import wf_thunder_hotfix_package as package
    import wf_thunder_hotfix_package_sources as sources
except ImportError:
    package = None
    sources = None


TOOL_ROOT = Path(__file__).resolve().parents[1]
SOURCE_WORKSPACE = (
    TOOL_ROOT / "work" / "character_packs"
    / "cnmod_thunder_dragon_ascendant_abyss_gacha"
)
BUILD_ROOT = (
    TOOL_ROOT / "work" / "builds" / "cnmod_thunder_dragon_ascendant"
)


@unittest.skipUnless(
    SOURCE_WORKSPACE.exists() and BUILD_ROOT.exists(),
    "local sealed 1.1.0 production inputs are unavailable",
)
class ThunderHotfixPackageTests(unittest.TestCase):
    def _require_modules(self):
        if package is None or sources is None:
            self.fail("thunder hotfix package modules are missing")

    def _compile(self):
        self._require_modules()
        source = sources.load_sealed_source_workspace(SOURCE_WORKSPACE)
        donor = sources.load_locked_donor_template(BUILD_ROOT)
        return source, package.compile_hotfix_package(
            source, donor, generator_git_head="a" * 40
        )

    def test_builds_full_116_replacement_with_banners_and_nine_pickups(self):
        source, image = self._compile()
        audit = package.audit_hotfix_package(image)
        self.assertEqual("1.1.6", image.manifest["package_version"])
        self.assertEqual("1.4.325", image.manifest["requires_client_base"])
        self.assertEqual(107, audit["payload_count"])
        self.assertEqual(39, audit["table_claim_count"])
        self.assertEqual({
            "common": 68, "medium": 26, "android": 2, "server": 11,
        }, audit["root_counts"])
        self.assertEqual(17, audit["changed_payload_count"])
        self.assertEqual(2, audit["added_payload_count"])
        self.assertEqual(88, audit["unchanged_payload_count"])
        self.assertEqual(
            list(package.CHANGED_PAYLOADS), audit["changed_payloads"]
        )
        self.assertEqual(list(package.ADDED_PAYLOADS), audit["added_payloads"])
        self.assertEqual(source.manifest["tables"], image.manifest["tables"])
        self.assertEqual(
            list(package.CURRENT_SHARED_ASSET_BASELINE),
            image.manifest["snapshot"]["accepted_asset_replacements"],
        )
        for replacement in package.CURRENT_SHARED_ASSET_BASELINE:
            raw = source.roots[replacement["root"]][replacement["logical_path"]]
            self.assertEqual(replacement["before_size"], len(raw))
            self.assertEqual(
                replacement["before_sha256"],
                hashlib.sha256(raw).hexdigest(),
                replacement["logical_path"],
            )
        acceptance = image.source_report["acceptance"]
        self.assertEqual(9, acceptance["gacha_limited_pickup_count"])
        self.assertEqual([1, 100], acceptance["gacha_limited_rate_total_ratio"])
        self.assertEqual([1, 900], acceptance["gacha_limited_rate_each_ratio"])
        self.assertEqual(8, acceptance["gacha_exchangeable_limited_count"])
        self.assertEqual(
            [139997], acceptance["gacha_non_exchangeable_limited_ids"]
        )
        for root in package.ROOT_NAMES:
            for logical, raw in source.roots[root].items():
                if (root, logical) not in package.CHANGED_PAYLOADS:
                    self.assertEqual(raw, image.roots[root][logical])

        runtime = json.loads(image.roots["server"]["gacha.json"])["990001"]
        self.assertEqual(2, runtime["pageKind"])
        self.assertEqual([50, 250, 700], runtime["rankRates"]["normal"])
        self.assertEqual(4, runtime["guaranteeRarity"])
        master = core.read_orderedmap_file_from_bytes(
            image.roots["common"][gacha_contract.GACHA_MASTER_LOGICAL]
        )
        self.assertEqual(
            "true",
            core.read_csv_lines(master[gacha_contract.GACHA_KEY])[0][44],
        )
        self.assertTrue(runtime["pool"]["2"])
        self.assertTrue(runtime["pool"]["3"])
        limited = [item for item in runtime["pool"]["1"] if item["id"] in {
            129999, 139997, 139998, 139999, 149998,
            149999, 169998, 169999, 179999,
        }]
        self.assertEqual(9, len(limited))
        self.assertEqual(
            [139997],
            [item["id"] for item in limited if not item["isExchangeable"]],
        )
        self.assertEqual(
            8, sum(1 for item in limited if item["isExchangeable"])
        )
        self.assertTrue(all(item["isRateUp"] for item in limited))
        self.assertTrue(all(item["isLimited"] for item in limited))
        exchange_standard = [
            item for item in runtime["pool"]["1"]
            if item["id"] in set(gacha_contract.STANDARD_EXCHANGE_CHARACTER_IDS)
        ]
        self.assertEqual(4, len(exchange_standard))
        self.assertTrue(all(item["isExchangeable"] for item in exchange_standard))
        self.assertTrue(all(not item["isRateUp"] for item in exchange_standard))
        self.assertTrue(all(not item["isLimited"] for item in exchange_standard))
        standard = [
            item for item in runtime["pool"]["1"]
            if item not in limited and item not in exchange_standard
        ]
        self.assertTrue(standard)
        self.assertTrue(all(not item["isExchangeable"] for item in standard))
        five_weight = sum(item["odds"] for item in runtime["pool"]["1"])
        self.assertTrue(all(
            abs(1 / 900 - 0.05 * item["odds"] / five_weight) < 1e-12
            for item in limited
        ))
        self.assertAlmostEqual(
            0.01,
            0.05 * sum(item["odds"] for item in limited) / five_weight,
        )
        self.assertAlmostEqual(
            0.04,
            0.05 * sum(
                item["odds"] for item in (*standard, *exchange_standard)
            ) / five_weight,
        )
        self.assertEqual(
            (Fraction(1, 100), Fraction(1, 900)),
            pool_contract.pickup_rates(runtime["pool"]),
        )
        self.assertTrue(all(
            not item["isExchangeable"] and not item["isRateUp"]
            for rank in ("2", "3") for item in runtime["pool"][rank]
        ))
        note = zlib.decompress(
            image.roots["common"][
                "rich_text/cnmod_abyss_limited_gacha_note.html.deflate"
            ],
            -15,
        ).decode("utf-8")
        self.assertIn("★5角色总出现概率为5%", note)
        self.assertIn("9名深渊限定角色合计出现概率为1%", note)
        self.assertIn("泳皇女EX（莉莉丝）不可用兑换点数兑换", note)
        self.assertIn("各需250点兑换", note)
        self.assertEqual(2, note.count("250点兑换"))
        self.assertNotIn("各需50点兑换", note)
        self.assertNotIn("0.5%", note)

        portrait = image.roots["medium"][
            gacha_contract.TOP_BANNER_PAYLOAD_LOGICAL
        ]
        decoded = wf_assets.png_decode(portrait)
        with Image.open(io.BytesIO(decoded)) as banner:
            self.assertEqual((1440, 1789), banner.size)
            self.assertEqual("RGBA", banner.mode)

        self.assertEqual(
            source.roots["common"][gacha_contract.LIST_BANNER_LOGICAL],
            image.roots["common"][gacha_contract.LIST_BANNER_LOGICAL],
        )
        list_banner = image.roots["common"][
            gacha_contract.LIST_BANNER_PAYLOAD_LOGICAL
        ]
        with Image.open(io.BytesIO(wf_assets.png_decode(list_banner))) as banner:
            self.assertEqual((510, 180), banner.size)
            self.assertEqual("RGBA", banner.mode)

    def test_recompiles_character_values_and_concise_skill_description(self):
        _source, image = self._compile()
        expected = build_summer_thunder_ability_rows()

        flat_contracts = {
            "master/ability/ability.orderedmap": expected["ability"],
            "master/ability/leader_ability.orderedmap": {
                "139998": expected["leader_ability"]["139998"]
            },
            "master/character/unique_condition.orderedmap": {
                "139998": [expected["unique_condition"]["139998"]]
            },
        }
        for logical, expected_rows in flat_contracts.items():
            decoded = core.read_orderedmap_file_from_bytes(image.roots["common"][logical])
            for key, rows in expected_rows.items():
                self.assertEqual(rows, core.read_csv_lines(decoded[key]), f"{logical}:{key}")

        description = (
            "向前方释放由中心扩散的黄蓝雷波，对扇形范围内的敌人造成雷属性伤害"
            "（合计55倍／55段），并赋予自身「雷电增幅」效果（10秒）。"
        )
        client_text = core.read_orderedmap_file_from_bytes(
            image.roots["common"]["master/character/character_text.orderedmap"]
        )
        client_row = core.read_csv_lines(client_text["139998"])[0]
        server_row = json.loads(
            image.roots["server"]["cdndata/character_text.json"]
        )["139998"][0]
        self.assertEqual(description, client_row[5])
        self.assertEqual(description, client_row[7])
        self.assertEqual(client_row, server_row)
        self.assertNotIn("额外乘区", description)

        action = core.load_nested_table_bytes(
            image.roots["common"]["master/skill/action_skill.orderedmap"],
            "master/skill/action_skill.orderedmap",
        )
        for row_text in action.rows[package.CODE_NAME].text_rows().values():
            self.assertEqual(description, core.read_csv_lines(row_text)[0][1])

    def test_rejects_source_payload_and_donor_drift(self):
        self._require_modules()
        source = sources.load_sealed_source_workspace(SOURCE_WORKSPACE)
        donor = sources.load_locked_donor_template(BUILD_ROOT)
        bad_roots = {
            root: dict(files) for root, files in source.roots.items()
        }
        logical = package.CHANGED_PAYLOADS[0][1]
        bad_roots["common"][logical] += b"drift"
        drifted = source.__class__(
            roots=bad_roots,
            manifest=source.manifest,
            source_locks=source.source_locks,
            workspace_input_sha256=source.workspace_input_sha256,
            manifest_sha256=source.manifest_sha256,
            evidence_sha256=source.evidence_sha256,
        )
        with self.assertRaisesRegex(package.PackageAssemblyError, "source payload"):
            package.compile_hotfix_package(
                drifted, donor, generator_git_head="a" * 40
            )

        donor_files = dict(donor.files)
        first = next(iter(donor_files))
        donor_files[first] += b"drift"
        bad_donor = donor.__class__(
            files=donor_files,
            report_sha256=donor.report_sha256,
            source_store=donor.source_store,
            input_sha256=donor.input_sha256,
        )
        with self.assertRaisesRegex(package.PackageAssemblyError, "donor"):
            package.compile_hotfix_package(
                source, bad_donor, generator_git_head="a" * 40
            )

    def test_audit_rejects_relabelled_extra_change(self):
        _source, image = self._compile()
        roots = {root: dict(files) for root, files in image.roots.items()}
        logical = "character/cnmod_thunder_dragon_ascendant/ui/square_0.png"
        roots["medium"][logical] += b"unexpected"
        mutated = image.__class__(roots, image.manifest, image.source_report)
        with self.assertRaisesRegex(
            package.PackageAssemblyError, "payload binding|unexpected change"
        ):
            package.audit_hotfix_package(mutated)


if __name__ == "__main__":
    unittest.main()

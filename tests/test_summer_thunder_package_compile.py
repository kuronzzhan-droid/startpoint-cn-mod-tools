#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure orchestration gates for the summer-thunder production package."""

from __future__ import annotations

import tempfile
import unittest
import zlib
from pathlib import Path

import wf_dsl
import wf_mod_tool as core
import wf_summer_thunder_package_compile as module
from wf_summer_thunder_package_assemble import PackageAssemblyError


def _flat(logical: str, rows: dict[str, bytes]) -> bytes:
    return core.build_orderedmap(
        core.OrderedMap(logical, list(rows), list(rows.values()), Path("<test>"))
    )


def _amf(value) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    raw = wf_dsl.encode_amf3(value)
    return compressor.compress(raw) + compressor.flush()


class CleanReleaseClaimTests(unittest.TestCase):
    def test_scaffold_rebase_drops_unrelated_authoring_wip(self):
        logical = "master/character/character.orderedmap"
        claim = {
            "root": "common",
            "logical_path": logical,
            "codec_id": "flat",
            "outer_keys": ["139998"],
            "inner_keys": [],
            "semantic_claims": [],
        }
        clean = _flat(logical, {"1": b"official"})
        authoring = _flat(
            logical,
            {"1": b"unrelated user WIP", "139998": b"locked scaffold"},
        )
        rebased = module.rebase_claimed_scaffold(clean, authoring, claim)
        rows = core.read_orderedmap_file_from_bytes(rebased)
        self.assertEqual("official", rows["1"])
        self.assertEqual("locked scaffold", rows["139998"])

    def test_only_declared_outer_rows_may_differ_from_clean_release(self):
        logical = "master/character/character.orderedmap"
        claim = {
            "root": "common",
            "logical_path": logical,
            "codec_id": "flat",
            "outer_keys": ["139998"],
            "inner_keys": [],
            "semantic_claims": [],
        }
        clean = _flat(logical, {"1": b"official"})
        candidate = _flat(
            logical, {"1": b"official", "139998": b"owned replacement"}
        )
        report = module.validate_claimed_table_rebase(clean, candidate, claim)
        self.assertEqual(["139998"], report["owned_added"])
        self.assertEqual(0, report["nonowned_changes"])

        drifted = _flat(logical, {"1": b"drift", "139998": b"owned replacement"})
        with self.assertRaisesRegex(PackageAssemblyError, "non-owned"):
            module.validate_claimed_table_rebase(clean, drifted, claim)


class EffectRuntimeClosureTests(unittest.TestCase):
    def test_parts_texture_references_must_all_exist_in_loader_atlas(self):
        base = (
            "battle/effect/skill_unique/cnmod_thunder_dragon_ascendant/"
            "fan_lightning"
        )
        files = {
            f"{base}/fan_lightning_wave.parts.amf3.deflate": _amf(
                {"i": [{"p": f"{base}/.gen/fan_lightning_wave/f00"}], "t": []}
            ),
            f"{base}/fan_lightning.atlas.amf3.deflate": _amf(
                [{"n": f"{base}/.gen/fan_lightning_wave/f00"}]
            ),
        }
        report = module.validate_effect_runtime_texture_closure(files)
        self.assertEqual(1, report["texture_reference_count"])
        self.assertEqual([], report["missing_textures"])

        files[f"{base}/fan_lightning.atlas.amf3.deflate"] = _amf([])
        with self.assertRaisesRegex(PackageAssemblyError, "missing textures"):
            module.validate_effect_runtime_texture_closure(files)


class InputBoundaryTests(unittest.TestCase):
    def test_clean_release_store_is_a_distinct_isolated_store(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build = root / "work" / "builds" / module.PACKAGE_ID
            authoring = (
                root / "work" / "stores" / f"{module.PACKAGE_ID}_current"
                / "production" / "upload"
            )
            clean = (
                root / "work" / "stores" / "cnmod_thunder_dragon_release_base"
                / "production" / "upload"
            )
            server = build / "server_shadow" / "assets"
            for path in (build, authoring, clean, server):
                path.mkdir(parents=True)
            validated = module.validate_isolated_inputs(
                module.ProductionInputs(build, authoring, clean, server),
                tool_root=root,
            )
            self.assertEqual(clean.resolve(), validated.clean_release_store)

            self_claimed = (
                root / "work" / "stores" / "self_claimed_1.4.346"
                / "production" / "upload"
            )
            self_claimed.mkdir(parents=True)
            with self.assertRaisesRegex(PackageAssemblyError, "locked release-base store"):
                module.validate_isolated_inputs(
                    module.ProductionInputs(build, authoring, self_claimed, server),
                    tool_root=root,
                )

            with self.assertRaisesRegex(PackageAssemblyError, "distinct"):
                module.validate_isolated_inputs(
                    module.ProductionInputs(build, authoring, authoring, server),
                    tool_root=root,
                )


if __name__ == "__main__":
    unittest.main()

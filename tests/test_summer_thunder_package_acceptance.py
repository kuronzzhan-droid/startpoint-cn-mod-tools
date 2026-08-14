#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Package-level UI/effect integration acceptance tests."""

from __future__ import annotations

import unittest
from pathlib import Path

import wf_action_skill_compile as action_compile
import wf_mod_tool as core
import wf_quest_lib as quest
import wf_summer_thunder_master_compile as master_compile
import wf_summer_thunder_package_acceptance as module
from wf_summer_thunder_package_contract import PackageAssemblyError


VISUAL_EVIDENCE = {
    "portrait_selection_sha256": "5a3e0ad0ee0cb86383379aad933a1747f04f90fb51a16dd526e6a4d7b833f4ad",
    "framing_audit_sha256": "eb87eaa399f5180daf5014fc2c61822bb372a973049db497c899e9aa638dcc76",
    "contact_sha256": {
        "accepted_pair_framing_boxes_contact.png": "c575cd4bffef305e636b87fffc790169fb624d3dad6f63775dfc1312f1f5869f",
        "skill_cutin_qa_contact.png": "d3bc433b5e8952d6cc5325b20fb80fb6e4098f658e70fa60c711d4a240fa25f7",
        "ui_derivatives_contact.png": "62eb94a88eda02d8a172175b9e15b718b5235e4a64f672f7b0a94408716889f3",
    },
    "user_approved_locked_pair": True,
    "writes_live": False,
}


def _raw_outer(logical: str, rows: dict[str, bytes]) -> bytes:
    return core.build_orderedmap_raw_rows(
        core.OrderedMap(logical, list(rows), list(rows.values()), Path("<test>"))
    )


def _flat(logical: str, rows: dict[str, bytes]) -> bytes:
    return core.build_orderedmap(
        core.OrderedMap(logical, list(rows), list(rows.values()), Path("<test>"))
    )


def _master_files() -> dict[str, bytes]:
    key = str(module.CHARACTER_ID)
    return {
        master_compile.CHARACTER_IMAGE_LOGICAL: _raw_outer(
            master_compile.CHARACTER_IMAGE_LOGICAL,
            {key: quest.build_node(master_compile.IMAGE_ROWS[master_compile.CHARACTER_IMAGE_LOGICAL])},
        ),
        master_compile.FULL_SHOT_LOGICAL: _raw_outer(
            master_compile.FULL_SHOT_LOGICAL,
            {key: quest.build_node(master_compile.IMAGE_ROWS[master_compile.FULL_SHOT_LOGICAL])},
        ),
        master_compile.TRIMMED_IMAGE_LOGICAL: _flat(
            master_compile.TRIMMED_IMAGE_LOGICAL,
            {logical: row.encode("utf-8") for logical, row in master_compile.TRIM_ROWS.items()},
        ),
    }


def _ui_report() -> dict:
    return {
        "package_manifest_eligible": False,
        "compiler": {
            "png": {
                "master_sha256": {
                    "0": "ab842d15fb2a9e70162a86f2291a4cda5191456be276aeabfd59f65e75b27dac",
                    "1": "cb553428246fe1cd12b11b0bbba7523360ff06ea9f976b3e1d97492a03ca8eed",
                }
            }
        },
        "skill_cutin_qa": {
            "0": {"size": [1024, 512], "problems": []},
            "1": {"size": [1024, 512], "problems": []},
        },
        "writes_live": False,
    }


def _effect_report() -> dict:
    return {
        "package_manifest_eligible": False,
        "contains_character": False,
        "contains_scene": False,
        "contains_powerflip": False,
        "writes_live": False,
    }


class PackageAcceptanceTests(unittest.TestCase):
    def test_visual_three_table_and_55_hit_effect_gates_close_upstream_holds(self):
        result = module.build_package_acceptance(
            ui_report=_ui_report(),
            visual_evidence=VISUAL_EVIDENCE,
            master_files=_master_files(),
            effect_report=_effect_report(),
            effect_closure={
                "texture_reference_count": 10,
                "atlas_record_count": 10,
                "missing_textures": [],
            },
            action_files=action_compile.compile_summer_thunder_dragon_action_skills(),
        )
        self.assertTrue(result["package_manifest_eligible"])
        self.assertEqual(3, result["ui"]["framing_table_count"])
        self.assertEqual(55, result["effect"]["hit_count"])
        self.assertEqual(2, result["effect"]["action_program_count"])

    def test_visual_evidence_or_framing_drift_is_rejected(self):
        drifted_visual = dict(VISUAL_EVIDENCE)
        drifted_visual["portrait_selection_sha256"] = "0" * 64
        with self.assertRaisesRegex(PackageAssemblyError, "visual QA evidence"):
            module.build_package_acceptance(
                ui_report=_ui_report(), visual_evidence=drifted_visual,
                master_files=_master_files(), effect_report=_effect_report(),
                effect_closure={"texture_reference_count": 10, "atlas_record_count": 10, "missing_textures": []},
                action_files=action_compile.compile_summer_thunder_dragon_action_skills(),
            )

        master_files = _master_files()
        master_files[master_compile.TRIMMED_IMAGE_LOGICAL] = _flat(
            master_compile.TRIMMED_IMAGE_LOGICAL, {},
        )
        with self.assertRaisesRegex(PackageAssemblyError, "three-table framing"):
            module.build_package_acceptance(
                ui_report=_ui_report(), visual_evidence=VISUAL_EVIDENCE,
                master_files=master_files, effect_report=_effect_report(),
                effect_closure={"texture_reference_count": 10, "atlas_record_count": 10, "missing_textures": []},
                action_files=action_compile.compile_summer_thunder_dragon_action_skills(),
            )

    def test_effect_payload_hash_or_runtime_closure_drift_is_rejected(self):
        actions = action_compile.compile_summer_thunder_dragon_action_skills()
        first = next(iter(actions))
        actions[first] += b"drift"
        with self.assertRaisesRegex(PackageAssemblyError, "ActionDSL identity"):
            module.build_package_acceptance(
                ui_report=_ui_report(), visual_evidence=VISUAL_EVIDENCE,
                master_files=_master_files(), effect_report=_effect_report(),
                effect_closure={"texture_reference_count": 10, "atlas_record_count": 10, "missing_textures": []},
                action_files=actions,
            )

        with self.assertRaisesRegex(PackageAssemblyError, "effect runtime closure"):
            module.build_package_acceptance(
                ui_report=_ui_report(), visual_evidence=VISUAL_EVIDENCE,
                master_files=_master_files(), effect_report=_effect_report(),
                effect_closure={"texture_reference_count": 10, "atlas_record_count": 9, "missing_textures": ["x"]},
                action_files=action_compile.compile_summer_thunder_dragon_action_skills(),
            )


if __name__ == "__main__":
    unittest.main()

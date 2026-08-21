#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locked 1.4.346 release-base identity tests."""

from __future__ import annotations

import json
import unittest

import wf_summer_thunder_package_base as module
from wf_summer_thunder_package_contract import PackageAssemblyError


PROFILE = {
    "active": "cn",
    "profiles": {
        "cn": {
            "label": "国服(雷霆)",
            "res_version": "1.4.346",
            "server_dir": r"D:\WF\startpoint-cn",
            "cdndata": r"D:\WF\startpoint-cn\assets\cdndata",
            "store": (
                r"D:\WF\wf-mod-tools\work\stores\cnmod_thunder_dragon_release_base"
                r"\production\upload"
            ),
        }
    },
}

RECEIPT = {
    "ok": True,
    "tail": "1.4.346",
    "files": 138750,
    "bytes": 10320258973,
    "rejected": 0,
    "per_root": {
        "common": {"files": 114174, "bytes": 6789216247},
        "medium": {"files": 23558, "bytes": 3443375458},
        "android": {"files": 1018, "bytes": 87667268},
    },
    "unreachable_edges": 0,
    "unreachable_samples": [],
    "max_visible_version": "1.4.346",
    "chain_issues": [],
}

CLEAN_TABLE_SHA256 = {
    "master/ability/ability.orderedmap": "0ac8dabdecaac7b433f6e2207cebcace1445355626e19e1c3f6b120f98f64ae7",
    "master/ability/leader_ability.orderedmap": "beb44eb4074abda41ec3c3857a14e0d7fdb74720d1b6a55c250308248954af9f",
    "master/character/character.orderedmap": "19663638e769e7afcb7a99ed5463f8db0c7fdb8c0a573a550f60442917668b65",
    "master/character/character_gacha_sound.orderedmap": "64db627a93b355d5e9ab8edb5a59a4106ae06f56e66457777c69954d54557a81",
    "master/character/character_speech.orderedmap": "fcbc84ef68e542b0ea04cee9cf07cf8c492b74c0ef02c8dd173528806c67292d",
    "master/character/character_status.orderedmap": "d1b5ff66ba9dc0c2ce2ce33908f0b2b8002b01b12f85ba218ed58a87a3533485",
    "master/character/character_text.orderedmap": "b2fc6a4d937a4eee74864235319cc4421163a29ca658b37458d1db71b6804929",
    "master/character/full_shot_image_attribute.orderedmap": "c3f883dcca299f2006533998d36b7ba6f2763f44b930f8fb86ebebbea84cbb33",
    "master/character/unique_condition.orderedmap": "eabbfc98d0bd52b46b5c683cedd197b9997848c40b3e1ced5068ffd376abe2fe",
    "master/generated/character_image.orderedmap": "299de6b9e43e70f57e1c37f8f4b9877ac57b95715438354c9f8b823803222ebe",
    "master/generated/mana_board.orderedmap": "82b8c6114c9f0e9f7d915edaf2958760d31c909c8efb1702574a7e5bce812379",
    "master/generated/trimmed_image.orderedmap": "6601e2ae98a6e8c5201da2302632448454bdba43bf1959128c2a9239678eb57b",
    "master/mana_board/mana_board2_open_condition.orderedmap": "be686b93e25b690931f7cf1e5958689c1a4ca1d9834c2c8bae1836619e3191e6",
    "master/mana_board/mana_node.orderedmap": "b705e6a717e8096a5bc0be558c2fc11578d2206d2aef19e751131ab62d8b88cb",
    "master/mana_board/upskill.orderedmap": "ab06cea316778d79cdfbad8a58a71f9650aa50dbf7ac3d283a13ebd7f7dea8cc",
    "master/skill/action_skill.orderedmap": "4872d1a0072508ce458e6ecad3c5e46ac56871d3e5257dc51c1fb9a16634873f",
    "master/skill_preview/skill_preview_character.orderedmap": "124201f1b0e28f333e05522dcc8a4e578be6e4bc948b1be0baec08f0bf0fac4c",
    "master/stance_detail/character_stance_detail.orderedmap": "45b679d2cd6e7e272ffe7522a5a1d653535c1532ffe7f13ade72b1878c2c0218",
}


def _raw(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


class ReleaseBaseIdentityTests(unittest.TestCase):
    def test_exact_profile_receipt_and_all_eighteen_tables_are_bound(self):
        report = module.validate_release_base_evidence(
            _raw(PROFILE), b"progress\n" + _raw(RECEIPT) + b"\n", b"",
            CLEAN_TABLE_SHA256,
        )
        self.assertEqual("1.4.346", report["client_base"])
        self.assertEqual(18, report["table_count"])
        self.assertEqual(138750, report["materialize_receipt"]["files"])
        self.assertFalse(report["writes_live"])

    def test_self_claimed_version_or_one_table_drift_is_rejected(self):
        profile = json.loads(json.dumps(PROFILE))
        profile["profiles"]["cn"]["res_version"] = "1.4.346-self-claimed"
        with self.assertRaisesRegex(PackageAssemblyError, "profile identity"):
            module.validate_release_base_evidence(
                _raw(profile), _raw(RECEIPT), b"", CLEAN_TABLE_SHA256,
            )

        drifted = dict(CLEAN_TABLE_SHA256)
        drifted["master/ability/ability.orderedmap"] = "0" * 64
        with self.assertRaisesRegex(PackageAssemblyError, "clean table identity"):
            module.validate_release_base_evidence(
                _raw(PROFILE), _raw(RECEIPT), b"", drifted,
            )

    def test_failed_materialize_or_stderr_is_rejected(self):
        failed = dict(RECEIPT)
        failed["ok"] = False
        with self.assertRaisesRegex(PackageAssemblyError, "materialize receipt"):
            module.validate_release_base_evidence(
                _raw(PROFILE), _raw(failed), b"", CLEAN_TABLE_SHA256,
            )
        with self.assertRaisesRegex(PackageAssemblyError, "stderr"):
            module.validate_release_base_evidence(
                _raw(PROFILE), _raw(RECEIPT), b"unexpected", CLEAN_TABLE_SHA256,
            )


if __name__ == "__main__":
    unittest.main()

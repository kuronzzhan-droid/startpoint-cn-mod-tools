#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locked identity for the verified CN 1.4.346 release-base store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from wf_summer_thunder_package_contract import PackageAssemblyError


PROFILE_RELATIVE = "profiles-release-base.json"
RECEIPT_STDOUT_RELATIVE = "logs/materialize-release-base.stdout.log"
RECEIPT_STDERR_RELATIVE = "logs/materialize-release-base.stderr.log"
LOCKED_PROFILE_IDENTITY_SHA256 = (
    "de84127cd0a6c20e932d7214b010121bd51413193aee42a925b5b648a8228f57"
)
LOCKED_RECEIPT_IDENTITY_SHA256 = (
    "258842c4d14883aaba4844e4aaf0d5abe2ecaf909145d6f15ffe57fe25330f0f"
)
LOCKED_CLEAN_TABLE_SHA256 = {
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


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON value: {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise PackageAssemblyError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise PackageAssemblyError(f"{label} must be a JSON object")
    return value


def validate_release_base_evidence(
    profile_raw: bytes,
    receipt_stdout_raw: bytes,
    receipt_stderr_raw: bytes,
    clean_table_sha256: Mapping[str, str],
) -> dict[str, Any]:
    """Bind the clean store to its profile, materialize receipt, and 18 tables."""

    profile = _json(profile_raw, "release-base profile")
    if _sha256(_canonical(profile)) != LOCKED_PROFILE_IDENTITY_SHA256:
        raise PackageAssemblyError("release-base profile identity drift")
    if receipt_stderr_raw:
        raise PackageAssemblyError("release-base materialize stderr is not empty")
    nonempty = [line for line in receipt_stdout_raw.splitlines() if line.strip()]
    if not nonempty:
        raise PackageAssemblyError("release-base materialize receipt is absent")
    receipt = _json(nonempty[-1], "release-base materialize receipt")
    if _sha256(_canonical(receipt)) != LOCKED_RECEIPT_IDENTITY_SHA256:
        raise PackageAssemblyError("release-base materialize receipt identity drift")
    actual_tables = dict(clean_table_sha256)
    if actual_tables != LOCKED_CLEAN_TABLE_SHA256:
        missing = sorted(set(LOCKED_CLEAN_TABLE_SHA256) - set(actual_tables))
        extra = sorted(set(actual_tables) - set(LOCKED_CLEAN_TABLE_SHA256))
        changed = sorted(
            logical for logical in set(actual_tables) & set(LOCKED_CLEAN_TABLE_SHA256)
            if actual_tables[logical] != LOCKED_CLEAN_TABLE_SHA256[logical]
        )
        raise PackageAssemblyError(
            "clean table identity drift: "
            f"missing={missing}, extra={extra}, changed={changed}"
        )
    return {
        "schema_version": 1,
        "client_base": "1.4.346",
        "profile_relative": PROFILE_RELATIVE,
        "profile_identity_sha256": LOCKED_PROFILE_IDENTITY_SHA256,
        "profile_raw_sha256": _sha256(profile_raw),
        "materialize_stdout_relative": RECEIPT_STDOUT_RELATIVE,
        "materialize_stderr_relative": RECEIPT_STDERR_RELATIVE,
        "materialize_receipt_sha256": LOCKED_RECEIPT_IDENTITY_SHA256,
        "materialize_stdout_sha256": _sha256(receipt_stdout_raw),
        "materialize_stderr_sha256": _sha256(receipt_stderr_raw),
        "materialize_receipt": receipt,
        "clean_table_sha256": actual_tables,
        "table_count": 18,
        "writes_live": False,
    }


def load_release_base_evidence(
    build_root: Path,
    clean_table_bytes: Mapping[str, bytes],
) -> dict[str, Any]:
    """Load only the locked receipt paths and validate the supplied table bytes."""

    build = Path(build_root)
    try:
        profile_raw = (build / PROFILE_RELATIVE).read_bytes()
        stdout_raw = (build / RECEIPT_STDOUT_RELATIVE).read_bytes()
        stderr_raw = (build / RECEIPT_STDERR_RELATIVE).read_bytes()
    except OSError as exc:
        raise PackageAssemblyError("release-base materialize evidence is unreadable") from exc
    hashes = {logical: _sha256(bytes(raw)) for logical, raw in clean_table_bytes.items()}
    return validate_release_base_evidence(
        profile_raw, stdout_raw, stderr_raw, hashes,
    )


__all__ = [
    "PROFILE_RELATIVE", "RECEIPT_STDOUT_RELATIVE", "RECEIPT_STDERR_RELATIVE",
    "LOCKED_PROFILE_IDENTITY_SHA256", "LOCKED_RECEIPT_IDENTITY_SHA256",
    "LOCKED_CLEAN_TABLE_SHA256", "validate_release_base_evidence",
    "load_release_base_evidence",
]

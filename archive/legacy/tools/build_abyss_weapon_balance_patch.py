#!/usr/bin/env python
"""Build the deterministic 1.4.105 -> 1.4.106 abyss weapon balance patch.

This repair builder is intentionally isolated from wf_publish.py and the active
CN store. It validates the pinned bridge archive and two official backup
payloads, copies the validated backups into an OS temp directory, and writes
one repository asset-patch archive. The committed archive hash is canonical;
rebuilds on different zlib implementations are validated by decoded table
content because standard zlib and zlib-ng may choose different DEFLATE bytes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import struct
import sys
import tempfile
import zipfile
import zlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
MOD_TOOLS = ROOT / "mod-tools"
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_quest_lib as quest  # noqa: E402


BRIDGE_ARCHIVE = (
    ROOT
    / "assets"
    / "asset-patch"
    / "active"
    / "pinball-1.4.101-1.4.102-1-mod07142258.zip"
)
OUTPUT_ARCHIVE = (
    ROOT
    / "assets"
    / "asset-patch"
    / "active"
    / "pinball-1.4.105-1.4.106-1-abyssbalance0718.zip"
)

BRIDGE_SHA256 = "31c897762d89e6d55064c477dc989d97e30e86a05ecca258e61e44ea90d0f86d"
SOUL_BASELINE_SIZE = 38_313
SOUL_BASELINE_SHA256 = "70dd53d7e1f9078199a017d49c0adb2946ecb6e91abfbc42f4b6a4da4b0a2e1e"
SOUL_CANONICAL_BASELINE_SHA256 = (
    "a464c324f44a9a7a685ec0036bb895e4a0f70ab4e1f0bd1f0a0a1780bfc661df"
)
WAB_BASELINE_SIZE = 3_640
WAB_BASELINE_SHA256 = "b9aa82f7c7483af88f758bcdaeed6474178e57a076d86b660d0bab902996e0ae"

EQUIPMENT_LOGICAL = "master/item/equipment.orderedmap"
SOUL_LOGICAL = "master/ability/ability_soul.orderedmap"
WAB_LOGICAL = (
    "master/equipment_enhancement/equipment_enhancement_ability.orderedmap"
)
ARCHIVE_SHA256 = "e9ec4451ac5b3101f060c74278fd8901b7c207c57f19e313084ff9f9639f7272"
RELEASE_CONTRACT_PATH = (
    MOD_TOOLS / "release-contracts" / "abyss_weapon_balance_v1.json"
)
EXPECTED_CUSTOM_IDS = tuple(str(value) for value in range(8000101, 8000116))


@dataclass(frozen=True)
class HistoricalReleaseContract:
    custom_ids: tuple[str, ...]
    equipment_rows: Mapping[str, str]
    ability_soul_rows: Mapping[str, str]
    equipment_canonical_sha256: str
    equipment_key_sequence_sha256: str
    ability_soul_canonical_sha256: str
    ability_soul_key_sequence_sha256: str


def _require_mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _require_exact_keys(
    value: Mapping[str, object], expected: Iterable[str], field: str
) -> None:
    expected_keys = tuple(expected)
    if tuple(value) != expected_keys:
        raise ValueError(
            f"{field} keys must exactly match the required order: {expected_keys}"
        )


def _require_sha256(value: object, field: str, *, expected: str | None = None) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{field} must be a lowercase 64-character SHA-256")
    if expected is not None and value != expected:
        raise ValueError(f"{field} does not match the pinned release value")
    return value


def _require_csv_leaf(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty CSV string")
    try:
        rows = list(csv.reader(io.StringIO(value), strict=True))
    except csv.Error as exc:
        raise ValueError(f"{field} must be parseable CSV") from exc
    if not rows or any(not row for row in rows):
        raise ValueError(f"{field} must contain non-empty CSV rows")
    return value


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_v1_contract(
    path: Path = RELEASE_CONTRACT_PATH,
) -> HistoricalReleaseContract:
    try:
        raw_document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"release contract could not be read: {path}") from exc

    document = _require_mapping(raw_document, "contract")
    _require_exact_keys(
        document,
        ("schema_version", "published", "custom_ids", "payload_rows"),
        "contract",
    )
    schema_version = document["schema_version"]
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError("schema_version must be the integer 1")

    published = _require_mapping(document["published"], "published")
    _require_exact_keys(
        published,
        (
            "id",
            "status",
            "depends_on",
            "version",
            "archive",
            "archive_sha256",
            "equipment_canonical_sha256",
            "equipment_key_sequence_sha256",
            "ability_soul_canonical_sha256",
            "ability_soul_key_sequence_sha256",
        ),
        "published",
    )
    expected_metadata = {
        "id": "abyss-weapon-balance-v1",
        "status": "published",
        "depends_on": "1.4.105",
        "version": "1.4.106",
        "archive": "pinball-1.4.105-1.4.106-1-abyssbalance0718.zip",
    }
    for field, expected_value in expected_metadata.items():
        if published[field] != expected_value:
            raise ValueError(f"published.{field} does not match the v1 release")
    _require_sha256(
        published["archive_sha256"],
        "archive_sha256",
        expected=ARCHIVE_SHA256,
    )
    equipment_canonical_sha256 = _require_sha256(
        published["equipment_canonical_sha256"],
        "equipment_canonical_sha256",
    )
    equipment_key_sequence_sha256 = _require_sha256(
        published["equipment_key_sequence_sha256"],
        "equipment_key_sequence_sha256",
    )
    ability_soul_canonical_sha256 = _require_sha256(
        published["ability_soul_canonical_sha256"],
        "ability_soul_canonical_sha256",
    )
    ability_soul_key_sequence_sha256 = _require_sha256(
        published["ability_soul_key_sequence_sha256"],
        "ability_soul_key_sequence_sha256",
    )

    custom_ids_value = document["custom_ids"]
    if not isinstance(custom_ids_value, list) or tuple(custom_ids_value) != EXPECTED_CUSTOM_IDS:
        raise ValueError("custom_ids must exactly match 8000101 through 8000115")
    custom_ids = tuple(custom_ids_value)

    payload_rows = _require_mapping(document["payload_rows"], "payload_rows")
    _require_exact_keys(payload_rows, ("equipment", "ability_soul"), "payload_rows")
    equipment_value = _require_mapping(
        payload_rows["equipment"], "payload_rows.equipment"
    )
    ability_soul_value = _require_mapping(
        payload_rows["ability_soul"], "payload_rows.ability_soul"
    )
    _require_exact_keys(
        equipment_value, custom_ids, "payload_rows.equipment"
    )
    _require_exact_keys(
        ability_soul_value, custom_ids, "payload_rows.ability_soul"
    )
    equipment_rows = {
        custom_id: _require_csv_leaf(
            equipment_value[custom_id], f"payload_rows.equipment.{custom_id}"
        )
        for custom_id in custom_ids
    }
    ability_soul_rows = {
        custom_id: _require_csv_leaf(
            ability_soul_value[custom_id],
            f"payload_rows.ability_soul.{custom_id}",
        )
        for custom_id in custom_ids
    }

    return HistoricalReleaseContract(
        custom_ids=custom_ids,
        equipment_rows=MappingProxyType(equipment_rows),
        ability_soul_rows=MappingProxyType(ability_soul_rows),
        equipment_canonical_sha256=equipment_canonical_sha256,
        equipment_key_sequence_sha256=equipment_key_sequence_sha256,
        ability_soul_canonical_sha256=ability_soul_canonical_sha256,
        ability_soul_key_sequence_sha256=ability_soul_key_sequence_sha256,
    )


V1_CONTRACT = load_v1_contract()


def archive_member(logical: str) -> str:
    return f"production/upload/{quest.hashed_rel(logical)}"


EQUIPMENT_MEMBER = archive_member(EQUIPMENT_LOGICAL)
SOUL_MEMBER = archive_member(SOUL_LOGICAL)
WAB_MEMBER = archive_member(WAB_LOGICAL)
ARCHIVE_MEMBERS = (EQUIPMENT_MEMBER, SOUL_MEMBER, WAB_MEMBER)
ZIP_TIMESTAMP = (2026, 7, 18, 0, 0, 0)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def key_sequence_sha256(keys: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for key in keys:
        raw = key.encode("utf-8")
        digest.update(struct.pack("<Q", len(raw)))
        digest.update(raw)
    return digest.hexdigest()


def checked_read(path: Path, *, size: int, digest: str, label: str) -> bytes:
    data = path.read_bytes()
    actual_digest = sha256(data)
    if len(data) != size or actual_digest != digest:
        raise ValueError(
            f"{label} does not match pinned input: "
            f"size={len(data)} sha256={actual_digest}"
        )
    return data


def checked_bridge(path: Path) -> bytes:
    data = path.read_bytes()
    actual_digest = sha256(data)
    if actual_digest != BRIDGE_SHA256:
        raise ValueError(
            f"bridge archive does not match pinned input: sha256={actual_digest}"
        )
    return data


def read_bridge_member(bridge_bytes: bytes, logical: str) -> bytes:
    member = archive_member(logical)
    with zipfile.ZipFile(io.BytesIO(bridge_bytes)) as archive:
        if archive.testzip() is not None:
            raise ValueError("bridge archive failed ZIP integrity validation")
        try:
            return archive.read(member)
        except KeyError as exc:
            raise ValueError(f"bridge archive is missing {member}") from exc


def parse_table(data: bytes, logical: str) -> dict[str, object]:
    table = quest.parse_node(data)
    if not isinstance(table, dict):
        raise ValueError(f"{logical} is not a top-level orderedmap")
    return table


def canonical_node_sha256(node: object) -> str:
    """Hash ordered table content and order independently of compression bytes."""
    digest = hashlib.sha256()

    def visit(value: object) -> None:
        if isinstance(value, str):
            raw = value.encode("utf-8")
            digest.update(b"S")
            digest.update(struct.pack("<Q", len(raw)))
            digest.update(raw)
            return
        if not isinstance(value, dict):
            raise TypeError(
                f"orderedmap node must be str or dict, got {type(value).__name__}"
            )
        digest.update(b"M")
        digest.update(struct.pack("<Q", len(value)))
        for key, child in value.items():
            raw = key.encode("utf-8")
            digest.update(b"K")
            digest.update(struct.pack("<Q", len(raw)))
            digest.update(raw)
            visit(child)

    visit(node)
    return digest.hexdigest()


def build_official_orderedmap(node: object) -> bytes:
    """Serialize with the official ability_soul payload's zlib level 9."""
    if isinstance(node, str):
        return zlib.compress(node.encode("utf-8"), 9) if node else b""
    if not isinstance(node, dict):
        raise TypeError(f"orderedmap node must be str or dict, got {type(node).__name__}")

    key_blob = b""
    row_blob = b""
    pairs: list[tuple[int, int]] = []
    for key, child in node.items():
        key_blob += key.encode("utf-8")
        row_blob += build_official_orderedmap(child)
        pairs.append((len(key_blob), len(row_blob)))
    index = bytearray(struct.pack("<I", len(pairs)))
    for key_end, row_end in pairs:
        index += struct.pack("<II", key_end, row_end)
    index += key_blob
    packed_index = zlib.compress(bytes(index), 9)
    return struct.pack("<I", len(packed_index)) + packed_index + row_blob


def strip_custom_soul_rows(soul_bytes: bytes) -> bytes:
    table = parse_table(soul_bytes, SOUL_LOGICAL)
    custom_ids = set(V1_CONTRACT.custom_ids)
    stripped = {key: value for key, value in table.items() if key not in custom_ids}
    return build_official_orderedmap(stripped)


def build_payloads_from_soul_table(
    bridge_bytes: bytes,
    soul_baseline: dict[str, object],
    wab_baseline_bytes: bytes,
) -> tuple[bytes, bytes, bytes]:
    """Build from an already parsed official soul table."""
    if canonical_node_sha256(soul_baseline) != SOUL_CANONICAL_BASELINE_SHA256:
        raise ValueError("ability_soul baseline does not match canonical content")
    if sha256(wab_baseline_bytes) != WAB_BASELINE_SHA256:
        raise ValueError(
            "equipment_enhancement_ability hash is not pinned official baseline"
        )

    bridge_equipment_bytes = read_bridge_member(bridge_bytes, EQUIPMENT_LOGICAL)
    equipment = parse_table(bridge_equipment_bytes, EQUIPMENT_LOGICAL)
    for custom_id in V1_CONTRACT.custom_ids:
        if custom_id not in equipment:
            raise ValueError(f"bridge equipment is missing historical id {custom_id}")
        equipment[custom_id] = V1_CONTRACT.equipment_rows[custom_id]

    ability_soul = dict(soul_baseline)
    for custom_id in V1_CONTRACT.custom_ids:
        ability_soul[custom_id] = V1_CONTRACT.ability_soul_rows[custom_id]

    if key_sequence_sha256(equipment) != V1_CONTRACT.equipment_key_sequence_sha256:
        raise RuntimeError("historical equipment key order does not match v1 contract")
    if canonical_node_sha256(equipment) != V1_CONTRACT.equipment_canonical_sha256:
        raise RuntimeError("historical equipment content does not match v1 contract")
    if (
        key_sequence_sha256(ability_soul)
        != V1_CONTRACT.ability_soul_key_sequence_sha256
    ):
        raise RuntimeError("historical ability_soul key order does not match v1 contract")
    if (
        canonical_node_sha256(ability_soul)
        != V1_CONTRACT.ability_soul_canonical_sha256
    ):
        raise RuntimeError("historical ability_soul content does not match v1 contract")

    equipment_bytes = quest.build_node(equipment)
    soul_bytes = build_official_orderedmap(ability_soul)

    custom_ids = set(V1_CONTRACT.custom_ids)
    bridge_equipment = parse_table(bridge_equipment_bytes, EQUIPMENT_LOGICAL)
    final_equipment = parse_table(equipment_bytes, EQUIPMENT_LOGICAL)
    bridge_noncustom = [
        (key, value) for key, value in bridge_equipment.items() if key not in custom_ids
    ]
    final_noncustom = [
        (key, value) for key, value in final_equipment.items() if key not in custom_ids
    ]
    if final_noncustom != bridge_noncustom:
        raise RuntimeError("equipment non-custom rows or order changed")
    stripped_soul = parse_table(strip_custom_soul_rows(soul_bytes), SOUL_LOGICAL)
    if canonical_node_sha256(stripped_soul) != canonical_node_sha256(soul_baseline):
        raise RuntimeError("removing custom ability_soul rows did not restore baseline")

    return equipment_bytes, soul_bytes, wab_baseline_bytes


def build_payloads(
    bridge_bytes: bytes, soul_baseline_bytes: bytes, wab_baseline_bytes: bytes
) -> tuple[bytes, bytes, bytes]:
    if sha256(soul_baseline_bytes) != SOUL_BASELINE_SHA256:
        raise ValueError("ability_soul baseline hash is not pinned official baseline")
    soul_baseline = parse_table(soul_baseline_bytes, SOUL_LOGICAL)
    return build_payloads_from_soul_table(
        bridge_bytes, soul_baseline, wab_baseline_bytes
    )


def build_archive_bytes(payloads: tuple[bytes, bytes, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for member, payload in zip(ARCHIVE_MEMBERS, payloads, strict=True):
            info = zipfile.ZipInfo(member, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            archive.writestr(
                info,
                payload,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return output.getvalue()


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as temp_file:
            temp_file.write(data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        Path(temp_name).replace(path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def build_from_paths(
    bridge_path: Path,
    soul_path: Path,
    wab_path: Path,
) -> bytes:
    bridge_bytes = checked_bridge(bridge_path)
    soul_bytes = checked_read(
        soul_path,
        size=SOUL_BASELINE_SIZE,
        digest=SOUL_BASELINE_SHA256,
        label="ability_soul baseline",
    )
    wab_bytes = checked_read(
        wab_path,
        size=WAB_BASELINE_SIZE,
        digest=WAB_BASELINE_SHA256,
        label="equipment_enhancement_ability baseline",
    )
    with tempfile.TemporaryDirectory(prefix="wf-abyss-balance-inputs-") as temp:
        temp_root = Path(temp)
        soul_copy = temp_root / "ability_soul.orderedmap"
        wab_copy = temp_root / "equipment_enhancement_ability.orderedmap"
        soul_copy.write_bytes(soul_bytes)
        wab_copy.write_bytes(wab_bytes)
        return build_archive_bytes(
            build_payloads(
                bridge_bytes,
                soul_copy.read_bytes(),
                wab_copy.read_bytes(),
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge", type=Path, default=BRIDGE_ARCHIVE)
    parser.add_argument("--soul-baseline", type=Path, required=True)
    parser.add_argument("--wab-baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT_ARCHIVE)
    args = parser.parse_args()

    archive_bytes = build_from_paths(
        args.bridge, args.soul_baseline, args.wab_baseline
    )
    write_atomic(args.output, archive_bytes)
    print(
        f"[OK] {args.output} size={len(archive_bytes)} "
        f"sha256={sha256(archive_bytes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strict immutable provenance for the local-live release inventory."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from wf_contract_json import load_json_strict
from wf_release_inventory_contract import InventoryError, validate_logical_path


SCHEMA = "wf-local-baseline-provenance/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
VERSIONS = ("1.4.277", "1.4.311")


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    owner: str
    present: bool
    projection_sha256: str | None


@dataclass(frozen=True, slots=True)
class BaselineEvidence:
    writer: str
    archive_member: str
    size: int
    sha256: str
    table_claims: tuple[ClaimEvidence, ...]
    unclaimed_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ProvenanceMember:
    root: str
    logical_path: str
    owners: tuple[str, ...]
    versions: dict[str, BaselineEvidence | None]

    @property
    def key(self) -> tuple[str, str]:
        return self.root, self.logical_path


@dataclass(frozen=True, slots=True)
class ProvenanceContract:
    contract_id: str
    terminal_contract_id: str
    inventory_sha256: str
    baselines: tuple[str, ...]
    members: tuple[ProvenanceMember, ...]


def _exact(value: object, fields: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InventoryError(f"{label}: must be an object")
    if set(value) != fields:
        raise InventoryError(f"{label}: fields must be exactly {sorted(fields)}")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise InventoryError(f"{label}: invalid sha256")
    return value


def _safe_writer(value: object, label: str) -> str:
    if not isinstance(value, str) or "\\" in value:
        raise InventoryError(f"{label}: unsafe writer")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise InventoryError(f"{label}: unsafe writer")
    if not (
        value.startswith(".cdn/cn/archive-")
        or value.startswith("assets/asset-patch/active/")
    ):
        raise InventoryError(f"{label}: writer is outside frozen archive roots")
    return value


def _claim(value: object, label: str) -> ClaimEvidence:
    if not isinstance(value, dict):
        raise InventoryError(f"{label}: must be an object")
    present = value.get("present")
    expected = {"owner", "present", "projection_sha256"} if present is True else {
        "owner", "present"
    }
    obj = _exact(value, expected, label)
    owner = obj["owner"]
    if not isinstance(owner, str) or not owner:
        raise InventoryError(f"{label}.owner: invalid owner")
    if type(present) is not bool:
        raise InventoryError(f"{label}.present: must be bool")
    digest = _sha(obj["projection_sha256"], label) if present else None
    return ClaimEvidence(owner, present, digest)


def _evidence(value: object, label: str) -> BaselineEvidence:
    if not isinstance(value, dict):
        raise InventoryError(f"{label}: must be an object or null")
    fields = {"writer", "archive_member", "size", "sha256"}
    if "table_claims" in value:
        fields.update({"table_claims", "unclaimed_sha256"})
    obj = _exact(value, fields, label)
    member = validate_logical_path(obj["archive_member"], label)
    size = obj["size"]
    if type(size) is not int or size < 0:
        raise InventoryError(f"{label}.size: invalid size")
    raw_claims = obj.get("table_claims", [])
    if not isinstance(raw_claims, list):
        raise InventoryError(f"{label}.table_claims: must be an array")
    claims = tuple(_claim(item, f"{label}.table_claims") for item in raw_claims)
    if len({claim.owner for claim in claims}) != len(claims):
        raise InventoryError(f"{label}.table_claims: duplicate owner")
    return BaselineEvidence(
        _safe_writer(obj["writer"], label), member, size,
        _sha(obj["sha256"], label), claims,
        (
            _sha(obj["unclaimed_sha256"], f"{label}.unclaimed_sha256")
            if "table_claims" in obj
            else None
        ),
    )


def provenance_sha256(members: tuple[ProvenanceMember, ...]) -> str:
    lines: list[str] = []
    for member in sorted(members, key=lambda item: item.key):
        versions: list[object] = []
        for version in VERSIONS:
            value = member.versions[version]
            versions.append(None if value is None else [
                value.writer, value.archive_member, value.size, value.sha256,
                value.unclaimed_sha256,
            ])
        lines.append(json.dumps(
            [member.root, member.logical_path, ",".join(member.owners), *versions],
            ensure_ascii=False, separators=(",", ":"),
        ))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def parse_provenance(value: object) -> ProvenanceContract:
    obj = _exact(value, {
        "schema", "contract_id", "terminal_contract_id", "inventory_sha256",
        "baselines", "members",
    }, "provenance")
    if obj["schema"] != SCHEMA or obj["baselines"] != list(VERSIONS):
        raise InventoryError("provenance: unsupported schema or baselines")
    for field in ("contract_id", "terminal_contract_id"):
        token = obj[field]
        if not isinstance(token, str) or TOKEN_RE.fullmatch(token) is None:
            raise InventoryError(f"provenance.{field}: invalid token")
    raw_members = obj["members"]
    if not isinstance(raw_members, list) or not raw_members:
        raise InventoryError("provenance.members: must be a non-empty array")
    members: list[ProvenanceMember] = []
    for index, raw in enumerate(raw_members):
        label = f"provenance.members[{index}]"
        item = _exact(raw, {"root", "logical_path", "owners", "versions"}, label)
        root = item["root"]
        if root not in ("common", "medium", "android"):
            raise InventoryError(f"{label}.root: invalid root")
        logical = validate_logical_path(item["logical_path"], label)
        owners = item["owners"]
        if (
            not isinstance(owners, list) or not owners
            or any(not isinstance(owner, str) or not owner for owner in owners)
            or owners != sorted(set(owners))
        ):
            raise InventoryError(f"{label}.owners: must be sorted and unique")
        raw_versions = _exact(item["versions"], set(VERSIONS), f"{label}.versions")
        versions = {
            version: None if raw_versions[version] is None else _evidence(
                raw_versions[version], f"{label}.versions.{version}"
            )
            for version in VERSIONS
        }
        members.append(ProvenanceMember(root, logical, tuple(owners), versions))
    if len({member.key for member in members}) != len(members):
        raise InventoryError("provenance.members: duplicate root/logical_path")
    contract = ProvenanceContract(
        obj["contract_id"], obj["terminal_contract_id"],
        _sha(obj["inventory_sha256"], "provenance.inventory_sha256"),
        VERSIONS, tuple(members),
    )
    if provenance_sha256(contract.members) != contract.inventory_sha256:
        raise InventoryError("provenance.inventory_sha256: digest mismatch")
    return contract


def load_provenance(path: Path) -> ProvenanceContract:
    return parse_provenance(load_json_strict(path, InventoryError, "provenance"))

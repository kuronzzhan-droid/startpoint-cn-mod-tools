#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic release receipt writer and offline verifier for local-live 1.4.312."""
from __future__ import annotations

import hashlib
import io
import json
import re
import stat
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping, cast

import wf_character_pack as character_pack
import wf_local_release_contract as local_contract
import wf_local_server_contract as server_contract
import wf_mod_tool as core
import wf_release_inventory as inventory
import wf_scoped_table_merge as table_merge
from wf_release_inventory_contract import (
    InventoryContract,
    InventoryError,
    InventoryMember,
    MemberKey,
    project_claim,
    projection_sha256,
)


SCHEMA = "wf-local-release-receipt/v1"
ZIP_CAP = 5 << 20
ZIP_TIMESTAMP = (2026, 8, 6, 0, 0, 0)
ZIP_MODE = (stat.S_IFREG | 0o644) << 16
ROOTS = ("common", "medium", "android")
ROOT_PREFIX = {
    "common": "production/upload/",
    "medium": "production/medium_upload/",
    "android": "production/android_upload/",
}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
TAG_RE = re.compile(r"^[a-z0-9]+$")
PATCH_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
RUNTIME_KEYS = frozenset({
    "mtime", "mtime_ns", "ctime", "ctime_ns", "atime", "atime_ns",
    "temp", "tmp", "temp_dir", "temporary_directory", "workspace",
})


class ReceiptError(RuntimeError):
    """Receipt evidence is incomplete, non-deterministic, or inconsistent."""


@dataclass(frozen=True, slots=True)
class ContractBinding:
    role: str
    relative_path: str
    contract_id: str
    raw: bytes


@dataclass(frozen=True, slots=True)
class BaselineDescriptor:
    present: bool
    size: int | None
    sha256: str | None
    writer: str | None
    archive_member: str | None
    unclaimed_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ReleaseContext:
    terminal: InventoryContract
    baselines: Mapping[str, InventoryContract]
    baseline_descriptors: Mapping[str, Mapping[MemberKey, BaselineDescriptor]]
    migration: server_contract.MigrationContract
    contract_bindings: tuple[ContractBinding, ...]
    inventory_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ReleasePolicy:
    release_id: str
    terminal_contract_id: str
    baseline_versions: tuple[str, ...]
    terminal_member_count: int
    unique_path_count: int
    server_member_count: int
    client_migration_count: int
    contract_ids: Mapping[str, str]
    manifest_preimage_sha256: str
    manifest_cdn_version: str
    manifest_preimage_patch_count: int


@dataclass(frozen=True, slots=True)
class ArchiveEvidence:
    root: str
    name: str
    blob: bytes


@dataclass(frozen=True, slots=True)
class EdgeEvidence:
    from_version: str
    to_version: str
    patch_id: str
    tag: str
    baseline: Mapping[MemberKey, bytes | None]
    output: Mapping[MemberKey, bytes]
    archives: tuple[ArchiveEvidence, ...]


@dataclass(frozen=True, slots=True)
class VerificationReport:
    edge_count: int
    path_count_per_edge: int
    claim_count_per_edge: int


LOCAL_CONTRACT_IDS = {
    "terminal": "local-live-terminal-1-4-312",
    "baseline_1_4_277": "local-live-baseline-1-4-277",
    "baseline_1_4_311": "local-live-baseline-1-4-311",
    "provenance": "local-live-baseline-provenance-1-4-312",
    "migration": "local-live-migrations-1-4-312",
}
LOCAL_POLICY = ReleasePolicy(
    "local-live-1-4-312",
    "local-live-terminal-1-4-312",
    ("1.4.277", "1.4.311"),
    257,
    233,
    18,
    1,
    LOCAL_CONTRACT_IDS,
    "8c828497f8fd40a6cf7093001058d0f1c9f1a928e6feb71d48ff0cae4fe8a948",
    "1.4.54",
    13,
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frame(raw: bytes) -> bytes:
    return struct.pack(">Q", len(raw)) + raw


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON constant {value}")


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _json(raw: bytes, label: str) -> object:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise ReceiptError(f"{label}: {error}") from error


def _safe_relative(value: str, label: str) -> str:
    if not value or "\\" in value:
        raise ReceiptError(f"{label}: unsafe relative path")
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    if (
        posix.is_absolute() or windows.is_absolute() or windows.drive
        or any(part in ("", ".", "..") for part in value.split("/"))
        or posix.as_posix() != value
    ):
        raise ReceiptError(f"{label}: absolute or unsafe relative path")
    return value


def _scan_portable(value: object, label: str = "receipt") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in RUNTIME_KEYS:
                raise ReceiptError(f"{label}: runtime field {key!r} is forbidden")
            _scan_portable(child, f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_portable(child, f"{label}[{index}]")
    elif isinstance(value, str):
        windows = PureWindowsPath(value)
        if value.startswith("/") or windows.is_absolute() or windows.drive:
            raise ReceiptError(f"{label}: absolute runtime path is forbidden")


def canonical_receipt(value: object) -> bytes:
    _scan_portable(value)
    try:
        return (
            json.dumps(
                value, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ReceiptError(f"cannot encode receipt: {error}") from error


def parse_receipt(raw: bytes) -> dict[str, object]:
    value = _json(raw, "receipt")
    if not isinstance(value, dict):
        raise ReceiptError("receipt: top level must be an object")
    _scan_portable(value)
    return value


def archive_member_name(root: str, logical_path: str) -> str:
    if root not in ROOT_PREFIX:
        raise ReceiptError(f"invalid client root {root!r}")
    _safe_relative(logical_path, "logical_path")
    digest = core.sha1_path(logical_path)
    return f"{ROOT_PREFIX[root]}{digest[:2]}/{digest[2:]}"


def load_local_context(contract_dir: Path) -> ReleaseContext:
    root = Path(contract_dir)
    try:
        bundle = local_contract.load_bundle(root)
        names = (
            ("terminal", local_contract.TERMINAL_NAME, bundle.terminal.contract_id),
            ("baseline_1_4_277", local_contract.BASELINE_NAMES["1.4.277"], bundle.baselines["1.4.277"].contract_id),
            ("baseline_1_4_311", local_contract.BASELINE_NAMES["1.4.311"], bundle.baselines["1.4.311"].contract_id),
            ("provenance", local_contract.PROVENANCE_NAME, bundle.provenance.contract_id),
            ("migration", local_contract.MIGRATION_NAME, bundle.migrations.contract_id),
        )
        bindings = tuple(
            ContractBinding(role, f"mod-tools/release-contracts/{name}", contract_id, (root / name).read_bytes())
            for role, name, contract_id in names
        )
    except (OSError, InventoryError, server_contract.MigrationError) as error:
        raise ReceiptError(f"cannot load local release contracts: {error}") from error
    descriptors: dict[str, dict[MemberKey, BaselineDescriptor]] = {}
    for version in bundle.baseline_versions:
        descriptors[version] = {}
        for member in bundle.provenance.members:
            evidence = member.versions[version]
            descriptors[version][member.key] = BaselineDescriptor(
                evidence is not None,
                None if evidence is None else evidence.size,
                None if evidence is None else evidence.sha256,
                None if evidence is None else evidence.writer,
                None if evidence is None else evidence.archive_member,
                None if evidence is None else evidence.unclaimed_sha256,
            )
    return ReleaseContext(
        bundle.terminal, bundle.baselines, descriptors, bundle.migrations,
        bindings, bundle.provenance.inventory_sha256,
    )


def _members_by_path(contract: InventoryContract) -> dict[MemberKey, tuple[InventoryMember, ...]]:
    grouped: dict[MemberKey, list[InventoryMember]] = {}
    for member in contract.members:
        grouped.setdefault(member.key, []).append(member)
    return {key: tuple(value) for key, value in grouped.items()}


def _claim_record(member: InventoryMember) -> dict[str, object]:
    result: dict[str, object] = {"owner": member.owner, "kind": member.kind}
    if member.kind == "file":
        result.update({"size": member.size, "sha256": member.sha256})
    else:
        claim = cast(character_pack.TableClaim, member.claim)
        result.update({
            "codec_id": claim.codec_id,
            "outer_keys": list(claim.outer_keys),
            "inner_keys": {outer: list(keys) for outer, keys in claim.inner_keys},
            "projection_sha256": member.projection_sha256,
        })
    return result


def _all_rows(raw: bytes, codec: str, logical: str) -> tuple[tuple[str, str | None, bytes], ...]:
    try:
        if codec in {"flat", "raw_outer"}:
            keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                raw, label=logical, compressed_rows=codec == "flat"
            )
            return tuple((key, None, row) for key, row in zip(keys, rows))
        if codec in {"action_nested", "switched_nested"}:
            outer, chunks = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                raw, label=logical, compressed_rows=False
            )
            result: list[tuple[str, str | None, bytes]] = []
            for outer_key, chunk in zip(outer, chunks):
                inner, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                    chunk, label=f"{logical}:{outer_key}", compressed_rows=True
                )
                result.extend((outer_key, key, row) for key, row in zip(inner, rows))
            return tuple(result)
        if codec == "json_object":
            value = _json(raw, logical)
            if not isinstance(value, dict):
                raise ReceiptError(f"{logical}: JSON table must be an object")
            return tuple(
                (key, None, json.dumps(item, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":"), allow_nan=False).encode("utf-8"))
                for key, item in value.items()
            )
    except ReceiptError:
        raise
    except Exception as error:
        raise ReceiptError(f"cannot inspect table {logical}: {error}") from error
    raise ReceiptError(f"unsupported table codec {codec!r}")


def _unclaimed_sha(raw: bytes, members: tuple[InventoryMember, ...]) -> str:
    table_members = [member for member in members if member.kind == "table"]
    if not table_members:
        raise ReceiptError("unclaimed digest requested for a non-table path")
    claims = [cast(character_pack.TableClaim, member.claim) for member in table_members]
    codec = claims[0].codec_id
    if any(claim.codec_id != codec for claim in claims):
        raise ReceiptError("table path has conflicting codecs")
    owned: set[tuple[str, str | None]] = set()
    for claim in claims:
        if codec in {"action_nested", "switched_nested"}:
            for outer, keys in claim.inner_keys:
                owned.update((outer, inner) for inner in keys)
        else:
            owned.update((outer, None) for outer in claim.outer_keys)
    digest = hashlib.sha256(b"wf-local-unclaimed-v1\0")
    digest.update(_frame(codec.encode("utf-8")))
    for outer, inner, row in _all_rows(raw, codec, members[0].logical_path):
        if (outer, inner) in owned:
            continue
        digest.update(_frame(outer.encode("utf-8")))
        digest.update(b"\0" if inner is None else b"\1" + _frame(inner.encode("utf-8")))
        digest.update(_frame(row))
    return digest.hexdigest()


def _validate_context(context: ReleaseContext, policy: ReleasePolicy) -> tuple[MemberKey, ...]:
    if context.terminal.contract_id != policy.terminal_contract_id:
        raise ReceiptError("terminal contract id mismatch")
    keys = tuple(sorted({member.key for member in context.terminal.members}))
    if len(context.terminal.members) != policy.terminal_member_count or len(keys) != policy.unique_path_count:
        raise ReceiptError("terminal contract count mismatch")
    if tuple(context.baselines) != policy.baseline_versions:
        raise ReceiptError("baseline version order mismatch")
    if len(context.migration.server_members) != policy.server_member_count:
        raise ReceiptError("server migration count mismatch")
    if len(context.migration.client_tables) != policy.client_migration_count:
        raise ReceiptError("client migration count mismatch")
    if (
        SHA_RE.fullmatch(policy.manifest_preimage_sha256) is None
        or not isinstance(policy.manifest_cdn_version, str)
        or not policy.manifest_cdn_version
        or type(policy.manifest_preimage_patch_count) is not int
        or policy.manifest_preimage_patch_count < 0
    ):
        raise ReceiptError("manifest policy is invalid")
    bindings = {binding.role: binding for binding in context.contract_bindings}
    if set(bindings) != set(policy.contract_ids) or len(bindings) != len(context.contract_bindings):
        raise ReceiptError("five-contract binding set mismatch")
    for role, expected_id in policy.contract_ids.items():
        binding = bindings[role]
        if binding.contract_id != expected_id:
            raise ReceiptError(f"contract id mismatch for {role}")
        _safe_relative(binding.relative_path, f"contract {role}")
    if set(context.baseline_descriptors) != set(policy.baseline_versions):
        raise ReceiptError("baseline descriptor version mismatch")
    for version in policy.baseline_versions:
        if set(context.baseline_descriptors[version]) != set(keys):
            raise ReceiptError(f"baseline descriptor path coverage mismatch for {version}")
    return keys


def _attest_sources(
    context: ReleaseContext,
    keys: tuple[MemberKey, ...],
    terminal_sources: Mapping[MemberKey, bytes],
    edges: tuple[EdgeEvidence, ...],
) -> None:
    if set(terminal_sources) != set(keys) or any(not isinstance(raw, bytes) for raw in terminal_sources.values()):
        raise ReceiptError("terminal source path coverage mismatch")
    inventory.attest_source(context.terminal, lambda member: terminal_sources[member.key])
    members_by_path = _members_by_path(context.terminal)
    for edge in edges:
        if set(edge.baseline) != set(keys) or set(edge.output) != set(keys):
            raise ReceiptError(f"edge {edge.from_version} path coverage mismatch")
        descriptors = context.baseline_descriptors[edge.from_version]
        for key in keys:
            raw, descriptor = edge.baseline[key], descriptors[key]
            if descriptor.present != (raw is not None):
                raise ReceiptError(f"baseline presence drift for {edge.from_version}:{key}")
            if raw is not None and (len(raw) != descriptor.size or _sha(raw) != descriptor.sha256):
                raise ReceiptError(f"baseline source drift for {edge.from_version}:{key}")
            is_table = members_by_path[key][0].kind == "table"
            if raw is not None and is_table:
                actual_unclaimed = _unclaimed_sha(raw, members_by_path[key])
                if descriptor.unclaimed_sha256 != actual_unclaimed:
                    raise ReceiptError(
                        f"baseline unclaimed sha256 drift for {edge.from_version}:{key}"
                    )
            elif descriptor.unclaimed_sha256 is not None:
                raise ReceiptError(
                    f"unexpected baseline unclaimed anchor for {edge.from_version}:{key}"
                )
        inventory.attest_source(
            context.baselines[edge.from_version],
            lambda member, source=edge.baseline: cast(bytes, source[member.key]),
        )


def _expected_output(
    source: bytes, baseline: bytes | None, members: tuple[InventoryMember, ...]
) -> bytes:
    """Re-derive the payload the publisher must have produced for one path.

    This has to use the same joint claim-order merge the publisher uses.
    Folding the owners in one at a time instead rebases each owner onto the
    previous owner's intermediate table rather than onto the baseline, so as
    soon as a table carries more than one owner — or its claimed rows are not
    already contiguous — the two derivations disagree on row order and the
    receipt rejects a correctly published edge.
    """
    kinds = {member.kind for member in members}
    if len(kinds) != 1:
        raise ReceiptError("terminal members disagree on kind")
    if next(iter(kinds)) == "file":
        return source
    if baseline is None:
        raise ReceiptError("table baseline is absent and cannot preserve unclaimed rows")
    try:
        return table_merge.merge_table_members(members, source, baseline)
    except table_merge.ScopedTableMergeError as error:
        raise ReceiptError(f"cannot re-derive claimed table merge: {error}") from error


def _terminal_source_anchor(
    members: tuple[InventoryMember, ...]
) -> tuple[int, str]:
    anchors = {
        (
            cast(int, member.size), cast(str, member.sha256)
        ) if member.kind == "file" else (
            cast(int, member.source_size), cast(str, member.source_sha256)
        )
        for member in members
    }
    if len(anchors) != 1:
        raise ReceiptError("terminal members disagree on whole-source anchor")
    return next(iter(anchors))


def _read_archives(edge: EdgeEvidence) -> tuple[list[dict[str, object]], dict[tuple[str, str], tuple[bytes, str]]]:
    records: list[dict[str, object]] = []
    payloads: dict[tuple[str, str], tuple[bytes, str]] = {}
    last_root = -1
    for sequence, part in enumerate(edge.archives, start=1):
        if part.root not in ROOT_PREFIX or ROOTS.index(part.root) < last_root:
            raise ReceiptError("archive roots are not in canonical order")
        last_root = ROOTS.index(part.root)
        expected_name = f"pinball-{edge.from_version}-{edge.to_version}-{sequence}-{edge.tag}.zip"
        if part.name != expected_name:
            raise ReceiptError(f"archive sequence/name mismatch: {part.name}")
        _safe_relative(part.name, "archive name")
        if len(part.blob) > ZIP_CAP:
            raise ReceiptError(f"archive size exceeds CI cap: {part.name}")
        members: list[dict[str, object]] = []
        try:
            with zipfile.ZipFile(io.BytesIO(part.blob)) as zipped:
                infos = zipped.infolist()
                names = [info.filename for info in infos]
                if not names or names != sorted(names) or len(names) != len(set(names)):
                    raise ReceiptError(f"archive member order/duplicates: {part.name}")
                for info in infos:
                    if (
                        info.date_time != ZIP_TIMESTAMP or info.compress_type != zipfile.ZIP_DEFLATED
                        or info.create_system != 3 or info.external_attr != ZIP_MODE
                        or info.flag_bits != 0 or info.extra != b"" or info.comment != b""
                        or info.is_dir() or not info.filename.startswith(ROOT_PREFIX[part.root])
                    ):
                        raise ReceiptError(f"archive metadata/root drift: {part.name}!{info.filename}")
                    raw = zipped.read(info)
                    key = part.root, info.filename
                    if key in payloads:
                        raise ReceiptError(f"archive member repeated across parts: {info.filename}")
                    payloads[key] = raw, part.name
                    members.append({"name": info.filename, "size": len(raw), "sha256": _sha(raw)})
                if zipped.comment or zipped.testzip() is not None:
                    raise ReceiptError(f"archive CRC/comment drift: {part.name}")
        except ReceiptError:
            raise
        except (OSError, zipfile.BadZipFile, RuntimeError) as error:
            raise ReceiptError(f"cannot read archive {part.name}: {error}") from error
        records.append({
            "root": part.root, "name": part.name, "path": f"active/{part.name}",
            "size": len(part.blob), "sha256": _sha(part.blob), "members": members,
        })
    return records, payloads


def _baseline_terminal_equivalent(
    terminal_members: tuple[InventoryMember, ...], baseline: InventoryContract
) -> bool:
    by_key: dict[MemberKey, list[InventoryMember]] = {}
    for member in baseline.members:
        by_key.setdefault(member.key, []).append(member)
    for member in terminal_members:
        candidates = tuple(
            other for other in by_key.get(member.key, ())
            if other.kind == member.kind
        )
        if member.kind == "file":
            if not any(
                (other.size, other.sha256) == (member.size, member.sha256)
                for other in candidates
            ):
                return False
        elif not any(
            other.projection_sha256 == member.projection_sha256
            and other.claim == member.claim
            for other in candidates
        ):
            return False
    return True


def _manifest_evidence(
    preimage_raw: bytes,
    output_raw: bytes,
    edges: tuple[EdgeEvidence, ...],
    policy: ReleasePolicy,
) -> dict[str, object]:
    before = _json(preimage_raw, "manifest preimage")
    after = _json(output_raw, "manifest output")
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ReceiptError("manifest must be an object")
    if not isinstance(before.get("patches"), list) or not isinstance(after.get("patches"), list):
        raise ReceiptError("manifest patches must be arrays")
    render_before = (json.dumps(before, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    render_after = (json.dumps(after, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    if preimage_raw != render_before or output_raw != render_after:
        raise ReceiptError("manifest bytes do not match the canonical renderer")
    before_other, after_other = dict(before), dict(after)
    old_patches = cast(list[object], before_other.pop("patches"))
    new_patches = cast(list[object], after_other.pop("patches"))
    if before_other != after_other or new_patches[:len(old_patches)] != old_patches:
        raise ReceiptError("manifest changed outside append-only patches")
    appended = new_patches[len(old_patches):]
    if (
        _sha(preimage_raw) != policy.manifest_preimage_sha256
        or before.get("cdn_version") != policy.manifest_cdn_version
        or len(old_patches) != policy.manifest_preimage_patch_count
    ):
        raise ReceiptError("manifest policy baseline mismatch")
    if len(appended) != len(edges):
        raise ReceiptError("manifest must append exactly both release edges")
    for patch, edge in zip(appended, edges):
        if not isinstance(patch, dict):
            raise ReceiptError("manifest appended patch must be an object")
        integrity = [
            {
                "name": part.name,
                "size": len(part.blob),
                "sha256": _sha(part.blob),
            }
            for part in edge.archives
        ]
        if (
            patch.get("id") != edge.patch_id
            or patch.get("version") != edge.to_version
            or patch.get("depends_on") != edge.from_version
            or patch.get("chain") != [part.name for part in edge.archives]
            or patch.get("archive_integrity") != integrity
            or patch.get("enabled") is not True
        ):
            raise ReceiptError(
                f"manifest edge/archive_integrity mismatch for {edge.from_version}"
            )
    return {
        "preimage_sha256": _sha(preimage_raw),
        "output_sha256": _sha(output_raw),
        "cdn_version": before.get("cdn_version"),
        "preimage_patch_count": len(old_patches),
        "appended_patches": appended,
    }


def _server_evidence(
    context: ReleaseContext, server_files: Mapping[str, bytes]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[str, list[server_contract.ServerMember]] = {}
    for member in context.migration.server_members:
        grouped.setdefault(member.logical_path, []).append(member)
    if set(server_files) != set(grouped):
        raise ReceiptError("server file path coverage mismatch")
    server_records: list[dict[str, object]] = []
    for logical in sorted(grouped):
        raw = server_files[logical]
        if not isinstance(raw, bytes):
            raise ReceiptError(f"server file is not bytes: {logical}")
        selectors = []
        for member in grouped[logical]:
            if server_contract.classify_server_member(member, raw) != "terminal":
                raise ReceiptError(f"server member is not terminal: {logical}")
            selectors.append({"owner": member.owner, "terminal_sha256": member.terminal_sha256})
        server_records.append({
            "logical_path": logical, "size": len(raw), "sha256": _sha(raw),
            "selectors": selectors,
        })
    clients = [{
        "owner": member.owner, "root": member.root,
        "logical_path": member.logical_path,
        "source_size": member.terminal.source_size,
        "source_sha256": member.terminal.source_sha256,
        "projection_sha256": member.terminal.projection_sha256,
    } for member in context.migration.client_tables]
    return server_records, clients


def _build_receipt(
    context: ReleaseContext,
    policy: ReleasePolicy,
    *,
    terminal_sources: Mapping[MemberKey, bytes],
    edges: tuple[EdgeEvidence, ...],
    manifest_preimage: bytes,
    manifest_output: bytes,
    server_files: Mapping[str, bytes],
) -> bytes:
    keys = _validate_context(context, policy)
    if len(edges) != len(policy.baseline_versions):
        raise ReceiptError("exactly two baseline edges are required")
    if tuple(edge.from_version for edge in edges) != policy.baseline_versions:
        raise ReceiptError("edge baseline order mismatch")
    if any(edge.to_version != "1.4.312" for edge in edges):
        raise ReceiptError("edge target must be 1.4.312")
    for edge in edges:
        if (
            VERSION_RE.fullmatch(edge.from_version) is None
            or TAG_RE.fullmatch(edge.tag) is None
            or PATCH_RE.fullmatch(edge.patch_id) is None
        ):
            raise ReceiptError("edge version, tag, or patch id is invalid")
    _attest_sources(context, keys, terminal_sources, edges)
    members_by_path = _members_by_path(context.terminal)
    edge_records: list[dict[str, object]] = []
    for edge in edges:
        archive_records, archive_payloads = _read_archives(edge)
        used: set[tuple[str, str]] = set()
        paths: list[dict[str, object]] = []
        for key in keys:
            root, logical = key
            baseline, output = edge.baseline[key], edge.output[key]
            if not isinstance(output, bytes):
                raise ReceiptError(f"output is not bytes for {root}:{logical}")
            expected = _expected_output(terminal_sources[key], baseline, members_by_path[key])
            if output != expected:
                raise ReceiptError(f"output differs from row-scoped terminal merge for {root}:{logical}")
            inventory.attest_contract(
                InventoryContract(context.terminal.contract_id, members_by_path[key]),
                lambda _member, raw=output: raw,
            )
            member_name = archive_member_name(root, logical)
            payload = archive_payloads.get((root, member_name))
            record: dict[str, object] = {
                "root": root, "logical_path": logical,
                "baseline": None if baseline is None else {"size": len(baseline), "sha256": _sha(baseline)},
                "output_size": len(output), "output_sha256": _sha(output),
                "claims": [_claim_record(member) for member in members_by_path[key]],
            }
            if baseline == output:
                if payload is not None or baseline is None:
                    raise ReceiptError(f"no-op path must be omitted from archives: {root}:{logical}")
                if not _baseline_terminal_equivalent(members_by_path[key], context.baselines[edge.from_version]):
                    raise ReceiptError(f"omitted path lacks terminal baseline claim: {root}:{logical}")
                record.update({"disposition": "omitted_equal", "archive": None, "archive_member": None})
            else:
                if payload is None or payload[0] != output:
                    raise ReceiptError(f"changed output missing from archive: {root}:{logical}")
                used.add((root, member_name))
                record.update({
                    "disposition": "included", "archive": f"active/{payload[1]}",
                    "archive_member": member_name,
                })
            if members_by_path[key][0].kind == "table":
                if baseline is None:
                    before_unclaimed = _unclaimed_sha(output, members_by_path[key])
                else:
                    before_unclaimed = _unclaimed_sha(baseline, members_by_path[key])
                after_unclaimed = _unclaimed_sha(output, members_by_path[key])
                if before_unclaimed != after_unclaimed:
                    raise ReceiptError(f"unclaimed table rows changed for {root}:{logical}")
                record.update({
                    "unclaimed_before_sha256": before_unclaimed,
                    "unclaimed_after_sha256": after_unclaimed,
                })
            paths.append(record)
        if used != set(archive_payloads):
            raise ReceiptError("archive contains payload outside terminal path coverage")
        edge_records.append({
            "from_version": edge.from_version, "to_version": edge.to_version,
            "patch_id": edge.patch_id, "tag": edge.tag,
            "archives": archive_records, "paths": paths,
        })
    server_records, client_records = _server_evidence(context, server_files)
    for client in context.migration.client_tables:
        raw = terminal_sources[(client.root, client.logical_path)]
        if server_contract.classify_client_table(client, raw) != "terminal":
            raise ReceiptError(f"client migration is not terminal: {client.logical_path}")
    contracts = [{
        "role": binding.role, "path": binding.relative_path,
        "contract_id": binding.contract_id, "size": len(binding.raw),
        "sha256": _sha(binding.raw),
    } for binding in context.contract_bindings]
    body: dict[str, object] = {
        "schema": SCHEMA, "release_id": policy.release_id,
        "target_version": "1.4.312", "terminal_contract_id": policy.terminal_contract_id,
        "terminal_member_count": policy.terminal_member_count,
        "unique_path_count": policy.unique_path_count,
        "contracts": contracts, "edges": edge_records,
        "manifest": _manifest_evidence(
            manifest_preimage, manifest_output, edges, policy
        ),
        "server": {"remaining_changes": 0, "files": server_records},
        "client_migrations": client_records,
    }
    digest = _sha(canonical_receipt(body))
    body["receipt_sha256"] = digest
    return canonical_receipt(body)


def build_receipt(
    context: ReleaseContext,
    policy: ReleasePolicy,
    *,
    terminal_sources: Mapping[MemberKey, bytes],
    edges: tuple[EdgeEvidence, ...],
    manifest_preimage: bytes,
    manifest_output: bytes,
    server_files: Mapping[str, bytes],
) -> bytes:
    try:
        return _build_receipt(
            context, policy, terminal_sources=terminal_sources, edges=edges,
            manifest_preimage=manifest_preimage, manifest_output=manifest_output,
            server_files=server_files,
        )
    except ReceiptError:
        raise
    except (InventoryError, server_contract.MigrationError, KeyError, TypeError, ValueError) as error:
        raise ReceiptError(f"cannot build release receipt: {error}") from error


def verify_receipt(
    context: ReleaseContext,
    policy: ReleasePolicy,
    receipt_raw: bytes,
    *,
    archive_blobs: Mapping[str, bytes],
    manifest_raw: bytes,
    server_files: Mapping[str, bytes],
) -> VerificationReport:
    """Compatibility entry point; implementation lives in the verifier module."""
    from wf_local_release_verify import verify_receipt as offline_verify

    return offline_verify(
        context, policy, receipt_raw, archive_blobs=archive_blobs,
        manifest_raw=manifest_raw, server_files=server_files,
    )

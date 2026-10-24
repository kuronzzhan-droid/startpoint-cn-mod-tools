#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build row-scoped client patch edges without mutating live release state."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Mapping, cast

import wf_character_pack as character_pack
import wf_mod_tool as core
import wf_release_inventory as inventory
from wf_release_inventory_contract import (
    CLIENT_ROOTS,
    InventoryContract,
    InventoryMember,
    MemberKey,
)
import wf_scoped_release_archive as archive
import wf_scoped_table_merge as table_merge
import wf_scoped_release_transaction as transaction


CI_ZIP_CAP = archive.CI_ZIP_CAP
ZIP_TIMESTAMP = archive.ZIP_TIMESTAMP
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PATCH_ARCHIVE_RE = re.compile(
    r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-([1-9]\d*)-([^/\\]+)\.zip$"
)
MAX_ARCHIVE_SEQUENCE = (1 << 53) - 1


class ScopedReleaseError(RuntimeError):
    """The scoped release cannot be built or committed safely."""


def _version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or VERSION_RE.fullmatch(value) is None:
        raise ScopedReleaseError(f"invalid release version: {value!r}")
    return cast(tuple[int, int, int], tuple(int(part) for part in value.split(".")))


@dataclass(frozen=True, slots=True)
class EdgeSpec:
    from_version: str
    to_version: str
    tag: str
    patch_id: str
    name: str
    description: str
    created_at: str

    def __post_init__(self) -> None:
        if _version(self.to_version) <= _version(self.from_version):
            raise ScopedReleaseError("edge version must increase")
        if not isinstance(self.tag, str) or re.fullmatch(r"[a-z0-9]+", self.tag) is None:
            raise ScopedReleaseError("tag must contain only lowercase ASCII letters and digits")
        if not isinstance(self.patch_id, str) or TOKEN_RE.fullmatch(self.patch_id) is None:
            raise ScopedReleaseError("patch_id is not a safe token")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ScopedReleaseError("patch name must be non-empty")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ScopedReleaseError("patch description must be non-empty")
        if not isinstance(self.created_at, str) or DATE_RE.fullmatch(self.created_at) is None:
            raise ScopedReleaseError("created_at must use YYYY-MM-DD")
        try:
            date.fromisoformat(self.created_at)
        except ValueError as error:
            raise ScopedReleaseError("created_at is not a real calendar date") from error


@dataclass(frozen=True, slots=True)
class ScopedEntry:
    root: str
    logical_path: str
    member_name: str
    payload: bytes


ArchivePart = archive.ArchivePart


@dataclass(frozen=True, slots=True)
class EdgePlan:
    spec: EdgeSpec
    entries: tuple[ScopedEntry, ...]
    parts: tuple[ArchivePart, ...]


def _client_contract(contract: InventoryContract) -> InventoryContract:
    members = tuple(member for member in contract.members if member.root in CLIENT_ROOTS)
    if not members:
        raise ScopedReleaseError("terminal contract has no client members")
    return InventoryContract(contract.contract_id, members)


def _baseline_keys(
    contract: InventoryContract, baseline: Mapping[MemberKey, bytes | None]
) -> tuple[MemberKey, ...]:
    expected = set(member.key for member in contract.members)
    actual = set(baseline)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ScopedReleaseError(
            f"baseline key set must exactly match client inventory; "
            f"missing={missing[:3]} extra={extra[:3]}"
        )
    for key, raw in baseline.items():
        if (
            not isinstance(key, tuple)
            or len(key) != 2
            or key[0] not in CLIENT_ROOTS
            or not isinstance(key[1], str)
        ):
            raise ScopedReleaseError(f"invalid baseline key: {key!r}")
        if raw is not None and not isinstance(raw, bytes):
            raise ScopedReleaseError(f"baseline payload must be bytes or absent: {key}")
    return tuple(sorted(expected, key=lambda key: (CLIENT_ROOTS.index(key[0]), key[1])))


def _archive_name(root: str, logical_path: str) -> str:
    digest = core.sha1_path(logical_path)
    return f"{character_pack.ARCHIVE_PREFIXES[root]}{digest[:2]}/{digest[2:]}"


def build_edge_plan(
    contract: InventoryContract,
    baseline: Mapping[MemberKey, bytes | None],
    terminal_reader: Callable[[InventoryMember], bytes],
    spec: EdgeSpec,
    *,
    max_zip_bytes: int = CI_ZIP_CAP,
) -> EdgePlan:
    """Merge only declared terminal claims onto one independently frozen baseline."""
    client = _client_contract(contract)
    keys = _baseline_keys(client, baseline)
    ordered_members = sorted(
        client.members,
        key=lambda member: (
            CLIENT_ROOTS.index(member.root), member.logical_path, member.owner
        ),
    )
    by_key: dict[MemberKey, list[InventoryMember]] = {key: [] for key in keys}
    terminal: dict[MemberKey, bytes] = {}
    try:
        for member in ordered_members:
            by_key[member.key].append(member)
            if member.key not in terminal:
                raw = terminal_reader(member)
                if not isinstance(raw, bytes):
                    raise ScopedReleaseError(
                        f"terminal reader returned non-bytes for {member.key}"
                    )
                terminal[member.key] = raw
        inventory.attest_source_contract(
            client, lambda member: terminal[member.key]
        )

        output: dict[MemberKey, bytes] = {}
        entries: list[ScopedEntry] = []
        for key in keys:
            members = by_key[key]
            baseline_raw = baseline[key]
            is_table = members[0].kind == "table"
            if is_table and baseline_raw is None:
                raise ScopedReleaseError(
                    f"table baseline is absent and cannot preserve unclaimed rows: {key}"
                )
            if is_table:
                merged = table_merge.merge_table_members(
                    members, terminal[key], cast(bytes, baseline_raw)
                )
            else:
                merged = terminal[key]
            output[key] = merged
            if baseline_raw != merged:
                entries.append(ScopedEntry(
                    root=key[0],
                    logical_path=key[1],
                    member_name=_archive_name(*key),
                    payload=merged,
                ))

        inventory.attest_terminal_contract(
            client, lambda member: output[member.key]
        )
        parts = archive.build_parts(
            entries,
            roots=CLIENT_ROOTS,
            from_version=spec.from_version,
            to_version=spec.to_version,
            tag=spec.tag,
            max_zip_bytes=max_zip_bytes,
        )
    except ScopedReleaseError:
        raise
    except (
        OSError,
        KeyError,
        inventory.InventoryError,
        archive.ArchiveError,
        table_merge.ScopedTableMergeError,
    ) as error:
        raise ScopedReleaseError(str(error)) from error
    return EdgePlan(spec, tuple(entries), parts)


def _duplicate_free(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _manifest(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_free,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-JSON constant {value}")
            ),
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise ScopedReleaseError(f"invalid patch manifest: {error}") from error
    if not isinstance(value, dict):
        raise ScopedReleaseError("patch manifest must be a JSON object")
    patches = value.get("patches")
    if not isinstance(patches, list):
        raise ScopedReleaseError("patch manifest patches must be an array")
    cdn_version = value.get("cdn_version")
    if not isinstance(cdn_version, str) or VERSION_RE.fullmatch(cdn_version) is None:
        raise ScopedReleaseError("patch manifest cdn_version is invalid")
    return value


def _patch_entry(plan: EdgePlan) -> dict[str, object]:
    if not plan.parts:
        raise ScopedReleaseError(f"edge {plan.spec.patch_id} has no changed payloads")
    expected_sequences = list(range(1, len(plan.parts) + 1))
    if [part.sequence for part in plan.parts] != expected_sequences:
        raise ScopedReleaseError(f"edge {plan.spec.patch_id} has invalid ZIP sequence")
    expected_names = [
        f"pinball-{plan.spec.from_version}-{plan.spec.to_version}-"
        f"{part.sequence}-{plan.spec.tag}.zip"
        for part in plan.parts
    ]
    if [part.name for part in plan.parts] != expected_names:
        raise ScopedReleaseError(f"edge {plan.spec.patch_id} has invalid ZIP names")
    if any(part.root not in CLIENT_ROOTS for part in plan.parts):
        raise ScopedReleaseError(f"edge {plan.spec.patch_id} has invalid ZIP root")
    roots = [CLIENT_ROOTS.index(part.root) for part in plan.parts]
    if roots != sorted(roots):
        raise ScopedReleaseError(f"edge {plan.spec.patch_id} has invalid root order")
    try:
        archive.attest_plan_parts(plan.entries, plan.parts)
    except (ValueError, archive.ArchiveError) as error:
        raise ScopedReleaseError(str(error)) from error
    return {
        "id": plan.spec.patch_id,
        "type": "patch",
        "name": plan.spec.name,
        "description": plan.spec.description,
        "version": plan.spec.to_version,
        "depends_on": plan.spec.from_version,
        "enabled": True,
        "chain": expected_names,
        "archive_integrity": [
            {
                "name": part.name,
                "size": len(part.blob),
                "sha256": hashlib.sha256(part.blob).hexdigest(),
            }
            for part in plan.parts
        ],
        "created_at": plan.spec.created_at,
    }


def _enabled_manifest_chain_edges(
    item: dict[str, object],
    patch_id: str,
    depends_on: str,
    version: str,
) -> tuple[tuple[str, str], ...]:
    chain = item.get("chain")
    if not isinstance(chain, list) or not chain:
        raise ScopedReleaseError(f"manifest patch {patch_id} has invalid chain")
    names: set[str] = set()
    edge_order: list[tuple[str, str]] = []
    sequences: dict[tuple[str, str], list[int]] = {}
    for raw_name in chain:
        if not isinstance(raw_name, str) or raw_name in names:
            raise ScopedReleaseError(
                f"manifest patch {patch_id} has invalid archive names"
            )
        match = PATCH_ARCHIVE_RE.fullmatch(raw_name)
        if match is None:
            raise ScopedReleaseError(
                f"manifest patch {patch_id} has invalid archive name: {raw_name!r}"
            )
        archive_from, archive_to = match.group(1), match.group(2)
        sequence = int(match.group(3))
        if (
            sequence > MAX_ARCHIVE_SEQUENCE
            or _version(archive_to) <= _version(archive_from)
        ):
            raise ScopedReleaseError(
                f"manifest patch {patch_id} has invalid archive edge or sequence"
            )
        names.add(raw_name)
        edge = archive_from, archive_to
        if edge not in sequences:
            edge_order.append(edge)
            sequences[edge] = []
        sequences[edge].append(sequence)
    for edge, values in sequences.items():
        if sorted(values) != list(range(1, len(values) + 1)):
            raise ScopedReleaseError(
                f"manifest patch {patch_id} archive sequence is not contiguous: "
                f"{edge[0]}->{edge[1]}"
            )
    if (
        edge_order[0][0] != depends_on
        or edge_order[-1][1] != version
        or any(
            edge_order[index - 1][1] != edge_order[index][0]
            for index in range(1, len(edge_order))
        )
    ):
        raise ScopedReleaseError(
            f"manifest patch {patch_id} chain is disconnected from its edge"
        )
    return tuple(edge_order)


def render_manifest(original: bytes, plans: Iterable[EdgePlan]) -> bytes:
    value = _manifest(original)
    selected = tuple(plans)
    if not selected:
        raise ScopedReleaseError("at least one scoped edge is required")
    existing = cast(list[object], value["patches"])
    existing_ids: set[str] = set()
    existing_edge_owners: dict[tuple[str, str], str] = {}
    for index, item in enumerate(existing):
        if not isinstance(item, dict):
            raise ScopedReleaseError(f"manifest patch {index} must be an object")
        patch_id = item.get("id")
        depends_on, version = item.get("depends_on"), item.get("version")
        if not isinstance(patch_id, str) or not patch_id:
            raise ScopedReleaseError(f"manifest patch {index} has invalid id")
        if patch_id in existing_ids:
            raise ScopedReleaseError(f"duplicate manifest patch id: {patch_id}")
        if not isinstance(depends_on, str) or not isinstance(version, str):
            raise ScopedReleaseError(f"manifest patch {patch_id} has invalid edge")
        if (
            VERSION_RE.fullmatch(depends_on) is None
            or VERSION_RE.fullmatch(version) is None
            or _version(version) <= _version(depends_on)
        ):
            raise ScopedReleaseError(f"manifest patch {patch_id} has invalid edge")
        outer_edge = depends_on, version
        item_edges = {outer_edge}
        if item.get("enabled") is True:
            if item.get("type") != "patch":
                raise ScopedReleaseError(f"manifest patch {patch_id} has invalid type")
            item_edges.update(
                _enabled_manifest_chain_edges(item, patch_id, depends_on, version)
            )
        for edge in item_edges:
            owner = existing_edge_owners.get(edge)
            if owner is not None:
                raise ScopedReleaseError(
                    f"duplicate manifest edge: {edge[0]}->{edge[1]} "
                    f"({owner}, {patch_id})"
                )
            existing_edge_owners[edge] = patch_id
        existing_ids.add(patch_id)
    seen_ids: set[str] = set()
    seen_edges: set[tuple[str, str]] = set()
    additions: list[dict[str, object]] = []
    for plan in selected:
        edge = (plan.spec.from_version, plan.spec.to_version)
        if plan.spec.patch_id in existing_ids or plan.spec.patch_id in seen_ids:
            raise ScopedReleaseError(f"duplicate manifest patch id: {plan.spec.patch_id}")
        if edge in existing_edge_owners or edge in seen_edges:
            raise ScopedReleaseError(f"duplicate scoped edge: {edge[0]}->{edge[1]}")
        seen_ids.add(plan.spec.patch_id)
        seen_edges.add(edge)
        additions.append(_patch_entry(plan))
    value["patches"] = [*existing, *additions]
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def stage_archives(
    plans: Iterable[EdgePlan], staging_dir: Path
) -> tuple[Path, ...]:
    try:
        return transaction.stage_archives(tuple(plans), Path(staging_dir))
    except (OSError, transaction.TransactionError) as error:
        raise ScopedReleaseError(str(error)) from error


def _plan_payload_entries(plan: EdgePlan) -> list:
    import wfx_gate

    return [
        wfx_gate.PayloadEntry(
            label=f"{entry.root}:{entry.logical_path}",
            read=lambda payload=entry.payload: payload,
            logical=entry.logical_path,
            root=entry.root,
        )
        for entry in plan.entries
    ]


def _client_capability_gate(
    plans: tuple[EdgePlan, ...],
    client_profile: str,
    unique_context: Mapping[str, str] | None = None,
) -> None:
    """Reject edges whose payloads need capabilities the receiving client lacks.

    Each edge is checked on its own: two edges may carry different versions of
    the same table.  Data without wfx rows or patch constructs passes as a no-op.

    uid references (461/413/134 rows, DSL ACUnique) are resolved against the
    caller's unique_condition context (source store) overlaid with every
    selected edge's unique_condition payload, so an edge that only references a
    wfx row delivered by another edge (or already in the source) is still
    derived.  The union errs toward blocking (a row the receiver lacks can
    still count); clean data is unaffected because an empty wfx index is a no-op.
    """
    import wfx_gate

    try:
        profile = wfx_gate.resolve_profile(client_profile)
        entries_by_plan = [_plan_payload_entries(plan) for plan in plans]
        context = wfx_gate.merge_unique_context(
            unique_context,
            *(wfx_gate.unique_context_from_entries(entries) for entries in entries_by_plan),
        )
        for plan, entries in zip(plans, entries_by_plan):
            report = wfx_gate.check_entries(entries, profile, unique_context=context)
            if not report.ok:
                raise ScopedReleaseError(
                    f"client capability gate rejected edge {plan.spec.patch_id} "
                    f"for profile {profile.name}: " + "; ".join(report.problems)
                )
    except wfx_gate.GateError as error:
        raise ScopedReleaseError(str(error)) from error


def publish_archives_and_manifest(
    plans: Iterable[EdgePlan],
    active_dir: Path,
    manifest_path: Path,
    *,
    expected_manifest_sha256: str,
    checkpoint: Callable[[str], None] | None = None,
    client_profile: str | None = None,
    client_unique_context: Mapping[str, str] | None = None,
) -> tuple[Path, ...]:
    """client_profile: receiving client profile in mod-tools/client_profiles.json.

    Scoped edges leave this machine (overlay/public chain), so the profile is
    mandatory and never defaults to the local device (wfx_gate, design 4.9).
    client_unique_context: unique_condition rows {uid: row text} of the source
    (normally the terminal store) used to resolve uid references.
    """
    selected = tuple(plans)
    if client_profile is None:
        raise ScopedReleaseError(
            "scoped release requires an explicit client profile "
            "(client_profile=<name in mod-tools/client_profiles.json>)"
        )
    if (
        not isinstance(expected_manifest_sha256, str)
        or SHA256_RE.fullmatch(expected_manifest_sha256) is None
    ):
        raise ScopedReleaseError("expected manifest sha256 is invalid")
    manifest_path = Path(manifest_path)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ScopedReleaseError(f"manifest path is unsafe: {manifest_path}")
    preimage = manifest_path.read_bytes()
    if hashlib.sha256(preimage).hexdigest() != expected_manifest_sha256:
        raise ScopedReleaseError("manifest preimage sha256 mismatch")
    output = render_manifest(preimage, selected)
    _client_capability_gate(selected, client_profile, client_unique_context)
    try:
        return transaction.publish_transaction(
            selected,
            Path(active_dir),
            manifest_path,
            manifest_preimage=preimage,
            manifest_output=output,
            checkpoint=checkpoint,
        )
    except (OSError, transaction.TransactionError) as error:
        raise ScopedReleaseError(str(error)) from error

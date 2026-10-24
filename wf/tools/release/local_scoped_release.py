#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapt the frozen local-live bundle into two immutable scoped release edges."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping

import wf_local_release_contract as local_contract
import wf_mod_tool as core
import wf_release_inventory as inventory
import wf_scoped_release as scoped
from wf_release_inventory_contract import CLIENT_ROOTS, MemberKey


TARGET_VERSION = "1.4.312"
PUBLISH_CONFIRMATION = "PUBLISH_LOCAL_1_4_312"
PRIMARY_SPEC = scoped.EdgeSpec(
    from_version="1.4.277",
    to_version=TARGET_VERSION,
    tag="localsync0806",
    patch_id="local-live-main",
    name="1.4.277→1.4.312 本地实装终态回灌",
    description=(
        "以冻结的本地实装合同外科式回灌 700099 深渊连战塔、15 把深渊武器、"
        "光暗龙、拉芙与基诺维的主数据、技能、立绘、像素、特效和语音；"
        "未认领表行保持 1.4.277 基线。"
    ),
    created_at="2026-08-06",
)
COMPATIBILITY_SPEC = scoped.EdgeSpec(
    from_version="1.4.311",
    to_version=TARGET_VERSION,
    tag="localsync0806",
    patch_id="local-live-compatibility",
    name="1.4.311→1.4.312 本地实装兼容入口",
    description=(
        "供已更新到本地 1.4.311 链尾的客户端直接取得同一份 1.4.312 终态；"
        "仅携带相对 1.4.311 仍有差异的认领路径。"
    ),
    created_at="2026-08-06",
)


class AdapterError(RuntimeError):
    """The fixed local contract could not be adapted or safely published."""


@dataclass(frozen=True, slots=True)
class PayloadSnapshot:
    version: str
    values: tuple[tuple[MemberKey, bytes | None], ...]
    mapping: Mapping[MemberKey, bytes | None]
    digest: str


@dataclass(frozen=True, slots=True)
class LocalEdgeEvidence:
    plan: scoped.EdgePlan
    baseline: PayloadSnapshot
    output: PayloadSnapshot


@dataclass(frozen=True, slots=True)
class LocalScopedPlans:
    bundle: local_contract.ContractBundle
    terminal: PayloadSnapshot
    baselines: tuple[PayloadSnapshot, ...]
    primary: scoped.EdgePlan
    compatibility: scoped.EdgePlan
    edges: tuple[LocalEdgeEvidence, ...]
    deterministic_digest: str
    # Terminal store's unique_condition table (uid context for the client
    # capability gate only; not part of the deterministic digest).
    source_unique_condition: bytes | None = None

    @property
    def terminal_digest(self) -> str:
        return self.terminal.digest

    @property
    def public_edges(self) -> tuple[scoped.EdgePlan, ...]:
        return self.primary, self.compatibility

    @property
    def local_311_edges(self) -> tuple[scoped.EdgePlan, ...]:
        return (self.compatibility,)

    def select(self, selection: str) -> tuple[scoped.EdgePlan, ...]:
        if selection == "public":
            return self.public_edges
        if selection == "local-311":
            return self.local_311_edges
        raise AdapterError("selection must be 'public' or 'local-311'")


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_reparse(path: Path) -> bool:
    path = Path(path)
    if path.is_symlink():
        return True
    junction = getattr(path, "is_junction", None)
    if junction is not None and junction():
        return True
    metadata = path.lstat()
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(metadata, "st_file_attributes", 0) & marker)


def _ancestry(path: Path) -> tuple[Path, ...]:
    current = _absolute(path)
    result = [current]
    while current.parent != current:
        current = current.parent
        result.append(current)
    return tuple(reversed(result))


def _assert_plain(path: Path, *, leaf: str) -> Path:
    chain = _ancestry(path)
    for index, component in enumerate(chain):
        try:
            metadata = component.lstat()
            reparse = _is_reparse(component)
        except OSError as error:
            raise AdapterError(f"missing or unreadable ancestor: {component}") from error
        if reparse:
            raise AdapterError(f"ancestor is a symlink/junction/reparse: {component}")
        final = index == len(chain) - 1
        if not final and not stat.S_ISDIR(metadata.st_mode):
            raise AdapterError(f"ancestor is not a directory: {component}")
        if final and leaf == "directory" and not stat.S_ISDIR(metadata.st_mode):
            raise AdapterError(f"expected directory: {component}")
        if final and leaf == "file" and not stat.S_ISREG(metadata.st_mode):
            raise AdapterError(f"expected regular file: {component}")
    return chain[-1]


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


def _read_stable(path: Path, label: str) -> bytes:
    target = _assert_plain(path, leaf="file")
    before = target.lstat()
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise AdapterError(f"{label} opened object is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1 << 20):
            chunks.append(chunk)
        after_open = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after = _assert_plain(target, leaf="file").lstat()
    if len({_identity(item) for item in (before, opened, after_open, after)}) != 1:
        raise AdapterError(f"{label} identity changed during read")
    return b"".join(chunks)


def _ordered_values(
    values: Mapping[MemberKey, bytes | None], version: str
) -> PayloadSnapshot:
    ordered = tuple(sorted(
        values.items(), key=lambda item: (CLIENT_ROOTS.index(item[0][0]), item[0][1])
    ))
    records = [
        [root, logical, None if raw is None else [len(raw), hashlib.sha256(raw).hexdigest()]]
        for (root, logical), raw in ordered
    ]
    digest = hashlib.sha256(json.dumps(
        ["wf-local-payload-snapshot/v1", version, records],
        ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return PayloadSnapshot(version, ordered, MappingProxyType(dict(ordered)), digest)


def _safe_live_roots(roots: Mapping[str, Path]) -> Mapping[str, Path]:
    if set(roots) != set(CLIENT_ROOTS):
        raise AdapterError("live root set must be exactly common, medium, android")
    selected: dict[str, Path] = {}
    for root in CLIENT_ROOTS:
        value = roots[root]
        if not isinstance(value, Path):
            value = Path(value)
        selected[root] = _assert_plain(value, leaf="directory")
    return MappingProxyType(selected)


def _source_unique_condition(roots: Mapping[str, Path]) -> bytes | None:
    """Read-only uid context for the capability gate (terminal common store)."""
    import wfx_gate

    target = core.table_path(roots["common"], wfx_gate.UNIQUE_CONDITION_LOGICAL)
    try:
        return target.read_bytes() if target.is_file() else None
    except OSError:
        return None


def _terminal_snapshot(
    bundle: local_contract.ContractBundle, roots: Mapping[str, Path]
) -> PayloadSnapshot:
    values: dict[MemberKey, bytes | None] = {}
    for member in bundle.terminal.members:
        if member.key in values:
            continue
        target = core.table_path(roots[member.root], member.logical_path)
        values[member.key] = _read_stable(
            target, f"terminal {member.root}:{member.logical_path}"
        )
    inventory.attest_source_contract(
        bundle.terminal, lambda member: values[member.key]  # type: ignore[return-value]
    )
    return _ordered_values(values, TARGET_VERSION)


def _relative_writer(path: Path, source_repo_root: Path) -> str:
    absolute = _absolute(path)
    try:
        relative = absolute.relative_to(source_repo_root).as_posix()
    except ValueError as error:
        raise AdapterError(f"baseline writer escapes source repo: {path}") from error
    if absolute.exists() or absolute.is_symlink():
        _assert_plain(absolute, leaf="file")
    return relative


def _baseline_snapshot(
    bundle: local_contract.ContractBundle,
    version: str,
    cdn_root: Path,
    source_repo_root: Path,
) -> PayloadSnapshot:
    provenance = {member.key: member for member in bundle.provenance.members}
    present = tuple(
        member.key for member in bundle.provenance.members
        if member.versions[version] is not None
    )
    resolved = inventory.resolve_allowlisted_members(
        cdn_root, source_repo_root, present, target_tail=version
    )
    if set(resolved) != set(present):
        raise AdapterError(f"baseline {version} resolver key set drift")
    values: dict[MemberKey, bytes | None] = {}
    for key in sorted(provenance, key=lambda item: (CLIENT_ROOTS.index(item[0]), item[1])):
        expected = provenance[key].versions[version]
        if expected is None:
            values[key] = None
            continue
        actual = resolved[key]
        if (
            actual.tail != version
            or _relative_writer(actual.writer_archive, source_repo_root) != expected.writer
            or actual.archive_member != expected.archive_member
            or len(actual.raw) != expected.size
            or hashlib.sha256(actual.raw).hexdigest() != expected.sha256
        ):
            raise AdapterError(f"baseline provenance drift for {version}:{key}")
        values[key] = actual.raw
    contract = bundle.baselines[version]
    inventory.attest_source_contract(
        contract, lambda member: values[member.key]  # type: ignore[return-value]
    )
    return _ordered_values(values, version)


def _output_snapshot(
    bundle: local_contract.ContractBundle,
    baseline: PayloadSnapshot,
    plan: scoped.EdgePlan,
) -> PayloadSnapshot:
    output = dict(baseline.mapping)
    for entry in plan.entries:
        output[(entry.root, entry.logical_path)] = entry.payload
    if any(raw is None for raw in output.values()):
        raise AdapterError(f"edge {plan.spec.patch_id} left an absent terminal path")
    inventory.attest_terminal_contract(
        bundle.terminal, lambda member: output[member.key]  # type: ignore[return-value]
    )
    return _ordered_values(output, plan.spec.to_version)


def _result_digest(
    bundle: local_contract.ContractBundle,
    terminal: PayloadSnapshot,
    edges: tuple[LocalEdgeEvidence, ...],
) -> str:
    records: list[object] = []
    for edge in edges:
        plan = edge.plan
        records.append({
            "spec": [
                plan.spec.from_version, plan.spec.to_version, plan.spec.tag,
                plan.spec.patch_id, plan.spec.name, plan.spec.description,
                plan.spec.created_at,
            ],
            "baseline": edge.baseline.digest,
            "output": edge.output.digest,
            "entries": [
                [entry.root, entry.logical_path, entry.member_name, len(entry.payload),
                 hashlib.sha256(entry.payload).hexdigest()]
                for entry in plan.entries
            ],
            "parts": [
                [part.root, part.sequence, part.name, len(part.blob),
                 hashlib.sha256(part.blob).hexdigest()]
                for part in plan.parts
            ],
        })
    payload = [
        "wf-local-scoped-plans/v1", bundle.terminal.contract_id,
        bundle.provenance.inventory_sha256, terminal.digest, records,
    ]
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def build_local_scoped_plans(
    contract_dir: Path,
    cdn_root: Path,
    source_repo_root: Path,
    terminal_roots: Mapping[str, Path],
) -> LocalScopedPlans:
    """Build both fixed edges without writing contracts, stores, archives, or manifest."""
    try:
        roots = _safe_live_roots(terminal_roots)
        contracts = _assert_plain(Path(contract_dir), leaf="directory")
        source = _assert_plain(Path(source_repo_root), leaf="directory")
        cdn = _assert_plain(Path(cdn_root), leaf="directory")
        if cdn != source / ".cdn" / "cn":
            raise AdapterError("cdn_root must be source_repo_root/.cdn/cn")
        bundle = local_contract.load_bundle(contracts)
        local_contract.validate_bundle(bundle)
        local_contract.attest_bundle_baselines(bundle, cdn, source)
        terminal = _terminal_snapshot(bundle, roots)
        baseline_by_version = {
            version: _baseline_snapshot(bundle, version, cdn, source)
            for version in bundle.baseline_versions
        }
        if set(baseline_by_version) != {"1.4.277", "1.4.311"}:
            raise AdapterError("frozen baseline version set drift")
        reader = lambda member: terminal.mapping[member.key]  # type: ignore[return-value]
        primary = scoped.build_edge_plan(
            bundle.terminal, baseline_by_version["1.4.277"].mapping,
            reader, PRIMARY_SPEC,
        )
        compatibility = scoped.build_edge_plan(
            bundle.terminal, baseline_by_version["1.4.311"].mapping,
            reader, COMPATIBILITY_SPEC,
        )
        if not primary.parts or not compatibility.parts:
            raise AdapterError("both fixed edges must contain changed payloads")
        baselines = (
            baseline_by_version["1.4.277"], baseline_by_version["1.4.311"]
        )
        edges = (
            LocalEdgeEvidence(
                primary, baselines[0], _output_snapshot(bundle, baselines[0], primary)
            ),
            LocalEdgeEvidence(
                compatibility, baselines[1],
                _output_snapshot(bundle, baselines[1], compatibility),
            ),
        )
        return LocalScopedPlans(
            bundle, terminal, baselines, primary, compatibility, edges,
            _result_digest(bundle, terminal, edges),
            _source_unique_condition(roots),
        )
    except AdapterError:
        raise
    except (
        OSError,
        KeyError,
        ValueError,
        inventory.InventoryError,
        scoped.ScopedReleaseError,
    ) as error:
        raise AdapterError(str(error)) from error


def publish_local_scoped_plans(
    result: LocalScopedPlans,
    output_repo_root: Path,
    *,
    selection: str,
    expected_manifest_sha256: str,
    confirmation: str,
    checkpoint: Callable[[str], None] | None = None,
    client_profile: str | None = None,
) -> tuple[Path, ...]:
    """Publish a selected immutable plan through the manifest-last transaction.

    client_profile is mandatory (receiving client profile, see
    mod-tools/client_profiles.json); the scoped publisher rejects None.
    uid references are resolved against the terminal store's unique_condition
    captured at build time (plus the edges' own unique_condition payloads).
    """
    if not isinstance(result, LocalScopedPlans):
        raise AdapterError("publish result is not a local scoped plan")
    if confirmation != PUBLISH_CONFIRMATION:
        raise AdapterError(f"publish requires {PUBLISH_CONFIRMATION}")
    root = _assert_plain(Path(output_repo_root), leaf="directory")
    active = root / "assets" / "asset-patch" / "active"
    manifest = active.parent / "manifest.json"
    unique_context = None
    if result.source_unique_condition is not None:
        import wfx_gate

        try:
            unique_context = wfx_gate.decode_rows(result.source_unique_condition)
        except Exception:
            unique_context = None
    try:
        return scoped.publish_archives_and_manifest(
            result.select(selection), active, manifest,
            expected_manifest_sha256=expected_manifest_sha256,
            checkpoint=checkpoint,
            client_profile=client_profile,
            client_unique_context=unique_context,
        )
    except scoped.ScopedReleaseError as error:
        raise AdapterError(str(error)) from error

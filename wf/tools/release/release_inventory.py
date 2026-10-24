#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only release inventory attestation and baseline provenance resolver."""
from __future__ import annotations

import hashlib
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, cast

import wf_character_pack as character_pack
import wf_mod_tool as core
import wf_release
import wf_store_materialize
from wf_release_inventory_contract import (
    CLIENT_ROOTS,
    InventoryContract,
    InventoryError,
    InventoryMember,
    MemberKey,
    Projection,
    SCHEMA,
    load_contract,
    parse_contract,
    project_claim,
    projection_sha256,
    validate_logical_path,
)


@dataclass(frozen=True, slots=True)
class ResolvedMember:
    root: str
    logical_path: str
    raw: bytes
    writer_archive: Path
    archive_member: str
    tail: str


@dataclass(frozen=True, slots=True)
class AttestationReport:
    member_count: int
    unique_claim_count: int


def attest_contract(
    contract: InventoryContract,
    reader: Callable[[InventoryMember], bytes],
) -> AttestationReport:
    """Attest terminal/live semantics.

    Table members compare only their declared projection so unrelated terminal
    rows may evolve.  Opaque files are whole-file owned and remain exact.
    """
    claims: dict[tuple[str, str, str, str | None], tuple[bytes, str]] = {}
    for member in contract.members:
        label = f"{member.owner}:{member.root}:{member.logical_path}"
        try:
            raw = reader(member)
        except (FileNotFoundError, KeyError, OSError) as error:
            raise InventoryError(f"missing member {label}: {error}") from error
        if not isinstance(raw, bytes):
            raise InventoryError(f"member reader returned non-bytes for {label}")
        if member.kind == "file":
            if len(raw) != member.size:
                raise InventoryError(
                    f"size drift for {label}: expected={member.size} actual={len(raw)}"
                )
            actual_sha = hashlib.sha256(raw).hexdigest()
            if actual_sha != member.sha256:
                raise InventoryError(
                    f"sha256 drift for {label}: expected={member.sha256} actual={actual_sha}"
                )
            projection = Projection((("*", None, raw),))
        else:
            claim = cast(character_pack.TableClaim, member.claim)
            projection = project_claim(raw, claim)
            actual_projection = projection_sha256(raw, claim)
            if actual_projection != member.projection_sha256:
                raise InventoryError(f"projection sha256 drift for {label}")
        for outer, inner, row in projection.rows:
            key = member.root, member.logical_path, outer, inner
            previous = claims.get(key)
            if previous is not None and previous[0] != row:
                raise InventoryError(
                    f"divergent overlap for {member.root}:{member.logical_path}:"
                    f"{outer}/{inner or '-'} between {previous[1]} and {member.owner}"
                )
            claims[key] = row, member.owner
    return AttestationReport(len(contract.members), len(claims))


def attest_source(
    contract: InventoryContract,
    reader: Callable[[InventoryMember], bytes],
) -> AttestationReport:
    """Attest an exact candidate or independently frozen baseline source."""
    def exact(member: InventoryMember) -> bytes:
        raw = reader(member)
        if not isinstance(raw, bytes):
            label = f"{member.owner}:{member.root}:{member.logical_path}"
            raise InventoryError(f"member reader returned non-bytes for {label}")
        if member.kind == "table":
            label = f"{member.owner}:{member.root}:{member.logical_path}"
            if len(raw) != member.source_size:
                raise InventoryError(
                    f"source size drift for {label}: "
                    f"expected={member.source_size} actual={len(raw)}"
                )
            actual_sha = hashlib.sha256(raw).hexdigest()
            if actual_sha != member.source_sha256:
                raise InventoryError(
                    f"source sha256 drift for {label}: "
                    f"expected={member.source_sha256} actual={actual_sha}"
                )
        return raw

    return attest_contract(contract, exact)


attest_terminal_contract = attest_contract
attest_source_contract = attest_source


def _live_path(roots: Mapping[str, Path], member: InventoryMember) -> Path:
    if member.root not in roots:
        raise FileNotFoundError(f"live root is not configured: {member.root}")
    root = Path(roots[member.root]).resolve()
    target = (
        root.joinpath(*member.logical_path.split("/"))
        if member.root == "server"
        else core.table_path(root, member.logical_path)
    )
    resolved = target.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise OSError(f"live member escapes root: {target}") from error
    if target.is_symlink() or not resolved.is_file():
        raise OSError(f"unsafe live member: {target}")
    return resolved


def attest_live_roots(
    contract: InventoryContract, roots: Mapping[str, Path]
) -> AttestationReport:
    """Attest terminal roots; table-level source hashes are intentionally ignored."""
    return attest_contract(contract, lambda member: _live_path(roots, member).read_bytes())


def _contained_archive(path: Path, allowed_roots: tuple[Path, ...]) -> Path:
    if path.is_symlink():
        raise InventoryError(f"unsafe symlink baseline archive: {path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise InventoryError(f"missing baseline archive: {path}") from error
    if not resolved.is_file():
        raise InventoryError(f"baseline archive is not a file: {path}")
    if not any(
        _is_relative_to(resolved, root.resolve()) for root in allowed_roots
    ):
        raise InventoryError(f"baseline archive escapes allowed roots: {path}")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _archive_raw(
    entry: wf_store_materialize.PlannedEntry,
    allowed_roots: tuple[Path, ...],
) -> bytes:
    archive_path = _contained_archive(entry.zip_path, allowed_roots)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            matches = [info for info in archive.infolist() if info.filename == entry.name]
            if len(matches) > 1:
                raise InventoryError(f"duplicate ZIP member {archive_path}!{entry.name}")
            if not matches:
                raise InventoryError(f"missing ZIP member {archive_path}!{entry.name}")
            info = matches[0]
            if info.is_dir() or info.file_size != entry.size or info.CRC != entry.crc:
                raise InventoryError(
                    f"archive member changed after planning: {archive_path}!{entry.name}"
                )
            chunks: list[bytes] = []
            with archive.open(info) as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b""):
                    chunks.append(chunk)
            raw = b"".join(chunks)
    except InventoryError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise InventoryError(f"cannot read baseline archive member: {error}") from error
    if len(raw) != entry.size or (zlib.crc32(raw) & 0xFFFFFFFF) != entry.crc:
        raise InventoryError(f"baseline member readback drift: {archive_path}!{entry.name}")
    return raw


def resolve_allowlisted_members(
    cdn_root: Path,
    repo_root: Path,
    allowlist: Iterable[MemberKey],
    *,
    target_tail: str | None = None,
    official_only: bool = False,
) -> dict[MemberKey, ResolvedMember]:
    requested: list[MemberKey] = []
    for root, logical in allowlist:
        if root not in CLIENT_ROOTS:
            raise InventoryError(f"baseline resolver does not support root {root!r}")
        key = root, validate_logical_path(logical, "allowlist")
        if key in requested:
            raise InventoryError(f"duplicate allowlist member: {root}:{logical}")
        requested.append(key)
    if not requested:
        raise InventoryError("baseline allowlist must not be empty")
    try:
        plan = wf_store_materialize.build_read_only_plan(
            Path(cdn_root), Path(repo_root), target_tail, official_only
        )
    except wf_store_materialize.MaterializeError as error:
        raise InventoryError(f"cannot resolve baseline plan: {error}") from error
    if plan.rejected:
        raise InventoryError(f"baseline plan rejected {plan.rejected} unsafe members")
    if plan.health.issues:
        raise InventoryError(f"baseline graph issue: {plan.health.issues[0]}")
    if (
        target_tail is None
        and not official_only
        and plan.health.gap(plan.tail)
    ):
        raise InventoryError(
            "baseline graph has a newer visible but unreachable tail: "
            f"resolved={plan.tail} visible={plan.health.max_visible}"
        )
    allowed_roots = (
        Path(cdn_root),
        Path(repo_root) / "assets" / "asset-patch" / "active",
    )
    result: dict[MemberKey, ResolvedMember] = {}
    for root, logical in requested:
        digest = core.sha1_path(logical)
        entry = plan.entries.get((root, f"{digest[:2]}/{digest[2:]}"))
        if entry is None:
            raise InventoryError(f"missing baseline member: {root}:{logical}")
        result[(root, logical)] = ResolvedMember(
            root, logical, _archive_raw(entry, allowed_roots),
            entry.zip_path, entry.name, plan.tail,
        )
    return result


def attest_baseline(
    contract: InventoryContract,
    cdn_root: Path,
    repo_root: Path,
    *,
    target_tail: str | None = None,
    official_only: bool = False,
) -> AttestationReport:
    """Attest against an independently frozen baseline contract.

    A terminal contract must not be reused when its owned rows differ from the
    historical base.  Callers freeze a distinct baseline expectation, whose
    table ``source`` hashes bind the exact archive member returned by resolver.
    """
    if any(member.root == "server" for member in contract.members):
        raise InventoryError("baseline CDN attestation cannot resolve server members")
    resolved = resolve_allowlisted_members(
        cdn_root,
        repo_root,
        dict.fromkeys(member.key for member in contract.members),
        target_tail=target_tail,
        official_only=official_only,
    )
    return attest_source(contract, lambda member: resolved[member.key].raw)


def merge_claimed_member(
    member: InventoryMember, candidate_raw: bytes, live_raw: bytes
) -> bytes:
    label = f"{member.owner}:{member.root}:{member.logical_path}"
    if member.kind == "file":
        if (
            len(candidate_raw) != member.size
            or hashlib.sha256(candidate_raw).hexdigest() != member.sha256
        ):
            raise InventoryError(f"whole-file drift for {label}")
        return candidate_raw
    claim = cast(character_pack.TableClaim, member.claim)
    if projection_sha256(candidate_raw, claim) != member.projection_sha256:
        raise InventoryError(f"projection sha256 drift for {label}")
    try:
        return wf_release.merge_claimed_table_bytes(claim, candidate_raw, live_raw)
    except wf_release.ReleaseError as error:
        raise InventoryError(f"cannot merge claimed member {label}: {error}") from error

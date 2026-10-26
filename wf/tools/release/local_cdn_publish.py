#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atomic stopped-server publication of the fixed 311->312 edge to local CDN roots."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import wf_local_scoped_release as adapter
import wf_local_server_status as server_status
import wf_scoped_release as scoped
import wf_scoped_release_archive as archive
import wf_scoped_release_transaction as transaction
import wf_scoped_release_validation as validation


CONFIRMATION = "PUBLISH_LOCAL_CDN_1_4_312"
LOCK_NAME = ".wf-local-1.4.312.lock"
COMPATIBILITY_EDGE_DIGEST = (
    "28131158c75402a7df59a2e0df4b882a451d406c6cbb9eb6476d6efcad9b3983"
)
ROOT_DIRS = {
    "common": "archive-common-diff",
    "medium": "archive-medium-diff",
    "android": "archive-android-diff",
}


class LocalCdnPublishError(RuntimeError):
    """The local CDN edge was rejected, rolled back, or retained its lock."""


@dataclass(frozen=True, slots=True)
class LocalCdnPublishResult:
    edge_digest: str
    paths: tuple[Path, ...]


def _edge_digest(plan: scoped.EdgePlan) -> str:
    payload = [
        "wf-local-cdn-edge/v1",
        [
            plan.spec.from_version,
            plan.spec.to_version,
            plan.spec.tag,
            plan.spec.patch_id,
        ],
        [
            [
                part.root,
                part.sequence,
                part.name,
                len(part.blob),
                hashlib.sha256(part.blob).hexdigest(),
            ]
            for part in plan.parts
        ],
    ]
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def _directories(cdn_root: Path) -> tuple[Path, dict[str, Path]]:
    root = transaction._assert_plain_ancestry(
        Path(cdn_root), leaf="directory"
    )
    if root.name != "cn" or root.parent.name != ".cdn":
        raise LocalCdnPublishError("cdn_root must be <repo>/.cdn/cn")
    directories = {
        name: transaction._assert_plain_ancestry(
            root / directory, leaf="directory"
        )
        for name, directory in ROOT_DIRS.items()
    }
    return root, directories


def _preflight(
    plan: scoped.EdgePlan, directories: dict[str, Path]
) -> tuple[tuple[archive.ArchivePart, ...], str]:
    if plan.spec != adapter.COMPATIBILITY_SPEC:
        raise LocalCdnPublishError(
            "local CDN publisher only accepts the fixed 1.4.311->1.4.312 edge"
        )
    if not plan.parts:
        raise LocalCdnPublishError("local compatibility edge has no archive parts")
    try:
        archive.attest_plan_parts(plan.entries, plan.parts)
        parts = validation.parts((plan,))
    except (archive.ArchiveError, validation.TransactionError) as error:
        raise LocalCdnPublishError(str(error)) from error
    digest = _edge_digest(plan)
    if digest != COMPATIBILITY_EDGE_DIGEST:
        raise LocalCdnPublishError(
            "local compatibility edge digest differs from the frozen real edge: "
            f"{digest}"
        )
    return parts, digest


def _edge_archives(directories: dict[str, Path]) -> tuple[Path, ...]:
    prefix = "pinball-1.4.311-1.4.312-"
    return tuple(sorted(
        (
            candidate
            for directory in directories.values()
            for candidate in directory.iterdir()
            if candidate.name.casefold().startswith(prefix)
            and candidate.name.casefold().endswith(".zip")
        ),
        key=lambda path: str(path),
    ))


def _existing_edge_complete(
    parts: tuple[archive.ArchivePart, ...],
    targets: tuple[Path, ...],
    directories: dict[str, Path],
) -> bool:
    found = _edge_archives(directories)
    if not found:
        return False
    if len(found) != len(targets) or set(found) != set(targets):
        raise LocalCdnPublishError(
            "existing local edge is partial, mismatched, or in the wrong root: "
            + ", ".join(str(path) for path in found)
        )
    for part, target in zip(parts, targets, strict=True):
        raw, _identity = transaction._read_stable(
            target, f"existing local CDN archive {part.name}"
        )
        if raw != part.blob:
            raise LocalCdnPublishError(
                f"existing local CDN archive bytes mismatch: {part.name}"
            )
        validation.validate_blob(part, raw)
    return True


def _require_stopped(probe: Callable[[], bool]) -> None:
    try:
        running = probe()
    except LocalCdnPublishError:
        raise
    except Exception as error:
        raise LocalCdnPublishError(
            f"server stopped state cannot be verified: {error}"
        ) from error
    if running is True:
        raise LocalCdnPublishError(
            "CN server must be stopped before local CDN publication"
        )
    if running is not False:
        raise LocalCdnPublishError(
            "server stopped probe returned an invalid result"
        )


def _verify(
    parts: tuple[archive.ArchivePart, ...],
    targets: tuple[Path, ...],
    owned: tuple[transaction._OwnedPath, ...],
) -> None:
    for part, target, authority in zip(parts, targets, owned, strict=True):
        raw, identity = transaction._read_stable(
            target, f"local CDN archive {part.name}"
        )
        if (
            raw != part.blob
            or identity[:2] != authority.object_id
        ):
            raise LocalCdnPublishError(
                f"local CDN archive bytes or identity changed: {part.name}"
            )
        validation.validate_blob(part, raw)


def _sync(directories: dict[str, Path], parts: tuple[archive.ArchivePart, ...]) -> None:
    for root in archive.CLIENT_ROOTS:
        if any(part.root == root for part in parts):
            transaction._fsync_directory(directories[root])


def publish_local_311_edge(
    plan: scoped.EdgePlan,
    cdn_root: Path,
    *,
    confirmation: str,
    checkpoint: Callable[[str], None] | None = None,
    server_probe: Callable[[], bool] | None = None,
) -> LocalCdnPublishResult:
    """Publish without renumbering; the lock removal is the transaction commit point."""
    if confirmation != CONFIRMATION:
        raise LocalCdnPublishError(f"publication requires {CONFIRMATION}")
    try:
        root, directories = _directories(Path(cdn_root))
        parts, digest = _preflight(plan, directories)
    except LocalCdnPublishError:
        raise
    except (OSError, transaction.TransactionError) as error:
        raise LocalCdnPublishError(str(error)) from error
    targets = tuple(directories[part.root] / part.name for part in parts)
    token = uuid.uuid4().hex
    pending = tuple(
        directories[part.root] / f".wf-local-{token}-{part.sequence}.pending"
        for part in parts
    )
    lock = root / LOCK_NAME
    callback = checkpoint or (lambda _phase: None)
    lock_owned: list[transaction._OwnedPath] = []
    private_owned: list[transaction._OwnedPath] = []
    final_owned: list[transaction._OwnedPath] = []
    try:
        transaction._write_exclusive(
            lock, bytes.fromhex(digest), lock_owned
        )
        transaction._fsync_directory(root)
        if _existing_edge_complete(parts, targets, directories):
            lock_cleanup = transaction._remove_owned(lock_owned)
            if lock_cleanup:
                raise LocalCdnPublishError(
                    "existing local CDN edge is valid but lock cleanup failed: "
                    + "; ".join(lock_cleanup)
                )
            transaction._fsync_directory(root)
            return LocalCdnPublishResult(digest, targets)

        probe = (
            server_probe
            if server_probe is not None
            else lambda: server_status.server_running(root.parent.parent)
        )
        _require_stopped(probe)
        for part, private in zip(parts, pending, strict=True):
            transaction._write_exclusive(private, part.blob, private_owned)
        _sync(directories, parts)

        for part, private, target in zip(parts, pending, targets, strict=True):
            authority = next(item for item in private_owned if item.path == private)
            transaction._link_owned(authority, target, final_owned)
            cleanup = transaction._remove_owned((authority,))
            private_owned.remove(authority)
            if cleanup:
                raise LocalCdnPublishError(
                    "pending archive cleanup incomplete: " + "; ".join(cleanup)
                )
            callback("after_archive")
        _sync(directories, parts)
        _verify(parts, targets, tuple(final_owned))
        callback("before_commit")
        _verify(parts, targets, tuple(final_owned))
        _require_stopped(probe)
    except BaseException as error:
        cleanup = transaction._remove_owned(private_owned)
        cleanup.extend(transaction._remove_owned(final_owned))
        if isinstance(error, transaction._UncertainLinkError):
            cleanup.append(str(error))
        try:
            _sync(directories, parts)
        except (OSError, transaction.TransactionError) as sync_error:
            cleanup.append(f"directory sync: {sync_error}")
        if cleanup:
            raise LocalCdnPublishError(
                "local CDN rollback incomplete; lock retained: "
                + "; ".join(cleanup)
            ) from error
        lock_cleanup = transaction._remove_owned(lock_owned)
        if lock_cleanup:
            raise LocalCdnPublishError(
                "local CDN rollback finished but lock is retained: "
                + "; ".join(lock_cleanup)
            ) from error
        if isinstance(error, LocalCdnPublishError):
            raise
        raise LocalCdnPublishError(str(error)) from error

    lock_cleanup = transaction._remove_owned(lock_owned)
    if lock_cleanup:
        raise LocalCdnPublishError(
            "local CDN archives committed but lock cleanup failed: "
            + "; ".join(lock_cleanup)
        )
    transaction._fsync_directory(root)
    transaction._release_owned(final_owned)
    transaction._release_owned(private_owned)
    return LocalCdnPublishResult(digest, targets)

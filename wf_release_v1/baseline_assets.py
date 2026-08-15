"""Fail-closed before-byte gates for sealed shared-asset replacements."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import zipfile

from wf_offline_store import StoreError, _require_same_lstat, _stable_reader

from ._baseline_snapshot import (
    ArchiveDescriptor,
    _guard_file,
    assert_unchanged,
    load_snapshot_authority,
)
from ._legacy_mapping import _hashed_member
from .compatibility import VerifiedRelease
from .errors import ReleaseError
from .probe import TargetFacts
from .schema import AssetReplacement
from .target import ManagedTarget


_ROOT_LAYER = {"common": "common", "medium": "quality", "android": "platform"}


@dataclass(frozen=True)
class AssetBaselineReport:
    checked: int
    asset_version: str
    release_digest: str


def _unavailable(message: str, *, label: str) -> ReleaseError:
    return ReleaseError(
        "WFREL_ASSET_BASELINE_UNAVAILABLE",
        message,
        {"label": label},
    )


def _mismatch(item: AssetReplacement) -> ReleaseError:
    return ReleaseError(
        "WFREL_ASSET_BASELINE_MISMATCH",
        "active asset bytes do not match the sealed before identity",
        {"asset": f"{item.root}:{item.logical_path}"},
    )


def _source_root(target: ManagedTarget, archive: ArchiveDescriptor) -> Path:
    if archive.source_kind == "baseline":
        return target.cdn_root / "cn"
    if archive.source_kind == "patch" and archive.source_target_version is not None:
        return target.cdn_root / "patches" / archive.source_target_version
    raise _unavailable("archive source cannot be resolved", label=archive.relative_path)


def _member_identity(
    target: ManagedTarget,
    archive: ArchiveDescriptor,
    member_name: str,
    *,
    expected_size: int,
) -> tuple[int, str] | None:
    source_root = _source_root(target, archive)
    path, guards = _guard_file(
        source_root,
        archive.relative_path,
        label="content archive",
    )
    signature = guards[-1][1]
    if signature[3] != archive.compressed_bytes:
        raise _unavailable(
            "archive size disagrees with the active catalog",
            label=archive.relative_path,
        )
    try:
        with _stable_reader(path, signature, kind="content archive") as stream:
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != archive.sha256:
                raise _unavailable(
                    "archive digest disagrees with the active catalog",
                    label=archive.relative_path,
                )
            stream.seek(0, os.SEEK_SET)
            with zipfile.ZipFile(stream) as bundle:
                matches = [info for info in bundle.infolist() if info.filename == member_name]
                if len(matches) > 1:
                    raise _unavailable(
                        "archive contains a duplicate physical asset member",
                        label=archive.relative_path,
                    )
                if not matches:
                    result = None
                else:
                    info = matches[0]
                    if info.is_dir() or info.file_size < 0:
                        raise _unavailable(
                            "archive asset member is not a regular file",
                            label=archive.relative_path,
                        )
                    if info.file_size != expected_size:
                        result = (info.file_size, "")
                    else:
                        member_digest = hashlib.sha256()
                        size = 0
                        with bundle.open(info, "r") as reader:
                            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                                size += len(chunk)
                                if size > expected_size:
                                    break
                                member_digest.update(chunk)
                        result = (size, member_digest.hexdigest())
    except ReleaseError:
        raise
    except (OSError, RuntimeError, StoreError, zipfile.BadZipFile) as error:
        raise _unavailable(
            "active content archive cannot be verified",
            label=archive.relative_path,
        ) from error
    try:
        for guard_path, guard_signature, kind in guards:
            _require_same_lstat(guard_path, guard_signature, kind=kind)
    except StoreError as error:
        raise _unavailable(
            "active content archive changed during verification",
            label=archive.relative_path,
        ) from error
    return result


def _verify_one(
    release: VerifiedRelease,
    target: ManagedTarget,
    archives: tuple[ArchiveDescriptor, ...],
    item: AssetReplacement,
) -> None:
    del release
    member_name = _hashed_member(item.root, item.logical_path)
    layer = _ROOT_LAYER[item.root]
    for archive in reversed(archives):
        if archive.layer != layer:
            continue
        identity = _member_identity(
            target,
            archive,
            member_name,
            expected_size=item.before_size,
        )
        if identity is None:
            continue
        if identity != (item.before_size, item.before_sha256):
            raise _mismatch(item)
        return
    raise _mismatch(item)


def verify_asset_replacement_baseline(
    verified: VerifiedRelease,
    target: ManagedTarget,
    facts: TargetFacts | None = None,
) -> AssetBaselineReport:
    """Verify current effective bytes without modifying target or release state."""
    if not isinstance(verified, VerifiedRelease) or not isinstance(target, ManagedTarget):
        raise _unavailable("asset baseline inputs are invalid", label="inputs")
    replacements = verified.manifest.source_evidence.accepted_asset_replacements
    if not replacements:
        return AssetBaselineReport(0, "", "")
    if verified.overlay is None:
        raise _unavailable("release overlay evidence is missing", label="release.overlay")
    if facts is not None and not isinstance(facts, TargetFacts):
        raise _unavailable("target facts are invalid", label="targetFacts")
    if facts is not None and facts.cdn_target_version != verified.overlay.from_version:
        raise _unavailable(
            "live target version disagrees with release overlay",
            label="targetFacts.cdnTargetVersion",
        )
    if facts is not None and facts.release_digest is None:
        raise _unavailable(
            "live target does not identify a managed Content Snapshot",
            label="targetFacts.releaseDigest",
        )
    authority = load_snapshot_authority(
        target,
        expected_version=verified.overlay.from_version,
        expected_release_digest=None if facts is None else facts.release_digest,
    )
    for item in replacements:
        _verify_one(verified, target, authority.archives, item)
    for snapshot in authority.evidence:
        assert_unchanged(snapshot)
    return AssetBaselineReport(
        len(replacements),
        authority.asset_version,
        authority.release_digest,
    )


__all__ = ["AssetBaselineReport", "verify_asset_replacement_baseline"]

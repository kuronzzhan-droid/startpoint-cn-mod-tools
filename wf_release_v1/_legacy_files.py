"""Private staging and exact recovery helpers for legacy CDN archives."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Final
import zipfile

from ._legacy_zip import central_preflight, copy_member, validate_infos
from ._platform_state import validate_operation_id
from .canonical import FileIdentity
from .errors import ReleaseError
from .legacy_compatibility import LegacyInstallPlan
from .materialize import CandidateSet
from .receipts import _sync_directory
from .verifier_overlay import VerifiedOverlayArchive


_REPARSE_POINT: Final = 0x0400


def _error(message: str, *, code: str = "WFREL_LEGACY_CDN_IO") -> ReleaseError:
    return ReleaseError(code, message)


def _is_reparse(item: os.stat_result) -> bool:
    return stat.S_ISLNK(item.st_mode) or bool(
        getattr(item, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _directory(path: Path) -> tuple[int, int]:
    try:
        item = path.lstat()
    except OSError:
        raise _error("legacy CDN directory is unavailable") from None
    if not stat.S_ISDIR(item.st_mode) or _is_reparse(item):
        raise _error("legacy CDN directory is unsafe")
    return item.st_dev, item.st_ino


def _file_identity(path: Path) -> tuple[int, int, int, int]:
    try:
        item = path.lstat()
    except OSError:
        raise _error("legacy CDN archive is unavailable") from None
    if not stat.S_ISREG(item.st_mode) or _is_reparse(item):
        raise _error("legacy CDN archive is unsafe")
    return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns


def _hash_file(path: Path) -> FileIdentity:
    expected = _file_identity(path)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as reader:
            opened = os.fstat(reader.fileno())
            if (
                opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns
            ) != expected:
                raise OSError("opened identity changed")
            while chunk := reader.read(1024 * 1024):
                digest.update(chunk)
            opened_after = os.fstat(reader.fileno())
        after = _file_identity(path)
    except OSError:
        raise _error("legacy CDN archive changed while it was read") from None
    if (
        opened_after.st_dev,
        opened_after.st_ino,
        opened_after.st_size,
        opened_after.st_mtime_ns,
    ) != expected or after != expected:
        raise _error("legacy CDN archive changed while it was read")
    return FileIdentity(expected[2], digest.hexdigest())


def _ensure_staging(state_root: Path, operation_id: str) -> Path:
    validate_operation_id(operation_id)
    state_identity = _directory(state_root)
    staging = state_root / "staging"
    try:
        staging.mkdir()
    except FileExistsError:
        pass
    except OSError:
        raise _error("legacy staging root could not be created") from None
    if _directory(state_root) != state_identity:
        raise _error("legacy state root changed")
    _directory(staging)
    operation = staging / operation_id
    try:
        operation.mkdir()
    except OSError:
        raise _error("legacy operation staging already exists", code="WFREL_STATE_CONFLICT") from None
    _directory(operation)
    _sync_directory(staging)
    return operation


@dataclass(frozen=True)
class StagedLegacyArchive:
    relative_path: str
    size: int
    sha256: str
    staging_path: Path = field(repr=False)
    target_path: Path = field(repr=False)


@dataclass(frozen=True)
class LegacyFileSwitch:
    operation_id: str
    archives: tuple[StagedLegacyArchive, ...]
    staging_root: Path = field(repr=False)
    staging_parent_identity: tuple[int, int] = field(repr=False)
    target_parent_identities: tuple[tuple[int, int], ...] = field(repr=False)


def _extract_expected(
    outer: Path,
    identity: FileIdentity,
    remaining: dict[str, VerifiedOverlayArchive],
    operation: Path,
    staged: list[StagedLegacyArchive],
    cn_root: Path,
) -> None:
    before = _file_identity(outer)
    if FileIdentity(before[2], _hash_file(outer).sha256) != identity:
        raise _error("candidate Overlay identity changed")
    try:
        with outer.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != before:
                raise OSError("opened identity changed")
            central_preflight(stream)
            with zipfile.ZipFile(stream) as bundle:
                members = dict(validate_infos(bundle.infolist(), allow_directories=False))
                for relative_path in tuple(remaining):
                    info = members.get(relative_path)
                    if info is None:
                        continue
                    expected = remaining.pop(relative_path)
                    index = len(staged)
                    staging_path = operation / f"archive-{index}.zip"
                    try:
                        with staging_path.open("xb") as writer:
                            size, digest = copy_member(bundle, info, writer)
                            os.fsync(writer.fileno())
                    except OSError:
                        try:
                            staging_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                        raise _error("legacy archive staging could not be written") from None
                    if size != expected.size or digest != expected.sha256:
                        raise _error("legacy archive identity disagrees with verified facts")
                    if _hash_file(staging_path) != FileIdentity(size, digest):
                        raise _error("legacy archive staging readback disagrees")
                    staged.append(StagedLegacyArchive(
                        relative_path,
                        size,
                        digest,
                        staging_path,
                        cn_root / Path(relative_path),
                    ))
            opened_after = os.fstat(stream.fileno())
        after = _file_identity(outer)
    except ReleaseError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise _error("candidate Overlay changed while it was read") from error
    if (
        opened_after.st_dev,
        opened_after.st_ino,
        opened_after.st_size,
        opened_after.st_mtime_ns,
    ) != before or after != before:
        raise _error("candidate Overlay changed while it was read")


def prepare_legacy_switch(
    candidates: CandidateSet,
    plan: LegacyInstallPlan,
    state_root: Path,
    cdn_root: Path,
    operation_id: str,
) -> LegacyFileSwitch:
    """Extract exact verified inner archives into same-volume private staging."""
    if (
        not isinstance(candidates, CandidateSet)
        or not isinstance(plan, LegacyInstallPlan)
        or not plan.installable
        or plan.no_op
        or candidates.release_id != plan.release_id
        or candidates.content_root is None
        or candidates.server_root is not None
        or candidates.modes_root is not None
        or len(candidates.relative_paths) != len(candidates.identities)
    ):
        raise _error("legacy switch input is invalid")
    cn_root = cdn_root / "cn"
    if _directory(state_root)[0] != _directory(cn_root)[0]:
        raise _error("legacy staging and CDN roots must share one volume")
    expected = {
        archive.relative_path: archive
        for edge in plan.overlay.edges
        for archive in edge.archives
    }
    if len(expected) != sum(len(edge.archives) for edge in plan.overlay.edges):
        raise _error("verified legacy archive paths are ambiguous")
    operation = _ensure_staging(state_root, operation_id)
    staged: list[StagedLegacyArchive] = []
    try:
        retained_overlays = tuple(
            (relative, identity)
            for relative, identity in zip(
                candidates.relative_paths, candidates.identities, strict=True
            )
            if (
                len(PurePosixPath(relative).parts) == 3
                and PurePosixPath(relative).parts[0] == "patches"
                and PurePosixPath(relative).name
                not in {"README.md", "requires.json", "patch-manifest.json"}
            )
        )
        if len(retained_overlays) != len(plan.overlay.edges):
            raise _error("verified legacy Overlay set is incomplete")
        for relative, identity in retained_overlays:
            _extract_expected(
                candidates.content_root / Path(relative),
                identity,
                expected,
                operation,
                staged,
                cn_root,
            )
        if expected or not staged:
            raise _error("verified legacy archives are incomplete")
        staged.sort(key=lambda item: item.relative_path.encode("utf-8"))
        target_parents: list[tuple[int, int]] = []
        for item in staged:
            parent = item.target_path.parent
            target_parents.append(_directory(parent))
            if item.target_path.exists() or item.target_path.is_symlink():
                raise _error("legacy archive target already exists", code="WFREL_LEGACY_CDN_CONFLICT")
        _sync_directory(operation)
        return LegacyFileSwitch(
            operation_id,
            tuple(staged),
            operation,
            _directory(operation.parent),
            tuple(target_parents),
        )
    except ReleaseError:
        for item in staged:
            try:
                item.staging_path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            operation.rmdir()
            _sync_directory(operation.parent)
        except OSError:
            pass
        raise


def _link_archive(
    item: StagedLegacyArchive,
    parent_identity: tuple[int, int],
) -> None:
    """Commit one archive without replacing an existing target path."""
    try:
        if _directory(item.target_path.parent) != parent_identity:
            raise OSError("target parent changed")
        if item.target_path.exists() or item.target_path.is_symlink():
            raise _error(
                "legacy archive target already exists",
                code="WFREL_LEGACY_CDN_CONFLICT",
            )
        if _hash_file(item.staging_path) != FileIdentity(item.size, item.sha256):
            raise OSError("staging archive changed")
        os.link(item.staging_path, item.target_path)
        _sync_directory(item.target_path.parent)
        if _hash_file(item.target_path) != FileIdentity(item.size, item.sha256):
            raise OSError("target readback disagrees")
        item.staging_path.unlink()
        _sync_directory(item.staging_path.parent)
    except ReleaseError:
        raise
    except OSError:
        raise _error("legacy archive could not be committed") from None


def verify_legacy_switch(switch: LegacyFileSwitch) -> None:
    """Read back every exact target archive after the switch."""
    if not isinstance(switch, LegacyFileSwitch):
        raise _error("legacy switch is invalid")
    for item, parent_identity in zip(
        switch.archives, switch.target_parent_identities, strict=True
    ):
        if _directory(item.target_path.parent) != parent_identity or _hash_file(
            item.target_path
        ) != FileIdentity(item.size, item.sha256):
            raise _error("legacy archive readback disagrees")


def restore_legacy_switch(switch: LegacyFileSwitch) -> None:
    """Remove only unchanged archives created by this operation."""
    if not isinstance(switch, LegacyFileSwitch):
        raise _error("legacy switch is invalid")
    failure = False
    for item, parent_identity in zip(
        reversed(switch.archives), reversed(switch.target_parent_identities), strict=True
    ):
        if not (item.target_path.exists() or item.target_path.is_symlink()):
            continue
        try:
            if _directory(item.target_path.parent) != parent_identity:
                raise OSError("parent changed")
            if _hash_file(item.target_path) != FileIdentity(item.size, item.sha256):
                raise OSError("archive changed")
            item.target_path.unlink()
            _sync_directory(item.target_path.parent)
        except (OSError, ReleaseError):
            failure = True
    if failure:
        raise _error("legacy archive recovery could not restore exact bytes", code="WFREL_RECOVERY_FAILED")


def finalize_legacy_switch(switch: LegacyFileSwitch) -> None:
    """Remove only the operation's verified private staging files."""
    if not isinstance(switch, LegacyFileSwitch):
        raise _error("legacy switch is invalid")
    try:
        if _directory(switch.staging_root.parent) != switch.staging_parent_identity:
            raise OSError("staging parent changed")
        for item in switch.archives:
            if item.staging_path.exists() or item.staging_path.is_symlink():
                if _hash_file(item.staging_path) != FileIdentity(item.size, item.sha256):
                    raise OSError("staging archive changed")
                item.staging_path.unlink()
        switch.staging_root.rmdir()
        _sync_directory(switch.staging_root.parent)
    except (OSError, ReleaseError):
        raise _error("legacy staging could not be finalized") from None


__all__ = [
    "LegacyFileSwitch",
    "StagedLegacyArchive",
    "_link_archive",
    "finalize_legacy_switch",
    "prepare_legacy_switch",
    "restore_legacy_switch",
    "verify_legacy_switch",
]

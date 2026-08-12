"""Exact staged removal and restoration of one legacy Overlay release."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from ._legacy_files import (
    LegacyFileSwitch,
    _directory,
    _ensure_staging,
    _extract_expected,
    _hash_file,
    _link_archive,
)
from .canonical import FileIdentity
from .compatibility import VerifiedRelease
from .errors import ReleaseError
from .receipts import _sync_directory
from .verifier_overlay import VerifiedOverlayChain


def _error(message: str, *, code: str = "WFREL_LEGACY_CDN_IO") -> ReleaseError:
    return ReleaseError(code, message)


def prepare_legacy_removal(
    release: VerifiedRelease,
    content_root: Path,
    state_root: Path,
    cdn_root: Path,
    operation_id: str,
) -> LegacyFileSwitch:
    """Stage exact rollback bytes and prove every installed archive is unchanged."""
    if not isinstance(release, VerifiedRelease):
        raise _error("legacy rollback Release is unsupported", code="WFREL_TARGET_PROTOCOL")
    overlay = release.overlay
    kinds = tuple(item.kind for item in release.manifest.components)
    files = tuple(item for item in release.manifest.files if item.path.startswith("content/"))
    if (
        not isinstance(overlay, VerifiedOverlayChain)
        or kinds != ("content",)
        or len(files) != len(release.manifest.files)
        or not files
        or release.manifest.expected_state.cdn_target_version != overlay.target_version
    ):
        raise _error("legacy rollback Release is unsupported", code="WFREL_TARGET_PROTOCOL")
    cn_root = cdn_root / "cn"
    if _directory(state_root)[0] != _directory(cn_root)[0]:
        raise _error("legacy rollback staging and CDN roots must share one volume")
    candidate_root = content_root / release.manifest.release_id.replace(":", "-", 1)
    expected = {
        archive.relative_path: archive
        for edge in overlay.edges
        for archive in edge.archives
    }
    if len(expected) != sum(len(edge.archives) for edge in overlay.edges):
        raise _error("legacy rollback archive paths are ambiguous")
    operation = _ensure_staging(state_root, operation_id)
    staged = []
    try:
        candidate_names: set[str] = set()
        for item in files:
            name = PurePosixPath(item.path).name
            if not name or name in candidate_names:
                raise _error("legacy rollback candidate paths are ambiguous")
            candidate_names.add(name)
            _extract_expected(
                candidate_root / "patches" / overlay.target_version / name,
                FileIdentity(item.size, item.sha256),
                expected,
                operation,
                staged,
                cn_root,
            )
        if expected or not staged:
            raise _error("legacy rollback archives are incomplete")
        staged.sort(key=lambda item: item.relative_path.encode("utf-8"))
        parents: list[tuple[int, int]] = []
        for item in staged:
            parent = _directory(item.target_path.parent)
            parents.append(parent)
            if _hash_file(item.target_path) != FileIdentity(item.size, item.sha256):
                raise _error("legacy rollback target archive changed")
        _sync_directory(operation)
        return LegacyFileSwitch(
            operation_id,
            tuple(staged),
            operation,
            _directory(operation.parent),
            tuple(parents),
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


def remove_legacy_archives(switch: LegacyFileSwitch) -> None:
    """Remove only unchanged installed archives, retaining rollback bytes."""
    if not isinstance(switch, LegacyFileSwitch):
        raise _error("legacy rollback switch is invalid")
    try:
        for item, parent in zip(
            reversed(switch.archives), reversed(switch.target_parent_identities), strict=True
        ):
            if _directory(item.target_path.parent) != parent or _hash_file(
                item.target_path
            ) != FileIdentity(item.size, item.sha256):
                raise OSError("installed archive changed")
            item.target_path.unlink()
            _sync_directory(item.target_path.parent)
    except (OSError, ReleaseError):
        raise _error("legacy rollback archive removal failed") from None


def restore_removed_archives(switch: LegacyFileSwitch) -> None:
    """Restore each missing archive and reject every changed survivor."""
    if not isinstance(switch, LegacyFileSwitch):
        raise _error("legacy rollback switch is invalid", code="WFREL_RECOVERY_FAILED")
    try:
        for item, parent in zip(
            switch.archives, switch.target_parent_identities, strict=True
        ):
            if item.target_path.exists() or item.target_path.is_symlink():
                if _directory(item.target_path.parent) != parent or _hash_file(
                    item.target_path
                ) != FileIdentity(item.size, item.sha256):
                    raise OSError("installed archive changed")
            else:
                _link_archive(item, parent)
    except (OSError, ReleaseError):
        raise _error(
            "legacy rollback recovery could not restore exact archives",
            code="WFREL_RECOVERY_FAILED",
        ) from None


__all__ = ["prepare_legacy_removal", "remove_legacy_archives", "restore_removed_archives"]

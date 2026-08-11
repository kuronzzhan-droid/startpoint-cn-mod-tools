"""Private exact Mode candidate materialization and re-verification."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path, PurePosixPath
import tempfile

from .canonical import FileIdentity, normalize_relative_path
from .errors import ReleaseError
from .receipts import _sync_directory
from .schema import ReleaseManifest
from .verifier_zip import ROOT, open_release, parse_classic_store


@dataclass(frozen=True)
class ModeCandidate:
    release_id: str
    root: Path = field(repr=False)
    identities: tuple[FileIdentity, ...]
    relative_paths: tuple[str, ...]


def _invalid(message: str) -> ReleaseError:
    return ReleaseError("WFREL_CANDIDATE_INVALID", message, {"label": "candidate"})


def _release_directory(release_id: str) -> str:
    from .materialize import _release_directory as release_directory

    return release_directory(release_id)


def _expected(release: ReleaseManifest) -> tuple[tuple[str, ...], tuple[FileIdentity, ...]]:
    files = tuple(item for item in release.files if item.path.startswith("modes/"))
    paths = tuple(item.path.removeprefix("modes/") for item in files)
    identities = tuple(FileIdentity(item.size, item.sha256) for item in files)
    if not paths:
        raise _invalid("Mode candidate has no declared files")
    return paths, identities


def verify_mode_candidate(candidate: ModeCandidate) -> None:
    from .materialize import (
        _directory_identity,
        _hash_stable,
        _scan_candidate,
        _same_directory,
    )

    if not isinstance(candidate, ModeCandidate):
        raise _invalid("Mode candidate reference is invalid")
    if candidate.root.name != _release_directory(candidate.release_id):
        raise _invalid("Mode candidate root does not match the release identity")
    if len(candidate.relative_paths) != len(candidate.identities):
        raise _invalid("Mode candidate identity set is invalid")
    for relative in candidate.relative_paths:
        normalize_relative_path(relative)
    if candidate.relative_paths != tuple(sorted(
        set(candidate.relative_paths), key=lambda item: item.encode("utf-8")
    )):
        raise _invalid("Mode candidate paths are not canonical")
    before = _directory_identity(candidate.root, candidate=True)
    actual_files, actual_directories = _scan_candidate(candidate.root)
    expected_directories = tuple(sorted({
        PurePosixPath(*PurePosixPath(relative).parts[:depth]).as_posix()
        for relative in candidate.relative_paths
        for depth in range(1, len(PurePosixPath(relative).parts))
    }, key=lambda item: item.encode("utf-8")))
    if actual_files != candidate.relative_paths or actual_directories != expected_directories:
        raise _invalid("Mode candidate member set changed")
    actual = tuple(
        _hash_stable(candidate.root / Path(relative), candidate=True)
        for relative in candidate.relative_paths
    )
    if actual != candidate.identities:
        raise _invalid("Mode candidate file identities changed")
    _same_directory(candidate.root, before, candidate=True)


def _sync_tree(root: Path) -> None:
    directories = sorted(
        (item for item in root.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    )
    for directory in directories:
        _sync_directory(directory)
    _sync_directory(root)


def materialize_mode_candidate(
    archive: Path,
    release: ReleaseManifest,
    release_id: str,
    component_root: Path,
    operation_id: str,
) -> ModeCandidate:
    from .materialize import (
        _directory_identity,
        _same_directory,
        _write_member,
    )

    expected_paths, expected_identities = _expected(release)
    root_identity = _directory_identity(component_root, candidate=True)
    release_name = _release_directory(release_id)
    final_root = component_root / release_name
    existing = ModeCandidate(release_id, final_root, expected_identities, expected_paths)
    if final_root.exists() or final_root.is_symlink():
        verify_mode_candidate(existing)
        return existing
    tag = hashlib.sha256(operation_id.encode("ascii")).hexdigest()[:12]
    with tempfile.TemporaryDirectory(prefix=f".modes-{tag}-", dir=component_root) as temporary:
        staging = Path(temporary) / release_name
        staging.mkdir()
        with open_release(archive) as (stream, archive_size):
            members = {item.name: item for item in parse_classic_store(stream, archive_size)}
            for relative, expected in zip(expected_paths, expected_identities, strict=True):
                destination = staging / Path(relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                member = members.get(f"{ROOT}modes/{relative}")
                if member is None:
                    raise ReleaseError(
                        "WFREL_OBJECT_CORRUPT",
                        "stored Mode payload is missing",
                        {"label": "object"},
                    )
                _write_member(stream, member, destination, expected)
        _sync_tree(staging)
        staged = ModeCandidate(release_id, staging, expected_identities, expected_paths)
        verify_mode_candidate(staged)
        _same_directory(component_root, root_identity, candidate=True)
        try:
            os.rename(staging, final_root)
        except FileExistsError:
            verify_mode_candidate(existing)
            return existing
        except OSError:
            raise ReleaseError(
                "WFREL_CANDIDATE_IO",
                "Mode candidate could not be committed",
            ) from None
        _sync_directory(component_root)
        verify_mode_candidate(existing)
        return existing


__all__ = ["ModeCandidate", "materialize_mode_candidate", "verify_mode_candidate"]

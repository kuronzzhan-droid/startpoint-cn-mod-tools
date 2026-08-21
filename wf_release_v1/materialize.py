"""Immutable Release objects and private, re-verifiable component candidates."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import tempfile
from typing import Final

from ._receipt_contract import _OPERATION_ID
from ._path_io import native_path
from .canonical import FileIdentity, normalize_relative_path, stream_copy_and_hash_stable_file
from .compatibility import VerifiedRelease
from .errors import ReleaseError
from .receipts import _sync_directory
from .target import ManagedTarget
from .mode_candidates import (
    ModeCandidate,
    materialize_mode_candidate,
    verify_mode_candidate,
)
from .overlay_candidates import (
    content_candidate_contract,
    materialize_verified_overlay,
)
from .verifier import _exact_set, _metadata, verify_release
from .verifier_zip import ROOT, copy_hash_member, open_release, parse_classic_store


_ARCHIVE_NAME: Final = "release.wf-release.zip"
_RELEASE_ID: Final = re.compile(r"sha256:[0-9a-f]{64}")
_REPARSE_POINT: Final = 0x0400
_WINDOWS_FORBIDDEN: Final = frozenset('<>:"\\|?*')
_WINDOWS_DEVICES: Final = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


@dataclass(frozen=True)
class StoredObject:
    release_id: str
    archive: Path = field(repr=False)
    identity: FileIdentity


@dataclass(frozen=True)
class CandidateSet:
    release_id: str
    content_root: Path | None
    server_root: Path | None
    modes_root: Path | None
    identities: tuple[FileIdentity, ...]
    # FileIdentity intentionally stays host-path-free.  This aligned path tuple
    # is necessary for verify_candidates() to detect rename/extra-file attacks.
    relative_paths: tuple[str, ...]
    mode_candidate: ModeCandidate | None = None


def _error(code: str, message: str, **details: object) -> ReleaseError:
    return ReleaseError(code, message, details)


def _candidate_invalid(message: str) -> ReleaseError:
    return _error("WFREL_CANDIDATE_INVALID", message, label="candidate")


def _is_reparse(item: os.stat_result) -> bool:
    return stat.S_ISLNK(item.st_mode) or bool(
        (getattr(item, "st_file_attributes", 0) or 0) & _REPARSE_POINT
    )


def _directory_identity(path: Path, *, candidate: bool = False) -> tuple[int, int]:
    try:
        item = os.lstat(native_path(path))
    except OSError:
        error = _candidate_invalid if candidate else lambda message: _error(
            "WFREL_OBJECT_CORRUPT", message, label="object"
        )
        raise error("managed root is unavailable") from None
    if not stat.S_ISDIR(item.st_mode) or _is_reparse(item):
        error = _candidate_invalid if candidate else lambda message: _error(
            "WFREL_OBJECT_CORRUPT", message, label="object"
        )
        raise error("managed root must be a non-reparse directory")
    return item.st_dev, item.st_ino


def _same_directory(path: Path, expected: tuple[int, int], *, candidate: bool = False) -> None:
    if _directory_identity(path, candidate=candidate) != expected:
        if candidate:
            raise _candidate_invalid("managed component root changed during materialization")
        raise _error("WFREL_OBJECT_CORRUPT", "managed state root changed", label="object")


def _ensure_directory(parent: Path, expected: tuple[int, int], name: str, *, candidate: bool) -> Path:
    child = parent / name
    try:
        os.mkdir(native_path(child))
    except FileExistsError:
        pass
    except OSError:
        code = "WFREL_CANDIDATE_IO" if candidate else "WFREL_OBJECT_IO"
        raise _error(code, "managed directory could not be created") from None
    _same_directory(parent, expected, candidate=candidate)
    _directory_identity(child, candidate=candidate)
    return child


def _release_directory(release_id: str) -> str:
    if not isinstance(release_id, str) or _RELEASE_ID.fullmatch(release_id) is None:
        raise _error("WFREL_OBJECT_CORRUPT", "release identity is invalid", label="object")
    return release_id.replace(":", "-", 1)


def _hash_stable(path: Path, *, candidate: bool) -> FileIdentity:
    error = _candidate_invalid if candidate else lambda message: _error(
        "WFREL_OBJECT_CORRUPT", message, label="object"
    )
    try:
        before_stat = os.lstat(native_path(path))
        if not stat.S_ISREG(before_stat.st_mode) or _is_reparse(before_stat):
            raise error("managed file must be a non-reparse regular file")
        before = (
            before_stat.st_dev, before_stat.st_ino, before_stat.st_size, before_stat.st_mtime_ns
        )
        digest = hashlib.sha256()
        descriptor = os.open(
            native_path(path), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        with os.fdopen(descriptor, "rb") as reader:
            opened = os.fstat(reader.fileno())
            if (
                opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns
            ) != before or _is_reparse(opened) or not stat.S_ISREG(opened.st_mode):
                raise error("managed file changed before open")
            while chunk := reader.read(1024 * 1024):
                digest.update(chunk)
            opened_after = os.fstat(reader.fileno())
        after = os.lstat(native_path(path))
        if (
            opened_after.st_dev, opened_after.st_ino, opened_after.st_size, opened_after.st_mtime_ns
        ) != before or (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ) != before or _is_reparse(after):
            raise error("managed file changed while being read")
        return FileIdentity(size=before[2], sha256=digest.hexdigest())
    except ReleaseError:
        raise
    except OSError:
        raise error("managed file is unavailable") from None


def _object_at(path: Path, release_id: str, expected: FileIdentity | None = None) -> StoredObject:
    root = path.parent
    _directory_identity(root)
    try:
        names = tuple(item.name for item in root.iterdir())
    except OSError:
        raise _error("WFREL_OBJECT_CORRUPT", "object directory is unreadable", label="object") from None
    if names != (_ARCHIVE_NAME,):
        raise _error("WFREL_OBJECT_CORRUPT", "object member set is invalid", label="object")
    identity = _hash_stable(path, candidate=False)
    if expected is not None and identity != expected:
        raise _error("WFREL_OBJECT_CORRUPT", "stored object bytes disagree", label="object")
    try:
        report = verify_release(path)
    except ReleaseError as error:
        raise _error("WFREL_OBJECT_CORRUPT", "stored object is not a valid Release", label="object") from error
    if report.release_id != release_id:
        raise _error("WFREL_OBJECT_CORRUPT", "stored object identity disagrees", label="object")
    return StoredObject(release_id=release_id, archive=path, identity=identity)


def _translate_verifier(error: ReleaseError) -> ReleaseError:
    if error.code == "WFREL_COMPONENT_UNSUPPORTED":
        return _error(
            "WFREL_INSTALL_UNSUPPORTED_COMPONENT",
            "Release component has no installed receiver schema",
            label="components",
        )
    return error


def import_verified_object(release: Path, target: ManagedTarget) -> StoredObject:
    """Copy, verify and atomically retain one immutable Release object."""
    if not isinstance(target, ManagedTarget):
        raise _error("WFREL_OBJECT_CORRUPT", "managed target is invalid", label="object")
    state_identity = _directory_identity(target.state_root)
    objects = _ensure_directory(target.state_root, state_identity, "objects", candidate=False)
    objects_identity = _directory_identity(objects)
    with tempfile.TemporaryDirectory(prefix=".import-", dir=objects) as temporary:
        temporary_root = Path(temporary)
        archive = temporary_root / _ARCHIVE_NAME
        copied = stream_copy_and_hash_stable_file(Path(release), archive)
        try:
            report = verify_release(archive)
        except ReleaseError as error:
            raise _translate_verifier(error) from error
        destination_root = objects / _release_directory(report.release_id)
        destination = destination_root / _ARCHIVE_NAME
        if destination_root.exists():
            return _object_at(destination, report.release_id, copied)
        _same_directory(objects, objects_identity)
        try:
            os.rename(temporary_root, destination_root)
        except FileExistsError:
            return _object_at(destination, report.release_id, copied)
        except OSError:
            raise _error("WFREL_OBJECT_IO", "verified object could not be committed") from None
        _sync_directory(objects)
        return _object_at(destination, report.release_id, copied)


def load_verified_release(obj: StoredObject, target: ManagedTarget) -> VerifiedRelease:
    """Re-verify one retained object and return its detached contract facts."""
    if not isinstance(obj, StoredObject) or not isinstance(target, ManagedTarget):
        raise _error("WFREL_OBJECT_CORRUPT", "stored object reference is invalid", label="object")
    expected_archive = (
        target.state_root / "objects" / _release_directory(obj.release_id) / _ARCHIVE_NAME
    )
    if obj.archive != expected_archive or _hash_stable(obj.archive, candidate=False) != obj.identity:
        raise _error("WFREL_OBJECT_CORRUPT", "stored object reference is invalid", label="object")
    try:
        report = verify_release(obj.archive)
    except ReleaseError as error:
        raise _translate_verifier(error) from error
    if report.release_id != obj.release_id:
        raise _error("WFREL_OBJECT_CORRUPT", "stored object facts disagree", label="object")
    with open_release(obj.archive) as (stream, archive_size):
        members = parse_classic_store(stream, archive_size)
        by_name = {item.name: item for item in members}
        release, requirements, ownership, _raw = _metadata(stream, by_name)
        _exact_set(release, by_name)
    if release.release_id != obj.release_id:
        raise _error("WFREL_OBJECT_CORRUPT", "stored manifest identity disagrees", label="object")
    if report.components != tuple(component.kind for component in release.components):
        raise _error("WFREL_OBJECT_CORRUPT", "stored component facts disagree", label="object")
    return VerifiedRelease(release, requirements, ownership)


def _read_object_manifest(obj: StoredObject, target: ManagedTarget):
    return load_verified_release(obj, target).manifest


def _portable_candidate_part(value: str) -> None:
    if (
        not value
        or value.endswith((" ", "."))
        or value.split(".", 1)[0].upper() in _WINDOWS_DEVICES
        or any(character in _WINDOWS_FORBIDDEN for character in value)
    ):
        raise _candidate_invalid("candidate member path is not portable")


def _scan_candidate(root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    found: list[str] = []
    directories: list[str] = []

    def visit(directory: Path, prefix: tuple[str, ...]) -> None:
        try:
            entries = tuple(os.scandir(native_path(directory)))
        except OSError:
            raise _candidate_invalid("candidate directory is unreadable") from None
        for entry in entries:
            _portable_candidate_part(entry.name)
            relative = prefix + (entry.name,)
            try:
                item = entry.stat(follow_symlinks=False)
            except OSError:
                raise _candidate_invalid("candidate member is unavailable") from None
            if _is_reparse(item):
                raise _candidate_invalid("candidate contains a reparse point")
            path = Path(entry.path)
            if stat.S_ISDIR(item.st_mode):
                directories.append(PurePosixPath(*relative).as_posix())
                visit(path, relative)
            elif stat.S_ISREG(item.st_mode):
                found.append(PurePosixPath(*relative).as_posix())
            else:
                raise _candidate_invalid("candidate contains a special file")

    visit(root, ())
    return (
        tuple(sorted(found, key=lambda item: item.encode("utf-8"))),
        tuple(sorted(directories, key=lambda item: item.encode("utf-8"))),
    )


def _verify_content_candidate(candidates: CandidateSet) -> None:
    """Re-read every exact candidate path and revalidate the Overlay chain."""
    if not isinstance(candidates, CandidateSet) or candidates.server_root is not None:
        raise _candidate_invalid("candidate component set is unsupported")
    _release_directory(candidates.release_id)
    root = candidates.content_root
    if root is None or len(candidates.relative_paths) != len(candidates.identities):
        raise _candidate_invalid("candidate identity set is invalid")
    if root.name != _release_directory(candidates.release_id):
        raise _candidate_invalid("candidate root does not match the release identity")
    before = _directory_identity(root, candidate=True)
    for relative in candidates.relative_paths:
        normalize_relative_path(relative)
    if candidates.relative_paths != tuple(sorted(set(candidates.relative_paths), key=lambda item: item.encode("utf-8"))):
        raise _candidate_invalid("candidate paths are not canonical")
    actual_files, actual_directories = _scan_candidate(root)
    expected_directories = tuple(sorted({
        PurePosixPath(*PurePosixPath(relative).parts[:depth]).as_posix()
        for relative in candidates.relative_paths
        for depth in range(1, len(PurePosixPath(relative).parts))
    }, key=lambda item: item.encode("utf-8")))
    if actual_files != candidates.relative_paths or actual_directories != expected_directories:
        raise _candidate_invalid("candidate member set changed")
    paths = tuple(root / Path(relative) for relative in candidates.relative_paths)
    workers = min(4, os.cpu_count() or 1, len(paths))
    if workers >= 4:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            actual = tuple(executor.map(lambda path: _hash_stable(path, candidate=True), paths))
    else:
        actual = tuple(_hash_stable(path, candidate=True) for path in paths)
    if actual != candidates.identities:
        raise _candidate_invalid("candidate file identities changed")
    parts = tuple(PurePosixPath(item).parts for item in candidates.relative_paths)
    if not parts or any(len(item) < 3 or item[0] != "patches" for item in parts):
        raise _candidate_invalid("content candidate layout is invalid")
    targets = {item[1] for item in parts}
    if len(targets) != 1:
        raise _candidate_invalid("content candidate Overlay target disagrees")
    metadata = {"README.md", "requires.json", "patch-manifest.json"}
    outer_indexes = tuple(
        index for index, item in enumerate(parts)
        if len(item) == 3 and item[2] not in metadata
    )
    if len(outer_indexes) != 1:
        raise _candidate_invalid("content candidate must retain one verified Overlay")
    outer_index = outer_indexes[0]
    outer_relative = candidates.relative_paths[outer_index]
    expected_paths, expected_identities = content_candidate_contract(
        root, outer_relative, candidates.identities[outer_index]
    )
    if (
        candidates.relative_paths != expected_paths
        or candidates.identities != expected_identities
    ):
        raise _candidate_invalid("content candidate receiver contract disagrees")
    _same_directory(root, before, candidate=True)


def verify_candidates(candidates: CandidateSet) -> None:
    """Re-read every exact candidate path and component-specific contract."""
    _verify_content_candidate(candidates)
    if (candidates.modes_root is None) != (candidates.mode_candidate is None):
        raise _candidate_invalid("Mode candidate reference is inconsistent")
    if candidates.mode_candidate is not None:
        if candidates.mode_candidate.root != candidates.modes_root:
            raise _candidate_invalid("Mode candidate root is inconsistent")
        verify_mode_candidate(candidates.mode_candidate)


def _write_member(stream, member, destination: Path, expected: FileIdentity) -> FileIdentity:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(native_path(destination), flags, 0o600)
        with os.fdopen(descriptor, "wb", buffering=0) as writer:
            digest = copy_hash_member(stream, member, writer)
            writer.flush()
            os.fsync(writer.fileno())
    except ReleaseError:
        raise
    except OSError:
        raise _error("WFREL_CANDIDATE_IO", "candidate member could not be written") from None
    actual = FileIdentity(member.size, digest)
    if actual != expected or _hash_stable(destination, candidate=True) != expected:
        raise _candidate_invalid("candidate member identity disagrees")
    return actual


def _materialize_content_candidate(
    obj: StoredObject,
    target: ManagedTarget,
    operation_id: str,
    release,
) -> CandidateSet:
    """Materialize the content member of one already-validated Release."""
    component_root = target.component_roots.content
    root_identity = _directory_identity(component_root, candidate=True)
    _same_directory(component_root, root_identity, candidate=True)
    release_name = _release_directory(obj.release_id)
    final_root = component_root / release_name
    content_files = tuple(item for item in release.files if item.path.startswith("content/"))
    if len(content_files) != 1:
        raise _error(
            "WFREL_INSTALL_UNSUPPORTED_COMPONENT",
            "multi-edge content receiver switching is unavailable",
            label="components",
        )
    content_file = content_files[0]
    target_version = release.expected_state.cdn_target_version
    outer_name = PurePosixPath(content_file.path).name
    _portable_candidate_part(outer_name)
    outer_relative = f"patches/{target_version}/{outer_name}"
    outer_identity = FileIdentity(content_file.size, content_file.sha256)

    def candidate_at(candidate_root: Path) -> CandidateSet:
        relative_paths, identities = content_candidate_contract(
            candidate_root, outer_relative, outer_identity
        )
        return CandidateSet(
            obj.release_id,
            candidate_root,
            None,
            None,
            identities,
            relative_paths,
        )

    if final_root.exists():
        existing = candidate_at(final_root)
        verify_candidates(existing)
        return existing

    operation_tag = hashlib.sha256(operation_id.encode("ascii")).hexdigest()[:12]
    prefix = f".materialize-{operation_tag}-"
    with tempfile.TemporaryDirectory(prefix=prefix, dir=component_root) as temporary:
        staging = Path(temporary) / release_name
        os.mkdir(native_path(staging))
        patches = staging / "patches"
        target_root = patches / release.expected_state.cdn_target_version
        os.mkdir(native_path(patches))
        os.mkdir(native_path(target_root))
        with open_release(obj.archive) as (stream, archive_size):
            by_name = {
                item.name: item for item in parse_classic_store(stream, archive_size)
            }
            member = by_name.get(f"{ROOT}{content_file.path}")
            if member is None:
                raise _error("WFREL_OBJECT_CORRUPT", "stored payload is missing", label="object")
            _write_member(stream, member, staging / Path(outer_relative), outer_identity)
        materialize_verified_overlay(staging / Path(outer_relative), target_root)
        _sync_directory(Path(native_path(target_root)))
        _sync_directory(Path(native_path(patches)))
        _sync_directory(Path(native_path(staging)))
        staged = candidate_at(staging)
        verify_candidates(staged)
        _same_directory(component_root, root_identity, candidate=True)
        try:
            os.rename(native_path(staging), native_path(final_root))
        except FileExistsError:
            existing = candidate_at(final_root)
            verify_candidates(existing)
            return existing
        except OSError:
            raise _error("WFREL_CANDIDATE_IO", "candidate could not be committed") from None
        _sync_directory(Path(native_path(component_root)))
        existing = candidate_at(final_root)
        verify_candidates(existing)
        return existing


def materialize_candidates(
    obj: StoredObject,
    target: ManagedTarget,
    operation_id: str,
) -> CandidateSet:
    """Materialize exact content and optional Mode candidates."""
    if not isinstance(operation_id, str) or _OPERATION_ID.fullmatch(operation_id) is None:
        raise _candidate_invalid("operation identity is invalid")
    if not isinstance(obj, StoredObject) or not isinstance(target, ManagedTarget):
        raise _candidate_invalid("materialization input is invalid")
    release = _read_object_manifest(obj, target)
    kinds = tuple(component.kind for component in release.components)
    if kinds not in (("content",), ("content", "modes")):
        raise _error(
            "WFREL_INSTALL_UNSUPPORTED_COMPONENT",
            "Release component has no installed receiver schema",
            label="components",
        )
    candidates = _materialize_content_candidate(obj, target, operation_id, release)
    if kinds == ("content",):
        return candidates
    mode = materialize_mode_candidate(
        obj.archive,
        release,
        obj.release_id,
        target.component_roots.modes,
        operation_id,
    )
    combined = replace(candidates, modes_root=mode.root, mode_candidate=mode)
    verify_candidates(combined)
    return combined

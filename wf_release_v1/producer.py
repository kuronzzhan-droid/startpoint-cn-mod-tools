"""Deterministic content-only wf-release-v1 archive producer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from typing import Final

from .canonical import FileIdentity, canonical_json_bytes
from .character_source import CharacterReleaseSource, SourceFile, inspect_character_source
from .errors import ReleaseError
from .ownership import project_character_ownership
from .release_archive import (
    ParentState,
    capture_parent,
    force_utf8_flags,
    publish_new,
    reopen_for_readback,
    verify_parent,
    write_archive,
)
from .schema import (
    ExpectedState,
    MetadataSha256,
    ProducerIdentity,
    ReleaseComponent,
    ReleaseFile,
    ReleaseManifest,
    ReleaseRequirements,
    SourceEvidence,
    compute_release_id,
    parse_ownership,
    parse_release_manifest,
    parse_requirements,
    verify_release_id,
)


_ROOT: Final = "wf-release-v1"
_REPARSE_POINT: Final = 0x0400
_WINDOWS_DEVICES: Final = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


@dataclass(frozen=True)
class BuildRequest:
    name: str
    version: str
    workspace: Path
    overlay_archives: tuple[Path, ...]
    output: Path
    requirements: ReleaseRequirements
    replaces: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuildReceipt:
    output: Path
    release_id: str
    archive_sha256: str
    file_count: int
    bytes_read: int
    hash_count: int


def _error(code: str, message: str, **details: object) -> ReleaseError:
    return ReleaseError(code, message, details)


def _snapshot(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def _is_reparse(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_within(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath((os.fspath(path), os.fspath(parent))) == os.fspath(parent)
    except ValueError:
        return False


def _validate_output(request: BuildRequest) -> tuple[Path, ParentState]:
    output = _absolute(Path(request.output))
    workspace = _absolute(Path(request.workspace))
    if output == workspace or _is_within(output, workspace):
        raise _error(
            "WFREL_BUILD_OUTPUT_INVALID",
            "output cannot overlap the sealed workspace",
            label="output",
        )
    try:
        os.lstat(output)
    except FileNotFoundError:
        pass
    except OSError as error:
        raise _error(
            "WFREL_BUILD_OUTPUT_INVALID",
            "output path cannot be inspected",
            label="output",
        ) from error
    else:
        raise _error(
            "WFREL_BUILD_OUTPUT_EXISTS",
            "output already exists",
            label="output",
        )
    return output, capture_parent(output.parent)


def _portable_member(path: str) -> str:
    if not path.isascii() or "\\" in path or path.startswith("/"):
        raise _error(
            "WFREL_BUILD_PATH_INVALID",
            "release member path is not portable ASCII",
            label="member",
        )
    parts = PurePosixPath(path).parts
    if not parts or any(
        not part
        or part in {".", ".."}
        or part.endswith((" ", "."))
        or part.split(".", 1)[0].upper() in _WINDOWS_DEVICES
        for part in parts
    ):
        raise _error(
            "WFREL_BUILD_PATH_INVALID",
            "release member path is not portable",
            label="member",
        )
    return path


def _manifest_paths(manifest: Mapping[str, object], roots: Sequence[str]) -> tuple[str, ...]:
    raw_roots = manifest.get("roots")
    if not isinstance(raw_roots, Mapping):
        return ()
    paths: list[str] = []
    for root in roots:
        entries = raw_roots.get(root)
        if not isinstance(entries, list):
            return ()
        for entry in entries:
            if not isinstance(entry, Mapping) or not isinstance(entry.get("logical_path"), str):
                return ()
            paths.append(entry["logical_path"])
    return tuple(paths)


def _stable_source_identity(source: SourceFile) -> None:
    try:
        metadata = os.lstat(source.path)
    except OSError as error:
        raise _error(
            "WFREL_BUILD_SOURCE_CHANGED",
            "an inspected source is unavailable",
            label="overlay",
        ) from error
    if (
        _snapshot(metadata) != source._identity
        or _is_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
    ):
        raise _error(
            "WFREL_BUILD_SOURCE_CHANGED",
            "an inspected source identity changed",
            label="overlay",
        )


def _copy_pinned_source(source: SourceFile, destination: Path) -> FileIdentity:
    """Copy/hash from one descriptor bound to the Task 4 inspection identity."""
    source_descriptor = destination_descriptor = -1
    digest = hashlib.sha256()
    bytes_read = 0
    try:
        before = os.lstat(source.path)
        if (
            _snapshot(before) != source._identity
            or _is_reparse(before)
            or not stat.S_ISREG(before.st_mode)
        ):
            raise OSError("source changed before open")
        source_descriptor = os.open(
            source.path,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(source_descriptor)
        if _snapshot(opened) != source._identity or not stat.S_ISREG(opened.st_mode):
            raise OSError("opened source is not the inspected file")
        destination_descriptor = os.open(
            destination,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(source_descriptor, "rb", closefd=True) as reader:
            source_descriptor = -1
            with os.fdopen(destination_descriptor, "wb", closefd=True) as writer:
                destination_descriptor = -1
                while chunk := reader.read(1024 * 1024):
                    digest.update(chunk)
                    writer.write(chunk)
                    bytes_read += len(chunk)
            opened_after = os.fstat(reader.fileno())
        after = os.lstat(source.path)
        if _snapshot(opened_after) != source._identity or _snapshot(after) != source._identity:
            raise OSError("source changed during copy")
    except OSError as error:
        raise _error(
            "WFREL_BUILD_SOURCE_CHANGED",
            "an inspected source changed while being copied",
            label="overlay",
        ) from error
    finally:
        if source_descriptor >= 0:
            os.close(source_descriptor)
        if destination_descriptor >= 0:
            os.close(destination_descriptor)
    return FileIdentity(bytes_read, digest.hexdigest())


def _write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except OSError as error:
        raise _error(
            "WFREL_BUILD_IO",
            "private staging metadata could not be written",
            label=path.name,
        ) from error


def _copy_payloads(source: CharacterReleaseSource, staging_root: Path) -> tuple[tuple[ReleaseFile, ...], int]:
    files: list[ReleaseFile] = []
    bytes_read = 0
    seen: set[str] = set()
    for item in source.overlay_files:
        member = _portable_member(f"content/{item.relative_path}")
        folded = member.casefold()
        if folded in seen:
            raise _error(
                "WFREL_BUILD_PATH_INVALID",
                "release member paths conflict portably",
                label="member",
            )
        seen.add(folded)
        _stable_source_identity(item)
        destination = staging_root / member
        destination.parent.mkdir(parents=True, exist_ok=True)
        identity = _copy_pinned_source(item, destination)
        _stable_source_identity(item)
        if identity.size != item.size:
            raise _error(
                "WFREL_BUILD_SOURCE_CHANGED",
                "an inspected source size changed",
                label="overlay",
            )
        files.append(ReleaseFile(member, identity.size, identity.sha256))
        bytes_read += identity.size
    return tuple(sorted(files, key=lambda value: value.path.encode("utf-8"))), bytes_read


def _build_metadata(
    request: BuildRequest,
    source: CharacterReleaseSource,
    files: tuple[ReleaseFile, ...],
    staging_root: Path,
) -> ReleaseManifest:
    requirements = parse_requirements(request.requirements.to_wire())
    manifest = source.package_manifest
    ownership = project_character_ownership(
        workspace_manifest=manifest,
        declared_server_paths=_manifest_paths(manifest, ("server",)),
        declared_overlay_paths=_manifest_paths(manifest, ("common", "medium", "android")),
    )
    ownership = parse_ownership(ownership.to_wire())
    requires_raw = canonical_json_bytes(requirements.to_wire())
    ownership_raw = canonical_json_bytes(ownership.to_wire())
    _write_new(staging_root / "requires.json", requires_raw)
    _write_new(staging_root / "ownership.json", ownership_raw)

    body = ReleaseManifest(
        schema_version=1,
        name=request.name,
        version=request.version,
        producer=ProducerIdentity("wf-mod-tools", "1"),
        replaces=request.replaces,
        source_evidence=SourceEvidence(
            "character-workspace-v1", source.workspace_input_sha256
        ),
        components=(ReleaseComponent("content", "content"),),
        expected_state=ExpectedState(source.cdn_target_version, None, None),
        metadata_sha256=MetadataSha256(
            hashlib.sha256(requires_raw).hexdigest(),
            hashlib.sha256(ownership_raw).hexdigest(),
        ),
        files=files,
        release_id="sha256:" + "0" * 64,
    )
    wire = body.to_wire()
    del wire["releaseId"]
    release_id = compute_release_id(wire)
    release = parse_release_manifest({**wire, "releaseId": release_id})
    verify_release_id(release)
    _write_new(staging_root / "release-manifest.json", canonical_json_bytes(release.to_wire()))
    return release


def _stage_members(staging_root: Path) -> tuple[tuple[str, Path], ...]:
    members = tuple(
        sorted(
            (
                (_portable_member(f"{_ROOT}/{path.relative_to(staging_root).as_posix()}"), path)
                for path in staging_root.rglob("*")
                if path.is_file()
            ),
            key=lambda item: item[0].encode("utf-8"),
        )
    )
    names = [name for name, _ in members]
    if len(names) != len(set(name.casefold() for name in names)):
        raise _error(
            "WFREL_BUILD_PATH_INVALID",
            "release member paths conflict portably",
            label="member",
        )
    return members


def _cleanup_stage(path: Path, identity: tuple[int, int] | None) -> None:
    if identity is None:
        return
    try:
        metadata = os.lstat(path)
        if (
            (metadata.st_dev, metadata.st_ino) == identity
            and stat.S_ISDIR(metadata.st_mode)
            and not _is_reparse(metadata)
        ):
            shutil.rmtree(path)
    except OSError:
        pass


def build_character_release(request: BuildRequest) -> BuildReceipt:
    """Build one immutable content-only release without touching live state."""
    if type(request) is not BuildRequest or type(request.requirements) is not ReleaseRequirements:
        raise _error("WFREL_BUILD_REQUEST_INVALID", "build request is invalid", label="request")
    output, parent = _validate_output(request)
    source = inspect_character_source(
        workspace=Path(request.workspace),
        overlay_archives=request.overlay_archives,
    )
    verify_parent(parent)
    stage = Path(tempfile.mkdtemp(prefix=".wfrel-stage-", dir=output.parent))
    stage_stat = os.lstat(stage)
    stage_identity: tuple[int, int] | None = (stage_stat.st_dev, stage_stat.st_ino)
    archive: tempfile._TemporaryFileWrapper[bytes] | None = None
    try:
        staging_root = stage / _ROOT
        staging_root.mkdir()
        files, bytes_read = _copy_payloads(source, staging_root)
        release = _build_metadata(request, source, files, staging_root)
        members = _stage_members(staging_root)
        verify_parent(parent)
        archive = tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=".wfrel-archive-",
            suffix=".zip",
            dir=output.parent,
            delete=True,
        )
        archive_path = Path(archive.name)
        write_archive(archive, members)
        force_utf8_flags(archive)
        archive.flush()
        readback = reopen_for_readback(archive_path, output.parent)
        if readback.release_id != release.release_id:
            raise _error("WFREL_ARCHIVE_INVALID", "readback identity changed", label="archive")
        publish_new(archive_path, output, parent)
        return BuildReceipt(
            output=output,
            release_id=readback.release_id,
            archive_sha256=readback.archive_sha256,
            file_count=readback.file_count,
            bytes_read=bytes_read,
            hash_count=len(source.overlay_files),
        )
    except ReleaseError:
        raise
    except (OSError, ValueError, TypeError) as error:
        raise _error("WFREL_BUILD_IO", "release build failed", label="build") from error
    finally:
        if archive is not None:
            try:
                archive.close()
            except OSError:
                pass
        _cleanup_stage(stage, stage_identity)

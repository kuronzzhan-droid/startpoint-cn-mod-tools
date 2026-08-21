"""Deterministic content-only wf-release-v1 archive producer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import BinaryIO, Final
import unicodedata

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
    OwnershipManifest,
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
_MAX_METADATA_BYTES: Final = 1024 * 1024
_REPARSE_POINT: Final = 0x0400
_WINDOWS_FORBIDDEN: Final = frozenset('<>:"\\|?*')
_WINDOWS_DEVICES: Final = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
    | {f"COM{index}" for index in "¹²³"}
    | {f"LPT{index}" for index in "¹²³"}
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


@dataclass
class _StagedMember:
    path: str
    stream: BinaryIO
    size: int


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
        raise _error("WFREL_BUILD_OUTPUT_EXISTS", "output already exists", label="output")
    return output, capture_parent(output.parent)


def _portable_member(path: str) -> str:
    if unicodedata.normalize("NFC", path) != path or path.startswith("/"):
        raise _error(
            "WFREL_BUILD_PATH_INVALID",
            "release member path is not portable NFC",
            label="member",
        )
    try:
        path.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise _error(
            "WFREL_BUILD_PATH_INVALID",
            "release member path is not valid Unicode",
            label="member",
        ) from error
    parts = PurePosixPath(path).parts
    if not parts or any(
        not part
        or part in {".", ".."}
        or part.endswith((" ", "."))
        or part.split(".", 1)[0].upper() in _WINDOWS_DEVICES
        or any(ord(character) < 32 or ord(character) == 127 for character in part)
        or any(character in _WINDOWS_FORBIDDEN for character in part)
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


def _copy_pinned_source(source: SourceFile) -> tuple[FileIdentity, BinaryIO]:
    """Copy/hash from one descriptor bound to the Task 4 inspection identity."""
    source_descriptor = -1
    staging: BinaryIO | None = None
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
        staging = tempfile.TemporaryFile(mode="w+b")
        with os.fdopen(source_descriptor, "rb", closefd=True) as reader:
            source_descriptor = -1
            while chunk := reader.read(1024 * 1024):
                digest.update(chunk)
                staging.write(chunk)
                bytes_read += len(chunk)
            opened_after = os.fstat(reader.fileno())
        after = os.lstat(source.path)
        if _snapshot(opened_after) != source._identity or _snapshot(after) != source._identity:
            raise OSError("source changed during copy")
        staging.flush()
        staging.seek(0)
        return FileIdentity(bytes_read, digest.hexdigest()), staging
    except OSError as error:
        if staging is not None:
            staging.close()
        raise _error(
            "WFREL_BUILD_SOURCE_CHANGED",
            "an inspected source changed while being copied",
            label="overlay",
        ) from error
    finally:
        if source_descriptor >= 0:
            os.close(source_descriptor)


def _copy_payloads(
    source: CharacterReleaseSource,
    members: dict[str, _StagedMember],
) -> tuple[tuple[ReleaseFile, ...], int]:
    files: list[ReleaseFile] = []
    bytes_read = 0
    seen: set[str] = set()
    for item in source.overlay_files:
        member = _portable_member(f"content/{item.relative_path}")
        folded = unicodedata.normalize("NFC", member).casefold()
        if folded in seen:
            raise _error(
                "WFREL_BUILD_PATH_INVALID",
                "release member paths conflict portably",
                label="member",
            )
        seen.add(folded)
        _stable_source_identity(item)
        identity, stream = _copy_pinned_source(item)
        _stable_source_identity(item)
        if identity.size != item.size:
            stream.close()
            raise _error(
                "WFREL_BUILD_SOURCE_CHANGED",
                "an inspected source size changed",
                label="overlay",
            )
        members[member] = _StagedMember(member, stream, identity.size)
        files.append(ReleaseFile(member, identity.size, identity.sha256))
        bytes_read += identity.size
    return tuple(sorted(files, key=lambda value: value.path.encode("utf-8"))), bytes_read


def _memory_member(path: str, raw: bytes) -> _StagedMember:
    if len(raw) > _MAX_METADATA_BYTES:
        raise _error(
            "WFREL_BUILD_LIMIT",
            "release metadata exceeds the supported limit",
            label=path,
        )
    return _StagedMember(path, io.BytesIO(raw), len(raw))


def _build_metadata(
    request: BuildRequest,
    source: CharacterReleaseSource,
    files: tuple[ReleaseFile, ...],
    members: dict[str, _StagedMember],
) -> ReleaseManifest:
    requirements = parse_requirements(request.requirements.to_wire())
    manifest = source.package_manifest
    ownership = project_character_ownership(
        workspace_manifest=manifest,
        declared_server_paths=_manifest_paths(manifest, ("server",)),
        declared_overlay_paths=_manifest_paths(manifest, ("common", "medium", "android")),
    )
    if source.accepted_asset_replacements:
        asset_claims = tuple(
            f"asset:{item.root}/{item.logical_path}"
            for item in source.accepted_asset_replacements
        )
        ownership = OwnershipManifest(
            schema_version=ownership.schema_version,
            entities=ownership.entities,
            records=tuple(sorted(
                {*ownership.records, *asset_claims},
                key=lambda item: item.encode("utf-8"),
            )),
            paths=ownership.paths,
        )
    ownership = parse_ownership(ownership.to_wire())
    requires_raw = canonical_json_bytes(requirements.to_wire())
    ownership_raw = canonical_json_bytes(ownership.to_wire())
    members["requires.json"] = _memory_member("requires.json", requires_raw)
    members["ownership.json"] = _memory_member("ownership.json", ownership_raw)
    body = ReleaseManifest(
        schema_version=1,
        name=request.name,
        version=request.version,
        producer=ProducerIdentity("wf-mod-tools", "1"),
        replaces=request.replaces,
        source_evidence=SourceEvidence(
            (
                "character-workspace-v2"
                if source.accepted_asset_replacements
                else "character-workspace-v1"
            ),
            source.workspace_input_sha256,
            source.accepted_asset_replacements,
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
    release = parse_release_manifest({**wire, "releaseId": compute_release_id(wire)})
    verify_release_id(release)
    release_raw = canonical_json_bytes(release.to_wire())
    members["release-manifest.json"] = _memory_member(
        "release-manifest.json", release_raw
    )
    return release


def _ordered_members(members: Mapping[str, _StagedMember]) -> tuple[_StagedMember, ...]:
    names = tuple(members)
    if len(names) != len({unicodedata.normalize("NFC", name).casefold() for name in names}):
        raise _error(
            "WFREL_BUILD_PATH_INVALID",
            "release member paths conflict portably",
            label="member",
        )
    manifest = "release-manifest.json"
    if manifest not in members:
        raise _error("WFREL_ARCHIVE_INVALID", "release manifest is missing", label="archive")
    ordered = sorted(
        (name for name in names if name != manifest),
        key=lambda name: name.encode("utf-8"),
    )
    ordered.append(manifest)
    return tuple(members[name] for name in ordered)


def _archive_temp(parent: Path) -> tuple[BinaryIO, Path | None]:
    if os.name == "nt":
        stream = tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=".wfrel-archive-",
            suffix=".zip",
            dir=parent,
            delete=True,
        )
        return stream, Path(stream.name)
    anonymous = getattr(os, "O_TMPFILE", 0)
    if not anonymous:
        raise _error(
            "WFREL_BUILD_IO",
            "safe anonymous archive staging is unavailable",
            label="archive",
        )
    descriptor = -1
    try:
        # Do not add O_EXCL: with O_TMPFILE it would make the inode
        # intentionally unlinkable through linkat(AT_EMPTY_PATH).
        descriptor = os.open(
            parent,
            os.O_RDWR | anonymous | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        stream = os.fdopen(descriptor, "w+b", closefd=True)
        descriptor = -1
        return stream, None
    except OSError as error:
        raise _error(
            "WFREL_BUILD_IO",
            "safe anonymous archive staging is unavailable",
            label="archive",
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def build_character_release(request: BuildRequest) -> BuildReceipt:
    """Build one immutable content-only release without touching live state."""
    if type(request) is not BuildRequest or type(request.requirements) is not ReleaseRequirements:
        raise _error("WFREL_BUILD_REQUEST_INVALID", "build request is invalid", label="request")
    if request.requirements.patch_overlay_schema != 1:
        raise _error(
            "WFREL_REQUIRE_UNSUPPORTED",
            "patch Overlay schema is unsupported by this producer",
            field="patchOverlaySchema",
        )
    output, parent = _validate_output(request)
    source = inspect_character_source(
        workspace=Path(request.workspace),
        overlay_archives=request.overlay_archives,
    )
    verify_parent(parent)
    members: dict[str, _StagedMember] = {}
    archive: BinaryIO | None = None
    try:
        files, bytes_read = _copy_payloads(source, members)
        release = _build_metadata(request, source, files, members)
        ordered = _ordered_members(members)
        verify_parent(parent)
        archive, archive_path = _archive_temp(output.parent)
        write_archive(
            archive,
            tuple((f"{_ROOT}/{item.path}", item.stream, item.size) for item in ordered),
        )
        force_utf8_flags(archive)
        readback = reopen_for_readback(archive)
        if readback.release_id != release.release_id:
            raise _error("WFREL_ARCHIVE_INVALID", "readback identity changed", label="archive")
        receipt = BuildReceipt(
            output=output,
            release_id=readback.release_id,
            archive_sha256=readback.archive_sha256,
            file_count=readback.file_count,
            bytes_read=bytes_read,
            hash_count=len(source.overlay_files),
        )
        publish_new(archive, archive_path, output, parent, readback)
        return receipt
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
        for item in members.values():
            try:
                item.stream.close()
            except OSError:
                pass

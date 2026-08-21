"""Safe Patch Overlay expansion into the Content Sync receiver layout."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Final
import zipfile

from ._path_io import native_path
from ._owned_receiver import OwnedReceiver, OwnedReceiverError
from .canonical import FileIdentity, normalize_relative_path
from .errors import ReleaseError
from .receipts import _sync_directory
from .verifier_overlay import VerifiedOverlayEdge, inspect_overlay_chain


_METADATA: Final = frozenset({"README.md", "requires.json", "patch-manifest.json"})
_REPARSE_POINT: Final = 0x0400
_WINDOWS_FORBIDDEN: Final = frozenset('<>:"\\|?*')
_WINDOWS_DEVICES: Final = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


def _before_member_open(_destination: Path) -> None:
    """Test seam at the final filesystem boundary; production is intentionally empty."""


def _invalid(message: str) -> ReleaseError:
    return ReleaseError("WFREL_CANDIDATE_INVALID", message, {"label": "candidate"})


def _io_error(message: str) -> ReleaseError:
    return ReleaseError("WFREL_CANDIDATE_IO", message, {"label": "candidate"})


def _is_reparse(item: os.stat_result) -> bool:
    return stat.S_ISLNK(item.st_mode) or bool(
        (getattr(item, "st_file_attributes", 0) or 0) & _REPARSE_POINT
    )


def _directory_identity(path: Path) -> tuple[int, int]:
    try:
        item = os.lstat(native_path(path))
    except OSError:
        raise _invalid("Overlay receiver directory is unavailable") from None
    if not stat.S_ISDIR(item.st_mode) or _is_reparse(item):
        raise _invalid("Overlay receiver directory must be a non-reparse directory")
    return item.st_dev, item.st_ino


def _stable_identity(path: Path) -> FileIdentity:
    try:
        before = os.lstat(native_path(path))
        if not stat.S_ISREG(before.st_mode) or _is_reparse(before):
            raise OSError("unsafe file")
        snapshot = (
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
        )
        digest = hashlib.sha256()
        descriptor = os.open(
            native_path(path), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        with os.fdopen(descriptor, "rb") as reader:
            opened = os.fstat(reader.fileno())
            if (
                opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns
            ) != snapshot or _is_reparse(opened) or not stat.S_ISREG(opened.st_mode):
                raise OSError("opened identity changed")
            while chunk := reader.read(1024 * 1024):
                digest.update(chunk)
            opened_after = os.fstat(reader.fileno())
        after = os.lstat(native_path(path))
        if (
            opened_after.st_dev, opened_after.st_ino,
            opened_after.st_size, opened_after.st_mtime_ns,
        ) != snapshot or (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
        ) != snapshot or _is_reparse(after):
            raise OSError("file changed")
        return FileIdentity(snapshot[2], digest.hexdigest())
    except OSError:
        raise _invalid("materialized Overlay member changed or is unsafe") from None


def _file_snapshot(path: Path) -> tuple[int, int, int, int]:
    try:
        item = os.lstat(native_path(path))
    except OSError:
        raise _invalid("verified Overlay source is unavailable") from None
    if not stat.S_ISREG(item.st_mode) or _is_reparse(item):
        raise _invalid("verified Overlay source must be a non-reparse regular file")
    return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns


def _portable_part(value: str) -> None:
    if (
        not value
        or value.endswith((" ", "."))
        or value.split(".", 1)[0].upper() in _WINDOWS_DEVICES
        or any(character in _WINDOWS_FORBIDDEN for character in value)
    ):
        raise _invalid("Overlay member path is not portable")


def _safe_infos(
    bundle: zipfile.ZipFile,
    edge: VerifiedOverlayEdge,
    *,
    outer_name: str,
) -> dict[str, zipfile.ZipInfo]:
    expected = _METADATA | {archive.relative_path for archive in edge.archives}
    infos: dict[str, zipfile.ZipInfo] = {}
    folded = {outer_name.casefold()}
    for info in bundle.infolist():
        try:
            original = normalize_relative_path(info.orig_filename)
            name = normalize_relative_path(info.filename)
        except ReleaseError as error:
            raise _invalid("Overlay member path is unsafe to materialize") from error
        if original != name or name in infos:
            raise _invalid("Overlay member path is duplicated")
        for part in PurePosixPath(name).parts:
            _portable_part(part)
        folded_name = name.casefold()
        if folded_name in folded:
            raise _invalid("Overlay member path has a portable case collision")
        folded.add(folded_name)
        unix_mode = (info.external_attr >> 16) & 0xFFFF
        unix_kind = stat.S_IFMT(unix_mode)
        if (
            info.is_dir()
            or info.filename.endswith("/")
            or bool(info.external_attr & 0x10)
            or unix_kind not in (0, stat.S_IFREG)
        ):
            raise _invalid("Overlay member is not a regular file")
        infos[name] = info
    if set(infos) != expected:
        raise _invalid("Overlay member set does not match the verified receiver contract")
    return infos


def _single_edge(outer: Path) -> VerifiedOverlayEdge:
    chain = inspect_overlay_chain((Path(native_path(outer)),))
    if len(chain.edges) != 1:
        raise _invalid("Overlay package must contain exactly one version edge")
    return chain.edges[0]


def _verified_source(
    outer: Path,
) -> tuple[VerifiedOverlayEdge, tuple[int, int, int, int], FileIdentity]:
    snapshot = _file_snapshot(outer)
    identity = _stable_identity(outer)
    edge = _single_edge(outer)
    if _file_snapshot(outer) != snapshot or _stable_identity(outer) != identity:
        raise _invalid("verified Overlay source changed after semantic verification")
    return edge, snapshot, identity


def _source_unchanged(
    outer: Path,
    snapshot: tuple[int, int, int, int],
    identity: FileIdentity,
) -> None:
    if _file_snapshot(outer) != snapshot or _stable_identity(outer) != identity:
        raise _invalid("verified Overlay source changed while it was read")


def _copy_member(
    authority: OwnedReceiver,
    bundle: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    relative: str,
) -> FileIdentity:
    destination = authority.root_path / Path(relative)
    try:
        def write(writer) -> None:
            with bundle.open(info, "r") as reader:
                while chunk := reader.read(1024 * 1024):
                    if writer.write(chunk) != len(chunk):
                        raise OSError("short receiver write")

        identity = authority.create_file(
            relative, write, before_open=lambda: _before_member_open(destination)
        )
    except (OSError, OwnedReceiverError, RuntimeError, zipfile.BadZipFile):
        raise _io_error("Overlay member could not be materialized") from None
    if identity.size != info.file_size:
        raise _invalid("materialized Overlay member identity disagrees")
    return identity


def _ordered_member_names(edge: VerifiedOverlayEdge) -> tuple[str, ...]:
    archives = tuple(archive.relative_path for archive in edge.archives)
    return ("README.md", "requires.json", *archives, "patch-manifest.json")


def materialize_verified_overlay(
    outer: Path,
    receiver_root: Path,
) -> tuple[tuple[str, FileIdentity], ...]:
    """Re-verify and safely expand one outer Overlay; manifest is written last."""
    outer = Path(outer)
    receiver_root = Path(receiver_root)
    root_identity = _directory_identity(receiver_root)
    try:
        with OwnedReceiver(receiver_root, root_identity) as authority:
            edge, source_snapshot, source_identity = _verified_source(outer)
            if receiver_root.name != edge.target_version:
                raise _invalid("Overlay target disagrees with receiver directory")
            descriptor = os.open(
                native_path(outer), os.O_RDONLY | getattr(os, "O_BINARY", 0)
            )
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (
                    opened.st_dev, opened.st_ino,
                    opened.st_size, opened.st_mtime_ns,
                ) != source_snapshot:
                    raise _invalid("verified Overlay source is unsafe")
                with zipfile.ZipFile(stream, "r", allowZip64=True) as bundle:
                    infos = _safe_infos(bundle, edge, outer_name=outer.name)
                    written: list[tuple[str, FileIdentity]] = []
                    for name in _ordered_member_names(edge):
                        identity = _copy_member(authority, bundle, infos[name], name)
                        written.append((name, identity))
                opened_after = os.fstat(stream.fileno())
                if (
                    opened_after.st_dev, opened_after.st_ino,
                    opened_after.st_size, opened_after.st_mtime_ns,
                ) != source_snapshot:
                    raise _invalid("verified Overlay source changed while it was read")
            _source_unchanged(outer, source_snapshot, source_identity)
            authority.commit()
    except ReleaseError:
        raise
    except (OSError, OwnedReceiverError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise _io_error("verified Overlay source could not be read") from error
    if _directory_identity(receiver_root) != root_identity:
        raise _invalid("Overlay receiver root changed during materialization")
    _sync_directory(Path(native_path(receiver_root)))
    verified = verify_materialized_overlay(outer, receiver_root)
    if tuple(written) != verified:
        raise _invalid("materialized Overlay readback disagrees")
    return verified


def verify_materialized_overlay(
    outer: Path,
    receiver_root: Path,
) -> tuple[tuple[str, FileIdentity], ...]:
    """Bind exact receiver member bytes back to one independently verified outer ZIP."""
    outer = Path(outer)
    receiver_root = Path(receiver_root)
    root_identity = _directory_identity(receiver_root)
    try:
        with OwnedReceiver(receiver_root, root_identity) as authority:
            edge, source_snapshot, source_identity = _verified_source(outer)
            if receiver_root.name != edge.target_version:
                raise _invalid("Overlay target disagrees with receiver directory")
            descriptor = os.open(
                native_path(outer), os.O_RDONLY | getattr(os, "O_BINARY", 0)
            )
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (
                    opened.st_dev, opened.st_ino,
                    opened.st_size, opened.st_mtime_ns,
                ) != source_snapshot:
                    raise _invalid("verified Overlay source is unsafe")
                with zipfile.ZipFile(stream, "r", allowZip64=True) as bundle:
                    infos = _safe_infos(bundle, edge, outer_name=outer.name)
                    verified: list[tuple[str, FileIdentity]] = []
                    for name in _ordered_member_names(edge):
                        digest = hashlib.sha256()
                        size = 0
                        with bundle.open(infos[name], "r") as reader:
                            while chunk := reader.read(1024 * 1024):
                                digest.update(chunk)
                                size += len(chunk)
                        outer_identity = FileIdentity(size, digest.hexdigest())
                        installed_identity = authority.file_identity(name)
                        if outer_identity != installed_identity:
                            raise _invalid("receiver member bytes disagree with verified Overlay")
                        verified.append((name, installed_identity))
                opened_after = os.fstat(stream.fileno())
                if (
                    opened_after.st_dev, opened_after.st_ino,
                    opened_after.st_size, opened_after.st_mtime_ns,
                ) != source_snapshot:
                    raise _invalid("verified Overlay source changed while it was read")
            _source_unchanged(outer, source_snapshot, source_identity)
            authority.commit()
    except ReleaseError:
        raise
    except (OSError, OwnedReceiverError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise _invalid("materialized Overlay could not be re-verified") from error
    if _directory_identity(receiver_root) != root_identity:
        raise _invalid("Overlay receiver root changed during verification")
    return tuple(verified)


def content_candidate_contract(
    root: Path,
    outer_relative: str,
    outer_identity: FileIdentity,
) -> tuple[tuple[str, ...], tuple[FileIdentity, ...]]:
    """Derive the exact receiver contract from one retained, identity-bound outer ZIP."""
    try:
        normalized = normalize_relative_path(outer_relative)
    except ReleaseError as error:
        raise _invalid("retained Overlay path is invalid") from error
    parts = PurePosixPath(normalized).parts
    if len(parts) != 3 or parts[0] != "patches":
        raise _invalid("retained Overlay path is not in one receiver version root")
    root = Path(root)
    outer = root / Path(normalized)
    if _stable_identity(outer) != outer_identity:
        raise _invalid("retained Overlay identity disagrees with Release")
    extracted = verify_materialized_overlay(outer, root / "patches" / parts[1])
    contract = [(normalized, outer_identity)] + [
        (f"patches/{parts[1]}/{relative}", identity)
        for relative, identity in extracted
    ]
    contract.sort(key=lambda item: item[0].encode("utf-8"))
    return (
        tuple(relative for relative, _identity in contract),
        tuple(identity for _relative, identity in contract),
    )


__all__ = [
    "content_candidate_contract",
    "materialize_verified_overlay",
    "verify_materialized_overlay",
]

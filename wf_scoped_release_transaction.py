#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed filesystem transaction for scoped release archives and manifest."""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import wf_scoped_release_archive as archive
from wf_scoped_release_validation import (
    TransactionError,
    parts as _parts,
    validate_blob as _validate_blob,
)


class _UncertainLinkError(TransactionError):
    """A link result cannot be attributed safely; retain the recovery lock."""


@dataclass(frozen=True, slots=True)
class _OwnedPath:
    path: Path
    object_id: tuple[int, int]
    # POSIX only.  A descriptor held from the moment we created or identified
    # the object pins its inode, so the number cannot be recycled underneath
    # us.  Without it, `(st_dev, st_ino)` is not an identity on POSIX at all:
    # unlink a file and write a new one at the same name and the kernel hands
    # the fresh file the inode that was just freed.
    descriptor: int | None = None


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_reparse(path: Path) -> bool:
    path = Path(path)
    if path.is_symlink():
        return True
    junction = getattr(path, "is_junction", None)
    if junction is not None and junction():
        return True
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)


def _ancestry(path: Path) -> tuple[Path, ...]:
    current = _absolute(path)
    result = [current]
    while current.parent != current:
        current = current.parent
        result.append(current)
    return tuple(reversed(result))


def _assert_plain_ancestry(path: Path, *, leaf: str) -> Path:
    chain = _ancestry(path)
    for index, component in enumerate(chain):
        try:
            metadata = component.lstat()
        except OSError as error:
            raise TransactionError(f"missing or unreadable ancestor: {component}") from error
        if _is_reparse(component):
            raise TransactionError(f"ancestor is a symlink/junction/reparse: {component}")
        expected_leaf = index == len(chain) - 1
        if not expected_leaf and not stat.S_ISDIR(metadata.st_mode):
            raise TransactionError(f"ancestor is not a directory: {component}")
        if expected_leaf and leaf == "directory" and not stat.S_ISDIR(metadata.st_mode):
            raise TransactionError(f"expected directory: {component}")
        if expected_leaf and leaf == "file" and not stat.S_ISREG(metadata.st_mode):
            raise TransactionError(f"expected regular file: {component}")
    return chain[-1]


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def _object_identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _read_stable(path: Path, label: str) -> tuple[bytes, tuple[int, int, int, int]]:
    target = _assert_plain_ancestry(path, leaf="file")
    before = target.lstat()
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise TransactionError(f"{label} opened object is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1 << 20):
            chunks.append(chunk)
        after_open = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after = _assert_plain_ancestry(target, leaf="file").lstat()
    identities = {_identity(item) for item in (before, opened, after_open, after)}
    if len(identities) != 1:
        raise TransactionError(f"{label} identity changed during read")
    return b"".join(chunks), _identity(after)


def _retain(descriptor: int) -> int | None:
    """Hold an independent POSIX reference to the object behind ``descriptor``."""
    if os.name == "nt" or not _posix_exact_cleanup_supported():
        return None
    return os.dup(descriptor)


def _release_owned(items: Iterable[_OwnedPath]) -> None:
    """Drop retained references for owned objects we are done with."""
    for owned in items:
        if owned.descriptor is None:
            continue
        try:
            os.close(owned.descriptor)
        except OSError:
            pass


def _write_exclusive(
    path: Path, payload: bytes, owned: list[_OwnedPath]
) -> None:
    _assert_plain_ancestry(path.parent, leaf="directory")
    with path.open("xb") as stream:
        # Record ownership immediately after exclusive creation.  Callers may then
        # retry cleanup without ever deleting a pre-existing foreign path.
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise TransactionError(f"exclusive output is not a regular file: {path}")
        owned.append(
            _OwnedPath(
                path, _object_identity(metadata), _retain(stream.fileno())
            )
        )
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    actual, _file_id = _read_stable(path, f"exclusive write {path.name}")
    if actual != payload:
        raise TransactionError(f"exclusive write readback drift: {path}")


def _fsync_directory(path: Path) -> None:
    directory = _assert_plain_ancestry(path, leaf="directory")
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        if os.name == "nt":
            return
        raise
    try:
        os.fsync(descriptor)
    except OSError:
        if os.name != "nt":
            raise
    finally:
        os.close(descriptor)


def _windows_owned_api():
    if os.name != "nt":
        raise TransactionError("Windows exact cleanup is unavailable")
    import wf_character_pack as character_pack

    api = character_pack._WIN_OWNED_API
    if api is None:
        raise TransactionError("Windows exact cleanup API is unavailable")
    return api


def _posix_exact_cleanup_supported() -> bool:
    """Report whether ``unlinkat``/``fstatat`` can scope cleanup to a directory."""
    if os.name == "nt":
        return False
    supports = getattr(os, "supports_dir_fd", frozenset())
    return (
        hasattr(os, "O_DIRECTORY")
        and os.unlink in supports
        and os.stat in supports
    )


def _open_owned_parent_posix(parent: Path) -> int:
    """Open the owning directory itself, never a path that may be re-resolved."""
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(parent, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode):
            raise TransactionError(f"owned parent is not a directory: {parent}")
        if _object_identity(opened) != _object_identity(parent.lstat()):
            raise TransactionError(
                f"owned parent directory identity changed: {parent}"
            )
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _remove_owned_posix(paths: Iterable[_OwnedPath]) -> list[str]:
    """Unlink only the exact object, resolved relative to its owning directory.

    POSIX has no delete-by-handle primitive, so this is assembled from the
    pieces that do exist.  ``_assert_plain_ancestry`` rejects reparse points,
    ``O_DIRECTORY | O_NOFOLLOW`` pins the parent object, ``fstatat`` reads the
    name without following a symlink, and ``unlinkat`` acts on that same
    directory descriptor -- so no path component can be re-resolved between the
    check and the unlink.

    Identity is anchored on the descriptor retained since the object was
    created, not on the recorded ``(st_dev, st_ino)`` alone.  Inode numbers are
    reused the instant a file is unlinked, so a replacement written at the same
    name commonly inherits the same number and would pass a bare comparison;
    the retained descriptor keeps the original inode allocated, which makes
    that impossible.  An owned path with no retained descriptor is therefore
    refused rather than deleted on a guess.

    The residual window is a replacement of the identical name inside the
    pinned directory between ``fstatat`` and ``unlinkat``, which the caller's
    exclusive, token-unique creation discipline already excludes.  Falling back
    to ``Path.unlink()`` would re-walk the whole path and is never done.
    """
    errors: list[str] = []
    for owned in reversed(tuple(paths)):
        path = _absolute(owned.path)
        descriptor: int | None = None
        try:
            if owned.descriptor is None:
                errors.append(
                    f"{path}: owned object was never pinned; left untouched"
                )
                continue
            try:
                pinned = os.fstat(owned.descriptor)
            except OSError as error:
                errors.append(f"{path}: retained reference is unusable: {error}")
                continue
            if _object_identity(pinned) != owned.object_id:
                errors.append(f"{path}: retained reference identity drifted")
                continue
            parent = _assert_plain_ancestry(path.parent, leaf="directory")
            if parent.lstat().st_dev != owned.object_id[0]:
                errors.append(f"{path}: owned parent volume changed; left untouched")
                continue
            descriptor = _open_owned_parent_posix(parent)
            try:
                metadata = os.stat(
                    path.name, dir_fd=descriptor, follow_symlinks=False
                )
            except FileNotFoundError:
                continue
            if (
                not stat.S_ISREG(metadata.st_mode)
                or _object_identity(metadata) != _object_identity(pinned)
            ):
                errors.append(f"{path}: owned identity changed; left untouched")
                continue
            os.unlink(path.name, dir_fd=descriptor)
        except FileNotFoundError:
            continue
        except (OSError, TransactionError) as error:
            errors.append(f"{path}: exact relative cleanup failed: {error}")
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError as error:
                    errors.append(f"{path}: close owned parent handle failed: {error}")
    _release_owned(paths)
    return errors


def _remove_owned_unsupported(paths: Iterable[_OwnedPath]) -> list[str]:
    """Fail closed where no exact object-scoped unlink primitive exists."""
    errors: list[str] = []
    for owned in reversed(tuple(paths)):
        path = owned.path
        try:
            _assert_plain_ancestry(path.parent, leaf="directory")
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                continue
            if (
                _is_reparse(path)
                or not stat.S_ISREG(metadata.st_mode)
                or _object_identity(metadata) != owned.object_id
            ):
                errors.append(
                    f"{path}: owned identity changed; left untouched"
                )
                continue
            errors.append(
                f"{path}: exact cleanup unavailable on this platform;"
                " owned path retained"
            )
        except (OSError, TransactionError) as error:
            errors.append(f"{path}: {error}")
    _release_owned(paths)
    return errors


def _remove_owned_windows(paths: Iterable[_OwnedPath]) -> list[str]:
    """Delete only the object opened and identity-checked by a Windows handle."""
    api = _windows_owned_api()
    errors: list[str] = []
    for owned in reversed(tuple(paths)):
        path = _absolute(owned.path)
        parent_handle: int | None = None
        output_handle: int | None = None
        disposed = False
        try:
            parent = _assert_plain_ancestry(path.parent, leaf="directory")
            if parent.lstat().st_dev != owned.object_id[0]:
                errors.append(f"{path}: owned parent volume changed; left untouched")
                continue
            parent_handle = api.open_root(parent)
            expected_parent = os.path.normcase(os.path.abspath(os.fspath(parent)))
            opened_parent = os.path.normcase(
                os.path.abspath(os.fspath(api.final_path(parent_handle)))
            )
            if opened_parent != expected_parent:
                errors.append(
                    f"{path}: owned parent handle resolved elsewhere; left untouched"
                )
                continue
            output_handle = api.reopen_output_cleanup(parent_handle, path.name)
            current = api.identity(output_handle, directory=False)
            if current[1] != owned.object_id[1]:
                errors.append(f"{path}: owned identity changed; left untouched")
                continue
            api.dispose(output_handle)
            disposed = True
        except FileNotFoundError:
            continue
        except (OSError, RuntimeError) as error:
            errors.append(f"{path}: exact handle cleanup failed: {error}")
        finally:
            if output_handle is not None:
                try:
                    api.close(output_handle)
                except OSError as error:
                    errors.append(f"{path}: close owned output handle failed: {error}")
            if parent_handle is not None:
                try:
                    api.close(parent_handle)
                except OSError as error:
                    errors.append(f"{path}: close owned parent handle failed: {error}")
        if disposed:
            try:
                path.lstat()
            except FileNotFoundError:
                pass
            except OSError as error:
                errors.append(f"{path}: exact cleanup readback failed: {error}")
            else:
                errors.append(
                    f"{path}: path occupied after exact cleanup; left untouched"
                )
    _release_owned(paths)
    return errors


def _remove_owned_strategy() -> Callable[[Iterable[_OwnedPath]], list[str]]:
    """Resolve the exact-cleanup implementation this platform can honour."""
    if os.name == "nt":
        return _remove_owned_windows
    if _posix_exact_cleanup_supported():
        return _remove_owned_posix
    return _remove_owned_unsupported


def _remove_owned(paths: Iterable[_OwnedPath]) -> list[str]:
    """Remove only exact owned objects; never unlink a re-resolved pathname."""
    return _remove_owned_strategy()(paths)


def _remove_owned_directory(owned: _OwnedPath) -> list[str]:
    path = owned.path
    try:
        _assert_plain_ancestry(path.parent, leaf="directory")
        metadata = path.lstat()
        if (
            _is_reparse(path)
            or not stat.S_ISDIR(metadata.st_mode)
            or _object_identity(metadata) != owned.object_id
        ):
            return [f"{path}: owned directory identity changed; left untouched"]
        path.rmdir()
        return []
    except (OSError, TransactionError) as error:
        return [f"{path}: {error}"]


def _probe_owned_at(path: Path, *, label: str) -> _OwnedPath | None:
    target = _absolute(path)
    _assert_plain_ancestry(target.parent, leaf="directory")
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        return None
    if _is_reparse(target) or not stat.S_ISREG(metadata.st_mode):
        raise TransactionError(f"{label} is not a plain regular file")
    # Pin the object we just identified, so its inode cannot be recycled into
    # some other file before cleanup gets to it.
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except FileNotFoundError:
        return None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise TransactionError(f"{label} is not a plain regular file")
        if _object_identity(opened) != _object_identity(metadata):
            raise TransactionError(f"{label} changed while being identified")
        retained = _retain(descriptor)
    finally:
        os.close(descriptor)
    return _OwnedPath(target, _object_identity(opened), retained)


def _owned_at(path: Path, *, label: str) -> _OwnedPath:
    owned = _probe_owned_at(path, label=label)
    if owned is None:
        raise TransactionError(f"{label} is missing: {path}")
    return owned


def _link_owned(
    source: _OwnedPath, target: Path, created: list[_OwnedPath]
) -> None:
    try:
        os.link(source.path, target, follow_symlinks=False)
    except BaseException as error:
        try:
            linked = _probe_owned_at(target, label="ambiguous link target")
        except (OSError, TransactionError) as probe_error:
            raise _UncertainLinkError(
                f"cannot prove ambiguous link outcome for {target}: {probe_error}"
            ) from error
        if linked is None:
            raise
        if linked.object_id != source.object_id:
            _release_owned((linked,))
            raise _UncertainLinkError(
                f"ambiguous link target identity changed; left untouched: {target}"
            ) from error
        created.append(linked)
        raise
    linked = _owned_at(target, label="linked archive")
    if linked.object_id != source.object_id:
        _release_owned((linked,))
        raise _UncertainLinkError(
            f"linked archive identity differs from pending source: {target}"
        )
    created.append(linked)


def stage_archives(plans: Iterable[object], staging_dir: Path) -> tuple[Path, ...]:
    parts = _parts(plans)
    staging_dir = _absolute(Path(staging_dir))
    if staging_dir.exists() or staging_dir.is_symlink():
        raise TransactionError(f"staging directory already exists: {staging_dir}")
    _assert_plain_ancestry(staging_dir.parent, leaf="directory")
    staging_dir.mkdir(parents=False, exist_ok=False)
    staging_owned = _OwnedPath(
        staging_dir, _object_identity(staging_dir.lstat())
    )
    created: list[_OwnedPath] = []
    try:
        _assert_plain_ancestry(staging_dir, leaf="directory")
        for part in parts:
            target = staging_dir / part.name
            _write_exclusive(target, part.blob, created)
        _fsync_directory(staging_dir)
        paths = tuple(item.path for item in created)
        _release_owned(created)
        return paths
    except BaseException as error:
        failures = _remove_owned(created)
        failures.extend(_remove_owned_directory(staging_owned))
        if failures:
            raise TransactionError(
                "staging cleanup incomplete: " + "; ".join(failures)
            ) from error
        raise


def _verify_final(
    parts: tuple[archive.ArchivePart, ...],
    targets: tuple[Path, ...],
    identities: dict[Path, tuple[int, int, int, int]] | None = None,
) -> dict[Path, tuple[int, int, int, int]]:
    verified: dict[Path, tuple[int, int, int, int]] = {}
    for part, target in zip(parts, targets, strict=True):
        raw, file_id = _read_stable(target, f"final archive {part.name}")
        if raw != part.blob:
            raise TransactionError(f"final archive bytes changed: {part.name}")
        _validate_blob(part, raw)
        if identities is not None and identities.get(target) != file_id:
            raise TransactionError(f"final archive identity changed: {part.name}")
        verified[target] = file_id
    return verified


def publish_transaction(
    plans: Iterable[object],
    active_dir: Path,
    manifest_path: Path,
    *,
    manifest_preimage: bytes,
    manifest_output: bytes,
    checkpoint: Callable[[str], None] | None = None,
) -> tuple[Path, ...]:
    parts = _parts(plans)
    active = _assert_plain_ancestry(Path(active_dir), leaf="directory")
    manifest = _assert_plain_ancestry(Path(manifest_path), leaf="file")
    if active.parent != manifest.parent:
        raise TransactionError("manifest must be a sibling of the active directory")
    manifest_raw, manifest_id = _read_stable(manifest, "manifest preimage")
    if manifest_raw != manifest_preimage:
        raise TransactionError("manifest changed before archive publication")

    targets = tuple(active / part.name for part in parts)
    if any(path.exists() or path.is_symlink() for path in targets):
        raise TransactionError("one or more archive targets already exist")
    lock = manifest.parent / ".wf-scoped-release.lock"
    token = uuid.uuid4().hex
    private = tuple(
        active / f".wf-scoped-{token}-{index}.pending"
        for index, _part in enumerate(parts, start=1)
    )
    callback = checkpoint or (lambda _phase: None)
    created: list[_OwnedPath] = []
    private_created: list[_OwnedPath] = []
    temporary: _OwnedPath | None = None
    lock_created = False
    committed = False
    lock_owned: list[_OwnedPath] = []
    try:
        _write_exclusive(
            lock, hashlib.sha256(manifest_preimage).digest(), lock_owned
        )
        lock_created = True
        for part, pending in zip(parts, private, strict=True):
            _write_exclusive(pending, part.blob, private_created)
        _fsync_directory(active)

        for part, pending, target in zip(parts, private, targets, strict=True):
            pending_owned = next(
                item for item in private_created if item.path == pending
            )
            _link_owned(pending_owned, target, created)
            raw, _file_id = _read_stable(target, f"linked archive {part.name}")
            if raw != part.blob:
                raise TransactionError(f"linked archive readback drift: {part.name}")
            pending_cleanup = _remove_owned((pending_owned,))
            if pending_cleanup:
                raise TransactionError(
                    "pending archive cleanup incomplete: "
                    + "; ".join(pending_cleanup)
                )
            private_created.remove(pending_owned)
            callback("after_archive")
        _fsync_directory(active)
        archive_ids = _verify_final(parts, targets)

        current_manifest, current_id = _read_stable(manifest, "manifest commit point")
        if current_manifest != manifest_preimage or current_id != manifest_id:
            raise TransactionError("manifest changed before commit point")
        callback("before_manifest")
        _verify_final(parts, targets, archive_ids)
        current_manifest, current_id = _read_stable(manifest, "manifest checkpoint")
        if current_manifest != manifest_preimage or current_id != manifest_id:
            raise TransactionError("manifest changed during commit checkpoint")

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{manifest.name}.", suffix=".tmp", dir=manifest.parent
        )
        temporary_path = Path(temporary_name)
        temporary = _OwnedPath(
            temporary_path, _object_identity(os.fstat(descriptor)),
            _retain(descriptor),
        )
        with os.fdopen(descriptor, "wb") as stream:
            os.chmod(temporary_path, stat.S_IMODE(manifest.stat().st_mode))
            stream.write(manifest_output)
            stream.flush()
            os.fsync(stream.fileno())
        staged_manifest, _staged_id = _read_stable(
            temporary_path, "staged manifest"
        )
        if staged_manifest != manifest_output:
            raise TransactionError("manifest staging readback drift")
        _verify_final(parts, targets, archive_ids)
        current_manifest, current_id = _read_stable(manifest, "manifest final preimage")
        if current_manifest != manifest_preimage or current_id != manifest_id:
            raise TransactionError("manifest changed before atomic replace")
        os.replace(temporary_path, manifest)
        _release_owned((temporary,))
        temporary = None
        committed = True
        _fsync_directory(manifest.parent)
        callback("after_manifest")
    except BaseException as error:
        lock_created = lock_created or bool(lock_owned)
        cleanup = _remove_owned(
            ([temporary] if temporary is not None else [])
        )
        cleanup.extend(_remove_owned(private_created))
        if isinstance(error, _UncertainLinkError):
            cleanup.append(str(error))
        if committed:
            _release_owned(created)
            detail = (
                "; cleanup incomplete: " + "; ".join(cleanup) if cleanup else ""
            )
            raise TransactionError(
                "manifest committed but completion failed; release lock retained"
                + detail
            ) from error
        if not committed:
            cleanup.extend(_remove_owned(created))
            try:
                _fsync_directory(active)
            except OSError as cleanup_error:
                cleanup.append(f"fsync {active}: {cleanup_error}")
        if cleanup:
            raise TransactionError(
                "rollback incomplete; release lock retained: " + "; ".join(cleanup)
            ) from error
        if lock_created:
            lock_cleanup = _remove_owned(lock_owned)
            if lock_cleanup:
                raise TransactionError(
                    "release lock retained after failure: "
                    + "; ".join(lock_cleanup)
                ) from error
            lock_created = False
        raise
    if lock_created:
        lock_cleanup = _remove_owned(lock_owned)
        if lock_cleanup:
            raise TransactionError(
                "manifest committed but release lock cleanup failed: "
                + "; ".join(lock_cleanup)
            )
    _release_owned(created)
    _release_owned(private_created)
    return targets

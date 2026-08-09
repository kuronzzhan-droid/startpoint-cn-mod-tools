"""Canonical JSON, safe relative paths, and stable file-copy primitives."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Final
import unicodedata

from .errors import ReleaseError


_COPY_CHUNK_SIZE: Final = 1024 * 1024
_REPARSE_POINT_ATTRIBUTE: Final = 0x0400


@dataclass(frozen=True)
class FileIdentity:
    """The immutable identity returned for a copied regular file."""

    size: int
    sha256: str


class _DuplicateKey(ValueError):
    pass


class _NonFiniteValue(ValueError):
    pass


def _label_details(label: str) -> dict[str, object]:
    return {"label": label}


def load_json_strict_bytes(raw: bytes, *, label: str) -> object:
    """Parse UTF-8 JSON while rejecting ambiguous or non-standard forms."""
    details = _label_details(label)
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ReleaseError("WFREL_JSON_BOM", "UTF-8 BOM is not permitted", details)
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReleaseError("WFREL_JSON_UTF8", "JSON must be valid UTF-8", details) from error

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise _DuplicateKey(key)
            result[key] = value
        return result

    def reject_nonfinite(value: str) -> object:
        raise _NonFiniteValue(value)

    def reject_nonfinite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise _NonFiniteValue(value)
        return parsed

    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite,
            parse_float=reject_nonfinite_float,
        )
    except _DuplicateKey as error:
        raise ReleaseError("WFREL_JSON_DUPLICATE_KEY", "duplicate JSON key", details) from error
    except _NonFiniteValue as error:
        raise ReleaseError("WFREL_JSON_NONFINITE", "non-finite JSON number", details) from error
    except json.JSONDecodeError as error:
        raise ReleaseError("WFREL_JSON_PARSE", "invalid JSON", details) from error
    if not _contains_non_scalar_unicode(value):
        return value
    raise ReleaseError("WFREL_JSON_VALUE", "JSON contains a non-Unicode scalar", details)


def canonical_json_bytes(value: object) -> bytes:
    """Encode one deterministic UTF-8 JSON document with exactly one final LF."""
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return text.encode("utf-8") + b"\n"
    except (TypeError, UnicodeEncodeError, ValueError) as error:
        raise ReleaseError("WFREL_JSON_VALUE", "value cannot be canonical JSON") from error


def _contains_non_scalar_unicode(value: object) -> bool:
    if isinstance(value, str):
        return any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    if isinstance(value, dict):
        return any(
            _contains_non_scalar_unicode(key) or _contains_non_scalar_unicode(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_non_scalar_unicode(item) for item in value)
    return False


def normalize_relative_path(value: str) -> str:
    """Accept only an already-canonical POSIX relative path."""
    details = {"field": "relativePath"}
    if not isinstance(value, str):
        raise ReleaseError("WFREL_PATH_INVALID", "relative path must be a string", details)
    if (
        not value
        or any(ord(character) <= 0x1F or ord(character) == 0x7F for character in value)
        or "\\" in value
        or value.startswith("/")
        or (len(value) >= 2 and value[0].isalpha() and value[1] == ":")
        or value.endswith("/")
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ReleaseError("WFREL_PATH_INVALID", "path is not canonical", details)

    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ReleaseError("WFREL_PATH_INVALID", "path is not canonical", details)
    return value


def _source_details(source: Path) -> dict[str, object]:
    return {"relativePath": source.name or "."}


def _snapshot_from_stat(source_stat: os.stat_result) -> tuple[int, int, int, int, bool, int]:
    attributes = getattr(source_stat, "st_file_attributes", 0)
    is_regular = stat.S_ISREG(source_stat.st_mode)
    return (
        source_stat.st_dev,
        source_stat.st_ino,
        source_stat.st_size,
        source_stat.st_mtime_ns,
        is_regular,
        attributes & _REPARSE_POINT_ATTRIBUTE,
    )


def _source_snapshot(source: Path) -> tuple[int, int, int, int, bool, int]:
    """Take the source identity required to detect replacement or mutation."""
    return _snapshot_from_stat(source.lstat())


def _stable_regular_source(source: Path) -> tuple[int, int, int, int, bool, int]:
    try:
        snapshot = _source_snapshot(source)
    except OSError as error:
        raise ReleaseError(
            "WFREL_HASH_SOURCE_CHANGED",
            "source file is unavailable",
            _source_details(source),
        ) from error
    if not snapshot[4] or snapshot[5]:
        raise ReleaseError(
            "WFREL_HASH_SOURCE_CHANGED",
            "source must be a non-reparse regular file",
            _source_details(source),
        )
    return snapshot


def _same_file(
    first: tuple[int, int, int, int, bool, int],
    second: tuple[int, int, int, int, bool, int],
) -> bool:
    return first[:2] == second[:2]


def _reject_source_change(source: Path, message: str) -> ReleaseError:
    return ReleaseError("WFREL_HASH_SOURCE_CHANGED", message, _source_details(source))


def _open_destination_for_copy(
    source: Path,
    source_snapshot: tuple[int, int, int, int, bool, int],
    destination: Path,
):
    try:
        destination_snapshot = _source_snapshot(destination)
    except FileNotFoundError:
        destination_snapshot = None
    except OSError as error:
        raise _reject_source_change(source, "destination file is unavailable") from error
    if destination_snapshot is not None and _same_file(source_snapshot, destination_snapshot):
        raise _reject_source_change(source, "source and destination refer to the same file")
    if destination_snapshot is not None and destination_snapshot[5]:
        raise _reject_source_change(source, "destination must not be a reparse point")

    flags = os.O_WRONLY
    if destination_snapshot is None:
        flags |= os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(destination, flags, 0o666)
    except OSError as error:
        raise _reject_source_change(source, "destination file could not be opened") from error
    try:
        opened_destination = _snapshot_from_stat(os.fstat(descriptor))
        if not opened_destination[4] or opened_destination[5]:
            raise _reject_source_change(source, "destination must be a regular file")
        if _same_file(source_snapshot, opened_destination):
            raise _reject_source_change(source, "source and destination refer to the same file")
        if (
            destination_snapshot is not None
            and opened_destination != destination_snapshot
        ):
            raise _reject_source_change(source, "destination changed before it was opened")
        opened_path = _source_snapshot(destination)
        if opened_path != opened_destination:
            raise _reject_source_change(source, "destination changed before it was opened")
        os.ftruncate(descriptor, 0)
        return os.fdopen(descriptor, "wb")
    except BaseException:
        os.close(descriptor)
        raise


def stream_copy_and_hash_stable_file(source: Path, destination: Path) -> FileIdentity:
    """Copy a regular source once, hash its streamed bytes, and verify stability."""
    before = _stable_regular_source(source)
    digest = hashlib.sha256()
    try:
        with source.open("rb") as reader:
            opened_before = _snapshot_from_stat(os.fstat(reader.fileno()))
            if not opened_before[4] or opened_before != before:
                raise _reject_source_change(source, "source changed before it was opened")
            with _open_destination_for_copy(source, before, destination) as writer:
                while chunk := reader.read(_COPY_CHUNK_SIZE):
                    digest.update(chunk)
                    writer.write(chunk)
            opened_after = _snapshot_from_stat(os.fstat(reader.fileno()))
    except OSError as error:
        raise _reject_source_change(source, "source file could not be copied") from error

    after = _stable_regular_source(source)
    if opened_after != before or before != after:
        raise _reject_source_change(source, "source file changed while it was copied")
    return FileIdentity(size=before[2], sha256=digest.hexdigest())

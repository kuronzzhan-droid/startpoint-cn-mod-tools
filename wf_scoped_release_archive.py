#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic ZIP assembly and manifest-last filesystem transaction helpers."""
from __future__ import annotations

import io
import re
import stat
import zipfile
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence


CI_ZIP_CAP = 5 << 20
ZIP_TIMESTAMP = (2026, 8, 6, 0, 0, 0)
ZIP_MODE = (stat.S_IFREG | 0o644) << 16
CLIENT_ROOTS = ("common", "medium", "android")
ROOT_PREFIXES = {
    "common": "production/upload/",
    "medium": "production/medium_upload/",
    "android": "production/android_upload/",
}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
TAG_RE = re.compile(r"^[a-z0-9]+$")


class ArchiveError(RuntimeError):
    """The archive plan or filesystem transaction is unsafe."""


class PayloadEntry(Protocol):
    root: str
    member_name: str
    payload: bytes


@dataclass(frozen=True, slots=True)
class ArchivePart:
    root: str
    sequence: int
    name: str
    blob: bytes


@dataclass(frozen=True, slots=True)
class _CanonicalEntry:
    root: str
    member_name: str
    payload: bytes


def _version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or VERSION_RE.fullmatch(value) is None:
        raise ArchiveError(f"invalid archive version: {value!r}")
    parts = value.split(".")
    if any(str(int(part)) != part for part in parts):
        raise ArchiveError(f"archive version is not canonical: {value!r}")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _compressed_size(payload: bytes) -> int:
    import zlib

    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return len(compressor.compress(payload) + compressor.flush())


def _entry_cost(entry: PayloadEntry) -> int:
    try:
        name_size = len(entry.member_name.encode("ascii"))
    except UnicodeEncodeError as error:
        raise ArchiveError(f"ZIP member name is not ASCII: {entry.member_name!r}") from error
    # Local header (30), central header (46), and the name in both records.
    return 76 + (2 * name_size) + _compressed_size(entry.payload)


def _archive_blob(entries: Sequence[PayloadEntry]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for entry in entries:
            info = zipfile.ZipInfo(entry.member_name, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ZIP_MODE
            info.extra = b""
            info.comment = b""
            archive.writestr(
                info,
                entry.payload,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return output.getvalue()


def _verify_blob(
    blob: bytes, entries: Sequence[PayloadEntry], max_zip_bytes: int
) -> None:
    if len(blob) > max_zip_bytes:
        raise ArchiveError(
            f"ZIP hard cap exceeded: actual={len(blob)} cap={max_zip_bytes}"
        )
    expected = [entry.member_name for entry in entries]
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if names != expected or len(names) != len(set(names)):
                raise ArchiveError("ZIP readback member set or order drift")
            for info, entry in zip(infos, entries, strict=True):
                if (
                    info.date_time != ZIP_TIMESTAMP
                    or info.compress_type != zipfile.ZIP_DEFLATED
                    or info.create_system != 3
                    or info.external_attr != ZIP_MODE
                    or info.flag_bits != 0
                    or info.extra != b""
                    or info.comment != b""
                    or info.is_dir()
                    or archive.read(info) != entry.payload
                ):
                    raise ArchiveError(f"ZIP readback drift: {info.filename}")
            if archive.comment != b"":
                raise ArchiveError("ZIP archive comment drift")
            bad = archive.testzip()
            if bad is not None:
                raise ArchiveError(f"ZIP CRC failure: {bad}")
        if _archive_blob(entries) != blob:
            raise ArchiveError("ZIP byte representation is not canonical")
    except ArchiveError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise ArchiveError(f"cannot verify generated ZIP: {error}") from error


def build_parts(
    entries: Iterable[PayloadEntry],
    *,
    roots: tuple[str, ...],
    from_version: str,
    to_version: str,
    tag: str,
    max_zip_bytes: int,
) -> tuple[ArchivePart, ...]:
    if (
        not isinstance(roots, tuple)
        or not roots
        or len(set(roots)) != len(roots)
        or any(root not in CLIENT_ROOTS for root in roots)
        or tuple(root for root in CLIENT_ROOTS if root in roots) != roots
    ):
        raise ArchiveError("roots must be unique client roots in canonical order")
    if _version(to_version) <= _version(from_version):
        raise ArchiveError("archive edge version must increase")
    if not isinstance(tag, str) or TAG_RE.fullmatch(tag) is None:
        raise ArchiveError("archive tag must contain lowercase ASCII letters and digits")
    if type(max_zip_bytes) is not int or max_zip_bytes < 22:
        raise ArchiveError("max_zip_bytes must be an integer of at least 22")
    if max_zip_bytes > CI_ZIP_CAP:
        raise ArchiveError("max_zip_bytes cannot exceed the 5 MiB CI hard cap")

    grouped = {root: [] for root in roots}
    for entry in entries:
        if entry.root not in grouped:
            raise ArchiveError(f"unsupported client root: {entry.root!r}")
        if not isinstance(entry.member_name, str) or not isinstance(entry.payload, bytes):
            raise ArchiveError("archive entry name and payload have invalid types")
        grouped[entry.root].append(entry)

    planned: list[tuple[str, list[PayloadEntry]]] = []
    for root in roots:
        ordered = sorted(grouped[root], key=lambda item: item.member_name)
        if len({entry.member_name for entry in ordered}) != len(ordered):
            raise ArchiveError(f"duplicate ZIP member in {root}")
        current: list[PayloadEntry] = []
        current_size = 22  # empty archive end-of-central-directory record
        for entry in ordered:
            cost = _entry_cost(entry)
            if 22 + cost > max_zip_bytes:
                raise ArchiveError(
                    f"single member exceeds ZIP hard cap: {entry.member_name}"
                )
            if current and current_size + cost > max_zip_bytes:
                planned.append((root, current))
                current = []
                current_size = 22
            current.append(entry)
            current_size += cost
        if current:
            planned.append((root, current))

    parts: list[ArchivePart] = []
    for sequence, (root, part_entries) in enumerate(planned, start=1):
        name = f"pinball-{from_version}-{to_version}-{sequence}-{tag}.zip"
        blob = _archive_blob(part_entries)
        _verify_blob(blob, part_entries, max_zip_bytes)
        parts.append(ArchivePart(root, sequence, name, blob))
    return tuple(parts)


def attest_plan_parts(
    entries: Iterable[PayloadEntry], parts: Iterable[ArchivePart]
) -> None:
    """Fail closed if a plan's ZIPs omit, add, move, or alter any payload."""
    selected = tuple(entries)
    expected = {(entry.root, entry.member_name): entry.payload for entry in selected}
    if len(expected) != len(selected):
        raise ArchiveError("release plan contains duplicate expected entries")
    actual: dict[tuple[str, str], bytes] = {}
    for part in parts:
        if part.root not in ROOT_PREFIXES:
            raise ArchiveError(f"archive part has invalid root: {part.root!r}")
        try:
            canonical: list[_CanonicalEntry] = []
            with zipfile.ZipFile(io.BytesIO(part.blob)) as zipped:
                infos = zipped.infolist()
                names = [info.filename for info in infos]
                if names != sorted(names):
                    raise ArchiveError(f"archive part member order drift: {part.name}")
                if len(infos) != len(set(names)):
                    raise ArchiveError(f"archive part has duplicate members: {part.name}")
                for info in infos:
                    if (
                        info.date_time != ZIP_TIMESTAMP
                        or info.compress_type != zipfile.ZIP_DEFLATED
                        or info.create_system != 3
                        or info.external_attr != ZIP_MODE
                        or info.flag_bits != 0
                        or info.extra != b""
                        or info.comment != b""
                        or info.is_dir()
                    ):
                        raise ArchiveError(
                            f"archive part metadata drift: {part.name}!{info.filename}"
                        )
                    if not info.filename.startswith(ROOT_PREFIXES[part.root]):
                        raise ArchiveError(
                            f"archive member is in the wrong root: {info.filename}"
                        )
                    key = part.root, info.filename
                    if key in actual:
                        raise ArchiveError(f"archive member repeated across parts: {key}")
                    payload = zipped.read(info)
                    actual[key] = payload
                    canonical.append(_CanonicalEntry(part.root, info.filename, payload))
                if zipped.testzip() is not None:
                    raise ArchiveError(f"archive part failed CRC readback: {part.name}")
                if zipped.comment != b"":
                    raise ArchiveError(f"archive part comment drift: {part.name}")
            if _archive_blob(canonical) != part.blob:
                raise ArchiveError(
                    f"archive part byte representation is not canonical: {part.name}"
                )
        except ArchiveError:
            raise
        except (OSError, zipfile.BadZipFile, RuntimeError) as error:
            raise ArchiveError(f"cannot attest archive part {part.name}: {error}") from error
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(key for key in expected.keys() & actual.keys() if expected[key] != actual[key])
    if missing or extra or changed:
        raise ArchiveError(
            "archive plan payload mismatch: "
            f"missing={missing[:3]} extra={extra[:3]} changed={changed[:3]}"
        )

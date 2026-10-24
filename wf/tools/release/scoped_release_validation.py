#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strict archive-plan validation shared by scoped filesystem publishers."""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from typing import Iterable

import wf_scoped_release_archive as archive


ARCHIVE_RE = re.compile(
    r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-([1-9]\d*)-([a-z0-9]+)\.zip$"
)
MEMBER_RE = {
    root: re.compile(rf"^{re.escape(prefix)}[0-9a-f]{{2}}/[0-9a-f]{{38}}$")
    for root, prefix in archive.ROOT_PREFIXES.items()
}


class TransactionError(RuntimeError):
    """The archive plan or its canonical byte representation is unsafe."""


@dataclass(frozen=True, slots=True)
class _CanonicalEntry:
    root: str
    member_name: str
    payload: bytes


def validate_blob(part: archive.ArchivePart, blob: bytes) -> None:
    if not isinstance(blob, bytes) or not blob or len(blob) > archive.CI_ZIP_CAP:
        raise TransactionError(
            f"archive exceeds final 5 MiB hard cap or is empty: {part.name}"
        )
    if part.root not in MEMBER_RE:
        raise TransactionError(f"archive has invalid root: {part.root!r}")
    try:
        canonical: list[_CanonicalEntry] = []
        with zipfile.ZipFile(io.BytesIO(blob)) as zipped:
            infos = zipped.infolist()
            names = [info.filename for info in infos]
            if not names or names != sorted(names) or len(names) != len(set(names)):
                raise TransactionError(
                    f"archive member set/order is invalid: {part.name}"
                )
            for info in infos:
                if (
                    MEMBER_RE[part.root].fullmatch(info.filename) is None
                    or info.date_time != archive.ZIP_TIMESTAMP
                    or info.compress_type != zipfile.ZIP_DEFLATED
                    or info.create_system != 3
                    or info.external_attr != archive.ZIP_MODE
                    or info.flag_bits != 0
                    or info.extra != b""
                    or info.comment != b""
                    or info.is_dir()
                ):
                    raise TransactionError(
                        f"archive member path/metadata is invalid: "
                        f"{part.name}!{info.filename}"
                    )
                canonical.append(
                    _CanonicalEntry(part.root, info.filename, zipped.read(info))
                )
            if zipped.comment != b"" or zipped.testzip() is not None:
                raise TransactionError(
                    f"archive CRC/comment validation failed: {part.name}"
                )
        if archive._archive_blob(canonical) != blob:
            raise TransactionError(
                f"archive byte representation is not canonical: {part.name}"
            )
    except TransactionError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise TransactionError(f"invalid final archive {part.name}: {error}") from error


def parts(plans: Iterable[object]) -> tuple[archive.ArchivePart, ...]:
    flattened: list[archive.ArchivePart] = []
    for plan in plans:
        values = getattr(plan, "parts", None)
        spec = getattr(plan, "spec", None)
        if not isinstance(values, tuple) or any(
            not isinstance(part, archive.ArchivePart) for part in values
        ):
            raise TransactionError("release plan contains invalid archive parts")
        if [part.sequence for part in values] != list(range(1, len(values) + 1)):
            raise TransactionError("release plan archive sequence is not contiguous")
        if any(part.root not in archive.CLIENT_ROOTS for part in values):
            raise TransactionError("release plan archive root is invalid")
        roots = [archive.CLIENT_ROOTS.index(part.root) for part in values]
        if roots != sorted(roots):
            raise TransactionError("release plan archive roots are not canonical")
        for part in values:
            match = ARCHIVE_RE.fullmatch(part.name)
            if match is None or int(match[3]) != part.sequence:
                raise TransactionError(
                    f"non-canonical archive filename: {part.name!r}"
                )
            try:
                archive._version(match[1])
                archive._version(match[2])
            except archive.ArchiveError as error:
                raise TransactionError(str(error)) from error
            if spec is not None and (
                match[1] != getattr(spec, "from_version", None)
                or match[2] != getattr(spec, "to_version", None)
                or match[4] != getattr(spec, "tag", None)
            ):
                raise TransactionError(
                    f"archive filename differs from edge spec: {part.name}"
                )
            validate_blob(part, part.blob)
        flattened.extend(values)
    if len({part.name for part in flattened}) != len(flattened):
        raise TransactionError("duplicate archive filename across release plans")
    return tuple(flattened)

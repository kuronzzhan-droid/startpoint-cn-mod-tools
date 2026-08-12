"""Build one deterministic Patch Overlay from a sealed character workspace."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Final, Mapping

import wf_character_workspace

from ._legacy_mapping import _hashed_member
from .canonical import canonical_json_bytes
from .errors import ReleaseError
from .patch_overlay_source import inspect_patch_overlay_chain
from .release_archive import capture_parent, force_utf8_flags, verify_parent, write_archive


_VERSION_RE: Final = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_ROOTS: Final = ("android", "common", "medium")
_REPARSE_POINT: Final = 0x0400


@dataclass(frozen=True)
class OverlayBuildReceipt:
    archive_sha256: str
    from_version: str
    payload_file_count: int
    target_version: str

    def to_wire(self) -> dict[str, object]:
        return {
            "archiveSha256": self.archive_sha256,
            "fromVersion": self.from_version,
            "overlayBuildVersion": 1,
            "payloadFileCount": self.payload_file_count,
            "targetVersion": self.target_version,
            "verified": True,
        }


def _fail(message: str, *, code: str = "WFREL_OVERLAY_BUILD_INVALID") -> ReleaseError:
    return ReleaseError(code, message)


def _version(value: object, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise _fail(f"{label} version is invalid")
    match = _VERSION_RE.fullmatch(value)
    if match is None:
        raise _fail(f"{label} version is invalid")
    parsed = tuple(int(item) for item in match.groups())
    if any(item > (1 << 53) - 1 for item in parsed):
        raise _fail(f"{label} version is invalid")
    return parsed


def _is_reparse(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def _regular_bytes(path: Path, claim: Mapping[str, object]) -> bytes:
    try:
        before = path.lstat()
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise OSError("not a regular file")
        raw = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        raise _fail("sealed workspace payload is unavailable or changed") from error
    if _identity(before) != _identity(after):
        raise _fail("sealed workspace payload changed while being read")
    digest = hashlib.sha256(raw).hexdigest()
    if claim.get("size") != len(raw) or claim.get("sha256") != digest:
        raise _fail("sealed workspace payload disagrees with its manifest")
    return raw


def _zip_bytes(members: list[tuple[str, bytes]]) -> bytes:
    stream = io.BytesIO()
    sources = tuple(
        (name, io.BytesIO(raw), len(raw))
        for name, raw in sorted(members, key=lambda item: item[0].encode("utf-8"))
    )
    write_archive(stream, sources)
    return stream.getvalue()


def _workspace_payloads(
    workspace: Path,
) -> tuple[dict[str, list[tuple[str, bytes]]], str]:
    before = wf_character_workspace.inspect_workspace(workspace)
    if before.get("release_ready") is not True:
        raise _fail("character workspace must be sealed and release ready")
    current = wf_character_workspace.load_workspace(workspace)
    try:
        manifest = json.loads(
            (current.package_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise _fail("sealed workspace manifest is unavailable") from error
    roots = manifest.get("roots") if isinstance(manifest, Mapping) else None
    if not isinstance(roots, Mapping):
        raise _fail("sealed workspace roots are invalid")
    result: dict[str, list[tuple[str, bytes]]] = {}
    seen_logical: set[str] = set()
    for root in _ROOTS:
        values = roots.get(root)
        if not isinstance(values, list) or not values:
            raise _fail("sealed workspace must provide every client CDN root")
        payloads: list[tuple[str, bytes]] = []
        for claim in values:
            if not isinstance(claim, Mapping):
                raise _fail("sealed workspace root claim is invalid")
            logical = claim.get("logical_path")
            if not isinstance(logical, str) or not logical or logical in seen_logical:
                raise _fail("sealed workspace logical paths are invalid or duplicated")
            seen_logical.add(logical)
            raw = _regular_bytes(current.package_dir / "roots" / root / Path(logical), claim)
            payloads.append((_hashed_member(root, logical), raw))
        result[root] = payloads
    after = wf_character_workspace.inspect_workspace(workspace)
    if after.get("input_digest") != before.get("input_digest"):
        raise _fail("sealed workspace changed while building the Overlay")
    digest = before.get("input_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise _fail("sealed workspace digest is invalid")
    return result, digest


def _outer_members(
    payloads: Mapping[str, list[tuple[str, bytes]]],
    workspace_digest: str,
    from_version: str,
    target_version: str,
) -> tuple[tuple[str, bytes], ...]:
    tag = workspace_digest[:12]
    archives: list[dict[str, object]] = []
    members: list[tuple[str, bytes]] = [
        ("README.md", b"wf-release-v1 deterministic character Patch Overlay\n"),
        ("requires.json", canonical_json_bytes({
            "schema": 1,
            "workspaceInputSha256": workspace_digest,
        })),
    ]
    for root in _ROOTS:
        inner = _zip_bytes(payloads[root])
        relative = (
            f"archive-{root}-diff/"
            f"pinball-{from_version}-{target_version}-1-{tag}.zip"
        )
        archives.append({
            "bytes": len(inner),
            "layer": root,
            "order": 1,
            "relativePath": relative,
            "sha256": hashlib.sha256(inner).hexdigest(),
        })
        members.append((relative, inner))
    manifest = {
        "archives": archives,
        "baseVersion": from_version,
        "compatibleClient": "CN 1.8.1",
        "schema": 1,
        "targetVersion": target_version,
    }
    ordered = sorted(members, key=lambda item: item[0].encode("utf-8"))
    return (*ordered, ("patch-manifest.json", canonical_json_bytes(manifest)))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def build_character_overlay(
    workspace: Path,
    from_version: str,
    target_version: str,
    output: Path,
) -> OverlayBuildReceipt:
    """Create one no-clobber Overlay without reading or writing live CDN roots."""
    if _version(from_version, "from") >= _version(target_version, "target"):
        raise _fail("Overlay versions must increase")
    destination = Path(output)
    if not destination.is_absolute() or destination.exists():
        raise _fail("Overlay output must be a new absolute path")
    parent = capture_parent(destination.parent)
    payloads, workspace_digest = _workspace_payloads(Path(workspace))
    members = _outer_members(payloads, workspace_digest, from_version, target_version)
    staging_path: Path | None = None
    committed = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b", prefix=".wf-overlay-", suffix=".tmp", dir=destination.parent,
            delete=False,
        ) as staging:
            staging_path = Path(staging.name)
            write_archive(
                staging,
                tuple((name, io.BytesIO(raw), len(raw)) for name, raw in members),
            )
            force_utf8_flags(staging)
        chain, tail = inspect_patch_overlay_chain([staging_path])
        if (
            len(chain) != 1
            or chain[0].from_version != from_version
            or tail != target_version
        ):
            raise _fail("built Overlay failed independent graph readback")
        archive_sha256 = _sha256(staging_path)
        verify_parent(parent)
        try:
            os.link(staging_path, destination)
        except OSError as error:
            raise _fail(
                "Overlay output could not be committed without clobbering",
                code="WFREL_BUILD_OUTPUT_CHANGED",
            ) from error
        committed = True
        try:
            descriptor = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            if os.name != "nt":
                raise
        return OverlayBuildReceipt(
            archive_sha256,
            from_version,
            sum(len(items) for items in payloads.values()),
            target_version,
        )
    finally:
        if staging_path is not None:
            try:
                staging_path.unlink()
            except FileNotFoundError:
                pass
        if not committed and destination.exists():
            # os.link is the only commit point; never remove a concurrent winner.
            pass


__all__ = ["OverlayBuildReceipt", "build_character_overlay"]

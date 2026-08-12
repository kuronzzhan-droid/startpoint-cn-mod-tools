"""Create and reseal isolated editable copies of character workspaces."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from typing import Iterator, Mapping

import wf_character_pack
import wf_character_workspace

from .canonical import canonical_json_bytes, load_json_strict_bytes, normalize_relative_path
from ._character_edit_claims import (
    validate_edit_boundaries,
    validate_table_claims,
    write_edit_baselines,
)
from .errors import ReleaseError


_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_ROOTS = ("common", "medium", "android", "server")
_REPARSE_POINT = 0x0400


@dataclass(frozen=True)
class CharacterCheckoutReceipt:
    character_id: int
    editable: bool
    package_version: str
    source_workspace_input_sha256: str
    workspace_file_count: int

    def to_wire(self) -> dict[str, object]:
        return {
            "characterCheckoutVersion": 1,
            "characterId": self.character_id,
            "editable": self.editable,
            "packageVersion": self.package_version,
            "releaseReady": False,
            "sourceWorkspaceInputSha256": self.source_workspace_input_sha256,
            "workspaceFileCount": self.workspace_file_count,
            "writesLive": False,
        }


@dataclass(frozen=True)
class CharacterSealReceipt:
    character_id: int
    package_version: str
    release_ready: bool
    workspace_file_count: int
    workspace_input_sha256: str

    def to_wire(self) -> dict[str, object]:
        return {
            "characterEditSealVersion": 1,
            "characterId": self.character_id,
            "packageVersion": self.package_version,
            "releaseReady": self.release_ready,
            "workspaceFileCount": self.workspace_file_count,
            "workspaceInputSha256": self.workspace_input_sha256,
            "writesLive": False,
        }


def _fail(message: str) -> ReleaseError:
    return ReleaseError("WFREL_CHARACTER_EDIT_INVALID", message)


def _is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _stable_bytes(path: Path) -> bytes:
    try:
        before = path.lstat()
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise OSError("not a regular file")
        raw = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        raise _fail("character workspace file is unavailable or unsafe") from error
    before_id = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_id = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_id != after_id or len(raw) != before.st_size:
        raise _fail("character workspace changed while being read")
    return raw


def _manifest(path: Path) -> dict[str, object]:
    try:
        value = load_json_strict_bytes(_stable_bytes(path), label="character edit manifest")
    except (UnicodeError, ValueError, TypeError) as error:
        raise _fail("character edit manifest is invalid") from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise _fail("character edit manifest must be an object")
    return value


def _declared(manifest: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    roots = manifest.get("roots")
    if not isinstance(roots, Mapping) or set(roots) != set(_ROOTS):
        raise _fail("character manifest roots are invalid")
    result: dict[str, Mapping[str, object]] = {}
    for root in _ROOTS:
        claims = roots[root]
        if not isinstance(claims, list):
            raise _fail("character manifest root claims are invalid")
        for claim in claims:
            if not isinstance(claim, Mapping) or set(claim) != {"logical_path", "sha256", "size"}:
                raise _fail("character manifest file claim is invalid")
            logical = claim.get("logical_path")
            if not isinstance(logical, str):
                raise _fail("character manifest logical path is invalid")
            try:
                normalize_relative_path(logical)
            except ReleaseError as error:
                raise _fail("character manifest logical path is invalid") from error
            marker = f"{root}/{logical}"
            if marker in result:
                raise _fail("character manifest has a duplicate file claim")
            result[marker] = claim
    return result


def _actual_root_files(package: Path) -> set[str]:
    result: set[str] = set()
    for root in _ROOTS:
        anchor = package / "roots" / root
        stack = [anchor]
        while stack:
            directory = stack.pop()
            try:
                directory_info = directory.lstat()
                if _is_reparse(directory_info) or not stat.S_ISDIR(directory_info.st_mode):
                    raise OSError("unsafe directory")
                entries = list(os.scandir(directory))
            except OSError as error:
                raise _fail("character workspace root cannot be enumerated safely") from error
            for entry in entries:
                path = Path(entry.path)
                try:
                    info = path.lstat()
                except OSError as error:
                    raise _fail("character workspace root changed while being read") from error
                if _is_reparse(info):
                    raise _fail("character workspace roots cannot contain reparse points")
                if stat.S_ISDIR(info.st_mode):
                    stack.append(path)
                elif stat.S_ISREG(info.st_mode):
                    logical = path.relative_to(anchor).as_posix()
                    result.add(f"{root}/{logical}")
                else:
                    raise _fail("character workspace roots must contain only regular files")
    return result


def _snapshot_roots(
    package: Path,
    manifest: Mapping[str, object],
) -> dict[str, bytes]:
    declared = _declared(manifest)
    actual = _actual_root_files(package)
    if actual != set(declared):
        raise _fail("character workspace file set differs from its manifest")
    result: dict[str, bytes] = {}
    for marker, claim in declared.items():
        root, logical = marker.split("/", 1)
        raw = _stable_bytes(package / "roots" / root / Path(logical))
        if claim.get("size") != len(raw) or claim.get("sha256") != hashlib.sha256(raw).hexdigest():
            raise _fail("sealed character source does not match its manifest")
        result[marker] = raw
    return result


def _updated_roots(
    manifest: dict[str, object], payloads: Mapping[str, bytes]
) -> None:
    roots = manifest["roots"]
    assert isinstance(roots, dict)
    for root in _ROOTS:
        claims = roots[root]
        assert isinstance(claims, list)
        for claim in claims:
            assert isinstance(claim, dict)
            marker = f"{root}/{claim['logical_path']}"
            raw = payloads[marker]
            claim["sha256"] = hashlib.sha256(raw).hexdigest()
            claim["size"] = len(raw)


def _sync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        if os.name != "nt":
            raise


@contextmanager
def _staging(parent: Path) -> Iterator[Path]:
    raw = Path(tempfile.mkdtemp(prefix=".character-edit-", dir=parent))
    path = wf_character_workspace._absolute(raw)  # type: ignore[attr-defined]
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def checkout_character_workspace(
    workspace: Path,
    output: Path,
    package_version: str,
) -> CharacterCheckoutReceipt:
    """Copy one sealed workspace into a new, derived editable directory."""
    if not isinstance(package_version, str) or _VERSION.fullmatch(package_version) is None:
        raise _fail("new package version must use canonical x.y.z form")
    destination = Path(output)
    if not destination.is_absolute() or destination.exists():
        raise _fail("character edit output must be a new absolute path")
    parent = destination.parent
    if not parent.is_dir() or wf_character_workspace._path_has_reparse_component(parent):  # type: ignore[attr-defined]
        raise _fail("character edit output parent is unsafe")

    source = wf_character_workspace.load_workspace(Path(workspace))
    before = wf_character_workspace.workspace_status(source, persist=False)
    if not before.release_ready:
        raise _fail("character checkout source must be sealed and release ready")
    manifest = _manifest(source.package_dir / "manifest.json")
    current_version = manifest.get("package_version")
    if package_version == current_version:
        raise _fail("character checkout requires a new package version")
    current_match = _VERSION.fullmatch(current_version) if isinstance(current_version, str) else None
    requested_match = _VERSION.fullmatch(package_version)
    if current_match is None or requested_match is None:
        raise _fail("character package version is not canonical")
    current_parts = tuple(int(current_match.group(index)) for index in range(1, 4))
    requested_parts = tuple(int(requested_match.group(index)) for index in range(1, 4))
    if requested_parts <= current_parts:
        raise _fail("character checkout package version must increase")
    errors = wf_character_pack.validate_manifest(manifest, source.package_dir)
    if errors:
        raise _fail("sealed character source manifest is invalid")
    payloads = _snapshot_roots(source.package_dir, manifest)
    validate_table_claims(manifest, payloads)
    after = wf_character_workspace.workspace_status(source, persist=False)
    if before.input_digest != after.input_digest or not after.release_ready:
        raise _fail("sealed character source changed while being copied")

    with _staging(parent) as temporary:
        edit = wf_character_workspace.init_workspace(
            temporary,
            source.template_character_id,
            source.character_id,
            source.code_name,
            source.package_id,
        )
        for marker, raw in payloads.items():
            root, logical = marker.split("/", 1)
            path = edit.package_dir / "roots" / root / Path(logical)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        editable_manifest = json.loads(json.dumps(manifest))
        editable_manifest["package_version"] = package_version
        qa = editable_manifest.get("qa")
        if not isinstance(qa, dict):
            raise _fail("character manifest qa fields are invalid")
        qa.update({"release_ready": False, "workspace_input_sha256": ""})
        (edit.package_dir / "manifest.json").write_bytes(canonical_json_bytes(editable_manifest))
        write_edit_baselines(edit.evidence_dir, editable_manifest, payloads, before.input_digest)
        status = wf_character_workspace.workspace_status(edit, persist=False)
        if (
            status.release_ready
            or status.manifest_errors
            or status.three_layer_claim_status.get("consistent") is not True
            or status.requirement_report.get("release_ready") is not True
        ):
            raise _fail("editable character checkout did not pass structural validation")
        final = temporary / source.package_id
        if destination.exists():
            raise _fail("character edit output appeared during commit")
        os.rename(final, destination)
        _sync_directory(parent)
    return CharacterCheckoutReceipt(
        source.character_id,
        True,
        package_version,
        before.input_digest,
        len(payloads) + 1,
    )


def seal_edited_character_workspace(workspace: Path) -> CharacterSealReceipt:
    """Validate existing declared edits, refresh file claims, and reseal in place."""
    current = wf_character_workspace.load_workspace(Path(workspace))
    manifest_path = current.package_dir / "manifest.json"
    original = _stable_bytes(manifest_path)
    manifest = _manifest(manifest_path)
    qa = manifest.get("qa")
    if (
        not isinstance(qa, dict)
        or qa.get("delivery_mode") != "production"
        or qa.get("release_ready") is not False
        or qa.get("workspace_input_sha256") != ""
    ):
        raise _fail("seal-character requires an editable checkout")
    payloads = {
        marker: _stable_bytes(current.package_dir / "roots" / marker.split("/", 1)[0] / Path(marker.split("/", 1)[1]))
        for marker in _declared(manifest)
    }
    if _actual_root_files(current.package_dir) != set(payloads):
        raise _fail("character workspace file set differs from its manifest")
    validate_edit_boundaries(current.evidence_dir, manifest, payloads)
    _updated_roots(manifest, payloads)
    errors = wf_character_pack.validate_manifest(manifest, current.package_dir)
    if errors:
        raise _fail("edited character manifest is invalid: " + "; ".join(errors))
    try:
        wf_character_workspace._atomic_bytes(  # type: ignore[attr-defined]
            manifest_path, canonical_json_bytes(manifest)
        )
        sealed = wf_character_workspace.seal_workspace(current)
    except Exception:
        wf_character_workspace._atomic_bytes(manifest_path, original)  # type: ignore[attr-defined]
        raise
    if not sealed.release_ready:
        wf_character_workspace._atomic_bytes(manifest_path, original)  # type: ignore[attr-defined]
        raise _fail("edited character workspace did not seal successfully")
    package_version = manifest.get("package_version")
    assert isinstance(package_version, str)
    return CharacterSealReceipt(
        current.character_id,
        package_version,
        True,
        sealed.file_count,
        sealed.input_digest,
    )


__all__ = [
    "CharacterCheckoutReceipt",
    "CharacterSealReceipt",
    "checkout_character_workspace",
    "seal_edited_character_workspace",
]

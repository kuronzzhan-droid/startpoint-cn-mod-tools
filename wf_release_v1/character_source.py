"""Read-only adapter for sealed character workspaces and Patch Overlays."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass
import os
from pathlib import Path
import stat

from wf_character_workspace import (
    Workspace,
    WorkspaceError,
    load_workspace,
    workspace_status,
)

from .canonical import load_json_strict_bytes
from .errors import ReleaseError
from .patch_overlay_source import SourceFile, inspect_patch_overlay_chain


_REPARSE_POINT = 0x0400


@dataclass(frozen=True)
class CharacterReleaseSource:
    workspace_input_sha256: str
    package_manifest: Mapping[str, object]
    overlay_files: tuple[SourceFile, ...]
    cdn_target_version: str


@dataclass(frozen=True)
class _WorkspaceInspection:
    workspace: Workspace
    input_digest: str
    package_manifest: dict[str, object]


def _error(code: str, message: str, **details: object) -> ReleaseError:
    return ReleaseError(code, message, details)


def _snapshot(file_stat: os.stat_result) -> tuple[int, int, int, int]:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_size,
        file_stat.st_mtime_ns,
    )


def _is_reparse(file_stat: os.stat_result) -> bool:
    return stat.S_ISLNK(file_stat.st_mode) or bool(
        getattr(file_stat, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _read_stable_manifest(path: Path) -> bytes:
    descriptor = -1
    try:
        before_stat = os.lstat(path)
        if _is_reparse(before_stat) or not stat.S_ISREG(before_stat.st_mode):
            raise OSError("not a regular file")
        before = _snapshot(before_stat)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode) or _snapshot(opened) != before:
            raise OSError("file identity changed before open")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            raw = stream.read()
            after_open = _snapshot(os.fstat(stream.fileno()))
        after_path = os.lstat(path)
        if after_open != before or _snapshot(after_path) != before or _is_reparse(after_path):
            raise OSError("file identity changed while reading")
        return raw
    except OSError as error:
        raise _error(
            "WFREL_CHARACTER_SOURCE_CHANGED",
            "sealed workspace input changed while being inspected",
            label="package/manifest.json",
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _inspect_workspace_before(workspace: Path) -> _WorkspaceInspection:
    try:
        current = load_workspace(workspace)
        status = workspace_status(current, persist=False)
    except (OSError, WorkspaceError) as error:
        raise _error(
            "WFREL_CHARACTER_SOURCE_INVALID",
            "character workspace is unavailable or invalid",
            label="workspace",
        ) from error
    requirements = status.requirement_report
    layers = status.three_layer_claim_status
    layer_names = ("layer_1_cdndata", "layer_2_client", "server_character")
    if (
        not status.release_ready
        or requirements.get("required_total") != 37
        or requirements.get("required_present") != 37
        or requirements.get("missing_required") != []
        or requirements.get("release_ready") is not True
        or layers.get("consistent") is not True
        or not all(layers.get(name) is True for name in layer_names)
    ):
        raise _error(
            "WFREL_CHARACTER_SOURCE_INVALID",
            "character workspace is not sealed production 37/37",
            label="workspace",
        )

    manifest_raw = _read_stable_manifest(current.package_dir / "manifest.json")
    try:
        manifest = load_json_strict_bytes(manifest_raw, label="package/manifest.json")
    except ReleaseError as error:
        raise _error(
            "WFREL_CHARACTER_SOURCE_INVALID",
            "character package manifest is not strict JSON",
            label="package/manifest.json",
        ) from error
    if not isinstance(manifest, dict):
        raise _error(
            "WFREL_CHARACTER_SOURCE_INVALID",
            "character package manifest must be an object",
            label="package/manifest.json",
        )
    qa = manifest.get("qa")
    if (
        manifest.get("character_id") != current.character_id
        or manifest.get("code_name") != current.code_name
        or manifest.get("package_id") != current.package_id
        or not isinstance(qa, Mapping)
        or qa.get("delivery_mode") != "production"
        or qa.get("release_ready") is not True
        or qa.get("required_assets_total") != 37
        or qa.get("required_assets_present") != 37
        or qa.get("workspace_input_sha256") != status.input_digest
    ):
        raise _error(
            "WFREL_CHARACTER_SOURCE_INVALID",
            "workspace identity and package seal do not match",
            label="package/manifest.json",
        )
    return _WorkspaceInspection(
        workspace=current,
        input_digest=status.input_digest,
        package_manifest=copy.deepcopy(manifest),
    )


def inspect_character_source(
    *,
    workspace: Path,
    overlay_archives: Sequence[Path],
) -> CharacterReleaseSource:
    """Inspect explicit release inputs without writing workspace, CDN, or live state."""
    before = _inspect_workspace_before(Path(workspace))
    overlay_files, target = inspect_patch_overlay_chain(overlay_archives)
    try:
        after = workspace_status(before.workspace, persist=False)
    except (OSError, WorkspaceError) as error:
        raise _error(
            "WFREL_CHARACTER_SOURCE_CHANGED",
            "sealed workspace changed while being inspected",
            label="workspace",
        ) from error
    if not after.release_ready or after.input_digest != before.input_digest:
        raise _error(
            "WFREL_CHARACTER_SOURCE_CHANGED",
            "sealed workspace changed while being inspected",
            label="workspace",
        )
    return CharacterReleaseSource(
        workspace_input_sha256=before.input_digest,
        package_manifest=before.package_manifest,
        overlay_files=overlay_files,
        cdn_target_version=target,
    )

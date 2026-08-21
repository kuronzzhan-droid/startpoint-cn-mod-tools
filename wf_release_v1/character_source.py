"""Read-only adapter for sealed character workspaces and Patch Overlays."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass, field
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
from .schema import AssetReplacement, parse_asset_replacements


_REPARSE_POINT = 0x0400


@dataclass(frozen=True, init=False)
class CharacterReleaseSource:
    workspace_input_sha256: str
    _package_manifest: dict[str, object] = field(repr=False)
    overlay_files: tuple[SourceFile, ...]
    cdn_target_version: str
    accepted_asset_replacements: tuple[AssetReplacement, ...]

    def __init__(
        self,
        *,
        workspace_input_sha256: str,
        package_manifest: Mapping[str, object],
        overlay_files: tuple[SourceFile, ...],
        cdn_target_version: str,
        accepted_asset_replacements: tuple[AssetReplacement, ...] = (),
    ) -> None:
        object.__setattr__(self, "workspace_input_sha256", workspace_input_sha256)
        object.__setattr__(
            self,
            "_package_manifest",
            copy.deepcopy(dict(package_manifest)),
        )
        object.__setattr__(self, "overlay_files", overlay_files)
        object.__setattr__(self, "cdn_target_version", cdn_target_version)
        object.__setattr__(
            self, "accepted_asset_replacements", accepted_asset_replacements
        )

    @property
    def package_manifest(self) -> dict[str, object]:
        """Return a caller-owned copy of the authenticated package manifest."""
        return copy.deepcopy(self._package_manifest)


@dataclass(frozen=True)
class _WorkspaceInspection:
    workspace: Workspace
    input_digest: str
    package_manifest: dict[str, object]
    accepted_asset_replacements: tuple[AssetReplacement, ...]


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
    replacements = _accepted_asset_replacements(manifest)
    return _WorkspaceInspection(
        workspace=current,
        input_digest=status.input_digest,
        package_manifest=copy.deepcopy(manifest),
        accepted_asset_replacements=replacements,
    )


def _accepted_asset_replacements(
    manifest: Mapping[str, object],
) -> tuple[AssetReplacement, ...]:
    snapshot = manifest.get("snapshot")
    raw = (
        snapshot.get("accepted_asset_replacements", [])
        if isinstance(snapshot, Mapping)
        else []
    )
    if not isinstance(raw, list):
        raise _error(
            "WFREL_CHARACTER_SOURCE_INVALID",
            "accepted asset replacements must be an array",
            label="snapshot.accepted_asset_replacements",
        )
    if not raw:
        return ()
    wire: list[dict[str, object]] = []
    for index, value in enumerate(raw):
        if not isinstance(value, Mapping) or set(value) != {
            "root", "logical_path", "before_sha256", "before_size"
        }:
            raise _error(
                "WFREL_CHARACTER_SOURCE_INVALID",
                "accepted asset replacement fields are invalid",
                label=f"snapshot.accepted_asset_replacements[{index}]",
            )
        wire.append({
            "root": value["root"],
            "logicalPath": value["logical_path"],
            "beforeSha256": value["before_sha256"],
            "beforeSize": value["before_size"],
        })
    wire.sort(key=lambda item: (
        str(item["root"]).encode("utf-8"),
        str(item["logicalPath"]).encode("utf-8"),
    ))
    try:
        replacements = parse_asset_replacements(wire)
    except ReleaseError as error:
        raise _error(
            "WFREL_CHARACTER_SOURCE_INVALID",
            "accepted asset replacements are invalid",
            label="snapshot.accepted_asset_replacements",
        ) from error

    roots = manifest.get("roots")
    tables = manifest.get("tables")
    if not isinstance(roots, Mapping) or not isinstance(tables, list):
        raise _error(
            "WFREL_CHARACTER_SOURCE_INVALID",
            "character manifest roots or tables are invalid",
            label="package/manifest.json",
        )
    declared: set[tuple[str, str]] = set()
    for root in ("common", "medium", "android"):
        entries = roots.get(root)
        if not isinstance(entries, list):
            raise _error(
                "WFREL_CHARACTER_SOURCE_INVALID",
                "character manifest client roots are invalid",
                label=f"roots.{root}",
            )
        declared.update(
            (root, entry.get("logical_path"))
            for entry in entries
            if isinstance(entry, Mapping) and isinstance(entry.get("logical_path"), str)
        )
    table_paths = {
        (entry.get("root"), entry.get("logical_path"))
        for entry in tables
        if isinstance(entry, Mapping)
    }
    for replacement in replacements:
        key = replacement.root, replacement.logical_path
        if key not in declared or key in table_paths:
            raise _error(
                "WFREL_CHARACTER_SOURCE_INVALID",
                "accepted asset replacement is not an exact non-table candidate entry",
                label=f"{replacement.root}:{replacement.logical_path}",
            )
    return replacements


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
        accepted_asset_replacements=before.accepted_asset_replacements,
    )

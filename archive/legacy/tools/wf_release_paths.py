# -*- coding: utf-8 -*-
"""Resolve tool, server, store, and CDN roots for character releases."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import wf_character_pack as character_pack
import wf_mod_tool as core


class ReleasePathError(ValueError):
    """A configured release root is missing or has the wrong shape."""


@dataclass(frozen=True)
class ReleasePaths:
    tool_root: Path
    server_root: Path
    live_roots: character_pack.LiveRoots
    cdn_root: Path


def tool_checkout_root(module_file: Path) -> Path:
    """Return the checkout root for embedded and flat tool layouts."""
    tool_dir = Path(module_file).resolve().parent
    return tool_dir.parent if tool_dir.name.casefold() == "mod-tools" else tool_dir


def resolve_release_paths(profile_id: str, *, module_file: Path) -> ReleasePaths:
    if profile_id != "cn":
        raise ReleasePathError("character release is CN-only")

    profile = core.resolve_profile("cn")
    if profile is not None and profile.id != "cn":
        raise ReleasePathError("active CN profile/store is unavailable")
    try:
        store = core.require_active_store(profile=profile, profile_id="cn")
    except (OSError, ValueError) as exc:
        raise ReleasePathError(
            f"active CN profile/store is unavailable: {exc}"
        ) from exc

    try:
        server_root = Path(core.resolve_server_dir("cn")).resolve()
    except (OSError, ValueError) as exc:
        raise ReleasePathError(
            f"configured server root is unavailable: {exc}"
        ) from exc
    if not server_root.is_dir() or not (server_root / "assets").is_dir():
        raise ReleasePathError(f"configured server root is unavailable: {server_root}")
    try:
        cdn_root = Path(core.resolve_cdn_root("cn")).resolve()
    except (OSError, ValueError) as exc:
        raise ReleasePathError(f"configured CDN root is unavailable: {exc}") from exc

    live_roots = character_pack.LiveRoots(
        common=store,
        medium=store.parent / "medium_upload",
        android=store.parent / "android_upload",
        server=server_root / "assets",
        protected=(cdn_root,),
    )
    return ReleasePaths(
        tool_root=tool_checkout_root(module_file),
        server_root=server_root,
        live_roots=live_roots,
        cdn_root=cdn_root,
    )

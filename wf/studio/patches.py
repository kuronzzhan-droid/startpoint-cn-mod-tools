"""补丁管理: read-only listing of the kulo asset-patch chain."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from wf.paths import path

from .source import StudioSource, edge_versions


def manifest_path() -> Path:
    return path("kulo") / "assets/asset-patch/manifest.json"


def _members(archive: Path) -> list[str] | None:
    try:
        with zipfile.ZipFile(archive) as handle:
            return handle.namelist()
    except (OSError, zipfile.BadZipFile):
        return None


def patch_chain(source: StudioSource) -> dict:
    location = manifest_path()
    manifest = json.loads(location.read_text("utf-8")) if location.is_file() else {"patches": []}
    active = Path(source.view.active)
    in_view = {Path(p).name for p in source.view.zips}
    listed = set()
    patches = []
    for entry in manifest.get("patches", []):
        archive = entry.get("archive", "")
        listed.add(archive)
        file = active / archive if archive else None
        patches.append({
            "id": entry.get("id"), "name": entry.get("name"), "description": entry.get("description", ""),
            "version": entry.get("version"), "dependsOn": entry.get("depends_on"),
            "enabled": bool(entry.get("enabled")), "archive": archive,
            "archiveSize": entry.get("archive_size"), "createdAt": entry.get("created_at"),
            "changes": entry.get("changes", []), "fileCount": len(entry.get("files", []) or []),
            "presentInActive": bool(file and file.is_file()), "inView": archive in in_view,
            "origin": "清单登记",
        })
    # ZIPs that the view reads but the manifest does not list (local edges or extras).
    for archive in source.view.zips:
        archive = Path(archive)
        if archive.name in listed:
            continue
        versions = edge_versions(archive.name)
        members = _members(archive)
        patches.append({
            "id": archive.stem, "name": archive.stem, "description": "",
            "version": f"1.4.{versions[1]}" if versions else None,
            "dependsOn": f"1.4.{versions[0]}" if versions else None,
            "enabled": None, "archive": archive.name, "archiveSize": archive.stat().st_size,
            "createdAt": None, "changes": [], "fileCount": len(members) if members is not None else None,
            "presentInActive": archive.parent == active, "inView": True,
            "origin": "active 目录（清单未登记）" if archive.parent == active else "额外叠加 ZIP",
        })

    def order(item):
        version = item.get("version") or "0.0.0"
        try:
            return tuple(int(x) for x in version.split(".")), item["archive"]
        except ValueError:
            return (0,), item["archive"]

    patches.sort(key=order, reverse=True)
    return {"cdnVersion": manifest.get("cdn_version"), "viewVersion": source.version,
            "manifest": "kulo assets/asset-patch/manifest.json", "count": len(patches), "patches": patches,
            "note": "只读：列出补丁链与视图实际叠加的 ZIP；本版不生成、不导出、不应用、不发布补丁。"}


def patch_members(source: StudioSource, archive_name: str) -> dict | None:
    candidates = [Path(p) for p in source.view.zips if Path(p).name == archive_name]
    active = Path(source.view.active) / archive_name
    if not candidates and active.is_file() and active.parent.name == "active":
        candidates = [active]
    if not candidates:
        return None
    members = _members(candidates[0])
    return {"archive": archive_name, "members": members or [], "count": len(members or [])}

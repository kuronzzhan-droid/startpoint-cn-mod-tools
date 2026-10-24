"""Manifest-bound package access for explicitly selected external Wiki records."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re

from wf_wiki_catalog_source import TABLES, WikiSource
from wf_wiki_media import WikiMedia, digest


class PackageFiles:
    def __init__(self, package: Path, media):
        self.root = Path(package).resolve()
        self.media = media
        manifest_path = self.root / "manifest.json"
        raw = manifest_path.read_bytes()
        self.manifest_hash = digest(raw)
        self.manifest = json.loads(raw)
        self.media._sources[manifest_path] = self.manifest_hash
        self.entries = {}
        for tier, entries in self.manifest.get("roots", {}).items():
            if tier not in {"common", "medium", "android", "ios", "server"}:
                raise ValueError("外部角色包含未知资源分层")
            for entry in entries:
                logical = entry.get("logical_path", "")
                path = PurePosixPath(logical)
                if (not logical or path.is_absolute() or ".." in path.parts
                        or "\\" in logical or ":" in logical):
                    raise ValueError("外部角色包含不安全资源路径")
                checksum = entry.get("sha256", "")
                if not re.fullmatch(r"[0-9a-f]{64}", checksum):
                    raise ValueError("外部角色包缺少有效资源校验值")
                key = tier, logical
                if key in self.entries:
                    raise ValueError("外部角色包含重复资源")
                self.entries[key] = entry

    def read(self, logical: str, tier: str = "common") -> bytes | None:
        entry = self.entries.get((tier, logical))
        if entry is None:
            return None
        path = (self.root / "roots" / tier / logical).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("外部角色资源指向包目录之外")
        raw = path.read_bytes()
        if digest(raw) != entry["sha256"]:
            raise ValueError("外部角色包与清单校验值不符，请重新确认资料版本")
        self.media._sources[path] = entry["sha256"]
        return raw


class PackageSource(WikiSource):
    """Overlay only manifest-owned table keys; never expose stale table copies."""

    def __init__(self, repo: Path, store: Path, files: PackageFiles):
        super().__init__(repo, store)
        self.files = files
        self.live = WikiSource(repo, store)
        self.claims = {item["logical_path"]: set(item["outer_keys"])
                       for item in files.manifest.get("tables", [])
                       if item.get("root") == "common"}

    def raw(self, logical: str, official: bool = False) -> bytes | None:
        if official:
            return self.live.raw(logical, True)
        key = logical, False
        if key not in self._raw:
            raw = self.files.read(logical)
            if raw is None:
                raw = self.live.raw(logical)
            elif raw is not None:
                self.fingerprints[logical] = digest(raw)
            self._raw[key] = raw
        return self._raw[key]

    def table(self, name: str, official: bool = False) -> dict:
        if official:
            return self.live.table(name, True)
        logical = TABLES.get(name, name)
        owned = self.claims.get(logical)
        if owned is None:
            return self.live.table(name)
        if ("common", logical) not in self.files.entries:
            raise ValueError("外部角色包认领的数据表不在清单内")
        package_rows = super().table(name)
        if not owned.issubset(package_rows):
            raise ValueError("外部角色包缺少清单认领的数据键")
        merged = dict(self.live.table(name))
        merged.update({key: package_rows[key] for key in owned})
        return merged

    def citation(self, name: str) -> dict:
        logical = TABLES.get(name, name)
        if logical not in self.fingerprints:
            return self.live.citation(name)
        return {"logical": logical, "sha256": self.fingerprints[logical],
                "source": "2026-09-27 外部独立角色包"}

    def verify_unchanged(self) -> None:
        self.live.verify_unchanged()
        # Parent exporter checks these again immediately before writing output.
        self.files.media._sources.update({p: sha for p, sha in self.live._files.items()
                                          if sha is not None})
        self.files.media.verify_sources()


class PackageMedia(WikiMedia):
    """Use the normal codecs/cache while reading only declared package media."""

    def __init__(self, parent, files: PackageFiles):
        self.__dict__.update(parent.__dict__)
        self.files = files

    def has(self, logical: str) -> bool:
        return any((tier, logical) in self.files.entries
                   for tier in ("common", "medium", "android", "ios"))

    def _read(self, logical: str) -> bytes | None:
        for tier in ("common", "medium", "android", "ios"):
            raw = self.files.read(logical, tier)
            if raw is not None:
                return raw
        self.errors.append({"logical": logical, "reason": "独立角色包缺少资源"})
        return None

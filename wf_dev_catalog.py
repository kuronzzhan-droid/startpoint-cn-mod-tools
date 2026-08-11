#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wf_dev_catalog.py — 现有发布链 ⇄ 上游 dev 分支 CDN Catalog 适配层。

上游 dev(origin/dev)引入 content:sync:服务端启动前把完整 CDN 输入编译成
不可变 Content Release。Catalog schema 与校验规则源自
src/content/cdn/{types,patch-graph,catalog-builder,runtime-manifest}.ts,
本工具把整套校验移植到 Python(错误码逐一对应),服务两条并存路径:

  运行时接收(现状路径,零改动):cn-asset-graph 动态扫描 + mod-admin 热重载,
      本工具只读不写现有链目录结构。
  启动前编译(dev 路径):以本工具产出的 runtime-manifest JSON + 合并
      EntityLists CSV 作为 content:sync / Content Builder 的输入。

子命令:
  audit           体检:按 dev 语义扫链,输出 扫描器/归档/版本图 三层问题清单
  emit            发射:产出 dev 格式 catalog-cn-<target>.json + 合并 EntityLists
  heal-layers     为缺 quality/platform 层的历史边补官方样式 .empty 占位包(默认 dry-run)
  verify-baseline 用 dev 侧 tracked manifest(金样)验证本移植的保真度

用法:
  python mod-tools/wf_dev_catalog.py audit [--digest skip|cache]
  python mod-tools/wf_dev_catalog.py emit [--out DIR] [--allow-issues]
  python mod-tools/wf_dev_catalog.py heal-layers [--apply]
  python mod-tools/wf_dev_catalog.py verify-baseline --manifest FILE [--stat-files]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import posixpath
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CDN_ROOT = core.resolve_cdn_root_lax()
# asset-patch 是 main 时代的服务端仓内机制;独立布局下按 WF_SERVER_DIR 定位
_SERVER_DIR = core.resolve_server_dir()
ASSET_PATCH_ACTIVE = _SERVER_DIR / "assets" / "asset-patch" / "active"

OFFICIAL_TARGET = "1.4.54"
BASELINE_LABEL = "cn-1.4.54"

# —— dev 侧常量(与 catalog-builder.ts 逐一对应) ——
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
DIFF_NAME_RE = re.compile(
    r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-(\d+)-([a-fA-F0-9]+)\.zip$"
)
FULL_NAME_RE = re.compile(r"^pinball-(\d+\.\d+\.\d+)-(\d+)-([a-fA-F0-9]+)\.zip$")
# 本地链宽松名(cn-asset-graph 同款):后缀允许任意串,dev 扫描器不认
LEGACY_DIFF_RE = re.compile(
    r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-([1-9]\d*)-(.+)\.zip$"
)
LEGACY_FULL_RE = re.compile(r"^pinball-(\d+\.\d+\.\d+)-([1-9]\d*)-(.+)\.zip$")
SHA256_HEX_RE = re.compile(r"^[a-f0-9]{64}$")
# 官方 EntityLists 的 path 列有三种根,tag 与根一一对应:
#   production/upload → common, production/medium_upload → medium,
#   production/android_upload → android(与所在 zip 的层无关)
UPLOAD_MEMBER_RE = re.compile(
    r"^production/(upload|medium_upload|android_upload)/[0-9a-f]{2}/[0-9a-f]{38}$"
)
MEMBER_PREFIX_TO_CSV_TAG = {
    "upload": "common",
    "medium_upload": "medium",
    "android_upload": "android",
}
ENTITY_CSV_RE = re.compile(r"-android_medium\.csv$")
ENTITY_LIST_HEADER = ("path", "version", "size", "hash", "layer")

ARCHIVE_DIRECTORIES = (
    ("archive-common-full", "full", "common"),
    ("archive-medium-full", "full", "quality"),
    ("archive-android-full", "full", "platform"),
    ("archive-common-diff", "diff", "common"),
    ("archive-medium-diff", "diff", "quality"),
    ("archive-android-diff", "diff", "platform"),
)
LAYER_ORDER = {"common": 0, "quality": 1, "platform": 2}
# (kind, layer) -> 目录名。layer 是语义名(common/quality/platform),目录名用的是
# 介质名(common/medium/android),两者不能互相当成对方用。
ARCHIVE_DIRECTORY_BY_LAYER = {
    (kind, layer): directory for directory, kind, layer in ARCHIVE_DIRECTORIES
}
ASSET_SIZE_KINDS = ("shortened", "fulfill")
DIGEST_PLACEHOLDER = "0" * 64
JS_MAX_SAFE_INTEGER = (1 << 53) - 1
OVERLAY_SCHEMA = 1
OVERLAY_CLIENT = "CN 1.8.1"
OVERLAY_LAYER_NAMES = {
    "common": ("common", "archive-common-diff"),
    "quality": ("medium", "archive-medium-diff"),
    "platform": ("android", "archive-android-diff"),
}


@dataclass
class Issue:
    code: str
    message: str
    category: str  # layout | scanner | archive | graph
    relative_path: str | None = None

    def line(self) -> str:
        suffix = f"  [{self.relative_path}]" if self.relative_path else ""
        return f"{self.code}: {self.message}{suffix}"


class OverlayExportError(ValueError):
    """Stable machine-readable failure raised before an Overlay batch is published."""

    def __init__(
        self,
        code: str,
        message: str,
        category: str,
        *,
        target_version: str,
        relative_path: str | None = None,
    ) -> None:
        self.code = code
        self.category = category
        self.target_version = target_version
        self.relative_path = relative_path
        suffix = f" path={relative_path}" if relative_path else ""
        super().__init__(
            f"{code}: {message} [category={category} target={target_version}{suffix}]"
        )


@dataclass
class ArchiveInput:
    kind: str  # full | diff
    from_version: str | None
    to_version: str
    platform: str
    layer: str
    order: int
    relative_path: str
    compressed_bytes: int
    sha256: str
    dev_legal_name: bool = True
    foreign_root: bool = False

    def metadata_key(self) -> tuple:
        return (
            self.kind, self.from_version, self.to_version, self.platform,
            self.layer, self.order, self.compressed_bytes, self.sha256,
        )

    def edge_group_key(self) -> tuple:
        return (self.kind, self.from_version, self.to_version, self.platform)


@dataclass
class OverlaySource:
    archive: ArchiveInput
    source_root: Path
    source_relative_path: str
    snapshot_path: Path
    snapshot_identity: tuple[int, int, int, int, int]


@dataclass(frozen=True)
class PinnedPackageMember:
    relative_path: str
    path: Path
    identity: tuple[int, int, int, int, int]


@dataclass(frozen=True)
class OverlayCandidatePin:
    root_identity: tuple[int, int, int, int, int]
    members: tuple[PinnedPackageMember, ...]


@dataclass
class CatalogEdge:
    from_version: str | None  # None = full
    to_version: str
    platform: str
    asset_size_kind: str
    archives: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------- 基础函数

def parse_version(version: str) -> tuple[int, int, int] | None:
    match = VERSION_RE.fullmatch(version) if isinstance(version, str) else None
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def compare_versions(left: str, right: str) -> int:
    left_parts, right_parts = parse_version(left), parse_version(right)
    if left_parts is None or right_parts is None:
        return (left > right) - (left < right)
    return (left_parts > right_parts) - (left_parts < right_parts)


def is_safe_relative_path(relative_path: str) -> bool:
    if (
        not relative_path
        or "\\" in relative_path
        or posixpath.isabs(relative_path)
    ):
        return False
    normalized = posixpath.normpath(relative_path)
    return (
        normalized == relative_path
        and normalized != ".."
        and not normalized.startswith("../")
    )


def _parse_csv_line(line: str, line_number: int) -> list[str]:
    columns: list[str] = []
    value = ""
    quoted = False
    index = 0
    while index < len(line):
        character = line[index]
        if character == '"':
            if quoted and index + 1 < len(line) and line[index + 1] == '"':
                value += '"'
                index += 1
            else:
                quoted = not quoted
        elif character == "," and not quoted:
            columns.append(value)
            value = ""
        else:
            value += character
        index += 1
    if quoted:
        raise ValueError(f"EntityLists row {line_number} has an unterminated quote")
    columns.append(value)
    return columns


def parse_entity_list_rows(content: str) -> list[tuple[str, str, int, str, str]]:
    """解析 5 列 CSV → [(path, version, size, hash, tag)];与 dev 同规则。"""
    rows: list[tuple[str, str, int, str, str]] = []
    content_rows = 0
    for line_index, line in enumerate(content.lstrip("﻿").splitlines()):
        if not line.strip():
            continue
        columns = [column.strip() for column in _parse_csv_line(line, line_index + 1)]
        is_header = content_rows == 0 and tuple(columns) == ENTITY_LIST_HEADER
        content_rows += 1
        if is_header:
            continue
        if len(columns) != 5:
            raise ValueError(
                f"EntityLists row {line_index + 1} must contain exactly five columns"
            )
        if not columns[2] or not columns[2].isdigit():
            raise ValueError(
                f"EntityLists row {line_index + 1} has an invalid third column"
            )
        rows.append((columns[0], columns[1], int(columns[2]), columns[3], columns[4]))
    return rows


def entity_rows_installed_bytes(rows: list[tuple[str, str, int, str, str]]) -> int:
    return sum(row[2] for row in rows)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_hash_b64url(payload: bytes) -> str:
    """EntityLists hash 列:解压后单文件 SHA-256 的无填充 urlsafe base64(43 字符)。"""
    raw = hashlib.sha256(payload).digest()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


# ---------------------------------------------------------------- digest 缓存

def _load_digest_cache(cache_path: Path) -> dict:
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), dict):
            return data["entries"]
    except (OSError, ValueError):
        pass
    return {}


def _save_digest_cache(cache_path: Path, entries: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{cache_path.name}.", suffix=".tmp", dir=cache_path.parent
    )
    os.close(handle)
    Path(temporary).write_text(
        json.dumps({"version": 1, "entries": entries}, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(temporary, cache_path)


def resolve_digests(
    candidates: list[tuple[str, Path]],
    mode: str,
    cache_path: Path,
) -> dict[str, str]:
    """relpath → sha256。mode: cache(默认,增量哈希) / skip(占位,不读内容)。"""
    if mode == "skip":
        return {relative: DIGEST_PLACEHOLDER for relative, _ in candidates}
    entries = _load_digest_cache(cache_path)
    resolved: dict[str, str] = {}
    dirty = False
    for relative, absolute in candidates:
        stat = absolute.stat()
        cached = entries.get(relative)
        if (
            isinstance(cached, dict)
            and cached.get("size") == stat.st_size
            and cached.get("mtime_ns") == stat.st_mtime_ns
            and isinstance(cached.get("sha256"), str)
        ):
            resolved[relative] = cached["sha256"]
            continue
        digest = file_sha256(absolute)
        entries[relative] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": digest,
        }
        resolved[relative] = digest
        dirty = True
    if dirty:
        _save_digest_cache(cache_path, entries)
    return resolved


# ---------------------------------------------------------------- 链扫描

@dataclass
class ScanResult:
    archives: list[ArchiveInput]
    installed_bytes: int
    entity_lists_relative_path: str
    entity_rows: list[tuple[str, str, int, str, str]]
    entity_dir_name: str | None
    issues: list[Issue]
    stats: dict


def default_digest_cache_path(cdn_root: Path) -> Path:
    return cdn_root.parent / "dev-catalog-digest-cache.json"


def asset_patch_for(cdn_root: Path) -> Path | None:
    """asset-patch 覆盖层是本仓相对物,只在目标就是默认嵌套 CDN 根时纳入。

    对物化视图/外部部署等非默认根,canonical 集里已含(或不该含)覆盖层,
    再混入真实仓 asset-patch 只会制造 外根/旧名/序重复 噪声。
    """
    try:
        if Path(cdn_root).resolve() == CDN_ROOT.resolve():
            return ASSET_PATCH_ACTIVE
    except OSError:
        pass
    return None


FOREIGN_ROOT_PREFIX = "asset-patch/active/"


def archive_source_root_relative(
    archive: ArchiveInput,
    cdn_root: Path,
    asset_patch_active: Path | None,
) -> tuple[Path, str] | None:
    """Where an archive physically lives, as (root, path-relative-to-root).

    Foreign archives keep an ``asset-patch/active/…`` display path so reports,
    issues and catalogs stay readable, but they sit outside the CDN root.
    Joining that display path onto ``cdn_root`` yields a path that simply does
    not exist -- which is how materialization used to die with a bare
    FileNotFoundError from ``shutil.copy2`` on the first foreign archive.
    Returns None when the foreign root is unavailable; callers decide whether
    that is fatal.
    """
    if not archive.foreign_root:
        return cdn_root, archive.relative_path
    if (
        asset_patch_active is None
        or not archive.relative_path.startswith(FOREIGN_ROOT_PREFIX)
    ):
        return None
    return (
        Path(asset_patch_active),
        archive.relative_path.removeprefix(FOREIGN_ROOT_PREFIX),
    )


def archive_source_path(
    archive: ArchiveInput,
    cdn_root: Path,
    asset_patch_active: Path | None,
) -> Path | None:
    """Absolute source path of an archive, honouring the foreign root."""
    located = archive_source_root_relative(archive, cdn_root, asset_patch_active)
    if located is None:
        return None
    root, relative = located
    return root / relative


def scan_chain(
    cdn_root: Path = CDN_ROOT,
    asset_patch_active: Path | None = ASSET_PATCH_ACTIVE,
    *,
    digest_mode: str = "cache",
    digest_cache: Path | None = None,
) -> ScanResult:
    issues: list[Issue] = []
    stats: dict = {"directories": {}, "ignored": []}

    # —— EntityLists(dev 只认 EntityLists/;本地 dump 是 entities/) ——
    entity_dir_name: str | None = None
    for candidate in ("EntityLists", "entities"):
        if (cdn_root / candidate).is_dir():
            entity_dir_name = candidate
            break
    entity_rows: list[tuple[str, str, int, str, str]] = []
    installed_bytes = 0
    entity_lists_relative_path = "EntityLists/10939-android_medium.csv"
    if entity_dir_name is None:
        issues.append(Issue(
            "MISSING_PATH", "missing Android medium EntityLists CSV", "layout",
        ))
    else:
        if entity_dir_name != "EntityLists":
            issues.append(Issue(
                "DEV_LAYOUT_ENTITYLISTS",
                "EntityLists directory is named 'entities'; dev scanner only reads"
                " 'EntityLists' (rename or hardlink required)",
                "layout",
                relative_path=entity_dir_name,
            ))
        candidates = sorted(
            name for name in os.listdir(cdn_root / entity_dir_name)
            if ENTITY_CSV_RE.search(name)
            and (cdn_root / entity_dir_name / name).is_file()
        )
        if not candidates:
            issues.append(Issue(
                "MISSING_PATH", "missing Android medium EntityLists CSV", "layout",
            ))
        elif len(candidates) > 1:
            issues.append(Issue(
                "AMBIGUOUS_PATH",
                f"multiple Android medium EntityLists CSV files: {', '.join(candidates)}",
                "layout",
            ))
        else:
            entity_lists_relative_path = f"EntityLists/{candidates[0]}"
            try:
                content = (cdn_root / entity_dir_name / candidates[0]).read_text(
                    encoding="utf-8-sig"
                )
                entity_rows = parse_entity_list_rows(content)
                installed_bytes = entity_rows_installed_bytes(entity_rows)
            except ValueError as exc:
                issues.append(Issue(
                    "INVALID_INSTALLED_BYTES", str(exc), "layout",
                    relative_path=f"{entity_dir_name}/{candidates[0]}",
                ))

    # —— 归档目录扫描(dev 六目录;宽松名收进图但计 scanner 问题) ——
    pending: list[tuple[ArchiveInput, Path]] = []

    def scan_directory(
        directory: Path,
        kind: str,
        layer: str,
        relative_prefix: str,
        foreign_root: bool,
    ) -> None:
        if not directory.is_dir():
            return
        count = 0
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".zip"):
                continue
            absolute = directory / name
            if not absolute.is_file():
                continue
            dev_match = (
                FULL_NAME_RE.fullmatch(name) if kind == "full"
                else DIFF_NAME_RE.fullmatch(name)
            )
            legacy_match = None
            if dev_match is None:
                legacy_match = (
                    LEGACY_FULL_RE.fullmatch(name) if kind == "full"
                    else LEGACY_DIFF_RE.fullmatch(name)
                )
                if legacy_match is None:
                    issues.append(Issue(
                        "INVALID_ARCHIVE_PATH",
                        f"invalid archive name {relative_prefix}/{name}",
                        "scanner",
                        relative_path=f"{relative_prefix}/{name}",
                    ))
                    continue
                issues.append(Issue(
                    "DEV_INVALID_ARCHIVE_NAME",
                    f"archive name suffix is not hex; dev scanner rejects it: {name}",
                    "scanner",
                    relative_path=f"{relative_prefix}/{name}",
                ))
            match = dev_match or legacy_match
            assert match is not None
            if kind == "full":
                from_version: str | None = None
                to_version = match.group(1)
                order = int(match.group(2))
            else:
                from_version = match.group(1)
                to_version = match.group(2)
                order = int(match.group(3))
            if foreign_root:
                issues.append(Issue(
                    "DEV_FOREIGN_ROOT",
                    "archive lives outside the CDN root; dev scanner never reads"
                    f" {relative_prefix}/ (relocation into archive-common-diff required)",
                    "scanner",
                    relative_path=f"{relative_prefix}/{name}",
                ))
            pending.append((
                ArchiveInput(
                    kind=kind,
                    from_version=from_version,
                    to_version=to_version,
                    platform="android",
                    layer=layer,
                    order=order,
                    relative_path=f"{relative_prefix}/{name}",
                    compressed_bytes=absolute.stat().st_size,
                    sha256="",
                    dev_legal_name=dev_match is not None,
                    foreign_root=foreign_root,
                ),
                absolute,
            ))
            count += 1
        stats["directories"][relative_prefix] = count

    for directory_name, kind, layer in ARCHIVE_DIRECTORIES:
        scan_directory(cdn_root / directory_name, kind, layer, directory_name, False)
    if asset_patch_active is not None and asset_patch_active.is_dir():
        scan_directory(
            asset_patch_active, "diff", "common", "asset-patch/active", True
        )

    digest_cache = digest_cache or default_digest_cache_path(cdn_root)
    digests = resolve_digests(
        [(archive.relative_path, absolute) for archive, absolute in pending],
        digest_mode,
        digest_cache,
    )
    archives = []
    for archive, _absolute in pending:
        archive.sha256 = digests[archive.relative_path]
        archives.append(archive)
    stats["digest_mode"] = digest_mode
    stats["archives_total"] = len(archives)
    return ScanResult(
        archives=archives,
        installed_bytes=installed_bytes,
        entity_lists_relative_path=entity_lists_relative_path,
        entity_rows=entity_rows,
        entity_dir_name=entity_dir_name,
        issues=issues,
        stats=stats,
    )


# ---------------------------------------------------------------- 图校验(patch-graph.ts 移植)

def _scope_key(edge: CatalogEdge) -> tuple:
    return (edge.platform, edge.asset_size_kind)


def _edge_archive_metadata_key(edge: CatalogEdge) -> str:
    rows = sorted(
        [
            [a["relativePath"], a["compressedBytes"], a["sha256"], a["layer"], a["order"]]
            for a in edge.archives
        ],
        key=lambda row: json.dumps(row, ensure_ascii=False),
    )
    return json.dumps(rows, ensure_ascii=False)


def validate_patch_graph(
    edges: list[CatalogEdge], full_base_version: str
) -> list[Issue]:
    issues: list[Issue] = []
    exact_edges: dict[tuple, tuple[int, str]] = {}
    outgoing: dict[tuple, tuple[str, int]] = {}

    for edge_index, edge in enumerate(edges):
        exact_key = (
            *_scope_key(edge), edge.from_version or "<full>", edge.to_version,
        )
        existing_exact = exact_edges.get(exact_key)
        if existing_exact is not None:
            metadata_matches = existing_exact[1] == _edge_archive_metadata_key(edge)
            issues.append(Issue(
                "DUPLICATE_EDGE" if metadata_matches else "CONFLICTING_EDGE",
                f"edge {'duplicates' if metadata_matches else 'conflicts with'}"
                f" edge {existing_exact[0]}",
                "graph",
            ))
        else:
            exact_edges[exact_key] = (edge_index, _edge_archive_metadata_key(edge))

        from_key = (*_scope_key(edge), edge.from_version or "<full>")
        existing = outgoing.get(from_key)
        if existing is not None and existing[0] != edge.to_version:
            label = "full base" if edge.from_version is None else edge.from_version
            issues.append(Issue(
                "CONFLICTING_EDGE" if edge.from_version is None else "GRAPH_FORK",
                f"{label} points to both {existing[0]} and {edge.to_version}",
                "graph",
            ))
            issues.append(Issue(
                "CONFLICTING_EDGE", f"edge conflicts with edge {existing[1]}", "graph",
            ))
        elif existing is None:
            outgoing[from_key] = (edge.to_version, edge_index)

    _find_cycle_issues(edges, issues)
    _find_reachability_issues(edges, full_base_version, issues)
    return issues


def _find_cycle_issues(edges: list[CatalogEdge], issues: list[Issue]) -> None:
    by_scope: dict[tuple, list[tuple[int, CatalogEdge]]] = {}
    for edge_index, edge in enumerate(edges):
        if edge.from_version is None:
            continue
        by_scope.setdefault(_scope_key(edge), []).append((edge_index, edge))

    for scoped_edges in by_scope.values():
        adjacency: dict[str, list[tuple[str, int]]] = {}
        for edge_index, edge in scoped_edges:
            adjacency.setdefault(edge.from_version, []).append(
                (edge.to_version, edge_index)
            )
        visiting: set[str] = set()
        visited: set[str] = set()
        reported: set[int] = set()

        def visit(version: str) -> None:
            if version in visited:
                return
            visiting.add(version)
            for next_version, edge_index in adjacency.get(version, []):
                if next_version in visiting:
                    if edge_index not in reported:
                        issues.append(Issue(
                            "GRAPH_CYCLE",
                            f"patch graph cycle reaches {next_version}",
                            "graph",
                        ))
                        reported.add(edge_index)
                    continue
                visit(next_version)
            visiting.discard(version)
            visited.add(version)

        for version in list(adjacency):
            visit(version)


def _find_reachability_issues(
    edges: list[CatalogEdge], full_base_version: str, issues: list[Issue]
) -> None:
    scopes = {_scope_key(edge) for edge in edges}
    for scope in sorted(scopes):
        scoped = [
            (edge_index, edge)
            for edge_index, edge in enumerate(edges)
            if _scope_key(edge) == scope
        ]
        full_edges = [entry for entry in scoped if entry[1].from_version is None]
        if not any(edge.to_version == full_base_version for _, edge in full_edges):
            issues.append(Issue(
                "MISSING_PATH",
                f"missing full edge for base {full_base_version}",
                "graph",
            ))
        reachable = {full_base_version}
        changed = True
        while changed:
            changed = False
            for _, edge in scoped:
                if (
                    edge.from_version is not None
                    and edge.from_version in reachable
                    and edge.to_version not in reachable
                ):
                    reachable.add(edge.to_version)
                    changed = True
        for _, edge in scoped:
            if edge.from_version is not None and edge.from_version not in reachable:
                issues.append(Issue(
                    "MISSING_PATH",
                    f"diff edge {edge.from_version} -> {edge.to_version} is not"
                    f" reachable from full base {full_base_version}",
                    "graph",
                ))


# ---------------------------------------------------------------- Catalog 构建(catalog-builder.ts 移植)

def derive_target_version(edges: list[CatalogEdge], full_base_version: str) -> str:
    outgoing: dict[str, str] = {}
    for edge in edges:
        if (
            edge.platform == "android"
            and edge.asset_size_kind == "shortened"
            and edge.from_version is not None
        ):
            outgoing[edge.from_version] = edge.to_version
    target = full_base_version
    visited: set[str] = set()
    while target in outgoing and target not in visited:
        visited.add(target)
        target = outgoing[target]
    return target


def build_catalog(
    archives: list[ArchiveInput],
    installed_bytes: int,
    entity_lists_relative_path: str,
) -> tuple[dict, list[Issue]]:
    """catalog-builder.ts:buildCdnCatalog 移植;dev 有 issue 即 throw,
    这里始终返回尽力构建的 catalog + issues,由调用方决定是否阻断。"""
    issues: list[Issue] = []
    if not isinstance(installed_bytes, int) or installed_bytes < 0:
        issues.append(Issue(
            "INVALID_INSTALLED_BYTES",
            "installedBytes must be a non-negative safe integer",
            "archive",
        ))
    if not is_safe_relative_path(entity_lists_relative_path):
        issues.append(Issue(
            "INVALID_ARCHIVE_PATH",
            "entityListsRelativePath must be a normalized relative path",
            "archive",
            relative_path=entity_lists_relative_path,
        ))

    ordered = sorted(
        archives,
        key=lambda archive: (
            archive.relative_path,
            json.dumps(archive.metadata_key(), ensure_ascii=False, default=str),
        ),
    )
    paths: dict[str, ArchiveInput] = {}
    edge_groups: dict[tuple, list[ArchiveInput]] = {}
    orders: dict[tuple, int] = {}

    for archive_index, archive in enumerate(ordered):
        if archive.platform != "android":
            issues.append(Issue(
                "UNSUPPORTED_PLATFORM",
                f"unsupported platform {archive.platform}",
                "archive", relative_path=archive.relative_path,
            ))
        bad_version = (
            parse_version(archive.to_version) is None
            or (archive.kind == "diff" and (
                not isinstance(archive.from_version, str)
                or parse_version(archive.from_version) is None
            ))
            or (archive.kind == "full" and archive.from_version is not None)
            or archive.kind not in ("full", "diff")
        )
        if bad_version:
            issues.append(Issue(
                "INVALID_VERSION",
                f"archive {archive.relative_path} has invalid edge versions",
                "archive", relative_path=archive.relative_path,
            ))
        if (
            archive.kind == "diff"
            and isinstance(archive.from_version, str)
            and parse_version(archive.from_version) is not None
            and parse_version(archive.to_version) is not None
            and compare_versions(archive.from_version, archive.to_version) >= 0
        ):
            issues.append(Issue(
                "INVALID_VERSION",
                f"diff edge {archive.from_version} -> {archive.to_version} must increase",
                "archive", relative_path=archive.relative_path,
            ))
        if (
            not is_safe_relative_path(archive.relative_path)
            or not archive.relative_path.endswith(".zip")
        ):
            issues.append(Issue(
                "INVALID_ARCHIVE_PATH",
                f"invalid archive path {archive.relative_path}",
                "archive", relative_path=archive.relative_path,
            ))
        if not isinstance(archive.compressed_bytes, int) or archive.compressed_bytes < 0:
            issues.append(Issue(
                "INVALID_COMPRESSED_BYTES",
                f"archive {archive.relative_path} has invalid compressedBytes",
                "archive", relative_path=archive.relative_path,
            ))
        if not SHA256_HEX_RE.fullmatch(archive.sha256 or ""):
            issues.append(Issue(
                "INVALID_SHA256",
                f"archive {archive.relative_path} has invalid SHA256",
                "archive", relative_path=archive.relative_path,
            ))
        if not isinstance(archive.order, int) or archive.order <= 0:
            issues.append(Issue(
                "INVALID_ARCHIVE_ORDER",
                f"archive {archive.relative_path} has invalid order",
                "archive", relative_path=archive.relative_path,
            ))
        if archive.layer not in LAYER_ORDER:
            issues.append(Issue(
                "INVALID_ARCHIVE_PATH",
                f"archive {archive.relative_path} has invalid layer",
                "archive", relative_path=archive.relative_path,
            ))

        previous = paths.get(archive.relative_path)
        if previous is not None:
            issues.append(Issue(
                "DUPLICATE_ARCHIVE_PATH"
                if previous.metadata_key() == archive.metadata_key()
                else "CONFLICTING_ARCHIVE_PATH",
                f"archive path {archive.relative_path} appears more than once",
                "archive", relative_path=archive.relative_path,
            ))
        else:
            paths[archive.relative_path] = archive

        group_key = archive.edge_group_key()
        edge_groups.setdefault(group_key, []).append(archive)

        order_key = (*group_key, archive.layer, archive.order)
        if order_key in orders:
            issues.append(Issue(
                "DUPLICATE_ARCHIVE_ORDER",
                f"archive order duplicates archive {orders[order_key]}",
                "archive", relative_path=archive.relative_path,
            ))
        else:
            orders[order_key] = archive_index

    for group in edge_groups.values():
        layers = {archive.layer for archive in group}
        for required_layer in ("common", "quality", "platform"):
            if required_layer not in layers:
                representative = group[0]
                issues.append(Issue(
                    "MISSING_ARCHIVE_LAYER",
                    f"{representative.kind} edge"
                    f" {representative.from_version or 'full'} ->"
                    f" {representative.to_version} is missing {required_layer}",
                    "archive", relative_path=representative.relative_path,
                ))

    full_base_versions = sorted(
        {a.to_version for a in ordered if a.kind == "full"},
        key=lambda version: parse_version(version) or (0, 0, 0),
    )
    if not full_base_versions:
        issues.append(Issue(
            "MISSING_PATH", "catalog has no full base archive", "graph",
        ))
    elif len(full_base_versions) > 1:
        issues.append(Issue(
            "CONFLICTING_EDGE",
            f"catalog has multiple full base versions: {', '.join(full_base_versions)}",
            "graph",
        ))
    full_base_version = full_base_versions[0] if full_base_versions else "0.0.0"

    edges: list[CatalogEdge] = []
    for group in edge_groups.values():
        representative = group[0]
        catalog_archives = sorted(
            (
                {
                    "relativePath": archive.relative_path,
                    "compressedBytes": archive.compressed_bytes,
                    "sha256": archive.sha256,
                    "layer": archive.layer,
                    "order": archive.order,
                }
                for archive in group
            ),
            key=lambda a: (LAYER_ORDER.get(a["layer"], 9), a["order"], a["relativePath"]),
        )
        for asset_size_kind in ASSET_SIZE_KINDS:
            edges.append(CatalogEdge(
                from_version=(
                    None if representative.kind == "full"
                    else representative.from_version
                ),
                to_version=representative.to_version,
                platform=representative.platform,
                asset_size_kind=asset_size_kind,
                archives=catalog_archives,
            ))
    edges.sort(key=lambda edge: (
        edge.platform,
        ASSET_SIZE_KINDS.index(edge.asset_size_kind),
        edge.from_version is not None,
        parse_version(edge.from_version or edge.to_version) or (0, 0, 0),
        parse_version(edge.to_version) or (0, 0, 0),
    ))

    # 每层 order 必须从 1 连续(仅统计合法正整数 order)
    for edge in edges:
        for layer in sorted({a["layer"] for a in edge.archives}):
            layer_orders = sorted({
                a["order"] for a in edge.archives
                if a["layer"] == layer and isinstance(a["order"], int) and a["order"] > 0
            })
            if any(order != index + 1 for index, order in enumerate(layer_orders)):
                issues.append(Issue(
                    "NON_CONTIGUOUS_ARCHIVE_ORDER",
                    f"{'full' if edge.from_version is None else 'diff'} edge"
                    f" {edge.from_version or 'full'} -> {edge.to_version} platform"
                    f" {edge.platform} mode {edge.asset_size_kind} layer {layer}"
                    " must use contiguous archive orders starting at 1",
                    "archive",
                ))

    issues.extend(validate_patch_graph(edges, full_base_version))

    catalog = {
        "schemaVersion": 1,
        "fullBaseVersion": full_base_version,
        "targetVersion": derive_target_version(edges, full_base_version),
        "installedBytes": installed_bytes,
        "entityListsRelativePath": entity_lists_relative_path,
        "edges": [
            {
                "fromVersion": edge.from_version,
                "toVersion": edge.to_version,
                "platform": edge.platform,
                "assetSizeKind": edge.asset_size_kind,
                "archives": edge.archives,
            }
            for edge in edges
        ],
    }
    return catalog, issues


# ---------------------------------------------------------------- 规范化(仅作用于发射产物,不动磁盘)

def canonicalize_archives(
    archives: list[ArchiveInput],
) -> tuple[list[ArchiveInput], dict]:
    """把物理扫描结果整理成 dev 可校验的 catalog 输入:

    - 同(边,层)内 sha256 相同的重复包只保留一份(charbridge 硬链桥与 charpkg
      原包同边同序,内容相同,无损去重);
    - 同(边,层)内容不同的包按"asset-patch 覆盖层最后解压、后写胜"的现网语义
      重排 order(common 根在前,patch 根在后),保证每层 1..n 连续;
    - 只改 catalog 元数据,不重命名/移动任何磁盘文件——运行时接收路径零影响。

    digest 为占位值(skip 模式)时跳过内容去重,只做重排。
    """
    groups: dict[tuple, list[ArchiveInput]] = {}
    for archive in archives:
        groups.setdefault((*archive.edge_group_key(), archive.layer), []).append(archive)

    kept: list[ArchiveInput] = []
    stats = {"deduplicated": 0, "reordered": 0}
    for key in sorted(groups, key=lambda k: json.dumps(k, default=str)):
        group = sorted(
            groups[key],
            key=lambda a: (a.foreign_root, a.order, a.relative_path),
        )
        seen_digests: set[str] = set()
        selected: list[ArchiveInput] = []
        for archive in group:
            if (
                archive.sha256 != DIGEST_PLACEHOLDER
                and archive.sha256 in seen_digests
            ):
                stats["deduplicated"] += 1
                continue
            seen_digests.add(archive.sha256)
            selected.append(archive)
        for index, archive in enumerate(selected, start=1):
            if archive.order != index:
                stats["reordered"] += 1
                archive.order = index
            kept.append(archive)
    return kept, stats


# ---------------------------------------------------------------- EntityLists 回填与合并

def backfill_entity_rows(
    archives: list[ArchiveInput],
    cdn_root: Path,
    asset_patch_active: Path | None = ASSET_PATCH_ACTIVE,
) -> tuple[dict[str, tuple[str, str, int, str, str]], list[Issue]]:
    """从超出官方目标(1.4.54)的 diff 包读出内部文件行:path→(path,ver,size,hash,tag)。"""
    issues: list[Issue] = []
    rows: dict[str, tuple[str, str, int, str, str]] = {}
    mod_archives = sorted(
        (
            archive for archive in archives
            if archive.kind == "diff"
            and compare_versions(archive.to_version, OFFICIAL_TARGET) > 0
        ),
        key=lambda archive: (
            parse_version(archive.to_version) or (0, 0, 0), archive.relative_path,
        ),
    )
    for archive in mod_archives:
        absolute = archive_source_path(archive, cdn_root, asset_patch_active)
        if absolute is None:
            issues.append(Issue(
                "DEV_ENTITY_ROW_SKIPPED",
                "foreign archive source root is unavailable",
                "scanner", relative_path=archive.relative_path,
            ))
            continue
        try:
            with zipfile.ZipFile(absolute) as bundle:
                for info in bundle.infolist():
                    if info.is_dir() or info.filename == ".empty":
                        continue
                    member = info.filename
                    match = UPLOAD_MEMBER_RE.fullmatch(member)
                    if match is None:
                        issues.append(Issue(
                            "DEV_ENTITY_ROW_SKIPPED",
                            f"zip member is not an upload path: {member}",
                            "scanner", relative_path=archive.relative_path,
                        ))
                        continue
                    payload = bundle.read(info)
                    existing = rows.get(member)
                    if (
                        existing is not None
                        and compare_versions(existing[1], archive.to_version) > 0
                    ):
                        continue
                    rows[member] = (
                        member,
                        archive.to_version,
                        len(payload),
                        content_hash_b64url(payload),
                        MEMBER_PREFIX_TO_CSV_TAG[match.group(1)],
                    )
        except (OSError, zipfile.BadZipFile) as exc:
            issues.append(Issue(
                "DEV_ENTITY_ROW_SKIPPED",
                f"unreadable archive: {exc}",
                "scanner", relative_path=archive.relative_path,
            ))
    return rows, issues


def merge_entity_rows(
    official_rows: list[tuple[str, str, int, str, str]],
    mod_rows: dict[str, tuple[str, str, int, str, str]],
) -> list[tuple[str, str, int, str, str]]:
    """官方行保序;被 mod 覆盖的路径原位替换;新路径按(版本,路径)追加。"""
    merged: list[tuple[str, str, int, str, str]] = []
    consumed: set[str] = set()
    for row in official_rows:
        override = mod_rows.get(row[0])
        if override is not None:
            merged.append(override)
            consumed.add(row[0])
        else:
            merged.append(row)
    additions = sorted(
        (row for path, row in mod_rows.items() if path not in consumed),
        key=lambda row: (parse_version(row[1]) or (0, 0, 0), row[0]),
    )
    merged.extend(additions)
    return merged


def render_entity_csv(rows: list[tuple[str, str, int, str, str]]) -> str:
    return "\n".join(
        f"{path},{version},{size},{digest},{tag}"
        for path, version, size, digest, tag in rows
    ) + "\n"


# ---------------------------------------------------------------- emit / audit / heal

def emit_dev_catalog(
    cdn_root: Path = CDN_ROOT,
    asset_patch_active: Path | None = ASSET_PATCH_ACTIVE,
    out_dir: Path | None = None,
    *,
    digest_mode: str = "cache",
    allow_issues: bool = False,
    canonicalize: bool = True,
) -> tuple[Path | None, list[Issue], dict]:
    scan = scan_chain(
        cdn_root, asset_patch_active, digest_mode=digest_mode,
    )
    archives = scan.archives
    canonical_stats: dict = {}
    if canonicalize:
        archives, canonical_stats = canonicalize_archives(archives)
    mod_rows, row_issues = backfill_entity_rows(
        archives, cdn_root, asset_patch_active
    )
    merged_rows = merge_entity_rows(scan.entity_rows, mod_rows)
    installed_bytes = entity_rows_installed_bytes(merged_rows)
    catalog, catalog_issues = build_catalog(
        archives, installed_bytes, scan.entity_lists_relative_path,
    )
    issues = scan.issues + row_issues + catalog_issues
    summary = {
        "archives": len(archives),
        **{f"canonical_{key}": value for key, value in canonical_stats.items()},
        "officialInstalledBytes": scan.installed_bytes,
        "mergedInstalledBytes": installed_bytes,
        "modRows": len(mod_rows),
        "mergedRows": len(merged_rows),
        "issues": len(issues),
    }
    blocking = [issue for issue in issues if issue.code != "DEV_ENTITY_ROW_SKIPPED"]
    if blocking and not allow_issues:
        return None, issues, summary

    out_dir = out_dir or (cdn_root / "dev-catalog")
    (out_dir / "EntityLists").mkdir(parents=True, exist_ok=True)
    csv_name = Path(scan.entity_lists_relative_path).name
    csv_path = out_dir / "EntityLists" / csv_name
    csv_path.write_text(render_entity_csv(merged_rows), encoding="utf-8", newline="\n")

    archives_json = [
        {
            "kind": archive.kind,
            "fromVersion": archive.from_version,
            "toVersion": archive.to_version,
            "platform": archive.platform,
            "layer": archive.layer,
            "order": archive.order,
            "relativePath": archive.relative_path,
            "compressedBytes": archive.compressed_bytes,
            "sha256": archive.sha256,
        }
        for archive in sorted(
            archives,
            key=lambda a: (
                a.kind != "full",
                parse_version(a.from_version or a.to_version) or (0, 0, 0),
                parse_version(a.to_version) or (0, 0, 0),
                LAYER_ORDER.get(a.layer, 9),
                a.order,
                a.relative_path,
            ),
        )
    ]
    target = catalog["targetVersion"]
    manifest = {
        "schemaVersion": 1,
        "baseline": BASELINE_LABEL,
        "catalogInput": {
            "archives": archives_json,
            "installedBytes": installed_bytes,
            "entityListsRelativePath": f"EntityLists/{csv_name}",
        },
        "entityLists": {
            "relativePath": f"EntityLists/{csv_name}",
            "compressedBytes": csv_path.stat().st_size,
            "sha256": file_sha256(csv_path),
        },
    }
    manifest_path = out_dir / f"catalog-cn-{target}.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    report_path = out_dir / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "targetVersion": target,
                "issues": [issue.__dict__ for issue in issues],
            },
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    summary["manifest"] = str(manifest_path)
    return manifest_path, issues, summary


def heal_missing_layers(
    cdn_root: Path = CDN_ROOT,
    asset_patch_active: Path | None = ASSET_PATCH_ACTIVE,
    *,
    apply: bool = False,
    digest_mode: str = "skip",
) -> list[str]:
    """给缺 quality/platform 层的 diff 边补官方样式 .empty 占位包(默认只列出)。"""
    scan = scan_chain(cdn_root, asset_patch_active, digest_mode=digest_mode)
    groups: dict[tuple, set[str]] = {}
    for archive in scan.archives:
        if archive.kind != "diff":
            continue
        key = (archive.from_version, archive.to_version)
        groups.setdefault(key, set()).add(archive.layer)
    layer_directories = {"quality": "archive-medium-diff", "platform": "archive-android-diff",
                         "common": "archive-common-diff"}
    planned: list[str] = []
    for (from_version, to_version), layers in sorted(
        groups.items(), key=lambda item: parse_version(item[0][1]) or (0, 0, 0),
    ):
        for layer in ("common", "quality", "platform"):
            if layer in layers:
                continue
            suffix = hashlib.sha256(
                f"{from_version}->{to_version}:{layer}".encode("utf-8")
            ).hexdigest()[:8]
            directory = cdn_root / layer_directories[layer]
            name = f"pinball-{from_version}-{to_version}-1-{suffix}.zip"
            planned.append(f"{layer_directories[layer]}/{name}")
            if apply:
                directory.mkdir(parents=True, exist_ok=True)
                final = directory / name
                if final.exists():
                    continue
                handle, temporary = tempfile.mkstemp(
                    prefix=f".{name}.", suffix=".tmp", dir=directory,
                )
                os.close(handle)
                with zipfile.ZipFile(
                    Path(temporary), "w", zipfile.ZIP_STORED
                ) as bundle:
                    bundle.writestr(".empty", b"\n")
                os.replace(temporary, final)
    return planned


# ---------------------------------------------------------------- 外根迁入(M1.2)

def relocate_foreign_archives(
    cdn_root: Path = CDN_ROOT,
    asset_patch_active: Path | None = ASSET_PATCH_ACTIVE,
    *,
    apply: bool = False,
) -> tuple[list[dict], list[Issue]]:
    """把 CDN 根外(asset-patch/active)的包以 dev 合法名硬链/复制进 archive-common-diff。

    - 保留原件:运行时接收路径(含覆盖层"后解压胜"语义)零改动;
    - 副本命名 pinball-<from>-<to>-<N>-<hex8>.zip,N=该边现有最大序号+1,
      字典序落在原 common 包之后、patch 原件之前,现网解压顺序不变;
    - hex8=sha256("relocate:"+原文件名)[:8],确定性→幂等(重跑跳过已存在同内容副本);
    - 迁入后 emit 的规范化去重会自动用"根内副本"替换 catalog 里的外根原件,
      canonical manifest 即全部可从 CDN 根 stat/供给。
    """
    actions: list[dict] = []
    issues: list[Issue] = []
    if asset_patch_active is None or not asset_patch_active.is_dir():
        return actions, issues
    target_dir = cdn_root / "archive-common-diff"

    max_orders: dict[tuple[str, str], int] = {}
    by_suffix: dict[tuple[str, str, str], str] = {}
    if target_dir.is_dir():
        for name in os.listdir(target_dir):
            match = LEGACY_DIFF_RE.fullmatch(name)
            if match is None:
                continue
            key = (match.group(1), match.group(2))
            max_orders[key] = max(max_orders.get(key, 0), int(match.group(3)))
            by_suffix[(*key, match.group(4))] = name

    def _sort_key(name: str) -> tuple:
        match = LEGACY_DIFF_RE.fullmatch(name)
        to_version = match.group(2) if match else "0.0.0"
        return (parse_version(to_version) or (0, 0, 0), name)

    foreign = sorted(
        (name for name in os.listdir(asset_patch_active)
         if name.endswith(".zip") and (asset_patch_active / name).is_file()),
        key=_sort_key,
    )
    for name in foreign:
        match = LEGACY_DIFF_RE.fullmatch(name)
        if match is None:
            issues.append(Issue(
                "INVALID_ARCHIVE_PATH",
                f"foreign archive name is not a diff name: {name}",
                "scanner", relative_path=f"asset-patch/active/{name}",
            ))
            continue
        from_version, to_version = match.group(1), match.group(2)
        key = (from_version, to_version)
        suffix = hashlib.sha256(f"relocate:{name}".encode("utf-8")).hexdigest()[:8]
        source = asset_patch_active / name
        source_size = source.stat().st_size
        already = by_suffix.get((*key, suffix))
        if already is not None:
            # 确定性后缀命中=此原件已迁入过(幂等,不看序号)
            target = target_dir / already
            if (
                target.stat().st_size == source_size
                and file_sha256(target) == file_sha256(source)
            ):
                actions.append({
                    "action": "exists", "source": f"asset-patch/active/{name}",
                    "target": f"archive-common-diff/{already}", "bytes": source_size,
                })
            else:
                issues.append(Issue(
                    "CONFLICTING_ARCHIVE_PATH",
                    f"relocation target exists with different content: {already}",
                    "scanner", relative_path=f"archive-common-diff/{already}",
                ))
            continue
        order = max_orders.get(key, 0) + 1
        max_orders[key] = order
        target_name = f"pinball-{from_version}-{to_version}-{order}-{suffix}.zip"
        target = target_dir / target_name
        if order >= 10:
            issues.append(Issue(
                "DEV_RELOCATE_ORDER_HIGH",
                f"edge {from_version}->{to_version} order {order} >= 10:"
                " lexical extraction order on the legacy server may interleave",
                "scanner", relative_path=f"archive-common-diff/{target_name}",
            ))
        if target.exists():
            same = (
                target.stat().st_size == source_size
                and file_sha256(target) == file_sha256(source)
            )
            if same:
                actions.append({
                    "action": "exists", "source": f"asset-patch/active/{name}",
                    "target": f"archive-common-diff/{target_name}", "bytes": source_size,
                })
                continue
            issues.append(Issue(
                "CONFLICTING_ARCHIVE_PATH",
                f"relocation target exists with different content: {target_name}",
                "scanner", relative_path=f"archive-common-diff/{target_name}",
            ))
            continue
        method = "plan"
        if apply:
            target_dir.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source, target)
                method = "hardlink"
            except OSError:
                import shutil
                shutil.copy2(source, target)
                method = "copy"
            if target.stat().st_size != source_size:
                issues.append(Issue(
                    "UNSTABLE_ARCHIVE_SNAPSHOT",
                    f"relocated copy size mismatch: {target_name}",
                    "scanner", relative_path=f"archive-common-diff/{target_name}",
                ))
        actions.append({
            "action": method, "source": f"asset-patch/active/{name}",
            "target": f"archive-common-diff/{target_name}", "bytes": source_size,
        })
    if apply and actions:
        receipt_path = cdn_root / "dev-catalog" / "relocate-receipt.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        existing: list = []
        if receipt_path.exists():
            try:
                existing = json.loads(receipt_path.read_text(encoding="utf-8"))
            except ValueError:
                existing = []
        known = {entry.get("target") for entry in existing if isinstance(entry, dict)}
        for action in actions:
            if action["target"] not in known:
                existing.append(action)
        receipt_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
    return actions, issues


# ---------------------------------------------------------------- 合规视图物化(F1/新收方干净链)

def materialize_dev_view(
    cdn_root: Path = CDN_ROOT,
    asset_patch_active: Path | None = ASSET_PATCH_ACTIVE,
    out_parent: Path | None = None,
    *,
    digest_mode: str = "cache",
) -> tuple[Path, dict, list[Issue]]:
    """把 canonical 链物化成 dev 物理扫描器可直接消费的 CDN 视图。

    - 同卷硬链(零磁盘成本),对现网链零改动零重命名;
    - 旧命名(非 hex 后缀)归档以合规名 pinball-<from>-<to>-<order>-<hex8>.zip
      硬链存在于视图中,hex8=sha256(原相对路径)[:8],order=canonical 序号
      (文件名 N 与 catalog order 保持一致,保证 dev 扫描重建出同一 catalog);
    - EntityLists/ 放合并 CSV(dev 扫描器硬性输入;现网 entities/ 不动,files_list 雷不触发);
    - 视图同时就是"新收方干净链"的分发形态(物理扫描路线可用)。

    返回 (视图 cn 根, 统计, 问题)。CDN_DIR 应指向视图 cn 根的父目录。
    """
    import shutil

    scan = scan_chain(cdn_root, asset_patch_active, digest_mode=digest_mode)
    archives, canonical_stats = canonicalize_archives(scan.archives)
    mod_rows, row_issues = backfill_entity_rows(
        archives, cdn_root, asset_patch_active
    )
    merged_rows = merge_entity_rows(scan.entity_rows, mod_rows)
    issues = scan.issues + row_issues

    out_parent = out_parent or (cdn_root.parent / "dev-view")
    view_root = out_parent / "cn"
    stats: dict = {
        "linked": 0, "renamed": 0, "copied": 0, "missing": 0,
        **{f"canonical_{key}": value for key, value in canonical_stats.items()},
    }

    for archive in archives:
        source = archive_source_path(archive, cdn_root, asset_patch_active)
        if source is None or not source.is_file():
            issues.append(Issue(
                "MATERIALIZE_SOURCE_MISSING",
                "archive source is unreachable; view omits it",
                "materialize",
                relative_path=archive.relative_path,
            ))
            stats["missing"] += 1
            continue
        # Derive the layer directory from the archive's own layer/kind rather
        # than from its display path.  A foreign archive's display path starts
        # with `asset-patch/active/`, so splitting it put the file in a bogus
        # `asset-patch/` directory inside the view -- present on disk, invisible
        # to the scanner, and the edge then looked like it was missing its
        # common layer.
        directory = ARCHIVE_DIRECTORY_BY_LAYER[(archive.kind, archive.layer)]
        name = archive.relative_path.rsplit("/", 1)[1]
        if archive.kind == "full":
            legal = FULL_NAME_RE.fullmatch(name) is not None
        else:
            legal = DIFF_NAME_RE.fullmatch(name) is not None
        if not legal:
            suffix = hashlib.sha256(
                archive.relative_path.encode("utf-8")
            ).hexdigest()[:8]
            if archive.kind == "full":
                name = f"pinball-{archive.to_version}-{archive.order}-{suffix}.zip"
            else:
                name = (
                    f"pinball-{archive.from_version}-{archive.to_version}"
                    f"-{archive.order}-{suffix}.zip"
                )
            stats["renamed"] += 1
        target = view_root / directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.stat().st_size == archive.compressed_bytes:
                continue
            target.unlink()
        try:
            os.link(source, target)
            stats["linked"] += 1
        except OSError:
            shutil.copy2(source, target)
            stats["copied"] += 1

    entity_dir = view_root / "EntityLists"
    entity_dir.mkdir(parents=True, exist_ok=True)
    csv_name = Path(scan.entity_lists_relative_path).name
    (entity_dir / csv_name).write_text(
        render_entity_csv(merged_rows), encoding="utf-8", newline="\n",
    )
    stats["entityRows"] = len(merged_rows)
    stats["archives"] = len(archives)
    return view_root, stats, issues


def cmd_materialize(args: argparse.Namespace) -> int:
    view_root, stats, issues = materialize_dev_view(
        Path(args.cdn_root),
        asset_patch_for(Path(args.cdn_root)),
        Path(args.out) if args.out else None,
        digest_mode=args.digest,
    )
    blocking = [i for i in issues if i.category in ("layout",)
                and i.code == "MISSING_PATH"]
    _print_issue_groups(issues)
    for key, value in stats.items():
        print(f"{key}: {value}")
    print(f"[OK] dev 物理扫描视图: {view_root}")
    print(f"用法: CDN_DIR={view_root.parent} npm run content:sync")
    return 1 if blocking else 0


# ---------------------------------------------------------------- 分享包导出(M2.1)

# 显式例外的自动检测:命中这些逻辑表的包=需要服务端配套动作(定位文档 §0:
# 需要服务端/客户端配套的内容必须显式声明,不伪装成纯 CDN 包)。
# 成员路径=SHA1(逻辑路径+盐),可反查:core.sha1_path(logical)。
RESTART_SENSITIVE_LOGICALS = {
    "master/character/character.orderedmap":
        "角色表(服务端邮件白名单启动定格,拉新角色必须重启服务端)",
    "master/character/character_text.orderedmap":
        "角色文本表(名称/称号与服务端派生表联动)",
}


def _detect_pack_requirements_from_paths(paths: list[Path]) -> tuple[bool, list[str]]:
    """扫描归档成员哈希,反查是否命中重启敏感表。只读 namelist,不解压。"""
    import wf_mod_tool as core

    sensitive = {
        core.sha1_path(logical): reason
        for logical, reason in RESTART_SENSITIVE_LOGICALS.items()
    }
    reasons: list[str] = []
    seen: set[str] = set()
    for path in paths:
        try:
            with zipfile.ZipFile(path) as bundle:
                names = bundle.namelist()
        except (OSError, zipfile.BadZipFile):
            continue
        for member in names:
            if UPLOAD_MEMBER_RE.fullmatch(member) is None:
                continue
            parts = member.split("/")
            reason = sensitive.get(parts[-2] + parts[-1])
            if reason and reason not in seen:
                seen.add(reason)
                reasons.append(reason)
    return bool(reasons), reasons


def detect_pack_requirements(
    selected: list[ArchiveInput], cdn_root: Path,
) -> tuple[bool, list[str]]:
    """Legacy boundary: resolve selected archives beneath the single CDN root."""
    return _detect_pack_requirements_from_paths([
        cdn_root / archive.relative_path for archive in selected
    ])


SHARE_README_TEMPLATE = """WF mod 分享包  {name}
生成时间: {generated}
适用范围: 链尾已达 {since} 的服务端(官方 1.4.54 dump 满足 since=1.4.54 的包)
内容: {edge_count} 条版本边({since} -> {tail}),{file_count} 个归档,共 {total_bytes} 字节

== 依赖声明(requires.json 机器可读) ==
{requires_text}

== main 服务端(运行时接收) ==
1. 把 archive-*-diff/ 三个目录解压合并到你的 CDN 根(…/cn/)下;
2. 服务端动态扫描,客户端重启游戏即自动拉取;
3. 若包含新角色,需重启一次服务端(邮件表启动定格)。

== dev 服务端(启动前编译) ==
1. 同上解压归档目录;
2. 把 dev-catalog/EntityLists/ 拷到 CDN 根成为 …/cn/EntityLists/
   (main 服务端请勿做这一步:会翻转其 files_list 行为);
3. dev-catalog/catalog-cn-{tail}.json 为整链候选 manifest,
   对应"官方 dump + 完整 mod 链到 {tail}"的状态,供校验/评审/兜底路线使用;
4. 用受支持入口重启(启动同步会自动重建 Release)。

注意: 本包不含官方 1.4.0-1.4.54 基线;增量包只对链尾恰好衔接的服务端生效。
"""


def export_share_pack(
    cdn_root: Path = CDN_ROOT,
    asset_patch_active: Path | None = ASSET_PATCH_ACTIVE,
    out_dir: Path | None = None,
    *,
    since: str = OFFICIAL_TARGET,
    digest_mode: str = "cache",
    min_server: str | None = None,
    server_features: tuple[str, ...] = (),
    client_patches: tuple[str, ...] = (),
) -> tuple[Path | None, dict, list[Issue]]:
    """把 since 之后的 mod 链(canonical 视图)打成收方解压即用的分享目录。

    - 归档按 relativePath 硬链/复制(canonical=桥包已去重、外根已换根内副本);
    - dev 材料(整链候选 manifest + 合并 EntityLists)收进 dev-catalog/ 子目录,
      避免 main 收方误落 EntityLists/ 到 CDN 根(files_list 翻转雷);
    - 附 说明.txt(两条路径的启用步骤 + 衔接前提)。
    """
    if parse_version(since) is None:
        raise ValueError(f"invalid --since version: {since}")
    scan = scan_chain(cdn_root, asset_patch_active, digest_mode=digest_mode)
    archives, _stats = canonicalize_archives(scan.archives)
    selected = [
        archive for archive in archives
        if archive.kind == "diff" and compare_versions(archive.to_version, since) > 0
    ]
    issues = list(scan.issues)
    stats: dict = {"since": since, "files": 0, "bytes": 0, "edges": 0}
    if not selected:
        return None, stats, issues

    edges = sorted(
        {(a.from_version, a.to_version) for a in selected},
        key=lambda edge: parse_version(edge[1]) or (0, 0, 0),
    )
    tail = edges[-1][1]
    name = f"wfshare-{since}-to-{tail}"
    out_dir = (out_dir or (cdn_root.parent / "share")) / name
    out_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    for archive in selected:
        source = cdn_root / archive.relative_path
        target = out_dir / archive.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
        stats["files"] += 1
        stats["bytes"] += archive.compressed_bytes

    # dev 材料:复用 emit 单一代码路径,保证与 CDN 根侧产物一致
    manifest_path, emit_issues, _summary = emit_dev_catalog(
        cdn_root, asset_patch_active,
        digest_mode=digest_mode, allow_issues=True,
    )
    issues += [i for i in emit_issues if i not in issues]
    pack_dev = out_dir / "dev-catalog"
    (pack_dev / "EntityLists").mkdir(parents=True, exist_ok=True)
    if manifest_path is not None:
        shutil.copy2(manifest_path, pack_dev / manifest_path.name)
        source_csv_dir = manifest_path.parent / "EntityLists"
        for csv_file in source_csv_dir.glob("*.csv"):
            shutil.copy2(csv_file, pack_dev / "EntityLists" / csv_file.name)

    stats["edges"] = len(edges)
    stats["tail"] = tail

    # 依赖声明:自动检测(重启敏感表)+ 手动声明(模式类服务端逻辑/客户端补丁)
    restart, restart_reasons = detect_pack_requirements(selected, cdn_root)
    requires = {
        "schemaVersion": 2,
        # 本通道是整 zip 原样搬运,产物必然带发包方的个人增强(平衡总包/白虎重做等);
        # 去增强的 content-only 变体走 wf_share_variant.py,那边会把 enhancement 写成 false。
        "pack": {"variant": "full", "since": since, "tail": tail, "edges": len(edges)},
        "enhancement": True,
        "enhancementDetail": {
            "note": "整链原样打包,含发包方自服的个人增强;"
                    "需要官方原值的收方请索取 content-only 变体"
                    "(mod-tools/wf_share_variant.py)",
        },
        "requires": {
            "serverRestart": restart,
            "restartReasons": restart_reasons,
            "minServerVersion": min_server,
            "serverFeatures": list(server_features),
            "clientPatches": list(client_patches),
        },
    }
    if restart:
        requires["requires"]["serverDataNote"] = (
            "角色类内容的服务端派生表(assets/character.json 等)不在本包内;"
            "收方服务端需同步拉新(重启)或用 mod-admin 热载"
        )
    (out_dir / "requires.json").write_text(
        json.dumps(requires, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    stats["serverRestart"] = restart

    requires_lines = [
        f"- 需重启服务端: {'是' if restart else '否'}"
        + (f"({';'.join(restart_reasons)})" if restart_reasons else ""),
    ]
    if min_server:
        requires_lines.append(f"- 最低服务端版本: {min_server}")
    if server_features:
        requires_lines.append(f"- 需要服务端功能: {', '.join(server_features)}")
    if client_patches:
        requires_lines.append(f"- 需要客户端补丁: {', '.join(client_patches)}")
    if len(requires_lines) == 1 and not restart:
        requires_lines.append("- 纯 CDN 内容包,无额外依赖")
    requires_lines.append(
        "- 变体: full(含发包方个人增强;要官方原值请索取 content-only 变体)")

    (out_dir / "说明.txt").write_text(
        SHARE_README_TEMPLATE.format(
            name=name,
            generated=__import__("time").strftime("%Y-%m-%d %H:%M"),
            since=since,
            tail=tail,
            edge_count=len(edges),
            file_count=stats["files"],
            total_bytes=stats["bytes"],
            requires_text="\n".join(requires_lines),
        ),
        encoding="utf-8",
    )
    return out_dir, stats, issues


# ---------------------------------------------------------------- Patch Overlay 导出

def _overlay_path_is_safe(relative_path: str) -> bool:
    if (
        not isinstance(relative_path, str)
        or not relative_path
        or not relative_path.endswith(".zip")
        or relative_path.startswith("/")
        or "\\" in relative_path
        or "//" in relative_path
        or any(character in relative_path for character in ":?#%")
        or any(ord(character) < 0x21 or ord(character) > 0x7e for character in relative_path)
        or posixpath.normpath(relative_path) != relative_path
    ):
        return False
    parts = relative_path.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _overlay_version_is_valid(version: str) -> bool:
    parsed = parse_version(version)
    return parsed is not None and all(part <= JS_MAX_SAFE_INTEGER for part in parsed)


def _overlay_positive_safe_integer(value: object) -> bool:
    return (
        isinstance(value, int) and not isinstance(value, bool)
        and 0 < value <= JS_MAX_SAFE_INTEGER
    )


def _path_components(path: Path) -> list[Path]:
    absolute = path.absolute()
    parts = absolute.parts
    if not parts:
        return []
    current = Path(parts[0])
    result = [current]
    for part in parts[1:]:
        current = current / part
        result.append(current)
    return result


def _is_link_or_reparse(file_stat: os.stat_result) -> bool:
    """Treat Windows junctions/reparse points like symlinks on every path boundary."""
    return stat.S_ISLNK(file_stat.st_mode) or bool(
        getattr(file_stat, "st_file_attributes", 0) & 0x400
    )


def _validated_overlay_file(
    package_root: Path,
    relative_path: str,
    target_version: str,
) -> Path:
    if not _overlay_path_is_safe(relative_path):
        raise OverlayExportError(
            "PATCH_ARCHIVE_PATH_INVALID",
            "archive relativePath must be a safe printable ASCII ZIP path",
            "archive",
            target_version=target_version,
            relative_path=relative_path,
        )
    try:
        root_resolved = package_root.resolve(strict=True)
    except OSError as exc:
        raise OverlayExportError(
            "PATCH_ARCHIVE_FILE_MISSING", str(exc), "archive",
            target_version=target_version, relative_path=relative_path,
        ) from exc
    candidate = package_root.joinpath(*relative_path.split("/"))
    try:
        for component in _path_components(candidate):
            component_stat = os.lstat(component)
            if _is_link_or_reparse(component_stat):
                raise OverlayExportError(
                    "PATCH_ARCHIVE_SYMLINK",
                    "declared path contains a symbolic link",
                    "archive",
                    target_version=target_version,
                    relative_path=relative_path,
                )
        final_stat = os.lstat(candidate)
    except OverlayExportError:
        raise
    except FileNotFoundError as exc:
        raise OverlayExportError(
            "PATCH_ARCHIVE_FILE_MISSING", "declared path is missing", "archive",
            target_version=target_version, relative_path=relative_path,
        ) from exc
    except OSError as exc:
        raise OverlayExportError(
            "PATCH_ARCHIVE_FILE_TYPE", str(exc), "archive",
            target_version=target_version, relative_path=relative_path,
        ) from exc
    if not stat.S_ISREG(final_stat.st_mode) or not _overlay_positive_safe_integer(final_stat.st_size):
        raise OverlayExportError(
            "PATCH_ARCHIVE_FILE_TYPE",
            "declared path must be a nonempty safe-sized regular file",
            "archive",
            target_version=target_version,
            relative_path=relative_path,
        )
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root_resolved)
    except (OSError, ValueError) as exc:
        raise OverlayExportError(
            "PATCH_ARCHIVE_SYMLINK",
            "declared path resolves outside package root",
            "archive",
            target_version=target_version,
            relative_path=relative_path,
        ) from exc
    descriptor = -1
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(candidate, flags)
        opened = os.fstat(descriptor)
        if (
            _is_link_or_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or _overlay_object_key(opened) != _overlay_object_key(final_stat)
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "declared path changed before ZIP validation",
                "archive", target_version=target_version,
                relative_path=relative_path,
            )
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            with zipfile.ZipFile(stream) as bundle:
                bad_member = bundle.testzip()
            after_read = os.fstat(stream.fileno())
        after_path = os.lstat(candidate)
        if (
            _is_link_or_reparse(after_path)
            or _overlay_file_identity(after_read) != _overlay_file_identity(opened)
            or _overlay_file_identity(after_path) != _overlay_file_identity(final_stat)
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "declared path changed during ZIP validation",
                "archive", target_version=target_version,
                relative_path=relative_path,
            )
    except OverlayExportError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise OverlayExportError(
            "PATCH_ARCHIVE_FILE_TYPE", "declared path is not a valid ZIP", "archive",
            target_version=target_version, relative_path=relative_path,
        ) from exc
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
    if bad_member is not None:
        raise OverlayExportError(
            "PATCH_ARCHIVE_FILE_TYPE",
            f"declared ZIP has a corrupt member: {bad_member}",
            "archive",
            target_version=target_version,
            relative_path=relative_path,
        )
    return candidate


def _overlay_file_identity(file_stat: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_size,
        file_stat.st_mtime_ns,
        file_stat.st_ctime_ns,
    )


def _overlay_object_key(file_stat: os.stat_result) -> tuple[int, int]:
    """Fields with comparable semantics between Windows path and handle stats."""
    return file_stat.st_dev, file_stat.st_ino


def _private_directory_pin(
    path: Path,
    target_version: str,
    relative_path: str,
) -> tuple[Path, tuple[int, int, int, int, int]]:
    try:
        path_stat = os.lstat(path)
    except OSError as exc:
        raise OverlayExportError(
            "PATCH_STAGING_IO_FAILED", f"could not inspect private staging directory: {exc}",
            "output", target_version=target_version,
            relative_path=relative_path,
        ) from exc
    if _is_link_or_reparse(path_stat) or not stat.S_ISDIR(path_stat.st_mode):
        raise OverlayExportError(
            "PATCH_ARCHIVE_SYMLINK",
            "private staging parent must be a real directory",
            "output", target_version=target_version,
            relative_path=relative_path,
        )
    return path, _overlay_file_identity(path_stat)


def _revalidate_private_directories(
    pins: list[tuple[Path, tuple[int, int, int, int, int]]],
    target_version: str,
    relative_path: str,
) -> None:
    for path, identity in pins:
        try:
            path_stat = os.lstat(path)
        except OSError as exc:
            raise OverlayExportError(
                "PATCH_STAGING_IO_FAILED",
                f"could not recheck private staging directory: {exc}",
                "output", target_version=target_version,
                relative_path=relative_path,
            ) from exc
        if (
            _is_link_or_reparse(path_stat)
            or not stat.S_ISDIR(path_stat.st_mode)
            or _overlay_file_identity(path_stat) != identity
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK",
                "private staging parent identity changed",
                "output", target_version=target_version,
                relative_path=relative_path,
            )


def _refresh_mutated_private_parent(
    pins: list[tuple[Path, tuple[int, int, int, int, int]]],
    target_version: str,
    relative_path: str,
) -> None:
    """Accept metadata changes caused by our child creation, but not parent replacement."""
    if len(pins) > 1:
        _revalidate_private_directories(pins[:-1], target_version, relative_path)
    path, identity = pins[-1]
    refreshed = _private_directory_pin(path, target_version, relative_path)
    if refreshed[1][:2] != identity[:2]:
        raise OverlayExportError(
            "PATCH_ARCHIVE_SYMLINK", "private staging parent object changed",
            "output", target_version=target_version,
            relative_path=relative_path,
        )
    pins[-1] = refreshed


@contextmanager
def _secure_private_leaf(
    trusted_root: Path,
    leaf: Path,
    *,
    target_version: str,
    relative_path: str,
):
    """Exclusively create one private leaf while pinning every parent directory."""
    trusted_absolute = trusted_root.absolute()
    leaf_absolute = leaf.absolute()
    try:
        leaf_relative = leaf_absolute.relative_to(trusted_absolute)
    except ValueError as exc:
        raise OverlayExportError(
            "PATCH_ARCHIVE_PATH_INVALID", "private staging leaf escapes its trusted root",
            "output", target_version=target_version,
            relative_path=relative_path,
        ) from exc
    if not leaf_relative.parts or any(part in ("", ".", "..") for part in leaf_relative.parts):
        raise OverlayExportError(
            "PATCH_ARCHIVE_PATH_INVALID", "private staging leaf path is invalid",
            "output", target_version=target_version,
            relative_path=relative_path,
        )

    pins = [_private_directory_pin(
        trusted_absolute, target_version, relative_path,
    )]
    current = trusted_absolute
    try:
        for component in leaf_relative.parts[:-1]:
            next_parent = current / component
            try:
                os.lstat(next_parent)
            except FileNotFoundError:
                _revalidate_private_directories(pins, target_version, relative_path)
                os.mkdir(next_parent, 0o700)
                _refresh_mutated_private_parent(pins, target_version, relative_path)
            pins.append(_private_directory_pin(
                next_parent, target_version, relative_path,
            ))
            current = next_parent
        _revalidate_private_directories(pins, target_version, relative_path)

        flags = (
            os.O_WRONLY | os.O_CREAT | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(leaf_absolute, flags, 0o600)
    except OverlayExportError:
        raise
    except OSError as exc:
        raise OverlayExportError(
            "PATCH_STAGING_IO_FAILED", f"could not create private staging leaf: {exc}",
            "output", target_version=target_version,
            relative_path=relative_path,
        ) from exc

    stream = None
    try:
        opened = os.fstat(descriptor)
        if _is_link_or_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise OverlayExportError(
                "PATCH_ARCHIVE_FILE_TYPE", "private staging leaf is not a regular file",
                "output", target_version=target_version,
                relative_path=relative_path,
            )
        _refresh_mutated_private_parent(pins, target_version, relative_path)
        stream = os.fdopen(descriptor, "wb", closefd=True)
        descriptor = -1
        yield stream
        stream.flush()
        os.fsync(stream.fileno())
        after_write = os.fstat(stream.fileno())
        if not stat.S_ISREG(after_write.st_mode) or _overlay_object_key(after_write) != _overlay_object_key(opened):
            raise OverlayExportError(
                "PATCH_ARCHIVE_FILE_TYPE", "private staging leaf identity changed while writing",
                "output", target_version=target_version,
                relative_path=relative_path,
            )
        stream.close()
        stream = None
        _revalidate_private_directories(pins, target_version, relative_path)
        after_path = os.lstat(leaf_absolute)
        if (
            _is_link_or_reparse(after_path)
            or not stat.S_ISREG(after_path.st_mode)
            or _overlay_object_key(after_path) != _overlay_object_key(after_write)
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "private staging leaf changed after writing",
                "output", target_version=target_version,
                relative_path=relative_path,
            )
    except OverlayExportError:
        raise
    except OSError as exc:
        raise OverlayExportError(
            "PATCH_STAGING_IO_FAILED", f"private staging leaf write failed: {exc}",
            "output", target_version=target_version,
            relative_path=relative_path,
        ) from exc
    finally:
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass
        elif descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _validate_overlay_archive_metadata(archive: ArchiveInput) -> None:
    target_version = archive.to_version
    if not _overlay_path_is_safe(archive.relative_path):
        raise OverlayExportError(
            "PATCH_ARCHIVE_PATH_INVALID", "source archive path is unsafe",
            "archive", target_version=target_version,
            relative_path=archive.relative_path,
        )
    if (
        archive.from_version is None
        or not _overlay_version_is_valid(archive.from_version)
        or not _overlay_version_is_valid(archive.to_version)
    ):
        raise OverlayExportError(
            "PATCH_TARGET_VERSION_INVALID", "archive edge has an unsafe version",
            "archive", target_version=target_version,
            relative_path=archive.relative_path,
        )
    if not _overlay_positive_safe_integer(archive.order):
        raise OverlayExportError(
            "PATCH_ARCHIVE_ORDER_INVALID", "archive order must be a positive safe integer",
            "archive", target_version=target_version,
            relative_path=archive.relative_path,
        )


def _overlay_source_location(
    archive: ArchiveInput,
    cdn_root: Path,
    asset_patch_active: Path | None,
) -> tuple[Path, str]:
    root_relative = archive_source_root_relative(
        archive, cdn_root, asset_patch_active
    )
    if root_relative is None:
        raise OverlayExportError(
            "PATCH_ARCHIVE_FILE_MISSING", "foreign archive source root is unavailable",
            "archive", target_version=archive.to_version,
            relative_path=archive.relative_path,
        )
    return root_relative


def _pin_overlay_source(
    archive: ArchiveInput,
    source_root: Path,
    source_relative_path: str,
    snapshot_path: Path,
    staging_root: Path,
) -> OverlaySource:
    """Snapshot a source through a pinned no-follow handle and reject identity races."""
    _validate_overlay_archive_metadata(archive)
    source = _validated_overlay_file(
        source_root, source_relative_path, archive.to_version,
    )
    relative_context = archive.relative_path
    descriptor = -1
    try:
        before = os.lstat(source)
        if _is_link_or_reparse(before):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "source archive is a link or reparse point",
                "archive", target_version=archive.to_version,
                relative_path=relative_context,
            )
        if not stat.S_ISREG(before.st_mode):
            raise OverlayExportError(
                "PATCH_ARCHIVE_FILE_TYPE", "source archive must remain a regular file",
                "archive", target_version=archive.to_version,
                relative_path=relative_context,
            )
        if not _overlay_positive_safe_integer(before.st_size):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SIZE_INVALID", "archive bytes must be a positive safe integer",
                "archive", target_version=archive.to_version,
                relative_path=relative_context,
            )
        flags = (
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(source, flags)
    except OverlayExportError:
        raise
    except OSError as exc:
        raise OverlayExportError(
            "PATCH_ARCHIVE_FILE_TYPE", f"could not pin source archive: {exc}", "archive",
            target_version=archive.to_version, relative_path=relative_context,
        ) from exc
    digest = hashlib.sha256()
    total_bytes = 0
    try:
        opened = os.fstat(descriptor)
        if (
            _is_link_or_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or _overlay_object_key(opened) != _overlay_object_key(before)
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "source archive identity changed before open",
                "archive", target_version=archive.to_version,
                relative_path=relative_context,
            )
        with os.fdopen(descriptor, "rb", closefd=True) as source_stream, _secure_private_leaf(
            staging_root, snapshot_path,
            target_version=archive.to_version,
            relative_path=relative_context,
        ) as target:
            descriptor = -1
            for block in iter(lambda: source_stream.read(1 << 20), b""):
                target.write(block)
                digest.update(block)
                total_bytes += len(block)
            after_read = os.fstat(source_stream.fileno())
        after_path = os.lstat(source)
        if (
            _is_link_or_reparse(after_path)
            or _overlay_file_identity(after_read) != _overlay_file_identity(opened)
            or _overlay_file_identity(after_path) != _overlay_file_identity(before)
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "source archive identity changed while snapshotting",
                "archive", target_version=archive.to_version,
                relative_path=relative_context,
            )
        if not _overlay_positive_safe_integer(total_bytes):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SIZE_INVALID", "archive bytes must be a positive safe integer",
                "archive", target_version=archive.to_version,
                relative_path=relative_context,
            )
        _validated_overlay_file(snapshot_path.parent, snapshot_path.name, archive.to_version)
    except BaseException as exc:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            snapshot_path.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, OverlayExportError):
            raise
        if isinstance(exc, OSError):
            raise OverlayExportError(
                "PATCH_STAGING_IO_FAILED", f"private source snapshot failed: {exc}",
                "output", target_version=archive.to_version,
                relative_path=str(snapshot_path),
            ) from exc
        raise
    archive.compressed_bytes = total_bytes
    archive.sha256 = digest.hexdigest()
    snapshot_stat = os.lstat(snapshot_path)
    return OverlaySource(
        archive=archive,
        source_root=source_root,
        source_relative_path=source_relative_path,
        snapshot_path=snapshot_path,
        snapshot_identity=_overlay_file_identity(snapshot_stat),
    )


def _overlay_full_base(version: str) -> list[ArchiveInput]:
    return [
        ArchiveInput(
            kind="full", from_version=None, to_version=version,
            platform="android", layer=layer, order=1,
            relative_path=(
                f"archive-{directory.removeprefix('archive-').removesuffix('-diff')}-full/"
                f"pinball-{version}-1-{index:02x}00.zip"
            ),
            compressed_bytes=1, sha256="0" * 64,
        )
        for index, (layer, (_manifest_layer, directory)) in enumerate(
            OVERLAY_LAYER_NAMES.items(), start=1,
        )
    ]


def _first_unreachable_target(
    archives: list[ArchiveInput], from_version: str,
) -> str | None:
    edges = sorted(
        {(archive.from_version, archive.to_version) for archive in archives},
        key=lambda edge: parse_version(edge[1]) or (0, 0, 0),
    )
    reachable = {from_version}
    changed = True
    while changed:
        changed = False
        for edge_from, edge_to in edges:
            if edge_from in reachable and edge_to not in reachable:
                reachable.add(edge_to)
                changed = True
    return next((edge_to for edge_from, edge_to in edges if edge_from not in reachable), None)


def _raise_overlay_issue(
    issue: Issue,
    archives: list[ArchiveInput],
    from_version: str,
) -> None:
    by_path = {archive.relative_path: archive.to_version for archive in archives}
    target_version = by_path.get(issue.relative_path or "")
    if target_version is None and issue.code == "MISSING_PATH":
        target_version = _first_unreachable_target(archives, from_version)
    if target_version is None:
        target_version = max(
            (archive.to_version for archive in archives),
            key=lambda version: parse_version(version) or (0, 0, 0),
            default=from_version,
        )
    raise OverlayExportError(
        issue.code, issue.message, issue.category,
        target_version=target_version, relative_path=issue.relative_path,
    )


def _validate_overlay_graph(
    archives: list[ArchiveInput], from_version: str,
) -> None:
    _catalog, issues = build_catalog(
        _overlay_full_base(from_version) + archives,
        0,
        "EntityLists/overlay-android_medium.csv",
    )
    if issues:
        _raise_overlay_issue(issues[0], archives, from_version)


def _manifest_archive_input(item: dict) -> ArchiveInput:
    match = DIFF_NAME_RE.fullmatch(Path(item["relativePath"]).name)
    if match is None:
        raise AssertionError("validated Overlay filename did not parse")
    catalog_layer = {"common": "common", "medium": "quality", "android": "platform"}[
        item["layer"]
    ]
    return ArchiveInput(
        kind="diff", from_version=match.group(1), to_version=match.group(2),
        platform="android", layer=catalog_layer, order=item["order"],
        relative_path=item["relativePath"], compressed_bytes=item["bytes"],
        sha256=item["sha256"],
    )


def _validate_staged_overlay(package_root: Path, manifest: dict) -> None:
    target_version = manifest.get("targetVersion", "<missing>")
    if manifest.get("schema") != OVERLAY_SCHEMA:
        raise OverlayExportError(
            "PATCH_MANIFEST_SCHEMA", "manifest must use schema 1", "manifest",
            target_version=target_version,
        )
    if manifest.get("compatibleClient") != OVERLAY_CLIENT:
        raise OverlayExportError(
            "PATCH_CLIENT_INCOMPATIBLE", "compatibleClient must be CN 1.8.1", "manifest",
            target_version=target_version,
        )
    if not _overlay_version_is_valid(target_version):
        raise OverlayExportError(
            "PATCH_TARGET_VERSION_INVALID", "targetVersion must use safe version components",
            "manifest", target_version=target_version,
        )
    if (
        "baseVersion" in manifest
        and not _overlay_version_is_valid(manifest["baseVersion"])
    ):
        raise OverlayExportError(
            "PATCH_BASE_VERSION_INVALID", "baseVersion must use safe version components",
            "manifest", target_version=target_version,
        )
    if not isinstance(manifest.get("archives"), list) or not manifest["archives"]:
        raise OverlayExportError(
            "PATCH_ARCHIVES_INVALID", "archives must be a nonempty array", "archive",
            target_version=target_version,
        )
    archives: list[ArchiveInput] = []
    for item in manifest["archives"]:
        relative_path = item["relativePath"]
        layer = item.get("layer")
        if layer not in ("common", "medium", "android"):
            raise OverlayExportError(
                "PATCH_ARCHIVE_LAYER_INVALID", "archive layer is invalid", "archive",
                target_version=target_version, relative_path=relative_path,
            )
        expected_directory = f"archive-{layer}-diff"
        match = DIFF_NAME_RE.fullmatch(Path(relative_path).name)
        if (
            not _overlay_path_is_safe(relative_path)
            or relative_path.split("/")[:-1] != [expected_directory]
            or match is None
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_PATH_INVALID",
                "archive layer and filename must agree with relativePath",
                "archive", target_version=target_version,
                relative_path=relative_path,
            )
        if not _overlay_positive_safe_integer(item.get("order")):
            raise OverlayExportError(
                "PATCH_ARCHIVE_ORDER_INVALID", "archive order must be a positive safe integer",
                "archive", target_version=target_version, relative_path=relative_path,
            )
        if not _overlay_positive_safe_integer(item.get("bytes")):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SIZE_INVALID", "archive bytes must be a positive safe integer",
                "archive", target_version=target_version, relative_path=relative_path,
            )
        if (
            not _overlay_version_is_valid(match.group(1))
            or not _overlay_version_is_valid(match.group(2))
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_TARGET_MISMATCH", "archive filename has unsafe versions",
                "archive", target_version=target_version, relative_path=relative_path,
            )
        if match.group(2) != target_version or int(match.group(3)) != item["order"]:
            raise OverlayExportError(
                "PATCH_ARCHIVE_TARGET_MISMATCH",
                "archive filename edge/order does not match manifest",
                "archive", target_version=target_version,
                relative_path=relative_path,
            )
        path = _validated_overlay_file(package_root, relative_path, target_version)
        if path.stat().st_size != item["bytes"]:
            raise OverlayExportError(
                "PATCH_ARCHIVE_SIZE_MISMATCH", "archive size does not match manifest",
                "archive", target_version=target_version, relative_path=relative_path,
            )
        if not SHA256_HEX_RE.fullmatch(item["sha256"] or ""):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SHA256_INVALID", "archive sha256 must be lowercase hexadecimal",
                "archive", target_version=target_version, relative_path=relative_path,
            )
        if file_sha256(path) != item["sha256"]:
            raise OverlayExportError(
                "PATCH_ARCHIVE_HASH_MISMATCH", "archive digest does not match manifest",
                "archive", target_version=target_version, relative_path=relative_path,
            )
        archives.append(_manifest_archive_input(item))
    edge_from = archives[0].from_version
    assert edge_from is not None
    _validate_overlay_graph(archives, edge_from)


def _publish_overlay_manifest(package_root: Path, manifest: dict) -> Path:
    """Publish the runtime completion marker after every other package file exists."""
    target = package_root / "patch-manifest.json"
    handle = -1
    temporary_name: str | None = None
    try:
        handle, temporary_name = tempfile.mkstemp(
            prefix=".patch-manifest.", suffix=".tmp", dir=package_root,
        )
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, target)
    except BaseException as exc:
        if handle >= 0:
            try:
                os.close(handle)
            except OSError:
                pass
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(exc, OverlayExportError):
            raise
        raise OverlayExportError(
            "PATCH_MANIFEST_WRITE_FAILED", f"manifest publication failed: {exc}",
            "output", target_version=manifest.get("targetVersion", "<unknown>"),
            relative_path="patch-manifest.json",
        ) from exc
    return target


OVERLAY_README_TEMPLATE = """# World Flipper Patch Overlay {target}

This package requires Overlay schema 1 and a compatible CN 1.8.1 server.

Install by extracting this outer ZIP directly into `CDN_DIR/patches/{target}/`.
Use a normal supported restart such as `npm run start:cn`; startup Content Sync discovers,
validates, and activates the package. Do not merge these files into `cn`.

`requires.json` contains author/dependency metadata and does not replace patch-manifest.json,
which is the runtime authority. `dev-catalog/EntityLists` and `server-patch/` are legacy and
are not required in this Overlay mode.
"""


def _overlay_requires(
    sources: list[OverlaySource],
    from_version: str,
    target_version: str,
    *,
    min_server: str | None,
    server_features: tuple[str, ...],
    client_patches: tuple[str, ...],
) -> dict:
    restart, reasons = _detect_pack_requirements_from_paths([
        source.snapshot_path for source in sources
    ])
    return {
        "schemaVersion": 2,
        "pack": {
            "format": "patch-overlay", "variant": "full",
            "from": from_version, "tail": target_version, "edges": 1,
        },
        "enhancement": True,
        "enhancementDetail": {
            "note": "Author/dependency metadata only; patch-manifest.json is runtime authority",
        },
        "requires": {
            "serverRestart": restart,
            "restartReasons": reasons,
            "minServerVersion": min_server,
            "serverFeatures": list(server_features),
            "clientPatches": list(client_patches),
        },
    }


def _guarded_copy_file(
    source: Path,
    target: Path,
    *,
    target_root: Path,
    expected_identity: tuple[int, int, int, int, int],
    expected_sha256: str,
    target_version: str,
    relative_path: str,
) -> tuple[int, str]:
    """Copy a pinned regular file through a no-follow handle while rechecking identity."""
    descriptor = -1
    try:
        before = os.lstat(source)
        if (
            _is_link_or_reparse(before)
            or not stat.S_ISREG(before.st_mode)
            or _overlay_file_identity(before) != expected_identity
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "private source snapshot identity changed",
                "archive", target_version=target_version,
                relative_path=relative_path,
            )
        flags = (
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(source, flags)
        opened = os.fstat(descriptor)
        if (
            _is_link_or_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or _overlay_object_key(opened) != expected_identity[:2]
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "private source snapshot changed before open",
                "archive", target_version=target_version,
                relative_path=relative_path,
            )
        digest = hashlib.sha256()
        total_bytes = 0
        with os.fdopen(descriptor, "rb", closefd=True) as source_stream, _secure_private_leaf(
            target_root, target,
            target_version=target_version,
            relative_path=relative_path,
        ) as target_stream:
            descriptor = -1
            for block in iter(lambda: source_stream.read(1 << 20), b""):
                target_stream.write(block)
                digest.update(block)
                total_bytes += len(block)
            after_read = os.fstat(source_stream.fileno())
        after_path = os.lstat(source)
        if (
            _is_link_or_reparse(after_path)
            or _overlay_file_identity(after_read) != _overlay_file_identity(opened)
            or _overlay_file_identity(after_path) != expected_identity
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "private source snapshot changed while copying",
                "archive", target_version=target_version,
                relative_path=relative_path,
            )
        actual_sha256 = digest.hexdigest()
        if not _overlay_positive_safe_integer(total_bytes) or actual_sha256 != expected_sha256:
            raise OverlayExportError(
                "PATCH_ARCHIVE_HASH_MISMATCH", "private source snapshot bytes changed",
                "archive", target_version=target_version,
                relative_path=relative_path,
            )
        return total_bytes, actual_sha256
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _stage_overlay_package(
    package_root: Path,
    sources: list[OverlaySource],
    dependency_sources: list[OverlaySource],
    *,
    base_version: str | None,
    min_server: str | None,
    server_features: tuple[str, ...],
    client_patches: tuple[str, ...],
) -> dict:
    first = sources[0].archive
    edge_from = first.from_version
    target_version = first.to_version
    assert edge_from is not None
    try:
        package_root.mkdir(parents=True)
    except OSError as exc:
        raise OverlayExportError(
            "PATCH_STAGING_IO_FAILED", f"could not create package staging: {exc}",
            "output", target_version=target_version,
            relative_path=str(package_root),
        ) from exc
    manifest_archives: list[dict] = []
    for pinned in sorted(
        sources,
        key=lambda item: (
            LAYER_ORDER[item.archive.layer], item.archive.order,
            item.archive.relative_path,
        ),
    ):
        archive = pinned.archive
        source = pinned.snapshot_path
        manifest_layer, directory = OVERLAY_LAYER_NAMES[archive.layer]
        digest = archive.sha256
        filename = (
            f"pinball-{archive.from_version}-{archive.to_version}-{archive.order}-"
            f"{digest[:12]}.zip"
        )
        relative_path = f"{directory}/{filename}"
        target = package_root.joinpath(*relative_path.split("/"))
        try:
            staged_bytes, staged_sha256 = _guarded_copy_file(
                source, target,
                target_root=package_root,
                expected_identity=pinned.snapshot_identity,
                expected_sha256=archive.sha256,
                target_version=target_version,
                relative_path=archive.relative_path,
            )
        except OverlayExportError:
            raise
        except OSError as exc:
            raise OverlayExportError(
                "PATCH_STAGING_IO_FAILED", f"could not stage archive bytes: {exc}",
                "output", target_version=target_version,
                relative_path=relative_path,
            ) from exc
        _validated_overlay_file(package_root, relative_path, target_version)
        manifest_archives.append({
            "relativePath": relative_path,
            "layer": manifest_layer,
            "order": archive.order,
            "bytes": staged_bytes,
            "sha256": staged_sha256,
        })

    requires = _overlay_requires(
        dependency_sources, edge_from, target_version,
        min_server=min_server, server_features=server_features,
        client_patches=client_patches,
    )
    try:
        (package_root / "requires.json").write_text(
            json.dumps(requires, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        (package_root / "README.md").write_text(
            OVERLAY_README_TEMPLATE.format(target=target_version), encoding="utf-8",
        )
    except OSError as exc:
        raise OverlayExportError(
            "PATCH_STAGING_IO_FAILED", f"could not write package metadata: {exc}",
            "output", target_version=target_version,
            relative_path=str(package_root),
        ) from exc
    manifest = {
        "schema": OVERLAY_SCHEMA,
        "targetVersion": target_version,
        "compatibleClient": OVERLAY_CLIENT,
        "archives": manifest_archives,
    }
    if base_version is not None:
        manifest["baseVersion"] = base_version
    _validate_staged_overlay(package_root, manifest)
    _publish_overlay_manifest(package_root, manifest)
    return manifest


def _overlay_package_files(package_root: Path, manifest: dict) -> list[PinnedPackageMember]:
    expected = {
        "README.md", "requires.json", "patch-manifest.json",
        *(item["relativePath"] for item in manifest["archives"]),
    }
    actual: set[str] = set()
    pinned: dict[str, PinnedPackageMember] = {}
    expected_directories = {
        Path(item["relativePath"]).parent.as_posix()
        for item in manifest["archives"]
    }
    for current, directory_names, file_names in os.walk(package_root, followlinks=False):
        current_path = Path(current)
        for name in [*directory_names, *file_names]:
            path = current_path / name
            relative = path.relative_to(package_root).as_posix()
            try:
                path_stat = os.lstat(path)
            except OSError as exc:
                raise OverlayExportError(
                    "PATCH_ARCHIVE_FILE_TYPE", f"could not inspect staged path: {exc}",
                    "archive", target_version=manifest["targetVersion"],
                    relative_path=relative,
                ) from exc
            if _is_link_or_reparse(path_stat):
                raise OverlayExportError(
                    "PATCH_ARCHIVE_SYMLINK", "staged package contains a symbolic link",
                    "archive", target_version=manifest["targetVersion"],
                    relative_path=relative,
                )
            if stat.S_ISDIR(path_stat.st_mode):
                if relative not in expected_directories:
                    raise OverlayExportError(
                        "PATCH_ARCHIVE_FILE_TYPE", "staged package contains an unexpected directory",
                        "archive", target_version=manifest["targetVersion"],
                        relative_path=relative,
                    )
                continue
            if not stat.S_ISREG(path_stat.st_mode):
                raise OverlayExportError(
                    "PATCH_ARCHIVE_FILE_TYPE", "staged package contains a non-regular file",
                    "archive", target_version=manifest["targetVersion"],
                    relative_path=relative,
                )
            actual.add(relative)
            pinned[relative] = PinnedPackageMember(
                relative_path=relative,
                path=path,
                identity=_overlay_file_identity(path_stat),
            )
    unexpected = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unexpected or missing:
        relative = unexpected[0] if unexpected else missing[0]
        raise OverlayExportError(
            "PATCH_ARCHIVE_FILE_TYPE",
            "staged package does not match the explicit manifest allowlist",
            "archive", target_version=manifest["targetVersion"],
            relative_path=relative,
        )
    ordered = [
        "README.md", "requires.json",
        *sorted(item["relativePath"] for item in manifest["archives"]),
        "patch-manifest.json",
    ]
    return [pinned[relative] for relative in ordered]


def _write_pinned_package_member(
    bundle: zipfile.ZipFile,
    member: PinnedPackageMember,
    target_version: str,
) -> None:
    descriptor = -1
    try:
        before = os.lstat(member.path)
        if (
            _is_link_or_reparse(before)
            or not stat.S_ISREG(before.st_mode)
            or _overlay_file_identity(before) != member.identity
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "staged package member identity changed",
                "archive", target_version=target_version,
                relative_path=member.relative_path,
            )
        flags = (
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(member.path, flags)
        opened = os.fstat(descriptor)
        if (
            _is_link_or_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or _overlay_object_key(opened) != member.identity[:2]
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "staged package member changed before open",
                "archive", target_version=target_version,
                relative_path=member.relative_path,
            )
        with os.fdopen(descriptor, "rb", closefd=True) as source, bundle.open(
            member.relative_path, "w",
        ) as target:
            descriptor = -1
            for block in iter(lambda: source.read(1 << 20), b""):
                target.write(block)
            after_read = os.fstat(source.fileno())
        after_path = os.lstat(member.path)
        if (
            _is_link_or_reparse(after_path)
            or _overlay_file_identity(after_read) != _overlay_file_identity(opened)
            or _overlay_file_identity(after_path) != member.identity
        ):
            raise OverlayExportError(
                "PATCH_ARCHIVE_SYMLINK", "staged package member changed while streaming",
                "archive", target_version=target_version,
                relative_path=member.relative_path,
            )
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _write_outer_overlay(package_root: Path, outer_path: Path, manifest: dict) -> None:
    temporary = outer_path.with_name(f".{outer_path.name}.tmp")
    try:
        members = _overlay_package_files(package_root, manifest)
        member_names = [member.relative_path for member in members]
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for member in members:
                _write_pinned_package_member(bundle, member, manifest["targetVersion"])
        with zipfile.ZipFile(temporary) as bundle:
            names = bundle.namelist()
            if (
                bundle.testzip() is not None
                or names != member_names
                or len(names) != len(set(names))
            ):
                raise OverlayExportError(
                    "PATCH_ARCHIVE_FILE_TYPE", "outer ZIP member allowlist verification failed",
                    "archive", target_version=manifest["targetVersion"],
                    relative_path=outer_path.name,
                )
            if json.loads(bundle.read("patch-manifest.json")) != manifest:
                raise OverlayExportError(
                    "PATCH_ARCHIVE_HASH_MISMATCH", "outer ZIP manifest changed while writing",
                    "archive", target_version=manifest["targetVersion"],
                    relative_path="patch-manifest.json",
                )
            for item in manifest["archives"]:
                digest = hashlib.sha256()
                total_bytes = 0
                with bundle.open(item["relativePath"]) as stream:
                    for block in iter(lambda: stream.read(1 << 20), b""):
                        digest.update(block)
                        total_bytes += len(block)
                if total_bytes != item["bytes"] or digest.hexdigest() != item["sha256"]:
                    raise OverlayExportError(
                        "PATCH_ARCHIVE_HASH_MISMATCH",
                        "outer ZIP archive bytes do not match manifest",
                        "archive", target_version=manifest["targetVersion"],
                        relative_path=item["relativePath"],
                    )
        os.replace(temporary, outer_path)
    except BaseException as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, OverlayExportError):
            raise
        raise OverlayExportError(
            "PATCH_OUTER_ZIP_WRITE_FAILED", f"outer ZIP publication failed: {exc}",
            "output", target_version=manifest["targetVersion"],
            relative_path=outer_path.name,
        ) from exc


def _empty_consolidated_layer(
    root: Path, layer: str, from_version: str, to_version: str,
) -> tuple[ArchiveInput, Path]:
    _manifest_layer, directory = OVERLAY_LAYER_NAMES[layer]
    filename = f"pinball-{from_version}-{to_version}-1-e0e0.zip"
    path = root / directory / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED):
        pass
    return ArchiveInput(
        kind="diff", from_version=from_version, to_version=to_version,
        platform="android", layer=layer, order=1,
        relative_path=f"{directory}/{filename}", compressed_bytes=path.stat().st_size,
        sha256=file_sha256(path),
    ), path


def _consolidated_overlay_sources(
    selected: list[OverlaySource],
    work_dir: Path,
    from_version: str,
    target_version: str,
) -> list[OverlaySource]:
    import wf_pack_consolidate

    root_names = {"common": "common", "quality": "medium", "platform": "android"}
    inputs = [
        (source.snapshot_path, root_names[source.archive.layer])
        for source in selected
    ]
    try:
        report = wf_pack_consolidate.consolidate(
            selected[0].source_root, ROOT, tag="c0decafe", files=inputs,
            max_zip_mib=0, out_dir=work_dir, force=False,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise OverlayExportError(
            "PATCH_ARCHIVE_FILE_TYPE", f"consolidation failed: {exc}", "archive",
            target_version=target_version,
        ) from exc
    if report.get("from") != from_version or report.get("to") != target_version:
        raise OverlayExportError(
            "PATCH_ARCHIVE_TARGET_MISMATCH",
            "consolidator output edge does not match requested from/final target",
            "graph", target_version=target_version,
        )
    catalog_layers = {"common": "common", "medium": "quality", "android": "platform"}
    result: list[OverlaySource] = []
    for output in report["outputs"]:
        try:
            layer = catalog_layers[output["root"]]
            _manifest_layer, directory = OVERLAY_LAYER_NAMES[layer]
            reported_path = Path(output["path"])
        except (KeyError, TypeError, ValueError) as exc:
            raise OverlayExportError(
                "PATCH_ARCHIVE_PATH_INVALID", "consolidator reported invalid output metadata",
                "archive", target_version=target_version,
            ) from exc
        expected_path = work_dir / directory / reported_path.name
        if reported_path.absolute() != expected_path.absolute():
            raise OverlayExportError(
                "PATCH_ARCHIVE_PATH_INVALID",
                "consolidator output path is not the exact private work path",
                "archive", target_version=target_version,
                relative_path=str(reported_path),
            )
        path = _validated_overlay_file(
            work_dir, f"{directory}/{reported_path.name}", target_version,
        )
        try:
            if path.resolve(strict=True) != expected_path.resolve(strict=True):
                raise ValueError("resolved output path differs")
        except (OSError, ValueError) as exc:
            raise OverlayExportError(
                "PATCH_ARCHIVE_PATH_INVALID",
                "consolidator output does not resolve to its private work path",
                "archive", target_version=target_version,
                relative_path=str(reported_path),
            ) from exc
        match = DIFF_NAME_RE.fullmatch(path.name)
        if match is None:
            raise OverlayExportError(
                "PATCH_ARCHIVE_PATH_INVALID", "consolidator emitted an invalid filename",
                "archive", target_version=target_version, relative_path=path.name,
            )
        path_stat = os.lstat(path)
        archive = ArchiveInput(
            kind="diff", from_version=match.group(1), to_version=match.group(2),
            platform="android", layer=layer, order=int(match.group(3)),
            relative_path=f"{directory}/{path.name}", compressed_bytes=path_stat.st_size,
            sha256=file_sha256(path),
        )
        result.append(OverlaySource(
            archive=archive, source_root=work_dir,
            source_relative_path=archive.relative_path, snapshot_path=path,
            snapshot_identity=_overlay_file_identity(path_stat),
        ))
    present = {source.archive.layer for source in result}
    for layer in OVERLAY_LAYER_NAMES:
        if layer not in present:
            archive, path = _empty_consolidated_layer(
                work_dir, layer, from_version, target_version,
            )
            result.append(OverlaySource(
                archive=archive, source_root=work_dir,
                source_relative_path=archive.relative_path, snapshot_path=path,
                snapshot_identity=_overlay_file_identity(os.lstat(path)),
            ))
    _validate_overlay_graph([source.archive for source in result], from_version)
    return result


def _resolved_path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_overlay_output_parent(
    output_parent: Path,
    cdn_root: Path,
    asset_patch_active: Path | None,
    target_version: str,
) -> None:
    output_resolved = output_parent.resolve(strict=False)
    protected = [cdn_root, cdn_root.parent / "patches"]
    if asset_patch_active is not None:
        protected.append(Path(asset_patch_active))
    for protected_root in protected:
        protected_resolved = protected_root.resolve(strict=False)
        if _resolved_path_is_within(output_resolved, protected_resolved):
            raise OverlayExportError(
                "PATCH_OUTPUT_PROTECTED",
                "--out must not be equal to or inside a live CDN/patch root",
                "output", target_version=target_version,
                relative_path=str(output_parent),
            )


def _remove_overlay_work(work_dir: Path) -> None:
    shutil.rmtree(work_dir)
    if work_dir.exists():
        raise OSError(f"private work directory still exists: {work_dir}")


def _validate_overlay_candidate(
    candidate: Path,
    expected_names: list[str],
    target_version: str,
) -> OverlayCandidatePin:
    try:
        root_stat = os.lstat(candidate)
        if _is_link_or_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
            raise OverlayExportError(
                "PATCH_ARCHIVE_FILE_TYPE", "batch candidate root is not a real directory",
                "output", target_version=target_version,
                relative_path=str(candidate),
            )
        actual_names: list[str] = []
        members: list[PinnedPackageMember] = []
        for path in candidate.iterdir():
            path_stat = os.lstat(path)
            if _is_link_or_reparse(path_stat) or not stat.S_ISREG(path_stat.st_mode):
                raise OverlayExportError(
                    "PATCH_ARCHIVE_FILE_TYPE",
                    "batch candidate contains a non-regular outer ZIP",
                    "output", target_version=target_version,
                    relative_path=path.name,
                )
            actual_names.append(path.name)
            members.append(PinnedPackageMember(
                relative_path=path.name,
                path=path,
                identity=_overlay_file_identity(path_stat),
            ))
        if sorted(actual_names) != sorted(expected_names) or len(actual_names) != len(set(actual_names)):
            raise OverlayExportError(
                "PATCH_ARCHIVE_FILE_TYPE",
                "batch candidate does not contain exactly the expected outer ZIPs",
                "output", target_version=target_version,
            )
        after_root = os.lstat(candidate)
        if _overlay_file_identity(after_root) != _overlay_file_identity(root_stat):
            raise OverlayExportError(
                "PATCH_BATCH_PUBLISH_FAILED", "batch candidate root changed during validation",
                "output", target_version=target_version,
                relative_path=str(candidate),
            )
        return OverlayCandidatePin(
            root_identity=_overlay_file_identity(root_stat),
            members=tuple(sorted(members, key=lambda item: item.relative_path)),
        )
    except OverlayExportError:
        raise
    except OSError as exc:
        raise OverlayExportError(
            "PATCH_BATCH_PUBLISH_FAILED", f"could not verify batch candidate: {exc}",
            "output", target_version=target_version,
        ) from exc


def _recheck_overlay_candidate(
    candidate: Path,
    pin: OverlayCandidatePin,
    expected_names: list[str],
    target_version: str,
) -> None:
    """Recheck the pinned candidate immediately before the atomic directory rename."""
    try:
        root_stat = os.lstat(candidate)
        if (
            _is_link_or_reparse(root_stat)
            or not stat.S_ISDIR(root_stat.st_mode)
            or _overlay_file_identity(root_stat) != pin.root_identity
        ):
            raise OverlayExportError(
                "PATCH_BATCH_PUBLISH_FAILED", "batch candidate root identity changed",
                "output", target_version=target_version,
                relative_path=str(candidate),
            )
        current = {path.name: path for path in candidate.iterdir()}
        if sorted(current) != sorted(expected_names) or len(current) != len(expected_names):
            raise OverlayExportError(
                "PATCH_BATCH_PUBLISH_FAILED", "batch candidate members changed",
                "output", target_version=target_version,
                relative_path=str(candidate),
            )
        for member in pin.members:
            path_stat = os.lstat(current[member.relative_path])
            if (
                _is_link_or_reparse(path_stat)
                or not stat.S_ISREG(path_stat.st_mode)
                or _overlay_file_identity(path_stat) != member.identity
            ):
                raise OverlayExportError(
                    "PATCH_BATCH_PUBLISH_FAILED", "batch candidate file identity changed",
                    "output", target_version=target_version,
                    relative_path=member.relative_path,
                )
    except OverlayExportError:
        raise
    except OSError as exc:
        raise OverlayExportError(
            "PATCH_BATCH_PUBLISH_FAILED", f"could not recheck batch candidate: {exc}",
            "output", target_version=target_version,
            relative_path=str(candidate),
        ) from exc


def export_patch_overlays(
    cdn_root: Path = CDN_ROOT,
    asset_patch_active: Path | None = ASSET_PATCH_ACTIVE,
    out_dir: Path | None = None,
    *,
    from_version: str,
    base_version: str | None = None,
    consolidate: bool = False,
    min_server: str | None = None,
    server_features: tuple[str, ...] = (),
    client_patches: tuple[str, ...] = (),
) -> tuple[Path, dict, list[Issue]]:
    """Build atomic schema-1 Patch Overlay outer ZIPs without writing the CDN/store."""
    if not _overlay_version_is_valid(from_version):
        raise OverlayExportError(
            "PATCH_TARGET_VERSION_INVALID",
            "--from-ver must use safe semantic-version components", "graph",
            target_version=from_version,
        )
    if base_version is not None and not _overlay_version_is_valid(base_version):
        raise OverlayExportError(
            "PATCH_BASE_VERSION_INVALID",
            "--base-version must use safe semantic-version components",
            "manifest", target_version=from_version,
        )
    cdn_root = Path(cdn_root)
    output_parent = Path(out_dir) if out_dir is not None else cdn_root.parent / "share"
    _validate_overlay_output_parent(
        output_parent, cdn_root, asset_patch_active, from_version,
    )
    scan = scan_chain(cdn_root, asset_patch_active, digest_mode="skip")
    selected = [
        archive for archive in scan.archives
        if archive.kind == "diff" and compare_versions(archive.to_version, from_version) > 0
    ]
    if not selected:
        raise OverlayExportError(
            "MISSING_PATH", f"no upgrade edge is available from {from_version}", "graph",
            target_version=from_version,
        )
    for archive in selected:
        _validate_overlay_archive_metadata(archive)
    _validate_overlay_graph(selected, from_version)

    edges = sorted(
        {(archive.from_version, archive.to_version) for archive in selected},
        key=lambda edge: parse_version(edge[1]) or (0, 0, 0),
    )
    tail = edges[-1][1]
    assert tail is not None
    generated_targets = {edge_to for _edge_from, edge_to in edges}
    if base_version is not None and base_version in generated_targets:
        raise OverlayExportError(
            "PATCH_BASE_VERSION_CYCLE",
            "--base-version must not depend on a package generated by this batch",
            "graph", target_version=base_version,
        )
    batch_name = f"wf-overlay-{from_version}-to-{tail}"
    final_batch = output_parent / batch_name
    if final_batch.exists():
        raise OverlayExportError(
            "PATCH_OUTPUT_EXISTS", "output batch already exists", "output",
            target_version=tail, relative_path=batch_name,
        )
    work_dir: Path | None = None
    candidate: Path | None = None
    try:
        output_parent.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix=f".{batch_name}.work.", dir=output_parent))
        candidate = Path(tempfile.mkdtemp(prefix=f".{batch_name}.candidate.", dir=output_parent))
    except OSError as exc:
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)
        raise OverlayExportError(
            "PATCH_BATCH_PUBLISH_FAILED", f"could not create private output staging: {exc}",
            "output", target_version=tail, relative_path=str(output_parent),
        ) from exc
    stats = {"from": from_version, "tail": tail, "packages": 0, "outerZips": []}
    published = False
    assert work_dir is not None and candidate is not None
    try:
        pinned_sources: list[OverlaySource] = []
        for index, archive in enumerate(selected, start=1):
            source_root, source_relative = _overlay_source_location(
                archive, cdn_root, asset_patch_active,
            )
            pinned_sources.append(_pin_overlay_source(
                archive, source_root, source_relative,
                work_dir / "sources" / f"{index:04d}"
                / Path(archive.relative_path).name,
                work_dir,
            ))
        _validate_overlay_graph(
            [source.archive for source in pinned_sources], from_version,
        )

        package_stage = work_dir / "packages"
        plans: list[tuple[str, str, list[OverlaySource], list[OverlaySource]]] = []
        if consolidate:
            consolidated_dir = work_dir / "consolidated"
            consolidated = _consolidated_overlay_sources(
                pinned_sources, consolidated_dir, from_version, tail,
            )
            plans.append((from_version, tail, consolidated, pinned_sources))
        else:
            for edge_from, edge_to in edges:
                assert edge_from is not None
                edge_sources = [
                    source for source in pinned_sources
                    if source.archive.from_version == edge_from
                    and source.archive.to_version == edge_to
                ]
                plans.append((edge_from, edge_to, edge_sources, edge_sources))

        for edge_from, edge_to, sources, dependencies in plans:
            package_root = package_stage / edge_to
            manifest = _stage_overlay_package(
                package_root, sources, dependencies,
                base_version=base_version, min_server=min_server,
                server_features=server_features, client_patches=client_patches,
            )
            outer_name = f"worldflipper-overlay-{edge_from}-to-{edge_to}.zip"
            _write_outer_overlay(package_root, candidate / outer_name, manifest)
            stats["outerZips"].append(outer_name)

        try:
            _remove_overlay_work(work_dir)
        except OSError as exc:
            raise OverlayExportError(
                "PATCH_OUTPUT_CLEANUP_FAILED", f"private work cleanup failed: {exc}",
                "output", target_version=tail, relative_path=str(work_dir),
            ) from exc
        candidate_pin = _validate_overlay_candidate(candidate, stats["outerZips"], tail)
        stats["packages"] = len(plans)
        try:
            _recheck_overlay_candidate(
                candidate, candidate_pin, stats["outerZips"], tail,
            )
            os.replace(candidate, final_batch)
        except OSError as exc:
            raise OverlayExportError(
                "PATCH_BATCH_PUBLISH_FAILED", f"atomic batch publication failed: {exc}",
                "output", target_version=tail, relative_path=batch_name,
            ) from exc
        published = True
    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
        if not published and candidate.exists():
            shutil.rmtree(candidate, ignore_errors=True)
    return final_batch, stats, []


# ---------------------------------------------------------------- CLI

def _print_issue_groups(issues: list[Issue]) -> None:
    by_category: dict[str, list[Issue]] = {}
    for issue in issues:
        by_category.setdefault(issue.category, []).append(issue)
    for category in ("layout", "scanner", "archive", "graph"):
        group = by_category.get(category, [])
        if not group:
            print(f"[{category}] 0 issue(s)")
            continue
        print(f"[{category}] {len(group)} issue(s)")
        by_code: dict[str, list[Issue]] = {}
        for issue in group:
            by_code.setdefault(issue.code, []).append(issue)
        for code, members in sorted(by_code.items()):
            print(f"  {code} x{len(members)}")
            for issue in members[:5]:
                print(f"    - {issue.message}"
                      + (f"  [{issue.relative_path}]" if issue.relative_path else ""))
            if len(members) > 5:
                print(f"    ... {len(members) - 5} more")


def cmd_audit(args: argparse.Namespace) -> int:
    scan = scan_chain(
        Path(args.cdn_root), asset_patch_for(Path(args.cdn_root)), digest_mode=args.digest,
    )
    catalog, catalog_issues = build_catalog(
        scan.archives, scan.installed_bytes, scan.entity_lists_relative_path,
    )
    issues = scan.issues + catalog_issues
    print("=== wf_dev_catalog audit ===")
    print(f"CDN root         : {args.cdn_root}")
    print(f"归档总数         : {scan.stats['archives_total']}"
          f"  (digest={scan.stats['digest_mode']})")
    for directory, count in scan.stats["directories"].items():
        print(f"  {directory}: {count}")
    print(f"官方 CSV 安装体积: {scan.installed_bytes}")
    print(f"full base        : {catalog['fullBaseVersion']}")
    print(f"catalog 目标版本 : {catalog['targetVersion']}"
          f"  (官方 {OFFICIAL_TARGET},超出部分即 mod 链)")
    print()
    _print_issue_groups(issues)
    dev_scanner_fatal = next(
        (issue for issue in issues
         if issue.code in ("DEV_INVALID_ARCHIVE_NAME", "DEV_LAYOUT_ENTITYLISTS")),
        None,
    )
    print()
    if dev_scanner_fatal is not None:
        print("dev content:sync 首个硬失败点:", dev_scanner_fatal.line())
    verdict = "PASS" if not issues else "FAIL"
    print(f"verdict: {verdict} ({len(issues)} issue(s))")
    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {
                    "stats": scan.stats,
                    "installedBytes": scan.installed_bytes,
                    "targetVersion": catalog["targetVersion"],
                    "issues": [issue.__dict__ for issue in issues],
                },
                ensure_ascii=False, indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        print(f"JSON 报告: {args.json}")
    return 0 if not issues else 1


def cmd_emit(args: argparse.Namespace) -> int:
    manifest_path, issues, summary = emit_dev_catalog(
        Path(args.cdn_root),
        asset_patch_for(Path(args.cdn_root)),
        Path(args.out) if args.out else None,
        digest_mode=args.digest,
        allow_issues=args.allow_issues,
        canonicalize=not args.raw,
    )
    _print_issue_groups(issues)
    print()
    for key, value in summary.items():
        print(f"{key}: {value}")
    if manifest_path is None:
        print("emit 被阻断:存在 dev 阻断性问题(--allow-issues 可强制产出)")
        return 1
    print(f"[OK] dev catalog 已产出: {manifest_path}")
    return 0


def cmd_heal_layers(args: argparse.Namespace) -> int:
    planned = heal_missing_layers(Path(args.cdn_root), apply=args.apply)
    if not planned:
        print("所有 diff 边三层齐全,无需补占位包。")
        return 0
    print(("已写入" if args.apply else "将写入(dry-run,加 --apply 生效)")
          + f" {len(planned)} 个占位包:")
    for item in planned:
        print(f"  {item}")
    return 0


def cmd_relocate_foreign(args: argparse.Namespace) -> int:
    actions, issues = relocate_foreign_archives(
        Path(args.cdn_root), ASSET_PATCH_ACTIVE, apply=args.apply,
    )
    _print_issue_groups(issues)
    if not actions:
        print("没有外根包需要迁入。")
        return 0 if not issues else 1
    by_kind: dict[str, int] = {}
    for action in actions:
        by_kind[action["action"]] = by_kind.get(action["action"], 0) + 1
        print(f"  [{action['action']}] {action['source']} -> {action['target']}"
              f" ({action['bytes']}B)")
    print(("已迁入" if args.apply else "将迁入(dry-run,加 --apply 生效)")
          + f": {by_kind}")
    if args.apply:
        print(f"回执: {Path(args.cdn_root) / 'dev-catalog' / 'relocate-receipt.json'}")
    return 0 if not issues else 1


def cmd_export_pack(args: argparse.Namespace) -> int:
    pack_dir, stats, issues = export_share_pack(
        Path(args.cdn_root),
        asset_patch_for(Path(args.cdn_root)),
        Path(args.out) if args.out else None,
        since=args.since,
        min_server=args.min_server,
        server_features=tuple(args.server_feature),
        client_patches=tuple(args.client_patch),
    )
    if pack_dir is None:
        print(f"没有高于 {args.since} 的版本边,无可导出。")
        return 1
    for key, value in stats.items():
        print(f"{key}: {value}")
    blocking = [i for i in issues if i.code == "CONFLICTING_ARCHIVE_PATH"]
    if blocking:
        _print_issue_groups(blocking)
        print("[WARN] 存在路径冲突问题,分享前请先排查")
    print(f"[OK] 分享包: {pack_dir}")
    print("打包分发: 直接压缩该目录;收方按 说明.txt 操作。")
    return 0


def cmd_export_overlay(args: argparse.Namespace) -> int:
    try:
        batch_dir, stats, _issues = export_patch_overlays(
            Path(args.cdn_root),
            asset_patch_for(Path(args.cdn_root)),
            Path(args.out) if args.out else None,
            from_version=args.from_ver,
            base_version=args.base_version,
            consolidate=args.consolidate,
            min_server=args.min_server,
            server_features=tuple(args.server_feature),
            client_patches=tuple(args.client_patch),
        )
    except OverlayExportError as exc:
        print(f"[ERR] {exc}", file=sys.stderr)
        return 1
    for key, value in stats.items():
        print(f"{key}: {value}")
    print(f"[OK] Patch Overlay batch: {batch_dir}")
    return 0


def cmd_verify_baseline(args: argparse.Namespace) -> int:
    raw = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    catalog_input = raw["catalogInput"]
    archives = [
        ArchiveInput(
            kind=item["kind"],
            from_version=item["fromVersion"],
            to_version=item["toVersion"],
            platform=item["platform"],
            layer=item["layer"],
            order=item["order"],
            relative_path=item["relativePath"],
            compressed_bytes=item["compressedBytes"],
            sha256=item["sha256"],
        )
        for item in catalog_input["archives"]
    ]
    catalog, issues = build_catalog(
        archives,
        catalog_input["installedBytes"],
        catalog_input["entityListsRelativePath"],
    )
    _print_issue_groups(issues)
    if issues:
        print("verdict: FAIL(金样在本移植下未通过——移植或输入有误)")
        return 1
    print(f"targetVersion    : {catalog['targetVersion']}")
    print(f"fullBaseVersion  : {catalog['fullBaseVersion']}")
    print(f"installedBytes   : {catalog['installedBytes']}")
    print(f"edges            : {len(catalog['edges'])}")
    print(f"archives         : {len(archives)}")
    if args.stat_files:
        cdn_root = Path(args.cdn_root)
        missing = size_mismatch = 0
        for archive in archives:
            absolute = cdn_root / archive.relative_path
            if not absolute.is_file():
                missing += 1
            elif absolute.stat().st_size != archive.compressed_bytes:
                size_mismatch += 1
        print(f"本地文件核对     : missing={missing} size_mismatch={size_mismatch}")
        if missing or size_mismatch:
            return 1
    print("verdict: PASS(金样通过本移植校验)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="dev 分支 CDN Catalog 适配器")
    parser.add_argument(
        "--cdn-root", default=None,
        help="CDN 根(默认按 core 四级解析链定位:env>profile>服务端识别>嵌套遗留)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="按 dev 语义体检现有链")
    audit.add_argument("--digest", choices=("cache", "skip"), default="cache")
    audit.add_argument("--json", help="附加输出 JSON 报告路径")
    audit.set_defaults(func=cmd_audit)

    emit = subparsers.add_parser("emit", help="产出 dev 格式 manifest + EntityLists")
    emit.add_argument("--out", help="输出目录(默认 <cdn>/dev-catalog)")
    emit.add_argument("--digest", choices=("cache", "skip"), default="cache")
    emit.add_argument("--allow-issues", action="store_true",
                      help="存在阻断问题时仍然产出(报告附带)")
    emit.add_argument("--raw", action="store_true",
                      help="跳过规范化(不去重桥接包/不重排 order)")
    emit.set_defaults(func=cmd_emit)

    heal = subparsers.add_parser("heal-layers", help="补齐缺层占位包(默认 dry-run)")
    heal.add_argument("--apply", action="store_true")
    heal.set_defaults(func=cmd_heal_layers)

    relocate = subparsers.add_parser(
        "relocate-foreign", help="外根(asset-patch)包迁入 CDN 根(默认 dry-run,保留原件)"
    )
    relocate.add_argument("--apply", action="store_true")
    relocate.set_defaults(func=cmd_relocate_foreign)

    materialize = subparsers.add_parser(
        "materialize", help="物化 dev 物理扫描合规视图(硬链+合规名,零改现网)"
    )
    materialize.add_argument("--out", help="输出父目录(默认 <cdn>/../dev-view)")
    materialize.add_argument("--digest", choices=("cache", "skip"), default="cache")
    materialize.set_defaults(func=cmd_materialize)

    export = subparsers.add_parser(
        "export-pack", help="导出收方解压即用的分享包(默认整条 mod 链)"
    )
    export.add_argument("--since", default=OFFICIAL_TARGET,
                        help=f"起始版本(不含,默认 {OFFICIAL_TARGET}=完整 mod 链)")
    export.add_argument("--out", help="输出父目录(默认 <cdn>/../share)")
    export.add_argument("--min-server", help="声明最低服务端版本(模式类内容)")
    export.add_argument("--server-feature", action="append", default=[],
                        help="声明需要的服务端功能,可重复(如 rush-mode)")
    export.add_argument("--client-patch", action="append", default=[],
                        help="声明需要的客户端补丁,可重复(如 seris-pcode-v2)")
    export.set_defaults(func=cmd_export_pack)

    overlay = subparsers.add_parser(
        "export-overlay", help="导出 schema 1 Patch Overlay 外层 ZIP 批次"
    )
    overlay.add_argument("--from-ver", required=True,
                         help="显式客户端升级起点版本")
    overlay.add_argument("--base-version",
                         help="可选内容依赖;不参与升级边计算")
    overlay.add_argument("--consolidate", action="store_true",
                         help="显式整合成 from-ver 到最终版本的一条真实边")
    overlay.add_argument("--out", help="原子批次输出父目录(默认 <cdn>/../share)")
    overlay.add_argument("--min-server", help="requires.json 作者元数据:最低服务端版本")
    overlay.add_argument("--server-feature", action="append", default=[],
                         help="requires.json 作者元数据:服务端功能,可重复")
    overlay.add_argument("--client-patch", action="append", default=[],
                         help="requires.json 作者元数据:客户端补丁,可重复")
    overlay.set_defaults(func=cmd_export_overlay)

    verify = subparsers.add_parser("verify-baseline", help="金样验证移植保真度")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--stat-files", action="store_true",
                        help="逐个核对本地文件存在与大小")
    verify.set_defaults(func=cmd_verify_baseline)

    args = parser.parse_args(argv)
    if args.cdn_root is None:
        import wf_mod_tool as core
        try:
            args.cdn_root = str(core.resolve_cdn_root())
        except ValueError as exc:
            print(f"[ERR] {exc}", file=sys.stderr)
            return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

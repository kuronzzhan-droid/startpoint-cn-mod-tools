#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Frozen pending overlay 的只读 manifest 校验与终态合并。"""
from __future__ import annotations

import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import wf_enhancement_policy as policy_mod
from wf_enhancement_policy import CLIENT_ROOTS, EntrySource, sha256

SCHEMA_VERSION = 1
MANIFEST_KEYS = frozenset({
    "schemaVersion", "sourceChainTail", "storePath", "pendingPath",
    "pendingSha256", "pendingSequence", "entries", "overlayDigest",
})
ENTRY_KEYS = frozenset({
    "root", "logicalPath", "hashedRel", "size", "sha256", "codec", "owner",
})
CODECS = frozenset({
    "orderedmap-flat-zlib", "orderedmap-nested-zlib", "raw-deflate", "png",
})
_HEX = frozenset("0123456789abcdef")


class PendingOverlayError(ValueError):
    """Frozen overlay 合同、路径或 live 字节不一致。"""


@dataclass
class PendingOverlay:
    sources: list[EntrySource]
    report: dict
    protected_paths: tuple[Path, ...]


def _manifest_digest(manifest: dict) -> str:
    canonical = dict(manifest)
    canonical.pop("overlayDigest", None)
    return sha256(json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))


def _require_exact_keys(payload: dict, wanted: frozenset[str], label: str) -> None:
    actual = set(payload)
    if actual != wanted:
        missing = sorted(wanted - actual)
        extra = sorted(actual - wanted)
        raise PendingOverlayError(
            f"{label} schema 字段不符: missing={missing}, extra={extra}")


def _manifest_relative(base: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise PendingOverlayError(f"{label} 必须是 manifest 内的非空相对路径")
    relative = Path(value)
    if relative.is_absolute() or relative.drive or any(
        part in ("", ".", "..") for part in relative.parts
    ):
        raise PendingOverlayError(
            f"{label} 必须是 manifest 内安全相对路径，禁止绝对路径/穿越: {value!r}")
    resolved_base = base.resolve()
    cursor = resolved_base
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise PendingOverlayError(f"{label} 不允许经过 symlink: {value!r}")
    resolved = cursor.resolve()
    if resolved == resolved_base or resolved_base not in resolved.parents:
        raise PendingOverlayError(f"{label} 相对路径越出 manifest 目录: {value!r}")
    return resolved


def _explicit_path(value: Path, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise PendingOverlayError(f"{label} 显式覆盖必须是绝对路径: {path}")
    if path.is_symlink():
        raise PendingOverlayError(f"{label} 不允许是 symlink: {path}")
    return path.resolve()


def _validate_logical_path(logical: object) -> str:
    if not isinstance(logical, str) or not logical:
        raise PendingOverlayError("overlay entry logicalPath 必须是非空字符串")
    if ("\\" in logical or logical.startswith("/") or logical.endswith("/")
            or "//" in logical or ":" in logical or "\x00" in logical):
        raise PendingOverlayError(
            f"overlay entry logicalPath 不是规范相对逻辑路径: {logical!r}")
    parts = logical.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise PendingOverlayError(
            f"overlay entry logicalPath 含路径穿越: {logical!r}")
    lowered = logical.lower()
    lowered_parts = [piece.lower() for piece in parts]
    forbidden = (
        any(part.startswith(".env") or part.startswith(".database") for part in
            lowered_parts)
        or any(part == "tmp" or part.startswith(".tmp") for part in lowered_parts)
        or ".bak" in lowered
        or ".tmp" in lowered
        or re.search(r"(^|[/_.-])bots?([/_.-]|$)", lowered) is not None
    )
    if forbidden:
        raise PendingOverlayError(
            f"overlay entry 命中禁入路径(env/database/bak/tmp/bot): {logical}")
    return logical


def _validate_hashed_rel(value: object) -> str:
    if not isinstance(value, str):
        raise PendingOverlayError("overlay entry hashedRel 必须是字符串")
    parts = value.split("/")
    if (len(parts) != 2 or len(parts[0]) != 2 or len(parts[1]) != 38
            or any(char not in _HEX for char in parts[0] + parts[1])):
        raise PendingOverlayError(
            f"overlay entry hashedRel 不是 2/38 小写 SHA-1 路径: {value!r}")
    return value


def _safe_store_file(store_root: Path, rel: str) -> Path:
    unresolved = store_root / Path(rel)
    cursor = store_root
    for part in Path(rel).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise PendingOverlayError(
                f"overlay live payload 不允许 symlink: {cursor}")
    resolved = unresolved.resolve()
    if store_root != resolved and store_root not in resolved.parents:
        raise PendingOverlayError(f"overlay live payload 越出 store root: {rel}")
    if not resolved.is_file():
        raise PendingOverlayError(
            f"overlay live payload 不存在或不是文件: {rel}")
    return resolved


def load_pending_overlay(
    manifest_path: Path,
    *,
    source_chain_tail: str,
    store_root: Path | None = None,
    pending_path: Path | None = None,
) -> PendingOverlay:
    """只读并冻结 manifest/store/pending；任一漂移都 fail closed。"""
    manifest_input = Path(manifest_path)
    if manifest_input.is_symlink():
        raise PendingOverlayError(
            f"pending overlay manifest 不允许 symlink: {manifest_input}")
    manifest_path = manifest_input.resolve()
    if not manifest_path.is_file():
        raise PendingOverlayError(
            f"pending overlay manifest 不存在或不是文件: {manifest_path}")
    manifest_raw = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PendingOverlayError(
            f"pending overlay manifest 不是 UTF-8 JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise PendingOverlayError(
            "pending overlay manifest 顶层必须是 JSON object")
    _require_exact_keys(manifest, MANIFEST_KEYS, "pending overlay manifest")
    schema = manifest["schemaVersion"]
    if isinstance(schema, bool) or schema != SCHEMA_VERSION:
        raise PendingOverlayError(
            f"pending overlay schemaVersion 必须是 {SCHEMA_VERSION}: {schema!r}")
    digest = _manifest_digest(manifest)
    if manifest["overlayDigest"] != digest:
        raise PendingOverlayError(
            "pending overlay overlayDigest 与 canonical manifest 不一致: "
            f"manifest={manifest['overlayDigest']!r}, current={digest}")
    if manifest["sourceChainTail"] != source_chain_tail:
        raise PendingOverlayError(
            "pending overlay sourceChainTail 与当前重放链尾不一致: "
            f"manifest={manifest['sourceChainTail']!r}, current={source_chain_tail!r}")

    base = manifest_path.parent
    default_store = _manifest_relative(base, manifest["storePath"], "storePath")
    default_pending = _manifest_relative(base, manifest["pendingPath"], "pendingPath")
    if store_root is not None:
        explicit_store = _explicit_path(store_root, "pending overlay store")
        if explicit_store != default_store:
            raise PendingOverlayError(
                "pending overlay store 显式路径必须等于 manifest storePath；"
                "禁止用干净副本绕过 live store 漂移")
    if pending_path is not None:
        explicit_pending = _explicit_path(
            pending_path, "pending overlay pending file")
        if explicit_pending != default_pending:
            raise PendingOverlayError(
                "pending overlay pending 显式路径必须等于 manifest pendingPath；"
                "禁止用干净副本绕过 live pending 漂移")
    store_root = default_store
    pending_path = default_pending
    if not store_root.is_dir():
        raise PendingOverlayError(
            f"pending overlay store 不存在或不是目录: {store_root}")
    if pending_path.is_symlink() or not pending_path.is_file():
        raise PendingOverlayError(
            f"pending overlay pending 不存在、不是文件或为 symlink: {pending_path}")

    pending_raw = pending_path.read_bytes()
    pending_digest = sha256(pending_raw)
    if pending_digest != manifest["pendingSha256"]:
        raise PendingOverlayError(
            "pending 文件 SHA-256 已漂移: "
            f"manifest={manifest['pendingSha256']!r}, current={pending_digest}")
    try:
        pending_sequence = json.loads(pending_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PendingOverlayError(
            f"pending 文件不是 UTF-8 JSON: {exc}") from exc
    if pending_sequence != manifest["pendingSequence"]:
        raise PendingOverlayError(
            "pending 当前有序序列与 manifest 不完全一致；拒绝吞入并发/半截改动")
    if (not isinstance(pending_sequence, list)
            or any(not isinstance(item, str) for item in pending_sequence)):
        raise PendingOverlayError("pending 文件必须是字符串有序数组")
    raw_entries = manifest["entries"]
    if not isinstance(raw_entries, list):
        raise PendingOverlayError("pending overlay entries 必须是有序数组")

    sources: list[EntrySource] = []
    entries: list[dict] = []
    derived_pending: list[str] = []
    seen_rel: set[tuple[str, str]] = set()
    seen_logical: set[str] = set()
    for index, item in enumerate(raw_entries):
        if not isinstance(item, dict):
            raise PendingOverlayError(
                f"overlay entry[{index}] 必须是 JSON object")
        _require_exact_keys(item, ENTRY_KEYS, f"overlay entry[{index}]")
        root = item["root"]
        if root not in CLIENT_ROOTS:
            raise PendingOverlayError(
                f"overlay entry[{index}] root 非法: {root!r}")
        logical = _validate_logical_path(item["logicalPath"])
        rel = _validate_hashed_rel(item["hashedRel"])
        expected_rel = policy_mod.quest.hashed_rel(logical)
        if rel != expected_rel:
            raise PendingOverlayError(
                f"overlay entry[{index}] logicalPath 正向哈希不等于 hashedRel: "
                f"{logical!r} -> {expected_rel}, manifest={rel}")
        key = (root, rel)
        if key in seen_rel or logical in seen_logical:
            raise PendingOverlayError(
                f"overlay entry[{index}] 重复 root/rel 或 logicalPath: {logical}")
        seen_rel.add(key)
        seen_logical.add(logical)
        size = item["size"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise PendingOverlayError(
                f"overlay entry[{index}] size 必须是非负整数")
        expected_sha = item["sha256"]
        if (not isinstance(expected_sha, str) or len(expected_sha) != 64
                or any(char not in _HEX for char in expected_sha)):
            raise PendingOverlayError(
                f"overlay entry[{index}] sha256 必须是 64 位小写十六进制")
        codec = item["codec"]
        if not isinstance(codec, str) or codec not in CODECS:
            raise PendingOverlayError(
                f"overlay entry[{index}] 未知 codec: {codec!r}; 允许 {sorted(CODECS)}")
        owner = item["owner"]
        if (not isinstance(owner, str) or not owner.strip()
                or owner != owner.strip() or any(ord(char) < 32 for char in owner)):
            raise PendingOverlayError(
                f"overlay entry[{index}] owner 必须是无首尾空白/控制字符的非空字符串")
        target = _safe_store_file(store_root, rel)
        payload = target.read_bytes()
        actual_sha = sha256(payload)
        if len(payload) != size or actual_sha != expected_sha:
            raise PendingOverlayError(
                f"overlay live payload size/SHA-256 已漂移: {logical}; "
                f"manifest={size}/{expected_sha}, current={len(payload)}/{actual_sha}")
        sources.append(EntrySource(
            root, rel, zlib.crc32(payload), len(payload),
            lambda data=payload: data, len(zlib.compress(payload, 9))))
        entries.append(dict(item))
        derived_pending.append(rel if root == "common" else f"{root}:{rel}")
    if derived_pending != pending_sequence:
        raise PendingOverlayError(
            "pending 有未知路径、顺序漂移或 manifest entries 未一一覆盖 exact sequence")

    return PendingOverlay(sources=sources, report={
        "entryCount": len(entries),
        "manifestSha256": sha256(manifest_raw),
        "overlayDigest": digest,
        "pendingSha256": pending_digest,
        "pendingSequence": list(pending_sequence),
        "entries": entries,
        "publicationReceipt": False,
        "note": "正式 CDN 链 + 冻结未发布 overlay；这不是发布回执。",
    }, protected_paths=(manifest_path, store_root, pending_path))


def merge_pending_overlay(
    chain: Sequence[EntrySource], overlay: PendingOverlay,
) -> list[EntrySource]:
    """overlay 作为最后一层，覆盖同 root/rel 的正式链终态。"""
    merged = {(source.root, source.rel): source for source in chain}
    for source, entry in zip(overlay.sources, overlay.report["entries"]):
        previous = merged.get((source.root, source.rel))
        entry["overridesChain"] = previous is not None
        entry["chainSha256"] = sha256(previous.read()) if previous is not None else None
        entry["overlaySha256"] = entry["sha256"]
        merged[(source.root, source.rel)] = source
    return list(merged.values())

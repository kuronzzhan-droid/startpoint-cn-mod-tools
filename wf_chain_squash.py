#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""链压缩器:把 mod 增量链(>=base)压成"最终版合集"单边 + 全历史版本硬链桥。

背景:客户端 POST /get_path 沿版本图(文件名 pinball-<from>-<to>-<seq>-<tag>.zip)
逐边下载增量,每个 zip 都是整文件替换(后写覆盖先写)。链会无限变长
(1.4.54 起 ~150 条边、GB 级),而全部文件的最终状态只有几十 MiB。

本工具:
  1. 按服务端 cn-asset-graph.ts 的同一套规则重建"客户端可见图"
     (三根 legacy 目录隐藏 -charpkg- + asset-patch/active + active.json 锚定边,
     边内归档按 root 序 common<medium<android<patch 应用);
  2. 沿 base→tail 的路径重放,得到每个 entry 的最终版本,按最后写入者的
     root 分桶(patch 并入 common),打成 pinball-<base>-<tail>-<seq>-<tag>.zip
     (按 --max-zip-mib 拆分,先例 1.4.102 拆 7 包);
  3. 给链上每个历史版本端点建指向同一批 zip 的硬链接别名
     pinball-<v>-<tail>-<seq>-<tag>.zip —— 停在任意中间版本的客户端一跳到
     tail(findReleasePath 同目标取边数少者,桥天然优先)。**没有这一步就是
     2026-07-18 链重锚事故:中间版本被告知"已最新"永久停更**;
  4. verify:旧链全程重放 vs 合集逐 entry(CRC32+size)等价 + 每个历史端点
     可达 tail + tail 不变;
  5. retire:合集验证通过后,把变冗余的旧 legacy zip 移入 retired/ 退役
     (不碰官方段 <base、不碰任何 -charpkg- 文件、不碰 asset-patch)。

用法:
  python mod-tools/wf_chain_squash.py                 # analyze:只读报告
  python mod-tools/wf_chain_squash.py build --dry-run # staging+等价校验后回滚
  python mod-tools/wf_chain_squash.py build           # 落盘合集+桥,写回执
  python mod-tools/wf_chain_squash.py verify --tag squash0725
  python mod-tools/wf_chain_squash.py retire --tag squash0725 --yes
  python mod-tools/wf_chain_squash.py undo --receipt work/chain_squash/xxx.json

安全序:build(自带 verify) → 同步玩家仓 → 真机金丝雀(新装 + .bak 回溯中间版本)
→ 才 retire。active.json 与 charpkg 文件本工具永不改动。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf_release  # noqa: E402

FULL_BASE = "1.4.0"
DEFAULT_BASE = "1.4.54"
CHARPKG_MARK = "-charpkg-"
# 与服务端 cn-asset-graph.ts ARCHIVE_RE 完全一致(seq 无前导零)
ARCHIVE_RE = re.compile(r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-([1-9]\d*)-(.+)\.zip$")
TAG_RE = re.compile(r"^[a-z0-9]+$")
ROOT_ORDER = {"common": 0, "medium": 1, "android": 2, "patch": 3}
# patch 根没有独立归档目录,合集时并入 common
BUCKET_OF_ROOT = {"common": "common", "medium": "medium", "android": "android", "patch": "common"}
WORK_DIR = Path(__file__).resolve().parent / "work" / "chain_squash"


def vkey(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


@dataclass(frozen=True)
class VisibleArchive:
    root: str          # common | medium | android | patch
    path: Path         # 磁盘绝对路径
    relative: str      # 服务端 relativePath(排序键,posix 斜杠)
    source: str        # legacy:<root> | asset-patch:active | character:<id>

    def order_key(self) -> tuple[int, str, str]:
        # 复刻服务端 archiveOrder:root 序 → relativePath → source
        return (ROOT_ORDER[self.root], self.relative, self.source)


@dataclass
class VisibleGraph:
    edges: dict[tuple[str, str], list[VisibleArchive]] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    def add(self, frm: str, to: str, archive: VisibleArchive) -> None:
        if vkey(to) <= vkey(frm):
            self.issues.append(f"non-increasing edge {frm}->{to} from {archive.relative}")
            return
        bucket = self.edges.setdefault((frm, to), [])
        if all(a.root != archive.root or a.relative != archive.relative for a in bucket):
            bucket.append(archive)

    def outgoing(self) -> dict[str, list[tuple[str, str]]]:
        result: dict[str, list[tuple[str, str]]] = {}
        for frm, to in sorted(self.edges, key=lambda e: (vkey(e[0]), vkey(e[1]))):
            result.setdefault(frm, []).append((frm, to))
        return result

    def endpoints(self) -> set[str]:
        found: set[str] = set()
        for frm, to in self.edges:
            found.add(frm)
            found.add(to)
        return found


def _scan_zip_dir(graph: VisibleGraph, directory: Path, root: str, rel_prefix: str,
                  source: str, hide_charpkg: bool) -> None:
    if not directory.is_dir():
        graph.issues.append(f"archive directory is missing: {directory}")
        return
    for name in sorted(p.name for p in directory.iterdir() if p.name.endswith(".zip")):
        if hide_charpkg and CHARPKG_MARK in name:
            continue
        match = ARCHIVE_RE.fullmatch(name)
        if match is None:
            graph.issues.append(f"invalid archive filename: {directory / name}")
            continue
        path = directory / name
        if not path.is_file() or path.stat().st_size <= 0:
            graph.issues.append(f"archive missing or empty: {path}")
            continue
        graph.add(match.group(1), match.group(2),
                  VisibleArchive(root, path, f"{rel_prefix}/{name}", source))


def _add_anchored_edges(graph: VisibleGraph, cdn_root: Path) -> None:
    """active.json 锚定的 charpkg 边(客户端可见,文件名被隐藏)。宽松读,同 guard。"""
    active_path = cdn_root / "character-releases" / "active.json"
    try:
        payload = json.loads(active_path.read_bytes())
    except (OSError, ValueError):
        return
    releases = payload.get("releases") if isinstance(payload, dict) else None
    for release in releases if isinstance(releases, list) else ():
        if not isinstance(release, dict):
            continue
        frm, to = release.get("from_version"), release.get("version")
        if not (isinstance(frm, str) and isinstance(to, str)
                and wf_release.VERSION_RE.fullmatch(frm) and wf_release.VERSION_RE.fullmatch(to)):
            continue
        rid = release.get("release_id", "?")
        for archive in release.get("archives", []) if isinstance(release.get("archives"), list) else ():
            if not isinstance(archive, dict):
                continue
            relative = archive.get("relative_path")
            root = archive.get("root")
            if not isinstance(relative, str) or root not in wf_release.ROOT_DIRS:
                continue
            relative = relative.replace("\\", "/")
            path = cdn_root / relative
            if not path.is_file() or path.stat().st_size <= 0:
                graph.issues.append(f"anchored archive missing: {path}")
                continue
            graph.add(frm, to, VisibleArchive(root, path, relative, f"character:{rid}"))


def build_visible_graph(cdn_root: Path, repo_root: Path) -> VisibleGraph:
    graph = VisibleGraph()
    for root, dirname in wf_release.ROOT_DIRS.items():
        _scan_zip_dir(graph, cdn_root / dirname, root, dirname, f"legacy:{root}", True)
    _scan_zip_dir(graph, repo_root / "assets" / "asset-patch" / "active", "patch",
                  "asset-patch/active", "asset-patch:active", False)
    _add_anchored_edges(graph, cdn_root)
    return graph


def find_path(graph: VisibleGraph, start: str) -> tuple[str, list[tuple[str, str]]]:
    """复刻服务端 findReleasePath:BFS 最短路,取可达最高版本,同版本取边少者。"""
    outgoing = graph.outgoing()
    best: dict[str, list[tuple[str, str]]] = {start: []}
    queue = [start]
    while queue:
        version = queue.pop(0)
        current = best[version]
        for edge in outgoing.get(version, ()):
            candidate = current + [edge]
            previous = best.get(edge[1])
            if previous is not None and len(previous) <= len(candidate):
                continue
            best[edge[1]] = candidate
            queue.append(edge[1])
    target, edges = start, []
    for version, candidate in best.items():
        cmp = (vkey(version) > vkey(target)) - (vkey(version) < vkey(target))
        if cmp > 0 or (cmp == 0 and len(candidate) < len(edges)):
            target, edges = version, candidate
    return target, edges


@dataclass(frozen=True)
class FinalEntry:
    name: str
    root: str            # 最后写入者的 root
    zip_path: Path       # 最后写入者所在 zip
    crc: int
    size: int
    compress_size: int


def replay(graph: VisibleGraph, path_edges: list[tuple[str, str]],
           skip_tag: str | None = None) -> tuple[dict[str, FinalEntry], list[str]]:
    """按服务端应用顺序重放整条路径,返回 entry 终态与边内冲突警告。

    skip_tag:重放时忽略该 tag 的归档(verify 用:排除合集自身看旧链)。
    """
    final: dict[str, FinalEntry] = {}
    conflicts: list[str] = []
    for frm, to in path_edges:
        seen_in_edge: dict[str, tuple[int, int, str]] = {}
        for archive in sorted(graph.edges[(frm, to)], key=VisibleArchive.order_key):
            match = ARCHIVE_RE.fullmatch(archive.path.name)
            if skip_tag is not None and match is not None and match.group(4) == skip_tag:
                continue
            with zipfile.ZipFile(archive.path) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    identity = (info.CRC, info.file_size)
                    prior = seen_in_edge.get(info.filename)
                    if prior is not None and prior[:2] != identity:
                        conflicts.append(
                            f"edge {frm}->{to}: {info.filename} differs between "
                            f"{prior[2]} and {archive.relative} (applied later wins)"
                        )
                    seen_in_edge[info.filename] = (*identity, archive.relative)
                    final[info.filename] = FinalEntry(
                        info.filename, archive.root, archive.path,
                        info.CRC, info.file_size, info.compress_size,
                    )
    return final, conflicts


# ---------------------------------------------------------------- squash 构建

@dataclass
class PlannedPart:
    root: str
    seq: int
    entries: list[FinalEntry]
    est_bytes: int


def plan_parts(final: dict[str, FinalEntry], max_zip_bytes: int) -> list[PlannedPart]:
    """按最后写入者 root 分桶(patch→common),名字序稳定切分。"""
    buckets: dict[str, list[FinalEntry]] = {}
    for entry in final.values():
        buckets.setdefault(BUCKET_OF_ROOT[entry.root], []).append(entry)
    parts: list[PlannedPart] = []
    overhead = 128  # zip 目录项/头的粗略预留
    # 重压缩尺寸与源 compress_size 有小偏差,预留余量保证实际产物不破 CI 上限
    budget = max_zip_bytes - max(64 << 10, max_zip_bytes // 64)
    for root in ("common", "medium", "android"):
        entries = sorted(buckets.get(root, ()), key=lambda e: e.name)
        if not entries:
            continue
        current: list[FinalEntry] = []
        size = 0
        seq = 1
        for entry in entries:
            cost = entry.compress_size + overhead
            if current and size + cost > budget:
                parts.append(PlannedPart(root, seq, current, size))
                current, size, seq = [], 0, seq + 1
            current.append(entry)
            size += cost
        parts.append(PlannedPart(root, seq, current, size))
    return parts


def part_name(base: str, tail: str, seq: int, tag: str) -> str:
    return f"pinball-{base}-{tail}-{seq}-{tag}.zip"


def write_parts(parts: list[PlannedPart], staging: Path, base: str, tail: str,
                tag: str, max_zip_bytes: int) -> list[tuple[PlannedPart, Path]]:
    staging.mkdir(parents=True, exist_ok=True)
    handles: dict[Path, zipfile.ZipFile] = {}
    written: list[tuple[PlannedPart, Path]] = []
    try:
        for part in parts:
            out_path = staging / part.root / part_name(base, tail, part.seq, tag)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for entry in part.entries:
                    source = handles.get(entry.zip_path)
                    if source is None:
                        source = handles[entry.zip_path] = zipfile.ZipFile(entry.zip_path)
                    zf.writestr(entry.name, source.read(entry.name))
            actual = out_path.stat().st_size
            if actual > max_zip_bytes:
                print(f"[WARN] {out_path.name} ({part.root}) {actual} B 超过上限 "
                      f"{max_zip_bytes} B(单文件过大无法再拆)")
            written.append((part, out_path))
    finally:
        for handle in handles.values():
            handle.close()
    return written


def bridge_versions(graph: VisibleGraph, base: str, tail: str) -> list[str]:
    """需要建桥的历史版本端点:base <= v < tail(不含官方段 <base)。"""
    versions = {v for v in graph.endpoints() if vkey(base) <= vkey(v) < vkey(tail)}
    return sorted(versions, key=vkey)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _link_or_copy(source: Path, target: Path) -> None:
    try:
        os.link(source, target)
    except OSError:
        temp = target.with_name(f".{target.name}.tmp")
        shutil.copy2(source, temp)
        os.replace(temp, target)


# ------------------------------------------------------------------- 校验

def verify_squash(cdn_root: Path, repo_root: Path, base: str, tag: str) -> list[str]:
    """返回问题列表;空 = 通过。旧链仍在时做全程等价,已退役则跳过等价only可达性。"""
    problems: list[str] = []
    graph = build_visible_graph(cdn_root, repo_root)
    problems += [f"graph: {issue}" for issue in graph.issues]

    tail, path_edges = find_path(graph, base)
    squash_edge = graph.edges.get((base, tail))
    squash_archives = [] if squash_edge is None else [
        a for a in squash_edge
        if (m := ARCHIVE_RE.fullmatch(a.path.name)) is not None and m.group(4) == tag
    ]
    if not squash_archives:
        return problems + [f"no squash archives with tag {tag} on edge {base}->{tail}"]

    # 1) 每个历史端点必须能到 tail
    outgoing = graph.outgoing()
    for version in bridge_versions(graph, base, tail):
        reach, _ = find_path(graph, version)
        if reach != tail:
            problems.append(f"stranded: {version} stops at {reach} (tail {tail})")
    # base 一跳直达(桥优先生效的抽查)
    _, base_path = find_path(graph, base)
    if len(base_path) != 1:
        problems.append(f"path from {base} uses {len(base_path)} edges; squash edge not preferred")

    # 2) 合集内容 vs 旧链全程重放逐 entry 等价
    old_graph = VisibleGraph()
    for edge, archives in graph.edges.items():
        kept = [a for a in archives
                if (m := ARCHIVE_RE.fullmatch(a.path.name)) is None or m.group(4) != tag]
        if kept:
            old_graph.edges[edge] = kept
    old_tail, old_path = find_path(old_graph, base)
    if old_tail != tail:
        problems.append(f"equivalence skipped: old chain retired (reaches {old_tail}, tail {tail})")
        old_final = None
    else:
        old_final, _ = replay(old_graph, old_path)

    squash_graph = VisibleGraph()
    squash_graph.edges[(base, tail)] = squash_archives
    new_final, _ = replay(squash_graph, [(base, tail)])

    if old_final is not None:
        for name, entry in old_final.items():
            got = new_final.get(name)
            if got is None:
                problems.append(f"squash missing entry: {name}")
            elif (got.crc, got.size) != (entry.crc, entry.size):
                problems.append(f"squash content differs: {name}")
        for name in new_final:
            if name not in old_final:
                problems.append(f"squash has extra entry: {name}")
    return problems


# ------------------------------------------------------------------- 命令

def _resolve_dirs(args) -> tuple[Path, Path]:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parent.parent
    if args.cdn:
        cdn_root = Path(args.cdn).resolve()
    elif os.environ.get("WF_CDN_DIR"):
        cdn_root = Path(os.environ["WF_CDN_DIR"]).resolve()
    else:
        cdn_root = repo_root / ".cdn" / "cn"
    return cdn_root, repo_root


def cmd_analyze(args) -> int:
    cdn_root, repo_root = _resolve_dirs(args)
    graph = build_visible_graph(cdn_root, repo_root)
    tail, path_edges = find_path(graph, args.base)
    final, conflicts = replay(graph, path_edges)
    parts = plan_parts(final, args.max_zip_mib << 20)
    versions = bridge_versions(graph, args.base, tail)
    chain_bytes = sum(a.path.stat().st_size for edge in path_edges for a in graph.edges[edge])
    union_bytes = sum(e.compress_size for e in final.values())

    print(f"可见图: {len(graph.edges)} 条边, issues {len(graph.issues)}")
    for issue in graph.issues:
        print(f"  [ISSUE] {issue}")
    print(f"mod 链: {args.base} → {tail}, 路径 {len(path_edges)} 条边, 现存 {chain_bytes / 2**20:.1f} MiB")
    for conflict in conflicts:
        print(f"  [边内冲突] {conflict}")
    print(f"合集: {len(final)} 个 entry, 压缩约 {union_bytes / 2**20:.1f} MiB")
    for part in parts:
        print(f"  {part.root} #{part.seq}: {len(part.entries)} entries ~{part.est_bytes / 2**20:.2f} MiB")
    print(f"桥: {len(versions)} 个版本 × {len(parts)} 个 zip = {len(versions) * len(parts)} 个硬链接")
    print(f"预计: 旧链 {chain_bytes / 2**20:.1f} MiB → 合集 {union_bytes / 2**20:.1f} MiB")
    return 0


def cmd_build(args) -> int:
    cdn_root, repo_root = _resolve_dirs(args)
    if not TAG_RE.fullmatch(args.tag) or "charpkg" in args.tag or "charbridge" in args.tag:
        print(f"[ERR] tag 必须是纯 [a-z0-9] 且不含 charpkg/charbridge: {args.tag}")
        return 2
    with wf_release._release_lock(cdn_root / ".character-release.lock"):
        return _build_locked(args, cdn_root, repo_root)


def _build_locked(args, cdn_root: Path, repo_root: Path) -> int:
    graph = build_visible_graph(cdn_root, repo_root)
    tail, path_edges = find_path(graph, args.base)
    if not path_edges:
        print(f"[ERR] {args.base} 出发没有任何可见边")
        return 2
    primary = part_name(args.base, tail, 1, args.tag)
    for dirname in wf_release.ROOT_DIRS.values():
        if (cdn_root / dirname / primary).exists():
            print(f"[ERR] 已存在同 tag 合集 {primary};换 tag 或先 undo")
            return 2

    final, conflicts = replay(graph, path_edges)
    for conflict in conflicts:
        print(f"[边内冲突] {conflict}")
    parts = plan_parts(final, args.max_zip_mib << 20)
    staging = cdn_root / f".squash-staging-{args.tag}"
    if staging.exists():
        shutil.rmtree(staging)
    written = write_parts(parts, staging, args.base, tail, args.tag, args.max_zip_mib << 20)
    print(f"staging: {len(written)} 个 zip @ {staging}")

    # staging 内容 vs 旧链等价(落盘前把好第一道门)
    stage_graph = VisibleGraph()
    stage_graph.edges[(args.base, tail)] = [
        VisibleArchive(part.root, path, f"staging/{part.root}/{path.name}", "staging")
        for part, path in written
    ]
    staged_final, _ = replay(stage_graph, [(args.base, tail)])
    mismatch = [name for name, entry in final.items()
                if (staged_final.get(name) is None
                    or (staged_final[name].crc, staged_final[name].size) != (entry.crc, entry.size))]
    mismatch += [name for name in staged_final if name not in final]
    if mismatch:
        shutil.rmtree(staging)
        print(f"[ERR] staging 等价校验失败 {len(mismatch)} 项: {mismatch[:5]}")
        return 2
    print(f"staging 等价校验通过: {len(staged_final)} entries")

    if args.dry_run:
        shutil.rmtree(staging)
        print("[dry-run] 校验通过,已回滚 staging,盘上无变化")
        return 0

    # 落盘:主文件进各 root 目录,再为每个历史版本建硬链桥
    versions = bridge_versions(graph, args.base, tail)
    created: list[dict] = []
    try:
        placed: list[tuple[PlannedPart, Path]] = []
        for part, staged_path in written:
            target = cdn_root / wf_release.ROOT_DIRS[part.root] / staged_path.name
            os.replace(staged_path, target)
            created.append({"path": str(target), "sha256": _sha256(target)})
            placed.append((part, target))
        for version in versions:
            if version == args.base:
                continue
            for part, primary_path in placed:
                alias = primary_path.with_name(part_name(version, tail, part.seq, args.tag))
                if alias.exists():
                    continue
                _link_or_copy(primary_path, alias)
                created.append({"path": str(alias), "sha256": _sha256(alias)})
    except Exception:
        for item in reversed(created):
            Path(item["path"]).unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(staging, ignore_errors=True)

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    receipt = WORK_DIR / f"build-{args.tag}-{time.strftime('%Y%m%dt%H%M%S')}.json"
    receipt.write_text(json.dumps({
        "kind": "build", "tag": args.tag, "base": args.base, "tail": tail,
        "created": created,
    }, indent=2), encoding="utf-8")
    print(f"落盘 {len(created)} 个文件(合集 {len(written)} + 桥 {len(created) - len(written)}), 回执 {receipt}")

    problems = verify_squash(cdn_root, repo_root, args.base, args.tag)
    if problems:
        print(f"[ERR] 落盘后校验失败,自动回滚 {len(created)} 个文件:")
        for problem in problems:
            print(f"  {problem}")
        for item in reversed(created):
            Path(item["path"]).unlink(missing_ok=True)
        return 2
    print(f"verify 通过: {args.base}→{tail} 一跳直达, {len(versions)} 个历史版本全部可达 tail")
    print("下一步: 同步玩家仓 → 真机金丝雀(新装 + 回溯中间版本) → 全绿后再 retire")
    return 0


def cmd_verify(args) -> int:
    cdn_root, repo_root = _resolve_dirs(args)
    problems = verify_squash(cdn_root, repo_root, args.base, args.tag)
    hard = [p for p in problems if not p.startswith("equivalence skipped")]
    for note in problems:
        if note.startswith("equivalence skipped"):
            print(f"[NOTE] {note}")
    if hard:
        for problem in hard:
            print(f"[FAIL] {problem}")
        return 1
    print("verify 通过")
    return 0


def _retire_candidates(cdn_root: Path, base: str, tail: str, tag: str) -> list[Path]:
    """可退役 = 三根目录里 base<=from、to<=tail 的非 charpkg legacy zip(含 charbridge),
    排除本 tag 自己的合集/桥。asset-patch 与官方段(<base)不碰。"""
    candidates: list[Path] = []
    for dirname in wf_release.ROOT_DIRS.values():
        directory = cdn_root / dirname
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            match = ARCHIVE_RE.fullmatch(path.name)
            if match is None or CHARPKG_MARK in path.name:
                continue
            if match.group(4) == tag:
                continue
            if vkey(match.group(1)) >= vkey(base) and vkey(match.group(2)) <= vkey(tail):
                candidates.append(path)
    return candidates


def cmd_retire(args) -> int:
    cdn_root, repo_root = _resolve_dirs(args)
    problems = verify_squash(cdn_root, repo_root, args.base, args.tag)
    hard = [p for p in problems if not p.startswith("equivalence skipped")]
    if hard:
        for problem in hard:
            print(f"[FAIL] {problem}")
        print("[ERR] 合集校验未通过,拒绝退役")
        return 2
    graph = build_visible_graph(cdn_root, repo_root)
    tail, _ = find_path(graph, args.base)
    candidates = _retire_candidates(cdn_root, args.base, tail, args.tag)
    if not candidates:
        print("没有可退役的旧包")
        return 0

    # 模拟退役后图:每个端点仍须可达 tail 且 tail 不变
    removed = {path.resolve() for path in candidates}
    sim = VisibleGraph()
    sim.edges = {edge: kept for edge, archives in graph.edges.items()
                 if (kept := [a for a in archives if a.path.resolve() not in removed])}
    sim_tail, _ = find_path(sim, args.base)
    stranded = [v for v in bridge_versions(graph, args.base, tail)
                if find_path(sim, v)[0] != tail]
    if sim_tail != tail or stranded:
        print(f"[ERR] 模拟退役后 tail={sim_tail}, 搁浅 {stranded[:5]};拒绝退役")
        return 2

    total = sum(path.stat().st_size for path in candidates)
    print(f"退役 {len(candidates)} 个 zip, 目录体积 {total / 2**20:.1f} MiB → retired/{args.tag}/")
    if not args.yes:
        print("[dry-run] 加 --yes 执行移动")
        return 0
    with wf_release._release_lock(cdn_root / ".character-release.lock"):
        moves: list[dict] = []
        for path in candidates:
            target = cdn_root / "retired" / args.tag / path.parent.name / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(path, target)
            moves.append({"from": str(path), "to": str(target)})
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        receipt = WORK_DIR / f"retire-{args.tag}-{time.strftime('%Y%m%dt%H%M%S')}.json"
        receipt.write_text(json.dumps({"kind": "retire", "tag": args.tag, "moves": moves},
                                      indent=2), encoding="utf-8")
    print(f"完成,回执 {receipt}(undo 可整体还原)")
    return 0


def cmd_undo(args) -> int:
    payload = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    if payload.get("kind") == "retire":
        restored = 0
        for move in reversed(payload.get("moves", [])):
            source, target = Path(move["to"]), Path(move["from"])
            if source.is_file() and not target.exists():
                os.replace(source, target)
                restored += 1
        print(f"还原 {restored}/{len(payload.get('moves', []))} 个文件")
        return 0
    if payload.get("kind") == "build":
        removed = 0
        for item in reversed(payload.get("created", [])):
            path = Path(item["path"])
            if path.is_file() and _sha256(path) == item["sha256"]:
                path.unlink()
                removed += 1
        print(f"删除 {removed}/{len(payload.get('created', []))} 个本次创建的文件")
        return 0
    print(f"[ERR] 未知回执类型: {payload.get('kind')}")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", default="analyze",
                        choices=["analyze", "build", "verify", "retire", "undo"])
    parser.add_argument("--base", default=DEFAULT_BASE, help="mod 链起点(默认 1.4.54)")
    parser.add_argument("--tag", default=time.strftime("squash%m%d"),
                        help="合集 tag,纯 [a-z0-9](默认 squashMMDD)")
    parser.add_argument("--max-zip-mib", type=int, default=5, help="单 zip 上限 MiB(CI 门禁 5)")
    parser.add_argument("--cdn", help="CDN 根(默认 WF_CDN_DIR 或 <repo>/.cdn/cn)")
    parser.add_argument("--repo-root", help="仓库根(默认按脚本位置)")
    parser.add_argument("--dry-run", action="store_true", help="build:staging+校验后回滚")
    parser.add_argument("--yes", action="store_true", help="retire:真正移动文件")
    parser.add_argument("--receipt", help="undo:回执 json 路径")
    args = parser.parse_args(argv)
    if args.command == "undo" and not args.receipt:
        parser.error("undo 需要 --receipt")
    return {
        "analyze": cmd_analyze, "build": cmd_build, "verify": cmd_verify,
        "retire": cmd_retire, "undo": cmd_undo,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

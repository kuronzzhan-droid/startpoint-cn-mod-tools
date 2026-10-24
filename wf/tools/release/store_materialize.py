#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Materialize the CN CDN archive stack into a fresh three-root store tree.

Exit codes: 0 = ok, 2 = plan/write error (MaterializeError), 3 = chain break --
the visible graph holds edges above the materialized tail whose start version
cannot be reached from the official base, so the store silently stops at an old
tail (2026-07-17 rollback incident, docs/self-host-modes.md "前提 0"). Only the
default auto-tail mode fails; --tail / --official-only / --allow-partial-chain
state an intent, so they downgrade the same finding to a warning.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import threading
import zipfile
import zlib
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import wf_chain_squash
import wf_mod_tool
import wf_offline_store


ROOT_NAMES = ("common", "medium", "android")
ROOT_DIRECTORIES = {
    "common": "upload",
    "medium": "medium_upload",
    "android": "android_upload",
}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
FULL_ARCHIVE_RE = re.compile(r"^pinball-1\.4\.0-([1-9]\d*)-(.+)\.zip$")
# JSON 里最多列几条够不到的边(全量可能上百条,样例足够定位)
SAMPLE_LIMIT = 5


class MaterializeError(RuntimeError):
    """The requested store cannot be planned or safely materialized."""


@dataclass(frozen=True, slots=True)
class PlannedEntry:
    name: str
    root: str
    relative: str
    zip_path: Path
    crc: int
    size: int


@dataclass(frozen=True, slots=True)
class ChainHealth:
    """链体检:可见图里够不到的边 + 链上可见的最高版本 + 建图告警。"""

    max_visible: str = ""
    unreachable: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()

    def gap(self, tail: str) -> bool:
        if not self.max_visible or not tail:
            return False
        return wf_chain_squash.vkey(self.max_visible) > wf_chain_squash.vkey(tail)


@dataclass(frozen=True, slots=True)
class MaterializePlan:
    tail: str
    entries: dict[tuple[str, str], PlannedEntry]
    rejected: int
    edge_count: int
    health: ChainHealth = ChainHealth()

    def summary(self, *, ok: bool = True) -> dict[str, object]:
        per_root = {
            root: {
                "files": sum(entry.root == root for entry in self.entries.values()),
                "bytes": sum(
                    entry.size for entry in self.entries.values() if entry.root == root
                ),
            }
            for root in ROOT_NAMES
        }
        return {
            "ok": ok,
            "tail": self.tail,
            "files": len(self.entries),
            "bytes": sum(entry.size for entry in self.entries.values()),
            "rejected": self.rejected,
            "per_root": per_root,
            "unreachable_edges": len(self.health.unreachable),
            "unreachable_samples": list(self.health.unreachable[:SAMPLE_LIMIT]),
            "max_visible_version": self.health.max_visible,
            "chain_issues": list(self.health.issues),
        }


def _is_placeholder(name: str) -> bool:
    return name in (".empty", ".empty/")


def _ensure_empty_destination(destination: Path) -> None:
    if not destination.exists():
        return
    if not destination.is_dir():
        raise MaterializeError(f"destination is not a directory: {destination}")
    if any(destination.iterdir()):
        raise MaterializeError(f"destination must be nonexistent or empty: {destination}")


def _full_archive_order(archive_path: Path) -> tuple[int, str]:
    if archive_path.is_symlink() or not archive_path.is_file():
        raise MaterializeError(f"unsafe full archive path: {archive_path}")
    match = FULL_ARCHIVE_RE.fullmatch(archive_path.name)
    if match is None:
        raise MaterializeError(f"noncanonical full archive filename: {archive_path.name}")
    sequence = int(match.group(1))
    if sequence > wf_chain_squash.MAX_ARCHIVE_SEQ:
        raise MaterializeError(
            "full archive sequence exceeds "
            f"{wf_chain_squash.MAX_ARCHIVE_SEQ}: {archive_path.name}: {match.group(1)}"
        )
    return sequence, archive_path.name


def _scan_full_archives(cdn_root: Path) -> tuple[dict[tuple[str, str], PlannedEntry], int]:
    entries: dict[tuple[str, str], PlannedEntry] = {}
    rejected = 0
    for archive_root in ROOT_NAMES:
        directory = cdn_root / f"archive-{archive_root}-full"
        if not directory.is_dir():
            raise MaterializeError(f"full archive directory is missing: {directory}")
        archive_paths = [path for path in directory.iterdir() if path.name.endswith(".zip")]
        for archive_path in sorted(archive_paths, key=_full_archive_order):
            try:
                with zipfile.ZipFile(archive_path) as archive:
                    for info in archive.infolist():
                        if _is_placeholder(info.filename):
                            continue
                        try:
                            root, relative = wf_offline_store._parse_archive_member(
                                info.filename, legacy=False
                            )
                        except wf_offline_store.StoreError:
                            rejected += 1
                            continue
                        entries[(root, relative)] = PlannedEntry(
                            name=info.filename,
                            root=root,
                            relative=relative,
                            zip_path=archive_path,
                            crc=info.CRC,
                            size=info.file_size,
                        )
            except (OSError, zipfile.BadZipFile) as error:
                raise MaterializeError(f"cannot read full archive {archive_path}: {error}") from error
    return entries, rejected


def _targeted_path(
    graph: wf_chain_squash.VisibleGraph, start: str, target: str
) -> list[tuple[str, str]]:
    if VERSION_RE.fullmatch(target) is None:
        raise MaterializeError(f"invalid target version: {target}")
    outgoing = graph.outgoing()
    best: dict[str, list[tuple[str, str]]] = {start: []}
    queue: deque[str] = deque([start])
    while queue:
        version = queue.popleft()
        current = best[version]
        for edge in outgoing.get(version, ()):
            candidate = current + [edge]
            previous = best.get(edge[1])
            if previous is not None and len(previous) <= len(candidate):
                continue
            best[edge[1]] = candidate
            queue.append(edge[1])
    if target not in best:
        raise MaterializeError(f"target tail is unreachable from {start}: {target}")
    return best[target]


def _reachable(graph: wf_chain_squash.VisibleGraph, start: str) -> set[str]:
    outgoing = graph.outgoing()
    seen = {start}
    queue: deque[str] = deque([start])
    while queue:
        for _frm, to in outgoing.get(queue.popleft(), ()):
            if to not in seen:
                seen.add(to)
                queue.append(to)
    return seen


def _edge_label(
    graph: wf_chain_squash.VisibleGraph, edge: tuple[str, str]
) -> str:
    archives = sorted(archive.relative for archive in graph.edges.get(edge, ()))
    if not archives:
        return f"{edge[0]}->{edge[1]}"
    extra = f" (+{len(archives) - 1})" if len(archives) > 1 else ""
    return f"{edge[0]}->{edge[1]} {archives[0]}{extra}"


def _chain_health(
    graph: wf_chain_squash.VisibleGraph, tail: str, *, official_only: bool = False
) -> ChainHealth:
    """够不到的边 = 起点从 FULL_BASE 走不到、且终点高于 tail 的边。

    2026-07-17 野外事故就长这样:官方基座链尾停在 1.4.54,mod 边从 1.4.90 起,
    工具沿图只能走到 1.4.54 却照样 ok:true —— 拿这棵落后的 store 发布会把客户端
    滚回几十个版本(docs/self-host-modes.md「前提 0」)。

    终点 <= tail 的不可达边不是缺陷:wf_chain_squash 的硬链接桥就是成批的
    "中间版本 -> 合集"别名边(实测本仓 7 条),它们的起点本来就不在基座链上,
    内容也早已被 tail 覆盖 —— 按起点一刀切会在健康的链上误报。
    """
    versions = graph.endpoints() | {wf_chain_squash.FULL_BASE, tail}
    max_visible = max(versions, key=wf_chain_squash.vkey)
    if official_only:
        # --official-only 停在官方段是模式契约,不是链断。
        return ChainHealth(max_visible, (), tuple(graph.issues))
    reachable = _reachable(graph, wf_chain_squash.FULL_BASE)
    stranded = sorted(
        (
            edge
            for edge in graph.edges
            if edge[0] not in reachable
            and wf_chain_squash.vkey(edge[1]) > wf_chain_squash.vkey(tail)
        ),
        key=lambda edge: (wf_chain_squash.vkey(edge[0]), wf_chain_squash.vkey(edge[1])),
    )
    return ChainHealth(
        max_visible,
        tuple(_edge_label(graph, edge) for edge in stranded),
        tuple(graph.issues),
    )


def _official_graph(
    graph: wf_chain_squash.VisibleGraph,
) -> wf_chain_squash.VisibleGraph:
    filtered = wf_chain_squash.VisibleGraph(issues=list(graph.issues))
    for (frm, to), archives in graph.edges.items():
        for archive in archives:
            if archive.source.startswith("legacy:"):
                filtered.add(frm, to, archive)
    return filtered


def _diff_plan(
    cdn_root: Path,
    repo_root: Path,
    target_tail: str | None,
    official_only: bool,
) -> tuple[str, dict[tuple[str, str], PlannedEntry], int, int, ChainHealth]:
    graph = wf_chain_squash.build_visible_graph(cdn_root, repo_root)
    if official_only:
        # --official-only 的契约就是只要官方段:体检也只看官方图,mod 边够不到
        # 是这个模式的预期而非缺陷。
        graph = _official_graph(graph)
        tail = target_tail or wf_chain_squash.DEFAULT_BASE
        if VERSION_RE.fullmatch(tail) is None:
            raise MaterializeError(f"invalid target version: {tail}")
        if (
            wf_chain_squash.vkey(tail) < wf_chain_squash.vkey(wf_chain_squash.FULL_BASE)
            or wf_chain_squash.vkey(tail)
            > wf_chain_squash.vkey(wf_chain_squash.DEFAULT_BASE)
        ):
            raise MaterializeError(
                "--official-only tail must be between "
                f"{wf_chain_squash.FULL_BASE} and {wf_chain_squash.DEFAULT_BASE}: {tail}"
            )
        path_edges = _targeted_path(graph, wf_chain_squash.FULL_BASE, tail)
    elif target_tail is None:
        tail, path_edges = wf_chain_squash.find_path(
            graph, wf_chain_squash.FULL_BASE
        )
    else:
        tail = target_tail
        path_edges = _targeted_path(graph, wf_chain_squash.FULL_BASE, tail)
    health = _chain_health(graph, tail, official_only=official_only)
    rejected = 0
    for edge in path_edges:
        for visible in sorted(graph.edges[edge], key=wf_chain_squash.VisibleArchive.order_key):
            try:
                with zipfile.ZipFile(visible.path) as archive:
                    for info in archive.infolist():
                        if _is_placeholder(info.filename):
                            continue
                        try:
                            wf_offline_store._parse_archive_member(
                                info.filename, legacy=False
                            )
                        except wf_offline_store.StoreError:
                            rejected += 1
            except (OSError, zipfile.BadZipFile) as error:
                raise MaterializeError(
                    f"cannot validate diff archive {visible.path}: {error}"
                ) from error

    try:
        raw_final, _conflicts = wf_chain_squash.replay(graph, path_edges)
    except (OSError, zipfile.BadZipFile) as error:
        raise MaterializeError(f"cannot replay diff chain: {error}") from error

    entries: dict[tuple[str, str], PlannedEntry] = {}
    for name, final in raw_final.items():
        if _is_placeholder(name):
            continue
        try:
            root, relative = wf_offline_store._parse_archive_member(name, legacy=False)
        except wf_offline_store.StoreError:
            continue
        entries[(root, relative)] = PlannedEntry(
            name=name,
            root=root,
            relative=relative,
            zip_path=final.zip_path,
            crc=final.crc,
            size=final.size,
        )
    return tail, entries, rejected, len(path_edges), health


def _build_plan(
    cdn_root: Path,
    repo_root: Path,
    target_tail: str | None,
    official_only: bool,
) -> MaterializePlan:
    entries, rejected = _scan_full_archives(cdn_root)
    tail, diff_entries, diff_rejected, edge_count, health = _diff_plan(
        cdn_root, repo_root, target_tail, official_only
    )
    entries.update(diff_entries)
    return MaterializePlan(
        tail, entries, rejected + diff_rejected, edge_count, health
    )


build_read_only_plan = _build_plan


def _write_plan(plan: MaterializePlan, destination: Path, workers: int) -> None:
    roots = {
        root: destination / "production" / directory
        for root, directory in ROOT_DIRECTORIES.items()
    }
    for root in roots.values():
        root.mkdir(parents=True, exist_ok=True)

    grouped: dict[Path, list[PlannedEntry]] = defaultdict(list)
    for entry in sorted(plan.entries.values(), key=lambda item: (item.root, item.relative)):
        grouped[entry.zip_path].append(entry)

    total = len(plan.entries)
    if total == 0:
        print("0/0")
        return
    interval = max(1, total // 100)
    progress = 0
    lock = threading.Lock()

    def write_archive(archive_path: Path, entries: list[PlannedEntry]) -> int:
        nonlocal progress
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for entry in entries:
                    info = archive.getinfo(entry.name)
                    if info.file_size != entry.size or info.CRC != entry.crc:
                        raise MaterializeError(
                            f"archive member changed after planning: {archive_path}!{entry.name}"
                        )
                    target = roots[entry.root] / entry.relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                    with lock:
                        progress += 1
                        if progress == total or progress % interval == 0:
                            print(f"{progress}/{total}")
            return len(entries)
        except MaterializeError:
            raise
        except (KeyError, OSError, zipfile.BadZipFile) as error:
            raise MaterializeError(f"cannot materialize {archive_path}: {error}") from error

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(write_archive, archive_path, entries)
            for archive_path, entries in sorted(grouped.items(), key=lambda item: str(item[0]))
        ]
        for future in as_completed(futures):
            future.result()


def _verify_plan(plan: MaterializePlan, destination: Path, workers: int) -> None:
    production = destination / "production"
    roots = wf_offline_store.StoreRoots(
        common=production / ROOT_DIRECTORIES["common"],
        medium=production / ROOT_DIRECTORIES["medium"],
        android=production / ROOT_DIRECTORIES["android"],
    )
    try:
        report = wf_offline_store.enumerate_hashed_members(roots)
    except wf_offline_store.StoreError as error:
        raise MaterializeError(f"store verification scan failed: {error}") from error

    expected = plan.entries
    actual = {member.key: member for member in report.members}
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    if missing or unexpected:
        raise MaterializeError(
            "store verification member mismatch: "
            f"missing={missing[:3]} unexpected={unexpected[:3]}"
        )
    for key, planned in expected.items():
        if actual[key].size != planned.size:
            raise MaterializeError(
                f"store verification size mismatch: {key} "
                f"expected={planned.size} actual={actual[key].size}"
            )

    def crc32(path: Path) -> int:
        checksum = 0
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                checksum = zlib.crc32(chunk, checksum)
        return checksum & 0xFFFFFFFF

    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {
            executor.submit(crc32, member.source): key
            for key, member in actual.items()
        }
        for future in as_completed(pending):
            key = pending[future]
            try:
                checksum = future.result()
            except OSError as error:
                raise MaterializeError(
                    f"store verification cannot read {actual[key].source}: {error}"
                ) from error
            if checksum != expected[key].crc:
                raise MaterializeError(
                    f"store verification CRC mismatch: {key} "
                    f"expected={expected[key].crc:08x} actual={checksum:08x}"
                )


def _new_profile_paths(server_dir: Path | None) -> dict[str, str]:
    """新建档案的路径键:只写解析得到且真实存在的目录,拿不到就不写这个键。"""
    if server_dir is None:
        return {}
    try:
        resolved = server_dir.resolve()
    except OSError:
        return {}
    if not resolved.is_dir():
        return {}
    paths = {"server_dir": str(resolved)}
    cdndata = resolved / "assets" / "cdndata"
    if cdndata.is_dir():
        paths["cdndata"] = str(cdndata)
    return paths


def _write_profile(
    profiles_path: Path,
    store_root: Path,
    res_version: str,
    server_dir: Path | None = None,
) -> Path | None:
    profiles_path = profiles_path.absolute()
    original: bytes | None
    if profiles_path.exists():
        try:
            original = profiles_path.read_bytes()
            payload = json.loads(original.decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise MaterializeError(f"cannot read profiles file {profiles_path}: {error}") from error
        if not isinstance(payload, dict):
            raise MaterializeError(f"profiles file must contain a JSON object: {profiles_path}")
    else:
        original = None
        payload = {}

    profiles = payload.get("profiles")
    if profiles is None:
        profiles = {}
    if not isinstance(profiles, dict):
        raise MaterializeError("profiles field must be a JSON object")
    active = payload.get("active")
    if not isinstance(active, str) or not active:
        active = "cn"
        payload["active"] = active
    current = profiles.get(active)
    if current is None:
        # 新建档案:res_version 必须是真正物化到的链尾(写死 DEFAULT_BASE 会让
        # 后续发布拿 1.4.54 当基线),再补上 GUI ①层与 CDN 解析要用的两把路径钥匙。
        current = {
            "label": "国服(雷霆)" if active == "cn" else active,
            "res_version": res_version or wf_chain_squash.DEFAULT_BASE,
            **_new_profile_paths(server_dir),
        }
    elif not isinstance(current, dict):
        raise MaterializeError(f"profile {active!r} must be a JSON object")
    else:
        current = dict(current)
        # 已有档案:只补**缺失**的键,绝不覆盖用户已填的值。缺 cdndata 的症状是
        # GUI 角色列表静默为空(界面不报错),新手很难查到是档案少了一个键;
        # _new_profile_paths 只返回磁盘上真实存在的目录,所以补不上时是不写,而不是写错。
        for key, value in _new_profile_paths(server_dir).items():
            if not current.get(key):
                current[key] = value
                print(f"[profile] filled missing {key}: {value}", file=sys.stderr)
    current["store"] = str(store_root.resolve())
    profiles[active] = current
    payload["profiles"] = profiles

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if original is not None:
        backup = profiles_path.with_name(
            profiles_path.name + f".bak-materialize-{timestamp}"
        )
        try:
            shutil.copy2(profiles_path, backup)
        except OSError as error:
            raise MaterializeError(f"cannot back up profiles file: {error}") from error

    temporary = profiles_path.with_name(
        f".{profiles_path.name}.materialize-{timestamp}.tmp"
    )
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    try:
        with temporary.open("xb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, profiles_path)
    except OSError as error:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise MaterializeError(f"cannot write profiles file {profiles_path}: {error}") from error
    return backup


def _empty_summary(tail: str = "") -> dict[str, object]:
    return {
        "ok": False,
        "tail": tail,
        "files": 0,
        "bytes": 0,
        "rejected": 0,
        "per_root": {
            root: {"files": 0, "bytes": 0} for root in ROOT_NAMES
        },
        "unreachable_edges": 0,
        "unreachable_samples": [],
        "max_visible_version": "",
        "chain_issues": [],
    }


def _report_chain_health(
    plan: MaterializePlan, *, official_only: bool, allow_partial: bool,
    explicit_tail: bool,
) -> bool:
    """把建图告警与「够不到的边」打到 stderr;返回 True 表示必须失败退出。

    只有默认模式(自动取可达最高版本)才致命 —— 那正是链断了也无声无息的路径;
    --tail 是用户指名道姓要的版本,--official-only 只要官方段,两者降级为告警。
    """
    health = plan.health
    for issue in health.issues:
        print(f"[WARN] chain issue: {issue}", file=sys.stderr)
    if official_only or not health.unreachable:
        if health.gap(plan.tail) and not official_only:
            print(
                f"[WARN] chain stops at {plan.tail} while the visible chain shows "
                f"{health.max_visible}; check --tail before publishing this store.",
                file=sys.stderr,
            )
        return False
    fatal = not allow_partial and not explicit_tail
    level = "ERR" if fatal else "WARN"
    print(
        f"[{level}] chain break: materialized tail={plan.tail} but the visible chain "
        f"reaches {health.max_visible} -- "
        f"{len(health.unreachable)} edge(s) cannot be reached from "
        f"{wf_chain_squash.FULL_BASE} and were dropped:",
        file=sys.stderr,
    )
    for label in health.unreachable[:SAMPLE_LIMIT]:
        print(f"[{level}]   unreachable edge: {label}", file=sys.stderr)
    if len(health.unreachable) > SAMPLE_LIMIT:
        print(
            f"[{level}]   ... and {len(health.unreachable) - SAMPLE_LIMIT} more",
            file=sys.stderr,
        )
    print(
        f"[{level}] this store would be a {plan.tail} baseline: publishing it over a "
        f"{health.max_visible} client rolls the client back "
        "(2026-07-17 incident, docs/self-host-modes.md 前提 0). "
        "Repair the base chain (bridge the gap) first.",
        file=sys.stderr,
    )
    print(
        f"[{level}] only need the official segment? use --official-only "
        "(it stops at the official tail by contract and never trips this gate; "
        "the GUI toolbox card exposes it). "
        "--allow-partial-chain accepts a knowingly partial store instead.",
        file=sys.stderr,
    )
    return fatal


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize CDN archives into a fresh World Flipper store"
    )
    parser.add_argument("--cdn", type=Path, help="CN CDN root (defaults to profile resolution)")
    parser.add_argument("--dest", type=Path, required=True, help="fresh output directory")
    parser.add_argument("--tail", help="target version (default: highest reachable)")
    parser.add_argument("--official-only", action="store_true")
    parser.add_argument(
        # 刻意**不**进 GUI 工具箱卡片:这是绕过安全门禁的开关,而门禁存在的理由就是
        # 2026-07-17 那次「拿落后 store 发布把客户端滚回 71 版」的事故。GUI 用户真正
        # 需要的场景(只要官方段)已由 --official-only 覆盖,那个是暴露在卡片上的。
        # 命令行的那点摩擦在这里是特性,不是缺陷 —— 别"顺手"给它加复选框。
        "--allow-partial-chain",
        action="store_true",
        help="downgrade the unreachable-edge failure to a warning (partial store)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="plan only (default)")
    mode.add_argument("--apply", action="store_true", help="write the planned store")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--server-dir", type=Path)
    parser.add_argument("--write-profile", action="store_true")
    parser.add_argument("--profiles", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    summary = _empty_summary(args.tail or "")
    try:
        if args.workers <= 0:
            raise MaterializeError("--workers must be a positive integer")
        cdn_root = args.cdn if args.cdn is not None else wf_mod_tool.resolve_cdn_root()
        destination = args.dest.absolute()
        _ensure_empty_destination(destination)
        repo_root = (
            args.server_dir if args.server_dir is not None else wf_mod_tool.resolve_server_dir()
        )
        plan = _build_plan(
            cdn_root.absolute(), repo_root.absolute(), args.tail, args.official_only
        )
        summary = plan.summary()
        print(
            f"[plan] tail={plan.tail} edges={plan.edge_count} files={summary['files']} "
            f"bytes={summary['bytes']} rejected={plan.rejected}"
        )
        fatal = _report_chain_health(
            plan,
            official_only=args.official_only,
            allow_partial=args.allow_partial_chain,
            explicit_tail=args.tail is not None,
        )
        if fatal:
            # 链断了就地停手:此时还没写过任何文件,绝不产出会滚回客户端的 store。
            print(json.dumps(plan.summary(ok=False), ensure_ascii=False,
                             separators=(",", ":")))
            return 3
        if args.apply:
            _write_plan(plan, destination, args.workers)
            if args.verify:
                _verify_plan(plan, destination, args.workers)
                print(f"[verify] files={len(plan.entries)}")
            if args.write_profile:
                profiles_path = (
                    args.profiles if args.profiles is not None else wf_mod_tool.profiles_file()
                )
                backup = _write_profile(
                    profiles_path,
                    destination / "production" / ROOT_DIRECTORIES["common"],
                    plan.tail,
                    repo_root,
                )
                suffix = f" backup={backup}" if backup is not None else ""
                print(f"[profile] updated={profiles_path}{suffix}")
        print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (MaterializeError, OSError, ValueError) as error:
        summary = dict(summary)
        summary["ok"] = False
        print(f"[ERR] {error}", file=sys.stderr)
        print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

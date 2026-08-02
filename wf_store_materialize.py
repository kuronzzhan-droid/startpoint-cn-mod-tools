#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Materialize the CN CDN archive stack into a fresh three-root store tree."""
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
class MaterializePlan:
    tail: str
    entries: dict[tuple[str, str], PlannedEntry]
    rejected: int
    edge_count: int

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


def _scan_full_archives(cdn_root: Path) -> tuple[dict[tuple[str, str], PlannedEntry], int]:
    entries: dict[tuple[str, str], PlannedEntry] = {}
    rejected = 0
    for archive_root in ROOT_NAMES:
        directory = cdn_root / f"archive-{archive_root}-full"
        if not directory.is_dir():
            raise MaterializeError(f"full archive directory is missing: {directory}")
        for archive_path in sorted(directory.glob("*.zip"), key=lambda path: path.name):
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
) -> tuple[str, dict[tuple[str, str], PlannedEntry], int, int]:
    graph = wf_chain_squash.build_visible_graph(cdn_root, repo_root)
    if official_only:
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
    return tail, entries, rejected, len(path_edges)


def _build_plan(
    cdn_root: Path,
    repo_root: Path,
    target_tail: str | None,
    official_only: bool,
) -> MaterializePlan:
    entries, rejected = _scan_full_archives(cdn_root)
    tail, diff_entries, diff_rejected, edge_count = _diff_plan(
        cdn_root, repo_root, target_tail, official_only
    )
    entries.update(diff_entries)
    return MaterializePlan(tail, entries, rejected + diff_rejected, edge_count)


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


def _write_profile(profiles_path: Path, store_root: Path) -> Path | None:
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
        current = {
            "label": "国服(雷霆)" if active == "cn" else active,
            "res_version": wf_chain_squash.DEFAULT_BASE,
        }
    elif not isinstance(current, dict):
        raise MaterializeError(f"profile {active!r} must be a JSON object")
    else:
        current = dict(current)
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
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize CDN archives into a fresh World Flipper store"
    )
    parser.add_argument("--cdn", type=Path, help="CN CDN root (defaults to profile resolution)")
    parser.add_argument("--dest", type=Path, required=True, help="fresh output directory")
    parser.add_argument("--tail", help="target version (default: highest reachable)")
    parser.add_argument("--official-only", action="store_true")
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
                    profiles_path, destination / "production" / ROOT_DIRECTORIES["common"]
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

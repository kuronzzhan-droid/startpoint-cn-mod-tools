#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全执行冻结的 1.4.312 本地终态迁移；默认只做 dry-run。"""
from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import wf_mod_tool as core
from wf_release_migrate_contract import DEFAULT_CONTRACT_PATH, load_frozen_contract
from wf_release_migrate_plan import (
    CHARACTER_LOGICAL,
    CHARACTER_TEXT_LOGICAL,
    CLIENT_LOGICALS,
    SERVER_CHARACTER,
    SERVER_CHARACTER_TEXT,
    SERVER_EQUIPMENT_LOOKUP,
    SERVER_FILES,
    SHOP_LOGICAL,
    ClientRowSpec,
    ClientSourceSpec,
    FrozenContract,
    MigrationError,
    MigrationPlan,
    NameJsonSpec,
    NameRowSpec,
    ServerRowSpec,
    plan_terminal_migration,
    strict_json_object,
)


CONFIRM_TOKEN = "APPLY_RELEASE_1_4_312_MIGRATION"
REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@dataclass(frozen=True, slots=True)
class FileIdentity:
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class TargetSnapshot:
    raw: bytes
    identity: FileIdentity


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _lstat(path: Path) -> os.stat_result:
    try:
        return os.lstat(path)
    except OSError as exc:
        raise MigrationError(f"cannot lstat migration path {path}: {exc}") from exc


def _is_reparse(path: Path, info: os.stat_result) -> bool:
    junction = getattr(path, "is_junction", None)
    return (
        stat.S_ISLNK(info.st_mode)
        or bool(getattr(info, "st_file_attributes", 0) & REPARSE_ATTRIBUTE)
        or bool(junction and junction())
    )


def _safe_file(root: Path, target: Path) -> Path:
    """按 lstat 验证 root 到 target 的每层，拒绝链接、junction/reparse。"""
    root, target = _absolute(root), _absolute(target)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise MigrationError(f"target escapes configured root: {target}") from exc
    try:
        resolved_root, resolved_target = root.resolve(strict=True), target.resolve(strict=True)
    except OSError as exc:
        raise MigrationError(f"cannot resolve migration target {target}: {exc}") from exc
    if (
        os.path.normcase(os.fspath(resolved_root)) != os.path.normcase(os.fspath(root))
        or os.path.normcase(os.fspath(resolved_target)) != os.path.normcase(os.fspath(target))
    ):
        raise MigrationError(f"migration path resolves through a link/reparse point: {target}")
    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise MigrationError(f"resolved target escapes configured root: {target}") from exc
    components = (root, *(root / Path(*relative.parts[:index]) for index in range(1, len(relative.parts) + 1)))
    for index, component in enumerate(components):
        info = _lstat(component)
        if _is_reparse(component, info):
            raise MigrationError(f"symlink/junction/reparse path is forbidden: {component}")
        final = index == len(components) - 1
        if final and not stat.S_ISREG(info.st_mode):
            raise MigrationError(f"migration target is not a regular file: {component}")
        if not final and not stat.S_ISDIR(info.st_mode):
            raise MigrationError(f"migration parent is not a directory: {component}")
    return target


def _target_paths(
    client_root: Path, server_root: Path,
) -> tuple[dict[str, Path], dict[str, Path]]:
    candidates_client = {
        logical: core.table_path(_absolute(client_root), logical)
        for logical in CLIENT_LOGICALS
    }
    candidates_server = {
        relative: _absolute(server_root).joinpath(*relative.split("/"))
        for relative in SERVER_FILES
    }
    clients = {
        logical: _safe_file(client_root, target)
        for logical, target in candidates_client.items()
    }
    servers = {
        relative: _safe_file(server_root, target)
        for relative, target in candidates_server.items()
    }
    return clients, servers


def _identity(path: Path) -> FileIdentity:
    info = _lstat(path)
    if _is_reparse(path, info) or not stat.S_ISREG(info.st_mode):
        raise MigrationError(f"migration target identity became unsafe: {path}")
    return FileIdentity(info.st_dev, info.st_ino)


def _snapshot(path: Path) -> TargetSnapshot:
    before = _identity(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise MigrationError(f"cannot read migration target {path}: {exc}") from exc
    after = _identity(path)
    if before != after:
        raise MigrationError(f"target identity drifted while reading: {path}")
    return TargetSnapshot(raw, before)


def _assert_snapshot(path: Path, expected: TargetSnapshot) -> None:
    actual = _snapshot(path)
    if actual.identity != expected.identity or actual.raw != expected.raw:
        raise MigrationError(f"target bytes/identity drifted after planning: {path}")


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":  # Windows has no portable directory fsync.
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _stage_bytes(target: Path, raw: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
    )
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if staged.read_bytes() != raw:
            raise MigrationError(f"staging readback mismatch: {target}")
        return staged
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        staged.unlink(missing_ok=True)
        raise


def _commit_replace(staged: Path, target: Path) -> None:
    os.replace(staged, target)


def _atomic_restore(target: Path, raw: bytes) -> None:
    staged = _stage_bytes(target, raw)
    try:
        os.replace(staged, target)
        _fsync_directory(target.parent)
        if target.read_bytes() != raw:
            raise MigrationError(f"rollback readback mismatch: {target}")
    finally:
        staged.unlink(missing_ok=True)


def _verify_readback(
    client_paths: Mapping[str, Path], server_paths: Mapping[str, Path],
    expected: Mapping[Path, bytes], contract: FrozenContract,
) -> None:
    for path, raw in expected.items():
        if path.read_bytes() != raw:
            raise MigrationError(f"write readback mismatch: {path}")
    plan = plan_terminal_migration(
        {logical: path.read_bytes() for logical, path in client_paths.items()},
        {relative: path.read_bytes() for relative, path in server_paths.items()},
        contract=contract,
    )
    if plan.changes:
        raise MigrationError("write readback is not terminal/no-op")


def _apply_plan(
    client_paths: Mapping[str, Path], server_paths: Mapping[str, Path],
    snapshots: Mapping[Path, TargetSnapshot], plan: MigrationPlan,
    contract: FrozenContract,
) -> int:
    expected: dict[Path, bytes] = {}
    for logical, path in client_paths.items():
        if plan.client_after[logical] != snapshots[path].raw:
            expected[path] = plan.client_after[logical]
    for relative, path in server_paths.items():
        if plan.server_after[relative] != snapshots[path].raw:
            expected[path] = plan.server_after[relative]
    if not expected:
        print("[NO-OP] 所有冻结迁移目标已是 1.4.312 终态。")
        return 0

    staged: dict[Path, Path] = {}
    replaced: list[tuple[Path, bytes, FileIdentity | None]] = []
    try:
        for target, raw in expected.items():
            staged[target] = _stage_bytes(target, raw)
        # 统一复读全部六个 target；任何 replace 之前先消除规划后的并发漂移。
        for path, snapshot in snapshots.items():
            _assert_snapshot(path, snapshot)
        for target, temporary in staged.items():
            # 每次 replace 前再次检查，避免较晚目标被并发写入后遭覆盖。
            _assert_snapshot(target, snapshots[target])
            try:
                _commit_replace(temporary, target)
            except Exception:
                # 防御“replace 已完成但后续封装抛错”的实现或测试注入。
                if target.exists() and target.read_bytes() == expected[target]:
                    replaced.append((target, snapshots[target].raw, _identity(target)))
                raise
            # os.replace 已成功后立刻登记；即使后续 identity/fsync 失败也必须回滚。
            replaced.append((target, snapshots[target].raw, None))
            replaced[-1] = (target, snapshots[target].raw, _identity(target))
            _fsync_directory(target.parent)
        _verify_readback(client_paths, server_paths, expected, contract)
    except BaseException:
        errors: list[str] = []
        for target, raw, committed_identity in reversed(replaced):
            try:
                actual_identity = _identity(target)
                if (
                    (committed_identity is not None and actual_identity != committed_identity)
                    or target.read_bytes() != expected[target]
                ):
                    raise MigrationError(f"rollback target changed after this transaction: {target}")
                _atomic_restore(target, raw)
            except BaseException as exc:
                errors.append(f"{target}: {exc}")
        if errors:
            print("[ERR] rollback failed: " + " | ".join(errors), file=sys.stderr)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
    print(f"[OK] 原子写入并复读 {len(expected)} 个目标；未发布 CDN。")
    return 0


def main(
    argv: Sequence[str] | None = None, *, contract: FrozenContract | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="1.4.312 精确终态迁移（默认 dry-run）")
    parser.add_argument("--client-root", type=Path, required=True)
    parser.add_argument("--server-root", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args(argv)
    if args.write and args.confirm != CONFIRM_TOKEN:
        print(f"[ERR] --write requires --confirm {CONFIRM_TOKEN}", file=sys.stderr)
        return 1
    try:
        frozen = contract if contract is not None else load_frozen_contract(args.contract)
        client_paths, server_paths = _target_paths(args.client_root, args.server_root)
        snapshots = {
            path: _snapshot(path)
            for path in (*client_paths.values(), *server_paths.values())
        }
        plan = plan_terminal_migration(
            {logical: snapshots[path].raw for logical, path in client_paths.items()},
            {relative: snapshots[path].raw for relative, path in server_paths.items()},
            contract=frozen,
        )
        print(f"[PLAN] {len(plan.changes)} 个迁移单元；目标文件均已完成内存规划。")
        for change in plan.changes:
            print(f"[PLAN] {change}")
        if not args.write:
            print("[DRY-RUN] 未写入；本工具不会发布 CDN 或操作设备。")
            return 0
        return _apply_plan(client_paths, server_paths, snapshots, plan, frozen)
    except Exception as exc:
        print(f"[ERR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

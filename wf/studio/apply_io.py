"""Confined, recoverable file transactions for explicitly enabled local targets."""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from wf.paths import REPOSITORY, profile_data
from .drafts import DraftError
from .rehearsal_io import inside, read_json, server_root, server_name, protected_roots

APPLIED = REPOSITORY / "work/studio-applied"
MANIFEST = "assets/asset-patch/manifest.json"
CLIENT_RISK = "客户端已下载过这条边时，服务端版本回退不会还原客户端；客户端可能无法继续更新。需人工处理版本与资源，或制作更高版本修复边；本工具不操作客户端。"


class RecoveryRequired(DraftError):
    """Leave the server lock in place until an operator reconciles the receipt."""


def sha(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def target(root, relative):
    path = inside(root, relative)
    current = Path(root)
    for part in relative.split("/"):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise DraftError("应用路径不能包含链接：" + relative)
    if path.exists() and (not path.is_file() or path.stat().st_nlink > 1):
        raise DraftError("应用目标必须为普通单链接文件：" + relative)
    return path


def content(path):
    return path.read_bytes() if path.exists() else None


def enabled_root(name):
    server_name(name)
    config, _ = profile_data()
    servers = config.get("servers", {})
    entry = servers.get(name) if isinstance(servers, dict) else None
    if not isinstance(entry, dict) or entry.get("apply_enabled") is not True:
        raise DraftError(f"拒绝应用：servers.{name}.apply_enabled 必须为 true")
    root = server_root(name)
    if not root.is_dir():
        raise DraftError("服务端根目录不存在")
    return root


def receipt_folder(folder, root, server="local"):
    name = folder.parent.name if folder.name == "delivery" else folder.name
    identity = sha((str(root.resolve()) + "\n" + str(folder.resolve())).encode())[:20]
    result = inside(APPLIED, server_name(server) + "/" + name + "-" + identity)
    roots = [root, *protected_roots()]
    if any(result.is_relative_to(p) or APPLIED.resolve().is_relative_to(p) for p in roots):
        raise DraftError("应用备份必须位于服务端目录之外")
    return result


@contextmanager
def server_lock(root):
    """Serialize Studio processes without placing a lock in the server tree."""
    lock_dir = APPLIED / ".locks"
    if any(lock_dir.resolve().is_relative_to(p) for p in [root, *protected_roots()]):
        raise DraftError("应用锁必须位于服务端目录之外")
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = lock_dir / (sha(str(root).encode()) + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise DraftError("此服务端已有应用事务；若进程中断，请先核对回执再人工移除锁") from exc
    keep = False
    try:
        os.close(fd)
        yield
    except RecoveryRequired:
        keep = True
        raise
    finally:
        if not keep:
            lock.unlink()


def atomic_write(path, raw, *, before_replace=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".studio-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if before_replace is not None:
            before_replace()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def verify(root, expected):
    for relative, digest in expected.items():
        if sha(content(target(root, relative))) != digest:
            raise DraftError("文件摘要变化，拒绝写入：" + relative)


def transact(root, changes, expected, steps, before_manifest=None):
    """Optimistic checks include the manifest before every write and at commit."""
    done, created_dirs = [], []
    try:
        verify(root, expected)
        for relative, before, after in changes:
            verify(root, expected)
            if before_manifest is not None and relative == MANIFEST:
                from .rehearsal_server import chain_tail
                if chain_tail(read_json(target(root, MANIFEST))) != before_manifest:
                    raise DraftError("写入前链尾已变化")
            path = target(root, relative)
            missing = []
            parent = path.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            created_dirs.extend(reversed(missing))
            # Record before mutation so failure after replace is recoverable too.
            done.append((relative, before, after))
            if after is None:
                path.unlink()
            else:
                atomic_write(path, after, before_replace=lambda: verify(root, expected))
            expected[relative] = sha(after)
            steps.append({"step": "write", "path": relative, "status": "done"})
        verify(root, expected)
    except Exception:
        errors = []
        for relative, before, after in reversed(done):
            try:
                path = target(root, relative)
                actual = content(path)
                if sha(actual) == sha(before):
                    continue
                if sha(actual) != sha(after):
                    raise DraftError("回滚拒绝覆盖并发改动：" + relative)
                if before is None:
                    path.unlink()
                else:
                    atomic_write(path, before, before_replace=lambda: verify(root, {relative: sha(after)}))
            except Exception as exc:
                errors.append(str(exc))
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        steps.append({"step": "rollback", "status": "failed" if errors else "done", "errors": errors})
        if errors:
            raise RecoveryRequired("回滚未完成，需要按备份人工恢复：" + "; ".join(errors))
        raise

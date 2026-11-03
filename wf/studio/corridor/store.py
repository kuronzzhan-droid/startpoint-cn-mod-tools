"""Editor state on disk: workspace with revision lock, import base bytes, snapshots, audit log.

Layout under the configured store directory (never inside the repository by default)::

    workspace.json         current draft (optimistic revision)
    base/<file>            raw bytes of the runtime files at import (byte-identical rebuilds)
    snapshots/<id>/        immutable workspace copies (workspace.json + meta.json)
    releases/<ver12>/      immutable release packages (see releases.py)
    trial/                 deploy state + append-only deploy log
    audit.jsonl            append-only edit log
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from . import jsonio
from .workspace import dump, now


class ConflictError(Exception):
    """Stale revision / expected state mismatch (HTTP 409)."""


class StoreError(Exception):
    """Bad request against the store (HTTP 400)."""


SNAPSHOT_ID = re.compile(r"^s\d{4}-\d{8}T\d{6}$")


class CorridorStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.lock = threading.RLock()

    # -- paths ------------------------------------------------------------
    @property
    def workspace_path(self) -> Path:
        return self.root / "workspace.json"

    @property
    def base_dir(self) -> Path:
        return self.root / "base"

    @property
    def releases_dir(self) -> Path:
        return self.root / "releases"

    @property
    def trial_dir(self) -> Path:
        return self.root / "trial"

    # -- workspace --------------------------------------------------------
    def exists(self) -> bool:
        return self.workspace_path.is_file()

    def load(self) -> dict:
        with self.lock:
            if not self.exists():
                raise StoreError("还没有回廊工作区：请先「从源文件导入」")
            return jsonio.read_json(self.workspace_path)

    def save(self, workspace: dict, expected_revision: int | None, action: str, detail=None) -> dict:
        """Write a new revision; ``expected_revision`` None only for the very first import."""
        with self.lock:
            current = jsonio.read_json(self.workspace_path)["revision"] if self.exists() else None
            if current != expected_revision:
                raise ConflictError(f"工作区已被改动（当前 revision {current}，请求基于 {expected_revision}），请刷新后重做")
            workspace["revision"] = (current or 0) + 1
            jsonio.atomic_write(self.workspace_path, dump(workspace))
            self.audit({"action": action, "revision_before": current, "revision_after": workspace["revision"],
                        "detail": detail})
            return workspace

    def base_raw(self) -> dict[str, bytes]:
        if not self.base_dir.is_dir():
            return {}
        return {p.name: p.read_bytes() for p in self.base_dir.iterdir() if p.is_file()}

    def write_base(self, raws: dict[str, bytes]) -> None:
        with self.lock:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            for old in self.base_dir.iterdir():
                if old.is_file() and old.name not in raws:
                    old.unlink()
            for name, raw in raws.items():
                jsonio.atomic_write(self.base_dir / name, raw)

    # -- audit --------------------------------------------------------------
    def audit(self, entry: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"at": now(), **entry}, ensure_ascii=False)
        with open(self.root / "audit.jsonl", "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def audit_tail(self, limit: int = 50) -> list[dict]:
        path = self.root / "audit.jsonl"
        if not path.is_file():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(line) for line in reversed(lines) if line.strip()]

    # -- snapshots ----------------------------------------------------------
    def snapshot(self, workspace: dict, message: str, kind: str = "manual") -> dict:
        with self.lock:
            root = self.root / "snapshots"
            root.mkdir(parents=True, exist_ok=True)
            seq = 1 + max((int(p.name[1:5]) for p in root.iterdir() if SNAPSHOT_ID.match(p.name)), default=0)
            stamp = now().replace("-", "").replace(":", "")[:15]
            sid = f"s{seq:04d}-{stamp}"
            target = root / sid
            target.mkdir()
            jsonio.atomic_write(target / "workspace.json", dump(workspace))
            meta = {"id": sid, "revision": workspace["revision"], "message": message, "kind": kind,
                    "created_at": now(), "digest": jsonio.digest(workspace["data"])}
            jsonio.write_json(target / "meta.json", meta)
            return meta

    def snapshots(self) -> list[dict]:
        root = self.root / "snapshots"
        if not root.is_dir():
            return []
        metas = []
        for p in sorted(root.iterdir(), reverse=True):
            if SNAPSHOT_ID.match(p.name) and (p / "meta.json").is_file():
                metas.append(jsonio.read_json(p / "meta.json"))
        return metas

    def load_snapshot(self, sid: str) -> dict:
        if not SNAPSHOT_ID.match(sid or ""):
            raise StoreError("快照 ID 无效")
        path = self.root / "snapshots" / sid / "workspace.json"
        if not path.is_file():
            raise StoreError(f"没有快照 {sid}")
        return jsonio.read_json(path)

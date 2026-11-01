"""Draft workspace: ``work/studio-drafts/<cid>/`` = files + ``changeset.json``.

A draft only records *what would replace what*. It never writes a game table,
the store, a patch chain, a server or a device. Every change is validated
against ``schemas/studio-draft.schema.json`` before it is written, and the
whole changeset again on every write, so a half-valid file never lands.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import secrets
import shutil
import threading
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY / "schemas" / "studio-draft.schema.json"
SCHEMA_ID = "wf-studio-draft/1"
_CID = re.compile(r"^([0-9]{1,9}|scratch-[a-z0-9][a-z0-9-]{0,47})$")
_SAFE_REL = re.compile(r"^(files|sources)/[A-Za-z0-9_./\-]+$")


class DraftError(ValueError):
    """Invalid draft request; message is shown to the user / agent as is."""


def default_root() -> Path:
    override = os.environ.get("WF_STUDIO_DRAFTS")
    return Path(override) if override else REPOSITORY / "work" / "studio-drafts"


def now() -> str:
    return _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_change_id() -> str:
    return "c-" + secrets.token_hex(6)


_schema_cache: dict | None = None


def schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(SCHEMA_PATH.read_text("utf-8"))
    return _schema_cache


def _validator(ref: str | None = None):
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
        raise RuntimeError("缺少 jsonschema：pip install -r requirements.txt") from exc
    document = schema()
    if ref is None:
        return jsonschema.Draft202012Validator(document)
    # Validate against one $defs entry while keeping $ref resolution inside the document.
    wrapper = {"$schema": document["$schema"], "$ref": "#/$defs/" + ref, "$defs": document["$defs"]}
    return jsonschema.Draft202012Validator(wrapper)


def schema_errors(value, ref: str | None = None) -> list[str]:
    errors = sorted(_validator(ref).iter_errors(value), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(map(str, e.absolute_path)) or '(根)'}: {e.message}" for e in errors]


def validate(value, ref: str | None = None) -> None:
    problems = schema_errors(value, ref)
    if problems:
        raise DraftError("不符合 studio-draft.schema.json：" + "；".join(problems[:6]))


class DraftStore:
    """One directory per character. Thread-safe within a process."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_root()
        self._lock = threading.RLock()

    # -- paths ----------------------------------------------------------
    def directory(self, cid: str) -> Path:
        if not _CID.match(cid or ""):
            raise DraftError(f"角色 ID 无效：{cid!r}")
        return self.root / cid

    def resolve(self, cid: str, relative: str) -> Path:
        if not _SAFE_REL.match(relative or "") or ".." in relative.split("/"):
            raise DraftError(f"草稿内路径无效：{relative!r}")
        base = self.directory(cid).resolve()
        target = (base / relative).resolve()
        if not target.is_relative_to(base):
            raise DraftError("草稿路径越界")
        return target

    # -- changeset ------------------------------------------------------
    def load(self, cid: str) -> dict | None:
        path = self.directory(cid) / "changeset.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text("utf-8"))

    def load_or_new(self, cid: str, code: str, base_view: str) -> dict:
        current = self.load(cid)
        if current is None and cid.startswith("scratch-"):
            raise DraftError(f"没有草稿角色 {cid}（先「新建草稿角色」）")
        if current is not None:
            if current.get("code") != code:
                raise DraftError(f"草稿代码名 {current.get('code')} 与当前视图 {code} 不一致")
            return current
        stamp = now()
        return {"schema": SCHEMA_ID, "characterId": cid, "code": code, "baseView": base_view,
                "createdAt": stamp, "updatedAt": stamp, "savedAt": None, "revision": 0, "savedRevision": None,
                "changes": []}

    def _write(self, cid: str, changeset: dict) -> None:
        validate(changeset)
        directory = self.directory(cid)
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / "changeset.json.tmp"
        temporary.write_text(json.dumps(changeset, ensure_ascii=False, indent=1), "utf-8", newline="\n")
        os.replace(temporary, directory / "changeset.json")

    def write_file(self, cid: str, relative: str, data: bytes) -> Path:
        target = self.resolve(cid, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, target)
        return target

    def read_file(self, cid: str, relative: str) -> bytes | None:
        target = self.resolve(cid, relative)
        return target.read_bytes() if target.is_file() else None

    @staticmethod
    def same_target(a: dict, b: dict) -> bool:
        return a["kind"] == b["kind"] and a["target"] == b["target"]

    def put_change(self, cid: str, code: str, base_view: str, change: dict) -> dict:
        """Add ``change`` (replacing an earlier change with the same target)."""
        validate(change, "change")
        with self._lock:
            changeset = self.load_or_new(cid, code, base_view)
            kept, dropped = [], []
            for item in changeset["changes"]:
                (dropped if self.same_target(item, change) else kept).append(item)
            changeset["changes"] = kept + [change]
            changeset["updatedAt"] = now()
            changeset["revision"] += 1
            self._write(cid, changeset)
            self._prune(cid, changeset, dropped)
            return changeset

    def put_changes(self, cid: str, code: str, base_view: str, changes: list[dict]) -> tuple[dict, list[dict]]:
        """Add several changes as one revision (same-target changes are replaced).

        Returns (changeset, dropped); the caller prunes ``dropped`` files with :meth:`prune`
        once the surrounding operation succeeded, so a rollback still finds them.
        """
        for change in changes:
            validate(change, "change")
        with self._lock:
            changeset = self.load_or_new(cid, code, base_view)
            kept, dropped = [], []
            for item in changeset["changes"]:
                (dropped if any(self.same_target(item, c) for c in changes) else kept).append(item)
            changeset["changes"] = kept + list(changes)
            changeset["updatedAt"] = now()
            changeset["revision"] += 1
            self._write(cid, changeset)
            return changeset, dropped

    def prune(self, cid: str, dropped: list[dict]) -> None:
        with self._lock:
            changeset = self.load(cid)
            if changeset is not None:
                self._prune(cid, changeset, dropped)

    def restore(self, cid: str, changeset: dict | None) -> None:
        """Put back a changeset read earlier (rollback); None removes the changeset file."""
        with self._lock:
            if changeset is None:
                path = self.directory(cid) / "changeset.json"
                if path.is_file():
                    path.unlink()
            else:
                self._write(cid, changeset)

    def revert(self, cid: str, change_id: str, *, speech_baseline: set[str] | None = None) -> dict:
        with self._lock:
            changeset = self.load(cid)
            if changeset is None:
                raise DraftError("这个角色没有草稿")
            gone = [c for c in changeset["changes"] if c["id"] == change_id]
            if not gone:
                raise DraftError(f"草稿里没有改动 {change_id}")
            if any(c["kind"] == "speech_rows" for c in gone):
                from .speech import guard_revert
                guard_revert(changeset, gone, speech_baseline)
            changeset["changes"] = [c for c in changeset["changes"] if c["id"] != change_id]
            if any(c["kind"] == "summon_clone" for c in gone):
                from .summon import sync_reservations
                sync_reservations(changeset, gone)
            changeset["updatedAt"] = now()
            changeset["revision"] += 1
            self._write(cid, changeset)
            self._prune(cid, changeset, gone)
            return changeset

    def _prune(self, cid: str, changeset: dict, removed: list[dict]) -> None:
        """Delete unreferenced files, keeping only portrait sources for re-cropping."""
        alive = {f["draft"] for c in changeset["changes"] for f in c["files"]}
        alive |= {p for c in changeset["changes"] for p in _param_files(c)}
        for change in removed:
            for relative in [f["draft"] for f in change["files"]] + list(_param_files(change)):
                if relative in alive or relative.startswith("sources/portrait_"):
                    continue
                path = self.resolve(cid, relative)
                if path.is_file():
                    path.unlink()
        files = self.directory(cid) / "files"
        if files.is_dir():
            for folder in sorted((p for p in files.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
                if not any(folder.iterdir()):
                    folder.rmdir()

    def save(self, cid: str) -> dict:
        """「保存」动作：整体 schema 校验 + 逐文件哈希复核，通过才记 savedAt。"""
        with self._lock:
            changeset = self.load(cid)
            if changeset is None:
                raise DraftError("这个角色没有草稿，没有可保存的改动")
            problems = verify(self, cid, changeset)
            if problems:
                raise DraftError("保存前复核失败：" + "；".join(problems[:6]))
            changeset["savedAt"] = now()
            changeset["savedRevision"] = changeset["revision"]
            self._write(cid, changeset)
            return changeset

    def create(self, cid: str, changeset: dict) -> dict:
        """新建一份空草稿（草稿角色用）；已存在就拒绝。"""
        with self._lock:
            if self.load(cid) is not None:
                raise DraftError(f"草稿 {cid} 已存在")
            self._write(cid, changeset)
            return changeset

    def update_scratch(self, cid: str, meta: dict) -> dict:
        with self._lock:
            changeset = self.load(cid)
            if changeset is None or "scratch" not in changeset:
                raise DraftError(f"没有草稿角色 {cid}")
            changeset["scratch"] = meta
            changeset["updatedAt"] = now()
            changeset["revision"] += 1
            self._write(cid, changeset)
            return changeset

    def characters(self) -> list[dict]:
        result = []
        if self.root.is_dir():
            for folder in sorted(self.root.iterdir()):
                if folder.is_dir() and _CID.match(folder.name):
                    changeset = self.load(folder.name)
                    if changeset:
                        item = {"characterId": folder.name, "code": changeset["code"],
                                "changes": len(changeset["changes"]),
                                "updatedAt": changeset["updatedAt"], "savedAt": changeset["savedAt"]}
                        if "scratch" in changeset:
                            item["scratch"] = changeset["scratch"]
                        result.append(item)
        return result

    def discard_all(self, cid: str) -> None:
        directory = self.directory(cid)
        if directory.is_dir():
            shutil.rmtree(directory)


def _param_files(change: dict):
    params = change.get("params", {})
    if isinstance(params.get("sourceFile"), str):
        yield params["sourceFile"]
    for frame in params.get("frames", []) or []:
        if isinstance(frame, dict) and isinstance(frame.get("file"), str):
            yield frame["file"]


def verify(store: DraftStore, cid: str, changeset: dict) -> list[str]:
    problems = schema_errors(changeset)
    for change in changeset.get("changes", []):
        for entry in change.get("files", []):
            data = store.read_file(cid, entry["draft"])
            if data is None:
                problems.append(f"{change['title']}：缺少文件 {entry['draft']}")
            elif sha256(data) != entry["sha256"]:
                problems.append(f"{change['title']}：{entry['draft']} 哈希不符")
        for relative in _param_files(change):
            if store.read_file(cid, relative) is None:
                problems.append(f"{change['title']}：缺少源文件 {relative}")
        for frame in change.get("params", {}).get("frames", []) or []:
            data = store.read_file(cid, frame["file"]) if isinstance(frame, dict) and frame.get("file") else None
            if data is not None and frame.get("sha256") and sha256(data) != frame["sha256"]:
                problems.append(f"{change['title']}：{frame['file']} 哈希不符")
    return problems


def status(changeset: dict | None) -> dict:
    """Codex 三栏里的「保存状态」一栏。"""
    if not changeset or not changeset["changes"]:
        return {"state": "clean", "label": "无草稿改动", "changes": 0}
    count = len(changeset["changes"])
    saved = changeset.get("savedAt")
    if changeset.get("savedRevision") == changeset.get("revision"):
        return {"state": "saved", "label": f"草稿 {count} 项 · 已保存", "changes": count, "savedAt": saved}
    return {"state": "dirty", "label": f"草稿 {count} 项 · 未保存", "changes": count, "savedAt": saved}

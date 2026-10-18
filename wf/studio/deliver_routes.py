"""HTTP glue for 「生成」/「导出」: run the existing deliver bridge and list its output.

No delivery logic lives here. ``POST /api/drafts/<cid>/build`` calls
:func:`wf.studio.deliver_bridge.build_draft` with the same manifest baseline the
editor view was resolved from, writing only under ``work/studio-deliveries/``.
GET routes list and serve files of those output folders (read-only).
"""
from __future__ import annotations

import json
import mimetypes
import re
import threading
import time
import traceback
from pathlib import Path

from wf.paths import REPOSITORY

from .drafts import DraftError

DELIVERIES = REPOSITORY / "work" / "studio-deliveries"
NAME = re.compile(r"^[0-9]+-[0-9.]+-to-[0-9.]+-[0-9]{8}-[0-9]{6}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def next_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return version
    return f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"


class DeliverRoutes:
    name_pattern = NAME

    def output_identity(self, cid):
        self.app.ops.store.directory(cid)
        return cid

    def display_root(self):
        root = self.root.resolve()
        return root.relative_to(REPOSITORY.resolve()).as_posix() if root.is_relative_to(REPOSITORY.resolve()) else str(root)

    def __init__(self, app, server_dir=None, root: Path | None = None, default_provides=None):
        self.app, self.server_dir = app, server_dir
        self.default_provides = Path(default_provides) if default_provides is not None else None
        self.root = Path(root) if root is not None else DELIVERIES
        self._lock = threading.Lock()
        self.running: dict[str, str] = {}

    # -- baseline options derived from the editor view ------------------
    def baseline_options(self) -> dict:
        source = self.app.source
        options: dict = {}
        chain = getattr(source, "chain", None)
        if chain is not None:
            options["baseline_manifest"] = Path(chain.manifest)
        # Exact folders the editor view already resolved (flat lookup by the manifest view).
        view = source.view
        dirs = []
        for archive in getattr(view, "zips", []):
            parent = Path(archive).parent
            if parent not in dirs:
                dirs.append(parent)
        if dirs:
            options["baseline_zip_dirs"] = dirs
        if self.server_dir is not None:
            options["server_dir"] = Path(self.server_dir)
        return options

    # -- handlers --------------------------------------------------------
    def defaults(self, query):
        from .server import json_response
        version = self.app.source.version
        return json_response({"from": version, "to": next_version(version),
                              "outRoot": self.display_root(),
                              "serverDir": str(self.server_dir) if self.server_dir else None,
                              "provides": str(self.default_provides) if self.default_provides else None,
                              "note": "来源版本取当前视图末端；目标版本默认 +1，只是本地测试候选，不代表正式版本分配。"})

    def build(self, query, body, cid):
        from .server import json_response
        from .deliver_bridge import build_draft
        version = self.app.source.version
        from_version = str(body.get("from") or version)
        to_version = str(body.get("to") or next_version(from_version))
        for value in (from_version, to_version):
            if not VERSION.fullmatch(value):
                raise DraftError(f"版本无效：{value}")
        provides = body.get("provides") or self.default_provides
        if provides is not None:
            provides = Path(str(provides))
            if not provides.is_file():
                raise DraftError(f"provides 文件不存在：{provides}")
        output_id = self.output_identity(cid)
        with self._lock:
            if cid in self.running:
                raise DraftError(f"角色 {cid} 已在生成中（{self.running[cid]}），请稍候")
            name = f"{output_id}-{from_version}-to-{to_version}-{time.strftime('%Y%m%d-%H%M%S')}"
            self.running[cid] = name
        out = self.root / name
        started = time.time()
        try:
            result = build_draft(cid, from_version=from_version, to_version=to_version, out=out,
                                 store=self.app.ops.store, provides=provides, **self.baseline_options())
            result = {**result, "name": name, "seconds": round(time.time() - started, 1)}
        except Exception as exc:  # noqa: BLE001 - every failure is reported, never hidden
            detail = {"ok": False, "name": name, "characterId": cid, "from": from_version, "to": to_version,
                      "error": f"{type(exc).__name__}: {exc}", "seconds": round(time.time() - started, 1),
                      "deviceValidation": "未执行"}
            if not isinstance(exc, (DraftError, ValueError, FileNotFoundError, PermissionError)):
                traceback.print_exc()
            if out.is_dir():
                (out / "studio-build-error.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2), "utf-8")
            result = detail
        finally:
            with self._lock:
                self.running.pop(cid, None)
        return json_response(result)

    def listing(self, query):
        from .server import json_response
        cid = (query.get("cid") or [""])[0]
        cid = self.output_identity(cid) if cid else ""
        items = []
        if self.root.is_dir():
            for folder in sorted(self.root.iterdir(), reverse=True):
                if not folder.is_dir() or not self.name_pattern.fullmatch(folder.name):
                    continue
                if cid and not folder.name.startswith(cid + "-"):
                    continue
                report = _read_json(folder / "build-report.json") or _read_json(folder / "studio-build-error.json")
                counts: dict[str, int] = {}
                checks = (report or {}).get("checks", [])
                compat = (report or {}).get("compatChecks", (report or {}).get("compat", []))
                entries = (checks if isinstance(checks, list) else []) + (compat if isinstance(compat, list) else [])
                for item in entries:
                    if not isinstance(item, dict):
                        continue
                    counts[item.get("status", "?")] = counts.get(item.get("status", "?"), 0) + 1
                items.append({"name": folder.name, "ok": bool(report and report.get("ok")),
                              "error": report.get("error") if report else "没有 build-report.json（生成可能中断）",
                              "from": report.get("from") if report else None,
                              "to": report.get("to") if report else None,
                              "draftRevision": report.get("draftRevision") if report else None,
                              "prepush": (report.get("prepush") or {}).get("status") if report else None,
                              "counts": counts})
        return json_response({"root": self.display_root(), "deliveries": items,
                              "running": dict(self.running)})

    def _folder(self, name: str) -> Path:
        if not self.name_pattern.fullmatch(name):
            raise DraftError("交付目录名无效")
        folder = (self.root / name).resolve()
        if not folder.is_relative_to(self.root.resolve()) or not folder.is_dir():
            raise DraftError("没有这个交付目录")
        return folder

    def detail(self, query, name):
        from .server import json_response
        folder = self._folder(name)
        report = _read_json(folder / "build-report.json")
        error = _read_json(folder / "studio-build-error.json")
        delivery = folder / "delivery"
        files = []
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                rel = path.relative_to(folder).as_posix()
                if rel.startswith("inputs/blobs/"):
                    continue
                files.append({"path": rel, "size": path.stat().st_size})
        manifest = _read_json(delivery / "delivery-manifest.json") or {}
        archives = [{"name": a.get("name"), "size": a.get("size"), "sha256": a.get("sha256"),
                     "members": a["members"] if isinstance(a.get("members"), int) else len(a.get("files") or []),
                     "files": a.get("files") or []} for a in manifest.get("archives", [])]
        changeset = _read_json(folder / "inputs" / "changeset.json") or {}
        members = [{"root": m.get("root"), "logical": m.get("logical_path"), "sha256": m.get("sha256"),
                    "before": m.get("before_sha256")} for m in changeset.get("members", [])]
        servers = [{"target": s.get("target"), "sha256": s.get("sha256")} for s in changeset.get("server_changes", [])]
        check = (_read_json(delivery / "check.json") or {}).get("results")
        compat = (_read_json(delivery / "compat.json") or {}).get("results")
        return json_response({"name": name, "path": str(folder), "report": report, "error": error,
                              "archives": archives, "members": members, "serverChanges": servers,
                              "requires": _read_json(delivery / "requires.json"),
                              "check": check, "compat": compat, "files": files,
                              "deviceValidation": "未执行"})

    def file(self, query, name):
        from .server import Response
        folder = self._folder(name)
        relative = (query.get("path") or [""])[0]
        target = (folder / relative).resolve()
        if not relative or not target.is_relative_to(folder) or not target.is_file():
            raise DraftError("交付目录里没有这个文件")
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix in (".json", ".txt", ".md", ".py") or target.name == "SHA256SUMS":
            kind = "text/plain; charset=utf-8"
        return Response(200, target.read_bytes(), kind)

    def routes(self):
        return [("GET", re.compile(r"^/api/deliveries$"), self.listing),
                ("GET", re.compile(r"^/api/deliveries/defaults$"), self.defaults),
                ("GET", re.compile(r"^/api/deliveries/(?P<name>[^/]+)$"), self.detail),
                ("GET", re.compile(r"^/api/deliveries/(?P<name>[^/]+)/file$"), self.file),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/build$"), self.build)]

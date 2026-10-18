"""HTTP glue for 「生成」/「导出」: run the existing deliver bridge and list its output.

No delivery logic lives here. ``POST /api/drafts/<cid>/build`` calls
:func:`wf.studio.deliver_bridge.build_draft` with the same manifest baseline the
editor view was resolved from, writing only under ``work/studio-deliveries/``.
With ``{"background": true}`` the build runs in a worker thread: the response is the
job (``GET /api/deliveries/jobs/<name>`` reports the stage — 编译 / wf deliver / check /
兼容), and ``POST /api/drafts/<cid>/build/cancel`` stops it between stages (the partial
output folder is removed). GET routes list and serve files of those output folders.
"""
from __future__ import annotations

import json
import mimetypes
import re
import shutil
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
        self.jobs: dict[str, dict] = {}       # name -> public job record (kept for the session)
        self._cancel: dict[str, threading.Event] = {}

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
        from wf.caps.profiles import profile_options, resolve_client
        provides, selected = resolve_client(self.default_provides)
        version = self.app.source.version
        return json_response({"from": version, "to": next_version(version),
                              "outRoot": self.display_root(),
                              "serverDir": str(self.server_dir) if self.server_dir else None,
                              "provides": str(provides) if provides else None,
                              "clientProfile": selected, **profile_options(),
                              "note": "来源版本取当前视图末端；目标版本默认 +1，只是本地测试候选，不代表正式版本分配。"})

    def build(self, query, body, cid):
        from .server import json_response
        from .deliver_bridge import STAGES
        version = self.app.source.version
        from_version = str(body.get("from") or version)
        to_version = str(body.get("to") or next_version(from_version))
        for value in (from_version, to_version):
            if not VERSION.fullmatch(value):
                raise DraftError(f"版本无效：{value}")
        from wf.caps.profiles import resolve_client
        try:
            explicit = body.get("provides") or (None if body.get("clientProfile") else self.default_provides)
            provides, selected = resolve_client(explicit,
                                               body.get("clientProfile"))
        except ValueError as exc:
            raise DraftError(str(exc)) from exc
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
            cancel = self._cancel[name] = threading.Event()
            job = self.jobs[name] = {"name": name, "characterId": cid, "from": from_version, "to": to_version,
                                     "clientProfile": selected,
                                     "state": "running", "stage": None, "stages": [
                                         {"id": s, "label": label, "state": "waiting"} for s, label in STAGES],
                                     "startedAt": time.time(), "seconds": 0, "result": None}
        if body.get("background"):
            threading.Thread(target=self._run, name=f"build-{name}", daemon=True,
                             args=(cid, name, from_version, to_version, provides, cancel)).start()
            return json_response(self._public(job))
        return json_response(self._run(cid, name, from_version, to_version, provides, cancel))

    def _progress(self, name):
        def report(stage):
            with self._lock:
                job = self.jobs[name]
                for item in job["stages"]:
                    if item["state"] == "running":
                        item["state"] = "done"
                    if item["id"] == stage:
                        item["state"] = "running"
                job["stage"] = stage
        return report

    def _run(self, cid, name, from_version, to_version, provides, cancel):
        from .deliver_bridge import BuildCancelled, build_draft
        out = self.root / name
        started = time.time()
        try:
            selected = self.jobs[name].get("clientProfile")
            result = build_draft(cid, from_version=from_version, to_version=to_version, out=out,
                                 store=self.app.ops.store, provides=None if selected else provides,
                                 client_profile=selected,
                                 progress=self._progress(name), cancel=cancel, **self.baseline_options())
            result = {**result, "name": name, "seconds": round(time.time() - started, 1)}
            state = "ok" if result.get("ok") else "failed"
        except BuildCancelled as exc:
            result = {"ok": False, "name": name, "characterId": cid, "from": from_version, "to": to_version,
                      "cancelled": True, "error": str(exc), "seconds": round(time.time() - started, 1),
                      "deviceValidation": "未执行"}
            state = "cancelled"
            if out.is_dir() and out.resolve().is_relative_to(self.root.resolve()):
                shutil.rmtree(out, ignore_errors=True)  # partial output of this job only
        except Exception as exc:  # noqa: BLE001 - every failure is reported, never hidden
            detail = {"ok": False, "name": name, "characterId": cid, "from": from_version, "to": to_version,
                      "error": f"{type(exc).__name__}: {exc}", "seconds": round(time.time() - started, 1),
                      "deviceValidation": "未执行"}
            if not isinstance(exc, (DraftError, ValueError, FileNotFoundError, PermissionError)):
                traceback.print_exc()
            if out.is_dir():
                (out / "studio-build-error.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2), "utf-8")
            result, state = detail, "failed"
        finally:
            with self._lock:
                self.running.pop(cid, None)
                self._cancel.pop(name, None)
        with self._lock:
            job = self.jobs[name]
            for item in job["stages"]:
                if item["state"] == "running":
                    item["state"] = "done" if state == "ok" else state
            job.update(state=state, seconds=result.get("seconds", 0), result=result)
        return result

    def _public(self, job):
        out = {k: v for k, v in job.items() if k != "startedAt"}
        if job["state"] == "running":
            out["seconds"] = round(time.time() - job["startedAt"], 1)
        return out

    def job(self, query, name):
        from .server import json_response
        with self._lock:
            job = self.jobs.get(name)
            if job is None:
                raise DraftError("没有这个生成任务（编辑台重启后任务记录会清空，结果见「导出」）")
            return json_response(self._public(json.loads(json.dumps(job))))

    def cancel(self, query, body, cid):
        from .server import json_response
        with self._lock:
            name = self.running.get(cid)
            if not name:
                raise DraftError(f"角色 {cid} 没有正在进行的生成")
            self._cancel[name].set()
        return json_response({"name": name, "cancelling": True,
                              "note": "当前阶段结束后停止；已写出的半成品目录会删除"})

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
        with self._lock:
            jobs = [self._public(job) for job in self.jobs.values() if not cid or job["characterId"] == cid]
        return json_response({"root": self.display_root(), "deliveries": items,
                              "running": dict(self.running), "jobs": jobs})

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
                ("GET", re.compile(r"^/api/deliveries/jobs/(?P<name>[^/]+)$"), self.job),
                ("GET", re.compile(r"^/api/deliveries/(?P<name>[^/]+)$"), self.detail),
                ("GET", re.compile(r"^/api/deliveries/(?P<name>[^/]+)/file$"), self.file),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/build$"), self.build),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/build/cancel$"), self.cancel)]

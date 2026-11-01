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
from types import SimpleNamespace

from wf.paths import REPOSITORY

from . import device_result
from .drafts import DraftError
from .delivery_actions import DeliveryActions
from .overlay_export import availability

DELIVERIES = REPOSITORY / "work" / "studio-deliveries"
NAME = re.compile(r"^[0-9]+-[0-9.]+-to-[0-9.]+-[0-9]{8}-[0-9]{6}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def next_version(version: str, *, source=None) -> str:
    from .versions import next_version as suggest
    view = getattr(source, "view", None)
    return suggest(SimpleNamespace(version=version, view=view))["next"]


class DeliverRoutes(DeliveryActions):
    name_pattern = NAME
    kind = "character"

    def compile_delivery(self, cid, **kwargs):
        from .deliver_bridge import build_draft
        return build_draft(cid, **kwargs)

    def output_identity(self, cid):
        self.app.ops.store.directory(cid)
        return cid

    def current_draft(self, subject):
        """Revision and creation time of the draft a delivery came from (None: gone or unreadable)."""
        try:
            changeset = self.app.ops.store.load(self.draft_id(subject)) if subject else None
        except (DraftError, ValueError, OSError, TypeError):
            return None
        if not changeset:
            return None
        return {"revision": changeset.get("revision"), "createdAt": changeset.get("createdAt")}

    def draft_id(self, subject):
        return subject

    def screenshots(self):
        from .device_result import Screenshots
        return getattr(self.app, "screenshots", None) or Screenshots([])

    def display_root(self):
        root = self.root.resolve()
        return root.relative_to(REPOSITORY.resolve()).as_posix() if root.is_relative_to(REPOSITORY.resolve()) else str(root)

    def __init__(self, app, server_dir=None, root: Path | None = None, default_provides=None):
        self.app, self.server_dir = app, server_dir
        self.default_provides = Path(default_provides) if default_provides is not None else None
        self.root = Path(root) if root is not None else DELIVERIES
        self._lock = threading.Lock()
        self._rehearsing = set()
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
        from wf.view import ManifestView
        if isinstance(view, ManifestView):
            options.update(baseline_view=view, base_store=view.store, base_version=view.base_version)
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
        return json_response({"from": version, "to": next_version(version, source=self.app.source),
                              "outRoot": self.display_root(),
                              "serverDir": str(self.server_dir) if self.server_dir else None,
                              "provides": str(provides) if provides else None,
                              "clientProfile": selected, **profile_options(),
                              "note": "来源版本取当前视图末端；默认目标跳过版本预留与已声明版本，只是本地测试候选，不代表正式版本分配。"})

    def build(self, query, body, cid):
        from .server import json_response
        from .deliver_bridge import STAGES
        version = self.app.source.version
        from_version = str(body.get("from") or version)
        to_version = str(body.get("to") or next_version(from_version, source=self.app.source))
        for value in (from_version, to_version):
            if not VERSION.fullmatch(value):
                raise DraftError(f"版本无效：{value}")
        from wf.caps.profiles import resolve_client
        from .delivery_safety import resolve_apks
        try:
            explicit = body.get("provides") or (None if body.get("clientProfile") else self.default_provides)
            provides, selected = resolve_client(explicit,
                                               body.get("clientProfile"))
            apks = resolve_apks(selected, body.get("apk"))
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
            if name in self._rehearsing:
                raise DraftError("交付正在预演，请等待结束")
            self.running[cid] = name
            cancel = self._cancel[name] = threading.Event()
            job = self.jobs[name] = {"name": name, "characterId": cid, "from": from_version, "to": to_version,
                                     "clientProfile": selected,
                                     "apk": [str(path) for path in apks],
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
        from .deliver_bridge import BuildCancelled
        out = self.root / name
        started = time.time()
        try:
            selected = self.jobs[name].get("clientProfile")
            result = self.compile_delivery(cid, from_version=from_version, to_version=to_version, out=out,
                                 store=self.app.ops.store, provides=None if selected else provides,
                                 client_profile=selected,
                                 apk=self.jobs[name].get("apk"),
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

    def _matches_cid(self, folder: Path, raw_cid: str, output_id: str) -> bool:
        return folder.name.startswith(output_id + "-")

    def listing(self, query):
        from .server import json_response
        raw_cid = (query.get("cid") or [""])[0]
        cid = self.output_identity(raw_cid) if raw_cid else ""
        items = []
        draft = self.current_draft(cid) if cid else None
        if self.root.is_dir():
            for folder in sorted(self.root.iterdir(), reverse=True):
                if not folder.is_dir() or not self.name_pattern.fullmatch(folder.name):
                    continue
                if cid and not self._matches_cid(folder, raw_cid, cid):
                    continue
                report = _read_json(folder / "build-report.json") or _read_json(folder / "studio-build-error.json")
                counts: dict[str, int] = {}
                checks = (report or {}).get("checks", [])
                compat = (report or {}).get("compatChecks", (report or {}).get("compat", []))
                entries = (checks if isinstance(checks, list) else []) + (compat if isinstance(compat, list) else [])
                for item in entries:
                    if not isinstance(item, dict) or item.get("category") == "联机风险":
                        continue
                    counts[item.get("status", "?")] = counts.get(item.get("status", "?"), 0) + 1
                items.append({"name": folder.name, "ok": bool(report and report.get("ok")),
                              "error": report.get("error") if report else "没有 build-report.json（生成可能中断）",
                              "from": report.get("from") if report else None,
                              "to": report.get("to") if report else None,
                              "draftRevision": report.get("draftRevision") if report else None,
                              "draftCreatedAt": (_read_json(folder / "inputs" / "draft.json") or {}).get("createdAt"),
                              "prepush": (report.get("prepush") or {}).get("status") if report else None,
                              "counts": counts,
                              "device": device_result.summary(device_result.read(folder, self.kind), draft)})
        with self._lock:
            jobs = [self._public(job) for job in self.jobs.values() if not raw_cid or job["characterId"] == raw_cid]
        return json_response({"root": self.display_root(), "deliveries": items,
                              "currentRevision": (draft or {}).get("revision"),
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
            if any(p.startswith((".overlay-", ".studio-")) for p in path.relative_to(folder).parts):
                continue
            if path.is_file():
                rel = path.relative_to(folder).as_posix()
                if rel.startswith("inputs/blobs/"):
                    continue
                try:
                    files.append({"path": rel, "size": path.stat().st_size})
                except FileNotFoundError:
                    continue  # An export may publish/remove temporary files concurrently.
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
        device = self._device(folder)
        from .key_diff import summarize
        from .rehearsal_io import latest
        key_diff = _read_json(delivery / "key-diff.json")
        if isinstance(report, dict) and isinstance(report.get("keyDiff"), dict):
            report = {**report, "keyDiff": summarize(report["keyDiff"])}
        return json_response({"name": name, **availability(folder), "path": str(folder), "report": report, "error": error,
                              "archives": archives, "members": members, "serverChanges": servers,
                              "requires": _read_json(delivery / "requires.json"),
                              "check": check, "compat": compat, "files": files,
                              "bundleCheck": _read_json(delivery / "bundle-check.json"),
                              "keyDiff": summarize(key_diff) if key_diff is not None else None,
                              "iconAlpha": _read_json(delivery / "icon-alpha.json"),
                              "clientExtensions": _read_json(delivery / "client-extensions.json"),
                              "rehearsal": latest(delivery) if delivery.is_dir() else None,
                              "deviceResult": device,
                              "deviceValidation": (device.get("result") or {}).get("status", "未执行") if device else "未执行"})

    # -- 实测（device-result.json） ----------------------------------------
    def rehearse(self, query, body, name):
        from .server import json_response
        from .rehearsal import rehearse
        if set(body) != {"server"}:
            raise DraftError('预演请求只接受 {"server": "local"}')
        with self._lock:
            if name in self.running.values() or name in self._rehearsing:
                raise DraftError("交付仍在生成中，请等待生成结束")
            self._rehearsing.add(name)
        try:
            result = rehearse(self._folder(name), body["server"])
        finally:
            with self._lock:
                self._rehearsing.discard(name)
        return json_response({"name": name, "ok": result["ok"], "rehearsal": result})

    def _device(self, folder: Path) -> dict | None:
        entry = device_result.read(folder, self.kind)
        if entry is None:
            return None
        result = entry.get("result")
        draft = self.current_draft(device_result.subject_of(folder.name))
        return {**entry, "screenshots": self.screenshots().annotate(result),
                "currentRevision": (draft or {}).get("revision"), "draftMissing": draft is None,
                "stale": device_result.stale(result, draft)}

    def device_get(self, query, name):
        from .server import json_response
        folder = self._folder(name)
        return json_response({"name": name, "deviceResult": self._device(folder),
                              "screenshotDirs": self.screenshots().public()})

    def _owned(self, cid, name) -> Path:
        identity = self.output_identity(cid)
        if device_result.subject_of(name) != identity:
            raise DraftError(f"交付 {name} 不属于 {cid}")
        return self._folder(name)

    def device_write(self, query, body, cid, name):
        from .server import json_response
        folder = self._owned(cid, name)
        device_result.write(folder, self.kind, body)
        return json_response({"name": name, "deviceResult": self._device(folder)})

    def device_import(self, query, body, cid, name):
        from .server import json_response
        source = str(body.get("path") or "").strip()
        if not source:
            raise DraftError("需要 path：来源 device-result.json 或它所在的交付目录")
        folder = self._owned(cid, name)
        try:
            device_result.import_file(Path(source), folder, self.kind,
                                      allow_unverified=bool(body.get("allowUnverified")))
        except OSError as exc:
            raise DraftError(f"读取来源失败：{exc}") from exc
        return json_response({"name": name, "deviceResult": self._device(folder)})

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
                ("POST", re.compile(r"^/api/deliveries/(?P<name>[^/]+)/rehearse$"), self.rehearse),
                ("POST", re.compile(r"^/api/deliveries/(?P<name>[^/]+)/apply$"), self.apply),
                ("POST", re.compile(r"^/api/deliveries/(?P<name>[^/]+)/unapply$"), self.unapply),
                ("POST", re.compile(r"^/api/deliveries/(?P<name>[^/]+)/overlay$"), self.overlay),
                ("GET", re.compile(r"^/api/deliveries/(?P<name>[^/]+)/device-result$"), self.device_get),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/deliveries/(?P<name>[^/]+)/device-result$"), self.device_write),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/deliveries/(?P<name>[^/]+)/device-result/import$"),
                 self.device_import),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/build$"), self.build),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/build/cancel$"), self.cancel)]

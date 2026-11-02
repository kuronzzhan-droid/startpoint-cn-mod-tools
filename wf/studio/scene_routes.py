"""Scene workshop routes reuse guarded local delivery infrastructure."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace

from wf.view.safety import local_output
from . import device_result
from .mode_store import ModeStore, ViewInputs
from .drafts import DraftError, sha256
from .freshness import freshness
from .deliver_routes import DeliverRoutes, DELIVERIES, _read_json

MOTHER_SLOT = "hell-pumpkin"
MOTHER_EVENT = "300097"
SCENE_SLOT_PATTERN = r"hell-pumpkin|scene-[3-9][0-9]{5}"
SLOT_RE = re.compile(rf"^(?:{SCENE_SLOT_PATTERN})$")
CLONE_SLOT_RE = re.compile(r"^scene-([3-9][0-9]{5})$")
EVENT_ID_RE = re.compile(r"^[3-9][0-9]{5}$")


def slot_for_payload(payload) -> str:
    if not isinstance(payload, dict):
        raise DraftError("场景规格必须是对象")
    spec_id = payload.get("id")
    event = payload.get("event")
    event_id = event.get("id") if isinstance(event, dict) else None
    if payload.get("creation"):
        if not isinstance(event_id, str) or not EVENT_ID_RE.fullmatch(event_id) or event_id == MOTHER_EVENT:
            raise DraftError("新场景活动 ID 必须为不同于 300097 的六位编号")
        expected = "scene-" + event_id
        if spec_id != expected:
            raise DraftError(f"新场景规格 id 必须为 {expected}")
        return expected
    if spec_id == MOTHER_SLOT and event_id == MOTHER_EVENT:
        return MOTHER_SLOT
    raise DraftError("母本草稿槽必须对应 hell-pumpkin (300097)；新活动须带创建声明保存到独立槽 scene-<event>")


def _legacy_clone_slot(payload) -> str | None:
    if not isinstance(payload, dict):
        return None
    spec_id = payload.get("id")
    event = payload.get("event")
    event_id = event.get("id") if isinstance(event, dict) and isinstance(event.get("id"), str) else None
    match = CLONE_SLOT_RE.fullmatch(spec_id) if isinstance(spec_id, str) else None
    candidate = event_id if event_id and EVENT_ID_RE.fullmatch(event_id) else (match[1] if match else None)
    if candidate and candidate != MOTHER_EVENT and (payload.get("creation") or match or event_id != MOTHER_EVENT):
        return "scene-" + candidate
    return None


class SceneStore(ModeStore):
    def __init__(self, root):
        super().__init__(root)
        self.migrated_slot: str | None = None

    def directory(self, mode):
        if not isinstance(mode, str) or not SLOT_RE.fullmatch(mode):
            raise DraftError("未知场景草稿槽")
        return local_output(self.root / mode)

    def _write_atomic(self, folder: Path, filename: str, data: dict) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        target = local_output(folder / filename)
        if target.exists() and target.stat().st_nlink > 1:
            raise DraftError("草稿文件不能是硬链接")
        temp = local_output(folder / (filename + ".migrate.tmp"))
        if temp.exists():
            temp.unlink()
        with temp.open("x", encoding="utf8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temp, target)
        return target

    def _migrate_legacy(self) -> None:
        with self.lock:
            legacy_file = self.directory(MOTHER_SLOT) / "changeset.json"
            if not legacy_file.is_file():
                return
            try:
                data = json.loads(legacy_file.read_text("utf8"))
            except (OSError, ValueError):
                return
            if not isinstance(data, dict):
                return
            target_slot = _legacy_clone_slot(data.get("payload"))
            if not target_slot:
                return
            migrated = copy.deepcopy(data)
            migrated["characterId"] = target_slot
            migrated["code"] = target_slot
            if isinstance(migrated.get("payload"), dict):
                migrated["payload"]["id"] = target_slot
            dest_dir = self.directory(target_slot)
            dest_file = dest_dir / "changeset.json"
            if dest_file.is_file():
                existing = _read_json(dest_file)
                if not isinstance(existing, dict) or (
                        existing.get("payload") != migrated.get("payload")
                        or existing.get("revision") != migrated.get("revision")):
                    backup_rev = migrated.get("revision", 0)
                    backup_name = f"legacy-hell-pumpkin-rev{backup_rev}.json"
                    if isinstance(existing, dict) and existing.get("revision", 0) >= migrated.get("revision", 0):
                        self._write_atomic(dest_dir, backup_name, migrated)
                    else:
                        if isinstance(existing, dict):
                            self._write_atomic(dest_dir, f"legacy-preexisting-rev{existing.get('revision', 0)}.json", existing)
                        self._write_atomic(dest_dir, "changeset.json", migrated)
            else:
                self._write_atomic(dest_dir, "changeset.json", migrated)
            legacy_file.unlink()
            self.migrated_slot = target_slot

    def load(self, mode):
        with self.lock:
            self._migrate_legacy()
            return super().load(mode)

    def save(self, mode, version, payload, inputs, preview, expected_revision):
        with self.lock:
            self._migrate_legacy()
            return super().save(mode, version, payload, inputs, preview, expected_revision)

    def list_drafts(self) -> list[dict]:
        with self.lock:
            self._migrate_legacy()
            if not self.root.is_dir():
                return []
            items = []
            for folder in sorted(self.root.iterdir()):
                if not folder.is_dir() or not SLOT_RE.fullmatch(folder.name):
                    continue
                if not (folder / "changeset.json").is_file():
                    continue
                draft = super().load(folder.name)
                if not draft:
                    continue
                payload = draft.get("payload") if isinstance(draft.get("payload"), dict) else {}
                event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
                match = CLONE_SLOT_RE.fullmatch(folder.name)
                event_id = event.get("id") if isinstance(event.get("id"), str) else (
                    match[1] if match else MOTHER_EVENT)
                items.append({
                    "slot": folder.name,
                    "name": payload.get("name") if isinstance(payload.get("name"), str) else folder.name,
                    "eventId": event_id,
                    "isClone": folder.name != MOTHER_SLOT,
                    "revision": draft.get("revision", 0),
                    "baseView": draft.get("baseView"),
                    "updatedAt": draft.get("updatedAt"),
                })
            items.sort(key=lambda item: (0 if item["slot"] == MOTHER_SLOT else 1, item["slot"]))
            return items

    def reserved_events(self) -> set[str]:
        reserved = set()
        for item in self.list_drafts():
            match = CLONE_SLOT_RE.fullmatch(item["slot"])
            if match:
                reserved.add(match[1])
            elif isinstance(item.get("eventId"), str) and EVENT_ID_RE.fullmatch(item["eventId"]) and item["eventId"] != MOTHER_EVENT:
                reserved.add(item["eventId"])
        return reserved


class SceneDeliveries(DeliverRoutes):
    kind = "boss"
    name_pattern = re.compile(r"^(?:hell-pumpkin(?:-300097)?|scene-[3-9][0-9]{5})-[0-9.]+-to-[0-9.]+-[0-9]{8}-[0-9]{6}$")

    def __init__(self, owner, app, server_dir, default_provides):
        self.owner = owner
        super().__init__(app, server_dir, DELIVERIES / "scenes", default_provides)

    def output_identity(self, cid):
        self.app.ops.store.directory(cid)
        return "hell-pumpkin-300097" if cid == MOTHER_SLOT else cid

    def draft_id(self, subject):
        return MOTHER_SLOT if subject in {MOTHER_SLOT, "hell-pumpkin-300097"} else subject

    def folder_slot(self, folder: Path) -> str:
        subject = device_result.subject_of(folder.name) or ""
        if subject == MOTHER_SLOT:
            draft = _read_json(folder / "inputs" / "draft.json")
            migrated = _legacy_clone_slot(draft.get("payload") if isinstance(draft, dict) else None)
            if migrated:
                return migrated
        return self.draft_id(subject)

    def _matches_cid(self, folder: Path, raw_cid: str, output_id: str) -> bool:
        return self.folder_slot(folder) == raw_cid

    def _device(self, folder: Path) -> dict | None:
        entry = device_result.read(folder, self.kind)
        if entry is None:
            return None
        result = entry.get("result")
        draft = self.current_draft(self.folder_slot(folder))
        return {**entry, "screenshots": self.screenshots().annotate(result),
                "currentRevision": (draft or {}).get("revision"), "draftMissing": draft is None,
                "stale": device_result.stale(result, draft)}

    def _owned(self, cid, name) -> Path:
        self.app.ops.store.directory(cid)
        folder = self._folder(name)
        if self.folder_slot(folder) != cid:
            raise DraftError(f"交付 {name} 不属于 {cid}")
        return folder

    def compile_delivery(self, cid, **kwargs):
        from wf.caps.profiles import resolve_client
        from .deliver_bridge import deliver_compiled, open_baseline
        from .delivery_safety import resolve_apks
        draft = self.app.ops.store.load(cid)
        if not draft or draft["baseView"] != self.app.source.version:
            raise DraftError("请先在当前视图预览并保存场景规格")
        if kwargs["from_version"] != self.app.source.version:
            raise DraftError("来源版本必须是当前视图链尾")
        computed, inputs = self.owner.compute(cid, draft["payload"])
        if not computed["canGenerate"]:
            raise DraftError("；".join(computed["blockers"]))
        if inputs.inputs != draft["inputs"] or computed["outputSha256"] != draft["preview"]["outputSha256"]:
            raise DraftError("规格输入或构建结果变化，请重新预览并保存")
        if computed["serverBefore"] != draft["preview"].get("serverBefore"):
            raise DraftError("只读服务端镜像已变化，请重新预览并保存")
        compiled = ({("common", logical): raw for logical, raw in computed["files"].items()},
                    computed["servers"], computed["serverBefore"], computed["changes"], computed["checks"])
        options = self.baseline_options()
        if "baseline_view" not in options:
            raise DraftError("场景交付要求完整 manifest 当前视图")
        baseline = open_baseline(kwargs["from_version"], kwargs["to_version"], **options)
        provides, selected = resolve_client(kwargs.get("provides"), kwargs.get("client_profile"))
        apks = resolve_apks(selected, kwargs.get("apk"))
        out = local_output(kwargs["out"])
        if out.exists() and any(out.iterdir()):
            raise DraftError("交付输出目录必须为空")
        inputs.verify()
        return deliver_compiled(draft, compiled, source=self.app.source, baseline=baseline,
            from_version=kwargs["from_version"], to_version=kwargs["to_version"], out=out,
            provides=provides, selected_profile=selected, apks=apks,
            progress=kwargs.get("progress"), cancel=kwargs.get("cancel"), **options)

    def routes(self):
        return [(verb, re.compile(pattern.pattern.replace("/api/", "/api/scenes/")
                .replace(r"(?P<cid>\d+)", rf"(?P<cid>{SCENE_SLOT_PATTERN})")), handler)
                for verb, pattern, handler in super().routes()
                if not any(token in pattern.pattern for token in ("/apply", "/unapply"))]


class SceneRoutes:
    def __init__(self, app, server_dir=None, default_provides=None):
        self.app, self.server_dir = app, server_dir
        self.store = SceneStore(app.ops.store.root / "scenes")
        proxy = SimpleNamespace(source=app.source, ops=SimpleNamespace(store=self.store),
                                screenshots=getattr(app, "screenshots", None))
        self.deliveries = SceneDeliveries(self, proxy, server_dir, default_provides)

    def compute(self, mode, payload):
        from wf.boss.scene import compile_scene
        self.store.directory(mode)
        inputs = ViewInputs(self.app.source)
        result = compile_scene(inputs.read, payload, server_dir=self.server_dir)
        expected_slot = slot_for_payload(payload)
        if expected_slot != mode:
            raise DraftError(f"规格槽位 {expected_slot} 与目标草稿槽 {mode} 不一致，拒绝覆盖其他场景草稿")
        inputs.verify()
        fresh = freshness(self.app.source)
        if fresh.get("error") or fresh["latest"] != self.app.source.version or payload["sourceVersion"] != self.app.source.version:
            result["canGenerate"] = False
            result["blockers"].append("当前视图不是已确认的新鲜链尾或规格版本过期")
        result.update(version=self.app.source.version, freshness=fresh)
        result["outputSha256"] = {**{logical: sha256(raw) for logical, raw in result["files"].items()},
                                  **{"server:" + key: sha256(raw) for key, raw in result["servers"].items()}}
        return result, inputs

    @staticmethod
    def public(result):
        return {key: value for key, value in result.items() if key not in {"files", "servers"}}

    def drafts(self, query):
        from .server import json_response
        return json_response({"drafts": self.store.list_drafts(), "migratedSlot": self.store.migrated_slot})

    def read(self, query, mode):
        from .server import json_response
        from wf.boss.scene_import import import_hell_pumpkin
        draft = self.store.load(mode)
        if mode != MOTHER_SLOT and not draft:
            raise DraftError(f"没有已保存的场景草稿：{mode}")
        inputs = ViewInputs(self.app.source)
        spec = None
        try:
            spec = import_hell_pumpkin(inputs.read, self.app.source.version)
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as import_exc:
            if mode == MOTHER_SLOT and not draft:
                return json_response({
                    "mode": "scene", "slot": mode, "version": self.app.source.version,
                    "spec": None, "payload": None, "draft": None,
                    "drafts": self.store.list_drafts(), "migratedSlot": self.store.migrated_slot,
                    "preview": {"ok": False, "canGenerate": False, "blockers": [str(import_exc)], "checks": []},
                })
        payload = draft["payload"] if draft else spec
        try:
            result, _ = self.compute(mode, payload)
            preview = self.public(result)
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            preview = {"ok": False, "canGenerate": False, "blockers": [str(exc)], "checks": []}
        return json_response({
            "mode": "scene", "slot": mode, "version": self.app.source.version,
            "spec": spec, "payload": payload, "draft": draft,
            "drafts": self.store.list_drafts(), "migratedSlot": self.store.migrated_slot,
            "preview": preview,
        })

    def edit(self, query, body, mode, action):
        from .server import json_response
        if not isinstance(body, dict) or set(body) - {"payload", "revision"} or "payload" not in body:
            raise DraftError("请求只接受 payload 与 revision")
        try:
            result, inputs = self.compute(mode, body["payload"])
            public = self.public(result)
            public["slot"] = mode
            if action == "save":
                if not result["ok"]:
                    raise DraftError("规格存在构建错误，未保存")
                revision = body.get("revision")
                if type(revision) is not int or revision < 0:
                    raise DraftError("保存需要非负整数 revision")
                public["draft"] = self.store.save(mode, self.app.source.version, body["payload"],
                    inputs.inputs, copy.deepcopy(public), revision)
                public["drafts"] = self.store.list_drafts()
            return json_response(public)
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            raise DraftError(str(exc)) from exc

    def schema(self, query):
        from .server import json_response
        from wf.boss.scene_spec import schema
        return json_response(schema())

    def clone(self, query, body, mode):
        from .server import json_response
        from wf.boss.scene_clone import clone_scene
        from wf.boss.scene_allocate import allocate_scene, delivered_event_ids
        if not isinstance(body, dict) or set(body) - {"payload", "eventId", "name"} or "payload" not in body:
            raise DraftError("克隆需要 payload，可选 name 与 eventId")
        try:
            inputs = ViewInputs(self.app.source)
            reserved = set(self.store.reserved_events()) | delivered_event_ids(self.deliveries.root)
            with self.deliveries._lock:
                for running_cid in self.deliveries.running:
                    match = CLONE_SLOT_RE.fullmatch(running_cid)
                    if match:
                        reserved.add(match[1])
            explicit_id = body.get("eventId")
            if explicit_id:
                if str(explicit_id) in reserved:
                    raise ValueError(f"新活动 ID {explicit_id} 已被本地草稿或已有交付占用")
                payload = clone_scene(body["payload"], explicit_id, body.get("name"))
            else:
                payload = allocate_scene(body["payload"], inputs.read, server_dir=self.server_dir,
                                         reserved=sorted(reserved), deliveries_dir=self.deliveries.root,
                                         name=body.get("name"))
            target_slot = slot_for_payload(payload)
            result, _ = self.compute(target_slot, payload)
            return json_response({
                "slot": target_slot,
                "payload": payload,
                "draft": self.store.load(target_slot),
                "drafts": self.store.list_drafts(),
                "allocation": {
                    "eventId": payload["event"]["id"],
                    "quests": [tier["quest"] for tier in payload["tiers"]],
                    "reserved": False,
                },
                "preview": self.public(result),
            })
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            raise DraftError(str(exc)) from exc

    def routes(self):
        return [*self.deliveries.routes(), ("GET", re.compile(r"^/api/scenes/schema$"), self.schema),
                ("GET", re.compile(r"^/api/scenes/drafts$"), self.drafts),
                ("POST", re.compile(r"^/api/scenes/(?P<mode>hell-pumpkin)/clone$"), self.clone),
                ("GET", re.compile(rf"^/api/scenes/(?P<mode>{SCENE_SLOT_PATTERN})$"), self.read),
                ("POST", re.compile(rf"^/api/scenes/(?P<mode>{SCENE_SLOT_PATTERN})/(?P<action>preview|save)$"), self.edit)]

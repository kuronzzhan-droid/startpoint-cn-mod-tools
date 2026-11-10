"""HTTP surface for the corridor editor: /api/corridor/... (writes guarded by the studio WriteGuard)."""
from __future__ import annotations

import json
import re
import threading

from . import catalog, commands as cmds, diff as differ, effects as fx, encounters as enc, jsonio, release, rulesfields
from .layout import MASTER_FILES, RUNTIME_FILES, load_config
from .store import ConflictError, CorridorStore, StoreError
from .trial import Trial
from .validate import validate
from .workspace import build_workspace, import_from_sources, dump

SETUP_HINT = ('在 profiles/local.json 加 "rogue_corridor": {"data_dir": "<回廊 data 目录>", '
              '"proto_server": "<proto-server 目录>", "store": "<编辑台存档目录，可省略>"}，然后重启编辑台')


def _q(query, name, default=""):
    return (query.get(name) or [default])[0]


def forbidden_roots() -> list:
    """Real server roots from the profile (paths.server, servers.*.root) that apply must never touch."""
    from wf.paths import profile_data, root_path
    data, _ = profile_data()
    roots = []
    candidates = [(data.get("paths") or {}).get("server")]
    candidates += [(s or {}).get("root") for s in (data.get("servers") or {}).values() if isinstance(s, dict)]
    for raw in candidates:
        if isinstance(raw, str) and raw.strip():
            from pathlib import Path
            p = Path(raw).expanduser()
            roots.append(p if p.is_absolute() else root_path() / p)
    return roots


class CorridorService:
    def __init__(self, app, config=None, trial_runner=None):
        self.app = app
        self._config = config
        self._config_error = None
        self._trial_runner = trial_runner
        self._validation_cache: dict = {}
        self._lock = threading.Lock()
        if config is None:
            try:
                self._config = load_config(app.ops.store.root / "rogue-corridor")
            except (ValueError, OSError) as exc:
                self._config_error = str(exc)

    # -- context ------------------------------------------------------------
    @property
    def cfg(self):
        if self._config is None:
            raise StoreError(self._config_error or ("还没配置深渊回廊编辑：" + SETUP_HINT))
        return self._config

    @property
    def store(self) -> CorridorStore:
        return CorridorStore(self.cfg.store)

    def master(self):
        paths = {spec.key: self.cfg.source_path(spec) for spec in MASTER_FILES}
        return catalog.load_master(paths["tier_table"], paths["soul_catalog"])

    def workspace(self) -> dict:
        return self.store.load()

    def base_workspace(self) -> dict | None:
        path = self.store.base_dir / "workspace.json"
        return jsonio.read_json(path) if path.is_file() else None

    def validation(self, ws: dict) -> dict:
        master = self.master()
        upstream = self.upstream_changes(ws)
        key = (jsonio.digest(ws), master.tier_sha, master.soul_sha, ws["revision"], tuple(upstream))
        with self._lock:
            if key in self._validation_cache:
                return self._validation_cache[key]
        result = validate(ws, master, self.base_workspace())
        if upstream:
            result["findings"].append({"code": "W-012", "severity": "warning", "pointer": "/source/runtime_files_sha256",
                                       "entity_type": "source", "entity_id": None, "related_ids": upstream,
                                       "message": "源文件在导入后被改动（编辑台不会覆盖源文件）：" + "、".join(upstream),
                                       "suggested_fix": "需要吸收上游改动时用「重新从源文件导入」（会先自动快照）"})
            result["warnings"] += 1
        with self._lock:
            self._validation_cache = {key: result}
        return result

    def upstream_changes(self, ws) -> list[str]:
        changed = []
        for spec in RUNTIME_FILES:
            path = self.cfg.source_path(spec)
            sha = jsonio.sha256(path.read_bytes()) if path.is_file() else None
            if sha != ws["source"]["runtime_files_sha256"].get(spec.name):
                changed.append(spec.name)
        return changed

    def trial(self) -> Trial:
        return Trial(self.cfg, self.store, forbidden_roots(), runner=self._trial_runner)

    # -- helpers --------------------------------------------------------------
    def _commit(self, ws, expected, action, detail=None):
        saved = self.store.save(ws, expected, action, detail)
        result = self.validation(saved)
        return {"revision": saved["revision"], "validation": _summary(result)}

    # -- routes ---------------------------------------------------------------
    def routes(self):
        p = r"^/api/corridor"
        return [
            ("GET", re.compile(p + r"/status$"), self.status),
            ("GET", re.compile(p + r"/workspace$"), self.get_workspace),
            ("GET", re.compile(p + r"/registry$"), self.registry),
            ("GET", re.compile(p + r"/characters$"), self.characters),
            ("GET", re.compile(p + r"/characters/(?P<cid>\d+)$"), self.character),
            ("GET", re.compile(p + r"/weapons$"), self.weapons),
            ("GET", re.compile(p + r"/souls$"), self.souls),
            ("GET", re.compile(p + r"/relics$"), self.relics),
            ("GET", re.compile(p + r"/events$"), self.events),
            ("GET", re.compile(p + r"/encounters$"), self.encounters),
            ("GET", re.compile(p + r"/locales$"), self.locales),
            ("GET", re.compile(p + r"/rules$"), self.rules),
            ("GET", re.compile(p + r"/validation$"), self.get_validation),
            ("GET", re.compile(p + r"/diff$"), self.diff),
            ("GET", re.compile(p + r"/releases$"), self.releases),
            ("GET", re.compile(p + r"/snapshots$"), self.snapshots),
            ("GET", re.compile(p + r"/trial$"), self.trial_status),
            ("GET", re.compile(p + r"/trial/plan$"), self.trial_plan),
            ("GET", re.compile(p + r"/deploys$"), self.deploys),
            ("GET", re.compile(p + r"/audit$"), self.audit),
            ("GET", re.compile(p + r"/export$"), self.export),
            ("POST", re.compile(p + r"/import/source$"), self.import_source),
            ("POST", re.compile(p + r"/import/workspace$"), self.import_workspace),
            ("POST", re.compile(p + r"/commands$"), self.commands),
            ("POST", re.compile(p + r"/validate$"), self.post_validate),
            ("POST", re.compile(p + r"/build$"), self.build),
            ("POST", re.compile(p + r"/snapshots$"), self.create_snapshot),
            ("POST", re.compile(p + r"/snapshots/(?P<sid>s\d{4}-\d{8}T\d{6})/restore$"), self.restore_snapshot),
            ("POST", re.compile(p + r"/trial/apply$"), self.trial_apply),
            ("POST", re.compile(p + r"/trial/rollback$"), self.trial_rollback),
            ("POST", re.compile(p + r"/trial/restore-original$"), self.trial_restore_original),
            ("POST", re.compile(p + r"/trial/stop$"), self.trial_stop),
            ("POST", re.compile(p + r"/trial/start$"), self.trial_start),
        ]

    # -- GET ------------------------------------------------------------------
    def status(self, query):
        if self._config is None:
            return {"configured": False, "hint": self._config_error or SETUP_HINT}
        cfg = self.cfg
        out = {"configured": True, "config": cfg.public(), "workspace": None}
        master = self.master()
        meta = (master.tier_table or {}).get("meta") or {}
        out["master"] = {"errors": master.error, "tier_sha256": master.tier_sha, "soul_sha256": master.soul_sha,
                         "source_version": meta.get("source_version"), "status": meta.get("status"),
                         "runtime_tested": meta.get("runtime_tested"), "counts_by_tier": meta.get("counts_by_tier"),
                         "characters": len(master.characters()), "excluded_characters": len(master.excluded_characters()),
                         "weapons": len(master.weapons()), "pending_weapons": len(master.pending_weapons()),
                         "souls": len(master.soul_list())}
        if not self.store.exists():
            return out
        ws = self.workspace()
        result = self.validation(ws)
        rules = ws["data"]["rules"]
        out["workspace"] = {"revision": ws["revision"], "source": ws["source"],
                            "counts": {"relics": len(ws["data"]["relics"]), "events": len(ws["data"]["events"]),
                                       "overrides": len(((ws["data"]["pool_overlay"].get("tier_overrides") or {}).get("characters") or {})),
                                       "tombstones": len(ws["lifecycle"]["tombstones"])},
                            "active_profile": (rules.get("difficulty") or {}).get("active_profile"),
                            "locks_ok": ws["source"]["tier_table_sha256"] == master.tier_sha
                            and ws["source"]["soul_catalog_sha256"] == master.soul_sha,
                            "upstream_changed": self.upstream_changes(ws)}
        out["validation"] = result
        out["releases"] = release.releases(self.store)[:5]
        out["snapshots"] = self.store.snapshots()[:5]
        return out

    def get_workspace(self, query):
        ws = self.workspace()
        return {"workspace": ws}

    def registry(self, query):
        return {**fx.registry(), "templates": fx.templates(), "rules_groups": rulesfields.GROUPS}

    def _pool(self, kind):
        ws = self.workspace()
        master = self.master()
        rules, pol = ws["data"]["rules"], ws["policy"]
        if kind == "character":
            items = catalog.character_pool(master, rules, ws["data"]["pool_overlay"], pol)
        elif kind == "weapon":
            items = catalog.weapon_pool(master, rules, pol)
        else:
            items = catalog.soul_pool(master, pol)
        return ws, items

    def characters(self, query):
        ws, items = self._pool("character")
        page = catalog.filter_page(items, query, ("id", "name", "code"))
        bp = (ws["data"]["rules"].get("v3f") or {}).get("boss_playable") or {}
        summary = {"in_pool": sum(1 for c in items if c["in_pool"]), "boss_playable": sum(1 for c in items if c["boss_playable"] and c["in_pool"]),
                   "overrides": sum(1 for c in items if c["override"]), "total": len(items),
                   "by_tier": {str(t): sum(1 for c in items if c["in_pool"] and c["effective_tier"] == t) for t in range(1, 5)}}
        return {"revision": ws["revision"], **page, "summary": summary, "boss_playable": bp}

    def character(self, query, cid):
        ws, items = self._pool("character")
        item = next((c for c in items if c["id"] == cid), None)
        if item is None:
            raise StoreError(f"主数据里没有角色 {cid}")
        master = self.master()
        row = next((c for c in master.characters() + master.excluded_characters() if str(c.get("id")) == cid), {})
        detail = {k: row.get(k) for k in ("tier_reason", "rule_reason", "release_source", "overridable", "first_seen",
                                           "server_registered", "server_base_registered", "starter_profile")}
        return {"revision": ws["revision"], "item": item, "master": detail}

    def weapons(self, query):
        ws, items = self._pool("weapon")
        page = catalog.filter_page(items, query, ("id", "name", "code"))
        return {"revision": ws["revision"], **page,
                "summary": {"in_pool": sum(1 for w in items if w["in_pool"]), "pending": sum(1 for w in items if w["group"] == "pending_element"),
                            "excluded": sum(1 for w in items if w["group"] == "excluded"), "total": len(items)}}

    def souls(self, query):
        ws, items = self._pool("soul")
        page = catalog.filter_page(items, query, ("id", "name"))
        rules = ws["data"]["rules"]
        return {"revision": ws["revision"], **page,
                "rules": {"guaranteed_chests_per_act": (rules.get("souls") or {}).get("guaranteed_chests_per_act"),
                          "duplicates": (rules.get("souls") or {}).get("duplicates"),
                          "shop_souls": (rules.get("shop") or {}).get("souls"), "soul_price": (rules.get("shop") or {}).get("soul_price"),
                          "extract_soul_price": (rules.get("shop") or {}).get("extract_soul_price"),
                          "elite_soul_chance": (rules.get("rewards") or {}).get("elite_soul_chance")}}

    def relics(self, query):
        ws = self.workspace()
        data = ws["data"]
        aliases = fx.relic_aliases(data["rules"])
        zh, en = data["locales"].get("zh") or {}, data["locales"].get("en") or {}
        result = self.validation(ws)
        out = []
        for r in data["relics"]:
            rid = r.get("relic_id")
            settled = fx.server_relic(r, aliases)
            effects = r["effects"] if isinstance(r.get("effects"), list) else [r.get("effect")]
            out.append({"relic": r, "effects": effects, "shape": "effects" if "effects" in r else "effect",
                        "zh": {"name": zh.get(r.get("name_key")), "desc": zh.get(r.get("desc_key"))},
                        "en": {"name": en.get(r.get("name_key")), "desc": en.get(r.get("desc_key"))},
                        "settled": settled, "settled_text": [fx.describe_settled(e) for e in settled.get("effects", [])],
                        "combat": any(e.get("runtime") == "client_pending" for e in settled.get("effects", [])),
                        "policy": ws["policy"]["relics"].get(rid, {}),
                        "findings": [x for x in result["findings"] if x.get("entity_type") == "relic" and x.get("entity_id") == rid]})
        return {"revision": ws["revision"], "relics": out,
                "tombstones": [t for t in ws["lifecycle"]["tombstones"] if t["kind"] == "relic"]}

    def events(self, query):
        ws = self.workspace()
        data = ws["data"]
        aliases = fx.event_aliases(data["rules"])
        zh, en = data["locales"].get("zh") or {}, data["locales"].get("en") or {}
        result = self.validation(ws)
        out = []
        for ev in data["events"]:
            eid = ev.get("event_id")
            ids = ws["policy"]["event_option_ids"].get(eid) or []
            options = [{"option_id": ids[i] if i < len(ids) else None, "index": i, "option": o,
                        "zh": zh.get(o.get("label_key")), "en": en.get(o.get("label_key"))}
                       for i, o in enumerate(ev.get("options") or [])]
            out.append({"event": ev, "options": options, "settled": fx.server_event(ev, aliases),
                        "zh": {"title": zh.get(ev.get("title_key")), "text": zh.get(ev.get("text_key"))},
                        "en": {"title": en.get(ev.get("title_key")), "text": en.get(ev.get("text_key"))},
                        "policy": ws["policy"]["events"].get(eid, {}),
                        "findings": [x for x in result["findings"] if x.get("entity_type") == "event" and x.get("entity_id") == eid]})
        return {"revision": ws["revision"], "events": out,
                "tombstones": [t for t in ws["lifecycle"]["tombstones"] if t["kind"] in ("event", "event_option")]}

    def encounters(self, query):
        ws = self.workspace()
        data = ws["data"]
        view = enc.acts_view(data["rules"], data["encounter_pool"])
        rank = {q: i + 1 for i, q in enumerate(view["ranked"])}
        acts_of = {}
        for a in view["acts"]:
            for q in a["quests"]:
                acts_of.setdefault(q, []).append(a["act"])
        for e in view["host"]:
            e["rank"] = rank.get(e["quest_id"])
            e["excluded"] = e["round"] in view["excluded_rounds"]
            e["acts"] = acts_of.get(e["quest_id"], [])
            e["policy"] = ws["policy"]["encounters"].get(e["quest_id"], {})
        enc_cfg = data["rules"].get("encounters") or {}
        return {"revision": ws["revision"], **view, "boss_rounds": enc_cfg.get("boss_rounds"),
                "boss_elements": (data["rules"].get("v3f") or {}).get("boss_elements"),
                "act_policy": ws["policy"]["acts"], "meta": (data["encounter_pool"].get("meta") or {})}

    def locales(self, query):
        ws = self.workspace()
        data = ws["data"]
        zh, en = data["locales"].get("zh") or {}, data["locales"].get("en") or {}
        owners = {}
        for r in data["relics"]:
            for k in (r.get("name_key"), r.get("desc_key")):
                owners[k] = ("relic", r.get("relic_id"))
        for ev in data["events"]:
            for k in (ev.get("title_key"), ev.get("text_key"), *[o.get("label_key") for o in ev.get("options") or []]):
                owners[k] = ("event", ev.get("event_id"))
        keys = list(dict.fromkeys(list(zh) + list(en) + list(owners)))
        text = _q(query, "q").strip().lower()
        missing = _q(query, "missing") == "1"
        items = []
        for k in keys:
            row = {"key": k, "zh": zh.get(k), "en": en.get(k), "owner": owners.get(k)}
            row["missing"] = [lang for lang, v in (("zh", row["zh"]), ("en", row["en"])) if not (v or "").strip()]
            if missing and not row["missing"]:
                continue
            if text and text not in k.lower() and text not in (row["zh"] or "").lower() and text not in (row["en"] or "").lower():
                continue
            items.append(row)
        return {"revision": ws["revision"], "count": len(items), "items": items,
                "totals": {"zh": len(zh), "en": len(en), "missing": sum(1 for k in keys if not (zh.get(k) or "").strip() or not (en.get(k) or "").strip())}}

    def rules(self, query):
        ws = self.workspace()
        return {"revision": ws["revision"], "fields": rulesfields.view(ws["data"]["rules"]), "groups": rulesfields.GROUPS,
                "rules": ws["data"]["rules"]}

    def get_validation(self, query):
        return self.validation(self.workspace())

    def diff(self, query):
        ws = self.workspace()
        against = _q(query, "against", "base")
        base, before_files = None, None
        store = self.store
        if against == "base":
            base = self.base_workspace()
            label = "导入基线"
            before_files = {spec.release: raw for spec in RUNTIME_FILES if (raw := store.base_raw().get(spec.name)) is not None}
        elif against.startswith("release:") or against == "trial":
            if against == "trial":
                active = self.trial().active()
                if active["kind"] != "release":
                    base = self.base_workspace()
                    label = f"试验服（{active['label']}，按导入基线对比）"
                    before_files = {spec.release: raw for spec in RUNTIME_FILES if (raw := store.base_raw().get(spec.name)) is not None}
                else:
                    against = "release:" + active["version"]
            if base is None:
                path = release.release_dir(store, against.split(":", 1)[1])
                data = release.workspace_from_release(path)
                files = release.read_files(path)
                policy = json.loads(files["rogue_pool_policy.json"].decode("utf-8"))
                base = {"data": data, "policy": policy["policy"], "lifecycle": policy["lifecycle"]}
                before_files = {k: v for k, v in files.items() if not k.startswith(("data/tier_table", "data/rules_v3"))}
                label = "发布包 " + release.short(against)
        elif against.startswith("snapshot:"):
            base = store.load_snapshot(against.split(":", 1)[1])
            label = "快照 " + against.split(":", 1)[1]
            before_files = release.compile_runtime(base, store.base_raw())
        else:
            raise StoreError("against 只能是 base / trial / release:<版本> / snapshot:<ID>")
        if base is None:
            raise StoreError("没有导入基线")
        after_files = release.compile_runtime(ws, store.base_raw())
        before_files = {k: v for k, v in (before_files or {}).items()}
        if "rogue_pool_policy.json" not in before_files and against == "base":
            before_files["rogue_pool_policy.json"] = release.compile_runtime(base, store.base_raw())["rogue_pool_policy.json"]
        master = self.master()
        pointers = differ.pointer_diff({"data": base["data"], "policy": base["policy"]},
                                       {"data": ws["data"], "policy": ws["policy"]})
        return {"revision": ws["revision"], "against": against, "label": label,
                "readable": differ.readable(base, ws, master), "pointers": pointers[:1000], "pointer_count": len(pointers),
                "files": differ.file_changes(before_files, after_files),
                "impact": differ.impact(base, ws, master)}

    def releases(self, query):
        return {"releases": release.releases(self.store)}

    def snapshots(self, query):
        return {"snapshots": self.store.snapshots()}

    def trial_status(self, query):
        trial = self.trial()
        status = trial.status()
        runs = trial.open_runs()
        return {"status": status, "active": trial.active(), "deploy_state": trial.deploy_state(),
                "open_runs": [{k: r.get(k) for k in ("run_id", "player_id", "status", "revision", "updated_at", "error")}
                              | {"floor": (r.get("run") or {}).get("floor")} for r in runs]}

    def trial_plan(self, query):
        version = _q(query, "version")
        return self.trial().plan(version)

    def deploys(self, query):
        return {"deploys": self.trial().deploys()}

    def audit(self, query):
        return {"audit": self.store.audit_tail(100)}

    def export(self, query):
        from ..server import Response
        fmt = _q(query, "format", "workspace")
        if fmt == "workspace":
            ws = self.workspace()
            body = dump(ws)
            return Response(200, body, "application/json; charset=utf-8",
                            headers=(("Content-Disposition", f'attachment; filename="rogue-corridor-workspace-r{ws["revision"]}.json"'),))
        if fmt == "runtime":
            version = _q(query, "version")
            path = release.release_dir(self.store, version)
            body = release.export_zip(path)
            return Response(200, body, "application/zip",
                            headers=(("Content-Disposition", f'attachment; filename="rogue-corridor-{path.name}.zip"'),))
        raise StoreError("format 只能是 workspace 或 runtime")

    # -- POST -----------------------------------------------------------------
    def _expected(self, body):
        revision = body.get("revision")
        if revision is not None and (not isinstance(revision, int) or isinstance(revision, bool)):
            raise StoreError("revision 必须是整数")
        return revision

    def import_source(self, query, body):
        store = self.store
        expected = self._expected(body)
        with store.lock:
            previous = store.load() if store.exists() else None
            if previous is not None:
                store.snapshot(previous, "重新导入前自动快照", kind="auto")
            ws, raws = import_from_sources(self.cfg, previous)
            store.write_base(raws)
            jsonio.atomic_write(store.base_dir / "workspace.json", dump({**ws, "revision": 0}))
            saved = store.save(ws, expected if previous is not None else None, "import.source",
                               {"files": sorted(raws), "label": ws["source"]["import_label"]})
        result = self.validation(saved)
        return {"revision": saved["revision"], "validation": _summary(result)}

    def import_workspace(self, query, body):
        doc = body.get("workspace")
        if not isinstance(doc, dict) or doc.get("document_type") != "rogue_content_workspace" or doc.get("content_id") != "abyss_corridor":
            raise StoreError("不是深渊回廊工作区文件（document_type/content_id 不符）")
        from .validate import schema_errors
        errors = schema_errors(doc)
        if errors:
            raise StoreError("工作区结构校验失败：" + "；".join(f"{e['pointer']} {e['message']}" for e in errors[:5]))
        store = self.store
        expected = self._expected(body)
        with store.lock:
            current = store.load()
            store.snapshot(current, "导入工作区前自动快照", kind="auto")
            doc = json.loads(json.dumps(doc))
            # IDs never come back: keep every reserved ID and tombstone we already know.
            for key in ("reserved_relic_ids", "reserved_event_ids", "reserved_option_ids"):
                doc["lifecycle"][key] = list(dict.fromkeys(current["lifecycle"][key] + doc["lifecycle"][key]))
            known = {(t["kind"], t["id"]) for t in doc["lifecycle"]["tombstones"]}
            alive = {("relic", r.get("relic_id")) for r in doc["data"]["relics"]} | {("event", e.get("event_id")) for e in doc["data"]["events"]}
            doc["lifecycle"]["tombstones"] += [t for t in current["lifecycle"]["tombstones"]
                                               if (t["kind"], t["id"]) not in known and (t["kind"], t["id"]) not in alive]
            saved = store.save(doc, expected, "import.workspace", {"revision_in_file": body["workspace"].get("revision")})
        return {"revision": saved["revision"], "validation": _summary(self.validation(saved))}

    def commands(self, query, body):
        if set(body) - {"revision", "commands", "message"}:
            raise StoreError("请求只接受 revision / commands / message")
        store = self.store
        expected = self._expected(body)
        with store.lock:
            ws = store.load()
            if ws["revision"] != expected:
                raise ConflictError(f"工作区已被改动（当前 revision {ws['revision']}，请求基于 {expected}），请刷新后重做")
            try:
                new, results = cmds.apply(ws, body.get("commands"), self.master())
            except cmds.CommandError as exc:
                raise StoreError(str(exc)) from None
            out = self._commit(new, expected, "commands", {"message": body.get("message"),
                                                           "ops": [c.get("op") for c in body["commands"]][:50], "results": results[:50]})
        return {**out, "results": results}

    def post_validate(self, query, body):
        return self.validation(self.workspace())

    def build(self, query, body):
        store = self.store
        expected = self._expected(body)
        message = body.get("message") or ""
        if not isinstance(message, str):
            raise StoreError("message 必须是文本")
        with store.lock:
            ws = store.load()
            if ws["revision"] != expected:
                raise ConflictError(f"工作区已被改动（当前 revision {ws['revision']}），请刷新后重新构建")
            result = self.validation(ws)
            manifest = release.build(store, self.cfg, ws, result, message)
            if not manifest.get("reused"):
                store.snapshot(ws, f"构建 {release.short(manifest['content_version'])}：{message}", kind="build")
            store.audit({"action": "build", "revision": ws["revision"], "content_version": manifest["content_version"],
                         "reused": manifest.get("reused")})
        return {"release": {k: manifest.get(k) for k in ("content_version", "workspace_revision", "created_at", "message",
                                                         "validation_summary", "active_profile", "reused", "files")}}

    def create_snapshot(self, query, body):
        ws = self.workspace()
        message = body.get("message") or "手动快照"
        if not isinstance(message, str):
            raise StoreError("message 必须是文本")
        return {"snapshot": self.store.snapshot(ws, message)}

    def restore_snapshot(self, query, body, sid):
        store = self.store
        expected = self._expected(body)
        with store.lock:
            current = store.load()
            snap = store.load_snapshot(sid)
            store.snapshot(current, f"恢复 {sid} 前自动快照", kind="auto")
            restored = json.loads(json.dumps(snap))
            for key in ("reserved_relic_ids", "reserved_event_ids", "reserved_option_ids"):
                restored["lifecycle"][key] = list(dict.fromkeys(current["lifecycle"][key] + restored["lifecycle"][key]))
            alive = {("relic", r.get("relic_id")) for r in restored["data"]["relics"]} | \
                {("event", e.get("event_id")) for e in restored["data"]["events"]} | \
                {("event_option", o) for ids in restored["policy"]["event_option_ids"].values() for o in ids}
            seen = set()
            tombs = []
            for t in current["lifecycle"]["tombstones"] + restored["lifecycle"]["tombstones"]:
                k = (t["kind"], t["id"])
                if k not in alive and k not in seen:
                    seen.add(k)
                    tombs.append(t)
            restored["lifecycle"]["tombstones"] = tombs
            out = self._commit(restored, expected, "snapshot.restore", {"snapshot": sid})
        return out

    def _trial_body(self, body, keys):
        extra = set(body) - keys
        if extra:
            raise StoreError("不支持的参数：" + "、".join(sorted(extra)))

    def trial_apply(self, query, body, action="apply"):
        self._trial_body(body, {"version", "expected_active", "acknowledge_open_runs", "start"})
        version, expected = body.get("version"), body.get("expected_active")
        if not isinstance(version, str) or not isinstance(expected, str):
            raise StoreError("需要 version 与 expected_active（确认时看到的试验服当前内容）")
        result = self.trial().apply(version, expected, bool(body.get("acknowledge_open_runs")),
                                    body.get("start", True) is not False, action)
        self.store.audit({"action": "trial." + action, "version": version, "result": result.get("result")})
        return result

    def trial_rollback(self, query, body):
        return self.trial_apply(query, body, action="rollback")

    def trial_restore_original(self, query, body):
        self._trial_body(body, {"expected_active", "start"})
        if not isinstance(body.get("expected_active"), str):
            raise StoreError("需要 expected_active")
        result = self.trial().restore_original(body["expected_active"], body.get("start"))
        self.store.audit({"action": "trial.restore_original", "result": result.get("result")})
        return result

    def trial_stop(self, query, body):
        return self.trial().stop()

    def trial_start(self, query, body):
        return self.trial().start()


def _summary(result: dict) -> dict:
    return {"blockers": result["blockers"], "warnings": result["warnings"]}


class CorridorRoutes:
    """Adapter to the studio route table: JSON responses and HTTP status mapping."""

    def __init__(self, app, service: CorridorService | None = None):
        self.service = service or CorridorService(app)

    def routes(self):
        from ..server import Response, error, json_response

        def wrap(handler):
            def call(**kwargs):
                try:
                    result = handler(**kwargs)
                except ConflictError as exc:
                    return error(409, str(exc))
                except StoreError as exc:
                    return error(400, str(exc))
                except (OSError, ValueError) as exc:
                    return error(500, f"{type(exc).__name__}: {exc}")
                return result if isinstance(result, Response) else json_response(result)
            return call
        return [(verb, pattern, wrap(handler)) for verb, pattern, handler in self.service.routes()]

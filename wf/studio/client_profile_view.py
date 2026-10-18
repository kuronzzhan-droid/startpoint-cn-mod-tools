"""编辑台「目标客户端」只读胶水：档案说明、按标记/数据行/程序查能力需求、全角色兼容报告。

能力判断全部复用 ``wf.caps``（registry 数据面、``table_signals``/``dsl_signals`` 信号提取、
``check_compat`` 档案比较），这里只做三件事：

* 进程内缓存注册表、每个档案的 provides 证据与「能力集合 → 各档案比较结果」，
  让编辑器的行内标记不必每次重读 600 KB 证据（``/api/capabilities/requirements`` 单次约 2–3 秒）；
* 把一行词条 / 一个技能程序沿引用走到固有状态字符串、配置字符串和 DSL，得到与交付相同的信号；
* 读入库的全角色兼容报告 ``docs/m2/compat-v34-v35.json``，供角色列表筛选。

只读：不写草稿、不写交付；结果只说明已登记能力与离线方法证据，不代表设备验收。
"""
from __future__ import annotations

import csv
import io
import json
import re
import threading
from collections import deque
from pathlib import Path

from wf.dsl.references import DSL_SUFFIX, program_logical

from .drafts import DraftError

REPOSITORY = Path(__file__).resolve().parents[2]
COMPAT_REPORT = REPOSITORY / "docs" / "m2" / "compat-v34-v35.json"
ROW_TABLES = {"ability": "master/ability/ability.orderedmap",
              "leader_ability": "master/ability/leader_ability.orderedmap",
              "action_skill": "master/skill/action_skill.orderedmap"}
LOOKUP_PARAMS = ("kind", "unique", "dsl", "selector", "customKey", "capability")
CONTENT_BLOCKS = {"instant_content", "during_content"}
SATISFIED = {"静态证据满足", "能力满足，方法待补"}
MAX_STEPS = 400
NOTE = "只比较已登记能力与离线方法证据；没有命中不证明未知写法有效，也不代表装机实测。"


def _csv(cells) -> str:
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="").writerow(["" if c is None else str(c) for c in cells])
    return buffer.getvalue()


def short_label(profile_id: str, record: dict | None = None) -> str:
    if record and record.get("label"):
        return str(record["label"])
    return profile_id.removeprefix("test-")


class ClientProfileView:
    """Cached, read-only capability answers for the editor UI."""

    def __init__(self, app):
        self.app = app
        self._lock = threading.Lock()
        self._registry = None
        self._clients: dict | None = None
        self._compat: dict = {}
        self._report = None
        self._default: str | None = None

    # -- cached inputs ----------------------------------------------------
    def registry(self) -> dict:
        with self._lock:
            if self._registry is None:
                from wf.caps.registry import load_registry
                self._registry = load_registry()
            return self._registry

    def clients(self) -> dict:
        """{profile: {"document": provides | None, "error": str | None, "record": profile record}}."""
        with self._lock:
            if self._clients is not None:
                return self._clients
        from wf.caps.profiles import load_profiles, read_client, resolve_client
        default, records = load_profiles()
        clients = {}
        for name, record in records.items():
            if not record.get("provides"):
                continue
            try:
                path, _ = resolve_client(client_profile=name)
                clients[name] = {"document": read_client(path), "error": None, "record": record, "path": path}
            except (OSError, ValueError) as exc:
                clients[name] = {"document": None, "error": str(exc), "record": record, "path": None}
        with self._lock:
            self._clients = clients
            self._default = default
        return clients

    def prewarm(self) -> None:
        """Load the registry and every profile's evidence once (the slow part of the first chip)."""
        self.registry()
        self.clients()
        self.compat(())

    def default_profile(self) -> str:
        self.clients()
        return self._default

    # -- capability sets → per-profile comparison ------------------------
    def compat(self, ids, partial=False) -> dict:
        key = tuple(sorted(set(ids))), bool(partial)
        with self._lock:
            if key in self._compat:
                return self._compat[key]
        from wf.caps.compat import check_compat
        registry = self.registry()
        patches = sorted({n for cid in key[0] if cid in registry for n in registry[cid]["provided_by"]["patches"]})
        requires = {"schemaVersion": 2, "pack": {"since": "0.0.0", "tail": "0.0.1",
                    "anchor": {"from": "0.0.0", "to": "0.0.1"}, "archives": ["query.zip"]},
                    "requires": {"clientCapabilities": list(key[0]), "clientPatches": [f"#{n}" for n in patches],
                                 "serverFeatures": [], "serverRestart": False, "restartReasons": [],
                                 "minServerVersion": None,
                                 "capabilityResolution": "partial" if partial else "resolved"}}
        result = {}
        for name, client in self.clients().items():
            if client["document"] is None:
                result[name] = {"compatible": False, "error": client["error"], "missing": [], "pending": []}
                continue
            try:
                checks = check_compat(requires, client["document"], registry=registry)
            except (OSError, ValueError) as exc:
                result[name] = {"compatible": False, "error": str(exc), "missing": [], "pending": []}
                continue
            missing = [self._missing(c) for c in checks if c.get("blocking")]
            pending = [{"id": c.get("id"), "message": c.get("message")} for c in checks
                       if not c.get("blocking") and c.get("status") == "待验证"]
            result[name] = {"compatible": not missing, "missing": missing, "pending": pending}
        with self._lock:
            self._compat[key] = result
        return result

    def _missing(self, check: dict) -> dict:
        registry = self.registry()
        cid = check.get("id")
        cap = registry.get(cid) if cid else None
        return {"id": cid, "rule": check.get("rule"), "message": check.get("message"),
                "title": cap["title"] if cap else None,
                "patches": check.get("patches", cap["provided_by"]["patches"] if cap else []),
                "missingPatches": check.get("missing_patches", [])}

    def describe_ids(self, ids, *, unsupported=(), signals=(), references=(), placement=()) -> dict:
        registry = self.registry()
        ids = sorted(set(ids))
        compat = self.compat(ids, bool(unsupported))
        capabilities = [{"id": cid, "title": registry[cid]["title"] if cid in registry else cid,
                         "layer": registry.get(cid, {}).get("layer"),
                         "official": registry.get(cid, {}).get("layer") == "B",
                         "patches": registry[cid]["provided_by"]["patches"] if cid in registry else []}
                        for cid in ids]
        return {"capabilities": capabilities,
                "requiredClientProfiles": [name for name, r in compat.items() if r["compatible"]],
                "profiles": compat,
                "recognized": bool(ids) and not unsupported,
                "unsupported": list(unsupported), "placement": list(placement),
                "references": list(references),
                "signals": [{"kind": k, "value": v} for k, v in signals],
                "note": NOTE}

    def describe_signals(self, signals, *, references=(), placement=()) -> dict:
        from wf.caps.query import requirements_for_signals
        signals = list(dict.fromkeys(signals))
        unsupported = [v for k, v in signals if k == "unsupported"]
        ids = requirements_for_signals([s for s in signals if s[0] != "unsupported"], self.registry())
        return self.describe_ids(ids, unsupported=unsupported, signals=signals, references=references,
                                 placement=placement)

    # -- signal extraction -------------------------------------------------
    def marker_signals(self, query) -> list:
        """Same parameters and signal mapping as ``wf.caps.query.query_requirements``."""
        from wf.caps.signals_v35 import custom_signals, unique_signals
        signals = [("kinds", v) for v in query.get("kind", [])]
        dsl = query.get("dsl", [])
        signals += [("dsl_nodes", v) for v in dsl]
        signals += [("selectors", v) for v in (*dsl, *query.get("selector", []))]
        uid = (query.get("uniqueId") or [None])[0]
        for value in query.get("unique", []):
            signals.extend(unique_signals(value, uid))
        for value in query.get("customKey", []):
            signals.extend(custom_signals(value))
        return signals

    def close(self, values):
        """Follow references from table/DSL signals: unique → string_id, config strings, skills, PF, programs."""
        from wf.caps.facts import PF, SKILL, STRINGS, UNIQUE, dsl_signals
        from wf.caps.signals_v35 import custom_signals, unique_signals
        signals, references, seen = [], [], set()
        queue, steps = deque(values), 0
        while queue and steps < MAX_STEPS:
            steps += 1
            kind, value = queue.popleft()
            if kind == "kind_site":
                signals.append(("kinds", str(value["kind"])))
                continue
            if kind == "program":
                target = program_logical(value)
                if target is None and str(value).startswith("battle/"):
                    target = value if str(value).endswith(DSL_SUFFIX) else str(value) + DSL_SUFFIX
                if not target or ("program", target) in seen:
                    continue
                seen.add(("program", target))
                try:
                    tree = self.app.source.tree(target)
                except Exception as exc:  # noqa: BLE001 - unreadable DSL is reported, never skipped silently
                    references.append({"type": "program", "path": target, "error": f"{type(exc).__name__}: {exc}"})
                    continue
                if tree is None:
                    references.append({"type": "program", "path": target, "missing": True})
                    continue
                references.append({"type": "program", "path": target})
                try:
                    queue.extend(dsl_signals(tree))
                except ValueError as exc:
                    references.append({"type": "program", "path": target, "error": str(exc)})
                continue
            if kind not in ("ref", "optional_ref"):
                signals.append((kind, value))
                continue
            logical, key = value
            key = str(key)
            if (logical, key) in seen or key in {"", "(None)"}:
                continue
            seen.add((logical, key))
            table = self._table(logical)
            if logical == UNIQUE:
                rows = table.get(key)
                if not rows or not rows[0]:
                    references.append({"type": "unique", "id": key, "missing": True})
                    continue
                references.append({"type": "unique", "id": key, "stringId": rows[0][0],
                                   "name": rows[0][1] if len(rows[0]) > 1 else ""})
                signals.extend(unique_signals(rows[0][0], key))
            elif logical == STRINGS:
                if key not in table:
                    if kind == "ref":
                        references.append({"type": "string", "key": key, "missing": True})
                    continue
                references.append({"type": "string", "key": key})
                signals.extend(custom_signals(key))
                if key.startswith("desc_override_"):
                    signals.append(("selectors", "text.desc_override"))
            elif logical == SKILL:
                levels = table.get(key) or {}
                references.append({"type": "skill", "key": key, "missing": not levels})
                for rows in (levels.values() if isinstance(levels, dict) else [levels]):
                    for row in rows:
                        if len(row) > 7 and row[7] not in {"", "(None)"}:
                            queue.append(("program", row[7]))
            elif logical == PF:
                rows = table.get(key) or []
                references.append({"type": "power_flip", "key": key, "missing": not rows})
                queue.append(("optional_ref", (STRINGS, "wfx_snapcombo_" + key)))
                for row in rows:
                    for cell in row:
                        if program_logical(cell):
                            queue.append(("program", cell))
        return signals, references

    def _table(self, logical) -> dict:
        try:
            return self.app.source.table(logical) or {}
        except (KeyError, FileNotFoundError, ValueError):
            return {}

    def row(self, item: dict) -> dict:
        from wf.caps.facts import table_signals
        table = str(item.get("table") or "")
        if table not in ROW_TABLES:
            raise DraftError(f"不支持的表：{table}")
        key = str(item.get("key") or "")
        cells = item.get("cells")
        if not key or not isinstance(cells, list):
            raise DraftError("每一行需要 key 与 cells")
        level = item.get("level")
        trail = (key,) if level in (None, "") else (key, str(level))
        placement, first = [], []
        try:
            first = list(table_signals(ROW_TABLES[table], trail, _csv(cells), registry=self.registry()))
        except ValueError as exc:
            placement.append(str(exc).removeprefix("问题: "))
        signals, references = self.close(first)
        return self.describe_signals(signals, references=references, placement=placement)

    # -- HTTP --------------------------------------------------------------
    def routes(self):
        return [("GET", re.compile(r"^/api/studio/client-profiles$"), self.profiles),
                ("GET", re.compile(r"^/api/studio/caps/lookup$"), self.lookup),
                ("GET", re.compile(r"^/api/studio/caps/kinds$"), self.kinds),
                ("GET", re.compile(r"^/api/studio/caps/program$"), self.program),
                # Read-only dry run, but POST bodies stay under /api/drafts/ (token-guarded) like ability/check.
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/caps/rows$"), self.rows),
                ("GET", re.compile(r"^/api/studio/character-compat$"), self.character_compat)]

    def profiles(self, query):
        from .server import json_response
        registry = self.registry()
        clients = self.clients()
        default = self.default_profile()
        base = {e["id"] for e in (clients.get(default, {}).get("document") or {}).get("provides", [])}
        out = []
        for name, client in clients.items():
            record = client["record"]
            provided = [e["id"] for e in (client["document"] or {}).get("provides", [])]
            extra = [cid for cid in provided if cid not in base]
            semantic = [{"id": cid, "title": registry[cid]["title"] if cid in registry else cid}
                        for cid in extra if not cid.startswith("client.apk.patch")]
            out.append({"id": name, "label": short_label(name, record), "default": name == default,
                        "description": record.get("description", ""), "packageName": record.get("package_name"),
                        "versionCode": record.get("versionCode"),
                        "verification": (record.get("evidence") or {}).get("verification"),
                        "capabilityCount": len(provided), "extraCount": len(extra), "extra": semantic,
                        "available": client["document"] is not None, "error": client["error"]})
        return json_response({"defaultClientProfile": default, "profiles": out, "note": NOTE})

    def lookup(self, query):
        from .server import json_response
        if not any(query.get(p) for p in LOOKUP_PARAMS):
            raise DraftError("至少给一个 kind / unique / dsl / selector / customKey / capability")
        explicit = query.get("capability", [])
        unknown = [cid for cid in explicit if cid not in self.registry()]
        if unknown:
            raise DraftError("注册表没有能力：" + "、".join(unknown))
        signals = self.marker_signals(query)
        if explicit and not signals:
            return json_response(self.describe_ids(explicit))
        result = self.describe_signals(signals)
        if explicit:
            ids = sorted({c["id"] for c in result["capabilities"]} | set(explicit))
            result = self.describe_ids(ids, unsupported=result["unsupported"],
                                       signals=[(s["kind"], s["value"]) for s in result["signals"]])
        return json_response(result)

    def program(self, query):
        from .server import json_response
        path = (query.get("path") or [""])[0]
        if not path.startswith("battle/"):
            raise DraftError("path 必须是 battle/… 程序路径")
        signals, references = self.close([("program", path)])
        return json_response(self.describe_signals(signals, references=references))

    def rows(self, query, body, cid):
        from .server import json_response
        items = body.get("rows")
        if not isinstance(items, list) or len(items) > 200:
            raise DraftError("rows 必须是不超过 200 项的数组")
        out = {}
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise DraftError("rows 的每一项必须是对象")
            out[str(item.get("id", index))] = self.row(item)
        return json_response({"rows": out})

    def kinds(self, query):
        """kind → capabilities for one table/block, so the template picker can mark every option at once."""
        from .server import json_response
        table = (query.get("table") or ["ability"])[0]
        block = (query.get("block") or ["instant_content"])[0]
        if block not in CONTENT_BLOCKS:
            # Trigger/precondition kinds are other enums; registered kinds only describe content blocks.
            return json_response({"table": table, "block": block, "kinds": {}, "note": NOTE})
        registry = self.registry()
        fits, elsewhere = {}, {}
        for cid, cap in registry.items():
            surface = cap["data_surface"]
            for kind in surface.get("kinds", []):
                tables, blocks = surface.get("allowed_tables") or [], surface.get("allowed_blocks") or []
                ok = (not tables or table in tables) and (not blocks or block in blocks)
                (fits if ok else elsewhere).setdefault(str(kind), []).append(
                    cid if ok else f"{'/'.join(tables) or '任意表'} · {'/'.join(blocks) or '任意区块'}")
        result = {kind: self.describe_ids(ids) for kind, ids in fits.items()}
        for kind, places in elsewhere.items():
            if kind not in fits:
                # wf.caps.facts judges kinds by number: a row here would fail requires derivation at 「生成」,
                # even when this block's enum gives the number another (official) meaning.
                result[kind] = {**self.describe_ids([]), "placement": [
                    f"生成时的能力推导会拦下：注册表只在 {'；'.join(sorted(set(places)))} 登记了 kind {kind}，"
                    f"{table}.{block} 不在其中。若这个区块的同号 kind 是另一个枚举项，属于按编号判断的误报，需要后端确认"]}
        return json_response({"table": table, "block": block, "kinds": result, "note": NOTE})

    def character_compat(self, query):
        from .server import json_response
        report = self._load_report()
        return json_response(report)

    def _load_report(self) -> dict:
        with self._lock:
            if self._report is not None:
                return self._report
        if not COMPAT_REPORT.is_file():
            raise DraftError(f"没有全角色兼容报告：{COMPAT_REPORT.relative_to(REPOSITORY).as_posix()}")
        document = json.loads(COMPAT_REPORT.read_text("utf-8"))
        snapshot = (document.get("snapshots") or [{}])[-1]
        registry = self.registry()
        profiles = list(document.get("profiles", {}))
        characters = {}
        for entry in snapshot.get("characters", []):
            states = {}
            for name in profiles:
                record = (entry.get("profiles") or {}).get(name, {})
                states[name] = {"status": record.get("status"), "satisfied": record.get("status") in SATISFIED,
                                "missing": [{"id": cid, "title": registry[cid]["title"] if cid in registry else cid,
                                             "patches": registry[cid]["provided_by"]["patches"] if cid in registry else []}
                                            for cid in record.get("missing", [])]}
            characters[str(entry.get("id"))] = {"name": entry.get("name"), "title": entry.get("title"),
                                                "origin": entry.get("origin"), "profiles": states}
        report = {"source": COMPAT_REPORT.relative_to(REPOSITORY).as_posix(), "tip": snapshot.get("tip"),
                  "scope": document.get("snapshot_scope"), "liveServerVerified": document.get("live_server_verified"),
                  "deviceVerified": document.get("device_verified"), "scanComplete": snapshot.get("scan_complete"),
                  "profiles": profiles, "summary": snapshot.get("summary", {}), "characters": characters,
                  "note": "全角色兼容报告是入库的离线静态结果，只对报告里的资源版本成立；草稿改动要以「生成」时的检查为准。"}
        with self._lock:
            self._report = report
        return report

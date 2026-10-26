"""Character-owned summon drafts using the shared ID and delivery workflow."""
from __future__ import annotations

import copy
from pathlib import Path

from .drafts import DraftError, DraftStore, new_change_id, now, sha256, status, validate
from .ids import check_id, collect_occupancy, next_id
from .summon_recipe import recipe
from .summon_tables import BALL, CHAR, CUSTOM, Tables, single


def changes(draft):
    return [c for c in (draft or {}).get("changes", []) if c["kind"] == "summon_clone"]


def sync_reservations(draft, removed=()):
    """Release only this feature's previous declarations, then register survivors."""
    registered = {kind: set(values) for kind, values in draft.get("reservations", {}).items()}
    for change in [*removed, *changes(draft)]:
        for kind, values in change["params"].get("reservations", {}).items():
            registered.setdefault(kind, set()).difference_update(values)
    for change in draft["changes"]:
        for kind, values in change.get("params", {}).get("reservations", {}).items():
            registered.setdefault(kind, set()).update(values)
    draft["reservations"] = {kind: sorted(values) for kind, values in registered.items() if values}


def _effective(source, store, draft):
    from .character_clone import clone_change, clone_members, overlay_source
    if clone_change(draft):
        return overlay_source(source, clone_members(source, store, draft))
    return source


def _identity(source, cid, draft):
    if draft and (draft.get("subjectKind", "character") != "character" or "scratch" in draft
                  or draft["baseView"] != source.version or draft["characterId"] != cid):
        raise DraftError("召唤工坊需要同一基线下的正式角色草稿")
    row = single(Tables(source).get(CHAR, cid), "角色草稿主体", 37)
    if draft and draft["code"] != row[0]:
        raise DraftError("草稿代码名与角色主体不一致")
    return row[0]


def _available(source, store, cid, spec, previous, server_dir):
    occupied = collect_occupancy(source, store.root, server_dir)
    prior = previous["params"].get("reservations", {}) if previous else {}
    filename = (store.directory(cid) / "changeset.json").resolve()
    # Updating an owned summon may reuse exactly its own declarations. Other
    # drafts, namespaces, manual reservations and baseline rows still conflict.
    for kind, identities in prior.items():
        for identity in identities:
            other_changes = [c for c in (store.load(cid) or {}).get("changes", [])
                             if c.get("id") != previous["id"] and identity in
                             c.get("params", {}).get("reservations", {}).get(kind, [])]
            if other_changes:
                continue
            occupied[kind][identity] = [owner for owner in occupied[kind].get(identity, [])
                if not (owner["source"] == "draft" and owner["owner"] == cid
                        and Path(owner["location"]).resolve() == filename)]
    allocation = check_id(source, "multiball", spec["id"], occupancy=occupied, server_dir=server_dir)
    if not allocation["available"]:
        raise DraftError(f"multiball ID 已占用：{spec['id']}：{allocation['owners']}")
    return allocation, occupied


def _verified(source, change):
    validate(change, "change")
    spec = change["params"]["spec"]
    if change["target"] != {"multiball": spec["id"]}:
        raise DraftError("召唤 change 目标与 spec.id 不一致")
    for logical, expected in change["params"]["inputs"].items():
        raw = source.raw(logical)
        if (sha256(raw) if raw is not None else None) != expected:
            raise DraftError(f"召唤母本输入已变化，请重新预览并保存：{logical}")
    tables, detail = recipe(source, spec)
    if tables.inputs() != change["params"]["inputs"]:
        raise DraftError("召唤母本输入已变化，请重新预览并保存")
    if (detail["ownedRows"] != change["params"]["ownedRows"]
            or detail["reservations"] != change["params"]["reservations"]):
        raise DraftError("召唤自有键或 ID 预留与编译结果不一致")
    return tables, detail


def compile_summons(source, store, draft, members=None, *, server_dir=None):
    """Merge additions into prior compiler output; retain other modules' edits."""
    output, assertions, checks = dict(members or {}), [], []
    effective = _effective(source, store, draft)
    _identity(effective, draft["characterId"], draft)
    for change in changes(draft):
        tables, detail = _verified(effective, change)
        _, occupied = _available(effective, store, draft["characterId"], change["params"]["spec"], change, server_dir)
        for key in detail["reservations"]["string_id"]:
            if not check_id(effective, "string_id", key, occupancy=occupied)["available"]:
                raise DraftError(f"召唤字符串键已被其他来源预留：{key}")
        compiled = tables.compile(output)
        output.update({("common", logical): raw for logical, raw in compiled.items()})
        checks.extend(detail["checks"])
        assertions.extend({"table": logical, "path": [key], "old": None, "new": value}
                          for logical, values in tables.additions.items() for key, value in values.items())
    changed = {logical: raw for (root, logical), raw in output.items()
               if root == "common" and raw != (members or {}).get((root, logical))}
    return {"client": changed, "changes": assertions, "checks": checks}


class SummonEditor:
    def __init__(self, source, store=None, server_dir=None):
        self.source, self.store, self.server_dir = source, store or DraftStore(), server_dir

    def templates(self, q=""):
        from .summon_catalog import templates
        return templates(self.source, q)

    def read(self, cid):
        draft = self.store.load(cid)
        effective = _effective(self.source, self.store, draft)
        _identity(effective, cid, draft)
        items = []
        for change in changes(draft):
            _, detail = _verified(effective, change)
            items.append({"changeId": change["id"], "characterId": cid,
                          "multiballId": change["params"]["spec"]["id"],
                          "spec": change["params"]["spec"], **detail, "runtime": "未执行"})
        return {"schema": "wf-studio-summons/1", "version": effective.version,
                "characterId": cid, "items": items, "status": status(draft), "runtime": "未执行"}

    def apply(self, cid, request, preview=False):
        validate(request, "summonCloneRequest")
        spec = copy.deepcopy(request)
        body_preview = spec.pop("preview", False)
        preview = preview or body_preview
        with self.store._lock:
            current = self.store.load(cid)
            source = _effective(self.source, self.store, current)
            code = _identity(source, cid, current)
            if "id" not in spec:
                spec["id"] = next_id(source, "multiball", drafts_root=self.store.root,
                                     server_dir=self.server_dir)["id"]
            previous = next((c for c in changes(current) if c["target"]["multiball"] == spec["id"]), None)
            allocation, occupied = _available(source, self.store, cid, spec, previous, self.server_dir)
            tables, detail = recipe(source, spec)
            for key in detail["reservations"]["string_id"]:
                available = check_id(source, "string_id", key, occupancy=occupied, server_dir=self.server_dir)
                if not available["available"]:
                    raise DraftError(f"召唤字符串键已占用：{key}：{available['owners']}")
            result = {"ok": True, "preview": bool(preview), "characterId": cid,
                      "multiballId": spec["id"], "spec": spec, "allocation": allocation,
                      **detail, "runtime": "未执行"}
            if preview:
                return result
            change = {"id": previous["id"] if previous else new_change_id(), "kind": "summon_clone",
                      "title": f"召唤协力角色 {spec['id']}", "createdAt": now(),
                      "target": {"multiball": spec["id"]},
                      "params": {"spec": spec, "inputs": tables.inputs(), "ownedRows": detail["ownedRows"],
                                 "reservations": detail["reservations"]}, "files": [], "pending": [],
                      "checks": [{"level": "error" if c.get("blocking") else "info" if c["status"] == "满足" else "warn",
                                  "code": c["rule"].lower(), "message": c["message"]} for c in detail["checks"]]}
            validate(change, "change")
            draft = self.store.load_or_new(cid, code, source.version)
            draft["changes"] = [c for c in draft["changes"] if not self.store.same_target(c, change)] + [change]
            sync_reservations(draft, [previous] if previous else [])
            draft["updatedAt"], draft["revision"] = now(), draft["revision"] + 1
            self.store._write(cid, draft)
            return {**result, "change": change, "changeset": draft, "status": status(draft)}

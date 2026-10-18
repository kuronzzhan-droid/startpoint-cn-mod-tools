"""Studio ability draft API; compilation returns bytes to the deliver bridge."""
from __future__ import annotations

import copy

from wf.balance.ownership import owner_index
from wf.balance.rows import TABLES, split_leaf
from wf.rules.catalog import result, with_metadata

from .ability_engine import EditState, apply_operation, describe
from .ability_templates import templates
from .ability_text import apply_text, load_mirrors, split_operations, sync_skill_structure
from .drafts import DraftError, DraftStore, new_change_id, now, sha256, status, validate


def _replay(source, cid, requests, *, server_dir=None, server_text=None, server_rank=None):
    state = EditState(source)
    state.character(cid)
    for request in requests:
        validate(request, "abilityRequest")
        operations = request.get("operations", [])
        # Text operations still check their key, owner, tier and row assertions.
        for op in operations:
            if op.get("character", cid) != cid:
                raise ValueError("operation character must match the draft character")
        numeric, action = split_operations(operations)
        text_ops = [op for op in operations if op["op"] == "set_cells" and op["table"] == "action_skill"
                    and any(str(c["column"]) in {"0", "1", "c0", "c1"} for c in op["cells"])]
        from wf.balance.ownership import check_owner
        for op in text_ops:
            check_owner({**op, "character": cid}, owner_index(state))
            if state.character(cid)[8] != op["key"]:
                raise ValueError("action_skill key does not match current character")
        structural_owners = set()
        for op in numeric:
            apply_operation(state, cid, op)
            if op["table"] == "action_skill" and op["op"] in {"attach_key", "insert_row", "delete_row", "move_row"}:
                structural_owners.update(owner_index(state)["action_skill"].get(op["key"], set()))
        for op in text_ops:
            if state.character(cid)[8] != op["key"]:
                raise ValueError("文本操作的 action_skill key 与挂接后的当前技能键不同")
        sections = copy.deepcopy(request.get("text", {}))
        if action:
            if "action_skill" in sections:
                raise ValueError("action_skill text must appear in operations or text, not both")
            sections["action_skill"] = action
        if structural_owners:
            load_mirrors(state, server_dir, server_text=server_text, server_rank=server_rank)
            sync_skill_structure(state, structural_owners)
        if sections:
            load_mirrors(state, server_dir, server_text=server_text, server_rank=server_rank)
            explicit_shared = request.get("shared_ok") is True or bool(text_ops) and all(
                op.get("shared_ok") is True for op in text_ops)
            apply_text(state, cid, sections, shared_ok=explicit_shared)
    state.client = {key: value for key, value in state.client.items() if value != state.original[key]}
    if requests and not state.client:
        raise ValueError("词条操作互相抵消或没有实际改动")
    if requests:
        state.checks += [result("ability.old-values", "满足", "全部旧值、行数与完整行断言已在内存执行"),
                         result("ability.instant-fields", "满足", "实际输出词条已执行客户端解析与能力声明位置检查")]
    return state


def _fingerprints(state):
    return {**{key: sha256(raw) for key, raw in state.original.items()},
            **{key: sha256(raw) for key, raw in state.server_original.items()}}


def _guard_inputs(state, changeset):
    actual = _fingerprints(state)
    for change in changeset.get("changes", []):
        if change["kind"] != "ability_edit":
            continue
        for logical, expected in change["params"]["inputSha256"].items():
            if actual.get(logical) != expected:
                raise ValueError(f"词条草稿输入已变化：{logical}；请基于当前视图重新编辑")


def _requests(changeset):
    return [request for change in changeset.get("changes", []) if change["kind"] == "ability_edit"
            for request in change["params"]["requests"]]


def _identity(source, cid, changeset):
    if not changeset or "characterId" not in changeset:
        return
    if changeset["characterId"] != cid:
        raise ValueError("草稿 characterId 与请求角色不一致")
    if changeset["baseView"] != source.version:
        raise ValueError(f"草稿 baseView {changeset['baseView']} 与当前视图 {source.version} 不一致")
    if changeset["code"] != EditState(source).character(cid)[0]:
        raise ValueError("草稿 code 与当前角色代码名不一致")
    for change in changeset["changes"]:
        if change["kind"] == "ability_edit" and change["target"]["character"] != cid:
            raise ValueError("词条改动 target 与草稿角色不一致")


def compile_ability_operations(source, store, changeset, server_dir=None):
    """Compile asserted draft requests; returns no filesystem paths or writes."""
    validate(changeset)
    _identity(source, changeset["characterId"], changeset)
    requests = _requests(changeset)
    if not requests:
        return {"client": {}, "servers": {}, "before": {}, "server_before": {}, "changes": [], "checks": []}
    state = _replay(source, changeset["characterId"], requests, server_dir=server_dir)
    _guard_inputs(state, changeset)
    return {"client": state.client, "servers": state.servers,
            "before": {key: sha256(state.original[key]) for key in state.client},
            "server_before": {key: sha256(raw) for key, raw in state.server_original.items()},
            "changes": state.changes, "checks": state.checks}


class AbilityEditor:
    def __init__(self, source, *, store=None, server_dir=None, server_text=None, server_rank=None):
        self.source = source
        self.store = store or DraftStore()
        self.inputs = dict(server_dir=server_dir, server_text=server_text, server_rank=server_rank)

    def _state(self, cid, extra=None):
        draft = self.store.load(cid) or {"changes": []}
        _identity(self.source, cid, draft)
        requests = _requests(draft)
        state = _replay(self.source, cid, requests + ([extra] if extra is not None else []), **self.inputs)
        _guard_inputs(state, draft)
        return state, requests

    def read(self, cid):
        try:
            state, _ = self._state(cid)
            character = state.character(cid)
            owners = owner_index(state)
            groups = [("ability", key, slot) for slot, key in enumerate(character[19:25], 1) if key]
            groups += [("leader_ability", character[17], 0), ("action_skill", character[8], 0)]
            entries = []
            for table, key, slot in groups:
                if not key:
                    continue
                node = state.table(TABLES[table]).get(key)
                if node is None:
                    continue
                levels = node if table == "action_skill" else {None: node}
                for level, leaf in levels.items():
                    rows = split_leaf(leaf, table)
                    entries.append({"table": table, "key": key, "slot": slot, "level": level,
                                    "rows": rows, "owners": sorted(owners[table].get(key, set())),
                                    "descriptions": [describe(row, table) for row in rows]})
            return {"characterId": cid, "entries": entries,
                    "checks": with_metadata(state.checks, "balance"), "runtime": "未执行"}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def apply(self, cid, request):
        try:
            validate(request, "abilityRequest")
            # Serialize read/replay/write so concurrent HTTP edits cannot lose a request.
            with self.store._lock:
                state, previous = self._state(cid, request)
                change = {"id": new_change_id(), "kind": "ability_edit", "title": "词条编辑",
                          "createdAt": now(), "target": {"character": cid},
                          "params": {"requests": previous + [copy.deepcopy(request)], "inputSha256": _fingerprints(state)},
                          "files": [], "pending": [],
                          "checks": [{"level": "warn" if check["status"] in {"待验证", "问题"} else "info",
                                      "code": check["rule"], "message": check["message"]} for check in state.checks]}
                draft = self.store.put_change(cid, state.character(cid)[0], self.source.version, change)
            return {"change": change, "changeset": draft, "status": status(draft),
                    "checks": with_metadata(state.checks, "balance"), "runtime": "未执行"}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def preview(self, cid, request):
        try:
            state, _ = self._state(cid, request)
            return {"characterId": cid, "changes": state.changes,
                    "checks": with_metadata(state.checks, "balance"), "runtime": "未执行"}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            return {"characterId": cid, "changes": [], "checks": with_metadata([
                result("ability.old-values", "问题", str(exc), blocking=True)], "balance"), "runtime": "未执行"}

    def row_preview(self, cid, table, key, row=0, level=None):
        try:
            if table not in TABLES or table == "custom_ability_string":
                raise ValueError("unsupported ability table")
            state, _ = self._state(cid)
            owners = sorted(owner_index(state)[table].get(key, set()))
            if cid not in owners:
                raise ValueError(f"{table}/{key}: character {cid} is not an owner; owners={owners}")
            original = EditState(self.source).table(TABLES[table]).get(key)
            current = state.table(TABLES[table])[key]
            if table == "action_skill":
                original = original.get(level) if original else None
                current = current.get(level)
            before_rows = split_leaf(original, table) if original else []
            after_rows = split_leaf(current, table) if current else []
            if row < 0 or row >= max(len(before_rows), len(after_rows)):
                raise ValueError("row index out of range")
            before = before_rows[row] if row < len(before_rows) else None
            after = after_rows[row] if row < len(after_rows) else None
            return {"characterId": cid, "table": table, "key": key, "row": row, "level": level,
                    "before": {"cells": before, "description": describe(before, table)},
                    "after": {"cells": after, "description": describe(after, table)}, "owners": owners,
                    "checks": with_metadata(state.checks, "balance"), "runtime": "未执行"}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def templates(self, table="ability", block="instant_content", kind=None):
        try:
            return templates(self.source, table, block, kind)
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

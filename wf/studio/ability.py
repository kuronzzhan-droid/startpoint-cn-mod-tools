"""Studio ability draft API; compilation returns bytes to the deliver bridge."""
from __future__ import annotations

import copy
import threading
from pathlib import Path

from wf.balance.rows import TABLES, split_leaf
from wf.rules.catalog import result, with_metadata

from . import perf
from .ability_engine import EditState, apply_operation, describe, owner_index
from .ability_templates import templates
from .ability_text import apply_text, load_mirrors, split_operations, sync_skill_structure
from .drafts import DraftError, DraftStore, new_change_id, now, sha256, status, validate


def _replay(source, cid, requests, *, server_dir=None, server_text=None, server_rank=None):
    state = EditState(source)
    state.character(cid)
    _replay_into(state, cid, requests, dict(server_dir=server_dir, server_text=server_text, server_rank=server_rank))
    return _finish(state, requests)


def _replay_into(state, cid, requests, inputs):
    """Apply asserted requests in order onto ``state`` (no final filtering; see :func:`_finish`)."""
    server_dir, server_text, server_rank = inputs["server_dir"], inputs["server_text"], inputs["server_rank"]
    for request in requests:
        validate(request, "abilityRequest")
        operations = request.get("operations", [])
        # Text operations still check their key, owner, tier and row assertions.
        for op in operations:
            if op.get("character", cid) != cid:
                raise ValueError("operation character must match the draft character")
        tier_keys = {op["key"] for op in operations if op["table"] == "action_skill"
                     and op["op"] in {"insert_row", "delete_row", "move_row"}}
        if any(op["table"] == "action_skill" and op["op"] == "set_cells" and op["key"] in tier_keys
               for op in operations):
            raise ValueError("技能档位插入/删除/移动必须单独写入：同一次请求里不能再改该技能的格子（档号会错位）")
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


def _finish(state, requests):
    state.client = {key: value for key, value in state.client.items() if value != state.original[key]}
    state.servers = {key: value for key, value in state.servers.items() if value != state.server_original[key]}
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
            "server_before": {key: sha256(state.server_original[key]) for key in state.servers},
            "changes": state.changes, "checks": state.checks}


_DESCRIBED = perf._LRU(40000)


def _describe_leaf(table, leaf):
    """(row count, descriptions) of one key's first leaf; memoized by the leaf text."""
    hit = _DESCRIBED.get((table, leaf))
    if hit is None:
        rows = split_leaf(leaf, table)
        hit = _DESCRIBED.put((table, leaf), (len(rows), tuple(describe(row, table) or "" for row in rows)))
    return hit


class AbilityEditor:
    """Draft ability API.

    With a :class:`~wf.studio.source.StudioSource` (or ``cache=True``) the replayed state of the
    saved draft, the panel text, the read result and the key-search index are memoized per
    draft revision (createdAt / revision / updatedAt), view version and mirror signature;
    previews and writes clone that state and replay only the new request.
    """

    def __init__(self, source, *, store=None, server_dir=None, server_text=None, server_rank=None, cache=None):
        self.source = source
        self.store = store or DraftStore()
        self.inputs = dict(server_dir=server_dir, server_text=server_text, server_rank=server_rank)
        self.caching = hasattr(source, "raw_with_origin") if cache is None else bool(cache)
        self._memo: dict = {}
        self._order: list = []
        self._lock = threading.Lock()
        self._inflight: dict = {}

    # -- memo -------------------------------------------------------------
    def _mirror_signature(self):
        paths = (self.inputs["server_text"], self.inputs["server_rank"])
        if self.inputs["server_dir"] is not None:
            from wf.text.model import SERVER_TARGETS
            paths = tuple(Path(self.inputs["server_dir"]) / target for target in SERVER_TARGETS)
        signature = []
        for path in paths:
            try:
                stat = Path(path).stat() if path is not None else None
            except OSError:
                stat = None
            signature.append((str(path), stat.st_mtime_ns, stat.st_size) if stat else (str(path), None, None))
        return tuple(signature)

    def _draft_key(self, cid, draft):
        return (cid, self.source.version, draft.get("createdAt"), draft.get("revision"), draft.get("updatedAt"),
                self._mirror_signature())

    def _once(self, key, build):
        """Memoized ``build()``; concurrent callers of one key share a single computation."""
        if not self.caching:
            return build()
        with self._lock:
            if key in self._memo:
                return self._memo[key]
            gate = self._inflight.get(key)
            owner = gate is None
            if owner:
                gate = self._inflight[key] = threading.Lock()
                gate.acquire()
        if not owner:
            with gate:
                pass
            return self._once(key, build)  # done (cached) or the owner failed: compute and report here
        try:
            value = build()
            with self._lock:
                self._memo[key] = value
                self._order.append(key)
                while len(self._order) > 48:
                    self._memo.pop(self._order.pop(0), None)
            return value
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            gate.release()

    def _base(self, cid):
        """(replayed state of the saved draft requests, draft, requests, key); unfinished, never mutated."""
        draft = self.store.load(cid) or {"changes": []}
        _identity(self.source, cid, draft)
        requests = _requests(draft)
        key = self._draft_key(cid, draft)

        def build():
            state = EditState(self.source)
            state.character(cid)
            _replay_into(state, cid, requests, self.inputs)
            _guard_inputs(state, draft)
            return state
        return self._once(("base",) + key, build), draft, requests, key

    def _state(self, cid, extra=None):
        base, draft, requests, _ = self._base(cid)
        state = base.clone()
        if extra is not None:
            _replay_into(state, cid, [extra], self.inputs)
            _guard_inputs(state, draft)
        _finish(state, requests + ([extra] if extra is not None else []))
        return state, requests

    def read(self, cid):
        try:
            _, _, _, key = self._base(cid)
            return self._once(("read",) + key, lambda: self._read(cid))
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def _read(self, cid):
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
            # wf text asserts the leader name against character_text c10 (character c18 is synced from it).
            from wf.text.model import CHARACTER_TEXT, cells
            try:
                text_leaf = state.table(CHARACTER_TEXT).get(cid)
            except (KeyError, FileNotFoundError):
                text_leaf = None
            text_row = cells(text_leaf) if isinstance(text_leaf, str) else []
            slots = {"ability": list(character[19:25]), "leader_ability": character[17],
                     "action_skill": character[8], "leaderName": character[18],
                     "leaderNameText": text_row[10] if len(text_row) > 10 else None}
            return {"characterId": cid, "entries": entries, "slots": slots,
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

    def _document(self, cid, key):
        """(state with mirrors, wf text workspace, document) of the draft; memoized per draft key."""
        from .ability_text import load_mirrors, workspace_for

        def build():
            state, _ = self._state(cid)
            load_mirrors(state, **self.inputs)
            workspace = workspace_for(state)
            return state, workspace, workspace.read(cid)
        return self._once(("document",) + key, build)

    def _base_document(self, cid):
        """The same document for the unmodified view (「改动前」); memoized per view."""
        from .ability_text import load_mirrors, workspace_for

        def build():
            base = EditState(self.source)
            load_mirrors(base, **self.inputs)
            return workspace_for(base).read(cid)
        return self._once(("base-document", cid, self.source.version, self._mirror_signature()), build)

    def _owners(self, cid, key, state, workspace, document):
        from .text_panel import custom_owners

        def build():
            owners = custom_owners(workspace, [*document["desc_override"], *document["custom_ability_string"]])
            owners[document["skill_key"]] = sorted(
                owner_index(state)["action_skill"].get(document["skill_key"], set()))
            return owners
        return self._once(("owners",) + key, build)

    def text_panel(self, cid, text=None, *, light=False):
        """Panel text of the current draft state (optionally with proposed values); never writes.

        ``light`` skips the original-view document and owner scan (used for live lint): with the
        draft document memoized, a lint is only the projection plus the wf text rules.
        """
        from .text_panel import panel
        try:
            _, _, _, key = self._base(cid)
            state, workspace, document = self._document(cid, key)
            character = state.character(cid)
            if light:
                return panel(document, owners={}, base_document=None, character=character, text=text)

            def build():
                return panel(document, owners=self._owners(cid, key, state, workspace, document),
                             base_document=self._base_document(cid), character=character, text=text)
            return build() if text else self._once(("panel",) + key, build)
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def _key_index(self, table, cid):
        """Every key of ``table`` in the draft state: owners, row count, descriptions (memoized)."""
        if cid:
            _, _, _, draft_key = self._base(cid)
            key = ("keys", table) + draft_key
        else:
            key = ("keys", table, None, self.source.version)

        def build():
            state = self._state(cid)[0] if cid else EditState(self.source)
            owners = owner_index(state)[table]
            index = []
            for name, node in state.table(TABLES[table]).items():
                leaf = node.get("1") if isinstance(node, dict) else node
                if not isinstance(leaf, str) or not leaf:
                    continue
                rows, descriptions = _describe_leaf(table, leaf)
                index.append({"key": name, "rows": rows,
                              "levels": sorted(node, key=int) if isinstance(node, dict) else None,
                              "owners": sorted(owners.get(name, set())), "descriptions": descriptions,
                              "lower": tuple(d.lower() for d in descriptions)})
            return index
        return self._once(key, build)

    def key_search(self, table, query="", cid=None, limit=40, names=None):
        """Existing keys of a table with all owners; draft-created keys included for ``cid``.

        Ranking: exact key > key prefix > key contains > owner (ID / name) > description; every
        term must match somewhere. ``matches`` tells the UI which descriptions to highlight.
        """
        try:
            if table not in {"ability", "leader_ability", "action_skill"}:
                raise ValueError("unsupported ability table")
            names = names or {}
            text = str(query or "").strip().lower()
            terms = [t for t in text.split() if t]
            ranked = []
            for entry in self._key_index(table, cid):
                key = entry["key"].lower()
                owner_names = [names.get(o, "").lower() for o in entry["owners"]]
                score, hit_rows, ok = 0, set(), True
                for term in terms:
                    best = 1000 if key == term else 400 if key.startswith(term) else 200 if term in key else 0
                    if term in entry["owners"]:
                        best = max(best, 150)
                    if any(term in n for n in owner_names if n):
                        best = max(best, 120)
                    rows = [i for i, d in enumerate(entry["lower"]) if term in d]
                    if rows:
                        best = max(best, 10 + min(len(rows), 5))
                        hit_rows.update(rows)
                    if not best:
                        ok = False
                        break
                    score += best
                if ok:
                    ranked.append((-score, entry["key"], entry, sorted(hit_rows)))
            ranked.sort(key=lambda item: (item[0], len(item[1]), item[1]))
            results = []
            for _, _, entry, rows in ranked[:limit]:
                shown = (rows + [i for i in range(len(entry["descriptions"])) if i not in rows])[:4]
                results.append({"key": entry["key"], "rows": entry["rows"], "levels": entry["levels"],
                                "owners": [{"id": o, "name": names.get(o, "")} for o in entry["owners"]],
                                "descriptions": [entry["descriptions"][i] for i in shown],
                                "descriptionRows": shown, "matches": [i for i in shown if i in rows]})
            exact = next((entry["key"] for _, _, entry, _ in ranked if entry["key"].lower() == text), None)
            return {"table": table, "total": len(ranked), "results": results, "terms": terms, "exact": exact}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def templates(self, table="ability", block="instant_content", kind=None):
        try:
            return templates(self.source, table, block, kind)
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

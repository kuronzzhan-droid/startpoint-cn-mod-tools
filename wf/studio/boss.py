"""Boss drafts share the existing delivery bridge in a separate namespace."""
from __future__ import annotations

import copy

from wf.boss.edit_state import BossEditState, digest
from wf.boss.parameters import edit_parameters
from wf.boss.template import create_shared, REWARD_FILES
from wf.rules.catalog import result
import wf_quest_lib as codec

from .drafts import DraftError, new_change_id, now, status, validate
from .boss_store import BossDraftStore
from wf.boss.identity import safe_id


class BossRulesRejected(ValueError):
    """Blocking rule results; preview still shows every five-state result."""

    def __init__(self, message, checks, allocation=None):
        super().__init__(message)
        self.checks, self.allocation = checks, allocation


def _identity(draft, quest, version):
    if draft and (draft.get("subjectKind") != "boss" or draft["characterId"] != quest
                  or draft["code"] != f"boss_{safe_id(quest)}" or draft["baseView"] != version):
        raise ValueError("boss draft identity or source version mismatch")
    if draft and any(change["kind"] != "boss" or change["target"]["quest"] != quest
                     for change in draft["changes"]):
        raise ValueError("boss draft has a mixed or foreign target")


def _requests(draft):
    changes = (draft or {}).get("changes", [])
    if len(changes) > 1:
        raise ValueError("boss draft must contain one replayable operation sequence")
    return copy.deepcopy(changes[0]["params"]["requests"]) if changes else []


def _context(state, created, document, baseline, requests, acknowledgment=False):
    from wf.boss.atlas import encounter_budget
    new_ids, existing_ids = {}, {}
    def paths(node, prefix=()):
        if isinstance(node, dict):
            for key, value in node.items():
                yield "/".join((*prefix, key))
                yield from paths(value, (*prefix, key))
    for change in state.changes:
        if change.get("resource"):
            continue
        if change["old"] is None:
            logical = change["table"]
            new_ids.setdefault(logical, []).append("/".join(change["path"]))
            existing_ids[logical] = list(paths(codec.parse_node(state.original[logical]))) if logical in state.original else []
    supplied = next((req["atlasBudget"] for req in reversed(requests) if "atlasBudget" in req), None)
    return {"custom_content": created, "new_ids": new_ids, "existing_ids": existing_ids,
            "acknowledgePreload": acknowledgment,
            "atlas_budget": encounter_budget(state, document,
                source_quest=baseline.get("quest", {}).get("id"), supplied=supplied)}


def _replay(source, quest, requests, *, server_dir=None, reserved=()):
    from wf.boss.reader import BossReader
    from wf.rules.boss import check_boss
    from .source import StudioSource
    state = BossEditState(source, server_dir=server_dir)
    affected, created, allocation = [], False, None
    preload_approvals = {}
    for index, request in enumerate(requests):
        validate(request, "bossRequest")
        if request["operation"] == "create_shared":
            if index or quest not in ("new", str(int(request.get("ids", {}).get("event", "0")) * 1000 + 1)):
                raise ValueError("create_shared must be the first operation in a new boss draft")
            allocation = create_shared(state, request, reserved=reserved)
            quest, touched, created = allocation["quest"], [allocation["quest"]], True
            request["ids"] = {key: allocation[key] for key in ("event", "node")}
        elif request["operation"] == "edit":
            touched = edit_parameters(state, quest, request)
        else:
            from .boss_dispatch import apply_operation
            touched = apply_operation(state, quest, request, reserved=reserved)
        affected.extend(touched)
        for identifier in touched:
            current = BossReader(StudioSource(state)).show(identifier)
            # Confirmations belong to the same element and enemy resource rows.
            # HP/BGM edits preserve that scope; changed attributes/tiers do not.
            scope = (current["quest"]["fields"].get("recommended_element"),
                     [(e.get("table"), e.get("code"), e.get("path"), e.get("row"))
                      for e in current.get("enemies", [])])
            key = current["quest"]["selector"]
            previous_scope, approved = preload_approvals.get(key, (None, False))
            if scope != previous_scope:
                approved = False
            if "acknowledgePreload" in request:
                approved = request["acknowledgePreload"] is True
            preload_approvals[key] = (scope, approved)
    if not requests:
        return state, quest, [], None
    # Reward checks use all four server baselines, and the actual candidate tables.
    if server_dir is not None:
        for target in (*REWARD_FILES, "assets/boss_coin_shop.json", "assets/boss_coin_shop_item_category_map.json"):
            state.server(target, required=False)
    candidate = BossReader(StudioSource(state))
    before = BossReader(source)
    checks = []
    for identifier in dict.fromkeys(affected):
        document = candidate.show(identifier)
        baseline = before.show(requests[0].get("sourceQuest", "hard_multi:1006/1")) if created else before.show(identifier)
        results = check_boss(document, view=state, baseline=baseline,
                             server_changes=state.servers, server_before=state.server_original,
                             context=_context(state, created, document, baseline, requests,
                                              preload_approvals[document["quest"]["selector"]][1]))
        if any(req["operation"].startswith(("terrain_", "behavior_")) for req in requests):
            from wf.boss.behavior_guards import check_behavior_positions
            results.append(check_behavior_positions(state, document))
        # Five-tier edits check five quests; each result names the quest it belongs to.
        checks.extend({**entry, "quest": document["quest"]["selector"]} for entry in results)
    blocking = [entry for entry in checks if entry.get("blocking")]
    if blocking:
        raise BossRulesRejected("boss rules rejected the candidate: " + "; ".join(entry["message"] for entry in blocking),
                                checks, allocation)
    return state, quest, checks, allocation


def compile_boss(source, store, draft, *, server_dir=None):
    validate(draft)
    quest = draft["characterId"]
    _identity(draft, quest, source.version)
    requests = _requests(draft)
    reserved = BossEditor(source, store=store, server_dir=server_dir)._reservations(quest)
    state, _, checks, _ = _replay(source, quest, requests, server_dir=server_dir, reserved=reserved)
    state.verify_snapshot(draft["changes"][0]["params"]["inputs"])
    return {"client": state.client, "servers": state.servers,
            "server_before": {key: digest(state.server_original[key]) for key in state.servers},
            "changes": state.changes, "checks": checks}


class BossEditor:
    def __init__(self, source, *, store=None, server_dir=None):
        self.source, self.store, self.server_dir = source, store or BossDraftStore(), server_dir

    def _reservations(self, except_quest):
        quests, nodes = [], []
        products, weapons, enhancement_products = [], [], []
        for entry in self.store.characters():
            identifier = entry["characterId"]
            if identifier == except_quest:
                continue
            for request in _requests(self.store.load(identifier)):
                if request["operation"] == "create_shared":
                    quests.append(identifier)
                    nodes.append(request["ids"]["node"])
                if request["operation"] == "shop_add":
                    products.append(request["shop"]["productId"])
                if request["operation"] == "weapon_clone":
                    weapons.append(request["weapon"]["id"])
                    enhancement_products.extend(request["weapon"].get("enhancementProducts", []))
        return {"quests": quests, "nodes": nodes, "products": products,
                "weapons": weapons, "enhancementProducts": enhancement_products}

    def canonical(self, quest):
        """One identity for every existing quest; newly allocated drafts keep IDs."""
        if quest == "new":
            return quest
        safe_id(quest)
        from wf.boss.reader import BossReader
        reader = BossReader(self.source)
        try:
            selected = reader.find(quest)
        except ValueError:
            identity = quest
            if quest.startswith("hard_multi:"):
                path = quest.split(":", 1)[1].split("/")
                if len(path) == 2:
                    if path[1] != "1":
                        raise
                    identity = str(int(path[0]) * 1000 + 1)
                else:
                    identity = str(int(path[0]))
            elif not quest.isdigit():
                raise
            # An ambiguous or other-kind baseline ID cannot become a new draft.
            if any(item["id"] == identity for item in reader.list()["items"]):
                raise
            draft = self.store.load(identity)
            requests = _requests(draft)
            if requests and requests[0]["operation"] == "create_shared":
                event = requests[0].get("ids", {}).get("event")
                if event is not None and str(int(event) * 1000 + 1) == identity:
                    return identity
            raise
        canonical = selected["selector"]
        # Preserve an old ID-named draft while routing both spellings to it.
        if selected["id"] != canonical and self.store.load(selected["id"]) is not None:
            if self.store.load(canonical) is not None:
                raise DraftError(f"副本 {canonical} 已有两份别名草稿，请先解决重复草稿")
            return selected["id"]
        return canonical

    def _state(self, quest, extra=None):
        quest = self.canonical(quest)
        draft = None if quest == "new" else self.store.load(quest)
        _identity(draft, quest, self.source.version)
        requests = _requests(draft)
        if draft and requests:
            old, _, _, _ = _replay(self.source, quest, copy.deepcopy(requests), server_dir=self.server_dir)
            old.verify_snapshot(draft["changes"][0]["params"]["inputs"])
        if extra is not None:
            requests.append(copy.deepcopy(extra))
        state, identity, checks, allocation = _replay(self.source, quest, requests,
            server_dir=self.server_dir, reserved=self._reservations(quest))
        return state, identity, requests, checks, allocation

    def read(self, quest):
        from wf.boss.reader import BossReader
        from .source import StudioSource
        try:
            state, identity, requests, checks, _ = self._state(quest)
            from .boss_dispatch import draft_weapons
            return {"questId": identity, "boss": BossReader(StudioSource(state)).show(identity),
                    "draftWeapons": draft_weapons(state, requests),
                    "changeset": self.store.load(identity), "checks": checks, "runtime": "未执行"}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def preview(self, quest, request):
        try:
            validate(request, "bossRequest")
            state, identity, _, checks, allocation = self._state(quest, request)
            return {"ok": True, "questId": identity, "allocation": allocation,
                    "changes": state.changes, "serverTargets": sorted(state.servers),
                    "checks": checks, "runtime": "未执行"}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            # The summary stays first; rule rejections also carry every result
            # so the editor can show which rule blocks and what still passes.
            rules = exc.checks if isinstance(exc, BossRulesRejected) else []
            allocation = exc.allocation if isinstance(exc, BossRulesRejected) else None
            return {"ok": False, "questId": quest, "allocation": allocation, "checks": [
                result("boss.inputs", "问题", str(exc), blocking=True), *rules], "runtime": "未执行"}

    def inspect(self, quest, section):
        from wf.boss.reader import BossReader
        from .source import StudioSource
        from .boss_dispatch import inspect_section
        try:
            state, identity, requests, checks, _ = self._state(quest)
            document = BossReader(StudioSource(state)).show(identity)
            return {"questId": identity, "section": section,
                    "data": inspect_section(state, document, section, requests),
                    "checks": checks, "runtime": "未执行"}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def apply(self, quest, request):
        try:
            validate(request, "bossRequest")
            with self.store._lock:
                state, identity, requests, checks, allocation = self._state(quest, request)
                if not state.client:
                    raise ValueError("boss request produces no changes")
                change = {"id": new_change_id(), "kind": "boss", "title": "副本草稿",
                          "createdAt": now(), "target": {"quest": identity},
                          "params": {"requests": requests, "inputs": state.snapshot()},
                          "files": [], "pending": [],
                          "checks": [{"level": "warn" if c["status"] in {"待验证", "问题"} else "info",
                                      "code": c["rule"], "message": c["message"]} for c in checks]}
                draft = self.store.put_change(identity, f"boss_{safe_id(identity)}", self.source.version, change)
            return {"ok": True, "questId": identity, "allocation": allocation,
                    "change": change, "changeset": draft, "status": status(draft), "checks": checks,
                    "runtime": "未执行"}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

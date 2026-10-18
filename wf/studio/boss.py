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


def _context(state, created):
    new_ids, existing_ids = {}, {}
    def paths(node, prefix=()):
        if isinstance(node, dict):
            for key, value in node.items():
                yield "/".join((*prefix, key))
                yield from paths(value, (*prefix, key))
    for change in state.changes:
        if change["old"] is None:
            logical = change["table"]
            new_ids.setdefault(logical, []).append("/".join(change["path"]))
            existing_ids[logical] = list(paths(codec.parse_node(state.original[logical]))) if logical in state.original else []
    return {"custom_content": created, "choice_count": 1, "new_ids": new_ids, "existing_ids": existing_ids}


def _replay(source, quest, requests, *, server_dir=None, reserved=()):
    from wf.boss.reader import BossReader
    from wf.rules.boss import check_boss
    from .source import StudioSource
    state = BossEditState(source, server_dir=server_dir)
    affected, created, allocation = [], False, None
    for index, request in enumerate(requests):
        validate(request, "bossRequest")
        if request["operation"] == "create_shared":
            if index or quest not in ("new", str(int(request.get("ids", {}).get("event", "0")) * 1000 + 1)):
                raise ValueError("create_shared must be the first operation in a new boss draft")
            allocation = create_shared(state, request, reserved=reserved)
            quest, affected, created = allocation["quest"], [allocation["quest"]], True
            request["ids"] = {key: allocation[key] for key in ("event", "node")}
        else:
            affected.extend(edit_parameters(state, quest, request))
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
        checks.extend(check_boss(document, view=state, baseline=baseline,
                                 server_changes=state.servers, server_before=state.server_original,
                                 context=_context(state, created)))
    blocking = [entry for entry in checks if entry.get("blocking")]
    if blocking:
        raise ValueError("boss rules rejected the candidate: " + "; ".join(entry["message"] for entry in blocking))
    return state, quest, checks, allocation


def compile_boss(source, store, draft, *, server_dir=None):
    validate(draft)
    quest = draft["characterId"]
    _identity(draft, quest, source.version)
    requests = _requests(draft)
    state, _, checks, _ = _replay(source, quest, requests, server_dir=server_dir)
    state.verify_snapshot(draft["changes"][0]["params"]["inputs"])
    return {"client": state.client, "servers": state.servers,
            "server_before": {key: digest(state.server_original[key]) for key in state.servers},
            "changes": state.changes, "checks": checks}


class BossEditor:
    def __init__(self, source, *, store=None, server_dir=None):
        self.source, self.store, self.server_dir = source, store or BossDraftStore(), server_dir

    def _reservations(self, except_quest):
        quests, nodes = [], []
        for entry in self.store.characters():
            identifier = entry["characterId"]
            if identifier == except_quest:
                continue
            for request in _requests(self.store.load(identifier)):
                if request["operation"] == "create_shared":
                    quests.append(identifier)
                    nodes.append(request["ids"]["node"])
        return {"quests": quests, "nodes": nodes}

    def _state(self, quest, extra=None):
        if quest != "new":
            safe_id(quest)
        if ":" in quest:
            from wf.boss.reader import BossReader
            quest = BossReader(self.source).find(quest)["selector"]
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
            state, identity, _, checks, _ = self._state(quest)
            return {"questId": identity, "boss": BossReader(StudioSource(state)).show(identity),
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
            return {"ok": False, "questId": quest, "checks": [
                result("boss.inputs", "问题", str(exc), blocking=True)], "runtime": "未执行"}

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

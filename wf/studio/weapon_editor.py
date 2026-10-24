"""Quest-free weapon edits replay the existing weapon graph operations."""
import copy

from wf.boss.edit_state import BossEditState, digest
from wf.boss.weapon_edit import clone_weapon, edit_materials

from .boss_store import BossDraftStore
from .drafts import DraftError, new_change_id, now, status, validate
from .weapon_store import WeaponDraftStore, identity, reservations


def _requests(draft):
    return copy.deepcopy(draft["changes"][0]["params"]["requests"]) if draft and draft["changes"] else []


def _replay(source, wid, requests, *, server_dir, reserved, client_profile=None, provides=None):
    state = BossEditState(source, server_dir=server_dir)
    state.client_profile, state.client_provides = client_profile, provides
    for index, request in enumerate(requests):
        validate(request, "weaponRequest")
        spec = request["weapon"]
        if request["operation"] == "weapon_clone":
            if index or (wid is not None and spec.get("id") != wid):
                raise DraftError("weapon clone must be the first operation for its draft ID")
            clone_weapon(state, spec, reserved)
            wid = spec["id"]
        else:
            if spec["id"] != wid:
                raise DraftError("weapon materials target does not match draft ID")
            edit_materials(state, spec)
    blocking = [entry for entry in getattr(state, "weapon_checks", [])
                if entry.get("blocking") or entry.get("level") == "error"]
    if blocking:
        raise DraftError("weapon rules rejected the candidate: " + "; ".join(entry["message"] for entry in blocking))
    return state, wid


def compile_weapon(source, store, draft, *, server_dir=None, client_profile=None, provides=None):
    wid = draft["characterId"]
    if not isinstance(store, WeaponDraftStore):
        raise DraftError("武器交付必须使用独立 WeaponDraftStore 命名空间")
    identity(draft, wid, source.version)
    editor = WeaponEditor(source, store=store, server_dir=server_dir)
    state, _ = _replay(source, wid, _requests(draft), server_dir=server_dir,
                       reserved=editor.reserved(wid), client_profile=client_profile, provides=provides)
    state.verify_snapshot(draft["changes"][0]["params"]["inputs"])
    return {"client": state.client, "servers": state.servers,
            "server_before": {key: digest(state.server_original[key]) for key in state.servers},
            "changes": state.changes, "checks": getattr(state, "weapon_checks", [])}


class WeaponEditor:
    def __init__(self, source, *, store=None, server_dir=None):
        self.source, self.store, self.server_dir = source, store or WeaponDraftStore(), server_dir

    def reserved(self, wid=None):
        result = reservations(self.store, wid)
        # Boss and standalone editors allocate from the same existing native ranges.
        other = reservations(BossDraftStore(self.store.root.parent / "boss"))
        for key in result:
            result[key].extend(other[key])
        return result

    def state(self, wid):
        draft = self.store.load(wid)
        identity(draft, wid, self.source.version)
        requests = _requests(draft)
        state, _ = _replay(self.source, wid, requests, server_dir=self.server_dir, reserved=self.reserved(wid))
        if requests:
            state.verify_snapshot(draft["changes"][0]["params"]["inputs"])
        return state, draft

    def apply(self, operation, spec, *, wid=None, preview=False):
        try:
            with self.store._lock:
                request = {"operation": operation, "weapon": copy.deepcopy(spec)}
                validate(request, "weaponRequest")
                previous = self.state(wid)[1] if wid is not None else None
                requests = _requests(previous) + [request]
                state, selected = _replay(self.source, wid, requests, server_dir=self.server_dir,
                                           reserved=self.reserved(wid))
                if not state.client:
                    raise DraftError("weapon request produces no changes")
                checks = getattr(state, "weapon_checks", [])
                result = {"ok": True, "weaponId": selected, "subjectKind": "weapon",
                          "allocation": request["weapon"] if operation == "weapon_clone" else None,
                          "changes": state.changes, "serverTargets": sorted(state.servers),
                          "checks": checks, "runtime": "未执行"}
                if preview:
                    return result
                change = {"id": new_change_id(), "kind": "weapon", "title": "武器草稿",
                          "createdAt": now(), "target": {"weapon": selected},
                          "params": {"requests": requests, "inputs": state.snapshot()},
                          "files": [], "pending": [],
                          "checks": [{"level": c.get("level", "warn"), "code": c["rule"], "message": c["message"]}
                                     for c in checks]}
                draft = self.store.put_change(selected, f"weapon_{selected}", self.source.version, change)
                return {**result, "change": change, "changeset": draft, "status": status(draft)}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

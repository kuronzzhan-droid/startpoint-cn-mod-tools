"""Independent weapon draft identities and cross-workshop ID reservations."""
from wf.boss import schema as s
from wf.boss.weapon_ids import validate_weapon_id

from .drafts import DraftStore, DraftError, default_root, validate


def draft_summary(entry, draft, tables):
    """Describe active operations without requiring a successful candidate replay."""
    requests = [request for change in (draft or {}).get("changes", [])
                for request in change["params"].get("requests", [])]
    clone = next((request["weapon"] for request in requests
                  if request.get("operation") == "weapon_clone"), None)
    wid = entry["characterId"]
    name = clone.get("name") if clone is not None else None
    if name is None:
        source = clone["sourceWeapon"] if clone is not None else wid
        rows = s.rows_at(tables.table(s.EQUIPMENT), [source])
        name = s.cell(rows[0][1], 1) if rows else None
    return {**entry, "weaponId": wid, "name": name if s.present(name) else None,
            "isNew": clone is not None}


def identity(draft, wid, version=None):
    try:
        validate_weapon_id(wid)
    except ValueError as exc:
        raise DraftError("武器 ID 无效：" + str(exc)) from exc
    if draft is None:
        return
    validate(draft)
    if (draft.get("subjectKind") != "weapon" or draft["characterId"] != wid
            or draft["code"] != f"weapon_{wid}"
            or (version is not None and draft["baseView"] != version)):
        raise DraftError("weapon draft identity / namespace / source version mismatch")
    if any(c["kind"] != "weapon" or c["target"].get("weapon") != wid for c in draft["changes"]):
        raise DraftError("weapon draft contains a foreign change target")
    if len(draft["changes"]) > 1:
        raise DraftError("weapon draft must contain one replayable operation sequence")


class WeaponDraftStore(DraftStore):
    def __init__(self, root=None):
        super().__init__(root if root is not None else default_root() / "weapons")

    def directory(self, cid):
        identity(None, cid)
        target = super().directory(cid)
        if not target.resolve().is_relative_to(self.root.resolve()):
            raise DraftError("weapon draft directory escapes its namespace")
        return target

    def load(self, cid):
        draft = super().load(cid)
        identity(draft, cid)
        return draft

    def load_or_new(self, cid, code, base_view):
        draft = super().load_or_new(cid, code, base_view)
        draft.setdefault("subjectKind", "weapon")
        identity(draft, cid, base_view)
        return draft

    def _write(self, cid, changeset):
        identity(changeset, cid)
        super()._write(cid, changeset)


def reservations(store, exclude=None):
    """Reserve clone identities and existing material-edit targets across stores."""
    result = {"weapons": [], "enhancementProducts": [], "codes": []}
    for entry in store.characters():
        if entry["characterId"] == exclude:
            continue
        draft = store.load(entry["characterId"])
        for change in draft["changes"]:
            for request in change.get("params", {}).get("requests", []):
                if request.get("operation") == "weapon_clone":
                    spec = request["weapon"]
                    result["weapons"].append(spec["id"])
                    result["enhancementProducts"].extend(spec.get("enhancementProducts", []))
                    code = spec.get("code", "boss_workshop_" + spec["id"])
                    result["codes"].extend([code, code + "_soul" if "code" in spec
                                             else "boss_workshop_soul_" + spec["id"]])
                elif request.get("operation") == "weapon_materials":
                    spec = request["weapon"]
                    result["weapons"].append(spec["id"])
                    result["enhancementProducts"].extend(stage["productId"] for stage in spec["stages"])
    if not result["codes"]:
        result.pop("codes")  # Preserve the legacy empty/material-only reservation shape.
    return result

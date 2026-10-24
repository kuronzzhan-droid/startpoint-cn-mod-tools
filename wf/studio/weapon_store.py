"""Independent weapon draft identities and cross-workshop ID reservations."""
import re

from .drafts import DraftStore, DraftError, default_root, validate


def identity(draft, wid, version=None):
    if not re.fullmatch(r"[1-9][0-9]{0,8}", wid or ""):
        raise DraftError("武器 ID 无效")
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
    """Return clone IDs allocated in this store, including enhancement products."""
    result = {"weapons": [], "enhancementProducts": []}
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
    return result

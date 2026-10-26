"""Boss-only draft storage; kind-qualified selectors never become directory paths."""
from wf.boss.identity import safe_id, from_directory
from .drafts import DraftStore, DraftError, default_root, validate


class BossDraftStore(DraftStore):
    def __init__(self, root=None):
        super().__init__(root if root is not None else default_root() / "boss")

    def directory(self, cid):
        try:
            directory = self.root / safe_id(cid)
        except ValueError as exc:
            raise DraftError(str(exc)) from exc
        if not directory.resolve().is_relative_to(self.root.resolve()):
            raise DraftError("boss draft directory escapes its namespace")
        return directory

    def load(self, cid):
        try:
            draft = super().load(cid)
        except (ValueError, OSError, TypeError) as exc:
            raise DraftError(f"无法读取副本草稿：{exc}") from exc
        if draft is not None:
            validate(draft)
            if (draft.get("subjectKind") != "boss" or draft.get("characterId") != cid
                    or draft.get("code") != f"boss_{safe_id(cid)}"):
                raise DraftError("boss draft identity / namespace mismatch")
            if any(change["kind"] != "boss" or change["target"]["quest"] != cid for change in draft["changes"]):
                raise DraftError("boss draft contains a foreign change target")
        return draft

    def load_or_new(self, cid, code, base_view):
        if code != f"boss_{safe_id(cid)}":
            raise DraftError("boss draft code / identity mismatch")
        draft = super().load_or_new(cid, code, base_view)
        if draft.get("subjectKind", "boss") != "boss":
            raise DraftError("boss and character draft namespaces cannot be mixed")
        draft["subjectKind"] = "boss"
        return draft

    def _write(self, cid, changeset):
        if (changeset.get("subjectKind") != "boss" or changeset.get("characterId") != cid
                or changeset.get("code") != f"boss_{safe_id(cid)}"
                or any(c.get("kind") != "boss" or c.get("target", {}).get("quest") != cid
                       for c in changeset.get("changes", []))):
            raise DraftError("boss draft identity / namespace mismatch")
        super()._write(cid, changeset)

    def characters(self):
        result = []
        for folder in sorted(self.root.iterdir()) if self.root.is_dir() else []:
            if not folder.is_dir():
                continue
            try:
                cid = from_directory(folder.name)
            except ValueError:
                continue
            draft = self.load(cid)
            if draft:
                result.append({"characterId": cid, "code": draft["code"], "changes": len(draft["changes"]),
                               "updatedAt": draft["updatedAt"], "savedAt": draft["savedAt"]})
        return result

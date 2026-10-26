"""Read-only inputs and deterministic fingerprints for skill templates."""
from __future__ import annotations

from pathlib import Path
import wf_mod_tool as core

from wf.balance.rows import TABLES
from wf.studio.deliver_media import read_root
from wf.studio.drafts import DraftError, sha256

CHARACTER = "master/character/character.orderedmap"
ACTION = TABLES["action_skill"]


class Inputs:
    def __init__(self, current, official):
        self.current, self.official = current, official
        self.hashes = {}

    def read(self, logical, *, official=False, root="common"):
        if official:
            source = self.official
            if hasattr(source, "read_official_root"):
                raw = source.read_official_root(root, logical)
            elif hasattr(source, "_official"):
                baseline = source._official()
                digest = core.sha1_path(logical)
                # An absent optional root is not evidence from the current view.
                raw = (baseline.get(root, digest[:2] + "/" + digest[2:])
                       if baseline is not None and baseline.archives(root) else None)
            elif root == "common":
                raw = source.raw(logical, official=True)
            else:
                raw = None
        else:
            raw = read_root(self.current, root, logical)
        token = f"{'official' if official else 'current'}:{root}:{logical}"
        self.hashes[token] = sha256(raw) if raw is not None else None
        return raw

    def require(self, logical, *, official=False):
        raw = self.read(logical, official=official)
        if raw is None:
            raise DraftError(f"技能模板缺少{'官方' if official else '当前'}输入：{logical}")
        return raw

    def verify(self, expected):
        for token, digest in expected.items():
            scope, root, logical = token.split(":", 2)
            if scope not in {"official", "current"}:
                raise DraftError("技能模板输入快照来源无效")
            self.read(logical, official=scope == "official", root=root)
            if self.hashes[token] != digest:
                raise DraftError(f"技能模板输入已变化：{scope}/{root}/{logical}；请重新预览保存")


class OfficialEffects:
    """Expose exact official roots without a current-view fallback."""
    def __init__(self, inputs):
        self.inputs = inputs

    def read_root(self, root, logical):
        return self.inputs.read(logical, official=True, root=root)

    def raw(self, logical):
        return self.read_root("common", logical)


def current_source(source, store, draft, *, server_dir=None):
    """Apply already-authorized clone/ability edits before the skill template."""
    from .character_clone import clone_change, clone_members, overlay_source
    members = {}
    if draft and clone_change(draft):
        members.update(clone_members(source, store, draft))
    if draft and any(c["kind"] == "ability_edit" for c in draft["changes"]):
        if members:
            raise DraftError("克隆角色的 ability_edit 交付尚未支持")
        from .ability import compile_ability_operations
        edited = compile_ability_operations(source, store, draft, server_dir=server_dir)
        members.update({("common", key): raw for key, raw in edited["client"].items()})
    return overlay_source(source, members) if members else source


def vacant(source, store, cid, key, previous=None, *, server_dir=None):
    from .ids import check_id
    draft = store.load(cid)
    if draft:
        declared = list(draft.get("reservations", {}).get("action_skill", []))
        for change in draft["changes"]:
            if previous and change["id"] == previous["id"]:
                continue
            declared.extend(change.get("params", {}).get("reservations", {}).get("action_skill", []))
        if key in declared:
            raise DraftError(f"action_skill 键已被本草稿其他改动预留：{key}")
    found = check_id(source, "action_skill", key, drafts_root=store.root, server_dir=server_dir)
    old = previous.get("params", {}).get("request", {}).get("newKey") if previous else None
    own = str((store.directory(cid) / "changeset.json").resolve())
    owners = [entry for entry in found["owners"] if not
              (old == key and entry["source"] == "draft" and entry["owner"] == cid
               and str(Path(entry["location"]).resolve()) == own)]
    if owners:
        raise DraftError(f"action_skill 键已占用或预留：{key}")

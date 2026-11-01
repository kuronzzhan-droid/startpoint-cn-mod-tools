"""Linked clone identity checks, including draft-only keys and program paths."""
from .drafts import DraftError
from .ids import canonical, collect_occupancy, check_id
from .id_catalog import load_json
from .clone_tables import T


def draft_keys(store):
    keys, paths = set(), set()
    for path in store.root.rglob("changeset.json"):
        if not path.resolve().is_relative_to(store.root.resolve()):
            raise DraftError("草稿来源越界")
        for change in load_json(path).get("changes", []):
            params = change.get("params", {})
            for logical, owned in params.get("ownedRows", {}).items():
                keys.update((logical, key) for key in owned)
            for req in params.get("requests", []):
                for op in req.get("operations", []):
                    if op.get("op") == "attach_key":
                        logical = {"ability": T.ABILITY, "leader_ability": T.LEADER,
                                   "action_skill": T.ACTION}.get(op.get("table"))
                        if logical:
                            keys.add((logical, op["key"]))
            paths.update(item["logical"] for item in change.get("files", []))
    return keys, paths


def linked_check(ops, cid, *, code=None, server_dir=None, occupancy=None, reserved=None):
    canonical("character", cid)
    canonical("mana_node", cid)
    occupancy = occupancy if occupancy is not None else collect_occupancy(ops.source, ops.store.root, server_dir)
    keys, _ = reserved if reserved is not None else draft_keys(ops.store)
    reasons = []
    for kind in ("character", "mana_node"):
        if not check_id(ops.source, kind, cid, occupancy=occupancy)["available"]:
            reasons.append(f"{kind}/{cid} 已占用")
    if ops.store.directory(cid).exists():
        reasons.append("目标草稿目录已存在")
    wanted = [(T.LEADER, cid), *((T.ABILITY, cid + str(i)) for i in range(1, 7))]
    if code:
        wanted.append((T.ACTION, code))
        if not check_id(ops.source, "action_skill", code, occupancy=occupancy)["available"]:
            reasons.append(f"action_skill/{code} 已占用")
    for logical, key in wanted:
        if (logical, key) in keys or key in ops.source.table(logical):
            label = {T.ABILITY: "能力键", T.LEADER: "队长技键", T.ACTION: "技能键"}[logical]
            reasons.append(f"{label}已占用或被草稿预留：{logical}/{key}")
    return {"id": cid, "available": not reasons, "reasons": reasons, "serverChecked": server_dir is not None}


def next_linked(ops, near=None, *, donor, server_dir=None):
    cid = canonical("mana_node", near or "199000")
    occupancy = collect_occupancy(ops.source, ops.store.root, server_dir)
    reserved = draft_keys(ops.store)
    while True:
        result = linked_check(ops, cid, code=f"variant_{donor}_{cid}", server_dir=server_dir,
                              occupancy=occupancy, reserved=reserved)
        if result["available"]:
            return result
        cid = canonical("mana_node", str(int(cid) + 1))

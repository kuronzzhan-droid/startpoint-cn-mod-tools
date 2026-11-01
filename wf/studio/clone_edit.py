"""Replay clone text/ability edits over clone bytes, with read-only server inputs."""
from wf.balance.rows import split_leaf
from .drafts import DraftError


def edit_source(source, store, draft):
    from .character_clone import clone_change, clone_members, overlay_source
    if not clone_change(draft) or getattr(source, "_clone_text_cid", None) == draft["characterId"]:
        return source
    effective = overlay_source(source, clone_members(source, store, draft))
    effective._clone_text_cid = draft["characterId"]
    return effective


def seed_text_mirror(state):
    """Only the new clone's primary mirror row is projected; originals retain real hashes."""
    from wf.text.model import CHARACTER_TEXT, SERVER_TARGETS
    from wf.boss.edit_state import merge_keys
    from wf.text.json_patch import parse_mirror
    cid = state.clone_text_cid
    target = SERVER_TARGETS[0]
    if cid in parse_mirror(state.server_original[target]):
        raise DraftError("克隆角色已进入服务端文本镜像，请重新建立已有角色草稿")
    rows = split_leaf(state.table(CHARACTER_TEXT)[cid], "text")
    state.servers[target] = merge_keys(state.servers[target], {cid: rows})


def pending_text(variant, final, code):
    """Resolve only explicit text follow-ups from current compiled bytes; unknown rules remain blocking."""
    pending = []
    for item in (variant or {}).get("requirements", (variant or {}).get("manual", [])):
        if "textKey" in item:
            rows = final.table("strings").get(item["textKey"], [])
            if rows and rows[0] and rows[0][0].strip():
                continue
        elif "skillText" in item:
            rows = final.table("skill").get(code, {}).get(item["key"], [])
            if rows and len(rows[0]) > 1 and rows[0][1].strip() and rows[0][1] != item["skillText"]:
                continue
        pending.append(item)
    return pending


def refreshed_clone(source, store, draft, client):
    from copy import deepcopy
    from .character_clone import clone_change, overlay_source
    original = clone_change(draft)
    if not original or not original["params"].get("variant"):
        return None
    change = deepcopy(original)
    variant = change["params"]["variant"]
    variant.setdefault("requirements", deepcopy(variant["manual"]))
    final = overlay_source(edit_source(source, store, draft), {("common", k): v for k, v in client.items()})
    variant["manual"] = pending_text(variant, final, draft["code"])
    change["checks"] = [c for c in change["checks"] if c["code"] not in {"variant.manual", "variant.incomplete"}]
    if variant["manual"]:
        change["checks"].append({"level": "error", "code": "variant.incomplete",
                                 "message": "变体仍有需人工条目：" + "；".join(i["reason"] for i in variant["manual"])})
    return change

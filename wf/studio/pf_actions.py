"""PF workshop operations shared by HTTP, CLI and summon-workshop discovery."""
from __future__ import annotations

import copy

from .drafts import DraftError, new_change_id, now, sha256, status, validate
from .pf_catalog import PfCatalog, PF_TABLE
from .pf_compile import prepare, table_bytes, vacant


def listing(source, query="", **options):
    return PfCatalog(source, **options).list(query or "")


def detail(source, key, **options):
    catalog = PfCatalog(source, **options)
    return catalog.detail(key) if key in catalog.keys else None


def draft_keys(store, cid):
    """Discover references only; callers must compile this draft when using them."""
    try:
        draft = store.load(cid)
        if draft is not None:
            validate(draft)
    except DraftError:
        raise
    except (ValueError, OSError, TypeError) as exc:
        raise DraftError("PF 草稿读取失败：" + str(exc)) from exc
    return {"characterId": cid, "items": [
        {"key": c["params"]["spec"]["key"], "source": c["params"]["spec"]["source"],
         "element": c["params"]["spec"]["element"], "changeId": c["id"],
         "reference": c["params"]["spec"]["key"], "state": "draft"}
        for c in (draft or {}).get("changes", []) if c["kind"] == "pf_action_clone"]}


def clone(ops, cid, request, *, preview=False, **options):
    validate(request, "pfActionCloneRequest")
    spec = copy.deepcopy(request)
    preview = preview or spec.pop("dryRun", False)
    # pop even when the explicit preview flag short-circuits the expression.
    spec.pop("dryRun", None)
    try:
        with ops.store._lock:
            existing = ops.store.load(cid)
            if existing and existing["baseView"] != ops.source.version:
                raise DraftError("PF 草稿基线版本与当前视图不一致")
            if existing and (existing.get("subjectKind", "character") != "character" or "scratch" in existing):
                raise DraftError("PF 动作需要正式角色草稿")
            # Existing formal character-clone drafts expose their identity via DraftOps.
            character = ops.character(cid)
            result = prepare(ops.source, spec, **options)
            vacant(ops.source, ops.store, result["catalog"], spec["key"])
            members = {**result["members"], ("common", PF_TABLE): table_bytes(
                ops.source, [(spec["key"], result["paths"])])}
            response = {k: v for k, v in result.items() if k not in {"catalog", "members", "inputs", "paths"}}
            response.update(ok=True, preview=bool(preview), characterId=cid, buildable=True, runtime="未执行",
                            tables=[{"logical": PF_TABLE, "addedKeys": [spec["key"]]}],
                            files=[{"root": root, "logical": logical, "size": len(raw), "sha256": sha256(raw)}
                                   for (root, logical), raw in sorted(members.items())])
            if preview:
                return response
            change = {"id": new_change_id(), "kind": "pf_action_clone", "title": "克隆强化弹射 " + spec["key"],
                      "createdAt": now(), "target": {"key": spec["key"]}, "params": {
                          "spec": spec, "inputs": result["inputs"],
                          "reservations": {"power_flip_action": [spec["key"]]}},
                      "files": [], "pending": [], "checks": result["checks"]}
            draft = ops.store.put_change(cid, character["code"], ops.source.version, change)
            return {**response, "change": change, "changeset": draft, "status": status(draft)}
    except DraftError:
        raise
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        raise DraftError(str(exc)) from exc

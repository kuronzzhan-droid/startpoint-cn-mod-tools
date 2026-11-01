"""Formal new-ID character drafts, using the existing media and delivery pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import wf_character_pack as pack
from wf.deliver.changeset import member_name
from .clone_tables import build_tables, rows, validate_speech, T
from .clone_assets import checklist, collect_assets, special_checks
from .clone_server import SERVER_FILES, server_root as _server_root, server_files, server_plan
from .pixel_workshop import family_paths
from .deliver_media import read_root
from .drafts import DraftError, new_change_id, now, sha256, status, validate, verify


def clone_change(draft):
    found = [c for c in (draft or {}).get("changes", []) if c["kind"] == "character_clone"]
    if len(found) > 1:
        raise DraftError("角色草稿只能有一个 clone 身份")
    return found[0] if found else None


def identity(source, draft):
    change = clone_change(draft)
    spec = change["params"]["spec"] if change else None
    if not spec or spec["to"] != draft["characterId"] or spec["code"] != draft["code"]:
        raise DraftError("克隆草稿身份与目标 ID / code 不一致")
    if draft["baseView"] != source.version:
        raise DraftError("克隆草稿基线版本与当前视图不一致")
    if spec["to"] in source.table("character"):
        raise DraftError("目标角色已进入当前视图；请重新建立已有角色草稿")
    return change


def _vacant(ops, spec, server_dir):
    cid, code = spec["to"], spec["code"]
    if cid == "0" or not cid.isdigit() or len(cid) > 9:
        raise DraftError("目标角色 ID 必须是 1–9 位正整数")
    chars = ops.source.table("character")
    if cid in chars or any(rs and rs[0][0] == code for rs in chars.values()):
        raise DraftError("目标角色 ID 或代码名已被当前视图占用")
    if ops.store.directory(cid).exists():
        raise DraftError(f"目标草稿目录已存在：{cid}")
    for existing in ops.store.characters():
        if existing.get("code") == code:
            raise DraftError(f"代码名已被草稿 {existing['characterId']} 占用")
    if server_dir is not None:
        root = _server_root(server_dir)
        for name in SERVER_FILES:
            path = root / name
            raw = path.read_bytes()
            data = pack.load_server_json_mirror(raw, name)
            if cid in data:
                raise DraftError(f"目标角色已被服务端镜像占用：{path}/{cid}")
    from .ids import canonical, check_id
    canonical("mana_node", cid)
    occupied = check_id(ops.source, "character", cid, drafts_root=ops.store.root, server_dir=server_dir)
    if not occupied["available"]:
        raise DraftError("Character ID is reserved: " + json.dumps(occupied, ensure_ascii=False))
    from .clone_ids import linked_check
    linked = linked_check(ops, cid, code=code if spec.get("skill", "copy") == "copy" else None, server_dir=server_dir)
    if not linked["available"]:
        raise DraftError("；".join(linked["reasons"]))


def clone(ops, request, *, server_dir=None, preview=False, transform=None):
    if isinstance(request, dict) and "rarity" in request:
        raise DraftError("不支持 rarity 字段：星级必须继承母本，尚未完成星级相关表与资产的全联动")
    validate(request, "characterCloneRequest")
    spec = {**request, "skill": request.get("skill", "copy")}
    with ops.store._lock:
        _vacant(ops, spec, server_dir)
        client, tables, nodes = build_tables(ops.source, spec)
        from .ids import check_id
        reserved = check_id(ops.source, "mana_node", spec["to"], drafts_root=ops.store.root, server_dir=server_dir)
        if not reserved["available"]:
            raise DraftError("Mana node segment is reserved: " + json.dumps(reserved, ensure_ascii=False))
        donor = ops.source.table("character")[spec["from"]][0]
        assets, inputs, matrix, checks = collect_assets(ops.source, donor[0], spec["code"], int(donor[2]))
        variant = None
        if transform is not None:
            variant = transform(client, tables, assets, inputs, checks)
        owned = {logical: sorted(set(rows(raw)) - set(rows(tables[logical]))) for logical, raw in client.items()}
        planned = [{"logical": logical, "root": "common", "addedKeys": owned[logical],
                    "size": len(raw), "sha256": sha256(raw)} for logical, raw in sorted(client.items())]
        if preview:
            server_tables = server_plan(client, spec["to"], server_dir)
            if server_dir is None:
                checks.append({"level": "error", "code": "character.server_inputs",
                               "message": "未提供服务端五表基线；可保存草稿，交付前必须提供 server_dir 并复核"})
            return {"ok": True, "preview": True, "characterId": spec["to"], "code": spec["code"],
                    "tables": planned, "serverTables": server_tables, "assets": matrix, "checks": checks,
                    "buildable": not any(c["level"] == "error" for c in checks), "runtime": "未执行",
                    **({"variant": variant} if variant is not None else {})}
        members = {("common", logical): raw for logical, raw in client.items()}
        members.update(assets)
        inputs.update({f"common:{logical}": sha256(raw) for logical, raw in tables.items()})
        cid = spec["to"]
        files = []
        staged = {}
        for (root, logical), raw in sorted(members.items()):
            before = read_root(ops.source, root, logical)
            rel = f"files/clone/{root}/{logical}"
            staged[rel] = raw
            files.append({"logical": logical, "root": root, "draft": rel, "sha256": sha256(raw),
                          "size": len(raw), "encoding": "stored", "approximate": False,
                          "base": {"sha256": sha256(before) if before is not None else None, "layer": "clone baseline"}})
        change = {"id": new_change_id(), "kind": "character_clone", "title": f"从 {spec['from']} 克隆角色 {cid}",
                  "createdAt": now(), "target": {"character": cid},
                  "params": {"spec": spec, "templateCode": donor[0], "inputs": inputs, "assets": matrix,
                             "manaNodes": nodes, "ownedRows": owned},
                  "files": files, "pending": [], "checks": checks}
        if variant is not None:
            change["params"]["variant"] = variant
            change["params"]["reservations"] = {"string_id": variant.get("stringIds", [])}
        validate(change, "change")
        try:
            for relative, raw in staged.items():
                ops.store.write_file(cid, relative, raw)
            draft = ops.store.put_change(cid, spec["code"], ops.source.version, change)
        except Exception:
            ops.store.discard_all(cid)
            raise
    return {"ok": True, "characterId": cid, "code": spec["code"], "changeset": draft,
            "status": status(draft), "assets": checklist(draft), "tables": planned, "checks": checks,
            "buildable": not any(c["level"] == "error" for c in checks), "runtime": "未执行",
            **({"variant": variant} if variant is not None else {})}


def clone_members(source, store, draft):
    change = identity(source, draft)
    for token, expected in change["params"]["inputs"].items():
        root, logical = token.split(":", 1)
        raw = read_root(source, root, logical)
        if raw is None or sha256(raw) != expected:
            raise DraftError(f"克隆母本输入已变化：{token}")
    problems = verify(store, draft["characterId"], draft)
    if problems:
        raise DraftError("克隆草稿文件复核失败：" + "；".join(problems[:6]))
    members = {}
    for entry in change["files"]:
        before = read_root(source, entry["root"], entry["logical"])
        if (sha256(before) if before is not None else None) != entry["base"]["sha256"]:
            raise DraftError(f"克隆目标旧值断言失败：{entry['logical']}")
        members[entry["root"], entry["logical"]] = store.read_file(draft["characterId"], entry["draft"])
    return members


class CloneView:
    def __init__(self, source, members):
        self.source, self.members, self.version = source, members, source.version
        self.tip, self.zips, self.extra_zips = source.version, [], []
        base = getattr(source, "view", None)
        self.store = getattr(base, "store", Path("/__no_clone_store__"))
        self.index = dict(getattr(base, "index", {}))
        self._names = {member_name(root, logical): raw for (root, logical), raw in members.items()}
        self.index.update({name: "character-draft.zip" for name in self._names})

    def read_member(self, name):
        if name in self._names:
            return self._names[name], "character draft"
        if hasattr(self.source, "view"):
            return self.source.view.read_member(name)
        raise FileNotFoundError(name)

    def read_raw(self, logical):
        for root in ("common", "medium", "android"):
            if (root, logical) in self.members:
                return self.members[root, logical], "character draft"
        raw = self.source.raw(logical)
        if raw is None:
            raise FileNotFoundError(logical)
        return raw, "baseline"


def overlay_source(source, members):
    from .source import StudioSource
    return StudioSource(CloneView(source, members), official_root=getattr(source, "official_root", None))


def ops_for(ops, cid):
    draft = ops.store.load(cid)
    if not clone_change(draft) or getattr(ops.source, "_clone_cid", None) == cid:
        return ops
    from .operations import DraftOps
    source = overlay_source(ops.source, clone_members(ops.source, ops.store, draft))
    source._clone_cid = cid
    return DraftOps(source, store=ops.store, characters=ops.character_list)


def compile_clone(source, store, draft, *, server_dir=None, **pf_options):
    variant = clone_change(draft)["params"].get("variant")
    members = clone_members(source, store, draft)
    effective = overlay_source(source, members)
    effective._clone_text_cid = draft["characterId"]
    from .ability import compile_ability_operations
    ability = compile_ability_operations(effective, store, draft, server_dir=server_dir)
    members.update({("common", logical): raw for logical, raw in ability["client"].items()})
    effective = overlay_source(source, members)
    from .deliver_media import compile_media
    media = compile_media(effective, store, draft)
    members.update(media.members)
    checks = [*media.checks, *ability["checks"]]
    extra_assertions = []
    if any(c["kind"] == "pf_action_clone" for c in draft["changes"]):
        from .pf_compile import compile_pf
        added, assertions, pf_checks = compile_pf(overlay_source(source, members), store, draft, **pf_options)
        members.update(added)
        extra_assertions.extend(assertions)
        checks.extend(pf_checks)
    if any(c["kind"] == "summon_clone" for c in draft["changes"]):
        from .summon import compile_summons
        summons = compile_summons(source, store, draft, members, server_dir=server_dir, **pf_options)
        members.update({("common", logical): raw for logical, raw in summons["client"].items()})
        extra_assertions.extend(summons["changes"])
        checks.extend(summons["checks"])
    skill_assertions = []
    if any(change["kind"] == "skill_template" for change in draft["changes"]):
        from .skill_template_compile import compile_skill_template
        added, skill_assertions, skill_checks = compile_skill_template(
            overlay_source(source, members), store, draft, official_source=source, server_dir=server_dir)
        members.update(added)
        checks.extend(skill_checks)
    cid = draft["characterId"]
    final = overlay_source(source, members)
    row = final.table("character")[cid][0]
    donor = source.table("character")[clone_change(draft)["params"]["spec"]["from"]][0]
    if row[3] != donor[3] or row[2] != donor[2]:
        raise DraftError("跨属性或跨星级的旧克隆草稿不能交付；请按母本属性和星级重建")
    for slot in (17, *range(19, 25)):
        if row[slot] not in ("", "(None)") and row[slot] != (cid if slot == 17 else cid + str(slot - 18)):
            raise DraftError("旧克隆草稿仍共享母本队长或能力键；请重新克隆后交付")
    validate_speech(final.table(T.SPEECH).get(cid, []))
    checks.extend(special_checks(final, draft["code"], int(row[2])))
    missing = [item["logical"] for item in checklist(draft)
               if not (int(row[2]) < 4 and item["logical"] in family_paths(draft["code"], "special"))
               and read_root(final, item["root"], item["logical"]) is None]
    if missing:
        checks.append({"level": "error", "code": "character.assets", "message": "缺少必需资产：" + ", ".join(missing)})
    if any(c.get("level") == "error" or c.get("blocking") for c in checks):
        raise DraftError("角色克隆检查失败：" + json.dumps(checks, ensure_ascii=False))
    from .clone_edit import pending_text
    pending = pending_text(variant, final, draft["code"])
    if pending:
        raise DraftError("变体存在需人工条目，不能生成交付：" + "；".join(i["reason"] for i in pending))
    if server_dir is None:
        raise DraftError("克隆角色生成需要显式 --server-dir，用于键级合并服务端五表")
    clients = {logical: raw for (kind, logical), raw in members.items() if kind == "common" and logical.endswith(".orderedmap")}
    servers, before = server_files(clients, cid, server_dir)
    # Clone five-table merge uses the final client text. Extra text mirrors retain their own assertions.
    for target, raw in ability["servers"].items():
        if target not in servers:
            servers[target] = raw
            before[target] = ability["server_before"][target]
    assertions = [{"kind": "character_clone", "from": clone_change(draft)["params"]["spec"]["from"], "to": cid,
                   "code": draft["code"], "manaNodes": clone_change(draft)["params"]["manaNodes"]},
                  *media.assertions, *skill_assertions, *ability["changes"]]
    assertions.extend(extra_assertions)
    if any(c["kind"] == "skill_template" for c in draft["changes"]):
        from .skill_template_text import server_mirrors
        server_mirrors(members, cid, server_dir, servers, before)
    return members, servers, before, assertions, checks

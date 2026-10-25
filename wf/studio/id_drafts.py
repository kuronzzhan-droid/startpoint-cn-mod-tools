"""Reservations from all three studio namespaces and their declared payloads."""
from pathlib import Path
import hashlib
import zlib

from .drafts import DraftError
from .id_catalog import TABLES, SERVER_FILES, load_json, table_ids, server_ids


def _reservations(reservations, add, owner, origin):
    if not isinstance(reservations, dict):
        raise DraftError(f"草稿 reservations 必须是对象: {origin}")
    for kind, identities in reservations.items():
        if kind in TABLES:
            if not isinstance(identities, list):
                raise DraftError(f"草稿 reservations/{kind} 必须是数组: {origin}")
            for identity in identities:
                add(kind, str(identity), owner, "draft", origin)


def _requests(draft, add, origin, known_strings):
    owner = str(draft.get("characterId", "unknown"))
    subject = draft.get("subjectKind", "character")
    if subject == "character" and owner.isdigit():
        add("character", owner, owner, "draft", origin)
        add("mana_node", owner, owner, "draft", origin)
    if subject == "weapon":
        for kind in ("weapon", "soul_item"):
            add(kind, owner, owner, "draft", origin)
    _reservations(draft.get("reservations", {}), add, owner, origin)
    for change in draft.get("changes", []):
        if not isinstance(change, dict) or not isinstance(change.get("params", {}), dict):
            raise DraftError(f"草稿 change / params 必须是对象: {origin}")
        params = change.get("params", {})
        _reservations(params.get("reservations", {}), add, owner, origin)
        for req in params.get("requests", []):
            if not isinstance(req, dict):
                raise DraftError(f"草稿请求必须是对象: {origin}")
            spec = req.get("weapon", {})
            if not isinstance(spec, dict) or not isinstance(spec.get("soul_template", {}), dict):
                raise DraftError(f"草稿 weapon / soul_template 必须是对象: {origin}")
            if req.get("operation", "").startswith("weapon_") and "id" in spec:
                for kind in ("weapon", "soul_item"):
                    add(kind, str(spec["id"]), owner, "draft", origin)
                products = list(spec.get("enhancementProducts", []))
                products += [s["productId"] for s in spec.get("stages", []) if "productId" in s]
                for identity in products:
                    add("enhancement_shop", str(identity), owner, "draft", origin)
                    if str(identity).isdigit():
                        add("weapon", str(int(identity) // 100), owner, "draft", origin)
                template = spec.get("soul_template", {}).get("template")
                if template in {"pf_hit_invoke_damage", "pf_use_invoke_damage"}:
                    code = spec.get("code", "boss_workshop_" + str(spec["id"]))
                    add("string_id", code + "_pf_damage", owner, "draft", origin)
                if "awakening_material_" + str(spec.get("sourceWeapon")) in known_strings:
                    add("string_id", "awakening_material_" + str(spec["id"]), owner, "draft", origin)
            text = req.get("text", {})
            if not isinstance(text, dict):
                raise DraftError(f"草稿 text 必须是对象: {origin}")
            for section in ("custom_ability_string", "desc_override"):
                for key in text.get(section, {}):
                    add("string_id", str(key), owner, "draft", origin)


def _table_payload(payload, item):
    from wf_quest_lib import parse_node
    raw = payload.read_bytes()
    if ("size" in item and len(raw) != item["size"] or "sha256" in item
            and hashlib.sha256(raw).hexdigest() != item["sha256"]):
        raise DraftError(f"草稿预留文件大小或 SHA-256 不符: {payload}")
    encoding = item.get("encoding", "stored")
    try:
        if encoding in {"deflate", "raw-deflate"}:
            decoder = zlib.decompressobj(-15)
            raw = decoder.decompress(raw) + decoder.flush()
            if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise ValueError("不是完整的单一 raw-deflate 流")
        elif encoding != "stored":
            raise ValueError(f"不支持的 orderedmap 编码 {encoding}")
        return parse_node(raw)
    except (ValueError, TypeError, zlib.error) as exc:
        raise DraftError(f"无法解码草稿预留表 {payload}: {exc}") from exc


def collect_drafts(root, add, *, known_strings=()):
    root = Path(root).resolve()
    if not root.exists():
        return
    logical_kinds = {}
    for kind, logicals in TABLES.items():
        for logical in logicals:
            logical_kinds.setdefault(logical, []).append(kind)
    server_kinds = {}
    for kind, names in SERVER_FILES.items():
        for name in names:
            server_kinds.setdefault(name, []).append(kind)
    # Recursive enumeration includes character, scratch, boss and weapons directories.
    for filename in sorted(root.rglob("changeset.json")):
        if not filename.resolve().is_relative_to(root):
            raise DraftError(f"草稿 ID 来源越界: {filename}")
        draft = load_json(filename)
        if (not isinstance(draft, dict) or not isinstance(draft.get("changes"), list)
                or not isinstance(draft.get("characterId"), str)):
            raise DraftError(f"草稿 ID 来源结构无效: {filename}")
        _requests(draft, add, str(filename), known_strings)
        for change in draft["changes"]:
            if not isinstance(change.get("files", []), list):
                raise DraftError(f"草稿 files 必须是数组: {filename}")
            for item in change.get("files", []):
                if not isinstance(item, dict):
                    raise DraftError(f"草稿 file 必须是对象: {filename}")
                logical = item.get("logical", "")
                kinds = logical_kinds.get(logical, [])
                server_name = logical.removeprefix("assets/")
                is_server = item.get("kind") == "server" or logical.endswith(".json")
                if is_server:
                    kinds = server_kinds.get(server_name, [])
                if not kinds:
                    continue
                relative = item.get("draft")
                if not relative:
                    raise DraftError(f"草稿预留缺少文件路径: {filename}: {logical}")
                payload = (filename.parent / relative).resolve()
                if not payload.is_relative_to(filename.parent.resolve()) or not payload.is_file():
                    raise DraftError(f"草稿预留文件缺失或越界: {payload}")
                rows = load_json(payload) if is_server else _table_payload(payload, item)
                for kind in kinds:
                    identities = server_ids(kind, server_name, rows) if is_server else table_ids(kind, logical, rows)
                    for identity, _ in identities:
                        add(kind, identity, str(draft["characterId"]), "draft", str(payload))
                        if kind == "enhancement_shop" and identity.isdigit():
                            add("weapon", str(int(identity) // 100), str(draft["characterId"]), "draft", str(payload))

"""Exact public-file plan for the lazy character-family index."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from wf_wiki_categories import HIDDEN_CHARACTER_IDS
from wf_wiki_pixel_output import checked_path
from wf_wiki_public import public_id

INDEX = "data/character-variants.js"
JSON_INDEX = "data/character-variants.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def variant_plan(source: Path, catalog: dict) -> tuple[list[dict], dict, dict]:
    """Check metadata, JSON/JS parity and complete visible-ID group closure."""
    root = checked_path(source)
    reference = catalog.get("meta", {}).get("characterVariants")
    # The existing frontend explicitly supports this exact fallback when older
    # snapshots have no metadata. No caller-supplied or inferred path is allowed.
    require(reference is None or (isinstance(reference, dict) and set(reference) == {"url", "version", "schemaVersion"}
            and reference["url"] == INDEX and reference["schemaVersion"] == 1),
            "角色变体元数据没有声明受支持的固定索引")
    raw_json = checked_path(root / JSON_INDEX).read_bytes()
    raw_js = checked_path(root / INDEX).read_bytes()
    value = json.loads(raw_json)
    match = re.fullmatch(r"\s*window\.WF_CHARACTER_VARIANTS\s*=\s*(\{.*\})\s*;\s*", raw_js.decode("utf-8"), re.S)
    require(match is not None and json.loads(match[1]) == value, "变体 JSON 与脚本索引不同或脚本含额外代码")
    require(isinstance(value, dict) and set(value) == {"schemaVersion", "dataVersion", "groups"}
            and value["schemaVersion"] == 1 and isinstance(value["groups"], dict), "变体索引格式不受支持")
    visible = [c["id"] for c in catalog["characters"]]
    require(visible and len(visible) == len(set(visible))
            and all(isinstance(cid, str) and re.fullmatch(r"c[0-9a-f]{12}", cid) for cid in visible), "变体发布需要唯一公开角色目录")
    visible = set(visible)
    require(not visible & {public_id("c", cid) for cid in HIDDEN_CHARACTER_IDS}, "变体目录含隐藏角色")
    groups = value["groups"]
    require(set(groups) <= visible, "变体索引键不在可见角色白名单")
    for cid, members in groups.items():
        require(isinstance(members, list) and all(isinstance(m, str) for m in members)
                and len(members) >= 2 and len(members) == len(set(members))
                and cid in members and set(members) <= visible, "变体组成员不在可见角色白名单或重复")
        require(all(groups.get(member) == members for member in members), "变体组反向关系不完整或顺序不同")
    version = hashlib.sha256(json.dumps({"schemaVersion": 1, "groups": groups},
                                       sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    require(value["dataVersion"] == version and (reference is None or reference["version"] == version),
            "变体索引版本摘要与页面元数据不同")
    hashes = {INDEX: hashlib.sha256(raw_js).hexdigest(), JSON_INDEX: hashlib.sha256(raw_json).hexdigest()}
    return ([{"path": INDEX, "bytes": len(raw_js), "sha256": hashes[INDEX]}], hashes,
            {"groups": len({tuple(group) for group in groups.values()}), "characters": len(groups),
             "version": version, "publicIndex": INDEX, "jsonIndexExcluded": True,
             "metadataDeclared": reference is not None})

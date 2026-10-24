"""Public character-family links from official identities and unambiguous MOD names."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from wf_wiki_categories import HIDDEN_CHARACTER_IDS
from wf_wiki_public import public_id
from wf_wiki_paths import is_junction

PUBLIC_ID = re.compile(r"c[0-9a-f]{12}\Z")


def _name(value) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def _identity(cid: str, official: dict) -> str:
    """Follow only valid official identity keys; missing/sentinel/cyclic keys never group."""
    seen = set()
    current = cid
    while current not in seen:
        seen.add(current)
        rows = official.get(current, [])
        row = rows[0] if rows else []
        parent = str(row[27]) if len(row) > 27 else ""
        if parent in ("", "(None)", current) or parent not in official:
            return current
        current = parent
    return cid


def build_variant_index(characters: list[dict], current: dict, official: dict) -> dict:
    if not official:
        raise ValueError("官方角色基准为空，不能可靠建立角色变体关系")
    hidden = {public_id("c", cid) for cid in HIDDEN_CHARACTER_IDS}
    visible = {}
    for character in characters:
        cid = str(character.get("id", ""))
        if not PUBLIC_ID.fullmatch(cid):
            raise ValueError("变体索引只接受公开角色 ID")
        if cid in visible:
            raise ValueError("公开角色 ID 重复")
        if cid not in hidden:
            visible[cid] = character
    official_ids = {public_id("c", cid): str(cid) for cid in official}
    current_ids = {public_id("c", cid): str(cid) for cid in current}
    family_by_id = {cid: _identity(raw, official) for cid, raw in official_ids.items() if cid in visible}
    names = defaultdict(set)
    for cid, family in family_by_id.items():
        name = _name(visible[cid].get("name"))
        if name:
            names[name].add(family)
    for cid, character in visible.items():
        if cid in family_by_id:
            continue
        name = _name(character.get("name"))
        families = names.get(name, set())
        raw = current_ids.get(cid)
        rows = current.get(raw, []) if raw else []
        row = rows[0] if rows else []
        parent = str(row[27]) if len(row) > 27 else ""
        explicit = _identity(parent, official) if parent in official else None
        # A cloned row with another name is not the same person. Names alone are
        # accepted only when they point to exactly one already verified family.
        if explicit in families:
            family_by_id[cid] = explicit
        elif len(families) == 1:
            family_by_id[cid] = next(iter(families))
    families = defaultdict(list)
    for cid, family in family_by_id.items():
        families[family].append(cid)
    position = {cid: i for i, cid in enumerate(visible)}
    groups = {}
    for members in families.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda cid: (cid not in official_ids, visible[cid].get("catalogOrder", position[cid]), position[cid]))
        for cid in members:
            groups[cid] = members
    payload = {"schemaVersion": 1, "groups": groups}
    payload["dataVersion"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    return payload


def write_character_variants(repo: Path, output: Path, catalog: dict, store: Path | None = None) -> dict:
    """Run after public_catalog; no asset decode, current-store mutation or raw-ID output."""
    import wf_mod_tool as core
    from wf_wiki_catalog_source import WikiSource

    source = WikiSource(repo, store if store is not None else core.resolve_active_store())
    payload = build_variant_index(catalog["characters"], source.table("character"), source.table("character", True))
    source.verify_unchanged()
    directory = Path(output) / "data"
    if directory.is_symlink() or is_junction(directory):
        raise ValueError("变体索引目录不能是链接")
    directory.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    for filename, content in (("character-variants.json", text + "\n"),
                              ("character-variants.js", "window.WF_CHARACTER_VARIANTS=" + text + ";\n")):
        path = directory / filename
        if path.is_symlink() or is_junction(path):
            raise ValueError("变体索引不能覆盖链接")
        path.write_text(content, encoding="utf-8", newline="\n")
    # The snapshot hash busts browser caches; repeated mounts share one lazy load.
    catalog.setdefault("meta", {})["characterVariants"] = {
        "url": "data/character-variants.js", "version": payload["dataVersion"], "schemaVersion": 1,
    }
    return {"groups": len({tuple(group) for group in payload["groups"].values()}),
            "characters": len(payload["groups"]), "version": payload["dataVersion"]}

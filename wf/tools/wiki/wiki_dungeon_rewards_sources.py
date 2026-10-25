"""Read only copied gray assets and the existing public Wiki identity catalog."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from wf_wiki_data import chunk_payload
from wf_wiki_public import public_id
from wf_wiki_dungeon_rewards_schema import require, unique_object
from wf_wiki_paths import is_junction


def collect_event_titles(store):
    """One explicitly named client table supplies names only, never reward values."""
    import wf_assets
    import wf_quest_lib
    from wf_wiki_dungeons_schema import clean_text, leaf_rows
    logical = "master/reward/event/collect_item_event.orderedmap"
    found = wf_assets.locate(Path(store), logical)
    if found is None:
        return {}, None
    path = found[1]
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 8 * 1024 * 1024,
            "Invalid collection-event title table")
    raw = path.read_bytes()
    tree = wf_quest_lib.parse_node(raw)
    titles = {}
    for key, node in tree.items():
        row = next(leaf_rows(node), [])
        if len(row) > 1 and clean_text(row[1]):
            titles[str(key)] = clean_text(row[1])
    return titles, {"logical": logical, "origin": "local-name-reference", "sha256": hashlib.sha256(raw).hexdigest()}


def read_json(path):
    require(path.is_file() and not path.is_symlink() and not is_junction(path),
            f"Missing or linked snapshot file: {path.name}")
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)


def read_assignment(path, name):
    raw = path.read_text(encoding="utf-8-sig").strip()
    match = re.fullmatch(r"window\." + re.escape(name) + r"\s*=\s*(.*);", raw, re.S)
    require(match is not None, f"Invalid data assignment: {path.name}")
    return json.loads(match[1], object_pairs_hook=unique_object)


def wiki_catalog(site):
    data = read_assignment(site / "data.js", "WF_WIKI")
    if "equipment" not in data:
        record = data["dataManifest"]["chunks"]["equipment"]
        require(re.fullmatch(r"data/equipment-[0-9a-f]{16}\.js", record["url"]), "Invalid equipment chunk")
        raw = (site / record["url"]).read_bytes()
        require(len(raw) == record["bytes"] and hashlib.sha256(raw).hexdigest() == record["sha256"],
                "Equipment chunk changed")
        data.update(chunk_payload(raw, "equipment"))
    return data


class GrayAssets:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.loaded = {}
        self.hashes = {}

    def get(self, name):
        require(re.fullmatch(r"[a-z0-9_]+\.json", name), "Invalid snapshot filename")
        if name not in self.loaded:
            path = self.directory / name
            self.loaded[name] = read_json(path)
            self.hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return self.loaded[name]

    def merged(self, base, extra):
        return {**self.get(base), **self.get(extra)}

    def rogue(self):
        data = copy.deepcopy(self.get("rogue_event.json"))
        for event_id, extra in self.get("rogue_event_cnmod.json").get("events", {}).items():
            require(event_id in data.get("events", {}), "Rogue extension references missing event")
            rows = data["events"][event_id].setdefault("folder_clear_chance", [])
            for row in extra.get("folder_clear_chance", []):
                current = next((r for r in rows if r.get("type", 0) == row.get("type", 0)
                                and r.get("id") == row.get("id")), None)
                if current is None:
                    rows.append(row)
                else:
                    require(current.get("count", 1) == row.get("count", 1)
                            and current.get("chance") == row.get("chance"), "Conflicting rogue extension")
        return data.get("events", {}) if data.get("enabled") is True else {}


class Names:
    def __init__(self, assets, wiki):
        self.items = assets.merged("item_lookup.json", "item_lookup_cnmod.json")
        self.equipment_lookup = assets.get("equipment_lookup.json")
        self.equipment = {row["id"]: row for row in wiki.get("equipment", [])}
        self.characters = {row["id"]: row for row in wiki.get("characters", [])}
        self.degrees = {}
        for name in ("degree", "degree_rank_p5b", "degree_sponsor", "degree_character_mod", "degree_exclusive", "degree_author926"):
            self.degrees.update(assets.get(name + ".json"))
        self.unknown = set()

    def reward(self, kind, raw_id=None, amount=1, probability=None):
        raw_id = str(raw_id) if raw_id is not None else ""
        link = {}
        if kind == "equipment":
            pid = public_id("w", raw_id)
            row = self.equipment.get(pid)
            name = row.get("name") if row else self.equipment_lookup.get(raw_id)
            if row:
                link["equipmentId"] = pid
        elif kind == "character":
            pid = public_id("c", raw_id)
            row = self.characters.get(pid)
            name = row.get("name") if row else None
            if row:
                link["characterId"] = pid
        elif kind == "item":
            name = self.items.get(raw_id)
        elif kind == "degree":
            row = self.degrees.get(raw_id)
            name = row.get("name") if isinstance(row, dict) else row if isinstance(row, str) else None
        else:
            name = {"beads": "星导石", "mana": "玛纳", "exp": "经验值"}.get(kind)
        if not isinstance(name, str) or not name.strip():
            self.unknown.add((kind, raw_id))
            name = "未收录的" + {"item": "道具", "equipment": "武器", "character": "角色", "degree": "称号"}.get(kind, "奖励资料")
        result = {"kind": kind, "name": name.strip(), "amountText": str(amount), **link}
        if probability:
            result["probabilityText"] = str(probability)
        return result

    def raw_reward(self, raw, *, shop=False, probability=None):
        enum = ({0: "item", 1: "exp", 2: "mana", 3: "character", 4: "equipment", 5: "degree"}
                if shop else {0: "item", 1: "equipment", 2: "character", 3: "beads", 4: "mana", 5: "exp", 6: "item", 7: "item"})
        kind = enum.get(raw.get("type", 0), "unknown")
        return self.reward(kind, raw.get("id"), raw.get("count", 1), probability)

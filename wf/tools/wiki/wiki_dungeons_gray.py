"""Build provenance-only quest indexes from explicitly supplied gray snapshots."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from wf_wiki_dungeons_schema import QUEST_CATEGORIES, quest_table
from wf_wiki_paths import is_junction


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("灰服关卡配置存在重复 JSON 字段")
        result[key] = value
    return result


def gray_quest_lookup(directory):
    """Retain category boundaries and CN overrides; expose only private hashes."""
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink() or is_junction(directory):
        raise ValueError("灰服关卡配置目录不存在或属于链接")
    lookup, hashes = {}, {}

    def read(name):
        path = directory / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("灰服关卡配置缺失、不安全或过大：" + name)
        raw = path.read_bytes()
        records = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)
        if not isinstance(records, dict) or any(
            not re.fullmatch(r"\d+", key) or not isinstance(row, dict)
            or not isinstance(row.get("name", ""), str) or len(row.get("name", "")) > 500
            for key, row in records.items()
        ):
            raise ValueError("灰服关卡配置格式无效：" + name)
        hashes[name] = hashlib.sha256(raw).hexdigest()
        return records

    for kind, categories in QUEST_CATEGORIES.items():
        filename = quest_table(kind).rsplit("/", 1)[1].replace(".orderedmap", ".json")
        records = read(filename)
        if kind == "boss":
            records.update(read("boss_battle_quest_cnmod.json"))
        for key, row in records.items():
            for category in categories:
                lookup[f"{category}_{key}"] = row.get("name", "")
    return lookup, hashes


def verify_gray_quests_unchanged(directory, hashes):
    for name, expected in hashes.items():
        if hashlib.sha256((Path(directory) / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("导出时灰服关卡配置发生变化，请重新生成")

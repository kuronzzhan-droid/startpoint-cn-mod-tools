"""Read-only allowlist for the public dungeon catalog and its referenced artwork."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import io
import json
from pathlib import Path
import re

from PIL import Image
from wf_wiki_pixel_output import checked_path, digest
from wf_wiki_dungeon_groups import SERIES_VARIANTS, validate_series_fields

INDEX = "dungeons-data.js"
MANIFEST = "dungeons-manifest.json"
MEDIA = re.compile(r"media/[0-9a-f]{64}\.webp")
IDENTIFIER = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
CATEGORIES = {"活动", "领主战", "降临讨伐", "模式"}
SOURCE_STATUSES = {"local-snapshot", "mixed-snapshot", "gray-snapshot"}
ELEMENTS = {"", "火", "水", "雷", "风", "光", "暗", "无"}
STATS = {"total", "matched", "sameName", "differentName"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def shape(value, required, optional=frozenset()):
    require(isinstance(value, dict) and required <= set(value) <= required | optional,
            "副本索引包含缺失、未知或非公开字段")


def text(value, maximum, empty=True):
    require(isinstance(value, str) and len(value) <= maximum and (empty or value.strip())
            and not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value), "副本索引文字格式无效")


def source(value, allow_lookup=False):
    shape(value, {"label", "status", "checkedAt"}, {"questLookup"} if allow_lookup else set())
    text(value["label"], 1000, False)
    require(isinstance(value["status"], str) and value["status"] in SOURCE_STATUSES, "副本来源状态无效")
    checked = value["checkedAt"]
    require(isinstance(checked, str) and len(checked) <= 40, "副本来源时间无效")
    try:
        parsed = datetime.fromisoformat(checked.replace("Z", "+00:00"))
        require(parsed.tzinfo is not None and "T" in checked, "副本来源时间必须包含时区")
    except ValueError as exc:
        raise ValueError("副本来源时间无效") from exc
    if "questLookup" in value:
        stats = value["questLookup"]
        shape(stats, STATS)
        require(all(type(number) is int and 0 <= number <= 1_000_000 for number in stats.values())
                and stats["matched"] <= stats["total"]
                and stats["sameName"] + stats["differentName"] == stats["matched"], "副本关卡核对统计不闭合")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "副本 JSON 不允许重复字段")
        result[key] = value
    return result


def non_json(value):
    raise ValueError(f"副本 JSON 不支持常量 {value}")


def series(item):
    validate_series_fields(item)
    if "seriesId" not in item:
        return None
    identifier, variant = item["seriesId"], item["variantLabel"]
    require(isinstance(identifier, str) and identifier in SERIES_VARIANTS
            and isinstance(variant, str) and variant in SERIES_VARIANTS[identifier], "副本系列或变体不在白名单")
    require(identifier != "series-gauntlets" or item["category"] == "模式", "连战系列必须属于模式分类")
    return identifier, variant


def dungeon_plan(source_root: Path) -> tuple[list[dict], dict, dict]:
    """Return only the script and verified referenced WebP files, without writes.

    The private manifest is deliberately not an input: it contains logical game
    paths and collection provenance that must never enter the public package.
    """
    root = checked_path(source_root)
    index_path = checked_path(root / INDEX)
    require(index_path.stat().st_size <= 8 * 1024 * 1024, "副本索引超过发布大小上限")
    raw = index_path.read_bytes()
    match = re.fullmatch(r"\s*window\.WF_WIKI_DUNGEONS\s*=\s*(\{.*\})\s*;\s*", raw.decode("utf-8"), re.S)
    require(match is not None, "副本脚本不是固定 JSON 赋值或包含额外代码")
    value = json.loads(match[1], object_pairs_hook=unique_object, parse_constant=non_json)
    shape(value, {"schemaVersion", "source", "items"})
    require(type(value["schemaVersion"]) is int and value["schemaVersion"] == 1, "副本索引版本不受支持")
    source(value["source"])
    items = value["items"]
    require(isinstance(items, list) and 0 < len(items) <= 5000, "副本目录为空或条目过多")
    seen, media, categories, stats = set(), set(), Counter(), Counter()
    series_counts, series_variants = Counter(), {}
    quest_count = checked_items = 0
    for item in items:
        shape(item, {"id", "title", "category", "summary", "quests", "banner", "entryImage", "previewImages", "source"},
              {"legacyGuide", "seriesId", "seriesTitle", "variantLabel"})
        identifier = item["id"]
        require(isinstance(identifier, str) and len(identifier) <= 80 and IDENTIFIER.fullmatch(identifier)
                and identifier not in seen, "副本 ID 无效或重复")
        seen.add(identifier)
        text(item["title"], 500, False); text(item["summary"], 2000)
        require(isinstance(item["category"], str) and item["category"] in CATEGORIES, "副本分类无效")
        categories[item["category"]] += 1
        grouped = series(item)
        if grouped:
            series_counts[grouped[0]] += 1
            series_variants.setdefault(grouped[0], Counter())[grouped[1]] += 1
        if "legacyGuide" in item:
            require(item["legacyGuide"] == "five-boss" and identifier == "boss-1-99" and item["category"] == "模式",
                    "副本旧版查询入口不在白名单")
        source(item["source"], allow_lookup=True)
        if "questLookup" in item["source"]:
            checked_items += 1; stats.update(item["source"]["questLookup"])
        quests = item["quests"]
        require(isinstance(quests, list) and len(quests) <= 10000, "副本关卡列表无效")
        for quest in quests:
            shape(quest, {"name", "difficulty", "element"})
            text(quest["name"], 500, False); text(quest["difficulty"], 100)
            require(isinstance(quest["element"], str) and quest["element"] in ELEMENTS, "副本关卡属性无效")
        quest_count += len(quests)
        previews = item["previewImages"]
        require(isinstance(previews, list) and len(previews) <= 3
                and all(isinstance(url, str) for url in previews) and len(previews) == len(set(previews)), "副本预览图列表无效")
        for url in [item["banner"], item["entryImage"], *previews]:
            if url is None:
                continue
            require(isinstance(url, str) and MEDIA.fullmatch(url), "副本媒体路径不在白名单")
            media.add(url)
    files = [{"path": INDEX, "bytes": len(raw), "sha256": digest(raw)}]
    watched = {INDEX: digest(raw)}
    for url in sorted(media):
        file = checked_path(root / url)
        require(file.is_file() and file.stat().st_size <= 8 * 1024 * 1024, "副本图片缺失或超过大小上限")
        data = file.read_bytes()
        require(digest(data) == file.stem, "副本图片实际哈希与文件名不同")
        try:
            with Image.open(io.BytesIO(data)) as image:
                require(image.format == "WEBP" and image.n_frames == 1 and 0 < image.width <= 1200 and 0 < image.height <= 1600,
                        "副本图片不是受支持的静态 WebP 或尺寸超限")
                image.load()
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError("副本图片无法解码") from exc
        files.append({"path": url, "bytes": len(data), "sha256": file.stem})
        watched[url] = file.stem
    return files, watched, {"items": len(items), "categories": dict(categories), "quests": quest_count,
                           "series": dict(series_counts), "seriesVariants": {key: dict(counts) for key, counts in series_variants.items()},
                           "questLookupItems": checked_items, "questLookup": dict(stats), "source": value["source"],
                           "images": len(media), "bytes": sum(row["bytes"] for row in files),
                           "publicIndex": INDEX, "manifestExcluded": True, "mediaHashVerified": True}

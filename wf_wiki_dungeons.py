"""Export activity/boss/mode entries without changing game data or the main Wiki bundle.

Local: python -X utf8 mod-tools/wf_wiki_dungeons.py --site <Wiki site>
Gray:  add --gray-url <public upload root> --gray-snapshot <isolated directory>
"""
from __future__ import annotations

import argparse
import io
import json
import re
from collections import Counter
from pathlib import Path

from PIL import Image

import wf_assets
import wf_mod_tool as core
from wf_wiki_paths import is_junction
from wf_wiki_dungeons_sources import DungeonSources, checksum
from wf_wiki_dungeons_gray import gray_quest_lookup, verify_gray_quests_unchanged
from wf_wiki_dungeons_series import (
    boss_series, correct_gauntlet_images, event_series, validate_series, verified_gauntlet_tables,
)
from wf_wiki_dungeons_schema import (
    BOSS_QUEST, EVENTS, MODES, NODE_TABLE, RANK_TABLE, cell, clean_text,
    event_table, image_paths, leaf_rows, quest_details, quest_table, table_paths,
)


class DungeonMedia:
    """Independent manifest: wide banners must not inherit the portrait/icon 384px cap."""
    def __init__(self, sources, site):
        self.sources, self.site = sources, Path(site)
        self.entries, self.errors = {}, {}
        try:
            self.previous = json.loads((self.site / "dungeons-manifest.json").read_text(encoding="utf-8")).get("media", {})
        except (OSError, ValueError):
            self.previous = {}

    def image(self, logical):
        if logical in self.entries:
            return self.entries[logical]["url"]
        raw = self.sources.raw(logical)
        if raw is None:
            return None
        previous = self.previous.get(logical, {})
        url = previous.get("url", "")
        if (previous.get("profile") == "dungeon-1200x1600-q92" and previous.get("sourceSha256") == checksum(raw)
                and re.fullmatch(r"media/[0-9a-f]{64}\.webp", url) and (self.site / url).is_file()
                and checksum((self.site / url).read_bytes()) == previous.get("sha256")):
            self.entries[logical] = {**previous, "origin": self.sources.records[logical]["origin"]}
            return url
        try:
            with Image.open(io.BytesIO(wf_assets.png_decode(raw))) as original:
                if original.width * original.height > 20_000_000:
                    raise ValueError("图片像素超过上限")
                original.load()
                picture = original.convert("RGBA")
                picture.thumbnail((1200, 1600), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                picture.save(output, "WEBP", quality=92, method=4)
                encoded = output.getvalue()
                digest = checksum(encoded)
                url = f"media/{digest}.webp"
                target = self.site / url
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.is_file() or checksum(target.read_bytes()) != digest:
                    target.write_bytes(encoded)
                self.entries[logical] = {"url": url, "sha256": digest, "sourceSha256": checksum(raw),
                                         "width": picture.width, "height": picture.height, "bytes": len(encoded),
                                         "origin": self.sources.records[logical]["origin"], "profile": "dungeon-1200x1600-q92"}
                return url
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            self.errors[logical] = str(exc)
            return None


def thumbnail_paths(node):
    found = []
    for row in leaf_rows(node):
        for value in row:
            if value.startswith("quest/thumbnail/"):
                for path in image_paths(value):
                    if path not in found:
                        found.append(path)
        if len(found) >= 4:
            break
    return found[:4]


def base_item(identifier, title, category, summary, quests, logicals, banners, entries, previews):
    return {"id": identifier, "title": title, "category": category, "summary": summary,
            "quests": quests, "_sources": logicals, "_banners": banners,
            "_entries": entries, "_previews": previews}


def build_items(sources, lookup=None):
    sources.prefetch(table_paths())
    ranks = sources.table(RANK_TABLE)
    result = []
    for kind, (label, title_col, banner_col, entry_col, preview_cols) in EVENTS.items():
        logical, qlogical = event_table(kind), quest_table(kind)
        tree, quest_tree = sources.table(logical), sources.table(qlogical)
        extra = sources.table(quest_table("world_story_boss")) if kind == "world_story" else {}
        for key, node in tree.items():
            row = next(leaf_rows(node), [])
            if not row or not re.fullmatch(r"[a-zA-Z0-9_-]+", str(key)):
                continue
            qnode = quest_tree.get(key, {})
            audit = Counter(total=0, matched=0, sameName=0, differentName=0) if lookup is not None else None
            details = quest_details(qnode, kind, ranks, lookup, audit)
            if kind == "world_story":
                details += quest_details(extra.get(key, {}), "world_story_boss", ranks, lookup, audit)
            title = clean_text(cell(row, title_col))
            if title in ("", "活动名"):
                title = details[0]["name"] if details else label
            mode = MODES.get((kind, key))
            if mode and kind == "rush":
                # Custom towers borrow native rank slots; these do not describe their actual difficulty.
                for detail in details:
                    detail["difficulty"] = ""
            category = "模式" if mode else "活动"
            summary = mode[1] if mode else f"{label} · {len(details)} 项关卡资料"
            logicals = [logical, qlogical, RANK_TABLE]
            if kind == "world_story":
                logicals.append(quest_table("world_story_boss"))
            previews = [p for column in preview_cols for p in image_paths(cell(row, column))]
            item = base_item(f"event-{kind.replace('_', '-')}-{str(key).lower()}", title, category, summary,
                             details, logicals, image_paths(cell(row, banner_col)),
                             image_paths(cell(row, entry_col)) or thumbnail_paths(qnode), previews)
            item.update(event_series(kind, key, row))
            if audit is not None:
                item["_questCheck"] = dict(audit)
            result.append(item)
    nodes, boss_quests = sources.table(NODE_TABLE), sources.table(BOSS_QUEST)
    for group_key, group in nodes.items():
        if not isinstance(group, dict):
            continue
        for key, node in group.items():
            row = next(leaf_rows(node), [])
            if not row or not re.fullmatch(r"[a-zA-Z0-9_-]+", str(key)):
                continue
            title = clean_text(cell(row, 1))
            category = "降临讨伐" if clean_text(cell(row, 0)) == "降临讨伐" else "领主战"
            qnode = boss_quests.get(group_key, {}).get(key, {})
            audit = Counter(total=0, matched=0, sameName=0, differentName=0) if lookup is not None else None
            details = quest_details(qnode, "boss", ranks, lookup, audit)
            five_boss = group_key == "1" and key == "99"
            if five_boss:
                category, title = "模式", "五重决战"
            item = base_item(f"boss-{group_key}-{key}".lower(), title or category, category,
                             f"{clean_text(cell(row, 0))} · {len(details)} 项关卡资料", details,
                             [NODE_TABLE, BOSS_QUEST, RANK_TABLE], [], image_paths(cell(row, 11)),
                             image_paths(cell(row, 12)))
            item.update(boss_series(row))
            if five_boss:
                item["legacyGuide"] = "five-boss"
                item["_banners"] = image_paths(cell(row, 12)) + ["quest/event/banner/story_event/mod/five_boss/five_boss.png"]
            if audit is not None:
                item["_questCheck"] = dict(audit)
            result.append(item)
    correct_gauntlet_images(result)
    return result


def render_catalog(sources, media, drafts, *, quest_assets=False):
    candidates = {logical for item in drafts for key in ("_banners", "_entries", "_previews") for logical in item[key]}
    sources.prefetch(candidates)
    items = []
    for draft in drafts:
        item = {key: value for key, value in draft.items() if not key.startswith("_")}
        used = []

        def choose(paths, limit):
            urls = []
            # Prefer an actually fetched gray image over a local fallback alternative.
            for logical in sorted(paths, key=lambda p: sources.records.get(p, {}).get("origin") not in ("gray", "gray-snapshot")):
                url = media.image(logical)
                if url:
                    used.append(logical)
                    if url not in urls:
                        urls.append(url)
                    if len(urls) >= limit:
                        break
            return urls

        banners = choose(draft["_banners"], 1)
        entries = choose(draft["_entries"], 1)
        previews = choose(draft["_previews"], 3)
        verified = verified_gauntlet_tables(sources, item["id"])
        logicals = [logical for logical in draft["_sources"] if not (verified and logical == RANK_TABLE)]
        item.update(banner=banners[0] if banners else None, entryImage=entries[0] if entries else None,
                    previewImages=previews, source=sources.source(logicals + used))
        if verified:
            item["source"]["label"] = "灰服当前补丁已核对；游戏内开放状态未实测"
        if "_questCheck" in draft:
            audit = draft["_questCheck"]
            if quest_assets or not verified or audit["matched"]:
                item["source"]["questLookup"] = audit
                label = "灰服当前关卡配置已对应" if quest_assets else "灰服后台可对应"
                item["source"]["label"] += f"；{label} {audit['matched']}/{audit['total']} 项关卡"
                if quest_assets and not verified:
                    item["source"]["label"] += "；游戏内开放状态未实测"
        items.append(item)
    return {"schemaVersion": 1, "source": sources.source(sources.records), "items": items}


def validate_catalog(payload, site):
    ids = [item["id"] for item in payload["items"]]
    if not ids or len(ids) != len(set(ids)) or any(len(x) > 80 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", x) for x in ids):
        raise ValueError("副本目录为空或包含重复/不安全的 ID")
    for item in payload["items"]:
        for url in [item["banner"], item["entryImage"], *item["previewImages"]]:
            if url and (not re.fullmatch(r"media/[0-9a-f]{64}\.webp", url) or not (site / url).is_file()):
                raise ValueError("副本图片链接无效")
        if item["category"] not in ("活动", "领主战", "降临讨伐", "模式"):
            raise ValueError("副本分类无效")
        validate_series(item)


def export_dungeons(repo, site, *, gray_url=None, snapshot=None, store=None, gray_lookup=None,
                    gray_quest_assets=None, community_catalog=None):
    repo, site = Path(repo).resolve(), Path(site).resolve()
    store = Path(store or core.resolve_active_store(repo)).resolve()
    if site == repo or site in repo.parents or site == store or site.is_relative_to(store.parent):
        raise ValueError("导出目录不得覆盖仓库或游戏资源目录")
    if site.is_relative_to(repo) and not site.is_relative_to(repo / "work"):
        raise ValueError("仓库内产物仅允许放在 work 下")
    if (site / "media").is_symlink() or is_junction(site / "media") or site.is_symlink() or is_junction(site):
        raise ValueError("导出目录不得使用链接或目录联接")
    site.mkdir(parents=True, exist_ok=True)
    if gray_url and not snapshot:
        raise ValueError("采集灰服资源时请显式指定 --gray-snapshot")
    sources = DungeonSources(store, snapshot=snapshot, gray_url=gray_url)
    lookup = None
    quest_hashes = {}
    if gray_quest_assets:
        lookup, quest_hashes = gray_quest_lookup(gray_quest_assets)
    elif gray_lookup:
        lookup = json.loads(Path(gray_lookup).read_text(encoding="utf-8"))
        if not isinstance(lookup, dict) or any(not re.fullmatch(r"\d+_\d+", key) or not isinstance(value, str)
                                               or len(value) > 500 for key, value in lookup.items()):
            raise ValueError("灰服关卡查询快照格式无效")
    print("正在读取副本入口和关卡元表……", flush=True)
    drafts = build_items(sources, lookup)
    print(f"已读取 {len(drafts)} 项入口，正在匹配横幅和预览图……", flush=True)
    media = DungeonMedia(sources, site)
    payload = render_catalog(sources, media, drafts, quest_assets=bool(gray_quest_assets))
    validate_catalog(payload, site)
    sources.verify_local_unchanged()
    if gray_quest_assets:
        verify_gray_quests_unchanged(gray_quest_assets, quest_hashes)
    sources.write_manifest()
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    (site / "dungeons-data.js").write_text("window.WF_WIKI_DUNGEONS=" + encoded + ";\n", encoding="utf-8")
    receipt = {"generator": "wf_wiki_dungeons", "schemaVersion": 1, "source": payload["source"],
               "items": len(payload["items"]), "categories": dict(Counter(x["category"] for x in payload["items"])),
               "series": dict(Counter(x["seriesId"] for x in payload["items"] if "seriesId" in x)),
               "media": media.entries, "mediaErrors": media.errors, "sourceFiles": sources.records,
               "sourceErrors": sources.errors, "bytes": len(encoded.encode("utf-8"))}
    if lookup is not None:
        totals = Counter()
        for draft in drafts:
            totals.update(draft.get("_questCheck", {}))
        provenance = ({"origin": "gray-quest-assets", "files": quest_hashes} if gray_quest_assets
                      else {"sha256": checksum(Path(gray_lookup).read_bytes())})
        receipt["questLookup"] = {**provenance, **dict(totals)}
    (site / "dungeons-manifest.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if community_catalog:
        target = Path(community_catalog)
        entries = [{"id": item["id"], "title": item["title"]} for item in payload["items"]]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("// Generated by wf_wiki_dungeons.py; refresh with an explicit --community-catalog.\nexport default "
                          + json.dumps({"items": entries}, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description="只读导出活动、副本和模式目录")
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--gray-url", help="显式启用灰服公开资源 GET 采集")
    parser.add_argument("--gray-snapshot", type=Path, help="独立快照目录；无 URL 时只离线读已保存快照")
    parser.add_argument("--gray-lookup", type=Path, help="已只读获取的灰服 /api/lookup/quests JSON，仅核对名称，不推断开放")
    parser.add_argument("--gray-quest-assets", type=Path, help="实际灰服关卡 JSON 快照，优先于旧后台查询快照；仅核对配置")
    parser.add_argument("--community-catalog", type=Path, help="仅显式指定时生成社区后端可信 ID/标题模块")
    args = parser.parse_args()
    result = export_dungeons(Path(__file__).resolve().parent.parent, args.site,
                             gray_url=args.gray_url, snapshot=args.gray_snapshot,
                             gray_lookup=args.gray_lookup, gray_quest_assets=args.gray_quest_assets,
                             community_catalog=args.community_catalog)
    print(json.dumps({key: result[key] for key in ("items", "categories", "source", "bytes")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

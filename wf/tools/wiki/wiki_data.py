"""Classic-script data chunks: portable offline, auditable, no media conversion."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from wf_wiki_categories import HIDDEN_CHARACTER_IDS
from wf_wiki_public import PRIVATE, public_id
from wf_wiki_paths import is_junction

PREFIX = "window.WF_WIKI_CHUNKS = window.WF_WIKI_CHUNKS || {};\nwindow.WF_WIKI_CHUNKS["
CHARACTER_ID = re.compile(r"c[0-9a-f]{12}\Z")
LOCAL_PATH = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]|file://|/(?:Users|home)/[^/\s]+")
INDEX_FIELDS = ("id", "name", "title", "rarity", "element", "type", "origin", "category", "icon", "avatars",
                "aliases", "themes", "theme", "earlyDesign", "editorNote", "limited",
                "availabilitySource", "availabilityNote", "catalogOrder")


def compact(value, *, sort_keys=False):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular(path):
    require(not path.is_symlink() and not is_junction(path), "数据路径不得为链接")


def check_public(value):
    if isinstance(value, dict):
        require(not set(value) & PRIVATE, "拆包输入必须已清除私有字段")
        if "id" in value:
            require(isinstance(value["id"], str) and re.fullmatch(r"[cw][0-9a-f]{12}", value["id"]),
                    "拆包输入必须使用公开标识")
        for child in value.values():
            check_public(child)
    elif isinstance(value, list):
        for child in value:
            check_public(child)
    elif isinstance(value, str):
        require(not LOCAL_PATH.search(value), "拆包输入不得包含本机路径")


def search_text(value):
    """Keep all public human text/numbers, including voices and skill details."""
    def leaves(item):
        if isinstance(item, dict):
            for child in item.values():
                yield from leaves(child)
        elif isinstance(item, list):
            for child in item:
                yield from leaves(child)
        elif isinstance(item, str):
            if item and not item.startswith("media/") and not LOCAL_PATH.search(item):
                yield item
        elif isinstance(item, (bool, int, float)):
            yield json.dumps(item, ensure_ascii=False)
    return "\n".join(dict.fromkeys(leaves(value)))


def index_character(character, *, legacy_effects=False):
    result = {key: character[key] for key in INDEX_FIELDS if key in character}
    if character.get("portraits"):
        result["portraits"] = [{key: portrait[key] for key in ("label", "url") if key in portrait}
                               for portrait in character["portraits"] if isinstance(portrait, dict)]
    if not result.get("icon") and character.get("portraits"):
        result["icon"] = character["portraits"][0].get("url")
    # Only the reader accepts older format-1 indexes. New bootstrap data leaves
    # effect text in the existing complete character and full-search chunks.
    if legacy_effects:
        result["leader"] = {"description": character.get("leader", {}).get("description", "")}
        result["abilities"] = [{key: ability[key] for key in ("name", "description") if key in ability}
                               for ability in character.get("abilities", [])]
    return result


def split_catalog(catalog):
    check_public(catalog)
    require(set(catalog) <= {"meta", "characters", "equipment", "equipmentMeta", "bossGuide"},
            "出现未声明的顶层数据，拒绝遗漏后继续拆包")
    characters = catalog["characters"]
    ids = [character["id"] for character in characters]
    require(ids and len(ids) == len(set(ids)) and all(CHARACTER_ID.fullmatch(cid) for cid in ids),
            "角色标识为空、重复或不是公开角色标识")
    require(not set(ids) & {public_id("c", cid) for cid in HIDDEN_CHARACTER_IDS}, "隐藏角色不得进入数据包")
    chunks = {"character:" + c["id"]: c for c in characters}
    equipment = {key: catalog[key] for key in ("equipment", "equipmentMeta") if key in catalog}
    if equipment:
        chunks["equipment"] = equipment
    if "bossGuide" in catalog:
        chunks["bossGuide"] = catalog["bossGuide"]
    chunks["search"] = {c["id"]: search_text(c) for c in characters}
    files, manifest = {}, {}
    for key, payload in chunks.items():
        raw = PREFIX.encode() + compact(key) + b"] = " + compact(payload) + b";\n"
        sha = digest(raw)
        url = f"data/{key.replace(':', '-')}-{sha[:16]}.js"
        files[url] = raw
        manifest[key] = {"url": url, "sha256": sha, "bytes": len(raw)}
    bootstrap = {"meta": catalog["meta"], "characters": [index_character(c) for c in characters],
                 "dataManifest": {"format": 1, "catalogSha256": digest(compact(catalog, sort_keys=True)),
                                  "chunks": manifest}}
    return bootstrap, files


def chunk_payload(raw, expected_key):
    text = raw.decode("utf-8")
    require(text.startswith(PREFIX), "数据包注册前缀不符合静态 JSON 契约")
    decoder = json.JSONDecoder()
    key, offset = decoder.raw_decode(text[len(PREFIX):])
    rest = text[len(PREFIX) + offset:]
    require(key == expected_key and rest.startswith("] = "), "数据包注册键与清单不同")
    value, offset = decoder.raw_decode(rest[4:])
    require(rest[4 + offset:].strip() == ";", "数据包含额外可执行内容")
    return value


def read_split_catalog(output: Path, bootstrap=None):
    """Verify every declared payload and reconstruct the exact public catalog."""
    output = Path(output)
    regular(output)
    regular(output / "data")
    if bootstrap is None:
        regular(output / "data.js")
        text = (output / "data.js").read_text(encoding="utf-8")
        require(text.startswith("window.WF_WIKI = ") and text.rstrip().endswith(";"), "首页数据包装无效")
        bootstrap = json.loads(text[len("window.WF_WIKI = "):].rstrip()[:-1])
    require(set(bootstrap) == {"meta", "characters", "dataManifest"}, "首页索引字段不符合分包契约")
    manifest = bootstrap["dataManifest"]
    require(manifest.get("format") == 1 and set(manifest) == {"format", "catalogSha256", "chunks"}, "数据清单格式不受支持")
    entries = manifest["chunks"]
    require(isinstance(entries, dict), "数据包清单不是映射")
    ids = [c["id"] for c in bootstrap["characters"]]
    expected = {"character:" + cid for cid in ids} | {"search"}
    require(expected <= set(entries) <= expected | {"equipment", "bossGuide"}, "数据包清单缺项或含未声明角色")
    parts = {}
    for key, entry in entries.items():
        require(set(entry) == {"url", "sha256", "bytes"}, "数据包条目字段错误")
        sha = entry["sha256"]
        require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha), "数据包 SHA256 无效")
        url = f"data/{key.replace(':', '-')}-{sha[:16]}.js"
        require(entry["url"] == url and re.fullmatch(r"data/(?:character-c[0-9a-f]{12}|equipment|bossGuide|search)-[0-9a-f]{16}\.js", url),
                "数据包路径越界或名称与哈希不同")
        path = output / url
        regular(path)
        raw = path.read_bytes()
        require(len(raw) == entry["bytes"] and digest(raw) == sha, "数据包哈希或大小与清单不同")
        parts[key] = chunk_payload(raw, key)
    characters = [parts["character:" + cid] for cid in ids]
    require(all(c.get("id") == cid for c, cid in zip(characters, ids)), "详情包角色与索引不符")
    require(all(brief == index_character(c) or brief == index_character(c, legacy_effects=True)
                for c, brief in zip(characters, bootstrap["characters"])), "首页摘要与详情资料不一致")
    require(parts["search"] == {c["id"]: search_text(c) for c in characters}, "全文检索内容与详情不同")
    catalog = {"meta": bootstrap["meta"], "characters": characters}
    if "equipment" in parts:
        require(isinstance(parts["equipment"], dict) and set(parts["equipment"]) <= {"equipment", "equipmentMeta"}, "装备包结构错误")
        catalog.update(parts["equipment"])
    if "bossGuide" in parts:
        catalog["bossGuide"] = parts["bossGuide"]
    require(digest(compact(catalog, sort_keys=True)) == manifest["catalogSha256"], "完整数据摘要哈希不同")
    check_public(catalog)
    # Reuse roster/exclusion checks, without trusting a caller-supplied manifest.
    split_catalog(catalog)
    return catalog


def atomic_write(path, raw):
    regular(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".wiki-data-", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
    try:
        regular(path)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_split_public(output: Path, catalog: dict):
    """Write immutable hashed chunks first and atomically switch data.js last."""
    output = Path(output)
    regular(output)
    require(output.is_dir(), "拆包输出目录不存在")
    regular(output / "data")
    regular(output / "data.js")
    source = output / "data.json"
    regular(source)
    original = source.read_bytes() if source.exists() else None
    if original is not None:
        require(json.loads(original) == catalog, "拆包输入与完整 data.json 不同")
    bootstrap, files = split_catalog(catalog)
    (output / "data").mkdir(exist_ok=True)
    for url, raw in files.items():
        path = output / url
        regular(path)
        if path.exists():
            require(path.is_file() and path.read_bytes() == raw, "已有同名数据包内容不同")
        else:
            atomic_write(path, raw)
    require(read_split_catalog(output, bootstrap) == catalog, "分包回读与完整资料不同")
    if original is not None:
        require(source.read_bytes() == original, "拆包期间完整 data.json 发生变化")
    script = b"window.WF_WIKI = " + compact(bootstrap) + b";\n"
    atomic_write(output / "data.js", script)
    return {"format": 1, "indexBytes": len(script), "chunks": len(files),
            "chunkBytes": sum(map(len, files.values())), "catalogSha256": bootstrap["dataManifest"]["catalogSha256"]}


def resplit_existing(output: Path):
    output = Path(output)
    regular(output)
    marker = output / ".wf-wiki-export.json"
    regular(marker)
    receipt = json.loads(marker.read_text(encoding="utf-8"))
    require(receipt.get("generator") == "wf_wiki" and receipt.get("complete") is True,
            "仅可拆分已完成的 Wiki 导出")
    regular(output / "data.json")
    catalog = json.loads((output / "data.json").read_text(encoding="utf-8"))
    require(receipt.get("version") == catalog["meta"].get("version")
            and receipt.get("characters") == len(catalog["characters"]), "完整资料与导出回执不同")
    return write_split_public(output, catalog)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="仅从既有 public data.json 拆包，不读取游戏或转换媒体")
    parser.add_argument("--resplit", type=Path, required=True)
    print(json.dumps(resplit_existing(parser.parse_args().resplit), ensure_ascii=False, indent=2))

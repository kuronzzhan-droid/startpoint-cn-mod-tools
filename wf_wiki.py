'Export the current MOD character catalog as a portable, read-only website.\n\npython -X utf8 mod-tools/wf_wiki.py --output ${WF_ROOT}/out/MOD角色Wiki/site\n'
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import wf_mod_tool as core
import wf_publish
from wf_wiki_media import WikiMedia
from wf_wiki_media import digest
from wf_wiki_paths import is_junction

HERE = Path(__file__).resolve().parent
MARKER = ".wf-wiki-export.json"


def prepare_output(output: Path, repo: Path, store: Path) -> Path:
    output = output.resolve()
    for protected in (repo.resolve(), store.resolve().parent):
        if output == protected or output in protected.parents:
            raise ValueError("输出路径不得覆盖仓库、数据目录或其上级目录")
    if output.is_relative_to(store.resolve().parent):
        raise ValueError("输出路径不得位于游戏数据目录")
    if output.is_relative_to(repo.resolve()) and not output.is_relative_to(repo.resolve() / "work"):
        raise ValueError("仓库内导出仅允许 work/；建议放到仓库外")
    if output.exists() and any(output.iterdir()):
        children = list(output.iterdir())
        if any(path.is_symlink() or is_junction(path) for path in children):
            raise ValueError("输出目录含链接或目录联接，请选择独立目录")
        marker = output / MARKER
        try:
            identity = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            identity = None
        if not isinstance(identity, dict) or identity.get("generator") != "wf_wiki":
            raise ValueError("输出目录非空且不是本工具产物，请选择新目录")
        media = output / "media"
        if media.is_dir() and any(path.is_symlink() or is_junction(path) for path in media.iterdir()):
            raise ValueError("媒体目录含链接或目录联接，请选择独立目录")
    output.mkdir(parents=True, exist_ok=True)
    (output / MARKER).write_text('{"generator":"wf_wiki","complete":false}\n', encoding="utf-8")
    return output


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_catalog(catalog: dict, output: Path) -> None:
    characters = catalog["characters"]
    ids = [str(character["id"]) for character in characters]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("角色目录为空或存在重复 ID")
    for character in characters:
        urls = [character.get("icon")]
        urls.extend(item.get("url") for item in character.get("portraits", []))
        urls.extend(item.get("audio") for item in character.get("voices", []))
        for url in filter(None, urls):
            path = (output / url).resolve()
            if not url.startswith("media/") or not path.is_relative_to(output.resolve() / "media"):
                raise ValueError("媒体链接必须指向导出目录内的 media 文件夹")
            if not path.is_file():
                raise ValueError(f"角色 {character['id']} 存在失效媒体链接：{url}")
    def validate_links(value):
        if isinstance(value, dict):
            for child in value.values():
                validate_links(child)
        elif isinstance(value, list):
            for child in value:
                validate_links(child)
        elif isinstance(value, str) and value.startswith("media/"):
            path = (output / value).resolve()
            if not path.is_relative_to(output.resolve() / "media") or not path.is_file():
                raise ValueError("附加资料存在失效媒体链接")
    validate_links(catalog)


def verify_table_sources(meta: dict, voice_summary: dict, store: Path) -> None:
    hashes = dict(meta.get("sourceHashes", {}))
    hashes.update(voice_summary.get("sourceHashes", {}))
    for logical, expected in hashes.items():
        path = core.table_path(store, logical)
        if not path.is_file() or digest(path.read_bytes()) != expected:
            raise RuntimeError(f"导出期间数据源变化：{logical}，请重新导出")
    for logical in meta.get("sourceMissing", []):
        if core.table_path(store, logical).exists():
            raise RuntimeError(f"导出期间出现新的覆盖数据：{logical}，请重新导出")


def merge_sources(meta: dict, extra: dict) -> None:
    for group in ("sourceHashes", "sourceFiles"):
        hashes = meta.setdefault(group, {})
        for logical, expected in extra.get(group, {}).items():
            if logical in hashes and hashes[logical] != expected:
                raise RuntimeError(f"导出各模块读取到不同版本：{logical}，请重新导出")
            hashes[logical] = expected
    missing = set(meta.get("sourceMissing", [])) | set(extra.get("sourceMissing", []))
    if missing & set(meta.get("sourceHashes", {})):
        raise RuntimeError("导出期间覆盖数据从缺失变为存在，请重新导出")
    meta["sourceMissing"] = sorted(missing)


def verify_source_files(meta: dict, repo: Path) -> None:
    for relative, expected in meta.get("sourceFiles", {}).items():
        path = (repo / relative).resolve()
        if not path.is_relative_to(repo.resolve()) or not path.is_file() or digest(path.read_bytes()) != expected:
            raise RuntimeError(f"导出期间本地来源文件变化：{relative}，请重新导出")


def export(output: Path, *, legacy_data: Path | None = None, external_character: Path | None = None) -> dict:
    from wf_wiki_catalog import build_catalog
    from wf_wiki_voice import export_voices
    from wf_wiki_ui_assets import export_ui_assets
    from wf_wiki_equipment import build_equipment_catalog
    from wf_wiki_public import public_catalog
    from wf_wiki_pixels import export_pixels
    from wf_wiki_variants import write_character_variants

    repo = HERE.parent
    store = core.resolve_active_store()
    version_before = wf_publish.current_max_version()
    pending = HERE / "work/sync_pending.json"
    pending_before = pending.read_bytes() if pending.exists() else None
    if pending_before and json.loads(pending_before):
        raise RuntimeError("当前存在待发布修改；请待发布结束后导出，避免把候选标为生效版")
    output = prepare_output(output, repo, store)
    media = WikiMedia(store, output)
    print("正在读取角色、技能与能力数据……", flush=True)
    catalog = build_catalog(repo, media)
    if legacy_data:
        from wf_wiki_legacy import enrich_legacy_reference
        enrich_legacy_reference(catalog, legacy_data)
    catalog["meta"]["uiAssets"] = export_ui_assets(media)
    print("正在读取武器与强化资料……", flush=True)
    equipment = build_equipment_catalog(repo, media)
    catalog["equipment"] = equipment["equipment"]
    catalog["equipmentMeta"] = equipment["meta"]
    merge_sources(catalog["meta"], equipment["meta"])
    if (HERE / "wf_wiki_boss_guide.py").is_file():
        from wf_wiki_boss_guide import build_boss_guide
        catalog["bossGuide"] = build_boss_guide(repo, media)
        merge_sources(catalog["meta"], catalog["bossGuide"].get("meta", {}))
    print(f"正在匹配 {len(catalog['characters'])} 个角色的语音与字幕……", flush=True)
    voice_summary = export_voices(repo, catalog["characters"], media)
    if external_character:
        from wf_wiki_external_character import augment_catalog
        augment_catalog(repo, media, catalog, external_character)
        for key, value in catalog["meta"].get("externalVoiceCounts", {}).items():
            if isinstance(value, int):
                voice_summary[key] = voice_summary.get(key, 0) + value
    media.verify_sources()
    verify_table_sources(catalog["meta"], voice_summary, store)
    verify_source_files(catalog["meta"], repo)
    if legacy_data and digest(legacy_data.read_bytes()) != catalog["meta"]["legacyReference"]["sha256"]:
        raise RuntimeError("导出期间旧 Wiki 参考文件发生变化，请重新导出")
    validate_catalog(catalog, output)
    version_after = wf_publish.current_max_version()
    pending_after = pending.read_bytes() if pending.exists() else None
    if version_before != version_after or pending_before != pending_after:
        raise RuntimeError("导出期间发布状态改变，请重新导出")
    catalog["meta"].update({
        "version": version_after,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "voiceCounts": voice_summary, "media": media.summary(),
        "snapshotNote": "本地数据快照；更新游戏数据后需重新导出。语音取当前资源，字幕来源逐条标注。",
    })
    catalog = public_catalog(catalog)
    print("正在生成角色像素动作预览……", flush=True)
    pixels = export_pixels(repo, output, catalog=catalog, store=store, external_package=external_character)
    variants = write_character_variants(repo, output, catalog, store=store)
    if version_after != wf_publish.current_max_version() or pending_after != (pending.read_bytes() if pending.exists() else None):
        raise RuntimeError("像素导出期间发布状态改变，请重新导出")
    write_json(output / "data.json", catalog)
    from wf_wiki_data import write_split_public
    data_summary = write_split_public(output, catalog)
    from wf_wiki_dungeons import export_dungeons
    export_dungeons(repo, output, store=store)
    for path in (HERE / "wiki").iterdir():
        if path.suffix in {".html", ".css", ".js"} or path.name in {
            "brand-logo.png", "reborn-group-1.jpg", "reborn-group-2.jpg", "wiki-share-poster.png", "_headers",
        }:
            shutil.copyfile(path, output / path.name)
    write_json(output / "media-manifest.json", media.entries)
    (output / "打开角色Wiki.bat").write_bytes(b'@echo off\r\nstart "" "%~dp0index.html"\r\n')
    (output / "使用说明.txt").write_text(
        "世界弹射 MOD 角色资料站\n\n双击 index.html 或 打开角色Wiki.bat 即可浏览，无需联网。\n"
        "保留同目录下的 data.js、data 数据包文件夹、CSS、JavaScript 和 media 文件夹。\n"
        "搜索支持名字、别名、主题、技能与能力关键词；详情页面地址可保留角色定位。\n"
        "角色数据是导出时的本地快照。普通/进化技能分别展示；属性面板保留数值口径。\n"
        "语音逐条显示当前可用的日文原文和中文台词；缺失项不代表音频不存在。\n"
        "更新资料：在仓库执行 python -X utf8 mod-tools/wf_wiki.py --output <此目录>\n",
        encoding="utf-8")
    receipt = {"generator": "wf_wiki", "complete": True,
               "version": version_after, "characters": len(catalog["characters"]),
               "voices": voice_summary, "media": media.summary(), "data": data_summary,
               "pixels": pixels["summary"], "variants": variants}
    write_json(output / MARKER, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="只读导出 MOD 角色 Wiki（不发布、不改游戏数据）")
    parser.add_argument("--output", type=Path, required=True, help="独立产物目录，推荐放在仓库外")
    parser.add_argument("--legacy-data", type=Path, help="作者提供的旧 Wiki localApi.json，仅作标记参考")
    parser.add_argument("--external-character", type=Path, help="作者指定的独立角色包，仅为 Wiki 读取")
    args = parser.parse_args()
    result = export(args.output, legacy_data=args.legacy_data, external_character=args.external_character)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"网页：{args.output.resolve() / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

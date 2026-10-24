"""Add the explicitly selected 2026-09-27 Moon Fox package to a Wiki snapshot.

Call after live export_voices: the independent package must not be mistaken for
an installed character, nor have its audio overwritten by a later live scan.
"""
from __future__ import annotations

from pathlib import Path

from wf_wiki_catalog import character_entry
from wf_wiki_external_source import PackageFiles, PackageMedia, PackageSource
from wf_wiki_external_voice import package_voices

CHARACTER_ID = "159991"
CODE = "cnmod_inaho_midautumn"
PACKAGE_ID = "inaho-midautumn-20260927"
SOURCE_NOTE = ("灰服独立角色资料，本机快照未含。资料版本：2026-09-27 作者调整版；"
               "不代表此角色已在本机安装或经过实机验证。")


def augment_catalog(repo: Path, media, catalog: dict, package_path: Path | None = None) -> list[dict]:
    """Append one record, update counts, return added records; all sources read-only.

    Package hashes are checked against its manifest and registered with media's
    final drift check. Audit fields contain logical names and hashes, no local
    package path. Existing live characters always take precedence.
    """
    if any(str(character["id"]) == CHARACTER_ID for character in catalog["characters"]):
        return []
    package = package_path or Path(repo) / "work/character_packs" / PACKAGE_ID / "package"
    files = PackageFiles(package, media)
    manifest = files.manifest
    if (str(manifest.get("character_id")) != CHARACTER_ID
            or manifest.get("code_name") != CODE or manifest.get("package_id") != PACKAGE_ID):
        raise ValueError("外部资料不是已选定的 2026-09-27 月狐狸角色包")
    source = PackageSource(repo, media.store, files)
    own_media = PackageMedia(media, files)
    row = source.table("character").get(CHARACTER_ID, [[]])[0]
    if not row or row[0] != CODE or row[3] != "4":
        raise ValueError("外部月狐狸角色身份或光属性与选定资料不符")
    character = character_entry(source, CHARACTER_ID, None, own_media)
    character.update({"origin": "灰服独立角色资料", "category": "原创与变体",
                      "categorySource": "作者明确指定的外部独立角色资料",
                      "aliases": ["月饼狐", "月狐狸", "中秋稻穗"],
                      "theme": "中秋", "themes": ["中秋"], "editorNote": SOURCE_NOTE,
                      "external": True, "sourceVersion": "2026-09-27 作者调整版",
                      "runtimeVerified": False})
    voices = package_voices(Path(repo), character, source, own_media)
    source.verify_unchanged()
    character["sources"].append({"label": "2026-09-27 外部独立角色包清单",
                                  "sha256": files.manifest_hash})
    catalog["characters"].append(character)
    meta = catalog["meta"]
    counts = meta.setdefault("counts", {})
    for key in ("total", "newMod", "external"):
        counts[key] = counts.get(key, 0) + 1
    categories = meta.setdefault("categoryCounts", {})
    categories["原创与变体"] = categories.get("原创与变体", 0) + 1
    meta["externalVoiceCounts"] = voices
    meta["externalNote"] = SOURCE_NOTE
    meta.setdefault("sources", []).append({"label": "2026-09-27 月狐狸独立资料",
                                            "sha256": files.manifest_hash})
    return [character]

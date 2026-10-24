"""Read only visible Wiki characters from live resources or the approved Moon Fox package."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import wf_assets
from wf_wiki_catalog_source import WikiSource
from wf_wiki_categories import HIDDEN_CHARACTER_IDS
from wf_wiki_external_character import CHARACTER_ID, CODE, PACKAGE_ID
from wf_wiki_external_source import PackageFiles
from wf_wiki_media import WikiMedia
from wf_wiki_public import public_id

BASE_FILES = ("sprite_sheet.png", "sprite_sheet.atlas.amf3.deflate",
              "pixelart.frame.amf3.deflate", "pixelart.timeline.amf3.deflate")
SPECIAL_FILES = ("special_sprite_sheet.png", "special_sprite_sheet.atlas.amf3.deflate",
                 "special.frame.amf3.deflate", "special.timeline.amf3.deflate")


class PixelSources:
    def __init__(self, repo, store, output, external_package=None):
        self.source = WikiSource(Path(repo), Path(store))
        self.media = WikiMedia(Path(store), Path(output))
        self.mapping = {public_id("c", cid): (cid, row[0][0])
                        for cid, row in self.source.table("character").items()
                        if cid not in HIDDEN_CHARACTER_IDS and row and row[0]}
        self.external = Path(external_package) if external_package else Path(repo) / "work/character_packs" / PACKAGE_ID / "package"
        self.package = None
        self.resolved = {}

    def read(self, public):
        if not re.fullmatch(r"c[0-9a-f]{12}", public):
            raise ValueError("像素索引必须使用公开角色标识")
        files = None
        if public in self.mapping:
            _, code = self.mapping[public]
        elif public == public_id("c", CHARACTER_ID):
            if not self.package:
                self.package = PackageFiles(self.external, self.media)
                manifest = self.package.manifest
                if (str(manifest.get("character_id")), manifest.get("code_name"), manifest.get("package_id")) != (CHARACTER_ID, CODE, PACKAGE_ID):
                    raise ValueError("独立像素资料不是已收录的月狐狸包")
            files, code = self.package, CODE
        else:
            raise ValueError("公开角色没有对应的可信像素来源")
        raw = {}
        for filename in BASE_FILES + SPECIAL_FILES:
            logical = f"character/{code}/pixelart/{filename}"
            if files:
                value = next((value for tier in ("common", "medium", "android")
                              if (value := files.read(logical, tier)) is not None), None)
            else:
                found = wf_assets.locate(self.media.store, logical)
                self.resolved[logical] = found[1] if found else None
                value = self.media._read(logical) if found else None
            if value is not None:
                raw[filename] = value
        if any(name not in raw for name in BASE_FILES):
            raise ValueError("角色缺少基础像素资源")
        return raw

    def verify(self):
        self.source.verify_unchanged()
        self.media.verify_sources()
        for logical, previous in self.resolved.items():
            found = wf_assets.locate(self.media.store, logical)
            if (found[1] if found else None) != previous:
                raise RuntimeError("导出期间像素资源路径发生变化，请重新导出")


def source_revision(raw, renderer):
    fingerprints = [(name, hashlib.sha256(value).hexdigest()) for name, value in sorted(raw.items())]
    return hashlib.sha256(json.dumps([renderer, fingerprints], separators=(",", ":")).encode()).hexdigest()

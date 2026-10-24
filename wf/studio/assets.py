"""「全套资源」: every asset a character owns in the layered view (read-only).

Asset paths are salted hashes in the CDN, so they cannot be listed directly.
Candidates come from (1) the recovered path list (every ``character/*/<suffix>``
seen for any character, applied to this code name, plus entries that mention
the code name), (2) the fixed per-character template matrix of
``wf_character_requirements``, (3) ``character_speech`` voice registrations and
(4) effect directories referenced by the character's skill / ability DSL.
Each candidate is probed in the view; only present items and *expected* or
*referenced* missing items are listed.
"""
from __future__ import annotations

import os
import re
import struct
import threading
import zlib
from pathlib import Path

import wf_assets
import wf_mod_tool as core
from wf.paths import path
from wf_character_requirements import (
    MasterAssetReference, char_asset_requirements, extract_master_asset_references, required_asset_paths,
)

from .source import StudioSource, edge_versions

ROOTS = ("upload", "medium_upload", "android_upload")
ROOT_LABEL = {"upload": "通用", "medium_upload": "大图", "android_upload": "安卓"}
SPEECH_LOGICAL = "master/character/character_speech.orderedmap"
SPEECH_KIND = {"0": "主页", "1": "觉醒", "2": "入队"}
SPEECH_CONSTRAINT = {"0": "仅觉醒前", "1": "仅觉醒后", "2": "始终", "": ""}
GROUPS = (
    ("portrait", "立绘"), ("ui", "UI 图标 / 头像 / 卡面裁剪"), ("pixel", "像素"),
    ("cutin", "技能 cutin"), ("effect", "特效"), ("voice", "语音"), ("other", "其它"),
)
# Element column (character c3, 0-based fire..dark) → internal element for effects.
_ELEMENTS = {str(i): i for i in range(7)}
AVATAR_ORDER = ("ui/square_{form}.png", "ui/thumbnail_{form}.png", "ui/square_132_132_{form}.png",
                "ui/square_round_136_136_{form}.png")


def png_size(data: bytes) -> tuple[int, int] | None:
    data = wf_assets.png_decode(data)
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    return None


def group_for(logical: str, code: str) -> str:
    rel = logical[len(f"character/{code}/"):] if logical.startswith(f"character/{code}/") else None
    if rel is None:
        if logical.startswith("battle/effect/"):
            return "effect"
        if logical.startswith("bgm/"):
            return "voice"
        return "other"
    if rel.startswith("ui/full_shot"):
        return "portrait"
    if rel.startswith("ui/skill_cutin"):
        return "cutin"
    if rel.startswith("ui/story/"):
        return "other"
    if rel.startswith("ui/"):
        return "ui"
    if rel.startswith("pixelart/"):
        return "pixel"
    if rel.startswith("voice/"):
        return "voice"
    return "other"


def media_type(logical: str) -> str:
    if logical.endswith(".png"):
        return "image"
    if logical.endswith(".mp3"):
        return "audio"
    return "data"


class AssetIndex:
    def __init__(self, source: StudioSource):
        self.source = source
        self._lock = threading.Lock()
        self._store: set[str] | None = None
        self._suffixes: list[str] | None = None
        self._pathlist: list[str] | None = None
        self._cache: dict[str, dict] = {}
        self._avatar: dict[tuple[str, str], tuple[bytes, str] | None] = {}

    # -- existence -------------------------------------------------------
    def _store_names(self) -> dict[str, set[str]]:
        with self._lock:
            if self._store is None:
                stores: dict[str, set[str]] = {}
                base = Path(self.source.view.store).parent
                for root in ROOTS:
                    names: set[str] = set()
                    directory = base / root
                    if directory.is_dir():
                        with os.scandir(directory) as tops:
                            for top in tops:
                                if top.is_dir():
                                    with os.scandir(top.path) as files:
                                        names.update(f"{top.name}/{f.name}" for f in files)
                    stores[root] = names
                self._store = stores
            return self._store

    def locate_all(self, logical: str) -> list[tuple[str, str, str]]:
        """[(root, member, layer)] for every CDN root that provides the path."""
        digest = core.sha1_path(logical)
        rel = digest[:2] + "/" + digest[2:]
        found = []
        stores = self._store_names()
        for root in ROOTS:
            name = f"production/{root}/{rel}"
            archive = self.source.view.index.get(name)
            if archive is not None:
                found.append((root, name, Path(archive).name))
            elif rel in stores.get(root, ()):
                found.append((root, name, "store131"))
        return found

    def locate(self, logical: str) -> str | None:
        found = self.locate_all(logical)
        return found[0][2] if found else None

    def read(self, logical: str) -> bytes | None:
        found = self.locate_all(logical)
        if not found:
            return None
        return self.source.view.read_member(found[0][1])[0]

    def _load_pathlist(self):
        with self._lock:
            if self._pathlist is None:
                location = path("pathlist")
                lines = location.read_text("utf-8").splitlines() if location.is_file() else []
                self._pathlist = [line.strip() for line in lines if line.strip()]
                suffixes = set()
                for line in self._pathlist:
                    parts = line.split("/", 2)
                    if parts[0] == "character" and len(parts) == 3:
                        suffixes.add(parts[2])
                self._suffixes = sorted(suffixes)
        return self._pathlist, self._suffixes

    # -- metadata --------------------------------------------------------
    def describe_item(self, logical: str, layer: str | None) -> dict:
        item = {"path": logical, "layer": layer, "layerLabel": layer_label(layer), "media": media_type(logical)}
        if layer is None:
            return item
        found = self.locate_all(logical)
        item["roots"] = [{"root": ROOT_LABEL[r], "layer": l, "layerLabel": layer_label(l)} for r, _, l in found]
        raw = self.source.view.read_member(found[0][1])[0]
        if raw is not None:
            item["size"] = len(raw)
            item["official"] = self.official_state(logical, raw)
            if logical.endswith(".png"):
                dims = png_size(raw)
                if dims:
                    item["width"], item["height"] = dims
        return item

    def official_state(self, logical: str, raw: bytes) -> str:
        baseline = self.source._official()
        if baseline is None:
            return "未比对"
        digest = core.sha1_path(logical)
        rel = digest[:2] + "/" + digest[2:]
        crc = zlib.crc32(raw) & 0xFFFFFFFF
        found = False
        for root in ("common", "medium", "android"):
            try:
                identity = baseline.identity(root, rel)
            except Exception:  # noqa: BLE001
                continue
            if identity is None:
                continue
            found = True
            if tuple(identity) == (crc, len(raw)):
                return "与官方一致"
        return "与官方不同" if found else "官方无此文件"

    # -- references ------------------------------------------------------
    def speech_rows(self, cid: str) -> list[list[str]]:
        raw = self.source.raw(SPEECH_LOGICAL)
        if raw is None:
            return []
        table = core.read_orderedmap_raw_rows_from_bytes(raw, SPEECH_LOGICAL)
        for key, value in zip(table.keys, table.rows):
            if key == cid:
                try:
                    text = zlib.decompress(value).decode("utf-8")
                except zlib.error:
                    text = value.decode("utf-8", "replace")
                return core.read_csv_lines(text)
        return []

    def effect_references(self, row: list[str]) -> list[MasterAssetReference]:
        programs = set()
        for level, rows in self.source.table("skill").get(row[8], {}).items():
            if rows and len(rows[0]) > 7 and rows[0][7] not in ("", "(None)"):
                programs.add(rows[0][7])
        switch_key = row[14] if len(row) > 14 else ""
        for level, rows in self.source.table("switched").get(switch_key, {}).items():
            if rows and rows[0] and rows[0][0] not in ("", "(None)"):
                programs.add(rows[0][0])
        ability = self.source.table("ability")
        for key in row[19:25]:
            for line in ability.get(key, []):
                for value in line:
                    if value.startswith("battle/") and "/" in value[7:]:
                        programs.add(value)
        trees = {}
        for program in programs:
            logical = program if program.endswith(".amf3.deflate") else program + ".action.dsl.amf3.deflate"
            try:
                tree = self.source.tree(logical)
            except Exception:  # noqa: BLE001 - unreadable DSL is reported as missing effects only
                tree = None
            if tree is not None:
                trees[logical] = tree
        element = _ELEMENTS.get(row[3]) if len(row) > 3 else None
        refs = extract_master_asset_references({}, None, trees, context_element=element)
        return [r for r in refs if r.kind == "skill_effect"]

    # -- main ------------------------------------------------------------
    def character(self, cid: str) -> dict | None:
        if cid in self._cache:
            return self._cache[cid]
        rows = self.source.table("character").get(cid)
        if not rows or not rows[0]:
            return None
        row = rows[0]
        code = row[0]
        prefix = f"character/{code}/"
        pathlist, suffixes = self._load_pathlist()
        items: dict[str, dict] = {}

        def add(logical: str, *, expected: str | None = None, note: str = "", text: str = "", tag: str = ""):
            entry = items.get(logical)
            if entry is None:
                layer = self.locate(logical)
                entry = {**self.describe_item(logical, layer), "group": group_for(logical, code),
                         "expected": None, "notes": [], "text": "", "tag": ""}
                items[logical] = entry
            if expected and entry["expected"] in (None, "optional"):
                entry["expected"] = expected
            if note and note not in entry["notes"]:
                entry["notes"].append(note)
            if text:
                entry["text"] = text
            if tag:
                entry["tag"] = tag

        for suffix in suffixes:
            logical = prefix + suffix
            if self.locate(logical):
                add(logical)
        needle = re.compile(rf"(?<![a-z0-9]){re.escape(code)}(?![a-z0-9])")
        for line in pathlist:
            if not line.startswith(prefix) and needle.search(line) and self.locate(line):
                add(line)
        for requirement in char_asset_requirements(code):
            expected = "required" if requirement.category == "required" else "optional"
            add(requirement.logical_path, expected=expected, note=requirement.requirement)

        speech = []
        for number, line in enumerate(self.speech_rows(cid), 1):
            cells = line + [""] * (5 - len(line))
            kind, constraint, evo, subtitle, voice = cells[:5]
            entry = {"row": number, "kind": SPEECH_KIND.get(kind, kind),
                     "constraint": SPEECH_CONSTRAINT.get(constraint, constraint), "evoLevel": evo,
                     "text": subtitle, "voice": voice}
            if voice and voice != "(None)":
                logical = f"{prefix}voice/{voice}.mp3"
                entry["path"] = logical
                add(logical, expected="referenced", note=f"character_speech 第 {number} 行引用",
                    text=subtitle, tag=entry["kind"])
                entry["present"] = items[logical]["layer"] is not None
            speech.append(entry)

        for reference in self.effect_references(row):
            for logical in required_asset_paths(reference):
                add(logical, expected="referenced", note="技能/能力 DSL 引用：" + Path(reference.source).name)
            end = reference.value + "_end"
            for logical in (end + ".parts.amf3.deflate", end + ".timeline.amf3.deflate"):
                if self.locate(logical):
                    add(logical, note="同目录收尾段")

        listed = [item for item in items.values()
                  if item["layer"] is not None or item["expected"] in ("required", "referenced")]
        for item in listed:
            if item["layer"] is None:
                item["status"] = "引用但缺失" if item["expected"] == "referenced" else "缺失"
            else:
                item["status"] = "存在"
        cutins = []
        for form in ("0", "1"):
            png = items.get(f"{prefix}ui/skill_cutin_{form}.png")
            atf = items.get(f"{prefix}ui/skill_cutin_{form}.atf.deflate")
            cutins.append({"form": form, "png": bool(png and png["layer"]), "atf": bool(atf and atf["layer"]),
                           "pngLayer": png and png["layer"], "atfLayer": atf and atf["layer"]})
        groups = []
        for gid, label in GROUPS:
            members = sorted((i for i in listed if i["group"] == gid), key=lambda i: i["path"])
            groups.append({"id": gid, "label": label, "items": members,
                           "present": sum(1 for i in members if i["layer"]),
                           "missing": sum(1 for i in members if not i["layer"])})
        result = {"characterId": cid, "code": code, "groups": groups, "speech": speech, "cutins": cutins,
                  "total": len(listed),
                  "note": ("资源路径是加盐哈希，无法直接枚举：候选来自恢复路径表、角色模板矩阵、character_speech "
                           "与技能 DSL 引用，逐条在当前视图中探测。不在这些来源里的文件不会列出。")}
        self._cache[cid] = result
        return result

    def avatar(self, cid: str, form: str) -> tuple[bytes, str] | None:
        key = cid, form
        if key in self._avatar:
            return self._avatar[key]
        rows = self.source.table("character").get(cid)
        result = None
        if rows and rows[0]:
            code = rows[0][0]
            for pattern in AVATAR_ORDER:
                logical = f"character/{code}/" + pattern.format(form=form)
                raw = self.read(logical)
                if raw is not None:
                    result = (wf_assets.png_decode(raw), logical)
                    break
        self._avatar[key] = result
        return result

    def file(self, logical: str) -> tuple[bytes, str] | None:
        if ".." in logical.split("/") or logical.startswith("/"):
            return None
        raw = self.read(logical)
        if raw is None:
            return None
        if logical.endswith(".png"):
            return wf_assets.png_decode(raw), "image/png"
        if logical.endswith(".mp3"):
            return raw, "audio/mpeg"
        return raw, "application/octet-stream"


def layer_label(layer: str | None) -> str:
    if layer is None:
        return "缺失"
    if layer == "store131":
        return "store131 基底"
    versions = edge_versions(layer)
    if versions:
        tag = layer.split("-", 4)[-1].removesuffix(".zip") if layer.count("-") >= 4 else layer
        return f"补丁 1.4.{versions[0]}→1.4.{versions[1]} · {tag}"
    return layer


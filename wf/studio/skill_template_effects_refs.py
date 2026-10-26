"""Read-only native effect dependency discovery and flatomo shape checks."""
from __future__ import annotations

import math
import re

from .deliver_media import tree
from .drafts import DraftError

PREFIX = "battle/effect/"
PATH = re.compile(r"battle/effect/(?:[A-Za-z0-9_$-]+/)+[A-Za-z0-9_$-]+\Z")
SUFFIXES = (".parts.amf3.deflate", ".frame.amf3.deflate", ".timeline.amf3.deflate")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def effect_refs(value):
    """Find animation base paths, excluding atlas subtextures and sheet paths."""
    result = set()
    for path in _strings(value):
        if not path.startswith(PREFIX) or "/.gen/" in path:
            continue
        if path.endswith((".png", ".atlas.amf3.deflate", ".atf.deflate")):
            continue
        for suffix in SUFFIXES:
            path = path.removesuffix(suffix)
        if not PATH.fullmatch(path):
            raise DraftError(f"特效逻辑路径无效：{path}")
        result.add(path)
    return sorted(result)


def discover(pack, requested):
    groups, metadata, seen = {}, {}, set()
    queue = list(requested)
    while queue:
        effect = queue.pop(0)
        if effect in seen:
            continue
        seen.add(effect)
        if len(seen) > 256:
            raise DraftError("单个技能的特效依赖超过 256 项")
        directory, _, name = effect.rpartition("/")
        groups.setdefault(directory, set()).add(name)
        found = []
        for suffix in SUFFIXES:
            logical = effect + suffix
            raw = pack.read("common", logical, required=suffix == SUFFIXES[2])
            if raw is None:
                continue
            value = tree(raw)
            if not isinstance(value, dict):
                raise DraftError(f"flatomo 元数据需要对象：{logical}")
            found.append(suffix)
            metadata[logical] = value
            dependencies = {key: item for key, item in value.items() if key != "sounds"}
            queue.extend(effect_refs(dependencies))
            if suffix == SUFFIXES[0] and value.get("m"):
                clips = value["m"]
                if not isinstance(clips, list) or any(not effect_refs(item) for item in clips):
                    raise DraftError(f"flatomo MovieClip 依赖无法解析，不允许遗漏：{effect}")
            if suffix == SUFFIXES[2]:
                _sounds(pack, value, effect)
        if not any(suffix in found for suffix in SUFFIXES[:2]):
            raise DraftError(f"特效缺少 parts/frame 动画主体：{effect}")
    return groups, metadata


def _sounds(pack, timeline, effect):
    sounds = timeline.get("sounds", [])
    if not isinstance(sounds, list):
        raise DraftError(f"特效 sounds 需要数组：{effect}")
    for sound in sounds:
        path = sound.get("path") if isinstance(sound, dict) else None
        if not isinstance(path, str) or not path or ".." in path.split("/") or "\\" in path:
            raise DraftError(f"特效音效路径无效：{effect}")
        logical = path if path.endswith(".mp3") else path + ".mp3"
        pack.read("common", logical)


def validate_atlas(atlas, image):
    if not isinstance(atlas, list) or not atlas:
        raise DraftError("特效 atlas 必须为非空记录数组")
    names = set()
    for record in atlas:
        if not isinstance(record, dict) or not isinstance(record.get("n"), str):
            raise DraftError("特效 atlas 记录缺少纹理名称")
        if record["n"] in names:
            raise DraftError("特效 atlas 纹理名称重复")
        names.add(record["n"])
        coords = [record.get(key) for key in ("x", "y", "w", "h")]
        if any(type(value) not in (int, float) or not math.isfinite(value) or int(value) != value for value in coords):
            raise DraftError("特效 atlas 坐标需要整数")
        x, y, w, h = coords
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > image.width or y + h > image.height:
            raise DraftError("特效 atlas 纹理区域超出 PNG")


def validate_metadata(effect, metadata, atlas):
    names = {record["n"] for record in atlas}
    parts = metadata.get(effect + SUFFIXES[0])
    if parts is not None:
        images = parts.get("i", [])
        if not isinstance(images, list) or any(not isinstance(item, dict) or item.get("p") not in names for item in images):
            raise DraftError(f"特效 parts 存在 atlas 无法解析的纹理：{effect}")
        if not isinstance(parts.get("g"), list) or not parts["g"]:
            raise DraftError(f"特效 parts 缺少动画组：{effect}")
    frame = metadata.get(effect + SUFFIXES[1])
    if frame is not None:
        prefix = frame.get("name")
        if not isinstance(prefix, str) or not any(name.startswith(prefix + "/") for name in names):
            raise DraftError(f"特效 frame.name 无法解析到 atlas：{effect}")

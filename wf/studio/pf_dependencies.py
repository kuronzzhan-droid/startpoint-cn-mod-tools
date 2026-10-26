"""Read-only PF preload inventory, using the shared effect resolver contract."""
from __future__ import annotations

from collections.abc import Mapping
import struct
import zlib

import wf_character_requirements as requirements
from wf.dsl.references import linked_programs

from .deliver_media import tree as decode_tree
from .drafts import DraftError, sha256


def _walk(value):
    yield value
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk(child)


def _sound_path(value):
    if not isinstance(value, str):
        return None
    if value.startswith("sound_effect/"):
        return value if value.endswith(".mp3") else value + ".mp3"
    if value.endswith((".mp3", ".ogg", ".wav")) and "/" in value:
        return value
    return None


def _references(trees, element):
    dynamic = False
    for value in _walk(trees):
        if not isinstance(value, (list, tuple)) or not value or value[0] != "ResolveByElement":
            continue
        if (len(value) != 3 or not isinstance(value[1], str)
                or type(value[2]) is not int or value[2] not in (*range(1, 8), 255)):
            raise DraftError("PF 特效 ResolveByElement 必须指定合法路径和元素码 1..7 / 255")
        dynamic |= value[2] == 255
    references = {}
    # Attack element does not change an Effect's 255 selector: that selector
    # follows the executor. Check every supported executor colour, not just the
    # new attack element, so a differently coloured summoned ball stays valid.
    for context in range(7) if dynamic else (element,):
        for reference in requirements.extract_master_asset_references(
                {}, dsl_trees=trees, context_element=context):
            references.setdefault((reference.kind, reference.value), reference)
    return list(references.values()), dynamic


def prepare_dependencies(catalog, trees, element):
    """Return ``(dependencies, checks)`` without writing or copying assets.

    ``catalog.read(logical, root='common')`` supplies current-view bytes with
    bundled fallback. ``trees`` accepts the generated closure as a list or a
    logical-path mapping. The caller validates/clones linked DSL programs;
    their generated paths need not exist in the current source catalog.
    ``element`` is the internal attack element, 0..6.
    """
    if type(element) is not int or element not in range(7):
        raise DraftError("PF 依赖检查的内部元素码必须为 0..6")
    named = (dict(trees) if isinstance(trees, Mapping) else
             {f"generated[{index}]": value for index, value in enumerate(trees, 1)})
    references, dynamic = _references(named, element)
    dependencies, raw_cache, sounds = {}, {}, set()

    def read(logical, root="common"):
        key = root, logical
        if key not in raw_cache:
            raw_cache[key] = catalog.read(logical, root=root)
        return raw_cache[key]

    def add(logical, kind, reference, *, root="common", required=True):
        raw = read(logical, root)
        if not raw:
            if required:
                raise DraftError(f"PF 预载依赖缺失：{root}/{logical}（引用 {reference}）")
            return None
        key = root, logical
        item = dependencies.setdefault(key, {
            "kind": kind, "root": root, "logical": logical, "required": required,
            "status": "existing", "sha256": sha256(raw), "size": len(raw), "references": [],
        })
        if reference not in item["references"]:
            item["references"].append(reference)
        return raw

    effects = {ref.value: ref for ref in references if ref.kind == "skill_effect"}
    # Some authored families carry a separate end animation. An absent optional
    # companion is normal; a present half-family must not pass as complete.
    for effect, reference in list(effects.items()):
        ending = effect + "_end"
        if any(read(ending + suffix) is not None for suffix in
               (".parts.amf3.deflate", ".timeline.amf3.deflate")):
            effects.setdefault(ending, requirements.MasterAssetReference("skill_effect", ending, reference.source))

    for effect, reference in sorted(effects.items()):
        paths = requirements.required_asset_paths(reference)
        assets = [add(path, kind, effect) for path, kind in zip(paths,
                  ("effect_parts", "effect_timeline", "effect_image", "effect_atlas"))]
        try:
            parts, timeline, atlas = (decode_tree(assets[index]) for index in (0, 1, 3))
        except (ValueError, IndexError, TypeError, KeyError, zlib.error, struct.error) as exc:
            raise DraftError(f"PF 特效元数据无法解码：{effect}：{exc}") from exc
        if not isinstance(parts, dict) or not isinstance(timeline, dict) or not isinstance(atlas, list):
            raise DraftError(f"PF 特效 parts/timeline/atlas 结构无效：{effect}")
        atlas_names = {item.get("n") for item in atlas if isinstance(item, dict)}
        image_refs = {item.get("p") for item in parts.get("i", []) if isinstance(item, dict) and item.get("p")}
        missing = sorted(image_refs - atlas_names)
        if missing:
            raise DraftError(f"PF 特效 parts 引用不在目录 atlas 中：{effect}：{', '.join(missing)}")
        for value in _walk(timeline):
            if sound := _sound_path(value):
                sounds.add(sound)
        texture = paths[2].removesuffix(".png") + ".atf.deflate"
        add(texture, "effect_android_texture", effect, root="android", required=False)

    for value in _walk(named):
        if sound := _sound_path(value):
            sounds.add(sound)
    for sound in sorted(sounds):
        add(sound, "sound", "DSL / effect timeline")
    for logical in sorted({path for value in named.values() for path in linked_programs(value)}):
        dependencies.setdefault(("common", logical), {
            "kind": "dsl", "root": "common", "logical": logical, "required": True,
            "status": "compiled_reference", "references": ["generated DSL closure"],
        })
    checks = [{"level": "info", "code": "pf.preload", "message":
               f"已检查 {len(effects)} 个特效的 parts/timeline/PNG/atlas 及 {len(sounds)} 个声音引用；"
               "列出的子程序由克隆编译器校验。"},
              {"level": "info", "code": "pf.preload.boundary", "message":
               "预载清单覆盖显式 DSL 引用、特效目录四件、parts→atlas 和 timeline 声音；"
               "不穷尽客户端隐式命中特效、flatomo 嵌套 MovieClip 或运行时动态资源，仍需客户端冷缓存验收。"}]
    if dynamic:
        checks.append({"level": "info", "code": "pf.preload.element-context", "message":
                       "ResolveByElement 255 保持跟随执行者属性，已按内部元素 0..6 检查全部七色，未按攻击属性固定。"})
    return [dependencies[key] for key in sorted(dependencies)], checks

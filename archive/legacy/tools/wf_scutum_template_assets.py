"""盾牌座所需原生配套数据与王子特效；只生成隔离资源。"""
import zlib

import wf_assets
import wf_character_requirements as requirements
import wf_dsl
from wf_character_revision import encode_tree
from wf_scutum_seed import CODE, TEMPLATE_CODE, remap

EFFECT_DIR = "battle/effect/skill_unique/" + CODE + "/"
ROOT_NAMES = {"upload": "common", "medium_upload": "medium", "android_upload": "android"}


def build(seed):
    for item in requirements.char_asset_requirements(CODE):
        if item.category != "required":
            continue
        source = item.logical_path.replace(CODE, TEMPLATE_CODE)
        location = wf_assets.locate(seed.store, source)
        if not location:
            raise FileNotFoundError(source)
        tier, path = location
        raw = path.read_bytes()
        if source.endswith(".amf3.deflate"):
            tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            raw = encode_tree(remap(tree))
        seed.emit(ROOT_NAMES.get(tier, tier), item.logical_path, raw)
    # Final artwork/pixels replace these base assets before production preflight.
    prefix = "battle/effect/skill_unique/" + TEMPLATE_CODE + "/"
    names = {p.strip() for p in (seed.repo / "mod-tools/WF_PATHLIST_recovered.txt").read_text().splitlines()
             if p.strip().startswith(prefix)}
    names.update(prefix + TEMPLATE_CODE + s for s in (".png", ".atlas.amf3.deflate"))
    effects = []
    for logical in sorted(names):
        location = wf_assets.locate(seed.store, logical)
        if not location:
            continue
        raw = location[1].read_bytes()
        target = remap(logical)
        if logical.endswith(".amf3.deflate"):
            tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            raw = encode_tree(remap(tree))
        seed.emit("common", target, raw)
        effects.append(target)
    return {"effect_source": TEMPLATE_CODE, "effect_assets": effects,
            "presentation_pending": True, "pixel_pending": True}

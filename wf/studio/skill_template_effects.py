"""Clone native effect families in memory using the existing character packer."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import math
import re
import zlib

import numpy as np

import wf_assets
import wf_atf
from wf.chars.halloween.color import transform
from wf.chars.support.common import clone_effect_family, rewrite_effect_refs, replace_strings, S7Error
from .deliver_media import encode_tree, png, read_root, tree
from .drafts import DraftError, sha256
from .pixel_workshop import recolor
from .skill_template_effects_refs import discover, effect_refs, validate_atlas, validate_metadata

NAME = re.compile(r"[a-z0-9][a-z0-9_]*\Z")


def _color(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise DraftError("特效颜色需要 #RRGGBB")
    return tuple(bytes.fromhex(value[1:]))


def color_transform(spec):
    """Use existing alpha-preserving palette tools; never rearrange atlas cells."""
    spec = {} if spec is None else spec
    if not isinstance(spec, dict) or set(spec) not in (set(), {"hueShift"}, {"pairs"}):
        raise DraftError("recolor 只能包含 hueShift 或 pairs")
    if not spec:
        return lambda image: image.copy()
    if "hueShift" in spec:
        shift = spec["hueShift"]
        if type(shift) not in (int, float) or not math.isfinite(shift) or not -360 <= shift <= 360:
            raise DraftError("hueShift 需要 -360..360 的有限数值")
        # The shared tool normalizes 360 to zero; use two intervals to cover the circle.
        return transform([{"from": [0, 180], "shift": shift},
                          {"from": [180, 359.999999], "shift": shift}])
    pairs = spec["pairs"]
    if not isinstance(pairs, list) or not pairs:
        raise DraftError("pairs 需要至少一组 from/to 颜色")
    mapping = {}
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {"from", "to"}:
            raise DraftError("每组颜色需要且只能包含 from/to")
        old, new = _color(pair["from"]), _color(pair["to"])
        if old in mapping:
            raise DraftError("颜色映射不能重复 from")
        mapping[old] = new
    return lambda image: recolor(image, mapping)[0]


class _MemoryPack:
    """Only the existing family helper's narrow pack protocol, without disk writes."""
    root = Path("__studio_effect_memory_only__")

    def __init__(self, source, code):
        self.source, self.spec = source, SimpleNamespace(code=code)
        self.members, self.inputs, self.snapshots, self.evidence = {}, {}, {}, {}

    def read(self, root, logical, *, required=True):
        raw = read_root(self.source, root, logical)
        self.snapshots[root, logical] = sha256(raw) if raw is not None else None
        if raw is None and required:
            raise DraftError(f"特效依赖缺失：{root}/{logical}")
        if raw is not None:
            self.inputs[f"{root}:{logical}"] = sha256(raw)
        return raw

    def template_asset(self, logical):
        raw = self.read("common", logical, required=False)
        if raw is None:
            raise FileNotFoundError(logical)
        return "common", raw, "template source"

    def write_asset(self, root, logical, raw, **_):
        if (root, logical) in self.members:
            raise DraftError(f"特效目标资源重复：{logical}")
        self.members[root, logical] = raw

    def read_evidence(self, name, default):
        return self.evidence.get(name, default)

    def write_evidence(self, name, value):
        self.evidence[name] = value


def _atfs(pack, family, changed):
    source, target = family["src_dir"], family["dst_dir"]
    src = f"{source}/{family['donor']}.atf.deflate"
    dst = f"{target}/{family['dst_name']}.atf.deflate"
    png_bytes = wf_assets.png_decode(pack.members["common", f"{target}/{family['dst_name']}.png"])
    resources = []
    for root in ("android", "common"):
        raw = pack.read(root, src, required=False)
        if raw is None:
            continue
        try:
            original = wf_atf.inflate(raw)
            # parse_atf explicitly rejects variants that the existing encoder cannot retain.
            wf_atf.parse_atf(original)
            output = wf_atf.deflate(wf_atf.build_cutin_atf(png_bytes, original)) if changed else raw
        except (ValueError, IndexError, zlib.error) as exc:
            raise DraftError(f"特效 ATF 无法由现有编码器保真派生：{src}：{exc}") from exc
        pack.write_asset(root, dst, output)
        resources.append({"root": root, "source": src, "target": dst,
                          "sourceSha256": sha256(raw), "sha256": sha256(output)})
    return resources


def clone_effects(source, effects, code: str, new_key: str, color=None):
    """Return stored members, source assertions, exact reference map and checks.

    ``source`` must already select the intended official/template view. All selected
    effects and recursively referenced native effects are copied. Whole atlas sheets
    retain layout, trim/rotation records, alpha, frame timing and sound references.
    """
    if not isinstance(code, str) or not NAME.fullmatch(code):
        raise DraftError("特效目标 code 需要小写字母、数字、下划线")
    if not isinstance(new_key, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}", new_key):
        raise DraftError("特效新技能键格式无效")
    tint = color_transform(color)
    pack = _MemoryPack(source, code)
    requested = effect_refs(effects)
    groups, metadata = discover(pack, requested)
    families, maps, checks = [], {}, []
    # Hash the full key to avoid collisions caused by sanitizing ':' / '.' / '-'.
    namespace = "skill_" + sha256(new_key.encode("utf-8"))[:16]
    originals = []
    for index, (directory, names) in enumerate(sorted(groups.items())):
        atlas_path = f"{directory}/{directory.rsplit('/', 1)[-1]}.atlas.amf3.deflate"
        image_path = atlas_path.removesuffix(".atlas.amf3.deflate") + ".png"
        image, atlas = png(pack.read("common", image_path)), tree(pack.read("common", atlas_path))
        validate_atlas(atlas, image)
        for name in names:
            validate_metadata(f"{directory}/{name}", metadata, atlas)
        try:
            family = clone_effect_family(pack, directory, f"{namespace}_{index + 1}",
                                         fx_names=sorted(names), png_transform=tint)
        except (S7Error, FileNotFoundError, ValueError) as exc:
            raise DraftError(f"特效族克隆失败：{directory}：{exc}") from exc
        # The old helper clones parts/timeline. FrameAnimation's extra document
        # is retained here using the same reference rewriter, without repacking.
        for name in names:
            old = f"{directory}/{name}.frame.amf3.deflate"
            if old in metadata:
                output, _ = rewrite_effect_refs(metadata[old], family, strict=True)
                dst = f"{family['dst_dir']}/{name}.frame.amf3.deflate"
                pack.write_asset("common", dst, encode_tree(output))
                family["files"].append({"root": "common", "source": old, "target": dst,
                                        "source_sha256": pack.inputs[f"common:{old}"]})
        for effect in family["effects"]:
            maps[effect["source"]] = effect["target"]
        originals.append(family)
        changed = int(np.count_nonzero(np.any(np.asarray(image) != np.asarray(tint(image)), axis=-1)))
        extra = _atfs(pack, family, changed)
        families.append({"source": directory, "target": family["dst_dir"],
                         "effects": family["effects"], "changedPixels": changed,
                         "resources": extra, "completeDependencies": True})
    # Timeline and nested flatomo references can cross effect families. Rewrite
    # after the full dependency closure has received private destination paths.
    prefixes = {family["src_dir"] + "/": family["dst_dir"] + "/" for family in originals}
    for (root, logical), raw in list(pack.members.items()):
        if logical.endswith(".amf3.deflate"):
            original_value = tree(raw)
            value = replace_strings(original_value, prefixes)
            if logical.endswith(".timeline.amf3.deflate") and "sounds" in original_value:
                value["sounds"] = original_value["sounds"]
            pack.members[root, logical] = encode_tree(value)
    for public, original in zip(families, originals):
        public["resources"] += [{"root": item["root"], "source": item["source"],
                                 "target": item["target"], "sourceSha256": item["source_sha256"],
                                 "sha256": sha256(pack.members[item["root"], item["target"]])}
                                for item in original["files"]]
        public["resources"].sort(key=lambda item: (item["root"], item["target"]))
    if families:
        checks.append({"level": "info", "code": "skill_template.effect_dependencies",
                       "message": "特效 atlas、parts/frame、timeline 与声音依赖已核对；布局、帧时序和 alpha 保留，ATF 沿用现有编码器。"})
    checks.append({"level": "info", "code": "skill_template.effect_runtime",
                   "message": "换色与依赖检查为静态验证；未执行客户端预载或设备战斗验收。"})
    return {"members": pack.members, "inputs": pack.inputs, "rewrite_map": maps,
            "families": families, "checks": checks,
            "snapshots": [{"root": root, "logical": logical, "sha256": digest}
                          for (root, logical), digest in sorted(pack.snapshots.items())]}

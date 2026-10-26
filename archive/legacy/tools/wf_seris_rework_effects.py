"""赛瑞斯新技能演出：自有API帧→原生flatomo，仅替换候选的视觉引用。"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

from PIL import Image
import wf_generated_vfx as V
import wf_seasonal7_common as C

ROOT = "battle/effect/skill_unique/seris_rework_v3"
OLD = {
    "battle/effect/skill_unique/seris_human_royal_tide_ring/seris_human_royal_tide_ring": "tide_ring",
    "battle/effect/skill_unique/seris_dragon_frozen_thunder_breath/seris_dragon_frozen_thunder_breath": "breath",
    "battle/effect/skill_unique/seris_dragon_flight/seris_dragon_flight": "flight",
    "battle/effect/skill_unique/seris_dragon_king/seris_dragon_king_transform": "transform",
}
SPECS = {
    "tide_ring": ("fx_tide_ring_anim", 32, "once", (9, 0, 0, 9, -576, -576)),
    "breath": ("fx_breath_anim", 36, "once", (0, 6, -6, 0, 288, -560)),
    "flight": ("dragon_neutral", 32, "loop", (8.7, 0, 0, 8.7, -139, -900)),
    "transform": ("transform", 60, "once", (6, 0, 0, 6, -96, -96)),
    "thunder": ("fx_thunder_anim", 36, "once", (4, 0, 0, 4, -256, -384)),
}


def compile_frames(images, name, total, kind, matrix):
    if len(images) < 4 or total < len(images) or kind not in ("once", "loop"):
        raise ValueError("incomplete VFX frames or duration")
    if len({im.size for im in images}) != 1:
        raise ValueError("VFX frame sizes differ")
    if any(im.mode != "RGBA" or im.getchannel("A").getextrema()[0] != 0 for im in images):
        raise ValueError("VFX requires transparent RGBA frames")
    prefix = f"{ROOT}/{name}/texture_"
    parts, timeline = V.build_parts(len(images), images[0].size, prefix)
    parts["g"][0]["t"] = total
    parts["t"] = [dict(zip(("a", "b", "c", "d", "x", "y"),
                            (round(v * 4096) for v in matrix)))]
    for i, segment in enumerate(parts["g"][0]["s"]):
        start, end = round(i * total / len(images)), round((i + 1) * total / len(images))
        alpha = 255 if kind == "loop" else round(255 * math.sin(math.pi * i / (len(images) - 1)))
        segment.update(s=start)
        segment["l"][0].update(t=end - start, m=alpha)
    timeline["sequences"][0].update(end=total, kind=kind)
    sheet, atlas = V.pack_images(images, [item["p"] for item in parts["i"]])
    return sheet, atlas, parts, timeline


def replace_visual_paths(tree):
    result = copy.deepcopy(tree)
    count = 0
    for node in C.walk(result):
        if isinstance(node, list) and len(node) == 2 and node[0] == "SpecifyEffectDirectly":
            if node[1] in OLD:
                node[1] = f"{ROOT}/{OLD[node[1]]}/effect"
                count += 1
    # 只允许视觉资源名改变；倍率、命中、等待、状态和主体均保留。
    reverse = {f"{ROOT}/{name}/effect": old for old, name in OLD.items()}
    if count and C.replace_strings(result, reverse) != tree:
        raise ValueError("nonvisual DSL behavior changed")
    return result, count


def build(pack, source: Path):
    report = dict(status="candidate", summary="水环、吐息、四足龙演出、变身及雷击五套原生特效",
                  runtime_verified=False, timing="沿用既有技能等待和特效生命周期；角色定位未重写", effects={})
    for name, (job, total, kind, matrix) in SPECS.items():
        folder = source / "jobs" / job
        state = json.loads((folder / "status.json").read_bytes())
        if state.get("status") != "completed":
            raise ValueError(f"unfinished effect job {job}")
        paths = sorted(folder.glob("[0-9][0-9].png"))
        images = [Image.open(p).convert("RGBA") for p in paths]
        sheet, atlas, parts, timeline = compile_frames(images, name, total, kind, matrix)
        if name == "transform":
            timeline["sounds"] = [dict(path="sound_effect/unique/se_seris_transform", begin=8,
                                        loop=1, end=59, volume=9)]
        prefix = f"{ROOT}/{name}"
        pack.write_asset("common", f"{prefix}/{name}.png", C.png_store_bytes(sheet), owner="effects")
        for stem, tree in ((name + ".atlas", atlas), ("effect.parts", parts), ("effect.timeline", timeline)):
            pack.write_asset("common", f"{prefix}/{stem}.amf3.deflate", C.amf_bytes(tree), owner="effects")
        output = pack.evidence_path(f"effects/{name}"); output.mkdir(parents=True, exist_ok=True)
        V.previews(images, output, hold=max(1, round(total / len(images))))
        report["effects"][name] = dict(frames=len(images), total_frames=total, kind=kind,
                                        sources={str(p): C.sha256(p.read_bytes()) for p in paths})
    updated = []
    for program in pack.pkg_dsl_programs():
        raw = pack.pkg_path("common", program).read_bytes()
        tree = C.amf_parse(raw)
        after, count = replace_visual_paths(tree)
        if count:
            pack.write_dsl(program, after, owner="effects")
        updated.append(dict(program=program, replaced_visual_references=count,
                            damage_conditions_waits_unchanged=True))
    report["dsl"] = updated
    pack.write_evidence("effects-report.json", report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--workspace", type=Path)
    a = p.parse_args()
    from wf_seris_rework_workspace import context
    print(json.dumps(build(context(a.workspace), a.source), ensure_ascii=False, indent=2))

# -*- coding: utf-8 -*-
"""立绘装配：透明母图 art/masters/<key>-<0|1>.png + 手标 landmarks → full_shot×2、图标、cutin PNG+ATF、
立绘图集、三张定位表（wf_seasonal7_art.build 去掉 flow manifest 记账的同等流程）。
    python hw_art.py ludi [momiya ...]
"""
from __future__ import annotations

import json
import sys

from wf.chars.halloween import env as hw_env
from wf.chars.halloween import common as HC
import wf_assets
import wf_atf
from wf.chars.support import portraits as campus_art
from wf.chars.support import images as images
from wf.chars.support import masks as ART
import wf_ui_derive_gate as gate

MASTERS = hw_env.OUT / "art" / "masters"


def lm(eyes, head, face_dy=20, sq=1.25):
    return dict(eyes=list(eyes), face=[eyes[0], eyes[1] + face_dy], head_height=head, square_height=round(head * sq))


LANDMARKS = {
    "ludi": [lm((534, 211), 300), lm((590, 215), 300)],
    "momiya": [lm((538, 215), 210), lm((554, 310), 210)],
    "seriol": [lm((457, 166), 200), lm((533, 301), 200)],
    "recital": [lm((555, 301), 260), lm((496, 331), 260)],
}


def build(key):
    pack = HC.pack_for(key)
    spec = pack.spec
    role = f"hw:{key}"
    images.COLORS[role] = tuple(tuple(c) for c in spec.backdrop_colors)
    ui = f"character/{spec.code}/ui/"
    out = pack.evidence / "art"
    out.mkdir(parents=True, exist_ok=True)
    cands, fulls, geometry, prev_i, prev_a, report = {}, [], [], {}, {}, {"gates": {}}
    cache = hw_env.INPUT / "pkgroot/art-official-shape-masks.npz"
    for level in (0, 1):
        land = LANDMARKS[key][level]
        master, _src = images.load_master(MASTERS / f"{key}-{level}.png", land)
        full, geom = images.full_shot(master, land["eyes"])
        fulls.append(full)
        geometry.append(geom)
        full.save(out / f"full-shot-{level}.png")
        cands["medium/" + ui + f"full_shot_1440_1920_{level}.png"] = wf_assets.png_encode(images.png(full))
        masks, _ms = ART._load_masks(pack, level, cache)
        icons = images.make_icons(master, land, masks, role)
        icons["skill_cutin"] = images.make_cutin(master, land)
        probs = gate.derived_icon_problems(icons, masks, level=str(level))
        report["gates"][str(level)] = probs
        for slot, im in icons.items():
            cands["medium/" + ui + f"{slot}_{level}.png"] = wf_assets.png_encode(images.png(im))
            prev_i[f"{slot}_{level}"] = im
        atf_rel = "android/" + ui + f"skill_cutin_{level}.atf.deflate"
        template = wf_atf.inflate(pack.pkg_path("android", ui + f"skill_cutin_{level}.atf.deflate").read_bytes())
        cands[atf_rel] = wf_atf.deflate(wf_atf.build_cutin_atf(images.png(icons["skill_cutin"]), template))
        prev_a[f"full-shot-{level}"] = full
        prev_a[f"skill-cutin-{level}"] = icons["skill_cutin"]
    sheet_rel, sheet = campus_art.atlas_sheet(pack.package, ui, fulls)
    cands[sheet_rel] = wf_assets.png_encode(images.png(sheet))
    prev_a["illustration-sheet"] = sheet
    cands.update(campus_art.patch_tables(pack.package, spec.cid_s, ui, geometry))
    images.preview(prev_i, out / "icons-contact.png")
    images.preview(prev_a, out / "art-contact.png")
    for rel, raw in cands.items():
        root, logical = rel.split("/", 1)
        pack.write_pkg(root, logical, raw)
    report["files"] = sorted(cands)
    report["geometry"] = geometry
    (out / "applied.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), "utf-8")
    return {"files": len(cands), "gates": report["gates"], "contact": str(out / "icons-contact.png")}


if __name__ == "__main__":
    for k in sys.argv[1:]:
        print(k, json.dumps(build(k), ensure_ascii=False, default=str))

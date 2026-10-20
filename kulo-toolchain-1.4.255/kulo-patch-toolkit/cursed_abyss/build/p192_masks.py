# -*- coding: utf-8 -*-
"""官方 1.4.0 全量档形状蒙版：每槽 alpha>127 多数票（_0/_1 合并）。"""
from p192_common import *
import numpy as np, glob, json, sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_ui_derive_gate as gate
ARCH = Path(r"D:/WF/startpoint-cn-kulo/.cdn/cn/archive-medium-full")
idx = {}
for z in sorted(ARCH.glob("pinball-1.4.0-*.zip")):
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist(): idx[n] = z
print("indexed", len(idx))
C = load("master/character/character.orderedmap")
codes = sorted({row(v)[0] for v in C.values() if isinstance(v, str) and v})
votes = {s: None for s in gate.SHAPE_SLOTS}; n = {s: 0 for s in gate.SHAPE_SLOTS}; used = {s: [] for s in gate.SHAPE_SLOTS}
handles = {}
for slot in gate.SHAPE_SLOTS:
    want = gate.OFFICIAL_ICON_SIZES[slot]
    for code in codes:
        for lv in (0, 1):
            m = f"production/medium_upload/{digest(f'character/{code}/ui/{slot}_{lv}.png')}"
            if m not in idx: continue
            z = idx[m]; zf = handles.get(z) or handles.setdefault(z, zipfile.ZipFile(z))
            im = png_img(zf.read(m))
            if im.size != want: continue
            a = (np.asarray(im)[:, :, 3] > 127).astype(np.int32)
            votes[slot] = a if votes[slot] is None else votes[slot] + a; n[slot] += 1
            if not used[slot] or used[slot][-1] != code: used[slot].append(code)
masks = {s: np.where(votes[s] * 2 > n[s], 255, 0).astype(np.uint8) for s in gate.SHAPE_SLOTS}
np.savez_compressed(ART / "official-shape-masks-140-majority.npz", **masks)
meta = {"method": "archive-medium-full pinball-1.4.0 alpha>127 majority, levels 0+1 pooled",
        "samples": n, "characters": {s: len(v) for s, v in used.items()},
        "coverage": {s: round(float((masks[s] > 8).mean()), 4) for s in masks}}
(ART / "official-shape-masks-140-majority.json").write_text(json.dumps(meta, indent=1), "utf8"); print(meta)

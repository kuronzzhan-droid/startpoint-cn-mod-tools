"""从已选 C049 原图恢复斩铁普通立绘；只去边界相连的白底，保留场景和手部。"""
from __future__ import annotations

from wf.paths import root_path

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

import wf_seasonal7_common as C
import wf_seasonal7_specs as S
import wf_seasonal7_art as art

SOURCE = Path(('${WF_ROOT}/out/Claude角色制作交接-20260916/立绘/斩铁/普通_C049.png'.replace("${WF_ROOT}", str(root_path()))))
SOURCE_SHA = "c7eb99d3f9a25bd66d5e637c6ae117342caef6755791d1caff921500f976e2cc"


def restore_master(path=SOURCE):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError("selected C049 source changed")
    with Image.open(path) as image:
        source = np.array(image.convert("RGBA"))
    rgb = source[:, :, :3].astype(np.int16)
    white = (rgb.min(2) >= 244) & (np.ptp(rgb, axis=2) <= 10)
    labels, _ = ndimage.label(white)
    border = np.unique(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1])))
    background = np.isin(labels, border[border != 0])
    restored = source.copy()
    restored[background, 3] = 0
    # Restore means copying source pixels, not repainting the character or scene.
    assert np.array_equal(restored[:, :, :3], source[:, :, :3])
    for x, y in ((816, 680), (820, 704), (834, 862), (1060, 650), (136, 750)):
        if restored[y, x, 3] != 255:
            raise ValueError(f"hand/bag/scenery was removed at {x},{y}")
    return Image.fromarray(restored), dict(source=str(path), source_sha256=SOURCE_SHA,
        source_size=[source.shape[1], source.shape[0]], removed_white_pixels=int(background.sum()),
        rgb_unchanged=True, original_hand_bag_and_scene_retained=True)


def build(*, apply=False):
    pack = C.S7Pack(S.get_spec("zantetsu"))
    folder = pack.evidence / "art-restore-20260919"
    folder.mkdir(parents=True, exist_ok=True)
    master, source_report = restore_master()
    sources = folder / "masters"
    sources.mkdir(exist_ok=True)
    master.save(sources / "zantetsu-0.png")
    default_sources = art.default_source_dir(pack.root)
    (sources / "zantetsu-1.png").write_bytes((default_sources / "zantetsu-1.png").read_bytes())
    lm_path = art.default_landmarks(pack.root)
    landmarks = json.loads(lm_path.read_bytes())
    lm = landmarks["zantetsu"]
    lm[0]["sha256"] = C.sha256((sources / "zantetsu-0.png").read_bytes())
    (folder / "landmarks.json").write_text(C.json_dump({"zantetsu": lm}), encoding="utf-8")
    report = art.build(pack, lm, source_dir=sources, output=folder, apply=apply)
    report["restoration"] = source_report
    if apply:
        # Keep future art rebuilds on the restored master. Originals stay in backup.
        backup = folder / "source-before"
        backup.mkdir(exist_ok=True)
        for path in (default_sources / "zantetsu-0.png", lm_path):
            dest = backup / path.name
            if not dest.exists():
                dest.write_bytes(path.read_bytes())
        (default_sources / "zantetsu-0.png").write_bytes((sources / "zantetsu-0.png").read_bytes())
        lm_path.write_text(C.json_dump(landmarks), encoding="utf-8")
    (folder / "restore-report.json").write_text(C.json_dump(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    result = build(apply=parser.parse_args().apply)
    print(json.dumps({"applied": result["applied"], "gates": result["gates"],
        "changes": [f["logical"] for f in result["files"] if f["changed"]]}, ensure_ascii=False))

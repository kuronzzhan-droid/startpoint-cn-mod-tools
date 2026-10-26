"""海豹球已确认原画的游戏资产转换；RGB主体与原文件保持一致。"""

from wf.paths import root_path
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy import ndimage
from PIL import Image

import wf_seasonal7_art as art
import wf_seasonal7_manifest as manifest
import wf_spheal_mascot_pixel as pixel

ART = Path(('${WF_ROOT}/out/海豹球-觉醒前后立绘-20260919'.replace("${WF_ROOT}", str(root_path()))))
SOURCES = ("海豹球-觉醒前-官方鳍结构修订.png", "海豹球-觉醒后-短尾修订03.png")


def cutout(source, destination):
    """白底资产格式转换：只去除连通画布边缘的白底，保留封闭的白斑/眼睛/泡沫。"""
    rgb = np.asarray(Image.open(source).convert("RGB"))
    neutral = (rgb.min(2) >= 242) & (np.ptp(rgb.astype(np.int16), axis=2) <= 12)
    labels, _ = ndimage.label(neutral)
    outside = np.unique(np.concatenate((labels[0], labels[-1], labels[:,0], labels[:,-1])))
    background = np.isin(labels, outside[outside != 0])
    alpha = np.where(background, 0, 255).astype(np.uint8)
    rgba = np.dstack((rgb, alpha))
    rgba[alpha == 0, :3] = 0
    Image.fromarray(rgba).save(destination)
    return dict(source=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                transparent_ratio=float(background.mean()), method="border-connected white only",
                preserves_foreground_rgb=True)


def build(pack):
    pixel.build(pack)
    masters = pack.evidence_path("masters")
    masters.mkdir(exist_ok=True, parents=True)
    provenance = [cutout(ART/name, masters/f"spheal-{i}.png") for i,name in enumerate(SOURCES)]
    manifest.build(pack)
    landmarks = [dict(face=[450,570],eyes=[450,515],square_height=840,head_height=800),
                 dict(face=[685,480],eyes=[690,440],square_height=890,head_height=840)]
    report = art.build(pack, landmarks, source_dir=masters, apply=True, headshots=True)
    # 法夫的语音仅是脚手架资源；无语音吉祥物不可留原角色人声。
    voice_dir = pack.pkg_path("common",f"character/{pack.spec.code}/voice")
    removed = []
    if voice_dir.exists():
        for path in voice_dir.rglob("*.mp3"):
            assert path.resolve().is_relative_to((pack.package/"roots/common").resolve())
            removed.append(path.relative_to(pack.package/"roots/common").as_posix())
            path.unlink()
    pack.write_evidence("voice-report.json",dict(status="ready",mode="native-unvoiced",
        summary="原生无语音绑定，觉醒前后均有展示行；不借用法夫人声",removed_template_voices=removed))
    report["cutout_provenance"] = provenance
    manifest.build(pack)
    return report

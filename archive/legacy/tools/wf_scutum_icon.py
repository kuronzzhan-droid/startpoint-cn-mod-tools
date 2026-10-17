"""将已生成并检查过的收集图标裁到游戏原生 32 像素。"""
import io

from PIL import Image

import wf_assets
from wf_campus_art_images import png, sha

LOGICAL = "battle/common/unique_condition/scutum_valentine_collect.png"


def build(seed, source_path, output):
    raw = source_path.read_bytes()
    source = Image.open(io.BytesIO(raw))
    if source.mode != "RGBA" or source.getchannel("A").getextrema() != (0, 255):
        raise ValueError("collect icon requires genuine transparent RGBA")
    box = source.getchannel("A").point(lambda x: 255 if x > 64 else 0).getbbox()
    if box is None:
        raise ValueError("collect icon is empty")
    icon = source.crop(box).resize((30, 30), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (32, 32))
    canvas.alpha_composite(icon, (1, 1))
    seed.emit("common", LOGICAL, wf_assets.png_encode(png(canvas)))
    output.mkdir(parents=True, exist_ok=True)
    canvas.save(output / "collect-32.png")
    canvas.resize((256, 256), Image.Resampling.NEAREST).save(output / "collect-preview.png")
    return dict(source=str(source_path), source_sha256=sha(raw), generator="built-in image_gen",
                logical=LOGICAL, dimensions=[32, 32], postprocessing="transparent crop and native-size resize")

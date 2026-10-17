"""把参考派生帧编为赛瑞斯双形态完整原生时间轴，只写候选 workspace。"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image
import wf_seasonal7_common as C

REGULAR = ("neutral", "walk_back", "walk_front", "skill_ready", "kachidoki",
           "into_coffin", "ghost_raise", "ghost_neutral", "revive")
EXTRA = ("skill", "special_land", "special_pose")
SOLID = frozenset(("neutral", "walk_back", "walk_front"))
LOOPS = SOLID | {"kachidoki", "ghost_neutral"}


def bounded_frame(image, *, human, name):
    """像素整数对齐及最近邻尺寸约束；原始API帧保留在来源目录。"""
    im = image.convert("RGBA")
    if im.size != (32, 32):
        raise ValueError(f"expected 32x32 source frame, got {im.size}")
    box = im.getchannel("A").getbbox()
    if box is None:
        return im
    # 人形生成动作会把16像素高的原设拉长；只向下约束，不放大倒地姿势。
    if human and box[3] - box[1] > 17:
        tile = im.crop(box)
        height = 16 if name in ("neutral", "walk_back", "walk_front") else 17
        tile = tile.resize((tile.width, height), Image.Resampling.NEAREST)
        im = Image.new("RGBA", (32, 32))
        bottom = box[3] if name in ("ghost_raise", "ghost_neutral") else 27
        im.alpha_composite(tile, (box[0], bottom - height))
    return im


def load_clips(source: Path, name: str, dragon: bool):
    if name not in (*REGULAR, *EXTRA):
        raise ValueError(name)
    if name == "neutral" and not dragon:
        # 待机保留作者提供的精确像素，不采用API拉长了头部的候选帧。
        path = source / "refs/front.png"
        im = Image.open(path).convert("RGBA")
        raised = Image.new("RGBA", im.size)
        raised.alpha_composite(im, (0, -1))
        return [(im, 36), (raised, 12), (im.copy(), 36)], [path]
    job = source / "jobs" / (("dragon_" if dragon else "") + name)
    state = json.loads((job / "status.json").read_bytes())
    if state.get("status") != "completed":
        raise ValueError(f"unfinished animation job: {job.name}")
    paths = sorted(job.glob("[0-9][0-9].png"))
    if len(paths) < 8:
        raise ValueError(f"incomplete frames: {job.name}: {len(paths)}")
    clips = []
    for i, path in enumerate(paths):
        im = bounded_frame(Image.open(path), human=not dragon, name=name)
        if name in ("ghost_raise", "ghost_neutral"):
            im.putalpha(im.getchannel("A").point(lambda a: round(a * .45)))
        elif name == "into_coffin":
            im.putalpha(im.getchannel("A").point(lambda a: round(a * (1 - i / (len(paths) - 1)))))
        hold = 4 if name.startswith("walk") else 6 if name == "skill" else 8
        clips.append((im, hold))
    return clips, paths


def compile_family(clips_by_name, code, dragon=False):
    """两个资源族都包含常规9槽；special另有技能和展示，供Unique22分支调用。"""
    names = (*REGULAR, *EXTRA)
    if set(clips_by_name) != set(names):
        raise ValueError("both forms need all 12 action slots")
    stem = "special" if dragon else "pixelart"
    sheet_name = "special_sprite_sheet" if dragon else "sprite_sheet"
    prefix = f"character/{code}/pixelart/"
    cursor, atlas, sequences, circles, tiles, cells = 1, [], [], [], [], {}
    for name in names:
        clips = clips_by_name[name]
        if not clips:
            raise ValueError(f"empty action: {name}")
        begin = cursor
        for im, hold in clips:
            if im.mode != "RGBA" or im.size != (32, 32) or not isinstance(hold, int) or hold < 2:
                raise ValueError(f"invalid frame/hold in {name}")
            key = hashlib.sha256(im.tobytes()).hexdigest()
            if key not in cells:
                cells[key] = len(tiles)
                tiles.append(im)
            cell = cells[key]
            # flatomo 的数字后缀是持有帧的终点（包含该帧），不是起点。
            atlas.append(dict(n=f"{prefix}{stem}{cursor + hold - 1:04d}", x=(cell % 8) * 34, y=(cell // 8) * 34,
                              w=32, h=32, fx=-112, fy=-101, fw=256, fh=256))
            cursor += hold
        kind = "loop" if name in LOOPS else "pass" if name in ("into_coffin", "ghost_raise", "special_land") else "once"
        sequences.append(dict(name=name, kind=kind, begin=begin, end=cursor - 1))
        circles.append(dict(begin=begin + 1, data=[dict(x=0, y=0, r=8.3)] if name in SOLID else []))
    height = 2 ** math.ceil(math.log2(max(32, math.ceil(len(tiles) / 8) * 34)))
    sheet = Image.new("RGBA", (512, height))
    for i, tile in enumerate(tiles):
        sheet.alpha_composite(tile, ((i % 8) * 34, (i // 8) * 34))
    timeline = dict(sequences=sequences, circles=[dict(path="unit_body", frames=circles)],
                    points=[dict(path="hp_gauge", frames=[dict(begin=1, data=[dict(x=0, y=-10)])])], sounds=[])
    metadata = {sheet_name + ".atlas": atlas,
                stem + ".frame": dict(name=prefix + stem, x=-128, y=-128, scale=6, smoothing=False),
                stem + ".timeline": timeline}
    return sheet_name, sheet, metadata


def build(pack, source: Path):
    report = dict(status="candidate", summary="双形态各12动作；常规9槽齐全；人形待机锁定原参考",
                  normalization="nearest-neighbor height cap for human motion; raw API frames retained",
                  runtime_verified=False, accepted_by_user=False, forms={})
    for dragon in (False, True):
        form = "dragon" if dragon else "human"
        clips, hashes = {}, {}
        for name in (*REGULAR, *EXTRA):
            clips[name], paths = load_clips(source, name, dragon)
            hashes.update({str(p): C.sha256(p.read_bytes()) for p in paths})
            preview = [im.resize((256, 256), Image.Resampling.NEAREST) for im, _ in clips[name]]
            target = pack.evidence_path(f"pixel/{form}/{name}.gif")
            target.parent.mkdir(parents=True, exist_ok=True)
            preview[0].save(target, save_all=True, append_images=preview[1:],
                            duration=[round(hold * 1000 / 60) for _, hold in clips[name]], loop=0, disposal=2)
        name, sheet, metadata = compile_family(clips, pack.spec.code, dragon)
        prefix = f"character/{pack.spec.code}/pixelart/"
        buf = io.BytesIO(); sheet.save(buf, "PNG")
        pack.write_asset("common", prefix + name + ".png", C.wf_assets.png_encode(buf.getvalue()), owner="pixel")
        for logical, tree in metadata.items():
            pack.write_asset("common", prefix + logical + ".amf3.deflate", C.amf_bytes(tree), owner="pixel")
        report["forms"][form] = dict(source_hashes=hashes, sheet_size=list(sheet.size),
                                    frames=sum(len(c) for c in clips.values()), sequences=list(clips))
    pack.write_evidence("pixel-report.json", report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--workspace", type=Path)
    a = p.parse_args()
    from wf_seris_rework_workspace import context
    print(json.dumps(build(context(a.workspace), a.source), ensure_ascii=False, indent=2))

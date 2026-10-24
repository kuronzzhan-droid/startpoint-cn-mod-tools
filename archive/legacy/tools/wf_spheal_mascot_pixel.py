"""将已确认的海豹球原生像素工程编成战斗全动作；不写 live。"""

from wf.paths import root_path
from pathlib import Path
import hashlib
import io
import math

from PIL import Image
import wf_seasonal7_common as C

SOURCE = Path(('${WF_ROOT}/out/海豹球-CharacterStudio像素试作-20260918/修订05/绘制帧'.replace("${WF_ROOT}", str(root_path()))))


def frames_for(name):
    front = lambda pose: Image.open(SOURCE / f"front_{pose}.png").convert("RGBA")
    back = lambda pose: Image.open(SOURCE / f"back_{pose}.png").convert("RGBA")
    if name == "special_land":
        return [(front(p), n) for p, n in zip(
            ("apex", "up", "squash", "up", "rest"), (8, 6, 10, 6, 12))]
    if name == "special_pose":
        return [(front(p), n) for p, n in zip(
            ("rest", "squash", "up", "apex", "up", "rest", "blink", "rest"),
            (8, 6, 6, 10, 6, 12, 6, 18))]
    if name == "neutral":
        return [(front(p), n) for p, n in zip(("rest", "squash", "rest", "blink", "rest"), (30, 10, 16, 6, 16))]
    if name in ("walk_front", "walk_back", "skill_ready", "kachidoki", "skill"):
        load = back if name == "walk_back" else front
        return [(load(p), n) for p, n in zip(("squash", "up", "apex", "up", "rest"),
                                           (4, 4, 6, 4, 6) if name.startswith("walk") else (6, 6, 8, 6, 6))]
    result = []
    for i in range(6):
        im = front("blink" if name == "into_coffin" else "rest")
        if name == "into_coffin":
            im = im.rotate(-i * 12, Image.Resampling.NEAREST)
            opacity = max(0, 1 - i / 5)
        elif name == "revive":
            opacity = .2 + .8 * i / 5
        else:
            opacity = .4 + .15 * math.sin(i * math.pi / 3)
        im.putalpha(im.getchannel("A").point(lambda a: round(a * opacity)))
        result.append((im, 6 if name != "ghost_neutral" else 10))
    return result


def build_family(pack, special=False):
    names = ["special_land", "special_pose"] if special else ["neutral", "walk_back", "walk_front", "skill_ready", "kachidoki",
                                       "into_coffin", "ghost_raise", "ghost_neutral", "revive"]
    stem = "special" if special else "pixelart"
    sheet_name = "special_sprite_sheet" if special else "sprite_sheet"
    prefix = f"character/{pack.spec.code}/pixelart/"
    cursor, atlas, sequences, cells, tiles, gifs = 1, [], [], {}, [], {}
    circles = []
    for name in names:
        clips = frames_for(name)
        begin = cursor
        preview = []
        for im, hold in clips:
            key = hashlib.sha256(im.tobytes()).hexdigest()
            if key not in cells:
                cells[key] = len(tiles)
                tiles.append(im)
            cell = cells[key]
            atlas.append(dict(n=f"{prefix}{stem}{cursor:04d}", x=(cell % 4)*26, y=(cell//4)*26,
                              w=24, h=24, fx=-116, fy=-106, fw=256, fh=256))
            cursor += hold
            preview.extend([im.resize((192,192), Image.Resampling.NEAREST)] * hold)
        kind = ("pass" if name in ("special_land", "into_coffin", "ghost_raise") else
                "loop" if name in ("neutral", "walk_back", "walk_front", "kachidoki", "ghost_neutral") else "once")
        sequences.append(dict(name=name, kind=kind, begin=begin, end=cursor-1))
        circles.append(dict(begin=begin+1, data=[dict(x=0,y=0,r=8.3)]
                            if name in ("neutral", "walk_back", "walk_front") else []))
        out = pack.evidence_path(f"pixel/{name}.gif")
        out.parent.mkdir(parents=True, exist_ok=True)
        preview[0].save(out, save_all=True, append_images=preview[1:], duration=20, loop=0, disposal=2)
        gifs[name] = str(out)
    height = 2 ** math.ceil(math.log2(max(32, math.ceil(len(tiles)/4)*26)))
    sheet = Image.new("RGBA", (128,height))
    for i, tile in enumerate(tiles):
        sheet.alpha_composite(tile, ((i%4)*26,(i//4)*26))
    buf = io.BytesIO(); sheet.save(buf, "PNG")
    pack.write_asset("common", prefix+sheet_name+".png", C.wf_assets.png_encode(buf.getvalue()), owner="pixel")
    timeline = dict(sequences=sequences, circles=[dict(path="unit_body", frames=circles)],
                    points=[dict(path="hp_gauge", frames=[dict(begin=1,data=[dict(x=0,y=-10)])])], sounds=[])
    if special:
        # 原生五星展示动画不带战斗碰撞体/血条；UI依次请求这两个固定名称。
        timeline.update(circles=[], points=[])
    metadata = {sheet_name+".atlas": atlas,
                stem+".frame": dict(name=prefix+stem,x=-128,y=-128,scale=6,smoothing=False),
                stem+".timeline": timeline}
    for name, tree in metadata.items():
        pack.write_asset("common", prefix+name+".amf3.deflate", C.amf_bytes(tree), owner="pixel")
    return dict(sequences=sequences, sheet_size=list(sheet.size), unique_tiles=len(tiles), previews=gifs)


def build(pack):
    result = dict(status="candidate", summary="海豹球自有9个常规动作＋落地/摆姿势2段展示动作",
                  regular=build_family(pack), special=build_family(pack, True),
                  source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SOURCE.glob('*.png'))})
    pack.write_evidence("pixel-report.json",result)
    return result

"""Add transparent generated particles behind selected WF pixelart actions.

The source frame/timeline documents and every visible source pixel are preserved.
Only a new offline output directory is written; all frames are resolved before
editing so a sparse atlas cannot accidentally leak an edit into another action.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

from wf_generated_vfx import (check_output, file_hash, pack_images, previews, read_image,
                              read_tree, split_frames, write_tree)


def restore_frame(sheet, entry):
    x, y, w, h = (int(entry[k]) for k in ("x","y","w","h"))
    if min(x,y) < 0 or min(w,h) <= 0 or x+w > sheet.width or y+h > sheet.height:
        raise ValueError("atlas crop outside source sheet")
    tile = sheet.convert("RGBA").crop((x,y,x+w,y+h))
    if entry.get("r", False):
        # Starling SubTexture maps local UV (u,v) to stored (1-v,u):
        # atlas pixels are clockwise, so Pillow must undo them anticlockwise.
        tile = tile.transpose(Image.Transpose.ROTATE_90)
    fw, fh = int(entry.get("fw",tile.width)), int(entry.get("fh",tile.height))
    dx, dy = -int(entry.get("fx",0)), -int(entry.get("fy",0))
    if min(fw,fh) <= 0 or max(fw,fh) > 4096 or min(dx,dy) < 0:
        raise ValueError("invalid untrimmed frame geometry")
    if dx+tile.width > fw or dy+tile.height > fh:
        raise ValueError("trimmed image exceeds untrimmed frame")
    canvas = Image.new("RGBA",(fw,fh))
    canvas.paste(tile,(dx,dy))
    return canvas


def frame_index(entries, prefix):
    indexed = {}
    for entry in entries:
        name = entry.get("n", "")
        suffix = name[len(prefix):] if name.startswith(prefix) else ""
        if not suffix.isdigit():
            continue
        number = int(suffix)
        if number in indexed or number < 1:
            raise ValueError("duplicate or nonpositive atlas frame")
        indexed[number] = entry
    if not indexed:
        raise ValueError("no atlas frames match frame.name")
    return sorted(indexed), indexed


def entry_for_frame(index, frame):
    keys, entries = index
    # flatomo FrameAnimationSource fills up to each suffix, inclusively.
    # The suffix is the END frame of a held image, not its starting keyframe.
    # Taking the preceding image leaks walk_back into the next walk_front loop.
    if not isinstance(frame, int) or not 1 <= frame <= keys[-1]:
        raise ValueError("frame outside atlas endpoint range")
    pos = bisect.bisect_left(keys,frame)
    return entries[keys[pos]]


def overlay_behind(body, effect, position, opacity):
    if not 0 <= opacity <= 1:
        raise ValueError("opacity must be within 0..1")
    background = Image.new("RGBA",body.size)
    effect = effect.convert("RGBA").copy()
    effect.putalpha(effect.getchannel("A").point(lambda a: round(a*opacity)))
    background.paste(effect,position)
    # Preserve even semitransparent original pixels byte-for-byte, not a normal
    # alpha composite which would change their RGB/alpha over the new backdrop.
    mask = body.getchannel("A").point(lambda a: 255 if a else 0)
    background.paste(body,(0,0),mask)
    return background


def animate_overlays(frames, vfx, timeline, actions, vfx_size, opacity,
                     *, anchor=None, hold=3):
    if not frames or not vfx or vfx_size <= 0 or hold <= 0 or not 0 <= opacity <= 1:
        raise ValueError("invalid overlay parameters")
    if any(im.size != frames[0].size for im in frames):
        raise ValueError("all source frames must share untrimmed geometry")
    if vfx_size > max(frames[0].size):
        raise ValueError("effect size exceeds source canvas")
    sequences = timeline["sequences"]
    known = {s["name"] for s in sequences}
    if not actions <= known:
        raise ValueError("unknown action name")
    schedule = {}
    for sequence in sequences:
        begin, end = sequence["begin"], sequence["end"]
        if not 1 <= begin <= end <= len(frames):
            raise ValueError("timeline action is outside frame range")
        if sequence["name"] in actions:
            for number in range(begin,end+1):
                if number in schedule:
                    raise ValueError("selected actions overlap")
                schedule[number] = (number-begin,end-begin+1)
    effects = []
    for image in vfx:
        ratio = vfx_size/max(image.size)
        effects.append(image.resize((max(1,round(image.width*ratio)),
                                     max(1,round(image.height*ratio))),Image.Resampling.NEAREST))
    anchor = anchor or (frames[0].width/2,frames[0].height/2)
    result, changed = [], 0
    for number, body in enumerate(frames,1):
        if number not in schedule:
            result.append(body.copy())
            continue
        local, length = schedule[number]
        envelope = math.sin(math.pi*local/(length-1))**2 if length>1 else 0
        effect = effects[(local//hold) % len(effects)]
        xy = (round(anchor[0]-effect.width/2),round(anchor[1]-effect.height/2))
        current = overlay_behind(body,effect,xy,opacity*envelope)
        mask = body.getchannel("A").point(lambda a: 255 if a else 0)
        difference = ImageChops.difference(body,current)
        protected = Image.new("RGBA",body.size)
        protected.paste(difference,(0,0),mask)
        if any(protected.getchannel(c).getbbox() for c in "RGBA"):
            raise ValueError("source body pixel changed")
        changed += current.tobytes() != body.tobytes()
        result.append(current)
    return result, dict(body_pixels_changed=0,frames_changed=changed,frame_count=len(frames),
                        actions=sorted(actions),vfx_size=vfx_size,opacity=opacity,hold=hold,
                        timing_source="assembly choice; action ranges unchanged")


def _document(source, stem):
    for suffix in (".amf3.deflate", ".json"):
        path = source/(stem+suffix)
        if path.is_file():
            return path
    raise FileNotFoundError(f"{stem}.amf3.deflate or .json")


def assemble_pixelart(source, vfx_sheet, count, frame_size, output, *, kind="pixelart",
                      actions=None, vfx_size=32, opacity=0.6, hold=3):
    source, vfx_sheet = Path(source), Path(vfx_sheet)
    output = check_output(Path(output),[source,vfx_sheet])
    if kind not in ("pixelart","special"):
        raise ValueError("kind must be pixelart or special")
    sheet_stem = "sprite_sheet" if kind == "pixelart" else "special_sprite_sheet"
    sheet_path = source/(sheet_stem+".png")
    atlas_path = _document(source,sheet_stem+".atlas")
    frame_path = _document(source,kind+".frame")
    timeline_path = _document(source,kind+".timeline")
    inputs = [sheet_path,atlas_path,frame_path,timeline_path,vfx_sheet]
    before = {str(p.resolve()):file_hash(p) for p in inputs}
    atlas, frame, timeline = read_tree(atlas_path),read_tree(frame_path),read_tree(timeline_path)
    index = frame_index(atlas,frame["name"])
    total = max(s["end"] for s in timeline["sequences"])
    if not isinstance(total,int) or not 1 <= total <= 10000:
        raise ValueError("timeline frame count outside supported bounds")
    sheet = read_image(sheet_path)
    originals = [restore_frame(sheet,entry_for_frame(index,n)) for n in range(1,total+1)]
    effects = split_frames(read_image(vfx_sheet),count,frame_size)
    actions = set(actions) if actions is not None else (
        {"skill_ready","kachidoki","special_pose"} & {s["name"] for s in timeline["sequences"]})
    rendered, report = animate_overlays(originals,effects,timeline,actions,vfx_size,opacity,
        anchor=(-frame.get("x",0),-frame.get("y",0)),hold=hold)
    # Keep the source's sparse endpoint numbering: record N is the image held for
    # frames prev+1..N, so one record per source endpoint reproduces the official
    # cadence exactly.  Emitting one record per tick instead grew
    # fox_oracle_autumn from 157 records / 0.18 Mpx to 550 records / 1.04 Mpx.
    endpoints = [n for n in index[0] if n < total] + [total]
    names = [f"{frame['name']}{n:04d}" for n in endpoints]
    sheet, entries = pack_images([rendered[n-1] for n in endpoints],names,trim=True,
                                 dedup=True,max_width=None)
    report.update(source_hashes=before,frame=frame,kind=kind,source_atlas_entries=len(index[0]),
                  output_atlas_entries=len(entries),
                  output_atlas_rectangles=len({(e["x"],e["y"],e["w"],e["h"]) for e in entries}),
                  sheet_size=list(sheet.size),sequences=timeline["sequences"])
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".pixelart-vfx-",dir=output.parent) as tmp:
        target = Path(tmp)/"result"
        target.mkdir()
        sheet.save(target/(sheet_stem+".png"))
        write_tree(target/(sheet_stem+".atlas.amf3.deflate"),entries)
        (target/(sheet_stem+".atlas.json")).write_text(json.dumps(entries,indent=2),encoding="utf-8")
        for path, tree in [(frame_path,frame),(timeline_path,timeline)]:
            shutil.copyfile(path,target/path.name)
            if path.suffix == ".json":
                write_tree(target/(path.stem+".amf3.deflate"),tree)
        for sequence in timeline["sequences"]:
            if sequence["name"] not in actions:
                continue
            selected = rendered[sequence["begin"]-1:sequence["end"]]
            # Crop preview only to the stable union; game frames stay 256x256.
            boxes = [im.getchannel("A").getbbox() for im in selected]
            boxes = [b for b in boxes if b]
            if boxes:
                box = (min(b[0] for b in boxes),min(b[1] for b in boxes),
                       max(b[2] for b in boxes),max(b[3] for b in boxes))
                selected = [im.crop(box) for im in selected]
            previews(selected,target,hold=1,name=sequence["name"])
        after = {str(p.resolve()):file_hash(p) for p in inputs}
        if before != after:
            raise ValueError("source changed during assembly")
        (target/"assembly.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        target.rename(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pixelart",required=True,type=Path)
    parser.add_argument("--vfx-sheet",required=True,type=Path)
    parser.add_argument("--frames",required=True,type=int)
    parser.add_argument("--frame-size",required=True,type=int,nargs=2,metavar=("W","H"))
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--kind",choices=("pixelart","special"),default="pixelart")
    parser.add_argument("--actions",nargs="+")
    parser.add_argument("--vfx-size",type=int,default=32)
    parser.add_argument("--opacity",type=float,default=0.6)
    parser.add_argument("--hold",type=int,default=3)
    args = parser.parse_args()
    result = assemble_pixelart(args.source_pixelart,args.vfx_sheet,args.frames,tuple(args.frame_size),
        args.output,kind=args.kind,actions=args.actions,vfx_size=args.vfx_size,
        opacity=args.opacity,hold=args.hold)
    print(json.dumps(result,ensure_ascii=False))


if __name__ == "__main__":
    main()

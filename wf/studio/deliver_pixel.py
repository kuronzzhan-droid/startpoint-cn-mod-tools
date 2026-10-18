"""Compile action replacements while preserving every untouched atlas region."""
from __future__ import annotations

from bisect import bisect_left
import copy

from PIL import Image

from wf_pixelart_vfx import frame_index, restore_frame

from .deliver_media import MediaResult, encode_png, encode_tree, png, require_raw, tree
from .drafts import DraftError, sha256


def _prepared_frames(store, cid, change, frame, first):
    fw, fh = int(first.get("fw", first["w"])), int(first.get("fh", first["h"]))
    origin = -float(frame.get("x", 0)), -float(frame.get("y", 0))
    prepared = []
    for item in change["params"]["frames"]:
        raw = store.read_file(cid, item["file"])
        if raw is None or sha256(raw) != item["sha256"]:
            raise DraftError(f"问题：像素源帧 SHA-256 不符：{item['file']}")
        image = png(raw)
        if image.size != (item["width"], item["height"]) or image.width > fw or image.height > fh:
            raise DraftError("问题：像素源帧尺寸与草稿或官方帧框不一致")
        if image.getchannel("A").getextrema()[0] == 255:
            raise DraftError("问题：像素源帧必须有透明背景")
        dx, dy = (round(origin[i] - float(item["anchor"][i])) for i in (0, 1))
        box = image.getchannel("A").getbbox()
        if box and (box[0] + dx < 0 or box[1] + dy < 0 or box[2] + dx > fw or box[3] + dy > fh):
            raise DraftError("问题：像素锚点使可见像素超出官方帧框")
        canvas = Image.new("RGBA", (fw, fh))
        canvas.paste(image, (dx, dy))
        box = canvas.getchannel("A").getbbox() or (0, 0, 1, 1)
        duration = item["duration"]
        if type(duration) is not int or duration < 1:
            raise DraftError("问题：像素帧停留时长必须为正整数")
        prepared.append((canvas.crop(box), box, duration, fw, fh))
    if not prepared or sum(p[2] for p in prepared) != change["params"]["totalFrames"]:
        raise DraftError("问题：像素动作总时长与源帧不一致")
    return prepared


def _append_pack(original, images, maximum):
    """Append below or beside the original rectangle; its pixels never move."""
    candidates = []
    widths = sorted({original.width, 128, 256, 512, 1024, 2048, maximum})
    for width in widths:
        if width < original.width or width > maximum:
            continue
        for beside in (False, True):
            left, top = (original.width + 1, 1) if beside else (1, original.height + 1)
            x, y, row = left, top, 0
            positions = []
            for image in images:
                if x + image.width + 1 > width:
                    x, y, row = left, y + row + 1, 0
                if x + image.width + 1 > width or y + image.height + 1 > maximum:
                    break
                positions.append((x, y))
                x += image.width + 1
                row = max(row, image.height)
            else:
                actual_w = max(original.width, max(x + im.width + 1 for (x, y), im in zip(positions, images)))
                actual_h = max(original.height, max(y + im.height + 1 for (x, y), im in zip(positions, images)))
                candidates.append((actual_w * actual_h, actual_w, actual_h, positions))
    if not candidates:
        raise DraftError("问题：像素图集预算超过 4096²（包含战斗图集 margin），不能生成")
    _, width, height, positions = min(candidates, key=lambda c: c[:3])
    packed = Image.new("RGBA", (width, height))
    packed.paste(original, (0, 0))
    for image, point in zip(images, positions):
        packed.paste(image, point)
    return packed, positions


def _compile_family(source, store, changeset, family, changes):
    result = MediaResult()
    cid, code = changeset["characterId"], changeset["code"]
    base = f"character/{code}/pixelart/"
    sheet_name = "sprite_sheet" if family == "pixelart" else "special_sprite_sheet"
    paths = [base + sheet_name + ".png", base + sheet_name + ".atlas.amf3.deflate",
             base + family + ".frame.amf3.deflate", base + family + ".timeline.amf3.deflate"]
    original = [require_raw(source, "common", name) for name in paths]
    sheet, atlas, frame, timeline = png(original[0]), tree(original[1]), tree(original[2]), tree(original[3])
    keys, entries = frame_index(atlas, frame["name"])
    sequences = timeline.get("sequences", [])
    by_name = {s["name"]: s for s in sequences}
    if len(by_name) != len(sequences):
        raise DraftError("问题：原像素时间轴有重复动作槽")
    prepared, groups = [], []
    for change in changes:
        action = change["target"]["action"]
        if action not in by_name:
            raise DraftError(f"问题：{family}/{action} 不是已有动作槽")
        sequence = by_name[action]
        length = sequence["end"] - sequence["begin"] + 1
        if change["params"]["originalTotalFrames"] != length:
            raise DraftError(f"问题：像素动作旧时长断言失败：{action}")
        frames = _prepared_frames(store, cid, change, frame, entries[keys[0]])
        if sum(item[2] for item in frames) != length and sequence != sequences[-1]:
            raise DraftError("问题：非末尾动作必须保持原总时长，否则会改动其它动作槽；可重新分配各帧时长")
        if any(s["name"] != action and s["begin"] <= sequence["end"] and s["end"] >= sequence["begin"]
               for s in sequences):
            raise DraftError("问题：原时间轴动作槽重叠，不能保证其它动作槽逐字节不变")
        groups.append((change, frames, len(prepared)))
        prepared.extend(frames)
    maximum = 4094 if family == "pixelart" else 4096
    packed, positions = _append_pack(sheet, [item[0] for item in prepared], maximum)
    target_timeline = copy.deepcopy(timeline)
    target_by_name = {s["name"]: s for s in target_timeline["sequences"]}
    target_entries = dict(entries)
    foreign = [copy.deepcopy(e) for e in atlas if e not in entries.values()]
    for change, frames, start in groups:
        action = change["target"]["action"]
        old = by_name[action]
        total = sum(item[2] for item in frames)
        begin = old["begin"]
        # Sparse atlas endpoints hold backwards. Split the preceding range
        # before removing this slot's records, so edits cannot leak out.
        if begin > 1 and begin - 1 not in target_entries:
            donor = copy.deepcopy(entries[keys[bisect_left(keys, begin - 1)]])
            donor["n"] = frame["name"] + f"{begin - 1:04d}"
            target_entries[begin - 1] = donor
        for endpoint in list(target_entries):
            if begin <= endpoint <= old["end"]:
                del target_entries[endpoint]
        target_by_name[action].update(begin=begin, end=begin + total - 1)
        cursor = begin - 1
        for index, (image, box, duration, fw, fh) in enumerate(frames):
            cursor += duration
            x, y = positions[start + index]
            entry = copy.deepcopy(entries[keys[bisect_left(keys, old["begin"])]])
            entry.update(n=frame["name"] + f"{cursor:04d}", x=x, y=y, w=image.width, h=image.height,
                         fx=-box[0], fy=-box[1], fw=fw, fh=fh)
            if "r" in entry:
                entry["r"] = False
            target_entries[cursor] = entry
        result.assertions.append({"kind": "pixel_action", "family": family, "action": action,
                                  "old": copy.deepcopy(old), "value": copy.deepcopy(target_by_name[action])})
    target_atlas = [target_entries[k] for k in sorted(target_entries)] + foreign
    outputs = [encode_png(packed), encode_tree(target_atlas), original[2], encode_tree(target_timeline)]
    result.members.update({("common", logical): raw for logical, raw in zip(paths, outputs)})
    result.checks.append({"state": "满足", "code": "studio.pixel.budget",
                          "message": f"{family} 实际图集 {packed.width}×{packed.height}，预算 ≤4096²；frame.scale/锚点保留"})
    _verify_untouched(sheet, atlas, frame, timeline, packed, target_atlas, target_timeline,
                      {c["target"]["action"] for c in changes})
    return result


def _verify_untouched(old_sheet, old_atlas, frame, old_timeline, new_sheet, new_atlas, new_timeline, changed):
    old_keys, old_entries = frame_index(old_atlas, frame["name"])
    new_keys, new_entries = frame_index(new_atlas, frame["name"])
    new_sequences = {s["name"]: s for s in new_timeline["sequences"]}
    compared = set()
    for sequence in old_timeline["sequences"]:
        if sequence["name"] in changed:
            continue
        if new_sequences[sequence["name"]] != sequence:
            raise DraftError("问题：未替换动作的时间轴发生变化")
        for pos in range(sequence["begin"], sequence["end"] + 1):
            old_key, new_key = old_keys[bisect_left(old_keys, pos)], new_keys[bisect_left(new_keys, pos)]
            if (old_key, new_key) in compared:
                continue
            compared.add((old_key, new_key))
            old = restore_frame(old_sheet, old_entries[old_key])
            new = restore_frame(new_sheet, new_entries[new_key])
            if old.size != new.size or old.tobytes() != new.tobytes():
                raise DraftError("问题：未替换动作帧逐字节回读不一致")


def compile_pixels(source, store, changeset: dict) -> MediaResult:
    result = MediaResult()
    for family in ("pixelart", "special"):
        changes = [c for c in changeset["changes"]
                   if c["kind"] == "pixel_action" and c["target"]["family"] == family]
        if not changes:
            continue
        part = _compile_family(source, store, changeset, family, changes)
        result.members.update(part.members)
        result.assertions.extend(part.assertions)
        result.checks.extend(part.checks)
    return result

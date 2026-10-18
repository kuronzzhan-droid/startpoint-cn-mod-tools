"""Compile action replacements while preserving every untouched atlas region."""
from __future__ import annotations

from bisect import bisect_left
import copy

from PIL import Image

from wf_pixelart_vfx import frame_index, restore_frame

from .deliver_media import MediaResult, draft_file, encode_png, encode_tree, png, require_raw, tree
from .deliver_pixel_pack import budget_check, repack
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
    """Compatibility helper for callers that reserve the entire old sheet."""
    reserved = {"x": 0, "y": 0, "w": original.width, "h": original.height}
    return repack(original, [reserved], [reserved], images, maximum)


def _compile_family(source, store, changeset, family, changes, original=None):
    result = MediaResult()
    cid, code = changeset["characterId"], changeset["code"]
    base = f"character/{code}/pixelart/"
    sheet_name = "sprite_sheet" if family == "pixelart" else "special_sprite_sheet"
    paths = [base + sheet_name + ".png", base + sheet_name + ".atlas.amf3.deflate",
             base + family + ".frame.amf3.deflate", base + family + ".timeline.amf3.deflate"]
    if original is None:
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
        total = sum(item[2] for item in frames)
        if total != length and sequence["end"] != max(s["end"] for s in sequences):
            raise DraftError("问题：非末尾动作必须保持原总时长，否则会改动其它动作槽；可重新分配各帧时长")
        new_end = sequence["begin"] + total - 1
        outside = [key for key in keys if sequence["end"] < key <= new_end]
        if outside:
            raise DraftError(f"问题：末尾动作加长会覆盖序列外的原图集端点：{outside}")
        if any(s["name"] != action and s["begin"] <= sequence["end"] and s["end"] >= sequence["begin"]
               for s in sequences):
            raise DraftError("问题：原时间轴动作槽重叠，不能保证其它动作槽逐字节不变")
        groups.append((change, frames))
        prepared.extend(frames)
    maximum = 4094 if family == "pixelart" else 4096
    target_timeline = copy.deepcopy(timeline)
    target_by_name = {s["name"]: s for s in target_timeline["sequences"]}
    target_entries = dict(entries)
    foreign = [copy.deepcopy(e) for e in atlas if e not in entries.values()]
    new_entries = []
    for change, frames in groups:
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
        for image, box, duration, fw, fh in frames:
            cursor += duration
            entry = copy.deepcopy(entries[keys[bisect_left(keys, old["begin"])]])
            entry.update(n=frame["name"] + f"{cursor:04d}", x=0, y=0, w=image.width, h=image.height,
                         fx=-box[0], fy=-box[1], fw=fw, fh=fh)
            if "r" in entry:
                entry["r"] = False
            target_entries[cursor] = entry
            new_entries.append(entry)
        result.assertions.append({"kind": "pixel_action", "family": family, "action": action,
                                  "old": copy.deepcopy(old), "value": copy.deepcopy(target_by_name[action])})
    retained = [entry for entry in target_entries.values() if not any(entry is new for new in new_entries)] + foreign
    # Identical new frames share one atlas region (official sheets reuse regions too).
    unique, slots, seen = [], [], {}
    for item in prepared:
        image = item[0]
        signature = (image.size, image.tobytes())
        if signature not in seen:
            seen[signature] = len(unique)
            unique.append(image)
        slots.append(seen[signature])
    packed, unique_positions = repack(sheet, atlas, retained, unique, maximum)
    positions = [unique_positions[slot] for slot in slots]
    for entry, (x, y) in zip(new_entries, positions):
        entry.update(x=x, y=y)
    target_atlas = [target_entries[k] for k in sorted(target_entries)] + foreign
    outputs = [encode_png(packed), encode_tree(target_atlas), original[2], encode_tree(target_timeline)]
    result.members.update({("common", logical): raw for logical, raw in zip(paths, outputs)})
    result.checks.append(budget_check(family, packed))
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


def compile_family_replacement(source, store, changeset, change) -> MediaResult:
    """Whole-family remap: rebuild from the base character and the mapping, then
    require the draft files to match the rebuild exactly (determinism + drift)."""
    from .pixel_workshop import family_paths, normalize_mapping, read_family_raw, remap_family
    result = MediaResult()
    cid, code = changeset["characterId"], changeset["code"]
    family, params = change["target"]["family"], change["params"]
    if params.get("mode") == "import":
        return _compile_import(source, store, changeset, change)
    if params.get("mode") != "remap":
        raise DraftError(f"问题：不支持的整族替换方式 {params.get('mode')}")
    base = params["base"]
    base_raws = read_family_raw(source, base["code"], family)
    if base_raws is None:
        raise DraftError(f"问题：母本 {base['characterId']} 缺 {family} 像素族")
    for logical, raw in zip(family_paths(base["code"], family), base_raws):
        if sha256(raw) != base["files"].get(logical):
            raise DraftError(f"问题：母本文件已变化（{logical}），请重新映射")
    rebuilt = remap_family(base_raws, base["code"], code, normalize_mapping(params["mapping"]))
    paths = family_paths(code, family)
    by_logical = {entry["logical"]: entry for entry in change["files"]}
    if set(by_logical) != set(paths):
        raise DraftError("问题：整族替换必须正好包含四件文件")
    for index, logical in enumerate(paths):
        stored = draft_file(source, store, cid, by_logical[logical])
        if index == 0:
            if png(stored).tobytes() != rebuilt["sheet"].convert("RGBA").tobytes():
                raise DraftError("问题：草稿 sprite_sheet 与按母本 + 映射表重算的结果不一致")
        elif stored != rebuilt["stored"][index]:
            raise DraftError(f"问题：草稿 {logical} 与按母本重算的结果不一致")
        result.members["common", logical] = stored
    result.assertions.append({"kind": "pixel_family", "family": family, "base": base["characterId"],
                              "mapping": len(params["mapping"])})
    return result


def _compile_import(source, store, changeset, change) -> MediaResult:
    """Imported family: the draft files are the content; names must carry this character's code."""
    from .pixel_workshop import decode_family, family_paths
    result = MediaResult()
    cid, code, family = changeset["characterId"], changeset["code"], change["target"]["family"]
    paths = family_paths(code, family)
    by_logical = {entry["logical"]: entry for entry in change["files"]}
    if set(by_logical) != set(paths):
        raise DraftError("问题：导入的整族替换必须正好包含本角色的四件文件（草稿角色未绑定？）")
    stored = [draft_file(source, store, cid, by_logical[logical]) for logical in paths]
    data = decode_family(stored)
    prefix = f"character/{code}/"
    if not data["frame"].get("name", "").startswith(prefix) or any(
            isinstance(e, dict) and not str(e.get("n", "")).startswith(prefix) for e in data["atlas"]):
        raise DraftError(f"问题：导入集的 atlas/frame 名前缀不是 {prefix}")
    for key, entry in data["entries"].items():
        try:
            restore_frame(data["sheet"], entry)
        except ValueError as exc:
            raise DraftError(f"问题：导入集端点 {key} 越界：{exc}") from None
    result.members.update({("common", logical): raw for logical, raw in zip(paths, stored)})
    result.assertions.append({"kind": "pixel_family", "family": family, "mode": "import",
                              "source": change["params"]["source"].get("name")})
    return result


def compile_pixels(source, store, changeset: dict) -> MediaResult:
    from .pixel_workshop import family_paths
    result = MediaResult()
    for family in ("pixelart", "special"):
        replaced = [c for c in changeset["changes"]
                    if c["kind"] == "pixel_family" and c["target"]["family"] == family]
        changes = [c for c in changeset["changes"]
                   if c["kind"] == "pixel_action" and c["target"]["family"] == family]
        if len(replaced) > 1:
            raise DraftError(f"问题：{family} 有多个整族替换")
        original = None
        if replaced:
            part = compile_family_replacement(source, store, changeset, replaced[0])
            result.members.update(part.members)
            result.assertions.extend(part.assertions)
            original = [part.members["common", logical] for logical in family_paths(changeset["code"], family)]
            if not changes:
                result.checks.append(budget_check(family, png(original[0])))
        if not changes:
            continue
        part = _compile_family(source, store, changeset, family, changes, original=original)
        result.members.update(part.members)
        result.assertions.extend(part.assertions)
        result.checks.extend(part.checks)
    return result

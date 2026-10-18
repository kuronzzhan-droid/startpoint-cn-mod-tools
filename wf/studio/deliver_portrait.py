"""Portrait assets and assertion-backed geometry leaves for local delivery."""
from __future__ import annotations

import zlib

from PIL import Image

import wf_atf
import wf_assets
import wf_mod_tool as core
import wf_ui_derive_gate as gate
from wf.chars.support import images

from .deliver_media import MediaResult, draft_file, encode_png, png, read_root, require_raw, tree
from .drafts import DraftError, sha256

TABLES = {
    "character_image": "master/generated/character_image.orderedmap",
    "trimmed_image": "master/generated/trimmed_image.orderedmap",
    "full_shot_image_attribute": "master/character/full_shot_image_attribute.orderedmap",
}
SHEET = "ui/illustration_setting_sprite_sheet.png"
ATLAS = "ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"


def geometry_key(table: str, cid: str, code: str, form: str) -> tuple[str, ...]:
    if table == "trimmed_image":
        return (f"character/{code}/ui/full_shot_1440_1920_{form}",)
    return cid, form


def leaf_value(raw: bytes | None, keys: tuple[str, ...]) -> str | None:
    if raw is None:
        return None
    for depth, key in enumerate(keys):
        ordered = core.read_orderedmap_raw_rows_from_bytes(raw)
        if key not in ordered.keys:
            return None
        raw = ordered.rows[ordered.keys.index(key)]
        if depth == len(keys) - 1:
            return zlib.decompress(raw).decode("utf-8") if raw else ""
    raise AssertionError("empty geometry key")


def replace_leaf(raw: bytes, keys: tuple[str, ...], old: str | None, value: str) -> bytes:
    if leaf_value(raw, keys) != old:
        raise DraftError(f"问题：定位表旧值断言失败：{'/'.join(keys)}")
    ordered = core.read_orderedmap_raw_rows_from_bytes(raw)
    key = keys[0]
    if key not in ordered.keys:
        raise DraftError(f"问题：不能通过立绘替换新增定位表键 {key}")
    position = ordered.keys.index(key)
    if len(keys) > 1:
        ordered.rows[position] = replace_leaf(ordered.rows[position], keys[1:], old, value)
    else:
        ordered.rows[position] = zlib.compress(value.encode("utf-8")) if value else b""
    return core.build_orderedmap_raw_rows(ordered)


def snapshot_geometry(source, cid: str, code: str, form: str) -> dict:
    """Capture preimages at draft editing time, rather than at build time."""
    result = {}
    for name, logical in TABLES.items():
        raw = source.raw(logical)
        result[name] = {"value": leaf_value(raw, geometry_key(name, cid, code, form)),
                        "sha256": sha256(raw) if raw is not None else None}
    return result


def _geometry(source, result, change, cid, code):
    form = change["target"]["form"]
    before = change["params"].get("tableBefore")
    if not before or set(before) != set(TABLES):
        raise DraftError("问题：旧立绘草稿缺三张定位表旧值断言，请重新保存立绘裁剪")
    for table, logical in TABLES.items():
        raw = require_raw(source, "common", logical)
        keys = geometry_key(table, cid, code, form)
        expected = before[table]
        if sha256(raw) != expected["sha256"] or leaf_value(raw, keys) != expected["value"]:
            raise DraftError(f"问题：定位表旧值断言失败：{table}/{'/'.join(keys)}")
        value = change["params"]["tableRows"].get(table, expected["value"])
        if value is None:
            raise DraftError(f"问题：定位表缺少目标行：{table}/{'/'.join(keys)}")
        current = result.members.get(("common", logical), raw)
        if value != expected["value"]:
            current = replace_leaf(current, keys, expected["value"], value)
        result.members["common", logical] = current
        result.assertions.append({"kind": "portrait_geometry", "logical": logical,
                                  "key": list(keys), "old": expected["value"], "value": value,
                                  "before_sha256": expected["sha256"]})


def _draw_form(sheet, atlas, form, master):
    touched = 0
    for entry in atlas:
        if not str(entry.get("n", "")).endswith("_" + form):
            continue
        x, y, w, h = (int(entry[k]) for k in ("x", "y", "w", "h"))
        if min(x, y) < 0 or min(w, h) < 1 or x + w > sheet.width or y + h > sheet.height:
            raise DraftError("问题：立绘切换 atlas 格子越界")
        size = (h, w) if entry.get("r") else (w, h)
        tile = images.fit_rgba(master, size)
        if entry.get("r"):
            tile = tile.transpose(Image.Transpose.ROTATE_270)
        sheet.paste(tile, (x, y))
        touched += 1
    if not touched:
        raise DraftError(f"问题：立绘切换 atlas 缺少 _{form} 格子")


def compile_portraits(source, store, changeset: dict) -> MediaResult:
    result = MediaResult()
    changes = [c for c in changeset["changes"] if c["kind"] == "portrait"]
    if not changes:
        return result
    cid, code = changeset["characterId"], changeset["code"]
    prefix = f"character/{code}/"
    atlas_raw = require_raw(source, "common", prefix + ATLAS)
    atlas = tree(atlas_raw)
    sheet = png(require_raw(source, "medium", prefix + SHEET))
    for change in changes:
        form = change["target"]["form"]
        _geometry(source, result, change, cid, code)
        expected = {prefix + f"ui/{slot}_{form}.png" for slot in gate.OFFICIAL_ICON_SIZES}
        expected.add(prefix + f"ui/skill_cutin_{form}.png")
        full = prefix + f"ui/full_shot_1440_1920_{form}.png"
        atf_logical = prefix + f"ui/skill_cutin_{form}.atf.deflate"
        permitted = expected | {full, atf_logical, prefix + SHEET}
        seen = set()
        for entry in change["files"]:
            logical = entry["logical"]
            wanted_root = "android" if logical == atf_logical else "medium"
            if logical not in permitted or entry["root"] != wanted_root or logical in seen:
                raise DraftError(f"问题：立绘草稿含非目标成员、错误根或重复成员：{logical}")
            stored = draft_file(source, store, cid, entry)
            if logical == full and change["params"]["source"] == "current":
                original = require_raw(source, "medium", full)
                if wf_assets.png_decode(stored) != wf_assets.png_decode(original):
                    raise DraftError("问题：重新裁剪草稿不能改动原 full_shot")
                stored = original
            if logical in expected:
                slot = logical.rsplit("/", 1)[1][:-6]
                if png(stored).size != gate.OFFICIAL_ICON_SIZES[slot]:
                    raise DraftError(f"问题：图标 {slot} 尺寸不符合官方槽")
            seen.add(logical)
            if logical != prefix + SHEET:
                result.members[entry["root"], logical] = stored
        if not expected.issubset(seen):
            raise DraftError(f"问题：立绘草稿缺少图标或 cutin：{sorted(expected - seen)}")
        if ("medium", full) not in result.members:
            result.members["medium", full] = require_raw(source, "medium", full)
        master = png(result.members["medium", full])
        if change["params"]["source"] == "current":
            from .portrait import trim_transparent
            master = trim_transparent(master)[0]
        _draw_form(sheet, atlas, form, master)
        cutin = result.members["medium", prefix + f"ui/skill_cutin_{form}.png"]
        if ("android", atf_logical) not in result.members:
            reference = read_root(source, "android", atf_logical)
            result.members["android", atf_logical] = wf_atf.deflate(wf_atf.build_cutin_atf(
                wf_assets.png_decode(cutin), wf_atf.inflate(reference) if reference else None))
        atf = wf_atf.parse_atf(wf_atf.inflate(result.members["android", atf_logical]))
        if (atf["w"], atf["h"]) != png(cutin).size:
            raise DraftError("问题：cutin PNG 与 Android ATF 尺寸不一致")
    result.members["medium", prefix + SHEET] = encode_png(sheet)
    result.members["common", prefix + ATLAS] = atlas_raw
    result.checks.append({"state": "满足", "code": "studio.portrait.assets",
                          "message": "立绘、十图标、cutin PNG/Android ATF、切换 atlas 与三表旧值断言已编译"})
    return result

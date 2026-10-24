"""Small read-only helpers for public equipment descriptions and native icons."""
from __future__ import annotations

import io
import re
import zlib
from collections import defaultdict

import wf_assets
import wf_describe
import wf_mod_tool as core
import wf_quest_lib

PUBLIC_TERMS = {
    "DirectAttack3": "直接攻击（三连击）", "DirectAttack2": "直接攻击（二连击）",
    "MySelf": "自身", "Direct": "直接攻击", "Flying": "浮游", "HPIncrease": "回复生命",
    "HPDecrease": "失去生命", "Revival": "复活", "Display": "显示值", "Specific": "指定",
    "Elapsed": "经过时间", "Ease": "受到的", "Collision": "碰撞", "Guts": "毅力",
    "HitLvAny": "命中（任意等级）", "Hit": "命中", "Speedup": "加速", "Adversity": "逆境",
    "Appear": "登场", "Remove": "消失", "Excess": "超出", "CT": "冷却",
    "Red": "火", "Blue": "水", "Yellow": "雷", "Green": "风", "White": "光", "Black": "暗",
}


def cell(row, index, default=""):
    return row[index] if index < len(row) else default


def integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def nested(source, logical):
    key = (logical, False, "wiki-nested")
    if key not in source._tables:
        raw = source.raw(logical)
        source._tables[key] = wf_quest_lib.parse_node(raw) if raw else {}
    return source._tables[key]


def status_points(source, logical, key):
    result = []
    for level, text in nested(source, logical).get(str(key), {}).items():
        rows = core.read_csv_lines(text)
        if rows and len(rows[0]) >= 2:
            result.append({"level": integer(level), "hp": integer(rows[0][0]),
                           "atk": integer(rows[0][1])})
    return sorted(result, key=lambda row: row["level"])


class PublicText:
    def __init__(self, source):
        self.custom = {key: "\n".join(row[0] for row in rows if row)
                       for key, rows in source.table("strings").items()}
        self.conditions = {key: cell(rows[0], 1) for key, rows in
                           source.table("condition").items() if rows}
        groups = defaultdict(list)
        texts = source.table("text")
        for cid, rows in source.table("character").items():
            if rows:
                for group in cell(rows[0], 5).split(","):
                    if group.startswith("tag_"):
                        name = texts.get(cid, [[""]])[0][0]
                        if name:
                            groups[group].append(name)
        self.groups = {key: "／".join(dict.fromkeys(names)) for key, names in groups.items()}

    def clean(self, text):
        text = re.sub(r"<icon\s+id=['\"]main['\"]\s*/?>", "【主位】", str(text))
        text = re.sub(r"<[^>]*>|::[^:]+::", "", text)
        text = re.sub(r"固有(\d+)", lambda m: self.conditions.get(m[1]) or "专属状态", text)
        text = re.sub(r"\[([A-Za-z][A-Za-z0-9_$./-]*)\]",
                      lambda m: self.custom.get(m[1], self.groups.get(m[1], "特殊效果")), text)
        text = re.sub(r"\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_$./-]+",
                      lambda m: self.groups.get(m[0], self.custom.get(m[0], "指定效果")), text)
        text = re.sub(r"(?:battle|character|item)/[^\s，。；）]+", "特殊效果", text)
        text = text.replace("2号位技能槽", "技能槽上限").replace("HP≤Excludes阈值≥", "HP低于")
        text = re.sub(r"战斗不能Base计数([+-]) ([\d.]+)%",
                      lambda m: f"复活所需碰撞次数{m[1]}{float(m[2]) / 100:g}次", text)
        for original, public in PUBLIC_TERMS.items():
            text = text.replace(original, public)
        return text.replace("经过时间时间", "经过时间").replace("(None)", "").strip()

    def override(self, key):
        return self.clean(self.custom.get(key, ""))


def learned_rows(rows, level):
    """Native equipment slots replace older learn-level rows; never sum both."""
    slots = {}
    for row in rows:
        learned = integer(cell(row, 1), 1)
        if learned <= level and (row[0] not in slots or
                                 learned > integer(slots[row[0]][1])):
            slots[row[0]] = row
    return list(slots.values())


def endpoint_row(row, kind, maximum):
    """Collapse every declared power1/first_max pair to a verified endpoint."""
    result = list(row)
    definitions = wf_describe.enum_map()["block_fields"]
    for name, base in wf_describe.layout(kind)["blocks"].items():
        field_group = "precondition" if name.startswith("precondition") else name
        fields = definitions.get(field_group, [])
        for offset, field, _ in fields:
            if field.endswith(".power1") and base + offset + 1 < len(result):
                first, last = base + offset, base + offset + 1
                value = row[last] if maximum else row[first]
                result[first] = result[last] = value
    return result


def effects(rows, kind, level, text, maximum=True):
    descriptions = []
    for row in learned_rows(rows, level):
        rendered = wf_describe.describe_line(endpoint_row(row, kind, maximum), kind)
        # InvokeSkill's public wording is stored separately from its program.
        block = wf_describe.layout(kind)["blocks"]["instant_content"]
        sid = cell(row, block + 23)
        if sid in text.custom:
            rendered = rendered.replace("[" + sid + "]", "：" + text.custom[sid])
        description = text.clean(rendered)
        if description:
            descriptions.append(description)
    return descriptions


class EquipmentImages:
    """Prefer independent PNGs, otherwise crop the native item atlas."""
    def __init__(self, media):
        self.media = media
        self._atlas = None
        self._cache = {}

    def image(self, logical):
        if not logical or logical == "(None)":
            return None
        if logical in self._cache:
            return self._cache[logical]
        if wf_assets.locate(self.media.store, logical + ".png"):
            result = self.media.image(logical + ".png")
        else:
            result = self._crop(logical)
        self._cache[logical] = result
        return result

    def _crop(self, logical):
        from PIL import Image
        if self._atlas is None:
            png = self.media._read("item/sprite_sheet.png")
            atlas = self.media._read("item/sprite_sheet.atlas.amf3.deflate")
            if not png or not atlas:
                return None
            picture = Image.open(io.BytesIO(wf_assets.png_decode(png))).convert("RGBA")
            rows = core.AMF3Reader(zlib.decompress(atlas, -15)).read_value()
            self._atlas = picture, {row["n"]: row for row in rows}, png + atlas
        sheet, entries, source_bytes = self._atlas
        row = entries.get(logical)
        if not row:
            return None
        x, y, w, h = (int(row[key]) for key in ("x", "y", "w", "h"))
        if min(x, y, w, h) < 0 or x + w > sheet.width or y + h > sheet.height:
            raise ValueError("装备图标超出原图集")
        crop = sheet.crop((x, y, x + w, y + h))
        if row.get("r"):
            crop = crop.transpose(Image.Transpose.ROTATE_90)
        result = Image.new("RGBA", (row.get("fw", crop.width), row.get("fh", crop.height)))
        result.paste(crop, (-row.get("fx", 0), -row.get("fy", 0)))
        output = io.BytesIO()
        result.save(output, "WEBP", lossless=True)
        return self.media._save("wiki-equipment-icon/" + logical, source_bytes,
                                output.getvalue(), ".webp", width=result.width, height=result.height)

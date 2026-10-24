"""五位角色按UI用途派生头像和编队卡面，不修改立绘或角色包。"""
from __future__ import annotations

import io
import hashlib
from collections.abc import Callable, Mapping

import numpy as np
from PIL import Image

import wf_assets
import wf_atf
import wf_campus_art_images as images
import wf_ui_derive_gate as gate

CODES = frozenset(("white_tiger_summer", "lady_summoner_campus", "wind_spgirl_campus",
                   "ruin_girl_campus", "scutum_valentine"))
GROUPS = (
    ("square", "square_132_132", "square_round_136_136", "square_round_95_95"),
    ("thumb_level_up", "thumb_party_unison"),
    ("battle_member_status",), ("battle_control_board",),
    ("cutin_skill_chain",), ("thumb_party_main",),
)
COLORS = {"white_tiger_summer": ((67, 110, 117), (25, 44, 54)),
          "lady_summoner_campus": ((139, 68, 53), (51, 29, 42)),
          "wind_spgirl_campus": ((63, 132, 107), (27, 42, 57)),
          "ruin_girl_campus": ((115, 86, 144), (34, 30, 55)),
          "scutum_valentine": ((71, 140, 125), (28, 53, 54))}


def verified_masks(npz_bytes, official_modes):
    """Read the audited official modal masks, never an older portrait silhouette."""
    with np.load(io.BytesIO(npz_bytes), allow_pickle=False) as cache:
        masks = {slot: cache[slot].copy() for slot in gate.SHAPE_SLOTS}
    for slot, mask in masks.items():
        signature = hashlib.sha1(mask.tobytes()).hexdigest()[:12] + f"_{mask.shape}"
        if signature != official_modes[slot][0][0]:
            raise ValueError("official modal mask drift: " + slot)
    return masks


def _background(size, code):
    yy, xx = np.mgrid[:size[1], :size[0]]
    radius = np.sqrt((xx / size[0] - .5) ** 2 + (yy / size[1] - .42) ** 2)
    radius = (radius / radius.max())[..., None]
    inner, outer = map(np.array, COLORS[code])
    rgb = (inner * (1 - radius) + outer * radius).astype(np.uint8)
    return Image.fromarray(np.dstack((rgb, np.full(radius.shape[:2], 255, np.uint8))))


def _box(box, size):
    if len(box) != 4 or any(not isinstance(v, int) for v in box):
        raise ValueError("reviewed face crop requires four integer coordinates")
    left, top, right, bottom = box
    if not (0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]):
        raise ValueError("face crop is outside its source")
    if right - left != bottom - top:
        raise ValueError("canonical face crop must be square")
    return ((left + right) / 2, (top + bottom) / 2), right - left


def make_images(code, source, square_box, masks, *, transparent_background=False):
    """头像留出头部空间，编队和弹射板按各自竖框保留头肩与上身。"""
    if code not in CODES:
        raise ValueError("unassigned character")
    source = source.convert("RGBA")
    center, side = _box(square_box, source.size)
    result = {}
    for slots in GROUPS:
        size = gate.OFFICIAL_ICON_SIZES[slots[0]]
        height = 1.13 * max(side, .82 * side * size[1] / size[0])
        anchor = (.5, .5)
        if slots[0] == "thumb_party_main":
            height, anchor = 2.4 * side, (.5, .30)
        elif slots[0] == "battle_control_board":
            height, anchor = 2.85 * side, (.5, .23)
        elif slots[0] == "thumb_level_up":
            height, anchor = 1.57 * side, (.5, .38)
        image = Image.new("RGBA", size) if transparent_background else _background(size, code)
        image.alpha_composite(images.crop_at(source, center, height, size, anchor))
        for slot in slots:
            target = image.resize(gate.OFFICIAL_ICON_SIZES[slot], Image.Resampling.LANCZOS)
            if slot in gate.SHAPE_SLOTS:
                alpha = np.asarray(masks[slot])
                if alpha.shape != (target.height, target.width) or alpha.dtype != np.uint8:
                    raise ValueError("wrong native alpha mask for " + slot)
                # The native frame is a ceiling, not a replacement for the
                # artwork silhouette. Replacing alpha fills empty art regions.
                if transparent_background:
                    alpha = np.minimum(np.asarray(target.getchannel("A")), alpha)
                target.putalpha(Image.fromarray(alpha))
            result[slot] = target
    # The horizontal skill banner shows the upper body. Reusing the square
    # portrait scale here turns the animation into a face-only close-up.
    cutin = images.crop_at(source, center, 2.4 * side, (1024, 512), (.5, .32))
    pixels = np.array(cutin)
    alpha = pixels[:, :, 3].astype(float)
    # Tight portraits can fill the entire banner. Keep transparent side padding
    # outside the centered face so the native cutin never becomes an opaque slab.
    alpha[:, :160] = 0
    alpha[:, 160:224] *= np.linspace(0, 1, 64)
    alpha[:24, :] = 0
    alpha[24:88, :] *= np.linspace(0, 1, 64)[:, None]
    alpha[:, 800:960] *= np.linspace(1, 0, 160)
    alpha[:, 960:] = 0
    pixels[:, :, 3] = alpha.astype(np.uint8)
    result["skill_cutin"] = Image.fromarray(pixels)
    return result


def assets(code: str, source_pngs: Mapping[int, bytes], square_boxes: Mapping[int, tuple],
           stored_loader: Callable[[str, str], bytes], *, native_masks) -> dict[tuple[str, str], bytes]:
    """两状态各10头像+1横切PNG+1Android切入；不返回任何表、fullshot或像素。"""
    if code not in CODES or set(source_pngs) != {0, 1} or set(square_boxes) != {0, 1}:
        raise ValueError("requires assigned code and both evolution states")
    output = {}
    for level in (0, 1):
        prefix = f"character/{code}/ui/"
        source = Image.open(io.BytesIO(source_pngs[level])).convert("RGBA")
        icons = make_images(code, source, square_boxes[level], native_masks)
        problems = gate.derived_icon_problems(icons, native_masks, level=str(level))
        if problems:
            raise ValueError("; ".join(problems))
        for slot, icon in icons.items():
            output["medium", prefix + f"{slot}_{level}.png"] = wf_assets.png_encode(images.png(icon))
        logical = prefix + f"skill_cutin_{level}.atf.deflate"
        template = wf_atf.inflate(stored_loader("android", logical))
        atf = wf_atf.build_cutin_atf(images.png(icons["skill_cutin"]), template)
        info = wf_atf.parse_atf(atf)
        if (info["w"], info["h"], info["mips"]) != (1024, 512, 11):
            raise ValueError("cutin ATF layout changed")
        output["android", logical] = wf_atf.deflate(atf)
    return output

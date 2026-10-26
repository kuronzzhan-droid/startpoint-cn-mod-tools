"""校园角色立绘派生：脸部锚点、完整地面保留和官方图标形状。"""
from __future__ import annotations

import hashlib
import io

import numpy as np
from PIL import Image, ImageDraw

import wf_assets
import wf_ui_derive_gate as gate

GROUPS = (
    (("square", "square_132_132", "square_round_136_136", "square_round_95_95"), (.5, .5, 1.0)),
    (("thumb_level_up", "thumb_party_unison"), (.50, .32, 1.55)),
    (("battle_member_status",), (.5, .50, .92)),
    (("battle_control_board",), (.50, .23, 2.45)),
    (("cutin_skill_chain",), (.50, .43, 1.20)),
    (("thumb_party_main",), (.5, .25, 2.15)),
)
COLORS = {"bianca": ((139, 68, 53), (51, 29, 42)),
          "celtie": ((63, 132, 107), (27, 42, 57)),
          "nephtim": ((115, 86, 144), (34, 30, 55))}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def png(image):
    buf = io.BytesIO()
    image.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def read_png(path):
    return Image.open(io.BytesIO(wf_assets.png_decode(path.read_bytes()))).convert("RGBA")


def load_master(path, landmarks):
    raw = path.read_bytes()
    if landmarks.get("sha256") and landmarks["sha256"] != sha(raw):
        raise ValueError("artwork differs from visually reviewed source")
    source = Image.open(io.BytesIO(raw))
    if source.mode != "RGBA":
        raise ValueError("source must have real RGBA; baked grid or RGB backdrop is not accepted")
    alpha = np.asarray(source.getchannel("A"))
    if (alpha == 0).mean() < .02 or (alpha > 240).mean() < .15:
        raise ValueError("source alpha has no meaningful transparent background or solid character")
    for key in ("face", "eyes"):
        x, y = landmarks[key]
        if not (0 <= x < source.width and 0 <= y < source.height):
            raise ValueError(f"{key} is outside source")
    return source, dict(source=str(path), sha256=sha(raw), source_size=list(source.size),
                        alpha_bbox=list(source.getchannel("A").getbbox()),
                        transparent_ratio=float((alpha == 0).mean()), landmarks=landmarks)


def crop_at(image, face, height, size, anchor):
    width = height * size[0] / size[1]
    left = round(face[0] - anchor[0] * width)
    top = round(face[1] - anchor[1] * height)
    return image.crop((left, top, left + round(width), top + round(height))).resize(size, Image.Resampling.LANCZOS)


def full_shot(source, eyes):
    """仅去掉全透明边缘；将完整角色、脚、地面、道具放入2000虚拟画布。"""
    left, top, right, bottom = source.getchannel("A").getbbox()
    eye_x, eye_y = eyes[0] - left, eyes[1] - top
    width, height = right - left, bottom - top
    # 原生三角色模板使用2000x2000，统一眼部(1000,500)，底边留20像素。
    bounds = (980 / max(eye_x, 1), 980 / max(width - eye_x, 1),
              480 / max(eye_y, 1), 1480 / max(height - eye_y, 1))
    scale = min(1.10, *bounds)
    size = (round(width * scale), round(height * scale))
    result = source.crop((left, top, right, bottom)).resize(size, Image.Resampling.LANCZOS)
    x, y = round(1000 - eye_x * scale), round(500 - eye_y * scale)
    if not (0 <= x and 0 <= y and x + size[0] <= 2000 and y + size[1] <= 2000):
        raise ValueError("full artwork escaped native virtual canvas")
    return result, dict(x=x, y=y, width=size[0], height=size[1], scale=scale,
                        source_alpha_bbox=[left, top, right, bottom],
                        crop_removes_only_fully_transparent_pixels=True)


def background(size, role):
    yy, xx = np.mgrid[:size[1], :size[0]]
    radius = np.sqrt(((xx / size[0]) - .5) ** 2 + ((yy / size[1]) - .42) ** 2)
    radius = np.clip(radius / radius.max(), 0, 1)[..., None]
    inner, outer = COLORS[role]
    rgb = np.array(inner) * (1 - radius) + np.array(outer) * radius
    return Image.fromarray(np.dstack((rgb.astype(np.uint8), np.full(radius.shape[:2], 255, np.uint8))))


def make_icons(source, landmarks, masks, role, *, headshots=False):
    headshots = landmarks.get("headshot_icons", headshots)
    icons = {}
    for slots, (fx, fy, factor) in GROUPS:
        size = gate.OFFICIAL_ICON_SIZES[slots[0]]
        if headshots:
            # 窄长的原生框仍留足脸宽；锚点居中，不再偏上露出半身。
            fx = fy = .5
            factor = max(1.0, .82 * size[1] / size[0])
        # 按本组主槽单独定位；写入角色 landmarks，重建时保留作者的构图修订。
        anchor = landmarks.get("icon_anchors", {}).get(slots[0])
        if anchor is not None:
            if (not isinstance(anchor, (list, tuple)) or len(anchor) != 2
                    or any(type(v) not in (int, float) or not 0 <= v <= 1 for v in anchor)):
                raise ValueError(f"invalid icon anchor: {slots[0]}")
            fx, fy = anchor
        base = (Image.new("RGBA", size) if landmarks.get("transparent_icon_background", False)
                else background(size, role))
        base.alpha_composite(crop_at(source, landmarks["face"], landmarks["square_height"] * factor,
                                    size, (fx, fy)))
        for slot in slots:
            image = base.resize(gate.OFFICIAL_ICON_SIZES[slot], Image.Resampling.LANCZOS)
            if slot in gate.SHAPE_SLOTS:
                pixels = np.asarray(image).copy()
                if masks[slot].shape != pixels.shape[:2]:
                    raise ValueError(f"wrong native shape mask: {slot}")
                pixels[:, :, 3] = np.minimum(pixels[:, :, 3], masks[slot])
                image = Image.fromarray(pixels)
            icons[slot] = image
    return icons


def make_cutin(source, landmarks, *, headshots=False):
    framing = landmarks.get("cutin_framing")
    if framing is not None:
        # Creature heads can sit far above their torso; retain explicit upper-body framing.
        if framing["height"] <= 0 or len(framing["center"]) != 2:
            raise ValueError("invalid cutin framing")
        result = crop_at(source, framing["center"], framing["height"],
                         (1024, 512), framing.get("anchor", (.5, .32)))
    elif headshots:
        result = crop_at(source, landmarks["face"], landmarks["head_height"] * 1.35,
                         (1024, 512), (.5, .5))
    else:
        result = crop_at(source, landmarks["eyes"], 512 * landmarks["head_height"] / 207,
                         (1024, 512), (.51, .44))
    pixels = np.asarray(result).copy()
    alpha = pixels[:, :, 3].astype(float)
    ramp = np.r_[np.zeros(4), np.linspace(0, 1, 60)]
    alpha[:, :64] *= ramp
    alpha[:64, :] *= ramp[:, None]
    alpha[:, -64:] *= ramp[::-1]
    alpha[:, 800:960] *= np.linspace(1, 0, 160)
    alpha[:, 960:] = 0
    pixels[:, :, 3] = alpha.astype(np.uint8)
    return Image.fromarray(pixels)


def preview(images, path, columns=5):
    cell = (310, 375)
    sheet = Image.new("RGB", (cell[0] * columns, cell[1] * ((len(images) + columns - 1) // columns)), "#343949")
    draw = ImageDraw.Draw(sheet)
    for index, (name, image) in enumerate(images.items()):
        tile = image.copy()
        tile.thumbnail((286, 336))
        x, y = index % columns * cell[0], index // columns * cell[1]
        bg = Image.new("RGBA", tile.size, "#b6bac3")
        bg.alpha_composite(tile)
        sheet.paste(bg.convert("RGB"), (x + (310 - tile.width) // 2, y + 25))
        draw.text((x + 8, y + 6), name, fill="white")
    sheet.save(path)

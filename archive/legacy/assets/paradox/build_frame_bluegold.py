#!/usr/bin/env python
"PARADOX Lv200 蓝金强化框：把官方粉色强化框逐像素染成蓝金（作者 0928「粉色框染色成蓝金色」）。\n\n输出两张图，同一个 recolor()：\n- mod-tools/assets/paradox/paradox_frame_bluegold.png（144×144 不透明，72×72 结果 ×2 最近邻），\n  由补丁 equipment-enhanced-look 的 enhanced_frame_override_ 键在 Lv200 缩略图上替换粉框；\n- mod-tools/assets/paradox/paradox_party_frame_bluegold.png（72×72 RGBA，原尺寸），\n  由补丁 equipment-enhanced-party-frame 的 enhanced_party_frame_override_ 键在编成装备槽替换粉框。\n  源图是官方 party_equipment_rainbow_enhanced（图集 (2008,3771) 72×72，圆角：24 个 α=0、46 个半透明），\n  α 逐像素照抄官方；补丁把它归一到 72×72 再套 rarity 容器的矩阵（≈2.028 倍 = 146×146，双线性），与粉图同样柔和。\n结构（边框明暗、内缘、菱格）逐像素保留，每个像素保持原 OKLab 亮度，只换色相/彩度。\n官方原图 item_rainbow_enhanced / party_equipment_rainbow_enhanced 取自 APK 图集\n（坐标见 ${WF_ROOT}/out/PARADOX-20260928/lv200-frame/official/manifest.json），\n不入仓库；三版换色对比与评审在 ${WF_ROOT}/out/PARADOX-20260928/lv200-frame/v2/。\n用法：python mod-tools/assets/paradox/build_frame_bluegold.py [--preview]\n\nStrategy A: dye the official pink enhanced frame blue-gold by hue remap.\n\nInput : ../../official/item_rainbow_enhanced.png (72x72, official, untouched)\nOutput: frame_72.png, frame_144.png (x2 NEAREST), preview.png\n\nOnly colour changes. Every output pixel keeps the OKLab lightness L of the\nsource pixel, so the diamond lattice, the border shading and the soft inner\nedge survive exactly as luminance modulation. Structure is not redrawn.\n\nHow the colour is changed\n  The official texture is a pink border layer composited over a rainbow\n  interior layer with a 2 px soft ring (weights ~0.7 / ~0.3). Each pixel is\n  split back into (border colour P, interior colour I, weight m); for pure\n  border / interior pixels this is the pixel itself. P and I are recoloured\n  separately in OKLCH. Gold and blue are near-complementary, so an a/b blend\n  in the ring would turn grey/olive: ring pixels take the dominant layer's hue\n  (outer ring -> light gold; inner ring -> lavender-blue, mirroring the\n  official cyan -> violet lean) with the layer chromas blended by m.\n  Finally every pixel takes the source pixel's OKLab L.\n\n  border   pink/magenta (h~325)       -> warm gold (h ~80 amber .. ~90 yellow,\n                                         by lightness), 0.92 of the gamut edge\n  interior yellow-green (h 100..132)  -> pale gold (h 86..90)\n           green (h ~146)             -> narrow neutral seam (only 5 deg wide)\n           cyan/teal (h 160..205)     -> clear sky blue (h 224..240)\n           blue (h 205..245)          -> royal blue (h 240..256)\n  Interior chroma is max(source C, gamut-relative C * 1.12), clipped to the\n  gamut, so the pastel look and relative saturation survive at every L.\n\nDeterministic: pure numpy float64, no randomness; run twice -> same sha256.\nUsage: python recolor.py\n"
from __future__ import annotations

from wf.paths import root_path

import hashlib
from pathlib import Path

import numpy as np
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent            # mod-tools/assets/paradox
PREVIEW_DIR = Path(('${WF_ROOT}/out/PARADOX-20260928/lv200-frame/v2/huemap'.replace("${WF_ROOT}", str(root_path()))))
OFF = PREVIEW_DIR.parent.parent / "official"
SRC = OFF / "item_rainbow_enhanced.png"
PARTY_SRC = OFF / "party_equipment_rainbow_enhanced.png"
ICON_120 = OFF / "paradox_icon_lv120_20x20.png"
ICON_200 = Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\assets\\paradox\\paradox_lv200.png'.replace("${WF_ROOT}", str(root_path()))))

# ---------------------------------------------------------------- tunables
BORDER_HUE = 85.0          # gold hue at L=0.80
BORDER_HUE_SLOPE = 80.0    # darker -> warmer amber, lighter -> paler yellow
BORDER_CFRAC = 0.92        # gold chroma as a fraction of the gamut edge
INTERIOR_ABS_GAIN = 1.00   # interior: keep absolute chroma ...
INTERIOR_REL_GAIN = 1.12   # ... or gamut-relative chroma, whichever is larger
RING_CHROMA = 0.90         # soft ring keeps the dominant layer's hue
RING_LAVENDER = 20.0       # inner ring pixel leans toward lavender-blue,
                           # as the official ring leans cyan -> violet
# interior anchors: source hue -> (target hue, weight of chroma)
# vectors are interpolated in the OKLab a/b plane between anchors
INTERIOR_ANCHORS = [
    (100.0, 86.0, 1.00),
    (132.0, 90.0, 0.90),   # yellow-green -> pale gold
    (141.0, 94.0, 0.55),
    (146.0, 150.0, 0.00),  # hue irrelevant at weight 0: narrow neutral seam
    (151.0, 220.0, 0.45),
    (160.0, 224.0, 0.75),
    (178.0, 229.0, 1.00),  # cyan/teal -> clear sky blue
    (192.0, 232.0, 1.00),
    (205.0, 240.0, 1.00),
    (222.0, 248.0, 1.00),  # blue -> royal blue
    (245.0, 256.0, 1.00),
]
CMAX_FRAC = 0.97           # never push to the exact gamut edge

# ---------------------------------------------------------------- colour math
M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
               [0.2119034982, 0.6806995451, 0.1073969566],
               [0.0883024619, 0.2817188376, 0.6299787005]])
M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
               [1.9779984951, -2.4285922050, 0.4505937099],
               [0.0259040371, 0.7827717662, -0.8086757616]])
M2I = np.linalg.inv(M2)
M1I = np.linalg.inv(M1)


def srgb_to_lin(c):
    c = np.asarray(c, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return 255.0 * np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def rgb_to_oklab(rgb):
    lms = np.cbrt(srgb_to_lin(rgb) @ M1.T)
    return lms @ M2.T


def oklab_to_lin(lab):
    lms = (lab @ M2I.T) ** 3
    return lms @ M1I.T


def oklch_to_lin(L, C, h):
    hr = np.radians(h)
    lab = np.stack([L, C * np.cos(hr), C * np.sin(hr)], axis=-1)
    return oklab_to_lin(lab)


def cmax(L, h, iters=40):
    """Largest in-gamut OKLCH chroma for each (L, h)."""
    lo = np.zeros_like(L)
    hi = np.full_like(L, 0.45)
    for _ in range(iters):
        mid = (lo + hi) / 2
        lin = oklch_to_lin(L, mid, h)
        ok = np.all((lin >= -1e-7) & (lin <= 1 + 1e-7), axis=-1)
        lo = np.where(ok, mid, lo)
        hi = np.where(ok, hi, mid)
    return lo


def lch(rgb):
    lab = rgb_to_oklab(rgb)
    L = lab[..., 0]
    C = np.hypot(lab[..., 1], lab[..., 2])
    h = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360.0
    return L, C, h


def to_rgb_clipped(L, a, b):
    """OKLab -> sRGB float, chroma-reduced into gamut at fixed L and hue."""
    C = np.hypot(a, b)
    h = np.degrees(np.arctan2(b, a)) % 360.0
    C = np.minimum(C, cmax(L, h) * CMAX_FRAC)
    return lin_to_srgb(oklch_to_lin(L, C, h))


# ---------------------------------------------------------------- layer split
def split_layers(rgb):
    """-> (P, I, m): border colour, interior colour, border weight per pixel.

    Border = outside [6,65]^2, interior = [8,63]^2, the 2 px ring between is a
    blend. For ring pixels P / I are the nearest pure pixels outward / inward
    and m is the least-squares blend weight."""
    n = rgb.shape[0]
    idx = np.arange(n)
    ys, xs = np.meshgrid(idx, idx, indexing="ij")
    inner = (xs >= 8) & (xs <= 63) & (ys >= 8) & (ys <= 63)
    outer = (xs <= 5) | (xs >= 66) | (ys <= 5) | (ys >= 66)
    ring = ~inner & ~outer

    def out_coord(v):
        return np.where(v <= 7, 5, np.where(v >= 64, 66, v))

    def in_coord(v):
        return np.clip(v, 8, 63)

    P = rgb.copy()
    I = rgb.copy()
    m = np.where(outer, 1.0, 0.0)
    # ring: nearest pure border pixel (push the ring coordinate(s) outward)
    oy, ox = out_coord(ys), out_coord(xs)
    iy, ix = in_coord(ys), in_coord(xs)
    Pr = rgb[oy, ox]
    Ir = rgb[iy, ix]
    d = Pr - Ir
    mm = np.sum((rgb - Ir) * d, axis=-1) / np.maximum(np.sum(d * d, axis=-1), 1e-9)
    mm = np.clip(mm, 0.0, 1.0)
    P[ring] = Pr[ring]
    I[ring] = Ir[ring]
    m[ring] = mm[ring]
    # border pixels still need an interior colour only for completeness
    I[outer] = rgb[iy, ix][outer]
    P[inner] = rgb[oy, ox][inner]
    return P, I, m, inner, outer, ring


# ---------------------------------------------------------------- recolour
def recolor_border(P):
    L, C, h = lch(P)
    rel = C / np.maximum(cmax(L, h), 1e-9)
    h2 = BORDER_HUE + (L - 0.80) * BORDER_HUE_SLOPE
    C2 = np.minimum(rel, 1.0) * BORDER_CFRAC * cmax(L, h2)
    hr = np.radians(h2)
    return L, C2 * np.cos(hr), C2 * np.sin(hr)


def interior_target(h):
    """source hue -> target unit-ish vector (a, b) * chroma weight."""
    src = np.array([a[0] for a in INTERIOR_ANCHORS])
    vec = np.array([[w * np.cos(np.radians(t)), w * np.sin(np.radians(t))]
                    for _, t, w in INTERIOR_ANCHORS])
    hc = np.clip(h, src[0], src[-1])
    va = np.interp(hc, src, vec[:, 0])
    vb = np.interp(hc, src, vec[:, 1])
    return va, vb


def recolor_interior(I):
    L, C, h = lch(I)
    rel = C / np.maximum(cmax(L, h), 1e-9)
    va, vb = interior_target(h)
    w = np.hypot(va, vb)
    h2 = np.degrees(np.arctan2(vb, va)) % 360.0
    cm = cmax(L, h2)
    C2 = np.maximum(C * INTERIOR_ABS_GAIN, rel * INTERIOR_REL_GAIN * cm)
    C2 = np.minimum(C2, cm) * w
    hr = np.radians(h2)
    return L, C2 * np.cos(hr), C2 * np.sin(hr)


def recolor(rgb8):
    rgb = rgb8.astype(float)
    P, I, m, inner, outer, ring = split_layers(rgb)
    Lp, ap, bp = recolor_border(P)
    Li, ai, bi = recolor_interior(I)
    # soft ring: gold and blue are near-complementary, so an a/b blend would
    # go grey/olive. Take the dominant layer's hue and blend the chroma.
    Cp, Ci = np.hypot(ap, bp), np.hypot(ai, bi)
    hp, hi = np.arctan2(bp, ap), np.arctan2(bi, ai)
    # inner ring pixel: lavender-blue where the interior is on the blue side,
    # light gold where it is on the gold side or neutral (crossover corner)
    _, vb = interior_target(lch(I)[2])
    blue_side = vb < 0
    hi = hi + np.where(ring & blue_side, np.radians(RING_LAVENDER), 0.0)
    hr = np.where((m >= 0.5) | (ring & ~blue_side), hp, hi)
    Cr = (m * Cp + (1 - m) * Ci) * np.where(ring, RING_CHROMA, 1.0)
    L0 = rgb_to_oklab(rgb)[..., 0]
    out = to_rgb_clipped(L0, Cr * np.cos(hr), Cr * np.sin(hr))
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- preview
LIGHT_BG = (205, 205, 210, 255)   # in-game list grey
DARK_BG = (34, 36, 50, 255)


def thumb(frame144: Image.Image, icon: Image.Image | None) -> Image.Image:
    """Frame at 2x with the 20x20 icon at 6x centred (pixels 12..131)."""
    t = frame144.copy()
    if icon is not None:
        t.alpha_composite(icon.resize((120, 120), Image.NEAREST), (12, 12))
    return t


def _font(size=13):
    try:
        return ImageFont.truetype("msyh.ttc", size)
    except OSError:
        return ImageFont.load_default()


def _ingame_band(frame144, pink, ic120, ic200, font):
    """item_frame card + frame + icon + official sweep at its brightest frame,
    replayed by ../../final_preview.py (read-only import)."""
    # Historical preview dependency is not an active compatibility API.
    import final_preview as fp  # noqa: E402
    parts, total = fp.load_sweep()

    def energy(f):
        hist = parts.render(f, fp.CARD, fp.CARD / 2).getchannel("A").histogram()
        return sum(v * n for v, n in enumerate(hist))
    sf = max(range(total), key=energy)
    sw = parts.render(sf, fp.CARD, fp.CARD / 2)
    cards = [("official, card", fp.thumbnail(pink, ic120)),
             ("dyed, card", fp.thumbnail(frame144, ic200)),
             (f"official + sweep f{sf}", fp.thumbnail(pink, ic120, sw)),
             (f"dyed + sweep f{sf}", fp.thumbnail(frame144, ic200, sw))]
    pad = 16
    band = Image.new("RGBA", (pad + 4 * (fp.CARD + pad) + 2 * (84 + 12), fp.CARD + 44),
                     LIGHT_BG)
    d = ImageDraw.Draw(band)
    x = pad
    for name, c in cards:
        d.text((x, 4), name, fill=(40, 40, 48), font=font)
        band.alpha_composite(c, (x, 26))
        x += fp.CARD + pad
    for name, c in cards[:2]:
        band.alpha_composite(c.resize((84, 84), Image.LANCZOS), (x, 26 + 42))
        x += 84 + 12
    d.text((x - 2 * 96, 26 + 20), "0.5x cards", fill=(40, 40, 48), font=font)
    return band


def preview(frame144: Image.Image) -> Image.Image:
    pink = Image.open(SRC).convert("RGBA").resize((144, 144), Image.NEAREST)
    ic120 = Image.open(ICON_120).convert("RGBA")
    ic200 = Image.open(ICON_200).convert("RGBA")
    trio = [("official + lv120", thumb(pink, ic120)),
            ("dyed + lv200", thumb(frame144, ic200)),
            ("dyed frame", thumb(frame144, None))]
    font = _font()
    pad, gap, lab = 16, 16, 22
    ingame = _ingame_band(frame144, pink, ic120, ic200, font)
    band_w = max(pad * 2 + 3 * 144 + 2 * gap + 40 + 3 * 72 + 2 * 12, ingame.width)
    band_h = pad + lab + 144 + pad
    bands = []
    for bg, fg in ((LIGHT_BG, (40, 40, 48)), (DARK_BG, (214, 218, 232))):
        band = Image.new("RGBA", (band_w, band_h), bg)
        d = ImageDraw.Draw(band)
        x = pad
        for name, t in trio:
            d.text((x, pad - 6), name, fill=fg, font=font)
            band.alpha_composite(t, (x, pad + lab))
            x += 144 + gap
        x += 40 - gap
        d.text((x, pad - 6), "0.5x (LANCZOS)", fill=fg, font=font)
        for _, t in trio:
            band.alpha_composite(t.resize((72, 72), Image.LANCZOS), (x, pad + lab + 36))
            x += 72 + 12
        bands.append(band)
    bands.append(ingame)
    W = max(b.width for b in bands)
    img = Image.new("RGBA", (W, sum(b.height for b in bands)), LIGHT_BG)
    y = 0
    for b in bands:
        img.alpha_composite(b, (0, y))
        y += b.height
    return img.convert("RGB")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------- party slot frame
PARTY_OUT = HERE / "paradox_party_frame_bluegold.png"
PARTY_PREVIEW = Path(('${WF_ROOT}/out/PARADOX-20260928/apk/enhanced-look-party-20260928/preview_party_frame.png'.replace("${WF_ROOT}", str(root_path()))))
PARTY_TRANSPARENT, PARTY_SEMI = 24, 46      # official rounded corners: alpha 0 / 0 < alpha < 255
PARTY_OPAQUE_RGB_TOLERANCE = 7              # official item vs party texture on opaque pixels
PARTY_SCALE = 2.02777099609375              # rarity container matrix in item_thumbnail.ui (72 -> 146)


def party_frame(item: np.ndarray, party: np.ndarray) -> np.ndarray:
    """Party-slot frame (72x72 RGBA): same recolor() as the list frame, alpha copied from the official texture.

    The official party texture is the list texture plus rounded corners (opaque RGB differs by <= 7). The
    corner pixels (alpha < 255) come out of the atlas un-premultiplied, so at low alpha their RGB is distorted
    (G channel ~60-100 instead of ~150), and recolouring them would give dark gold edges once the device scales
    the frame 2.03x bilinearly. Their RGB is therefore taken from the list texture at the same position before
    recolouring (not premultiplied: the PNG keeps straight alpha), then the official alpha is put back."""
    assert item.shape == party.shape == (72, 72, 4) and item[..., 3].min() == 255
    alpha = party[..., 3]
    opaque = alpha == 255
    assert int((alpha == 0).sum()) == PARTY_TRANSPARENT and int((~opaque & (alpha > 0)).sum()) == PARTY_SEMI, \
        "party_equipment_rainbow_enhanced corners changed: re-extract the official texture"
    diff = np.abs(item[..., :3].astype(int) - party[..., :3].astype(int))[opaque].max()
    assert diff <= PARTY_OPAQUE_RGB_TOLERANCE, f"party texture no longer matches the list texture ({diff})"
    source = np.where(opaque[..., None], party[..., :3], item[..., :3])
    return np.dstack([recolor(source), alpha]).astype(np.uint8)


def party_preview(frame: Image.Image) -> Image.Image:
    """Official pink vs dyed party frame at the device size (bilinear 2.03x) with the Lv200 icon at 6x."""
    size = int(round(72 * PARTY_SCALE))
    pink = Image.open(PARTY_SRC).convert("RGBA")
    ic120 = Image.open(ICON_120).convert("RGBA").resize((120, 120), Image.NEAREST)
    ic200 = Image.open(ICON_200).convert("RGBA").resize((120, 120), Image.NEAREST)
    font = _font()
    pad, lab = 16, 22
    cells = [("official + lv120", pink, ic120), ("dyed + lv200", frame, ic200), ("dyed frame", frame, None)]
    img = Image.new("RGBA", (pad + len(cells) * (size + pad), 2 * (lab + size + pad) + pad), LIGHT_BG)
    d = ImageDraw.Draw(img)
    for row, (bg, fg) in enumerate(((LIGHT_BG, (40, 40, 48)), (DARK_BG, (214, 218, 232)))):
        y = pad + row * (lab + size + pad)
        d.rectangle((0, y - pad // 2, img.width, y + lab + size + pad // 2), fill=bg)
        for i, (name, fr, icon) in enumerate(cells):
            x = pad + i * (size + pad)
            d.text((x, y), name, fill=fg, font=font)
            cell = fr.resize((size, size), Image.BILINEAR)
            if icon is not None:
                cell.alpha_composite(icon, ((size - 120) // 2, (size - 120) // 2))
            img.alpha_composite(cell, (x, y + lab))
    return img.convert("RGB")


def main():
    src = np.array(Image.open(SRC).convert("RGBA"))
    assert src.shape == (72, 72, 4) and src[..., 3].min() == 255
    rgb = recolor(src[..., :3])
    f72 = Image.fromarray(np.dstack([rgb, np.full((72, 72), 255, np.uint8)]), "RGBA")
    f144 = f72.resize((144, 144), Image.NEAREST)
    out = HERE / "paradox_frame_bluegold.png"
    f144.save(out, optimize=False)
    party_src = np.array(Image.open(PARTY_SRC).convert("RGBA"))
    party = party_frame(src, party_src)
    Image.fromarray(party, "RGBA").save(PARTY_OUT, optimize=False)
    if "--preview" in sys.argv[1:]:
        preview(f144).save(PREVIEW_DIR / "preview.png", optimize=False)
        party_preview(Image.fromarray(party, "RGBA")).save(PARTY_PREVIEW, optimize=False)
    # lightness check: every pixel keeps its source OKLab L
    dL = np.abs(rgb_to_oklab(rgb.astype(float))[..., 0]
                - rgb_to_oklab(src[..., :3].astype(float))[..., 0])
    print(f"max |dL| = {dL.max():.4f}  mean |dL| = {dL.mean():.5f}")
    print(out.name, sha(out))
    opaque = party_src[..., 3] == 255
    dLp = np.abs(rgb_to_oklab(party[..., :3].astype(float))[..., 0]
                 - rgb_to_oklab(party_src[..., :3].astype(float))[..., 0])[opaque]
    assert (party[..., 3] == party_src[..., 3]).all()
    print(f"party: alpha copied, opaque max |dL| = {dLp.max():.4f}  mean |dL| = {dLp.mean():.5f}")
    print(PARTY_OUT.name, sha(PARTY_OUT))


if __name__ == "__main__":
    main()

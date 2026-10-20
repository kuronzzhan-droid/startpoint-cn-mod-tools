# -*- coding: utf-8 -*-
"""护花使龙觉醒 PF 特效：仿索维光球（克隆索维特殊 PF 族换色）+ 单根小龙卷（从旋风龙技能特效里剥一根）。

只依赖调用方已经建好的 live149 视图（read_raw）。返回 {逻辑路径: 字节}。
"""
import colorsys
import copy
import io
import zlib

import numpy as np
from PIL import Image

import wf_dsl
import wf_mod_tool as M

SOVI = "battle/effect/powerflip/psycho_reaper_meteor23"
SOVI_NAMES = [f"psycho_reaper_meteor23_powerflip_attack_special_{p}{n}"
              for n in ("one", "two", "three") for p in ("player_", "")]
WD = "battle/effect/skill_unique/wind_dragon"
TORNADO_POS = (-3686, -152780)     # 旋风龙 6 根里正上方那根的平移（×4096 定点）
TORNADO_GROUPS = {2, 42, 40, 46}   # 这根的 出现/循环/循环叠层/消散 四个子组


def amf(b):
    return M.AMF3Reader(zlib.decompress(b, -15)).read_value()


def deflate(b):
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(b) + co.flush()


def png_rgba(raw):
    b = bytearray(raw)
    b[1:4] = b"PNG"
    return Image.open(io.BytesIO(bytes(b))).convert("RGBA")


def png_store(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    b = bytearray(buf.getvalue())
    b[1:4] = b"png"
    return bytes(b)


def hue_shift(img, deg):
    a = np.asarray(img).astype(np.float32) / 255
    rgb = a[..., :3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    hsv = np.stack(np.vectorize(colorsys.rgb_to_hsv)(rgb[..., 0], rgb[..., 1], rgb[..., 2]), -1)
    hsv[..., 0] = (hsv[..., 0] + deg / 360) % 1
    out = np.stack(np.vectorize(colorsys.hsv_to_rgb)(hsv[..., 0], hsv[..., 1], hsv[..., 2]), -1)
    a[..., :3] = out
    return Image.fromarray((a * 255 + .5).clip(0, 255).astype(np.uint8), "RGBA")


def colorize(img, hue, sat_low, sat_keep=0.0, lift=0.0):
    """低饱和像素染成 hue（保留明度）；高饱和像素也转到 hue。"""
    a = np.asarray(img).astype(np.float32) / 255
    rgb = a[..., :3]
    h, s, v = np.vectorize(colorsys.rgb_to_hsv)(rgb[..., 0], rgb[..., 1], rgb[..., 2])
    s2 = np.maximum(s * sat_keep, sat_low * (1 - s) + s * 0.8)
    h2 = np.full_like(h, hue / 360)
    r, g, b = np.vectorize(colorsys.hsv_to_rgb)(h2, np.clip(s2, 0, 1), v * (1 - lift) + lift)
    a[..., 0], a[..., 1], a[..., 2] = r, g, b
    return Image.fromarray((a * 255 + .5).clip(0, 255).astype(np.uint8), "RGBA")


# 绿白多层：按亮度映射到 深绿 → 翠绿 → 薄荷 → 白，层与层之间靠原图明暗分出层次
GREEN_WHITE = ((0.0, (8, 52, 34)), (0.30, (24, 128, 72)), (0.55, (88, 206, 132)), (0.78, (186, 244, 206)),
               (1.0, (255, 255, 252)))


def gradient_map(img, stops=GREEN_WHITE, lift=0.0):
    a = np.asarray(img).astype(np.float32) / 255
    lum = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
    lum = np.clip(lum * (1 - lift) + lift, 0, 1)
    xs = [p for p, _ in stops]
    for ch in range(3):
        a[..., ch] = np.interp(lum, xs, [c[ch] / 255 for _, c in stops])
    return Image.fromarray((a * 255 + .5).clip(0, 255).astype(np.uint8), "RGBA")


# 作者 1015「绿色太多、不够多彩」：三件各走一条色带，叠在一起是 青蓝/翠绿/黄绿/金/白 的层次
# 作者 1015：台风/龙卷以绿色为主，层次靠同色系不同明度 + 少量青/黄绿点缀
TORNADO_BANDS = (
    ((0.0, (8, 58, 36)), (0.30, (24, 146, 78)), (0.55, (118, 222, 110)), (0.78, (218, 250, 200)),
     (1.0, (255, 255, 250))),                                                                         # 第 1 圈 翠绿
    ((0.0, (6, 56, 52)), (0.30, (22, 146, 112)), (0.55, (88, 222, 168)), (0.78, (200, 250, 232)),
     (1.0, (255, 255, 255))),                                                                         # 第 2 圈 青绿
    ((0.0, (28, 66, 18)), (0.30, (86, 166, 40)), (0.55, (186, 230, 88)), (0.78, (248, 250, 192)),
     (1.0, (255, 255, 248))),                                                                         # 第 3 圈 黄绿
)
TYPHOON_BAND = ((0.0, (6, 40, 30)), (0.35, (22, 118, 78)), (0.62, (80, 200, 140)), (0.85, (204, 246, 222)),
                (1.0, (255, 255, 255)))
TYPHOON_SQUASH = 0.62      # 台风俯视成椭圆：纵向压到 0.62（与龙卷椭圆外推同比）
TYPHOON_GROUPS = {30, 36, 44, 45}   # 旋风龙技能中央的大旋涡（出现/循环/叠层/消散）


def center_typhoon(name, parts):
    """旋风龙技能只留中央大旋涡，去掉周围 6 根龙卷。"""
    g1 = parts["g"][1]
    keep = [seg for seg in g1["s"] if seg["i"] in TYPHOON_GROUPS]
    assert sorted(s["i"] for s in keep) == sorted(TYPHOON_GROUPS), [s["i"] for s in keep]
    g1["s"] = keep
    # 根节点矩阵纵向压扁 ⇒ 椭圆旋涡
    root = parts["g"][0]["s"]
    assert len(root) == 1 and all((kf["m"] >> 12) == 0 for kf in root[0]["l"])
    t0 = parts["t"][0]
    parts["t"].append(dict(t0, c=round(t0["c"] * TYPHOON_SQUASH), d=round(t0["d"] * TYPHOON_SQUASH)))
    for kf in root[0]["l"]:
        kf["m"] = ((len(parts["t"]) - 1) << 12) | (kf["m"] & 0xFFF)


def clone_family(read_raw, src_dir, src_sheet, dst_dir, names, rename, recolor, parts_hook=None):
    """整族克隆：新目录 <dst>/<dst名>.png/.atlas，帧名与 parts i[].p 改前缀，timeline 原字节。"""
    dname = dst_dir.rsplit("/", 1)[1]
    files = {}
    atlas = amf(read_raw(f"{src_dir}/{src_sheet}.atlas.amf3.deflate")[0])
    keep = []
    for e in atlas:
        base = e["n"].split("/.gen/")[1].split("/")[0]
        if base in rename:
            keep.append(dict(e, n=e["n"].replace(f"{src_dir}/.gen/{base}/", f"{dst_dir}/.gen/{rename[base]}/")))
    files[f"{dst_dir}/{dname}.atlas.amf3.deflate"] = deflate(wf_dsl.encode_amf3(keep))
    sheet = recolor(png_rgba(read_raw(f"{src_dir}/{src_sheet}.png")[0]))
    files[f"{dst_dir}/{dname}.png"] = png_store(sheet)
    out_parts = {}
    for n in names:
        raw = zlib.decompress(read_raw(f"{src_dir}/{n}.parts.amf3.deflate")[0], -15)
        parts = wf_dsl.parse_dsl(raw)["tree"]
        assert wf_dsl.encode_amf3(parts) == raw, n
        for e in parts["i"]:
            assert e["p"].startswith(f"{src_dir}/.gen/{n}/"), e["p"]
            e["p"] = e["p"].replace(f"{src_dir}/.gen/{n}/", f"{dst_dir}/.gen/{rename[n]}/")
        if parts_hook:
            parts_hook(n, parts)
        names_ok = {e["n"] for e in keep}
        assert all(e["p"] in names_ok for e in parts["i"]), n
        files[f"{dst_dir}/{rename[n]}.parts.amf3.deflate"] = deflate(wf_dsl.encode_amf3(parts))
        tl = read_raw(f"{src_dir}/{n}.timeline.amf3.deflate")[0]
        files[f"{dst_dir}/{rename[n]}.timeline.amf3.deflate"] = tl
        out_parts[rename[n]] = (parts, sheet, keep)
    return files, out_parts


def single_tornado(name, parts):
    """旋风龙 6 根龙卷只留正上方一根并挪到原点；去掉中央大旋涡。"""
    g1 = parts["g"][1]
    keep = []
    for seg in g1["s"]:
        if seg["i"] not in TORNADO_GROUPS:
            continue
        t0 = parts["t"][seg["l"][0]["m"] >> 12]
        if (t0["x"], t0["y"]) != TORNADO_POS:
            continue
        for kf in seg["l"]:
            src = parts["t"][kf["m"] >> 12]
            assert (src["x"], src["y"]) == TORNADO_POS
            parts["t"].append(dict(src, x=0, y=0))
            kf["m"] = ((len(parts["t"]) - 1) << 12) | (kf["m"] & 0xFFF)
        keep.append(seg)
    assert sorted(s["i"] for s in keep) == sorted(TORNADO_GROUPS), [s["i"] for s in keep]
    g1["s"] = keep


def build(read_raw, fx_root):
    """fx_root = battle/effect/skill_unique/wind_dragon_wt22/"""
    pf_dir = fx_root + "ol_pf"
    tor_dir = fx_root + "ol_tornado"
    rename = {n: n.replace("psycho_reaper_meteor23_powerflip_attack", "rose_ol_pf") for n in SOVI_NAMES}
    f1, p1 = clone_family(read_raw, SOVI, "psycho_reaper_meteor23", pf_dir, SOVI_NAMES, rename,
                          lambda im: hue_shift(im, 100))      # 保留索维原图多色，整体转到绿/青/金/粉
    f2, p2, tornados = {}, {}, []
    for w, band in enumerate(TORNADO_BANDS, 1):
        d, base = f"{tor_dir}{w}", f"rose_ol_tornado{w}"
        fw, pw = clone_family(read_raw, WD, "wind_dragon", d, ["wind_dragon"], {"wind_dragon": base},
                              lambda im, band=band: gradient_map(im, band, lift=0.25), parts_hook=single_tornado)
        # 12 道同屏：去掉 timeline 里的两条大爆风音效（爆发/台风自带音效）
        tl_lp = f"{d}/{base}.timeline.amf3.deflate"
        tl = wf_dsl.parse_dsl(zlib.decompress(fw[tl_lp], -15))["tree"]
        assert [x["path"] for x in tl["sounds"]] == ["sound_effect/wind/se_wind_large_explosion",
                                                      "sound_effect/wind/se_wind_bang_down"]
        tl["sounds"] = []
        fw[tl_lp] = deflate(wf_dsl.encode_amf3(tl))
        f2.update(fw)
        p2.update(pw)
        tornados.append(f"{d}/{base}")
    ty_dir = fx_root + "ol_typhoon"
    f3, p3 = clone_family(read_raw, WD, "wind_dragon", ty_dir, ["wind_dragon"],
                          {"wind_dragon": "rose_ol_typhoon"}, lambda im: gradient_map(im, TYPHOON_BAND, lift=0.3),
                          parts_hook=center_typhoon)
    paths = {
        "orb": {lv: f"{pf_dir}/rose_ol_pf_special_player_{n}" for lv, n in ((1, "one"), (2, "two"), (3, "three"))},
        "burst": {lv: f"{pf_dir}/rose_ol_pf_special_{n}" for lv, n in ((1, "one"), (2, "two"), (3, "three"))},
        "tornado": tornados,
        "typhoon": f"{ty_dir}/rose_ol_typhoon",
    }
    return {**f1, **f2, **f3}, paths, {**p1, **p2, **p3}

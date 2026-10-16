# -*- coding: utf-8 -*-
"""1.4.191 -> 1.4.192: 四张立绘换新(杰拉德_0 / 杰拉尔_0 / 歌狼_0,_1),派生 UI 图标 + 三张定位表行级改写。"""
from p192_common import *
import numpy as np, json, struct, zlib, sys, pickle
from PIL import ImageDraw
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_ui_derive_gate as gate
import wf_assets, wf_atf, wf_dsl
from wf_quest_lib import _try_parse_map

INDIGO = (20, 30, 95, 255)
# 眼中点(母图像素,4x 放大网格目测)与头宽
LANDMARKS = {0: dict(eye=(572, 111), head=180), 1: dict(eye=(662, 182), head=165),
             2: dict(eye=(580, 135), head=185), 3: dict(eye=(600, 205), head=190)}
# (槽列表, 头宽占比, 眼高占比)
GROUPS = [(("square", "square_132_132", "square_round_136_136", "square_round_95_95"), .55, .42),
          (("thumb_level_up", "thumb_party_unison"), .40, .30),
          (("thumb_party_main",), .50, .24),
          (("battle_control_board",), .85, .22),
          (("battle_member_status",), .80, .45),
          (("cutin_skill_chain",), .50, .36)]
CUTIN = dict(head=.30, ex=.50, ey=.32)
MASKS = dict(np.load(ART / "official-shape-masks-140-majority.npz"))


def crop_box(eye, head, size, frac, ey):
    w = head / frac
    h = w * size[1] / size[0]
    l = eye[0] - w / 2
    t = eye[1] - ey * h
    return (l, t, l + w, t + h)


def render(master, box, size):
    l, t, r, b = box
    sx = (r - l) / size[0]
    sy = (b - t) / size[1]
    big = (size[0] * 2, size[1] * 2)
    im = master.convert("RGBa").transform(big, Image.Transform.AFFINE, (sx / 2, 0, l, 0, sy / 2, t),
                                          resample=Image.Resampling.BICUBIC)
    return im.resize(size, Image.Resampling.LANCZOS).convert("RGBA")


def png_bytes(im):
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def clear_hidden(im):
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(im)
    return out


def make_icons(master, lm):
    icons = {}
    for slots, frac, ey in GROUPS:
        size = gate.OFFICIAL_ICON_SIZES[slots[0]]
        box = crop_box(lm["eye"], lm["head"], size, frac, ey)
        base = Image.new("RGBA", size, INDIGO)
        base.alpha_composite(render(master, box, size))
        for s in slots:
            im = base if s == slots[0] else base.resize(gate.OFFICIAL_ICON_SIZES[s], Image.Resampling.LANCZOS)
            if s in gate.SHAPE_SLOTS:
                px = np.asarray(im).copy()
                px[:, :, 3] = np.minimum(px[:, :, 3], MASKS[s])
                im = Image.fromarray(px)
            icons[s] = clear_hidden(im)
    return icons


def make_cutin(master, lm):
    size = (1024, 512)
    box = crop_box(lm["eye"], lm["head"], size, CUTIN["head"], CUTIN["ey"])
    im = render(master, box, size)
    px = np.asarray(im).astype(np.float64)
    a = px[:, :, 3]
    # 场景母图非抠图: 以脸/上身为心的柔和椭圆渐隐; 右侧 0.81 宽后清零
    yy, xx = np.mgrid[:512, :1024]
    cx, cy = CUTIN["ex"] * 1024, CUTIN["ey"] * 512 + 90
    d = np.sqrt(((xx - cx) / 360) ** 2 + ((yy - cy) / 330) ** 2)
    v = np.clip((1.25 - d) / 0.45, 0, 1)
    v = v * v * (3 - 2 * v)
    a = a * v
    ramp = np.r_[np.zeros(4), np.linspace(0, 1, 60)]
    a[:, :64] *= ramp
    a[:64, :] *= ramp[:, None]
    a[-64:, :] *= ramp[::-1][:, None]
    a[:, 800:960] *= np.linspace(1, 0, 160)
    a[:, 960:] = 0
    px[:, :, 3] = a
    return clear_hidden(Image.fromarray(px.round().astype(np.uint8)))


# ---------------------------------------------------------------- 表: 原始行级替换
def build_raw(keys, chunks):
    kb = b""
    rb = b""
    pairs = []
    for k, c in zip(keys, chunks):
        kb += k.encode("utf-8")
        rb += c
        pairs.append((len(kb), len(rb)))
    idx = struct.pack("<I", len(pairs)) + b"".join(struct.pack("<II", *p) for p in pairs) + kb
    packed = zlib.compress(idx)
    return struct.pack("<I", len(packed)) + packed + rb


def zrow(text):
    return zlib.compress(text.encode("utf-8"))


def patch_table(lp, edits):
    raw, src = read_raw(lp)
    keys, c0 = _try_parse_map(raw)
    chunks = list(c0)
    before = {}
    for path, text in edits.items():
        i = keys.index(path[0])
        if len(path) == 1:
            before[path] = q.parse_node(chunks[i])
            chunks[i] = zrow(text)
        else:
            sk, sc = _try_parse_map(chunks[i])
            sc = list(sc)
            j = sk.index(path[1])
            before[path] = q.parse_node(sc[j])
            sc[j] = zrow(text)
            chunks[i] = build_raw(sk, sc)
    new = build_raw(keys, chunks)
    k2, c2 = _try_parse_map(new)
    assert k2 == keys
    touched = {p[0] for p in edits}
    for k, a, b in zip(keys, c0, c2):
        if k not in touched:
            assert a == b, k
            continue
        ma = _try_parse_map(a)
        if ma is not None:
            mb = _try_parse_map(b)
            assert ma[0] == mb[0]
            subs = {p[1] for p in edits if p[0] == k and len(p) == 2}
            for s_, x, y in zip(ma[0], ma[1], mb[1]):
                if s_ not in subs:
                    assert x == y
    t = q.parse_node(new)
    for path, text in edits.items():
        v = t[path[0]]
        v = v[path[1]] if len(path) == 2 else v
        assert v == text
    return new, src, before


def contact(items, path):
    cellw, cellh, cols = 330, 420, 6
    fulls = [(n, im) for n, im in items if n.startswith("full_")]
    rest = [(n, im) for n, im in items if not n.startswith("full_")]
    rows_ = (len(rest) + cols - 1) // cols
    fh = 580
    sheet = Image.new("RGB", (max(cellw * cols, 495 * len(fulls) + 20), fh + cellh * rows_), (52, 57, 73))
    d = ImageDraw.Draw(sheet)
    for k, (n, im) in enumerate(fulls):
        t = im.copy()
        t.thumbnail((470, 530))
        sheet.paste(t.convert("RGB"), (k * 495 + 10, 30))
        d.text((k * 495 + 10, 8), n, fill="white")
    for k, (n, im) in enumerate(rest):
        t = im.copy()
        t.thumbnail((cellw - 20, cellh - 40))
        bg = Image.new("RGBA", t.size, (182, 186, 195, 255))
        bg.alpha_composite(t)
        x, y = k % cols * cellw, fh + k // cols * cellh
        sheet.paste(bg.convert("RGB"), (x + (cellw - t.width) // 2, y + 26))
        d.text((x + 6, y + 6), n, fill="white")
    sheet.save(path)


def main():
    files, lps = {}, {}

    def put(root, lp, data):
        m = amember(root, lp)
        files[m] = data
        lps[m] = lp

    report = {"slots": [], "gates": {}}
    ci_edits, tr_edits, fa_edits = {}, {}, {}
    atlas_cache = {}
    previews = []
    CI = load("master/generated/character_image.orderedmap")
    TR = load("master/generated/trimmed_image.orderedmap")
    FA = load("master/character/full_shot_image_attribute.orderedmap")
    for i, (fname, cid, code, s) in enumerate(SLOTS):
        lm = LANDMARKS[i]
        mraw = (MASTERS / fname).read_bytes()
        master = Image.open(io.BytesIO(mraw)).convert("RGBA")
        assert master.size == (1086, 1448)
        ui = f"character/{code}/ui/"
        W, H = master.size
        ex, ey = lm["eye"]
        cr = row(TR[f"{ui}full_shot_1440_1920_{s}"])
        cw, ch = int(cr[2]), int(cr[3])
        x = min(max(0, 1000 - ex), cw - W)
        y = min(max(0, 509 - ey), ch - H)
        fx, fy = x + ex, y + ey
        tkey = f"{ui}full_shot_1440_1920_{s}"
        ci_edits[(cid, str(s))] = f"{x},{y},{W},{H}"
        tr_edits[(tkey,)] = f"{x},{y},{cw},{ch}"
        fa_edits[(cid, str(s))] = f"1000,1000,1,{fx},{fy}"
        rec = dict(cid=cid, code=code, slot=s, master=fname, master_sha256=hashlib.sha256(mraw).hexdigest(),
                   eye_local=[ex, ey], head_width=lm["head"],
                   character_image=[CI[cid][str(s)], ci_edits[(cid, str(s))]],
                   trimmed_image=[TR[tkey], tr_edits[(tkey,)]],
                   full_shot_image_attribute=[FA[cid][str(s)], fa_edits[(cid, str(s))]])
        report["slots"].append(rec)
        std = png_bytes(master)
        full_lp = f"{ui}full_shot_1440_1920_{s}.png"
        rec["full_shot_roots"] = roots_of(full_lp)
        for r in rec["full_shot_roots"]:
            put(r, full_lp, wf_assets.png_encode(std))
        icons = make_icons(master, lm)
        icons["skill_cutin"] = make_cutin(master, lm)
        probs = gate.derived_icon_problems({k: np.asarray(v) for k, v in icons.items()}, MASKS, level=str(s))
        report["gates"][f"{code}_{s}"] = probs
        rec["coverage"] = {k: round(gate.coverage(np.asarray(v)), 3) for k, v in icons.items()}
        replaced = []
        for slot, im in icons.items():
            lp = f"{ui}{slot}_{s}.png"
            rs = roots_of(lp)
            if not rs:
                rec.setdefault("skipped_absent", []).append(slot)
                continue
            raw = png_bytes(im)
            for r in rs:
                put(r, lp, wf_assets.png_encode(raw))
            replaced.append(f"{slot}[{','.join(rs)}]")
            previews.append((f"{code}_{slot}_{s}", im))
            if slot == "skill_cutin":
                alp = f"{ui}skill_cutin_{s}.atf.deflate"
                ars = roots_of(alp)
                if ars:
                    ref = wf_atf.inflate(aread(ars[0], alp)[0])
                    atf = wf_atf.deflate(wf_atf.build_cutin_atf(raw, ref))
                    info = wf_atf.parse_atf(wf_atf.inflate(atf))
                    refi = wf_atf.parse_atf(ref)
                    assert (info["w"], info["h"], info["mips"]) == (refi["w"], refi["h"], refi["mips"])
                    assert (info["w"], info["h"]) == (1024, 512)
                    for r in ars:
                        put(r, alp, atf)
                    replaced.append(f"skill_cutin.atf.deflate[{','.join(ars)}]")
        sheet_lp = f"{ui}illustration_setting_sprite_sheet.png"
        if roots_of(sheet_lp):
            if code not in atlas_cache:
                araw = aread("upload", f"{ui}illustration_setting_sprite_sheet.atlas.amf3.deflate")[0]
                atlas = wf_dsl.parse_dsl(zlib.decompress(araw, -15))["tree"]
                sheet = png_img(aread("medium_upload", sheet_lp)[0])
                atlas_cache[code] = [atlas, sheet, sheet.size]
            atlas, sheet, _ = atlas_cache[code]
            es = [a for a in atlas if str(a["n"]).endswith(f"full_shot_illustration_setting_{s}")]
            assert len(es) == 1, atlas
            e = es[0]
            # 官方格 = 整张立绘缩进格内(朱/歌狼先例); 在 atlas 窗口(w,h)内等比 contain 居中; r=true 则顺时针 90° 存
            cw_, ch_ = (e["h"], e["w"]) if e.get("r") else (e["w"], e["h"])
            k_ = min(cw_ / W, ch_ / H)
            fit = master.resize((round(W * k_), round(H * k_)), Image.Resampling.LANCZOS)
            cell = Image.new("RGBA", (cw_, ch_), (0, 0, 0, 0))
            cell.alpha_composite(fit, ((cw_ - fit.width) // 2, (ch_ - fit.height) // 2))
            if e.get("r"):
                cell = cell.rotate(-90, expand=True)
            assert cell.size == (e["w"], e["h"]), (cell.size, e)
            sheet.paste(Image.new("RGBA", (e["w"], e["h"]), (0, 0, 0, 0)), (e["x"], e["y"]))
            sheet.alpha_composite(clear_hidden(cell), (e["x"], e["y"]))
            replaced.append(f"illustration_setting_sprite_sheet cell_{s}")
            report.setdefault("atlas", {})[f"{code}_{s}"] = dict(e)
        rec["replaced"] = replaced
        pv = Image.new("RGBA", master.size, (128, 128, 128, 255))
        pv.alpha_composite(master)
        d = ImageDraw.Draw(pv)
        d.line([(ex - 50, ey), (ex + 50, ey)], fill=(255, 0, 0, 255), width=4)
        d.line([(ex, ey - 50), (ex, ey + 50)], fill=(255, 0, 0, 255), width=4)
        previews.insert(len([p for p in previews if p[0].startswith("full_")]),
                        (f"full_{code}_{s} eye({ex},{ey}) xy({x},{y}) face({fx},{fy})", pv))
    for code, (atlas, sheet, size0) in atlas_cache.items():
        assert sheet.size == size0
        lp = f"character/{code}/ui/illustration_setting_sprite_sheet.png"
        b = wf_assets.png_encode(png_bytes(sheet))
        for r in roots_of(lp):
            put(r, lp, b)
        previews.append((f"{code}_illustration_sheet", sheet))
    tables = {}
    for lp, ed in (("master/generated/character_image.orderedmap", ci_edits),
                   ("master/generated/trimmed_image.orderedmap", tr_edits),
                   ("master/character/full_shot_image_attribute.orderedmap", fa_edits)):
        new, src, before = patch_table(lp, ed)
        put("upload", lp, new)
        tables[lp] = dict(base=src, rows={"/".join(k): [before[k], v] for k, v in ed.items()})
    report["tables"] = tables
    contact(previews, ART / "portrait192-contact.png")
    return files, lps, report


if __name__ == "__main__":
    files, lps, report = main()
    (ART / "portrait192-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf8")
    print(json.dumps(report["gates"], ensure_ascii=False, indent=1))
    pickle.dump((files, lps), open(ART / "portrait192-files.pkl", "wb"))
    print(len(files), sum(len(v) for v in files.values()))

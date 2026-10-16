# -*- coding: utf-8 -*-
"""构建全部族 → game 文件、预览 GIF、总览图、drop_manifest.json、budget.json。"""
import hashlib
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fxlib as X  # noqa: E402
import art  # noqa: E402
from build_fx import FAMILIES  # noqa: E402

FX = X.FX
V = 0.4                                   # 预览缩放
BG = (12, 14, 24, 255)


def field_bg():
    im = Image.new("RGBA", (int(1080 * V), int(1920 * V)), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, int(250 * V), im.width - 1, int(1230 * V)), outline=(40, 44, 70, 255))   # 敌带 y250-1230
    for i, x in enumerate((270, 540, 810)):
        d.ellipse((x * V - 18, 700 * V - 18, x * V + 18, 700 * V + 18), outline=(70, 60, 80, 255))  # 假想敌
    d.ellipse((540 * V - 10, 1650 * V - 10, 540 * V + 10, 1650 * V + 10), outline=(90, 110, 140, 255))  # 假想球/角色
    return im


def play_index(eff, t, lifetime=None, only_first=False):
    """按 timeline 语义把『第 t 帧』映射到 parts 帧号；返回 None=已结束。"""
    seqs = eff.seqs or ([{"begin": 1, "end": eff.main_len, "name": "neutral", "kind": "once"}] +
                        ([{"begin": eff.main_len + 1, "end": eff.total, "name": "end", "kind": "once"}] if eff.total > eff.main_len else []))
    end = [s for s in seqs if s["name"] == "end"]
    body = [s for s in seqs if s["name"] != "end"]
    if only_first:
        body = body[:1]
    life = lifetime if lifetime is not None else sum(s["end"] - s["begin"] + 1 for s in body)
    if t < life:
        f = 0
        for s in body:
            n = s["end"] - s["begin"] + 1
            if s["kind"] == "loop":
                return s["begin"] - 1 + (t - f) % n
            if t - f < n:
                return s["begin"] - 1 + (t - f)
            f += n
        return body[-1]["end"] - 1
    if end:
        k = t - life
        n = end[0]["end"] - end[0]["begin"] + 1
        return end[0]["begin"] - 1 + k if k < n else None
    return None


def render_seq(fam, plan, n, base_fn, size=None, origin=None):
    """plan = [(effect, start, lifetime, only_first, anchor(x,y), dsl_scale)]"""
    frames = []
    for t in range(n):
        im = base_fn()
        for eff, st, life, of, (ax, ay), sc in plan:
            if t < st:
                continue
            idx = play_index(eff, t - st, life, of)
            if idx is None:
                continue
            im = X.render_frame(fam[eff.name][0], eff, idx, origin=(ax * V, ay * V), scale=sc * V, base=im)
        frames.append(im)
    return frames


def main():
    built = {}
    fams = {}
    manifest = []
    budget = []
    effmap = {}
    for sub, fn in FAMILIES:
        F = fn()
        out = FX / sub
        info = X.build(F, out)
        fams[sub] = (F, info)
        for e in F.effects:
            effmap[e.name] = (F, e)
        W, H = info["sheet"]
        uniq = sum((w) * (h) for w, h in info["sizes"].values())
        peak = 0
        for e in F.effects:
            for f in range(e.total):
                peak = max(peak, sum(1 for L in e.layers if L.start <= f < L.start + len(L.frames) and L.frames[f - L.start][5] > 0))
        budget.append({"family": sub, "sheet": [W, H], "packed_px": (W + 2) * (H + 2), "fill": round(uniq / (W * H), 3),
                       "effects": [e.name for e in F.effects], "images": len(F.images), "peak_quads": peak})
        for lp, data in sorted(info["files"].items()):
            p = out / "game" / lp
            prev = None
            try:
                raw, src = X.read_raw(lp)
                prev = {"upload": {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "source": src}}
            except FileNotFoundError:
                pass
            manifest.append({"logical": lp, "local": str(p), "roots": ["upload"], "sha256": X.sha256(data), "size": len(data),
                             "replaces_existing": prev is not None, **({"previous": prev} if prev else {})})
    # 固有状态图标
    icon = art.unique_icon()
    lp = "battle/common/unique_condition/unique_seris_dragon_king.png"
    data = X.png_obf(icon)
    p = FX / "icon" / "game" / lp
    p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    icon.resize((192, 192), Image.NEAREST).save(FX / "icon" / "unique_seris_dragon_king_x4.png")
    raw, src = X.read_raw(lp)
    manifest.append({"logical": lp, "local": str(p), "roots": ["upload"], "sha256": X.sha256(data), "size": len(data),
                     "replaces_existing": True, "previous": {"upload": {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "source": src}}})

    manifest += json.loads((FX / "pf_quiet" / "manifest_part.json").read_text("utf-8"))      # 官方 PF 静音副本（copy_pf.py）
    (FX / "drop_manifest.json").write_text(json.dumps({"character": {"id": "129999", "code": "seris_dragon_king"},
                                                       "view": "WF_TIP=206", "files": manifest}, ensure_ascii=False, indent=2), "utf-8")
    (FX / "_scripts" / "budget.json").write_text(json.dumps(budget, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(budget, ensure_ascii=False))

    fam = {k: v for k, v in effmap.items()}
    C = (540, 960)
    previews = {}
    # 1 潮涌：DSL 寿命 32（neutral）+ end
    previews["tide"] = render_seq(fam, [(effmap["seris_tide"][1], 0, 32, False, C, 1.0)], 46, field_bg)
    # 2 龙息：升空(220) + 三段吐息 40/95/150（偏移 0,-740；scale 1.0/1.3/1.6）
    plan = [(effmap["seris_flight"][1], 0, 220, False, C, 1.0)]
    for st, sc in ((40, 1.0), (95, 1.3), (150, 1.6)):
        plan.append((effmap["seris_breath"][1], st, None, True, (540, 960 - 740), sc))
    previews["breath"] = render_seq(fam, plan, 240, field_bg)
    # 3 冲撞：人形 1.0 / 龙形 1.35，挂在敌人身上
    def small_bg(w=600, h=600):
        def f():
            im = Image.new("RGBA", (int(w * V * 1.5), int(h * V * 1.5)), BG)
            return im
        return f
    def sub_seq(name, n, sc, w=600, h=600, oy=0.5):
        F, e = effmap[name]
        frames = []
        for t in range(n):
            idx = play_index(e, t, None, True)
            im = small_bg(w, h)()
            if idx is not None:
                im = X.render_frame(F, e, idx, origin=(w * V * 0.75, h * V * 1.5 * oy), scale=sc * V * 1.5, base=im)
            frames.append(im)
        return frames
    previews["dash_human"] = sub_seq("seris_dash", 32, 1.0)
    previews["dash_dragon"] = sub_seq("seris_dash", 32, 1.35)
    # 4 Lv4
    previews["lv4_human"] = render_seq(fam, [(effmap["seris_lv4_human"][1], 0, 60, False, C, 1.0)], 76, field_bg)
    previews["lv4_dragon"] = render_seq(fam, [(effmap["seris_lv4_dragon"][1], 0, 60, False, C, 1.0)], 76, field_bg)
    previews["red_bolt"] = sub_seq("seris_red_bolt", 16, 1.0, 400, 400)
    # 5 化龙 / 回龙人
    previews["transform"] = sub_seq("seris_transform", 48, 1.0, 600, 800, 0.62)
    previews["revert"] = sub_seq("seris_revert", 34, 1.0, 600, 600, 0.6)
    gifdir = FX / "preview"; gifdir.mkdir(exist_ok=True)
    for k, frs in previews.items():
        X.save_gif(frs, gifdir / f"{k}.gif")
    # 总览：每个预览取 4 张关键帧
    picks = {"tide": [4, 9, 13, 17], "breath": [10, 48, 105, 160], "dash_human": [1, 3, 6, 12], "dash_dragon": [2, 5, 9, 16],
             "lv4_human": [3, 14, 24, 33], "lv4_dragon": [3, 16, 26, 36], "red_bolt": [1, 4, 8, 12],
             "transform": [4, 10, 16, 24], "revert": [3, 10, 16, 22]}
    rows = []
    for k, idxs in picks.items():
        fr = [previews[k][i] for i in idxs]
        h = 330
        fr = [f.resize((int(f.width * h / f.height), h), Image.NEAREST) for f in fr]
        row = Image.new("RGBA", (sum(f.width for f in fr) + 8 * len(fr) + 150, h + 8), (24, 26, 36, 255))
        d = ImageDraw.Draw(row)
        try:
            font = ImageFont.truetype("msyh.ttc", 18)
        except Exception:
            font = None
        d.text((8, 8), k, fill=(240, 240, 120, 255), font=font)
        for i, ii in enumerate(idxs):
            d.text((8, 40 + i * 22), f"f{ii}", fill=(170, 170, 190, 255), font=font)
        x = 150
        for f in fr:
            row.alpha_composite(f, (x, 4)); x += f.width + 8
        rows.append(row)
    Wd = max(r.width for r in rows)
    sheet = Image.new("RGBA", (Wd, sum(r.height for r in rows)), (24, 26, 36, 255))
    y = 0
    for r in rows:
        sheet.alpha_composite(r, (0, y)); y += r.height
    sheet.convert("RGB").save(FX / "特效总览.png")
    print("ok", sheet.size)


if __name__ == "__main__":
    main()

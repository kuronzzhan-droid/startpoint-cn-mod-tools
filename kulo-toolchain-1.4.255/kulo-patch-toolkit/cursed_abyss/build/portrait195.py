# -*- coding: utf-8 -*-
"""1.4.194 -> 1.4.195: 月狼 149986 black_wolf_knight_moon _0/_1 换作者 1009 重选立绘 + 现成面部特写图标(保留场景) + ATF + 图鉴格 + 三张定位表。"""
import os
os.environ["WF_TIP"] = "194"
from portrait192 import *  # noqa  (p192_common 视图 = 1.4.194)
import base149
assert base149.TIP == 194
PK = Path(r"D:/WF/out/立绘重设计-20261008/月狼替换包-20261009")
CID, CODE = "149986", "black_wolf_knight_moon"
EYE = {0: (520, 135), 1: (575, 105)}
SL = ["square","square_132_132","square_round_136_136","square_round_95_95","battle_member_status","cutin_skill_chain",
      "thumb_level_up","thumb_party_unison","thumb_party_main","battle_control_board","skill_cutin"]
OUT = Path(__file__).resolve().parent.parent / "patch"
files, lps = {}, {}
def put(root, lp, data): m = amember(root, lp); files[m] = data; lps[m] = lp
ui = f"character/{CODE}/ui/"
TR = load("master/generated/trimmed_image.orderedmap"); CI = load("master/generated/character_image.orderedmap")
FA = load("master/character/full_shot_image_attribute.orderedmap")
ci_e, tr_e, fa_e, rep = {}, {}, {}, []
araw = aread("upload", f"{ui}illustration_setting_sprite_sheet.atlas.amf3.deflate")[0]
atlas = wf_dsl.parse_dsl(zlib.decompress(araw, -15))["tree"]
sheet_lp = f"{ui}illustration_setting_sprite_sheet.png"
sheet = png_img(wf_assets.png_decode(aread("medium_upload", sheet_lp)[0])); size0 = sheet.size
for s in (0, 1):
    raw = (PK / "full_shot" / f"full_shot_1440_1920_{s}.png").read_bytes()
    master = Image.open(io.BytesIO(raw)).convert("RGBA"); W, H = master.size
    assert (W, H) == (1086, 1448) and master.getpixel((0, 0))[3] == 0
    ex, ey = EYE[s]; tkey = f"{ui}full_shot_1440_1920_{s}"
    cr = row(TR[tkey]); cw, ch = int(cr[2]), int(cr[3])
    x = min(max(0, 1000 - ex), cw - W); y = min(max(0, 509 - ey), ch - H)
    ci_e[(CID, str(s))] = f"{x},{y},{W},{H}"; tr_e[(tkey,)] = f"{x},{y},{cw},{ch}"; fa_e[(CID, str(s))] = f"1000,1000,1,{x+ex},{y+ey}"
    rep.append(dict(slot=s, ci=[CI[CID][str(s)], ci_e[(CID, str(s))]], tr=[TR[tkey], tr_e[(tkey,)]], fa=[FA[CID][str(s)], fa_e[(CID, str(s))]]))
    flp = f"{tkey}.png"
    for r in roots_of(flp): put(r, flp, wf_assets.png_encode(png_bytes(master)))
    for slot in SL:
        lp = f"{ui}{slot}_{s}.png"; rs = roots_of(lp); assert rs, lp
        im = Image.open(PK / "icons" / f"{slot}_{s}.png").convert("RGBA")
        old = png_img(wf_assets.png_decode(aread(rs[0], lp)[0])); assert im.size == old.size, (lp, im.size, old.size)
        std = png_bytes(im)
        for r in rs: put(r, lp, wf_assets.png_encode(std))
        if slot == "skill_cutin":
            alp = f"{ui}skill_cutin_{s}.atf.deflate"; ars = roots_of(alp); assert ars
            ref = wf_atf.inflate(aread(ars[0], alp)[0]); atf = wf_atf.deflate(wf_atf.build_cutin_atf(std, ref))
            a, b = wf_atf.parse_atf(wf_atf.inflate(atf)), wf_atf.parse_atf(ref)
            assert (a["w"], a["h"], a["mips"]) == (b["w"], b["h"], b["mips"]) == (1024, 512, b["mips"])
            for r in ars: put(r, alp, atf)
    e = [a for a in atlas if str(a["n"]).endswith(f"full_shot_illustration_setting_{s}")]; assert len(e) == 1; e = e[0]
    cw_, ch_ = (e["h"], e["w"]) if e.get("r") else (e["w"], e["h"])
    k_ = min(cw_ / W, ch_ / H); fit = master.resize((round(W * k_), round(H * k_)), Image.Resampling.LANCZOS)
    cell = Image.new("RGBA", (cw_, ch_), (0, 0, 0, 0)); cell.alpha_composite(fit, ((cw_ - fit.width) // 2, (ch_ - fit.height) // 2))
    if e.get("r"): cell = cell.rotate(-90, expand=True)
    assert cell.size == (e["w"], e["h"])
    sheet.paste(Image.new("RGBA", (e["w"], e["h"]), (0, 0, 0, 0)), (e["x"], e["y"])); sheet.alpha_composite(clear_hidden(cell), (e["x"], e["y"]))
assert sheet.size == size0
b_ = wf_assets.png_encode(png_bytes(sheet))
for r in roots_of(sheet_lp): put(r, sheet_lp, b_)
for lp, ed in (("master/generated/character_image.orderedmap", ci_e), ("master/generated/trimmed_image.orderedmap", tr_e),
               ("master/character/full_shot_image_attribute.orderedmap", fa_e)):
    new, src, before = patch_table(lp, ed); put("upload", lp, new); print(lp, "base", src)
print(json.dumps(rep, ensure_ascii=False, indent=1))
CAP = 5 * 1024 * 1024 - 64 * 1024
est = {m: len(zlib.compress(b, 9)) + 120 for m, b in files.items()}
tabs = sorted(m for m in files if lps[m].endswith(".orderedmap"))
bins = [[list(tabs), sum(est[m] for m in tabs)]]
for m in sorted((m for m in files if m not in tabs), key=lambda m: (-est[m], m)):
    for bn in bins:
        if bn[1] + est[m] <= CAP: bn[0].append(m); bn[1] += est[m]; break
    else: bins.append([[m], est[m]])
for k, (mem, _) in enumerate(bins, 1):
    name = f"pinball-1.4.194-1.4.195-{k}-moon-wolf-art-local.zip"; path = OUT / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(mem): zf.writestr(m, files[m])
    blob = path.read_bytes(); assert len(blob) <= 5 * 1024 * 1024
    integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(mem), "files": sorted(mem),
             "member_sha256": {m: hashlib.sha256(files[m]).hexdigest() for m in sorted(mem)}, "logical_paths": {m: lps[m] for m in sorted(mem)},
             "applies_on": "1.4.194", "version": "1.4.195", "part": f"{k}/{len(bins)}", "face_anchor": rep,
             "log": ["月狼 149986 _0/_1 立绘换作者1009重选版 + 面部特写图标(保留场景) + skill_cutin ATF + 图鉴格 + 三张定位表行级"]}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(name, len(blob), integ["sha256"], len(mem))
pickle.dump((files, lps), open(ART / "portrait195-files.pkl", "wb"))

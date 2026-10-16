# -*- coding: utf-8 -*-
"""1.4.195 -> 1.4.196：五重 boss 侧 layer0 瘦身（只挪 atlas 区域 x/y，带 1px 环；渲染不变）。
输入 = fb_slim196_repack.py 产出的 overlay/log；这里只挑「五重自有表」+「单表省 ≥4000 px」的官方表，
从 1.4.195 原件重新逐区域校验后打 zip + integrity，并跑门禁 before/after。"""
import hashlib, json, os, pickle, zipfile, zlib, sys
os.environ["WF_TIP"] = "195"
from fb_layer0_gate import *  # noqa
sys.path.insert(0, str(P.base149.TOOLS))
from wf_battle_atlas_repack import decode_png, decode_atlas
from fb_slim196_repack import crop_pad, norm
import base149
assert base149.TIP == 195

ART = Path(__file__).resolve().parent.parent / "art" / "fb_slim196"
OUTP = Path(__file__).resolve().parent.parent / "patch"
MIN_PX = 4000
ov_all = pickle.load(open(ART / "repack_overlay.pkl", "rb"))
log_all = [x for x in json.load(open(ART / "repack_log.json", encoding="utf-8")) if "gain_px" in x]
chosen = [x for x in log_all if x["gain_px"] >= MIN_PX or "/five_boss_v2/" in x["sheet"]]
v0 = View()
files, lps = {}, {}
for x in chosen:
    s = x["sheet"]
    png0, atl0 = v0.file(s + ".png"), v0.file(s + ".atlas.amf3.deflate")
    png1, atl1 = ov_all[s + ".png"], ov_all[s + ".atlas.amf3.deflate"]
    # 根：两件都只在 upload 根（fb 预检已确认无 medium/android 副本、无 ATF）
    assert [r for r in P.ROOTS if P.aread(r, s + ".png")[0] is not None] == ["upload"], s
    assert [r for r in P.ROOTS if P.aread(r, s + ".atlas.amf3.deflate")[0] is not None] == ["upload"], s
    for suf in (".atf.deflate", ".atf"):
        assert all(P.aread(r, s + suf)[0] is None for r in P.ROOTS), s
    i0, i1 = decode_png(png0), decode_png(png1)
    r0, r1 = decode_atlas(atl0), decode_atlas(atl1)
    assert len(r0) == len(r1)
    for a, b in zip(r0, r1):
        assert list(a) == list(b) and {k: v for k, v in a.items() if k not in "xy"} == {k: v for k, v in b.items() if k not in "xy"}
        assert norm(crop_pad(i0, a["x"] - 1, a["y"] - 1, a["w"] + 2, a["h"] + 2)) == \
            norm(crop_pad(i1, b["x"] - 1, b["y"] - 1, b["w"] + 2, b["h"] + 2)), (s, a["n"])
    assert i1.size == tuple(x["after"]) and i0.size == tuple(x["before"])
    for suf, data in ((".png", png1), (".atlas.amf3.deflate", atl1)):
        m = P.amember("upload", s + suf); files[m] = data; lps[m] = s + suf
overlay = {lps[m]: b for m, b in files.items()}

# ---- 门禁
chars = char_table(v0)
pick, ps = worst_party(v0, chars)
before = gate(v0, ps)
v1 = View(overlay)
after = gate(v1, ps)


def tipping(v, quests):
    """按最坏 18 人的挑选顺序逐个加人，记录还能装下的人数与该点占用。"""
    out = {}
    common = {s: d for s, (d, _) in sheets_from_anims(v, {a: "c" for a in COMMON_FX}).items()}
    for qid in quests:
        an, _ = round_assets(v, qid)
        cur = dict(common); cur.update({s: d for s, (d, _) in sheets_from_anims(v, an).items()})
        base = run_pack(cur); n = 0; last = base
        for cid, code, role in pick:
            parts = {"leader": ("main", "skill", "leader"), "main": ("main", "skill"), "unison": ("skill",)}[role]
            nxt = dict(cur)
            for p_ in parts:
                nxt.update(chars[cid][p_])
            r = run_pack(nxt)
            if not r["ok"]:
                break
            cur, n, last = nxt, n + 1, r
        out[qid] = dict(base=base, fit=n, at=last)
    return out


tip0, tip1 = tipping(v0, R0 + R1), tipping(v1, R0 + R1)
TARGET = 0.85 * CAP
common_area = sum(area(d) for s, (d, _) in sheets_from_anims(v0, {a: "c" for a in COMMON_FX}).items())
gate_rows = []
for q in R0 + R1:
    b, a = before[q], after[q]
    gate_rows.append(dict(quest=q, bosses=b["bosses"], before=b, after=a, tip_before=tip0[q], tip_after=tip1[q],
                          need_to_fit_85=(a["area"] - TARGET)))
json.dump(dict(party=pick, party_mpx=sum(area(d) for d in ps.values()) / 1e6, common_fx_mpx=common_area / 1e6,
               rows=gate_rows, chosen=chosen), open(ART / "gate_before_after.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)

# ---- zip + integrity
CAPZ = 5 * 1024 * 1024 - 64 * 1024
est = {m: len(zlib.compress(b, 9)) + 120 for m, b in files.items()}
bins = []
for m in sorted(files, key=lambda m: (-est[m], m)):
    for bn in bins:
        if bn[1] + est[m] <= CAPZ:
            bn[0].append(m); bn[1] += est[m]; break
    else:
        bins.append([[m], est[m]])
LOG = [f"五重 boss 侧 layer0 瘦身：{len(chosen)} 张精灵表只挪 atlas 区域 x/y（带 1px bleed 环），帧名/尺寸/旋转/偏移与顺序不变",
       "不改任何表、DSL、boss 数值/时机/招式；第 2/3/4 项（合并重复特效族、删不触发槽、合并垫片）实测 0 收益或不可证等价，未做"]
results = []
for k, (mem, _) in enumerate(bins, 1):
    name = f"pinball-1.4.195-1.4.196-{k}-five-boss-atlas-slim-local.zip"; path = OUTP / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(mem):
            zf.writestr(m, files[m])
    blob = path.read_bytes(); assert len(blob) <= 5 * 1024 * 1024
    with zipfile.ZipFile(path) as zf:
        assert sorted(zf.namelist()) == sorted(mem) and all(zf.read(m) == files[m] for m in mem)
    integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(mem),
             "files": sorted(mem), "member_sha256": {m: hashlib.sha256(files[m]).hexdigest() for m in sorted(mem)},
             "logical_paths": {m: lps[m] for m in sorted(mem)}, "applies_on": "1.4.195", "version": "1.4.196",
             "part": f"{k}/{len(bins)}",
             "sheets": [{kk: x[kk] for kk in ("sheet", "before", "after", "gain_px", "records", "unique")} for x in chosen],
             "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    results.append((str(path), len(blob), integ["sha256"], len(mem)))
    print(name, len(blob), integ["sha256"], len(mem))

print(f"party {sum(area(d) for d in ps.values())/1e6:.3f} Mpx; common fx {common_area/1e6:.3f}")
for r in gate_rows:
    b, a = r["before"], r["after"]
    print(r["quest"], f"rects {b['rects']}->{a['rects']} area {b['area']/1e6:.3f}->{a['area']/1e6:.3f} "
          f"fill {100*b['fill']:.1f}->{100*a['fill']:.1f}% boss {b['boss_area']/1e6:.3f}->{a['boss_area']/1e6:.3f} "
          f"{'PASS' if a['ok'] else 'FAIL'}; fit {r['tip_before']['fit']}->{r['tip_after']['fit']}/18 "
          f"bossonly {r['tip_after']['base']['w']}x{r['tip_after']['base']['h']}")

# -*- coding: utf-8 -*-
"""1.4.193 -> 1.4.194: 用作者认可的「保留场景面部特写」图标一对一替换 1.4.192 派生图标(含 skill_cutin 安卓 ATF)。"""
from p192_common import *
import json, pickle, zlib
import wf_assets, wf_atf
SRC = Path(r"D:/WF/out/立绘重设计-20261008/图标重派生-保留场景")
OUT = Path(__file__).resolve().parent.parent / "patch"
SL = ["square","square_132_132","square_round_136_136","square_round_95_95","battle_member_status","cutin_skill_chain",
      "thumb_level_up","thumb_party_unison","thumb_party_main","battle_control_board","skill_cutin"]
files192, lps192 = pickle.load(open(ART / "portrait192-files.pkl", "rb"))
by_lp = {}
for m, lp in lps192.items(): by_lp.setdefault(lp, []).append(m)
files, lps, log = {}, {}, []
for _, cid, code, s in SLOTS:
    ui = f"character/{code}/ui/"
    for slot in SL:
        lp = f"{ui}{slot}_{s}.png"
        ms = by_lp[lp]
        raw = (SRC / code / f"{slot}_{s}.png").read_bytes()
        new = Image.open(io.BytesIO(raw)).convert("RGBA")
        old = png_img(wf_assets.png_decode(files192[ms[0]]) if hasattr(wf_assets, "png_decode") else files192[ms[0]])
        assert new.size == old.size, (lp, new.size, old.size)
        b = io.BytesIO(); new.save(b, "PNG", optimize=True); std = b.getvalue()
        enc = wf_assets.png_encode(std)
        for m in ms: files[m] = enc; lps[m] = lp
        if slot == "skill_cutin":
            alp = f"{ui}skill_cutin_{s}.atf.deflate"
            ams = by_lp[alp]
            ref = wf_atf.inflate(aread(roots_of(alp)[0], alp)[0])
            atf = wf_atf.deflate(wf_atf.build_cutin_atf(std, ref))
            info = wf_atf.parse_atf(wf_atf.inflate(atf)); refi = wf_atf.parse_atf(ref)
            assert (info["w"], info["h"], info["mips"]) == (refi["w"], refi["h"], refi["mips"]) == (1024, 512, refi["mips"])
            for m in ams: files[m] = atf; lps[m] = alp
assert len({lps[m] for m in files}) == 44 + 4, len({lps[m] for m in files})
CAP = 5 * 1024 * 1024 - 64 * 1024
est = {m: len(zlib.compress(b, 9)) + 120 for m, b in files.items()}
bins = []
for m in sorted(files, key=lambda m: (-est[m], m)):
    for bn in bins:
        if bn[1] + est[m] <= CAP: bn[0].append(m); bn[1] += est[m]; break
    else: bins.append([[m], est[m]])
res = []
for k, (members, _) in enumerate(bins, 1):
    name = f"pinball-1.4.193-1.4.194-{k}-icon-reframe-local.zip"; path = OUT / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members): zf.writestr(m, files[m])
    blob = path.read_bytes(); assert len(blob) <= 5 * 1024 * 1024
    integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(files[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {m: lps[m] for m in sorted(members)}, "applies_on": "1.4.193", "version": "1.4.194",
             "part": f"{k}/{len(bins)}", "log": ["1.4.192 四套派生图标改为保留场景的面部特写(作者1008认可), skill_cutin 同步重编安卓 ATF; full_shot/表不动"]}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    res.append({x: integ[x] for x in ("name", "size", "sha256", "members")})
print(json.dumps(res, ensure_ascii=False, indent=1)); print(len(files), "members")

# -*- coding: utf-8 -*-
"""portrait192 打包: 按成员装箱成 <=5MiB 的 1.4.191->1.4.192 分包 + integrity.json。"""
from p192_common import *
import json, pickle, zlib
OUT = Path(__file__).resolve().parent.parent / "patch"
CAP = 5 * 1024 * 1024 - 64 * 1024   # 留 zip 目录余量
NL = chr(10)
files, lps = pickle.load(open(ART / "portrait192-files.pkl", "rb"))
report = json.loads((ART / "portrait192-report.json").read_text("utf8"))
est = {m: len(zlib.compress(b, 9)) + 120 for m, b in files.items()}
tables = sorted(m for m in files if lps[m].endswith(".orderedmap"))
rest = sorted((m for m in files if m not in tables), key=lambda m: (-est[m], m))
bins = [[list(tables), sum(est[m] for m in tables)]]
for m in rest:
    for b in bins:
        if b[1] + est[m] <= CAP:
            b[0].append(m); b[1] += est[m]; break
    else:
        bins.append([[m], est[m]])
n = len(bins)
results = []
LOG = ["四张立绘换新: 杰拉德(149999)_0 ZL2 / 杰拉尔(129992)_0 V2 / 歌狼(149986)_0 ZB3 / 歌狼_1 Y3",
       "full_shot + 派生图标(官方1.4.0多数票形状蒙版, 夜靛底 (20,30,95)) + skill_cutin PNG/安卓ATF + 立绘图集格原位重画(atlas 不动)",
       "三张定位表行级改写: character_image / trimmed_image / full_shot_image_attribute(脸锚=眼中点→(1000,509))"]
for k, (members, _) in enumerate(bins, 1):
    name = f"pinball-1.4.191-1.4.192-{k}-portrait-redesign-local.zip"
    path = OUT / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, files[m])
    blob = path.read_bytes()
    assert len(blob) <= 5 * 1024 * 1024, (name, len(blob))
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None
        for m in sorted(members):
            assert zf.read(m) == files[m]
    integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(files[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {m: lps[m] for m in sorted(members)}, "applies_on": "1.4.191", "version": "1.4.192",
             "part": f"{k}/{n}", "log": LOG}
    if k == 1:
        integ["tables"] = report["tables"]
        integ["face_anchor"] = [{x: s[x] for x in ("cid", "code", "slot", "eye_local", "character_image", "trimmed_image", "full_shot_image_attribute")} for s in report["slots"]]
        integ["gates"] = report["gates"]
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
    results.append({x: integ[x] for x in ("name", "size", "sha256", "members")})
print(json.dumps(results, ensure_ascii=False, indent=1))
assert sum(r["members"] for r in results) == len(files)

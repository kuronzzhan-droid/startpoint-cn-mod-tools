# -*- coding: utf-8 -*-
"""杰拉德(149999 white_wolf_gerald) 语音重录: 1.4.192 视图之上的成员 + 分包。"""
import os; os.environ["WF_TIP"] = "192"
import sys; sys.path.insert(0, r"D:/WF/startpoint-cn-wiki/mod-tools")
from p192_common import *
import json, shutil, zlib
import wf_share_update_codec as codec
import wf_assets
assert base149._ZIPS[-1].name.startswith("pinball-1.4.191-1.4.192-"), base149._ZIPS[-1]
SRC = Path(r"D:/WF/out/杰拉德语音重录-20261008/成品")
CID, CODE = "149999", "white_wolf_gerald"
SP = "master/character/character_speech.orderedmap"
BUILD = Path(__file__).resolve().parent
OUT = BUILD / "out193_voice"
PATCH = BUILD.parent / "patch"
sha = lambda b: hashlib.sha256(b).hexdigest()
lines = {x["path"]: x for x in json.loads((SRC / "台词清单.json").read_text("utf8"))}
files, lps, report = {}, {}, {"voices": [], "rows": [], "skipped": []}
# ---- voices
for p in sorted(SRC.rglob("*.mp3")):
    slot = p.relative_to(SRC).with_suffix("").as_posix()
    lp = f"character/{CODE}/voice/{slot}.mp3"
    std = p.read_bytes()
    stored = wf_assets.mp3_encode(std)
    assert wf_assets.mp3_decode(stored) == std, slot
    roots = roots_of(lp) or ["upload"]
    for r in roots:
        before, src = aread(r, lp)
        m = amember(r, lp)
        files[m] = stored; lps[m] = lp
        report["voices"].append(dict(slot=slot, root=r, member=m, size=len(stored), sha256=sha(stored),
                                     before_sha256=sha(before) if before else None, before_src=src,
                                     new_file=before is None))
# ---- speech table
sroots = roots_of(SP); assert sroots == ["upload"], sroots
raw, base = aread("upload", SP)
flat = codec.unpack(raw); assert codec.unpack(codec.pack(flat)) == flat
leaf = flat[CID]; rows = codec.csv_read(leaf); orig = [list(r) for r in rows]
want = {f"home/home_{i}": lines[f"home/home_{i}"]["zh"] for i in range(12)}
for slot in ("ally/join", "ally/evolution"): want[slot] = lines[slot]["zh"]
seen = set()
for r in rows:
    if r[4] in want:
        assert r[4] not in seen; seen.add(r[4])
        before = list(r); r[3] = want[r[4]]
        if r[4].startswith("home/"): r[1] = "2"
        report["rows"].append(dict(slot=r[4], op="update", before=before, after=list(r)))
for i in range(12):
    s = f"home/home_{i}"
    if s not in seen:
        r = ["0", "2", "", want[s], s]; rows.append(r)
        report["rows"].append(dict(slot=s, op="append", before=None, after=r))
newleaf = codec.csv_write_like(rows, leaf)
flat2 = dict(flat); flat2[CID] = newleaf
table = codec.pack(flat2)
chk = codec.unpack(table)
assert list(chk) == list(flat)
assert all(chk[k] == flat[k] for k in flat if k != CID)
assert codec.csv_read(chk[CID]) == rows
m = amember("upload", SP); files[m] = table; lps[m] = SP
report["table"] = dict(base=base, before_sha256=sha(raw), after_sha256=sha(table), size=len(table), keys=len(flat))
# ---- dump members
if OUT.exists(): shutil.rmtree(OUT)
for mm, b in files.items():
    p = OUT / "members" / mm; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
(OUT / "members.json").write_text(json.dumps({mm: dict(logical_path=lps[mm], sha256=sha(files[mm]), size=len(files[mm]))
    for mm in sorted(files)}, ensure_ascii=False, indent=2) + "\n", "utf-8")
(OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
# ---- zips
CAP = 5 * 1024 * 1024 - 64 * 1024
est = {mm: len(zlib.compress(b, 9)) + 120 for mm, b in files.items()}
tables = sorted(mm for mm in files if lps[mm].endswith(".orderedmap"))
rest = sorted((mm for mm in files if mm not in tables), key=lambda mm: (-est[mm], mm))
bins = [[list(tables), sum(est[mm] for mm in tables)]]
for mm in rest:
    for b in bins:
        if b[1] + est[mm] <= CAP: b[0].append(mm); b[1] += est[mm]; break
    else: bins.append([[mm], est[mm]])
LOG = ["杰拉德(149999 white_wolf_gerald)语音全量重录: ally 2 + battle 20 + home 12 共 34 条 mp3 (44.1kHz mono 96k CBR, 存储态编码)",
       "character_speech 149999 叶行级改写: home_0..11 中文字幕(约束2全显示) + ally/join、ally/evolution 字幕; 其余键逐字节不变",
       "skill_ready_alt_1..3 随包但当前 APK 只对 129992/139993/159998 轮换, 149999 不会播放(需新 APK)"]
res = []
for old in PATCH.glob("pinball-1.4.192-1.4.193-*-gerald-voice-local*"): old.unlink()
for k, (members, _) in enumerate(bins, 1):
    name = f"pinball-1.4.192-1.4.193-{k}-gerald-voice-local.zip"; path = PATCH / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for mm in sorted(members): zf.writestr(mm, files[mm])
    blob = path.read_bytes(); assert len(blob) <= 5 * 1024 * 1024
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None and all(zf.read(mm) == files[mm] for mm in members)
    integ = {"name": name, "size": len(blob), "sha256": sha(blob), "members": len(members), "files": sorted(members),
             "member_sha256": {mm: sha(files[mm]) for mm in sorted(members)},
             "logical_paths": {mm: lps[mm] for mm in sorted(members)}, "applies_on": "1.4.192", "version": "1.4.193",
             "part": f"{k}/{len(bins)}", "log": LOG}
    if k == 1:
        integ["tables"] = {SP: {"base": base, "rows": {f"{CID}/{x['slot']}": [x['before'][3] if x['before'] else None, x['after'][3]] for x in report["rows"]}}}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    res.append({x: integ[x] for x in ("name", "size", "sha256", "members")})
print(json.dumps(res, ensure_ascii=False, indent=1)); print(len(files), "members")

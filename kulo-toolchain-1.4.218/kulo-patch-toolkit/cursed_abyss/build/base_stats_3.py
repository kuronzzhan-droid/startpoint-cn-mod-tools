# -*- coding: utf-8 -*-
"""魔王/深渊之兽/歼灭者 基础 HP/ATK 降到官方 5★「特殊」(character c6=4) lv100 中位数；全等级点按 lv100 比例缩放。叠加在 1.4.163 上。"""
import copy, hashlib, json, os, zipfile, statistics as S
os.environ.setdefault("WF_TIP", "164")
from live149 import *  # noqa
from off import official
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.163-1.4.164-1-base-stats-3chars-local.zip"
LP = "master/character/character_status.orderedmap"
OC = official("master/character/character.orderedmap"); OS_ = official(LP)
ref = [tuple(map(int, OS_[k]["100"].split(","))) for k, v in OC.items()
       if rows(v)[0][2] == "5" and rows(v)[0][6] == "4" and k in OS_ and "100" in OS_[k]]
MH, MA = S.median(x[0] for x in ref), S.median(x[1] for x in ref)
TH, TA = int(MH + 0.5), int(MA + 0.5)
T = load(LP); BASE = copy.deepcopy(T); LOG = [f"参照：官方1.4.0 5★ 特殊型 {len(ref)} 人 lv100 中位数 HP {MH} / ATK {MA} → 取 {TH}/{TA}"]
C = load("master/character/character.orderedmap")
for cid, nm in (("169995", "魔王"), ("169980", "深渊之兽"), ("179981", "歼灭者")):
    r = rows(C[cid])[0]; assert r[2] == "5" and r[6] == "4", (cid, r[:8])
    s = dict(T[cid]); h0, a0 = map(int, s["100"].split(","))
    assert h0 > TH and a0 > TA, (cid, h0, a0)
    fh, fa = TH / h0, TA / a0; new = {}
    for lv, v in s.items():
        h, a = map(int, v.split(",")); new[lv] = f"{int(round(h * fh))},{int(round(a * fa))}"
    assert new["100"] == f"{TH},{TA}"
    T[cid] = new
    LOG.append(f"{nm} {cid}: " + " ".join(f"lv{l} {s[l]}→{new[l]}" for l in ("1", "10", "80", "100")))
data = q.build_node(T); back = q.parse_node(data)
assert back == T and set(back) == set(BASE)
assert sorted(k for k in BASE if BASE[k] != back[k]) == ["169980", "169995", "179981"]
members = {member(LP): data}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(LP): LP}, "applies_on": "1.4.163", "version": "1.4.164", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print("\n".join(LOG))

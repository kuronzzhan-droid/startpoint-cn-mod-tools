# -*- coding: utf-8 -*-
"""五重决战 全部 boss 血量 -50%：boss_battle_quest 文件夹 1/99 每个 quest 的 c99（boss HP 修正）×0.5。叠加在 1.4.162 上。"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "162")
from live149 import *  # noqa
from stage_all import csv_text as _csv
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.162-1.4.163-1-five-boss-hp-half-local.zip"
LP = "master/quest/boss_battle_quest.orderedmap"
NL = chr(10)
T = load(LP); BASE = copy.deepcopy(T); LOG = []
def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)
fo = T["1"]["99"]; n = 0
for k, v in fo.items():
    rs = [r for r in rows(v) if r]; assert len(rs) == 1
    r = rs[0]; assert r[0].startswith("1099"), r[0]
    old = r[99]; new = f"{float(old) / 2:.15g}"
    r[99] = new; fo[k] = leaf(v, rs); n += 1
    LOG.append(f"{r[0]} {r[2]}: c99 {old} → {new}")
data = q.build_node(T); back = q.parse_node(data)
assert back == T
for f in T["1"]:
    if f != "99": assert back["1"][f] == BASE["1"][f]
for k in fo:
    a, b = rows(BASE["1"]["99"][k])[0], rows(back["1"]["99"][k])[0]
    assert [i for i in range(max(len(a), len(b))) if a[i] != b[i]] == [99], k
members = {member(LP): data}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(LP): LP}, "applies_on": "1.4.162", "version": "1.4.163", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(n); print(NL.join(LOG))

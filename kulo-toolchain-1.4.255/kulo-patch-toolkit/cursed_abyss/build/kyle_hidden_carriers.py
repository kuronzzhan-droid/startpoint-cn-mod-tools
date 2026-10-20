# -*- coding: utf-8 -*-
"""凯尔载体固有状态改 string_id 为 hidden_*（v23 状态栏不画）。叠加在 1.4.178 上。"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "179")
from live149 import *  # noqa
from stage_all import csv_text as _csv
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.178-1.4.179-1-kyle-hidden-carriers-local.zip"
LP = "master/character/unique_condition.orderedmap"
NL = chr(10)
REN = {"13999010": ("unique_kyle_moon_charge_cap", "hidden_kyle_moon_charge_cap"),
       "13999011": ("unique_kyle_moon_direct_base", "hidden_kyle_moon_direct_base"),
       "13999012": ("unique_kyle_moon_direct_combo", "hidden_kyle_moon_direct_combo")}
T = load(LP); BASE = copy.deepcopy(T); LOG = []
for k, (old, new) in REN.items():
    r = rows(T[k])[0]; assert r[0] == old, r[0]
    assert not any(rows(v)[0][0] == new for v in T.values())
    r[0] = new; s = _csv([r]); T[k] = s if T[k].endswith(NL) else s.rstrip(NL)
    LOG.append(f"unique {k} string_id {old} → {new}")
data = q.build_node(T); back = q.parse_node(data)
assert back == T and set(back) == set(BASE)
assert sorted(k for k in BASE if back[k] != BASE[k]) == sorted(REN)
for k in REN:
    a, b = rows(BASE[k])[0], rows(back[k])[0]; assert a[1:] == b[1:]
members = {member(LP): data}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(LP): LP}, "applies_on": "1.4.178", "version": "1.4.179",
         "requires_client": "v23 (hidden-unique-icons-v1) to hide; older clients just keep showing the icons", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))

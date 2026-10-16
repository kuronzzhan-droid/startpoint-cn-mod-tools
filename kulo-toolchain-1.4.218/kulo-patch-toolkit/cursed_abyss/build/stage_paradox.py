# -*- coding: utf-8 -*-
"""PARADOX 第二轮增量包：在 kulo 1.4.151 视图上按 wf_paradox_weapon_r2 输出，只收变化的表/DSL；服务端变化才写 ../server3/。
用法：python patch_paradox.py && WF_TIP=151 python stage_paradox.py"""
import hashlib, json, os, shutil, sys, zipfile
os.environ.setdefault("WF_TIP", "151")
from live149 import *
import wf_paradox_weapon_r2 as P
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text, detect_style, dump_like
W = P.W
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.151-1.4.152-1-paradox-r2-local.zip"
raw, _ = read_raw(P.MATERIAL_ATLAS_MAP)
o = P.build(reader(W), allow_existing=True, client_capabilities=P.PATCHED_CLIENT_CAPABILITIES,
            atlas_names=P.atlas_names_from_raw(raw))
assert o["problems"] == [], o["problems"][:10]
files, changed = {}, {}
for lp, keys in o["flat"].items():
    live = flat(lp)
    ch = {k: v for k, v in keys.items() if live.get(k) != v}
    if not ch:
        continue
    node = load(lp)
    before = dict(node)
    for k, v in ch.items():
        node[k] = csv_text(v)
    data = q.build_node(node)
    back = q.parse_node(data)
    assert back == node and all(back[k] == v for k, v in before.items() if k not in ch)
    files[lp] = data
    changed[lp] = sorted(ch)
for lp, keys in o["nested"].items():
    assert all(nested(lp).get(k) == v for k, v in keys.items()), lp
for prog, tree in o["dsl"].items():
    try:
        same = dsl_tree(prog) == tree
    except Exception:
        same = False
    if not same:
        files[wf_dsl.dsl_logical(prog)] = encode_tree(tree)
        changed[wf_dsl.dsl_logical(prog)] = ["(dsl)"]
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
    for n in sorted(members):
        z.writestr(n, members[n])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {n: hashlib.sha256(members[n]).hexdigest() for n in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.151", "version": "1.4.152"}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
# 服务端
s3 = OUT / "server3"
if s3.exists():
    shutil.rmtree(s3)
srv = []
for name, delta in o["server"].items():
    live = server(name)
    if isinstance(delta, list):
        miss = [x for x in delta if x not in live]
        if miss: srv.append((name, miss))
    else:
        for k, v in delta.items():
            lv = live.get(k)
            if isinstance(lv, dict) and isinstance(v, dict):
                lv = {kk: vv for kk, vv in lv.items() if kk != "enhancementPurchaseMode"}
            if lv != v: srv.append((name, k))
print(json.dumps({"zip": {k: integ[k] for k in ("name", "size", "sha256", "members")}, "changed": changed,
                  "server_diffs": srv}, ensure_ascii=False, indent=1))

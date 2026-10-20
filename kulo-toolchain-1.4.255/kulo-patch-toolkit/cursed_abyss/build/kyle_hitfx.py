# -*- coding: utf-8 -*-
"""凯尔 139990：月牙追击 DSL 的 CreateCondition 施加特效 GenericConditionHitEffect → None（段数/伤害/叠层不变）。叠加在 1.4.164 上。"""
import copy, hashlib, json, os, zipfile, zlib
os.environ.setdefault("WF_TIP", "165")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from dsltools import commands
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_cursed_weapons as W
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.164-1.4.165-1-kyle-hitfx-local.zip"
p = "battle/action/skill/action/ability_skill/ability_skill_kyle_moon_pierce$ability_skill_kyle_moon_pierce"
t0 = dsl_tree(p); t = copy.deepcopy(t0); n = 0
for pp, c in commands(t, "CreateCondition"):
    assert c[2][0][0] == "ACAdditionalDirectAttack" and c[4] == ["GenericConditionHitEffect"], c
    c[4] = ["None"]; n += 1
assert n == 1
a0 = [c for _, c in commands(t0, "CreateCondition")][0]; a1 = [c for _, c in commands(t, "CreateCondition")][0]
assert [i for i in range(len(a0)) if a0[i] != a1[i]] == [4]
files = {wf_dsl.dsl_logical(p): encode_tree(t)}
back = wf_dsl.parse_dsl(zlib.decompress(files[wf_dsl.dsl_logical(p)], -15))["tree"]
assert back == t, "roundtrip"
probs = W.dsl_signature_problems(back); assert not probs, probs
LOG = ["ability_skill_kyle_moon_pierce：CreateCondition(ACAdditionalDirectAttack) 施加特效 GenericConditionHitEffect → None；段数 vlv/伤害 3.0/持续/上限 99 不变"]
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in files}, "applies_on": "1.4.164", "version": "1.4.165", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))

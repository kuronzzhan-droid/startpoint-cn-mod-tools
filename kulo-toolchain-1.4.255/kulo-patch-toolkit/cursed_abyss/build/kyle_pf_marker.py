# -*- coding: utf-8 -*-
"""凯尔特殊 PF 追加判定区命中特效 None → hitfx-silence-v1 静默标记（attack_to_hostile_hit, randomRotation=false）。叠加在 1.4.167 上。
补丁客户端：该标记命中不弹伤害数字/特效/音效/闪烁；未打补丁客户端：显示普通直击火花（轻量）。伤害/次数不变。"""
import copy, hashlib, json, os, zipfile, zlib
os.environ.setdefault("WF_TIP", "168")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from dsltools import commands
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_cursed_weapons as W
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.167-1.4.168-1-kyle-pf-silent-marker-local.zip"
MARK = ["SpecifyHitEffectDirectly", ["SpecifyEffectDirectly", "battle/common/layer0/attack_to_hostile_hit"], False]
files, LOG = {}, []
for n in (1, 2, 3):
    p = f"battle/action/power_flip/action/override/kyle_moon_thunder_ring$kyle_moon_thunder_ring_lv{n}"
    t0 = dsl_tree(p); t = copy.deepcopy(t0); k = 0
    for pp, c in commands(t, "CreateNormalAttack"):
        if c[1] == 10:
            assert c[15] == ["None"], c[15]; c[15] = copy.deepcopy(MARK); k += 1
        else:
            assert c[1] == 7 and c[15] == ["Fine"]
    assert k == 1
    d = encode_tree(t); back = wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"]; assert back == t
    pr = W.dsl_signature_problems(back); assert not pr, pr
    files[wf_dsl.dsl_logical(p)] = d
    LOG.append(f"PF lv{n} 追加判定区 CNA(10) 命中特效 None → SpecifyHitEffectDirectly(attack_to_hostile_hit, false)")
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.167", "version": "1.4.168", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))

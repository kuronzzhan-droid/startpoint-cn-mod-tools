# -*- coding: utf-8 -*-
"""1008 平衡 b 版（作者「改动按表为准」），叠加在 1.4.159 上：
杰拉德 PF Lv3 全队直击 6→4 段；稻穗月满丰穰所有版本 攻/能/直击 +50%；白「假日」层数 5→3（1499903 #0/#1 触发次数）。
用法：WF_TIP=159 python balance_1008b.py
"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "159")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
from dsltools import commands
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.159-1.4.160-1-balance-1008b-local.zip"
AB_LP, CAS_LP = "master/ability/ability.orderedmap", "master/string/custom_ability_string.orderedmap"
NL = chr(10)
LOG, files = [], {}
T = {lp: load(lp) for lp in (AB_LP, CAS_LP)}
BASE = copy.deepcopy(T)

def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)

def override(key, old, new):
    s = rows(T[CAS_LP][key])[0][0]
    assert old in s, (key, old)
    T[CAS_LP][key] = leaf(T[CAS_LP][key], [[s.replace(old, new)]])

# 1) 杰拉德 PF Lv3 段数 6 → 4
p = "battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv3"
t = copy.deepcopy(dsl_tree(p)); n = 0
for pp, c in commands(t, "CreateCondition"):
    for a in c[2]:
        if a[0] == "ACAdditionalDirectAttack":
            assert a[2] == [{"min": 6, "max": 6}] and a[3] == [{"min": 0.0, "max": 0.0}], a
            a[2] = [{"min": 4, "max": 4}]; n += 1
assert n == 2
files[wf_dsl.dsl_logical(p)] = encode_tree(t); LOG.append("杰拉德 PF Lv3：全队直击段数 6 → 4（×2 分支）")
override("override_string_white_wolf_gerald", "队伍全体的直接攻击变为6次（60秒）", "队伍全体的直接攻击变为4次（60秒）")
# 2) 稻穗 月满丰穰 全版本 +50%
for i in (1, 2):
    p = f"battle/action/skill/action/rare5/cnmod_inaho_midautumn$cnmod_inaho_midautumn_{i}"
    t = copy.deepcopy(dsl_tree(p)); n = 0
    for pp, c in commands(t, "CreateCondition"):
        if any(b[0] == "ACRegeneration" for b in c[2]):
            for a in c[2]:
                if a[0] in ("ACAttackPoint", "ACAbilityDamage", "ACDirectDamage"):
                    if a[2][0]["max"] != 0.5:
                        a[2] = [{"min": 0.5, "max": 0.5}]; n += 1
    assert n == 3, (p, n)   # 只剩强化版 3 项未是 0.5
    files[wf_dsl.dsl_logical(p)] = encode_tree(t)
    s = json.dumps(t)
    assert "0.625" not in s and "0.6875" not in s
LOG.append("稻穗 月满丰穰 强化版 攻 62.5%/能 68.75%/直击 100% → 均 +50%（两个技能文件）")
# 4) 白 假日 最多 3 层
rs = [r for r in rows(T[AB_LP]["1499903"]) if r]
for i in (0, 1):
    assert rs[i][34] == "5"; rs[i][34] = "3"
T[AB_LP]["1499903"] = leaf(T[AB_LP]["1499903"], rs)
LOG.append("白 1499903 #0/#1（假日每 2 秒 攻/能 +50%）触发次数 5 → 3")
override("desc_override_white_tiger_summer_3", "风属性角色攻击力＋50%、能力伤害＋50%（最多5层）", "风属性角色攻击力＋50%、能力伤害＋50%（最多3层）")
probs = []
for i, r in enumerate(rs):
    probs += [f"1499903#{i}: {x}" for x in L.client_legality_problems("ability", r)]
for lp in T:
    data = q.build_node(T[lp]); back = q.parse_node(data)
    assert back == T[lp] and set(back) == set(BASE[lp])
    assert [k for k in BASE[lp] if back[k] != BASE[lp][k]], lp
    files[lp] = data
for lp, d in files.items():
    if lp.endswith(".deflate"):
        import zlib
        probs += W.dsl_signature_problems(wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"])
assert not probs, probs
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.159", "version": "1.4.160", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print("\n".join(LOG))

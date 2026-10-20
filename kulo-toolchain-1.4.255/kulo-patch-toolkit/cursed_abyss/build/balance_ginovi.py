# -*- coding: utf-8 -*-
"""基诺维平衡（作者「改动按表为准」），叠加在 1.4.159 上：
杰拉德 PF Lv3 全队直击 6→4 段；稻穗月满丰穰所有版本 攻/能/直击 +50%；白「假日」层数 5→3（1499903 #0/#1 触发次数）。
用法：WF_TIP=159 python balance_1008b.py
"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "160")
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
NAME = "pinball-1.4.160-1.4.161-1-balance-ginovi-local.zip"
AB_LP, CAS_LP = "master/ability/ability.orderedmap", "master/string/custom_ability_string.orderedmap"
LD_LP, ST_LP = "master/ability/leader_ability.orderedmap", "master/character/character_status.orderedmap"
NL = chr(10)
LOG, files = [], {}
T = {lp: load(lp) for lp in (AB_LP, CAS_LP, LD_LP, ST_LP)}
BASE = copy.deepcopy(T)

def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)

def override(key, old, new):
    s = rows(T[CAS_LP][key])[0][0]
    assert old in s, (key, old)
    T[CAS_LP][key] = leaf(T[CAS_LP][key], [[s.replace(old, new)]])


def setrows(lp, key, rs):
    old = [r for r in rows(T[lp][key]) if r]
    if rs[0][1:3] != old[0][1:3]:
        raise AssertionError((key, "c1/c2", rs[0][1:3], old[0][1:3]))
    T[lp][key] = leaf(T[lp][key], rs)

CHECK = []
# 0) 基础攻击力：表内 1268 → 1000，全等级按 1000/1268 等比（lv100 845 → 666.4，取 667）
st = dict(T[ST_LP]["169999"]); assert st["100"] == "2970,845", st
k = 667 / 845; new = {}
for lv, v in st.items():
    hp, atk = v.split(","); new[lv] = f"{hp},{int(round(int(atk) * k))}"
T[ST_LP]["169999"] = new
assert new["100"] == "2970,667"
LOG.append("基础攻击力 lv1/10/80/100 = 13/128/768/845 → " + "/".join(new[l].split(",")[1] for l in ("1", "10", "80", "100")) + "（×1000/1268 等比，HP 不动）")
# 1) 技能倍率 8×12 → 4×12（ginovi_1 / ginovi_2）
for i in (1, 2):
    p = f"battle/action/skill/action/rare5/ginovi$ginovi_{i}"
    t = copy.deepcopy(dsl_tree(p)); n = 0
    for pp, c in commands(t, "CreateHitArea"):
        assert c[15] == ["Some", [{"min": 12, "max": 12}]], c[15]
    for pp, c in commands(t, "CreateNormalAttack"):
        assert c[6] == [{"min": 8.0, "max": 8.0}], c[6]
        c[6] = [{"min": 4.0, "max": 4.0}]; n += 1
    assert n == 1, n
    files[wf_dsl.dsl_logical(p)] = encode_tree(t)
LOG.append("技能『掠影协奏』/『掠影协奏＋』命中倍率 8.0×12 段 = 96 → 4.0×12 = 48")
# 2) 队长：死印每层 +5% → +1%（限 10 层，最高 10%）
rs = [r for r in rows(T[LD_LP]["169999"]) if r]
r = rs[10]; assert r[107] == "158" and r[100] == "10" and r[102] == "1699901" and r[111] == r[112] == "5000", r
r[111] = r[112] = "1000"
for i in (6, 7, 8): assert rs[i][32] == "3" and rs[i][49] == "25000", (i, rs[i][32], rs[i][49])  # 1.4.154 贯穿上限保持
setrows(LD_LP, "169999", rs); CHECK.append(("leader_ability", "169999", rs))
override("desc_override_ginovi", "每持有1层「死印」＋5%（状态特攻乘区，最多10层）", "每持有1层「死印」＋1%（状态特攻乘区，最多10层）")
LOG.append("队长 L10（死印层数 → 全队触发敌方特攻）5% → 1%/层，最多 10 层 = 最高 10%；L6-8 贯穿 25%×3 次保持")
# 3) 能力2：死印固有特攻 200% → 5%
rs = [r for r in rows(T[AB_LP]["1699992"]) if r]
assert rs[1][47] == "518" and rs[1][51] == rs[1][52] == "200000"; rs[1][51] = rs[1][52] = "5000"
setrows(AB_LP, "1699992", rs); CHECK.append(("ability", "1699992", rs))
override("desc_override_ginovi_2", "造成的所有伤害＋200%（状态特攻乘区）", "造成的所有伤害＋5%（状态特攻乘区）")
LOG.append("能力2 对死印敌人所有伤害 200% → 5%")
# 4) 能力3：删除连击35 攻/技/能 +50%×8
rs = [r for r in rows(T[AB_LP]["1699993"]) if r]
assert [x[47] for x in rs[:3]] == ["32", "34", "388"] and all(x[27] == "12" and x[30] == "3500000" and x[34] == "8" for x in rs[:3])
rs = rs[3:]; setrows(AB_LP, "1699993", rs); CHECK.append(("ability", "1699993", rs))
override("desc_override_ginovi_3", " <icon id='main'>  每当连击达到35，暗属性角色攻击力＋50%、技能伤害＋50%、能力伤害＋50%（最多8层）" + NL, "")
LOG.append("能力3 删除 #0-#2（连击35 攻/技伤/能伤 +50% 最多8层），其余 4 条保留")
# 5) 能力5：死印技伤独立乘区 50% → 5%，新增 暗共鸣 暗属性技能伤害 +25%
rs = [r for r in rows(T[AB_LP]["1699995"]) if r]; assert len(rs) == 1
assert rs[0][47] == "721" and rs[0][51] == rs[0][52] == "50000"; rs[0][51] = rs[0][52] = "5000"
nr = list(rs[0]); nr[47] = "34"; nr[51] = nr[52] = "25000"; nr[68] = ""; rs.append(nr)
setrows(AB_LP, "1699995", rs); CHECK.append(("ability", "1699995", rs))
override("desc_override_ginovi_5", "技能伤害＋50%（独立乘区）", "技能伤害＋5%（独立乘区）、暗属性角色技能伤害＋25%")
LOG.append("能力5 死印技伤独立乘区 50% → 5%；新增 #1 暗共鸣时 暗属性角色技能伤害 +25%（kind34）")
# 6) 能力6：技能伤害 100% → 25%
rs = [r for r in rows(T[AB_LP]["1699996"]) if r]
assert rs[0][47] == "34" and rs[0][51] == rs[0][52] == "100000"; rs[0][51] = rs[0][52] = "25000"
setrows(AB_LP, "1699996", rs); CHECK.append(("ability", "1699996", rs))
override("desc_override_ginovi_6", "技能伤害＋100%", "技能伤害＋25%")
LOG.append("能力6 暗属性角色技能伤害 100% → 25%")
probs = []
for tb, key, rs in CHECK:
    for i, r in enumerate(rs):
        probs += [f"{key}#{i}: {x}" for x in L.client_legality_problems(tb, r)]
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
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.160", "version": "1.4.161", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print("\n".join(LOG))

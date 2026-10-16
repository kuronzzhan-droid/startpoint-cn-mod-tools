# -*- coding: utf-8 -*-
"""芙拉菲 149987 能力6 追加：风共鸣开局给自身 999 层 13999010（v23+：充能速度上限 999%）；发动技能时自身充能速度 +10%（限 99 次）。叠加在 1.4.181 上。"""
import copy, hashlib, json, os, zipfile, zlib
os.environ.setdefault("WF_TIP", "182")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.181-1.4.182-1-balance-rabbit-local.zip"
AB_LP, CAS_LP = "master/ability/ability.orderedmap", "master/string/custom_ability_string.orderedmap"
P = "battle/action/skill/action/ability_skill/ability_skill_combat_animal_moon_charge_cap$ability_skill_combat_animal_moon_charge_cap"
NL = chr(10)
T = {lp: load(lp) for lp in (AB_LP, CAS_LP)}; BASE = copy.deepcopy(T); files, LOG = {}, []
def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)
tree = ["ActionDsl", 2, ["None"], False, False, False, False, False, False, False, 0, ["Block", [
    ["Command", ["CreateCondition", -17, [["ACUnique", 13999010, [{"min": 999, "max": 999}]]], [{"min": 1, "max": 1}], ["None"],
                 False, False, "combat_animal_moon_charge_cap", None, False, 3, [{"min": 1, "max": 1}], True]]]]]
assert not W.dsl_signature_problems(tree)
d = encode_tree(tree); assert wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"] == tree
files[wf_dsl.dsl_logical(P)] = d
rs = [r for r in rows(T[AB_LP]["1499876"]) if r]; assert len(rs) == 1 and rs[0][47] == "35"
base = rs[0]
a = list(base)
a[27], a[28], a[30], a[31], a[35] = "0", "0", "100000", "100000", "36"
a[47], a[48], a[49], a[51], a[52] = "629", "", "", "", ""
a[70], a[71] = "ability_skill_combat_animal_moon_charge_cap", P
tpl = [r for r in rows(T[AB_LP]["1499872"]) if r][2]; assert tpl[27] == "23" and tpl[47] == "34" and tpl[34] == "5"
b = list(tpl)
b[0] = base[0]
b[34], b[47], b[48], b[49], b[51], b[52] = "99", "35", "0", "", "10000", "10000"
rs += [a, b]
T[AB_LP]["1499876"] = leaf(T[AB_LP]["1499876"], rs)
LOG.append("能力6 1499876 新增 #1：风共鸣 开局(CT36帧) → 629 ability_skill_combat_animal_moon_charge_cap（自身 13999010×999 层 ⇒ v23 充能速度上限 999%）")
LOG.append("能力6 1499876 新增 #2：风共鸣 自身技能发动≥1（限 99 次）→ 自身 技能充能速度(35) +10%")
assert "ability_skill_combat_animal_moon_charge_cap" not in T[CAS_LP] and "desc_override_combat_animal_moon_6" not in T[CAS_LP]
T[CAS_LP]["ability_skill_combat_animal_moon_charge_cap"] = "风属性共鸣时，战斗开始时自身技能充能速度的上限提升至999%" + NL
text = "风属性共鸣时，风属性角色技能充能速度＋10%" + NL + "风属性共鸣时，自身技能充能速度上限提升至999%；自身发动技能时，自身技能充能速度+10%"
T[CAS_LP]["desc_override_combat_animal_moon_6"] = _csv([[text]])
assert rows(T[CAS_LP]["desc_override_combat_animal_moon_6"])[0][0] == text
LOG.append("新增面板 desc_override_combat_animal_moon_6（原自动行 + 新句）与 CAS 说明")
probs = [f"1499876#{i}: {x}" for i, r in enumerate(rs) for x in L.client_legality_problems("ability", r)]
assert not probs, probs
for lp in T:
    data = q.build_node(T[lp]); back = q.parse_node(data); assert back == T[lp] and set(BASE[lp]) <= set(back)
    assert all(back[k] == v for k, v in BASE[lp].items() if k != "1499876")
    files[lp] = data
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.181", "version": "1.4.182",
         "requires_client": "v23+ (charge-cap formula stacks/100; hidden_ carrier icon)", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))

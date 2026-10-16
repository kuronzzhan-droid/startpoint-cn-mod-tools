# -*- coding: utf-8 -*-
"""1.4.210 → 1.4.211：炎龙王超限（觉醒）三处调整（作者 1015）：
① 队长技给的「勇敢之焰」一次 6 层、上限 12 层；② 觉醒特殊强化弹射说明只写「赋予特殊强化弹射」；
③ 觉醒特殊强化弹射（722，仅队长位）伤害整体转为技能伤害：判定区 buffTargetAs=101（客户端分类转换补丁，v28 起）。


官方固有 19（勇敢之焰，上限 3）未觉醒也在用，不能改；新建固有 1111830（同名同图标，上限 12），
只把觉醒行（leader 111183 第 9/10/11 行：给层 461 / 629 门控 / 525 消耗）改指新固有，给层 300%→600%。
用法：python overlimit120_brave211.py [--write]
"""
import copy, glob, hashlib, json, os, sys, zipfile
from pathlib import Path

OUT = Path(r"D:/WF/out/角色超限-120")
EXTRA = [r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/patch/pinball-1.4.205-1.4.206-1-rolf-moon-skill-rework-local.zip",
         str(OUT / "patch/pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip"),
         str(OUT / "patch/pinball-1.4.207-1.4.208-1-overlimit120-rose-dragon-local.zip")] \
    + sorted(glob.glob(r"D:/WF/out/赛瑞斯重做-20261015/patch/pinball-1.4.208-1.4.209-*-seris-rework-local.zip")) \
    + [str(OUT / "patch/pinball-1.4.209-1.4.210-1-overlimit-crystal-icon-fix-local.zip")]
os.environ["WF_TIP"] = "205"
os.environ["WF_EXTRA_ZIPS"] = ";".join(EXTRA)
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from live149 import *  # noqa
import wf_mod_tool as M  # noqa
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L  # noqa
import wf_describe as D  # noqa

NAME = "pinball-1.4.210-1.4.211-1-wagner-overlimit-tweak-local.zip"
NL = chr(10)
UC_LP, LE_LP = "master/character/unique_condition.orderedmap", "master/ability/leader_ability.orderedmap"
OLD_UC, NEW_UC, CID = "19", "1111830", "111183"
STACK_GIVE, STACK_CAP = 6, 12

uc = load(UC_LP)
assert NEW_UC not in uc
r19 = row(uc[OLD_UC])
assert r19[0] == "unique_fire_dragon_zenith" and r19[1] == "勇敢之焰" and r19[4] == "3", r19
rn = list(r19)
rn[0], rn[4] = "unique_fire_dragon_zenith_ol", str(STACK_CAP)
uc_edit = {NEW_UC: join(rn) + (NL if uc[OLD_UC].endswith(NL) else "")}

le = load(LE_LP)
rs = [r for r in rows(le[CID]) if r]
assert len(rs) == 13, len(rs)
give, gate_629, consume = rs[9], rs[10], rs[11]
assert (give[1], give[2], give[45], give[49], give[50], give[66]) == ("1", "1", "461", "300000", "300000", OLD_UC), give
assert (gate_629[2], gate_629[45], gate_629[11], gate_629[17]) == ("1", "629", "188", OLD_UC), gate_629
assert (consume[2], consume[45], consume[17], consume[66]) == ("1", "525", OLD_UC, OLD_UC), consume
rs2 = copy.deepcopy(rs)
rs2[9][49] = rs2[9][50] = str(STACK_GIVE * 100000)
rs2[9][66] = NEW_UC
rs2[10][17] = NEW_UC
rs2[11][17] = rs2[11][66] = NEW_UC
assert rs2[:9] == rs[:9] and rs2[12] == rs[12]
le_edit = {CID: join_rows(rs2) + (NL if le[CID].endswith(NL) else "")}
probs = [p for r in rs2 for p in L.client_legality_problems("leader_ability", r)]
assert not probs, probs
LOG = ["unique_condition 新增 %s：%s" % (NEW_UC, rn)] + \
      ["leader %s#%d %s" % (CID, i, D.describe_line(rs2[i], "leader_ability")) for i in (9, 10, 11)]


def raw_replace(lp, edits):
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        if k in keys0:
            om.rows[om.keys.index(k)] = q.build_node(node)
        else:
            om.keys.append(k)
            om.rows.append(q.build_node(node))
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys[:len(keys0)] == keys0
    changed = [keys0[i] for i in range(len(rows0)) if back.rows[i] != rows0[i]]
    assert sorted(changed + back.keys[len(keys0):]) == sorted(edits), (lp, changed)
    parsed = q.parse_node(out)
    for k, node in edits.items():
        assert parsed[k] == node, (lp, k)
    return out


# ② 说明文字
CAS_LP, PF_KEY = "master/string/custom_ability_string.orderedmap", "override_string_fire_dragon_zenith_overlimit_pf"
cas = load(CAS_LP)
assert cas[PF_KEY].startswith("觉醒后的射击强化弹射"), cas[PF_KEY]
cas_edit = {PF_KEY: "赋予特殊强化弹射" + (NL if cas[PF_KEY].endswith(NL) else "")}
# ③ PF → 技能伤害
import wf_dsl, zlib  # noqa
from wf_character_revision import encode_tree  # noqa
TO_SKILL = 101
dsl_files = {}
for lv in (1, 2, 3):
    p = f"battle/action/power_flip/action/override/fire_dragon_zenith_overlimit_pf$fire_dragon_zenith_overlimit_pf_lv{lv}"
    t = dsl_tree(p)
    n = 0

    def walk(x):
        global n
        if isinstance(x, list):
            if len(x) == 2 and x[0] == "Command" and x[1][0] == "CreateHitArea":
                assert x[1][24] == 0, x[1][24]
                x[1][24] = TO_SKILL
                n += 1
            for y in x:
                walk(y)
    walk(t)
    assert n == lv, (lv, n)
    enc = encode_tree(t)
    assert wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == t
    dsl_files[wf_dsl.dsl_logical(p)] = enc
LOG.append("PF 说明改「赋予特殊强化弹射」；fire_dragon_zenith_overlimit_pf lv1-3 判定区 buffTargetAs 0→101（转技能伤害）")
files = {UC_LP: raw_replace(UC_LP, uc_edit), LE_LP: raw_replace(LE_LP, le_edit), CAS_LP: raw_replace(CAS_LP, cas_edit),
         **dsl_files}
print(NL.join(LOG))
if "--write" in sys.argv:
    path = OUT / "patch" / NAME
    assert not path.exists()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for lp in sorted(files):
            zf.writestr(member(lp) if not lp.startswith('production/') else lp, files[lp])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(files),
             "applies_on": "1.4.210", "version": "1.4.211", "logical_paths": {member(lp): lp for lp in files},
             "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL,
                                                             "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}))

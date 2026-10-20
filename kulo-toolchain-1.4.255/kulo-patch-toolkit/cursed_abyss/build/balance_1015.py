# -*- coding: utf-8 -*-
"""角色平衡 1015（腾讯表 1.4.200 之后新增 A–E 块），叠加在 kulo 1.4.202 视图上 → 1.4.203。
spec：research/balance_sheet_20261015_new.md。
A 灼原的狮王 119996：技能领域 全属性(254)抗性 -25%/3900帧 → -10%/1800帧；技能文本六处补全属性抗性下降。
B 基诺维 169999：全属性 -40% → -10%（旗号两支），暗 -20% → -15%；文本无数字不改。
C 机车玛格诺斯 119990：能力3 #3 引擎点火≥5层 自身技能伤害额外乘区 25% → 10%；#4 每层火属性角色 1% → 0.5%；CAS 同步。
D 代号·月兔 夏琳 139992：全属性抗性降低 原只在旗号1(能力1/536)分支内 -8%(+alv -3%)=11%；
   改为移出旗号分支成技能本体 -1%，alv(能力1强化) -2% ⇒ 强化后 -3%（4层上限不变）；技能文本六处补本体效果，
   能力1 change_skill 改为「强化…的全属性抗性降低效果」。
E 月下独奏的黑狼 罗尔夫 149986：只核对不改（判定区 buffTargetAs 已=4；真直击标志在引擎写死，见 LOG）。
用法：WF_TIP=202 python balance_1015.py
"""
import copy
import hashlib
import json
import os
import zipfile
import zlib

os.environ.setdefault("WF_TIP", "202")
from live149 import *  # noqa
import wf_dsl
import wf_mod_tool as M
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
from dsltools import commands, get

import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W

assert TIP == 202, TIP
import base149 as _B
assert not os.environ.get("WF_EXTRA_ZIPS")
assert all(z.parent == ACTIVE for z in _B._ZIPS)
assert _B._ZIPS[-1].name == "pinball-1.4.201-1.4.202-1-funnel-variable-lv100-local.zip", _B._ZIPS[-1].name

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.202-1.4.203-1-balance-1015-local.zip"
AS_LP = "master/skill/action_skill.orderedmap"
TX_LP = "master/character/character_text.orderedmap"
CAS_LP = "master/string/custom_ability_string.orderedmap"
AB_LP = "master/ability/ability.orderedmap"
SRV_SRC = OUT / "server23/character_text.json"   # = kulo assets/cdndata 现值（1.4.200 起未再变）
SRV_DST = OUT / "server26/character_text.json"
NL = chr(10)
LOG: list[str] = []
DSL: dict[str, list] = {}
EDIT: dict[str, dict] = {AS_LP: {}, TX_LP: {}, CAS_LP: {}, AB_LP: {}}
TEXTS: dict[str, dict] = {}
probs: list[str] = []

T = {lp: load(lp) for lp in EDIT}
assert hashlib.sha256(SRV_SRC.read_bytes()).hexdigest() == hashlib.sha256((KULO / "assets/cdndata/character_text.json").read_bytes()).hexdigest()
SRV = json.loads(SRV_SRC.read_text("utf-8"))


def V(x):
    return [{"min": x, "max": x}]


def dsl(program):
    if program not in DSL:
        DSL[program] = copy.deepcopy(dsl_tree(program))
    return DSL[program]


def tol(tree, el):
    return [(pp, ac) for pp, c in commands(tree, "CreateCondition") for ac in c[2] if ac[0] == "ACToleranceOfElement" and ac[2] == el]


def in_flag(tree, pp):
    for i in range(len(pp)):
        n = get(tree, pp[:i])
        if isinstance(n, list) and len(n) == 2 and n[0] == "Command" and isinstance(n[1], list) and n[1] and n[1][0] == "ConditionalsChangeSkillFlag":
            return True
    return False


def leaf(v: str, rs):
    s = _csv(rs)
    return s if v.endswith(NL) else s.rstrip(NL)


def raw_replace(lp, edits):
    """外层 raw rows 原样保留，只替换 edits 中的键 chunk（未动键逐字节相同）。"""
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        assert q.build_node(load(lp)[k]) == rows0[keys0.index(k)], (lp, k, "原 chunk 不能逐字节重建")
        om.rows[om.keys.index(k)] = q.build_node(node)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0
    assert [i for i in range(len(rows0)) if back.rows[i] != rows0[i]] == sorted(keys0.index(k) for k in edits)
    return out


def skill_text(cid, code, old_frag, new_frag, base_c1=None):
    """action_skill 两档 c1 + character_text c5/c7 + 服务端 [5]/[7] 六处统一为同一串。"""
    g = copy.deepcopy(T[AS_LP][code]); assert list(g) == ["1", "2"], list(g)
    tx = rows(T[TX_LP][cid])[0]; srv = SRV[cid][0]
    assert srv == tx, (cid, "服务端与客户端 character_text 不一致")
    before = {"action_skill_1": row(g["1"])[1], "action_skill_2": row(g["2"])[1], "character_text_c5": tx[5], "character_text_c7": tx[7]}
    src = base_c1 if base_c1 is not None else row(g["1"])[1]
    assert src.count(old_frag) == 1, (cid, old_frag)
    new = src.replace(old_frag, new_frag)
    for lv in ("1", "2"):
        r = row(g[lv]); r2 = list(r); r2[1] = new
        assert r[7].endswith(f"{code}_{lv}"), r[7]
        g[lv] = join(r2) + (NL if g[lv].endswith(NL) else "")
        assert row(g[lv]) == r2 and [j for j in range(len(r)) if r[j] != r2[j]] == [1]
    EDIT[AS_LP][code] = g
    tx2 = list(tx); tx2[5] = new; tx2[7] = new
    v = T[TX_LP][cid]
    nv = join(tx2) + (NL if v.endswith(NL) else "")
    assert rows(nv)[0] == tx2 and [j for j in range(len(tx)) if tx[j] != tx2[j]] == [j for j in (5, 7) if tx[j] != new]
    EDIT[TX_LP][cid] = nv
    SRV[cid][0] = tx2
    TEXTS[cid] = {"before": before, "after_all_six": new}
    return before, new


def cas_replace(key, pairs):
    v = T[CAS_LP][key]; s = rows(v)[0]; assert len(rows(v)) == 1 and len(s) == 1
    before = s[0]; t = before
    for old, new in pairs:
        assert t.count(old) == 1, (key, old)
        t = t.replace(old, new)
    nv = leaf(v, [[t]])
    assert rows(nv)[0] == [t]
    EDIT[CAS_LP][key] = nv
    TEXTS[key] = {"before": before, "after": t}


# ============================================================ A) 灼原的狮王 119996
for lv in ("1", "2"):
    t = dsl("battle/action/skill/action/rare5/lion_swordman_reborn$lion_swordman_reborn_" + lv)
    a = tol(t, 254); assert len(a) == 1, a
    pp, ac = a[0]
    assert not in_flag(t, pp)
    assert ac[1] == V(3900) and ac[3] == V(-0.25) and ac[4] == V(1), ac
    ac[1] = V(1800); ac[3] = V(-0.1)
    f = tol(t, 1); assert len(f) == 1 and f[0][1][1] == V(3900) and f[0][1][4] == V(3)
LOG.append("A 灼原的狮王 119996 lion_swordman_reborn_1/_2：领域命中 全属性(254)抗性 -25%/3900帧(65秒) → -10%/1800帧(30秒)（技能本体，非旗号分支）；"
           "同块 火属性 -5%/-6%×3层、烈狱等固有 3900 帧不动")
OLD_A = "并赋予累积火属性抗性降低及“烈狱”效果"
NEW_A = "并赋予累积火属性抗性降低、全属性抗性下降及“烈狱”效果"
b, n = skill_text("119996", "lion_swordman_reborn", OLD_A, NEW_A)
assert b["action_skill_1"] == b["action_skill_2"] and b["character_text_c5"] == b["character_text_c7"]
assert b["action_skill_1"] == "点燃自身的“永恒之火”，" + b["character_text_c5"]
LOG.append(f"A 技能文本六处统一为「{n}」（原 character_text/cdndata 缺「点燃自身的“永恒之火”，」前缀，与详情页 action_skill 不一致，顺带对齐）")

# ============================================================ B) 基诺维 169999
for i in (1, 2):
    t = dsl(f"battle/action/skill/action/rare5/ginovi$ginovi_{i}")
    a = tol(t, 254); d = tol(t, 6)
    assert len(a) == 2 and len(d) == 1, (a, d)
    for pp, ac in a:
        assert ac[1] == V(750) and ac[3] == V(-0.4) and ac[4] == V(1), ac
        ac[3] = V(-0.1)
    pp, ac = d[0]
    assert ac[1] == V(750) and ac[3] == V(-0.2) and ac[4] == V(1), ac
    ac[3] = V(-0.15)
LOG.append("B 基诺维 169999 ginovi_1/_2：全场敌人 全属性(254)抗性 -40% → -10%（旗号 on/off 两支同改）；命中 暗属性(6)抗性 -20% → -15%；750 帧不变；文本不含数字不改")

# ============================================================ C) 机车玛格诺斯 119990 能力3
rs = [r for r in rows(T[AB_LP]["1199903"]) if r]
assert len(rs) == 6 and leaf(T[AB_LP]["1199903"], rs) == T[AB_LP]["1199903"]
r = rs[3]
assert (r[97], r[100], r[102], r[104], r[109], r[113], r[114]) == ("134", "500000", "1", "11999001", "411", "25000", "25000"), r
r[113] = r[114] = "10000"
r = rs[4]
assert (r[97], r[100], r[102], r[104], r[109], r[110], r[111], r[113], r[114]) == ("134", "100000", "10", "11999001", "411", "5", "Red", "1000", "1000"), r
r[113] = r[114] = "500"
assert rs[1][47] == "629" and rs[1][70] in T[CAS_LP]
EDIT[AB_LP]["1199903"] = leaf(T[AB_LP]["1199903"], rs)
LOG.append("C 机车玛格诺斯 119990 能力3(1199903) #3 during134 引擎点火(11999001)≥5层 自身 kind411 技能伤害额外乘区 25000 → 10000（25% → 10%）；"
           "#4 每层(最多10层) 火属性角色 kind411 1000 → 500（1% → 0.5%）")
cas_replace("desc_override_lion_swordman_moon_3", [("自身引擎点火在5层以上时：自身技能伤害额外乘区＋25%", "自身引擎点火在5层以上时：自身技能伤害额外乘区＋10%"),
                                                    ("火属性角色技能伤害额外乘区＋1%（最多10层）", "火属性角色技能伤害额外乘区＋0.5%（最多10层）")])

# ============================================================ D) 代号·月兔 夏琳 139992 artificialeye_sniper_moon
for lv in ("1", "2"):
    t = dsl(f"battle/action/skill/action/rare5/artificialeye_sniper_moon$artificialeye_sniper_moon_{lv}")
    a = tol(t, 254); assert len(a) == 1, a
    pp, ac = a[0]
    assert ac[1] == V(1800) and ac[3] == [{"min": -0.06, "max": -0.08, "alv_min": -0.02, "alv_max": -0.03}] and ac[4] == V(4), ac
    # pp = (..., 23, 1, k, 1, 2, 1, 0)：onHit 块第 k 条 = ConditionalsChangeSkillFlag(1)，其 then 块第 0 条 = 本 CreateCondition
    blk_path, k = pp[:-5], pp[-5]
    blk = get(t, blk_path)
    flag = blk[k][1]
    assert flag[0] == "ConditionalsChangeSkillFlag" and flag[1] == 1 and flag[3] == ["Block", []], flag[:2]
    assert pp[-4:] == (1, 2, 1, 0) and get(t, pp)[1][0] == "CreateCondition" and pp[-7:-5] == (23, 1)
    cc_node = flag[2][1].pop(0)
    assert cc_node[1][2][0] is ac and cc_node[1][-1] is True   # forceApply 保留
    ac[3] = [{"min": -0.01, "max": -0.01, "alv_min": -0.02, "alv_max": -0.02}]
    blk.insert(k, cc_node)
    na = tol(t, 254); assert len(na) == 1 and not in_flag(t, na[0][0]) and na[0][0][:-1] == blk_path, na
    assert [n[1][0] for n in blk][k:k + 2] == ["CreateCondition", "ConditionalsChangeSkillFlag"]
    rest = [c[2][0][0] for p2, c in commands(flag[2], "CreateCondition")]
    assert rest[0] == "ACAttackPoint", rest
LOG.append("D 夏琳 139992 artificialeye_sniper_moon_1/_2：全属性(254)抗性降低 CreateCondition 从 ConditionalsChangeSkillFlag(1) then 支移到同一 onHit 块、紧挨旗号节点之前（技能本体）；"
           "数值 {技能等级 -6%→-8%, ALv -2%→-3%} → {-1%, ALv -2%}（拉平）：无能力1 = -1%、能力1(536 旗号1)生效 = -1%-2% = -3%；"
           "1800 帧、4 层上限、forceApply=true 不变；攻击力降低与随机麻痹/中毒/冻结仍在旗号分支内")
OLD_D = "瞄准敌人射出月华贯穿弹，命中后爆炸"
NEW_D = "瞄准敌人射出月华贯穿弹，无视弱体抗性赋予命中的敌人累积全属性抗性降低效果（最多4层），命中后爆炸"
skill_text("139992", "artificialeye_sniper_moon", OLD_D, NEW_D)
cas_replace("change_skill_artificialeye_sniper_moon",
            [("强化『桂影·望月三千』：命中敌人时赋予其累积全属性抗性降低与累积攻击力降低效果（无视弱体抗性），并随机追加赋予麻痹、中毒、冻结中的两种效果",
              "强化『桂影·望月三千』的全属性抗性降低效果；为『桂影·望月三千』追加：命中敌人时赋予其累积攻击力降低效果（无视弱体抗性），并随机赋予麻痹、中毒、冻结中的两种效果")])
LOG.append("D 能力1(1399921 #1 536) 文案 change_skill_artificialeye_sniper_moon：全属性抗性降低由「追加」改为「强化」，攻击力降低/随机异常仍为追加；定性无数字")

# ============================================================ E) 月下独奏的黑狼 罗尔夫 149986（核对，不改）
for p in ("battle/action/skill/action/rare5/black_wolf_knight_moon$black_wolf_knight_moon_1",
          "battle/action/skill/action/rare5/black_wolf_knight_moon$black_wolf_knight_moon_2",
          "battle/action/skill/action/ability_skill/ability_skill_wolf_moon_encore$ability_skill_wolf_moon_encore"):
    t = dsl_tree(p)
    has = [c[24] for pp, c in commands(t, "CreateHitArea")]
    assert has == [4, 4], (p, has)
    assert len(list(commands(t, "CreateNormalAttack"))) >= 2 and t[10] == 0
LOG.append("E 罗尔夫 149986：技能两档与能力3 #4 的 629 ability_skill_wolf_moon_encore 全部 CreateHitArea 的 buffTargetAs(params[23]) 已=4"
           "（官方「伤害量以直接攻击伤害判定」写法，直击通用乘区生效、技能通用乘区不生效）。剩余「技能」属性来自引擎写死："
           "ActionEvaluator 造伤 createdByDirectAttack 恒 false、createdByMainSkillAction 按动作种类恒 true ⇒ 伤害飘字/伤害计数/统计=技能、"
           "吃技能独立乘区与敌方技能耐性、吃不到直击独立乘区(410/693)。数据层无开关，本包不改；要真直击须客户端补丁")

# ============================================================ 检查 + 编码
files: dict[str, bytes] = {}
for p, tree in DSL.items():
    probs += [f"{p}: {x}" for x in W.dsl_signature_problems(tree)]
    enc = encode_tree(tree)
    assert wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == tree, p
    files[wf_dsl.dsl_logical(p)] = enc
for lp, ed in EDIT.items():
    if ed:
        files[lp] = raw_replace(lp, ed)
        back = q.parse_node(files[lp])
        assert set(back) == set(T[lp]) and sorted(k for k in T[lp] if back[k] != T[lp][k]) == sorted(ed), lp
        LOG.append(f"{lp}：改动键 {sorted(ed)}；其余 {len(T[lp]) - len(ed)} 键 chunk 逐字节保留")
for i, r in enumerate(r for r in rows(EDIT[AB_LP]["1199903"]) if r):
    assert len(r) == 126
    probs += [f"ability 1199903#{i}: {p}" for p in L.client_legality_problems("ability", r)]
    if r[47] == "629":
        assert r[70] in q.parse_node(files[CAS_LP]) or r[70] in T[CAS_LP]
for i, r in enumerate(r for r in rows(T[AB_LP]["1399921"]) if r):
    probs += [f"ability 1399921#{i}: {p}" for p in L.client_legality_problems("ability", r)]
    if r[47] == "536":
        assert r[70] == "change_skill_artificialeye_sniper_moon"
assert not probs, probs

old_txt = SRV_SRC.read_text("utf-8")
new_srv = old_txt
for cid in ("119996", "139992"):
    o = TEXTS[cid]["before"]["character_text_c5"]
    assert o == TEXTS[cid]["before"]["character_text_c7"]
    oj, nj = json.dumps(o, ensure_ascii=False), json.dumps(TEXTS[cid]["after_all_six"], ensure_ascii=False)
    assert new_srv.count(oj) == 2, (cid, new_srv.count(oj))
    new_srv = new_srv.replace(oj, nj)
assert json.loads(new_srv) == SRV
jo = json.loads(old_txt); jn = json.loads(new_srv)
assert set(jo) == set(jn) and sorted(k for k in jo if jo[k] != jn[k]) == ["119996", "139992"]
SRV_DST.parent.mkdir(exist_ok=True)
SRV_DST.write_bytes(new_srv.encode("utf-8"))
LOG.append("服务端 assets/cdndata/character_text.json：119996、139992 的 [5]/[7] 同步（整文件副本 server26/character_text.json，其余键不变）")


def main():
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    assert len(blob) <= 5 * 1024 * 1024
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None
        a = q.parse_node(zf.read(member(AS_LP)))
        tx = q.parse_node(zf.read(member(TX_LP)))
    for cid, code in (("119996", "lion_swordman_reborn"), ("139992", "artificialeye_sniper_moon")):
        six = [row(a[code]["1"])[1], row(a[code]["2"])[1], rows(tx[cid])[0][5], rows(tx[cid])[0][7], jn[cid][0][5], jn[cid][0][7]]
        assert len(set(six)) == 1, (cid, six)
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "new_files": [],
             "server_files": {"assets/cdndata/character_text.json": {"copy": "server26/character_text.json",
                                                                      "sha256": hashlib.sha256(SRV_DST.read_bytes()).hexdigest()}},
             "applies_on": "1.4.202", "version": "1.4.203", "requires_client": "纯数据", "texts": TEXTS,
             "checks": {"dsl_signature_problems": 0, "ability_legality_problems": 0}, "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print(json.dumps(integ["logical_paths"], ensure_ascii=False, indent=1))
    print(json.dumps(TEXTS, ensure_ascii=False, indent=1))
    print("\n".join(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

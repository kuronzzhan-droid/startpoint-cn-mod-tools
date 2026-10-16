# -*- coding: utf-8 -*-
"""1.4.200 → 1.4.201：
A) 基诺维 169999 技能详情页文案：action_skill ginovi 1/2 c1 补「赋予命中的敌人暗属性抗性降低效果」，与 character_text c5/c7、
   服务端 cdndata/character_text.json [5]/[7] 六处一致（1.4.200 漏了 action_skill，详情页读的是它）。
   DSL 判定：暗抗降 CreateCondition 挂在根块顶层 CreateHitArea（不在 ConditionalsChangeSkillFlag 内）= 技能本体效果，
   故强化条目 change_skill_ginovi / desc_override_ginovi_1 不写（wf-skill-enhance-text-rule）。
B) C8601：executable_instant_item_level 补 wf_dummy_skill_charge_half（复制 skill_charge_middle 行），
   采用 D:/WF/bughunt-20261014/out 候选成员，并在本视图下按同法重建、逐字节比对。
用法：WF_TIP=200 python build_201.py
"""
import copy
import hashlib
import json
import os
import zipfile
import zlib

os.environ.setdefault("WF_TIP", "200")
from live149 import *  # noqa
import wf_dsl
import wf_mod_tool as M
import wf_client_legality as L
from dsltools import commands, get

import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_cursed_weapons as W

assert TIP == 200, TIP
import base149 as _B
assert not os.environ.get("WF_EXTRA_ZIPS")
assert _B._ZIPS[-1].name == "pinball-1.4.199-1.4.200-1-balance-ginovi2-local.zip", _B._ZIPS[-1].name

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.200-1.4.201-1-ginovi-text-c8601-local.zip"
AS_LP = "master/skill/action_skill.orderedmap"
TX_LP = "master/character/character_text.orderedmap"
CAS_LP = "master/string/custom_ability_string.orderedmap"
AB_LP = "master/ability/ability.orderedmap"
LV_LP = "master/battle/item/executable_instant_item_level.orderedmap"
EII_LP = "master/battle/item/executable_instant_item.orderedmap"
DII_LP = "master/battle/yakumono/direct_instant_item.orderedmap"
SRV = OUT / "server23/character_text.json"           # 1.4.200 服务端整文件副本（= kulo assets/cdndata 现值）
CAND = Path(r"D:/WF/bughunt-20261014/out/pinball-1.4.200-1.4.201-1-c8601-item-level-fix-candidate.zip")
DARK = "赋予命中的敌人暗属性抗性降低效果"
LOG: list[str] = []
files: dict[str, bytes] = {}
probs: list[str] = []


def raw_replace(lp, edits):
    """外层 raw rows 原样保留，只替换 edits 中的键 chunk（未动键逐字节相同）。"""
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        om.rows[om.keys.index(k)] = q.build_node(node)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0
    assert [i for i in range(len(rows0)) if back.rows[i] != rows0[i]] == sorted(keys0.index(k) for k in edits)
    return out


# ============================================================ A-1) DSL 分支判定（证据）
for lv in ("1", "2"):
    p = f"battle/action/skill/action/rare5/ginovi$ginovi_{lv}"
    t = dsl_tree(p)
    root = t[11][1]
    flag_idx = [i for i, n in enumerate(root) if n[0] == "Command" and n[1][0] == "ConditionalsChangeSkillFlag"]
    assert len(flag_idx) == 1
    dark = [(pp, c) for pp, c in commands(t, "CreateCondition")
            if c[2] and c[2][0][0] == "ACToleranceOfElement" and c[2][0][2] == 6]
    assert len(dark) == 1, dark
    pp, c = dark[0]
    # (11,1,8,...) ：根块第 8 条 = CreateHitArea，非 ConditionalsChangeSkillFlag（第 flag_idx 条）
    assert pp[:3] == (11, 1, 8) and root[8][1][0] == "CreateHitArea" and flag_idx == [5], (pp, flag_idx)
    assert c[2][0][3] == [{"min": -0.2, "max": -0.2}] and c[2][0][1] == [{"min": 750, "max": 750}]
    allel = [pp for pp, c in commands(t, "CreateCondition") if c[2] and c[2][0][0] == "ACToleranceOfElement" and c[2][0][2] == 254]
    assert sorted(x[:5] for x in allel) == [(11, 1, 5, 1, 2), (11, 1, 5, 1, 3)], allel   # 旗号两支各一份 = 两支都有 = 本体
    probs += [f"{p}: {x}" for x in W.dsl_signature_problems(t)]
LOG.append("DSL 判定：ginovi_1/_2 暗属性(6)抗性 -20% 的 CreateCondition 位于根块第 8 条 CreateHitArea 的命中块内（路径 (11,1,8,…)），"
           "不在第 5 条 ConditionalsChangeSkillFlag 内 ⇒ 强化/非强化都生效 = 技能本体效果；全属性(254) -40% 在旗号 on/off 两支各一份，同为本体")

# ============================================================ A-2) action_skill c1
OLD_C1 = "对全场敌人附加全属性抗性下降效果；吞噬"
NEW_C1 = f"对全场敌人附加全属性抗性下降效果；{DARK}；吞噬"
AS = load(AS_LP)
BASE_AS = copy.deepcopy(AS)
TX = load(TX_LP)
tx = rows(TX["169999"])[0]
srv = json.loads(SRV.read_text("utf-8"))["169999"][0]
assert srv == tx, "server23 与客户端 character_text 不一致"
before_c1 = {}
g = copy.deepcopy(AS["ginovi"])
assert list(g) == ["1", "2"]
for lv, name, txc in (("1", "掠影协奏", 5), ("2", "掠影协奏＋", 7)):
    r = row(g[lv])
    assert r[0] == name and r[7] == f"battle/action/skill/action/rare5/ginovi$ginovi_{lv}"
    assert r[1].count(OLD_C1) == 1 and DARK not in r[1], r[1]
    before_c1[lv] = r[1]
    new = g[lv].replace(OLD_C1, NEW_C1)
    assert g[lv].count(OLD_C1) == 1
    r2 = row(new)
    assert len(r2) == len(r) and [j for j in range(len(r)) if r[j] != r2[j]] == [1]
    assert r2[1] == tx[txc] == srv[txc], (r2[1], tx[txc])
    g[lv] = new
files[AS_LP] = raw_replace(AS_LP, {"ginovi": g})
back = q.parse_node(files[AS_LP])
assert [k for k in BASE_AS if back[k] != BASE_AS[k]] == ["ginovi"] and set(back) == set(BASE_AS)
LOG.append(f"{AS_LP} ginovi 1/2 c1：「{OLD_C1}」→「{NEW_C1}」；现与 character_text c5/c7、cdndata [5]/[7] 六处逐字相同；"
           f"其余 {len(BASE_AS) - 1} 键 chunk 逐字节保留")

# ============================================================ A-3) 强化条目核对（不改）
CAS = load(CAS_LP)
for k in ("change_skill_ginovi", "desc_override_ginovi_1"):
    assert "为『掠影协奏』追加" in CAS[k] and "暗属性抗性" not in CAS[k], k
LOG.append("强化条目 change_skill_ginovi / desc_override_ginovi_1 不改：暗抗降是本体效果，按 wf-skill-enhance-text-rule 只写技能描述")
for i, r in enumerate(r for k in ("1699991", "1699992", "1699993", "1699994", "1699995", "1699996") for r in rows(load(AB_LP)[k]) if r):
    probs += [f"ability ginovi #{i}: {p}" for p in L.client_legality_problems("ability", r)]

# ============================================================ B) C8601 道具等级行
lraw, lsrc = read_raw(LV_LP)
assert hashlib.sha256(lraw).hexdigest() == "766ff3592bc66a87fa417dc9be38196abf9cd0a0beaef21bb942cc604201dc85", lsrc
lv0, eii, dii = load(LV_LP), load(EII_LP), load(DII_LP)
assert sorted(set(eii) - set(lv0)) == ["wf_dummy_skill_charge_half"]
om = M.read_orderedmap_raw_rows_from_bytes(lraw, LV_LP)
k0, c0 = list(om.keys), list(om.rows)
om.keys.append("wf_dummy_skill_charge_half")
om.rows.append(c0[k0.index("skill_charge_middle")])
rebuilt = M.build_orderedmap_raw_rows(om)
with zipfile.ZipFile(CAND) as zf:
    assert zf.namelist() == [member(LV_LP)]
    cand = zf.read(member(LV_LP))
assert cand == rebuilt, "候选成员与本视图重建结果不一致"
lv1 = q.parse_node(cand)
assert list(lv1) == k0 + ["wf_dummy_skill_charge_half"] and all(lv1[k] == lv0[k] for k in lv0)
assert lv1["wf_dummy_skill_charge_half"] == lv0["skill_charge_middle"] == "atk_basic_normal,1,1"
st = M.read_orderedmap_raw_rows_from_bytes(cand, LV_LP)
assert st.rows[:len(c0)] == c0
assert not (set(eii) - set(lv1)) and not ({row(v)[1] for v in dii.values()} - {""} - set(lv1))
files[LV_LP] = cand
LOG.append(f"{LV_LP}：末尾追加 wf_dummy_skill_charge_half = \"atk_basic_normal,1,1\"（复制 skill_charge_middle 的压缩 chunk）；"
           f"原 {len(c0)} 行 chunk 与键序逐字节不变；成员与 bughunt 候选逐字节相同；eii 全键/dii 引用道具均有等级行（修 C8601）")
LOG.append("根修：build/dummy_variants.py 新增道具时同步写 executable_instant_item_level 行（从 ITEM_TEMPLATE=skill_charge_middle 复制），"
           "并断言 eii 每键、dii 每个引用道具都有等级行；WF_TIP=179 干跑：原 1.4.180 成员逐字节不变，仅多出该等级表成员")

assert not probs, probs


def main():
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    assert len(blob) <= 5 * 1024 * 1024
    # ---- 成品自测（从 zip 读回）
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None
        a = q.parse_node(zf.read(member(AS_LP)))["ginovi"]
        lv = q.parse_node(zf.read(member(LV_LP)))
    for lvk, c in (("1", 5), ("2", 7)):
        assert DARK in row(a[lvk])[1] and row(a[lvk])[1] == tx[c] == srv[c]
    assert DARK in tx[5] and DARK in tx[7]
    assert all("暗属性抗性" not in CAS[k] for k in ("change_skill_ginovi", "desc_override_ginovi_1"))
    assert lv["wf_dummy_skill_charge_half"] == "atk_basic_normal,1,1"
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "new_files": [],
             "server_files": {}, "applies_on": "1.4.200", "version": "1.4.201", "requires_client": "纯数据",
             "texts": {"action_skill_ginovi_c1_before": before_c1,
                       "action_skill_ginovi_c1_after": {k: row(a[k])[1] for k in ("1", "2")},
                       "change_skill_ginovi": CAS["change_skill_ginovi"], "desc_override_ginovi_1": CAS["desc_override_ginovi_1"]},
             "checks": {"dsl_signature_problems": 0, "ability_legality_problems": 0}, "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print(json.dumps(integ["logical_paths"], ensure_ascii=False, indent=1))
    print(json.dumps(integ["member_sha256"], ensure_ascii=False, indent=1))
    print("\n".join(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

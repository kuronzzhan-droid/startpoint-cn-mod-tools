# -*- coding: utf-8 -*-
"""1.4.227：把 6.1 Sol 两轮定稿的面板文案（audit/rewrites/*.json）装进表。
cas：custom_ability_string 单格整段替换（只改已有键）；skill：action_skill 各档 c1 + character_text c5/c7 + 服务端镜像同列。"""
import copy, glob, json, re
from fw import AB, AS, CAS, CH, LE, TX, HERE, join, leaf, row, rows

ICON = " <icon id='main'>  "
BAN = ("额外乘区", "（独立乘区）", "状态特攻乘区", "觉醒后")


def load_rewrites():
    cas, skill = {}, {}
    for f in sorted(glob.glob(str(HERE / "audit" / "rewrites" / "[0-9][0-9].json"))):
        d = json.load(open(f, encoding="utf-8"))
        for k, v in d.get("cas", {}).items():
            assert k not in cas, ("重复键", k); cas[k] = v
        for k, v in d.get("skill", {}).items():
            assert k not in skill, ("重复技能", k); skill[k] = v
    keep = json.load(open(HERE / "audit" / "keep_official.json", encoding="utf-8"))
    for k in keep["cas"]:
        cas.pop(k, None)
    for k, lv in keep["skill"]:
        if k in skill: skill[k].pop(lv, None)
    skill = {k: v for k, v in skill.items() if v}
    # 直接攻击计算为N次但伤害+0%：官方不标乘区
    cas = {k: v.replace("合计伤害不变（独立伤害乘区6）", "合计伤害不变") for k, v in cas.items()}
    # 作者1017：五种类型全发动时写「全部类型」
    cas = {k: re.sub(r"同时发动剑士型、格斗型、射击型、辅助型与特殊型", "同时发动全部类型", v) for k, v in cas.items()}
    return cas, skill


def main_only_sids(F):
    out = set()
    for k, v in F.table(AB).items():
        rs = [r for r in rows(v) if r]
        if rs and len(rs[0]) > 1 and rs[0][1] == "false":
            out.add(rs[0][0])
    return out


def apply(F):
    cas, skill = load_rewrites()
    mains = main_only_sids(F)
    leaders = {[r for r in rows(v) if r][0][0] for v in F.table(LE).values() if [r for r in rows(v) if r]}
    T = F.table(CAS)
    nc = 0
    for k, t in cas.items():
        assert k in T, ("新键需另行支持", k)
        t = t.replace("\r\n", "\n").strip("\n")
        for b in BAN:
            assert b not in t, (k, b)
        if k.startswith("desc_override_") and k[len("desc_override_"):] in leaders:
            assert "自身为队长时" not in t, (k, "队长槽")
        if k.startswith("desc_override_") and k[len("desc_override_"):] in mains:
            for ln in t.split("\n"):
                assert ln.startswith(ICON), ("主位行缺图标", k, ln)
        v = F.string(CAS, k)
        assert len(rows(v)) == 1 and len(rows(v)[0]) == 1, k
        if rows(v)[0][0] == t:
            continue
        nv = leaf(v, [[t]])
        assert rows(nv)[0] == [t]
        F.set_string(CAS, k, nv); nc += 1
    ns = 0
    for code, lvs in skill.items():
        g = copy.deepcopy(F.table(AS)[code])
        for lv, t in lvs.items():
            assert lv in g, (code, lv)
            r = row(g[lv]); r2 = list(r); r2[1] = t
            g[lv] = join(r2) + ("\n" if g[lv].endswith("\n") else "")
        if g != F.table(AS)[code]:
            F.STR[(AS, code)] = json.dumps(g, ensure_ascii=False); ns += 1
        # 抽卡特性页 / 服务端镜像：c5=档1，c7=最高档（两档技能=档2）
        cids = [cid for cid, v in F.table(CH).items() if (row(v)[8] if row(v)[8] not in ("", "(None)") else row(v)[0]) == code]
        for cid in cids:
            pairs = {5: row(g["1"])[1], 7: row(g["2"])[1]} if "2" in g else {5: row(g["1"])[1]}
            if "3" in g: pairs[9] = row(g["3"])[1]
            if cid in F.table(TX):
                v = F.string(TX, cid); tx = rows(v)[0]
                for c, t in pairs.items():
                    if c == 9 and tx[c] in ("", "(None)"): continue
                    tx[c] = t
                F.set_string(TX, cid, join(tx) + ("\n" if v.endswith("\n") else ""))
            if cid in F.SRV:
                for c, t in pairs.items():
                    if c == 9 and F.SRV[cid][0][c] in ("", "(None)", None): continue
                    F.SRV[cid][0][c] = t
    F.log(f"面板文案规范化：custom_ability_string {nc} 键、技能描述 {ns} 个技能")

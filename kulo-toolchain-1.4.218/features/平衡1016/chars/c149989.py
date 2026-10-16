# -*- coding: utf-8 -*-
"""定格星风的剑圣 希尔媞 149989（wind_spgirl_campus）—— 平衡表 1016。"""
import math
import sys
sys.path.insert(0, r"D:/WF/out/平衡1016")
from fw import commands, AS  # noqa: E402

CID, CODE = "149989", "wind_spgirl_campus"
SKILL = "battle/action/skill/action/rare5/wind_spgirl_campus$wind_spgirl_campus_"
OLD_BASE = {3: 26.785714285714285, 6: 48.214285714285715}   # 判定区 subject 3 / 6 两刀，合计 75
OLD_VLV = {3: 3.5714285714285716, 6: 6.428571428571429}     # 每层星风心得，合计 10
NEW_BASE = {3: 2.5, 6: 4.5}                                 # 合计 7（×7/75，两刀比例不变）
NEW_VLV = {3: 2.5, 6: 4.5}                                  # 每层合计 7（×0.7）


def close(a, b):
    return math.isclose(a, b, rel_tol=0, abs_tol=1e-9)


def eq(r, c, v):
    assert r[c] == v, (c, r[c], v)


def apply(F):
    # ---------------- 技能两档 DSL
    for lv in ("1", "2"):
        t = F.dsl(SKILL + lv)
        # 1) 伤害归属 2（只换通用池）→ 102（完整能力伤害，同风巨蜥 149998）
        assert t[10] == 2, t[10]
        t[10] = 102
        ha = list(commands(t, "CreateHitArea"))
        assert len(ha) == 32 and {c[24] for pp, c in ha} == {2}, (lv, len(ha))
        for pp, c in ha:
            c[24] = 102
        # 2) 倍率：基础 75 → 7，每层 10 → 7
        cna = list(commands(t, "CreateNormalAttack"))
        assert len(cna) == 32
        for pp, c in cna:
            s = c[1]
            cell = c[6]
            assert len(cell) == 1 and close(cell[0]["min"], OLD_BASE[s]) and close(cell[0]["max"], OLD_BASE[s]), (lv, cell)
            vl = cell[0]["vlv"]
            assert len(vl) == 1 and vl[0]["vid"] == 14998905 and vl[0]["min"] == 0 and close(vl[0]["max"], OLD_VLV[s]), vl
            cell[0]["min"] = cell[0]["max"] = NEW_BASE[s]
            vl[0]["max"] = NEW_VLV[s]
        # 3) 成长层数上限：队长分支 Bind 上限 2147483647（无上限）→ 7、非队长分支 10 → 7（协调方 1016 追加：两分支一致）
        binds = [c for pp, c in commands(t, "BindConditionAccumulationVariable")]
        assert [b[5] for b in binds] == [2147483647.0, 10, 0, 0], [b[5] for b in binds]
        assert all(b[1:5] == [-17, 14998905, ["DCUnique", 14998902], 1] for b in binds)
        binds[0][5] = 7.0   # 队长分支（Flag2）：无上限 → 7 层
        binds[1][5] = 7     # 非队长分支：10 → 7 层
    F.log("希尔媞 技能『风中快门·十字双空牙』两档：伤害归属 技能伤害（tree[10]/32 个判定区 buffTargetAs=2）→ 能力伤害（102，完整能力伤害结算）")
    F.log("希尔媞 技能两档：基础合计倍率 75倍 → 7倍（两刀 26.79+48.21 → 2.5+4.5）；风共鸣 Fever 中每层「星风心得」额外倍率 +10倍 → +7倍，最多 10层 → 7层")
    F.log("希尔媞 技能两档：自身为队长时的星风心得成长分支 层数上限 无上限 → 最多7层（与非队长分支一致）")
    F.cas_replace("change_skill_wind_spgirl_campus_leader", [
        ("技能倍率随「星风心得」层数持续提升", "技能倍率随「星风心得」层数提升（最多7层）")])
    F.skill_text(CID, CODE, [
        ("造成基础合计75倍风属性伤害，伤害量以能力伤害加成判定。", "造成基础合计7倍风属性能力伤害。"),
        ("每层额外增加10倍（最多10层）", "每层额外增加7倍（最多7层）"),
    ])

    # ---------------- 队长技：星风心得 25%×3层 → 20%×7层
    le = F.le(CID)
    for i in (6, 7):
        r = le[i]
        eq(r, 95, "134"); eq(r, 102, "14998902"); eq(r, 100, "3"); eq(r, 111, "25000"); eq(r, 112, "25000")
        r[100] = "7"; r[111] = r[112] = "20000"
    eq(le[6], 107, "154")
    F.log("希尔媞 队长技：Fever 中每层「星风心得」风属性角色能力伤害 +25% → +20%、攻击力 +25% → +20%，最多计入 3层 → 7层")
    F.cas_replace("desc_override_wind_spgirl_campus", [
        ("能力伤害+25%、攻击力+25%（最多计3层）", "能力伤害+20%、攻击力+20%（最多计7层）"),
        ("技能倍率随「星风心得」层数持续提升。", "技能倍率随「星风心得」层数提升（最多7层）。")])

    # ---------------- 能力3
    ab = F.ab("1499893")
    r = ab[2]  # 连击每 7 → 攻击力
    eq(r, 27, "12"); eq(r, 30, "700000"); eq(r, 31, "700000"); eq(r, 34, "10"); eq(r, 47, "32"); eq(r, 51, "70000"); eq(r, 52, "70000")
    r[30] = r[31] = "7700000"; r[34] = "7"; r[51] = r[52] = "100000"
    r = ab[3]  # 连击每 7 → 技能槽
    eq(r, 27, "12"); eq(r, 30, "700000"); eq(r, 31, "700000"); eq(r, 35, "42"); eq(r, 47, "211"); eq(r, 51, "700"); eq(r, 52, "700")
    r[30] = r[31] = "7700000"; r[35] = "420"; r[51] = r[52] = "7000"
    F.log("希尔媞 能力3：风共鸣 Fever 中连击每达到 7的倍数 → 77的倍数；风属性角色攻击力 +70%（限10次，最大+700%）→ +100%（限7次，最大+700%）；技能槽 +0.7%（CT 0.7秒）→ +7%（CT 7秒）")
    for i, (o, n) in ((6, ("8000", "14000")), (7, ("5000", "7000"))):
        r = ab[i]
        eq(r, 97, "134"); eq(r, 104, "14998902"); eq(r, 102, "10"); eq(r, 113, o); eq(r, 114, o)
        r[102] = "7"; r[113] = r[114] = n
    eq(ab[6], 109, "154"); eq(ab[7], 109, "0")
    F.log("希尔媞 能力3：Fever 中每层「星风心得」风属性角色能力伤害 +8% → +14%、攻击力 +5% → +7%，最多 10层 → 7层")
    F.cas_replace("desc_override_wind_spgirl_campus_3", [
        ("连击每达到7的倍数，风属性角色攻击力+70%（最大+700%）、技能槽+0.7%（回槽冷却时间：0.7秒）",
         "连击每达到77的倍数，风属性角色攻击力+100%（最大+700%）、技能槽+7%（回槽冷却时间：7秒）"),
        ("能力伤害+8%、攻击力+5%（最多10层）", "能力伤害+14%、攻击力+7%（最多7层）"),
    ])

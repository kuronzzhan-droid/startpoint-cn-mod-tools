# -*- coding: utf-8 -*-
"""月下博饼的黑豹 黑 139991（outlaw_panther_moon）—— 平衡表（Shazixnar 10-18 02:21）「技能buff可叠加需刀一下，快速出fever是负优化」。
技能（两档）：全部 ACAttackPoint/ACDirectDamage 数值 ×0.25；给队长的技能槽 30%/15% → 5%；每段伤害 2.7倍 → 1.2倍（按比例 ×4/9）。
能力3：每500次直击Fever+35% → 每750次；进入Fever直击+40%（3次）→+50%（6次）；Fever中每20次直击Fever-50% → 每50次 -20%；
骰运 每1000次直击 → 每750次。"""
from decimal import Decimal, ROUND_HALF_UP
from dsltools import commands
from common import *

def q(x, places=3):
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))

def scale(v, f):
    out = []
    for d in v:
        nd = dict(d); nd["min"] = q(d["min"] * f); nd["max"] = q(d["max"] * f); out.append(nd)
    return out

def apply(F):
    for lv in ("1", "2"):
        t = F.dsl(f"battle/action/skill/action/rare5/outlaw_panther_moon$outlaw_panther_moon_{lv}")
        nb = 0
        for pp, c in commands(t, "CreateCondition"):
            k = c[2][0]
            if k[0] in ("ACAttackPoint", "ACDirectDamage"):
                k[2] = scale(k[2], 0.25); nb += 1
        assert nb == 25, (lv, nb)
        na = 0
        for pp, c in commands(t, "AddSkillPoint"):
            assert c[2][0]["min"] in (0.3, 0.15), c
            c[2] = [{"min": 0.05, "max": 0.05}]; na += 1
        assert na == 12, na
        cn = [c for pp, c in commands(t, "CreateNormalAttack")]
        assert len(cn) == 2
        for c in cn:
            c[6] = scale(c[6], 1.2 / 2.7)
    F.log("黑 技能『博饼·满堂彩』：抽到的攻击力提升、直接攻击伤害提升数值 ×0.25；队长技能槽增加 30%/15% → 5%；"
          "每段伤害倍率 ×1.2/2.7（满级每段 2.7 → 1.2）")
    ab3 = F.ab("1399913")
    r = ab3[0]; assert (r[27], r[47]) == ("20", "724"); setv(r, [AB_TRIG_TH1, AB_TRIG_TH2], 50000000, 75000000)
    r = ab3[1]; assert (r[27], r[47], r[34]) == ("8", "33", "3"); setv(r, [AB_IC_S1, AB_IC_S2], 40000, 50000); setv(r, [AB_TRIG_LIMIT], 3, 6)
    r = ab3[2]; assert (r[27], r[47]) == ("20", "724"); setv(r, [AB_TRIG_TH1, AB_TRIG_TH2], 2000000, 5000000); setv(r, [AB_IC_S1, AB_IC_S2], -50000, -20000)
    r = ab3[3]; assert (r[27], r[47]) == ("20", "461"); setv(r, [AB_TRIG_TH1, AB_TRIG_TH2], 100000000, 75000000)
    F.log("黑 能力3（主位）：非Fever中每直接攻击500次Fever槽+35% → 每750次；进入Fever时直接攻击伤害 +40%（最多3次）→ +50%（最多6次）；"
          "Fever中每直接攻击20次 Fever槽-50% → 每50次 -20%；每直接攻击1000次获得1层「骰运」→ 每750次")
    F.cas_replace("desc_override_outlaw_panther_moon_3", [
        ("合计每直接攻击500次，Fever槽+35%", "合计每直接攻击750次，Fever槽+35%"),
        ("直接攻击伤害+40%（最多3次）", "直接攻击伤害+50%（最多6次）"),
        ("合计每直接攻击20次，Fever槽-50%", "合计每直接攻击50次，Fever槽-20%"),
        ("合计每直接攻击1000次，自身获得1层「骰运」", "合计每直接攻击750次，自身获得1层「骰运」")])

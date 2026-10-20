# -*- coding: utf-8 -*-
"""平衡 1016：原野的风灾 风巨蜥 149998（land_dragon_wind_playable）。说明见 c149998.md。"""
from decimal import Decimal, ROUND_HALF_UP
from dsltools import commands

CID, CODE = "149998", "land_dragon_wind_playable"
P = ["battle/action/skill/action/rare5/land_dragon_wind_playable$land_dragon_wind_playable_" + lv for lv in ("1", "2")]
FACTOR = "0.9"
OLD = {(22.5, 30.0), (2.8125, 3.75), (2.25, 3.0)}


def _dec(x):
    d = Decimal(repr(x))
    return max(0, -d.as_tuple().exponent)


def scale_mult(v, factor):
    """[{min,max,...}] 每项乘 factor；精度=该格内原值的最大小数位，四舍五入（半进位）；全整数格保持 int。"""
    out = []
    for d in v:
        keys = [k for k in d if isinstance(d[k], (int, float)) and not isinstance(d[k], bool)]
        places = max(_dec(d[k]) for k in keys)
        allint = all(isinstance(d[k], int) for k in keys)
        nd = dict(d)
        for k in keys:
            q = (Decimal(repr(d[k])) * Decimal(factor)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
            nd[k] = int(q) if (allint and places == 0) else float(q)
        out.append(nd)
    return out


def scale_tree(F, program, factor, expect):
    """把树里全部 CreateNormalAttack 的倍率格 c[6] 乘 factor；expect = 旧倍率(min,max) 的集合，锁现状。"""
    t = F.dsl(program)
    names = {c[0] for pp, c in commands(t) if "Attack" in c[0]}
    assert names == {"CreateNormalAttack"}, (program, names)
    seen = {}
    for pp, c in commands(t, "CreateNormalAttack"):
        old = c[6]
        assert len(old) == 1 and set(old[0]) == {"min", "max"}, old
        key = (old[0]["min"], old[0]["max"])
        assert key in expect, (program, key)
        c[6] = scale_mult(old, factor)
        seen[key] = (c[6][0]["min"], c[6][0]["max"])
    assert set(seen) == set(expect), (program, seen)
    return seen


def fmt(m):
    return "；".join(f"{a[0]}/{a[1]}→{b[0]}/{b[1]}" for a, b in sorted(m.items()))


def apply(F):
    # ---------------- 所有技能倍率 ×0.9（两档技能全部 25 个判定区；伤害类型 102 不动）
    for p in P:
        assert F.dsl(p)[10] == 102
        m = scale_tree(F, p, FACTOR, OLD)
        assert sum(1 for _ in commands(F.dsl(p), "CreateNormalAttack")) == 25
        F.log(f"风巨蜥 技能『荒岚·群龙天袭』{p[-1]}档 全部25段倍率×0.9（SLv1/满级）：{fmt(m)}")

    # ---------------- 能力2 #2：每25连击技能槽+5% CT 3秒→6秒
    r = F.ab(CID + "2")[2]
    assert (r[27], r[30], r[35], r[47], r[51]) == ("12", "2500000", "180", "211", "5000"), r
    r[35] = "360"
    F.log("风巨蜥 能力2 风属性共鸣时每达成25连击 自身技能槽+5% 冷却 180→360 帧（3秒→6秒）")
    F.cas_replace("desc_override_land_dragon_wind_playable_2", [("自身技能槽+5%（CT：3秒）", "自身技能槽+5%（CT：6秒）")])

    # ---------------- 能力3：Fever 中 自身技能充能速度+50% 删除（保留 Fever 中风属性角色能力伤害+150%）
    a3 = F.ab(CID + "3")
    assert len(a3) == 5
    r = a3[1]
    assert (r[97], r[109], r[110], r[111], r[113], r[114]) == ("4", "154", "5", "Green", "75000", "150000"), r
    r = a3[2]
    assert (r[97], r[109], r[110], r[113], r[114]) == ("4", "3", "0", "25000", "50000"), r
    del a3[2]
    F.log("风巨蜥 能力3 删除「风属性共鸣时 Fever模式中 自身技能充能速度+25%→+50%」，保留「Fever模式中 风属性角色能力伤害+75%→+150%」")

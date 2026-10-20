# -*- coding: utf-8 -*-
"""平衡 1016：月下独奏的黑狼 罗尔夫 149986（black_wolf_knight_moon）。说明见 c149986.md。"""
from decimal import Decimal, ROUND_HALF_UP
from dsltools import commands

CID, CODE = "149986", "black_wolf_knight_moon"
P1 = "battle/action/skill/action/rare5/black_wolf_knight_moon$black_wolf_knight_moon_1"
P2 = "battle/action/skill/action/rare5/black_wolf_knight_moon$black_wolf_knight_moon_2"
PE = "battle/action/skill/action/ability_skill/ability_skill_wolf_moon_encore$ability_skill_wolf_moon_encore"
FACTOR = "0.7"


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


def tot(m, new):
    """六连斩×6 + 重斩×1 + 爆击×10 的 (min,max) 合计。m: 旧→新 映射，按旧值大小区分三段。"""
    ks = sorted(m, key=lambda k: k[1])           # 爆击 < 斩击 < 重斩
    n = {ks[0]: 10, ks[1]: 6, ks[2]: 1}
    pick = (lambda k: m[k]) if new else (lambda k: k)
    return "/".join(str(round(sum(n[k] * pick(k)[j] for k in ks), 4)) for j in (0, 1))


def apply(F):
    # ---------------- 技能倍率 ×0.7（两档技能本体 + 629 安可，安可一直镜像 lv2）
    m1 = scale_tree(F, P1, FACTOR, {(2.8, 2.8), (25.2, 25.2), (1.4, 1.4)})
    m2 = scale_tree(F, P2, FACTOR, {(3.5, 4.0), (31.5, 36), (1.75, 2.0)})
    me = scale_tree(F, PE, FACTOR, {(3.5, 4.0), (31.5, 36), (1.75, 2.0)})
    assert me == m2
    F.log(f"罗尔夫 技能『月下独奏』每段倍率×0.7（SLv1→满级，斩击/重斩/爆击）：lv1 {fmt(m1)}；lv2 {fmt(m2)}"
          f"。全段合计（6斩+重斩+爆击10击）lv1 {tot(m1,0)}→{tot(m1,1)}，lv2 {tot(m2,0)}→{tot(m2,1)}")
    F.log(f"罗尔夫 能力3『每达成100连击发动自身技能攻击效果』(629 安可 ability_skill_wolf_moon_encore) 同步×0.7（与技能lv2同值）：{fmt(me)}")

    # ---------------- 队长技：每100次直击 攻击力/直击伤害（leader #3/#4）+ 额外乘区（能力6 #3，队长门控）
    le = F.le(CID)
    for i, old_v, new_v, nm in ((3, "100000", "40000", "攻击力"), (4, "90000", "30000", "直击伤害")):
        r = le[i]
        assert (r[25], r[28], r[29], r[32], r[49], r[50]) == ("20", "10000000", "10000000", "3", old_v, old_v), r
        r[32] = "6"
        r[49] = r[50] = new_v
        F.log(f"罗尔夫 队长技 风属性角色每造成100次直接攻击 {nm} +{int(old_v)//1000}%→+{int(new_v)//1000}%，次数上限 3→6")
    a6 = F.ab(CID + "6")
    r = a6[3]
    assert (r[27], r[30], r[34], r[47], r[51], r[52]) == ("20", "10000000", "3", "693", "9000", "9000"), r
    r[34] = "6"
    r[51] = r[52] = "1000"
    F.log("罗尔夫 队长技（能力6 #3，队长门控）每100次直接攻击 风属性角色直击伤害额外乘区 +9%→+1%，次数上限 3→6")

    # ---------------- 队长技：最大速度固定持续 每1秒 → 每10秒（能力6 #5/#6，队长门控）
    for i, kind, nm in ((5, "32", "攻击力"), (6, "33", "直击伤害")):
        r = a6[i]
        assert (r[27], r[30], r[32], r[33], r[34], r[35], r[47], r[51], r[52]) == (
            "246", "100000", "6000000", "6000000", "3", "0", kind, "45000", "45000"), r
        r[32] = r[33] = "60000000"     # threshold2 = 持续帧数（resolveInt /100000）：60 → 600 帧
        r[34] = "9"
        r[51] = r[52] = "10000"
        F.log(f"罗尔夫 队长技 最大速度固定持续期间 自身{nm}：每持续1秒+45%（最多3次）→ 每持续10秒+10%（最多9次）")
    F.cas_replace("desc_override_black_wolf_knight_moon", [
        ("风属性角色攻击力＋100%、直击伤害＋90%，直击伤害额外乘区＋9%（最多3次）",
         "风属性角色攻击力＋40%、直击伤害＋30%，直击伤害额外乘区＋1%（最多6次）"),
        ("每持续1秒，自身攻击力＋45%、直击伤害＋45%（最多3次）",
         "每持续10秒，自身攻击力＋10%、直击伤害＋10%（最多9次）"),
    ])

    # ---------------- 能力1：冲刺 / 贯穿
    a1 = F.ab(CID + "1")
    r = a1[0]
    assert (r[27], r[30], r[34], r[47], r[51], r[52]) == ("4", "100000", "4", "33", "50000", "50000"), r
    r[34] = "20"
    r[51] = r[52] = "5000"
    F.log("罗尔夫 能力1 风属性共鸣时冲刺时 自身直击伤害 +50%（最多+200%，4次）→ +5%（最多+100%，20次）")
    r = a1[1]
    assert (r[97], r[109], r[113], r[114]) == ("30", "0", "200000", "200000"), r
    r[113] = r[114] = "100000"
    F.log("罗尔夫 能力1 风属性共鸣时处于贯穿效果时 自身攻击力 +200%→+100%")
    F.cas_replace("desc_override_black_wolf_knight_moon_1", [
        ("自身直接攻击伤害＋50%（最多＋200%）", "自身直接攻击伤害＋5%（最多＋100%）"),
        ("自身攻击力＋200%", "自身攻击力＋100%"),
    ])

    # ---------------- 能力3：直击强化为3次 合计伤害额外乘区
    r = F.ab(CID + "3")[0]
    assert (r[47], r[48], r[49], r[51], r[52]) == ("202", "5", "Green", "200000", "200000"), r
    r[51] = r[52] = "150000"
    F.log("罗尔夫 能力3 风属性角色直接攻击强化为3次 合计伤害额外乘区 +200%→+150%")
    F.cas_replace("desc_override_black_wolf_knight_moon_3", [("合计伤害额外乘区＋200%", "合计伤害额外乘区＋150%")])

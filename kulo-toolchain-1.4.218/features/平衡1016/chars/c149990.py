# -*- coding: utf-8 -*-
"""平衡 1016：盛夏白虎兽人 白 149990（white_tiger_summer）。说明见 c149990.md。"""
from decimal import Decimal, ROUND_HALF_UP
from dsltools import commands
from fw import LE

CID, CODE = "149990", "white_tiger_summer"
P = {lv: "battle/action/skill/action/rare5/white_tiger_summer$white_tiger_summer_" + lv for lv in ("1", "2")}
FACTOR = "0.4"
OLD = {"1": {(2.5, 2.5), (30.0, 30.0), (75.0, 75.0)}, "2": {(3.0, 3.5), (35.0, 40.0), (75.0, 75.0)}}
TEMPLATE_LE = ("151099", 1)   # 官方 airship_captain：光·编成≥6 时 持续·Fever → 赋予全队(光) 攻击力


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


def fever_row(F, kind, value):
    """按官方 151099#1（during Fever → 全队属性角色）克隆一行：kind 0=攻击力 154=能力伤害。"""
    tk, ti = TEMPLATE_LE
    t = list(F.rows(LE, tk)[ti])
    assert (t[0], t[3], t[4], t[7], t[9], t[95], t[106], t[107], t[108], t[109]) == (
        "airship_captain", "1", "2", "600000", "White", "4", "false", "0", "5", "White"), t
    t[0] = CODE
    t[9] = t[109] = "Green"
    t[107] = kind
    t[111] = t[112] = value
    return t


def apply(F):
    # ---------------- 技能：伤害归属 → 102（完整能力伤害，同风巨蜥），倍率 ×0.4
    for lv, p in P.items():
        t = F.dsl(p)
        assert t[10] == 0, t[10]
        has = [c for pp, c in commands(t, "CreateHitArea")]
        assert [c[24] for c in has] == [2, 2, 2], [c[24] for c in has]
        for c in has:
            c[24] = 102
        t[10] = 102
        m = scale_tree(F, p, FACTOR, OLD[lv])
        F.log(f"白 技能『盛夏咆哮』{lv}档：伤害改为完整能力伤害结算（根头 buffTargetAs 0→102，3 个判定区 params[23] 2→102，同风巨蜥）；"
              f"倍率×0.4（SLv1/满级）：{fmt(m)}")
    F.skill_text(CID, CODE, [("技能伤害量以能力伤害加成判定。", "全段伤害均以能力伤害结算。")])

    # ---------------- 队长技：Fever 中常驻 攻击力/能力伤害 +300%；每持续1.5秒 +60%×6 → +6%×40
    le = F.le(CID)
    assert len(le) == 6
    for i, kind in ((3, "32"), (4, "388")):
        r = le[i]
        assert (r[25], r[28], r[29], r[32], r[45], r[47], r[49], r[50]) == (
            "248", "9000000", "9000000", "6", kind, "Green", "60000", "60000"), r
        r[32] = "40"
        r[49] = r[50] = "6000"
    le.insert(3, fever_row(F, "0", "300000"))
    le.insert(4, fever_row(F, "154", "300000"))
    F.log("白 队长技 新增「风属性共鸣时 Fever模式中 风属性角色攻击力+300%、能力伤害+300%」（两行 during Fever，按官方 151099 写法）")
    F.log("白 队长技 Fever模式每持续1.5秒 风属性角色攻击力/能力伤害 +60%（最多6次，合计360%）→ +6%（最多40次）")
    F.cas_replace("desc_override_white_tiger_summer", [(
        "风属性共鸣时，FEVER模式中每持续1.5秒，风属性角色攻击力＋60%、能力伤害＋60%（最大360%）",
        "风属性共鸣时，FEVER模式中，风属性角色攻击力＋300%、能力伤害＋300%，且FEVER模式每持续1.5秒，风属性角色攻击力＋6%、能力伤害＋6%（最多40次）")])

    # ---------------- 能力3：「假日」每持续2秒 +50%×3 → +5%×40
    a3 = F.ab(CID + "3")
    for i, kind in ((0, "32"), (1, "388")):
        r = a3[i]
        assert (r[27], r[30], r[31], r[34], r[47], r[49], r[51], r[52]) == (
            "77", "12000000", "12000000", "3", kind, "Green", "50000", "50000"), r
        r[34] = "40"
        r[51] = r[52] = "5000"
    F.log("白 能力3 「假日」期间每持续2秒 风属性角色攻击力/能力伤害 +50%（最多3层）→ +5%（最多40层）")
    F.cas_replace("desc_override_white_tiger_summer_3", [(
        "每持续2秒，风属性角色攻击力＋50%、能力伤害＋50%（最多3层）",
        "每持续2秒，风属性角色攻击力＋5%、能力伤害＋5%（最多40层）")])

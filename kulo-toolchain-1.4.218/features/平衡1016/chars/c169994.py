# -*- coding: utf-8 -*-
"""平衡 1016：虎魂白帝 白虎 169994（white_tiger_ghost_playable）。说明见 c169994.md。"""
from decimal import Decimal, ROUND_HALF_UP
from dsltools import commands
from fw import AS, row, V

CID, CODE = "169994", "white_tiger_ghost_playable"
P = "battle/action/skill/action/rare5/white_tiger_ghost_playable$white_tiger_ghost_playable"   # 两档技能共用这一棵
FACTOR = "0.6"
OLD = {(1.0, 1.0), (2.2, 2.2), (1.8, 1.8), (2.5, 2.5), (3.5, 3.5), (3.0, 3.0), (5.5, 5.5), (9.0, 9.0)}


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
    g = F.table(AS)[CODE]
    assert [row(g[lv])[7] for lv in ("1", "2")] == [P, P]

    # ---------------- 雷/风属性抗性降低 -30% → -20%（技能首段命中，元素码 3=雷 4=风）
    t = F.dsl(P)
    tol = [ac for pp, c in commands(t, "CreateCondition") for ac in c[2] if ac[0] == "ACToleranceOfElement"]
    assert [(ac[2], ac[1], ac[3], ac[4]) for ac in tol] == [
        (3, V(1200), [{"min": -0.3, "max": -0.3}], [{"min": 0, "max": 0}]),
        (4, V(1200), [{"min": -0.3, "max": -0.3}], [{"min": 0, "max": 0}])], tol
    for ac in tol:
        ac[3] = [{"min": -0.2, "max": -0.2}]
    F.log("白虎 技能『白帝幻界・虎魂刚岚击』雷/风属性抗性降低 -30% → -20%（1200帧不变）")

    # ---------------- 技能倍率 ×0.6（全部 12 段）
    m = scale_tree(F, P, FACTOR, OLD)
    assert sum(1 for _ in commands(t, "CreateNormalAttack")) == 12
    F.log(f"白虎 技能『白帝幻界・虎魂刚岚击』全部12段倍率×0.6：{fmt(m)}")

# -*- coding: utf-8 -*-
"""塞里奥尔 159985 —— 平衡表（罐头）：技能「释放时取消停球」；技能强化给的固定最大速度 2档 → 3档（充能衰减 -0.4 → -0.55，
官方静寂铃鹿 (1,-0.3)/(4,-0.65) 内插 3 档 ≈ -0.53，取 5 的倍数）。"""
from dsltools import commands

def _drop_stopball(node):
    n = 0
    if isinstance(node, list):
        for i in range(len(node) - 1, -1, -1):
            x = node[i]
            if isinstance(x, list) and len(x) == 2 and x[0] == "Command" and isinstance(x[1], list) and x[1][:1] == ["StopBall"]:
                del node[i]; n += 1
            else:
                n += _drop_stopball(x)
    return n

def apply(F):
    for lv in ("1", "2"):
        p = f"battle/action/skill/action/rare5/crystal_swordman_halloween$crystal_swordman_halloween_{lv}"
        t = F.dsl(p)
        assert _drop_stopball(t) == 1, lv
        hits = [c[2][0] for pp, c in commands(t, "CreateCondition") if c[2][0][0] == "ACFixedSpeed"]
        enh = [k for k in hits if k[1][0]["max"] == 1500]
        assert len(enh) == 1 and enh[0][2] == [{"min": 2, "max": 2}] and enh[0][3] == [{"min": -0.4, "max": -0.4}], enh
        enh[0][2] = [{"min": 3, "max": 3}]
        enh[0][3] = [{"min": -0.55, "max": -0.55}]
    F.log("塞里奥尔 技能『伯爵之礼』：释放时不再停球")
    F.log("塞里奥尔 能力3 技能强化：「固定最大速度」2档 → 3档，期间技能充能速度 -40% → -55%")

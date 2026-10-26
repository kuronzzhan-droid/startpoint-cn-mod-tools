# -*- coding: utf-8 -*-
"""平衡 1017 共用小工具。ability 126 列：precondition1@6 / precondition2@13；leader 124 列：precondition1@4 / precondition2@11。"""
EMPTY = ("", "0", "(None)")
AB_P1, AB_P2, LE_P1, LE_P2 = 6, 13, 4, 11
# ability 列（leader = ability - 2）
AB_TRIG_TH1, AB_TRIG_TH2, AB_TRIG_LIMIT, AB_TRIG_CT = 30, 31, 34, 35
AB_IC_KIND, AB_IC_TGT, AB_IC_GRP, AB_IC_S1, AB_IC_S2 = 47, 48, 49, 51, 52
AB_DT_TH1, AB_DT_TH2, AB_DT_LIMIT = 100, 101, 102
AB_DC_KIND, AB_DC_TGT, AB_DC_GRP, AB_DC_S1, AB_DC_S2 = 109, 110, 111, 113, 114


def gate(r, base, group, prec2_base=None):
    """在 precondition1 写「<属性>·编成≥6」（属性共鸣，照抄各角色已有共鸣行：kind 2 + 阈值 600000 + 角色组）。
    precondition1 原有内容先挪到 precondition2（须为空）。"""
    blk = r[base:base + 7]
    stray_ok = [x for i, x in enumerate(blk) if x not in EMPTY and not (i == 5 and x == group)]
    if stray_ok:
        assert prec2_base is not None, blk
        assert all(x in EMPTY for x in r[prec2_base:prec2_base + 7]), r[prec2_base:prec2_base + 7]
        r[prec2_base:prec2_base + 7] = blk
    r[base:base + 7] = [""] * 7
    r[base] = "2"; r[base + 3] = "600000"; r[base + 4] = "600000"; r[base + 5] = group


def setv(r, cols, old, new):
    """cols 里每格必须等于 old，再写成 new（锁旧值）。"""
    for c in cols:
        assert r[c] == str(old), (c, r[c], old)
        r[c] = str(new)


def pct(x):
    """百分数 → 表内单位（1000 = 1%）。"""
    v = round(x * 1000)
    assert abs(v - x * 1000) < 1e-6, x
    return v

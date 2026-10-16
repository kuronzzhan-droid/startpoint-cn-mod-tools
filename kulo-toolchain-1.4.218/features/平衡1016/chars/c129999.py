# -*- coding: utf-8 -*-
"""碧海的龙王 赛瑞斯 129999（seris_dragon_king）—— 平衡表 1016：队长技、能力3 限制 6 水（水属性共鸣）。
前置写法照抄本角色队长 #6（已有的共鸣行）：precondition kind 2 + 阈值 600000（=6人）+ 角色组 Blue。
"""
CID = "129999"
EMPTY = ("", "0", "(None)")


def gate(r, base, prec2_base=None):
    """在 precondition1 写 水·编成≥6；precondition1 原有内容先挪到 precondition2（须为空）。"""
    blk = r[base:base + 7]
    if any(x not in EMPTY for x in blk):
        assert prec2_base is not None
        assert all(x in EMPTY for x in r[prec2_base:prec2_base + 7]), r[prec2_base:prec2_base + 7]
        r[prec2_base:prec2_base + 7] = blk
        r[base:base + 7] = [""] * 7
    r[base] = "2"; r[base + 3] = "600000"; r[base + 4] = "600000"; r[base + 5] = "Blue"


def apply(F):
    # ---------------- 队长技：除 #6（已是共鸣）外 9 行全部加 水·编成≥6
    le = F.le(CID)
    assert len(le) == 10
    ref = le[6]
    assert (ref[4], ref[7], ref[8], ref[9], ref[45]) == ("2", "600000", "600000", "Blue", "536"), ref[:12]
    kinds = []
    for i, r in enumerate(le):
        if i == 6:
            continue
        assert all(x in EMPTY for x in r[4:18]), (i, r[4:18])   # precondition1/2 均空
        kinds.append(r[45] if r[3] != "1" else "d" + r[107])
        gate(r, 4)
    assert kinds == ["461", "50", "d0", "d23", "489", "226", "d419", "d419", "d419"], kinds
    F.log("赛瑞斯 队长技：Fever获得量+100%、Fever中攻击力+350%/强化弹射伤害+450%、Fever开始连击加成保底40、弹射连击+3、"
          "Fever中加速箭头变随机道具、龙人/真龙特殊强化弹射与强化弹射Lv4 —— 全部改为需水属性共鸣（水属性编成≥6）才生效（原无前置）")
    t = F.cas_text("desc_override_seris_dragon_king_leader")
    F.cas_replace("desc_override_seris_dragon_king_leader", [
        ("自身Fever获得量＋100％", "水属性共鸣时，自身Fever获得量＋100％"),
        ("进入FEVER模式时化身「真龙」", "水属性共鸣时，进入FEVER模式时化身「真龙」"),
        ("FEVER模式中，自身攻击力＋350％", "水属性共鸣时，FEVER模式中，自身攻击力＋350％"),
        ("FEVER模式开始时，赋予自身「连击加成」", "水属性共鸣时，FEVER模式开始时，赋予自身「连击加成」"),
        ("弹射时，连击＋3", "水属性共鸣时，弹射时，连击＋3"),
        ("FEVER模式中，场地上的加速箭头", "水属性共鸣时，FEVER模式中，场地上的加速箭头"),
        ("赋予特殊强化弹射效果：", "水属性共鸣时，赋予特殊强化弹射效果："),
        ("解放强化弹射Lv4：", "水属性共鸣时，解放强化弹射Lv4："),
    ])
    assert t.count("\n") == 8

    # ---------------- 能力3：8 行全部加 水·编成≥6（#7 原有 非Fever 前置挪到 precondition2）
    ab = F.ab("1299993")
    assert len(ab) == 8
    for i, r in enumerate(ab):
        if i == 7:
            assert (r[6], r[27], r[47]) == ("186", "77", "724") and all(x in EMPTY for x in r[7:20]), r[:20]
            gate(r, 6, 13)
            assert (r[6], r[13]) == ("2", "186")
        else:
            assert all(x in EMPTY for x in r[6:27]), (i, r[6:27])
            gate(r, 6)
    F.log("赛瑞斯 能力3：「真龙」形态攻击力+300%/强化弹射伤害+300%/独立乘区+15%、化身「真龙」及发动「龙王吐息·苍潮」、"
          "「龙人」形态每15秒Fever槽+15% —— 全部改为需水属性共鸣（水属性编成≥6）才生效（原无前置）")
    F.cas_replace("desc_override_seris_dragon_king_3", [
        ("<icon id='main'>  「真龙」形态中，", "<icon id='main'>  水属性共鸣时，「真龙」形态中，"),
        ("<icon id='main'>  化身「真龙」时，", "<icon id='main'>  水属性共鸣时，化身「真龙」时，"),
        ("<icon id='main'>  「龙人」形态中，", "<icon id='main'>  水属性共鸣时，「龙人」形态中，"),
    ])

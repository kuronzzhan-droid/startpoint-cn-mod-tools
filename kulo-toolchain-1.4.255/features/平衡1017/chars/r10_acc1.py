# -*- coding: utf-8 -*-
"""固有上限 1 陷阱修复：按层数判断（ConditionalsConditionAccumulationNumber / 持续触发 134）只认可叠加状态，
上限为 1 的固有状态层数恒为 0，分支/条目从未生效。DSL 改为 ConditionalsConditionExist(-17, ...)（官方先例，只判有无）；
词条行 134（状态累积计数）改 194（状态计数，只判有无）。水杰拉德 129989 与赛瑞斯真龙判断已由 1.4.244 修，不碰。"""
from dsltools import commands

PROGS = {
    "battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv1": [1499989],
    "battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv2": [1499989],
    "battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv3": [1499989],
    "battle/action/skill/action/rare5/ginovi$ginovi_1": [169998],
    "battle/action/skill/action/rare5/ginovi$ginovi_2": [169998],
    "battle/action/skill/action/rare5/spirit_beast_water_playable$spirit_beast_water_playable_1": [1299510],
    "battle/action/skill/action/rare5/spirit_beast_water_playable$spirit_beast_water_playable_2": [1299510],
    "battle/action/skill/action/rare5/super_robot_tailcoat$super_robot_tailcoat_1": [13999302],
    "battle/action/skill/action/rare5/super_robot_tailcoat$super_robot_tailcoat_2": [13999302],
}

def _fix(node, uids, cnt):
    if isinstance(node, list):
        if len(node) >= 2 and node[0] == "Command" and isinstance(node[1], list) and node[1] and node[1][0] == "ConditionalsConditionAccumulationNumber":
            c = node[1]
            if isinstance(c[1], list) and c[1][0] == "DCUnique" and c[1][1] in uids:
                assert c[2] == 1, c[:3]
                node[1] = ["ConditionalsConditionExist", -17, c[1], c[3], c[4]]
                cnt[0] += 1
        for x in node:
            _fix(x, uids, cnt)

def apply(F):
    F.owner = "r10_acc1"
    for p, uids in PROGS.items():
        t = F.dsl(p); cnt = [0]
        _fix(t, uids, cnt)
        assert cnt[0] >= 1, p
        F.log(f"{p.split('$')[-1]}：{cnt[0]} 处按层数判断上限1固有状态 {uids} → 改为判断是否持有")
    r = F.ab("1599996")[1]
    assert (r[5], r[97], r[104]) == ("1", "134", "1599990"), r[:8]
    r[97] = "194"
    F.log("security_robot_playable 能力6：「交战模式」期间强化弹射伤害+50% 的持续条件由层数计数改为持有判断")
    F.owner = None

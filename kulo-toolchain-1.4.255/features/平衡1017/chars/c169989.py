# -*- coding: utf-8 -*-
"""校园奈芙提姆 169989（ruin_girl_campus）—— 用户 10-17：Fever 中召唤协力球的效果从队长技挪回能力1。
召唤靠「星夜茶会」，星夜茶会只有技能强化旗号（536 change_skill_ruin_girl_campus_fever）分支才给；0927 第一轮把这行从能力1#1 搬进了队长。
这里原样搬回：ability 行 = 能力1 现有行的 c0..c4 + 队长行[3:]（0927 搬家时 leader = [CODE,'0',''] + ab[5:] 的逆操作）。"""
from common import *

def apply(F):
    le = F.le("169989")
    r = le[1]
    assert (r[4], r[9], r[45], r[68]) == ("2", "Black", "536", "change_skill_ruin_girl_campus_fever"), r[:70]
    del le[1]
    ab = F.ab("1699891")
    assert len(ab) == 4 and ab[0][47] == "211" and ab[1][47] == "629"
    pre = ab[1][:5]
    assert pre[0] == "ruin_girl_campus_1" and pre[1] == "false" and (pre[3], pre[4]) == (r[1], r[2])
    nr = list(pre) + list(r[3:])
    assert len(nr) == 126 and nr[47] == "536"
    ab.insert(1, nr)
    F.log("校园奈芙 队长技 → 能力1：技能强化（暗属性共鸣时强化技能，Fever 中发动技能获得「星夜茶会」并召唤协力球）"
          "从队长技挪回能力1（主位即生效，不再要求当队长）")
    F.cas_replace("desc_override_ruin_girl_campus", [
        ("暗属性共鸣时，强化『午后星轨·甜蜜续杯』：额外赋予暗属性角色及协力球攻击力提升效果；Fever 模式中发动时，自身获得或刷新「星夜茶会」，并赋予暗属性角色及协力球护盾。\n", "")])
    F.cas_replace("desc_override_ruin_girl_campus_1", [("每经过1.5秒交替召唤", "每经过2秒交替召唤")])
    F.log("校园奈芙 面板：队长技删去技能强化那一行（能力1面板本来就写着这几条）；能力1召唤间隔文案 1.5秒→2秒，和数据（09-27 起就是 2 秒）对齐")

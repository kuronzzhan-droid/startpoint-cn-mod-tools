# -*- coding: utf-8 -*-
"""1.4.231：作者「按开始的设计写」——瑞西塔尔、tweyen_light 能力4 的「气绝」按官方口径已由麻痹·气绝行(kind 118，乘区2)覆盖，
删掉误做成追击伤害的那一行(kind 53，乘区3)，面板同步删去追击那句。底稿=线上 1.4.230（481b4430）；同时把两处麻痹改成化学家游戏内原文写法。"""
from fw import CAS, rows, leaf


WORD = [("对处于麻痹・气绝状态的敌人造成的伤害", "对麻痹·气绝效果中的敌人造成的伤害"),
        ("对处于「麻痹・气绝」状态的敌人伤害", "对麻痹·气绝效果中的敌人造成的伤害")]   # 线上 230(481b4430) 的旧写法 → 化学家游戏内原文


def apply(F):
    for key, sid in (("1499854", "lich_halloween_4"), ("1599944", "tweyen_light_4")):
        rs = F.ab(key)
        hit = [i for i, r in enumerate(rs) if r[47] == "53"]
        assert len(hit) == 1 and any(r[47] == "118" for r in rs), (key, [r[47] for r in rs])
        del rs[hit[0]]
        ok = "desc_override_" + sid
        v = F.string(CAS, ok); lines = rows(v)[0][0].split("\n")
        keep = [ln for ln in lines if "追击伤害" not in ln]
        for i, ln in enumerate(keep):
            for a, b in WORD: keep[i] = keep[i].replace(a, b)
        assert any("对麻痹·气绝效果中的敌人造成的伤害" in ln for ln in keep), (ok, keep)
        assert len(keep) == len(lines) - 1, (ok, lines)
        F.set_string(CAS, ok, leaf(v, [["\n".join(keep)]]))
        F.log(f"{sid}：删去追击伤害行（kind 53），保留麻痹·气绝行；面板同步")

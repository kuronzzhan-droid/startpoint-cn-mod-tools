# -*- coding: utf-8 -*-
"""覆盖文案补「（独立伤害乘区N）」：N 按客户端说明器（AbilityDescriptionGenerator / InstantAbilityDescriptionGenerator）
对该行内容种类给的标签取，标签串 = ui_string ability_description_separated_term_*（官方原样，乘区9 为全角「９」）。
每条 (old, new, n)：old 必须恰好出现 n 次。"""
from fw import CAS, rows, leaf

Z = {n: f"（独立伤害乘区{n}）" for n in range(1, 9)}
Z[9] = "（独立伤害乘区９）"

EDITS = {
    # ---- 队长技
    "desc_override_ginovi": [("＋1%（状态特攻乘区，最多10层）", f"＋1%{Z[2]}（最多10层）", 1)],
    "desc_override_ghost_girl_playable": [("冻结特攻 30%。", f"冻结特攻 30%{Z[2]}。", 1)],
    "desc_override_security_robot_playable": [("眩晕畏缩特攻 30%、", f"眩晕畏缩特攻 30%{Z[3]}、", 1)],
    "desc_override_killer_whale_playable": [("冻结特攻 30%、", f"冻结特攻 30%{Z[2]}、", 1)],
    "desc_override_genin_playable": [("中毒特攻 30%、", f"中毒特攻 30%{Z[2]}、", 1)],
    "desc_override_fox_oracle_autumn": [("独立乘区的强化弹射伤害提升4.5％", f"强化弹射伤害提升4.5％{Z[5]}", 1)],
    "desc_override_guildknight_leader_tavern": [("强化弹射伤害额外乘区＋0.4%（最多计15层）", f"强化弹射伤害＋0.4%{Z[5]}（最多计15层）", 1)],
    "desc_override_lion_swordman_moon": [("火属性角色技能伤害额外乘区＋3.5%（最多计3层）", f"火属性角色技能伤害＋3.5%{Z[7]}（最多计3层）", 1)],
    "desc_override_combat_animal_moon": [("技能伤害额外乘区＋0.2%（最多50次）", f"技能伤害＋0.2%{Z[7]}（最多50次）", 1)],
    "desc_override_kyle_moon": [("对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋4%", f"对处于“眩晕”、“畏缩”状态的敌人造成的伤害＋4%{Z[3]}", 1)],
    "desc_override_black_wolf_knight_moon": [("直击伤害＋30%，直击伤害额外乘区＋1%（最多6次）", f"直击伤害＋30%、直击伤害＋1%{Z[6]}（最多6次）", 1)],
    # ---- 能力
    "desc_override_seris_dragon_king_3": [("强化弹射伤害＋15％（独立乘区）", f"强化弹射伤害＋15％{Z[5]}", 1)],
    "desc_override_ginovi_2": [("（状态特攻乘区）", Z[2], 1)],
    "desc_override_ginovi_5": [("技能伤害＋5%（独立乘区）", f"技能伤害＋5%{Z[7]}", 1)],
    "desc_override_vaseraga_dark_6": [("逆境效果［最大＋40%］", f"逆境效果［最大＋40%］{Z[4]}", 2),
                                      ("能力伤害＋15%（独立乘区）", f"能力伤害＋15%{Z[8]}", 1)],
    "desc_override_ghost_girl_playable_3": [("（独立乘区）", Z[7], 1)],
    "desc_override_ghost_girl_playable_5": [("冻结敌人的伤害+30%。", f"冻结敌人的伤害+30%{Z[2]}。", 1)],
    "desc_override_cube_boss_playable_3": [("（独立乘区）", Z[5], 1)],
    "desc_override_clione_playable_6": [("（独立乘区）", Z[6], 1)],
    "desc_override_one_eyed_rabbit_playable_3": [("（独立乘区）", Z[6], 1)],
    "desc_override_one_eyed_rabbit_playable_5": [("眩晕敌人的伤害+25%；", f"眩晕敌人的伤害+25%{Z[3]}；", 1)],
    "desc_override_security_robot_playable_1": [("眩晕敌人的伤害+60%。", f"眩晕敌人的伤害+60%{Z[3]}。", 1)],
    "desc_override_security_robot_playable_3": [("（独立乘区）", Z[7], 1)],
    "desc_override_wander_armor_water_playable_6": [("（独立乘区）", Z[8], 1)],
    "desc_override_haniwa_green_playable_3": [("（独立乘区）", Z[7], 1)],
    "desc_override_dog_soldier_playable_3": [("（独立乘区）", Z[5], 1)],
    "desc_override_wander_armor_wind_playable_3": [("（独立乘区）", Z[6], 1)],
    "desc_override_haniwa_blue_playable_6": [("（独立乘区）", Z[6], 1)],
    "desc_override_cobra_playable_6": [("（独立乘区）", Z[7], 1)],
    "desc_override_killer_whale_playable_3": [("（独立乘区）", Z[7], 1)],
    "desc_override_killer_whale_playable_5": [("冻结敌人的伤害+75%；", f"冻结敌人的伤害+75%{Z[2]}；", 1)],
    "desc_override_genin_playable_6": [("（独立乘区）", Z[7], 1)],
    "desc_override_big_bear_monster_playable_5": [("（独立乘区）", Z[6], 1)],
    "desc_override_haniwa_playable_6": [("（独立乘区）", Z[6], 1)],
    "desc_override_fox_oracle_autumn_6": [("独立乘区的强化弹射伤害提升10％", f"强化弹射伤害提升10％{Z[5]}", 1)],
    "desc_override_white_tiger_summer_1": [("能力伤害额外乘区＋5%", f"能力伤害＋5%{Z[8]}", 1)],
    "desc_override_ruin_girl_campus_3": [("（独立乘区）", Z[6], 2)],
    "desc_override_ruin_girl_campus_4": [("（独立乘区）", Z[6], 1)],
    # 同一效果的 629 技能动作说明串（面板被覆盖文案接管，一并改齐）
    "ruin_girl_campus_multiball_direct": [("（独立乘区）", Z[6], 1)],
    "ruin_girl_campus_multiball_direct_a4": [("（独立乘区）", Z[6], 1)],
    "desc_override_scutum_valentine_3": [("（独立乘区）", Z[6], 1)],
    "desc_override_rec_android_seaside_3": [("技能伤害额外乘区＋25%", f"技能伤害＋25%{Z[7]}", 1)],
    "desc_override_guildknight_leader_tavern_1": [("强化弹射伤害额外乘区＋1%（最多10层）", f"强化弹射伤害＋1%{Z[5]}（最多10层）", 1)],
    "desc_override_guildknight_leader_tavern_3": [("强化弹射伤害额外乘区＋15%", f"强化弹射伤害＋15%{Z[5]}", 1)],
    "desc_override_cnmod_inaho_midautumn_2": [("直接攻击伤害额外乘区＋5%、能力伤害额外乘区＋5%", f"直接攻击伤害＋5%{Z[6]}、能力伤害＋5%{Z[8]}", 1)],
    "desc_override_cnmod_inaho_midautumn_4": [("弱化效果中的敌人造成的伤害＋7.5%、", f"弱化效果中的敌人造成的伤害＋7.5%{Z[2]}、", 1)],
    "desc_override_lion_swordman_moon_3": [("自身技能伤害额外乘区＋5%", f"自身技能伤害＋5%{Z[7]}", 1),
                                           ("火属性角色技能伤害额外乘区＋0.33%（最多15层）", f"火属性角色技能伤害＋0.33%{Z[7]}（最多15层）", 1)],
    "desc_override_lion_swordman_moon_5": [("自身独立乘区技能伤害＋10%", f"自身技能伤害＋10%{Z[7]}", 1)],
    "desc_override_psychic_teleport_moon_3": [("强化弹射伤害额外乘区＋1%（最多5层）", f"强化弹射伤害＋1%{Z[5]}（最多5层）", 1)],
    "desc_override_psychic_teleport_moon_5": [("强化弹射伤害额外乘区＋5%", f"强化弹射伤害＋5%{Z[5]}", 1)],
    "desc_override_combat_animal_moon_3": [("技能伤害额外乘区＋5%", f"技能伤害＋5%{Z[7]}", 1)],
    "desc_override_combat_animal_moon_5": [("攻击特攻＋25%", f"攻击特攻＋25%{Z[3]}", 1)],
    "desc_override_still_obstinator_moon_3": [("技能伤害额外乘区＋15%", f"技能伤害＋15%{Z[7]}", 1)],
    "desc_override_sorceress_teacher_moon_3": [("对敌人的技能额外伤害乘区＋2%", f"对敌人的技能伤害＋2%{Z[7]}", 1)],
    "desc_override_black_wolf_knight_moon_3": [("合计伤害额外乘区＋150%", f"合计伤害＋150%{Z[6]}", 1)],
    "desc_override_black_wolf_knight_moon_5": [("直击伤害额外乘区＋50%", f"直击伤害＋50%{Z[6]}", 1)],
    "desc_override_kyle_moon_3": [("合计伤害额外乘区＋150%", f"合计伤害＋150%{Z[6]}", 1)],
    "desc_override_kyle_moon_6": [("造成伤害，额外乘区＋15%", f"造成的伤害＋15%{Z[2]}", 1)],
    "desc_override_tweyen_light_4": [("对处于麻痹、气绝、冻结状态的敌人造成的伤害，额外乘区＋5%",
                                      f"对处于麻痹、冻结状态的敌人造成的伤害＋5%{Z[2]}，对处于气绝状态的敌人造成的伤害＋5%{Z[3]}", 1)],
    "desc_override_lady_android_halloween_3": [("技能伤害额外乘区＋5%", f"技能伤害＋5%{Z[7]}", 1)],
    "desc_override_lady_android_halloween_4": [("伤害＋10%", f"伤害＋10%{Z[2]}", 1)],
    "desc_override_lady_android_halloween_6": [("雷属性角色伤害额外乘区＋5%（最多＋15%）", f"雷属性角色伤害＋5%{Z[9]}（最多＋15%）", 1)],
    # 直击 3 段（场上有协力球时、合计伤害+25%）已在数据里，面板漏写，补一行
    "desc_override_blade_witch_halloween_4": [("暗属性角色「贯通」效果时间＋100%",
                                              f"暗属性角色「贯通」效果时间＋100%\n场上有协力球时，暗属性角色直接攻击计算为3次，合计伤害＋25%{Z[6]}", 1)],
    "desc_override_blade_witch_halloween_6": [("直接攻击伤害额外乘区＋15%", f"直接攻击伤害＋15%{Z[6]}", 1)],
    "desc_override_crystal_swordman_halloween_6": [("强化弹射伤害额外乘区＋0.5%（最多＋5%）", f"强化弹射伤害＋0.5%{Z[5]}（最多＋5%）", 1)],
    "desc_override_lich_halloween_3": [("伤害额外乘区＋1%（最多＋10%）", f"伤害＋1%{Z[9]}（最多＋10%）", 1)],
    "desc_override_lich_halloween_4": [("对处于「麻痹」或「气绝」状态的敌人伤害＋5%",
                                        f"对处于「麻痹」状态的敌人伤害＋5%{Z[2]}，对处于「气绝」状态的敌人伤害＋5%{Z[3]}", 1)],
}


def apply(F):
    n = 0
    for key, pairs in EDITS.items():
        v = F.string(CAS, key)
        s = rows(v)
        assert len(s) == 1 and len(s[0]) == 1, key
        t = s[0][0]
        for old, new, cnt in pairs:
            assert t.count(old) == cnt, (key, old, t.count(old))
            t = t.replace(old, new)
            n += cnt
        assert "额外乘区" not in t and "（独立乘区）" not in t and "状态特攻乘区" not in t, (key, t)
        nv = leaf(v, [[t]])
        assert rows(nv)[0] == [t]
        F.set_string(CAS, key, nv)
    F.log(f"覆盖文案补独立伤害乘区标签：{len(EDITS)} 个键，{n} 处")

def setrows(lp, key, rs):
    old = [r for r in rows(T[lp][key]) if r]
    if rs[0][1:3] != old[0][1:3]:
        raise AssertionError((key, "c1/c2", rs[0][1:3], old[0][1:3]))
    T[lp][key] = leaf(T[lp][key], rs)

def R(lp, key):
    return [r for r in rows(T[lp][key]) if r]

def setv(r, cols, old, new):
    for c in cols:
        assert r[c] == old, (c, r[c], old)
        r[c] = new

CHECK = []
# ===== A) 澄波响 169988 psychic_teleport_moon
rs = R(LD_LP, "169988")
for i, kind in ((10, "23"), (11, "0")):
    r = rs[i]; assert r[95] == "134" and r[102] == "16998801" and r[107] == kind and r[111] == r[112] == "20000", r
    setv(r, [100], "99", "10")
setrows(LD_LP, "169988", rs); CHECK.append(("leader_ability", "169988", rs))
override("desc_override_psychic_teleport_moon", "每1层“回响”，自身强化弹射伤害＋20%、攻击力＋20%", "每1层“回响”，自身强化弹射伤害＋20%（最大200%）、攻击力＋20%（最大200%）")
LOG.append("澄波响 队长 L10/L11（每层回响 强化弹射伤害/攻击力 +20%）计数上限 99 → 10（最大 200%）")
rs = R(AB_LP, "1699883"); r = rs[2]; assert r[109] == "413" and r[102] == "5"
setv(r, [113, 114], "5000", "1000"); setrows(AB_LP, "1699883", rs); CHECK.append(("ability", "1699883", rs))
override("desc_override_psychic_teleport_moon_3", "强化弹射伤害额外乘区＋5%（最多5层）", "强化弹射伤害额外乘区＋1%（最多5层）")
LOG.append("澄波响 能力3 #2 每层回响 强化弹射额外乘区 5% → 1%（最多5层）")
rs = R(AB_LP, "1699885"); r = rs[0]; assert r[109] == "413"
setv(r, [113, 114], "30000", "5000"); setrows(AB_LP, "1699885", rs); CHECK.append(("ability", "1699885", rs))
override("desc_override_psychic_teleport_moon_5", "强化弹射伤害额外乘区＋30%", "强化弹射伤害额外乘区＋5%")
LOG.append("澄波响 能力5 #0 强化弹射伤害额外乘区 30% → 5%")
# ===== B) 索恩 159994 tweyen_light
rs = R(AB_LP, "1599941"); r = rs[2]; assert r[47] == "538"
setv(r, [51, 52], "40000", "20000"); setrows(AB_LP, "1599941", rs); CHECK.append(("ability", "1599941", rs))
override("desc_override_tweyen_light_1", "光属性角色减益技能特攻＋40%", "光属性角色减益技能特攻＋20%")
LOG.append("索恩 能力1 #2 光属性减益技能特攻 40% → 20%")
rs = R(AB_LP, "1599942"); r = rs[0]; assert r[97] == "136" and r[109] == "258" and r[113] == "100000"
setv(r, [102], "", "4"); setrows(AB_LP, "1599942", rs); CHECK.append(("ability", "1599942", rs))
override("desc_override_tweyen_light_2", "光属性角色对该敌人的攻击力＋100%", "光属性角色对该敌人的攻击力＋100%【最大+400%】")
LOG.append("索恩 能力2 #0 每个弱体 光属性对敌攻击力特攻 +100%：计数上限 无 → 4（最大 +400%）")
rs = R(AB_LP, "1599943"); r = rs[3]; assert r[97] == "136" and r[109] == "2" and r[113] == "40000"
setv(r, [102], "", "4"); setrows(AB_LP, "1599943", rs); CHECK.append(("ability", "1599943", rs))
override("desc_override_tweyen_light_3", "自身技能伤害＋40%，且连击＋50", "自身技能伤害＋40%【最大+160%】，且连击＋50")
LOG.append("索恩 能力3 #3 每个弱体 自身技能伤害 +40%：计数上限 无 → 4（最大 +160%）")
# ===== C) 杰拉德 149999
p = "battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv3"
t = copy.deepcopy(dsl_tree(p)); n = 0
for pp, c in list(commands(t, "FindAllSubjects")):
    blk = c[9][1]
    idx = [i for i, cmd in enumerate(blk) if cmd[1][0] == "CreateCondition" and cmd[1][2][0][0] == "ACAdditionalDirectAttack"]
    if not idx: continue
    assert c[1] == 4 and c[2] == 33 and c[3] == [] and len(idx) == 1, c[:4]
    cc = blk.pop(idx[0])
    a = cc[1][2][0]; assert a[2] == [{"min": 4, "max": 4}] and a[3] == [{"min": 0.0, "max": 0.0}], a
    a[3] = [{"min": 1.0, "max": 1.0}]
    newfind = ["Command", ["FindAllSubjects", 4, 33, [5], [], [], [], [], ["DoNothing"], ["Block", [cc]]]]
    parent = get(t, pp[:-1]); assert parent[pp[-1]][1] is c
    parent.insert(pp[-1] + 1, newfind); n += 1
assert n == 2, n
files[wf_dsl.dsl_logical(p)] = encode_tree(t)
override("override_string_white_wolf_gerald", "强化弹射Lv3时，队伍全体的直接攻击变为4次（60秒）", "强化弹射Lv3时，强化光属性角色的直接攻击【直接攻击计算为4次，合计伤害+100%】（60秒）")
LOG.append("杰拉德 PF Lv3：直击 4 段 ACAdditionalDirectAttack 从全队选择器移到 光属性(元素码5) 选择器，合计伤害 0 → +100%（×2 分支）")
rs = R(LD_LP, "149999"); tpl = rs[5]
assert tpl[25] == "20" and tpl[27] == "White" and tpl[28] == "3500000" and tpl[45] == "255" and tpl[9] == "White"
for kind in ("32", "33", "388"):
    nr = list(tpl)
    nr[28] = nr[29] = "5000000"; nr[32] = "100"; nr[45] = kind; nr[46] = "5"; nr[47] = "White"; nr[49] = nr[50] = "4000"
    rs.append(nr)
setrows(LD_LP, "149999", rs); CHECK.append(("leader_ability", "149999", rs))
LOG.append("杰拉德 队长 新增 #9-#11：光共鸣时 光属性角色直击每 50 次 → 光属性角色 攻击力/直接攻击伤害/能力伤害 各 +4%（限 100 次 = 最大 +400%）")
rs = R(AB_LP, "1499993"); r = rs[3]; assert r[97] == "4" and r[109] == "46" and r[111] == "White"
setv(r, [113, 114], "0", "75000"); setrows(AB_LP, "1499993", rs); CHECK.append(("ability", "1499993", rs))
LOG.append("杰拉德 能力3 #3 Fever中 光属性角色 DirectAttack3 合计伤害 0 → +75%")

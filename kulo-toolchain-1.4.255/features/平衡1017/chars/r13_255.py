# -*- coding: utf-8 -*-
"""平衡表 10-19 14:34 至 23:00 的新块（1.4.255），14 个角色。"""
import copy
from dsltools import commands
from common import *
from fw import UQ, rows, join

S = lambda v: [{"min": v, "max": v}]
EMPTY7 = ["0", "", "", "", "", "", ""]


def _del(lst, idxs):
    for i in sorted(idxs, reverse=True):
        del lst[i]


def _uq_set(F, uid, **kw):
    v = F.string(UQ, uid)
    r = list(rows(v)[0])
    for k, val in kw.items():
        c = {"sid": 0, "name": 1, "cap": 4}[k]
        r[c] = val
    F.set_string(UQ, uid, join(r) + ("\n" if v.endswith("\n") else ""))
    return r


def _strip_cond(t, kind):
    """删掉 DSL 里所有只含 kind 一条状态的 CreateCondition 命令，返回删除数。"""
    n = [0]
    def walk(node):
        if isinstance(node, list):
            if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
                keep = []
                for c in node[1]:
                    if (isinstance(c, list) and len(c) == 2 and c[0] == "Command" and c[1][0] == "CreateCondition"
                            and len(c[1][2]) == 1 and c[1][2][0][0] == kind):
                        n[0] += 1; continue
                    keep.append(c)
                node[1] = keep
            for x in node:
                walk(x)
    walk(t)
    return n[0]


# ---------------- 1 拉夫马诺 151159
def lafumanuo(F):
    F.owner = "r13_151159"
    p = "battle/action/skill/action/rare5/golden_dragon_jr$golden_dragon_jr_3"
    t = F.dsl(p)
    hits = [c[2][0] for pp, c in commands(t, "CreateCondition") if c[2][0][0] == "ACAttackPoint"]
    assert len(hits) == 2 and all(h[2] == S(3.0) for h in hits), hits
    for h in hits:
        h[2] = S(1.5)
    F.log("拉夫马诺 技能『至天光辉＋＋』：赋予的攻击力提升 +300% → +150%")


# ---------------- 2 阿鲁玛德乌斯 261089
def alumadeus(F):
    F.owner = "r13_261089"
    p = "battle/action/skill/action/rare4/darkness_dragon$darkness_dragon_3"
    t = F.dsl(p)
    assert _strip_cond(t, "ACAttackPoint") == 2
    sd = [c[2][0] for pp, c in commands(t, "CreateCondition") if c[2][0][0] == "ACSkillDamage"]
    assert len(sd) == 2 and all(h[2] == S(3.0) for h in sd), sd
    for h in sd:
        h[2] = S(1.5)
    ab3 = F.ab("2610893")
    assert ab3[4][47] == "35" and ab3[4][51] == "30000"
    del ab3[4]
    F.skill_text("261089", "darkness_dragon", [("赋予我方全体角色攻击力提升＋技能伤害提升效果", "赋予我方全体角色技能伤害提升效果")], levels=("3",))
    F.log("阿鲁玛德乌斯 技能『魂魄终局＋＋』：删去攻击力提升，技能伤害提升 +300% → +150%；能力3 删去「技能充能速度+30%」")


# ---------------- 3 白狼杰拉德 149999
def gerald(F):
    F.owner = "r13_149999"
    p = "battle/action/skill/action/ability_skill/ability_skill_white_wolf_moon_fang$ability_skill_white_wolf_moon_fang"
    t = F.dsl(p)
    has = [c for pp, c in commands(t, "CreateHitArea")]
    assert [c[24] for c in has] == [4, 0, 4], [c[24] for c in has]
    for c in has:
        c[24] = 4
    t[10] = 4
    F.log("白狼杰拉德 「月牙斩」：所有判定区的伤害都按直接攻击伤害结算（原有一段按技能伤害结算）")


# ---------------- 4 稻穗 159991
def inaho(F):
    F.owner = "r13_159991"
    r = F.ab("1599911")[2]
    assert r[109] == "0"; setv(r, [AB_DC_S1, AB_DC_S2], 100000, 300000)
    ab3 = F.ab("1599913")
    a, b = ab3[1], ab3[2]
    assert (a[47], b[47], a[34], b[34]) == ("32", "388", "10", "10")
    setv(a, [AB_IC_S1, AB_IC_S2], 15000, 10000); a[34] = b[34] = "25"
    d = copy.deepcopy(b); d[47] = "33"
    ab3.insert(3, d)
    F.cas_replace("desc_override_cnmod_inaho_midautumn_1", [("Fever模式中，队伍全体攻击力+100%、能力伤害+300%", "Fever模式中，队伍全体攻击力+300%、能力伤害+300%")])
    F.cas_replace("desc_override_cnmod_inaho_midautumn_3", [("自身回复生命值时，队伍全体攻击力+15%、能力伤害+10%（最多10次）",
                                                             "自身回复生命值时，队伍全体攻击力+10%、能力伤害+10%、直接攻击伤害+10%（最多25次）")])
    F.log("稻穗（祈月之穗）能力1：Fever模式中队伍全体攻击力 +100% → +300%；能力3：光属性共鸣时Fever中自身回复生命值时，队伍全体攻击力 +15% → +10%、能力伤害 +10%，新增直接攻击伤害 +10%，最多 10 → 25 次")


# ---------------- 5 泽赫尔 159997
def zeher(F):
    F.owner = "r13_159997"
    le = F.le("159997")
    assert (le[2][45], le[6][45], le[7][45], le[6][33]) == ("55", "32", "55", "300")
    r = le[6]; setv(r, [49, 50], 5000, 10000); r[33] = "120"
    pf = copy.deepcopy(r); pf[45] = "55"; pf[49] = pf[50] = "12000"
    le.insert(7, pf)
    _del(le, [2, 8])          # 35连击自身强化弹射伤害、原第7条（自身强化弹射+5%）
    ab2 = F.ab("1599972"); assert ab2[0][6] == "42" and ab2[1][6] == "42"
    _del(ab2, [0, 1])
    ab3 = F.ab("1599973")
    r = ab3[0]; assert (r[47], r[48], r[34], r[35]) == ("32", "5", "8", "300")
    r[48] = "0"; r[49] = ""; r[34] = "20"; r[35] = "120"
    pf = copy.deepcopy(r); pf[47] = "55"
    assert ab3[3][47] == "55" and ab3[3][34] == "10"
    del ab3[3]
    ab3.insert(1, pf)
    F.cas_replace("desc_override_guildknight_leader_tavern", [
        (" / " if False else "\n每达成35连击，自身强化弹射伤害+6%（最多15次）", ""),
        ("光属性共鸣时，每达成55连击，光属性角色攻击力+5%（最多45次，CT：5秒）", "光属性共鸣时，每达成55连击，光属性角色攻击力+10%、强化弹射伤害+12%（最多45次，CT：2秒）"),
        ("\n光属性共鸣时，每达成55连击，自身强化弹射伤害+5%（最多45次，CT：5秒）", ""),
        ("\n每达成15连击，自身攻击力+25%、强化弹射伤害+25%（最多10次）", "")])
    F.cas_replace("desc_override_guildknight_leader_tavern_3", [
        ("光属性共鸣时，每达成55连击，光属性角色攻击力+10%（最多8次，CT：5秒）", "光属性共鸣时，每达成55连击，自身攻击力+10%、强化弹射伤害+10%（最多20次，CT：2秒）"),
        ("\n <icon id='main'>  光属性共鸣时，每达成55连击，自身强化弹射伤害+10%（最多10次，CT：5秒）", "")])
    F.log("泽赫尔 队长技：删去「每达成35连击自身强化弹射伤害+6%」「每达成55连击自身强化弹射伤害+5%」「每达成15连击自身攻击力+25%、强化弹射伤害+25%」；"
          "每达成55连击光属性角色攻击力 +5% → +10%，新增强化弹射伤害 +12%（最多45次），CT 5秒 → 2秒")
    F.log("泽赫尔 能力3：每达成55连击「光属性角色攻击力+10%（8次）」→「自身攻击力+10%、强化弹射伤害+10%（20次）」，CT 5秒 → 2秒；删去「自身强化弹射伤害+10%（10次）」")


# ---------------- 6 克劳斯 129997
ATK_SLAYER = "258"   # 触发敌方攻击力特攻（贝尔赛蒂亚能力1同款）


def klaus(F):
    F.owner = "r13_129997"
    le = F.le("129997")
    assert (le[1][45], le[2][45]) == ("388", "33")
    setv(le[1], [49, 50], 600000, 200000); setv(le[2], [49, 50], 1000000, 200000)
    atk = copy.deepcopy(le[2]); atk[45] = "32"; atk[49] = atk[50] = "150000"
    r4, r5 = le[4], le[5]
    assert (r4[107], r5[107], r4[100], r5[100]) == ("159", "348", "5", "5")
    setv(r4, [111, 112], 150000, 25000); setv(r5, [111, 112], 70000, 25000); r4[100] = r5[100] = "20"
    sl = copy.deepcopy(r4); sl[107] = ATK_SLAYER; sl[111] = sl[112] = "10000"
    le.insert(6, sl)
    le.insert(3, atk)
    _uq_set(F, "12999702", sid="wfx:28:129997:18800:1:hidden_klaus_poison_reach", name="敌人「淬毒」等级达到1时，对其直接攻击的基础伤害变为3倍")
    _uq_set(F, "12999703", sid="wfx:29:129997:1200:21:hidden_klaus_poison_layer", name="敌人「淬毒」等级从2级起每1级，对其直接攻击的基础伤害再+12%（最多20级）")
    ab1 = F.ab("1299971"); assert (ab1[0][47], ab1[1][47]) == ("33", "388")
    _del(ab1, [0, 1])
    ab2 = F.ab("1299972"); r = ab2[1]
    assert (r[109], r[102]) == ("159", "10")
    setv(r, [AB_DC_S1, AB_DC_S2], 40000, 20000); r[102] = "20"
    a = copy.deepcopy(r); a[109] = "348"
    k = copy.deepcopy(r); k[109] = ATK_SLAYER; k[113] = k[114] = "5000"
    ab2[2:2] = [a, k]
    ab3 = F.ab("1299973")
    assert (ab3[0][109], ab3[1][109]) == ("348", "159")
    setv(ab3[0], [AB_DC_S1, AB_DC_S2], 200000, 300000); setv(ab3[1], [AB_DC_S1, AB_DC_S2], 400000, 300000)
    k = copy.deepcopy(ab3[1]); k[109] = ATK_SLAYER; k[113] = k[114] = "150000"
    ab3.insert(2, k)
    r = ab3[3]; assert r[68] == "12999701" and r[34] == "5"; r[34] = "20"
    setv(ab3[4], [AB_DC_S1, AB_DC_S2], 3000, 2000); setv(ab3[5], [AB_DC_S1, AB_DC_S2], 1500, 1000)
    ab3[4][102] = ab3[5][102] = "20"
    _uq_set(F, "12999701", cap="20")
    ab5 = F.ab("1299975")
    a, b = ab5
    assert (a[47], b[47], a[30], a[34]) == ("33", "388", "500000", "5")
    for r in ab5:
        r[30] = r[31] = "6000000"; r[34] = "20"
    k = copy.deepcopy(a); k[47] = "32"; k[51] = k[52] = "5000"
    ab5.insert(0, k)
    F.cas_replace("desc_override_claude_wolf_assassin_ex_2", [
        ("敌人的「淬毒」每1层，队伍全体对其造成的直接攻击伤害+40%（最多10层）", "敌人的「淬毒」每1层，队伍全体对其造成的直接攻击伤害+20%、能力伤害+20%、攻击力+5%（最多20层）")])
    F.log("克劳斯 队长技：水属性共鸣时战斗开始 能力伤害 +600%→+200%、直接攻击伤害 +1000%→+200%，新增攻击力 +150%（技能槽+50%不变）；"
          "「淬毒」等级达到1时全队对其直接攻击基础伤害 2.5倍→3倍，从2级起每级 +55%（最多10级）→ +12%（最多20级）；"
          "敌人「淬毒」每1层 对其直接攻击伤害 +150%（5层）→ +25%（20层，最大+500%）、能力伤害 +70%（5层）→ +25%（20层）、新增攻击力 +10%（20层）")
    F.log("克劳斯 能力1：删去「水属性角色直接攻击伤害+150%、能力伤害+150%」；能力2：「淬毒」每1层队伍全体对其直接攻击伤害 +40%（10层）→ +20%，新增能力伤害 +20%、攻击力 +5%（20层）")
    F.log("克劳斯 能力3：对「淬毒」中的敌人 能力伤害 +200%→+300%、直接攻击伤害 +400%→+300%，新增攻击力 +150%；「猎狼连击」每级 直接攻击伤害 +3%→+2%（乘区6）、能力伤害 +1.5%→+1%（乘区8），最多 5→20 级")
    F.log("克劳斯 能力5：每直接攻击5次 → 每60次：直接攻击伤害 +20%、能力伤害 +20%（最多 5→20 次），新增攻击力 +5%（20次）")


# ---------------- 7 雷吉斯 139994
def regis(F):
    F.owner = "r13_139994"
    le = F.le("139994")
    for i in (0, 1):
        r = le[i]; assert r[102] == "13999401" and r[100] == "30"
        setv(r, [111, 112], 40000, 80000); r[100] = "15"
    r = F.ab("1399946")[1]; assert r[47] == "724"; setv(r, [AB_TRIG_CT], 300, 120)
    r = F.ab("1399942")[0]; assert r[47] == "629"; setv(r, [AB_TRIG_CT], 300, 0)
    ab3 = F.ab("1399943")
    r = ab3[2]; assert r[47] == "211" and r[46] == "2"; r[46] = "4"
    a, b = ab3[3], ab3[4]
    assert a[104] == b[104] == "13999401"
    setv(a, [AB_DC_S1, AB_DC_S2], 10000, 20000); setv(b, [AB_DC_S1, AB_DC_S2], 20000, 40000); a[102] = b[102] = "15"
    F.cas_replace("desc_override_rec_android_seaside", [
        ("「浪涌充能」每1层，雷属性角色攻击力+40%、技能伤害+40%（最多30层）", "「浪涌充能」每1层，雷属性角色攻击力+80%、技能伤害+80%（最多15层）"),
        ("每冲刺1次，Fever槽+5%（CT：5秒）", "每冲刺1次，Fever槽+5%（CT：2秒）")])
    F.cas_replace("desc_override_rec_android_seaside_2", [("雷属性技能伤害（CT：5秒）", "雷属性技能伤害")])
    F.cas_replace("desc_override_rec_android_seaside_3", [
        ("进入Fever模式2秒后", "进入Fever模式4秒后"),
        ("「浪涌充能」每1层，自身攻击力+10%、技能伤害+20%（最多30层）", "「浪涌充能」每1层，自身攻击力+20%、技能伤害+40%（最多15层）")])
    F.log("雷吉斯 队长技：「浪涌充能」每1层雷属性角色攻击力、技能伤害 +40% → +80%（最多 30 → 15 层）；非Fever中每冲刺1次Fever槽+5% 的 CT 5秒 → 2秒")
    F.log("雷吉斯 能力2：雷属性角色发动技能时对全体敌人20倍雷属性技能伤害，去掉 CT 5秒；能力3：进入Fever模式 2秒 → 4秒后自身技能槽+50%；「浪涌充能」每1层自身攻击力 +10%→+20%、技能伤害 +20%→+40%（最多 30 → 15 层）")


# ---------------- 8 黑 139991
def kuro(F):
    F.owner = "r13_139991"
    r = F.ab("1399913")[2]; assert r[47] == "724"
    setv(r, [AB_TRIG_TH1, AB_TRIG_TH2], 5000000, 7500000)
    F.cas_replace("desc_override_outlaw_panther_moon_3", [("Fever模式中，雷属性角色合计每直接攻击50次，Fever槽-20%", "Fever模式中，雷属性角色合计每直接攻击75次，Fever槽-20%")])
    F.log("黑 能力3：Fever模式中雷属性角色合计每直接攻击 50 → 75 次，Fever槽-20%")


# ---------------- 9 凯尔 139990
def kyle(F):
    F.owner = "r13_139990"
    le = F.le("139990")
    setv(le[1], [111, 112], 7500, 3500); setv(le[3], [111, 112], 15000, 7500)
    ab2 = F.ab("1399902")
    setv(ab2[0], [AB_DC_S1, AB_DC_S2], 5000, 4000); setv(ab2[1], [AB_DC_S1, AB_DC_S2], 8000, 4000)
    ab3 = F.ab("1399903")
    a, b = ab3[4], ab3[5]
    assert a[70] == b[70] == "ability_skill_kyle_moon_pierce" and (a[27], b[27]) == ("23", "20")
    a[27] = "77"; a[28] = "0"; a[29] = ""; a[30] = a[31] = "3000000"
    del ab3[5]
    p = "battle/action/skill/action/ability_skill/ability_skill_kyle_moon_pierce$ability_skill_kyle_moon_pierce"
    t = F.dsl(p)
    blk = t[11][1]
    assert len(blk) == 2 and blk[0][1][0] == "BindConditionAccumulationVariable" and blk[1][1][0] == "CreateCondition"
    self_cc = blk[1]
    bind2 = copy.deepcopy(blk[0]); bind2[1][2] = 2; bind2[1][4] = 3; bind2[1][5] = 33
    party_cc = copy.deepcopy(self_cc); party_cc[1][1] = 11
    party_cc[1][2][0][2] = [{"min": 1, "max": 1, "vlv": [{"vid": 2, "min": 0, "max": 1}]}]
    find = ["Command", ["FindAllSubjects", 11, 113, [3], [], [], [], [], ["DoNothing"], ["Block", [party_cc]]]]
    t[11][1] = [blk[0], bind2, find, self_cc]       # 先给全队雷属性按 月牙/3，再用同名状态把自身覆盖成 月牙层数
    F.cas_replace("ability_skill_kyle_moon_pierce", [("「月牙」每1层，自身直接攻击计算次数+1", "「月牙」每1层，自身直接攻击计算次数+1；「月牙」每3层，除自身外的雷属性角色直接攻击计算次数+1")])
    F.cas_replace("desc_override_kyle_moon", [
        ("「月牙」每1层，自身攻击力+7.5%、直接攻击伤害+15%（最多66层）", "「月牙」每1层，自身攻击力+3.5%、直接攻击伤害+7.5%（最多66层）"),
        ("雷属性共鸣时，雷属性角色发动技能时，按「月牙」层数增加自身直接攻击计算次数（每1层+1）",
         "雷属性共鸣时，「月牙」每1层，自身直接攻击计算次数+1；「月牙」每3层，除自身外的雷属性角色直接攻击计算次数+1"),
        ("\n雷属性共鸣时，雷属性角色合计每直接攻击100次，按「月牙」层数增加自身直接攻击计算次数（每1层+1）", "")])
    F.cas_replace("desc_override_kyle_moon_2", [("自身攻击力+8%（最多99层）", "自身攻击力+4%（最多99层）"), ("雷属性角色直接攻击伤害+5%（最多99层）", "雷属性角色直接攻击伤害+4%（最多99层）")])
    F.log("凯尔 队长技：「月牙」每1层自身攻击力 +7.5%→+3.5%、直接攻击伤害 +15%→+7.5%；直接攻击计算次数由「发动技能时/每直接攻击100次按月牙加」改为常驻："
          "「月牙」每1层自身+1，每3层除自身外的雷属性角色+1（删去每直接攻击100次那条）")
    F.log("凯尔 能力2：「月牙」每1层自身攻击力 +8%→+4%、雷属性角色直接攻击伤害 +5%→+4%")


# ---------------- 10 休尔特 141099（超限）
def shulte(F):
    F.owner = "r13_141099"
    le = F.le("141099")
    r = le[2]; assert r[45] == "32"; setv(r, [49], 225000, 75000); setv(r, [50], 300000, 100000)
    r = F.ab("1410991")[2]; assert r[47] == "696"; setv(r, [AB_IC_S1], 12500, 7500); setv(r, [AB_IC_S2], 25000, 15000)
    ab3 = F.ab("1410993"); assert ab3[4][47] == "55"; del ab3[4]
    r = F.ab("1410994")[2]; assert (r[5], r[27], r[47]) == ("0", "0", "55")
    r[47] = "245"; setv(r, [AB_IC_S1], 75000, 7500); setv(r, [AB_IC_S2], 150000, 15000)
    p = "battle/action/skill/action/ability_skill/ability_skill_wind_dragon_wt22_ol_typhoon$ability_skill_wind_dragon_wt22_ol_typhoon"
    t = F.dsl(p)
    n3 = n5 = 0
    for pp, c in commands(t, "CreateNormalAttack"):
        if c[6] == S(3.0): c[6] = S(5.0); n3 += 1
        elif c[6] == S(5.0): c[6] = S(10.0); n5 += 1
        else: raise AssertionError(c[6])
    assert n3 == 36 and n5 == 3, (n3, n5)
    F.log("休尔特（超限）队长技：风属性角色攻击力 +300% → +100%；能力1（主位）：强化弹射伤害 +25% → +15%（独立伤害乘区5）；"
          "能力3（主位）：删去每2次强化弹射「强化弹射伤害+45%」；能力4：战斗开始时「强化弹射伤害+150%」→「技能槽最大值+15%」；"
          "超限后强化弹射卷起的龙卷每道 ×3 → ×5、台风每圈 ×5 → ×10")


# ---------------- 11 莫弥亚 169985
MARK, MO_BASE, MO_MARK2 = "16998501", "16998502", "16998503"


def momiya(F):
    F.owner = "r13_169985"
    _uq_set(F, MO_BASE, sid="wfx:24:0:50000:0:hidden_mo_direct_base")
    _uq_set(F, MARK, sid="unique_halloween_hunter_mark")
    uq = F.table(UQ); assert MO_MARK2 not in uq
    nr = list(rows(F.string(UQ, MO_BASE))[0])
    nr[0] = "wfx:24:0:6000:0:hidden_mo_mark_base"; nr[1] = "猎魔标记·直击基础倍率"; nr[4] = "11"
    F.set_string(UQ, MO_MARK2, join(nr) + "\n")
    for lv in ("1", "2"):
        t = F.dsl(f"battle/action/skill/action/rare5/blade_witch_halloween$blade_witch_halloween_{lv}")
        hit = []
        def walk(node):
            if isinstance(node, list):
                if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
                    out = []
                    for c in node[1]:
                        out.append(c)
                        if (isinstance(c, list) and len(c) == 2 and c[0] == "Command" and c[1][0] == "CreateCondition"
                                and c[1][2][0][0] == "ACUnique" and c[1][2][0][1] == int(MARK)):
                            d = copy.deepcopy(c); d[1][2] = [["ACUnique", int(MO_MARK2), S(1)]]
                            out.append(d); hit.append(1)
                    node[1] = out
                for x in node:
                    walk(x)
        walk(t)
        assert len(hit) == 1, (lv, hit)
    F.cas_replace("desc_override_blade_witch_halloween_3", [
        ("自身直接攻击的基础伤害变为2倍，「猎魔标记」每1层再+6%（最大+666%）", "自身直接攻击的基础伤害变为6倍，「猎魔标记」每1层再+60%（最大+660%）")])
    F.log("莫弥亚 能力3（主位）：自身直接攻击的基础伤害 2倍 → 6倍，「猎魔标记」每1层再 +6%（最大+666%）→ +60%（最大+660%，即计 11 层）")


# ---------------- 12 露迪 139985
def ludi(F):
    F.owner = "r13_139985"
    r = F.ab("1399853")[0]; assert (r[27], r[28], r[47]) == ("23", "0", "724")
    r[28] = "5"; r[29] = "Yellow"
    F.cas_replace("desc_override_lady_android_halloween_3", [("非Fever模式中，自身发动技能时，Fever槽+5%", "非Fever模式中，雷属性角色发动技能时，Fever槽+5%")])
    F.log("露迪 能力3：非Fever模式中「自身发动技能时」→「雷属性角色发动技能时」Fever槽+5%")


# ---------------- 13 特克托 139993
def tecto(F):
    F.owner = "r13_139993"
    le = F.le("139993")
    assert len(le) == 12
    r = le[2]; assert r[11] == "9"; r[11:18] = list(EMPTY7); setv(r, [111, 112], 4000, 5000)
    gate_thunder = ["2", "0", "", "600000", "600000", "Yellow", ""]
    for i, n in ((10, 125000), (11, 210000)):
        r = le[i]; assert r[4] == "8" and r[11] in EMPTY
        r[11:18] = list(gate_thunder); r[49] = r[50] = str(n)
    _del(le, [0, 1, 4, 8])
    ab2 = F.ab("1399932")
    tpl = F.ab("1399853")[0]     # 露迪能力3：自身发动技能时（瞬发 23）
    new = []
    for r, kind, n in ((ab2[0], "32", 70000), (ab2[1], "34", 90000)):
        assert r[97] == "134" and r[6] == "9"
        x = list(tpl); x[0:5] = r[0:5]
        x[6:13] = ["8", "0", "", "50000", "50000", "", ""]
        x[27:32] = ["23", "0", "", "100000", "100000"]; x[34] = "2"; x[35] = "0"
        x[47] = kind; x[48] = "0"; x[51] = x[52] = str(n)
        new.append(x)
    ab2[:] = new
    ab4 = F.ab("1399934")
    setv(ab4[0], [AB_IC_S1], 35000, 60000); setv(ab4[0], [AB_IC_S2], 70000, 120000)
    r = ab4[1]; assert r[47] == "32"
    g = copy.deepcopy(r); g[6:13] = ["2", "", "", "600000", "600000", "Yellow", ""]; g[47] = "245"; g[51] = g[52] = "25000"
    ab4[1] = g
    F.log("特克托 队长技：删去「生命值50%以下时引擎每级 自身攻击力/技能伤害+150%」「技能槽最大值+5%」「重炮展开中生命值50%以下释放技能时技能伤害+135%」；"
          "引擎每级技能伤害 +4%（生命值50%以下）→ +5%（独立伤害乘区7，最大+15%，不再要求生命值）；"
          "生命值50%以上释放技能时 攻击力 +50%→+125%（最大+250%）、技能伤害 +60%→+210%（最大+420%），改为需要雷属性共鸣")
    F.log("特克托 能力2：「生命值50%以下引擎每级 攻击力+70%、技能伤害+90%」→「生命值50%以上释放技能时 攻击力+70%（最大+140%）、技能伤害+90%（最大+180%）」")
    F.log("特克托 能力4：生命值50%以下对抗性降低中的敌人攻击力 +70% → +120%；删去「自身攻击力+80%」；新增「雷属性共鸣时，自身技能槽最大值+25%」")


# ---------------- 14 风巨蜥 149998
def land_dragon(F):
    F.owner = "r13_149998"
    r = F.ab("1499981")[1]; assert r[47] == "21"
    setv(r, [AB_IC_S1], 50000, 5000); setv(r, [AB_IC_S2], 100000, 10000)
    ab2 = F.ab("1499982")
    a, b = ab2[0], ab2[1]
    assert (a[30], b[30]) == ("1000000", "1500000")
    setv(a, [AB_IC_S1], 7500000, 2500000); setv(a, [AB_IC_S2], 15000000, 5000000)
    setv(b, [AB_TRIG_TH1, AB_TRIG_TH2], 1500000, 1000000)
    setv(b, [AB_IC_S1], 15000000, 5000000); setv(b, [AB_IC_S2], 30000000, 10000000)
    F.cas_replace("desc_override_land_dragon_wind_playable_2", [
        ("每达成10连击，Fever槽+150", "每达成10连击，Fever槽+50"),
        ("每达成15连击，Fever槽+300", "每达成10连击，Fever槽+100")])
    F.log("风巨蜥 能力1：风属性共鸣时自身发动技能时，15秒内自身攻击造成的Fever槽上升率 +100% → +10%；"
          "能力2：非Fever中每达成10连击 Fever槽 +150 → +50，「每达成15连击 +300」→「每达成10连击 +100」")


def apply(F):
    for f in (lafumanuo, alumadeus, gerald, inaho, zeher, klaus, regis, kuro, kyle, shulte, momiya, ludi, tecto, land_dragon):
        f(F)
    F.owner = None

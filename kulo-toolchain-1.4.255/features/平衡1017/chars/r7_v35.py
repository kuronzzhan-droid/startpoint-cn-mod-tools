# -*- coding: utf-8 -*-
"""v35 客户端（通用直击基础倍率 wfx 码 24/28/29 + wfx 隐藏图标）上线后才生效的平衡表条目（表 10-18 晚版本）。
v34 客户端读到这些 wfx 状态只是普通固有状态（不生效、不崩）；凯尔 13999012 改 625→500 后，v34 上是 2倍+5%/连击。
- 莫弥亚 169985 能力3（主位）：自身直接攻击基础伤害 2倍，「猎魔标记」每1层再+6%（最大+666%）。
- 凯尔 139990 队长技：自身直接攻击基础伤害 2倍+6.25%/连击 → 表上原值 2.5倍+5%/连击。
- 贝尔赛蒂亚 129952 队长技：敌人弱体≥1 时自身直击基础倍率 2倍，≥2 起每个再+3%（最大20层）。
- 克劳斯 129997 队长技（水共鸣）：敌人「淬毒」等级≥1 时全队直击基础伤害 1.3倍，≥2 起每级再+3%（最高10层）。"""
import copy
from common import *
from fw import UQ, rows, join

MARK = "16998501"      # 猎魔标记（1.4.232 新建）
MO_BASE = "16998502"
KY_PLUS = "13999013"
BEL_BASE, BEL_EACH = "12995201", "12995202"
KL_REACH, KL_LAYER = "12999702", "12999703"
POISON = "129997"      # 敌人身上的「淬毒」（层数 = 等级，c4=20）
DP = "battle/action/skill/action/ability_skill/ability_skill_kyle_moon_direct_params$ability_skill_kyle_moon_direct_params"


def _new_unique(F, uid, sid, name, icon, src_uid="16998501"):
    uq = F.table(UQ)
    assert uid not in uq, uid
    src = rows(uq[src_uid])[0]
    nr = list(src)
    nr[0], nr[1], nr[2], nr[3], nr[4] = sid, name, icon, "99999999", "1"
    nr[9] = "false"     # 不可驱散
    F.set_string(UQ, uid, join(nr) + ("\n" if uq[src_uid].endswith("\n") else ""))


def _ab_grant_self(F, head_row, uid):
    """能力表：战斗开始时给自身 1 层固有（模板 = 官方 1410216#0 自身 461）。"""
    t = list(F.ab("1410216")[0])
    assert (t[5], t[27], t[47], t[48]) == ("0", "0", "461", "0") and t[68] == "1"
    t[0:5] = head_row[0:5]
    t[68] = uid
    return t


def _le_grant(F, cid, gate_src, target, group, uid):
    """队长表：战斗开始时给 target 1 层固有（模板 = 赛瑞斯队长#0 自身 461，官方先例 111183/121177 等）。"""
    s = list(F.le("129999")[0])
    assert (s[3], s[25], s[45], s[46], s[66]) == ("0", "0", "461", "0", "1299901")
    s[0] = F.le(cid)[0][0]
    s[4:11] = gate_src[4:11] if gate_src is not None else ["0", "", "", "", "", "", ""]
    s[46], s[47] = target, group
    s[66] = uid
    return s


def apply(F):
    # ---------- 莫弥亚 169985 能力3
    F.owner = "r7_169985"
    uq = F.table(UQ)
    m = list(rows(uq[MARK])[0])
    assert m[0] == "unique_halloween_hunter_mark" and m[4] == "111"
    m[0] = "wfx:24:0:600:0:hunter_mark"            # 标记本身：每层 自身直击基础倍率 +6%
    F.set_string(UQ, MARK, join(m) + ("\n" if uq[MARK].endswith("\n") else ""))
    _new_unique(F, MO_BASE, "wfx:24:0:10000:0:hidden_mo_direct_base", "猎魔·直击基础倍率",
                "battle/common/unique_condition/unique_halloween_candy")
    ab3 = F.ab("1699853")
    assert len(ab3) == 3 and all(r[104] == MARK for r in ab3)
    ab3.append(_ab_grant_self(F, ab3[0], MO_BASE))
    F.cas_replace("desc_override_blade_witch_halloween_3", [
        ("暗属性角色攻击力+6%、直接攻击伤害+6%（最大+666%）",
         "暗属性角色攻击力+6%、直接攻击伤害+6%（最大+666%）\n <icon id='main'>  自身直接攻击的基础伤害变为2倍，「猎魔标记」每1层再+6%（最大+666%）")])
    F.log("莫弥亚 能力3（主位）：新增自身直接攻击的基础伤害变为2倍，「猎魔标记」每1层再+6%（最大+666%）")

    # ---------- 凯尔 139990 队长技
    F.owner = "r7_139990"
    _new_unique(F, KY_PLUS, "wfx:24:0:2500:0:hidden_kyle_base_plus", "月狼直击倍率·追加",
                "battle/common/unique_condition/unique_kyle_moon_crescent", src_uid="13999011")
    t = F.dsl(DP)
    cc = t[11][1]
    a, b = cc[0][1][2][0], cc[1][1][2][0]
    assert a[:2] == ["ACUnique", 13999011] and a[2] == [{"min": 2, "max": 2}]
    assert b[:2] == ["ACUnique", 13999012] and b[2] == [{"min": 625, "max": 625}]
    b[2] = [{"min": 500, "max": 500}]
    plus = copy.deepcopy(cc[0])
    plus[1][2] = [["ACUnique", int(KY_PLUS), [{"min": 1, "max": 1}]]]
    plus[1][7] = "kyle_moon_direct_" + KY_PLUS
    cc.append(plus)
    F.cas_replace("desc_override_kyle_moon", [
        ("自身直接攻击的基础伤害变为2倍，每1连击再+6.25%（无上限）", "自身直接攻击的基础伤害变为2.5倍，每1连击再+5%（无上限）")])
    F.cas_replace("ability_skill_kyle_moon_direct_params", [("基础伤害变为2倍，每1连击再+6.25%", "基础伤害变为2.5倍，每1连击再+5%")])
    F.log("凯尔 队长技：自身直接攻击的基础伤害 2倍、每1连击+6.25% → 2.5倍、每1连击+5%（1.4.236 受客户端限制取的近似，现按表原值）")

    # ---------- 贝尔赛蒂亚 129952 队长技
    F.owner = "r7_129952"
    icon = "battle/common/unique_condition/unique_halloween_candy"
    _new_unique(F, BEL_BASE, "wfx:24:2:9700:0:hidden_bel_weak_base",
                "敌人弱体效果数量达到1时，自身对其直接攻击的基础伤害变为2倍", icon)
    _new_unique(F, BEL_EACH, "wfx:24:3:300:21:hidden_bel_weak_each",
                "敌人弱体效果数量从第2个起每多1个，自身对其直接攻击的基础伤害再+3%（最多20个）", icon)
    le = F.le("129952")
    assert len(le) == 8
    le.append(_le_grant(F, "129952", None, "0", "", BEL_BASE))
    le.append(_le_grant(F, "129952", None, "0", "", BEL_EACH))
    F.log("贝尔赛蒂亚 队长技：新增敌人弱体效果数量达到1时，自身对其直接攻击的基础伤害变为2倍；从第2个起每多1个再+3%（最多20个）")

    # ---------- 克劳斯 129997 队长技
    F.owner = "r7_129997"
    _new_unique(F, KL_REACH, f"wfx:28:{POISON}:2700:1:hidden_klaus_poison_reach",
                "敌人「淬毒」等级达到1时，对其直接攻击的基础伤害变为1.3倍",
                "battle/common/unique_condition/unique_claude_wolf_poison")
    _new_unique(F, KL_LAYER, f"wfx:29:{POISON}:300:11:hidden_klaus_poison_layer",
                "敌人「淬毒」等级从2级起每1级，对其直接攻击的基础伤害再+3%（最多10级）",
                "battle/common/unique_condition/unique_claude_wolf_poison")
    le = F.le("129997")
    assert len(le) == 9 and le[1][4:11] == ["2", "0", "", "600000", "600000", "Blue", ""]
    le.append(_le_grant(F, "129997", le[1], "5", "(None)", KL_REACH))
    le.append(_le_grant(F, "129997", le[1], "5", "(None)", KL_LAYER))
    F.log("克劳斯 队长技：新增水属性共鸣时，敌人「淬毒」等级达到1时，队伍全体对其直接攻击的基础伤害变为1.3倍；从2级起每1级再+3%（最多10级）")
    F.owner = None

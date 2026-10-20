# -*- coding: utf-8 -*-
"""赛瑞斯 129999 seris_dragon_king 重做（设计稿 v2，作者 10-15 拍板）：纯水 Fever＋强化弹射队长。

用法：WF_TIP=<当前尾号> python seris_rework.py --from 1.4.X --to 1.4.Y [--write]
默认 dry run。要新 APK（PF Lv4 = v32-pflv4）；没有该 APK 时 Lv4 行查询不到，其余照常。

改动面：
- 技能：action_skill 两档（人形『苍海潮涌』）、switched_action_skill（龙形『龙王吐息・苍潮』）、4 棵技能 DSL；
- 629：化龙自动龙息 / 冲刺「龙翼冲撞」人形与龙形各一棵；
- PF：override_seris_human_powerflip（射击＋特殊）、override_seris_dragon_special（五种）lv1-3 重写；
  新键 override_seris_human_lv4 / override_seris_dragon_lv4（lv3 列 = Lv4 动作，levels "4"）；
- 队长技 9 行 → 新 9 行；六个能力键重写；unique_condition 22 时长 1500→3600（由 Fever 结束删除）；
- 面板 desc_override 七条；character_text 技能名/说明；服务端 cdndata/character_text.json 同步。
"""
import copy
import hashlib
import json
import os
import sys
import zipfile
import zlib
from pathlib import Path

BUILD = Path(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(BUILD))
sys.path.insert(0, str(HERE))
os.chdir(BUILD)
from live149 import *  # noqa
from layout import D  # noqa
import wf_dsl
import wf_mod_tool as M
from dsltools import commands
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W
import seris_pf_quiet as PF          # quiet 1015：非保留类型 PF 特效走静音副本

NL = chr(10)
CID, CODE = "129999", "seris_dragon_king"
OUTDIR = HERE.parent / "patch"
LOG: list[str] = []

AB_LP = "master/ability/ability.orderedmap"
LE_LP = "master/ability/leader_ability.orderedmap"
AS_LP = "master/skill/action_skill.orderedmap"
SW_LP = "master/skill/switched_action_skill.orderedmap"
PFA_LP = "master/skill/power_flip_action.orderedmap"
UC_LP = "master/character/unique_condition.orderedmap"
TX_LP = "master/character/character_text.orderedmap"
CAS_LP = "master/string/custom_ability_string.orderedmap"

SK = "battle/action/skill/seris_dragon_king/"
P_H1, P_H2 = SK + "seris_dragon_king", SK + "seris_dragon_king_2"
P_D1, P_D2 = SK + "seris_dragon_king_matched", SK + "seris_dragon_king_matched_2"
AS629 = "battle/action/skill/action/ability_skill/"
def p629(name): return f"{AS629}{name}${name}"
P_BREATH, P_DASH_H, P_DASH_D = p629("ability_skill_seris_breath"), p629("ability_skill_seris_dash_h"), p629("ability_skill_seris_dash_d")
P_REVERT = p629("ability_skill_seris_revert")
PFO = "battle/action/power_flip/action/override/"
EMPTY = "battle/action/power_flip/action/empty"
def pfp(key, lv): return f"{PFO}{key}${key}_lv{lv}"
K_HUMAN, K_DRAGON = "override_seris_human_powerflip", "override_seris_dragon_special"
K_HUMAN4, K_DRAGON4 = "override_seris_human_lv4", "override_seris_dragon_lv4"
PF3_BTA = 133           # damage-type-rules-v1：按强化弹射 Lv3 完整结算
UID_DRAGON = "22"
UID_TIDE = "1299901"       # 苍海龙域（队长开局自挂，客户端补丁 feverItems 读它）

V = lambda lo, hi=None: [{"min": lo, "max": lo if hi is None else hi}]
cmd = lambda *a: ["Command", list(a)]
wait = lambda n, body: ["Event", ["Wait", n, "*", ["Block", body]]]
files: dict[str, bytes] = {}
new_files: list[str] = []


# ================================================================== DSL
ENH_FRAMES = 1200          # 技能强化：敌方强化弹射抗性 / 水属性抗性 −15%，20 秒，强制赋予


def water_only(tree, mults, add_combo=None, keep_effects=True, enhance=True):
    """基于旧技能树：删雷段（元素码 3）、删驱散/状态/贯穿/化龙，水段倍率按 mults 顺序重写；根头 133。"""
    t = copy.deepcopy(tree)
    t[10] = PF3_BTA
    blk = t[11][1]
    out = []
    for st in blk:
        c = st[1]
        if st[0] == "Command" and c[0] == "CreateCondition":
            continue                                   # 化龙 uc22（形态改由 Fever 驱动）
        if st[0] == "Command" and c[0] == "FindAllSubjects" and c[2] == 97:
            continue                                   # 全队贯穿（加成纯自身）
        if st[0] == "Command" and c[0] == "ShowEffect" and "transform" in json.dumps(c[2]):
            continue                                   # 化龙演出挪到 Fever
        if st[0] == "Command" and c[0] == "FindAllSubjects" and c[2] == 49:
            body = []
            k = 0
            for b in c[-1][1]:
                bc = b[1]
                if b[0] == "Command" and bc[0] in ("DeleteCondition", "CreateCondition"):
                    continue
                if b[0] == "Event" and bc[0] == "Wait":
                    atk = bc[3][1][0][1]
                    assert atk[0] == "CreateNormalAttack"
                    if atk[2] == 3:
                        continue                       # 雷段
                    assert atk[2] == 2
                    atk = copy.deepcopy(atk)
                    atk[2] = 255                       # 随角色属性（水）
                    atk[6] = V(*mults[k]); k += 1
                    body.append(["Event", ["Wait", bc[1], bc[2], ["Block", [["Command", atk]]]]])
                    continue
                body.append(b)
            assert k == len(mults), (k, mults)
            c = copy.deepcopy(c); c[-1] = ["Block", body]
            out.append(["Command", c])
            continue
        out.append(st)
    if enhance:
        for st in out:                                    # 敌方 FindAll(49) 块尾追加强化分支
            c = st[1]
            if st[0] == "Command" and c[0] == "FindAllSubjects" and c[2] == 49:
                sid = c[1]
                then = [cmd("CreateCondition", sid, [["ACPowerFlipDamageResistance", V(ENH_FRAMES), V(-0.15), V(1)]], V(1),
                            ["GenericConditionHitEffect"], True, False, "", None, False, 3, V(1), True),
                        cmd("CreateCondition", sid, [["ACToleranceOfElement", V(ENH_FRAMES), 2, V(-0.15), V(1)]], V(1),
                            ["GenericConditionHitEffect"], True, False, "", None, False, 3, V(1), True)]
                c[-1][1].append(cmd("ConditionalsChangeSkillFlag", 1, ["Block", then], ["Block", []]))
                break
        else:
            raise AssertionError("no enemy FindAll")
    if add_combo:
        out.append(cmd("AddCombo", V(add_combo)))
    t[11] = ["Block", out]
    return t


def dash_tree(mult, label):
    """冲刺「龙翼冲撞」：照基诺维 ability_skill_ginovi_dash 骨架——骑球判定区（朝最近敌人），命中才打；
    官方 FindNear 兜底是 CreateImaginaryTarget，不能直接对它 CreateNormalAttack（ImaginaryTarget.isHostile 崩 U_db830c）。"""
    hit = ["Block", [cmd("ShakeCamera", 2),
                     cmd("ShowEffect", label, ["SpecifyEffectDirectly",
                                               "battle/effect/powerflip/effect_powerflip_attack_special/powerflip_attack_special_three"],
                         9002, ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"], ["AB"], 0, 0, 0, False, False, ["Some", V(3)]),
                     cmd("CreateNormalAttack", 9002, 255, [], [], 0, V(mult), V(0), True, False, False, False, False,
                         V(0.25), V(1), ["None"], True)]]
    area = cmd("CreateHitArea", "*", -18, ["GH", 0], 0, -85, 0, True, False, ["Circle", V(220)], ["Center"], ["Center"],
               ["Single"], ["SpecifyHitAreaLifetimeDirectly", 20], ["CalculatedUsingMaxNumOfHits", 1], ["None"], False, True,
               ["None"], 9000, ["Block", []], 9001, 9002, hit, 0, 0, ["None"])
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, PF3_BTA, ["Block", [
        cmd("FindNearSubjects", -18, 1, 49, ["CreateImaginaryTarget", -1000000], 0, ["Block", [area]])]]]


def checks(p, t):
    probs = W.dsl_signature_problems(t)
    probs += L.action_dsl_subject_binding_problems(t)
    probs += L.action_dsl_lookup_scope_problems(t)
    probs += L.action_dsl_hit_area_target_problems(t)
    probs += L.action_dsl_element_problems(t, 2)
    assert not probs, (p, probs)


def put_dsl(p, t, new=False):
    checks(p, t)
    enc = wf_dsl.encode_amf3(t)
    assert wf_dsl.parse_dsl(enc)["tree"] == t, p
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    data = co.compress(enc) + co.flush()
    lp = wf_dsl.dsl_logical(p)
    files[lp] = data
    if new:
        try:
            read_raw(lp); raise AssertionError(f"{lp} 已存在却按新文件写")
        except FileNotFoundError:
            new_files.append(lp)


FX = json.loads((HERE.parent / "fx" / "dsl_hooks.json").read_text("utf-8"))


def replace_show(t, label, node):
    n = 0
    for _p, c in commands(t, "ShowEffect"):
        if c[1] == label:
            c[:] = copy.deepcopy(node); n += 1
    assert n >= 1, label
    return t


def fx_human(t):
    return replace_show(t, "全体演出", FX["human_skill"]["node"])


def fx_dragon(t, transform=False):
    d = FX["dragon_skill"]
    replace_show(t, "龙形升空演出", d["flight"])
    for k in (1, 2, 3):
        key = "breath_1_auto" if (transform and k == 1) else f"breath_{k}"     # quiet 1015：化龙自动龙息整棵静音，只留化龙一声
        replace_show(t, f"龙息第{k}段", d[key])
    if transform:
        t[11][1].insert(0, ["Command", copy.deepcopy(FX["transform_on_fever_start"]["node"])])
    return t


def fx_dash(t, form):
    for _p, c in commands(t, "ShowEffect"):
        node = copy.deepcopy(FX["dash"][form]); node[3] = 9002      # 挂命中目标（判定区第三个号），不挂 FindNear 的 0（可能是虚拟目标）
        c[:] = node
    return t


WAVE_HITS = [(14, 15), (34, 15)]          # 海浪两段：帧, 倍率（对全体敌人，PF 动作内=强化弹射伤害）


def wave_hits():
    return cmd("FindAllSubjects", 9500, 49, [], [], [], [], [], ["DoNothing"], ["Block", [
        wait(f, [cmd("CreateNormalAttack", 9500, 255, [], [], 0, V(m), V(0), False, False, False, False, False,
                     V(2), V(3), ["Coarse"], True), cmd("ShakeCamera", 2)]) for f, m in WAVE_HITS]])


def fx_lv4(t, form):
    h = FX["pf_lv4"]
    blk = t[11][1]
    blk.insert(1, wave_hits())
    assert blk[0][1][0] == "SetPowerFilpSuppress"
    blk.insert(1, ["Command", copy.deepcopy(h[form])])
    blk.insert(2, ["Command", copy.deepcopy(h["red_bolt_at_ball"])])
    return t


# 技能（每档倍率：[SLv1, 满级]）
SKILL_H = {"1": [(8, 8), (8, 8), (8, 8)], "2": [(8, 10), (8, 10), (8, 10)]}          # 人形 24 / 24→30
SKILL_D = {"1": [(8, 8), (12, 12), (16, 16)], "2": [(8, 10), (12, 15), (16, 20)]}    # 龙形 36 / 36→45


def build_dsls():
    for lv, p in (("1", P_H1), ("2", P_H2)):
        t = fx_human(water_only(dsl_tree(p), SKILL_H[lv])); put_dsl(p, t)
    for lv, p in (("1", P_D1), ("2", P_D2)):
        t = fx_dragon(water_only(dsl_tree(p), SKILL_D[lv], add_combo=30)); put_dsl(p, t)
    put_dsl(P_BREATH, fx_dragon(water_only(dsl_tree(P_D2), SKILL_D["2"], enhance=False), transform=True), new=True)   # 化龙演出＋自动龙息，不加连击
    put_dsl(P_REVERT, copy.deepcopy(FX["revert_on_fever_end_optional"]["tree"]), new=True)              # Fever 结束回龙人演出
    put_dsl(P_DASH_H, fx_dash(dash_tree(4, "龙翼冲撞"), "human"), new=True)
    put_dsl(P_DASH_D, fx_dash(dash_tree(8, "龙翼冲撞・真龙"), "dragon"), new=True)
    for lv in (1, 2, 3):
        put_dsl(pfp(K_HUMAN, lv), PF.compose(PF.TYPES_HUMAN, lv))
        put_dsl(pfp(K_DRAGON, lv), PF.compose(PF.TYPES_DRAGON, lv))
    put_dsl(pfp(K_DRAGON4, 3), fx_lv4(PF.compose(PF.TYPES_DRAGON, 3, lv4=True), "dragon"), new=True)
    LOG.append("DSL：人形技能 24/24→30、龙形 36/36→45（+30 连击）、自动龙息 45、冲撞 4/8、PF 两套 lv1-3 + 两棵 Lv4，根头 133（PF3 完整结算）")


# ================================================================== 词条行
AB, LE = flat(AB_LP), flat(LE_LP)


def clone(table, key, i, edits, expect=None):
    r = list((AB if table == "A" else LE)[key][i])
    for c, v in edits.items():
        r[c] = v
    want = 126 if table == "A" else 124
    assert len(r) == want
    if expect:
        d = D.describe_line(r, "ability" if table == "A" else "leader_ability")
        assert expect in d, (expect, d)
    return r


CLR_PRE_A = {6: "0", 7: "", 8: "", 9: "", 10: "", 11: "", 12: "", 13: "0", 14: "", 15: "", 16: "", 17: "", 18: "", 19: "", 20: "0"}
CLR_PRE_L = {4: "0", 5: "", 6: "", 7: "", 8: "", 9: "", 10: "", 11: "0", 12: "", 13: "", 14: "", 15: "", 16: "", 17: "", 18: "0"}
LIVE_A3 = AB["1299993"]
LIVE_LE = LE[CID]


def ab(sid, flag, rows_):
    for r in rows_:
        r[0], r[1] = sid, flag
    return rows_


def build_rows():
    A = {}
    # A1 龙王血脉：开局技能槽 +50%、强化弹射伤害 +100%、开技能 Fever +35%、队长：PF Lv3 / Fever 结束回槽
    A["1299991"] = ab("seris_dragon_king_1", "true", [
        clone("A", "1211771", 0, {**CLR_PRE_A, 51: "25000", 52: "50000"}, "技能槽"),
        clone("A", "1110011", 0, {51: "50000", 52: "100000"}, "强化弹射伤害"),
        clone("A", "1399956", 1, {**CLR_PRE_A, 6: "186", 27: "23", 30: "100000", 31: "100000", 35: "0",
                                  51: "35000", 52: "35000"}, "Fever槽增减"),
        clone("A", "1399956", 1, {**CLR_PRE_A, 6: "42", 13: "186", 27: "65", 30: "100000", 31: "100000", 35: "120",
                                  51: "5000", 52: "5000"}, "Fever槽增减"),
        clone("A", "1399956", 1, {**CLR_PRE_A, 6: "42", 27: "184", 30: "100000", 31: "100000", 35: "0",
                                  51: "30000", 52: "30000"}, "Fever槽增减"),
    ])
    # A2 潮翼疾驰：冲刺速度 +30%（不缩冷却）、冲刺连击 +8（CT1s）、龙人形冲刺 Fever +2%（CT2s）
    A["1299992"] = ab("seris_dragon_king_2", "true", [
        clone("A", "1699991", 2, {113: "30000", 114: "30000", 118: "1"}, "冲刺参数"),
        clone("A", "1699991", 2, {113: "50000", 114: "50000", 118: "6"}, "冲刺参数"),      # 可冲刺高度 +50%（作者 10-15 选 3）
        clone("A", "1399953", 5, {**CLR_PRE_A, 35: "60", 51: "800000", 52: "800000"}, "追加连击"),
        clone("A", "1399956", 1, {**CLR_PRE_A, 6: "186", 27: "4", 30: "100000", 31: "100000", 35: "120",
                                  51: "2000", 52: "2000"}, "Fever槽增减"),
    ])
    # A3 龙王显现（主位）：龙形攻/PF +100%、进 Fever 化龙＋自动龙息、Fever 结束回龙人、龙人形每 15 秒 Fever +15%
    a31 = list(LIVE_A3[1]); a31[113] = a31[114] = "300000"; a31[110], a31[111] = "0", ""      # 目标改自身
    a32 = list(LIVE_A3[2]); a32[109] = "23"; a32[113] = a32[114] = "300000"; a32[110], a32[111] = "0", ""
    a33 = list(a32); a33[109] = "413"; a33[113] = a33[114] = "15000"                           # 强化弹射独立乘区 +15%
    A["1299993"] = ab("seris_dragon_king_3", "false", [
        a31, a32, a33,
        clone("A", "1399953", 8, {**CLR_PRE_A, 68: UID_DRAGON}, "状态固有"),
        clone("A", "1199893", 3, {68: UID_DRAGON}, "Delete固有状态"),
        clone("A", "1699993", 3, {**CLR_PRE_A, 27: "184", 34: "(None)", 35: "0", 70: "ability_skill_seris_revert", 71: P_REVERT},
              "发动技能动作"),
        clone("A", "1699993", 3, {**CLR_PRE_A, 27: "8", 34: "(None)", 35: "0", 70: "ability_skill_seris_breath", 71: P_BREATH},
              "发动技能动作"),
        clone("A", "1399956", 1, {**CLR_PRE_A, 6: "186", 27: "77", 30: "90000000", 31: "90000000", 35: "0",
                                  51: "15000", 52: "15000"}, "Fever槽增减"),
    ])
    # A4 苍潮连击：连击 ≥50 / ≥100 各 +50% 强化弹射伤害
    A["1299994"] = ab("seris_dragon_king_4", "true", [
        clone("A", "1410012", 0, {100: "5000000", 101: "5000000", 109: "23", 113: "25000", 114: "50000"}, "连击≥50"),
        clone("A", "1410012", 0, {100: "10000000", 101: "10000000", 109: "23", 113: "25000", 114: "50000"}, "连击≥100"),
    ])
    # A5 龙翼冲撞：冲刺时对最近敌人 PF 伤害 4 倍 / 龙形 8 倍（CT2s）
    A["1299995"] = ab("seris_dragon_king_5", "true", [
        clone("A", "1699993", 3, {**CLR_PRE_A, 6: "186", 27: "4", 34: "(None)", 35: "120", 70: "ability_skill_seris_dash_h", 71: P_DASH_H},
              "发动技能动作"),
        clone("A", "1699993", 3, {**CLR_PRE_A, 6: "12", 27: "4", 34: "(None)", 35: "120", 70: "ability_skill_seris_dash_d", 71: P_DASH_D},
              "发动技能动作"),
    ])
    # A6 潮汐共鸣：自身强化弹射伤害 +50%、Fever 获得量 +30%
    A["1299996"] = ab("seris_dragon_king_6", "true", [
        clone("A", "1110011", 0, {51: "25000", 52: "50000"}, "强化弹射伤害"),
        clone("A", "3210055", 0, {51: "15000", 52: "30000"}, "Fever点"),
    ])
    # 队长技
    sid = LIVE_LE[0][0]
    l_dragon, l_human = list(LIVE_LE[7]), list(LIVE_LE[8])
    assert l_dragon[118] == K_DRAGON and l_human[118] == K_HUMAN and l_dragon[119] == l_human[119] == "1,2,3"
    l_dragon4, l_human4 = list(l_dragon), list(l_human)
    l_dragon4[118], l_dragon4[119] = K_DRAGON4, "4"
    # 作者 10-15：Lv4 保持挂真龙形（固有 22）
    l_human4[118], l_human4[119] = K_HUMAN4, "4"
    LEAD = [
        clone("L", "119997", 0, {66: UID_TIDE, 49: "100000", 50: "100000"}, "状态固有"),   # 苍海龙域标记：APK v32g 据此把 Fever 箭头换成随机道具
        clone("L", "139995", 0, {**CLR_PRE_L, 49: "100000", 50: "100000"}, "Fever点"),
        clone("L", "251001", 1, {108: "0", 109: "", 111: "350000", 112: "350000"}, "攻击力"),
        clone("L", "251001", 1, {107: "23", 108: "0", 109: "", 111: "450000", 112: "450000"}, "强化弹射伤害"),
        clone("L", "121177", 2, {**CLR_PRE_L, 49: "4000000", 50: "4000000", 60: "(None)"}, "连击加成"),
        clone("L", "121177", 5, {**CLR_PRE_L, 49: "300000", 50: "300000"}, "追加连击"),
        clone("L", "121189", 2, {68: "change_skill_seris_dragon_king"}, "切换技能形态"),   # 水共鸣：技能强化（旗号 1）
        l_dragon4, l_dragon, l_human,                      # Lv4 只挂真龙形（=Fever 中，作者 10-15）；平时两行照旧
    ]
    for r in LEAD:
        r[0] = sid
    return A, LEAD


# ================================================================== 文案
SKILL_H_NAME, SKILL_D_NAME = "苍海潮涌", "龙王吐息・苍潮"
SKILL_H_TXT = "对全体敌人造成3段水属性伤害（伤害量以强化弹射伤害判定）"
LEADER_TXT = NL.join([
    "自身Fever获得量＋100％",
    "进入FEVER模式时化身「真龙」，FEVER模式结束时恢复「龙人」形态",
    "FEVER模式中，自身攻击力＋350％，强化弹射伤害＋450％",
    "水属性共鸣时，为『苍海潮涌』与『龙王吐息・苍潮』追加「强制赋予敌人强化弹射抗性降低」与「强制赋予敌人水属性抗性降低」",
    "FEVER模式开始时，赋予自身「连击加成」（拍板后连击数保底40）",
    "弹射时，连击＋3",
    "FEVER模式中，场地上的加速箭头变为随机道具",
    "赋予特殊强化弹射效果：龙人形态同时发动射击型与特殊型强化弹射；真龙形态同时发动剑士、格斗、射击、辅助、特殊五种强化弹射",
    "解放强化弹射Lv4：FEVER模式中，弹射瞬间连击数在100以上时，强化弹射升级为Lv4「苍海怒涛」，范围与威力大幅提升，掀起的海浪对冲刷到的敌人追加2段强化弹射伤害",
])
MAIN = " <icon id='main'>  "
ABIL_TXT = {
    1: [f"战斗开始时，自身技能槽＋50％", "强化弹射伤害＋100％", "非FEVER模式中，发动技能时，FEVER槽＋35％",
        "自身为队长且非FEVER模式中，发动强化弹射Lv3时，FEVER槽＋5％（CT：2秒）", "自身为队长时，FEVER模式结束时，FEVER槽＋30％"],
    2: ["自身冲刺速度提升，可冲刺的高度范围扩大", "冲刺时，连击＋8（CT：1秒）", "非FEVER模式中，冲刺时FEVER槽＋2％（CT：2秒）"],
    3: [MAIN + "「真龙」形态中，自身攻击力＋300％，强化弹射伤害＋300％，强化弹射伤害＋15％（独立乘区）",
        MAIN + "化身「真龙」时，发动「龙王吐息・苍潮」（不消耗技能槽）",
        MAIN + "「龙人」形态中，每经过15秒，FEVER槽＋15％"],
    4: ["连击数50以上时，强化弹射伤害＋50％", "连击数100以上时，强化弹射伤害再＋50％"],
    5: ["冲刺时，对距离最近的敌人造成自身攻击4倍威力的水属性伤害；「真龙」形态中改为8倍（伤害量以强化弹射伤害判定，CT：2秒）"],
    6: ["强化弹射伤害＋50％", "自身Fever获得量＋30％"],
}


INVOKE_TXT = {
    "change_skill_seris_dragon_king": "为『苍海潮涌』与『龙王吐息・苍潮』追加「强制赋予敌人强化弹射抗性降低」与「强制赋予敌人水属性抗性降低」",
    "ability_skill_seris_breath": "化身「真龙」时发动「龙王吐息・苍潮」",
    "ability_skill_seris_dash_h": "冲刺时发动「龙翼冲撞」",
    "ability_skill_seris_dash_d": "「真龙」形态中，冲刺时发动「龙翼冲撞」",
    "ability_skill_seris_revert": "FEVER模式结束时恢复「龙人」形态",
}


def csv_cell(text):
    return join([text]) + NL


# ================================================================== 汇编
def raw_edit(lp, edits, appends=()):
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        om.rows[om.keys.index(k)] = q.build_node(node)
    for k, node in appends:
        assert k not in om.keys, k
        om.keys.append(k); om.rows.append(q.build_node(node))
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys[:len(keys0)] == keys0
    changed = [i for i in range(len(rows0)) if back.rows[i] != rows0[i]]
    assert changed == sorted(keys0.index(k) for k in edits if q.build_node(edits[k]) != rows0[keys0.index(k)]), lp
    files[lp] = out
    LOG.append(f"{lp}：改 {sorted(edits)}，新增 {[k for k, _ in appends]}")


def write_server(path_out):
    """服务端 cdndata/character_text.json：只替换 129999 一条（文件格式两空格缩进、LF，逐字节保留其余）。"""
    src = Path(os.environ.get("SERIS_SRV_BASE", KULO / "assets/cdndata/character_text.json"))   # 叠在上游同批服务端改动之上
    s = src.read_text("utf-8")
    j = json.loads(s)
    tx = rows(load(TX_LP)[CID])[0] if TX_LP not in files else rows(q.parse_node(files[TX_LP])[CID])[0]
    if NL not in s.strip():                           # 紧凑单行格式（上游构建器输出）：整体重排须与原文逐字一致
        assert json.dumps(json.loads(s), ensure_ascii=False, separators=(",", ":")) == s.rstrip(NL)
        j = json.loads(s); j[CID] = [tx]
        out = json.dumps(j, ensure_ascii=False, separators=(",", ":")) + (NL if s.endswith(NL) else "")
        path_out.parent.mkdir(parents=True, exist_ok=True)
        path_out.write_text(out, "utf-8")
        return hashlib.sha256(out.encode("utf-8")).hexdigest()
    i = s.index('"129999": [')
    k = s.index(NL + "  ]", i) + len(NL + "  ]")
    block = '"129999": ' + json.dumps([tx], ensure_ascii=False, indent=2).replace(NL, NL + "  ")
    out = s[:i] + block + s[k:]
    jo, jn = json.loads(s), json.loads(out)
    assert set(jo) == set(jn) and [x for x in jo if jo[x] != jn[x]] in ([CID], []) and jn[CID] == [tx]
    path_out.parent.mkdir(parents=True, exist_ok=True)
    path_out.write_text(out, "utf-8")
    return hashlib.sha256(out.encode("utf-8")).hexdigest()


# ================================================================== 美术（立绘/图标/cut-in；像素另附）
ART_MANIFEST = HERE.parent / "portrait" / "final" / "manifest.json"
raw_members: dict[str, bytes] = {}          # 直接按 production/<root>/<盐路径> 落包的资源
raw_lps: dict[str, str] = {}


def amember(root, lp):
    h = hashlib.sha1((lp + SALT).encode()).hexdigest()
    return f"production/{root}/{h[:2]}/{h[2:]}"


def add_asset(root, lp, data):
    m = amember(root, lp)
    assert m not in raw_members or raw_members[m] == data, m
    raw_members[m] = data; raw_lps[m] = lp


def build_art():
    man = json.loads(ART_MANIFEST.read_text("utf-8"))
    n = 0
    for f in man["files"]:
        data = Path(f["local"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == f["sha256"], f["logical"]
        for r in f["roots"]:
            add_asset(r, f["logical"], data); n += 1
    CI_LP, TR_LP = "master/generated/character_image.orderedmap", "master/generated/trimmed_image.orderedmap"
    CI, TR = load(CI_LP), load(TR_LP)
    ci = copy.deepcopy(CI[CID]); tr_ed = {}
    for e in man["table_edits"]:
        k1 = e["character_image"]["key"][1]
        assert ci[k1].rstrip(NL) == e["character_image"]["old"], (ci[k1], e)
        ci[k1] = e["character_image"]["new"] + (NL if ci[k1].endswith(NL) else "")
        tk = e["trimmed_image"]["key"]
        assert TR[tk].rstrip(NL) == e["trimmed_image"]["old"], (TR[tk], e)
        tr_ed[tk] = e["trimmed_image"]["new"] + (NL if TR[tk].endswith(NL) else "")
        assert e["full_shot_image_attribute"]["old"] == e["full_shot_image_attribute"]["new"]
    raw_edit(CI_LP, {CID: ci})
    raw_edit(TR_LP, tr_ed)
    LOG.append(f"美术：立绘/图标/cut-in {len(man['files'])} 个逻辑文件、{n} 个根成员；character_image/trimmed_image 按新图定位")


PIXEL_DIR = os.environ.get("SERIS_PIXEL_DIR")   # 选定后的像素套件目录（main + special），未选时不打包


def build_pixel():
    if not PIXEL_DIR:
        LOG.append("像素：未指定 SERIS_PIXEL_DIR，沿用旧像素"); return
    man = json.loads((Path(PIXEL_DIR) / "drop_manifest.json").read_text("utf-8"))
    for f in man["files"]:
        data = Path(f["local"]).read_bytes()
        for r in f["roots"]:
            add_asset(r, f["logical"], data)
    LOG.append(f"像素：{len(man['files'])} 个文件（{PIXEL_DIR}）")


def build_fx():
    man = json.loads((HERE.parent / "fx" / "drop_manifest.json").read_text("utf-8"))
    for f in man["files"]:
        data = Path(f["local"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == f["sha256"], f["logical"]
        for r in f["roots"]:
            add_asset(r, f["logical"], data)
        if not existing_roots(f["logical"]):
            new_files.append(f["logical"])
    LOG.append(f"特效：{len(man['files'])} 个文件")


VOICE_DIR = Path(os.environ.get("SERIS_VOICE_DIR", r"D:/WF/角色语音/赛瑞斯重做v2_20261015"))   # v2 = Argon 台词 + 情绪化 Seed Audio（作者 10-15「台词可以」）
ROOTS = ("upload", "medium_upload", "android_upload", "ios_upload")


def existing_roots(lp):
    out = []
    for r in ROOTS:
        m = amember(r, lp)
        import base149 as _b
        if m in _b._INDEX or (STORE131.parent / m.split("production/")[1]).exists():
            out.append(r)
    return out


HOME_NAMES = ["human_form", "storm", "memory", "courage", "true_form", "tea"]   # 线上 character_speech 已注册的主页文件名


def build_voice():
    if os.environ.get("SERIS_NO_VOICE"):
        LOG.append("语音：跳过"); return
    plan = json.loads((VOICE_DIR / "plan-seris.json").read_text("utf-8"))
    SP_LP = "master/character/character_speech.orderedmap"
    sp = rows(load(SP_LP)[CID]); sp = [r for r in sp if r]
    by_path = {r[4]: r for r in sp}
    n, new_slots = 0, []
    for x in plan:
        slot = x["slot"]
        import wf_assets
        data = wf_assets.mp3_encode((VOICE_DIR / "final" / (slot + ".mp3")).read_bytes())   # 存储态：帧同步字改写，客户端解码还原
        sub = x["zh"].replace(NL, "")
        if slot.startswith("home/home_"):
            name = "home/" + HOME_NAMES[int(slot.rsplit("_", 1)[1])]
        else:
            name = slot
        lp = f"character/{CODE}/voice/{name}.mp3"
        if name in by_path:
            by_path[name][3] = sub                      # 字幕跟新台词
        rs = existing_roots(lp) or ["upload"]
        if not existing_roots(lp):
            new_slots.append(lp); new_files.append(lp)
        for r in rs:
            add_asset(r, lp, data); n += 1
    assert all(r[4] in by_path for r in sp) and len([r for r in sp if r[4].startswith("home/")]) == 6
    raw_edit(SP_LP, {CID: join_rows(sp) + NL})
    LOG.append(f"语音：{len(plan)} 条，{n} 个根成员；主页 6 条沿用线上注册名换音频＋字幕；新增文件 {new_slots}")


def main(argv):
    frm, to = argv[argv.index("--from") + 1], argv[argv.index("--to") + 1]
    assert TIP + len([z for z in os.environ.get("WF_EXTRA_ZIPS", "").split(";") if z]) == int(frm.split(".")[-1]), (TIP, frm)
    build_dsls()
    A, LEAD = build_rows()
    probs = []
    CAS_KEYS = set(load(CAS_LP)) | set(INVOKE_TXT)
    for k, rs in A.items():
        for r in rs:
            probs += [f"{k}: {x}" for x in L.client_legality_problems("ability", r) + L.declared_block_field_problems("ability", r)
                      + L.invoke_skill_string_problems(r, CAS_KEYS)]
            probs += [f"{k}: {x}" for x in L.ability_element_column_problems(r, "ability")] if False else []
    for r in LEAD:
        probs += [f"L: {x}" for x in L.client_legality_problems("leader_ability", r) + L.declared_block_field_problems("leader_ability", r)]
    assert not probs, NL.join(probs)
    for k, rs in A.items():
        assert len(rs) <= 9, (k, len(rs))
        for r in rs:
            LOG.append(f"  {k} " + D.describe_line(r, "ability"))
    for r in LEAD:
        LOG.append(f"  L " + D.describe_line(r, "leader_ability"))
    raw_edit(AB_LP, {k: join_rows(rs) + NL for k, rs in A.items()})
    raw_edit(LE_LP, {CID: join_rows(LEAD) + NL})

    # action_skill / switched
    AS = load(AS_LP); g = copy.deepcopy(AS[CODE])
    for lv, nm in (("1", SKILL_H_NAME), ("2", SKILL_H_NAME + "＋")):
        r = row(g[lv]); r[0], r[1] = nm, SKILL_H_TXT; assert r[3] == "true" and r[4] == r[5] == "520", r[:6]; r[4] = r[5] = "480"
        g[lv] = join(r) + (NL if g[lv].endswith(NL) else "")
    raw_edit(AS_LP, {CODE: g})
    SW = load(SW_LP); s = copy.deepcopy(SW[CODE])
    raw_edit(SW_LP, {CODE: s})                         # 龙形技能槽沿用（数据格式先不动，SP 调整另核 switched 解析）
    # power_flip_action：两个 Lv4 新键
    raw_edit(PFA_LP, {}, appends=[
                                   (K_DRAGON4, ",".join([EMPTY, EMPTY, pfp(K_DRAGON4, 3)]))])
    # unique 22 时长
    U = load(UC_LP); u = rows(U[UID_DRAGON])[0]; assert u[3] == "1500"; u[3] = "3600"
    tide = ["fever:items:hp_recovery_small|skill_charge_middle|accumulation_attack_power_up_25_500|condition_piercing:seris", "苍海龙域", "battle/common/unique_condition/unique_seris_dragon_king",
            "99999999", "2", "(None)", "(None)", "(None)", "(None)", "false", "true", "0", "0", "false", "(None)"]
    assert len(tide) == len(u)
    raw_edit(UC_LP, {UID_DRAGON: join(u) + (NL if U[UID_DRAGON].endswith(NL) else "")},
             appends=[(UID_TIDE, join(tide) + NL)] if UID_TIDE not in U else ())
    # character_text
    TX = load(TX_LP); tx = rows(TX[CID])[0]
    tx[2] = "统御苍海的古龙之王。平日以银鳞龙人的姿态行走于人世；当战意沸腾到极点，便显露翼龙真身，以万潮肃清战场。"
    tx[4], tx[5], tx[6], tx[7] = SKILL_H_NAME, SKILL_H_TXT, SKILL_H_NAME + "＋", SKILL_H_TXT
    raw_edit(TX_LP, {CID: join(tx) + (NL if TX[CID].endswith(NL) else "")})
    # 面板覆盖
    CAS = load(CAS_LP)
    ed, ap = {}, []
    for k, txt in list(INVOKE_TXT.items()) + [(f"desc_override_{LE[CID][0][0]}", LEADER_TXT)] + [(f"desc_override_{CODE}_{n}", NL.join(v)) for n, v in ABIL_TXT.items()]:
        (ed.__setitem__(k, csv_cell(txt)) if k in CAS else ap.append((k, csv_cell(txt))))
    raw_edit(CAS_LP, ed, ap)

    build_art()
    build_pixel()
    build_voice()
    build_fx()
    print(NL.join(LOG))
    members = {member(lp): d for lp, d in files.items()}
    for m, d in raw_members.items():
        assert m not in members, m
        members[m] = d
    name = f"pinball-{frm}-{to}-1-seris-rework-local.zip"
    print(f"{'WRITE' if '--write' in argv else 'DRY RUN'}: {name} members={len(members)} new={len(new_files)}")
    if "--write" not in argv:
        return 0
    OUTDIR.mkdir(exist_ok=True)
    CAP = 5 * 1024 * 1024 - 64 * 1024                     # CI 单包 5MiB 门禁，留余量
    est = {m: len(zlib.compress(d, 6)) + 200 for m, d in members.items()}
    parts, cur, size = [], [], 0
    for m in sorted(members, key=lambda m: (-est[m], m)):  # 先放大件，贪心装箱
        for part in parts:
            if part[1] + est[m] <= CAP:
                part[0].append(m); part[1] += est[m]; break
        else:
            parts.append([[m], est[m]])
    names = [f"pinball-{frm}-{to}-{k + 1}-seris-rework-local.zip" for k in range(len(parts))]
    srv_sha = write_server(HERE.parent / "server/character_text.json")
    lps_all = {**{member(lp): lp for lp in sorted(files)}, **raw_lps}
    out = []
    for name, (mems, _) in zip(names, parts):
        path = OUTDIR / name
        assert not path.exists(), path
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for m in sorted(mems):
                zf.writestr(m, members[m])
        blob = path.read_bytes(); assert len(blob) <= 5 * 1024 * 1024, (name, len(blob))
        with zipfile.ZipFile(path) as zf:
            assert zf.testzip() is None and sorted(zf.namelist()) == sorted(mems)
        out.append({"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(mems),
                    "files": sorted(mems)})
        print(json.dumps(out[-1] | {"files": None}, ensure_ascii=False))
    integ = {"version": to, "applies_on": frm, "chain": names, "archive_integrity": out,
             "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": lps_all, "new_files": sorted(new_files),
             "server_files": {"assets/cdndata/character_text.json": {"copy": "server/character_text.json", "sha256": srv_sha}},
             "requires_client": ["damage-type-rules-v1", "dash-parameter-v1", "pf-lv4 (v32)"], "log": LOG}
    (OUTDIR / f"pinball-{frm}-{to}-seris-rework-local.integrity.json").write_text(
        json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

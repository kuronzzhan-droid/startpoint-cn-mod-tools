"""雷吉斯·海滨 139994：2026-09-27 作者确认的「能力相关都换成技能伤害」修订（纯函数）。

作者口径：能力相关都换成技能伤害；「合计造成 N 次能力伤害」的计数触发改成按发动技能计。
本模块只转换传入的自有行 / 文案 / DSL，不读写 live、候选或 assets；由批次暂存脚本调用
:func:`revise`，``wf_seasonal7_kit_regis.build`` 在浪涌修订（``wf_regis_surge_stages``）之后
调用同一组转换，重跑 kit 不会回退本次改动。

落点（行号 = 0 起的 CSV 下标）：

- 两档技能 DSL：根 ``tree[10]``（buffTargetAs）2→0、三个 ``CreateHitArea`` ``node[24]`` 2→0
  （来源本来就是 ActionSkill，0 = 自动 = 技能伤害）；雷队 ``CreateCondition`` 的
  ``ACAbilityDamage`` → ``ACSkillDamage``（持续 / 强度不变，两者构造签名相同）。
- 队长：持续「每层浪涌」c107 154→2；除自身雷队技能槽行 c25 144→23（技能发动），
  c28/c29 2000000→100000（1 次），puller c26=6 / Yellow / CT c33=300 保持。
- 能力 2 第 1 行：253（全体 20 倍雷能力伤害）→ 629 发动技能动作，c48/c51/c52/c69 置空，
  c70/c71 = 新文案键 / 新 DSL；触发 23+puller7 Yellow、CT300、共鸣前置保持；**不加 202**
  （作者选择保留副位效果；live 自制先例 1299921#0 / 1699894#1 / 1799822#1 / 1499885#1）。
- 新 629 DSL：官方 psychic_tomboygirl_2 的 FindAllSubjects(0,49) → CreateHitArea(Circle 10,
  寿命 2, 每敌 1 次) → CreateNormalAttack（元素显式 3 = 雷、20 倍、固定伤害 0、
  削韧 / Fever 各 1 = 原生能力伤害的 ABILITY_ATTACK_BASIC_*），复用包内光束命中特效；根 bta=0。
- 能力 3：Fever 独立乘区 412→411（雷队）；非Fever 回 Fever 槽行 c27 144→23、阈值
  1000000→100000；每层浪涌 c109 154→2；删除自身 411 行（与第 1 行合计会变成 +50%）。
- 能力 5：瞬发 388→34（限 10 次、10% 不变）。
- upskill:139994 c2/c8：ability_damage_up → skill_damage_up（= 母本 131020）。
- 面板 4 个覆盖键、技能描述三处（action_skill 两档 c1、character_text c5/c7、服务端镜像）。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

CID = "139994"
CODE = "rec_android_seaside"
PACKAGES = ["s7-regis"]
PACKAGE_VERSION = {"s7-regis": "1.0.7"}
CAPABILITIES: list[str] = []
UID = "13999401"
MAIN_ICON = " <icon id='main'>  "

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
TEXT = "master/character/character_text.orderedmap"
ACTION = "master/skill/action_skill.orderedmap"
UPSKILL = "master/mana_board/upskill.orderedmap"

SKILL_PROGRAMS = {lv: f"battle/action/skill/action/rare5/{CODE}${CODE}_{lv}" for lv in ("1", "2")}
STRIKE_KEY = f"{CODE}_skill_strike"
STRIKE_PROGRAM = f"battle/action/skill/action/ability_skill/{CODE}${STRIKE_KEY}"
STRIKE_TEXT = "对全体敌人造成20倍雷属性技能伤害"
HIT_EFFECT = "battle/effect/skill_unique/rec_android_seaside/seaside_beam/rec_android_1anv_beam_hit"
THUNDER_DSL = 3          # DSL 元素码 1-based：雷（内部 2）+1
STRIKE_MULTIPLIER = 20.0

OLD_DESCRIPTION = ("向最近的敌人发射光束，造成雷属性伤害（按能力伤害加成计算）"
                   "／「浪涌充能」达到3层、5层时提升光束形态，基础威力依次为50、75、100倍，每层额外＋15倍"
                   "／非FEVER模式中，增加FEVER槽并提升自身攻击力"
                   "／提升雷属性角色能力伤害")
DESCRIPTION = ("向最近的敌人发射光束，造成雷属性伤害"
               "／「浪涌充能」达到3层、5层时提升光束形态，基础威力依次为50、75、100倍，每层额外＋15倍"
               "／非FEVER模式中，增加FEVER槽并提升自身攻击力"
               "／提升雷属性角色技能伤害")

PANEL_KEYS = {"leader": f"desc_override_{CODE}", "2": f"desc_override_{CODE}_2",
              "3": f"desc_override_{CODE}_3", "5": f"desc_override_{CODE}_5"}
_LEADER_TAIL = ("雷属性共鸣时，FEVER时间－50%\n"
                "雷属性共鸣时，进入FEVER模式2秒后，自身技能槽＋25%、雷属性角色技能槽＋25%\n"
                "雷属性共鸣时，非FEVER模式中冲刺时FEVER槽＋10%；FEVER模式中冲刺时FEVER槽－10%\n"
                "FEVER模式结束时，自身「浪涌充能」＋1层")
PANEL_BEFORE = {
    PANEL_KEYS["leader"]: ("雷属性共鸣时，每层「浪涌充能」，雷属性角色能力伤害＋150%、攻击力＋100%\n"
                           "雷属性共鸣时，除自身外的雷属性角色合计造成20次能力伤害时，"
                           "除自身外的雷属性角色技能槽＋5%（CT：5秒）\n" + _LEADER_TAIL),
    PANEL_KEYS["2"]: ("雷属性共鸣时，雷属性角色发动技能时，对全体敌人造成20倍能力伤害（CT：5秒）\n"
                      "雷属性共鸣时，雷属性角色攻击力＋100%"),
    PANEL_KEYS["3"]: (MAIN_ICON + "雷属性共鸣时，FEVER模式中，雷属性角色能力伤害、自身技能伤害额外乘区＋25%\n"
                      + MAIN_ICON + "雷属性共鸣时，非FEVER模式中，雷属性角色合计造成10次能力伤害时，"
                      "FEVER槽＋10%（CT：5秒）\n"
                      + MAIN_ICON + "进入FEVER模式时，自身技能槽＋25%（CT：20秒）\n"
                      + MAIN_ICON + "每层「浪涌充能」，自身攻击力＋150%、能力伤害＋150%"),
    PANEL_KEYS["5"]: ("雷属性角色发动技能时，雷属性角色能力伤害＋10%（最多10次）\n"
                      "雷属性共鸣时，非FEVER模式中，雷属性角色技能充能速度＋10%"),
}
PANEL_AFTER = {
    PANEL_KEYS["leader"]: ("雷属性共鸣时，每层「浪涌充能」，雷属性角色技能伤害＋150%、攻击力＋100%\n"
                           "雷属性共鸣时，除自身外的雷属性角色发动技能时，"
                           "除自身外的雷属性角色技能槽＋5%（CT：5秒）\n" + _LEADER_TAIL),
    PANEL_KEYS["2"]: ("雷属性共鸣时，雷属性角色发动技能时，对全体敌人造成20倍雷属性技能伤害（CT：5秒）\n"
                      "雷属性共鸣时，雷属性角色攻击力＋100%"),
    PANEL_KEYS["3"]: (MAIN_ICON + "雷属性共鸣时，FEVER模式中，雷属性角色技能伤害额外乘区＋25%\n"
                      + MAIN_ICON + "雷属性共鸣时，非FEVER模式中，雷属性角色发动技能时，FEVER槽＋10%（CT：5秒）\n"
                      + MAIN_ICON + "进入FEVER模式时，自身技能槽＋25%（CT：20秒）\n"
                      + MAIN_ICON + "每层「浪涌充能」，自身攻击力＋150%、技能伤害＋150%"),
    PANEL_KEYS["5"]: ("雷属性角色发动技能时，雷属性角色技能伤害＋10%（最多10次）\n"
                      "雷属性共鸣时，非FEVER模式中，雷属性角色技能充能速度＋10%"),
}

# revise() 的输入基线（live 1.4.1047 = s7-regis 1.0.6；零漂移，见调研 regis.txt）。
BEFORE = {
    ("leader", CID): "0a3805bc77c01b9c3c09b24cf3d0716ae583e432731297feb3f31699db32c637",
    ("ability", CID + "2"): "404001d627d04bb751ee791091aa517c1b4462998b8675ee906c8a67294c1107",
    ("ability", CID + "3"): "27734dd1f523dc9b77c19795cae3b38087d0cfa2643320a0c72328e7011bc8eb",
    ("ability", CID + "5"): "f78f5b7027d427ecfd7069f9a19627c94f4a8c71542e1d26c152b274496c4634",
    ("cas", PANEL_KEYS["leader"]): "b35e7122134d6b7339f2feca569db43a642dfcc1d9ad9251c0fe2117db4f4540",
    ("cas", PANEL_KEYS["2"]): "7654ed3073eab861ed9c5788fbe23ac49114fb6352c532edc0ef60ba8ad0d935",
    ("cas", PANEL_KEYS["3"]): "7fe49c63cadd831cf0023d5c7cc464455835c70f931dea710da716c06ef83f09",
    ("cas", PANEL_KEYS["5"]): "ef5a64fe42cf5bc62981c552351d537bdf029fb3143b92b92439ea5bf48be4d0",
    ("text", CID): "ea8c131721d046289fdbb25cfd472a23ccd3736d550a0173cc08ade84f1fe45f",
    ("table", (UPSKILL, CID)): "815bd7b7fd2391015a365417a9f24cfdb46afca4b83e467218defc221760be4f",
    ("action", CODE): "9784c9746c1000a5626d10a8a806b1eab2b05e9d722b451abd979c702e99ac18",
    ("dsl", SKILL_PROGRAMS["1"]): "0bd283a54760d7cb3657e91f7fa32758c88d18aafd119f2ccf5f680343fde94b",
    ("dsl", SKILL_PROGRAMS["2"]): "15a094bb24dd7cd39bd5fa1c466c0e35601a6a9c4b60ab5e852d667cc213e43f",
    ("server_text", CID): "ea8c131721d046289fdbb25cfd472a23ccd3736d550a0173cc08ade84f1fe45f",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


# ---------------------------------------------------------------- 行

def _width(rows, width: int, label: str):
    if not rows or any(len(r) != width for r in rows):
        raise ValueError(f"unexpected {label} row width")


def _one(rows, pred, label: str) -> list[str]:
    hits = [r for r in rows if pred(r)]
    if len(hits) != 1:
        raise ValueError(f"expected exactly one {label} row, found {len(hits)}")
    return hits[0]


def _count_trigger(row, kind_col: int, lo: int, before: str, label: str):
    state = (row[kind_col], row[lo], row[lo + 1])
    if state not in (("144", before, before), ("23", "100000", "100000")):
        raise ValueError(f"{label} trigger drift: {state}")
    row[kind_col] = "23"                 # SkillInvoke：只数真正的主动技能释放，629 不计
    row[lo:lo + 2] = ["100000", "100000"]


def leader_rows(rows):
    """队长：每层浪涌能力伤害→技能伤害；雷队技能槽行改按「除自身外雷属性角色发动技能」1 次触发。"""
    out = deepcopy(rows)
    _width(out, 124, "leader_ability")
    stack = _one(out, lambda r: r[3] == "1" and r[95] == "134" and r[102] == UID
                 and r[107] in ("154", "2") and r[108:110] == ["5", "Yellow"]
                 and r[111:113] == ["150000", "150000"], "leader per-stack damage")
    stack[107] = "2"                     # 持续 SkillDamage
    gauge = _one(out, lambda r: r[3] == "0" and r[25] in ("144", "23") and r[26:28] == ["6", "Yellow"]
                 and r[33] == "300" and r[45:48] == ["211", "1", "Yellow"], "leader skill-gauge")
    _count_trigger(gauge, 25, 28, "2000000", "leader skill-gauge")
    return out


def strike_rows(rows):
    """能力 2：253 全体雷能力伤害 → 629 发动技能动作（技能伤害）；不加 202，保留副位效果。"""
    out = deepcopy(rows)
    _width(out, 126, "ability 2")
    row = _one(out, lambda r: r[5] == "0" and r[6] == "2" and r[11] == "Yellow"
               and r[27:30] == ["23", "7", "Yellow"] and r[35] == "300"
               and r[47] in ("253", "629"), "ability 2 strike")
    if row[47] == "253":
        if (row[48], row[51], row[52], row[69], row[70], row[71]) != \
                ("0", "2000000", "2000000", "(None)", "", ""):
            raise ValueError("ability 2 native strike drift")
        row[47] = "629"
        row[48] = row[51] = row[52] = row[69] = ""
        row[70], row[71] = STRIKE_KEY, STRIKE_PROGRAM
    elif (row[48], row[51], row[52], row[69], row[70], row[71]) != \
            ("", "", "", "", STRIKE_KEY, STRIKE_PROGRAM):
        raise ValueError("ability 2 invoke row drift")
    return out


def third_rows(rows):
    """能力 3：412→411、144→23（1 次）、每层 154→2，删除重复的自身 411。"""
    out = deepcopy(rows)
    _width(out, 126, "ability 3")
    fever = _one(out, lambda r: r[5] == "1" and r[13] == "12" and r[109] in ("412", "411")
                 and r[110:112] == ["5", "Yellow"] and r[113:115] == ["25000", "25000"],
                 "ability 3 Fever separated term")
    fever[109] = "411"                   # 独立乘区 SkillDamage，雷队
    gauge = _one(out, lambda r: r[5] == "0" and r[13] == "186" and r[27] in ("144", "23")
                 and r[28:30] == ["7", "Yellow"] and r[35] == "300" and r[47] == "724",
                 "ability 3 Fever gauge")
    _count_trigger(gauge, 27, 30, "1000000", "ability 3 Fever gauge")
    stack = _one(out, lambda r: r[5] == "1" and r[97] == "134" and r[104] == UID
                 and r[109] in ("154", "2") and r[110] == "0"
                 and r[113:115] == ["150000", "150000"], "ability 3 per-stack damage")
    stack[109] = "2"                     # 持续 SkillDamage
    duplicate = [i for i, r in enumerate(out) if r[5] == "1" and r[13] == "12" and r[109] == "411"
                 and r[110] == "0" and r[113:115] == ["25000", "25000"]]
    if len(duplicate) > 1:
        raise ValueError("ambiguous self separated-skill rows")
    return [r for i, r in enumerate(out) if i not in duplicate]


def fifth_rows(rows):
    """能力 5：发动技能时雷队能力伤害 10%（限 10 次）→ 技能伤害。"""
    out = deepcopy(rows)
    _width(out, 126, "ability 5")
    row = _one(out, lambda r: r[5] == "0" and r[27:30] == ["23", "7", "Yellow"] and r[34] == "10"
               and r[47] in ("388", "34") and r[48:50] == ["5", "Yellow"]
               and r[51:53] == ["10000", "10000"], "ability 5 stacking bonus")
    row[47] = "34"                       # 瞬发 SkillDamage
    return out


def upskill_rows(rows):
    """升级预览标签恢复母本 131020 的 skill_damage_up。"""
    out = deepcopy(rows)
    if len(out) != 1 or len(out[0]) != 12:
        raise ValueError("unexpected upskill row shape")
    out[0] = ["skill_damage_up" if c == "ability_damage_up" else c for c in out[0]]
    if out[0].count("skill_damage_up") != 2:
        raise ValueError("upskill damage tags drift")
    return out


# ---------------------------------------------------------------- 文案

def description(text: str) -> str:
    if text not in (OLD_DESCRIPTION, DESCRIPTION):
        raise ValueError("skill description drift")
    return DESCRIPTION


def panel_text(key: str, text: str) -> str:
    if key not in PANEL_BEFORE:
        raise ValueError(f"unexpected panel key {key}")
    if text not in (PANEL_BEFORE[key], PANEL_AFTER[key]):
        raise ValueError(f"panel text drift: {key}")
    return PANEL_AFTER[key]


def text_rows(rows):
    out = deepcopy(rows)
    if len(out) != 1 or len(out[0]) != 12:
        raise ValueError("unexpected character_text row shape")
    out[0][5], out[0][7] = description(out[0][5]), description(out[0][7])
    return out


def action_rows(entries):
    out = []
    for inner, fields in entries:
        fields = list(fields)
        if len(fields) != 24 or fields[7] != SKILL_PROGRAMS.get(inner):
            raise ValueError(f"unexpected action_skill inner row {inner}")
        fields[1] = description(fields[1])
        out.append((inner, fields))
    if [k for k, _ in out] != ["1", "2"]:
        raise ValueError("action_skill inner keys drift")
    return out


# ---------------------------------------------------------------- DSL

def _commands(node, name):
    if isinstance(node, list):
        if node and node[0] == "Command" and len(node) == 2 and isinstance(node[1], list) \
                and node[1] and node[1][0] == name:
            yield node[1]
        for child in node:
            yield from _commands(child, name)


def skill_tree(tree):
    """技能本体改按技能伤害结算；雷队增益 ACAbilityDamage → ACSkillDamage。幂等。"""
    out = deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl"):
        raise ValueError("expected native ActionDsl")
    areas = list(_commands(out, "CreateHitArea"))
    buffs = [ac for c in _commands(out, "CreateCondition") for ac in c[2]
             if isinstance(ac, list) and ac and ac[0] in ("ACAbilityDamage", "ACSkillDamage")]
    state = (out[10], tuple(a[24] for a in areas), tuple(ac[0] for ac in buffs))
    if state not in ((2, (2, 2, 2), ("ACAbilityDamage",)), (0, (0, 0, 0), ("ACSkillDamage",))):
        raise ValueError(f"unreviewed Regis skill damage attribution: {state}")
    out[10] = 0
    for area in areas:
        area[24] = 0
    buffs[0][0] = "ACSkillDamage"
    return out


def strike_tree():
    """全体敌人各 1 次 20 倍雷属性技能伤害（629，根 bta=0）。"""
    slv = lambda v: [{"min": v, "max": v}]
    attack = ["CreateNormalAttack", 3, THUNDER_DSL, [], [], 0, slv(STRIKE_MULTIPLIER), slv(0),
              False, False, False, False, False, slv(1), slv(1), ["Coarse"], True]
    hit = ["ShowEffect", "hit", ["SpecifyEffectDirectly", HIT_EFFECT], 0, ["ForesideOfCharacter"],
           ["PlayOnlyFirstSequence"], ["AB"], 0, 0, 0, False, False, ["None"]]
    area = ["CreateHitArea", "*", 0, ["AB"], 0, 0, 0, True, True, ["Circle", slv(10)],
            ["Center"], ["Center"], ["Single"], ["SpecifyHitAreaLifetimeDirectly", 2],
            ["CalculatedUsingMaxNumOfHits", 1], ["Some", slv(1)], True, False, ["None"], 1,
            ["Block", []], 2, 3, ["Block", [["Command", attack]]], 0, 0, ["None"]]
    find = ["FindAllSubjects", 0, 49, [], [], [], [], [], ["DoNothing"],
            ["Block", [["Command", hit], ["Command", area]]]]
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
            ["Block", [["Command", find]]]]


# ---------------------------------------------------------------- 门禁

def row_problems(kind: str, rows) -> list[str]:
    import wf_client_legality as L
    probs = []
    for i, row in enumerate(rows):
        for p in (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
                  + L.invoke_skill_string_problems(row, {STRIKE_KEY}, kind)):
            probs.append(f"{kind}#{i}: {p}")
    return probs


def dsl_problems(tree) -> list[str]:
    import wf_client_legality as L
    import wf_dsl
    probs = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        probs.append("AMF3 roundtrip mismatch")
    probs += L.action_dsl_element_problems(tree, 2)
    probs += L.action_dsl_subject_binding_problems(tree)
    probs += L.action_dsl_lookup_scope_problems(tree)
    probs += L.action_dsl_hit_area_target_problems(tree)
    return probs


# ---------------------------------------------------------------- 批次入口

def revise(read) -> dict:
    live = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        if digest(value) != want:
            raise ValueError(f"live input drifted from the reviewed baseline: {kind}:{key}")
        live[kind, key] = deepcopy(value)
    leader = leader_rows(live["leader", CID])
    ability = {CID + "2": strike_rows(live["ability", CID + "2"]),
               CID + "3": third_rows(live["ability", CID + "3"]),
               CID + "5": fifth_rows(live["ability", CID + "5"])}
    probs = row_problems("leader_ability", leader)
    for rows in ability.values():
        probs += row_problems("ability", rows)
    dsl = {program: skill_tree(live["dsl", program]) for program in SKILL_PROGRAMS.values()}
    dsl[STRIKE_PROGRAM] = strike_tree()
    for program, tree in dsl.items():
        probs += [f"{program}: {p}" for p in dsl_problems(tree)]
    if probs:
        raise ValueError(probs)
    cas = {key: [[panel_text(key, live["cas", key][0][0])]] for key in PANEL_KEYS.values()}
    cas[STRIKE_KEY] = [[STRIKE_TEXT]]
    server = deepcopy(live["server_text", CID])
    server[0][5], server[0][7] = description(server[0][5]), description(server[0][7])
    return {
        "ability": ability,
        "leader": {CID: leader},
        "cas": cas,
        "text": {CID: text_rows(live["text", CID])},
        "table": {(UPSKILL, CID): upskill_rows(live["table", (UPSKILL, CID)])},
        "action": {CODE: action_rows(live["action", CODE])},
        "dsl": dsl,
        "server_text": {CID: server},
        "new_programs": [STRIKE_PROGRAM],
        "notes": {
            "request": "能力相关都换成技能伤害；计数触发改成按发动技能计（作者 2026-09-27 确认）",
            "skill_dsl": "tree[10] 2→0、CreateHitArea node[24] 2→0、ACAbilityDamage→ACSkillDamage",
            "leader": "c107 154→2；c25 144→23、c28/c29 2000000→100000",
            "ability2": "253→629 全体 20 倍雷属性技能伤害，不加 202（保留副位效果，官方零先例，需真机测副位）",
            "ability3": "412→411；c27 144→23、c30/c31 1000000→100000；154→2；删除自身 411 行",
            "ability5": "388→34",
            "upskill": "ability_damage_up→skill_damage_up",
            "runtime_verified": False,
        },
    }

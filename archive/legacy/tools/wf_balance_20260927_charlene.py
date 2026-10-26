# -*- coding: utf-8 -*-
"""2026-09-27 平衡批次：夏琳 139992 ``artificialeye_sniper_moon`` 的键级修订（纯函数）。

作者 2026-09-27 确认的规格（目标选「雷属性全队」）：

1. 技能 DSL 两档：顶层在队友护盾 ``FindAllSubjects(5,35,[3])`` 之后插入
   ``CreateBarrier(-17, 0.1, GenericBarrierHitEffect)``——自身护盾＝自身最大 HP 10%
   （官方先例 alice_smr20 / woman_knight_1anv 顶层 -17 写法；BarrierCalculator 按受盾者自己的最大 HP 算）。
2. 技能 DSL 两档：强化分支（``ConditionalsChangeSkillFlag(1)``）里两个 ``ConditionalsProbability``
   各删掉 ``ACStun`` 分支，剩麻痹 / 中毒 / 迟缓三支，权重仍写 25（评估器按相对权重，和 75 ⇒ 每支 1/3）。
   ``ACStun`` 转成 Stunify，``fit()`` 只允许挂成员，挂敌人被静默丢弃——原分支是死格。
3. 能力 1（``1399921``）追加第 3 条：官方 ``1310014#0``（fox_oracle_4，kind 53 StunWinceSlayer
   ＝眩晕畏缩特攻＝对虚弱中敌人的追击伤害，独立乘区）全队 target 5 Yellow，c51/c52＝20000，
   带雷共鸣前置（c6=2、c9/c10=600000、c11=Yellow）；不写面板覆盖（客户端自动生成）。
4. ``custom_ability_string:change_skill_artificialeye_sniper_moon`` 去掉「、使敌人更容易进入DOWN」。
5. 技能描述四处同步（action_skill 两档 c1、character_text c5/c7、服务端 character_text [5]/[7]）：
   在「护盾值为其最大生命值25%」后插入「，同时为自身赋予护盾，护盾值为自身最大生命值10%」。

接口见 ``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``：:func:`revise` 只经 ``read`` 读 live，
开头按 :data:`BEFORE` 摘要校验（漂移即抛 :class:`CharleneBalanceError`，fail closed），不改 ``read`` 的返回对象。
生成器 ``wf_midautumn_kit_charlene`` 已同步修改，``tests/test_balance_20260927_charlene.py`` 断言两者输出一致。
本模块不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl

CID = "139992"
CODE = "artificialeye_sniper_moon"
PACKAGES = ["ma-charlene"]
#: 候选现值 1.0.0（``work/character_packs/ma-charlene/package/manifest.json``）→ 递增。
PACKAGE_VERSION = {"ma-charlene": "1.0.1"}
CAPABILITIES: list[str] = []

ELEMENT = 2                      # 内部 ElementKind：雷
ELEMENT_TOKEN = "Yellow"
ABILITY_KEY = CID + "1"          # 能力 1
CAS_KEY = "change_skill_" + CODE
PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in ("1", "2")}

# ------------------------------------------------------------------ 能力 1 第 3 条

ABILITY_NCOLS = 126


def _sparse_row(cells: dict[int, str], ncols: int = ABILITY_NCOLS) -> list[str]:
    row = [""] * ncols
    for col, value in cells.items():
        row[col] = value
    return row


#: 官方 fox_oracle_4 ``1310014#0`` 逐格快照（只列非空格；测试与官方基线逐字比对）：
#: 常驻（c27=0）、kind 53 StunWinceSlayer、target 5 全队、c49 Yellow、3.5%→7%。
DONOR_ROW = _sparse_row({
    0: "fox_oracle_4", 1: "true", 2: "attack_yellow", 3: "0", 5: "0", 6: "0", 13: "0", 20: "0",
    27: "0", 39: "(None)", 46: "0", 47: "53", 48: "5", 49: "Yellow", 51: "3500", 52: "7000",
})
DONOR = "1310014#0"

#: 雷属性共鸣前置（与本角色 536 行同一道门：前置 1 = kind 2 编成人数 ≥6 + Yellow）。
PRE_RESONANCE = {6: "2", 9: "600000", 10: "600000", 11: ELEMENT_TOKEN}
STUN_WINCE_RATE = "20000"        # 20%（×100000 口径）
STUN_WINCE_CELLS = {0: CODE + "_1", 2: "attack_yellow", 51: STUN_WINCE_RATE, 52: STUN_WINCE_RATE,
                    **PRE_RESONANCE}
STUN_WINCE_DESCRIBE = "雷·编成≥6 时: 赋予全队(雷) 眩晕畏缩特攻 20%"


def stun_wince_row() -> list[str]:
    row = list(DONOR_ROW)
    for col, value in STUN_WINCE_CELLS.items():
        row[col] = value
    return row


# ------------------------------------------------------------------ 文案

OLD_CAS_TEXT = ("雷属性共鸣时强化技能：命中敌人时赋予其累积全属性抗性降低与累积攻击力降低效果"
                "（无视弱体抗性），并随机追加赋予麻痹、中毒、迟缓、使敌人更容易进入DOWN中的两种效果")
CAS_REMOVED = "、使敌人更容易进入DOWN"
NEW_CAS_TEXT = OLD_CAS_TEXT.replace(CAS_REMOVED, "")

DESC_ANCHOR = "护盾值为其最大生命值25%"
DESC_INSERT = "，同时为自身赋予护盾，护盾值为自身最大生命值10%"
OLD_DESC = ("抽取全体队伍成员生命值55%（若该成员当前生命值低于50%，则改为抽取其生命值20%），"
            "并为除自身外的雷属性角色赋予护盾，护盾值为其最大生命值25% ＋ "
            "瞄准敌人射出月华贯穿弹，命中后爆炸，对范围内的敌人造成雷属性伤害")
NEW_DESC = OLD_DESC.replace(DESC_ANCHOR, DESC_ANCHOR + DESC_INSERT)

#: character_text 行里技能说明所在列（觉醒前 / 觉醒后）。
TEXT_DESC_COLUMNS = (5, 7)

# ------------------------------------------------------------------ DSL

SELF_SUBJECT = -17               # 内建主体：自身
SELF_BARRIER_RATIO = 0.1
SELF_BARRIER = ["Command", ["CreateBarrier", SELF_SUBJECT,
                            [{"min": SELF_BARRIER_RATIO, "max": SELF_BARRIER_RATIO}],
                            ["GenericBarrierHitEffect"]]]

#: 顶层现有的队友护盾（插入锚点；逐字核对，不对就拒绝）。
ALLY_BARRIER = ["Command", ["FindAllSubjects", 5, 35, [3], [], [], [], [], ["DoNothing"],
                            ["Block", [["Command", ["CreateBarrier", 5, [{"min": 0.25, "max": 0.25}],
                                                    ["GenericBarrierHitEffect"]]]]]]]

ROULETTE_KEPT = ("ACParalysis", "ACPoison", "ACFrozen")
ROULETTE_DROPPED = "ACStun"
ROULETTE_WEIGHT = 25

#: live 两档（修订前）的命令计数指纹。
COUNTS_BEFORE = {
    "FindAllSubjects": 2, "ConditionalsHealthPointRatioOf": 1, "CreateRatioAttack": 2,
    "CreateBarrier": 1, "FindNearSubjects": 1, "StopBall": 1, "ShowEffect": 5, "CreateHitArea": 2,
    "MoveHitArea": 1, "ShakeCamera": 1, "ConditionalsChangeSkillFlag": 1, "CreateCondition": 10,
    "ConditionalsProbability": 2, "ProbabilityWeight": 8, "CreateReferencePoint": 1,
    "CreateNormalAttack": 1,
}
COUNTS_AFTER = dict(COUNTS_BEFORE, CreateBarrier=2, CreateCondition=8, ProbabilityWeight=6)

# ------------------------------------------------------------------ 输入基线

#: ``{(kind, key): sha256}``：revise() 读取的每一项在 live 上的摘要（2026-09-27 只读采集；
#: 调研记录的链尾 1.4.1047、pending 为空）。fixture ``tests/fixtures/balance_20260927_charlene.json`` 同源。
BEFORE: dict[tuple[str, str], str] = {
    ("ability", ABILITY_KEY): "26672056e6c510d780220c445551c6a5fec7f92c789cb5a5bd321edc3f24733c",
    ("cas", CAS_KEY): "0f2acef1156beadd006f9f4e84130895c3870de9ff140c8e71a08816cd6bed9c",
    ("text", CID): "b68e72a7b7955075b9ac5bee4a9ab213c1ef6c3da2ea5bb1c26247077dd43717",
    ("action", CODE): "647a03a7491674d67aba7c044c34eca90d8dca79f4989c3ceb41b5f6e6a37fa3",
    ("dsl", PROGRAMS["1"]): "7fb2692a6d7556288b7bfdd4fdf872de5877b73419154fc97e9dd4189eb00e1a",
    ("dsl", PROGRAMS["2"]): "0d632e2d218d2a6b5894530f6edceb16fa987a401c2bd790fc18063e0626a6a2",
    ("server_text", CID): "b68e72a7b7955075b9ac5bee4a9ab213c1ef6c3da2ea5bb1c26247077dd43717",
}


class CharleneBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ DSL 工具

def _commands(node, out: list | None = None) -> list[list]:
    """深度优先收集 ``["Command", [name, …]]`` 的参数数组。"""
    out = [] if out is None else out
    if isinstance(node, list):
        if len(node) == 2 and node[0] == "Command" and isinstance(node[1], list) and node[1] \
                and isinstance(node[1][0], str):
            out.append(node[1])
        for child in node:
            _commands(child, out)
    elif isinstance(node, dict):
        for child in node.values():
            _commands(child, out)
    return out


def command_counts(tree) -> dict[str, int]:
    counts: dict[str, int] = {}
    for args in _commands(tree):
        counts[args[0]] = counts.get(args[0], 0) + 1
    return counts


def _branch_ac(branch) -> tuple[int, str]:
    """``["Block", [PW, ["Block", [CreateCondition]]]]`` → (权重, AC 名)；形状不对就抛错。"""
    if not (isinstance(branch, list) and len(branch) == 2 and branch[0] == "Block"
            and isinstance(branch[1], list) and len(branch[1]) == 2):
        raise CharleneBalanceError(f"roulette branch shape changed: {branch!r:.200}")
    weight_cmd, body = branch[1]
    if not (isinstance(weight_cmd, list) and weight_cmd[0] == "Command"
            and weight_cmd[1][0] == "ProbabilityWeight" and len(weight_cmd[1]) == 2):
        raise CharleneBalanceError(f"roulette branch weight changed: {weight_cmd!r:.200}")
    if not (isinstance(body, list) and body[0] == "Block" and len(body[1]) == 1
            and body[1][0][0] == "Command" and body[1][0][1][0] == "CreateCondition"):
        raise CharleneBalanceError(f"roulette branch body changed: {body!r:.200}")
    acs = body[1][0][1][2]
    if not (isinstance(acs, list) and len(acs) == 1 and isinstance(acs[0], list)):
        raise CharleneBalanceError(f"roulette CreateCondition AC list changed: {acs!r:.200}")
    return weight_cmd[1][1], acs[0][0]


def revise_tree(tree, level: str) -> tuple[list, dict[str, Any]]:
    """live 技能树 → 新树（深拷贝）。结构不符直接抛错。"""
    out = copy.deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl"):
        raise CharleneBalanceError(f"skill {level}: unexpected root")
    before = command_counts(out)
    if before != COUNTS_BEFORE:
        raise CharleneBalanceError(f"skill {level}: commands {before} != {COUNTS_BEFORE}")

    # --- 1) 顶层：队友护盾之后插自身护盾
    top = out[11]
    if not (isinstance(top, list) and top[0] == "Block"):
        raise CharleneBalanceError(f"skill {level}: top is not a Block")
    names = [cmd[1][0] for cmd in top[1]]
    if names != ["FindAllSubjects", "FindAllSubjects", "FindNearSubjects"]:
        raise CharleneBalanceError(f"skill {level}: top commands {names}")
    if top[1][1] != ALLY_BARRIER:
        raise CharleneBalanceError(f"skill {level}: ally barrier block changed")
    top[1].insert(2, copy.deepcopy(SELF_BARRIER))

    # --- 2) 强化分支两轮轮盘各删 ACStun
    flags = [args for args in _commands(out) if args[0] == "ConditionalsChangeSkillFlag"]
    if len(flags) != 1 or flags[0][1] != 1 or flags[0][3] != ["Block", []]:
        raise CharleneBalanceError(f"skill {level}: ConditionalsChangeSkillFlag(1) shape changed")
    boost = flags[0][2]
    probs = [cmd[1] for cmd in boost[1] if cmd[1][0] == "ConditionalsProbability"]
    if [cmd[1][0] for cmd in boost[1]] != ["CreateCondition", "CreateCondition",
                                           "ConditionalsProbability", "ConditionalsProbability"]:
        raise CharleneBalanceError(f"skill {level}: boost block order changed")
    removed = []
    for index, args in enumerate(probs):
        branches = args[1][1]
        seen = [_branch_ac(branch) for branch in branches]
        want = [(ROULETTE_WEIGHT, ac) for ac in (*ROULETTE_KEPT, ROULETTE_DROPPED)]
        if seen != want:
            raise CharleneBalanceError(f"skill {level}: roulette #{index} {seen} != {want}")
        removed.append(branches.pop(len(ROULETTE_KEPT)))
        if [ac for _w, ac in map(_branch_ac, branches)] != list(ROULETTE_KEPT):
            raise CharleneBalanceError(f"skill {level}: roulette #{index} left wrong branches")

    after = command_counts(out)
    if after != COUNTS_AFTER:
        raise CharleneBalanceError(f"skill {level}: revised commands {after} != {COUNTS_AFTER}")
    changed = {name: [before.get(name, 0), after.get(name, 0)]
               for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)}
    return out, {"level": level, "self_barrier_index": 2,
                 "removed_branches": len(removed), "counts_changed": changed}


def dsl_gate_problems(tree) -> list[str]:
    """contract 要求的四道 DSL 门 + AMF3 往返。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


def row_gate_problems(row: list[str]) -> list[str]:
    """contract 要求的词条行门禁（合法性 / 声明块字段 / 元素列 / 629 文案键 / capability）。"""
    problems = [f"legality: {p}" for p in L.client_legality_problems("ability", row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems("ability", row)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems("ability", row, ELEMENT)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, {CAS_KEY})]
    caps = L.required_client_capabilities("ability", row)
    if sorted(caps) != sorted(CAPABILITIES):
        problems.append(f"capabilities {caps} != {CAPABILITIES}")
    return problems


# ------------------------------------------------------------------ 各表

def _replace_desc(text: str, label: str) -> str:
    if text != OLD_DESC:
        raise CharleneBalanceError(f"{label}: skill description is not the reviewed text")
    return NEW_DESC


def revise_ability(rows: list[list[str]]) -> list[list[str]]:
    out = copy.deepcopy(rows)
    if len(out) != 2 or any(len(r) != ABILITY_NCOLS for r in out) or [r[47] for r in out] != ["211", "536"]:
        raise CharleneBalanceError(f"ability {ABILITY_KEY}: expected 2×126 rows (211, 536)")
    if out[1][70] != CAS_KEY:
        raise CharleneBalanceError(f"ability {ABILITY_KEY}: 536 row no longer points at {CAS_KEY}")
    out.append(stun_wince_row())
    if {r[0] for r in out} != {CODE + "_1"} or {r[1] for r in out} != {"true"} \
            or {r[2] for r in out} != {"attack_yellow"}:
        raise CharleneBalanceError(f"ability {ABILITY_KEY}: mixed c0/c1/c2 after append")
    return out


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        got = digest(value)
        if got != want:
            raise CharleneBalanceError(f"live drift: {kind}:{key} sha256 {got} != reviewed {want}")
        inputs[kind, key] = copy.deepcopy(value)

    ability = revise_ability(inputs["ability", ABILITY_KEY])
    problems = row_gate_problems(ability[2])
    if problems:
        raise CharleneBalanceError(f"ability {ABILITY_KEY}#2 rejected: {problems}")

    cas = inputs["cas", CAS_KEY]
    if cas != [[OLD_CAS_TEXT]]:
        raise CharleneBalanceError(f"{CAS_KEY}: text is not the reviewed one")
    cas = [[NEW_CAS_TEXT]]

    text = inputs["text", CID]
    if len(text) != 1 or len(text[0]) != 12:
        raise CharleneBalanceError(f"character_text {CID}: expected one 12-column row")
    for col in TEXT_DESC_COLUMNS:
        text[0][col] = _replace_desc(text[0][col], f"character_text c{col}")

    action = inputs["action", CODE]
    if [inner for inner, _fields in action] != ["1", "2"]:
        raise CharleneBalanceError(f"action_skill {CODE}: inner keys changed")
    new_action = []
    for inner, fields in action:
        fields = list(fields)
        if fields[7] != PROGRAMS[inner]:
            raise CharleneBalanceError(f"action_skill {CODE}/{inner}: program {fields[7]!r}")
        fields[1] = _replace_desc(fields[1], f"action_skill {inner} c1")
        new_action.append((inner, fields))

    server = inputs["server_text", CID]
    if len(server) != 1 or len(server[0]) != 12:
        raise CharleneBalanceError(f"server character_text {CID}: expected one 12-column row")
    for col in TEXT_DESC_COLUMNS:
        server[0][col] = _replace_desc(server[0][col], f"server character_text [{col}]")

    trees, tree_notes = {}, []
    for level, program in PROGRAMS.items():
        tree, ev = revise_tree(inputs["dsl", program], level)
        problems = dsl_gate_problems(tree)
        if problems:
            raise CharleneBalanceError(f"skill {level} rejected: {problems}")
        ev["amf3_bytes"] = {"before": len(wf_dsl.encode_amf3(inputs["dsl", program])),
                            "after": len(wf_dsl.encode_amf3(tree))}
        trees[program] = tree
        tree_notes.append(ev)

    return {
        "ability": {ABILITY_KEY: ability},
        "leader": {},
        "cas": {CAS_KEY: cas},
        "text": {CID: text},
        "table": {},
        "action": {CODE: new_action},
        "dsl": trees,
        "server_text": {CID: server},
        "new_programs": [],
        "notes": {
            "character": f"{CID} {CODE} 夏琳",
            "ability": {"key": ABILITY_KEY, "appended_index": 2, "donor": DONOR,
                        "cells": {str(k): v for k, v in STUN_WINCE_CELLS.items()},
                        "describe": STUN_WINCE_DESCRIBE,
                        "why": "kind 53 StunWinceSlayer→PinchSlayer：目标处于虚弱（Down）时的独立乘区 "
                               "(1+Σ)；只作用于 NormalAttackCalculator，不含比例/定值伤害与毒；"
                               "与 536 共用雷共鸣门；不写 desc_override，面板由客户端生成"},
            "custom_ability_string": {"key": CAS_KEY, "removed": CAS_REMOVED},
            "skill_description": {"inserted_after": DESC_ANCHOR, "inserted": DESC_INSERT,
                                  "places": ["action_skill 1/2 c1", "character_text c5/c7",
                                             "server cdndata/character_text.json [5]/[7]"]},
            "dsl": tree_notes,
            "self_barrier": {"subject": SELF_SUBJECT, "ratio": SELF_BARRIER_RATIO,
                             "why": "BarrierCalculator 按受盾者自身最大 HP 取整；新盾只在 canOverride "
                                    "时替换旧盾、不叠加；抽血是友伤、不被护盾吸收"},
            "roulette": {"kept": list(ROULETTE_KEPT), "dropped": ROULETTE_DROPPED,
                         "weight": ROULETTE_WEIGHT,
                         "why": "ACStun→Stunify 只能挂成员（fit），挂敌人被静默丢弃，原分支是死格；"
                                "删后三支各 1/3（相对权重，和 75）"},
            "generator": "wf_midautumn_kit_charlene.py 已同步（ROULETTE / CAS_TEXTS / _SKILL_DESC / "
                         "self_barrier_block / ABILITY['1399921']），生成器输出 == revise() 输出",
            "capabilities": list(CAPABILITIES),
            "mirrors": "设计镜像由 sync_mirrors() 幂等收敛（python mod-tools/wf_balance_20260927_charlene.py "
                       "--write-mirrors）；候选包由暂存脚本回写",
        },
    }


# ------------------------------------------------------------------ 设计镜像（work/ 下，gitignore）
# contract 允许写：design/charlene.json（kit 的 design_crosscheck 逐字比对 texts 与
# plan.ability.keys['1399921']，不同步的话重跑 kit 直接 CharleneError）、rework1/panel/charlene.json、
# rework1/panel/_deviations.json charlene 段。变换幂等：改前 / 改后两种状态都收敛到同一结果，
# 其它形状一律抛错；读改写只动夏琳自己的条目（_deviations.json 其它角色段原样保留）。

BATCH_REL = "work/character_packs/midautumn-20260920"
DESIGN_REL = BATCH_REL + "/design/charlene.json"
PANEL_REL = BATCH_REL + "/rework1/panel/charlene.json"
DEVIATIONS_REL = BATCH_REL + "/rework1/panel/_deviations.json"

AUTHORITY = "作者 2026-09-27 平衡批次（目标选「雷属性全队」）；live 键级修订 mod-tools/wf_balance_20260927_charlene.py"

DESIGN_RECORD = {
    "index": 2,
    "donor": "official ability[1310014] #1",
    "desc_expected": STUN_WINCE_DESCRIBE,
    "edits_old_new": {str(i): [DONOR_ROW[i], value]
                      for i, value in enumerate(stun_wince_row()) if DONOR_ROW[i] != value},
    "cells": {str(i): value for i, value in enumerate(stun_wince_row()) if value},
    "why": "09-27 平衡批次：作者要「对处于虚弱状态的敌人造成伤害，额外乘区＋20%」、目标选雷属性全队。"
           "kind 53 StunWinceSlayer→PinchSlayer（InstantAbilitySource.as:953-956），NormalAttackCalculator.as:647-660 "
           "对 hasPinched 目标单独乘 (1+Σ)＝独立乘区；donor 官方 fox_oracle_4 1310014#0（常驻、target 5、Yellow、3.5→7%），"
           "改 c0 与 20%，加与 536 同一道雷共鸣前置。面板由客户端自动生成（不写 desc_override，零补丁依赖）。",
    "legality_problems": [],
    "required_capabilities": [],
}
DESIGN_ROLE_OLD = "开局自身充能 ＋ 雷共鸣时强化技能(536)"
DESIGN_ROLE = "开局自身充能 ＋ 雷共鸣时强化技能(536) ＋ 雷共鸣全队(雷)眩晕畏缩特攻(53)"
R3_SHAPE_OLD = "ConditionalsProbability(4 分支)"
R3_SHAPE_NEW = "ConditionalsProbability(3 分支；09-27 删 ACStun)"
DESIGN_D18 = {
    "id": "D18",
    "original": "D13：「气绝」落成 ACStun（眩晕蓄积），文案「使敌人更容易进入 DOWN」",
    "actual": "09-27 平衡批次删掉两轮轮盘里的 ACStun 分支（剩麻痹/中毒/迟缓，权重仍 25 ⇒ 各 1/3），"
              "强化条目文案去掉「、使敌人更容易进入DOWN」；「对虚弱敌人」的加成改由词条 1 第 3 条 kind 53（全队雷 20%，独立乘区）承担",
    "why": "ACStun 转成 ConditionChangeContent.Stunify（AdditionalConditionKindTools.as:241-243），fit() 规定 Stunify 只能挂 xMember"
           "（ConditionChangeContentTools.as:1059-1071），挂敌人在 ConditionSlot.as:7454 直接 return；削韧也只读攻击方自己的 Stunify"
           "（NormalAttackCalculator.as:159/802）⇒ 原分支是死格、面板说法不属实。" + AUTHORITY,
}
DESIGN_SECTION = {
    "date": "2026-09-27",
    "authority": [AUTHORITY],
    "changed": {
        "skill_dsl": "两档顶层在队友护盾之后插 CreateBarrier(-17, 0.1, GenericBarrierHitEffect)（自身最大 HP 10%）；"
                     "强化分支两轮 ConditionalsProbability 各删 ACStun 分支（CreateBarrier 1→2、CreateCondition 10→8、ProbabilityWeight 8→6）",
        "ability_1": "追加第 3 条：donor 1310014#0 kind 53，全队(雷) 20%，雷共鸣前置（2 条 → 3 条）",
        "custom_ability_string": "change_skill_artificialeye_sniper_moon 去掉「、使敌人更容易进入DOWN」",
        "skill_desc": "在「护盾值为其最大生命值25%」后插入「，同时为自身赋予护盾，护盾值为自身最大生命值10%」"
                      "（action_skill 两档 c1、character_text c5/c7、服务端 character_text [5]/[7]）",
    },
    "unchanged": ["队长技 5 行", "词条 2–6", "技能能量 500/500、爆炸倍率", "立绘/语音/像素/图标"],
    "generator": "wf_midautumn_kit_charlene.py 同步（ROULETTE / CAS_TEXTS / _SKILL_DESC / self_barrier_block / ABILITY['1399921']）；"
                 "tests/test_balance_20260927_charlene.py 断言生成器输出 == revise() 输出",
}
# 词条行 11 → 12（1399921 两条 → 三条）后设计稿里写死「11 条行」的四处：(定位说明, 旧值, 新值)。
# 真机验收清单 C2 必须点名新增的 1399921#2：它的面板是客户端自动生成的，desc_expected 只是 wf_describe 预览。
ROW_COUNT_E5_CLAIM = (
    "本套件所有 11 条行的 required_client_capabilities 都是空，不需要任何 APK 补丁 kind（无 422 / 724 / desc_override）。",
    "本套件所有 12 条行（含 09-27 追加的 1399921#2 kind 53）的 required_client_capabilities 都是空，"
    "不需要任何 APK 补丁 kind（无 422 / 724 / desc_override）。",
)
ROW_COUNT_E5_EVIDENCE = ("09-27 追加的 1399921#2：tests/test_balance_20260927_charlene.py::test_new_record_passes_every_gate "
                         "实跑 wf_client_legality，problems 全空、required_client_capabilities 全空")
ROW_COUNT_OVERRIDE_WHY = (
    "11 条行全部由客户端原生渲染，且没有恒真 during 触发（无 HpLow/HpHigh 100% 文本），不需要覆盖。",
    "12 条行全部由客户端原生渲染（09-27 追加的 1399921#2 kind 53 由客户端按 stun_wince_slayer 自动拼出，"
    "末尾带「（独立乘区）」），且没有恒真 during 触发（无 HpLow/HpHigh 100% 文本；新行的门是雷共鸣前置），不需要覆盖。",
)
ROW_COUNT_CANARY_C2 = (
    "C2 面板逐行回读：11 条行的中文描述与 design.json 的 desc_expected 逐字一致；"
    "确认没有出现『生命值100%以下』『自身为队长时』『(觉醒后X%)』。",
    "C2 面板逐行回读：12 条行的中文描述与 design.json 的 desc_expected 逐字一致；例外是 09-27 追加的 1399921#2（kind 53）："
    "它的 desc_expected 只是 wf_describe 预览，真机面板由客户端自动生成，须逐字记下并核对为「雷属性共鸣时、全队雷属性角色、"
    "追击伤害＋20%」且末尾带「（独立乘区）」；确认没有出现『生命值100%以下』『自身为队长时』『(觉醒后X%)』。",
)
ROW_COUNT_EVIDENCE_FILE = (
    "scratchpad/charlene_rows.py（11 条行的构建与 wf_client_legality 实跑，problems 全空、caps 全空）",
    "scratchpad/charlene_rows.py（09-20 的 11 条原有行的构建与 wf_client_legality 实跑，problems 全空、caps 全空）；"
    "09-27 追加的第 12 条 1399921#2 由 tests/test_balance_20260927_charlene.py::test_new_record_passes_every_gate 实跑，"
    "problems 全空、caps 全空",
)
CANARY_C10 = ("C10（09-27 平衡批次）打一发技能：夏琳自身出现护盾，数值≈自身最大生命值10%（队友护盾仍为各自最大生命值25%；"
              "自身护盾只覆盖不叠加）；强化技能随机减益只出现麻痹/中毒/迟缓。雷共鸣下对照「编成里有夏琳」与「换掉夏琳」两组："
              "同一雷属性队友普通伤害在敌人 DOWN 中 / DOWN 外的比值，有夏琳时应再多乘约 1.20（比例/定值伤害与毒不吃这条加成）。")

PANEL_SKILL_OLD = OLD_DESC.split(" ＋ ")[0]
PANEL_SKILL_NEW = NEW_DESC.split(" ＋ ")[0]
PANEL_DEV_WHY_OLD = "「气绝」按作者 09-21 定案换成「使敌人更容易进入 DOWN」（ACStun＝Stunify 眩晕蓄积）。"
PANEL_DEV_WHY_NEW = ("「气绝」09-21 曾落成「使敌人更容易进入 DOWN」（ACStun＝Stunify 眩晕蓄积），"
                     "09-27 平衡批次确认它挂不上敌人（fit 只允许挂成员）后移除，轮盘剩麻痹/中毒/迟缓三格。")
PANEL_LINE = {
    "text": "雷属性共鸣时，赋予全队雷属性角色对处于虚弱状态的敌人造成的伤害，额外乘区＋20%",
    "status": "changed",
    "dev": True,
    "dev_why": "09-27 平衡批次新增：kind 53 眩晕畏缩特攻（donor 官方 1310014#0），全队雷 20%，与 536 共用雷共鸣门。"
               "不写 desc_override，真机面板为客户端按 stun_wince_slayer ＋「（独立乘区）」自动生成的文案（本行只是语义预览，措辞以真机为准）；"
               "只作用于普通伤害链，不含比例/定值伤害与毒。",
}
PANEL_NOTE = ("平衡批次（2026-09-27）：技能加自身护盾（自身最大生命值10%）；随机池删掉挂不上敌人的「更容易进入DOWN」格；"
              "能力1追加雷共鸣时全队雷对虚弱敌人独立乘区＋20%（kind 53，面板客户端自动生成）。live 修订 wf_balance_20260927_charlene.py。")
STUN_DEVIATION_KEY = "随机追加麻痹/气绝/中毒/迟缓两种"
PANEL_DEVIATION = ("09-21 曾把「气绝」换成「使敌人更容易进入 DOWN」（ACStun）；09-27 平衡批次确认 ACStun 挂不上敌人（死格）后移除，"
                   "轮盘剩麻痹/中毒/迟缓三格，「对虚弱敌人」改由能力1 kind 53 独立乘区＋20% 承担。")
BATCH_DEVIATION = ("作者已定（09-21）：「气绝」这一格换成「使敌人更容易进入 DOWN」。"
                   "09-27 平衡批次：该格（ACStun）挂不上敌人、实为死格，已移除；轮盘剩麻痹/中毒/迟缓，"
                   "「对虚弱敌人」改由能力1 kind 53 全队雷独立乘区＋20% 承担。")


def _converge(value, old, new, label: str):
    if value not in (old, new):
        raise CharleneBalanceError(f"mirror {label}: unexpected value {value!r:.120}")
    return new


def later_cas_text() -> str:
    """第三轮（wf_balance_20260927c_panels FLAG_TEXT，主会话 R2）改写后的强化条目：本批不再改它，镜像里原样保留。"""
    import wf_balance_20260927c_panels as P3
    return P3.FLAG_TEXT[CID]["after"]


def _converge_cas(value, label: str):
    return value if value == later_cas_text() else _converge(value, OLD_CAS_TEXT, NEW_CAS_TEXT, label)


def design_update(design: dict) -> dict:
    out = copy.deepcopy(design)
    texts = out["texts"]
    for name in ("desc1", "desc2"):
        texts[name] = _converge(texts[name], OLD_DESC, NEW_DESC, f"texts.{name}")
    plan_texts = out["plan"]["texts"]
    desc = plan_texts["action_skill_desc"]
    for name in ("desc1", "desc2"):
        desc[name] = _converge(desc[name], OLD_DESC, NEW_DESC, f"plan.texts.action_skill_desc.{name}")
    rows = [row for row in plan_texts["custom_ability_string"]["rows"] if row.get("key") == CAS_KEY]
    if len(rows) != 1:
        raise CharleneBalanceError(f"mirror design: {CAS_KEY} row count {len(rows)}")
    rows[0]["text"] = _converge_cas(rows[0]["text"], "custom_ability_string")

    entry = out["plan"]["ability"]["keys"][ABILITY_KEY]
    entry["role"] = _converge(entry["role"], DESIGN_ROLE_OLD, DESIGN_ROLE, "ability role")
    records = entry["records"]
    if len(records) == 2:
        records.append(copy.deepcopy(DESIGN_RECORD))
    elif len(records) != 3 or records[2] != DESIGN_RECORD:
        raise CharleneBalanceError(f"mirror design: ability {ABILITY_KEY} records drifted")
    entry["unisonable_per_record"] = _converge(entry["unisonable_per_record"], ["true"] * 2, ["true"] * 3,
                                               "unisonable_per_record")
    entry["record_count"] = _converge(entry["record_count"], {"old": 2, "new": 2}, {"old": 2, "new": 3},
                                      "record_count")

    r3 = [item for item in out["plan"]["skills"]["edits_rework1"] if item.get("id") == "R3"]
    if len(r3) != 1 or (R3_SHAPE_OLD not in r3[0]["shape"] and R3_SHAPE_NEW not in r3[0]["shape"]):
        raise CharleneBalanceError("mirror design: edits_rework1 R3 shape drifted")
    r3[0]["shape"] = r3[0]["shape"].replace(R3_SHAPE_OLD, R3_SHAPE_NEW)

    deviations = out["deviations"]
    d13 = [item for item in deviations if item.get("id") == "D13"]
    if len(d13) != 1:
        raise CharleneBalanceError("mirror design: D13 missing")
    d13[0]["superseded_by"] = "D18（2026-09-27 平衡批次）"
    d18 = [index for index, item in enumerate(deviations) if item.get("id") == "D18"]
    if not d18:
        deviations.append(copy.deepcopy(DESIGN_D18))
    elif len(d18) != 1 or deviations[d18[0]] != DESIGN_D18:
        raise CharleneBalanceError("mirror design: D18 drifted")
    _design_row_count(out)
    out["balance_20260927"] = copy.deepcopy(DESIGN_SECTION)
    return out


def _single(items, predicate, label: str) -> dict:
    found = [item for item in items if predicate(item)]
    if len(found) != 1:
        raise CharleneBalanceError(f"mirror design: {label} count {len(found)}")
    return found[0]


def _design_row_count(out: dict) -> None:
    """设计稿里写死的「11 条行」收敛为 12 条（原地改 ``out``），并补 C10 真机验收项。"""
    e5 = _single(out["engine_findings"], lambda item: item.get("id") == "E5", "engine_findings E5")
    e5["claim"] = _converge(e5["claim"], *ROW_COUNT_E5_CLAIM, "engine_findings E5 claim")
    if ROW_COUNT_E5_EVIDENCE not in e5["evidence"]:
        e5["evidence"].append(ROW_COUNT_E5_EVIDENCE)

    override = out["plan"]["texts"]["desc_override"]
    override["why"] = _converge(override["why"], *ROW_COUNT_OVERRIDE_WHY, "plan.texts.desc_override.why")

    canary = out["canary"]
    c2 = [index for index, item in enumerate(canary) if item.startswith("C2 ")]
    if len(c2) != 1:
        raise CharleneBalanceError(f"mirror design: canary C2 count {len(c2)}")
    canary[c2[0]] = _converge(canary[c2[0]], *ROW_COUNT_CANARY_C2, "canary C2")
    c10 = [item for item in canary if item.startswith("C10")]
    if not c10:
        canary.append(CANARY_C10)
    elif c10 != [CANARY_C10]:
        raise CharleneBalanceError("mirror design: canary C10 drifted")

    files = out["evidence_files"]
    rows_file = [index for index, item in enumerate(files) if item.startswith("scratchpad/charlene_rows.py")]
    if len(rows_file) != 1:
        raise CharleneBalanceError(f"mirror design: evidence_files charlene_rows.py count {len(rows_file)}")
    files[rows_file[0]] = _converge(files[rows_file[0]], *ROW_COUNT_EVIDENCE_FILE, "evidence_files charlene_rows.py")


def panel_update(panel: dict) -> dict:
    out = copy.deepcopy(panel)
    skill = out["skill"]["lines"][0]
    skill["text"] = _converge(skill["text"], PANEL_SKILL_OLD, PANEL_SKILL_NEW, "panel skill line")
    ability = [item for item in out["abilities"] if item.get("index") == 1]
    if len(ability) != 1:
        raise CharleneBalanceError("mirror panel: ability 1 missing")
    lines = ability[0]["lines"]
    lines[1]["text"] = _converge_cas(lines[1]["text"], "panel ability 1 line 2")
    if PANEL_DEV_WHY_OLD in lines[1]["dev_why"]:
        lines[1]["dev_why"] = lines[1]["dev_why"].replace(PANEL_DEV_WHY_OLD, PANEL_DEV_WHY_NEW)
    elif PANEL_DEV_WHY_NEW not in lines[1]["dev_why"]:
        raise CharleneBalanceError("mirror panel: ability 1 line 2 dev_why drifted")
    if len(lines) == 2:
        lines.append(copy.deepcopy(PANEL_LINE))
    elif len(lines) != 3 or lines[2] != PANEL_LINE:
        raise CharleneBalanceError("mirror panel: ability 1 lines drifted")
    if PANEL_NOTE not in out["notes"]:
        out["notes"].append(PANEL_NOTE)
    deviation = [item for item in out["deviations"] if item.get("原话", "").startswith(STUN_DEVIATION_KEY)]
    if len(deviation) != 1:
        raise CharleneBalanceError("mirror panel: stun deviation missing")
    deviation[0]["落法"] = PANEL_DEVIATION
    return out


def deviations_update(deviations: dict) -> dict:
    out = copy.deepcopy(deviations)
    items = [item for item in out["charlene"] if item.get("原话") == STUN_DEVIATION_KEY]
    if len(items) != 1:
        raise CharleneBalanceError("mirror _deviations.json: charlene stun entry missing")
    items[0]["落法"] = BATCH_DEVIATION
    return out


#: (相对路径, 变换, JSON indent, 文件尾)：保留本机原格式（CRLF；两份无尾换行、_deviations.json 有）。
MIRRORS = ((DESIGN_REL, design_update, 1, ""),
           (PANEL_REL, panel_update, 1, ""),
           (DEVIATIONS_REL, deviations_update, 2, "\n"))


def _dump_mirror(value, indent: int, tail: str, newline: str) -> bytes:
    text = json.dumps(value, ensure_ascii=False, indent=indent) + tail
    return text.replace("\n", newline).encode("utf-8")


def sync_mirrors(root, *, write: bool = False) -> list[str]:
    """把设计镜像收敛到本批状态；返回有变化的相对路径（``write=True`` 才写）。缺文件的镜像跳过。"""
    from pathlib import Path
    root = Path(root)
    changed = []
    for rel, update, indent, tail in MIRRORS:
        path = root / rel
        if not path.is_file():
            continue
        raw = path.read_bytes()
        before = json.loads(raw.decode("utf-8"))
        after = update(before)
        if after == before:
            continue
        changed.append(rel)
        if write:
            if path.read_bytes() != raw:
                raise CharleneBalanceError(f"mirror {rel} changed while syncing")
            path.write_bytes(_dump_mirror(after, indent, tail, "\r\n" if b"\r\n" in raw else "\n"))
    return changed


if __name__ == "__main__":
    import sys
    from pathlib import Path
    result = sync_mirrors(Path(__file__).resolve().parents[1], write="--write-mirrors" in sys.argv[1:])
    print(json.dumps({"mirrors_changed": result, "write": "--write-mirrors" in sys.argv[1:]},
                     ensure_ascii=False))

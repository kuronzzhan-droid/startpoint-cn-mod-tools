# -*- coding: utf-8 -*-
"""希尔媞·校园 149989 ``wind_spgirl_campus``：2026-09-27 平衡调整第二批——「星风心得」无上限成长。

依据：``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md`` A1–A5（作者已拍板），
设计稿 ``growth/growth_design.json`` id=149989（按当前 live 1.4.1049 重读、重推；行号与设计稿一致）。

星风心得（固有 14998902，上限 2147483647）由风队在 Fever 中每次施技获得 3 层（队长 629 给 2 层、
能力3 629 给 1 层），只增不减。改前它在三处无上限地放大伤害：能力3 两条 D134 行（每层风队能力伤害 /
攻击力各 +25%，c102 (None)），以及技能 DSL 的倍率（每层 +10 倍，Bind 上限 2147483647）。

改动（其余行、树节点逐字保留）：

1. ``ability:1499893`` #6 / #7（能力3，整键仅主位）——有上限的弱化版（口径 A3）：
   c102 (None)→10（最多计 10 层；官方 1611231..6 blackflower_wiz_smr22 同为 D134 + 限 10），
   c113/c114：#6 能力伤害 25000→8000（+8%/层，上限 +80%），#7 攻击力 25000→5000（+5%/层，上限 +50%）。
2. ``leader_ability:149989`` 追加 #6 / #7——把原两行的无上限成长搬进队长（口径 A3），行形 =
   ``[CODE, '0', ''] + 改前能力行[5:]``（列号 −2），c111/c112 25000→2500（放缓 1/10，口径 A2：
   按实际步数计，这两行每层心得一步；3 分钟 Fever 中风队施技约 13–20 次、每次 +3 层 ⇒ 约 40–60 层，
   仅队长 629 的 2 层也有 26–40 层 ⇒ ≥30 ⇒ 1/10。设计稿按「每层固有＝低频」标签取 1/5，口径 A2
   「不按事件名称」不采用；同批 hibiki / kyle / magnus / nephtim 的逐层成长同样按层数取 1/10）。
   队长原 6 行没有同触发/同 kind 的行（行1/行2 是瞬发常驻 32/388），不合并。D134 进队长有官方先例
   （161123/141081，目标 5），154 进队长有官方 151021#2，D134 + (None) + 154 + 目标 5 有 live 自制
   139995#6；前置 12 在本角色队长行 3–5 已上线（口径 A4 列名「pre12 希尔媞」，但都是瞬发行）。
   **持续块 + 前置 12 的组合在 live 队长表没有先例**（1.4.1049 全表扫描：pre12 只出现在 149989#3–#5、
   149999#10、129986#3，全是瞬发；设计稿引的「169989 队长持续行 D4 + pre12」已不存在）——前置 puller
   与持续块各自解析，C7050 风险低，但须真机打开角色页 / 队长页并确认只在风共鸣 Fever 中生效。
3. 技能 DSL 两档（``rare5/wind_spgirl_campus$wind_spgirl_campus_{1,2}``）——层数贡献封顶 10（口径 A5）：
   风共鸣 ∧ Fever 支里 ``BindConditionAccumulationVariable(-17, 14998905, DCUnique 14998902, 1, 上限)``
   的上限 2147483647→10。原生取 ``min(层数/1, 上限)``（ActionEvaluator.as case 101）；官方先例
   blackflower_wiz_smr22 两档技能同为 ``Bind(-17, vid, DCUnique 11, 1, 10)``。另外两处 Bind（非共鸣 /
   非 Fever 支）上限本就是 0，不动。超出 10 层的逐层成长由第 2 条的队长两行承担（口径 A5「视为已合并」）。
   技能削韧保留（口径 B5：两支互斥，实际 28）。
4. 文案：``desc_override_wind_spgirl_campus`` 第 4 行注明队长也给 2 层心得、追加第 6 行「每层心得
   +2.5%/+2.5%」（按裁决不写「可无限累积」）；``desc_override_wind_spgirl_campus_3`` 第 7 行改为
   「+8%、+5%（最多10层）」；技能描述 5 处（action_skill 两档 c1、character_text c5/c7、服务端
   character_text [5]/[7]）在「每层额外增加10倍」后加「（最多10层）」。

生成器已同步：``wf_celtie_fever_abilities``（GAIN_BONUS_LIMIT/STRENGTH）、``wf_celtie_fever_leader``
（gain_growth_row，队长 6→8 行）、``wf_celtie_skill_growth``（GAIN_MAX_LAYERS=10）、
``wf_campus_panel_text``（_CELTIE active/leader/a3）；测试断言生成器输出 == :func:`revise` 输出。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl
import wf_midautumn_kitlib as KL

CID = "149989"
CODE = "wind_spgirl_campus"
#: flow owner（active.json base_package_owners 登记 campus-celtie-20260911）。
PACKAGES = ["campus-celtie-20260911"]
#: 候选 manifest 现值 0.20260925（日期式版本）⇒ 0.20260927（同 campus-nephtim / fox_oracle_autumn 本批写法）。
PACKAGE_VERSION = {"campus-celtie-20260911": "0.20260927"}
#: 候选 manifest required_capabilities 现为 []：能力3（1499893）整键回写含 #1 I724（比例版 Fever 槽，
#: kyubi-fever-ratio-v1），两条 desc_override_* 覆盖行需要面板覆盖补丁 v2；live 早已依赖二者。
CAPABILITIES = ["kyubi-fever-ratio-v1", "panel-description-override-v2"]
#: 候选文件与 manifest 哈希逐一一致（2026-09-27 RevisionCandidate 只读构造通过）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 3                         # 内部元素：风（与 wf_celtie_fever_* 的 legality 调用一致）
ELEMENT_TOKEN = "Green"
ABILITY_KEY = CID + "3"
CAS_LEADER = "desc_override_" + CODE
CAS_A3 = CAS_LEADER + "_3"
PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in ("1", "2")}
LEADER_NCOLS, ABILITY_NCOLS = 124, 126

GAIN_UID = "14998902"               # 固有「星风心得」
GAIN_FLOAT_ID = 14998905            # 技能 DSL 里心得层数的浮点变量
OLD_SKILL_CAP = 2147483647
NEW_SKILL_CAP = 10
ABILITY_LIMIT = "10"                # 能力3 两行 c102
#: 能力3 两行：c109 内容 kind → (改前, 改后) 每层强度（100000 = 100%）。
ABILITY_STRENGTH = {"154": ("25000", "8000"), "0": ("25000", "5000")}
#: 队长新两行：每层强度（25% × 1/10；口径 A2 按层数计 3 分钟约 40–60 步 ≥30）。
LEADER_STRENGTH = "2500"
GAIN_ROWS = (6, 7)                  # 能力3 #6（154 能力伤害）/ #7（0 攻击力）
#: 能力3 八行的 instant/during 内容 kind（#0–#5 瞬发看 c47，#6/#7 持续看 c109）。
ABILITY_KINDS = ("254", "724", "32", "211", "629", "629", "154", "0")
#: 队长六行的内容 kind（c45）；存在 D134 行即说明本修订已落地 ⇒ 拒绝重跑。
LEADER_KINDS = ("32", "388", "722", "254", "629", "629")

#: 改前能力3 #6/#7 的逐格指纹（全部非空列；其余列必须为空）。BEFORE 之外的第二道锁。
_GAIN_CELLS = {
    0: CODE + "_3", 1: "false", 2: "special", 3: "0", 5: "1", 6: "2", 9: "600000", 10: "600000",
    11: ELEMENT_TOKEN, 13: "12", 20: "0", 85: "(None)", 97: "134", 98: "0", 100: "100000",
    101: "100000", 104: GAIN_UID, 108: "false", 110: "5", 111: ELEMENT_TOKEN,
}
BEFORE_GAIN_CELLS = {content: {**_GAIN_CELLS, 102: "(None)", 109: content,
                               113: old, 114: old}
                     for content, (old, _new) in ABILITY_STRENGTH.items()}
AFTER_GAIN_CELLS = {content: {**_GAIN_CELLS, 102: ABILITY_LIMIT, 109: content,
                              113: new, 114: new}
                    for content, (_old, new) in ABILITY_STRENGTH.items()}

#: 能力3/队长里 629 行引用的 custom_ability_string 键（live 已有；生成器 flat_string_rows 同名）。
INVOKE_STRING_KEYS = frozenset({
    CODE + "_flip_stock", CODE + "_flip_stock_spent",
    CODE + "_flip_stock_ability", CODE + "_flip_stock_ability_spent",
})

# ------------------------------------------------------------------ 文案

LEADER_LINES_BEFORE = (
    "风属性角色攻击力+200%、能力伤害+400%。",
    "风属性共鸣时，强化弹射变为特殊剑士型，造成风属性伤害，伤害量以能力伤害加成判定。",
    "风属性共鸣时，Fever模式中，强化弹射时，对全场敌人追加10倍风属性能力伤害。",
    "风属性共鸣时，Fever模式中，风属性角色发动技能时，自身获得2层「星风快门」。",
    "风属性共鸣时，Fever模式中，弹射时消耗1层「星风快门」，连击+7。",
)
LEADER_LINE4_AFTER = "风属性共鸣时，Fever模式中，风属性角色发动技能时，自身获得2层「星风快门」与2层「星风心得」。"
LEADER_LINE_ADDED = "风属性共鸣时，Fever模式中，每层「星风心得」使风属性角色能力伤害+2.5%、攻击力+2.5%。"
LEADER_LINES_AFTER = LEADER_LINES_BEFORE[:3] + (LEADER_LINE4_AFTER, LEADER_LINES_BEFORE[4],
                                                 LEADER_LINE_ADDED)

MAIN_ICON = " <icon id='main'>  "
A3_LAST_BEFORE = MAIN_ICON + "风属性共鸣时，Fever模式中，每层「星风心得」使风属性角色能力伤害+25%、攻击力+25%。"
A3_LAST_AFTER = MAIN_ICON + "风属性共鸣时，Fever模式中，每层「星风心得」使风属性角色能力伤害+8%、攻击力+5%（最多10层）。"
A3_LINES = 7

DESC_ANCHOR = "每层额外增加10倍。"
DESC_ANCHOR_AFTER = "每层额外增加10倍（最多10层）。"
OLD_DESC = ("向Boss突进并持续朝其释放十字双空牙（无Boss时选择最近敌人），对命中敌人造成基础合计75倍风属性伤害，"
            "伤害量以能力伤害加成判定。风属性共鸣且Fever模式中，技能倍率随「星风心得」成长，" + DESC_ANCHOR)
NEW_DESC = OLD_DESC.replace(DESC_ANCHOR, DESC_ANCHOR_AFTER)
TEXT_DESC_COLUMNS = (5, 7)          # character_text 技能说明（觉醒前 / 后）

# ------------------------------------------------------------------ 输入基线

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数；候选 campus-celtie-20260911 0.20260925 的
#: 1499893 / 两条 desc_override / character_text / action_skill / 两棵 DSL / 服务端镜像与之逐字相同，
#: leader:149989 候选仍是初版 3 行，见 notes.candidate_preexisting_drift）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", CID): "db93fa9b920c1a0cc8e88a6061afb4376c9f30e3eab0bd62c7a6c20b63a0742d",
    ("ability", ABILITY_KEY): "390aace0923c3257285dfc72c336f01838b3b07e8c16f3b5357bb2d29a3d4a36",
    ("cas", CAS_LEADER): "42eadc937faaacd58b6cf2fc7e843b14961e90ed380054783456927313ba8831",
    ("cas", CAS_A3): "6aedcd6887453923adad04e826fd5eb1d7238859d49d70d7da45edfd714360e8",
    ("text", CID): "319d299bcd7299526d4469f37b772c7f47bba6b88044a6625459bf619855cc04",
    ("action", CODE): "b34ef4ba57ab7e08d9bb651ba8ab4f71a588f019caebce45fc3ac2d697889bbb",
    ("dsl", PROGRAMS["1"]): "c6b844e9e24e626b46220feb9553ac10818a6a63d8a74155729fea1c9804e8aa",
    ("dsl", PROGRAMS["2"]): "c6b844e9e24e626b46220feb9553ac10818a6a63d8a74155729fea1c9804e8aa",
    ("server_text", CID): "319d299bcd7299526d4469f37b772c7f47bba6b88044a6625459bf619855cc04",
}


class CeltieBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise CeltieBalanceError(f"unreviewed live baseline for {kind}:{key} "
                                 f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _ability_kind(row: list[str]) -> str:
    return row[109] if row[5] == "1" else row[47]


# ------------------------------------------------------------------ 词条

def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力3 #6/#7：c102 (None)→10，强度 25%→8% / 5%；#0–#5 逐字保留。"""
    if len(rows) != len(ABILITY_KINDS) or any(len(row) != ABILITY_NCOLS for row in rows):
        raise CeltieBalanceError(f"ability {ABILITY_KEY}: expected {len(ABILITY_KINDS)}×{ABILITY_NCOLS} rows")
    if tuple(_ability_kind(row) for row in rows) != ABILITY_KINDS:
        raise CeltieBalanceError(f"ability {ABILITY_KEY}: content kinds drifted")
    out = deepcopy(rows)
    for index, content in zip(GAIN_ROWS, ("154", "0")):
        if not _matches(rows[index], ABILITY_NCOLS, BEFORE_GAIN_CELLS[content]):
            raise CeltieBalanceError(f"ability {ABILITY_KEY}#{index}: uncapped Starwind Insight row "
                                     f"(D134, (None), {ABILITY_STRENGTH[content][0]}) not found")
        row = out[index]
        row[102] = ABILITY_LIMIT
        row[113] = row[114] = ABILITY_STRENGTH[content][1]
        if not _matches(row, ABILITY_NCOLS, AFTER_GAIN_CELLS[content]):
            raise AssertionError("ability3_rows touched more than c102/c113/c114")
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != list(GAIN_ROWS):
        raise AssertionError("ability3_rows touched another record")
    return out


def leader_growth_row(ability_row: list[str]) -> list[str]:
    """口径 A3：``[CODE, '0', ''] + 能力行[5:]``（能力 c≥5 → 队长 c−2），强度放缓到 2.5%/层。"""
    content = ability_row[109] if len(ability_row) == ABILITY_NCOLS else None
    if content not in BEFORE_GAIN_CELLS or not _matches(ability_row, ABILITY_NCOLS,
                                                         BEFORE_GAIN_CELLS[content]):
        raise CeltieBalanceError("leader growth must be derived from the uncapped ability row")
    row = [CODE, "0", ""] + list(ability_row[5:])
    row[111] = row[112] = LEADER_STRENGTH
    if len(row) != LEADER_NCOLS or (row[3], row[95], row[100], row[102], row[107], row[108]) != (
            "1", "134", "(None)", GAIN_UID, content, "5"):
        raise AssertionError("unexpected leader growth row shape")
    return row


def leader_rows(rows: list[list[str]], ability_before: list[list[str]]) -> list[list[str]]:
    """队长原 6 行逐字保留，追加两行「每层星风心得 → 风队能力伤害 / 攻击力 2.5%」。"""
    if len(rows) != len(LEADER_KINDS) or any(len(row) != LEADER_NCOLS for row in rows):
        raise CeltieBalanceError(f"leader_ability {CID}: expected {len(LEADER_KINDS)}×{LEADER_NCOLS} rows")
    if tuple(row[45] for row in rows) != LEADER_KINDS or any(row[95] for row in rows):
        raise CeltieBalanceError(f"leader_ability {CID}: layout drifted (or growth rows already present)")
    return deepcopy(rows) + [leader_growth_row(ability_before[index]) for index in GAIN_ROWS]


def row_gate_problems(table: str, row: list[str]) -> list[str]:
    problems = [f"legality: {p}" for p in L.client_legality_problems(table, row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems(table, row)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems(table, row, ELEMENT)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, INVOKE_STRING_KEYS, kind=table)]
    return problems


def required_capabilities(ability: list[list[str]], leader: list[list[str]], cas_keys) -> list[str]:
    caps = {cap for row in ability for cap in L.required_client_capabilities("ability", row)}
    caps |= {cap for row in leader for cap in L.required_client_capabilities("leader_ability", row)}
    caps |= {cap for key in cas_keys for cap in L.required_client_capabilities("custom_ability_string", [key])}
    return sorted(caps)


# ------------------------------------------------------------------ 文案

def _single_text(rows: list[list[str]], key: str) -> str:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise CeltieBalanceError(f"{key}: expected one single-column row")
    return rows[0][0]


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    if tuple(_single_text(rows, CAS_LEADER).split("\n")) != LEADER_LINES_BEFORE:
        raise CeltieBalanceError(f"{CAS_LEADER}: unexpected panel text")
    return [["\n".join(LEADER_LINES_AFTER)]]


def a3_text(rows: list[list[str]]) -> list[list[str]]:
    lines = _single_text(rows, CAS_A3).split("\n")
    if len(lines) != A3_LINES or lines[-1] != A3_LAST_BEFORE:
        raise CeltieBalanceError(f"{CAS_A3}: unexpected panel text layout")
    if any(not line.startswith(MAIN_ICON) for line in lines):
        raise CeltieBalanceError(f"{CAS_A3}: main-position slot lines must start with the main icon")
    lines[-1] = A3_LAST_AFTER
    return [["\n".join(lines)]]


def _replace_desc(text: str, label: str) -> str:
    if text != OLD_DESC:
        raise CeltieBalanceError(f"{label}: skill description is not the reviewed text")
    return NEW_DESC


def text_problems() -> list[str]:
    problems = []
    if OLD_DESC.count(DESC_ANCHOR) != 1:
        problems.append("description anchor is not unique")
    for line in (*LEADER_LINES_AFTER, A3_LAST_AFTER, NEW_DESC):
        problems += [f"{line[:24]}…: {p}" for p in KL.panel_problems(line)]
        if "／" in line:
            problems.append(f"{line[:24]}…: 多条不用「／」")
    return problems


# ------------------------------------------------------------------ DSL

def _commands(node, out: list | None = None) -> list[list]:
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


#: live 两档（改前改后相同）的命令计数指纹。
COUNTS = {
    "ConditionalsChangeSkillFlag": 25, "FindAllSubjects": 2, "CreateCondition": 26,
    "ConditionalsFeverMode": 1, "ConditionalsUnifyElement": 1, "BindConditionAccumulationVariable": 3,
    "FindNearSubjects": 6, "MoveBall": 6, "ShowEffect": 84, "HideEffect": 12, "RemoveEvent": 39,
    "StopBall": 12, "HideCharacter": 12, "CreateReferencePoint": 12, "CreateHitArea": 24,
    "CreateNormalAttack": 24,
}


def _bind(block, cap) -> list:
    """Block 首条必须是本角色的心得 Bind，且上限为 ``cap``。返回其参数数组。"""
    if not (isinstance(block, list) and len(block) == 2 and block[0] == "Block" and block[1]):
        raise CeltieBalanceError(f"not a growth branch: {block!r:.120}")
    command = block[1][0]
    if not (isinstance(command, list) and command[0] == "Command"):
        raise CeltieBalanceError("growth branch does not start with a command")
    args = command[1]
    if args[:5] != ["BindConditionAccumulationVariable", -17, GAIN_FLOAT_ID, ["DCUnique", int(GAIN_UID)], 1] \
            or args[5] != cap:
        raise CeltieBalanceError(f"unexpected Starwind binding {args!r:.160}")
    return args


def growth_bindings(tree) -> tuple[list, list, list]:
    """(共鸣∧Fever, 非共鸣∧Fever, 非Fever) 三支的 Bind 参数数组（按结构定位，不按下标猜）。"""
    top = tree[11]
    if not (isinstance(top, list) and top[0] == "Block" and len(top[1]) == 2):
        raise CeltieBalanceError("unexpected top block")
    fever = top[1][1][1]
    if fever[0] != "ConditionalsFeverMode" or len(fever) != 3:
        raise CeltieBalanceError("second top command must be ConditionalsFeverMode")
    then = fever[1]
    if not (then[0] == "Block" and len(then[1]) == 1 and then[1][0][0] == "Command"):
        raise CeltieBalanceError("Fever branch must hold only ConditionalsUnifyElement")
    unify = then[1][0][1]
    if unify[:3] != ["ConditionalsUnifyElement", 4, 6] or len(unify) != 5:
        raise CeltieBalanceError("Fever branch must gate wind resonance (UnifyElement 4, 6)")
    return unify[3], unify[4], fever[2]


def revise_tree(tree, level: str) -> tuple[list, dict[str, Any]]:
    """技能树 → 新树（深拷贝）：只把共鸣∧Fever 支的心得 Bind 上限 2147483647 → 10。"""
    out = deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl"):
        raise CeltieBalanceError(f"skill {level}: unexpected root")
    if command_counts(out) != COUNTS:
        raise CeltieBalanceError(f"skill {level}: command counts drifted")
    resonant, plain, calm = growth_bindings(out)
    target = _bind(resonant, OLD_SKILL_CAP)
    _bind(plain, 0)
    _bind(calm, 0)
    target[5] = NEW_SKILL_CAP
    if command_counts(out) != COUNTS:
        raise AssertionError("revise_tree changed the command set")
    return out, {"level": level, "node": "ConditionalsFeverMode.then → ConditionalsUnifyElement(4,6).then[0]",
                 "command": "BindConditionAccumulationVariable(-17, 14998905, DCUnique 14998902, 1, cap)",
                 "cap": [OLD_SKILL_CAP, NEW_SKILL_CAP], "untouched_caps": [0, 0]}


def dsl_gate_problems(tree) -> list[str]:
    """contract 要求的四道 DSL 门 + AMF3 往返。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


# ------------------------------------------------------------------ 入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {key: _checked(read, *key) for key in BEFORE}
    problems = text_problems()
    if problems:
        raise CeltieBalanceError(f"panel text rejected: {problems}")

    ability_before = inputs["ability", ABILITY_KEY]
    ability = ability3_rows(ability_before)
    leader = leader_rows(inputs["leader", CID], ability_before)
    for table, rows in (("ability", ability), ("leader_ability", leader)):
        for index, row in enumerate(rows):
            problems = row_gate_problems(table, row)
            if problems:
                raise CeltieBalanceError(f"{table}#{index} rejected: {problems}")

    cas = {CAS_LEADER: leader_text(inputs["cas", CAS_LEADER]), CAS_A3: a3_text(inputs["cas", CAS_A3])}
    caps = required_capabilities(ability, leader, cas)
    if caps != sorted(CAPABILITIES):
        raise CeltieBalanceError(f"capabilities {caps} != {CAPABILITIES}")

    text = inputs["text", CID]
    if len(text) != 1 or len(text[0]) != 12:
        raise CeltieBalanceError(f"character_text {CID}: expected one 12-column row")
    for col in TEXT_DESC_COLUMNS:
        text[0][col] = _replace_desc(text[0][col], f"character_text c{col}")

    action = inputs["action", CODE]
    if [inner for inner, _fields in action] != ["1", "2"]:
        raise CeltieBalanceError(f"action_skill {CODE}: inner keys changed")
    new_action = []
    for inner, fields in action:
        fields = list(fields)
        if fields[7] != PROGRAMS[inner]:
            raise CeltieBalanceError(f"action_skill {CODE}/{inner}: program {fields[7]!r}")
        fields[1] = _replace_desc(fields[1], f"action_skill {inner} c1")
        new_action.append((inner, fields))

    server = inputs["server_text", CID]
    if len(server) != 1 or len(server[0]) != 12:
        raise CeltieBalanceError(f"server character_text {CID}: expected one 12-column row")
    for col in TEXT_DESC_COLUMNS:
        server[0][col] = _replace_desc(server[0][col], f"server character_text [{col}]")

    trees, tree_notes = {}, []
    for level, program in PROGRAMS.items():
        tree, note = revise_tree(inputs["dsl", program], level)
        problems = dsl_gate_problems(tree)
        if problems:
            raise CeltieBalanceError(f"skill {level} rejected: {problems}")
        trees[program] = tree
        tree_notes.append(note)
    if trees[PROGRAMS["1"]] != trees[PROGRAMS["2"]]:
        raise CeltieBalanceError("skill tiers diverged after revision")

    return {
        "ability": {ABILITY_KEY: ability},
        "leader": {CID: leader},
        "cas": cas,
        "text": {CID: text},
        "table": {},
        "action": {CODE: new_action},
        "dsl": trees,
        "server_text": {CID: server},
        "new_programs": [PROGRAMS["1"], PROGRAMS["2"]],
        "notes": _notes(tree_notes),
    }


def _notes(tree_notes: list) -> dict[str, Any]:
    return {
        "character": f"{CID} {CODE} 希尔媞「追逐光影的课后时光」（校园，风）",
        "source": "wf_balance_20260927b_celtie.py",
        "basis": ["第二批施工口径 A1–A5（作者 2026-09-27 拍板）", "growth_design.json id=149989 + critic C10",
                  "第二批方案-待拍板.md 表一 149989 行"],
        "changes": {
            f"ability:{ABILITY_KEY}#6": "D134 心得每层 → 风队能力伤害：c102 (None)→10，c113/c114 25000→8000",
            f"ability:{ABILITY_KEY}#7": "D134 心得每层 → 风队攻击力：c102 (None)→10，c113/c114 25000→5000",
            f"leader_ability:{CID}#6": "新增：[CODE,'0','']+能力3#6[5:]，c100 (None)，c107=154，c111/c112=2500",
            f"leader_ability:{CID}#7": "新增：[CODE,'0','']+能力3#7[5:]，c100 (None)，c107=0，c111/c112=2500",
            "dsl": tree_notes,
            CAS_LEADER: {"line4": LEADER_LINE4_AFTER, "line6_added": LEADER_LINE_ADDED},
            CAS_A3: {"line7": A3_LAST_AFTER.strip()},
            "skill_description": {"replaced": DESC_ANCHOR, "with": DESC_ANCHOR_AFTER,
                                  "places": ["action_skill 1/2 c1", "character_text c5/c7",
                                             "server cdndata/character_text.json [5]/[7]"]},
        },
        "frequency": {
            "estimate": "3 分钟：技能能量 570/520、开局 +50%、Fever 中每 7 连击风队 +0.7% 槽（CT 0.7 秒），"
                        "3 名风主位约 27–36 次施技，其中 Fever 中约 13–20 次；每次 +3 层心得（队长 2 + 能力3 1）"
                        "⇒ 约 40–60 层",
            "tier": "口径 A2 按实际次数、不按事件名称：这两行每层心得成长一步，3 分钟约 40–60 层"
                    "（仅队长 629 的 2 层/次也有 26–40 层）⇒ ≥30 ⇒ 每步 ×1/10：25% → 2.5%",
            "deviation_from_design": "设计稿按「每层固有＝低频」标签取 1/5（5%）；口径 A2 不按事件名称，改取 1/10。"
                                     "上一轮曾按施技次数（13–20）取 1/5，复核指出与同批 hibiki/kyle/magnus/nephtim "
                                     "按层数计步不一致，已改。若作者改判为按施技次数：LEADER_STRENGTH 与 "
                                     "wf_celtie_fever_leader.GAIN_GROWTH_STRENGTH 改 5000、队长面板第 6 行改 +5%",
            "growth_3min_50_layers": {"before": "风队能力伤害 +1250%、攻击力 +1250%（仅 Fever 中）",
                                      "after": "队长 +125% / +125% ＋ 能力3 +80% / +50%（10 层封顶）"
                                               "＝ +205% / +175%；技能倍率 75+10×min(层,10) ≤ 175 倍（原 75+10×层）"},
        },
        "precedents": {
            "ability_limit": "官方 1611231..6 blackflower_wiz_smr22：D134 + c102=10",
            "dsl_cap": "官方 blackflower_wiz_smr22_1/_2：BindConditionAccumulationVariable(-17, vid, DCUnique 11, 1, 10)",
            "leader_d134": "官方 leader 161123/141081（D134，目标 5）",
            "leader_154": "官方 leader 151021#2（c107=154）；live 139995#6（D134+(None)+154+目标5）",
            "leader_pre12": "本角色队长 #3–#5 已上线（口径 A4 列名 pre12 希尔媞），但都是瞬发行",
            "leader_during_plus_pre12": ("无 live 先例：1.4.1049 队长表 pre12 只在 149989#3–#5、149999#10、129986#3，"
                                         "全是瞬发；设计稿引的 169989 队长持续行（D4+pre12）已不存在。"
                                         "前置 puller 与持续块各自解析、单件均有先例，C7050 风险低；"
                                         "须真机打开角色页 / 队长页，并确认 #6/#7 只在风共鸣 Fever 中生效、超过 10 层仍随层成长"),
        },
        "kept": {
            f"ability:{ABILITY_KEY}#2": "Fever 中每 7 连击风队攻击 +70%（限 10 次）——有上限，本批不动",
            f"ability:{ABILITY_KEY}#3, ability:1499892#2/#3": "技能槽 / Fever 槽回填（口径 A6 充能暂缓）",
            "skill_down": "技能削韧保留（口径 B5：Boss/备用两支互斥，实际 28）",
            "unique_condition:14998902": "固有上限 2147483647 不动（压低会把队长无上限行一起封死）",
        },
        "generator": ("wf_celtie_fever_abilities.GAIN_BONUS_LIMIT/GAIN_BONUS_STRENGTH、"
                      "wf_celtie_fever_leader.gain_growth_row（队长 6→8 行）、"
                      "wf_celtie_skill_growth.GAIN_MAX_LAYERS=10、wf_campus_panel_text._CELTIE；"
                      "生成器输出 == revise() 输出（tests/test_balance_20260927b_celtie.py）"),
        "new_programs": "候选 manifest skills={}（两棵技能树文件在 roots.common 但未登记）⇒ 同 rolfwt26 先例作为程序登记",
        "capabilities": list(CAPABILITIES),
        "candidate_preexisting_drift": {
            f"leader_ability:{CID}": "候选仍是 09-11 初版 3 行（32/56/during4 154），live 为 fever 版 6 行；"
                                     "暂存整键替换 ⇒ 候选收敛为 live 6 行 + 本批 2 行（同 09-25 回写 1499893 的做法）",
            "ability:1499891/1499892/1499894-6": "候选仍是初版，本批不触碰（既有漂移，不在本次 splice 范围）",
            "manifest.required_capabilities": "候选为 []，本批补登 CAPABILITIES（live 早已依赖）",
        },
        "donor_replay_check": ("wf_midautumn_kit_kuro 以 live:1499893#1（I724 行）作 donor；本批只改 #6/#7，"
                               "#1 与行序不变；队长只在末尾追加，已有下标不移位 ⇒ 无需外部钉格"),
        "preexisting_panel_for_author": ("desc_override_wind_spgirl_campus_1 第 2 行（技能强化 536）写了"
                                         "「能力伤害提升100%…持续15秒」，与口径 D「技能强化（536/704）条目不写数字与秒数」"
                                         "不符；该文本早于本批、不在本单元改动范围，未改，是否统一整改由作者决定"),
        "runtime_verified": False,
    }

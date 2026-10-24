# -*- coding: utf-8 -*-
"""2026-09-27 平衡批次：冰雪罗尔夫 179999 ``black_wolf_knight_wt26``（火）的键级修订（纯函数）。

作者 2026-09-27 确认的规格：

1. **超级Fever 加门槛**。超级Fever 没有独立状态，就是两档技能 DSL
   （``rare5/black_wolf_knight_wt26$black_wolf_knight_wt26_1/_2``，两档逐字相同）里
   ``ConditionalsFeverMode`` 的 Fever 分支：``AddFeverPoint 200`` ＋ ``FindAllSubjects(0,33)``
   全队攻/PF/技伤/直击/能伤 +350%（600 帧）＋ ``ChangeFieldAssets`` 换六色 Fever 条。
   现在把这整套包进 ``ConditionalsChangeSkillFlag(1, then, ["Block", []])``：旗号 1 由能力 3
   ``1799993#4``（kind 536 ChangeSkillFlag，前置 202 仅主位 ＋ 火·编成≥6）打开，此前 DSL 没读它。
   旗号为假时 Fever 中施放不再触发超级Fever、不加 Fever 槽；非 Fever 部分（护盾/再生/增伤/贯通）照旧。
   分支形状按项目先例：then/else 都是 ``["Block", …]``，else 写空 Block
   （不写 ``["DoNothing"]``，那是 IfTargetNotFound 的枚举，塞进表达式位 ⇒ F1009）。
2. **新增回复**（同在旗号为真的 Fever 分支内，每次 Fever 中施放都执行）：
   在超级Fever 三件之后追加一个全队 ``FindAllSubjects(0, 33)``（技能里现有的全队写法），块内
   ``CreateRatioHeal(0, 2, 5%)``（p1=2 ⇒ ``RatioHealKind.UseHealeesMaximumHealthPoint``，按受疗者
   **自己的**最大生命值；ActionEvaluator.as:3208-3215、RatioHealCalculator.as case 1）＋
   ``CreateCondition(0, ACRegeneration(600 帧, 每跳 53))``（每 120 帧一跳、首跳第 30 帧 ⇒ 5 跳合计 265，
   ≈罗尔夫 Lv100 生命 3295 的 8%）。官方先例：``asahina_mikuru_1`` 的 ``FindAllSubjects(0,33)``
   块内正是 CreateRatioHeal(0,2,…) ＋ CreateCondition(0, ACRegeneration)；无特攻的
   CreateRatioHeal 形状 ``[] / [{0,0}] / GenericHealHitEffect`` 取 ``alk_1anv_1``。
   再生叠加规则：条件 ID ＝ 来源 ＋ 命中率 ＋ 时长 ＋ 叠加上限 ＋ 内容值（``ConditionId_Impl_``：
   ``REG-<每跳值>``）⇒ 同一技能重复施放是同一 ID，只刷新不叠层；与顶层给体力最低者的
   ``ACRegeneration(600,100)`` 内容值不同 ⇒ 两条并存（``getTotalRegeneration`` 求和），不互相覆盖。
3. **文案**：能力 3 第 5 行 c70 现指 ``superfever_desc_wt26``（不在命名空间）→ 新建
   ``change_skill_black_wolf_knight_wt26`` 并改指。技能强化条目（536）按裁决 §3 不写数字与时间
   （``wf_midautumn_kitlib.panel_problems(skill_flag=True)``），所以新文案＝原说明去掉「350%(10秒)」
   ＋追加回复与再生；数字（350%/10秒/5%）写进技能描述。技能描述 5 处（action_skill 两档 c1、
   character_text c5/c7、服务端 cdndata/character_text.json [5]/[7]）把「Fever状态中使用时：…」
   改为注明「火属性共鸣时，自身在主位且于Fever状态中使用」并追加回复与再生。
4. 候选包 ``black_wolf_knight_wt26`` 不含这两棵技能 DSL（manifest ``skills={}``）⇒ 放进
   ``new_programs``；CAS 新键由暂存脚本写进候选认领。候选与 live 的既有漂移（``1799991#1``
   c30/c31/c49）不动，见 ``notes.open_points``。候选服务端镜像 character_text 179999 行是换皮前
   旧文（11/12 列与 live 不同，:data:`CANDIDATE_STALE_SERVER_MIRROR`）；暂存整行替换，会顺带把
   [5]/[7] 以外 9 列刷回 live 值，同样记进 ``notes.open_points``。

接口见 ``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``：:func:`revise` 只经 ``read`` 读 live，
开头按 :data:`BEFORE` 摘要校验（漂移即抛 :class:`RolfWt26BalanceError`，fail closed），不改 ``read``
的返回对象。本角色没有 kit 生成器（技能树由 1.4.3xx 一次性装配脚本落盘），无生成器一致性要求。
本模块不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl
import wf_midautumn_kitlib as KL

CID = "179999"
CODE = "black_wolf_knight_wt26"
PACKAGES = ["black_wolf_knight_wt26"]
#: 候选现值 0.1.1（``work/character_packs/black_wolf_knight_wt26/package/manifest.json``）→ 递增。
PACKAGE_VERSION = {"black_wolf_knight_wt26": "0.1.2"}
CAPABILITIES: list[str] = []

ELEMENT = 0                      # 内部 ElementKind：火（character c3 = 0）
ABILITY_KEY = CID + "3"          # 能力 3
FLAG_ROW = 4                     # 第 5 行：kind 536
OLD_CAS_KEY = "superfever_desc_wt26"
CAS_KEY = "change_skill_" + CODE
PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in ("1", "2")}

ABILITY_NCOLS = 126
#: 536 行的门：前置 1 = 202（持有者为主位），前置 2 = kind 2 编成人数 ≥6 ＋ Red（火属性共鸣）。
FLAG_ROW_GATE = {47: "536", 6: "202", 13: "2", 16: "600000", 17: "600000", 18: "Red"}

# ------------------------------------------------------------------ DSL 常量

SKILL_FLAG = 1                   # 536 = ChangeSkillFlag ⇒ 旗号 1（InstantAbilitySource.as:5018）
TEAM_BINDING = 0                 # 技能里现有全队写法 FindAllSubjects(0, 33, …)
TEAM_SELECTOR = 33
HEAL_BASIS = 2                   # CreateRatioHeal p1：2 = UseHealeesMaximumHealthPoint（按目标最大生命值）
HEAL_RATIO = 0.05
REGEN_FRAMES = 600
REGEN_PER_TICK = 53
CONDITION_TARGET_KIND = 3        # CreateCondition p10：选择器 33 = Member ⇒ 3（与技能里现有各条一致）

SUPER_FEVER_POINT = [{"min": 200.0, "max": 200.0}]
SUPER_FEVER_ACS = ("ACAttackPoint", "ACPowerFlipDamage", "ACSkillDamage", "ACDirectDamage", "ACAbilityDamage")
SUPER_FEVER_FRAMES = [{"min": 600.0, "max": 600.0}]
SUPER_FEVER_VALUE = [{"min": 3.5, "max": 3.5}]
SUPER_FEVER_GAUGE = ["Some", "battle/field_object/black_wolf_knight_wt26/fever_gauge/superfever_gauge"]
FEVER_BRANCH_BEFORE = ("AddFeverPoint", "FindAllSubjects", "ChangeFieldAssets")
TOP_BEFORE = ("StopBall", "ShowEffect", "ShakeCamera", "FindAllSubjects", "FindAllSubjects",
              "FindAllSubjects", "FindAllSubjects", "ConditionalsFeverMode")
FEVER_INDEX = 7

RATIO_HEAL = ["Command", ["CreateRatioHeal", TEAM_BINDING, HEAL_BASIS,
                          [{"min": HEAL_RATIO, "max": HEAL_RATIO}], [], [{"min": 0, "max": 0}],
                          ["GenericHealHitEffect"]]]
REGENERATION = ["Command", ["CreateCondition", TEAM_BINDING,
                            [["ACRegeneration", [{"min": REGEN_FRAMES, "max": REGEN_FRAMES}],
                              [{"min": REGEN_PER_TICK, "max": REGEN_PER_TICK}]]],
                            [{"min": 1, "max": 1}], ["GenericConditionHitEffect"], True, False, "", None,
                            False, CONDITION_TARGET_KIND, [{"min": 1, "max": 1}], False]]
TEAM_RECOVERY = ["Command", ["FindAllSubjects", TEAM_BINDING, TEAM_SELECTOR, [], [], [], [], [],
                             ["DoNothing"], ["Block", [RATIO_HEAL, REGENERATION]]]]

#: live 两档（修订前）的命令计数指纹。
COUNTS_BEFORE = {
    "StopBall": 1, "ShowEffect": 1, "ShakeCamera": 1, "FindAllSubjects": 5, "CreateBarrier": 1,
    "CreateCondition": 4, "ConditionalsFeverMode": 1, "AddFeverPoint": 1, "ChangeFieldAssets": 1,
}
COUNTS_AFTER = dict(COUNTS_BEFORE, FindAllSubjects=6, CreateCondition=5, CreateRatioHeal=1,
                    ConditionalsChangeSkillFlag=1)

# ------------------------------------------------------------------ 文案

OLD_CAS_TEXT = ("Fever状态中发动技能时，触发超级Fever：队伍全体的攻击力、强化弹射伤害、技能伤害、"
                "直接攻击伤害、能力伤害提升350%(10秒)")
CAS_REMOVED = "350%(10秒)"
CAS_APPENDED = "，同时为队伍全体回复生命值并赋予再生效果"
NEW_CAS_TEXT = OLD_CAS_TEXT.replace(CAS_REMOVED, "") + CAS_APPENDED

OLD_DESC = ("赋予队长护盾、体力最低角色再生／火属性和风属性角色的技能伤害与强化弹射伤害提升150%"
            "／队伍全体贯通(12.5秒)／Fever状态中使用时：Fever槽增加200，并触发超级Fever ※技能无后摇")
DESC_OLD_SEGMENT = "Fever状态中使用时：Fever槽增加200，并触发超级Fever"
DESC_NEW_SEGMENT = ("火属性共鸣时，自身在主位且于Fever状态中使用：Fever槽增加200，并触发超级Fever"
                    "（队伍全体的攻击力、强化弹射伤害、技能伤害、直接攻击伤害、能力伤害提升350%(10秒)），"
                    "同时为队伍全体回复最大生命值5%的生命值并赋予再生效果(10秒)")
NEW_DESC = OLD_DESC.replace(DESC_OLD_SEGMENT, DESC_NEW_SEGMENT)

#: character_text 行里技能说明所在列（觉醒前 / 觉醒后）。
TEXT_DESC_COLUMNS = (5, 7)

# ------------------------------------------------------------------ 输入基线

#: ``{(kind, key): sha256}``：revise() 读取的每一项在 live 上的摘要（2026-09-27 只读采集）。
#: fixture ``tests/fixtures/balance_20260927_rolfwt26.json`` 同源。
BEFORE: dict[tuple[str, str], str] = {
    ("ability", ABILITY_KEY): "f6c977e99283c6deb4e6e19567a5d68a0473fcd6151c5abb46ec04fec01d3cf4",
    ("cas", OLD_CAS_KEY): "900e2cd7f367de6ab5abfd22f2e697d6a34bf96c4abfcc4c7322062b03bf3d26",
    ("text", CID): "b3d76db8c9a24cee01cc95d8d8d824720a565001d31bf4e2a23bae444d791600",
    ("action", CODE): "f0b072cd510853233b14cceb1f0316a02784751c912ed1c02e66a0fa878a74cc",
    ("dsl", PROGRAMS["1"]): "a207d03b41112d87ee94968282677bd945a6cc5858bb7a9f9a2d927af6fe25e5",
    ("dsl", PROGRAMS["2"]): "a207d03b41112d87ee94968282677bd945a6cc5858bb7a9f9a2d927af6fe25e5",
    ("server_text", CID): "b3d76db8c9a24cee01cc95d8d8d824720a565001d31bf4e2a23bae444d791600",
}

#: 候选包与 live 的既有漂移（本批不动，写进 notes.open_points）：``1799991#1`` 候选 / live。
CANDIDATE_PREEXISTING_DRIFT = {"key": CID + "1", "row": 1,
                               "cells": {"30": ["2500000", "3500000"], "31": ["2500000", "3500000"],
                                         "49": ["(None)", "Green"]}}

#: 候选服务端镜像 ``roots/server/cdndata/character_text.json`` 的 179999 行仍是换皮前（黑狼自由骑士）
#: 旧文，与 live ``assets/cdndata/character_text.json`` 12 列中 11 列不同（只有 [0] 名字相同）。
#: 暂存 ``Plan.server_text`` → ``RevisionCandidate.server_character_row`` 整行替换 ``rows[cid]``，
#: 所以本批写候选时除 [5]/[7] 技能说明外，还会把下表 ``overwritten_beyond_revision`` 9 列顺带
#: 刷成 live 值——终态（候选＝live＋本修订）正确，只是候选 diff 会多出这些列。客户端侧
#: ability 1799993 / character_text 179999 / action_skill 三键候选与 live 逐字节相同，无此问题。
#: 值为 ``[候选, live]``（2026-09-27 只读采集；长文列只记开头）。
CANDIDATE_STALE_SERVER_MIRROR = {
    "file": "cdndata/character_text.json", "key": CID,
    "differing_columns": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
    "overwritten_beyond_revision": (1, 2, 3, 4, 6, 8, 9, 10, 11),
    "cells": {
        "1": ["LUOERFU", "ROLF"],
        "2": ["曾为犬族带来过无数胜利的骑士。而现在…", "曾为犬族带来过无数胜利的骑士，如今行至北境雪国…"],
        "3": ["黑狼自由骑士", "雪夜里的炉火"],
        "4": ["古剑斩", "炉心颂歌"],
        "5": ["向距离最近的敌人发动斩击及爆击…", "赋予队长护盾、体力最低角色再生…"],
        "6": ["古剑斩＋", "炉心颂歌＋"],
        "7": ["向距离最近的敌人发动斩击及爆击…", "赋予队长护盾、体力最低角色再生…"],
        "8": ["古剑斩＋＋", "(None)"],
        "9": ["向距离最近的敌人发动斩击及爆击…", "(None)"],
        "10": ["雪夜里的炉火", "月耀守护"],
        "11": ["上田耀司", "AI声线"],
    },
}


class RolfWt26BalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ DSL

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


def _names(block) -> list[str]:
    if not (isinstance(block, list) and len(block) == 2 and block[0] == "Block" and isinstance(block[1], list)):
        raise RolfWt26BalanceError(f"not a Block: {block!r:.160}")
    return [cmd[1][0] if isinstance(cmd, list) and cmd and cmd[0] == "Command" else repr(cmd)[:40]
            for cmd in block[1]]


def fever_node(tree) -> list:
    """顶层 ``ConditionalsFeverMode`` 的参数数组（``[name, then, else]``；修订前后顶层命令序列相同）。"""
    top = tree[11]
    if tuple(_names(top)) != TOP_BEFORE:
        raise RolfWt26BalanceError(f"top commands {_names(top)}")
    return top[1][FEVER_INDEX][1]


def _check_super_fever(commands: list, level: str) -> None:
    """Fever 分支原有三件逐项核对（数值/选择器/AC 列表/场地资产）。"""
    add, find, field = commands
    if add != ["Command", ["AddFeverPoint", SUPER_FEVER_POINT]]:
        raise RolfWt26BalanceError(f"skill {level}: AddFeverPoint changed: {add!r:.160}")
    args = find[1]
    if args[:3] != ["FindAllSubjects", TEAM_BINDING, TEAM_SELECTOR] or args[3:8] != [[], [], [], [], []] \
            or args[8] != ["DoNothing"] or _names(args[9]) != ["CreateCondition"]:
        raise RolfWt26BalanceError(f"skill {level}: super-fever FindAllSubjects changed: {args[:9]!r:.200}")
    cond = args[9][1][0][1]
    acs = cond[2]
    if cond[1] != TEAM_BINDING or cond[10] != CONDITION_TARGET_KIND \
            or tuple(ac[0] for ac in acs) != SUPER_FEVER_ACS \
            or any(ac[1] != SUPER_FEVER_FRAMES or ac[2] != SUPER_FEVER_VALUE for ac in acs):
        raise RolfWt26BalanceError(f"skill {level}: super-fever CreateCondition changed")
    if field[1][0] != "ChangeFieldAssets" or field[1][13] != SUPER_FEVER_GAUGE:
        raise RolfWt26BalanceError(f"skill {level}: super-fever ChangeFieldAssets changed")


def gated_fever_branch(super_fever: list) -> list:
    """Fever 分支新形状：``[ConditionalsChangeSkillFlag(1, [原三件…, 全队回复], [])]``。"""
    then = ["Block", copy.deepcopy(super_fever) + [copy.deepcopy(TEAM_RECOVERY)]]
    return ["Block", [["Command", ["ConditionalsChangeSkillFlag", SKILL_FLAG, then, ["Block", []]]]]]


def revise_tree(tree, level: str) -> tuple[list, dict[str, Any]]:
    """live 技能树 → 新树（深拷贝）。结构不符直接抛错。"""
    out = copy.deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl"):
        raise RolfWt26BalanceError(f"skill {level}: unexpected root")
    before = command_counts(out)
    if before != COUNTS_BEFORE:
        raise RolfWt26BalanceError(f"skill {level}: commands {before} != {COUNTS_BEFORE}")
    fever = fever_node(out)
    if len(fever) != 3 or fever[2] != ["Block", []]:
        raise RolfWt26BalanceError(f"skill {level}: ConditionalsFeverMode else-branch is not empty")
    then = fever[1]
    if tuple(_names(then)) != FEVER_BRANCH_BEFORE:
        raise RolfWt26BalanceError(f"skill {level}: fever branch {_names(then)} != {FEVER_BRANCH_BEFORE}")
    _check_super_fever(then[1], level)

    fever[1] = gated_fever_branch(then[1])

    after = command_counts(out)
    if after != COUNTS_AFTER:
        raise RolfWt26BalanceError(f"skill {level}: revised commands {after} != {COUNTS_AFTER}")
    changed = {name: [before.get(name, 0), after.get(name, 0)]
               for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)}
    return out, {"level": level, "gate": f"ConditionalsChangeSkillFlag({SKILL_FLAG})",
                 "gated": list(FEVER_BRANCH_BEFORE), "appended": "FindAllSubjects(0,33){CreateRatioHeal, "
                 "CreateCondition(ACRegeneration)}", "counts_changed": changed}


def dsl_gate_problems(tree) -> list[str]:
    """contract 要求的四道 DSL 门 + AMF3 往返。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


# ------------------------------------------------------------------ 词条 / 文案

def row_gate_problems(row: list[str]) -> list[str]:
    """contract 要求的词条行门禁（合法性 / 声明块字段 / 元素列 / 629 文案键 / capability）＋ 536 文案键。"""
    problems = [f"legality: {p}" for p in L.client_legality_problems("ability", row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems("ability", row)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems("ability", row, ELEMENT)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, {CAS_KEY})]
    if row[47] == "536" and row[70] != CAS_KEY:
        problems.append(f"536 string_id {row[70]!r} != {CAS_KEY!r}（MasterStringMap.get 缺键 = C8601）")
    caps = L.required_client_capabilities("ability", row)
    if sorted(caps) != sorted(CAPABILITIES):
        problems.append(f"capabilities {caps} != {CAPABILITIES}")
    return problems


def revise_ability(rows: list[list[str]]) -> list[list[str]]:
    out = copy.deepcopy(rows)
    if len(out) != 5 or any(len(r) != ABILITY_NCOLS for r in out) \
            or [r[47] for r in out] != ["629", "211", "3", "6", "536"]:
        raise RolfWt26BalanceError(f"ability {ABILITY_KEY}: expected 5×126 rows (629, 211, 3, 6, 536)")
    row = out[FLAG_ROW]
    wrong = {col: row[col] for col, value in FLAG_ROW_GATE.items() if row[col] != value}
    if wrong:
        raise RolfWt26BalanceError(f"ability {ABILITY_KEY}#{FLAG_ROW}: gate cells changed {wrong}")
    if row[70] != OLD_CAS_KEY:
        raise RolfWt26BalanceError(f"ability {ABILITY_KEY}#{FLAG_ROW}: c70 {row[70]!r} != {OLD_CAS_KEY!r}")
    row[70] = CAS_KEY
    return out


def _replace_desc(text: str, label: str) -> str:
    if text != OLD_DESC:
        raise RolfWt26BalanceError(f"{label}: skill description is not the reviewed text")
    return NEW_DESC


def _text_problems() -> list[str]:
    problems = []
    if OLD_DESC.count(DESC_OLD_SEGMENT) != 1 or OLD_CAS_TEXT.count(CAS_REMOVED) != 1:
        problems.append("text anchors are not unique")
    problems += [f"cas: {p}" for p in KL.panel_problems(NEW_CAS_TEXT, skill_flag=True)]
    problems += [f"desc: {p}" for p in KL.panel_problems(NEW_DESC)]
    return problems


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        got = digest(value)
        if got != want:
            raise RolfWt26BalanceError(f"live drift: {kind}:{key} sha256 {got} != reviewed {want}")
        inputs[kind, key] = copy.deepcopy(value)
    try:
        existing = read("cas", CAS_KEY)
    except KeyError:
        existing = None
    if existing is not None:
        raise RolfWt26BalanceError(f"{CAS_KEY} already exists in live: {existing!r:.120}")

    problems = _text_problems()
    if problems:
        raise RolfWt26BalanceError(f"panel text rejected: {problems}")

    ability = revise_ability(inputs["ability", ABILITY_KEY])
    problems = row_gate_problems(ability[FLAG_ROW])
    if problems:
        raise RolfWt26BalanceError(f"ability {ABILITY_KEY}#{FLAG_ROW} rejected: {problems}")

    if inputs["cas", OLD_CAS_KEY] != [[OLD_CAS_TEXT]]:
        raise RolfWt26BalanceError(f"{OLD_CAS_KEY}: text is not the reviewed one")
    cas = [[NEW_CAS_TEXT]]

    text = inputs["text", CID]
    if len(text) != 1 or len(text[0]) != 12:
        raise RolfWt26BalanceError(f"character_text {CID}: expected one 12-column row")
    for col in TEXT_DESC_COLUMNS:
        text[0][col] = _replace_desc(text[0][col], f"character_text c{col}")

    action = inputs["action", CODE]
    if [inner for inner, _fields in action] != ["1", "2"]:
        raise RolfWt26BalanceError(f"action_skill {CODE}: inner keys changed")
    new_action = []
    for inner, fields in action:
        fields = list(fields)
        if fields[7] != PROGRAMS[inner]:
            raise RolfWt26BalanceError(f"action_skill {CODE}/{inner}: program {fields[7]!r}")
        fields[1] = _replace_desc(fields[1], f"action_skill {inner} c1")
        new_action.append((inner, fields))

    server = inputs["server_text", CID]
    if len(server) != 1 or len(server[0]) != 12:
        raise RolfWt26BalanceError(f"server character_text {CID}: expected one 12-column row")
    for col in TEXT_DESC_COLUMNS:
        server[0][col] = _replace_desc(server[0][col], f"server character_text [{col}]")

    trees, tree_notes = {}, []
    for level, program in PROGRAMS.items():
        tree, ev = revise_tree(inputs["dsl", program], level)
        problems = dsl_gate_problems(tree)
        if problems:
            raise RolfWt26BalanceError(f"skill {level} rejected: {problems}")
        ev["amf3_bytes"] = {"before": len(wf_dsl.encode_amf3(inputs["dsl", program])),
                            "after": len(wf_dsl.encode_amf3(tree))}
        trees[program] = tree
        tree_notes.append(ev)
    if trees[PROGRAMS["1"]] != trees[PROGRAMS["2"]]:
        raise RolfWt26BalanceError("skill tiers diverged after revision")

    return {
        "ability": {ABILITY_KEY: ability},
        "leader": {},
        "cas": {CAS_KEY: cas},
        "text": {CID: text},
        "table": {},
        "action": {CODE: new_action},
        "dsl": trees,
        "server_text": {CID: server},
        "new_programs": [PROGRAMS["1"], PROGRAMS["2"]],
        "notes": {
            "character": f"{CID} {CODE} 冰雪罗尔夫（火）",
            "skill_dsl": {
                "gate": f"Fever 分支整体包进 ConditionalsChangeSkillFlag({SKILL_FLAG})，else 空 Block；"
                        "旗号 1 = 能力3 1799993#4 kind 536（前置 202 主位 ＋ 火·编成≥6）",
                "gated": ["AddFeverPoint 200", "FindAllSubjects(0,33) 全队攻/PF/技伤/直击/能伤 +350% 600帧",
                          "ChangeFieldAssets 超级Fever 槽"],
                "appended": {"selector": f"FindAllSubjects({TEAM_BINDING},{TEAM_SELECTOR})",
                             "ratio_heal": {"basis": HEAL_BASIS, "ratio": HEAL_RATIO,
                                            "why": "RatioHealKind.UseHealeesMaximumHealthPoint：受疗者自身最大生命值 × 比例 "
                                                   "× (1+回复量提升)，封顶 MAX_CURE"},
                             "regeneration": {"frames": REGEN_FRAMES, "per_tick": REGEN_PER_TICK,
                                              "ticks": 5, "total": 5 * REGEN_PER_TICK,
                                              "why": "每 120 帧一跳、首跳第 30 帧；ConditionId 含内容值 REG-53 ⇒ 重复施放只刷新；"
                                                     "与顶层 ACRegeneration(600,100) 内容值不同 ⇒ 两条并存"}},
                "precedents": ["asahina_mikuru_1 FindAllSubjects(0,33){CreateRatioHeal(0,2,…), "
                               "CreateCondition(0, ACRegeneration)}",
                               "alk_1anv_1 CreateRatioHeal 无特攻形状 [] / [{0,0}] / GenericHealHitEffect",
                               "wf_zantetsu_fever_revision / wf_nephtim_fever_skill：ChangeSkillFlag 与 FeverMode 嵌套"],
                "trees": tree_notes,
            },
            "ability": {"key": ABILITY_KEY, "row": FLAG_ROW, "c70": [OLD_CAS_KEY, CAS_KEY]},
            "custom_ability_string": {"key": CAS_KEY, "text": NEW_CAS_TEXT,
                                      "why": "536 技能强化条目按裁决 §3 不写数字与时间；数字移入技能描述；"
                                             f"旧键 {OLD_CAS_KEY} 留在 live 不动（不在命名空间、改后无引用）"},
            "skill_description": {"replaced": DESC_OLD_SEGMENT, "with": DESC_NEW_SEGMENT,
                                  "places": ["action_skill 1/2 c1", "character_text c5/c7",
                                             "server cdndata/character_text.json [5]/[7]"]},
            "new_programs": "候选 manifest skills={} 不含两档技能树，本批作为新程序写入候选",
            "generator": "无 kit 生成器（技能树来自 work/character_packs/black_wolf_knight_wt26/build_1_4_3xx.py "
                         "一次性装配脚本，依赖旧会话 scratchpad，不可重跑）",
            "capabilities": list(CAPABILITIES),
            "candidate_preexisting_drift": {
                "ability": copy.deepcopy(CANDIDATE_PREEXISTING_DRIFT),
                "server_mirror": {"file": CANDIDATE_STALE_SERVER_MIRROR["file"],
                                  "key": CANDIDATE_STALE_SERVER_MIRROR["key"],
                                  "differing_columns": list(CANDIDATE_STALE_SERVER_MIRROR["differing_columns"]),
                                  "overwritten_beyond_revision":
                                      list(CANDIDATE_STALE_SERVER_MIRROR["overwritten_beyond_revision"]),
                                  "cells": copy.deepcopy(CANDIDATE_STALE_SERVER_MIRROR["cells"])},
            },
            "open_points": [
                f"候选与 live 既有漂移 {CANDIDATE_PREEXISTING_DRIFT['key']}#{CANDIDATE_PREEXISTING_DRIFT['row']}："
                "c30/c31 候选 2500000 / live 3500000，c49 候选 (None) / live Green；本批不动",
                "候选服务端镜像 roots/server/cdndata/character_text.json 的 "
                f"{CANDIDATE_STALE_SERVER_MIRROR['key']} 行是换皮前旧文（LUOERFU／黑狼自由骑士／古剑斩／上田耀司），"
                "与 live 12 列中 11 列不同（列 "
                + ",".join(str(c) for c in CANDIDATE_STALE_SERVER_MIRROR["differing_columns"])
                + "，仅 [0] 相同）；暂存 server_character_row 整行替换 rows[cid]，除本批 [5]/[7] 外还会把列 "
                + ",".join(str(c) for c in CANDIDATE_STALE_SERVER_MIRROR["overwritten_beyond_revision"])
                + " 顺带刷成 live 值（ROLF／雪夜里的炉火／炉心颂歌／月耀守护／AI声线 等）。终态＝live＋本修订，"
                "镜像由此与 live 对齐；候选 diff 里这 9 列是既有漂移的收敛，不是本批改动。客户端 ability 1799993 / "
                "character_text 179999 / action_skill 三键候选与 live 逐字节相同",
                "超级Fever 门槛与全队回复需真机验收：非主位或非火共鸣时 Fever 中施放不应出现六色 Fever 条与回复",
            ],
        },
    }

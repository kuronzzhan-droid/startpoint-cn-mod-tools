# -*- coding: utf-8 -*-
"杰拉德「月耀守护」149999 ``white_wolf_gerald``（光）：2026-09-27 第二批追加（作者 09-27 追加）。\n\n注意：杰拉德（149999 光，白狼骑士）≠ 杰拉尔（129992 水，unicorn_lancer_rose）。\n\n作者原话（2026-09-27，回答第二批的两个待定项）：「杰拉德我是把他的共鸣时强化技能效果造成敌人当前生命值\n百分比伤害且随着技能释放次数每次造成的敌方当前最大生命值不断提高最开始是敌方当前生命值5%,然后是6%-7%以此类推\n当敌方生命值低于最大生命值的5%斩杀放到队长技描述为固定伤害,基诺维不要影响他当前能力的效果,跑」。\n\n按 live 1.4.1051 推导（第二批 ``wf_balance_20260927b_gerald_wolf`` 已发布：队长行7–10 放缓、PF Lv3 削韧、\n技能两档时空侵蚀 Bind 上限 2147483647→10）。行号 0 基（``#n``）。\n\nA. 技能强化（kind 536 ChangeSkillFlag，光属性共鸣前置）在队长技：**live 已如此，无需搬行**。\n   09-25 修订（``wf_gerald_cast_growth.relocate``，manifest snapshot ``skill_enhancement_moved_to_leader``）\n   已把它从能力3 搬到队长末行：``leader_ability:149999#11`` = ``[black_wolf_knight, 0, '']`` + 536、\n   前置 kind 2 光·编成≥6（c7/c8=600000，c9 White）、c68 ``change_skill_white_wolf_gerald``。六个能力键\n   （1499991–1499996）里 0 条 536 ⇒ 能力里没有可删的行，队长 12 行不变，不返回 leader/ability。\n   本模块逐格核对这行与「能力里无 536」（fail closed）。强化分支（``ConditionalsChangeSkillFlag(1)``）只在\n   杰拉德当队长且光属性共鸣时打开；比例伤害、逐次成长与斩杀都只在这支里 ⇒ 「无上限只留在队长技」已成立。\nB. 撤回第二批的封顶：技能两档强化分支 ``BindConditionAccumulationVariable(-17, 360, [DCUnique, 14999903], 1, 上限)``\n   的上限 10 → ``2147483647.0``（浮点，与第二批改前逐字相同；AMF3 29 位整数放不下 ⇒ 编码为 double，\n   整棵树重编码与第二批改前 live 原始字节同哈希 8d323968…/f27b8a14…）。第 n 次强化施技打当前生命值\n   5%+1%×(n−1)，不再封顶。计数固有 14999903「时空侵蚀」（c3 99999999 帧、c4 2147483647）本来就没封，不动。\nC. 斩杀：**已存在，不动**。同一分支 ``FindNearSubjects(-18, 1, 49, DoNothing, 301)`` →\n   ``ConditionalsHealthPointRatioOf(301, 5, 成长比例伤害, CreateRatioAttack(301, 1, 100%))``：原生 HP 条件\n   第一分支为「≥最大生命值 5%」，第二分支严格「<5%」时打当前生命值 100%（``wf_gerald_percent_skill``\n   09-25 写入）。本模块逐节点核对（fail closed）。\nD. 文案「固定伤害」：它是 ``CreateRatioAttack``（不吃攻击力/增伤、绕过抗性）⇒ 统一称固定伤害。\n   - 队长 536 行 c68 指向 ``change_skill_white_wolf_gerald``（已在本角色命名空间，候选已认领）⇒ 原键改写为\n     无数字版（裁决「技能强化条目不写数字与秒数」，``panel_problems(skill_flag=True)``）。**不写**\n     「光属性共鸣时，」前缀：队长面板按行自动生成，客户端已按前置 kind 2 拼出「光属性共鸣」\n     （ui_string ``ability_description_instant_trigger_kind_member_element_unified`` = ``::element_full::共鸣``；\n     官方同形队长 536 行 dryad_hw23 121189#2 前置 2 Blue≥6，其文案也不带条件），写了会重复。\n   - 数字写进技能描述 5 处（action_skill 两档 c1、character_text c5/c7、服务端 cdndata/character_text.json\n     [5]/[7]，参照 ``wf_balance_20260927_rolfwt26``）：在原描述末尾追加「／强化后：…」一段，沿用本角色描述的\n     「／」分段风格；数字从技能树读出并核对（5% 起、每次 +1%、低于最大生命值 5% 斩杀）。\n   - 队长面板 ``desc_override_black_wolf_knight`` 在 live 不存在（自动生成）⇒ 保持自动生成；存在即拒绝。\n     原描述/文案里没有「当前生命值百分比伤害」之类说法需要替换（本模块核对）。\n\n基诺维：作者「不要影响他当前能力的效果」⇒ 不重跑 ``build_workspace.py kit-v3``（不属本单元，本模块不读不写）。\n\n生成器：``wf_gerald_cast_growth.py`` 同步——``COUNTER_CAP = 2147483647.0``（恢复不封顶）、``ENHANCEMENT_TEXT``\n改为本模块 :data:`NEW_CAS_TEXT`；对施技成长前的技能树重跑 ``rewrite()`` == 本模块输出（测试断言，连类型）。\n``wf_gerald_percent_skill`` / ``wf_gerald_percent_revision`` 按旧源 sha256 fail closed，不写这些格子；\n技能描述/character_text 没有现行生成器（09-03 v3 一次性装配），本模块是现行唯一写入源。\n\n候选（work/character_packs/white_wolf_gerald，manifest 0.20260927）：本模块读取的键与 live 逐字相同、零哈希漂移；\n只有服务端镜像 character_text 149999 行是旧文（见 :data:`CANDIDATE_STALE_SERVER_MIRROR`），暂存整行替换后一致。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写 live store / assets / .cdn / 候选包；接口见\n``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``（第二批 b 后缀）。\n"
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable

import wf_balance_20260927b_gerald_wolf as B2
import wf_client_legality as L
import wf_midautumn_kitlib as KL

CID = "149999"
CODE = "white_wolf_gerald"
PACKAGES = ["white_wolf_gerald"]
#: 候选 manifest 现值 0.20260927（第二批 wf_balance_20260927b_gerald_wolf 回写）→ 递增。
PACKAGE_VERSION = {"white_wolf_gerald": "0.20260927.1"}
#: 本次只改文案与一格 DSL 常量，不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 manifest 自身零哈希漂移（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}
ELEMENT = B2.ELEMENT               # 4 = 光（0 基内部元素）

SKILLS = B2.SKILLS
ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
COUNTER_TABLE = ("master/character/unique_condition.orderedmap", str(B2.COUNTER_UID))
CAS_KEY = "change_skill_" + CODE
#: 客户端按「desc_override_ + 首行 c0」取队长面板覆盖；live 不存在 ⇒ 自动生成（存在即拒绝）。
LEADER_PANEL_KEY = "desc_override_black_wolf_knight"

# ---------------------------------------------------------------- A：队长 536 行（核对，不改）

LEADER_NCOLS = 124
FLAG_ROW = 11
#: 队长 #11 的完整非空格（其余列必须为空）：c0 母本名、光·编成≥6、无触发、536 → change_skill_white_wolf_gerald。
FLAG_CELLS: dict[int, str] = {
    0: B2.LEADER_NAME, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: B2.ELEMENT_TOKEN,
    11: "0", 18: "0", 25: "0", 37: "(None)", 44: "0", 45: "536", 68: CAS_KEY,
}
ABILITY_CONTENT, ABILITY_STRING = 47, 70     # 能力表 instant_content / 文案键列（= 队长列 + 2）
SKILL_FLAG_KINDS = ("536", "704")            # ChangeSkillFlag / ChangeSkillFlag2（旗号 1 / 2）

# ---------------------------------------------------------------- B：技能两档 Bind 上限

BIND_PATH = (11, 1, 0, 1, 2, 1, 0, 1)
CAP_BATCH2 = B2.SKILL_CAP_NEW                # 10（第二批，int）
CAP_RESTORED = float(B2.SKILL_CAP_OLD)       # 2147483647.0（第二批改前，AMF3 double）
CAP_ARG = B2.SKILL_CAP_ARG                   # 5

# ---------------------------------------------------------------- C：斩杀分支（核对，不改）

TARGET = 301                                 # 私有绑定：FindNearSubjects 选出的最近敌人
EXECUTE_BELOW_PERCENT = 5                    # ConditionalsHealthPointRatioOf 第 2 参：最大生命值 %
EXECUTE_STRIKE = ["CreateRatioAttack", TARGET, 1, [{"min": 1.0, "max": 1.0}]]
NEAREST = ["FindNearSubjects", -18, 1, 49, ["DoNothing"], TARGET]
RATIO_KIND_CURRENT_HP = 1                    # CreateRatioAttack 第 2 参 1 = 当前生命值（2 = 最大生命值）

# ---------------------------------------------------------------- D：文案

OLD_CAS_TEXT = "强化自身技能效果，额外造成一定固定伤害。"
#: 技能强化条目：不写数字与秒数，不写共鸣前缀（客户端按前置拼「光属性共鸣」）。
NEW_CAS_TEXT = "强化自身技能：追加按敌人当前生命值计算的固定伤害（随技能发动次数提高），并斩杀低生命值的敌人"

OLD_ACTION_DESC = (
    "时空为之凝滞的一闪。向最近的敌人突进，对接触到的敌人造成光属性伤害／以全屏月牙交叉斩对全体敌人造成光属性伤害"
    " ＋ 消除敌人的2个强化效果 ＋ 赋予敌人累积全属性抗性降低效果（无视弱体抵抗、不可驱散）"
    "／赋予队伍最大速度固定＋贯穿＋浮游效果（技能伤害以直接攻击伤害计算）")
OLD_TEXT_DESC = (
    "时空为之凝滞的一闪。展开时之魔法阵，向最近的敌人突进并对接触到的敌人造成光属性伤害／以全屏月牙交叉斩对领域内"
    "全体敌人造成光属性伤害 ＋ 强制消除1个强化效果 ＋ 赋予累积光属性抗性降低效果／赋予队伍最大速度固定＋贯穿＋浮游效果")


def _pct(value: float) -> str:
    return f"{round(value * 100, 6):g}%"


#: 追加到技能描述末尾的一段（数字与技能树一致，见 :func:`skill_numbers`）。
DESC_SEGMENT = (f"／强化后：对最近的敌人追加造成其当前生命值{_pct(B2.RATIO_BASE)}的固定伤害"
                f"（每次发动技能提高{_pct(B2.RATIO_PER_STACK)}），"
                f"敌人生命值低于最大生命值{EXECUTE_BELOW_PERCENT}%时直接斩杀")
NEW_ACTION_DESC = OLD_ACTION_DESC + DESC_SEGMENT
NEW_TEXT_DESC = OLD_TEXT_DESC + DESC_SEGMENT
TEXT_DESC_COLUMNS = (5, 7)                   # character_text 技能说明（技能 / 技能＋）
ACTION_DESC_COLUMN = 1
#: 旧说法（按比例/百分比伤害）不得残留在本角色任何技能文案里。
PERCENT_DAMAGE_WORDS = ("百分比伤害", "比例伤害", "生命值百分比")

#: 候选服务端镜像 ``roots/server/cdndata/character_text.json`` 的 149999 行仍是 09-03 前旧文
#: （[5]/[6]/[7] 为「以震耳的咆哮破坏领主的全部弱点…」「剑柄锤击＋」），与 live 其余 9 列相同。暂存
#: ``Plan.server_text`` → ``RevisionCandidate.server_character_row`` 整行替换 ⇒ [6] 技能＋名顺带刷成 live 值
#: 「月耀一闪＋」——终态（候选 = live + 本修订）正确，只是候选 diff 多这一列。客户端侧各键候选与 live 逐字相同。
CANDIDATE_STALE_SERVER_MIRROR = {
    "file": "cdndata/character_text.json", "key": CID,
    "differing_columns": (5, 6, 7), "overwritten_beyond_revision": (6,),
    "cells": {"6": ["剑柄锤击＋", "月耀一闪＋"]},
}

# ---------------------------------------------------------------- 输入基线

#: live 1.4.1051 只读取数（stage_batch.make_read(live_only=True)，2026-09-27）；值 = digest(read(kind, key))。
#: 队长/能力/固有只读不改（核对 A 与计数固有未封顶）。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", CID): "86c7076a2c0aac0ee174ea9bb90f1ec19111357da44600d09f843dd2c2c0bd2f",
    ("ability", CID + "1"): "53c72fb83b0e53752874ee55e18b7478ebb60744bff285b4fa148855c0213f08",
    ("ability", CID + "2"): "b030988a31cf0fb15a52aa638df23a57f8031a5ac9138571c87eee58b7a79315",
    ("ability", CID + "3"): "89a2da79be44d43011410b42cc125506d26f0e8a596f454a91fcdd461d02f5ff",
    ("ability", CID + "4"): "5ce581e2bb72fc8893304231f33f6aa965b53b327bd676b226ce40bc79c8d904",
    ("ability", CID + "5"): "58174262c8d72a42061b8f1b01a3ae320c049a730de12f2cd99b04f3f8d1eac3",
    ("ability", CID + "6"): "67afd91a963948494f54fb41ca0d43485da135279b5503877cf3f52bbe5a6b33",
    ("table", COUNTER_TABLE): "7b2c9251f13b3815159adc44d790733644aec9f92eb2cf886aad0d9289cb0744",
    ("dsl", SKILLS[0]): "918b03c70908fa8c6f592239cbf35b89d0e132d4a9a9b9cc90a0c139f01b60de",
    ("dsl", SKILLS[1]): "f0ce6885dcdbfcb4e8cf47ef105234140cd991028cc4c25f9d8032bf44a3dfda",
    ("cas", CAS_KEY): "6864d19ec8dc4a03c3660f41ba231b6ca6a74404bfa2a1a78590f9b7aed98f52",
    ("action", CODE): "98b7ca2fad54f8717704a1943b68907992be83908ccc7bff2caaa7376c634fc5",
    ("text", CID): "5d085c292cff402bf9ff58cb7a65dacabd38b0c3dabdee76331a4c99a13477b0",
    ("server_text", CID): "5d085c292cff402bf9ff58cb7a65dacabd38b0c3dabdee76331a4c99a13477b0",
}

#: 固有「时空侵蚀」live 行（与 wf_gerald_cast_growth.counter_row() 相同）；本模块只核对，不改。
COUNTER_ROW = [[B2.COUNTER_KEY, "时空侵蚀", "battle/common/unique_condition/unique_gerald_time_seal",
                "99999999", "2147483647", "(None)", "(None)", "(None)", "(None)",
                "false", "true", "0", "0", "false", "(None)"]]


class GeraldAppendError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


digest = B2.digest


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GeraldAppendError(f"{CID} balance 20260927b-2: {message}")


def _baseline(read: Callable[[str, Any], Any]) -> dict:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        got = digest(value) if value is not None else None
        if got != want:
            raise GeraldAppendError(f"unreviewed live baseline for {kind}:{key} ({got} != {want})")
        inputs[kind, key] = deepcopy(value)
    try:
        present = read("cas", LEADER_PANEL_KEY) is not None
    except KeyError:
        present = False
    _require(not present, f"{LEADER_PANEL_KEY} exists: leader panel is no longer auto-generated")
    return inputs


# ---------------------------------------------------------------- A

def skill_flag_rows(leader: list[list[str]], abilities: dict[str, list[list[str]]]) -> list[tuple[str, int]]:
    """[(表:键, 行号)]：本角色所有技能强化（536/704）行。"""
    found = [(f"leader:{CID}", i) for i, row in enumerate(leader) if row[45] in SKILL_FLAG_KINDS]
    found += [(f"ability:{key}", i) for key, rows in abilities.items()
              for i, row in enumerate(rows) if row[ABILITY_CONTENT] in SKILL_FLAG_KINDS]
    return found


def check_flag_in_leader(leader: list[list[str]], abilities: dict[str, list[list[str]]]) -> None:
    """A：536 只在队长 #11（逐格核对），能力里一条都没有。"""
    _require(len(leader) == 12 and all(len(row) == LEADER_NCOLS for row in leader),
             f"leader_ability:{CID} must stay 12 rows of {LEADER_NCOLS} columns")
    _require(skill_flag_rows(leader, abilities) == [(f"leader:{CID}", FLAG_ROW)],
             f"skill flag rows moved: {skill_flag_rows(leader, abilities)}")
    row = leader[FLAG_ROW]
    _require(all(row[c] == v for c, v in FLAG_CELLS.items())
             and all(v == "" for c, v in enumerate(row) if c not in FLAG_CELLS),
             f"leader #{FLAG_ROW} is not the reviewed light-resonance 536 row")
    _require(sorted(abilities) == sorted(ABILITY_KEYS), "ability keys changed")


# ---------------------------------------------------------------- B / C

def _nodes(tree, name):
    return [(p, n) for p, n in B2._walk(tree) if n and n[0] == name]


def enhanced_branches(tree) -> tuple[tuple, list, list]:
    """(旗号节点路径, 强化分支 Block, 普通分支 Block)。"""
    flags = _nodes(tree, "ConditionalsChangeSkillFlag")
    _require(len(flags) == 1 and flags[0][1][1] == 1, "expected one ConditionalsChangeSkillFlag(1)")
    path, flag = flags[0]
    _require(path == BIND_PATH[:-4], f"skill flag node moved: {path}")
    return path, flag[2], flag[3]


def execute_branch(tree) -> tuple[tuple, list]:
    """C：(路径, ConditionalsHealthPointRatioOf 节点)；逐节点核对最近敌人 → ≥5% 成长比例 / <5% 当前生命值 100%。"""
    flag_path, enhanced, plain = enhanced_branches(tree)
    for name in ("ConditionalsHealthPointRatioOf", "CreateRatioAttack", "BindConditionAccumulationVariable"):
        _require(not _nodes(plain, name), f"{name} leaked into the non-enhanced branch")
    checks = _nodes(tree, "ConditionalsHealthPointRatioOf")
    _require(len(checks) == 1, f"expected one HP-ratio branch, got {len(checks)}")
    path, check = checks[0]
    _require(path[:len(flag_path) + 1] == flag_path + (2,), "HP-ratio branch is outside the enhanced branch")
    parent = B2._at(tree, path[:-4])
    _require(parent[:6] == NEAREST and parent[6] == ["Block", [["Command", check]]],
             "execute must be the only command under FindNearSubjects(-18, 1, 49, DoNothing, 301)")
    _require(check[1:3] == [TARGET, EXECUTE_BELOW_PERCENT], f"HP-ratio gate drifted: {check[1:3]}")
    _require(check[3] == ["Block", [["Command", B2.RATIO_STRIKE]]], "growing ratio strike drifted")
    _require(check[4] == ["Block", [["Command", EXECUTE_STRIKE]]], "execute strike drifted")
    _require([n for _p, n in _nodes(tree, "CreateRatioAttack")] == [B2.RATIO_STRIKE, EXECUTE_STRIKE],
             "unexpected extra ratio attacks")
    return path, check


def skill_numbers(tree) -> dict[str, float]:
    """技能树里的文案数字：起始比例、每次增量（都按当前生命值）、斩杀阈值（最大生命值 %）。"""
    _path, check = execute_branch(tree)
    strike = check[3][1][0][1]
    base, per = strike[3]
    _require(strike[2] == RATIO_KIND_CURRENT_HP and "mul" not in base and per.get("mul") == B2.COUNTER_VARIABLE,
             "ratio strike is not current-HP base + per-stack")
    _require(base["min"] == base["max"] and per["min"] == per["max"], "ratio strike is level-scaled")
    return {"base": base["min"], "per_cast": per["min"], "execute_below": check[2]}


def skill_tree(tree) -> list:
    """B：技能树 → 新树（深拷贝）：只把时空侵蚀 Bind 上限 10 → 2147483647.0，其余节点逐字保留。"""
    result = deepcopy(tree)
    _require(result[:11] == B2.SKILL_ROOT_HEADER, "skill root header drift")
    path, bind = B2.skill_counter_bind(result)
    _require(path == BIND_PATH, f"Bind moved: {path}")
    cap = bind[CAP_ARG]
    _require(bind[:CAP_ARG] == B2.BIND_PREFIX and len(bind) == CAP_ARG + 1
             and type(cap) is int and cap == CAP_BATCH2,
             f"time-erosion Bind is not the batch-2 capped preimage: {bind!r:.160}")
    execute_branch(result)
    B2._at(result, path)[CAP_ARG] = CAP_RESTORED
    restored = deepcopy(result)
    B2._at(restored, path)[CAP_ARG] = cap
    if json.dumps(restored) != json.dumps(tree):
        raise AssertionError("skill_tree touched more than the Bind cap")
    return result


# ---------------------------------------------------------------- D

def _texts_problem(text: str, label: str) -> list[str]:
    return [f"{label}: {p}" for p in KL.panel_problems(text)] + \
           [f"{label}: stale wording {w!r}" for w in PERCENT_DAMAGE_WORDS if w in text]


def revise_action(action: list) -> list:
    _require([inner for inner, _fields in action] == ["1", "2"], "action_skill inner keys changed")
    out = []
    for (inner, fields), program in zip(action, SKILLS):
        fields = list(fields)
        _require(fields[7] == program, f"action_skill {CODE}/{inner} program {fields[7]!r}")
        _require(fields[ACTION_DESC_COLUMN] == OLD_ACTION_DESC,
                 f"action_skill {CODE}/{inner} c1 is not the reviewed text")
        fields[ACTION_DESC_COLUMN] = NEW_ACTION_DESC
        out.append((inner, fields))
    return out


def revise_text_row(rows: list[list[str]], label: str) -> list[list[str]]:
    _require(len(rows) == 1 and len(rows[0]) == 12, f"{label}: expected one 12-column row")
    out = deepcopy(rows)
    for col in TEXT_DESC_COLUMNS:
        _require(out[0][col] == OLD_TEXT_DESC, f"{label} [{col}] is not the reviewed text")
        out[0][col] = NEW_TEXT_DESC
    return out


def text_gate_problems() -> list[str]:
    problems = [f"cas: {p}" for p in KL.panel_problems(NEW_CAS_TEXT, skill_flag=True)]
    problems += [f"cas: stale wording {w!r}" for w in PERCENT_DAMAGE_WORDS if w in NEW_CAS_TEXT]
    problems += _texts_problem(NEW_ACTION_DESC, "action desc") + _texts_problem(NEW_TEXT_DESC, "text desc")
    for text in (NEW_CAS_TEXT, NEW_ACTION_DESC, NEW_TEXT_DESC):
        if "固定伤害" not in text:
            problems.append(f"missing 固定伤害: {text[:24]}…")
    if OLD_ACTION_DESC.count("／强化后") or OLD_TEXT_DESC.count("／强化后"):
        problems.append("description already carries the enhanced segment")
    return problems


# ---------------------------------------------------------------- revise

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    leader = inputs["leader", CID]
    abilities = {key: inputs["ability", key] for key in ABILITY_KEYS}
    check_flag_in_leader(leader, abilities)
    counter = inputs["table", COUNTER_TABLE]
    _require(counter == COUNTER_ROW, "unique_condition 14999903 (时空侵蚀) drifted")

    skills = {program: inputs["dsl", program] for program in SKILLS}
    numbers = {program: skill_numbers(tree) for program, tree in skills.items()}
    want = {"base": B2.RATIO_BASE, "per_cast": B2.RATIO_PER_STACK, "execute_below": EXECUTE_BELOW_PERCENT}
    _require(all(n == want for n in numbers.values()), f"skill numbers differ from the text: {numbers}")
    new_skills = {program: skill_tree(tree) for program, tree in skills.items()}

    _require(inputs["cas", CAS_KEY] == [[OLD_CAS_TEXT]], f"{CAS_KEY} is not the reviewed text")
    new_action = revise_action(inputs["action", CODE])
    new_text = revise_text_row(inputs["text", CID], f"character_text {CID}")
    new_server = revise_text_row(inputs["server_text", CID], f"server character_text {CID}")

    problems = text_gate_problems()
    problems += [f"dsl {program}: {p}" for program, tree in new_skills.items() for p in B2.dsl_problems(tree)]
    problems += [f"leader #{FLAG_ROW}: {p}" for p in B2.row_problems(leader[FLAG_ROW], frozenset({CAS_KEY}))]
    problems += [f"leader #{FLAG_ROW}: {p}" for p in L.required_client_capabilities("leader_ability", leader[FLAG_ROW])]
    if problems:
        raise GeraldAppendError("; ".join(problems))

    ratio = lambda casts: round(B2.RATIO_BASE + B2.RATIO_PER_STACK * casts, 6)
    return {
        "ability": {}, "leader": {}, "cas": {CAS_KEY: [[NEW_CAS_TEXT]]}, "text": {CID: new_text}, "table": {},
        "action": {CODE: new_action}, "dsl": new_skills, "server_text": {CID: new_server}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_gerald2.py",
            "spec": "作者 2026-09-27 追加（回答第二批两问：①施技成长封顶 ②基诺维重建）：强化效果放在队长技（只在当队长时生效）"
                    "⇒ 不封顶；文案称固定伤害；基诺维不要影响当前能力",
            "live_tail": "1.4.1051（第二批已发布）",
            "changes": {
                f"{B2.SKILL_BASE}{{1,2}} 强化分支 BindConditionAccumulationVariable 第 5 参":
                    f"{CAP_BATCH2}→{CAP_RESTORED!r}（撤回第二批封顶；与第二批改前逐字同、重编码同哈希）",
                f"custom_ability_string:{CAS_KEY}": [OLD_CAS_TEXT, NEW_CAS_TEXT],
                "技能描述（action_skill 1/2 c1、character_text c5/c7、服务端 [5]/[7]）": f"末尾追加「{DESC_SEGMENT}」",
            },
            "a_skill_flag_in_leader": {
                "status": "live 已在队长（09-25 wf_gerald_cast_growth.relocate 能力3 → 队长末行），本次不搬行",
                "row": f"leader_ability:{CID}#{FLAG_ROW}：[black_wolf_knight, 0, ''] + 536，前置 2 光·编成≥6，c68 {CAS_KEY}",
                "abilities_with_536": 0,
                "leader_rows": 12,
                "effect": "强化分支只在队长 + 光属性共鸣时打开；比例伤害/逐次成长/斩杀都只在强化分支 ⇒ 无上限只留在队长技",
            },
            "b_growth_uncapped": {
                "before_after": f"第 n 次强化施技：5%+1%×min(n−1, {CAP_BATCH2})（最多 15%）→ 5%+1%×(n−1)（不封顶）",
                "examples": {"1": ratio(0), "2": ratio(1), "3": ratio(2), "11": ratio(10), "21": ratio(20)},
                "counter": "固有 14999903「时空侵蚀」c3 99999999 帧、c4 2147483647（未封，不动）；先快照后 +1",
                "extreme": "第 96 次起比例 ≥100% 当前生命值（每次都是斩杀量级）；设计稿估 3 分钟施技 5–7 次，实际到不了",
                "batch2_blocked_resolved": "第二批 notes.blocked.a5_skill_growth_remainder_to_leader 由作者裁决：成长本就只在队长技"
                                           "（536 在队长）⇒ 取消封顶，不另起队长行",
            },
            "c_execute": {
                "status": "已存在（09-25 wf_gerald_percent_skill），不动",
                "shape": "FindNearSubjects(-18,1,49,DoNothing,301) → ConditionalsHealthPointRatioOf(301, 5, "
                         "[CreateRatioAttack(301,1,[5%, 1%×v360])], [CreateRatioAttack(301,1,[100%])])",
                "semantics": "第一分支 ≥ 最大生命值 5%，第二分支严格 <5% ⇒ 打当前生命值 100%",
                "caveat": "RatioAttack 仍受原生伤害上限、无敌、金属、转阶段保护（percent_skill metadata "
                          "unconditional_execute_guaranteed=False）；文案写「直接斩杀」按作者口径",
            },
            "d_text": {
                "cas": {"key": CAS_KEY, "before": OLD_CAS_TEXT, "after": NEW_CAS_TEXT,
                        "rule": "技能强化条目不写数字与秒数（panel_problems skill_flag=True 为空）",
                        "no_resonance_prefix": "队长面板自动生成，客户端按前置 kind 2 拼「光属性共鸣」"
                                               "（ui_string ability_description_instant_trigger_kind_member_element_unified"
                                               " = ::element_full::共鸣；官方 dryad_hw23 121189#2 同形不带条件）⇒ 不重复写"},
                "skill_description": {"appended": DESC_SEGMENT,
                                      "places": ["action_skill 1/2 c1", "character_text c5/c7",
                                                 "server cdndata/character_text.json [5]/[7]"],
                                      "numbers_from_tree": numbers[SKILLS[0]]},
                "leader_panel": f"{LEADER_PANEL_KEY} 在 live 不存在 ⇒ 保持自动生成（536 行 = 前置前缀 + {CAS_KEY}）",
                "fixed_damage": "CreateRatioAttack 不吃攻击力/增伤、绕过抗性 ⇒ 称固定伤害",
            },
            "kept": {
                "leader_ability:149999": "12 行逐字不动（第二批放缓/眩晕蓄积保留）",
                "PF Lv3": "第二批削韧 25 保留，本模块不读不写",
                "unique_condition:14999903": "不动",
            },
            "ginovi": "作者：基诺维不要影响他当前能力的效果 ⇒ 不重跑 build_workspace.py kit-v3（不在本单元，未读未写）",
            "generators": "wf_gerald_cast_growth：COUNTER_CAP=2147483647.0、ENHANCEMENT_TEXT=新文案；对施技成长前技能树重跑 "
                          "rewrite() == 本模块输出（测试断言）；percent_skill/percent_revision 按旧源 sha256 fail closed",
            "open_points": {
                "candidate_stale_server_mirror": "候选服务端镜像 character_text 149999 [5]/[6]/[7] 是 09-03 前旧文；暂存整行替换"
                                                 "会顺带把 [6]「剑柄锤击＋」刷成 live「月耀一闪＋」（终态正确）",
                "existing_text_mismatch": "action_skill 描述写「消除敌人的2个强化效果/全属性抗性降低」，character_text 写"
                                          "「强制消除1个强化效果/光属性抗性降低」；树里是 DCAll 2 删 2 个 + 元素 254 全属性。"
                                          "既有不一致，本次只追加强化段、不改",
            },
            "reviewed_input_drift": [],
            "capabilities": [],
            "runtime_verified": False,
        },
    }

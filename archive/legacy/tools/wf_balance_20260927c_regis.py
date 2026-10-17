# -*- coding: utf-8 -*-
"""雷吉斯·海滨 139994 ``rec_android_seaside``：2026-09-27 平衡第三轮（c）——成长复核 + 技能倍率撤封顶（纯函数）。

作者原话（2026-09-27，主会话逐字转述，节选与本角色相关的）：

- 「部分角色技能都倍率成长也要无限成长,成长条件放到队长技里面带上对应共鸣条件,……很多角色成长过于缓慢」
- 「雷吉斯队长技的成长太慢了,fever对雷吉斯来说很难快速进出,这个成长可以高一点,降低成长也要看触发难度」
- 「砍到4/5,或者7/10这样吧,很多角色没有成长完全没用了」「可以砍到2/3」
- 「数值尽量取5的倍数比如36就变成35,39就变成40」

此前的 1/2 版（``wf_balance_20260927b_regis2``，未提交、未发布）已被上面第 4–5 条口径取代并作废，由本模块取代。

输入 = live 1.4.1053（链尾；本模块读取的各键 = 第二批 ``wf_balance_20260927b_regis`` 输出 = 候选 s7-regis 1.0.8，
逐字相同、零漂移，2026-09-27 只读核对）。行号 = 0 起下标。

A. 队长「每层浪涌充能」四条逐层成长（持续 134，固有 13999401）c111/c112 = 第二批改前原值 × 4/5（就近取 5% 的倍数）：

   ====  ==========================  ==========  ========  ============
   行    效果                        原值        第二批    本次（4/5）
   ====  ==========================  ==========  ========  ============
   #0    雷队技能伤害（雷共鸣）      150000      30000     120000
   #1    雷队攻击力（雷共鸣）        100000      20000     80000
   #7    自身攻击力                  150000      30000     120000
   #8    自身技能伤害                150000      30000     120000
   ====  ==========================  ==========  ========  ============

   档位：浪涌只由进 Fever（能力 1#2，主位）与 Fever 结束（队长 #6）各 +1；每进一次 Fever 槽上限 ×1.25、Fever 中
   全队不攒槽 ⇒ 3 分钟约 5–8 次 Fever、约 10–16 层（推断，按 12 层估）⇒ 难；作者点名「Fever 难进出」且队长技没有
   别的固定技能伤害 ⇒ 取最轻的 4/5。c100 仍 ``(None)``（队长侧不设上限），#2–#6 逐字保留；能力 3#3/#4 的封顶版
   （每层 30%、最多 5 层）按口径 D4 保持第二批的值不动（不读不写）。
B. 技能倍率撤封顶（口径 U3：当队长且雷共鸣时不封顶，其他情况保留第二批 5 层）：
   1. 队长表追加 #9 = kind 536 ChangeSkillFlag（旗号 1，瞬发、无触发），前置 1 = kind 2 雷·编成≥6（共鸣），
      c68 文案键 :data:`FLAG_KEY`。与 live 杰拉德 ``149999#11``、官方 ``dryad_hw23 121189#2`` 逐格同形
      （只换 c0 / 颜色 / 文案键）。旗号 1 在本角色空闲：六个能力键与队长现有 9 行里都没有 536/704–708（本模块核对，
      fail closed）；character c9=1 与 action_skill c16=(None) 都不读旗号。
   2. 两档技能 DSL 只改 ≥5 层档（``tree[11]`` 第 2 条 ``ConditionalsConditionAccumulationNumber(≥5)`` 的 then 块）：
      ``[Bind(vid1, 5.0), FindNearSubjects(光束)]`` → ``[ConditionalsChangeSkillFlag(1, 开支, 关支)]``；
      关支 = live 原两节点逐字，开支 = 同两节点、只把 Bind 上限改回第二批前的 ``99.0``（double）。
      Bind 挪进分支后分支外看不到变量 1，而它唯一的消费者（该档光束 CreateNormalAttack 的 vlv）就在同一分支内
      （:func:`vlv_scope_problems` 核对）。3–4 层 / 0–2 层两档的 Bind（上限 5.0）不改：层数到不了 5，改不改结果一样。
   3. 文案：新 CAS :data:`FLAG_KEY` = 「强化『浪花爆破』：光束威力随「浪涌充能」层数持续提升」（技能强化条目按官方格式点名
      技能、定性不写数字，``panel_problems(skill_flag=True)``；技能名由 revise() 对 action_skill 第 1 档 c0 核对）；队长覆盖
      文案在第 2 行后插入「雷属性共鸣时，」+ 同句（536 行前置 1 = 雷≥6 共鸣）。
      技能描述 5 处（action_skill 两档 c1、character_text c5/c7、服务端镜像 [5]/[7]）**不改**，保持第二批
      「（最多5层）」：主会话 2026-09-27 技能强化文案口径（作者「技能都强化效果只在队长技或者能力里面按照格式写就行,
      技能里面不要重复描述强化后的效果」）——技能描述只写技能本体（关支上限 5 层照写），强化后的不封顶只由队长面板的
      强化条目与 :data:`FLAG_KEY` 描述。:func:`description` / :func:`text_rows` / :func:`action_rows` 仍逐处核对
      第二批原文与 action_skill c16，但结果与 live 相同 ⇒ revise() 不返回这三类键（接口「只返回有变化的键」）。
C. 面板按数据条件拆行（主会话口径 5 扩展 B，2026-09-27 暂存前最后一轮）：队长覆盖文案第 7 行（插入旗号行后；第二批原
   第 6 行）「雷属性共鸣时，非FEVER模式中冲刺时FEVER槽＋10%；FEVER模式中冲刺时FEVER槽－10%」用「；」挤了两种数据条件——
   能力 6 ``1399946#1``（前置 2 = 186 非 Fever）与 ``#2``（前置 2 = 12 Fever），两行都挂前置 1 雷≥6 共鸣、前置 3 = 42
   仅队长、触发 4 冲刺、内容 724 Fever 槽 ±10% ⇒ 拆成两行，各自照写「雷属性共鸣时，」（:data:`SPLIT_LINES_AFTER`，
   依据 :func:`split_basis_problems` 在 revise() 里核对，fail closed）。数据不动。返回面板的规则扫描
   （:func:`panel_problems`）另拦「X属性共鸣时：」、全角「／」与半角「/」。

生成器 ``wf_seasonal7_kit_regis.build``：第二批层之后再调用本模块（:func:`leader_rows` / :func:`skill_tree` /
:func:`panel_text` / :func:`description`，kit 侧 ``balance_c_rows`` / ``balance_c_panel``），kit 重跑产物 == :func:`revise`。
纯函数：只转换 ``read()`` 给出的 live 输入，不写 live store / assets / .cdn / 候选包；接口见
``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_balance_20260927_regis as B1
import wf_balance_20260927b_regis as B2

CID = B2.CID                                  # "139994"
CODE = B2.CODE                                # "rec_android_seaside"
PACKAGES = ["s7-regis"]
#: 候选 manifest 现值 1.0.8（第二批 wf_balance_20260927b_regis 回写；作废的 regis2 未回写）→ 下一号。
PACKAGE_VERSION = {"s7-regis": "1.0.9"}
#: 536 队长行 / change_skill 文案键都不需要新 capability（``required_client_capabilities`` 为空）。
CAPABILITIES: list[str] = []
#: 本模块读取的各键与候选 s7-regis 1.0.8 逐字相同（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ELEMENT = B2.ELEMENT                          # 2 = 雷（内部 ElementKind）
UID = B2.UID                                  # "13999401" 浪涌充能
LEADER_NCOLS = B2.LEADER_NCOLS                # 124
LEADER_ROWS_BEFORE = B2.LEADER_ROWS_AFTER     # 9（第二批后）
LEADER_ROWS_AFTER = LEADER_ROWS_BEFORE + 1    # 10：追加 536 行
FLAG_ROW = LEADER_ROWS_BEFORE                 # 新行下标 9
ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
SKILL_PROGRAMS = B2.SKILL_PROGRAMS
PANEL_LEADER = B2.PANEL_LEADER                # desc_override_rec_android_seaside
FLAG_KEY = f"change_skill_{CODE}_leader"      # 536 行 c68 文案键（change_skill_<code> 命名空间）

# ---------------------------------------------------------------- A. 成长复核（4/5，取 5% 的倍数）

RATIO = (4, 5)
ROUND_STEP = 5000                             # 5%（强度单位 1000 = 1%）
VALUE_COLS = (111, 112)                       # 队长持续块强度（低 / 满）

#: 行号 → (第二批输出指纹 = 本次输入, 第二批改前原值)。
_SOURCES = {
    B2.TEAM_SKILL_ROW: (B2.LEADER_TEAM_SKILL_AFTER, B2.LEADER_TEAM_SKILL[111]),       # #0 雷队技能伤害
    B2.TEAM_ATTACK_ROW: (B2.LEADER_TEAM_ATTACK_AFTER, B2.LEADER_TEAM_ATTACK[111]),    # #1 雷队攻击力
    7: (B2.MOVED_SELF_ATTACK, B2.THIRD_SELF_ATTACK[113]),                           # #7 自身攻击力
    8: (B2.MOVED_SELF_SKILL, B2.THIRD_SELF_SKILL[113]),                             # #8 自身技能伤害
}


def scaled(original: str) -> str:
    """原值 × 4/5，就近取 5% 的倍数（四舍五入，整数运算）。"""
    num, den = RATIO
    q, r = divmod(int(original) * num, den * ROUND_STEP)
    if 2 * r >= den * ROUND_STEP:
        q += 1
    return str(q * ROUND_STEP)


GROWTH_ROWS = tuple(sorted(_SOURCES))                                       # (0, 1, 7, 8)
ORIGINAL_VALUES = {row: original for row, (_cells, original) in _SOURCES.items()}
BATCH2_VALUES = {row: cells[111] for row, (cells, _original) in _SOURCES.items()}
NEW_VALUES = {row: scaled(original) for row, original in ORIGINAL_VALUES.items()}
#: 主会话数值表（reeval_full.json table.rows，雷吉斯 L#0 / L#1 / L#7–L#8「建议」）。
TABLE_VALUES = {0: "120000", 1: "80000", 7: "120000", 8: "120000"}
if NEW_VALUES != TABLE_VALUES:
    raise ImportError(f"regis c growth table drifted: {NEW_VALUES} != {TABLE_VALUES}")
ROWS_BEFORE = {row: cells for row, (cells, _original) in _SOURCES.items()}
ROWS_AFTER = {row: {**cells, **{c: NEW_VALUES[row] for c in VALUE_COLS}} for row, cells in ROWS_BEFORE.items()}

# ---------------------------------------------------------------- B1. 旗号 1 开关行（队长 536）

SKILL_FLAG = 1                                # 536 ⇒ 旗号 1（InstantAbilitySource.as:5018）
SKILL_FLAG_KIND = "536"
#: 能切技能旗号的全部 kind（536 = 旗号 1，704–708 = 旗号 2–6）。
FLAG_KINDS = ("536", "704", "705", "706", "707", "708")
#: 队长 536 行全部非空列（其余列必须为空）：瞬发（c3=0）、无触发（c25=0）、前置 1 = kind 2 雷·编成≥6。
FLAG_ROW_CELLS = {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: "Yellow", 11: "0", 18: "0",
                  25: "0", 37: "(None)", 44: "0", 45: SKILL_FLAG_KIND, 68: FLAG_KEY}
#: 与 live 杰拉德 149999#11 / 官方 dryad_hw23 121189#2 同形时，只允许这三格不同（c0 / 共鸣颜色 / 文案键）。
FLAG_ROW_PRECEDENT_DIFF = (0, 9, 68)

# ---------------------------------------------------------------- B2. DSL（≥5 层档按旗号 1 分两支）

CAP_CAPPED = B2.DSL_CAP_AFTER                 # 5.0：第二批封顶（关支，逐字保留）
CAP_UNCAPPED = B2.DSL_CAP_BEFORE              # 99.0：第二批改前（开支，double，逐字恢复）
TOP_VID = B2.BIND_VIDS[0]                     # 1：≥5 层档光束的层数变量
TOP_THRESHOLD = 5

# ---------------------------------------------------------------- B3. 文案

#: 技能强化条目（主会话 2026-09-27 口径 R2）：官方格式「强化『<技能名>』：<定性说明>」，点明技能名、不写数字。
SKILL_NAME = "浪花爆破"                        # action_skill rec_android_seaside 第 1 档 c0（revise() 核对）
FLAG_TEXT = f"强化『{SKILL_NAME}』：光束威力随「浪涌充能」层数持续提升"
FLAG_PANEL_LINE = "雷属性共鸣时，" + FLAG_TEXT
FLAG_PANEL_INDEX = 2                           # 插在第 2 行（自身逐层行）之后

OLD_DESCRIPTION = B2.DESCRIPTION
#: 技能本体上限（关支 Bind 5.0）照写；强化后的不封顶不进技能描述（口径 R3）⇒ 本轮描述 == 第二批原文。
DESCRIPTION_CAP_TEXT = B2.LAYER_CAP_TEXT                               # （最多5层）
if OLD_DESCRIPTION.count(DESCRIPTION_CAP_TEXT) != 1:
    raise ImportError("batch-2 description no longer carries exactly one layer-cap segment")
DESCRIPTION = OLD_DESCRIPTION
#: 技能描述里不得出现的强化后描述（口径 R3）：强化条件 / 强化后上限的写法。
ENHANCED_DESCRIPTION_MARKS = ("不受此限", "担任队长", "强化后")

PANEL_BEFORE = B2.PANEL_AFTER[PANEL_LEADER]
_LINE0_BEFORE = B2._LEADER_LINE0_AFTER        # 雷属性共鸣时，每层「浪涌充能」，雷属性角色技能伤害＋30%、攻击力＋20%
_LINE1_BEFORE = B2.LEADER_SELF_LINE           # 每层「浪涌充能」，自身攻击力＋30%、技能伤害＋30%


def _pct(value: str) -> str:
    num = int(value)
    if num % 1000:
        raise ValueError(f"{value} is not a whole percent")
    return f"{num // 1000}%"


LINE0_AFTER = (f"雷属性共鸣时，每层「浪涌充能」，雷属性角色技能伤害＋{_pct(NEW_VALUES[0])}、"
               f"攻击力＋{_pct(NEW_VALUES[1])}")
LINE1_AFTER = f"每层「浪涌充能」，自身攻击力＋{_pct(NEW_VALUES[7])}、技能伤害＋{_pct(NEW_VALUES[8])}"


#: C. 口径 5 拆行（主会话扩展 B）：队长覆盖文案里「；」前后是两种数据条件的那一行 → 拆后两行（各自照写共鸣前缀）。
SPLIT_LINE_BEFORE = "雷属性共鸣时，非FEVER模式中冲刺时FEVER槽＋10%；FEVER模式中冲刺时FEVER槽－10%"
SPLIT_LINES_AFTER = ("雷属性共鸣时，非FEVER模式中冲刺时FEVER槽＋10%",
                     "雷属性共鸣时，FEVER模式中冲刺时FEVER槽－10%")
SPLIT_PANEL_INDEX = 6                          # 0 基，插入旗号行之后（第二批原第 6 行 = 下标 5）
SPLIT_ABILITY_KEY = CID + "6"                  # 1399946：这一行描述的是能力 6 的两条「仅队长」行
#: 拆行依据：能力 6 行号 → (前置 2 kind：186 非 Fever / 12 Fever, 强度 c51/c52, 对应面板行)。
SPLIT_ROWS = {1: ("186", "10000", SPLIT_LINES_AFTER[0]),
              2: ("12", "-10000", SPLIT_LINES_AFTER[1])}
#: 两行共有的条件：前置 1 = 雷≥6 共鸣、前置 3 = 42 仅队长、触发 4 冲刺、内容 724 Fever 槽（上限比例）。
SPLIT_SHARED_CELLS = {6: "2", 9: "600000", 10: "600000", 11: "Yellow", 20: "42", 27: "4", 47: "724"}
ABILITY_NCOLS = 126


def _panel_after() -> str:
    lines = PANEL_BEFORE.split("\n")
    if lines[:2] != [_LINE0_BEFORE, _LINE1_BEFORE] or FLAG_TEXT in PANEL_BEFORE:
        raise ValueError("batch-2 leader panel constants drifted")
    lines[:2] = [LINE0_AFTER, LINE1_AFTER]
    lines.insert(FLAG_PANEL_INDEX, FLAG_PANEL_LINE)
    if lines.count(SPLIT_LINE_BEFORE) != 1 or lines[SPLIT_PANEL_INDEX] != SPLIT_LINE_BEFORE:
        raise ValueError("batch-2 leader panel no longer carries the two-condition dash line at the reviewed place")
    lines[SPLIT_PANEL_INDEX:SPLIT_PANEL_INDEX + 1] = list(SPLIT_LINES_AFTER)
    return "\n".join(lines)


PANEL_AFTER = _panel_after()

#: revise() 的输入基线（live 1.4.1053 = 第二批输出 = s7-regis 1.0.8，零漂移）。任一不符 ⇒ 拒绝（fail closed）。
#: 六个能力键只读不改：用来核对旗号 1 空闲（能力里没有 536/704–708）。
BEFORE = {
    ("leader", CID): "632cada29890e1aad692aa28440ec80825bbc14c406b847b88713e9315de162b",
    ("cas", PANEL_LEADER): "76f4dea7257a31810909c7e1520cb153faeac0857eb6c02adf65b734e33b443d",
    ("text", CID): "2aa57d4fc9cb8b204be49140f222d3494920774ba0a9cd5ef4f80fbdd26ad681",
    ("action", CODE): "796d40b88860f15f9988431f725e3c2c30918d4835a96a697c6ac668b13c6715",
    ("dsl", SKILL_PROGRAMS["1"]): "ff467bcf2d390647e65faac81574fcdb18d43a0d19de40a337ad245b29086fe9",
    ("dsl", SKILL_PROGRAMS["2"]): "229758737533bb68d002e8dc612d1107d99e2379f9ce1ea2f67f650e52dcd83b",
    ("server_text", CID): "2aa57d4fc9cb8b204be49140f222d3494920774ba0a9cd5ef4f80fbdd26ad681",
    ("ability", CID + "1"): "a93bbf061ec8ccdddd571f6432b6abff0ffbae80b0fcb4a984472249a0e02552",
    ("ability", CID + "2"): "73802e0e0446918fe0b00083afb52611ca31f644dac385a7de035007f3126b11",
    ("ability", CID + "3"): "d23c07cacf722ac63c2c1f83511fea63dd4161fbe6331dac2a572a1334a93728",
    ("ability", CID + "4"): "a3ad7bfd31d849756ee639cadc27cbbc582b45ba5e2718fe296c95238e1af70e",
    ("ability", CID + "5"): "4bcab9fe2f9c565c762b13e5bd38c99efff47b1ca8c7d75cd6f36de70c059fd0",
    ("ability", CID + "6"): "e7220071979f9b9ee78244b59c9d766ddcd4bd171894e7c8d44085d1568ce40f",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


# ---------------------------------------------------------------- 行

def flag_row() -> list[str]:
    row = [""] * LEADER_NCOLS
    for col, value in FLAG_ROW_CELLS.items():
        row[col] = value
    return row


def flag_rows_in(kind: str, rows: list[list[str]]) -> list[int]:
    """切技能旗号的行下标（瞬发内容列：能力 c47 / 队长 c45；持续块写旗号会 C2308，也一并查 c109 / c107）。"""
    cols = (47, 109) if kind == "ability" else (45, 107)
    return [i for i, row in enumerate(rows) if any(c < len(row) and row[c] in FLAG_KINDS for c in cols)]


def flag_free_problems(leader: list[list[str]], ability: dict[str, list[list[str]]] | None) -> list[str]:
    """旗号 1 必须只由新增的队长 536 行打开：既有队长行与各能力键里不得已有 536/704–708。"""
    probs = [f"leader #{i} already switches a skill flag" for i in flag_rows_in("leader_ability", leader)]
    for key, rows in sorted((ability or {}).items()):
        probs += [f"ability {key}#{i} already switches a skill flag" for i in flag_rows_in("ability", rows)]
    return probs


def leader_rows(leader: list[list[str]], ability: dict[str, list[list[str]]] | None = None) -> list[list[str]]:
    """队长四条逐层成长行 c111/c112 → 原值 4/5；追加 536 旗号 1 行（雷共鸣）。只接受第二批输出。

    ``ability``（可选）= 本角色能力键 → 行，用来核对旗号 1 空闲；其余格与其余行逐字保留。"""
    out = deepcopy(leader)
    if len(out) != LEADER_ROWS_BEFORE or any(len(r) != LEADER_NCOLS for r in out):
        raise ValueError(f"leader_ability:{CID} is not the reviewed {LEADER_ROWS_BEFORE}-row batch-2 output")
    for row in GROWTH_ROWS:
        B2._require(out[row], LEADER_NCOLS, ROWS_BEFORE[row], f"batch-2 leader #{row}")
    probs = flag_free_problems(out, ability)
    if probs:
        raise ValueError(f"skill flag 1 is not free: {probs}")
    for row in GROWTH_ROWS:
        B2._set(out[row], {c: NEW_VALUES[row] for c in VALUE_COLS})
        B2._require(out[row], LEADER_NCOLS, ROWS_AFTER[row], f"regis c leader #{row}")
    out.append(flag_row())
    probs = row_problems(out)
    if probs:
        raise ValueError(f"leader rows fail the legality gates: {probs}")
    return out


def row_problems(rows) -> list[str]:
    """client_legality / declared_block_field / invoke_skill_string（第二批同一实现）+ 536 行文案键必须是
    :data:`FLAG_KEY`（本批同时写进 custom_ability_string；缺键 = 渲染描述 C8601）。"""
    probs = B2.row_problems("leader_ability", rows)
    for i in flag_rows_in("leader_ability", rows):
        if rows[i][45] != SKILL_FLAG_KIND or rows[i][68] != FLAG_KEY:
            probs.append(f"leader_ability#{i}: skill flag row must be 536 with c68={FLAG_KEY!r}")
    return probs


# ---------------------------------------------------------------- DSL

def _is(node, name: str) -> bool:
    return (isinstance(node, list) and len(node) == 2 and node[0] == "Command" and isinstance(node[1], list)
            and bool(node[1]) and node[1][0] == name)


def flag_nodes(tree) -> list[list]:
    return list(B2._commands(tree, "ConditionalsChangeSkillFlag"))


def top_branch(tree) -> list:
    """≥5 层档的 then 块（``tree[11]`` 第 2 条 ConditionalsConditionAccumulationNumber(DCUnique 浪涌, 5)）。"""
    choose = tree[11][1][1] if isinstance(tree[11], list) and len(tree[11]) == 2 and len(tree[11][1]) > 1 else None
    if not _is(choose, "ConditionalsConditionAccumulationNumber") \
            or choose[1][1] != ["DCUnique", int(UID)] or choose[1][2] != TOP_THRESHOLD:
        raise ValueError("unreviewed skill tree: surge ≥5 stage split not found at tree[11][1][1]")
    block = choose[1][3]
    if not (isinstance(block, list) and len(block) == 2 and block[0] == "Block"):
        raise ValueError("unreviewed skill tree: ≥5 stage then-branch is not a Block")
    return block


def _bind_state(node) -> tuple:
    c = node[1]
    return (c[1], c[2], c[3], c[4], c[5], type(c[5]).__name__)


def skill_tree(tree):
    """≥5 层档 ``[Bind(vid1, 5.0), FindNearSubjects]`` → ``[ConditionalsChangeSkillFlag(1, 开支, 关支)]``。

    开支 = 同两节点、Bind 上限 99.0（第二批改前，double）；关支 = live 原两节点逐字。只接受第二批输出。"""
    out = deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl" and out[10] == 0):
        raise ValueError("expected the batch-1/2 skill tree (native ActionDsl, buffTargetAs 0)")
    if flag_nodes(out):
        raise ValueError("unreviewed skill tree: already carries ConditionalsChangeSkillFlag")
    state = sorted((b[1], b[2], b[3], b[4], b[5], type(b[5]).__name__) for b in B2.binds(out))
    want = [(-17, vid, ["DCUnique", int(UID)], 1, CAP_CAPPED, "float") for vid in B2.BIND_VIDS]
    if state != want:
        raise ValueError(f"unreviewed surge layer bindings (expected the batch-2 5.0 caps): {state}")
    block = top_branch(out)
    body = block[1]
    if len(body) != 2 or not _is(body[0], "BindConditionAccumulationVariable") \
            or _bind_state(body[0]) != (-17, TOP_VID, ["DCUnique", int(UID)], 1, CAP_CAPPED, "float") \
            or not _is(body[1], "FindNearSubjects"):
        raise ValueError("unreviewed ≥5 stage body (expected [Bind(vid1, 5.0), FindNearSubjects])")
    off = deepcopy(body)
    on = deepcopy(body)
    on[0][1][5] = CAP_UNCAPPED
    block[1] = [["Command", ["ConditionalsChangeSkillFlag", SKILL_FLAG, ["Block", on], ["Block", off]]]]
    return out


def unwrap(tree):
    """:func:`skill_tree` 的逆：把 ≥5 层档的旗号分支换回关支（测试用：关支 == live 原段）。"""
    out = deepcopy(tree)
    block = top_branch(out)
    if len(block[1]) != 1 or not _is(block[1][0], "ConditionalsChangeSkillFlag"):
        raise ValueError("≥5 stage is not a skill-flag split")
    block[1] = deepcopy(block[1][0][1][3][1])
    return out


def _expr(value) -> bool:
    return isinstance(value, list) and bool(value) and value[0] in ("Block", "Command", "Event")


def _vlv_vids(value) -> list[int]:
    """非表达式参数里出现的 vlv 变量号（CNA p6 等 slv 单元）。"""
    found = []
    if isinstance(value, dict):
        for item in value.get("vlv", []) or []:
            if isinstance(item, dict) and "vid" in item:
                found.append(item["vid"])
        for child in value.values():
            if isinstance(child, (list, dict)):
                found += _vlv_vids(child)
    elif isinstance(value, list) and not _expr(value):
        for child in value:
            found += _vlv_vids(child)
    return found


def vlv_scope_problems(tree) -> list[str]:
    """层数变量作用域（``wf_client_legality`` 的作用域门禁只查主体 lookup，不查 vlv）：

    按词法作用域走树——Block 里 Bind 之后的兄弟（及其子孙）才看得见该变量；ConditionalsChangeSkillFlag 两支各在
    新的局部环境里执行（ActionEvaluator.as:4509-4526），支内的 Bind 在支外不可见。任何 vlv 引用了当前不可见的
    变量号即报错。"""
    probs: list[str] = []

    def walk(node, visible: frozenset, path: str):
        if not isinstance(node, list) or not node:
            return
        tag = node[0]
        if tag == "Block":
            local = set(visible)
            for i, item in enumerate(node[1]):
                walk(item, frozenset(local), f"{path}/{i}")
                if _is(item, "BindConditionAccumulationVariable"):
                    local.add(item[1][2])
            return
        if tag == "Command":
            cmd = node[1]
            for vid in (v for p in cmd[1:] if not _expr(p) for v in _vlv_vids(p)):
                if vid not in visible:
                    probs.append(f"{path}:{cmd[0]} reads vlv vid {vid} outside its Bind scope")
            for i, p in enumerate(cmd[1:], 1):
                if _expr(p):
                    walk(p, visible, f"{path}:{cmd[0]}#{i}")
            return
        if tag == "Event":
            for i, p in enumerate(node[1][1:], 1):
                if _expr(p):
                    walk(p, visible, f"{path}:event#{i}")

    walk(tree[11], frozenset(), "$")
    return probs


def dsl_problems(tree) -> list[str]:
    """AMF3 往返 + 四道客户端门禁（第二批同一实现）+ vlv 作用域。"""
    return B2.dsl_problems(tree) + vlv_scope_problems(tree)


# ---------------------------------------------------------------- 文案

def description(text: str) -> str:
    """技能描述只写本体（口径 R3）：核对是第二批原文并原样返回（本轮不改）。"""
    if text != OLD_DESCRIPTION:
        raise ValueError("skill description is not the batch-2 text")
    if any(mark in DESCRIPTION for mark in ENHANCED_DESCRIPTION_MARKS):
        raise ValueError("skill description must not describe the leader-flag enhancement")
    return DESCRIPTION


def panel_text(key: str, text: str) -> str:
    if key != PANEL_LEADER:
        raise ValueError(f"unexpected panel key {key}")
    if text != PANEL_BEFORE:
        raise ValueError(f"panel text is not the batch-2 text: {key}")
    return PANEL_AFTER


#: 返回面板不许出现的写法：共鸣冒号（口径 3）、全角「／」与半角「/」（口径 5，主会话扩展 B 起覆盖半角）、「；」挤两种条件
#: 的那一行（本模块唯一一处已拆）。
FORBIDDEN_PANEL_MARKS = ("属性共鸣时：", "属性共鸣时:", "／", "/")


def panel_problems(key: str, text: str) -> list[str]:
    """面板规则；:data:`FLAG_KEY` 是技能强化条目 ⇒ ``skill_flag=True``（不写数字与时间）。另拦共鸣冒号、全角 / 半角斜杠，
    以及拆行前的那一行原文（「；」挤两种数据条件）。"""
    import wf_midautumn_kitlib as KL
    probs = KL.panel_problems(text, skill_flag=(key == FLAG_KEY))
    probs += [f"panel text contains {mark!r}" for mark in FORBIDDEN_PANEL_MARKS if mark in text]
    if SPLIT_LINE_BEFORE in text.split("\n"):
        probs.append("panel line joins two data conditions with 「；」 (split it, 口径 5)")
    return probs


def split_basis_problems(ability6: list[list[str]]) -> list[str]:
    """口径 5 拆行的数据依据（只读）：能力 6 #1/#2 共有前置 1 雷≥6 共鸣 / 前置 3 = 42 仅队长 / 触发 4 冲刺 / 内容 724，
    前置 2 分别是 186 非 Fever、12 Fever（两种数据条件，否则该合并而不是拆），强度与拆出的两行逐一对上。"""
    if len(ability6) != 3 or any(len(row) != ABILITY_NCOLS for row in ability6):
        return [f"ability:{SPLIT_ABILITY_KEY} is not the reviewed 3-row shape"]
    probs = []
    for index, (fever_kind, value, line) in SPLIT_ROWS.items():
        row = ability6[index]
        shared = {col: row[col] for col in SPLIT_SHARED_CELLS}
        if shared != SPLIT_SHARED_CELLS:
            probs.append(f"ability {SPLIT_ABILITY_KEY}#{index}: shared cells drifted {shared}")
        if row[13] != fever_kind:
            probs.append(f"ability {SPLIT_ABILITY_KEY}#{index}: precondition 2 {row[13]!r} != {fever_kind!r}")
        if (row[51], row[52]) != (value, value):
            probs.append(f"ability {SPLIT_ABILITY_KEY}#{index}: strength {row[51]}/{row[52]} != {value}")
        sign = "＋" if int(value) > 0 else "－"
        if not line.startswith("雷属性共鸣时，") or not line.endswith(f"FEVER槽{sign}{abs(int(value)) // 1000}%"):
            probs.append(f"ability {SPLIT_ABILITY_KEY}#{index}: panel line {line!r} does not match the data")
    first, second = (ability6[i] for i in SPLIT_ROWS)
    if [first[c] for c in range(6, 37)] == [second[c] for c in range(6, 37)]:
        probs.append("split rows share one data condition: merge instead of splitting")
    return probs


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
        if fields[16] != "(None)":            # 自动施放的「按旗号改条件」只看旗号 1（AutoplaySkillReadyShapes）
            raise ValueError(f"action_skill {inner} c16={fields[16]!r} would react to skill flag 1")
        fields[1] = description(fields[1])
        out.append((inner, fields))
    if [k for k, _ in out] != ["1", "2"]:
        raise ValueError("action_skill inner keys drift")
    return out


# ---------------------------------------------------------------- 批次入口

def _require_absent(read: Callable[[str, Any], Any], kind: str, key: Any) -> None:
    try:
        read(kind, key)
    except KeyError:
        return
    raise ValueError(f"{kind}:{key} already exists in live (unreviewed)")


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    live = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        if digest(value) != want:
            raise ValueError(f"live input drifted from the reviewed baseline: {kind}:{key}")
        live[kind, key] = deepcopy(value)
    _require_absent(read, "cas", FLAG_KEY)
    action = live["action", CODE]
    if action[0][1][0] != SKILL_NAME:
        raise ValueError(f"skill name drifted: {action[0][1][0]!r} != {SKILL_NAME!r} (flag text names the skill)")
    ability = {key: live["ability", key] for key in ABILITY_KEYS}
    leader = leader_rows(live["leader", CID], ability)
    dsl = {program: skill_tree(live["dsl", program]) for program in SKILL_PROGRAMS.values()}
    probs = [f"{program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    cells = live["cas", PANEL_LEADER]
    if len(cells) != 1 or len(cells[0]) != 1:
        raise ValueError("unexpected custom_ability_string row shape")
    cas = {PANEL_LEADER: [[panel_text(PANEL_LEADER, cells[0][0])]], FLAG_KEY: [[FLAG_TEXT]]}
    probs += [f"{key}: {p}" for key, value in cas.items() for p in panel_problems(key, value[0][0])]
    probs += [f"panel split basis: {p}" for p in split_basis_problems(live["ability", SPLIT_ABILITY_KEY])]
    # 技能描述 5 处：核对第二批原文与 action_skill c16（不读旗号）；口径 R3 下结果 == live ⇒ 不返回
    unchanged = (text_rows(live["text", CID]) == live["text", CID]
                 and text_rows(live["server_text", CID]) == live["server_text", CID]
                 and [(k, list(f)) for k, f in action_rows(action)] == [(k, list(f)) for k, f in action])
    if not unchanged:
        probs.append("skill descriptions would change (口径 R3: only the leader panel describes the enhancement)")
    if probs:
        raise ValueError(probs)
    return {
        "ability": {},
        "leader": {CID: leader},
        "cas": cas,
        "text": {},
        "table": {},
        "action": {},
        "dsl": dsl,
        "server_text": {},
        "new_programs": [],
        "notes": {
            "request": "第三轮 c：作者「雷吉斯队长技的成长太慢了,fever对雷吉斯来说很难快速进出」「砍到4/5,或者7/10」"
                       "「数值尽量取5的倍数」；技能倍率「成长条件放到队长技里面带上对应共鸣条件」（口径 U3）",
            "leader_growth": "c111/c112 = 原值×4/5：#0 雷队技伤 30000→120000（原 150000）；#1 雷队攻击 20000→80000"
                             "（原 100000）；#7 自身攻击 30000→120000（原 150000）；#8 自身技伤 30000→120000（原 150000）；"
                             "c100 仍 (None)；#2–#6 逐字保留",
            "frequency": "浪涌=进 Fever +1（能力1#2 主位）与 Fever 结束 +1（队长#6）；每次进 Fever 槽上限 ×1.25、Fever 中"
                         "不攒槽 ⇒ 3 分钟约 5–8 次 Fever、10–16 层（推断，按 12 层）⇒ 难 ⇒ 4/5",
            "leader_flag_row": "追加 #9：536 ChangeSkillFlag（旗号 1，瞬发无触发），前置 kind 2 雷·编成≥6，c68 "
                               f"{FLAG_KEY}；同形先例 live 149999#11、官方 dryad_hw23 121189#2；9→10 行",
            "skill_dsl": "两档 ≥5 层档 [Bind(vid1,5.0), FindNearSubjects] → ConditionalsChangeSkillFlag(1, "
                         "[Bind(vid1,99.0), 同光束], [live 原两节点])；3–4 / 0–2 层档不动（上限到不了）",
            "text": f"新 CAS {FLAG_KEY}「{FLAG_TEXT}」（技能强化条目，官方格式点名技能、无数字）；队长覆盖文案前两行 "
                    f"120/80、120/120 并在第 2 行后插入「{FLAG_PANEL_LINE}」；技能描述 5 处不改（保持第二批「（最多5层）」，"
                    "强化后的不封顶只写在队长面板强化条目，口径 R3）",
            "panel_split": {
                "rule": "主会话口径 5 扩展 B（2026-09-27 暂存前最后一轮）：一行挤两种数据条件的按数据条件拆行",
                f"L{SPLIT_PANEL_INDEX + 1}": {"from": SPLIT_LINE_BEFORE, "to": list(SPLIT_LINES_AFTER)},
                "basis": f"ability:{SPLIT_ABILITY_KEY}#1（前置2 186 非Fever）/ #2（前置2 12 Fever）：共有前置1 雷≥6 共鸣、"
                         "前置3 42 仅队长、触发 4 冲刺、内容 724 Fever 槽 ±10% ⇒ 两种数据条件，各自照写「雷属性共鸣时，」",
                "layout": "队长覆盖文案第二批 7 行 → 本轮 9 行（插入旗号行 + 拆出 1 行），其余行逐字",
                "rule_scan": "返回面板无「X属性共鸣时：」、无全角「／」与半角「/」（panel_problems）",
            },
            "unchanged": "能力 3#3/#4 封顶版（每层 30%、最多 5 层）与面板 _3（口径 D4）；队长充能 / Fever 行；"
                         "旗号 1 在能力 1–6 与队长既有行里空闲（已核对）",
            "superseded": "wf_balance_20260927b_regis2（1/2 版，未提交未发布）作废，由本模块取代",
            "generator": "wf_seasonal7_kit_regis：balance_c_rows / balance_c_panel / balance_c.skill_tree / "
                         "balance_c.description 叠在第二批层之后，kit 重跑 == revise()",
            "runtime_verified": False,
        },
    }

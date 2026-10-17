# -*- coding: utf-8 -*-
"雷吉斯·海滨 139994 ``rec_android_seaside``：2026-09-27 平衡第二批（无上限成长，纯函数）。\n\n作者口径（``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md`` A 节）：无上限成长全部放到\n队长技并大幅放缓；能力栏换成有上限的弱化版；技能 DSL 里随层数无上限增长的倍率做成带上限的弱化版\n（雷吉斯 5 层），无上限部分由队长技承担。叠在第一批 ``wf_balance_20260927_regis``（能力相关都换成\n技能伤害）之后；输入 = live 1.4.1049（= 第一批输出 = 候选 s7-regis 1.0.7，逐字相同、零漂移）。\n\n频率（口径 A2，按 3 分钟实际触发次数）：「浪涌充能」只由进入 Fever（能力 1#2，461，主位）与 Fever\n结束（队长 #6，184）各 +1 层；队长 Fever 时间 −50%、非 Fever 雷队技能 Fever 槽 +10%（CT 5 秒）、冲刺\n±10% ⇒ 3 分钟约 6–10 次 Fever ⇒ 当队长约 12–20 层、非队长主位约 6–10 层。每层一步，≤30 次 ⇒ 每步 ×1/5。\n\n落点（行号 = 0 起下标）：\n\n1. ``leader_ability:139994``（7 → 9 行）\n   - #0 每层「浪涌充能」雷队技能伤害（持续 134 → kind 2，全队雷，共鸣）c111/c112 150000 → 30000；\n   - #1 每层雷队攻击力（134 → kind 0）c111/c112 100000 → 20000；\n   - #7 新增 = ``[CODE, '0', '']`` + 能力 3#3 ``[5:]``（自身攻击力 / 134 / c100 ``(None)``）c111/c112 30000；\n   - #8 新增 = ``[CODE, '0', '']`` + 能力 3#4 ``[5:]``（自身技能伤害）c111/c112 30000。\n     队长 #0/#1 是全队雷 + 共鸣前置，目标与前置都不同 ⇒ 不合并（口径 A3）。官方队长先例：\n     ``161063#2``（134 → kind 0 自身）/ ``161063#3``（134 → kind 2 自身）。\n2. ``ability:1399943``（主位键，5 行）#3 / #4：c102 ``(None)`` → ``5``、c113/c114 150000 → 30000\n   （每层 +30%，最多 5 层 = 满 150%；官方形态 ``1610631#1/#2``：134 自身攻/技伤、c102=4）。\n   客户端：``DuringConditionAccumulationChecker.getActiveCount`` = ``TriggerLimitTools.limit(c102, 层数/阈值)``。\n3. 两档技能 DSL：三条 ``BindConditionAccumulationVariable(-17, vid 1/2/3, DCUnique 13999401, 1, 99.0)``\n   第 5 参（上限，double）99.0 → 5.0。客户端 ``ActionEvaluator`` case 101：\n   ``var = Math.min(层数 / 除数, 上限)``，CNA p6 的 vlv（每段 +1.5 倍 × 10 段 = 每层 +15 倍）读它 ⇒\n   层数贡献封顶 5 层（≥5 层分支 100 + 75 = 175 倍封顶）。官方先例：``blackflower_wiz_smr22_1/_2``\n   同命令第 5 参 = 10。三档分支（≥5 / 3–4 / 0–2 层）都改成 5.0，实际只有 ≥5 层分支会触顶。\n   无上限的部分由队长 #0/#1（同一固有层数的逐层成长行）承担 ⇒ 视为已合并（口径 A5）。\n4. 技能描述 5 处（action_skill 两档 c1、character_text c5/c7、服务端镜像 [5]/[7]）：\n   「每层额外＋15倍」→「每层额外＋15倍（最多5层）」。\n5. 面板：``desc_override_rec_android_seaside`` 第 1 行 150/100 → 30/20，并在其后插入\n   「每层「浪涌充能」，自身攻击力＋30%、技能伤害＋30%」；``desc_override_rec_android_seaside_3``\n   第 4 行 150/150 → 30/30 并加「（最多5层）」。无上限的句子写到效果为止（作者裁决，不写「可无限累积」）。\n\n生成器 ``wf_seasonal7_kit_regis.build``：plan → 第二轮 → 浪涌（``wf_regis_surge_stages``）→ 第一批\n（``wf_balance_20260927_regis``）→ 本批（:func:`growth_rows` / :func:`skill_tree` / :func:`panel_text` /\n:func:`description`），kit 重跑产物 == :func:`revise`。本模块只转换传入值，不读写 live / 候选 / assets。\n"
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_balance_20260927_regis as batch1

CID = "139994"
CODE = "rec_android_seaside"
PACKAGES = ["s7-regis"]
#: 候选 manifest 现值 1.0.7（第一批写入）→ 下一号。
PACKAGE_VERSION = {"s7-regis": "1.0.8"}
CAPABILITIES: list[str] = []
#: 候选 126 个 manifest 条目与文件逐一一致（2026-09-27 只读核对），本模块读取的各键与 live 逐字相同。
REVIEWED_DRIFT: dict = {}

UID = "13999401"
ELEMENT = 2                                  # 内部 ElementKind：雷
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
THIRD_KEY = CID + "3"
MAIN_ICON = batch1.MAIN_ICON

LAYER_CAP = 5
LAYER_CAP_TEXT = f"（最多{LAYER_CAP}层）"
DSL_CAP_BEFORE, DSL_CAP_AFTER = 99.0, float(LAYER_CAP)
BIND_VIDS = (1, 2, 3)                         # ≥5 层 / 3–4 层 / 0–2 层三档光束各绑一个变量
VLV_PER_HIT = {"vid": None, "min": 0.0, "max": 1.5}   # 每段 +1.5 倍 × 10 段 = 每层 +15 倍（不改）

SKILL_PROGRAMS = batch1.SKILL_PROGRAMS
PANEL_LEADER = batch1.PANEL_KEYS["leader"]
PANEL_THIRD = batch1.PANEL_KEYS["3"]

# ---------------------------------------------------------------- 行指纹（全部非空列；其余列必须为空）

_RES_L = {4: "2", 7: "600000", 8: "600000", 9: "Yellow"}          # 队长前置 1：雷共鸣
_STACK_L = {0: CODE, 1: "0", 3: "1", **_RES_L, 11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0",
            98: "100000", 99: "100000", 100: "(None)", 102: UID, 106: "false", 108: "5", 109: "Yellow"}
LEADER_TEAM_SKILL = {**_STACK_L, 107: "2", 111: "150000", 112: "150000"}
LEADER_TEAM_ATTACK = {**_STACK_L, 107: "0", 111: "100000", 112: "100000"}
LEADER_TEAM_SKILL_AFTER = {**LEADER_TEAM_SKILL, 111: "30000", 112: "30000"}
LEADER_TEAM_ATTACK_AFTER = {**LEADER_TEAM_ATTACK, 111: "20000", 112: "20000"}

_STACK_A = {0: f"{CODE}_3", 1: "false", 2: "attack_yellow", 3: "0", 5: "1", 6: "0", 13: "0", 20: "0",
            85: "(None)", 97: "134", 98: "0", 100: "100000", 101: "100000", 104: UID, 108: "false", 110: "0"}
THIRD_SELF_ATTACK = {**_STACK_A, 102: "(None)", 109: "0", 113: "150000", 114: "150000"}
THIRD_SELF_SKILL = {**_STACK_A, 102: "(None)", 109: "2", 113: "150000", 114: "150000"}
THIRD_SELF_ATTACK_AFTER = {**THIRD_SELF_ATTACK, 102: str(LAYER_CAP), 113: "30000", 114: "30000"}
THIRD_SELF_SKILL_AFTER = {**THIRD_SELF_SKILL, 102: str(LAYER_CAP), 113: "30000", 114: "30000"}

#: 从能力 3 搬进队长的两行（能力 c≥5 → 队长 c−2；c100 保持 ``(None)`` = 队长侧不设上限）。
MOVED_SELF_ATTACK = {0: CODE, 1: "0", 3: "1", 4: "0", 11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0",
                     98: "100000", 99: "100000", 100: "(None)", 102: UID, 106: "false", 107: "0", 108: "0",
                     111: "30000", 112: "30000"}
MOVED_SELF_SKILL = {**MOVED_SELF_ATTACK, 107: "2"}

LEADER_ROWS_BEFORE, LEADER_ROWS_AFTER = 7, 9
THIRD_ROWS = 5
TEAM_SKILL_ROW, TEAM_ATTACK_ROW = 0, 1
SELF_ATTACK_ROW, SELF_SKILL_ROW = 3, 4

# ---------------------------------------------------------------- 文案

OLD_DESCRIPTION = batch1.DESCRIPTION
DESCRIPTION_SEGMENT = "每层额外＋15倍"
DESCRIPTION = OLD_DESCRIPTION.replace(DESCRIPTION_SEGMENT, DESCRIPTION_SEGMENT + LAYER_CAP_TEXT, 1)

PANEL_BEFORE = {PANEL_LEADER: batch1.PANEL_AFTER[PANEL_LEADER],
                PANEL_THIRD: batch1.PANEL_AFTER[PANEL_THIRD]}
_LEADER_LINE0_BEFORE = "雷属性共鸣时，每层「浪涌充能」，雷属性角色技能伤害＋150%、攻击力＋100%"
_LEADER_LINE0_AFTER = "雷属性共鸣时，每层「浪涌充能」，雷属性角色技能伤害＋30%、攻击力＋20%"
LEADER_SELF_LINE = "每层「浪涌充能」，自身攻击力＋30%、技能伤害＋30%"
_THIRD_LINE3_BEFORE = MAIN_ICON + "每层「浪涌充能」，自身攻击力＋150%、技能伤害＋150%"
_THIRD_LINE3_AFTER = MAIN_ICON + "每层「浪涌充能」，自身攻击力＋30%、技能伤害＋30%" + LAYER_CAP_TEXT


def _panel_after() -> dict[str, str]:
    leader = PANEL_BEFORE[PANEL_LEADER].split("\n")
    third = PANEL_BEFORE[PANEL_THIRD].split("\n")
    if leader[0] != _LEADER_LINE0_BEFORE or third[3] != _THIRD_LINE3_BEFORE:
        raise ValueError("batch-1 panel constants drifted")
    leader[0:1] = [_LEADER_LINE0_AFTER, LEADER_SELF_LINE]
    third[3] = _THIRD_LINE3_AFTER
    return {PANEL_LEADER: "\n".join(leader), PANEL_THIRD: "\n".join(third)}


PANEL_AFTER = _panel_after()

#: revise() 的输入基线（live 1.4.1049 = s7-regis 1.0.7，零漂移）。任一不符 ⇒ 拒绝（fail closed）。
BEFORE = {
    ("leader", CID): "4190371061cabf43823b750a4cf9f6a824477a3953ee20dd105019202f91900d",
    ("ability", THIRD_KEY): "d143689dee46b500a905d11d77ecef09eccba5e9821916180fa189f6f4658986",
    ("cas", PANEL_LEADER): "984ec7e05bb3c0d908cccfa33dd2f502df80baeed529a44366dd0663dbe19f80",
    ("cas", PANEL_THIRD): "210f2b8f4fe369910ea2fa9192be56a6fe059be6d2c1f68a0a8f5f374be5fa73",
    ("text", CID): "bdf7ac4ab1aea957cde85b6042d6e1c1d03a0ebd75fc19a0a5b897900e1de840",
    ("action", CODE): "e036cfcdc96748f37be1d5cfd7a37eb7ef8611de522d6f711546a88645d43ef1",
    ("dsl", SKILL_PROGRAMS["1"]): "a957c3af3ce4056c24057606aa247db644708004312040bd109e2fe54608fea1",
    ("dsl", SKILL_PROGRAMS["2"]): "75030f80f267d68d105404b90eb9a8bff7d4870e2c2b2e15cd093d9e02131282",
    ("server_text", CID): "bdf7ac4ab1aea957cde85b6042d6e1c1d03a0ebd75fc19a0a5b897900e1de840",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


# ---------------------------------------------------------------- 行

def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width and all(row[c] == v for c, v in cells.items())
            and all(v == "" for c, v in enumerate(row) if c not in cells))


def _require(row: list[str], width: int, cells: dict[int, str], label: str) -> None:
    if not _matches(row, width, cells):
        got = {c: v for c, v in enumerate(row) if v != "" or c in cells}
        raise ValueError(f"unreviewed {label} preimage: {got}")


def _set(row: list[str], cells: dict[int, str]) -> None:
    for col, value in cells.items():
        row[col] = value


def moved_row(ability_row: list[str]) -> list[str]:
    """能力行 → 队长行：``[CODE, '0', '']`` + 能力 ``[5:]``（列号能力 c≥5 → 队长 c−2）。"""
    if len(ability_row) != ABILITY_NCOLS:
        raise ValueError("unexpected ability row width")
    row = [CODE, "0", ""] + deepcopy(ability_row[5:])
    if len(row) != LEADER_NCOLS:
        raise ValueError("moved leader row width")
    return row


def growth_rows(leader: list[list[str]], third: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    """队长放缓 + 能力 3 两行搬入队长（1/5）+ 能力 3 原位换成「最多 5 层」。只接受第一批输出。"""
    leader, third = deepcopy(leader), deepcopy(third)
    if len(leader) != LEADER_ROWS_BEFORE or any(len(r) != LEADER_NCOLS for r in leader):
        raise ValueError(f"leader_ability:{CID} is not the reviewed {LEADER_ROWS_BEFORE}-row batch-1 output")
    if len(third) != THIRD_ROWS or any(len(r) != ABILITY_NCOLS for r in third):
        raise ValueError(f"ability:{THIRD_KEY} is not the reviewed {THIRD_ROWS}-row batch-1 output")
    _require(leader[TEAM_SKILL_ROW], LEADER_NCOLS, LEADER_TEAM_SKILL, "leader per-stack team skill damage")
    _require(leader[TEAM_ATTACK_ROW], LEADER_NCOLS, LEADER_TEAM_ATTACK, "leader per-stack team attack")
    _require(third[SELF_ATTACK_ROW], ABILITY_NCOLS, THIRD_SELF_ATTACK, "ability 3 per-stack self attack")
    _require(third[SELF_SKILL_ROW], ABILITY_NCOLS, THIRD_SELF_SKILL, "ability 3 per-stack self skill damage")

    moved = []
    for source, cells in ((third[SELF_ATTACK_ROW], MOVED_SELF_ATTACK), (third[SELF_SKILL_ROW], MOVED_SELF_SKILL)):
        row = moved_row(source)
        row[111] = row[112] = "30000"                # 150% × 1/5
        _require(row, LEADER_NCOLS, cells, "moved leader row")
        moved.append(row)
    _set(leader[TEAM_SKILL_ROW], {111: "30000", 112: "30000"})      # 150% × 1/5
    _set(leader[TEAM_ATTACK_ROW], {111: "20000", 112: "20000"})     # 100% × 1/5
    leader.extend(moved)

    cap = {102: str(LAYER_CAP), 113: "30000", 114: "30000"}       # 每层 30%，最多 5 层
    _set(third[SELF_ATTACK_ROW], cap)
    _set(third[SELF_SKILL_ROW], cap)
    probs = row_problems("leader_ability", leader) + row_problems("ability", third)
    if probs:
        raise ValueError(f"growth rows fail the legality gates: {probs}")
    return leader, third


# ---------------------------------------------------------------- DSL

def _commands(node, name: str):
    if isinstance(node, list):
        if node and node[0] == "Command" and len(node) == 2 and isinstance(node[1], list) \
                and node[1] and node[1][0] == name:
            yield node[1]
        for child in node:
            yield from _commands(child, name)


def binds(tree) -> list[list]:
    return list(_commands(tree, "BindConditionAccumulationVariable"))


def skill_tree(tree):
    """三条浪涌层数绑定的上限 99.0 → 5.0；其余节点逐字保留。只接受第一批输出（bta 0 / ACSkillDamage）。"""
    out = deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl" and out[10] == 0):
        raise ValueError("expected the batch-1 skill tree (native ActionDsl, buffTargetAs 0)")
    found = binds(out)
    state = [(b[1], b[2], b[3], b[4], b[5]) for b in found]
    want = [(-17, vid, ["DCUnique", int(UID)], 1, DSL_CAP_BEFORE) for vid in BIND_VIDS]
    if sorted(state, key=lambda s: s[1]) != want or any(not isinstance(b[5], float) for b in found):
        raise ValueError(f"unreviewed surge layer bindings: {state}")
    grown = [cell for cna in _commands(out, "CreateNormalAttack") for cell in cna[6] if "vlv" in cell]
    if sorted(cell["vlv"][0]["vid"] for cell in grown) != list(BIND_VIDS) \
            or any(cell["vlv"] != [dict(VLV_PER_HIT, vid=cell["vlv"][0]["vid"])] for cell in grown):
        raise ValueError("per-layer vlv growth drifted")
    for bind in found:
        bind[5] = DSL_CAP_AFTER
    return out


# ---------------------------------------------------------------- 文案

def description(text: str) -> str:
    if text != OLD_DESCRIPTION:
        raise ValueError("skill description is not the batch-1 text")
    return DESCRIPTION


def panel_text(key: str, text: str) -> str:
    if key not in PANEL_BEFORE:
        raise ValueError(f"unexpected panel key {key}")
    if text != PANEL_BEFORE[key]:
        raise ValueError(f"panel text is not the batch-1 text: {key}")
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


# ---------------------------------------------------------------- 门禁

def row_problems(kind: str, rows) -> list[str]:
    import wf_client_legality as L
    probs = []
    for i, row in enumerate(rows):
        for p in (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
                  + L.invoke_skill_string_problems(row, {batch1.STRIKE_KEY}, kind)):
            probs.append(f"{kind}#{i}: {p}")
    return probs


def dsl_problems(tree) -> list[str]:
    import wf_client_legality as L
    import wf_dsl
    probs = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        probs.append("AMF3 roundtrip mismatch")
    probs += L.action_dsl_element_problems(tree, ELEMENT)
    probs += L.action_dsl_subject_binding_problems(tree)
    probs += L.action_dsl_lookup_scope_problems(tree)
    probs += L.action_dsl_hit_area_target_problems(tree)
    return probs


def panel_problems(text: str) -> list[str]:
    import wf_midautumn_kitlib as KL
    return KL.panel_problems(text)


# ---------------------------------------------------------------- 批次入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    live = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        if digest(value) != want:
            raise ValueError(f"live input drifted from the reviewed baseline: {kind}:{key}")
        live[kind, key] = deepcopy(value)
    leader, third = growth_rows(live["leader", CID], live["ability", THIRD_KEY])
    dsl = {program: skill_tree(live["dsl", program]) for program in SKILL_PROGRAMS.values()}
    probs = [f"{program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    cas = {key: [[panel_text(key, live["cas", key][0][0])]] for key in PANEL_BEFORE}
    probs += [f"{key}: {p}" for key, cells in cas.items() for p in panel_problems(cells[0][0])]
    if probs:
        raise ValueError(probs)
    server = deepcopy(live["server_text", CID])
    server[0][5], server[0][7] = description(server[0][5]), description(server[0][7])
    return {
        "ability": {THIRD_KEY: third},
        "leader": {CID: leader},
        "cas": cas,
        "text": {CID: text_rows(live["text", CID])},
        "table": {},
        "action": {CODE: action_rows(live["action", CODE])},
        "dsl": dsl,
        "server_text": {CID: server},
        "new_programs": [],
        "notes": {
            "request": "第二批口径 A：无上限成长移到队长并放缓；能力栏有上限；技能 DSL 层数贡献封顶 5 层（A5）",
            "frequency": "浪涌=进 Fever +1（能力1#2 主位）与 Fever 结束 +1（队长#6）；3 分钟约 6–10 次 Fever ⇒ "
                         "队长 12–20 层 / 非队长主位 6–10 层；≤30 步 ⇒ 每步 ×1/5",
            "leader": "#0 c111/c112 150000→30000；#1 100000→20000；新增 #7/#8 = [CODE,'0','']+能力3#3/#4[5:]，"
                      "c111/c112 30000（自身攻/技伤每层 +30%，c100 (None)）；7→9 行",
            "ability3": "#3/#4 c102 (None)→5、c113/c114 150000→30000（每层 +30%，最多 5 层，官方 1610631#1/#2 形态）",
            "skill_dsl": "BindConditionAccumulationVariable ×3 第 5 参 99.0→5.0（ActionEvaluator case 101 "
                         "min(层数/除数, 上限)；官方 blackflower_wiz_smr22 上限 10）；vlv/倍率/分支不动",
            "merge": "技能层数无上限部分由队长 #0/#1（同一固有逐层成长）承担，视为已合并；队长 #0/#1 全队+共鸣，"
                     "与自身行目标/前置不同，不合并",
            "text": "技能描述 5 处加「（最多5层）」；面板队长首行放缓并新增自身行、能力3 第 4 行 30%+（最多5层）",
            "not_in_batch": "队长 #4「进入 Fever 自身技能槽＋25%」等充能行按口径 A6 本批不动",
            "runtime_verified": False,
        },
    }

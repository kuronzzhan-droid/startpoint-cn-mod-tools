# -*- coding: utf-8 -*-
"基诺维「破契的黑翼」169999 ``ginovi``（暗）：2026-09-27 平衡第三轮（c，成长复核）。\n\n口径 = 主会话 ``growth_c_spec.md``（作者原话：成长「砍到4/5，或者7/10」「可以砍到2/3」「数值尽量取5的倍数」；\n默认选择 D1/D3），数值表 = ``reeval_full.json`` table.rows 的 169999 一行。本角色不在技能倍率撤封顶名单里。\n\n队长 ``leader_ability:169999`` #6/#7/#8：暗共鸣 + trigger 235 ConditionKeepFramePiercing（自身每保持贯穿 90 帧＝1.5 秒\n一跳，c32=(None) 不限次）→ 暗属性全队 攻击力 32 / 技能伤害 34 / 能力伤害 388。第二批（``wf_balance_20260927b_ginovi``，\n1.4.1051 已发布）把每跳 25% 砍到 2.5%；本轮回调：触发很频繁（3 分钟约 84 跳）、基础充足 ⇒ 下限 2/3：\n25×2/3=16.7，不低于 2/3 的 5 的倍数只有 20%（D1：取 20%，不用 17.5%）⇒ c49/c50 2500 → 20000。\n面板 ``desc_override_ginovi`` 原第 4 行（拆行后第 5 行）三处「＋2.5%」→「＋20%」。\n\n面板拆行（主会话第三轮追加 B = 口径 5 扩展：一行挤两种数据条件的按数据条件拆行）：原第 3 行\n「常态冲刺冷却时间延长，冲刺效果强化；暗属性共鸣时，弹射后冲刺冷却时间缩短（3秒）」按「；」拆两行，文字不改：\n\n- 「常态冲刺冷却时间延长，冲刺效果强化」= 能力1 ``1699991`` #2–#7（during 422 DashParameter；前置 42 仅队长、\n  无共鸣；#2–#6 常驻：速度 / 高度上限 / 蓄力 / 回拉 / 冷却倍率 +83.3%，#7 疾走中冷却补偿）；\n- 「暗属性共鸣时，弹射后冲刺冷却时间缩短（3秒）」= 队长 #5（暗编成≥6 + 触发 6 BallFlip → 31 ConditionSwift 180 帧）。\n\n两组前置不同（一组无共鸣、一组带暗共鸣）⇒ 两种数据条件，按口径 5 拆行；依据只读核对（:func:`split_basis_problems`，\n不符即拒绝）。能力1 ``1699991`` 因此进 :data:`BEFORE`（只读，不返回）。\n\n不动：其余 8 行队长行（722、629 ×4、疾走、开局技能槽、死印乘区）；第二批的削韧（技能/629/PF 本体 p13）；\n不新增共鸣前置（D3，本来就带暗共鸣）。\n\n技能强化文案（作者原话「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的\n效果,规范并简化描述做了吗」；主会话口径 R1–R4）：\n\n- 强化条目 ``change_skill_ginovi``（能力1 ``1699991`` #1 kind 536，旗号 1，前置 暗≥6 共鸣，c70 = 本串）按官方格式\n  「为『掠影协奏』追加「…」」重写，定性不写数字（原「直接攻击变为3次」「1层」）⇒「直接攻击分为多次」「不可消除的「死印」」，\n  内容不变（旗号 1 开支：额外 ACAttackPoint、ACAdditionalDirectAttack(3)、额外护盾与 ACFixedSpeed、最近敌人 ACUnique\n  1699901「死印」、首次（DCUnique 169998 计数）血契）。\n- 能力1 面板 ``desc_override_ginovi_1`` 第 2 行（描述同一 536 行）=「暗属性共鸣时，」+ 同一条目（原文带数字且与条目不一致：\n  缺「为」、血契后半句）；第 1 行逐字。\n- 技能说明（action_skill 两档 c1、character_text c5/c7）本来就只写技能本体，不改；数据行与 DSL 一格不动（R4）。\n\n生成器 ``work/character_packs/ginovi/build_workspace.py``（kit-v3 的 ``write_m3_leader_rows``）：只改源码常量\n``PIERCING_BUFF`` 与 ``DESC_OVERRIDE_LINES['desc_override_ginovi']``（第 3 行拆成 [2]/[3]，贯穿行移到 [4]），\n测试断言生成器输出 == :func:`revise` 输出。\nkit-v3 影子表是构建产物，本模块不重建（重建会写包，需主会话执行）。\n\n接口见 ``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``：:func:`revise` 只经 ``read`` 读 live，\n开头按 :data:`BEFORE` 摘要校验（漂移即抛 :class:`GinoviBalanceError`，fail closed），不改 ``read`` 的返回对象。\n本模块不写 live store / assets / .cdn / 候选包，不发布，不 git。\n"
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as L
import wf_midautumn_kitlib as KL

CID = "169999"
CODE = "ginovi"
PACKAGES = ["ginovi"]
#: 候选现值 0.3.1（``work/character_packs/ginovi/package/manifest.json``，第二批与 kit-v3 重建已回写）→ 递增。
PACKAGE_VERSION = {"ginovi": "0.3.2"}
#: 候选已声明 dash-parameter-v1 / panel-description-override-v2；只改数值，不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 ginovi 与 live 在本模块读取的 7 个键上逐字相同（2026-09-27 只读核对；能力1 ``1699991`` 为拆行依据新增）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 5                       # master/character c3：暗（0 基内部元素）
ELEMENT_TOKEN = "Black"
LEADER = CID
LEADER_NCOLS = 124
LEADER_ROWS = 11
CAS_LEADER = f"desc_override_{CODE}"
_ACTION = "battle/action/skill/action/ability_skill/"
#: 629 行 0 基行号 → (trigger c25, CT c33, 文案键 c68)；只读核对。
INVOKE_ROWS = {1: ("180", "36", f"ability_skill_{CODE}_pf_lv1"), 2: ("181", "36", f"ability_skill_{CODE}_pf_lv2"),
               3: ("182", "36", f"ability_skill_{CODE}_pf_lv3"), 4: ("4", "20", f"ability_skill_{CODE}_dash")}
CAS_INVOKE = tuple(name for _t, _c, name in INVOKE_ROWS.values())

# ------------------------------------------------------------------ 数值

PIERCING_ROWS = {6: "32", 7: "34", 8: "388"}          # 0 基行号 → c45 内容 kind（攻 / 技伤 / 能伤）
TICK_COLS = (49, 50)
OLD_TICK, NEW_TICK = "2500", "20000"                  # 千 = 1%：第二批 2.5% → 本轮 20%
ORIGINAL_TICK = "25000"                               # 第二批之前 25%
TICK_FRAMES = 90
THREE_MIN_TICKS = 84                                  # 表 reeval_full：72–96 跳，按 84 跳算
#: 三行共有的前置/触发/目标格（改前改后都必须成立；其余列必须为空）。
PIERCING_GATE = {0: CODE, 1: "0", 2: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
                 11: "0", 18: "0", 25: "235", 26: "0", 28: "100000", 29: "100000",
                 30: str(TICK_FRAMES * 100000), 31: str(TICK_FRAMES * 100000), 32: "(None)", 33: "0",
                 37: "(None)", 44: "0", 46: "5", 47: ELEMENT_TOKEN}

OLD_PANEL_LINES = 6                                   # live 面板行数（拆行前）
PANEL_LINES = 7                                       # 本轮输出行数（第 3 行拆两行）
OLD_PANEL_LINE_INDEX = 3                              # 0 基；live 面板第 4 行 = 贯穿成长
PANEL_LINE = 4                                        # 0 基；拆行后贯穿成长在第 5 行
OLD_PANEL_LINE = "暗属性共鸣时，自身每保持贯穿效果1.5秒，暗属性角色攻击力＋2.5%、技能伤害＋2.5%、能力伤害＋2.5%"
NEW_PANEL_LINE = "暗属性共鸣时，自身每保持贯穿效果1.5秒，暗属性角色攻击力＋20%、技能伤害＋20%、能力伤害＋20%"

# ------------------------------------------------------------------ 面板拆行（口径 5 扩展，主会话追加 B）

PANEL_SPLIT_LINE = 2                                  # 0 基；live 面板第 3 行
OLD_SPLIT_LINE = "常态冲刺冷却时间延长，冲刺效果强化；暗属性共鸣时，弹射后冲刺冷却时间缩短（3秒）"
#: 按「；」拆成两行，文字逐字不改（前半行无共鸣前置，后半行保留「暗属性共鸣时，」）。
SPLIT_LINES = ("常态冲刺冷却时间延长，冲刺效果强化", "暗属性共鸣时，弹射后冲刺冷却时间缩短（3秒）")
#: 前半行的数据：能力1 的 during 422 DashParameter 行（0 基行号 → c118 param_id：1 速度 / 6 高度上限 /
#: 3 蓄力 / 4 回拉 / 0 冷却倍率常驻 / 0 疾走中冷却补偿）。dash-parameter-v1 只给词条表加了 422，所以住能力1、
#: 用前置 42（仅队长）换回「当队长时」。
DASH_ABILITY = f"{CID}1"
DASH_ABILITY_ROWS = 8
DASH_PARAM_ROWS = {2: "1", 3: "6", 4: "3", 5: "4", 6: "0", 7: "0"}
DASH_CD_ROW = 6                                       # 常驻冷却倍率：正值 = 「冷却时间延长」
#: 后半行的数据：队长 #5 暗编成≥6 + 触发 6 BallFlip → 31 ConditionSwift（疾走）180 帧 = 3 秒。
SWIFT_ROW = 5
SWIFT_FRAMES = 180
ABILITY_PRECONDITION_BASES = (6, 13, 20)              # 词条表前置三块（队长表 4/11/18 + 2）
LEADER_PRECONDITION_BASES = (4, 11, 18)
RESONANCE_PRECONDITION = "2"                          # 编成人数前置（+3 下限 600000 = 6 人，+5 属性组）

# ------------------------------------------------------------------ 输入基线

#: ``{(kind, key): sha256}``：revise() 读取的每一项在 live 1.4.1053 上的摘要（2026-09-27 只读采集）。
#: fixture ``tests/fixtures/balance_20260927c_ginovi.json`` 同源。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", LEADER): "42398495323db8eb42dc59ecb6790bdc5fc810b20b1011c7f106377ef5a66756",
    ("cas", CAS_LEADER): "51f40903ff8c5fe43a73dad466560ec79f177332850fddf9ab0760302af3a2de",
    # 629 行的文案键（只读：InvokeSkill 文案键必须在 custom_ability_string 里，C8601 门）
    ("cas", CAS_INVOKE[0]): "953f3efd3b319b1d727d6a629f13580cb0f0be9c445b76a8b91cf634f01302fc",
    ("cas", CAS_INVOKE[1]): "b4b4369c714838d5bcd1b0f9536cd70a853bbf1d1b5c2fb514b4e1868ba7d25a",
    ("cas", CAS_INVOKE[2]): "a554dad8d22a1334463fdce2fb96455befee249015aa930e5ede1647411ee5ee",
    ("cas", CAS_INVOKE[3]): "4758c77f26df902f3b84eb7f349d9e55a773b7ff685a3b7e6bc7e4d95d09097c",
    # 能力1（只读：面板第 3 行拆行的数据依据；live 1.4.1053 与 1.4.1054 逐字相同）
    ("ability", DASH_ABILITY): "468621929bf6c9ae400e6be2330f5c4d455b4ff60b330e666681f35b06f6bc1e",
    # 技能强化文案（链尾 1.4.1054 只读取数，与候选 ginovi 0.3.1 逐字相同）：强化条目与能力1 面板改写。
    ("cas", "change_skill_ginovi"): "49b362ca2e1dd70a0c7095482104464bcfe0b926754cd09a1ab2e2832791004c",
    ("cas", "desc_override_ginovi_1"): "1ae0dcc129369417bd62df470d51e6867f5c63e8b395b692f3300fddc87763a5",
}

# ------------------------------------------------------------------ 技能强化文案（R1–R4）

SKILL_NAME = "掠影协奏"
CAS_FLAG = f"change_skill_{CODE}"                     # 能力1 #1 kind 536（旗号 1）c70
CAS_A1 = f"desc_override_{CODE}_1"
FLAG_ROW = 1                                          # 能力1 ``1699991`` #1
OLD_FLAG_TEXT = ("为『掠影协奏』追加「攻击力提升效果」 ＆ 直接攻击变为3次 ＆ 暗属性角色的护盾提升并获得最大速度固定效果 "
                 "＆ 对距离最近的敌人强制赋予1层不可消除的「死印」 ＋ 首次发动时缔结血契，夺取全体参战成员的生命值并为全体"
                 "队员赋予护盾")
NEW_FLAG_TEXT = ("为『掠影协奏』追加「攻击力提升效果」「直接攻击分为多次」与「暗属性角色护盾提升＋最大速度固定效果」，"
                 "并对距离最近的敌人强制赋予不可消除的「死印」；首次发动时缔结血契，夺取全体参战成员的生命值并为全体队员赋予护盾")
RESONANCE = "暗属性共鸣时，"
OLD_A1_LINES = (
    "战斗开始时，自身技能槽＋50%",
    "暗属性共鸣时，『掠影协奏』追加「攻击力提升效果 ＆ 直接攻击变为3次 ＆ 暗属性角色的护盾提升+最大速度固定效果」，"
    "并对距离最近的敌人强制赋予1层「死印」（无法消除）；首次发动时缔结血契",
)
A1_FLAG_LINE = 1
NEW_A1_LINES = (OLD_A1_LINES[0], RESONANCE + NEW_FLAG_TEXT)
FLAG_ENTRY_HEADS = (f"强化『{SKILL_NAME}』", f"为『{SKILL_NAME}』追加")
FLAG_ENTRY_BANNED = ("强化自身技能", "强化技能", "属性共鸣时", "担任队长", "强化后", "＆")


class GinoviBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _matches(row: list[str], cells: dict[int, str]) -> bool:
    return (len(row) == LEADER_NCOLS and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


# ------------------------------------------------------------------ 词条 / 文案

def check_leader_shape(rows: list[list[str]]) -> None:
    if len(rows) != LEADER_ROWS or any(len(r) != LEADER_NCOLS for r in rows):
        raise GinoviBalanceError(f"leader {LEADER}: expected {LEADER_ROWS}×{LEADER_NCOLS} rows")
    if (rows[0][45], rows[0][80]) != ("722", f"{CODE}_pf"):
        raise GinoviBalanceError("leader #0 (722 PF override) drifted")
    for index, (trigger, ct, name) in INVOKE_ROWS.items():
        row = rows[index]
        want = {3: "0", 25: trigger, 32: "(None)", 33: ct, 45: "629", 68: name, 69: f"{_ACTION}{name}${name}"}
        if {col: row[col] for col in want} != want:
            raise GinoviBalanceError(f"leader #{index} (629) drifted")


def revise_leader(rows: list[list[str]]) -> list[list[str]]:
    check_leader_shape(rows)
    out = deepcopy(rows)
    for index, kind in PIERCING_ROWS.items():
        if not _matches(out[index], {**PIERCING_GATE, 45: kind, TICK_COLS[0]: OLD_TICK, TICK_COLS[1]: OLD_TICK}):
            raise GinoviBalanceError(f"leader #{index} (235 piercing tick): unexpected preimage")
        for col in TICK_COLS:
            out[index][col] = NEW_TICK
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != sorted(PIERCING_ROWS):
        raise AssertionError("revise_leader touched another record")
    return out


def leader_row_problems(row: list[str], cas_keys) -> list[str]:
    problems = [f"legality: {p}" for p in L.client_legality_problems("leader_ability", row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems("leader_ability", row)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems("leader_ability", row, ELEMENT)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, set(cas_keys), "leader_ability")]
    caps = L.required_client_capabilities("leader_ability", row)
    if caps:
        problems.append(f"unexpected capabilities {caps}")
    return problems


def _resonance(row: list[str], bases: tuple[int, ...]) -> bool:
    """前置三块里有「暗编成≥6」（kind 2、下限 600000、属性组 Black）。"""
    return any(row[base] == RESONANCE_PRECONDITION and row[base + 3] == "600000" and row[base + 5] == ELEMENT_TOKEN
               for base in bases)


def split_basis_problems(ability: list[list[str]], leader: list[list[str]]) -> list[str]:
    """口径 5 拆行的数据依据：前半行（能力1 422 行）只有队长前置、无共鸣；后半行（队长 #5）带暗共鸣、
    弹射触发、疾走 3 秒 ⇒ 两种数据条件（否则该合写而不是拆）。"""
    problems = []
    if len(ability) != DASH_ABILITY_ROWS or any(len(r) != 126 for r in ability):
        return [f"ability {DASH_ABILITY}: expected {DASH_ABILITY_ROWS}×126 rows"]
    if len(leader) <= SWIFT_ROW or len(leader[SWIFT_ROW]) != LEADER_NCOLS:
        return [f"leader {LEADER}: row #{SWIFT_ROW} missing"]
    for index, param in DASH_PARAM_ROWS.items():
        row = ability[index]
        got = (row[5], row[6], row[13], row[20], row[109], row[118])
        if got != ("1", "42", "0", "0", "422", param):
            problems.append(f"ability {DASH_ABILITY}#{index}: (c5,c6,c13,c20,c109,c118) {got} is not "
                            f"a leader-only 422 DashParameter param {param}")
        if _resonance(row, ABILITY_PRECONDITION_BASES):
            problems.append(f"ability {DASH_ABILITY}#{index}: resonance-gated (first split line has no prefix)")
    if not int(ability[DASH_CD_ROW][113] or 0) > 0:
        problems.append(f"ability {DASH_ABILITY}#{DASH_CD_ROW}: cooldown multiplier is not an extension (「延长」)")
    swift = leader[SWIFT_ROW]
    if not _resonance(swift, LEADER_PRECONDITION_BASES):
        problems.append(f"leader #{SWIFT_ROW}: no dark-resonance precondition (second split line keeps the prefix)")
    got = (swift[25], swift[45], swift[55], swift[56])
    want = ("6", "31", str(SWIFT_FRAMES * 100000), str(SWIFT_FRAMES * 100000))
    if got != want:
        problems.append(f"leader #{SWIFT_ROW}: (c25,c45,c55,c56) {got} != BallFlip → ConditionSwift {want}")
    if f"（{SWIFT_FRAMES // 60}秒）" not in SPLIT_LINES[1]:
        problems.append("second split line duration disagrees with the swift frames")
    return problems


def revise_panel(cas: list[list[str]]) -> list[list[str]]:
    if not (len(cas) == 1 and len(cas[0]) == 1 and isinstance(cas[0][0], str)):
        raise GinoviBalanceError(f"{CAS_LEADER}: expected one single-cell row")
    lines = cas[0][0].split("\n")
    if len(lines) != OLD_PANEL_LINES or lines[OLD_PANEL_LINE_INDEX] != OLD_PANEL_LINE:
        raise GinoviBalanceError(f"{CAS_LEADER}: panel line {OLD_PANEL_LINE_INDEX + 1} is not the reviewed text")
    if lines[PANEL_SPLIT_LINE] != OLD_SPLIT_LINE or "；".join(SPLIT_LINES) != OLD_SPLIT_LINE:
        raise GinoviBalanceError(f"{CAS_LEADER}: panel line {PANEL_SPLIT_LINE + 1} is not the reviewed text")
    lines[OLD_PANEL_LINE_INDEX] = NEW_PANEL_LINE
    lines[PANEL_SPLIT_LINE:PANEL_SPLIT_LINE + 1] = list(SPLIT_LINES)
    if len(lines) != PANEL_LINES or lines[PANEL_LINE] != NEW_PANEL_LINE:
        raise AssertionError("revise_panel produced an unexpected layout")
    return [["\n".join(lines)]]


def flag_basis_problems(ability: list[list[str]]) -> list[str]:
    """R2 的数据依据：能力1 #1 = 536 开关行（c70 = 条目串，前置 暗≥6 共鸣 ⇒ 面板行保留「暗属性共鸣时，」），且只此一行引用。"""
    if len(ability) <= FLAG_ROW or len(ability[FLAG_ROW]) != 126:
        return [f"ability {DASH_ABILITY}#{FLAG_ROW}: missing"]
    row, problems = ability[FLAG_ROW], []
    if (row[47], row[70]) != ("536", CAS_FLAG):
        problems.append(f"ability {DASH_ABILITY}#{FLAG_ROW}: (c47,c70) {(row[47], row[70])} is not the 536 row")
    if not _resonance(row, ABILITY_PRECONDITION_BASES):
        problems.append(f"ability {DASH_ABILITY}#{FLAG_ROW}: no dark-resonance precondition")
    if [i for i, r in enumerate(ability) if r[70] == CAS_FLAG] != [FLAG_ROW]:
        problems.append(f"{CAS_FLAG}: referenced by other rows")
    return problems


def flag_entry_problems(text: str) -> list[str]:
    """R2：官方格式、点明技能名、定性无数字（kitlib skill_flag 门）、不写条件。"""
    problems = [f"{CAS_FLAG}: {p}" for p in KL.panel_problems(text, skill_flag=True)]
    if not text.startswith(FLAG_ENTRY_HEADS):
        problems.append(f"{CAS_FLAG}: must start with one of {FLAG_ENTRY_HEADS}")
    problems += [f"{CAS_FLAG}: banned wording {w!r}" for w in FLAG_ENTRY_BANNED if w in text]
    return problems


def revise_flag_texts(flag: list[list[str]], a1: list[list[str]]) -> dict[str, list[list[str]]]:
    """强化条目 + 能力1 面板第 2 行；live 必须是改前文字（不接受自身输出，fail closed）。"""
    if flag != [[OLD_FLAG_TEXT]]:
        raise GinoviBalanceError(f"{CAS_FLAG}: live text differs from the reviewed text")
    if a1 != [["\n".join(OLD_A1_LINES)]]:
        raise GinoviBalanceError(f"{CAS_A1}: live panel differs from the reviewed text")
    return {CAS_FLAG: [[NEW_FLAG_TEXT]], CAS_A1: [["\n".join(NEW_A1_LINES)]]}


def panel_percent(line: str) -> float:
    """面板行里「＋X%」的唯一取值（三处必须相同）。"""
    values = {part.split("%", 1)[0] for part in line.split("＋")[1:]}
    if len(values) != 1:
        raise GinoviBalanceError(f"panel line carries several values: {sorted(values)}")
    return float(values.pop())


# ------------------------------------------------------------------ 主入口

def _baseline(read: Callable[[str, Any], Any]) -> dict:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        if value is None or digest(value) != want:
            raise GinoviBalanceError(f"live drift: {kind}:{key} is not the reviewed baseline")
        inputs[kind, key] = deepcopy(value)
    return inputs


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    # 口径 5 拆行的数据依据（只读核对；不符 ⇒ 拒绝，面板要重审）。
    basis = split_basis_problems(inputs["ability", DASH_ABILITY], inputs["leader", LEADER])
    if basis:
        raise GinoviBalanceError(f"panel split basis drifted: {basis}")
    leader = revise_leader(inputs["leader", LEADER])
    cas = {CAS_LEADER: revise_panel(inputs["cas", CAS_LEADER])}
    if cas[CAS_LEADER][0][0].split("\n")[PANEL_LINE] != NEW_PANEL_LINE or \
            panel_percent(NEW_PANEL_LINE) != int(NEW_TICK) / 1000:
        raise GinoviBalanceError("panel value disagrees with the leader tick strength")

    # 技能强化文案（R1–R4）：先按数据核对 536 开关行，再改条目与能力1 面板第 2 行。
    basis = flag_basis_problems(inputs["ability", DASH_ABILITY])
    if basis:
        raise GinoviBalanceError(f"skill-flag basis drifted: {basis}")
    cas.update(revise_flag_texts(inputs["cas", CAS_FLAG], inputs["cas", CAS_A1]))

    cas_keys = {CAS_LEADER, *CAS_INVOKE}
    problems = [f"leader #{i}: {p}" for i, row in enumerate(leader) for p in leader_row_problems(row, cas_keys)]
    problems += [f"{CAS_LEADER}: {p}" for p in KL.panel_problems(cas[CAS_LEADER][0][0])]
    problems += [f"{CAS_A1}: {p}" for line in cas[CAS_A1][0][0].split("\n") for p in KL.panel_problems(line)]
    problems += flag_entry_problems(cas[CAS_FLAG][0][0])
    if cas[CAS_A1][0][0].split("\n")[A1_FLAG_LINE] != RESONANCE + cas[CAS_FLAG][0][0]:
        problems.append(f"{CAS_A1}: line {A1_FLAG_LINE + 1} is not the {CAS_FLAG} entry")
    if any("／" in rows[0][0] for rows in cas.values()):
        problems.append("panel uses 「／」")
    if problems:
        raise GinoviBalanceError("; ".join(problems))

    return {
        "ability": {},
        "leader": {LEADER: leader},
        "cas": cas,
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "character": f"{CID} {CODE} 基诺维「破契的黑翼」（暗）",
            "source": "mod-tools/wf_balance_20260927c_ginovi.py",
            "spec": "growth_c_spec.md（作者：2/3 为下限；数值尽量取 5 的倍数；D1 原值 25% 的 2/3 行取 20%；D3）；"
                    "reeval_full.json table.rows 169999",
            "live_tail": "1.4.1053（第二批 1.4.1051 已发布，本角色 live == wf_balance_20260927b_ginovi 输出）",
            "growth": {
                "rows": {f"leader #{i}": kind for i, kind in PIERCING_ROWS.items()},
                "trigger": f"235 ConditionKeepFramePiercing，每保持贯穿 {TICK_FRAMES} 帧一跳，c32=(None)",
                "c49/c50": [OLD_TICK, NEW_TICK],
                "per_tick": ["原 25%", "第二批 2.5%", "本轮 20%"],
                "rounding": "25×2/3=16.7；取 15 实际 0.6 低于 2/3 下限，不低于下限的 5 的倍数只有 20%（D1，备选 17.5% 不用）",
                "three_minute_total": f"约 {THREE_MIN_TICKS} 跳：暗队攻/技伤/能伤 各 原 +2100% / 第二批 +210% / 本轮 +1680%",
            },
            "panel": {"key": CAS_LEADER, "line": PANEL_LINE + 1, "before_line": OLD_PANEL_LINE_INDEX + 1,
                      "before": OLD_PANEL_LINE, "after": NEW_PANEL_LINE},
            "panel_split": {
                "rule": "口径 5 扩展（主会话第三轮追加 B）：一行挤两种数据条件的按数据条件拆行，文字逐字不改",
                "key": CAS_LEADER,
                f"line {PANEL_SPLIT_LINE + 1} → lines {PANEL_SPLIT_LINE + 1}+{PANEL_SPLIT_LINE + 2}":
                    [OLD_SPLIT_LINE, list(SPLIT_LINES)],
                "basis": {
                    SPLIT_LINES[0]: f"ability:{DASH_ABILITY}#2–#7 during 422 DashParameter（前置 42 仅队长，无共鸣；"
                                    "#2–#6 常驻 param 1/6/3/4/0，#7 疾走中冷却补偿 param 0）",
                    SPLIT_LINES[1]: f"leader_ability:{LEADER}#{SWIFT_ROW} 暗编成≥6 + 触发 6 BallFlip → 31 ConditionSwift "
                                    f"{SWIFT_FRAMES} 帧",
                },
            },
            "skill_enhancement_text": {
                "request": "作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,"
                           "规范并简化描述做了吗」；主会话口径 R1–R4",
                "basis": f"ability:{DASH_ABILITY}#{FLAG_ROW} kind 536（旗号 1，前置 暗≥6 共鸣）c70 = {CAS_FLAG}；旗号 1 开支：额外 "
                         "ACAttackPoint、ACAdditionalDirectAttack(3)、额外护盾与 ACFixedSpeed、最近敌人 ACUnique 1699901「死印」、"
                         "首次（DCUnique 169998 计数）血契",
                "changes": {f"cas:{CAS_FLAG}": [OLD_FLAG_TEXT, NEW_FLAG_TEXT],
                            f"cas:{CAS_A1} 第{A1_FLAG_LINE + 1}行": [OLD_A1_LINES[A1_FLAG_LINE], NEW_A1_LINES[A1_FLAG_LINE]]},
                "rule": "条目官方格式「为『掠影协奏』追加「…」」、定性不写数字（「直接攻击变为3次」→「直接攻击分为多次」、"
                        "「1层」删去）；面板行 =「暗属性共鸣时，」+ 同一条目",
                "skill_description": "action_skill 两档 c1 / character_text c5/c7 本来就只写技能本体，不改",
                "observed_not_changed": f"能力1 #1（536）c1=false（仅主位）但 {CAS_A1} 各行无主位图标；R4 只改强化文字，未补",
            },
            "kept": ["其余 8 行队长行逐字不动（722 / 629×4 / 疾走 / 开局技能槽 / 死印乘区）",
                     "第二批削韧（技能/629/PF 本体 p13）不动", "不新增共鸣前置（D3）",
                     f"能力1 {DASH_ABILITY} 只读（拆行依据），不返回"],
            "generator": {
                "file": "work/character_packs/ginovi/build_workspace.py",
                "constants": {"PIERCING_BUFF": NEW_TICK},
                "panel": "DESC_OVERRIDE_LINES['desc_override_ginovi'][2]/[3]（原第 3 行拆两行）与 [4]（贯穿成长）；"
                         "DESC_OVERRIDE_LINES['desc_override_ginovi_1'][1] 与 CHANGE_SKILL_TEXT（技能强化文案）",
                "not_run": "只改源码常量；build/kit-v3 会写包（影子表与候选），本模块不运行",
            },
            "runtime_verified": False,
        },
    }

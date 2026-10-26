# -*- coding: utf-8 -*-
"""2026-09-27 平衡第三轮（c，成长复核）：芙拉菲「圆月下的捣糕之约」149987 ``combat_animal_moon``（风）。

口径 = 主会话 ``growth_c_spec.md``（作者原话：成长「砍到4/5，或者7/10」「可以砍到2/3」「数值尽量取5的倍数」；
默认选择 D2/D3），数值表 = ``reeval_full.json`` table.rows 的 149987 三行。本角色不在技能倍率撤封顶名单里。
第二批（``wf_balance_20260927b_fluffy``，1.4.1051 已发布）把三条无上限成长砍到 1/10、1/5、1/5；
作者认为砍过头，本轮按「原值 × 档位系数、取 5 的倍数（<10% 取整数）」回调：

1. **队长 L#4/L#5**（风共鸣：每 1 次强化弹射 → 风队攻击力 / 技能伤害，不限次）：c49/c50 2000 → 15000。
   原 20%，全队这两项只能靠成长 ⇒ 4/5 = 16%，就近取 5 的倍数 15%（实际 3/4，按 7/10 也落 15%）。
2. **队长 L#9**（风共鸣：每 250 连击 → 自身技能伤害，不限次）：20000 → 70000。原 100%，中频、自身基础充足 ⇒ 7/10。
3. **队长 L#12**（风共鸣：每 3 次强化弹射 → 风队技能伤害独立乘区 694，不限次）：1000 → 4000。
   原 5%，次数少且只能靠成长 ⇒ 4/5 = 4%（<10% 不取 5 的倍数，D2）。
4. **面板** ``desc_override_combat_animal_moon`` 第 3/4/6 行同步数字（其余逐字）。

不动：同触发的 L#10（35 充能速度 5%）/ L#11（245 技能槽上限 5%）属充能；L#7/L#8「每 5 次 Lv3 PF」CT；其余队长行、
全部能力行与 DSL（第二批的削韧 p13 保持）。不新增共鸣前置（D3）。

技能强化只写在能力的强化条目（作者原话「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要
重复描述强化后的效果,规范并简化描述做了吗」；主会话口径 R1–R4）：

5. **能力3 面板** ``desc_override_combat_animal_moon_3`` 第 5 行（0 基 #4）= 能力 ``1499873`` #4 kind 704（旗号 2，
   前置 风≥6 共鸣）的强化条目：「风属性共鸣时，强化『玉杵捣月·桂风连打』的连击效果，技能命中每次连击＋55」→
   「风属性共鸣时，」+ 条目 ``change_skill_2_combat_animal_moon`` 原文（「…，技能命中时追加连击」，条目本身已合规，
   只读不改）——强化条目定性、不写数字（R2）；数据前置带风共鸣 ⇒ 保留「风属性共鸣时，」。其余 5 行逐字。
   技能说明（action_skill 两档 c1、character_text c5/c7）本来就只写技能本体，不改（R3）；数据行与 DSL 一格不动（R4）。

生成器 ``wf_midautumn_kit_fluffy``：新增 ``BALANCE_C``，LEADER / CAS_TEXTS 改用本轮值（``BALANCE_B`` 留作第二批历史），
能力3 面板第 5 行同步，
测试断言生成器输出 == :func:`revise` 输出；设计镜像（design/fluffy.json、rework1/panel/fluffy.json）由
:func:`sync_mirrors` 幂等同步。本模块只读 ``read()``；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as L
import wf_midautumn_kitlib as KL

CID = "149987"
CODE = "combat_animal_moon"
PACKAGES = ["ma-fluffy"]
#: 候选 ma-fluffy manifest 现值 1.0.1（第二批已回写）⇒ 下一号。
PACKAGE_VERSION = {"ma-fluffy": "1.0.2"}
#: 候选已声明 panel-description-override-v2 / dash-parameter-v1 / gauge-gain-rules-v1；只改数值，不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 ma-fluffy 与 live 在本模块读取的 3 个键上逐字相同（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ELEMENT_TOKEN = "Green"
LEADER_NCOLS = 124
LEADER_ROWS = 13

LEADER_KEY = CID
CAS_LEADER = f"desc_override_{CODE}"
#: 队长 L#8 629 行的文案键（只读：invoke_skill_string_problems 要求它在 custom_ability_string 里）。
INVOKE_KEY = f"ability_skill_{CODE}"
INVOKE_PROGRAM = f"battle/action/skill/action/ability_skill/{INVOKE_KEY}${INVOKE_KEY}"

# ---------------------------------------------------------------- 数值

#: 队长行号 → (第二批 live 值, 本轮值)（c49/c50 同值；千 = 1%）。
LEADER_CHANGES = {4: ("2000", "15000"), 5: ("2000", "15000"), 9: ("20000", "70000"), 12: ("1000", "4000")}
#: 第二批之前的原值与本轮系数（notes / 测试核算用）。
ORIGINAL = {4: "20000", 5: "20000", 9: "100000", 12: "5000"}
FACTOR = {4: "4/5", 5: "4/5", 9: "7/10", 12: "4/5"}
#: 3 分钟触发次数的取值（表 reeval_full：35 次 / 20 次 / 12 次）。
THREE_MIN_EVENTS = {4: 35, 5: 35, 9: 20, 12: 12}

# ---------------------------------------------------------------- 行指纹（第二批 live 形状）

_LEADER_COMMON = {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
                  11: "0", 18: "0", 37: "(None)", 44: "0"}
_PF1 = {25: "2", 28: "100000", 29: "100000", 32: "(None)", 33: "0"}
_PF3 = {25: "2", 28: "300000", 29: "300000", 32: "(None)", 33: "0"}


def _cells(extra: dict[int, str], value: str) -> dict[int, str]:
    return {**_LEADER_COMMON, **extra, 49: value, 50: value}


#: 改前逐格指纹（全部非空列；其余列必须为空）。
LEADER_BEFORE = {
    4: _cells({**_PF1, 45: "32", 46: "5", 47: ELEMENT_TOKEN}, LEADER_CHANGES[4][0]),
    5: _cells({**_PF1, 45: "34", 46: "5", 47: ELEMENT_TOKEN}, LEADER_CHANGES[5][0]),
    9: _cells({25: "12", 28: "25000000", 29: "25000000", 32: "(None)", 33: "0", 45: "34", 46: "0"},
              LEADER_CHANGES[9][0]),
    12: _cells({**_PF3, 45: "694", 46: "5", 47: ELEMENT_TOKEN}, LEADER_CHANGES[12][0]),
    # 不动但要锁住的同触发充能行（35/245，5%）
    10: _cells({**_PF3, 45: "35", 46: "5", 47: ELEMENT_TOKEN}, "5000"),
    11: _cells({**_PF3, 45: "245", 46: "5", 47: ELEMENT_TOKEN}, "5000"),
}
#: 只核对的 629 行（L#8）：触发/CT/被调程序。
INVOKE_ROW, INVOKE_ROW_CELLS = 8, {25: "65", 33: "360", 45: "629", 68: INVOKE_KEY, 69: INVOKE_PROGRAM}

# ---------------------------------------------------------------- 面板

#: 0 基行号 → (第二批 live 文本, 本轮文本)。
PANEL_CHANGES = {
    2: ("风属性共鸣时，每发动3次强化弹射，风属性角色技能充能速度＋5%、技能槽最大值＋5%、技能伤害额外乘区＋1%",
        "风属性共鸣时，每发动3次强化弹射，风属性角色技能充能速度＋5%、技能槽最大值＋5%、技能伤害额外乘区＋4%"),
    3: ("风属性共鸣时，每发动1次强化弹射，风属性角色攻击力＋2%、技能伤害＋2%、连击＋5",
        "风属性共鸣时，每发动1次强化弹射，风属性角色攻击力＋15%、技能伤害＋15%、连击＋5"),
    5: ("风属性共鸣时，每达到250连击，自身技能伤害＋20%",
        "风属性共鸣时，每达到250连击，自身技能伤害＋70%"),
}
PANEL_LINES = 7
PANEL_LV3_LINE = (4, "风属性共鸣时，每发动5次强化弹射Lv3时，连击＋500，并触发自身技能效果（不消耗技能槽，冷却时间：6秒）")

# ---------------------------------------------------------------- 技能强化文案（R1–R4）

A3_KEY = f"{CID}3"                                      # 1499873
CAS_A3 = f"desc_override_{CODE}_3"
CAS_FLAG2 = f"change_skill_2_{CODE}"                    # 能力3 #4 kind 704（旗号 2）c70
FLAG2_ROW = 4
SKILL_NAME = "玉杵捣月·桂风连打"
FLAG2_TEXT = f"强化『{SKILL_NAME}』的连击效果，技能命中时追加连击"      # live 条目原文（已合规，只读）
MAIN_ICON = " <icon id='main'>  "
RESONANCE = "风属性共鸣时，"
A3_LINES = 6
A3_FLAG_LINE = 4                                        # 0 基：第 5 行 = 704 开关行
OLD_A3_FLAG_LINE = MAIN_ICON + RESONANCE + f"强化『{SKILL_NAME}』的连击效果，技能命中每次连击＋55"
NEW_A3_FLAG_LINE = MAIN_ICON + RESONANCE + FLAG2_TEXT

#: live 输入基线（2026-09-27 本地链尾 1.4.1053 只读取数；候选 ma-fluffy 1.0.1 逐字相同）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", LEADER_KEY): "cf7b5bb569e26249fdde0d372fd5b967de056d1a1afc03b5613829a1691cd13d",
    ("cas", CAS_LEADER): "41513263e6fc054e51ed82cd191ae35ea166c9458ee69d6d6fc6df3e2b92d74e",
    ("cas", INVOKE_KEY): "51280ed1cf079e917e3287f255b51e0c5f148a77f0ad4750a8341c1af4500a8d",
    # 技能强化文案（链尾 1.4.1054 只读取数，与候选 ma-fluffy 1.0.1 逐字相同）：能力3 面板改写；条目串与能力3 行只读。
    ("cas", CAS_A3): "a8043e9bd17b158f40eca7180f9369fe6570c1ad785f130c1c93f06fd7331025",
    ("cas", CAS_FLAG2): "541b3c7ea3219eab58cd96080e78069b4aa8c0bf4114e14d21b9c7b914c95a7f",
    ("ability", A3_KEY): "cadcc2fb1fddc400d9bb02e97d0499924b0fcd9376cb9f9d69a02549701da2be",
}


class FluffyBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise FluffyBalanceError(f"unreviewed live baseline for {kind}:{key} ({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], cells: dict[int, str]) -> bool:
    return (len(row) == LEADER_NCOLS and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


# ---------------------------------------------------------------- 词条 / 面板

def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 L#4/#5/#9/#12 c49/c50 回调；L#10/#11 与 L#8 锁住不动；其余行逐字保留。"""
    if len(rows) != LEADER_ROWS or any(len(r) != LEADER_NCOLS for r in rows):
        raise FluffyBalanceError(f"leader {LEADER_KEY}: expected {LEADER_ROWS}×{LEADER_NCOLS} rows")
    for index, cells in LEADER_BEFORE.items():
        if not _matches(rows[index], cells):
            raise FluffyBalanceError(f"leader {LEADER_KEY}#{index}: row drifted from the reviewed shape")
    invoke = rows[INVOKE_ROW]
    if {col: invoke[col] for col in INVOKE_ROW_CELLS} != INVOKE_ROW_CELLS:
        raise FluffyBalanceError(f"leader {LEADER_KEY}#{INVOKE_ROW}: 629 invoke row drifted")
    out = deepcopy(rows)
    for index, (_old, new) in LEADER_CHANGES.items():
        out[index][49] = out[index][50] = new
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != sorted(LEADER_CHANGES):
        raise AssertionError("leader_rows touched another record")
    return out


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise FluffyBalanceError(f"{CAS_LEADER}: expected one single-column row")
    lines = rows[0][0].split("\n")
    if len(lines) != PANEL_LINES or lines[PANEL_LV3_LINE[0]] != PANEL_LV3_LINE[1]:
        raise FluffyBalanceError(f"{CAS_LEADER}: unexpected panel text layout")
    for index, (old, new) in PANEL_CHANGES.items():
        if lines[index] != old:
            raise FluffyBalanceError(f"{CAS_LEADER}: line {index + 1} drifted: {lines[index]!r}")
        lines[index] = new
    return [["\n".join(lines)]]


def flag_basis_problems(a3: list[list[str]], flag_text: list[list[str]]) -> list[str]:
    """R2 的数据依据：能力3 #4 = 704 开关行（c70 = 条目串、前置 风≥6 共鸣、主位槽 c1=false），条目串 == 已合规原文。"""
    problems = []
    row = a3[FLAG2_ROW] if len(a3) > FLAG2_ROW else []
    if len(row) != 126:
        return [f"ability {A3_KEY}#{FLAG2_ROW}: missing"]
    if (row[47], row[70], row[1]) != ("704", CAS_FLAG2, "false"):
        problems.append(f"ability {A3_KEY}#{FLAG2_ROW}: (c47,c70,c1) {(row[47], row[70], row[1])} is not the 704 row")
    if not any(row[b] == "2" and (row[b + 3], row[b + 5]) == ("600000", ELEMENT_TOKEN) for b in (6, 13, 20)):
        problems.append(f"ability {A3_KEY}#{FLAG2_ROW}: no wind-resonance precondition (panel keeps the prefix)")
    if [i for i, r in enumerate(a3) if r[70] == CAS_FLAG2] != [FLAG2_ROW]:
        problems.append(f"{CAS_FLAG2}: referenced by other rows")
    if flag_text != [[FLAG2_TEXT]]:
        problems.append(f"{CAS_FLAG2}: live entry is not the reviewed text")
    problems += [f"{CAS_FLAG2}: {p}" for p in KL.panel_problems(FLAG2_TEXT, skill_flag=True)]
    return problems


def ability3_text(rows: list[list[str]]) -> list[list[str]]:
    """能力3 面板第 5 行 → 「风属性共鸣时，」+ 强化条目（R2）；其余 5 行逐字；不接受自身输出（fail closed）。"""
    if len(rows) != 1 or len(rows[0]) != 1:
        raise FluffyBalanceError(f"{CAS_A3}: expected one single-column row")
    lines = rows[0][0].split("\n")
    if len(lines) != A3_LINES or lines[A3_FLAG_LINE] != OLD_A3_FLAG_LINE:
        raise FluffyBalanceError(f"{CAS_A3}: unexpected panel text layout")
    if not all(line.startswith(MAIN_ICON) for line in lines):
        raise FluffyBalanceError(f"{CAS_A3}: main-only panel lost its icon")
    lines[A3_FLAG_LINE] = NEW_A3_FLAG_LINE
    return [["\n".join(lines)]]


def panel_problems(text: str) -> list[str]:
    problems = ["uses 「／」 instead of line breaks"] if "／" in text else []
    for line in text.split("\n"):
        problems += KL.panel_problems(line)
    return problems


def row_problems(row: list[str], cas_keys) -> list[str]:
    return (L.client_legality_problems("leader_ability", row)
            + L.declared_block_field_problems("leader_ability", row)
            + L.invoke_skill_string_problems(row, set(cas_keys), "leader_ability"))


def _pct(value: str) -> str:
    number = int(value) / 1000
    return f"{number:g}%"


# ---------------------------------------------------------------- 入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader = _checked(read, "leader", LEADER_KEY)
    cas = _checked(read, "cas", CAS_LEADER)
    _checked(read, "cas", INVOKE_KEY)                       # 只读：629 文案键在场
    cas_a3 = _checked(read, "cas", CAS_A3)
    flag2 = _checked(read, "cas", CAS_FLAG2)                # 只读：强化条目原文（已合规）
    a3 = _checked(read, "ability", A3_KEY)                  # 只读：704 开关行

    new_leader = leader_rows(leader)
    # 技能强化文案（R1–R4）：先按数据核对 704 开关行与条目，再改能力3 面板第 5 行。
    found = flag_basis_problems(a3, flag2)
    if found:
        raise FluffyBalanceError(f"skill-flag basis drifted: {found}")
    new_cas = {CAS_LEADER: leader_text(cas), CAS_A3: ability3_text(cas_a3)}
    cas_keys = {CAS_LEADER, INVOKE_KEY}
    problems = [f"leader#{i}: {p}" for i, row in enumerate(new_leader) for p in row_problems(row, cas_keys)]
    for key, rows in new_cas.items():
        problems += [f"{key}: {p}" for p in panel_problems(rows[0][0].replace(MAIN_ICON, ""))]
    if new_cas[CAS_A3][0][0].split("\n")[A3_FLAG_LINE] != MAIN_ICON + RESONANCE + flag2[0][0]:
        problems.append(f"{CAS_A3}: line {A3_FLAG_LINE + 1} is not the {CAS_FLAG2} entry")
    if problems:
        raise FluffyBalanceError("; ".join(problems))

    return {
        "ability": {},
        "leader": {LEADER_KEY: new_leader},
        "cas": new_cas,
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_fluffy.py",
            "character": f"{CID} {CODE} 芙拉菲「圆月下的捣糕之约」（风，中秋）",
            "spec": "growth_c_spec.md（作者：4/5 或 7/10，2/3 为下限；数值尽量取 5 的倍数，<10% 不强取；D2/D3）；"
                    "reeval_full.json table.rows 149987",
            "live_tail": "1.4.1053（第二批 1.4.1051 已发布，本角色 live == wf_balance_20260927b_fluffy 输出）",
            "changes": {
                f"leader:{LEADER_KEY}#{i} c49/c50":
                    f"{old} → {new}（原 {_pct(ORIGINAL[i])} / 第二批 {_pct(old)} / 本轮 {_pct(new)}，{FACTOR[i]}）"
                for i, (old, new) in LEADER_CHANGES.items()},
            "rounding": {
                "L#4/L#5": "20%×4/5=16% → 就近取 5 的倍数 15%（实际 0.75；按 7/10=14% 也落 15%）",
                "L#9": "100%×7/10=70%（已是 5 的倍数）",
                "L#12": "5%×4/5=4%（原值太小，<10% 不取 5 的倍数，D2）",
            },
            "growth_3min": {
                "team_atk_skill": "每次 PF 约 35 次：风队攻击力/技能伤害各 原 +700% / 第二批 +70% / 本轮 +525%",
                "self_skill_combo250": "每 250 连击约 20 次：自身技能伤害 原 +2000% / 第二批 +400% / 本轮 +1400%",
                "team_skill_ic694": "每 3 次 PF 约 12 次：风队技能伤害独立乘区 原 +60% / 第二批 +12% / 本轮 +48%",
            },
            "panel": {CAS_LEADER: {f"line {i + 1}": [old, new] for i, (old, new) in PANEL_CHANGES.items()},
                      CAS_A3: {f"line {A3_FLAG_LINE + 1}": [OLD_A3_FLAG_LINE, NEW_A3_FLAG_LINE]}},
            "skill_enhancement_text": {
                "request": "作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,"
                           "规范并简化描述做了吗」；主会话口径 R1–R4",
                "basis": f"ability:{A3_KEY}#{FLAG2_ROW} kind 704（旗号 2，前置 风≥6 共鸣，主位槽）c70 = {CAS_FLAG2}",
                "change": f"{CAS_A3} 第{A3_FLAG_LINE + 1}行：强化条目不写数字（原「技能命中每次连击＋55」）⇒ "
                          f"「风属性共鸣时，」+ {CAS_FLAG2} 原文；条目串本身已合规，只读不改",
                "skill_description": "action_skill 两档 c1 / character_text c5/c7 本来就只写技能本体，不改",
                "kept": "其余 5 行逐字；数据行与 DSL 一格不动（R4）",
            },
            "kept": ["队长 L#10（35 充能速度 5%）/ L#11（245 技能槽上限 5%）：充能类，不动",
                     "队长 L#7/L#8「每 5 次 Lv3 PF → 连击＋500 ＋ 触发技能」CT 360 帧：不动",
                     "不给成长行新增共鸣前置（D3）；全部能力行、DSL（第二批削韧）不动"],
            "generator": "wf_midautumn_kit_fluffy.py（BALANCE_C / LEADER / CAS_TEXTS 已同步；BALANCE_B 留作第二批历史）",
            "capabilities": list(CAPABILITIES),
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/fluffy.json"
PANEL_REL = BATCH / "rework1/panel/fluffy.json"
MIRROR_TAG = "balance_20260927c"
MIRROR_ROWS = tuple(sorted(LEADER_CHANGES))
LINE_NOTE = "2026-09-27 平衡第三轮：成长按作者「4/5 或 7/10、取 5 的倍数」回调"
MIRROR_NOTE = ("2026-09-27 平衡第三轮（成长复核）：队长「每发动1次强化弹射」攻击力/技能伤害 2% → 15%（原 20%）、"
               "「每达到250连击」自身技能伤害 20% → 70%（原 100%）、「每发动3次强化弹射」技能伤害额外乘区 1% → 4%"
               "（原 5%）；充能速度与技能槽最大值、削韧不动。技能强化文案（作者「技能都强化效果只在队长技或者能力里面"
               "按照格式写」）：能力3 第5行改为「风属性共鸣时，」+ 强化条目原文，不写数字。")
FLAG_LINE_NOTE = ("2026-09-27 平衡第三轮技能强化文案：强化条目不写数字（原「技能命中每次连击＋55」），"
                  "写成「风属性共鸣时，」+ change_skill_2_combat_animal_moon 原文")


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等）。"""
    import wf_midautumn_kit_fluffy as K
    design, panel = deepcopy(design), deepcopy(panel)

    rows = design["rework1"]["leader_ability"]["rows"]
    if [r["index"] for r in rows] != list(range(len(K.LEADER))):
        raise ValueError("design mirror leader rows are out of step with the generator")
    for index in MIRROR_ROWS:
        donor, _source, cells, expect = K.LEADER[index]
        entry = rows[index]
        if entry["donor"] != f"official leader_ability[{donor}]":
            raise ValueError(f"design mirror L#{index} donor drifted: {entry['donor']}")
        entry["cells"] = {str(col): value for col, value in cells.items()}
        entry["desc_expected"] = expect
    design["rework1"][MIRROR_TAG] = dict(
        spec="growth_c_spec.md（作者：4/5 或 7/10，2/3 为下限，数值尽量取 5 的倍数）＋ reeval_full 149987",
        changed=[f"队长 L#{i} c49/c50 {old} → {new}（原 {ORIGINAL[i]}，{FACTOR[i]}）"
                 for i, (old, new) in LEADER_CHANGES.items()],
        kept=["队长 L#10/L#11（35/245 充能类）", "每 5 次 Lv3 PF 触发技能 CT 6 秒",
              "第二批削韧（技能八连重击 1.5、629 树 0.15）", "队长 13 行、能力 18 条"],
        panel={K.LEADER_OVERRIDE: K.CAS_TEXTS[K.LEADER_OVERRIDE], CAS_A3: K.CAS_TEXTS[CAS_A3]},
        skill_enhancement_text=f"{CAS_A3} 第{A3_FLAG_LINE + 1}行 = 「风属性共鸣时，」+ {CAS_FLAG2}（强化条目不写数字）",
        module="mod-tools/wf_balance_20260927c_fluffy.py",
    )

    want = K.CAS_TEXTS[K.LEADER_OVERRIDE].split("\n")
    lines = panel["leader"]["lines"]
    if len(lines) != len(want):
        raise ValueError("leader panel mirror line count drifted")
    for index, text in enumerate(want):
        if lines[index]["text"] != text:
            if index not in PANEL_CHANGES or lines[index]["text"] != PANEL_CHANGES[index][0]:
                raise ValueError(f"leader panel mirror line {index} drifted: {lines[index]['text']!r}")
            lines[index] = dict(lines[index], text=text, status="changed", note=LINE_NOTE)
    if [line["text"] for line in lines] != want:
        raise ValueError("leader panel mirror still differs from the generator")

    if K.SLOT_OVERRIDE[3] != CAS_A3 or K.CAS_TEXTS[CAS_A3].split("\n")[A3_FLAG_LINE] != NEW_A3_FLAG_LINE:
        raise ValueError("generator ability 3 panel is not the batch-3 text")
    three = [entry for entry in panel["abilities"] if int(entry["index"]) == 3]
    if len(three) != 1 or len(three[0]["lines"]) != A3_LINES:
        raise ValueError("panel mirror ability 3 layout drifted")
    entry = three[0]["lines"][A3_FLAG_LINE]
    old_text, new_text = OLD_A3_FLAG_LINE[len(MAIN_ICON):], NEW_A3_FLAG_LINE[len(MAIN_ICON):]   # 镜像行不带主位图标
    if entry["text"] == old_text:
        three[0]["lines"][A3_FLAG_LINE] = dict(entry, text=new_text, status="changed", note=FLAG_LINE_NOTE)
    elif entry["text"] != new_text:
        raise ValueError(f"panel mirror ability 3 line {A3_FLAG_LINE + 1} drifted: {entry['text']!r}")
    if [MAIN_ICON + line["text"] for line in three[0]["lines"]] != K.CAS_TEXTS[CAS_A3].split("\n"):
        raise ValueError("ability 3 panel mirror still differs from the generator")
    notes = [note for note in panel.get("notes", []) if not note.startswith("2026-09-27 平衡第三轮")]
    panel["notes"] = notes + [MIRROR_NOTE]
    return design, panel


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """保留原文件的缩进、换行风格与末尾有无换行。"""
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    second = raw.split(b"\n", 2)[1]
    indent = len(second) - len(second.lstrip(b" "))
    text = json.dumps(value, ensure_ascii=False, indent=indent or 2)
    if raw.endswith(b"\n"):
        text += "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def sync_mirrors(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回两份设计镜像；返回有变化的相对路径。"""
    root = Path(root)
    rels = (DESIGN_REL, PANEL_REL)
    paths = tuple(root / rel for rel in rels)
    before = [_load(path) for path in paths]
    after = mirror_updates(*before)
    changed = [str(rel) for rel, old, new in zip(rels, before, after) if old != new]
    if write:
        for path, old, new in zip(paths, before, after):
            if old != new:
                _save(path, new)
    return changed


if __name__ == "__main__":
    import sys
    here = Path(__file__).resolve().parent
    pass  # Imports resolve from this checkout/package, not external source copies.
    changed = sync_mirrors(here.parent, write="--write" in sys.argv[1:])
    print(json.dumps({"changed": changed, "write": "--write" in sys.argv[1:]}, ensure_ascii=False))

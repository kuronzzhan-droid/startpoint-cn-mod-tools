# -*- coding: utf-8 -*-
"""2026-09-27 平衡第三轮（c，成长复核）：澄波响 169988 ``psychic_teleport_moon``（暗 · 特殊型 PF 主 C）。

口径 = 主会话 ``growth_c_spec.md``（作者原话：成长「砍到4/5，或者7/10」「可以砍到2/3」「数值尽量取5的倍数」；
默认选择 D1/D3/D4），数值表 = ``reeval_full.json`` table.rows 的 169988 两行。本角色不在技能倍率撤封顶名单里。
第二批（``wf_balance_20260927b_hibiki``，1.4.1051 已发布）把两条无上限成长砍到 1/10；本轮回调：

1. **队长 L#6**（全等级 PF 累计命中每 4 次 → 自身攻击力，不限次）：c49/c50 5000 → 35000。
   触发很频繁（3 分钟约 50 次）、基础极其充足 ⇒ 下限 2/3：50%×2/3=33.3 → 向上取 5 的倍数 35%。
2. **队长 L#10/L#11**（每层「回响」→ 自身强化弹射伤害 / 攻击力，during 134，限 99 ＝ 固有上限）：
   c111/c112 2500 → 20000。原 25%，2/3 = 16.7 → 5 的倍数且不低于 2/3 的只有 20%（D1：取 20%，不用 17.5%）。
3. **面板** ``desc_override_psychic_teleport_moon`` 第 7/8 行同步数字；另按主会话统一口径改第 4 行标点（见 6）、
   第 5 行拆成两行（见 7），9 行 → 10 行，其余逐字。
4. **面板同条件合并**（作者「同一个条件的提升能不能写到一起来简化描述」；主会话合并规则）：只合并同一面板里
   数据条件完全相同的行（前置/触发/CT/c1/次数上限/后缀列逐格相同，只有效果列不同），每个效果原措辞与数值保留、
   只省略重复对象名，合并行放在组首行位置：
   - 能力 2 ``_2``：#0/#1（持有贯穿时 PF≥1、限 25 次 → 自身攻击力 8% / 强化弹射伤害 12%）两行并一行；
   - 能力 4 ``_4``：#0/#1（持续·持有贯穿 → 自身攻击力 200% / 强化弹射伤害 150%）两行并一行，回响那行不动。
   队长块四个同条件组（#2/#3、#6/#9、#8/#10、#11/#12）在面板上本来就各是一行；能力 5 的冲刺参数组没有独立面板行
   （文案在队长块第 2/3 行）；其余面板没有同条件组。
5. **共鸣省略**（作者「引擎点火的获取带火属性共鸣，引擎点火提供的效果就不用写火属性共鸣」）：本角色唯一固有状态
   「回响」16998801 的获取来源里有不带共鸣的（队长 #4「每 3 次强化弹射 +2 层」前置块 c4=0，另有技能 DSL 授予）
   ⇒ 不成立；而且回响提供的效果行本来就没写共鸣前缀。本轮不删任何「暗属性共鸣时，」。
6. **强化弹射伤害不补对象**（主会话统一口径 1：kind 55 / during 23 是战场级，原文没写对象的不加「自身」，与前一个
   带对象的效果用「，」隔开）：返回的三块面板里「、强化弹射伤害」一律改「，强化弹射伤害」——队长第 4 行
   （``暗属性角色攻击力＋300%，强化弹射伤害＋200%``）、能力 2 合并行、能力 4 合并行。数据侧只读核对这三处的
   强化弹射伤害行确是 kind 55 / during 23（:func:`pf_damage_problems`）。
7. **一行两种条件拆行**（主会话统一口径 5）：队长第 5 行原文用「；」把两种数据条件写在一行——#3「暗共鸣常驻 →
   贯穿延长 30%」与 #5/#8「暗共鸣 且 暗属性角色发动技能 → 立即获得强化弹射」——拆成两行，两行各自带
   「暗属性共鸣时，」（三行数据都带暗编成≥6 前置，共鸣是真实条件）；数值与措辞不变。数据侧只读核对两组条件确实
   不同、各自都带暗共鸣（:func:`split_basis_problems`）。
8. 共鸣写法（主会话统一口径 3）：返回的面板里没有「X属性共鸣时：」，无需规范化（:func:`panel_problems` 拒绝冒号写法）。

不动（D4）：能力 3 #1 / 能力 4 #2 的封顶版（10%/5% × 10 层）保持第二批值；能力 3 #0 与队长 #4 只产回响层数；
629 追击树削韧（第二批 0.25）；其余队长行与能力行。不给 L#6/L#10/L#11 新增共鸣前置（D3）。

生成器 ``wf_midautumn_kit_hibiki``：``ECHO_LEADER_STEP`` / ``HIT_ATTACK_STEP`` / LEADER 描述 / ``PANEL_LEADER`` /
``PANEL_ABILITY[2]`` / ``PANEL_ABILITY[4]`` 已同步，
测试断言生成器输出 == :func:`revise` 输出；设计镜像（design/hibiki.json、rework1/panel/hibiki.json）由
:func:`sync_mirrors` 幂等同步。本模块只读 ``read()``；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as legality

CID = "169988"
CODE = "psychic_teleport_moon"
PACKAGES = ["ma-hibiki"]
#: 候选 ``work/character_packs/ma-hibiki/package/manifest.json`` 现值 1.0.1（第二批已回写）⇒ 下一号。
PACKAGE_VERSION = {"ma-hibiki": "1.0.2"}
#: 候选已声明 dash-parameter-v1 / panel-description-override-v2 / damage-type-rules-v1；只改数值，不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 ma-hibiki 与 live 在本模块读取的 4 个键上逐字相同（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

LEADER_KEY = CID
CAS_LEADER = f"desc_override_{CODE}"
#: 队长两行 629 的条目串（只读：invoke_skill_string_problems 需要它们在 custom_ability_string 里）。
CAS_INVOKE = (f"ability_skill_{CODE}_pf_skill", f"ability_skill_{CODE}_pf_dash")
INVOKE_PROGRAM = (f"battle/action/skill/action/ability_skill/ability_skill_{CODE}_pf"
                  f"$ability_skill_{CODE}_pf")
UID = "16998801"                   # 固有「回响」
UNIQUE_CAP = "99"
LEADER_NCOLS = 124
LEADER_ROWS = 12

# ---------------------------------------------------------------- 数值（千 = 1%）

HIT_ROW = 6                        # 0 基：累计命中每 4 次 → 自身攻击力（c49/c50）
HIT_OLD, HIT_NEW = "5000", "35000"
HIT_ORIGINAL = "50000"
ECHO_ROWS = {10: "23", 11: "0"}    # 0 基 → during kind（c107）：强化弹射伤害 / 攻击力（c111/c112）
ECHO_OLD, ECHO_NEW = "2500", "20000"
ECHO_ORIGINAL = "25000"

# ---------------------------------------------------------------- 行指纹（第二批 live 形状）

BEFORE_HIT_CELLS: dict[int, str] = {
    0: CODE, 1: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "15", 28: "400000", 29: "400000",
    32: "(None)", 33: "0", 37: "(None)", 44: "0", 45: "32", 46: "0", 49: HIT_OLD, 50: HIT_OLD,
}
_ECHO_L = {0: CODE, 1: "0", 3: "1", 4: "0", 11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0",
           98: "100000", 99: "100000", 100: UNIQUE_CAP, 102: UID, 106: "false", 108: "0",
           111: ECHO_OLD, 112: ECHO_OLD}
BEFORE_ECHO_CELLS = {index: {**_ECHO_L, 107: kind} for index, kind in ECHO_ROWS.items()}
#: 队长两行 629（只核对触发 → CT；两者都 ≤3 秒，第二批削韧的前提，不改）。
INVOKE_ROWS = {5: ("23", "0"), 7: ("4", "90")}

# ---------------------------------------------------------------- 面板

OLD_LEADER_LINES = (
    "赋予自身特殊强化弹射",
    "强化自身冲刺",
    "自身冲刺间隔无法进一步缩短",
    "持有贯穿效果时，暗属性角色攻击力＋300%、强化弹射伤害＋200%",
    "暗属性共鸣时，贯穿效果持续时间＋30%；暗属性角色发动技能时，自身立即获得强化弹射效果",
    "每发动3次强化弹射（含额外触发），自身“回响”＋2层",
    "强化弹射每累计命中4次，自身攻击力＋5%",
    "每1层“回响”，自身强化弹射伤害＋2.5%、攻击力＋2.5%",
    "冲刺时，立即获得强化弹射效果（冷却时间：1.5秒）",
)
PANEL_HIT_LINE, PANEL_ECHO_LINE = 6, 7      # 0 基
NEW_LEADER_HIT = "强化弹射每累计命中4次，自身攻击力＋35%"
NEW_LEADER_ECHO = "每1层“回响”，自身强化弹射伤害＋20%、攻击力＋20%"
#: 数值同步后（9 行，合并 / 拆行 / 标点规范化之前）。
NUMBER_LEADER_LINES = (OLD_LEADER_LINES[:PANEL_HIT_LINE] + (NEW_LEADER_HIT, NEW_LEADER_ECHO)
                       + OLD_LEADER_LINES[PANEL_ECHO_LINE + 1:])

#: 口径 1：强化弹射伤害（战场级）原文不带对象，不再用「、」接在带对象的效果后面（读作同一对象），改用「，」隔开。
PF_DAMAGE_JOIN_OLD, PF_DAMAGE_JOIN_NEW = "、强化弹射伤害", "，强化弹射伤害"
PANEL_PIERCE_LINE = 3                        # 0 基：队长第 4 行（持有贯穿 → 暗队攻击 + 强化弹射伤害）
NEW_LEADER_PIERCE = "持有贯穿效果时，暗属性角色攻击力＋300%，强化弹射伤害＋200%"
#: 口径 5：队长第 5 行「；」前后是两种数据条件 ⇒ 拆两行，各自带共鸣前缀（数据三行都带暗编成≥6）。
PANEL_SPLIT_LINE = 4                         # 0 基
SPLIT_LEADER_LINES = (
    "暗属性共鸣时，贯穿效果持续时间＋30%",
    "暗属性共鸣时，暗属性角色发动技能时，自身立即获得强化弹射效果",
)
NEW_LEADER_LINES = (NUMBER_LEADER_LINES[:PANEL_PIERCE_LINE] + (NEW_LEADER_PIERCE,) + SPLIT_LEADER_LINES
                    + NUMBER_LEADER_LINES[PANEL_SPLIT_LINE + 1:])
#: 拆行的数据依据（队长行号 0 基）：#3 常驻贯穿延长（前置块 2 = 暗编成≥6）；#5/#8 暗编成≥6 且暗属性角色发动技能
#: （触发 23，c26/c27 = 5/Black）→ 629 PF 追击 / 立即获得强化弹射（248）。
SPLIT_ROWS = ((3,), (5, 8))
#: 口径 1 的数据依据：各面板里「强化弹射伤害」对应的数据行 → (表, 键, 行号, 内容列, 期望 kind)。
PF_DAMAGE_ROWS = (("leader", CID, 2, 107, "23"),
                  ("ability", f"{CID}2", 1, 47, "55"),
                  ("ability", f"{CID}4", 1, 109, "23"))

# ---------------------------------------------------------------- 面板同条件合并 / 共鸣省略

ABILITY2, ABILITY4 = f"{CID}2", f"{CID}4"
CAS_SLOT2, CAS_SLOT4 = f"desc_override_{CODE}_2", f"desc_override_{CODE}_4"
ABILITY_NCOLS = 126

OLD_SLOT2_LINES = (
    "持有贯穿效果时，每发动1次强化弹射，自身攻击力＋8%（最多25次）",
    "持有贯穿效果时，每发动1次强化弹射，强化弹射伤害＋12%（最多25次）",
)
NEW_SLOT2_LINES = (
    "持有贯穿效果时，每发动1次强化弹射，自身攻击力＋8%，强化弹射伤害＋12%（最多25次）",
)
OLD_SLOT4_LINES = (
    "持有贯穿效果期间，自身攻击力＋200%",
    "持有贯穿效果期间，强化弹射伤害＋150%",
    "每1层“回响”，自身攻击力＋5%（最多10层）",
)
NEW_SLOT4_LINES = (
    "持有贯穿效果期间，自身攻击力＋200%，强化弹射伤害＋150%",
    "每1层“回响”，自身攻击力＋5%（最多10层）",
)
#: 合并组：面板键 → (词条键, 同条件数据行（0 基）, 被合并的面板行（0 基）, 改前行, 改后行)。
PANEL_MERGES: dict[str, tuple[str, tuple[int, ...], tuple[int, ...], tuple[str, ...], tuple[str, ...]]] = {
    CAS_SLOT2: (ABILITY2, (0, 1), (0, 1), OLD_SLOT2_LINES, NEW_SLOT2_LINES),
    CAS_SLOT4: (ABILITY4, (0, 1), (0, 1), OLD_SLOT4_LINES, NEW_SLOT4_LINES),
}
#: 同条件的判据：组内各行除「效果列」外逐格相同（前置三块、触发与参数、CT、次数上限、c1 主位、觉醒列、效果后缀列）。
#: 效果列 = instant 内容块 kind/对象/对象元素/强度（能力 c47–c52）与 during 内容块同位（能力 c109–c114）。
EFFECT_COLUMNS = {"ability": frozenset(range(47, 53)) | frozenset(range(109, 115)),
                  "leader_ability": frozenset(range(45, 51)) | frozenset(range(107, 113))}
#: 共鸣省略：无（见模块说明 5）。键 = 面板键，值 = 可删「X属性共鸣时，」的面板行号（1 起）。
PREFIX_DROPS: dict[str, tuple[int, ...]] = {}
ECHO_GRANT_KIND = "461"            # 队长 c45 内容 = 固有状态付与；c66 = 固有 id
RESONANCE_PRECONDITION = "2"       # 前置块 kind 2 = 编成（共鸣）


def merge_condition_problems(table: str, rows: list[list[str]], indexes: tuple[int, ...]) -> list[str]:
    """合并组内各行除效果列外必须逐格相同；返回不同的列（空 = 数据条件完全相同）。"""
    effect = EFFECT_COLUMNS[table]
    if any(i >= len(rows) for i in indexes):
        return [f"merge group {indexes} out of range ({len(rows)} rows)"]
    first = rows[indexes[0]]
    problems = []
    for index in indexes[1:]:
        row = rows[index]
        diff = [col for col in range(max(len(first), len(row)))
                if col not in effect and (first[col] if col < len(first) else None)
                != (row[col] if col < len(row) else None)]
        if diff:
            problems.append(f"rows #{indexes[0]}/#{index} differ outside the effect columns: {diff}")
    return problems


#: 队长表的「条件列」：觉醒 c1/c2、触发种类 c3、前置三块 c4–c24、瞬发触发与参数 c25–c36、触发前置 c37–c43、延迟 c44。
LEADER_CONDITION_COLUMNS = tuple(range(1, 45))
SPLIT_CONTENT = {3: "190", 5: "629", 8: "248"}   # 贯通延长 / 629 PF 追击 / 立即获得强化弹射


def _dark_resonance(row: list[str]) -> bool:
    """队长前置三块里有「暗编成≥6」（kind 2、下限 600000、属性组 Black）。"""
    return any(row[base] == RESONANCE_PRECONDITION and row[base + 3] == "600000" and row[base + 5] == "Black"
               for base in (4, 11, 18))


def split_basis_problems(leader: list[list[str]]) -> list[str]:
    """口径 5 拆行的数据依据：两组行各自条件列逐格相同、各自带暗共鸣，而两组条件不同（否则该合并而不是拆）。"""
    problems = []
    if any(i >= len(leader) for group in SPLIT_ROWS for i in group):
        return [f"split rows {SPLIT_ROWS} out of range ({len(leader)} rows)"]
    signatures = []
    for group in SPLIT_ROWS:
        cells = [tuple(leader[i][c] for c in LEADER_CONDITION_COLUMNS) for i in group]
        if len(set(cells)) != 1:
            problems.append(f"leader rows {group} are not one data condition")
        signatures.append(cells[0])
        for i in group:
            if not _dark_resonance(leader[i]):
                problems.append(f"leader #{i}: no dark-resonance precondition (split line keeps 「暗属性共鸣时，」)")
            if leader[i][45] != SPLIT_CONTENT[i]:
                problems.append(f"leader #{i}: content kind {leader[i][45]!r} != {SPLIT_CONTENT[i]!r}")
    if len(set(signatures)) != len(signatures):
        problems.append("split groups share one data condition: merge instead of splitting")
    return problems


def pf_damage_problems(inputs: dict) -> list[str]:
    """口径 1 的数据依据：面板里改成「，强化弹射伤害」的三处，数据确是强化弹射伤害（kind 55 / during 23）。"""
    problems = []
    for kind, key, index, col, want in PF_DAMAGE_ROWS:
        rows = inputs.get((kind, key)) or []
        got = rows[index][col] if index < len(rows) and col < len(rows[index]) else None
        if got != want:
            problems.append(f"{kind}:{key}#{index} c{col} = {got!r}, want PF damage kind {want!r}")
    return problems


def echo_grant_sources(leader: list[list[str]]) -> list[tuple[int, bool]]:
    """队长表里授予「回响」的行：[(行号, 是否带共鸣前置)]。有一条不带共鸣 ⇒ 共鸣省略不成立。"""
    out = []
    for index, row in enumerate(leader):
        if row[3] == "0" and row[45] == ECHO_GRANT_KIND and row[66] == UID:
            out.append((index, any(row[base] == RESONANCE_PRECONDITION for base in (4, 11, 18))))
    return out


def merged_panel(key: str, text: str) -> str:
    """同条件合并：改前行逐字核对，合并行放在组首行位置，其余行逐字保留。"""
    _ability, _rows, _lines, old, new = PANEL_MERGES[key]
    _require(tuple(text.split("\n")) == old, f"{key}: unexpected panel text layout")
    return "\n".join(new)


def slot2_panel(text: str) -> str:
    return merged_panel(CAS_SLOT2, text)


def slot4_panel(text: str) -> str:
    return merged_panel(CAS_SLOT4, text)


#: 口径面板禁语（与 wf_midautumn_kitlib.FORBIDDEN_PANEL_WORDS 同口径，另加分隔符）。
FORBIDDEN_PANEL_PHRASES = ("自身为队长时", "觉醒后", "生命值100%以下", "无上限", "无限叠加",
                           "不设上限", "可无限", "／", "(None)", "null")
MAIN_ICON = " <icon id='main'>  "

# ---------------------------------------------------------------- 输入基线

#: live 输入基线（2026-09-27 本地链尾 1.4.1053 只读取数，与候选 ma-hibiki 1.0.1 逐字相同）。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", LEADER_KEY): "5669079f1f0bde90c7cc97d12ac076b01b42cd56763de68e95f1c1a0501771de",
    ("cas", CAS_LEADER): "18c92f99c66ac62138f661e50677c850e036083534bcf499f7cb1ab0a0068ad8",
    ("cas", CAS_INVOKE[0]): "b73d4db3eb38bbb783996a87f5820e9a65f7c889c1d893fed57bfcc7b27c8959",
    ("cas", CAS_INVOKE[1]): "506cd903110e1f69ae4cad7f0858f2a4c9f8815f410bec8748c64a6262c5a20a",
    # 面板同条件合并（2026-09-27 链尾 1.4.1054 只读取数，与候选 ma-hibiki 1.0.1 逐字相同）：
    # 能力 2 / 能力 4 的行只读（核对合并组数据条件），面板覆盖串改写。
    ("ability", ABILITY2): "bc579fbb4bc2768c8bc03c067ffe834912184f923ef125eb6483a7e47007ed57",
    ("ability", ABILITY4): "cb4019616313be6ced224feffb5e8280d7ad418a10973ea09bc470ce050dcccd",
    ("cas", CAS_SLOT2): "dcb4493b49b90c98f47f0e5aa0ff3aef88689c07d4c2eaddcf1e530cfb556753",
    ("cas", CAS_SLOT4): "bd5e1f5ded82604c634b0677a71e28904529a8cefe837f29c2f0673ede52ecf7",
}


class HibikiBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HibikiBalanceError(message)


def _checked(read: Callable[[str, Any], Any], kind: str, key: Any) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise HibikiBalanceError(f"unreviewed live baseline for {kind}:{key} ({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], cells: dict[int, str]) -> bool:
    return (len(row) == LEADER_NCOLS
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


# ---------------------------------------------------------------- 行 / 面板

def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 #6 c49/c50 5000 → 35000；#10/#11 c111/c112 2500 → 20000；其余行逐字保留。"""
    _require(len(rows) == LEADER_ROWS and all(len(r) == LEADER_NCOLS for r in rows),
             f"leader {LEADER_KEY} shape drift ({len(rows)} rows)")
    _require([i for i, row in enumerate(rows) if _matches(row, BEFORE_HIT_CELLS)] == [HIT_ROW],
             f"leader PF-hit growth row not found at #{HIT_ROW}")
    for index, cells in BEFORE_ECHO_CELLS.items():
        _require(_matches(rows[index], cells), f"leader #{index}: echo growth row drifted")
    for index, (trigger, ct) in INVOKE_ROWS.items():
        row = rows[index]
        _require((row[3], row[25], row[33], row[45], row[69]) == ("0", trigger, ct, "629", INVOKE_PROGRAM),
                 f"leader #{index}: 629 invoke row drift")
    out = deepcopy(rows)
    out[HIT_ROW][49] = out[HIT_ROW][50] = HIT_NEW
    for index in ECHO_ROWS:
        out[index][111] = out[index][112] = ECHO_NEW
    _require([i for i, (a, b) in enumerate(zip(rows, out)) if a != b] == [HIT_ROW, *ECHO_ROWS],
             "leader_rows touched another record")
    return out


def leader_panel(text: str) -> str:
    _require(tuple(text.split("\n")) == OLD_LEADER_LINES, f"{CAS_LEADER}: unexpected panel text layout")
    return "\n".join(NEW_LEADER_LINES)


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    _require(len(rows) == 1 and len(rows[0]) == 1, f"{CAS_LEADER}: expected one single-column row")
    return [[leader_panel(rows[0][0])]]


def slot_text(key: str, rows: list[list[str]]) -> list[list[str]]:
    _require(len(rows) == 1 and len(rows[0]) == 1, f"{key}: expected one single-column row")
    return [[merged_panel(key, rows[0][0])]]


def panel_problems(key: str, text: str) -> list[str]:
    """队长块与槽 2/槽 4 都不限主位（c1 = true / 队长）⇒ 任一行都不许带 Ⓜ。"""
    problems = [f"{key}: forbidden phrase {word!r}" for word in FORBIDDEN_PANEL_PHRASES if word in text]
    problems += [f"{key}: unrestricted panel carries the main-position icon: {line!r}"
                 for line in text.split("\n") if line.startswith(MAIN_ICON)]
    if "属性共鸣时：" in text or "属性共鸣时:" in text:
        problems.append(f"{key}: resonance must be written as 「X属性共鸣时，」")
    if PF_DAMAGE_JOIN_OLD in text:
        problems.append(f"{key}: 强化弹射伤害 is battlefield-level; separate it with 「，」, not 「、」")
    return problems


def row_problems(row: list[str], cas_keys) -> list[str]:
    return (legality.client_legality_problems("leader_ability", row)
            + legality.declared_block_field_problems("leader_ability", row)
            + legality.invoke_skill_string_problems(row, set(cas_keys), "leader_ability"))


# ---------------------------------------------------------------- revise

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {key: _checked(read, *key) for key in BEFORE}
    leader = {LEADER_KEY: leader_rows(inputs["leader", LEADER_KEY])}
    # 口径 5 拆行 / 口径 1 标点的数据依据（只读核对；不符 ⇒ 拒绝，面板要重审）。
    basis = split_basis_problems(inputs["leader", LEADER_KEY]) + pf_damage_problems(inputs)
    _require(not basis, f"panel rewrite basis drifted: {basis}")
    cas = {CAS_LEADER: leader_text(inputs["cas", CAS_LEADER])}

    # 面板同条件合并：先按数据核对组内条件逐格相同，再改写面板。
    for key, (ability_key, rows, _lines, _old, _new) in PANEL_MERGES.items():
        found = merge_condition_problems("ability", inputs["ability", ability_key], rows)
        _require(not found, f"{key}: merge group is not one data condition: {found}")
        cas[key] = slot_text(key, inputs["cas", key])
    # 共鸣省略：回响的获取来源里有不带共鸣的队长行 ⇒ 不删任何共鸣前缀（数据变了必须重审）。
    _require(any(not resonant for _index, resonant in echo_grant_sources(leader[LEADER_KEY])) and not PREFIX_DROPS,
             "echo acquisition is now resonance-only: re-review the resonance-prefix omission")

    cas_keys = {CAS_LEADER, *CAS_INVOKE}
    problems = [f"leader {LEADER_KEY}#{i}: {p}" for i, row in enumerate(leader[LEADER_KEY])
                for p in row_problems(row, cas_keys)]
    for key, rows in cas.items():
        problems += panel_problems(key, rows[0][0])
    if problems:
        raise HibikiBalanceError("; ".join(problems))

    return {
        "ability": {}, "leader": leader, "cas": cas,
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": notes(),
    }


def notes() -> dict[str, Any]:
    return {
        "source": "wf_balance_20260927c_hibiki.py",
        "character": f"{CID} {CODE} 澄波响（暗，中秋）",
        "spec": "growth_c_spec.md（作者：2/3 为下限；数值尽量取 5 的倍数；D1 原值 25% 的 2/3 行取 20%；D3/D4）；"
                "reeval_full.json table.rows 169988",
        "live_tail": "1.4.1053（第二批 1.4.1051 已发布，本角色 live == wf_balance_20260927b_hibiki 输出）；"
                     "面板合并的 4 个输入键于 1.4.1054 补读（本角色 1.4.1053 → 1.4.1054 未变）",
        "changes": {
            f"leader_ability:{LEADER_KEY}#{HIT_ROW} c49/c50":
                f"{HIT_OLD} → {HIT_NEW}（原 50% / 第二批 5% / 本轮 35%：50×2/3=33.3 向上取 35）",
            **{f"leader_ability:{LEADER_KEY}#{i} c111/c112":
               f"{ECHO_OLD} → {ECHO_NEW}（原 25% / 第二批 2.5% / 本轮 20%：25×2/3=16.7，不低于 2/3 的 5 的倍数只有 20%，D1）"
               for i in ECHO_ROWS},
        },
        "growth_3min": {
            "hit_quads": "累计命中每 4 次约 50 次（30–75）：自身攻击力 原 +2500% / 第二批 +250% / 本轮 +1750%（1050–2625%）",
            "echo_layers": "回响约 2–2.5 分钟满 99 层：每条 原 +2475% / 第二批 +247.5% / 本轮 +1980%（另加能力封顶版 "
                           "PF 伤害 +100%、攻击力 +50%）",
            "stacking_note": "前 10 层与能力栏封顶版叠加：PF 伤害每层 20%+10%=30%（高于原 25%）、攻击力 20%+5%=25%（等于原值）"
                             "——表 summary 已列入「需要作者知情」，本轮按 D4 不动能力栏",
        },
        "panel": {CAS_LEADER: {"line 7": [OLD_LEADER_LINES[PANEL_HIT_LINE], NEW_LEADER_HIT],
                               "line 8": [OLD_LEADER_LINES[PANEL_ECHO_LINE], NEW_LEADER_ECHO],
                               "line 4（口径 1）": [OLD_LEADER_LINES[PANEL_PIERCE_LINE], NEW_LEADER_PIERCE],
                               "line 5 → lines 5+6（口径 5）": [OLD_LEADER_LINES[PANEL_SPLIT_LINE],
                                                              list(SPLIT_LEADER_LINES)],
                               "layout": "9 行 → 10 行（拆行），其余行逐字",
                               "split_rows": "#3（暗编成≥6 常驻 → 贯通延长 30%）｜#5/#8（暗编成≥6 且暗属性角色发动技能 → "
                                             "629 PF 追击 / 立即获得强化弹射）；两组各自带暗共鸣，条件不同"},
                  **{key: {"merged": {f"lines {'+'.join(str(i + 1) for i in lines)}":
                                      [[old[i] for i in lines], new[lines[0]]]},
                           "data_rows": f"ability:{ability_key}#{'/#'.join(map(str, rows))}（除效果列外逐格相同）"}
                     for key, (ability_key, rows, lines, old, new) in PANEL_MERGES.items()}},
        "panel_merge": {
            "rule": "同一面板里数据条件完全相同的行合并（前置/触发/CT/c1/次数上限/后缀列逐格相同）；"
                    "效果原措辞与数值保留、只省略重复对象名；合并行放在组首行位置",
            "merged": {CAS_SLOT2: "能力2 两行 → 一行", CAS_SLOT4: "能力4 前两行 → 一行（回响行不动）"},
            "not_merged": {
                CAS_LEADER: "同条件组 #2/#3、#6/#9、#8/#10、#11/#12 在面板上本来就各是一行；第5行「；」前后是两种条件"
                            "⇒ 按口径 5 拆成两行（各带「暗属性共鸣时，」）",
                f"desc_override_{CODE}_5": "冲刺参数组 #1–#4 没有独立面板行（文案在队长块第2/3行）",
                "其余": "能力1/能力3/能力6 没有同条件组",
            },
            "resonance_prefix_drops": {
                "result": "无",
                "basis": f"「回响」{UID} 获取来源：队长 #4（每3次强化弹射 +2 层，前置块 c4=0 无共鸣）、"
                         f"能力3 #0（暗共鸣）、技能两档 DSL（无共鸣节点）⇒ 不是全部带暗共鸣；且回响效果行本来就没写共鸣前缀",
            },
            "pf_damage_object": "口径 1：强化弹射伤害（kind 55 / during 23，战场级）原文不带对象，不补「自身」；与前一个带对象的"
                                "效果之间「、」改「，」——队长第4行、能力2 合并行、能力4 合并行",
            "resonance_punctuation": "口径 3：返回面板里没有「X属性共鸣时：」，无需规范化",
        },
        "kept": [f"能力 {CID}3#1 / {CID}4#2 封顶版（10%/5% × 10 层，D4）",
                 "能力 3#0 与队长 #4 只产回响层数", "629 追击树削韧（第二批 0.25/段）",
                 "L#6/L#10/L#11 仍无共鸣前置（D3：不新增）"],
        "generator": "wf_midautumn_kit_hibiki.py（ECHO_LEADER_STEP / HIT_ATTACK_STEP / LEADER / PANEL_LEADER / "
                     "PANEL_ABILITY[2] / PANEL_ABILITY[4] 已同步）",
        "capabilities": [],
        "runtime_verified": False,
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/hibiki.json"
PANEL_REL = BATCH / "rework1/panel/hibiki.json"

MIRROR_TAG = "balance_20260927c"
MIRROR_NOTE = ("2026-09-27：第三轮平衡（成长复核）——队长累计命中每4次自身攻击力＋5%→＋35%（原＋50%，2/3 取整）；"
               "回响每层自身强化弹射伤害/攻击力＋2.5%→＋20%（原＋25%，2/3 向上取 5 的倍数）；能力3/能力4 封顶版不动。"
               "面板同条件合并：能力2 两行、能力4 前两行各并成一行（数据条件逐格相同，原措辞与数值不变）；"
               "「回响」有不带共鸣的获取来源，不省略共鸣前缀。强化弹射伤害（战场级）不补对象，与前一效果用「，」隔开；"
               "队长第5行「；」前后是两种数据条件，拆成两行（各带暗属性共鸣）。")


def _lines(entries: list[dict], texts) -> list[dict]:
    """按文本重排镜像行：原文不变的行保留原记录，新增/改动的行标 ``changed``。"""
    old = {entry["text"]: entry for entry in entries}
    return [old[text] if text in old else {"text": text, "status": "changed"} for text in texts]


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等）。"""
    import wf_midautumn_kit_hibiki as K
    design, panel = deepcopy(design), deepcopy(panel)

    plan = design["plan_rework1"]
    plan["leader_rows"] = K.LEADER_ROWS
    plan["leader_records"] = [
        {"index": index, "donor": addr, "source": source,
         "cells": {str(col): value for col, value in sorted(cells.items())}, "describe": expect}
        for index, (addr, source, cells, expect) in enumerate(K.LEADER)]
    design["rework1"][MIRROR_TAG] = dict(
        spec="growth_c_spec.md（作者：4/5 或 7/10，2/3 为下限，数值尽量取 5 的倍数；D1/D3/D4）＋ reeval_full 169988",
        changed=[f"队长#{HIT_ROW} 累计命中每4次自身攻击力 {HIT_OLD}→{HIT_NEW}（原 {HIT_ORIGINAL}，2/3 向上取 5 的倍数）",
                 f"队长#10/#11 回响每层自身PF伤害/攻击力 {ECHO_OLD}→{ECHO_NEW}（原 {ECHO_ORIGINAL}，2/3 → 20%，D1）"],
        kept=["能力3#1/能力4#2 封顶版 10%/5%×10 层（D4）", "629 追击树削韧", "不新增共鸣前置（D3）"],
        panel={CAS_LEADER: list(NEW_LEADER_LINES), CAS_SLOT2: list(NEW_SLOT2_LINES),
               CAS_SLOT4: list(NEW_SLOT4_LINES)},
        panel_merge=[f"{key}：面板行 {'+'.join(str(i + 1) for i in lines)} 合并（{ability_key}#"
                     f"{'/#'.join(map(str, rows))} 数据条件逐格相同）"
                     for key, (ability_key, rows, lines, _old, _new) in PANEL_MERGES.items()],
        resonance_prefix_drops="无：「回响」获取来源含队长#4（无共鸣）与技能 DSL",
        panel_rules=["口径1：「、强化弹射伤害」→「，强化弹射伤害」（队长第4行、能力2、能力4）",
                     "口径5：队长第5行按数据条件拆两行（#3 常驻｜#5/#8 发动技能），各带「暗属性共鸣时，」"],
        module="mod-tools/wf_balance_20260927c_hibiki.py",
    )
    problems = K.design_problems(design)
    if problems:
        raise HibikiBalanceError(f"design mirror still drifts: {problems}")

    panel["leader"]["lines"] = _lines(panel["leader"]["lines"], K.PANEL_LEADER.split("\n"))
    for block in panel["abilities"]:
        block["lines"] = _lines(block["lines"], K.PANEL_ABILITY[int(block["index"])].split("\n"))
    notes_ = [note for note in panel.get("notes", []) if not note.startswith("2026-09-27：第三轮平衡")]
    panel["notes"] = notes_ + [MIRROR_NOTE]
    return design, panel


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """保留原文件的缩进、换行风格与末尾换行。"""
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

# -*- coding: utf-8 -*-
"""黑 139991 ``outlaw_panther_moon``：2026-09-27 作者平衡**第二批**（无上限成长）。

口径 = ``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md`` A 节（作者已拍板）；设计稿
``growth/growth_design.json`` 139991 按 live 1.4.1049 重读重推。黑的技能轮盘与直击 +3 不动（口径 C / B5），
能力5 击杀回槽的 CT、轮盘「队长技能槽」数值属表二充能规范（本批暂缓），也不动。

频率（口径 A2，3 分钟实际次数）：
  * 技能命中（trigger 107）：550 能量 3 分钟约 7–9 发，单体每发约 15 hit ⇒ 105–135 次 ⇒ ≥30 取 1/10；
  * 进入 Fever（trigger 8）：约每 135 直击回满、技能 +50 Fever 点、Fever 中每 20 直击 −50% ⇒ 8–12 次 ⇒ ≤15 取 1/5。

改动（其余行逐字保留）：
  1. ``ability:1399912#0``（雷共鸣：技能每命中 1 次 → 队长攻击力 +50%，不限次）原位换成有上限的弱化版：
     c34 (None) → 25、c51/c52 50000 → 2000（+2% × 25 次 = 50%；官方 trigger 107 先例 1610054#0 +1% × 50）。
  2. 其无上限部分：trigger 107 在官方与 live 自制队长表都是 **0 行**（口径 A4：零先例进队长表 = 角色页崩溃，
     已实锤三次）⇒ 不进队长表，改为能力2 末尾新增 ``1399912#3``：前置1 = 42（持有者为队长），前置2 = 雷共鸣
     （kind 2 ≥6 Yellow），target 0 自身，c51/c52 5000（每 hit +5%，1/10），c34 保持 (None)。
     行形照 live 凯尔 ``1399903#4/#5``（前置1 42 + 前置2 雷共鸣，在线）；官方前置1 = 42 共 4 行、前置2 = kind 2
     先例 1210756#1。文案写进队长面板（desc_override_outlaw_panther_moon）。
  3. ``ability:1399913#1``（Ⓜ：每次进入 Fever → 雷队直击 +150%，不限次）原位换成有上限的弱化版：
     c34 (None) → 3、c51/c52 150000 → 40000（+40% × 3 = 120%，官方能力 trigger 8 限 3 族）。
  4. 其无上限部分进队长：``leader_ability:139991#4`` = ['outlaw_panther_moon','0',''] + 1399913#1[5:]，
     c49/c50 30000（每次 +30%，1/5）。先例（逐列）：队长 trigger 8 官方 24 行（kind 32/0/34/211/206/461 等），
     队长瞬发 kind 33 target 5 官方 14 行（其中带触发的 trigger 23 两行、trigger 20 一行）；**trigger 8 与 kind 33
     的组合在官方队长表、官方能力表都是 0 行**，只有 live 能力行 1399913#1（在线）。donor 131164#1 是
     trigger 8 → kind 32 target 5 Yellow（同触发、同目标，kind 不同，不是同形）。队长表按列逐项解析，两列取值
     各有先例 ⇒ C7050/F1009 风险低，但上线前须真机打开黑的角色页与队长页确认（runtime_verified=False）。
     队长现有 #0 是持续 Fever → 直击 400%，触发不同，不合并。
  5. 面板（desc_override 整块接管）：队长追加两行；能力2 第 1 行、能力3 第 2 行改数字并写出上限。
     上限按黑现有写法「，最多N层/次」（骰运行），共鸣前缀按口径 D 写「雷属性共鸣时，」（本批新写/改写的行）。
     按作者裁决「无上限就写到效果为止」，不写「（可无限累积）」。
     队长面板第 5 行的数据在能力2（前置 42 承载行）：能力2 未解锁时该行不生效但面板仍显示（与凯尔先例相同）。

生成器 ``wf_midautumn_kit_kuro``（LEADER / ABILITY / PANEL_*）已同步，测试断言生成器装配 == :func:`revise` 输出；
设计镜像（design/kuro.json、rework1/panel/kuro.json）由 :func:`sync_mirrors` 幂等同步。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as L

CID = "139991"
CODE = "outlaw_panther_moon"
PACKAGES = ["ma-kuro"]
#: 候选 manifest 现值 1.0.1（${WF_ROOT}/pkgarchive/ma-kuro-* 四份全是 1.0.0）⇒ 下一号。
PACKAGE_VERSION = {"ma-kuro": "1.0.2"}
#: 候选已声明 kyubi-fever-ratio-v1 / panel-description-override-v2；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 ma-kuro 的 manifest 条目与文件逐一一致（2026-09-27 RevisionCandidate 只读打开无漂移），
#: 本模块读取的 6 项与 live 逐项相同。
REVIEWED_DRIFT: dict = {}

ELEMENT = 2                          # master/character c3：雷（0 基内部元素）
ELEMENT_TOKEN = "Yellow"
MAIN_ICON = " <icon id='main'>  "
LEADER_KEY = CID
ABILITY2_KEY = f"{CID}2"
ABILITY3_KEY = f"{CID}3"
CAS_LEADER = f"desc_override_{CODE}"
CAS_ABILITY2 = f"desc_override_{CODE}_2"
CAS_ABILITY3 = f"desc_override_{CODE}_3"
LEADER_NCOLS, ABILITY_NCOLS = 124, 126

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数，与候选 ma-kuro 1.0.1 逐字相同）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", LEADER_KEY): "d0e5e5b58a0161997b6d94bf29c3961d22651725d57e41135afe40d630141f09",
    ("ability", ABILITY2_KEY): "04eb5f16240635d602f7942c248754579b6be8076e6703db472613587433855e",
    ("ability", ABILITY3_KEY): "5b8321e68697914284fd8b33fef8439c48f692c2b37716371d43ac45b9a5c7ec",
    ("cas", CAS_LEADER): "657f3d87c74a79fbf3b02ba7d0c75a06d030c8d66206c3eae8e9d979b705ca94",
    ("cas", CAS_ABILITY2): "2282fc8a32c04ad2c9b9a0dfd3f658d0f0d0a8d2cc7ed045fb3da076b157cca5",
    ("cas", CAS_ABILITY3): "55e50400202f28d4959842dd14acc15282a5d1c5cc67430e5ccb1260f0f70147",
}

# ------------------------------------------------------------------ 词条行

#: 改前 ``1399912#0``：雷共鸣 → trigger 107（自身技能命中，puller 0）→ kind 32 target 2（队长）50%，不限次。
HIT_ROW_BEFORE = {
    0: f"{CODE}_2", 1: "true", 2: "attack_common", 3: "0", 5: "0", 6: "2", 9: "600000", 10: "600000",
    11: ELEMENT_TOKEN, 13: "0", 20: "0", 27: "107", 28: "0", 30: "100000", 31: "100000",
    34: "(None)", 35: "0", 39: "(None)", 46: "0", 47: "32", 48: "2", 51: "50000", 52: "50000",
}
HIT_ROW_AFTER = {**HIT_ROW_BEFORE, 34: "25", 51: "2000", 52: "2000"}
#: 新增 ``1399912#3``：前置1 42（持有者为队长）＋ 前置2 雷共鸣，target 0 自身，每 hit +5%，不限次。
HIT_LEADER_ROW = {
    **{k: v for k, v in HIT_ROW_BEFORE.items() if k not in (9, 10, 11)},
    6: "42", 13: "2", 16: "600000", 17: "600000", 18: ELEMENT_TOKEN, 48: "0", 51: "5000", 52: "5000",
}
#: 改前 ``1399913#1``（Ⓜ）：trigger 8（进入 Fever）→ kind 33 target 5 雷 150%，不限次。
FEVER_ROW_BEFORE = {
    0: f"{CODE}_3", 1: "false", 2: "attack_common", 3: "0", 5: "0", 6: "0", 13: "0", 20: "0",
    27: "8", 30: "100000", 31: "100000", 34: "(None)", 35: "0", 39: "(None)", 46: "0",
    47: "33", 48: "5", 49: ELEMENT_TOKEN, 51: "150000", 52: "150000",
}
FEVER_ROW_AFTER = {**FEVER_ROW_BEFORE, 34: "3", 51: "40000", 52: "40000"}
#: 新增队长 ``139991#4``（能力 c≥5 → 队长 c−2）。
FEVER_LEADER_ROW = {
    0: CODE, 1: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "8", 28: "100000", 29: "100000",
    32: "(None)", 33: "0", 37: "(None)", 44: "0", 45: "33", 46: "5", 47: ELEMENT_TOKEN,
    49: "30000", 50: "30000",
}
HIT_ROW, FEVER_ROW = 0, 1            # 0 基记录号
ABILITY2_ROWS_BEFORE, ABILITY3_ROWS, LEADER_ROWS_BEFORE = 3, 4, 4

# ------------------------------------------------------------------ 面板

LEADER_ADDED_LINES = (
    "雷属性共鸣时，自身技能每命中1次，自身攻击力＋5%",
    "每次进入Fever：雷属性角色直击伤害＋30%",
)
LEADER_PANEL_BEFORE = (
    "Fever中：赋予雷属性角色直接攻击伤害＋400%",
    "Fever中：赋予雷属性角色攻击力＋200%",
    "自身Fever持续时间延长＋25%",
    "雷属性共鸣时，非Fever状态下：发动技能，自身Fever槽＋50%",
)
ABILITY2_PANEL_LINE = 0
OLD_ABILITY2_LINE = "雷属性共鸣时：自身技能每命中1次，队长攻击力＋50%"
NEW_ABILITY2_LINE = "雷属性共鸣时，自身技能每命中1次，队长攻击力＋2%，最多25次"
ABILITY2_PANEL_LINES = 2
ABILITY3_PANEL_LINE = 1
OLD_ABILITY3_LINE = MAIN_ICON + "每次进入Fever：雷属性角色直击伤害＋150%"
NEW_ABILITY3_LINE = MAIN_ICON + "每次进入Fever：雷属性角色直击伤害＋40%，最多3次"
ABILITY3_PANEL_LINES = 6
#: 本批第一稿（复核前）写进过设计镜像 rework1/panel/kuro.json 的三行，从未进 live / 候选；
#: :func:`mirror_updates` 只认这几行为可替换的旧稿，其余不符一律当漂移拒绝。
SUPERSEDED_DRAFT_LINES = {
    "leader": ("雷属性共鸣时：自身技能每命中1次，自身攻击力＋5%", "每次进入Fever：雷属性角色直击伤害＋30%"),
    2: "雷属性共鸣时：自身技能每命中1次，队长攻击力＋2%（最多25次）",
    3: "每次进入Fever：雷属性角色直击伤害＋40%（最多3次）",
}


class KuroBalanceBError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _build(width: int, cells: dict[int, str]) -> list[str]:
    row = [""] * width
    for col, value in cells.items():
        row[col] = value
    return row


def ability2_rows(rows: list[list[str]]) -> list[list[str]]:
    """#0 封顶 25 次 × 2%；#1/#2 逐字保留；末尾追加前置 42 的队长承载行。"""
    if len(rows) != ABILITY2_ROWS_BEFORE or any(len(r) != ABILITY_NCOLS for r in rows):
        raise KuroBalanceBError(f"ability {ABILITY2_KEY}: expected {ABILITY2_ROWS_BEFORE}×{ABILITY_NCOLS}")
    if not _matches(rows[HIT_ROW], ABILITY_NCOLS, HIT_ROW_BEFORE):
        raise KuroBalanceBError(f"ability {ABILITY2_KEY}#{HIT_ROW}: not the reviewed uncapped skill-hit row")
    out = deepcopy(rows)
    out[HIT_ROW] = _build(ABILITY_NCOLS, HIT_ROW_AFTER)
    out.append(_build(ABILITY_NCOLS, HIT_LEADER_ROW))
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != [HIT_ROW]:
        raise AssertionError("ability2_rows touched another record")
    return out


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """#1 封顶 3 次 × 40%；其余 3 行逐字保留。"""
    if len(rows) != ABILITY3_ROWS or any(len(r) != ABILITY_NCOLS for r in rows):
        raise KuroBalanceBError(f"ability {ABILITY3_KEY}: expected {ABILITY3_ROWS}×{ABILITY_NCOLS}")
    if not _matches(rows[FEVER_ROW], ABILITY_NCOLS, FEVER_ROW_BEFORE):
        raise KuroBalanceBError(f"ability {ABILITY3_KEY}#{FEVER_ROW}: not the reviewed uncapped Fever row")
    out = deepcopy(rows)
    out[FEVER_ROW] = _build(ABILITY_NCOLS, FEVER_ROW_AFTER)
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != [FEVER_ROW]:
        raise AssertionError("ability3_rows touched another record")
    return out


def moved_fever_leader_row(ability3_before: list[list[str]]) -> list[str]:
    """口径 A3 公式：[c0, '0', ''] + 能力行[5:]，强度 150% → 30%（1/5）。"""
    source = ability3_before[FEVER_ROW]
    if not _matches(source, ABILITY_NCOLS, FEVER_ROW_BEFORE):
        raise KuroBalanceBError(f"ability {ABILITY3_KEY}#{FEVER_ROW}: moved row drifted")
    row = [CODE, "0", ""] + deepcopy(source[5:])
    row[49] = row[50] = FEVER_LEADER_ROW[49]
    if not _matches(row, LEADER_NCOLS, FEVER_LEADER_ROW):
        raise AssertionError("moved Fever leader row is not the reviewed shape")
    return row


def leader_rows(rows: list[list[str]], ability3_before: list[list[str]]) -> list[list[str]]:
    """队长 4 行逐字保留，末尾追加「每次进入 Fever → 雷队直击 +30%」。"""
    if len(rows) != LEADER_ROWS_BEFORE or any(len(r) != LEADER_NCOLS for r in rows):
        raise KuroBalanceBError(f"leader {LEADER_KEY}: expected {LEADER_ROWS_BEFORE}×{LEADER_NCOLS}")
    if any(r[25] == "8" for r in rows):
        raise KuroBalanceBError(f"leader {LEADER_KEY}: already carries a Fever-entry row")
    return deepcopy(rows) + [moved_fever_leader_row(ability3_before)]


def _single_text(rows: list[list[str]], key: str) -> str:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise KuroBalanceBError(f"{key}: expected one single-column row")
    return rows[0][0]


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    lines = _single_text(rows, CAS_LEADER).split("\n")
    if tuple(lines) != LEADER_PANEL_BEFORE:
        raise KuroBalanceBError(f"{CAS_LEADER}: unexpected panel text")
    return [["\n".join(lines + list(LEADER_ADDED_LINES))]]


def _replace_line(rows, key, index, count, old, new) -> list[list[str]]:
    lines = _single_text(rows, key).split("\n")
    if len(lines) != count or lines[index] != old:
        raise KuroBalanceBError(f"{key}: unexpected panel text layout")
    lines[index] = new
    return [["\n".join(lines)]]


def ability2_text(rows) -> list[list[str]]:
    return _replace_line(rows, CAS_ABILITY2, ABILITY2_PANEL_LINE, ABILITY2_PANEL_LINES,
                         OLD_ABILITY2_LINE, NEW_ABILITY2_LINE)


def ability3_text(rows) -> list[list[str]]:
    out = _replace_line(rows, CAS_ABILITY3, ABILITY3_PANEL_LINE, ABILITY3_PANEL_LINES,
                        OLD_ABILITY3_LINE, NEW_ABILITY3_LINE)
    if any(not line.startswith(MAIN_ICON) for line in out[0][0].split("\n")):
        raise KuroBalanceBError(f"{CAS_ABILITY3}: main-position slot lines must start with the main icon")
    return out


def row_problems(kind: str, row: list[str]) -> list[str]:
    return (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
            + L.invoke_skill_string_problems(row, set(), kind=kind)
            + L.ability_element_column_problems(kind, row, ELEMENT))


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        got = digest(value)
        if got != want:
            raise KuroBalanceBError(f"unreviewed live baseline for {kind}:{key} ({got} != {want})")
        inputs[kind, key] = deepcopy(value)

    ability3_before = inputs["ability", ABILITY3_KEY]
    ability = {ABILITY2_KEY: ability2_rows(inputs["ability", ABILITY2_KEY]),
               ABILITY3_KEY: ability3_rows(ability3_before)}
    leader = leader_rows(inputs["leader", LEADER_KEY], ability3_before)
    problems = [f"leader#{i}: {p}" for i, row in enumerate(leader) for p in row_problems("leader_ability", row)]
    problems += [f"{key}#{i}: {p}" for key, rows in ability.items()
                 for i, row in enumerate(rows) for p in row_problems("ability", row)]
    if L.required_client_capabilities("leader_ability", leader[-1]) \
            or L.required_client_capabilities("ability", ability[ABILITY2_KEY][-1]):
        problems.append("new rows unexpectedly need client capabilities")
    if problems:
        raise KuroBalanceBError("; ".join(problems))
    cas = {CAS_LEADER: leader_text(inputs["cas", CAS_LEADER]),
           CAS_ABILITY2: ability2_text(inputs["cas", CAS_ABILITY2]),
           CAS_ABILITY3: ability3_text(inputs["cas", CAS_ABILITY3])}
    return {
        "ability": ability,
        "leader": {LEADER_KEY: leader},
        "cas": cas,
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_kuro.py",
            "spec": "第二批施工口径 A1–A4（无上限成长；trigger 107 队长表零先例 ⇒ 能力行 + 前置 42）；设计稿 growth_design 139991",
            "frequency": {"skill_hit_107": "3 分钟约 105–135 次 ⇒ ≥30 取 1/10",
                          "fever_entry_8": "3 分钟约 8–12 次 ⇒ ≤15 取 1/5"},
            "changes": {
                f"ability:{ABILITY2_KEY}#{HIT_ROW}": "c34 (None)→25；c51/c52 50000→2000（技能每命中 队长攻击力 +2%，最多 25 次）",
                f"ability:{ABILITY2_KEY}#3（新增）": "前置1 42 队长 + 前置2 雷共鸣：技能每命中 → 自身攻击力 +5%（不限次，1/10）",
                f"ability:{ABILITY3_KEY}#{FEVER_ROW}": "c34 (None)→3；c51/c52 150000→40000（每次进入 Fever 雷队直击 +40%，最多 3 次）",
                f"leader_ability:{LEADER_KEY}#4（新增）": "每次进入 Fever → 雷队直击 +30%（不限次，1/5）",
            },
            "leader_precedents": {
                "trigger_8": "官方队长表 24 行（kind 32×6、0×4、34×4、489×3、28×2、211×2、206、461、246）",
                "content_33_target_5": "官方队长表瞬发 kind 33 target 5 共 14 行（常驻 11、trigger 23 两行、trigger 20 一行）",
                "combination": "trigger 8 → kind 33 在官方队长表与官方能力表都是 0 行；只有 live 能力行 1399913#1 在线。"
                               "两列取值各有先例（队长表按列逐项解析）⇒ 风险低，上线前真机开角色页/队长页确认",
                "donor": "官方 131164#1（trigger 8 → kind 32 target 5 Yellow，同触发同目标，kind 不同）",
                "trigger_107": "官方与 live 自制队长表 0 行 ⇒ 走能力行 + 前置 42（口径 A4）"},
            "pre42_shape": "live 凯尔 1399903#4/#5：前置1 42 + 前置2 kind 2 ≥6 Yellow（在线）",
            "panel": {CAS_LEADER: list(LEADER_ADDED_LINES), CAS_ABILITY2: NEW_ABILITY2_LINE,
                      CAS_ABILITY3: NEW_ABILITY3_LINE.strip(),
                      "style": "上限按黑现有写法「，最多N次」；共鸣前缀「雷属性共鸣时，」（口径 D）",
                      "leader_line_5_source": "能力2 前置42 承载行：能力2 未解锁时不生效但队长面板仍显示（同凯尔先例）"},
            "untouched": ["技能 DSL 轮盘（口径 C）", "直击 +3（口径 B5）", "能力5 击杀回槽 CT（表二暂缓）",
                          "队长 #3 非Fever 技能 → Fever 点 213（资源，不是成长）", "能力3 #3 骰运（上限 6）"],
            "generator": "wf_midautumn_kit_kuro.py（LEADER +1、ABILITY 1399912 #0/+#3、1399913 #1、PANEL_* 已同步）",
            "capabilities": [],
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/kuro.json"
PANEL_REL = BATCH / "rework1/panel/kuro.json"

MIRROR_TAG = "balance_20260927b"
MIRROR_NOTE = ("2026-09-27：作者平衡第二批（无上限成长）——能力2「技能每命中→队长攻击力」50%不限次→2%最多25次，"
               "无上限部分改为能力2新增行（前置42 仅队长时：每命中自身攻击力＋5%，trigger 107 队长表零先例）；"
               "能力3「每次进入Fever→雷队直击」150%不限次→40%最多3次，无上限部分进队长（每次＋30%）。"
               "队长面板追加两行，能力2第1行、能力3第2行同步。")


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等）。"""
    import wf_midautumn_kit_kuro as K
    design, panel = deepcopy(design), deepcopy(panel)

    plan = design["plan"]
    leader = plan["leader_ability"]
    base_rows = [row for row in leader["rows"] if row.get("index", 0) < LEADER_ROWS_BEFORE]
    added = []
    for index, (donor, cells, expect) in enumerate(K.LEADER):
        if index < LEADER_ROWS_BEFORE:
            continue
        added.append(dict(index=index, donor=donor, desc_expected=expect,
                          cells={str(k): v for k, v in sorted(cells.items())},
                          why="2026-09-27 平衡第二批：能力3「每次进入Fever→雷队直击」的无上限部分搬进队长（1/5）；"
                              "官方队长 trigger 8 有 24 行、瞬发 kind 33 target 5 有 14 行，但 trigger 8→kind 33 组合"
                              "在官方队长/能力表都是 0 行（只有 live 能力行 1399913#1）；donor 131164#1 是 trigger 8→"
                              "kind 32，上线前真机确认角色页/队长页"))
    leader["rows"] = base_rows + added
    leader["new_row_count"] = len(K.LEADER)
    leader[MIRROR_TAG] = "队长 4→5 行：追加 #4「每次进入Fever→雷队直击＋30%」（不限次）"

    keys = plan["ability"]["keys"]
    for key in (ABILITY2_KEY, ABILITY3_KEY):
        records = []
        for index, (donor, cells, expect) in enumerate(K.ABILITY[key]):
            old = next((r for r in keys[key]["records"] if r.get("index") == index), {})
            records.append({**{k: v for k, v in old.items() if k not in ("donor", "desc_expected", "cells")},
                            "index": index, "donor": donor, "desc_expected": expect,
                            "cells": {str(k): v for k, v in sorted(cells.items())}})
        keys[key]["records"] = records
        keys[key]["unisonable_per_record"] = [cells.get(1) for _d, cells, _e in K.ABILITY[key]]
    keys[ABILITY2_KEY][MIRROR_TAG] = ("#0 c34 (None)→25、c51/c52 50000→2000；新增 #3 前置1 42 队长＋前置2 雷共鸣 "
                                      "技能每命中→自身攻击力＋5%（不限次）")
    keys[ABILITY3_KEY][MIRROR_TAG] = "#1 c34 (None)→3、c51/c52 150000→40000"

    rows = plan["texts"]["custom_ability_string"]["rows"]
    for row in rows:
        if row["key"] in K.CAS_TEXTS:
            row["text"] = K.CAS_TEXTS[row["key"]]
    if {row["key"]: row["text"] for row in rows} != K.CAS_TEXTS:
        raise ValueError("design custom_ability_string still differs from the generator")
    design[MIRROR_TAG] = dict(
        spec="第二批施工口径 A 节：无上限成长移到队长并放缓（按 3 分钟实际次数），能力栏换有上限的弱化版；"
             "trigger 107 队长表零先例 ⇒ 能力行 + 前置 42 承载",
        module="mod-tools/wf_balance_20260927b_kuro.py",
    )

    # 面板镜像只动本批三处（队长追加两行、能力2 第1行、能力3 第2行）。镜像里能力3 的「每直击1000次」
    # 与缺少的「骰运6层翻倍」行是 09-21/09-23 两轮修订留下的既有漂移（生成器已是 500 次 + 翻倍行），不在本批范围。
    leader_lines = panel["leader"]["lines"]
    texts = [line.get("text") for line in leader_lines]
    if texts == list(LEADER_PANEL_BEFORE):
        leader_lines.extend(dict(text=text, status="changed") for text in LEADER_ADDED_LINES)
    elif texts == list(LEADER_PANEL_BEFORE + SUPERSEDED_DRAFT_LINES["leader"]):     # 本批第一稿 → 定稿
        for line, text in zip(leader_lines[len(LEADER_PANEL_BEFORE):], LEADER_ADDED_LINES):
            line.update(text=text, status="changed")
    elif texts != list(LEADER_PANEL_BEFORE + LEADER_ADDED_LINES):
        raise ValueError("panel mirror leader layout drifted")
    if list(K.PANEL_LEADER) != list(LEADER_PANEL_BEFORE + LEADER_ADDED_LINES):
        raise ValueError("generator PANEL_LEADER differs from the batch-b leader panel")
    for slot, index, old, new in ((2, ABILITY2_PANEL_LINE, OLD_ABILITY2_LINE, NEW_ABILITY2_LINE),
                                  (3, ABILITY3_PANEL_LINE, OLD_ABILITY3_LINE, NEW_ABILITY3_LINE)):
        old, new = old.replace(MAIN_ICON, ""), new.replace(MAIN_ICON, "")
        if K.PANEL_ABILITY[slot][index] != new:
            raise ValueError(f"generator PANEL_ABILITY[{slot}][{index}] is not the batch-b line")
        entry = next(e for e in panel["abilities"] if int(e["index"]) == slot)
        line = entry["lines"][index]
        if line.get("text") in (old, SUPERSEDED_DRAFT_LINES[slot]):
            entry["lines"][index] = dict(line, text=new, status="changed")
        elif line.get("text") != new:
            raise ValueError(f"panel mirror ability {slot} line {index} drifted: {line.get('text')!r}")
    notes = [note for note in panel.get("notes", []) if not note.startswith("2026-09-27：作者平衡第二批")]
    panel["notes"] = notes + [MIRROR_NOTE]
    return design, panel


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """保留原文件的缩进、换行风格（本机 CRLF）与末尾有无换行。"""
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

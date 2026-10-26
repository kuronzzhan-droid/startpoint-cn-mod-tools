# -*- coding: utf-8 -*-
"""碧安卡「女王的开放课堂」119989 ``lady_summoner_campus``（火）：2026-09-27 平衡第二批。

作者原话（2026-09-27，依次两条）：
  (2)「校园龙妈的能力1获得幼龙吐息的时候自身技能槽+50%改为+20%」
  (3)「校园龙妈的能力5也去掉主位限制,能力1战斗开始时自身技能槽+75%降低为+50%,」
（第二批施工口径写「碧安卡不动」，指 A 条无上限成长；这两条是作者当面追加的单点改值，作者原话优先。）

落点（只动下列格子，其余逐字保留；行号 0 基，面板/作者口中的「行3」= #2）：

========================  ===================================================  ==============  ==============
位置                      内容                                                 改前            改后
========================  ===================================================  ==============  ==============
ability:1199891#0         战斗开始 → 自身（t0）技能槽 I211（请求 3）            c51/c52 75000   c51/c52 50000
ability:1199891#2         火共鸣 + 触发 185 获得固有 11998902「幼龙吐息」       c51/c52 50000   c51/c52 20000
                          → 自身技能槽 I211；限次 (None)、CT 0 不动（请求 2）
ability:1199895#0         火共鸣 + 火属性角色发动技能（T23 puller7 Red）        c1 false        c1 true
                          → Fever 槽 I724 15%（请求 3：去主位限制；行内无 202）
desc_override_…_1         面板第 1 行「自身技能槽+75%」/ 第 3 行「+50%」        +75% / +50%     +50% / +20%
desc_override_…_5         面板唯一一行去掉主位图标前缀 " <icon id='main'>  "     带 Ⓜ            不带 Ⓜ
========================  ===================================================  ==============  ==============

能力1 仍是整键主位（4 行 c1 全 false，面板每行保留 Ⓜ）；1199891#1（I536 强化幼龙吐息）、#3（同触发 → 队长攻击力
200% 15 秒）、面板第 2 行、1199895 的触发/前置/数值与面板文字逐字不动。改后能力 1、3 主位；2、4、5、6 不限主位。

生成器（已同步源码常量，测试断言生成器输出 == :func:`revise` 输出）：
- 1199891#0 与 1199895 由 ``wf_bianca_dragon_abilities.ability_rows`` 产出（``opening`` 50_000；
  ``MAIN_ONLY_SLOTS = (1, 3)`` 决定整键 c1）；1199891#1–#3 由 ``wf_bianca_dragon_bridge.a1_enhancement_rows``
  产出（``charge`` 20000），``wf_bianca_dragon.assemble`` 把后者追加到 A1。
- 面板 ``wf_campus_panel_text._BIANCA["a1"]``（+50% / +20%）经 ``wf_featured_main_ability.main_description``
  加主位图标；``panel_descriptions`` 不再给碧安卡 a5 加图标。
- ``wf_featured_main_ability`` 只管五名置顶角色的能力1，不写 1199895；``wf_campus_bianca_data`` 是被取代的
  09-11 Fever 版生成器，不产这些行。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from wf.paths import root_path

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

CID = "119989"
CODE = "lady_summoner_campus"
#: flow owner（``.cdn/cn/character-releases/active.json`` base_package_owners 登记 campus-bianca-20260911）。
PACKAGES = ["campus-bianca-20260911"]
#: 候选 manifest 现值 0.1.0 ⇒ 0.1.1（只升不降；本批此前未暂存，请求 2、3 合并为同一次回写）。
PACKAGE_VERSION = {"campus-bianca-20260911": "0.1.1"}
#: 候选 manifest required_capabilities 现为 []。本批回写的 1199895（I724 AddFeverPointRatio）需要
#: kyubi-fever-ratio-v1，两条 desc_override_* 覆盖行需要面板覆盖补丁 v2；live 早已依赖二者（同 celtie 本批写法）。
CAPABILITIES = ["kyubi-fever-ratio-v1", "panel-description-override-v2"]
#: 候选 91 个 manifest 条目与文件哈希逐一一致（2026-09-27 RevisionCandidate 只读构造通过）。
REVIEWED_DRIFT: dict = {}

ABILITY_KEY = CID + "1"              # 能力1
A5_KEY = CID + "5"                   # 能力5
CAS_A1 = f"desc_override_{CODE}_1"
CAS_A5 = f"desc_override_{CODE}_5"
ABILITY_NCOLS = 126
ELEMENT = 0                          # master/character c3：火（0 基内部元素）
ELEMENT_TOKEN = "Red"
BREATH_UID = "11998902"              # 固有「幼龙吐息」
CHANGE_SKILL_STRING = f"change_skill_{CODE}_dragon"
MAIN_ICON = " <icon id='main'>  "    # 与 wf_featured_main_ability.MAIN 逐字一致
PRE_KIND_COLS = (6, 13, 20)          # 三组前置的种类列；202/203 = 仅主位/仅副位门

VALUE_COLS = (51, 52)                # instant_content.value（Lv1 / 满级），100000 = 100%
OPEN_ROW, BREATH_ROW = 0, 2
#: 能力1 改值 {行号: (改前, 改后)}。
A1_VALUE_CHANGES = {
    OPEN_ROW: ("75000", "50000"),    # 请求 3：战斗开始自身技能槽 75% → 50%
    BREATH_ROW: ("50000", "20000"),  # 请求 2：获得幼龙吐息自身技能槽 50% → 20%
}

#: live 输入基线（2026-09-27 本地链尾 1.4.1049，stage_batch.make_read(live_only=True) 只读取数）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("ability", ABILITY_KEY): "8164c52e55d8a3020e4028aa89c66111467eecff3025fc45d9016db8fb43cd03",
    ("ability", A5_KEY): "80ede2e6e925063e6c35e3a83446380b642e743cd6c4dedc29ca6616583c6f83",
    ("cas", CAS_A1): "7a739888a8cf6e28d64343cf1482c6a820c9811d66b7e4b331f4e5551041f236",
    ("cas", CAS_A5): "b54b0b58f6c4e90b143a8d6afedee16c162f2a57d8c247def0a64fe99651d7ca",
}

# ------------------------------------------------------------------ 逐格指纹（BEFORE 之外的第二道锁）


def _head(slot: int, main: str) -> dict[int, str]:
    return {0: f"{CODE}_{slot}", 1: main, 2: "attack_red", 3: "0", 5: "0", 13: "0", 20: "0",
            39: "(None)", 46: "0"}


_FIRE = {6: "2", 9: "600000", 10: "600000", 11: ELEMENT_TOKEN}
#: 触发 185（固有状态变化，puller 0 = 自身）监听「幼龙吐息」被赋予；不限次、无 CT。
_BREATH = {27: "185", 28: "0", 30: "100000", 31: "100000", 34: "(None)", 35: "0", 37: BREATH_UID}
_A1 = _head(1, "false")

#: 能力1 全部非空列（其余列必须为空），改前。
ROW_CELLS: tuple[dict[int, str], ...] = (
    {**_A1, 6: "0", 27: "0", 47: "211", 48: "0", 51: "75000", 52: "75000"},          # #0 开局自身技能槽 75%
    {**_A1, **_FIRE, 27: "0", 47: "536", 70: CHANGE_SKILL_STRING},                    # #1 强化幼龙吐息
    {**_A1, **_FIRE, **_BREATH, 47: "211", 48: "0", 51: "50000", 52: "50000"},       # #2 吐息 → 自身技能槽 50%
    {**_A1, **_FIRE, **_BREATH, 47: "0", 48: "2", 51: "200000", 52: "200000",         # #3 吐息 → 队长攻击力 200% 15 秒
     57: "90000000", 58: "90000000", 59: "100000", 60: "100000", 61: "(None)", 62: "(None)",
     63: "(None)", 64: "(None)", 65: "(None)", 67: "0", 72: "false", 74: "1", 75: "0"},
)
AFTER_ROW_CELLS: tuple[dict[int, str], ...] = tuple(
    {**cells, **({col: A1_VALUE_CHANGES[i][1] for col in VALUE_COLS} if i in A1_VALUE_CHANGES else {})}
    for i, cells in enumerate(ROW_CELLS))

#: 能力5 唯一一行：火共鸣 + 火属性角色发动技能（T23 puller 7 Red）→ Fever 槽 I724 15%；改前主位。
A5_CELLS: dict[int, str] = {**_head(5, "false"), **_FIRE, 27: "23", 28: "7", 29: ELEMENT_TOKEN,
                            30: "100000", 31: "100000", 34: "(None)", 35: "0",
                            47: "724", 51: "15000", 52: "15000"}
A5_AFTER_CELLS: dict[int, str] = {**A5_CELLS, 1: "true"}

# ------------------------------------------------------------------ 面板

PANEL_A1_BEFORE = (
    MAIN_ICON + "战斗开始时：自身技能槽+75%。",
    MAIN_ICON + "火属性共鸣时，强化幼龙吐息，赋予全场敌人能力伤害抗性降低20%效果，持续15秒。",
    MAIN_ICON + "火属性共鸣时，每次获得「幼龙吐息」，自身技能槽+50%，赋予队长攻击力提升200%效果，持续15秒。",
)
#: 面板改字 {行号: (改前片段, 改后片段)}；每行恰好一处。
PANEL_A1_EDITS = {
    OPEN_ROW: ("自身技能槽+75%", "自身技能槽+50%"),
    BREATH_ROW: ("自身技能槽+50%", "自身技能槽+20%"),
}
PANEL_A1_AFTER = tuple(line.replace(*PANEL_A1_EDITS[i]) if i in PANEL_A1_EDITS else line
                       for i, line in enumerate(PANEL_A1_BEFORE))
PANEL_A5_TEXT = "火属性共鸣时，火属性角色发动技能：Fever槽+15%。"
PANEL_A5_BEFORE = (MAIN_ICON + PANEL_A5_TEXT,)
PANEL_A5_AFTER = (PANEL_A5_TEXT,)


class BiancaBalanceError(ValueError):
    pass


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise BiancaBalanceError(f"unreviewed live baseline for {kind}:{key} "
                                 f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], cells: dict[int, str]) -> bool:
    return (len(row) == ABILITY_NCOLS
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _changed(before: list[list[str]], after: list[list[str]]) -> dict[int, list[int]]:
    return {i: [c for c in range(ABILITY_NCOLS) if a[c] != b[c]]
            for i, (a, b) in enumerate(zip(before, after)) if a != b}


def ability1_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力1 #0 c51/c52 75000 → 50000、#2 c51/c52 50000 → 20000；#1/#3 与其余列逐字保留，整键仍主位。"""
    if len(rows) != len(ROW_CELLS):
        raise BiancaBalanceError(f"ability {ABILITY_KEY}: expected {len(ROW_CELLS)} records, got {len(rows)}")
    for index, cells in enumerate(ROW_CELLS):
        if not _matches(rows[index], cells):
            raise BiancaBalanceError(f"ability {ABILITY_KEY}: #{index} is not the reviewed row "
                                     f"(kind {cells[47]}, strength {cells.get(51)})")
    out = deepcopy(rows)
    for index, (_, new) in A1_VALUE_CHANGES.items():
        for col in VALUE_COLS:
            out[index][col] = new
    # 自检：只动了 #0/#2 的 c51/c52，且整键主位不变。
    if not all(_matches(row, cells) for row, cells in zip(out, AFTER_ROW_CELLS)):
        raise AssertionError("ability1_rows produced an unexpected row")
    if _changed(rows, out) != {i: list(VALUE_COLS) for i in A1_VALUE_CHANGES}:
        raise AssertionError("ability1_rows touched more than #0/#2 c51/c52")
    if {row[1] for row in out} != {"false"}:
        raise AssertionError("ability1 must stay main-slot only")
    return out


def ability5_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力5 去主位限制：整键 c1 false → true；行内无 202/203 门，触发/前置/数值逐字保留。"""
    if len(rows) != 1:
        raise BiancaBalanceError(f"ability {A5_KEY}: expected 1 record, got {len(rows)}")
    if not _matches(rows[0], A5_CELLS):
        raise BiancaBalanceError(f"ability {A5_KEY}: #0 is not the reviewed main-only I724 row")
    out = deepcopy(rows)
    out[0][1] = "true"
    if not _matches(out[0], A5_AFTER_CELLS) or _changed(rows, out) != {0: [1]}:
        raise AssertionError("ability5_rows touched more than c1")
    if any(row[col] in ("202", "203") for row in out for col in PRE_KIND_COLS):
        raise AssertionError("ability5 still carries a main/unison-only precondition")
    return out


def _panel_lines(rows: list[list[str]], key: str, expected: tuple[str, ...]) -> tuple[str, ...]:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise BiancaBalanceError(f"{key}: expected one single-column row")
    lines = tuple(rows[0][0].split("\n"))
    if lines != expected:
        raise BiancaBalanceError(f"{key}: unexpected panel text")
    return lines


def panel_a1(rows: list[list[str]]) -> list[list[str]]:
    """面板第 1 行「+75%」→「+50%」、第 3 行「+50%」→「+20%」；第 2 行与三行主位图标逐字保留。"""
    _panel_lines(rows, CAS_A1, PANEL_A1_BEFORE)
    return [["\n".join(PANEL_A1_AFTER)]]


def panel_a5(rows: list[list[str]]) -> list[list[str]]:
    """面板唯一一行去掉行首主位图标前缀，文字其余逐字保留。"""
    _panel_lines(rows, CAS_A5, PANEL_A5_BEFORE)
    return [["\n".join(PANEL_A5_AFTER)]]


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    ability1 = _checked(read, "ability", ABILITY_KEY)
    ability5 = _checked(read, "ability", A5_KEY)
    text1 = _checked(read, "cas", CAS_A1)
    text5 = _checked(read, "cas", CAS_A5)
    return {
        "ability": {ABILITY_KEY: ability1_rows(ability1), A5_KEY: ability5_rows(ability5)},
        "leader": {}, "cas": {CAS_A1: panel_a1(text1), CAS_A5: panel_a5(text5)},
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_bianca.py",
            "spec": [
                "作者 2026-09-27：「校园龙妈的能力1获得幼龙吐息的时候自身技能槽+50%改为+20%」",
                "作者 2026-09-27：「校园龙妈的能力5也去掉主位限制,能力1战斗开始时自身技能槽+75%降低为+50%,」",
            ],
            "change": {
                f"ability:{ABILITY_KEY}#{OPEN_ROW} c51/c52": "75000 → 50000（战斗开始自身技能槽 75% → 50%）",
                f"ability:{ABILITY_KEY}#{BREATH_ROW} c51/c52": "50000 → 20000（获得幼龙吐息自身技能槽 50% → 20%）",
                f"ability:{A5_KEY}#0 c1": "false → true（去主位限制；行内无 202/203）",
                f"cas:{CAS_A1} 第1行": "自身技能槽+75% → 自身技能槽+50%",
                f"cas:{CAS_A1} 第3行": "自身技能槽+50% → 自身技能槽+20%",
                f"cas:{CAS_A5}": "去掉行首主位图标 \" <icon id='main'>  \"，文字不变",
            },
            "meaning": {
                f"ability:{ABILITY_KEY}#{BREATH_ROW}": "火共鸣（pre2 Member Red 6）时，自身每次被赋予固有 11998902"
                                                      "「幼龙吐息」（技能在场吐息成功后授予；触发 185 puller 0）→ 自身技能槽 +20%",
                f"ability:{A5_KEY}": "火共鸣时火属性角色发动技能 → Fever 槽 +15%（I724 按槽上限比例）；"
                                     "现可作副位合击装配（live 先例 1599985#0：同 T23 puller7 + I724 且 c1=true）",
            },
            "kept": {
                f"ability:{ABILITY_KEY}": "整键仍主位（4 行 c1=false）；#1 I536 强化幼龙吐息、#3 队长攻击力 200%（15 秒）逐字不动；"
                                          "#2 触发 185、限次 (None)、CT 0 不动",
                f"ability:{A5_KEY}": "触发 T23/puller 7/Red、火共鸣前置、I724 15000/15000 逐字不动",
                f"cas:{CAS_A1}": "第 2 行与三行主位图标逐字保留",
                "main_only_slots": "改后只有能力 1、3 主位",
            },
            "generator": "wf_bianca_dragon_abilities.ability_rows opening 211 → 50_000、MAIN_ONLY_SLOTS=(1, 3)（metadata 同步）；"
                         "wf_bianca_dragon_bridge.a1_enhancement_rows charge → 20000；"
                         "wf_campus_panel_text._BIANCA['a1'] 第1/3行 → +50%/+20%，panel_descriptions 不再给碧安卡 a5 加图标"
                         "（精确替换，未动希尔媞段）",
            "candidate_preexisting_drift": {
                "workspace": ('work/character_packs/campus-bianca-20260911 manifest 0.1.0，但 active.json owner 哈希 a14552f7… 对应 ${WF_ROOT}/pkgarchive/campus-bianca-20260911-1.4.846（2026.09.12.acceptance）；候选 ability 1199891–1199896 仍是 09-11 Fever 版（1199891 只有 2 行、1199895 是 I56+D154 两行且 c1=true），无 11998991 支援键、无 custom_ability_string 声明，required_capabilities 为 []'.replace("${WF_ROOT}", str(root_path()))),
                "effect": "暂存整键替换 1199891/1199895 ⇒ 候选这两键收敛为 live + 本批改值；"
                          "desc_override_lady_summoner_campus_1/_5 作为新声明写入（RevisionCandidate 面板覆盖命名空间）；"
                          "CAPABILITIES 补登 kyubi-fever-ratio-v1（I724）与 panel-description-override-v2；"
                          "1199892–1199894、1199896 等其余键为既有漂移，本批不触碰",
            },
            "capabilities": list(CAPABILITIES),
            "runtime_verified": False,
        },
    }

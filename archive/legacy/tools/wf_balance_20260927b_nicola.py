# -*- coding: utf-8 -*-
"""妮可拉·中秋 119991 ``sorceress_teacher_moon``：2026-09-27 平衡调整第二批——让能力3「月讲」消耗行生效。

作者原话（2026-09-27）：「妮可拉……让生效不限制次数」。口径 C 条（第二批施工口径.md）：
能力3（``ability:1199913``）行2–6 限次 c34 ``"0"`` → ``"(None)"``，其他格不动，面板不改，充能数值不动。

为什么是死行：``AbilityValues.parseAt34`` 把 ``"0"`` 解析成 ``Some(0)``，``restTriggerLimit=0``，
``AbilityTriggerHandler`` 在 ``restTriggerLimit<=0`` 时直接 return（第二批复核 C11 反编译核实）。
「不限次」的官方写法是字面量 ``(None)``（空串同样会被吃成 0，见 ``wf_seasonal7_kit_zehr.trigger_limit_problems``）。
同形官方先例：``1510141#0`` lamp_guide_1（I23 + puller 4 + 组 White → 触发者 t7，c34=(None)）；
同键 #0（触发 24 → 461 加层）本来就是 ``(None)``。

只动五格（0 基 #1–#5 的 c34），其余逐字保留：

====  ======================================  =========  ========
行    内容（前置 187 持有「月讲」、I23 puller 4 除自身任一 + Red）  c34 改前   c34 改后
====  ======================================  =========  ========
#1    211 触发者技能槽 10%                   "0"        (None)
#2    32  触发者攻击力 50%                   "0"        (None)
#3    245 自身技能槽上限 5%                  "0"        (None)
#4    35  自身技能充能 5%                    "0"        (None)
#5    525 消耗 1 层「月讲」（必须排在 #1–#4 之后）  "0"        (None)
====  ======================================  =========  ========

五行 c27..c34 改后仍逐格同形（生成器 ``consume_order_problems`` 的层数门契约）。
层数来源不变：#0 自身技能槽充满（触发 24）+1 层，「月讲」上限 99（``unique_condition`` c4=99）。

生成器 ``wf_midautumn_kit_nicola`` 由 ``design/nicola.json`` 驱动：设计镜像五条记录的 ``cells["34"]``
与 ``row_final[34]`` 已由 :func:`sync_mirrors` 同步为 ``(None)``，kit 另加 :func:`dead_trigger_limit_problems`
同款门禁（有瞬发触发而 c34 为 ``""``/``"0"`` 即拒绝），测试断言生成器输出 == :func:`revise` 输出。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

CID = "119991"
CODE = "sorceress_teacher_moon"
PACKAGES = ["ma-nicola"]
#: 候选 manifest 现值 1.0.0；包档案 ${WF_ROOT}/pkgarchive/ma-nicola-20260920-1.4.{942..1006} 六份全是 1.0.0 ⇒ 下一号。
PACKAGE_VERSION = {"ma-nicola": "1.0.1"}
#: 候选已声明 panel-description-override-v2；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 106 个 manifest 条目与文件逐一一致，能力键 1199913 与 desc_override 串与 live 逐字相同（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ABILITY_KEY = f"{CID}3"
CAS_SLOT3 = f"desc_override_{CODE}_3"
ABILITY_NCOLS = 126
ELEMENT = 0                        # master/character c3：火（0 基内部元素）
ELEMENT_TOKEN = "Red"
UID = "11999101"                   # 固有「月讲」
MAIN_ICON = " <icon id='main'>  "

TRIGGER_COL, LIMIT_COL = 27, 34    # instant_trigger.kind / trigger_limit
OLD_LIMIT, NEW_LIMIT = "0", "(None)"
ROWS = (1, 2, 3, 4, 5)             # 0 基；面板/作者口中的「行2–6」
CONSUME_ROW = 5

#: live 输入基线（2026-09-27 本地链尾 1.4.1049，make_read(live_only=True) 只读取数，与候选 ma-nicola 1.0.0 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("ability", ABILITY_KEY): "8b01a66c8bec189f4cd0dbf2537f9b5dcadaafdc8b643b8bd2fa7bffd7bb5b3f",
    ("cas", CAS_SLOT3): "5eec3f7ca0db6dc2e1c95b2a057af298742f293b6afc0ec969035c1da8c67299",
}

#: 火共鸣前置 + 前置 187（自身持有「月讲」）+ I23 puller 4（除自身任一）+ 组 Red —— 五行共用，逐格一致。
_GATE = {
    0: f"{CODE}_3", 1: "false", 2: "action_skill", 3: "0", 5: "0", 6: "2", 9: "600000", 10: "600000",
    11: ELEMENT_TOKEN, 13: "187", 14: "0", 19: UID, 20: "0", 27: "23", 28: "4", 29: ELEMENT_TOKEN,
    30: "100000", 31: "100000", 35: "0", 39: "(None)", 46: "0",
}
#: 各行内容块（c47 kind / c48 target / c51,c52 强度 / 其余非空列）。数值一格不改。
_CONTENT: dict[int, dict[int, str]] = {
    1: {47: "211", 48: "7", 51: "10000", 52: "10000"},        # 触发者 技能槽 10%
    2: {47: "32", 48: "7", 51: "50000", 52: "50000"},         # 触发者 攻击力 50%
    3: {47: "245", 48: "0", 51: "5000", 52: "5000"},          # 自身 技能槽上限 5%
    4: {47: "35", 48: "0", 51: "5000", 52: "5000"},           # 自身 技能充能 5%
    5: {47: "525", 48: "0", 51: "100000", 52: "100000",       # 自身 消耗 1 层「月讲」
        68: UID, 74: "1", 75: "0"},
}
BEFORE_CELLS: dict[int, dict[int, str]] = {
    row: {**_GATE, LIMIT_COL: OLD_LIMIT, **content} for row, content in _CONTENT.items()}
AFTER_CELLS: dict[int, dict[int, str]] = {
    row: {**cells, LIMIT_COL: NEW_LIMIT} for row, cells in BEFORE_CELLS.items()}
#: 同键 #0：自身技能槽充满（触发 24，puller 0）→ +1 层「月讲」；本来就是 (None)，不动。
ADD_LAYER_CELLS = {
    0: f"{CODE}_3", 1: "false", 2: "action_skill", 3: "0", 5: "0", 6: "2", 9: "600000", 10: "600000",
    11: ELEMENT_TOKEN, 13: "0", 20: "0", 27: "24", 28: "0", 30: "100000", 31: "100000",
    LIMIT_COL: NEW_LIMIT, 35: "0", 39: "(None)", 46: "0", 47: "461", 48: "0", 51: "100000",
    52: "100000", 59: "100000", 60: "100000", 68: UID, 74: "1", 75: "0",
}

#: 面板（不改）：第 2 行已写「消耗1层「月讲」……（可叠加）」，与改后「不限次、可叠加」一致。
PANEL_LINES = (
    MAIN_ICON + "火属性共鸣时：自身技能槽每达到100%，自身获得1层「月讲」状态",
    MAIN_ICON + "火属性共鸣时：除自身外的火属性角色发动技能时，消耗1层「月讲」，使该角色技能槽＋10%、"
                "攻击力＋50%，同时自身技能槽上限＋5%、技能充能速度＋5%（可叠加）",
    MAIN_ICON + "火属性共鸣时：火属性角色对处于抗性降低状态的敌人，攻击力＋300%、技能伤害＋300%",
    MAIN_ICON + "火属性共鸣时：火属性角色对敌人的技能额外伤害乘区＋15%",
)
PANEL_TRIGGER_LINE = 1


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise ValueError(f"unreviewed live baseline for {kind}:{key} "
                         f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], cells: dict[int, str]) -> bool:
    return (len(row) == ABILITY_NCOLS
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def dead_trigger_limit_problems(rows: list[list[str]]) -> list[str]:
    """有瞬发触发（c27 非空非 0）的行，c34 写 ``""`` 或 ``"0"`` = 限 0 次 = 永不触发。"""
    return [f"#{index}: instant trigger {row[TRIGGER_COL]} has trigger_limit {row[LIMIT_COL]!r} "
            f"(= 0 次, never fires)"
            for index, row in enumerate(rows)
            if row[TRIGGER_COL] not in ("", "0") and row[LIMIT_COL] in ("", "0")]


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力3 #1–#5：c34 "0" → "(None)"；#0 与 #6–#8 以及这五行其余列逐字保留。"""
    if len(rows) != 9:
        raise ValueError(f"ability {ABILITY_KEY}: expected 9 records, got {len(rows)}")
    if any(len(row) != ABILITY_NCOLS for row in rows):
        raise ValueError(f"ability {ABILITY_KEY}: unexpected row width")
    if not _matches(rows[0], ADD_LAYER_CELLS):
        raise ValueError(f"ability {ABILITY_KEY}: #0 (skill-max → +1 月讲) drifted")
    for index, cells in BEFORE_CELLS.items():
        if not _matches(rows[index], cells):
            raise ValueError(f"ability {ABILITY_KEY}: #{index} is not the reviewed dead-limit row "
                             f"(kind {cells[47]}, c34 {OLD_LIMIT!r})")
    out = deepcopy(rows)
    for index in ROWS:
        out[index][LIMIT_COL] = NEW_LIMIT
        if not _matches(out[index], AFTER_CELLS[index]):   # 自检：只动了 c34
            raise AssertionError(f"ability3_rows touched more than c{LIMIT_COL} on #{index}")
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != list(ROWS):
        raise AssertionError("ability3_rows touched another record")
    # 层数门契约：受益行与消耗行 c6..c34 逐格同形，消耗行排在最后。
    consume = out[CONSUME_ROW]
    for index in ROWS:
        if out[index][6:35] != consume[6:35]:
            raise AssertionError(f"#{index} trigger block differs from the consume row")
    if max(ROWS) != CONSUME_ROW or consume[47] != "525":
        raise AssertionError("consume row must stay after the four beneficiary rows")
    problems = dead_trigger_limit_problems(out)
    if problems:
        raise AssertionError(f"ability {ABILITY_KEY} still carries dead trigger limits: {problems}")
    return out


def check_panel(rows: list[list[str]]) -> str:
    """面板不改：逐行核对现文案（写着「可叠加」，与改后不限次一致）。"""
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError(f"{CAS_SLOT3}: expected one single-column row")
    text = rows[0][0]
    if tuple(text.split("\n")) != PANEL_LINES:
        raise ValueError(f"{CAS_SLOT3}: unexpected panel text")
    return text


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    ability = _checked(read, "ability", ABILITY_KEY)
    check_panel(_checked(read, "cas", CAS_SLOT3))
    return {
        "ability": {ABILITY_KEY: ability3_rows(ability)},
        "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_nicola.py",
            "spec": "作者 2026-09-27：妮可拉……让生效不限制次数；第二批施工口径 C 条",
            "change": {f"ability:{ABILITY_KEY}#{i} c{LIMIT_COL}": f"{OLD_LIMIT!r} → {NEW_LIMIT}"
                       for i in ROWS},
            "meaning": "火共鸣且自身持有「月讲」：除自身外的火属性角色发动技能（I23 puller 4 + Red）→ "
                       "触发者技能槽 10%、攻击力 50%，自身技能槽上限 5%、充能 5%，再消耗 1 层；"
                       "改前 c34=\"0\" ⇒ parseAt34=Some(0) ⇒ 永不触发（复核 C11）；改后 (None) 不限次",
            "precedent": "官方 1510141#0 lamp_guide_1（I23 + puller 4 + 组 White → t7，c34=(None)）；"
                         f"同键 #0 461 加层行 c34=(None)",
            "kept": {
                f"ability:{ABILITY_KEY}#0": "技能槽充满 → +1 层「月讲」（461，已是 (None)）",
                f"ability:{ABILITY_KEY}#1-#5": "数值、目标、前置 187、CT 0 逐格不动（充能数值按作者不动）",
                f"ability:{ABILITY_KEY}#6-#8": "503/550/694 特攻与独立乘区，不动",
                CAS_SLOT3: "面板不改（第 2 行已写「消耗1层「月讲」……（可叠加）」）",
            },
            "growth": "改后成为按「月讲」层数门控的永久叠加（32 攻击力给触发者、245/35 给自身）；"
                      "层数只来自自身技能槽充满（3 分钟约 7–9 层，growth_design.json frequency_estimate），"
                      "每次队友施技消耗 1 层 ⇒ 3 分钟约 7–9 次：队友攻击力合计 +350–450%、自身槽上限 +35–45%、"
                      "充能 +35–45%（充能受引擎钳位）。按作者原话「不限制次数」执行，不另设限次、不搬队长。",
            "generator": "wf_midautumn_kit_nicola.py 由 design/nicola.json 驱动：五条记录 cells['34'] 与 "
                         "row_final[34] 已同步 (None)，kit 新增 dead_trigger_limit_problems 门禁",
            "capabilities": [],
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/nicola.json"
PANEL_REL = BATCH / "rework1/panel/nicola.json"

MIRROR_TAG = "balance_20260927b"
MIRROR_NOTE = ("2026-09-27：作者平衡第二批——能力3 行2–6（除自身外火属性角色施技的四条受益行与消耗行）"
               "限次 c34 \"0\"→(None)：原 \"0\" = 限 0 次、从未触发；改后按作者「让生效不限制次数」生效。"
               "面板文字不变。")
WHY_SUFFIX = ("（2026-09-27 平衡第二批更正：c34 写字面量 (None) = 不限次；此前写的 \"0\" 被 parseAt34 "
              "读成 Some(0) = 限 0 次、永不触发）")


def _slot3_records(design: dict) -> list[dict]:
    return design["plan"]["ability"]["keys"][ABILITY_KEY]["records"]


def merged_panel_lines() -> list[str]:
    """第三轮面板合并（wf_balance_20260927c_panels）后能力3 镜像的形态：本批不改面板文字，两种形态都接受。"""
    import wf_balance_20260927c_panels as P3
    return [line.replace(MAIN_ICON, "") for line in P3.PANELS_BY_CAS[CAS_SLOT3]["after"]]


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按本批改动重算两份设计镜像（纯函数、幂等）。"""
    design, panel = deepcopy(design), deepcopy(panel)
    records = _slot3_records(design)
    if len(records) != 9:
        raise ValueError("design mirror ability 3 layout drifted")
    for index in ROWS:
        entry = records[index]
        if int(entry["index"]) != index or str(entry["row_final"][47]) != _CONTENT[index][47]:
            raise ValueError(f"design mirror ability 3 #{index} drifted")
        entry["cells"]["34"] = NEW_LIMIT
        entry["row_final"][LIMIT_COL] = NEW_LIMIT
        if WHY_SUFFIX not in entry["why"]:
            entry["why"] = entry["why"] + WHY_SUFFIX
        entry["why"] = entry["why"].replace("不设 trigger_limit ⇒ 可叠加。", "c34=(None) ⇒ 不限次、可叠加。")
    rework = design["rework1"]
    rework[MIRROR_TAG] = dict(
        spec="作者 2026-09-27：妮可拉……让生效不限制次数（第二批施工口径 C 条）",
        changed=[f"槽3#{i} c{LIMIT_COL} {OLD_LIMIT!r}→{NEW_LIMIT}" for i in ROWS],
        kept=["槽3#0 461 加层（已是 (None)）", "槽3#1–#5 数值/目标/前置/CT", "槽3#6–#8", "面板文字"],
        precedent="官方 1510141#0（I23 + puller 4 + t7，c34=(None)）",
        module="mod-tools/wf_balance_20260927b_nicola.py",
    )
    three = [entry for entry in panel["abilities"] if int(entry["index"]) == 3]
    if len(three) != 1 or [line["text"] for line in three[0]["lines"]] not in (
            [line.replace(MAIN_ICON, "") for line in PANEL_LINES], merged_panel_lines()):
        raise ValueError("panel mirror ability 3 differs from the live panel")
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

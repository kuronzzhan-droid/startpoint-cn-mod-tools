# -*- coding: utf-8 -*-
"""索恩 159994 ``tweyen_light``：2026-09-27 平衡调整第二批——能力3「自身发动技能时」改成真的自身发动。

作者原话（2026-09-27）：「索恩改成自身发动技能」。口径 C 条（第二批施工口径.md）：
能力3（``ability:1599943``）面板写「自身发动技能时」而数据触发不是自身的行 → 数据改成自身发动技能
（官方 trigger 23 自身施技的 puller 写法），面板不改，充能数值不动。

逐行核对 c27/c28/c29（instant_trigger.kind / trigger_puller / trigger_puller.character_groups；
puller 枚举：0 Myself、4 OneOfExceptMyself、5 OneOfParty、6 TotalOfExceptMyself、7 TotalOfParty）：

====  ====================================================  =====================  =================
行    面板（desc_override_tweyen_light_3）                  改前 c27/c28/c29       处理
====  ====================================================  =====================  =================
#0    自身发动技能时：光属性角色状态技能伤害＋200%           23 / 0 / ""            已是自身，不动
#1    自身发动技能时：自身技能伤害＋20%（最多叠加10次）      23 / 7 / White         → 23 / 0 / ""
#2    自身发动技能时：光属性角色技能充能速度＋1.5%（…10次） 23 / 7 / White         → 23 / 0 / ""
#4/5  光属性共鸣时：光属性角色发动技能时，…                 23 / 7 / White         面板即此语义，不动
#6    光属性共鸣时：……且连击＋50（自身施技）                23 / 0 / ""            不动
====  ====================================================  =====================  =================

#1/#2 的 7+White 来自 donor 官方 ``1510813#0/#1``（high_priestess_ny22_3「光属性角色施技」），rework1 面板
沿用了「自身发动技能时」的措辞（rework1/panel/thorn.json notes[13] 登记待确认）。

官方自身施技写法 = ``c27=23, c28="0", c29=""``：官方 ability 表 569 条 I23 行里 469 条是此形，例
``1510813#2``（同母本，自身施技 → 全队(光) 状态技伤）、``2310012#0`` thunder_dragon_2（自身施技 → 自身技伤，限 4）、
``1110813#2`` shadow_redhood_3（自身施技 → 全队(火) 技能槽充能，限 4）；同键 live ``#0``/``#6`` 亦同形。

每行只动两格（c28 ``"7"``→``"0"``、c29 ``"White"``→``""``），限次 c34=10、CT 0、数值与目标逐格不动。

生成器 ``wf_midautumn_kit_thorn``：``ABILITY_DONORS[1599943]`` 两行 ``changed`` 加 28/29，新增
``check_self_trigger_rows`` 门禁；``design/thorn.json`` 两条记录的 cells 由 :func:`sync_mirrors` 同步，
测试断言生成器输出 == :func:`revise` 输出。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

CID = "159994"
CODE = "tweyen_light"
PACKAGES = ["ma-thorn"]
#: 候选 manifest 现值 1.0.0；包档案 ${WF_ROOT}/pkgarchive/ma-thorn-20260920-1.4.{947..1009} 四份全是 1.0.0 ⇒ 下一号。
PACKAGE_VERSION = {"ma-thorn": "1.0.1"}
#: 候选已声明 panel-description-override-v2；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 112 个 manifest 条目与文件逐一一致，能力键 1599943 与 desc_override 串与 live 逐字相同（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ABILITY_KEY = f"{CID}3"
CAS_SLOT3 = f"desc_override_{CODE}_3"
ABILITY_NCOLS = 126
ELEMENT = 4                        # master/character c3：光（0 基内部元素）
ELEMENT_TOKEN = "White"
MAIN_ICON = " <icon id='main'>  "

TRIGGER, PULLER, PULLER_GROUP = 27, 28, 29
SELF_TRIGGER = ("23", "0", "")     # 自身发动技能（官方写法）
OLD_TRIGGER = ("23", "7", ELEMENT_TOKEN)   # 全队合计 + 光 = 光属性角色发动技能
ROWS = (1, 2)                      # 0 基；面板第 2/3 行
SELF_PANEL_ROWS = (0, 1, 2)        # 面板写「自身发动技能时」的三行
PARTY_TRIGGER_ROWS = (4, 5)        # 面板写「光属性角色发动技能时」，本来就是 7+White

#: live 输入基线（2026-09-27 本地链尾 1.4.1049，make_read(live_only=True) 只读取数，与候选 ma-thorn 1.0.0 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("ability", ABILITY_KEY): "a05701c755039365299ba890378777130ed75ae546ed679d5b8867ff14e0f073",
    ("cas", CAS_SLOT3): "7ccc77effbd34b3ebd8db2945eb5815fe10d3910fc2c9ca810f6df5b51b2bde6",
}

#: 无前置 + 瞬发触发 23（阈值 1、CT 0、限 10）公共部分（#1/#2 共用，逐格一致）。
_TRIGGER = {
    0: f"{CODE}_3", 1: "false", 2: "action_skill", 3: "0", 5: "0", 6: "0", 13: "0", 20: "0",
    TRIGGER: "23", 30: "100000", 31: "100000", 34: "10", 35: "0", 39: "(None)", 46: "0",
}
_CONTENT: dict[int, dict[int, str]] = {
    1: {47: "34", 48: "0", 51: "20000", 52: "20000"},                         # 自身 技能伤害 20%
    2: {47: "35", 48: "5", 49: ELEMENT_TOKEN, 51: "1500", 52: "1500"},        # 全队(光) 技能槽充能 1.5%
}
BEFORE_CELLS: dict[int, dict[int, str]] = {
    row: {**_TRIGGER, PULLER: OLD_TRIGGER[1], PULLER_GROUP: OLD_TRIGGER[2], **content}
    for row, content in _CONTENT.items()}
AFTER_CELLS: dict[int, dict[int, str]] = {
    row: {**_TRIGGER, PULLER: SELF_TRIGGER[1], **content} for row, content in _CONTENT.items()}

#: 面板（不改）。
PANEL_LINES = (
    MAIN_ICON + "自身发动技能时：光属性角色状态技能伤害＋200%（持续10秒，可叠加）",
    MAIN_ICON + "自身发动技能时：自身技能伤害＋20%（最多叠加10次）",
    MAIN_ICON + "自身发动技能时：光属性角色技能充能速度＋1.5%（最多叠加10次）",
    MAIN_ICON + "光属性共鸣时：强化技能，敌方每有1个弱体效果，自身技能伤害＋40%，且连击＋50",
    MAIN_ICON + "光属性共鸣时：光属性角色发动技能时，光属性角色技能伤害＋50%（最多＋350%）、"
                "攻击力＋50%（最多＋350%）",
)
SELF_PANEL_PREFIX = MAIN_ICON + "自身发动技能时："
PARTY_PANEL_PREFIX = MAIN_ICON + "光属性共鸣时：光属性角色发动技能时，"


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


def trigger_of(row: list[str]) -> tuple[str, str, str]:
    return row[TRIGGER], row[PULLER], row[PULLER_GROUP]


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力3 #1/#2：触发方 7+White → 自身（c28 0、c29 空）；其余 5 行与本两行其余列逐字保留。"""
    if len(rows) != 7:
        raise ValueError(f"ability {ABILITY_KEY}: expected 7 records, got {len(rows)}")
    if any(len(row) != ABILITY_NCOLS for row in rows):
        raise ValueError(f"ability {ABILITY_KEY}: unexpected row width")
    for index, cells in BEFORE_CELLS.items():
        if not _matches(rows[index], cells):
            raise ValueError(f"ability {ABILITY_KEY}: #{index} is not the reviewed light-party-trigger row "
                             f"(kind {cells[47]}, c28/c29 {OLD_TRIGGER[1]}/{OLD_TRIGGER[2]})")
    if trigger_of(rows[0]) != SELF_TRIGGER or rows[0][47] != "1":
        raise ValueError(f"ability {ABILITY_KEY}: #0 (self skill → 光队状态技伤) drifted")
    for index in PARTY_TRIGGER_ROWS:
        if trigger_of(rows[index]) != OLD_TRIGGER:
            raise ValueError(f"ability {ABILITY_KEY}: #{index} (光属性角色施技) drifted")
    out = deepcopy(rows)
    for index in ROWS:
        out[index][PULLER], out[index][PULLER_GROUP] = SELF_TRIGGER[1], SELF_TRIGGER[2]
        if not _matches(out[index], AFTER_CELLS[index]):     # 自检：只动了 c28/c29
            raise AssertionError(f"ability3_rows touched more than c{PULLER}/c{PULLER_GROUP} on #{index}")
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != list(ROWS):
        raise AssertionError("ability3_rows touched another record")
    if any(trigger_of(out[i]) != SELF_TRIGGER for i in SELF_PANEL_ROWS):
        raise AssertionError("「自身发动技能时」rows must all trigger on self")
    return out


def check_panel(rows: list[list[str]]) -> str:
    """面板不改：逐行核对现文案；前三行写「自身发动技能时」，#4 行写「光属性角色发动技能时」。"""
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
            "source": "wf_balance_20260927b_thorn.py",
            "spec": "作者 2026-09-27：索恩改成自身发动技能；第二批施工口径 C 条",
            "row_audit": {
                f"ability:{ABILITY_KEY}#0": "面板「自身发动技能时」，c27/c28/c29=23/0/'' 已是自身，不动",
                f"ability:{ABILITY_KEY}#1": "面板「自身发动技能时」，c27/c28/c29=23/7/White（光属性角色施技）→ 23/0/''",
                f"ability:{ABILITY_KEY}#2": "面板「自身发动技能时」，c27/c28/c29=23/7/White（光属性角色施技）→ 23/0/''",
                f"ability:{ABILITY_KEY}#4-#5": "面板「光属性角色发动技能时」，23/7/White 与面板一致，不动",
                f"ability:{ABILITY_KEY}#6": "自身施技 → 连击＋50，23/0/''，不动",
            },
            "change": {f"ability:{ABILITY_KEY}#{i} c{PULLER}/c{PULLER_GROUP}":
                       f"{OLD_TRIGGER[1]}/{OLD_TRIGGER[2]} → {SELF_TRIGGER[1]}/''" for i in ROWS},
            "precedent": "官方自身施技写法 c27=23,c28='0',c29=''（官方 ability 569 条 I23 行中 469 条）："
                         "1510813#2 high_priestess_ny22_3（同母本）、2310012#0 thunder_dragon_2（自身施技→自身技伤 限4）、"
                         "1110813#2 shadow_redhood_3（自身施技→全队(火)充能 限4）；同键 live #0/#6",
            "kept": {
                f"ability:{ABILITY_KEY}#1-#2": "限次 c34=10、CT 0、数值（技伤 20%、充能 1.5%，充能按作者不动）、目标逐格不动",
                CAS_SLOT3: "面板不改（本来就写「自身发动技能时」）",
            },
            "effect": "改前：队伍中任一光属性角色施技都计 1 次（光队里 10 次上限很快打满）；"
                      "改后：只有索恩自己施技计次，打满需 10 次自身施技",
            "generator": "wf_midautumn_kit_thorn.py：ABILITY_DONORS[1599943] #1/#2 changed 加 28/29、"
                         "check_self_trigger_rows 门禁；design/thorn.json 两条记录 cells 已同步",
            "capabilities": [],
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/thorn.json"
PANEL_REL = BATCH / "rework1/panel/thorn.json"

MIRROR_TAG = "balance_20260927b"
MIRROR_NOTE = ("2026-09-27：作者平衡第二批「索恩改成自身发动技能」——能力3 第2/3行（自身技能伤害＋20%、"
               "光属性角色技能充能速度＋1.5%，各最多10次）的触发方由 c28=7 全队合计 + c29=White"
               "（光属性角色施技）改成自身 c28=0、c29 空，与面板「自身发动技能时」一致；上面「待作者确认」"
               "那条就此结案。面板文字、数值、限次不变。")
DONOR_SUFFIX = ("；2026-09-27 平衡第二批：触发方 c28/c29 7/White→0/空（自身施技，官方写法同母本 "
                "1510813 #2，作者「索恩改成自身发动技能」）")


def merged_panel_lines() -> list[str]:
    """第三轮面板合并（wf_balance_20260927c_panels）后能力3 镜像的形态：本批不改面板文字，两种形态都接受。"""
    import wf_balance_20260927c_panels as P3
    return [line.replace(MAIN_ICON, "") for line in P3.PANELS_BY_CAS[CAS_SLOT3]["after"]]


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按本批改动重算两份设计镜像（纯函数、幂等）。"""
    design, panel = deepcopy(design), deepcopy(panel)
    records = design["plan"]["ability"]["keys"][ABILITY_KEY]["records"]
    if len(records) != 7:
        raise ValueError("design mirror ability 3 layout drifted")
    for index in ROWS:
        entry = records[index]
        cells = entry["cells"]
        if int(entry["index"]) != index or cells.get("c47") != _CONTENT[index][47] \
                or cells.get("c34") != "10":
            raise ValueError(f"design mirror ability 3 #{index} drifted")
        cells["c28"] = SELF_TRIGGER[1]
        cells.pop("c29", None)                     # cells 只列非空列
        if DONOR_SUFFIX not in entry["donor"]:
            entry["donor"] = entry["donor"] + DONOR_SUFFIX
    design[MIRROR_TAG] = dict(
        spec="作者 2026-09-27：索恩改成自身发动技能（第二批施工口径 C 条）",
        changed=[f"槽3#{i} c28/c29 7/White→0/空" for i in ROWS],
        kept=["槽3#0/#6 本来就是自身施技", "槽3#4/#5 光属性角色施技（面板即此语义）",
              "槽3#1/#2 限次 10、CT 0、数值", "面板文字"],
        precedent="官方 1510813#2 / 2310012#0 / 1110813#2（c27=23,c28='0',c29=''）",
        module="mod-tools/wf_balance_20260927b_thorn.py",
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
    """保留原文件的缩进（design 1 格 / panel 2 格）、换行风格（本机 CRLF）与末尾有无换行。"""
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

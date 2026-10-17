# -*- coding: utf-8 -*-
"""丝缇涅尔·中秋 159995 ``still_obstinator_moon``：2026-09-27 作者平衡批次——友技回槽减半。

作者原话：「光兔丝缇涅尔的技能回转除自身外的光角色发动技能自身技能槽+10%改为+5%添加ct2s」，
随后追加「加 CT 2 秒这个不带ct了」⇒ 只减数值，CT 保持 0。

只动两处，其余逐字保留：

1. ``ability:1599953``（能力3，整键主位 c1=false）第 4 行（0 基 #3）「除自身外的光属性角色
   发动技能时（trigger 23，puller 6 除自身合计，c29 White）→ 自身技能槽（kind 211）」：
   c51/c52 10000/10000 → 5000/5000（10%→5%，满级单值）；CT c35 仍为 0（锁在前后指纹里）。
   同触发的第 5 行（#4，226 追加连击 50）按作者原话不动。
2. ``desc_override_still_obstinator_moon_3`` 第 3 行 →
   「 <icon id='main'>  光属性共鸣时：除自身外的光属性角色发动技能时，自身技能槽＋5%、连击＋50」
   （原句只换数字；无 CT 故无括号）。

生成器 ``wf_midautumn_kit_stinel``：``ABILITY[3]`` 的「友技回槽」cells 与 expect_describe、
``PANEL_SLOT3`` 第 3 行已同步，测试断言生成器输出 == :func:`revise` 输出。设计镜像
（design/stinel.json、rework1/panel/stinel.json）由 :func:`sync_mirrors` 幂等同步。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

CID = "159995"
CODE = "still_obstinator_moon"
PACKAGES = ["ma-stinel"]
#: 候选 manifest 现值 1.0.0；包档案 ${WF_ROOT}/pkgarchive/ma-stinel-20260920-1.4.{941..1001} 八份全是 1.0.0 ⇒ 下一号。
PACKAGE_VERSION = {"ma-stinel": "1.0.1"}
#: 候选已声明 kyubi-fever-ratio-v1 / panel-description-override-v2；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 104 个 manifest 条目与文件逐一一致（2026-09-27 只读核对），6 个能力键与 4 个自有串键与 live 逐字相同。
REVIEWED_DRIFT: dict = {}

ABILITY_KEY = f"{CID}3"
CAS_SLOT3 = f"desc_override_{CODE}_3"
ABILITY_NCOLS = 126
ELEMENT = 4                        # master/character c3：光（0 基内部元素）
ELEMENT_TOKEN = "White"
MAIN_ICON = " <icon id='main'>  "  # 主位限制槽 desc_override 每行的前缀

ROW = 3                            # 0 基；面板/作者口中的「能力3 第 4 条」
COMBO_ROW = 4                      # 同触发的「连击＋50」，不动
COOLTIME = 35                      # instant_trigger.cooltime（帧）；作者追加「不带 CT」⇒ 前后都是 0
NO_CT = "0"
LOW_COL, MAX_COL = 51, 52          # 瞬发内容块数值：低级 / 满级
OLD_VALUES = ("10000", "10000")    # 10%（100000 = 100%）
NEW_VALUES = ("5000", "5000")      # 5%

PANEL_LINE = 2                     # 0 基；面板第 3 行
OLD_PANEL_LINE = MAIN_ICON + "光属性共鸣时：除自身外的光属性角色发动技能时，自身技能槽＋10%、连击＋50"
NEW_PANEL_LINE = MAIN_ICON + "光属性共鸣时：除自身外的光属性角色发动技能时，自身技能槽＋5%、连击＋50"
PANEL_LINES = 4

#: live 输入基线（2026-09-27 本地链尾 1.4.1048 只读取数，与候选 ma-stinel 1.0.0 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("ability", ABILITY_KEY): "0585f341cb2a811dd51bea39a52320d61bb5bb3d00894f4bd1f7c317dc6cfa0d",
    ("cas", CAS_SLOT3): "3fed5dda2836f8ab2bcca9993e83c2b201fc58eab882da8555b1af09a37aa486",
}

#: 共鸣前置 + 瞬发触发块公共部分（#3/#4 两行共用，逐格一致）。
_TRIGGER = {
    0: f"{CODE}_3", 1: "false", 2: "action_skill", 3: "0", 5: "0", 6: "2", 9: "600000", 10: "600000",
    11: ELEMENT_TOKEN, 13: "0", 20: "0", 27: "23", 28: "6", 29: ELEMENT_TOKEN, 30: "100000",
    31: "100000", 34: "(None)", 39: "(None)", 46: "0",
}
#: 改前 #3 的逐格指纹（全部非空列；其余列必须为空）。BEFORE 之外的第二道锁，也让纯函数可单测，
#: 且对自身输出重跑必然拒绝（数值已不是旧值）。
BEFORE_CELLS: dict[int, str] = {**_TRIGGER, COOLTIME: NO_CT, 47: "211", 48: "0",
                                LOW_COL: OLD_VALUES[0], MAX_COL: OLD_VALUES[1]}
AFTER_CELLS: dict[int, str] = {**BEFORE_CELLS, LOW_COL: NEW_VALUES[0], MAX_COL: NEW_VALUES[1]}
#: 同触发的连击行（#4）：必须在场且不带 CT。
COMBO_CELLS: dict[int, str] = {**_TRIGGER, COOLTIME: NO_CT, 47: "226",
                               LOW_COL: "5000000", MAX_COL: "5000000"}


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


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力3 #3：技能槽 10%→5%（CT 保持 0）；其余 5 行与本行其余列逐字保留。"""
    if len(rows) != 6:
        raise ValueError(f"ability {ABILITY_KEY}: expected 6 records, got {len(rows)}")
    if any(len(row) != ABILITY_NCOLS for row in rows):
        raise ValueError(f"ability {ABILITY_KEY}: unexpected row width")
    hits = [i for i, row in enumerate(rows) if _matches(row, BEFORE_CELLS)]
    if hits != [ROW]:
        raise ValueError(f"ability {ABILITY_KEY}: peer-skill gauge row (211, 10%, no CT) "
                         f"not found at #{ROW}: {hits}")
    if not _matches(rows[COMBO_ROW], COMBO_CELLS):
        raise ValueError(f"ability {ABILITY_KEY}: same-trigger combo row #{COMBO_ROW} drifted")
    out = deepcopy(rows)
    out[ROW][LOW_COL], out[ROW][MAX_COL] = NEW_VALUES
    if not _matches(out[ROW], AFTER_CELLS):             # 自检：只动了这两格
        raise AssertionError("ability3_rows touched more than c51/c52")
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != [ROW]:
        raise AssertionError("ability3_rows touched another record")
    return out


def ability3_text(rows: list[list[str]]) -> list[list[str]]:
    """面板第 3 行换成新文案；其余 3 行逐字保留。"""
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError(f"{CAS_SLOT3}: expected one single-column row")
    lines = rows[0][0].split("\n")
    if len(lines) != PANEL_LINES or lines[PANEL_LINE] != OLD_PANEL_LINE:
        raise ValueError(f"{CAS_SLOT3}: unexpected panel text layout")
    if any(not line.startswith(MAIN_ICON) for line in lines):
        raise ValueError(f"{CAS_SLOT3}: main-position slot lines must start with the main icon")
    lines[PANEL_LINE] = NEW_PANEL_LINE
    return [["\n".join(lines)]]


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    ability = _checked(read, "ability", ABILITY_KEY)
    cas = _checked(read, "cas", CAS_SLOT3)
    return {
        "ability": {ABILITY_KEY: ability3_rows(ability)},
        "cas": {CAS_SLOT3: ability3_text(cas)},
        "leader": {}, "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927_stinel.py",
            "spec": "作者 2026-09-27：能力3「除自身外的光角色发动技能→自身技能槽」+10%→+5%；追加「不带ct了」",
            "change": {
                f"ability:{ABILITY_KEY}#{ROW} c{LOW_COL}/c{MAX_COL}":
                    f"{'/'.join(OLD_VALUES)} → {'/'.join(NEW_VALUES)}",
                "meaning": "光编成≥6：除自身外光属性角色发动技能（trigger 23，puller 6）→ 自身技能槽 kind 211 "
                           "10%→5%，CT 保持 0（每次触发）",
            },
            "kept": {
                f"ability:{ABILITY_KEY}#{ROW} c{COOLTIME}": "0（作者追加：不加 CT）",
                f"ability:{ABILITY_KEY}#{COMBO_ROW}": "同触发 → 226 追加连击 50，不动",
                f"ability:{ABILITY_KEY}#0-2,#5": "逐字不动",
            },
            "panel": {CAS_SLOT3: f"第{PANEL_LINE + 1}行 → {NEW_PANEL_LINE.strip()}"},
            "panel_wording": "原句只换数字；无 CT 故不加括号",
            "generator": "wf_midautumn_kit_stinel.py（ABILITY[3] 友技回槽 cells/expect、PANEL_SLOT3 已同步；"
                         "c35 显式写 0 防 donor 漂移）",
            "capabilities": [],
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/stinel.json"
PANEL_REL = BATCH / "rework1/panel/stinel.json"

MIRROR_TAG = "balance_20260927"
MIRROR_NOTE = ("2026-09-27：作者平衡批次——能力3「除自身外的光属性角色发动技能时，自身技能槽」"
               "＋10%→＋5%，不加 CT（同触发的连击＋50 不变），面板第3行同步。")
SELF_AXIS_GAUGE = "开局 50%（队长给除自身外，自身靠槽1）+ 除自身外光角色每次施技 +5%"


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等）。"""
    import wf_midautumn_kit_stinel as K
    design, panel = deepcopy(design), deepcopy(panel)

    rework = design["rework1"]
    rework[MIRROR_TAG] = dict(
        spec="作者 2026-09-27：光兔丝缇涅尔的技能回转除自身外的光角色发动技能自身技能槽+10%改为+5%；"
             "追加「加 CT 2 秒这个不带ct了」",
        changed=[f"槽3#{ROW} 211 自身技能槽 10%→5%（CT c{COOLTIME} 保持 0）"],
        kept=[f"槽3#{COMBO_ROW} 同触发 226 追加连击 50"],
        panel={CAS_SLOT3: K.PANEL_SLOT3[PANEL_LINE]},
        module="mod-tools/wf_balance_20260927_stinel.py",
    )
    rework["calibration"]["self_axis"]["技能槽"] = SELF_AXIS_GAUGE

    three = [entry for entry in panel["abilities"] if int(entry["index"]) == 3]
    if len(three) != 1 or len(three[0]["lines"]) != len(K.PANEL_SLOT3):
        raise ValueError("panel mirror ability 3 layout drifted")
    line = three[0]["lines"][PANEL_LINE]
    if line["text"] != K.PANEL_SLOT3[PANEL_LINE]:
        three[0]["lines"][PANEL_LINE] = dict(line, text=K.PANEL_SLOT3[PANEL_LINE], status="changed")
    if [entry["text"] for entry in three[0]["lines"]] != list(K.PANEL_SLOT3):
        raise ValueError("panel mirror ability 3 still differs from the generator")
    notes = [note for note in panel.get("notes", []) if not note.startswith("2026-09-27：作者平衡批次")]
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

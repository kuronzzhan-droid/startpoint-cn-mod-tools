# -*- coding: utf-8 -*-
"""凯尔 139990 ``kyle_moon``：2026-09-27 作者平衡批次（方案A）——去掉 Down 效果成长。

只做三处键级删改，其余行逐字保留：

1. ``leader_ability:139990`` 删第 5 行（0 基 #4）：during 134「月牙」层数 → 自身
   眩晕蓄积（Stunify，kind 19）每层 +25%。原行 6-10 顺移为 5-9。
2. ``ability:1399905`` 删第 2 行（#1）：编成直击 ≥50 → 雷队眩晕蓄积（Stunify，kind 51）
   +100%。同触发的第 1 行（技能充能 +5%）有独立触发块，保留。
3. 面板：``desc_override_kyle_moon`` 第 4 行去掉「、使敌人进入Down状态的能力＋25%」；
   ``desc_override_kyle_moon_5`` 只留技能充能那一句。

队长第 9 行（贯穿 → 雷队眩晕畏缩特攻 kind 53 +5%，面板「追击伤害＋5%」）按作者确认保留。

生成器 ``wf_midautumn_kit_kyle`` 已同步（LEADER / PLAN[5] / EXPECT / PANEL_*），测试断言
生成器输出 == :func:`revise` 输出。设计镜像（design/kyle.json、rework1/panel/kyle.json、
rework1/panel/_deviations.json）由 :func:`sync_mirrors` 幂等同步。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

CID = "139990"
CODE = "kyle_moon"
PACKAGES = ["ma-kyle"]
PACKAGE_VERSION = {"ma-kyle": "1.0.2"}
CAPABILITIES: list[str] = []

ABILITY_KEY = "1399905"
CAS_LEADER = "desc_override_kyle_moon"
CAS_ABILITY5 = "desc_override_kyle_moon_5"
UID_CRESCENT = "13999001"          # 固有「月牙」；删除后仍被队长行 1-4、能力 2/3 使用
ELEMENT_TOKEN = "Yellow"

LEADER_NCOLS, ABILITY_NCOLS = 124, 126
REMOVED_LEADER_INDEX = 4           # 0 基；面板/调研里的「第 5 行」
REMOVED_ABILITY_INDEX = 1          # 0 基；「第 2 行」

REMOVED_LEADER_PHRASE = "、使敌人进入Down状态的能力＋25%"
LEADER_PANEL_LINE = 3              # 0 基；面板第 4 行
OLD_ABILITY5_TEXT = ("雷属性共鸣时：雷属性角色每造成50次直击，雷属性角色技能充能速度＋5%，"
                     "敌人进入击倒状态的几率＋100%")
NEW_ABILITY5_TEXT = "雷属性共鸣时：雷属性角色每造成50次直击，雷属性角色技能充能速度＋5%"

#: live 输入基线（2026-09-27 本地链尾 1.4.1047 只读取数，与候选 ma-kyle 1.0.1 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", CID): "b3a381750c09e647c03abe22faefd9f5c1c37a7c9e7605cb8439ac5c102f2f24",
    ("ability", ABILITY_KEY): "e7832d0bf5d4cebd8393733ec186ef5d37ecc650e752700a9b19434046584374",
    ("cas", CAS_LEADER): "860c36c354f9928a421214e651c6cb1426f966e46c8fa43ce7f8941d3bae10d3",
    ("cas", CAS_ABILITY5): "cb68644ca5b33e31bc6cb446149b52384b3f81fd4fe8393b5cab60824558733a",
}

#: 被删的两条记录的逐格指纹（非空列）；BEFORE 之外的第二道锁，也让纯函数可单测。
REMOVED_LEADER_CELLS = {
    0: CODE, 1: "0", 3: "1", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
    11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0", 98: "100000", 99: "100000",
    100: "(None)", 102: UID_CRESCENT, 106: "false", 107: "19", 108: "0",
    111: "25000", 112: "25000",
}
REMOVED_ABILITY_CELLS = {
    0: f"{CODE}_5", 1: "true", 2: "special", 3: "0", 5: "0", 6: "2", 9: "600000",
    10: "600000", 11: ELEMENT_TOKEN, 13: "0", 20: "0", 27: "20", 28: "7",
    29: ELEMENT_TOKEN, 30: "5000000", 31: "5000000", 34: "(None)", 35: "0",
    39: "(None)", 46: "0", 47: "51", 48: "5", 49: ELEMENT_TOKEN,
    51: "100000", 52: "100000",
}

#: Down 成长相关内容 kind：leader c107 / ability c47 = 19 或 51（Stunify）。删后不得残留。
STUNIFY_KINDS = ("19", "51")


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


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """删队长 #4（月牙每层 → 自身 Stunify 25%）；其余 9 行逐字保留、顺序不变。"""
    out = deepcopy(rows)
    if any(len(row) != LEADER_NCOLS for row in out):
        raise ValueError("unexpected leader_ability row width")
    hits = [i for i, row in enumerate(out) if _matches(row, LEADER_NCOLS, REMOVED_LEADER_CELLS)]
    if hits != [REMOVED_LEADER_INDEX]:
        raise ValueError(f"crescent Stunify leader row not found at #{REMOVED_LEADER_INDEX}: {hits}")
    del out[REMOVED_LEADER_INDEX]
    left = [i for i, row in enumerate(out) if row[107] in STUNIFY_KINDS or row[45] in STUNIFY_KINDS]
    if left:
        raise ValueError(f"leader still carries Stunify rows: {left}")
    return out


def ability5_rows(rows: list[list[str]]) -> list[list[str]]:
    """删能力 5 #1（编成直击 ≥50 → 雷队 Stunify 100%）；#0 的充能行与 422/贯通行保留。"""
    out = deepcopy(rows)
    if any(len(row) != ABILITY_NCOLS for row in out):
        raise ValueError("unexpected ability row width")
    hits = [i for i, row in enumerate(out) if _matches(row, ABILITY_NCOLS, REMOVED_ABILITY_CELLS)]
    if hits != [REMOVED_ABILITY_INDEX]:
        raise ValueError(f"direct-hit Stunify ability row not found at #{REMOVED_ABILITY_INDEX}: {hits}")
    del out[REMOVED_ABILITY_INDEX]
    left = [i for i, row in enumerate(out) if row[47] in STUNIFY_KINDS or row[109] in STUNIFY_KINDS]
    if left:
        raise ValueError(f"ability {ABILITY_KEY} still carries Stunify rows: {left}")
    # 同触发的回槽行必须仍在，且自带完整触发块（不依赖被删行）。
    kept = [row for row in out if row[27] == "20" and row[47] == "35"]
    if len(kept) != 1 or kept[0][30:32] != ["5000000", "5000000"] or kept[0][51:53] != ["5000", "5000"]:
        raise ValueError("direct-hit gauge-charge row (kind 35, 5%) must remain intact")
    return out


def _single_text(rows: list[list[str]], key: str) -> str:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError(f"{key}: expected one single-column row")
    return rows[0][0]


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    text = _single_text(rows, CAS_LEADER)
    lines = text.split("\n")
    if len(lines) != 6 or text.count(REMOVED_LEADER_PHRASE) != 1 \
            or REMOVED_LEADER_PHRASE not in lines[LEADER_PANEL_LINE]:
        raise ValueError(f"{CAS_LEADER}: unexpected panel text layout")
    lines[LEADER_PANEL_LINE] = lines[LEADER_PANEL_LINE].replace(REMOVED_LEADER_PHRASE, "")
    return [["\n".join(lines)]]


def ability5_text(rows: list[list[str]]) -> list[list[str]]:
    if _single_text(rows, CAS_ABILITY5) != OLD_ABILITY5_TEXT:
        raise ValueError(f"{CAS_ABILITY5}: unexpected panel text")
    return [[NEW_ABILITY5_TEXT]]


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader = _checked(read, "leader", CID)
    ability = _checked(read, "ability", ABILITY_KEY)
    cas_leader = _checked(read, "cas", CAS_LEADER)
    cas_ability5 = _checked(read, "cas", CAS_ABILITY5)
    return {
        "ability": {ABILITY_KEY: ability5_rows(ability)},
        "leader": {CID: leader_rows(leader)},
        "cas": {CAS_LEADER: leader_text(cas_leader), CAS_ABILITY5: ability5_text(cas_ability5)},
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "plan": "A",
            "source": "wf_balance_20260927_kyle.py",
            "generator": "wf_midautumn_kit_kyle.py（LEADER/PLAN[5]/EXPECT/PANEL_* 已同步）",
            "removed": {
                f"leader_ability:{CID}#{REMOVED_LEADER_INDEX}":
                    "during 134 月牙层数 → 自身 Stunify(19) 每层 +25%",
                f"ability:{ABILITY_KEY}#{REMOVED_ABILITY_INDEX}":
                    "编成直击≥50 → 雷队 Stunify(51) +100%",
            },
            "kept": {
                f"leader_ability:{CID}#8→#7": "贯穿 → 雷队 StunWinceSlayer(53) +5%（面板「追击伤害＋5%」）",
                f"ability:{ABILITY_KEY}#0": "编成直击≥50 → 雷队技能充能 +5%",
            },
            "rows": {"leader": [len(leader), len(leader) - 1],
                     ABILITY_KEY: [len(ability), len(ability) - 1]},
            "panel": {CAS_LEADER: f"第4行去掉「{REMOVED_LEADER_PHRASE[1:]}」",
                      CAS_ABILITY5: NEW_ABILITY5_TEXT},
            "unique_condition_untouched": UID_CRESCENT,
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/kyle.json"
PANEL_REL = BATCH / "rework1/panel/kyle.json"
DEVIATIONS_REL = BATCH / "rework1/panel/_deviations.json"

MIRROR_NOTE = ("2026-09-27：作者平衡批次（方案A）去掉 Down 效果成长——删队长「月牙每层自身"
               "Stunify＋25%」与能力5「每50直击雷队Stunify＋100%」两行，面板同步删去对应文案；"
               "贯穿→雷队追击伤害＋5%（原生眩晕畏缩特攻）保留。")
DEVIATION_VOID = ("2026-09-27 作废：作者平衡批次去掉 Down 效果成长，能力5全队 Stunify 行已删除，"
                  "本条落法不再适用（保留作历史）。")
DOWN_DEVIATION_WORD = "使敌人进入down的容易程度"


def _void_down_deviation(entries: list[dict[str, Any]]) -> None:
    hits = [entry for entry in entries if DOWN_DEVIATION_WORD in entry.get("原话", "")]
    if len(hits) != 1:
        raise ValueError(f"expected exactly one Down deviation entry, got {len(hits)}")
    hits[0]["作废"] = DEVIATION_VOID
    if "ask" in hits[0]:
        hits[0]["ask"] = False


def mirror_updates(design: dict, panel: dict, deviations: dict) -> tuple[dict, dict, dict]:
    """按当前生成器常量重算三份设计镜像（纯函数、幂等）。写法同 09-23 sync-source.py。"""
    import wf_midautumn_kit_kyle as K
    design, panel, deviations = deepcopy(design), deepcopy(panel), deepcopy(deviations)

    mirror = design["plan"]["rework1"]
    mirror["leader"] = [f"{src}:{addr}" for addr, src, _cells, _d in K.LEADER]
    mirror["ability"][ABILITY_KEY] = [f"{src}:{addr}" for addr, src, _cells, _d in K.PLAN[5]]
    stunify = mirror.get("crescent_stunify_20260923")
    if isinstance(stunify, dict):
        stunify.update(revoked="2026-09-27", revoked_by="作者平衡批次：去掉 Down 效果成长（方案A）")
    mirror["down_growth_removed_20260927"] = dict(
        plan="A",
        removed=[f"leader_ability:{CID} 月牙每层自身Stunify 25%",
                 f"ability:{ABILITY_KEY} 每50直击雷队Stunify 100%"],
        kept=[f"leader_ability:{CID} 贯穿→雷队StunWinceSlayer 5%（面板「追击伤害＋5%」）",
              f"ability:{ABILITY_KEY} 每50直击雷队技能充能 5%"],
        module="mod-tools/wf_balance_20260927_kyle.py",
    )
    problems = K._design_problems(design)
    if problems:
        raise ValueError(f"design mirror still drifts: {problems}")

    panel["leader"]["lines"] = [dict(text=line, status="changed")
                                for line in K.PANEL_LEADER.split("\n")]
    for entry in panel["abilities"]:
        slot = int(entry["index"])
        entry["lines"] = [dict(text=line.replace(K.MAIN_ICON, ""), status="changed")
                          for line in K.PANEL_ABILITY[slot].split("\n")]
    notes = [note for note in panel.get("notes", []) if not note.startswith("2026-09-27：作者平衡批次")]
    panel["notes"] = notes + [MIRROR_NOTE]
    _void_down_deviation(panel.get("deviations", []))
    _void_down_deviation(deviations["kyle"])
    return design, panel, deviations


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """indent=2、保留原文件换行风格（这三份镜像在本机是 CRLF，字符串里的换行都被 JSON 转义）。"""
    newline = "\r\n" if b"\r\n" in path.read_bytes() else "\n"
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def sync_mirrors(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回三份设计镜像；返回有变化的相对路径。"""
    root = Path(root)
    paths = (root / DESIGN_REL, root / PANEL_REL, root / DEVIATIONS_REL)
    before = [_load(path) for path in paths]
    after = mirror_updates(*before)
    changed = [str(rel) for rel, old, new in zip((DESIGN_REL, PANEL_REL, DEVIATIONS_REL), before, after)
               if old != new]
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

# -*- coding: utf-8 -*-
"""玛格诺斯「疾风同路」119990 ``lion_swordman_moon``（火）：2026-09-27 平衡第二批——无上限成长（口径 A）。

作用域（作者已拍板口径 ``batch2/第二批施工口径.md`` A 节 + 设计稿 ``growth_design.json`` 119990 + 复核 C06；
修复轮按复核补上口径 B3）：无上限成长（口径 A）+ 「引擎之炎」629 追击的每次削韧（口径 B3/B6，设计稿漏扫）。
疾风同路 PF（队长 #6–#8 的 629 代打 15/20/25 顶格）按口径 B5 保留；充能行（能力 6 自身充能、
能力 5 每 3PF 技能槽 CT、队长 #3 全队技能槽）按口径 A6 / 表二一律不动。

放缓倍率按 3 分钟实际次数（口径 A2，不按事件名称）：

- 「每 3 次强化弹射」：技能能量 600、能力 6 充能 +20%、开局 +50%，约 15–20 秒一发；技能后 10 秒「烈焰光环」
  期间每次弹射 +35 连击（能力 6 PF 所需连击 −5）⇒ 光环期几乎每次弹射都是 Lv3 PF，其余时间约 5 秒一次 ⇒
  3 分钟约 45–70 次 PF ⇒ 触发 15–23 次（≤30）⇒ 每步 ×1/5。
- 「引擎点火每 1 层」：3 分钟获得约 175–230 层（火属性技能 25–30 次 × 1，每 3PF 15–20 次 × (7+3)），
  自身技能命中每 0.6 秒消耗 1 层 ⇒ 常驻 20–60 层、PF 密集时顶到固有上限 99 ⇒ ≥30 ⇒ 每步 ×1/10。
  设计稿写 1/5（理由「每层属低频事件」），与口径 A2「不按事件名称」冲突，按实际层数改判为 1/10，
  写进 ``notes.judgement``（改回 1/5 只需 :data:`LAYER_SELF_LEADER` 10000、:data:`LAYER_TEAM_411_LEADER` 1000）。

改动（其余行、其余列、其余树节点逐字保留）：

1. ``leader_ability:119990``：#1 每 3PF 全队(火)技能伤害 100% → 20%；#2 全队(火)攻击力 50% → 10%；
   末尾追加 4 行（行 = ``[CODE, '0', ''] + 能力行[5:]``，能力 c≥5 → 队长 c−2）：
   #9 ← 能力 1#2 每 3PF 自身技能伤害 5%（复核 C06：与 #1 目标不同，不合并）；
   #10/#11 ← 能力 2#0/#1 点火每层自身技能伤害 / 攻击力 5%；#12 ← 能力 3#4 点火每层全队(火)独立乘区技能伤害 0.5%。
   队长里没有同触发/同 kind/同目标/同前置且无 CT 的行 ⇒ 全部新起一行。9 行 → 13 行（复核 C14：≤13 可接受）。
2. ``ability:1199901#2``：限次 c34 (None) → 4（25%×4 = 100%，设计稿值）。
3. ``ability:1199902#0/#1``：c102 (None) → 10（最多计 10 层，官方 donor 1611231/1611232 原值），c113/c114 50% → 15%。
4. ``ability:1199903#4``：c102 (None) → 10，c113/c114 5% → 1%（整键主位限定 c1=false 保持）。
5. 技能 DSL 6 棵（主技能两档、引擎之炎追击、三档特殊 PF 技能）：根块首条
   ``BindConditionAccumulationVariable(-17, 11999005, DCUnique 11999001, 1, 99)`` 第 5 参 99 → 10。
   客户端 ``ActionEvaluator.as`` case 101 ``bindFloatVariable(vid, min(层数 / 第4参, 第5参))`` ⇒ 点火对
   「每层 +5 倍」的贡献封顶 10 层；vlv/段数/伤害归属不动。无上限部分由队长 #10「点火每层自身技能伤害」承担
   （口径 A5：队长已有同一层数的逐层成长行 ⇒ 视为已合并）。live 先例：wf_gbf_kit_soriz ``(…, 1, 10)``、
   wf_seasonal7_kit_primula ``(…, 1, 20)``。
6. Down（口径 B3/B6）：「引擎之炎」追击树（能力 3#1 的 629，触发 136 自身技能命中、CT 36 帧 = 0.6 秒 ≤3 秒
   ⇒ 每次 ≤1）爆炸判定区 30 帧 / ``CalculatedUsingMaxNumOfHits(5)`` / p15 None ⇒ 单个 boss 吃满 5 段，
   ``CreateNormalAttack`` p13 0.25 → 0.2（每次 1.25 → 1.0，= 官方火龙母本 4 × 0.25）；其余节点逐字保留。
   其余 5 棵树的 p13 不动（主技能 10 + 10 × 1.43 ≈ 24.3 ≤30；三档 PF 15/20/25 顶格，口径 B5 保留）。
7. 面板：``desc_override_lion_swordman_moon``（队长）/``_1``/``_2``/``_3`` 同步。技能描述（action_skill、
   character_text、服务端 character_text）不含点火数值，不改。

生成器 ``wf_midautumn_kit_magnus`` 已同步（LEADER/PLAN/CAS_TEXTS/``ignition_growth``/``CHASE_DOWN``），测试断言生成器输出
== :func:`revise` 输出。设计镜像（design/magnus.json、rework1/panel/magnus.json）由 :func:`sync_mirrors` 幂等同步。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl
import wf_midautumn_kitlib as KL

CID = "119990"
CODE = "lion_swordman_moon"
PACKAGES = ["ma-magnus"]
#: 候选 ``work/character_packs/ma-magnus/package/manifest.json`` 现值 1.0.1 → 下一号。
PACKAGE_VERSION = {"ma-magnus": "1.0.2"}
#: 候选已声明 dash-parameter-v1 / panel-description-override-v2；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选与 live 在本模块读取的 14 项上逐字相同（2026-09-27 只读核对：3 个能力键、队长键、4 个面板键、6 棵 DSL）。
REVIEWED_DRIFT: dict = {}

UID = "11999001"                   # 固有「引擎点火」（99 层 / 99999999 帧，unique_condition 不动）
IGNITION_VARIABLE = 11999005       # DSL vlv 变量号
ELEMENT = 0                        # master/character c3：火（0 基内部元素）
ELEMENT_TOKEN = "Red"
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
MAIN_ICON = " <icon id='main'>  "

A1, A2, A3 = f"{CID}1", f"{CID}2", f"{CID}3"
CAS_LEADER = f"desc_override_{CODE}"
CAS_SLOT = {slot: f"desc_override_{CODE}_{slot}" for slot in (1, 2, 3)}

PROGRAMS = (
    f"battle/action/skill/action/rare5/{CODE}${CODE}_1",
    f"battle/action/skill/action/rare5/{CODE}${CODE}_2",
    f"battle/action/skill/action/ability_skill/ability_skill_{CODE}_ignite$ability_skill_{CODE}_ignite",
    *(f"battle/action/skill/action/ability_skill/{CODE}_pf_skill${CODE}_pf_skill_lv{n}" for n in (1, 2, 3)),
)

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数，与候选 ma-magnus 1.0.1 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", CID): "8055445c4b8c0a895ec33b89ae9218fd3e25272800eb443e5d2a909ff66a8ce7",
    ("ability", A1): "63fec46cdf7cd017899699628fd3de3ac2ae372dd33ee7a05bad37cf18cc0591",
    ("ability", A2): "9112be16277a095b34bc7539e2c02b28d02996b22a3aedec52a80bf6a08abc19",
    ("ability", A3): "7ca77ceb05537ed1b43b96289f2d38852d8d7270378e391f53a4f4daf64372a9",
    ("cas", CAS_LEADER): "78bd8dc6e3289b3da7ae3f3912a583a01fb3c7ffac1e1c00b945bc8c32d78efe",
    ("cas", CAS_SLOT[1]): "6273cf959cf409cc88479b29f965a6b5ac7050f21aa39fd291c6db989f7f3af9",
    ("cas", CAS_SLOT[2]): "b27e66b0ef2a0e265926a3347408f7ebecf1876e7b92f5476e3bad7763a93269",
    ("cas", CAS_SLOT[3]): "95a95b0792009e0d9866d368ae4172bf27315e868c7e2c26fe63349f5d3b6e94",
    ("dsl", PROGRAMS[0]): "ced08d7eeb24b0dd2c8bb98caa0a33b9e5b00aa10c75adf31c24f15c030ec221",
    ("dsl", PROGRAMS[1]): "67e9ec96036f3c3ce6c9e61c0fdfc8baed81e37ffa5065a71ef7596286bc970a",
    ("dsl", PROGRAMS[2]): "331feac194c4531ab02d5e80dff0748bfb2043c3f409c7a6a5fed89d36eb5d90",
    ("dsl", PROGRAMS[3]): "28deed1fb80c0054bf79d8992142d52e7ce8f38d3743cb7f8dbdf2ca5909c7e0",
    ("dsl", PROGRAMS[4]): "708b301ce17e8ae11f2edaa851ae062b40cf8dcf11b6aacc4b67c4322a59d53c",
    ("dsl", PROGRAMS[5]): "1111ab92668acc4f3f9af8bfa5b0fd1572042be06b17cb3ef357a6ccbfd4ee53",
}

# ------------------------------------------------------------------ 数值（改前 → 改后）

PF3_TEAM_SKILL_DAMAGE = ("100000", "20000")   # 队长 #1：×1/5
PF3_TEAM_ATTACK = ("50000", "10000")          # 队长 #2：×1/5
PF3_SELF_SKILL_DAMAGE_LEADER = "5000"         # 队长 #9 ← 能力 1#2 的 25%×1/5
LAYER_SELF_LEADER = "5000"                    # 队长 #10/#11 ← 能力 2 的 50%×1/10
LAYER_TEAM_411_LEADER = "500"                 # 队长 #12 ← 能力 3#4 的 5%×1/10
PF3_SELF_LIMIT = ("(None)", "4")              # 能力 1#2 c34
LAYER_LIMIT = ("(None)", "10")                # 能力 2#0/#1、能力 3#4 c102
LAYER_SELF_ABILITY = ("50000", "15000")       # 能力 2#0/#1 c113/c114
LAYER_TEAM_411_ABILITY = ("5000", "1000")     # 能力 3#4 c113/c114
DSL_LAYER_CAP = (99, 10)                      # BindConditionAccumulationVariable 第 5 参
#: 口径 B3/B6（复核补漏）：「引擎之炎」629 追击（能力 3#1，触发 136，CT c35 = 36 帧 = 0.6 秒 ≤3 秒）
#: 每次单目标削韧 ≤1。爆炸判定区 CalculatedUsingMaxNumOfHits(5) + p15 None ⇒ 单个 boss 吃满 5 段。
CHASE_PROGRAM = PROGRAMS[2]
CHASE_DOWN = (0.25, 0.2)                      # CreateNormalAttack p13（SLv min/max 都改）
CHASE_HITS = (1, 5)                           # 外层（挂球、Some 1 ⇒ 每次只引爆一次）× 爆炸判定区
CHASE_DOWN_CAP = 1.0                          # 5 × 0.25 = 1.25 → 5 × 0.2 = 1.0
CHASE_TRIGGER_CT = ("136", "36")              # 能力 3#1 c27 触发 / c35 CT（帧），用于核对 B3 适用
DOWN_SLOT = 13                                # CreateNormalAttack node[13] = 参数卡 p13 削韧（node[14] = Fever 点）

# ------------------------------------------------------------------ 行指纹（全部非空列；其余列必须为空）

_FIRE_LEADER = {4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN}
_PF3_LEADER = {0: CODE, 1: "0", 3: "0", **_FIRE_LEADER, 11: "0", 18: "0", 25: "2", 28: "300000",
               29: "300000", 32: "(None)", 33: "0", 37: "(None)", 44: "0"}
LEADER_TEAM_SKILL_BEFORE = {**_PF3_LEADER, 45: "34", 46: "5", 47: ELEMENT_TOKEN,
                            49: PF3_TEAM_SKILL_DAMAGE[0], 50: PF3_TEAM_SKILL_DAMAGE[0]}
LEADER_TEAM_ATTACK_BEFORE = {**_PF3_LEADER, 45: "32", 46: "5", 47: ELEMENT_TOKEN,
                             49: PF3_TEAM_ATTACK[0], 50: PF3_TEAM_ATTACK[0]}
LEADER_ROWS_BEFORE = 9
LEADER_TEAM_SKILL_ROW, LEADER_TEAM_ATTACK_ROW = 1, 2

_FIRE_ABILITY = {6: "2", 9: "600000", 10: "600000", 11: ELEMENT_TOKEN}
A1_ROW = 2
A1_BEFORE = {0: f"{CODE}_1", 1: "true", 2: "action_skill", 3: "0", 5: "0", **_FIRE_ABILITY, 13: "0",
             20: "0", 27: "2", 30: "300000", 31: "300000", 34: PF3_SELF_LIMIT[0], 35: "0", 39: "(None)",
             46: "0", 47: "34", 48: "0", 51: "25000", 52: "25000"}
_LAYER_SELF = {1: "true", 2: "action_skill", 3: "0", 5: "1", **_FIRE_ABILITY, 13: "0", 20: "0",
               85: "(None)", 97: "134", 98: "0", 100: "100000", 101: "100000", 102: LAYER_LIMIT[0],
               104: UID, 108: "false", 110: "0",
               113: LAYER_SELF_ABILITY[0], 114: LAYER_SELF_ABILITY[0]}
A2_BEFORE = ({0: f"{CODE}_2", **_LAYER_SELF, 109: "2"},      # #0 自身技能伤害
             {0: f"{CODE}_2", **_LAYER_SELF, 109: "0"})      # #1 自身攻击力
A3_ROW = 4
A3_BEFORE = {0: f"{CODE}_3", 1: "false", 2: "action_skill", 3: "0", 5: "1", 6: "0", 13: "0", 20: "0",
             85: "(None)", 97: "134", 98: "0", 100: "100000", 101: "100000", 102: LAYER_LIMIT[0],
             104: UID, 108: "false", 109: "411", 110: "5", 111: ELEMENT_TOKEN,
             113: LAYER_TEAM_411_ABILITY[0], 114: LAYER_TEAM_411_ABILITY[0]}

BIND_BEFORE = ["BindConditionAccumulationVariable", -17, IGNITION_VARIABLE,
               ["DCUnique", int(UID)], 1, DSL_LAYER_CAP[0]]

# ------------------------------------------------------------------ 面板（改前 → 改后，按行）

OLD_LEADER_LINE = "火属性共鸣时，每发动3次强化弹射，火属性角色技能伤害＋100%、攻击力＋50%"
NEW_LEADER_LINE = "火属性共鸣时，每发动3次强化弹射，火属性角色技能伤害＋20%、攻击力＋10%"
LEADER_SELF_LINE = "火属性共鸣时，每发动3次强化弹射，自身技能伤害＋5%"
LEADER_LAYER_LINES = ("火属性共鸣时，引擎点火每提升1层，自身技能伤害＋5%、攻击力＋5%",
                      "自身引擎点火每提升1层，火属性角色技能伤害额外乘区＋0.5%")
AURA_LINE = "自身持有「烈焰光环」期间，每次弹射，连击＋35"
LEADER_PANEL_LINES = (7, 10)

OLD_SLOT1_LINES = ("战斗开始时，自身技能槽＋50%",
                   "火属性共鸣时，强化自身技能：光环范围扩大，自身技能伤害随强化弹射次数按层叠加提升",
                   "自身引擎点火每提升1层，技能基础总倍率＋5倍（含引擎之炎及特殊强化弹射）")
NEW_SLOT1_LINES = ("战斗开始时，自身技能槽＋50%",
                   "火属性共鸣时，强化自身技能：光环范围扩大",
                   "火属性共鸣时，每发动3次强化弹射，自身技能伤害＋25%（最多4次）",
                   "自身引擎点火每提升1层，技能基础总倍率＋5倍（含引擎之炎及特殊强化弹射，最多10层）")
SLOT1_SKILL_FLAG_LINE = 1          # 536 条目：不写数字与时间

OLD_SLOT2 = "火属性共鸣时，引擎点火每提升1层，自身技能伤害＋50%、攻击力＋50%"
NEW_SLOT2 = "火属性共鸣时，引擎点火每提升1层，自身技能伤害＋15%、攻击力＋15%（最多10层）"

SLOT3_LINE = 4
OLD_SLOT3_LINE = MAIN_ICON + "自身引擎点火每提升1层，火属性角色技能伤害额外乘区＋5%"
NEW_SLOT3_LINE = MAIN_ICON + "自身引擎点火每提升1层，火属性角色技能伤害额外乘区＋1%（最多10层）"
SLOT3_LINES = 6


class MagnusBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise MagnusBalanceError(f"unreviewed live baseline for {kind}:{key} "
                                 f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise MagnusBalanceError(message)


def _only_changed(before: list[list[str]], after: list[list[str]], index: int,
                  cols: tuple[int, ...]) -> None:
    """自检：只动了 ``before[index]`` 的 ``cols`` 列。"""
    changed = [(i, c) for i, (a, b) in enumerate(zip(before, after))
               for c, (x, y) in enumerate(zip(a, b)) if x != y]
    if not changed or {i for i, _c in changed} != {index} or not {c for _i, c in changed} <= set(cols):
        raise AssertionError(f"touched cells {changed} beyond #{index} c{cols}")


def leader_from_ability(row: list[str], strength_cols: tuple[int, int], value: str) -> list[str]:
    """能力行 → 队长行：``[CODE, '0', ''] + row[5:]``（能力 c≥5 → 队长 c−2），再改强度两列。"""
    _require(len(row) == ABILITY_NCOLS, f"ability row width {len(row)} != {ABILITY_NCOLS}")
    out = [CODE, "0", ""] + deepcopy(row[5:])
    _require(len(out) == LEADER_NCOLS, f"leader row width {len(out)} != {LEADER_NCOLS}")
    for col in strength_cols:
        out[col] = value
    return out


def moved_leader_rows(a1: list[list[str]], a2: list[list[str]], a3: list[list[str]]) -> list[list[str]]:
    """从**改前**能力行转置出的 4 条队长新行（#9–#12）。"""
    _require(_matches(a1[A1_ROW], ABILITY_NCOLS, A1_BEFORE), f"ability {A1}#{A1_ROW} drifted")
    for index, cells in enumerate(A2_BEFORE):
        _require(_matches(a2[index], ABILITY_NCOLS, cells), f"ability {A2}#{index} drifted")
    _require(_matches(a3[A3_ROW], ABILITY_NCOLS, A3_BEFORE), f"ability {A3}#{A3_ROW} drifted")
    return [
        leader_from_ability(a1[A1_ROW], (49, 50), PF3_SELF_SKILL_DAMAGE_LEADER),
        leader_from_ability(a2[0], (111, 112), LAYER_SELF_LEADER),
        leader_from_ability(a2[1], (111, 112), LAYER_SELF_LEADER),
        leader_from_ability(a3[A3_ROW], (111, 112), LAYER_TEAM_411_LEADER),
    ]


def leader_rows(rows: list[list[str]], a1: list[list[str]], a2: list[list[str]],
                a3: list[list[str]]) -> list[list[str]]:
    """队长 #1/#2 放缓（×1/5），末尾追加 4 条搬入行；#0、#3–#8 逐字不动。"""
    _require(len(rows) == LEADER_ROWS_BEFORE, f"leader {CID}: expected {LEADER_ROWS_BEFORE} rows, got {len(rows)}")
    _require(all(len(row) == LEADER_NCOLS for row in rows), f"leader {CID}: unexpected row width")
    _require(_matches(rows[LEADER_TEAM_SKILL_ROW], LEADER_NCOLS, LEADER_TEAM_SKILL_BEFORE),
             f"leader {CID}#{LEADER_TEAM_SKILL_ROW} (每3PF 全队技伤 100%) drifted")
    _require(_matches(rows[LEADER_TEAM_ATTACK_ROW], LEADER_NCOLS, LEADER_TEAM_ATTACK_BEFORE),
             f"leader {CID}#{LEADER_TEAM_ATTACK_ROW} (每3PF 全队攻 50%) drifted")
    _require(not [r for r in rows if r[95] == "134" and r[102] == UID],
             f"leader {CID} already carries ignition per-layer rows")
    out = deepcopy(rows)
    out[LEADER_TEAM_SKILL_ROW][49] = out[LEADER_TEAM_SKILL_ROW][50] = PF3_TEAM_SKILL_DAMAGE[1]
    out[LEADER_TEAM_ATTACK_ROW][49] = out[LEADER_TEAM_ATTACK_ROW][50] = PF3_TEAM_ATTACK[1]
    for index in range(LEADER_ROWS_BEFORE):
        if index not in (LEADER_TEAM_SKILL_ROW, LEADER_TEAM_ATTACK_ROW):
            _require(out[index] == rows[index], f"leader #{index} touched")
    return out + moved_leader_rows(a1, a2, a3)


def ability1_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力 1#2：限次 (None) → 4；#0（开局 50%）、#1（536）逐字不动。"""
    _require(len(rows) == 3 and all(len(r) == ABILITY_NCOLS for r in rows), f"ability {A1}: expected 3×126")
    _require(_matches(rows[A1_ROW], ABILITY_NCOLS, A1_BEFORE), f"ability {A1}#{A1_ROW} drifted")
    out = deepcopy(rows)
    out[A1_ROW][34] = PF3_SELF_LIMIT[1]
    _only_changed(rows, out, A1_ROW, (34,))
    return out


def ability2_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力 2 两行：每层 50% 不限层 → 每层 15% 最多计 10 层。"""
    _require(len(rows) == 2 and all(len(r) == ABILITY_NCOLS for r in rows), f"ability {A2}: expected 2×126")
    out = deepcopy(rows)
    for index, cells in enumerate(A2_BEFORE):
        _require(_matches(rows[index], ABILITY_NCOLS, cells), f"ability {A2}#{index} drifted")
        out[index][102] = LAYER_LIMIT[1]
        out[index][113] = out[index][114] = LAYER_SELF_ABILITY[1]
    for index in range(2):
        _only_changed([rows[index]], [out[index]], 0, (102, 113, 114))
    return out


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力 3#4：每层全队独立乘区 5% 不限层 → 1% 最多计 10 层；其余 5 行（含 629/525 顺序）逐字不动。"""
    _require(len(rows) == 6 and all(len(r) == ABILITY_NCOLS for r in rows), f"ability {A3}: expected 6×126")
    _require([r[47] if r[5] == "0" else r[109] for r in rows] == ["461", "629", "525", "411", "411", "461"],
             f"ability {A3}: record kinds drifted")
    chase = rows[1]
    _require((chase[27], chase[35], chase[71]) == (*CHASE_TRIGGER_CT, CHASE_PROGRAM),
             f"ability {A3}#1 (629 引擎之炎) trigger/CT/program drifted: "
             f"{(chase[27], chase[35], chase[71])} — 口径 B3 的 CT≤3 秒判定要重核")
    _require(_matches(rows[A3_ROW], ABILITY_NCOLS, A3_BEFORE), f"ability {A3}#{A3_ROW} drifted")
    out = deepcopy(rows)
    out[A3_ROW][102] = LAYER_LIMIT[1]
    out[A3_ROW][113] = out[A3_ROW][114] = LAYER_TEAM_411_ABILITY[1]
    _only_changed(rows, out, A3_ROW, (102, 113, 114))
    return out


def _single_text(rows: list[list[str]], key: str) -> str:
    _require(len(rows) == 1 and len(rows[0]) == 1, f"{key}: expected one single-column row")
    return rows[0][0]


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    """第 4 行放缓；其后插入「自身技能伤害＋5%」；「烈焰光环」行之前插入点火逐层两行。"""
    lines = _single_text(rows, CAS_LEADER).split("\n")
    _require(len(lines) == LEADER_PANEL_LINES[0] and lines[3] == OLD_LEADER_LINE and lines[-1] == AURA_LINE,
             f"{CAS_LEADER}: unexpected panel text layout")
    new = lines[:3] + [NEW_LEADER_LINE, LEADER_SELF_LINE] + lines[4:-1] + list(LEADER_LAYER_LINES) + [AURA_LINE]
    _require(len(new) == LEADER_PANEL_LINES[1], "leader panel line count")
    return [["\n".join(new)]]


def slot1_text(rows: list[list[str]]) -> list[list[str]]:
    _require(tuple(_single_text(rows, CAS_SLOT[1]).split("\n")) == OLD_SLOT1_LINES,
             f"{CAS_SLOT[1]}: unexpected panel text")
    return [["\n".join(NEW_SLOT1_LINES)]]


def slot2_text(rows: list[list[str]]) -> list[list[str]]:
    _require(_single_text(rows, CAS_SLOT[2]) == OLD_SLOT2, f"{CAS_SLOT[2]}: unexpected panel text")
    return [[NEW_SLOT2]]


def slot3_text(rows: list[list[str]]) -> list[list[str]]:
    lines = _single_text(rows, CAS_SLOT[3]).split("\n")
    _require(len(lines) == SLOT3_LINES and lines[SLOT3_LINE] == OLD_SLOT3_LINE,
             f"{CAS_SLOT[3]}: unexpected panel text layout")
    _require(all(line.startswith(MAIN_ICON) for line in lines),
             f"{CAS_SLOT[3]}: main-position slot lines must start with the main icon")
    lines[SLOT3_LINE] = NEW_SLOT3_LINE
    return [["\n".join(lines)]]


def panel_problems(texts: dict[str, str]) -> list[str]:
    """口径 D 面板规则：kitlib 禁语、536 条目无数字、主位槽每行带图标、不用「／」分行。"""
    problems: list[str] = []
    for key, text in texts.items():
        if "／" in text:
            problems.append(f"{key}: uses ／ as a line separator")
        for index, line in enumerate(text.split("\n")):
            flag = key == CAS_SLOT[1] and index == SLOT1_SKILL_FLAG_LINE
            problems += [f"{key}#{index}: {p}" for p in
                         KL.panel_problems(line.replace(MAIN_ICON, ""), skill_flag=flag)]
            if (key == CAS_SLOT[3]) != line.startswith(MAIN_ICON):
                problems.append(f"{key}#{index}: main icon must appear exactly on the main-only slot 3")
    return problems


def row_gate_problems(kind: str, row: list[str], cas_keys: set[str]) -> list[str]:
    """口径 D 词条门禁：合法性 / 声明块字段 / 629 文案键 / capability / 元素列。"""
    table = "leader_ability" if kind == "leader" else "ability"
    problems = [f"legality: {p}" for p in L.client_legality_problems(table, row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems(table, row)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, cas_keys, kind=table)]
    problems += [f"kitlib {name}: {p}" for name, found in KL.row_problems(table, row, ELEMENT).items()
                 for p in found]
    caps = L.required_client_capabilities(table, row)
    if caps and set(caps) - {"dash-parameter-v1"}:
        problems.append(f"capabilities {caps}")
    return problems


# ------------------------------------------------------------------ DSL

def _slv(value: float) -> list[dict[str, float]]:
    return [{"min": value, "max": value}]


def chase_burst(tree) -> tuple[list, list, list]:
    """追击树结构核对：``(外层挂球判定区, 爆炸判定区, 唯一的 CreateNormalAttack)``（节点引用，可就地改）。

    外层：挂球（-18）、``CalculatedUsingMaxNumOfHits(1)`` + p15 ``Some 1`` ⇒ 每次发动只引爆一次；
    爆炸：寿命 30 帧、``CalculatedUsingMaxNumOfHits(5)``、p15 None（无每目标硬上限）⇒ 单目标吃满 5 段；
    CNA 直接挂在爆炸判定区的命中块（p23）里。任一处不符 ⇒ 拒绝（段数变了，削韧账要重算）。
    """
    attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    areas = list(wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))
    _require(len(attacks) == 1 and len(areas) == 2,
             f"chase tree shape drift: {len(areas)} hit areas / {len(attacks)} attacks")
    cna = attacks[0]
    bursts = [a for a in areas if any(node == ["Command", cna] and node[1] is cna for node in a[23][1])]
    _require(len(bursts) == 1, "chase CreateNormalAttack must sit directly in one hit area's on-hit block")
    burst = bursts[0]
    outer = next(a for a in areas if a is not burst)
    _require(any(inner is burst for inner in wf_dsl.iter_dsl_commands(outer, "CreateHitArea")),
             "chase burst must be nested inside the ball hit area")
    _require((outer[2], outer[14], outer[15]) ==
             (-18, ["CalculatedUsingMaxNumOfHits", CHASE_HITS[0]], ["Some", _slv(CHASE_HITS[0])]),
             f"chase ball hit area drift: {(outer[2], outer[14], outer[15])}")
    _require((burst[13], burst[14], burst[15]) ==
             (["SpecifyHitAreaLifetimeDirectly", 30], ["CalculatedUsingMaxNumOfHits", CHASE_HITS[1]], ["None"]),
             f"chase burst hit accounting drift: {(burst[13], burst[14], burst[15])}")
    return outer, burst, cna


def chase_down_per_activation(tree) -> float:
    """每次发动单目标削韧上界 = 外层引爆次数 × 爆炸段数 × p13（取 SLv 端点最大值）。"""
    _outer, _burst, cna = chase_burst(tree)
    per_hit = max(max(float(slv["min"]), float(slv["max"])) for slv in cna[DOWN_SLOT])
    return CHASE_HITS[0] * CHASE_HITS[1] * per_hit


def revise_tree(tree, program: str) -> list:
    """根块首条点火绑定的第 5 参 99 → 10；追击树另把 CNA p13 0.25 → 0.2；其余节点逐字不动。"""
    out = deepcopy(tree)
    _require(isinstance(out, list) and out and out[0] == "ActionDsl" and out[10] == 0,
             f"{program}: unexpected root (buffTargetAs must stay 0 = skill damage)")
    binds = list(wf_dsl.iter_dsl_commands(out, "BindConditionAccumulationVariable"))
    _require(binds == [BIND_BEFORE], f"{program}: ignition binding drifted: {binds}")
    head = out[11][1][0]
    _require(head == ["Command", BIND_BEFORE], f"{program}: ignition binding is not the root's first command")
    users = [attack[6][0].get("vlv") for attack in wf_dsl.iter_dsl_commands(out, "CreateNormalAttack")]
    _require(users and all(v and [x["vid"] for x in v] == [IGNITION_VARIABLE] for v in users),
             f"{program}: every CreateNormalAttack must scale with the ignition variable")
    head[1][5] = DSL_LAYER_CAP[1]
    if program == CHASE_PROGRAM:
        cna = chase_burst(out)[2]
        _require(cna[DOWN_SLOT] == _slv(CHASE_DOWN[0]), f"{program}: CNA p13 preimage drift: {cna[DOWN_SLOT]}")
        cna[DOWN_SLOT] = _slv(CHASE_DOWN[1])
        per_activation = chase_down_per_activation(out)
        _require(per_activation <= CHASE_DOWN_CAP,
                 f"{program}: detoughness per activation {per_activation} > {CHASE_DOWN_CAP}")
    after = deepcopy(out)
    after[11][1][0][1][5] = DSL_LAYER_CAP[0]
    if program == CHASE_PROGRAM:
        chase_burst(after)[2][DOWN_SLOT] = _slv(CHASE_DOWN[0])
    if after != tree:
        raise AssertionError(f"{program}: touched more than the binding cap / chase p13")
    return out


def dsl_gate_problems(tree) -> list[str]:
    """口径 D 四道 DSL 门 + AMF3 往返。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


# ------------------------------------------------------------------ 入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader = _checked(read, "leader", CID)
    a1 = _checked(read, "ability", A1)
    a2 = _checked(read, "ability", A2)
    a3 = _checked(read, "ability", A3)
    cas = {key: _checked(read, "cas", key) for key in (CAS_LEADER, *CAS_SLOT.values())}
    trees = {program: _checked(read, "dsl", program) for program in PROGRAMS}

    new_leader = leader_rows(leader, a1, a2, a3)
    ability = {A1: ability1_rows(a1), A2: ability2_rows(a2), A3: ability3_rows(a3)}
    texts = {CAS_LEADER: leader_text(cas[CAS_LEADER]), CAS_SLOT[1]: slot1_text(cas[CAS_SLOT[1]]),
             CAS_SLOT[2]: slot2_text(cas[CAS_SLOT[2]]), CAS_SLOT[3]: slot3_text(cas[CAS_SLOT[3]])}

    problems = panel_problems({key: rows[0][0] for key, rows in texts.items()})
    cas_keys = {f"override_string_{CODE}_pf", f"ability_skill_{CODE}_ignite", f"change_skill_{CODE}"}
    for index, row in enumerate(new_leader):
        problems += [f"leader#{index}: {p}" for p in row_gate_problems("leader", row, cas_keys)]
    for key, rows in ability.items():
        for index, row in enumerate(rows):
            problems += [f"{key}#{index}: {p}" for p in row_gate_problems("ability", row, cas_keys)]
    new_trees = {}
    for program, tree in trees.items():
        new_trees[program] = revise_tree(tree, program)
        problems += [f"{program}: {p}" for p in dsl_gate_problems(new_trees[program])]
    if problems:
        raise MagnusBalanceError(f"revision rejected: {problems}")

    return {
        "leader": {CID: new_leader},
        "ability": ability,
        "cas": texts,
        "text": {}, "table": {}, "action": {}, "server_text": {},
        "dsl": new_trees,
        "new_programs": [],
        "notes": _notes(len(leader), len(new_leader)),
    }


def _notes(before_rows: int, after_rows: int) -> dict[str, Any]:
    return {
        "source": "wf_balance_20260927b_magnus.py",
        "character": f"{CID} {CODE} 玛格诺斯「疾风同路」（火）",
        "scope": "口径 A（无上限成长）＋ 口径 B3/B6（「引擎之炎」629 追击每次削韧 ≤1，修复轮按复核补上，设计稿漏扫）；"
                 "疾风同路 PF（629 代打 15/20/25 顶格）按口径 B5 保留；"
                 "充能行（能力 6 自身充能 20%、能力 5#1 每 3PF 技能槽 CT5 秒、队长 #3 全队技能槽 5%）按口径 A6 不动",
        "frequency_3min": {
            "pf3": "技能约 15–20 秒一发；光环 10 秒内每次弹射 +35 连击 ⇒ 几乎每次弹射都是 Lv3 PF；3 分钟约 45–70 次 PF "
                   "⇒「每 3 次强化弹射」15–23 次（≤30）⇒ ×1/5",
            "ignition_layer": "3 分钟获得约 175–230 层（火属性技能 25–30 次 ×1、每 3PF 15–20 次 ×(7+3)），自身技能命中每 "
                              "0.6 秒消耗 1 层 ⇒ 常驻 20–60 层、PF 密集时顶到 99 ⇒ ≥30 ⇒ ×1/10",
        },
        "judgement": "设计稿把点火逐层按「每层属低频事件」取 1/5；口径 A2 要求按 3 分钟实际次数、不按事件名称，"
                     "点火常驻层数与累计获得层数都 ≥30 ⇒ 本批取 1/10（队长每层自身技伤/攻 5%、全队独立乘区 0.5%）。"
                     "如作者维持设计稿 1/5：队长 #10/#11 c111/c112 改 10000、#12 改 1000，面板两行同步",
        "author_summary": "【给作者】方案表（第二批方案-待拍板.md 玛格诺斯行）写点火每层 自身技伤/攻 50→10%、火队独立技伤 5→1%"
                          "（×1/5）；实装按口径 A2 实际次数取 ×1/10 ⇒ 队长每层 5% / 5% / 0.5%。改回 1/5 只动 4 个常量："
                          "kit 与本模块 LAYER_SELF_LEADER=10000、LAYER_TEAM_411_LEADER=1000，队长面板两行 10%/1%。"
                          "另：「引擎之炎」追击每段削韧 0.25→0.2（每次 1.25→1.0，口径 B3），不在原方案表里",
        "changes": {
            f"leader_ability:{CID}#1 c49/c50": "100000 → 20000（每3PF 全队(火)技能伤害 100%→20%，×1/5）",
            f"leader_ability:{CID}#2 c49/c50": "50000 → 10000（每3PF 全队(火)攻击力 50%→10%，×1/5）",
            f"leader_ability:{CID}#9 (新)": f"← ability:{A1}#{A1_ROW} 每3PF 自身技能伤害 25%×1/5 = 5%（复核 C06 另起自身行）",
            f"leader_ability:{CID}#10 (新)": f"← ability:{A2}#0 点火每层自身技能伤害 50%×1/10 = 5%，不限层",
            f"leader_ability:{CID}#11 (新)": f"← ability:{A2}#1 点火每层自身攻击力 50%×1/10 = 5%，不限层",
            f"leader_ability:{CID}#12 (新)": f"← ability:{A3}#{A3_ROW} 点火每层全队(火)独立乘区技能伤害 5%×1/10 = 0.5%，"
                                             "不限层、无前置（原行无前置）",
            f"ability:{A1}#{A1_ROW} c34": "(None) → 4（每3PF 自身技能伤害 25%，最多 4 次 = 100%）",
            f"ability:{A2}#0/#1 c102,c113/c114": "(None) → 10；50000 → 15000（点火每层自身技伤/攻 15%，最多计 10 层）",
            f"ability:{A3}#{A3_ROW} c102,c113/c114": "(None) → 10；5000 → 1000（点火每层全队独立乘区 1%，最多计 10 层）",
            "dsl ×6 root[0] BindConditionAccumulationVariable p5": "99 → 10（点火每层 +5 倍基础倍率封顶 10 层）",
            f"dsl {CHASE_PROGRAM} CreateNormalAttack p13": f"{CHASE_DOWN[0]} → {CHASE_DOWN[1]}（SLv min/max；"
                                                          f"外层 {CHASE_HITS[0]} 次 × 爆炸 {CHASE_HITS[1]} 段 ⇒ 每次 "
                                                          f"{CHASE_HITS[1] * CHASE_DOWN[0]} → {CHASE_HITS[1] * CHASE_DOWN[1]}）",
        },
        "down": {
            "rule": "口径 B3：能力调用技能（629）每次 ≤3，触发 CT ≤3 秒的每次 ≤1；B6：只改 CreateNormalAttack p13",
            "chase_trigger": f"ability:{A3}#1 c27={CHASE_TRIGGER_CT[0]}（自身技能命中）c35={CHASE_TRIGGER_CT[1]} 帧 = 0.6 秒 ≤3 秒 ⇒ ≤1",
            "chase_hits": "外层挂球判定区 CalculatedUsingMaxNumOfHits(1)+Some 1 ⇒ 每次只引爆一次；爆炸判定区寿命 30 帧、"
                          "CalculatedUsingMaxNumOfHits(5)（间隔 30/4.5≈6.7 帧）、p15 None 无每目标硬上限 ⇒ 单个 boss 吃满 5 段",
            "chase": f"{CHASE_HITS[1]} × {CHASE_DOWN[0]} = {CHASE_HITS[1] * CHASE_DOWN[0]} → "
                     f"{CHASE_HITS[1]} × {CHASE_DOWN[1]} = {CHASE_HITS[1] * CHASE_DOWN[1]}；"
                     "官方母本 ability_skill_fire_dragon_zenith 是 4 × 0.25 = 1.0（rework 把段数抬到 5 才超）",
            "kept": "疾风同路 PF（队长 #6–#8 629，lv1/2/3 = 3×5 / 4×5 / 4×6.25 = 15/20/25 顶格）口径 B5 保留；"
                    "主技能 _1/_2 每次 10 + 10×1.43 ≈ 24.3 ≤30（B1 名单外，不动）",
            "design_gap": "down_design / down_scan 未扫 119990 的追击树（B3 的 CT≤3 秒收紧晚于扫描）；独立复核指出，修复轮补上",
        },
        "rows": {"leader": [before_rows, after_rows]},
        "leader_precedents": {
            "#9 instant 2→34 target 0": "官方 111183#1 同形（target 改 0）；自身行先例 = 本队长 #4（461 target 0）",
            "#10 during 134→2 target 0": "官方 161063#3",
            "#11 during 134→0 target 0": "官方 161063#2",
            "#12 during 134→411 target 5": "形状 = 官方 161123#0（134→0 target 5）；411 队长表官方 0 行、live 先例特克托 "
                                           "139993#2（134→411 target 0），口径 A4 列名放行；LeaderAbilityValues.parseAt107 "
                                           "原生 case \"411\" = SeparatedTermSkillDamage{target: parseAt108, strength: parseAt111}",
        },
        "ability_cap_precedent": "c102 = 10 与官方 donor 1611231#1 / 1611232#0（134 每层、限 10 次）原值相同",
        "dsl_cap_evidence": {
            "client": "ActionEvaluator.as case 101：bindFloatVariable(p2, min(getConditionAccumulationCount / p4, p5))",
            "live_precedents": ["wf_gbf_kit_soriz BindConditionAccumulationVariable(-17, 2, DCUnique, 1, 10)",
                                "wf_seasonal7_kit_primula BindConditionAccumulationVariable(-17, 1, DCUnique, 1, 20)"],
            "unlimited_part": "队长 #10 点火每层自身技能伤害（口径 A5：同一层数的逐层成长行已在队长 ⇒ 视为已合并）",
        },
        "panel": {
            CAS_LEADER: "第4行放缓；插入「自身技能伤害＋5%」；「烈焰光环」行前插入点火逐层两行（7 → 10 行）",
            CAS_SLOT[1]: "536 行去掉按层叠加子句；新增「每3PF 自身技能伤害＋25%（最多4次）」；DSL 行加「最多10层」",
            CAS_SLOT[2]: NEW_SLOT2,
            CAS_SLOT[3]: f"第{SLOT3_LINE + 1}行 → {NEW_SLOT3_LINE.strip()}",
        },
        "unchanged": {
            "skill_description": "action_skill / character_text / 服务端 character_text 不含点火数值，不改",
            "unique_condition": f"{UID} 引擎点火 99 层 / 99999999 帧不动（层数本身不是加成）",
            "kept_rows": f"队长 #0 #3–#8；能力 {A1}#0/#1、{A3}#0–#3/#5、{CID}4/5/6 全键",
        },
        "generator": "wf_midautumn_kit_magnus.py（LEADER #1/#2 数值 + 追加 #9–#12、PLAN[1]/[2]/[3]、CAS_TEXTS、"
                     "ignition_growth 封顶 IGNITION_DSL_CAP=10、build_chase_tree 追击 p13 CHASE_DOWN=0.2）",
        "capabilities": list(CAPABILITIES),
        "open_points": [
            "真机验收：角色详情页（队长 13 行含 134→411 target 5 新组合）不崩；点火 >10 层后技能倍率不再随层增长",
            "test_midautumn_kit_magnus.PackageIntegrationTests.test_package_leader_table_carries_the_ball_flip_combo_row "
            "比对候选包队长行数（9）与 kit（13），候选由暂存脚本回写后转绿（本单元不许跑 stage；"
            "暂存跳过时由主会话登记到 当前状态.md）",
            "真机验收：「引擎之炎」追击每次对 boss 的虚弱累积 = 1.0（5 段 × 0.2）",
        ],
        "runtime_verified": False,
    }


# ------------------------------------------------------------------ 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/magnus.json"
PANEL_REL = BATCH / "rework1/panel/magnus.json"

MIRROR_TAG = "balance_20260927b"
MIRROR_NOTE = ("2026-09-27：平衡第二批（口径 A 无上限成长）——每3次强化弹射 火队技伤/攻 100%/50%→20%/10%，"
               "自身技伤另起队长行 5%（能力1 该行限4次）；引擎点火每层 自身技伤/攻 队长 5%（能力2 改 15%、最多10层）、"
               "火队独立乘区 队长 0.5%（能力3 改 1%、最多10层）；技能点火倍率封顶 10 层。面板同步。"
               "口径 B3：「引擎之炎」追击每段削韧 0.25→0.2（5 段每次 1.25→1.0），面板不写削韧、不改。")


def _cells_json(cells: dict[int, str]) -> dict[str, str]:
    return {str(col): value for col, value in cells.items()}


def _plan_entry(item, index: int | None, old: dict | None = None) -> dict[str, Any]:
    donor, source, cells, expect = item
    entry = dict(old or {})
    if index is not None:
        entry["index"] = index
    entry.update(donor=donor, source=source, cells=_cells_json(cells), desc_expected=expect)
    return entry


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等）。写法同 wf_balance_20260927_stinel。"""
    import wf_midautumn_kit_magnus as K
    design, panel = deepcopy(design), deepcopy(panel)

    plan = design["plan_rework1"]
    block = plan["leader_ability"]
    rows = block["rows"]
    block["rows"] = [_plan_entry(item, index, rows[index] if index < len(rows) else None)
                     for index, item in enumerate(K.LEADER)]
    block["row_count"] = len(K.LEADER)
    for slot in (1, 2, 3):
        records = plan["ability"]["keys"][f"{CID}{slot}"]["records"]
        if len(records) != len(K.PLAN[slot]):
            raise ValueError(f"design mirror {CID}{slot} record count drifted")
        plan["ability"]["keys"][f"{CID}{slot}"]["records"] = [
            _plan_entry(item, None, old) for item, old in zip(K.PLAN[slot], records)]
    strings = plan["texts"]["custom_ability_string"]["rows"]
    for row in strings:
        if row.get("key") in K.CAS_TEXTS:
            row["text"] = K.CAS_TEXTS[row["key"]]
    plan[MIRROR_TAG] = dict(
        spec="口径 A：无上限成长移队长并放缓（每3PF ×1/5，点火逐层 ×1/10），能力栏换有上限弱化版；"
             "技能 DSL 点火倍率封顶 10 层（BindConditionAccumulationVariable 第 5 参 99→10）；"
             "口径 B3/B6：「引擎之炎」629 追击（CT 0.6 秒）CreateNormalAttack p13 0.25→0.2，5 段每次 1.25→1.0",
        changed=["leader#1 全队技伤 100%→20%", "leader#2 全队攻 50%→10%",
                 "leader#9–#12 新增（能力1#2 / 能力2#0#1 / 能力3#4 的无上限部分）",
                 f"{A1}#2 限4次", f"{A2}#0/#1 每层15% 最多10层", f"{A3}#4 每层1% 最多10层",
                 "DSL×6 点火绑定上限 99→10", "引擎之炎追击 p13 0.25→0.2（每次 1.0）"],
        ignition_dsl_cap=K.IGNITION_DSL_CAP,
        chase_down_per_hit=K.CHASE_DOWN,
        chase_down_per_activation=K.CHASE_DOWN * K.BURST_MAX_HITS,
        module="mod-tools/wf_balance_20260927b_magnus.py",
    )
    problems = K._design_problems(design)
    if problems:
        raise ValueError(f"design mirror still drifts: {problems}")

    panel["leader"]["lines"] = _panel_lines(panel["leader"]["lines"], K.CAS_TEXTS[K.LEADER_OVERRIDE])
    for entry in panel["abilities"]:
        slot = int(entry["index"])
        if slot in (1, 2, 3):
            entry["lines"] = _panel_lines(entry["lines"],
                                          K.CAS_TEXTS[K.SLOT_OVERRIDE[slot]].replace(K.MAIN_ICON, ""))
    notes = [note for note in panel.get("notes", []) if not str(note).startswith("2026-09-27：平衡第二批")]
    panel["notes"] = notes + [MIRROR_NOTE]
    return design, panel


def _panel_lines(old: list[dict], text: str) -> list[dict]:
    """逐行对齐：文字没变的行原样保留（含 status/dev 等附注），变了或新增的行标 changed。"""
    by_text = {line["text"]: line for line in old}
    return [by_text.get(line, dict(text=line, status="changed")) for line in text.split("\n")]


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

# -*- coding: utf-8 -*-
"""菲莉亚·夏祭浴衣 159996 ``wind_oracle_yukata``：2026-09-27 平衡第二批（纯函数）。

口径 ``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``（作者已拍板）：

**A 无上限成长**（按 3 分钟实际触发次数分档，口径 A2 / 复核 C07）。频率依据：强化弹射所需连击常驻 −10
（队长 #4 −7、能力 5#0 −3），另有施放后 20 秒 −5、每 10 次 PF 后 30 秒 −7，且每次弹射消耗「风刃余势」
+15 连击 ⇒ 几乎每次拍板都是 PF，约 2.5–3 秒一次 ⇒ 3 分钟约 50–70 次（取 60）；「每 5 次 PF」约 10–14 次；
技能能量 580/530，约 20–25 秒一次 ⇒ 3 分钟 7–9 次。

1. ``leader_ability:159996``（6 → 8 行）
   - #1 光共鸣·每次 PF → 光队攻击力 +25%（限次 ``(None)``）：60 次 ≥30 ⇒ ×1/10，c49/c50 25000 → 2500；
   - #3 光共鸣·每次 PF → 自身 PF 伤害 +50%：×1/10 = 5000，并入能力 3#6「每 5 次 PF → 自身 PF 伤害 +50%」
     （同触发 kind 2、同 kind 55、同目标（无）、同前置光共鸣、无 CT；阈值 5 → 1 线性折算；10–14 次 ≤15 ⇒
     ×1/5 = 每 5 次 10% = 每次 2%）⇒ c49/c50 50000 → 7000；
   - #6 新增 = ``[CODE, '0', '']`` + 能力 3#4 ``[5:]``（光共鸣·技能发动 → 光队攻击力，7–9 次 ≤15 ⇒ ×1/5）
     c49/c50 100000 → 20000（队长表先例：trigger 23 + puller 0 官方 70 行如 ``111183#3``；
     trigger 23 → kind 32 全队官方 14 行如 ``121021#1``）；
   - #7 新增 = ``[CODE, '0', '']`` + 能力 3#5 ``[5:]``（光共鸣·每 5 次 PF → 攻击力，10–14 次 ⇒ ×1/5）
     c46 2 → 0（队长技只在自身为队长时生效，「队长」即自身；队长表 kind 32 target 2 零先例、target 0
     有官方先例 ``121001#4``；trigger 2 + puller 空 官方 51 行如 ``111183#0``）、c49/c50 50000 → 10000。
2. ``ability:1599963``（主位键 c1=false，7 行，腾出的槽换成有上限的弱化版）
   - #4 光共鸣·技能发动 → 光队攻击力：c34 ``(None)`` → 8、c51/c52 100000 → 10000（最多 8 次，满 80%）；
   - #5 光共鸣·每 5 次 PF → 队长攻击力：c34 ``(None)`` → 8、c51/c52 50000 → 10000（最多 8 次，满 80%，
     target 仍为 2，保留「喂队长」的辅助定位）；
   - #6 整行换成持续型「光共鸣·持有『风刃余势』期间 → 自身 PF 伤害 +50%」：c5=1、c85 ``(None)``、
     c97=194（ConditionCountUnique，数实例 = 持有判断）c98=0、c100/c101=100000、c102=1、c104=15999601、
     c108=false、c109=23（PowerFlipDamage）、c113/c114=50000；瞬发列 c27–c84 清空。行形照官方
     ``1211771#1``（194 → 23，限 1）与 live ``1599973#4``（泽赫尔 194 行）。

**B Down**（口径 B1/B2/B6：只改 CreateNormalAttack p13，按 SLv 的 {min,max} 都改，其余逐字保留）：

3. 两档技能：10 道风刃（p13 0.75）不动，10 份剑雨（2 段 ``CalculatedUsingMaxNumOfHits 2``）p13 2.5 → 1.0
   ⇒ 单体每次施放 10×0.75 + 10×2×2.5 = 57.5 → 27.5（≤30）。
4. 特殊强化弹射三档 ``wind_oracle_yukata_pf_lv{1,2,3}``：``ConditionalsProbability`` 36 选 1 的每个选项
   5 道风刃（p13 0.75）＋命中处剑雨（2 段 × 2.5）全部 → 0 ⇒ 单体每次 43.75/48.75/53.75 → 15/20/25
   （官方 special 底座两段爆炸不动；down critic C1 推荐方案）。

面板：本角色队长 / 能力都没有 desc_override（客户端按行自动生成），技能 / PF 覆盖说明不含这些数值 ⇒ 无文案改动。

生成器 ``wf_seasonal7_kit_philia.build``：行在 stock / nofly 之后先补 0917 的 ``wf_seasonal_pf_revision``（能力 3
追加两行，原为 kit 重建后手动套的一次性候选），再调 :func:`growth_rows`；技能树在 ``build_skill_tree`` 之后、
PF 在 ``random_pf`` 之后分别调 :func:`skill_tree` / :func:`pf_tree` ⇒ kit 重跑产物 == :func:`revise`。
一次性候选（``wf_skill_feel_candidate`` / ``wf_philia_wind_candidate`` / ``wf_regis_philia_pf_candidate`` /
``wf_philia_no_flying_revision``）只改倍率/朝向/浮游，不碰 p13，对本批输出重跑不会回退。
本模块只转换传入值，不读写 live / 候选 / assets。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

CID = "159996"
CODE = "wind_oracle_yukata"
PACKAGES = ["s7-philia"]
#: 候选 manifest 现值 1.0.11（0921 去浮游写入）→ 下一号。
PACKAGE_VERSION = {"s7-philia": "1.0.12"}
CAPABILITIES: list[str] = []
#: 候选 128 个 manifest 条目与文件逐一一致（2026-09-27 只读核对），本模块读取的各键与 live 逐字相同。
REVIEWED_DRIFT: dict = {}

ELEMENT = 4                                   # 内部 ElementKind：光
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
THIRD_KEY = CID + "3"
STOCK_UID = "15999601"                        # 固有「风刃余势」（wf_philia_combo_stock.UID）

SKILL_PROGRAMS = {lv: f"battle/action/skill/action/rare5/{CODE}${CODE}_{lv}" for lv in ("1", "2")}
PF_KEY = f"{CODE}_pf"
PF_PROGRAMS = {lv: f"battle/action/power_flip/action/override/{PF_KEY}${PF_KEY}_lv{lv}" for lv in (1, 2, 3)}

# ---------------------------------------------------------------- 行指纹（全部非空列；其余列必须为空）

_PRE_L = {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: "White", 11: "0", 18: "0",
          32: "(None)", 33: "0", 37: "(None)", 44: "0"}
_PF_L = {**_PRE_L, 25: "2", 28: "100000", 29: "100000"}
LEADER_PF_ATTACK = {**_PF_L, 45: "32", 46: "5", 47: "White", 49: "25000", 50: "25000"}
LEADER_PF_DAMAGE = {**_PF_L, 45: "55", 49: "50000", 50: "50000"}
LEADER_PF_ATTACK_AFTER = {**LEADER_PF_ATTACK, 49: "2500", 50: "2500"}
LEADER_PF_DAMAGE_AFTER = {**LEADER_PF_DAMAGE, 49: "7000", 50: "7000"}

_PRE_A = {0: f"{CODE}_3", 1: "false", 2: "power_flip", 3: "0", 5: "0", 6: "2", 9: "600000", 10: "600000",
          11: "White", 13: "0", 20: "0", 34: "(None)", 35: "0", 39: "(None)", 46: "0"}
THIRD_CAST_ATTACK = {**_PRE_A, 27: "23", 28: "0", 30: "100000", 31: "100000", 47: "32", 48: "5", 49: "White",
                     51: "100000", 52: "100000"}
_FIVE_PF = {**_PRE_A, 27: "2", 30: "500000", 31: "500000"}
THIRD_LEADER_ATTACK = {**_FIVE_PF, 47: "32", 48: "2", 51: "50000", 52: "50000"}
THIRD_PF_DAMAGE = {**_FIVE_PF, 47: "55", 51: "50000", 52: "50000"}
THIRD_CAST_ATTACK_AFTER = {**THIRD_CAST_ATTACK, 34: "8", 51: "10000", 52: "10000"}
THIRD_LEADER_ATTACK_AFTER = {**THIRD_LEADER_ATTACK, 34: "8", 51: "10000", 52: "10000"}
THIRD_STOCK_PF_DAMAGE = {0: f"{CODE}_3", 1: "false", 2: "power_flip", 3: "0", 5: "1", 6: "2", 9: "600000",
                         10: "600000", 11: "White", 13: "0", 20: "0", 85: "(None)", 97: "194", 98: "0",
                         100: "100000", 101: "100000", 102: "1", 104: STOCK_UID, 108: "false", 109: "23",
                         113: "50000", 114: "50000"}

MOVED_CAST_ATTACK = {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: "White", 11: "0", 18: "0",
                     25: "23", 26: "0", 28: "100000", 29: "100000", 32: "(None)", 33: "0", 37: "(None)",
                     44: "0", 45: "32", 46: "5", 47: "White", 49: "20000", 50: "20000"}
MOVED_FIVE_PF_ATTACK = {**_PF_L, 28: "500000", 29: "500000", 45: "32", 46: "0", 49: "10000", 50: "10000"}

LEADER_ROWS_BEFORE, LEADER_ROWS_AFTER = 6, 8
THIRD_ROWS = 7
LEADER_PF_ATTACK_ROW, LEADER_PF_DAMAGE_ROW = 1, 3
CAST_ROW, LEADER_ATTACK_ROW, PF_DAMAGE_ROW = 4, 5, 6

#: 放缓倍率（口径 A2）与合并折算，供测试与 notes 复核。
SLOWDOWN = {"leader#1 每次PF 光队攻": ("60/3min", "1/10", 25000, 2500),
            "leader#3 每次PF 自身PF伤": ("60/3min", "1/10", 50000, 5000),
            "ability3#6→leader#3 每5次PF 自身PF伤": ("10–14/3min", "1/5", 50000, 2000),   # 10%/5 次 = 2%/次
            "ability3#4→leader#6 每次施放 光队攻": ("7–9/3min", "1/5", 100000, 20000),
            "ability3#5→leader#7 每5次PF 攻击力": ("10–14/3min", "1/5", 50000, 10000)}

# ---------------------------------------------------------------- Down（p13）

SKILL_SWORDS, SKILL_RAIN_HITS = 10, 2
SKILL_SWORD_P13 = 0.75
SKILL_RAIN_P13_BEFORE, SKILL_RAIN_P13_AFTER = 2.5, 1.0
PF_CHOICES, PF_BLADES = 36, 5
PF_SWORD_P13_BEFORE, PF_RAIN_P13_BEFORE, PF_P13_AFTER = 0.75, 2.5, 0.0
SKILL_TOUGHNESS = (57.5, 27.5)
PF_TOUGHNESS = {1: (43.75, 15.0), 2: (48.75, 20.0), 3: (53.75, 25.0)}


def slv(value: float) -> list[dict]:
    return [{"min": value, "max": value}]


#: revise() 的输入基线（live 1.4.1049 = s7-philia 1.0.11，零漂移）。任一不符 ⇒ 拒绝（fail closed）。
BEFORE = {
    ("leader", CID): "a04ba40d07dfdd39949fda94331aba855cceb9ccb8f43eb0e649cac9bb7b479d",
    ("ability", THIRD_KEY): "c55fcae7b19626273d6d4b53b3b63a11a645d4e8e2b3c9479f7c2a1576f99c5e",
    ("dsl", SKILL_PROGRAMS["1"]): "663a5a15ba5db6ed592a6938341df0906a3a84446fffa39a7103d94c13484a4e",
    ("dsl", SKILL_PROGRAMS["2"]): "15839fe0d6145ef325decb55a55b9c0357b10866f4609fa0c2d78a0721ae4695",
    ("dsl", PF_PROGRAMS[1]): "5a71f05bf4d49733c8be4eda1b9864fe62bda00e63d4f81bfb9511a38a4d0fb7",
    ("dsl", PF_PROGRAMS[2]): "3ade62e74831611c70906dd5f0cca7800c99f5653029b478691cf12e48a7aaa6",
    ("dsl", PF_PROGRAMS[3]): "9b05e8d641e281d5883e4f3f366a14837feb4be8a211064c3459149c9e2eb182",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


# ---------------------------------------------------------------- 行

def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width and all(row[c] == v for c, v in cells.items())
            and all(v == "" for c, v in enumerate(row) if c not in cells))


def _require(row: list[str], width: int, cells: dict[int, str], label: str) -> None:
    if not _matches(row, width, cells):
        got = {c: v for c, v in enumerate(row) if v != "" or c in cells}
        raise ValueError(f"unreviewed {label} preimage: {got}")


def moved_row(ability_row: list[str]) -> list[str]:
    """能力行 → 队长行：``[CODE, '0', '']`` + 能力 ``[5:]``（列号能力 c≥5 → 队长 c−2）。"""
    if len(ability_row) != ABILITY_NCOLS:
        raise ValueError("unexpected ability row width")
    return [CODE, "0", ""] + deepcopy(ability_row[5:])


def stock_pf_damage_row(template: list[str]) -> list[str]:
    """能力 3#6 的替代：同键头部 + 光共鸣前置原样，瞬发块清空，换成 194 持有「风刃余势」→ PF 伤害 50%。"""
    row = list(template[:27]) + [""] * (ABILITY_NCOLS - 27)
    for col, value in THIRD_STOCK_PF_DAMAGE.items():
        row[col] = value
    return row


def growth_rows(leader: list[list[str]], third: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    """队长放缓/合并/新增两行 + 能力 3 三行换成有上限的弱化版。只接受 live 1.4.1049 形态（能力 3 为 7 行）。"""
    leader, third = deepcopy(leader), deepcopy(third)
    if len(leader) != LEADER_ROWS_BEFORE or any(len(r) != LEADER_NCOLS for r in leader):
        raise ValueError(f"leader_ability:{CID} is not the reviewed {LEADER_ROWS_BEFORE}-row shape")
    if len(third) != THIRD_ROWS or any(len(r) != ABILITY_NCOLS for r in third):
        raise ValueError(f"ability:{THIRD_KEY} is not the reviewed {THIRD_ROWS}-row shape")
    _require(leader[LEADER_PF_ATTACK_ROW], LEADER_NCOLS, LEADER_PF_ATTACK, "leader per-PF team attack")
    _require(leader[LEADER_PF_DAMAGE_ROW], LEADER_NCOLS, LEADER_PF_DAMAGE, "leader per-PF self PF damage")
    _require(third[CAST_ROW], ABILITY_NCOLS, THIRD_CAST_ATTACK, "ability 3 per-cast team attack")
    _require(third[LEADER_ATTACK_ROW], ABILITY_NCOLS, THIRD_LEADER_ATTACK, "ability 3 per-5-PF leader attack")
    _require(third[PF_DAMAGE_ROW], ABILITY_NCOLS, THIRD_PF_DAMAGE, "ability 3 per-5-PF self PF damage")

    cast = moved_row(third[CAST_ROW])
    cast[49] = cast[50] = "20000"                                # 100% × 1/5
    five = moved_row(third[LEADER_ATTACK_ROW])
    five[46] = "0"                                               # 队长 = 自身
    five[49] = five[50] = "10000"                                # 50% × 1/5
    _require(cast, LEADER_NCOLS, MOVED_CAST_ATTACK, "moved per-cast leader row")
    _require(five, LEADER_NCOLS, MOVED_FIVE_PF_ATTACK, "moved per-5-PF leader row")

    leader[LEADER_PF_ATTACK_ROW][49] = leader[LEADER_PF_ATTACK_ROW][50] = "2500"    # 25% × 1/10
    leader[LEADER_PF_DAMAGE_ROW][49] = leader[LEADER_PF_DAMAGE_ROW][50] = "7000"    # 50%×1/10 + 50%×1/5÷5
    leader.extend([cast, five])

    for index in (CAST_ROW, LEADER_ATTACK_ROW):
        third[index][34] = "8"                                   # 最多 8 次
        third[index][51] = third[index][52] = "10000"            # 每次 +10%，满 80%
    third[PF_DAMAGE_ROW] = stock_pf_damage_row(third[PF_DAMAGE_ROW])
    probs = row_problems("leader_ability", leader) + row_problems("ability", third)
    if probs:
        raise ValueError(f"growth rows fail the legality gates: {probs}")
    return leader, third


# ---------------------------------------------------------------- DSL

def _walk_attacks(node, ctx=(), out=None):
    """``(祖先命令名元组, CreateNormalAttack 节点)``，按树序。"""
    out = [] if out is None else out
    if isinstance(node, list):
        if node and node[0] == "Command" and len(node) == 2 and isinstance(node[1], list) and node[1]:
            command = node[1]
            if command[0] == "CreateNormalAttack":
                out.append((ctx, command))
            for child in command[1:]:
                _walk_attacks(child, ctx + (command[0],), out)
            return out
        for child in node:
            _walk_attacks(child, ctx, out)
    return out


def skill_attacks(tree) -> tuple[list, list]:
    """(风刃, 剑雨)：剑雨挂在每道风刃命中处的 CreateReferencePoint 里。"""
    pairs = _walk_attacks(tree)
    rains = [c for ctx, c in pairs if "CreateReferencePoint" in ctx]
    swords = [c for ctx, c in pairs if "CreateReferencePoint" not in ctx]
    return swords, rains


def pf_attacks(tree) -> tuple[list, list, list]:
    """(底座, 随机选项风刃, 随机选项剑雨)。"""
    base, swords, rains = [], [], []
    for ctx, c in _walk_attacks(tree):
        if "ConditionalsProbability" not in ctx:
            base.append(c)
        elif "CreateReferencePoint" in ctx[ctx.index("ConditionalsProbability"):]:
            rains.append(c)
        else:
            swords.append(c)
    return base, swords, rains


def _skill_state(tree) -> float:
    if not (isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl" and tree[10] == 3):
        raise ValueError("expected the native Philia skill tree (buffTargetAs 3)")
    swords, rains = skill_attacks(tree)
    if len(swords) != SKILL_SWORDS or len(rains) != SKILL_SWORDS \
            or any(c[13] != slv(SKILL_SWORD_P13) for c in swords):
        raise ValueError("unreviewed Philia skill blade/rain layout")
    values = {c[13][0]["max"] for c in rains}
    if len(values) != 1 or rains[0][13] not in (slv(SKILL_RAIN_P13_BEFORE), slv(SKILL_RAIN_P13_AFTER)):
        raise ValueError(f"unreviewed Philia skill rain toughness: {sorted(values)}")
    return values.pop()


def skill_tree(tree):
    """剑雨 CreateNormalAttack p13 2.5 → 1.0（10 处）；风刃 0.75 与其余节点逐字保留。只接受改前形态。"""
    out = deepcopy(tree)
    if _skill_state(out) != SKILL_RAIN_P13_BEFORE:
        raise ValueError("Philia skill rain toughness already revised (unreviewed preimage)")
    for attack in skill_attacks(out)[1]:
        attack[13] = slv(SKILL_RAIN_P13_AFTER)
    return out


def _pf_state(tree) -> str:
    if not (isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl" and tree[10] == 0):
        raise ValueError("expected the native Philia PF tree (buffTargetAs 0)")
    base, swords, rains = pf_attacks(tree)
    if len(base) != 2 or len(swords) != PF_CHOICES * PF_BLADES or len(rains) != PF_CHOICES * PF_BLADES:
        raise ValueError("unreviewed Philia PF random-volley layout")
    pair = ({json.dumps(c[13]) for c in swords}, {json.dumps(c[13]) for c in rains})
    if pair == ({json.dumps(slv(PF_SWORD_P13_BEFORE))}, {json.dumps(slv(PF_RAIN_P13_BEFORE))}):
        return "before"
    if pair == ({json.dumps(slv(PF_P13_AFTER))}, {json.dumps(slv(PF_P13_AFTER))}):
        return "after"
    raise ValueError(f"unreviewed Philia PF volley toughness: {pair}")


def pf_tree(tree):
    """随机选项里的风刃 p13 0.75 → 0、剑雨 2.5 → 0（各 180 处）；底座两段爆炸与其余节点逐字保留。"""
    out = deepcopy(tree)
    if _pf_state(out) != "before":
        raise ValueError("Philia PF volley toughness already revised (unreviewed preimage)")
    _, swords, rains = pf_attacks(out)
    for attack in swords + rains:
        attack[13] = slv(PF_P13_AFTER)
    return out


def before_batch2(program: str, tree):
    """本批 p13 改动的精确逆变换（只供回归测试把候选树还原成 0921 产物）；改前形态原样返回。"""
    out = deepcopy(tree)
    if program in SKILL_PROGRAMS.values() or program.startswith(tuple(SKILL_PROGRAMS.values())):
        if _skill_state(out) == SKILL_RAIN_P13_AFTER:
            for attack in skill_attacks(out)[1]:
                attack[13] = slv(SKILL_RAIN_P13_BEFORE)
        return out
    if program in PF_PROGRAMS.values() or program.startswith(tuple(PF_PROGRAMS.values())):
        if _pf_state(out) == "after":
            _, swords, rains = pf_attacks(out)
            for attack in swords:
                attack[13] = slv(PF_SWORD_P13_BEFORE)
            for attack in rains:
                attack[13] = slv(PF_RAIN_P13_BEFORE)
        return out
    raise ValueError(f"not a Philia batch-2 program: {program}")


def toughness(node, hits: int = 1) -> float:
    """单体每次执行的最大削韧：p13 × 所在判定区的最大命中数；``ConditionalsProbability`` 取各选项最大值。"""
    if not isinstance(node, list):
        return 0.0
    if node and node[0] == "Command" and len(node) == 2 and isinstance(node[1], list) and node[1]:
        command = node[1]
        if command[0] == "CreateNormalAttack":
            return hits * command[13][0]["max"]
        if command[0] == "CreateHitArea":
            n = command[14][1] if command[14][0] == "CalculatedUsingMaxNumOfHits" else 1
            return sum(toughness(a, hits * n if i == 23 else hits) for i, a in enumerate(command[1:], 1))
        if command[0] == "ConditionalsProbability":
            return max(toughness(branch, hits) for branch in command[1][1])
        return sum(toughness(a, hits) for a in command[1:])
    return sum(toughness(child, hits) for child in node)


# ---------------------------------------------------------------- 门禁

def row_problems(kind: str, rows) -> list[str]:
    import wf_client_legality as L
    probs = []
    for i, row in enumerate(rows):
        for p in (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
                  + L.invoke_skill_string_problems(row, set(), kind)):
            probs.append(f"{kind}#{i}: {p}")
    return probs


def dsl_problems(tree) -> list[str]:
    import wf_client_legality as L
    import wf_dsl
    probs = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        probs.append("AMF3 roundtrip mismatch")
    probs += L.action_dsl_element_problems(tree, ELEMENT)
    probs += L.action_dsl_subject_binding_problems(tree)
    probs += L.action_dsl_lookup_scope_problems(tree)
    probs += L.action_dsl_hit_area_target_problems(tree)
    return probs


# ---------------------------------------------------------------- 批次入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    live = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        if digest(value) != want:
            raise ValueError(f"live input drifted from the reviewed baseline: {kind}:{key}")
        live[kind, key] = deepcopy(value)
    leader, third = growth_rows(live["leader", CID], live["ability", THIRD_KEY])
    dsl = {program: skill_tree(live["dsl", program]) for program in SKILL_PROGRAMS.values()}
    dsl.update({program: pf_tree(live["dsl", program]) for program in PF_PROGRAMS.values()})
    probs = [f"{program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    if probs:
        raise ValueError(probs)
    return {
        "ability": {THIRD_KEY: third},
        "leader": {CID: leader},
        "cas": {}, "text": {}, "table": {}, "action": {}, "server_text": {},
        "dsl": dsl,
        "new_programs": [],
        "notes": {
            "request": "第二批口径 A（无上限成长，按实际次数分档）+ B1/B2（技能总削 ≤30、强化弹射 15/20/25）",
            "frequency": "PF 约 60 次/3 分钟（连击需求常驻 −10、弹射耗余势 +15 连击）⇒ 每次 PF ×1/10；"
                         "每 5 次 PF 10–14 次 ⇒ ×1/5；施放 7–9 次 ⇒ ×1/5",
            "leader": "#1 25000→2500；#3 50000→7000（5000 + 并入能力3#6 的 2000）；新增 #6 施放→光队攻 20000、"
                      "#7 每5次PF→自身攻 10000（c46 2→0）；6→8 行",
            "ability3": "#4/#5 c34 (None)→8、c51/c52 →10000；#6 → 194 持有风刃余势 → PF 伤害 50%（限 1）",
            "design_alternative": "设计稿风险 1 的替代值（每次 PF 与每 5 次 PF 都按 1/10）为 #3=6000、#7=5000；"
                                  "口径 A2 按实际次数，每 5 次 PF 只有 10–14 次 ⇒ 取 1/5（#3=7000、#7=10000）",
            "skill_dsl": "剑雨 CNA p13 2.5→1.0 ×10（单体 57.5→27.5）",
            "pf_dsl": "随机选项风刃 p13 0.75→0、剑雨 2.5→0 各 ×180（单体 43.75/48.75/53.75→15/20/25）",
            "panel": "无 desc_override，面板自动生成；技能/PF 说明无相关数值，不改文案",
            "runtime_verified": False,
        },
    }

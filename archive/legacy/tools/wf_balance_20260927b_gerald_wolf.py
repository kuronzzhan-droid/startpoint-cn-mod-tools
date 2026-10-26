# -*- coding: utf-8 -*-
"""杰拉德「月耀守护」149999 ``white_wolf_gerald``（光）：2026-09-27 平衡调整第二批。

注意：杰拉德（149999 光，白狼骑士）≠ 杰拉尔（129992 水，unicorn_lancer_rose）。

同一个队长键 ``leader_ability:149999`` 里的成长批与 Down 批在本模块内串行、按行改；
另改技能两档的层数封顶、强化弹射 Lv3 树的削韧。其余一律逐字保留：

1. 成长（口径 A.1–A.3 / growth_design 149999）：队长行7–9（0 基 #6–#8）「光编成≥6：
   编成直接攻击（trigger 20，puller 7 全队合计，c27 White）每满 50 次 → 光队 攻击力(32) /
   直击伤害(33) / 能力伤害(388)」，限次 c32=(None)、CT 0，为永久无上限成长 → 原位放缓：
   c49/c50 50000→5000（每步 +50% → +5%，×1/10；3 分钟实际触发 ≥30 次，见 notes）。
2. 成长（口径 A.5，技能程序里随层数无上限增长的倍率）：技能两档
   （``rare5/white_wolf_gerald$white_wolf_gerald_{1,2}``）强化分支 ConditionalsChangeSkillFlag(1) 首条
   ``BindConditionAccumulationVariable(-17, 360, DCUnique 14999903, 1, 上限)`` 的上限
   2147483647→10。变量 360 喂 ``CreateRatioAttack(301, 1, [0.05, 0.01×v360])``（当前 HP 比例伤害），
   计数固有 14999903「时空侵蚀」每次强化施技 +1、持续 99999999 帧（永久）。客户端
   ActionEvaluator case 101 取 ``min(层数/第4参, 第5参)`` ⇒ 比例伤害封顶 5%+1%×10 = 15%。
   官方先例 blackflower_wiz_smr22_1/_2 ``Bind(-17, vid, DCUnique 11, 1, 10)``；本批
   校园希尔媞 / 玛格诺斯中秋 / 凯尔同写法。固有 14999903 的上限（c4）不动。
   无上限部分「由队长技承担」（A.5）做不到：队长表没有「当前 HP 比例伤害」内容 kind，
   队长里也没有按 14999903 逐层成长的行 ⇒ 列为 blocked 交作者拍板（见 notes.blocked）。
3. Down（口径 B.4 / down_design 149999）：队长行10（#9）「持续·Fever（c95=4）→ 全队(光)
   眩晕蓄积（during kind 19 Stunify）」c111/c112 500000→50000（500% → 50%，全队 ≤50%）。
4. Down（口径 B.2 + 复核 R6）：强化弹射 Lv3 树（``white_wolf_gerald_pf_lv3``）时之刻印分支
   CreateNormalAttack p13 {3,3} → {2.5,2.5}：10 段 × 2.5 = 25（原 30，正好顶到 Lv3 上限 25）。
   无刻印分支（非光队走这支）5 段 × 3 = 15，本就 ≤25，按「尽量正好顶到上限」保留不动。

保留（口径 B.1 / B.3 / A.6，设计稿 action=keep）：技能两档削韧（能量 1500，66/73.5 按 550 折算 ≈27）、
能力3 行6 月牙斩 629（3.5，B.3「其余按设计稿」+ 方案表「保留 同意」）、队长行6（每 35 直击
15 倍能力伤害，是造伤不是成长）、全部充能行（队长行4 CT、能力3 行3/5/7 等，表二本批暂缓）。

面板：队长面板键 ``desc_override_black_wolf_knight`` 在 live 不存在 → 客户端按行自动生成，
本次不写覆盖文案；技能描述 / character_text / 服务端文本 / ``change_skill_white_wolf_gerald``
（「额外造成一定固定伤害」）都不含这些数值，不改。

生成器：``wf_gerald_cast_growth.py``（COUNTER_CAP=10）已同步：对 09-25 捕获的施技成长前技能树
重跑 ``rewrite()`` == 本模块输出（测试断言）；它对已带 Bind 的树 fail closed，不会回退。
``wf_gerald_percent_skill.py`` / ``wf_gerald_percent_revision.py`` 按旧源 sha256 fail closed，
不写本次任何格子。杰拉德没有设计镜像（evidence/v3-20260903/spec_v2.json 是 09-03 的历史施工
规格，已与 live 不同，只当证据）。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl

CID = "149999"
CODE = "white_wolf_gerald"
PACKAGES = ["white_wolf_gerald"]
#: 候选 manifest 现值 0.20260925（revision_20260925）⇒ 本批 0.20260927，只升不降。
PACKAGE_VERSION = {"white_wolf_gerald": "0.20260927"}
#: 候选已声明 gauge-gain-rules-v1 / panel-description-override-v2；改后的行与树不需要新能力。
CAPABILITIES: list[str] = []
ELEMENT = 4                        # master/character c3：光（0 基内部元素）
ELEMENT_TOKEN = "White"
LEADER_NCOLS = 124
LEADER_NAME = "black_wolf_knight"  # 队长行 c0（克隆母本名）；面板键 desc_override_black_wolf_knight 不存在

PF_ACTION = ("master/skill/power_flip_action.orderedmap", "white_wolf_gerald_pf")
PF_BASE = "battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv"
PF_LV3 = PF_BASE + "3"
TIME_SEAL_UID = 1499989            # 固有「时之刻印」（能力3 #0 开局 461 给予，光编成≥6）
SKILL_BASE = f"battle/action/skill/action/rare5/{CODE}${CODE}_"
SKILLS = (SKILL_BASE + "1", SKILL_BASE + "2")

#: 候选 white_wolf_gerald 的 PF Lv3 文件与 live 逐字节相同（sha256 4598…），但 manifest 仍封着旧值
#: c3ffe558…（revision_20260925 已按同一哈希登记为已审漂移）。本次重写 Lv3 后该条目被重新封口。
REVIEWED_DRIFT: dict[tuple[str, str], str] = {
    ("common", wf_dsl.dsl_logical(PF_LV3)):
        "45984762e68f9f0676e7e1a64019a4a4d69da074b5abaa205c31fe26ab4f3406",
}

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数；队长键与候选逐字相同，
#: PF Lv3 树与候选文件相同，技能两档与候选文件、manifest 封口三者同字节 8d323968…/f27b8a14…）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", CID): "ab09a29c31679b09c7afe3f53c13433287eb974f0c3075c80b6bf56f9826f2df",
    ("dsl", PF_LV3): "1f7d7d5bea0ccdb0715685fd773030cad43a583e2fa8a238c18c56117f7b5d20",
    ("table", PF_ACTION): "9b5c14ce6792e5bc35e49195f73abf862039a630f9d51a61681a9e0577b78105",
    ("dsl", SKILLS[0]): "0c87b53bf50446be34d3aa257d6dfa7b0b1f7351b78532d67781c1c72026eb9e",
    ("dsl", SKILLS[1]): "915c5bdaba3b1702d247943277913dbb0c9b1fa4dd5fa75b4e9c8792b87bd5e6",
}

# ---------------------------------------------------------------- 队长：成长行 #6–#8

GROWTH_ROWS = {6: "32", 7: "33", 8: "388"}   # 0 基行号 → c45 内容 kind（攻击力 / 直击伤害 / 能力伤害）
GROWTH_COLS = (49, 50)                       # 瞬发内容强度：低级 / 满级
GROWTH_OLD = ("50000", "50000")              # +50% / 次
GROWTH_NEW = ("5000", "5000")                # +5% / 次（×1/10）
GROWTH_STEP = "1/10"

#: 光编成≥6（前置 2，c7/c8=600000）+ 编成直接攻击（trigger 20，puller 7=全队合计，组 White）
#: 每满 50 次（c28/c29=5000000），限次 (None)、CT 0 → 全队(光)（c46=5，c47 White）。
_DIRECT_GATE: dict[int, str] = {
    0: LEADER_NAME, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
    11: "0", 18: "0", 25: "20", 26: "7", 27: ELEMENT_TOKEN, 28: "5000000", 29: "5000000",
    32: "(None)", 33: "0", 37: "(None)", 44: "0", 46: "5", 47: ELEMENT_TOKEN,
}


def _growth_cells(index: int, values: tuple[str, str]) -> dict[int, str]:
    return {**_DIRECT_GATE, 45: GROWTH_ROWS[index], GROWTH_COLS[0]: values[0], GROWTH_COLS[1]: values[1]}


# ---------------------------------------------------------------- 队长：Fever 眩晕蓄积 #9

STUN_ROW = 9
STUN_COLS = (111, 112)                       # 持续内容强度：低级 / 满级
STUN_OLD = ("500000", "500000")              # 500%
STUN_NEW = ("50000", "50000")                # 50%（全队 ≤50%）
#: 口径 B.4 眩晕蓄积全谱：瞬发 22 ConditionStunify / 51 Stunify / 183 StunifyUpExtend /
#: 241 ConditionStunifyShare；持续 19 Stunify / 120 ConditionStunifyShare（ability_enum_map）。
STUNIFY_INSTANT_KINDS = ("22", "51", "183", "241")
STUNIFY_DURING_KINDS = ("19", "120")
STUNIFY_CAP = {"0": 100000}                  # 目标 0=自身 ≤100%；其余（全队等）≤50%
STUNIFY_TEAM_CAP = 50000


def stunify_rows(rows: list[list[str]]) -> list[tuple[int, str, int]]:
    """[(行号, 目标, 强度 max(低级, 满级))]：本键里所有眩晕蓄积行
    （瞬发 c45 kind / c46 目标 / c49–c50 强度；持续 c107 / c108 / c111–c112）。"""
    found = [(i, r[46], max(int(r[49]), int(r[50]))) for i, r in enumerate(rows)
             if r[3] == "0" and r[45] in STUNIFY_INSTANT_KINDS]
    found += [(i, r[108], max(int(r[111]), int(r[112]))) for i, r in enumerate(rows)
              if r[3] == "1" and r[107] in STUNIFY_DURING_KINDS]
    return sorted(found)


def stunify_problems(rows: list[list[str]]) -> list[str]:
    """口径 B.4：自身 ≤100%、全队（及其他非自身目标）≤50%。"""
    return [f"#{i} target {target} Stunify {value}" for i, target, value in stunify_rows(rows)
            if value > STUNIFY_CAP.get(target, STUNIFY_TEAM_CAP)]


def _stun_cells(values: tuple[str, str]) -> dict[int, str]:
    return {0: LEADER_NAME, 1: "0", 3: "1", 4: "0", 11: "0", 18: "0", 83: "(None)", 95: "4",
            106: "false", 107: "19", 108: "5", 109: ELEMENT_TOKEN,
            STUN_COLS[0]: values[0], STUN_COLS[1]: values[1]}


#: 同键里必须原样在场、不许被本模块碰的行（按内容指纹锁定位置）：#5 每 35 直击 15 倍能力伤害。
KEPT_DAMAGE_ROW = 5
KEPT_DAMAGE_CELLS: dict[int, str] = {
    **{c: v for c, v in _DIRECT_GATE.items() if c not in (28, 29, 46, 47)},
    28: "3500000", 29: "3500000", 45: "255", 46: "0", 49: "1500000", 50: "1500000", 67: "(None)",
}

# ---------------------------------------------------------------- 强化弹射 Lv3 削韧（p13）

PF_ROOT_HEADER = ["ActionDsl", 1, ["None"], *[False] * 7, 0]
PF_P13 = 13                                  # CreateNormalAttack 第 14 个节点 = 削韧（detoughness）
PF_P13_OLD = [{"min": 3, "max": 3}]
PF_P13_NEW = [{"min": 2.5, "max": 2.5}]
PF_RATIO = [{"min": 6.3, "max": 6.3}]
#: 条件分支下标 → 该分支 CreateHitArea 的最大命中段数（3=有时之刻印，4=无刻印）。
PF_BRANCH_HITS = {3: 10, 4: 5}
#: 只改超上限的时之刻印分支（10×3=30 → 10×2.5=25）；无刻印分支 5×3=15 本就 ≤25，按口径 B.2
#: 「尽量正好顶到上限」不再往下压（非光队走这支，改了等于额外削弱）。
PF_SEAL_BRANCH = 3
PF_LV3_CAP = 25                              # 口径 B.2：PF 每级削韧上限 15 / 20 / 25


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: Any) -> Any:
    value = read(kind, key)
    got = digest(value) if value is not None else None
    if got != BEFORE[(kind, key)]:
        raise ValueError(f"unreviewed live baseline for {kind}:{key} ({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], cells: dict[int, str]) -> bool:
    return (len(row) == LEADER_NCOLS
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _hits(rows: list[list[str]], cells: dict[int, str]) -> list[int]:
    return [i for i, row in enumerate(rows) if _matches(row, cells)]


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """同一队长键串行按行改：#6–#8 成长 50000→5000、#9 Fever 眩晕蓄积 500000→50000；其余 8 行逐字保留。"""
    if len(rows) != 12 or any(len(row) != LEADER_NCOLS for row in rows):
        raise ValueError(f"leader_ability:{CID}: expected 12 rows of {LEADER_NCOLS} columns")
    for index in GROWTH_ROWS:
        found = _hits(rows, _growth_cells(index, GROWTH_OLD))
        if found != [index]:
            raise ValueError(f"leader_ability:{CID}: direct-hit growth row kind {GROWTH_ROWS[index]} "
                             f"(50%/50 hits, (None), CT0) not found at #{index}: {found}")
    found = _hits(rows, _stun_cells(STUN_OLD))
    if found != [STUN_ROW]:
        raise ValueError(f"leader_ability:{CID}: Fever Stunify 500% row not found at #{STUN_ROW}: {found}")
    if _hits(rows, KEPT_DAMAGE_CELLS) != [KEPT_DAMAGE_ROW]:
        raise ValueError(f"leader_ability:{CID}: 35-hit ability-damage row #{KEPT_DAMAGE_ROW} drifted")

    out = deepcopy(rows)
    for index in GROWTH_ROWS:                                   # 成长批（行7–9）
        out[index][GROWTH_COLS[0]], out[index][GROWTH_COLS[1]] = GROWTH_NEW
    out[STUN_ROW][STUN_COLS[0]], out[STUN_ROW][STUN_COLS[1]] = STUN_NEW   # Down 批（行10）

    # 自检：只动了这 8 格。
    for index in GROWTH_ROWS:
        if not _matches(out[index], _growth_cells(index, GROWTH_NEW)):
            raise AssertionError(f"leader #{index} touched more than c49/c50")
    if not _matches(out[STUN_ROW], _stun_cells(STUN_NEW)):
        raise AssertionError(f"leader #{STUN_ROW} touched more than c111/c112")
    changed = [i for i, (a, b) in enumerate(zip(rows, out)) if a != b]
    if changed != sorted([*GROWTH_ROWS, STUN_ROW]):
        raise AssertionError(f"leader rows touched: {changed}")
    if stunify_problems(out):
        raise AssertionError(f"Stunify still above the B.4 caps: {stunify_problems(out)}")
    return out


# ---------------------------------------------------------------- DSL

def _walk(node, path=()):
    if isinstance(node, list):
        yield path, node
        for index, child in enumerate(node):
            yield from _walk(child, path + (index,))


def _at(tree, path):
    for index in path:
        tree = tree[index]
    return tree


def pf_attacks(tree) -> list[tuple[tuple, list, list]]:
    """[(CreateNormalAttack 路径, 该节点, 最内层所属 CreateHitArea)]，按树序。"""
    areas = [(p, n) for p, n in _walk(tree) if n and n[0] == "CreateHitArea"]
    out = []
    for path, node in _walk(tree):
        if node and node[0] == "CreateNormalAttack":
            owners = [(p, n) for p, n in areas if path[:len(p)] == p]
            if not owners:
                raise ValueError(f"CreateNormalAttack at {path} is outside every hit area")
            out.append((path, node, max(owners, key=lambda item: len(item[0]))[1]))
    return out


def pf_detoughness(tree) -> dict[int, float]:
    """每个时之刻印分支（3=有刻印 / 4=无刻印）的单次强化弹射总削韧 = 段数 × p13.max。"""
    totals: dict[int, float] = {}
    for path, attack, area in pf_attacks(tree):
        branch = path[4]
        if area[14][0] != "CalculatedUsingMaxNumOfHits":
            raise ValueError(f"unexpected hit count spec {area[14]}")
        totals[branch] = totals.get(branch, 0) + area[14][1] * attack[PF_P13][0]["max"]
    return totals


def pf_lv3_tree(tree) -> list:
    """Lv3 时之刻印分支 CreateNormalAttack p13 3→2.5（30→25）；无刻印分支（15）与其余节点逐字保留。"""
    result = deepcopy(tree)
    if result[:11] != PF_ROOT_HEADER:
        raise ValueError("PF lv3 root header drift")
    body = result[11]
    if body[0] != "Block" or len(body[1]) != 1 or body[1][0][0] != "Command":
        raise ValueError("PF lv3 body is not a single conditional command")
    gate = body[1][0][1]
    if gate[:3] != ["ConditionalsConditionAccumulationNumber", ["DCUnique", TIME_SEAL_UID], 1]:
        raise ValueError("PF lv3 time-seal branch drift")
    attacks = pf_attacks(result)
    if len(attacks) != 2:
        raise ValueError(f"expected two PF lv3 CreateNormalAttack nodes, got {len(attacks)}")
    seen = {}
    for path, attack, area in attacks:
        if path[:4] != (11, 1, 0, 1) or path[4] not in PF_BRANCH_HITS:
            raise ValueError(f"PF lv3 attack outside the time-seal branches: {path}")
        if (attack[1], attack[2], attack[6], attack[PF_P13]) != (2, 255, PF_RATIO, PF_P13_OLD):
            raise ValueError(f"PF lv3 attack preimage drift at {path}: p13={attack[PF_P13]}")
        if area[2] != -18 or area[14] != ["CalculatedUsingMaxNumOfHits", PF_BRANCH_HITS[path[4]]]:
            raise ValueError(f"PF lv3 hit area drift at {path}")
        seen[path[4]] = path
    if set(seen) != set(PF_BRANCH_HITS):
        raise ValueError("PF lv3 must carry one attack per time-seal branch")
    before = pf_detoughness(result)
    _at(result, seen[PF_SEAL_BRANCH])[PF_P13] = deepcopy(PF_P13_NEW)
    totals = pf_detoughness(result)
    if totals[PF_SEAL_BRANCH] != PF_LV3_CAP or max(totals.values()) != PF_LV3_CAP:
        raise AssertionError(f"PF lv3 detoughness {totals} does not top out at {PF_LV3_CAP}")
    if {b: v for b, v in totals.items() if b != PF_SEAL_BRANCH} != \
            {b: v for b, v in before.items() if b != PF_SEAL_BRANCH}:
        raise AssertionError("PF lv3 no-seal branch must stay untouched")
    return result


# ---------------------------------------------------------------- 技能两档：时空侵蚀层数封顶（口径 A.5）

SKILL_ROOT_HEADER = ["ActionDsl", 3, ["None"], *[False] * 7, 0]
COUNTER_UID = 14999903             # 固有「时空侵蚀」white_wolf_gerald_cast_growth（c3 99999999 帧、c4 2147483647）
COUNTER_KEY = CODE + "_cast_growth"
COUNTER_VARIABLE = 360             # Bind 出来的浮点变量号，只被强化分支比例伤害的 mul 引用
SKILL_CAP_OLD = 2147483647         # live 解码为 2147483647.0（AMF3 29 位整数放不下 ⇒ double）
SKILL_CAP_NEW = 10                 # 官方 blackflower_wiz_smr22_1/_2 Bind(-17, vid, DCUnique 11, 1, 10)
SKILL_CAP_ARG = 5                  # Bind 参数数组下标（[名, 主体, 变量, 状态, 除数, 上限]）
BIND_PREFIX = ["BindConditionAccumulationVariable", -17, COUNTER_VARIABLE, ["DCUnique", COUNTER_UID], 1]
#: 强化分支：Bind 后紧跟「时空侵蚀 +1 层」（先快照、后递增）。
COUNTER_INCREMENT = ["CreateCondition", -17, [["ACUnique", COUNTER_UID, [{"min": 1, "max": 1}]]],
                     [{"min": 1, "max": 1}], ["None"], False, False, COUNTER_KEY, None, False, 3,
                     [{"min": 1, "max": 1}], True]
RATIO_STRIKE = ["CreateRatioAttack", 301, 1,
                [{"min": 0.05, "max": 0.05}, {"min": 0.01, "max": 0.01, "mul": COUNTER_VARIABLE}]]
RATIO_BASE, RATIO_PER_STACK = 0.05, 0.01


def _commands(tree, name):
    return [(p, n) for p, n in _walk(tree) if n and n[0] == name]


def skill_counter_bind(tree) -> tuple[tuple, list]:
    """(路径, Bind 参数数组)：强化分支 ConditionalsChangeSkillFlag(1) 首条、且是整树唯一的 Bind。"""
    flags = _commands(tree, "ConditionalsChangeSkillFlag")
    if len(flags) != 1 or flags[0][1][1] != 1:
        raise ValueError("expected one enhanced skill branch ConditionalsChangeSkillFlag(1)")
    flag_path, flag = flags[0]
    enhanced = flag[2]
    if not (isinstance(enhanced, list) and enhanced[0] == "Block" and len(enhanced[1]) >= 2
            and enhanced[1][0][0] == "Command" and enhanced[1][1][0] == "Command"):
        raise ValueError("enhanced branch does not start with the counter commands")
    binds = _commands(tree, "BindConditionAccumulationVariable")
    path = flag_path + (2, 1, 0, 1)
    if [p for p, _n in binds] != [path]:
        raise ValueError(f"expected exactly one Bind at the enhanced branch head: {[p for p, _n in binds]}")
    if enhanced[1][1][1] != COUNTER_INCREMENT:
        raise ValueError("time-erosion counter increment drifted")
    return path, binds[0][1]


def skill_ratio_at(tree, prior_casts: int) -> float:
    """按客户端 case 101 语义算第 prior_casts+1 次强化施技的当前 HP 比例：base + per × min(n/除数, 上限)。"""
    _path, bind = skill_counter_bind(tree)
    bound = min(prior_casts / bind[4], bind[SKILL_CAP_ARG])
    strikes = [n for _p, n in _commands(tree, "CreateRatioAttack") if len(n[3]) == 2]
    if len(strikes) != 1:
        raise ValueError("expected one growing ratio strike")
    return sum(v["min"] * (bound if v.get("mul") == COUNTER_VARIABLE else 1) for v in strikes[0][3])


def skill_tree(tree) -> list:
    """技能树 → 新树（深拷贝）：只把时空侵蚀 Bind 的上限 2147483647 → 10，其余节点逐字保留。"""
    result = deepcopy(tree)
    if result[:11] != SKILL_ROOT_HEADER:
        raise ValueError("skill root header drift")
    path, bind = skill_counter_bind(result)
    if bind[:SKILL_CAP_ARG] != BIND_PREFIX or len(bind) != SKILL_CAP_ARG + 1 \
            or isinstance(bind[SKILL_CAP_ARG], bool) or bind[SKILL_CAP_ARG] != SKILL_CAP_OLD:
        raise ValueError(f"time-erosion Bind preimage drift: {bind!r:.160}")
    ratios = [n for _p, n in _commands(result, "CreateRatioAttack")]
    if [n for n in ratios if len(n[3]) == 2] != [RATIO_STRIKE]:
        raise ValueError("growing current-HP ratio strike drifted")
    uses = [n for _p, n in _walk(result) if any(isinstance(v, dict) and "mul" in v for v in n)]
    if len(uses) != 1:
        raise ValueError(f"variable {COUNTER_VARIABLE} must feed only the ratio strike: {len(uses)} users")
    old_cap = bind[SKILL_CAP_ARG]
    _at(result, path)[SKILL_CAP_ARG] = SKILL_CAP_NEW
    # 自检：恢复上限即回到输入树（只动了这一格；比较连类型一起，2147483647.0 仍是 float）。
    restored = deepcopy(result)
    _at(restored, path)[SKILL_CAP_ARG] = old_cap
    if json.dumps(restored) != json.dumps(tree):
        raise AssertionError("skill_tree touched more than the Bind cap")
    return result


def dsl_problems(tree) -> list[str]:
    """契约要求的四道 DSL 门 + AMF3 往返。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


def row_problems(row: list[str], cas_keys=frozenset()) -> list[str]:
    kind = "leader_ability"
    return (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
            + L.invoke_skill_string_problems(row, cas_keys, kind))


# ---------------------------------------------------------------- revise

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader = _checked(read, "leader", CID)
    pf_tree = _checked(read, "dsl", PF_LV3)
    pf_action = _checked(read, "table", PF_ACTION)
    if pf_action != [[f"{PF_BASE}{level}" for level in (1, 2, 3)]]:
        raise ValueError("power_flip_action no longer points at the reviewed PF trees")

    skills = {program: _checked(read, "dsl", program) for program in SKILLS}

    new_leader = leader_rows(leader)
    new_pf = pf_lv3_tree(pf_tree)
    new_skills = {program: skill_tree(tree) for program, tree in skills.items()}
    problems = [f"leader #{i}: {p}" for i in (*GROWTH_ROWS, STUN_ROW) for p in row_problems(new_leader[i])]
    problems += [f"leader #{i}: capability {caps}" for i in (*GROWTH_ROWS, STUN_ROW)
                 if (caps := L.required_client_capabilities("leader_ability", new_leader[i]))]
    problems += [f"dsl {program}: {p}" for program, tree in {PF_LV3: new_pf, **new_skills}.items()
                 for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    before_pf, after_pf = pf_detoughness(pf_tree), pf_detoughness(new_pf)
    ratio_cap = round(RATIO_BASE + RATIO_PER_STACK * SKILL_CAP_NEW, 6)
    return {
        "ability": {}, "leader": {CID: new_leader}, "cas": {}, "text": {}, "table": {},
        "action": {}, "dsl": {PF_LV3: new_pf, **new_skills}, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_gerald_wolf.py",
            "spec": "第二批施工口径 A.1–A.3（成长原位放缓）、A.5（技能程序层数倍率封顶 10）、"
                    "B.2（PF 每级 ≤15/20/25，复核 R6 顶到 25）、B.4（全队眩晕蓄积 ≤50%）；"
                    "growth_design / down_design 149999；复核（修复轮）major：技能施技成长漏列 A.5",
            "live_tail": "1.4.1049（设计稿按 1.4.1048 写；行号与数值已按 1.4.1049 live 重读，与设计稿所引一致）",
            "changes": {
                f"leader_ability:{CID}#6（行7）c49/c50": "50000→5000：每 50 次全队直击 光队攻击力 +50%→+5%",
                f"leader_ability:{CID}#7（行8）c49/c50": "50000→5000：同触发 光队直击伤害 +50%→+5%",
                f"leader_ability:{CID}#8（行9）c49/c50": "50000→5000：同触发 光队能力伤害 +50%→+5%",
                f"leader_ability:{CID}#9（行10）c111/c112": "500000→50000：Fever 中 光队眩晕蓄积 500%→50%",
                f"{PF_LV3} 时之刻印分支 CreateNormalAttack p13": "{3,3}→{2.5,2.5}（10 段 30→25）",
                f"{SKILL_BASE}{{1,2}} 强化分支 BindConditionAccumulationVariable 第 5 参":
                    f"{SKILL_CAP_OLD}→{SKILL_CAP_NEW}：当前 HP 比例伤害 5%+1%×层 → 封顶 {ratio_cap:.0%}",
            },
            "growth_frequency": {
                "trigger": "光编成≥6；编成直接攻击（trigger 20 MemberDirectAttack，puller 7=全队合计，组 White）每满 50 次；"
                           "限次 (None)、CT 0 ⇒ 永久无上限（口径 A.1）",
                "estimate_3min": "设计稿 20–50 次、典型 30（全队直击 1000–2500 次 / 50：普通 4–6 次/秒，技能给全队"
                                 "最大速度固定+贯穿+浮游时 8–15 次/秒）。设计稿没算 PF Lv3 给全队的 60 秒 "
                                 "ACAdditionalDirectAttack 6 段：客户端 MemberImpl 每次接触按 directAttackTimes 排 N 个 "
                                 "NormalAttack（伤害÷N），若 trigger 20 按每个 NormalAttack 计数（未真机验证），"
                                 "PF Lv3 窗口内计数 ×6，3 分钟现实范围约 60–200 次",
                "tier": f"无论 30 次还是 200 次都 ≥30 ⇒ 每步 {GROWTH_STEP}（口径 A.2 最强档），50%→5%",
                "typical_before_after": "每项（光队攻击力/直击伤害/能力伤害）：设计稿口径 30 次 +1500%→+150%；"
                                        "计入 PF Lv3 6 段后约 60–200 次 ⇒ 改前 +3000%–+10000% → 改后 +300%–+1000%",
                "placement": "已在队长技 ⇒ 原位放缓（A.3）；三行 kind 32/33/388 不同，不合并；不增行（仍 12 行）",
            },
            "skill_cast_growth": {
                "where": "技能两档强化分支 ConditionalsChangeSkillFlag(1)（队长 #11 I536 光编成≥6 常开）"
                         "路径 (11,1,0,1,2,1,0,1)：Bind(-17, 360, DCUnique 14999903, 1, 上限) → "
                         "CreateRatioAttack(301, 1, [0.05, 0.01×v360])",
                "semantics": "ActionEvaluator case 101：v360 = min(时空侵蚀层数 / 1, 上限)；层数每次强化施技 +1（先快照后递增）、"
                             "固有 c3=99999999 帧（永久）",
                "before_after": f"第 n 次强化施技比例 5%+1%×(n−1)，无上限 → 5%+1%×min(n−1, {SKILL_CAP_NEW})，最多 {ratio_cap:.0%}",
                "frequency": "设计稿估 3 分钟施技 5–7 次 ⇒ 3 分钟内本来到不了 10 层（最多约 11%），封顶只在长战斗生效",
                "precedent": "官方 blackflower_wiz_smr22_1/_2 Bind(-17, vid, DCUnique 11, 1, 10)；本批校园希尔媞 149989、"
                             "玛格诺斯中秋、凯尔同写法",
                "untouched": "固有 14999903 上限（unique_condition c4=2147483647）不动：只封 DSL 读数，队长若将来承接逐层成长仍可读到真实层数",
                "text": "change_skill_white_wolf_gerald「额外造成一定固定伤害」、技能描述、character_text 都不写比例与层数 ⇒ 不改文案",
            },
            "pf_lv3_detoughness": {
                "time_seal_branch": [before_pf[3], after_pf[3]],
                "no_seal_branch": [before_pf[4], after_pf[4]],
                "why_only_seal_branch": "口径 B.2「尽量正好顶到上限」：只有刻印分支（光队，10 段）超 25；无刻印分支"
                                        "（非光队，5 段 ×3 = 15）本就 ≤25，压到 12.5 属未要求的削弱（复核 minor）⇒ 保留",
                "other_levels_unchanged": "Lv1 9/4.5、Lv2 16/8（≤15/20）",
            },
            "kept": {
                "skill white_wolf_gerald_1/_2 削韧": "66/73.5，技能能量 1500 按 550 折算 ≈27 ≤30（口径 B.1 保留）",
                "ability:1499993#5 月牙斩 629": "单次 3.5（2.5×1 + 0.25×4），每 10 次弹射触发（口径 B.3「其余按设计稿」："
                                             "设计稿 keep + 方案表「杰拉德（fang）3.5 保留 同意」）",
                f"leader_ability:{CID}#5": "每 35 次直击 15 倍能力伤害：造伤不是成长",
                "gauge rows": "队长 #3 CT、能力3 行3/5/7 等充能行不动（口径 A.6 / 表二本批暂缓）",
                "ability:1499994#1": "Fever 冲刺 +5 连击：追加连击不算成长",
            },
            "panel": "desc_override_black_wolf_knight 在 live 不存在 ⇒ 队长面板按行自动生成（5% / 50%），不写覆盖；"
                     "技能描述、character_text、服务端文本均不含这些数值",
            "generators": "wf_gerald_cast_growth.COUNTER_CAP=10 已同步：对 09-25 捕获的施技成长前技能树重跑 rewrite() == 本模块输出"
                          "（测试断言），它对已带 Bind 的树 fail closed；wf_gerald_percent_skill / wf_gerald_percent_revision "
                          "按旧源 sha256 fail closed、不写这些格子；无设计镜像",
            "blocked": {
                "a5_skill_growth_remainder_to_leader": "口径 A.5 要求技能里超出 10 层的无上限部分由队长技承担；队长表没有"
                    "「当前 HP 比例伤害」内容 kind（比例伤害只有 DSL CreateRatioAttack），队长里也没有按 14999903 逐层成长的行"
                    " ⇒ 无法等价搬移。选项：A 只封顶、不搬（本模块现状；3 分钟内施技 5–7 次本来到不了 10 层）；"
                    "B 队长新起一行 during 134（按固有 14999903 层数，c83 (None)）→ 光队技能伤害 +x%/层并按 A.2 放缓"
                    "（换了效果类型，需作者定 kind 与强度；D134 + 目标 5 + c83 (None) 进队长有官方 161123#0/#1、141081#1/#2 先例，本批校园希尔媞 149989 同写法、尚未发布）；"
                    "C 把 unique_condition 14999903 c4 也压到 10（与 A 同效，但堵死将来 B 的读数）",
            },
            "open_points": {
                "fang_629": "月牙斩单次 3.5 略高于口径 B.3 首句「629 每次 ≤3」；按 B.3「其余按设计稿」+ 设计稿 keep + 方案表「同意」保留。"
                            "若作者要求严格 ≤3：只把月牙斩树第一段 CreateNormalAttack p13 2.5→2.0（路径 (11,1,1,1,3,1,0,1,23,1,0,1)，1 段）"
                            "⇒ 2.0+0.25×4=3.0。复核另提示：r60 触发圈若同时碰到多个敌人，多个 4 段子判定区可能叠在同一 boss 上（该圈 CalculatedUsingMaxNumOfHits 1，大概率只触发一次；未真机验证）",
                "override_string_text": "既有文案/数据不符（不在本批）：override_string_white_wolf_gerald 写「强化弹射Lv3时，队伍全体的"
                                        "直接攻击变为4次」，PF Lv3 两支的 ACAdditionalDirectAttack 实为 6 段（[3600],[6],[1.0],[1]）；"
                                        "口径 B.5 不改 +N，只能改文案，交作者",
                "candidate_pf_lv1_lv2": "候选 PF Lv1/Lv2 文件（manifest 封口 f249ffbc…/8456436a…）仍是旧的单分支树，"
                                        "live（73e0429e…/1141a3f6…）已带时之刻印分支；本模块不读不写，属既有 store≠包 差异",
            },
            "reviewed_input_drift": [list(key) for key in REVIEWED_DRIFT],
            "capabilities": [],
            "runtime_verified": False,
        },
    }

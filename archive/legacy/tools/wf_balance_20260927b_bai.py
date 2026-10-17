# -*- coding: utf-8 -*-
'白「盛夏的咆哮」149990 ``white_tiger_summer``：2026-09-27 第二批平衡修订。\n\n依据：``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``（作者已拍板）A.2/A.3/A.6、B.1/B.2/B.6，\n设计稿 growth_design.json / down_design.json 的 149990 条目（按 live 1.4.1049 重读重推）。\n\n只做三类键级修改，其余行、其余树节点逐字保留：\n\n1. 成长（口径 A.3「已在队长技的成长 → 原位放缓」）：``leader_ability:149990`` 行4/行5（0 基 #3/#4，\n   trigger 248 FeverFrame 每满 90 帧 → 风队攻击力 kind32 / 能力伤害 kind388）c49/c50 50000 → 5000，\n   即每 1.5 秒 +50% → +5%。3 分钟触发次数 ≥30（见 ``FEVER_TICK_ESTIMATE``）⇒ 每步 ×1/10（口径 A.2）。\n   c32=(None) 保持——本来就在队长，只放缓不封顶。队长行1（每次进 Fever 风队技能槽充能 +100%，kind 35）\n   属于充能，口径 A.6「其他充能的都暂时不动」，原样保留。\n   面板 ``desc_override_white_tiger_summer`` 第 5 行同步 50% → 5%，不写「可无限」类后缀（口径 D）。\n2. 技能 Down（口径 B.1/B.6）：两档技能树里 p13=1.625 的两处 CreateNormalAttack（750 帧领域\n   SpecifyMinHitIntervalDirectly 30 ⇒ 单目标最多 26 段；技能旗分支 1 段）→ 0.75；Fever 真分支全屏一击 p13=8 不动。\n   单目标每次施放最坏（Fever 中 + 技能旗）51.875 → 28.25 ≤ 30。\n3. 强化弹射 Down（口径 B.2「每级上限 15/20/25，尽量正好顶到上限」）：PF 覆盖树碰撞块里特殊型爆裂参考点\n   （CreateReferencePoint id 101，官方 special 供体）两处 CreateNormalAttack 的 p13：\n   Lv1 5→1、Lv2 5→1.25、Lv3 6.25→1.25；格斗连打 0.5 段与格斗终结段不动。27/35/45 → 15/20/25。\n   （设计稿写「都改 1 → 15/19/24」，口径 B.2 要求正好顶到上限，Lv2/Lv3 取 1.25。）\n\n真源：角色由 flow 包 ``work/character_packs/white_tiger_summer`` 管理；mod-tools 里只有两个增量修订脚本\n``wf_summer_bai_ability.py``（Fever 判定区 params[23]→2）与 ``wf_summer_bai_fever_damage.py``（Fever 追加 75 倍），\n都不碰 p13 与队长行，对本模块输出幂等（测试断言）。PF 树/队长行的历史构建脚本\n（``work/character_packs/_wts_scripts``、``work/codex_out/emergency-takeover-20260910/.../sum_kit``）是快照，\n禁止重跑。候选包的两档技能树仍是 75 倍与 params[23] 修订之前的版本（live 已上、未回写）；本模块从 live\n整树修订后写回候选即补齐。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做\n（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，第二批 b 后缀）。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as legality
import wf_dsl
import wf_midautumn_kitlib as kitlib   # 面板规则（禁语、恒真条件文本等）

CID = "149990"
CODE = "white_tiger_summer"
PACKAGES = ["white_tiger_summer"]
PACKAGE_VERSION = {"white_tiger_summer": "1.0.3"}     # 候选 manifest 现值 1.0.2 → 1.0.3
CAPABILITIES: list[str] = []
REVIEWED_DRIFT: dict = {}     # 候选打开无漂移（manifest 与文件一致）；技能树落后 live 属于未回写，不是漂移
ELEMENT = 3                   # master/character c3：风（0 基内部元素）

LEADER = CID
CAS_LEADER = "desc_override_" + CODE
ACTION = CODE
PF_ACTION = ("master/skill/power_flip_action.orderedmap", CODE + "_pf")
SKILL_PROGRAMS = {lv: f"battle/action/skill/action/rare5/{CODE}${CODE}_{lv}" for lv in (1, 2)}
PF_PROGRAMS = {lv: f"battle/action/power_flip/action/override/{CODE}_pf${CODE}_pf_lv{lv}"
               for lv in (1, 2, 3)}

LEADER_NCOLS = 124

# ---------------------------------------------------------------- 1. Fever 每 1.5 秒成长（队长行 #3/#4）

#: 0 基行号 → 内容 kind（c45）。两行同触发、不同 kind，不合并。
FEVER_TICK_ROWS = {3: "32", 4: "388"}
FEVER_TICK_OLD, FEVER_TICK_NEW = "50000", "5000"
#: 两行放缓前的逐格指纹（全部非空列；其余列必须为空串）。
FEVER_TICK_CELLS = {
    0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: "Green", 11: "0", 18: "0",
    25: "248", 28: "9000000", 29: "9000000", 32: "(None)", 33: "0", 37: "(None)", 44: "0",
    46: "5", 47: "Green", 49: FEVER_TICK_OLD, 50: FEVER_TICK_OLD,
}
FEVER_TICK_ESTIMATE = {
    "trigger": "leader c25=248 FeverFrame，c28/c29=9000000 ⇒ 全场累计 Fever 帧每满 90 帧（1.5 秒）一次，不归零",
    "fever_frames": "Fever 基础 900 帧（每帧扣 max/900/(1+延长)）× 队长行3 Fever 时间 +50% = 1350 帧 ⇒ 每次 Fever 15 跳",
    "extension": "Fever 中 724 加槽=加剩余时长：队长能力6行2 每 35 连击 +35%（≈472 帧≈5 跳）、"
                 "「假日」期间每次技能 +35%（能力2行2）",
    "three_minutes": "下限：3 分钟 2 次 Fever 不计延长 = 2×1350/90 = 30 跳；设计稿覆盖率 60–85% ⇒ 72–102 跳",
    "tier": "≥30 次 ⇒ 每步 ×1/10（口径 A.2）：50% → 5%",
}

PANEL_LINE_INDEX = 4
PANEL_OLD_LINE = "风属性共鸣时，FEVER模式中每持续1.5秒，风属性角色攻击力＋50%、能力伤害＋50%"
PANEL_NEW_LINE = "风属性共鸣时，FEVER模式中每持续1.5秒，风属性角色攻击力＋5%、能力伤害＋5%"
PANEL_LINES = 6

# ---------------------------------------------------------------- 2/3. Down（p13）

SKILL_DOWN_OLD, SKILL_DOWN_NEW = 1.625, 0.75
FEVER_BURST_DOWN = 8                      # Fever 真分支全屏一击，保持
SKILL_DOWN_TOTAL = (51.875, 28.25)        # 单目标每次施放最坏（Fever + 技能旗），前 → 后
SKILL_DOWN_CAP = 30

#: 爆裂参考点（CreateReferencePoint，碰撞块第 5 条命令）的绑定号。
BURST_REFERENCE_ID = 101
BURST_COMMAND_INDEX = 4
PF_BURST_DOWN = {1: (5, 1), 2: (5, 1.25), 3: (6.25, 1.25)}
PF_BURST_HITS = {1: 3, 2: 4, 3: 4}        # 爆裂两判定区 MaxNumOfHits 之和
PF_FIGHT_DOWN = 0.5                       # 格斗连打每段，不动
PF_FINISH_DOWN = {1: 10.5, 2: 13, 3: 17}  # 格斗终结，不动
PF_DOWN_TOTAL = {1: (27, 15), 2: (35, 20), 3: (45, 25)}
PF_DOWN_CAP = {1: 15, 2: 20, 3: 25}

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数）。值 = digest(read(kind, key))；任一不符 ⇒ 拒绝。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", LEADER): "1ec3b9d1b535eeeab5d07d33aeb9301c037237fd39d4ab685e4295c806b7d249",
    ("cas", CAS_LEADER): "8882f7848dd8b3fb6744b0db13d962b59d23e8e11900904edd9c28602c4b0d8e",
    ("action", ACTION): "05e211f2cb48786efa512b3ff369c03f1bf87e0c4b0aa23db244f11c68049099",
    ("table", PF_ACTION): "20d565577ab5a1f7b0e051bbf4748b05fb39670606e1ed0228fe3025d403b881",
    ("dsl", SKILL_PROGRAMS[1]): "bdef4f905e54c21a4a5c57326780513c355708267cfa6650b00ab1505008ae0c",
    ("dsl", SKILL_PROGRAMS[2]): "690db42c92aae8a42cead003da75dd051ffa8390a74519b821dcfafc2f363795",
    ("dsl", PF_PROGRAMS[1]): "4c991e3349a9d6e9cfdd8f28811d6463308c9f3396aee5fe7faf64c8cf31b5a2",
    ("dsl", PF_PROGRAMS[2]): "e68c8191b51994d619a19a55d44311159beb96da9795265e004313cd66ed3e8b",
    ("dsl", PF_PROGRAMS[3]): "a118ca643afd7370ebd9b5c1a161261e268a635ce241732b17f129db2025640a",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _baseline(read: Callable[[str, Any], Any]) -> dict:
    """读取并锁定全部输入；任何一项漂移或缺失都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in BEFORE:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise ValueError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    paths = {str(level): row[7] for level, row in inputs["action", ACTION]}
    if paths != {str(lv): program for lv, program in SKILL_PROGRAMS.items()}:
        raise ValueError(f"action_skill no longer points at the reviewed skill trees: {paths}")
    if inputs["table", PF_ACTION] != [[PF_PROGRAMS[lv] for lv in (1, 2, 3)]]:
        raise ValueError("power_flip_action no longer points at the reviewed PF trees")
    return inputs


# ---------------------------------------------------------------- 队长 / 面板

def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """只改 #3/#4 的 c49/c50（50000 → 5000）；其余 4 行与两行其余列逐字保留。"""
    out = deepcopy(rows)
    if len(out) != 6 or any(len(row) != LEADER_NCOLS for row in out):
        raise ValueError("unexpected leader_ability shape")
    for index, kind in FEVER_TICK_ROWS.items():
        row, cells = out[index], {**FEVER_TICK_CELLS, 45: kind}
        if any(row[c] != v for c, v in cells.items()) or any(
                v != "" for c, v in enumerate(row) if c not in cells):
            raise ValueError(f"unexpected preimage for leader #{index} (Fever tick {kind})")
        row[49] = row[50] = FEVER_TICK_NEW
    gauge = out[0]
    if (gauge[25], gauge[45], gauge[46], gauge[49], gauge[50]) != ("8", "35", "5", "100000", "100000"):
        raise ValueError("leader #0 (enter Fever → wind gauge charge 100%) drifted; charge rows stay untouched")
    return out


def _single_text(rows: list[list[str]], key: str) -> str:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError(f"{key}: expected one single-column row")
    return rows[0][0]


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    lines = _single_text(rows, CAS_LEADER).split("\n")
    if len(lines) != PANEL_LINES or lines[PANEL_LINE_INDEX] != PANEL_OLD_LINE:
        raise ValueError(f"{CAS_LEADER}: unexpected panel text layout")
    lines[PANEL_LINE_INDEX] = PANEL_NEW_LINE
    return [["\n".join(lines)]]


# ---------------------------------------------------------------- DSL 工具

def _nodes(node, name: str, path=()):
    """先序遍历，产出 (路径, 节点)；路径是下标元组。"""
    if isinstance(node, list):
        if node and node[0] == name:
            yield path, node
        for i, child in enumerate(node):
            yield from _nodes(child, name, path + (i,))


def _down(attack) -> float:
    value = attack[13]
    if (not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict)
            or set(value[0]) != {"min", "max"} or value[0]["min"] != value[0]["max"]):
        raise ValueError(f"unexpected p13 shape: {value!r}")
    return value[0]["max"]


def _set_down(attack, value) -> None:
    attack[13] = [{"min": value, "max": value}]


def area_hits(area) -> int:
    """单目标最多命中段数：MaxNumOfHits=n；MinHitInterval=寿命//间隔+1。"""
    life, rule = area[13], area[14]
    if rule[0] == "CalculatedUsingMaxNumOfHits":
        return rule[1]
    if rule[0] == "SpecifyMinHitIntervalDirectly" and life[0] == "SpecifyHitAreaLifetimeDirectly":
        return life[1] // rule[1] + 1
    raise ValueError(f"unsupported hit-count rule {rule!r} / {life!r}")


def _area_attacks(area):
    """判定区 params[22]（下标 23）命中块里的攻击，不进嵌套判定区。"""
    found = []

    def visit(node):
        if isinstance(node, list):
            if node and node[0] == "CreateHitArea":
                return
            if node and node[0] == "CreateNormalAttack":
                found.append(node)
            for child in node:
                visit(child)
    visit(area[23])
    return found


def single_target_down(tree) -> float:
    """所有分支都走（最坏情况）的单目标总 Down = Σ 判定区段数 × 该区攻击 p13。"""
    total = 0.0
    for _, area in _nodes(tree, "CreateHitArea"):
        hits = area_hits(area)
        total += sum(hits * _down(attack) for attack in _area_attacks(area))
    return total


def dsl_problems(tree) -> list[str]:
    """AMF3 往返 + 四道 DSL 门禁（口径 D）。"""
    problems = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in legality.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in legality.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in legality.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in legality.action_dsl_hit_area_target_problems(tree)]
    return problems


# ---------------------------------------------------------------- 技能树

def skill_tree(tree) -> list:
    """两处 p13=1.625 → 0.75；Fever 真分支 p13=8 与其余节点不动。"""
    result = deepcopy(tree)
    if len(result) != 12 or result[0] != "ActionDsl" or result[10] != 0:
        raise ValueError("unexpected summer skill root")
    attacks = [node for _, node in _nodes(result, "CreateNormalAttack")]
    fever = [n for _, branch in _nodes(result, "ConditionalsFeverMode")
             for _, n in _nodes(branch[1], "CreateNormalAttack")]
    if len(attacks) != 3 or len(fever) != 1 or _down(fever[0]) != FEVER_BURST_DOWN:
        raise ValueError("summer skill must hold slash field, flag slash and one Fever burst")
    slashes = [a for a in attacks if a is not fever[0]]
    if [_down(a) for a in slashes] != [SKILL_DOWN_OLD, SKILL_DOWN_OLD]:
        raise ValueError(f"skill Down preimage drift: {[_down(a) for a in slashes]}")
    if single_target_down(result) != SKILL_DOWN_TOTAL[0]:
        raise ValueError(f"skill single-target Down drift: {single_target_down(result)}")
    for attack in slashes:
        _set_down(attack, SKILL_DOWN_NEW)
    after = single_target_down(result)
    if after != SKILL_DOWN_TOTAL[1] or after > SKILL_DOWN_CAP:
        raise ValueError(f"skill single-target Down after revision: {after}")
    return result


# ---------------------------------------------------------------- 强化弹射树

def _burst_reference(tree):
    """碰撞块第 5 条命令 = 爆裂参考点 CreateReferencePoint(-18, …, id 101)。"""
    if tree[:11] != ["ActionDsl", 2, ["None"], *[False] * 7, 0]:
        raise ValueError("PF root header drift")
    collision = tree[11][1][4]
    if collision[0] != "Event" or collision[1][0] != "CollisionOfBallAndEnemy":
        raise ValueError("PF body[4] is not the ball-enemy collision block")
    command = collision[1][5][1][BURST_COMMAND_INDEX]
    ref = command[1] if command[0] == "Command" else None
    if not ref or ref[0] != "CreateReferencePoint" or ref[1] != -18 or ref[10] != BURST_REFERENCE_ID:
        raise ValueError("PF collision block no longer starts the special burst reference point")
    return ref


def pf_tree(tree, level: int) -> list:
    """爆裂参考点内两处攻击 p13 按档改；格斗连打 0.5 与格斗终结不动。"""
    if level not in PF_BURST_DOWN:
        raise ValueError("expected PF level 1..3")
    result = deepcopy(tree)
    ref = _burst_reference(result)
    areas = [a for _, a in _nodes(ref, "CreateHitArea")]
    bursts = [a for _, a in _nodes(ref, "CreateNormalAttack")]
    old, new = PF_BURST_DOWN[level]
    if (len(areas) != 2 or len(bursts) != 2
            or any(a[2] != BURST_REFERENCE_ID for a in areas)
            or sum(area_hits(a) for a in areas) != PF_BURST_HITS[level]
            or [_down(b) for b in bursts] != [old, old]):
        raise ValueError(f"PF lv{level} special burst preimage drift")
    others = [a for _, a in _nodes(result, "CreateNormalAttack") if all(a is not b for b in bursts)]
    downs = [_down(a) for a in others]
    if downs != [PF_FIGHT_DOWN] * (len(downs) - 1) + [PF_FINISH_DOWN[level]]:
        raise ValueError(f"PF lv{level} fighter segments drift: {downs}")
    if single_target_down(result) != PF_DOWN_TOTAL[level][0]:
        raise ValueError(f"PF lv{level} single-target Down drift: {single_target_down(result)}")
    for attack in bursts:
        _set_down(attack, new)
    after = single_target_down(result)
    if after != PF_DOWN_TOTAL[level][1] or after > PF_DOWN_CAP[level]:
        raise ValueError(f"PF lv{level} Down after revision: {after}")
    return result


# ---------------------------------------------------------------- 入口

def row_problems(row: list[str]) -> list[str]:
    return (legality.client_legality_problems("leader_ability", row)
            + legality.declared_block_field_problems("leader_ability", row)
            + legality.invoke_skill_string_problems(row, set(), "leader_ability"))


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    leader = {LEADER: leader_rows(inputs["leader", LEADER])}
    cas = {CAS_LEADER: leader_text(inputs["cas", CAS_LEADER])}
    dsl = {program: skill_tree(inputs["dsl", program]) for program in SKILL_PROGRAMS.values()}
    dsl.update({program: pf_tree(inputs["dsl", program], level)
                for level, program in PF_PROGRAMS.items()})

    problems = [f"leader {LEADER}#{i}: {p}" for i, row in enumerate(leader[LEADER])
                for p in row_problems(row)]
    problems += [f"panel {CAS_LEADER}: {p}" for p in kitlib.panel_problems(cas[CAS_LEADER][0][0])]
    problems += [f"dsl {program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": {}, "leader": leader, "cas": cas, "text": {}, "table": {},
        "action": {}, "dsl": dsl, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "mod-tools/wf_balance_20260927b_bai.py",
            "spec": "第二批施工口径 A.2/A.3/A.6、B.1/B.2/B.6；growth_design/down_design 149990（按 live 1.4.1049 重推）",
            "growth": {
                f"leader_ability:{LEADER}#3": "248 FeverFrame 每1.5秒 → 风队攻击力(32) 50000→5000，c32=(None) 保持",
                f"leader_ability:{LEADER}#4": "248 FeverFrame 每1.5秒 → 风队能力伤害(388) 50000→5000，c32=(None) 保持",
                "frequency": FEVER_TICK_ESTIMATE,
                "kept_charge": f"leader_ability:{LEADER}#0 进 Fever 风队技能槽充能 +100%（kind35）属充能，口径 A.6 不动",
                "kept_limited": "ability:1499903#0/#1「假日」每2秒 攻/能伤 +50% 已限10次；技能 ACAttackPoint/ACAbilityDamage maxAccumulation 10",
                "panel": {CAS_LEADER: f"第5行：{PANEL_OLD_LINE} → {PANEL_NEW_LINE}"},
            },
            "skill_down": {
                "nodes": "两档技能 CreateNormalAttack p13 1.625→0.75（750帧领域 26 段 + 技能旗 1 段）；Fever 全屏 p13=8 保持",
                "single_target_total": {"before": SKILL_DOWN_TOTAL[0], "after": SKILL_DOWN_TOTAL[1],
                                        "cap": SKILL_DOWN_CAP},
            },
            "pf_down": {
                "nodes": "PF 覆盖树碰撞块 CreateReferencePoint(id 101) 内爆裂两攻击 p13；格斗 0.5 段与终结段保持",
                "burst_p13": {f"lv{lv}": list(v) for lv, v in PF_BURST_DOWN.items()},
                "single_target_total": {f"lv{lv}": list(v) for lv, v in PF_DOWN_TOTAL.items()},
                "cap": PF_DOWN_CAP,
                "deviation_from_design": "设计稿爆裂段都改 1（15/19/24）；口径 B.2 要求正好顶到上限，Lv2/Lv3 取 1.25（20/25）",
            },
            "descriptions_unchanged": "技能描述 / character_text / 服务端 character_text / PF 说明串不含 Down 与该成长数值",
            "candidate_catch_up": "候选两档技能树为 Fever 追加 50/60 倍、Fever 判定区 params[23]=0 的旧版（live 已是 75 倍、=2，"
                                  "wf_summer_bai_fever_damage / wf_summer_bai_ability 修订未回写）；本次按 live 整树修订写回即补齐",
            "generators": "wf_summer_bai_ability.native_reference / wf_summer_bai_fever_damage.fever_damage 不碰 p13，"
                          "对本模块输出幂等（测试断言）；PF/队长历史构建脚本（_wts_scripts、codex_out sum_kit）为快照，禁止重跑",
            "runtime_verified": False,
        },
    }

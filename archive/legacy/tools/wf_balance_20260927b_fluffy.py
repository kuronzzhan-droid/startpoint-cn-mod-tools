# -*- coding: utf-8 -*-
'2026-09-27 平衡第二批：芙拉菲「圆月下的捣糕之约」149987 ``combat_animal_moon``（风）的键级修订。\n\n口径 = ``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``（A 无上限成长 / B Down），\n设计参考 = ``growth/growth_design.json`` designs[149987]、``growth/down_design.json`` characters[149987]。\n设计稿按 live 1.4.1048 写；本模块按 live 1.4.1049 重读（本角色两版逐字相同，候选 ma-fluffy 与 live 逐字相同）。\n\n改动（其余行、其余列、其余节点逐字保留）：\n\n1. **队长 L#4/L#5**（风共鸣：每 1 次强化弹射 → 风队攻击力 / 技能伤害，不限次）：c49/c50 20000 → 2000。\n   3 分钟约 30–45 次 PF（中值 35）⇒ 口径 A.2「按实际次数、≥30 取 1/10」。设计稿（按事件标签）写的 1/5（→4000）\n   已被口径「不按事件名称」取代。\n2. **队长 L#9**（风共鸣：连击每达 250 → 自身技能伤害，不限次）：100000 → 20000。3 分钟约 15–30 次（中值 20）⇒ 1/5。\n3. **队长 L#12**（风共鸣：每 3 次强化弹射 → 风队技能伤害独立乘区 694，不限次）：5000 → 1000。约 10–15 次 ⇒ 1/5。\n   同触发的 L#10（35 充能速度）/ L#11（245 技能槽上限）是「充能」，口径 A.6 与作者「其他充能的都暂时不动」⇒ 原样。\n4. **面板**：队长 desc_override 第 3/4/6 行数值同步（只改数字，其余逐字）。\n5. **Down**：技能两档 ``combat_animal_moon_1/_2`` 八连重击 8 条 CreateNormalAttack p13 6.25 → 1.5\n   （每次施放 10×1.3636 ＋ 8×1.5 ＋ 1×1.3636 = 27，原 65；精准连击与裂地不动）；\n   629 树 ``ability_skill_combat_animal_moon``（队长 L#8 CT 6 秒、能力3 #2 CT 12 秒，均 > 3 秒 ⇒ 每次 ≤3）\n   全部 11 条 CreateNormalAttack（执行 19 段）p13 → 0.15 ⇒ 每次 2.85（原 65）。\n   「每 5 次 Lv3 强化弹射免费发动技能」的 CT 按作者原话不动；1.5 批为斩铁 donor 钉的 A1#1 c6=202 不涉及。\n\n生成器 ``wf_midautumn_kit_fluffy``：``BALANCE_B`` / LEADER / CAS_TEXTS / graft_tree / build_invoke_tree 已同步，\n测试断言生成器输出 == :func:`revise` 输出。设计镜像（design/fluffy.json 的 rework1.leader_ability.rows ＋\nrework1.balance_20260927b、rework1/panel/fluffy.json）由 :func:`sync_mirrors` 幂等同步。\n本模块只读 ``read()``；不写 live store / assets / .cdn / 候选包，不发布，不 git。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl
import wf_midautumn_kitlib as KL

CID = "149987"
CODE = "combat_animal_moon"
PACKAGES = ["ma-fluffy"]
#: 候选 manifest 现值 1.0.0；包档案 ${WF_ROOT}/pkgarchive/ma-fluffy-20260920-1.4.{940..1010} 七份全是 1.0.0 ⇒ 下一号。
PACKAGE_VERSION = {"ma-fluffy": "1.0.1"}
#: 候选已声明 panel-description-override-v2 / dash-parameter-v1 / gauge-gain-rules-v1；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 ma-fluffy 与 live 在本模块读取的全部键上逐字相同、manifest 哈希无漂移（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 3                        # master/character c3：风（0 基内部元素）
ELEMENT_TOKEN = "Green"
LEADER_NCOLS = 124

LEADER_KEY = CID
A3_KEY = f"{CID}3"                  # 只读：核对能力3 的 629 行 CT
CAS_LEADER = f"desc_override_{CODE}"
INVOKE_KEY = f"ability_skill_{CODE}"
INVOKE_PROGRAM = f"battle/action/skill/action/ability_skill/{INVOKE_KEY}${INVOKE_KEY}"
SKILL_PROGRAMS = tuple(f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in ("1", "2"))
CAS_KEYS = frozenset({f"change_skill_{CODE}", f"change_skill_2_{CODE}", INVOKE_KEY,
                      f"override_string_{CODE}_pf", CAS_LEADER,
                      *(f"desc_override_{CODE}_{slot}" for slot in (1, 2, 3, 5))})

# ---------------------------------------------------------------- 数值

#: 队长行号 → (改前, 改后)（c49/c50 同值）。
LEADER_CHANGES = {4: ("20000", "2000"), 5: ("20000", "2000"), 9: ("100000", "20000"), 12: ("5000", "1000")}
PF3_CHARGE_ROWS = (10, 11)                 # 35 / 245：充能类，本批不动
LV3_INVOKE_ROWS = (7, 8)                   # 每 5 次 Lv3 PF：226 连击 / 629 技能（CT 360 帧，作者：不动）
PESTLE_P13 = (6.25, 1.5)
SIDE_P13 = 1.3636363636363635              # 精准连击 ×10 与裂地 ×1 的 p13（不动）
INVOKE_P13 = 0.15
HITS = {"rush": 10, "pestle": 8, "finisher": 1}
CNA_P13 = 13
LEADER_629_CT = "360"                      # 队长 L#8 c33（6 秒）
ABILITY3_629_ROW, ABILITY3_629_CT = 2, "720"   # 能力3 #2 c35（12 秒）

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数；候选 ma-fluffy 1.0.0 逐字相同）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", LEADER_KEY): "2a365a22fe75429bc1bf11da4e5b2c775b3b56611062540e0ab784a591829b72",
    ("ability", A3_KEY): "cadcc2fb1fddc400d9bb02e97d0499924b0fcd9376cb9f9d69a02549701da2be",
    ("cas", CAS_LEADER): "771db1022e27c2db0a1cb1e02e3a7822c4cf012ba36d8c07018054e0bec6c1cd",
    ("dsl", SKILL_PROGRAMS[0]): "426ec82e53ce236ef773455fe23b60ac18c8239750163fa41ba20d8cbbd93b3e",
    ("dsl", SKILL_PROGRAMS[1]): "071e32e85391b73f253e835005a131e462a33055f38c5f032fc8d936d6eab635",
    ("dsl", INVOKE_PROGRAM): "071e32e85391b73f253e835005a131e462a33055f38c5f032fc8d936d6eab635",
}

# ---------------------------------------------------------------- 行指纹

_LEADER_COMMON = {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
                  11: "0", 18: "0", 37: "(None)", 44: "0"}
_PF1 = {25: "2", 28: "100000", 29: "100000", 32: "(None)", 33: "0"}
_PF3 = {25: "2", 28: "300000", 29: "300000", 32: "(None)", 33: "0"}


def _leader_cells(extra: dict[int, str], value: str) -> dict[int, str]:
    return {**_LEADER_COMMON, **extra, 49: value, 50: value}


#: 改前逐格指纹（全部非空列；其余列必须为空）。
LEADER_BEFORE = {
    4: _leader_cells({**_PF1, 45: "32", 46: "5", 47: ELEMENT_TOKEN}, LEADER_CHANGES[4][0]),
    5: _leader_cells({**_PF1, 45: "34", 46: "5", 47: ELEMENT_TOKEN}, LEADER_CHANGES[5][0]),
    9: _leader_cells({25: "12", 28: "25000000", 29: "25000000", 32: "(None)", 33: "0", 45: "34", 46: "0"},
                     LEADER_CHANGES[9][0]),
    12: _leader_cells({**_PF3, 45: "694", 46: "5", 47: ELEMENT_TOKEN}, LEADER_CHANGES[12][0]),
    # 不动但要锁住的同触发行：35/245 充能（5%）与每 5 次 Lv3 PF 两行（CT 6 秒）
    10: _leader_cells({**_PF3, 45: "35", 46: "5", 47: ELEMENT_TOKEN}, "5000"),
    11: _leader_cells({**_PF3, 45: "245", 46: "5", 47: ELEMENT_TOKEN}, "5000"),
    7: _leader_cells({25: "65", 28: "500000", 29: "500000", 32: "(None)", 33: LEADER_629_CT, 45: "226"},
                     "50000000"),
    8: {**_LEADER_COMMON, 25: "65", 28: "500000", 29: "500000", 32: "(None)", 33: LEADER_629_CT,
        45: "629", 68: INVOKE_KEY, 69: INVOKE_PROGRAM},
}

# ---------------------------------------------------------------- 面板

PANEL_CHANGES = {
    2: ("风属性共鸣时，每发动3次强化弹射，风属性角色技能充能速度＋5%、技能槽最大值＋5%、技能伤害额外乘区＋5%",
        "风属性共鸣时，每发动3次强化弹射，风属性角色技能充能速度＋5%、技能槽最大值＋5%、技能伤害额外乘区＋1%"),
    3: ("风属性共鸣时，每发动1次强化弹射，风属性角色攻击力＋20%、技能伤害＋20%、连击＋5",
        "风属性共鸣时，每发动1次强化弹射，风属性角色攻击力＋2%、技能伤害＋2%、连击＋5"),
    5: ("风属性共鸣时，每达到250连击，自身技能伤害＋100%",
        "风属性共鸣时，每达到250连击，自身技能伤害＋20%"),
}
PANEL_LINES = 7
PANEL_LV3_LINE = (4, "风属性共鸣时，每发动5次强化弹射Lv3时，连击＋500，并触发自身技能效果（不消耗技能槽，冷却时间：6秒）")


class FluffyBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise FluffyBalanceError(f"unreviewed live baseline for {kind}:{key} "
                                 f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], cells: dict[int, str]) -> bool:
    return (len(row) == LEADER_NCOLS and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


# ---------------------------------------------------------------- 词条 / 面板

def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 L#4/#5/#9/#12 c49/c50 放缓；L#7/#8/#10/#11 锁指纹不动；其余行逐字保留。"""
    if len(rows) != 13 or any(len(r) != LEADER_NCOLS for r in rows):
        raise FluffyBalanceError(f"leader {LEADER_KEY}: expected 13×{LEADER_NCOLS} rows")
    for index, cells in LEADER_BEFORE.items():
        if not _matches(rows[index], cells):
            raise FluffyBalanceError(f"leader {LEADER_KEY}#{index}: row drifted from the reviewed shape")
    out = deepcopy(rows)
    for index, (_old, new) in LEADER_CHANGES.items():
        out[index][49] = out[index][50] = new
    changed = [i for i, (a, b) in enumerate(zip(rows, out)) if a != b]
    if changed != sorted(LEADER_CHANGES):
        raise AssertionError("leader_rows touched another record")
    return out


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise FluffyBalanceError(f"{CAS_LEADER}: expected one single-column row")
    lines = rows[0][0].split("\n")
    if len(lines) != PANEL_LINES or lines[PANEL_LV3_LINE[0]] != PANEL_LV3_LINE[1]:
        raise FluffyBalanceError(f"{CAS_LEADER}: unexpected panel text layout")
    for index, (old, new) in PANEL_CHANGES.items():
        if lines[index] != old:
            raise FluffyBalanceError(f"{CAS_LEADER}: line {index + 1} drifted: {lines[index]!r}")
        lines[index] = new
    return [["\n".join(lines)]]


def panel_problems(text: str) -> list[str]:
    problems = ["uses 「／」 instead of line breaks"] if "／" in text else []
    for line in text.split("\n"):
        problems += KL.panel_problems(line)
    return problems


# ---------------------------------------------------------------- DSL

def _p13(cna) -> float:
    value = cna[CNA_P13]
    if not (isinstance(value, list) and len(value) == 1 and value[0]["min"] == value[0]["max"]):
        raise FluffyBalanceError(f"CreateNormalAttack p13 is not a flattened single level: {value!r}")
    return value[0]["max"]


def _layout(tree) -> dict[str, list]:
    """按 p13 / 位置把 11 条 CNA 归成 rush（1）/ pestle（8）/ finisher（then/else 2）。"""
    cnas = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    if len(cnas) != 11:
        raise FluffyBalanceError(f"expected 11 CreateNormalAttack, got {len(cnas)}")
    groups = {"rush": [cnas[0]], "pestle": cnas[1:9], "finisher": cnas[9:]}
    if any(cna[16] is not False for cna in cnas[:9]) or any(cna[16] is not True for cna in cnas[9:]):
        raise FluffyBalanceError("incrementCombo layout drifted (rush/pestle silent, finisher counting)")
    if cnas[9][6] != cnas[10][6] or [cnas[9][8], cnas[10][8]] != [True, False]:
        raise FluffyBalanceError("finisher then/else branch copies drifted")
    return groups


def skill_tree(tree) -> tuple[list, dict[str, Any]]:
    """技能档：八连重击 8 条 p13 6.25 → 1.5；精准连击与裂地保持 1.3636。"""
    out = deepcopy(tree)
    groups = _layout(out)
    got = {tag: sorted({_p13(c) for c in cnas}) for tag, cnas in groups.items()}
    if got != {"rush": [SIDE_P13], "pestle": [PESTLE_P13[0]], "finisher": [SIDE_P13]}:
        raise FluffyBalanceError(f"skill p13 layout drifted: {got}")
    for cna in groups["pestle"]:
        cna[CNA_P13] = [{"min": PESTLE_P13[1], "max": PESTLE_P13[1]}]
    before = SIDE_P13 * (HITS["rush"] + HITS["finisher"]) + PESTLE_P13[0] * HITS["pestle"]
    after = SIDE_P13 * (HITS["rush"] + HITS["finisher"]) + PESTLE_P13[1] * HITS["pestle"]
    return out, {"per_cast": [round(before, 6), round(after, 6)]}


def invoke_tree(tree) -> tuple[list, dict[str, Any]]:
    """629 树：全部 11 条 CNA p13 → 0.15（执行 19 段：精准 10 ＋ 八连 8 ＋ 裂地 1）。"""
    out = deepcopy(tree)
    groups = _layout(out)
    got = {tag: sorted({_p13(c) for c in cnas}) for tag, cnas in groups.items()}
    if got != {"rush": [SIDE_P13], "pestle": [PESTLE_P13[0]], "finisher": [SIDE_P13]}:
        raise FluffyBalanceError(f"invoke p13 layout drifted: {got}")
    for cnas in groups.values():
        for cna in cnas:
            cna[CNA_P13] = [{"min": INVOKE_P13, "max": INVOKE_P13}]
    before = SIDE_P13 * (HITS["rush"] + HITS["finisher"]) + PESTLE_P13[0] * HITS["pestle"]
    return out, {"per_call": [round(before, 6), round(INVOKE_P13 * sum(HITS.values()), 6)]}


def dsl_problems(tree) -> list[str]:
    problems = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    return problems


def row_problems(row: list[str]) -> list[str]:
    return (L.client_legality_problems("leader_ability", row)
            + L.declared_block_field_problems("leader_ability", row)
            + L.invoke_skill_string_problems(row, set(CAS_KEYS), "leader_ability"))


# ---------------------------------------------------------------- 入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader = _checked(read, "leader", LEADER_KEY)
    ability3 = _checked(read, "ability", A3_KEY)
    cas = _checked(read, "cas", CAS_LEADER)
    skills = {program: _checked(read, "dsl", program) for program in SKILL_PROGRAMS}
    invoke = _checked(read, "dsl", INVOKE_PROGRAM)
    # 两档只差自身攻击力提升的时长/数值（母本 141033 两档原值），伤害段结构相同；629 树 = 档 2 深拷贝
    if invoke != skills[SKILL_PROGRAMS[1]]:
        raise FluffyBalanceError("629 tree is no longer a copy of skill tier 2")

    new_leader = leader_rows(leader)
    new_cas = {CAS_LEADER: leader_text(cas)}
    trees, detoughness = {}, {}
    for program, tree in skills.items():
        trees[program], detoughness[program] = skill_tree(tree)
    trees[INVOKE_PROGRAM], detoughness[INVOKE_PROGRAM] = invoke_tree(invoke)

    # 口径 B：技能每次 ≤30；629 两个触发源 CT 6/12 秒（>3 秒）⇒ 每次 ≤3
    invoke_row = ability3[ABILITY3_629_ROW] if len(ability3) > ABILITY3_629_ROW else []
    if [invoke_row[i] if len(invoke_row) > 71 else None for i in (1, 27, 35, 47, 70, 71)] !=             ["false", "12", ABILITY3_629_CT, "629", INVOKE_KEY, INVOKE_PROGRAM]:
        raise FluffyBalanceError(f"ability {A3_KEY}#{ABILITY3_629_ROW}: 629 invoke row drifted")
    ct_seconds = min(int(new_leader[8][33]), int(invoke_row[35])) / 60
    invoke_cap = 1 if ct_seconds <= 3 else 3
    problems = [f"{program}: per cast {info['per_cast'][1]} > 30" for program, info in detoughness.items()
                if "per_cast" in info and info["per_cast"][1] > 30]
    if detoughness[INVOKE_PROGRAM]["per_call"][1] > invoke_cap:
        problems.append(f"629 per call {detoughness[INVOKE_PROGRAM]['per_call'][1]} > {invoke_cap}")
    problems += [f"leader#{i}: {p}" for i, row in enumerate(new_leader) for p in row_problems(row)]
    problems += [f"{CAS_LEADER}: {p}" for p in panel_problems(new_cas[CAS_LEADER][0][0])]
    problems += [f"dsl {program}: {p}" for program, tree in trees.items() for p in dsl_problems(tree)]
    if problems:
        raise FluffyBalanceError("; ".join(problems))

    return {
        "ability": {},
        "leader": {LEADER_KEY: new_leader},
        "cas": new_cas,
        "text": {}, "table": {}, "action": {}, "server_text": {},
        "dsl": trees,
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_fluffy.py",
            "character": f"{CID} {CODE} 芙拉菲「圆月下的捣糕之约」（风，中秋）",
            "spec": "第二批施工口径 A（无上限成长，按 3 分钟实际次数分档）/ A.6（充能不动）/ B.1（技能 ≤30）/ "
                    "B.3（629 每次 ≤3）；growth_design 149987、down_design 149987",
            "live_tail": "1.4.1049（设计稿基于 1.4.1048，本角色两版逐字相同）",
            "frequency": {
                "pf_each": "格斗/辅助 PF 队约每 4–6 秒一次强化弹射 ⇒ 3 分钟约 30–45 次（中值 35）⇒ ≥30 取 1/10"
                           "（设计稿按「每次PF」标签取 1/5=4000；口径 A.2「不按事件名称」取代之）",
                "combo_250": "每个技能周期（约 20–25 秒）连击约 700–900 后清零，跨 250 倍数 2–3 次 ⇒ 3 分钟约 15–30 次"
                             "（中值 20）⇒ 1/5",
                "pf_every_3": "约 35/3 ≈ 10–15 次 ⇒ 1/5",
            },
            "growth_3min": {
                "team_atk_skill": "每次 PF 约 35 次（30–45）：风队攻击力/技能伤害各 +700% → +70%（+60%–+90%）",
                "self_skill_combo250": "每 250 连击约 20 次（15–30）：自身技能伤害 +2000% → +400%（+300%–+600%）",
                "team_skill_ic694": "每 3 次 PF 约 12 次：风队技能伤害独立乘区 +60% → +12%",
                "unchanged_charge": "同触发 35 充能速度 / 245 技能槽上限仍各 +5%/步（引擎钳 ±100%），本批不动",
            },
            "changes": {
                f"leader:{LEADER_KEY}#4 c49/c50": "20000 → 2000（每次 PF 风队攻击力 +20% → +2%）",
                f"leader:{LEADER_KEY}#5 c49/c50": "20000 → 2000（每次 PF 风队技能伤害 +20% → +2%）",
                f"leader:{LEADER_KEY}#9 c49/c50": "100000 → 20000（每 250 连击 自身技能伤害 +100% → +20%）",
                f"leader:{LEADER_KEY}#12 c49/c50": "5000 → 1000（每 3 次 PF 风队技能伤害独立乘区 +5% → +1%）",
                f"cas:{CAS_LEADER}": "第 3/4/6 行数值同步（额外乘区＋1%；攻击力＋2%、技能伤害＋2%；自身技能伤害＋20%）",
                **{f"dsl:{program}": f"八连重击 8 条 CNA p13 6.25 → 1.5；每次施放 "
                                     f"{detoughness[program]['per_cast'][0]} → {detoughness[program]['per_cast'][1]}"
                   for program in SKILL_PROGRAMS},
                f"dsl:{INVOKE_PROGRAM}": "全部 11 条 CNA p13 → 0.15；每次调用 "
                                         f"{detoughness[INVOKE_PROGRAM]['per_call'][0]} → "
                                         f"{detoughness[INVOKE_PROGRAM]['per_call'][1]}",
            },
            "invoke_ct": {"leader_L8_frames": int(new_leader[8][33]),
                          "ability3_row2_frames": int(invoke_row[35]),
                          "min_seconds": ct_seconds, "cap_per_call": invoke_cap},
            "kept": [f"队长 L#10（35 充能速度 5%）/ L#11（245 技能槽上限 5%）：充能类，口径 A.6 不动",
                     "队长 L#7/L#8「每 5 次 Lv3 PF → 连击＋500 ＋ 触发技能」CT 360 帧：作者「芙拉菲 CT 不动」",
                     "队长 L#0-3、L#6；全部能力行（能力2 冲刺层数上限 4、技能发动限 5 次、能力3 连击≥50 限 1 次均有上限）",
                     "技能倍率 / 精准连击与裂地的 p13 / 其余 DSL 节点"],
            "generator": "wf_midautumn_kit_fluffy.py（BALANCE_B / LEADER / CAS_TEXTS / PESTLE_DETOUGHNESS / "
                         "INVOKE_DETOUGHNESS / graft_tree / build_invoke_tree 已同步）",
            "capabilities": list(CAPABILITIES),
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/fluffy.json"
PANEL_REL = BATCH / "rework1/panel/fluffy.json"
MIRROR_TAG = "balance_20260927b"
MIRROR_NOTE = ("2026-09-27 平衡第二批：队长「每发动1次强化弹射」攻击力/技能伤害 20% → 2%、「每达到250连击」"
               "自身技能伤害 100% → 20%、「每发动3次强化弹射」技能伤害额外乘区 5% → 1%（充能速度与技能槽最大值属充能，"
               "本批不动）；技能八连重击削韧 6.25 → 1.5（每次 65 → 27），技能复制（629）削韧每次 65 → 2.85。")
MIRROR_ROWS = (4, 5, 9, 12)


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等）。"""
    import wf_midautumn_kit_fluffy as K
    design, panel = deepcopy(design), deepcopy(panel)

    rows = design["rework1"]["leader_ability"]["rows"]
    if [r["index"] for r in rows] != list(range(len(K.LEADER))):
        raise ValueError("design mirror leader rows are out of step with the generator")
    for index in MIRROR_ROWS:
        donor, _source, cells, expect = K.LEADER[index]
        entry = rows[index]
        if entry["donor"] != f"official leader_ability[{donor}]":
            raise ValueError(f"design mirror L#{index} donor drifted: {entry['donor']}")
        entry["cells"] = {str(col): value for col, value in cells.items()}
        entry["desc_expected"] = expect
    design["rework1"][MIRROR_TAG] = dict(
        spec="第二批施工口径 A/B（作者 2026-09-27 拍板）＋ growth_design / down_design 149987",
        changed=[f"队长 L#4/L#5 c49/c50 20000 → {K.BALANCE_B['pf_growth']}（每次 PF，约 35 次/3 分钟 ⇒ 1/10）",
                 f"队长 L#9 c49/c50 100000 → {K.BALANCE_B['combo_growth']}（每 250 连击，约 20 次 ⇒ 1/5）",
                 f"队长 L#12 694 c49/c50 5000 → {K.BALANCE_B['pf3_growth']['694']}（每 3 次 PF，约 12 次 ⇒ 1/5）",
                 f"技能两档八连重击 p13 {K.PESTLE_DETOUGHNESS_DONOR} → {K.PESTLE_DETOUGHNESS}（每次 65 → 27）",
                 f"629 树全部 p13 → {K.INVOKE_DETOUGHNESS}（每次 65 → 2.85）"],
        kept=["队长 L#10/L#11（35/245 充能类）", "每 5 次 Lv3 PF 触发技能 CT 6 秒（作者：不动）", "队长 13 行、能力 18 条"],
        panel={K.LEADER_OVERRIDE: K.CAS_TEXTS[K.LEADER_OVERRIDE]},
        module="mod-tools/wf_balance_20260927b_fluffy.py",
    )

    want = K.CAS_TEXTS[K.LEADER_OVERRIDE].split("\n")
    lines = panel["leader"]["lines"]
    if len(lines) != len(want):
        raise ValueError("leader panel mirror line count drifted")
    for index, text in enumerate(want):
        if lines[index]["text"] != text:
            if index not in PANEL_CHANGES or lines[index]["text"] != PANEL_CHANGES[index][0]:
                raise ValueError(f"leader panel mirror line {index} drifted: {lines[index]['text']!r}")
            lines[index] = dict(lines[index], text=text, status="changed",
                                note="2026-09-27 平衡第二批：无上限成长按 3 分钟触发次数放缓")
    if [line["text"] for line in lines] != want:
        raise ValueError("leader panel mirror still differs from the generator")
    notes = [note for note in panel.get("notes", []) if not note.startswith("2026-09-27 平衡第二批")]
    panel["notes"] = notes + [MIRROR_NOTE]
    return design, panel


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """保留原文件的缩进、换行风格与末尾有无换行。"""
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

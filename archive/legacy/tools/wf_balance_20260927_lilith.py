'雷皇女 莉莉丝（139997 resistance_princess_ex）：2026-09-27 作者确认的平衡修订。\n\n直击相关的词条全部换成强化弹射（PF）口径；能力1 的冲刺间隔缩短行换成\n「自身能力伤害累计 10 次（CT 5 秒）→ 立即发动 PF Lv3 剑段」：629 载荷 + 配对 248（计 1 次 PF 发动）。\n技能两档「降低全体敌人雷耐性」的元素由 live 的水（2）改为雷（3），以 live 为准只动这一格。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做\n（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md）。\n本角色没有可重跑的生成器：``work/character_packs/resistance_princess_ex/build_workspace.py`` 是禁止重跑的\n历史 kit（L1276-1281），本模块是这批行的唯一真源。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import wf_client_legality as legality
import wf_dsl
from wf_battle_rules import DAMAGE_CAP, segment_override

CID = "139997"
CODE = "resistance_princess_ex"
PACKAGES = ["resistance_princess_ex"]
PACKAGE_VERSION = {"resistance_princess_ex": "0.1.1"}
CAPABILITIES = [DAMAGE_CAP]
ELEMENT = 2  # master/character c3：雷（0 基内部元素）；载荷攻击写 255 继承

ABILITY = {slot: f"{CID}{slot}" for slot in range(1, 7)}
LEADER = CID
PF_ACTION = ("master/skill/power_flip_action.orderedmap", "resistance_princess_ex_pf")
PF_LV3 = ("battle/action/power_flip/action/override/"
          "resistance_princess_ex_pf$resistance_princess_ex_pf_lv3")

BURST_KEY = "change_skill_resistance_princess_ex_pf_burst"
BURST_PROGRAM = ("battle/action/skill/action/ability_skill/"
                 "resistance_princess_ex_pf_burst$resistance_princess_ex_pf_burst")
# 触发词与 CT 由客户端按行自动拼接，文案只写效果本身。
BURST_TEXT = "立即发动强化弹射Lv3「剑之斩击」，伤害以强化弹射伤害计算"
#: 根头 buffTargetAs：damage-type-rules-v1 按 PF3 完整结算（通用池、分档、413 独立乘区）。
#: 未装补丁的客户端丢弃 133，按技能伤害结算与显示，不崩。
BURST_BTA = segment_override("pf3")
BURST_HITS = 5
PF3_SWORD_MULTIPLIER = 6.3
#: 原 PF3 满打 = 剑 6.3×5 + 拳 1.6667×6 + 终结 17 ≈ 58.5；载荷只带剑段，5 段 × 11.7 = 58.5。
BURST_MULTIPLIER = 11.7
BURST_HIT_AREA_BTA = 0  # 判定区位不覆盖，回落到根头 133
PF_LIFECYCLE = ("SetPowerFilpSuppress", "NotifyPowerflipEnd", "CollisionOfBallAndEnemy")

#: 触发：自身能力伤害（trigger 144，puller 0）累计 10 次（1000000），CT 300 帧＝5 秒，不限次。
#: 202 仅主位：合击位放 629 零先例（演出者硬绑主位），面板行首带 Ⓜ。
BURST_GATE = {6: "202", 13: "0", 20: "0",
              27: "144", 28: "0", 30: "1000000", 31: "1000000", 34: "(None)", 35: "300",
              39: "(None)", 46: "0"}

#: 两档技能：降低全体敌人属性耐性的 ACToleranceOfElement 在 live 写成 2（DSL 元素码＝内部+1，2=水），
#: 与描述「降低全体敌人雷耐性」不符。作者 2026-09-27：以 live 为准只把元素改成 3（雷），其余节点不动。
SKILL_PROGRAMS = tuple(f"battle/action/skill/action/rare5/resistance_princess_ex$resistance_princess_ex_{lv}"
                       for lv in (1, 2))
RESIST_FROM, RESIST_TO = 2, 3

#: 候选里两档技能 DSL 与 manifest 不一致（ACToleranceOfElement 候选=3 雷、live=2 水；
#: 2026-08-18 finalize_ring_kit.py 产物，从未发布）。候选打开时按已审漂移放行；本次写入的新 live 树
#: （live 只改元素为 3）与候选文件的树逐节点相同，回写后漂移消失。
REVIEWED_DRIFT = {
    ("common", "battle/action/skill/action/rare5/resistance_princess_ex$resistance_princess_ex_1"
               ".action.dsl.amf3.deflate"):
        "fe0b9d498b5ed9611ab4bb1aa0359ef2361a82b0699f08c647d8f0a622e905d9",
    ("common", "battle/action/skill/action/rare5/resistance_princess_ex$resistance_princess_ex_2"
               ".action.dsl.amf3.deflate"):
        "48fc347fab3e4e8ec1b9bf79b0f72a13af6ff9673f5b46e602145f9248b0789c",
}

BEFORE = {
    ("ability", ABILITY[1]): "763c96020033e7cd6d415ea33d1c22a4fcad5175f393ce9e8b0a88d68fcd4ebf",
    ("ability", ABILITY[2]): "d64d3f5bd9ea1774db8155cf21991c26fc21429f1cffc9563f4cede8de6afbeb",
    ("ability", ABILITY[3]): "2f42ccc5519d399ff8d95b9350e3f6f21f31f9a172f24dcbf2b65970c3207413",
    ("ability", ABILITY[4]): "50d2dc4c2eefb7bb6bd7237c67c0111ae75950c8ae23826ee05f10f288fcbace",
    ("ability", ABILITY[5]): "6e1c51cc945e80bbd90ef782d368be02f4cdfe03e7f56cd6738c64de0d539f10",
    ("leader", LEADER): "5364027e5d8dab88fb9988dc8f377c3e8659cb90666e7d7a16dcbd59182fcee8",
    ("table", PF_ACTION): "d9df344c7bd3fb1a37d28ced4ab91d68cdb9df487ddd74c2338b6c3892c47a61",
    ("dsl", PF_LV3): "56152f7dfbaa5d46f7c8fcf963c640f2f6283499dd10bee9044ce479f46a2d28",
    ("dsl", SKILL_PROGRAMS[0]): "d64880a39fb05ad50a6d249b8c44b33a43cefa31a69ae325875c98fc940fbca5",
    ("dsl", SKILL_PROGRAMS[1]): "c4bd9027948bd9bbe30cfbe1a1b06580c8d63a88e34b068dc44f5346111fbd4d",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _baseline(read) -> dict:
    """读取并锁定全部输入；任何一项漂移都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in BEFORE:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise ValueError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    for key in ABILITY.values():
        if key != ABILITY[6] and any(len(r) != 126 for r in inputs["ability", key]):
            raise ValueError(f"unexpected ability row width: {key}")
    if any(len(r) != 124 for r in inputs["leader", LEADER]):
        raise ValueError("unexpected leader row width")
    if inputs["table", PF_ACTION] != [[f"{PF_LV3[:-1]}{level}" for level in (1, 2, 3)]]:
        raise ValueError("power_flip_action no longer points at the reviewed PF trees")
    return inputs


def _expect(row, cells: dict, what: str):
    got = {col: row[col] for col in cells}
    if got != cells:
        raise ValueError(f"unexpected preimage for {what}: {got}")


def burst_rows(name: str) -> list[list[str]]:
    """629 载荷行与配对 248 行：前置/触发/阈值/CT 逐列相同（c0..c46）。

    行形照 live ability:1599981 行3（斩铁 629）与官方 3110096#0（248）；248 让每次追加只向
    公共 PF 次数池加 1（trigger 2 类行可读到），不按载荷多段命中重复计数。
    """
    gate = [""] * 126
    for col, value in {0: name, 1: "true", 2: "power_flip", 3: "0", 5: "0",
                       **BURST_GATE}.items():
        gate[col] = value
    invoke, count = list(gate), list(gate)
    invoke[47], invoke[70], invoke[71] = "629", BURST_KEY, BURST_PROGRAM
    count[47], count[51], count[52] = "248", "100000", "100000"
    return [invoke, count]


def ability_rows(inputs) -> dict:
    out = {}
    # 1. 能力1 行3「持续·固有139997≥1(限1次) → 自身冲刺间隔缩短20%」删除，原位放 629 + 248。
    rows = inputs["ability", ABILITY[1]]
    _expect(rows[2], {5: "1", 97: "194", 104: CID, 109: "420", 113: "20000"}, "ability1 row3")
    if len(rows) != 3 or any(r[1] != "true" for r in rows):
        raise ValueError("ability1 shape drift")
    out[ABILITY[1]] = rows[:2] + burst_rows(rows[0][0]) + rows[3:]

    # 5. 能力2 行4（背水）：持续 kind1 自身直击 200% → kind23 自身强化弹射伤害 200%。
    rows = inputs["ability", ABILITY[2]]
    _expect(rows[3], {5: "1", 97: "227", 109: "1", 110: "0", 113: "200000", 114: "200000"},
            "ability2 row4")
    rows[3][109], rows[3][110] = "23", ""
    out[ABILITY[2]] = rows

    # 6. 能力3 行1、行3：触发 20(编成直击) → 2(强化弹射)；官方 trigger 2 的 puller 为空。
    rows = inputs["ability", ABILITY[3]]
    for index, content in ((0, "354"), (2, "211")):
        _expect(rows[index], {5: "0", 27: "20", 28: "0", 47: content}, f"ability3 row{index + 1}")
        rows[index][27], rows[index][28] = "2", ""
    out[ABILITY[3]] = rows

    # 7. 能力4 行2：kind33 自身直击 50%→100% → kind55 自身强化弹射伤害 50%→100%。
    rows = inputs["ability", ABILITY[4]]
    _expect(rows[1], {5: "0", 47: "33", 48: "0", 51: "50000", 52: "100000"}, "ability4 row2")
    rows[1][47], rows[1][48] = "55", ""
    out[ABILITY[4]] = rows

    # 8. 能力5 行2：kind201 直击2次 → kind200 强化弹射所需连击数 -3。
    rows = inputs["ability", ABILITY[5]]
    _expect(rows[1], {5: "0", 47: "201", 48: "0", 51: "100000", 52: "100000"}, "ability5 row2")
    rows[1][47], rows[1][48], rows[1][51], rows[1][52] = "200", "", "300000", "300000"
    out[ABILITY[5]] = rows
    return out


def leader_rows(inputs) -> list[list[str]]:
    rows = inputs["leader", LEADER]
    # 3. 队长行4：kind33 全队(雷)直击 +200% → kind55 自身强化弹射伤害 +200%（PF 类 kind 无 target）。
    _expect(rows[3], {3: "0", 45: "33", 46: "5", 47: "Yellow", 49: "200000", 50: "200000"},
            "leader row4")
    rows[3][45], rows[3][46], rows[3][47] = "55", "", ""
    # 4. 队长行6（持续·背水 HP≥50%）：kind1 全队(雷)直击 → kind23 自身强化弹射伤害 200%。
    _expect(rows[5], {3: "1", 95: "227", 107: "1", 108: "5", 109: "Yellow",
                      111: "200000", 112: "200000"}, "leader row6")
    rows[5][107], rows[5][108], rows[5][109] = "23", "", ""
    return rows


def _tags(node):
    if isinstance(node, list):
        if node and isinstance(node[0], str):
            yield node[0]
        for child in node:
            yield from _tags(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _tags(child)


def burst_tree(pf_lv3) -> list:
    """PF Lv3 树 body[1] 剑段 CreateHitArea 整块 → 629 载荷；根头 133，不带 PF 生命周期命令。"""
    source = deepcopy(pf_lv3)
    if source[:11] != ["ActionDsl", 2, ["None"], *[False] * 7, 0]:
        raise ValueError("PF lv3 root header drift")
    sword = source[11][1][1]
    area = sword[1] if sword[0] == "Command" else None
    if not area or area[0] != "CreateHitArea" or area[2] != -18 or area[3] != ["AB"]:
        raise ValueError("PF lv3 body[1] is not the ball-anchored sword hit area")
    if area[14] != ["CalculatedUsingMaxNumOfHits", BURST_HITS] or area[24] != BURST_HIT_AREA_BTA:
        raise ValueError("PF lv3 sword hit count or damage attribution drift")
    attacks = list(wf_dsl.iter_dsl_commands(sword, "CreateNormalAttack"))
    if (len(attacks) != 1 or attacks[0][2] != 255
            or attacks[0][6] != [{"min": PF3_SWORD_MULTIPLIER, "max": PF3_SWORD_MULTIPLIER}]):
        raise ValueError("PF lv3 sword attack drift")
    attacks[0][6] = [{"min": BURST_MULTIPLIER, "max": BURST_MULTIPLIER}]
    tree = ["ActionDsl", 1, ["None"], *[False] * 7, BURST_BTA, ["Block", [sword]]]
    stray = sorted(set(_tags(tree)) & set(PF_LIFECYCLE))
    if stray:
        raise ValueError(f"629 payload carries PF lifecycle nodes: {stray}")
    return tree


def _resistance_nodes(node, out):
    if isinstance(node, list):
        if node and node[0] == "ACToleranceOfElement":
            out.append(node)
        for child in node:
            _resistance_nodes(child, out)
    return out


def skill_resistance_tree(tree) -> list:
    """技能里唯一的属性耐性降低改为雷（2→3）；其他节点逐一保持。"""
    result = deepcopy(tree)
    nodes = _resistance_nodes(result, [])
    if len(nodes) != 1 or nodes[0][2] != RESIST_FROM:
        raise ValueError(f"skill resistance-down preimage drift: {[n[2] for n in nodes]}")
    nodes[0][2] = RESIST_TO
    return result


def dsl_problems(tree) -> list[str]:
    problems = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in legality.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in legality.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in legality.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in legality.action_dsl_hit_area_target_problems(tree)]
    return problems


def row_problems(kind: str, row: list[str], cas_keys) -> list[str]:
    return (legality.client_legality_problems(kind, row)
            + legality.declared_block_field_problems(kind, row)
            + legality.invoke_skill_string_problems(row, cas_keys, kind))


def revise(read) -> dict:
    inputs = _baseline(read)
    ability = ability_rows(inputs)
    leader = {LEADER: leader_rows(inputs)}
    cas = {BURST_KEY: [[BURST_TEXT]]}
    tree = burst_tree(inputs["dsl", PF_LV3])
    skills = {program: skill_resistance_tree(inputs["dsl", program]) for program in SKILL_PROGRAMS}
    problems = [f"ability {key}#{i}: {p}" for key, rows in ability.items()
                for i, row in enumerate(rows) for p in row_problems("ability", row, set(cas))]
    problems += [f"leader {LEADER}#{i}: {p}" for i, row in enumerate(leader[LEADER])
                 for p in row_problems("leader_ability", row, set(cas))]
    problems += [f"dsl {program}: {p}" for program, t in {BURST_PROGRAM: tree, **skills}.items()
                 for p in dsl_problems(t)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": ability, "leader": leader, "cas": cas, "text": {}, "table": {},
        "action": {}, "dsl": {BURST_PROGRAM: tree, **skills}, "server_text": {},
        "new_programs": [BURST_PROGRAM],
        "notes": {
            "source": "wf_balance_20260927_lilith.py",
            "spec": "作者 2026-09-27 确认：直击相关换强化弹射；冲刺行换 629+248",
            "burst": {"trigger": "self ability damage x10 (144/puller0/1000000)",
                      "cooltime_frames": 300, "main_only": True,
                      "damage_type": f"PF3 via root buffTargetAs {BURST_BTA} ({DAMAGE_CAP})",
                      "multiplier": f"{BURST_HITS}x{BURST_MULTIPLIER}"},
            "leader_row7_realigned": "候选 leader 行7 c49/50=10000 为 1.4.864 未回写；整键取 live 5000",
            "skill_resistance_element": "两档技能降低全体敌人属性耐性：live 2(水) → 3(雷)，与描述一致；其余节点不变",
            "reviewed_input_drift": [list(key) for key in REVIEWED_DRIFT],
            "runtime_verified": False,
        },
    }

# -*- coding: utf-8 -*-
"""稻穗「秋灯雷华妖狐姬」（139995 fox_oracle_autumn）：2026-09-27 平衡调整第二批。

口径：${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md（A 无上限成长、B Down、D 模块与面板）。
设计稿（growth_design / down_design 139995）按 live 1.4.1048 写；本模块按 live 1.4.1049 重读，
行号、数值、树结构与设计稿一致（两版之间本角色未变）。

一、无上限成长（口径 A）——成长原本全部在队长表，原位放缓，能力栏不腾位：
    固有「余辉」1399952（上限 99 层，永久）每层驱动的 5 条队长 during 134 行，c111/c112 各 ×1/5：
    行2（#1）雷队 Fever 获得量（kind 18，= Fever 点成长，口径 A.6 不算充能）40% → 8%；
    行5（#4）自身强化弹射伤害 160% → 32%；行6（#5）雷队攻击力 160% → 32%；
    行7（#6）雷队能力伤害 160% → 32%；行10（#9）自身独立乘区强化弹射伤害 5% → 1%。
    分档按 3 分钟实际次数（口径 A.2）：稻穗当队长时每次进入 Fever 余辉 +2（队长行11 与能力1 行4
    两源相加，记忆卡 wf-fox-fever-afterglow-fix），3 分钟约 7–10 次 Fever ⇒ 14–20 步；放缓后正反馈
    变弱约 12–16 步。<30 ⇒ 取 1/5。
    行11（进 Fever 余辉+1）、能力1 行4（同）、能力6 行2（余辉≥10 的 724）只提供层数/资源，不动。

二、Down（口径 B）：
    1. 能力4 行2（#1）Fever 中雷队眩晕蓄积（持续 kind 19，全队）300% → 50%（口径 B.4 全队 ≤50%）。
       能力4 无覆盖文案，面板由客户端自动生成。
    2. 双段 PF（override_fox_oracle_autumn_dual_pf lv1/2/3）每级单目标削韧顶到 15/20/25（口径 B.2）。
       只改 CreateNormalAttack 的 p13（SLv {min,max} 同改），其余节点逐字保留：
       Lv1：射击 3 段 3→1.5；碰撞 5→2.1（设计 2；5 段 +0.5 正好顶 15）。          34 → 15
       Lv2：射击 2 段 0.75→0.5、4 段 1.5→1.0（设计 0.75）；碰撞 5→2.5。          37.5 → 20
       Lv3：射击 2 段 0.75 保持（设计 0.5）、3 段 0.5 保持、4 段 1.5→1.0（设计 0.75）；
            碰撞 6.25→3。                                                        46.5 → 25
       取法：碰撞主段按设计稿（Lv1 除外：射击仅 3 段，差 0.5 无法整除），差额由射击段补，
       各段数值随等级不降、且都不高于 live 原值。
       单目标口径同设计稿：射击段全计，碰撞段取最强分支（Fever+雷共鸣+35 连击，多 2 段）。

三、面板 ``desc_override_fox_oracle_autumn``（队长）：
    末行数值同步 40/160/5/160 → 8/32/1/32，不写「（可无限累积）」（口径 D 禁语）；
    第 2 行「……增加20％／首次进入时……」按口径 D「换行分行不用／」拆成两行（文字不改义）。
    「余辉」累积行的「（最多99层）」保留（本角色现有写法）。
    当队长时实际每次 Fever +2 层而面板写「累积1层」是既有偏差，设计稿明确本批不修。

生成器：这些键没有可重跑的现行生成器。历史链（wf_inaho_* / wf_newchars_r3 / wf_inaho_native_pf_r2）
全部锁定历史输入哈希（或只写历史克隆），对本模块的输出重跑会拒绝而不会回退；队长覆盖文案在 mod-tools
与 work 下都没有生成源。本模块是 leader:139995、ability:1399954、desc_override_fox_oracle_autumn
与三棵双段 PF 树现行的唯一生成源（测试断言历史生成器对新旧两态都拒绝/不覆盖）。

候选（work/character_packs/fox_oracle_autumn）：leader:139995 候选 12 行、live 11 行（1.4.864 删了
候选行1「雷队员放技能 → 雷队技能槽 4%」，未回写）；本模块按 live 整键替换，回写后候选与 live 一致。
ability:1399954、cas、三棵 PF 树候选与 live 逐字相同。

纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做
（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，第二批 b 后缀）。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import wf_client_description_legality as description
import wf_client_legality as legality
import wf_dsl

CID = "139995"
CODE = "fox_oracle_autumn"
PACKAGES = ["fox_oracle_autumn"]
#: 候选 manifest 现值 0.20260927（第一批）→ 递增。
PACKAGE_VERSION = {"fox_oracle_autumn": "0.20260927.1"}
#: 队长覆盖文案 desc_override_fox_oracle_autumn 需要 V11 面板覆盖补丁（required_client_capabilities），
#: 候选 manifest 一直漏登记（同包 desc_override_fox_oracle_autumn_2 亦同）。
CAPABILITIES = ["kyubi-panel-description-override-v1"]
#: 候选 manifest 自身零哈希漂移。
REVIEWED_DRIFT: dict = {}
ELEMENT = 2  # master/character c3：雷（0 基内部元素）

LEADER = CID
ABILITY4 = f"{CID}4"
PANEL = f"desc_override_{CODE}"
PF_KEY = f"override_{CODE}_dual_pf"
PF_ACTION = ("master/skill/power_flip_action.orderedmap", PF_KEY)
PF_PROGRAMS = {level: f"battle/action/power_flip/action/override/{PF_KEY}${PF_KEY}_lv{level}"
               for level in (1, 2, 3)}
AFTERGLOW = "1399952"  # 固有「余辉」（unique_condition c4=99）

#: live 1.4.1049 只读取数（make_read(live_only=True)）；值 = digest(read(kind, key))。
BEFORE = {
    ("leader", LEADER): "6c60a17c31bbff15f26930f67c7bc21701d888e37aaca3b9ea2478de969cef85",
    ("ability", ABILITY4): "759986cb3d60f6fc774f26f6813d8f20360139f9888c972fbb2be7fb3013a979",
    ("cas", PANEL): "0ba67371a1d0538ea6c593290b19a9cf0f4da4eaefc15b11e9a4d4a2f941895d",
    ("table", PF_ACTION): "6c380d371661f8606fe92e74f257af8b946f998b85aabc592213c712df2a3d7f",
    ("dsl", PF_PROGRAMS[1]): "d69fdb9bb87200904db3f74779a8bafc13e4481152db2622f736bc1143eb2238",
    ("dsl", PF_PROGRAMS[2]): "7a22a9de761602dd2c176657cdaf0985982b4107425d7d969d804b395123ade3",
    ("dsl", PF_PROGRAMS[3]): "22cdc78537ce222d911ecc8f3aa802063adaa3c8281feb36de26ca0656067545",
}

LEADER_NCOLS, ABILITY_NCOLS = 124, 126
SLOWDOWN = 5  # 口径 A.2：3 分钟实际 14–20 步（<30）⇒ 每步 ×1/5

#: 队长 during 134「余辉」每层行：0 起行号 -> (内容 kind c107, 对象 c108, 属性 c109, 旧强度, 新强度)。
GROWTH = {
    1: ("18", "5", "Yellow", "40000", "8000"),      # 雷队 Fever 获得量
    4: ("23", "", "", "160000", "32000"),           # 自身 强化弹射伤害
    5: ("0", "5", "Yellow", "160000", "32000"),     # 雷队 攻击力
    6: ("154", "5", "Yellow", "160000", "32000"),   # 雷队 能力伤害
    9: ("413", "", "", "5000", "1000"),             # 自身 独立乘区强化弹射伤害
}
#: 成长行的公共指纹（非空列；c107–c112 另按 GROWTH 核对）：雷编成≥6（前置 2）+ during 134 余辉每层、不封顶。
GROWTH_CELLS = {
    0: CODE, 1: "0", 3: "1", 4: "2", 7: "600000", 8: "600000", 9: "Yellow", 11: "0", 18: "0",
    83: "(None)", 95: "134", 96: "0", 98: "100000", 99: "100000", 100: "(None)",
    102: AFTERGLOW, 106: "false",
}

#: 能力4 行2（#1）：持续·Fever → 雷队眩晕蓄积（Stunify 19）。
STUN_ROW = 1
STUN_CELLS = {
    0: f"{CODE}_4", 1: "true", 2: "attack_yellow", 3: "0", 5: "1", 6: "0", 13: "0", 20: "0",
    85: "(None)", 97: "4", 108: "false", 109: "19", 110: "5", 111: "Yellow",
    113: "300000", 114: "300000",
}
STUN_NEW = "50000"  # 口径 B.4：全队 ≤50%

#: 双段 PF 每级 p13：(射击段按出现顺序的 (旧, 新), 碰撞段 (旧, 新))。碰撞段 8 个攻击节点同值。
PF_DOWN = {
    1: (((3, 1.5),), (5, 2.1)),
    2: (((0.75, 0.5), (1.5, 1.0)), (5, 2.5)),
    3: (((0.75, 0.75), (0.5, 0.5), (1.5, 1.0)), (6.25, 3.0)),
}
PF_DOWN_CAP = {1: 15, 2: 20, 3: 25}          # 口径 B.2
PF_DOWN_LIVE = {1: 34, 2: 37.5, 3: 46.5}     # 设计稿现值（单目标，碰撞取最强分支）
COLLISION_ATTACKS = 8                        # 4 分支 × (多段 + 收尾 1 段)

OLD_PANEL_LINES = (
    "雷属性共鸣时，战斗开始时自身FEVER获得量提升160％",
    "雷属性共鸣时，FEVER模式开始时雷属性角色的技能槽增加20％／首次进入时技能槽最大值提升20％",
    "雷属性共鸣时，每进入一次FEVER模式「余辉」累积1层（最多99层）",
    "雷属性共鸣时，「余辉」10层以上且非FEVER模式中，强化弹射时FEVER槽增加15％",
    "雷属性共鸣时，「余辉」每1层：雷属性角色的FEVER获得量提升40％、强化弹射伤害提升160％、"
    "独立乘区的强化弹射伤害提升5％、雷属性角色的攻击力与能力伤害提升160％",
)
NEW_PANEL_LINES = (
    "雷属性共鸣时，战斗开始时自身FEVER获得量提升160％",
    "雷属性共鸣时，FEVER模式开始时雷属性角色的技能槽增加20％",
    "雷属性共鸣时，首次进入FEVER模式时雷属性角色的技能槽最大值提升20％",
    "雷属性共鸣时，每进入一次FEVER模式「余辉」累积1层（最多99层）",
    "雷属性共鸣时，「余辉」10层以上且非FEVER模式中，强化弹射时FEVER槽增加15％",
    "雷属性共鸣时，「余辉」每1层：雷属性角色的FEVER获得量提升8％、强化弹射伤害提升32％、"
    "独立乘区的强化弹射伤害提升1％、雷属性角色的攻击力与能力伤害提升32％",
)
OLD_PANEL = "\n".join(OLD_PANEL_LINES)
NEW_PANEL = "\n".join(NEW_PANEL_LINES)


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
    if inputs["table", PF_ACTION] != [[PF_PROGRAMS[level] for level in (1, 2, 3)]]:
        raise ValueError("power_flip_action no longer points at the reviewed dual-PF trees")
    return inputs


def _matches(row: list[str], width: int, cells: dict) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


# ---------------------------------------------------------------- 队长：余辉每层放缓

def _growth_cells(kind: str, target: str, token: str, strength: str) -> dict:
    cells = {**GROWTH_CELLS, 107: kind, 111: strength, 112: strength}
    if target:
        cells[108] = target
    if token:
        cells[109] = token
    return cells


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """5 条余辉每层 during 134 行 c111/c112 ×1/5；其余 6 行逐字保留、顺序不变。"""
    out = deepcopy(rows)
    if len(out) != 11 or any(len(row) != LEADER_NCOLS for row in out):
        raise ValueError("leader 139995 shape drift")
    per_layer = [i for i, row in enumerate(out)
                 if row[3] == "1" and row[95] == "134" and row[102] == AFTERGLOW]
    if per_layer != sorted(GROWTH):
        raise ValueError(f"afterglow per-layer leader rows moved: {per_layer}")
    for index, (kind, target, token, old, new) in GROWTH.items():
        if int(old) != int(new) * SLOWDOWN:
            raise ValueError(f"leader row{index + 1}: {new} is not {old}/{SLOWDOWN}")
        if not _matches(out[index], LEADER_NCOLS, _growth_cells(kind, target, token, old)):
            raise ValueError(f"unexpected preimage for leader row{index + 1}")
        out[index][111] = out[index][112] = new
    if out[7][45] != "722" or out[7][80] != PF_KEY:
        raise ValueError("leader 722 dual-PF override row moved")
    return out


# ---------------------------------------------------------------- 能力4：Fever 中雷队眩晕蓄积

def ability4_rows(rows: list[list[str]]) -> list[list[str]]:
    out = deepcopy(rows)
    if len(out) != 2 or any(len(row) != ABILITY_NCOLS for row in out):
        raise ValueError("ability 1399954 shape drift")
    if not _matches(out[STUN_ROW], ABILITY_NCOLS, STUN_CELLS):
        raise ValueError("unexpected preimage for ability4 row2 (Fever thunder-team Stunify 300%)")
    out[STUN_ROW][113] = out[STUN_ROW][114] = STUN_NEW
    stunify = [i for i, row in enumerate(out) if row[109] in ("19", "120") or row[47] in
               ("22", "51", "183", "241")]
    if stunify != [STUN_ROW]:
        raise ValueError(f"ability4 carries other Stunify rows: {stunify}")
    return out


# ---------------------------------------------------------------- 面板

def panel_rows(rows: list[list[str]]) -> list[list[str]]:
    if rows != [[OLD_PANEL]]:
        raise ValueError(f"{PANEL}: unexpected panel text")
    return [[NEW_PANEL]]


# ---------------------------------------------------------------- 双段 PF 削韧

def _attacks(node) -> list:
    return list(wf_dsl.iter_dsl_commands(node, "CreateNormalAttack"))


def _p13(value) -> list:
    return [{"min": value, "max": value}]


def _segments(tree) -> tuple[list, list]:
    """(碰撞段 8 个攻击节点, 射击段攻击节点按出现顺序)；结构不认识就拒绝。"""
    if tree[:11] != ["ActionDsl", 1, ["None"], *[False] * 7, 0]:
        raise ValueError("dual-PF root header drift")
    body = tree[11][1]
    if len(body) != 5:
        raise ValueError(f"dual-PF body has {len(body)} top-level nodes")
    collision, beam = body[3], body[4]
    if collision[0] != "Command" or collision[1][0] != "ConditionalsFeverMode":
        raise ValueError("dual-PF special collision branch moved")
    if beam[0] != "Event" or beam[1][0] != "Wait":
        raise ValueError("dual-PF ranged beam block moved")
    if any(_attacks(node) for node in body[:3]):
        raise ValueError("dual-PF carries attacks outside the collision/beam blocks")
    return _attacks(collision), _attacks(beam)


def pf_tree(tree, level: int) -> list:
    """只改 CreateNormalAttack p13；每个节点先核对旧值。"""
    result = deepcopy(tree)
    beam_plan, (collision_old, collision_new) = PF_DOWN[level]
    collision, beam = _segments(result)
    if len(collision) != COLLISION_ATTACKS or len(beam) != len(beam_plan):
        raise ValueError(f"dual-PF lv{level} attack count drift: {len(collision)}/{len(beam)}")
    for attack in collision:
        if attack[13] != _p13(collision_old):
            raise ValueError(f"dual-PF lv{level} collision p13 drift: {attack[13]}")
        attack[13] = _p13(collision_new)
    for attack, (old, new) in zip(beam, beam_plan):
        if attack[13] != _p13(old):
            raise ValueError(f"dual-PF lv{level} beam p13 drift: {attack[13]}")
        if new != old:
            attack[13] = _p13(new)
    return result


def max_single_target_down(node) -> float:
    """单目标每次 PF 的削韧：判定区 = 段数 × 区内攻击 p13 之和；条件分支取最大；其余相加。"""
    if not isinstance(node, list) or not node:
        return 0
    head = node[0]
    if head == "CreateHitArea":
        if node[14][0] != "CalculatedUsingMaxNumOfHits":
            raise ValueError(f"unexpected hit count mode {node[14]}")
        return node[14][1] * sum(attack[13][0]["max"] for attack in _attacks(node))
    if isinstance(head, str) and head.startswith("Conditionals"):
        return max(max_single_target_down(child) for child in node[1:]
                   if isinstance(child, list) and child and child[0] == "Block")
    return sum(max_single_target_down(child) for child in node if isinstance(child, list))


# ---------------------------------------------------------------- 门禁

def dsl_problems(tree) -> list[str]:
    problems = []
    if digest(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"]) != digest(tree):
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in legality.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in legality.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in legality.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in legality.action_dsl_hit_area_target_problems(tree)]
    return problems


def row_problems(kind: str, row: list[str]) -> list[str]:
    return (legality.client_legality_problems(kind, row)
            + legality.declared_block_field_problems(kind, row)
            + legality.invoke_skill_string_problems(row, set(), kind)
            + description.description_compatibility_problems(kind, row)
            + [f"needs client capability {cap}"
               for cap in legality.required_client_capabilities(kind, row)])


def revise(read) -> dict:
    inputs = _baseline(read)
    leader = leader_rows(inputs["leader", LEADER])
    ability4 = ability4_rows(inputs["ability", ABILITY4])
    panel = panel_rows(inputs["cas", PANEL])
    trees = {PF_PROGRAMS[level]: pf_tree(inputs["dsl", PF_PROGRAMS[level]], level)
             for level in (1, 2, 3)}
    problems = [f"leader {LEADER}#{i}: {p}" for i, row in enumerate(leader)
                for p in row_problems("leader_ability", row)]
    problems += [f"ability {ABILITY4}#{i}: {p}" for i, row in enumerate(ability4)
                 for p in row_problems("ability", row)]
    problems += [f"dsl {program}: {p}" for program, tree in trees.items()
                 for p in dsl_problems(tree)]
    for level in (1, 2, 3):
        down = max_single_target_down(trees[PF_PROGRAMS[level]])
        if abs(down - PF_DOWN_CAP[level]) > 1e-9:
            problems.append(f"dual-PF lv{level} single-target Down {down} != {PF_DOWN_CAP[level]}")
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": {ABILITY4: ability4}, "leader": {LEADER: leader}, "cas": {PANEL: panel},
        "text": {}, "table": {}, "action": {}, "dsl": trees, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_inaho.py",
            "spec": "第二批施工口径 A（余辉每层队长行 ×1/5，含 kind 18 Fever 获得量）、"
                    "B.4（能力4 行2 雷队眩晕蓄积 300%→50%）、B.2（双段 PF 顶到 15/20/25）",
            "growth": {
                "slowdown": f"1/{SLOWDOWN}",
                "frequency": "当队长每次进 Fever 余辉 +2（队长行11 + 能力1 行4 同 unique 相加）；"
                             "3 分钟约 7–10 次 Fever ⇒ 14–20 步（放缓后约 12–16）；<30 取 1/5",
                "rows": {f"leader row{i + 1}": f"c107={k} {int(o) / 1000:g}% -> {int(n) / 1000:g}%"
                         for i, (k, _, _, o, n) in GROWTH.items()},
                "kept": ["leader row11 / ability1 row4（进 Fever 余辉+1）",
                         "ability6 row2（余辉≥10 且非 Fever，PF 时 Fever 槽 +15%，阈值门控资源）"],
            },
            "stun": {f"ability {ABILITY4} row{STUN_ROW + 1}": "during Fever 雷队 Stunify(19) 300% -> 50%"},
            "power_flip_down": {
                f"lv{level}": {"live": PF_DOWN_LIVE[level], "new": PF_DOWN_CAP[level],
                               "beam_p13": [list(pair) for pair in PF_DOWN[level][0]],
                               "collision_p13": list(PF_DOWN[level][1])}
                for level in (1, 2, 3)},
            "power_flip_design_delta": "相对设计稿（14.5/19/23.5）：Lv1 碰撞 2→2.1；Lv2 射击4段 0.75→1.0；"
                                       "Lv3 射击2段 0.5→保持 live 0.75、射击4段 0.75→1.0；"
                                       "碰撞主段 Lv2/Lv3 同设计稿（2.5/3）。三级正好 15/20/25",
            "panel": {PANEL: "末行数值 40/160/5/160 → 8/32/1/32；第2行按「换行分行不用／」拆成两行；"
                             "不写（可无限累积）"},
            "panel_preexisting_gap": "当队长每次 Fever 实际 +2 层、面板写「累积1层」（设计稿：本批不修）",
            "candidate_leader_realigned": "候选 leader:139995 12 行（含 1.4.864 已删的雷队员放技能→雷队4%），"
                                          "整键取 live 11 行",
            "generators": "无现行生成器；wf_inaho_* / wf_newchars_r3 / wf_inaho_native_pf_r2 哈希锁定，"
                          "对新输出重跑拒绝",
            "unchanged": ["ability3（第一批）", "leader row3（进 Fever 雷队技能槽 20%，充能暂缓）",
                          "技能 fox_oracle_autumn_1/_2（单段 20）"],
            "runtime_verified": False,
        },
    }

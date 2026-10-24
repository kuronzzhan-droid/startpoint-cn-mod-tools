"""拉夫马诺「我乃圣龙王！」（151159 golden_dragon_jr，重做的官方光龙）：2026-09-27 平衡调整第二批（Down / 削韧）。

口径（${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md，作者已拍板）B.1：技能每次施放单目标总削韧 ≤30。
设计稿 down_design.json 151159（按 live 1.4.1048 写；本模块按 live 1.4.1049 重读，数值与设计稿一致）：

- 两档技能 ``golden_dragon_jr_1`` / ``_2`` 同构：Wait(55) 的减益判定区（无 CreateNormalAttack，削韧 0）＋
  Wait(100) 的伤害判定区（场地固定点 -1，寿命 120、CalculatedUsingMaxNumOfHits 8），onHit 一条
  CreateNormalAttack p13=15 ⇒ 8 × 15 = 120。官方原版同名 DSL 是单段 15；重做（2026-08-05
  rework_golden_dragon_v2_skill）把单段改成 8 段时没调每段削韧，总量变成原版的 8 倍。
- p13 15 → 2：120 → 16（回到官方原版 15 / ★5 进化技 P50≈16 的水平）。两档写同一组数字（沿用重做时
  「前后一致」）。
- B.6：只改 CreateNormalAttack 的 p13（SLv 的 {min,max} 同改），其余逐字保留；整树 AMF3 往返一致
  （连 int/float 类型）并过四道 DSL 门禁。

无 flow 包（官方路径被 store 覆写的 reworked_official 角色，不受 flow 管）⇒ ``PACKAGES = []``，只走 wf_publish 裸表边。
设计稿风险提示：merge_official / wf_enhancement_* 这类以官方为基线的工具可能把它当作偏离官方的值回滚或误报；
另与暗龙 261089 曾同属 1.4.288 一包——本模块只返回本角色两棵技能树，不碰暗龙的键。

纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md）。
生成器：无。``mod-tools/work/rework_golden_dragon_v2_skill.py``（gitignored 一次性直写 live 的重做脚本）只改判定区寿命/
段数/倍率，p13=15 继承自官方单段树，脚本里没有 p13 常量；它带改前形状校验（寿命 25、1 段），对今天的 live 会拒绝重跑。
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json

import wf_client_legality as legality
import wf_dsl

CID = "151159"
CODE = "golden_dragon_jr"
PACKAGES: list[str] = []
PACKAGE_VERSION: dict[str, str] = {}
CAPABILITIES: list[str] = []
REVIEWED_DRIFT: dict = {}
ELEMENT = 4  # master/character c3：光（0 基内部元素）

SKILL_LEVELS = (1, 2)
SKILL_PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in SKILL_LEVELS}

#: 技能每次施放单目标总削韧上限（口径 B.1）。
SKILL_CAP = 30
HITS = 8
P13_FROM, P13_TO = 15, 2
SKILL_TOTAL = (HITS * P13_FROM, HITS * P13_TO)   # 120 → 16
TOLERANCE = 1e-9

BEFORE = {
    ("action", CODE): "bbaab7834193c23e598a506583332749f3fa76fb5d38c5a2b14a71dee2ac3569",
    ("dsl", SKILL_PROGRAMS[1]): "7b014a88cd910cd8c9741928ecc5046b920a00ea421fa3c8e77c8c6d250d1c60",
    ("dsl", SKILL_PROGRAMS[2]): "0379d07447734e39be6f43c2c2728f4bc356b9e3de5bd1d2ec0e03bfa0a9a9f6",
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
    skills = {str(inner): fields[7] for inner, fields in inputs["action", CODE]}
    if skills != {str(level): SKILL_PROGRAMS[level] for level in SKILL_LEVELS}:
        raise ValueError(f"action_skill no longer points at the reviewed skill trees: {skills}")
    return inputs


# ---------------------------------------------------------------- 单目标削韧


def _tag(node):
    return node[0] if isinstance(node, list) and node and isinstance(node[0], str) else None


def _area_hits(args) -> int:
    """判定区对单一目标的命中数：MaxNumOfHits，或「寿命 ÷ 最小间隔 + 1」，再与 Some 上限取小。"""
    lifetime, count, cap = args[13], args[14], args[15]
    if count[0] == "CalculatedUsingMaxNumOfHits":
        hits = count[1]
    elif count[0] == "SpecifyMinHitIntervalDirectly" and lifetime[0] == "SpecifyHitAreaLifetimeDirectly":
        hits = lifetime[1] // count[1] + 1
    else:
        raise ValueError(f"unreviewed hit-area count shape: {lifetime} / {count}")
    if cap[0] == "Some":
        hits = min(hits, cap[1][0]["max"])
    elif cap != ["None"]:
        raise ValueError(f"unreviewed hit-area cap shape: {cap}")
    return hits


def _p13(args):
    value = args[13]
    if (not isinstance(value, list) or len(value) != 1 or set(value[0]) != {"min", "max"}
            or value[0]["min"] != value[0]["max"]):
        raise ValueError(f"unreviewed CreateNormalAttack p13 shape: {value}")
    return value[0]["max"]


def hit_areas(tree) -> list[tuple[list, int, list]]:
    """[(CreateHitArea 参数, 单目标命中数, onHit 内 CreateNormalAttack 参数列表)]，按树序；遇未审形状拒绝。"""
    found = []

    def walk(node):
        if not isinstance(node, list):
            return
        tag = _tag(node)
        if tag and (tag.startswith("Conditionals") or tag == "Repeat"):
            raise ValueError(f"unreviewed branch/loop node: {tag}")
        if tag == "Command":
            args = node[1]
            if args[0] == "CreateNormalAttack":
                raise ValueError("CreateNormalAttack outside a hit area onHit block")
            if args[0] == "CreateHitArea":
                if (list(wf_dsl.iter_dsl_commands(args[20], "CreateNormalAttack"))
                        or list(wf_dsl.iter_dsl_commands(args[20], "CreateHitArea"))
                        or list(wf_dsl.iter_dsl_commands(args[23], "CreateHitArea"))):
                    raise ValueError("unreviewed nested hit-area shape")
                found.append((args, _area_hits(args),
                              list(wf_dsl.iter_dsl_commands(args[23], "CreateNormalAttack"))))
                return
            for child in args[1:]:
                walk(child)
            return
        for child in node:
            walk(child)

    walk(tree)
    return found


def detoughness(tree) -> float:
    """每次施放对单一目标的总削韧：Σ 判定区命中数 × onHit 里 CreateNormalAttack 的 p13。"""
    return round(sum(hits * _p13(a) for _, hits, attacks in hit_areas(tree) for a in attacks), 6)


def p13_census(tree) -> dict:
    return dict(Counter(_p13(a) for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")))


# ---------------------------------------------------------------- DSL 改写


def revise_skill_tree(tree, level: int) -> list:
    """技能第 level 档：伤害判定区（8 段）p13 15 → 2；减益判定区与其余节点不动；不改输入。"""
    what = f"skill lv{level}"
    result = deepcopy(tree)
    if result[:11] != ["ActionDsl", 1, ["None"], *[False] * 7, 0]:
        raise ValueError(f"{what}: root header drift")
    areas = hit_areas(result)
    shape = [(args[2], args[14], [_p13(a) for a in attacks]) for args, _, attacks in areas]
    if shape != [(-1, ["CalculatedUsingMaxNumOfHits", 1], []),
                 (-1, ["CalculatedUsingMaxNumOfHits", HITS], [P13_FROM])]:
        raise ValueError(f"{what}: hit-area / p13 preimage drift {shape}")
    if detoughness(result) != SKILL_TOTAL[0]:
        raise ValueError(f"{what}: detoughness preimage {detoughness(result)} != {SKILL_TOTAL[0]}")
    areas[1][2][0][13] = [{"min": P13_TO, "max": P13_TO}]
    after = detoughness(result)
    if abs(after - SKILL_TOTAL[1]) > TOLERANCE or after > SKILL_CAP:
        raise ValueError(f"{what}: detoughness {after} (want {SKILL_TOTAL[1]}, cap {SKILL_CAP})")
    return result


def dsl_problems(tree) -> list[str]:
    problems = []
    back = wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"]
    if json.dumps(back) != json.dumps(tree):   # 连 int/float 类型一起比
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in legality.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in legality.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in legality.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in legality.action_dsl_hit_area_target_problems(tree)]
    return problems


def revise(read) -> dict:
    inputs = _baseline(read)
    dsl = {SKILL_PROGRAMS[level]: revise_skill_tree(inputs["dsl", SKILL_PROGRAMS[level]], level)
           for level in SKILL_LEVELS}
    problems = [f"dsl {program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": {}, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": dsl, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_goldendragon.py",
            "spec": "第二批施工口径 B.1（技能 ≤30）、B.6；down_design 151159（按 live 1.4.1049 重读）",
            "skill_detoughness": {f"lv{level}": list(SKILL_TOTAL) for level in SKILL_LEVELS},
            "skill_p13": [P13_FROM, P13_TO],
            "hits": HITS,
            "packages": "无 flow 包（reworked_official，官方路径被 store 覆写）⇒ 只走 wf_publish 裸表边",
            "risks": ("以官方为基线的工具（merge_official / wf_enhancement_*）可能把这两棵树当作偏离官方回滚或误报；"
                      "本模块不碰暗龙 261089 的键"),
            "generators": ("无：mod-tools/work/rework_golden_dragon_v2_skill.py 是一次性直写 live 的重做脚本，"
                           "p13 继承官方单段树、无常量，且改前形状校验会拒绝对今天 live 重跑"),
            "text_sync": "技能描述、character_text、服务端文本都不含削韧数值，无需同步",
            "runtime_verified": False,
        },
    }

"""克劳斯「蚀水狩阵」（129997 claude_wolf_assassin_ex）：2026-09-27 平衡调整第二批（Down / 削韧）。

口径（${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md，作者已拍板）B.2：强化弹射每级削韧上限 15 / 20 / 25，
尽量正好顶到上限。设计稿 down_design.json 129997（按 live 1.4.1048 写；本模块按 live 1.4.1049 重读，结构与数值一致）：

- PF 覆盖树（leader 129997#0 kind 722 → power_flip_action ``claude_wolf_assassin_ex_pf`` → lv1/lv2/lv3）= 官方辅助段 ＋
  按 Wait 串联的「淬毒爪击」判定区（每爪 CalculatedUsingMaxNumOfHits 3，onHit 一条 CreateNormalAttack p13=3 + ACPoison），
  Lv1/Lv2/Lv3 = 1/3/5 爪；Lv3 另有开头一个场地固定点（-1）判定区 1 段 × p13 1。
  ⇒ 9 / 27 / 46。
- 设计稿：只改 Lv2/Lv3 爪 p13 3→1.5 得 9 / 13.5 / 23.5（Lv2、Lv3 都低于上限）。本模块按口径「尽量正好顶到上限」：
  Lv1 9 ≤ 15 不动；Lv2 爪 p13 3→2.2（9 段 × 2.2 = 19.8；Lv2 全部 9 段同一 p13，正好 20 需要 20/9 的无限小数，
  取一位小数的最大值）；Lv3 爪 p13 3→1.6（15 × 1.6 + 1 = 25，正好顶格；开头 1 段 p13=1 不动）。
- 他的「每次 PF 水队技能充能」成长属于充能（口径 A.6/表二「其他充能的都暂时不动」），本模块不读不改。
- B.6：只改 CreateNormalAttack 的 p13（SLv 的 {min,max} 同改），其余逐字保留；整树 AMF3 往返一致（连 int/float 类型）
  并过四道 DSL 门禁。

候选：``work/character_packs/claude_wolf_assassin_ex``（active.json base_package_owners 引用）。候选 manifest 0.1.0 → 0.1.1。
候选打开时有 2 条既有漂移（技能两档 DSL：候选文件与 live 逐字节相同、manifest 哈希未重封），与 PF 树无关，按已审漂移放行。
候选只认领 power_flip_action 表，PF 三档 DSL 从未进包（build_claw_pf 等直写 live）：暂存回写会把本次改的 Lv2/Lv3 两棵
作为新 root 条目加进候选（``RevisionCandidate.finish`` 的新增分支，before_sha256=None），Lv1 不变、仍只在 live。

纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md）。
生成器：无可同步的源码常量。包内 ``build_claw_pf.py`` 从 wt26 母本克隆爪击（p13=3 继承母本、脚本里没有常量），其后
``restore_pf_support.py`` / ``patch_poison_*`` / ``patch_detonate_v3.py`` 等一次性补丁又加了辅助段、毒与 Lv3 开头判定区，
它的输出早已不等于 live，且 main() 直写 live store，禁止重跑。本模块是这批 PF 数值的唯一真源。
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json

import wf_client_legality as legality
import wf_dsl

CID = "129997"
CODE = "claude_wolf_assassin_ex"
PACKAGES = ["claude_wolf_assassin_ex"]
#: 候选 manifest 现值 0.1.0 → 递增。
PACKAGE_VERSION = {"claude_wolf_assassin_ex": "0.1.1"}
CAPABILITIES: list[str] = []
ELEMENT = 1  # master/character c3：水（0 基内部元素）

_R5 = "battle/action/skill/action/rare5/"
#: 候选既有漂移（2026-09-27 审过：两档技能 DSL 候选文件与 live 逐字节相同，manifest 哈希未重封）。
REVIEWED_DRIFT = {
    ("common", f"{_R5}{CODE}${CODE}_1.action.dsl.amf3.deflate"):
        "d440501bece36c789d7c09b28a364fe858a74b21f6ca991fce7f1019f244e41a",
    ("common", f"{_R5}{CODE}${CODE}_2.action.dsl.amf3.deflate"):
        "8e4910a78f9f909e9d22d59e74be7b958d5b4882af67178d7b3f95328f01d0bf",
}

PF_ACTION = ("master/skill/power_flip_action.orderedmap", f"{CODE}_pf")
PF_LEVELS = (1, 2, 3)
PF_PROGRAMS = {level: f"battle/action/power_flip/action/override/{CODE}_pf${CODE}_pf_lv{level}"
               for level in PF_LEVELS}
#: 强化弹射每级削韧上限（口径 B.2）。
PF_CAP = {1: 15, 2: 20, 3: 25}
#: 每档：(爪数, 每爪段数, 改前爪 p13, 改后爪 p13)。Lv1 9 已在上限内，不动。
PF_PLAN = {1: (1, 3, 3, 3), 2: (3, 3, 3, 2.2), 3: (5, 3, 3, 1.6)}
#: Lv3 开头场地固定点（-1）判定区：(段数, p13)，不动。
LV3_OPENER = (1, 1)
PF_TOTAL = {1: (9, 9), 2: (27, 19.8), 3: (46, 25)}
CHANGED_LEVELS = tuple(level for level in PF_LEVELS if PF_PLAN[level][2] != PF_PLAN[level][3])
TOLERANCE = 1e-9

BEFORE = {
    ("table", PF_ACTION): "aa5f7476ba53d6fd1b7deb754093753ef8384150e3aaa29f136a1eb620636968",
    ("dsl", PF_PROGRAMS[1]): "8ea4bb1d5008c1f41d1b4229bf9239dd981301dd4ae48302561cd3f27c944b01",
    ("dsl", PF_PROGRAMS[2]): "ed2f0bf93fc8f56f5aab52037e836021c971d261543c0fbd5527cd9a1bbfe589",
    ("dsl", PF_PROGRAMS[3]): "111e65cfe546bf737f16a3872e8a53552d10168216cc8aeb55fae4ce15637e4b",
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
    if inputs["table", PF_ACTION] != [[PF_PROGRAMS[level] for level in PF_LEVELS]]:
        raise ValueError("power_flip_action no longer points at the reviewed PF trees")
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
    """每次 PF 对单一目标的总削韧：Σ 判定区命中数 × onHit 里 CreateNormalAttack 的 p13。"""
    return round(sum(hits * _p13(a) for _, hits, attacks in hit_areas(tree) for a in attacks), 6)


def p13_census(tree) -> dict:
    return dict(Counter(_p13(a) for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")))


# ---------------------------------------------------------------- DSL 改写


def _claws(tree, level: int) -> list:
    """爪击判定区（球锚定 -18、坐标 EF、每爪 3 段、onHit 一条 CreateNormalAttack）；Lv3 先核对开头判定区。"""
    claws, hits, before, _ = PF_PLAN[level]
    areas = hit_areas(tree)
    shape = [(args[2], args[3], n, [_p13(a) for a in attacks]) for args, n, attacks in areas]
    want = [(-18, ["EF"], hits, [before])] * claws
    if level == 3:
        want = [(-1, ["AB"], LV3_OPENER[0], [LV3_OPENER[1]])] + want
    if shape != want:
        raise ValueError(f"PF lv{level}: claw preimage drift {shape}")
    return areas[1:] if level == 3 else areas


def revise_pf_tree(tree, level: int) -> list:
    """PF 覆盖树第 level 档：爪击 p13 改到 PF_PLAN，Lv3 开头判定区与其余节点逐字保持；不改输入。"""
    what = f"PF lv{level}"
    result = deepcopy(tree)
    if result[:11] != ["ActionDsl", 1, ["None"], *[False] * 7, 0]:
        raise ValueError(f"{what}: root header drift")
    if abs(detoughness(result) - PF_TOTAL[level][0]) > TOLERANCE:
        raise ValueError(f"{what}: detoughness preimage {detoughness(result)} != {PF_TOTAL[level][0]}")
    after = PF_PLAN[level][3]
    for _, _, attacks in _claws(result, level):
        attacks[0][13] = [{"min": after, "max": after}]
    total = detoughness(result)
    if total > PF_CAP[level] + TOLERANCE or abs(total - PF_TOTAL[level][1]) > TOLERANCE:
        raise ValueError(f"{what}: detoughness {total} (want {PF_TOTAL[level][1]}, cap {PF_CAP[level]})")
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
    revised = {level: revise_pf_tree(inputs["dsl", PF_PROGRAMS[level]], level) for level in PF_LEVELS}
    if json.dumps(revised[1]) != json.dumps(inputs["dsl", PF_PROGRAMS[1]]):
        raise ValueError("PF lv1 must stay byte-identical (already within the cap)")
    dsl = {PF_PROGRAMS[level]: revised[level] for level in CHANGED_LEVELS}
    problems = [f"dsl {program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": {}, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": dsl, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_klaus.py",
            "spec": "第二批施工口径 B.2（PF 每级 ≤15/20/25，尽量正好顶到上限）、B.6；down_design 129997（按 live 1.4.1049 重读）",
            "pf_detoughness": {f"lv{level}": list(PF_TOTAL[level]) for level in PF_LEVELS},
            "pf_claw_p13": {f"lv{level}": [PF_PLAN[level][2], PF_PLAN[level][3]] for level in PF_LEVELS},
            "deviation_from_design": ("设计稿 Lv2/Lv3 爪 p13 3→1.5（13.5/23.5）；口径「尽量正好顶到上限」⇒ Lv2 2.2（19.8，"
                                      "正好 20 需 20/9 无限小数）、Lv3 1.6（25）；Lv1 9 不动（与设计稿同）"),
            "charge_growth": "队长行8 每次 PF 水队技能充能 +5%（kind 35）属于充能，口径 A.6 本批不动",
            "candidate_drift": "2 条既有漂移（技能两档 DSL，候选 == live、manifest 未重封）按已审放行，非本次引入",
            "candidate_new_roots": ("候选原本不含 PF 三档 DSL；回写后 Lv2/Lv3 以新 root 条目进包，Lv1 仍只在 live"
                                    "（只返回有变化的键）。若要包内 PF 族完整，由主会话决定是否另把 Lv1 原样纳入"),
            "generators": ("无可同步常量：build_claw_pf.py 的 p13 继承 wt26 母本、输出早已不等于 live 且 main() 直写 live；"
                           "后续补丁脚本都是一次性直写。本模块是唯一真源"),
            "text_sync": "PF 覆盖文案「追加「淬毒爪击」特殊强化弹射」不含数值，无需同步",
            "runtime_verified": False,
        },
    }

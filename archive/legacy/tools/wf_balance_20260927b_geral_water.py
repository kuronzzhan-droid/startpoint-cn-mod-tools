'杰拉尔（129992 unicorn_lancer_rose，水；不是光杰拉德 149999）：2026-09-27 平衡调整第二批（Down / 削韧）。\n\n口径（${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md，作者已拍板）：\n\n- B.1 技能每次施放单目标总削韧 ≤30（严格口径；作者选「严格按 30」，杰拉尔在多降的 5 名里）。\n  两档技能树（``unicorn_lancer_rose_1`` / ``_2``，按 live 1.4.1049 读取）结构相同，三段伤害：\n  「鱼叉突进」判定区（球锚定 -18、``CalculatedUsingMaxNumOfHits 12``）p13 1.5 = 18；\n  「连突」判定区（8 段）p13 1 = 8；「收尾」判定区（1 段）p13 10 = 10；合计 36。\n  只改鱼叉 CreateNormalAttack 的 p13 ``{1.5,1.5}`` → ``{1,1}``：18 → 12，合计 36 → 30。\n  复核意见 B1-P95 (a) 写的「杰拉尔 10→7」只到 33（18+8+7），不满足 ≤30；要单改收尾须 10→4（−60%），\n  而鱼叉 1.5→1 把多段段位与连突段统一到每段 1、收尾保留原母本（251002 unicorn_lancer_1）的 10，\n  改动幅度最小（本段 −33%）。倍率、连击加成、对决、浮游等节点一律不动。\n- B.6 DSL 只改 CreateNormalAttack 的 p13（每个 SLv 的 {min,max} 同改），其余逐字保留；\n  整树 AMF3 往返一致并过四道 DSL 门禁。\n- 1.5 批（4980e206 ``wf_balance_20260927_waterab``）只改了能力伤害倍率（629 追击 45→36、能力5 252 15→12）\n  与追击树，本模块不读不改那些键 ⇒ 不回退。1.5 批把这两棵技能树列为只读审计输入（``GERALD_BEFORE`` 摘要与本模块\n  ``BEFORE`` 相同 ⇒ 1.5 批没改过它们）；本批发布后它的 revise() 会对新 live fail closed——1.5 批已发布、不再重跑，属预期。\n\n文案：技能描述（action_skill c1 / character_text / 服务端 character_text「合计60/75倍」）与面板都不写削韧数值\n⇒ 无文案同步。\n\n生成器：mod-tools 里没有能重现今 live 技能树的生成器。首建 kit ``work/character_packs/_ulr_scripts/kit_dsl.py``\n（``slv(1.5)`` 鱼叉 p13）是 09-06 v1 历史构建脚本，其输出与今 live 已不同（倍率、连击加成、浮游都被后续修订改过），\n不作为同步目标；后续修订 ``wf_gerald_r2_data.revise_tree`` / ``wf_gerald_self_flying_fix.fix_tree`` 都按\n1.4.764 / 1.4.768 树哈希 fail closed（测试断言它们拒绝本模块输出，重跑不会回退）；``wf_water_balance_20260924``\n与 ``wf_balance_20260927_waterab`` 不碰技能树。本模块是这批技能 p13 的唯一真源。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做\n（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，第二批 b 后缀）。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as legality
import wf_dsl

CID = "129992"
CODE = "unicorn_lancer_rose"
PACKAGES = ["unicorn_lancer_rose"]
#: 候选 manifest 现值 0.1.14（1.5 批 waterab 回写后）→ 递增。
PACKAGE_VERSION = {"unicorn_lancer_rose": "0.1.15"}
#: 候选已声明 damage-type-rules-v1；本次只改 p13，不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 manifest 与文件逐一一致，两档技能树与 live 逐节点相同（2026-09-27 只读核对）⇒ 无已审漂移。
REVIEWED_DRIFT: dict = {}
ELEMENT = 1  # master/character c3：水（0 基内部元素）

LEVELS = ("1", "2")
SKILL_PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in LEVELS}
ACTION_KEY = CODE

#: 技能每次施放单目标总削韧上限（口径 B.1）。
SKILL_CAP = 30
#: 三段：(名称, 判定区主体, 坐标系, 最大命中数, 改前 p13, 改后 p13)。
PHASES = (
    ("lance", -18, ["GH", 1], 12, 1.5, 1),     # 18 → 12
    ("combo", 6, ["CD"], 8, 1, 1),              # 8（不动）
    ("finisher", 6, ["CD"], 1, 10, 10),         # 10（不动）
)

BEFORE = {
    ("dsl", SKILL_PROGRAMS["1"]): "28a27cfd3216e484ce44f20756b5818e2fa0c9d1e60f60eb734956acd0a3b8f7",
    ("dsl", SKILL_PROGRAMS["2"]): "87d62572a1a4303adeb2830d5d8e44ae5e9b72ac957cc4b6f7fd484ce6280891",
    ("action", ACTION_KEY): "7d8ae4069a1c4ecb7490872ca566932e2e127311b068d1bcec1e89e383c1fe6a",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _baseline(read: Callable[[str, Any], Any]) -> dict:
    """读取并锁定全部输入；任何一项漂移都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in BEFORE:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise ValueError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    programs = {str(level): fields[7] for level, fields in inputs["action", ACTION_KEY]}
    if programs != SKILL_PROGRAMS:
        raise ValueError(f"action_skill no longer points at the reviewed skill trees: {programs}")
    return inputs


# ---------------------------------------------------------------- 单目标削韧


def _tag(node):
    return node[0] if isinstance(node, list) and node and isinstance(node[0], str) else None


def _p13(value) -> list:
    return [{"min": value, "max": value}]


def area_hits(area) -> int:
    """判定区对单一目标的最大命中数（CalculatedUsingMaxNumOfHits，或 寿命÷最小间隔+1 再与 Some 上限取小）。"""
    lifetime, count, cap = area[13], area[14], area[15]
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


def hit_areas(tree) -> list[tuple[list, int, list]]:
    """[(CreateHitArea 节点, 最大命中数, onHit 内的 CreateNormalAttack 列表)]，按树序。

    判定区或攻击挂在 Repeat / Conditionals* 之下、攻击不在任何判定区 onHit 里、判定区嵌套判定区，一律拒绝。
    """
    found: list[tuple[list, int, list]] = []

    def walk(node, guarded: str | None):
        if isinstance(node, dict):
            for child in node.values():
                walk(child, guarded)
            return
        if not isinstance(node, list):
            return
        tag = _tag(node)
        if tag == "Repeat" or (tag or "").startswith("Conditionals"):
            guarded = tag
        if tag == "CreateNormalAttack":
            raise ValueError("CreateNormalAttack outside a hit area onHit block")
        if tag == "CreateHitArea":
            if guarded:
                raise ValueError(f"hit area under {guarded}")
            if (list(wf_dsl.iter_dsl_commands(node[20], "CreateNormalAttack"))
                    or list(wf_dsl.iter_dsl_commands(node[20], "CreateHitArea"))
                    or list(wf_dsl.iter_dsl_commands(node[23], "CreateHitArea"))):
                raise ValueError("unreviewed nested hit-area shape")
            found.append((node, area_hits(node),
                          list(wf_dsl.iter_dsl_commands(node[23], "CreateNormalAttack"))))
            return
        for child in node:
            walk(child, guarded)

    walk(tree, None)
    return found


def detoughness(tree) -> float:
    """每次施放对单一目标的总削韧：Σ 判定区最大命中数 × onHit 里 CreateNormalAttack 的 p13。"""
    total = 0.0
    for _, hits, attacks in hit_areas(tree):
        for attack in attacks:
            value = attack[13]
            if (not isinstance(value, list) or len(value) != 1 or set(value[0]) != {"min", "max"}
                    or value[0]["min"] != value[0]["max"]):
                raise ValueError(f"unreviewed CreateNormalAttack p13 shape: {value}")
            total += hits * value[0]["max"]
    return round(total, 6)


# ---------------------------------------------------------------- 改写


def revise_skill_tree(tree, level: str) -> list:
    """技能第 level 档：鱼叉 p13 1.5→1（36→30），其余节点逐字保持。"""
    what = f"skill lv{level}"
    result = deepcopy(tree)
    if result[:11] != ["ActionDsl", 3, ["None"], True, *[False] * 6, 0]:
        raise ValueError(f"{what}: root header drift")
    areas = hit_areas(result)
    if len(areas) != len(PHASES):
        raise ValueError(f"{what}: expected {len(PHASES)} damage phases, got {len(areas)}")
    for (name, subject, coords, hits, old, _), (area, got_hits, attacks) in zip(PHASES, areas):
        if (area[2], area[3], area[24], got_hits) != (subject, coords, 0, hits):
            raise ValueError(f"{what}: {name} hit area drift {(area[2], area[3], area[24], got_hits)}")
        if len(attacks) != 1:
            raise ValueError(f"{what}: {name} onHit must hold one CreateNormalAttack, got {len(attacks)}")
        attack = attacks[0]
        if attack[1] != area[22] or attack[2] != 255 or attack[8] is not True:
            raise ValueError(f"{what}: {name} CreateNormalAttack binding/element/combo-bonus drift")
        if attack[13] != _p13(old):
            raise ValueError(f"{what}: {name} p13 preimage drift {attack[13]}")
    for (name, *_, old, new), (_, _, attacks) in zip(PHASES, areas):
        if new != old:
            attacks[0][13] = _p13(new)
    if detoughness(result) > SKILL_CAP:
        raise ValueError(f"{what}: detoughness {detoughness(result)} > {SKILL_CAP}")
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


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    before = {level: detoughness(inputs["dsl", SKILL_PROGRAMS[level]]) for level in LEVELS}
    dsl = {SKILL_PROGRAMS[level]: revise_skill_tree(inputs["dsl", SKILL_PROGRAMS[level]], level)
           for level in LEVELS}
    problems = [f"dsl {program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    energy = {str(level): fields[4:6] for level, fields in inputs["action", ACTION_KEY]}
    return {
        "ability": {}, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": dsl, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_geral_water.py",
            "spec": "第二批施工口径 B.1（技能单目标总削韧 ≤30，严格口径）、B.6",
            "skill_detoughness": {f"lv{level}": [before[level], detoughness(dsl[SKILL_PROGRAMS[level]])]
                                  for level in LEVELS},
            "segments": {name: f"{hits}x{old} -> {hits}x{new}" for name, _, _, hits, old, new in PHASES},
            "vs_critic": ("复核 B1-P95 (a)「杰拉尔 10→7」只到 33（18+8+7），不满足 ≤30；改鱼叉 12 段 1.5→1"
                          "（18→12），收尾 10 与连突 8 不动 ⇒ 30"),
            "skill_energy": energy,
            "batch15_untouched": ("1.5 批 waterab 改的能力伤害倍率/追击树不在本模块输入与输出里；它把两棵技能树列为只读"
                                  "审计输入（摘要相同），本批发布后其 revise() 对新 live fail closed（已发布，不再重跑）"),
            "generator": ("无可重跑生成器：_ulr_scripts/kit_dsl.py 为 v1 历史构建（输出≠今 live）；"
                          "wf_gerald_r2_data / wf_gerald_self_flying_fix 按旧树哈希 fail closed"),
            "panel_text": "技能描述与面板不写削韧数值，无文案同步",
            "runtime_verified": False,
        },
    }

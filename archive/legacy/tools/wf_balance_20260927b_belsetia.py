'贝尔赛蒂亚（129952 dimension_witch_smr20_ex，水）：2026-09-27 平衡调整第二批（Down / 削韧）。\n\n口径（${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md，作者已拍板）：\n\n- B.3 能力调用技能（kind 629）每次单目标削韧 ≤3；触发 CT ≤3 秒的每次 ≤1。\n  「宙域穿刺」629 由能力3 ``1299523#1``（0 基；整键主位 c1=false）调用：trigger 2（PowerFlip）累计 3 次\n  （c30/c31=300000），限 10 次（c34），行 CT c35=0，puller 空（按 live 1.4.1049 读取核对）。\n  行 CT 虽为 0，但触发事件是「强化弹射累计 3 次」：每次发动之间至少隔 3 次完整的强化弹射\n  （每次都要重新蓄 PF 槽并播完 PF 动作），实际间隔远大于 3 秒，且整场至多 10 次 ⇒ 适用「每次 ≤3」。\n  与第二批同口径先例一致：斩铁 629（行 CT 0、自身施技）、水灵幽魂/拉比 629（行 CT 0、每次 PF）都按\n  事件自身间隔判定。若主会话/作者改按「行 CT 字面值 0 ≤3 秒」判定，只需把 ``PIERCE_P13[1]`` 改成 0.125（=1）。\n  穿刺树唯一的判定区 ``CalculatedUsingMaxNumOfHits 8``，onHit 里唯一的 CreateNormalAttack p13\n  ``{1,1}`` → ``{0.25,0.25}``：每次 8 → 2（设计稿 down_design.json 129952 行1：p13 1→0.25，8→2）。\n- B.6 DSL 只改 CreateNormalAttack 的 p13（每个 SLv 的 {min,max} 同改），其余逐字保留；\n  整树 AMF3 往返一致并过四道 DSL 门禁。\n- 能力4 ``1299524#2`` 的 629「无明幽环」（自身施技，单段 p13 1 ⇒ 每次 1）在口径以内，设计稿「不改」，本模块不读不改。\n\n文案：629 文案串 ``ability_skill_witch_ex_pierce`` 与面板（客户端自动生成）都不写削韧数值 ⇒ 无文案同步。\n\n生成器：穿刺树由候选包内 ``work/character_packs/thunder_witch_ex/build_workspace.py``\n``build_ability_skill_tree(1)`` 生成（CreateNormalAttack 的 p13 写死为 ``_mm(1, 1)``，今 live == 该函数输出），\n该文件是禁止重跑、且不在本工作单元可改范围内的包内 kit ⇒ 源码常量同步列入 needed_edits_elsewhere\n（``_mm(1, 1)`` → ``_mm(0.25, 0.25)``，只动 which == 1 分支 onHit 那一处）。测试用 AST 读取该常量，\n断言生成器与本模块输出只差这一处 p13（同步后则逐字相同）。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做\n（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，第二批 b 后缀）。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as legality
import wf_dsl

CID = "129952"
CODE = "dimension_witch_smr20_ex"
PACKAGES = ["thunder_witch_ex"]
#: 候选 manifest 现值 0.1.0 → 递增。
PACKAGE_VERSION = {"thunder_witch_ex": "0.1.1"}
CAPABILITIES: list[str] = []
#: 候选 manifest 与文件逐一一致，穿刺树与 live 逐节点相同（2026-09-27 只读核对）⇒ 无已审漂移。
REVIEWED_DRIFT: dict = {}
ELEMENT = 1  # master/character c3：水（0 基内部元素）

INVOKE_KEY, INVOKE_ROW = f"{CID}3", 1
PIERCE_KEY = "ability_skill_witch_ex_pierce"
PIERCE_PROGRAM = f"battle/action/skill/action/ability_skill/{PIERCE_KEY}${PIERCE_KEY}"

#: 629 每次上限（口径 B.3）：CT ≤3 秒（180 帧）的 ≤1，否则 ≤3。
INVOKE_CAP, INVOKE_CAP_FAST, FAST_CT_FRAMES = 3, 1, 180
#: 审查时的 629 行触发形状：(c5, c27 触发, c28 puller, c30, c31, c34 限次, c35 CT 帧, c47, c70, c71)。
#: 任何一格变化都要按「CT≤3 秒每次≤1」重新判定 ⇒ 拒绝。
REVIEWED_INVOKE = ("0", "2", "", "300000", "300000", "10", "0", "629", PIERCE_KEY, PIERCE_PROGRAM)
#: 触发事件本身的最短间隔判定（行 CT 为 0 时用）：PowerFlip 累计 3 次 ⇒ >3 秒。
EVENT_SPACING = "trigger 2 (PowerFlip) accumulates 3 power flips per fire (limit 10) => interval >> 3 s"

PIERCE_HITS = 8
PIERCE_P13 = (1, 0.25)            # 8 → 2

BEFORE = {
    ("ability", INVOKE_KEY): "06341a49a5affcbf0c731f45e1d8c4be49dc3755df15e9bb025d47f255b27ebd",
    ("dsl", PIERCE_PROGRAM): "d9107267e08f9834d36dc7c06ab9c60f05c0d00cd002e1898e8aedd67ace8988",
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
    if any(len(row) != 126 for row in inputs["ability", INVOKE_KEY]):
        raise ValueError("unexpected ability row width")
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


# ---------------------------------------------------------------- 629 触发核对与改写


def invoke_cap(row) -> int:
    """629 行的每次削韧上限：行形（触发/CT/限次/程序）与审查时一致才判定，否则拒绝重判。"""
    got = (row[5], row[27], row[28], row[30], row[31], row[34], row[35], row[47], row[70], row[71])
    if got != REVIEWED_INVOKE:
        raise ValueError(f"629 invoke row drift (re-check CT rule): {INVOKE_KEY}#{INVOKE_ROW}: {got}")
    # 行 CT 0 帧（≤3 秒），但触发事件「强化弹射累计 3 次」本身间隔远大于 3 秒 ⇒ 每次 ≤3（口径 B.3
    # 「按实际触发 CT 核对」；同批斩铁 / 水灵幽魂 / 拉比 629 同一判法）。
    return INVOKE_CAP


def revise_pierce_tree(tree, cap: int = INVOKE_CAP) -> list:
    """穿刺树：8 段 p13 1→0.25（8→2），其余节点逐字保持。"""
    result = deepcopy(tree)
    if result[:11] != ["ActionDsl", 1, ["None"], *[False] * 7, 0]:
        raise ValueError("pierce root header drift")
    areas = hit_areas(result)
    if len(areas) != 1:
        raise ValueError(f"pierce must hold one hit area, got {len(areas)}")
    area, hits, attacks = areas[0]
    if (area[2], area[3], area[24]) != (1, ["GH", 0], 4) or hits != PIERCE_HITS:
        raise ValueError(f"pierce hit area drift: {(area[2], area[3], area[24], hits)}")
    if len(attacks) != 1:
        raise ValueError(f"pierce onHit must hold one CreateNormalAttack, got {len(attacks)}")
    attack = attacks[0]
    if attack[1] != area[22] or attack[2] != 255:
        raise ValueError("pierce CreateNormalAttack binding/element drift")
    if attack[13] != _p13(PIERCE_P13[0]):
        raise ValueError(f"pierce p13 preimage drift {attack[13]}")
    attack[13] = _p13(PIERCE_P13[1])
    if detoughness(result) > cap:
        raise ValueError(f"pierce detoughness {detoughness(result)} > 629 cap {cap}")
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
    row = inputs["ability", INVOKE_KEY][INVOKE_ROW]
    cap = invoke_cap(row)
    source = inputs["dsl", PIERCE_PROGRAM]
    before = detoughness(source)
    tree = revise_pierce_tree(source, cap)
    problems = [f"dsl {PIERCE_PROGRAM}: {p}" for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": {}, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": {PIERCE_PROGRAM: tree}, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_belsetia.py",
            "spec": "第二批施工口径 B.3（629 每次 ≤3，CT≤3 秒 ≤1）、B.6；设计稿 down_design.json 129952 行1",
            "pierce": {"invoke_row": f"{INVOKE_KEY}#{INVOKE_ROW}",
                       "trigger": "PowerFlip x3 (c27=2, c30=300000), limit 10, row CT 0",
                       "event_spacing": EVENT_SPACING, "per_call_cap": cap,
                       "hits": PIERCE_HITS, "p13": list(PIERCE_P13),
                       "detoughness": [before, detoughness(tree)],
                       "literal_ct_alternative": "按行 CT 字面值（0 ≤3 秒）判 ≤1 时 PIERCE_P13[1]=0.125（8→1）"},
            "ring_unchanged": "能力4 1299524#2 629 无明幽环 单段 p13 1（每次 1，自身施技）在口径内，设计稿不改",
            "generator": ("work/character_packs/thunder_witch_ex/build_workspace.py build_ability_skill_tree(1) "
                          "的 p13 _mm(1, 1) → _mm(0.25, 0.25) 列入 needed_edits_elsewhere（包内 kit，本单元不可改）"),
            "panel_text": "629 文案与自动面板不写削韧数值，无文案同步",
            "runtime_verified": False,
        },
    }

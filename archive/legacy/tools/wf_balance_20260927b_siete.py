"""希耶提（149995 seofon_wind，风）：2026-09-27 平衡调整第二批（Down / 削韧）。

口径（${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md，作者已拍板）：

- B.3 能力调用技能（kind 629）每次单目标削韧 ≤3；**按当前 live 的实际触发 CT 核对，CT ≤3 秒的一律 ≤1**。
  「剑界回响」629 由能力6 ``1499956#0``（0 基；整键主位 c1=false）调用：trigger 23（技能发动），
  puller c28=4（除自身任一），c29=(None)，限次 (None)，行 CT c35=0（按 live 1.4.1049 读取核对）。
  触发源是「除自身以外任一队员发动技能」：行 CT 为 0，且触发事件来自多名不同队员，彼此之间没有
  间隔保证——本角色自己的技能会同时给其余风属性队员回槽（队长 #6 +35%、能力3 #1 +35%、能力5 #1 +5%），
  两名队友在 3 秒内相继施技是常态 ⇒ 实际触发间隔 ≤3 秒，适用「每次 ≤1」。
  （对照：斩铁 629 是「自身」施技，两次之间隔一个完整技能周期 >3 秒，才按 ≤3 处理。）
  回响树 5 个判定区各 ``CalculatedUsingMaxNumOfHits 1``，每个 onHit 一条 CreateNormalAttack，p13
  ``{2.0,2.0}`` → ``{0.2,0.2}``：每次 10 → 1。
  设计稿（down_design.json 149995）写的是 2→0.5（10→2.5），当时未核对触发 CT；本模块按口径 B.3
  的 CT 核对取 ≤1。若主会话/作者判定该触发按 ≤3 处理，只需把 ``ECHO_P13[1]`` 改成 0.5（=2.5）。
- B.6 DSL 只改 CreateNormalAttack 的 p13（每个 SLv 的 {min,max} 同改），其余逐字保留；
  整树 AMF3 往返一致并过四道 DSL 门禁。
- 成长（A 节）：剑神固有上限 12 层（c4=12），设计稿判定为有限成长，不动。

文案：629 文案串 ``ability_skill_seofon_wind_echo``「发动技能「剑界回响」」与自动面板都不写削韧数值 ⇒ 无文案同步。

生成器：回响树由候选包内 ``work/character_packs/seofon_wind/seofon_dsl.py`` ``build_ability_skill_tree()``
生成（纯函数，今 live == 该函数输出；每刃 ``_attack(ids[2], 33, A6_PER_BLADE, 2.0, 1.4285714285714286, …)``
的第 4 参即 p13）。该文件不在本工作单元可改范围内 ⇒ 源码常量 ``2.0`` → ``0.2`` 列入 needed_edits_elsewhere；
测试直接调用该纯函数，断言生成器与本模块输出只差这 5 处 p13（同步后则逐字相同）。
``wf_seasonal7_kit_tekuto.py`` 只借用本角色 1499955#1/#2 作 donor，与回响树无关。

纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做
（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，第二批 b 后缀）。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as legality
import wf_dsl

CID = "149995"
CODE = "seofon_wind"
PACKAGES = ["seofon_wind"]
#: 候选 manifest 现值 1.0.1 → 递增。
PACKAGE_VERSION = {"seofon_wind": "1.0.2"}
CAPABILITIES: list[str] = []
#: 候选 manifest 与文件逐一一致，回响树与 live 逐节点相同（2026-09-27 只读核对）⇒ 无已审漂移。
REVIEWED_DRIFT: dict = {}
ELEMENT = 3  # master/character c3：风（0 基内部元素）

INVOKE_KEY, INVOKE_ROW = f"{CID}6", 0
ECHO_KEY = "ability_skill_seofon_wind_echo"
ECHO_PROGRAM = f"battle/action/skill/action/ability_skill/{ECHO_KEY}${ECHO_KEY}"

#: 629 每次上限（口径 B.3）：CT ≤3 秒（180 帧）的 ≤1，否则 ≤3。
INVOKE_CAP, INVOKE_CAP_FAST, FAST_CT_FRAMES = 3, 1, 180
#: 审查时的 629 行触发形状：(c5, c27 触发, c28 puller, c29 组, c30, c31, c34 限次, c35 CT 帧, c47, c70, c71)。
REVIEWED_INVOKE = ("0", "23", "4", "(None)", "100000", "100000", "(None)", "0", "629", ECHO_KEY, ECHO_PROGRAM)
EVENT_SPACING = ("trigger 23 (SkillInvoke) with puller 4 (any other member), row CT 0, no limit: "
                 "two teammates can cast back to back => no >3 s spacing")

BLADES = 5
ECHO_P13 = (2.0, 0.2)             # 每刃 1 段；5 刃：10 → 1
ECHO_MULTIPLIER = 20.0            # 每刃倍率（不动，只作形状核对）

BEFORE = {
    ("ability", INVOKE_KEY): "6a6da6f0cbeabae530036919bedf5f9869ba21b0dd42baa62a741feab6224c6a",
    ("dsl", ECHO_PROGRAM): "7aec30b5ac04ad4cadf70feea7357be4922f392d8a6dd756632b30663142d6a6",
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
    """629 行的每次削韧上限：行形（触发/puller/CT/限次/程序）与审查时一致才判定，否则拒绝重判。"""
    got = (row[5], row[27], row[28], row[29], row[30], row[31], row[34], row[35], row[47], row[70], row[71])
    if got != REVIEWED_INVOKE:
        raise ValueError(f"629 invoke row drift (re-check CT rule): {INVOKE_KEY}#{INVOKE_ROW}: {got}")
    # 行 CT 0 帧（≤3 秒），触发事件是「除自身任一队员施技」，多名队员可在 3 秒内相继施技 ⇒ 每次 ≤1。
    return INVOKE_CAP_FAST


def revise_echo_tree(tree, cap: int = INVOKE_CAP_FAST) -> list:
    """回响树：5 刃各 1 段 p13 2.0→0.2（10→1），其余节点逐字保持。"""
    result = deepcopy(tree)
    if result[:11] != ["ActionDsl", 3, ["None"], *[False] * 7, 0]:
        raise ValueError("echo root header drift")
    areas = hit_areas(result)
    if len(areas) != BLADES:
        raise ValueError(f"echo must hold {BLADES} blades, got {len(areas)}")
    for index, (area, hits, attacks) in enumerate(areas):
        what = f"echo blade {index + 1}"
        if (area[2], area[3], area[24], hits) != (9, ["AB"], 0, 1):
            raise ValueError(f"{what}: hit area drift {(area[2], area[3], area[24], hits)}")
        if len(attacks) != 1:
            raise ValueError(f"{what}: onHit must hold one CreateNormalAttack, got {len(attacks)}")
        attack = attacks[0]
        if (attack[1] != area[22] or attack[2] != 255
                or attack[6] != _p13(ECHO_MULTIPLIER)):
            raise ValueError(f"{what}: CreateNormalAttack binding/element/multiplier drift")
        if attack[13] != _p13(ECHO_P13[0]):
            raise ValueError(f"{what}: p13 preimage drift {attack[13]}")
        attack[13] = _p13(ECHO_P13[1])
    if detoughness(result) > cap:
        raise ValueError(f"echo detoughness {detoughness(result)} > 629 cap {cap}")
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
    source = inputs["dsl", ECHO_PROGRAM]
    before = detoughness(source)
    tree = revise_echo_tree(source, cap)
    problems = [f"dsl {ECHO_PROGRAM}: {p}" for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": {}, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": {ECHO_PROGRAM: tree}, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_siete.py",
            "spec": "第二批施工口径 B.3（629 每次 ≤3，按 live 实际触发 CT 核对，CT≤3 秒 ≤1）、B.6",
            "echo": {"invoke_row": f"{INVOKE_KEY}#{INVOKE_ROW}",
                     "trigger": "SkillInvoke by any other member (c27=23, c28=4), no limit, row CT 0",
                     "event_spacing": EVENT_SPACING, "per_call_cap": cap,
                     "blades": BLADES, "p13": list(ECHO_P13),
                     "detoughness": [before, detoughness(tree)]},
            "vs_design": ("设计稿 2→0.5（10→2.5）未核对触发 CT；按口径 B.3 CT 核对取 ≤1（2→0.2，10→1）。"
                          "若判定按 ≤3，只改 ECHO_P13[1]=0.5"),
            "growth": "剑神固有上限 12 层（有限成长），本批不动",
            "generator": ("work/character_packs/seofon_wind/seofon_dsl.py build_ability_skill_tree() 每刃 "
                          "_attack(..., A6_PER_BLADE, 2.0, ...) 的 p13 2.0 → 0.2 列入 needed_edits_elsewhere"),
            "panel_text": "629 文案与自动面板不写削韧数值，无文案同步",
            "runtime_verified": False,
        },
    }

'普莉姆拉·浴衣（169992 blackflower_wiz_yukata，暗）：2026-09-27 平衡调整第二批（Down / 削韧）。\n\n口径（${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md，作者已拍板）：\n\n- B.1 技能每次施放单目标总削韧 ≤30（严格口径；作者选「严格按 30」，普莉姆拉在多降的 5 名里）。\n  两档技能树（``blackflower_wiz_yukata_1`` / ``_2``，按 live 1.4.1049 读取）结构相同：\n  「紫百合花园」判定区（寿命 160 帧、最小间隔 20 帧、Some 上限 8 ⇒ 单目标 8 段）每段 p13 2 = 16；\n  「烟花」终结判定区（``CalculatedUsingMaxNumOfHits 1``）p13 20 = 20；合计 36。\n  只改烟花 CreateNormalAttack 的 p13 ``{20,20}`` → ``{14,14}``：36 → 30（复核意见 B1-P95 修正 (a)\n  「普莉姆拉 20→14」）。花园 8×2 与倍率（含夜百合 vlv）不动。\n- B.6 DSL 只改 CreateNormalAttack 的 p13（每个 SLv 的 {min,max} 同改），其余逐字保留；\n  整树 AMF3 往返一致并过四道 DSL 门禁。\n\n文案：技能描述（action_skill c1 / character_text / 服务端 character_text）与面板都不写削韧数值 ⇒ 无文案同步。\n\n生成器：``wf_seasonal7_kit_primula.compose_tree`` 的烟花 CreateNormalAttack 原样继承官方\n``blackflower_wiz_smr22`` 的 p12（数组下标 13）=20；已在 kit 里加一条 ``log.setp(…, 12, _slv(20), _slv(14))``\n（常量 ``FINALE_DETOUGHNESS``）。设计镜像 ``work/character_packs/seasonal7-20260916/revision-20260916/primula/\nprimula_tree_{1,2}.json``（kit 门禁以它为原型）由 :func:`sync_mirrors` 幂等同步。测试断言\nkit 拼装（含特效改址）== 镜像 == :func:`revise` 输出。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件（``sync_mirrors(write=True)`` 只写设计镜像）；\n候选回写、发布由批次暂存脚本统一做（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，第二批 b 后缀）。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as legality
import wf_dsl

CID = "169992"
CODE = "blackflower_wiz_yukata"
PACKAGES = ["s7-primula"]
#: 候选 manifest 现值 1.0.0 → 递增。
PACKAGE_VERSION = {"s7-primula": "1.0.1"}
CAPABILITIES: list[str] = []
#: 候选 manifest 与文件逐一一致，两档技能树与 live 逐节点相同（2026-09-27 只读核对）⇒ 无已审漂移。
REVIEWED_DRIFT: dict = {}
ELEMENT = 5  # master/character c3：暗（0 基内部元素）

LEVELS = ("1", "2")
SKILL_PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in LEVELS}
ACTION_KEY = CODE

#: 技能每次施放单目标总削韧上限（口径 B.1）。
SKILL_CAP = 30
GARDEN_HITS, GARDEN_P13 = 8, 2    # 不动
FINALE_P13 = (20, 14)             # 36 → 30

MIRROR_DIR = "work/character_packs/seasonal7-20260916/revision-20260916/primula"
MIRRORS = {level: f"{MIRROR_DIR}/primula_tree_{level}.json" for level in LEVELS}

BEFORE = {
    ("dsl", SKILL_PROGRAMS["1"]): "c64ebc0fad0a476ea1c3d94d09567e9d3f94c6cf2f540c4ba40538a0c2def32c",
    ("dsl", SKILL_PROGRAMS["2"]): "aa956fa1ce3ef3681050c847d1fc186aa64be1c845027c2ecfdf04c322d85f7c",
    ("action", ACTION_KEY): "fd507a1473bbcdeeae562ddda9c4340705be663242ccfc80afa6f066fcd993b7",
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


def _parts(tree, what: str) -> tuple[list, list]:
    """(花园攻击, 烟花攻击)；判定区形状与绑定逐项核对。"""
    if tree[:11] != ["ActionDsl", 1, ["None"], *[False] * 7, 0]:
        raise ValueError(f"{what}: root header drift")
    areas = hit_areas(tree)
    if len(areas) != 2:
        raise ValueError(f"{what}: expected garden + finale hit areas, got {len(areas)}")
    (garden, garden_hits, garden_attacks), (finale, finale_hits, finale_attacks) = areas
    if ((garden[2], garden[3], garden[24], garden_hits, garden[14])
            != (11, ["AB"], 4, GARDEN_HITS, ["SpecifyMinHitIntervalDirectly", 20])):
        raise ValueError(f"{what}: garden hit area drift")
    if ((finale[2], finale[3], finale[24], finale_hits, finale[14])
            != (11, ["AB"], 4, 1, ["CalculatedUsingMaxNumOfHits", 1])):
        raise ValueError(f"{what}: finale hit area drift")
    if len(garden_attacks) != 1 or len(finale_attacks) != 1:
        raise ValueError(f"{what}: each hit area must hold one CreateNormalAttack")
    for area, attack in ((garden, garden_attacks[0]), (finale, finale_attacks[0])):
        if attack[1] != area[22] or attack[2] != 255:
            raise ValueError(f"{what}: CreateNormalAttack binding/element drift")
    if garden_attacks[0][13] != _p13(GARDEN_P13):
        raise ValueError(f"{what}: garden p13 drift {garden_attacks[0][13]}")
    return garden_attacks[0], finale_attacks[0]


def revise_skill_tree(tree, level: str) -> list:
    """技能第 level 档：烟花 p13 20→14（36→30），其余节点逐字保持。"""
    what = f"skill lv{level}"
    result = deepcopy(tree)
    _, finale = _parts(result, what)
    if finale[13] != _p13(FINALE_P13[0]):
        raise ValueError(f"{what}: finale p13 preimage drift {finale[13]}")
    finale[13] = _p13(FINALE_P13[1])
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
            "source": "wf_balance_20260927b_primula.py",
            "spec": "第二批施工口径 B.1（技能单目标总削韧 ≤30，严格口径）、B.6；复核 B1-P95 (a) 普莉姆拉 20→14",
            "skill_detoughness": {f"lv{level}": [before[level], detoughness(dsl[SKILL_PROGRAMS[level]])]
                                  for level in LEVELS},
            "segments": {"garden": f"{GARDEN_HITS}x{GARDEN_P13} (unchanged)",
                         "finale": f"1x{FINALE_P13[0]} -> 1x{FINALE_P13[1]}"},
            "skill_energy": energy,
            "generator": ("wf_seasonal7_kit_primula.compose_tree 已加 HA_F.CNA p12 20→14（FINALE_DETOUGHNESS）；"
                          "设计镜像 revision-20260916/primula/primula_tree_{1,2}.json 由 sync_mirrors 同步"),
            "panel_text": "技能描述与面板不写削韧数值，无文案同步",
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像


def mirror_tree(tree, level: str) -> list:
    """镜像树的目标形：改前形 → 本批输出；已是本批形 → 原样（幂等）；其它 → 拒绝。"""
    _, finale = _parts(deepcopy(tree), f"mirror lv{level}")
    if finale[13] == _p13(FINALE_P13[1]):
        return deepcopy(tree)
    return revise_skill_tree(tree, level)


def sync_mirrors(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回两份设计镜像树；返回有变化的相对路径。"""
    changed = []
    for level in LEVELS:
        path = Path(root) / MIRRORS[level]
        raw = path.read_bytes()
        old = json.loads(raw)
        new = mirror_tree(old, level)
        if json.dumps(new) != json.dumps(old):
            changed.append(MIRRORS[level])
            if write:
                # 镜像原格式：indent=1、ensure_ascii=False、行尾与原文件一致（现为 CRLF）。
                text = json.dumps(new, ensure_ascii=False, indent=1) + "\n"
                if b"\r\n" in raw:
                    text = text.replace("\n", "\r\n")
                path.write_bytes(text.encode("utf-8"))
    return changed


if __name__ == "__main__":
    import sys
    here = Path(__file__).resolve().parent
    pass  # Imports resolve from this checkout/package, not external source copies.
    result = sync_mirrors(here.parent, write="--write" in sys.argv[1:])
    print(json.dumps({"changed": result, "write": "--write" in sys.argv[1:]}, ensure_ascii=False))

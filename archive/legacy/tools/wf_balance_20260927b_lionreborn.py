'玛格诺斯「燎原之炎」（119996 lion_swordman_reborn）：2026-09-27 平衡调整第二批（Down / 削韧）。\n\n口径（${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md，作者已拍板）与设计稿 down_design.json 119996\n（设计稿按 live 1.4.1048 写；本模块按 live 1.4.1049 重读、重算，行号与数值与设计稿所引一致）：\n\n1. B.4 眩晕蓄积（瞬发 kind 51）自身 ≤100%：能力5 行2（``1199965#1``，0 基）「永恒之火（固有 119996）≥1 时\n   自身眩晕蓄积 600%」c51/c52 600000→100000。前置（188）、行1（Fever 点 200%）与 c1 都不动。\n   能力5 没有 desc_override（面板由客户端按数值自动生成），无文案要同步。\n2. B.2 强化弹射每级削韧 ≤15/20/25，尽量正好顶到上限：PF 覆盖树（leader 119996#4 kind 722 →\n   power_flip_action ``lion_swordman_reborn_pf`` → lv1/lv2/lv3）= 开头剑士扫击（球锚定 body[1]，\n   最多 3/4/5 段，p13 1.5/2/3）+ 撞敌后特殊爆裂（参考点判定区，最小间隔 7 帧、寿命 40、Some 3/4/4，p13 5/5/6.25）。\n   剑士扫击 p13 → 0：19.5/28/40 → 15/20/25（爆裂段本身就是特殊 PF 每级上限，正好顶格）。\n3. B.1 技能每次施放单目标总削韧 ≤30（严格口径，燎原在作者点名的 5 名里）：两档技能树同构 =\n   猛击地面 1 段 × 10（官方 lion_swordman_playable 111129 母本原值）+ 爆炸 8 段 × 1.0 + 灼烧领域\n   （寿命 840 / 间隔 50 → 17，Some 16）16 段 × 1.0 = 34。\n   本模块只降 MOD 追加的 24 段：p13 1.0 → 0.8（官方 17–40 段技能每段削韧 P50 = 0.8，设计稿官方基线），\n   34 → 10 + 6.4 + 12.8 = 29.2 ≤ 30；官方母本的猛击 10 不动。\n   复核 B1-P95 给的「10→7.5 或 24 段 1→0.85」是按 P95≈32 算的（31.5 / 30.4），不满足本批 ≤30，未采用。\n4. B.6 DSL 只改 CreateNormalAttack 的 p13（每个 SLv 的 {min,max} 同改），其余逐字保留；整树 AMF3 往返一致\n   （连 int/float 类型）并过四道 DSL 门禁。\n\n无 flow 包（``work/character_packs/lion_swordman_reborn`` 存在，但未被 .cdn/cn/character-releases/active.json\n引用）⇒ ``PACKAGES = []``，改完只走 wf_publish 裸表边。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md）。\n生成源（包内历史 kit，禁止重跑，只同步了源码常量）：\n- ``work/character_packs/lion_swordman_reborn/build_pf.py`` ``KNIGHT[*]["c1"]``（剑士扫击 p13）1.5/2/3 → 0.0，\n  ``spin_hit_area(level)`` 与本模块输出的 PF body[1] 逐节点相同（测试断言）。\n- ``work/character_packs/lion_swordman_reborn/build_skill_dsl.py`` ``TICK_DETOUGHNESS``（爆炸 / 领域每段 p13）\n  1.0 → 0.8；``build_field`` 与输出逐节点相同，``build_blast`` 除两条特效路径（该脚本之后被特效族搬家到\n  ``skill_unique/lion_swordman_reborn/zenith_explosion/``，改前就不等）外逐节点相同。\n- ``apply_m_batch.py``（能力5 眩晕蓄积行的原始写入者）是一次性直写 live 的迁移脚本、不幂等，不是生成器，未改。\n'
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json

import wf_client_legality as legality
import wf_dsl

CID = "119996"
CODE = "lion_swordman_reborn"
#: 无 flow 包：只暂存 live 表/DSL，不回写候选（口径 D 节）。
PACKAGES: list[str] = []
PACKAGE_VERSION: dict[str, str] = {}
CAPABILITIES: list[str] = []
REVIEWED_DRIFT: dict = {}
ELEMENT = 0  # master/character c3：火（0 基内部元素）

ABILITY5 = f"{CID}5"
STUN_ROW = 1                      # 0 基；面板/设计稿里的「行2」
STUN_FROM, STUN_TO = "600000", "100000"
SELF_STUN_CAP = 100000            # 口径 B.4：自身 ≤100%

PF_ACTION = ("master/skill/power_flip_action.orderedmap", f"{CODE}_pf")
PF_LEVELS = (1, 2, 3)
PF_PROGRAMS = {level: f"battle/action/power_flip/action/override/{CODE}_pf${CODE}_pf_lv{level}"
               for level in PF_LEVELS}
SKILL_LEVELS = (1, 2)
SKILL_PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in SKILL_LEVELS}

#: 强化弹射每级削韧上限（口径 B.2）。
PF_CAP = {1: 15, 2: 20, 3: 25}
#: 剑士扫击（body[1]）：(最大段数, 改前 p13, 改后 p13)。改后写 0.0：live 里 p13=0 的 185 个 CNA 全是 float 0.0。
PF_SWEEP = {1: (3, 1.5, 0.0), 2: (4, 2, 0.0), 3: (5, 3, 0.0)}
#: 不动的特殊爆裂：(命中数, p13)。
PF_BURST = {1: (3, 5), 2: (4, 5), 3: (4, 6.25)}
PF_BEFORE_TOTAL = {1: 19.5, 2: 28, 3: 40}

#: 技能每次施放单目标总削韧上限（口径 B.1）。
SKILL_CAP = 30
#: {旧 p13: 新 p13}；只命中爆炸 8 段与领域 16 段（都是 1.0），猛击 10 不动。
SKILL_P13 = {1.0: 0.8}
#: 改前 p13 普查 {值: CNA 数}：猛击 10×1 条、爆炸与领域 1.0×2 条。
SKILL_CENSUS = {10: 1, 1.0: 2}
SKILL_TOTAL = (34, 29.2)
TOLERANCE = 1e-9

BEFORE = {
    ("ability", ABILITY5): "4372a6898031b4fb7e8c01dac6fd202bcb7b345ea955e6e616d64d2aeb96ed93",
    ("table", PF_ACTION): "db0874b808d819a89ff388652f3020e7f3b77d17fcfc4384ccef1ab94fa9015b",
    ("action", CODE): "68d73ac85bc572069497fe009139eda4254b30d0a05212e9106dd2d2b430e8bb",
    ("dsl", PF_PROGRAMS[1]): "a3438a69d2f7db0504a63e55fe577860b50dc3a6a313f1f04217634da1b0a0e7",
    ("dsl", PF_PROGRAMS[2]): "c1a66606fa43f4640e81950e31d0305f60af27dc2d92a9a6417a72d99d12f990",
    ("dsl", PF_PROGRAMS[3]): "e43b0a1b856f4dda4b81a4ffd755889e72dac06f116ba16ddfa29be5b5d75cc4",
    ("dsl", SKILL_PROGRAMS[1]): "2b7bd5575a3ad8ff58f7b5dd3921c228eaa22bfedee6aefc6060bb0f5d875609",
    ("dsl", SKILL_PROGRAMS[2]): "9ff9c33004b04129e47026bf96a04c3e90be989393d3e217efc11b8170dbc7f0",
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


def _set_p13(args, value) -> None:
    args[13] = [{"min": value, "max": value}]


# ---------------------------------------------------------------- DSL 改写


def _sweep_area(tree, level: int) -> list:
    """PF body[1]：球锚定（subject -18、AB）的剑士扫击判定区。"""
    command = tree[11][1][1]
    area = command[1] if _tag(command) == "Command" else None
    hits = PF_SWEEP[level][0]
    if (not area or area[0] != "CreateHitArea" or area[2] != -18 or area[3] != ["AB"]
            or area[14] != ["CalculatedUsingMaxNumOfHits", hits]):
        raise ValueError(f"PF lv{level}: body[1] is not the {hits}-hit ball-anchored sweep area")
    return area


def revise_pf_tree(tree, level: int) -> list:
    """PF 覆盖树第 level 档：剑士扫击 p13 → 0，特殊爆裂不动；不改输入。"""
    what = f"PF lv{level}"
    result = deepcopy(tree)
    if result[:11] != ["ActionDsl", 1, ["None"], *[False] * 7, 0]:
        raise ValueError(f"{what}: root header drift")
    hits, old, new = PF_SWEEP[level]
    burst_hits, burst_p13 = PF_BURST[level]
    area = _sweep_area(result, level)
    areas = hit_areas(result)
    if [(a is area, n, [_p13(x) for x in attacks]) for a, n, attacks in areas] != [
            (True, hits, [old]), (False, burst_hits, [burst_p13])]:
        raise ValueError(f"{what}: sweep/burst preimage drift "
                         f"{[(n, [_p13(x) for x in attacks]) for _, n, attacks in areas]}")
    _set_p13(areas[0][2][0], new)
    if abs(detoughness(result) - PF_CAP[level]) > TOLERANCE:
        raise ValueError(f"{what}: detoughness {detoughness(result)} != cap {PF_CAP[level]}")
    return result


def revise_skill_tree(tree, level: int) -> list:
    """技能第 level 档：爆炸 + 领域 24 段 p13 1.0 → 0.8，猛击 10 不动；不改输入。"""
    what = f"skill lv{level}"
    if p13_census(tree) != SKILL_CENSUS:
        raise ValueError(f"{what}: p13 preimage drift {p13_census(tree)}")
    before = detoughness(tree)
    if abs(before - SKILL_TOTAL[0]) > TOLERANCE:
        raise ValueError(f"{what}: detoughness preimage {before} != {SKILL_TOTAL[0]}")
    result = deepcopy(tree)
    for args in wf_dsl.iter_dsl_commands(result, "CreateNormalAttack"):
        old = _p13(args)
        if old in SKILL_P13:
            _set_p13(args, SKILL_P13[old])
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


# ---------------------------------------------------------------- 词条行


def row_problems(row: list[str]) -> list[str]:
    return (legality.client_legality_problems("ability", row)
            + legality.declared_block_field_problems("ability", row)
            + legality.invoke_skill_string_problems(row, set(), "ability"))


def _expect(row, cells: dict, what: str):
    got = {col: row[col] for col in cells}
    if got != cells:
        raise ValueError(f"unexpected preimage for {what}: {got}")


def ability5_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力5 行2（#1）自身眩晕蓄积 600%→100%；行1（Fever 点 200%）逐字保留。不改输入。"""
    out = deepcopy(rows)
    if len(out) != 2 or any(len(r) != 126 for r in out):
        raise ValueError("ability5 shape drift")
    gate = {0: f"{CODE}_5", 1: "true", 5: "0", 6: "188", 9: "100000", 10: "100000", 12: CID}
    _expect(out[0], {**gate, 47: "50", 48: "0", 51: "200000", 52: "200000"}, "ability5 row1")
    _expect(out[STUN_ROW], {**gate, 27: "0", 47: "51", 48: "0", 51: STUN_FROM, 52: STUN_FROM},
            "ability5 row2")
    out[STUN_ROW][51] = out[STUN_ROW][52] = STUN_TO
    if int(out[STUN_ROW][52]) > SELF_STUN_CAP:
        raise ValueError("self stunify above the 100% cap")
    return out


def revise(read) -> dict:
    inputs = _baseline(read)
    ability = {ABILITY5: ability5_rows(inputs["ability", ABILITY5])}
    dsl = {PF_PROGRAMS[level]: revise_pf_tree(inputs["dsl", PF_PROGRAMS[level]], level)
           for level in PF_LEVELS}
    dsl.update({SKILL_PROGRAMS[level]: revise_skill_tree(inputs["dsl", SKILL_PROGRAMS[level]], level)
                for level in SKILL_LEVELS})
    problems = [f"ability {ABILITY5}#{i}: {p}" for i, row in enumerate(ability[ABILITY5])
                for p in row_problems(row)]
    problems += [f"dsl {program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": ability, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": dsl, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_lionreborn.py",
            "spec": ("第二批施工口径 B.1（技能 ≤30，严格口径点名）、B.2（PF 每级 ≤15/20/25，尽量顶格）、"
                     "B.4（自身眩晕蓄积 ≤100%）、B.6；down_design 119996（按 live 1.4.1049 重读重推）"),
            "stunify": {"row": f"{ABILITY5}#{STUN_ROW}", "c51_c52": [STUN_FROM, STUN_TO],
                        "panel": "能力5 无 desc_override，客户端按数值自动生成面板"},
            "pf_detoughness": {f"lv{level}": [PF_BEFORE_TOTAL[level], PF_CAP[level]] for level in PF_LEVELS},
            "pf_sweep_p13": {f"lv{level}": list(PF_SWEEP[level][1:]) for level in PF_LEVELS},
            "skill_detoughness": list(SKILL_TOTAL),
            "skill_p13": {"blast_8_hits_and_field_16_ticks": [1.0, 0.8], "slam_1_hit": [10, 10]},
            "skill_choice": ("只降 MOD 追加的爆炸/领域 24 段（0.8 = 官方 17–40 段技能每段 P50），保留官方母本"
                             "猛击 10；可选：爆炸 1.0→0.5（正好 30）或领域 1.0→0.75（正好 30）"),
            "packages": "无 flow 包（lion_swordman_reborn 工作区未被 active.json 引用）⇒ 只走 wf_publish 裸表边",
            "generators": ("包内历史 kit 已同步源码常量（不运行）：build_pf.py KNIGHT c1 → 0.0；"
                           "build_skill_dsl.py TICK_DETOUGHNESS 1.0 → 0.8。apply_m_batch.py 是一次性直写 live 的"
                           "迁移脚本（不幂等），不是生成器，未改"),
            "text_sync": "技能描述、PF 覆盖文案、character_text、服务端文本都不含削韧/眩晕数值，无需同步",
            "runtime_verified": False,
        },
    }

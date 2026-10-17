'雷皇女 莉莉丝（139997 resistance_princess_ex）：2026-09-27 平衡调整第二批（Down / 削韧）。\n\n口径（${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md，作者已拍板）：\n\n- B.2 强化弹射每级削韧上限 15 / 20 / 25，尽量正好顶到上限。\n  PF 覆盖树（leader 139997#0 kind 722 → power_flip_action ``resistance_princess_ex_pf`` → lv1/lv2/lv3）\n  由三段组成：body[1] 球锚定剑段 ``CreateHitArea``（最多 3/4/5 段）、碰撞后拳段（3/4/6 段，每段 0.5）、\n  格斗终结（10.5/13/17）。只改剑段 ``CreateNormalAttack`` 的 p13：\n  Lv1 1.5→1（16.5→15）、Lv2 2→1.25（23→20）、Lv3 3→1（35→25）。拳段与终结不动。\n  设计稿（down_design.json）Lv2 写的是 →1（得 19）；口径「尽量正好顶到上限」＋任务「按树结构能顶就顶」\n  ⇒ Lv2 剑 4 段取 1.25，正好 20。\n- B.3 能力调用技能（kind 629）每次 ≤3，触发 CT ≤3 秒的每次 ≤1。\n  突袭 629 由能力1 ``1399971#2`` 调用（trigger 144 自身能力伤害累计 10 次，CT c35=300 帧＝5 秒，\n  按 live 1.4.1049 读取核对）⇒ 上限 3。突袭树 5 段 p13 3→0.5：15→2.5。\n  突袭树是第一批（wf_balance_20260927_lilith.py）从 PF Lv3 剑段派生的输出，本批在其 live 结果上只改 p13，\n  两边不要求同值（第二批方案复核：「不需要和突袭树取同值」）。\n- B.6 DSL 只改 CreateNormalAttack 的 p13（每个 SLv 的 {min,max} 同改），其余逐字保留；\n  整树 AMF3 往返一致并过四道 DSL 门禁。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做\n（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，第二批 b 后缀）。\n生成源：PF 三档树由 ``work/character_packs/resistance_princess_ex/build_pf.py`` 一次性拼装\n（fighter 官方拳段 ＋ 杰拉德 live PF 剑段整块克隆），源码里没有 p13 常量可改；该脚本与\n``build_workspace.py`` 都是禁止重跑的历史 kit（重跑会用杰拉德 live 剑段/旧 build 产物回退本批）。\n突袭树的生成器是第一批模块，它按 BEFORE 摘要 fail closed，不会在新 live 上重跑回退。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import wf_client_legality as legality
import wf_dsl
from wf_battle_rules import DAMAGE_CAP

CID = "139997"
CODE = "resistance_princess_ex"
PACKAGES = ["resistance_princess_ex"]
#: 候选 manifest 现值 0.1.1（第一批回写，snapshot revision_20260927）→ 递增。
PACKAGE_VERSION = {"resistance_princess_ex": "0.1.2"}
#: 突袭树根头 buffTargetAs 133 仍需 damage-type-rules-v1（第一批已声明；并集幂等）。
CAPABILITIES = [DAMAGE_CAP]
#: 候选四棵树与 manifest 哈希一致、且与 live 逐节点相同（2026-09-27 核对），无已审漂移。
REVIEWED_DRIFT: dict = {}
ELEMENT = 2  # master/character c3：雷（0 基内部元素）

PF_ACTION = ("master/skill/power_flip_action.orderedmap", f"{CODE}_pf")
PF_LEVELS = (1, 2, 3)
PF_PROGRAMS = {level: f"battle/action/power_flip/action/override/{CODE}_pf${CODE}_pf_lv{level}"
               for level in PF_LEVELS}
BURST_PROGRAM = (f"battle/action/skill/action/ability_skill/{CODE}_pf_burst${CODE}_pf_burst")
INVOKE_KEY, INVOKE_ROW = f"{CID}1", 2

#: 强化弹射每级削韧上限（口径 B.2）。
PF_CAP = {1: 15, 2: 20, 3: 25}
#: 剑段（body[1] 球锚定 CreateHitArea）：(最大段数, 改前 p13, 改后 p13)。
PF_SWORD = {1: (3, 1.5, 1), 2: (4, 2, 1.25), 3: (5, 3, 1)}
#: 不动的拳段与终结：(拳段数, 每段 p13, 终结 p13)。
PF_KEPT = {1: (3, 0.5, 10.5), 2: (4, 0.5, 13), 3: (6, 0.5, 17)}

#: 629 每次上限（口径 B.3）：CT ≤3 秒（180 帧）的 ≤1，否则 ≤3。
INVOKE_CAP, INVOKE_CAP_FAST, FAST_CT_FRAMES = 3, 1, 180
BURST_HITS = 5
BURST_P13 = (3, 0.5)
#: live 1.4.1049 ``1399971#2`` c35（300 帧＝5 秒，已由 BEFORE 摘要钉住）；只用于 notes 与测试对照。
BURST_CT_FRAMES = 300

BEFORE = {
    ("ability", INVOKE_KEY): "975794df2c086612e99885cf34b2ec9d6f80a5ac9b7ddef28e2e62530b514a35",
    ("table", PF_ACTION): "d9df344c7bd3fb1a37d28ced4ab91d68cdb9df487ddd74c2338b6c3892c47a61",
    ("dsl", PF_PROGRAMS[1]): "85dbd7c51d94ecbbf59fe3e8e3745c7c8e9cbdb4ff07686fffe6a4664ee9635e",
    ("dsl", PF_PROGRAMS[2]): "4536d5bb19fe436791183a18b43480ed331b6576004b909f5ed74e0a692fbd30",
    ("dsl", PF_PROGRAMS[3]): "56152f7dfbaa5d46f7c8fcf963c640f2f6283499dd10bee9044ce479f46a2d28",
    ("dsl", BURST_PROGRAM): "9fcf1776a3a3bdf21970d3b5bc5c255610a7997dbea6d0cce25e5eac0a16bd2d",
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


def _p13(value) -> list:
    return [{"min": value, "max": value}]


def hit_areas(tree) -> list[tuple[list, int, list]]:
    """[(CreateHitArea 节点, 最大段数, onHit 内的 CreateNormalAttack 列表)]，按树序。"""
    found = []

    def walk(node):
        if isinstance(node, list):
            if node and node[0] == "CreateHitArea":
                hits = node[14]
                if hits[0] != "CalculatedUsingMaxNumOfHits":
                    raise ValueError(f"unexpected hit-count mode: {hits}")
                found.append((node, hits[1],
                              list(wf_dsl.iter_dsl_commands(node[23], "CreateNormalAttack"))))
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(tree)
    return found


def detoughness(tree) -> float:
    """单目标满打削韧：Σ 判定区最大段数 × onHit 里 CreateNormalAttack 的 p13 上限值。

    所有 CreateNormalAttack 都必须挂在某个判定区的 onHit 里，否则拒绝（不漏算直接攻击）。
    """
    areas = hit_areas(tree)
    attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    if sum(len(a) for _, _, a in areas) != len(attacks):
        raise ValueError("CreateNormalAttack outside a hit area onHit block")
    total = 0.0
    for _, hits, cnas in areas:
        for attack in cnas:
            if len(attack[13]) != 1:
                raise ValueError(f"unexpected p13 SLv shape: {attack[13]}")
            total += hits * attack[13][0]["max"]
    return round(total, 6)


def _one_attack(area, what: str) -> list:
    attacks = list(wf_dsl.iter_dsl_commands(area[23], "CreateNormalAttack"))
    if len(attacks) != 1:
        raise ValueError(f"{what}: expected one CreateNormalAttack, got {len(attacks)}")
    return attacks[0]


def _sword_area(tree, what: str) -> list:
    """body 里球锚定（subject -18、AB 坐标）的剑段 CreateHitArea。"""
    command = tree[11][1][1]
    area = command[1] if command[0] == "Command" else None
    if not area or area[0] != "CreateHitArea" or area[2] != -18 or area[3] != ["AB"]:
        raise ValueError(f"{what}: body[1] is not the ball-anchored sword hit area")
    return area


def revise_pf_tree(tree, level: int) -> list:
    """PF 覆盖树第 level 档：只把剑段 p13 改到上限，其余节点逐字保持。"""
    what = f"PF lv{level}"
    result = deepcopy(tree)
    if result[:11] != ["ActionDsl", 2, ["None"], *[False] * 7, 0]:
        raise ValueError(f"{what}: root header drift")
    hits, old, new = PF_SWORD[level]
    fists, fist_p13, finish_p13 = PF_KEPT[level]
    area = _sword_area(result, what)
    if area[14] != ["CalculatedUsingMaxNumOfHits", hits]:
        raise ValueError(f"{what}: sword hit count drift {area[14]}")
    attack = _one_attack(area, what)
    if attack[13] != _p13(old):
        raise ValueError(f"{what}: sword p13 preimage drift {attack[13]}")
    kept = [(n, [a[13] for a in attacks]) for node, n, attacks in hit_areas(result)
            if node is not area]
    if kept != [(1, [_p13(fist_p13)])] * fists + [(1, [_p13(finish_p13)])]:
        raise ValueError(f"{what}: fist/finisher preimage drift {kept}")
    attack[13] = _p13(new)
    if detoughness(result) != PF_CAP[level]:
        raise ValueError(f"{what}: detoughness {detoughness(result)} != cap {PF_CAP[level]}")
    return result


def invoke_cap(row) -> int:
    """629 行的每次削韧上限：按 live CT（c35 帧）判 ≤3 秒 → 1，否则 3。"""
    if row[47] != "629" or row[71] != BURST_PROGRAM:
        raise ValueError("ability1 row3 no longer invokes the burst program")
    if (row[27], row[30]) != ("144", "1000000") or not row[35].isdigit():
        raise ValueError(f"burst trigger/CT drift: {(row[27], row[30], row[35])}")
    return INVOKE_CAP_FAST if int(row[35]) <= FAST_CT_FRAMES else INVOKE_CAP


def revise_burst_tree(tree, cap: int = INVOKE_CAP) -> list:
    """629 突袭树：5 段剑击 p13 3→0.5（15→2.5），其余节点逐字保持。"""
    result = deepcopy(tree)
    if result[:11] != ["ActionDsl", 1, ["None"], *[False] * 7, 133] or len(result[11][1]) != 1:
        raise ValueError("burst root header or body drift")
    command = result[11][1][0]
    area = command[1] if command[0] == "Command" else None
    if not area or area[0] != "CreateHitArea" or area[2] != -18 or area[3] != ["AB"]:
        raise ValueError("burst body is not the ball-anchored sword hit area")
    if area[14] != ["CalculatedUsingMaxNumOfHits", BURST_HITS]:
        raise ValueError(f"burst hit count drift {area[14]}")
    attack = _one_attack(area, "burst")
    if attack[13] != _p13(BURST_P13[0]):
        raise ValueError(f"burst p13 preimage drift {attack[13]}")
    attack[13] = _p13(BURST_P13[1])
    if detoughness(result) > cap:
        raise ValueError(f"burst detoughness {detoughness(result)} > 629 cap {cap}")
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


def revise(read) -> dict:
    inputs = _baseline(read)
    before = {PF_PROGRAMS[level]: detoughness(inputs["dsl", PF_PROGRAMS[level]])
              for level in PF_LEVELS}
    before[BURST_PROGRAM] = detoughness(inputs["dsl", BURST_PROGRAM])
    cap = invoke_cap(inputs["ability", INVOKE_KEY][INVOKE_ROW])
    dsl = {PF_PROGRAMS[level]: revise_pf_tree(inputs["dsl", PF_PROGRAMS[level]], level)
           for level in PF_LEVELS}
    dsl[BURST_PROGRAM] = revise_burst_tree(inputs["dsl", BURST_PROGRAM], cap)
    problems = [f"dsl {program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": {}, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": dsl, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_lilith.py",
            "spec": "第二批施工口径 B.2（PF 每级 ≤15/20/25，尽量顶格）、B.3（629 每次 ≤3，CT≤3 秒 ≤1）、B.6",
            "pf_detoughness": {f"lv{level}": [before[PF_PROGRAMS[level]], PF_CAP[level]]
                               for level in PF_LEVELS},
            "pf_sword_p13": {f"lv{level}": list(PF_SWORD[level][1:]) for level in PF_LEVELS},
            "pf_lv2_vs_design": "设计稿 Lv2 剑段 →1（19）；按口径「尽量正好顶到上限」取 1.25（20）",
            "burst": {"detoughness": [before[BURST_PROGRAM], BURST_HITS * BURST_P13[1]],
                      "p13": list(BURST_P13), "invoke_row": f"{INVOKE_KEY}#{INVOKE_ROW}",
                      "cooltime_frames": int(inputs["ability", INVOKE_KEY][INVOKE_ROW][35]),
                      "per_call_cap": cap},
            "generators": ("PF 三档由 build_pf.py 拼装时整块克隆杰拉德当时的 PF 剑段，源码无 p13 常量"
                           "（今 live 杰拉德 PF 已改结构，该脚本对其会直接报错）；build_pf.py / "
                           "build_workspace.py 是禁止重跑的历史 kit"),
            "batch1_test": ("test_balance_20260927_lilith 的回写断言已按「第一批输出 + 第二批覆盖」更新，"
                            "主会话暂存回写 revision_20260927b 后才走到新分支"),
            "runtime_verified": False,
        },
    }

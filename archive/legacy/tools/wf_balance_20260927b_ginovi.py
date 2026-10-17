# -*- coding: utf-8 -*-
"基诺维「破契的黑翼」169999 ``ginovi``（暗）：2026-09-27 平衡调整第二批（无上限成长 + Down/削韧）。\n\n口径：``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``（作者已拍板），\n设计稿 growth_design.json / down_design.json 的 169999 条目 + critic G1/R6/F1；数值按 live 1.4.1049 重读重推。\n\n一、无上限成长（口径 A.1–A.3、A.7）\n  队长 ``leader_ability:169999`` 行 7/8/9（0 基 #6/#7/#8）：暗共鸣 + trigger 235 ConditionKeepFramePiercing\n  （自身每保持贯穿 90 帧＝1.5 秒触发一次，c32=(None) 不限次）→ 暗属性全队 攻击力 32 / 技能伤害 34 / 能力伤害 388。\n  成长本来就在队长 ⇒ 原位放缓，只改 c49/c50：25000 → 2500（每跳 25% → 2.5%）。\n  频率（按实际次数分档，A.2）：技能 750 帧贯穿 ⇒ 每次施放 8 跳；开局暗共鸣技能槽 100%（能力1 +50%、队长行10 +50%）\n  立即首发，之后每 18–25 秒一发 ⇒ 3 分钟持有贯穿约 108–144 秒 ≈ 72–96 跳；即使只放 4 次也有 32 跳 ≥30 ⇒ ×1/10。\n  三行 kind 不同（32/34/388）不合并；仍无上限（c32 保持 (None)）。面板 ``desc_override_ginovi`` 第 4 行三处\n  「＋25%」→「＋2.5%」，按裁决「无上限就写到效果为止」不加「可无限累积」。\n\n二、Down / 削韧（口径 B.1–B.3、B.6：只改 CreateNormalAttack p13，其余节点逐字保留）\n  1. 技能两档 ``rare5/ginovi$ginovi_1/_2``（两档逐字相同）：尾部跟球判定区（寿命 750 帧、最小间隔 60、\n     每目标硬帽 Some 12）内唯一的 CNA p13 20 → 2.5：每次施放单目标 240 → 30（B.1 ≤30）。\n  2. 629「夜鸦裂空」``ability_skill_ginovi_pf_lv1/2/3``（队长 #1/#2/#3，trigger 180/181/182，CT c33=36 帧＝0.6 秒）：\n     CT ≤3 秒 ⇒ 每次 ≤1（B.3「按当前 live 的实际触发 CT 核对」）。设计稿 p13 20→0.3（1.5/2.1/2.7）只满足 ≤3，\n     这里再按同一比例收到 0.1：5/7/9 段 = 0.5/0.7/0.9（原 100/140/180）。见 ``notes.open_points`` 备选。\n  3. 629「黑羽斩」``ability_skill_ginovi_dash``（队长 #4，trigger 4 冲刺，CT c33=20 帧＝0.33 秒）：p13 20 → 0.25（单段）。\n  4. PF 本体 ``power_flip/action/override/ginovi_pf$ginovi_pf_lv3``（队长 #0 kind 722 → power_flip_action\n     ``ginovi_pf``）：碰撞后 10 个单段判定区 p13 3 → 2.5：30 → 25（B.2 正好顶到 Lv3 上限，复核 R6）。\n     Lv1 4×3=12（≤15）、Lv2 6×3=18（≤20）不动，只读核对。夜鸦裂空是技能伤害归属的 629，按 R6 另算。\n  直击判定次数 +3（技能 ACAdditionalDirectAttack）按 B.5 不动。\n\n生成器：``work/character_packs/ginovi/build_workspace.py``（critic G1）只改源码常量——\n``PIERCING_BUFF``、``DESC_OVERRIDE_LINES['desc_override_ginovi']`` 第 4 行、``SKILL_AURA_DETOUGHNESS`` /\n``DASH_BLADE_DETOUGHNESS`` / ``BLACKFEATHER_DETOUGHNESS`` / ``PF_BODY_DETOUGHNESS``；测试断言生成器输出 ==\n:func:`revise` 输出。本角色没有设计镜像 JSON。\n\n接口见 ``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``（第二批 b 后缀）：:func:`revise` 只经 ``read``\n读 live，开头按 :data:`BEFORE` 摘要校验（漂移即抛 :class:`GinoviBalanceError`，fail closed），不改 ``read``\n的返回对象。本模块不写 live store / assets / .cdn / 候选包，不发布，不 git。\n"
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl

CID = "169999"
CODE = "ginovi"
PACKAGES = ["ginovi"]
#: 候选现值 0.3.0（``work/character_packs/ginovi/package/manifest.json``）→ 递增。
PACKAGE_VERSION = {"ginovi": "0.3.1"}
#: 候选已声明 dash-parameter-v1 / panel-description-override-v2；改后的行与面板键不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 manifest 全部 133 个条目与文件哈希一致（2026-09-27 只读核对）⇒ 无已审输入漂移。
REVIEWED_DRIFT: dict = {}

ELEMENT = 5                       # master/character c3：暗（0 基内部元素）
ELEMENT_TOKEN = "Black"
LEADER = CID
LEADER_NCOLS = 124
LEADER_ROWS = 11
CAS_LEADER = f"desc_override_{CODE}"

_ACTION = "battle/action/"
SKILL_PROGRAMS = {level: f"{_ACTION}skill/action/rare5/{CODE}${CODE}_{level}" for level in (1, 2)}
PF_INVOKE_PROGRAMS = {
    level: f"{_ACTION}skill/action/ability_skill/ability_skill_{CODE}_pf_lv{level}$ability_skill_{CODE}_pf_lv{level}"
    for level in (1, 2, 3)}
DASH_PROGRAM = f"{_ACTION}skill/action/ability_skill/ability_skill_{CODE}_dash$ability_skill_{CODE}_dash"
PF_BODY_PROGRAMS = {level: f"{_ACTION}power_flip/action/override/{CODE}_pf${CODE}_pf_lv{level}"
                    for level in (1, 2, 3)}
PF_ACTION = ("master/skill/power_flip_action.orderedmap", f"{CODE}_pf")

# ------------------------------------------------------------------ 一、无上限成长（队长 #6–#8）

PIERCING_ROWS = {6: "32", 7: "34", 8: "388"}          # 0 基行号 → c45 内容 kind（攻 / 技伤 / 能伤）
TICK_COLS = (49, 50)
OLD_TICK, NEW_TICK = "25000", "2500"                  # 千 = 1%：25% → 2.5%
TICK_FRAMES = 90
#: 三行共有的前置/触发/目标格（改前改后都必须成立）。
PIERCING_GATE = {1: "0", 2: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
                 25: "235", 26: "0", 28: "100000", 29: "100000", 30: str(TICK_FRAMES * 100000),
                 31: str(TICK_FRAMES * 100000), 32: "(None)", 33: "0", 46: "5", 47: ELEMENT_TOKEN}

PANEL_LINES = 6
PANEL_LINE = 3                                        # 0 基；面板第 4 行
OLD_PANEL_LINE = "暗属性共鸣时，自身每保持贯穿效果1.5秒，暗属性角色攻击力＋25%、技能伤害＋25%、能力伤害＋25%"
NEW_PANEL_LINE = "暗属性共鸣时，自身每保持贯穿效果1.5秒，暗属性角色攻击力＋2.5%、技能伤害＋2.5%、能力伤害＋2.5%"

# ------------------------------------------------------------------ 二、Down / 削韧

#: 629 行：0 基行号 → (trigger c25, 被调程序)。CT 在 c33（帧），按 live 读出判定每次上限。
INVOKE_ROWS = {1: ("180", PF_INVOKE_PROGRAMS[1]), 2: ("181", PF_INVOKE_PROGRAMS[2]),
               3: ("182", PF_INVOKE_PROGRAMS[3]), 4: ("4", DASH_PROGRAM)}
INVOKE_CT_BEFORE = {1: "36", 2: "36", 3: "36", 4: "20"}
FAST_CT_FRAMES = 180                                  # 3 秒
INVOKE_CAP, INVOKE_CAP_FAST = 3, 1                    # 口径 B.3
SKILL_CAP = 30                                        # 口径 B.1
PF_CAP = {1: 15, 2: 20, 3: 25}                        # 口径 B.2

#: 每棵树：(判定区每目标段数列表, 改前 p13, 改后 p13)。段数由判定区参数推出（:func:`area_hits`）。
SKILL_SPEC = ([12], 20, 2.5)
PF_INVOKE_SPEC = {1: ([5], 20, 0.1), 2: ([7], 20, 0.1), 3: ([9], 20, 0.1)}
DASH_SPEC = ([1], 20, 0.25)
PF_BODY_SPEC = {1: ([1] * 4, 3, 3), 2: ([1] * 6, 3, 3), 3: ([1] * 10, 3, 2.5)}

#: 改前 → 改后 单目标每次削韧（notes 与测试对照）。
DETOUGHNESS = {
    "skill": (240, 30),
    "pf_invoke": {1: (100, 0.5), 2: (140, 0.7), 3: (180, 0.9)},
    "dash": (20, 0.25),
    "pf_body": {1: (12, 12), 2: (18, 18), 3: (30, 25)},
}

# ------------------------------------------------------------------ 输入基线

#: ``{(kind, key): sha256}``：revise() 读取的每一项在 live 1.4.1049 上的摘要（2026-09-27 只读采集）。
#: fixture ``tests/fixtures/balance_20260927b_ginovi.json`` 同源。PF 本体 Lv1/Lv2 只读（核对 12/18 在上限内）。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", LEADER): "00bbe56112e22df607c7607dedc9c81d7f6029f55d95fe04d4c49ec4c66aff8c",
    ("cas", CAS_LEADER): "491b66f1284b8d5b4a1d5d47e1948224acb51baf3de9036fb2fd748ac7f21c27",
    # 629 行的文案键（只读：InvokeSkill 文案键必须在 custom_ability_string 里，C8601 门）
    ("cas", f"ability_skill_{CODE}_pf_lv1"): "953f3efd3b319b1d727d6a629f13580cb0f0be9c445b76a8b91cf634f01302fc",
    ("cas", f"ability_skill_{CODE}_pf_lv2"): "b4b4369c714838d5bcd1b0f9536cd70a853bbf1d1b5c2fb514b4e1868ba7d25a",
    ("cas", f"ability_skill_{CODE}_pf_lv3"): "a554dad8d22a1334463fdce2fb96455befee249015aa930e5ede1647411ee5ee",
    ("cas", f"ability_skill_{CODE}_dash"): "4758c77f26df902f3b84eb7f349d9e55a773b7ff685a3b7e6bc7e4d95d09097c",
    ("table", PF_ACTION): "aead65e7aa61783003807eeb261b8c07bb7d235ebc52c89aa717dd5affda0623",
    ("dsl", SKILL_PROGRAMS[1]): "b5007a03f392e6f2750f4803ba93395400635fe8e2361f30a6f268de69562fb9",
    ("dsl", SKILL_PROGRAMS[2]): "b5007a03f392e6f2750f4803ba93395400635fe8e2361f30a6f268de69562fb9",
    ("dsl", PF_INVOKE_PROGRAMS[1]): "f6886c5e26837246959780339974cc9add2ddad3d7ea9cdb237dc0f66b62e9c0",
    ("dsl", PF_INVOKE_PROGRAMS[2]): "747c1af9bcb6e16c60d465ca3792cc325cd00b0fb1a8b167a08d24cfae1692cb",
    ("dsl", PF_INVOKE_PROGRAMS[3]): "e8ddf532f466ccb889281b76cc1487ca32c026a42b86a7ff47d6d9137e49ce91",
    ("dsl", DASH_PROGRAM): "a84517ea90c2afc1e4a11801f7bdb53a9b6906f3fb42101012dd85297d36f580",
    ("dsl", PF_BODY_PROGRAMS[1]): "30dea00decb615c4d089bf737403d0b8eb6041320fb9b322ea6eba1aa72d57f9",
    ("dsl", PF_BODY_PROGRAMS[2]): "dd0b67ea6e839a68b7ae3a9230ab778ce4847c7ee506414e32615240c43505f3",
    ("dsl", PF_BODY_PROGRAMS[3]): "755ff95c1dcf3979d3ba3fb6652c0a2a7a5e41fce5ad1c47cd87573429429fc5",
}

#: 候选包与 live 的既有漂移（2026-09-27 只读核对；值为 ``[候选, live]``）。本批整键/整文件替换的三处会顺带收敛到
#: live；其余不在本批键内，留在 ``notes.open_points``（下次 flow publish 前需另行回写）。
CANDIDATE_STALE = {
    "converged_by_this_revision": {
        "leader_ability 169999#10 c107": ["421", "158"],
        "desc_override_ginovi 第 6 行": ["敌人每持有1层「死印」，我方全体获得＋5%额外伤害乘区（最多10层）",
                                        "全体队员对敌人造成的所有伤害，随该敌人每持有1层「死印」＋5%（状态特攻乘区，最多10层）"],
        "ginovi_pf_lv3 10 段 p6 倍率": [28.0, 4.0],
    },
    "left_as_is": {
        "ability 1699992#0 c51/c52": ["5000", "2000"],
        "ability 1699993#4 c51/c52": ["15000", "10000"],
        "ability 1699993#5 c51/c52": ["20000", "15000"],
        "ginovi_pf_lv1 4 段 p6 倍率": [18.75, 2.5],
        "ginovi_pf_lv2 6 段 p6 倍率": [26.666666666666668, 4.166666666666667],
    },
}


class GinoviBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _slv(value) -> list[dict]:
    return [{"min": value, "max": value}]


# ------------------------------------------------------------------ DSL：判定区段数与削韧

def area_hits(area: list) -> int:
    """单个 CreateHitArea（参数数组，[0] 为名字）对同一目标的最多命中段数。

    p14 ``CalculatedUsingMaxNumOfHits(N)`` = 期望命中机会数（N=1 只放首次）；
    p14 ``SpecifyMinHitIntervalDirectly(I)`` = 按寿命 p13 每 I 帧一跳；每目标硬帽是 p15 ``Some``
    （记忆卡 wf-hitarea-param-card）。间隔模式必须带硬帽，否则拒绝估算。
    """
    mode, cap = area[14], area[15]
    limit = None
    if cap != ["None"]:
        if not (isinstance(cap, list) and cap[0] == "Some" and len(cap[1]) == 1):
            raise GinoviBalanceError(f"unexpected hit cap {cap!r}")
        limit = int(cap[1][0]["max"])
    if mode[0] == "CalculatedUsingMaxNumOfHits":
        hits = int(mode[1])
    elif mode[0] == "SpecifyMinHitIntervalDirectly":
        life = area[13]
        if life[0] != "SpecifyHitAreaLifetimeDirectly" or limit is None:
            raise GinoviBalanceError(f"interval hit area without lifetime/cap: {life!r} {cap!r}")
        hits = int(life[1]) // int(mode[1]) + 1
    else:
        raise GinoviBalanceError(f"unexpected hit mode {mode!r}")
    return hits if limit is None else min(hits, limit)


def hit_areas(tree) -> list[tuple[list, int, list[list]]]:
    """[(CreateHitArea 参数, 每目标段数, onHit p23 里的 CreateNormalAttack 参数列表)]，按树序。

    所有 CreateNormalAttack 都必须挂在某个判定区的 onHit 里（不漏算），且判定区不嵌套判定区。
    """
    found = [(area, area_hits(area), list(wf_dsl.iter_dsl_commands(area[23], "CreateNormalAttack")))
             for area in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")]
    attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    if sum(len(cnas) for _, _, cnas in found) != len(attacks):
        raise GinoviBalanceError("CreateNormalAttack outside a hit-area onHit block")
    return found


def detoughness(tree) -> float:
    """单目标每次满打削韧：Σ 判定区段数 × onHit 里 CreateNormalAttack 的 p13 上限值。"""
    total = 0.0
    for _area, hits, cnas in hit_areas(tree):
        for attack in cnas:
            if len(attack[13]) != 1:
                raise GinoviBalanceError(f"unexpected p13 SLv shape {attack[13]!r}")
            total += hits * attack[13][0]["max"]
    return round(total, 6)


def revise_p13(tree, spec: tuple[list[int], Any, Any], label: str) -> list:
    """把树里全部 CreateNormalAttack 的 p13 从 ``old`` 改成 ``new``；段数布局与改前值逐项核对。"""
    hits_layout, old, new = spec
    out = deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl"):
        raise GinoviBalanceError(f"{label}: unexpected root")
    areas = hit_areas(out)
    if [hits for _, hits, cnas in areas for _ in cnas] != hits_layout or any(len(c) != 1 for _, _, c in areas):
        raise GinoviBalanceError(f"{label}: hit layout {[(h, len(c)) for _, h, c in areas]} != {hits_layout}")
    for _area, _hits, cnas in areas:
        attack = cnas[0]
        if attack[13] != _slv(old):
            raise GinoviBalanceError(f"{label}: p13 preimage {attack[13]!r} != {old!r}")
        attack[13] = _slv(new)
    return out


def _body_stripped(tree) -> Any:
    """把全部 CNA 的 p13 抹成同一占位，用于「只有 p13 变化」的逐字比较。"""
    out = deepcopy(tree)
    for attack in wf_dsl.iter_dsl_commands(out, "CreateNormalAttack"):
        attack[13] = None
    return out


def dsl_gate_problems(tree) -> list[str]:
    """contract 要求的四道 DSL 门 + AMF3 往返。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


# ------------------------------------------------------------------ 词条 / 文案

def _expect(row: list[str], cells: dict[int, str], what: str) -> None:
    got = {col: row[col] for col in cells}
    if got != cells:
        raise GinoviBalanceError(f"{what}: unexpected preimage {got}")


def invoke_cap(row: list[str]) -> int:
    """629 行每次削韧上限：live CT（c33 帧）≤3 秒 → 1，否则 3（口径 B.3）。"""
    ct = row[33]
    if not ct.isdigit():
        raise GinoviBalanceError(f"629 CT is not a frame count: {ct!r}")
    return INVOKE_CAP_FAST if int(ct) <= FAST_CT_FRAMES else INVOKE_CAP


def check_leader_shape(rows: list[list[str]]) -> None:
    if len(rows) != LEADER_ROWS or any(len(r) != LEADER_NCOLS for r in rows):
        raise GinoviBalanceError(f"leader {LEADER}: expected {LEADER_ROWS}×{LEADER_NCOLS} rows")
    _expect(rows[0], {45: "722", 80: f"{CODE}_pf", 81: "1,2,3"}, "leader #0 (722 PF override)")
    for index, (trigger, program) in INVOKE_ROWS.items():
        name = program.rsplit("$", 1)[-1]
        _expect(rows[index], {3: "0", 25: trigger, 28: "100000", 29: "100000", 32: "(None)",
                              33: INVOKE_CT_BEFORE[index], 45: "629", 68: name, 69: program},
                f"leader #{index} (629)")


def revise_leader(rows: list[list[str]]) -> list[list[str]]:
    out = deepcopy(rows)
    check_leader_shape(out)
    for index, kind in PIERCING_ROWS.items():
        row = out[index]
        _expect(row, {**PIERCING_GATE, 45: kind, TICK_COLS[0]: OLD_TICK, TICK_COLS[1]: OLD_TICK},
                f"leader #{index} (235 piercing tick)")
        for col in TICK_COLS:
            row[col] = NEW_TICK
    return out


def leader_row_problems(row: list[str], cas_keys) -> list[str]:
    problems = [f"legality: {p}" for p in L.client_legality_problems("leader_ability", row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems("leader_ability", row)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems("leader_ability", row, ELEMENT)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, cas_keys, "leader_ability")]
    caps = L.required_client_capabilities("leader_ability", row)
    if caps:
        problems.append(f"unexpected capabilities {caps}")
    return problems


def revise_panel(cas: list[list[str]]) -> list[list[str]]:
    if not (len(cas) == 1 and len(cas[0]) == 1 and isinstance(cas[0][0], str)):
        raise GinoviBalanceError(f"{CAS_LEADER}: expected one single-cell row")
    lines = cas[0][0].split("\n")
    if len(lines) != PANEL_LINES or lines[PANEL_LINE] != OLD_PANEL_LINE:
        raise GinoviBalanceError(f"{CAS_LEADER}: panel line {PANEL_LINE + 1} is not the reviewed text")
    lines[PANEL_LINE] = NEW_PANEL_LINE
    return [["\n".join(lines)]]


def panel_percent(line: str) -> float:
    """面板行里「＋X%」的唯一取值（三处必须相同）。"""
    values = {part.split("%", 1)[0] for part in line.split("＋")[1:]}
    if len(values) != 1:
        raise GinoviBalanceError(f"panel line carries several values: {sorted(values)}")
    return float(values.pop())


# ------------------------------------------------------------------ 主入口

def _baseline(read: Callable[[str, Any], Any]) -> dict:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        if value is None or digest(value) != want:
            raise GinoviBalanceError(f"live drift: {kind}:{key if isinstance(key, str) else '|'.join(key)} "
                                     "is not the reviewed baseline")
        inputs[kind, key] = deepcopy(value)
    if inputs["table", PF_ACTION] != [[PF_BODY_PROGRAMS[level] for level in (1, 2, 3)]]:
        raise GinoviBalanceError("power_flip_action ginovi_pf no longer points at the reviewed PF trees")
    return inputs


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    leader_before = inputs["leader", LEADER]
    leader = revise_leader(leader_before)
    cas = {CAS_LEADER: revise_panel(inputs["cas", CAS_LEADER])}
    if panel_percent(NEW_PANEL_LINE) != int(NEW_TICK) / 1000:
        raise GinoviBalanceError("panel value disagrees with the leader tick strength")

    trees: dict[str, list] = {}
    evidence: dict[str, Any] = {}

    def revise_one(program: str, spec, cap: float, label: str, expected: tuple, *, exact: bool = False) -> None:
        before = inputs["dsl", program]
        after = revise_p13(before, spec, label)
        old_total, new_total = detoughness(before), detoughness(after)
        if (old_total, new_total) != expected:
            raise GinoviBalanceError(f"{label}: detoughness {old_total}->{new_total} != reviewed {expected}")
        if new_total > cap or (exact and new_total != cap):
            raise GinoviBalanceError(f"{label}: detoughness {new_total} vs cap {cap}")
        if _body_stripped(before) != _body_stripped(after):
            raise GinoviBalanceError(f"{label}: nodes other than p13 changed")
        problems = dsl_gate_problems(after)
        if problems:
            raise GinoviBalanceError(f"{label} rejected: {problems}")
        trees[program] = after
        evidence[label] = {"program": program, "p13": [spec[1], spec[2]], "hits": spec[0],
                           "detoughness": [old_total, new_total], "cap": cap}

    for level, program in SKILL_PROGRAMS.items():
        revise_one(program, SKILL_SPEC, SKILL_CAP, f"skill lv{level}", DETOUGHNESS["skill"], exact=True)
    for level, program in PF_INVOKE_PROGRAMS.items():
        cap = invoke_cap(leader_before[level])
        revise_one(program, PF_INVOKE_SPEC[level], cap, f"629 夜鸦裂空 lv{level}", DETOUGHNESS["pf_invoke"][level])
        evidence[f"629 夜鸦裂空 lv{level}"]["ct_frames"] = int(leader_before[level][33])
    revise_one(DASH_PROGRAM, DASH_SPEC, invoke_cap(leader_before[4]), "629 黑羽斩", DETOUGHNESS["dash"])
    evidence["629 黑羽斩"]["ct_frames"] = int(leader_before[4][33])
    revise_one(PF_BODY_PROGRAMS[3], PF_BODY_SPEC[3], PF_CAP[3], "PF 本体 lv3", DETOUGHNESS["pf_body"][3], exact=True)
    for level in (1, 2):   # 只读核对：不改，不返回
        total = detoughness(inputs["dsl", PF_BODY_PROGRAMS[level]])
        spec_hits, old, _new = PF_BODY_SPEC[level]
        if total != DETOUGHNESS["pf_body"][level][0] or total != sum(spec_hits) * old or total > PF_CAP[level]:
            raise GinoviBalanceError(f"PF 本体 lv{level}: detoughness {total} drifted or exceeds {PF_CAP[level]}")
        evidence[f"PF 本体 lv{level}"] = {"program": PF_BODY_PROGRAMS[level], "detoughness": [total, total],
                                          "cap": PF_CAP[level], "unchanged": True}
    if trees[SKILL_PROGRAMS[1]] != trees[SKILL_PROGRAMS[2]]:
        raise GinoviBalanceError("skill tiers diverged after revision")

    cas_keys = {key for kind, key in BEFORE if kind == "cas"}
    problems = [f"leader #{i}: {p}" for i, row in enumerate(leader) for p in leader_row_problems(row, cas_keys)]
    if problems:
        raise GinoviBalanceError("; ".join(problems))

    return {
        "ability": {},
        "leader": {LEADER: leader},
        "cas": cas,
        "text": {},
        "table": {},
        "action": {},
        "dsl": trees,
        "server_text": {},
        "new_programs": [],
        "notes": {
            "character": f"{CID} {CODE} 基诺维「破契的黑翼」（暗）",
            "source": "mod-tools/wf_balance_20260927b_ginovi.py",
            "spec": "第二批施工口径 A.1–A.3/A.7（无上限成长）、B.1–B.3/B.5/B.6（Down）；"
                    "growth_design 169999、down_design 169999、critic G1/R6/F1",
            "growth": {
                "rows": {f"leader #{i}": kind for i, kind in PIERCING_ROWS.items()},
                "trigger": f"235 ConditionKeepFramePiercing，每保持贯穿 {TICK_FRAMES} 帧一跳，c32=(None)",
                "c49/c50": [OLD_TICK, NEW_TICK],
                "per_tick": ["25%", "2.5%"],
                "frequency": "技能 750 帧贯穿=8 跳/次；开局暗共鸣技能槽 100% 首发，之后约每 18–25 秒一发 ⇒ "
                             "3 分钟持有贯穿约 108–144 秒≈72–96 跳；只放 4 次也有 32 跳 ≥30 ⇒ 口径 A.2 取 1/10",
                "position": "已在队长 ⇒ 原位放缓（口径 A.3）；三行 kind 32/34/388 不同，不合并；仍无上限",
                "three_minute_total": "暗队攻/技伤/能伤 各约 +1800–2400% → +180–240%",
            },
            "panel": {"key": CAS_LEADER, "line": PANEL_LINE + 1, "before": OLD_PANEL_LINE,
                      "after": NEW_PANEL_LINE,
                      "why": "只换数字；无上限按裁决写到效果为止，不加「可无限累积」（设计稿 panel_text 的后缀不采用）"},
            "detoughness": evidence,
            "invoke_ct_rule": "629 每次 ≤3；live CT（队长 c33）≤180 帧（3 秒）的每次 ≤1。夜鸦裂空 CT 36 帧、"
                              "黑羽斩 CT 20 帧 ⇒ 两者都按 ≤1",
            "kept": ["技能 ACAdditionalDirectAttack 直击 3 次（口径 B.5 特色不改）",
                     "PF 本体 Lv1 12 / Lv2 18（已在 15/20 上限内）",
                     "技能描述（action_skill / character_text / 服务端）不含削韧与成长数字，不改"],
            "generator": {
                "file": "work/character_packs/ginovi/build_workspace.py",
                "constants": {"PIERCING_BUFF": NEW_TICK, "SKILL_AURA_DETOUGHNESS": SKILL_SPEC[2],
                              "DASH_BLADE_DETOUGHNESS": DASH_SPEC[2],
                              "BLACKFEATHER_DETOUGHNESS": PF_INVOKE_SPEC[1][2],
                              "PF_BODY_DETOUGHNESS": {str(k): v[2] for k, v in PF_BODY_SPEC.items()}},
                "panel": "DESC_OVERRIDE_LINES['desc_override_ginovi'][3]",
                "not_run": "只改源码常量；build/kit-v3 会写包，本批不运行",
            },
            "candidate_preexisting_drift": deepcopy(CANDIDATE_STALE),
            "open_points": [
                "夜鸦裂空按 live 行 CT 36 帧（≤3 秒）取每次 ≤1：p13 0.1 → 0.5/0.7/0.9。若作者认定其实际触发间隔"
                "＝强化弹射间隔（>3 秒）、按设计稿「每次 ≤3」执行，则 PF_INVOKE_SPEC 与生成器 "
                "BLACKFEATHER_DETOUGHNESS 同改 0.3（1.5/2.1/2.7）",
                "候选包既有漂移：本批整键/整文件替换的 leader 169999（#10 c107 421→158）、desc_override_ginovi"
                "（第 6 行死印文案）、ginovi_pf_lv3（倍率 28→4）会顺带收敛到 live；ability 1699992#0、1699993#4/#5 "
                "（充能数值）与 ginovi_pf_lv1/lv2（倍率 18.75/26.67 vs live 2.5/4.17）不在本批键内，候选仍是旧值，"
                "下次 flow publish 前需另行回写",
                "生成器与 live 既有差异（充能类，口径 A.6 本批不动）：能力2 a2a c51/c52 生成 5000、live 2000；"
                "能力3 a3e/a3f 生成 15000/20000、live 10000/15000；DESC_OVERRIDE_LINES _2/_3 仍是对应旧文案；"
                "write_m3_leader_rows 的 629 行 #1–#4 c111 生成 150000、live 25000",
                "影子表（build/shadow，kit-v3 产物）未重建：test_build_workspace GinoviKitV3Tests 的贯穿跳与死印两条"
                "断言会按产物过期报红，重跑 kit-v3 需作者授权（会写包）",
                "范围外（口径 B.5 / 未列入）：技能全员直击 +3（750 帧）放大直击削韧；能力3 冲刺 kind 357 能力伤害"
                "每段固定削韧 1",
            ],
            "runtime_verified": False,
        },
    }

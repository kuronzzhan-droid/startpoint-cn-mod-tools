# -*- coding: utf-8 -*-
"""斩铁·白梅 159998 ``samurai_robot_plum``（光）：2026-09-27 平衡第三轮（成长复核），纯函数。

口径：主会话 ``growth_c_spec.md``（作者原话：成长砍到 1/10 不合理 →「砍到 4/5，或者 7/10」→「可以砍到 2/3」、
「数值尽量取 5 的倍数」）+ ``reeval_full.json`` table.rows 斩铁两组 + 默认选择 D1–D4。
第二批（``wf_balance_20260927b_zantetsu``，已发布）把能力 3 的三条 250 连击成长搬进队长并砍到原值 1/5；
本轮：250 连击须单次飞行叠出，3 分钟约 6 次、难 ⇒ 4/5（原值已是 5 的倍数 / <10% 行按整数）。

落点（队长 ``leader_ability:159998``，行号 0 起；其余格、原 7 行逐字保留）：

- L#7 光共鸣·每 250 连击 → 自身攻击力：c49/c50 10000/20000 → **40000/80000**（原 50→100%，×4/5）；
- L#8 光共鸣·每 250 连击 → 自身技能伤害：c49/c50 10000/20000 → **40000/80000**（同上）；
- L#9 光共鸣·每 250 连击 → 自身技能伤害独立乘区（694）：c49/c50 1000/2000 → **4000/8000**（原 5→10%，×4/5）。

不动：能力 3 #1–#3 封顶版（D4，12.5→25%×4、1→2%×5）；629 剑 PF 树（第二批 Down）；共鸣前置（D3，三行本就带光共鸣）。
面板：斩铁没有 desc_override，队长面板由客户端按行自动生成；技能描述不含这些数值 ⇒ 不改文案。

技能强化文案（作者原话「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的
效果,规范并简化描述做了吗」；主会话口径 R1–R4）：能力3 ``1599983`` #6 kind 704（旗号 2，前置 光≥6 共鸣）c70 引用的
强化条目 ``change_skill_samurai_robot_plum_fever``「Fever模式中，强化『超振动斩铁剑·寒梅一闪』，追加…」不合官方格式
⇒「强化『超振动斩铁剑·寒梅一闪』：Fever模式中追加随连击数提升的威力，并赋予自身贯穿效果」（Fever 条件挪进说明；
能力3 是自动面板，客户端按前置拼「光属性共鸣时」）。依据（:func:`flag_basis_problems`，两档技能 DSL 只读）：
``ConditionalsChangeSkillFlag(2)`` 开支里 ``ConditionalsFeverMode`` 的 then 支给自身（-17）``ACPiercing``，三段
``CreateNormalAttack`` 在 Fever then 支连击加成开关 True、else 支 False。技能说明（action_skill 两档 c1、
character_text c5/c7）本来就只写技能本体，不改；数据行与 DSL 一格不动（R4）。
生成器：``wf_zantetsu_fever_revision.apply_candidate`` 回写该串时用 :data:`NEW_FEVER_TEXT`（不再写旧字面）。

生成器链（kit 重建后固定顺序）：``wf_seasonal7_kit_zantetsu``（kit 已钉冻结 donor 1499963#1（FROZEN_DONORS）；源码 sha 已变，
``gates.json`` 的 ``kit_source_sha256`` 登记为已知过期、待按 tables→kit→…→gates 步序重跑，本轮不重跑）
→ ``wf_zantetsu_fever_revision.apply_candidate``（09-17 → 1.5 批 → 第二批 → 本模块
:func:`leader_rows`）⇒ 链尾 == :func:`revise`（测试断言）。
本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_balance_20260927b_zantetsu as B

CID = B.CID
CODE = B.CODE
PACKAGES = ["s7-zantetsu"]
#: 候选 manifest 现值 1.0.3（第二批写入）⇒ 1.0.4。
PACKAGE_VERSION = {"s7-zantetsu": "1.0.4"}
CAPABILITIES: list[str] = []
#: 候选 s7-zantetsu 的 leader_ability:159998 与 live 逐字相同（2026-09-27 只读核对，链尾 1.4.1053）。
REVIEWED_DRIFT: dict = {}

ELEMENT = B.ELEMENT
LEADER_NCOLS = B.LEADER_NCOLS
LEADER_ROWS = B.LEADER_ROWS_AFTER               # 第二批之后 10 行
STRINGS = frozenset({B.CAS_CHANGE_SKILL, B.CAS_PF})

#: 第二批落值（= 本轮输入）的逐格指纹：行号 → 全部非空格。
B_AFTER = {i: B.LEADER_NEW[i] for i in sorted(B.LEADER_NEW)}
#: 本轮新值（c49 低 / c50 满）= 能力行原值 ×4/5。
C_VALUES = {7: ("40000", "80000"), 8: ("40000", "80000"), 9: ("4000", "8000")}
C_AFTER = {i: {**cells, 49: C_VALUES[i][0], 50: C_VALUES[i][1]} for i, cells in B_AFTER.items()}
#: 原值（能力 3 搬入前，= 第二批源行 c51/c52）与系数，供测试复核。
ORIGINAL = {7: (50000, 100000), 8: (50000, 100000), 9: (5000, 10000)}
FACTOR = (4, 5)

#: live 输入基线（2026-09-27 本地链尾 1.4.1053 只读取数 = 第二批产物）。任一不符 ⇒ 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", CID): "c0de80214517a4325b0d5bca13d2eca204c1eb1b78dcc97fa7a77256b1177416",
    # 技能强化文案（链尾 1.4.1054 只读取数，与候选 s7-zantetsu 1.0.3 逐字相同）：条目改写；能力3 行与两档技能 DSL 只读。
    ("cas", "change_skill_samurai_robot_plum_fever"): "02ba887c5045daed83836d503dbb4d590729685e0f4fcdc77e74ccbd87389998",
    ("ability", B.A3): "3945bb69f3a42e6595e5652bc0444d1c40f49d618f91aad5ff687244dbd6db7b",
    ("dsl", f"battle/action/skill/action/rare5/{CODE}${CODE}_1"):
        "5f8c9b4241c4acc8c581d38f2d7926edd6debb8a47952b5ac92b59efc8738717",
    ("dsl", f"battle/action/skill/action/rare5/{CODE}${CODE}_2"):
        "91d88428916a8548d984ee968ab1fd000c2d540ba910c56f968043e2e01c3085",
}

# ---------------------------------------------------------------- 技能强化文案（R1–R4）

SKILL_NAME = "超振动斩铁剑·寒梅一闪"
FEVER_TEXT = "change_skill_samurai_robot_plum_fever"      # 能力3 #6 kind 704（旗号 2）c70
FLAG2_ROW = 6
SKILLS = tuple(f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in (1, 2))
OLD_FEVER_TEXT = f"Fever模式中，强化『{SKILL_NAME}』，追加随连击数提升的威力，并赋予贯穿效果"
NEW_FEVER_TEXT = f"强化『{SKILL_NAME}』：Fever模式中追加随连击数提升的威力，并赋予自身贯穿效果"
FLAG_ENTRY_HEADS = (f"强化『{SKILL_NAME}』", f"为『{SKILL_NAME}』追加")
FLAG_ENTRY_BANNED = ("强化自身技能", "强化技能", "属性共鸣时", "担任队长", "强化后")
SELF = -17                                                 # DSL 内置 subject：自身
NA_COMBO_ARG = 8                                           # CreateNormalAttack 第 8 参：连击加成开关


def _commands(node, chain=(), out=None):
    """DSL 里每个命令 → (祖先链, 参数表)；祖先链 = ((命令名, 参数位, 首参（标量才记）), …)，外 → 内。"""
    out = [] if out is None else out
    if isinstance(node, list):
        if len(node) >= 2 and node[0] == "Command" and isinstance(node[1], list) and node[1] \
                and isinstance(node[1][0], str):
            args = node[1]
            out.append((chain, args))
            head = args[1] if len(args) > 1 and not isinstance(args[1], (list, dict)) else None
            for index, arg in enumerate(args[1:], 1):
                _commands(arg, chain + ((args[0], index, head),), out)
            return out
        for item in node:
            _commands(item, chain, out)
    elif isinstance(node, dict):
        for item in node.values():
            _commands(item, chain, out)
    return out


def _under(chain, name, index, head=None) -> bool:
    return any(n == name and i == index and (head is None or h == head) for n, i, h in chain)


def flag_basis_problems(a3: list[list[str]], trees: dict[str, Any]) -> list[str]:
    """R1/R2 依据：条目挂在能力3 #6（704、光≥6 共鸣、c70 = 串，只此一行）；两档技能 DSL 的旗号 2 开支里 Fever then 支
    给自身贯穿、三段普攻在 Fever then 支开连击加成（else 支关）⇒ 条目「Fever模式中追加随连击数提升的威力，并赋予自身
    贯穿效果」与数据一致。"""
    problems = []
    row = a3[FLAG2_ROW] if len(a3) > FLAG2_ROW else []
    if len(row) != B.ABILITY_NCOLS or (row[47], row[70]) != ("704", FEVER_TEXT):
        problems.append(f"ability {B.A3}#{FLAG2_ROW}: not the 704 row pointing at {FEVER_TEXT}")
    elif not any(row[b] == "2" and (row[b + 3], row[b + 5]) == ("600000", B.LIGHT) for b in (6, 13, 20)):
        problems.append(f"ability {B.A3}#{FLAG2_ROW}: no light-resonance precondition")
    if [i for i, r in enumerate(a3) if len(r) > 70 and r[70] == FEVER_TEXT] != [FLAG2_ROW]:
        problems.append(f"{FEVER_TEXT}: referenced by other rows")
    for program in SKILLS:
        cmds = _commands(trees.get(program))
        flag2 = [(chain, args) for chain, args in cmds if _under(chain, "ConditionalsChangeSkillFlag", 2, 2)]
        piercing = [(chain, args) for chain, args in cmds if args[0] == "CreateCondition" and len(args) > 2
                    and any(isinstance(c, list) and c and c[0] == "ACPiercing" for c in args[2])]
        if not piercing or any(args[1] != SELF or not _under(chain, "ConditionalsChangeSkillFlag", 2, 2)
                               or not _under(chain, "ConditionalsFeverMode", 1) for chain, args in piercing):
            problems.append(f"{program}: piercing is not self-only inside flag 2 + Fever")
        attacks = [(chain, args) for chain, args in flag2 if args[0] == "CreateNormalAttack"]
        fever_on = [args[NA_COMBO_ARG] for chain, args in attacks if _under(chain, "ConditionalsFeverMode", 1)]
        fever_off = [args[NA_COMBO_ARG] for chain, args in attacks if not _under(chain, "ConditionalsFeverMode", 1)]
        if not fever_on or set(fever_on) != {True} or set(fever_off) != {False}:
            problems.append(f"{program}: flag-2 combo bonus is not Fever-only ({fever_on} / {fever_off})")
    return problems


def flag_entry_problems(text: str) -> list[str]:
    """R2：官方格式、点明技能名、定性无数字（kitlib skill_flag 门）、不写共鸣前缀（客户端按前置拼）。"""
    import wf_midautumn_kitlib as KL
    problems = [f"{FEVER_TEXT}: {p}" for p in KL.panel_problems(text, skill_flag=True)]
    if not text.startswith(FLAG_ENTRY_HEADS):
        problems.append(f"{FEVER_TEXT}: must start with one of {FLAG_ENTRY_HEADS}")
    problems += [f"{FEVER_TEXT}: banned wording {w!r}" for w in FLAG_ENTRY_BANNED if w in text]
    return problems


def fever_text(rows: list[list[str]]) -> list[list[str]]:
    """条目改写：live 必须是改前文字（不接受自身输出，fail closed）。"""
    if rows != [[OLD_FEVER_TEXT]]:
        raise ValueError(f"{FEVER_TEXT}: live text differs from the reviewed text")
    return [[NEW_FEVER_TEXT]]

#: wf_describe 回读（改后）；测试与 notes 共用。
DESCRIBE_AFTER = {
    7: "光·编成≥6 时: 连击≥250 → 自身 攻击力 40%→80%",
    8: "光·编成≥6 时: 连击≥250 → 自身 技能伤害 40%→80%",
    9: "光·编成≥6 时: 连击≥250 → 自身 独立乘区技能伤害 4%→8%",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise ValueError(f"unreviewed live baseline for {kind}:{key} ({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 250 连击三行强度 ×4/5 回调；只接受第二批产物（或本轮产物，幂等），原 7 行逐字保留。"""
    if len(rows) != LEADER_ROWS or any(len(r) != LEADER_NCOLS for r in rows):
        raise ValueError(f"leader_ability {CID}: expected the {LEADER_ROWS}-row batch-2 shape")
    out = deepcopy(rows)
    for index, cells in B_AFTER.items():
        if not (B._matches(out[index], LEADER_NCOLS, cells)
                or B._matches(out[index], LEADER_NCOLS, C_AFTER[index])):
            raise ValueError(f"leader_ability {CID}#{index}: row is not the reviewed batch-2 shape")
        out[index] = B._row(LEADER_NCOLS, C_AFTER[index])
    for index, (old, new) in enumerate(zip(rows, out)):
        if index not in B_AFTER and old != new:
            raise AssertionError(f"leader_ability {CID}#{index}: untouched row changed")
    growth = [i for i, row in enumerate(out) if row[3] == "0" and row[25] == "12" and row[28] == B.COMBO_250]
    if growth != sorted(B_AFTER):
        raise ValueError(f"leader_ability {CID}: 250-combo growth rows at {growth}")
    return out


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader_in = _checked(read, "leader", CID)
    flag_in = _checked(read, "cas", FEVER_TEXT)
    a3 = _checked(read, "ability", B.A3)
    trees = {program: _checked(read, "dsl", program) for program in SKILLS}
    leader = leader_rows(leader_in)
    probs = B.row_problems("leader_ability", leader, set(STRINGS))
    if probs:
        raise ValueError(probs)
    # 技能强化文案（R1–R4）：先按数据核对 704 开关行与旗号 2 开支，再改条目（能力3 行与 DSL 只读）。
    basis = flag_basis_problems(a3, trees)
    if basis:
        raise ValueError(f"skill-flag basis drifted: {basis}")
    cas = {FEVER_TEXT: fever_text(flag_in)}
    probs = flag_entry_problems(cas[FEVER_TEXT][0][0])
    if probs:
        raise ValueError(probs)
    new_caps = B.capability_set("leader_ability", leader) - B.capability_set("leader_ability", leader_in)
    if new_caps - set(CAPABILITIES):
        raise ValueError(f"revised rows need undeclared client capabilities: {sorted(new_caps)}")
    return {
        "ability": {},
        "leader": {CID: leader},
        "cas": cas, "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_zantetsu.py",
            "request": "第三轮成长复核：1/5 → 4/5（250 连击 3 分钟约 6 次、难）",
            "changes": {f"leader_ability:{CID}#{i} c49/c50": f"{B_AFTER[i][49]}/{B_AFTER[i][50]} → "
                        f"{C_VALUES[i][0]}/{C_VALUES[i][1]}（原 {ORIGINAL[i][0]}/{ORIGINAL[i][1]} ×4/5）"
                        for i in sorted(C_VALUES)},
            "growth_3min": "6 次 250 连击：攻/技伤 原 300→600% / 第二批 60→120% / 本轮 240→480%（另加能力封顶 50→100%）；"
                           "独立乘区 原 30→60% / 第二批 6→12% / 本轮 24→48%（另加能力封顶 5→10%）",
            "first_layers": "前 4 次 80%+25% = 105% 略高于原 100%；独立乘区前 5 次 8%+2% = 原 10%（D4 不动封顶版）",
            "kept": "能力 3 封顶版（D4）；629 剑 PF 树；共鸣前置（D3）；1.5 批与第二批其余改动",
            "panel": "无 desc_override，队长面板客户端按行自动生成；技能描述无相关数值 ⇒ 不改文案",
            "skill_enhancement_text": {
                "request": "作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,"
                           "规范并简化描述做了吗」；主会话口径 R1–R4",
                "change": {f"custom_ability_string:{FEVER_TEXT}": [OLD_FEVER_TEXT, NEW_FEVER_TEXT]},
                "basis": f"ability:{B.A3}#{FLAG2_ROW} kind 704（旗号 2，前置 光≥6 共鸣）c70 = {FEVER_TEXT}；两档技能 DSL "
                         "ConditionalsChangeSkillFlag(2) 开支：ConditionalsFeverMode then 支 CreateCondition(-17, ACPiercing)、"
                         "三段 CreateNormalAttack 连击加成开关 Fever then 支 True / else 支 False",
                "rule": "官方格式「强化『技能名』：…」，Fever 条件挪进说明；「自身」按 DSL 对象 -17 补上；能力3 是自动面板"
                        "（客户端拼「光属性共鸣时」）",
                "skill_description": "action_skill 两档 c1 / character_text c5/c7 本来就只写技能本体，不改",
            },
            "describe_after": {f"leader_ability:{CID}#{i}": d for i, d in DESCRIBE_AFTER.items()},
            "generator": "wf_seasonal7_kit_zantetsu（kit 已钉冻结 donor 1499963#1（FROZEN_DONORS））→ wf_zantetsu_fever_revision.apply_candidate"
                         "（09-17 → 1.5 批 → 第二批 → 本模块 leader_rows）",
            "capabilities": [],
            "runtime_verified": False,
        },
    }

# -*- coding: utf-8 -*-
'基诺维「破契的黑翼」169999 ``ginovi``（暗）：2026-09-27 平衡第四轮（d）——技能「掠影协奏」吞噬协力球。\n\n作者原话（2026-09-27）：「基诺维的技能能不能添加效果扣除协力球100%生命值,每消灭一个协力球自身攻击力+50%」。\n主会话可行性调研（扣血有友伤钳位只能打到 1HP ⇒ 真消灭只能用原生 ``RemoveMultiball``）呈给作者后，作者选择题四项：\n\n- 吃球范围 =「只吃角色召唤球（推荐）」：只吃角色技能召唤的有生命协力球（校园奈芙光/暗球、暗系召唤者的球等）；\n  不吃炸弹球、关卡 NPC 协力角色、kind=1 非生物投射球（魔女火球等），也不吃碧安卡幼龙 1199891。\n- 叠加方式 =「每次施放覆盖，上限9个（推荐）」：每次施放按本次吃掉的个数，每个自身攻击力 +50%，最多 9 个（+450%），\n  持续 750 帧（12.5 秒，与技能其余增益一致）；再施放覆盖为新个数（引擎默认降为新值并刷新时长）；\n  0 个球时不执行、不覆盖已有加成。\n- 生效档位 =「技能本体就有（推荐）」：技能 / 技能＋ 两档、强化 / 非强化两支都生效（节点放在\n  ``ConditionalsChangeSkillFlag`` 之前）；技能说明写吞噬效果（本体效果），不写进强化条目。\n- 奈芙联动 =「保留联动，真机看强度（推荐）」：奈芙的球 1699891/1699892 在白名单内，奈芙队长第 6 行不改。\n\nDSL（签名按 ``wf_dsl_sig`` 核对）::\n\n    ConditionalsMultiballNumber(DEVOUR_IDS, [], 1, Block[\n        MultiballNumberVariable(DEVOUR_VARIABLE, False, DEVOUR_IDS, [], 1, 9),   # V = min(个数, 9)；先数后删\n        RemoveMultiball(False, DEVOUR_IDS),                                      # 基诺维自己不召球 ⇒ 第一参 False\n        CreateCondition(-17, [ACAttackPoint 750 帧 × 0.5·V], …, "ginovi_devour", None, False, 3, …),\n    ], Block[])\n\n陷阱（测试逐条锁）：\n\n1. 键串必须非空且树内唯一：ConditionSlot 合并键 gid 用不乘 mul 的内容算，强化支固定 +50%\n   （``SKILL_ATTACK_UP_EXTRA``，750 帧，键串空）与本节点同形；键串空 ⇒ 同 gid，后到的强化支把 0.5×N 整条覆盖成\n   +50%（静默失效）。官方带 mul 的 CreateCondition（katana_ghost_wt22 / estateguild_leader）键串都非空。\n2. ID 表语义不一致：``RemoveMultiball`` 的 [] 被转成 null = 全部；``MultiballNumberVariable`` /\n   ``ConditionalsMultiballNumber`` 的 [] = 一个都不匹配 ⇒ 三处同一份非空 :data:`DEVOUR_IDS`（给了 ID 表时炸弹球永不匹配）。\n3. 先数后删（删后待发 / 入场中的球已销毁，计数不全）。\n4. 不进 TargetMate 作用域（联机跨机只许治疗/状态）；目标 -17（自身）、付与种类 3。\n\n:data:`DEVOUR_IDS` = :func:`scan_devour_ids` 对 live 的扫描结果（测试对 live 重扫断言相等）：live\n``action_skill`` / ``ability`` / ``leader_ability`` 引用的 ``battle/action/skill/action/**`` DSL（= 可玩角色的技能与\n629 能力技能）里 ``CreateSummonsMultiball`` 用到的 ID，取 live ``multiball`` 表 c25 == 0（有生命 SummonsMultiball，\nisLivingKind）的，排除 1199891。敌方 DSL（boss_kadomatsu 召 202001，路径 battle/action/enemy/**）、炸弹\n（1001–1006，CreateBombMultiball）、关卡 NPC（不是技能召唤）自然不在内；kind=1 的 3110021–23 / 3310101–02 被 c25 滤掉。\n\n技能说明（action_skill 两档 c1、character_text c5/c7、服务端 cdndata/character_text.json [5]/[7]，六处一致）\n末尾追加「；吞噬场上被召唤的协力球，赋予自身攻击力提升效果【效果随吞噬数量提升[最大9个]】」（官方「【效果随…提升[最大N]】」句式，上限照写，\n定性无数字）；强化条目 ``change_skill_ginovi`` 与能力面板不动。\n\n生成器 ``work/character_packs/ginovi/build_workspace.py``：常量 ``DEVOUR_*`` + ``skill_devour_multiballs()`` 插在\n``m4_skill_root()`` 的 ``ConditionalsChangeSkillFlag`` 之前，``CT_SKILL_DESC`` 同步；测试断言生成器输出 == :func:`revise`\n输出。kit 重建会写包，本模块不运行。\n\n接口见 ``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``：:func:`revise` 只经 ``read`` 读 live，开头按\n:data:`BEFORE` 摘要校验（漂移即抛 :class:`GinoviDevourError`，fail closed），不改 ``read`` 的返回对象。\n本模块不写 live store / assets / .cdn / 候选包，不发布，不 git。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl
import wf_dsl_sig
import wf_midautumn_kitlib as KL

CID = "169999"
CODE = "ginovi"
PACKAGES = ["ginovi"]
#: 候选现值 0.3.2（第三轮 ``wf_balance_20260927c_ginovi`` 暂存回写）→ 递增。
PACKAGE_VERSION = {"ginovi": "0.3.3"}
#: 只用原生命令（ConditionalsMultiballNumber / MultiballNumberVariable / RemoveMultiball 客户端原有），不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 ginovi 与 live 在本模块读取的 5 个键上逐字相同（2026-09-27 只读核对，链尾 1.4.1055）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 5                                   # master/character c3：暗（0 基内部元素）
SKILL_NAME = "掠影协奏"
LEVELS = ("1", "2")
PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in LEVELS}
TEXT_NCOLS = 12
TEXT_NAME_COLUMNS = (4, 6)
TEXT_DESC_COLUMNS = (5, 7)

# ------------------------------------------------------------------ 吞噬

MULTIBALL_TABLE = "master/battle/multiball/multiball.orderedmap"
MULTIBALL_KIND_COLUMN = 25                    # c25 = kind：0 = 有生命（isLivingKind），1 = 非生物投射球
LIVING_KIND = "0"
SKILL_PROGRAM_PREFIX = "battle/action/skill/action/"
SCAN_TABLES = ("master/skill/action_skill.orderedmap", "master/ability/ability.orderedmap",
               "master/ability/leader_ability.orderedmap")
#: live 扫描结果（:func:`scan_devour_ids`，2026-09-27 链尾 1.4.1055）：48 个。
DEVOUR_IDS = (
    1110021, 1110022, 1110061, 1110062, 1110063, 1110064, 1110391, 1110392, 1110393, 1110394,
    1110811, 1110812, 1111351, 1111352, 1111471, 1111472, 1111711, 1111712, 1130011, 1399961,
    1610391, 1610392, 1610511, 1610512, 1610871, 1610872, 1611051, 1611291, 1611292, 1611771,
    1611772, 1611891, 1611892, 1611951, 1611952, 1699891, 1699892, 2510061, 2510062, 2510063,
    2610011, 2610012, 2610651, 2610652, 2630031, 2630032, 3510041, 3510042,
)
DEVOUR_EXCLUDED_IDS = (1199891,)              # 碧安卡幼龙（作者：不吃）
NEPHTIM_BALLS = (1699891, 1699892)            # 校园奈芙光/暗球（作者：保留联动）
DEVOUR_VARIABLE = 1
DEVOUR_CAP = 9
DEVOUR_ATTACK = 0.5
DEVOUR_FRAMES = 750
DEVOUR_CONDITION_KEY = "ginovi_devour"
DEVOUR_SUBJECT = -17
DEVOUR_TARGET_KIND = 3
SKILL_ATTACK_UP_EXTRA = 0.5                   # 强化支固定 +50%（同形节点，键串空 —— 陷阱 1 的对照）
VARIABLE_COMMANDS = ("MultiballNumberVariable", "BindConditionAccumulationVariable",
                     "BindCoffinRevivalCountVariableOf", "BindCoffinRevivalCountVariable")
DEVOUR_COMMANDS = ("ConditionalsMultiballNumber", "MultiballNumberVariable", "RemoveMultiball")
FLAG_COMMAND = "ConditionalsChangeSkillFlag"

# ------------------------------------------------------------------ 技能说明

OLD_DESC = ("化作黑影掠过战场，为全体队员赋予护盾，为全体参战角色赋予攻击力提升效果／技能伤害提升效果／"
            "贯穿效果，并消耗其生命值；对全场敌人附加全属性抗性下降效果")
DEVOUR_DESC = "；吞噬场上被召唤的协力球，赋予自身攻击力提升效果【效果随吞噬数量提升[最大9个]】"
NEW_DESC = OLD_DESC + DEVOUR_DESC

# ------------------------------------------------------------------ 输入基线

#: ``{(kind, key): sha256}``：revise() 读取的每一项在 live 1.4.1055 上的摘要（2026-09-27 只读采集）。
#: fixture ``tests/fixtures/balance_20260927d_ginovi.json`` 同源。
BEFORE: dict[tuple[str, Any], str] = {
    # 两档 DSL 字节相同（生成器同一棵 m4_skill_root，ActionDsl 头也相同）。
    ("dsl", PROGRAMS["1"]): "c0cbca8cb7d25d9721fba1c3137744607ac2604453bb1246e0d3850716bcfc77",
    ("dsl", PROGRAMS["2"]): "c0cbca8cb7d25d9721fba1c3137744607ac2604453bb1246e0d3850716bcfc77",
    ("action", CODE): "b4a9131ad64f664b529405851cb2958e355e3942ff5cb55a7e68e946e8028cec",
    # 客户端表与服务端镜像逐字相同。
    ("text", CID): "546a704b588e738e22e6dfde35c13bf804a135448a918a5fbe21d19f01dc92a9",
    ("server_text", CID): "546a704b588e738e22e6dfde35c13bf804a135448a918a5fbe21d19f01dc92a9",
}


class GinoviDevourError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise GinoviDevourError(message)


# ------------------------------------------------------------------ DSL 小工具

def _power(value: float | int) -> list[dict]:
    return [{"min": value, "max": value}]


def _command(name: str, *params: Any) -> list[Any]:
    return ["Command", [name, *params]]


def _block(*expressions: Any) -> list[Any]:
    return ["Block", list(expressions)]


def is_command(node: Any, name: str | None = None) -> bool:
    return (isinstance(node, list) and len(node) == 2 and node[0] == "Command" and isinstance(node[1], list)
            and bool(node[1]) and (name is None or node[1][0] == name))


def walk(node: Any, path: tuple = ()):
    """深度优先：产出 ``(node, ancestors)``（ancestors = 自根起的祖先节点元组）。"""
    yield node, path
    if isinstance(node, list):
        for child in node:
            yield from walk(child, path + (node,))
    elif isinstance(node, dict):
        for child in node.values():
            yield from walk(child, path + (node,))


def commands(tree: Any, name: str | None = None) -> list[list[Any]]:
    return [node for node, _ in walk(tree) if is_command(node, name)]


def signature_problems(tree: Any) -> list[str]:
    problems = []
    for node, _ in walk(tree):
        if isinstance(node, list) and len(node) == 2 and node[0] in ("Command", "Event") \
                and isinstance(node[1], list) and node[1]:
            table = wf_dsl_sig.COMMANDS if node[0] == "Command" else wf_dsl_sig.EVENTS
            name = node[1][0]
            if name not in table:
                problems.append(f"unknown {node[0]} {name}")
            elif len(node[1]) - 1 != len(table[name]):
                problems.append(f"{name} arity {len(node[1]) - 1} != {len(table[name])}")
    return problems


def condition_keys(tree: Any) -> list[str]:
    """树内每个 CreateCondition 的键串（params[7]）。"""
    return [node[1][7] for node in commands(tree, "CreateCondition")]


# ------------------------------------------------------------------ 白名单扫描（live）

def summoned_multiball_ids(tree: Any) -> set[int]:
    return {int(node[1][2]) for node in commands(tree, "CreateSummonsMultiball")}


def _program(cell: str) -> str:
    suffix = ".action.dsl.amf3.deflate"
    return cell[:-len(suffix)] if cell.endswith(suffix) else cell


def skill_program_refs(store: Path) -> dict[str, list[str]]:
    """live 三张表引用的 ``battle/action/skill/action/**`` 程序 → 引用者（``action:<code>/<lv>`` / ``ability:<key>`` …）。"""
    import wf_mod_tool as C
    import wf_share_update_codec as X
    refs: dict[str, set[str]] = {}
    for logical in SCAN_TABLES:
        rows = X.unpack(C.table_path(store, logical).read_bytes())
        for key, raw in rows.items():
            if logical.endswith("action_skill.orderedmap"):
                records = [(f"action:{key}/{inner}", fields) for inner, fields in C.decode_action_skill_row(raw)]
            else:
                tag = logical.rsplit("/", 1)[-1].split(".")[0]
                records = [(f"{tag}:{key}", row) for row in X.csv_read(raw)]
            for label, cells in records:
                for cell in cells:
                    if isinstance(cell, str) and cell.startswith(SKILL_PROGRAM_PREFIX):
                        refs.setdefault(_program(cell), set()).add(label)
    return {program: sorted(labels) for program, labels in sorted(refs.items())}


def scan_devour_ids(store: Path) -> dict[str, Any]:
    """按作者规则从 live store 重新生成白名单（只读）。返回 ``ids``（升序元组）与取证明细。"""
    import zlib
    import wf_mod_tool as C
    import wf_share_update_codec as X
    store = Path(store)
    summoned: dict[int, list[str]] = {}
    absent = []
    for program in skill_program_refs(store):
        path = C.table_path(store, wf_dsl.dsl_logical(program))
        if not path.is_file():
            absent.append(program)                  # 表里引用但 store 没有的程序（官方遗留），无从召球
            continue
        tree = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
        for ball in summoned_multiball_ids(tree):
            summoned.setdefault(ball, []).append(program.rsplit("/", 1)[-1])
    table = X.unpack(C.table_path(store, MULTIBALL_TABLE).read_bytes())
    kinds = {ball: (X.csv_read(table[str(ball)])[0][MULTIBALL_KIND_COLUMN] if str(ball) in table else None)
             for ball in summoned}
    ids = tuple(sorted(ball for ball, kind in kinds.items()
                       if kind == LIVING_KIND and ball not in DEVOUR_EXCLUDED_IDS))
    return {"ids": ids, "summoned": {ball: sorted(p) for ball, p in sorted(summoned.items())},
            "kinds": dict(sorted(kinds.items())), "absent_programs": absent,
            "excluded": list(DEVOUR_EXCLUDED_IDS)}


# ------------------------------------------------------------------ 节点

def devour_node() -> list[Any]:
    """与生成器 ``skill_devour_multiballs()`` 逐字相同（测试断言）。"""
    ids = list(DEVOUR_IDS)
    return _command(
        "ConditionalsMultiballNumber", list(ids), [], 1,
        _block(
            _command("MultiballNumberVariable", DEVOUR_VARIABLE, False, list(ids), [], 1, DEVOUR_CAP),
            _command("RemoveMultiball", False, list(ids)),
            _command("CreateCondition", DEVOUR_SUBJECT,
                     [["ACAttackPoint", _power(DEVOUR_FRAMES),
                       [{"min": DEVOUR_ATTACK, "max": DEVOUR_ATTACK, "mul": DEVOUR_VARIABLE}], _power(1)]],
                     _power(1), ["GenericConditionHitEffect"], True, False, DEVOUR_CONDITION_KEY, None, False,
                     DEVOUR_TARGET_KIND, _power(1), False),
        ),
        _block(),
    )


def _root(tree: Any) -> list[Any]:
    _require(isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl", "not an ActionDsl tree")
    root = tree[11]
    _require(isinstance(root, list) and len(root) == 2 and root[0] == "Block" and isinstance(root[1], list),
             "ActionDsl root is not a Block")
    return root


def flag_index(tree: Any) -> int:
    body = _root(tree)[1]
    flags = [i for i, node in enumerate(body) if is_command(node, FLAG_COMMAND)]
    _require(len(flags) == 1 and len(commands(tree, FLAG_COMMAND)) == 1,
             f"expected exactly one top-level {FLAG_COMMAND}")
    return flags[0]


def preimage_problems(tree: Any) -> list[str]:
    """live 树必须是改前形状：无吞噬命令、无变量、无 mul/vlv、键串未被占用（不接受自身输出）。"""
    problems = []
    for name in DEVOUR_COMMANDS + VARIABLE_COMMANDS:
        if commands(tree, name):
            problems.append(f"live tree already carries {name}")
    if DEVOUR_CONDITION_KEY in condition_keys(tree):
        problems.append(f"condition key {DEVOUR_CONDITION_KEY!r} already used")
    if any(isinstance(node, dict) and ("mul" in node or "vlv" in node) for node, _ in walk(tree)):
        problems.append("live tree already reads a variable (mul/vlv)")
    return problems


def insert_devour(tree: Any) -> list[Any]:
    out = deepcopy(tree)
    index = flag_index(out)
    _root(out)[1].insert(index, devour_node())
    return out


def devour_problems(tree: Any) -> list[str]:
    """吞噬节点结构锁（陷阱 1–4 + 位置/数值）。"""
    problems: list[str] = []
    try:
        body = _root(tree)[1]
        index = flag_index(tree)
    except GinoviDevourError as error:
        return [str(error)]
    gates = commands(tree, "ConditionalsMultiballNumber")
    if len(gates) != 1 or index == 0 or body[index - 1] is not gates[0]:
        return [f"expected one ConditionalsMultiballNumber directly before {FLAG_COMMAND} at the top level"]
    gate = gates[0][1]
    for name in ("MultiballNumberVariable", "RemoveMultiball"):
        if len(commands(tree, name)) != 1:
            problems.append(f"expected exactly one {name}")
    count_ids, groups, threshold, hit, miss = gate[1:]
    if (groups, threshold) != ([], 1):
        problems.append(f"gate groups/threshold {groups}/{threshold} != []/1")
    if miss != ["Block", []]:
        problems.append("0-ball branch must be empty (no execution, keep the previous buff)")
    inner = hit[1] if isinstance(hit, list) and len(hit) == 2 and hit[0] == "Block" else []
    names = [node[1][0] if is_command(node) else None for node in inner]
    if names != ["MultiballNumberVariable", "RemoveMultiball", "CreateCondition"]:
        return problems + [f"devour branch order {names} != count → remove → buff"]
    variable, remover, buff = inner[0][1], inner[1][1], inner[2][1]
    var_id, mine, var_ids, var_groups, divisor, cap = variable[1:]
    remove_mine, remove_ids = remover[1:]
    id_lists = (count_ids, var_ids, remove_ids)
    if not all(isinstance(ids, list) and ids for ids in id_lists) or not (count_ids == var_ids == remove_ids):
        problems.append("the three ID lists must be the same non-empty whitelist")
    if list(count_ids or []) != list(DEVOUR_IDS):
        problems.append("ID whitelist differs from DEVOUR_IDS")
    if any(ball in (count_ids or []) for ball in DEVOUR_EXCLUDED_IDS):
        problems.append("excluded multiball in the whitelist")
    if (mine, remove_mine) != (False, False):
        problems.append("Ginovi summons nothing: the own-summons flag must be False")
    if (var_groups, divisor, cap) != ([], 1, DEVOUR_CAP):
        problems.append(f"MultiballNumberVariable groups/divisor/cap {var_groups}/{divisor}/{cap}")
    subject, kinds, _stack, _effect, _a, _b, key, _hit, _c, target_kind, _d, _e = buff[1:]
    if (subject, target_kind) != (DEVOUR_SUBJECT, DEVOUR_TARGET_KIND):
        problems.append(f"buff target {subject}/{target_kind} != -17/3")
    if not (len(kinds) == 1 and kinds[0][0] == "ACAttackPoint"
            and kinds[0][1] == _power(DEVOUR_FRAMES)
            and kinds[0][2] == [{"min": DEVOUR_ATTACK, "max": DEVOUR_ATTACK, "mul": var_id}]
            and kinds[0][3] == _power(1)):
        problems.append(f"buff content {kinds} != ACAttackPoint {DEVOUR_FRAMES}f × {DEVOUR_ATTACK}·V{var_id}")
    if not (isinstance(key, str) and key):
        problems.append("condition key must be non-empty (empty key merges with the enhanced +50%)")
    elif condition_keys(tree).count(key) != 1:
        problems.append(f"condition key {key!r} is not unique in the tree")
    variables = [node[1][1] for name in VARIABLE_COMMANDS for node in commands(tree, name)]
    if variables != [var_id] or var_id != DEVOUR_VARIABLE:
        problems.append(f"variable {var_id} is not the only variable in the tree: {variables}")
    readers = [node for node, _ in walk(tree) if isinstance(node, dict) and ("mul" in node or "vlv" in node)]
    if len(readers) != 1:
        problems.append(f"expected one mul reader, got {len(readers)}")
    # 陷阱 4：不在 TargetMate 作用域（同一 Block 里不跟 TargetMate、主体不是任何 TargetMate 绑定）。
    mate_binds = {node[1][1] for node in commands(tree, "TargetMate")}
    if subject in mate_binds:
        problems.append("devour buff targets a TargetMate binding")
    for node, ancestors in walk(tree):
        if node is gates[0] and any(isinstance(a, list) and len(a) == 2 and a[0] == "Block"
                                    and any(is_command(x, "TargetMate") for x in a[1]) for a in ancestors):
            problems.append("devour node sits in a block with TargetMate")
    return problems


def tree_gate_problems(tree: Any) -> list[str]:
    problems = [f"signature: {p}" for p in signature_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 round-trip mismatch")
    problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject_binding: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup_scope: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_area: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    return problems


# ------------------------------------------------------------------ 技能说明

def desc_problems(text: str) -> list[str]:
    problems = [f"skill desc: {p}" for p in KL.panel_problems(text)]
    cap_note = f"[最大{DEVOUR_CAP}个]"                       # 本体上限照写（官方 katana_ghost_wt22「[最大4次]」）
    if DEVOUR_DESC.count(cap_note) != 1:
        problems.append(f"skill desc: devour sentence must state the cap {cap_note}")
    if any(ch.isdigit() for ch in DEVOUR_DESC.replace(cap_note, "")):
        problems.append("skill desc: devour sentence must be qualitative apart from the cap")
    for word in ("强化", "共鸣", "队长"):
        if word in DEVOUR_DESC:
            problems.append(f"skill desc: devour sentence carries enhanced/condition wording {word!r}")
    return problems


def revise_texts(inputs: dict) -> dict[str, Any]:
    actions = []
    levels = [inner for inner, _fields in inputs["action", CODE]]
    _require(levels == list(LEVELS), f"action_skill {CODE} levels {levels}")
    for (inner, fields), name in zip(inputs["action", CODE], (SKILL_NAME, SKILL_NAME + "＋")):
        fields = list(fields)
        _require(fields[0] == name and fields[7] == PROGRAMS[inner] and fields[1] == OLD_DESC,
                 f"action_skill {CODE}/{inner}: name/program/c1 differ from the reviewed text")
        fields[1] = NEW_DESC
        actions.append((inner, fields))
    rows_out = {}
    for kind in ("text", "server_text"):
        rows = deepcopy(inputs[kind, CID])
        _require(isinstance(rows, list) and len(rows) == 1 and len(rows[0]) == TEXT_NCOLS,
                 f"{kind}:{CID}: expected one {TEXT_NCOLS}-column row")
        _require([rows[0][c] for c in TEXT_NAME_COLUMNS] == [SKILL_NAME, SKILL_NAME + "＋"],
                 f"{kind}:{CID}: skill names drifted")
        for col in TEXT_DESC_COLUMNS:
            _require(rows[0][col] == OLD_DESC, f"{kind}:{CID} c{col}: live description differs from the reviewed text")
            rows[0][col] = NEW_DESC
        rows_out[kind] = rows
    return {"action": {CODE: actions}, "text": {CID: rows_out["text"]}, "server_text": {CID: rows_out["server_text"]}}


# ------------------------------------------------------------------ 主入口

def _baseline(read: Callable[[str, Any], Any]) -> dict:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        if value is None or digest(value) != want:
            raise GinoviDevourError(f"live drift: {kind}:{key} is not the reviewed baseline")
        inputs[kind, key] = deepcopy(value)
    return inputs


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    trees = [inputs["dsl", PROGRAMS[level]] for level in LEVELS]
    # 两档是同一棵根（生成器 m4_skill_root 同源），只有 ActionDsl 头可能不同。
    _require(trees[0][11] == trees[1][11], "the two skill levels no longer share one root")
    dsl, problems = {}, []
    for level, tree in zip(LEVELS, trees):
        found = preimage_problems(tree) + [f"live {p}" for p in tree_gate_problems(tree)]
        _require(not found, f"{PROGRAMS[level]}: unexpected preimage: {found}")
        new = insert_devour(tree)
        problems += [f"{PROGRAMS[level]}: {p}" for p in devour_problems(new) + tree_gate_problems(new)]
        before, after = _root(tree)[1], _root(new)[1]
        if after[:flag_index(tree)] + after[flag_index(tree) + 1:] != before:
            problems.append(f"{PROGRAMS[level]}: insertion touched another expression")
        dsl[PROGRAMS[level]] = new
    texts = revise_texts(inputs)
    descs = ([fields[1] for _inner, fields in texts["action"][CODE]]
             + [rows[0][c] for kind in ("text", "server_text") for rows in texts[kind].values() for c in TEXT_DESC_COLUMNS])
    if set(descs) != {NEW_DESC} or len(descs) != 6:
        problems.append("the six skill descriptions disagree")
    problems += desc_problems(NEW_DESC)
    if problems:
        raise GinoviDevourError("; ".join(problems))

    return {
        "ability": {}, "leader": {}, "cas": {},
        "text": texts["text"], "table": {}, "action": texts["action"], "dsl": dsl,
        "server_text": texts["server_text"], "new_programs": [],
        "notes": {
            "character": f"{CID} {CODE} 基诺维「破契的黑翼」（暗）",
            "source": "mod-tools/wf_balance_20260927d_ginovi.py",
            "request": "作者 2026-09-27「基诺维的技能能不能添加效果扣除协力球100%生命值,每消灭一个协力球自身攻击力+50%」",
            "choices": {
                "scope": "只吃角色召唤球（推荐）：角色技能召唤的有生命协力球；不吃炸弹 / 关卡 NPC / kind=1 投射球 / 碧安卡幼龙 1199891",
                "stacking": f"每次施放覆盖，上限 {DEVOUR_CAP} 个（推荐）：每个 +{DEVOUR_ATTACK:.0%}，{DEVOUR_FRAMES} 帧；0 个不执行",
                "tier": "技能本体就有（推荐）：两档、强化/非强化两支都有（节点在 ConditionalsChangeSkillFlag 之前）",
                "nephtim": "保留联动，真机看强度（推荐）：1699891/1699892 在白名单内，奈芙队长第 6 行不改",
            },
            "dsl": {
                "programs": list(dsl),
                "node": "ConditionalsMultiballNumber(ids,[],1,[MultiballNumberVariable(1,False,ids,[],1,9) → "
                        "RemoveMultiball(False,ids) → CreateCondition(-17,ACAttackPoint 750f × 0.5·V1,"
                        f"key {DEVOUR_CONDITION_KEY!r},kind 3)],[])",
                "position": f"top level, directly before {FLAG_COMMAND}",
                "whitelist": {"count": len(DEVOUR_IDS), "ids": list(DEVOUR_IDS), "excluded": list(DEVOUR_EXCLUDED_IDS),
                              "rule": "live action_skill/ability/leader_ability 引用的 battle/action/skill/action/** 里 "
                                      "CreateSummonsMultiball 的 ID，multiball c25==0，排除 1199891"},
                "traps": ["键串非空唯一（空键串与强化支 +50% 同 gid 被覆盖）", "三处同一非空 ID 表（RemoveMultiball [] = 全部）",
                          "先数后删", "不进 TargetMate 作用域（-17 / 付与种类 3）"],
            },
            "skill_description": {"before": OLD_DESC, "after": NEW_DESC,
                                  "places": "action_skill ginovi 1/2 c1、character_text c5/c7、cdndata/character_text.json [5]/[7]",
                                  "rule": "本体效果写技能说明，不写进强化条目（作者 0927 技能强化文案规范）"},
            "kept": ["强化条目 change_skill_ginovi 与能力/队长面板不动", "队长/能力行不动", "奈芙队长第 6 行不改"],
            "generator": {
                "file": "work/character_packs/ginovi/build_workspace.py",
                "constants": ["DEVOUR_IDS", "DEVOUR_EXCLUDED_IDS", "DEVOUR_VARIABLE", "DEVOUR_CAP", "DEVOUR_ATTACK",
                              "DEVOUR_FRAMES", "DEVOUR_CONDITION_KEY", "CT_SKILL_DESC"],
                "function": "skill_devour_multiballs()（m4_skill_root 里 ConditionalsChangeSkillFlag 之前）",
                "not_run": "只改源码；build/kit-v3 会写包，本模块不运行",
            },
            "runtime_verified": False,
        },
    }

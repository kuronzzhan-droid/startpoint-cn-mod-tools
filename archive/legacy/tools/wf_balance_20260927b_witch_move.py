'贝尔赛蒂亚（129952 dimension_witch_smr20_ex，水）：作者 2026-09-27 小重做（与克劳斯同批）。\n\n作者原话（聊天，2026-09-27）：「水魔女的能力4的额外技能改成每直击50次触发,ct10s并且移动到能力3,能力4和5去掉主位限制」。\n作者对选择题 ④ 的确认：能力4 与能力6 都去掉主位限制（能力5 本来就不限主位）。\n\n落点（行号 0 基 ``#n``；live 链尾 1.4.1051，含第二批穿刺削韧）：\n\n1. 环爆 629「无明幽环」行 ``1299524#2`` 整行移到能力3 ``1299523`` 末尾（成为 ``#2``）：\n   c0 ``dimension_witch_smr20_ex_4`` → ``_3``；触发 c27 23（自身发动技能）→ 20（MemberDirectAttack）；\n   c28 puller ``0``（自身计数，与同键 ``#0`` 的「直击 6 次 → 252」同一取数方式）不变；\n   c30/c31 100000 → 5000000（1 次 = 100000 ⇒ 50 次）；c35 CT 0 → 600 帧（10 秒）；\n   c1 ``false``、c2 ``special``、c34 ``(None)``、c39 ``(None)``、c47 629、c70/c71 原样。\n   629 文案键 ``ability_skill_witch_ex_ring`` 不含槽位号、候选 manifest 已认领 ⇒ 不改名（改名要重认领且受 MAX_PATH 约束）。\n   能力3 整键 c1=false（主位限定），629 只在主位生效 ⇒ 满足「629 副位禁」（wf_midautumn_kit_kyle/rolf/fluffy 同规则）。\n2. 能力4 ``1299524`` 移走 629 后剩 ``#0/#1``（143 → 391/394）：c1 false → true（两行都无 202 前置）。\n3. 能力6 ``1299526`` ``#0/#1``（持有增益 → 46 DirectAttack3 自身 / 410 水队直击独立乘区）：c1 false → true（无 202）。\n4. 能力5 ``1299525`` 本就三行 c1=true、无 202 ⇒ 不改；本模块只读取并核对这一前提（fail closed）。\n5. 环爆树 ``ability_skill_witch_ex_ring``：**不改、不返回**，削韧保持每次 1。只读核对：唯一判定区对单一目标只命中\n   1 次（``CalculatedUsingMaxNumOfHits 1`` + ``Some(1)``），onHit 里唯一的 CreateNormalAttack p13 ``{1,1}`` ⇒ 每次 1；\n   第二批口径 B.3：629 每次 ≤3，触发 CT ≤3 秒（180 帧）的 ≤1；新触发行 CT 600 帧 > 180 ⇒ 上限 3，1 ≤ 3 合规\n   （即使 CT 以后缩到 ≤180 帧，1 也不超 B.3 的快档上限 1）。\n   复核裁定（major）：任务书要求「调到合计 ≤3 的最大值」，其前提「第二批已把环爆树 p13 1→0.25」不成立——第二批改的是\n   **穿刺**树（8 段 p13 1→0.25，8→2），环爆树第二批「不读不改」（wf_balance_20260927b_belsetia notes.ring_unchanged），\n   live 一直是 p13 1。取 3 等于把 Down 上调到 3 倍，作者没有要求，且与本批「不希望频繁眩晕 boss」的方向相反；B.3 只是\n   上限，不要求顶格 ⇒ 默认保持 1。若作者确认要 3：恢复树改写（p13 ``{1,1}``→``{3,3}``，``dsl`` 返回该树并过四道门禁），\n   生成器 ``build_ability_skill_tree(2)`` p13 同改 ``_mm(3, 3)``。\n\n面板：水魔女六个能力槽都没有 desc_override 键，面板由客户端按行自动生成（本模块开头确认这些键在 live 仍不存在，\n存在即拒绝）；629 文案串与技能描述（action_skill / character_text / 服务端 character_text）都不写环爆的触发条件或削韧\n⇒ 无文案同步。\n\n生成器：``work/character_packs/thunder_witch_ex/build_workspace.py`` 已同步（只改源码常量，不运行）：\n``TRIG_DIRECT50_CD``、``build_ability_rows`` 环爆记录移到 ``AB_KEY[3]``（``SID[3]``）、能力4/6 unisonable ``true``、\n``stage_kit`` 的 PRECEDENT ``(AB_KEY[4],2)`` → ``(AB_KEY[3],2)``；``build_ability_skill_tree(2)`` 保持 p13 ``_mm(1, 1)``。\n测试断言生成器能力行 == :func:`revise` 输出、环爆树 == live。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做\n（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，第二批 b 后缀）。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_balance_20260927b_belsetia as batch2   # 同角色第二批：判定区命中数 / 削韧 / 四道 DSL 门禁
import wf_client_legality as legality

CID = "129952"
CODE = "dimension_witch_smr20_ex"
PACKAGES = ["thunder_witch_ex"]
#: 候选 manifest 现值 0.1.1（第二批穿刺削韧）→ 递增。
PACKAGE_VERSION = {"thunder_witch_ex": "0.1.2"}
CAPABILITIES: list[str] = []
#: 候选 ability 表本角色 6 键、环爆树与 live 逐字一致（2026-09-27 只读核对）⇒ 无已审漂移。
REVIEWED_DRIFT: dict = {}
ELEMENT = batch2.ELEMENT          # master/character c3：水（0 基内部元素）
ABILITY_WIDTH = 126

ABILITY = {slot: f"{CID}{slot}" for slot in range(1, 7)}
SID = {slot: f"{CODE}_{slot}" for slot in range(1, 7)}
RING_KEY = "ability_skill_witch_ex_ring"
RING_PROGRAM = f"battle/action/skill/action/ability_skill/{RING_KEY}${RING_KEY}"
PIERCE_KEY = batch2.PIERCE_KEY
PIERCE_PROGRAM = batch2.PIERCE_PROGRAM
INVOKE_STRINGS = frozenset({PIERCE_KEY, RING_KEY})
#: 客户端按「desc_override_ + 首行 string_id」取覆盖；这些键在 live 不存在 ⇒ 面板自动生成（存在即拒绝）。
AUTO_PANEL_KEYS = (f"desc_override_{CODE}", *(f"desc_override_{CODE}_{slot}" for slot in range(1, 7)))

#: 列位（ability 126 列布局）。
C_UNISON, C_TRIGGER, C_PULLER, C_TH_LO, C_TH_HI, C_LIMIT, C_CT, C_PRECONTENT, C_CONTENT = 1, 27, 28, 30, 31, 34, 35, 39, 47
C_STRING, C_PATH = 70, 71
PRECONDITION_COLS = (6, 13, 20)

#: 移动前 ``1299524#2`` 的非空格（全部 126 格的其余格必须为空串）。
RING_ROW_BEFORE = {
    0: SID[4], 1: "false", 2: "special", 3: "0", 5: "0", 6: "0", 13: "0", 20: "0",
    27: "23", 28: "0", 30: "100000", 31: "100000", 34: "(None)", 35: "0", 39: "(None)",
    46: "0", 47: "629", 70: RING_KEY, 71: RING_PROGRAM,
}
#: 移动时逐格改动 {col: (改前, 改后)}；其余格逐字搬运。
RING_MOVE = {
    0: (SID[4], SID[3]),
    C_TRIGGER: ("23", "20"),              # 自身发动技能 → MemberDirectAttack
    C_TH_LO: ("100000", "5000000"),        # 1 次 → 50 次（1 次 = 100000）
    C_TH_HI: ("100000", "5000000"),
    C_CT: ("0", "600"),                    # 10 秒
}
RING_DIRECT_HITS, RING_CT_FRAMES = 50, 600
#: {外层键: {live 行号: {col: (改前, 改后)}}}（去主位）。
UNLOCK = {
    ABILITY[4]: {0: {C_UNISON: ("false", "true")}, 1: {C_UNISON: ("false", "true")}},
    ABILITY[6]: {0: {C_UNISON: ("false", "true")}, 1: {C_UNISON: ("false", "true")}},
}
#: 每个键的 (c0, c27 触发 / c97 持续触发, c47 瞬发内容 / c109 持续内容) 指纹，按行序。
SHAPE = {
    ABILITY[3]: ((SID[3], "20", "252"), (SID[3], "2", "629")),
    ABILITY[4]: ((SID[4], "143", "391"), (SID[4], "143", "394"), (SID[4], "23", "629")),
    ABILITY[5]: ((SID[5], "0", "211"), (SID[5], "144", "32"), (SID[5], "144", "388")),
    ABILITY[6]: ((SID[6], "8", "46"), (SID[6], "8", "410")),
}
#: 改后每键的主位标记（c1）：能力3 仍主位限定（含两条 629），能力4/5/6 全开。
UNISON_AFTER = {ABILITY[3]: "false", ABILITY[4]: "true", ABILITY[5]: "true", ABILITY[6]: "true"}

#: 629 每次单目标削韧上限（第二批口径 B.3，与第二批模块同一组常量）。
INVOKE_CAP, INVOKE_CAP_FAST, FAST_CT_FRAMES = batch2.INVOKE_CAP, batch2.INVOKE_CAP_FAST, batch2.FAST_CT_FRAMES
RING_HITS = 1
#: 环爆 CreateNormalAttack p13：保持 1（不改树）。1 次命中 × 1 = 1 ≤ 上限 3（也 ≤ 快档上限 1）。
RING_P13 = 1

#: live 输入基线（本地链尾 1.4.1051，stage_batch.make_read(live_only=True) 只读取数）；任一不符 ⇒ 拒绝。
#: 能力5 与两条 629 文案只读核对（前提：能力5 已不限主位；629 文案键存在），不返回。
BEFORE = {
    ("ability", ABILITY[3]): "06341a49a5affcbf0c731f45e1d8c4be49dc3755df15e9bb025d47f255b27ebd",
    ("ability", ABILITY[4]): "fbce6cd0fd597637f12cb81fbddb6d7f598e80968aa9b4e1126a4e88e6659e3d",
    ("ability", ABILITY[5]): "ed43f9bbf3ae28a4e28ade3938693fa80d7405a6caac3aab07fb8cec64be3d1f",
    ("ability", ABILITY[6]): "6d56706951e087009966bcf411c823894f40fa9bf26eb18d21321437c5b1bc5e",
    ("cas", PIERCE_KEY): "2a7ad705efb33df87a9cd03ea61761918907dc5f7b158c24cf1d45ea34bafdf3",
    ("cas", RING_KEY): "500bb91041dbe9401ca99d0ca26ad1c8d65e3992d1dae8a3178a10eb82cb55e7",
    ("dsl", RING_PROGRAM): "cdb238c6e050bf82eac28eae1d8a309884e2c895d7a2ae064d0c986f5b1265d4",
}


class WitchMoveError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WitchMoveError(f"{CID} witch move 20260927b: {message}")


def _absent(read: Callable[[str, Any], Any], kind: str, key: str) -> bool:
    try:
        return read(kind, key) is None
    except KeyError:
        return True


def _baseline(read: Callable[[str, Any], Any]) -> dict:
    """读取并锁定全部输入；任何一项漂移都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in BEFORE:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise WitchMoveError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    for key in AUTO_PANEL_KEYS:
        if not _absent(read, "cas", key):
            raise WitchMoveError(f"live drift: cas:{key} now exists (panel is no longer auto-generated)")
    return inputs


# ---------------------------------------------------------------- 词条行


def _fingerprint(row: list[str]) -> tuple[str, str, str]:
    if row[5] == "1":                                   # 持续行：c97 持续触发 / c109 持续内容
        return row[0], row[97], row[109]
    return row[0], row[C_TRIGGER], row[C_CONTENT]


def _shape(key: str, rows: list[list[str]]) -> None:
    want = SHAPE[key]
    _require(len(rows) == len(want), f"{key}: expected {len(want)} records, got {len(rows)}")
    for index, (row, fingerprint) in enumerate(zip(rows, want)):
        _require(len(row) == ABILITY_WIDTH, f"{key}#{index}: expected {ABILITY_WIDTH} columns")
        _require(_fingerprint(row) == fingerprint, f"{key}#{index}: fingerprint {_fingerprint(row)} != {fingerprint}")
        _require(all(row[col] == "0" for col in PRECONDITION_COLS), f"{key}#{index}: unexpected precondition")


def _edit(row: list[str], edits: dict[int, tuple[str, str]], tag: str) -> list[str]:
    out = list(row)
    for col, (old, new) in edits.items():
        _require(row[col] == old, f"{tag} c{col}: expected {old!r}, got {row[col]!r}")
        out[col] = new
    return out


def moved_ring_row(row: list[str]) -> list[str]:
    """``1299524#2`` → 能力3 末行：只改 c0 / 触发 / 阈值 / CT，其余格逐字搬运。"""
    _require(all(row[col] == RING_ROW_BEFORE.get(col, "") for col in range(ABILITY_WIDTH)),
             f"{ABILITY[4]}#2 is not the reviewed ring 629 row")
    return _edit(row, RING_MOVE, f"{ABILITY[4]}#2")


def ring_invoke_cap(row: list[str]) -> int:
    """629 行每次削韧上限（B.3）：行 CT ≤180 帧 ⇒ 1，否则 3。只认审查过的新触发形状。"""
    got = (row[C_UNISON], row[C_TRIGGER], row[C_PULLER], row[C_TH_LO], row[C_TH_HI], row[C_LIMIT], row[C_CT],
           row[C_PRECONTENT], row[C_CONTENT], row[C_STRING], row[C_PATH])
    want = ("false", "20", "0", "5000000", "5000000", "(None)", str(RING_CT_FRAMES), "(None)", "629",
            RING_KEY, RING_PROGRAM)
    _require(got == want, f"ring 629 row drift (re-check CT rule): {got}")
    return INVOKE_CAP_FAST if int(row[C_CT]) <= FAST_CT_FRAMES else INVOKE_CAP


def ability_rows(abilities: dict[str, list[list[str]]]) -> dict[str, list[list[str]]]:
    """改后的能力3 / 4 / 6（能力5 只核对不返回）。"""
    for key, rows in abilities.items():
        _shape(key, rows)
    a3, a4, a5, a6 = (abilities[ABILITY[slot]] for slot in (3, 4, 5, 6))
    _require(all(row[C_UNISON] == "false" for row in a3 + a4 + a6), "abilities 3/4/6 must start main-only")
    _require(all(row[C_UNISON] == "true" for row in a5), "ability 5 must already be open to the unison slot")
    out = {
        ABILITY[3]: [list(a3[0]), list(a3[1]), moved_ring_row(a4[2])],
        ABILITY[4]: [_edit(a4[i], UNLOCK[ABILITY[4]][i], f"{ABILITY[4]}#{i}") for i in (0, 1)],
        ABILITY[6]: [_edit(a6[i], UNLOCK[ABILITY[6]][i], f"{ABILITY[6]}#{i}") for i in (0, 1)],
    }
    for key, rows in out.items():
        _require(all(row[C_UNISON] == UNISON_AFTER[key] for row in rows), f"{key}: main-slot flag mismatch")
        for index, row in enumerate(rows):
            # 629 在副位不生效：只能留在 unisonable=false 的键里（kyle/rolf/fluffy 套件同规则）。
            _require(row[C_CONTENT] != "629" or row[C_UNISON] == "false", f"{key}#{index}: 629 in an open key")
    return out


def row_problems(rows_by_key: dict[str, list[list[str]]]) -> list[str]:
    problems = []
    for key, rows in rows_by_key.items():
        for index, row in enumerate(rows):
            tag = f"{key}#{index}"
            problems += [f"{tag}: {p}" for p in legality.client_legality_problems("ability", row)]
            problems += [f"{tag}: {p}" for p in legality.declared_block_field_problems("ability", row)]
            problems += [f"{tag}: {p}" for p in legality.invoke_skill_string_problems(row, INVOKE_STRINGS, "ability")]
    return problems


# ---------------------------------------------------------------- 环爆树削韧（只读核对，不改）


def check_ring_tree(tree, cap: int) -> float:
    """环爆树只读核对：唯一全屏判定区 1 次命中、唯一 CreateNormalAttack p13 = 1，每次削韧 ≤ ``cap``。

    不修改、不返回树；返回每次施放单目标削韧（= 1）。结构或 p13 漂移都拒绝（fail closed）。
    """
    _require(tree[:11] == ["ActionDsl", 1, ["None"], *[False] * 7, 0], "ring root header drift")
    areas = batch2.hit_areas(tree)
    _require(len(areas) == 1, f"ring must hold one hit area, got {len(areas)}")
    area, hits, attacks = areas[0]
    shape = (area[2], area[3], area[9], area[14], area[15], area[24])
    _require(shape == (-1, ["AB"], ["Rectangle", [{"min": 1080, "max": 1080}], [{"min": 1920, "max": 1920}]],
                       ["CalculatedUsingMaxNumOfHits", RING_HITS], ["Some", [{"min": 1, "max": 1}]], 4)
             and hits == RING_HITS, f"ring hit area drift: {shape} / {hits}")
    _require(len(attacks) == 1, f"ring onHit must hold one CreateNormalAttack, got {len(attacks)}")
    attack = attacks[0]
    _require(attack[1] == area[22] and attack[2] == 255, "ring CreateNormalAttack binding/element drift")
    _require(attack[13] == batch2._p13(RING_P13), f"ring p13 drift {attack[13]}")
    value = batch2.detoughness(tree)
    _require(value <= cap, f"ring detoughness {value} > 629 cap {cap}")
    return value


# ---------------------------------------------------------------- 入口


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    abilities = {ABILITY[slot]: inputs["ability", ABILITY[slot]] for slot in (3, 4, 5, 6)}
    for key in INVOKE_STRINGS:
        _require(len(inputs["cas", key]) == 1 and len(inputs["cas", key][0]) == 1, f"cas:{key} shape drift")
    rows = ability_rows(abilities)
    problems = row_problems(rows)
    ring_row = rows[ABILITY[3]][2]
    cap = ring_invoke_cap(ring_row)
    per_call = check_ring_tree(inputs["dsl", RING_PROGRAM], cap)   # 环爆树不改：只核对新触发下仍合规
    if problems:
        raise WitchMoveError("; ".join(problems))
    return {
        "ability": rows, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": {}, "server_text": {}, "new_programs": [],
        "notes": _notes(cap, per_call),
    }


def _notes(cap: int, per_call: float) -> dict[str, Any]:
    return {
        "source": "wf_balance_20260927b_witch_move.py",
        "spec": ("作者 2026-09-27：「水魔女的能力4的额外技能改成每直击50次触发,ct10s并且移动到能力3,能力4和5去掉主位限制」；"
                 "选择题④：能力4 与能力6 都去掉主位限制（能力5 本来就不限）；第二批口径 B.3"),
        "change": {
            f"ability:{ABILITY[4]}#2 → {ABILITY[3]}#2": (
                "环爆 629 整行搬到能力3 末尾：c0 _4→_3；c27 23→20（MemberDirectAttack）；c28 0（自身）不变；"
                "c30/c31 100000→5000000（50 次）；c35 0→600（10 秒）；c1 false / c2 special / c34 (None) / "
                "c39 (None) / c47 629 / c70 / c71 原样"),
            f"ability:{ABILITY[4]}#0-#1": "c1 false→true（143 → 391/394；无 202）",
            f"ability:{ABILITY[6]}#0-#1": "c1 false→true（持有增益 → 46 DirectAttack3 / 410 水队直击独立乘区；无 202）",
            f"ability:{ABILITY[5]}": "不改：三行本就 c1=true、无 202（作者选择题④确认）",
            f"dsl:{RING_KEY}": (f"不改、不返回：CreateNormalAttack p13 保持 {{1,1}}，单目标每次削韧 {per_call}"
                                f"（≤ 新 CT 下上限 {cap}）"),
        },
        "ring_detoughness": {
            "decision": ("保持每次 1，不上调（复核 major 的默认裁定）。任务书要求「调到合计 ≤3 的最大值」基于错误前提"
                         "「第二批已把环爆树 p13 1→0.25」：第二批改的是穿刺树（8 段 p13 1→0.25，8→2），环爆树第二批未改，"
                         "live 一直 p13 1。取 3 = Down 上调到 3 倍，作者没有要求，且与本批「不希望频繁眩晕 boss」方向相反；"
                         "B.3 的「每次 ≤3」只是上限，不要求顶格"),
            "rule": "口径 B.3：629 每次 ≤3；触发 CT ≤3 秒（180 帧）的 ≤1",
            "row_ct_frames": RING_CT_FRAMES, "per_call_cap": cap,
            "calculation": ("全屏判定区 CalculatedUsingMaxNumOfHits 1 + Some(1) ⇒ 每个敌人每次施放 1 次命中；"
                            "p13 = 1 ⇒ 每次 1×1 = 1 ≤ 3（也 ≤ 快档上限 1）"),
            "detoughness": per_call,
            "frequency": ("旧触发=每次自身发动技能（CT 0）；新触发=自身直击 50 次、CT 10 秒且 CT 期间计数丢弃"
                          "（AbilityTriggerHandler.countHandler），实际周期 = 10 秒 + 重新攒 50 次直击。"
                          "能力6 持有增益时直击算 3 段（kind 46）⇒ 约 17 次碰撞即够；环爆自带 ACDirectDamage 720 帧"
                          "会让「持有增益」更常成立，形成加速循环 ⇒ 触发可能比旧版（跟技能走）更频繁；"
                          "单次削韧不变，单位时间 Down 随触发频率变化，需真机观察"),
            "if_author_wants_3": ("作者确认要 3 时：恢复树改写（onHit 唯一 CreateNormalAttack p13 {1,1}→{3,3}，路径 "
                                  "[11,1,1,1,3,1,0,1,23,1,1,1,13]），revise() 的 dsl 返回该树并过 AMF3 往返与四道门禁；"
                                  "生成器 build_ability_skill_tree(2) p13 同改 _mm(3, 3)；测试同步"),
        },
        "precedents": {
            "trigger20_to_629": "live 1699805#0（自身、阈值 1、CT 120）、1399903#6（自身、10 次、CT 180）、"
                                "1399903#5（7 Yellow 100 次）；官方 629 只有 3 行（触发 139/2/65），官方零先例",
            "threshold_50": "官方 trigger 20 阈值只有 10/20/25/30/60/200 次；live 50 次先例 1299913#1、1399905#0、1699923#1"
                            "（均为 puller 7 编成计数）；自身 puller 0 + 50 次是这两类先例的组合",
            "unison_629": "629 只放 unisonable=false 的键（wf_midautumn_kit_kyle/rolf/fluffy 同一检查）",
        },
        "unison_semantics": ("水魔女在副位时，能力4/6 并入主位角色的能力池、「自身」= 主位角色："
                             "能力4 由主位角色的能力伤害命中触发（水魔女自己的 252 在能力3、副位不生效），"
                             "主位没有能力伤害时两行不触发；能力6 让持有增益的主位角色直击算 3 段、水队直击独立乘区照常"),
        "level_scaling": "629 的 {min,max} 按发起行所在能力的等级插值：环爆 6→9 倍与 ACDirectDamage 0.4→0.6 改由能力3 等级决定，"
                         "两键都满级时无差",
        "panel_text": ("六个能力槽无 desc_override（开头已核对不存在），面板由客户端按行自动生成；629 文案串与技能描述"
                       "不写触发条件或削韧 ⇒ 无文案同步。新行 c28=0 ⇒ InstantAbilityTriggerPullerKind.Myself"
                       "（InstantAbilityTriggerPullerKindTools.as case 0），按水魔女自身直击计数，不是全队；"
                       "wf_describe 的离线渲染把 puller 0 通用地写成「编成直接攻击≥50(CT10秒)」（旧行 1299523#0 同样渲染成"
                       "「编成直接攻击≥6」），「编成」只是该工具的通用措辞，转述给作者时应说「自身直击 50 次」"),
        "generator": ("work/character_packs/thunder_witch_ex/build_workspace.py：TRIG_DIRECT50_CD、build_ability_rows"
                      "（环爆移到 AB_KEY[3]/SID[3]、能力4/6 unisonable true，共 13 条记录）、stage_kit PRECEDENT "
                      "(AB_KEY[3],2)；build_ability_skill_tree(2) 保持 p13 _mm(1, 1)；测试断言生成器能力行 == revise()、"
                      "环爆树 == live"),
        "staging": ("暂存建议（复核 minor，主会话处理）：batch2/stage_batch.py 的 SNAPSHOT='revision_20260927b' 与 evidence 名"
                    "'revision-20260927b.json' 是固定值，直接复用会覆盖候选 manifest 里第二批 belsetia 的快照元数据与 evidence；"
                    "before/packages/thunder_witch_ex 是第二批之前的备份，reset_stage 会连第二批穿刺削韧一起撤掉。"
                    "应另起暂存目录（或先归档清空 batch2 的 stage/before/plans），并改用独立快照键 / evidence 名"
                    "（例如 revision_20260927c / revision-20260927c.json）。本模块只改 ability 表（dsl 为空）"),
        "batch2_interaction": ("第二批 wf_balance_20260927b_belsetia 锁了 ability:1299523 的 BEFORE，新 live 上重跑会 fail closed"
                               "（预期，勿重跑）；其候选测试的 package_version 断言已放宽为 ≥0.1.1（作者 09-27 小重做）"),
        "runtime_verified": False,
    }

# -*- coding: utf-8 -*-
"""斩铁·白梅 159998 ``samurai_robot_plum``（光）：2026-09-27 作者平衡批次（第二批）修订，纯函数。

作者原话：「斩铁的队长技共鸣时光属性角色发动技能时自身技能槽+5%改为除自身外的光属性角色发动技能
自身技能槽+5%，能力3的共鸣时光属性角色发动技能自身技能槽+5%连击+25改为除自身外的光属性角色发动技能
自身技能槽+5%,连击+50，斩铁去掉能力1的主位限制」。

落点（行号 = 0 起；只改下列 6 格，其余逐字保留）：

1. ``leader_ability:159998#3``（光共鸣：技能发动 trig23 → 自身技能槽 2.5%→5%）：
   触发 puller c26 ``7``（全队合计）→ ``6``（除自身合计），组 c27 ``White`` 保持 ⇒
   「除自身外的光属性角色发动技能时」。强度 c49/c50 = 2500/5000 不变。
   先例：官方 1611713#1（暗共鸣，trig23 + puller 6 → 自身技能槽）；live 雷吉斯队长 139994#2
   （trig23 + 6 + Yellow）、丝缇涅尔能力3 1599953#3/#4（trig23 + 6 + White，donor 就是本角色 1599983#4）。
2. ``ability:1599983#4``（技能发动 → 自身技能槽 5%）与 ``#5``（技能发动 → 自身追加连击）：
   puller c28 ``7`` → ``6``（组 c29 ``White`` 保持）；``#5`` 强度 c51/c52 2500000 → 5000000（连击 +25 → +50）。
3. ``ability:1599981``（能力1）去掉主位限制：``#1``（536 切换技能形态）与 ``#2``（629 追加剑士 PF）的
   前置1 c6 ``202``（OwnerIsMain）→ ``0``，前置2（c13=2 光共鸣 ≥6，c16/c17/c18）原位保留；
   整键 c1 本来就是 ``true``（不限主位池），保持。本角色没有 desc_override，面板由客户端按行自动生成。

副位语义（需真机）：去掉 202 后斩铁在合击副位时，本键两行并入主位角色的能力池、「自身」= 主位：
629 在主位角色发动技能时由主位执行（官方零先例；live 可进合击池的自制 629 共 11 行，如 1299921#0 /
1699894#1 / 1499885#1 / 1699945#0，含第一批雷吉斯 1399942#0；树只有 -18 球锚判定区 + 显式光元素
CreateNormalAttack + 震屏，伤害按执行者即主位的面板结算）；536 会打开主位角色的
技能 Flag1（live 带 536 的 14 名光角色，其 Flag1 条件都是无条件或光共鸣 / 主位，光共鸣队里本已为真）。

生成器链（重建后固定顺序）：``wf_seasonal7_kit_zantetsu``（改版施工单回放；kit 已钉冻结 donor 1499963#1（FROZEN_DONORS），
源码 sha 已变，``gates.json`` 的 ``kit_source_sha256`` 登记为已知过期、待按 tables→kit→…→gates 步序重跑）→
``wf_zantetsu_fever_revision.apply_candidate``（09-17 Fever 修订之后调用本模块 :func:`balance_rows`）。
测试断言「kit 行 → Fever 修订 → 本批」== :func:`revise` 输出。

另：丝缇涅尔 / 芙拉菲 / 妮可拉三个 kit 以 live ``1599981#1`` 为 donor 回放 536 行，已在
``wf_midautumn_kit_stinel.ABILITY[1]``、``wf_midautumn_kit_fluffy.PLAN[1]`` 与妮可拉设计稿
``work/character_packs/midautumn-20260920/design/nicola.json``（gitignore）的 cells 里显式钉住 ``c6=202``，
本批发布后重跑输出不变（不钉则三者都会 wf_describe drift 报错）。丝缇涅尔「友技回槽」借的 1599983#4
本来就显式写 c28=6，不受影响。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

CID = "159998"
CODE = "samurai_robot_plum"
PACKAGES = ["s7-zantetsu"]
#: 候选 manifest 现值 1.0.1（09-17 Fever 修订写入；更早的 evidence 只有 1.0.0）⇒ 1.0.2。
PACKAGE_VERSION = {"s7-zantetsu": "1.0.2"}
CAPABILITIES: list[str] = []
#: 候选 134 个 manifest 条目与文件逐一一致，三键与 live 逐字相同（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 4                        # master/character c3：光（0 基内部元素）
LIGHT = "White"
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
A1, A3 = f"{CID}1", f"{CID}3"
CAS_CHANGE_SKILL = f"change_skill_{CODE}"
CAS_PF = f"ability_skill_{CODE}_pf"
PF_PROGRAM = f"battle/action/skill/action/rare5/{CODE}${CODE}_pf"

PULLER_ALL_TOTAL = "7"             # 全队合计（含自身）
PULLER_OTHERS_TOTAL = "6"          # 除自身合计
OWNER_IS_MAIN = "202"
COMBO_OLD, COMBO_NEW = "2500000", "5000000"      # 追加连击 25 → 50（100000 = 1 连击）

LEADER_INDEX = 3                   # 队长第 4 行
A1_MAIN_ONLY_INDEXES = (1, 2)      # 能力1 第 2 行（536）、第 3 行（629）
A3_GAUGE_INDEX, A3_COMBO_INDEX = 4, 5              # 能力3 第 5 行（211 5%）、第 6 行（226）
LEADER_PULLER_COL = 26             # leader 触发块 c25 kind / c26 puller / c27 组
A1_PRECONDITION1_COL = 6           # ability 前置1 kind（c5 = 触发模式）
A3_PULLER_COL = 28                 # ability 触发块 c27 kind / c28 puller / c29 组
PRECONDITION_KIND_COLS = {"leader_ability": (4, 11, 18), "ability": (6, 13, 20)}

#: live 输入基线（2026-09-27 本地链尾 1.4.1048 只读取数，与候选 s7-zantetsu 1.0.1 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", CID): "87c686ac8e2b1af758552985530ec2eed652ddfd75ffe53b847618a038a1d15e",
    ("ability", A1): "d5b05aeea6f99afdd8734a54f8629be9e3559ad53725475c3cde10e82163dbbd",
    ("ability", A3): "abf98afc3d40672797fbb376d977a3e6be62368613dd6e3f5e323a096fccecf3",
    ("cas", CAS_CHANGE_SKILL): "d324ecee2c5c14f1f60d7a4864d6ac716ff6886d3df1e1cfc62a7d811410740d",
    ("cas", CAS_PF): "605e46c99e46e3cf8c4263f72ad508c03d0dbe1238fb15c8129476da04039881",
}

# ---------------------------------------------------------------- 逐格指纹（全部非空列；其余列必须为空）

_LEADER_GAUGE = {
    0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: LIGHT, 11: "0", 18: "0",
    25: "23", 26: PULLER_ALL_TOTAL, 27: LIGHT, 28: "100000", 29: "100000", 32: "(None)", 33: "0",
    37: "(None)", 44: "0", 45: "211", 46: "0", 49: "2500", 50: "5000",
}
_A1_COMMON = {
    0: f"{CODE}_1", 1: "true", 2: "action_skill", 3: "0", 5: "0", 6: OWNER_IS_MAIN,
    13: "2", 16: "600000", 17: "600000", 18: LIGHT, 20: "0", 39: "(None)", 46: "0",
}
_A1_CHANGE_SKILL = {**_A1_COMMON, 27: "0", 47: "536", 70: CAS_CHANGE_SKILL}
_A1_INVOKE_PF = {**_A1_COMMON, 27: "23", 28: "0", 30: "100000", 31: "100000", 34: "(None)",
                 35: "0", 47: "629", 70: CAS_PF, 71: PF_PROGRAM}
_A3_COMMON = {
    0: f"{CODE}_3", 1: "false", 2: "action_skill", 3: "0", 5: "0", 6: "2", 9: "600000",
    10: "600000", 11: LIGHT, 13: "0", 20: "0", 27: "23", 28: PULLER_ALL_TOTAL, 29: LIGHT,
    30: "100000", 31: "100000", 34: "(None)", 35: "0", 39: "(None)", 46: "0", 48: "0",
}
_A3_GAUGE = {**_A3_COMMON, 47: "211", 51: "5000", 52: "5000"}
_A3_COMBO = {**_A3_COMMON, 47: "226", 51: COMBO_OLD, 52: COMBO_OLD}

#: (改前, 改后) 指纹。改后 = 改前 + 本批的格；两态都接受 ⇒ 变换幂等，其余形态一律拒绝。
LEADER_CELLS = (_LEADER_GAUGE, {**_LEADER_GAUGE, LEADER_PULLER_COL: PULLER_OTHERS_TOTAL})
A1_CELLS = {
    1: (_A1_CHANGE_SKILL, {**_A1_CHANGE_SKILL, A1_PRECONDITION1_COL: "0"}),
    2: (_A1_INVOKE_PF, {**_A1_INVOKE_PF, A1_PRECONDITION1_COL: "0"}),
}
A3_CELLS = {
    A3_GAUGE_INDEX: (_A3_GAUGE, {**_A3_GAUGE, A3_PULLER_COL: PULLER_OTHERS_TOTAL}),
    A3_COMBO_INDEX: (_A3_COMBO, {**_A3_COMBO, A3_PULLER_COL: PULLER_OTHERS_TOTAL,
                                 51: COMBO_NEW, 52: COMBO_NEW}),
}

#: wf_describe 回读（改后）；测试与 notes 共用。wf_describe 不渲染触发块的 puller / 组，
#: 所以前两类改动在这里看不出来（由逐格指纹锁住）；能力1 两行已不再带「持有者为主位 且」。
DESCRIBE_AFTER = {
    f"leader_ability:{CID}#{LEADER_INDEX}": "光·编成≥6 时: 技能发动≥1 → 自身 技能槽 2.5%→5%",
    f"ability:{A1}#1": f"光·编成≥6 时: 自身 切换技能形态[{CAS_CHANGE_SKILL}]",
    f"ability:{A1}#2": f"光·编成≥6 时: 技能发动≥1 → 自身 发动技能动作[{CAS_PF}]",
    f"ability:{A3}#{A3_GAUGE_INDEX}": "光·编成≥6 时: 技能发动≥1 → 自身 技能槽 5%",
    f"ability:{A3}#{A3_COMBO_INDEX}": "光·编成≥6 时: 技能发动≥1 → 自身 追加连击 50",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise ValueError(f"unreviewed live baseline for {kind}:{key} "
                         f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _revise_rows(rows: list[list[str]], width: int, label: str,
                 targets: dict[int, tuple[dict[int, str], dict[int, str]]]) -> list[list[str]]:
    """``targets`` 指定行号的行必须逐格等于改前或改后指纹，改成改后；其余行原样。"""
    if any(len(row) != width for row in rows):
        raise ValueError(f"{label}: unexpected row width")
    out = deepcopy(rows)
    for index, (before, after) in targets.items():
        if index >= len(out):
            raise ValueError(f"{label}#{index}: row missing")
        row = out[index]
        if not (_matches(row, width, before) or _matches(row, width, after)):
            raise ValueError(f"{label}#{index}: row is not the reviewed shape")
        for col, value in after.items():
            row[col] = value
        if not _matches(row, width, after):          # 自检：只动了指纹里的格
            raise AssertionError(f"{label}#{index}: revised row left extra cells")
    for index, (old, new) in enumerate(zip(rows, out)):
        if index not in targets and old != new:
            raise AssertionError(f"{label}#{index}: untouched row changed")
    return out


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 #3：光共鸣技能发动回槽改为「除自身外的光属性角色」发动技能时（puller 7 → 6）。"""
    if len(rows) != 7:
        raise ValueError(f"leader_ability {CID}: expected 7 records, got {len(rows)}")
    out = _revise_rows(rows, LEADER_NCOLS, f"leader_ability:{CID}", {LEADER_INDEX: LEADER_CELLS})
    friends = [i for i, r in enumerate(out) if r[25] == "23" and r[45] == "211"]
    if friends != [LEADER_INDEX]:
        raise ValueError(f"leader_ability {CID}: skill-invoke gauge rows {friends}")
    return out


def ability1_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力1 #1 #2：前置1 202 → 0（去主位限制），前置2 光共鸣原位保留；整键 c1 = true。"""
    if len(rows) != 3:
        raise ValueError(f"ability {A1}: expected 3 records, got {len(rows)}")
    out = _revise_rows(rows, ABILITY_NCOLS, f"ability:{A1}", A1_CELLS)
    if {row[1] for row in out} != {"true"}:
        raise ValueError(f"ability {A1}: whole key must stay unisonable (c1=true)")
    gated = [i for i, row in enumerate(out)
             for col in PRECONDITION_KIND_COLS["ability"] if row[col] in ("202", "203")]
    if gated:
        raise ValueError(f"ability {A1}: main/unison slot preconditions remain on {gated}")
    return out


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力3 #4 #5：改为除自身外的光属性角色发动技能时（puller 7 → 6）；#5 连击 25 → 50。"""
    if len(rows) != 7:
        raise ValueError(f"ability {A3}: expected 7 records, got {len(rows)}")
    out = _revise_rows(rows, ABILITY_NCOLS, f"ability:{A3}", A3_CELLS)
    if {row[1] for row in out} != {"false"}:
        raise ValueError(f"ability {A3}: whole-key main-slot flag drifted")
    return out


def balance_rows(leader: list[list[str]], ability1: list[list[str]],
                 ability3: list[list[str]]) -> tuple[list[list[str]], list[list[str]], list[list[str]]]:
    """生成器链入口（``wf_zantetsu_fever_revision.apply_candidate`` 在 09-17 修订之后调用）。"""
    return leader_rows(leader), ability1_rows(ability1), ability3_rows(ability3)


# ---------------------------------------------------------------- 门禁

def row_problems(kind: str, rows: list[list[str]], strings: set[str]) -> list[str]:
    import wf_client_legality as L
    probs = []
    for i, row in enumerate(rows):
        for p in (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
                  + L.invoke_skill_string_problems(row, frozenset(strings), kind)
                  + L.ability_element_column_problems(kind, row, ELEMENT)):
            probs.append(f"{kind}#{i}: {p}")
    return probs


def capability_set(kind: str, rows: list[list[str]]) -> set[str]:
    import wf_client_legality as L
    return {cap for row in rows for cap in L.required_client_capabilities(kind, row)}


# ---------------------------------------------------------------- 批次入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader_in = _checked(read, "leader", CID)
    a1_in = _checked(read, "ability", A1)
    a3_in = _checked(read, "ability", A3)
    strings = {key for key in (CAS_CHANGE_SKILL, CAS_PF) if _checked(read, "cas", key)}
    leader, a1, a3 = balance_rows(leader_in, a1_in, a3_in)
    probs = (row_problems("leader_ability", leader, strings)
             + row_problems("ability", a1, strings) + row_problems("ability", a3, strings))
    if probs:
        raise ValueError(probs)
    new_caps = ((capability_set("leader_ability", leader) - capability_set("leader_ability", leader_in))
                | (capability_set("ability", a1 + a3) - capability_set("ability", a1_in + a3_in)))
    if new_caps - set(CAPABILITIES):
        raise ValueError(f"revised rows need undeclared client capabilities: {sorted(new_caps)}")
    return {
        "ability": {A1: a1, A3: a3},
        "leader": {CID: leader},
        "cas": {}, "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927_zantetsu.py",
            "request": "队长/能力3 技能发动回槽改为「除自身外的光属性角色」发动技能时，能力3 连击 +25→+50，"
                       "能力1 去掉主位限制（作者 2026-09-27）",
            "changes": {
                f"leader_ability:{CID}#{LEADER_INDEX} c{LEADER_PULLER_COL}": "7 → 6（除自身合计，组 White）",
                f"ability:{A1}#1/#2 c{A1_PRECONDITION1_COL}": "202 → 0（前置2 光共鸣原位保留，整键 c1=true）",
                f"ability:{A3}#{A3_GAUGE_INDEX}/#{A3_COMBO_INDEX} c{A3_PULLER_COL}": "7 → 6（除自身合计，组 White）",
                f"ability:{A3}#{A3_COMBO_INDEX} c51/c52": f"{COMBO_OLD} → {COMBO_NEW}（连击 25 → 50）",
            },
            "describe_after": DESCRIBE_AFTER,
            "panel": "队长/能力1/能力3 均无 desc_override，客户端按行自动生成；不新增覆盖文案",
            "generator": "wf_seasonal7_kit_zantetsu（kit 已钉冻结 donor 1499963#1（FROZEN_DONORS））→ wf_zantetsu_fever_revision.apply_candidate"
                         "（09-17 修订后调用 balance_rows，并回写 1599981）",
            "donor_pins": "丝缇涅尔/芙拉菲 kit 与妮可拉设计稿的 1599981#1 donor 已钉 c6=202",
            "needs_device": [
                "副位斩铁的 629：主位角色发动技能时由主位执行剑士 PF（官方零先例，live 有自制先例）",
                "副位斩铁的 536：打开主位角色技能 Flag1",
                "队长表 trig23 + puller 6 只有 live 先例（雷吉斯 139994#2，同批未实机）",
            ],
            "capabilities": [],
            "runtime_verified": False,
        },
    }

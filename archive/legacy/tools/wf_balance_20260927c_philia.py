# -*- coding: utf-8 -*-
"""菲莉亚·夏祭浴衣 159996 ``wind_oracle_yukata``（光）：2026-09-27 平衡第三轮（成长复核），纯函数。

口径：主会话 ``growth_c_spec.md``（作者原话：成长砍到 1/10 不合理 →「砍到 4/5，或者 7/10」→「可以砍到 2/3」、
「数值尽量取 5 的倍数」）+ ``reeval_full.json`` table.rows 菲莉亚四行 + 默认选择 D1–D4。
第二批（``wf_balance_20260927b_philia``，已发布）把队长成长砍到原值 1/10–1/5；本轮按触发难度回调到原值的
2/3 / 7/10 / 4/5（取整规则：≥20% 就近取 5 的倍数，2/3 档向上取且不低于 2/3）。

只改队长 ``leader_ability:159996`` 四行的 c49/c50（行号 0 起；其余格、其余 4 行逐字保留）：

- L#1 光共鸣·每次 PF → 光队攻击力：2500 → **20000**（原 25%；每次 PF 3 分钟约 60 次、易 ⇒ 2/3 = 16.7%，
  5 的倍数且不低于 2/3 只剩 20%；D1 取 20%，实际 4/5，不用 17.5%）；
- L#3 光共鸣·每次 PF → 自身 PF 伤害（含并入的「每 5 次 PF +50%」）：7000 → **40000**
  （原 50% + 并入折算 10%：50×2/3 + 10×7/10 = 40.3 ⇒ 40%，= 60% 的 2/3）；
- L#6 光共鸣·技能发动 → 光队攻击力：20000 → **80000**（原 100%；3 分钟 7–9 次、难 ⇒ 4/5）；
- L#7 光共鸣·每 5 次 PF → 自身攻击力：10000 → **35000**（原 50%；10–14 次、中 ⇒ 7/10）。

不动：能力 3 的封顶版（D4，保持第二批 10%×8）、技能 / PF 树（第二批 Down）、共鸣前置（D3，四行本来就带光共鸣）。
面板：菲莉亚没有 desc_override，队长面板由客户端按行自动生成 ⇒ 无文案改动；技能描述不含这些数值。

生成器：``wf_seasonal7_kit_philia.build`` 在 ``wf_balance_20260927b_philia.growth_rows`` 之后调
:func:`growth_rows` ⇒ kit 重跑产物 == :func:`revise`（测试断言）。
本模块只转换传入值，不读写 live / 候选 / assets。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_balance_20260927b_philia as B

CID = B.CID
CODE = B.CODE
PACKAGES = ["s7-philia"]
#: 候选 manifest 现值 1.0.12（第二批写入）→ 下一号。
PACKAGE_VERSION = {"s7-philia": "1.0.13"}
CAPABILITIES: list[str] = []
#: 候选 s7-philia 的 leader_ability:159996 与 live 逐字相同（2026-09-27 只读核对，链尾 1.4.1053）。
REVIEWED_DRIFT: dict = {}

ELEMENT = B.ELEMENT
LEADER_NCOLS = B.LEADER_NCOLS
LEADER_ROWS = B.LEADER_ROWS_AFTER               # 第二批之后 8 行

#: 第二批落值（= 本轮输入）的逐格指纹：行号 → 全部非空格。
B_AFTER = {1: B.LEADER_PF_ATTACK_AFTER, 3: B.LEADER_PF_DAMAGE_AFTER,
           6: B.MOVED_CAST_ATTACK, 7: B.MOVED_FIVE_PF_ATTACK}
#: 本轮新值（c49 = c50）。
C_VALUES = {1: "20000", 3: "40000", 6: "80000", 7: "35000"}
C_AFTER = {i: {**cells, 49: C_VALUES[i], 50: C_VALUES[i]} for i, cells in B_AFTER.items()}

#: 行 → (成长, 原值 %, 第二批 %, 档位, 本轮 %)，供测试与 notes 复核。
GROWTH = {
    1: ("光共鸣·每次PF → 光队攻击力", 25, 2.5, "2/3（D1 取 20%，实际 4/5）", 20),
    3: ("光共鸣·每次PF → 自身PF伤害（含并入每5次PF）", 60, 7, "2/3 自身部分 + 7/10 并入部分", 40),
    6: ("光共鸣·技能发动 → 光队攻击力", 100, 20, "4/5", 80),
    7: ("光共鸣·每5次PF → 自身攻击力", 50, 10, "7/10", 35),
}

#: live 输入基线（2026-09-27 本地链尾 1.4.1053 只读取数 = 第二批产物）。任一不符 ⇒ 拒绝（fail closed）。
BEFORE = {
    ("leader", CID): "474dfeb6e602118a609348eed937c05d339045f25fb3e7e6db2c28cacd27762e",
}

#: wf_describe 回读（改后）；测试与 notes 共用。
DESCRIBE_AFTER = {
    1: "光·编成≥6 时: 强化弹射≥1 → 赋予全队(光) 攻击力 20%",
    3: "光·编成≥6 时: 强化弹射≥1 → 自身 强化弹射伤害 40%",
    6: "光·编成≥6 时: 技能发动≥1 → 赋予全队(光) 攻击力 80%",
    7: "光·编成≥6 时: 强化弹射≥5 → 自身 攻击力 35%",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _row(cells: dict[int, str]) -> list[str]:
    row = [""] * LEADER_NCOLS
    for col, value in cells.items():
        row[col] = value
    return row


def growth_rows(leader: list[list[str]]) -> list[list[str]]:
    """队长四行 c49/c50 回调到原值 2/3–4/5；只接受第二批产物（或本轮产物，幂等），其余 4 行逐字保留。"""
    if len(leader) != LEADER_ROWS or any(len(r) != LEADER_NCOLS for r in leader):
        raise ValueError(f"leader_ability:{CID} is not the reviewed {LEADER_ROWS}-row batch-2 shape")
    out = deepcopy(leader)
    for index, cells in B_AFTER.items():
        if not (B._matches(out[index], LEADER_NCOLS, cells)
                or B._matches(out[index], LEADER_NCOLS, C_AFTER[index])):
            got = {c: v for c, v in enumerate(out[index]) if v != ""}
            raise ValueError(f"unreviewed leader#{index} preimage: {got}")
        out[index] = _row(C_AFTER[index])
    for index, (old, new) in enumerate(zip(leader, out)):
        if index not in B_AFTER and old != new:
            raise AssertionError(f"leader#{index}: untouched row changed")
    probs = B.row_problems("leader_ability", out)
    if probs:
        raise ValueError(f"growth rows fail the legality gates: {probs}")
    return out


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    live = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        if digest(value) != want:
            raise ValueError(f"live input drifted from the reviewed baseline: {kind}:{key}")
        live[kind, key] = deepcopy(value)
    leader = growth_rows(live["leader", CID])
    return {
        "ability": {},
        "leader": {CID: leader},
        "cas": {}, "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_philia.py",
            "request": "第三轮成长复核：1/10–1/5 → 2/3 / 7/10 / 4/5，数值尽量取 5 的倍数（D1 25% 行取 20%）",
            "changes": {f"leader_ability:{CID}#{i} c49/c50": f"{B_AFTER[i][49]} → {C_VALUES[i]}（{GROWTH[i][0]}："
                        f"原 {GROWTH[i][1]}% / 第二批 {GROWTH[i][2]}% / 本轮 {GROWTH[i][4]}%，{GROWTH[i][3]}）"
                        for i in sorted(C_VALUES)},
            "growth_3min": "L#1 60 次 1500%→1200%（第二批 150%）；L#3 60 次 3600%→2400%（第二批 420%）；"
                           "L#6 8 次 800%→640%（另加能力封顶 80%）；L#7 12 次 600%→420%（另加能力封顶 80%）",
            "kept": "能力 3 封顶版（D4）；技能 / PF 树；共鸣前置（D3）",
            "panel": "无 desc_override，队长面板客户端按行自动生成；技能描述无相关数值 ⇒ 不改文案",
            "describe_after": {f"leader_ability:{CID}#{i}": d for i, d in DESCRIBE_AFTER.items()},
            "generator": "wf_seasonal7_kit_philia.build：balance_b.growth_rows → 本模块 growth_rows",
            "runtime_verified": False,
        },
    }

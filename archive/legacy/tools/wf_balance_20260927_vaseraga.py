# -*- coding: utf-8 -*-
'巴萨拉卡 169997 ``vaseraga_dark``（暗）：2026-09-27 作者逐条确认的平衡修订（纯函数）。\n\n规格（行号从 1 起，全部行都带暗共鸣前置 kind2/600000/Black）：\n\n1. 去主位限制：能力 1、2、4、5 整键 c1 → "true"；能力 3 保持主位（整键 c1 统一 "false"，\n   含原先写成 "true" 的行 2-4）；能力 6 行 6 c1 → "true"（整键不限主位）。本角色没有 202/203 前置。\n2. 能力 1 行 3（技能发动 → 除自身全员代受 kind198 20 秒）移到能力 3 末尾（c0 → vaseraga_dark_3，c1=false）。\n3. 删除能力 2 行 1（技能发动 → 自身固有 1699979「超负荷」，与技能 DSL 重复）。\n4. 修能力 3 行 2-4：持续触发 c97 134 → 194。1699979 叠层上限 c4=1 ⇒ ``get_accumulatable()`` 为 false，\n   134（按层数）恒读 0 层、三行从未生效；194（ConditionCountUnique，按实例个数）持有即 1。\n   行形照官方 6 条自身来源（c98=0）during-194 行（1211771#1、1211775#0、1211776#0、1411412#0、1411414#0、\n   1411416#0）：c98=0、c100/c101=100000、c102=1、c108=false、c104=固有 ID。官方另有 3 条 1511823#0…1511825#0\n   是 c98=5、c110=7 的非自身来源形，不作本次先例。\n5. 能力加成 ×0.8（取最近的 5% 倍数）：见 :data:`SCALED`；技能槽类 / Guts / 无敌 / 代受 / 8 倍与 100 倍真伤 /\n   棺柩 -35 / 队长其余行不动。\n6. 能力 5 行 2：每次 +10%（c51/c52=10000），限 10 次（c34=10），CT 1.5 秒保留 ⇒ 最高 +100%。\n   官方先例：瞬发 144 + 388 全队 + c34=10：2510534#0 / 2510536#0 / 1510215#0，带 CT 的 1510333#2。\n7. 队长行 11/12：仍无上限（c32=(None)），c49/c50 50000 → 5000。\n8. 面板覆盖：新增 ``desc_override_vaseraga_dark`` 与 ``_1`` … ``_6``（custom_ability_string 新键），\n   文案由改后的行数据推导（数值不会与数据脱节），测试逐字对照作者确认稿。\n9. 技能描述规范化：action_skill 两档 c1、character_text c5/c7/c9、服务端 character_text [5]/[7]/[9]；\n   文案由两档技能 DSL 抽取的事实推导（DSL 本身不改）。持续伤害按「不符就按 DSL 改文案」写作「中毒」：\n   DSL 是 ACPoison，客户端 ui_string 状态名为「中毒效果」，没有「流血」状态（作者确认稿原写「流血」）。\n\n接口见 ``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``：:func:`revise` 只经 ``read`` 读 live，\n开头按 :data:`BEFORE` 摘要校验（漂移即抛 :class:`VaseragaBalanceError`，fail closed），不改 ``read`` 的返回对象。\n本角色没有可重跑的生成器：``work/character_packs/vaseraga_dark/build_workspace.py`` 是禁止重跑的历史 kit\n（会写盘并回退数据），本模块是这批行的唯一真源。不写 live store / assets / .cdn / 候选包，不发布，不 git。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as legality
import wf_describe

CID = "169997"
CODE = "vaseraga_dark"
PACKAGES = ["vaseraga_dark"]
#: 候选现值 0.1.1（``work/character_packs/vaseraga_dark/package/manifest.json``）→ 递增。
PACKAGE_VERSION = {"vaseraga_dark": "0.1.2"}
#: 七个 desc_override_* 覆盖行需要 V14 面板覆盖补丁（缺补丁不崩，只是面板仍走官方生成器）。
CAPABILITIES = ["panel-description-override-v2"]

DARK_ELEMENT = 5                 # master/character c3 内部 ElementKind：暗
DARK = "Black"
ABILITY = {slot: f"{CID}{slot}" for slot in range(1, 7)}
LEADER = CID
ABILITY_WIDTH, LEADER_WIDTH = 126, 124
MAIN_ONLY_SLOTS = frozenset({3})  # 作者 2026-09-27：只有能力 3 保留主位限制

UNIQUE_TABLE = "master/character/unique_condition.orderedmap"
OVERLOAD_ID = "1699979"          # 超负荷：960 帧，叠层上限 1
MARK_ID = "1699970"              # 古洛诺斯伤痕：永久，叠层上限 10
UNIQUE = {OVERLOAD_ID: (UNIQUE_TABLE, OVERLOAD_ID), MARK_ID: (UNIQUE_TABLE, MARK_ID)}

SKILL_NAME = "失落传说·古洛诺斯"
PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in ("1", "2")}
TEXT_DESC_COLUMNS = (5, 7, 9)    # character_text：c4/c6/c8 是技能名，c5/c7/c9 是对应描述
#: DSL 持续伤害状态 → 客户端状态名（ui_string ability_description_condition_target_poison =「中毒效果」）。
DOT_STATUS_NAME = {"ACPoison": "中毒"}

PANEL_LEADER = "desc_override_" + CODE
PANEL = {slot: f"{PANEL_LEADER}_{slot}" for slot in range(1, 7)}
PANEL_KEYS = (PANEL_LEADER, *PANEL.values())
MAIN_ICON = " <icon id='main'>  "   # 与 wf_featured_main_ability.MAIN 逐字一致
FORBIDDEN_PANEL_PHRASES = ("自身为队长时", "觉醒后", "生命值100%以下", "／", "/", "Ⓜ", "\\n")

#: ×0.8 取最近 5% 倍数：{(能力槽, live 行号 1 起): (旧值, 新值)}；持续行改 c113/c114，瞬发行改 c51/c52。
SCALE, STEP = 0.8, 5000
SCALED = {
    (1, 1): ("30000", "25000"), (1, 2): ("50000", "40000"),
    (2, 2): ("10000", "10000"), (2, 3): ("100000", "80000"),
    (2, 4): ("15000", "10000"), (2, 5): ("150000", "120000"),
    (2, 6): ("25000", "20000"), (2, 7): ("250000", "200000"),
    (3, 2): ("200000", "160000"), (3, 3): ("150000", "120000"), (3, 4): ("15000", "10000"),
    (6, 3): ("50000", "40000"), (6, 4): ("50000", "40000"), (6, 5): ("20000", "15000"),
}
ABILITY5_STEP, ABILITY5_LIMIT = "10000", "10"
LEADER_GROWTH_OLD, LEADER_GROWTH_NEW = "50000", "5000"

#: 官方 during-194（ConditionCountUnique）自身来源行形：官方 ability 里 c98=0 的 6 条全部如此
#: （另 3 条 1511823#0…1511825#0 为 c98=5、c110=7，c100/c101/c102/c108 同值）。
OFFICIAL_194_SELF = {98: "0", 100: "100000", 101: "100000", 102: "1", 108: "false"}
OFFICIAL_194_SELF_PRECEDENTS = ("1211771#1", "1211775#0", "1211776#0", "1411412#0", "1411414#0", "1411416#0")
OFFICIAL_194_OTHER_ROWS = ("1511823#0", "1511824#0", "1511825#0")

# ------------------------------------------------------------------ 输入基线

#: ``{(kind, key): sha256}``：revise() 读取的每一项在 live 上的摘要（2026-09-27 只读导出）。
BEFORE: dict[tuple[str, Any], str] = {
    ("ability", ABILITY[1]): "6e541f3b9067fcd65d23d8d9d585355f6f0e22fcdab4d27b6aac5d53f5e12e9c",
    ("ability", ABILITY[2]): "3c9ed2f284fedcfae96a4febb558813d1933fabd7257fa74183a273017056abc",
    ("ability", ABILITY[3]): "728f04df8589ee424d77440262183babd4ff14afa3a75ea545da8ccda623f580",
    ("ability", ABILITY[4]): "8b23a1f7fe588447b54f8d370b175bb6e92be618110c49f1b366c7c8c2b82c6c",
    ("ability", ABILITY[5]): "6e7f71d937c189d7d0535b6aa1755f45da5f0a01416de171c32659b0878424ac",
    ("ability", ABILITY[6]): "145de9e3a291a5560995375869423133887b40e2f17753b9ecab6be10f2fbce6",
    ("leader", LEADER): "390a3e5a7916a88dd6dfe5d805aba86040b21f09b963e7f57faf9fc9cd589be9",
    ("text", CID): "53cb1fb5153f30f588e70c8fd3306707926683e30b1cbd05714db8e15713fdf9",
    ("action", CODE): "3213ee6959c286195f07f1fd51b59939ab9f1da4c9ea14682601e9dad52493be",
    ("server_text", CID): "53cb1fb5153f30f588e70c8fd3306707926683e30b1cbd05714db8e15713fdf9",
    # 两档技能 DSL 只读（不改），用于从 DSL 推导技能描述；两档逐字相同。
    ("dsl", PROGRAMS["1"]): "15c2ebaef6b1e373c535ef7d88151a728f44bc14de0aca12db08e9f39c21003d",
    ("dsl", PROGRAMS["2"]): "15c2ebaef6b1e373c535ef7d88151a728f44bc14de0aca12db08e9f39c21003d",
    # 固有状态只读：名字 / 时长 / 叠层上限（证明 134 失效、给面板与描述取名与秒数）。
    ("table", UNIQUE[OVERLOAD_ID]): "da9a4d550171bd84db30a8d80fc7d991a9355215febbaf9589175b88a306d15f",
    ("table", UNIQUE[MARK_ID]): "8234f23b8142ea1bbaa29a118a4a34c4ab75d538fba4e74492f49c33a8024440",
}


class VaseragaBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VaseragaBalanceError(f"{CID} balance 20260927: {message}")


def _expect(row: list[str], cells: dict[int, str], what: str) -> None:
    got = {col: row[col] for col in cells}
    _require(got == cells, f"unexpected preimage for {what}: {got} != {cells}")


def _absent(read: Callable, kind: str, key: str) -> bool:
    try:
        return read(kind, key) is None
    except KeyError:
        return True


def _baseline(read: Callable) -> dict:
    """读取并锁定全部输入；任何一项漂移都拒绝。新面板键必须仍不存在于 live。"""
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        got = digest(value)
        if got != want:
            raise VaseragaBalanceError(f"live drift: {kind}:{key} sha256 {got} != reviewed {want}")
        inputs[kind, key] = deepcopy(value)
    for key in PANEL_KEYS:
        if not _absent(read, "cas", key):
            raise VaseragaBalanceError(f"live drift: cas:{key} already exists (panel keys must be new)")
    for slot, key in ABILITY.items():
        rows = inputs["ability", key]
        _require(all(len(r) == ABILITY_WIDTH and r[0] == f"{CODE}_{slot}" for r in rows),
                 f"ability {key}: expected {ABILITY_WIDTH}-column rows with c0={CODE}_{slot}")
        # 所有行都带暗共鸣门：前置 1 = kind 2（Member）≥ 6 人 Black（能力 3 行 1 在前置 2）。
        for index, row in enumerate(rows, 1):
            gate = (row[6], row[9], row[10], row[11]) if row[6] == "2" else (row[13], row[16], row[17], row[18])
            _require(gate == ("2", "600000", "600000", DARK), f"ability {key}#{index}: dark resonance gate")
    _require(all(len(r) == LEADER_WIDTH and r[0] == CODE and (r[4], r[7], r[8], r[9])
                 == ("2", "600000", "600000", DARK) for r in inputs["leader", LEADER]),
             "leader rows must be 124-column dark-resonance rows")
    return inputs


# ------------------------------------------------------------------ 数值工具

def _rounded(old: str) -> str:
    """×0.8 后取最近的 5% 倍数（×100000 口径的 5000）。"""
    return str(round(int(old) * SCALE / STEP) * STEP)


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def pct(value: str) -> str:
    """×100000 口径 → 百分数（25000 → "25"）。"""
    return _num(int(value) / 1000)


def times(value: str) -> str:
    """×100000 口径 → 倍数 / 计数（800000 → "8"，3500000 → "35"）。"""
    return _num(int(value) / 100000)


def seconds(frames: int | str) -> str:
    return _num(int(frames) / 60)


def frames_x100k(value: str) -> int:
    """帧 ×100000 的持续/阈值列 → 帧。"""
    n = int(value)
    _require(n % 100000 == 0, f"frame value {value} is not a multiple of 100000")
    return n // 100000


def cooltime_frames(value: str) -> int:
    """CT 列：< 100000 是原始帧，≥ 100000 时 ÷100000。"""
    n = int(value)
    return n // 100000 if n >= 100000 else n


def _mode_col(table: str) -> int:
    return int(wf_describe.layout(table)["blocks"]["precondition1"]) - 1


def _strength_cols(row: list[str]) -> tuple[int, int]:
    """能力行的强度两列：持续行 c113/c114，瞬发行 c51/c52。"""
    return (113, 114) if row[5] == "1" else (51, 52)


# ------------------------------------------------------------------ 词条行

def ability_rows(inputs: dict) -> tuple[dict[str, list[list[str]]], dict]:
    rows = {slot: deepcopy(inputs["ability", key]) for slot, key in ABILITY.items()}
    _require([len(rows[s]) for s in range(1, 7)] == [3, 7, 7, 2, 2, 6], "ability row counts drift")

    # 5. ×0.8：先按 live 行号改值（逐格核对旧值），再做行的搬移与删除。
    for (slot, number), (old, new) in SCALED.items():
        _require(new == _rounded(old), f"ability{slot}#{number}: {old}×0.8 → {new} is not the nearest 5% step")
        row = rows[slot][number - 1]
        low, high = _strength_cols(row)
        _expect(row, {low: old, high: old}, f"ability{slot}#{number} strength")
        row[low] = row[high] = new

    # 2. 能力1 行3（代受 198）→ 能力3 末尾。
    scapegoat = rows[1][2]
    _expect(scapegoat, {5: "0", 27: "23", 28: "0", 30: "100000", 31: "100000", 35: "0",
                        47: "198", 48: "1", 57: "120000000", 58: "120000000"}, "ability1#3 scapegoat")
    rows[1] = rows[1][:2]
    _expect(rows[1][0], {5: "1", 97: "110", 98: "9", 100: "10000", 102: "10", 109: "0", 110: "0"},
            "ability1#1 party HP decrease → attack")
    _expect(rows[1][1], {5: "1", 97: "110", 98: "9", 100: "10000", 102: "10", 109: "154", 110: "0"},
            "ability1#2 party HP decrease → ability damage")
    moved = list(scapegoat)
    moved[0], moved[1] = f"{CODE}_3", "false"

    # 3. 删除能力2 行1（技能发动 → 获得超负荷，与技能 DSL 重复）。
    _expect(rows[2][0], {5: "0", 27: "23", 47: "461", 48: "0", 68: OVERLOAD_ID}, "ability2#1 overload grant")
    rows[2] = rows[2][1:]

    # 4. 能力3 行2-4：134 → 194（照官方 194 行形），整键 c1 统一 false；代受行追加为第 8 行。
    for index in (1, 2, 3):
        row = rows[3][index]
        _expect(row, {5: "1", 85: "(None)", 97: "134", 104: OVERLOAD_ID, **OFFICIAL_194_SELF, 110: "0"},
                f"ability3#{index + 1} overload during row")
        row[97] = "194"
    rows[3].append(moved)

    # 6. 能力5 行2：每次 +10%，限 10 次，CT 1.5 秒保留。
    boost = rows[5][1]
    _expect(boost, {5: "0", 27: "144", 28: "0", 30: "100000", 31: "100000", 34: "(None)", 35: "90",
                    47: "388", 48: "5", 49: DARK, 51: "25000", 52: "25000"}, "ability5#2 party ability damage")
    boost[51] = boost[52] = ABILITY5_STEP
    boost[34] = ABILITY5_LIMIT

    # 1. 主位限制分布：能力 3 整键 false，其余整键 true。
    for slot, slot_rows in rows.items():
        for row in slot_rows:
            row[1] = "false" if slot in MAIN_ONLY_SLOTS else "true"

    _require([len(rows[s]) for s in range(1, 7)] == [2, 6, 8, 2, 2, 6], "revised ability row counts")
    evidence = {"moved_scapegoat": {"from": f"{ABILITY[1]}#3", "to": f"{ABILITY[3]}#8"},
                "deleted": f"{ABILITY[2]}#1 (461 {OVERLOAD_ID})",
                "during_194_rows": [f"{ABILITY[3]}#{n}" for n in (2, 3, 4)]}
    return {ABILITY[slot]: rows[slot] for slot in range(1, 7)}, evidence


def leader_rows(inputs: dict) -> list[list[str]]:
    rows = deepcopy(inputs["leader", LEADER])
    _require(len(rows) == 13, "leader must have 13 rows")
    for index, content in ((10, "32"), (11, "388")):
        _expect(rows[index], {3: "0", 25: "144", 26: "0", 28: "100000", 29: "100000", 32: "(None)",
                              33: "0", 45: content, 46: "0", 49: LEADER_GROWTH_OLD, 50: LEADER_GROWTH_OLD},
                f"leader#{index + 1} per-ability-damage growth")
        rows[index][49] = rows[index][50] = LEADER_GROWTH_NEW
    return rows


# ------------------------------------------------------------------ 技能 DSL 事实

def _cmd(node) -> list | None:
    if (isinstance(node, list) and len(node) == 2 and node[0] == "Command" and isinstance(node[1], list)
            and node[1] and isinstance(node[1][0], str)):
        return node[1]
    return None


def _block(node) -> list:
    _require(isinstance(node, list) and len(node) == 2 and node[0] == "Block" and isinstance(node[1], list),
             f"expected a Block, got {node!r:.120}")
    return node[1]


def _wait(node) -> tuple[int, list] | None:
    if (isinstance(node, list) and len(node) == 2 and node[0] == "Event" and isinstance(node[1], list)
            and node[1][:1] == ["Wait"]):
        return node[1][1], _block(node[1][3])
    return None


def _slv(value) -> float:
    _require(isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict)
             and value[0].get("min") == value[0].get("max"), f"expected a flat SLv value, got {value!r:.80}")
    return value[0]["min"]


def _conditions(commands: list) -> list[tuple[int, str, list]]:
    """CreateCondition → [(主体, AC 名, AC 参数)]。"""
    out = []
    for args in commands:
        if args and args[0] == "CreateCondition":
            for ac in args[2]:
                out.append((args[1], ac[0], ac[1:]))
    return out


def _hit_area(args: list) -> dict:
    """CreateHitArea → 锚点 / 形状 / 寿命 / 次数 / 命中绑定号 / 命中块内命令。"""
    _require(args[13][0] == "SpecifyHitAreaLifetimeDirectly" and args[14][0] == "CalculatedUsingMaxNumOfHits",
             "hit area lifetime / hit count shape")
    on_hit = [_cmd(node) for node in _block(args[23])]
    attacks = [a for a in on_hit if a and a[0] == "CreateNormalAttack"]
    _require(len(attacks) == 1 and attacks[0][1] == args[22], "hit area must carry one bound attack")
    return {"anchor": args[2], "shape": args[9], "lifetime": args[13][1], "hits": args[14][1],
            "bind": args[22], "element": attacks[0][2], "multiplier": _slv(attacks[0][6]),
            "conditions": _conditions([a for a in on_hit if a])}


def skill_facts(tree) -> dict:
    """两档技能 DSL → 描述用的事实；结构不符直接拒绝（描述不会脱离 DSL）。"""
    _require(isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl", "skill root")
    top = _block(tree[11])
    _require([(_cmd(n) or ["Event"])[0] for n in top]
             == ["StopBall", "ShakeCamera", "Event", "Event", "CreateCondition", "CreateCondition",
                 "CreateCondition"], "skill top-level command order")
    (swing_wait, swing_body), (moon_wait, moon_body) = _wait(top[2]), _wait(top[3])

    swing_areas = [_hit_area(a) for a in map(_cmd, swing_body) if a and a[0] == "CreateHitArea"]
    _require(len(swing_areas) == 1, "scythe swing must be one hit area")
    swing = swing_areas[0]
    _require(swing["anchor"] == -18 and swing["shape"][0] == "Sector" and swing["hits"] == 1
             and swing["element"] == 255 and not swing["conditions"], "scythe swing shape")

    moon = [_hit_area(a) for a in map(_cmd, moon_body) if a and a[0] == "CreateHitArea"]
    _require(len(moon) == 2, "blood moon must be two hit areas")
    near = next(a for a in moon if a["anchor"] == -18)
    field = next(a for a in moon if a["anchor"] == -1)
    _require(near["shape"][0] == "Circle" and field["shape"][0] == "Rectangle"
             and [_slv(v) for v in field["shape"][1:]] == [1500, 2000], "blood moon areas: self circle + full field")
    for area in (near, field):
        _require(area["element"] == 255 and area["lifetime"] == 960 and area["hits"] == 16
                 and area["lifetime"] // area["hits"] == 60, "blood moon ticks once per second for 16 seconds")
    _require(near["conditions"] == [(near["bind"], "ACUnique", [int(MARK_ID), [{"min": 1, "max": 1}]])],
             "self circle only marks the hit enemy")

    marks = {subject for subject, name, params in field["conditions"]
             if name == "ACUnique" and params[0] == int(MARK_ID)}
    _require(marks == {field["bind"], -17}, "full field marks the hit enemy and self")
    debuffs = {name: params for subject, name, params in field["conditions"]
               if subject == field["bind"] and name != "ACUnique" and name != "ACToleranceOfElement"}
    tolerances = {params[1]: _slv(params[2]) for subject, name, params in field["conditions"]
                  if subject == field["bind"] and name == "ACToleranceOfElement"}
    _require(set(debuffs) == {"ACPoison"} and _slv(debuffs["ACPoison"][0]) == 960,
             "full field applies the 16-second poison (ACPoison)")
    _require(set(tolerances) == {254, DARK_ELEMENT + 1}, "resistance down: all elements + dark (DSL element +1)")
    _require(all(_slv(p[0]) == 960 for s, n, p in field["conditions"] if n == "ACToleranceOfElement"),
             "resistance down lasts 16 seconds")

    own = _conditions([_cmd(n) for n in top[4:]])
    _require([(s, n) for s, n, _p in own] == [(-17, "ACUnique"), (-17, "ACAbilityDamage"), (-17, "ACInvincible")],
             "self conditions: overload, ability damage, invincible")
    _require(own[0][2] == [int(OVERLOAD_ID), [{"min": 1, "max": 1}]], "self overload grant")
    return {
        "swing": {"wait": swing_wait, "multiplier": swing["multiplier"]},
        "moon": {"wait": moon_wait, "lifetime": field["lifetime"], "field_multiplier": field["multiplier"],
                 "near_multiplier": near["multiplier"], "dot": next(iter(debuffs)), "all_resist": tolerances[254],
                 "dark_resist": tolerances[DARK_ELEMENT + 1]},
        "self": {"ability_damage": _slv(own[1][2][1]), "ability_damage_frames": _slv(own[1][2][0]),
                 "invincible_frames": _slv(own[2][2][0])},
    }


def skill_description(facts: dict, uniques: dict[str, list[str]]) -> str:
    swing, moon, own = facts["swing"], facts["moon"], facts["self"]
    overload, mark = uniques[OVERLOAD_ID], uniques[MARK_ID]
    return (f"向前方大范围挥动巨镰，造成{_num(swing['multiplier'])}倍暗属性伤害／"
            f"{seconds(moon['wait'])}秒后降下「血月」（{seconds(moon['lifetime'])}秒）："
            f"每秒对全场敌人造成{_num(moon['field_multiplier'])}倍暗属性伤害"
            f"（自身附近的敌人额外受到{_num(moon['near_multiplier'])}倍），"
            f"并赋予{DOT_STATUS_NAME[moon['dot']]}、全属性抗性降低{_num(round(-moon['all_resist'] * 100, 6))}%、"
            f"暗属性抗性降低{_num(round(-moon['dark_resist'] * 100, 6))}%效果／"
            f"血月命中的敌人与自身获得「{mark[1]}」／"
            f"自身获得「{overload[1]}」（{seconds(overload[3])}秒）、"
            f"能力伤害提升{_num(round(own['ability_damage'] * 100, 6))}%"
            f"（{seconds(own['ability_damage_frames'])}秒）与无敌效果（{seconds(own['invincible_frames'])}秒）")


# ------------------------------------------------------------------ 面板覆盖（由改后数据推导）

def _unique_rows(inputs: dict) -> dict[str, list[str]]:
    out = {}
    for uid, item in UNIQUE.items():
        rows = inputs["table", item]
        _require(len(rows) == 1 and len(rows[0]) == 15, f"unique_condition {uid}: one 15-column row")
        out[uid] = rows[0]
    _require(out[OVERLOAD_ID][1] == "超负荷" and out[OVERLOAD_ID][3] == "960" and out[OVERLOAD_ID][4] == "1",
             "overload: 960 frames, cap 1")
    _require(out[MARK_ID][1] == "古洛诺斯伤痕" and out[MARK_ID][4] == "10", "Chronos mark: cap 10")
    return out


def leader_panel(rows: list[list[str]]) -> str:
    atk, dmg, gauge, low_dmg, sp, burst, cost, charge, buff, resist, g_atk, g_dmg, coffin = rows
    _expect(atk, {45: "32", 46: "5", 47: DARK}, "leader#1")
    _expect(dmg, {45: "388", 46: "5", 47: DARK}, "leader#2")
    _expect(coffin, {45: "466", 46: "5", 47: DARK}, "leader#13")
    _expect(gauge, {3: "1", 95: "1", 96: "0", 107: "3", 108: "5", 109: DARK}, "leader#3")
    _expect(low_dmg, {3: "1", 95: "1", 96: "0", 98: gauge[98], 107: "154", 108: "5", 109: DARK}, "leader#4")
    _expect(sp, {25: "25", 26: "0", 45: "211", 46: "1", 47: DARK}, "leader#5")
    _expect(burst, {25: "25", 26: "0", 28: sp[28], 45: "0", 46: "5", 47: DARK}, "leader#6")
    for row, content in ((cost, "209"), (charge, "211"), (buff, "0"), (resist, "2")):
        _expect(row, {25: "23", 26: "0", 28: "100000", 45: content, 46: "0"}, f"leader skill row {content}")
    _require(buff[55] == resist[55], "leader skill buffs share one duration")
    for row, content in ((g_atk, "32"), (g_dmg, "388")):
        _expect(row, {25: "144", 26: "0", 28: "100000", 32: "(None)", 45: content, 46: "0"}, "leader growth")
    return "\n".join([
        f"暗属性共鸣时，暗属性角色攻击力＋{pct(atk[49])}%、能力伤害＋{pct(dmg[49])}%，"
        "且暗属性角色即使成为棺柩，个体特殊效果也不会消失",
        f"暗属性共鸣时，自身生命值{pct(gauge[98])}%以下时，暗属性角色技能充能速度＋{pct(gauge[111])}%、"
        f"能力伤害＋{pct(low_dmg[111])}%",
        f"暗属性共鸣时，自身生命值低于{pct(sp[28])}%时，除自身外的暗属性角色技能槽＋{pct(sp[49])}%"
        f"（CT：{seconds(cooltime_frames(sp[33]))}秒），暗属性角色攻击力＋{pct(burst[49])}%"
        f"（持续{seconds(frames_x100k(burst[55]))}秒，CT：{seconds(cooltime_frames(burst[33]))}秒）",
        f"暗属性共鸣时，自身发动技能时，受到最大生命值{pct(cost[49])}%的伤害，技能槽＋{pct(charge[49])}%，"
        f"并获得攻击力＋{pct(buff[49])}%、全属性抗性＋{pct(resist[49])}%（持续{seconds(frames_x100k(buff[55]))}秒）",
        f"暗属性共鸣时，自身每造成1次能力伤害，攻击力＋{pct(g_atk[49])}%、能力伤害＋{pct(g_dmg[49])}%",
    ])


def ability_panels(ability: dict[str, list[list[str]]], uniques: dict[str, list[str]]) -> dict[int, list[str]]:
    """每个能力槽的面板行（未加主位图标）。"""
    overload, mark = uniques[OVERLOAD_ID][1], uniques[MARK_ID][1]
    a1, a2, a3, a4, a5, a6 = (ability[ABILITY[s]] for s in range(1, 7))

    atk, dmg = a1
    _require(atk[100] == dmg[100] and atk[102] == dmg[102], "ability1 rows share one trigger")
    panels = {1: [f"暗属性共鸣时，队伍全员的总生命值每下降{pct(atk[100])}%，自身攻击力＋{pct(atk[113])}%、"
                  f"能力伤害＋{pct(dmg[113])}%（最多{atk[102]}层）"]}

    lines = []
    for index in range(0, 6, 2):
        resist, damage = a2[index], a2[index + 1]
        _expect(resist, {5: "1", 97: "1", 98: "0", 109: "4", 110: "0"}, f"ability2 resist row {index + 1}")
        _expect(damage, {5: "1", 97: "1", 98: "0", 100: resist[100], 109: "154", 110: "0"},
                f"ability2 damage row {index + 2}")
        more = "" if index == 0 else "再"
        lines.append(f"暗属性共鸣时，自身生命值{pct(resist[100])}%以下时，自身全属性抗性{more}＋{pct(resist[113])}%、"
                     f"能力伤害{more}＋{pct(damage[113])}%")
    panels[2] = lines

    pulse, p_dmg, p_atk, p_res, guts_open, guts_skill, coffin, scapegoat = a3
    _expect(pulse, {6: "187", 7: "0", 12: OVERLOAD_ID, 27: "77", 47: "256"}, "ability3#1 overload pulse")
    for row, content in ((p_dmg, "154"), (p_atk, "0"), (p_res, "4")):
        _expect(row, {97: "194", 104: OVERLOAD_ID, 109: content, 110: "0"}, f"ability3 overload {content}")
    for row, trigger in ((guts_open, "0"), (guts_skill, "23")):
        _expect(row, {27: trigger, 47: "468", 48: "0", 67: "1"}, f"ability3 guts ({trigger})")
    _require(guts_open[59] == guts_skill[59], "ability3 guts rows grant the same count")
    _expect(coffin, {47: "203", 48: "5", 49: DARK}, "ability3 coffin count")
    _expect(scapegoat, {27: "23", 47: "198", 48: "1"}, "ability3#8 scapegoat")
    panels[3] = [
        f"暗属性共鸣时，「{overload}」期间，自身能力伤害＋{pct(p_dmg[113])}%、攻击力＋{pct(p_atk[113])}%、"
        f"全属性抗性＋{pct(p_res[113])}%，并每经过{seconds(frames_x100k(pulse[30]))}秒对全体敌人造成"
        f"{times(pulse[51])}倍暗属性能力伤害",
        f"暗属性共鸣时，自身发动技能时，自身代替其他队员承受伤害（持续{seconds(frames_x100k(scapegoat[57]))}秒）",
        f"暗属性共鸣时，战斗开始时及自身发动技能时，获得{times(guts_open[59])}次不死效果（无法消除）",
        f"暗属性共鸣时，暗属性角色的棺柩计数－{times(coffin[51])}",
    ]

    gauge, second = a4
    _expect(gauge, {27: "0", 47: "211", 48: "0"}, "ability4#1")
    _expect(second, {27: "0", 47: "245", 48: "0"}, "ability4#2")
    panels[4] = [f"暗属性共鸣时，战斗开始时，自身技能槽＋{pct(gauge[51])}%、技能槽最大值＋{pct(second[51])}%"]

    charge, boost = a5
    _expect(charge, {27: "144", 28: "0", 30: "100000", 47: "211", 48: "0"}, "ability5#1")
    _expect(boost, {27: "144", 28: "0", 30: "100000", 47: "388", 48: "5", 49: DARK}, "ability5#2")
    panels[5] = [f"暗属性共鸣时，自身造成能力伤害时，自身技能槽＋{pct(charge[51])}%"
                 f"（CT：{seconds(cooltime_frames(charge[35]))}秒），暗属性角色能力伤害＋{pct(boost[51])}%"
                 f"（CT：{seconds(cooltime_frames(boost[35]))}秒，最多{boost[34]}次）"]

    low_inv, guts_inv, guts_adv, low_adv, scar, guts_hit = a6
    for row, trigger, content in ((low_inv, "25", "16"), (low_adv, "25", "470"),
                                  (guts_inv, "189", "16"), (guts_adv, "189", "470"), (guts_hit, "189", "256")):
        _expect(row, {27: trigger, 28: "0", 47: content, 48: "0"}, f"ability6 {trigger}->{content}")
    _require(low_inv[30] == low_adv[30] and low_inv[34] == low_adv[34], "ability6 HP-low rows share one trigger")
    _require(low_adv[51] == guts_adv[51] and len({r[57] for r in (low_inv, guts_inv, guts_adv, low_adv)}) == 1,
             "ability6 invincible/adversity share strength and duration")
    _expect(scar, {5: "1", 97: "194", 104: MARK_ID, 109: "412", 110: "0"}, "ability6#5 Chronos mark")
    duration = seconds(frames_x100k(low_inv[57]))
    panels[6] = [
        f"暗属性共鸣时，自身生命值低于{pct(low_inv[30])}%时（限{low_inv[34]}次），"
        f"获得无敌效果与逆境效果［最大＋{pct(low_adv[51])}%］（持续{duration}秒）",
        f"暗属性共鸣时，自身因不死效果以生命值1抵抗住攻击时，获得无敌效果与逆境效果［最大＋{pct(guts_adv[51])}%］"
        f"（持续{duration}秒），并对全体敌人造成{times(guts_hit[51])}倍暗属性能力伤害",
        f"暗属性共鸣时，持有「{mark}」时，自身对敌人造成的能力伤害＋{pct(scar[113])}%（独立乘区）",
    ]
    return panels


def panel_rows(ability: dict[str, list[list[str]]], leader: list[list[str]],
               uniques: dict[str, list[str]]) -> dict[str, list[list[str]]]:
    out = {PANEL_LEADER: [[leader_panel(leader)]]}
    for slot, lines in ability_panels(ability, uniques).items():
        main = {row[1] for row in ability[ABILITY[slot]]} == {"false"}
        out[PANEL[slot]] = [["\n".join(MAIN_ICON + line if main else line for line in lines)]]
    return out


# ------------------------------------------------------------------ 门禁

def row_problems(table: str, row: list[str], strings) -> list[str]:
    return ([f"legality: {p}" for p in legality.client_legality_problems(table, row)]
            + [f"declared: {p}" for p in legality.declared_block_field_problems(table, row)]
            + [f"element: {p}" for p in legality.ability_element_column_problems(table, row, DARK_ELEMENT)]
            + [f"invoke: {p}" for p in legality.invoke_skill_string_problems(row, strings, table)])


def accumulation_problems(ability: dict[str, list[list[str]]], uniques: dict[str, list[str]]) -> list[str]:
    """被 during-134 按层数计数的固有，叠层上限必须 > 1（否则层数恒 0、词条静默失效）。"""
    problems = []
    for key, rows in ability.items():
        for index, row in enumerate(rows, 1):
            if row[5] == "1" and row[97] == "134" and row[104] in uniques:
                cap = uniques[row[104]][4]
                if not (cap.isdigit() and int(cap) > 1):
                    problems.append(f"ability {key}#{index}: during-134 counts stacks of {row[104]} "
                                    f"but its cap c4={cap!r} ⇒ always 0 stacks")
    return problems


def panel_problems(key: str, text: str, main_only: bool) -> list[str]:
    problems = [f"{key}: forbidden phrase {p!r}" for p in FORBIDDEN_PANEL_PHRASES if p in text]
    lines = text.split("\n")
    icons = [line.startswith(MAIN_ICON) for line in lines]
    if main_only and not all(icons):
        problems.append(f"{key}: every main-only line must start with the main icon")
    if not main_only and "<icon id='main'>" in text:
        problems.append(f"{key}: unrestricted panel must not carry the main icon")
    if any(not line.strip() for line in lines):
        problems.append(f"{key}: empty panel line")
    if any(not line.replace(MAIN_ICON, "").startswith("暗属性共鸣时，") for line in lines):
        problems.append(f"{key}: every line must start with the dark resonance clause")
    return problems


def validate(result: dict, uniques: dict[str, list[str]]) -> list[str]:
    problems = []
    strings = set(result["cas"])
    for key, rows in result["ability"].items():
        slot = int(key[-1])
        if {row[1] for row in rows} != ({"false"} if slot in MAIN_ONLY_SLOTS else {"true"}):
            problems.append(f"ability {key}: c1 distribution {[row[1] for row in rows]}")
        for index, row in enumerate(rows, 1):
            if len(row) != ABILITY_WIDTH or row[0] != f"{CODE}_{slot}":
                problems.append(f"ability {key}#{index}: shape / string_id")
            problems += [f"ability {key}#{index} {p}" for p in row_problems("ability", row, strings)]
            if row[_mode_col("ability")] == "1" and row[97] == "194":
                # 限次列只要求正整数：能力6 行5（伤痕，live 既有 c102=10）不在本次修复范围；
                # 194 数实例个数（持有即 1），限次 ≥1 时效果相同。本次修的三行在 ability_rows 里钉死 c102=1。
                shape = {col: v for col, v in OFFICIAL_194_SELF.items() if col != 102}
                got = {col: row[col] for col in shape}
                if (got != shape or not row[102].isdigit() or int(row[102]) < 1
                        or row[85] != "(None)" or row[104] not in uniques):
                    problems.append(f"ability {key}#{index}: during-194 row off the official shape "
                                    f"{got} c102={row[102]!r} c104={row[104]!r}")
    for index, row in enumerate(result["leader"].get(LEADER, []), 1):
        problems += [f"leader {LEADER}#{index} {p}" for p in row_problems("leader_ability", row, strings)]
    problems += accumulation_problems(result["ability"], uniques)
    for key, rows in result["cas"].items():
        if not (len(rows) == 1 and len(rows[0]) == 1 and isinstance(rows[0][0], str)):
            problems.append(f"{key}: expected one text cell")
            continue
        slot = key[len(PANEL_LEADER) + 1:]
        main_only = slot.isdigit() and int(slot) in MAIN_ONLY_SLOTS
        problems += panel_problems(key, rows[0][0], main_only)
    needed = set()
    for table, group in (("ability", result["ability"]), ("leader_ability", result["leader"])):
        for rows in group.values():
            for row in rows:
                needed |= set(legality.required_client_capabilities(table, row))
    for key in result["cas"]:
        needed |= set(legality.required_client_capabilities(legality.CUSTOM_ABILITY_STRING_KIND, [key]))
    if needed != set(CAPABILITIES):
        problems.append(f"capabilities {sorted(needed)} != declared {CAPABILITIES}")
    return problems


# ------------------------------------------------------------------ 入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    uniques = _unique_rows(inputs)
    ability, moves = ability_rows(inputs)
    leader = leader_rows(inputs)

    facts = {level: skill_facts(inputs["dsl", program]) for level, program in PROGRAMS.items()}
    _require(facts["1"] == facts["2"], "both skill levels must carry the same DSL facts")
    description = skill_description(facts["1"], uniques)

    action = inputs["action", CODE]
    _require([inner for inner, _fields in action] == ["1", "2"], "action_skill inner keys")
    new_action = []
    for inner, fields in action:
        fields = list(fields)
        _require(fields[0] == SKILL_NAME and fields[7] == PROGRAMS[inner], f"action_skill {inner} name/program")
        fields[1] = description
        new_action.append((inner, fields))

    texts = {}
    for kind in ("text", "server_text"):
        rows = inputs[kind, CID]
        _require(len(rows) == 1 and len(rows[0]) == 12, f"{kind} {CID}: one 12-column row")
        for col in TEXT_DESC_COLUMNS:
            _require(rows[0][col - 1] == SKILL_NAME, f"{kind} c{col - 1} must be the skill name")
            rows[0][col] = description
        texts[kind] = rows

    result = {
        "ability": ability,
        "leader": {LEADER: leader},
        "cas": panel_rows(ability, leader, uniques),
        "text": {CID: texts["text"]},
        "table": {},
        "action": {CODE: new_action},
        "dsl": {},
        "server_text": {CID: texts["server_text"]},
        "new_programs": [],
    }
    problems = validate(result, uniques)
    if problems:
        raise VaseragaBalanceError("; ".join(problems))
    result["notes"] = notes(moves, facts["1"], ability, leader)
    return result


def notes(moves: dict, facts: dict, ability: dict, leader: list[list[str]]) -> dict:
    describe = {key: [wf_describe.describe_line(row, "ability") for row in rows] for key, rows in ability.items()}
    describe[LEADER] = [wf_describe.describe_line(row, "leader_ability") for row in leader]
    return {
        "character": f"{CID} {CODE} 巴萨拉卡（暗）",
        "spec": "作者 2026-09-27 逐条确认：去主位限制、代受移入能力3、删能力2超负荷行、134→194、"
                "能力加成×0.8、能力5 +10%×10、队长成长 1/10、面板覆盖 7 键、技能描述规范化",
        "changes": [
            "ability 1699971: 行3代受移出；行1/2 25%/40%；c1=true（2 行）",
            "ability 1699972: 删行1（461 超负荷）；六行 ×0.8；c1=true（6 行）",
            "ability 1699973: 行2-4 c97 134→194 且 ×0.8；追加代受为行8；整键 c1=false（8 行）",
            "ability 1699974: c1=true",
            "ability 1699975: 行2 c51/c52 25000→10000、c34 (None)→10；c1=true",
            "ability 1699976: 行3/4 逆境 40%、行5 独立乘区 15%；行6 c1 false→true",
            "leader_ability 169997: 行11/12 c49/c50 50000→5000（c32 仍 (None)）",
            "custom_ability_string: 新增 desc_override_vaseraga_dark 与 _1.._6",
            "action_skill 1/2 c1、character_text c5/c7/c9、服务端 character_text [5]/[7]/[9]：技能描述规范化",
        ],
        "moves": moves,
        "scaled": {f"ability{slot}#{number}": [old, new] for (slot, number), (old, new) in SCALED.items()},
        "fix_194": {
            "why": "1699979 叠层上限 c4=1 ⇒ Condition.get_accumulatable()=false，during-134（按层数）恒读 0 层；"
                   "194 ConditionCountUnique 按实例个数，持有超负荷即 1",
            "shape": {str(k): v for k, v in OFFICIAL_194_SELF.items()},
            "official_precedents": list(OFFICIAL_194_SELF_PRECEDENTS),
            "official_other_shape": {"rows": list(OFFICIAL_194_OTHER_ROWS),
                                     "note": "c98=5、c110=7 的非自身来源形；c100/c101=100000、c102=1、c108=false 同值，"
                                             "不作本次先例"},
        },
        "ability5_limit": {"c34": ABILITY5_LIMIT, "step": ABILITY5_STEP, "cooltime_frames": 90,
                           "official_precedents": ["2510534#0", "2510536#0", "1510215#0", "1510333#2 (CT 600)"]},
        "skill_dsl_facts": facts,
        "skill_description_note": "DSL 的持续伤害是 ACPoison，客户端 ui_string 状态名「中毒效果」、无「流血」状态；"
                                  "作者确认稿原写「流血」，按规格「不符就按 DSL 改文案」写作「中毒」",
        "panel_note": "逆境措辞对照 ui_string ability_description_condition_content_adversity_buff"
                      "「逆境效果[最大 ::percent_up_down2::]」；主位槽只有能力3，逐行带 main 图标",
        "candidate_notes": [
            "候选 vaseraga_dark leader 行5 c33=600 与 live 1200 漂移（既有）；本次 leader 整键按 live 派生值替换，候选随之对齐 live",
            "候选包内文件与 manifest 无哈希漂移（无需 REVIEWED_DRIFT）",
            "live 与候选里旧的 custom_ability_string vaseraga_dark / _1.._6 设计稿串不被任何行引用（c70 空），本次不动",
        ],
        "generator": "无 mod-tools 生成器；work/character_packs/vaseraga_dark/build_workspace.py 是禁止重跑的历史 kit，"
                     "重跑会回退本次改动，本模块是唯一真源",
        "describe": describe,
        "capabilities": list(CAPABILITIES),
        "runtime_verified": False,
    }

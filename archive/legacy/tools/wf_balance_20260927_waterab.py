# -*- coding: utf-8 -*-
"""水属性两名的能力伤害倍率：杰拉尔 129992 ``unicorn_lancer_rose`` 与 见岛勇希(泳装) 129991
``psychic_yuki_swim``——2026-09-27 作者「杰拉尔和夏勇希的能力伤害倍率都降低一些」（纯函数）。

口径（主会话定）：只降**造成能力伤害的那一下的攻击倍率**，×0.8；能力伤害加成类 buff
（388 AbilityDamage、695 独立乘区能力伤害等）一律不动。三个倍数 ×0.8 都是整数，不需要取整。

杰拉尔（3 处，= 该角色全部能力伤害攻击，见 :func:`audit` 的全量核对）：

1. 能力1 kind 629 誓约之枪追击：能力 DSL ``…/ability_skill/unicorn_lancer_rose_oath_strike$…``，
   根头 tree[10]=102（damage-type-rules ``segment_override("ability")``，按能力伤害结算），
   唯一一处 CreateNormalAttack p6 每段倍率 45 → 36；629 行本身 c51/c52=0 不带倍率。
   文案 custom_ability_string ``change_skill_unicorn_lancer_rose_oath_strike``「45倍」→「36倍」。
2. 能力3 行3（水属性角色发动技能 → 最近敌人 kind353 NearestEnemyDamageByAttackBlue）
   c51/c52 1000000 → 800000（10 → 8 倍）。
3. 能力5 行1（水共鸣 技能Hit、CT1秒 → 全体 kind252 EnemyDamageByAttackBlue）
   c51/c52 1500000 → 1200000（15 → 12 倍）。

勇希（1 处）：能力2 行3（水共鸣 每 75 连击 → 全体 kind252）c51/c52 1000000 → 800000（10 → 8 倍）。

核实范围（全部只读、全部进 BEFORE）：两人的队长 + 6 个能力键全部行的内容块、全部 629 调用的 DSL、
技能 DSL 两档、杰拉尔 722 强化弹射覆盖 DSL 三档。技能/PF DSL 根头 tree[10]=0 且所有 CreateHitArea
p24（node[24]）=0 ⇒ 按技能/PF 结算，不是能力伤害；词条表瞬发行里造成伤害的 kind（251-286 / 316-387
EnemyDamageBy*、208-210 / 719 比例与定值伤害）只有上面列出的
（杰拉尔 2 行 + 1 条 629、勇希 1 行）。出现任何未审查的能力伤害来源 ⇒ 拒绝。

面板：两人都没有 ``desc_override_*`` 覆盖行，能力面板由客户端按行数据自动生成（wf_describe：
「…能力伤害·依攻击水 800%(8倍)」），不新增覆盖；只有 629 行的文案键需要改数字。

生成器：``wf_water_balance_20260924`` 同步（STRIKE 倍率 36 与 STRIKE_TEXT、``yuki_rows`` 的 252 行
800000、``gerald_rows("1299925")`` 行1 1200000）；勇希 kit ``wf_seasonal7_kit_yuki.build`` 在改版方案
锁定行之上调用同一个 ``yuki_rows``。:func:`revise_gerald` 运行时断言 strike DSL / 文案 == 生成器，
其余一致性由测试断言。能力3 行3（kind353）没有可重跑的跟踪生成器：它来自未跟踪的历史 staging kit
``work/character_packs/_ulr_scripts/kit_rows.py``（整体早已落后 live，不可重跑），本模块是这一行的真源；
``wf_gerald_resonance`` 对 1299925 的哈希闸门对三行现状与新倍率都拒绝（fail closed，不会回退）。

接口见 ``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``（多角色 ⇒ :data:`UNITS`）。每个 revise 只经
``read`` 读 live，开头按该单元的 BEFORE 摘要校验（漂移即抛 :class:`WaterAbilityBalanceError`），不改
``read`` 的返回对象。不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as legality
import wf_describe
import wf_dsl
from wf_battle_rules import DAMAGE_CAP, segment_override
import wf_water_balance_20260924 as generator

ABILITY_WIDTH, LEADER_WIDTH = 126, 124
WATER_ELEMENT = 1                  # master/character c3 内部 ElementKind（0 基）：水
WATER = "Blue"
SCALE_NUM, SCALE_DEN = 4, 5        # ×0.8，只接受整除（三个倍数都整除，不取整）
STRENGTH = (51, 52)                # ability 瞬发内容块强度：c51 低级 / c52 满级（1000000 = 10 倍）

#: 造成伤害的词条内容 kind（InstantAbilityContentMasterValue）：EnemyDamageBy* 三族 + 比例 / 定值伤害。
ABILITY_DAMAGE_KINDS = frozenset(
    {str(k) for k in (*range(251, 287), *range(316, 388), 208, 209, 210, 719)})
INVOKE_SKILL = "629"
PF_OVERRIDE = "722"
INVOKE_PROGRAM_OFFSET = 24         # 629 行：内容 kind 列 + 23 = 文案键、+ 24 = DSL 程序（ability c70/c71）
PF_OVERRIDE_NAME_OFFSET, PF_OVERRIDE_LEVELS_OFFSET = 35, 36   # 722 行：leader c80 覆盖名 / c81 档位
DAMAGE_CONSTRUCTS = ("CreateNormalAttack", "CreateFixedAttack", "CreateRatioAttack",
                     "CreateShockWaveAttack", "CreateTargetAttack", "CreateWindAttack",
                     "CreateOnlyHitAttack")
ABILITY_SEGMENTS = frozenset({2, segment_override("ability")})   # 2 原生能力归属 / 102 规则补丁覆盖


class WaterAbilityBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WaterAbilityBalanceError(message)


def scaled(value: str) -> str:
    """强度 ×0.8；不整除或非正即拒绝（本批三个倍数都整除）。"""
    number = int(value)
    _require(number > 0 and number * SCALE_NUM % SCALE_DEN == 0, f"strength {value!r} is not scalable")
    return str(number * SCALE_NUM // SCALE_DEN)


def pf_override_program(name: str, level: str) -> str:
    """722 行（覆盖名, 档位）→ 强化弹射覆盖 DSL 程序路径。"""
    return f"battle/action/power_flip/action/override/{name}${name}_lv{level}"


# ------------------------------------------------------------------ 杰拉尔 129992

GERALD_CID, GERALD_CODE = "129992", "unicorn_lancer_rose"
GERALD_ABILITY = {slot: f"{GERALD_CID}{slot}" for slot in range(1, 7)}
GERALD_SKILLS = {lv: f"battle/action/skill/action/rare5/{GERALD_CODE}${GERALD_CODE}_{lv}" for lv in ("1", "2")}
PF_OVERRIDE_NAME = f"override_{GERALD_CODE}_dual_pf"
GERALD_PF = {lv: pf_override_program(PF_OVERRIDE_NAME, lv) for lv in ("1", "2", "3")}
STRIKE_KEY = generator.STRIKE_KEY                 # change_skill_unicorn_lancer_rose_oath_strike
STRIKE_PROGRAM = generator.STRIKE_PROGRAM         # …/ability_skill/unicorn_lancer_rose_oath_strike$…
STRIKE_OLD, STRIKE_NEW = 45, 36
STRIKE_TEXT_OLD = "对距离最近的敌人造成45倍水属性能力伤害，威力随连击数提升"
STRIKE_TEXT_NEW = STRIKE_TEXT_OLD.replace(f"{STRIKE_OLD}倍", f"{STRIKE_NEW}倍")

#: {(能力键, 行号 0 起): 改前指纹（含 c51/c52 旧值）}；两格改成 :func:`scaled` 的结果。
GERALD_ROWS = {
    (GERALD_ABILITY[3], 2): {0: f"{GERALD_CODE}_3", 1: "false", 2: "special", 5: "0", 6: "0",
                             27: "23", 28: "5", 29: WATER, 30: "100000", 31: "100000", 35: "0",
                             47: "353", 48: "0", 51: "1000000", 52: "1000000"},
    (GERALD_ABILITY[5], 0): {0: f"{GERALD_CODE}_5", 1: "true", 2: "attack_blue", 5: "0", 6: "2",
                             9: "600000", 10: "600000", 11: WATER, 27: "107", 28: "0",
                             30: "100000", 31: "100000", 35: "60",
                             47: "252", 48: "0", 51: "1500000", 52: "1500000"},
}
GERALD_NEW = {(GERALD_ABILITY[3], 2): "800000", (GERALD_ABILITY[5], 0): "1200000"}

#: live 输入基线（2026-09-27 本地链尾 1.4.1048 只读取数）。候选 unicorn_lancer_rose 0.1.13 的 138 个
#: manifest 条目与文件零漂移；除队长键 129992（既有：live 10 行、候选 9 行——live 的连击+10/+20 两行与
#: 「除自身水技能槽 10%」未回写候选；本批只读、不回写，另报）外，下列各项与候选逐项相同。
GERALD_BEFORE: dict[tuple[str, str], str] = {
    ("ability", GERALD_ABILITY[1]): "9e3aac47ef74e819f0a1e0fc3aeed8248994ced08232ae85ab6068c31880bcd7",
    ("ability", GERALD_ABILITY[2]): "9b51f4167aec99fa2172007165d6835115cf185150acb9cfb0f4a51bfac26ade",
    ("ability", GERALD_ABILITY[3]): "6547a4222284806e4eb4111c17638440482fbc979a6a4acf3c82d945b03a8b62",
    ("ability", GERALD_ABILITY[4]): "6dad9f7c747450873f04261b68bf0261de4b96dd4ce5f04d5614a913514fb142",
    ("ability", GERALD_ABILITY[5]): "594c4608108a1692c7a408b3b40b288e7b118955d1eab58b80ba6ac289d57c00",
    ("ability", GERALD_ABILITY[6]): "baad2fa220590640f27848ba712cacce4a0a5cf04fcfebeb27b4362806201744",
    ("leader", GERALD_CID): "394e1a11bdff8187a5bd0e2d3503bd5509dcb7c4ab5312b863eb5fd92abc14af",
    ("cas", STRIKE_KEY): "1dc7ba9969b60a0a95a91ed6579259f4ba619a7d5ec1340186fa8e338636a729",
    ("dsl", STRIKE_PROGRAM): "2513c86b1ad2c9e94ac287a29e3521499add11c2a02a4e8c59f496e549e0c158",
    ("dsl", GERALD_SKILLS["1"]): "28a27cfd3216e484ce44f20756b5818e2fa0c9d1e60f60eb734956acd0a3b8f7",
    ("dsl", GERALD_SKILLS["2"]): "87d62572a1a4303adeb2830d5d8e44ae5e9b72ac957cc4b6f7fd484ce6280891",
    ("dsl", GERALD_PF["1"]): "e27ef7fc0bd793de97b9ebc01c15e4e9175d2465cda000a93a2b1900a81a3623",
    ("dsl", GERALD_PF["2"]): "69900dd4492060671a1d84302ba7e87006f1d0545754311b645fe0ddb5504bd3",
    ("dsl", GERALD_PF["3"]): "bc0c694401f0fb2e239824db711956f26603441a40500f1e61cef49f88bc5501",
}

# ------------------------------------------------------------------ 见岛勇希(泳装) 129991

YUKI_CID, YUKI_CODE = "129991", "psychic_yuki_swim"
YUKI_ABILITY = {slot: f"{YUKI_CID}{slot}" for slot in range(1, 7)}
YUKI_SKILLS = {lv: f"battle/action/skill/action/rare5/{YUKI_CODE}${YUKI_CODE}_{lv}" for lv in ("1", "2")}
YUKI_ROWS = {
    (YUKI_ABILITY[2], 2): {0: f"{YUKI_CODE}_2", 1: "true", 2: "action_skill", 5: "0", 6: "2",
                           9: "600000", 10: "600000", 11: WATER, 27: "12", 30: "7500000",
                           31: "7500000", 35: "0", 47: "252", 48: "0", 51: "1000000", 52: "1000000"},
}
YUKI_NEW = {(YUKI_ABILITY[2], 2): "800000"}

#: live 输入基线（同上取数；与候选 s7-yuki 0.2.0 逐项相同，120 个 manifest 条目零漂移）。
YUKI_BEFORE: dict[tuple[str, str], str] = {
    ("ability", YUKI_ABILITY[1]): "fe88be326e086da7282cf9441ed838fdff318b6af2ac04e8f50be85d9329de83",
    ("ability", YUKI_ABILITY[2]): "1cb0210ab4986020eb89f91d9e17d766f89ffa418d28ec6682c3e00605f983e6",
    ("ability", YUKI_ABILITY[3]): "6f797c4356ef0a7a572fba63d722f29c16929eff50bce82f73f9883e955bd477",
    ("ability", YUKI_ABILITY[4]): "508b6f06f2ae3e5a9e3b87b1a2dac1ee58eca871062e3334939010cceeb98189",
    ("ability", YUKI_ABILITY[5]): "c3f519b787b23101af22148636c93d4b92fb253679030fdf206026f6638b3d31",
    ("ability", YUKI_ABILITY[6]): "bb1c54dfcf0b896b131eb96bc719fa281a1917e0ac3023d91b1bb108d5834e5e",
    ("leader", YUKI_CID): "38b2df3d666bcd09b297627a0a53f5970cd110a8bb155936d8297f0771031b1e",
    ("dsl", YUKI_SKILLS["1"]): "1be26afd2c5cc35e0f6c1ea5b3b0a0d783ca82f7e5a7ad1942c94ca94b0a263a",
    ("dsl", YUKI_SKILLS["2"]): "ef49aea6a866ef6dc8f88ae1c6358580dd7e23607aca441e9aadfef4ffe3ab47",
}

BEFORE = {**GERALD_BEFORE, **YUKI_BEFORE}


# ------------------------------------------------------------------ 读取与核对

def _baseline(read: Callable, before: dict) -> dict:
    inputs = {}
    for (kind, key), want in before.items():
        value = read(kind, key)
        got = digest(value)
        if got != want:
            raise WaterAbilityBalanceError(f"live drift: {kind}:{key} sha256 {got} != reviewed {want}")
        inputs[kind, key] = deepcopy(value)
    return inputs


def _content_col(kind: str, row: list[str]) -> int | None:
    """瞬发行的内容 kind 列；持续行（模式 1，CommonAbilityContentMasterValue 最大 424，无造伤 / 629 / 722，
    且 252 等数字在那套枚举里是别的含义）与开幕行（模式 2）返回 None，不参与造伤分类。"""
    blocks = wf_describe.layout(kind)["blocks"]
    mode = row[blocks["precondition1"] - 1]
    _require(mode in ("0", "1", "2"), f"{kind}: unknown trigger mode {mode!r}")
    return blocks["instant_content"] if mode == "0" else None


def row_damage_sites(kind: str, key: str, rows: list[list[str]]) -> tuple[list, list, list]:
    """一个键里的（能力伤害行 [(key, 行号, kind)]、629 调用 [(key, 行号, 文案键, 程序)]、722 覆盖 [(名, 档位)]）。"""
    width = ABILITY_WIDTH if kind == "ability" else LEADER_WIDTH
    damage, invokes, overrides = [], [], []
    for index, row in enumerate(rows):
        _require(len(row) == width, f"{kind}:{key}#{index} width {len(row)} != {width}")
        col = _content_col(kind, row)
        if col is None:
            continue
        if row[col] in ABILITY_DAMAGE_KINDS:
            damage.append((key, index, row[col]))
        elif row[col] == INVOKE_SKILL:
            invokes.append((key, index, row[col + INVOKE_PROGRAM_OFFSET - 1],
                            row[col + INVOKE_PROGRAM_OFFSET]))
        elif row[col] == PF_OVERRIDE:
            overrides.append((row[col + PF_OVERRIDE_NAME_OFFSET],
                              tuple(row[col + PF_OVERRIDE_LEVELS_OFFSET].split(","))))
    return damage, invokes, overrides


def ability_damage_sites(tree) -> list[list]:
    """树里按能力伤害结算的伤害命令：根头 tree[10] ∈ {2, 102} ⇒ 全部；否则只算 p24 ∈ {2, 102} 判定区的命中块。"""
    if tree[10] in ABILITY_SEGMENTS:
        return [node for name in DAMAGE_CONSTRUCTS for node in wf_dsl.iter_dsl_commands(tree, name)]
    sites = []
    for area in wf_dsl.iter_dsl_commands(tree, "CreateHitArea"):
        if area[24] in ABILITY_SEGMENTS:
            sites += [node for name in DAMAGE_CONSTRUCTS for node in wf_dsl.iter_dsl_commands(area[23], name)]
    return sites


def dsl_attribution(tree) -> dict:
    return {"buffTargetAs": tree[10],
            "hit_area_p24": sorted({area[24] for area in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")}),
            "damage_commands": sum(1 for name in DAMAGE_CONSTRUCTS for _ in wf_dsl.iter_dsl_commands(tree, name)),
            "ability_damage_commands": len(ability_damage_sites(tree))}


def audit(inputs: dict, cid: str, abilities: dict, *, row_sites: set, invoke_programs: dict,
          pf_programs: dict, skill_programs: dict) -> dict:
    """全量核对：能力伤害来源必须恰好是已审查的那几处，否则拒绝。返回写进 notes 的证据。"""
    damage, invokes, overrides = row_damage_sites("leader_ability", cid, inputs["leader", cid])
    for key in abilities.values():
        more = row_damage_sites("ability", key, inputs["ability", key])
        damage, invokes, overrides = damage + more[0], invokes + more[1], overrides + more[2]
    _require({(key, index) for key, index, _ in damage} == row_sites,
             f"{cid}: ability-damage rows {damage} != reviewed {sorted(row_sites)}")
    _require({(key, index): (sid, program) for key, index, sid, program in invokes} == invoke_programs,
             f"{cid}: 629 invokes {invokes} != reviewed {invoke_programs}")
    want_pf = sorted(pf_override_program(name, lv) for name, levels in overrides for lv in levels)
    _require(want_pf == sorted(pf_programs.values()), f"{cid}: PF override programs {want_pf} != {pf_programs}")
    trees = {"invoke": {program: dsl_attribution(inputs["dsl", program]) for _, program in invoke_programs.values()},
             "skill": {program: dsl_attribution(inputs["dsl", program]) for program in skill_programs.values()},
             "power_flip": {program: dsl_attribution(inputs["dsl", program]) for program in pf_programs.values()}}
    for group in ("skill", "power_flip"):
        for program, info in trees[group].items():
            _require(info["ability_damage_commands"] == 0, f"{program}: unreviewed ability-damage segment {info}")
    return {"rows": [{"key": key, "row": index + 1, "kind": kind} for key, index, kind in damage],
            "invokes": [{"key": key, "row": index + 1, "string": sid, "program": program}
                        for key, index, sid, program in invokes],
            "dsl": trees}


def _scale_row(rows: list[list[str]], index: int, expected: dict[int, str], new: str, label: str) -> None:
    row = rows[index]
    got = {col: row[col] for col in expected}
    _require(got == expected, f"{label}: unexpected preimage {got} != {expected}")
    for col in STRENGTH:
        row[col] = scaled(row[col])
    _require(all(row[col] == new for col in STRENGTH), f"{label}: ×0.8 gives {row[51]}/{row[52]} != {new}")


def scale_rows(inputs: dict, edits: dict, news: dict) -> dict[str, list[list[str]]]:
    out: dict[str, list[list[str]]] = {}
    for (key, index), expected in edits.items():
        rows = out.setdefault(key, deepcopy(inputs["ability", key]))
        _scale_row(rows, index, expected, news[key, index], f"ability:{key}#{index}")
    return out


def strike_tree(tree):
    """629 誓约之枪追击：唯一一处 CreateNormalAttack 每段倍率 45 → 36；其余逐字保留。"""
    out = deepcopy(tree)
    _require(out[0] == "ActionDsl" and out[10] == segment_override("ability"),
             f"strike root is not an ability-damage segment override: {out[10]!r}")
    attacks = list(wf_dsl.iter_dsl_commands(out, "CreateNormalAttack"))
    _require(len(attacks) == 1 and attacks[0][6] == [{"min": STRIKE_OLD, "max": STRIKE_OLD}],
             "strike tree is not the reviewed single 45x hit")
    _require(len(ability_damage_sites(out)) == 1, "strike tree has other damage commands")
    attacks[0][6] = [{"min": STRIKE_NEW, "max": STRIKE_NEW}]
    _require(STRIKE_OLD * SCALE_NUM == STRIKE_NEW * SCALE_DEN, "strike multiplier is not ×0.8")
    return out


def strike_text(rows: list[list[str]]) -> list[list[str]]:
    _require(rows == [[STRIKE_TEXT_OLD]], f"unexpected strike text {rows!r}")
    return [[STRIKE_TEXT_NEW]]


# ------------------------------------------------------------------ 门禁

def row_problems(rows: dict[str, list[list[str]]], cas_keys) -> list[str]:
    probs = []
    for key, table in rows.items():
        for index, row in enumerate(table):
            for p in (legality.client_legality_problems("ability", row)
                      + legality.declared_block_field_problems("ability", row)
                      + legality.invoke_skill_string_problems(row, set(cas_keys), "ability")
                      + legality.ability_element_column_problems("ability", row, WATER_ELEMENT)):
                probs.append(f"ability:{key}#{index}: {p}")
    return probs


def dsl_problems(tree) -> list[str]:
    probs = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        probs.append("AMF3 roundtrip mismatch")
    probs += legality.action_dsl_element_problems(tree, WATER_ELEMENT)
    probs += legality.action_dsl_subject_binding_problems(tree)
    probs += legality.action_dsl_lookup_scope_problems(tree)
    probs += legality.action_dsl_hit_area_target_problems(tree)
    return probs


def _change_notes(inputs: dict, out: dict[str, list[list[str]]], edits: dict) -> list[dict]:
    notes = []
    for key, index in edits:
        old, new = inputs["ability", key][index], out[key][index]
        notes.append({"key": key, "row": index + 1, "kind": old[47],
                      "c51/c52": f"{old[51]}/{old[52]} → {new[51]}/{new[52]}",
                      "panel": f"{wf_describe.describe_line(old, 'ability')} → "
                               f"{wf_describe.describe_line(new, 'ability')}"})
    return notes


# ------------------------------------------------------------------ 入口

def revise_gerald(read: Callable) -> dict:
    inputs = _baseline(read, GERALD_BEFORE)
    evidence = audit(inputs, GERALD_CID, GERALD_ABILITY, row_sites=set(GERALD_ROWS),
                     invoke_programs={(GERALD_ABILITY[1], 0): (STRIKE_KEY, STRIKE_PROGRAM)},
                     pf_programs=GERALD_PF, skill_programs=GERALD_SKILLS)
    _require(evidence["dsl"]["invoke"][STRIKE_PROGRAM]["ability_damage_commands"] == 1,
             "strike DSL must be the single ability-damage hit")
    ability = scale_rows(inputs, GERALD_ROWS, GERALD_NEW)
    tree = strike_tree(inputs["dsl", STRIKE_PROGRAM])
    cas = {STRIKE_KEY: strike_text(inputs["cas", STRIKE_KEY])}
    # 生成器一致性（运行时）：wf_water_balance_20260924 重跑产出的追击 DSL / 文案必须 == 本次输出。
    _require(tree == generator.strike_tree(), "generator strike_tree() differs from the revision")
    _require(cas[STRIKE_KEY] == [[generator.STRIKE_TEXT]], "generator STRIKE_TEXT differs from the revision")
    probs = row_problems(ability, set(cas)) + [f"{STRIKE_PROGRAM}: {p}" for p in dsl_problems(tree)]
    _require(not probs, "; ".join(probs))
    return {
        "ability": ability, "leader": {}, "cas": cas, "text": {}, "table": {}, "action": {},
        "dsl": {STRIKE_PROGRAM: tree}, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927_waterab.py",
            "request": "杰拉尔和夏勇希的能力伤害倍率都降低一些（作者 2026-09-27）；口径：只降能力伤害攻击倍率 ×0.8",
            "changed": _change_notes(inputs, ability, GERALD_ROWS) + [
                {"dsl": STRIKE_PROGRAM, "CreateNormalAttack p6": f"{STRIKE_OLD} → {STRIKE_NEW}",
                 "buffTargetAs": "102 (segment override → ability damage)"},
                {"cas": STRIKE_KEY, "text": f"{STRIKE_TEXT_OLD} → {STRIKE_TEXT_NEW}"}],
            "audit": evidence,
            "untouched": "能力伤害加成 buff（队长 388 300%、能力2/3 388 200%、能力5 695 20%）与其余行、技能 DSL、PF DSL",
            "panel": "无 desc_override_unicorn_lancer_rose*；能力面板客户端按行自动生成，只改 629 文案键",
            "generator": ("wf_water_balance_20260924：STRIKE_MULTIPLIER/STRIKE_TEXT 36 倍、gerald_rows(1299925) 行1 "
                          "1200000；能力3 行3 无可重跑跟踪生成器（_ulr_scripts/kit_rows.py 为未跟踪的历史 staging kit）"),
            "capabilities": [DAMAGE_CAP],
            "runtime_verified": False,
        },
    }


def revise_yuki(read: Callable) -> dict:
    inputs = _baseline(read, YUKI_BEFORE)
    evidence = audit(inputs, YUKI_CID, YUKI_ABILITY, row_sites=set(YUKI_ROWS), invoke_programs={},
                     pf_programs={}, skill_programs=YUKI_SKILLS)
    ability = scale_rows(inputs, YUKI_ROWS, YUKI_NEW)
    probs = row_problems(ability, set())
    _require(not probs, "; ".join(probs))
    return {
        "ability": ability, "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": {}, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927_waterab.py",
            "request": "杰拉尔和夏勇希的能力伤害倍率都降低一些（作者 2026-09-27）；口径：只降能力伤害攻击倍率 ×0.8",
            "changed": _change_notes(inputs, ability, YUKI_ROWS),
            "audit": evidence,
            "untouched": "其余行（含能力2 行1/行2）、队长技、技能 DSL（按技能伤害结算）",
            "panel": "无 desc_override_psychic_yuki_swim*；能力面板客户端按行自动生成",
            "generator": ("wf_water_balance_20260924.yuki_rows 的 252 行 800000；"
                          "wf_seasonal7_kit_yuki.build 在改版方案锁定行上调用同一 yuki_rows"),
            "capabilities": [],
            "runtime_verified": False,
        },
    }


UNITS = [
    dict(CID=GERALD_CID, CODE=GERALD_CODE, NAME="杰拉尔",
         PACKAGES=["unicorn_lancer_rose"],
         #: 候选现值 0.1.13（wf_water_balance_20260924 写入；此前 combo35 0.1.11）→ 递增。
         PACKAGE_VERSION={"unicorn_lancer_rose": "0.1.14"},
         #: 追击 DSL 根头 102 依赖 damage-type-rules-v1（候选已声明；并集写回不变）。
         CAPABILITIES=[DAMAGE_CAP], REVIEWED_DRIFT={}, BEFORE=GERALD_BEFORE, revise=revise_gerald),
    dict(CID=YUKI_CID, CODE=YUKI_CODE, NAME="见岛勇希(泳装)",
         PACKAGES=["s7-yuki"],
         #: 候选现值 0.2.0（0924 写入，比 0917 surge-anchor 写过的 1.0.5 低）；取历史最高的下一号，只升不降。
         PACKAGE_VERSION={"s7-yuki": "1.0.6"},
         CAPABILITIES=[], REVIEWED_DRIFT={}, BEFORE=YUKI_BEFORE, revise=revise_yuki),
]

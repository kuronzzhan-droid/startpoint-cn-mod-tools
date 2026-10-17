"""Deterministic Gerald R2 table/DSL transforms against published 1.4.764."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import wf_dsl
import wf_mod_tool as core

OLD_DESCRIPTION = ("举起碧海之矛向距离最近的敌人突进，原地释放连续突刺，对命中的敌人造成水属性伤害"
                   "／水属性共鸣时：追加赋予己方贯穿效果 ＋ 队伍技能伤害提升效果，并赋予命中的敌人「对决」效果")
DESCRIPTIONS = {
    "1": "举起碧海之矛向距离最近的敌人突进，原地释放连续突刺，对命中的敌人造成合计60倍水属性技能伤害，随连击数提升威力。",
    "2": "举起碧海之矛向距离最近的敌人突进，原地释放连续突刺，对命中的敌人造成合计90倍水属性技能伤害，随连击数提升威力。",
}
OLD_ABILITY3 = "为『碧海圣矛·连突』追加「赋予己方贯穿效果 ＆ 队伍技能伤害提升效果 ＆ 赋予命中的敌人对决效果」"
PREVIOUS_ABILITY3 = ("为『碧海圣矛·连突』追加「赋予己方贯穿效果 ＆ 队伍技能伤害提升效果 ＆ "
            "强制赋予命中的敌人无法消除的『对决』效果 ＆ 赋予自身浮游效果20秒」")
R2_ABILITY3 = ("技能追加：己方贯穿、队伍技能伤害提升、自身浮游20秒；"
               "命中时强制赋予敌人不可消除的「对决」。")
#: 2026-09-27 第三轮（wf_balance_20260927c_panels FLAG_TEXT，主会话 R2）：技能强化条目用官方格式「为『<技能名>』追加「…」」，
#: 点明现技能名、不写数字与秒数（live 技能名 = 誓约之枪·连突）。
ABILITY3 = "为『誓约之枪·连突』追加「己方贯穿＋队伍技能伤害提升＋自身浮游效果」，命中时强制赋予敌人不可消除的「对决」"
LEADER_HASH = "0f2859871aacaf12dfe28b68ab88506fa383002baaac7fba50afdbe6c826f76c"
ABILITY2_HASH = "21784829c9fc249088e4df055fd233de22475a86d5abde5c2ed8034d477fcc29"
TEXT_HASH = "28f62354378d40a833046294046524efb8b8a356abd61eaf2c66cfc6379b7ca3"
TREE_HASHES = {
    "1": "af0ddb8235cfa87972bd382c91b06f5913246392ea5b1217d8f25d2c1ea65c50",
    "2": "7be0561c7ce9db14a0c2c49297fa85a57c340a5e344e43769d16d56127b23160",
}
# -17 is the casting Member; -18 is its movement Ball, whose condition-owner
# probe throws. Member's condition slot forwards Flying to the squad slot.
FLYING = ["Command", ["CreateCondition", -17,
    [["ACFlying", [{"min": 1200, "max": 1200}]]], [{"min": 1, "max": 1}],
    ["GenericConditionHitEffect"], True, False, "", None, False, 3,
    [{"min": 1, "max": 1}], False]]


def guard_text(value: str, digest: str):
    if hashlib.sha256(value.encode("utf-8")).hexdigest() != digest:
        raise ValueError("unrecognized Gerald 1.4.764 target row")


def leader(value: str) -> str:
    rows = core.read_csv_lines(value)
    if len(rows) != 8 or rows[0][45] not in ("565", "721"):
        raise ValueError("unexpected Gerald leader structure")
    if (rows[1][32], rows[1][49], rows[1][50]) not in (
            ("5", "1000000", "1000000"), ("10", "100000", "100000")):
        raise ValueError("unrecognized leader combo progression")
    normalized = deepcopy(rows)
    normalized[0][45] = "565"
    normalized[1][32], normalized[1][49], normalized[1][50] = "5", "1000000", "1000000"
    guard_text(core.write_csv_lines(normalized), LEADER_HASH)
    rows[0][45] = "721"  # SeparatedTermUniqueSkillSlayer, native Unique 129992 filter.
    rows[1][32], rows[1][49], rows[1][50] = "10", "100000", "100000"
    return core.write_csv_lines(rows)


def ability2(value: str) -> str:
    rows = core.read_csv_lines(value)
    if len(rows) not in (2, 3):
        raise ValueError("unexpected Gerald ability 2 structure")
    guard_text(core.write_csv_lines(rows[:2]), ABILITY2_HASH)
    added = [""] * 126
    added[:5] = rows[0][:5]
    for column, value in {5: "0", 6: "0", 13: "0", 20: "0", 27: "23", 28: "5",
                          29: "Blue", 30: "100000", 31: "100000", 34: "(None)",
                          35: "0", 39: "(None)", 46: "0", 47: "226",
                          51: "2500000", 52: "2500000"}.items():
        added[column] = value
    if len(rows) == 3 and rows[-1] != added:
        raise ValueError("unknown extra row in Gerald ability 2")
    return core.write_csv_lines(rows[:2] + [added])


def description(value: str, level: str) -> str:
    if value not in (OLD_DESCRIPTION, DESCRIPTIONS[level]):
        raise ValueError("unknown Gerald skill description")
    return DESCRIPTIONS[level]


def character_text(value: str) -> str:
    row, = core.read_csv_lines(value)
    row[5], row[7] = description(row[5], "1"), description(row[7], "2")
    normalized = deepcopy(row)
    normalized[5] = normalized[7] = OLD_DESCRIPTION
    guard_text(core.write_csv_lines([normalized]), TEXT_HASH)
    return core.write_csv_lines([row])


def ability3(value: str) -> str:
    if value not in (OLD_ABILITY3, PREVIOUS_ABILITY3, R2_ABILITY3, ABILITY3):
        raise ValueError("unknown Gerald ability 3 string")
    return ABILITY3


def revise_tree(source, level: str):
    tree = deepcopy(source)
    attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    if len(attacks) != 3:
        raise ValueError("Gerald must retain its three damage phases")
    for attack in attacks:
        if not isinstance(attack[8], bool):
            raise ValueError("invalid native combo-bonus flag")
        attack[8] = False
    gates = [node[1] for node in tree[11][1] if node[0] == "Command"
             and node[1][0] == "ConditionalsChangeSkillFlag"]
    if len(gates) != 1 or gates[0][1] != 1:
        raise ValueError("missing ability-3 cast-time change-skill gate")
    commands = gates[0][2][1]
    legacy_flying = deepcopy(FLYING)
    legacy_flying[1][1] = -18
    known_flying = [entry for entry in commands if entry in (FLYING, legacy_flying)]
    if len(known_flying) > 1:
        raise ValueError("duplicate self-Flying command")
    if known_flying:
        commands.remove(known_flying[0])
    canonical = json.dumps(tree, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    guard_text(canonical, TREE_HASHES[level])
    # Native enablesComboBonus matches the official wind Siltie skill path.
    for attack in attacks:
        attack[8] = True
    commands.append(deepcopy(FLYING))
    return tree

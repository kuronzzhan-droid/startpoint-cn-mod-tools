"""Extract typed capability signals, never search arbitrary prose for kind IDs."""
from __future__ import annotations

import csv
import io
import re

from wf.dsl.references import ABILITY_TABLES, program_logical
from wf.view.layout import EM, col

UNIQUE = "master/character/unique_condition.orderedmap"
PF = "master/skill/power_flip_action.orderedmap"
SKILL = "master/skill/action_skill.orderedmap"
STRINGS = "master/string/custom_ability_string.orderedmap"
CHARACTER = "master/character/character.orderedmap"
BTA = {101, 102, 104, 131, 132, 133}
KIND_BLOCKS = {"422": "during_content", "423": "during_content", "424": "during_content",
               "419": "during_content", "724": "instant_content", "722": "instant_content", "629": "instant_content"}


def leaves(value, trail=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, (*trail, key))
    elif isinstance(value, str):
        yield trail, value
    else:
        raise ValueError(f"invalid orderedmap leaf at {trail}")


def rows(text):
    return list(csv.reader(io.StringIO(text, newline="")))


def table_signals(logical, trail, text, *, registry=None):
    """Yield (signal type, value), including references for a bounded closure."""
    table = logical.rsplit("/", 1)[-1].removesuffix(".orderedmap")
    yield "tables", table
    if table == "character_status" and len(trail) > 1 and trail[-1].isdigit() and int(trail[-1]) > 100:
        yield "selectors", "character_status.level>100"
    if logical == STRINGS and trail[-1].startswith("desc_override_"):
        yield "selectors", "text.desc_override"
    if logical == UNIQUE:
        yield "unique_ids", str(trail[-1])
        for row in rows(text):
            if row:
                yield "unique_string", row[0]
    for index, row in enumerate(rows(text)):
        if not row:
            continue
        if logical in ABILITY_TABLES:
            name = ABILITY_TABLES[logical]
            layout = EM["layouts"][name]
            heads = {note.split(" ")[0]: int(key[1:]) for key, note in layout["head"]}
            width = max(int(layout["blocks"][block]) + max(int(f[0]) for f in
                EM["block_fields"]["precondition" if block.startswith("precondition") else block])
                for block in layout["blocks"]) + 1
            if len(row) < width:
                raise ValueError(f"{logical}/{'/'.join(trail)}/{index}: truncated ability row ({len(row)} < {width})")
            trigger = row[heads["trigger"]]
            block = {"0": "instant_content", "1": "during_content"}.get(trigger)
            if block:
                kind = row[col(name, block, "kind")]
                if registry is None:
                    from .registry import load_registry
                    registry = load_registry()
                for cap in registry.values():
                    surface = cap["data_surface"]
                    if kind not in {str(k) for k in surface["kinds"]}:
                        continue
                    for field, actual in (("allowed_tables", name), ("allowed_blocks", block)):
                        if field in surface and actual not in surface[field]:
                            raise ValueError(f"问题: {logical}/{'/'.join(trail)}/{index}: kind {kind} "
                                             f"{field}={surface[field]}, actual={actual}")
                if KIND_BLOCKS.get(kind, block) != block:
                    raise ValueError(f"问题: {logical}/{'/'.join(trail)}/{index}: kind {kind} "
                                     f"requires {KIND_BLOCKS[kind]}, actual={block}")
                yield "kinds", kind
                if kind in {"722", "419"}:
                    levels = row[col(name, block, "powerflip_override.levels")]
                    if "4" in [v.strip() for v in levels.split(",")]:
                        yield "selectors", "pf.forLevels=4"
                    yield "ref", (PF, row[col(name, block, "powerflip_override.id")])
                if kind == "629" and block == "instant_content":
                    action = row[col(name, block, "action_path")]
                    skill = row[col(name, block, "string_id")]
                    if action not in {"", "(None)"}:
                        yield "program", action
                    elif program_logical(skill):
                        yield "program", skill
                    elif skill not in {"", "(None)"}:
                        yield "ref", (SKILL, skill)
            for block_name in layout["blocks"]:
                fields = EM["block_fields"]["precondition" if block_name.startswith("precondition") else block_name]
                for offset, field, _ in fields:
                    if field == "unique_condition_id":
                        value = row[int(layout["blocks"][block_name]) + int(offset)]
                        if value not in {"", "0", "(None)"}:
                            yield "unique_ids", value
                            yield "ref", (UNIQUE, value)
            if index == 0 and "unisonable" in heads and row[heads["unisonable"]] == "true":
                yield "selectors", "ability.unison-first-row"
            if "awake_kind" in heads and row[heads["awake_kind"]] in {"1", "2"}:
                yield "selectors", "ability.awake-row"
            yield "optional_ref", (STRINGS, "desc_override_" + row[0])
        elif logical == CHARACTER:
            if len(row) > 5 and "ModDualForm" in row[5].split(","):
                yield "selectors", "character.tag=ModDualForm"
            for position, target in [(8, SKILL), (14, "master/skill/switched_action_skill.orderedmap"),
                    (17, "master/ability/leader_ability.orderedmap"),
                    *[(p, "master/ability/ability.orderedmap") for p in range(19, 25)]]:
                if len(row) > position and row[position] not in {"", "0", "(None)"}:
                    yield "ref", (target, row[position])
            if len(row) > 14 and row[14].endswith("_voice_ready"):
                yield "selectors", "voice.skill_ready_alt"
        elif logical in {SKILL, "master/skill/switched_action_skill.orderedmap"}:
            if len(row) > 7 and row[7] not in {"", "(None)"}:
                yield "program", row[7]
        elif logical == PF:
            for value in row:
                if program_logical(value):
                    yield "program", value
        if "speech" in table and any(re.search(r"skill_ready.*alt|skill_ready_alt", cell) for cell in row):
            yield "selectors", "voice.skill_ready_alt"


def dsl_signals(tree):
    if not isinstance(tree, list) or not tree or tree[0] != "ActionDsl":
        raise ValueError("capability scan requires an ActionDsl root")
    if len(tree) > 10 and isinstance(tree[10], int) and tree[10] in BTA:
        yield "selectors", "dsl.buffTargetAs.convert"

    def walk(value):
        if isinstance(value, list):
            if value and isinstance(value[0], str):
                yield "dsl_nodes", value[0]
                if value[0] in {"ACUnique", "DCUnique"} and len(value) > 1:
                    unique = str(value[1])
                    if isinstance(value[1], (int, float)):
                        unique = str(int(value[1]))
                    yield "unique_ids", unique
                    yield "ref", (UNIQUE, unique)
                if value[0] == "CreateHitArea" and len(value) > 24 and isinstance(value[24], int) and value[24] in BTA:
                    yield "selectors", "dsl.buffTargetAs.convert"
            for child in value:
                yield from walk(child)
        elif isinstance(value, dict):
            for child in value.values():
                yield from walk(child)
        elif program_logical(value):
            yield "program", value

    yield from walk(tree)

"""Extract typed capability signals, never search arbitrary prose for kind IDs."""
from __future__ import annotations

import csv
import io
import re

from wfx_registry import patch_kinds_borrowing_uid_column
from wf.dsl.references import program_logical
from wf.view.layout import EM, col
from .signals_v35 import character_signals, custom_signals, unique_signals
from .surfaces import ABILITY_TABLES

UNIQUE = "master/character/unique_condition.orderedmap"
PF = "master/skill/power_flip_action.orderedmap"
SKILL = "master/skill/action_skill.orderedmap"
STRINGS = "master/string/custom_ability_string.orderedmap"
CHARACTER = "master/character/character.orderedmap"
BTA = {101, 102, 104, 131, 132, 133}


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
    if logical == STRINGS:
        yield from custom_signals(trail[-1])
    if logical == UNIQUE:
        yield "unique_ids", str(trail[-1])
        for row in rows(text):
            if row:
                yield from unique_signals(row[0], trail[-1])
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
                # Registry surfaces select dependencies. Only the selected
                # client's real SWF can decide whether a concrete site exists.
                yield "kind_site", {"table": name, "block": block, "kind": kind, "row": index}
                if (block, kind) in {("instant_content", "722"), ("during_content", "419")}:
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
                block_kind = row[int(layout["blocks"][block_name])]
                if (block_name, block_kind) in patch_kinds_borrowing_uid_column():
                    continue  # R3/423 carries a rule mask here, not a unique-condition reference.
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
            if name in {"ability", "leader_ability"}:
                prefix = "wfx_adaptive_" if name == "ability" else "wfx_unlock_"
                yield "optional_ref", (STRINGS, prefix + trail[0])
        elif logical == CHARACTER:
            yield from character_signals(trail[0], row)
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
            position = 7 if logical == SKILL else 0
            if len(row) > position and row[position] not in {"", "(None)"}:
                yield "program", row[position]
        elif logical == PF:
            yield "optional_ref", (STRINGS, "wfx_snapcombo_" + trail[0])
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

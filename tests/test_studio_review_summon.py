"""Ownership, template filtering and native summon edge regressions."""
import pytest
import wf_quest_lib as codec

from test_studio_summon import (summon_env, CID, MOTHER, OLD_BALL, NEW_BALL, request,
                                BALL, LEVEL, CHARACTER, STRINGS, flat, compiled)  # noqa: F401
from wf.studio.drafts import DraftError
from wf.studio.summon_tables import csv


@pytest.mark.parametrize("kind,key", [("multiball", NEW_BALL), ("string_id", "studio_summon_" + NEW_BALL)])
def test_reapply_never_releases_manual_reservations(summon_env, kind, key):
    _, store, editor = summon_env
    editor.apply(CID, request())
    document = store.load(CID)
    document["reservations"] = {kind: [key]}
    store.restore(CID, document)
    before = (store.directory(CID) / "changeset.json").read_bytes()
    with pytest.raises(DraftError, match="占用|预留"):
        editor.apply(CID, request())
    with pytest.raises(DraftError, match="占用|预留"):
        editor.read(CID)
    assert (store.directory(CID) / "changeset.json").read_bytes() == before


def test_empty_query_rarity_and_pagination(summon_env):
    _, _, editor = summon_env
    all_rows = editor.templates()
    assert all_rows["count"] > 0 and all_rows["items"][0]["rarity"] == 4
    assert editor.templates("none")["items"] == []
    page = editor.templates(limit=1, offset=1, rarity=4)
    expected = [r for r in all_rows["items"] if r["rarity"] == 4]
    assert page["items"] == expected[1:2] and page["total"] == len(expected)


def test_empty_native_skill_cannot_inherit_requested_tier_and_zero_attack_is_valid(summon_env):
    source, _, editor = summon_env
    balls = codec.parse_node(source.raw(BALL))
    row = flat(source.raw(BALL), OLD_BALL)[0]
    row[9] = "(None)"
    balls[OLD_BALL] = csv([row])
    levels = codec.parse_node(source.raw(LEVEL))
    level = flat(source.raw(LEVEL), OLD_BALL)[0]
    level[5] = "0"
    levels[OLD_BALL] = csv([level])
    source.view.files["common", BALL] = codec.build_node(balls)
    source.view.files["common", LEVEL] = codec.build_node(levels)
    source._raw.clear()
    with pytest.raises(DraftError, match="档位|技能"):
        editor.apply(CID, request(template={"kind": "multiball", "id": OLD_BALL},
                                  skill={"mode": "inherit", "level": "1"}), preview=True)
    result = editor.apply(CID, request(template={"kind": "multiball", "id": OLD_BALL}))
    assert result["panel"]["first"]["attack"] == result["panel"]["last"]["attack"] == 0


def test_image_overrides_and_lifetime_handoff_are_checked(summon_env):
    _, _, editor = summon_env
    with pytest.raises(DraftError, match="image_prefix"):
        editor.apply(CID, request(image_prefix="missing"), preview=True)
    result = editor.apply(CID, request(), preview=True)
    block = result["skillTemplate"]["summon"]
    assert block == {"multiballId": NEW_BALL, "durationFrames": 2147483647,
                     "maxCount": 1, "selfOnly": True}
    from wf.studio.skill_template_core import clone_tree
    from wf.studio.deliver_media import tree
    from test_studio_skill_template_core import root
    from wf.studio.pf_dsl import nodes
    raw = clone_tree(root(), summon=block)["raw"]
    summon = next(nodes(tree(raw), "CreateSummonsMultiball"))
    assert summon[3] == [{"min": 2147483647, "max": 2147483647}]


def test_caps_follow_multiball_active_program_and_ball_pf_configuration(summon_env):
    source, _, _ = summon_env
    from wf.caps.facts import table_signals
    from wf.caps.signals_v35 import custom_signals
    row = codec.parse_node(source.raw(BALL))[OLD_BALL]
    assert ("program", "battle/action/skill/mother_high") in list(table_signals(BALL, (OLD_BALL,), row))
    assert ("ref", ("master/skill/power_flip_action.orderedmap", "custom_pf")) in list(
        custom_signals("wfx_ball_pf_action_" + NEW_BALL, "custom_pf"))


def test_summon_inherits_same_draft_ability_weight_and_keeps_it_at_compile(summon_env):
    source, store, editor = summon_env
    from wf.studio.ability import AbilityEditor
    from test_studio_summon import ACTION
    from wf.studio.clone_tables import leaf
    from test_studio_summon import ordered
    skills = codec.parse_node(source.raw(ACTION))
    def valid_skill(row):
        cells = row.split(",")
        cells[3], cells[6] = "false", "0"
        return leaf([cells + ["0"] * (24 - len(cells))])
    source.view.files["common", ACTION] = ordered({key: ordered({level: valid_skill(row)
        for level, row in tiers.items()})
        for key, tiers in skills.items()})
    from wf.studio.source import StudioSource
    from wf.studio.summon import SummonEditor
    source = StudioSource(source.view)
    editor = SummonEditor(source, store=store)
    AbilityEditor(source, store=store).apply(CID, {"operations": [{
        "op": "set_cells", "table": "action_skill", "key": "mother_skill", "level": "3",
        "row": 0, "row_count": 1, "column_space": "native", "shared_ok": True,
        "cells": [{"column": 5, "old": "480", "new": "555"}]}]})
    editor.apply(CID, request())
    from wf.studio.ability import compile_ability_operations
    from wf.studio.summon import compile_summons
    draft = store.load(CID)
    previous = compile_ability_operations(source, store, draft)["client"]
    result = {**previous, **compile_summons(source, store, draft,
        members={("common", logical): raw for logical, raw in previous.items()})["client"]}
    assert flat(result[BALL], NEW_BALL)[0][11] == "555"
    assert codec.parse_node(result[ACTION])["mother_skill"]["3"].split(",")[5] == "555"

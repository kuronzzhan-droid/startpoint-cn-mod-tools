"""Skill refresh, text consistency, safety and same-draft summon regressions."""
import json
import pytest
import wf_quest_lib as codec

from test_studio_skill_template import (skill_env, CID, NEW_KEY, DSL, ACTION, CHARACTER, request,
                                       skill_tree, encode_tree, effect_files)  # noqa: F401
from test_studio_skill_template_core import root, cmd, area, Source
from wf.studio.skill_template_compile import compile_skill_template
from wf.studio.skill_template_validation import validate_tree
from wf.studio.skill_template_catalog import template_detail
from wf.studio.drafts import DraftError
from wf.studio.skill_template_text import TEXT


def test_refresh_after_source_drift_and_text_mirrors(skill_env, tmp_path):
    source, store, editor, official = skill_env
    editor.apply(CID, request())
    changed = skill_tree()
    changed[11][1][-1][1][6] = [{"min": 9, "max": 9}]
    official["common", DSL] = encode_tree(changed)
    with pytest.raises(DraftError, match="输入已变化"):
        compile_skill_template(source, store, store.load(CID))
    update = request(text={"1": {"name": "New skill", "description": "New description"}})
    assert editor.preview(CID, update)["ok"]
    editor.apply(CID, update)
    from wf.studio.deliver_bridge import compile_draft
    server = tmp_path / "server"
    for name in ("character", "character_text", "character_text_rank_p5b"):
        path = server / f"assets/cdndata/{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"keep": [["untouched"]]}', encoding="utf-8")
    members, mirrors, _, _, _ = compile_draft(source, store, store.load(CID), server_dir=server)
    from wf.balance.rows import split_leaf
    text = split_leaf(codec.parse_node(members["common", TEXT])[CID], TEXT)
    assert text[0][4:6] == ["New skill", "New description"]
    for name in ("character_text", "character_text_rank_p5b"):
        doc = json.loads(mirrors[f"assets/cdndata/{name}.json"])
        assert doc[CID] == text and doc["keep"] == [["untouched"]]
    assert json.loads(mirrors["assets/cdndata/character.json"])[CID][0][8] == NEW_KEY
    from wf.studio.ability import AbilityEditor
    ability = AbilityEditor(source, store=store)
    assert ability.read(CID)["slots"]["action_skill"] == NEW_KEY
    with pytest.raises(DraftError, match="模板已接管"):
        ability._state(CID, {})


def test_existing_ability_edit_remains_visible_before_template_takeover(skill_env):
    source, store, editor, _ = skill_env
    from wf.studio.ability import AbilityEditor
    ability = AbilityEditor(source, store=store)
    ability.apply(CID, {"operations": [{"op": "set_cells", "table": "action_skill", "key": "donor",
        "level": "1", "row": 0, "row_count": 1, "column_space": "native", "shared_ok": True,
        "cells": [{"column": 4, "old": "100", "new": "101"}]}]})
    from wf.studio.summon import _effective
    effective = _effective(source, store, store.load(CID))
    assert codec.parse_node(effective.raw(ACTION))["donor"]["1"].split(",")[4] == "101"
    editor.apply(CID, request())
    assert ability.read(CID)["slots"]["action_skill"] == NEW_KEY


def test_missing_element_context_is_uncloneable_not_catalog_error():
    source = Source()
    source.official["character"] = {}
    value = skill_tree()
    value[11][1][0][1][2] = ["ResolveByElement", "battle/effect/generic/demo", 255]
    for path in source.raws:
        source.raws[path] = encode_tree(value)
    detail = template_detail(source, "donor")
    assert detail["cloneable"] is False
    assert any(c["level"] == "error" for c in detail["tiers"][0]["checks"])


def test_target_effect_color_is_preferred_and_source_fallback_is_explicit(skill_env):
    _, _, editor, official = skill_env
    base = "battle/effect/generic/shine"
    value = skill_tree()
    value[11][1][0][1][2] = ["ResolveByElement", base, 255]
    official["common", DSL] = encode_tree(value)
    official.update(effect_files(directory=base + "/shine_yellow", name="shine_yellow"))
    result = editor.preview(CID, request(element=1))
    assert any(c["rule"] == "skill-template.effect-color" for c in result["checks"])
    assert result["summary"]["effectFamilies"][0]["source"].endswith("shine_yellow")
    official.update(effect_files(directory=base + "/shine_blue", name="shine_blue"))
    result = editor.preview(CID, request(element=1))
    assert not any(c["rule"] == "skill-template.effect-color" for c in result["checks"])
    assert result["summary"]["effectFamilies"][0]["source"].endswith("shine_blue")


@pytest.mark.parametrize("name,args", [("AddCombo", [[1]]), ("AddFeverPoint", [[1]]),
                                       ("CreateBarrier", [-17, [1], ["None"]])])
def test_additional_native_slv_slots_reject_scalar_arrays(name, args):
    with pytest.raises(ValueError, match="SLvValue"):
        validate_tree(root(cmd(name, *args)))


def test_callback_cd_coordinate_and_invalid_hit_target_are_rejected():
    value = root(area())
    nested = area(coord=["CD"], target=2)
    value[11][1][0][1][23][1].append(nested)
    with pytest.raises(ValueError, match="CD|坐标"):
        validate_tree(value)
    value = root(area(target=9999))
    with pytest.raises(ValueError):
        validate_tree(value)


def test_summon_and_template_joint_compile_from_one_draft(skill_env, tmp_path):
    source, store, editor, official = skill_env
    from test_studio_summon import fixture_files, MOTHER, NEW_BALL, request as ball_request
    from wf.studio.summon import SummonEditor
    fixture = fixture_files()
    for (kind, logical), raw in fixture.items():
        if logical in (CHARACTER, ACTION):
            existing = codec.parse_node(source.raw(logical))
            incoming = codec.parse_node(raw)
            source.view.files[kind, logical] = codec.build_node({**existing, **incoming})
        elif logical != TEXT:
            source.view.files[kind, logical] = raw
    prefix = "battle/effect/skill_unique/donor/shine"
    # Every animation shares the same synthetic texture, as an ordinary atlas family does.
    sheet = "battle/effect/skill_unique/donor/donor.atlas.amf3.deflate"
    from wf.studio.deliver_media import tree
    atlas = tree(official["common", sheet])
    for suffix in ("_ready_generation", "_ready_left", "_ready_right", "_appear", "_disappear"):
        assets = effect_files(name="shine" + suffix)
        atlas.extend(tree(assets["common", sheet]))
        official.update(assets)
    official["common", sheet] = encode_tree(atlas)
    source._raw.clear()
    ball = SummonEditor(source, store=store).apply(CID, ball_request())
    summon = {**ball["skillTemplate"]["summon"], "effectPrefix": prefix}
    assert editor.preview(CID, request(summon=summon))["ok"]
    editor.apply(CID, request(summon=summon))
    from wf.studio.skill_template_inputs import current_source
    effective = current_source(source, store, store.load(CID))
    members, _, _ = compile_skill_template(effective, store, store.load(CID), official_source=source)
    from wf.studio.pf_dsl import nodes
    program = next(raw for (_, path), raw in members.items() if path.endswith(".action.dsl.amf3.deflate"))
    assert next(nodes(tree(program), "CreateSummonsMultiball"))[2] == int(NEW_BALL)

"""M5: names are checked as names, all description tiers share one wording."""
import json

import pytest
import wf_quest_lib as codec

from test_m1_text import edit_for, workspace  # noqa: F401
from wf.text.edit import prepare_edit
from wf.text.model import ACTION_SKILL, TextWorkspace, cells, replace_cells
from wf.text.release import audit_workspace
from wf.text.standard import check_document


def test_name_c0_is_checked_by_character_and_whole_table(workspace):
    table = codec.parse_node(workspace.view.raw[ACTION_SKILL])
    row = cells(table["wolf"]["2"])
    row[0] = "月光之核+"
    table["wolf"]["2"] = replace_cells("", row)
    workspace.view.raw[ACTION_SKILL] = codec.build_node(table)
    current = TextWorkspace(workspace.view, workspace.server_path, workspace.rank_path)
    single = check_document(current.read("1"))
    assert any(f["rule"] == "text.standard.skill-name" and f["location"] == "action_skill.2.c0" for f in single)
    audit = audit_workspace(current)
    assert any(f["rule"] == "text.standard.skill-name" and f["location"] == "action_skill.wolf.2.c0"
               for f in audit["findings"])


def test_legal_skill_name_upgrade_suffixes_are_not_effect_separators(workspace):
    assert not any(f["state"] == "问题" and f["location"].endswith(".c0")
                   for f in check_document(workspace.read("1")))


def test_tier_wording_drift_rejected_even_when_individual_text_is_valid(workspace):
    doc = workspace.read("1")
    doc["action_skill"]["2"]["c1"] = "攻击敌人／赋予浮游效果"
    assert any(f["rule"] == "text.standard.skill-tier-wording" for f in check_document(doc))
    changes = {tier: {"c1": {"old": "攻击敌人", "new": pair["c1"]}}
               for tier, pair in doc["action_skill"].items()}
    with pytest.raises(ValueError, match="skill-tier-wording"):
        prepare_edit(workspace, edit_for(workspace, action_skill=changes))


def test_duration_and_stack_progression_keeps_same_wording(workspace):
    doc = workspace.read("1")
    for index, pair in enumerate(doc["action_skill"].values(), 1):
        pair["c1"] = f"赋予浮游效果（持续{index * 10}秒，最多{index}层）"
    assert not any(f["rule"] == "text.standard.skill-tier-wording" for f in check_document(doc))


def test_numeric_parts_of_effect_names_are_not_ignored(workspace):
    doc = workspace.read("1")
    for index, pair in enumerate(doc["action_skill"].values(), 1):
        pair["c1"] = f"赋予自身「模式{index}」"
    assert any(f["rule"] == "text.standard.skill-tier-wording" for f in check_document(doc))


def test_whole_table_catches_orphan_and_mirror_tier_drift(workspace):
    table = codec.parse_node(workspace.view.raw[ACTION_SKILL])
    table["orphan"] = {"1": replace_cells("", ["旧名", "攻击敌人"]),
                       "2": replace_cells("", ["旧名+", "追加浮游效果"])}
    workspace.view.raw[ACTION_SKILL] = codec.build_node(table)
    rank = json.loads(workspace.rank_path.read_bytes())
    rank["1"][0][7] = "追加浮游效果"
    workspace.rank_path.write_text(json.dumps(rank), "utf-8")
    result = audit_workspace(TextWorkspace(workspace.view, workspace.server_path, workspace.rank_path))
    locations = {f["location"] for f in result["findings"] if f["rule"] == "text.standard.skill-tier-wording"}
    assert {"action_skill.orphan", "character_text_rank_p5b.json.1"} <= locations

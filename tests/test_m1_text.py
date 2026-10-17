"""Synchronized edits must change the actual client fields and every mirror."""
import json

import pytest

import wf_quest_lib as codec
from wf.text import TextWorkspace, check_character
from wf.text.edit import prepare_edit, stage_edit
from wf.text.model import (ABILITY, ACTION_SKILL, CHARACTER, CHARACTER_TEXT, CUSTOM,
                           LEADER, cells, replace_cells, sha256)


class View:
    def __init__(self, tables):
        self.raw = {key: codec.build_node(value) for key, value in tables.items()}

    def read_raw(self, logical):
        return self.raw[logical], "fixture"


@pytest.fixture
def workspace(tmp_path):
    char = ["wolf"] + [""] * 36
    char[8], char[17], char[18], char[19] = "wolf", "1", "leader", "11"
    text = ["狼", "LANG", "这是一段角色介绍", "白狼骑士", "斩击", "攻击敌人", "斩击+", "攻击敌人", "斩击++", "攻击敌人", "队长", "声优"]
    tables = {CHARACTER: {"1": replace_cells("", char)},
              CHARACTER_TEXT: {"1": replace_cells("", text)},
              ACTION_SKILL: {"wolf": {str(i): replace_cells("", [f"斩击{'+'*(i-1)}", "攻击敌人", "unchanged"]) for i in (1, 2, 3)}},
              CUSTOM: {"change_skill_wolf": "额外赋予全体队员攻击力提升效果",
                       "desc_override_wolf_1": "自身攻击力提升", "shared_text": "共用描述"},
              ABILITY: {"11": "wolf_1,true,shared_text"}, LEADER: {"1": "wolf"}}
    server = tmp_path / "character_text.json"
    server.write_text(json.dumps({"1": [text], "untouched": [["保持"]]}, ensure_ascii=False), "utf-8")
    return TextWorkspace(View(tables), server)


def edit_for(workspace, **sections):
    return {"character_id": "1", "snapshot_sha256": workspace.read("1")["snapshot_sha256"], **sections}


def test_read_all_surfaces_title_is_c3(workspace):
    doc = workspace.read("1")
    assert doc["title"] == "白狼骑士" and doc["title_column"] == 3
    assert set(doc["action_skill"]) == {"1", "2", "3"}
    assert doc["desc_override"] == {"desc_override_wolf_1": "自身攻击力提升"}
    assert "shared_text" in doc["custom_ability_string"]
    assert doc["server_character_text"][0][2] == "这是一段角色介绍"


def test_three_tiers_names_descriptions_and_server_sync(workspace, tmp_path):
    before = workspace.server_path.read_bytes()
    operations = {tier: {field: {"old": value, "new": f"新{tier}{field}"}
                         for field, value in pair.items()}
                  for tier, pair in workspace.read("1")["action_skill"].items()}
    prepared = prepare_edit(workspace, edit_for(workspace, action_skill=operations))
    action = codec.parse_node(prepared["client"][ACTION_SKILL])
    ct = cells(codec.parse_node(prepared["client"][CHARACTER_TEXT])["1"])
    server = json.loads(prepared["server"])
    for tier in ("1", "2", "3"):
        row = cells(action["wolf"][tier])
        assert row[:2] == [f"新{tier}c0", f"新{tier}c1"]
        assert row[2] == "unchanged"
        assert ct[2+2*int(tier):4+2*int(tier)] == row[:2]
        assert server["1"][0][2+2*int(tier):4+2*int(tier)] == row[:2]
    assert server["untouched"] == [["保持"]]
    assert workspace.server_path.read_bytes() == before
    metadata = dict(id="text-1", name="文本", from_version="1.4.1", to_version="1.4.2", slug="text", created_at="2026-10-17")
    result = stage_edit(prepared, tmp_path / "staged", metadata)
    manifest = json.loads(result.read_text("utf-8"))
    assert manifest["schema"] == "wf-change-set/1"
    assert len(manifest["members"]) == 2 and len(manifest["server_changes"]) == 1
    assert manifest["server_changes"][0]["before_sha256"] == sha256(before)
    from wf.deliver.changeset import load_changeset
    loaded, members, staged_server = load_changeset(result)
    assert loaded == manifest and len(members) == 2
    assert json.loads(staged_server["assets/cdndata/character_text.json"]) == server
    assert workspace.server_path.read_bytes() == before
    with pytest.raises(FileExistsError):
        stage_edit(prepared, result.parent, metadata)


def test_custom_and_override_write_exact_csv(workspace):
    prepared = prepare_edit(workspace, edit_for(workspace,
        custom_ability_string={"shared_text": {"old": "共用描述", "new": "第一行,带逗号\n第二行"}},
        desc_override={"desc_override_wolf_1": {"old": "自身攻击力提升", "new": "自身防御力提升"}}))
    table = codec.parse_node(prepared["client"][CUSTOM])
    assert cells(table["shared_text"]) == ["第一行,带逗号\n第二行"]
    assert cells(table["desc_override_wolf_1"]) == ["自身防御力提升"]


def test_title_sync_does_not_overwrite_biography(workspace):
    prepared = prepare_edit(workspace, edit_for(workspace, character_text={"3": {"old": "白狼骑士", "new": "月下骑士"}}))
    row = cells(codec.parse_node(prepared["client"][CHARACTER_TEXT])["1"])
    assert row[2:4] == ["这是一段角色介绍", "月下骑士"]
    assert json.loads(prepared["server"])["1"][0][3] == "月下骑士"


def test_reject_wrong_old_partial_and_stale_snapshot(workspace):
    with pytest.raises(ValueError, match="every existing"):
        prepare_edit(workspace, edit_for(workspace, action_skill={"1": {"c1": {"old": "攻击敌人", "new": "新"}}}))
    with pytest.raises(ValueError, match="old-value"):
        prepare_edit(workspace, edit_for(workspace, character_text={"3": {"old": "错误", "new": "新"}}))
    edit = edit_for(workspace, character_text={"3": {"old": "白狼骑士", "new": "新"}})
    edit["snapshot_sha256"] = "bad"
    with pytest.raises(ValueError, match="snapshot changed"):
        prepare_edit(workspace, edit)
    with pytest.raises(ValueError, match="through action_skill"):
        prepare_edit(workspace, edit_for(workspace, character_text={"5": {"old": "攻击敌人", "new": "新"}}))


def test_reject_missing_server_and_external_output(workspace, tmp_path):
    no_server = TextWorkspace(workspace.view)
    with pytest.raises(ValueError, match="synchronized"):
        prepare_edit(no_server, edit_for(no_server, character_text={"3": {"old": "白狼骑士", "new": "新"}}))
    prepared = prepare_edit(workspace, edit_for(workspace, character_text={"3": {"old": "白狼骑士", "new": "新"}}))
    with pytest.raises(PermissionError):
        stage_edit(prepared, tmp_path.anchor + "outside-text-output", {})


@pytest.mark.parametrize("bad", ["生命值 100% 以下时攻击力提升", "HP１００％以下", "生命值100.0%及以下"])
def test_tautology_rule_cannot_be_deleted(workspace, bad):
    doc = workspace.read("1")
    doc["desc_override"]["desc_override_wolf_1"] = bad
    assert any(x["rule"] == "text.tautology" and x["state"] == "问题" for x in check_character(doc))


def test_name_and_duplicate_enhancement_rules(workspace):
    doc = workspace.read("1")
    doc["action_skill"]["1"]["c0"] = "月光之核"
    doc["action_skill"]["2"]["c1"] = "攻击敌人／额外赋予全体队员攻击力提升效果"
    results = check_character(doc)
    assert any(x["rule"] == "text.core_name" for x in results)
    assert any(x["rule"] == "text.duplicate_enhancement" for x in results)
    doc["action_skill"]["2"]["c1"] = "生命值80%以下时攻击力提升"
    assert not any(x["rule"] == "text.tautology" for x in check_character(doc))


def test_new_rule_failure_prevents_staging(workspace):
    with pytest.raises(ValueError, match="text rules failed"):
        prepare_edit(workspace, edit_for(workspace, character_text={"3": {"old": "白狼骑士", "new": "白狼之核"}}))


def test_server_drift_after_prepare_creates_no_output(workspace, tmp_path):
    prepared = prepare_edit(workspace, edit_for(workspace, character_text={"3": {"old": "白狼骑士", "new": "新"}}))
    workspace.server_path.write_text("{}", "utf-8")
    metadata = dict(id="text-1", name="文本", from_version="1.4.1", to_version="1.4.2", slug="text", created_at="2026-10-17")
    with pytest.raises(ValueError, match="changed during edit"):
        stage_edit(prepared, tmp_path / "staged", metadata)
    assert not (tmp_path / "staged").exists()


def test_shared_custom_key_edit_requires_ownership_decision(workspace):
    char = cells(workspace.table(CHARACTER)["1"])
    char[0], char[8], char[19] = "other", "other", "22"
    workspace.view.raw[CHARACTER] = codec.build_node({"1": workspace.table(CHARACTER)["1"], "2": replace_cells("", char)})
    workspace.view.raw[ABILITY] = codec.build_node({"11": "wolf_1,true,shared_text", "22": "other_1,true,shared_text"})
    workspace = TextWorkspace(workspace.view, workspace.server_path)
    with pytest.raises(ValueError, match="shared custom text"):
        prepare_edit(workspace, edit_for(workspace, custom_ability_string={"shared_text": {"old": "共用描述", "new": "新"}}))


def test_semantic_overlap_is_pending_not_hard_failure(workspace):
    doc = workspace.read("1")
    doc["action_skill"]["1"]["c1"] = "对敌人造成伤害／队伍攻击力提升"
    doc["desc_override"]["desc_override_wolf_1"] = "强化『斩击』的攻击力提升效果"
    results = check_character(doc)
    assert any(x["state"] == "待验证" and x["evidence"]["key"] == "desc_override_wolf_1" for x in results)


def test_program_string_reference_and_variant_ownership(workspace):
    tables = {logical: codec.parse_node(raw) for logical, raw in workspace.view.raw.items()}
    tables[ABILITY]["11"] += ",battle/action/ability_skill_wolf_pf$ability_skill_wolf_pf"
    tables[CUSTOM]["ability_skill_wolf_pf"] = "召唤追击"
    tables[CUSTOM]["change_skill_wolf_summer"] = "夏日强化"
    variant = cells(tables[CHARACTER]["1"])
    variant[0], variant[8] = "wolf_summer", "wolf_summer"
    tables[CHARACTER]["2"] = replace_cells("", variant)
    workspace = TextWorkspace(View(tables), workspace.server_path)
    keys = workspace.custom_keys("1")
    assert "ability_skill_wolf_pf" in keys
    assert "change_skill_wolf_summer" not in keys


@pytest.mark.parametrize("section,key,new_prefix", [
    ("custom_ability_string", "change_skill_wolf", ""),
    ("desc_override", "desc_override_wolf_1", "强化『斩击』："),
])
def test_editing_enhancement_cannot_introduce_cross_field_duplicate(workspace, section, key, new_prefix):
    effect = "对前方的敌人造成火属性伤害"
    workspace.view.raw[ACTION_SKILL] = codec.build_node({"wolf": {
        str(tier): replace_cells("", [f"斩击{tier}", effect, "unchanged"])
        for tier in (1, 2, 3)}})
    workspace = TextWorkspace(workspace.view, workspace.server_path)
    before = workspace.server_path.read_bytes()
    old = workspace.read("1")[section][key]
    with pytest.raises(ValueError, match="text.duplicate_enhancement"):
        prepare_edit(workspace, edit_for(workspace, **{
            section: {key: {"old": old, "new": new_prefix + effect}}}))
    assert workspace.server_path.read_bytes() == before


def test_noop_is_rejected_before_producing_changeset(workspace):
    with pytest.raises(ValueError, match="no actual client changes"):
        prepare_edit(workspace, edit_for(workspace,
            character_text={"3": {"old": "白狼骑士", "new": "白狼骑士"}}))
    custom = codec.parse_node(workspace.view.raw[CUSTOM])
    custom["shared_text"] = '"共用描述"\n'
    workspace.view.raw[CUSTOM] = codec.build_node(custom)
    workspace = TextWorkspace(workspace.view, workspace.server_path)
    with pytest.raises(ValueError, match="no actual client changes"):
        prepare_edit(workspace, edit_for(workspace,
            custom_ability_string={"shared_text": {"old": "共用描述", "new": "共用描述"}}))


def test_unrelated_existing_cross_field_problem_is_retained(workspace):
    effect = "对前方的敌人造成火属性伤害"
    workspace.view.raw[ACTION_SKILL] = codec.build_node({"wolf": {
        str(tier): replace_cells("", [f"斩击{tier}", effect, "unchanged"])
        for tier in (1, 2, 3)}})
    custom = codec.parse_node(workspace.view.raw[CUSTOM])
    custom["change_skill_wolf"] = effect
    workspace.view.raw[CUSTOM] = codec.build_node(custom)
    workspace = TextWorkspace(workspace.view, workspace.server_path)
    prepared = prepare_edit(workspace, edit_for(workspace,
        character_text={"3": {"old": "白狼骑士", "new": "月下骑士"}}))
    assert sum(f["rule"] == "text.duplicate_enhancement" for f in prepared["checks"]) == 3

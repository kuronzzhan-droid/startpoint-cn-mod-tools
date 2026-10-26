"""D3/D4 counterexamples use real slot c0/c1, including misleading names."""
from types import SimpleNamespace

import pytest
import wf_quest_lib as codec

from test_m1_text import View, edit_for, workspace  # noqa: F401
from wf.text.draft import check_compiled_text
from wf.text.edit import prepare_edit
from wf.text.markup import MAIN_ICON
from wf.text.model import ABILITY, CHARACTER, CUSTOM, LEADER, TextWorkspace, cells, replace_cells
from wf.text.release import audit_workspace
from wf.text.standard import check_document, check_entry


def changed(workspace, updates):
    tables = {key: codec.parse_node(raw) for key, raw in workspace.view.raw.items()}
    for table, changes in updates.items():
        tables[table].update(changes)
    return TextWorkspace(View(tables), workspace.server_path, workspace.rank_path)


def rules(findings):
    return {item["rule"] for item in findings}


def test_exact_c0_finds_139985_and_arbitrary_ability_keys(workspace):
    character = cells(workspace.table(CHARACTER)["1"])
    character[0], character[17], character[19] = "unrelated", "139985", "1399851"
    current = changed(workspace, {
        CHARACTER: {"139985": replace_cells("", character)},
        LEADER: {"139985": "lady_android_halloween,0"},
        ABILITY: {"1399851": "unrelated_slot,false"},
        CUSTOM: {"desc_override_lady_android_halloween": "自身为队长时，自身攻击力+100%",
                 "desc_override_unrelated_slot": "泽赫尔为队长时，自身攻击力+10%"}})
    # No usable skill/text row for the new ID is required to audit the table.
    report = audit_workspace(current)
    finding = next(item for item in report["findings"] if item["rule"] == "text.standard.leader-slot")
    assert finding["location"] == "desc_override.desc_override_lady_android_halloween"
    assert finding["evidence"]["slots"][0]["key"] == "139985"
    assert finding["character_ids"] == ["139985"]
    assert "text.standard.leader-relocation" in rules(report["findings"])
    assert "text.standard.main-icon" in rules(report["findings"])


def test_character_snapshot_resolves_exact_slot_and_edit_gate(workspace):
    current = changed(workspace, {LEADER: {"1": "lady_android_halloween,0"},
        CUSTOM: {"desc_override_lady_android_halloween": "自身攻击力+100%"}})
    document = current.read("1")
    key = "desc_override_lady_android_halloween"
    assert document["override_slots"][key][0]["kind"] == "leader"
    document["desc_override"][key] = "自身为队长时，自身攻击力+100%"
    assert "text.standard.leader-slot" in rules(check_document(document))
    with pytest.raises(ValueError, match="text.standard.leader-slot"):
        prepare_edit(current, edit_for(current, desc_override={key: {
            "old": "自身攻击力+100%", "new": document["desc_override"][key]}}))


def test_no_suffix_inference_and_all_overrides_forbid_self_leader():
    assert not check_entry("desc_override_looks_like_ability_3", "泽赫尔为队长时，攻击力+10%")
    for key in ("desc_override_anything", "desc_override_hero_3", "desc_override_orphan"):
        assert "text.standard.leader-slot" in rules(check_entry(key, "自身为队长时，自身攻击力+10%"))
    found = check_entry("desc_override_misleading_leader", "担任队长时，自身攻击力+10%",
                        slots=[{"kind": "ability"}])
    assert "text.standard.leader-relocation" in rules(found)


@pytest.mark.parametrize("bad", [
    "自身攻击力+10%", "<icon id='main'>  自身攻击力+10%",
    "  <icon id='main'>  自身攻击力+10%", " <icon id='main'> 自身攻击力+10%",
    " <icon id='main'>   自身攻击力+10%", ' <icon id="main">  自身攻击力+10%',
    MAIN_ICON + "自身攻击力+10%\n自身技能伤害+20%", "Ⓜ 自身攻击力+10%",
])
def test_every_main_limited_line_requires_exact_markup(bad):
    assert "text.standard.main-icon" in rules(check_entry("desc_override_unusual", bad,
        slots=[{"kind": "ability", "main_only": True}]))


def test_correct_main_markup_nonmain_and_leader_slots():
    good = MAIN_ICON + "自身攻击力+10%\n" + MAIN_ICON + "自身技能伤害+20%"
    assert not check_entry("desc_override_x", good, slots=[{"kind": "ability", "main_only": True}])
    for slot in ({"kind": "leader"}, {"kind": "ability", "main_only": False}):
        assert not check_entry("desc_override_x", "自身攻击力+10%", slots=[slot])
    mixed = [{"kind": "ability", "key": "1", "main_only": flag} for flag in (False, True)]
    assert not check_entry("desc_override_x", "自身攻击力+10%\n" + MAIN_ICON + "自身技能伤害+20%", slots=mixed)
    from wf_featured_main_ability import MAIN
    assert MAIN_ICON == MAIN


@pytest.mark.parametrize("text,rule", [
    ("自身攻击力+50%（觉醒后 100%）", "max-level"),
    ("自身攻击力+50%(觉醒后100%)", "max-level"),
    ("Ⓜ自身攻击力+50%", "literal-main-icon"),
    ("自身攻击力+50%／自身技能伤害+50%", "compressed-lines"),
    ("自身（攻击力+50%／技能伤害+50%）", "compressed-lines"),
])
def test_d4_each_rejected_form(text, rule):
    assert "text.standard." + rule in rules(check_entry("desc_override_x", text))


def test_slash_skill_separator_and_documented_enumeration_are_preserved():
    assert not check_entry("skill", "造成火属性伤害／赋予浮游效果", surface="action_skill")
    assert not check_entry("desc_override_x", "造成自身攻击力2倍的六属性能力伤害（火／水／雷／风／光／暗各结算1次）")
    for text in ("其他雷／风属性角色发动技能时，自身攻击力+50%",
                 "自身为基诺维／杰拉德／凯尔时，攻击力+150%",
                 "每次发动技能，全部伤害类型（直接攻击／技能／能力／强化弹射）+44%"):
        assert "text.standard.compressed-lines" not in rules(check_entry("desc_override_x", text))


def test_compiled_readback_catches_raw_override_and_ability_changes(workspace):
    current = changed(workspace, {LEADER: {"1": "lady_android_halloween,0"},
        CUSTOM: {"desc_override_lady_android_halloween": "自身攻击力+100%"}})
    custom = dict(current.table(CUSTOM))
    custom["desc_override_lady_android_halloween"] = "自身为队长时，自身攻击力+100%"
    members = {("common", CUSTOM): codec.build_node(custom)}
    result = check_compiled_text(SimpleNamespace(view=current.view), members)
    assert any(item["blocking"] and item["rule"] == "text.standard.leader-slot" for item in result)
    ability = dict(current.table(ABILITY))
    ability["11"] = "wolf_1,false,shared_text"
    result = check_compiled_text(SimpleNamespace(view=current.view), {("common", ABILITY): codec.build_node(ability)})
    assert any(item["blocking"] and item["rule"] == "text.standard.main-icon" for item in result)


def test_compiled_readback_keeps_unrelated_history_nonblocking(workspace):
    current = changed(workspace, {CUSTOM: {"desc_override_orphan": "自身为队长时，攻击力+10%"}})
    ability = dict(current.table(ABILITY))
    ability["11"] += ",unrelated"
    result = check_compiled_text(SimpleNamespace(view=current.view), {("common", ABILITY): codec.build_node(ability)})
    assert result and all(not item["blocking"] for item in result)


def test_draft_compilation_rechecks_bytes_despite_saved_green_checks(workspace, monkeypatch):
    from wf.studio.deliver_bridge import compile_draft
    from wf.studio.drafts import DraftError
    import wf.studio.deliver_media
    current = changed(workspace, {LEADER: {"1": "lady_android_halloween,0"},
        CUSTOM: {"desc_override_lady_android_halloween": "自身攻击力+100%"}})
    strings = dict(current.table(CUSTOM))
    strings["desc_override_lady_android_halloween"] = "自身为队长时，自身攻击力+100%"
    monkeypatch.setattr(wf.studio.deliver_media, "compile_media", lambda *args: SimpleNamespace(
        members={("common", CUSTOM): codec.build_node(strings)}, assertions=[], checks=[]))
    with pytest.raises(DraftError, match="text.standard.leader-slot"):
        compile_draft(SimpleNamespace(view=current.view), None, {"changes": []})

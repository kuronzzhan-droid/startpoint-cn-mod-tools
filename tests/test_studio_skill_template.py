"""Template editor, reservations, drift and real local delivery on synthetic bytes."""
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest
import wf_quest_lib as codec
import wf_mod_tool as core

from wf.deliver.changeset import member_name
from wf.studio.clone_tables import leaf, rows
from wf.studio.deliver_media import encode_tree, tree
from wf.studio.drafts import DraftError, DraftStore
from wf.studio.skill_template import SkillTemplateEditor
from wf.studio.skill_template_compile import compile_skill_template
from wf.studio.skill_template_inputs import ACTION, CHARACTER, Inputs
from wf.studio.source import StudioSource
from test_studio_character_clone import View, ordered, env as clone_env, request as clone_request, NEW, CODE
from test_studio_skill_template_core import fixture as skill_tree, root, attack
from test_studio_skill_template_effects import fixture as effect_files
from test_m1_balance import valid_row

CID, OTHER = "199001", "199002"
PROGRAM = "battle/action/skill/donor$donor_1"
DSL = PROGRAM + ".action.dsl.amf3.deflate"
NEW_KEY = "studio_skill_demo"


def action_row():
    row = [""] * 24
    row[0:9] = ["Official skill", "Original description", "", "true", "100", "100", "0", PROGRAM, "0"]
    row[16] = "0"
    return row


def character(code, identity):
    row = [""] * 37
    row[0], row[2], row[3], row[6], row[8], row[26], row[27] = code, "5", "2", "1", "donor", "Attacker", identity
    return row


def request(**extra):
    return {"source": {"key": "donor"}, "newKey": NEW_KEY, "scale": 2, "element": 2,
            "recolor": {"hueShift": 120}, **extra}


def official_reader(monkeypatch, members):
    original_raw = StudioSource.raw

    def raw(self, logical, official=False):
        return members.get(("common", logical)) if official else original_raw(self, logical)

    monkeypatch.setattr(StudioSource, "raw", raw)
    monkeypatch.setattr(StudioSource, "read_official_root", lambda self, root, logical:
                        members.get((root, logical)), raising=False)


@pytest.fixture
def skill_env(tmp_path, monkeypatch):
    donor = character("donor", "151001")
    official = effect_files(name="shine")
    official.update({("common", CHARACTER): ordered({"151001": leaf([donor])}),
                     ("common", ACTION): ordered({"donor": ordered({"1": leaf([action_row()])})}),
                     ("common", DSL): encode_tree(skill_tree())})
    current = dict(official)
    current["common", CHARACTER] = ordered({CID: leaf([character("new_hero", CID)]),
                                            OTHER: leaf([character("another_hero", OTHER)]),
                                            "151001": leaf([donor])})
    live_row = action_row()
    live_row[0] = "Current modified skill"
    current["common", ACTION] = ordered({"donor": ordered({"1": leaf([live_row])}),
                                        "unrelated": ordered({"1": leaf([action_row()])})})
    current["common", DSL] = encode_tree(root(attack(999)))
    current["common", "master/string/custom_ability_string.orderedmap"] = ordered({"keep": leaf([["keep"]])})
    ability_row = valid_row("fixture_ability")
    current["common", "master/ability/ability.orderedmap"] = ordered({"1": leaf([ability_row])})
    current["common", "master/ability/leader_ability.orderedmap"] = ordered({"1": leaf([ability_row[:1] + ability_row[3:]])})
    official_reader(monkeypatch, official)
    source = StudioSource(View(current))
    store = DraftStore(tmp_path / "drafts")
    return source, store, SkillTemplateEditor(source, store=store), official


def test_preview_is_memory_only_and_official_donor_wins_over_current(skill_env):
    source, store, editor, official = skill_env
    before, official_before = dict(source.view.files), dict(official)
    result = editor.preview(CID, request())
    assert result["ok"] and result["preview"] and result["buildable"]
    assert result["summary"]["damageNodeCount"] == 2
    assert result["summary"]["levels"][0]["damageNodes"][0]["coefficient"] == [{"min": 4, "max": 6}]
    assert result["reservations"] == {"action_skill": [NEW_KEY]}
    assert not store.root.exists()
    assert source.view.files == before and official == official_before


def test_apply_compiles_compressed_new_rows_preserving_every_old_key_byte(skill_env):
    source, store, editor, official = skill_env
    before = dict(source.view.files)
    result = editor.apply(CID, request())
    draft = store.load(CID)
    assert draft["changes"][0]["kind"] == "skill_template"
    assert draft["changes"][0]["params"]["reservations"] == {"action_skill": [NEW_KEY]}
    members, changes, checks = compile_skill_template(source, store, draft)
    old_action = rows(before["common", ACTION])
    new_action = rows(members["common", ACTION])
    assert all(new_action[key] == value for key, value in old_action.items())
    old_chars, new_chars = rows(before["common", CHARACTER]), rows(members["common", CHARACTER])
    assert all(new_chars[key] == value for key, value in old_chars.items() if key != CID)
    imported = codec.parse_node(members["common", ACTION])[NEW_KEY]["1"]
    assert imported.startswith("Official skill,")
    assert "battle/action/skill/action/rare5/new_hero$" in imported
    nested = rows(new_action[NEW_KEY])
    assert nested["1"][:1] == b"x"  # zlib-wrapped CSV leaf, not an uncompressed row.
    assert source.view.files == before and result["runtime"] == "未执行"
    assert changes[0]["newKey"] == NEW_KEY and checks


def test_foreign_reservation_and_existing_key_are_rejected_before_write(skill_env):
    _, store, editor, _ = skill_env
    editor.apply(CID, request())
    with pytest.raises(DraftError, match="占用|预留"):
        editor.apply(OTHER, request())
    assert store.load(OTHER) is None
    with pytest.raises(DraftError, match="占用|预留"):
        editor.preview(OTHER, request(newKey="donor"))


def test_own_template_exception_cannot_bypass_a_top_level_reservation(skill_env):
    _, store, editor, _ = skill_env
    editor.apply(CID, request())
    draft = store.load(CID)
    draft["reservations"] = {"action_skill": [NEW_KEY]}
    store.restore(CID, draft)
    with pytest.raises(DraftError, match="其他改动预留"):
        editor.preview(CID, request())


def test_official_input_assertion_reads_through_studio_raw_cache(monkeypatch):
    logical = "battle/action/skill/donor.action.dsl.amf3.deflate"
    digest = core.sha1_path(logical)
    rel = digest[:2] + "/" + digest[2:]
    assets = {("common", rel): b"first official bytes"}
    baseline = SimpleNamespace(get=lambda root, name: assets.get((root, name)), archives=lambda root: ["fixture"])
    source = StudioSource(View({}))
    monkeypatch.setattr(source, "_official", lambda: baseline)
    assert source.raw(logical, official=True) == b"first official bytes"
    inputs = Inputs(source, source)
    inputs.read(logical, official=True)
    expected = dict(inputs.hashes)
    assets["common", rel] = b"changed official bytes"
    assert source.raw(logical, official=True) == b"first official bytes"  # demonstrate the real cache boundary.
    with pytest.raises(DraftError, match="输入已变化"):
        inputs.verify(expected)


def test_reapply_replaces_one_change_then_revert_releases_reservation(skill_env):
    _, store, editor, _ = skill_env
    first = editor.apply(CID, request())
    second = editor.apply(CID, request(scale=3))
    assert len(second["changeset"]["changes"]) == 1
    assert second["changeset"]["revision"] > first["changeset"]["revision"]
    assert second["changeset"]["changes"][0]["params"]["request"]["scale"] == 3
    store.revert(CID, second["change"]["id"])
    assert editor.preview(OTHER, request())["ok"]


def test_retargeting_releases_retired_output_dependencies(skill_env):
    source, store, editor, _ = skill_env
    first = editor.apply(CID, request())
    old_target = first["summary"]["levels"][0]["logical"]
    second = editor.apply(CID, request(newKey="replacement_skill"))
    hashes = second["change"]["params"]["inputs"]
    assert f"current:common:{old_target}" not in hashes
    new_target = second["summary"]["levels"][0]["logical"]
    assert hashes[f"current:common:{new_target}"] is None
    source.view.files["common", old_target] = encode_tree(root(attack()))
    source._raw.clear()
    members, _, _ = compile_skill_template(source, store, store.load(CID))
    assert ("common", old_target) not in members
    assert ("common", new_target) in members


def test_failed_reapply_keeps_saved_changeset_bytes_and_revision(skill_env):
    _, store, editor, _ = skill_env
    saved = editor.apply(CID, request())
    path = store.directory(CID) / "changeset.json"
    before = path.read_bytes()
    with pytest.raises(DraftError, match="占用|预留"):
        editor.apply(CID, request(newKey="donor"))
    assert path.read_bytes() == before
    assert store.load(CID)["revision"] == saved["changeset"]["revision"]


@pytest.mark.parametrize("scope,logical", [("official", DSL), ("official", ACTION),
                                          ("current", CHARACTER), ("current", ACTION)])
def test_saved_draft_rejects_source_drift(skill_env, scope, logical):
    source, store, editor, official = skill_env
    editor.apply(CID, request())
    data = official if scope == "official" else source.view.files
    data["common", logical] += b"changed"
    source._raw.clear()
    with pytest.raises(DraftError, match="输入已变化"):
        compile_skill_template(source, store, store.load(CID))


def test_missing_official_art_never_falls_back_to_current_view(skill_env):
    source, store, editor, official = skill_env
    logical = "battle/effect/skill_unique/donor/donor.png"
    assert source.raw(logical)
    del official["common", logical]
    with pytest.raises(DraftError, match="依赖缺失"):
        editor.apply(CID, request())
    assert store.load(CID) is None


def test_preview_rejects_cached_catalog_row_after_official_table_changes(skill_env):
    source, store, editor, official = skill_env
    source.table("skill", official=True)  # Catalogue is already cached in this HTTP process.
    changed = action_row()
    changed[0] = "A changed official name"
    official["common", ACTION] = ordered({"donor": ordered({"1": leaf([changed])})})
    with pytest.raises(DraftError, match="目录与 action_skill 行不一致"):
        editor.apply(CID, request())
    assert not store.root.exists()


def test_editor_accepts_native_ability_level_coefficients_without_base_minmax(skill_env):
    _, store, editor, official = skill_env
    value = root(attack())
    value[11][1][0][1][6] = [{"alv_min": 2, "alv_max": 4}]
    official["common", DSL] = encode_tree(value)
    result = editor.preview(CID, request(nodeCoefficients={
        "1": {"/11/1/0/1": [{"alv_min": 7, "alv_max": 9}]}}))
    assert result["summary"]["levels"][0]["damageNodes"][0]["coefficient"] == [{"alv_min": 7, "alv_max": 9}]
    assert not store.root.exists()


def test_saved_absent_destination_cannot_be_overwritten_after_new_resource_appears(skill_env):
    source, store, editor, _ = skill_env
    result = editor.apply(CID, request())
    generated = result["summary"]["levels"][0]["logical"]
    source.view.files["common", generated] = encode_tree(root(attack()))
    source._raw.clear()
    with pytest.raises(DraftError, match="输入已变化"):
        compile_skill_template(source, store, store.load(CID))


def test_real_build_draft_uses_standard_delivery_and_pr26_reports(skill_env, tmp_path):
    from wf.view import ManifestView
    from wf.studio.deliver_bridge import build_draft

    source, store, _, _ = skill_env
    active = tmp_path / "archives"
    active.mkdir()
    archive = active / "pinball-1.4.131-1.4.233-1-fixture.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for (root_name, logical), raw in source.view.files.items():
            bundle.writestr(member_name(root_name, logical), raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.233", "patches": [
        {"version": "1.4.233", "depends_on": "1.4.131", "chain": [archive.name], "type": "patch"}]}), encoding="utf-8")
    base = tmp_path / "store"
    base.mkdir()
    view = ManifestView("1.4.233", store=base, manifest=manifest, search_dirs=[active])
    selected = StudioSource(view)
    editor = SkillTemplateEditor(selected, store=store)
    result = editor.apply(CID, request())
    pathlist = tmp_path / "paths.txt"
    logicals = {item["logical"] for item in result["summary"]["files"]}
    logicals.update(logical for _, logical in source.view.files)
    pathlist.write_text("\n".join(sorted(logicals)), encoding="utf-8")
    delivered = build_draft(CID, from_version="1.4.233", to_version="1.4.234", out=tmp_path / "build",
                            store=store, baseline_view=view, pathlist=pathlist, allow_unknown_client=True)
    assert delivered["ok"], json.dumps(delivered, ensure_ascii=False, indent=2)
    assert {"bundleCheck", "keyDiff", "iconAlpha", "clientExtensions"} <= delivered.keys()
    delivery = Path(delivered["delivery"])
    assert (delivery / "delivery-manifest.json").is_file()
    assert delivered["deviceValidation"] == "未执行"


def test_character_clone_and_skill_template_compile_together(clone_env, monkeypatch):
    from wf.studio.character_clone import clone
    from wf.studio.deliver_bridge import compile_draft

    source, store, ops, server = clone_env
    donor_row = action_row()
    donor_row[7] = "battle/action/skill/mother"
    source.view.files["common", ACTION] = ordered({"mother_skill": ordered({"1": leaf([donor_row])})})
    source.view.files["common", donor_row[7] + ".action.dsl.amf3.deflate"] = encode_tree(skill_tree())
    source.view.files.update(effect_files(name="shine"))
    official_reader(monkeypatch, dict(source.view.files))
    before = dict(source.view.files)
    cloned = clone(ops, clone_request(), server_dir=server)
    clone_file_entries = cloned["changeset"]["changes"][0]["files"]
    editor = SkillTemplateEditor(source, store=store, server_dir=server)
    # A cloned action key is still occupied even though it belongs to this draft.
    with pytest.raises(DraftError, match="占用|预留"):
        editor.preview(NEW, request(source={"key": "mother_skill"}, newKey=CODE))
    result = editor.apply(NEW, request(source={"key": "mother_skill"}))
    assert {change["kind"] for change in result["changeset"]["changes"]} == {"character_clone", "skill_template"}
    members, servers, preimages, changes, checks = compile_draft(source, store, store.load(NEW), server_dir=server)
    from wf.balance.rows import split_leaf
    row = split_leaf(codec.parse_node(members["common", CHARACTER])[NEW], "character")[0]
    assert row[0] == CODE and row[8] == NEW_KEY
    assert NEW_KEY in codec.parse_node(members["common", ACTION])
    assert CODE in codec.parse_node(members["common", ACTION])  # clone's original row remains intact.
    assert len(servers) == len(preimages) == 5
    assert {change["kind"] for change in changes} == {"character_clone", "skill_template"}
    assert all(store.read_file(NEW, entry["draft"]) is not None for entry in clone_file_entries)
    assert source.view.files == before and not any(check.get("blocking") for check in checks)
    saved = store.load(NEW)
    saved["changes"][0]["params"]["reservations"] = {"action_skill": [NEW_KEY]}
    store.restore(NEW, saved)
    with pytest.raises(DraftError, match="其他改动预留"):
        editor.preview(NEW, request(source={"key": "mother_skill"}))

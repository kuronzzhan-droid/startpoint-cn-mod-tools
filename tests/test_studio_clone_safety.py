"""Clone preflight, independent ability keys and complete server mirror guards."""
import json
import zlib
from types import SimpleNamespace

import pytest
import wf_mod_tool as core
from wf.deliver.json_merge import _json_spans
from wf.deliver.key_guard import check_shared_keys
from wf.studio.character_clone import SERVER_FILES, clone, clone_members, compile_clone
from wf.studio.character_routes import CharacterRoutes
from wf.studio.clone_tables import T, leaf, rows
from wf.studio.drafts import DraftError
from wf.studio.pixel_workshop import family_paths
from test_studio_character_clone import env, OLD, NEW, CODE, ordered, request


def change_character(source, column, value):
    table = source.table("character")
    row = list(table[OLD][0])
    row[column] = value
    source.view.files["common", T.CHAR] = ordered({OLD: leaf([row])})
    source._tables.clear()
    source._raw.clear()


@pytest.mark.parametrize("rarity", [1, 2, 3])
def test_low_rarity_has_37_statuses_and_four_inapplicable_special_assets(env, rarity):
    source, store, ops, server = env
    change_character(source, 2, str(rarity))
    for logical in family_paths("mother", "special"):
        source.view.files.pop(("common", logical))
    result = clone(ops, request())
    assert result["buildable"] and len(result["assets"]) == 37
    special = [item for item in result["assets"] if item["logical"] in family_paths(CODE, "special")]
    assert len(special) == 4 and all(item["status"] == "not_applicable" for item in special)
    assert len(compile_clone(source, store, store.load(NEW), server_dir=server)[1]) == 5


def test_preview_plans_tables_and_assets_without_writing(env):
    source, store, ops, server = env
    before = {str(path.relative_to(server)): path.read_bytes() for path in server.rglob("*.json")}
    baseline = dict(source.view.files)
    response = CharacterRoutes(SimpleNamespace(ops=ops), server).clone({"preview": ["true"]}, request())
    result = json.loads(response.body)
    assert response.status == 200 and result["preview"] and result["buildable"]
    assert len(result["assets"]) == 37 and not store.root.exists()
    by_table = {item["logical"]: item for item in result["tables"]}
    assert by_table[T.CHAR]["addedKeys"] == [NEW]
    assert by_table[T.LEADER]["addedKeys"] == [NEW]
    assert by_table[T.ABILITY]["addedKeys"] == [NEW + str(i) for i in range(1, 7)]
    assert all(item["sha256"] and item["size"] > 0 for item in result["tables"])
    assert {item["target"] for item in result["serverTables"]} == set(SERVER_FILES)
    assert all(item["baselineVerified"] and item["beforeSha256"] and item["sha256"]
               for item in result["serverTables"])
    assert all(item["status"] in {"满足", "问题", "待验证", "不适用", "未执行"} for item in result["checks"])
    assert source.view.files == baseline
    assert before == {str(path.relative_to(server)): path.read_bytes() for path in server.rglob("*.json")}


@pytest.mark.parametrize("extra,match", [({"rarity": 5}, "rarity"), ({"element": 1}, "跨属性"), ({"element": 6}, "schema"), ({"from": "123"}, "母本")])
@pytest.mark.parametrize("preview", [False, True])
def test_clone_failure_http_400_and_blocking_five_state_checks(env, extra, match, preview):
    _, store, ops, server = env
    response = CharacterRoutes(SimpleNamespace(ops=ops), server).clone(
        {"preview": [str(preview).lower()]}, request(**extra))
    result = json.loads(response.body)
    assert response.status == 400 and not result["ok"] and match in result["error"]
    assert result["checks"][0]["status"] == "问题" and result["checks"][0]["blocking"]
    assert not store.root.exists()


def test_preview_missing_asset_has_blocking_check_without_creating_draft(env):
    source, store, ops, _ = env
    del source.view.files["medium", "character/mother/ui/square_0.png"]
    response = CharacterRoutes(SimpleNamespace(ops=ops)).clone({"preview": ["true"]}, request())
    result = json.loads(response.body)
    assert response.status == 200 and not result["buildable"]
    assert any(c["rule"] == "character.assets" and c["blocking"] for c in result["checks"])
    assert not store.root.exists()


def test_preview_without_server_input_reports_five_unverified_targets(env):
    _, store, ops, _ = env
    response = CharacterRoutes(SimpleNamespace(ops=ops)).clone({"preview": ["true"]}, request())
    document = json.loads(response.body)
    assert response.status == 200 and not document["buildable"]
    assert len(document["serverTables"]) == 5
    assert all(not item["baselineVerified"] for item in document["serverTables"])
    assert any(c["rule"] == "character.server_inputs" and c["blocking"] for c in document["checks"])
    assert not store.root.exists()


def test_preview_rejects_invalid_server_json_before_writing(env):
    _, store, ops, server = env
    (server / "mana_board.json").write_text("[]", encoding="utf-8")
    response = CharacterRoutes(SimpleNamespace(ops=ops), server).clone({"preview": ["true"]}, request())
    assert response.status == 400 and not json.loads(response.body)["ok"]
    assert not store.root.exists()


def test_independent_abilities_preserve_all_records_and_donor_bytes(env):
    source, store, ops, _ = env
    # A shared donor key in two slots must become two independently owned keys.
    change_character(source, 20, "100")
    donor_rows = rows(source.raw(T.ABILITY))
    lines = core.read_csv_lines(zlib.decompress(donor_rows["100"]).decode("utf-8"))
    donor_rows["100"] = leaf(lines + lines)
    source.view.files["common", T.ABILITY] = ordered(donor_rows)
    source._raw.clear()
    original = dict(source.view.files)
    result = clone(ops, request(skill="reuse"))
    members = clone_members(source, store, result["changeset"])
    for table, donor, target in ((T.LEADER, "3", NEW), (T.ABILITY, "100", NEW + "1"), (T.ABILITY, "100", NEW + "2")):
        actual = rows(members["common", table])
        assert actual[target] == actual[donor] == rows(original["common", table])[donor]
    assert result["changeset"]["changes"][0]["params"]["ownedRows"][T.CHAR] == [NEW]
    assert source.view.files == original


def test_ability_key_collision_rejected_before_write(env):
    source, store, ops, _ = env
    baseline = rows(source.raw(T.ABILITY))
    baseline[NEW + "1"] = baseline["100"]
    source.view.files["common", T.ABILITY] = ordered(baseline)
    source._raw.clear()
    with pytest.raises(DraftError, match="能力键已占用"):
        clone(ops, request())
    assert not store.root.exists()


def test_absent_leader_and_ability_slots_stay_absent(env):
    source, store, ops, _ = env
    for column in (17, *range(19, 25)):
        change_character(source, column, "(None)")
    source.view.files.pop(("common", T.ABILITY))
    source.view.files.pop(("common", T.LEADER))
    result = clone(ops, request())
    members = clone_members(source, store, result["changeset"])
    row = core.read_csv_lines(core.read_orderedmap_file_from_bytes(members["common", T.CHAR])[NEW])[0]
    assert row[17] == "(None)" and row[19:25] == ["(None)"] * 6
    assert ("common", T.ABILITY) not in members and ("common", T.LEADER) not in members


def test_future_mana_board_time_is_clamped_only_for_new_character(env):
    source, store, ops, _ = env
    old = leaf([["2026-12-31 12:00:00", "other"]])
    source.view.files["common", T.MANA_OPEN] = ordered({OLD: old})
    clone(ops, request())
    actual = rows(clone_members(source, store, store.load(NEW))["common", T.MANA_OPEN])
    assert actual[OLD] == old
    assert core.read_csv_lines(zlib.decompress(actual[NEW]).decode("utf-8"))[0][0] == T.SAFE_OPEN_START


@pytest.mark.parametrize("missing", SERVER_FILES)
def test_every_server_mirror_is_required_for_preflight_and_delivery(env, missing):
    source, store, ops, server = env
    (server / missing).unlink()
    with pytest.raises(DraftError, match="missing"):
        clone(ops, request(), server_dir=server, preview=True)
    assert not store.root.exists()
    clone(ops, request())
    with pytest.raises(DraftError, match="missing"):
        compile_clone(source, store, store.load(NEW), server_dir=server)


def test_all_server_mirrors_preserve_unselected_value_bytes(env):
    source, store, ops, server = env
    raw = b'{\r\n "other" : { "number":1.00, "nested" : [ 3, 2 ] }, "last" : "\\u4e2d"\r\n}\r\n'
    for name in SERVER_FILES:
        (server / name).write_bytes(raw)
    clone(ops, request(), server_dir=server)
    servers = compile_clone(source, store, store.load(NEW), server_dir=server)[1]
    original, _, spans = _json_spans(raw)
    for name, output in servers.items():
        text, parsed, after = _json_spans(output)
        assert NEW in parsed
        assert all(original[a:b] == text[slice(*after[key])] for key, (a, b) in spans.items())
        assert (server / name).read_bytes() == raw


@pytest.mark.parametrize("name", SERVER_FILES)
@pytest.mark.parametrize("prefix", ["", "assets/"])
def test_shared_key_guard_covers_character_server_maps(tmp_path, name, prefix):
    target = prefix + name
    path = tmp_path / target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'{"existing":{"keep":true}}')
    output = check_shared_keys({}, {target: b'{"new":{}}'}, server_dir=tmp_path, protected={})
    assert output["server_targets"] == [target]
    assert any("lost baseline JSON keys" in error for error in output["errors"])
    path.unlink()
    output = check_shared_keys({}, {target: b'{"new":{}}'}, server_dir=tmp_path, protected={})
    assert any("missing complete server baseline" in error for error in output["errors"])

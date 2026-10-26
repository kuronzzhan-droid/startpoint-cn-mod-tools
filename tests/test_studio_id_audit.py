"""Source-specific ID ownership, with negative cases for misleading columns."""
import pytest
import wf_quest_lib as codec
from wf.balance.rows import join_leaf
from wf.studio.id_catalog import CHARACTER, MANA, TABLES, ABILITY_STRINGS
from wf.studio.ids import check_id, collect_occupancy
from wf.view.layout import col, mode_col

from test_studio_ids import Source, write


@pytest.mark.parametrize("metadata", [False, True])
@pytest.mark.parametrize("historical", [False, True])
def test_clone_full_tables_only_reserve_inserted_rows(tmp_path, metadata, historical):
    target, donor, future = "199001", "111007", "111999"
    folder = tmp_path / target
    params = {"spec": {"from": donor, "to": target}}
    if metadata:
        params["ownedRows"] = {CHARACTER: [target], MANA: [target]}
    files = []
    for logical in (CHARACTER, MANA):
        payload = folder / (logical.rsplit("/", 1)[-1] + ".bin")
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_bytes(codec.build_node({donor: "baseline", future: "later baseline", target: "new"}))
        files.append({"logical": logical, "draft": payload.name})
    write(folder / "changeset.json", {"characterId": target, "changes": [
        {"kind": "character_clone", "params": params, "files": files}]})
    source = Source({} if historical else {CHARACTER: {donor: "baseline", future: "later baseline"}})
    occupied = collect_occupancy(source, drafts_root=tmp_path)
    for kind in ("character", "mana_node"):
        assert not any(e["source"] == "draft" for identity in (donor, future)
                       for e in occupied[kind].get(identity, []))
        assert any(e["source"] == "draft" for e in occupied[kind][target])


def test_character_aliases_do_not_treat_leader_key_as_character_id(tmp_path):
    row = [""] * 37
    row[17], row[27] = "777777", "199002"
    source = Source({CHARACTER: {"199001": join_leaf("", [row])},
                     "master/character/character_speech.orderedmap": {"199003": "speech"},
                     "master/character/character_image.orderedmap": {"199004": "image"}})
    for identity in ("199001", "199002", "199003", "199004"):
        assert not check_id(source, "character", identity, drafts_root=tmp_path)["available"]
    assert check_id(source, "character", "777777", drafts_root=tmp_path)["available"]


@pytest.mark.parametrize("logical", ABILITY_STRINGS)
def test_ability_string_sources_take_c0_not_outer_ability_key(tmp_path, logical):
    source = Source({logical: {"123": join_leaf("", [["used_text", "false"], ["another_text", "false"]])}})
    result = check_id(source, "string_id", "used_text", drafts_root=tmp_path)
    assert result["owners"][0]["owner"] == "123"
    assert not check_id(source, "string_id", "another_text", drafts_root=tmp_path)["available"]
    assert check_id(source, "string_id", "123", drafts_root=tmp_path)["available"]


def test_weapon_clone_text_defaults_match_weapon_identity(tmp_path):
    requests = [{"operation": "weapon_clone", "weapon": {"id": "5950001"}},
                {"operation": "weapon_clone", "weapon": {"id": "5950002", "code": "custom_gun"}}]
    write(tmp_path / "boss/q/changeset.json", {"characterId": "q", "subjectKind": "boss",
          "changes": [{"params": {"requests": requests}}]})
    occupied = collect_occupancy(Source(), drafts_root=tmp_path)["string_id"]
    assert {"boss_workshop_5950001", "boss_workshop_soul_5950001", "custom_gun", "custom_gun_soul"} <= occupied.keys()
    assert "boss_workshop_5950001_soul" not in occupied


@pytest.mark.parametrize("action,name,space", [("insert_row", "ability", "native"),
    ("attach_key", "leader_ability", "ability"), ("set_cells", "ability", "native")])
def test_ability_request_ids_use_layout_and_column_space(tmp_path, action, name, space):
    width = 124 if name == "leader_ability" else 126
    row = [""] * width
    row[0] = "inserted_text"
    row[mode_col(name)] = "0"
    row[col(name, "instant_content", "kind")] = "629"
    row[col(name, "instant_content", "string_id")] = "invoke_text"
    unique_column = col(name, "precondition1", "unique_condition_id")
    row[unique_column] = "199003"
    if name == "ability":
        row[2] = "199999"  # category is not a unique-condition reference
    column = lambda i: i + 2 if name == "leader_ability" and space == "ability" and i else i
    cells = [{"column": "c" + str(column(i)), "old": None, "new": value} for i, value in enumerate(row)]
    op = {"op": action, "table": name, "key": "10", "column_space": space,
          **({"rows": [cells]} if action == "attach_key" else {"cells": cells, "row": 0})}
    write(tmp_path / "199001/changeset.json", {"characterId": "199001", "changes": [
        {"kind": "ability_edit", "params": {"requests": [{"operations": [op]}]}}]})
    occupied = collect_occupancy(Source(), drafts_root=tmp_path)
    assert "199003" in occupied["unique_condition"]
    assert "199999" not in occupied["unique_condition"]
    assert {"inserted_text", "invoke_text"} <= occupied["string_id"].keys()


def test_partial_ability_edit_resolves_existing_629_kind(tmp_path):
    row = [""] * 126
    row[mode_col("ability")] = "0"
    row[col("ability", "instant_content", "kind")] = "629"
    source = Source({ABILITY_STRINGS[0]: {"10": join_leaf("", [row])}})
    op = {"op": "set_cells", "table": "ability", "key": "10", "row": 0, "cells": [
        {"column": col("ability", "instant_content", "string_id"), "old": "", "new": "new_invoke"}]}
    write(tmp_path / "199001/changeset.json", {"characterId": "199001", "changes": [
        {"kind": "ability_edit", "params": {"requests": [{"operations": [op]}]}}]})
    assert not check_id(source, "string_id", "new_invoke", drafts_root=tmp_path)["available"]


def test_ability_requests_replay_earlier_insert_and_exclude_patch_mask(tmp_path):
    from wf.studio.id_requests import ability_ids
    row = [""] * 126
    row[mode_col("ability")] = "0"
    row[col("ability", "instant_content", "kind")] = "629"
    cells = [{"column": i, "old": None, "new": value} for i, value in enumerate(row)]
    insert = {"op": "attach_key", "table": "ability", "key": "10", "rows": [cells]}
    update = {"op": "set_cells", "table": "ability", "key": "10", "row": 0, "cells": [
        {"column": col("ability", "instant_content", "string_id"), "old": "", "new": "later_text"}]}
    write(tmp_path / "199001/changeset.json", {"characterId": "199001", "changes": [
        {"kind": "ability_edit", "params": {"requests": [{"operations": [insert]}, {"operations": [update]}]}}]})
    assert not check_id(Source(), "string_id", "later_text", drafts_root=tmp_path)["available"]
    row[col("ability", "during_content", "kind")] = "423"
    row[col("ability", "during_content", "unique_condition_id")] = "199009"
    insert["rows"] = [[{"column": i, "old": None, "new": value} for i, value in enumerate(row)]]
    assert ("unique_condition", "199009") not in set(ability_ids([insert]))


def test_server_mirrors_use_real_product_and_overlimit_shapes(tmp_path):
    server = tmp_path / "server"
    for index, name in enumerate(("character_rank_p5b.json", "cdndata/character_rank_p5b.json",
            "cdndata/character_text_rank_p5b.json", "mana_node.json", "mana_board.json"), 1):
        write(server / name, {str(199000 + index): {}})
    write(server / "character_overlimit.json", {"characters": [199006], "maxLevel": 120})
    write(server / "equipment_dissolve.json", {"5950001": {"ability_soul_id": 5950001}})
    for name in ("boss_coin_shop.json", "boss_coin_shop_cnmod.json"):
        write(server / name, {"99": {"990001": {"rewards": [
            {"type": 4, "id": 5950002}, {"type": 0, "id": 5950003}, {"type": 3, "id": 777777}]}}})
    occupied = collect_occupancy(Source(), drafts_root=tmp_path / "drafts", server_dir=server)
    assert all(str(i) in occupied["character"] for i in range(199001, 199007))
    assert {"5950001", "5950002", "5950003"} <= occupied["weapon"].keys()
    assert "777777" not in occupied["weapon"] and "99" not in occupied["weapon"]
    assert "characters" not in occupied["character"]

"""Supported deletion contracts, store layouts and no-baseline preview limits."""
import json
import zipfile

import pytest
import wf_quest_lib as codec

from test_boss_shop_weapon import state  # noqa: F401 - shop graph, no kind inspection is invoked
from wf.boss import schema as s
from wf.boss.shop_edit import edit_shop
from wf.deliver.build import build_delivery
from wf.deliver.changeset import member_name, sha256
from wf.deliver.key_guard import CUSTOM, check_shared_keys, _table_problems
from wf.view import ManifestView


@pytest.mark.parametrize("edit_first", [False, True])
def test_explicit_shop_delete_keeps_other_products_and_passes_real_delivery(state, tmp_path, edit_first):
    active, store = tmp_path / "active", tmp_path / "store"
    active.mkdir()
    store.mkdir()
    for name in ("ability", "leader_ability"):
        state.base.files[f"master/ability/{name}.orderedmap"] = codec.build_node({})
    filename = "pinball-1.4.131-1.4.132-1-shop.zip"
    with zipfile.ZipFile(active / filename, "w") as archive:
        for logical, raw in state.base.files.items():
            archive.writestr(member_name("common", logical), raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.132", "patches": [{"version": "1.4.132",
        "depends_on": "1.4.131", "chain": [filename], "type": "patch"}]}), "utf-8")
    view = ManifestView("1.4.132", store=store, manifest=manifest, search_dirs=[active])
    if edit_first:
        edit_shop(state, {"operation": "shop_edit", "shop": {
            "category": "81", "productId": "100", "name": "Renamed product"}}, {"81"})
    edit_shop(state, {"operation": "shop_delete", "shop": {"category": "81", "productId": "100"}}, {"81"})
    stage = tmp_path / "staged"
    stage.mkdir()
    doc = {"schema": "wf-change-set/1", "id": "shop-delete", "name": "shop-delete", "slug": "shop-delete",
        "created_at": "2026-10-25", "from_version": "1.4.132", "to_version": "1.4.133",
        "local_test_only": True, "members": [], "server_changes": [], "changes": state.changes}
    for logical, raw in state.client.items():
        name = sha256(raw)
        (stage / name).write_bytes(raw)
        doc["members"].append({"root": "common", "logical_path": logical, "source": name,
            "sha256": name, "before_sha256": sha256(state.original[logical])})
    for target, raw in state.servers.items():
        name = sha256(raw)
        (stage / name).write_bytes(raw)
        doc["server_changes"].append({"target": target, "source": name,
            "sha256": name, "before_sha256": sha256(state.server_original[target])})
    changeset = stage / "changeset.json"
    changeset.write_text(json.dumps(doc), "utf-8")
    result = build_delivery(changeset, tmp_path / "delivery", baseline_view=view,
                            server_dir=state.server_dir, allow_unknown_client=True)
    assert result["prepush"]["exit_code"] == 0, result
    raw = state.client[s.SHOP]
    members = {member_name("common", s.SHOP): (raw, {"logical_path": s.SHOP})}
    assert codec.parse_node(raw).keys() == {"101"}
    # An omitted or forged old value never grants a general deletion escape.
    for changes in ([], [{**state.changes[0], "old": "wrong"}]):
        assert check_shared_keys(members, {}, baseline=view, protected={}, changes=changes)["errors"]
    if edit_first:
        broken_chain = [state.changes[0], {**state.changes[-1], "old": "wrong intermediate value"}]
        assert check_shared_keys(members, {}, baseline=view, protected={}, changes=broken_chain)["errors"]
    # Even a real, explicitly requested shop deletion cannot erase a claimed key.
    claimed = check_shared_keys(members, {}, baseline=view, protected={s.SHOP: {"100"}}, changes=state.changes)
    assert any("protected character-pack claims" in error for error in claimed["errors"])


@pytest.mark.parametrize("root", ["common", "medium", "android"])
def test_guard_uses_existing_production_store_layout(root, tmp_path):
    raw = codec.build_node({"legacy": "keep"})
    name = member_name(root, CUSTOM)
    production = tmp_path / "production"
    filename = production / name.removeprefix("production/")
    filename.parent.mkdir(parents=True)
    filename.write_bytes(raw)
    (production / "upload").mkdir(exist_ok=True)
    members = {name: (raw, {"logical_path": CUSTOM, "root": root})}
    assert not check_shared_keys(members, {}, base_store=production, protected={})["errors"]


def test_no_baseline_waiver_never_skips_parsing_a_new_table():
    logical = "master/test/new_table.orderedmap"
    report = check_shared_keys({member_name("common", logical): (b"bad", {"logical_path": logical})}, {},
                              no_baseline_i_know=True, protected={})
    assert any("cannot inspect candidate" in error for error in report["errors"])


def test_waiver_is_explicit_and_cannot_hide_a_missing_known_store_table(tmp_path):
    members = {member_name("common", CUSTOM): (codec.build_node({"new": "value"}), {"logical_path": CUSTOM})}
    assert check_shared_keys(members, {}, protected={})["errors"]
    preview = check_shared_keys(members, {}, no_baseline_i_know=True, protected={})
    assert not preview["errors"] and "unverified" in preview["notes"][0]
    assert preview["protected_claims_checked"] is False
    assert check_shared_keys(members, {}, base_store=tmp_path, no_baseline_i_know=True, protected={})["errors"]


def test_quoted_multiline_text_is_one_record_and_can_be_edited():
    before = codec.build_node({"description": '"First line\nsecond line"'})
    after = codec.build_node({"description": "Updated text"})
    errors, _notes = _table_problems(CUSTOM, before, after, set(), "fixture")
    assert errors == []

"""Frozen 223 acceptance; only the optional local source profile is external."""
from __future__ import annotations

import pytest
from recipes.balance_replay223 import replay

from wf.balance import apply_recipe, load_recipe
from wf.balance.inputs import open_inputs
from wf.balance.rows import TABLES, split_leaf
from wf.paths import REPOSITORY
import wf_quest_lib as nodes
from wf.view.base149 import member

RECIPE = REPOSITORY / "recipes/balance/balance1017-223.yml"
GOLDEN = {
    "production/upload/07/0c6e214359ccf27b1cb8078d3fc51aecfe0149": "2712bf39e5dcd3bccdc65cd470761aff5c82ff0e40b51139354fbb90c924aa7d",
    "production/upload/1e/664c1cc8d80f4f9a69aae2c49ae8c01d1c4001": "6d9448945f57093d1a52a0f8cfe459e70e93b00829d7f12a207c29c81a0bfb5f",
    "production/upload/ff/84353774cb95e8d7dc90c679f96a5bca7f42e5": "6967615bb73fa7bdbc8714810a04e26a3f20808c860b626d60164e35a8f97553",
}


def test_223_recipe_is_explicit_data_for_all_eight_characters():
    recipe = load_recipe(RECIPE)
    assert {op["character"] for op in recipe["operations"]} == {
        "129999", "129992", "139995", "119992", "169980", "119991", "139997", "119990"}
    assert len(recipe["operations"]) == 50
    assert sum(len(op["cells"]) for op in recipe["operations"]) == 519
    assert {op["op"] for op in recipe["operations"]} == {"set_cells", "insert_row", "delete_row"}
    for source in (REPOSITORY / "wf/balance").glob("*.py"):
        text = source.read_text("utf-8")
        assert "recipes.balance1017" not in text
        assert "importlib" not in text


@pytest.mark.skipif(not (REPOSITORY / "profiles/local.json").exists(), reason="需要本机只读历史输入 profile")
def test_223_yaml_rebuild_matches_all_three_original_member_hashes():
    report = replay()
    verification = report["view_verification"]
    assert report["member_sha256"] == GOLDEN
    assert verification["active_zip_count"] == 85
    assert verification["store_member_count"] == 0


@pytest.mark.skipif(not (REPOSITORY / "profiles/local.json").exists(), reason="需要本机只读历史输入 profile")
def test_real_action_skill_third_tier_can_be_edited_without_changing_other_tiers():
    document = load_recipe(RECIPE)
    view, verify = open_inputs(document, RECIPE)
    table = view.load(TABLES["action_skill"])
    from wf.balance.ownership import owner_index
    owners = owner_index(view)["action_skill"]
    key = next(key for key, tiers in table.items() if "3" in tiers and key in owners and len(owners[key]) == 1)
    old = split_leaf(table[key]["3"], "action_skill")[0][2]
    document["operations"] = [{"op": "set_cells", "character": next(iter(owners[key])),
        "table": "action_skill", "key": key, "level": "3", "row": 0, "row_count": 1,
        "cells": [{"column": "c2", "old": old, "new": "351" if old != "351" else "352"}]}]
    result = apply_recipe(document, view)
    after = nodes.parse_node(result.files[member(TABLES["action_skill"])])[key]
    assert split_leaf(after["3"], "action_skill")[0][2] == document["operations"][0]["cells"][0]["new"]
    assert after["1"] == table[key]["1"] and after["2"] == table[key]["2"]
    verify()


@pytest.mark.skipif(not (REPOSITORY / "profiles/local.json").exists(), reason="需要本机只读历史输入 profile")
def test_real_shared_resistance_princess_skill_names_both_owners():
    document = load_recipe(RECIPE)
    view, verify = open_inputs(document, RECIPE)
    key = "resistance_princess_3halfanv"
    leaf = view.load(TABLES["action_skill"])[key]["1"]
    old = split_leaf(leaf, "action_skill")[0][2]
    document["operations"] = [{"op": "set_cells", "character": "119999",
        "table": "action_skill", "key": key, "level": "1", "row": 0, "row_count": 1,
        "cells": [{"column": "c2", "old": old, "new": "351" if old != "351" else "352"}]}]
    with pytest.raises(ValueError, match=r"owners=\['111165', '119999'\].*shared_ok"):
        apply_recipe(document, view)
    document["operations"][0]["shared_ok"] = True
    result = apply_recipe(document, view)
    assert result.ownership == {f"action_skill/{key}": ["111165", "119999"]}
    verify()

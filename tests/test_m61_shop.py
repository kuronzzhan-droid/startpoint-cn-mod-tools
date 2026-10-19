"""M6.1 shop windows and loaded-atlas membership counterexamples."""
import pytest

from test_boss_shop_weapon import state, state as shop_state  # noqa: F401
from test_m6_boss_reservations import editor  # noqa: F401
from wf.boss import schema as s
from wf.boss.shop_edit import edit_shop, item_reference
from wf.boss.shop_model import SERVER_SHOP
from wf.studio.drafts import schema_errors
from wf.view.base149 import join


def test_expired_shop_source_is_reset_and_warned(state):
    row = s.parse_rows(state.table(s.SHOP)["100"])[0]
    row[25:27] = ["2024-01-01", "2024-05-18 11:59:59"]
    state.set_leaf(s.SHOP, ["100"], join(row))
    request = {"operation": "shop_add", "shop": {"category": "81", "sourceProduct": "100"}}
    edit_shop(state, request, {"81"})
    identity = request["shop"]["productId"]
    assert s.parse_rows(state.table(s.SHOP)[identity])[0][25:27] == ["2000-01-01", "(None)"]
    assert state.server(SERVER_SHOP)["81"][identity]["availableUntil"] is None
    assert state.shop_checks[0]["sourceProduct"] == "100"
    assert not state.shop_checks[0]["blocking"]


def test_shop_window_can_be_set_edited_and_cleared(state):
    request = {"operation": "shop_add", "shop": {"category": "81", "sourceProduct": "100",
        "availableFrom": "2020-02-29", "availableUntil": "2030-12-31 23:59:59"}}
    assert not schema_errors(request, "bossRequest")
    edit_shop(state, request, {"81"})
    identity = request["shop"]["productId"]
    row = s.parse_rows(state.table(s.SHOP)[identity])[0]
    assert row[25:27] == ["2020-02-29", "2030-12-31 23:59:59"]
    assert state.server(SERVER_SHOP)["81"][identity]["availableUntil"] == row[26]
    edit_shop(state, {"operation": "shop_edit", "shop": {"category": "81", "productId": identity,
        "availableFrom": "2001-01-01", "availableUntil": None}}, {"81"})
    assert s.parse_rows(state.table(s.SHOP)[identity])[0][25:27] == ["2001-01-01", "(None)"]
    assert state.server(SERVER_SHOP)["81"][identity]["availableFrom"] == "2001-01-01"
    assert state.server(SERVER_SHOP)["81"][identity]["availableUntil"] is None


@pytest.mark.parametrize("fields", [
    {"availableFrom": "2025-02-29"}, {"availableFrom": None},
    {"availableUntil": "2025-08-40"}, {"availableUntil": "1999-12-31"},
    {"availableFrom": "2026-01-01", "availableUntil": "2025-12-31"},
])
def test_invalid_shop_windows_are_rejected(state, fields):
    with pytest.raises(ValueError, match="available"):
        edit_shop(state, {"operation": "shop_add", "shop": {
            "category": "81", "sourceProduct": "100", **fields}}, {"81"})
    assert not state.client and not state.servers


def test_expired_shop_warning_reaches_preview_and_compile(editor):
    import wf_quest_lib as codec
    from wf.studio.boss import compile_boss
    rows = codec.parse_node(editor.source.view.files[s.SHOP])
    row = s.parse_rows(rows["100"])[0]
    row[26] = "2024-05-18"
    rows["100"] = join(row)
    editor.source.view.files[s.SHOP] = codec.build_node(rows)
    request = {"operation": "shop_add", "shop": {"category": "81", "sourceProduct": "100"}}
    preview = editor.preview("1006001", request)
    assert preview["ok"] and any(c["rule"] == "boss.shop.availability" for c in preview["checks"])
    applied = editor.apply("1006001", request)
    draft = editor.store.save(applied["questId"])
    result = compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)
    assert any(c["rule"] == "boss.shop.availability" for c in result["checks"])


@pytest.mark.parametrize("prefix", ["item", "item_icon", "item_sec", "scene/general"])
def test_c8004_accepts_each_loaded_atlas_but_requires_matching_sheet(state, prefix):
    from wf_weapon_awaken import encode_atlas
    from wf.boss.shop_model import ITEM
    name = prefix + "/member"
    row = s.parse_rows(state.table(ITEM)["1"])[0]
    row[4] = name
    state.set_leaf(ITEM, ["1"], join(row))
    atlas = prefix + "/sprite_sheet.atlas.amf3.deflate"
    state.base.files[atlas] = encode_atlas([{"n": name}])
    with pytest.raises(ValueError, match="C8004"):
        item_reference(state, "1")
    state.base.files[prefix + "/sprite_sheet.png"] = b"sheet"
    state.original.pop(prefix + "/sprite_sheet.png", None)
    item_reference(state, "1")

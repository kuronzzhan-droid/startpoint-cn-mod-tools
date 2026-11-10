"""Current abyss shop ownership includes tickets and excludes the degree shop."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest
import wf_mod_tool as core

from wf.tools.content import enhancement_policy as policy
from wf.tools.rogue import rogue_shop


SHOP_LOGICAL = "master/shop/event_item_shop.orderedmap"
OWNED = tuple(str(value) for value in range(9700101, 9700118))


@pytest.fixture
def gui(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "resolve_profile", lambda _name: None)
    monkeypatch.setattr(core, "resolve_active_store", lambda *args, **kwargs: tmp_path)
    monkeypatch.setattr(core, "default_source_store", lambda: None)
    path = Path(__file__).resolve().parents[1] / "wf/tools/core/gui.py"
    spec = importlib.util.spec_from_file_location("_rogue_shop_scope_gui", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gui_and_content_policy_cover_the_current_shop(gui):
    assert tuple(gui.ROGUE_SHOP_KEYS) == rogue_shop.OWNED_SHOP_IDS == OWNED
    assert policy.SHOP_ITEMS == OWNED
    assert "9700118" not in policy.SHOP_ITEMS
    # The degree row remains content under its own existing allowance.
    assert policy.EXPECTED_CONTENT_ROWS[SHOP_LOGICAL] == (*OWNED, "9700118")
    for key in (*OWNED, "9700118"):
        assert policy.Policy().is_content_key(SHOP_LOGICAL, key)
    for key in ("9700100", "9700119", "97001170"):
        assert not policy.Policy().is_content_key(SHOP_LOGICAL, key)


def test_gui_ticket_edit_preview_accepts_both_tickets_and_rejects_degree(gui, tmp_path, monkeypatch):
    import wf_quest_lib as quest

    tables = {}
    for key in (*rogue_shop.TICKET_SHOP_IDS, "9700118"):
        row = [""] * 51
        row[19] = "10"
        tables[key] = gui._rogue_join(row, "")
    before = copy.deepcopy(tables)
    server = tmp_path / "event_item_shop.json"
    raw = json.dumps({"11": {"700099": {key: {} for key in tables}}})
    server.write_text(raw, encoding="utf-8")
    monkeypatch.setattr(quest, "load_table", lambda _logical: tables)
    monkeypatch.setattr(gui, "_rogue_asset_path", lambda _name: str(server))

    def unexpected_write(*args, **kwargs):
        raise AssertionError("preview attempted a write or publication")

    monkeypatch.setattr(quest, "save_table", unexpected_write)
    monkeypatch.setattr(gui, "_rogue_run", unexpected_write)
    result = gui.rogue_shop_save(
        {"items": [{"id": key, "price": 20} for key in tables]}, dry_run=True
    )

    assert result["ok"] and result["dry_run"]
    for key in rogue_shop.TICKET_SHOP_IDS:
        assert f"{key} ②price:" in result["log"]
    assert "[跳过] 9700118 不是深渊商店键" in result["log"]
    assert tables == before
    assert server.read_text(encoding="utf-8") == raw

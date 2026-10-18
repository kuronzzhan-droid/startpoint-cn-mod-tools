"""M5.1 studio contexts, stable identities and delivery failure propagation."""
import struct

import pytest
import wf_quest_lib as codec

from test_boss_model import csv_row
from test_boss_rules_preload import View
from test_studio_boss_checks import fixture_editor, request
from test_studio_deliver_bridge import case, build
from wf.boss import schema as s
from wf.rules.boss_atlas import atlas_check
from wf.studio import boss, deliver_bridge
from wf.studio.drafts import DraftError


def png(width, height):
    return b'\x89png\r\n\x1a\n' + b'\x00\x00\x00\x0dIHDR' + struct.pack('>II', width, height)


def test_atlas_capacity_boundary_and_historical_warning():
    view = View()
    view.files = {"boss.png": png(4094, 4094)}
    context = {"atlas_budget": {"parties": [[], [], []], "enemy_sheets": ["boss.png"],
                               "source_quest": "1099031"}}
    report = atlas_check(view, context)
    assert report["padded_pixels"] == 4096 ** 2 and not report["blocking"]
    assert report["near_historical_max"] and report["known_heavy_source"]
    assert "14.61" in report["message"] and not report["historical_reference"]["current_runtime_proof"]
    view.files["boss.png"] = png(4095, 4094)
    assert atlas_check(view, context)["blocking"]


def test_studio_discovers_source_enemy_sheets_and_blocks_preview_and_compile(tmp_path):
    editor = fixture_editor(tmp_path)
    raw = editor.source.view
    table = codec.parse_node(raw.files[s.GENERAL_BOSS])
    for tier, text in table["org"].items():
        row = s.parse_rows(text)[0]
        row[24] = "battle/boss/org/idle"
        table["org"][tier] = csv_row(row)
    raw.files[s.GENERAL_BOSS] = codec.build_node(table)
    sheet = "battle/boss/org/org.png"
    raw.files[sheet] = png(100, 100)
    preview = editor.preview("new", request())
    assert preview["ok"], preview
    check = next(item for item in preview["checks"] if item["rule"] == "art.atlas-budget")
    assert check["status"] == "待验证" and check["padded_pixels"] == 102 ** 2
    assert check["enemy_lower_bound"] and check["source_quest"] == "1006001"
    choice = next(item for item in preview["checks"] if item["rule"] == "boss.choice-folder")
    assert choice["status"] == "未执行" and "本期未接入" in choice["message"]
    draft = editor.apply("new", request())["changeset"]
    raw.files[sheet] = png(4096, 4096)
    preview = editor.preview("new", request())
    assert not preview["ok"] and "4096" in preview["checks"][0]["message"]
    with pytest.raises(ValueError, match="4096"):
        boss.compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)


def test_atlas_supplied_parties_are_not_dropped_by_replay(tmp_path):
    editor = fixture_editor(tmp_path)
    logical = "character/test/pixelart/sprite_sheet.png"
    editor.source.view.files[logical] = png(4096, 4096)
    preview = editor.preview("new", request(atlasBudget={"parties": [[logical], [], []]}))
    assert not preview["ok"] and "4096" in preview["checks"][0]["message"]


def test_bare_and_qualified_id_share_one_draft(tmp_path):
    editor = fixture_editor(tmp_path)
    edit = {"operation": "edit", "parameters": {"hpMultiplier": 2}}
    first = editor.apply("1006001", edit)
    assert first["questId"] == "hard_multi:1006/1"
    second = editor.apply("hard_multi:1006/1", {"operation": "edit", "parameters": {"attackMultiplier": 3}})
    assert second["questId"] == first["questId"]
    assert len(editor.store.characters()) == 1
    assert len(second["change"]["params"]["requests"]) == 2
    assert editor.read("1006001")["changeset"] == editor.read("hard_multi:1006/1")["changeset"]


def test_acknowledgment_is_explicit_persisted_and_not_inherited(tmp_path, monkeypatch):
    editor = fixture_editor(tmp_path)
    original = boss._context
    seen = []

    def context(*args):
        value = original(*args)
        seen.append(value["acknowledgePreload"])
        return value

    monkeypatch.setattr(boss, "_context", context)
    draft = editor.apply("new", request(acknowledgePreload=True))["changeset"]
    assert draft["changes"][0]["params"]["requests"][0]["acknowledgePreload"] is True
    boss.compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)
    assert all(seen)
    editor.preview(draft["characterId"], {"operation": "edit", "parameters": {"hpMultiplier": 2}})
    assert seen[-1] is False
    assert not editor.preview("new", request(acknowledgePreload="true"))["ok"]


@pytest.mark.parametrize("check", [{"blocking": True}, {"level": "error"}])
def test_delivery_failure_includes_draft_checks(case, monkeypatch, check):
    original = deliver_bridge.compile_draft

    def compile_with_failure(*args, **kwargs):
        compiled = list(original(*args, **kwargs))
        compiled[4] = [check]
        return tuple(compiled)

    monkeypatch.setattr(deliver_bridge, "compile_draft", compile_with_failure)
    result = build(case, allow_unknown_client=True)
    assert not result["ok"] and result["draftChecks"] == [check]

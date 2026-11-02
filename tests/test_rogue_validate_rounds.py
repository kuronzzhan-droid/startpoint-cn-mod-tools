"""Offline round compatibility without the optional APK integration tree."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from wf.tools.rogue import rogue_validate as validate


def _round_fixture(tmp_path, rounds):
    store, assets = tmp_path / "store", tmp_path / "assets"
    assets.mkdir()
    client = {
        str(number): f"{700099000 + number},1,{number}"
        for number in range(1, rounds + 1)
    }
    client["99"] = "700099099,2,0"
    quest_path = store / validate.q.hashed_rel(validate.rogue_build.Q_QUEST)
    quest_path.parent.mkdir(parents=True)
    quest_path.write_bytes(validate.q.build_node({"700099": client}))
    server = {
        str(700099000 + number): {
            "rushEventId": 700099, "rushEventFolderId": 1,
            "rushEventRound": number,
        }
        for number in range(1, rounds + 1)
    }
    server["700099099"] = {
        "rushEventId": 700099, "rushEventFolderId": 2, "rushEventRound": 0,
    }
    (assets / "rush_event_quest.json").write_text(json.dumps(server), encoding="utf-8")
    return store, assets


@pytest.mark.parametrize("rounds", [None, 10, 15, 30])
def test_offline_rounds_accept_legacy_or_explicit_supported_contract(tmp_path, rounds):
    expected = 15 if rounds is None else rounds
    store, assets = _round_fixture(tmp_path, expected)
    if rounds is not None:
        (assets / "rogue_event.json").write_text(
            json.dumps({"events": {"700099": {"rounds": rounds}}}), encoding="utf-8",
        )

    errors = []
    assert validate._validate_offline_rounds(store, assets, errors) == expected
    assert errors == []


@pytest.mark.parametrize("config", ["{", "[]", '{"events":{"700099":{"rounds":20}}}'])
def test_offline_rounds_reject_invalid_explicit_configuration(tmp_path, config):
    store, assets = _round_fixture(tmp_path, 15)
    (assets / "rogue_event.json").write_text(config, encoding="utf-8")
    errors = []

    validate._validate_offline_rounds(store, assets, errors)

    assert any(error.startswith("assets.rogue_event.rounds.invalid:") for error in errors)


def test_offline_rounds_do_not_infer_contract_from_actual_row_count(tmp_path):
    store, assets = _round_fixture(tmp_path, 10)
    errors = []

    validate._validate_offline_rounds(store, assets, errors)

    assert any("expected=1..15" in error for error in errors)
    assert any("expected exactly 15" in error for error in errors)


def test_offline_rounds_validate_server_rows_for_explicit_contract(tmp_path):
    store, assets = _round_fixture(tmp_path, 30)
    (assets / "rogue_event.json").write_text(
        '{"events":{"700099":{"rounds":30}}}', encoding="utf-8",
    )
    server_path = assets / "rush_event_quest.json"
    server = json.loads(server_path.read_text(encoding="utf-8"))
    server["700099030"]["rushEventRound"] = 29
    server_path.write_text(json.dumps(server), encoding="utf-8")
    errors = []

    validate._validate_offline_rounds(store, assets, errors)

    assert "assets.rush_event_quest[30].mapping" in errors


@pytest.mark.parametrize("rounds", [10, 15, 30])
def test_rogue_data_gate_accepts_each_supported_complete_report(monkeypatch, tmp_path, rounds):
    report = SimpleNamespace(
        event_id=700099, round_count=rounds, token_id=2370099,
        weapon_ids=tuple(range(8000101, 8000116)), missing_logicals=(), ready=True,
    )
    monkeypatch.setattr(validate, "validate_release_data_only", lambda *_args: report)

    assert validate.validate_rogue_data(tmp_path, tmp_path) is report

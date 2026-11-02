"""New scene encounters must exercise the existing authored-content time gate."""
from types import SimpleNamespace

import pytest

import wf.boss.scene_checks as scenes


@pytest.mark.parametrize("created,start,end,status,blocked", [
    (True, "2000-01-01 00:00:00", "(None)", "满足", False),
    (True, "2099-01-01 00:00:00", "(None)", "问题", True),
    (True, "2000-01-01 00:00:00", "2026-01-01 00:00:00", "问题", True),
    (False, "2099-01-01 00:00:00", "(None)", "未执行", False),
])
def test_studio_scene_created_period_gate(monkeypatch, created, start, end, status, blocked):
    row = ["(None)"] * 132
    row[0], row[5], row[6] = "300099001", start, end
    document = {"quest": {"kind": "advent_event", "id": row[0],
                          "selector": "advent_event:300099/1", "row": row, "fields": {}},
                "terrain": {}, "enemies": []}
    monkeypatch.setattr(scenes, "encounter", lambda *args: document)
    monkeypatch.setattr(scenes, "MultiplayerScanner", lambda state: None)
    monkeypatch.setattr("wf.rules.multiplayer.check_multiplayer", lambda *args: [])
    monkeypatch.setattr("wf.boss.atlas.encounter_budget", lambda *args: None)
    state = SimpleNamespace(source=object(), table=lambda name: {}, raw=lambda name: None)
    spec = {"event": {"id": "300099"}, "tiers": [{"id": str(i)} for i in range(1, 6)]}
    if created:
        spec["creation"] = {"sourceEvent": "300097"}
    checks = scenes.scene_checks(state, spec)
    periods = [check for check in checks if check["rule"] == "boss.custom-time"]
    assert len(periods) == 5
    assert all(check["status"] == status and check["blocking"] is blocked for check in periods)

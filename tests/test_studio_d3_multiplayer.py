"""Candidate EnemyDsl closure and non-blocking multiplayer diagnostics."""
from wf.rules.multiplayer import scan_tree, check_multiplayer
from wf.studio.deliver_media import encode_tree
from wf.boss.esdl import transform
from wf.boss import schema


def test_evidenced_risk_classes_and_no_safety_claim():
    from test_studio_d3_multiplayer_regressions import RANDOM
    tree = ["Block", [RANDOM, ["Command", ["SetVariableValue", "phase", 1]]]]
    checks = scan_tree(tree, "battle/action/example")
    assert {c["rule"] for c in checks} == {"multiplayer.random"}
    assert all(c["category"] == "联机风险" and c["blocking"] is False for c in checks)
    assert all("可能" in c["message"] for c in checks)
    assert all(c["location"].startswith("battle/action/example#/") for c in checks)
    assert scan_tree({"subtitle": "RandomInt", "sync": False}, "plain") == []


def test_real_enemy_wire_events_and_referenced_action_closure():
    from test_studio_d3_multiplayer_regressions import RANDOM
    esdl = {"forms": [{"states": [{"canonicalPath": 0, "synchronization": False,
                                  "next": ["QS", ["Pure", ["D", [{"state": 1}, {"state": 2}]]]]}],
                       "events": [{"kind": ["SomebodyDead"]}],
                       "deadActions": [{"filePath": "on_dead"}]}],
            "action_base_path": "battle/action/test/"}
    files = {"battle/enemy/example.esdl.amf3.deflate": encode_tree(transform(esdl, encode=True)),
             "battle/action/test/on_dead.action.dsl.amf3.deflate": encode_tree(RANDOM)}
    class View:
        def read_raw(self, logical):
            return files.get(logical), "fixture"
    document = {"enemies": [{"kind": "boss", "code": "example", "path": ["example"],
                             "wave": "1", "level": "1", "table": schema.STANDARD_BOSS,
                             "row": ["", "battle/enemy/example"]}]}
    checks = check_multiplayer(document, View())
    assert {"multiplayer.random", "multiplayer.death_event"} <= {c["rule"] for c in checks}, checks
    assert not any(c["rule"] == "multiplayer.unsynced_state" for c in checks)
    assert any(c["rule"] == "multiplayer.state_random" and "共享基种" in c["message"] for c in checks)
    assert not any(c["blocking"] for c in checks)


def test_missing_program_is_not_a_pass():
    esdl = {"forms": [{"states": [], "deadActions": [{"filePath": "missing"}]}],
            "action_base_path": "battle/action/test/"}
    logical = "battle/enemy/example.esdl.amf3.deflate"
    class View:
        def read_raw(self, path):
            return (encode_tree(transform(esdl, encode=True)) if path == logical else None), None
    document = {"enemies": [{"kind": "boss", "code": "example", "table": schema.STANDARD_BOSS,
                             "row": ["", "battle/enemy/example"]}]}
    checks = check_multiplayer(document, View())
    assert checks and checks[0]["rule"] == "multiplayer.incomplete"
    assert any("battle/action/test/missing.action.dsl.amf3.deflate" in issue for issue in checks[0]["issues"])
    assert not checks[0]["blocking"]


def test_risks_reach_boss_read_preview_and_delivery_without_blocking(tmp_path, monkeypatch):
    from test_studio_boss_checks import fixture_editor, request
    from wf.studio.boss import compile_boss
    from test_studio_d3_multiplayer_regressions import RANDOM
    hints = scan_tree(RANDOM, "battle/action/test")
    monkeypatch.setattr("wf.rules.multiplayer.check_multiplayer", lambda *args: hints)
    editor = fixture_editor(tmp_path)
    assert editor.read("hard_multi:1006/1")["checks"] == hints
    candidate = editor.preview("new", request())
    assert candidate["ok"]
    found = next(c for c in candidate["checks"] if c["rule"] == hints[0]["rule"])
    assert found["quest"] and {k: found[k] for k in hints[0]} == hints[0]
    saved = editor.apply("new", request())["changeset"]
    compiled = compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)
    found = next(c for c in compiled["checks"] if c["rule"] == hints[0]["rule"])
    assert found["quest"] and {k: found[k] for k in hints[0]} == hints[0]
    assert not any(c["blocking"] for c in compiled["checks"])

"""Static package validity must not be reported as device loading proof."""
from types import SimpleNamespace

from test_boss_behavior import behavior_editor, request
from wf.boss.behavior_loading import check_behavior_loading
from wf.studio.boss import compile_boss


def test_bare_action_loading_is_nonblocking_pending():
    check = check_behavior_loading(SimpleNamespace(client={
        "battle/action/enemy/action/studio_behavior/test.action.dsl.amf3.deflate": b"payload"}))
    assert check["status"] == "待验证" and check["runtime_verified"] is False
    assert not check["blocking"] and len(check["paths"]) == 1


def test_unrelated_or_dollar_actions_do_not_claim_loading_evidence():
    check = check_behavior_loading(SimpleNamespace(client={
        "master/battle/boss/general_boss.orderedmap": b"table",
        "battle/action/enemy/action/test$action.action.dsl.amf3.deflate": b"payload"}))
    assert check["status"] == "不适用" and check["paths"] == []
    assert check["runtime_verified"] is False


def test_preview_and_compile_preserve_pending_loader_evidence(tmp_path):
    editor = behavior_editor(tmp_path)
    quest = "hard_multi:1006/1"
    change = request(slot=1, damageMultiplier=1.2)
    preview = editor.preview(quest, change)
    assert preview["ok"]
    assert next(c for c in preview["checks"] if c["rule"] == "boss.behavior-loading")["status"] == "待验证"
    editor.apply(quest, change)
    compiled = compile_boss(editor.source, editor.store, editor.store.save(quest), server_dir=editor.server_dir)
    check = next(c for c in compiled["checks"] if c["rule"] == "boss.behavior-loading")
    assert check["status"] == "待验证" and not check["blocking"]

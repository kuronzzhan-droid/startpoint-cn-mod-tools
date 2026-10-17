import copy
import json

import pytest

from wf.dsl import forbidden_629, sanitize_for_629
from wf.dsl.check import check_tree


def tree(*commands):
    return ["ActionDsl"] + [None] * 10 + [["Block", list(commands)]]


def command(name, *args):
    return ["Command", [name, *args]]


@pytest.mark.parametrize("name,args", [
    ("SetPowerFilpSuppress", [True]), ("NotifyPowerflipEnd", []), ("RemoveEvent", ["*"])
])
def test_each_forbidden_command_blocks_629(name, args):
    source = tree(command(name, *args))
    assert check_tree(source, kind=629)[1]["status"] == "问题"
    assert check_tree(source, kind=0)[1]["status"] == "不适用"
    assert check_tree(source)[1]["status"] == "未执行"
    cleaned = sanitize_for_629(source)
    assert cleaned[11] == ["Block", []]
    assert check_tree(cleaned, kind=629)[1]["status"] == "满足"
    assert source[11][1]


def test_wait_removed_only_when_its_callback_only_notifies():
    notify = command("NotifyPowerflipEnd")
    harmless = command("ShakeCamera", 1)
    notify_wait = ["Event", ["Wait", 109, "*", ["Block", [notify]]]]
    effect_wait = ["Event", ["Wait", 25, "effect", ["Block", [notify, harmless]]]]
    empty_wait = ["Event", ["Wait", 109, "*", ["Block", []]]]
    source = tree(notify_wait, effect_wait, empty_wait, command("Trace", "NotifyPowerflipEnd"))
    frozen = copy.deepcopy(source)
    cleaned = sanitize_for_629(source)
    assert source == frozen
    assert cleaned[11][1][0] == ["Event", ["Wait", 25, "effect", ["Block", [harmless]]]]
    assert cleaned[11][1][1] == empty_wait
    assert len(cleaned[11][1]) == 3
    assert not forbidden_629(cleaned)
    assert sanitize_for_629(cleaned) == cleaned
    assert any(item["command"].startswith("Wait(") for item in forbidden_629(source))


def test_positional_callback_keeps_expression_shape():
    source = tree(["Event", ["Wait", 5, "*", command("RemoveEvent", "*")]])
    assert sanitize_for_629(source)[11][1][0][1][3] == ["Block", []]


def test_signature_failure_is_not_hidden_by_sanitizer():
    source = tree(command("ShakeCamera", "bad-int"))
    assert check_tree(source, kind=629)[0]["status"] == "问题"
    assert sanitize_for_629(source) == source


@pytest.mark.parametrize("source", [
    ["ActionDsl", ["Block", []]],
    tree() + [command("DefinitelyUnknownCommand")],
])
def test_invalid_root_or_trailing_expression_fails_signature_gate(source):
    assert check_tree(source, kind=629)[0]["status"] == "问题"

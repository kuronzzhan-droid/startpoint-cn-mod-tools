"""Delivery read-back retains reward findings and execution boundaries."""
import json

import pytest

from wf.check_delivery import check_delivery
from test_m1_check_delivery import delivery


@pytest.mark.parametrize("level,state,blocking", [("ERROR", "问题", True), ("WARN", "待验证", False),
                                                 (None, "满足", False)])
def test_delivery_exposes_reward_key_result(delivery, level, state, blocking):
    directory, document = delivery
    filename = directory / "prepush.json"
    report = json.loads(filename.read_text("utf-8"))
    report["companion_reward_keys"] = {"executed": True, "server_baseline_complete": True,
                                       "checked_rows": 1, "server_targets": ["quest_reward.json"]}
    if level:
        report["findings"].append({"fid": "companion.reward_key:quest_reward.json:12100088:4", "level": level})
    if blocking:
        document["prepush"].update(status="问题", exit_code=1)
    filename.write_text(json.dumps(report), "utf-8")
    result = next(r for r in check_delivery(document, directory) if r["rule"] == "delivery.reward-keys")
    assert result["status"] == state and result["blocking"] is blocking
    assert bool(result["findings"]) is bool(level)


@pytest.mark.parametrize("evidence,state", [(None, "未执行"),
    ({"executed": True, "server_baseline_complete": False}, "待验证")])
def test_delivery_does_not_claim_unexecuted_reward_checks_passed(delivery, evidence, state):
    directory, document = delivery
    filename = directory / "prepush.json"
    report = json.loads(filename.read_text("utf-8"))
    if evidence is not None:
        report["companion_reward_keys"] = evidence
    filename.write_text(json.dumps(report), "utf-8")
    result = next(r for r in check_delivery(document, directory) if r["rule"] == "delivery.reward-keys")
    assert result["status"] == state

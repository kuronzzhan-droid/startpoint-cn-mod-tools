"""Optional real-chain regressions using the local read-only M5 evidence view."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from wf.boss.edit_state import BossEditState
from wf.boss.reader import BossReader
from wf.rules.boss import check_boss
from wf.view import ManifestView
from wf.view.base149 import join
from wf_rogue_build import QUEST_ELEM_CN


@pytest.fixture(scope="module")
def actual_view():
    config = Path(__file__).resolve().parents[1] / "work/m5/evidence/view-config-236.json"
    if not config.is_file():
        pytest.skip("local M5 236 view configuration is not installed")
    return ManifestView(**json.loads(config.read_text(encoding="utf-8-sig")))


def candidate(view, selector, column, value):
    baseline = BossReader(view).show(selector)
    state = BossEditState(view)
    quest = baseline["quest"]
    row = list(quest["row"])
    row[column] = str(value)
    state.set_leaf(quest["table"], quest["path"], join(row))
    document = BossReader(state).show(selector)
    checks = {entry["rule"]: entry for entry in check_boss(document, view=state, baseline=baseline)}
    return baseline, document, checks


def test_actual_236_arch_evil_recommended_light_is_blocked(actual_view):
    before, after, checks = candidate(actual_view, "boss_battle:1/12/1", 72, QUEST_ELEM_CN.index("光"))
    assert before["quest"]["row"][72] == "4"
    assert after["quest"]["row"][72] == "5"
    assert {enemy["code"] for enemy in after["enemies"]} == {"arch_evil_multi"}
    check = checks["boss.element-preload"]
    assert check["status"] == "问题" and check["blocking"]
    assert any("arch_evil_multi" in issue and "C8016" in issue for issue in check["issues"])


def test_actual_236_crab_level_100_requires_missing_p4(actual_view):
    before, after, checks = candidate(actual_view, "boss_battle:1/10/3", 106, 100)
    assert {enemy["row"][42] for enemy in before["enemies"]} == {"hermit_crab"}
    assert {enemy["row"][42] for enemy in after["enemies"]} == {"hermit_crab_80"}
    check = checks["boss.terrain-layers"]
    assert check["status"] == "问题" and check["blocking"]
    assert any("hermit_crab_80" in issue and "p4" in issue for issue in check["issues"])


def test_actual_236_official_crab_80_has_required_p4(actual_view):
    document = BossReader(actual_view).show("boss_battle:1/10/4")
    checks = {entry["rule"]: entry for entry in check_boss(document, view=actual_view)}
    assert checks["boss.terrain-layers"]["status"] == "满足"

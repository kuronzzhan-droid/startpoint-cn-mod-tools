"""Native floating-point order and serialized panel agreement at boundaries."""
import math

import pytest

from wf.studio.clone_tables import leaf, rows
from wf.studio.source import StudioSource
from wf.studio.summon import SummonEditor
from test_studio_summon import (
    ACTION, BALL, CID, HP, LEVEL, NEW_BALL, OLD_BALL, compiled, curve, flat,
    ordered, request, summon_env,
)


def rebuild(env, replacements):
    source, store, _ = env
    source.view.files.update({("common", key): raw for key, raw in replacements.items()})
    source = StudioSource(source.view)
    return source, store, SummonEditor(source, store=store)


@pytest.mark.parametrize("value,expected", [
    (999999999.9999999, 999999999),
    (999.9999999997999, 1000),
])
def test_manual_preview_and_serialized_native_values_agree(summon_env, value, expected):
    result = summon_env[2].apply(CID, request(panel={"mode": "manual", "levels": [
        {"level": 1, "hp": value, "attack": value}]}))
    tables = compiled(summon_env)
    level = flat(tables[LEVEL], NEW_BALL)[0]
    encoded = curve(tables[HP], level[0])[1]
    assert encoded == value  # Do not round a representable float to 15 decimal digits.
    readback = math.floor(float(level[1]) * encoded * float(level[2]) + 1e-10 + 1e-10)
    assert readback == result["panel"]["first"]["hp"] == expected
    assert result["panel"]["first"]["attack"] == expected


def test_scaled_ball_preview_uses_serialized_correction_before_native_floor(summon_env):
    env = rebuild(summon_env, {
        LEVEL: ordered({OLD_BALL: leaf([["native_hp", "99999990", "2.3", "native_atk", "20", "3"]])}),
        HP: ordered({"native_hp": ordered({"1": leaf([["1"]]), "100": leaf([["1"]])})}),
    })
    result = env[2].apply(CID, request(template={"kind": "multiball", "id": OLD_BALL},
                                      panel={"mode": "scaled", "hp_scale": 5}))
    level = flat(compiled(env)[LEVEL], NEW_BALL)[0]
    assert level[2] == "11.5"
    # ((99999990 * 2.3) * 5) rounds below the native result; the emitted
    # correction is 2.3*5 and the client evaluates 99999990 * 11.5.
    readback = math.floor(float(level[1]) * float(level[2]) + 1e-10 + 1e-10)
    assert readback == result["panel"]["first"]["hp"] == 1149999885
    assert result["panel"]["last"]["hp"] == readback


def test_inherit_skill_level_skips_unrelated_empty_action_leaf(summon_env):
    source = summon_env[0]
    actions = rows(source.raw(ACTION))
    actions["empty_unrelated"] = ordered({"1": leaf([])})
    env = rebuild(summon_env, {ACTION: ordered(actions)})
    result = env[2].apply(CID, request(template={"kind": "multiball", "id": OLD_BALL},
                                      skill={"mode": "inherit", "level": "1"}))
    assert result["skill"]["key"] == "mother_skill" and result["skill"]["level"] == "1"
    assert flat(compiled(env)[BALL], NEW_BALL)[0][9] == "battle/action/skill/mother_low"

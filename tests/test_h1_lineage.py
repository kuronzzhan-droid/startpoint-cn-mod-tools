"""B-lineage regressions: killable bosses, resistance exits and DSL signatures."""
from __future__ import annotations

import copy

import pytest

import wf_dsl_sig as sig
import wf_rogue_build as rb


def walls(open_kind):
    return {"name": "三重壁垒", "text": "三系免疫", "damage_resistance": [
        (kind, 1.0, False) for kind in range(4) if kind != open_kind]}


def stacked(kind, layers=90):
    return rb.stacked_resistance_entry(
        "层叠龙鳞", rb.DAMAGE_RESISTANCE_AC[kind], 0.01, layers)


def quest(kind, value=0.4):
    return {"name": "关卡抗性", "text": "关卡抗性",
            "cond": [(str(kind), str(value))]}


def compiled_totals(out):
    """Inspect emitted values without calling the production totals helper."""
    totals = [0.0] * 4
    for kind, value in out["conds"]:
        if kind in {"0", "1", "2", "3"}:
            totals[int(kind)] += float(value)
    for kind, value, _cancelable in out["damage_resistance"]:
        totals[kind] += value
    for constructor, strength, layers in out["stacked_resistance"]:
        if constructor in rb.STACKED_DAMAGE_AC_KIND:
            totals[rb.STACKED_DAMAGE_AC_KIND[constructor]] += strength * layers
    return totals


def test_score_event_shark_cannot_enter_kill_tower_pool():
    assert not rb._pool_safe(["shark_score_event"])
    assert not rb._pool_safe(["safe_boss", "shark_score_event"])
    assert rb._pool_safe(["shark"])


def test_score_event_shark_identity_gate_does_not_need_external_refs():
    refs = {"hard": set(), "degraded": False}
    assert "不可击杀" in rb.identity_locked_boss_reason(
        ["shark_score_event"], code_references=refs)
    assert "不可击杀" in rb.identity_locked_mix_reason(
        ["shark_score_event"], "native", "moved", code_references=refs)
    assert rb.identity_locked_boss_reason(["shark"], code_references=refs) is None


def test_deep_tower_anchors_start_at_floor26_without_score_shark():
    assert rb.deep_hp_anchor_field(25, 30) is None
    expected = ["eye_dragon_multibattle"] + [
        f"raid_alter_sheep_materia{i}" for i in range(1, 5)]
    assert [rb.deep_hp_anchor_field(r, 30) for r in range(26, 31)] == expected
    assert "score_event_shark" not in rb.DEEP_HP_ANCHOR_FIELDS_30
    assert rb.deep_hp_anchor_field(30, 31) is None


@pytest.mark.parametrize("kind", range(4))
@pytest.mark.parametrize("quest_value", (0.1, 0.4))
def test_quest_and_stacked_resistance_close_last_exit(kind, quest_value):
    picks = [walls(kind), stacked(kind), quest(kind, quest_value)]
    assert rb.immunity_axes(picks)[0] == {"0", "1", "2", "3"}
    assert "四种伤害类型" in rb.curse_conflict(picks)


@pytest.mark.parametrize("kind", range(4))
def test_all_three_resistance_sources_are_added(kind):
    picks = [walls(kind), stacked(kind, 40), quest(kind),
             {"name": "一次性", "text": "20%", "damage_resistance": [(kind, 0.2)]}]
    assert "四种伤害类型" in rb.curse_conflict(picks)


@pytest.mark.parametrize("kind", range(4))
def test_quest_and_one_shot_resistance_close_last_exit(kind):
    picks = [walls(kind), quest(kind), {"damage_resistance": [(kind, 0.6)]}]
    assert "四种伤害类型" in rb.curse_conflict(picks)


@pytest.mark.parametrize("kind", range(4))
def test_same_source_merge_below_threshold_still_builds(kind):
    picks = [walls(kind), stacked(kind, 50), quest(kind), quest(kind, 0.3)]
    assert rb.curse_conflict(picks) is None
    assert compiled_totals(rb.apply_picks({}, picks))[kind] == pytest.approx(0.9)


def test_effect_compilation_rejects_conflict_before_mutating_output():
    out = {"existing": ["preserve"]}
    before = copy.deepcopy(out)
    with pytest.raises(ValueError, match="四种伤害类型"):
        rb.apply_picks(out, [walls(1), stacked(1), quest(1)])
    assert out == before


def condition_tree():
    # Synthetic command with the same nullable p8 used by official shark DSL.
    command = ["CreateCondition", 0, [], [], ["None"], False, False, "",
               None, False, 0, [], False]
    return ["ActionDsl", ["Block", [["Command", command]]]]


def test_create_condition_nullable_linked_hit_check_kind():
    sig.validate_action_dsl(condition_tree())


@pytest.mark.parametrize("position", (4, 5, 9, 10))
def test_nullable_exception_does_not_relax_other_parameters(position):
    tree = condition_tree()
    tree[1][1][0][1][position] = None
    with pytest.raises(sig.DslSignatureError, match=f"参数{position}"):
        sig.validate_action_dsl(tree)


def test_signature_guard_preserves_allowed_parameter_edit_scope():
    before = ["ActionDsl", ["Block", [["Command", [
        "AddSkillPoint", 20, [{"min": 0.2, "max": 0.2}]]]]]]
    after = copy.deepcopy(before)
    after[1][1][0][1][2] = [{"min": 0.15, "max": 0.15}]
    sig.assert_command_parameter_edits(before, after, {"AddSkillPoint": {2}})
    after[1][1][0][1][1] = 15
    with pytest.raises(sig.DslSignatureError, match="未经授权"):
        sig.assert_command_parameter_edits(before, after, {"AddSkillPoint": {2}})


def test_show_effect_option_rejects_scalar_that_triggers_f1034():
    command = ["ShowEffect", "moonwave",
               ["SpecifyEffectDirectly", "battle/effect/test/moonwave"], -1,
               ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"], ["AB"],
               0, 0, 0, False, False, ["Some", 9]]
    tree = ["ActionDsl", ["Block", [["Command", command]]]]
    with pytest.raises(sig.DslSignatureError, match="Option<SLvValue>"):
        sig.validate_action_dsl(tree)
    command[12] = ["Some", [{"min": 9, "max": 9}]]
    sig.validate_action_dsl(tree)

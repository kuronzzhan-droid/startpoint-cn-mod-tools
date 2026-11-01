"""Damage-zone and element rules must preserve unsupported rows and active semantics."""
from copy import deepcopy
import pytest
import wf_describe
from test_m1_balance import valid_row
from wf.studio.variant_rules import transform_row, transform_skill, change_element_row


@pytest.mark.parametrize("target", ["7", "10"])
def test_special_targets_preserved(target):
    row = valid_row()
    row[47:51] = ["34", target, "White", "ball_group"]
    out, manual = transform_row(row, "ability", "direct")
    assert out == row and manual


def test_noninitial_trigger_and_multilayer_194_preserved():
    row = valid_row()
    row[47], row[27] = "34", "1"
    assert transform_row(row, "ability", "direct")[0] == row
    assert transform_row(row, "ability", "direct")[1]
    row[5], row[97], row[98], row[102], row[104], row[109], row[110] = "1", "194", "5", "1", "20", "411", "0"
    row[100:102] = ["200000", "200000"]
    assert transform_row(row, "ability", "direct")[0] == row
    assert transform_row(row, "ability", "direct")[1]


@pytest.mark.parametrize("kind", ["520", "490", "534"])
def test_attack_slayer_stays_attack(kind):
    row = valid_row()
    row[47] = kind
    assert transform_row(row, "ability", "direct") == (row, [])


def test_attack_point_up_slayer_is_damage_condition_not_attack_bonus():
    row = valid_row()
    row[47] = "98"  # AttackPointUpSlayer, distinct from *AttackSlayer
    out, manual = transform_row(row, "ability", "direct")
    assert out == row and manual


def test_during_attack_slayer_is_not_instant_direct_attack():
    row = valid_row()
    row[5], row[109] = "1", "223"  # DebuffAttackSlayer
    assert transform_row(row, "ability", "direct") == (row, [])


@pytest.mark.parametrize("mode,kind", [("0", "521"), ("0", "201"), ("0", "202"),
                                      ("1", "252"), ("1", "45"), ("1", "46"), ("0", "223"), ("0", "224"), ("0", "225")])
def test_unmapped_direct_attack_is_manual(mode, kind):
    row = valid_row()
    row[5] = mode
    row[47 if mode == "0" else 109] = kind
    out, manual = transform_row(row, "ability", "ability")
    assert out == row and manual


def test_during_unique_keeps_unique_condition():
    row = valid_row()
    row[5], row[97], row[109], row[110], row[118] = "1", "0", "287", "5", "20"
    out, manual = transform_row(row, "ability", "direct")
    assert not manual and out[109] == "250" and out[118] == "20"


@pytest.mark.parametrize("name", ["ACDirectDamage", "ACPowerFlipDamage", "ACAbilityDamage", "ACSkillDamage"])
def test_all_damage_keeps_original_skill_zone(name):
    node = ["ActionDsl", [name, 10, 20, 1]]
    assert transform_skill(node, "all") == (node, [])


@pytest.mark.parametrize("name", ["ACAdditionalDirectAttack", "ACAdversity", "ACOiuchi", "ACSeparatedTerm", "ACSpecialEfficacy"])
def test_skill_unmapped_buffs_are_manual(name):
    node = [name, 1, 2, 3]
    out, manual = transform_skill(node, "direct")
    assert out == node and manual


def test_element_active_conditions_groups_and_dead_columns():
    row = valid_row()
    row[2], row[5], row[6], row[97], row[109], row[111] = "attack_white", "1", "97", "169", "70", "White/Human"
    row[85] = "(None)"
    row[49] = "White"  # inactive instant content
    out, manual = change_element_row(row, "ability", 4, 5)
    assert not manual
    assert out[2] == "attack_black" and out[6] == "98" and out[97] == "170" and out[109] == "71"
    assert out[111] == "Black/Human" and out[49] == "White"


def test_damage_cut_maps_but_720_and_element_damage_require_manual():
    kinds = {v["en"]: k for k, v in wf_describe.enum_options()["instant_content"].items()}
    row = valid_row()
    row[47] = kinds["DamageCutWhite"]
    out, manual = change_element_row(row, "ability", 4, 5)
    assert not manual and out[47] == kinds["DamageCutBlack"]
    for kind in ["720", next(k for n, k in kinds.items() if "EnemyDamageBy" in n)]:
        row[47], row[73], row[36] = kind, "5", "White"
        before = deepcopy(row)
        out, manual = change_element_row(row, "ability", 5, 4)
        assert manual and out == before and row == before

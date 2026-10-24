"""Client action loaders accept plain resource paths as well as path$program."""
import pytest

import wf_quest_lib as nodes
from wf.dsl.references import ACTION_SKILL, DSL_SUFFIX, linked_programs, program_logical
from test_m11_dsl_gate import ABILITY, ROOT, ability, csv_row, data, dsl, run

BARE = 'battle/action/skill/ability/ability_skill_spheal_mascot_leader' + DSL_SUFFIX
CHILD = 'battle/action/skill/ability/plain_child' + DSL_SUFFIX


def bare_data():
    raw = data()
    raw[ABILITY] = nodes.build_node({'1001': ability(BARE)})
    raw[BARE] = dsl(['Command', ['Trace', 'safe']])
    return raw


def test_existing_bare_629_root_does_not_block_unrelated_enemy_dsl():
    raw = bare_data()
    enemy = 'battle/action/enemy/action/studio_behavior/independent' + DSL_SUFFIX
    report = run(raw, {enemy: dsl(['Command', ['Trace', 'enemy']])})
    assert report['status'] == '满足'
    assert report['checked_programs'] == []


def test_changed_bare_629_root_still_checks_lifecycle():
    raw = bare_data()
    report = run(raw, {BARE: dsl(['Command', ['NotifyPowerflipEnd', 0]])})
    assert report['status'] == '问题'
    assert report['checked_programs'] == [BARE]
    assert report['findings'][0]['command'] == 'NotifyPowerflipEnd'


def test_bare_transitive_child_and_cycle_cannot_hide_dangerous_change():
    raw = bare_data()
    raw[BARE] = dsl(['Command', ['Run', CHILD.removesuffix(DSL_SUFFIX)]])
    raw[CHILD] = dsl(['Command', ['Run', BARE.removesuffix(DSL_SUFFIX)]])
    report = run(raw, {CHILD: dsl(['NotifyPowerflipEnd', 0],
                                ['Run', BARE.removesuffix(DSL_SUFFIX)])})
    assert report['status'] == '问题'
    assert set(report['checked_programs']) == {BARE, CHILD}


def test_missing_bare_root_cannot_clear_unmapped_changed_child():
    raw = bare_data()
    del raw[BARE]
    report = run(raw, {CHILD: dsl(['NotifyPowerflipEnd', 0])})
    assert report['status'] == '问题'
    assert any(f.get('logical_path') == BARE for f in report['findings'])


def test_skill_fallback_bare_path_is_checked():
    raw = bare_data()
    raw[BARE] = dsl(['Command', ['SetPowerFilpSuppress', True]])
    raw[ACTION_SKILL] = nodes.build_node({'test': {'1': csv_row(
        [''] * 7 + [BARE.removesuffix(DSL_SUFFIX)])}})
    report = run(raw, {ABILITY: nodes.build_node({'1001': ability('')})})
    assert report['status'] == '问题'
    assert report['findings'][0]['command'] == 'SetPowerFilpSuppress'


@pytest.mark.parametrize('path', [
    'battle/action/../bad', 'battle/action//bad', 'battle/action/./bad',
    'battle/action/bad$', 'battle/action/bad$$root', 'battle/action/',
    'battle/action/bad root', 'battle/action/bad?x=1', 'battle/effect/bad',
])
def test_malformed_or_non_action_bare_roots_remain_blocking(path):
    raw = data()
    assert program_logical(path) is None
    report = run(raw, {ABILITY: nodes.build_node({'1001': ability(path)})})
    assert report['status'] == '问题'
    assert any('invalid kind 629 action_path' in f['message'] for f in report['findings'])


def test_action_discovery_retains_dollar_paths_and_ignores_effects_and_prose():
    assert linked_programs([ROOT, BARE.removesuffix(DSL_SUFFIX),
                            'battle/effect/normal/normal', 'describes ' + BARE]) == {ROOT, BARE}

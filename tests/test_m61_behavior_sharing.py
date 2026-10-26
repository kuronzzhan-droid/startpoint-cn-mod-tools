"""Actual entry multiplicity and all consumers constrain reusable damage clones."""
import pytest
import wf_quest_lib as codec

from test_boss_behavior import behavior_editor, request
from wf.boss import schema as s
from wf.boss.behavior import apply_behavior
from wf.boss.behavior_identity import GENERAL_FUNNEL, WATCH
from wf.boss.behavior_wire import compress, decode_wire, write_tree
from wf.boss.edit_state import BossEditState
from wf.boss.reader import BossReader
from wf.rules.boss_preload import walk
from wf.studio.boss import compile_boss
from wf.studio.source import StudioSource
from wf.view.base149 import join

QUEST = 'hard_multi:1006/1'


def selected(state, code=None):
    return next(e for e in BossReader(state).show(QUEST)['enemies']
                if e['code'] == code or code is None and e['code'].startswith('studio_behavior_'))


def attack(state, program):
    tree = decode_wire(state.raw(program + '.action.dsl.amf3.deflate'))['tree']
    return next(n[6] for n in walk(tree) if isinstance(n, list) and n[:1] == ['CreateNormalAttack'])


def shared_bosses(tmp_path):
    editor = behavior_editor(tmp_path)
    zone = codec.parse_node(editor.source.view.files[s.ZONE])
    row = s.parse_rows(zone['zone']['0'])[0]
    row[27:29] = ['1', 'donor']
    zone['zone']['0'] = join(row)
    editor.source.view.files[s.ZONE] = codec.build_node(zone)
    state = BossEditState(editor.source)
    apply_behavior(state, QUEST, request(slot=1, damageMultiplier=2))
    first = selected(state)['code']
    apply_behavior(state, QUEST, {'operation': 'behavior_replace', 'enemyCode': 'donor',
                   'slot': 1, 'sourceEnemyCode': first, 'sourceSlot': 1})
    return state, first


@pytest.mark.parametrize('edited', ['org', 'donor'])
def test_damage_edits_do_not_change_another_boss_sharing_the_owned_program(tmp_path, edited):
    state, first = shared_bosses(tmp_path)
    original = selected(state, first)['row'][111]
    before = state.raw(original + '.action.dsl.amf3.deflate')
    apply_behavior(state, QUEST, {'operation': 'behavior_parameters', 'enemyCode': edited,
                                 'slot': 1, 'damageMultiplier': 3})
    programs = {e['row'][111] for e in BossReader(state).show(QUEST)['enemies'] if e['kind'] == 'boss'}
    assert len(programs) == 2
    assert state.raw(original + '.action.dsl.amf3.deflate') == before
    assert sorted(attack(state, p)[0]['min'] for p in programs) == [2.0, 6.0]
    paths = set(state.client)
    apply_behavior(state, QUEST, {'operation': 'behavior_parameters', 'enemyCode': edited,
                                 'slot': 1, 'damageMultiplier': 2})
    assert set(state.client) == paths
    assert state.raw(original + '.action.dsl.amf3.deflate') == before


@pytest.mark.parametrize('consumer', ['initial', 'watch', 'funnel', 'indirect_watch'])
def test_owned_program_used_outside_marker_slots_is_not_mutated(tmp_path, consumer):
    editor = behavior_editor(tmp_path)
    state = BossEditState(editor.source)
    apply_behavior(state, QUEST, request(slot=1, damageMultiplier=2))
    enemy = selected(state)
    row = list(enemy['row'])
    original = row[111]
    if consumer == 'initial':
        row[109] = original
        state.set_leaf(s.GENERAL_BOSS, enemy['path'], join(row))
    elif consumer == 'funnel':
        state.set_leaf(GENERAL_FUNNEL, ['external'], {'100': '4,' + original}, new=True)
    else:
        root = original
        if consumer == 'indirect_watch':
            root = 'battle/action/watch_bridge'
            state.set_raw(root + '.action.dsl.amf3.deflate', compress(write_tree(['Invoke', original])), new=True)
        state.set_leaf(WATCH, ['1', enemy['code']], {row[42]: {
            '2': {'funnel': {'0': join(['0', 'idle', root])}}}}, new=True)
    before = state.raw(original + '.action.dsl.amf3.deflate')
    apply_behavior(state, QUEST, request(slot=1, damageMultiplier=3))
    assert selected(state)['row'][111] != original
    assert state.raw(original + '.action.dsl.amf3.deflate') == before


def test_same_slot_across_level_bands_remains_isolated(tmp_path):
    state = BossEditState(behavior_editor(tmp_path).source)
    apply_behavior(state, QUEST, request(slot=1, damageMultiplier=2))
    enemy = selected(state)
    original = enemy['row'][111]
    state.set_leaf(s.GENERAL_BOSS, [enemy['code'], '200'], join(enemy['row']), new=True)
    logical = s.QUEST_TABLES['hard_multi']
    row = s.parse_rows(state.table(logical)['1006']['1'])[0]
    row[107] = '150'
    state.set_leaf(logical, ['1006', '1'], join(row))
    apply_behavior(state, QUEST, request(slot=1, damageMultiplier=3))
    high = selected(state)['row'][111]
    assert high != original and attack(state, original)[0]['min'] == 2.0
    row[107] = '100'
    state.set_leaf(logical, ['1006', '1'], join(row))
    apply_behavior(state, QUEST, request(slot=1, damageMultiplier=5))
    assert attack(state, high)[0]['min'] == 6.0
    assert attack(state, selected(state)['row'][111])[0]['min'] == 10.0


def test_revisiting_an_old_source_cannot_overwrite_an_existing_shared_clone(tmp_path):
    state, first = shared_bosses(tmp_path)
    old = selected(state, first)['row'][111]
    apply_behavior(state, QUEST, request(slot=1, damageMultiplier=3))
    newer = selected(state, first)['row'][111]
    apply_behavior(state, QUEST, request('behavior_replace', slot=2, sourceEnemyCode=first, sourceSlot=1))
    donor = next(e['code'] for e in BossReader(state).show(QUEST)['enemies']
                 if e['kind'] == 'boss' and e['code'] != first)
    apply_behavior(state, QUEST, request('behavior_replace', slot=1, sourceEnemyCode=donor, sourceSlot=1))
    assert selected(state, first)['row'][111] == old
    before = state.raw(newer + '.action.dsl.amf3.deflate')
    apply_behavior(state, QUEST, request(slot=1, damageMultiplier=5))
    latest = selected(state, first)['row'][111]
    assert latest not in (old, newer)
    assert state.raw(newer + '.action.dsl.amf3.deflate') == before
    assert attack(state, latest)[0]['min'] == 10.0


@pytest.mark.parametrize('roots', ['battle/action/a,battle/action/b', 'battle/action/b,battle/action/b'])
def test_repeat_budget_preserves_explicit_root_occurrences_in_preview_and_compile(tmp_path, roots):
    editor = behavior_editor(tmp_path)
    table = codec.parse_node(editor.source.view.files[s.GENERAL_BOSS])
    row = s.parse_rows(table['donor']['100'])[0]
    row[112] = roots
    table['donor']['100'] = join(row)
    editor.source.view.files[s.GENERAL_BOSS] = codec.build_node(table)
    editor.source.view.files['battle/action/a.action.dsl.amf3.deflate'] = compress(write_tree(['Invoke', 'battle/action/b']))
    target = 'battle/action/b.action.dsl.amf3.deflate'
    editor.source.view.files[target] = compress(write_tree(['Repeat', 1, 400, '*', ['Block', []]]))
    payload = request('behavior_replace', slot=1, sourceEnemyCode='donor', sourceSlot=2)
    draft = editor.apply(QUEST, payload)['changeset']
    editor.source.view.files[target] = compress(write_tree(['Repeat', 1, 600, '*', ['Block', []]]))
    editor.source = StudioSource(editor.source.view)
    preview = editor.preview(QUEST, payload)
    assert not preview['ok'] and 'closure budget' in str(preview)
    with pytest.raises(ValueError, match='closure budget'):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)

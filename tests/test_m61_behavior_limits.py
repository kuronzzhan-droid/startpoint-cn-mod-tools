"""Repeated edits retain one owned closure; repetition is bounded as a whole."""
import pytest

from wf.boss.behavior import apply_behavior
from wf.boss.behavior_guards import reject_loops
from wf.boss.behavior_wire import compress, decode_wire, write_tree
from wf.boss.edit_state import BossEditState
from wf.boss.reader import BossReader
from wf.rules.boss_preload import walk
from test_boss_behavior import behavior_editor, request


def repeat(count, body=None):
    return ['Repeat', 1, count, '*', body or ['Block', []]]


@pytest.mark.parametrize('closure', [
    {'battle/action/a': repeat(999, repeat(999))},
    {'battle/action/a': ['Block', [repeat(600), repeat(600)]]},
    {'battle/action/a': repeat(100, ['Invoke', 'battle/action/b']), 'battle/action/b': repeat(10)},
    {'battle/action/a': repeat(600), 'battle/action/b': repeat(600)},
])
def test_repeat_limit_covers_nested_sibling_linked_and_multiple_roots(closure):
    with pytest.raises(ValueError, match='closure budget'):
        reject_loops(closure)


@pytest.mark.parametrize('count', [False, True, 1.5, 0, -1, float('inf'), float('nan')])
def test_repeat_count_requires_finite_positive_integer(count):
    with pytest.raises(ValueError, match='infinite/unbounded'):
        reject_loops({'battle/action/a': repeat(count)})


def test_bounded_closure_is_accepted():
    reject_loops({'battle/action/a': repeat(9, ['Invoke', 'battle/action/b']),
                  'battle/action/b': repeat(111)})


def test_repeated_damage_reuses_full_closure_without_changing_other_slot(tmp_path):
    editor = behavior_editor(tmp_path)
    view = editor.source.view
    leaf = view.files['battle/action/one.action.dsl.amf3.deflate']
    view.files['battle/action/one.action.dsl.amf3.deflate'] = compress(write_tree(
        ['Invoke', 'battle/action/leaf']))
    view.files['battle/action/leaf.action.dsl.amf3.deflate'] = leaf
    state = BossEditState(editor.source)
    apply_behavior(state, 'hard_multi:1006/1', request(slot=1, damageMultiplier=2))
    paths = {p for p in state.client if p.endswith('.action.dsl.amf3.deflate')}
    assert len(paths) == 2
    apply_behavior(state, 'hard_multi:1006/1', request(slot=1, damageMultiplier=3))
    assert {p for p in state.client if p.endswith('.action.dsl.amf3.deflate')} == paths
    attacks = [n[6] for p in paths for n in walk(decode_wire(state.client[p])['tree'])
               if isinstance(n, list) and n[:1] == ['CreateNormalAttack']]
    assert attacks == [[{'min': 6.0, 'max': 12.0}]]
    doc = BossReader(state).show('hard_multi:1006/1')
    assert doc['enemies'][0]['row'][112] == 'battle/action/two'


def test_editing_two_slots_with_same_source_does_not_overwrite_first_clone(tmp_path):
    editor = behavior_editor(tmp_path)
    state = BossEditState(editor.source)
    apply_behavior(state, 'hard_multi:1006/1', request('behavior_replace', slot=2,
                   sourceEnemyCode='org', sourceSlot=1))
    apply_behavior(state, 'hard_multi:1006/1', request(slot=1, damageMultiplier=2))
    first = BossReader(state).show('hard_multi:1006/1')['enemies'][0]['row'][111]
    original = state.raw(first + '.action.dsl.amf3.deflate')
    apply_behavior(state, 'hard_multi:1006/1', request(slot=2, damageMultiplier=3))
    row = BossReader(state).show('hard_multi:1006/1')['enemies'][0]['row']
    assert row[111] != row[112]
    assert state.raw(first + '.action.dsl.amf3.deflate') == original

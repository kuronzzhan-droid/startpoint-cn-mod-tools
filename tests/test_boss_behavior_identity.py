"""Reverse references must be checked from the candidate before renaming."""
import pytest
import wf_quest_lib as codec

from wf.boss.behavior import apply_behavior
from wf.boss.behavior_identity import GENERAL_FUNNEL, STANDARD_FUNNEL, WATCH, STATES
from wf.boss.behavior_wire import compress, write_tree
from wf.boss.edit_state import BossEditState
from wf.studio.boss import compile_boss
from test_boss_behavior import behavior_editor, request
from test_boss_model import row


@pytest.mark.parametrize('kind', ['damage_share', 'watch', 'alive', 'standard_damage', 'standard_watch'])
def test_incoming_identity_references_block_before_any_change(tmp_path, kind):
    editor = behavior_editor(tmp_path)
    state = BossEditState(editor.source)
    if kind == 'damage_share':
        # The later tier must also be inspected; the old builder checked one.
        state.set_leaf(GENERAL_FUNNEL, ['fin'], {'50': row(33, {}), '100': row(33, {32: 'org'})}, new=True)
    elif kind == 'watch':
        state.set_leaf(WATCH, ['1'], {'other': {'r': {'1': {'org': {'0': '0'}}}}}, new=True)
    elif kind == 'alive':
        state.set_leaf(STATES, ['other'], {'1': {'state': row(53, {29: 15, 30: 'org'})}}, new=True)
    else:
        tree = {'bG': 'org'} if kind == 'standard_damage' else {'au': [{'h': [{'a': ['T1', 'routine', 'org']}]}]}
        state.set_leaf(STANDARD_FUNNEL, ['funnel'], {'100': 'battle/enemy/funnel/test'}, new=True)
        state.set_raw('battle/enemy/funnel/test.esdl.amf3.deflate', compress(write_tree(tree)), new=True)
    before = list(state.changes)
    with pytest.raises(ValueError, match='identity-locked boss org.* -> org'):
        apply_behavior(state, 'hard_multi:1006/1', request(state='idle', intervalFrames=90))
    assert state.changes == before


def test_missing_identity_source_fails_closed_in_preview_and_saved_compile(tmp_path):
    editor = behavior_editor(tmp_path)
    draft = editor.apply('hard_multi:1006/1', request(state='idle', intervalFrames=90))['changeset']
    del editor.source.view.files[GENERAL_FUNNEL]
    from wf.studio.source import StudioSource
    editor.source = StudioSource(editor.source.view)
    preview = editor.preview('hard_multi:1006/1', request(state='idle', intervalFrames=90))
    assert not preview['ok'] and 'scan degraded' in str(preview)
    with pytest.raises(ValueError, match='scan degraded'):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)


def test_soft_self_watch_is_copied_to_renamed_boss(tmp_path):
    editor = behavior_editor(tmp_path)
    node = {'2': {'funnel': {'0': '0'}}}
    editor.source.view.files[WATCH] = codec.build_node({'1': {'org': {'r': node, 'org': node}}})
    state = BossEditState(editor.source)
    apply_behavior(state, 'hard_multi:1006/1', request(state='idle', intervalFrames=90))
    watches = state.table(WATCH)['1']
    alias = next(key for key in watches if key.startswith('studio_behavior_'))
    assert watches[alias]['r'] == watches['org']['r']
    assert watches[alias][alias] == watches['org']['org']

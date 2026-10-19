"""All authoring paths use the same GeneralBoss/Funnel named-position gate."""
import pytest
import wf_quest_lib as codec

from wf.boss import schema as s
from wf.boss.behavior_identity import GENERAL_FUNNEL, WATCH
from wf.boss.behavior_guards import check_behavior_positions
from wf.boss.behavior_wire import compress, decode_wire, write_tree
from wf.boss.reader import BossReader
from wf.rules.boss_terrain import terrain_checks
from wf.studio.boss import compile_boss
from wf.studio.source import StudioSource
from test_boss_behavior import behavior_editor, request


def position_program(editor, kind):
    view = editor.source.view
    target = 'battle/action/two.action.dsl.amf3.deflate'
    if kind == 'funnel':
        view.files[target] = compress(write_tree(['SpawnFunnel', ['Funnel', 'outer']]))
        view.files[GENERAL_FUNNEL] = codec.build_node({
            'outer': {'100': '4,battle/action/outer'}, 'inner': {'100': '4,battle/action/inner'}})
        view.files['battle/action/outer.action.dsl.amf3.deflate'] = compress(write_tree(
            ['SpawnFunnel', ['Funnel', 'inner']]))
        target = 'battle/action/inner.action.dsl.amf3.deflate'
    elif kind == 'linked':
        view.files[target] = compress(write_tree(['Invoke', 'battle/action/linked']))
        target = 'battle/action/linked.action.dsl.amf3.deflate'
    elif kind == 'watch':
        view.files[WATCH] = codec.build_node({'1': {'org': {'routine': {
            '2': {'funnel': {'0': '0,idle,battle/action/watched'}}}}}})
        target = 'battle/action/watched.action.dsl.amf3.deflate'
    view.files[target] = compress(write_tree(['CustomPosition', 'IL2']))


def add_position(editor):
    view = editor.source.view
    logical = 'battle/terrain/test.amf3.deflate'
    tree = decode_wire(view.files[logical])['tree']
    tree['layers'][0]['objects'].append({'type': 'CUSTOM_POSITION', 'name': 'IL2',
                                       'x': 20, 'y': 20, 'width': 0, 'height': 0})
    view.files[logical] = compress(write_tree(tree))
    editor.source = StudioSource(view)


@pytest.mark.parametrize('kind', ['direct', 'linked', 'funnel', 'watch'])
def test_custom_positions_required_in_every_action_closure(tmp_path, kind):
    editor = behavior_editor(tmp_path)
    position_program(editor, kind)
    doc = BossReader(editor.source).show('hard_multi:1006/1')
    checks = terrain_checks(doc, view=editor.source)
    assert checks[1]['blocking'] and 'IL2' in str(checks[1]['issues'])
    add_position(editor)
    doc = BossReader(editor.source).show('hard_multi:1006/1')
    assert not terrain_checks(doc, view=editor.source)[1]['blocking']
    # Position present only in another wave cannot satisfy the active wave.
    doc['terrain']['waves'].append({'name': 'other', 'objects': doc['terrain']['waves'][0]['objects']})
    doc['terrain']['waves'][0]['objects'] = [o for o in doc['terrain']['waves'][0]['objects']
                                         if o.get('name') != 'IL2']
    assert 'IL2' in str(terrain_checks(doc, view=editor.source)[1]['issues'])


def test_borrow_blocks_in_preview_and_saved_compile(tmp_path):
    editor = behavior_editor(tmp_path)
    view = editor.source.view
    table = codec.parse_node(view.files[s.GENERAL_BOSS])
    donor = s.parse_rows(table['donor']['100'])[0]
    donor[112] = 'battle/action/borrow'
    table['donor']['100'] = ','.join(donor)
    view.files[s.GENERAL_BOSS] = codec.build_node(table)
    logical = 'battle/action/borrow.action.dsl.amf3.deflate'
    view.files[logical] = view.files['battle/action/two.action.dsl.amf3.deflate']
    req = request('behavior_replace', slot=1, sourceEnemyCode='donor', sourceSlot=2)
    draft = editor.apply('hard_multi:1006/1', req)['changeset']
    view.files[logical] = compress(write_tree(['CustomPosition', 'IL2']))
    editor.source = StudioSource(view)
    assert 'IL2' in str(editor.preview('hard_multi:1006/1', req))
    with pytest.raises(ValueError, match='IL2'):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)


def test_delete_blocks_in_preview_and_saved_compile(tmp_path):
    editor = behavior_editor(tmp_path)
    add_position(editor)
    deletion = {'operation': 'terrain_position', 'layer': '0', 'name': 'IL2', 'action': 'delete'}
    draft = editor.apply('hard_multi:1006/1', deletion)['changeset']
    position_program(editor, 'direct')
    editor.source = StudioSource(editor.source.view)
    assert 'IL2' in str(editor.preview('hard_multi:1006/1', deletion))
    with pytest.raises(ValueError, match='IL2'):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)


def test_native_missing_action_input_is_pending_but_borrow_stays_blocked(tmp_path):
    editor = behavior_editor(tmp_path)
    del editor.source.view.files['battle/action/two.action.dsl.amf3.deflate']
    document = BossReader(editor.source).show('hard_multi:1006/1')
    for result in (terrain_checks(document, view=editor.source)[1],
                   check_behavior_positions(editor.source, document)):
        assert result['status'] == '待验证' and not result['blocking']
        assert 'battle/action/two' in str(result['limitations'])
    req = request('behavior_replace', slot=1, sourceEnemyCode='donor', sourceSlot=2)
    assert not editor.preview('hard_multi:1006/1', req)['ok']

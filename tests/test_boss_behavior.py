"""Meaningful behavior regressions: wire losslessness, isolation, and gates."""
import base64
import copy
import hashlib
import json

import pytest
import wf_quest_lib as codec
from wf.boss import schema as s
from wf.boss.behavior import apply_behavior
from wf.boss.behavior_guards import check_behavior_positions, reject_loops
from wf.boss.behavior_model import STATES, read_behavior
from wf.boss.behavior_wire import compress, decode_wire, write_tree
from wf.boss.edit_state import BossEditState
from wf.boss.esdl import decode_esdl, encode_esdl, transform
from wf.boss.reader import BossReader
from wf.studio.boss import compile_boss
from test_studio_boss_checks import fixture_editor
from test_boss_model import csv_row, row


def behavior_editor(tmp_path):
    editor = fixture_editor(tmp_path); view = editor.source.view
    from wf.boss.behavior_identity import GENERAL_FUNNEL, STANDARD_FUNNEL, WATCH
    view.files[GENERAL_FUNNEL] = codec.build_node({'unrelated': {'100': row(33, {})}})
    view.files[WATCH] = codec.build_node({'2': {'unrelated': {'r': {'2': {'other': {'0': '0'}}}}}})
    view.files[STANDARD_FUNNEL] = codec.build_node({'unrelated': {'100': 'battle/enemy/funnel/unrelated'}})
    view.files['battle/enemy/funnel/unrelated.esdl.amf3.deflate'] = compress(write_tree({}))
    tables = codec.parse_node(view.files[s.GENERAL_BOSS])
    for code in ('org', 'donor'):
        tables[code] = {'100': row(161, {0: 4, 1: code, 25: 'battle/marker/test', 41: 'p0',
            42: 'routine', 43: 'idle', 111: 'battle/action/one', 112: 'battle/action/two'})}
    view.files[s.GENERAL_BOSS] = codec.build_node(tables)
    view.files[STATES] = codec.build_node({'routine': {'1': {
        'idle': row(53, {0: 'idle', 1: 1, 2: 'idle', 3: 'idle', 22: 0, 23: 10, 46: 2, 47: 60}),
        'other': row(53, {0: 'other', 1: 1, 2: 'idle', 3: 'idle', 46: 3, 47: 1})}}})
    view.files['battle/marker/test.timeline.amf3.deflate'] = compress(write_tree({
        'sequences': [{'name': 'idle', 'begin': 1, 'end': 60}], 'points': [
            {'path': f'enemy_action{i}', 'frames': [{'begin': i * 4, 'data': [{'x': 0, 'y': 10}]}]} for i in (1, 2)]}))
    attack = ['ActionDsl', ['Block', [['Command', ['CreateNormalAttack', 0, 255, [], [], 0,
              [{'min': 1.0, 'max': 2.0}], [], False, False, False, False, False, [], [], ['None'], False]]]]]
    for name in ('one', 'two'):
        view.files[f'battle/action/{name}.action.dsl.amf3.deflate'] = compress(write_tree(attack))
    return editor


def request(operation='behavior_parameters', **kw):
    return {'operation': operation, 'enemyCode': 'org', **kw}


def test_behavior_draft_replay_isolates_and_roundtrips(tmp_path):
    editor = behavior_editor(tmp_path)
    before = copy.deepcopy(editor.source.view.files)
    editor.apply('hard_multi:1006/1', request(state='idle', intervalFrames=90, trialThreshold=15))
    editor.apply('hard_multi:1006/1', request(slot=1, damageMultiplier=2))
    draft = editor.store.save('hard_multi:1006/1')
    compiled = compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)
    assert editor.source.view.files == before
    updated = codec.parse_node(compiled['client'][s.GENERAL_BOSS])
    assert updated['org'] == codec.parse_node(before[s.GENERAL_BOSS])['org']
    changed = next(v for k, v in updated.items() if k.startswith('studio_behavior_'))
    cells = s.parse_rows(changed['100'])[0]
    routine = codec.parse_node(compiled['client'][STATES])[cells[42]]
    actual = s.parse_rows(routine['1']['idle'])[0]
    assert actual[23] == '15' and actual[47] == '90'
    assert routine['1']['other'] == codec.parse_node(before[STATES])['routine']['1']['other']
    tree = decode_wire(compiled['client'][cells[111] + '.action.dsl.amf3.deflate'])['tree']
    from wf.rules.boss_preload import walk
    assert next(n[6] for n in walk(tree) if isinstance(n,list) and n[:1] == ['CreateNormalAttack']) == [{'min': 2.0, 'max': 4.0}]
    assert all(value is None for key, value in draft['changes'][0]['params']['inputs']['client'].items()
               if key.startswith('battle/action/enemy/action/studio_behavior/'))


def test_marker_replace_keeps_original_and_requires_trigger(tmp_path):
    editor = behavior_editor(tmp_path)
    state = BossEditState(editor.source)
    apply_behavior(state, 'hard_multi:1006/1', request('behavior_replace', slot=1, sourceEnemyCode='org', sourceSlot=2))
    old = codec.parse_node(editor.source.view.files[s.GENERAL_BOSS])['org']
    assert state.table(s.GENERAL_BOSS)['org'] == old
    with pytest.raises(ValueError, match='not fired'):
        apply_behavior(BossEditState(editor.source), 'hard_multi:1006/1', request('behavior_replace', slot=1, sourceEnemyCode='org', sourceSlot=50))


def test_borrowed_loop_rejected_in_preview_and_compile(tmp_path):
    editor = behavior_editor(tmp_path)
    good = request('behavior_replace', slot=1, sourceEnemyCode='donor', sourceSlot=2)
    draft = editor.apply('hard_multi:1006/1', good)['changeset']
    editor.source.view.files['battle/action/two.action.dsl.amf3.deflate'] = compress(write_tree(['Repeat', 1, 9999, 'never_removed', ['Block', []]]))
    # Build fresh source caches for the changed input, matching a restarted server.
    from wf.studio.source import StudioSource
    editor.source = StudioSource(editor.source.view)
    with pytest.raises(ValueError, match='infinite'):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)
    preview = editor.preview('hard_multi:1006/1', good)
    assert preview['ok'] is False and 'infinite' in str(preview)


def test_borrowed_missing_preload_blocks(tmp_path):
    editor = behavior_editor(tmp_path)
    editor.source.view.files['battle/action/two.action.dsl.amf3.deflate'] = compress(write_tree(['ShowEffect', ['Path', 'battle/effect/missing/missing'], 'x']))
    with pytest.raises(ValueError, match='C8016'):
        apply_behavior(BossEditState(editor.source), 'hard_multi:1006/1', request('behavior_replace', slot=1, sourceEnemyCode='donor', sourceSlot=2))


def test_recursive_program_graph_rejected():
    with pytest.raises(ValueError, match='cycle'):
        reject_loops({'battle/action/a': ['battle/action/b'], 'battle/action/b': ['battle/action/a']})


def test_esdl_json_wire_roundtrip_preserves_noncanonical_and_invalid_utf8():
    # EnemyDsl.gender is a string; noncanonical U29 and GBK bytes are retained.
    raw = compress(b'\x0a\x0b\x01\x05ac\x06\x85\x03' + b'\x81' * 321 + b'\x01')
    # A simpler valid legacy string wire with a redundant U29 prefix.
    raw = compress(b'\x0a\x0b\x01\x05ac\x06\x80\x05\x81\x82\x01')
    document = decode_esdl(raw)
    assert document['tree']['gender'].encode('utf-8', 'surrogateescape') == b'\x81\x82'
    assert encode_esdl(json.loads(json.dumps(document, ensure_ascii=True))) == raw
    document['tree']['gender'] = 'Unknown'
    assert decode_esdl(encode_esdl(document))['tree']['gender'] == 'Unknown'


def test_esdl_parameters_and_missing_position(tmp_path):
    editor = behavior_editor(tmp_path); view = editor.source.view
    tree = {'gender': 'Unknown', 'initialPosition': ['Absolute', 'p0'], 'marker': 'battle/marker/test',
            'animations': ['idle'], 'forms': [{'states': [{'canonicalPath': 0, 'animation': 0,
                'terminationCondition': ['TimeElapsed', ['Frame', 60]], 'actions': [],
                'trial': ['HitCountCheck', {'content': ['DirectAttack', 10]}]}]}]}
    esdl = 'battle/enemy/boss/test.esdl.amf3.deflate'
    view.files[esdl] = compress(write_tree(transform(tree, encode=True)))
    view.files[s.STANDARD_BOSS] = codec.build_node({'org': {'100': 'Boss,battle/enemy/boss/test'}})
    zones = codec.parse_node(view.files[s.ZONE]); cells = s.parse_rows(zones['zone']['0'])[0]
    cells[23] = cells[25] = '0'; zones['zone']['0'] = csv_row(cells); view.files[s.ZONE] = codec.build_node(zones)
    with pytest.raises(ValueError, match='HitCountCheck.*integer'):
        apply_behavior(BossEditState(editor.source), 'hard_multi:1006/1', request(state='0', trialThreshold=10.5))
    state = BossEditState(editor.source)
    apply_behavior(state, 'hard_multi:1006/1', request(state='0', intervalFrames=80, trialThreshold=12))
    document = BossReader(state).show('hard_multi:1006/1')
    model = read_behavior(state, document); actual = model['enemies'][0]['decoded']['forms'][0]['states'][0]
    assert actual['terminationCondition'] == ['TimeElapsed', ['Frame', 80]]
    assert actual['trial'][1]['content'] == ['DirectAttack', 12]
    assert json.dumps(model, ensure_ascii=False).encode('utf-8')
    document['terrain']['waves'][0]['objects'] = []
    assert check_behavior_positions(state, document)['blocking']
    tree['forms'][0]['states'][0]['trial'] = ['DamageCheck', {'percentage': 5.0}]
    view.files[esdl] = compress(write_tree(transform(tree, encode=True)))
    state = BossEditState(editor.source)
    apply_behavior(state, 'hard_multi:1006/1', request(state='0', trialThreshold=6.25))
    changed = BossReader(state).show('hard_multi:1006/1')['enemies'][0]['row'][1] + '.esdl.amf3.deflate'
    actual = decode_esdl(state.raw(changed))['tree']['forms'][0]['states'][0]['trial']
    assert actual == ['DamageCheck', {'percentage': 6.25}]


@pytest.mark.parametrize('field', ['intervalFrames', 'trialThreshold'])
def test_general_integer_parameters_reject_fractional_values(tmp_path, field):
    editor = behavior_editor(tmp_path)
    with pytest.raises(ValueError, match='integer'):
        apply_behavior(BossEditState(editor.source), 'hard_multi:1006/1', request(state='idle', **{field: 10.5}))


def test_timeline_reports_marker_relative_frames(tmp_path):
    editor = behavior_editor(tmp_path)
    model = read_behavior(editor.source, BossReader(editor.source).show('hard_multi:1006/1'))
    states = model['enemies'][0]['states']; idle = next(s for s in states if s['name'] == 'idle')
    assert idle['duration_frames'] == 60
    assert [(a['slot'],a['begin']) for a in idle['actions']] == [(1,3),(2,7)]
    assert next(s for s in states if s['name'] == 'other')['duration_frames'] is None

def test_missing_preload_after_save_blocks_replay_compile(tmp_path):
    editor = behavior_editor(tmp_path)
    req = request('behavior_replace', slot=1, sourceEnemyCode='donor', sourceSlot=2)
    draft = editor.apply('hard_multi:1006/1', req)['changeset']
    editor.source.view.files['battle/action/two.action.dsl.amf3.deflate'] = compress(write_tree(
        ['ShowEffect', ['Path', 'battle/effect/missing/missing'], 'x']))
    from wf.studio.source import StudioSource
    editor.source = StudioSource(editor.source.view)
    assert not editor.preview('hard_multi:1006/1', req)['ok']
    with pytest.raises(ValueError, match='C8016'):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)


def test_same_boss_replacement_cannot_borrow_infinite_slot(tmp_path):
    editor = behavior_editor(tmp_path)
    editor.source.view.files['battle/action/two.action.dsl.amf3.deflate'] = compress(write_tree(
        ['Repeat', 1, 9999, 'forever', ['Block', []]]))
    with pytest.raises(ValueError, match='infinite'):
        apply_behavior(BossEditState(editor.source), 'hard_multi:1006/1',
            request('behavior_replace', slot=1, sourceEnemyCode='org', sourceSlot=2))


def test_new_derived_program_appearance_is_input_drift(tmp_path):
    editor = behavior_editor(tmp_path)
    draft = editor.apply('hard_multi:1006/1', request(slot=1, damageMultiplier=2))['changeset']
    inputs = draft['changes'][0]['params']['inputs']['client']
    created = next(k for k,v in inputs.items() if v is None and k.endswith('.action.dsl.amf3.deflate'))
    editor.source.view.files[created] = editor.source.view.files['battle/action/one.action.dsl.amf3.deflate']
    from wf.studio.source import StudioSource
    editor.source = StudioSource(editor.source.view)
    with pytest.raises(ValueError, match='drift|collision'):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)

def test_behavior_terrain_scene_sequences_keep_prior_edits(tmp_path):
    editor = behavior_editor(tmp_path); view = editor.source.view
    fields = codec.parse_node(view.files[s.FIELD]); fields['alternate'] = fields['field']
    view.files[s.FIELD] = codec.build_node(fields)
    quest = 'hard_multi:1006/1'
    editor.apply(quest, request(state='idle', intervalFrames=90))
    editor.apply(quest, {'operation':'terrain_position','layer':'0','name':'extra','action':'add','x':12,'y':34})
    editor.apply(quest, {'operation':'edit','parameters':{'scene':'alternate'}})
    editor.apply(quest, request(slot=1, damageMultiplier=2))
    editor.apply(quest, {'operation':'terrain_position','layer':'0','name':'extra','action':'update','x':56,'y':34})
    editor.apply(quest, {'operation':'edit','parameters':{'scene':'field'}})
    editor.apply(quest, request(state='idle', trialThreshold=20))
    draft = editor.store.save(quest)
    compiled = compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)
    class Unpacked:
        tip = '1.4.236'; zips = []
        def read_raw(self, logical):
            return compiled['client'].get(logical, view.files.get(logical)), 'unpacked'
    document = BossReader(Unpacked()).show(quest)
    assert document['field']['id'] == 'field'
    assert next(o for o in document['terrain']['waves'][0]['objects'] if o.get('name') == 'extra')['x'] == 56
    state = next(s for s in read_behavior(Unpacked(), document)['enemies'][0]['states'] if s['name'] == 'idle')
    assert state['duration_frames'] == 90 and state['trial']['threshold'] == '20'
    enemy = document['enemies'][0]
    assert '/studio_behavior/' in enemy['row'][111]


@pytest.mark.parametrize('suffix', ['damage', 'esdl'])
def test_initial_behavior_resource_collision_is_rejected(tmp_path, suffix):
    from wf.boss.behavior_clone import identity, set_owned_resource
    editor = behavior_editor(tmp_path)
    owner = identity('hard_multi:1006/1', 'org')
    if suffix == 'damage':
        scope = identity(owner, 'damage-slot:1')
        logical = 'battle/action/enemy/action/studio_behavior/' + identity(scope, 'battle/action/one') + '.action.dsl.amf3.deflate'
    else:
        logical = 'battle/enemy/boss/' + identity(owner, 'esdl') + '.esdl.amf3.deflate'
    original = compress(write_tree({'sentinel': 123}))
    editor.source.view.files[logical] = original
    state = BossEditState(editor.source)
    with pytest.raises(ValueError, match='collision'):
        if suffix == 'damage':
            apply_behavior(state, 'hard_multi:1006/1', request(slot=1, damageMultiplier=2))
        else:
            set_owned_resource(state, logical, compress(write_tree({'replacement': 456})))
    assert logical not in state.client and editor.source.view.files[logical] == original


def test_resource_created_in_same_replay_can_be_updated(tmp_path):
    from wf.boss.behavior_clone import set_owned_resource
    editor = behavior_editor(tmp_path); state = BossEditState(editor.source)
    logical = 'battle/enemy/boss/local.esdl.amf3.deflate'
    set_owned_resource(state, logical, b'first')
    set_owned_resource(state, logical, b'second')
    assert state.original[logical] is None and state.client[logical] == b'second'

def test_repeated_borrow_reuses_same_nontriggered_preload_shim(tmp_path):
    editor = behavior_editor(tmp_path); view = editor.source.view
    view.files['battle/action/two.action.dsl.amf3.deflate'] = compress(write_tree(['SpawnFunnel', ['Funnel', 'funnel']]))
    view.files['master/battle/boss/funnel/general_funnel.orderedmap'] = codec.build_node({'funnel': {'100': '2,battle/action/funnel'}})
    view.files['battle/action/funnel.action.dsl.amf3.deflate'] = view.files['battle/action/one.action.dsl.amf3.deflate']
    state = BossEditState(editor.source)
    for slot in (1, 2):
        apply_behavior(state, 'hard_multi:1006/1', request('behavior_replace', slot=slot, sourceEnemyCode='donor', sourceSlot=2))
    cells = BossReader(state).show('hard_multi:1006/1')['enemies'][0]['row']
    assert '/studio_behavior/' in cells[160]
    assert cells[159] == '(None)'
    resources = [item for item in state.changes if item.get('resource')]
    assert len(resources) == 1 and resources[0]['old'] is None

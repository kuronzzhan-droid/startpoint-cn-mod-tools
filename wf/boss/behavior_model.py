"""Read native GeneralBoss and EnemyDsl state-local timeline summaries."""
from __future__ import annotations

import re

from wf.rules.boss_common import CandidateView
from wf.rules.boss_preload import programs, walk
from . import schema as s
from .behavior_wire import decode_wire
from .esdl import decode_esdl

STATES = 'master/battle/boss/general_boss_state.orderedmap'


class Programs:
    def __init__(self, view):
        self.view, self.trees, self.missing = CandidateView(view), {}, set()

    def load(self, program):
        path = program if program.endswith('.action.dsl.amf3.deflate') else program + '.action.dsl.amf3.deflate'
        if program not in self.trees:
            raw = self.view.raw(path)
            self.trees[program] = decode_wire(raw)['tree'] if raw is not None else None
            if raw is None:
                self.missing.add(path)
        return self.trees[program]

    def closure(self, roots):
        queue, found = list(roots), {}
        while queue:
            program = queue.pop()
            if program in found:
                continue
            if len(found) >= 800:
                raise ValueError('behavior DSL closure exceeds 800 programs')
            tree = self.load(program); found[program] = tree
            queue.extend(p for item in walk(tree) if isinstance(item, str) for p in programs(item))
        return found

    def summary(self, roots):
        closure = self.closure(roots)
        effects, links = set(), []
        for program, tree in closure.items():
            for node in walk(tree):
                if isinstance(node, str) and node.startswith('battle/effect/'):
                    effects.add(node)
                if isinstance(node, list) and len(node) > 8 and node[0] == 'CreateCondition':
                    links.append({'program': program, 'trialKind': node[8], 'conditions': node[2],
                                  'source': 'CreateCondition.params[7]'})
        return {'dsl': sorted(closure), 'effects': sorted(effects), 'immunity_links': links,
                'missing': sorted(self.missing)}


def marker(view, path):
    if not s.present(path):
        return {'sequences': [], 'points': [], 'missing': True}
    raw = CandidateView(view).raw(path + '.timeline.amf3.deflate')
    return decode_wire(raw)['tree'] if raw is not None else {'sequences': [], 'points': [], 'missing': True}


def marker_actions(timeline, sequence, slots):
    if not sequence:
        return []
    begin, end = sequence['begin'], sequence['end']
    result = []
    for point in timeline.get('points', []):
        match = re.fullmatch(r'enemy_action(\d+)', point.get('path', ''))
        if not match:
            continue
        slot = int(match[1])
        for frame in point.get('frames', []):
            if frame.get('data') and begin <= frame['begin'] <= end:
                result.append({'slot': slot, 'begin': frame['begin'] - begin,
                               'end': None, 'trigger_frame': frame['begin'] - begin,
                               'interval_semantics': 'trigger_known_duration_unknown', 'marker_frame': frame['begin'],
                               'positions': frame['data'], 'dsl': programs(slots.get(slot, ''))})
    return result


def general_model(view, enemy, graph):
    row = enemy['row']; timeline = marker(view, s.cell(row, 25))
    slots = {slot: s.cell(row, 110 + slot) for slot in range(1, 51) if s.present(s.cell(row, 110 + slot))}
    routine = s.cell(row, 42)
    tree = (CandidateView(view).table(STATES) or {}).get(routine, {})
    sequences = {seq['name']: seq for seq in timeline.get('sequences', [])}
    states = []
    for path, text in s.iter_leaves(tree):
        cells = s.parse_rows(text)[0]; sequence = sequences.get(s.cell(cells, 3))
        actions = marker_actions(timeline, sequence, slots)
        roots = [p for action in actions for p in action['dsl']]
        trial = None
        if s.present(s.cell(cells, 22)):
            trial = {'kind': s.cell(cells, 22), 'threshold': s.cell(cells, 23),
                     'countdown': s.cell(cells, 24), 'wince': s.cell(cells, 25), 'next': s.cell(cells, 26),
                     'source': 'general_boss_state.c22-c26'}
        frames = int(cells[47]) if s.cell(cells, 46) == '2' and s.cell(cells, 47).isdigit() else None
        states.append({'id': '/'.join(path), 'name': path[-1], 'animation': s.cell(cells, 2),
                       'marker_sequence': s.cell(cells, 3), 'marker_interval': sequence,
                       'begin': 0, 'end': frames, 'duration_frames': frames,
                       'interval_semantics': 'scheduled_upper_bound' if frames is not None else 'conditional_or_loop_unknown',
                       'termination': {'kind': s.cell(cells, 46), 'value': s.cell(cells, 47)},
                       'next': s.cell(cells, 31), 'back': s.cell(cells, 40), 'trial': trial,
                       'invincible_by_phase_change': s.cell(cells, 15) == 'true',
                       'position': s.cell(cells, 50), 'actions': actions, **graph.summary(roots)})
    return {'kind': 'general', 'routine': routine, 'initial_state': s.cell(row, 43),
            'marker': s.cell(row, 25), 'slots': [{'slot': k, 'program': v} for k, v in slots.items()],
            'states': states, 'marker_missing': timeline.get('missing', False),
            'preload': graph.summary([p for value in [s.cell(row, 109), *slots.values()] for p in programs(value)])}


def standard_model(view, enemy, graph):
    logical = s.cell(enemy['row'], 1)
    logical = logical if logical.endswith('.esdl.amf3.deflate') else logical + '.esdl.amf3.deflate'
    raw = CandidateView(view).raw(logical)
    if raw is None:
        return {'kind': 'standard', 'logical': logical, 'missing': True, 'states': []}
    tree = decode_esdl(raw)['tree']; timeline = marker(view, tree.get('marker'))
    sequences = {seq['name']: seq for seq in timeline.get('sequences', [])}
    animations, states = tree.get('animations', []), []
    for form_number, form in enumerate(tree.get('forms', [])):
        for state in form.get('states', []):
            index = state.get('animation'); animation = animations[index] if isinstance(index, int) and 0 <= index < len(animations) else None
            condition = state.get('terminationCondition'); frames = None
            if isinstance(condition, list) and condition[:1] == ['TimeElapsed'] and condition[1][:1] == ['Frame']:
                frames = condition[1][1]
            actions = []
            for action in state.get('actions', []):
                value = action.get('filePath', '')
                program = value if value.startswith('battle/action/') else tree.get('action_base_path', '') + value
                event = action.get('event', []); at = 0 if event[:1] == ['OnStateEnter'] else frames if event[:1] == ['OnStateExit'] else None
                actions.append({'event': event, 'begin': at, 'end': at, 'dsl': [program],
                                'offset': [action.get('offsetX'), action.get('offsetY')]})
            roots = [p for action in actions for p in action['dsl']]
            states.append({'id': str(state['canonicalPath']), 'form': form_number, 'animation': animation,
                           'marker_sequence': animation, 'marker_interval': sequences.get(animation),
                           'begin': 0, 'end': frames, 'duration_frames': frames,
                       'interval_semantics': 'scheduled_upper_bound' if frames is not None else 'conditional_or_loop_unknown',
                           'termination': condition, 'next': state.get('next'), 'back': state.get('back'),
                           'trial': state.get('trial'), 'invincible_by_phase_change': state.get('invincibleByPhaseChange'),
                           'actions': actions, **graph.summary(roots)})
    return {'kind': 'standard', 'logical': logical, 'decoded': tree, 'states': states,
            'marker': tree.get('marker'), 'marker_missing': timeline.get('missing', False),
            'slots': [], 'slot_edit_supported': False}


def _display(value):
    if isinstance(value, str):
        return value.encode('utf-8', errors='backslashreplace').decode('utf-8')
    if isinstance(value, dict):
        return {key: _display(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_display(item) for item in value]
    return value


def read_behavior(view, document):
    graph, entries, seen = Programs(view), [], set()
    for enemy in document.get('enemies', []):
        key = enemy.get('code'), tuple(enemy.get('path') or [])
        if key in seen or enemy.get('kind') != 'boss':
            continue
        seen.add(key)
        if enemy.get('table') == s.GENERAL_BOSS:
            model = general_model(view, enemy, graph)
        elif enemy.get('table') == s.STANDARD_BOSS:
            model = standard_model(view, enemy, graph)
        else:
            model = {'kind': 'native-special', 'states': [], 'limitation': '原生特殊boss尚无通用状态映射'}
        entries.append({'enemyCode': enemy['code'], 'wave': enemy['wave'], 'level': enemy['level'], **model})
    return _display({'schema': 'wf-boss-behavior/1', 'display_escaped': True, 'enemies': entries,
            'timeline': {'schema': 'wf-boss-timeline/1', 'fps': 60, 'time_origin': 'state_entry',
                         'enemies': [{k: v for k, v in entry.items() if k != 'decoded'} for entry in entries],
                         'limitations': ['条件分支、循环和未知时长保留表达式；帧区间以每个状态进入时为零点，不模拟命中或运行时状态选择。']}})

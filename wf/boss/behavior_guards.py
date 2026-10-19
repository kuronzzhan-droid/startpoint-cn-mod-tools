"""Conservative gates for cross-boss borrowed programs and terrain references."""
from __future__ import annotations

from wf.rules.boss_common import CandidateView
from wf.rules.boss_preload import programs, walk
from wf.rules.catalog import result
from . import schema as s
from .atlas import _sheet
from .behavior_model import Programs
from .behavior_limits import reject_loops
from .esdl import decode_esdl

COLORS = {1: 'red', 2: 'blue', 3: 'yellow', 4: 'green', 5: 'white', 6: 'black', 7: 'colorless'}


def effect_dependencies(view, closure, element):
    source, animations, resolved_bases = CandidateView(view), set(), set()
    for tree in closure.values():
        for node in walk(tree):
            if isinstance(node, list) and len(node) >= 3 and node[0] == 'ResolveByElement':
                base, code = node[1], node[2]
                code = element if code == 255 else code
                if code not in COLORS:
                    raise ValueError(f'C8016: unresolved borrowed effect element {code}')
                name = base.rsplit('/', 1)[-1] + '_' + COLORS[code]
                animations.add(f'{base}/{name}/{name}'); resolved_bases.add(base)
    for tree in closure.values():
        animations.update(item for item in walk(tree) if isinstance(item, str)
                          and item.startswith('battle/effect/') and item not in resolved_bases)
    dependencies = set()
    for animation in animations:
        timeline, sheet = animation + '.timeline.amf3.deflate', _sheet(animation)
        if sheet is None or source.raw(timeline) is None or source.raw(sheet) is None:
            raise ValueError(f'C8016: borrowed effect preload resource missing: {animation}')
        atlas = sheet.removesuffix('.png') + '.atlas.amf3.deflate'
        layouts = [animation + suffix for suffix in ('.parts.amf3.deflate', '.frame.amf3.deflate')]
        present = [logical for logical in layouts if source.raw(logical) is not None]
        if source.raw(atlas) is None or not present:
            raise ValueError(f'C8016: borrowed effect atlas/layout preload missing: {animation}')
        dependencies.update((timeline, sheet, atlas, *present))
    return sorted(dependencies)


def borrowed_check(view, roots, receiver_row):
    graph = Programs(view); closure = graph.closure(roots)
    if graph.missing:
        raise ValueError('C8016: borrowed DSL preload missing: ' + ', '.join(sorted(graph.missing)))
    reject_loops(closure)
    # Standard/zako summons and state-dependent foreign mechanisms cannot be
    # inferred from a bare program. General Funnel is handled with fixed shims.
    for program, tree in closure.items():
        for node in walk(tree):
            if isinstance(node, list) and node:
                if node[0] == 'SpawnAlterEgo':
                    raise ValueError(f'C8016: borrowed alter-ego preload closure is unproven: {program}')
                if node[0] == 'SpawnFunnel' and (len(node) < 2 or not isinstance(node[1], list) or node[1][:1] != ['Funnel']):
                    raise ValueError(f'C8016: borrowed non-Funnel summon preload is unproven: {program}')
    return closure, effect_dependencies(view, closure, int(receiver_row[0]))


def _absolute_positions(tree):
    return {node[1] for node in walk(tree) if isinstance(node, list) and len(node) == 2
            and node[0] == 'Absolute' and isinstance(node[1], str)}


def check_behavior_positions(view, document):
    source, issues, checked = CandidateView(view), [], 0
    waves = {str(wave.get('name')): {obj.get('name') for obj in wave.get('objects', [])
             if obj.get('type') == 'CUSTOM_POSITION'} for wave in document.get('terrain', {}).get('waves', [])}
    from wf.rules.boss_references import routine_positions
    required, failures, pending = routine_positions(document, view)
    issues.extend(failures)
    for (wave, code, routine), positions in required.items():
        checked += 1
        for name in sorted(positions - waves.get(wave, set())):
            issues.append(f'{code}: routine/action 引用缺失站位 {name}（C14102）')
    seen = set()
    for enemy in document.get('enemies', []):
        if enemy.get('table') != s.STANDARD_BOSS or str(enemy.get('wave')) not in waves:
            continue
        logical = s.cell(enemy.get('row', []), 1)
        logical = logical if logical.endswith('.esdl.amf3.deflate') else logical + '.esdl.amf3.deflate'
        key = logical, str(enemy['wave'])
        if key in seen:
            continue
        seen.add(key); checked += 1
        raw = source.raw(logical)
        if raw is None:
            issues.append(f'{enemy["code"]}: esdl 缺失 {logical}')
            continue
        for name in sorted(_absolute_positions(decode_esdl(raw)['tree']) - waves[str(enemy['wave'])]):
            issues.append(f'{enemy["code"]}: esdl 引用缺失站位 {name}（C14102）')
    return result('boss.behavior-positions', '问题' if issues else '满足' if checked else '不适用',
                  ('逐波核对 GeneralBoss/Funnel 动作闭包及 StandardBoss esdl 命名站位' + (': ' + '; '.join(issues) if issues else '')), blocking=bool(issues), issues=issues, checked=checked,
                  limitations=pending, evidence_nature='源码推断',
                  source='CustomPosition / PositionKind.Absolute / routine c50', rule_version='1.1')

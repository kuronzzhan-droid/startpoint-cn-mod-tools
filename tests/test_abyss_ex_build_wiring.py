"""Execute production main's clone/finalization wiring with synthetic tables."""
import ast
import copy
import inspect
from types import SimpleNamespace

import pytest

from wf.tools.rogue import rogue_build as b


def main_body():
    return ast.parse(inspect.getsource(b.main)).body[0].body


def compile_scope(body, **state):
    scope = dict(vars(b))
    scope.update(state)
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    exec(compile(module, inspect.getsourcefile(b.main), 'exec'), scope)
    return scope


def boss_row(action):
    row = [''] * 162
    row[109] = action
    row[111] = 'battle/action/enemy/action/native$main'
    return b.join(row, False)


@pytest.mark.parametrize('mode', ['ex', 'normal'])
def test_pure_hp_clone_uses_stripped_donor_without_mutating_source(mode):
    # Match the existing main-routine tests: only nonlocal bindings are adapted
    # to globals; the production function body and all clone branches run intact.
    node = next(n for n in main_body()
                if isinstance(n, ast.FunctionDef) and n.name == 'make_caster_boss')
    for child in ast.walk(node):
        if isinstance(child, ast.Nonlocal):
            child.__class__ = ast.Global
    source = {'80': boss_row(b.abyss_ex.FIVE_MODE_PREFIXES[0]+'s1'),
              '100': boss_row(b.abyss_ex.FIVE_MODE_PREFIXES[1]+'entrance')}
    original = copy.deepcopy(source)
    scope = compile_scope([node], BUILD_MODE=mode, PRIVATE_PREFIX='private_',
                          gb_t={'donor': source}, bl_t={'donor': 'level'}, gv_t={}, ew_t=None,
                          code_refs={}, clone_sources={}, clone_watch_alias_counts={},
                          caster_dirty=False, general_state_dirty=False)
    code = scope['make_caster_boss'](30, 'donor')
    assert code == 'private_boss30'
    clone = scope['gb_t'][code]
    expected = (b.abyss_ex.without_five_curse(source, b.cells, b.join)
                if mode == 'ex' else source)
    assert clone == expected
    assert clone is not source and scope['caster_dirty']
    clone['80'] = 'changed'
    assert source == original
    assert scope['clone_sources'][code] == 'donor'


def finalization_body():
    # Bound the actual production tail by the preceding audit phase and first
    # write-phase declaration. Removing/moving the EX guard must break the test.
    body = main_body()
    start = next(i for i, n in enumerate(body) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == 'args.audit_json or args.audit_report') + 1
    end = next(i for i, n in enumerate(body) if isinstance(n, ast.AnnAssign)
               and isinstance(n.target, ast.Name) and n.target.id == 'written')
    wrapper = ast.parse('def finalize():\n    return 42').body[0]
    wrapper.body = body[start:end] + wrapper.body
    return wrapper


@pytest.mark.parametrize('write', [False, True])
def test_final_clone_guard_runs_before_candidate_collection_and_write_phase(monkeypatch, write):
    from wf.tools.rogue import rogue_candidate

    zone = [''] * 35
    zone[22:31] = ['1', '1', 'private_boss30', '1', 'private_boss30',
                   '1', 'private_boss30_2', '1', 'private_boss30_2']
    quest = [''] * 99
    quest[98] = 'field'
    clones = ['private_boss30', 'private_boss30_2']
    generals = {code: {'100': boss_row('')} for code in clones}
    collected, saved, checked = [], [], []
    monkeypatch.setattr(rogue_candidate, 'collect_candidate', lambda *a, **k: 'candidate')
    monkeypatch.setattr(b.q, 'save_table', lambda *a, **k: saved.append(a))
    real_check = b.abyss_ex.assert_final_clones

    def check(*args):
        checked.append(args)
        return real_check(*args)

    monkeypatch.setattr(b.abyss_ex, 'assert_final_clones', check)
    scope = compile_scope([finalization_body()], BUILD_MODE='ex', PRIVATE_PREFIX='private_',
                          floor_recs=[{'pick': {'runtime_bosses': clones}}],
                          quest_rows={'30': quest}, fd_t={'field': 'name,terrain,zone'},
                          zone_t={'zone': {'0': b.join(zone, False)}}, gb_t=generals,
                          candidate_sink=collected.append, args=SimpleNamespace(write=write))
    # Control: valid state reaches candidate collection and the write boundary.
    assert scope['finalize']() == (42 if write else 0)
    assert collected == ['candidate'] and len(checked) == 1
    assert checked[0][:6] == ('field', scope['fd_t'], scope['zone_t'], generals, clones, 'private_')
    collected.clear()
    # A contaminated final clone must return 1 before either downstream phase.
    generals[clones[1]]['100'] = boss_row(b.abyss_ex.FIVE_MODE_PREFIXES[1]+'entrance')
    assert scope['finalize']() == 1
    assert len(checked) == 2 and not collected and not saved

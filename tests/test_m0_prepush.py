"""Prepush migration tests using only fixtures under this worktree."""
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from uuid import uuid4
import zipfile

import pytest

import wf_prepush_check as compat
from wf.deliver import prepush as p
from wf.deliver import prepush_chain


@pytest.fixture
def fixture_dir():
    root = Path(__file__).resolve().parents[1] / 'work/m0/prepush-tests'
    directory = root / uuid4().hex
    directory.mkdir(parents=True)
    yield directory
    assert directory.resolve().is_relative_to(root.resolve())
    shutil.rmtree(directory)


def make_zip(directory, version, payload):
    archive = directory / f'pinball-1.4.{version - 1}-1.4.{version}-1-fixture.zip'
    with zipfile.ZipFile(archive, 'w') as zf:
        for name, raw in payload.items():
            zf.writestr(name, raw)
    return archive


def test_layered_view_uses_numeric_chain_order_and_zip_override(fixture_dir):
    logical = 'master/item/item.orderedmap'
    name = p.member('upload', logical)
    a = make_zip(fixture_dir, 9, {name: b'old'})
    b = make_zip(fixture_dir, 10, {name: b'new'})
    assert p.list_chain(fixture_dir) == [a, b]
    assert p.list_chain(fixture_dir, p.vkey('1.4.9')) == [a]
    view = p.View([a, b], None)
    assert view.raw(logical) == b'new'
    assert view.source(logical) == b.name
    for archive in view._zf.values():
        archive.close()


def test_chain_reports_bad_member_and_integrity(fixture_dir, monkeypatch):
    archive = make_zip(fixture_dir, 2, {'unsafe-name.txt': b'bad'})
    manifest = {'patches': [{'type': 'patch', 'enabled': True, 'archive': archive.name,
                           'version': '1.4.2', 'depends_on': '1.4.1',
                           'archive_integrity': [{'name': archive.name, 'sha256': '0' * 64,
                                                  'size': 1, 'members': 8}]}]}
    monkeypatch.setattr(prepush_chain, 'run_kulo35', lambda *args: None)
    rep = p.Report(set())
    p.check_chain(SimpleNamespace(server_dir=fixture_dir), manifest, fixture_dir,
                  {archive.name}, rep, {})
    identifiers = {finding.fid.split(':')[0] for finding in rep.items}
    assert {'chain.sha256', 'chain.size', 'chain.members', 'chain.member_path'} <= identifiers
    assert rep.count('ERROR') == 4


def test_companion_checks_c8601_and_downgrades_only_explicit_allowlist(fixture_dir):
    tables = {p.ITEM: {}, p.ITEM_QUEST_SEARCH: {}, p.EII: {'77': 'fixture'}, p.EII_LEVEL: {}}
    view = SimpleNamespace(table=lambda name: tables.get(name))
    args = SimpleNamespace(server_dir=fixture_dir, custom_item_min=10000300)
    rep = p.Report(set())
    p.check_companion(args, view, None, rep, set())
    assert [(f.level, f.fid) for f in rep.items] == [('ERROR', 'companion.eii_level:77')]
    allowed = p.Report({'companion.eii_level:77'})
    p.check_companion(args, view, None, allowed, set())
    assert allowed.count('ERROR') == 0 and allowed.count('WARN') == 1


def test_cli_compatibility_and_json_output(fixture_dir, capsys):
    active = fixture_dir / 'active'
    active.mkdir()
    output = fixture_dir / 'report.json'
    assert compat.main is p.main
    result = compat.main(['--server-dir', str(fixture_dir), '--active', str(active),
                          '--only', 'text,companion', '--json', str(output)])
    assert result == 0
    report = json.loads(output.read_text('utf-8'))
    assert {f['fid'] for f in report['findings']} == {'text.skipped', 'companion.item.skipped'}
    assert 'ERROR 0' in capsys.readouterr().out


def test_cli_missing_active_returns_environment_error(fixture_dir, capsys):
    assert p.main(['--server-dir', str(fixture_dir)]) == 2
    assert '补丁目录不存在' in capsys.readouterr().out


def test_skill_description_reports_wrong_table_and_partial_tier(fixture_dir):
    character = ','.join([''] * 8 + ['skill'])
    before_text = ','.join([''] * 4 + ['Name', 'Old'])
    after_text = ','.join([''] * 4 + ['Name', 'Wrong table change'])
    common = {p.CHARACTER: {'123': character}}
    previous = {**common, p.ACTION_SKILL: {'skill': {'1': 'Name,Old', '2': 'Name,Old'}},
                p.CHARACTER_TEXT: {'123': before_text}}
    current = {**common, p.ACTION_SKILL: {'skill': {'1': 'Name,New', '2': 'Name,Old'}},
               p.CHARACTER_TEXT: {'123': after_text}}
    args = SimpleNamespace(server_dir=fixture_dir, git_since=None)
    view = SimpleNamespace(table=lambda name: current.get(name))
    old = SimpleNamespace(table=lambda name: previous.get(name))
    rep = p.Report(set())
    p.check_text(args, view, old, rep)
    assert rep.count('ERROR') == 1
    assert rep.count('WARN') == 1
    assert any(f.fid == 'text.partial_tier:skill' for f in rep.items)


def test_level_gap_is_error_when_new_and_warning_when_historical():
    quest_name, level_column = p.QUEST_TABLES[0]
    quest = [''] * (level_column + 1)
    quest[0], quest[level_column] = 'field', '120'
    zone = [''] * 25
    zone[23], zone[24] = '1', 'enemy'
    tables = {quest_name: {'quest': ','.join(quest)},
              'master/battle/field_data.orderedmap': {'field': ',,zone'},
              'master/battle/zone.orderedmap': {'zone': ','.join(zone)},
              p.LEVEL_TABLES['general_boss']: {'enemy': {'100': 'fixture'}}}
    view = SimpleNamespace(table=lambda name: tables.get(name), raw=lambda name: None)
    rep = p.Report(set())
    p.check_level(None, view, None, rep)
    gap = [f for f in rep.items if f.fid == 'level.gap:general_boss:enemy']
    assert len(gap) == 1 and gap[0].level == 'ERROR'
    historical = p.Report(set())
    p.check_level(None, view, view, historical)
    gap = [f for f in historical.items if f.fid == 'level.gap:general_boss:enemy']
    assert len(gap) == 1 and gap[0].level == 'WARN'

"""重跑服务端行的三方合并；只写本分享包工作区。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
from server_merge_core import MISSING, apply_five_priority, changed_paths, clean, merge

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '交付'
AUDIT = ROOT / 'audit'
CACHE = ROOT / 'cache'
REPO = Path('D:/WF/startpoint-cn-kulo')
OURS = Path('D:/WF/out/角色超限-120/localsrv219/assets')
ANCESTOR = '7e6d55b62eacca91ca7e557a02b5b9af6e2495a9'
IGNORE_DIRS = ('assets/asset-patch/', 'assets/asset_lists/', 'assets/gacha-movie-variants/')


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path = path.resolve()
    assert path.is_relative_to(ROOT.resolve()), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path, value):
    write(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def tree(ref):
    return {p for p in git('ls-tree', '-r', '--name-only', ref, 'assets').decode().splitlines()
            if p.endswith('.json') and not any(p.startswith(d) for d in IGNORE_DIRS)}


def main():
    pin = OUT / 'build/source-lock.json'
    if not pin.exists():
        pin = CACHE / 'kulo-ref.json'
    pinned = json.loads(pin.read_text('utf-8')) if pin.exists() else {}
    hui_ref = pinned.get('hui_ref', pinned.get('ref')) or git('log', '-1', '--format=%H', 'origin/main').decode().strip()
    priority_document = json.loads((AUDIT / 'five-priority-220.json').read_text('utf-8'))
    priority_rules = {}
    for rule in priority_document['server_rules']:
        priority_rules.setdefault(rule['file'], []).append(rule)
    membership_rules = {rule['file']: rule['required_ids']
                        for rule in priority_document['server_membership_rules']}
    trees = {r: tree(r) for r in (ANCESTOR, hui_ref)}
    files = trees[ANCESTOR] | trees[hui_ref]
    files |= {'assets/' + p.relative_to(OURS).as_posix() for p in OURS.rglob('*.json')
              if not any(('assets/' + p.relative_to(OURS).as_posix()).startswith(d) for d in IGNORE_DIRS)}
    conflicts, excluded, deletions = [], [], []
    priority_decisions, priority_checked, membership_checked = [], 0, 0
    entries, source_files, changed = [], [], []
    expected_results = {}
    for file in sorted(files):
        raws = {r: git('show', f'{r}:{file}') if file in trees[r] else None for r in trees}
        base = json.loads(raws[ANCESTOR]) if raws[ANCESTOR] is not None else MISSING
        hui = json.loads(raws[hui_ref]) if raws[hui_ref] is not None else MISSING
        if raws[hui_ref] is not None:
            write(CACHE / 'server-origin-assets' / file.removeprefix('assets/'), raws[hui_ref])
            write(CACHE / 'server-merged-assets' / file.removeprefix('assets/'), raws[hui_ref])
        our_path = OURS / file.removeprefix('assets/')
        if not our_path.exists():
            continue
        ours_raw = our_path.read_bytes()
        ours = clean(json.loads(ours_raw), file, (), excluded)
        if ours is MISSING:
            continue
        source_files.append({'file': file, 'base_sha256': sha(raws[ANCESTOR]) if raws[ANCESTOR] else None,
                             'hui_sha256': sha(raws[hui_ref]) if raws[hui_ref] else None,
                             'ours_sha256': sha(ours_raw)})
        result = merge(base, hui, ours, file, (), conflicts, deletions)
        rules = priority_rules.get(file, [])
        if rules:
            result, decisions = apply_five_priority(result, hui, ours, file, rules)
            priority_checked += len(rules)
            priority_decisions += decisions
        if file in membership_rules:
            assert isinstance(result, list) and isinstance(ours, list), file
            for value in membership_rules[file]:
                assert value in ours, ('五重 ID 不在我方源', file, value)
                if value not in result:
                    result.append(value)
                membership_checked += 1
        if result == hui:
            continue
        ops = []
        if isinstance(result, dict):
            current = {} if hui is MISSING else hui
            for key, value in result.items():
                if key not in current or value != current[key]:
                    expected = {'exists': key in current}
                    if key in current:
                        expected['value'] = current[key]
                    ops.append({'key': key, 'action': 'replace' if key in current else 'add',
                                'expected': expected, 'value': value,
                                'changed_paths': changed_paths(current.get(key, MISSING), value, (key,))})
            kind = 'object'
        elif isinstance(result, list) and isinstance(hui, list):
            assert all(v in result for v in hui), ('unexpected deletion', file)
            ops = [{'key': str(v), 'action': 'append-id', 'expected': {'exists': False}, 'value': v}
                   for v in result if v not in hui]
            kind = 'id-list'
        else:
            raise ValueError(('unsupported server file', file))
        assert ops, file
        entries.append({'file': file, 'kind': kind, 'baseline_sha256': sha(raws[hui_ref]) if raws[hui_ref] else None,
                        'baseline_exists': hui is not MISSING, 'entries': ops})
        changed.append({'file': file, 'entries': len(ops), 'keys': [o['key'] for o in ops]})
        expected_results[file] = result
    assert priority_checked == len(priority_document['server_rules']), '五重规则存在未处理的服务端文件'
    assert membership_checked == sum(map(len, membership_rules.values())), '五重 ID 列表未全部核对'
    document = {'format': 'hui-share-server-entries-v1', 'from': '1.4.136', 'to': '1.4.220',
                'our_terminal': '1.4.219', 'ancestor_ref': ANCESTOR, 'hui_ref': hui_ref,
                'merge_policy': '祖先为7e6d55b6服务端assets；双方同列冲突默认取灰；五重精确叶行取我方219终态；训练木桩全部收入；GM武器只带已审计本体与使用配套，不带获取途径；不执行删除；按键追加或修改。',
                'files': entries}
    write_json(OUT / 'server-entries.json', document)
    spec = importlib.util.spec_from_file_location('server_apply', OUT / 'apply_server_entries.py')
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    prepared = app.prepare((CACHE / 'server-origin-assets').resolve(), document)
    for target, raw, _ in prepared:
        relative = target.relative_to(CACHE / 'server-origin-assets')
        assert json.loads(raw) == expected_results['assets/' + relative.as_posix()]
        write(CACHE / 'server-merged-assets' / relative, raw)
    audit = {'ancestor_ref': ANCESTOR, 'hui_ref': hui_ref, 'our_terminal': '1.4.219',
             'files': changed, 'file_count': len(entries), 'entry_count': sum(len(f['entries']) for f in entries),
             'conflicts': conflicts, 'conflict_count': len(conflicts), 'excluded': excluded,
             'excluded_count': len(excluded), 'skipped_deletions': deletions,
             'source_files': source_files,
             'five_priority': {'checked_leaf_count': priority_checked,
                               'checked_membership_id_count': membership_checked,
                               'hui_ours_difference_count': len(priority_decisions),
                               'overrode_default_count': sum(d['overrode_default'] for d in priority_decisions),
                               'decisions': priority_decisions,
                               'source': 'audit/five-priority-220.json'},
             'assets_view': str(CACHE / 'server-merged-assets')}
    write_json(AUDIT / 'server-audit.json', audit)
    from verify_gm_server_r3 import build_audit
    build_audit(document)
    print(json.dumps({k: audit[k] for k in ('file_count', 'entry_count', 'conflict_count', 'excluded_count', 'assets_view')}, ensure_ascii=False))


if __name__ == '__main__':
    main()

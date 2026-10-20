"""验证五重逐叶优先和实际服务端终态，不接触工作区外写入。"""
import copy
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from common import ROOT, write_json
from server_merge_core import apply_five_priority, merge, path_value


def main():
    document = json.loads((ROOT/'audit/five-priority-220.json').read_text('utf-8'))
    checked = 0
    parsed = {}
    for rule in document['server_rules']:
        source = ROOT/'cache/server-merged-assets'/rule['file'].removeprefix('assets/')
        if source not in parsed:
            parsed[source] = json.loads(source.read_text('utf-8-sig'))
        value = parsed[source]
        assert path_value(value, rule['path']) == rule['ours'], (rule['file'], rule['path'])
        checked += 1
    for rule in document['server_membership_rules']:
        source = ROOT/'cache/server-merged-assets'/rule['file'].removeprefix('assets/')
        value = json.loads(source.read_text('utf-8-sig'))
        assert all(v in value for v in rule['required_ids']), rule['file']
    base = {'five': {'hp': 100, 'buff': [0, 0]}, 'other': {'original': 1}}
    hui = {'five': {'hp': 200, 'buff': [55, 3]}, 'other': {'original': 2, 'preload': 'evil'}}
    ours = {'five': {'hp': 50, 'buff': [0, 2]}, 'other': {'original': 1}}
    preserved = copy.deepcopy((base, hui, ours))
    conflicts = []
    default = merge(base, hui, ours, 'fixture.json', (), conflicts, [])
    assert default['five'] == {'hp': 200, 'buff': [55, 3]}
    rules = [{'path': ['five', 'hp'], 'hui': 200, 'ours': 50},
             {'path': ['five', 'buff', 1], 'hui': 3, 'ours': 2}]
    result, decisions = apply_five_priority(default, hui, ours, 'fixture.json', rules)
    assert result['five'] == {'hp': 50, 'buff': [55, 2]}
    assert result['other'] == hui['other']
    assert all(row['overrode_default'] for row in decisions)
    assert (base, hui, ours) == preserved
    try:
        apply_five_priority(default, hui, ours, 'fixture.json',
                            [{'path': ['five', 'hp'], 'hui': 999, 'ours': 50}])
    except AssertionError:
        pass
    else:
        raise AssertionError('应拒绝过期五重灰基线')
    report = {'checked_server_leaf_count': checked,
              'checked_membership_ids': sum(len(r['required_ids']) for r in document['server_membership_rules']),
              'forced_ours_when_same_leaf_conflicts': True,
              'preserved_hui_other_leaf_and_evil_preload': True,
              'preserved_inputs': True, 'stale_priority_baseline_rejected': True}
    write_json(ROOT/'audit/five-server-verification.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()

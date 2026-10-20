"""在普通三方合并之后，按显式审核规则保护五重终态和已证实的缺陷修复。"""
import copy
import json
import common as c

def get_path(node, path):
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise KeyError('/'.join(path))
        node = node[key]
    return node

def set_path(node, path, value):
    if not path:
        return copy.deepcopy(value)
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = copy.deepcopy(value)

def load_rules():
    five=json.loads((c.ROOT/'audit/five-priority-220.json').read_text('utf-8'))
    defects=json.loads((c.ROOT/'audit/defect-resolutions-220.json').read_text('utf-8'))
    return five,defects

def apply_rows(member, tree, ours, rules, kind, records):
    for rule in rules:
        if rule['member'] != member or rule.get('resolution','ours') not in ('ours','ours_five','ours_defect'):
            continue
        path=rule.get('path',rule.get('key_path'))
        if not path:
            continue
        expected=get_path(ours,path)
        assert expected==rule['ours'],('优先规则与锁定我方终态不符',member,path)
        actual=get_path(tree,path)
        if actual != expected:
            set_path(tree,path,expected)
        records.append({**rule,'kind':kind,'final':expected,'changed_by_priority':actual != expected})
    return tree

def mark_conflicts(conflicts, start, member, rules, resolution):
    for conflict in conflicts[start:]:
        if conflict.get('member') != member:
            continue
        for rule in rules:
            path=rule.get('path',rule.get('key_path',[]))
            if rule['member']==member and path==conflict['path']:
                conflict['resolution']=resolution
                conflict['resolution_reason']=rule.get('reason','显式优先规则')

"""重放 130 分叉后的两条链，仅封装相对灰136发生变化的终态成员。"""
import copy
import io
import json
from pathlib import Path
import zipfile
import zlib
import common as c
from merge_core import merge, MISSING, neutralize, changed_rows
from priority_overrides import load_rules, apply_rows, mark_conflicts

def try_map(b):
    if b is None:
        return None
    try:
        t = c.q.parse_node(b)
        return t if isinstance(t, dict) else None
    except (ValueError, UnicodeError, zlib.error, IndexError):
        return None

def main():
    hui, ours = c.View('hui'), c.View('ours')
    logical = c.logical_index()
    policy = json.loads((c.OUT / '附录/exclusions.json').read_text('utf-8'))
    rules = policy['excluded_rows']
    excluded_members = {x['member'] if isinstance(x, dict) else x for x in policy['excluded_members']}
    five, defects = load_rules()
    five_rules = five['client_rules']
    defect_rules = [r for r in defects['rules'] if r['resolution']=='ours']
    logical.update({r['member']:r['logical'] for r in defect_rules})
    logical.update({r['member']:r['logical'] for r in five.get('binary_dependencies',[]) if r['logical']!='未核实'})
    output, conflicts, details, retained, normalizations, protected = {}, [], {}, [], [], []
    for m in sorted(ours.index):
        b, h, o = c.base_raw(m), hui.raw(m), ours.raw(m)
        name = logical.get(m, m)
        if m in excluded_members:
            retained.append({'member': m, 'logical': name, 'reason': 'excluded member'})
            continue
        bb, hh, oo = map(try_map, (b, h, o))
        if oo is not None:
            for rule in rules:
                if rule['member'] == m:
                    oo = neutralize(oo, bb or {}, rule['key_path'])
            if bb == oo:
                continue
            if hh is None and h is None:
                hh = {}
            if bb is None and b is None:
                bb = {}
            if bb is not None and hh is not None:
                changes = []
                start = len(conflicts)
                tree = merge(bb, hh, oo, [], conflicts, changes)
                for conflict in conflicts[start:]:
                    conflict.update(member=m, logical=name)
                tree = apply_rows(m,tree,oo,five_rules,'five',protected)
                tree = apply_rows(m,tree,oo,defect_rules,'defect',protected)
                mark_conflicts(conflicts,start,m,five_rules,'ours_five')
                mark_conflicts(conflicts,start,m,defect_rules,'ours_defect')
                # 我方219自身存在资料文案漂移。机械同步到实际战斗技能表，
                # 不改变任意战斗数值/DSL，也不覆盖灰侧冲突取值。
                if m == c.member('master/character/character_text.orderedmap'):
                    row = c.cells(tree['149999'])
                    skills = ours.load('master/skill/action_skill.orderedmap')['white_wolf_gerald']
                    for level, column in [('1',5),('2',7)]:
                        expected = c.cells(skills[level])[1]
                        if row[column] != expected:
                            normalizations.append({'logical':name,'path':['149999'], 'column':column,
                                                   'before':row[column], 'after':expected,
                                                   'reason':'prepush文本一致性：同步到我方219实际action_skill终态'})
                            row[column] = expected
                    tree['149999'] = c.join(row)
                if tree == hh:
                    continue
                raw = c.q.build_node(tree)
                assert c.q.parse_node(raw) == tree, name
                output[m] = raw
                details[m] = {'logical': name, 'rows': changed_rows(hh, tree),
                              'conflicts': list(range(start, len(conflicts))),
                              'base_sha256': c.sha(b) if b else None,
                              'hui_sha256': c.sha(h) if h else None,
                              'ours_sha256': c.sha(o)}
                continue
        if o == b or o == h:
            continue
        if h == b:
            output[m] = o
        else:
            fix = next((r for r in defect_rules if r['member']==m and not r['path']),None)
            if fix:
                output[m]=o
                protected.append({**fix,'kind':'defect','final_sha256':c.sha(o),'changed_by_priority':True})
            conflicts.append({'member': m, 'logical': name, 'path': [], 'kind': 'binary',
                              'base': c.sha(b) if b is not None else None,
                              'hui': c.sha(h) if h is not None else None,
                              'ours': c.sha(o), 'resolution': 'ours_defect' if fix else 'hui',
                              'resolution_reason':fix['reason'] if fix else '普通冲突保留灰'})
    c.write_json(c.ROOT/'audit/client-conflicts.json', conflicts)
    c.write_json(c.ROOT/'audit/priority-applied-220.json', protected)
    c.write_json(c.ROOT/'audit/text-normalizations.json', normalizations)
    c.write_json(c.ROOT/'audit/client-merged-tables.json', details)
    c.write_json(c.ROOT/'audit/client-members.json', [{'member':m, 'logical':logical.get(m),
                  'sha256':c.sha(v), 'source':ours.index[m].name} for m,v in output.items()])
    # 固定时间戳和稳定装箱，重跑得到同一 zip sha256。
    limit = 5 * 1024 * 1024
    groups = []
    for m in sorted(output, key=lambda n:(-len(zlib.compress(output[n], 6)), n)):
        cost = len(zlib.compress(output[m], 6)) + 2 * len(m) + 160
        assert cost < limit - 65536, ('single member too large', m, cost)
        for g in groups:
            if g['size'] + cost <= limit - 65536:
                g['members'].append(m); g['size'] += cost
                break
        else:
            groups.append({'members':[m], 'size':cost})
    integrity = []
    for part, g in enumerate(groups, 1):
        name = f'pinball-1.4.136-1.4.220-{part}-hui-share-20261016.zip'
        p = c.OUT / name
        with zipfile.ZipFile(p, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for m in sorted(g['members']):
                info = zipfile.ZipInfo(m, date_time=(2026,10,16,0,0,0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info, output[m], compresslevel=6)
        raw = p.read_bytes()
        assert len(raw) <= limit
        with zipfile.ZipFile(p) as z:
            assert z.testzip() is None
        x = {'name':name, 'size':len(raw), 'sha256':c.sha(raw), 'members':len(g['members']),
             'files':sorted(g['members']), 'member_sha256':{m:c.sha(output[m]) for m in sorted(g['members'])},
             'applies_on':'1.4.136', 'version':'1.4.220', 'part':f'{part}/{len(groups)}',
             'merged_tables':{m:details[m] for m in sorted(g['members']) if m in details},
             'priority_rows':[r for r in protected if r['member'] in g['members']],
             'hui_ref':hui.ref, 'ancestor':'1.4.130', 'ours_tip':'1.4.219'}
        c.write_json(p.with_suffix('.integrity.json'),x)
        integrity.append({k:x[k] for k in ('name','size','sha256','members','files')})
        print(name, len(raw), x['sha256'], x['members'], flush=True)
    entry = {'id':'hui-share-20261016-1.4.220', 'type':'patch',
             'name':'平衡与新内容分享整合（排除GM及测试辅助）',
             'description':'以灰1.4.136为基线三方合并我方1.4.219终态；新增决战副本需由灰重新排期。',
             'version':'1.4.220', 'depends_on':'1.4.136', 'enabled':True,
             'archive':integrity[0]['name'], 'archive_size':integrity[0]['size'],
             'chain':[x['name'] for x in integrity], 'archive_integrity':integrity,
             'files':sorted(output), 'created_at':'2026-10-16'}
    c.write_json(c.OUT/'manifest-entry-1.4.220.json',entry)
    c.write_json(c.OUT/'report.json',{'anchor':{'from':'1.4.136','to':'1.4.220'},
                 'ours':{'since':'1.4.219','tip':'1.4.219','delta_base':'1.4.130'},
                 'hui_ref':hui.ref,'members':len(output),'client_conflicts':len(conflicts),
                 'merged_tables':len(details),'archives':integrity,
                 'five_priority_rules':len(five_rules),'verified_defect_overrides':len(defect_rules)})
    print('members',len(output),'tables',len(details),'conflicts',len(conflicts))

if __name__ == '__main__':
    main()

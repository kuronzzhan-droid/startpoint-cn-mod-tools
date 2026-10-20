"""从交付ZIP读回，核对基线保护、终态、排除项、成员hash与功能ID。"""
import json
import re
import zipfile
import common as c
from merge_core import changed_rows, MISSING

def at(tree, path):
    for k in path:
        if not isinstance(tree, dict) or k not in tree:
            return MISSING
        tree = tree[k]
    return tree

def main():
    h, o = c.View('hui'), c.View('ours')
    entry = json.loads((c.OUT/'manifest-entry-1.4.137.json').read_text('utf-8'))
    data = {}
    for rec in entry['archive_integrity']:
        p = c.OUT/rec['name']; raw = p.read_bytes()
        assert len(raw) == rec['size'] <= 5*1024*1024 and c.sha(raw) == rec['sha256']
        integ = json.loads(p.with_suffix('.integrity.json').read_text('utf-8'))
        with zipfile.ZipFile(p) as z:
            assert z.testzip() is None
            assert sorted(z.namelist()) == sorted(rec['files'])
            for m in z.namelist():
                assert m not in data
                b = z.read(m)
                assert c.sha(b) == integ['member_sha256'][m]
                data[m] = b
    def load(p):
        m = c.member(p)
        b = data.get(m, h.raw(m))
        return c.q.parse_node(b) if b is not None else {}
    checks = []
    def check(label, actual, expected):
        assert actual == expected, label
        checks.append({'check':label, 'passed':True, 'value':actual})
    s = 'master/character/character_status.orderedmap'
    check('瓦格纳111183等级120',load(s)['111183']['120'],'4500,1060')
    check('护花使龙141099等级120',load(s)['141099']['120'],o.load(s)['141099']['120'])
    for p,k in [('master/skill/action_skill.orderedmap','seris_dragon_king'),
                ('master/ability/ability.orderedmap','1299991'),
                ('master/ability/leader_ability.orderedmap','111183'),
                ('master/ability/ability.orderedmap','1699991')]:
        check(p+'/'+k+'等于我方219终态',load(p)[k],o.load(p)[k])
    for p in ['master/character/character.orderedmap','master/character/character_status.orderedmap',
              'master/character/character_text.orderedmap']:
        check('碧169978保留灰版:'+p,load(p)['169978'],h.load(p)['169978'])
    for k in ['1699781','1699782','1699783','1699784','1699785','1699786']:
        check('碧能力保留灰版:'+k,load('master/ability/ability.orderedmap')[k],h.load('master/ability/ability.orderedmap')[k])
    for p,k in [('master/ability/ability.orderedmap','1599921'),
                ('master/ability/ability.orderedmap','1599922'),
                ('master/ability/leader_ability.orderedmap','159992')]:
        check('凉月冲突明确保留灰版:'+k,load(p)[k],h.load(p)[k])
    check('凉月获取语音保留灰版',load('master/character/character_speech.orderedmap')['159992'],h.load('master/character/character_speech.orderedmap')['159992'])
    policy = json.loads((c.OUT/'附录/exclusions.json').read_text('utf-8'))
    for r in policy['excluded_rows']:
        p = r['logical_path']; path = r['key_path']
        assert at(load(p),path) == at(h.load(p) or {},path), ('excluded row',p,path)
    for r in policy['excluded_members']:
        m = r['member'] if isinstance(r,dict) else r
        assert m not in data, ('excluded member',m)
    # 独立查残余 GM id 引用（CSV完整数字token），覆盖全部交付orderedmap。
    references=[]
    ids=set(policy['gm_weapon_ids'])
    maps={}
    for m,b in data.items():
        try:
            t=c.q.parse_node(b)
        except Exception:
            continue
        if not isinstance(t,dict):continue
        maps[m]=t
        for path,v in c.leaves(t):
            hits=ids.intersection(re.findall(r'(?<!\d)599000[1-6](?!\d)',str(v)))
            if hits:references.append({'member':m,'path':list(path),'ids':sorted(hits)})
    assert not references, references
    # 角色和装备ID清单取实际交付终态差异，不把中间边重复计数。
    cp='master/character/character.orderedmap'; chars=load(cp)
    texts=load('master/character/character_text.orderedmap')
    affected=set()
    diffs={}
    table_paths=['master/ability/ability.orderedmap','master/ability/leader_ability.orderedmap',
                 'master/skill/action_skill.orderedmap','master/character/character_status.orderedmap',
                 'master/character/character_text.orderedmap','master/character/character_awake_status.orderedmap',
                 'master/character/character_speech.orderedmap']
    for p in table_paths:
        diffs[p]=changed_rows(h.load(p) or {},load(p))
    for cid,v in chars.items():
        cv=c.cells(v); code=cv[8]; ability_ids=set(cv[19:25])
        for p,rs in diffs.items():
            keys={r['path'][0] for r in rs if r['path']}
            if cid in keys or ('/ability/ability.' in p and ability_ids.intersection(keys)) or ('/skill/' in p and code in keys):
                affected.add(cid)
    equipment='master/item/equipment.orderedmap'
    eqdiff=changed_rows(h.load(equipment) or {},load(equipment))
    equipment_ids=sorted({r['path'][0] for r in eqdiff if r['path']},key=lambda s:(len(s),s))
    result={'members':len(data),'archive_count':len(entry['chain']), 'checks':checks,
            'excluded_rows_verified':len(policy['excluded_rows']),
            'excluded_members_verified':len(policy['excluded_members']), 'gm_references':references,
            'affected_characters':[{'id':cid,'name':c.cells(texts[cid])[0]} for cid in sorted(affected,key=int)],
            'equipment_ids':equipment_ids, 'table_row_changes':{p:len(rs) for p,rs in diffs.items()}}
    c.write_json(c.ROOT/'audit/client-verification.json',result)
    print('客户端读回验证通过:',len(checks),'关键项;',len(data),'成员;',len(affected),'角色;',len(equipment_ids),'装备行')

if __name__=='__main__':
    main()

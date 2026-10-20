"""验证训练/GM本体恢复，并拒绝未分类的GM获取引用。"""
import json
import re
from functools import lru_cache
import common as c

def at(node,path):
    for key in path:
        node=node[key]
    return node

def verify(load, raw, data, policy):
    ours=c.View('ours')
    original=json.loads((c.OUT/'build/original-exclusions.json').read_text('utf-8'))
    @lru_cache(maxsize=None)
    def source(logical):return ours.load(logical)
    excluded={(r['member'],tuple(r['key_path'])) for r in policy['excluded_rows']}
    checked=0
    for row in original['excluded_rows']:
        path=row['key_path'];logical=row['logical_path']
        if (row['member'],tuple(path)) in excluded:continue
        assert at(load(logical),path)==at(source(logical),path),('恢复终态不符',logical,path)
        checked+=1
    excluded_members={r['member'] if isinstance(r,dict) else r for r in policy['excluded_members']}
    member_count=0
    for row in original['excluded_members']:
        m=row['member'] if isinstance(row,dict) else row
        if m in excluded_members:continue
        assert raw(m)==ours.raw(m),('恢复资源不符',m)
        member_count+=1
    logicals=c.logical_index()
    body_rows=policy['gm_body_rows']
    allowed={}
    for r in body_rows:
        allowed.setdefault(r['member'],[]).append(tuple(r.get('key_path',r.get('path',[]))))
    references=[]
    for m,b in data.items():
        try:tree=c.q.parse_node(b)
        except Exception:continue
        if not isinstance(tree,dict):continue
        for path,value in c.leaves(tree):
            tokens=re.findall(r'(?<!\d)599000[1-6](?!\d)','/'.join(path)+' '+str(value))
            if not tokens:continue
            assert any(path[:len(p)]==p for p in allowed.get(m,[])),('未分类GM引用',logicals.get(m,m),path)
            logical=logicals.get(m,'')
            assert not logical.startswith(('master/shop/','master/reward/','master/quest/','master/gacha/')),('GM获取途径引用',logical,path)
            references.append({'member':m,'logical':logical,'path':list(path),'ids':sorted(set(tokens))})
    result={'restored_table_keys_verified':checked,'restored_members_verified':member_count,
            'gm_body_references':references,'unclassified_gm_references':0,
            'gm_acquisition_references':0,'scope':'最终交付orderedmap读回；全来源路线审查另见gm-route-review-r3'}
    c.write_json(c.ROOT/'audit/inclusion-verification-r3.json',result)
    return result

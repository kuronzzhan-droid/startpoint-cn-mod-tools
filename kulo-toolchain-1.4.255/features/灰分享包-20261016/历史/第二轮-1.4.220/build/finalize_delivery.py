"""绑定双边检查证据、读回保护规则、检查交付目录卫生并生成校验和。"""
import ast
import hashlib
import json
from pathlib import Path
import zipfile
import common as c

def read(p):return json.loads(Path(p).read_text('utf-8'))

def main():
    live=read(c.OUT/'manifest-entry-1.4.220.json')
    align=read(c.OUT/'manifest-entry-align-1.4.220.json')
    assert (live['depends_on'],live['version'])==('1.4.136','1.4.220')
    assert (align['depends_on'],align['version'])==('1.4.219','1.4.220')
    sums={};counts={}
    for label,entry in [('live',live),('align',align)]:
        total=0;members=set()
        for rec in entry['archive_integrity']:
            p=c.OUT/rec['name'];b=p.read_bytes()
            assert len(b)==rec['size']<=5*1024*1024 and c.sha(b)==rec['sha256']
            integrity=read(p.with_suffix('.integrity.json'))
            with zipfile.ZipFile(p) as z:
                assert z.testzip() is None
                assert sorted(z.namelist())==sorted(rec['files'])
                for n in z.namelist():
                    assert n not in members
                    members.add(n)
                    assert c.sha(z.read(n))==integrity['member_sha256'][n]
            sums[p.name]=c.sha(b);total+=len(b)
        counts[label]={'archives':len(entry['chain']),'members':len(members),'bytes':total}
    for name,entry_name in [('prepush-summary.json','manifest-entry-1.4.220.json'),
                            ('prepush-align-summary.json','manifest-entry-align-1.4.220.json')]:
        summary=read(c.OUT/name)
        assert summary['returncode']==0 and summary['counts']['ERROR']==0,(name,summary)
        assert summary['manifest_entry_sha256']==c.sha((c.OUT/entry_name).read_bytes())
        expected=read(c.OUT/entry_name)
        assert {r['name'] for r in summary['candidate_artifacts']}==set(expected['chain'])
        for artifact in summary['candidate_artifacts']:
            assert sums[artifact['name']]==artifact['sha256']
    server=read(c.OUT/'server-entries.json')
    assert (server['from'],server['to'])==('1.4.136','1.4.220')
    for p in c.OUT.rglob('*.py'):ast.parse(p.read_text('utf-8'),filename=str(p))
    for p in c.OUT.rglob('*.md'):
        assert not [x for x in p.read_text('utf-8') if ord(x)<32 and x not in '\t\r\n'],p
    assert not list(c.OUT.glob('pinball-1.4.136-1.4.137-*')),'第一轮包不应混在当前交付'
    forbidden={'.apk','.so','.keystore','.jks','.pfx','.p12','.pem'}
    assert not [p for p in c.OUT.rglob('*') if p.is_file() and p.suffix.lower() in forbidden]
    evidence={'anchors_verified':True,'counts':counts,'final_archive_sha256':sums,
              'python_syntax_valid':True,'markdown_controls':0,'prohibited_files':0}
    prior=c.ROOT/'audit/rebuild-before-220.json'
    if prior.exists():
        previous=read(prior)
        assert previous==sums,'重跑ZIP字节变化'
        evidence['rebuild_archive_hashes_identical']=len(sums)
    c.write_json(c.OUT/'附录/final-verification.json',evidence)
    report=read(c.OUT/'report.json')
    report['final_verification']=evidence
    c.write_json(c.OUT/'report.json',report)
    lines=[]
    for p in sorted(c.OUT.rglob('*')):
        if p.is_file() and p.name!='SHA256SUMS.txt':
            lines.append(c.sha(p.read_bytes())+'  '+p.relative_to(c.OUT).as_posix())
    (c.OUT/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n','utf-8')
    print(json.dumps(evidence,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

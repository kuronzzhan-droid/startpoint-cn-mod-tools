"""在本工作区构造灰全链虚拟视图，调用原版 prepush，不启动服务端。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
import common as c

CHECKER = Path('D:/WF/out/kulo-patch-toolkit/prepush/wf_prepush_check.py')
TS = c.KULO / 'node_modules/typescript/lib/typescript.js'
VIRTUAL = c.CACHE / 'prepush-server'
NAMES = ['parseVersion', 'compareVersion', 'parseDiffArchiveName', 'checkPatchChainIntegrity']


def safe(path):
    path = Path(path).resolve()
    assert path.is_relative_to(c.ROOT.resolve()), path
    return path


def write(path, data):
    path = safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def resolve_lfs(raw, name):
    """只读本地LFS对象，不调用git-lfs、不联网；SHA/size绑定origin/main指针。"""
    if not raw.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
        return raw, 'git blob/cache'
    text = raw.decode('ascii')
    oid = re.search(r'^oid sha256:([0-9a-f]{64})$', text, re.M).group(1)
    size = int(re.search(r'^size (\d+)$', text, re.M).group(1))
    git_dir = c.KULO / '.git'
    if git_dir.is_file():
        location = git_dir.read_text('utf-8').strip().removeprefix('gitdir: ')
        git_dir = (c.KULO / location).resolve()
    obj = git_dir / 'lfs/objects' / oid[:2] / oid[2:4] / oid
    if not obj.is_file():
        raise FileNotFoundError(f'{name} 的本地LFS对象不存在，禁止联网补取：{obj}')
    content = obj.read_bytes()
    assert len(content) == size and c.sha(content) == oid, ('LFS sha/size', name)
    return content, str(obj)


def pure_chain(ref):
    """TypeScript AST提取真实上游纯函数，再用现有TypeScript编译器转译。"""
    source = c.git_show('src/routes/cn/asset.ts', ref)
    # 不require服务端asset.js：其顶层会report并require整个服务端依赖树。
    # 只从指定ref的真实源码提取四个函数及类型接口，函数正文不改写。
    script = r'''
const fs = require('fs');
const ts = require(process.argv[1]);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const sf = ts.createSourceFile('asset.ts', input.source, ts.ScriptTarget.Latest, true);
const wanted = new Set(input.names.concat(['DiffArchiveKey']));
const selected = sf.statements.filter(n => n.name && wanted.has(n.name.text));
const found = new Set(selected.map(n => n.name.text));
for (const name of wanted) if (!found.has(name)) throw Error('missing declaration: '+name);
const parts = selected.map(n => ({name:n.name.text, text:n.getText(sf)}));
for (const p of parts) {
  if (/\brequire\s*\(|\bimport\s+|\bprocess\.|\bfs\./.test(p.text))
    throw Error('unexpected side effect in selected source: '+p.name);
}
const text = parts.map(p => p.text).join('\n\n');
const result = ts.transpileModule(text, {compilerOptions:{target:ts.ScriptTarget.ES2018,
  module:ts.ModuleKind.CommonJS, strict:true}, reportDiagnostics:true});
const errors = (result.diagnostics || []).filter(d => d.category===ts.DiagnosticCategory.Error);
if (errors.length) throw Error(ts.formatDiagnosticsWithColorAndContext(errors, {
  getCanonicalFileName:x=>x,getCurrentDirectory:()=>'.',getNewLine:()=> '\n'}));
process.stdout.write(JSON.stringify({js:result.outputText, parts}));
'''
    p = subprocess.run(['node', '-e', script, str(TS)],
                       input=json.dumps({'source': source.decode('utf-8'), 'names': NAMES}),
                       capture_output=True, text=True, encoding='utf-8', cwd=c.ROOT, check=True)
    result = json.loads(p.stdout)
    output = VIRTUAL / 'out/routes/cn/asset.js'
    write(output, result['js'].encode('utf-8'))
    probe = r'''
const a=require(process.argv[1]);
const one='pinball-1.4.136-1.4.137-1-a.zip';
const two='pinball-1.4.136-1.4.137-2-b.zip';
const third='pinball-1.4.136-1.4.137-3-c.zip';
const duplicate='pinball-1.4.136-1.4.137-1-b.zip';
const samples={clean:a.checkPatchChainIntegrity([one,two],[one,two]),
 duplicate:a.checkPatchChainIntegrity([one,duplicate],[one,duplicate]),
 gap:a.checkPatchChainIntegrity([one,third],[one,third]),
 missing:a.checkPatchChainIntegrity([one],[])};
if(samples.clean.length || !samples.duplicate.some(x=>x.includes('duplicate (from,to,seq)'))
 || !samples.gap.some(x=>x.includes('sequence gap'))
 || !samples.missing.some(x=>x.includes('listed archive missing')))
 throw Error('real chain checker selftest failed');
process.stdout.write(JSON.stringify(samples));
'''
    checked = subprocess.run(['node', '-e', probe, str(output)], capture_output=True,
                             text=True, encoding='utf-8', cwd=c.ROOT, check=True)
    c.write_json(c.OUT / 'prepush-chain-source.json', {
        'ref': ref, 'source': 'src/routes/cn/asset.ts', 'source_sha256': c.sha(source),
        'functions': [{'name': v['name'], 'sha256': c.sha(v['text'].encode('utf-8'))}
                      for v in result['parts']],
        'output_sha256': c.sha(result['js'].encode('utf-8')),
        'method': 'TypeScript AST原文提取+transpileModule，仅四个真实纯函数及类型接口，无stub',
        'selftest': json.loads(checked.stdout),
    })


def prepare():
    hui = c.View('hui')
    merged = c.CACHE / 'server-merged-assets'
    if not merged.is_dir() or not (merged / 'item_ids.json').is_file():
        raise FileNotFoundError('服务端合并视图未齐：cache/server-merged-assets/item_ids.json')
    active = VIRTUAL / 'assets/asset-patch/active'
    active.mkdir(parents=True, exist_ok=True)
    for source in merged.rglob('*.json'):
        write(VIRTUAL / 'assets' / source.relative_to(merged), source.read_bytes())
    manifest = json.loads(c.git_show('assets/asset-patch/manifest.json', hui.ref))
    expected = set()
    evidence = []
    for entry in manifest['patches']:
        if entry.get('type') != 'patch' or entry.get('enabled') is not True:
            continue
        for name in c.archives(entry):
            expected.add(name)
            dest = active / name
            candidate = c.CACHE / 'hui' / name
            raw = candidate.read_bytes() if candidate.is_file() else c.git_show('assets/asset-patch/active/' + name, hui.ref)
            raw, source_kind = resolve_lfs(raw, name)
            evidence.append({'name': name, 'size': len(raw), 'sha256': c.sha(raw), 'source': source_kind})
            # 重跑也验证内容；不从工作区外导出或写Git对象。
            if not dest.is_file() or c.sha(dest.read_bytes()) != c.sha(raw):
                write(dest, raw)
    entry = json.loads((c.OUT / 'manifest-entry-1.4.137.json').read_text('utf-8'))
    for name in c.archives(entry):
        expected.add(name)
        write(active / name, (c.OUT / name).read_bytes())
    # 不删除任何文件；若旧运行残留不同候选，则明确拒绝而非静默混链。
    unknown = {p.name for p in active.glob('*.zip')} - expected
    if unknown:
        raise RuntimeError('虚拟active有非本次条目，需核实：' + ','.join(sorted(unknown)))
    manifest['patches'].append(entry)
    manifest['cdn_version'] = '1.4.137'
    c.write_json(VIRTUAL / 'assets/asset-patch/manifest.json', manifest)
    c.write_json(c.OUT / 'prepush-inputs.json', {'hui_ref': hui.ref, 'gray_archives': evidence})
    pure_chain(hui.ref)
    return hui, len(expected)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare-only', action='store_true')
    args = ap.parse_args()
    hui, archive_count = prepare()
    if args.prepare_only:
        print('已准备', archive_count, '个包；未运行完整prepush')
        return 0
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONPATH'] = str(c.TOOL)
    # 所有可能临时文件也约束到工作区。
    temp = safe(c.CACHE / 'prepush-temp')
    temp.mkdir(parents=True, exist_ok=True)
    env['TEMP'] = env['TMP'] = str(temp)
    command = [sys.executable, str(CHECKER), '--server-dir', str(VIRTUAL),
               '--base-store', str(c.BASE / 'production'), '--since', '1.4.136',
               '--json', str(c.OUT / 'prepush.json'), '--verbose']
    entry_raw = (c.OUT / 'manifest-entry-1.4.137.json').read_bytes()
    candidate = json.loads(entry_raw)
    for artifact in candidate['archive_integrity']:
        disk = VIRTUAL / 'assets/asset-patch/active' / artifact['name']
        assert c.sha(disk.read_bytes()) == artifact['sha256'], artifact['name']
    run = subprocess.run(command, cwd=c.ROOT, env=env, capture_output=True,
                         text=True, encoding='utf-8')
    write(c.OUT / 'prepush.txt', (run.stdout + ('\nSTDERR:\n' + run.stderr if run.stderr else '')).encode('utf-8'))
    counts = re.findall(r'合计: ERROR (\d+)\s+WARN (\d+)\s+INFO (\d+)', run.stdout)
    summary = {'returncode': run.returncode, 'since': '1.4.136', 'edge': '1.4.136->1.4.137',
               'hui_ref': hui.ref, 'archives': archive_count,
               'checker': str(CHECKER), 'checker_sha256': c.sha(CHECKER.read_bytes()),
               'base_store': str(c.BASE / 'production'), 'virtual_server': str(VIRTUAL),
               'manifest_entry_sha256': c.sha(entry_raw),
               'candidate_artifacts': [{k: x[k] for k in ('name', 'size', 'sha256', 'members')}
                                       for x in candidate['archive_integrity']],
               'command': command, 'counts': dict(zip(['ERROR', 'WARN', 'INFO'], map(int, counts[-1]))) if counts else None,
               'git_writes': False, 'server_started': False}
    c.write_json(c.OUT / 'prepush-summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return run.returncode


if __name__ == '__main__':
    raise SystemExit(main())

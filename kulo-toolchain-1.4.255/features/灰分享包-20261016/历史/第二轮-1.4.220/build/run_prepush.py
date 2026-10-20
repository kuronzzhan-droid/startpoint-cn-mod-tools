"""在独立目录构造灰136→220与测试219→220全链视图，调用原版 prepush。"""
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


def pure_chain(ref, virtual, suffix):
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
    output = virtual / 'out/routes/cn/asset.js'
    write(output, result['js'].encode('utf-8'))
    probe = r'''
const a=require(process.argv[1]);
const one='pinball-1.4.136-1.4.220-1-a.zip';
const two='pinball-1.4.136-1.4.220-2-b.zip';
const third='pinball-1.4.136-1.4.220-3-c.zip';
const duplicate='pinball-1.4.136-1.4.220-1-b.zip';
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
    c.write_json(c.OUT / f'prepush{suffix}-chain-source.json', {
        'ref': ref, 'source': 'src/routes/cn/asset.ts', 'source_sha256': c.sha(source),
        'functions': [{'name': v['name'], 'sha256': c.sha(v['text'].encode('utf-8'))}
                      for v in result['parts']],
        'output_sha256': c.sha(result['js'].encode('utf-8')),
        'method': 'TypeScript AST原文提取+transpileModule，仅四个真实纯函数及类型接口，无stub',
        'selftest': json.loads(checked.stdout),
    })


def prepare(mode):
    hui = c.View('hui')
    virtual = c.CACHE / ('prepush-hui-220' if mode == 'hui' else 'prepush-align-220')
    suffix = '' if mode == 'hui' else '-align'
    if mode == 'hui':
        assets = c.CACHE / 'server-merged-assets'
        manifest = json.loads(c.git_show('assets/asset-patch/manifest.json', hui.ref))
        entry_path = c.OUT / 'manifest-entry-1.4.220.json'
    else:
        assets = c.OURS_MANIFEST.parents[1]
        manifest = c.View('ours').manifest
        entry_path = c.OUT / 'manifest-entry-align-1.4.220.json'
    if not (assets / 'item_ids.json').is_file():
        raise FileNotFoundError(str(assets / 'item_ids.json'))
    for source in assets.rglob('*.json'):
        if 'asset-patch' not in source.relative_to(assets).parts:
            write(virtual / 'assets' / source.relative_to(assets), source.read_bytes())
    active = virtual / 'assets/asset-patch/active'
    active.mkdir(parents=True, exist_ok=True)
    expected, evidence = set(), []
    for entry in manifest['patches']:
        if entry.get('type') != 'patch' or entry.get('enabled') is not True:
            continue
        for name in c.archives(entry):
            expected.add(name)
            candidate = next((d / name for d in c.OURS_DIRS if (d / name).is_file()), None) if mode == 'align' else None
            if candidate is None:
                candidate = c.CACHE / 'hui' / name
            raw = candidate.read_bytes() if candidate.is_file() else c.git_show('assets/asset-patch/active/' + name, hui.ref)
            raw, source_kind = resolve_lfs(raw, name)
            evidence.append({'name': name, 'size': len(raw), 'sha256': c.sha(raw), 'source': source_kind})
            dest = active / name
            if not dest.is_file() or c.sha(dest.read_bytes()) != c.sha(raw):
                write(dest, raw)
    entry = json.loads(entry_path.read_text('utf-8'))
    for name in c.archives(entry):
        expected.add(name)
        write(active / name, (c.OUT / name).read_bytes())
    unknown = {p.name for p in active.glob('*.zip')} - expected
    if unknown:
        raise RuntimeError('unexpected archives in virtual active: ' + ','.join(sorted(unknown)))
    manifest['patches'].append(entry)
    manifest['cdn_version'] = '1.4.220'
    c.write_json(virtual / 'assets/asset-patch/manifest.json', manifest)
    c.write_json(c.OUT / f'prepush{suffix}-inputs.json', {'hui_ref': hui.ref, 'archives': evidence, 'mode': mode})
    pure_chain(hui.ref, virtual, suffix)
    return hui, virtual, entry_path, suffix, len(expected)


def run_one(mode, prepare_only=False):
    hui, virtual, entry_path, suffix, archive_count = prepare(mode)
    if prepare_only:
        print('prepared', mode, archive_count, 'archives; full prepush not run')
        return 0
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONPATH'] = str(c.TOOL)
    temp = safe(c.CACHE / ('prepush-temp-' + mode))
    temp.mkdir(parents=True, exist_ok=True)
    env['TEMP'] = env['TMP'] = str(temp)
    since = '1.4.136' if mode == 'hui' else '1.4.219'
    command = [sys.executable, str(CHECKER), '--server-dir', str(virtual),
               '--base-store', str(c.BASE / 'production'), '--since', since,
               '--json', str(c.OUT / f'prepush{suffix}.json'), '--verbose']
    entry_raw = entry_path.read_bytes()
    candidate = json.loads(entry_raw)
    for artifact in candidate['archive_integrity']:
        disk = virtual / 'assets/asset-patch/active' / artifact['name']
        assert c.sha(disk.read_bytes()) == artifact['sha256'], artifact['name']
    run = subprocess.run(command, cwd=c.ROOT, env=env, capture_output=True,
                         text=True, encoding='utf-8')
    write(c.OUT / f'prepush{suffix}.txt', (run.stdout + ('\nSTDERR:\n' + run.stderr if run.stderr else '')).encode('utf-8'))
    counts = re.findall(r'ERROR (\d+)\s+WARN (\d+)\s+INFO (\d+)', run.stdout)
    summary = {'returncode': run.returncode, 'since': since, 'edge': since + '->1.4.220',
               'mode': mode, 'hui_ref': hui.ref, 'archives': archive_count,
               'checker': str(CHECKER), 'checker_sha256': c.sha(CHECKER.read_bytes()),
               'base_store': str(c.BASE / 'production'), 'virtual_server': str(virtual),
               'manifest_entry_sha256': c.sha(entry_raw),
               'candidate_artifacts': [{k: x[k] for k in ('name', 'size', 'sha256', 'members')}
                                       for x in candidate['archive_integrity']],
               'command': command, 'counts': dict(zip(['ERROR', 'WARN', 'INFO'], map(int, counts[-1]))) if counts else None,
               'git_writes': False, 'server_started': False, 'allowlist': None}
    c.write_json(c.OUT / f'prepush{suffix}-summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return run.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare-only', action='store_true')
    ap.add_argument('--mode', choices=['hui', 'align', 'both'], default='both')
    args = ap.parse_args()
    modes = ['hui', 'align'] if args.mode == 'both' else [args.mode]
    return max(run_one(mode, args.prepare_only) for mode in modes)


if __name__ == '__main__':
    raise SystemExit(main())

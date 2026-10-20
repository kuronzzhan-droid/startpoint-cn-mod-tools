"""在分享包工作区内验证按键应用、污染拒绝与格式保持。"""
import codecs
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '交付'
CACHE = ROOT / 'cache'
spec = importlib.util.spec_from_file_location('apply_server_entries', OUT / 'apply_server_entries.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject(raw, spec):
    try:
        app.patch_text(raw, spec)
    except ValueError:
        return
    raise AssertionError('应拒绝但未拒绝')


def main():
    document = json.loads((OUT / 'server-entries.json').read_text('utf-8'))
    target = CACHE / 'server-apply-verification'
    target.mkdir(exist_ok=True)
    # 固定测试目录内只复制覆盖同源文件；不删除任何目录。
    for source in (CACHE / 'server-origin-assets').rglob('*.json'):
        destination = target / source.relative_to(CACHE / 'server-origin-assets')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    new = target / 'character_overlimit.json'
    if new.exists():
        new.unlink()
    command = [sys.executable, str(OUT / 'apply_server_entries.py'), '--assets', str(target)]
    dry_run = subprocess.check_output(command).decode().strip()
    applied = subprocess.check_output(command + ['--apply']).decode().strip()
    for item in document['files']:
        relative = item['file'].removeprefix('assets/')
        actual = target / relative
        expected = CACHE / 'server-merged-assets' / relative
        assert actual.read_bytes() == expected.read_bytes(), relative
        baseline = CACHE / 'server-origin-assets' / relative
        if baseline.exists():
            before, after = baseline.read_bytes(), actual.read_bytes()
            assert (b'\r\n' in before) == (b'\r\n' in after), relative
            if b'\r\n' in before:
                assert b'\n' not in after.replace(b'\r\n', b''), relative
    before = {p.relative_to(target).as_posix(): digest(p) for p in target.rglob('*.json')}
    repeated = subprocess.run(command + ['--apply'], capture_output=True)
    assert repeated.returncode != 0
    after = {p.relative_to(target).as_posix(): digest(p) for p in target.rglob('*.json')}
    assert before == after, '拒绝重复应用后不能写任何文件'
    fixture = codecs.BOM_UTF8 + '{\r\n    "keep" : [ 1, 2 ],\r\n    "改" : { "旧" : 1 }\r\n}\r\n'.encode('utf-8')
    update = {'kind': 'object', 'entries': [
        {'key': '改', 'expected': {'exists': True, 'value': {'旧': 1}}, 'value': {'新': 2}},
        {'key': '加', 'expected': {'exists': False}, 'value': ['中文', {'值': 3}]}]}
    result = app.patch_text(fixture, update)
    assert result.startswith(codecs.BOM_UTF8)
    assert b'    "keep" : [ 1, 2 ],\r\n' in result
    assert b'\n' not in result.replace(b'\r\n', b'')
    assert json.loads(result)['加'][0] == '中文'
    reject(fixture.replace(b'1 }', b'9 }'), update)
    reject(b'{"x":1,"x":1}', {'kind': 'object', 'entries': []})
    id_spec = {'kind': 'id-list', 'entries': [{'value': 3}]}
    assert json.loads(app.patch_text(b'[1, 9]\n', id_spec)) == [1, 9, 3]
    reject(b'[1,3]\n', id_spec)
    result = {'full_origin_dry_run': json.loads(dry_run), 'full_origin_apply': json.loads(applied),
              'files_match_merged_view': len(document['files']), 'repeated_apply_rejected_without_writes': True,
              'preserved_original_line_endings': True, 'preserved_bom_and_unrelated_bytes': True,
              'dirty_key_rejected': True, 'duplicate_json_key_rejected': True,
              'id_list_preserved_unrelated_id_and_rejected_existing_id': True}
    (ROOT / 'audit' / 'server-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

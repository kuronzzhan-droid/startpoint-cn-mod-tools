"""只读导出超限源码补充，逐 hunk 在内存验证，不执行 Git 写操作。"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPO = Path('D:/WF/startpoint-cn-kulo')
COMMIT = 'b75872031797413fe11ca49b516b517980ce65c7'


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def apply_hunks_in_memory(original, patch):
    source = original.splitlines(keepends=True)
    lines = patch.splitlines(keepends=True)
    result, consumed, i = [], 0, 0
    while i < len(lines):
        header = re.match(rb'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', lines[i])
        if header is None:
            i += 1
            continue
        start = max(0, int(header[1]) - 1)
        before, after = [], []
        i += 1
        while i < len(lines) and not lines[i].startswith((b'@@ ', b'diff --git ')):
            line = lines[i]
            if line.startswith(b'\\ No newline'):
                raise ValueError('本静态核对器不支持无末尾换行的 hunk')
            if line.startswith((b' ', b'-')):
                before.append(line[1:])
            if line.startswith((b' ', b'+')):
                after.append(line[1:])
            i += 1
        assert source[start:start + len(before)] == before, ('hunk 基线上下文不匹配', start)
        result += source[consumed:start] + after
        consumed = start + len(before)
    result += source[consumed:]
    return b''.join(result)


def main():
    pin = ROOT / '交付/build/source-lock.json'
    if not pin.exists():pin = ROOT / 'cache/kulo-ref.json'
    pinned = json.loads(pin.read_text('utf-8')) if pin.exists() else {}
    hui = pinned.get('hui_ref',pinned.get('ref')) or 'origin/main'
    tree = set(git('ls-tree', '-r', '--name-only', hui).decode().splitlines())
    patch = git('show', COMMIT, '--format=', '--', 'src', 'tests/character-overlimit.test.js')
    blocks = [b'diff --git ' + p for p in patch.split(b'diff --git ')[1:]]
    evidence = []
    for block in blocks:
        path = block.splitlines()[0].decode().split(' b/', 1)[1]
        original = git('show', hui + ':' + path) if path in tree else b''
        expected = git('show', COMMIT + ':' + path)
        actual = apply_hunks_in_memory(original, block)
        assert actual == expected, ('最终字节不同', path)
        parent = git('show', COMMIT + '^:' + path) if path in tree else None
        assert parent is None or parent == original, ('修改文件不等于来源父提交', path)
        evidence.append({'file': path, 'action': 'modify' if path in tree else 'add',
                         'hui_baseline_sha256': sha(original) if path in tree else None,
                         'source_sha256': sha(expected), 'all_hunks_match_hui_in_memory': True,
                         'applied_memory_result_equals_source': True})
    target = ROOT / '交付/服务端源码补充/overlimit-server-b7587203.patch'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(patch)
    report = {'source_commit': COMMIT, 'hui_ref': hui, 'patch_sha256': sha(patch),
              'patch_size': len(patch), 'files': evidence,
              'validation': '逐 hunk 原上下文及结果字节在内存核对通过；未编译、未启动服务端、未应用到任何仓库。'}
    (ROOT / 'audit/server-source-supplement.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()

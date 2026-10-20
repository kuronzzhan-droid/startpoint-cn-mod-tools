"""旧仓 assets 已随磁盘清理删除：从 kulo 视图回填 PARADOX 生成器读取的源文件（PNG 改回标准签名；回响 DSL 存为 JSON 树）。"""
import json
from live149 import *
import wf_paradox_weapon as P
for logical, src, size, required in P.ASSET_FILES:
    try:
        raw, _ = read_raw(logical)
    except FileNotFoundError:
        print('missing', logical); continue
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b'\x89PNG' + raw[4:] if raw[:4] == b'\x89png' else raw)
    print('png', src.name)
P.ECHO_DIR.mkdir(parents=True, exist_ok=True)
for cid, code, _ in P.ECHOES:
    (P.ECHO_DIR / f"{code}.json").write_text(json.dumps(dsl_tree(P.echo_program(code)), ensure_ascii=False), 'utf-8')
    print('echo', code)

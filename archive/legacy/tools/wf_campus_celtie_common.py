"""Campus Celtie candidate I/O; official donors and live-preserving table splices."""
from __future__ import annotations

from wf.paths import root_path

import hashlib
import json
from pathlib import Path
import re
import zlib

import wf_assets
import wf_dsl
import wf_mod_tool as core
from wf_enhancement_policy import OfficialBaseline

ROOT = Path(('${WF_ROOT}/startpoint-cn'.replace("${WF_ROOT}", str(root_path()))))
WORKSPACE = ROOT / 'work/character_packs/campus-celtie-20260911'
PACKAGE = WORKSPACE / 'package'
EVIDENCE = WORKSPACE / 'evidence'
CID, TEMPLATE_ID = '149989', '141201'
CODE, TEMPLATE_CODE = 'wind_spgirl_campus', 'wind_spgirl_4anv'
PACKAGE_ID = 'campus-celtie-20260911'
STORE = ROOT / '弹国服/WorldFlipper/dummy/download/production/upload'
BASELINE = OfficialBaseline(ROOT / '.cdn/cn',
    cache_dir=ROOT / 'mod-tools/work/official-baseline', write_cache=False)
CLAIMS: list[dict] = []
SOURCES: dict[str, dict] = {}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def output(root: str, logical: str) -> Path:
    if root not in ('common', 'medium', 'android', 'server'):
        raise ValueError('unsupported candidate root')
    if ':' in logical or any(p in ('', '.', '..') for p in logical.replace('\\', '/').split('/')):
        raise ValueError('logical path is not a relative asset path')
    for item in (PACKAGE,*PACKAGE.parents):
        if item.is_symlink() or getattr(item,'is_junction',lambda:False)():
            raise ValueError('candidate package has a reparse component')
    path = (PACKAGE / 'roots' / root / logical).resolve()
    if not path.is_relative_to((PACKAGE / 'roots' / root).resolve()):
        raise ValueError('candidate path escapes workspace')
    return path


def write(root: str, logical: str, data: bytes) -> Path:
    marker = json.loads((WORKSPACE / 'workspace.json').read_bytes())
    if (marker['character_id'], marker['code_name']) != (int(CID), CODE):
        raise ValueError('workspace identity differs from assigned character')
    path = output(root, logical)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if path.read_bytes() != data:
        raise OSError(f'candidate write readback failed: {logical}')
    return path


def evidence(name: str, value) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def official(logical: str, root: str = 'common') -> bytes:
    digest = core.sha1_path(logical)
    raw = BASELINE.get(root, digest[:2]+'/'+digest[2:])
    if raw is None:
        raise ValueError(f'official donor absent: {root}/{logical}')
    SOURCES[f'{root}/{logical}'] = {'sha256': sha(raw), 'size': len(raw), 'official_tail': BASELINE.official_tail}
    return raw


def official_asset(logical: str):
    digest = core.sha1_path(logical)
    rel = digest[:2]+'/'+digest[2:]
    found = [root for root in ('common','medium','android') if BASELINE.identity(root,rel) is not None]
    if len(found)!=1:
        raise ValueError(f'official asset must have one authoritative root: {logical}: {found}')
    return found[0], official(logical,found[0])


def official_flat(logical: str) -> dict[str, str]:
    return core.read_orderedmap_file_from_bytes(official(logical))


def official_raw(logical: str):
    return core.read_orderedmap_raw_rows_from_bytes(official(logical), logical)


def official_rows(table: str, key: str) -> list[list[str]]:
    return core.read_csv_lines(official_flat(f'master/ability/{table}.orderedmap')[key])


def claim(logical: str, keys, codec='flat', root='common', inner=None):
    CLAIMS.append({'codec_id': codec, 'inner_keys': inner or [], 'logical_path': logical,
        'outer_keys': sorted(keys), 'root': root, 'semantic_claims': []})


def flat(logical: str, additions: dict[str, str]):
    live = core.load_table(logical, STORE)
    before = live.text_rows()
    if set(additions) & set(before):
        raise ValueError(f'new identity already occupied: {logical}')
    live.set_text_rows(additions)
    raw = core.build_orderedmap(live)
    after = core.read_orderedmap_file_from_bytes(raw)
    if any(after[k] != v for k, v in before.items()) or any(after[k] != v for k,v in additions.items()):
        raise ValueError(f'unclaimed row drift or invalid roundtrip: {logical}')
    write('common', logical, raw)
    claim(logical, additions)


def raw_outer(logical: str, additions: dict[str, bytes], codec='raw_outer', inner=None):
    table = core.read_orderedmap_file_raw_rows(core.table_path(STORE, logical), logical)
    before = dict(zip(table.keys, table.rows))
    if set(additions) & set(before):
        raise ValueError(f'new identity already occupied: {logical}')
    table.keys.extend(additions)
    table.rows.extend(additions.values())
    raw = core.build_orderedmap_raw_rows(table)
    back = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
    after = dict(zip(back.keys, back.rows))
    if any(after[k] != v for k,v in (before | additions).items()):
        raise ValueError(f'raw row splice changed content: {logical}')
    write('common', logical, raw)
    claim(logical, additions, codec=codec, inner=inner)


def remap(cell: str) -> str:
    if cell==TEMPLATE_ID:
        return CID
    if re.fullmatch(str(int(TEMPLATE_ID)*2)+r'\d{3}', cell):
        return str(int(CID)*2)+cell[-3:]
    return cell.replace(TEMPLATE_CODE, CODE)


def clone_blob(blob: bytes, transform=remap) -> bytes:
    try:
        text = zlib.decompress(blob).decode('utf-8')
    except (zlib.error, UnicodeDecodeError):
        table = core.read_orderedmap_raw_rows_from_bytes(blob, 'nested')
        table.keys = [transform(k) for k in table.keys]
        table.rows = [clone_blob(r, transform) for r in table.rows]
        return core.build_orderedmap_raw_rows(table)
    rows = core.read_csv_lines(text)
    mapped = [[transform(c) for c in row] for row in rows]
    return blob if rows == mapped else zlib.compress(core.write_csv_lines(mapped).rstrip('\n').encode('utf-8'))


def clone_outer(logical: str, transform=remap):
    table = official_raw(logical)
    blob = dict(zip(table.keys, table.rows))[TEMPLATE_ID]
    raw_outer(logical, {CID: clone_blob(blob, transform)})


def server(logical: str, addition):
    before = json.loads((ROOT / 'assets' / logical).read_bytes())
    if CID in before:
        raise ValueError(f'server identity occupied: {logical}')
    after = dict(before)
    after[CID] = addition
    raw = json_bytes(after)
    back = json.loads(raw)
    if any(back[k] != v for k,v in before.items()) or back[CID] != addition:
        raise ValueError(f'server splice changed unowned rows: {logical}')
    write('server', logical, raw)
    claim(logical, [CID], codec='json_object', root='server')


def amf(raw: bytes):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']


def amf_bytes(tree) -> bytes:
    raw = zlib.compress(wf_dsl.encode_amf3(tree), 9)[2:-4]
    if amf(raw) != tree:
        raise ValueError('AMF3 roundtrip differs')
    return raw


def walk(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from walk(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from walk(child)


def commands(tree, name: str):
    return [n[1] for n in walk(tree) if isinstance(n,list) and len(n)==2
        and n[0]=='Command' and isinstance(n[1],list) and n[1] and n[1][0]==name]

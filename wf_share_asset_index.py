"""Validate a complete, scoped character-media share before receiver writes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import zipfile

SALT = 'K6R9T9Hz22OpeIGEWB0ui6c6PYFQnJGy'
TIERS = {'common': 'upload', 'medium': 'medium_upload', 'android': 'android_upload'}


def digest_file(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError('Expected a regular file: ' + str(path))
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative_path(logical: str) -> str:
    if (not isinstance(logical, str) or not logical or '\\' in logical or ':' in logical
            or logical.startswith('/') or any(x in ('', '.', '..') for x in logical.split('/'))):
        raise ValueError('Unsafe logical asset path')
    value = hashlib.sha1((logical + SALT).encode('utf-8')).hexdigest()
    return value[:2] + '/' + value[2:]


def target(roots: dict[str, Path], row: dict) -> Path:
    root = roots[row['root']]
    dest = root / row['relative']
    if dest.resolve() != dest or not dest.is_relative_to(root):
        raise ValueError('Asset path alias or escape: ' + str(dest))
    return dest


def inspect(package: Path, store: Path) -> dict:
    package, store = package.resolve(strict=True), store.resolve()
    roots = {key: (store if key == 'common' else store.parent / folder).resolve()
             for key, folder in TIERS.items()}
    if len(set(roots.values())) != 3:
        raise ValueError('Receiver resource roots overlap')
    manifest_path = package / 'asset-manifest.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get('schema_version') != 2:
        raise ValueError('Unsupported asset manifest schema')
    rows, parts = manifest['assets'], manifest['archives']
    expected, archive_hashes = {}, {}
    for row in rows:
        if row['root'] not in roots or row['classification'] not in ('owned', 'dependency'):
            raise ValueError('Unknown resource root or ownership')
        rel = relative_path(row['logical'])
        member = 'production/' + TIERS[row['root']] + '/' + rel
        if row['relative'] != rel or row['member'] != member or member in expected:
            raise ValueError('Invalid or duplicate resource mapping')
        if row['logical'].startswith('master/'):
            raise ValueError('Shared tables must use the separate keyed receiver')
        if not re.fullmatch('[0-9a-f]{64}', row['sha256']) or type(row['size']) is not int or row['size'] < 0:
            raise ValueError('Invalid size or digest')
        if 'approved_before_sha256' in row:
            approved = row['approved_before_sha256']
            if (row['classification'] != 'dependency' or not isinstance(approved, str)
                    or not re.fullmatch('[0-9a-f]{64}', approved)):
                raise ValueError('Invalid approved dependency preimage digest')
        if 'approved_before_sha256s' in row:
            approved = row['approved_before_sha256s']
            if (row['classification'] != 'dependency' or not isinstance(approved, list)
                    or not approved or any(not isinstance(value, str)
                    or not re.fullmatch('[0-9a-f]{64}', value) for value in approved)
                    or len(set(approved)) != len(approved)):
                raise ValueError('Invalid approved dependency preimage digests')
        expected[member] = row
    seen, source_members = set(), {}
    for part in parts:
        rel = part['path']
        if not isinstance(rel, str) or not rel.startswith('assets/') or '\\' in rel:
            raise ValueError('Invalid asset archive path')
        path = package / rel
        if path.resolve() != path or not path.is_relative_to(package) or '..' in Path(rel).parts:
            raise ValueError('Archive escaped package')
        actual = digest_file(path)
        if actual != part['sha256'] or str(path) in archive_hashes:
            raise ValueError('Archive hash mismatch or duplicate')
        archive_hashes[str(path)] = actual
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                row = expected.get(info.filename)
                if row is None or info.filename in seen or info.is_dir() or info.flag_bits & 1:
                    raise ValueError('Unexpected, duplicate or encrypted ZIP member')
                if info.file_size != row['size']:
                    raise ValueError('ZIP member size differs')
                with archive.open(info) as stream:
                    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
                if actual != row['sha256']:
                    raise ValueError('ZIP member content differs')
                seen.add(info.filename)
                source_members[info.filename] = str(path)
    if seen != set(expected):
        raise ValueError('Asset archive closure incomplete')
    entries, conflicts = [], []
    for row in rows:
        dest = target(roots, row)
        before = digest_file(dest)
        if (row['classification'] == 'dependency'
                and before not in (None, row['sha256'], row.get('approved_before_sha256'),
                                   *row.get('approved_before_sha256s', []))):
            conflicts.append(dict(logical=row['logical'], current_sha256=before,
                                  incoming_sha256=row['sha256']))
        entries.append(dict(row, destination=str(dest), before_sha256=before,
                            archive=source_members[row['member']]))
    return dict(schema_version=1, package=str(package), store=str(store),
                manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(), archives=archive_hashes,
                entries=entries, conflicts=conflicts)

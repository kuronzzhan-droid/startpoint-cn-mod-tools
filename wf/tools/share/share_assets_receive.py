"""Receive exact character media with whole-input preflight and retained preimages."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import time
import uuid
import zipfile

from wf_share_asset_index import digest_file, inspect


def atomic_json(path: Path, value: dict) -> None:
    temp = path.with_name(path.name + '.writing-' + uuid.uuid4().hex)
    with temp.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    replace(temp, path)


def replace(source: Path, destination: Path) -> None:
    for attempt in range(6):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(.2 * (attempt + 1))


def record(stream, phase: str, member: str) -> None:
    stream.write(json.dumps(dict(phase=phase, member=member)) + '\n')
    stream.flush()
    os.fsync(stream.fileno())


def apply_plan(plan: dict, output: Path) -> dict:
    output = output.resolve()
    if plan['conflicts']:
        raise ValueError('Shared dependency conflicts must be reviewed before apply')
    if output.exists():
        raise ValueError('Use a new receiver receipt directory')
    store = Path(plan['store'])
    protected_roots = [store, store.parent / 'medium_upload', store.parent / 'android_upload']
    if any(output.is_relative_to(root) or root.is_relative_to(output) for root in protected_roots):
        raise ValueError('Receipt directory must be separate from installed resource roots')
    if digest_file(Path(plan['package']) / 'asset-manifest.json') != plan['manifest_sha256']:
        raise ValueError('Manifest drift after preflight')
    for path, digest in plan['archives'].items():
        if digest_file(Path(path)) != digest:
            raise ValueError('Archive drift after preflight')
    for entry in plan['entries']:
        dest = Path(entry['destination'])
        if dest.resolve() != dest or digest_file(dest) != entry['before_sha256']:
            raise ValueError('Receiver changed after preflight: ' + entry['logical'])
    output.mkdir(parents=True)
    atomic_json(output / 'preflight.json', plan)
    receipt = dict(complete=False, applied=[], attempted=None, published=False,
                   journal='journal.jsonl', recovery='Inspect journal and preimages after interruption; no blind retry.')
    report_path = output / 'transaction.json'
    atomic_json(report_path, receipt)
    stack = ExitStack()
    try:
        archives = {path: stack.enter_context(zipfile.ZipFile(path)) for path in plan['archives']}
        journal = stack.enter_context((output / 'journal.jsonl').open('x', encoding='utf-8', newline='\n'))
        for entry in plan['entries']:
            if entry['before_sha256'] == entry['sha256']:
                continue
            dest = Path(entry['destination'])
            if dest.resolve() != dest or digest_file(dest) != entry['before_sha256']:
                raise ValueError('Concurrent receiver edit: ' + entry['logical'])
            receipt['attempted'] = entry['member']
            record(journal, 'attempted', entry['member'])
            if entry['before_sha256'] is not None:
                backup = output / 'before' / entry['root'] / entry['relative']
                backup.parent.mkdir(parents=True, exist_ok=True)
                with dest.open('rb') as source, backup.open('xb') as sink:
                    shutil.copyfileobj(source, sink)
                if digest_file(backup) != entry['before_sha256']:
                    raise ValueError('Backup verification failed')
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp = dest.with_name(dest.name + '.wfshare-' + uuid.uuid4().hex)
            with archives[entry['archive']].open(entry['member']) as source, temp.open('xb') as sink:
                shutil.copyfileobj(source, sink)
                sink.flush()
                os.fsync(sink.fileno())
            if digest_file(temp) != entry['sha256'] or digest_file(dest) != entry['before_sha256']:
                raise ValueError('Asset bytes drifted while staging')
            if dest.resolve() != dest:
                raise ValueError('Receiver path changed while staging')
            replace(temp, dest)
            receipt['applied'].append(entry['member'])
            receipt['attempted'] = None
            record(journal, 'applied', entry['member'])
        for entry in plan['entries']:
            if digest_file(Path(entry['destination'])) != entry['sha256']:
                raise ValueError('Installed asset readback mismatch')
        receipt['complete'] = True
    except BaseException as exc:
        receipt['error'] = type(exc).__name__ + ': ' + str(exc)
        receipt['recovery'] = 'Keep receipt and preimages. Inspect attempted/applied paths; do not retry or restore blindly.'
        raise
    finally:
        stack.close()
        atomic_json(report_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--store', type=Path, required=True, help='Receiver production/upload directory')
    parser.add_argument('--output', type=Path, required=True, help='New local report directory')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    plan = inspect(args.package, args.store)
    if args.apply:
        result = apply_plan(plan, args.output)
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        atomic_json(args.output / 'preflight.json', plan)
        result = dict(ready=not plan['conflicts'], total=len(plan['entries']),
                      changes=sum(e['before_sha256'] != e['sha256'] for e in plan['entries']),
                      conflicts=plan['conflicts'], applied=False, published=False)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not plan['conflicts'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

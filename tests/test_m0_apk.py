"""Offline ABC/SWF tests require neither an APK nor an Android toolchain."""
import importlib
import struct
import sys

import pytest

from wf.apk import asm
from wf.apk.abcfmt import ABC
from wf.apk.common import abc_tags, sha
from wf.apk.patching import Refused, apply_patches


def fixture_swf():
    abc = ABC(struct.pack('<HH', 16, 46) + b'\x01' * 7 + b'\0' * 5)
    abc.strings = [b'', b'Demo']
    abc.namespaces = [(0, 0), (0x16, 0)]
    abc.multinames = [(0,), (7, 1, 1)]
    abc.methods = [[0, [], 0, 0, None, None] for _ in range(2)]
    abc.instances = [[1, 0, 0, None, [], 0, []]]
    abc.classes = [[1, []]]
    abc.bodies = [[0, 1, 1, 0, 0, b'\x24\x01\x48', [], []],
                  [1, 0, 1, 0, 0, b'\x47', [], []]]
    raw = abc.serialize()
    assert ABC(raw).serialize() == raw
    content = b'\0' * 4 + b'boot_ffc6\0' + raw
    data = b'\0' * 5 + struct.pack('<HI', (82 << 6) | 63, len(content)) + content
    data += struct.pack('<H', (9 << 6) | 3) + b'RGB' + b'\0\0'
    return b'FWS\x0a' + struct.pack('<I', len(data) + 8) + data


def fixture_patch():
    def apply(abc, index, pool):
        abc.bodies[index][5] = b'\x24\x02\x48'
    return {'id': 'offline-demo', 'tag': b'boot_ffc6', 'label': 'Demo/<ctor>',
            'before': sha(b'\x24\x01\x48'), 'after': sha(b'\x24\x02\x48'), 'apply': apply}


def test_method_patch_exact_unrelated_bytes_and_idempotence():
    source = fixture_swf()
    patched, report = apply_patches(source, [fixture_patch()])
    before, after = ABC(abc_tags(source)[0][4]), ABC(abc_tags(patched)[0][4])
    assert after.bodies[0][5] == b'\x24\x02\x48'
    assert before.bodies[1] == after.bodies[1]
    assert source[-7:] == patched[-7:]
    assert report['patches'][0]['status'] == 'applied'
    repeated, report = apply_patches(patched, [fixture_patch()])
    assert repeated == patched
    assert report['patches'][0]['status'] == 'already_present'


def test_unknown_method_hash_refuses_without_mutating_source():
    source = fixture_swf()
    original = bytes(source)
    patch = fixture_patch()
    patch['before'] = '0' * 64
    with pytest.raises(Refused, match='matches neither'):
        apply_patches(source, [patch])
    assert source == original


def test_patcher_rejects_unrelated_method_change():
    patch = fixture_patch()
    original_apply = patch['apply']
    def bad_apply(abc, index, pool):
        original_apply(abc, index, pool)
        abc.bodies[1][5] = b'\x02\x47'
    patch['apply'] = bad_apply
    with pytest.raises(Refused, match='unrelated body'):
        apply_patches(fixture_swf(), [patch])


def test_assembler_branch_roundtrip_and_splice():
    ins = asm.assemble([('pushtrue',), ('iffalse', 'done'), ('pushbyte', 7),
                        ('pop',), ('label', 'done'), ('returnvoid',)])
    raw, _ = asm.encode(ins)
    assert asm.encode(asm.decode(raw))[0] == raw
    body = [0, 1, 1, 0, 0, raw, [], []]
    block = asm.assemble([('nop',)])
    updated, exceptions, merged = asm.splice(body, 2, block)
    assert not exceptions
    assert merged[1].target == 5
    assert asm.encode(asm.decode(updated))[0] == updated
    assert asm.simulate(merged, 0)[:2] == (1, 0)


def test_package_import_does_not_change_import_paths_or_bytecode_policy():
    old_path, old_policy = list(sys.path), sys.dont_write_bytecode
    import wf.apk.common as common
    importlib.reload(common)
    assert sys.path == old_path
    assert sys.dont_write_bytecode == old_policy
    assert asm.load_abc_module('abcfmt') is importlib.import_module('wf.apk.abcfmt')
    with pytest.raises(ValueError, match='unsupported ABC helper'):
        asm.load_abc_module('../outside')

"""Lossless AMF3 tree documents for packed enemy behavior resources.

The wire image retains string references, noncanonical numbers and compression.
Edits are encoded canonically; surrogateescape preserves legacy non-UTF8 bytes.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import struct
import zlib

import wf_dsl


class _Reader(wf_dsl._Parser):
    def read_string(self):
        ref, self.i = wf_dsl._read_u29(self.b, self.i)
        if not ref & 1:
            if ref >> 1 >= len(self.strings):
                raise ValueError('invalid AMF3 string reference')
            return self.strings[ref >> 1]
        size = ref >> 1
        raw = self.b[self.i:self.i + size]
        if len(raw) != size:
            raise ValueError('truncated AMF3 string')
        self.i += size
        value = raw.decode('utf-8', errors='surrogateescape')
        if value:
            self.strings.append(value)
        return value


def read_tree(data):
    reader = _Reader(data)
    try:
        tree = reader.read_value()
    except (IndexError, UnicodeError, struct.error) as error:
        raise ValueError('invalid AMF3 behavior resource') from error
    if reader.i != len(data):
        raise ValueError('trailing AMF3 behavior bytes')
    return tree


def write_tree(tree):
    out, strings, traits = bytearray(), {}, False

    def number(value):
        if not 0 <= value < (1 << 29):
            raise ValueError('AMF3 U29 outside range')
        width = 1 if value < 128 else 2 if value < 16384 else 3 if value < 2097152 else 4
        out.extend(wf_dsl.encode_u29_padded(value, width))

    def string(value):
        if not value:
            number(1)
        elif value in strings:
            number(strings[value] << 1)
        else:
            raw = value.encode('utf-8', errors='surrogateescape')
            number((len(raw) << 1) | 1)
            out.extend(raw)
            strings[value] = len(strings)

    def emit(value):
        nonlocal traits
        if value is None:
            out.append(1)
        elif isinstance(value, bool):
            out.append(3 if value else 2)
        elif isinstance(value, int) and -(1 << 28) <= value < (1 << 28):
            out.append(4); number(value & 0x1fffffff)
        elif isinstance(value, (int, float)):
            out.append(5); out.extend(struct.pack('>d', value))
        elif isinstance(value, str):
            out.append(6); string(value)
        elif isinstance(value, list):
            out.append(9); number((len(value) << 1) | 1); number(1)
            for item in value:
                emit(item)
        elif isinstance(value, dict):
            out.append(10); number(1 if traits else 11)
            if not traits:
                string(''); traits = True
            for key, item in value.items():
                if not isinstance(key, str) or not key:
                    raise ValueError('AMF3 object keys must be nonempty strings')
                string(key); emit(item)
            number(1)
        else:
            raise ValueError(f'unsupported AMF3 value: {type(value).__name__}')
    emit(tree)
    result = bytes(out)
    if read_tree(result) != tree:
        raise ValueError('AMF3 semantic roundtrip failed')
    return result


def compress(data):
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(data) + compressor.flush()


def decode_wire(raw):
    if not isinstance(raw, bytes):
        raise ValueError('behavior resource must be bytes')
    try:
        tree = read_tree(zlib.decompress(raw, -15))
    except zlib.error as error:
        raise ValueError('behavior resource is not raw deflate') from error
    return {'tree': tree, 'wire': base64.b64encode(raw).decode('ascii'),
            'sha256': hashlib.sha256(raw).hexdigest()}


def encode_wire(document, tree=None):
    raw = base64.b64decode(document['wire'], validate=True)
    if hashlib.sha256(raw).hexdigest() != document['sha256']:
        raise ValueError('behavior wire SHA-256 mismatch')
    original = decode_wire(raw)['tree']
    candidate = document['tree'] if tree is None else tree
    if candidate == original:
        return raw
    return compress(write_tree(copy.deepcopy(candidate)))

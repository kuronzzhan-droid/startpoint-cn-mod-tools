"""Production primitives extracted from wf_nephtim_fever_pixels.py (C baseline)."""
from __future__ import annotations
import zlib


import wf_dsl


def _decode(raw):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def _encode(tree):
    raw = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(raw)["tree"] != tree:
        raise ValueError("pixel metadata AMF roundtrip mismatch")
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(raw) + compressor.flush()

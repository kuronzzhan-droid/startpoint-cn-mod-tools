"""LiveReader over the 1.4.149 view + kulo server assets."""
import functools, json, sys, zlib
from .base149 import *
ASSETS = KULO / "assets"

@functools.lru_cache(maxsize=None)
def flat(logical):
    t = load(logical)
    return {k: [r for r in rows(v) if r] for k, v in t.items()}

@functools.lru_cache(maxsize=None)
def nested(logical):
    return load(logical)

@functools.lru_cache(maxsize=None)
def server(name):
    return json.loads((ASSETS / name).read_text("utf8"))

def reader(W):
    return W.LiveReader(flat, nested, server)

def dsl_tree(program):
    import wf_dsl
    raw, _ = read_raw(wf_dsl.dsl_logical(program))
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]

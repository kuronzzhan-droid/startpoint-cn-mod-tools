"""perf-v30: method-level ABC splice on top of v29-coop (no class recompilation).

Patch P1 `MasterBinaryMap/getIndex`:
  original: `return map._keys.indexOf(key)` (O(N) per master-table lookup; throws 8601 when missing).
  new prefix (inserted before the original body, original code kept intact as the fallback):
      d = this.cache.h[-1]                    # reverse index parked in the row cache's Dictionary at key -1
      if (!d) { d = new Dictionary(); this.cache.h[-1] = d;
                k = map._keys; i = k.length; while (i > 0) { i--; d[k[i]] = i; } }   # backwards: first occurrence wins
      v = d[key]; if (v === undefined) goto miss
      r = int(v)
      if (map._keys[r] === key) return r      # validated hit: identical to indexOf for unique keys
      this.cache.h[-1] = null                 # stale/miss: drop the index (rebuilt lazily next call)
      ... original indexOf / throw 8601 path, byte-identical ...
  `cache.h` only ever holds non-negative row indices (MasterMapBase.getByIndex returns null for <0 before
  touching the cache), so key -1 is never observed by hasCache/getCache/setCache.
  Only existing multinames (cache, h, map, _keys, length, the runtime MultinameL, flash.utils::Dictionary) are used.
"""
from __future__ import annotations

import copy
import json
import struct
import sys
import zlib

from common import (ABC, BASE_SWF_SHA, MAIN, ROOT, abc_tags, asm, bodies, freeze, listing, sha, swf_data)

COOP_LABEL = "BattleDerailleur/getDeferralLevel"
COOP_AFTER_SHA = "84e04501423fa23b0caeb53235652347b2d0d780ce526e1d7793a027951cb570"
CAPABILITY = ["master-binarymap-index-dict-v1"]


def mn_from(abc, body, position, name, expect_text):
    ins = asm.decode(body[5])[position]
    assert ins.name == name, (name, ins.name)
    assert abc.mn_name(ins.args[0]) == expect_text, (abc.mn_name(ins.args[0]), expect_text)
    return ins.args[0]


def p1_master_index(abc):
    labels = {"getIndex": "MasterBinaryMap/getIndex", "setCache": "MasterBinaryMap/setCache", "intmap": "IntMap/<ctor>"}
    idx = {k: bodies.resolve(abc, v) for k, v in labels.items()}
    body = abc.bodies[idx["getIndex"]]
    assert sha(body[5]) == "ec54f93d80b11c38480c43bb87966d0cf3ed05bf8bb3da7d47b0d11190517d1c", "getIndex guard"
    assert body[1:5] == [5, 6, 1, 2] and body[6] == [] and body[7] == [], "getIndex header guard"
    sc = abc.bodies[idx["setCache"]]
    assert sha(sc[5]) == "f8b8b39c5e8c3c95d9324b55aeb75d9bf43332126ccf4706f1a22a2d618da46b", "setCache guard"
    im = abc.bodies[idx["intmap"]]
    assert sha(im[5]) == "a04ff78745a5bf6fb6f8c9740ba542561015e5e59ee283e9278b5c2b5c2839f0", "IntMap ctor guard"
    m_cache = mn_from(abc, sc, 3, "getproperty", "cache")
    m_h = mn_from(abc, sc, 5, "getproperty", "h")
    mnl = asm.decode(sc[5])[8].args[0]
    assert asm.decode(sc[5])[8].name == "setproperty" and abc.multinames[mnl][0] == 0x1B, "MultinameL donor"
    m_map = mn_from(abc, body, 3, "getproperty", "map")
    m_keys = mn_from(abc, body, 15, "getproperty", "_keys")
    m_dict_find = mn_from(abc, im, 7, "findpropstrict", "flash.utils::Dictionary")
    m_dict_ctor = mn_from(abc, im, 8, "constructprop", "flash.utils::Dictionary")
    m_length = None
    for ins in asm.decode(body[5]):
        pass
    # `length` donor: CharacterTable/applyCharacters uses getproperty length on Arrays; take any QName/Multiname "length" used by getproperty.
    donor = abc.bodies[bodies.resolve(abc, "CharacterTable/applyCharacters")]
    for ins in asm.decode(donor[5]):
        if ins.name == "getproperty" and abc.mn_name(ins.args[0]) == "length":
            m_length = ins.args[0]
            break
    assert m_length is not None
    D, K, I, R = 6, 7, 8, 9
    block = asm.assemble([
        ("getlocal_0",), ("getproperty", m_cache), ("getproperty", m_h), ("pushbyte", 255), ("getproperty", mnl),
        ("setlocal", D), ("getlocal", D), ("iftrue", "HAVE"),
        ("findpropstrict", m_dict_find), ("constructprop", m_dict_ctor, 0), ("setlocal", D),
        ("getlocal_0",), ("getproperty", m_cache), ("getproperty", m_h), ("pushbyte", 255), ("getlocal", D), ("setproperty", mnl),
        ("getlocal_0",), ("getproperty", m_map), ("getproperty", m_keys), ("setlocal", K),
        ("getlocal", K), ("getproperty", m_length), ("convert_i",), ("setlocal", I),
        ("jump", "COND"),
        ("label", "LOOP"), ("avm_label",),
        ("declocal_i", I),
        ("getlocal", D), ("getlocal", K), ("getlocal", I), ("getproperty", mnl), ("getlocal", I), ("setproperty", mnl),
        ("label", "COND"),
        ("getlocal", I), ("pushbyte", 0), ("ifgt", "LOOP"),
        ("label", "HAVE"),
        ("getlocal", D), ("getlocal_1",), ("getproperty", mnl), ("setlocal", R),
        ("getlocal", R), ("pushundefined",), ("ifstricteq", "MISS"),
        ("getlocal", R), ("convert_i",), ("setlocal", R),
        ("getlocal_0",), ("getproperty", m_map), ("getproperty", m_keys), ("getlocal", R), ("getproperty", mnl),
        ("getlocal_1",), ("ifstrictne", "MISS"),
        ("getlocal", R), ("returnvalue",),
        ("label", "MISS"),
        ("getlocal_0",), ("getproperty", m_cache), ("getproperty", m_h), ("pushbyte", 255), ("pushnull",), ("setproperty", mnl),
    ])
    at = 2
    code = asm.decode(body[5])
    assert [code[0].name, code[1].name, code[2].name] == ["getlocal_0", "pushscope", "findproperty"], "insertion site"
    old_code = body[5]
    new_code, new_exc, merged = asm.splice(body, at, block, asm.FORBID)
    new_header = [body[1], 10, body[3], body[4]]
    metrics = asm.simulate(merged, new_header[2], abc.multinames)
    assert metrics[0] <= new_header[0] and metrics[1] <= new_header[3] and metrics[2] == 0, metrics
    assert asm.block_locals(merged) <= new_header[1], "local header insufficient"
    assert asm.unsplice(new_code, at, len(block)) == old_code, "inverse splice differs"
    body[1:5] = new_header
    body[5], body[6] = new_code, new_exc
    return idx["getIndex"], {
        "label": labels["getIndex"], "inserted_at": [[at, len(block), "forbid"]], "header_before": [5, 6, 1, 2],
        "header_after": new_header, "metrics": list(metrics), "multinames_used": {
            "cache": m_cache, "h": m_h, "MultinameL": mnl, "map": m_map, "_keys": m_keys, "length": m_length,
            "Dictionary(findpropstrict)": m_dict_find, "Dictionary(constructprop)": m_dict_ctor},
        "new_locals": {"dict": D, "keys": K, "i": I, "r": R}, "block_len": len(block),
        "old_code": old_code}


PATCHES = [p1_master_index]


def patch(swf: bytes):
    assert sha(swf) == BASE_SWF_SHA, "refusing unknown SWF (expect v29-coop)"
    signature, version = swf[:3], swf[3]
    data = swf_data(swf)
    tags = [t for t in abc_tags(swf) if t[0] == MAIN]
    assert len(tags) == 1
    _name, offset, size, prefix, raw = tags[0]
    abc = ABC(raw)
    assert abc.serialize() == raw, "main ABC roundtrip differs"
    original = copy.deepcopy(abc)
    coop = bodies.resolve(abc, COOP_LABEL)
    assert sha(abc.bodies[coop][5]) == COOP_AFTER_SHA, "v29 coop getDeferralLevel missing"
    methods, changed = {}, []
    for fn in PATCHES:
        index, meta = fn(abc)
        old_code = meta.pop("old_code")
        meta.update({"body": index, "method": abc.bodies[index][0], "before": sha(old_code), "after": sha(abc.bodies[index][5]),
                     "before_len": len(old_code), "after_len": len(abc.bodies[index][5])})
        methods[meta.pop("label")] = meta
        changed.append(index)
    for field in ("ints", "uints", "doubles", "strings", "namespaces", "ns_sets", "multinames", "methods", "metadata",
                  "instances", "classes", "scripts"):
        assert freeze(getattr(abc, field)) == freeze(getattr(original, field)), field
    assert len(abc.bodies) == len(original.bodies)
    unchanged = [i for i in range(len(abc.bodies)) if i not in changed]
    assert all(freeze(abc.bodies[i]) == freeze(original.bodies[i]) for i in unchanged), "unrelated body changed"
    assert sha(abc.bodies[coop][5]) == COOP_AFTER_SHA
    new_abc = abc.serialize()
    reread = ABC(new_abc)
    assert reread.serialize() == new_abc
    for i in changed:
        assert reread.bodies[i][5] == abc.bodies[i][5] and reread.bodies[i][1:5] == abc.bodies[i][1:5]
    content = prefix + new_abc
    new_tag = struct.pack("<HI", (82 << 6) | 63, len(content)) + content
    output_data = data[:offset] + new_tag + data[offset + size:]
    payload = zlib.compress(output_data) if signature == b"CWS" else output_data
    output = signature + bytes([version]) + struct.pack("<I", len(output_data) + 8) + payload
    report = {
        "capability": CAPABILITY, "status": "static_candidate_runtime_pending", "runtime_verified": False,
        "source_swf_sha256": sha(swf), "output_swf_sha256": sha(output),
        "source_abc_sha256": sha(raw), "output_abc_sha256": sha(new_abc),
        "bodies_total": len(abc.bodies), "bodies_changed": len(changed), "unchanged_main_body_count": len(unchanged),
        "constant_pool_appended": {"strings": [], "multinames": [], "ints": []},
        "coop_getDeferralLevel_preserved": {"body": coop, "sha256": COOP_AFTER_SHA},
        "methods": methods,
    }
    return output, report, original, abc, changed


def main():
    from common import read_base_swf
    output, report, old, new, changed = patch(read_base_swf())
    outdir = ROOT / "analysis" / "patch"
    outdir.mkdir(parents=True, exist_ok=True)
    labels = bodies.label_map(new)
    for i in changed:
        safe = labels[i].replace("/", "__")
        (outdir / f"{safe}.before.pcode.txt").write_text("\n".join(listing(old, old.bodies[i][5])) + "\n", encoding="utf8")
        (outdir / f"{safe}.after.pcode.txt").write_text("\n".join(listing(new, new.bodies[i][5])) + "\n", encoding="utf8")
    if len(sys.argv) > 1:
        (ROOT / sys.argv[1]).write_bytes(output)
    (outdir / "patch-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: report[k] for k in ("output_swf_sha256", "bodies_changed", "methods")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

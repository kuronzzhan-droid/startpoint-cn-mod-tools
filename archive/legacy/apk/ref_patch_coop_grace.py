"""Append two instructions in one existing ABC method; preserve all v28 content."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
import zipfile
import zlib
from pathlib import Path

from inspect_v28 import ROOT, ABC, asm, bodies, describe, iter_tags
from patch_local_endpoints import freeze
from swfabc import PoolEditor

LABEL = "BattleDerailleur/getDeferralLevel"
BODY_SHA = "e3ce66f068c4fa451c9083326119d3124e76df8065cc2e6ede7821be356f79bd"
BASES = {
    "9320277b7249fb4500f9cecf8f480f1a360ab6c514b6dbfab4747df45a696453": "original_v28",
    "6b0df742a54ebb5094b10d734616acefdb684e98086ad94831db637025627ed9": "local_replay_v28",
}
CAPABILITY = "coop-deferral-bounded-grace-1800-v1"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def listing(abc, code):
    lines, offset = [], 0
    for i, item in enumerate(asm.decode(code)):
        lines.append(f"#{i:04d} ofs{offset:04x}: {describe(abc, item)}")
        offset += item.size()
    return lines


def patch(swf):
    source_hash = sha(swf)
    if source_hash not in BASES:
        raise ValueError("refusing unknown or already modified SWF baseline")
    signature, version = swf[:3], swf[3]
    data = zlib.decompress(swf[8:]) if signature == b"CWS" else swf[8:]
    targets = []
    for kind, offset, header, length in iter_tags(data):
        if kind != 82:
            continue
        tag = data[offset + header:offset + header + length]
        nul = tag.index(b"\0", 4)
        if tag[4:nul] == b"boot_ffc6":
            targets.append((offset, header + length, tag[:nul + 1], tag[nul + 1:]))
    assert len(targets) == 1, "ambiguous main ABC"
    offset, size, prefix, raw = targets[0]
    abc = ABC(raw)
    assert abc.serialize() == raw, "main ABC roundtrip differs"
    original = copy.deepcopy(abc)
    index = bodies.resolve(abc, LABEL)
    body = abc.bodies[index]
    assert sha(body[5]) == BODY_SHA and body[1:5] == [2, 3, 1, 2] and body[6:] == [[], []], "method guard differs"
    code = asm.decode(body[5])
    assert code[15].name == "add_i" and code[16].name == "convert_i" and code[17].name == "setlocal_1", "insertion site differs"
    pool = PoolEditor(abc)
    block = asm.assemble([("pushint", pool.integer(1560)), ("subtract_i",)])
    old_code = body[5]
    body[5], body[6], merged = asm.splice(body, 16, block, asm.FORBID)
    assert asm.unsplice(body[5], 16, 2) == old_code, "inverse insertion differs"
    metrics = asm.simulate(merged, body[3], abc.multinames)
    assert metrics[:2] == (2, 2), "stack/scope header insufficient"
    assert asm.block_locals(merged) <= body[2], "local header insufficient"
    for field in ("uints", "doubles", "strings", "namespaces", "ns_sets", "multinames", "methods", "metadata", "instances", "classes", "scripts"):
        assert freeze(getattr(abc, field)) == freeze(getattr(original, field)), field
    assert abc.ints[:len(original.ints)] == original.ints
    unchanged = [i for i in range(len(abc.bodies)) if i != index]
    assert all(freeze(abc.bodies[i]) == freeze(original.bodies[i]) for i in unchanged), "unrelated body changed"
    new_abc = abc.serialize()
    reread = ABC(new_abc)
    assert reread.serialize() == new_abc and sha(reread.bodies[index][5]) == sha(body[5])
    content = prefix + new_abc
    new_tag = struct.pack("<HI", (82 << 6) | 63, len(content)) + content
    output_data = data[:offset] + new_tag + data[offset + size:]
    assert output_data[:offset] == data[:offset] and output_data[offset + len(new_tag):] == data[offset + size:]
    payload = zlib.compress(output_data) if signature == b"CWS" else output_data
    output = signature + bytes([version]) + struct.pack("<I", len(output_data) + 8) + payload
    report = {
        "status": "static_candidate_runtime_pending", "installed": False, "runtime_verified": False,
        "capability": [CAPABILITY], "baseline": BASES[source_hash],
        "source_swf_sha256": source_hash, "output_swf_sha256": sha(output),
        "source_abc_sha256": sha(raw), "output_abc_sha256": sha(new_abc),
        "bodies_total": len(abc.bodies), "bodies_changed": 1, "unchanged_main_body_count": len(unchanged),
        "constant_pool_appended": pool.report(),
        "methods": {LABEL: {"body": index, "method": body[0], "before": sha(old_code), "after": sha(body[5]), "inserted_at": [[16, 2, "forbid"]], "original_offset_hex": "002c", "original": ["convert_i", "setlocal1"], "new": ["pushint 1560", "subtract_i", "convert_i", "setlocal1"], "header_before": original.bodies[index][1:5], "header_after": body[1:5], "metrics": list(metrics), "inverse_bytewise_proof": True}},
        "constants": {"deferral_level8_before": 240, "deferral_level8_after": 1800, "grace_algorithm_units": 1560, "wall_clock_seconds_guaranteed": None},
        "preserved": ["all other main ABC bodies", "main ABC traits, methods and metadata", "all existing constant-pool values", "every other SWF tag including v28 helper ABCs", "no-socket-input timeout", "existing speed, stall and catch-up simulation"],
    }
    return output, report, original, abc, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-swf", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with zipfile.ZipFile(args.input) as archive:
        swf = archive.read("assets/worldflipper_android_release.swf")
    output, report, old, new, index = patch(swf)
    report["source_apk"] = str(args.input.resolve())
    report["source_apk_sha256"] = sha(args.input.read_bytes())
    for target in filter(None, (args.report, args.output_swf)):
        assert target.resolve().is_relative_to(ROOT.resolve()), "outputs must stay in ROOT"
        assert not target.exists(), "refusing existing output"
        target.parent.mkdir(parents=True, exist_ok=True)
    if args.output_swf:
        args.output_swf.write_bytes(output)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    before, after = listing(old, old.bodies[index][5]), listing(new, new.bodies[index][5])
    args.report.with_suffix(".before.pcode.txt").write_text("\n".join(before) + "\n", encoding="utf8")
    args.report.with_suffix(".after.pcode.txt").write_text("\n".join(after) + "\n", encoding="utf8")
    print(json.dumps({"status": report["status"], "baseline": report["baseline"], "bodies_changed": 1, "output_swf_written": bool(args.output_swf), "report": str(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

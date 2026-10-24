"""Method-body-only endpoint routing for a local v28 replay; no combat edits."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import struct
import zlib
from pathlib import Path

from inspect_v28 import ABC, asm, bodies, iter_tags
from abcfmt import R

OLD_HOST = os.environ.get("WF_LEGACY_APK_ORIGIN", "")
EXPECTED_SWF = "9320277b7249fb4500f9cecf8f480f1a360ab6c514b6dbfab4747df45a696453"
ALLOWED_TAGS = {b"boot_ffc6", b"cn/admission/ClientAdmission"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def freeze(value):
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if hasattr(value, "__slots__"):
        return tuple((name, freeze(getattr(value, name))) for name in value.__slots__)
    return value


def serialize_exact(abc, original):
    """Keep the original 0 spelling of empty numeric constant pools."""
    def counts(raw):
        reader = R(raw)
        reader.p = 4
        values = []
        for read in (reader.s32, reader.u32, reader.d64):
            at = reader.p
            count = reader.u30()
            values.append((at, count))
            for _ in range(max(0, count - 1)):
                read()
        return values
    output = bytearray(abc.serialize())
    for (_, old), (at, new) in zip(counts(original), counts(output)):
        if old == 0 and new == 1:
            output[at] = 0
    return bytes(output)


def patch_swf(swf, new_host):
    assert OLD_HOST, "set WF_LEGACY_APK_ORIGIN to the authorized baseline endpoint"
    assert sha(swf) == EXPECTED_SWF, "unknown baseline SWF"
    assert new_host in {os.environ.get("WF_LEGACY_APK_LAN_HOST"), "10.0.2.2:8001", "127.0.0.1:8001"}, "non-local replay target"
    signature, version = swf[:3], swf[3]
    assert signature in (b"FWS", b"CWS")
    data = zlib.decompress(swf[8:]) if signature == b"CWS" else swf[8:]
    changes, parts, cursor, total_preserved, instruction_changes = [], [], 0, 0, 0
    for kind, offset, header, length in iter_tags(data):
        if kind != 82:
            continue
        tag = data[offset + header:offset + header + length]
        nul = tag.index(b"\0", 4)
        name, raw = tag[4:nul], tag[nul + 1:]
        abc = ABC(raw)
        if name not in ALLOWED_TAGS:
            total_preserved += len(abc.bodies)
            continue  # Unmodified ABC tags are copied as raw bytes, not serialized.
        serialized = serialize_exact(abc, raw)
        assert serialized == raw, ("parser roundtrip differs", name.decode(), len(raw), len(serialized), [i for i, (a, b) in enumerate(zip(raw, serialized)) if a != b][:8])
        original = copy.deepcopy(abc)
        labels, changed = bodies.label_map(abc), []
        for index, body in enumerate(abc.bodies):
            decoded = asm.decode(body[5])
            original_bytes, old_offsets = asm.encode(decoded)
            assert original_bytes == body[5], "method roundtrip differs"
            replacements = []
            for position, instruction in enumerate(decoded):
                if instruction.name != "pushstring":
                    continue
                old = abc.s(instruction.args[0])
                if OLD_HOST not in old:
                    continue
                assert name in ALLOWED_TAGS, "unexpected active public endpoint tag"
                assert old == OLD_HOST or old.startswith("http://" + OLD_HOST), "unexpected endpoint structure"
                value = old.replace(OLD_HOST, new_host)
                new_index = len(abc.strings)
                abc.strings.append(value.encode("utf8"))
                instruction.args[0] = new_index
                replacements.append({"instruction": position, "original": ["pushstring", old], "new": ["pushstring", value]})
            if not replacements:
                continue
            body[5], new_offsets = asm.encode(decoded)
            old_offsets.append(len(original_bytes))
            new_offsets.append(len(body[5]))
            mapping = dict(zip(old_offsets, new_offsets))
            body[6] = [(mapping[start], mapping[stop], mapping[target], kind, variable) for start, stop, target, kind, variable in original.bodies[index][6]]
            assert body[1:5] == original.bodies[index][1:5]
            assert freeze(body[7]) == freeze(original.bodies[index][7])
            assert asm.encode(asm.decode(body[5]))[0] == body[5]
            changed.append(index)
            instruction_changes += len(replacements)
            changes.append({"tag": name.decode(), "method": labels.get(index, f"anonymous-body-{index}"), "body": index, "before": sha(original.bodies[index][5]), "after": sha(body[5]), "replacements": replacements})
        for attribute in ("ints", "uints", "doubles", "namespaces", "ns_sets", "multinames", "methods", "metadata", "instances", "classes", "scripts"):
            assert freeze(getattr(abc, attribute)) == freeze(getattr(original, attribute)), attribute
        assert abc.strings[:len(original.strings)] == original.strings
        assert all(freeze(body) == freeze(original.bodies[i]) for i, body in enumerate(abc.bodies) if i not in changed)
        total_preserved += len(abc.bodies) - len(changed)
        # BuildConfig constants are inlined by the compiler: no dynamic ORIGIN access is permitted.
        if name == b"cn/admission/ClientAdmission":
            for body in abc.bodies:
                for instruction in asm.decode(body[5]):
                    if instruction.name in {"getproperty", "getlex"}:
                        assert abc.mn_name(instruction.args[0]).split("::")[-1] != "ORIGIN", "dynamic public BuildConfig route"
        if changed:
            content = tag[:nul + 1] + serialize_exact(abc, raw)
            patched_tag = struct.pack("<HI", (82 << 6) | 63, len(content)) + content
            parts.extend((data[cursor:offset], patched_tag))
            cursor = offset + header + length
        for body in abc.bodies:
            for instruction in asm.decode(body[5]):
                assert instruction.name != "pushstring" or OLD_HOST not in abc.s(instruction.args[0]), "active public endpoint retained"
    assert instruction_changes == 8 and len(changes) == 7, (instruction_changes, len(changes))
    parts.append(data[cursor:])
    output = b"".join(parts)
    payload = zlib.compress(output) if signature == b"CWS" else output
    rebuilt = signature + bytes([version]) + struct.pack("<I", len(output) + 8) + payload
    report = {"scope": "local_replay_endpoint_only", "base_swf_sha256": sha(swf), "output_swf_sha256": sha(rebuilt), "api_origin": "http://" + new_host, "methods": changes, "unchanged_method_bodies": total_preserved, "instruction_changes": instruction_changes, "combat_methods_changed": 0, "pool_policy": "append only; old endpoint strings and unused BuildConfig const remain immutable"}
    return rebuilt, report

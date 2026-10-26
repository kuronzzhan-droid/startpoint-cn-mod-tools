"""perf-v30 round 2: replayable method-level patch framework.

Every patch names (DoABC2 tag, method label, original code sha256, patched code sha256). `apply_patches`:
  * original sha  -> splice, then require the result to equal the recorded patched sha (deterministic);
  * patched sha   -> already present, left untouched (lets the set be re-applied / stacked);
  * anything else -> refuse the whole SWF (nothing is written).
Only the touched DoABC2 tags are re-serialized; every other tag is copied byte-identical. Main-ABC patches never
append to the constant pool; helper-ABC patches may append (find-or-append, deterministic) to that helper's own pool.
"""
from __future__ import annotations

import copy
import struct
import zlib

from .common import ABC, abc_tags, asm, bodies, freeze, sha, swf_data

MAIN = b"boot_ffc6"


class Refused(RuntimeError):
    pass


class Pool:
    """Find-or-append editor for one ABC (strings, namespaces-by-existing-index, multinames)."""

    def __init__(self, abc, allow_append):
        self.abc, self.allow_append, self.added = abc, allow_append, []

    def _append(self, table, value, what):
        if not self.allow_append:
            raise Refused(f"constant-pool append refused in this ABC: {what}")
        table.append(value)
        self.added.append(what)
        return len(table) - 1

    def string(self, text):
        raw = text.encode()
        for i in range(1, len(self.abc.strings)):
            if self.abc.strings[i] == raw:
                return i
        return self._append(self.abc.strings, raw, f"string {text!r}")

    def multiname_nsset(self, name, nsset):
        s = self.string(name)
        for i in range(1, len(self.abc.multinames)):
            if self.abc.multinames[i] == (0x09, s, nsset):
                return i
        return self._append(self.abc.multinames, (0x09, s, nsset), f"multiname {name}@nsset{nsset}")

    def qname(self, name, ns):
        s = self.string(name)
        for i in range(1, len(self.abc.multinames)):
            if self.abc.multinames[i] == (0x07, ns, s):
                return i
        return self._append(self.abc.multinames, (0x07, ns, s), f"qname {self.abc.ns_name(ns)}::{name}")

    def find(self, text, kind=None):
        """Existing multiname whose printable name is `text` (unique), no append."""
        hits = [i for i in range(1, len(self.abc.multinames))
                if self.abc.mn_name(i) == text and (kind is None or self.abc.multinames[i][0] == kind)]
        if not hits:
            raise Refused(f"multiname {text!r} not in pool")
        return hits[0]


def mn_at(abc, body, position, opname, expect):
    ins = asm.decode(body[5])[position]
    if ins.name != opname or abc.mn_name(ins.args[0]) != expect:
        raise Refused(f"donor mismatch at #{position}: {ins.name} {abc.mn_name(ins.args[0])} != {opname} {expect}")
    return ins.args[0]


def check_body(abc, body, initial_scope=None):
    """Stack/scope simulation (incl. exception handlers) must fit the header; locals must fit localcount."""
    code = asm.decode(body[5])
    _enc, offsets = asm.encode(code)
    index_of = {o: i for i, o in enumerate(offsets)}
    handlers = [index_of[e[2]] for e in body[6]]
    ms, sc, unreachable = asm.simulate(code, body[3] if initial_scope is None else initial_scope, abc.multinames, handlers)
    if ms > body[1] or sc > body[4]:
        raise Refused(f"stack/scope {ms}/{sc} exceed header {body[1]}/{body[4]}")
    if asm.block_locals(code) > body[2]:
        raise Refused("locals exceed localcount")
    return {"max_stack": ms, "max_scope": sc, "unreachable": unreachable, "header": list(body[1:5])}


def splice_with_exits(body, at, block_src, exits, incoming=asm.FORBID):
    """Insert `block_src` at original instruction `at`; branches whose label is in `exits` (label -> ORIGINAL
    instruction index) are re-targeted to that original instruction after the splice. Returns (code, exc, merged)."""
    placeholder = {name: f"__exit_{name}" for name in exits}
    src, fixups = [], []
    for entry in block_src:
        if entry[0] != "label" and len(entry) == 2 and entry[0] in asm.MNEMONICS and \
                asm.MNEMONICS[entry[0]] in asm.BRANCHES and entry[1] in exits:
            fixups.append((len([e for e in src if e[0] != "label"]), entry[1]))
            src.append((entry[0], "END"))
        else:
            src.append(entry)
    block = asm.assemble(src)
    code, exc, merged = asm.splice(body, at, block, incoming)
    n = len(block)
    for local_index, name in fixups:
        original = exits[name]
        merged[at + local_index].target = original + n if original >= at else original
    code2, _ = asm.encode(merged)
    if exc:
        # re-map exception offsets for the re-encoded code (branch sizes are fixed, so offsets are unchanged)
        assert code2.__len__() == code.__len__()
    return code2, exc, asm.decode(code2), n


def parse_swf(swf):
    data = swf_data(swf)
    tags, dup = {}, set()
    for name, offset, size, prefix, raw in abc_tags(swf):
        if name in tags:
            dup.add(name)
        tags[name] = {"offset": offset, "size": size, "prefix": prefix, "raw": raw}
    for name in dup:
        tags[name] = None  # ambiguous name: never patchable
    return data, tags


def rebuild_swf(swf, data, tags, changed):
    pieces, cursor = [], 0
    for name in sorted(changed, key=lambda n: tags[n]["offset"]):
        t = tags[name]
        content = t["prefix"] + changed[name].serialize()
        pieces.append(data[cursor:t["offset"]])
        pieces.append(struct.pack("<HI", (82 << 6) | 63, len(content)) + content)
        cursor = t["offset"] + t["size"]
    pieces.append(data[cursor:])
    out = b"".join(pieces)
    payload = zlib.compress(out) if swf[:3] == b"CWS" else out
    return swf[:3] + bytes([swf[3]]) + struct.pack("<I", len(out) + 8) + payload


def apply_patches(swf, patches, select=None):
    """Returns (output_swf, report). Raises Refused without producing output on any mismatch."""
    data, tags = parse_swf(swf)
    abcs, originals, results, touched = {}, {}, [], {}
    for p in patches:
        if select is not None and p["id"] not in select:
            continue
        tag = p["tag"]
        if tags.get(tag) is None:
            raise Refused(f"{p['id']}: DoABC2 tag {tag!r} missing or not unique")
        if tag not in abcs:
            abc = ABC(tags[tag]["raw"])
            if abc.serialize() != tags[tag]["raw"]:
                raise Refused(f"{tag!r}: ABC roundtrip differs")
            abcs[tag], originals[tag] = abc, copy.deepcopy(abc)
        abc = abcs[tag]
        index = bodies.resolve(abc, p["label"])
        body = abc.bodies[index]
        now = sha(body[5])
        if now == p["after"]:
            results.append({"id": p["id"], "label": p["label"], "status": "already_present", "sha": now})
            continue
        if now != p["before"]:
            raise Refused(f"{p['id']} {p['label']}: body sha {now} matches neither original nor patched")
        for guard_label, guard_sha in p.get("guards", {}).items():
            gi = bodies.resolve(abc, guard_label)
            if sha(abc.bodies[gi][5]) != guard_sha:
                raise Refused(f"{p['id']}: guard {guard_label} sha differs")
        pool = Pool(abc, allow_append=(tag != MAIN))
        before_body = copy.deepcopy(body)
        meta = p["apply"](abc, index, pool) or {}
        after = sha(abc.bodies[index][5])
        if p["after"] is not None and after != p["after"]:
            raise Refused(f"{p['id']}: produced sha {after} != recorded {p['after']}")
        meta.update(check_body(abc, abc.bodies[index]))
        meta.update({"id": p["id"], "label": p["label"], "tag": tag.decode(), "body": index, "status": "applied",
                     "before": now, "after": after, "header_before": list(before_body[1:5]),
                     "pool_added": pool.added, "before_len": len(before_body[5]), "after_len": len(abc.bodies[index][5])})
        results.append(meta)
        touched.setdefault(tag, set()).add(index)
    # global invariants per touched ABC: only the touched bodies differ; non-pool tables identical
    for tag, idx in touched.items():
        abc, orig = abcs[tag], originals[tag]
        for field in ("namespaces", "ns_sets", "methods", "metadata", "instances", "classes", "scripts", "ints",
                      "uints", "doubles"):
            if freeze(getattr(abc, field)) != freeze(getattr(orig, field)):
                raise Refused(f"{tag!r}: table {field} changed")
        for field in ("strings", "multinames"):
            a, o = getattr(abc, field), getattr(orig, field)
            if a[:len(o)] != o or (tag == MAIN and len(a) != len(o)):
                raise Refused(f"{tag!r}: pool {field} not append-only")
        if len(abc.bodies) != len(orig.bodies):
            raise Refused("body count changed")
        for i in range(len(abc.bodies)):
            if i not in idx and freeze(abc.bodies[i]) != freeze(orig.bodies[i]):
                raise Refused(f"{tag!r}: unrelated body {i} changed")
        reread = ABC(abc.serialize())
        if reread.serialize() != abc.serialize():
            raise Refused("re-read differs")
    changed = {tag: abcs[tag] for tag in touched}
    out = rebuild_swf(swf, data, tags, changed) if changed else swf
    return out, {"source_swf_sha256": sha(swf), "output_swf_sha256": sha(out), "patches": results,
                 "tags_changed": [t.decode() for t in changed]}

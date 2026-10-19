"""Read actual method code and its referenced constants; never infer from versions."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import struct
import zlib

from . import asm
from .bodies import label_map
from .common import ABC, abc_tags


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def labels(abc):
    """Support the short, qualified, script and anonymous archive label forms."""
    result = defaultdict(set)
    bodies = {body[0]: index for index, body in enumerate(abc.bodies)}
    for index, label in label_map(abc).items():
        result[label].add(index)

    def put(method, label):
        if method in bodies:
            result[label].add(bodies[method])

    for position, instance in enumerate(abc.instances):
        name = abc.mn_name(instance[0])
        put(instance[5], name + "/<ctor>")
        klass = abc.classes[position]
        put(klass[0], name + "$/<cinit>")
        for static, traits in ((False, instance[6]), (True, klass[1])):
            for trait in traits:
                if trait.data[0] == "method":
                    put(trait.data[2], name + ("$/" if static else "/")
                        + abc.mn_name(trait.name) + "|" + str(trait.kind))
    for init, traits in abc.scripts:
        names = [abc.mn_name(t.name) for t in traits if t.kind == 4]
        for name in names:
            put(init, "script:" + name + "/<init>")
    for index, body in enumerate(abc.bodies):
        put(body[0], "anonymous-method-" + str(body[0]))
    return result


def resolve_label(abc, mapping, label):
    if "/closure:" not in label:
        return mapping.get(label, set())
    parent, number = label.rsplit("/closure:", 1)
    indices = resolve_label(abc, mapping, parent)
    if len(indices) != 1 or not number.isdecimal():
        return set()
    body = abc.bodies[next(iter(indices))]
    closures = [ins.args[0] for ins in asm.decode(body[5]) if ins.op == 0x40]
    if int(number) >= len(closures):
        return set()
    return {i for i, candidate in enumerate(abc.bodies) if candidate[0] == closures[int(number)]}


class Context:
    def __init__(self, abc):
        self.abc = abc
        self.by_method = {body[0]: body for body in abc.bodies}

    def namespace(self, index):
        kind, name = self.abc.namespaces[index]
        return [kind, self.abc.strings[name].hex(), index if kind == 5 else None]

    def multiname(self, index):
        value = self.abc.multinames[index]
        kind = value[0]
        if kind in (7, 13):
            return [kind, self.namespace(value[1]), self.abc.strings[value[2]].hex()]
        if kind in (9, 14):
            return [kind, self.abc.strings[value[1]].hex(),
                    [self.namespace(n) for n in self.abc.ns_sets[value[2]]]]
        if kind in (15, 16):
            return [kind, self.abc.strings[value[1]].hex()]
        if kind in (27, 28):
            return [kind, [self.namespace(n) for n in self.abc.ns_sets[value[1]]]]
        if kind == 29:
            return [kind, self.multiname(value[1]), [self.multiname(n) for n in value[2]]]
        return list(value)

    def constant(self, index, kind):
        if kind == 1:
            return self.abc.strings[index].hex()
        if kind in (3, 4, 6):
            value = {3: self.abc.ints, 4: self.abc.uints, 6: self.abc.doubles}[kind][index]
            return struct.pack("<d", value).hex() if kind == 6 else value
        if kind in (5, 8, 22, 23, 24, 25, 26):
            return self.namespace(index)
        return [kind, index]

    def signature(self, index):
        ret, parameters, name, flags, options, names = self.abc.methods[index]
        return [self.multiname(ret), [self.multiname(n) for n in parameters],
                self.abc.strings[name].hex(), flags,
                [[kind, self.constant(n, kind)] for n, kind in options or []],
                [self.abc.strings[n].hex() for n in names or []]]

    def traits(self, traits, *, declaration=False):
        rows = []
        for trait in traits:
            data = trait.data
            if data[0] == "slot":
                value = [data[1], self.multiname(data[2]),
                         self.constant(data[3], data[4]) if data[3] else None]
            elif declaration and data[0] in {"method", "function"}:
                value = [*data, self.signature(data[2])]
            elif declaration and data[0] == "class":
                value = [*data, self.multiname(self.abc.instances[data[2]][0])]
            else:
                raise ValueError("method context decoder only accepts slot/const activation traits")
            metadata = [[self.abc.strings[self.abc.metadata[i][0]].hex(),
                         [[self.abc.strings[k].hex(), self.abc.strings[v].hex()]
                          for k, v in self.abc.metadata[i][1]]] for i in trait.metadata]
            rows.append([self.multiname(trait.name), trait.kind, trait.attr,
                         value, metadata])
        return rows

    def class_declaration(self, index):
        instance, klass = self.abc.instances[index], self.abc.classes[index]
        return [self.multiname(instance[0]), self.multiname(instance[1]), instance[2],
                self.namespace(instance[3]) if instance[3] is not None else None,
                [self.multiname(n) for n in instance[4]], instance[5], self.signature(instance[5]),
                self.traits(instance[6], declaration=True), klass[0], self.signature(klass[0]),
                self.traits(klass[1], declaration=True)]

    def method(self, body, active=()):
        if body[0] in active:
            return fingerprint(["recursive-method", body[0]])
        active = (*active, body[0])
        refs = []
        multinames = {0x04, 0x05, 0x45, 0x46, 0x4A, 0x4C, 0x4E, 0x4F,
                      0x59, 0x5D, 0x5E, 0x5F, 0x60, 0x61, 0x66, 0x68, 0x6A,
                      0x80, 0x86, 0xB2}
        for ins in asm.decode(body[5]):
            if ins.op not in asm.BY_OPCODE and ins.op not in {
                    0x04, 0x05, 0x06, 0x07, 0x08, 0x35, 0x36, 0x37, 0x38,
                    0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x50, 0x51, 0x52,
                    0x67, 0x6B, 0x6E, 0x6F, 0x81, 0x83, 0x84, 0x88, 0x89,
                    0xEF, 0xF0, 0xF1, 0xF2}:
                raise ValueError("method context decoder does not support opcode " + hex(ins.op))
            if ins.op in multinames:
                refs.append([ins.op, ins.args[0], self.multiname(ins.args[0])])
            elif ins.op in {0x2C, 0x2D, 0x2E, 0x2F, 0x31}:
                kind = {0x2C: 1, 0x2D: 3, 0x2E: 4, 0x2F: 6, 0x31: 8}[ins.op]
                refs.append([ins.op, ins.args[0], self.constant(ins.args[0], kind)])
            elif ins.op in {0x40, 0x44}:
                target = ins.args[0]
                target_body = self.by_method.get(target)
                refs.append([ins.op, target, self.signature(target),
                             self.method(target_body, active) if target_body else None])
            elif ins.op == 0x58:
                refs.append([ins.op, ins.args[0], self.class_declaration(ins.args[0])])
            elif ins.op in {0x06, 0xF1}:
                refs.append([ins.op, ins.args[0], self.abc.strings[ins.args[0]].hex()])
            elif ins.op == 0xEF:
                refs.append([ins.op, ins.args[1], self.abc.strings[ins.args[1]].hex()])
        exceptions = [[*row[:3], self.multiname(row[3]), self.multiname(row[4])]
                      for row in body[6]]
        return fingerprint([body[5].hex(), body[1:5], exceptions,
                            self.traits(body[7]), self.signature(body[0]), refs])


def snapshot(swf, requested):
    """Return one observation per requested (ABC, label), refusing ambiguity."""
    if len(swf) < 8 or swf[:3] not in {b"FWS", b"CWS"}:
        raise ValueError("expected an FWS or CWS SWF")
    decoded = zlib.decompress(swf[8:]) if swf[:3] == b"CWS" else swf[8:]
    if struct.unpack_from("<I", swf, 4)[0] != len(decoded) + 8:
        raise ValueError("SWF declared length differs")
    tags = defaultdict(list)
    for name, _, _, _, raw in abc_tags(swf):
        tags[name.decode("utf-8")].append(raw)
    result = {}
    grouped = defaultdict(set)
    for name, label in requested:
        grouped[name].add(label)
    for name, names in grouped.items():
        if len(tags[name]) != 1:
            for label in names:
                result[(name, label)] = {"error": "missing or ambiguous ABC"}
            continue
        abc = ABC(tags[name][0])
        mapping, context = labels(abc), Context(abc)
        for label in names:
            indices = resolve_label(abc, mapping, label)
            if len(indices) != 1:
                result[(name, label)] = {"error": "missing or ambiguous method"}
                continue
            body = abc.bodies[next(iter(indices))]
            result[(name, label)] = {"sha256": hashlib.sha256(body[5]).hexdigest(),
                                     "context_sha256": context.method(body)}
    return result

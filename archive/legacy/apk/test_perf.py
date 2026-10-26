"""Offline self-tests for perf-v30 patches: readback, instruction-sequence, stack/locals, and execution of the
REAL original vs patched getIndex bytecode in a minimal AVM2 interpreter against emulated master tables."""
from __future__ import annotations

import json
import random

from common import ABC, ROOT, abc_tags, asm, bodies, freeze, main_abc, read_base_swf, sha
from patch_perf import COOP_AFTER_SHA, COOP_LABEL, patch


class Undefined:
    def __repr__(self):
        return "undefined"


UNDEF = Undefined()


class Thrown(Exception):
    pass


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Dictionary(dict):
    """AS3 Dictionary emulation: identity of primitive keys by (type-class, value), like `===` on keys."""

    @staticmethod
    def norm(key):
        if isinstance(key, bool):
            return ("b", key)
        if isinstance(key, (int, float)):
            return ("n", float(key))
        if isinstance(key, str):
            return ("s", key)
        return ("o", id(key))

    def get_(self, key):
        return self.get(self.norm(key), UNDEF)

    def set_(self, key, value):
        self[self.norm(key)] = value


def strict_eq(a, b):
    if a is UNDEF or b is UNDEF:
        return a is b
    if a is None or b is None:
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return float(a) == float(b)
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    return a is b


def to_int(v):
    if v is UNDEF or v is None:
        return 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        if v != v or v in (float("inf"), float("-inf")):
            return 0
        x = int(v) & 0xFFFFFFFF
        return x - (1 << 32) if x & 0x80000000 else x
    if isinstance(v, str):
        try:
            return to_int(float(v))
        except ValueError:
            return 0
    return 0


def run(abc, body, this, key, stats):
    code = asm.decode(body[5])
    loc = [this, key] + [UNDEF] * (body[2] - 2)
    stack, pc, steps = [], 0, 0
    while True:
        steps += 1
        assert steps < 5_000_000
        ins = code[pc]
        pc += 1
        n = ins.name
        if n == "getlocal_0":
            stack.append(loc[0])
        elif n == "getlocal_1":
            stack.append(loc[1])
        elif n == "getlocal_2":
            stack.append(loc[2])
        elif n == "getlocal_3":
            stack.append(loc[3])
        elif n == "getlocal":
            stack.append(loc[ins.args[0]])
        elif n.startswith("setlocal"):
            loc[int(n[-1]) if n != "setlocal" else ins.args[0]] = stack.pop()
        elif n == "pushscope":
            stack.pop()
        elif n in ("avm_label",):
            pass
        elif n in ("pushnull",):
            stack.append(None)
        elif n == "pushundefined":
            stack.append(UNDEF)
        elif n == "pushbyte":
            v = ins.args[0]
            stack.append(v - 256 if v > 127 else v)
        elif n == "pushstring":
            stack.append(abc.s(ins.args[0]))
        elif n == "pushint":
            stack.append(abc.ints[ins.args[0]])
        elif n in ("coerce", "coerce_a", "astype"):
            pass
        elif n == "convert_i":
            stack.append(to_int(stack.pop()))
        elif n == "findproperty":
            stack.append(this)
        elif n == "findpropstrict":
            name = abc.mn_name(ins.args[0])
            assert name == "flash.utils::Dictionary", name
            stack.append("DictionaryClass")
        elif n == "constructprop":
            name = abc.mn_name(ins.args[0])
            assert name == "flash.utils::Dictionary" and ins.args[1] == 0
            assert stack.pop() == "DictionaryClass"
            stats["dict_builds"] += 1
            stack.append(Dictionary())
        elif n == "getproperty":
            mn = abc.multinames[ins.args[0]]
            if mn[0] == 0x1B:
                name = stack.pop()
                obj = stack.pop()
                if isinstance(obj, Dictionary):
                    stack.append(obj.get_(name))
                elif isinstance(obj, list):
                    i = name if isinstance(name, int) else None
                    stack.append(obj[i] if i is not None and 0 <= i < len(obj) else UNDEF)
                else:
                    raise AssertionError("MNL on " + repr(type(obj)))
            else:
                obj = stack.pop()
                name = abc.mn_name(ins.args[0])
                if name == "length":
                    stack.append(len(obj))
                else:
                    stack.append(getattr(obj, name))
        elif n == "setproperty":
            mn = abc.multinames[ins.args[0]]
            assert mn[0] == 0x1B
            value, name, obj = stack.pop(), stack.pop(), stack.pop()
            assert isinstance(obj, Dictionary)
            if obj is not this.cache.h:
                stats["dict_sets"] += 1
            obj.set_(name, value)
        elif n == "callproperty":
            name = abc.mn_name(ins.args[0])
            argc = ins.args[1]
            args = [stack.pop() for _ in range(argc)][::-1]
            obj = stack.pop()
            assert name.endswith("::indexOf") and isinstance(obj, list), name
            needle, start = args[0], to_int(args[1])
            stats["indexof_calls"] += 1
            found = -1
            for i in range(max(0, start), len(obj)):
                stats["indexof_compares"] += 1
                if strict_eq(obj[i], needle):
                    found = i
                    break
            stack.append(found)
        elif n == "getlex":
            raise Thrown(8601)
        elif n == "iftrue":
            v = stack.pop()
            if v not in (UNDEF, None, False, 0, "") and v == v:
                pc = ins.target
        elif n == "jump":
            pc = ins.target
        elif n == "declocal_i":
            loc[ins.args[0]] = to_int(loc[ins.args[0]]) - 1
        elif n in ("ifgt", "ifnlt", "ifstrictne", "ifstricteq"):
            b, a = stack.pop(), stack.pop()
            if n == "ifgt":
                take = a > b
            elif n == "ifnlt":
                take = not (a < b)
            elif n == "ifstricteq":
                take = strict_eq(a, b)
            else:
                take = not strict_eq(a, b)
            if take:
                pc = ins.target
        elif n == "returnvalue":
            assert len(stack) == 1, stack
            return stack.pop()
        else:
            raise AssertionError("unsupported instruction " + n)


def make_table(keys):
    cache = Obj(h=Dictionary())
    return Obj(map=Obj(_keys=list(keys), extraInfo="t.bin"), cache=cache)


def call(abc, body, table, key):
    stats = {"dict_builds": 0, "dict_sets": 0, "indexof_calls": 0, "indexof_compares": 0}
    try:
        return run(abc, body, table, key, stats), stats
    except Thrown as error:
        return ("throw", error.args[0]), stats


def expected(keys, key):
    for i, k in enumerate(keys):
        if strict_eq(k, key):
            return i
    return ("throw", 8601)


def main():
    rnd = random.Random(20261015)
    base = read_base_swf()
    output, report, old, new, changed = patch(base)
    (i,) = changed
    ob, nb = old.bodies[i], new.bodies[i]
    assertions = 0
    # 1. readback of the produced SWF: main ABC parses, roundtrips, only this body differs, coop body intact
    new_abc, _ = main_abc(output)
    assert new_abc.serialize() == [t for t in abc_tags(output) if t[0] == b"boot_ffc6"][0][4]
    assert len(new_abc.bodies) == len(old.bodies)
    diff = [k for k in range(len(old.bodies)) if freeze(old.bodies[k]) != freeze(new_abc.bodies[k])]
    assert diff == [i], diff
    assert sha(new_abc.bodies[bodies.resolve(new_abc, COOP_LABEL)][5]) == COOP_AFTER_SHA
    assert bodies.label_map(new_abc)[i] == "MasterBinaryMap/getIndex"
    other_tags_old = [t for t in abc_tags(base) if t[0] != b"boot_ffc6"]
    other_tags_new = [t for t in abc_tags(output) if t[0] != b"boot_ffc6"]
    assert [(t[0], t[4]) for t in other_tags_old] == [(t[0], t[4]) for t in other_tags_new]
    assertions += 5
    # 2. instruction sequence: prefix kept, 62-instruction block, then the original body byte-identical
    oc, nc = asm.decode(ob[5]), asm.decode(nb[5])
    BL = report["methods"]["MasterBinaryMap/getIndex"]["block_len"]
    assert BL == len(nc) - len(oc) == 62
    assert [x.name for x in nc[:2]] == ["getlocal_0", "pushscope"]
    names = [x.name for x in nc[2:2+BL]]
    assert names[:8] == ["getlocal_0", "getproperty", "getproperty", "pushbyte", "getproperty", "setlocal", "getlocal", "iftrue"]
    assert names.count("constructprop") == 1 and names.count("declocal_i") == 1 and names.count("ifstrictne") == 1
    assert [x.name for x in nc[2+BL:]] == [x.name for x in oc[2:]]
    assert [x.args for x in nc[2+BL:]] == [x.args for x in oc[2:]]
    assert asm.unsplice(nb[5], 2, BL) == ob[5]
    assert nb[6] == ob[6] == [] and nb[7] == ob[7] == []
    assert nb[1:5] == [5, 10, 1, 2] and ob[1:5] == [5, 6, 1, 2]
    for x in nc[2:2+BL]:
        if x.name in ("getproperty", "setproperty", "findpropstrict", "constructprop"):
            assert x.args[0] < len(old.multinames)
    assertions += 9
    # 3. stack/scope/local balance on both bodies; new body's demand fits the header
    for body in (ob, nb):
        ms, sc, unreachable = asm.simulate(asm.decode(body[5]), body[3], new.multinames)
        assert ms <= body[1] and sc <= body[4] and unreachable == 0, (ms, sc, unreachable)
        assert asm.block_locals(asm.decode(body[5])) <= body[2]
        assertions += 2
    # 4. execution equivalence on emulated tables (real bytecode of both versions)
    cases = 0
    for size in (0, 1, 2, 3, 17, 64, 300, 1500):
        for kind in ("int", "str", "enum", "sparse"):
            if kind == "int":
                keys = list(range(1, size + 1))
            elif kind == "sparse":
                keys = rnd.sample(range(1, 10 * size + 10), size)
            elif kind == "str":
                keys = [f"k{n}" for n in rnd.sample(range(size * 3 + 3), size)]
            else:
                keys = [Obj(tag=n) for n in range(size)]
            t_old, t_new = make_table(keys), make_table(keys)
            probes = list(keys) + ([0, -1, "nope", Obj(tag=-1), UNDEF, None] if kind != "enum" else [Obj(tag=0), UNDEF, None])
            rnd.shuffle(probes)
            for key in probes * 2:
                a, sa = call(old, ob, t_old, key)
                b, sb = call(new, nb, t_new, key)
                assert a == b == expected(t_old.map._keys, key), (kind, size, key, a, b)
                cases += 1
            # mutation after the index exists: append, in-place reverse sort, removal
            for mutate in ("append", "reverse", "remove"):
                extra = Obj(tag=99999) if kind == "enum" else (f"k{10**6}" if kind == "str" else 10**6)
                for t in (t_old, t_new):
                    ks = t.map._keys
                    if mutate == "append":
                        ks.append(extra)
                    elif mutate == "reverse":
                        ks.reverse()
                    elif ks:
                        ks.pop(len(ks) // 2)
                for key in list(t_old.map._keys)[:40] + list(keys)[:40]:
                    a, _ = call(old, ob, t_old, key)
                    b, _ = call(new, nb, t_new, key)
                    assert a == b == expected(t_old.map._keys, key), (mutate, kind, size, a, b)
                    cases += 1
    # duplicate keys (not expected in master data): first occurrence must still win
    dup = [5, 7, 5, 9, 7]
    t = make_table(dup)
    for key in (5, 7, 9, 6):
        assert call(new, nb, t, key)[0] == call(old, ob, make_table(dup), key)[0] == expected(dup, key)
        cases += 1
    assertions += cases
    # 5. complexity: N lookups over an N-row table
    n = 2000
    keys = list(range(100, 100 + n))
    t_old, t_new = make_table(keys), make_table(keys)
    tot_old = {"indexof_compares": 0, "dict_builds": 0}
    tot_new = {"indexof_compares": 0, "dict_builds": 0, "dict_sets": 0}
    for key in keys:
        _, s = call(old, ob, t_old, key)
        tot_old["indexof_compares"] += s["indexof_compares"]
        _, s = call(new, nb, t_new, key)
        for k in tot_new:
            tot_new[k] += s[k]
    assert tot_old["indexof_compares"] == n * (n + 1) // 2
    assert tot_new["indexof_compares"] == 0 and tot_new["dict_builds"] == 1 and tot_new["dict_sets"] == n
    assertions += 3
    # 6. refuse already-patched input / unknown SWF
    try:
        patch(output)
        raise AssertionError("patched SWF accepted twice")
    except AssertionError as error:
        assert "refusing" in str(error)
        assertions += 1
    result = {
        "passed": True, "assertions": assertions, "execution_cases": cases, "real_bytecode_executed": True,
        "patched_method": "MasterBinaryMap/getIndex", "body": i,
        "complexity_probe": {"rows": n, "lookups": n, "original_indexOf_compares": tot_old["indexof_compares"],
                              "patched_indexOf_compares": tot_new["indexof_compares"], "patched_dictionary_builds": tot_new["dict_builds"],
                              "patched_dictionary_inserts": tot_new["dict_sets"]},
        "stack": {"original": list(asm.simulate(asm.decode(ob[5]), ob[3], new.multinames)), "patched": list(asm.simulate(asm.decode(nb[5]), nb[3], new.multinames)),
                  "header_before": ob[1:5], "header_after": nb[1:5]},
        "output_swf_sha256": report["output_swf_sha256"], "runtime_verified": False,
        "note": "Interpreter emulates Array/Dictionary/=== semantics needed by this body; AIR JIT behaviour itself is not verified.",
    }
    out = ROOT / "analysis" / "test-perf-results.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

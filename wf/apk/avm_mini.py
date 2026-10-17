"""Minimal AVM2 interpreter for offline equivalence tests of the round-2 patches.

It executes the REAL method bodies decoded from the SWF. Objects are Python stand-ins supplied by each test through
an `Env` (name lookup for getlex/findprop*, property get/set, method calls, construction). Only the instructions the
patched bodies use are implemented; anything else raises, so a test can never silently skip semantics.
"""
from __future__ import annotations

import math

from .common import asm


class Undefined:
    def __repr__(self):
        return "undefined"


UNDEF = Undefined()


class Thrown(Exception):
    pass


class Dictionary(dict):
    """AS3 Dictionary/Object-as-map: primitive keys by value (numbers unified), objects by identity."""

    @staticmethod
    def norm(key):
        if isinstance(key, bool):
            return ("b", key)
        if isinstance(key, (int, float)):
            return ("n", float(key))
        if isinstance(key, str):
            return ("s", key)
        if key is None or key is UNDEF:
            return ("z", repr(key))
        return ("o", id(key))

    def get_(self, key):
        return self.get(self.norm(key), (None, UNDEF))[1]

    def set_(self, key, value):
        self[self.norm(key)] = (key, value)


class PlainObject(Dictionary):
    """newobject result: string keys (AS3 converts keys of a plain Object to strings)."""

    @staticmethod
    def norm(key):
        return ("s", to_str(key))


def to_number(v):
    if v is UNDEF:
        return float("nan")
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip(" \t\n\r\x0b\x0c")
        if s == "":
            return 0.0
        try:
            if s.lower().startswith(("0x", "+0x", "-0x")):
                sign = -1 if s.startswith("-") else 1
                return sign * float(int(s.lstrip("+-")[2:], 16))
            if s.lower() in ("infinity", "+infinity"):
                return float("inf")
            if s.lower() == "-infinity":
                return float("-inf")
            if any(c.isalpha() and c.lower() != "e" for c in s) or "_" in s:
                return float("nan")
            return float(s)
        except ValueError:
            return float("nan")
    return float("nan")


def to_int(v):
    n = to_number(v)
    if n != n or n in (float("inf"), float("-inf")):
        return 0
    x = int(math.trunc(n)) & 0xFFFFFFFF
    return x - (1 << 32) if x & 0x80000000 else x


def to_str(v):
    if v is UNDEF:
        return "undefined"
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v:
            return "NaN"
        if v == int(v) and abs(v) < 1e21:
            return str(int(v))
        return repr(v)
    if isinstance(v, str):
        return v
    if hasattr(v, "as3_string"):
        return v.as3_string()
    return "[object]"


def truthy(v):
    if v is UNDEF or v is None or v is False:
        return False
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v == v and v != 0
    if isinstance(v, str):
        return v != ""
    return True


def strict_eq(a, b):
    if a is UNDEF or b is UNDEF or a is None or b is None:
        return a is b
    na = isinstance(a, (int, float)) and not isinstance(a, bool)
    nb = isinstance(b, (int, float)) and not isinstance(b, bool)
    if na and nb:
        return float(a) == float(b)
    if na or nb:
        return False
    if isinstance(a, str) or isinstance(b, str):
        return isinstance(a, str) and isinstance(b, str) and a == b
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    return a is b


def loose_eq(a, b):
    if (a is None or a is UNDEF) and (b is None or b is UNDEF):
        return True
    if a is None or a is UNDEF or b is None or b is UNDEF:
        return False
    if isinstance(a, (int, float, bool)) or isinstance(b, (int, float, bool)):
        if isinstance(a, str) or isinstance(b, str) or (isinstance(a, (int, float, bool)) and isinstance(b, (int, float, bool))):
            return to_number(a) == to_number(b)
    return strict_eq(a, b)


def add(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return to_str(a) + to_str(b)
    r = to_number(a) + to_number(b)
    return int(r) if r == int(r) and abs(r) < 2 ** 53 and isinstance(a, int) and isinstance(b, int) else r


class Env:
    """Override in tests. `abc` is used to print names; dispatch is by printable name."""

    def __init__(self, abc):
        self.abc = abc
        self.counts = {}

    def bump(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1

    # name resolution
    def lex(self, name):
        raise AssertionError("getlex/findprop " + name)

    def findprop(self, name, this):
        return self.lex(name)

    def get(self, obj, name):
        if name == "length" and isinstance(obj, (list, str)):
            return len(obj)
        if isinstance(obj, PlainObject) or isinstance(obj, Dictionary):
            return obj.get_(name)
        if hasattr(obj, name):
            return getattr(obj, name)
        raise AssertionError(f"get {name} on {type(obj).__name__}")

    def set(self, obj, name, value):
        if isinstance(obj, Dictionary):
            obj.set_(name, value)
            return
        setattr(obj, name, value)

    def call(self, obj, name, args):
        short = name.split("::")[-1]
        if isinstance(obj, list) and short == "push":
            obj.extend(args)
            return len(obj)
        if isinstance(obj, str) and short == "split":
            sep = to_str(args[0])
            parts = obj.split(sep) if sep != "" else list(obj)
            if len(args) > 1:
                limit = to_int(args[1]) & 0xFFFFFFFF
                parts = parts[:limit]
            return parts
        fn = getattr(obj, short, None)
        if fn is None or not callable(fn):
            raise AssertionError(f"call {name} on {type(obj).__name__}")
        return fn(*args)

    def construct(self, name, args):
        raise AssertionError("construct " + name)

    def coerce(self, name, value):
        return value

    def astypelate(self, value, cls):
        return value if cls == "Array" and isinstance(value, list) else None


def run(abc, body, env, this, args, max_steps=2_000_000):
    code = asm.decode(body[5])
    loc = [this] + list(args) + [UNDEF] * max(0, body[2] - 1 - len(args))
    stack, pc, steps = [], 0, 0
    mn = abc.multinames

    def name_of(index):
        return abc.mn_name(index)

    def is_mnl(index):
        return mn[index][0] in (0x1B, 0x1C)

    while True:
        steps += 1
        if steps > max_steps:
            raise AssertionError("step limit")
        ins = code[pc]
        pc += 1
        n = ins.name
        a = ins.args
        if n.startswith("getlocal_"):
            stack.append(loc[int(n[-1])])
        elif n == "getlocal":
            stack.append(loc[a[0]])
        elif n.startswith("setlocal_"):
            loc[int(n[-1])] = stack.pop()
        elif n == "setlocal":
            loc[a[0]] = stack.pop()
        elif n in ("pushscope",):
            stack.pop()
        elif n in ("avm_label", "nop"):
            pass
        elif n == "pushnull":
            stack.append(None)
        elif n == "pushundefined":
            stack.append(UNDEF)
        elif n == "pushtrue":
            stack.append(True)
        elif n == "pushfalse":
            stack.append(False)
        elif n == "pushbyte":
            stack.append(a[0] - 256 if a[0] > 127 else a[0])
        elif n == "pushshort":
            stack.append(a[0])
        elif n == "pushstring":
            stack.append(abc.s(a[0]))
        elif n == "pushint":
            stack.append(abc.ints[a[0]])
        elif n == "pushdouble":
            stack.append(abc.doubles[a[0]])
        elif n == "dup":
            stack.append(stack[-1])
        elif n == "pop":
            stack.pop()
        elif n == "swap":
            stack[-1], stack[-2] = stack[-2], stack[-1]
        elif n in ("coerce", "astype"):
            stack.append(env.coerce(name_of(a[0]), stack.pop()))
        elif n == "coerce_a":
            pass
        elif n in ("coerce_s",):
            v = stack.pop()
            stack.append(None if v is None or v is UNDEF else to_str(v))
        elif n == "convert_s":
            stack.append(to_str(stack.pop()))
        elif n == "convert_i":
            stack.append(to_int(stack.pop()))
        elif n == "convert_d":
            stack.append(to_number(stack.pop()))
        elif n == "convert_b":
            stack.append(truthy(stack.pop()))
        elif n == "not":
            stack.append(not truthy(stack.pop()))
        elif n == "add":
            b, x = stack.pop(), stack.pop()
            stack.append(add(x, b))
        elif n in ("equals", "strictequals", "greaterthan", "lessthan"):
            b, x = stack.pop(), stack.pop()
            if n == "equals":
                stack.append(loose_eq(x, b))
            elif n == "strictequals":
                stack.append(strict_eq(x, b))
            elif n == "greaterthan":
                stack.append(to_number(x) > to_number(b))
            else:
                stack.append(to_number(x) < to_number(b))
        elif n in ("findproperty", "findpropstrict"):
            stack.append(env.findprop(name_of(a[0]), this))
        elif n == "getlex":
            stack.append(env.lex(name_of(a[0])))
        elif n == "getproperty":
            if is_mnl(a[0]):
                key = stack.pop()
                obj = stack.pop()
                if isinstance(obj, Dictionary):
                    stack.append(obj.get_(key))
                elif hasattr(obj, "mnl_get"):
                    stack.append(obj.mnl_get(key))
                elif isinstance(obj, list):
                    i = key if isinstance(key, int) and not isinstance(key, bool) else None
                    stack.append(obj[i] if i is not None and 0 <= i < len(obj) else UNDEF)
                else:
                    raise AssertionError(f"MNL get on {type(obj).__name__}")
            else:
                obj = stack.pop()
                stack.append(env.get(obj, name_of(a[0])))
        elif n in ("setproperty", "initproperty"):
            value = stack.pop()
            if is_mnl(a[0]):
                key = stack.pop()
                obj = stack.pop()
                assert isinstance(obj, Dictionary), type(obj)
                obj.set_(key, value)
            else:
                obj = stack.pop()
                env.set(obj, name_of(a[0]), value)
        elif n in ("callproperty", "callpropvoid"):
            argc = a[1]
            call_args = [stack.pop() for _ in range(argc)][::-1]
            obj = stack.pop()
            r = env.call(obj, name_of(a[0]), call_args)
            if n == "callproperty":
                stack.append(r)
        elif n == "constructprop":
            argc = a[1]
            call_args = [stack.pop() for _ in range(argc)][::-1]
            stack.pop()
            stack.append(env.construct(name_of(a[0]), call_args))
        elif n == "newobject":
            obj = PlainObject()
            pairs = [(stack.pop(), stack.pop()) for _ in range(a[0])][::-1]
            for value, key in pairs:
                obj.set_(key, value)
            stack.append(obj)
        elif n == "newarray":
            items = [stack.pop() for _ in range(a[0])][::-1]
            stack.append(items)
        elif n == "astypelate":
            cls = stack.pop()
            stack.append(env.astypelate(stack.pop(), cls))
        elif n == "inclocal_i":
            loc[a[0]] = to_int(loc[a[0]]) + 1
        elif n == "declocal_i":
            loc[a[0]] = to_int(loc[a[0]]) - 1
        elif n == "jump":
            pc = ins.target
        elif n in ("iftrue", "iffalse"):
            v = truthy(stack.pop())
            if v == (n == "iftrue"):
                pc = ins.target
        elif n in ("ifeq", "ifne", "ifstricteq", "ifstrictne", "iflt", "ifle", "ifgt", "ifge", "ifnlt", "ifnle",
                   "ifngt", "ifnge"):
            b, x = stack.pop(), stack.pop()
            if n == "ifeq":
                take = loose_eq(x, b)
            elif n == "ifne":
                take = not loose_eq(x, b)
            elif n == "ifstricteq":
                take = strict_eq(x, b)
            elif n == "ifstrictne":
                take = not strict_eq(x, b)
            else:
                nx, nb = to_number(x), to_number(b)
                rel = {"iflt": nx < nb, "ifle": nx <= nb, "ifgt": nx > nb, "ifge": nx >= nb,
                       "ifnlt": not (nx < nb), "ifnle": not (nx <= nb), "ifngt": not (nx > nb),
                       "ifnge": not (nx >= nb)}
                take = rel[n]
            if take:
                pc = ins.target
        elif n == "lookupswitch":
            i = to_int(stack.pop())
            pc = ins.cases[i] if 0 <= i < len(ins.cases) else ins.default
        elif n == "returnvalue":
            assert len(stack) == 1, stack
            return stack.pop()
        elif n == "returnvoid":
            assert not stack, stack
            return UNDEF
        elif n == "throw":
            raise Thrown(stack.pop())
        else:
            raise AssertionError("unsupported instruction " + n)

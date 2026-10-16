"""avm_mini 的扩展版解释器（只给 verify_pflv4 用）：多支持 P1-P3 体里出现的指令，并可在指定 pc 停下。

执行的是 SWF 里真实的方法体字节码；对象由测试提供的 Env 模拟。未实现的指令一律抛异常。
"""
from __future__ import annotations

import sys

sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from common import asm  # noqa: E402
from avm_mini import UNDEF, Thrown, add, loose_eq, strict_eq, to_int, to_number, to_str, truthy  # noqa: E402,F401


class Stop(Exception):
    def __init__(self, pc, loc, stack):
        super().__init__(pc)
        self.pc, self.loc, self.stack = pc, loc, stack


def run(abc, body, env, this, args, stop_at=None, max_steps=200_000):
    code = asm.decode(body[5])
    loc = [this] + list(args) + [UNDEF] * max(0, body[2] - 1 - len(args))
    stack, pc, steps = [], 0, 0
    mn = abc.multinames

    def name_of(index):
        return abc.mn_name(index)

    def is_mnl(index):
        return mn[index][0] in (0x1B, 0x1C)

    while True:
        if stop_at is not None and pc == stop_at:
            raise Stop(pc, loc, stack)
        steps += 1
        if steps > max_steps:
            raise AssertionError("step limit")
        ins = code[pc]
        env.trace_pc(pc)
        pc += 1
        n, a = ins.name, ins.args
        if n.startswith("getlocal_"):
            stack.append(loc[int(n[-1])])
        elif n == "getlocal":
            stack.append(loc[a[0]])
        elif n.startswith("setlocal_"):
            loc[int(n[-1])] = stack.pop()
        elif n == "setlocal":
            loc[a[0]] = stack.pop()
        elif n == "pushscope":
            stack.pop()
        elif n == "pushnull":
            stack.append(None)
        elif n == "pushtrue":
            stack.append(True)
        elif n == "pushfalse":
            stack.append(False)
        elif n == "pushnan":
            stack.append(float("nan"))
        elif n == "pushbyte":
            stack.append(a[0] - 256 if a[0] > 127 else a[0])
        elif n == "pushshort":
            stack.append(a[0] - 0x10000 if a[0] > 0x7FFF else a[0])
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
            stack.append(env.coerce(n, name_of(a[0]), stack.pop()))
        elif n == "coerce_a":
            pass
        elif n == "coerce_s":
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
        elif n in ("add", "add_i", "subtract", "subtract_i", "multiply", "multiply_i", "divide", "modulo",
                   "bitxor", "bitor", "bitand", "lshift"):
            b, x = stack.pop(), stack.pop()
            if n == "add":
                r = add(x, b)
            elif n == "add_i":
                r = to_int(to_number(x) + to_number(b))
            elif n == "subtract":
                r = to_number(x) - to_number(b)
            elif n == "subtract_i":
                r = to_int(to_number(x) - to_number(b))
            elif n == "multiply":
                r = to_number(x) * to_number(b)
            elif n == "multiply_i":
                r = to_int(to_number(x) * to_number(b))
            elif n == "divide":
                r = to_number(x) / to_number(b) if to_number(b) else float("inf")
            elif n == "modulo":
                xi, bi = to_number(x), to_number(b)
                r = float(int(xi) % int(bi)) if xi >= 0 else -float(int(-xi) % int(bi))
            elif n == "bitxor":
                r = to_int(to_int(x) ^ to_int(b))
            elif n == "bitor":
                r = to_int(to_int(x) | to_int(b))
            elif n == "bitand":
                r = to_int(to_int(x) & to_int(b))
            else:
                r = to_int(to_int(x) << (to_int(b) & 31))
            stack.append(r)
        elif n in ("equals", "strictequals", "greaterthan", "lessthan"):
            b, x = stack.pop(), stack.pop()
            stack.append({"equals": loose_eq, "strictequals": strict_eq}[n](x, b) if n in ("equals", "strictequals")
                         else (to_number(x) > to_number(b) if n == "greaterthan" else to_number(x) < to_number(b)))
        elif n in ("findproperty", "findpropstrict"):
            stack.append(env.findprop(name_of(a[0]), this))
        elif n == "getlex":
            stack.append(env.lex(name_of(a[0])))
        elif n == "getglobalscope":
            stack.append(env.globalscope())
        elif n == "getproperty":
            if is_mnl(a[0]):
                key = stack.pop()
                obj = stack.pop()
                stack.append(env.mnl_get(obj, key))
            else:
                obj = stack.pop()
                stack.append(env.get(obj, name_of(a[0])))
        elif n in ("setproperty", "initproperty"):
            value = stack.pop()
            obj = stack.pop()
            env.set(obj, name_of(a[0]), value)
        elif n in ("callproperty", "callpropvoid"):
            argc = a[1]
            call_args = [stack.pop() for _ in range(argc)][::-1]
            obj = stack.pop()
            r = env.call(obj, name_of(a[0]), call_args)
            if n == "callproperty":
                stack.append(r)
        elif n == "call":
            argc = a[0]
            call_args = [stack.pop() for _ in range(argc)][::-1]
            _receiver = stack.pop()
            fn = stack.pop()
            stack.append(fn(*call_args))
        elif n == "constructprop":
            argc = a[1]
            call_args = [stack.pop() for _ in range(argc)][::-1]
            stack.pop()
            stack.append(env.construct(name_of(a[0]), call_args))
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
                take = {"iflt": nx < nb, "ifle": nx <= nb, "ifgt": nx > nb, "ifge": nx >= nb,
                        "ifnlt": not (nx < nb), "ifnle": not (nx <= nb), "ifngt": not (nx > nb),
                        "ifnge": not (nx >= nb)}[n]
            if take:
                pc = ins.target
        elif n == "lookupswitch":
            i = to_int(stack.pop())
            pc = ins.cases[i] if 0 <= i < len(ins.cases) else ins.default
        elif n == "returnvoid":
            assert not stack, stack
            return UNDEF
        elif n == "returnvalue":
            assert len(stack) == 1, stack
            return stack.pop()
        elif n == "throw":
            raise Thrown(stack.pop())
        else:
            raise AssertionError("unsupported instruction " + n)

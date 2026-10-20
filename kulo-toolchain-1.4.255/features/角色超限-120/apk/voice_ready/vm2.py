"""有限指令解释器：直接运行生成的指令，不另写补丁行为模型。"""
import math


def run(ins, abc, args, lex=None, stack=None):
    regs, stack, lex = dict(enumerate(args)), ([] if stack is None else stack), (lex or {})
    pc, steps = 0, 0
    def symbol(index):
        return abc.mn_name(index)
    def get(obj, key):
        if isinstance(obj, str) and key == 'substr':
            return lambda a, n: obj[a:a+n]
        if key == 'length':
            return len(obj)
        if isinstance(obj, list) and key == 'http://adobe.com/AS3/2006/builtin::push':
            def push(*values):
                obj.extend(values)
                return len(obj)
            return push
        if isinstance(obj, (dict, list)):
            return obj.get(key) if isinstance(obj, dict) else obj[key]
        return getattr(obj, key)
    def set_(obj, key, value):
        if isinstance(obj, dict): obj[key] = value
        else: setattr(obj, key, value)
    while pc < len(ins):
        x, steps = ins[pc], steps+1
        if steps > 10000: raise AssertionError('instruction loop')
        pc += 1
        op, a = x.name, x.args
        if op in ('avm_label', 'nop'): pass
        elif op.startswith('getlocal_'): stack.append(regs[int(op[-1])])
        elif op == 'getlocal': stack.append(regs[a[0]])
        elif op.startswith('setlocal_'): regs[int(op[-1])] = stack.pop()
        elif op == 'setlocal': regs[a[0]] = stack.pop()
        elif op == 'inclocal_i': regs[a[0]] += 1
        elif op == 'pushscope': stack.pop()
        elif op == 'pushbyte': stack.append(a[0] if a[0] < 128 else a[0]-256)
        elif op == 'pushint': stack.append(abc.ints[a[0]])
        elif op == 'pushstring': stack.append(abc.strings[a[0]].decode())
        elif op == 'pushtrue': stack.append(True)
        elif op == 'pushfalse': stack.append(False)
        elif op == 'pushnull': stack.append(None)
        elif op == 'dup': stack.append(stack[-1])
        elif op == 'pop': stack.pop()
        elif op in ('coerce', 'coerce_a', 'convert_b'): pass
        elif op in ('coerce_s', 'convert_s'):
            v = stack.pop(); stack.append(None if v is None and op == 'coerce_s' else (v if isinstance(v, str) else str(v)))
        elif op == 'increment_i': stack.append(int(stack.pop()) + 1)
        elif op in ('convert_i', 'convert_d'):
            value = stack.pop()
            stack.append((int if op == 'convert_i' else float)(value or 0))
        elif op == 'astype':
            obj = stack.pop()
            stack.append(obj if obj is not None and get(obj, '_type') == symbol(a[0]) else None)
        elif op == 'getproperty':
            # Runtime-name multinames can occupy different pool indexes after
            # an iOS import; the AVM2 kind determines the extra stack operand.
            key = stack.pop() if abc.multinames[a[0]][0] in (0x1b, 0x1c) else symbol(a[0])
            stack.append(get(stack.pop(), key))
        elif op in ('setproperty', 'initproperty'):
            value, obj = stack.pop(), stack.pop()
            set_(obj, symbol(a[0]), value)
        elif op == 'getlex': stack.append(lex[symbol(a[0])])
        elif op in ('findproperty', 'findpropstrict'):
            stack.append(lex.get(symbol(a[0]), regs[0]))
        elif op in ('callproperty', 'callpropvoid'):
            vals = [stack.pop() for _ in range(a[1])][::-1]
            obj = stack.pop()
            result = get(obj, symbol(a[0]))(*vals)
            if op == 'callproperty': stack.append(result)
        elif op == 'newarray': stack.append([stack.pop() for _ in range(a[0])][::-1])
        elif op == 'newobject':
            obj = {}
            for _ in range(a[0]):
                v, k = stack.pop(), stack.pop(); obj[k] = v
            stack.append(obj)
        elif op in ('strictequals', 'equals', 'subtract_i', 'subtract', 'add', 'divide', 'modulo', 'bitand', 'bitor'):
            b, c = stack.pop(), stack.pop()
            stack.append({'strictequals': lambda: type(c) is type(b) and c == b,
                          'equals': lambda: c == b, 'subtract_i': lambda: c-b,
                          'subtract': lambda: c-b, 'add': lambda: (c+str(b)) if isinstance(c,str) else ((str(c)+b) if isinstance(b,str) else c+b),
                          'divide': lambda: c/b, 'modulo': lambda: c%b,
                          'bitand': lambda: int(c)&int(b), 'bitor': lambda: int(c)|int(b)}[op]())
        elif op == 'not': stack.append(not stack.pop())
        elif op in ('iftrue', 'iffalse'):
            truth = bool(stack.pop())
            if truth == (op == 'iftrue'): pc = x.target
        elif op in ('ifeq', 'ifne', 'iflt', 'ifge', 'ifle', 'ifngt', 'ifgt'):
            b, c = stack.pop(), stack.pop()
            result = {'ifeq': lambda: c == b, 'ifne': lambda: c != b,
                      'iflt': lambda: c < b, 'ifge': lambda: c >= b, 'ifle': lambda: c <= b,
                      'ifngt': lambda: not c > b, 'ifgt': lambda: c > b}[op]()
            if result: pc = x.target
        elif op == 'jump': pc = x.target
        elif op == 'lookupswitch':
            index = int(stack.pop())
            pc = x.cases[index] if 0 <= index < len(x.cases) else x.default
        elif op == 'returnvalue': return stack.pop()
        elif op == 'returnvoid': return None
        else: raise AssertionError('unsupported instruction: ' + op)
    raise AssertionError('method fell through instead of returning')

#!/usr/bin/env python3
"""AVM2 方法体汇编器 / 拼接器 —— V12 客户端补丁的公共底座。

为什么不走 FFDec `-replace`:V12 要改的 `AbilityValues.parseAt47` /
`parseAt109` / `InstantAbilitySource.resolveInstantContent` /
`DuringAbilitySource.createFromDuringAbilityValues` 都是几万字节的巨型方法,
FFDec 的 P-code 往返即使**一个字节都不改**也会重写这些体里成百上千条
「终止指令之后的死 jump」(实测:体 39128 有 724 处、体 14582 有 723 处)。
那些改写可以证明无害(分类脚本 `<我方工作区>/out/newchars-v12-20260907/analyze_rt.py`:
全部是 throw/return/jump 之后、入口不可达、既不是分支目标也不是异常目标的
`jump`,偏移被归零),但它们会把「只有我改的地方变了」这条验收判据彻底淹掉。

所以 V12 全程走仓内 ABC 读写器(`client-patch/rank-button-p1/abc/abcfmt.py`,
逐字节往返自检),在字节码层面插入指令:除被插入的方法体外,ABC 的每一个
字节都保持不变,方法体差分因此可以直接断言「只有这 N 个体变了」。

本模块提供四件事:
  * `decode` / `encode` —— 指令级往返(分支目标按**指令下标**保存,重编码时
    重算 s24,所以在任意位置插入指令都不会错位);
  * `assemble` —— 把助记符列表翻译成指令表,标签写成 `("label", "NAME")`;
  * `splice` —— 在指定指令下标处插入指令,并同步修正异常表与所有分支;
  * `simulate` —— 前向抽象解释,算出栈深/作用域深并抓不平衡。

铁律:
  * 未知操作码一律抛异常,绝不「跳过」;
  * `lookupswitch` 的 case 偏移相对**指令起点**,不是下一条指令;
  * 新增局部变量或加深栈时,调用方必须自己抬高 `localcount` / `maxstack`
    —— 本模块只负责算出真实需求并让调用方断言,不替调用方猜。
"""
from __future__ import annotations

import importlib


def load_abc_module(name: str):
    """Load only the packaged ABC readers, without changing sys.path."""
    if name not in {"abcfmt", "opwalk", "swftags"}:
        raise ValueError(f"unsupported ABC helper: {name}")
    return importlib.import_module(f"{__package__}.{name}")


opwalk = load_abc_module("opwalk")
U30, U8, S24, SW = opwalk.U30, opwalk.U8, opwalk.S24, opwalk.SW
OPS = opwalk.OPS


class AsmError(RuntimeError):
    """拒绝未知输入、拒绝歧义、拒绝静默降级。"""


# ---------------------------------------------------------------------------
# 助记符表(AVM2 指令集官方编号)。写错名字会当场报错,不会静默变成别的指令。
MNEMONICS = {
    "bkpt": 0x01, "nop": 0x02, "throw": 0x03, "avm_label": 0x09,
    "ifnlt": 0x0C, "ifnle": 0x0D, "ifngt": 0x0E, "ifnge": 0x0F,
    "jump": 0x10, "iftrue": 0x11, "iffalse": 0x12, "ifeq": 0x13, "ifne": 0x14,
    "iflt": 0x15, "ifle": 0x16, "ifgt": 0x17, "ifge": 0x18,
    "ifstricteq": 0x19, "ifstrictne": 0x1A, "lookupswitch": 0x1B,
    "pushwith": 0x1C, "popscope": 0x1D, "nextname": 0x1E, "hasnext": 0x1F,
    "pushnull": 0x20, "pushundefined": 0x21, "nextvalue": 0x23,
    "pushbyte": 0x24, "pushshort": 0x25, "pushtrue": 0x26, "pushfalse": 0x27,
    "pushnan": 0x28, "pop": 0x29, "dup": 0x2A, "swap": 0x2B,
    "pushstring": 0x2C, "pushint": 0x2D, "pushuint": 0x2E, "pushdouble": 0x2F,
    "pushscope": 0x30, "pushnamespace": 0x31, "hasnext2": 0x32,
    "newfunction": 0x40, "call": 0x41, "construct": 0x42, "callmethod": 0x43,
    "callstatic": 0x44, "callsuper": 0x45, "callproperty": 0x46,
    "returnvoid": 0x47, "returnvalue": 0x48, "constructsuper": 0x49,
    "constructprop": 0x4A, "callproplex": 0x4C, "callsupervoid": 0x4E,
    "callpropvoid": 0x4F,
    "applytype": 0x53, "newobject": 0x55, "newarray": 0x56, "newactivation": 0x57,
    "newclass": 0x58, "getdescendants": 0x59, "newcatch": 0x5A,
    "findpropstrict": 0x5D, "findproperty": 0x5E, "finddef": 0x5F,
    "getlex": 0x60, "setproperty": 0x61, "getlocal": 0x62, "setlocal": 0x63,
    "getglobalscope": 0x64, "getscopeobject": 0x65, "getproperty": 0x66,
    "initproperty": 0x68, "deleteproperty": 0x6A, "getslot": 0x6C, "setslot": 0x6D,
    "convert_s": 0x70, "esc_xelem": 0x71, "esc_xattr": 0x72,
    "convert_i": 0x73, "convert_u": 0x74, "convert_d": 0x75, "convert_b": 0x76,
    "convert_o": 0x77, "checkfilter": 0x78,
    "coerce": 0x80, "coerce_a": 0x82, "coerce_s": 0x85, "astype": 0x86,
    "astypelate": 0x87,
    "negate": 0x90, "increment": 0x91, "inclocal": 0x92, "decrement": 0x93,
    "declocal": 0x94, "typeof": 0x95, "not": 0x96, "bitnot": 0x97,
    "add": 0xA0, "subtract": 0xA1, "multiply": 0xA2, "divide": 0xA3, "modulo": 0xA4,
    "lshift": 0xA5, "rshift": 0xA6, "urshift": 0xA7, "bitand": 0xA8,
    "bitor": 0xA9, "bitxor": 0xAA, "equals": 0xAB, "strictequals": 0xAC,
    "lessthan": 0xAD, "lessequals": 0xAE, "greaterthan": 0xAF, "greaterequals": 0xB0,
    "instanceof": 0xB1, "istype": 0xB2, "istypelate": 0xB3, "in": 0xB4,
    "increment_i": 0xC0, "decrement_i": 0xC1, "inclocal_i": 0xC2, "declocal_i": 0xC3,
    "negate_i": 0xC4, "add_i": 0xC5, "subtract_i": 0xC6, "multiply_i": 0xC7,
    "getlocal_0": 0xD0, "getlocal_1": 0xD1, "getlocal_2": 0xD2, "getlocal_3": 0xD3,
    "setlocal_0": 0xD4, "setlocal_1": 0xD5, "setlocal_2": 0xD6, "setlocal_3": 0xD7,
}
BY_OPCODE = {code: name for name, code in MNEMONICS.items()}
BRANCHES = frozenset(range(0x0C, 0x1B))
CONDITIONAL_BRANCHES = BRANCHES - {0x10}
TERMINALS = frozenset({0x03, 0x10, 0x47, 0x48, 0x1B})


class Instruction:
    """一条指令。分支目标存**指令下标**,不存字节偏移。"""

    __slots__ = ("op", "args", "target", "cases", "default")

    def __init__(self, op, args=(), target=None, cases=None, default=None):
        self.op = op
        self.args = list(args)
        self.target = target        # 单目标分支(0x0C..0x1A)
        self.cases = cases          # lookupswitch 的 case 目标(指令下标)
        self.default = default      # lookupswitch 的 default 目标(指令下标)

    @property
    def name(self):
        return BY_OPCODE.get(self.op, "op_%02x" % self.op)

    def size(self):
        total = 1
        kinds = OPS[self.op]
        if self.op in BRANCHES:
            return total + 3
        if self.op == 0x1B:
            return total + 3 + len(opwalk.enc_u30(len(self.cases) - 1)) + 3 * len(self.cases)
        for kind, value in zip(kinds, self.args):
            total += len(opwalk.enc_u30(value)) if kind == U30 else 1
        return total

    def __repr__(self):
        return "<%s %r%s>" % (self.name, self.args,
                              "" if self.target is None else " -> #%d" % self.target)


def _operand_kinds(op):
    kinds = OPS.get(op)
    if kinds is None:
        raise AsmError("unknown opcode 0x%02x" % op)
    return kinds


def decode(code: bytes) -> list[Instruction]:
    """字节码 -> 指令表(分支目标已换算成指令下标)。"""
    raw = []
    position = 0
    length = len(code)
    while position < length:
        start = position
        op = code[position]
        position += 1
        kinds = _operand_kinds(op)
        args = []
        branch = None
        cases = default = None
        for kind in kinds:
            if kind == U30:
                value, position = opwalk._u30(code, position)
                args.append(value)
            elif kind == U8:
                args.append(code[position])
                position += 1
            elif kind == S24:
                branch, position = opwalk._s24(code, position)
            else:
                default, position = opwalk._s24(code, position)
                count, position = opwalk._u30(code, position)
                cases = []
                for _ in range(count + 1):
                    value, position = opwalk._s24(code, position)
                    cases.append(value)
        raw.append((start, position, op, args, branch, cases, default))
    index_of = {start: number for number, (start, *_rest) in enumerate(raw)}
    index_of[length] = len(raw)          # 指向代码末尾的分支(官方体里确实存在)

    def resolve(base, delta):
        target = base + delta
        if target not in index_of:
            raise AsmError("branch to %d is not an instruction boundary" % target)
        return index_of[target]

    out = []
    for start, end, op, args, branch, cases, default in raw:
        instruction = Instruction(op, args)
        if branch is not None:
            instruction.target = resolve(end, branch)
        if cases is not None:
            instruction.default = resolve(start, default)
            instruction.cases = [resolve(start, x) for x in cases]
        out.append(instruction)
    return out


def encode(instructions: list[Instruction]) -> tuple[bytes, list[int]]:
    """指令表 -> (字节码, 每条指令的字节偏移)。"""
    offsets = []
    position = 0
    for instruction in instructions:
        offsets.append(position)
        position += instruction.size()
    end = position

    def address(index):
        return end if index == len(instructions) else offsets[index]

    out = bytearray()
    for number, instruction in enumerate(instructions):
        op = instruction.op
        out.append(op)
        kinds = _operand_kinds(op)
        after = offsets[number] + instruction.size()
        argument = iter(instruction.args)
        for kind in kinds:
            if kind == U30:
                out += opwalk.enc_u30(next(argument))
            elif kind == U8:
                value = next(argument)
                if not 0 <= value <= 0xFF:
                    raise AsmError("u8 operand out of range: %r" % value)
                out.append(value)
            elif kind == S24:
                out += _s24(address(instruction.target) - after)
            else:
                out += _s24(address(instruction.default) - offsets[number])
                out += opwalk.enc_u30(len(instruction.cases) - 1)
                for case in instruction.cases:
                    out += _s24(address(case) - offsets[number])
    if len(out) != end:
        raise AsmError("encoder size prediction is wrong: %d != %d" % (len(out), end))
    return bytes(out), offsets


def _s24(value: int) -> bytes:
    if not -0x800000 <= value < 0x800000:
        raise AsmError("s24 out of range: %d" % value)
    return (value & 0xFFFFFF).to_bytes(3, "little")


# ---------------------------------------------------------------------------
def assemble(source) -> list[Instruction]:
    """助记符列表 -> 指令表。

    元素形式:
      * `("label", "NAME")`                —— 标签定义
      * `("jump", "NAME")` / `("iffalse", "NAME")` …  —— 分支到标签
      * `("callproperty", multiname, 2)`   —— 普通指令 + 操作数
    """
    items = []
    labels = {}
    for entry in source:
        if entry[0] == "label":
            if entry[1] in labels:
                raise AsmError("duplicate label %r" % entry[1])
            labels[entry[1]] = len(items)
            continue
        name = entry[0]
        if name not in MNEMONICS:
            raise AsmError("unknown mnemonic %r" % name)
        op = MNEMONICS[name]
        kinds = _operand_kinds(op)
        if op in BRANCHES:
            if len(entry) != 2:
                raise AsmError("%s takes exactly one label" % name)
            items.append(Instruction(op, (), target=entry[1]))
            continue
        if op == 0x1B:
            raise AsmError("assembling a lookupswitch is not supported")
        if len(entry) - 1 != len(kinds):
            raise AsmError("%s expects %d operand(s), got %d"
                           % (name, len(kinds), len(entry) - 1))
        for value in entry[1:]:
            if not isinstance(value, int) or value < 0:
                raise AsmError("%s operand must be a non-negative int: %r" % (name, value))
        items.append(Instruction(op, entry[1:]))
    end_label = len(items)
    for instruction in items:
        if instruction.target is not None:
            if instruction.target == "END":
                instruction.target = end_label
                continue
            if instruction.target not in labels:
                raise AsmError("branch to undefined label %r" % instruction.target)
            instruction.target = labels[instruction.target]
    return items


def block_locals(block) -> int:
    """块里用到的最大局部变量号 + 1(用于断言 localcount 够不够)。"""
    highest = -1
    for instruction in block:
        op = instruction.op
        if 0xD0 <= op <= 0xD3:
            highest = max(highest, op - 0xD0)
        elif 0xD4 <= op <= 0xD7:
            highest = max(highest, op - 0xD4)
        elif op in (0x62, 0x63, 0x92, 0x94, 0xC2, 0xC3):
            highest = max(highest, instruction.args[0])
        elif op == 0x32:
            highest = max(highest, instruction.args[0], instruction.args[1])
    return highest + 1


# ---------------------------------------------------------------------------
# 插入点本身是原有分支目标时,必须显式声明怎么处理 —— 默认是「拒绝」。
# 这条纪律是拿真机级别的 bug 换来的:BallImpl.update 的冷却帧插入点同时是
# `isSwifting()` 假分支和 `if(_loc3_ < _loc2_)` 假分支的落点,按默认(分支落到块后)
# 拼进去,插入的代码就只在「疾走且更短」那一条路上跑,别的路径悄悄跳过。
FORBID = "forbid"   # 插入点不许有任何原有分支指向它(默认;不满足直接报错)
SKIP = "skip"       # 允许:原有分支落到**块之后**(必须写清为什么跳过是对的)
ENTER = "enter"     # 允许:原有分支落到**块开头**(所有路径都要执行这一块)
INCOMING_POLICIES = (FORBID, SKIP, ENTER)


def splice(body, at_index: int, block: list[Instruction], incoming: str = FORBID):
    """在指令下标 `at_index` 处插入 `block`,返回 (新 code, 新异常表, 新指令表)。

    `body` 是 abcfmt 的 body 列表 `[method, maxstack, localcount, isd, msd,
    code, exceptions, traits]`;本函数不修改它,只返回新值。
    `incoming` 决定「原本就跳到 `at_index` 的分支」落在块前还是块后,见上面的常量。
    """
    if incoming not in INCOMING_POLICIES:
        raise AsmError("unknown incoming-branch policy %r" % (incoming,))
    instructions = decode(body[5])
    verify_code, old_offsets = encode(instructions)
    if verify_code != body[5]:
        raise AsmError("decode/encode is not byte-exact for this body")
    if not 0 <= at_index <= len(instructions):
        raise AsmError("insertion point out of range")
    count = len(block)

    def shift(index):
        return index + count if index >= at_index else index

    def shift_target(index):
        if index == at_index:
            if incoming == FORBID:
                raise AsmError(
                    "an original branch targets the insertion point #%d; declare "
                    "incoming=ENTER (every path must run the block) or "
                    "incoming=SKIP (and say why skipping is correct)" % at_index)
            if incoming == ENTER:
                return at_index
        return shift(index)

    for instruction in instructions:
        if instruction.target is not None:
            instruction.target = shift_target(instruction.target)
        if instruction.cases is not None:
            instruction.default = shift_target(instruction.default)
            instruction.cases = [shift_target(x) for x in instruction.cases]
    rebased = []
    for instruction in block:
        moved = Instruction(instruction.op, instruction.args)
        if instruction.target is not None:
            moved.target = instruction.target + at_index
        if instruction.cases is not None:
            moved.default = instruction.default + at_index
            moved.cases = [x + at_index for x in instruction.cases]
        rebased.append(moved)
    merged = instructions[:at_index] + rebased + instructions[at_index:]
    new_code, new_offsets = encode(merged)
    mapping = {offset: new_offsets[shift(number)] for number, offset in enumerate(old_offsets)}
    mapping[len(body[5])] = len(new_code)
    exceptions = []
    for start, stop, target, exception_type, variable in body[6]:
        for value in (start, stop, target):
            if value not in mapping:
                raise AsmError("exception boundary %d is not an instruction boundary" % value)
        exceptions.append((mapping[start], mapping[stop], mapping[target],
                           exception_type, variable))
    return new_code, exceptions, merged


def splice_many(body, insertions):
    """按**原始指令下标**在一个体里插入多块。

    `insertions` = [(原始下标, 指令表[, incoming 策略]), …],必须严格升序且互不相同。
    返回 (新 code, 新异常表, 新指令表, [(实际插入下标, 块长, 策略), …])。
    """
    normalized = [(entry[0], entry[1], entry[2] if len(entry) > 2 else FORBID)
                  for entry in insertions]
    positions = [index for index, _block, _policy in normalized]
    if positions != sorted(set(positions)):
        raise AsmError("insertion points must be strictly ascending and unique")
    working = list(body)
    placed = []
    offset = 0
    code = body[5]
    exceptions = body[6]
    merged = decode(code)
    for index, block, policy in normalized:
        working[5], working[6] = code, exceptions
        actual = index + offset
        code, exceptions, merged = splice(working, actual, block, incoming=policy)
        placed.append((actual, len(block), policy))
        offset += len(block)
    return code, exceptions, merged, placed


def unsplice_many(code: bytes, placed) -> bytes:
    """`splice_many` 的逆:按倒序把每一块摘掉。"""
    for entry in reversed(placed):
        code = unsplice(code, entry[0], entry[1])
    return code


def unsplice(code: bytes, at_index: int, count: int) -> bytes:
    """`splice` 的逆:摘掉 [at_index, at_index+count) 这一块并重编码。

    任何指向被摘区间内部的分支都会被拒绝 —— 那说明摘的不是一个自洽的块。
    """
    instructions = decode(code)
    if not 0 <= at_index and at_index + count <= len(instructions):
        raise AsmError("removal range out of bounds")
    end = at_index + count
    kept = instructions[:at_index] + instructions[end:]

    def unshift(index, owner):
        if index == at_index:
            # incoming=ENTER 时,原有分支落在块开头;摘掉块之后它回到接合点。
            return at_index
        if at_index < index < end:
            raise AsmError("instruction #%d still branches into the removed block" % owner)
        return index - count if index >= end else index

    for number, instruction in enumerate(kept):
        if instruction.target is not None:
            instruction.target = unshift(instruction.target, number)
        if instruction.cases is not None:
            instruction.default = unshift(instruction.default, number)
            instruction.cases = [unshift(x, number) for x in instruction.cases]
    return encode(kept)[0]


# ---------------------------------------------------------------------------
# 栈/作用域抽象解释。只用于自检:官方体本身必须先算得通,插入后也必须算得通。
_POP_PUSH = {
    0x01: (0, 0), 0x02: (0, 0), 0x03: (1, 0), 0x09: (0, 0), 0x08: (0, 0),
    0x04: (1, 1), 0x05: (1, 1), 0x06: (0, 0), 0x07: (0, 0), 0x0A: (0, 0), 0x0B: (0, 0),
    0x1C: (1, 0), 0x1D: (0, 0), 0x1E: (2, 1), 0x1F: (2, 1),
    0x20: (0, 1), 0x21: (0, 1), 0x23: (2, 1), 0x24: (0, 1), 0x25: (0, 1),
    0x26: (0, 1), 0x27: (0, 1), 0x28: (0, 1), 0x29: (1, 0), 0x2A: (0, 1),
    0x2B: (2, 2), 0x2C: (0, 1), 0x2D: (0, 1), 0x2E: (0, 1), 0x2F: (0, 1),
    0x30: (1, 0), 0x31: (0, 1), 0x32: (0, 1),
    0x40: (0, 1), 0x47: (0, 0), 0x48: (1, 0), 0x53: (0, 0),
    0x57: (0, 1), 0x59: (1, 1), 0x5A: (0, 1),
    0x5D: (0, 1), 0x5E: (0, 1), 0x5F: (0, 1), 0x60: (0, 1),
    0x61: (2, 0), 0x62: (0, 1), 0x63: (1, 0), 0x64: (0, 1), 0x65: (0, 1),
    0x66: (1, 1), 0x68: (2, 0), 0x6A: (1, 1), 0x6C: (1, 1), 0x6D: (2, 0),
    0x70: (1, 1), 0x71: (1, 1), 0x72: (1, 1), 0x73: (1, 1), 0x74: (1, 1),
    0x75: (1, 1), 0x76: (1, 1), 0x77: (1, 1), 0x78: (1, 1),
    0x80: (1, 1), 0x82: (1, 1), 0x85: (1, 1), 0x86: (1, 1), 0x87: (2, 1),
    0x90: (1, 1), 0x91: (1, 1), 0x92: (0, 0), 0x93: (1, 1), 0x94: (0, 0),
    0x95: (1, 1), 0x96: (1, 1), 0x97: (1, 1),
    0xC0: (1, 1), 0xC1: (1, 1), 0xC2: (0, 0), 0xC3: (0, 0), 0xC4: (1, 1),
    0xC5: (2, 1), 0xC6: (2, 1), 0xC7: (2, 1),
    0x41: None, 0x42: None, 0x43: None, 0x44: None, 0x45: None, 0x46: None,
    0x49: None, 0x4A: None, 0x4C: None, 0x4E: None, 0x4F: None,
    0x55: None, 0x56: None, 0x58: (1, 1),
}
for _op in range(0xA0, 0xB5):
    _POP_PUSH[_op] = (2, 1)
for _op in range(0x0C, 0x1B):
    _POP_PUSH[_op] = (2, 0) if _op not in (0x10, 0x11, 0x12, 0x1B) else (0, 0)
_POP_PUSH[0x11] = (1, 0)
_POP_PUSH[0x12] = (1, 0)
_POP_PUSH[0x1B] = (1, 0)
# istype 的类型是**编译期**操作数,只吃栈上那一个值(istypelate 0xB3 才吃两个)。
# 上面那圈 0xA0..0xB4 的 (2,1) 把它一起盖了 —— V12 没用到 istype 所以没暴露。
_POP_PUSH[0xB2] = (1, 1)
for _op in range(0xD0, 0xD4):
    _POP_PUSH[_op] = (0, 1)
for _op in range(0xD4, 0xD8):
    _POP_PUSH[_op] = (1, 0)


# 带多名(multiname)操作数的指令:运行时名/命名空间会额外吃栈。
_MULTINAME_OPERAND = {
    0x04: 0, 0x05: 0, 0x59: 0, 0x5D: 0, 0x5E: 0, 0x60: 0, 0x61: 0, 0x66: 0,
    0x68: 0, 0x6A: 0, 0x80: 0, 0x86: 0, 0xB2: 0,
    0x45: 0, 0x46: 0, 0x4A: 0, 0x4C: 0, 0x4E: 0, 0x4F: 0,
}
_RUNTIME_POPS = {0x07: 0, 0x0D: 0, 0x09: 0, 0x0E: 0, 0x1D: 0,
                 0x0F: 1, 0x10: 1, 0x11: 2, 0x12: 2, 0x1B: 1, 0x1C: 1}


def _runtime_name_pops(instruction, multinames):
    slot = _MULTINAME_OPERAND.get(instruction.op)
    if slot is None or multinames is None:
        return 0
    index = instruction.args[slot]
    if index == 0 or index >= len(multinames):
        return 0
    if instruction.op == 0x60:      # getlex 只接受编译期名字
        return 0
    return _RUNTIME_POPS.get(multinames[index][0], 0)


def _effect(instruction, multinames=None):
    op = instruction.op
    extra = _runtime_name_pops(instruction, multinames)
    entry = _POP_PUSH.get(op)
    if entry is not None:
        return (entry[0] + extra, entry[1])
    args = instruction.args
    if op in (0x46, 0x4C, 0x4A, 0x45):          # callproperty/callproplex/constructprop/callsuper
        return (1 + args[1] + extra, 1)
    if op in (0x4F, 0x4E):                       # callpropvoid / callsupervoid
        return (1 + args[1] + extra, 0)
    if op == 0x41:                               # call
        return (2 + args[0], 1)
    if op == 0x42:                               # construct
        return (1 + args[0], 1)
    if op == 0x49:                               # constructsuper
        return (1 + args[0], 0)
    if op in (0x43, 0x44):                       # callmethod / callstatic
        return (1 + args[1], 1)
    if op == 0x53:                               # applytype
        return (1 + args[0], 1)
    if op == 0x55:                               # newobject
        return (2 * args[0], 1)
    if op == 0x56:                               # newarray
        return (args[0], 1)
    raise AsmError("no stack effect for opcode 0x%02x" % op)


def simulate(instructions, initial_scope: int, multinames=None, exception_targets=()):
    """前向抽象解释:返回 (最大栈深, 最大作用域深, 不可达指令数)。

    只走可达路径;栈深在汇合点必须一致,否则抛异常 —— AVM2 校验器也是这么判的。
    `exception_targets` 是异常处理入口的**指令下标**,进入时栈上有一个异常对象。
    """
    stack_at = {0: (0, initial_scope)}
    pending = [0]
    for target in exception_targets:
        if target < len(instructions):
            stack_at[target] = (1, initial_scope)
            pending.append(target)
    seen = set()
    max_stack = 0
    max_scope = initial_scope
    while pending:
        index = pending.pop()
        if index in seen:
            continue
        seen.add(index)
        depth, scope = stack_at[index]
        instruction = instructions[index]
        pop, push = _effect(instruction, multinames)
        if depth < pop:
            raise AsmError("stack underflow at #%d (%s)" % (index, instruction.name))
        after = depth - pop + push
        scope_after = scope
        if instruction.op == 0x30:
            scope_after += 1
        elif instruction.op == 0x1C:
            scope_after += 1
        elif instruction.op == 0x1D:
            scope_after -= 1
        max_stack = max(max_stack, depth, after)
        max_scope = max(max_scope, scope_after)
        successors = []
        if instruction.op == 0x1B:
            successors = [instruction.default] + list(instruction.cases)
        elif instruction.op == 0x10:
            successors = [instruction.target]
        elif instruction.op in CONDITIONAL_BRANCHES:
            successors = [instruction.target, index + 1]
        elif instruction.op in (0x03, 0x47, 0x48):
            successors = []
        else:
            successors = [index + 1]
        for successor in successors:
            if successor == len(instructions):
                continue
            state = (after, scope_after)
            if successor in stack_at:
                if stack_at[successor] != state:
                    raise AsmError("stack/scope mismatch at #%d: %r vs %r"
                                   % (successor, stack_at[successor], state))
            else:
                stack_at[successor] = state
                pending.append(successor)
    return max_stack, max_scope, len(instructions) - len(seen)

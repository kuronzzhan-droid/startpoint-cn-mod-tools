# -*- coding: utf-8 -*-
"""只读反汇编：python dis.py <swf> <标签|/regex> [起止下标]"""
import sys, re
from pathlib import Path
sys.path.insert(0, r"D:/WF/startpoint-cn-kulo/client-patch/author-merge-20261001/abcasm")
sys.stdout.reconfigure(encoding="utf-8")
import asm, bodies
from swfabc import SwfAbc

_SWF = {}
def load(path):
    if path not in _SWF:
        _SWF[path] = SwfAbc(Path(path))
    return _SWF[path]

def fmt(abc, ins, i):
    name = ins.name
    args = []
    for a, k in zip(ins.args, asm._operand_kinds(ins.op) if hasattr(asm, "_operand_kinds") else []):
        args.append(a)
    s = f"{i:5d} {name}"
    if ins.op in asm.MNEMONICS.values():
        pass
    mn_ops = (0x04, 0x05, 0x40, 0x41, 0x45, 0x46, 0x4A, 0x4C, 0x4E, 0x4F, 0x5D, 0x5E, 0x60, 0x61, 0x66, 0x68, 0x6A, 0x80, 0x86, 0xB2, 0x59, 0x46, 0x43, 0x44)
    if ins.op in (0x46, 0x4A, 0x4C, 0x4F, 0x45, 0x4E, 0x5D, 0x5E, 0x60, 0x61, 0x66, 0x68, 0x6A, 0x80, 0x86, 0xB2, 0x59):
        s += f" {abc.mn_name(ins.args[0])}#{ins.args[0]}" + (f" ({ins.args[1]})" if len(ins.args) > 1 else "")
    elif ins.op == 0x2C:
        s += f" {abc.strings[ins.args[0]]!r}"
    elif ins.op == 0x2D:
        s += f" {abc.ints[ins.args[0]]}"
    elif ins.op == 0x2F:
        s += f" {abc.doubles[ins.args[0]] if hasattr(abc,'doubles') else ins.args}"
    else:
        s += " " + " ".join(map(str, ins.args))
    if ins.target is not None:
        s += f" -> {ins.target}"
    if ins.cases is not None:
        s += f" cases={ins.cases} default={ins.default}"
    return s

def main():
    swf = load(sys.argv[1]); abc = swf.abc
    lab = sys.argv[2]
    if lab.startswith("re:"):
        rx = re.compile(lab[3:])
        for k, v in bodies.label_map(abc).items():
            if rx.search(v): print(k, v)
        return
    bi = bodies.resolve(abc, lab); body = abc.bodies[bi]
    ins = asm.decode(body[5])
    print("body", bi, "header", body[1:5], "len", len(body[5]), "nins", len(ins), "exc", body[6])
    a, b = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (0, len(ins))
    for i in range(a, min(b, len(ins))):
        print(fmt(abc, ins[i], i))

if __name__ == "__main__":
    main()

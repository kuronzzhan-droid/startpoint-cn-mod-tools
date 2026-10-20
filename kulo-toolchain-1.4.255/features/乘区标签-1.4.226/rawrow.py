# -*- coding: utf-8 -*-
"""python rawrow.py ab|le <key> [idx...]：打印非空列（列号:块.字段=值[枚举名]）"""
import sys
sys.path.insert(0, r"D:/WF/out/乘区标签-1.4.226")
from fw import *  # noqa
import layout as Lo
F = Framework()
t, key = sys.argv[1], sys.argv[2]
idx = [int(x) for x in sys.argv[3:]]
tbl = "leader_ability" if t == "le" else "ability"
rs = F.le(key) if t == "le" else F.ab(key)
lay = D.layout(tbl)["blocks"]
starts = sorted((v, k) for k, v in lay.items())
def where(c):
    blk, st = None, None
    for v, k in starts:
        if c >= v: blk, st = k, v
    if blk is None: return f"head{c}"
    fb = Lo.EM["block_fields"]["precondition" if blk.startswith("precondition") else blk]
    off = c - st
    nm = next((n for o, n, _ in fb if int(o) == off), f"+{off}")
    return f"{blk}.{nm}"
for i, r in enumerate(rs):
    if idx and i not in idx: continue
    print(f"#{i}", D.describe_line(r, tbl))
    print("   ", "  ".join(f"c{c}:{where(c)}={v}" for c, v in enumerate(r) if v not in ("", "0", "(None)")))

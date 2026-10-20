# -*- coding: utf-8 -*-
"""用法：python check.py c159997 [c149986 ...]   —— 套用 chars/<mod>.py 的 apply(F)，做合法性检查并打印前后对比。不写盘。"""
import importlib, sys
sys.path.insert(0, r"D:/WF/out/乘区标签-1.4.226")
sys.path.insert(0, r"D:/WF/out/乘区标签-1.4.226/chars")
from fw import *  # noqa

F = Framework()
for m in sys.argv[1:]:
    F.owner = m
    importlib.import_module(m).apply(F)
F.owner = None
probs = []
out = F.touched()
for lp, ed in out.items():
    for k, nv in ed.items():
        if lp in (AB, LE):
            t = "leader_ability" if lp == LE else "ability"
            old = [r for r in rows(F.table(lp)[k]) if r]
            new = [r for r in rows(nv) if r]
            for i, r in enumerate(new):
                n = 124 if lp == LE else 126
                if len(r) != n:
                    probs.append(f"{lp} {k}#{i} 列数 {len(r)}")
                probs += [f"{lp} {k}#{i}: {p}" for p in L.client_legality_problems(t, r)]
            print(f"== {lp.split('/')[-1]} {k}")
            for i in range(max(len(old), len(new))):
                a = D.describe_line(old[i], t) if i < len(old) else None
                b = D.describe_line(new[i], t) if i < len(new) else None
                if a != b:
                    print(f"  #{i} - {a}\n  #{i} + {b}")
        elif lp == AS:
            print(f"== action_skill {k}: " + " | ".join(row(nv[lv])[1][:80] for lv in sorted(nv)))
        else:
            o = F.table(lp)[k]
            print(f"== {lp.split('/')[-1]} {k}\n  - {str(o)[:400]!r}\n  + {str(nv)[:400]!r}")
for p, tree in F.DSL.items():
    probs += [f"{p}: {x}" for x in W.dsl_signature_problems(tree)]
    enc = encode_tree(tree)
    assert wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == tree, p
    print(f"== DSL {p} 已改（编码往返通过）")
srv = [k for k in F.SRV if F.SRV[k] != F.SRV0[k]]
print("服务端 character_text 改动键:", srv)
print("\n".join(F.LOG))
print("PROBLEMS:", probs if probs else "无")

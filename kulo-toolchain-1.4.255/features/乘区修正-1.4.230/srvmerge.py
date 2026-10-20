# -*- coding: utf-8 -*-
"""按键合入（按角色+列直接写成新文案） character_text.json 的技能文案改动：只在该角色条目范围内做字符串替换，保留文件原有换行/缩进。
用法（盒子上）：python srvmerge.py <character_text.json> <character_text.patch.json>  → 原地写回（先备份 .bak-227）"""
import json, re, shutil, sys


def merge(txt, patch):
    nl = "\r\n" if "\r\n" in txt else "\n"
    out = txt
    for cid, cols in patch.items():
        m = re.search(r'(^|\n)\s*"%s"\s*:\s*\[' % re.escape(cid), out)
        if not m:
            print("跳过：文件里没有该角色", cid); continue
        st = m.start(); nx = re.search(r'\n\s{0,4}"[0-9]+"\s*:\s*\[', out[m.end():])
        en = m.end() + nx.start() if nx else len(out)
        seg = out[st:en]
        lits = list(re.finditer(r'"(?:[^"\\]|\\.)*"', seg))   # 0=键名，1..=第0行各列（字符串列）
        rep = []
        for c in cols:
            o, n = cols[c]
            lit = lits[int(c) + 1]
            if json.loads(lit.group()) != o: print("注意：原文与预期不同，按新文案覆盖", cid, c)
            rep.append((lit.start(), lit.end(), json.dumps(n, ensure_ascii=False)))
        for s, e, nj in sorted(rep, reverse=True):
            seg = seg[:s] + nj + seg[e:]
        out = out[:st] + seg + out[en:]
    data = json.loads(out)
    for cid, cols in patch.items():
        if cid not in data: continue
        for c, (o, n) in cols.items():
            assert data[cid][0][int(c)] == n, (cid, c)
    return out


if __name__ == "__main__":
    p, pp = sys.argv[1], sys.argv[2]
    raw = open(p, "rb").read(); txt = raw.decode("utf-8")
    patch = json.load(open(pp, encoding="utf-8"))
    shutil.copyfile(p, p + ".bak-227")
    new = merge(txt, patch)
    open(p, "wb").write(new.encode("utf-8"))
    print("merged", len(patch))

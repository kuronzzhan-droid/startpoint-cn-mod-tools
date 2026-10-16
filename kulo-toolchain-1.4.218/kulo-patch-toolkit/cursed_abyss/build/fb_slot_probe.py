# -*- coding: utf-8 -*-
"""五重 boss 招式槽：marker 时间轴触发集 vs 已填槽；不触发槽的独占 layer0 贡献。"""
import re
from fb_layer0_gate import *
v = View()
def fired(marker):
    raw = v.file(marker + ".timeline.amf3.deflate")
    if raw is None: return None
    t = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    out = {}
    for p in t.get("points", []):
        m = re.match(r"enemy_action(\d+)$", p.get("path", ""))
        if m:
            out[int(m.group(1))] = any(fr.get("data") for fr in p.get("frames", []))
    return out
allq = R0 + R1
seen = {}
for qid in allq:
    an, bosses = round_assets(v, qid)
    for b in bosses:
        if b in seen: continue
        r = tier_row(v.table(T_GB)[b])
        f = fired(r[25])
        filled = {s: r[110 + s] for s in range(1, 51) if r[110 + s] not in ("", "(None)")}
        nf = {s: p for s, p in filled.items() if f is not None and not f.get(s)}
        seen[b] = (r[25], sorted(k for k, x in (f or {}).items() if x), nf)
        print(qid, b, "marker", r[25], "fired", seen[b][1])
        for s, p in nf.items(): print("    NOFIRE", s, p)

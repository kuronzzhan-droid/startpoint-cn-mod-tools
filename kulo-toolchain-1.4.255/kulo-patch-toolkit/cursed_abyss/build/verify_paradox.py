"""确认 PARADOX 生成器（模块名可传）输出 == kulo 视图（WF_TIP）。"""
import sys, importlib
from live149 import *
mod = sys.argv[1] if len(sys.argv) > 1 else "wf_paradox_weapon"
P = importlib.import_module(mod)
W = P.W
try:
    raw, _ = read_raw(P.MATERIAL_ATLAS_MAP); atlas = P.atlas_names_from_raw(raw)
except FileNotFoundError:
    atlas = None
out = P.build(reader(W), allow_existing=True, client_capabilities=P.PATCHED_CLIENT_CAPABILITIES, atlas_names=atlas)
print('problems', out['problems'][:10])
d = 0
for lp, keys in out['flat'].items():
    live = flat(lp)
    for k, v in keys.items():
        if live.get(k) != v: d += 1; print('FLAT', lp, k)
for lp, keys in out['nested'].items():
    for k, v in keys.items():
        if nested(lp).get(k) != v: d += 1; print('NESTED', lp, k)
for prog, tree in out['dsl'].items():
    try: t = dsl_tree(prog)
    except Exception: t = None
    if t != tree: d += 1; print('DSL', prog)
for lp, data in []:
    try: r, _ = read_raw(lp)
    except FileNotFoundError: r = None
    if r != data and not (r and r[:4] == b'\x89png' and data[:4] in (b'\x89png', b'\x89PNG')): d += 1; print('FILE', lp)
for name, delta in out['server'].items():
    live = server(name)
    if isinstance(delta, list):
        m = [x for x in delta if x not in live]
        if m: d += 1; print('SRV', name, m[:3])
    else:
        for k, v in delta.items():
            lv = live.get(k)
            if isinstance(lv, dict) and isinstance(v, dict):
                lv = {kk: vv for kk, vv in lv.items() if kk != 'enhancementPurchaseMode'}
            if lv != v: d += 1; print('SRV', name, k, str(lv)[:120], '|', str(v)[:120])
print('diffs', d)

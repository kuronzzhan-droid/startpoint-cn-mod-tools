"""确认旧仓生成器（未改）输出 == kulo 1.4.149 现状（全部诅咒自有键）。"""
import sys
from live149 import *
import importlib
modname = sys.argv[1] if len(sys.argv) > 1 else 'wf_cursed_weapons'
W = importlib.import_module(modname)
W._check_collisions = lambda *a, **k: None
out = W.build(reader(W), client_capabilities=W.PATCHED_CLIENT_CAPABILITIES)
print('problems', len(out['problems'])); [print(' ', p) for p in out['problems'][:20]]
diff = 0
for lp, keys in out['flat'].items():
    live = flat(lp)
    for k, v in keys.items():
        if live.get(k) != v:
            diff += 1; print('FLAT DIFF', lp, k)
for lp, keys in out['nested'].items():
    live = nested(lp)
    for k, v in keys.items():
        if live.get(k) != v: diff += 1; print('NESTED DIFF', lp, k)
for prog, tree in out['dsl'].items():
    try:
        t = dsl_tree(prog)
    except Exception as e:
        t = None
    if t != tree: diff += 1; print('DSL DIFF', prog)
for name, delta in out['server'].items():
    live = server(name)
    if isinstance(delta, list):
        miss = [x for x in delta if x not in live]
        if miss: diff += 1; print('SERVER MISSING', name, miss[:5])
    else:
        for k, v in delta.items():
            if live.get(k) != v: diff += 1; print('SERVER DIFF', name, k, live.get(k), v)
print('total diffs', diff)

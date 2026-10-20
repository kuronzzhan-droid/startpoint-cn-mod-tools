"""usage: python celldiff.py <old.json> <new.json> -> per-key per-cell changes"""
import json, sys
a = json.loads(open(sys.argv[1], 'rb').read().decode('utf-8-sig'))
b = json.loads(open(sys.argv[2], 'rb').read().decode('utf-8-sig'))
def walk(x, y, p):
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)): walk(x.get(k), y.get(k), p + '/' + k)
    elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
        for i, (u, v) in enumerate(zip(x, y)): walk(u, v, p + f'[{i}]')
    elif x != y: print(p, '|', str(x)[:60], '->', str(y)[:60])
walk(a, b, '')

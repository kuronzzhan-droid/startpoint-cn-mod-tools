"""usage: python jdiff.py <old.json> <new.json>  -> top-level key diff summary"""
import json, sys
a = json.loads(open(sys.argv[1], 'rb').read().decode('utf-8-sig'))
b = json.loads(open(sys.argv[2], 'rb').read().decode('utf-8-sig'))
add = [k for k in b if k not in a]; rem = [k for k in a if k not in b]
chg = [k for k in b if k in a and a[k] != b[k]]
print('add', add[:20], len(add)); print('rem', rem[:20], len(rem)); print('chg', chg[:20], len(chg))

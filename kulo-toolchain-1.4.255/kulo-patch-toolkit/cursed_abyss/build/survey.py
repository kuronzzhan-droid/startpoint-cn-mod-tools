import json
from collections import Counter
from off import *
from layout import *
C = load('master/character/character.orderedmap'); CO = official('master/character/character.orderedmap')
MOD = [k for k in C if k not in CO] + ['151159', '261089']
TABLES = {'ability': 'master/ability/ability.orderedmap', 'leader_ability': 'master/ability/leader_ability.orderedmap'}
T = {t: load(lp) for t, lp in TABLES.items()}
TO = {t: official(lp) for t, lp in TABLES.items()}
def keys_of(cid):
    r = row(C[cid])
    return [('leader_ability', cid)] + [('ability', r[i]) for i in range(19, 25) if r[i] not in ('', '(None)')]
def scan():
    out = []
    for cid in MOD:
        for t, key in keys_of(cid):
            if key not in T[t]:
                continue
            offrows = [x for x in rows(TO[t][key]) if x] if key in TO[t] else []
            for i, r in enumerate([x for x in rows(T[t][key]) if x]):
                if r in offrows:
                    continue
                m = r[mode_col(t)]
                if m == '0':
                    tk = r[col(t, 'instant_trigger', 'kind')]; lim = r[col(t, 'instant_trigger', 'trigger_limit')]
                    ck = r[col(t, 'instant_content', 'kind')]
                    fields = CASES['instant_content'].get(ck, {}).get('fields', {})
                    out.append(dict(cid=cid, t=t, key=key, i=i, mode=m, trig=tk, lim=lim, kind=ck,
                                    frame='frame' in fields, strength='strength' in fields))
                else:
                    tk = r[col(t, 'during_trigger', 'kind')]; ck = r[col(t, 'during_content', 'kind')]
                    tf = CASES['during_trigger'].get(tk, {}).get('fields', {})
                    lim = r[col(t, 'during_trigger', 'trigger_limit')] if 'trigger_limit' in tf else '-'
                    out.append(dict(cid=cid, t=t, key=key, i=i, mode=m, trig=tk, lim=lim, kind=ck))
    return out
if __name__ == '__main__':
    rs = scan()
    inst = [r for r in rs if r['mode']=='0' and r['trig'] not in ('0','') and r['lim'] in ('(None)','') and r['strength'] and not r['frame']]
    print('instant permanent unlimited by kind', Counter(r['kind'] for r in inst).most_common())
    print('  by trig', Counter(r['trig'] for r in inst).most_common())
    dur = [r for r in rs if r['mode']=='1' and r['lim'] not in ('-',) ]
    print('during counting triggers', Counter((r['trig'], r['lim'] if r['lim'] in ('(None)','') else 'num') for r in dur).most_common())
    print('mod chars', len(MOD))

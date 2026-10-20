from survey import *
U = load('master/character/unique_condition.orderedmap')
STAT_I = {'32','33','34','55','388','35','694','693','695','696','723','245','205','717'}
def ucap(uid):
    if uid not in U: return None
    c = row(U[uid])[4]
    return 1 if c == '(None)' else int(c) if c.isdigit() else None
def candidates():
    out, skipped = [], []
    for r in scan():
        t = r['t']; R = [x for x in rows(T[t][r['key']]) if x][r['i']]
        if r['mode'] == '0':
            if r['trig'] in ('0', '') or not r['strength'] or r['frame'] or r['kind'] not in STAT_I:
                continue
            lo, hi = R[col(t,'instant_content','strength.power1')], R[col(t,'instant_content','strength.first_max')]
            if r['lim'] == '':
                skipped.append((r, '触发次数列空串=0次（死行）')); continue
            if r['lim'] != '(None)':
                continue
            if not (lo.lstrip('-').isdigit() and int(hi) > 0):
                skipped.append((r, f'负值/非数值 {lo},{hi}')); continue
            out.append(dict(r, lo=lo, hi=hi, block='instant'))
        else:
            if r['lim'] not in ('(None)',):
                continue
            ck = r['kind']
            lo, hi = R[col(t,'during_content','strength.power1')], R[col(t,'during_content','strength.first_max')]
            cap = None
            if r['trig'] in ('134','171','194'):
                uid = R[col(t,'during_trigger','unique_condition_id')]
                cap = ucap(uid); r = dict(r, uid=uid, ucap=cap)
                th = R[col(t,'during_trigger','threshold.first_max')]
                eff = None if cap is None else cap // max(1, int(int(th)//100000) if th.isdigit() else 1)
                if eff is not None and eff <= 10:
                    skipped.append((r, f'固有上限 {cap} 已封顶（有效层数≤{eff}）')); continue
            if r['trig'] == '136':
                skipped.append((r, '敌方弱体个数计数，天然有上限')); continue
            if not (lo.lstrip('-').isdigit() and hi.lstrip('-').isdigit() and int(hi) > 0):
                skipped.append((r, f'非正数值 {lo},{hi}')); continue
            out.append(dict(r, lo=lo, hi=hi, block='during'))
    return out, skipped
if __name__ == '__main__':
    import collections
    out, sk = candidates()
    CN = {k: row(C[k])[18] for k in MOD}
    for c in out: print(c['cid'], CN[c['cid']], c['t'][:6], c['key'], c['i'], c['block'], 'trig', c['trig'], 'kind', c['kind'], c['lo'], c['hi'], c.get('ucap',''))
    print('---- skipped')
    for r, why in sk: print(r['cid'], CN[r['cid']], r['t'][:6], r['key'], r['i'], r['kind'], why)
    print(len(out), 'changes;', len(set((c['t'],c['key']) for c in out)), 'keys;', len(set(c['cid'] for c in out)), 'chars')

"""845 竞速验收修订：可抽Mod红标1%，零概率Mod次之，官方保持。"""
from copy import deepcopy
from fractions import Fraction

import wf_mod_tool as core
from wf_content_gacha import BIG_BOSS_ZERO, EARLY_CANARIES, MINIBOSSES, probability

POOL_ID = '990002'
ANNIHILATOR = 179981
ODDS_PATH = 'master/gacha_odds/cnmod_ashen_verdict_gacha_character_5.orderedmap'


def revise_racing(gacha, custom_ids):
    """稳定分组，仅顺序/可抽Mod红标变化，绝不重分配权重。"""
    custom = frozenset(map(int, custom_ids)) - EARLY_CANARIES
    source = gacha[POOL_ID]
    entries = source['pool']['1']; ids = [int(e['id']) for e in entries]
    if len(ids) != len(set(ids)) or not custom <= set(ids) or set(ids)&EARLY_CANARIES:
        raise ValueError('missing/duplicate custom character or early test character')
    if len(custom) != 68 or not MINIBOSSES <= custom or not BIG_BOSS_ZERO <= custom:
        raise ValueError('unreviewed formal Mod roster')
    if source['rankRates'] != {'normal':[950,20,30], 'multiGuarantee':[950,50]}:
        raise ValueError('unreviewed racing rarity rates')
    zero = [cid for cid in ids if cid in custom and not probability(source,cid)]
    drawable = [cid for cid in ids if cid in custom and cid not in zero]
    if set(zero) != BIG_BOSS_ZERO or len(drawable) != 43:
        raise ValueError('unreviewed drawable/zero Mod boundary')
    if any(probability(source,cid) != Fraction(1,100) for cid in drawable):
        raise ValueError('a drawable Mod is not already exactly1 percent')
    zero = [ANNIHILATOR] + [cid for cid in zero if cid != ANNIHILATOR]
    official = [cid for cid in ids if cid not in custom]
    result = deepcopy(gacha); pool = result[POOL_ID]
    by_id = {int(e['id']):e for e in pool['pool']['1']}
    for cid in drawable: by_id[cid]['isRateUp'] = True
    pool['pool']['1'] = [by_id[cid] for cid in drawable+zero+official]
    return result


def reorder_native(raw, before_pool, after_pool):
    """保留每角色原压缩行；只给新红标重编码，再同步原生显示顺序。"""
    outer = core.read_orderedmap_raw_rows_from_bytes(raw)
    if len(outer.keys) != 1: raise ValueError('unreviewed odds outer schema')
    inner = core.read_orderedmap_raw_rows_from_bytes(outer.rows[0])
    if inner.keys != [str(i) for i in range(len(inner.keys))]: raise ValueError('unreviewed odds index keys')
    import zlib
    native = {}; before_entries=before_pool['pool']['1']
    for index, chunk in enumerate(inner.rows):
        rows = core.read_csv_lines(zlib.decompress(chunk).decode('utf-8'))
        if len(rows)!=1 or len(rows[0])!=7: raise ValueError('unreviewed odds value schema')
        row=rows[0]; entry=before_entries[index]
        expected=[str(entry['id']),'5',str(entry['odds'])] + [
            'true' if entry.get(flag) else 'false' for flag in ('isRateUp','isLimited','isExchangeable','trialReadingForced')]
        if row!=expected: raise ValueError('native/server racing baseline mismatch')
        native[int(row[0])] = (row,chunk)
    if len(native)!=len(before_entries): raise ValueError('native racing count differs')
    output=[]
    for entry in after_pool['pool']['1']:
        row,chunk = native[int(entry['id'])]; new='true' if entry.get('isRateUp') else 'false'
        if row[3]!=new:
            row=list(row);row[3]=new
            chunk=zlib.compress(core.write_csv_lines([row]).rstrip('\n').encode('utf-8'))
        output.append(chunk)
    inner.rows=output;outer.rows[0]=core.build_orderedmap_raw_rows(inner)
    return core.build_orderedmap_raw_rows(outer)

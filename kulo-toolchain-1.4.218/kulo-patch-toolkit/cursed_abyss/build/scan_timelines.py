"""扫描角色像素动画 timeline：序列最大 end、末序列 kind、atlas 最大帧号；找 Playhead 会越过全部序列的形态。"""
import os, sys, zlib, json
os.environ.setdefault("WF_TIP", "157")
from live149 import *
import wf_dsl
from off import official
C = load('master/character/character.orderedmap')
CO = official('master/character/character.orderedmap')
ids = sys.argv[1:] or [k for k in C if k not in CO] + ['151159', '261089']
def tl(path):
    raw, src = read_raw(path)
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree'], src
def scan(code, sub):
    out = {}
    try:
        t, src = tl(f'character/{code}/pixelart/{sub}.timeline.amf3.deflate')
    except FileNotFoundError:
        return None
    seqs = t['sequences']
    a, _ = tl(f'character/{code}/pixelart/{"sprite_sheet" if sub == "pixelart" else sub.replace("special", "special_sprite_sheet") if False else sub + "_sprite_sheet" if sub != "pixelart" else "sprite_sheet"}.atlas.amf3.deflate') if False else (None, None)
    ends = [int(s['end']) for s in seqs]
    order_ok = all(int(seqs[i]['begin']) > int(seqs[i - 1]['end']) - 1 for i in range(1, len(seqs)))
    last = max(seqs, key=lambda s: int(s['end']))
    names = [s['name'] for s in seqs]
    issues = []
    if last['kind'] == 'pass':
        issues.append(f"末序列 {last['name']} kind=pass(播完越界)")
    for s in seqs:
        if int(s['end']) < int(s['begin']):
            issues.append(f"{s['name']} end<begin")
    for need in ('walk_front', 'walk_back', 'neutral', 'kachidoki'):
        if need not in names:
            issues.append(f"缺序列 {need}")
    # 非递增：get_currentSequence 按列表顺序取第一个 end>=帧
    for i in range(1, len(seqs)):
        if int(seqs[i]['end']) < int(seqs[i - 1]['end']):
            issues.append(f"序列 end 非递增 {seqs[i-1]['name']}→{seqs[i]['name']}")
            break
    return {"src": src, "n": len(seqs), "max_end": max(ends), "last": (last['name'], last['kind']), "issues": issues,
            "kinds": {s['name']: s['kind'] for s in seqs}}
for cid in ids:
    code = row(C[cid])[0]
    for sub in ('pixelart', 'special'):
        r = scan(code, sub)
        if r and (r['issues'] or len(ids) < 12):
            print(cid, code, sub, r['n'], r['max_end'], r['last'], r['issues'], r['src'] if len(ids) < 12 else '')

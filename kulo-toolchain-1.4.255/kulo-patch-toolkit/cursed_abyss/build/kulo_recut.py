# -*- coding: utf-8 -*-
"""把 Ku1o staging 的 1.4.131-134 四条边重切到本地链 1.4.188-191（表成员三方行级合并，其余原样，>5MiB 按序号拆包）。"""
import os, zipfile, json, hashlib, copy, zlib
os.environ["WF_TIP"] = "187"
from base149 import *
from base149 import _INDEX
OUT = Path(__file__).resolve().parent.parent
SD = OUT / "kulo_staging"
LIMIT = 5 * 1024 * 1024
PLAN = [("pinball-1.4.130-1.4.131-1-liangyue-character-final-merged.zip", 187, "liangyue-character"),
        ("pinball-1.4.131-1.4.132-1-midautumn-orochi-event-closure-20261007.zip", 188, "midautumn-orochi-closure"),
        ("pinball-1.4.132-1.4.133-1-midautumn-mod-pool-migration-20261008.zip", 189, "midautumn-mod-pool-migration"),
        ("pinball-1.4.133-1.4.134-1-abyss-race-gacha-art-20261008.zip", 190, "abyss-race-gacha-art")]
LOGICAL = {member(x): x for x in ["master/character/character_text.orderedmap", "master/ability/ability.orderedmap",
           "master/ability/leader_ability.orderedmap", "master/character/character_status.orderedmap",
           "master/shop/boss_coin_shop.orderedmap", "master/skill/action_skill.orderedmap"]}
ours_new = {}   # member -> bytes from our re-cut edges (188..)
def our_raw(m):
    if m in ours_new: return ours_new[m]
    if m in _INDEX:
        with zipfile.ZipFile(_INDEX[m]) as z: return z.read(m)
    return None
def base_raw(m):  # 1.4.130 == store131 for these members (verified)
    return (STORE131 / m.split("upload/")[1]).read_bytes()
def merge(b, t, o, path, log):
    r = dict(o)  # keep our key order, append new keys
    for k in list(b) + [k for k in t if k not in b]:
        bv, tv = b.get(k), t.get(k)
        if bv == tv: continue
        ov = o.get(k)
        if ov == bv:
            if tv is None: r.pop(k, None); log.append(("del", path + [k]))
            else: r[k] = tv; log.append(("add" if bv is None else "mod", path + [k]))
        elif ov == tv: log.append(("same", path + [k]))
        elif all(isinstance(x, dict) for x in (bv, tv, ov)): r[k] = merge(bv, tv, ov, path + [k], log)
        else: raise SystemExit(f"CONFLICT {path+[k]}")
    return r
REPORT = []
for zname, frm, tag in PLAN:
    to = frm + 1
    with zipfile.ZipFile(SD / zname) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        data = {n: zf.read(n) for n in names}
    merged = {}
    for m in names:
        o = our_raw(m)
        if o is None or m.startswith("production/upload/") is False and o is None: continue
        if o is None: continue
        if m not in LOGICAL: raise SystemExit(f"untracked overlap {m}")
        b, t, oo = q.parse_node(base_raw(m)), q.parse_node(data[m]), q.parse_node(o)
        assert q.build_node(oo) == o, m
        log = []; res = merge(b, t, oo, [], log)
        nb = q.build_node(res); assert q.parse_node(nb) == res
        data[m] = nb; merged[LOGICAL[m]] = {"src_ours": (_INDEX[m].name if m in _INDEX else "recut"), "rows": [f"{a}:{'/'.join(map(str,p))}" for a, p in log]}
    for m in names: ours_new[m] = data[m]
    # split
    comp = {m: len(zlib.compress(data[m], 6)) for m in names}
    groups = []; cur = []; size = 0
    for m in sorted(names, key=lambda x: -comp[x]):
        placed = False
        for g in groups:
            if g[1] + comp[m] + 400 <= LIMIT - 64 * 1024: g[0].append(m); g[1] += comp[m] + 400; placed = True; break
        if not placed: groups.append([[m], comp[m] + 400])
    zips = []
    for i, (gm, _) in enumerate(groups, 1):
        name = f"pinball-1.4.{frm}-1.4.{to}-{i}-{tag}-local.zip"
        p = OUT / "patch" / name
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
            for m in sorted(gm): zf.writestr(m, data[m])
        blob = p.read_bytes(); assert len(blob) <= LIMIT, (name, len(blob))
        integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(gm),
                 "files": sorted(gm), "member_sha256": {m: hashlib.sha256(data[m]).hexdigest() for m in sorted(gm)},
                 "logical_paths": {member(lp): lp for lp in merged if member(lp) in gm},
                 "applies_on": f"1.4.{frm}", "version": f"1.4.{to}", "part": f"{i}/{len(groups)}",
                 "source": {"repo": "Ku1o/startpoint-cn-kulo@staging df99b73c", "archive": zname,
                            "sha256": hashlib.sha256((SD / zname).read_bytes()).hexdigest()},
                 "merged_tables": {k: v for k, v in merged.items() if member(k) in gm},
                 "log": [f"重切自 Ku1o staging {zname}；与本地 1.4.131-1.4.{frm} 重叠的表做三方行级合并，其余成员原样"]}
        p.with_name(p.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
        zips.append((name, len(blob), integ["sha256"], len(gm)))
    REPORT.append({"version": f"1.4.{to}", "src": zname, "members": len(names), "zips": zips, "merged": merged})
print(json.dumps(REPORT, ensure_ascii=False, indent=1))

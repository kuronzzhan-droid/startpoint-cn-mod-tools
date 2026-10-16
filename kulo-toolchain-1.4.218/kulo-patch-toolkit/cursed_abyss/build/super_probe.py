# -*- coding: utf-8 -*-
import os, io, json, zipfile, zlib
os.environ.setdefault("WF_TIP", "181")
from live149 import *  # noqa
import base149

B = load("master/battle/boss/general_boss.orderedmap")
KEYS = ["waraboss_katai", "waraboss_hayai", "waraboss_tsuyoi", "waraboss_noroi", "waraboss_mamori",
        "practice_waraboss_tough_attack", "practice_waraboss_tough_attack_funnel"]
z = zipfile.ZipFile(r"D:/WF/out/item-rarity-frame-20260928/WorldFlipper-item-rarity-frame.apk")
bz = zipfile.ZipFile(io.BytesIO(z.read("assets/bundle.zip")))
bnames = set(n.replace("production/android_bundle/", "") for n in bz.namelist())


def exists(logical):
    m = member(logical)
    if m in base149._INDEX:
        return "chain"
    if (base149.STORE131 / m.split("production/upload/")[1]).exists():
        return "store"
    if m.split("production/upload/")[1] in bnames:
        return "apk"
    return None


def walk(t, acc, progs):
    if isinstance(t, list):
        if t and t[0] == "ResolveByElement":
            acc.add(t[1])
        for x in t:
            walk(x, acc, progs)
    elif isinstance(t, str) and t.startswith("battle/action/enemy/action/") and "$" in t:
        progs.add(t)


def progs_of(key):
    out = set()
    for kk, v in B[key].items():
        r = row(v)
        for c in r:
            if c.startswith("battle/action/") and "$" in c:
                out.add(c)
    return out


report = {}
for key in KEYS:
    todo, seen, eff = list(progs_of(key)), set(), set()
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        try:
            t = dsl_tree(p)
        except Exception as e:
            continue
        sub = set()
        walk(t, eff, sub)
        todo += list(sub - seen)
    miss = {}
    for e in sorted(eff):
        name = e.rsplit("/", 1)[-1]
        res = {}
        for suf in ("red", "colorless"):
            lp = f"{e}/{name}_{suf}/{name}_{suf}"
            res[suf] = next((x for x in (exists(lp + ext) for ext in (".parts.amf3.deflate", ".timeline.amf3.deflate", ".png")) if x), None)
        miss[e] = res
    report[key] = {"programs": sorted(seen), "effects": miss}
print(json.dumps(report, ensure_ascii=False, indent=1))

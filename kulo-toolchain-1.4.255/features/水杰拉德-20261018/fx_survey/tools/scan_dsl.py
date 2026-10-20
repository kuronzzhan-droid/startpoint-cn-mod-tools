# -*- coding: utf-8 -*-
"""Scan every action DSL for ShowEffect commands -> showeffects.json"""
import json, csv, collections, sys
from pathlib import Path
import wfio

DEC = wfio.DEC
out = []
dsl_files = sorted((DEC / "battle/action").rglob("*.action.dsl.json"))
print("dsl files", len(dsl_files))

def walk(node, ctx, sink, path):
    if isinstance(node, list):
        if len(node) >= 2 and node[0] == "Command" and isinstance(node[1], list) and node[1] and node[1][0] == "ShowEffect":
            sink.append((node[1], list(ctx)))
        if len(node) >= 1 and isinstance(node[0], str) and node[0].startswith("Conditionals"):
            ctx2 = ctx + [node[0]]
        elif len(node) >= 2 and node[0] == "Event" and isinstance(node[1], list) and node[1] and isinstance(node[1][0], str):
            ctx2 = ctx + ["Event:" + node[1][0] + ":" + str(node[1][1] if len(node[1]) > 1 else "")]
        else:
            ctx2 = ctx
        for ch in node:
            walk(ch, ctx2, sink, path)
    elif isinstance(node, dict):
        for v in node.values():
            walk(v, ctx, sink, path)

for f in dsl_files:
    rel = f.relative_to(DEC).as_posix()[:-len(".action.dsl.json")]
    tree = json.loads(f.read_text(encoding="utf-8"))
    # re-read names properly from AMF if json names were mangled
    sink = []
    walk(tree, [], sink, rel)
    for cmd, ctx in sink:
        a = cmd[1:]
        rec = {
            "dsl": rel, "name": a[0], "effect": a[1], "subject": a[2], "layer": a[3][0] if isinstance(a[3], list) else a[3],
            "lifetime": a[4], "coord": a[5], "x": a[6], "y": a[7], "rot": a[8], "trackPos": a[9], "trackDir": a[10], "scale": a[11],
            "ctx": ctx,
        }
        out.append(rec)
print("ShowEffect cmds", len(out))
Path("showeffects.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
c = collections.Counter((r["effect"][0]) for r in out)
print(c)
eff = collections.Counter(r["effect"][1] if r["effect"][0] == "SpecifyEffectDirectly" else "BYELEM:" + str(r["effect"][1]) for r in out)
print("unique effect refs", len(eff))
print(collections.Counter(r["layer"] for r in out))
print(collections.Counter(json.dumps(r["scale"]) for r in out).most_common(15))
print(collections.Counter(r["subject"] for r in out).most_common(15))

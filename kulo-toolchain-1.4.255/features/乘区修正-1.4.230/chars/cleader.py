# -*- coding: utf-8 -*-
"""1.4.230：带「队长」前置（precondition=42 Leader）的能力行，面板文字从能力覆盖文案移到队长技覆盖文案。只动文字，数据行不动。"""
import json, re
from fw import AB, CAS, CH, LE, rows, row, leaf, D

ICON = " <icon id='main'>  "
LEADER_LINE = re.compile(r"担任队长|为队长时")
PLACEHOLDER = "效果写在队长技中"


def strip_leader(ln):
    s = ln.replace(ICON, "").strip()
    for a, b in ((r"担任队长且", ""), (r"(自身)?担任队长时，", ""), (r"若担任队长，", ""), (r"泽赫尔为队长时，", "")):
        s = re.sub(a, b, s)
    assert "队长" not in s, ln
    return s


def apply(F):
    lay = D.layout("ability")["blocks"]
    pcs = [int(lay[k]) for k in ("precondition1", "precondition2", "precondition3")]
    idx = json.load(open(r"D:/WF/out/面板核对-1.4.227/audit/index.json", encoding="utf-8"))
    T = F.table(CAS); moved = 0
    for e in idx:
        r = row(F.table(CH)[e["id"]]); lid = r[17] if r[17] not in ("", "(None)") else e["id"]
        lr = [x for x in rows(F.table(LE).get(lid, "")) if x]
        if not lr: continue
        lkey = "desc_override_" + lr[0][0]
        if lkey not in T: continue
        add = []
        for a in r[19:25]:
            rs = [x for x in rows(F.table(AB).get(a, "")) if x]
            if not rs or not any(x[c] == "42" for x in rs for c in pcs): continue
            akey = "desc_override_" + rs[0][0]
            if akey not in T or akey == lkey: continue
            lines = rows(F.string(CAS, akey))[0][0].split("\n")
            keep = [ln for ln in lines if not LEADER_LINE.search(ln)]
            mv = [ln for ln in lines if LEADER_LINE.search(ln)]
            if not mv: continue
            add += [strip_leader(ln) for ln in mv]
            if not keep:
                keep = [(ICON if lines[0].startswith(ICON) else "") + PLACEHOLDER]
            v = F.string(CAS, akey); F.set_string(CAS, akey, leaf(v, [["\n".join(keep)]])); moved += len(mv)
        if add:
            v = F.string(CAS, lkey); lt = rows(v)[0][0].split("\n")
            lt += [x for x in add if x not in lt]
            F.set_string(CAS, lkey, leaf(v, [["\n".join(lt)]]))
    F.log(f"队长前置能力行的文字移到队长技：{moved} 行")

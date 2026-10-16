import sys, os
from base149 import *
OLD = r"D:/WF/_archive/startpoint-cn-old/repo/mod-tools"
sys.path.insert(0, OLD)
import wf_cursed_weapons as W
ws = W.weapons()
SOUL = load("master/ability/ability_soul.orderedmap"); EA = load("master/equipment_enhancement/equipment_enhancement_ability.orderedmap")
EQ = load("master/item/equipment.orderedmap")
for w in ws:
    soul = [W.build_row(W.SOUL_T, i, e) for i, e in enumerate(w.soul)]
    ea = [W.build_row(W.EA_T, i, e) for i, e in enumerate(w.ea)]
    ks = rows(SOUL.get(w.id, '')); ke = rows(EA.get(w.id, ''))
    ks = [r for r in ks if r]; ke = [r for r in ke if r]
    eqname = row(EQ[w.id])[1] if w.id in EQ else None
    print(w.row, w.id, w.name, eqname, 'soul', soul == ks, len(soul), len(ks), 'ea', ea == ke, len(ea), len(ke))

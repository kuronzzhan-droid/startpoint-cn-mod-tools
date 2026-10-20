# -*- coding: utf-8 -*-
"""1.4.245 view: store131 + kpr-1.4.245 active zips (from>=1.4.131) in (from,to,seq) order."""
import os, re, sys
from pathlib import Path
ACT = Path(r"D:/WF/kpr-1.4.245/assets/asset-patch/active")
RX = re.compile(r"^pinball-(\d+)\.(\d+)\.(\d+)-(\d+)\.(\d+)\.(\d+)-(\d+)-.*\.zip$")
zs = []
for n in os.listdir(ACT):
    m = RX.match(n)
    if not m or 'candidate' in n: continue
    g = tuple(int(x) for x in m.groups())
    if g[3:6] >= (1, 4, 131):
        zs.append((g, ACT / n))
zs.sort()
os.environ["WF_TIP"] = "131"
os.environ["WF_EXTRA_ZIPS"] = ";".join([str(p) for _, p in zs] + [x for x in os.environ.get("WF_MORE", "").split(";") if x])
ZIPS = [p.name for _, p in zs]
BUILD = Path(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
sys.path.insert(0, str(BUILD))
_cwd = os.getcwd(); os.chdir(BUILD)
from live149 import *  # noqa
import wf_dsl  # noqa
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_describe as D  # noqa
from layout import col, name_of  # noqa
os.chdir(_cwd)
AB = "master/ability/ability.orderedmap"
LE = "master/ability/leader_ability.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
AS = "master/skill/action_skill.orderedmap"
TX = "master/character/character_text.orderedmap"
UQ = "master/character/unique_condition.orderedmap"
CH = "master/character/character.orderedmap"

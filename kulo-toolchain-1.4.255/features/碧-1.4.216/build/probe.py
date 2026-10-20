import env; env.setup(212)
from base149 import *
from base149 import _INDEX, _ZIPS
print(len(_ZIPS), _ZIPS[-1].name)
for lp in ["master/character/character.orderedmap","master/character/character_text.orderedmap"]:
    t=load(lp); print(lp, source(lp), '169978' in t, str(t.get('169978'))[:300])

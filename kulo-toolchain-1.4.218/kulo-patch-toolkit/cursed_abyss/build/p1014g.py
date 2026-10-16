import os,sys,json
os.environ["WF_TIP"]="197"
from live149 import *
CAS=load('master/string/custom_ability_string.orderedmap'); U=load('master/character/unique_condition.orderedmap')
for k,v in CAS.items():
    if any(s in v for s in ('豹步','70倍','6.5%','＋300%','CT：1秒','狮咬','基础伤害','巨蜥')) or 'outlaw_panther_moon' in k or 'land_dragon_wind' in k or 'kyle_moon' in k:
        print('CAS',repr(k),repr(v[:400]))
for k in ('13999011','13999012','13999102','11999001','1199960','1199969'): print('U',k,U.get(k))

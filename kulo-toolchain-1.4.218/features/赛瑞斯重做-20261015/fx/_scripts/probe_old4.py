exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
for d,n in [("battle/effect/skill_unique/seris_human_royal_tide_ring","seris_human_royal_tide_ring"),("battle/effect/skill_unique/seris_dragon_frozen_thunder_breath","seris_dragon_frozen_thunder_breath"),("battle/effect/skill_unique/seris_dragon_flight","seris_dragon_flight")]:
    t,_=amf(f"{d}/{n}.parts.amf3.deflate"); print(n,"t",t['t'],"g0t",t['g'][0]['t'],"segs",t['g'][0]['s'][:3],"i0",t['i'][0])
    at,_=amf(f"{d}/{d.split('/')[-1]}.atlas.amf3.deflate"); print("  atlas0",at[0])

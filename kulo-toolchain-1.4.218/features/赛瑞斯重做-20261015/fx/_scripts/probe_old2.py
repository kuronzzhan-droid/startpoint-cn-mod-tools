exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
import hashlib
for d in ["battle/effect/skill_unique/seris_dragon_king","battle/uncommon/layer1/seris_dragon_king"]:
    dn=d.split('/')[-1]
    at,src=amf(f"{d}/{dn}.atlas.amf3.deflate"); print(d,src,[a['n'] for a in at[:5]], at[0])
    raw,_=read_raw(f"{d}/{dn}.png"); print(hashlib.sha1(raw).hexdigest(), member(f"{d}/{dn}.png"))

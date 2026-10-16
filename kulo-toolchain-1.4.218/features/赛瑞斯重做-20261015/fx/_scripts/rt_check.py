exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
for lp in ["battle/effect/skill_unique/seris_human_royal_tide_ring/seris_human_royal_tide_ring.parts.amf3.deflate","battle/effect/skill_unique/seris_human_royal_tide_ring/seris_human_royal_tide_ring.timeline.amf3.deflate","battle/effect/skill_unique/seris_human_royal_tide_ring/seris_human_royal_tide_ring.atlas.amf3.deflate","battle/effect/powerflip/effect_powerflip_attack_special/powerflip_attack_special_three.parts.amf3.deflate"]:
    raw,_=read_raw(lp); dec=zlib.decompress(raw,-15); t=wf_dsl.parse_dsl(dec)['tree']; enc=wf_dsl.encode_amf3(t)
    print(lp.split('/')[-1], enc==dec, len(enc),len(dec), raw[:2].hex())

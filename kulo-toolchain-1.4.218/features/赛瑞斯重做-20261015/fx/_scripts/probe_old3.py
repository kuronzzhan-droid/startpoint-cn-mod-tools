exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
for d in ["battle/effect/powerflip/seris_human_shooting_powerflip","battle/effect/powerflip/seris_dragon_special_powerflip","battle/effect/powerflip/effect_powerflip_attack_special","battle/effect/powerflip/effect_powerflip_attack_beam","character/seris_dragon_king/pixelart"]:
    dn=d.split('/')[-1]
    fn = f"{d}/{dn}.png" if 'pixelart' not in d else f"{d}/sprite_sheet.png"
    try: im,src=png(fn); print(d,im.size,src)
    except Exception as e: print(d,"miss",e)

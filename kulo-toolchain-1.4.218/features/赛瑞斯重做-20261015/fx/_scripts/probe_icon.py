exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
for n in ["unique_seris_dragon_king","unique_zeta","unique_girl_and_mecha","unique_ginovi"]:
    lp=f"battle/common/unique_condition/{n}.png"
    try:
        im,src=png(lp); print(n,im.size,im.mode,src); im.save(f"icon_{n}.png")
    except Exception as e: print(n,"miss",type(e).__name__)

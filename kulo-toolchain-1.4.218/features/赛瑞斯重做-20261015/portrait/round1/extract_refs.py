import os, sys
os.environ.setdefault("WF_TIP", "206")
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
os.chdir(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from base149 import *
OUT = r"D:/WF/out/赛瑞斯重做-20261015/portrait/round1/refs"
for code in ["seris_dragon_king", "ice_dragon", "wind_dragon"]:
    for n in (0, 1):
        p = f"character/{code}/ui/full_shot_1440_1920_{n}.png"
        try:
            raw, _ = read_raw(p)
        except Exception as e:
            print("MISS", p, e); continue
        b = bytearray(raw)
        if b[1:4] != b"PNG": b[1:4] = b"PNG"
        fn = os.path.join(OUT, f"{code}_{n}.png")
        open(fn, "wb").write(b); print("ok", fn, len(b))

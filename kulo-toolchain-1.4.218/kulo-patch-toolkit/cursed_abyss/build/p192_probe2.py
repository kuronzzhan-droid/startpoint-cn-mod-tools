import os, hashlib, zipfile; os.environ["WF_TIP"]="191"
from live149 import *
import base149
IDS={"149999":"white_wolf_gerald","129992":"unicorn_lancer_rose","149986":"black_wolf_knight_moon"}
for lp in ("master/generated/character_image.orderedmap","master/generated/trimmed_image.orderedmap","master/character/full_shot_image_attribute.orderedmap"):
    raw,src=read_raw(lp); t=q.parse_node(raw)
    rt = q.build_node(t)
    print(lp, "roundtrip_bytes_equal", rt==raw, len(raw), len(rt))
    if "trimmed" in lp:
        for c in IDS.values():
            for s in (0,1):
                k=f"character/{c}/ui/full_shot_1440_1920_{s}"; print(" ",k, repr(t.get(k)))
    else:
        for i in IDS: print(" ",i, repr(t.get(i)))
# asset index across roots
ROOTS=("upload","medium_upload","android_upload")
IDX={}
for z in base149._ZIPS:
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist(): IDX[n]=z
def h(lp): d=hashlib.sha1((lp+SALT).encode()).hexdigest(); return d[:2]+"/"+d[2:]
names=["full_shot_1440_1920_{n}.png","square_{n}.png","square_132_132_{n}.png","square_round_136_136_{n}.png","square_round_95_95_{n}.png","thumb_level_up_{n}.png","thumb_party_main_{n}.png","thumb_party_unison_{n}.png","battle_member_status_{n}.png","battle_control_board_{n}.png","cutin_skill_chain_{n}.png","skill_cutin_{n}.png","skill_cutin_{n}.atf","skill_cutin_{n}.atf.deflate","illustration_setting_sprite_sheet.png","illustration_setting_sprite_sheet.atlas","illustration_setting_sprite_sheet.atf","illustration_setting_sprite_sheet.json","illustration_setting_sprite_sheet.xml"]
for c in IDS.values():
    print("==",c)
    for nm in names:
        for n in (0,1):
            lp=f"character/{c}/ui/"+nm.format(n=n)
            for r in ROOTS:
                m=f"production/{r}/"+h(lp)
                src = IDX[m].name if m in IDX else ("store131" if (base149.SCR/"store131"/m).exists() else None)
                if src: print("  ",lp,r,src)
            if "{n}" not in nm: break

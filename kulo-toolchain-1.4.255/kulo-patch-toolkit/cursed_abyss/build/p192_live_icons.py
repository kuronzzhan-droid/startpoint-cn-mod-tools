from p192_common import *
import numpy as np, sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_ui_derive_gate as gate
NM=["square","square_132_132","square_round_136_136","square_round_95_95","thumb_level_up","thumb_party_main","thumb_party_unison","battle_member_status","battle_control_board","cutin_skill_chain","skill_cutin"]
out = ART/"inspect"/"live"; out.mkdir(exist_ok=True)
for f,cid,code,s in SLOTS:
    icons={}
    for nm in NM:
        lp=f"character/{code}/ui/{nm}_{s}.png"; rs=roots_of(lp)
        raws={r:aread(r,lp)[0] for r in rs}
        same = len(set(hashlib.sha256(v).hexdigest() for v in raws.values()))==1
        im=png_img(raws["medium_upload"]); icons[nm]=np.asarray(im)
        im.save(out/f"{code}_{nm}_{s}.png")
        print(code,s,nm,im.size,rs,"same" if same else "DIFF", round(gate.coverage(np.asarray(im)),3))
    print("  gate:", gate.derived_icon_problems(icons, None, level=str(s)))

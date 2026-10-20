# -*- coding: utf-8 -*-
"""水杰拉德包自检：wf_midautumn_verify（store 指向 1.4.238 视图）。用法：python wg_verify.py"""
import sys, json
import wg_env
import wf_midautumn_verify as V
for name in dir(V):
    obj = getattr(V, name)
    if isinstance(obj, type) and isinstance(getattr(obj, "store", None), property):
        setattr(obj, "store", property(lambda self: wg_env.STORE))
# 本包主位限定行一律用同台座图集的主位标副本 wfx_main（与 any_element 同纹理；同行混 scene/general 的 main
# 会让第二个图标画花，真机 1.4.239 实证），门禁按这个标记核对「每行都带主位标」。
V.MAIN_ICON_TAG = "<icon id='wfx_main'>"
rc = {}
for k in ("aqua",):
    ws = wg_env.ROOT / "work" / "character_packs" / f"wg-{k}"
    out = wg_env.OUT / "patch" / f"verify-{k}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        rc[k] = V.main(["--workspace", str(ws), "--skip-atlas", "--pixel-freeform", "--out", str(out), "--root", str(wg_env.ROOT)])
    except SystemExit as e:
        rc[k] = e.code
    except Exception as e:
        rc[k] = repr(e)[:300]
print(rc)

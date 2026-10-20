# -*- coding: utf-8 -*-
"""水杰拉德:环境(路径、mod-tools 导入、1.4.238 视图 store)。"""
import os, sys
from pathlib import Path
HW = Path(__file__).resolve().parent
OUT = HW.parent
ROOT = OUT / "pkgroot"                     # 包工作区根(work/character_packs/hw-<key>)
STORE = OUT / "viewstore" / "production" / "upload"   # 1.4.238 视图物化 store
MODTOOLS = Path(r"D:/WF/startpoint-cn-wiki/mod-tools")
SERVER_BASE = Path(r"D:/WF/startpoint-cn-kulo/assets")
os.environ["WF_TARGET_STORE"] = STORE.as_posix()
for p in (str(HW), str(MODTOOLS)):
    if p not in sys.path:
        sys.path.insert(0, p)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

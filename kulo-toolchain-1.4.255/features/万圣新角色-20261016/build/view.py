# -*- coding: utf-8 -*-
"""万圣四角色:测试服 1.4.220 视图(store131 + active 131-206 + rel1016/219/220 zips)。只读。"""
import os, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
os.environ["WF_TIP"] = "206"
os.environ["WF_EXTRA_ZIPS"] = ";".join(l.strip() for l in (HERE / "extra_zips.txt").read_text("utf-8").splitlines() if l.strip())
BUILD = Path(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
sys.path.insert(0, str(BUILD))
os.chdir(BUILD)
from live149 import *  # noqa

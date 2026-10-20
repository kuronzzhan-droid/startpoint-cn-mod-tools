# -*- coding: utf-8 -*-
"""重打 1.4.220→1.4.221 包并装进本线程自己的本地服副本（localsrv/），可重跑。
服务端文件从 server-backup/ 原件重新追加；manifest 用备份原件重新追加 220/221 两条。"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import hw_env

OUT = hw_env.OUT
L = OUT / "localsrv"
ACT = L / "assets" / "asset-patch" / "active"
import os
FRM, TO = os.environ.get("HW_FRM", "1.4.220"), os.environ.get("HW_TO", "1.4.221")
KEEP = [x for x in os.environ.get("HW_KEEP", "").split(";") if x]   # 之前本地边的 manifest-entry 文件


def main():
    for z in (OUT / "patch").glob(f"pinball-{FRM}-{TO}-*"):
        z.unlink()
    subprocess.check_call([sys.executable, str(hw_env.HW / "hw_pack.py"), FRM, TO])
    for z in ACT.glob(f"pinball-{FRM}-{TO}-*.zip"):
        z.unlink()
    for z in (OUT / "patch").glob(f"pinball-{FRM}-{TO}-*.zip"):
        shutil.copy2(z, ACT / z.name)
    bk = OUT / "server-backup"
    m = json.loads((bk / "manifest.json").read_text("utf-8"))
    for f in (Path(r"D:/WF/out/灰分享包-20261016/交付/manifest-entry-align-1.4.220.json"),
              *[Path(x) for x in KEEP], OUT / "patch" / f"manifest-entry-{TO}.json"):
        m["patches"].append(json.loads(f.read_text("utf-8")))
    m["cdn_version"] = TO
    s = json.dumps(m, ensure_ascii=False, indent=2) + "\n"
    (L / "assets" / "asset-patch" / "manifest.json").write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
    for p in bk.rglob("*.json"):
        if p.name == "manifest.json":
            continue
        shutil.copy2(p, L / "assets" / p.relative_to(bk))
    subprocess.check_call([sys.executable, str(hw_env.HW / "hw_server.py"), str(L / "assets"), str(L / "assets")])
    subprocess.check_call([sys.executable, str(hw_env.HW / "hw_server.py"), "--entries", str(OUT / "patch" / "server-entries.json")])
    print("installed", TO)


if __name__ == "__main__":
    main()

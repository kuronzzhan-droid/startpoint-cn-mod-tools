# -*- coding: utf-8 -*-
"""部署前/后断言（盒子服务端根目录）：python assert_box.py <服务端根> [--after]
前：manifest 尾 = 1.4.224、尚无 1.4.225；交付 zip sha256 对。
后：manifest 尾 = 1.4.225、前一条 1.4.224、条目与交付一致；active 下 zip sha 对。服务端 json 无改动。"""
import hashlib, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1]); AFTER = "--after" in sys.argv
entry = json.loads((HERE / "manifest-entry-1.4.225.json").read_text("utf-8"))
z = entry["archive"]; want = entry["archive_integrity"][0]["sha256"]
m = json.loads((ROOT / "assets/asset-patch/manifest.json").read_text("utf-8"))
ok = True
def check(c, msg):
    global ok
    print(("OK  " if c else "FAIL") + " " + msg); ok &= bool(c)
src = (ROOT / "assets/asset-patch/active" / z) if AFTER else (HERE / z)
check(src.is_file() and hashlib.sha256(src.read_bytes()).hexdigest() == want, f"zip sha {z}")
tail = m["patches"][-1]["version"]
if AFTER:
    check(tail == "1.4.225", f"manifest 尾 {tail}")
    got = m["patches"][-1]
    check(got["chain"] == entry["chain"] and got["archive_integrity"] == entry["archive_integrity"], "225 条目与交付一致")
    check(m["patches"][-2]["version"] == "1.4.224", "225 前一条是 224")
else:
    check(tail == "1.4.224", f"manifest 尾 {tail}")
    check(all(p["version"] != "1.4.225" for p in m["patches"]), "盒子尚无 1.4.225")
print("ALL OK" if ok else "HAS FAIL"); sys.exit(0 if ok else 1)

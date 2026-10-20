"""把赛瑞斯 1.4.209 接到某个本地服的补丁链上（拷 5 个 zip 到 active/ + 在 manifest 末尾追加条目 + cdn_version=1.4.209）。
用法: python apply-209-to-localsrv.py <localsrv 根目录> [--write]   不带 --write 只检查不写。
前置：该本地服 manifest 链尾必须是 1.4.208，且 208 的 sha 与 209 构建时一致（f637b427…）。"""
import hashlib, json, shutil, sys
from pathlib import Path
root = Path(sys.argv[1]); write = "--write" in sys.argv
here = Path(__file__).resolve().parent
patch = here.parent / "patch"
entry = json.loads((here / "manifest-entry-1.4.209.json").read_text("utf-8"))
mp = root / "assets/asset-patch/manifest.json"; act = root / "assets/asset-patch/active"
m = json.loads(mp.read_text("utf-8-sig"))
tail = m["patches"][-1]
assert tail["version"] == "1.4.208", f"chain tail is {tail['version']}, expected 1.4.208"
z8 = act / tail["archive"]
assert hashlib.sha256(z8.read_bytes()).hexdigest().startswith("f637b427"), "208 differs from the one 209 was built on; rebuild 209 first"
for ai in entry["archive_integrity"]:
    src = patch / ai["name"]
    assert hashlib.sha256(src.read_bytes()).hexdigest() == ai["sha256"], ai["name"]
print("checks OK; 5 zips + entry ready")
if write:
    for ai in entry["archive_integrity"]:
        shutil.copy2(patch / ai["name"], act / ai["name"])
    m["patches"] = [p for p in m["patches"] if p["version"] != "1.4.209"] + [entry]
    m["cdn_version"] = "1.4.209"
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print("written:", mp)

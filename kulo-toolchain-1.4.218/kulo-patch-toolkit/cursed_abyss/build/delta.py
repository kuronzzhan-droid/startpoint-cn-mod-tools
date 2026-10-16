# -*- coding: utf-8 -*-
"""1.4.150 → 1.4.151 增量包：全量重建（CA_STAGE_DIR=../full151）后，只收与已安装 1.4.150 zip 不同的成员。

用法：CA_STAGE_DIR=<scratch>/cursed_abyss/full151 python stage_all.py && python delta.py
产物：../patch/pinball-1.4.150-1.4.151-1-cursed-r4-fix-local.zip + .integrity.json；服务端有变化才写 ../server2/
"""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
FULL = OUT / "full151"
OLD = OUT / "patch" / "pinball-1.4.149-1.4.150-1-cursed-r4-abyss2-local.zip"
NEW_FULL = next((FULL / "patch").glob("*.zip"))
NAME = "pinball-1.4.150-1.4.151-1-cursed-r4-fix-local.zip"


def main() -> int:
    old_integ = json.loads(OLD.with_name(OLD.stem + ".integrity.json").read_text("utf-8"))
    new_integ = json.loads(NEW_FULL.with_name(NEW_FULL.stem + ".integrity.json").read_text("utf-8"))
    with zipfile.ZipFile(OLD) as zo, zipfile.ZipFile(NEW_FULL) as zn:
        old = {n: zo.read(n) for n in zo.namelist()}
        new = {n: zn.read(n) for n in zn.namelist()}
    assert set(old) <= set(new), "全量重建少了 1.4.150 的成员"
    diff = {n: d for n, d in new.items() if old.get(n) != d}
    lps = {**old_integ["logical_paths"], **new_integ["logical_paths"]}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n in sorted(diff):
            z.writestr(n, diff[n])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(diff),
             "files": sorted(diff), "member_sha256": {n: hashlib.sha256(diff[n]).hexdigest() for n in sorted(diff)},
             "logical_paths": {n: lps[n] for n in sorted(diff)}, "applies_on": "1.4.150", "version": "1.4.151"}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    # 服务端：与 1.4.150 交付的 server/ 比较，变化才写 server2/
    s2 = OUT / "server2"
    if s2.exists():
        shutil.rmtree(s2)
    changed = []
    for f in sorted((FULL / "server").glob("*.json")):
        prev = OUT / "server" / f.name
        if not prev.exists() or prev.read_bytes() != f.read_bytes():
            s2.mkdir(exist_ok=True)
            shutil.copy2(f, s2 / f.name)
            changed.append(f.name)
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members", "logical_paths")} | {"server_changed": changed},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

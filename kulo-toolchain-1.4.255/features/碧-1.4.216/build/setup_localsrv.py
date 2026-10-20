# -*- coding: utf-8 -*-
"""碧本地验证服:从 SRC localsrv 复制独立副本,叠碧的包+服务端条目。用法: python setup_localsrv.py <SRC localsrv> <patch dir> <TIP>"""
import os, sys, shutil, json, _winapi, subprocess
from pathlib import Path
SRC, PD, TIP = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
TO = TIP + 1
HERE = Path(__file__).resolve().parent
DST = HERE.parent / f"localsrv-{TO}"
assert not DST.exists(), DST
DST.mkdir()
for d in ("src", "out", "data", "config", "web", "admin", "scripts", ".database", "tests"):
    if (SRC / d).exists(): shutil.copytree(SRC / d, DST / d)
(DST / ".logs").mkdir()
for d in (".cdn", "node_modules", "tools", "client-patch", "docs", "deployment", "tmp"):
    p = SRC / d
    if os.path.lexists(p): _winapi.CreateJunction(os.path.realpath(p), str(DST / d))
for f in SRC.iterdir():
    if f.is_file(): shutil.copy2(f, DST / f.name)
(DST / "assets").mkdir()
for f in (SRC / "assets").iterdir():
    if f.is_file(): shutil.copy2(f, DST / "assets" / f.name)
for d in ("asset_lists", "cdndata", "gacha-movie-variants", "gacha_movie_configs"):
    shutil.copytree(SRC / "assets" / d, DST / "assets" / d)
ap = DST / "assets" / "asset-patch"; (ap / "active").mkdir(parents=True)
for f in (SRC / "assets" / "asset-patch").iterdir():
    if f.is_file(): shutil.copy2(f, ap / f.name)
for d in ("artwork", "audit", "dev-catalog"):
    p = SRC / "assets" / "asset-patch" / d
    if os.path.lexists(p): _winapi.CreateJunction(os.path.realpath(p), str(ap / d))
for f in (SRC / "assets" / "asset-patch" / "active").iterdir(): os.link(f, ap / "active" / f.name)
# 先补中间边(PRE_ZIPS=分号分隔 zip 路径,按版本顺序)与它们的服务端文件(PRE_SERVER=src=>dst;...)
mp = ap / "manifest.json"
for zp in filter(None, os.environ.get("PRE_ZIPS", "").split(";")):
    zp = Path(zp); integ = json.loads(zp.with_name(zp.stem + ".integrity.json").read_text("utf-8")); import zipfile, hashlib; integ["files"] = sorted(n for n in zipfile.ZipFile(zp).namelist() if not n.endswith("/")); assert hashlib.sha256(zp.read_bytes()).hexdigest() == integ["sha256"], zp
    shutil.copy2(zp, ap / "active" / zp.name)
    mraw = mp.read_bytes().decode("utf-8"); m = json.loads(mraw)
    v = integ.get("version") or "1.4." + zp.name.split("-1.4.")[1].split("-")[0]
    prev = m["patches"][-1]["version"]
    m["patches"].append({"id": zp.stem, "type": "patch", "name": "(本地) " + zp.stem, "description": "本地测试用", "version": v, "depends_on": prev,
        "enabled": True, "local_test_only": True, "archive": zp.name, "archive_size": zp.stat().st_size, "chain": [zp.name], "files": integ["files"],
        "archive_integrity": [{"name": zp.name, "size": zp.stat().st_size, "sha256": integ["sha256"], "members": len(integ["files"]), "files": integ["files"]}], "created_at": "2026-10-16"})
    m["cdn_version"] = v
    s2 = json.dumps(m, ensure_ascii=False, indent=2) + "\n"
    mp.write_bytes((s2.replace("\n", "\r\n") if "\r\n" in mraw else s2).encode("utf-8")); print("pre", v, zp.name)
for pair in filter(None, os.environ.get("PRE_SERVER", "").split(";")):
    a, b = pair.split("=>"); shutil.copy2(a, DST / b); print("pre-server", b)
SRC_ASSETS = DST / "assets"
# 服务端条目
subprocess.check_call([sys.executable, str(HERE / "build_server.py"), str(SRC_ASSETS), str(DST / "assets")])
for rel, old, new in (("src/lib/character-degree-catalog.ts", "    159995, 159994, 169991, 169988,\n", "    159995, 159994, 169991, 169988, 169978,\n"),
                      ("src/lib/character-degree-catalog.ts", "    [169988, [9_910_085, 9_910_086]],\n", "    [169988, [9_910_085, 9_910_086]],\n    [169978, [9_910_090, 9_910_091]],\n"),
                      ("out/lib/character-degree-catalog.js", "    159995, 159994, 169991, 169988,\n", "    159995, 159994, 169991, 169988, 169978,\n"),
                      ("out/lib/character-degree-catalog.js", "    [169988, [9910085, 9910086]],\n", "    [169988, [9910085, 9910086]],\n    [169978, [9910090, 9910091]],\n")):
    p = DST / rel; b = p.read_bytes().decode("utf-8"); crlf = "\r\n" in b
    o, n = (old.replace("\n", "\r\n"), new.replace("\n", "\r\n")) if crlf else (old, new)
    assert b.count(o) == 1, (rel, old); p.write_bytes(b.replace(o, n).encode("utf-8"))
# 包 + 清单
zips = sorted(PD.glob(f"pinball-1.4.{TIP}-1.4.{TO}-*-vyrn-character-local.zip"))
ints = [json.loads(z.with_name(z.stem + ".integrity.json").read_text("utf-8")) for z in zips]
for z in zips: shutil.copy2(z, ap / "active" / z.name)
mraw = mp.read_bytes().decode("utf-8")
m = json.loads(mraw); assert m["patches"][-1]["version"] == f"1.4.{TIP}", m["patches"][-1]["version"]
entry = {"id": f"vyrn-character-1.4.{TO}", "type": "patch", "name": "(本地) 碧 169978 角色+称号(灰 1.4.135 重切)",
         "description": "本地测试用，不提交", "version": f"1.4.{TO}", "depends_on": f"1.4.{TIP}", "enabled": True, "local_test_only": True,
         "archive": zips[0].name, "archive_size": ints[0]["size"], "chain": [z.name for z in zips],
         "files": sorted({f for i in ints for f in i["files"]}),
         "archive_integrity": [{k: i[k] for k in ("name", "size", "sha256", "members", "files")} for i in ints], "created_at": "2026-10-16"}
m["patches"].append(entry); m["cdn_version"] = f"1.4.{TO}"
s = json.dumps(m, ensure_ascii=False, indent=2) + "\n"
mp.write_bytes((s.replace("\n", "\r\n") if "\r\n" in mraw else s).encode("utf-8"))
json.dump(entry, open(HERE.parent / f"manifest-entry-1.4.{TO}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("done", DST, [z.name for z in zips])

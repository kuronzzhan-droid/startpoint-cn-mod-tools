# -*- coding: utf-8 -*-
"""凉月修复本地验证服:从十项收尾 localsrv(已到 1.4.212)复制独立副本;不写 kulo 工作区、不动源副本。
套上本次改动:mana_node/mana_board(盒子底 + 凉月修正)、character-overlimit.ts(盒子底 + ★4 结晶校验)。"""
import os, shutil, _winapi
from pathlib import Path

SRC = Path(r"D:/WF/out/十项收尾-20261015/localsrv")
HERE = Path(__file__).resolve().parent
DST = HERE / "localsrv"
assert not DST.exists(), DST
DST.mkdir()
for d in ("src", "out", "data", "config", "web", "admin", "scripts", ".database", "tests"):
    if (SRC / d).exists():
        shutil.copytree(SRC / d, DST / d)
(DST / ".logs").mkdir()


def target(p):
    return os.path.realpath(p)


for d in (".cdn", "node_modules", "tools", "client-patch", "docs", "deployment", "tmp"):
    p = SRC / d
    if os.path.lexists(p):
        _winapi.CreateJunction(target(p), str(DST / d))
for f in SRC.iterdir():
    if f.is_file():
        shutil.copy2(f, DST / f.name)
(DST / "assets").mkdir()
for f in (SRC / "assets").iterdir():
    if f.is_file():
        shutil.copy2(f, DST / "assets" / f.name)
for d in ("asset_lists", "cdndata", "gacha-movie-variants", "gacha_movie_configs"):
    shutil.copytree(SRC / "assets" / d, DST / "assets" / d)
ap = DST / "assets" / "asset-patch"
(ap / "active").mkdir(parents=True)
for f in (SRC / "assets" / "asset-patch").iterdir():
    if f.is_file():
        shutil.copy2(f, ap / f.name)
for d in ("artwork", "audit", "dev-catalog"):
    p = SRC / "assets" / "asset-patch" / d
    if os.path.lexists(p):
        _winapi.CreateJunction(target(p), str(ap / d))
for f in (SRC / "assets" / "asset-patch" / "active").iterdir():
    os.link(f, ap / "active" / f.name)
# 本次改动
for name in ("mana_node.json", "mana_board.json"):
    shutil.copy2(HERE / "server" / "assets" / name, DST / "assets" / name)
shutil.copy2(HERE / "server" / "src" / "lib" / "character-overlimit.ts", DST / "src" / "lib" / "character-overlimit.ts")
print("done", DST)

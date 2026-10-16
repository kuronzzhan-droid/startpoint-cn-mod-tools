# -*- coding: utf-8 -*-
"""portrait192 共用：1.4.191 live 视图下的多根资产读取。"""
import os, hashlib, zipfile, io
os.environ.setdefault("WF_TIP", "191")
from live149 import *  # noqa
import base149
from PIL import Image
MASTERS = Path(r"D:/WF/out/立绘重设计-20261008/定稿候选/母图")
ART = Path(__file__).resolve().parent.parent / "art" / "portrait192"
SLOTS = [  # (master file, cid, code, slot)
    ("杰拉德-觉醒前-ZL2.png", "149999", "white_wolf_gerald", 0),
    ("杰拉尔-觉醒前-V2.png", "129992", "unicorn_lancer_rose", 0),
    ("歌狼-觉醒前-ZB3.png", "149986", "black_wolf_knight_moon", 0),
    ("歌狼-觉醒后-Y3.png", "149986", "black_wolf_knight_moon", 1),
]
ROOTS = ("upload", "medium_upload", "android_upload")
_IDX = {}
for z in base149._ZIPS:
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist(): _IDX[n] = z
def digest(lp):
    d = hashlib.sha1((lp + SALT).encode()).hexdigest(); return d[:2] + "/" + d[2:]
def amember(root, lp):
    return f"production/{root}/{digest(lp)}"
def aread(root, lp):
    m = amember(root, lp)
    if m in _IDX:
        with zipfile.ZipFile(_IDX[m]) as zf: return zf.read(m), _IDX[m].name
    p = base149.SCR / "store131" / m
    if p.exists(): return p.read_bytes(), "store131"
    return None, None
def roots_of(lp):
    return [r for r in ROOTS if aread(r, lp)[0] is not None]
def png_img(raw):
    if raw[:8] == bytes([137,112,110,103,13,10,26,10]): raw = bytes([137,80,78,71,13,10,26,10]) + raw[8:]
    return Image.open(io.BytesIO(raw)).convert("RGBA")

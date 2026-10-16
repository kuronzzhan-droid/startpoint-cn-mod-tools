# -*- coding: utf-8 -*-
import os, sys, zlib, io
os.environ.setdefault('WF_TIP', '206')
sys.stdout.reconfigure(encoding='utf-8')
B = r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build"
sys.path.insert(0, B)
os.chdir(B)
from base149 import *  # noqa
sys.path.insert(0, r"D:\WF\startpoint-cn\mod-tools")
import wf_mod_tool as core
from PIL import Image
SR = r"C:/Users/12101/AppData/Local/Temp/claude/D--WF-startpoint-cn/f2e9136e-af15-453a-964a-6378d8ac3859/scratchpad/sr"
os.chdir(SR)

OUT = r"D:/WF/out/赛瑞斯重做-20261015/pixel/official_mother"

def raw(logical):
    try:
        return read_raw(logical)[0]
    except Exception:
        return None

def png(logical):
    b = raw(logical)
    if b is None: return None
    b = bytearray(b)
    if b[1:4] == b'png': b[1:4] = b'PNG'
    return Image.open(io.BytesIO(bytes(b))).convert('RGBA')

def amf(logical):
    b = raw(logical)
    if b is None: return None
    for blob in (b, b[4:]):
        for w in (15, -15):
            try:
                return core.AMF3Reader(zlib.decompress(blob, w)).read_value()
            except Exception:
                pass
    raise RuntimeError('amf fail ' + logical)

def charlist():
    import live149
    return live149.flat('master/character/character.orderedmap')

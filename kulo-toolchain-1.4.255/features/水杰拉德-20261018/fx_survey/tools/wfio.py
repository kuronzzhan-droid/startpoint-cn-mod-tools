# -*- coding: utf-8 -*-
"""Read-only helpers: logical path -> bytes (wf-decrypted first, store fallback)."""
import sys, os, io, json, zlib, hashlib
from pathlib import Path
sys.path.insert(0, r"D:/WF/air-platform-20261017/tools/fantasy-gauntlet-mod-tools")
import wf_mod_tool as core

SALT = "K6R9T9Hz22OpeIGEWB0ui6c6PYFQnJGy"
DEC = Path(r"D:/WF/resources/game/wf-decrypted")
UNNAMED = [DEC / "_unnamed" / "upload", DEC / "_unnamed" / "medium_upload"]
STORES = [Path(r"D:/WF/resources/game/wf-assets/upload"),
          Path(r"D:/WF/out/kulo-patch-toolkit/store131/production/upload"),
          Path(r"D:/WF/out/kulo-patch-toolkit/store131/production/medium_upload")]

def h(lp):
    return hashlib.sha1((lp + SALT).encode("utf-8")).hexdigest()

def unnamed_path(lp, ext):
    d = h(lp)
    for r in UNNAMED:
        p = r / d[:2] / (d[2:] + ext)
        if p.exists():
            return p
    return None

def store_path(lp):
    d = h(lp)
    for r in STORES:
        p = r / d[:2] / d[2:]
        if p.exists():
            return p
    return None

def read_store(lp):
    p = store_path(lp)
    return p.read_bytes() if p else None

def amf_decode(blob):
    for b in (blob, blob[4:]):
        for wb in (-15, 15):
            try:
                raw = zlib.decompress(b, wb)
            except Exception:
                continue
            try:
                return core.AMF3Reader(raw).read_value()
            except Exception:
                continue
    raise ValueError("amf decode failed")

def load_amf(lp_noext_suffix):
    """lp like battle/effect/.../x.parts -> json from wf-decrypted or store amf."""
    j = DEC / (lp_noext_suffix + ".json")
    if j.exists():
        return json.loads(j.read_text(encoding="utf-8")), "dec"
    u = unnamed_path(lp_noext_suffix + ".amf3.deflate", ".json")
    if u is not None:
        return json.loads(u.read_text(encoding="utf-8")), "dec_unnamed"
    b = read_store(lp_noext_suffix + ".amf3.deflate")
    if b is None:
        return None, None
    return amf_decode(b), "store"

def png_fix(b):
    if b[1:4] == b"png":
        b = b[:1] + b"PNG" + b[4:]
    return b

def load_png(lp):
    from PIL import Image
    p = DEC / lp
    if p.exists():
        return Image.open(io.BytesIO(png_fix(p.read_bytes()))).convert("RGBA"), "dec"
    u = unnamed_path(lp, ".png")
    if u is not None:
        return Image.open(io.BytesIO(png_fix(u.read_bytes()))).convert("RGBA"), "dec_unnamed"
    b = read_store(lp)
    if b is None:
        return None, None
    return Image.open(io.BytesIO(png_fix(b))).convert("RGBA"), "store"

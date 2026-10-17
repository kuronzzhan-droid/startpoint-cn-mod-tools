# -*- coding: utf-8 -*-
"""校园奈芙提姆候选包原语；只读生产素材，写入角色候选目录。"""
from __future__ import annotations

import csv as _csv
import hashlib
import io
import json
import os
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] if '.worktrees' in str(Path(__file__).resolve()) else Path(__file__).resolve().parents[1]
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402
import wf_assets  # noqa: E402

STORE = ROOT / "弹国服/WorldFlipper/dummy/download/production/upload"
STORE_MEDIUM = ROOT / "弹国服/WorldFlipper/dummy/download/production/medium_upload"
STORE_ANDROID = ROOT / "弹国服/WorldFlipper/dummy/download/production/android_upload"
STORES = {"common": STORE, "medium": STORE_MEDIUM, "android": STORE_ANDROID}
PACKS = ROOT / "work/character_packs"

CID = 169989
CODE = "ruin_girl_campus"
PKG_ID = "campus-nephtim-20260911"
TMPL_ID = 151001
TMPL_CODE = "ruin_girl"
ELEMENT = 5
ELEMENT_TOKEN = "Black"
RARITY = 5
WS = PACKS / PKG_ID
PKG = WS / "package"
EVIDENCE = WS / "evidence"
def addr(logical: str, store: Path = STORE) -> Path:
    h = hashlib.sha1((logical + core.SALT).encode("utf-8")).hexdigest()
    return store / h[:2] / h[2:]


def store_read(logical: str, store: Path = STORE) -> bytes:
    return addr(logical, store).read_bytes()


def store_has(logical: str, store: Path = STORE) -> bool:
    return addr(logical, store).is_file()


def load_flat(logical: str, store: Path = STORE):
    om = core.load_table(logical, store)
    return list(om.keys), om.text_rows()


def flat_rows_raw(logical: str, store: Path = STORE):
    om = core.read_orderedmap_file_raw_rows(addr(logical, store), logical)
    return list(om.keys), list(om.rows)


def csv_split(text: str):
    return core.read_csv_lines(text)


def csv_join(rows) -> str:
    return core.write_csv_lines(rows).rstrip("\n")


def pkg_path(root: str, logical: str) -> Path:
    return PKG / "roots" / root / Path(*logical.split("/"))


def write_pkg(root: str, logical: str, data: bytes) -> Path:
    p = pkg_path(root, logical)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png_open(raw: bytes):
    from PIL import Image
    return Image.open(io.BytesIO(wf_assets.PNG_REAL + raw[8:])).convert("RGBA")


def png_store_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    raw = buf.getvalue()
    return wf_assets.PNG_FAKE + raw[8:]


def amf_read(logical: str, store: Path = STORE):
    import wf_dsl
    return wf_dsl.parse_dsl(zlib.decompress(store_read(logical, store), -15))["tree"]


def amf_bytes(tree) -> bytes:
    """单一 compressobj —— 两个对象会造坏流（parse IndexError）。"""
    import wf_dsl
    return zlib.compress(wf_dsl.encode_amf3(tree), 9)[2:-4]

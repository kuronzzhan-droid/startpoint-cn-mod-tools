"""Shared prepush report and layered read-only view."""
from __future__ import annotations

import argparse
import csv
import functools
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import wf_quest_lib as q  # noqa: E402  (parse_node / SALT,无 store 副作用)

ROOTS = ("upload", "medium_upload", "android_upload")
ARCHIVE_RE = re.compile(r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-(\d+)-.*\.zip$")
# 早期包(如 1.4.70 mode15final70)成员不带 production/<root>/ 前缀,按 upload 根落地,照样合法
MEMBER_RE = re.compile(
    r"^(production/(upload|medium_upload|android_upload|ios_upload|small_upload)/)?[0-9a-f]{2}/[0-9a-f]{38}$")
NODE_MARK = "@@WF_PREPUSH_CHAIN@@"


def vkey(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def archive_key(name: str):
    m = ARCHIVE_RE.match(name)
    if not m:
        return None
    return vkey(m.group(1)), vkey(m.group(2)), int(m.group(3))


def digest(logical: str) -> str:
    return hashlib.sha1((logical + q.SALT).encode("utf-8")).hexdigest()


def member(root: str, logical: str) -> str:
    d = digest(logical)
    return f"production/{root}/{d[:2]}/{d[2:]}"


def row(text: str) -> list[str]:
    return next(csv.reader([text]), [])


def rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text, newline="")))


def is_stub(raw: bytes) -> bool:
    """store 里的 16 字节桩:键数为 0 的空 orderedmap,真表打包在 APK 里(曲线表等)。"""
    if len(raw) > 64 or len(raw) < 8:
        return False
    ilen = struct.unpack_from("<I", raw, 0)[0]
    if ilen <= 0 or 4 + ilen != len(raw):
        return False
    try:
        index = zlib.decompress(raw[4:])
    except zlib.error:
        return False
    return len(index) >= 4 and struct.unpack_from("<I", index, 0)[0] == 0


# ---------------------------------------------------------------- 发现

@dataclass
class Finding:
    level: str          # ERROR / WARN / INFO
    check: str          # chain / text / companion / level
    fid: str            # 稳定 id,allowlist 用
    msg: str
    detail: list[str] = field(default_factory=list)


class Report:
    def __init__(self, allow: set[str]):
        self.items: list[Finding] = []
        self.allow = allow
        self.notes: list[str] = []

    def add(self, level, check, fid, msg, detail=None):
        if fid in self.allow and level == "ERROR":
            level = "WARN"
            msg += "(allowlist 降级)"
        self.items.append(Finding(level, check, fid, msg, list(detail or [])))

    def count(self, level):
        return sum(1 for f in self.items if f.level == level)


# ---------------------------------------------------------------- 视图

class View:
    """基础 store + zip 链(后者覆盖),按逻辑路径读字节/解析表。"""

    def __init__(self, zips: list[Path], base: Path | None):
        self.zips = list(zips)
        self.base = base
        self.index: dict[str, Path] = {}
        for z in self.zips:
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    self.index[n] = z
        self._zf: dict[Path, zipfile.ZipFile] = {}
        self.stubs: set[str] = set()
        self.broken: dict[str, str] = {}

    def _open(self, z: Path) -> zipfile.ZipFile:
        if z not in self._zf:
            self._zf[z] = zipfile.ZipFile(z)
        return self._zf[z]

    def _base_file(self, m: str) -> Path | None:
        if self.base is None:
            return None
        _, root, a, b = m.split("/")
        if (self.base / "upload").is_dir():          # 给的是 production 目录
            p = self.base / root / a / b
        elif root == "upload":                        # 给的是 upload 目录本身
            p = self.base / a / b
        else:
            return None
        return p if p.is_file() else None

    def raw(self, logical: str, roots=ROOTS) -> bytes | None:
        for r in roots:
            m = member(r, logical)
            if m in self.index:
                return self._open(self.index[m]).read(m)
            p = self._base_file(m)
            if p is not None:
                return p.read_bytes()
        return None

    def source(self, logical: str) -> str | None:
        m = member("upload", logical)
        if m in self.index:
            return self.index[m].name
        return "base" if self._base_file(m) else None

    @functools.lru_cache(maxsize=None)
    def table(self, logical: str):
        """解析好的表;不在视图、APK 内置桩、解不开时返回 None(后两种记进 stubs/broken)。"""
        raw = self.raw(logical, ("upload",))
        if raw is None:
            return None
        if is_stub(raw):
            self.stubs.add(logical)
            return None
        try:
            node = q.parse_node(raw)
        except Exception as exc:  # noqa: BLE001
            self.broken[logical] = str(exc)
            return None
        return node if isinstance(node, dict) else None


def list_chain(active: Path, upto: tuple[int, ...] | None = None) -> list[Path]:
    out = []
    for p in active.glob("*.zip"):
        k = archive_key(p.name)
        if k is None:
            continue
        if upto is not None and k[1] > upto:
            continue
        out.append((k, p.name, p))
    return [p for _, _, p in sorted(out)]



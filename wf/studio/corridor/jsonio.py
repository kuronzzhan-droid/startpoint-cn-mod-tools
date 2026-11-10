"""Byte-faithful JSON helpers: detect a file's serialization style and reproduce it."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Style:
    indent: int | None = 2
    ensure_ascii: bool = False
    sort_keys: bool = False
    newline: str = "\n"        # line separator inside the document
    trailing: bool = True      # a final newline after the closing bracket
    bom: bool = False


DEFAULT_STYLE = Style()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse(raw: bytes):
    return json.loads(raw.decode("utf-8-sig"))


def dumps(value, style: Style = DEFAULT_STYLE) -> bytes:
    text = json.dumps(value, ensure_ascii=style.ensure_ascii, indent=style.indent, sort_keys=style.sort_keys)
    if style.trailing:
        text += "\n"
    if style.newline != "\n":
        text = text.replace("\n", style.newline)
    return (b"\xef\xbb\xbf" if style.bom else b"") + text.encode("utf-8")


def detect_style(raw: bytes, value=None) -> Style:
    """The first candidate style that reproduces ``raw`` exactly; otherwise a close guess."""
    value = parse(raw) if value is None else value
    bom = raw.startswith(b"\xef\xbb\xbf")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    trailing = raw.rstrip(b"\r\n") != raw
    for indent in (2, 1, 4, None):
        for sort_keys in (False, True):
            for ensure_ascii in (False, True):
                style = Style(indent, ensure_ascii, sort_keys, newline, trailing, bom)
                if dumps(value, style) == raw:
                    return style
    return Style(2, False, False, newline, trailing, bom)


def canonical(value) -> str:
    """Order-sensitive identity (key order matters for byte reuse)."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def digest(value) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json(path: Path, value) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")


def read_json(path: Path):
    return parse(path.read_bytes())


def same_number_shape(old, new):
    """Keep the stored representation when a client round-trip turned 1.0 into 1 (no spurious diff)."""
    if isinstance(old, bool) or isinstance(new, bool):
        return new
    if isinstance(old, (int, float)) and isinstance(new, (int, float)):
        return old if old == new else new
    if isinstance(old, dict) and isinstance(new, dict):
        order = list(old) if set(old) == set(new) else list(new)  # keep the stored key order too
        return {k: same_number_shape(old[k], new[k]) if k in old else new[k] for k in order}
    if isinstance(old, list) and isinstance(new, list):
        return [same_number_shape(old[i], v) if i < len(old) else v for i, v in enumerate(new)]
    return new

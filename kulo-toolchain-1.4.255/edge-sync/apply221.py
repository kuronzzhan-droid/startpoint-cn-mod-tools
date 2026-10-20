"""Append the 1.4.221 Halloween server entries to kulo assets by key, preserving file style.

usage: python apply221.py <server-entries.json> <assets dir>
Refuses if a target key already exists or a file does not round-trip byte-identically.
"""
import json
import sys
from pathlib import Path

entries = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assets = Path(sys.argv[2])


def dumps(obj, crlf, trailing_nl):
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    if trailing_nl:
        text += "\n"
    return text.replace("\n", "\r\n") if crlf else text


for rel, adds in entries.items():
    path = assets / rel
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    bom = raw.startswith(b"\xef\xbb\xbf")
    crlf = "\r\n" in text
    trailing = text.endswith("\n")
    data = json.loads(text)
    if dumps(data, crlf, trailing) != text:
        sys.exit(f"{rel}: does not round-trip; refusing")
    clash = [k for k in adds if k in data]
    if clash:
        sys.exit(f"{rel}: keys already present {clash}")
    if isinstance(data, list):
        sys.exit(f"{rel}: unexpected list root")
    data.update(adds)
    out = dumps(data, crlf, trailing).encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + out)
    print(f"{rel}: +{len(adds)} keys")

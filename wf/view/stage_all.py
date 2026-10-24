"""Shared staging primitives extracted from the historical cursed/abyss builder.

The delivery-specific main program is retained in archive/legacy.
"""
import csv
import io
import json
from PIL import Image

SOUL_TINT = (44, 204, 254)

def csv_text(rows: list[list[str]]) -> str:
    s = io.StringIO(newline="")
    csv.writer(s, lineterminator="\n").writerows(rows)
    return s.getvalue()


def png_cdn(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.convert("RGBA").save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return b"\x89png" + data[4:]


def soul_icon(im: Image.Image) -> Image.Image:
    px = im.convert("RGBA").load()
    out = Image.new("RGBA", im.size)
    po = out.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            po[x, y] = tuple(int(round(c * 0.7 + t * 0.3)) for c, t in zip((r, g, b), SOUL_TINT)) + (a,) if a else (0, 0, 0, 0)
    return out


def detect_style(text: str) -> dict:
    indent = None
    for line in text.splitlines()[1:6]:
        stripped = line.lstrip(" ")
        if stripped and len(line) != len(stripped):
            indent = len(line) - len(stripped)
            break
    if indent is None and "\n" in text.strip():
        indent = 0
    separators = (", ", ": ") if indent is None else (",", ": ")
    if indent is None and '":' in text and '": ' not in text:
        separators = (",", ":")
    return {"indent": indent, "separators": separators, "trailing": text[len(text.rstrip()):]}


def dump_like(value, style: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=style["indent"], separators=style["separators"]) + style["trailing"]

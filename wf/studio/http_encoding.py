"""Bounded, content-keyed gzip representations for large text responses."""
from __future__ import annotations

import gzip
from functools import lru_cache


def accepts_gzip(header: str) -> bool:
    qualities = {}
    for item in header.lower().split(","):
        parts = [part.strip() for part in item.split(";")]
        quality = 1.0
        for parameter in parts[1:]:
            if parameter.startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        qualities[parts[0]] = quality
    return qualities.get("gzip", qualities.get("*", 0.0)) > 0


@lru_cache(maxsize=16)
def _compressed(body: bytes) -> bytes:
    return gzip.compress(body, compresslevel=5, mtime=0)


def representation(body: bytes, content_type: str, accept_encoding: str):
    """Return bytes, encoding and whether the response varies by encoding."""
    eligible = len(body) >= 1024 and (
        content_type.startswith("text/") or content_type.split(";", 1)[0] in {
            "application/json", "application/javascript", "image/svg+xml"})
    if not eligible or not accepts_gzip(accept_encoding):
        return body, None, eligible
    # Bound retained memory, including pathological responses outside normal API sizes.
    encoded = _compressed(body) if len(body) <= 8 * 1024 * 1024 else gzip.compress(body, compresslevel=5, mtime=0)
    if len(encoded) >= len(body):
        return body, None, True
    return encoded, "gzip", True

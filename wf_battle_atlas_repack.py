#!/usr/bin/env python3
"""Deterministically repack battle atlases without changing rendered frames.

The repacker only moves complete atlas rectangles.  It deliberately does not
trim individual frames, alter frame metadata, rotate rectangles, resample
pixels, or deduplicate different regions.  A two-pixel leading gutter on every
packed rectangle preserves the spacing convention used by the source sheets.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import zlib
from dataclasses import dataclass
from typing import Iterable

from PIL import Image, ImageChops

import wf_assets
import wf_dsl


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True, slots=True)
class RepackResult:
    png_payload: bytes
    atlas_payload: bytes
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    record_count: int
    unique_region_count: int
    content_signature: str
    source_area: int
    output_area: int
    region_area: int
    placements: dict[tuple[int, int, int, int], tuple[int, int]]


def decode_png(payload: bytes) -> Image.Image:
    with Image.open(io.BytesIO(wf_assets.png_decode(payload))) as source:
        return source.convert("RGBA")


def encode_png(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG", optimize=True, compress_level=9)
    return wf_assets.png_encode(stream.getvalue())


def decode_atlas(payload: bytes) -> list[dict]:
    tree = wf_dsl.parse_dsl(zlib.decompress(payload, -15))["tree"]
    if not isinstance(tree, list) or not all(isinstance(record, dict) for record in tree):
        raise ValueError("atlas root must be a list of records")
    return tree


def encode_atlas(records: list[dict]) -> bytes:
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    raw = wf_dsl.encode_amf3(records)
    return compressor.compress(raw) + compressor.flush()


def _region(record: dict) -> Rect:
    missing = [key for key in ("x", "y", "w", "h") if key not in record]
    if missing:
        raise ValueError(f"atlas record is missing {missing}: {record!r}")
    values = tuple(record[key] for key in ("x", "y", "w", "h"))
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        raise ValueError(f"atlas rectangle must use integers: {record!r}")
    rect = Rect(*values)
    if min(rect.x, rect.y) < 0 or min(rect.w, rect.h) <= 0:
        raise ValueError(f"invalid atlas rectangle: {rect}")
    return rect


def _unique_regions(records: Iterable[dict]) -> list[Rect]:
    seen: set[Rect] = set()
    result: list[Rect] = []
    for record in records:
        rect = _region(record)
        if rect not in seen:
            seen.add(rect)
            result.append(rect)
    return result


def _intersects(left: Rect, right: Rect) -> bool:
    return not (
        left.x + left.w <= right.x
        or right.x + right.w <= left.x
        or left.y + left.h <= right.y
        or right.y + right.h <= left.y
    )


def _contains(outer: Rect, inner: Rect) -> bool:
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and outer.x + outer.w >= inner.x + inner.w
        and outer.y + outer.h >= inner.y + inner.h
    )


def _validate_source(image: Image.Image, records: list[dict]) -> list[Rect]:
    regions = _unique_regions(records)
    width, height = image.size
    for rect in regions:
        if rect.x + rect.w > width or rect.y + rect.h > height:
            raise ValueError(f"atlas rectangle falls outside source sheet: {rect} vs {image.size}")
    for index, left in enumerate(regions):
        for right in regions[index + 1 :]:
            if _intersects(left, right):
                raise ValueError(f"different atlas rectangles overlap: {left} vs {right}")

    covered = Image.new("L", image.size, 0)
    for rect in regions:
        covered.paste(255, (rect.x, rect.y, rect.x + rect.w, rect.y + rect.h))
    outside_alpha = ImageChops.multiply(image.getchannel("A"), ImageChops.invert(covered))
    if outside_alpha.getbbox() is not None:
        raise ValueError("source sheet contains non-transparent pixels outside atlas rectangles")
    return regions


def _split_free_rect(free: Rect, used: Rect) -> list[Rect]:
    if not _intersects(free, used):
        return [free]
    result: list[Rect] = []
    if used.x > free.x:
        result.append(Rect(free.x, free.y, used.x - free.x, free.h))
    if used.x + used.w < free.x + free.w:
        result.append(
            Rect(used.x + used.w, free.y, free.x + free.w - used.x - used.w, free.h)
        )
    if used.y > free.y:
        result.append(Rect(free.x, free.y, free.w, used.y - free.y))
    if used.y + used.h < free.y + free.h:
        result.append(
            Rect(free.x, used.y + used.h, free.w, free.y + free.h - used.y - used.h)
        )
    return [rect for rect in result if rect.w > 0 and rect.h > 0]


def _prune_free_rects(rectangles: list[Rect]) -> list[Rect]:
    unique = list(dict.fromkeys(rectangles))
    result: list[Rect] = []
    for rect in unique:
        if any(candidate != rect and _contains(candidate, rect) for candidate in unique):
            continue
        result.append(rect)
    return result


def _sort_regions(regions: list[Rect], mode: str) -> list[Rect]:
    if mode == "height":
        key = lambda rect: (-rect.h, -rect.w, rect.y, rect.x)
    elif mode == "area":
        key = lambda rect: (-rect.w * rect.h, -max(rect.w, rect.h), -rect.h, -rect.w, rect.y, rect.x)
    else:
        raise ValueError(f"unsupported packing sort mode: {mode}")
    return sorted(regions, key=key)


def pack_regions(
    regions: list[Rect],
    *,
    target_width: int,
    max_height: int = 2048,
    gap: int = 2,
    sort_mode: str = "height",
) -> tuple[dict[Rect, Rect], tuple[int, int]]:
    """Pack whole regions with a deterministic MaxRects short-side heuristic."""
    if target_width <= 0 or max_height <= 0 or gap < 0:
        raise ValueError("target dimensions and gap must be valid")
    free = [Rect(0, 0, target_width, max_height)]
    placed: dict[Rect, Rect] = {}
    for source in _sort_regions(regions, sort_mode):
        padded_w = source.w + gap
        padded_h = source.h + gap
        candidates: list[tuple[tuple[int, int, int, int], Rect]] = []
        for slot in free:
            if padded_w <= slot.w and padded_h <= slot.h:
                leftover_w = slot.w - padded_w
                leftover_h = slot.h - padded_h
                score = (min(leftover_w, leftover_h), max(leftover_w, leftover_h), slot.y, slot.x)
                candidates.append((score, Rect(slot.x, slot.y, padded_w, padded_h)))
        if not candidates:
            raise ValueError(
                f"region {source.w}x{source.h} does not fit {target_width}x{max_height}"
            )
        used = min(candidates, key=lambda item: item[0])[1]
        placed[source] = Rect(used.x + gap, used.y + gap, source.w, source.h)
        split: list[Rect] = []
        for slot in free:
            split.extend(_split_free_rect(slot, used))
        free = _prune_free_rects(split)

    output_width = max((rect.x + rect.w for rect in placed.values()), default=0)
    output_height = max((rect.y + rect.h for rect in placed.values()), default=0)
    return placed, (output_width, output_height)


def content_signature(image: Image.Image, records: list[dict]) -> str:
    """Hash ordered frame semantics while ignoring atlas x/y placement."""
    digest = hashlib.sha256()
    for record in records:
        rect = _region(record)
        metadata = {key: value for key, value in record.items() if key not in {"x", "y"}}
        digest.update(
            json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\0")
        digest.update(image.crop((rect.x, rect.y, rect.x + rect.w, rect.y + rect.h)).tobytes())
    return digest.hexdigest()


def repack_atlas(
    png_payload: bytes,
    atlas_payload: bytes,
    *,
    target_width: int,
    expected_height: int | None = None,
    max_height: int = 2048,
    gap: int = 2,
    sort_mode: str = "height",
) -> RepackResult:
    source_image = decode_png(png_payload)
    source_records = decode_atlas(atlas_payload)
    regions = _validate_source(source_image, source_records)
    source_signature = content_signature(source_image, source_records)

    placements, output_size = pack_regions(
        regions,
        target_width=target_width,
        max_height=max_height,
        gap=gap,
        sort_mode=sort_mode,
    )
    if output_size[0] != target_width:
        raise ValueError(f"packed width {output_size[0]} does not equal target width {target_width}")
    if expected_height is not None and output_size[1] != expected_height:
        raise ValueError(
            f"packed height {output_size[1]} does not equal expected height {expected_height}"
        )

    output_image = Image.new("RGBA", output_size, (0, 0, 0, 0))
    for source, target in placements.items():
        frame = source_image.crop(
            (source.x, source.y, source.x + source.w, source.y + source.h)
        )
        output_image.paste(frame, (target.x, target.y))

    output_records = copy.deepcopy(source_records)
    for record in output_records:
        source = _region(record)
        target = placements[source]
        record["x"] = target.x
        record["y"] = target.y

    # The source and output record sequences must differ only in placement.
    for before, after in zip(source_records, output_records, strict=True):
        if {key: value for key, value in before.items() if key not in {"x", "y"}} != {
            key: value for key, value in after.items() if key not in {"x", "y"}
        }:
            raise AssertionError("atlas metadata changed during repack")
    output_signature = content_signature(output_image, output_records)
    if output_signature != source_signature:
        raise AssertionError("frame pixels or atlas semantics changed during repack")
    _validate_source(output_image, output_records)

    return RepackResult(
        png_payload=encode_png(output_image),
        atlas_payload=encode_atlas(output_records),
        source_size=source_image.size,
        output_size=output_size,
        record_count=len(source_records),
        unique_region_count=len(regions),
        content_signature=source_signature,
        source_area=source_image.width * source_image.height,
        output_area=output_image.width * output_image.height,
        region_area=sum(region.w * region.h for region in regions),
        placements={
            (source.x, source.y, source.w, source.h): (target.x, target.y)
            for source, target in placements.items()
        },
    )

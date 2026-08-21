#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a small Flatomo flipbook effect from fixed-size RGBA PNG frames.

The compiler returns logical asset paths mapped to their encoded store bytes.
It does not write a store, package, CDN, or device by itself.
"""
from __future__ import annotations

import io
import re
import zlib
from pathlib import Path
from typing import Iterable

from PIL import Image

import wf_assets
import wf_dsl


_GUTTER = 1
_COLUMNS = 5
_LOGICAL_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_TRAVELLING_WAVE_ROOT = (
    "battle/effect/skill_unique/"
    "cnmod_thunder_dragon_ascendant/fan_lightning"
)


def _raw_deflate(data: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(data) + compressor.flush()


def _validate_component(value: str, label: str) -> str:
    if not _LOGICAL_COMPONENT.fullmatch(value):
        raise ValueError(f"{label} must be one safe logical path component")
    return value


def _validate_root(value: str) -> str:
    root = value
    if (
        not root
        or any(not _LOGICAL_COMPONENT.fullmatch(part) for part in root.split("/"))
    ):
        raise ValueError("effect_root must be a normalized relative logical path")
    return root


def _load_frames(frame_paths: Iterable[Path | str]) -> list[Image.Image]:
    frames: list[Image.Image] = []
    expected_size: tuple[int, int] | None = None
    for raw_path in frame_paths:
        path = Path(raw_path)
        with Image.open(path) as source:
            frame = source.convert("RGBA")
        if frame.getchannel("A").getbbox() is None:
            raise ValueError(f"frame is fully transparent: {path}")
        if expected_size is None:
            expected_size = frame.size
        elif frame.size != expected_size:
            raise ValueError(
                f"all frames must have the same size: {path} is {frame.size}, "
                f"expected {expected_size}"
            )
        frames.append(frame)
    if not frames:
        raise ValueError("at least one frame is required")
    return frames


def _encode_png(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    return wf_assets.png_encode(stream.getvalue())


def compile_flipbook_effect(
    frame_paths: Iterable[Path | str],
    *,
    effect_root: str,
    texture_name: str,
    effect_name: str,
    repetitions: int = 1,
    frame_origin: tuple[int, int] | None = None,
) -> dict[str, bytes]:
    """Compile frames into one texture/atlas and one Flatomo parts/timeline pair."""
    root = _validate_root(effect_root)
    texture = _validate_component(texture_name, "texture_name")
    effect = _validate_component(effect_name, "effect_name")
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")

    frames = _load_frames(frame_paths)
    frame_width, frame_height = frames[0].size
    if frame_origin is None:
        origin_x, origin_y = frame_width // 2, frame_height // 2
    else:
        origin_x, origin_y = frame_origin
        if (
            isinstance(origin_x, bool)
            or isinstance(origin_y, bool)
            or not isinstance(origin_x, int)
            or not isinstance(origin_y, int)
            or not 0 <= origin_x <= frame_width
            or not 0 <= origin_y <= frame_height
        ):
            raise ValueError("frame_origin must be an integer point inside the frame")
    rows = (len(frames) + _COLUMNS - 1) // _COLUMNS
    cell_width = frame_width + 2 * _GUTTER
    cell_height = frame_height + 2 * _GUTTER
    sheet = Image.new(
        "RGBA",
        (_COLUMNS * cell_width, rows * cell_height),
        (0, 0, 0, 0),
    )

    atlas = []
    images = []
    for index, frame in enumerate(frames):
        column = index % _COLUMNS
        row = index // _COLUMNS
        x = column * cell_width + _GUTTER
        y = row * cell_height + _GUTTER
        sheet.alpha_composite(frame, (x, y))
        generated_path = f"{root}/.gen/{effect}/f{index:02d}"
        atlas.append(
            {
                "n": generated_path,
                "w": frame_width,
                "h": frame_height,
                "x": x,
                "y": y,
            }
        )
        images.append({"s": False, "p": generated_path})

    wave_ticks = len(frames) + 1
    visible_ticks = len(frames) * repetitions
    root_segments = [
        {
            "s": float(-2147483648 + start),
            "i": 1,
            "l": [{"m": 255, "t": wave_ticks, "r": 1073741824.0}],
        }
        for start in range(0, visible_ticks, len(frames))
    ]
    wave_segments = [
        {"s": index, "i": index, "l": [{"m": 4351}]}
        for index in range(len(frames))
    ]
    parts = {
        "i": images,
        "g": [
            {"t": visible_ticks + 1, "s": root_segments},
            {"t": wave_ticks, "s": wave_segments},
        ],
        "m": [],
        "a": [1] * len(frames),
        "o": [],
        "t": [
            {
                "a": 4096,
                "b": 0,
                "c": 0,
                "d": 4096,
                "x": 0,
                "y": 0,
            },
            {
                "a": 4096,
                "b": 0,
                "c": 0,
                "d": 4096,
                "x": -origin_x * 4096,
                "y": -origin_y * 4096,
            }
        ],
        "c": [],
        "s": 1,
    }
    timeline = {
        "sequences": [
            {
                "begin": 1,
                "end": visible_ticks + 1,
                "name": "neutral",
                "kind": "once",
            }
        ],
        "sounds": [],
        "points": [],
        "circles": [],
        "rectangles": [],
        "matrices": [],
    }

    return {
        f"{root}/{texture}.png": _encode_png(sheet),
        f"{root}/{texture}.atlas.amf3.deflate": _raw_deflate(
            wf_dsl.encode_amf3(atlas)
        ),
        f"{root}/{effect}.parts.amf3.deflate": _raw_deflate(
            wf_dsl.encode_amf3(parts)
        ),
        f"{root}/{effect}.timeline.amf3.deflate": _raw_deflate(
            wf_dsl.encode_amf3(timeline)
        ),
    }


def compile_travelling_wave_effect(
    frame_paths: Iterable[Path | str],
) -> dict[str, bytes]:
    """Compile the locked 10-frame summer thunder-dragon travelling wave."""
    paths = [Path(path) for path in frame_paths]
    if len(paths) != 10:
        raise ValueError("travelling wave requires exactly 10 visible frames")
    for path in paths:
        with Image.open(path) as image:
            if image.format != "PNG" or image.size != (64, 64):
                raise ValueError(
                    f"travelling wave frame must be a 64x64 PNG: {path}"
                )
    return compile_flipbook_effect(
        paths,
        effect_root=_TRAVELLING_WAVE_ROOT,
        texture_name="fan_lightning",
        effect_name="fan_lightning_wave",
        repetitions=11,
        frame_origin=(8, 32),
    )

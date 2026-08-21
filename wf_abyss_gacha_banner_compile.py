#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SHA-locked WF-storage compiler for the two abyss-gacha banners."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from PIL import Image, UnidentifiedImageError

import wf_abyss_gacha_contract as contract
import wf_assets


SOURCE_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "abyss-gacha-banners"


@dataclass(frozen=True)
class BannerSpec:
    source_name: str
    source_sha256: str
    logical_path: str
    size: tuple[int, int]


@dataclass(frozen=True)
class BannerCompilation:
    files: Mapping[str, bytes]
    report: Mapping[str, object]


LOCKED_BANNERS = (
    BannerSpec(
        "abyss_limited_gacha_list_banner.png",
        "c27900816e3e0b896407f2ff6158c8b3f390c3a6c3bb49264956571e56d4d7db",
        contract.LIST_BANNER_PAYLOAD_LOGICAL,
        (510, 180),
    ),
    BannerSpec(
        "abyss_limited_gacha_top_banner_portrait.png",
        "07dd71a8579c64c216bbfeb4679505dd2590049dda43c528f13e3f5c9ba9b596",
        contract.TOP_BANNER_PAYLOAD_LOGICAL,
        (1440, 1789),
    ),
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_rgba(raw: bytes, label: str) -> Image.Image:
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.mode != "RGBA":
                raise ValueError(f"{label} must be RGBA; actual={image.mode}")
            return image.copy()
    except UnidentifiedImageError as exc:
        raise ValueError(f"{label} is not a valid PNG") from exc


def compile_banners(
    source_dir: Path, specs: Sequence[BannerSpec]
) -> BannerCompilation:
    """Encode explicit SHA-locked PNG sources and prove decoded pixel identity."""

    source_dir = Path(source_dir)
    names = [spec.source_name for spec in specs]
    logicals = [spec.logical_path for spec in specs]
    if (
        not specs
        or len(names) != len(set(names))
        or len(logicals) != len(set(logicals))
    ):
        raise ValueError("banner specs must have unique source names and logical paths")

    files: dict[str, bytes] = {}
    source_hashes: dict[str, str] = {}
    output_hashes: dict[str, str] = {}
    readback: dict[str, dict[str, object]] = {}
    for spec in specs:
        source = source_dir / spec.source_name
        if not source.is_file():
            raise ValueError(f"banner source is missing: {spec.source_name}")
        raw = source.read_bytes()
        actual_sha = _sha(raw)
        if actual_sha != spec.source_sha256:
            raise ValueError(
                f"banner source SHA-256 drift: {spec.source_name}; "
                f"expected={spec.source_sha256}, actual={actual_sha}"
            )
        source_image = _load_rgba(raw, spec.source_name)
        if source_image.size != spec.size:
            raise ValueError(
                f"banner source dimensions drift: {spec.source_name}; "
                f"expected={spec.size}, actual={source_image.size}"
            )
        source_pixels = source_image.tobytes()
        stored = wf_assets.png_encode(raw)
        if not stored.startswith(wf_assets.PNG_FAKE):
            raise ValueError(f"banner WF storage signature is absent: {spec.source_name}")
        decoded_raw = wf_assets.png_decode(stored)
        decoded = _load_rgba(decoded_raw, f"decoded {spec.source_name}")
        if decoded.size != spec.size or decoded.tobytes() != source_pixels:
            raise ValueError(f"banner decoded pixel readback drift: {spec.source_name}")
        files[spec.logical_path] = stored
        source_hashes[spec.source_name] = actual_sha
        output_hashes[spec.logical_path] = _sha(stored)
        readback[spec.logical_path] = {
            "width": decoded.width,
            "height": decoded.height,
            "mode": decoded.mode,
            "pixel_sha256": _sha(decoded.tobytes()),
            "decoded_png_sha256": _sha(decoded_raw),
        }

    return BannerCompilation(files, {
        "schema_version": 1,
        "status": "compiled_wf_storage_banners",
        "payload_count": len(files),
        "source_sha256": source_hashes,
        "output_sha256": output_hashes,
        "decoded_readback": readback,
        "logical_paths": sorted(files),
        "package_manifest_eligible": True,
        "writes_live": False,
        "formal_workspace_written": False,
    })


def compile_locked_banners() -> BannerCompilation:
    return compile_banners(SOURCE_ASSET_DIR, LOCKED_BANNERS)


__all__ = [
    "SOURCE_ASSET_DIR", "BannerSpec", "BannerCompilation", "LOCKED_BANNERS",
    "compile_banners", "compile_locked_banners",
]

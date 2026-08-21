#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure compiler for the summer thunder dragon's skill-preview replay.

The preview is authored as a semantic AMF3 tree.  It is not copied from a
donor asset, and this module never writes a store, package, CDN, server, or
device.
"""
from __future__ import annotations

import copy
import hashlib
import zlib

import wf_dsl
import wf_mod_tool as core


CODE_NAME = "cnmod_thunder_dragon_ascendant"
LOGICAL_PATH = (
    f"character/{CODE_NAME}/battle/"
    "character_detail_skill_preview.battle.amf3.deflate"
)

# This semantic shape is shared by 73 official CN characters in the audited
# 1.4.346 store, including thunder_dragon.  Frame 107 invokes member 0's
# action skill.  The 330-frame window leaves 52 frames after the engine's
# 60-frame skill-ready phase and this character's 111-frame travelling wave.
_PREVIEW_TREE = {
    "config": {
        "start_frame": 0,
        "end_frame": 330,
        "ball": {"x": -200, "y": -300, "vx": 0, "vy": 0},
        "hp_ratio": 1,
        "skill_gauge_ratio": 1,
        "power_flip_level": 0,
    },
    "log_parts": [
        {"f": 107, "c": [2, 0]},
        {"f": 232, "c": [13, True]},
    ],
}


def _raw_deflate(data: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(data) + compressor.flush()


def build_summer_thunder_skill_preview_tree() -> dict:
    """Return a fresh copy of the locked replay tree."""
    return copy.deepcopy(_PREVIEW_TREE)


def compile_summer_thunder_skill_preview() -> dict:
    """Compile the replay to its common-root logical path."""
    tree = build_summer_thunder_skill_preview_tree()
    encoded = wf_dsl.encode_amf3(tree)
    if core.AMF3Reader(encoded).read_value() != tree:
        raise ValueError("skill-preview AMF3 round-trip mismatch")
    payload = _raw_deflate(encoded)
    if core.AMF3Reader(zlib.decompress(payload, -15)).read_value() != tree:
        raise ValueError("skill-preview raw-deflate round-trip mismatch")

    invoke_frame = tree["log_parts"][0]["f"]
    end_frame = tree["config"]["end_frame"]
    tail = end_frame - (invoke_frame + 60 + 111)
    if tail != 52:
        raise ValueError(f"unexpected skill-preview tail: {tail}")

    return {
        "files": {LOGICAL_PATH: payload},
        "report": {
            "schema_version": 1,
            "code_name": CODE_NAME,
            "logical_path": LOGICAL_PATH,
            "root": "common",
            "start_frame": tree["config"]["start_frame"],
            "end_frame": end_frame,
            "skill_invoke_frame": invoke_frame,
            "skill_ready_frames": 60,
            "travelling_wave_frames": 111,
            "tail_frames_after_60_plus_111": tail,
            "official_semantic_precedent_count": 73,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
            "copied_donor_bytes": False,
            "writes_live": False,
            "package_manifest_eligible": True,
        },
    }


__all__ = [
    "CODE_NAME",
    "LOGICAL_PATH",
    "build_summer_thunder_skill_preview_tree",
    "compile_summer_thunder_skill_preview",
]

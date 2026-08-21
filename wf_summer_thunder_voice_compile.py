#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure voice compiler for the locked five-star summer thunder dragon.

The compiler accepts the two already-audited MP3 source mappings in memory,
requires their exact 9+8 split and SHA-256 identities, then returns game-store
bytes plus the replacement ``character_speech`` outer row.  It never reads or
writes a store, workspace, package, CDN, server, or device.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping

import wf_assets
import wf_mod_tool as core


CHARACTER_ID = 139998
CODE_NAME = "cnmod_thunder_dragon_ascendant"
CHARACTER_SPEECH_LOGICAL = "master/character/character_speech.orderedmap"

AUTHOR_CUT_RELATIVES = (
    "ally/evolution.mp3",
    "ally/join.mp3",
    "battle/power_flip_0.mp3",
    "battle/power_flip_1.mp3",
    "battle/skill_0.mp3",
    "battle/skill_1.mp3",
    "battle/skill_ready.mp3",
    "home/isekaidewa.mp3",
    "home/mukashiwa.mp3",
)

INGEST_RELATIVES = (
    "battle/battle_start_0.mp3",
    "battle/battle_start_1.mp3",
    "battle/outhole_0.mp3",
    "battle/win_0.mp3",
    "battle/win_1.mp3",
    "home/kono.mp3",
    "home/sono.mp3",
    "home/watashiwa.mp3",
)

LOCKED_VOICE_SHA256 = {
    "ally/evolution.mp3":
        "9d1b174a9c239c2e34905504ccfd3375e607a175d2215a389d85b02b6dc50a49",
    "ally/join.mp3":
        "e1361f83a4f81d948b95695ba549da7a6c9d167cdce9155542b8d60e558c15f7",
    "battle/battle_start_0.mp3":
        "ed1bf5c81388ca02358063e2c41cb186d28c3472a34d2b65ad43ef01916f2c5e",
    "battle/battle_start_1.mp3":
        "72acb4a12a660bbf65db399686b66998787c59f196b7e1b12a9590fa695551bd",
    "battle/outhole_0.mp3":
        "02fb651cca729b5650980b6ab79a5803ef079f159bdb7a0452cb6060a9dbe234",
    "battle/power_flip_0.mp3":
        "0de0a390e6ddc6a0d122a7361b675174d6632b7ea72df5d9fa305c1b8ad4391a",
    "battle/power_flip_1.mp3":
        "c64dda5e60c67c38b2cd5d369b5d36cfbd73a2a779f64163c34ee59cca4a629c",
    "battle/skill_0.mp3":
        "068529c1ba8a540305bd51290d3ac1133d10233d086f52737209c2bd7aed8cfa",
    "battle/skill_1.mp3":
        "b30d5dcf31d0714f0ae348011760355ce471ba00f4880b390918945afae741a3",
    "battle/skill_ready.mp3":
        "beaf4a9ff9952fb221677c645957f61eaad3f4a6071409b900276c74d6f414df",
    "battle/win_0.mp3":
        "fcabf8a2bd548e677cbe9e196fa4d68a28782a532d94b29a7b275c62ee0b578c",
    "battle/win_1.mp3":
        "d05eea1a52a0d2f99e146cca111f02c5ad4c63aa75bc2c24745e0ac4d485a095",
    "home/isekaidewa.mp3":
        "c6e37828566bb1caaf41537a4ad329a46d13858aba373c8d0e8bcf4f68de8cbd",
    "home/kono.mp3":
        "7e6bd007a57bbf65e954f0987521a4caf4625c6a6fb145eab277618d0bc8b79b",
    "home/mukashiwa.mp3":
        "69ec217378b4a3a85191b2bbfea425eb1d546de72c605f5b6421ccca2c1cc306",
    "home/sono.mp3":
        "e3e17de39fe6ea984f3e87d088ca0b42c58934c934909896dda17f01d89fe289",
    "home/watashiwa.mp3":
        "c83bc6e1c5d20a0a4f9543a45fd61169f953df9fbd8148416be92a5a9194e509",
}

# The author accepted these recorded-content deviations on 2026-08-15.  They
# are evidence, not encoding failures, and remain visible in every report.
KNOWN_CONTENT_DEVIATIONS = {
    "ally/evolution.mp3": "missing_clause",
    "home/mukashiwa.mp3": "missing_word",
    "battle/skill_ready.mp3": "oversized_internal_pause",
    "battle/skill_0.mp3": "no_silence_at_line_boundary",
    "battle/skill_1.mp3": "no_silence_at_line_boundary",
}


_SPEECH_ROWS = (
    (
        "0", "2", "",
        "异世界的海与天空，也充满了陌生的回响。\n"
        "旅行真是件好事啊。\n"
        "命运又描绘出了新的波澜。",
        "home/isekaidewa",
    ),
    (
        "0", "2", "",
        "过去，我曾从云端向海面降下雷霆，把鱼儿们吓得四散。\n"
        "呵呵……放心吧。\n"
        "今天只会稍微恶作剧一下。",
        "home/mukashiwa",
    ),
    (
        "0", "2", "",
        "那个游泳圈，你觉得我也能用吗？\n"
        "……呵呵，开玩笑的。\n"
        "不过让翅膀休息一下，随波漂流倒也不坏。",
        "home/sono",
    ),
    (
        "0", "1", "",
        "这片海滩的声音真悦耳。\n"
        "海浪、笑声，还有远方的雷鸣……\n"
        "当它们交叠在一起，便成了只属于夏日的歌。",
        "home/kono",
    ),
    (
        "0", "1", "",
        "我曾以为，安静的休息实在无聊。\n"
        "但若是与你们一同度过的夏日……\n"
        "就连无所事事的时光，也令人心生爱怜。",
        "home/watashiwa",
    ),
    (
        "2", "", "",
        "我是拉姆斯·恩弗利亚。\n"
        "潮声与雷鸣交相呼应的夏日……倒也不坏。\n"
        "来吧，一同尽情享受吧。",
        "ally/join",
    ),
    (
        "1", "", "1",
        "阳光与海风，都令我的雷霆更加耀眼。\n"
        "托付给你们的梦想……\n"
        "让它轰鸣至这片夏空的尽头吧。",
        "ally/evolution",
    ),
)


_BITRATE_V1 = (0, 32000, 40000, 48000, 56000, 64000, 80000, 96000,
               122000, 128000, 160000, 192000, 224000, 256000, 320000)
_BITRATE_V2 = (0, 8000, 16000, 24000, 32000, 40000, 48000, 56000,
               64000, 80000, 96000, 112000, 128000, 144000, 160000)
_SRATE_V1 = (44100, 48000, 32000)
_SRATE_V2 = (22050, 24000, 16000)
_SRATE_V25 = (11025, 12000, 8000)


def build_summer_thunder_character_speech_rows() -> list[list[str]]:
    """Return the seven locked home/ally rows; battle files use fixed names."""
    return [list(row) for row in _SPEECH_ROWS]


def patch_summer_thunder_character_speech_table(
    table_rows: Mapping[str, str],
) -> dict[str, str]:
    """Replace only outer key 139998 in a decoded flat-table mapping."""
    output: dict[str, str] = {}
    for key, value in table_rows.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError("character_speech table rows must map strings to strings")
        output[key] = value
    output[str(CHARACTER_ID)] = core.write_csv_lines(
        build_summer_thunder_character_speech_rows()
    )
    return output


def _require_exact_source(
    label: str,
    source: Mapping[str, bytes],
    required: tuple[str, ...],
) -> dict[str, bytes]:
    if not isinstance(source, Mapping):
        raise TypeError(f"{label} must be an in-memory mapping")
    actual = set(source)
    expected = set(required)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"{label} paths must match locked source split; "
            f"missing={missing}, extra={extra}"
        )
    output: dict[str, bytes] = {}
    for relative in required:
        payload = source[relative]
        if not isinstance(payload, bytes):
            raise TypeError(f"{label} payload must be bytes: {relative}")
        output[relative] = payload
    return output


def _standard_mp3_channel_modes(data: bytes) -> set[int]:
    """Return MPEG channel modes after walking the same complete frame stream.

    MPEG channel mode ``3`` is single-channel.  ``wf_assets.mp3_encode`` locks
    Layer III, constant bitrate, frame coverage, and sample rate discovery but
    intentionally permits stereo, so this character compiler adds the mono
    part of its stricter 44.1 kHz/96 kbps input contract.
    """
    position = 0
    modes: set[int] = set()
    while position + 4 <= len(data):
        if data[position:position + 3] == b"ID3":
            if position + 10 > len(data):
                raise ValueError("truncated ID3 header")
            size = 0
            for value in data[position + 6:position + 10]:
                if value & 0x80:
                    raise ValueError("invalid ID3 synchsafe size")
                size = (size << 7) | value
            position += 10 + size
            continue
        if data[position:position + 3] == b"TAG":
            position += 128
            continue
        if data[position] != 0xFF or data[position + 1] >> 5 != 7:
            raise ValueError(f"invalid MP3 frame at byte {position}")
        header = int.from_bytes(data[position:position + 4], "big")
        version = header >> 19 & 3
        layer = header >> 17 & 3
        bitrate_index = header >> 12 & 0x0F
        sample_rate_index = header >> 10 & 3
        padding = header >> 9 & 1
        if (
            version == 1
            or layer != 1
            or bitrate_index in (0, 15)
            or sample_rate_index == 3
        ):
            raise ValueError(f"unsupported MP3 frame at byte {position}")
        bitrates = _BITRATE_V1 if version == 3 else _BITRATE_V2
        sample_rates = (
            _SRATE_V1 if version == 3 else _SRATE_V2 if version == 2 else _SRATE_V25
        )
        bitrate = bitrates[bitrate_index]
        sample_rate = sample_rates[sample_rate_index]
        modes.add(header >> 6 & 3)
        position += int(144 * bitrate / sample_rate + padding + 2e-10)
    if position != len(data) or not modes:
        raise ValueError("MP3 frames do not cover the complete input")
    return modes


def compile_summer_thunder_voice_assets(
    author_cut_mp3: Mapping[str, bytes],
    ingest_mp3: Mapping[str, bytes],
) -> tuple[dict[str, bytes], dict[str, dict[str, str]], dict]:
    """Compile the exact audited 9+8 MP3 set and its speech-table patch."""
    author = _require_exact_source(
        "author_cut", author_cut_mp3, AUTHOR_CUT_RELATIVES
    )
    ingest = _require_exact_source("ingest", ingest_mp3, INGEST_RELATIVES)
    combined = {**author, **ingest}
    if set(combined) != set(LOCKED_VOICE_SHA256) or len(combined) != 17:
        raise AssertionError("locked voice source split no longer covers exactly 17 files")

    source_hashes: dict[str, str] = {}
    files: dict[str, bytes] = {}
    for relative in sorted(combined):
        payload = combined[relative]
        digest = hashlib.sha256(payload).hexdigest()
        source_hashes[relative] = digest
        if digest != LOCKED_VOICE_SHA256[relative]:
            raise ValueError(
                f"voice does not match locked SHA-256: {relative}; "
                f"expected={LOCKED_VOICE_SHA256[relative]}, actual={digest}"
            )
        if _standard_mp3_channel_modes(payload) != {3}:
            raise ValueError(f"voice is not mono: {relative}")
        stored = wf_assets.mp3_encode(payload)
        probe = wf_assets.mp3_probe(stored, 1023)
        if (
            probe["bitrates"] != {96000}
            or probe["srates"] != {44100}
            or probe["tail"] != 0
            or wf_assets.mp3_decode(stored) != payload
        ):
            raise ValueError(f"voice failed locked 96k/44.1k storage gate: {relative}")
        logical = f"character/{CODE_NAME}/voice/{relative}"
        files[logical] = stored

    speech_payload = core.write_csv_lines(
        build_summer_thunder_character_speech_rows()
    )
    tables = {
        CHARACTER_SPEECH_LOGICAL: {str(CHARACTER_ID): speech_payload},
    }
    report = {
        "schema_version": 1,
        "writes_live": False,
        "package_manifest_eligible": False,
        "reason": "isolated compiler output requires package assembly and preflight",
        "character_id": CHARACTER_ID,
        "code_name": CODE_NAME,
        "voice_count": len(files),
        "encoding_contract": {
            "codec": "MPEG Layer III",
            "sample_rate_hz": 44100,
            "channels": 1,
            "bitrate_bps": 96000,
            "constant_bitrate": True,
        },
        "source_counts": {"author_cut": len(author), "ingest": len(ingest)},
        "source_sha256": source_hashes,
        "output_sha256": {
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in files.items()
        },
        "roots": {
            "common": sorted(files),
            "medium": [],
            "android": [],
            "server": [],
        },
        "table_claim": {
            "root": "common",
            "logical_path": CHARACTER_SPEECH_LOGICAL,
            "codec_id": "flat",
            "outer_keys": [str(CHARACTER_ID)],
            "inner_keys": [],
            "semantic_claims": [],
        },
        "character_speech_sha256": hashlib.sha256(
            speech_payload.encode("utf-8")
        ).hexdigest(),
        "known_content_deviations": dict(KNOWN_CONTENT_DEVIATIONS),
    }
    return files, tables, report

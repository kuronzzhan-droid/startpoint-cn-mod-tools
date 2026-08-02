# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_assets
import wf_decrypt_all
import wf_export_assets


ID3V2 = b"ID3\x04\x00\x00\x00\x00\x00\x00"
ID3V1 = b"TAG" + (b"\x00" * 125)
MPEG1_LAYER3_HEADERS = {
    8: b"\xff\xfb\x80\x00",
    9: b"\xff\xfb\x90\x00",
}
FRAME_SIZES = {
    8: 398,  # The official MP3_BR_V1 table uses 122000 for index 8.
    9: 417,  # MPEG-1 Layer III, 128 kbps, 44.1 kHz, no padding.
}


def two_frame_mp3(
    *,
    id3v2: bool = True,
    id3v1: bool = False,
    bitrate_index: int = 9,
) -> tuple[bytes, bytes]:
    prefix = ID3V2 if id3v2 else b""
    suffix = ID3V1 if id3v1 else b""
    header = MPEG1_LAYER3_HEADERS[bitrate_index]
    frame_size = FRAME_SIZES[bitrate_index]
    clear = (
        prefix
        + header + (b"A" * (frame_size - len(header)))
        + header + (b"B" * (frame_size - len(header)))
        + suffix
    )
    obfuscated = bytearray(clear)
    for offset in (len(prefix), len(prefix) + frame_size):
        obfuscated[offset] = 0x7F
    return clear, bytes(obfuscated)


class Mp3DeobfuscationTests(unittest.TestCase):
    def assert_all_decoders_restore(self, clear: bytes, obfuscated: bytes) -> None:
        export_ext, export_output = wf_export_assets.decode(obfuscated)
        standalone_ext, standalone_output = wf_decrypt_all.decode(obfuscated)

        outputs = {
            "wf_assets": wf_assets.mp3_decode(obfuscated),
            "wf_export_assets": export_output,
            "wf_decrypt_all": standalone_output,
        }

        self.assertNotEqual(clear, obfuscated)
        self.assertEqual((".mp3", ".mp3"), (export_ext, standalone_ext))
        for name, output in outputs.items():
            with self.subTest(decoder=name):
                self.assertEqual(clear, output)
                self.assertFalse(any(
                    output[index] == 0x7F and (output[index + 1] & 0xE0) == 0xE0
                    for index in range(len(output) - 1)
                ))

    def test_decoders_restore_every_obfuscated_frame_after_id3v2(self) -> None:
        self.assert_all_decoders_restore(*two_frame_mp3())

    def test_decoders_restore_multiple_frames_without_id3v2(self) -> None:
        self.assert_all_decoders_restore(*two_frame_mp3(id3v2=False))

    def test_decoders_preserve_id3v1_after_obfuscated_frames(self) -> None:
        clear, obfuscated = two_frame_mp3(id3v2=False, id3v1=True)
        self.assert_all_decoders_restore(clear, obfuscated)
        self.assertTrue(clear.endswith(ID3V1))

    def test_bitrate_index_8_keeps_official_122000_frame_step(self) -> None:
        self.assert_all_decoders_restore(*two_frame_mp3(id3v2=False, bitrate_index=8))

    def test_clear_id3v2_mp3_returns_original_without_conversion(self) -> None:
        clear, _ = two_frame_mp3()

        with self.subTest(decoder="wf_export_assets"):
            with patch.object(
                wf_export_assets.wf_assets,
                "mp3_decode",
                side_effect=AssertionError("clear MP3 reached the copying decoder"),
            ):
                ext, output = wf_export_assets.decode(clear)
            self.assertEqual(".mp3", ext)
            self.assertIs(clear, output)
        with self.subTest(decoder="wf_decrypt_all"):
            with patch(
                "builtins.bytearray",
                side_effect=AssertionError("clear MP3 entered the copying frame walker"),
            ):
                ext, output = wf_decrypt_all.decode(clear)
            self.assertEqual(".mp3", ext)
            self.assertIs(clear, output)

    def test_mp3_gate_rejects_non_mp3_without_copying(self) -> None:
        candidates = (
            wf_export_assets.PNG_MAGIC + (b"\x00" * 32),
            b"not an mp3" + (b"\xa5" * 32),
        )

        for candidate in candidates:
            with self.subTest(decoder="wf_export_assets", candidate=candidate[:8]):
                with patch.object(
                    wf_export_assets.wf_assets,
                    "mp3_decode",
                    side_effect=AssertionError("non-MP3 reached the copying decoder"),
                ):
                    self.assertIsNone(wf_export_assets.deobf_mp3(candidate))
            with self.subTest(decoder="wf_decrypt_all", candidate=candidate[:8]):
                with patch(
                    "builtins.bytearray",
                    side_effect=AssertionError("non-MP3 entered the copying frame walker"),
                ):
                    self.assertIsNone(wf_decrypt_all.deobf_mp3(candidate))


if __name__ == "__main__":
    unittest.main()

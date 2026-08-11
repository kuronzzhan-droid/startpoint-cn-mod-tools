# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_assets


class VoiceDumpPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_cache = wf_assets._voice_vocab_cache
        wf_assets._voice_vocab_cache = None

    def tearDown(self) -> None:
        wf_assets._voice_vocab_cache = self.previous_cache

    @staticmethod
    def _write_voice(root: Path, code_name: str, category: str, filename: str) -> None:
        voice_dir = root / code_name / category
        voice_dir.mkdir(parents=True)
        (voice_dir / filename).write_bytes(b"mp3-fixture")
        (root / code_name / "voiceLines.json").write_text(
            json.dumps({f"{category}/{filename[:-4]}": filename}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_resolve_voice_dump_accepts_explicit_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ, {"WF_VOICE_DUMP": td}, clear=True
        ):
            self.assertEqual(Path(td).resolve(), wf_assets.resolve_voice_dump())

    def test_resolve_voice_dump_defaults_to_checkout_local_directory_when_unset(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                (Path(wf_assets.__file__).resolve().parent / "voice-dump").resolve(),
                wf_assets.resolve_voice_dump(),
            )

    def test_resolve_voice_dump_rejects_invalid_explicit_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "not-a-directory"
            file_path.write_bytes(b"")
            invalid_values = (
                "",
                "relative-voices",
                str(Path(td) / "missing"),
                str(file_path),
            )
            for value in invalid_values:
                with self.subTest(value=value), mock.patch.dict(
                    os.environ, {"WF_VOICE_DUMP": value}, clear=True
                ), self.assertRaisesRegex(ValueError, "WF_VOICE_DUMP"):
                    wf_assets.resolve_voice_dump()

    def test_dump_voices_observes_explicit_root_changes_without_reimport(self) -> None:
        with tempfile.TemporaryDirectory() as first_td, tempfile.TemporaryDirectory() as second_td:
            first = Path(first_td)
            second = Path(second_td)
            self._write_voice(first, "hero", "ally", "first.mp3")
            self._write_voice(second, "hero", "ally", "second.mp3")

            with mock.patch.object(wf_assets, "VOICE_DUMP", first):
                with mock.patch.dict(os.environ, {"WF_VOICE_DUMP": str(first)}, clear=True):
                    self.assertEqual(
                        [("ally", "first.mp3", "first.mp3")],
                        wf_assets.dump_voices("hero"),
                    )
                with mock.patch.dict(os.environ, {"WF_VOICE_DUMP": str(second)}, clear=True):
                    self.assertEqual(
                        [("ally", "second.mp3", "second.mp3")],
                        wf_assets.dump_voices("hero"),
                    )

    def test_voice_vocab_cache_is_bound_to_the_resolved_root(self) -> None:
        with tempfile.TemporaryDirectory() as first_td, tempfile.TemporaryDirectory() as second_td:
            first = Path(first_td)
            second = Path(second_td)
            self._write_voice(first, "first", "ally", "only-first.mp3")
            self._write_voice(second, "second", "battle", "only-second.mp3")

            with mock.patch.object(wf_assets, "VOICE_DUMP", first):
                with mock.patch.dict(os.environ, {"WF_VOICE_DUMP": str(first)}, clear=True):
                    first_vocab = wf_assets._voice_vocab()
                with mock.patch.dict(os.environ, {"WF_VOICE_DUMP": str(second)}, clear=True):
                    second_vocab = wf_assets._voice_vocab()

            self.assertIn("ally/only-first.mp3", first_vocab)
            self.assertNotIn("battle/only-second.mp3", first_vocab)
            self.assertIn("battle/only-second.mp3", second_vocab)
            self.assertNotIn("ally/only-first.mp3", second_vocab)


if __name__ == "__main__":
    unittest.main(verbosity=2)

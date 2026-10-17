"""Bounded asset downloads, fallback provenance and offline snapshot integrity."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_quest_lib as qlib
import wf_wiki_dungeons_sources as source


LOGICAL = "master/quest/boss_battle_stage_node.orderedmap"
URL = "http://example.test/patch/cn/dummy/download/production/upload"


class SourcesTests(unittest.TestCase):
    def test_url_and_logical_paths_are_scoped_and_credential_free(self):
        self.assertEqual(source.checked_gray_url(URL + "/"), URL)
        for url in ("file:///tmp/upload", URL + "?token=secret", URL.replace("example.test", "user:pass@example.test"), "http://example.test/api"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                source.checked_gray_url(url)
        for logical in ("../secret", "quest/../../secret.png", "https://other/image.png", "character/a/ui/icon.png", "quest/image.svg"):
            with self.subTest(logical=logical), self.assertRaises(ValueError):
                source.checked_logical(logical)

    def test_download_limit_covers_declared_and_streamed_size(self):
        class Response(io.BytesIO):
            headers = {}
        with self.assertRaises(ValueError):
            source.read_bounded(Response(b"12345"), 4)
        response = Response(b"a"); response.headers = {"Content-Length": "20"}
        with self.assertRaises(ValueError):
            source.read_bounded(response, 4)
        self.assertEqual(source.read_bounded(Response(b"1234"), 4), b"1234")

    def test_failed_remote_refresh_uses_explicit_local_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); store = root / "game" / "upload"
            path = store / qlib.hashed_rel(LOGICAL)
            path.parent.mkdir(parents=True); path.write_bytes(qlib.build_node({"1": "local"}))
            sources = source.DungeonSources(store, gray_url=URL, snapshot=root / "snapshot")
            with patch.object(sources, "_remote", side_effect=OSError("offline")):
                self.assertEqual(sources.table(LOGICAL), {"1": "local"})
            self.assertEqual(sources.records[LOGICAL]["origin"], "local-fallback")
            self.assertEqual(sources.source([LOGICAL])["status"], "local-snapshot")
            self.assertIn(LOGICAL, sources.errors)

    def test_snapshot_hash_and_timestamp_are_verified_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); snapshot = root / "snapshot"; store = root / "game" / "upload"
            raw = qlib.build_node({"1": "gray"}); path = snapshot / "store" / qlib.hashed_rel(LOGICAL)
            path.parent.mkdir(parents=True); path.write_bytes(raw)
            manifest = {"generator": "wf_wiki_dungeons", "errors": {"quest/other.png": "HTTP Error 404"}, "files": {LOGICAL: {
                "origin": "gray", "sha256": source.checksum(raw), "bytes": len(raw), "checkedAt": "2026-09-30T01:00:00+00:00"}}}
            (snapshot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(source.DungeonSources, "_remote", side_effect=AssertionError("network")):
                sources = source.DungeonSources(store, snapshot=snapshot)
                self.assertEqual(sources.table(LOGICAL), {"1": "gray"})
                self.assertEqual(sources.errors["quest/other.png"], "HTTP Error 404")
                self.assertEqual(sources.source([LOGICAL])["checkedAt"], "2026-09-30T01:00:00+00:00")
                sources.write_manifest()
                self.assertEqual(source.DungeonSources(store, snapshot=snapshot).table(LOGICAL), {"1": "gray"})
            path.write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "哈希"):
                source.DungeonSources(store, snapshot=snapshot).table(LOGICAL)

    def test_mixed_source_is_not_claimed_as_gray_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = source.DungeonSources(Path(tmp))
            sources.records = {"a": {"origin": "gray", "checkedAt": "2026-09-29"},
                               "b": {"origin": "local-fallback", "checkedAt": "2026-09-30"}}
            self.assertEqual(sources.source(["a", "b"])["status"], "mixed-snapshot")
            self.assertIn("本地补齐", sources.source(["a", "b"])["label"])

    def test_snapshot_inside_game_store_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                source.DungeonSources(root, snapshot=root / "snapshot", gray_url=URL)

    def test_remote_fetch_uses_only_hashed_leaf_and_isolated_store(self):
        class Response(io.BytesIO):
            headers = {}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); raw = qlib.build_node({"1": "gray"})
            sources = source.DungeonSources(root / "game", snapshot=root / "snapshot", gray_url=URL)
            with patch.object(source, "build_opener") as opener:
                opener.return_value.open.return_value = Response(raw)
                self.assertEqual(sources.table(LOGICAL), {"1": "gray"})
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual(request.full_url, URL + "/" + qlib.hashed_rel(LOGICAL))
                self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 15)
            self.assertFalse((root / "game").exists())
            self.assertTrue((root / "snapshot" / "store" / qlib.hashed_rel(LOGICAL)).is_file())

    def test_local_drift_is_detected_before_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root / qlib.hashed_rel(LOGICAL)
            path.parent.mkdir(parents=True); path.write_bytes(qlib.build_node({"1": "before"}))
            sources = source.DungeonSources(root)
            sources.table(LOGICAL)
            path.write_bytes(qlib.build_node({"1": "after"}))
            with self.assertRaises(RuntimeError):
                sources.verify_local_unchanged()


if __name__ == "__main__":
    unittest.main()

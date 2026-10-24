"""External Wiki package ownership, integrity and non-live provenance contracts."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_mod_tool as core
import wf_wiki_external_character as external
from wf_wiki_catalog_source import TABLES
from wf_wiki_external_source import PackageFiles, PackageMedia, PackageSource
from wf_wiki_media import WikiMedia, digest


def manifest(root, entries=None, claims=None):
    data = {"character_id": 159991, "code_name": external.CODE,
            "package_id": external.PACKAGE_ID, "roots": {"common": entries or []},
            "tables": claims or []}
    (root / "manifest.json").write_text(json.dumps(data), encoding="utf8")
    return data


class PackageSourceTests(unittest.TestCase):
    def test_portrait_can_be_read_from_medium_tier(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "roots/medium/portrait.png"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"declared portrait")
            data = manifest(root)
            data["roots"]["medium"] = [{"logical_path": "portrait.png",
                "sha256": digest(target.read_bytes())}]
            (root / "manifest.json").write_text(json.dumps(data), encoding="utf8")
            media = WikiMedia(root / "store", root / "output")
            scoped = PackageMedia(media, PackageFiles(root, media))
            self.assertEqual(scoped._read("portrait.png"), b"declared portrait")
            self.assertIn(target, media._sources)
            self.assertFalse(media.errors)

    def test_owned_keys_overlay_without_importing_stale_neighbors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logical = TABLES["text"]
            target = root / "roots/common" / logical
            target.parent.mkdir(parents=True)
            raw = core.build_orderedmap(core.OrderedMap(logical, ["159991", "131001"],
                [b'"Moon fox"\n', b'"Stale neighbor"\n'], target))
            target.write_bytes(raw)
            manifest(root, [{"logical_path": logical, "sha256": digest(raw)}],
                     [{"root": "common", "logical_path": logical, "outer_keys": ["159991"]}])
            media = WikiMedia(root / "store", root / "output")
            files = PackageFiles(root, media)
            source = PackageSource(root, media.store, files)
            live_rows = {"131001": [["Current neighbor"]], "10": [["Other live"]]}
            source.live = SimpleNamespace(table=Mock(return_value=live_rows))
            result = source.table("text")
            self.assertEqual(result["159991"], [["Moon fox"]])
            self.assertEqual(result["131001"], [["Current neighbor"]])
            self.assertNotIn("159991", live_rows)
            target.write_bytes(b"modified package")
            with self.assertRaisesRegex(RuntimeError, "源发生变化"):
                media.verify_sources()

    def test_integrity_and_unsafe_paths_fail_before_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            media = WikiMedia(root / "store", root / "output")
            for logical in ("../outside", "C:/outside", "bad\\outside", "/outside"):
                manifest(root, [{"logical_path": logical, "sha256": "0" * 64}])
                with self.assertRaisesRegex(ValueError, "不安全"):
                    PackageFiles(root, media)
            target = root / "roots/common/image.png"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"unexpected")
            manifest(root, [{"logical_path": "image.png", "sha256": "0" * 64}])
            with self.assertRaisesRegex(ValueError, "校验值不符"):
                PackageFiles(root, media).read("image.png")

    def test_external_counts_provenance_and_idempotence(self):
        catalog = {"characters": [], "meta": {"counts": {"total": 573, "newMod": 89},
                   "categoryCounts": {"原创与变体": 41}, "sourceHashes": {"live": "unchanged"}}}
        files = SimpleNamespace(manifest={"character_id": 159991, "code_name": external.CODE,
            "package_id": external.PACKAGE_ID}, manifest_hash="hash")
        source = Mock()
        source.table.return_value = {"159991": [[external.CODE, "", "5", "4"]]}
        character = {"id": "159991", "sources": []}
        with patch.object(external, "PackageFiles", return_value=files), \
                patch.object(external, "PackageSource", return_value=source), \
                patch.object(external, "PackageMedia"), \
                patch.object(external, "character_entry", return_value=character), \
                patch.object(external, "package_voices", return_value={"recordings": 18}):
            added = external.augment_catalog(Path("unused"), Mock(), catalog)
            self.assertEqual(len(added), 1)
            self.assertEqual(character["origin"], "灰服独立角色资料")
            self.assertIn("本机快照未含", character["editorNote"])
            self.assertEqual(catalog["meta"]["counts"], {"total": 574, "newMod": 90, "external": 1})
            self.assertEqual(catalog["meta"]["sourceHashes"], {"live": "unchanged"})
            self.assertEqual(external.augment_catalog(Path("unused"), Mock(), catalog), [])
            self.assertEqual(catalog["meta"]["counts"]["total"], 574)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import wf_character_workspace
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.errors import ReleaseError
from wf_release_v1._legacy_mapping import parse_path_map
from wf_release_v1.legacy_import import import_legacy_share


SALT = "K6R9T9Hz22OpeIGEWB0ui6c6PYFQnJGy"


def _member(name: str, raw: bytes) -> tuple[ZipInfo, bytes]:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_STORED
    info.create_system = 0
    info.external_attr = 0o100666 << 16
    return info, raw


def _hashed(logical: str) -> str:
    digest = hashlib.sha1((logical + SALT).encode("utf-8")).hexdigest()
    return f"{digest[:2]}/{digest[2:]}"


def _write_share(path: Path, payloads: dict[str, bytes]) -> bytes:
    inner_buffer = BytesIO()
    with ZipFile(inner_buffer, "w", compression=ZIP_STORED) as inner:
        for name, raw in payloads.items():
            info, value = _member(name, raw)
            inner.writestr(info, value)
    archive_raw = inner_buffer.getvalue()
    archive_name = "archive-common-diff/pinball-1.4.324-1.4.347-1-fixture.zip"
    requires = {
        "schemaVersion": 2,
        "pack": {
            "variant": "full",
            "since": "1.4.323",
            "tail": "1.4.346",
            "sourceEdges": 23,
            "anchor": {"from": "1.4.324", "to": "1.4.347"},
            "archives": [archive_name],
        },
        "enhancement": True,
        "enhancementDetail": {
            "officialBaseline": None,
            "revertedRows": 0,
            "restoredRows": 0,
            "revertedTables": [],
            "droppedEntries": [],
            "note": "fixture",
            "serverSideEnhancements": [],
        },
        "requires": {
            "serverRestart": True,
            "restartReasons": ["character table"],
            "minServerVersion": None,
            "serverFeatures": [],
            "clientPatches": [],
            "serverDataNote": "quarantined",
        },
    }
    report = {
        "variant": "full",
        "tag": "fixture",
        "pack": "wfshare-1.4.324-to-1.4.347-full",
        "entries": len(payloads),
        "summary": {
            "entries": len(payloads),
            "kept": len(payloads),
            "dropped": 0,
            "rebuilt": 0,
        },
        "outputs": [{
            "root": "common",
            "path": archive_name,
            "entries": len(payloads),
            "size": len(archive_raw),
            "sha256": hashlib.sha256(archive_raw).hexdigest(),
        }],
    }
    server_rows = canonical_json_bytes({"assets/character.json": {"179999": {"name": "罗尔夫"}}})
    members = {
        archive_name: archive_raw,
        "requires.json": canonical_json_bytes(requires),
        "report.json": canonical_json_bytes(report),
        "server-data/rolf_rows.json": server_rows,
        "server-data/apply_rows.py": b"raise RuntimeError('must never execute')\n",
    }
    with ZipFile(path, "w", compression=ZIP_STORED) as outer:
        for name, raw in members.items():
            info, value = _member(f"wfshare-fixture/{name}", raw)
            outer.writestr(info, value)
    return path.read_bytes()


class LegacyImportCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="wf-release-legacy-import-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.share = self.root / "share.zip"
        self.logical = "character/rolf/ui/full_shot.png"
        self.mapped_member = f"production/upload/{_hashed(self.logical)}"
        self.opaque_member = "production/upload/aa/" + "b" * 38
        self.original = _write_share(
            self.share,
            {self.mapped_member: b"mapped", self.opaque_member: b"opaque"},
        )

    def _mapping(self, *paths: tuple[str, str]) -> Path:
        output = self.root / "path-map.json"
        output.write_bytes(canonical_json_bytes({
            "legacyPathMapVersion": 1,
            "paths": [
                {"logicalPath": logical, "root": root}
                for root, logical in paths
            ],
        }))
        return output

    def test_import_creates_isolated_opaque_workspace_and_quarantines_scripts(self) -> None:
        output = self.root / "workspace"
        receipt = import_legacy_share(self.share, output)
        wire = receipt.to_wire()

        self.assertEqual(wire["legacyImportVersion"], 1)
        self.assertEqual(wire["mappingStatus"], "opaque")
        self.assertFalse(wire["clientPayloadEditable"])
        self.assertEqual(wire["payloadFileCount"], 2)
        self.assertEqual((output / "source.wfshare.zip").read_bytes(), self.original)
        self.assertEqual(
            (output / "opaque/common" / Path(_hashed(self.logical))).read_bytes(),
            b"mapped",
        )
        self.assertEqual(
            (output / "opaque/common/aa" / ("b" * 38)).read_bytes(),
            b"opaque",
        )
        self.assertIn("must never execute", (output / "quarantine/server-data/apply_rows.py").read_text("utf-8"))
        self.assertFalse((self.root / "script-ran").exists())
        inventory = (output / "legacy-import.json").read_bytes()
        self.assertEqual(inventory, canonical_json_bytes(json.loads(inventory)))
        self.assertNotIn(str(self.root), inventory.decode("utf-8"))

    @unittest.skipUnless(os.name == "nt", "Windows extended-path behavior")
    def test_import_writes_mapped_member_beyond_windows_max_path(self) -> None:
        logical = (
            "long-segment-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/"
            "battle/action/skill/action/ability_skill/"
            "ability_skill_black_wolf_knight_wt26_superfever$"
            "ability_skill_black_wolf_knight_wt26_superfever.action.dsl.amf3.deflate"
        )
        output = self.root / "workspace"
        mapped = output / "roots" / "common" / Path(logical)
        self.assertGreater(len(os.fspath(mapped)), 260)
        share = self.root / "long-path-share.zip"
        _write_share(
            share,
            {f"production/upload/{_hashed(logical)}": b"mapped"},
        )
        mapping = self._mapping(("common", logical))

        try:
            receipt = import_legacy_share(share, output, mapping=mapping)
            self.assertEqual(receipt.mapping_status, "complete")
            self.assertEqual(
                wf_character_workspace._absolute(mapped).read_bytes(),
                b"mapped",
            )
        finally:
            extended_output = wf_character_workspace._absolute(output)
            if extended_output.exists():
                shutil.rmtree(extended_output)

    def test_explicit_mapping_materializes_only_proven_logical_paths(self) -> None:
        output = self.root / "workspace"
        receipt = import_legacy_share(
            self.share,
            output,
            mapping=self._mapping(("common", self.logical)),
        )
        wire = receipt.to_wire()
        self.assertEqual(wire["mappingStatus"], "partial")
        self.assertFalse(wire["clientPayloadEditable"])
        self.assertEqual(
            (output / "roots/common" / Path(self.logical)).read_bytes(), b"mapped"
        )
        self.assertFalse((output / "opaque/common" / Path(_hashed(self.logical))).exists())
        self.assertTrue((output / "opaque/common/aa" / ("b" * 38)).is_file())
        mapping = json.loads((output / "legacy-path-map.json").read_bytes())
        self.assertEqual(mapping["paths"], [{"logicalPath": self.logical, "root": "common"}])

    def test_complete_mapping_marks_client_payload_editable(self) -> None:
        other_logical = "character/rolf/ui/square_0.png"
        other_member = f"production/upload/{_hashed(other_logical)}"
        self.original = _write_share(
            self.share,
            {self.mapped_member: b"mapped", other_member: b"other"},
        )
        receipt = import_legacy_share(
            self.share,
            self.root / "workspace",
            mapping=self._mapping(
                ("common", self.logical), ("common", other_logical)
            ),
        )
        self.assertEqual(receipt.mapping_status, "complete")
        self.assertTrue(receipt.client_payload_editable)

    def test_mapping_to_absent_member_fails_without_committing_output(self) -> None:
        output = self.root / "workspace"
        mapping = self._mapping(("common", "character/rolf/missing.bin"))
        with self.assertRaisesRegex(ReleaseError, "does not exist") as caught:
            import_legacy_share(self.share, output, mapping=mapping)
        self.assertEqual(caught.exception.code, "WFREL_SHARE_INVALID")
        self.assertFalse(output.exists())

    def test_same_logical_path_can_be_mapped_in_distinct_cdn_roots(self) -> None:
        raw = canonical_json_bytes({
            "legacyPathMapVersion": 1,
            "paths": [
                {"logicalPath": self.logical, "root": "common"},
                {"logicalPath": self.logical, "root": "android"},
            ],
        })

        parsed = parse_path_map(raw)

        self.assertEqual(
            [(item.root, item.logical_path) for item in parsed],
            [("android", self.logical), ("common", self.logical)],
        )

    def test_duplicate_mapping_in_the_same_root_is_rejected(self) -> None:
        mapping = self.root / "path-map.json"
        mapping.write_bytes(canonical_json_bytes({
            "legacyPathMapVersion": 1,
            "paths": [
                {"logicalPath": self.logical, "root": "common"},
                {"logicalPath": self.logical, "root": "common"},
            ],
        }))
        with self.assertRaisesRegex(ReleaseError, "duplicated"):
            import_legacy_share(self.share, self.root / "workspace", mapping=mapping)
        self.assertFalse((self.root / "workspace").exists())

    def test_existing_output_is_never_reused_or_overwritten(self) -> None:
        output = self.root / "workspace"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_bytes(b"keep")
        with self.assertRaises(ReleaseError) as caught:
            import_legacy_share(self.share, output)
        self.assertEqual(caught.exception.code, "WFREL_SHARE_IO")
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_private_source_snapshot_replacement_before_commit_is_rejected(self) -> None:
        import wf_release_v1.legacy_import as legacy_import

        output = self.root / "workspace"
        real_extract = legacy_import._extract_workspace

        def replace_after_extract(source, staging, plan, mappings):
            result = real_extract(source, staging, plan, mappings)
            source_path = Path(source) if isinstance(source, Path) else Path(source.name)
            before = source_path.stat()
            raw = bytearray(source_path.read_bytes())
            raw[0] ^= 1
            source_path.write_bytes(raw)
            os.utime(source_path, ns=(before.st_atime_ns, before.st_mtime_ns))
            return result

        with mock.patch.object(
            legacy_import, "_extract_workspace", side_effect=replace_after_extract
        ):
            with self.assertRaisesRegex(ReleaseError, "changed"):
                import_legacy_share(self.share, output)
        self.assertFalse(output.exists())

    def test_cli_imports_to_explicit_output_and_emits_sanitized_receipt(self) -> None:
        output = self.root / "workspace"
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-m",
                "wf_release_v1",
                "import-share",
                "--share",
                str(self.share),
                "--output",
                str(output),
                "--json",
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout.count(b"\n"), 1)
        self.assertNotIn(str(self.root), result.stdout.decode("utf-8"))
        self.assertEqual(json.loads(result.stdout)["mappingStatus"], "opaque")
        self.assertTrue((output / "legacy-import.json").is_file())


if __name__ == "__main__":
    unittest.main()

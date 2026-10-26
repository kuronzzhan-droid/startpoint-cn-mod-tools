from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import wf_character_workspace
import wf_mod_tool
from tests.release_v1_fixtures import make_sealed_character_workspace
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.errors import ReleaseError


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _flat_table(
    key: str,
    row: bytes = b"character-row",
    *,
    extra: tuple[str, bytes] | None = None,
) -> bytes:
    keys = [key]
    rows = [row]
    if extra is not None:
        keys.append(extra[0])
        rows.append(extra[1])
    table = wf_mod_tool.OrderedMap(
        "master/character/character.orderedmap",
        keys,
        rows,
        Path("<memory>"),
    )
    return wf_mod_tool.build_orderedmap(table)


class CharacterEditRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.character_id = 179999
        self.source = make_sealed_character_workspace(
            self.root / "source-parent",
            character_id=self.character_id,
            code_name="black_wolf_knight_wt26",
        )
        manifest_path = self.source / "package/manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        table_path = self.source / "package/roots/common/master/character/character.orderedmap"
        table_raw = _flat_table(
            str(self.character_id), extra=("200000", b"unowned-character-row")
        )
        table_path.write_bytes(table_raw)
        claim = manifest["roots"]["common"][0]
        claim.update({"sha256": _sha(table_raw), "size": len(table_raw)})
        android_path = self.source / "package/roots/android/battle/common/edit-roundtrip.bin"
        android_path.parent.mkdir(parents=True, exist_ok=True)
        android_raw = b"android-edit-roundtrip"
        android_path.write_bytes(android_raw)
        manifest["roots"]["android"].append({
            "logical_path": "battle/common/edit-roundtrip.bin",
            "sha256": _sha(android_raw),
            "size": len(android_raw),
        })
        for server_claim in manifest["roots"]["server"]:
            logical = server_claim["logical_path"]
            server_path = self.source / "package/roots/server" / logical
            raw = canonical_json_bytes({str(self.character_id): {"source": logical}})
            server_path.write_bytes(raw)
            server_claim.update({"sha256": _sha(raw), "size": len(raw)})
            manifest["tables"].append({
                "root": "server",
                "logical_path": logical,
                "codec_id": "json_object",
                "outer_keys": [str(self.character_id)],
                "inner_keys": [],
                "semantic_claims": [],
            })
        manifest["qa"].update({"release_ready": False, "workspace_input_sha256": ""})
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        sealed = wf_character_workspace.seal_workspace(self.source)
        self.assertTrue(sealed.release_ready)

    def test_checkout_edit_reseal_and_overlay_preserve_source(self) -> None:
        from wf_release_v1.character_edit import (
            checkout_character_workspace,
            seal_edited_character_workspace,
        )
        from wf_release_v1.overlay_builder import build_character_overlay

        source_manifest = (self.source / "package/manifest.json").read_bytes()
        output = self.root / "rolf-edit"
        receipt = checkout_character_workspace(self.source, output, "1.1.0")

        self.assertTrue(receipt.editable)
        self.assertFalse(wf_character_workspace.inspect_workspace(output)["release_ready"])
        self.assertTrue(wf_character_workspace.inspect_workspace(self.source)["release_ready"])
        self.assertEqual(source_manifest, (self.source / "package/manifest.json").read_bytes())
        manifest = json.loads((output / "package/manifest.json").read_bytes())
        self.assertEqual("1.1.0", manifest["package_version"])
        self.assertFalse(manifest["qa"]["release_ready"])

        table_path = output / "package/roots/common/master/character/character.orderedmap"
        changed = _flat_table(
            str(self.character_id),
            b"edited-character-row",
            extra=("200000", b"unowned-character-row"),
        )
        table_path.write_bytes(changed)
        sealed = seal_edited_character_workspace(output)

        self.assertTrue(sealed.release_ready)
        self.assertEqual("1.1.0", sealed.package_version)
        refreshed = json.loads((output / "package/manifest.json").read_bytes())
        self.assertEqual(_sha(changed), refreshed["roots"]["common"][0]["sha256"])
        overlay = self.root / "rolf-edit.patch-overlay.zip"
        built = build_character_overlay(output, "1.4.347", "1.4.348", overlay)
        self.assertTrue(overlay.is_file())
        self.assertEqual("1.4.348", built.target_version)
        self.assertEqual(source_manifest, (self.source / "package/manifest.json").read_bytes())

    def test_checkout_is_new_version_new_directory_and_seal_requires_edit_state(self) -> None:
        from wf_release_v1.character_edit import (
            checkout_character_workspace,
            seal_edited_character_workspace,
        )

        with self.assertRaisesRegex(ReleaseError, "new package version"):
            checkout_character_workspace(self.source, self.root / "same", "1.0.0")
        with self.assertRaisesRegex(ReleaseError, "increase"):
            checkout_character_workspace(self.source, self.root / "older", "0.9.0")
        with self.assertRaisesRegex(ReleaseError, "version"):
            checkout_character_workspace(self.source, self.root / "bad", "latest")
        occupied = self.root / "occupied"
        occupied.mkdir()
        with self.assertRaisesRegex(ReleaseError, "new absolute path"):
            checkout_character_workspace(self.source, occupied, "1.1.0")
        with self.assertRaisesRegex(ReleaseError, "editable checkout"):
            seal_edited_character_workspace(self.source)

    def test_reseal_rejects_manifest_path_escape_before_reading_root_payloads(self) -> None:
        from wf_release_v1.character_edit import (
            checkout_character_workspace,
            seal_edited_character_workspace,
        )

        output = self.root / "rolf-edit"
        checkout_character_workspace(self.source, output, "1.1.0")
        manifest_path = output / "package/manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["roots"]["common"][0]["logical_path"] = "../../manifest.json"
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with self.assertRaisesRegex(ReleaseError, "logical path"):
            seal_edited_character_workspace(output)

    def test_reseal_rejects_file_set_and_claim_drift_without_rewriting_manifest(self) -> None:
        from wf_release_v1.character_edit import (
            checkout_character_workspace,
            seal_edited_character_workspace,
        )

        output = self.root / "rolf-edit"
        checkout_character_workspace(self.source, output, "1.1.0")
        manifest_path = output / "package/manifest.json"
        original_manifest = manifest_path.read_bytes()
        extra = output / "package/roots/common/extra.bin"
        extra.write_bytes(b"extra")
        with self.assertRaisesRegex(ReleaseError, "file set"):
            seal_edited_character_workspace(output)
        self.assertEqual(original_manifest, manifest_path.read_bytes())
        extra.unlink()

        table_path = output / "package/roots/common/master/character/character.orderedmap"
        table_path.write_bytes(_flat_table("1"))
        with self.assertRaisesRegex(ReleaseError, "table claim"):
            seal_edited_character_workspace(output)
        self.assertEqual(original_manifest, manifest_path.read_bytes())

    def test_reseal_rejects_server_row_for_another_character(self) -> None:
        from wf_release_v1.character_edit import (
            checkout_character_workspace,
            seal_edited_character_workspace,
        )

        output = self.root / "rolf-edit"
        checkout_character_workspace(self.source, output, "1.1.0")
        manifest_path = output / "package/manifest.json"
        original_manifest = manifest_path.read_bytes()
        server = output / "package/roots/server/character.json"
        server.write_bytes(canonical_json_bytes({"1": {"name": "other"}}))
        with self.assertRaisesRegex(ReleaseError, "server table claim"):
            seal_edited_character_workspace(output)
        self.assertEqual(original_manifest, manifest_path.read_bytes())

    def test_reseal_rejects_changes_to_unowned_shared_table_rows(self) -> None:
        from wf_release_v1.character_edit import (
            checkout_character_workspace,
            seal_edited_character_workspace,
        )

        output = self.root / "rolf-edit"
        checkout_character_workspace(self.source, output, "1.1.0")
        manifest_path = output / "package/manifest.json"
        original_manifest = manifest_path.read_bytes()
        table = output / "package/roots/common/master/character/character.orderedmap"
        table.write_bytes(_flat_table(
            str(self.character_id),
            extra=("200000", b"silently-changed-other-character"),
        ))
        with self.assertRaisesRegex(ReleaseError, "unowned table"):
            seal_edited_character_workspace(output)
        self.assertEqual(original_manifest, manifest_path.read_bytes())

    def test_reseal_cannot_expand_ownership_claims_to_hide_an_unowned_edit(self) -> None:
        from wf_release_v1.character_edit import (
            checkout_character_workspace,
            seal_edited_character_workspace,
        )

        output = self.root / "rolf-edit"
        checkout_character_workspace(self.source, output, "1.1.0")
        manifest_path = output / "package/manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["tables"][0]["outer_keys"].append("200000")
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        table = output / "package/roots/common/master/character/character.orderedmap"
        table.write_bytes(_flat_table(
            str(self.character_id),
            extra=("200000", b"claimed-after-checkout"),
        ))
        with self.assertRaisesRegex(ReleaseError, "session"):
            seal_edited_character_workspace(output)

    def test_cli_checkout_and_seal_emit_path_free_receipts(self) -> None:
        checkout = self.root / "cli-edit"
        for arguments in (
            [
                "checkout-character", "--workspace", str(self.source),
                "--output", str(checkout), "--package-version", "1.1.0", "--json",
            ],
            ["seal-character", "--workspace", str(checkout), "--json"],
        ):
            result = subprocess.run(
                [sys.executable, "-X", "utf8", "-m", "wf_release_v1", *arguments],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr.decode("utf-8"))
            self.assertEqual(b"", result.stderr)
            self.assertEqual(1, result.stdout.count(b"\n"))
            self.assertNotIn(str(self.root), result.stdout.decode("utf-8"))
            self.assertTrue(json.loads(result.stdout)["releaseReady"] is (arguments[0] == "seal-character"))

        rejected = subprocess.run(
            [
                sys.executable, "-X", "utf8", "-m", "wf_release_v1",
                "checkout-character", "--workspace", str(self.source),
                "--output", str(self.root / "same-version"),
                "--package-version", "1.0.0", "--json",
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(20, rejected.returncode)
        self.assertEqual(b"", rejected.stdout)
        self.assertEqual("WFREL_CHARACTER_EDIT_INVALID", json.loads(rejected.stderr)["code"])


if __name__ == "__main__":
    unittest.main()

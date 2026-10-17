from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import wf_assets
import wf_character_workspace
import wf_mod_tool
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.errors import ReleaseError


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _flat_table(key: str) -> bytes:
    table = wf_mod_tool.OrderedMap(
        "master/character/character.orderedmap",
        [key],
        [b"character-row"],
        Path("<memory>"),
    )
    return wf_mod_tool.build_orderedmap(table)


class LegacyCharacterAdoptionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.imported = self.root / "imported"
        self.imported.mkdir()
        self.character_id = 179999
        self.code_name = "black_wolf_knight_wt26"
        self.server_rows = {
            "assets/character.json": {str(self.character_id): {"name": "Rolf"}},
            "assets/cdndata/character.json": {str(self.character_id): [[self.code_name]]},
            "assets/cdndata/character_text.json": {str(self.character_id): [["Rolf"]]},
            "assets/mana_node.json": {str(self.character_id): {"1": {}}},
        }
        server_path = self.imported / "quarantine/server-data/rows.json"
        server_path.parent.mkdir(parents=True)
        server_raw = canonical_json_bytes(self.server_rows)
        server_path.write_bytes(server_raw)

        payloads: list[dict[str, object]] = []
        for requirement in wf_character_workspace.char_asset_requirements(self.code_name):
            if requirement.category != "required":
                continue
            raw = (
                wf_assets.PNG_FAKE + b"image"
                if requirement.logical_path.endswith(".png")
                else requirement.logical_path.encode("utf-8")
            )
            self._payload(payloads, "medium", requirement.logical_path, raw)
        table_logical = "master/character/character.orderedmap"
        self._payload(payloads, "common", table_logical, _flat_table(str(self.character_id)))
        # Rolf's real super-Fever action path exceeds MAX_PATH only after the
        # isolated workspace staging prefix is added on Windows.
        self._payload(
            payloads,
            "common",
            "battle/action/skill/action/ability_skill/"
            "ability_skill_black_wolf_knight_wt26_superfever$"
            "ability_skill_black_wolf_knight_wt26_superfever.action.dsl.amf3.deflate",
            b"super-fever-action",
        )
        # Cross-root identical bytes are a real legacy shape and must collapse safely.
        self._payload(payloads, "common", "battle/common/layer0.png", b"same")
        self._payload(payloads, "android", "battle/common/layer0.png", b"same")

        source = b"legacy-share"
        (self.imported / "source.wfshare.zip").write_bytes(source)
        inventory = {
            "archiveSha256": _sha(source),
            "archiveSize": len(source),
            "clientPayloadEditable": True,
            "legacyImportVersion": 1,
            "mappingStatus": "complete",
            "payloadFileCount": len(payloads),
            "payloadFiles": payloads,
            "quarantineFileCount": 1,
            "quarantineFiles": [{
                "path": "quarantine/server-data/rows.json",
                "script": False,
                "sha256": _sha(server_raw),
                "size": len(server_raw),
                "sourcePath": "server-data/rows.json",
            }],
            "sourceArchive": {
                "path": "source.wfshare.zip",
                "sha256": _sha(source),
                "size": len(source),
            },
            "sourceFormat": "wfshare-v2",
        }
        (self.imported / "legacy-import.json").write_bytes(canonical_json_bytes(inventory))
        self.config = self.root / "adoption.json"
        self._write_config(server_raw)

    def _payload(
        self,
        payloads: list[dict[str, object]],
        root: str,
        logical: str,
        raw: bytes,
    ) -> None:
        index = len(payloads)
        relative = f"roots/{root}/{logical}"
        path = self.imported / Path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        payloads.append({
            "hashedPath": f"production/{root}/{index:040x}",
            "logicalPath": logical,
            "path": relative,
            "root": root,
            "sha256": _sha(raw),
            "size": len(raw),
        })

    def _write_config(self, server_raw: bytes) -> None:
        self.config.write_bytes(canonical_json_bytes({
            "clientTables": [{
                "codecId": "flat",
                "innerKeys": [],
                "logicalPath": "master/character/character.orderedmap",
                "outerKeys": [str(self.character_id)],
                "root": "common",
                "semanticClaims": [],
            }],
            "codeName": self.code_name,
            "legacyCharacterAdoptionVersion": 1,
            "packageId": self.code_name,
            "packageVersion": "1.0.0",
            "requiredCapabilities": ["content.sync@1"],
            "requiresClientBase": "1.4.324",
            "serverRows": {
                "path": "quarantine/server-data/rows.json",
                "sha256": _sha(server_raw),
            },
            "skills": {"superFever": True, "specialPowerFlip": True},
            "targetCharacterId": self.character_id,
            "templateCharacterId": 149999,
            "uniqueCondition": {"ids": [179999, 180000]},
        }))

    def test_adopts_complete_import_as_sealed_37_of_37_workspace(self) -> None:
        from wf_release_v1.legacy_character import adopt_legacy_character

        output = self.root / "rolf-workspace"
        receipt = adopt_legacy_character(self.imported, self.config, output)

        status = wf_character_workspace.inspect_workspace(output)
        self.assertTrue(status["release_ready"], status)
        self.assertEqual(37, status["requirement_report"]["required_present"])
        self.assertEqual("complete", receipt.mapping_status)
        self.assertEqual(45, receipt.workspace_file_count)
        manifest = json.loads((output / "package/manifest.json").read_text("utf-8"))
        self.assertEqual(179999, manifest["character_id"])
        self.assertEqual(149999, json.loads((output / "workspace.json").read_text("utf-8"))["template_character_id"])
        self.assertEqual(4, len(manifest["roots"]["server"]))
        self.assertEqual(5, len(manifest["tables"]))
        layer_claims = [
            item for root in manifest["roots"].values() for item in root
            if item["logical_path"] == "battle/common/layer0.png"
        ]
        self.assertEqual(1, len(layer_claims))
        self.assertFalse((output / "package/roots/android/battle/common/layer0.png").exists())
        self.assertEqual(
            {"179999": {"name": "Rolf"}},
            json.loads((output / "package/roots/server/character.json").read_text("utf-8")),
        )

    def test_rejects_incomplete_mapping_conflicting_cross_root_and_bad_claims_atomically(self) -> None:
        from wf_release_v1.legacy_character import adopt_legacy_character

        inventory_path = self.imported / "legacy-import.json"
        original_inventory = inventory_path.read_bytes()
        inventory = json.loads(original_inventory)
        inventory["mappingStatus"] = "partial"
        inventory["clientPayloadEditable"] = False
        inventory_path.write_bytes(canonical_json_bytes(inventory))
        with self.assertRaisesRegex(ReleaseError, "complete"):
            adopt_legacy_character(self.imported, self.config, self.root / "partial")
        self.assertFalse((self.root / "partial").exists())

        inventory_path.write_bytes(original_inventory)
        android = self.imported / "roots/android/battle/common/layer0.png"
        android.write_bytes(b"different")
        inventory = json.loads(original_inventory)
        item = next(row for row in inventory["payloadFiles"] if row["root"] == "android")
        item.update({"sha256": _sha(b"different"), "size": len(b"different")})
        inventory_path.write_bytes(canonical_json_bytes(inventory))
        with self.assertRaisesRegex(ReleaseError, "cross-root"):
            adopt_legacy_character(self.imported, self.config, self.root / "conflict")
        self.assertFalse((self.root / "conflict").exists())

        android.write_bytes(b"same")
        inventory_path.write_bytes(original_inventory)
        config = json.loads(self.config.read_bytes())
        config["clientTables"][0]["outerKeys"] = ["missing"]
        self.config.write_bytes(canonical_json_bytes(config))
        with self.assertRaisesRegex(ReleaseError, "claim"):
            adopt_legacy_character(self.imported, self.config, self.root / "bad-claim")
        self.assertFalse((self.root / "bad-claim").exists())

        self._write_config(canonical_json_bytes(self.server_rows))
        config = json.loads(self.config.read_bytes())
        config["uniqueCondition"] = []
        self.config.write_bytes(canonical_json_bytes(config))
        with self.assertRaisesRegex(ReleaseError, "uniqueCondition"):
            adopt_legacy_character(self.imported, self.config, self.root / "bad-late-config")
        self.assertFalse((self.root / "bad-late-config").exists())
        self.assertEqual([], list(self.root.glob(".legacy-character-*")))

    def test_rejects_server_rows_for_another_character_and_source_drift(self) -> None:
        from wf_release_v1.legacy_character import adopt_legacy_character

        rows_path = self.imported / "quarantine/server-data/rows.json"
        bad = dict(self.server_rows)
        bad["assets/character.json"] = {"1": {"name": "other"}}
        bad_raw = canonical_json_bytes(bad)
        rows_path.write_bytes(bad_raw)
        config = json.loads(self.config.read_bytes())
        config["serverRows"]["sha256"] = _sha(bad_raw)
        self.config.write_bytes(canonical_json_bytes(config))
        with self.assertRaisesRegex(ReleaseError, "target character"):
            adopt_legacy_character(self.imported, self.config, self.root / "bad-rows")
        self.assertFalse((self.root / "bad-rows").exists())

        rows_path.write_bytes(canonical_json_bytes(self.server_rows))
        self._write_config(canonical_json_bytes(self.server_rows))
        payload = next((self.imported / "roots/medium").rglob("*.png"))
        payload.write_bytes(payload.read_bytes() + b"drift")
        with self.assertRaisesRegex(ReleaseError, "changed"):
            adopt_legacy_character(self.imported, self.config, self.root / "drift")
        self.assertFalse((self.root / "drift").exists())

    def test_cli_adopts_to_explicit_output_without_leaking_local_paths(self) -> None:
        output = self.root / "cli-workspace"
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-m",
                "wf_release_v1",
                "adopt-character",
                "--imported",
                str(self.imported),
                "--config",
                str(self.config),
                "--output",
                str(output),
                "--json",
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr.decode("utf-8"))
        self.assertEqual(b"", result.stderr)
        self.assertEqual(1, result.stdout.count(b"\n"))
        self.assertNotIn(str(self.root), result.stdout.decode("utf-8"))
        self.assertTrue(json.loads(result.stdout)["releaseReady"])
        self.assertTrue((output / "package/manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()

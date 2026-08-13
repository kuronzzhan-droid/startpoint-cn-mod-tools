"""Clean-root legacy share to editable Release acceptance."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from zipfile import ZIP_STORED, ZipFile

import wf_character_workspace
from tests.release_v1_schema_support import requirements_wire
from tests.test_release_v1_legacy_character import _flat_table, _sha
from tests.test_release_v1_legacy_compatibility import _active, _target
from tests.test_release_v1_legacy_import import _member
from wf_release_v1._legacy_mapping import parse_path_map
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.character_edit import (
    checkout_character_workspace,
    seal_edited_character_workspace,
)
from wf_release_v1.legacy_character import adopt_legacy_character
from wf_release_v1.legacy_compatibility import plan_legacy_install
from wf_release_v1.legacy_import import import_legacy_share
from wf_release_v1.legacy_target import LegacyProcessStatus
from wf_release_v1.overlay_builder import build_character_overlay
from wf_release_v1.producer import BuildRequest, build_character_release
from wf_release_v1.schema import parse_requirements
from wf_release_v1.verifier import verify_release_contract


CHARACTER_ID = 179999
CODE_NAME = "black_wolf_knight_wt26"


def _inner(payloads: dict[str, bytes], members: dict[str, str]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for logical in sorted(payloads, key=lambda item: item.encode("utf-8")):
            info, raw = _member(members[logical], payloads[logical])
            archive.writestr(info, raw)
    return output.getvalue()


def _share(
    path: Path,
    payloads: dict[str, dict[str, bytes]],
    mapping_path: Path,
    server_rows: dict[str, object],
) -> None:
    mapping = {
        "legacyPathMapVersion": 1,
        "paths": [
            {"logicalPath": logical, "root": root}
            for root in sorted(payloads)
            for logical in sorted(payloads[root], key=lambda item: item.encode("utf-8"))
        ],
    }
    mapping_raw = canonical_json_bytes(mapping)
    mapping_path.write_bytes(mapping_raw)
    parsed = parse_path_map(mapping_raw)
    by_root = {
        root: {item.logical_path: item.member for item in parsed if item.root == root}
        for root in payloads
    }
    archives: list[tuple[str, bytes, int]] = []
    for root in sorted(payloads):
        raw = _inner(payloads[root], by_root[root])
        name = (
            f"archive-{root}-diff/"
            "pinball-1.4.324-1.4.347-1-vertical.zip"
        )
        archives.append((name, raw, len(payloads[root])))
    requires = {
        "schemaVersion": 2,
        "pack": {
            "variant": "full",
            "since": "1.4.323",
            "tail": "1.4.346",
            "sourceEdges": 23,
            "anchor": {"from": "1.4.324", "to": "1.4.347"},
            "archives": [name for name, _raw, _count in archives],
        },
        "enhancement": True,
        "enhancementDetail": {
            "officialBaseline": None,
            "revertedRows": 0,
            "restoredRows": 0,
            "revertedTables": [],
            "droppedEntries": [],
            "note": "vertical fixture",
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
    outputs = [
        {
            "root": name.split("-", 2)[1],
            "path": name,
            "entries": count,
            "size": len(raw),
            "sha256": _sha(raw),
        }
        for name, raw, count in archives
    ]
    total = sum(item[2] for item in archives)
    report = {
        "variant": "full",
        "tag": "vertical",
        "pack": "wfshare-1.4.324-to-1.4.347-full",
        "entries": total,
        "summary": {"entries": total, "kept": total, "dropped": 0, "rebuilt": 0},
        "outputs": outputs,
    }
    outer_members = {
        **{name: raw for name, raw, _count in archives},
        "requires.json": canonical_json_bytes(requires),
        "report.json": canonical_json_bytes(report),
        "server-data/rows.json": canonical_json_bytes(server_rows),
    }
    with ZipFile(path, "w", compression=ZIP_STORED) as archive:
        for name in sorted(outer_members, key=lambda item: item.encode("utf-8")):
            info, raw = _member(f"wfshare-vertical/{name}", outer_members[name])
            archive.writestr(info, raw)


class LegacyVerticalTests(unittest.TestCase):
    def test_import_adopt_edit_seal_release_and_read_only_plan(self) -> None:
        raw_root = Path(tempfile.mkdtemp(
            prefix=".wv-long-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-",
            dir=Path(__file__).resolve().parents[1],
        ))

        def cleanup() -> None:
            extended_root = wf_character_workspace._absolute(raw_root)
            if extended_root.exists():
                shutil.rmtree(extended_root)

        self.addCleanup(cleanup)
        root = raw_root
        required: dict[str, bytes] = {}
        for item in wf_character_workspace.char_asset_requirements(CODE_NAME):
            if item.category == "required":
                required[item.logical_path] = item.logical_path.encode("utf-8")
        action = (
            "battle/action/skill/action/ability_skill/"
            "ability_skill_black_wolf_knight_wt26_superfever$"
            "ability_skill_black_wolf_knight_wt26_superfever.action.dsl.amf3.deflate"
        )
        self.assertGreater(
            len(str(root / "imported" / "roots" / "common" / Path(action))),
            260,
        )
        payloads = {
            "android": {
                "battle/common/rolf-android-marker.bin": b"android-marker",
            },
            "common": {
                "master/character/character.orderedmap": _flat_table(str(CHARACTER_ID)),
                action: b"super-fever-action",
            },
            "medium": required,
        }
        server_rows = {
            "assets/character.json": {str(CHARACTER_ID): {"name": "Rolf"}},
            "assets/cdndata/character.json": {str(CHARACTER_ID): [[CODE_NAME]]},
            "assets/cdndata/character_text.json": {str(CHARACTER_ID): [["Rolf"]]},
            "assets/mana_node.json": {str(CHARACTER_ID): {"1": {}}},
        }
        share = root / "rolf.wfshare.zip"
        mapping = root / "path-map.json"
        _share(share, payloads, mapping, server_rows)

        imported = root / "imported"
        imported_receipt = import_legacy_share(share, imported, mapping=mapping)
        self.assertEqual(("complete", True), (
            imported_receipt.mapping_status, imported_receipt.client_payload_editable,
        ))
        server_raw = canonical_json_bytes(server_rows)
        adoption = root / "adoption.json"
        adoption.write_bytes(canonical_json_bytes({
            "clientTables": [{
                "codecId": "flat",
                "innerKeys": [],
                "logicalPath": "master/character/character.orderedmap",
                "outerKeys": [str(CHARACTER_ID)],
                "root": "common",
                "semanticClaims": [],
            }],
            "codeName": CODE_NAME,
            "legacyCharacterAdoptionVersion": 1,
            "packageId": CODE_NAME,
            "packageVersion": "1.0.0",
            "requiredCapabilities": ["content.sync@1"],
            "requiresClientBase": "1.4.324",
            "serverRows": {
                "path": "quarantine/server-data/rows.json",
                "sha256": _sha(server_raw),
            },
            "skills": {"superFever": True, "specialPowerFlip": True},
            "targetCharacterId": CHARACTER_ID,
            "templateCharacterId": 149999,
            "uniqueCondition": {"ids": [179999, 180000]},
        }))
        adopted = root / "adopted"
        adopt_legacy_character(imported, adoption, adopted)
        self.assertTrue(wf_character_workspace.inspect_workspace(adopted)["release_ready"])

        edited = root / "edited"
        checkout_character_workspace(adopted, edited, "1.0.1")
        action_path = wf_character_workspace._absolute(
            edited / "package" / "roots" / "common" / Path(action)
        )
        action_path.write_bytes(action_path.read_bytes() + b"-edited")
        sealed = seal_edited_character_workspace(edited)
        self.assertTrue(sealed.release_ready)

        overlay = root / "rolf-1.4.347-to-1.4.348.zip"
        build_character_overlay(edited, "1.4.347", "1.4.348", overlay)
        requirements = requirements_wire()
        requirements.update({
            "serverCapabilities": ["content.sync@1"],
            "clientVersions": ["1.4.324"],
            "resourceBaselines": ["1.4.324"],
        })
        release = root / "rolf-1.0.1.wf-release.zip"
        build_character_release(BuildRequest(
            name="rolf-black-wolf-knight",
            version="1.0.1",
            workspace=edited,
            overlay_archives=(overlay,),
            output=release,
            requirements=parse_requirements(requirements),
        ))
        _report, verified = verify_release_contract(release)
        plan = plan_legacy_install(
            verified,
            _target(
                tail="1.4.347",
                process=LegacyProcessStatus.NOT_OWNED,
                client_version="1.4.324",
                resource_baseline="1.4.324",
            ),
            _active(client_version="1.4.324", resource_baseline="1.4.324"),
        )
        self.assertEqual((True, False, "legacy", False), (
            plan.preview_only, plan.installable, plan.target_protocol, plan.writes_live,
        ))
        self.assertIn("WFREL_LEGACY_PROCESS_NOT_OWNED", plan.codes)


if __name__ == "__main__":
    unittest.main()

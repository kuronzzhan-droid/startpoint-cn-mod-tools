# -*- coding: utf-8 -*-
from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mod-tools"))

import wf_offline_bundle as module


TASK11_MODULE_PATH = client_patch_path('offline-android/build_offline_apk.py')


def load_task11_module():
    spec = importlib.util.spec_from_file_location("offline_bundle_task11_contract", require_external_source(TASK11_MODULE_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {TASK11_MODULE_PATH}")
    task11 = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = task11
    spec.loader.exec_module(task11)
    return task11


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_zip(
    path: Path,
    members: dict[str, bytes],
    *,
    compression: int = zipfile.ZIP_STORED,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "x", compression=compression) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


PRODUCTION_PINNED_BASELINE_SECRET_FINDINGS = getattr(
    module,
    "_PINNED_BASELINE_SECRET_FINDINGS",
    None,
)


class OfflineBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.baseline_secret_patch = mock.patch.object(
            module,
            "_PINNED_BASELINE_SECRET_FINDINGS",
            (),
            create=True,
        )
        self.baseline_secret_patch.start()
        self.apk = self.root / "signed.apk"
        self.data_zip = self.root / "data.zip"
        self.candidate = self.root / "candidate"
        self.final_dir = self.root / "WF离线整合版"
        self.entry_payloads = {
            "WorldFlipper/dummy/download/.empty": b"0",
            "WorldFlipper/dummy/info.json": b'{"version":"1.4.196"}\n',
            "WorldFlipper/dummy/download/production/upload/aa/" + "1" * 38: b"common",
            "WorldFlipper/dummy/download/production/medium_upload/bb/" + "2" * 38: b"medium",
            "WorldFlipper/dummy/download/production/android_upload/cc/" + "3" * 38: b"android",
        }
        write_zip(
            self.apk,
            {
                "AndroidManifest.xml": b"manifest",
                "assets/worldflipper_android_release.swf": b"patched-swf",
            },
        )
        write_zip(self.data_zip, self.entry_payloads)
        self.guide = module.render_import_guide()
        self.build_id = "build-fixture-001"

    def tearDown(self) -> None:
        self.baseline_secret_patch.stop()
        self.temp.cleanup()

    def evidence(self, *, entry_count: int = 5) -> dict[str, object]:
        entries = [
            {
                "path": name,
                "size": len(payload),
                "sha256": sha256(payload),
                "source": (
                    "generated-marker"
                    if name.endswith("/.empty") or name.endswith("/info.json")
                    else (
                        "medium"
                        if "/medium_upload/" in name
                        else "android" if "/android_upload/" in name else "common"
                    )
                ),
            }
            for name, payload in sorted(self.entry_payloads.items())
        ]
        if entry_count != len(entries):
            entries = [
                {
                    "path": f"WorldFlipper/dummy/download/production/upload/{index % 256:02x}/{index:038x}",
                    "size": 0,
                    "sha256": "0" * 64,
                    "source": "common",
                }
                for index in range(entry_count - 2)
            ] + [
                {
                    "path": "WorldFlipper/dummy/download/.empty",
                    "size": 1,
                    "sha256": sha256(b"0"),
                    "source": "generated-marker",
                },
                {
                    "path": "WorldFlipper/dummy/info.json",
                    "size": 0,
                    "sha256": "0" * 64,
                    "source": "generated-marker",
                },
            ]
        source_checkpoint = {
            "source_apk_sha256": "10" * 32,
            "store_tree_sha256": "11" * 32,
            "source_apk_size": 123456,
            "store_total_bytes": sum(map(len, self.entry_payloads.values())),
            "store_counts": {"common": 113822, "medium": 23458, "android": 1009},
        }
        return {
            "source_fingerprint": {
                "before": dict(source_checkpoint),
                "scan": dict(source_checkpoint),
                "after": dict(source_checkpoint),
                "unchanged": True,
            },
            "source_apk": {
                "basename": "base.apk.1",
                "size": 123456,
                "sha256": "10" * 32,
            },
            "patches": {
                "before_swf_sha256": "20" * 32,
                "after_swf_sha256": "30" * 32,
                "order": ["abyss-mode-equipment", "seris-phase4", "render-scale", "resource-version"],
            },
            "signer": {"certificate_sha256": "40" * 32},
            "versions": {
                "source_resource_version": "1.4.54",
                "output_resource_version": "1.4.196",
                "snapshot_version": "1.4.196",
            },
            "data": {
                "archive_sha256": sha256(self.data_zip.read_bytes()),
                "member_count": entry_count,
                "total_uncompressed_bytes": sum(map(len, self.entry_payloads.values())),
                "zip64": True,
                "roots": {
                    "common": {
                        "count": max(0, entry_count - 4),
                        "bytes": 6,
                        "archive_prefix": "WorldFlipper/dummy/download/production/upload/",
                    },
                    "medium": {
                        "count": 1,
                        "bytes": 6,
                        "archive_prefix": "WorldFlipper/dummy/download/production/medium_upload/",
                    },
                    "android": {
                        "count": 1,
                        "bytes": 7,
                        "archive_prefix": "WorldFlipper/dummy/download/production/android_upload/",
                    },
                },
                "entries": entries,
            },
            "player": {
                "player_id": "1000",
                "before_sha256": "50" * 32,
                "after_sha256": "60" * 32,
                "before_character_ids": ["1"],
                "after_character_ids": ["1", "129999", "139999", "149999"],
                "added_character_ids": ["129999", "139999", "149999"],
                "character_level": 1,
            },
            "content": {
                "ready": True,
                "client_gate_ready": True,
                "rogue": {"event_id": 700099, "round_count": 15, "token_id": 2370099, "ready": True},
                "characters": [
                    {
                        "identity": {"character_id": 129999, "code_name": "seris_dragon_king"},
                        "required_present": 37,
                        "required_total": 37,
                        "three_layer_consistent": True,
                        "missing": [],
                    },
                    {
                        "identity": {"character_id": 139999, "code_name": "stella_summer_goddess"},
                        "required_present": 37,
                        "required_total": 37,
                        "three_layer_consistent": True,
                        "missing": [],
                    },
                    {
                        "identity": {"character_id": 149999, "code_name": "white_wolf_gerald"},
                        "required_present": 37,
                        "required_total": 37,
                        "three_layer_consistent": True,
                        "missing": [],
                    },
                ],
            },
            "apk": {
                "output_sha256": sha256(self.apk.read_bytes()),
                "certificate_sha256": "40" * 32,
                "full_resource_version": "1.4.196",
                "aligned": True,
                "signature_schemes": {"v1": True, "v2": True, "v3": True},
                "verified": True,
            },
            "gates": {
                "store_snapshot": True,
                "content": True,
                "player_overlay": True,
                "apk": True,
                "zip": True,
            },
            "git": {"commit": "0123456789abcdef", "dirty": True},
        }

    def receipt(self, identity: module.CandidateIdentity | None = None) -> dict[str, object]:
        if identity is None:
            identity = module.CandidateIdentity(
                self.build_id,
                sha256(self.apk.read_bytes()),
                sha256(self.data_zip.read_bytes()),
                sha256(self.guide),
                sha256(module.canonical_json_bytes(self.evidence())),
            )
        return {
            "schema_version": 1,
            "build_id": identity.build_id,
            "apk_sha256": identity.apk_sha256,
            "data_zip_sha256": identity.data_zip_sha256,
            "evidence_sha256": identity.evidence_sha256,
            "serial_digest": "70" * 32,
            "probe": {
                "serial_digest": "70" * 32,
                "package_name": "com.leiting.wf",
                "airplane_mode": True,
                "wifi_disabled": True,
                "mobile_disabled": True,
                "no_default_route": True,
                "no_active_network": True,
                "companion_ports_unused": True,
                "save_haxe_present_before": False,
                "dummy_data_present_before": False,
                "fatal_log_lines": [],
            },
            "checks": {name: True for name in module.REQUIRED_MANUAL_CHECKS},
            "accepted_at_utc": "2026-07-21T00:00:00Z",
        }

    def freeze_fixture(self) -> module.CandidateIdentity:
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
        ):
            return module.freeze_candidate(
                self.apk,
                self.data_zip,
                self.guide,
                self.candidate,
                build_id=self.build_id,
                release_evidence=self.evidence(),
            )

    def write_receipt(self, identity: module.CandidateIdentity) -> Path:
        path = self.root / "device-acceptance.json"
        path.write_bytes(module.canonical_json_bytes(self.receipt(identity)))
        return path

    def finalize_fixture(self) -> tuple[module.CandidateIdentity, Path]:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
        ):
            output = module.finalize_candidate(self.candidate, receipt, self.final_dir)
        return identity, output

    def test_canonical_json_is_utf8_sorted_lf_and_rejects_unsafe_values(self) -> None:
        raw = module.canonical_json_bytes({"中": 1, "a": [2, 1]})
        self.assertEqual(raw, b'{"a":[2,1],"\xe4\xb8\xad":1}\n')
        self.assertNotIn(b"\r", raw)
        with self.assertRaisesRegex(module.BundleError, "absolute path"):
            module.canonical_json_bytes({"input": r"X:\sensitive\secret.txt"})
        with self.assertRaisesRegex(module.BundleError, "sensitive field"):
            module.canonical_json_bytes({"keystore_path": "release.jks"})
        with self.assertRaisesRegex(module.BundleError, "finite"):
            module.canonical_json_bytes({"value": float("nan")})

    def test_fixed_chinese_guide_contains_every_operator_step(self) -> None:
        text = self.guide.decode("utf-8")
        expected = (
            "SHA256SUMS.txt",
            "WorldFlipper/save_haxe",
            "WorldFlipper-离线整合版.apk",
            "所有文件访问权限",
            "直接解压到 /storage/emulated/0/",
            "/storage/emulated/0/WorldFlipper/dummy/download/production/upload/",
            "/storage/emulated/0/WorldFlipper/dummy/download/production/medium_upload/",
            "/storage/emulated/0/WorldFlipper/dummy/download/production/android_upload/",
            "/storage/emulated/0/WorldFlipper/dummy/info.json",
            "/storage/emulated/0/WorldFlipper/dummy/download/.empty",
            "禁止把 medium_upload 或 android_upload 扁平合并进 upload",
            "不能放在 Download 下",
            "不能多套一层 WorldFlipper",
            "飞行模式",
            "菜单点击“保存”",
            "129999/139999/149999",
            "ZIP 不覆盖个人进度",
        )
        self.assertTrue(all(token in text for token in expected))
        self.assertTrue(self.guide.endswith(b"\n"))
        self.assertNotIn(b"\r", self.guide)

    def test_import_guide_rejects_each_missing_three_root_marker_or_no_flatten_instruction(self) -> None:
        required = (
            "/storage/emulated/0/WorldFlipper/dummy/download/production/upload/",
            "/storage/emulated/0/WorldFlipper/dummy/download/production/medium_upload/",
            "/storage/emulated/0/WorldFlipper/dummy/download/production/android_upload/",
            "/storage/emulated/0/WorldFlipper/dummy/info.json",
            "/storage/emulated/0/WorldFlipper/dummy/download/.empty",
            "禁止把 medium_upload 或 android_upload 扁平合并进 upload",
        )
        original = module.TEMPLATE_PATH.read_text("utf-8")
        for index, token in enumerate(required):
            with self.subTest(token=token):
                template = self.root / f"missing-guide-token-{index}.txt"
                template.write_text(original.replace(token, "<missing>", 1), encoding="utf-8", newline="\n")
                with (
                    mock.patch.object(module, "TEMPLATE_PATH", template),
                    self.assertRaisesRegex(module.BundleError, "required operator instruction"),
                ):
                    module.render_import_guide()

    def test_freeze_candidate_is_exclusive_and_records_hash_bound_identity(self) -> None:
        identity = self.freeze_fixture()
        self.assertEqual(identity.build_id, self.build_id)
        self.assertEqual(identity.apk_sha256, sha256(self.apk.read_bytes()))
        self.assertEqual(identity.data_zip_sha256, sha256(self.data_zip.read_bytes()))
        self.assertEqual(identity.guide_sha256, sha256(self.guide))
        self.assertEqual(
            identity.evidence_sha256,
            sha256(module.canonical_json_bytes(self.evidence())),
        )
        self.assertEqual(
            set(path.name for path in self.candidate.iterdir()),
            {
                module.APK_NAME,
                module.DATA_ZIP_NAME,
                module.GUIDE_NAME,
                module.CANDIDATE_EVIDENCE_NAME,
            },
        )
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "already exists"),
        ):
            module.freeze_candidate(
                self.apk,
                self.data_zip,
                self.guide,
                self.candidate,
                build_id=self.build_id,
                release_evidence=self.evidence(),
            )

    @unittest.skipUnless(os.name == "nt", "Windows directory sharing contract")
    def test_freeze_candidate_accepts_an_existing_parent_deny_delete_guard(self) -> None:
        parent_guard = module._open_raw_directory(
            self.root,
            deny_delete=True,
            request_delete=False,
        )
        try:
            identity = self.freeze_fixture()
        finally:
            module._close_owned_directory(parent_guard)

        self.assertEqual(identity.build_id, self.build_id)
        self.assertTrue(self.candidate.is_dir())

    @unittest.skipUnless(os.name == "nt", "Windows directory sharing contract")
    def test_finalize_candidate_accepts_an_existing_parent_deny_delete_guard(self) -> None:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)
        parent_guard = module._open_raw_directory(
            self.root,
            deny_delete=True,
            request_delete=False,
        )
        try:
            with (
                mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
                mock.patch.object(
                    module,
                    "PRODUCTION_ROOT_COUNTS",
                    {"common": 1, "medium": 1, "android": 1},
                ),
            ):
                output = module.finalize_candidate(
                    self.candidate,
                    receipt,
                    self.final_dir,
                )
        finally:
            module._close_owned_directory(parent_guard)

        self.assertEqual(output, self.final_dir)
        self.assertTrue(self.final_dir.is_dir())

    def test_verify_candidate_publicly_rehashes_identity_and_returns_detached_evidence(self) -> None:
        self.assertIn("verify_candidate", module.__all__)
        identity = self.freeze_fixture()
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
        ):
            verified, evidence = module.verify_candidate(self.candidate)

        self.assertEqual(verified, identity)
        self.assertEqual(evidence, self.evidence())
        evidence["git"]["dirty"] = False
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
        ):
            _verified_again, evidence_again = module.verify_candidate(self.candidate)
        self.assertTrue(evidence_again["git"]["dirty"])

    def test_verify_candidate_rejects_tampered_artifact(self) -> None:
        self.freeze_fixture()
        (self.candidate / module.APK_NAME).write_bytes(b"tampered")
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
            self.assertRaisesRegex(module.BundleError, "hash|identity|changed"),
        ):
            module.verify_candidate(self.candidate)

    def test_verify_candidate_rejects_data_zip_member_corruption_even_when_outer_hash_is_rebound(self) -> None:
        self.freeze_fixture()
        corrupt_payloads = dict(self.entry_payloads)
        common = next(name for name in corrupt_payloads if "/upload/" in name)
        corrupt_payloads[common] = b"COMMON"
        frozen_zip = self.candidate / module.DATA_ZIP_NAME
        frozen_zip.unlink()
        write_zip(frozen_zip, corrupt_payloads)
        rebound_hash = sha256(frozen_zip.read_bytes())

        evidence_path = self.candidate / module.CANDIDATE_EVIDENCE_NAME
        document = json.loads(evidence_path.read_text("utf-8"))
        document["identity"]["data_zip_sha256"] = rebound_hash
        document["artifact_sizes"]["data_zip"] = frozen_zip.stat().st_size
        document["release_evidence"]["data"]["archive_sha256"] = rebound_hash
        document["identity"]["evidence_sha256"] = sha256(
            module.canonical_json_bytes(document["release_evidence"])
        )
        evidence_path.write_bytes(module.canonical_json_bytes(document))

        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
            self.assertRaisesRegex(module.BundleError, "data ZIP payload mismatch"),
        ):
            module.verify_candidate(self.candidate)

    def test_verify_candidate_binds_zip_member_check_to_the_same_outer_archive_hash(self) -> None:
        identity = self.freeze_fixture()
        frozen_zip = self.candidate / module.DATA_ZIP_NAME
        original_size = frozen_zip.stat().st_size
        replacement = self.root / "same-members-different-container.zip"
        with zipfile.ZipFile(replacement, "x", compression=zipfile.ZIP_STORED) as archive:
            for name, payload in self.entry_payloads.items():
                archive.writestr(name, payload)
            archive.comment = b"different-container-metadata"
        os.replace(replacement, frozen_zip)
        self.assertNotEqual(sha256(frozen_zip.read_bytes()), identity.data_zip_sha256)

        original_hash_regular = module._hash_regular

        def stale_outer_observation(path: Path, *, label: str):
            if Path(path) == frozen_zip and label == "frozen data ZIP":
                return original_size, identity.data_zip_sha256
            return original_hash_regular(path, label=label)

        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
            mock.patch.object(module, "_hash_regular", side_effect=stale_outer_observation),
            self.assertRaisesRegex(module.BundleError, "data ZIP.*hash|hash.*data ZIP"),
        ):
            module.verify_candidate(self.candidate)

    def test_candidate_evidence_digest_rejects_valid_schema_claim_mutation_and_receipt_reuse(self) -> None:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)
        evidence_path = self.candidate / module.CANDIDATE_EVIDENCE_NAME
        document = json.loads(evidence_path.read_text("utf-8"))
        document["release_evidence"]["git"]["dirty"] = False
        evidence_path.write_bytes(module.canonical_json_bytes(document))

        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
            self.assertRaisesRegex(module.BundleError, "evidence.*hash|digest"),
        ):
            module.verify_candidate(self.candidate)

        document["identity"]["evidence_sha256"] = sha256(
            module.canonical_json_bytes(document["release_evidence"])
        )
        evidence_path.write_bytes(module.canonical_json_bytes(document))
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
        ):
            rebound_identity, _rebound_evidence = module.verify_candidate(self.candidate)
        self.assertNotEqual(rebound_identity.evidence_sha256, identity.evidence_sha256)
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
            self.assertRaisesRegex(module.BundleError, "receipt evidence_sha256 mismatch"),
        ):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)
        self.assertFalse(self.final_dir.exists())

    def test_verify_candidate_rejects_extra_file(self) -> None:
        self.freeze_fixture()
        (self.candidate / "extra.txt").write_text("unexpected", encoding="utf-8")
        with self.assertRaisesRegex(module.BundleError, "exact frozen candidate files"):
            module.verify_candidate(self.candidate)

    def test_verify_candidate_rejects_reparse_member(self) -> None:
        self.freeze_fixture()
        original = module._is_reparse

        def simulated_reparse(metadata):
            return metadata.st_size == len(self.guide) or original(metadata)

        with (
            mock.patch.object(module, "_is_reparse", side_effect=simulated_reparse),
            self.assertRaisesRegex(module.BundleError, "reparse|non-regular"),
        ):
            module.verify_candidate(self.candidate)

    def test_finalize_creates_exactly_five_files_and_four_checksum_lines(self) -> None:
        identity, final = self.finalize_fixture()
        self.assertEqual(tuple(sorted(path.name for path in final.iterdir())), tuple(sorted(module.FINAL_FILES)))
        lines = (final / module.SHA256SUMS_NAME).read_text("utf-8").splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(" *" in line for line in lines))
        self.assertFalse(any(module.SHA256SUMS_NAME in line for line in lines))
        manifest_raw = (final / module.MANIFEST_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        self.assertEqual(manifest_raw, module.canonical_json_bytes(manifest))
        self.assertEqual(manifest["build_id"], identity.build_id)
        self.assertNotIn("manifest_sha256", json.dumps(manifest))
        self.assertTrue(manifest["git"]["dirty"])
        self.assertTrue(manifest["content"]["ready"])
        self.assertEqual(manifest["player"]["added_character_ids"], ["129999", "139999", "149999"])
        self.assertTrue(manifest["apk"]["verified"])
        self.assertEqual(manifest["evidence_sha256"], identity.evidence_sha256)
        self.assertTrue(manifest["device_acceptance"]["accepted"])
        self.assertEqual(
            manifest["device_acceptance"]["evidence_sha256"],
            identity.evidence_sha256,
        )

    def test_manifest_keeps_three_versions_roots_and_every_entry(self) -> None:
        evidence = self.evidence(entry_count=module.PRODUCTION_ENTRY_COUNT)
        evidence["data"]["roots"] = {
            "common": {
                "count": module.PRODUCTION_ROOT_COUNTS["common"],
                "bytes": 1,
                "archive_prefix": module.ROOT_PREFIXES["common"],
            },
            "medium": {
                "count": module.PRODUCTION_ROOT_COUNTS["medium"],
                "bytes": 2,
                "archive_prefix": module.ROOT_PREFIXES["medium"],
            },
            "android": {
                "count": module.PRODUCTION_ROOT_COUNTS["android"],
                "bytes": 3,
                "archive_prefix": module.ROOT_PREFIXES["android"],
            },
        }
        # The production contract is validated independently from fixture ZIP bytes.
        validated = module.validate_release_evidence(evidence, verify_entry_roots=False)
        self.assertEqual(len(validated["data"]["entries"]), 138291)
        self.assertEqual(
            validated["versions"],
            {
                "output_resource_version": "1.4.196",
                "snapshot_version": "1.4.196",
                "source_resource_version": "1.4.54",
            },
        )
        self.assertEqual(set(validated["data"]["roots"]), {"common", "medium", "android"})
        self.assertEqual(
            set(validated["source_fingerprint"]),
            {"before", "scan", "after", "unchanged"},
        )

    def test_source_fingerprint_requires_exact_three_equal_checkpoints_and_production_counts(self) -> None:
        patch_contract = (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
        )
        valid = self.evidence()
        with patch_contract[0], patch_contract[1]:
            validated = module.validate_release_evidence(valid)
        self.assertTrue(validated["source_fingerprint"]["unchanged"])

        cases: list[tuple[str, dict[str, object], str]] = []
        missing_checkpoint = self.evidence()
        missing_checkpoint["source_fingerprint"].pop("scan")
        cases.append(("missing scan", missing_checkpoint, "source_fingerprint schema"))
        extra_checkpoint_field = self.evidence()
        extra_checkpoint_field["source_fingerprint"]["before"]["unexpected"] = True
        cases.append(("checkpoint extra field", extra_checkpoint_field, "checkpoint schema"))
        drifted_hash = self.evidence()
        drifted_hash["source_fingerprint"]["after"]["store_tree_sha256"] = "ff" * 32
        cases.append(("hash drift", drifted_hash, "fingerprint.*changed"))
        drifted_size = self.evidence()
        drifted_size["source_fingerprint"]["scan"]["store_total_bytes"] += 1
        cases.append(("size drift", drifted_size, "fingerprint.*changed"))
        bad_counts = self.evidence()
        bad_counts["source_fingerprint"]["before"]["store_counts"]["common"] = 2
        cases.append(("count mismatch", bad_counts, "store_counts"))
        false_unchanged = self.evidence()
        false_unchanged["source_fingerprint"]["unchanged"] = False
        cases.append(("unchanged false", false_unchanged, "unchanged"))

        for name, evidence, message in cases:
            with self.subTest(name=name):
                with (
                    mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
                    mock.patch.object(
                        module,
                        "PRODUCTION_ROOT_COUNTS",
                        {"common": 1, "medium": 1, "android": 1},
                    ),
                    self.assertRaisesRegex(module.BundleError, message),
                ):
                    module.validate_release_evidence(evidence)

    def test_release_evidence_accepts_the_real_task11_report_contract(self) -> None:
        task11 = load_task11_module()
        report = task11.ApkBuildReport(
            output_sha256=sha256(self.apk.read_bytes()),
            certificate_sha256="40" * 32,
            patch_order=task11.PATCH_ORDER,
            stage_reports=(),
            full_resource_version="1.4.196",
            aligned=True,
            signature_schemes={"v1": True, "v2": True, "v3": True},
            verified=True,
        )
        evidence = self.evidence()
        evidence["patches"]["order"] = list(report.patch_order)
        evidence["signer"]["certificate_sha256"] = report.certificate_sha256
        evidence["apk"] = {
            "output_sha256": report.output_sha256,
            "certificate_sha256": report.certificate_sha256,
            "full_resource_version": report.full_resource_version,
            "aligned": report.aligned,
            "signature_schemes": dict(report.signature_schemes),
            "verified": report.verified,
        }
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
        ):
            validated = module.validate_release_evidence(evidence)
        self.assertEqual(module.PATCH_ORDER, task11.PATCH_ORDER)
        self.assertEqual(tuple(validated["patches"]["order"]), task11.PATCH_ORDER)

    def test_manifest_rejects_entry_count_and_absolute_or_secret_evidence(self) -> None:
        with self.assertRaisesRegex(module.BundleError, "138291"):
            module.validate_release_evidence(self.evidence())
        unsafe = self.evidence(entry_count=module.PRODUCTION_ENTRY_COUNT)
        unsafe["tool_path"] = r"D:\android\apksigner.bat"
        with self.assertRaisesRegex(module.BundleError, "sensitive field"):
            module.validate_release_evidence(unsafe, verify_entry_roots=False)
        unsafe = self.evidence(entry_count=module.PRODUCTION_ENTRY_COUNT)
        unsafe["note"] = "/home/tester/private.key"
        with self.assertRaisesRegex(module.BundleError, "absolute path"):
            module.validate_release_evidence(unsafe, verify_entry_roots=False)
        unsafe = self.evidence()
        unsafe["source_apk"]["manifest_sha256"] = "aa" * 32
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "self hash"),
        ):
            module.validate_release_evidence(unsafe)

        unknown = self.evidence()
        unknown["unexpected_evidence"] = True
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "unknown.*fields|schema"),
        ):
            module.validate_release_evidence(unknown)

    def test_manifest_binds_root_and_total_entry_bytes(self) -> None:
        unsafe = self.evidence()
        unsafe["data"]["roots"]["common"]["bytes"] += 1
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "root byte"),
        ):
            module.validate_release_evidence(unsafe)
        unsafe = self.evidence()
        unsafe["data"]["total_uncompressed_bytes"] += 1
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "total.*bytes"),
        ):
            module.validate_release_evidence(unsafe)

    def test_secret_scan_finds_utf8_utf16_and_nested_archives_without_echo(self) -> None:
        secret = "fixture-Pass-2468"
        nested = self.root / "nested.zip"
        write_zip(
            nested,
            {
                "plain.txt": secret.encode("utf-8"),
                "wide.txt": secret.encode("utf-16le"),
            },
        )
        outer = self.root / "scan"
        outer.mkdir()
        write_zip(outer / "payload.apk", {"assets/nested.zip": nested.read_bytes()})
        findings = module.scan_release_for_secrets(outer, secret_values=(secret,))
        self.assertGreaterEqual(len(findings), 2)
        self.assertTrue(all(secret not in finding.summary for finding in findings))
        self.assertTrue(all(not Path(finding.relative_path).is_absolute() for finding in findings))
        self.assertTrue(any(finding.container_member for finding in findings))
        self.assertTrue(all(finding.content_sha256 for finding in findings))
        self.assertTrue(all(finding.content_size is not None for finding in findings))

    def test_release_secret_policy_allows_only_exact_pinned_baseline(self) -> None:
        member = "lib/arm64-v8a/libCore.so"
        payload = b"prefix\n-----BEGIN ENCRYPTED PRIVATE KEY-----\nsuffix\n"
        scan = self.root / "baseline-scan"
        scan.mkdir()
        write_zip(
            scan / module.APK_NAME,
            {member: payload},
            compression=zipfile.ZIP_DEFLATED,
        )
        expected = (
            (
                module.APK_NAME,
                member,
                "private-key-marker",
                sha256(payload),
                len(payload),
            ),
        )
        with mock.patch.object(module, "_PINNED_BASELINE_SECRET_FINDINGS", expected):
            findings = module.scan_release_for_secrets(scan)
            report = module.validate_release_secret_findings(findings)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].content_sha256, sha256(payload))
        self.assertEqual(findings[0].content_size, len(payload))
        self.assertEqual(
            report,
            {
                "secret_finding_count": 0,
                "baseline_secret_finding_count": 1,
                "baseline_secret_verified": True,
                "raw_secret_finding_count": 1,
            },
        )

    def test_exact_pinned_baseline_survives_freeze_finalize_and_verify(self) -> None:
        member = "lib/arm64-v8a/libCore.so"
        payload = b"prefix\n-----BEGIN ENCRYPTED PRIVATE KEY-----\nsuffix\n"
        self.apk.unlink()
        write_zip(
            self.apk,
            {
                "AndroidManifest.xml": b"manifest",
                "assets/worldflipper_android_release.swf": b"patched-swf",
                member: payload,
            },
            compression=zipfile.ZIP_DEFLATED,
        )
        expected = (
            (
                module.APK_NAME,
                member,
                "private-key-marker",
                sha256(payload),
                len(payload),
            ),
        )
        with (
            mock.patch.object(module, "_PINNED_BASELINE_SECRET_FINDINGS", expected),
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
        ):
            identity = module.freeze_candidate(
                self.apk,
                self.data_zip,
                self.guide,
                self.candidate,
                build_id=self.build_id,
                release_evidence=self.evidence(),
            )
            receipt = self.write_receipt(identity)
            output = module.finalize_candidate(self.candidate, receipt, self.final_dir)
            self.assertEqual(module.verify_final_bundle(output), identity)

    def test_release_secret_policy_rejects_pin_drift_and_extra_findings(self) -> None:
        member = "lib/arm64-v8a/libCore.so"
        payload = b"prefix\n-----BEGIN RSA PRIVATE KEY-----\nsuffix\n"
        scan = self.root / "baseline-drift"
        scan.mkdir()
        apk = scan / module.APK_NAME
        write_zip(apk, {member: payload}, compression=zipfile.ZIP_DEFLATED)
        findings = module.scan_release_for_secrets(scan)
        exact = (
            (
                module.APK_NAME,
                member,
                "private-key-marker",
                sha256(payload),
                len(payload),
            ),
        )
        drifted = (
            (("renamed.apk", member, "private-key-marker", sha256(payload), len(payload)),),
            ((module.APK_NAME, member, "private-key-marker", "0" * 64, len(payload)),),
            ((module.APK_NAME, "lib/arm64-v8a/other.so", "private-key-marker", sha256(payload), len(payload)),),
            ((module.APK_NAME, member, "configured-secret", sha256(payload), len(payload)),),
            ((module.APK_NAME, member, "private-key-marker", sha256(payload), len(payload) + 1),),
            exact + exact,
        )
        for expected in drifted:
            with (
                self.subTest(expected=expected),
                mock.patch.object(module, "_PINNED_BASELINE_SECRET_FINDINGS", expected),
                self.assertRaisesRegex(module.BundleError, "secret scan failed"),
            ):
                module.validate_release_secret_findings(findings)
        with (
            mock.patch.object(module, "_PINNED_BASELINE_SECRET_FINDINGS", exact),
            self.assertRaisesRegex(module.BundleError, "finding_count=0"),
        ):
            module.validate_release_secret_findings(())

        extra = scan / "extra.txt"
        configured = "fixture-configured-secret-2468"
        extra.write_text(configured, encoding="utf-8")
        with (
            mock.patch.object(module, "_PINNED_BASELINE_SECRET_FINDINGS", exact),
            self.assertRaisesRegex(module.BundleError, "finding_count=2"),
        ):
            module.validate_release_secret_findings(
                module.scan_release_for_secrets(scan, secret_values=(configured,))
            )

        for index, members in enumerate(
            (
                {
                    member: payload,
                    "lib/arm64-v8a/extra.so": b"-----BEGIN PRIVATE KEY-----",
                },
                {
                    member: payload,
                    "assets/keys/release.p12": b"placeholder",
                },
            )
        ):
            extra_scan = self.root / f"baseline-extra-{index}"
            extra_scan.mkdir()
            write_zip(
                extra_scan / module.APK_NAME,
                members,
                compression=zipfile.ZIP_DEFLATED,
            )
            with (
                self.subTest(extra=index),
                mock.patch.object(module, "_PINNED_BASELINE_SECRET_FINDINGS", exact),
                self.assertRaisesRegex(module.BundleError, "finding_count=2"),
            ):
                module.validate_release_secret_findings(
                    module.scan_release_for_secrets(extra_scan)
                )

    def test_release_secret_policy_rejects_stored_raw_archive_finding(self) -> None:
        member = "lib/arm64-v8a/libCore.so"
        payload = b"prefix\n-----BEGIN EC PRIVATE KEY-----\nsuffix\n"
        scan = self.root / "stored-baseline"
        scan.mkdir()
        write_zip(scan / module.APK_NAME, {member: payload})
        expected = (
            (
                module.APK_NAME,
                member,
                "private-key-marker",
                sha256(payload),
                len(payload),
            ),
        )
        findings = module.scan_release_for_secrets(scan)
        self.assertEqual(len(findings), 2)
        self.assertTrue(any(finding.container_member is None for finding in findings))
        with (
            mock.patch.object(module, "_PINNED_BASELINE_SECRET_FINDINGS", expected),
            self.assertRaisesRegex(module.BundleError, "finding_count=2"),
        ):
            module.validate_release_secret_findings(findings)

    def test_production_secret_pin_matches_accepted_base_lock(self) -> None:
        self.assertIsNotNone(PRODUCTION_PINNED_BASELINE_SECRET_FINDINGS)
        lock = json.loads(
            (require_external_source(client_patch_path('offline-android/base-lock.json'))).read_text(
                encoding="utf-8"
            )
        )
        member = "lib/arm64-v8a/libCore.so"
        record = lock["native_members"][member]
        self.assertEqual(
            PRODUCTION_PINNED_BASELINE_SECRET_FINDINGS,
            (
                (
                    module.APK_NAME,
                    member,
                    "private-key-marker",
                    record["sha256"],
                    record["size"],
                ),
            ),
        )

    def test_secret_scan_rejects_key_names_pem_markers_and_malformed_archives(self) -> None:
        scan = self.root / "scan"
        scan.mkdir()
        (scan / "secret_observer.txt").write_text("generic secret text is harmless", encoding="utf-8")
        self.assertEqual(module.scan_release_for_secrets(scan), ())

        prohibited = ("release.jks", "release.keystore", "release.p12", "release.pfx", "release.pem", "release.key", "keystore-pass.txt")
        for index, name in enumerate(prohibited):
            (scan / name).write_bytes(b"placeholder")
            findings = module.scan_release_for_secrets(scan)
            self.assertTrue(any(item.rule_id == "credential-filename" for item in findings), name)
            (scan / name).unlink()
        (scan / "marker.txt").write_bytes(b"-----BEGIN PRIVATE KEY-----")
        self.assertTrue(any(item.rule_id == "private-key-marker" for item in module.scan_release_for_secrets(scan)))
        (scan / "marker.txt").unlink()
        (scan / "broken.apk").write_bytes(b"not-a-zip")
        with self.assertRaisesRegex(module.BundleError, "archive"):
            module.scan_release_for_secrets(scan)

    def test_secret_scan_checks_archive_member_names(self) -> None:
        scan = self.root / "scan"
        scan.mkdir()
        write_zip(scan / "release.apk", {"assets/keys/release.p12": b"placeholder"})
        findings = module.scan_release_for_secrets(scan)
        self.assertEqual(findings[0].rule_id, "credential-filename")
        self.assertEqual(findings[0].relative_path, "release.apk")
        self.assertEqual(findings[0].container_member, "assets/keys/release.p12")

    def test_secret_scan_binds_archive_to_the_already_open_file_identity(self) -> None:
        scan = self.root / "scan"
        scan.mkdir()
        archive_path = scan / "release.apk"
        replacement = self.root / "replacement.apk"
        write_zip(archive_path, {"assets/original.txt": b"original"})
        write_zip(replacement, {"assets/replacement.txt": b"replacement"})
        original_scan = module._scan_archive

        def replace_before_archive_read(source, **kwargs):
            os.replace(replacement, archive_path)
            return original_scan(source, **kwargs)

        with (
            mock.patch.object(module, "_scan_archive", side_effect=replace_before_archive_read),
            self.assertRaisesRegex(module.BundleError, "drift|read|scan"),
        ):
            module.scan_release_for_secrets(scan)

    def test_secret_scan_reparse_fails_closed(self) -> None:
        scan = self.root / "scan"
        scan.mkdir()
        target = scan / "target.txt"
        target.write_text("ok", encoding="utf-8")
        link = scan / "linked.txt"
        try:
            link.symlink_to(target)
        except OSError:
            target_identity = target.lstat().st_ino
            original = module._is_reparse

            def simulated(metadata):
                return metadata.st_ino == target_identity or original(metadata)

            with (
                mock.patch.object(module, "_is_reparse", side_effect=simulated),
                self.assertRaisesRegex(module.BundleError, "reparse|symlink"),
            ):
                module.scan_release_for_secrets(scan)
        else:
            with self.assertRaisesRegex(module.BundleError, "reparse|symlink"):
                module.scan_release_for_secrets(scan)

    def test_secret_scan_unreadable_fails_closed_without_echo(self) -> None:
        scan = self.root / "scan"
        scan.mkdir()
        target = scan / "target.txt"
        target.write_text("ok", encoding="utf-8")
        original_open = module._open_regular_for_scan

        def unreadable(path: Path):
            if path.name == "target.txt":
                raise PermissionError("fixture password must not be echoed")
            return original_open(path)

        with mock.patch.object(module, "_open_regular_for_scan", side_effect=unreadable):
            with self.assertRaises(module.BundleError) as raised:
                module.scan_release_for_secrets(scan)
        self.assertNotIn("fixture password", str(raised.exception))

    def test_secret_failure_summary_never_echoes_matching_value(self) -> None:
        secret = "fixture-Pass-2468"
        scan = self.root / "scan"
        scan.mkdir()
        (scan / f"{secret}.txt").write_text(secret, encoding="utf-8")
        findings = module.scan_release_for_secrets(scan, secret_values=(secret,))
        with self.assertRaises(module.BundleError) as raised:
            module._require_no_findings(findings)
        self.assertNotIn(secret, str(raised.exception))

    def test_every_error_path_scrubs_secret_from_a_malformed_apk_filename(self) -> None:
        secret = "fixture-Pass-2468"
        scan = self.root / "scan"
        scan.mkdir()
        (scan / f"{secret}.apk").write_bytes(b"not-a-zip")
        with mock.patch.dict(os.environ, {module.PASSWORD_ENV: secret}):
            with self.assertRaises(module.BundleError) as raised:
                module.scan_release_for_secrets(scan, secret_values=(secret,))
        self.assertNotIn(secret, str(raised.exception))

    def test_archive_scan_enforces_member_and_total_uncompressed_budgets(self) -> None:
        scan = self.root / "scan"
        scan.mkdir()
        archive = scan / "release.apk"
        write_zip(archive, {"one.txt": b"1234", "two.txt": b"5678"})
        with (
            mock.patch.object(module, "MAX_ARCHIVE_MEMBERS", 1),
            self.assertRaisesRegex(module.BundleError, "member.*budget"),
        ):
            module.scan_release_for_secrets(scan)
        with (
            mock.patch.object(module, "MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES", 7),
            self.assertRaisesRegex(module.BundleError, "uncompressed.*budget"),
        ):
            module.scan_release_for_secrets(scan)

    def test_archive_scan_fails_closed_on_crc_and_declared_size_drift(self) -> None:
        scan = self.root / "scan"
        scan.mkdir()
        payload = b"unique-crc-payload-2468"
        archive = scan / "release.apk"
        write_zip(archive, {"payload.txt": payload})
        damaged = bytearray(archive.read_bytes())
        offset = damaged.index(payload)
        damaged[offset] ^= 0x01
        archive.write_bytes(damaged)
        with self.assertRaisesRegex(module.BundleError, "safely scan archive"):
            module.scan_release_for_secrets(scan)

        archive.unlink()
        write_zip(archive, {"payload.txt": payload})
        original_infolist = zipfile.ZipFile.infolist

        def drifted_infolist(opened: zipfile.ZipFile):
            infos = original_infolist(opened)
            infos[0].file_size += 1
            return infos

        with (
            mock.patch.object(zipfile.ZipFile, "infolist", new=drifted_infolist),
            self.assertRaises(module.BundleError),
        ):
            module.scan_release_for_secrets(scan)

    def test_receipt_rejects_raw_device_fields_and_nonclean_probe(self) -> None:
        identity = self.freeze_fixture()
        bad = self.receipt(identity)
        bad["probe"]["serial"] = "127.0.0.1:16384"
        receipt = self.root / "bad-device.json"
        receipt.write_bytes(module.canonical_json_bytes(bad))
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "probe schema"),
        ):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)
        bad = self.receipt(identity)
        bad["probe"]["save_haxe_present_before"] = True
        receipt.write_bytes(module.canonical_json_bytes(bad))
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "clean device"),
        ):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)

    def test_receipt_accepts_an_explicit_utc_offset_timestamp(self) -> None:
        identity = module.CandidateIdentity(
            self.build_id,
            sha256(self.apk.read_bytes()),
            sha256(self.data_zip.read_bytes()),
            sha256(self.guide),
            sha256(module.canonical_json_bytes(self.evidence())),
        )
        receipt = self.receipt(identity)
        receipt["accepted_at_utc"] = "2026-07-21T00:00:00+00:00"
        validated = module._validated_receipt(receipt, identity)
        self.assertEqual(validated["accepted_at_utc"], "2026-07-21T00:00:00+00:00")

    def test_final_directory_cannot_be_nested_inside_candidate(self) -> None:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)
        nested = self.candidate / "nested-final"
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "overlap"),
        ):
            module.finalize_candidate(self.candidate, receipt, nested)
        self.assertFalse(nested.exists())

    def test_candidate_hash_drift_and_receipt_binding_fail_before_final(self) -> None:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)
        (self.candidate / module.APK_NAME).write_bytes(b"drift")
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "hash drift"),
        ):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)
        self.assertFalse(self.final_dir.exists())

        (self.candidate / module.APK_NAME).write_bytes(self.apk.read_bytes())
        bad = self.receipt(identity)
        bad["data_zip_sha256"] = "ff" * 32
        receipt.write_bytes(module.canonical_json_bytes(bad))
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "receipt.*mismatch"),
        ):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)
        self.assertFalse(self.final_dir.exists())

    def test_default_receipt_reader_rejects_drift_during_snapshot(self) -> None:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)
        original_open = Path.open

        class MutatingReader:
            def __init__(self, stream) -> None:
                self.stream = stream

            def __enter__(self):
                self.stream.__enter__()
                return self

            def __exit__(self, exc_type, exc, traceback):
                result = self.stream.__exit__(exc_type, exc, traceback)
                with original_open(receipt, "ab") as writer:
                    writer.write(b" ")
                    writer.flush()
                    os.fsync(writer.fileno())
                return result

            def __getattr__(self, name):
                return getattr(self.stream, name)

        def drift_open(path: Path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            mode = args[0] if args else kwargs.get("mode", "r")
            if path == receipt and mode == "rb":
                return MutatingReader(stream)
            return stream

        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            mock.patch.object(Path, "open", new=drift_open),
            self.assertRaisesRegex(module.BundleError, "drift"),
        ):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)
        self.assertFalse(self.final_dir.exists())

    def test_receipt_validator_is_injected_without_importing_device_module(self) -> None:
        identity = self.freeze_fixture()
        receipt_path = self.root / "opaque-receipt.bin"
        receipt_path.write_bytes(b"opaque")
        calls: list[tuple[Path, module.CandidateIdentity]] = []

        def validator(path: Path, expected: module.CandidateIdentity):
            calls.append((path, expected))
            return self.receipt(expected)

        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
        ):
            module.finalize_candidate(
                self.candidate,
                receipt_path,
                self.final_dir,
                receipt_validator=validator,
            )
        self.assertEqual(calls, [(receipt_path, identity)])

    def test_existing_final_and_cross_volume_are_never_overwritten(self) -> None:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)
        self.final_dir.mkdir()
        sentinel = self.final_dir / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(module.BundleError, "already exists"):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)
        self.assertEqual(sentinel.read_text("utf-8"), "keep")
        self.final_dir.rmdir() if not any(self.final_dir.iterdir()) else None

        # Use a fresh destination name and inject different volume identities.
        other = self.root / "other-final"
        with (
            mock.patch.object(module, "_volume_identity", side_effect=[1, 2]),
            self.assertRaisesRegex(module.BundleError, "same volume"),
        ):
            module.finalize_candidate(self.candidate, receipt, other)
        self.assertFalse(other.exists())

    def test_publish_race_preserves_competitor_and_cleans_only_owned_temp(self) -> None:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)

        def race(
            owned: module._OwnedDirectory,
            parent: module._OwnedDirectory,
            destination: Path,
        ) -> None:
            destination.mkdir()
            (destination / "competitor.txt").write_text("keep", encoding="utf-8")
            raise module.BundleError("publication race")

        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            mock.patch.object(module, "_publish_owned_directory_no_replace", side_effect=race),
            self.assertRaisesRegex(module.BundleError, "publication race"),
        ):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)
        self.assertEqual((self.final_dir / "competitor.txt").read_text("utf-8"), "keep")
        self.assertFalse(any(path.name.startswith(f".{self.final_dir.name}.finalizing-") for path in self.root.iterdir()))

    def test_cancel_does_not_delete_a_replacement_at_owned_temp_name(self) -> None:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)
        replacement: list[Path] = []
        rename_blocked: list[bool] = []

        def cancel(
            owned: module._OwnedDirectory,
            parent: module._OwnedDirectory,
            destination: Path,
        ) -> None:
            source = owned.path
            stolen = source.with_name(source.name + "-stolen")
            try:
                os.rename(source, stolen)
            except OSError:
                rename_blocked.append(True)
            else:
                source.mkdir()
                (source / "competitor.txt").write_text("keep", encoding="utf-8")
                replacement.append(source)
            raise KeyboardInterrupt()

        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            mock.patch.object(module, "_publish_owned_directory_no_replace", side_effect=cancel),
            self.assertRaises(KeyboardInterrupt),
        ):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)
        if replacement:
            self.assertEqual((replacement[0] / "competitor.txt").read_text("utf-8"), "keep")
        else:
            self.assertEqual(rename_blocked, [True])
        self.assertFalse(self.final_dir.exists())

    def test_verified_temp_cannot_be_replaced_before_handle_bound_publication(self) -> None:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)
        original_verify = module.verify_final_bundle
        replacements: list[Path] = []

        def verify_then_replace(path: Path):
            result = original_verify(path)
            stolen = path.with_name(path.name + "-stolen")
            try:
                os.rename(path, stolen)
            except OSError:
                return result
            replacements.append(stolen)
            path.mkdir()
            (path / "competitor.txt").write_text("unverified", encoding="utf-8")
            return result

        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            mock.patch.object(module, "verify_final_bundle", side_effect=verify_then_replace),
        ):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)
        self.assertEqual(replacements, [])
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
        ):
            self.assertEqual(original_verify(self.final_dir), identity)
        self.assertEqual(set(path.name for path in self.final_dir.iterdir()), set(module.FINAL_FILES))

    def test_cleanup_never_recursively_deletes_an_unbound_path(self) -> None:
        identity = self.freeze_fixture()
        receipt = self.write_receipt(identity)
        path_rmtree_calls: list[Path] = []
        original_rmtree = shutil.rmtree

        def replace_after_check_then_rmtree(path: Path) -> None:
            path = Path(path)
            stolen = path.with_name(path.name + "-stolen")
            os.rename(path, stolen)
            path.mkdir()
            (path / "competitor.txt").write_text("keep", encoding="utf-8")
            path_rmtree_calls.append(path)
            original_rmtree(path)

        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            mock.patch.object(module, "_write_five_files", side_effect=RuntimeError("fixture failure")),
            mock.patch.object(shutil, "rmtree", side_effect=replace_after_check_then_rmtree),
            self.assertRaisesRegex(RuntimeError, "fixture failure"),
        ):
            module.finalize_candidate(self.candidate, receipt, self.final_dir)
        self.assertEqual(path_rmtree_calls, [])

    def test_verify_final_bundle_detects_layout_checksum_and_manifest_tamper(self) -> None:
        identity, final = self.finalize_fixture()
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
        ):
            self.assertEqual(module.verify_final_bundle(final), identity)

        extra = final / "extra.txt"
        extra.write_text("bad", encoding="utf-8")
        with self.assertRaisesRegex(module.BundleError, "exactly five"):
            module.verify_final_bundle(final)
        extra.unlink()
        manifest = final / module.MANIFEST_NAME
        manifest.write_bytes(manifest.read_bytes() + b" ")
        with self.assertRaisesRegex(module.BundleError, "canonical|checksum"):
            module.verify_final_bundle(final)

    def test_verify_final_bundle_rejects_valid_schema_evidence_tamper_with_rebuilt_checksums(self) -> None:
        _, final = self.finalize_fixture()
        manifest_path = final / module.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text("utf-8"))
        manifest["git"]["dirty"] = False
        manifest_path.write_bytes(module.canonical_json_bytes(manifest))
        (final / module.SHA256SUMS_NAME).write_bytes(module.build_sha256sums(final))
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
            self.assertRaisesRegex(module.BundleError, "release evidence hash mismatch"),
        ):
            module.verify_final_bundle(final)

    def test_verify_final_bundle_reports_missing_manifest_evidence_as_bundle_error(self) -> None:
        _, final = self.finalize_fixture()
        manifest_path = final / module.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text("utf-8"))
        manifest.pop("source_fingerprint")
        manifest_path.write_bytes(module.canonical_json_bytes(manifest))
        (final / module.SHA256SUMS_NAME).write_bytes(module.build_sha256sums(final))
        with (
            mock.patch.object(module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(module, "PRODUCTION_ROOT_COUNTS", {"common": 1, "medium": 1, "android": 1}),
            self.assertRaisesRegex(module.BundleError, "missing"),
        ):
            module.verify_final_bundle(final)

    def test_build_sha256sums_is_stable_lf_and_excludes_itself(self) -> None:
        root = self.root / "hashes"
        root.mkdir()
        for name, payload in (
            (module.APK_NAME, b"apk"),
            (module.DATA_ZIP_NAME, b"zip"),
            (module.GUIDE_NAME, b"guide"),
            (module.MANIFEST_NAME, b"manifest"),
        ):
            (root / name).write_bytes(payload)
        raw = module.build_sha256sums(root)
        self.assertEqual(raw.count(b"\n"), 4)
        self.assertNotIn(b"\r", raw)
        self.assertNotIn(module.SHA256SUMS_NAME.encode("utf-8"), raw)
        self.assertEqual(raw, module.build_sha256sums(root))


if __name__ == "__main__":
    unittest.main()

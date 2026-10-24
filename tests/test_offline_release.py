from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from unittest import mock


MOD_TOOLS = Path(__file__).resolve().parents[1]
if str(MOD_TOOLS) not in sys.path:
    sys.path.insert(0, str(MOD_TOOLS))

import wf_offline_release as module  # noqa: E402
import wf_offline_bundle as bundle_contract  # noqa: E402


EXPECTED_STAGES = (
    "preflight",
    "scan-store",
    "legacy-tail-gates",
    "copy-snapshot",
    "player-overlay",
    "content-data-gates",
    "build-apk",
    "content-client-gate",
    "build-zip",
    "verify-zip",
    "render-guide",
    "freeze-candidate",
    "secret-scan",
)

COMMANDS = (
    "preflight",
    "build-candidate",
    "device-probe",
    "prepare-device",
    "device-accept",
    "finalize",
    "verify",
    "init-signer",
)

FINAL_FILES = (
    "WorldFlipper-离线整合版.apk",
    "WorldFlipper-数据-1.4.196.zip",
    "导入说明.txt",
    "build-manifest.json",
    "SHA256SUMS.txt",
)

CANDIDATE_FILES = (
    "WorldFlipper-离线整合版.apk",
    "WorldFlipper-数据-1.4.196.zip",
    "导入说明.txt",
    ".candidate-evidence.json",
)

REQUIRED_MANUAL_CHECKS = (
    "home_party_character_list_open",
    "original_character_1_and_129999_139999_149999_owned",
    "all_three_characters_enter_battle_and_use_skill",
    "seris_dual_form_skill_powerflip_results_stable",
    "gerald_scale_list_party_battle_correct",
    "rush_700099_round_reward_token_confirmed",
    "all_15_weapons_visible_one_obtained_and_equipped",
    "weapon_effect_whitelist_and_non_whitelist_confirmed",
    "save_button_force_stop_restart_restores_progress",
    "airplane_mode_held_no_companion_service",
)

BUILD_ID = "fixture-build-001"
BUILD_ID_B = "fixture-build-002"
SERIAL = "127.0.0.1:16384"
EXPECTED_BASE_APK_SHA256 = (
    "4f6884f33641788108c0522c7c70036c63ba530e1fdb183105b3cd395bdd66f6"
)
STORE_TREE_SHA256 = "31" * 32
APK_BYTES = b"fixture-signed-offline-apk"
DATA_ZIP_BYTES = b"fixture-data-zip"
GUIDE_BYTES = "离线导入说明\n".encode("utf-8")
INDEPENDENT_EVIDENCE = {
    "apk": {
        "aligned": True,
        "offline_baseline_verified": True,
        "patch_gate_count": 4,
        "signature_schemes": {"v1": True, "v2": True, "v3": True},
    },
    "content": {"ready": True, "client_gate_ready": True},
    "data": {"member_count": 138_291, "zip64": True},
    "legacy_tail": {"missing_count": 0, "tail_member_count": 12},
    "secret_finding_count": 0,
    "baseline_secret_finding_count": 1,
    "baseline_secret_verified": True,
    "raw_secret_finding_count": 1,
    "source_fingerprint": {"unchanged": True},
}

PINNED_BASELINE_FINDINGS = tuple(
    bundle_contract.SecretFinding(
        relative_path,
        container_member,
        rule_id,
        "accepted immutable baseline marker",
        content_sha256,
        content_size,
    )
    for (
        relative_path,
        container_member,
        rule_id,
        content_sha256,
        content_size,
    ) in bundle_contract._PINNED_BASELINE_SECRET_FINDINGS
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def top_level_json_keys(raw: str) -> list[str]:
    parsed = json.loads(raw, object_pairs_hook=lambda pairs: pairs)
    if not isinstance(parsed, list):
        raise AssertionError("final line is not a JSON object")
    return [str(pair[0]) for pair in parsed]


class FakeServices:
    """Small-fixture service boundary; no real builder, store, or ADB is used."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.version_root = config.output_root / config.snapshot_version
        self.candidate_dir = self.version_root / f".candidate-{BUILD_ID}"
        self.final_dir = self.version_root / "WF离线整合版"
        self.calls: list[str] = []
        self.timeline: list[str] = []
        self.source_reads = 0
        self.source_drift: str | None = None
        self.signer_ready = True
        self.disk_free_bytes = 4_000_000
        self.disk_required_bytes = 2_000_000
        self.source_apk_sha256 = EXPECTED_BASE_APK_SHA256
        self.expected_source_apk_sha256 = EXPECTED_BASE_APK_SHA256
        self.scan_store_tree_sha256 = STORE_TREE_SHA256
        self.raise_stage: str | None = None
        self.interrupt_stage: str | None = None
        self.failure_operation: str | None = None
        self.failure_text = "fixture service failure"
        self.live_publish_calls: list[str] = []
        self.manual_checks_seen: Mapping[str, bool] | None = None
        self.receipt_identity_seen: Mapping[str, str] | None = None
        self.staging_dirs_seen: list[Path] = []
        self.identity = {
            "build_id": BUILD_ID,
            "apk_sha256": sha256(APK_BYTES),
            "data_zip_sha256": sha256(DATA_ZIP_BYTES),
            "guide_sha256": sha256(GUIDE_BYTES),
            "evidence_sha256": "ef" * 32,
        }

    def _maybe_fail(self, operation: str) -> None:
        if self.failure_operation == operation:
            raise module.ReleaseError(self.failure_text)

    def _report(self, name: str, **evidence: Any) -> dict[str, Any]:
        return {
            "name": name,
            "status": "ok",
            "evidence": evidence or {"fixture": True},
        }

    def _stage(self, name: str, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self.calls.append(name)
        self.timeline.append(name)
        self._maybe_fail(name)
        if self.raise_stage == name:
            raise RuntimeError(self.failure_text)
        if name == "copy-snapshot":
            owned = [
                path
                for path in self.version_root.glob(".staging-*")
                if path.name != ".staging-competitor"
            ]
            if len(owned) != 1:
                raise AssertionError("orchestrator did not create one owned staging directory")
            self.staging_dirs_seen.append(owned[0])
            (owned[0] / "fake-stage.txt").write_text("owned", encoding="utf-8")
        if self.interrupt_stage == name:
            raise KeyboardInterrupt(f"cancel during {name}")
        return self._report(name)

    def fingerprint_sources(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self.source_reads += 1
        self.timeline.append("fingerprint")
        apk_hash = self.source_apk_sha256
        store_hash = STORE_TREE_SHA256
        if self.source_reads > 1 and self.source_drift == "apk":
            apk_hash = "92" * 32
        if self.source_reads > 1 and self.source_drift == "store":
            store_hash = "93" * 32
        return {
            "source_apk_sha256": apk_hash,
            "store_tree_sha256": store_hash,
            "source_apk_size": len(b"small fixture; hash supplied by fake service"),
            "store_total_bytes": 987_654_321,
            "store_counts": dict(module.EXPECTED_STORE_COUNTS),
        }

    def preflight(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        report = self._stage(
            "preflight",
        )
        report["evidence"] = {
            "build_id": BUILD_ID,
            "signer_ready": self.signer_ready,
            "fingerprint_verified": self.signer_ready,
            "certificate_sha256": "ab" * 32,
            "disk_free_bytes": self.disk_free_bytes,
            "disk_required_bytes": self.disk_required_bytes,
            "source_apk_sha256": self.source_apk_sha256,
            "expected_source_apk_sha256": self.expected_source_apk_sha256,
            "store_counts": dict(module.EXPECTED_STORE_COUNTS),
            "legacy_count": module.EXPECTED_LEGACY_COUNT,
            "current_count": module.EXPECTED_CURRENT_COUNT,
            "added_count": module.EXPECTED_ADDED_COUNT,
            "missing_count": 0,
            "tail_member_count": module.EXPECTED_TAIL_COUNT,
        }
        return report

    def scan_store(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        report = self._stage("scan-store", *args, **kwargs)
        report["evidence"] = {
            "counts": dict(module.EXPECTED_STORE_COUNTS),
            "total_count": sum(module.EXPECTED_STORE_COUNTS.values()),
            "total_bytes": 987_654_321,
            "tree_sha256": self.scan_store_tree_sha256,
        }
        return report

    def legacy_tail_gates(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._stage("legacy-tail-gates", *args, **kwargs)

    def copy_snapshot(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._stage("copy-snapshot", *args, **kwargs)

    def player_overlay(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._stage("player-overlay", *args, **kwargs)

    def content_data_gates(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._stage("content-data-gates", *args, **kwargs)

    def build_apk(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._stage("build-apk", *args, **kwargs)

    def content_client_gate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._stage("content-client-gate", *args, **kwargs)

    def build_zip(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._stage("build-zip", *args, **kwargs)

    def verify_zip(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._stage("verify-zip", *args, **kwargs)

    def render_guide(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._stage("render-guide", *args, **kwargs)

    def freeze_candidate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        report = self._stage("freeze-candidate", *args, **kwargs)
        self.seed_candidate()
        report["evidence"] = {"identity": dict(self.identity)}
        return report

    def secret_scan(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        report = self._stage("secret-scan", *args, **kwargs)
        report["evidence"] = {"finding_count": 0}
        return report

    def seed_candidate(self) -> None:
        self.candidate_dir.mkdir(parents=True, exist_ok=False)
        payloads = {
            CANDIDATE_FILES[0]: APK_BYTES,
            CANDIDATE_FILES[1]: DATA_ZIP_BYTES,
            CANDIDATE_FILES[2]: GUIDE_BYTES,
            CANDIDATE_FILES[3]: json.dumps(
                {"identity": self.identity}, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            + b"\n",
        }
        for name, payload in payloads.items():
            (self.candidate_dir / name).write_bytes(payload)

    def seed_receipt(
        self,
        path: Path,
        *,
        identity: Mapping[str, str] | None = None,
    ) -> Path:
        selected = dict(identity or self.identity)
        document = {
            "build_id": selected["build_id"],
            "apk_sha256": selected["apk_sha256"],
            "data_zip_sha256": selected["data_zip_sha256"],
            "evidence_sha256": selected["evidence_sha256"],
            "checks": {name: True for name in REQUIRED_MANUAL_CHECKS},
            "accepted": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    def seed_final(self) -> None:
        self.final_dir.mkdir(parents=True, exist_ok=False)
        payloads = {
            FINAL_FILES[0]: APK_BYTES,
            FINAL_FILES[1]: DATA_ZIP_BYTES,
            FINAL_FILES[2]: GUIDE_BYTES,
            FINAL_FILES[3]: b'{"build_id":"fixture-build-001"}\n',
            FINAL_FILES[4]: b"fixture checksums\n",
        }
        for name, payload in payloads.items():
            (self.final_dir / name).write_bytes(payload)

    def load_candidate_identity(
        self, candidate_id: str, *_args: Any, **_kwargs: Any
    ) -> dict[str, str]:
        if candidate_id != BUILD_ID or not self.candidate_dir.is_dir():
            raise module.ReleaseError("candidate identity not found")
        return dict(self.identity)

    def validate_acceptance_receipt(
        self,
        receipt: Path,
        identity: Mapping[str, str],
        *_args: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        self.receipt_identity_seen = dict(identity)
        document = json.loads(Path(receipt).read_text(encoding="utf-8"))
        for key in ("build_id", "apk_sha256", "data_zip_sha256", "evidence_sha256"):
            if document.get(key) != identity[key]:
                raise module.ReleaseError(f"device receipt {key} identity mismatch")
        checks = document.get("checks")
        if checks != {name: True for name in REQUIRED_MANUAL_CHECKS}:
            raise module.ReleaseError("device receipt checks mismatch")
        return document

    def finalize_candidate(
        self,
        _candidate_dir: Path,
        _receipt: Path,
        final_dir: Path,
        *_args: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        self._maybe_fail("finalize")
        if final_dir != self.final_dir:
            raise AssertionError("unexpected final path")
        self.seed_final()
        return {"identity": dict(self.identity)}

    def verify_final_bundle(
        self, final_dir: Path, *_args: Any, **_kwargs: Any
    ) -> dict[str, str]:
        self._maybe_fail("verify")
        names = tuple(sorted(path.name for path in final_dir.iterdir()))
        if names != tuple(sorted(FINAL_FILES)):
            raise module.ReleaseError("final bundle must contain exactly five files")
        return dict(self.identity)

    def probe_device(
        self, candidate_id: str, serial: str, *_args: Any, **_kwargs: Any
    ) -> dict[str, Any]:
        self._maybe_fail("device-probe")
        if candidate_id != BUILD_ID or serial != SERIAL:
            raise module.ReleaseError("device target identity mismatch")
        return {
            "serial_digest": "44" * 32,
            "all_offline_gates": True,
            "candidate_identity": dict(self.identity),
        }

    def prepare_device(
        self,
        candidate_id: str,
        serial: str,
        confirmation: str,
        *_args: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        self._maybe_fail("prepare-device")
        expected = f"RESET_AND_REINSTALL_COM_LEITING_WF_ON_{serial}"
        if candidate_id != BUILD_ID or confirmation != expected:
            raise module.ReleaseError("device preparation confirmation mismatch")
        return {"prepared": True, "candidate_identity": dict(self.identity)}

    def record_manual_acceptance(
        self,
        candidate_id: str,
        serial: str,
        receipt_out: Path,
        checks: Mapping[str, bool],
        *_args: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        self._maybe_fail("device-accept")
        if candidate_id != BUILD_ID or serial != SERIAL:
            raise module.ReleaseError("device acceptance target mismatch")
        self.manual_checks_seen = dict(checks)
        if tuple(checks) != REQUIRED_MANUAL_CHECKS or not all(checks.values()):
            raise module.ReleaseError("all ten manual checks require explicit yes input")
        self.seed_receipt(receipt_out)
        return {"accepted": True, "receipt": receipt_out.name}

    def init_signer(
        self, confirmation: str, *_args: Any, **_kwargs: Any
    ) -> dict[str, Any]:
        self._maybe_fail("init-signer")
        if confirmation != "CREATE_WF_OFFLINE_RELEASE_SIGNER":
            raise module.ReleaseError("signer confirmation mismatch")
        return {"signer_ready": True, "certificate_sha256": "55" * 32}

    def publish_live(self, *_args: Any, **_kwargs: Any) -> None:
        self.live_publish_calls.append("publish-live")
        raise AssertionError("offline release must never publish live data")


@unittest.skipUnless(os.name == "nt", "Windows path conversion regression")
class OfflineReleaseWindowsPathTests(unittest.TestCase):
    def test_extended_path_converts_unc_share_to_extended_unc_form(self) -> None:
        self.assertEqual(
            module._windows_extended_path(
                Path(r"\\server\share\release\device-preparation.json")
            ),
            r"\\?\UNC\server\share\release\device-preparation.json",
        )


class OfflineReleaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.test_temp_parent = module.DEFAULT_OUTPUT_ROOT / ".unit-test-temp"
        candidates = (
            module.REPO_ROOT / "out",
            module.DEFAULT_OUTPUT_ROOT,
            self.test_temp_parent,
        )
        self.created_temp_parents = tuple(
            path for path in candidates if not path.exists()
        )
        self.test_temp_parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.test_temp_parent)
        self.root = Path(self.temp.name)
        self.source_apk = self.root / "base.apk.1"
        self.source_apk.write_bytes(b"small fixture; hash supplied by fake service")
        self.legacy_zip = self.root / "legacy.zip"
        self.legacy_zip.write_bytes(b"legacy fixture")
        self.tail_zip = self.root / "tail.zip"
        self.tail_zip.write_bytes(b"tail fixture")
        self.config = self.make_config(self.root / "out")

    def tearDown(self) -> None:
        self.temp.cleanup()
        for path in reversed(self.created_temp_parents):
            try:
                path.rmdir()
            except OSError:
                pass

    def make_config(self, output_root: Path) -> Any:
        return module.OfflineReleaseConfig(
            source_apk=self.source_apk,
            snapshot_version="1.4.196",
            output_root=output_root,
            profile_id="cn",
            legacy_zip=self.legacy_zip,
            tail_zip=self.tail_zip,
            toolchain=object(),
            signing=object(),
        )

    def test_build_candidate_runs_fixed_thirteen_stages_and_stops_before_final(self) -> None:
        services = FakeServices(self.config)

        result = module.build_candidate(self.config, services=services)

        self.assertEqual(tuple(services.calls), EXPECTED_STAGES)
        self.assertEqual(result.status, "awaiting_device_acceptance")
        self.assertEqual(result.build_id, BUILD_ID)
        self.assertEqual(result.candidate_dir, services.candidate_dir)
        self.assertIsNone(result.final_dir)
        self.assertFalse(services.final_dir.exists())
        self.assertEqual(services.source_reads, 2)

    def test_source_fingerprints_bracket_all_source_reading_stages_before_freeze(self) -> None:
        services = FakeServices(self.config)

        module.build_candidate(self.config, services=services)

        self.assertEqual(
            tuple(services.timeline),
            (
                "fingerprint",
                "preflight",
                "scan-store",
                "legacy-tail-gates",
                "copy-snapshot",
                "player-overlay",
                "content-data-gates",
                "build-apk",
                "content-client-gate",
                "build-zip",
                "verify-zip",
                "fingerprint",
                "render-guide",
                "freeze-candidate",
                "secret-scan",
            ),
        )

    def test_every_stage_report_has_one_stable_schema(self) -> None:
        services = FakeServices(self.config)

        result = module.build_candidate(self.config, services=services)

        self.assertEqual(len(result.stage_reports), len(EXPECTED_STAGES))
        for expected_name, report in zip(EXPECTED_STAGES, result.stage_reports):
            self.assertEqual(set(report), {"name", "status", "evidence"})
            self.assertEqual(report["name"], expected_name)
            self.assertEqual(report["status"], "ok")
            self.assertIsInstance(report["evidence"], Mapping)

    def test_build_rechecks_and_rejects_source_apk_or_store_drift(self) -> None:
        for drift, message in (("apk", "source APK drift"), ("store", "source store drift")):
            with self.subTest(drift=drift):
                config = self.make_config(self.root / f"out-{drift}")
                services = FakeServices(config)
                services.source_drift = drift
                with self.assertRaisesRegex(module.ReleaseError, message):
                    module.build_candidate(config, services=services)
                self.assertFalse(services.final_dir.exists())

    def test_preflight_rejects_signer_disk_and_source_apk_hash_failures(self) -> None:
        cases: tuple[tuple[str, Callable[[FakeServices], None], str], ...] = (
            (
                "signer",
                lambda service: setattr(service, "signer_ready", False),
                "signer.*ready",
            ),
            (
                "disk",
                lambda service: setattr(service, "disk_free_bytes", 1),
                "disk space",
            ),
            (
                "source-apk",
                lambda service: setattr(service, "source_apk_sha256", "00" * 32),
                "source APK hash",
            ),
        )
        for name, mutate, message in cases:
            with self.subTest(case=name):
                config = self.make_config(self.root / f"out-{name}")
                services = FakeServices(config)
                mutate(services)
                with self.assertRaisesRegex(module.ReleaseError, message):
                    module.build_candidate(config, services=services)
                self.assertEqual(services.calls, ["preflight"])
                self.assertFalse(services.candidate_dir.exists())

    def test_real_signer_report_cannot_default_missing_proofs_to_ready(self) -> None:
        import types

        certificate = "ab" * 32
        signing = types.SimpleNamespace(
            expected_certificate_sha256=certificate.upper()
        )
        valid = {
            "certificate_sha256": certificate,
            "fingerprint_verified": True,
            "signer_ready": True,
        }
        module._require_verified_signer_report(valid, signing)

        invalid_reports = (
            {},
            {**valid, "signer_ready": False},
            {**valid, "fingerprint_verified": False},
            {**valid, "certificate_sha256": "cd" * 32},
        )
        for report in invalid_reports:
            with self.subTest(report=report), self.assertRaisesRegex(
                module.ReleaseError, "signer verification"
            ):
                module._require_verified_signer_report(report, signing)

    def test_existing_candidate_or_final_is_never_overwritten(self) -> None:
        for kind in ("candidate", "final"):
            with self.subTest(kind=kind):
                config = self.make_config(self.root / f"out-conflict-{kind}")
                services = FakeServices(config)
                conflict = (
                    services.candidate_dir if kind == "candidate" else services.final_dir
                )
                conflict.mkdir(parents=True)
                sentinel = conflict / "competitor.txt"
                sentinel.write_text("keep", encoding="utf-8")
                with self.assertRaisesRegex(module.ReleaseError, f"{kind}.*exists"):
                    module.build_candidate(config, services=services)
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_error_receipt_is_canonical_and_redacts_password_and_absolute_paths(self) -> None:
        services = FakeServices(self.config)
        secret = "NeverLeak-Offline-Signer-Password"
        services.raise_stage = "build-apk"
        services.failure_text = f"failed at {self.root} with password {secret}"

        with (
            mock.patch.dict(os.environ, {"WF_OFFLINE_KEYSTORE_PASSWORD": secret}),
            self.assertRaisesRegex(module.ReleaseError, "build-apk"),
        ):
            module.build_candidate(self.config, services=services)

        receipts = list((services.version_root / "failures").glob("*.json"))
        self.assertEqual(len(receipts), 1)
        raw = receipts[0].read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        self.assertNotIn(secret.encode("utf-8"), raw)
        self.assertNotIn(str(self.root).encode("utf-8"), raw)
        document = json.loads(raw)
        self.assertEqual(
            raw,
            (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"),
        )
        self.assertEqual(document["command"], "build-candidate")
        self.assertEqual(document["status"], "error")

    def test_keyboard_interrupt_cleans_only_the_owned_staging_directory(self) -> None:
        services = FakeServices(self.config)
        services.interrupt_stage = "build-zip"
        competitor = services.version_root / ".staging-competitor"
        competitor.mkdir(parents=True)
        sentinel = competitor / "competitor.txt"
        sentinel.write_text("keep", encoding="utf-8")

        with self.assertRaises(KeyboardInterrupt):
            module.build_candidate(self.config, services=services)

        self.assertTrue(services.staging_dirs_seen)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        self.assertEqual(
            [path.name for path in services.version_root.glob(".staging-*")],
            [".staging-competitor"],
        )
        self.assertFalse(services.candidate_dir.exists())
        self.assertFalse(services.final_dir.exists())

    def test_build_never_calls_live_publish_or_mutates_user_wip_roots(self) -> None:
        protected = []
        for name in ("弹国服", ".cdn", "assets", "work"):
            path = self.root / name / "sentinel.txt"
            path.parent.mkdir(parents=True)
            path.write_text(f"keep-{name}", encoding="utf-8")
            protected.append((path, path.read_bytes()))
        services = FakeServices(self.config)

        module.build_candidate(self.config, services=services)

        self.assertEqual(services.live_publish_calls, [])
        for path, before in protected:
            self.assertEqual(path.read_bytes(), before)

    @unittest.skipUnless(os.name == "nt", "Windows output-scope regression")
    def test_output_scope_rejects_junctions_resolving_into_a_protected_root(self) -> None:
        import subprocess

        protected = self.root / "protected-live-root"
        protected.mkdir()
        sentinel = protected / "must-survive.txt"
        sentinel.write_text("keep", encoding="utf-8")
        junction = self.root / "junction-output"
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(junction),
                str(protected),
            ],
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        try:
            with (
                mock.patch.object(
                    module, "PROTECTED_OUTPUT_ROOTS", (protected,)
                ),
                self.assertRaisesRegex(module.ReleaseError, "protected|WIP|live"),
            ):
                module._require_output_scope(junction / "1.4.196")
        finally:
            junction.rmdir()
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_repository_local_output_is_limited_to_canonical_out_subtree(self) -> None:
        for target in (
            module.REPO_ROOT / "mod-tools" / "offline-output",
            module.REPO_ROOT / "client-patch" / "offline-output",
        ):
            with self.subTest(target=target), self.assertRaisesRegex(
                module.ReleaseError, "out/wf-offline-android"
            ):
                module._require_output_scope(target)
        module._require_output_scope(
            module.DEFAULT_OUTPUT_ROOT / "safe-test" / "1.4.196"
        )

    def test_scope_failure_writes_no_failure_receipt_into_protected_output(self) -> None:
        protected = self.root / "protected-failure-root"
        protected.mkdir()
        sentinel = protected / "must-survive.txt"
        sentinel.write_text("keep", encoding="utf-8")
        config = self.make_config(protected)
        services = FakeServices(config)

        with (
            mock.patch.object(module, "PROTECTED_OUTPUT_ROOTS", (protected,)),
            self.assertRaisesRegex(module.ReleaseError, "protected|WIP|live"),
        ):
            module.build_candidate(config, services=services)

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        self.assertFalse((protected / config.snapshot_version).exists())

    def test_snapshot_version_traversal_or_absolute_path_fails_before_any_write(self) -> None:
        invalid_versions = (
            "..\\assets",
            str((self.root / "absolute-version-escape").resolve()),
        )
        for index, snapshot_version in enumerate(invalid_versions):
            with self.subTest(snapshot_version=snapshot_version):
                output_root = self.root / f"invalid-version-output-{index}"
                config = replace(
                    self.make_config(output_root),
                    snapshot_version=snapshot_version,
                )
                services = FakeServices(config)
                with self.assertRaisesRegex(
                    module.ReleaseError, "snapshot version"
                ):
                    module.build_candidate(config, services=services)
                self.assertEqual(services.calls, [])
                self.assertFalse(output_root.exists())

    def test_prepare_and_finalize_cannot_bypass_output_scope_preflight(self) -> None:
        protected = self.root / "protected-command-root"
        protected.mkdir()
        sentinel = protected / "must-survive.txt"
        sentinel.write_text("keep", encoding="utf-8")
        commands = (
            [
                "prepare-device",
                "--candidate",
                BUILD_ID,
                "--serial",
                SERIAL,
                "--confirm",
                f"RESET_AND_REINSTALL_COM_LEITING_WF_ON_{SERIAL}",
            ],
            [
                "finalize",
                "--candidate",
                BUILD_ID,
                "--receipt",
                str(self.root / "never-read-receipt.json"),
            ],
        )
        for command in commands:
            with self.subTest(command=command[0]):
                output = io.StringIO()
                with (
                    mock.patch.object(
                        module, "PROTECTED_OUTPUT_ROOTS", (protected,)
                    ),
                    contextlib.redirect_stdout(output),
                ):
                    exit_code = module.main(
                        [
                            *command,
                            "--output-root",
                            str(protected),
                            "--snapshot-version",
                            "1.4.196",
                        ]
                    )
                document = json.loads(output.getvalue().splitlines()[-1])
                self.assertNotEqual(exit_code, 0, document)
                self.assertRegex(document["errors"][0], "protected|WIP|live")
                self.assertFalse((protected / "1.4.196").exists())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_finalize_requires_receipt_bound_to_exact_candidate_identity(self) -> None:
        services = FakeServices(self.config)
        services.seed_candidate()
        wrong = dict(services.identity)
        wrong["apk_sha256"] = "99" * 32
        receipt = services.seed_receipt(self.root / "wrong-receipt.json", identity=wrong)

        with self.assertRaisesRegex(module.ReleaseError, "apk_sha256.*mismatch"):
            module.finalize_release(
                self.config,
                candidate_id=BUILD_ID,
                receipt=receipt,
                services=services,
            )

        self.assertEqual(services.receipt_identity_seen, services.identity)
        self.assertFalse(services.final_dir.exists())

    def test_finalize_and_verify_produce_exact_five_file_bundle(self) -> None:
        services = FakeServices(self.config)
        services.seed_candidate()
        receipt = services.seed_receipt(self.root / "device-acceptance.json")

        finalized = module.finalize_release(
            self.config,
            candidate_id=BUILD_ID,
            receipt=receipt,
            services=services,
        )
        verified = module.verify_release(
            self.config,
            bundle=services.final_dir,
            services=services,
        )

        self.assertEqual(finalized.status, "finalized")
        self.assertEqual(verified.status, "verified")
        self.assertEqual(
            tuple(sorted(path.name for path in services.final_dir.iterdir())),
            tuple(sorted(FINAL_FILES)),
        )
        self.assertEqual(verified.identity, services.identity)

    def test_verify_rejects_any_sixth_final_file(self) -> None:
        services = FakeServices(self.config)
        services.seed_final()
        (services.final_dir / "extra.txt").write_text("not allowed", encoding="utf-8")

        with self.assertRaisesRegex(module.ReleaseError, "exactly five files"):
            module.verify_release(
                self.config,
                bundle=services.final_dir,
                services=services,
            )

    def test_subprocess_adb_runner_uses_exact_argv_and_never_selects_a_default_device(self) -> None:
        calls: list[tuple[list[str], dict[str, Any]]] = []

        def run(command: list[str], **kwargs: Any) -> object:
            calls.append((list(command), dict(kwargs)))
            return object()

        adb = self.root / "platform tools" / "adb.exe"
        secret = "must-not-reach-adb-process"
        with mock.patch.dict(
            os.environ, {module.PASSWORD_ENV: secret}, clear=False
        ):
            runner = module.SubprocessAdbRunner(adb, timeout_seconds=17, runner=run)
            runner.adb(None, "devices", "-l")
            runner.adb(
                SERIAL,
                "shell",
                "settings",
                "get",
                "global",
                "airplane_mode_on",
            )

        self.assertEqual(calls[0][0], [str(adb), "devices", "-l"])
        self.assertEqual(
            calls[1][0],
            [
                str(adb),
                "-s",
                SERIAL,
                "shell",
                "settings",
                "get",
                "global",
                "airplane_mode_on",
            ],
        )
        for _command, kwargs in calls:
            self.assertIs(kwargs["shell"], False)
            self.assertIs(kwargs["check"], False)
            self.assertIs(kwargs["capture_output"], True)
            self.assertIs(kwargs["text"], False)
            self.assertEqual(kwargs["timeout"], 17)
            self.assertNotIn(module.PASSWORD_ENV, kwargs["env"])
            self.assertNotIn(secret, kwargs["env"].values())
        with self.assertRaisesRegex(module.ReleaseError, "devices -l"):
            runner.adb(None, "shell", "getprop")
        with self.assertRaisesRegex(module.ReleaseError, "serial"):
            runner.adb("device\nsecond-device", "shell", "getprop")

    def test_git_release_evidence_process_never_inherits_signer_password(self) -> None:
        secret = "must-not-reach-git-process"
        completed = type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "0123456789abcdef\n"},
        )()
        with (
            mock.patch.dict(
                os.environ, {module.PASSWORD_ENV: secret}, clear=False
            ),
            mock.patch.object(
                module.subprocess, "run", return_value=completed
            ) as run,
        ):
            self.assertEqual(
                module.RealReleaseServices._git_output(("rev-parse", "HEAD")),
                "0123456789abcdef",
            )

        child_env = run.call_args.kwargs["env"]
        self.assertNotIn(module.PASSWORD_ENV, child_env)
        self.assertNotIn(secret, child_env.values())

    def test_real_release_services_exposes_every_task3_to_13_adapter(self) -> None:
        services = module.RealReleaseServices(self.config)
        expected = (
            "fingerprint_sources",
            "preflight",
            "scan_store",
            "legacy_tail_gates",
            "copy_snapshot",
            "player_overlay",
            "content_data_gates",
            "build_apk",
            "content_client_gate",
            "build_zip",
            "verify_zip",
            "render_guide",
            "freeze_candidate",
            "secret_scan",
            "load_candidate_identity",
            "validate_acceptance_receipt",
            "finalize_candidate",
            "verify_final_bundle",
            "probe_device",
            "prepare_device",
            "record_manual_acceptance",
            "init_signer",
        )
        missing = [name for name in expected if not callable(getattr(services, name, None))]
        self.assertEqual(missing, [])

    def test_serial_only_device_target_ignores_an_optional_discovered_mumu_manager(self) -> None:
        import types

        config = replace(
            self.config,
            toolchain=types.SimpleNamespace(
                adb=self.root / "fake-adb.exe",
                mumu_manager=self.root / "MuMuManager.exe",
            ),
        )
        services = module.RealReleaseServices(config)
        runner = object()
        with mock.patch.object(module, "SubprocessAdbRunner", return_value=runner):
            target, actual_runner = services._target(SERIAL)

        self.assertEqual(target.serial, SERIAL)
        self.assertIsNone(target.mumu_manager)
        self.assertIsNone(target.instance)
        self.assertIs(actual_runner, runner)

    def test_real_content_validation_never_uses_workspace_character_sources(self) -> None:
        import types

        services = module.RealReleaseServices(self.config)
        services._staged_roots = object()
        calls: list[tuple[object, dict[str, Any]]] = []

        content_module = types.SimpleNamespace(
            SERIS_PHASE4_ASSET_LOGICALS=("seris-asset",),
            validate_offline_content=lambda roots, **kwargs: calls.append((roots, kwargs))
            or object(),
        )
        services._modules = lambda: (  # type: ignore[method-assign]
            object(),
            object(),
            content_module,
            object(),
            object(),
            object(),
            object(),
        )

        services._validate_content(None)

        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0], services._staged_roots)
        self.assertIsNone(calls[0][1]["workspace_sources"])
        source = Path(module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("character_packs", source)
        self.assertNotIn("_workspace_sources", source)

    def test_cross_process_candidate_load_repeats_secret_scan_and_fails_closed(self) -> None:
        import wf_offline_bundle as bundle_module

        identity = bundle_module.CandidateIdentity(
            BUILD_ID,
            sha256(APK_BYTES),
            sha256(DATA_ZIP_BYTES),
            sha256(GUIDE_BYTES),
            "ef" * 32,
        )
        services = module.RealReleaseServices(self.config)
        with (
            mock.patch.object(
                bundle_module,
                "verify_candidate",
                autospec=True,
                return_value=(identity, {"schema_version": 1}),
            ),
            mock.patch.object(
                bundle_module,
                "scan_release_for_secrets",
                autospec=True,
                return_value=("release-evidence.json: configured secret",),
            ) as scan,
            self.assertRaisesRegex(module.ReleaseError, "finding_count=1"),
        ):
            services.load_candidate_identity(BUILD_ID)

        scan.assert_called_once_with(
            self.config.output_root
            / self.config.snapshot_version
            / f".candidate-{BUILD_ID}",
            secret_values=(),
        )

    def test_real_services_rebind_exact_player_manifest_entry_for_both_zip_stages(self) -> None:
        import types

        import wf_offline_player as player_module
        import wf_offline_store as store_module
        import wf_offline_zip as zip_module

        services = module.RealReleaseServices(self.config)
        staging = self.root / "real-wiring-staging"
        worldflipper = staging / "WorldFlipper"
        production = worldflipper / "dummy" / "download" / "production"
        roots = store_module.StoreRoots(
            production / "upload",
            production / "medium_upload",
            production / "android_upload",
        )
        for root in (roots.common, roots.medium, roots.android):
            root.mkdir(parents=True, exist_ok=True)
        relative = Path("51") / "b73a9401c1fae38366ee79f4274942254d389c"
        player_path = roots.common / relative
        player_path.parent.mkdir(parents=True, exist_ok=True)
        player_path.write_bytes(b"old-player")
        archive_path = (
            "WorldFlipper/dummy/download/production/upload/"
            + relative.as_posix()
        )
        old_entry = store_module.ManifestEntry(
            archive_path,
            len(b"old-player"),
            sha256(b"old-player"),
            "store:common",
        )
        marker = store_module.ManifestEntry(
            "WorldFlipper/dummy/download/.empty",
            1,
            sha256(b"0"),
            "generated-marker",
        )
        services._staged_roots = roots
        services._snapshot = types.SimpleNamespace(worldflipper_root=worldflipper)
        services._entries = (old_entry, marker)

        overlay_report = player_module.PlayerOverlayReport(
            logical_path=player_module.PLAYER_LOGICAL_PATH,
            relative_path=relative.as_posix(),
            before_sha256=sha256(b"old-player"),
            after_sha256=sha256(b"new-player-overlay"),
            before_character_ids=("1",),
            after_character_ids=("1", "129999", "139999", "149999"),
            added_character_ids=("129999", "139999", "149999"),
            character_level=1,
        )

        def apply_overlay(common_root: Path) -> Any:
            self.assertEqual(common_root, roots.common)
            player_path.write_bytes(b"new-player-overlay")
            return overlay_report

        zip_build = zip_module.ZipBuildReport(
            "71" * 32,
            2,
            {"common": 1, "medium": 0, "android": 0},
            len(b"new-player-overlay") + 1,
            True,
        )
        zip_verify = zip_module.ZipVerificationReport(
            "71" * 32,
            2,
            {"common": 1, "medium": 0, "android": 0},
            len(b"new-player-overlay") + 1,
            True,
        )
        artifacts = staging / "artifacts"
        artifacts.mkdir()
        with (
            mock.patch.object(
                player_module,
                "apply_initial_player_overlay",
                autospec=True,
                side_effect=apply_overlay,
            ),
            mock.patch.object(
                zip_module,
                "write_data_zip",
                autospec=True,
                return_value=zip_build,
            ) as write_zip_mock,
            mock.patch.object(
                zip_module,
                "verify_data_zip",
                autospec=True,
                return_value=zip_verify,
            ) as verify_zip_mock,
        ):
            services.player_overlay(self.config)
            rebound_entries = services._entries
            services.build_zip(self.config, staging_dir=staging)
            services.verify_zip(self.config, staging_dir=staging)

        self.assertEqual(rebound_entries[0].path, old_entry.path)
        self.assertEqual(rebound_entries[0].source, old_entry.source)
        self.assertEqual(rebound_entries[0].size, len(b"new-player-overlay"))
        self.assertEqual(rebound_entries[0].sha256, sha256(b"new-player-overlay"))
        self.assertIs(write_zip_mock.call_args.args[2], rebound_entries)
        self.assertIs(verify_zip_mock.call_args.args[1], rebound_entries)

    def test_prepare_and_accept_resume_across_fresh_services_with_clean_baseline_and_qa_probe(self) -> None:
        import types

        import wf_offline_bundle as bundle_module
        import wf_offline_device as device_module

        config = replace(
            self.config,
            output_root=self.root / "cross-process-output",
            toolchain=types.SimpleNamespace(
                adb=self.root / "fake-adb.exe", mumu_manager=None
            ),
        )
        identity = bundle_module.CandidateIdentity(
            BUILD_ID,
            sha256(APK_BYTES),
            sha256(DATA_ZIP_BYTES),
            sha256(GUIDE_BYTES),
            "ef" * 32,
        )
        identity_b = bundle_module.CandidateIdentity(
            BUILD_ID_B,
            sha256(b"candidate-b-apk"),
            sha256(DATA_ZIP_BYTES),
            sha256(GUIDE_BYTES),
            "fe" * 32,
        )
        clean = device_module.DeviceProbeReport(
            serial_digest="44" * 32,
            package_name="com.leiting.wf",
            airplane_mode=True,
            wifi_disabled=True,
            mobile_disabled=True,
            no_default_route=True,
            no_active_network=True,
            companion_ports_unused=True,
            save_haxe_present_before=False,
            dummy_data_present_before=False,
            fatal_log_lines=(),
        )
        qa = replace(
            clean,
            save_haxe_present_before=True,
            dummy_data_present_before=True,
        )
        runner = object()
        receipt_out = self.root / "device-acceptance.json"
        checks = {name: True for name in REQUIRED_MANUAL_CHECKS}
        recorded: list[tuple[Any, Any, Mapping[str, bool], Path]] = []
        expected_sidecar = (
            config.output_root
            / config.snapshot_version
            / "device-preparation"
            / f"serial-{clean.serial_digest}.json"
        )

        def record(
            candidate_identity: Any,
            probe: Any,
            supplied_checks: Mapping[str, bool],
            output: Path,
        ) -> Mapping[str, Any]:
            recorded.append((candidate_identity, probe, supplied_checks, output))
            return {"accepted": True}

        def prepare(*_args: Any, **_kwargs: Any) -> Any:
            self.assertFalse(expected_sidecar.exists())
            self.assertTrue(
                expected_sidecar.with_name(
                    f".{expected_sidecar.name}.reserve"
                ).exists()
            )
            with self.assertRaisesRegex(
                module.ReleaseError, "reservation.*exists"
            ):
                module._reserve_file(expected_sidecar)
            return clean

        with (
            mock.patch.object(
                bundle_module,
                "verify_candidate",
                autospec=True,
                return_value=(identity, {}),
            ) as verify_candidate,
            mock.patch.object(
                bundle_module,
                "scan_release_for_secrets",
                autospec=True,
                return_value=PINNED_BASELINE_FINDINGS,
            ),
            mock.patch.object(module, "SubprocessAdbRunner", return_value=runner),
            mock.patch.object(
                device_module,
                "probe_device",
                autospec=True,
                side_effect=[clean, clean, qa],
            ),
            mock.patch.object(
                device_module,
                "prepare_device",
                autospec=True,
                side_effect=prepare,
            ) as destructive,
            mock.patch.object(
                device_module,
                "record_manual_acceptance",
                autospec=True,
                side_effect=record,
            ),
        ):
            first_process = module.RealReleaseServices(config)
            prepared = first_process.prepare_device(
                BUILD_ID,
                SERIAL,
                f"RESET_AND_REINSTALL_COM_LEITING_WF_ON_{SERIAL}",
            )
            self.assertEqual(
                first_process._prepared_sidecar(BUILD_ID, clean.serial_digest),
                first_process._prepared_sidecar(BUILD_ID_B, clean.serial_digest),
            )
            with self.assertRaisesRegex(
                module.ReleaseError, "candidate identity mismatch"
            ):
                first_process._load_prepared_probe(
                    identity_b, clean.serial_digest
                )
            verify_candidate.return_value = (identity_b, {})
            with self.assertRaisesRegex(module.ReleaseError, "sidecar.*exists"):
                module.RealReleaseServices(config).prepare_device(
                    BUILD_ID_B,
                    SERIAL,
                    f"RESET_AND_REINSTALL_COM_LEITING_WF_ON_{SERIAL}",
                )
            self.assertEqual(destructive.call_count, 1)
            verify_candidate.return_value = (identity, {})
            second_process = module.RealReleaseServices(config)
            candidate_receipt = (
                config.output_root
                / config.snapshot_version
                / f".candidate-{BUILD_ID}"
                / "device-acceptance.json"
            )
            with self.assertRaisesRegex(
                module.ReleaseError, "outside candidate"
            ):
                second_process.record_manual_acceptance(
                    BUILD_ID, SERIAL, candidate_receipt, checks
                )
            protected_receipts = self.root / "protected-receipts"
            with (
                mock.patch.object(
                    module, "PROTECTED_OUTPUT_ROOTS", (protected_receipts,)
                ),
                self.assertRaisesRegex(
                    module.ReleaseError, "protected|WIP|live"
                ),
            ):
                second_process.record_manual_acceptance(
                    BUILD_ID,
                    SERIAL,
                    protected_receipts / "device-acceptance.json",
                    checks,
                )
            accepted = second_process.record_manual_acceptance(
                BUILD_ID, SERIAL, receipt_out, checks
            )

        self.assertTrue(prepared["prepared"])
        self.assertTrue(accepted["accepted"])
        self.assertEqual(len(recorded), 1)
        recorded_identity, combined, recorded_checks, recorded_output = recorded[0]
        self.assertEqual(recorded_identity, identity)
        self.assertEqual(recorded_checks, checks)
        self.assertEqual(recorded_output, receipt_out)
        self.assertFalse(combined.save_haxe_present_before)
        self.assertFalse(combined.dummy_data_present_before)
        self.assertTrue(combined.airplane_mode)
        sidecars = list(
            (config.output_root / config.snapshot_version / "device-preparation").iterdir()
        )
        self.assertEqual(len(sidecars), 1)
        raw = sidecars[0].read_bytes()
        self.assertEqual(raw, bundle_module.canonical_json_bytes(json.loads(raw)))
        self.assertNotIn(SERIAL.encode("utf-8"), raw)

    def test_prepare_refuses_existing_sidecar_before_task13_destructive_call(self) -> None:
        import types

        import wf_offline_bundle as bundle_module
        import wf_offline_device as device_module

        config = replace(
            self.config,
            output_root=self.root / "sidecar-conflict-output",
            toolchain=types.SimpleNamespace(
                adb=self.root / "fake-adb.exe", mumu_manager=None
            ),
        )
        identity = bundle_module.CandidateIdentity(
            BUILD_ID,
            sha256(APK_BYTES),
            sha256(DATA_ZIP_BYTES),
            sha256(GUIDE_BYTES),
            "ef" * 32,
        )
        clean = device_module.DeviceProbeReport(
            serial_digest="44" * 32,
            package_name="com.leiting.wf",
            airplane_mode=True,
            wifi_disabled=True,
            mobile_disabled=True,
            no_default_route=True,
            no_active_network=True,
            companion_ports_unused=True,
            save_haxe_present_before=False,
            dummy_data_present_before=False,
            fatal_log_lines=(),
        )
        sidecar = (
            config.output_root
            / config.snapshot_version
            / "device-preparation"
            / f"serial-{clean.serial_digest}.json"
        )
        sidecar.parent.mkdir(parents=True)
        guard = sidecar.with_name(f".{sidecar.name}.reserve")
        for occupied in (sidecar, guard):
            with self.subTest(occupied=occupied.name):
                occupied.write_text("competitor", encoding="utf-8")
                with (
                    mock.patch.object(
                        bundle_module,
                        "verify_candidate",
                        autospec=True,
                        return_value=(identity, {}),
                    ),
                    mock.patch.object(
                        bundle_module,
                        "scan_release_for_secrets",
                        autospec=True,
                        return_value=PINNED_BASELINE_FINDINGS,
                    ),
                    mock.patch.object(
                        module, "SubprocessAdbRunner", return_value=object()
                    ),
                    mock.patch.object(
                        device_module,
                        "probe_device",
                        autospec=True,
                        return_value=clean,
                    ),
                    mock.patch.object(
                        device_module,
                        "prepare_device",
                        autospec=True,
                        return_value=clean,
                    ) as destructive,
                    self.assertRaisesRegex(module.ReleaseError, "sidecar.*exists"),
                ):
                    module.RealReleaseServices(config).prepare_device(
                        BUILD_ID,
                        SERIAL,
                        f"RESET_AND_REINSTALL_COM_LEITING_WF_ON_{SERIAL}",
                    )
                destructive.assert_not_called()
                self.assertEqual(
                    occupied.read_text(encoding="utf-8"), "competitor"
                )
                occupied.unlink()

    @unittest.skipUnless(os.name == "nt", "Windows atomic publication regression")
    def test_sidecar_atomic_publish_never_overwrites_a_racing_destination(self) -> None:
        parent = self.root / "atomic-sidecar-race"
        parent.mkdir()
        sidecar = parent / "prepared.json"
        guard = sidecar.with_name(f".{sidecar.name}.reserve")
        reserved = module._reserve_file(sidecar)
        reserved.destructive_started = True
        competitor = b"competitor-must-survive"
        sidecar.write_bytes(competitor)

        try:
            with self.assertRaises(OSError):
                module._finish_reserved_file(reserved, b'{"canonical":true}\n')
        finally:
            module._abort_reserved_file(reserved)

        self.assertEqual(sidecar.read_bytes(), competitor)
        self.assertTrue(guard.is_file())
        self.assertEqual(list(parent.glob("*.tmp-*")), [])

    @unittest.skipUnless(os.name == "nt", "Windows atomic publication regression")
    def test_sidecar_partial_staging_write_never_exposes_final_target(self) -> None:
        parent = self.root / "atomic-sidecar-partial"
        parent.mkdir()
        sidecar = parent / "prepared.json"
        guard = sidecar.with_name(f".{sidecar.name}.reserve")
        reserved = module._reserve_file(sidecar)
        reserved.destructive_started = True
        original_write = os.write
        calls = 0

        def interrupted_write(descriptor: int, payload: Any) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                return original_write(descriptor, payload[:3])
            raise OSError("simulated publication interruption")

        try:
            with (
                mock.patch.object(os, "write", side_effect=interrupted_write),
                self.assertRaisesRegex(OSError, "simulated publication interruption"),
            ):
                module._finish_reserved_file(reserved, b'{"canonical":true}\n')
        finally:
            module._abort_reserved_file(reserved)

        self.assertFalse(sidecar.exists())
        self.assertTrue(guard.is_file())
        self.assertEqual(list(parent.glob("*.tmp-*")), [])

    @unittest.skipUnless(os.name == "nt", "Windows long-path publication regression")
    def test_sidecar_atomic_publish_supports_real_staging_path_over_max_path(self) -> None:
        sidecar_name = "prepared.json"
        staging_name = f".{sidecar_name}.tmp-{'0' * 32}"
        staging_path_length = 267
        parent_length = staging_path_length - len(staging_name) - 1
        padding_length = parent_length - len(str(self.root)) - 1
        self.assertGreater(padding_length, 0)
        parent = self.root / ("x" * padding_length)
        parent.mkdir()
        sidecar = parent / sidecar_name
        staging = sidecar.with_name(staging_name)
        self.assertLess(len(str(sidecar)), 260)
        self.assertEqual(len(str(staging)), staging_path_length)
        payload = b'{"canonical":true}\n'
        reserved = module._reserve_file(sidecar)
        reserved.destructive_started = True

        try:
            with mock.patch.object(
                module.uuid,
                "uuid4",
                return_value=module.uuid.UUID(int=0),
            ):
                module._finish_reserved_file(reserved, payload)
        finally:
            module._abort_reserved_file(reserved)

        self.assertEqual(sidecar.read_bytes(), payload)
        self.assertFalse(reserved.guard_path.exists())

    def test_prepared_probe_loader_rejects_reparse_parent_instead_of_following_it(self) -> None:
        import subprocess

        import wf_offline_bundle as bundle_module
        import wf_offline_device as device_module

        config = replace(self.config, output_root=self.root / "reparse-sidecar-output")
        services = module.RealReleaseServices(config)
        identity = bundle_module.CandidateIdentity(
            BUILD_ID,
            sha256(APK_BYTES),
            sha256(DATA_ZIP_BYTES),
            sha256(GUIDE_BYTES),
            "ef" * 32,
        )
        probe = device_module.DeviceProbeReport(
            serial_digest="44" * 32,
            package_name="com.leiting.wf",
            airplane_mode=True,
            wifi_disabled=True,
            mobile_disabled=True,
            no_default_route=True,
            no_active_network=True,
            companion_ports_unused=True,
            save_haxe_present_before=False,
            dummy_data_present_before=False,
            fatal_log_lines=(),
        )
        version_root = config.output_root / config.snapshot_version
        version_root.mkdir(parents=True)
        real_parent = self.root / "competitor-sidecar-parent"
        real_parent.mkdir()
        sidecar = real_parent / f"serial-{probe.serial_digest}.json"
        sidecar.write_bytes(
            bundle_module.canonical_json_bytes(
                {
                    "schema_version": 1,
                    "candidate_identity": {
                        "build_id": identity.build_id,
                        "apk_sha256": identity.apk_sha256,
                        "data_zip_sha256": identity.data_zip_sha256,
                        "guide_sha256": identity.guide_sha256,
                        "evidence_sha256": identity.evidence_sha256,
                    },
                    "serial_digest": probe.serial_digest,
                    "probe": services._probe_document(probe),
                }
            )
        )
        linked_parent = version_root / "device-preparation"
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(linked_parent), str(real_parent)],
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

        with self.assertRaisesRegex(module.ReleaseError, "reparse|plain directory"):
            services._load_prepared_probe(identity, probe.serial_digest)

    @unittest.skipUnless(os.name == "nt", "Windows stable-read regression")
    def test_prepared_probe_loader_holds_complete_parent_chain_during_validation(self) -> None:
        import wf_offline_bundle as bundle_module
        import wf_offline_device as device_module

        config = replace(self.config, output_root=self.root / "bound-sidecar-output")
        services = module.RealReleaseServices(config)
        identity = bundle_module.CandidateIdentity(
            BUILD_ID,
            sha256(APK_BYTES),
            sha256(DATA_ZIP_BYTES),
            sha256(GUIDE_BYTES),
            "ef" * 32,
        )
        probe = device_module.DeviceProbeReport(
            serial_digest="44" * 32,
            package_name="com.leiting.wf",
            airplane_mode=True,
            wifi_disabled=True,
            mobile_disabled=True,
            no_default_route=True,
            no_active_network=True,
            companion_ports_unused=True,
            save_haxe_present_before=False,
            dummy_data_present_before=False,
            fatal_log_lines=(),
        )
        sidecar = services._prepared_sidecar(identity.build_id, probe.serial_digest)
        sidecar.parent.mkdir(parents=True)
        sidecar.write_bytes(
            bundle_module.canonical_json_bytes(
                {
                    "schema_version": 1,
                    "candidate_identity": module._public_identity(identity),
                    "serial_digest": probe.serial_digest,
                    "probe": services._probe_document(probe),
                }
            )
        )
        reserve = sidecar.with_name(f".{sidecar.name}.reserve")
        reserve.write_bytes(b"crash-poison")
        with self.assertRaisesRegex(
            module.ReleaseError, "reservation|crash-poison"
        ):
            services._load_prepared_probe(identity, probe.serial_digest)
        self.assertEqual(reserve.read_bytes(), b"crash-poison")
        reserve.unlink()
        original_read = module._read_locked_regular
        attempted_rebind = False

        def guarded_read(locked: Any, **kwargs: Any) -> bytes:
            nonlocal attempted_rebind
            if not attempted_rebind:
                attempted_rebind = True
                with self.assertRaises(OSError):
                    locked.path.parent.parent.rename(
                        locked.path.parent.parent.with_name("1.4.196-rebound")
                    )
            return original_read(locked, **kwargs)

        with mock.patch.object(
            module, "_read_locked_regular", side_effect=guarded_read
        ):
            loaded = services._load_prepared_probe(identity, probe.serial_digest)

        self.assertTrue(attempted_rebind)
        self.assertEqual(loaded, probe)

    def test_owned_staging_holds_parent_and_root_against_rebind_and_preserves_sibling(self) -> None:
        with tempfile.TemporaryDirectory(dir=MOD_TOOLS) as local_temp:
            version_root = Path(local_temp) / "staging-rebind" / "1.4.196"
            owned = module._create_owned_staging(version_root)
            competitor = version_root / ".staging-competitor"
            competitor.mkdir()
            sentinel = competitor / "sentinel.txt"
            sentinel.write_text("keep", encoding="utf-8")
            self.assertIsNotNone(owned.handle)
            self.assertIsNotNone(owned.parent_handle)

            with self.assertRaises(OSError):
                owned.path.rename(version_root / ".staging-swapped")
            with self.assertRaises(OSError):
                version_root.rename(version_root.with_name("1.4.196-rebound"))

            module._cleanup_owned_staging(owned)
            self.assertFalse(owned.path.exists())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_owned_staging_holds_complete_ancestor_chain_against_grandparent_rebind(self) -> None:
        with tempfile.TemporaryDirectory(dir=MOD_TOOLS) as local_temp:
            local_root = Path(local_temp)
            grandparent = local_root / "staging-grandparent"
            version_root = grandparent / "output" / "1.4.196"
            owned = module._create_owned_staging(version_root)
            try:
                self.assertGreaterEqual(len(owned.ancestor_chain), 3)
                with self.assertRaises(OSError):
                    grandparent.rename(local_root / "staging-grandparent-rebound")
            finally:
                module._cleanup_owned_staging(owned)
            self.assertFalse(owned.path.exists())

    @unittest.skipUnless(os.name == "nt", "Windows handle-binding regression")
    def test_owned_staging_is_handle_bound_before_owner_marker_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=MOD_TOOLS) as local_temp:
            version_root = Path(local_temp) / "staging-marker-race" / "1.4.196"
            original_write = module._write_exclusive
            attempted_rebind = False

            def guarded_write(path: Path, payload: bytes) -> int:
                nonlocal attempted_rebind
                if path.name == ".offline-release-owner.json":
                    attempted_rebind = True
                    with self.assertRaises(OSError):
                        path.parent.rename(path.parent.with_name(".staging-attacker"))
                return original_write(path, payload)

            with mock.patch.object(module, "_write_exclusive", guarded_write):
                owned = module._create_owned_staging(version_root)
            try:
                self.assertTrue(attempted_rebind)
                self.assertTrue(
                    (owned.path / ".offline-release-owner.json").is_file()
                )
            finally:
                module._cleanup_owned_staging(owned)

    @unittest.skipUnless(os.name == "nt", "Windows cleanup fail-closed regression")
    def test_owned_staging_cleanup_rejects_a_missing_owner_marker(self) -> None:
        with tempfile.TemporaryDirectory(dir=MOD_TOOLS) as local_temp:
            version_root = Path(local_temp) / "missing-marker" / "1.4.196"
            owned = module._create_owned_staging(version_root)
            marker = owned.path / ".offline-release-owner.json"
            marker.unlink()

            with self.assertRaisesRegex(module.ReleaseError, "handle-bound"):
                module._cleanup_owned_staging(owned)

            self.assertTrue(owned.path.is_dir())
            owned.path.rmdir()

    @unittest.skipUnless(os.name == "nt", "Windows cleanup fail-closed regression")
    def test_owned_staging_cleanup_never_follows_child_swapped_to_junction(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory(dir=MOD_TOOLS) as local_temp:
            local_root = Path(local_temp)
            version_root = local_root / "child-swap" / "1.4.196"
            owned = module._create_owned_staging(version_root)
            child = owned.path / "artifact-directory"
            child.mkdir()
            detached = owned.path / "artifact-directory-detached"
            victim = local_root / "outside-victim"
            victim.mkdir()
            sentinel = victim / "must-survive.txt"
            sentinel.write_text("keep", encoding="utf-8")
            original_open = module._windows_directory_handle
            swapped = False

            def swap_after_lstat(path: Path, **kwargs: Any) -> Any:
                nonlocal swapped
                if path == child and not swapped:
                    swapped = True
                    child.rename(detached)
                    completed = subprocess.run(
                        [
                            "cmd.exe",
                            "/d",
                            "/c",
                            "mklink",
                            "/J",
                            str(child),
                            str(victim),
                        ],
                        shell=False,
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    self.assertEqual(
                        completed.returncode, 0, completed.stdout + completed.stderr
                    )
                return original_open(path, **kwargs)

            with (
                mock.patch.object(
                    module,
                    "_windows_directory_handle",
                    side_effect=swap_after_lstat,
                ),
                self.assertRaisesRegex(module.ReleaseError, "handle-bound"),
            ):
                module._cleanup_owned_staging(owned)

            self.assertTrue(swapped)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertTrue(owned.path.is_dir())

            child.rmdir()
            detached.rmdir()
            marker = owned.path / ".offline-release-owner.json"
            if marker.exists():
                marker.unlink()
            owned.path.rmdir()

    def test_real_release_evidence_projects_overlay_entries_and_exact_task12_schema(self) -> None:
        import types

        import wf_offline_bundle as bundle_module
        import wf_offline_content as content_module
        import wf_offline_player as player_module
        import wf_offline_store as store_module
        from wf_rogue_validate import RogueDataReport

        services = module.RealReleaseServices(self.config)
        self.source_apk.write_bytes(b"accepted-base-apk")
        paths = {
            "common": bundle_module.ROOT_PREFIXES["common"] + "aa/" + "1" * 38,
            "medium": bundle_module.ROOT_PREFIXES["medium"] + "bb/" + "2" * 38,
            "android": bundle_module.ROOT_PREFIXES["android"] + "cc/" + "3" * 38,
        }
        entries = (
            store_module.ManifestEntry(paths["medium"], 6, "22" * 32, "store:medium"),
            store_module.ManifestEntry(
                "WorldFlipper/dummy/info.json", 9, "55" * 32, "generated-marker"
            ),
            store_module.ManifestEntry(paths["common"], 5, "11" * 32, "store:common"),
            store_module.ManifestEntry(
                "WorldFlipper/dummy/download/.empty", 1, "44" * 32, "generated-marker"
            ),
            store_module.ManifestEntry(paths["android"], 7, "33" * 32, "store:android"),
        )
        services._entries = entries
        services._player_report = player_module.PlayerOverlayReport(
            logical_path=player_module.PLAYER_LOGICAL_PATH,
            relative_path=player_module.PLAYER_RELATIVE_PATH.as_posix(),
            before_sha256="66" * 32,
            after_sha256="77" * 32,
            before_character_ids=("1",),
            after_character_ids=("1", "129999", "139999", "149999"),
            added_character_ids=("129999", "139999", "149999"),
            character_level=1,
        )
        rogue = RogueDataReport(
            700099,
            15,
            2370099,
            tuple(range(8000101, 8000116)),
            (),
            True,
        )
        characters = tuple(
            content_module.CharacterEvidenceReport(
                {"character_id": character_id, "code_name": code_name},
                "published-snapshot",
                37,
                37,
                True,
                (),
                (),
                f"{index + 8:02x}" * 32,
            )
            for index, (character_id, code_name) in enumerate(
                (
                    (129999, "seris_dragon_king"),
                    (139999, "stella_summer_goddess"),
                    (149999, "white_wolf_gerald"),
                )
            )
        )
        services._content_client_report = content_module.OfflineContentReport(
            rogue, characters, True, True
        )
        services._zip_verify_report = types.SimpleNamespace(
            archive_sha256="88" * 32,
            member_count=5,
            total_uncompressed_bytes=28,
            zip64=True,
        )
        services._apk_report = types.SimpleNamespace(
            output_sha256="99" * 32,
            certificate_sha256="aa" * 32,
            patch_order=(
                "abyss-mode-equipment",
                "seris-phase4",
                "render-scale",
                "resource-version",
            ),
            stage_reports=(
                {"input_sha256": "bb" * 32, "output_sha256": "bc" * 32},
                {"input_sha256": "bc" * 32, "output_sha256": "bd" * 32},
                {"input_sha256": "bd" * 32, "output_sha256": "be" * 32},
                {"input_sha256": "be" * 32, "output_sha256": "cc" * 32},
            ),
            full_resource_version="1.4.196",
            aligned=True,
            signature_schemes={"v1": True, "v2": True, "v3": True},
            verified=True,
        )
        source_hash = sha256(self.source_apk.read_bytes())
        checkpoint = {
            "source_apk_sha256": source_hash,
            "store_tree_sha256": "dd" * 32,
            "source_apk_size": self.source_apk.stat().st_size,
            "store_total_bytes": 987_654_321,
            "store_counts": dict(module.EXPECTED_STORE_COUNTS),
        }
        source_fingerprint = {
            "before": dict(checkpoint),
            "scan": dict(checkpoint),
            "after": dict(checkpoint),
            "unchanged": True,
        }
        with mock.patch.object(
            services,
            "_git_output",
            side_effect=lambda args: "0123456789abcdef" if args[0] == "rev-parse" else " M user-wip",
        ):
            evidence = services._release_evidence(source_fingerprint)
            with self.assertRaisesRegex(module.ReleaseError, "source APK drift"):
                services._release_evidence(
                    {
                        **source_fingerprint,
                        "after": {**checkpoint, "source_apk_sha256": "00" * 32},
                    }
                )

        self.assertEqual(
            [entry["path"] for entry in evidence["data"]["entries"]],
            sorted(entry.path for entry in entries),
        )
        self.assertEqual(
            {entry["source"] for entry in evidence["data"]["entries"]},
            {"common", "medium", "android", "generated-marker"},
        )
        self.assertEqual(evidence["data"]["roots"]["common"]["bytes"], 5)
        self.assertEqual(evidence["data"]["roots"]["medium"]["bytes"], 6)
        self.assertEqual(evidence["data"]["roots"]["android"]["bytes"], 7)
        self.assertEqual(evidence["patches"]["before_swf_sha256"], "bb" * 32)
        self.assertEqual(evidence["patches"]["after_swf_sha256"], "cc" * 32)
        self.assertEqual(evidence["source_fingerprint"], source_fingerprint)
        self.assertEqual(
            set(evidence["apk"]),
            {
                "output_sha256",
                "certificate_sha256",
                "full_resource_version",
                "aligned",
                "signature_schemes",
                "verified",
            },
        )
        with (
            mock.patch.object(bundle_module, "PRODUCTION_ENTRY_COUNT", 5),
            mock.patch.object(
                bundle_module,
                "PRODUCTION_ROOT_COUNTS",
                {"common": 1, "medium": 1, "android": 1},
            ),
        ):
            self.assertEqual(bundle_module.validate_release_evidence(evidence), evidence)

    def test_scan_store_checkpoint_blocks_a_to_b_to_a_source_aba(self) -> None:
        services = FakeServices(self.config)
        services.scan_store_tree_sha256 = "7a" * 32

        with self.assertRaisesRegex(module.ReleaseError, "source store drift"):
            module.build_candidate(self.config, services=services)

        self.assertEqual(services.source_reads, 1)
        self.assertFalse(services.candidate_dir.exists())

    def test_preflight_requires_exact_store_legacy_tail_and_signer_evidence(self) -> None:
        services = FakeServices(self.config)
        report = services.preflight()
        self.assertEqual(module._validate_preflight(report), BUILD_ID)
        required = {
            "certificate_sha256",
            "fingerprint_verified",
            "store_counts",
            "legacy_count",
            "current_count",
            "added_count",
            "missing_count",
            "tail_member_count",
        }
        self.assertTrue(required.issubset(report["evidence"]))
        for name, value in (
            ("store_counts", {"common": 1, "medium": 2, "android": 3}),
            ("legacy_count", module.EXPECTED_LEGACY_COUNT - 1),
            ("added_count", module.EXPECTED_ADDED_COUNT + 1),
            ("tail_member_count", module.EXPECTED_TAIL_COUNT - 1),
            ("fingerprint_verified", False),
        ):
            with self.subTest(field=name):
                invalid = {
                    **report,
                    "evidence": {**report["evidence"], name: value},
                }
                with self.assertRaises(module.ReleaseError):
                    module._validate_preflight(invalid)

    @unittest.skipUnless(os.name == "nt", "Windows output-lease regression")
    def test_preflight_holds_output_chain_after_scope_check_against_rebind(self) -> None:
        config = self.make_config(self.root / "leased-output")
        config.output_root.mkdir()
        sentinel = config.output_root / "sentinel.txt"
        sentinel.write_text("keep", encoding="utf-8")
        services = FakeServices(config)
        original = services.preflight
        attempted = False

        def attack(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal attempted
            attempted = True
            with self.assertRaises(OSError):
                config.output_root.rename(config.output_root.with_name("rebound-output"))
            return original(*args, **kwargs)

        with mock.patch.object(services, "preflight", side_effect=attack):
            module.preflight_release(config, services=services)

        self.assertTrue(attempted)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    @unittest.skipUnless(os.name == "nt", "Windows output-lease regression")
    def test_unprotected_external_junction_is_rejected_before_preflight_side_effect(self) -> None:
        import subprocess

        real = self.root / "external-output-target"
        real.mkdir()
        sentinel = real / "sentinel.txt"
        sentinel.write_text("keep", encoding="utf-8")
        junction = self.root / "external-output-junction"
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(real)],
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            self.skipTest("cannot create a test junction")
        config = self.make_config(junction)
        services = FakeServices(config)
        try:
            with self.assertRaisesRegex(module.ReleaseError, "bind|reparse|plain"):
                module.preflight_release(config, services=services)
            self.assertEqual(services.calls, [])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        finally:
            junction.rmdir()

    @unittest.skipUnless(os.name == "nt", "Windows receipt-lease regression")
    def test_record_acceptance_holds_external_receipt_parent_during_write(self) -> None:
        config = self.make_config(self.root / "receipt-lease-output")
        services = module.RealReleaseServices(config)
        receipt_parent = self.root / "external-receipts"
        receipt_parent.mkdir()
        receipt = receipt_parent / "accepted.json"
        attempted = False

        def attack(*_args: Any, **_kwargs: Any) -> dict[str, bool]:
            nonlocal attempted
            attempted = True
            with self.assertRaises(OSError):
                receipt_parent.rename(receipt_parent.with_name("rebound-receipts"))
            return {"accepted": True}

        with mock.patch.object(
            services, "_record_manual_acceptance_bound", side_effect=attack
        ):
            result = services.record_manual_acceptance(
                BUILD_ID,
                SERIAL,
                receipt,
                {name: True for name in REQUIRED_MANUAL_CHECKS},
            )
        self.assertEqual(result, {"accepted": True})
        self.assertTrue(attempted)

    def test_independent_verifier_process_never_inherits_signer_password(self) -> None:
        observed: list[dict[str, Any]] = []

        def run(_command: Sequence[str], **kwargs: Any) -> object:
            observed.append(dict(kwargs))
            return object()

        secret = "must-not-reach-independent-verifiers"
        with (
            mock.patch.dict(os.environ, {module.PASSWORD_ENV: secret}, clear=False),
            mock.patch.object(module.subprocess, "run", side_effect=run),
        ):
            module.RealReleaseServices._verification_runner(["tool", "verify"])
            module.RealReleaseServices._verification_runner(
                ["tool", "verify"],
                env={"PATH": "fixture", module.PASSWORD_ENV.lower(): secret},
            )
        self.assertEqual(len(observed), 2)
        for call in observed:
            self.assertFalse(
                any(key.casefold() == module.PASSWORD_ENV.casefold() for key in call["env"])
            )
            self.assertIs(call["shell"], False)

    def test_independent_client_report_uses_locked_abyss_fqcn(self) -> None:
        target_class = "pinball.common.data.character.BattleCharacterLogic"
        lock = {
            "abyss_stage": {
                "before_method_sha256": "1" * 64,
                "target_class": target_class,
            },
            "post_abyss_swf_sha256": "2" * 64,
        }
        builder = mock.Mock()
        builder.canonical_json_bytes.side_effect = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        verifier_stages = [
            {
                "after_method_sha256": "3" * 64,
                "target_class": target_class,
            },
            {"verified": True},
            {"verified": True},
            {"verified": True},
        ]

        stages = module.RealReleaseServices._verified_client_stage_reports(
            builder,
            lock,
            verifier_stages,
            "0" * 64,
            "f" * 64,
        )

        self.assertEqual(stages[0]["target_class"], target_class)
        short_lock = {
            **lock,
            "abyss_stage": {
                **lock["abyss_stage"],
                "target_class": "BattleCharacterLogic",
            },
        }
        with self.assertRaisesRegex(module.ReleaseError, "abyss target class"):
            module.RealReleaseServices._verified_client_stage_reports(
                builder,
                short_lock,
                verifier_stages,
                "0" * 64,
                "f" * 64,
            )
        for verifier_target in ("BattleCharacterLogic", None):
            invalid_verifier_stages = [dict(stage) for stage in verifier_stages]
            if verifier_target is None:
                invalid_verifier_stages[0].pop("target_class")
            else:
                invalid_verifier_stages[0]["target_class"] = verifier_target
            with self.subTest(verifier_target=verifier_target), self.assertRaisesRegex(
                module.ReleaseError, "verifier abyss target class"
            ):
                module.RealReleaseServices._verified_client_stage_reports(
                    builder,
                    lock,
                    invalid_verifier_stages,
                    "0" * 64,
                    "f" * 64,
                )

    def test_independent_verifier_loads_only_public_signer_without_password_or_keystore(self) -> None:
        certificate = "a7" * 32
        release_home = self.root / "public-signer-only"
        release_home.mkdir()
        (release_home / "signer-public.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "alias": "wf-offline-release",
                    "certificate_sha256": certificate,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        config = replace(self.config, signing=None)
        services = module.RealReleaseServices(config)
        with (
            mock.patch.object(module, "DEFAULT_RELEASE_HOME", release_home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            signing = services._verification_signing(certificate)
        self.assertEqual(signing.expected_certificate_sha256, certificate)
        self.assertFalse((release_home / "wf-offline-release.jks").exists())

    def test_candidate_verify_fails_closed_when_independent_apk_gate_fails(self) -> None:
        import wf_offline_bundle as bundle_module

        identity = bundle_module.CandidateIdentity(
            BUILD_ID,
            sha256(APK_BYTES),
            sha256(DATA_ZIP_BYTES),
            sha256(GUIDE_BYTES),
            "ef" * 32,
        )
        services = module.RealReleaseServices(self.config)
        with (
            mock.patch.object(
                services,
                "_load_candidate",
                return_value=(self.root / f".candidate-{BUILD_ID}", identity, {}),
            ),
            mock.patch.object(
                services,
                "_independently_verify_release_artifacts",
                side_effect=module.ReleaseError("independent apksigner gate failed"),
            ) as independent_verify,
            self.assertRaisesRegex(module.ReleaseError, "apksigner gate failed"),
        ):
            module.verify_release(
                self.config,
                candidate_id=BUILD_ID,
                services=services,
            )
        independent_verify.assert_called_once()

    @unittest.skipUnless(os.name == "nt", "Windows release-file lease regression")
    def test_release_file_set_lease_denies_modify_replace_and_delete_until_closed(self) -> None:
        artifact_dir = self.root / "lease-artifacts"
        artifact_dir.mkdir()
        names = ("offline.apk", "data.zip", "guide.txt", "manifest.json", "SHA256SUMS.txt")
        for index, name in enumerate(names):
            (artifact_dir / name).write_bytes(f"payload-{index}".encode("ascii"))
        replacement = self.root / "replacement.tmp"
        replacement.write_bytes(b"replacement")

        locks = module._open_locked_release_files(artifact_dir, names)
        try:
            with self.assertRaises(OSError):
                (artifact_dir / "guide.txt").write_bytes(b"tampered")
            with self.assertRaises(OSError):
                os.replace(replacement, artifact_dir / "manifest.json")
            with self.assertRaises(OSError):
                (artifact_dir / "SHA256SUMS.txt").unlink()
            sixth = artifact_dir / "unexpected-secret.txt"
            sixth.write_bytes(b"must-not-be-deliverable")
            with self.assertRaisesRegex(module.ReleaseError, "member set changed"):
                module._require_locked_release_files(artifact_dir, locks, names)
            sixth.unlink()
            module._require_locked_release_files(artifact_dir, locks, names)
        finally:
            module._close_locked_release_files(locks)

        (artifact_dir / "guide.txt").write_bytes(b"after-close")
        self.assertEqual((artifact_dir / "guide.txt").read_bytes(), b"after-close")

    @unittest.skipUnless(os.name == "nt", "Windows owned snapshot lease regression")
    def test_owned_staging_snapshot_lock_reuses_bound_root_chain(self) -> None:
        source = self.root / "snapshot-source.apk"
        payload = b"independent-apk-snapshot"
        source.write_bytes(payload)
        owned = module._create_owned_staging(self.root / "snapshot-output" / "1.4.196")
        snapshot = owned.path / "independent.apk"
        source_lock = None
        snapshot_lock = None
        try:
            source_lock = module.RealReleaseServices._copy_locked_artifact(
                source,
                snapshot,
                sha256(payload),
            )
            snapshot_lock = module._open_locked_regular(snapshot, bound_root=owned)
            self.assertEqual(module._read_locked_regular(snapshot_lock), payload)
            with self.assertRaises(OSError):
                snapshot.write_bytes(b"tampered")
            with self.assertRaises(OSError):
                snapshot.unlink()

            nested = owned.path / "apk-independent"
            nested.mkdir()
            nested_file = nested / "base.apk"
            nested_file.write_bytes(payload)
            with module._locked_regular_guard(
                nested_file,
                bound_root=owned,
            ):
                with self.assertRaises(OSError):
                    nested_file.write_bytes(b"tampered")
                with self.assertRaises(OSError):
                    nested_file.unlink()
                with self.assertRaises(OSError):
                    nested_file.rename(nested_file.with_name("rebound.apk"))

            extracted = owned.path / "extracted" / "WorldFlipper" / "dummy"
            lease = module._acquire_directory_lease(
                extracted,
                bound_root=owned,
            )
            try:
                self.assertTrue(extracted.is_dir())
                with self.assertRaises(OSError):
                    extracted.rename(extracted.with_name("rebound"))
            finally:
                module._release_directory_lease(lease)

            with self.assertRaisesRegex(module.ReleaseError, "outside"):
                module._open_windows_directory_chain(self.root, bound_root=owned)
        finally:
            if snapshot_lock is not None:
                module._close_locked_regular(snapshot_lock)
            if source_lock is not None:
                module._close_locked_regular(source_lock)
            module._cleanup_owned_staging(owned)

    @unittest.skipUnless(os.name == "nt", "Windows fixed-drive regression")
    def test_release_directory_chain_rejects_mapped_network_drive(self) -> None:
        with (
            mock.patch.object(module, "_windows_drive_type", return_value=4) as drive_type,
            self.assertRaisesRegex(module.ReleaseError, "fixed local Windows drive"),
        ):
            module._windows_chain_paths(Path(r"Z:\\offline-release"))
        drive_type.assert_called_once_with("Z:\\")

    @unittest.skipUnless(os.name == "nt", "Windows extracted-content lease regression")
    def test_independent_extracted_content_is_deny_write_locked_until_gate_finishes(self) -> None:
        import wf_offline_bundle as bundle_module
        import wf_offline_store as store_module

        logical = "WorldFlipper/dummy/download/production/upload/aa/bb"
        unguarded_logical = "WorldFlipper/dummy/download/production/upload/cc/dd"
        payload = b"content-snapshot"
        archive = self.root / "small-data.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as writer:
            writer.writestr(logical, payload)
            writer.writestr(unguarded_logical, b"manifest-only")
        entry = store_module.ManifestEntry(
            logical,
            len(payload),
            sha256(payload),
            "common",
        )
        unguarded_entry = store_module.ManifestEntry(
            unguarded_logical,
            len(b"manifest-only"),
            sha256(b"manifest-only"),
            "common",
        )
        extraction = self.root / "independent-content"
        services = module.RealReleaseServices(self.config)
        zip_lock = module._open_locked_regular(archive)
        leases: tuple[Any, ...] = ()
        handles: tuple[int, ...] = ()
        try:
            roots, leases, handles = services._extract_verified_data_zip(
                archive,
                zip_lock,
                extraction,
                (entry, unguarded_entry),
                bundle_module,
                guard_paths={logical},
            )
            extracted = roots.common / "aa" / "bb"
            self.assertEqual(extracted.read_bytes(), payload)
            self.assertFalse((roots.common / "cc" / "dd").exists())
            with self.assertRaises(OSError):
                extracted.write_bytes(b"tampered")
            self.assertEqual(extracted.read_bytes(), payload)
        finally:
            for raw_handle in reversed(handles):
                module._close_windows_handle(raw_handle)
            for lease in reversed(leases):
                module._release_directory_lease(lease)
            module._close_locked_regular(zip_lock)

    def test_extraction_constructor_failure_closes_stream_and_all_leases(self) -> None:
        import wf_offline_bundle as bundle_module

        services = module.RealReleaseServices(self.config)
        stream = mock.Mock()
        leases = [mock.Mock(name=f"lease-{index}") for index in range(3)]
        released: list[Any] = []

        def release(lease: Any) -> None:
            released.append(lease)
            if len(released) == 1:
                raise OSError("fixture cleanup failure")

        with (
            mock.patch.object(module, "_acquire_directory_lease", side_effect=leases),
            mock.patch.object(module, "_release_directory_lease", side_effect=release),
            mock.patch.object(module.os, "dup", return_value=123),
            mock.patch.object(module.os, "fdopen", return_value=stream),
            mock.patch.object(
                module.zipfile,
                "ZipFile",
                side_effect=RuntimeError("zip constructor failure"),
            ),
            self.assertRaisesRegex(RuntimeError, "zip constructor failure") as caught,
        ):
            services._extract_verified_data_zip(
                self.root / "fixture.zip",
                mock.Mock(descriptor=7),
                self.root / "constructor-failure",
                (),
                bundle_module,
                guard_paths=(),
            )

        stream.close.assert_called_once_with()
        self.assertEqual(released, list(reversed(leases)))
        self.assertTrue(
            any("cleanup failed at content-directory-1" in note for note in caught.exception.__notes__)
        )

    def test_content_lock_plan_cross_checks_bound_roots_and_uses_code_rogue_closure(self) -> None:
        import wf_offline_bundle as bundle_module
        import wf_offline_content as content_module
        import wf_rogue_validate as rogue_module

        logical = content_module.CHARACTER_MASTER_LOGICAL
        evidence = {
            "content": {
                "characters": [
                    {
                        "bound_files": [
                            {
                                "path": f"roots/common/{logical}",
                                "source": "snapshot:common",
                            }
                        ]
                    }
                ]
            }
        }
        guarded, members = module.RealReleaseServices._content_lock_plan(
            evidence,
            content_module,
            bundle_module,
        )
        self.assertIn(("common", logical), guarded)
        self.assertIn(("common", content_module.PLAYER_CHARACTER_LOGICAL), guarded)
        for rogue_logical in rogue_module.offline_release_logicals():
            self.assertIn(("common", rogue_logical), guarded)
        self.assertLess(len(members), module.MAX_CONTENT_GUARDS)

        evidence["content"]["characters"][0]["bound_files"][0]["source"] = (
            "snapshot:medium"
        )
        with self.assertRaisesRegex(module.ReleaseError, "root/source binding"):
            module.RealReleaseServices._content_lock_plan(
                evidence,
                content_module,
                bundle_module,
            )

    def test_release_cleanup_runs_every_step_after_early_cleanup_failure(self) -> None:
        calls: list[str] = []

        def fail_first() -> None:
            calls.append("first")
            raise OSError("fixture cleanup failure")

        def release_final_lock() -> None:
            calls.append("final-lock")

        primary = module.ReleaseError("primary verification failure")
        with self.assertRaisesRegex(module.ReleaseError, "primary verification failure") as caught:
            try:
                raise primary
            finally:
                module._run_release_cleanup(
                    (
                        ("first", fail_first),
                        ("final-lock", release_final_lock),
                    )
                )
        self.assertEqual(calls, ["first", "final-lock"])
        self.assertTrue(
            any("cleanup failed at first" in note for note in caught.exception.__notes__)
        )


class OfflineReleaseCliTests(OfflineReleaseTestCase):
    def command_args(
        self,
        command: str,
        services: FakeServices,
        receipt: Path,
    ) -> list[str]:
        common = [
            "--source-apk",
            str(self.source_apk),
            "--snapshot-version",
            "1.4.196",
            "--output-root",
            str(services.config.output_root),
        ]
        if command == "preflight":
            return [command, *common]
        if command == "build-candidate":
            return [command, *common]
        if command == "device-probe":
            return [command, "--candidate", BUILD_ID, "--serial", SERIAL]
        if command == "prepare-device":
            return [
                command,
                "--candidate",
                BUILD_ID,
                "--serial",
                SERIAL,
                "--confirm",
                f"RESET_AND_REINSTALL_COM_LEITING_WF_ON_{SERIAL}",
            ]
        if command == "device-accept":
            return [
                command,
                "--candidate",
                BUILD_ID,
                "--serial",
                SERIAL,
                "--receipt-out",
                str(receipt),
            ]
        if command == "finalize":
            return [
                command,
                "--candidate",
                BUILD_ID,
                "--receipt",
                str(receipt),
            ]
        if command == "verify":
            return [command, "--bundle", str(services.final_dir)]
        if command == "init-signer":
            return [command, "--confirm", "CREATE_WF_OFFLINE_RELEASE_SIGNER"]
        raise AssertionError(command)

    def prepare_command_fixture(
        self, command: str, index: str
    ) -> tuple[Any, FakeServices, Path]:
        config = self.make_config(self.root / f"cli-{index}-{command}")
        services = FakeServices(config)
        receipt = self.root / f"receipt-{index}-{command}.json"
        if command in {"device-probe", "prepare-device", "device-accept", "finalize"}:
            services.seed_candidate()
        if command == "finalize":
            services.seed_receipt(receipt)
        if command == "verify":
            services.seed_final()
        return config, services, receipt

    def run_cli(
        self,
        command: str,
        config: Any,
        services: FakeServices,
        receipt: Path,
        *,
        input_fn: Callable[[str], str],
    ) -> tuple[int, str, dict[str, Any]]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = module.main(
                self.command_args(command, services, receipt),
                services=services,
                config=config,
                input_fn=input_fn,
            )
        lines = [line for line in output.getvalue().splitlines() if line.strip()]
        self.assertTrue(lines, f"{command} emitted no final JSON line")
        final_line = lines[-1]
        document = json.loads(final_line)
        self.assertEqual(top_level_json_keys(final_line), sorted(document))
        return exit_code, final_line, document

    def test_each_cli_command_ends_with_stable_json_line(self) -> None:
        for index, command in enumerate(COMMANDS):
            with self.subTest(command=command):
                config, services, receipt = self.prepare_command_fixture(
                    command, f"success-{index}"
                )
                prompts: list[str] = []
                answers = iter(["yes"] * len(REQUIRED_MANUAL_CHECKS))

                def input_fn(prompt: str) -> str:
                    if command != "device-accept":
                        raise AssertionError(f"{command} must not prompt")
                    prompts.append(prompt)
                    return next(answers)

                exit_code, final_line, document = self.run_cli(
                    command,
                    config,
                    services,
                    receipt,
                    input_fn=input_fn,
                )
                self.assertEqual(exit_code, 0, final_line)
                self.assertIs(document["ok"], True)
                self.assertEqual(document["command"], command)
                self.assertIsInstance(document["status"], str)
                if command in {"build-candidate", "finalize", "verify"}:
                    self.assertIs(document["deliverable"], command == "verify")
                if command == "device-accept":
                    self.assertEqual(len(prompts), len(REQUIRED_MANUAL_CHECKS))
                    self.assertEqual(
                        services.manual_checks_seen,
                        {name: True for name in REQUIRED_MANUAL_CHECKS},
                    )

    def test_real_cli_candidate_verify_without_injected_services_is_not_deliverable(self) -> None:
        import wf_offline_bundle as bundle_module

        output_root = self.root / "real-cli-candidate"
        identity = bundle_module.CandidateIdentity(
            BUILD_ID,
            sha256(APK_BYTES),
            sha256(DATA_ZIP_BYTES),
            sha256(GUIDE_BYTES),
            "ef" * 32,
        )
        output = io.StringIO()
        with (
            mock.patch.object(
                bundle_module,
                "verify_candidate",
                autospec=True,
                return_value=(identity, {"schema_version": 1}),
            ) as verify_candidate,
            mock.patch.object(
                bundle_module,
                "scan_release_for_secrets",
                autospec=True,
                return_value=PINNED_BASELINE_FINDINGS,
            ),
            mock.patch.object(
                module.RealReleaseServices,
                "_independently_verify_release_artifacts",
                autospec=True,
                return_value=INDEPENDENT_EVIDENCE,
            ) as independent_verify,
            contextlib.redirect_stdout(output),
        ):
            exit_code = module.main(
                [
                    "verify",
                    "--candidate",
                    BUILD_ID,
                    "--output-root",
                    str(output_root),
                    "--snapshot-version",
                    "1.4.196",
                ]
            )

        document = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(exit_code, 0, document)
        self.assertIs(document["deliverable"], False)
        self.assertEqual(document["candidate"], f".candidate-{BUILD_ID}")
        self.assertIsNone(document["final"])
        self.assertEqual(
            document["verification"],
            {"name": "candidate-verify", **INDEPENDENT_EVIDENCE},
        )
        verify_candidate.assert_called_once_with(
            output_root / "1.4.196" / f".candidate-{BUILD_ID}"
        )
        independent_verify.assert_called_once()

    def test_real_cli_final_bundle_verify_is_the_only_deliverable_result(self) -> None:
        import wf_offline_bundle as bundle_module

        final_dir = self.root / "exact-five-file-final"
        final_dir.mkdir()
        final_evidence = {
            name: {}
            for name in (
                "source_apk",
                "source_fingerprint",
                "patches",
                "signer",
                "versions",
                "data",
                "player",
                "content",
                "apk",
                "gates",
                "git",
            )
        }
        (final_dir / "build-manifest.json").write_bytes(
            bundle_module.canonical_json_bytes(final_evidence)
        )
        identity = bundle_module.CandidateIdentity(
            BUILD_ID,
            sha256(APK_BYTES),
            sha256(DATA_ZIP_BYTES),
            sha256(GUIDE_BYTES),
            "ef" * 32,
        )
        output = io.StringIO()
        with (
            mock.patch.object(
                bundle_module,
                "verify_final_bundle",
                autospec=True,
                return_value=identity,
            ) as verify_final,
            mock.patch.object(
                bundle_module,
                "scan_release_for_secrets",
                autospec=True,
                return_value=PINNED_BASELINE_FINDINGS,
            ),
            mock.patch.object(
                module.RealReleaseServices,
                "_independently_verify_release_artifacts",
                autospec=True,
                return_value=INDEPENDENT_EVIDENCE,
            ) as independent_verify,
            contextlib.redirect_stdout(output),
        ):
            exit_code = module.main(["verify", "--bundle", str(final_dir)])

        document = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(exit_code, 0, document)
        self.assertIs(document["deliverable"], True)
        self.assertIsNone(document["candidate"])
        self.assertEqual(document["final"], final_dir.name)
        self.assertEqual(
            document["verification"],
            {"name": "final-verify", **INDEPENDENT_EVIDENCE},
        )
        verify_final.assert_called_once_with(final_dir)
        independent_verify.assert_called_once()

    def test_each_cli_command_failure_is_nonzero_and_still_ends_with_json(self) -> None:
        failure_operation = {
            "preflight": "preflight",
            "build-candidate": "build-apk",
            "device-probe": "device-probe",
            "prepare-device": "prepare-device",
            "device-accept": "device-accept",
            "finalize": "finalize",
            "verify": "verify",
            "init-signer": "init-signer",
        }
        for index, command in enumerate(COMMANDS):
            with self.subTest(command=command):
                config, services, receipt = self.prepare_command_fixture(
                    command, f"failure-{index}"
                )
                services.failure_operation = failure_operation[command]
                answers = iter(["yes"] * len(REQUIRED_MANUAL_CHECKS))
                exit_code, final_line, document = self.run_cli(
                    command,
                    config,
                    services,
                    receipt,
                    input_fn=lambda _prompt: next(answers),
                )
                self.assertNotEqual(exit_code, 0, final_line)
                self.assertIs(document["ok"], False)
                self.assertEqual(document["command"], command)
                self.assertTrue(document["errors"])

    def test_device_accept_cannot_auto_fill_ten_true_checks(self) -> None:
        config, services, receipt = self.prepare_command_fixture(
            "device-accept", "no-input"
        )

        exit_code, final_line, document = self.run_cli(
            "device-accept",
            config,
            services,
            receipt,
            input_fn=lambda _prompt: (_ for _ in ()).throw(EOFError("no input")),
        )

        self.assertNotEqual(exit_code, 0, final_line)
        self.assertIs(document["ok"], False)
        self.assertIsNone(services.manual_checks_seen)
        self.assertFalse(receipt.exists())

    def test_device_accept_rejects_any_explicit_no_answer(self) -> None:
        config, services, receipt = self.prepare_command_fixture(
            "device-accept", "one-no"
        )
        answers = iter(["yes"] * 4 + ["no"] + ["yes"] * 5)

        exit_code, final_line, document = self.run_cli(
            "device-accept",
            config,
            services,
            receipt,
            input_fn=lambda _prompt: next(answers),
        )

        self.assertNotEqual(exit_code, 0, final_line)
        self.assertIs(document["ok"], False)
        self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

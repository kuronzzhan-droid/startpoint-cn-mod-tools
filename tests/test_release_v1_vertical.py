"""Temporary end-to-end character install and recovery acceptance."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest

from tests.release_v1_fixtures import make_patch_overlay, make_sealed_character_workspace
from tests.release_v1_mode_fixture import (
    MODE_CAPABILITY,
    MODE_FILE,
    MODE_NAME,
    make_character_mode_release,
    mode_payloads,
)
from tests.release_v1_schema_support import requirements_wire
from tests.test_release_v1_probe import (
    GENERAL_CAPABILITIES,
    MODE_CAPABILITIES,
    RUNTIME_FILES,
    SERVER_FILES,
    _runtime_manifest,
    _server_manifest,
)
from wf_release_v1._platform_state import ManagedProcess
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.compatibility import ActiveState
from wf_release_v1.errors import ReleaseError
from wf_release_v1.producer import BuildRequest, build_character_release
from wf_release_v1.receipts import (
    commit_active_state,
    load_active_state,
    load_operation_receipt,
)
from wf_release_v1.schema import parse_requirements
from wf_release_v1.target import ManagedTarget
from wf_release_v1.transaction import install_release


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


EMPTY_MODE_DIGEST = "sha256:" + hashlib.sha256(canonical_json_bytes([])).hexdigest()


def _capabilities(
    target_version: str,
    *,
    content_digest: str,
    loaded_modes: list[dict[str, object]] | None = None,
    mode_digest: str = EMPTY_MODE_DIGEST,
    mode_contract: bool = True,
) -> dict[str, object]:
    patch_versions = ["1.4.54"]
    if target_version != "1.4.54":
        patch_versions.append(target_version)
    return {
        "contractVersion": 1,
        "serverCapabilities": [
            item for item in GENERAL_CAPABILITIES
            if mode_contract or item != "mode.release-contract@1"
        ],
        "serverBundle": {
            "version": "1.0.1",
            "bundleId": _server_manifest()["bundleId"],
        },
        "runtime": {
            "api": 1,
            "node": "20.12.2",
            "nodeAbi": "115",
            "platform": "win32",
            "arch": "x64",
        },
        "content": {
            "source": "release",
            "assetVersion": target_version,
            "generatorVersion": 3,
            "releaseDigest": f"sha256:{SHA_C}",
            "contentDigest": content_digest,
            "cdnTargetVersion": target_version,
            "patchVersions": patch_versions,
        },
        "modes": {
            "api": 1,
            "serverCapabilities": [
                item for item in MODE_CAPABILITIES
                if mode_contract or item != "mode.release-contract@1"
            ],
            "loaded": loaded_modes or [],
            "modeDigest": mode_digest,
        },
        "features": {
            "patchOverlaySchema": 1,
            "modeChangesRequireRestart": True,
            "activeContentManagement": False,
        },
    }


class _LiveContract:
    def __init__(self) -> None:
        self.running = False
        self.managed_launch: dict[str, object] | None = None
        self.value = _capabilities("1.4.54", content_digest=f"sha256:{SHA_A}")
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib callback
                if not owner.running:
                    self.send_error(503)
                    return
                if self.path == "/healthz":
                    raw = canonical_json_bytes({
                        "contractVersion": 1,
                        "status": "ready",
                        "managedLaunch": owner.managed_launch,
                        "services": {"http": True, "tcp": True},
                    })
                elif self.path == "/api/server/capabilities":
                    raw = canonical_json_bytes(owner.value)
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, _format: str, *args: object) -> None:
                del args

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def close(self) -> None:
        self.server.shutdown()
        self.worker.join(timeout=5)
        self.server.server_close()


class _VerticalPlatform:
    def __init__(
        self,
        target: ManagedTarget,
        contract: _LiveContract,
        *,
        wrong_candidate: bool = False,
        wrong_mode: bool = False,
        mode_contract: bool = True,
        fail_start_number: int | None = None,
    ) -> None:
        self.target = target
        self.contract = contract
        self.wrong_candidate = wrong_candidate
        self.wrong_mode = wrong_mode
        self.mode_contract = mode_contract
        self.fail_start_number = fail_start_number
        self.current: ManagedProcess | None = None
        self.start_count = 0
        self.events: list[str] = []

    def current_process(self) -> ManagedProcess | None:
        self.events.append("current")
        return self.current

    def stop_owned(self, process: ManagedProcess, timeout: float) -> bool:
        del timeout
        self.events.append("stop")
        if process != self.current:
            raise AssertionError("attempted to stop an unowned process")
        self.current = None
        self.contract.running = False
        self.contract.managed_launch = None
        return False

    def prepare_content(self, launch, environment) -> None:
        del launch
        self.events.append("prepare")
        candidate = environment.cdn_root / "patches" / "1.4.55"
        if not candidate.is_dir():
            raise ReleaseError("WFREL_PROCESS_START", "candidate content is unavailable")
        pointer = environment.data_root / "state" / "content" / "current.json"
        pointer.write_bytes(canonical_json_bytes({"targetVersion": "1.4.55"}))

    def start_server(self, launch, environment, operation_id: str) -> ManagedProcess:
        del launch
        self.events.append("start")
        self.start_count += 1
        if self.start_count == self.fail_start_number:
            raise ReleaseError("WFREL_PROCESS_START", "injected recovery startup failure")
        candidate = (environment.cdn_root / "patches" / "1.4.55").is_dir()
        if candidate:
            version = "1.4.99" if self.wrong_candidate else "1.4.55"
            digest = f"sha256:{SHA_B}"
        else:
            version = "1.4.54"
            digest = f"sha256:{SHA_A}"
        loaded_modes: list[dict[str, object]] = []
        mode_digest = EMPTY_MODE_DIGEST
        module = environment.modes_root / MODE_FILE
        if module.is_file():
            module_digest = hashlib.sha256(module.read_bytes()).hexdigest()
            loaded_modes = [{
                "name": MODE_NAME,
                "capabilities": [MODE_CAPABILITY],
                "sha256": module_digest,
            }]
            mode_digest = "sha256:" + hashlib.sha256(canonical_json_bytes([{
                "capabilities": [MODE_CAPABILITY],
                "fileName": MODE_FILE,
                "name": MODE_NAME,
                "sha256": module_digest,
            }])).hexdigest()
            if self.wrong_mode:
                mode_digest = f"sha256:{SHA_D}"
        self.contract.value = _capabilities(
            version,
            content_digest=digest,
            loaded_modes=loaded_modes,
            mode_digest=mode_digest,
            mode_contract=self.mode_contract,
        )
        self.contract.running = True
        self.current = ManagedProcess(
            1000 + self.start_count,
            2000 + self.start_count,
            SHA_A,
            operation_id,
        )
        self.contract.managed_launch = {
            "operationId": self.current.operation_id,
            "pid": self.current.pid,
            **environment.health_bindings(),
        }
        return self.current

    def wait_exited(self, process: ManagedProcess, timeout: float) -> bool:
        del timeout
        return process != self.current


class CharacterInstallVerticalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-vertical-build-")
        cls.addClassCleanup(temporary.cleanup)
        root = Path(temporary.name)
        workspace = make_sealed_character_workspace(root / "workspace")
        overlay = make_patch_overlay(
            root / "source" / "worldflipper-overlay-1.4.54-to-1.4.55.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        cls.release = root / "seris-release.wf-release.zip"
        build_character_release(BuildRequest(
            name="seris-dragon-king",
            version="1.0.0",
            workspace=workspace,
            overlay_archives=(overlay,),
            output=cls.release,
            requirements=parse_requirements(requirements_wire()),
        ))
        cls.mode_release = make_character_mode_release(
            cls.release,
            root / "seris-mode-release.wf-release.zip",
        )

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-vertical-target-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        names = (
            "server", "runtime", "data", "state", "cdn", "modes",
            "candidate-content", "candidate-server", "candidate-modes",
        )
        self.roots = {name: self.root / name for name in names}
        for root in self.roots.values():
            root.mkdir()
        for files, root in (
            (SERVER_FILES, self.roots["server"]),
            (RUNTIME_FILES, self.roots["runtime"]),
        ):
            for relative, raw in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
        (self.roots["server"] / "server-manifest.json").write_bytes(
            canonical_json_bytes(_server_manifest())
        )
        (self.roots["runtime"] / "runtime-pack-manifest.json").write_bytes(
            canonical_json_bytes(_runtime_manifest())
        )
        (self.roots["runtime"] / "node_modules").mkdir()
        pointer = self.roots["data"] / "state" / "content" / "current.json"
        pointer.parent.mkdir(parents=True)
        self.baseline_pointer = canonical_json_bytes({"targetVersion": "1.4.54"})
        pointer.write_bytes(self.baseline_pointer)
        official = self.roots["cdn"] / "cn" / "official.bin"
        official.parent.mkdir()
        official.write_bytes(b"official-baseline")
        self.contract = _LiveContract()
        self.addCleanup(self.contract.close)
        target_path = self.root / "target.json"
        target_path.write_bytes(canonical_json_bytes({
            "schemaVersion": 1,
            "managedBy": "wf-release-v1",
            "serverBundle": str(self.roots["server"]),
            "runtimePack": str(self.roots["runtime"]),
            "dataRoot": str(self.roots["data"]),
            "stateRoot": str(self.roots["state"]),
            "cdnRoot": str(self.roots["cdn"]),
            "modesRoot": str(self.roots["modes"]),
            "componentRoots": {
                "content": str(self.roots["candidate-content"]),
                "server": str(self.roots["candidate-server"]),
                "modes": str(self.roots["candidate-modes"]),
            },
            "compatibility": {
                "clientVersion": "1.4.54",
                "resourceBaseline": "1.4.53",
                "clientPatchProfile": True,
            },
            "network": {"publicHost": "127.0.0.1"},
            "serverUrl": self.contract.base_url,
        }))
        self.target = ManagedTarget.load(target_path)
        empty = ActiveState(
            client_version=self.target.compatibility.client_version,
            resource_baseline=self.target.compatibility.resource_baseline,
            client_patch_profile=self.target.compatibility.client_patch_profile,
            releases=(),
            known_release_ids=(),
        )
        commit_active_state(self.target.state_root, previous=empty, active=empty)

    def _pointer(self) -> Path:
        return self.roots["data"] / "state" / "content" / "current.json"

    def test_stopped_target_without_bootstrap_state_cannot_install(self) -> None:
        (self.target.state_root / "active.json").unlink()
        (self.target.state_root / "previous.json").unlink()
        platform = _VerticalPlatform(self.target, self.contract)

        with self.assertRaises(ReleaseError) as caught:
            install_release(self.release, self.target, platform, health_timeout=2)

        self.assertEqual("WFREL_STATE_CONFLICT", caught.exception.code)
        self.assertEqual([], platform.events)
        self.assertFalse(self.contract.running)
        self.assertFalse((self.target.state_root / "receipts").exists())

    def test_build_verify_install_accept_and_repeat_as_noop(self) -> None:
        platform = _VerticalPlatform(self.target, self.contract)
        result = install_release(self.release, self.target, platform, health_timeout=2)

        self.assertEqual("succeeded", result.outcome)
        self.assertIsNotNone(result.operation_id)
        facts = self.target.target_probe(timeout_seconds=2).run()
        self.assertEqual("1.4.55", facts.cdn_target_version)
        active = load_active_state(self.target.state_root)
        self.assertEqual((result.release_id,), tuple(item.release_id for item in active.releases))
        self.assertEqual((result.release_id,), active.known_release_ids)
        self.assertEqual(
            {"targetVersion": "1.4.55"},
            json.loads(self._pointer().read_text(encoding="utf-8")),
        )
        self.assertEqual(
            b"official-baseline",
            (self.target.cdn_root / "cn" / "official.bin").read_bytes(),
        )
        self.assertTrue((self.target.cdn_root / "patches" / "1.4.55").is_dir())
        receipt = load_operation_receipt(self.target.state_root, result.operation_id)
        self.assertEqual(("COMMITTED", "succeeded"), (receipt.phase, receipt.outcome))
        before_starts = platform.start_count
        before_receipts = tuple((self.target.state_root / "receipts").iterdir())

        repeated = install_release(self.release, self.target, platform, health_timeout=2)

        self.assertEqual("noop", repeated.outcome)
        self.assertIsNone(repeated.operation_id)
        self.assertEqual(before_starts, platform.start_count)
        self.assertEqual(before_receipts, tuple((self.target.state_root / "receipts").iterdir()))

    def test_wrong_candidate_facts_restore_exact_baseline_and_service(self) -> None:
        platform = _VerticalPlatform(self.target, self.contract, wrong_candidate=True)
        result = install_release(self.release, self.target, platform, health_timeout=2)

        self.assertEqual("recovered", result.outcome)
        self.assertEqual("WFREL_REQUIRE_EXPECTED_CDN_STATE", result.error_code)
        self.assertEqual(self.baseline_pointer, self._pointer().read_bytes())
        self.assertFalse((self.target.cdn_root / "patches" / "1.4.55").exists())
        self.assertTrue(any(self.target.component_roots.content.rglob("1.4.55")))
        self.assertEqual("1.4.54", self.target.target_probe(timeout_seconds=2).run().cdn_target_version)
        self.assertIsNotNone(platform.current_process())
        self.assertEqual((), load_active_state(self.target.state_root).releases)
        receipt = load_operation_receipt(self.target.state_root, result.operation_id)
        self.assertEqual(("recovered", "recovered"), (receipt.outcome, receipt.recovery_outcome))

    def test_recovery_restart_failure_leaves_target_stopped_with_evidence(self) -> None:
        platform = _VerticalPlatform(
            self.target,
            self.contract,
            wrong_candidate=True,
            fail_start_number=3,
        )
        result = install_release(self.release, self.target, platform, health_timeout=2)

        self.assertEqual("recovery_failed", result.outcome)
        self.assertEqual("WFREL_RECOVERY_FAILED", result.error_code)
        self.assertIsNone(platform.current_process())
        self.assertFalse(self.contract.running)
        self.assertEqual(self.baseline_pointer, self._pointer().read_bytes())
        self.assertEqual((), load_active_state(self.target.state_root).releases)
        receipt = load_operation_receipt(self.target.state_root, result.operation_id)
        self.assertEqual(("recovery_failed", "failed"), (
            receipt.outcome,
            receipt.recovery_outcome,
        ))

    def test_combined_mode_release_is_accepted_only_after_restart(self) -> None:
        platform = _VerticalPlatform(self.target, self.contract)
        _payloads, expected_mode_digest = mode_payloads()

        result = install_release(self.mode_release, self.target, platform, health_timeout=2)

        self.assertEqual("succeeded", result.outcome)
        self.assertTrue((self.target.modes_root / MODE_FILE).is_file())
        facts = self.target.target_probe(timeout_seconds=2).run()
        self.assertEqual(expected_mode_digest, facts.mode_digest)
        self.assertEqual("1.4.55", facts.cdn_target_version)
        self.assertEqual(2, platform.start_count)

    def test_missing_mode_server_contract_stops_before_active_roots_change(self) -> None:
        platform = _VerticalPlatform(
            self.target,
            self.contract,
            mode_contract=False,
        )
        original_pointer = self._pointer().read_bytes()

        result = install_release(self.mode_release, self.target, platform, health_timeout=2)

        self.assertEqual("failed", result.outcome)
        self.assertEqual("WFREL_REQUIRE_SERVER_CAPABILITY", result.error_code)
        self.assertEqual(original_pointer, self._pointer().read_bytes())
        self.assertFalse((self.target.cdn_root / "patches" / "1.4.55").exists())
        self.assertEqual([], list(self.target.modes_root.iterdir()))
        self.assertNotIn("prepare", platform.events)

    def test_wrong_mode_digest_restores_content_and_mode_roots(self) -> None:
        platform = _VerticalPlatform(
            self.target,
            self.contract,
            wrong_mode=True,
        )

        result = install_release(self.mode_release, self.target, platform, health_timeout=2)

        self.assertEqual("recovered", result.outcome)
        self.assertEqual("WFREL_REQUIRE_EXPECTED_MODE_STATE", result.error_code)
        self.assertEqual(self.baseline_pointer, self._pointer().read_bytes())
        self.assertFalse((self.target.cdn_root / "patches" / "1.4.55").exists())
        self.assertEqual([], list(self.target.modes_root.iterdir()))
        candidates = tuple(self.target.component_roots.modes.rglob(MODE_FILE))
        self.assertEqual(1, len(candidates))
        self.assertEqual(EMPTY_MODE_DIGEST, self.target.target_probe(timeout_seconds=2).run().mode_digest)


if __name__ == "__main__":
    unittest.main()

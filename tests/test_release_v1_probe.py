"""Focused contracts for the read-only wf-release-v1 TargetProbe."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch

from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.errors import ReleaseError
from wf_release_v1.probe import TargetProbe


HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64
SERVER_FILES = {
    "out/cn-server.js": b"server\n",
    "out/content/sync/entry.js": b"prepare\n",
    "web/dist/index.html": b"<html></html>\n",
}
RUNTIME_FILES = {"node/bin/node": b"node\n"}
MODE_CAPABILITIES = (
    "mode.release-contract@1",
    "mode.hook.quest-start@1",
    "mode.hook.rush-finish@1",
    "mode.hook.rush-parties-serialized@1",
    "mode.host.base-table@1",
    "mode.host.transaction-server@1",
)
GENERAL_CAPABILITIES = (
    "content.sync@1",
    "mode.hook.quest-start@1",
    "mode.hook.rush-finish@1",
    "mode.hook.rush-parties-serialized@1",
    "mode.host.base-table@1",
    "mode.host.transaction-server@1",
    "mode.release-contract@1",
)


def _manifest_files(files: dict[str, bytes]) -> list[dict[str, object]]:
    return [
        {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for path, raw in files.items()
    ]


def _identity(value: dict[str, object], field: str) -> str:
    body = dict(value)
    del body[field]
    return f"sha256:{hashlib.sha256(canonical_json_bytes(body)).hexdigest()}"


def _server_manifest() -> dict[str, object]:
    value: dict[str, object] = {
        "schemaVersion": 3,
        "name": "starpoint-cn",
        "serverVersion": "1.0.1",
        "bundleId": f"sha256:{HEX_A}",
        "entry": "out/cn-server.js",
        "startup": {"localPrepareEntry": "out/content/sync/entry.js"},
        "requires": {
            "runtimeApi": 1,
            "node": ">=20.12.0",
            "dependencyLock": f"sha256:{HEX_B}",
            "minDataSchema": 0,
            "targetDataSchema": 15,
        },
        "admin": {"path": "web/dist", "required": True},
        "assets": {
            "supportedModes": ["client-owned", "local", "remote"],
            "minClientAssetVersion": "1.4.54",
        },
        "ports": {"http": 8001, "tcp": 8003},
        "files": _manifest_files(SERVER_FILES),
    }
    value["bundleId"] = _identity(value, "bundleId")
    return value


def _runtime_manifest() -> dict[str, object]:
    value: dict[str, object] = {
        "schemaVersion": 1,
        "runtimeId": f"sha256:{HEX_C}",
        "runtimeApi": 1,
        "node": {
            "version": "20.12.2",
            "abi": "115",
            "platform": "win32",
            "arch": "x64",
        },
        "dependencyLock": f"sha256:{HEX_B}",
        "entry": "node/bin/node",
        "executables": ["node/bin/node"],
        "files": _manifest_files(RUNTIME_FILES),
    }
    value["runtimeId"] = _identity(value, "runtimeId")
    return value


def _capabilities() -> dict[str, object]:
    return {
        "contractVersion": 1,
        "serverCapabilities": list(GENERAL_CAPABILITIES),
        "serverBundle": {"version": "1.0.1", "bundleId": _server_manifest()["bundleId"]},
        "runtime": {
            "api": 1,
            "node": "20.12.2",
            "nodeAbi": "115",
            "platform": "win32",
            "arch": "x64",
        },
        "content": {
            "source": "release",
            "assetVersion": "1.4.58",
            "generatorVersion": 3,
            "releaseDigest": f"sha256:{HEX_C}",
            "contentDigest": f"sha256:{HEX_D}",
            "cdnTargetVersion": "1.4.58",
            "patchVersions": ["1.4.55", "1.4.58"],
        },
        "modes": {
            "api": 1,
            "serverCapabilities": list(MODE_CAPABILITIES),
            "loaded": [],
            "modeDigest": f"sha256:{HEX_D}",
        },
        "features": {
            "patchOverlaySchema": 1,
            "modeChangesRequireRestart": True,
            "activeContentManagement": False,
        },
    }


@contextmanager
def _capabilities_server(
    value: dict[str, object] | None = None,
    *,
    payload: bytes | None = None,
    status: int = 200,
    content_type: str = "application/json; charset=utf-8",
    declared_length: int | None = None,
    location: str | None = None,
    delay: float = 0,
):
    body = payload if payload is not None else canonical_json_bytes(value)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            time.sleep(delay)
            if self.path != "/api/server/capabilities":
                self.send_error(404)
                return
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(declared_length if declared_length is not None else len(body)))
            if location is not None:
                self.send_header("Location", location)
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass

        def log_message(self, _format: str, *args: object) -> None:
            del args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/server/capabilities"
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


class TargetProbeTests(unittest.TestCase):
    def _write_target(
        self,
        root: Path,
        server_manifest: dict[str, object] | None = None,
        runtime_manifest: dict[str, object] | None = None,
    ) -> tuple[Path, Path]:
        server_root = root / "server"
        runtime_root = root / "runtime"
        server_root.mkdir()
        runtime_root.mkdir()
        server_path = server_root / "server-manifest.json"
        runtime_path = runtime_root / "runtime-pack-manifest.json"
        server_path.write_bytes(canonical_json_bytes(server_manifest or _server_manifest()))
        runtime_path.write_bytes(canonical_json_bytes(runtime_manifest or _runtime_manifest()))
        for files, parent in ((SERVER_FILES, server_root), (RUNTIME_FILES, runtime_root)):
            for relative_path, raw in files.items():
                path = parent / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
        return server_path, runtime_path

    def _run_probe(
        self,
        root: Path,
        capabilities: dict[str, object],
        *,
        server_manifest: dict[str, object] | None = None,
        runtime_manifest: dict[str, object] | None = None,
    ):
        server_path, runtime_path = self._write_target(root, server_manifest, runtime_manifest)
        with _capabilities_server(capabilities) as url:
            return TargetProbe(
                server_manifest=server_path,
                runtime_manifest=runtime_path,
                capabilities_url=url,
            ).run()

    def test_combines_three_authorities_into_immutable_target_facts(self) -> None:
        with TemporaryDirectory(prefix="wfrel-probe-") as temporary:
            root = Path(temporary)
            server_path, runtime_path = self._write_target(root)
            before = {path.name: path.read_bytes() for path in (server_path, runtime_path)}

            with _capabilities_server(_capabilities()) as url:
                facts = TargetProbe(
                    server_manifest=server_path,
                    runtime_manifest=runtime_path,
                    capabilities_url=url,
                ).run()

            self.assertEqual(_server_manifest()["bundleId"], facts.bundle_id)
            self.assertEqual("1.0.1", facts.server_version)
            self.assertEqual(_runtime_manifest()["runtimeId"], facts.runtime_id)
            self.assertEqual("20.12.2", facts.node_version)
            self.assertEqual(GENERAL_CAPABILITIES, facts.capabilities)
            self.assertEqual(f"sha256:{HEX_D}", facts.content_digest)
            self.assertEqual("1.4.58", facts.cdn_target_version)
            self.assertEqual(f"sha256:{HEX_D}", facts.mode_digest)
            self.assertEqual(1, facts.patch_overlay_schema)
            with self.assertRaises(FrozenInstanceError):
                facts.node_version = "20.12.3"  # type: ignore[misc]

            after = {path.name: path.read_bytes() for path in (server_path, runtime_path)}
            self.assertEqual(before, after)
            self.assertEqual(
                {"server", "runtime"},
                {path.name for path in root.iterdir()},
            )

    def test_rejects_inconsistent_content_snapshot_semantics(self) -> None:
        cases = (
            ("unknown-source", {"source": "mystery"}),
            ("bundled-with-release", {"source": "bundled"}),
            ("release-without-digest", {"releaseDigest": None}),
            ("noncanonical-patch-order", {"patchVersions": ["1.4.58", "1.4.55"]}),
        )
        for label, changes in cases:
            with self.subTest(label=label), TemporaryDirectory(prefix="wfrel-probe-") as temporary:
                capabilities = _capabilities()
                content = capabilities["content"]
                assert isinstance(content, dict)
                content.update(changes)
                if label == "bundled-with-release":
                    self.assertIsNotNone(content["releaseDigest"])
                with self.assertRaises(ReleaseError) as raised:
                    self._run_probe(Path(temporary), capabilities)
                self.assertEqual("WFREL_SCHEMA_INVALID", raised.exception.code)

    def test_rejects_unsafe_urls_and_http_responses(self) -> None:
        invalid_urls = (
            "https://127.0.0.1/api/server/capabilities",
            "http://user@127.0.0.1/api/server/capabilities",
            "http://192.0.2.1/api/server/capabilities",
            "http://[::ffff:192.0.2.1]/api/server/capabilities",
            "http://127.0.0.1/api/server/status",
        )
        for url in invalid_urls:
            with self.subTest(url=url), TemporaryDirectory(prefix="wfrel-probe-") as temporary:
                server_path, runtime_path = self._write_target(Path(temporary))
                with self.assertRaises(ReleaseError):
                    TargetProbe(server_path, runtime_path, url).run()

        duplicate = canonical_json_bytes(_capabilities()).replace(
            b'"contractVersion":1', b'"contractVersion":1,"contractVersion":1', 1,
        )
        large = _capabilities()
        large_modes = large["modes"]
        assert isinstance(large_modes, dict)
        large_modes["loaded"] = [{"name": "a" * (256 * 1024), "capabilities": [], "sha256": HEX_A}]
        responses = (
            {"status": 503},
            {"content_type": "text/plain"},
            {"payload": canonical_json_bytes(large)},
            {"status": 302, "location": "http://127.0.0.1/api/server/capabilities"},
            {"declared_length": len(canonical_json_bytes(_capabilities())) + 1},
            {"payload": duplicate},
        )
        for index, options in enumerate(responses):
            with self.subTest(response=index), TemporaryDirectory(prefix="wfrel-probe-") as temporary:
                server_path, runtime_path = self._write_target(Path(temporary))
                with _capabilities_server(_capabilities(), **options) as url:
                    with self.assertRaises(ReleaseError):
                        TargetProbe(server_path, runtime_path, url).run()

        with TemporaryDirectory(prefix="wfrel-probe-") as temporary:
            server_path, runtime_path = self._write_target(Path(temporary))
            with _capabilities_server(_capabilities(), delay=0.2) as url:
                with self.assertRaises(ReleaseError):
                    TargetProbe(server_path, runtime_path, url, timeout_seconds=0.02).run()

        with TemporaryDirectory(prefix="wfrel-probe-") as temporary:
            server_path, runtime_path = self._write_target(Path(temporary))
            poisoned = {"HTTP_PROXY": "http://127.0.0.1:9", "NO_PROXY": "", "no_proxy": ""}
            with _capabilities_server(_capabilities()) as url, patch.dict(os.environ, poisoned):
                facts = TargetProbe(server_path, runtime_path, url).run()
            self.assertEqual(GENERAL_CAPABILITIES, facts.capabilities)

    def test_rejects_capability_privacy_leaks_and_constant_drift(self) -> None:
        def loaded_path(value: dict[str, object]) -> None:
            modes = value["modes"]
            assert isinstance(modes, dict)
            modes["loaded"] = [{"name": "C:/private/mode", "capabilities": [], "sha256": HEX_A}]

        def feature(name: str, replacement: object):
            def mutate(value: dict[str, object]) -> None:
                features = value["features"]
                assert isinstance(features, dict)
                features[name] = replacement
            return mutate

        mutations = (
            loaded_path,
            *(lambda value, field=field: value.update({field: "secret"}) for field in ("pid", "token", "player", "memory")),
            feature("patchOverlaySchema", 2),
            feature("modeChangesRequireRestart", False),
            feature("activeContentManagement", True),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate.__name__), TemporaryDirectory(prefix="wfrel-probe-") as temporary:
                capabilities = _capabilities()
                mutate(capabilities)
                with self.assertRaises(ReleaseError) as raised:
                    self._run_probe(Path(temporary), capabilities)
                self.assertEqual("WFREL_SCHEMA_INVALID", raised.exception.code)

    def test_rejects_cross_authority_disagreement_without_inference(self) -> None:
        cases: list[tuple[str, dict[str, object], dict[str, object], str]] = []
        wrong_bundle = _capabilities()
        wrong_bundle["serverBundle"] = {"version": "1.0.1", "bundleId": f"sha256:{HEX_A}"}
        cases.append(("bundle", _server_manifest(), wrong_bundle, "WFREL_REQUIRE_TARGET"))

        wrong_runtime = _capabilities()
        runtime = wrong_runtime["runtime"]
        assert isinstance(runtime, dict)
        runtime["arch"] = "arm64"
        cases.append(("runtime", _server_manifest(), wrong_runtime, "WFREL_REQUIRE_TARGET"))

        inferred = _capabilities()
        inferred["serverCapabilities"] = list(MODE_CAPABILITIES)
        cases.append(("content-inference", _server_manifest(), inferred, "WFREL_SCHEMA_INVALID"))

        missing = _capabilities()
        del missing["serverCapabilities"]
        cases.append(("missing-top-level", _server_manifest(), missing, "WFREL_SCHEMA_INVALID"))

        for label, server_manifest, live, code in cases:
            with self.subTest(label=label), TemporaryDirectory(prefix="wfrel-probe-") as temporary:
                with self.assertRaises(ReleaseError) as raised:
                    self._run_probe(Path(temporary), live, server_manifest=server_manifest)
                self.assertEqual(code, raised.exception.code)

    def test_rejects_every_runtime_and_bundle_compatibility_mismatch(self) -> None:
        for field, replacement in (("node", "20.12.3"), ("nodeAbi", "116"), ("platform", "linux"), ("arch", "arm64")):
            with self.subTest(field=field), TemporaryDirectory(prefix="wfrel-probe-") as temporary:
                live = _capabilities()
                runtime = live["runtime"]
                assert isinstance(runtime, dict)
                runtime[field] = replacement
                with self.assertRaises(ReleaseError) as raised:
                    self._run_probe(Path(temporary), live)
                self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)

        runtime_manifest = _runtime_manifest()
        runtime_manifest["dependencyLock"] = f"sha256:{HEX_A}"
        runtime_manifest["runtimeId"] = _identity(runtime_manifest, "runtimeId")
        with TemporaryDirectory(prefix="wfrel-probe-") as temporary:
            with self.assertRaises(ReleaseError) as raised:
                self._run_probe(Path(temporary), _capabilities(), runtime_manifest=runtime_manifest)
            self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)

        server_manifest = _server_manifest()
        requires = server_manifest["requires"]
        assert isinstance(requires, dict)
        requires["node"] = ">=21.0.0"
        server_manifest["bundleId"] = _identity(server_manifest, "bundleId")
        live = _capabilities()
        live["serverBundle"] = {"version": "1.0.1", "bundleId": server_manifest["bundleId"]}
        with TemporaryDirectory(prefix="wfrel-probe-") as temporary:
            with self.assertRaises(ReleaseError) as raised:
                self._run_probe(Path(temporary), live, server_manifest=server_manifest)
            self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)

    def test_rejects_manifest_identity_and_declared_file_drift(self) -> None:
        cases: list[tuple[str, dict[str, object], dict[str, object]]] = []

        bad_bundle = _server_manifest()
        bad_bundle["bundleId"] = f"sha256:{HEX_A}"
        cases.append(("bundle-identity", bad_bundle, _runtime_manifest()))

        bad_runtime = _runtime_manifest()
        bad_runtime["runtimeId"] = f"sha256:{HEX_A}"
        cases.append(("runtime-identity", _server_manifest(), bad_runtime))

        bad_server_schema = _server_manifest()
        bad_server_schema["schemaVersion"] = 4
        bad_server_schema["bundleId"] = _identity(bad_server_schema, "bundleId")
        cases.append(("server-schema", bad_server_schema, _runtime_manifest()))

        bad_runtime_schema = _runtime_manifest()
        bad_runtime_schema["schemaVersion"] = 2
        bad_runtime_schema["runtimeId"] = _identity(bad_runtime_schema, "runtimeId")
        cases.append(("runtime-schema", _server_manifest(), bad_runtime_schema))

        bad_file = _server_manifest()
        server_files = bad_file["files"]
        assert isinstance(server_files, list) and isinstance(server_files[0], dict)
        server_files[0]["sha256"] = HEX_A
        bad_file["bundleId"] = _identity(bad_file, "bundleId")
        cases.append(("server-file-digest", bad_file, _runtime_manifest()))

        missing_entry = _server_manifest()
        missing_entry["files"] = [
            entry for entry in missing_entry["files"]  # type: ignore[union-attr]
            if entry["path"] != "out/cn-server.js"
        ]
        missing_entry["bundleId"] = _identity(missing_entry, "bundleId")
        cases.append(("missing-server-entry", missing_entry, _runtime_manifest()))

        for label, server_manifest, runtime_manifest in cases:
            with self.subTest(label=label), TemporaryDirectory(prefix="wfrel-probe-") as temporary:
                live = _capabilities()
                live["serverBundle"] = {
                    "version": "1.0.1",
                    "bundleId": server_manifest["bundleId"],
                }
                with self.assertRaises(ReleaseError) as raised:
                    self._run_probe(
                        Path(temporary),
                        live,
                        server_manifest=server_manifest,
                        runtime_manifest=runtime_manifest,
                    )
                self.assertEqual("WFREL_SCHEMA_INVALID", raised.exception.code)

        with TemporaryDirectory(prefix="wfrel-probe-") as temporary:
            root = Path(temporary)
            server_path, runtime_path = self._write_target(root)
            (server_path.parent / "personal.txt").write_text("not declared", encoding="utf-8")
            with _capabilities_server(_capabilities()) as url:
                with self.assertRaises(ReleaseError) as raised:
                    TargetProbe(server_path, runtime_path, url).run()
            self.assertEqual("WFREL_SCHEMA_INVALID", raised.exception.code)


if __name__ == "__main__":
    unittest.main()

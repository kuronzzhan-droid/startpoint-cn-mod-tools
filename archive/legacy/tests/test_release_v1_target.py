"""Focused contracts for host-local wf-release-v1 managed targets."""

from __future__ import annotations

from dataclasses import fields
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.errors import ReleaseError
from wf_release_v1.probe import RuntimeFacts, ServerBundleFacts, TargetProbe
from wf_release_v1.target import (
    ComponentRoots,
    LaunchSpec,
    ManagedTarget,
    TargetCompatibility,
    TargetNetwork,
)


HEX_A = "a" * 64


def _payload(root: Path) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "managedBy": "wf-release-v1",
        "serverBundle": str(root / "server-bundle"),
        "runtimePack": str(root / "runtime-pack"),
        "dataRoot": str(root / "data"),
        "stateRoot": str(root / "state"),
        "cdnRoot": str(root / "active" / "cdn"),
        "modesRoot": str(root / "active" / "modes"),
        "componentRoots": {
            "content": str(root / "components" / "content"),
            "server": str(root / "components" / "server"),
            "modes": str(root / "components" / "modes"),
        },
        "compatibility": {
            "clientVersion": "1.4.54",
            "resourceBaseline": "1.4.54",
            "clientPatchProfile": False,
        },
        "network": {"publicHost": "10.0.0.130"},
        "serverUrl": "http://127.0.0.1:8001",
    }


def _write_target(root: Path, payload: object | None = None, *, raw: bytes | None = None) -> Path:
    target_path = root / "target.json"
    target_path.write_bytes(raw if raw is not None else canonical_json_bytes(payload or _payload(root)))
    return target_path


class ManagedTargetTests(unittest.TestCase):
    def test_loads_exact_host_contract_and_constructs_the_only_target_probe(self) -> None:
        with TemporaryDirectory(prefix="wfrel-target-") as temporary:
            root = Path(temporary)
            target_path = _write_target(root)
            before = target_path.read_bytes()
            target = ManagedTarget.load(target_path)

            self.assertEqual(root / "server-bundle", target.server_bundle)
            self.assertEqual(root / "runtime-pack", target.runtime_pack)
            self.assertEqual(root / "data", target.data_root)
            self.assertEqual(root / "state", target.state_root)
            self.assertEqual(root / "active" / "cdn", target.cdn_root)
            self.assertEqual(root / "active" / "modes", target.modes_root)
            self.assertEqual(ComponentRoots(
                content=root / "components" / "content",
                server=root / "components" / "server",
                modes=root / "components" / "modes",
            ), target.component_roots)
            self.assertEqual(TargetCompatibility(
                client_version="1.4.54",
                resource_baseline="1.4.54",
                client_patch_profile=False,
            ), target.compatibility)
            self.assertEqual(TargetNetwork("10.0.0.130"), target.network)
            self.assertEqual(
                {
                    "server_bundle", "runtime_pack", "data_root", "state_root",
                    "cdn_root", "modes_root", "component_roots", "compatibility",
                    "server_url", "network",
                },
                {field.name for field in fields(target)},
            )
            probe = target.target_probe(timeout_seconds=2.5)
            self.assertIsInstance(probe, TargetProbe)
            self.assertEqual(root / "server-bundle" / "server-manifest.json", probe.server_manifest)
            self.assertEqual(root / "runtime-pack" / "runtime-pack-manifest.json", probe.runtime_manifest)
            self.assertEqual("http://127.0.0.1:8001", target.server_url)
            self.assertEqual("http://127.0.0.1:8001/api/server/capabilities", target.capabilities_url)
            self.assertEqual("http://127.0.0.1:8001/healthz", target.health_url)
            self.assertEqual(target.capabilities_url, probe.capabilities_url)
            self.assertEqual(2.5, probe.timeout_seconds)
            self.assertEqual(before, target_path.read_bytes())
            self.assertEqual({"target.json"}, {path.name for path in root.iterdir()})

    def test_launch_spec_uses_only_entries_returned_by_the_validated_probe(self) -> None:
        with TemporaryDirectory(prefix="wfrel-target-") as temporary:
            root = Path(temporary)
            target = ManagedTarget.load(_write_target(root))
            server = ServerBundleFacts(
                version="1.0.0", bundle_id=f"sha256:{HEX_A}", runtime_api=1,
                node_requirement=">=20.0.0", dependency_lock=f"sha256:{HEX_A}",
                entry="validated/server.js", local_prepare_entry="validated/prepare.js",
            )
            runtime = RuntimeFacts(
                runtime_id=f"sha256:{HEX_A}", runtime_api=1, node_version="20.0.0",
                node_abi="115", platform="win32", arch="x64",
                dependency_lock=f"sha256:{HEX_A}", entry="validated/node.exe",
            )
            with patch.object(TargetProbe, "manifest_facts", return_value=(server, runtime)) as read:
                launch = target.launch_spec()
            self.assertEqual(LaunchSpec(
                executable=root / "runtime-pack" / "validated" / "node.exe",
                prepare_entry=root / "server-bundle" / "validated" / "prepare.js",
                server_entry=root / "server-bundle" / "validated" / "server.js",
                cwd=root / "server-bundle",
            ), launch)
            read.assert_called_once_with()

    def test_server_url_is_one_canonical_managed_loopback_base_origin(self) -> None:
        with TemporaryDirectory(prefix="wfrel-target-") as temporary:
            root = Path(temporary)
            for accepted in (
                "http://127.0.0.1:8001",
            ):
                with self.subTest(accepted=accepted):
                    payload = _payload(root); payload["serverUrl"] = accepted
                    target = ManagedTarget.load(_write_target(root, payload))
                    self.assertEqual(accepted + "/api/server/capabilities", target.capabilities_url)
                    self.assertEqual(accepted + "/healthz", target.health_url)

            for rejected in (
                "https://127.0.0.1:8001",
                "http://127.0.0.1",
                "http://127.0.0.1:0",
                "http://127.0.0.1:65536",
                "http://127.0.0.1:8001/",
                "http://127.0.0.1:8001/api/server/capabilities",
                "http://user@127.0.0.1:8001",
                "http://127.0.0.1:8001?query=1",
                "http://127.0.0.1:8001#fragment",
                "http://0.0.0.0:8001",
                "http://127.0.0.2:8001",
                "http://localhost:8001",
                "http://[::1]:8001",
                "http://10.0.0.130:8001",
                "http://172.15.255.255:8001",
                "http://172.32.0.1:8001",
                "http://192.0.2.1:8001",
                "http://[::ffff:192.0.2.1]:8001",
                "http://[::ffff:7f00:1]:8001",
                "http://[0:0:0:0:0:0:0:1]:8001",
                "http://example.invalid:8001",
                "HTTP://LOCALHOST:8001",
            ):
                with self.subTest(rejected=rejected):
                    payload = _payload(root); payload["serverUrl"] = rejected
                    with self.assertRaises(ReleaseError) as raised:
                        ManagedTarget.load(_write_target(root, payload))
                    self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)

    def test_public_host_is_one_canonical_local_ipv4_address(self) -> None:
        with TemporaryDirectory(prefix="wfrel-target-") as temporary:
            root = Path(temporary)
            for accepted in (
                "127.0.0.1", "10.20.30.40", "172.16.0.1",
                "172.31.255.254", "10.0.0.130",
            ):
                with self.subTest(accepted=accepted):
                    payload = _payload(root)
                    payload["network"] = {"publicHost": accepted}
                    self.assertEqual(
                        accepted,
                        ManagedTarget.load(_write_target(root, payload)).public_host,
                    )
            for rejected in (
                "0.0.0.0", "192.0.2.1", "172.15.255.255", "172.32.0.1",
                "localhost", "::1", "010.0.0.130",
            ):
                with self.subTest(rejected=rejected):
                    payload = _payload(root)
                    payload["network"] = {"publicHost": rejected}
                    with self.assertRaises(ReleaseError) as raised:
                        ManagedTarget.load(_write_target(root, payload))
                    self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)

    def test_rejects_non_exact_or_ambiguous_target_documents(self) -> None:
        with TemporaryDirectory(prefix="wfrel-target-") as temporary:
            root = Path(temporary)
            cases: list[tuple[str, object]] = []
            for label, key, value in (
                ("bool-schema", "schemaVersion", True),
                ("future-schema", "schemaVersion", 2),
                ("wrong-owner", "managedBy", "other-tool"),
                ("bad-url-type", "serverUrl", 8001),
                ("bad-path-type", "stateRoot", [str(root / "state")]),
            ):
                payload = _payload(root); payload[key] = value; cases.append((label, payload))
            extra = _payload(root); extra["unknown"] = True; cases.append(("extra-key", extra))
            missing = _payload(root); del missing["dataRoot"]; cases.append(("missing-key", missing))
            network_extra = _payload(root)
            assert isinstance(network_extra["network"], dict)
            network_extra["network"]["other"] = True
            cases.append(("network-extra", network_extra))
            component_extra = _payload(root)
            assert isinstance(component_extra["componentRoots"], dict)
            component_extra["componentRoots"]["other"] = str(root / "other")
            cases.append(("component-extra", component_extra))
            compatibility_extra = _payload(root)
            assert isinstance(compatibility_extra["compatibility"], dict)
            compatibility_extra["compatibility"]["other"] = True
            cases.append(("compatibility-extra", compatibility_extra))
            for label, key, value in (
                ("bad-client-version", "clientVersion", "latest"),
                ("bad-resource-baseline", "resourceBaseline", "01.4"),
                ("bad-client-patch-profile", "clientPatchProfile", 0),
            ):
                payload = _payload(root)
                compatibility = payload["compatibility"]
                assert isinstance(compatibility, dict)
                compatibility[key] = value
                cases.append((label, payload))
            for label, payload in cases:
                with self.subTest(label=label):
                    with self.assertRaises(ReleaseError) as raised:
                        ManagedTarget.load(_write_target(root, payload))
                    self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)

            raw = canonical_json_bytes(_payload(root)).replace(
                b'"schemaVersion":1', b'"schemaVersion":1,"schemaVersion":1', 1,
            )
            with self.assertRaises(ReleaseError) as duplicate:
                ManagedTarget.load(_write_target(root, raw=raw))
            self.assertEqual("WFREL_JSON_DUPLICATE_KEY", duplicate.exception.code)

    def test_rejects_relative_noncanonical_and_protected_roots(self) -> None:
        with TemporaryDirectory(prefix="wfrel-target-") as temporary:
            root = Path(temporary)
            tool_root = Path(__file__).resolve().parents[1]
            cases = (
                ("relative-bundle", "serverBundle", "relative/server"),
                ("relative-runtime", "runtimePack", "relative/runtime"),
                ("relative-data", "dataRoot", "relative/data"),
                ("relative-state", "stateRoot", "relative/state"),
                ("relative-cdn", "cdnRoot", "relative/cdn"),
                ("relative-active-modes", "modesRoot", "relative/modes"),
                ("relative-content", "componentRoots.content", "relative/content"),
                ("relative-server", "componentRoots.server", "relative/server-root"),
                ("relative-modes", "componentRoots.modes", "relative/modes"),
                ("parent-segment", "stateRoot", f"{root}{os.sep}state{os.sep}..{os.sep}other"),
                ("dot-segment", "stateRoot", f"{root}{os.sep}.{os.sep}state"),
                ("drive-root", "stateRoot", root.anchor),
                ("tool-root", "stateRoot", str(tool_root)),
                ("home-root", "stateRoot", str(Path.home())),
            )
            expected_messages = {
                "drive-root": "stateRoot must be an absolute canonical path",
                "home-root": "stateRoot uses a protected root",
            }
            for label, key, value in cases:
                with self.subTest(label=label):
                    payload = _payload(root)
                    if key.startswith("componentRoots."):
                        components = payload["componentRoots"]
                        assert isinstance(components, dict)
                        components[key.removeprefix("componentRoots.")] = value
                    else:
                        payload[key] = value
                    with self.assertRaises(ReleaseError) as raised:
                        ManagedTarget.load(_write_target(root, payload))
                    self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)
                    if label in expected_messages:
                        self.assertEqual(expected_messages[label], raised.exception.message)

    def test_rejects_every_managed_root_overlap(self) -> None:
        with TemporaryDirectory(prefix="wfrel-target-") as temporary:
            root = Path(temporary)
            cases = (
                ("state-equals-content", "stateRoot", "content", "same"),
                ("state-equals-server", "stateRoot", "server", "same"),
                ("state-equals-modes", "stateRoot", "modes", "same"),
                ("content-inside-state", "stateRoot", "content", "child"),
                ("state-inside-content", "content", "stateRoot", "child"),
                ("server-inside-content", "content", "server", "child"),
                ("modes-equals-content", "content", "modes", "same"),
                ("modes-equals-server", "modes", "server", "same"),
                ("cdn-equals-state", "stateRoot", "cdnRoot", "same"),
                ("active-modes-inside-cdn", "cdnRoot", "modesRoot", "child"),
                ("candidate-content-inside-cdn", "cdnRoot", "content", "child"),
                ("data-inside-active-modes", "modesRoot", "dataRoot", "child"),
            )
            for label, parent_key, child_key, relation in cases:
                with self.subTest(label=label):
                    payload = _payload(root)
                    components = payload["componentRoots"]
                    assert isinstance(components, dict)
                    paths = {
                        "dataRoot": payload["dataRoot"],
                        "stateRoot": payload["stateRoot"],
                        "cdnRoot": payload["cdnRoot"],
                        "modesRoot": payload["modesRoot"],
                        **components,
                    }
                    parent = Path(paths[parent_key])
                    value = parent if relation == "same" else parent / "nested"
                    if child_key in {"dataRoot", "stateRoot", "cdnRoot", "modesRoot"}:
                        payload[child_key] = str(value)
                    else: components[child_key] = str(value)
                    with self.assertRaises(ReleaseError) as raised:
                        ManagedTarget.load(_write_target(root, payload))
                    self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)

    def test_direct_construction_cannot_bypass_managed_root_invariants(self) -> None:
        with TemporaryDirectory(prefix="wfrel-target-") as temporary:
            root = Path(temporary)
            with self.assertRaises(ReleaseError) as raised:
                ManagedTarget(
                    server_bundle=Path.home(), runtime_pack=root / "runtime",
                    data_root=root / "data", state_root=root / "state",
                    cdn_root=root / "cdn", modes_root=root / "active-modes",
                    component_roots=ComponentRoots(root / "content", root / "server-root", root / "modes"),
                    compatibility=TargetCompatibility("1.4.54", "1.4.54", False),
                    server_url="http://127.0.0.1:8001",
                )
            self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)

    def test_rejects_unavailable_or_unsafe_target_file_without_path_disclosure(self) -> None:
        with TemporaryDirectory(prefix="wfrel-target-") as temporary:
            root = Path(temporary)
            targets = (root / "missing.json", root)
            for target_path in targets:
                with self.subTest(kind=target_path.name):
                    with self.assertRaises(ReleaseError) as raised:
                        ManagedTarget.load(target_path)
                    self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)
                    surface = f"{raised.exception!s}\n{raised.exception!r}\n{raised.exception.details!r}"
                    self.assertNotIn(str(root), surface)
            oversized = root / "oversized.json"
            oversized.write_bytes(b" " * (64 * 1024 + 1))
            with self.assertRaises(ReleaseError) as raised:
                ManagedTarget.load(oversized)
            self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)


if __name__ == "__main__":
    unittest.main()

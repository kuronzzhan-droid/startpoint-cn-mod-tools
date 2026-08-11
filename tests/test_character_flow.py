# -*- coding: utf-8 -*-
"""Unified character-flow CLI tests (temporary roots and injected release API)."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_character_flow as flow  # noqa: E402
import wf_character_workspace as workspace_module  # noqa: E402
import wf_dev_catalog as dev_catalog  # noqa: E402
import wf_release  # noqa: E402


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        digest.update(path.relative_to(root).as_posix().encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


class FakeReleaseModule:
    def __init__(self):
        self.preflight_calls = []
        self.publish_calls = []

    def preflight_package(self, package_dir, profile_id, installed_package_dir=None):
        self.preflight_calls.append((Path(package_dir), profile_id, installed_package_dir))
        return {"can_prepare": False, "conflicts": [{"kind": "fixture"}]}

    def publish_package(self, package_dir, profile_id, confirmation, installed_package_dir=None):
        self.publish_calls.append((Path(package_dir), profile_id, confirmation, installed_package_dir))
        return SimpleNamespace(
            committed=True,
            release_id="release-1",
            from_version="1.4.139",
            version="1.4.140",
            active_manifest_sha256="a" * 64,
            archive_paths=(Path("common.zip"),),
            snapshot_dir=Path("snapshot-1"),
        )


class FakeRebaseModule:
    def __init__(self):
        self.calls = []

    def rebase_package(
        self, package_dir, profile_id, *, output_dir, generator_git_head=None,
    ):
        self.calls.append((Path(package_dir), profile_id, Path(output_dir), generator_git_head))
        shutil.copytree(package_dir, output_dir)
        (Path(output_dir) / "rebased.marker").write_text("rebased", encoding="utf-8")
        return SimpleNamespace(
            output_dir=Path(output_dir),
            source_manifest_sha256="a" * 64,
            manifest_sha256="b" * 64,
            table_count=1,
        )


class ReadyPreflightModule(FakeReleaseModule):
    def preflight_package(self, package_dir, profile_id, installed_package_dir=None):
        self.preflight_calls.append((Path(package_dir), profile_id, installed_package_dir))
        return {"can_prepare": True, "release_ready": True, "conflicts": []}


class CdnReleaseModule(FakeReleaseModule):
    """归档落进真实链根的 release 模块(dev catalog 钩子应当发射)。"""

    def __init__(self, cdn_root: Path):
        super().__init__()
        self.cdn_root = Path(cdn_root)

    def publish_package(self, package_dir, profile_id, confirmation, installed_package_dir=None):
        result = super().publish_package(
            package_dir, profile_id, confirmation,
            installed_package_dir=installed_package_dir,
        )
        archive = (
            self.cdn_root / "archive-common-diff"
            / "pinball-1.4.139-1.4.140-1-charpkg-seris-r1-common.zip"
        )
        archive.write_bytes(b"archive")
        return SimpleNamespace(**{**vars(result), "archive_paths": (archive,)})


class TestCharacterFlow(unittest.TestCase):
    def test_master_gate_uses_target_store_before_profile_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_store = root / "env-store"
            profile_store = root / "profile-store"
            fallback = root / "fallback"
            for directory in (env_store, profile_store, fallback):
                directory.mkdir()
            profile = flow.core.VersionProfile(
                id="cn", label="CN", store=profile_store, fallback=fallback
            )
            with patch.object(
                flow.core, "resolve_profile", return_value=profile
            ), patch.dict(
                os.environ, {"WF_TARGET_STORE": str(env_store)}, clear=False
            ):
                stores = flow._master_gate_stores("cn")

        self.assertEqual((env_store.resolve(), fallback), stores)

    def test_explicit_apk_wins_over_the_legacy_embedded_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool_dir = root / "mod-tools"
            legacy_dir = root / "弹国服"
            tool_dir.mkdir()
            legacy_dir.mkdir()
            legacy_bundle = legacy_dir / "bundle.zip"
            explicit_apk = root / "configured.apk"
            with zipfile.ZipFile(legacy_bundle, "w") as archive:
                archive.writestr("legacy/aa/old", b"old")
            with zipfile.ZipFile(explicit_apk, "w") as archive:
                archive.writestr("configured/bb/new", b"new")

            flow._BUNDLE_INDEX_CACHE.clear()
            try:
                with patch.object(
                    flow, "__file__", str(tool_dir / "wf_character_flow.py")
                ), patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("WF_APK", None)
                    self.assertEqual(
                        frozenset({"aa/old"}),
                        flow._bundle_asset_tails(),
                    )
                    os.environ["WF_APK"] = str(explicit_apk)
                    tails = flow._bundle_asset_tails()
            finally:
                flow._BUNDLE_INDEX_CACHE.clear()

            self.assertIn("bb/new", tails)
            self.assertNotIn("aa/old", tails)

    def test_preflight_auto_seals_complete_production_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = workspace_module.init_workspace(
                Path(tmp), 111165, 129999, "seris_dragon_king", "seris",
            )
            complete = SimpleNamespace(
                release_ready=False,
                requirement_report={
                    "release_ready": True,
                    "required_total": 37,
                    "required_present": 37,
                },
                three_layer_claim_status={"consistent": True},
                manifest_errors=(),
                next_command="preflight",
                to_dict=lambda: {"release_ready": False},
            )
            sealed = SimpleNamespace(
                release_ready=True,
                next_command="publish",
                to_dict=lambda: {"release_ready": True},
            )
            fake = ReadyPreflightModule()
            with patch.object(
                flow.workspace_module, "workspace_status", return_value=complete
            ), patch.object(
                flow.workspace_module, "seal_workspace", return_value=sealed
            ) as seal:
                code, result = flow.run_command([
                    "preflight", "--workspace", str(workspace.root),
                ], release_module=fake)

            self.assertEqual(0, code)
            self.assertTrue(result["release_ready"])
            seal.assert_called_once_with(workspace)

    def test_production_rebase_replaces_package_and_reseals_workspace_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = workspace_module.init_workspace(
                Path(tmp), 111165, 129999, "seris_dragon_king", "seris",
            )
            fake = FakeRebaseModule()
            ready = SimpleNamespace(release_ready=True)
            sealed = SimpleNamespace(
                release_ready=True,
                input_digest="c" * 64,
                to_dict=lambda: {"release_ready": True, "input_digest": "c" * 64},
            )
            with patch.object(
                flow.workspace_module, "workspace_status", return_value=ready
            ), patch.object(
                flow.workspace_module, "seal_workspace", return_value=sealed
            ) as resealed:
                code, result = flow.run_command([
                    "rebase", "--workspace", str(workspace.root),
                ], release_module=fake)

            self.assertEqual(0, code)
            self.assertTrue(result["release_ready"])
            self.assertTrue((workspace.package_dir / "rebased.marker").is_file())
            self.assertFalse((workspace.root / "rebased-package").exists())
            self.assertEqual([], list(workspace.root.glob("package-pre-rebase-*")))
            resealed.assert_called_once()

    def test_production_rebase_seal_failure_restores_original_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = workspace_module.init_workspace(
                Path(tmp), 111165, 129999, "seris_dragon_king", "seris",
            )
            (workspace.package_dir / "original.marker").write_text("original", encoding="utf-8")
            fake = FakeRebaseModule()
            with patch.object(
                flow.workspace_module,
                "workspace_status",
                return_value=SimpleNamespace(release_ready=True),
            ), patch.object(
                flow.workspace_module,
                "seal_workspace",
                side_effect=workspace_module.WorkspaceError("fixture seal failure"),
            ):
                code, result = flow.run_command([
                    "rebase", "--workspace", str(workspace.root),
                ], release_module=fake)

            self.assertEqual(2, code)
            self.assertIn("activation failed", " ".join(result["errors"]))
            self.assertTrue((workspace.package_dir / "original.marker").is_file())
            self.assertFalse((workspace.package_dir / "rebased.marker").exists())
            self.assertTrue((workspace.root / "rebased-package" / "rebased.marker").is_file())
            self.assertEqual([], list(workspace.root.glob("package-pre-rebase-*")))

    def test_rollback_requires_distinct_confirmation_before_release_call(self):
        code, result = flow.run_command([
            "rollback", "--snapshot-dir", "missing", "--confirm", "yes",
        ])

        self.assertEqual(2, code)
        self.assertIn("ROLLBACK_CHARACTER_PACKAGE", " ".join(result["errors"]))

    def test_rollback_delegates_to_snapshot_release_api(self):
        released = SimpleNamespace(
            committed=True,
            release_id="rollback-1",
            from_version="1.4.140",
            version="1.4.141",
            active_manifest_sha256="b" * 64,
            archive_paths=(Path("rollback-common.zip"),),
            snapshot_dir=None,
        )
        with patch(
            "wf_character_rollback.publish_snapshot_rollback",
            return_value=released,
        ) as delegated:
            code, result = flow.run_command([
                "rollback",
                "--snapshot-dir", "snapshot-1",
                "--profile", "cn",
                "--installed-package-dir", "installed",
                "--confirm", "ROLLBACK_CHARACTER_PACKAGE",
            ])

        self.assertEqual(0, code)
        self.assertEqual("1.4.141", result["version"])
        delegated.assert_called_once_with(
            Path("snapshot-1"),
            profile_id="cn",
            confirmation="ROLLBACK_CHARACTER_PACKAGE",
            installed_package_dir=Path("installed"),
        )

    def test_init_and_status_write_only_inside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            live = base / "live"
            live.mkdir()
            before = tree_digest(live)

            code, initialized = flow.run_command([
                "init", "--root", str(base / "packs"),
                "--template-id", "111165", "--character-id", "129999",
                "--code-name", "seris_dragon_king", "--package-id", "seris",
            ])
            status_code, status = flow.run_command([
                "status", "--workspace", initialized["workspace"],
            ])

            self.assertEqual(0, code)
            self.assertEqual(0, status_code)
            self.assertTrue(initialized["ok"])
            self.assertEqual("status", status["stage"])
            self.assertFalse(status["release_ready"])
            self.assertEqual(before, tree_digest(live))

    def test_preflight_never_writes_live_roots_or_cdn(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = workspace_module.init_workspace(
                base / "packs", 111165, 129999, "seris_dragon_king", "seris",
            )
            live = base / "live"
            cdn = base / "cdn"
            live.mkdir()
            cdn.mkdir()
            (live / "keep.bin").write_bytes(b"live")
            before_live = tree_digest(live)
            before_cdn = tree_digest(cdn)
            fake = FakeReleaseModule()

            code, result = flow.run_command([
                "preflight", "--workspace", str(workspace.root),
            ], release_module=fake)

            self.assertEqual(3, code)
            self.assertFalse(result["release_ready"])
            self.assertEqual(1, len(fake.preflight_calls))
            self.assertEqual(before_live, tree_digest(live))
            self.assertEqual(before_cdn, tree_digest(cdn))

    def test_publish_requires_exact_confirmation_before_release_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = workspace_module.init_workspace(
                Path(tmp), 111165, 129999, "seris_dragon_king", "seris",
            )
            fake = FakeReleaseModule()

            code, result = flow.run_command([
                "publish", "--workspace", str(workspace.root), "--confirm", "yes",
            ], release_module=fake)

            self.assertEqual(2, code)
            self.assertIn("PUBLISH_CHARACTER_PACKAGE", " ".join(result["errors"]))
            self.assertEqual([], fake.publish_calls)

    def test_runtime_test_preserves_direct_real_test_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = workspace_module.init_workspace(
                Path(tmp), 111165, 129999, "seris_dragon_king", "seris",
            )
            manifest_path = workspace.package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["qa"] = {
                "delivery_mode": "runtime_test",
                "release_ready": False,
                "user_authorized_direct_real_test": True,
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            fake = FakeReleaseModule()

            code, result = flow.run_command([
                "publish", "--workspace", str(workspace.root),
                "--confirm", "DIRECT_REAL_TEST",
            ], release_module=fake)

            self.assertEqual(0, code)
            self.assertEqual("runtime_test", result["delivery_mode"])
            self.assertEqual("DIRECT_REAL_TEST", fake.publish_calls[0][2])

    def test_production_ready_status_delegates_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = workspace_module.init_workspace(
                Path(tmp), 111165, 129999, "seris_dragon_king", "seris",
            )
            fake = FakeReleaseModule()
            ready = SimpleNamespace(
                release_ready=True,
                to_dict=lambda: {"release_ready": True, "manifest_errors": []},
            )
            with patch.object(flow.workspace_module, "workspace_status", return_value=ready):
                code, result = flow.run_command([
                    "publish", "--workspace", str(workspace.root),
                    "--confirm", "PUBLISH_CHARACTER_PACKAGE",
                ], release_module=fake)

            self.assertEqual(0, code)
            self.assertTrue(result["ok"])
            self.assertEqual("production", result["delivery_mode"])
            self.assertEqual("PUBLISH_CHARACTER_PACKAGE", fake.publish_calls[0][2])


class TestDevCatalogHook(unittest.TestCase):
    """发布后重产 dev 启动前编译输入:只对真实链根发射,失败只告警。"""

    def _publish(self, tmp: str, release_module, **kwargs):
        workspace = workspace_module.init_workspace(
            Path(tmp), 111165, 129999, "seris_dragon_king", "seris",
        )
        ready = SimpleNamespace(
            release_ready=True,
            to_dict=lambda: {"release_ready": True, "manifest_errors": []},
        )
        with patch.object(flow.workspace_module, "workspace_status", return_value=ready):
            return flow.run_command([
                "publish", "--workspace", str(workspace.root),
                "--confirm", "PUBLISH_CHARACTER_PACKAGE",
            ], release_module=release_module, **kwargs)

    def test_publish_emits_dev_catalog_when_archives_land_in_chain_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdn = Path(tmp) / "cdn"
            (cdn / "archive-common-diff").mkdir(parents=True)
            manifest = cdn / "dev-catalog" / "catalog-cn-1.4.140.json"
            with patch.object(dev_catalog, "CDN_ROOT", cdn), patch.object(
                dev_catalog, "emit_dev_catalog", return_value=(manifest, [], {})
            ) as emit:
                code, result = self._publish(tmp, CdnReleaseModule(cdn))

            self.assertEqual(0, code)
            self.assertEqual(str(manifest), result["dev_catalog"])
            emit.assert_called_once()
            self.assertEqual(cdn, emit.call_args.args[0])
            self.assertEqual("cache", emit.call_args.kwargs["digest_mode"])
            self.assertTrue(emit.call_args.kwargs["allow_issues"])

    def test_publish_skips_dev_catalog_when_archives_are_outside_chain_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdn = Path(tmp) / "cdn"
            (cdn / "archive-common-diff").mkdir(parents=True)
            with patch.object(dev_catalog, "CDN_ROOT", cdn), patch.object(
                dev_catalog, "emit_dev_catalog"
            ) as emit:
                code, result = self._publish(tmp, FakeReleaseModule())

            self.assertEqual(0, code)
            self.assertTrue(result["ok"])
            self.assertIsNone(result["dev_catalog"])
            emit.assert_not_called()

    def test_publish_return_code_survives_dev_catalog_failure(self):
        def exploding_hook(_result):
            raise RuntimeError("fixture emit failure")

        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(stderr):
            code, result = self._publish(
                tmp, FakeReleaseModule(), dev_catalog_hook=exploding_hook,
            )

        self.assertEqual(0, code)
        self.assertTrue(result["ok"])
        self.assertEqual([], result["errors"])
        self.assertIsNone(result["dev_catalog"])
        self.assertIn("[WARN]", stderr.getvalue())
        self.assertIn("fixture emit failure", stderr.getvalue())


class TestReleaseQaContract(unittest.TestCase):
    def test_public_rebase_api_delegates_without_live_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            roots = SimpleNamespace(
                common=base / "common",
                medium=base / "medium",
                android=base / "android",
                server=base / "server",
            )
            expected = SimpleNamespace(output_dir=base / "out")
            with patch.object(
                wf_release,
                "_resolve_repo_paths",
                return_value=wf_release._RepoPaths(
                    tool_root=base,
                    server_root=base,
                    live_roots=roots,
                    cdn_root=base / "cdn",
                ),
            ), patch.object(
                wf_release, "_current_git_head", return_value="a" * 40
            ), patch.object(
                wf_release, "rebase_runtime_package", return_value=expected
            ) as delegated:
                result = wf_release.rebase_package(
                    base / "package", "cn", output_dir=base / "out"
                )

            self.assertIs(expected, result)
            delegated.assert_called_once_with(
                base / "package",
                base / "out",
                live_roots=roots,
                generator_git_head="a" * 40,
            )

    def test_checked_in_schema_documents_both_release_gates(self):
        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "character-pack-v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        qa = schema["properties"]["qa"]
        self.assertEqual({"delivery_mode", "release_ready"}, set(qa["required"]))
        self.assertEqual({"production", "runtime_test"}, set(
            qa["properties"]["delivery_mode"]["enum"]
        ))
        conditions = schema["allOf"]
        production = conditions[0]["then"]["properties"]["qa"]
        runtime_test = conditions[1]["then"]["properties"]["qa"]
        self.assertEqual(37, production["properties"]["required_assets_total"]["const"])
        self.assertEqual(37, production["properties"]["required_assets_present"]["const"])
        self.assertTrue(production["properties"]["release_ready"]["const"])
        self.assertFalse(runtime_test["properties"]["release_ready"]["const"])
        self.assertTrue(
            runtime_test["properties"]["user_authorized_direct_real_test"]["const"]
        )

    def test_production_contract_requires_37_assets_and_workspace_digest(self):
        manifest = {
            "qa": {
                "delivery_mode": "production",
                "release_ready": True,
                "required_assets_total": 37,
                "required_assets_present": 37,
                "workspace_input_sha256": "a" * 64,
            }
        }
        wf_release._validate_qa_contract(manifest, confirmation="PUBLISH_CHARACTER_PACKAGE")

        manifest["qa"]["required_assets_present"] = 36
        with self.assertRaisesRegex(wf_release.ReleaseError, "37/37"):
            wf_release._validate_qa_contract(manifest, confirmation="PUBLISH_CHARACTER_PACKAGE")

    def test_runtime_contract_keeps_legacy_authorization_and_confirmation(self):
        manifest = {"qa": {
            "delivery_mode": "runtime_test",
            "release_ready": False,
            "user_authorized_direct_real_test": True,
        }}
        wf_release._validate_qa_contract(manifest, confirmation="DIRECT_REAL_TEST")
        with self.assertRaisesRegex(wf_release.ReleaseError, "DIRECT_REAL_TEST"):
            wf_release._validate_qa_contract(manifest, confirmation="PUBLISH_CHARACTER_PACKAGE")


if __name__ == "__main__":
    unittest.main()

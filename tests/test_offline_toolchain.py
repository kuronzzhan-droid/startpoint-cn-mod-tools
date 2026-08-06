from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


MOD_TOOLS = Path(__file__).resolve().parents[1]
MODULE_PATH = MOD_TOOLS / "wf_offline_toolchain.py"
SPEC = importlib.util.spec_from_file_location("wf_offline_toolchain", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise AssertionError("offline toolchain module is missing")
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class RecordingRunner:
    def __init__(self, responses: dict[str, SimpleNamespace] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[SimpleNamespace] = []

    def __call__(self, argv, **kwargs):
        call = SimpleNamespace(argv=[str(value) for value in argv], kwargs=dict(kwargs))
        self.calls.append(call)
        name = (
            Path(call.argv[call.argv.index("-jar") + 1]).name.lower()
            if "-jar" in call.argv
            else Path(call.argv[0]).name.lower()
        )
        response = self.responses.get(name)
        if response is not None:
            return response
        return SimpleNamespace(returncode=0, stdout="", stderr="")


class BootstrapRunner(RecordingRunner):
    def __init__(self, certificate: bytes) -> None:
        super().__init__(
            {
                "java.exe": SimpleNamespace(
                    returncode=0, stdout="", stderr='java version "1.8.0_451"\n'
                )
            }
        )
        self.certificate = certificate

    def __call__(self, argv, **kwargs):
        result = super().__call__(argv, **kwargs)
        arguments = [str(value) for value in argv]
        cwd = Path(kwargs.get("cwd", "."))
        if "-genkeypair" in arguments:
            (cwd / arguments[arguments.index("-keystore") + 1]).write_bytes(b"fixture-jks")
        if "-exportcert" in arguments:
            (cwd / arguments[arguments.index("-file") + 1]).write_bytes(self.certificate)
        return result


class OfflineToolchainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def tool(self, relative: str) -> Path:
        path = self.path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
        return path

    def required_explicit(self) -> dict[str, Path]:
        return {
            "java": self.tool("explicit/java.exe"),
            "ffdec": self.tool("explicit/ffdec.jar"),
            "aapt": self.tool("explicit/aapt.exe"),
            "zipalign": self.tool("explicit/zipalign.exe"),
            "apksigner": self.tool("explicit/apksigner.bat"),
        }

    def signing_config(
        self, keystore: Path, fingerprint: str = "ab" * 32
    ) -> module.SigningConfig:
        kwargs = {
            "keystore": keystore,
            "expected_certificate_sha256": fingerprint,
        }
        parameters = inspect.signature(module.SigningConfig).parameters
        if "alias" in parameters:
            kwargs["alias"] = "wf-offline-release"
            kwargs["password_env"] = "WF_OFFLINE_KEYSTORE_PASSWORD"
        return module.SigningConfig(**kwargs)

    def bootstrap_signer(self, *args, **kwargs) -> module.SigningConfig:
        with mock.patch.object(module, "_console_streams_are_tty", return_value=True):
            return module.init_signer_interactive(*args, **kwargs)

    def version_runner(self) -> RecordingRunner:
        return RecordingRunner(
            {
                "java.exe": SimpleNamespace(
                    returncode=0, stdout="", stderr='java version "1.8.0_451"\n'
                ),
                "ffdec.jar": SimpleNamespace(
                    returncode=0,
                    stdout="JPEXS Free Flash Decompiler v.26.2.1\n",
                    stderr="",
                ),
                "aapt.exe": SimpleNamespace(
                    returncode=0, stdout="Android Asset Packaging Tool, v0.2-35.0.0\n", stderr=""
                ),
                "zipalign.exe": SimpleNamespace(
                    returncode=0, stdout="Zip alignment utility 35.0.0\n", stderr=""
                ),
                "apksigner.bat": SimpleNamespace(
                    returncode=0, stdout="0.9\n", stderr=""
                ),
            }
        )

    def test_discovery_prefers_explicit_then_env_then_path(self) -> None:
        explicit = self.required_explicit()
        env_java = self.tool("env/java.exe")
        path_java = self.tool("path/java.exe")
        env = {"WF_OFFLINE_JAVA": str(env_java)}
        path_tools = {"java.exe": str(path_java), "java": str(path_java)}

        found = module.discover_toolchain(
            explicit=explicit,
            env=env,
            which=lambda name: path_tools.get(name.lower()),
            runner=self.version_runner(),
        )

        self.assertEqual(explicit["java"].resolve(), found.java)

    def test_android_sdk_and_java_home_precede_path_and_capture_versions(self) -> None:
        sdk = self.path / "sdk"
        build_tools = sdk / "build-tools" / "35.0.0"
        sdk_tools = {
            "aapt": self.tool(str(build_tools.relative_to(self.path) / "aapt.exe")),
            "zipalign": self.tool(str(build_tools.relative_to(self.path) / "zipalign.exe")),
            "apksigner": self.tool(str(build_tools.relative_to(self.path) / "apksigner.bat")),
        }
        java_home = self.path / "jdk8"
        java = self.tool(str(java_home.relative_to(self.path) / "bin" / "java.exe"))
        ffdec = self.tool("env/ffdec.jar")
        path_aapt = self.tool("path/aapt.exe")
        env = {
            "JAVA_HOME": str(java_home),
            "ANDROID_SDK_ROOT": str(sdk),
            "WF_OFFLINE_FFDEC": str(ffdec),
        }
        runner = self.version_runner()

        found = module.discover_toolchain(
            env=env,
            which=lambda name: str(path_aapt) if name.lower() in {"aapt", "aapt.exe"} else None,
            runner=runner,
        )

        self.assertEqual(java.resolve(), found.java)
        self.assertEqual(sdk_tools["aapt"].resolve(), found.aapt)
        self.assertEqual(sdk_tools["zipalign"].resolve(), found.zipalign)
        self.assertEqual(sdk_tools["apksigner"].resolve(), found.apksigner)
        self.assertEqual("1.8.0_451", found.versions["java"])
        self.assertEqual("26.2.1", found.versions["ffdec"])
        self.assertEqual("35.0.0", found.versions["aapt"])

    def test_path_ffdec_precedes_repo_fallback(self) -> None:
        explicit = self.required_explicit()
        explicit.pop("ffdec")
        path_ffdec = self.tool("path/ffdec.jar")
        self.tool("repo/ffdec_26.2.1/ffdec.jar")

        found = module.discover_toolchain(
            explicit=explicit,
            env={},
            which=lambda name: str(path_ffdec) if name.lower() in {"ffdec", "ffdec.jar"} else None,
            runner=self.version_runner(),
        )

        self.assertEqual(path_ffdec.resolve(), found.ffdec)

    def test_ffdec_version_is_read_from_jar_without_launching_the_gui(self) -> None:
        explicit = self.required_explicit()
        ffdec = explicit["ffdec"]
        ffdec.unlink()
        with zipfile.ZipFile(ffdec, "w") as archive:
            archive.writestr(
                "project.properties",
                "version=26.2.1\r\nversion.major=26\r\nversion.minor=2\r\n",
            )

        class NoFfdecLaunchRunner(RecordingRunner):
            def __call__(self, argv, **kwargs):
                arguments = [str(value) for value in argv]
                if "-jar" in arguments:
                    raise AssertionError("FFDec GUI/CLI must not be launched for version discovery")
                return super().__call__(argv, **kwargs)

        found = module.discover_toolchain(
            explicit=explicit,
            env={},
            which=lambda _name: None,
            runner=NoFfdecLaunchRunner(self.version_runner().responses),
        )

        self.assertEqual("26.2.1", found.versions["ffdec"])

    def test_android_build_tools_version_is_read_from_source_properties(self) -> None:
        explicit = self.required_explicit()
        android_dir = self.path / "android-build-tools"
        for name, filename in (
            ("aapt", "aapt.exe"),
            ("zipalign", "zipalign.exe"),
            ("apksigner", "apksigner.bat"),
        ):
            explicit[name] = self.tool(str(android_dir.relative_to(self.path) / filename))
        (android_dir / "source.properties").write_text(
            "Pkg.UserSrc=false\r\nPkg.Revision=34.0.0\r\n",
            encoding="utf-8",
        )

        class NoAndroidLaunchRunner(RecordingRunner):
            def __call__(self, argv, **kwargs):
                name = Path(str(argv[0])).name.lower()
                if name in {"aapt.exe", "zipalign.exe", "apksigner.bat"}:
                    raise AssertionError("Android tool must not run just to read package version")
                return super().__call__(argv, **kwargs)

        found = module.discover_toolchain(
            explicit=explicit,
            env={},
            which=lambda _name: None,
            runner=NoAndroidLaunchRunner(self.version_runner().responses),
        )

        for name in ("aapt", "zipalign", "apksigner"):
            self.assertEqual("34.0.0", found.versions[name])

    def test_unversioned_optional_mumu_manager_is_reported_without_launching_gui(self) -> None:
        explicit = self.required_explicit()
        manager = self.tool("mumu/nx_main/MuMuManager.exe")
        explicit["mumu_manager"] = manager

        class NoManagerLaunchRunner(RecordingRunner):
            def __call__(self, argv, **kwargs):
                if Path(str(argv[0])).name.lower() == "mumumanager.exe":
                    raise AssertionError("MuMuManager GUI must not be launched for discovery")
                return super().__call__(argv, **kwargs)

        found = module.discover_toolchain(
            explicit=explicit,
            env={},
            which=lambda _name: None,
            runner=NoManagerLaunchRunner(self.version_runner().responses),
        )

        self.assertEqual(manager.resolve(), found.mumu_manager)
        self.assertEqual("unavailable", found.versions["mumu_manager"])

    def test_repo_ffdec_fallback_rejects_ambiguity(self) -> None:
        explicit = self.required_explicit()
        explicit.pop("ffdec")
        repo = self.path / "repo"
        self.tool("repo/ffdec_26.2.1/ffdec.jar")
        self.tool("repo/vendor/ffdec.jar")

        with self.assertRaisesRegex(module.ToolchainError, "ambiguous ffdec"):
            module._repo_ffdec(repo)

    def test_repo_ffdec_ignores_internal_cli_and_library_jars(self) -> None:
        explicit = self.required_explicit()
        explicit.pop("ffdec")
        main = self.tool("repo/ffdec_26.2.1/ffdec.jar")
        self.tool("repo/ffdec_26.2.1/lib/ffdec-cli.jar")
        self.tool("repo/ffdec_26.2.1/lib/ffdec_lib.jar")

        self.assertEqual(main.resolve(), module._repo_ffdec(self.path / "repo"))

    def test_missing_required_tool_fails_closed(self) -> None:
        explicit = self.required_explicit()
        explicit.pop("apksigner")
        with self.assertRaisesRegex(module.ToolchainError, "missing required tool: apksigner"):
            module.discover_toolchain(
                explicit=explicit,
                env={},
                which=lambda _name: None,
                runner=self.version_runner(),
            )

    def test_discovery_reports_all_missing_android_build_tools(self) -> None:
        explicit = self.required_explicit()
        for name in ("aapt", "zipalign", "apksigner"):
            explicit.pop(name)
        with self.assertRaises(module.ToolchainError) as raised:
            module.discover_toolchain(
                explicit=explicit,
                env={},
                which=lambda _name: None,
                runner=self.version_runner(),
            )

        message = str(raised.exception)
        for name in ("aapt", "zipalign", "apksigner"):
            self.assertIn(name, message)

    def test_invalid_direct_environment_override_does_not_fall_back_to_path(self) -> None:
        explicit = self.required_explicit()
        for name in ("aapt", "zipalign", "apksigner"):
            explicit.pop(name)
        path_aapt = self.tool("path/aapt.exe")
        env_dir = self.path / "env-build-tools"
        env = {
            "WF_OFFLINE_AAPT": str(self.path / "missing-aapt.exe"),
            "WF_OFFLINE_ZIPALIGN": str(self.tool("env-build-tools/zipalign.exe")),
            "WF_OFFLINE_APKSIGNER": str(self.tool("env-build-tools/apksigner.bat")),
        }
        with self.assertRaisesRegex(module.ToolchainError, "WF_OFFLINE_AAPT"):
            module.discover_toolchain(
                explicit=explicit,
                env=env,
                which=lambda name: str(path_aapt) if name.lower() in {"aapt", "aapt.exe"} else None,
                runner=self.version_runner(),
            )

    def test_public_discovery_has_no_repo_root_override(self) -> None:
        self.assertNotIn("repo_root", inspect.signature(module.discover_toolchain).parameters)

    def test_discovery_requires_java8_and_exact_ffdec_version(self) -> None:
        explicit = self.required_explicit()
        java17 = self.version_runner()
        java17.responses["java.exe"] = SimpleNamespace(
            returncode=0, stdout="", stderr='java version "17.0.12"\n'
        )
        with self.assertRaisesRegex(module.ToolchainError, "Java 8"):
            module.discover_toolchain(
                explicit=explicit, env={}, which=lambda _name: None, runner=java17
            )

        old_ffdec = self.version_runner()
        old_ffdec.responses["ffdec.jar"] = SimpleNamespace(
            returncode=0,
            stdout="JPEXS Free Flash Decompiler v.26.2.0\n",
            stderr="",
        )
        with self.assertRaisesRegex(module.ToolchainError, "FFDec 26.2.1"):
            module.discover_toolchain(
                explicit=explicit, env={}, which=lambda _name: None, runner=old_ffdec
            )

    def test_version_probes_are_bounded_and_have_no_stdin(self) -> None:
        runner = self.version_runner()
        module.discover_toolchain(
            explicit=self.required_explicit(),
            env={},
            which=lambda _name: None,
            runner=runner,
        )

        java_call = next(call for call in runner.calls if Path(call.argv[0]).name.lower() == "java.exe")
        self.assertEqual(subprocess.DEVNULL, java_call.kwargs["stdin"])
        self.assertGreater(java_call.kwargs["timeout"], 0)

    def test_invalid_java_home_does_not_fall_back_to_path(self) -> None:
        explicit = self.required_explicit()
        explicit.pop("java")
        path_java = self.tool("path/java.exe")
        with self.assertRaisesRegex(module.ToolchainError, "JAVA_HOME"):
            module.discover_toolchain(
                explicit=explicit,
                env={"JAVA_HOME": str(self.path / "missing-jdk")},
                which=lambda name: str(path_java) if name.lower() in {"java", "java.exe"} else None,
                runner=self.version_runner(),
            )

    def test_distinct_path_aliases_for_java_fail_closed(self) -> None:
        explicit = self.required_explicit()
        explicit.pop("java")
        java_aliases = {
            "java.exe": str(self.tool("path-a/java.exe")),
            "java": str(self.tool("path-b/java.exe")),
        }
        with self.assertRaisesRegex(module.ToolchainError, "ambiguous.*java.*PATH"):
            module.discover_toolchain(
                explicit=explicit,
                env={},
                which=lambda name: java_aliases.get(name.lower()),
                runner=self.version_runner(),
            )

    def test_distinct_path_aliases_for_ffdec_fail_closed(self) -> None:
        explicit = self.required_explicit()
        explicit.pop("ffdec")
        ffdec_aliases = {
            "ffdec": str(self.tool("path-a/ffdec")),
            "ffdec.jar": str(self.tool("path-b/ffdec.jar")),
        }
        runner = self.version_runner()
        runner.responses["ffdec"] = SimpleNamespace(
            returncode=0,
            stdout="JPEXS Free Flash Decompiler v.26.2.1\n",
            stderr="",
        )
        with self.assertRaisesRegex(module.ToolchainError, "ambiguous.*ffdec.*PATH"):
            module.discover_toolchain(
                explicit=explicit,
                env={},
                which=lambda name: ffdec_aliases.get(name.lower()),
                runner=runner,
            )

    def test_android_build_tools_must_be_a_complete_single_directory(self) -> None:
        explicit = self.required_explicit()
        explicit["zipalign"] = self.tool("other-build-tools/zipalign.exe")
        with self.assertRaisesRegex(module.ToolchainError, "same build-tools directory"):
            module.discover_toolchain(
                explicit=explicit,
                env={},
                which=lambda _name: None,
                runner=self.version_runner(),
            )

        partial = self.required_explicit()
        partial.pop("apksigner")
        with self.assertRaisesRegex(module.ToolchainError, "all three"):
            module.discover_toolchain(
                explicit=partial,
                env={},
                which=lambda _name: None,
                runner=self.version_runner(),
            )

        no_android = self.required_explicit()
        for name in ("aapt", "zipalign", "apksigner"):
            no_android.pop(name)
        with self.assertRaisesRegex(module.ToolchainError, "all three"):
            module.discover_toolchain(
                explicit=no_android,
                env={"WF_OFFLINE_AAPT": str(self.tool("env-only/aapt.exe"))},
                which=lambda _name: None,
                runner=self.version_runner(),
            )

    def test_android_roles_cannot_share_one_file_even_with_package_metadata(self) -> None:
        explicit = self.required_explicit()
        shared = self.tool("shared-build-tools/aapt.exe")
        for name in ("aapt", "zipalign", "apksigner"):
            explicit[name] = shared
        (shared.parent / "source.properties").write_text(
            "Pkg.Revision=34.0.0\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(module.ToolchainError, "Android build-tools"):
            module.discover_toolchain(
                explicit=explicit,
                env={},
                which=lambda _name: None,
                runner=self.version_runner(),
            )

    def test_android_role_basenames_cannot_be_swapped(self) -> None:
        explicit = self.required_explicit()
        directory = self.path / "swapped-build-tools"
        explicit["aapt"] = self.tool("swapped-build-tools/zipalign.exe")
        explicit["zipalign"] = self.tool("swapped-build-tools/aapt.exe")
        explicit["apksigner"] = self.tool("swapped-build-tools/apksigner.bat")
        (directory / "source.properties").write_text(
            "Pkg.Revision=34.0.0\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(module.ToolchainError, "aapt.*basename"):
            module.discover_toolchain(
                explicit=explicit,
                env={},
                which=lambda _name: None,
                runner=self.version_runner(),
            )

    def test_android_role_files_must_have_distinct_hardlink_identities(self) -> None:
        explicit = self.required_explicit()
        directory = self.path / "hardlinked-build-tools"
        aapt = self.tool("hardlinked-build-tools/aapt.exe")
        zipalign = directory / "zipalign.exe"
        apksigner = directory / "apksigner.bat"
        try:
            os.link(aapt, zipalign)
            os.link(aapt, apksigner)
        except OSError as exc:
            self.skipTest(f"hard links unavailable: {exc.__class__.__name__}")
        explicit.update(
            {"aapt": aapt, "zipalign": zipalign, "apksigner": apksigner}
        )
        (directory / "source.properties").write_text(
            "Pkg.Revision=34.0.0\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(module.ToolchainError, "distinct.*identity"):
            module.discover_toolchain(
                explicit=explicit,
                env={},
                which=lambda _name: None,
                runner=self.version_runner(),
            )

    def test_sdk_selects_one_highest_complete_build_tools_version(self) -> None:
        explicit = self.required_explicit()
        for name in ("aapt", "zipalign", "apksigner"):
            explicit.pop(name)
        sdk = self.path / "sdk"
        self.tool("sdk/build-tools/35.0.0/aapt.exe")
        self.tool("sdk/build-tools/34.0.0/zipalign.exe")
        self.tool("sdk/build-tools/34.0.0/apksigner.bat")
        complete = sdk / "build-tools" / "33.0.2"
        expected = {
            "aapt": self.tool("sdk/build-tools/33.0.2/aapt.exe"),
            "zipalign": self.tool("sdk/build-tools/33.0.2/zipalign.exe"),
            "apksigner": self.tool("sdk/build-tools/33.0.2/apksigner.bat"),
        }
        (complete / "source.properties").write_text(
            "Pkg.Revision=33.0.2\n", encoding="utf-8"
        )

        found = module.discover_toolchain(
            explicit=explicit,
            env={"ANDROID_SDK_ROOT": str(sdk)},
            which=lambda _name: None,
            runner=self.version_runner(),
        )

        for name, path in expected.items():
            self.assertEqual(path.resolve(), getattr(found, name))

    def test_sdk_conflict_invalid_root_and_incomplete_versions_fail_closed(self) -> None:
        explicit = self.required_explicit()
        for name in ("aapt", "zipalign", "apksigner"):
            explicit.pop(name)
        first = self.path / "sdk-a"
        second = self.path / "sdk-b"
        first.mkdir()
        second.mkdir()
        with self.assertRaisesRegex(module.ToolchainError, "ANDROID_SDK_ROOT.*ANDROID_HOME"):
            module.discover_toolchain(
                explicit=explicit,
                env={"ANDROID_SDK_ROOT": str(first), "ANDROID_HOME": str(second)},
                which=lambda _name: None,
                runner=self.version_runner(),
            )

        path_dir = self.path / "path-build-tools"
        path_tools = {
            "aapt.exe": self.tool("path-build-tools/aapt.exe"),
            "zipalign.exe": self.tool("path-build-tools/zipalign.exe"),
            "apksigner.bat": self.tool("path-build-tools/apksigner.bat"),
        }
        with self.assertRaisesRegex(module.ToolchainError, "ANDROID_SDK_ROOT"):
            module.discover_toolchain(
                explicit=explicit,
                env={"ANDROID_SDK_ROOT": str(self.path / "missing-sdk")},
                which=lambda name: str(path_tools[name.lower()]) if name.lower() in path_tools else None,
                runner=self.version_runner(),
            )

        incomplete = self.path / "incomplete-sdk"
        self.tool("incomplete-sdk/build-tools/35.0.0/aapt.exe")
        self.tool("incomplete-sdk/build-tools/34.0.0/zipalign.exe")
        self.tool("incomplete-sdk/build-tools/34.0.0/apksigner.bat")
        with self.assertRaisesRegex(module.ToolchainError, "complete Android build-tools"):
            module.discover_toolchain(
                explicit=explicit,
                env={"ANDROID_HOME": str(incomplete)},
                which=lambda _name: None,
                runner=self.version_runner(),
            )

    def test_discovery_report_contains_no_absolute_paths(self) -> None:
        found = module.discover_toolchain(
            explicit=self.required_explicit(),
            env={},
            which=lambda _name: None,
            runner=self.version_runner(),
        )

        report = module.toolchain_report(found)
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(str(self.path), serialized)
        self.assertEqual("java.exe", report["java"]["name"])
        self.assertEqual("1.8.0_451", report["java"]["version"])

    def test_signing_config_requires_keystore_public_fingerprint_and_password_env(self) -> None:
        home = self.path / ".wf-offline-release"
        with self.assertRaisesRegex(module.ToolchainError, "missing stable keystore"):
            module.load_signing_config(home, env={})
        home.mkdir()
        (home / "wf-offline-release.jks").write_bytes(b"fixture")
        with self.assertRaisesRegex(module.ToolchainError, "missing signer public config"):
            module.load_signing_config(home, env={})
        (home / "signer-public.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "alias": "wf-offline-release",
                    "certificate_sha256": "AB:" * 31 + "AB",
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(module.ToolchainError, "WF_OFFLINE_KEYSTORE_PASSWORD"):
            module.load_signing_config(home, env={})

        config = module.load_signing_config(home, env={"WF_OFFLINE_KEYSTORE_PASSWORD": "secret"})
        self.assertEqual("ab" * 32, config.expected_certificate_sha256)
        self.assertEqual("WF_OFFLINE_KEYSTORE_PASSWORD", config.password_env)
        self.assertFalse(hasattr(config, "password"))

    def test_signing_config_rejects_public_identity_drift(self) -> None:
        home = self.path / "release-home"
        home.mkdir()
        (home / "wf-offline-release.jks").write_bytes(b"fixture")
        for alias, fingerprint, message in (
            ("some-other-key", "ab" * 32, "alias drift"),
            ("wf-offline-release", "not-a-fingerprint", "certificate fingerprint"),
        ):
            with self.subTest(alias=alias, fingerprint=fingerprint):
                (home / "signer-public.json").write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "alias": alias,
                            "certificate_sha256": fingerprint,
                        }
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(module.ToolchainError, message):
                    module.load_signing_config(
                        home, env={"WF_OFFLINE_KEYSTORE_PASSWORD": "secret"}
                    )

    def test_signing_config_identity_fields_cannot_be_overridden(self) -> None:
        keystore = self.path / "release" / "wf-offline-release.jks"
        with self.assertRaises(TypeError):
            module.SigningConfig(
                keystore=keystore,
                alias="attacker-controlled",
                password_env="ATTACKER_PASSWORD",
                expected_certificate_sha256="ab" * 32,
            )

        config = self.signing_config(keystore)
        self.assertEqual("wf-offline-release", config.alias)
        self.assertEqual("WF_OFFLINE_KEYSTORE_PASSWORD", config.password_env)

    def test_signer_public_json_rejects_duplicate_bool_and_unknown_fields(self) -> None:
        home = self.path / "strict-public"
        home.mkdir()
        (home / "wf-offline-release.jks").write_bytes(b"fixture")
        public_path = home / "signer-public.json"
        fixtures = (
            (
                '{"schema_version":1,"schema_version":1,"alias":"wf-offline-release",'
                '"certificate_sha256":"' + "ab" * 32 + '"}',
                "duplicate",
            ),
            (
                json.dumps(
                    {
                        "schema_version": True,
                        "alias": "wf-offline-release",
                        "certificate_sha256": "ab" * 32,
                    }
                ),
                "schema",
            ),
            (
                json.dumps(
                    {
                        "schema_version": 1,
                        "alias": "wf-offline-release",
                        "certificate_sha256": "ab" * 32,
                        "keystore": "must-not-be-here",
                    }
                ),
                "unknown",
            ),
        )
        for raw, message in fixtures:
            with self.subTest(message=message):
                public_path.write_text(raw, encoding="utf-8")
                with self.assertRaisesRegex(module.ToolchainError, message):
                    module.load_signing_config(
                        home, env={"WF_OFFLINE_KEYSTORE_PASSWORD": "secret"}
                    )

    def test_parse_apksigner_verify_reads_v1_v2_v3_and_fingerprint(self) -> None:
        output = """Verifies
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Signer #1 certificate SHA-256 digest: AB:CD:{tail}
""".format(tail=":".join(["EF"] * 30))
        expected = "abcd" + "ef" * 30

        report = module.parse_apksigner_verify(
            output, expected_certificate_sha256=expected
        )

        self.assertTrue(report["verified"])
        self.assertEqual({"v1": True, "v2": True, "v3": True}, report["signature_schemes"])
        self.assertEqual(expected, report["certificate_sha256"])

    def test_parse_apksigner_verify_rejects_scheme_or_fingerprint_drift(self) -> None:
        output = """Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): false
Verified using v3 scheme (APK Signature Scheme v3): true
Signer #1 certificate SHA-256 digest: {fingerprint}
""".format(fingerprint="ab" * 32)
        with self.assertRaisesRegex(module.ToolchainError, "v2"):
            module.parse_apksigner_verify(output)

        good = output.replace("v2 scheme (APK Signature Scheme v2): false", "v2 scheme (APK Signature Scheme v2): true")
        with self.assertRaisesRegex(module.ToolchainError, "fingerprint drift"):
            module.parse_apksigner_verify(
                good, expected_certificate_sha256="cd" * 32
            )

    def test_parse_apksigner_verify_rejects_duplicate_scheme_and_multiple_signers(self) -> None:
        base = """Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Signer #1 certificate SHA-256 digest: {first}
""".format(first="ab" * 32)
        duplicate = base.replace(
            "Verified using v2 scheme (APK Signature Scheme v2): true",
            "Verified using v2 scheme (APK Signature Scheme v2): true\n"
            "Verified using v2 scheme (APK Signature Scheme v2): true",
        )
        with self.assertRaisesRegex(module.ToolchainError, "duplicate.*v2"):
            module.parse_apksigner_verify(duplicate)

        multiple = base + "Signer #2 certificate SHA-256 digest: " + "ab" * 32 + "\n"
        with self.assertRaisesRegex(module.ToolchainError, "multiple apksigner signers"):
            module.parse_apksigner_verify(multiple)

        signer_two_only = base.replace("Signer #1", "Signer #2")
        with self.assertRaisesRegex(module.ToolchainError, "Signer #1"):
            module.parse_apksigner_verify(signer_two_only)

    def test_password_is_redacted_from_utf8_utf16_commands_and_errors(self) -> None:
        secret = "p@ss-fixture-密码-123"
        failure = subprocess.CalledProcessError(
            1,
            ["apksigner", "sign", "--ks-pass", secret],
            output=("stdout " + secret).encode("utf-16-le"),
            stderr=("stderr " + secret).encode("utf-8"),
        )

        message = module.redact_process_error(failure, secrets=(secret,))

        self.assertNotIn(secret, message)
        self.assertNotIn(secret.encode("utf-8").hex(), message.lower())
        self.assertGreaterEqual(message.count("[REDACTED]"), 1)

    def test_password_redaction_selects_matching_byte_encoding_and_escaped_repr(self) -> None:
        secret = "密码密钥"
        for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
            with self.subTest(encoding=encoding):
                failure = subprocess.CalledProcessError(
                    9,
                    ["tool.exe"],
                    stderr=("错误：" + secret).encode(encoding),
                )
                message = module.redact_process_error(failure, secrets=(secret,))
                self.assertNotIn(secret, message)
                self.assertIn("[REDACTED]", message)

        escaped = repr(("错误：" + secret).encode("utf-16-le"))
        escaped_message = module.redact_process_error(escaped, secrets=(secret,))
        self.assertNotIn(repr(secret.encode("utf-16-le"))[2:-1], escaped_message)
        self.assertIn("[REDACTED]", escaped_message)

    def test_password_redaction_covers_reversible_unicode_escape_forms(self) -> None:
        secret = "密码口令"
        escaped_secret = secret.encode("unicode_escape").decode("ascii")
        uppercase_unicode = re.sub(
            r"(?<=\\u)[0-9a-f]{4}",
            lambda match: match.group(0).upper(),
            escaped_secret,
        )
        uppercase_utf8_bytes = "".join(
            f"\\x{byte:02X}" for byte in secret.encode("utf-8")
        )
        fixtures = (
            ascii(secret),
            escaped_secret,
            json.dumps({"error": secret}, ensure_ascii=True),
            uppercase_unicode,
            uppercase_utf8_bytes,
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                message = module.redact_process_error(fixture, secrets=(secret,))
                self.assertNotIn(secret, message)
                self.assertNotIn(escaped_secret, message)
                self.assertIn("[REDACTED]", message)
        for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
            with self.subTest(escaped_encoding=encoding):
                message = module.redact_process_error(
                    escaped_secret.encode(encoding), secrets=(secret,)
                )
                self.assertNotIn(escaped_secret, message)
                self.assertIn("[REDACTED]", message)

    def test_process_errors_hide_full_command_and_all_absolute_artifact_paths(self) -> None:
        secret = "fixture-secret"
        java = self.path / "Program Files" / "Java" / "java.exe"
        jar = self.path / "build-tools" / "lib" / "apksigner.jar"
        source = self.path / "private input.apk"
        output = self.path / "private output.apk"
        command = [str(java), "-jar", str(jar), "sign", str(source), str(output)]
        echoed = f"failed command {' '.join(command)} password={secret}"
        failure = subprocess.CalledProcessError(
            7,
            command,
            output=echoed.encode("utf-8"),
            stderr=echoed,
        )

        message = module.redact_process_error(failure, secrets=(secret,))

        self.assertIn("java.exe", message)
        self.assertIn("code 7", message)
        for forbidden in (
            secret,
            str(self.path),
            "apksigner.jar",
            "private input.apk",
            "private output.apk",
            "command:",
        ):
            self.assertNotIn(forbidden, message)

    def test_apksigner_command_and_failure_never_contain_password(self) -> None:
        secret = "p@ss-fixture-123"
        keystore = self.tool("release/wf-offline-release.jks")
        config = self.signing_config(keystore)
        apksigner = self.tool("android/apksigner.bat")
        apksigner_jar = self.tool("android/lib/apksigner.jar")
        java = self.tool("jdk/bin/java.exe")
        runner = RecordingRunner(
            {
                "apksigner.jar": SimpleNamespace(
                    returncode=2, stdout="", stderr=f"bad password {secret}"
                )
            }
        )

        with self.assertRaises(module.ToolchainError) as raised:
            module.run_apksigner(
                config,
                apksigner=apksigner,
                java=java,
                input_apk=self.tool("input.apk"),
                output_apk=self.path / "output & fixture.apk",
                env={"WF_OFFLINE_KEYSTORE_PASSWORD": secret},
                runner=runner,
            )

        self.assertNotIn(secret, str(raised.exception))
        self.assertTrue(all(secret not in " ".join(call.argv) for call in runner.calls))
        self.assertIn("env:WF_OFFLINE_KEYSTORE_PASSWORD", runner.calls[0].argv)
        self.assertEqual(str(java), runner.calls[0].argv[0])
        self.assertIn(str(apksigner_jar), runner.calls[0].argv)
        self.assertNotIn(str(apksigner), runner.calls[0].argv)
        self.assertNotIn(str(keystore.resolve()), runner.calls[0].argv)
        timeout = runner.calls[0].kwargs.get("timeout")
        self.assertIsInstance(timeout, (int, float))
        self.assertGreater(timeout, 0)

    def test_apksigner_timeout_is_bounded_and_sanitized(self) -> None:
        secret = "timeout-password"
        keystore = self.tool("timeout-release/wf-offline-release.jks")
        config = self.signing_config(keystore)
        apksigner = self.tool("timeout-android/apksigner.bat")
        self.tool("timeout-android/lib/apksigner.jar")
        java = self.tool("timeout-jdk/bin/java.exe")
        self.tool("timeout-jdk/bin/keytool.exe")
        leaked = f"{secret} {keystore.resolve()} {self.path / 'private.apk'}"

        def sign_timeout(argv, **kwargs):
            raise subprocess.TimeoutExpired(
                argv,
                3,
                output=leaked.encode("utf-8"),
                stderr=leaked,
            )

        with self.assertRaises(module.ToolchainError) as sign_raised:
            module.run_apksigner(
                config,
                apksigner=apksigner,
                java=java,
                input_apk=self.path / "private.apk",
                output_apk=self.path / "private-output.apk",
                env={"WF_OFFLINE_KEYSTORE_PASSWORD": secret},
                runner=sign_timeout,
            )
        self.assertIn("timed out", str(sign_raised.exception))
        self.assertNotIn(secret, str(sign_raised.exception))
        self.assertNotIn(str(self.path), str(sign_raised.exception))

    def test_timeout_redaction_hides_relative_artifact_arguments(self) -> None:
        secret = "relative-timeout-secret"
        command = [
            "java.exe",
            "-jar",
            "apksigner.jar",
            "sign",
            "private-input.apk",
            "private-output.apk",
        ]
        echoed = f"failed apksigner.jar private-input.apk private-output.apk {secret}"
        failure = subprocess.TimeoutExpired(
            command,
            3,
            output=echoed.encode("utf-8"),
            stderr=echoed,
        )

        message = module.redact_process_error(failure, secrets=(secret,))

        self.assertIn("java.exe", message)
        self.assertIn("timed out", message)
        for forbidden in (
            secret,
            "apksigner.jar",
            "private-input.apk",
            "private-output.apk",
        ):
            self.assertNotIn(forbidden, message)

        uppercase_command = [value.upper() for value in command]
        case_mismatched = subprocess.TimeoutExpired(
            uppercase_command,
            3,
            output=echoed.lower().encode("utf-8"),
            stderr=echoed.lower(),
        )
        case_message = module.redact_process_error(
            case_mismatched, secrets=(secret,)
        )
        for forbidden in (
            secret,
            "apksigner.jar",
            "private-input.apk",
            "private-output.apk",
        ):
            self.assertNotIn(forbidden, case_message.lower())

    def test_verify_timeout_is_bounded_and_sanitized(self) -> None:
        secret = "timeout-password"
        keystore = self.tool("timeout-release/wf-offline-release.jks")
        config = self.signing_config(keystore)
        java = self.tool("timeout-jdk/bin/java.exe")
        self.tool("timeout-jdk/bin/keytool.exe")
        leaked = f"{secret} {keystore.resolve()}"

        class VerifyTimeoutRunner(RecordingRunner):
            def __call__(self, argv, **kwargs):
                arguments = [str(value) for value in argv]
                if "-exportcert" in arguments:
                    super().__call__(argv, **kwargs)
                    raise subprocess.TimeoutExpired(
                        argv,
                        3,
                        output=leaked.encode("utf-16-le"),
                        stderr=leaked,
                    )
                return super().__call__(argv, **kwargs)

        verify_runner = VerifyTimeoutRunner(
            {
                "java.exe": SimpleNamespace(
                    returncode=0, stdout="", stderr='java version "1.8.0_451"\n'
                )
            }
        )
        with self.assertRaises(module.ToolchainError) as verify_raised:
            module.verify_signing_config(
                config,
                java=java,
                env={"WF_OFFLINE_KEYSTORE_PASSWORD": secret},
                runner=verify_runner,
            )
        self.assertIn("timed out", str(verify_raised.exception))
        self.assertNotIn(secret, str(verify_raised.exception))
        self.assertNotIn(str(self.path), str(verify_raised.exception))
        export_call = next(
            call for call in verify_runner.calls if "-exportcert" in call.argv
        )
        timeout = export_call.kwargs.get("timeout")
        self.assertIsInstance(timeout, (int, float))
        self.assertGreater(timeout, 0)

    def test_signer_fingerprint_is_verified_from_keystore_before_ready(self) -> None:
        secret = "fixture-password"
        certificate = b"actual certificate"
        keystore = self.tool("release/wf-offline-release.jks")
        java = self.tool("jdk/bin/java.exe")
        self.tool("jdk/bin/keytool.exe")
        config = self.signing_config(
            keystore, hashlib.sha256(certificate).hexdigest()
        )
        runner = RecordingRunner(
            {
                "java.exe": SimpleNamespace(
                    returncode=0, stdout="", stderr='java version "1.8.0_451"\n'
                ),
                "keytool.exe": SimpleNamespace(
                    returncode=0, stdout=certificate, stderr=b""
                )
            }
        )

        report = module.verify_signing_config(
            config,
            java=java,
            env={"WF_OFFLINE_KEYSTORE_PASSWORD": secret},
            runner=runner,
        )

        self.assertTrue(report["fingerprint_verified"])
        self.assertTrue(report["signer_ready"])
        self.assertNotIn(secret, " ".join(runner.calls[0].argv))
        self.assertNotIn(str(keystore.resolve()), runner.calls[0].argv)
        keytool_calls = [
            call for call in runner.calls if "keytool" in Path(call.argv[0]).name.lower()
        ]
        self.assertEqual(2, len(keytool_calls))
        certreq_call = next(call for call in keytool_calls if "-certreq" in call.argv)
        self.assertEqual((secret + "\n" + secret + "\n").encode("utf-8"), certreq_call.kwargs["input"])
        for call in keytool_calls:
            self.assertGreater(call.kwargs["timeout"], 0)
            joined = " ".join(call.argv)
            self.assertNotIn("-storepass", joined)
            self.assertNotIn("-keypass", joined)

        drifted = self.signing_config(keystore, "cd" * 32)
        with self.assertRaisesRegex(module.ToolchainError, "fingerprint drift"):
            module.verify_signing_config(
                drifted,
                java=java,
                env={"WF_OFFLINE_KEYSTORE_PASSWORD": secret},
                runner=runner,
            )

    def test_verify_rejects_private_key_with_a_different_password(self) -> None:
        secret = "shared-password"
        certificate = b"certificate for a key with another password"
        keystore = self.tool("different-keypass/wf-offline-release.jks")
        java = self.tool("different-keypass-jdk/bin/java.exe")
        self.tool("different-keypass-jdk/bin/keytool.exe")
        config = self.signing_config(
            keystore, hashlib.sha256(certificate).hexdigest()
        )

        class DifferentKeyPasswordRunner(RecordingRunner):
            def __call__(self, argv, **kwargs):
                call_result = super().__call__(argv, **kwargs)
                arguments = [str(value) for value in argv]
                if "-exportcert" in arguments:
                    return SimpleNamespace(
                        returncode=0, stdout=certificate, stderr=b""
                    )
                if "-certreq" in arguments:
                    leaked = f"wrong key password {secret} {keystore.resolve()}"
                    return SimpleNamespace(
                        returncode=1,
                        stdout=b"",
                        stderr=leaked.encode("utf-8"),
                    )
                return call_result

        runner = DifferentKeyPasswordRunner(
            {
                "java.exe": SimpleNamespace(
                    returncode=0, stdout="", stderr='java version "1.8.0_451"\n'
                )
            }
        )
        with self.assertRaises(module.ToolchainError) as raised:
            module.verify_signing_config(
                config,
                java=java,
                env={"WF_OFFLINE_KEYSTORE_PASSWORD": secret},
                runner=runner,
            )

        message = str(raised.exception)
        self.assertIn("private key", message)
        self.assertNotIn(secret, message)
        self.assertNotIn(str(self.path), message)
        certreq_call = next(call for call in runner.calls if "-certreq" in call.argv)
        self.assertGreater(certreq_call.kwargs["timeout"], 0)
        self.assertEqual(
            (secret + "\n" + secret + "\n").encode("utf-8"),
            certreq_call.kwargs["input"],
        )

    def test_discovery_marks_public_signer_configured_but_not_verified_ready(self) -> None:
        home = self.path / "release-home"
        home.mkdir()
        (home / "wf-offline-release.jks").write_bytes(b"fixture")
        (home / "signer-public.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "alias": "wf-offline-release",
                    "certificate_sha256": "ab" * 32,
                }
            ),
            encoding="utf-8",
        )

        configured, ready, fingerprint = module._signer_discovery_status(home)

        self.assertTrue(configured)
        self.assertFalse(ready)
        self.assertEqual("ab" * 32, fingerprint)

    def test_bootstrap_requires_exact_confirmation_and_outside_repo_home(self) -> None:
        java = self.tool("jdk/bin/java.exe")
        self.tool("jdk/bin/keytool.exe")
        runner = BootstrapRunner(b"certificate")

        with self.assertRaisesRegex(module.ToolchainError, "exact confirmation"):
            module.init_signer_interactive(
                self.path / "release-home",
                confirmation="create_wf_offline_release_signer",
                java=java,
                runner=runner,
            )
        self.assertEqual([], runner.calls)

        inside_repo = MOD_TOOLS / ".task7-signer-must-not-create"
        self.assertFalse(inside_repo.exists())
        with self.assertRaisesRegex(module.ToolchainError, "outside the repository"):
            module.init_signer_interactive(
                inside_repo,
                confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
                java=java,
                runner=runner,
            )
        self.assertEqual([], runner.calls)
        self.assertFalse(inside_repo.exists())

    def test_public_signer_apis_have_no_repo_or_keytool_override(self) -> None:
        bootstrap = inspect.signature(module.init_signer_interactive).parameters
        verify = inspect.signature(module.verify_signing_config).parameters
        self.assertNotIn("repo_root", bootstrap)
        self.assertNotIn("keytool", bootstrap)
        self.assertNotIn("keytool", verify)

    def test_bootstrap_and_verify_reject_non_java8_before_keytool_or_creation(self) -> None:
        java = self.tool("jdk17/bin/java.exe")
        self.tool("jdk17/bin/keytool.exe")
        java17 = RecordingRunner(
            {
                "java.exe": SimpleNamespace(
                    returncode=0, stdout="", stderr='java version "17.0.12"\n'
                )
            }
        )
        release_home = self.path / "must-not-exist"
        with self.assertRaisesRegex(module.ToolchainError, "Java 8"):
            self.bootstrap_signer(
                release_home,
                confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
                java=java,
                runner=java17,
            )
        self.assertFalse(release_home.exists())
        self.assertFalse(any("keytool" in Path(call.argv[0]).name.lower() for call in java17.calls))

        keystore = self.tool("release/wf-offline-release.jks")
        config = self.signing_config(keystore)
        with self.assertRaisesRegex(module.ToolchainError, "Java 8"):
            module.verify_signing_config(
                config,
                java=java,
                env={"WF_OFFLINE_KEYSTORE_PASSWORD": "secret"},
                runner=java17,
            )
        self.assertFalse(any("keytool" in Path(call.argv[0]).name.lower() for call in java17.calls))

    def test_default_bootstrap_requires_three_real_tty_streams_before_creation(self) -> None:
        release_home = self.path / "no-console-home"
        java = self.tool("jdk/bin/java.exe")
        self.tool("jdk/bin/keytool.exe")
        with mock.patch.object(module, "_console_streams_are_tty", return_value=False):
            with self.assertRaisesRegex(module.ToolchainError, "interactive console"):
                module.init_signer_interactive(
                    release_home,
                    confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
                    java=java,
                )
        self.assertFalse(release_home.exists())

    def test_custom_runner_cannot_bypass_bootstrap_tty_gate(self) -> None:
        release_home = self.path / "custom-runner-no-console"
        java = self.tool("custom-runner-jdk/bin/java.exe")
        self.tool("custom-runner-jdk/bin/keytool.exe")
        runner = BootstrapRunner(b"certificate")
        with mock.patch.object(module, "_console_streams_are_tty", return_value=False):
            with self.assertRaisesRegex(module.ToolchainError, "interactive console"):
                module.init_signer_interactive(
                    release_home,
                    confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
                    java=java,
                    runner=runner,
                )
        self.assertEqual([], runner.calls)
        self.assertFalse(release_home.exists())

    def test_atomic_public_config_never_overwrites_existing_or_racing_target(self) -> None:
        home = self.path / "atomic-public"
        home.mkdir()
        target = home / "signer-public.json"
        sentinel = b"existing-sentinel"
        target.write_bytes(sentinel)
        with self.assertRaisesRegex(module.ToolchainError, "already exists"):
            module._atomic_write_public_config(target, {"schema_version": 1})
        self.assertEqual(sentinel, target.read_bytes())

        target.unlink()
        original_link = os.link

        def race_link(source, destination):
            Path(destination).write_bytes(sentinel)
            return original_link(source, destination)

        with mock.patch.object(module.os, "link", side_effect=race_link):
            with self.assertRaisesRegex(module.ToolchainError, "already exists"):
                module._atomic_write_public_config(target, {"schema_version": 1})
        self.assertEqual(sentinel, target.read_bytes())
        self.assertEqual([], list(home.glob("*.tmp")))

    def test_bootstrap_exclusive_lock_refuses_parallel_initialization(self) -> None:
        release_home = self.path / "locked-home"
        release_home.mkdir()
        lock = release_home / ".wf-offline-signer-init.lock"
        lock.write_text("sentinel", encoding="utf-8")
        java = self.tool("jdk/bin/java.exe")
        self.tool("jdk/bin/keytool.exe")
        runner = BootstrapRunner(b"certificate")

        with self.assertRaisesRegex(module.ToolchainError, "bootstrap already in progress"):
            self.bootstrap_signer(
                release_home,
                confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
                java=java,
                runner=runner,
            )

        self.assertEqual("sentinel", lock.read_text("utf-8"))
        self.assertFalse((release_home / "wf-offline-release.jks").exists())
        self.assertFalse(any("keytool" in Path(call.argv[0]).name.lower() for call in runner.calls))

    def test_bootstrap_is_interactive_atomic_and_leaves_only_stable_public_config(self) -> None:
        release_home = self.path / "private" / ".wf-offline-release"
        java = self.tool("jdk/bin/java.exe")
        self.tool("jdk/bin/keytool.exe")
        certificate = b"public DER certificate fixture"
        runner = BootstrapRunner(certificate)

        config = self.bootstrap_signer(
            release_home,
            confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
            java=java,
            runner=runner,
        )

        self.assertEqual(release_home / "wf-offline-release.jks", config.keystore)
        public = json.loads((release_home / "signer-public.json").read_text("utf-8"))
        self.assertEqual(hashlib.sha256(certificate).hexdigest(), public["certificate_sha256"])
        self.assertEqual("wf-offline-release", public["alias"])
        keytool_calls = [call for call in runner.calls if "keytool" in Path(call.argv[0]).name.lower()]
        self.assertEqual(2, len(keytool_calls))
        for call in keytool_calls:
            joined = " ".join(call.argv)
            self.assertNotIn("-storepass", joined)
            self.assertNotIn("-keypass", joined)
            self.assertNotIn("stdin", call.kwargs)
            self.assertNotIn("stdout", call.kwargs)
            self.assertNotIn("stderr", call.kwargs)
            self.assertNotIn("timeout", call.kwargs)
        generated = " ".join(keytool_calls[0].argv)
        self.assertIn("-keysize 4096", generated)
        self.assertIn("-validity 9125", generated)
        self.assertIn("-storetype JKS", generated)
        self.assertIn("-sigalg SHA256withRSA", generated)
        generated_keystore = keytool_calls[0].argv[
            keytool_calls[0].argv.index("-keystore") + 1
        ]
        exported_keystore = keytool_calls[1].argv[
            keytool_calls[1].argv.index("-keystore") + 1
        ]
        generation_cwd = Path(keytool_calls[0].kwargs["cwd"])
        export_cwd = Path(keytool_calls[1].kwargs["cwd"])
        self.assertNotEqual(release_home, generation_cwd)
        self.assertEqual(release_home, generation_cwd.parent)
        self.assertEqual(generation_cwd, export_cwd)
        self.assertNotEqual(
            config.keystore, (generation_cwd / generated_keystore).resolve()
        )
        self.assertEqual(generated_keystore, exported_keystore)
        self.assertEqual(".jks", Path(generated_keystore).suffix)
        self.assertEqual(b"fixture-jks", config.keystore.read_bytes())
        self.assertEqual([config.keystore], list(release_home.glob("*.jks")))
        self.assertEqual([], list(release_home.glob(".wf-offline-release.*.tmp")))
        self.assertEqual([], list(release_home.glob("*.cer")))
        self.assertEqual([], list(release_home.glob("*.tmp")))
        self.assertFalse((release_home / ".wf-offline-signer-init.lock").exists())

        with self.assertRaisesRegex(module.ToolchainError, "already exists"):
            self.bootstrap_signer(
                release_home,
                confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
                java=java,
                runner=runner,
            )

    def test_bootstrap_never_overwrites_a_racing_final_keystore(self) -> None:
        release_home = self.path / "racing-keystore"
        java = self.tool("racing-jdk/bin/java.exe")
        self.tool("racing-jdk/bin/keytool.exe")
        runner = BootstrapRunner(b"certificate")
        final_keystore = release_home / "wf-offline-release.jks"
        sentinel = b"external-race-sentinel"
        original_link = os.link

        def race_link(source, destination):
            if Path(destination) == final_keystore:
                final_keystore.write_bytes(sentinel)
            return original_link(source, destination)

        with mock.patch.object(module.os, "link", side_effect=race_link):
            with self.assertRaisesRegex(module.ToolchainError, "already exists"):
                self.bootstrap_signer(
                    release_home,
                    confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
                    java=java,
                    runner=runner,
                )

        self.assertEqual(sentinel, final_keystore.read_bytes())
        self.assertEqual([final_keystore], list(release_home.glob("*.jks")))
        self.assertFalse((release_home / "signer-public.json").exists())
        self.assertFalse((release_home / module.SIGNER_LOCK_NAME).exists())

    def test_bootstrap_preserves_published_keystore_if_public_config_fails(self) -> None:
        release_home = self.path / "public-config-failure"
        java = self.tool("public-failure-jdk/bin/java.exe")
        self.tool("public-failure-jdk/bin/keytool.exe")
        runner = BootstrapRunner(b"certificate")
        with mock.patch.object(
            module,
            "_atomic_write_public_config",
            side_effect=module.ToolchainError("public config publication failed"),
        ):
            with self.assertRaisesRegex(module.ToolchainError, "publication failed"):
                self.bootstrap_signer(
                    release_home,
                    confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
                    java=java,
                    runner=runner,
                )

        final_keystore = release_home / "wf-offline-release.jks"
        self.assertEqual(b"fixture-jks", final_keystore.read_bytes())
        self.assertEqual([final_keystore], list(release_home.glob("*.jks")))
        self.assertFalse((release_home / "signer-public.json").exists())
        self.assertFalse((release_home / module.SIGNER_LOCK_NAME).exists())

    def test_bootstrap_resolves_keytool_from_the_selected_java_home(self) -> None:
        class JavaHomeRunner(BootstrapRunner):
            def __init__(self, certificate: bytes, java_home: Path) -> None:
                super().__init__(certificate)
                self.java_home = java_home

            def __call__(self, argv, **kwargs):
                arguments = [str(value) for value in argv]
                if "-XshowSettings:properties" in arguments:
                    RecordingRunner.__call__(self, argv, **kwargs)
                    return SimpleNamespace(
                        returncode=0,
                        stdout=b"",
                        stderr=f"    java.home = {self.java_home}\n".encode("utf-8"),
                    )
                return super().__call__(argv, **kwargs)

        release_home = self.path / "private" / ".wf-offline-release"
        selected_java = self.tool("shim/java.exe")
        real_java_home = self.path / "real-jre"
        real_keytool = self.tool("real-jre/bin/keytool.exe")
        runner = JavaHomeRunner(b"certificate", real_java_home)

        self.bootstrap_signer(
            release_home,
            confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
            java=selected_java,
            runner=runner,
        )

        settings_call = next(call for call in runner.calls if "-XshowSettings:properties" in call.argv)
        self.assertEqual(subprocess.DEVNULL, settings_call.kwargs["stdin"])
        keytool_call = next(call for call in runner.calls if "-genkeypair" in call.argv)
        self.assertEqual(str(real_keytool), keytool_call.argv[0])

    def test_bootstrap_cleans_temporary_certificate_on_export_failure(self) -> None:
        class FailingExportRunner(BootstrapRunner):
            def __call__(self, argv, **kwargs):
                result = super().__call__(argv, **kwargs)
                if "-exportcert" in [str(value) for value in argv]:
                    return SimpleNamespace(returncode=1, stdout="", stderr="export failed")
                return result

        release_home = self.path / "private" / ".wf-offline-release"
        java = self.tool("jdk/bin/java.exe")
        self.tool("jdk/bin/keytool.exe")
        runner = FailingExportRunner(b"temporary")

        with self.assertRaisesRegex(module.ToolchainError, "keytool exportcert failed"):
            self.bootstrap_signer(
                release_home,
                confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
                java=java,
                runner=runner,
            )

        self.assertEqual([], list(release_home.glob("*.cer")))
        self.assertEqual([], list(release_home.glob("*.jks")))
        self.assertFalse((release_home / "signer-public.json").exists())
        self.assertFalse((release_home / ".wf-offline-signer-init.lock").exists())

    def test_bootstrap_cleans_temporary_keystore_on_generation_failure(self) -> None:
        class FailingGenerationRunner(BootstrapRunner):
            def __call__(self, argv, **kwargs):
                result = super().__call__(argv, **kwargs)
                if "-genkeypair" in [str(value) for value in argv]:
                    return SimpleNamespace(
                        returncode=1, stdout="", stderr="generation failed"
                    )
                return result

        release_home = self.path / "generation-failure"
        java = self.tool("generation-failure-jdk/bin/java.exe")
        self.tool("generation-failure-jdk/bin/keytool.exe")
        runner = FailingGenerationRunner(b"unused")

        with self.assertRaisesRegex(module.ToolchainError, "keytool genkeypair failed"):
            self.bootstrap_signer(
                release_home,
                confirmation="CREATE_WF_OFFLINE_RELEASE_SIGNER",
                java=java,
                runner=runner,
            )

        self.assertEqual([], list(release_home.glob("*.jks")))
        self.assertEqual([], list(release_home.glob("*.cer")))
        self.assertFalse((release_home / "signer-public.json").exists())
        self.assertFalse((release_home / module.SIGNER_LOCK_NAME).exists())


if __name__ == "__main__":
    unittest.main()

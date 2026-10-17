from __future__ import annotations

from external_sources import client_patch_path, require_external_source

from wf.paths import root_path

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from contextlib import ExitStack
from pathlib import Path, PureWindowsPath
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = client_patch_path('offline-android/build_offline_apk.py')
TARGET_SWF = "assets/worldflipper_android_release.swf"
PASSWORD_ENV = "WF_OFFLINE_KEYSTORE_PASSWORD"
PASSWORD = "offline-test-secret"
FINGERPRINT = "12" * 32
OTHER_FINGERPRINT = "34" * 32


def load_module():
    spec = importlib.util.spec_from_file_location("offline_apk_builder", require_external_source(MODULE_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_apk(
    path: Path,
    *,
    swf: bytes = b"base-swf",
    dex: bytes = b"dex",
    signatures: bool = True,
    extra: dict[str, bytes] | None = None,
) -> None:
    members = {
        TARGET_SWF: swf,
        "AndroidManifest.xml": b"manifest",
        "classes.dex": dex,
        "classes2.dex": b"dex-2",
        "lib/arm64-v8a/libwf.so": b"native",
        "assets/unchanged.bin": b"unchanged",
        "META-INF/AIR/application.xml": b"air-metadata",
    }
    if signatures:
        members.update(
            {
                "META-INF/MANIFEST.MF": b"manifest-signature",
                "META-INF/CERT.SF": b"signature-file",
                "META-INF/CERT.RSA": b"signature-block",
            }
        )
    if extra:
        members.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def member_bytes(apk: Path, name: str) -> bytes:
    with zipfile.ZipFile(apk, "r") as archive:
        return archive.read(name)


class FakeBaseline:
    def __init__(self, lock: dict[str, object]) -> None:
        self.lock = lock
        self.inspected: list[Path] = []
        self.asserted = 0
        self.diffed = 0
        self.loads = 0
        self.mutate_after_final_inspect = False
        self.drift_final_devconfig = False
        self.drift_final_resource = False

    def load_base_lock(self, path: Path):
        self.loads += 1
        return self.lock

    def inspect_apk(self, apk: Path, toolchain, *, runner):
        self.inspected.append(Path(apk))
        save_hashes = self.lock["save_method_sha256"]
        final = len(self.inspected) == 2
        offline = {
            "DevConfig_individual/DevConfig_individual": (
                "f" * 64 if final and self.drift_final_devconfig else "a" * 64
            ),
            "boot_ffc6#$script364/$init": (
                "f" * 64
                if final and self.drift_final_resource
                else ("c" * 64 if final else "b" * 64)
            ),
            **save_hashes,
        }
        report = types.SimpleNamespace(
            apk_sha256=sha256(Path(apk).read_bytes()),
            swf_sha256=sha256(member_bytes(Path(apk), TARGET_SWF)),
            package_name="com.leiting.wf",
            version_code="1008001",
            version_name="1.8.1",
            manifest_sha256=sha256(b"manifest"),
            dex_sha256={
                "classes.dex": sha256(b"dex"),
                "classes2.dex": sha256(b"dex-2"),
            },
            native_aggregate_sha256=sha256(b"native"),
            offline_method_sha256=offline,
        )
        if self.mutate_after_final_inspect and len(self.inspected) == 2:
            Path(apk).write_bytes(Path(apk).read_bytes() + b"signature-tail-race")
        return report

    def assert_locked_baseline(self, report, lock):
        self.asserted += 1
        return report

    def assert_allowed_member_diff(self, base_apk: Path, output_apk: Path) -> None:
        self.diffed += 1
        with zipfile.ZipFile(base_apk, "r") as base, zipfile.ZipFile(
            output_apk, "r"
        ) as output:
            base_members = {
                item.filename: sha256(base.read(item))
                for item in base.infolist()
                if not self._is_signature(item.filename)
            }
            output_members = {
                item.filename: sha256(output.read(item))
                for item in output.infolist()
                if not self._is_signature(item.filename)
            }
        if set(base_members) != set(output_members):
            raise RuntimeError("non-signature APK member set changed")
        drift = sorted(
            name
            for name, digest in base_members.items()
            if name != TARGET_SWF and output_members[name] != digest
        )
        if drift:
            raise RuntimeError(f"unexpected member drift: {drift[0]}")

    @staticmethod
    def _is_signature(name: str) -> bool:
        parts = name.split("/")
        if len(parts) != 2 or parts[0] != "META-INF":
            return False
        filename = parts[1]
        return filename == "MANIFEST.MF" or filename.endswith(
            (".SF", ".RSA", ".DSA", ".EC")
        )


class FakeRunner:
    def __init__(
        self,
        *,
        fingerprint: str = FINGERPRINT,
        schemes: tuple[bool, bool, bool] = (True, True, True),
        fail_stage: str | None = None,
        race_output: Path | None = None,
        race_source: Path | None = None,
    ) -> None:
        self.fingerprint = fingerprint
        self.schemes = schemes
        self.fail_stage = fail_stage
        self.race_output = race_output
        self.race_source = race_source
        self.events: list[str] = []
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, command, **kwargs):
        argv = tuple(str(part) for part in command)
        self.commands.append(argv)
        if "sign" in argv:
            event = "apksigner-sign"
        elif "verify" in argv and "--print-certs" in argv:
            event = "apksigner-verify"
        elif "-c" in argv:
            event = "zipalign-check"
        else:
            event = "zipalign-build"
        self.events.append(event)
        if self.fail_stage == event:
            raise subprocess.CalledProcessError(
                7,
                argv,
                output=f"stdout {PASSWORD}".encode(),
                stderr=f"stderr {PASSWORD}".encode(),
            )
        if event == "zipalign-build":
            shutil.copyfile(Path(argv[-2]), Path(argv[-1]))
        elif event == "apksigner-sign":
            shutil.copyfile(Path(argv[-1]), Path(argv[argv.index("--out") + 1]))
        elif event == "apksigner-verify":
            if self.race_output is not None:
                self.race_output.write_bytes(b"competitor")
            if self.race_source is not None:
                payload = self.race_source.read_bytes()
                self.race_source.unlink()
                self.race_source.write_bytes(payload)
            v1, v2, v3 = (str(value).lower() for value in self.schemes)
            output = (
                f"Verified using v1 scheme (JAR signing): {v1}\n"
                f"Verified using v2 scheme (APK Signature Scheme v2): {v2}\n"
                f"Verified using v3 scheme (APK Signature Scheme v3): {v3}\n"
                f"Signer #1 certificate SHA-256 digest: {self.fingerprint}\n"
            ).encode()
            return subprocess.CompletedProcess(argv, 0, output, b"")
        return subprocess.CompletedProcess(argv, 0, b"ok", b"")

    def count(self, event: str) -> int:
        return self.events.count(event)


class BuilderFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        require_external_source(MODULE_PATH)
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="offline-apk-builder-")
        self.root = Path(self.temp.name)
        self.base = self.root / "base.apk"
        self.output = self.root / "发布" / "WorldFlipper-离线整合版.apk"
        self.report = self.root / "发布" / "build-report.json"
        self.work = self.root / "ascii-work"
        self.lock_path = self.root / "base-lock.json"
        self.keystore = self.root / "signer" / "offline-release.jks"
        self.java = self.root / "tools" / "java.exe"
        self.ffdec = self.root / "tools" / "ffdec.jar"
        self.aapt = self.root / "tools" / "aapt.exe"
        self.zipalign = self.root / "tools" / "zipalign.exe"
        self.apksigner = self.root / "tools" / "apksigner.exe"
        self.save_hashes = {
            "DummyRemote/debugUnlinkTwitter": "d" * 64,
            "InitializeDummyRemote/logicAssetLoadedHandler": "e" * 64,
        }
        self.lock = {
            "schema_version": 1,
            "offline_method_sha256": {
                "DevConfig_individual/DevConfig_individual": "a" * 64,
                "boot_ffc6#$script364/$init": "b" * 64,
                **self.save_hashes,
            },
            "save_method_sha256": self.save_hashes,
            "resource_version": {
                "target_version": "1.4.196",
                "after_abc_sha256": "c" * 64,
            },
            "site_ids": [f"seris-{index}" for index in range(9)],
            "render_site_ids": [f"render-{index}" for index in range(3)],
        }
        write_apk(self.base)
        self.lock_path.write_text(json.dumps(self.lock), encoding="utf-8")
        for path in (
            self.keystore,
            self.java,
            self.ffdec,
            self.aapt,
            self.zipalign,
            self.apksigner,
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"tool")
        self.toolchain = self.module.Toolchain(
            java=self.java,
            ffdec=self.ffdec,
            aapt=self.aapt,
            zipalign=self.zipalign,
            apksigner=self.apksigner,
            adb=None,
            mumu_manager=None,
            versions={"java": "1.8", "ffdec": "26.2.1", "build_tools": "34.0.0"},
        )
        self.signing = self.module.SigningConfig(
            keystore=self.keystore,
            expected_certificate_sha256=FINGERPRINT,
        )
        self.config = self.module.OfflineApkBuildConfig(
            source_apk=self.base,
            baseline_lock=self.lock_path,
            output_apk=self.output,
            report_path=self.report,
            work_dir=self.work,
            toolchain=self.toolchain,
            signing=self.signing,
        )
        self.baseline = FakeBaseline(self.lock)
        self.stage_events: list[str] = []
        self.verify_events: list[str] = []
        self.stage_locks: list[object] = []
        self.stage_work_dirs: list[tuple[str, Path]] = []
        self.seris_verify_work_dirs: list[Path] = []

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fake_apply(self, stage: str):
        def apply(source: Path, output: Path, *args, **kwargs):
            self.stage_events.append(stage)
            self.stage_work_dirs.append((stage, Path(kwargs["work_dir"])))
            if args:
                self.stage_locks.append(args[0])
            Path(output).write_bytes(Path(source).read_bytes() + stage.encode("ascii"))
            common = {
                "output_path": Path(output),
                "input_sha256": sha256(Path(source).read_bytes()),
                "output_sha256": sha256(Path(output).read_bytes()),
                "verified": True,
            }
            if stage == "abyss-mode-equipment":
                return types.SimpleNamespace(
                    stage=stage,
                    target_class="pinball.common.data.character.BattleCharacterLogic",
                    before_method_sha256="1" * 64,
                    after_method_sha256="2" * 64,
                    match_count=1,
                    **common,
                )
            if stage == "seris-phase4":
                return types.SimpleNamespace(
                    site_ids=tuple(self.lock["site_ids"]),
                    before_hashes={},
                    after_hashes={},
                    asset_logicals=("seris_skill_pf",),
                    **common,
                )
            if stage == "render-scale":
                return types.SimpleNamespace(
                    site_ids=tuple(self.lock["render_site_ids"]),
                    before_hashes={},
                    after_hashes={},
                    **common,
                )
            return types.SimpleNamespace(
                source_version="1.4.54",
                output_version="1.4.196",
                is_full_package=True,
                **common,
            )

        return apply

    def fake_seris_verify(self, output: Path, lock, **kwargs):
        self.verify_events.append("seris-phase4")
        self.seris_verify_work_dirs.append(Path(kwargs["work_dir"]))
        return types.SimpleNamespace(
            output_path=Path(output),
            input_sha256="3" * 64,
            output_sha256="3" * 64,
            site_ids=tuple(self.lock["site_ids"]),
            before_hashes={},
            after_hashes={},
            asset_logicals=("seris_skill_pf",),
            verified=True,
        )

    def fake_render_verify(self, output: Path, lock, **kwargs):
        self.verify_events.append("render-scale")
        return types.SimpleNamespace(
            output_path=Path(output),
            input_sha256="4" * 64,
            output_sha256="4" * 64,
            site_ids=tuple(self.lock["render_site_ids"]),
            before_hashes={},
            after_hashes={},
            verified=True,
        )

    def fake_resource_verify(self, output: Path, lock, **kwargs):
        self.verify_events.append("resource-version")
        return types.SimpleNamespace(
            output_path=Path(output),
            input_sha256="5" * 64,
            output_sha256="5" * 64,
            source_version="1.4.54",
            output_version="1.4.196",
            is_full_package=True,
            verified=True,
        )

    def fake_abyss_verify(self, output: Path, **kwargs):
        self.verify_events.append("abyss-mode-equipment")
        return {"stage": "abyss-mode-equipment", "verified": True}

    def patches(self) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(mock.patch.object(self.module, "BASELINE", self.baseline))
        stack.enter_context(
            mock.patch.object(
                self.module.ABYSS,
                "apply_gate_to_swf",
                self.fake_apply("abyss-mode-equipment"),
            )
        )
        stack.enter_context(
            mock.patch.object(
                self.module.SERIS,
                "apply_seris_phase4",
                self.fake_apply("seris-phase4"),
            )
        )
        stack.enter_context(
            mock.patch.object(
                self.module.RENDER,
                "apply_render_scale",
                self.fake_apply("render-scale"),
            )
        )
        stack.enter_context(
            mock.patch.object(
                self.module.RESOURCE,
                "apply_resource_version",
                self.fake_apply("resource-version"),
            )
        )
        stack.enter_context(
            mock.patch.object(
                self.module.SERIS,
                "verify_seris_phase4",
                self.fake_seris_verify,
            )
        )
        stack.enter_context(
            mock.patch.object(
                self.module.RENDER,
                "verify_render_scale",
                self.fake_render_verify,
            )
        )
        stack.enter_context(
            mock.patch.object(
                self.module.RESOURCE,
                "verify_resource_version",
                self.fake_resource_verify,
            )
        )
        stack.enter_context(
            mock.patch.object(
                self.module, "verify_abyss_gate", self.fake_abyss_verify
            )
        )
        stack.enter_context(mock.patch.dict(os.environ, {PASSWORD_ENV: PASSWORD}))
        return stack

    def assert_clean_failure(self) -> None:
        self.assertFalse(self.output.exists())
        self.assertFalse(self.report.exists())
        if self.work.exists():
            self.assertEqual(list(self.work.glob(".offline-apk-*")), [])
        output_parent = self.output.parent
        if output_parent.exists():
            self.assertEqual(list(output_parent.glob(".offline-apk-*")), [])


class OfflineApkBuilderTests(BuilderFixture):
    def test_same_destination_parent_reuses_one_deny_delete_handle(self) -> None:
        original = self.module._open_destination_directory
        opened: list[tuple[Path, bool]] = []

        def record(path: Path, *, deny_delete: bool = False):
            opened.append((Path(path), deny_delete))
            return original(path, deny_delete=deny_delete)

        with mock.patch.dict(os.environ, {PASSWORD_ENV: PASSWORD}), mock.patch.object(
            self.module, "_open_destination_directory", record
        ):
            resolved = self.module._resolve_config(self.config)
        try:
            self.assertIs(resolved.output_parent, resolved.report_parent)
            self.assertEqual(opened, [(self.output.parent, True)])
        finally:
            self.module._close_owned_directory(resolved.report_parent)
            self.module._close_owned_directory(resolved.output_parent)

    def test_patches_rewrites_aligns_signs_and_verifies_exactly_once(self) -> None:
        runner = FakeRunner()
        with self.patches(), mock.patch.object(
            self.module,
            "_rewrite_apk_archive",
            wraps=self.module._rewrite_apk_archive,
        ) as rewrite:
            report = self.module.build_offline_apk(self.config, runner=runner)

        self.assertEqual(report.patch_order, self.module.PATCH_ORDER)
        self.assertEqual(self.stage_events, list(self.module.PATCH_ORDER))
        self.assertEqual(self.verify_events, list(self.module.PATCH_ORDER))
        rewrite.assert_called_once()
        for event in (
            "zipalign-build",
            "apksigner-sign",
            "zipalign-check",
            "apksigner-verify",
        ):
            self.assertEqual(runner.count(event), 1)
        self.assertEqual(self.baseline.asserted, 1)
        self.assertEqual(self.baseline.loads, 1)
        self.assertEqual(len(self.baseline.inspected), 2)
        self.assertEqual(self.baseline.diffed, 2)
        self.assertEqual(self.stage_locks, [self.lock, self.lock, self.lock])
        self.assertTrue(report.verified)
        self.assertTrue(self.output.is_file())
        self.assertTrue(self.report.is_file())

    def test_ffdec_internal_paths_stay_below_windows_classic_max_path(self) -> None:
        with self.patches():
            self.module.build_offline_apk(self.config, runner=FakeRunner())

        apply_work = next(
            path for stage, path in self.stage_work_dirs if stage == "seris-phase4"
        )
        verify_work = self.seris_verify_work_dirs[0]

        def relative_to_transaction(path: Path) -> PureWindowsPath:
            transaction = next(
                parent
                for parent in (path, *path.parents)
                if parent.name.startswith(".offline-apk-")
            )
            return PureWindowsPath(*path.relative_to(transaction).parts)

        transaction = PureWindowsPath(
            ('${WF_ROOT}\\startpoint-cn\\out\\wf-offline-android\\1.4.196\\.staging-ed8b36a0a2194376af553988ebcb4a15\\apk-work\\.offline-apk-7a_mmq0j'.replace("${WF_ROOT}", str(root_path())))
        )
        class_leaf = PureWindowsPath(
            "scripts",
            "pinball",
            "scene",
            "battle",
            "viewInput",
            "processor",
            "flipButton",
            "CharacterSpriteView.pcode",
        )
        apply_relative = relative_to_transaction(apply_work)
        verify_relative = relative_to_transaction(verify_work)
        self.assertEqual(PureWindowsPath("w"), apply_relative)
        self.assertEqual(PureWindowsPath("v", "w"), verify_relative)

        apply_target = (
            transaction
            / apply_relative
            / ".seris-phase4-12345678"
            / "08-before-export"
            / class_leaf
        )
        verify_target = (
            transaction
            / verify_relative
            / ".seris-verify-12345678"
            / "reopen-export"
            / class_leaf
        )

        self.assertLess(len(str(apply_target)), 260, str(apply_target))
        self.assertLess(len(str(verify_target)), 260, str(verify_target))

    def test_rewrite_strips_only_top_level_signatures_and_preserves_air(self) -> None:
        swf = self.root / "patched.swf"
        unsigned = self.root / "unsigned.apk"
        swf.write_bytes(b"patched")
        self.module.rewrite_apk_once(self.base, swf, unsigned)
        with zipfile.ZipFile(unsigned, "r") as archive:
            names = archive.namelist()
            self.assertNotIn("META-INF/MANIFEST.MF", names)
            self.assertNotIn("META-INF/CERT.SF", names)
            self.assertNotIn("META-INF/CERT.RSA", names)
            self.assertIn("META-INF/AIR/application.xml", names)
            self.assertEqual(
                archive.read("META-INF/AIR/application.xml"), b"air-metadata"
            )
            self.assertEqual(archive.read(TARGET_SWF), b"patched")

    def test_rewrite_preserves_lowercase_signature_like_member(self) -> None:
        base = self.root / "lowercase.apk"
        write_apk(
            base,
            signatures=False,
            extra={"META-INF/cert.sf": b"not-a-signature"},
        )
        swf = self.root / "patched-lowercase.swf"
        unsigned = self.root / "unsigned-lowercase.apk"
        swf.write_bytes(b"patched")
        self.module.rewrite_apk_once(base, swf, unsigned)
        with zipfile.ZipFile(unsigned, "r") as archive:
            self.assertEqual(archive.read("META-INF/cert.sf"), b"not-a-signature")

    def test_member_diff_rejects_changed_dex(self) -> None:
        changed = self.root / "changed.apk"
        write_apk(changed, swf=b"patched", dex=b"changed-dex")
        with mock.patch.object(self.module, "BASELINE", self.baseline):
            with self.assertRaisesRegex(
                self.module.ApkBuildError, "unexpected member drift: classes.dex"
            ):
                self.module.assert_allowed_member_diff(self.base, changed)

    def test_output_uses_dedicated_signer_and_requires_v1_v2_v3(self) -> None:
        runner = FakeRunner(fingerprint=OTHER_FINGERPRINT)
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "fingerprint drift"
        ):
            self.module.build_offline_apk(self.config, runner=runner)
        self.assert_clean_failure()

        runner = FakeRunner(schemes=(True, False, True))
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "v2 verification failed"
        ):
            self.module.build_offline_apk(self.config, runner=runner)
        self.assert_clean_failure()

    def test_sign_command_uses_env_password_and_disables_v4(self) -> None:
        runner = FakeRunner()
        with self.patches():
            self.module.build_offline_apk(self.config, runner=runner)
        sign = next(command for command in runner.commands if "sign" in command)
        self.assertIn(f"env:{PASSWORD_ENV}", sign)
        self.assertEqual(sign.count(f"env:{PASSWORD_ENV}"), 2)
        self.assertEqual(sign[sign.index("--v4-signing-enabled") + 1], "false")
        self.assertNotIn(PASSWORD, " ".join(sign))

    def test_batch_apksigner_sign_and_verify_use_the_same_selected_java_jar(self) -> None:
        batch = self.root / "tools" / "apksigner.bat"
        jar = batch.parent / "lib" / "apksigner.jar"
        batch.write_bytes(b"batch")
        jar.parent.mkdir(parents=True, exist_ok=True)
        jar.write_bytes(b"jar")
        toolchain = self.module.Toolchain(
            java=self.java,
            ffdec=self.ffdec,
            aapt=self.aapt,
            zipalign=self.zipalign,
            apksigner=batch,
            adb=None,
            mumu_manager=None,
            versions=self.toolchain.versions,
        )
        config = self.module.OfflineApkBuildConfig(
            source_apk=self.config.source_apk,
            baseline_lock=self.config.baseline_lock,
            output_apk=self.config.output_apk,
            report_path=self.config.report_path,
            work_dir=self.config.work_dir,
            toolchain=toolchain,
            signing=self.config.signing,
        )
        runner = FakeRunner()
        with self.patches():
            self.module.build_offline_apk(config, runner=runner)
        sign = next(command for command in runner.commands if "sign" in command)
        verify = next(
            command
            for command in runner.commands
            if "verify" in command and "--print-certs" in command
        )
        expected_prefix = (str(self.java.resolve()), "-jar", str(jar.resolve()))
        self.assertEqual(sign[:3], expected_prefix)
        self.assertEqual(verify[:3], expected_prefix)

    def test_chinese_final_name_never_reaches_external_commands(self) -> None:
        runner = FakeRunner()
        with self.patches():
            self.module.build_offline_apk(self.config, runner=runner)
        self.assertTrue(self.output.is_file())
        rendered = "\n".join(" ".join(command) for command in runner.commands)
        self.assertNotIn("发布", rendered)
        self.assertNotIn("离线整合版", rendered)
        for command in runner.commands:
            self.assertTrue(all(part.isascii() for part in command))

    def test_failure_redacts_password_and_cleans_transaction(self) -> None:
        runner = FakeRunner(fail_stage="apksigner-sign")
        with self.patches(), self.assertRaises(self.module.ApkBuildError) as raised:
            self.module.build_offline_apk(self.config, runner=runner)
        self.assertNotIn(PASSWORD, str(raised.exception))
        self.assertIn("[REDACTED]", str(raised.exception))
        self.assert_clean_failure()

    def test_missing_signer_password_fails_before_baseline_or_patch_work(self) -> None:
        runner = FakeRunner()
        with self.patches(), mock.patch.dict(
            os.environ, {PASSWORD_ENV: ""}
        ), self.assertRaisesRegex(
            self.module.ApkBuildError, PASSWORD_ENV
        ):
            self.module.build_offline_apk(self.config, runner=runner)
        self.assertEqual(self.baseline.loads, 0)
        self.assertEqual(self.stage_events, [])
        self.assertEqual(runner.events, [])
        self.assert_clean_failure()

    def test_builder_uses_only_the_frozen_baseline_lock_mapping(self) -> None:
        original_read_bytes = Path.read_bytes

        def guarded_read_bytes(path: Path):
            if Path(path) == self.lock_path:
                raise AssertionError("builder re-read the accepted baseline lock")
            return original_read_bytes(path)

        with self.patches(), mock.patch.object(
            Path, "read_bytes", guarded_read_bytes
        ):
            self.module.build_offline_apk(self.config, runner=FakeRunner())
        self.assertEqual(self.baseline.loads, 1)
        self.assertEqual(self.stage_locks, [self.lock, self.lock, self.lock])

    def test_cancel_cleans_transaction_without_publishing(self) -> None:
        def cancel(*args, **kwargs):
            raise KeyboardInterrupt()

        runner = FakeRunner()
        with self.patches(), mock.patch.object(
            self.module.RENDER, "apply_render_scale", cancel
        ), self.assertRaises(KeyboardInterrupt):
            self.module.build_offline_apk(self.config, runner=runner)
        self.assert_clean_failure()

    def test_cancel_immediately_after_either_final_link_rolls_back_the_pair(self) -> None:
        real_rename = self.module._rename_publication_handle_no_replace
        for target in (self.output, self.report):
            with self.subTest(target=target.name):
                def cancel_after_rename(staged, directory, destination):
                    real_rename(staged, directory, destination)
                    if directory.path / destination == target:
                        raise KeyboardInterrupt()

                with self.patches(), mock.patch.object(
                    self.module,
                    "_rename_publication_handle_no_replace",
                    cancel_after_rename,
                ), self.assertRaises(KeyboardInterrupt):
                    self.module.build_offline_apk(self.config, runner=FakeRunner())
                self.assert_clean_failure()
                self.baseline.inspected.clear()
                self.baseline.loads = 0
                self.baseline.asserted = 0
                self.baseline.diffed = 0
                self.stage_events.clear()
                self.stage_locks.clear()
                self.verify_events.clear()

    def test_preexisting_output_or_report_is_never_overwritten(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_bytes(b"old-output")
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "output APK already exists"
        ):
            self.module.build_offline_apk(self.config, runner=FakeRunner())
        self.assertEqual(self.output.read_bytes(), b"old-output")
        self.output.unlink()
        self.report.write_bytes(b"old-report")
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "report already exists"
        ):
            self.module.build_offline_apk(self.config, runner=FakeRunner())
        self.assertEqual(self.report.read_bytes(), b"old-report")

    def test_publication_race_preserves_competitor_and_leaves_no_report(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        runner = FakeRunner(race_output=self.output)
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "output APK already exists"
        ):
            self.module.build_offline_apk(self.config, runner=runner)
        self.assertEqual(self.output.read_bytes(), b"competitor")
        self.assertFalse(self.report.exists())

    def test_report_publication_race_rolls_back_our_output(self) -> None:
        self.report.parent.mkdir(parents=True, exist_ok=True)
        runner = FakeRunner(race_output=self.report)
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "report already exists"
        ):
            self.module.build_offline_apk(self.config, runner=runner)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.report.read_bytes(), b"competitor")

    def test_handle_cleanup_after_path_replacement_preserves_competitor(self) -> None:
        staged = self.module._stage_publication_file(
            None, b"ours", self.root, ".stage"
        )
        moved = self.root / "moved-owned.stage"
        staged.path.rename(moved)
        staged.path.write_bytes(b"competitor")
        self.module._cleanup_publication_staging(staged)
        self.assertEqual(staged.path.read_bytes(), b"competitor")
        self.assertFalse(moved.exists())

    def test_publication_staging_writes_the_original_handle_inode(self) -> None:
        with mock.patch.object(
            Path,
            "unlink",
            side_effect=AssertionError("mkstemp path was unlinked before writing"),
        ):
            staged = self.module._stage_publication_file(
                None, b"payload", self.root, ".stage"
            )
        self.assertEqual(
            self.module._hash_publication_handle(staged),
            hashlib.sha256(b"payload").hexdigest(),
        )
        self.module._cleanup_publication_staging(staged)
        self.assertFalse(staged.path.exists())

    def test_staging_name_replacement_before_identity_return_preserves_competitor(self) -> None:
        original_identity = self.module._identity
        raced: list[Path] = []

        def replace_before_identity(path: Path):
            candidate = Path(path)
            if not raced and candidate.name.endswith(".race.stage"):
                raced.append(candidate)
                candidate.unlink()
                candidate.write_bytes(b"competitor")
            return original_identity(candidate)

        with mock.patch.object(
            self.module, "_identity", replace_before_identity
        ), self.assertRaisesRegex(
            self.module.ApkBuildError, "publication staging identity changed"
        ):
            self.module._stage_publication_file(
                None, b"ours", self.root, ".race.stage"
            )
        self.assertEqual(len(raced), 1)
        self.assertEqual(raced[0].read_bytes(), b"competitor")

    def test_cancellation_after_final_path_replacement_preserves_competitor(self) -> None:
        real_rename = self.module._rename_publication_handle_no_replace
        for target in (self.output, self.report):
            with self.subTest(target=target.name):
                moved = target.with_name(target.name + ".owned-moved")

                def replace_then_cancel(staged, directory, destination):
                    real_rename(staged, directory, destination)
                    final = directory.path / destination
                    if final == target:
                        final.rename(moved)
                        final.write_bytes(b"competitor")
                        raise KeyboardInterrupt()

                with self.patches(), mock.patch.object(
                    self.module,
                    "_rename_publication_handle_no_replace",
                    replace_then_cancel,
                ), self.assertRaises(KeyboardInterrupt):
                    self.module.build_offline_apk(self.config, runner=FakeRunner())
                self.assertEqual(target.read_bytes(), b"competitor")
                self.assertFalse(moved.exists())
                target.unlink()
                self.baseline.inspected.clear()
                self.baseline.loads = 0
                self.baseline.asserted = 0
                self.baseline.diffed = 0
                self.stage_events.clear()
                self.stage_locks.clear()
                self.verify_events.clear()

    def test_destination_parent_identity_drift_rolls_back_without_publication(self) -> None:
        original = self.module._require_destination_directory_identity
        calls = 0

        def drift_after_staging(directory, label):
            nonlocal calls
            calls += 1
            if calls >= 3:
                raise self.module.ApkBuildError(
                    "destination parent identity changed"
                )
            return original(directory, label)

        with self.patches(), mock.patch.object(
            self.module,
            "_require_destination_directory_identity",
            drift_after_staging,
        ), self.assertRaisesRegex(
            self.module.ApkBuildError, "destination parent identity changed"
        ):
            self.module.build_offline_apk(self.config, runner=FakeRunner())
        self.assert_clean_failure()

    def test_destination_parent_reparse_is_rejected_before_baseline_work(self) -> None:
        original = self.module._open_destination_directory

        def reject_output_parent(path: Path, *, deny_delete: bool = False):
            if Path(path) == self.output.parent:
                raise self.module.ApkBuildError(
                    "output parent must not be a reparse point"
                )
            return original(path, deny_delete=deny_delete)

        with self.patches(), mock.patch.object(
            self.module,
            "_open_destination_directory",
            reject_output_parent,
        ), self.assertRaisesRegex(
            self.module.ApkBuildError, "output parent must not be a reparse point"
        ):
            self.module.build_offline_apk(self.config, runner=FakeRunner())
        self.assertEqual(self.baseline.loads, 0)
        self.assert_clean_failure()

    def test_transaction_root_is_rename_locked_and_removed_by_handle(self) -> None:
        self.work.mkdir(parents=True, exist_ok=True)
        transaction = self.module._create_owned_transaction(self.work)
        moved = transaction.path.with_name(transaction.path.name + ".moved")
        competitor = transaction.path / "competitor.txt"
        competitor.write_text("ours", encoding="utf-8")
        with self.assertRaises(OSError):
            transaction.path.rename(moved)
        self.module._clean_owned_transaction(transaction)
        self.assertFalse(transaction.path.exists())
        self.assertFalse(moved.exists())

    def test_signed_apk_hash_is_bound_through_final_inspection(self) -> None:
        self.baseline.mutate_after_final_inspect = True
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "signed APK changed after verification"
        ):
            self.module.build_offline_apk(self.config, runner=FakeRunner())
        self.assert_clean_failure()

    def test_final_active_offline_and_resource_hashes_are_both_bound(self) -> None:
        self.baseline.drift_final_devconfig = True
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "active offline method hash drifted"
        ):
            self.module.build_offline_apk(self.config, runner=FakeRunner())
        self.assert_clean_failure()
        self.baseline.drift_final_devconfig = False
        self.baseline.drift_final_resource = True
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "active resource method hash drifted"
        ):
            self.module.build_offline_apk(self.config, runner=FakeRunner())
        self.assert_clean_failure()

    def test_publication_rejects_bytes_changed_after_verification(self) -> None:
        original = self.module._stage_publication_file

        def mutate_before_stage(source, payload, parent, suffix):
            if source is not None and suffix == ".apk.stage":
                Path(source).write_bytes(Path(source).read_bytes() + b"late-race")
            return original(source, payload, parent, suffix)

        with self.patches(), mock.patch.object(
            self.module, "_stage_publication_file", mutate_before_stage
        ), self.assertRaisesRegex(
            self.module.ApkBuildError, "verified signed APK bytes changed"
        ):
            self.module.build_offline_apk(self.config, runner=FakeRunner())
        self.assert_clean_failure()

    def test_same_byte_source_replacement_is_detected_by_identity(self) -> None:
        runner = FakeRunner(race_source=self.base)
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "source APK identity changed"
        ):
            self.module.build_offline_apk(self.config, runner=runner)
        self.assert_clean_failure()

    def test_report_is_canonical_and_contains_no_private_paths_or_secret(self) -> None:
        with self.patches():
            report = self.module.build_offline_apk(self.config, runner=FakeRunner())
        payload = self.report.read_bytes()
        self.assertEqual(payload, self.module.canonical_json_bytes(report))
        text = payload.decode("utf-8")
        for private in (
            str(self.root),
            str(self.work),
            str(self.keystore),
            PASSWORD,
        ):
            self.assertNotIn(private, text)
        parsed = json.loads(text)
        self.assertEqual(
            set(parsed),
            {
                "aligned",
                "certificate_sha256",
                "full_resource_version",
                "output_sha256",
                "patch_order",
                "signature_schemes",
                "stage_reports",
                "verified",
            },
        )
        self.assertTrue(all("output_path" not in stage for stage in parsed["stage_reports"]))

    def test_non_ascii_work_directory_fails_closed(self) -> None:
        config = self.module.OfflineApkBuildConfig(
            source_apk=self.config.source_apk,
            baseline_lock=self.config.baseline_lock,
            output_apk=self.config.output_apk,
            report_path=self.config.report_path,
            work_dir=self.root / "工作",
            toolchain=self.config.toolchain,
            signing=self.config.signing,
        )
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "ASCII work directory"
        ):
            self.module.build_offline_apk(config, runner=FakeRunner())
        self.assert_clean_failure()

    def test_source_and_lock_symlinks_reach_baseline_gate_without_resolution(self) -> None:
        source_link = self.root / "source-link.apk"
        lock_link = self.root / "lock-link.json"
        try:
            source_link.symlink_to(self.base)
            lock_link.symlink_to(self.lock_path)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        source_config = self.module.OfflineApkBuildConfig(
            source_apk=source_link,
            baseline_lock=self.lock_path,
            output_apk=self.output,
            report_path=self.report,
            work_dir=self.work,
            toolchain=self.toolchain,
            signing=self.signing,
        )
        original_inspect = self.baseline.inspect_apk

        def reject_source(apk, toolchain, *, runner):
            self.assertEqual(Path(apk), source_link.absolute())
            self.assertTrue(Path(apk).is_symlink())
            raise RuntimeError("source symlink rejected")

        self.baseline.inspect_apk = reject_source
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "source symlink rejected"
        ):
            self.module.build_offline_apk(source_config, runner=FakeRunner())
        self.baseline.inspect_apk = original_inspect

        lock_config = self.module.OfflineApkBuildConfig(
            source_apk=self.base,
            baseline_lock=lock_link,
            output_apk=self.output,
            report_path=self.report,
            work_dir=self.work,
            toolchain=self.toolchain,
            signing=self.signing,
        )
        original_load = self.baseline.load_base_lock

        def reject_lock(path):
            self.assertEqual(Path(path), lock_link.absolute())
            self.assertTrue(Path(path).is_symlink())
            raise RuntimeError("lock symlink rejected")

        self.baseline.load_base_lock = reject_lock
        with self.patches(), self.assertRaisesRegex(
            self.module.ApkBuildError, "lock symlink rejected"
        ):
            self.module.build_offline_apk(lock_config, runner=FakeRunner())
        self.baseline.load_base_lock = original_load

    def test_input_paths_are_not_resolved_before_the_baseline_gate(self) -> None:
        original_resolve = Path.resolve

        def guarded_resolve(path: Path, *args, **kwargs):
            if Path(path) in {
                self.base,
                self.lock_path,
                self.output,
                self.report,
            }:
                raise AssertionError("security-sensitive path was resolved")
            return original_resolve(path, *args, **kwargs)

        with self.patches(), mock.patch.object(Path, "resolve", guarded_resolve):
            self.module.build_offline_apk(self.config, runner=FakeRunner())

    def test_mocked_broken_output_and_report_links_are_refused_lexically(self) -> None:
        real_resolve = Path.resolve
        real_lexists = os.path.lexists

        for field_name, message in (
            ("output_apk", "output APK already exists"),
            ("report_path", "report already exists"),
        ):
            with self.subTest(field=field_name):
                destination = getattr(self.config, field_name)
                target = self.root / f"{field_name}-link-target"

                def simulate_old_resolve(path: Path, *args, **kwargs):
                    if Path(path) == destination:
                        return target
                    return real_resolve(path, *args, **kwargs)

                def simulate_broken_link(path):
                    if Path(path) == destination:
                        return True
                    return real_lexists(path)

                with self.patches(), mock.patch.object(
                    Path, "resolve", simulate_old_resolve
                ), mock.patch.object(
                    self.module.os.path, "lexists", simulate_broken_link
                ), self.assertRaisesRegex(self.module.ApkBuildError, message):
                    self.module.build_offline_apk(self.config, runner=FakeRunner())
                self.assertFalse(target.exists())

    def test_mocked_windows_reparse_source_and_lock_are_rejected_without_skip(self) -> None:
        accepted_lock = client_patch_path('offline-android/base-lock.json')
        real_lstat = Path.lstat

        def build_config(*, source: Path, lock: Path):
            return self.module.OfflineApkBuildConfig(
                source_apk=source,
                baseline_lock=lock,
                output_apk=self.output,
                report_path=self.report,
                work_dir=self.work,
                toolchain=self.toolchain,
                signing=self.signing,
            )

        def reparse_source(path: Path):
            if Path(path) == self.base:
                return types.SimpleNamespace(
                    st_mode=stat.S_IFREG | 0o600,
                    st_file_attributes=0x400,
                )
            return real_lstat(path)

        with mock.patch.dict(os.environ, {PASSWORD_ENV: PASSWORD}), mock.patch.object(
            Path, "lstat", reparse_source
        ), self.assertRaisesRegex(self.module.ApkBuildError, "regular non-symlink"):
            self.module.build_offline_apk(
                build_config(source=self.base, lock=accepted_lock),
                runner=FakeRunner(),
            )

        def reparse_lock(path: Path):
            if Path(path) == accepted_lock:
                return types.SimpleNamespace(
                    st_mode=stat.S_IFREG | 0o600,
                    st_file_attributes=0x400,
                )
            return real_lstat(path)

        with mock.patch.dict(os.environ, {PASSWORD_ENV: PASSWORD}), mock.patch.object(
            Path, "lstat", reparse_lock
        ), self.assertRaisesRegex(self.module.ApkBuildError, "base lock"):
            self.module.build_offline_apk(
                build_config(source=self.base, lock=accepted_lock),
                runner=FakeRunner(),
            )

    def test_source_has_no_dependency_on_work_or_repoint_artifacts(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn('"work/', source)
        self.assertNotIn("repoint", source.casefold())


if __name__ == "__main__":
    unittest.main()

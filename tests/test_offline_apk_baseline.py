from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = client_patch_path('offline-android/apk_baseline.py')
LOCK_PATH = client_patch_path('offline-android/base-lock.json')

TARGET_SWF = "assets/worldflipper_android_release.swf"
CERTIFICATE_SHA256 = (
    "a40da80a59d170caa950cf15c18c454d47a39b26989d8b640ecd745ba71bf5dc"
)
OFFLINE_IDENTITIES = {
    "DevConfig_individual/DevConfig_individual": (
        "pinball.config.core:DevConfig_individual/DevConfig_individual"
    ),
    "boot_ffc6#$script364/$init": "boot_ffc6#$script364/$init",
    "InitializeDummyRemote/logicAssetLoadedHandler": (
        "pinball.remote.initialize:InitializeDummyRemote/logicAssetLoadedHandler"
    ),
    "DummyRemote/debugUnlinkTwitter": (
        "pinball.context.remote.dummy:DummyRemote/debugUnlinkTwitter"
    ),
}


def load_module():
    name = "offline_apk_baseline_under_test"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, require_external_source(MODULE_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


module = load_module()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class FakeIndex:
    def __init__(self, code_by_identity: dict[str, bytes]) -> None:
        self.code_by_identity = code_by_identity
        self.requested: list[str] = []

    def require_ref(self, identity: str):
        self.requested.append(identity)
        if identity not in self.code_by_identity:
            raise RuntimeError(f"unexpected or ambiguous identity: {identity}")
        return SimpleNamespace(code=self.code_by_identity[identity])


class FakeRunner:
    def __init__(
        self,
        *,
        package: str = "com.leiting.wf",
        version_code: str = "1008001",
        version_name: str = "1.8.1",
        permission_count: int = 1,
        certificate: str = CERTIFICATE_SHA256,
    ) -> None:
        self.package = package
        self.version_code = version_code
        self.version_name = version_name
        self.permission_count = permission_count
        self.certificate = certificate
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv, **kwargs):
        command = tuple(str(value) for value in argv)
        self.calls.append(command)
        if "badging" in command:
            output = (
                f"package: name='{self.package}' versionCode='{self.version_code}' "
                f"versionName='{self.version_name}'\n"
            )
        elif "permissions" in command:
            permission = (
                "uses-permission: "
                "name='android.permission.MANAGE_EXTERNAL_STORAGE'\n"
            )
            output = f"package: {self.package}\n" + permission * self.permission_count
        elif "--print-certs" in command:
            output = (
                "Verified using v1 scheme (JAR signing): true\n"
                "Verified using v2 scheme (APK Signature Scheme v2): true\n"
                "Verified using v3 scheme (APK Signature Scheme v3): true\n"
                f"Signer #1 certificate SHA-256 digest: {self.certificate}\n"
            )
        else:
            raise AssertionError(f"unexpected command: {command}")
        return subprocess.CompletedProcess(command, 0, output.encode("utf-8"), b"")


class TestBaseLock(unittest.TestCase):
    def test_known_base_contract_is_locked(self) -> None:
        lock = module.load_base_lock(LOCK_PATH)
        self.assertEqual(
            lock.source_apk_sha256,
            "4f6884f33641788108c0522c7c70036c63ba530e1fdb183105b3cd395bdd66f6",
        )
        self.assertEqual(
            lock.source_swf_sha256,
            "08187f538703aecadce264b7bd5e085411f8e3aedb5f48adf2cf035a100f550d",
        )
        self.assertEqual(
            lock.manifest_sha256,
            "2823fbfad46bfcdc34c8df77b3f2ed2acf9f5812b8b61644304cc6d11109d6f9",
        )
        self.assertEqual(
            dict(lock.dex_sha256),
            {
                "classes.dex": (
                    "c12d119d425f0e8f35623dbac07296e00a8b9e60620c4f371b307121b389c043"
                ),
                "classes2.dex": (
                    "b310c77febb7da0d2908b32274391ae39226a9df334e0d7d7f51b5a081bc539b"
                ),
            },
        )
        self.assertEqual(
            lock.native_aggregate_sha256,
            "a42f92e417199a9ac99ca4f63efa0db487019bdf1220a86301fcfa0a4118f995",
        )
        self.assertEqual(
            dict(lock.offline_method_sha256),
            {
                "DevConfig_individual/DevConfig_individual": (
                    "ac87a4744507d4fa47fa46af99290a1aec0c230a5338e317cbeeb7c80badc139"
                ),
                "boot_ffc6#$script364/$init": (
                    "afcb8c8602158db0a64ba1560f36875166004283bfe6a04ad9eeaf49ee3714b2"
                ),
                "InitializeDummyRemote/logicAssetLoadedHandler": (
                    "d17591dc3c793faaa02c1080968b0bb30384b968f70dbe9363d8860fa30fcd3c"
                ),
                "DummyRemote/debugUnlinkTwitter": (
                    "45bc87da473d018f700f349fda2c743a6d11509cc236390584dccf2ac7d75a38"
                ),
            },
        )

    def test_lock_requires_canonical_json_and_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            compact = root / "compact.json"
            compact.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(module.ApkBuildError, "canonical"):
                module.load_base_lock(compact)

            duplicate = root / "duplicate.json"
            original = LOCK_PATH.read_text(encoding="utf-8")
            duplicate.write_text(
                original.replace("{\n", '{\n  "schema_version": 4,\n', 1),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(module.ApkBuildError, "duplicate JSON key"):
                module.load_base_lock(duplicate)

    def test_lock_rejects_hardlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "lock.json"
            target.write_bytes(LOCK_PATH.read_bytes())
            hardlink = root / "hardlink.json"
            os.link(target, hardlink)
            with self.assertRaisesRegex(module.ApkBuildError, "multiple hard links"):
                module.load_base_lock(hardlink)

    def test_lock_rejects_symlink_and_windows_reparse_metadata(self) -> None:
        fixtures = (
            SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0),
            SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400),
        )
        for metadata in fixtures:
            with self.subTest(metadata=metadata), mock.patch.object(
                module.Path, "lstat", return_value=metadata
            ), self.assertRaisesRegex(module.ApkBuildError, "non-symlink"):
                module.load_base_lock(Path("synthetic-lock.json"))


class ApkFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.apk = self.root / "fixture.apk"
        self.manifest = b"binary manifest fixture"
        self.swf = b"FWS fake active SWF; dormant RealRemote http strings"
        self.dex = {
            "classes.dex": b"dex one",
            "classes2.dex": b"dex two",
        }
        self.native = {
            "lib/arm64-v8a/libCore.so": b"native core",
            "lib/arm64-v8a/libSocketHelper.so": b"native socket",
        }
        self.method_code = {
            identity: (f"active:{key}").encode("utf-8")
            for key, identity in OFFLINE_IDENTITIES.items()
        }
        self.index = FakeIndex(self.method_code)
        self.runner = FakeRunner()
        self.toolchain = SimpleNamespace(
            aapt=self.root / "aapt.exe",
            apksigner=self.root / "apksigner.exe",
            java=self.root / "java.exe",
            ffdec=self.root / "ffdec.jar",
        )
        self._write_apk(self.apk)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_apk(
        self,
        path: Path,
        *,
        swf: bytes | None = None,
        dex: dict[str, bytes] | None = None,
        air: bytes = b"AIR metadata",
        signatures: dict[str, bytes] | None = None,
        duplicate: str | None = None,
        symlink_member: str | None = None,
    ) -> None:
        members: list[tuple[str, bytes]] = [
            ("AndroidManifest.xml", self.manifest),
            (TARGET_SWF, self.swf if swf is None else swf),
            *((name, data) for name, data in (self.dex if dex is None else dex).items()),
            *((name, data) for name, data in self.native.items()),
            ("META-INF/AIR/application.xml", air),
        ]
        signer_files = signatures or {
            "META-INF/MANIFEST.MF": b"manifest signer",
            "META-INF/CERT.SF": b"sf signer",
            "META-INF/CERT.RSA": b"rsa signer",
        }
        members.extend(signer_files.items())
        with zipfile.ZipFile(path, "w", allowZip64=True) as archive:
            for name, data in members:
                archive.writestr(name, data)
            if duplicate is not None:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr(duplicate, b"duplicate")
            if symlink_member is not None:
                info = zipfile.ZipInfo(symlink_member)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, b"classes.dex")

    def inspect(self, *, runner=None, index=None):
        selected_runner = self.runner if runner is None else runner
        selected_index = self.index if index is None else index
        with mock.patch.object(
            module.ABC_METHODS,
            "index_swf_methods",
            return_value=selected_index,
        ):
            return module.inspect_apk(
                self.apk,
                self.toolchain,
                runner=selected_runner,
            )


class TestApkInspection(ApkFixture):
    def test_inspect_apk_records_exact_contract_and_active_method_identities(self) -> None:
        report = self.inspect()
        self.assertEqual("com.leiting.wf", report.package_name)
        self.assertEqual("1008001", report.version_code)
        self.assertEqual("1.8.1", report.version_name)
        self.assertEqual(1, report.manage_external_storage_count)
        self.assertEqual(1, report.target_swf_count)
        self.assertEqual(CERTIFICATE_SHA256, report.input_certificate_sha256)
        self.assertEqual(sha256(self.apk.read_bytes()), report.apk_sha256)
        self.assertEqual(sha256(self.swf), report.swf_sha256)
        self.assertEqual(sha256(self.manifest), report.manifest_sha256)
        self.assertEqual(
            {name: sha256(data) for name, data in self.dex.items()},
            dict(report.dex_sha256),
        )
        self.assertEqual(
            {
                key: sha256(self.method_code[identity])
                for key, identity in OFFLINE_IDENTITIES.items()
            },
            dict(report.offline_method_sha256),
        )
        self.assertEqual(set(OFFLINE_IDENTITIES.values()), set(self.index.requested))
        self.assertFalse(any("RealRemote" in name for name in self.index.requested))

    def test_native_aggregate_is_name_size_and_hash_bound(self) -> None:
        report = self.inspect()
        aggregate = hashlib.sha256()
        for name in sorted(self.native):
            value = self.native[name]
            aggregate.update(
                f"{name}\0{len(value)}\0{sha256(value)}\n".encode("utf-8")
            )
        self.assertEqual(aggregate.hexdigest(), report.native_aggregate_sha256)

    def test_wrong_package_or_version_is_rejected(self) -> None:
        runners = (
            FakeRunner(package="com.example.wf"),
            FakeRunner(version_code="1008002"),
            FakeRunner(version_name="1.8.2"),
        )
        for runner in runners:
            with self.subTest(runner=runner), self.assertRaises(
                module.ApkBuildError
            ):
                self.inspect(runner=runner)

    def test_manage_external_storage_must_appear_exactly_once(self) -> None:
        for count in (0, 2):
            with self.subTest(count=count), self.assertRaisesRegex(
                module.ApkBuildError, "MANAGE_EXTERNAL_STORAGE"
            ):
                self.inspect(runner=FakeRunner(permission_count=count))

    def test_main_swf_must_appear_exactly_once(self) -> None:
        self._write_apk(self.apk, duplicate=TARGET_SWF)
        with self.assertRaisesRegex(module.ApkBuildError, "duplicate ZIP members"):
            self.inspect()

        without_swf = self.root / "without.apk"
        with zipfile.ZipFile(self.apk, "r") as source, zipfile.ZipFile(
            without_swf, "w"
        ) as output:
            seen = set()
            for info in source.infolist():
                if info.filename == TARGET_SWF or info.filename in seen:
                    continue
                seen.add(info.filename)
                output.writestr(info, source.read(info))
        self.apk = without_swf
        with self.assertRaisesRegex(module.ApkBuildError, "main SWF"):
            self.inspect()

    def test_zip_symlink_member_is_rejected(self) -> None:
        self._write_apk(self.apk, symlink_member="assets/link.dex")
        with self.assertRaisesRegex(module.ApkBuildError, "symlink"):
            self.inspect()

    def test_casefold_colliding_zip_members_are_rejected_during_inspection(self) -> None:
        self._write_apk(
            self.apk,
            signatures={
                "META-INF/CERT.RSA": b"canonical signer",
                "meta-inf/cert.rsa": b"case-colliding signer",
            },
        )
        with self.assertRaisesRegex(
            module.ApkBuildError, "case-insensitive ZIP member collision"
        ):
            self.inspect()

    def test_apksigner_fingerprint_is_recorded_but_not_pinned_to_input(self) -> None:
        replacement = "1" * 64
        report = self.inspect(runner=FakeRunner(certificate=replacement))
        self.assertEqual(replacement, report.input_certificate_sha256)

    def test_tool_failure_is_closed_and_does_not_expose_absolute_apk_path(self) -> None:
        def failing_runner(argv, **kwargs):
            raise subprocess.CalledProcessError(
                7,
                argv,
                output=f"failed {self.apk}".encode(),
                stderr=f"bad {self.apk}".encode(),
            )

        with self.assertRaises(module.ApkBuildError) as raised:
            self.inspect(runner=failing_runner)
        self.assertNotIn(str(self.root), str(raised.exception))


class TestLockedBaseline(unittest.TestCase):
    def setUp(self) -> None:
        self.lock = module.load_base_lock(LOCK_PATH)
        self.report = module.ApkBaselineReport(
            apk_sha256=self.lock.source_apk_sha256,
            swf_sha256=self.lock.source_swf_sha256,
            package_name="com.leiting.wf",
            version_code="1008001",
            version_name="1.8.1",
            manifest_sha256=self.lock.manifest_sha256,
            dex_sha256=dict(self.lock.dex_sha256),
            native_aggregate_sha256=self.lock.native_aggregate_sha256,
            offline_method_sha256=dict(self.lock.offline_method_sha256),
            manage_external_storage_count=1,
            target_swf_count=1,
            input_certificate_sha256=CERTIFICATE_SHA256,
        )

    def test_matching_report_is_returned_and_input_signer_is_not_required(self) -> None:
        changed_signer = module.ApkBaselineReport(
            **{
                **self.report.__dict__,
                "input_certificate_sha256": "2" * 64,
            }
        ) if hasattr(self.report, "__dict__") else module.ApkBaselineReport(
            apk_sha256=self.report.apk_sha256,
            swf_sha256=self.report.swf_sha256,
            package_name=self.report.package_name,
            version_code=self.report.version_code,
            version_name=self.report.version_name,
            manifest_sha256=self.report.manifest_sha256,
            dex_sha256=self.report.dex_sha256,
            native_aggregate_sha256=self.report.native_aggregate_sha256,
            offline_method_sha256=self.report.offline_method_sha256,
            manage_external_storage_count=1,
            target_swf_count=1,
            input_certificate_sha256="2" * 64,
        )
        self.assertIs(
            changed_signer,
            module.assert_locked_baseline(changed_signer, self.lock),
        )

    def test_active_devconfig_drift_is_rejected_while_dormant_strings_are_irrelevant(self) -> None:
        hashes = dict(self.report.offline_method_sha256)
        hashes["DevConfig_individual/DevConfig_individual"] = "f" * 64
        drifted = module.ApkBaselineReport(
            apk_sha256=self.report.apk_sha256,
            swf_sha256=self.report.swf_sha256,
            package_name=self.report.package_name,
            version_code=self.report.version_code,
            version_name=self.report.version_name,
            manifest_sha256=self.report.manifest_sha256,
            dex_sha256=self.report.dex_sha256,
            native_aggregate_sha256=self.report.native_aggregate_sha256,
            offline_method_sha256=hashes,
            manage_external_storage_count=1,
            target_swf_count=1,
            input_certificate_sha256=self.report.input_certificate_sha256,
        )
        with self.assertRaisesRegex(module.ApkBuildError, "offline method"):
            module.assert_locked_baseline(drifted, self.lock)

    def test_every_locked_byte_contract_rejects_drift(self) -> None:
        fields = (
            "apk_sha256",
            "swf_sha256",
            "manifest_sha256",
            "native_aggregate_sha256",
        )
        for field in fields:
            values = {
                name: getattr(self.report, name)
                for name in self.report.__dataclass_fields__
            }
            values[field] = "f" * 64
            with self.subTest(field=field), self.assertRaises(
                module.ApkBuildError
            ):
                module.assert_locked_baseline(
                    module.ApkBaselineReport(**values), self.lock
                )

        dex = dict(self.report.dex_sha256)
        dex["classes.dex"] = "f" * 64
        values = {
            name: getattr(self.report, name)
            for name in self.report.__dataclass_fields__
        }
        values["dex_sha256"] = dex
        with self.assertRaisesRegex(module.ApkBuildError, "DEX"):
            module.assert_locked_baseline(module.ApkBaselineReport(**values), self.lock)


class TestAllowedMemberDiff(ApkFixture):
    def test_allowed_to_change_is_exact_and_preserves_meta_inf_air(self) -> None:
        self.assertTrue(module.allowed_to_change(TARGET_SWF))
        for member in (
            "META-INF/MANIFEST.MF",
            "META-INF/CERT.SF",
            "META-INF/CERT.RSA",
            "META-INF/CERT.DSA",
            "META-INF/CERT.EC",
        ):
            self.assertTrue(module.allowed_to_change(member), member)
        for member in (
            "classes.dex",
            "META-INF/AIR/MANIFEST.MF",
            "META-INF/AIR/CERT.RSA",
            "META-INF/sub/CERT.SF",
            "META-INF/CERT.TXT",
            "meta-inf/CERT.RSA",
            "META-INF/cert.rsa",
            "META-INF/MANIFEST.mf",
        ):
            self.assertFalse(module.allowed_to_change(member), member)

    def test_only_main_swf_and_top_level_signatures_may_change(self) -> None:
        output = self.root / "allowed.apk"
        self._write_apk(
            output,
            swf=b"patched SWF",
            signatures={
                "META-INF/MANIFEST.MF": b"new manifest",
                "META-INF/NEW.SF": b"new sf",
                "META-INF/NEW.RSA": b"new rsa",
            },
        )
        module.assert_allowed_member_diff(self.apk, output)

    def test_changed_dex_is_rejected(self) -> None:
        output = self.root / "changed-dex.apk"
        changed = dict(self.dex)
        changed["classes.dex"] = b"changed"
        self._write_apk(output, dex=changed)
        with self.assertRaisesRegex(
            module.ApkBuildError, "unexpected member drift: classes.dex"
        ):
            module.assert_allowed_member_diff(self.apk, output)

    def test_meta_inf_air_must_be_preserved_byte_for_byte(self) -> None:
        output = self.root / "changed-air.apk"
        self._write_apk(output, air=b"changed AIR metadata")
        with self.assertRaisesRegex(
            module.ApkBuildError,
            "unexpected member drift: META-INF/AIR/application.xml",
        ):
            module.assert_allowed_member_diff(self.apk, output)

        missing = self.root / "missing-air.apk"
        with zipfile.ZipFile(self.apk, "r") as source, zipfile.ZipFile(
            missing, "w"
        ) as target:
            for info in source.infolist():
                if info.filename != "META-INF/AIR/application.xml":
                    target.writestr(info, source.read(info))
        with self.assertRaisesRegex(
            module.ApkBuildError, "non-signature APK member set changed"
        ):
            module.assert_allowed_member_diff(self.apk, missing)

    def test_duplicate_and_symlink_members_are_rejected_in_either_apk(self) -> None:
        duplicate = self.root / "duplicate.apk"
        self._write_apk(duplicate, duplicate="classes.dex")
        with self.assertRaisesRegex(module.ApkBuildError, "duplicate ZIP members"):
            module.assert_allowed_member_diff(self.apk, duplicate)

        symlink = self.root / "symlink.apk"
        self._write_apk(symlink, symlink_member="assets/link")
        with self.assertRaisesRegex(module.ApkBuildError, "symlink"):
            module.assert_allowed_member_diff(self.apk, symlink)

    def test_casefold_collisions_are_rejected_on_both_diff_sides(self) -> None:
        colliding_base = self.root / "colliding-base.apk"
        self._write_apk(
            colliding_base,
            signatures={
                "META-INF/CERT.RSA": b"canonical signer",
                "meta-inf/cert.rsa": b"case-colliding signer",
            },
        )
        with self.assertRaisesRegex(
            module.ApkBuildError, "case-insensitive ZIP member collision"
        ):
            module.assert_allowed_member_diff(colliding_base, self.apk)

        colliding_output = self.root / "colliding-output.apk"
        self._write_apk(
            colliding_output,
            signatures={
                "META-INF/CERT.RSA": b"canonical signer",
                "meta-inf/cert.rsa": b"case-colliding signer",
            },
        )
        with self.assertRaisesRegex(
            module.ApkBuildError, "case-insensitive ZIP member collision"
        ):
            module.assert_allowed_member_diff(self.apk, colliding_output)


if __name__ == "__main__":
    unittest.main()

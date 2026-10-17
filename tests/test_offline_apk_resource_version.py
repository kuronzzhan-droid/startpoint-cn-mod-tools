from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    client_patch_path('offline-android/resource_version_pcode.py')
)

RESOURCE_CLASS = "pinball.config.core.DevConfig"
RESOURCE_METHOD = "boot_ffc6#$script364/$init"
DUMMY_METHOD = (
    "pinball.context.remote.dummy:DummyRemote/debugUnlinkTwitter"
)
DUMMY_LOCK_KEY = "DummyRemote/debugUnlinkTwitter"
SOURCE_VERSION = "1.4.54"
TARGET_VERSION = "1.4.196"


def load_module():
    require_external_source(MODULE_PATH)
    spec = importlib.util.spec_from_file_location(
        "offline_resource_version_pcode", require_external_source(MODULE_PATH)
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def resource_block(
    version: str = SOURCE_VERSION,
    *,
    string_opcode: str = "pushstring",
    bool_opcode: str = "pushtrue",
) -> str:
    return (
        "method\n"
        "   name null\n"
        '   returns QName(PackageNamespace(""),"void")\n'
        "\n"
        "   body\n"
        "      maxstack 2\n"
        "      localcount 1\n"
        "      initscopedepth 1\n"
        "      maxscopedepth 3\n"
        "\n"
        "      code\n"
        "         getlocal0\n"
        "         pushscope\n"
        "         getglobalscope\n"
        '         getlex QName(PackageNamespace(""),"Object")\n'
        "         pushscope\n"
        '         getlex QName(PackageNamespace(""),"Object")\n'
        "         newclass 364\n"
        "         popscope\n"
        '         initproperty QName(PackageNamespace("pinball.config.core"),"DevConfig")\n'
        '         getlex QName(PackageNamespace("pinball.config.core"),"DevConfig")\n'
        f"         {bool_opcode}\n"
        '         initproperty QName(PackageNamespace(""),"isFullPackage")\n'
        '         getlex QName(PackageNamespace("pinball.config.core"),"DevConfig")\n'
        f'         {string_opcode} "{version}"\n'
        '         initproperty QName(PackageNamespace(""),"fullResourceVersion")\n'
        '         getlex QName(PackageNamespace("pinball.config.core"),"DevConfig")\n'
        "         pushtrue\n"
        '         initproperty QName(PackageNamespace(""),"sdkDummy")\n'
        "         returnvoid\n"
        "      end ; code\n"
        "   end ; body\n"
        "end ; method\n"
    )


def unrelated_method() -> str:
    return (
        "method\n"
        "   name null\n"
        '   returns QName(PackageNamespace(""),"void")\n'
        "   body\n"
        "      maxstack 1\n"
        "      localcount 1\n"
        "      initscopedepth 1\n"
        "      maxscopedepth 1\n"
        "      code\n"
        "         getlocal0\n"
        "         pushscope\n"
        "         returnvoid\n"
        "      end ; code\n"
        "   end ; body\n"
        "end ; method\n"
    )


class TestResourceVersionModuleExists(unittest.TestCase):
    def test_task10_resource_version_module_exists(self) -> None:
        require_external_source(MODULE_PATH)


@unittest.skipUnless(MODULE_PATH.is_file(), "external client-patch integration source unavailable")
class TestResourceVersionPcode(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.before = resource_block()
        self.after = resource_block(TARGET_VERSION)

    def test_exact_identity_and_release_versions_are_exposed(self) -> None:
        self.assertEqual(RESOURCE_CLASS, self.module.RESOURCE_CLASS)
        self.assertEqual(RESOURCE_METHOD, self.module.RESOURCE_METHOD)
        self.assertEqual(DUMMY_METHOD, self.module.DUMMY_REMOTE_METHOD)
        self.assertEqual(SOURCE_VERSION, self.module.SOURCE_VERSION)
        self.assertEqual(TARGET_VERSION, self.module.TARGET_VERSION)
        self.assertEqual("full-resource-version", self.module.RESOURCE_SITE_ID)

    def test_replaces_only_one_expected_value_and_preserves_full_package(self) -> None:
        output = self.module.patch_resource_version(self.before)
        self.assertEqual(self.after, output)
        self.assertEqual(output.count('pushstring "1.4.196"'), 1)
        self.assertNotIn('pushstring "1.4.54"', output)
        self.assertIn(
            'pushtrue\n         initproperty QName(PackageNamespace(""),"isFullPackage")',
            output,
        )
        self.assertIsNone(
            self.module.verify_resource_version(output, expected=TARGET_VERSION)
        )

    def test_plan_style_opcode_case_is_preserved(self) -> None:
        before = resource_block(string_opcode="PushString", bool_opcode="PushTrue")
        output = self.module.patch_resource_version(before)
        self.assertEqual(output.count('PushString "1.4.196"'), 1)
        self.assertNotIn('PushString "1.4.54"', output)
        self.assertIn(
            'PushTrue\n         initproperty QName(PackageNamespace(""),"isFullPackage")',
            output,
        )

    def test_zero_two_source_and_existing_target_are_rejected(self) -> None:
        cases = {
            "zero-source": self.before.replace(SOURCE_VERSION, "1.4.53"),
            "two-source": self.before.replace(
                "         returnvoid\n",
                '         pushstring "1.4.54"\n         returnvoid\n',
            ),
            "existing-target": self.before.replace(
                "         returnvoid\n",
                '         pushstring "1.4.196"\n         returnvoid\n',
            ),
        }
        for name, block in cases.items():
            with self.subTest(case=name), self.assertRaises(
                self.module.ResourceVersionError
            ):
                self.module.patch_resource_version(block)

    def test_idempotence_and_non_release_versions_are_rejected(self) -> None:
        with self.assertRaises(self.module.ResourceVersionError):
            self.module.patch_resource_version(self.after)
        for source, target in (
            ("1.4.53", TARGET_VERSION),
            (SOURCE_VERSION, "1.4.197"),
            ('1.4.54"\npushfalse', TARGET_VERSION),
        ):
            with self.subTest(source=source, target=target), self.assertRaises(
                self.module.ResourceVersionError
            ):
                self.module.patch_resource_version(
                    self.before, source=source, target=target
                )

    def test_is_full_package_false_missing_or_reordered_is_rejected(self) -> None:
        false_block = self.before.replace(
            "         pushtrue\n"
            '         initproperty QName(PackageNamespace(""),"isFullPackage")',
            "         pushfalse\n"
            '         initproperty QName(PackageNamespace(""),"isFullPackage")',
            1,
        )
        missing = self.before.replace("isFullPackage", "notFullPackage", 1)
        reordered = self.before.replace(
            '         pushstring "1.4.54"\n'
            '         initproperty QName(PackageNamespace(""),"fullResourceVersion")',
            '         initproperty QName(PackageNamespace(""),"fullResourceVersion")\n'
            '         pushstring "1.4.54"',
            1,
        )
        for name, block in (
            ("false", false_block),
            ("missing", missing),
            ("reordered", reordered),
        ):
            with self.subTest(case=name), self.assertRaises(
                self.module.ResourceVersionError
            ):
                self.module.patch_resource_version(block)

    def test_verify_requires_exact_expected_value_and_one_property(self) -> None:
        with self.assertRaises(self.module.ResourceVersionError):
            self.module.verify_resource_version(
                self.after, expected=SOURCE_VERSION
            )
        duplicate = self.after.replace(
            "         returnvoid\n",
            '         pushstring "1.4.196"\n'
            '         initproperty QName(PackageNamespace(""),"fullResourceVersion")\n'
            "         returnvoid\n",
        )
        with self.assertRaises(self.module.ResourceVersionError):
            self.module.verify_resource_version(
                duplicate, expected=TARGET_VERSION
            )

    def test_exported_initializer_extraction_is_unique(self) -> None:
        exported = unrelated_method() + self.before + unrelated_method()
        self.assertEqual(
            self.before,
            self.module._extract_resource_initializer(exported),
        )
        for invalid in (
            unrelated_method(),
            self.before + self.before,
            self.before.replace("fullResourceVersion", "other", 1),
        ):
            with self.assertRaises(self.module.ResourceVersionError):
                self.module._extract_resource_initializer(invalid)

    def test_canonical_pcode_only_normalizes_offset_label_names(self) -> None:
        left = self.before.replace(
            "         returnvoid",
            "         jump ofs00aa\n   ofs00aa:\n         returnvoid",
        )
        right = self.before.replace(
            "         returnvoid",
            "         jump ofs9F00\n   ofs9F00:\n         returnvoid",
        )
        self.assertEqual(
            self.module.canonical_pcode(left),
            self.module.canonical_pcode(right),
        )

    def test_source_has_no_runtime_dependency_on_work_tree(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("work/seris", source.lower())
        self.assertNotIn("work\\seris", source.lower())
        self.assertNotIn("refresh-lock", source.lower())


class FakeRef:
    def __init__(self, method_name: str, body_index: int, code: bytes) -> None:
        self.method_name = method_name
        self.body_index = body_index
        self.method_info_index = body_index + 7000
        self.code = code


class FakeIndex:
    def __init__(self, state: dict[str, str], calls: list[str]) -> None:
        self.state = state
        self.calls = calls

    def require_ref(self, method_name: str) -> FakeRef:
        self.calls.append(method_name)
        if method_name not in self.state:
            raise AssertionError(f"unknown fake method {method_name}")
        names = list(self.state)
        return FakeRef(
            method_name,
            names.index(method_name),
            self.state[method_name].encode("utf-8"),
        )


class FakeFfdecRunner:
    def __init__(
        self,
        module,
        source: Path,
        initial: dict[str, str],
        *,
        drift_dummy_after_replace: bool = False,
        drift_reopen_full_package: bool = False,
    ) -> None:
        self.module = module
        self.states: dict[Path, dict[str, str]] = {
            source.resolve(): dict(initial)
        }
        self.calls: list[tuple[str, tuple[str, ...], Path, str]] = []
        self.require_ref_calls: list[str] = []
        self.drift_dummy_after_replace = drift_dummy_after_replace
        self.drift_reopen_full_package = drift_reopen_full_package
        self.export_count = 0

    def index(self, path: Path) -> FakeIndex:
        return FakeIndex(self._state(path), self.require_ref_calls)

    def _state(self, path: Path) -> dict[str, str]:
        resolved = Path(path).resolve()
        if resolved not in self.states:
            self.states[resolved] = json.loads(
                resolved.read_text(encoding="utf-8")
            )
        return self.states[resolved]

    def __call__(self, command, *, cwd: Path, env: dict[str, str], timeout: int):
        del timeout
        argv = tuple(str(part) for part in command)
        kind = "replace" if "-replace" in argv else "export"
        self.calls.append((kind, argv, Path(cwd), env["APPDATA"]))
        if kind == "replace":
            position = argv.index("-replace")
            source = Path(argv[position + 1]).resolve()
            destination = Path(argv[position + 2]).resolve()
            self.assert_replace_class(argv[position + 3])
            replacement = Path(argv[position + 4]).read_text(encoding="utf-8")
            body_index = int(argv[position + 5])
            state = dict(self._state(source))
            method_name = list(state)[body_index]
            state[method_name] = replacement
            if self.drift_dummy_after_replace:
                state[DUMMY_METHOD] = "drifted-dummy-abc"
            destination.write_text(
                json.dumps(state, sort_keys=True), encoding="utf-8"
            )
            self.states[destination] = state
        else:
            self.export_count += 1
            position = argv.index("-export")
            export_root = Path(argv[position + 2])
            swf = Path(argv[position + 3]).resolve()
            class_position = argv.index("-selectclass")
            class_name = argv[class_position + 1]
            if class_name != RESOURCE_CLASS:
                raise AssertionError(f"wrong selected class: {class_name}")
            block = self._state(swf)[RESOURCE_METHOD]
            if self.drift_reopen_full_package and self.export_count >= 2:
                block = block.replace("pushtrue", "pushfalse", 1)
            target = (
                export_root
                / "scripts"
                / Path(*RESOURCE_CLASS.split(".")).with_suffix(".pcode")
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                unrelated_method() + block,
                encoding="utf-8",
                newline="\n",
            )
        return {"returncode": 0, "stdout": "", "stderr": ""}

    @staticmethod
    def assert_replace_class(class_name: str) -> None:
        if class_name != RESOURCE_CLASS:
            raise AssertionError(f"wrong replacement class: {class_name}")


@unittest.skipUnless(MODULE_PATH.is_file(), "external client-patch integration source unavailable")
class TestResourceVersionLock(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        before = resource_block()
        after = self.module.patch_resource_version(before)
        before_abc = hashlib.sha256(before.encode()).hexdigest()
        after_abc = hashlib.sha256(after.encode()).hexdigest()
        dummy_abc = hashlib.sha256(b"dummy-remote-abc").hexdigest()
        self.lock = {
            "schema_version": 4,
            "status": "accepted",
            "stage": "post-abyss",
            "site_count": 9,
            "resource_version": {
                "site_id": "full-resource-version",
                "class_name": RESOURCE_CLASS,
                "method_name": RESOURCE_METHOD,
                "source_version": SOURCE_VERSION,
                "target_version": TARGET_VERSION,
                "before_pcode_sha256": self.module._sha256_pcode(before),
                "after_pcode_sha256": self.module._sha256_pcode(after),
                "before_abc_sha256": before_abc,
                "after_abc_sha256": after_abc,
            },
            "offline_method_sha256": {
                RESOURCE_METHOD: before_abc,
                DUMMY_LOCK_KEY: dummy_abc,
            },
        }

    def test_lock_reader_is_strict_and_preserves_task9_fields(self) -> None:
        entry, dummy_hash = self.module._resource_lock(self.lock)
        self.assertEqual(self.lock["resource_version"], entry)
        self.assertEqual(
            self.lock["offline_method_sha256"][DUMMY_LOCK_KEY], dummy_hash
        )
        self.assertEqual(9, self.lock["site_count"])
        self.assertEqual("post-abyss", self.lock["stage"])

    def test_lock_rejects_missing_extra_identity_version_and_hash_drift(self) -> None:
        mutations = []
        missing = deepcopy(self.lock)
        del missing["resource_version"]["after_abc_sha256"]
        mutations.append(missing)
        extra = deepcopy(self.lock)
        extra["resource_version"]["body_index"] = 4900
        mutations.append(extra)
        for field, value in (
            ("site_id", "resource-version"),
            ("class_name", "pinball.config.core.Other"),
            ("method_name", "boot_ffc6#$script0/$init"),
            ("source_version", "1.4.53"),
            ("target_version", "1.4.197"),
            ("before_pcode_sha256", "0" * 63),
        ):
            candidate = deepcopy(self.lock)
            candidate["resource_version"][field] = value
            mutations.append(candidate)
        inconsistent = deepcopy(self.lock)
        inconsistent["offline_method_sha256"][RESOURCE_METHOD] = "f" * 64
        mutations.append(inconsistent)
        for candidate in mutations:
            with self.subTest(candidate=candidate), self.assertRaises(
                self.module.ResourceVersionError
            ):
                self.module._resource_lock(candidate)

    def test_before_and_after_locks_must_differ_and_dummy_lock_is_required(self) -> None:
        for field_pair in (
            ("before_pcode_sha256", "after_pcode_sha256"),
            ("before_abc_sha256", "after_abc_sha256"),
        ):
            candidate = deepcopy(self.lock)
            before, after = field_pair
            candidate["resource_version"][after] = candidate[
                "resource_version"
            ][before]
            with self.subTest(pair=field_pair), self.assertRaises(
                self.module.ResourceVersionError
            ):
                self.module._resource_lock(candidate)
        missing_dummy = deepcopy(self.lock)
        del missing_dummy["offline_method_sha256"][DUMMY_LOCK_KEY]
        with self.assertRaises(self.module.ResourceVersionError):
            self.module._resource_lock(missing_dummy)


@unittest.skipUnless(MODULE_PATH.is_file(), "external client-patch integration source unavailable")
class TestResourceVersionStage(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.swf"
        self.output = self.root / "output.swf"
        self.work = self.root / "work"
        self.profile = self.root / "profile"
        self.ffdec = self.root / "ffdec.jar"
        self.java = self.root / "java.exe"
        self.ffdec.write_bytes(b"fixture")
        self.java.write_bytes(b"fixture")
        self.before = resource_block()
        self.after = self.module.patch_resource_version(self.before)
        self.initial = {
            RESOURCE_METHOD: self.before,
            DUMMY_METHOD: "dummy-remote-abc",
        }
        self._write_source(self.initial)
        self.runner = self._new_runner()
        before_abc = hashlib.sha256(self.before.encode()).hexdigest()
        after_abc = hashlib.sha256(self.after.encode()).hexdigest()
        dummy_abc = hashlib.sha256(b"dummy-remote-abc").hexdigest()
        self.lock = {
            "schema_version": 4,
            "status": "accepted",
            "stage": "post-abyss",
            "site_count": 9,
            "resource_version": {
                "site_id": "full-resource-version",
                "class_name": RESOURCE_CLASS,
                "method_name": RESOURCE_METHOD,
                "source_version": SOURCE_VERSION,
                "target_version": TARGET_VERSION,
                "before_pcode_sha256": self.module._sha256_pcode(self.before),
                "after_pcode_sha256": self.module._sha256_pcode(self.after),
                "before_abc_sha256": before_abc,
                "after_abc_sha256": after_abc,
            },
            "offline_method_sha256": {
                RESOURCE_METHOD: before_abc,
                DUMMY_LOCK_KEY: dummy_abc,
            },
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_source(self, state: dict[str, str]) -> None:
        self.source.write_text(
            json.dumps(state, sort_keys=True), encoding="utf-8"
        )

    def _new_runner(self, **kwargs) -> FakeFfdecRunner:
        return FakeFfdecRunner(
            self.module, self.source, self.initial, **kwargs
        )

    def apply(self, *, runner=None):
        selected = self.runner if runner is None else runner
        with mock.patch.object(
            self.module.ABC_METHODS,
            "index_swf_methods",
            side_effect=selected.index,
        ):
            return self.module.apply_resource_version(
                self.source,
                self.output,
                self.lock,
                ffdec=self.ffdec,
                java=self.java,
                profile_dir=self.profile,
                work_dir=self.work,
                runner=selected,
            )

    def verify(self, *, runner=None):
        selected = self.runner if runner is None else runner
        with mock.patch.object(
            self.module.ABC_METHODS,
            "index_swf_methods",
            side_effect=selected.index,
        ):
            return self.module.verify_resource_version(
                self.output,
                self.lock,
                ffdec=self.ffdec,
                java=self.java,
                profile_dir=self.profile,
                work_dir=self.work,
                runner=selected,
            )

    def test_stage_resolves_names_replaces_reopens_and_reports_exact_versions(self) -> None:
        source_bytes = self.source.read_bytes()
        parent_appdata = "parent-appdata"
        with mock.patch.dict(os.environ, {"APPDATA": parent_appdata}, clear=False):
            report = self.apply()
            self.assertEqual(parent_appdata, os.environ["APPDATA"])
        self.assertEqual(source_bytes, self.source.read_bytes())
        self.assertTrue(self.output.is_file())
        self.assertTrue(report.verified)
        self.assertEqual(self.output.resolve(), report.output_path)
        self.assertEqual(SOURCE_VERSION, report.source_version)
        self.assertEqual(TARGET_VERSION, report.output_version)
        self.assertTrue(report.is_full_package)
        self.assertEqual(
            hashlib.sha256(source_bytes).hexdigest(), report.input_sha256
        )
        self.assertEqual(
            hashlib.sha256(self.output.read_bytes()).hexdigest(),
            report.output_sha256,
        )
        self.assertEqual(
            ["export", "replace", "export"],
            [kind for kind, *_ in self.runner.calls],
        )
        self.assertGreaterEqual(
            self.runner.require_ref_calls.count(RESOURCE_METHOD), 2
        )
        self.assertGreaterEqual(
            self.runner.require_ref_calls.count(DUMMY_METHOD), 2
        )
        self.assertTrue(
            all(
                appdata == str(self.profile.resolve())
                for *_, appdata in self.runner.calls
            )
        )
        commands = "\n".join(
            " ".join(argv).lower()
            for _, argv, _, _ in self.runner.calls
        )
        for forbidden in ("apksigner", "zipalign", "keystore", "-importscript"):
            self.assertNotIn(forbidden, commands)
        for kind, argv, _, _ in self.runner.calls:
            if kind == "replace":
                self.assertEqual(
                    "abort", argv[argv.index("-onerror") + 1]
                )
        self.assertFalse(any(self.work.iterdir()))

    def test_standalone_verify_reopens_and_checks_output(self) -> None:
        self.apply()
        before_calls = len(self.runner.calls)
        report = self.verify()
        self.assertTrue(report.verified)
        self.assertEqual(report.input_sha256, report.output_sha256)
        self.assertEqual(TARGET_VERSION, report.output_version)
        self.assertEqual(before_calls + 1, len(self.runner.calls))

    def test_stage_never_overwrites_preexisting_or_racing_output(self) -> None:
        self.output.write_bytes(b"sentinel")
        with self.assertRaises(self.module.ResourceVersionError):
            self.apply()
        self.assertEqual(b"sentinel", self.output.read_bytes())
        self.assertFalse(self.runner.calls)
        self.output.unlink()

        original_publish = self.module._publish_staged_exclusive

        def race(staging, destination: Path, expected_hash: str) -> None:
            destination.write_bytes(b"external-sentinel")
            original_publish(staging, destination, expected_hash)

        with mock.patch.object(
            self.module, "_publish_staged_exclusive", side_effect=race
        ):
            with self.assertRaises(self.module.ResourceVersionError):
                self.apply()
        self.assertEqual(b"external-sentinel", self.output.read_bytes())
        self.assertFalse(any(self.work.iterdir()))

    def test_stage_rejects_wrong_pcode_and_raw_abc_locks(self) -> None:
        cases = (
            ("before_abc_sha256", "0" * 64),
            ("before_pcode_sha256", "1" * 64),
            ("after_pcode_sha256", "2" * 64),
            ("after_abc_sha256", "3" * 64),
        )
        for field, value in cases:
            with self.subTest(field=field):
                self.runner = self._new_runner()
                self.lock["resource_version"][field] = value
                with self.assertRaises(self.module.ResourceVersionError):
                    self.apply()
                self.assertFalse(self.output.exists())
                self.assertTrue(
                    not self.work.exists() or not any(self.work.iterdir())
                )
                if field.startswith("before_"):
                    replacement = (
                        hashlib.sha256(self.before.encode()).hexdigest()
                        if field == "before_abc_sha256"
                        else self.module._sha256_pcode(self.before)
                    )
                else:
                    replacement = (
                        hashlib.sha256(self.after.encode()).hexdigest()
                        if field == "after_abc_sha256"
                        else self.module._sha256_pcode(self.after)
                    )
                self.lock["resource_version"][field] = replacement

    def test_dummy_remote_drift_before_or_after_replace_is_rejected(self) -> None:
        self.initial[DUMMY_METHOD] = "drifted-before"
        self._write_source(self.initial)
        runner = self._new_runner()
        with self.assertRaises(self.module.ResourceVersionError):
            self.apply(runner=runner)
        self.assertFalse(self.output.exists())

        self.initial[DUMMY_METHOD] = "dummy-remote-abc"
        self._write_source(self.initial)
        runner = self._new_runner(drift_dummy_after_replace=True)
        with self.assertRaises(self.module.ResourceVersionError):
            self.apply(runner=runner)
        self.assertFalse(self.output.exists())
        self.assertFalse(any(self.work.iterdir()))

    def test_reopen_is_full_package_drift_is_rejected_even_with_raw_abc_match(self) -> None:
        runner = self._new_runner(drift_reopen_full_package=True)
        with self.assertRaises(self.module.ResourceVersionError):
            self.apply(runner=runner)
        self.assertFalse(self.output.exists())
        self.assertFalse(any(self.work.iterdir()))

    def test_source_drift_after_external_call_stops_without_final(self) -> None:
        runner = self._new_runner()

        def mutate_after_first(command, *, cwd, env, timeout):
            result = runner(command, cwd=cwd, env=env, timeout=timeout)
            if len(runner.calls) == 1:
                self.source.write_bytes(b"source-drift")
            return result

        with mock.patch.object(
            self.module.ABC_METHODS,
            "index_swf_methods",
            side_effect=runner.index,
        ):
            with self.assertRaises(self.module.ResourceVersionError):
                self.module.apply_resource_version(
                    self.source,
                    self.output,
                    self.lock,
                    ffdec=self.ffdec,
                    java=self.java,
                    profile_dir=self.profile,
                    work_dir=self.work,
                    runner=mutate_after_first,
                )
        self.assertEqual(1, len(runner.calls))
        self.assertFalse(self.output.exists())
        self.assertFalse(any(self.work.iterdir()))

    def test_keyboard_interrupt_at_each_external_boundary_cleans_transaction(self) -> None:
        for boundary in (1, 2, 3):
            runner = self._new_runner()

            def interrupt_nth(
                command, *, cwd, env, timeout, selected=boundary
            ):
                if len(runner.calls) + 1 == selected:
                    raise KeyboardInterrupt(f"cancel external call {selected}")
                return runner(command, cwd=cwd, env=env, timeout=timeout)

            with self.subTest(boundary=boundary), mock.patch.object(
                self.module.ABC_METHODS,
                "index_swf_methods",
                side_effect=runner.index,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self.module.apply_resource_version(
                        self.source,
                        self.output,
                        self.lock,
                        ffdec=self.ffdec,
                        java=self.java,
                        profile_dir=self.profile,
                        work_dir=self.work,
                        runner=interrupt_nth,
                    )
                self.assertFalse(self.output.exists())
                self.assertFalse(any(self.work.iterdir()))

    def test_keyboard_interrupt_in_staging_hooks_cleans_owned_artifacts(self) -> None:
        for hook in (
            "_copy_snapshot",
            "_stage_output_sibling",
            "_clean_transaction_before_publish",
        ):
            with self.subTest(hook=hook), mock.patch.object(
                self.module,
                hook,
                side_effect=KeyboardInterrupt(f"cancel {hook}"),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self.apply()
                self.assertFalse(self.output.exists())
                self.assertFalse(any(self.work.iterdir()))

    def test_output_ancestor_and_hardlink_alias_are_rejected_before_tools(self) -> None:
        unsafe_output = self.root / "container"
        unsafe_work = unsafe_output / "work"
        with mock.patch.object(
            self.module.ABC_METHODS,
            "index_swf_methods",
            side_effect=self.runner.index,
        ):
            with self.assertRaises(self.module.ResourceVersionError):
                self.module.apply_resource_version(
                    self.source,
                    unsafe_output,
                    self.lock,
                    ffdec=self.ffdec,
                    java=self.java,
                    profile_dir=self.profile,
                    work_dir=unsafe_work,
                    runner=self.runner,
                )
        self.assertFalse(unsafe_output.exists())
        self.assertFalse(self.runner.calls)

        try:
            os.link(self.source, self.output)
        except OSError as exc:
            self.skipTest(f"hardlinks unavailable: {exc}")
        with self.assertRaises(self.module.ResourceVersionError):
            self.apply()
        self.assertFalse(self.runner.calls)
        self.assertEqual(self.source.read_bytes(), self.output.read_bytes())


if __name__ == "__main__":
    unittest.main()

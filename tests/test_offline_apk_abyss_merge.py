# -*- coding: utf-8 -*-
"""Composable, SWF-only abyss gate stage regression tests."""
from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import hashlib
import importlib.util
import inspect
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
BUILDER_PATH = client_patch_path('abyss-mode-equipment/build_apk.py')
SPEC = importlib.util.spec_from_file_location(
    "offline_apk_abyss_merge_builder", require_external_source(BUILDER_PATH)
)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - importlib guard
    raise ImportError(f"cannot load abyss builder module: {BUILDER_PATH}")
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


EXACT_CLASS_RELATIVE = Path(
    "scripts/pinball/common/data/character/BattleCharacterLogic.as"
)


def _source_text() -> str:
    patch = module.abyss_patch
    return "\n".join(
        [
            "package",
            "{",
            "   public class BattleCharacterLogic",
            "   {",
            f"      {patch.WITH_COND_SIGNATURE}",
            "      {",
            "         var _loc12_:* = null as AbilitySoulAbilityLogic;",
            "         var _loc13_:* = null as BattleAbilityPeek;",
            "         var _loc14_:Boolean = false;",
            "         _loc14_ = Boolean(param3(_loc13_.questKind));",
            "      }",
            "",
            f"      {patch.TARGET_SIGNATURE}",
            "      {",
            "         var _loc12_:* = null as AbilitySoulAbilityLogic;",
            "         var _loc13_:* = null as BattleAbilityPeek;",
            "         var _loc14_:Boolean = false;",
            "         var _loc15_:int = 0;",
            f"         {patch.ANCHOR}",
            "         if(_loc14_)",
            "         {",
            "            _loc10_ = _loc13_.getTriggers();",
            "            _loc7_.add(_loc18_,_loc10_[_loc17_],this,param1,param2,false);",
            "         }",
            "      }",
            "",
            "      public function getActionSkills() : Array",
            "      {",
            "         return [];",
            "      }",
            "   }",
            "}",
            "",
        ]
    )


def _patched_text(*, markers: bool) -> str:
    patched, count = module.abyss_patch.patch_text(_source_text())
    if count != 1:  # pragma: no cover - fixture invariant
        raise AssertionError(f"fixture patch count is {count}")
    if markers:
        return patched
    return (
        "\n".join(
            line
            for line in patched.splitlines()
            if module.abyss_patch.BEGIN_MARKER not in line
            and module.abyss_patch.END_MARKER not in line
        )
        + "\n"
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class RecordedCall:
    kind: str
    argv: tuple[str, ...]
    cwd: Path
    environment: dict[str, str]


class FakeFfdecRunner:
    """Model FFDec's three observable filesystem effects, without launching it."""

    def __init__(
        self,
        source_swf: Path,
        *,
        base_text: str | None = None,
        reopened_text: str | None = None,
        base_export_mode: str = "exact",
        reopen_export_mode: str = "exact",
        swf_mode: str = "changed",
        fail_kind: str | None = None,
        cancel_kind: str | None = None,
        drift_kind: str | None = None,
        race_output: Path | None = None,
        race_bytes: bytes = b"external-racing-output",
    ) -> None:
        self.source_swf = source_swf
        self.base_text = _source_text() if base_text is None else base_text
        self.reopened_text = (
            _patched_text(markers=False) if reopened_text is None else reopened_text
        )
        self.base_export_mode = base_export_mode
        self.reopen_export_mode = reopen_export_mode
        self.swf_mode = swf_mode
        self.fail_kind = fail_kind
        self.cancel_kind = cancel_kind
        self.drift_kind = drift_kind
        self.race_output = race_output
        self.race_bytes = race_bytes
        self.calls: list[RecordedCall] = []
        self._export_count = 0

    @staticmethod
    def _write_export(export_root: Path, text: str, mode: str) -> None:
        if mode == "missing":
            return
        if mode == "wrong-package":
            destinations = [
                export_root / "scripts/wrong/package/BattleCharacterLogic.as"
            ]
        else:
            destinations = [export_root / EXACT_CLASS_RELATIVE]
            if mode == "duplicate":
                destinations.append(
                    export_root / "scripts/duplicate/BattleCharacterLogic.as"
                )
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(text.encode("utf-8"))

    def __call__(
        self,
        command: list[str],
        *,
        check: bool,
        cwd: Path | str,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        argv = tuple(str(value) for value in command)
        if "-replace" in argv:
            kind = "import"
        elif "-export" in argv:
            kind = "export" if self._export_count == 0 else "reopen-export"
            self._export_count += 1
        else:  # pragma: no cover - test double rejects unexpected commands
            raise AssertionError(f"unexpected command: {argv!r}")
        self.calls.append(
            RecordedCall(kind, argv, Path(cwd).resolve(), dict(env))
        )
        if not check:  # pragma: no cover - contract assertion
            raise AssertionError("external commands must be checked")
        if self.cancel_kind == kind:
            raise KeyboardInterrupt(f"cancelled {kind}")
        if self.fail_kind == kind:
            raise subprocess.CalledProcessError(9, argv)

        if kind == "export":
            export_at = argv.index("-export")
            self._write_export(
                Path(argv[export_at + 2]), self.base_text, self.base_export_mode
            )
        elif kind == "import":
            replace_at = argv.index("-replace")
            source = Path(argv[replace_at + 1])
            destination = Path(argv[replace_at + 2])
            if self.swf_mode != "missing":
                destination.parent.mkdir(parents=True, exist_ok=True)
                if self.swf_mode == "empty":
                    destination.write_bytes(b"")
                elif self.swf_mode == "identical":
                    shutil.copyfile(source, destination)
                else:
                    destination.write_bytes(source.read_bytes() + b"\nabyss-gate")
        else:
            export_at = argv.index("-export")
            self._write_export(
                Path(argv[export_at + 2]),
                self.reopened_text,
                self.reopen_export_mode,
            )
            if self.race_output is not None:
                self.race_output.write_bytes(self.race_bytes)

        if self.drift_kind == kind:
            self.source_swf.write_bytes(b"source-drifted-during-" + kind.encode())
        return subprocess.CompletedProcess(list(argv), 0)


class AbyssStageFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.swf"
        self.output = self.root / "output.swf"
        self.work = self.root / "work"
        self.profile = self.root / "profile"
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.java = self.tools / "java.exe"
        self.ffdec = self.tools / "ffdec.jar"
        self.java.write_bytes(b"fixture java")
        self.ffdec.write_bytes(b"fixture ffdec")
        self.source_bytes = b"FWS-composable-abyss-source"
        self.source.write_bytes(self.source_bytes)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def apply(
        self,
        runner: FakeFfdecRunner,
        *,
        source: Path | None = None,
        output: Path | None = None,
        java: Path | None = None,
        ffdec: Path | None = None,
        profile: Path | None = None,
        work: Path | None = None,
    ):
        return module.apply_gate_to_swf(
            self.source if source is None else source,
            self.output if output is None else output,
            ffdec=self.ffdec if ffdec is None else ffdec,
            java=self.java if java is None else java,
            profile_dir=self.profile if profile is None else profile,
            work_dir=self.work if work is None else work,
            runner=runner,
        )

    def assert_clean_failure(self) -> None:
        self.assertFalse(self.output.exists())
        if self.work.exists():
            self.assertEqual([], list(self.work.iterdir()))
        self.assertEqual([], list(self.root.glob(f".{self.output.name}.*.tmp")))


class TestComposableAbyssStage(AbyssStageFixture):
    def test_exports_patches_reopens_and_reports_without_signing(self) -> None:
        runner = FakeFfdecRunner(self.source)
        parent_appdata = "parent-appdata-must-remain"

        with mock.patch.dict(os.environ, {"APPDATA": parent_appdata}, clear=False):
            report = self.apply(runner)
            self.assertEqual(parent_appdata, os.environ["APPDATA"])

        self.assertEqual("abyss-mode-equipment", report.stage)
        self.assertEqual(self.output.resolve(), report.output_path)
        self.assertEqual(_sha256_bytes(self.source_bytes), report.input_sha256)
        self.assertEqual(module.sha256_file(self.output), report.output_sha256)
        self.assertEqual(module.TARGET_CLASS, report.target_class)
        self.assertEqual(
            _sha256_bytes(_source_text().encode("utf-8")),
            report.before_method_sha256,
        )
        self.assertEqual(
            _sha256_bytes(_patched_text(markers=False).encode("utf-8")),
            report.after_method_sha256,
        )
        self.assertEqual(1, report.match_count)
        self.assertEqual(self.source_bytes, self.source.read_bytes())
        self.assertNotEqual(self.source_bytes, self.output.read_bytes())
        self.assertEqual(
            ["export", "import", "reopen-export"],
            [call.kind for call in runner.calls],
        )
        commands = "\n".join(" ".join(call.argv).lower() for call in runner.calls)
        for forbidden in ("zipalign", "apksigner", "keystore", "--ks-pass"):
            self.assertNotIn(forbidden, commands)

        transaction_cwds = {call.cwd for call in runner.calls}
        self.assertEqual(1, len(transaction_cwds))
        transaction = next(iter(transaction_cwds))
        self.assertEqual(self.work.resolve(), transaction.parent)
        self.assertTrue(transaction.name.startswith(".abyss-swf-stage-"))
        self.assertFalse(transaction.exists())
        for call in runner.calls:
            self.assertEqual(str(self.profile.resolve()), call.environment["APPDATA"])
        import_call = runner.calls[1]
        self.assertIn("-air", import_call.argv)
        self.assertIn("-onerror", import_call.argv)
        self.assertIn("abort", import_call.argv)
        self.assertIn("-replace", import_call.argv)

    def test_public_report_is_frozen_slotted_and_legacy_export_signature_stays(self) -> None:
        fields = module.PatchStageReport.__dataclass_fields__
        self.assertEqual(
            [
                "stage",
                "output_path",
                "input_sha256",
                "output_sha256",
                "target_class",
                "before_method_sha256",
                "after_method_sha256",
                "match_count",
            ],
            list(fields),
        )
        self.assertTrue(module.PatchStageReport.__dataclass_params__.frozen)
        self.assertIn("__slots__", module.PatchStageReport.__dict__)
        parameters = list(inspect.signature(module.export_verified_class).parameters)
        self.assertEqual(["swf", "export_dir", "ffdec", "java"], parameters)

    def test_preflight_rejects_alias_missing_inputs_and_existing_output(self) -> None:
        alias_runner = FakeFfdecRunner(self.source)
        alias = self.source.parent / "." / self.source.name
        with self.assertRaises(module.BuildError):
            self.apply(alias_runner, output=alias)
        self.assertEqual([], alias_runner.calls)

        for label, missing in (
            ("source", self.source),
            ("java", self.java),
            ("ffdec", self.ffdec),
        ):
            with self.subTest(label=label):
                original = missing.read_bytes()
                missing.unlink()
                runner = FakeFfdecRunner(self.source)
                try:
                    kwargs = {label: missing}
                    with self.assertRaises(module.BuildError):
                        self.apply(runner, **kwargs)
                    self.assertEqual([], runner.calls)
                finally:
                    missing.parent.mkdir(parents=True, exist_ok=True)
                    missing.write_bytes(original)

        sentinel = b"existing-output-must-survive"
        self.output.write_bytes(sentinel)
        runner = FakeFfdecRunner(self.source)
        with self.assertRaises(module.BuildError):
            self.apply(runner)
        self.assertEqual(sentinel, self.output.read_bytes())
        self.assertEqual([], runner.calls)

    def test_unsupported_platform_fails_before_directory_side_effects(self) -> None:
        runner = FakeFfdecRunner(self.source)

        with mock.patch.object(
            module.os, "name", "posix"
        ), self.assertRaisesRegex(module.BuildError, "Windows handle-bound"):
            self.apply(runner)

        self.assertEqual([], runner.calls)
        self.assertFalse(self.work.exists())
        self.assertFalse(self.profile.exists())
        self.assertFalse(self.output.exists())

    def test_preflight_rejects_output_ancestor_directory_topologies(self) -> None:
        cases = (
            ("work-equal", "work", "equal"),
            ("profile-equal", "profile", "equal"),
            ("work-descendant", "work", "descendant"),
            ("profile-descendant", "profile", "descendant"),
        )
        for case_name, directory_name, relationship in cases:
            with self.subTest(case=case_name):
                case_root = self.root / f"topology-{case_name}"
                output = case_root / "unsafe-output.swf"
                work = self.root / f"safe-work-{case_name}"
                profile = self.root / f"safe-profile-{case_name}"
                unsafe_directory = (
                    output
                    if relationship == "equal"
                    else output / f"nested-{directory_name}"
                )
                if directory_name == "work":
                    work = unsafe_directory
                else:
                    profile = unsafe_directory
                runner = FakeFfdecRunner(self.source)

                with self.assertRaisesRegex(module.BuildError, "output.*directory"):
                    self.apply(
                        runner,
                        output=output,
                        work=work,
                        profile=profile,
                    )

                self.assertEqual([], runner.calls)
                self.assertFalse(case_root.exists())
                self.assertFalse(work.exists())
                self.assertFalse(profile.exists())

    def test_output_beneath_work_or_profile_is_allowed(self) -> None:
        cases = (
            (
                "work",
                self.root / "output-under-work",
                self.root / "profile-for-work-output",
            ),
            (
                "profile",
                self.root / "work-for-profile-output",
                self.root / "output-under-profile",
            ),
        )
        for container_name, work, profile in cases:
            with self.subTest(container=container_name):
                container = work if container_name == "work" else profile
                output = container / "published" / "output.swf"
                runner = FakeFfdecRunner(self.source)

                report = self.apply(
                    runner,
                    output=output,
                    work=work,
                    profile=profile,
                )

                self.assertEqual(output.resolve(), report.output_path)
                self.assertTrue(output.is_file())
                self.assertEqual(
                    ["export", "import", "reopen-export"],
                    [call.kind for call in runner.calls],
                )

    def test_base_export_must_be_one_exact_package_path(self) -> None:
        for mode in ("missing", "duplicate", "wrong-package"):
            with self.subTest(mode=mode):
                runner = FakeFfdecRunner(self.source, base_export_mode=mode)
                with self.assertRaises(module.BuildError):
                    self.apply(runner)
                self.assertEqual(["export"], [call.kind for call in runner.calls])
                self.assert_clean_failure()

    def test_patch_count_and_source_semantics_fail_before_import(self) -> None:
        already_patched = FakeFfdecRunner(
            self.source, base_text=_patched_text(markers=True)
        )
        with self.assertRaises(module.BuildError):
            self.apply(already_patched)
        self.assertEqual(["export"], [call.kind for call in already_patched.calls])
        self.assert_clean_failure()

        damaged = FakeFfdecRunner(
            self.source,
            base_text=_source_text().replace(module.abyss_patch.ANCHOR, "missingAnchor"),
        )
        with self.assertRaises(module.abyss_patch.PatchError):
            self.apply(damaged)
        self.assertEqual(["export"], [call.kind for call in damaged.calls])
        self.assert_clean_failure()

        def report_two_matches(source: Path, output: Path) -> int:
            patched, count = module.abyss_patch.patch_text(
                Path(source).read_text(encoding="utf-8-sig")
            )
            self.assertEqual(1, count)
            Path(output).write_bytes(patched.encode("utf-8"))
            return 2

        runner = FakeFfdecRunner(self.source)
        with mock.patch.object(
            module.abyss_patch, "patch_file", side_effect=report_two_matches
        ), self.assertRaises(module.BuildError):
            self.apply(runner)
        self.assertEqual(["export"], [call.kind for call in runner.calls])
        self.assert_clean_failure()

    def test_reopened_export_and_markerless_semantics_are_fail_closed(self) -> None:
        cases = (
            ("missing", None),
            ("duplicate", None),
            ("wrong-package", None),
            ("exact", "invalid ActionScript"),
            (
                "exact",
                _patched_text(markers=False).replace("_loc15_ <= 97", "_loc15_ <= 98"),
            ),
        )
        for mode, text in cases:
            with self.subTest(mode=mode, invalid=text is not None):
                runner = FakeFfdecRunner(
                    self.source,
                    reopen_export_mode=mode,
                    reopened_text=text,
                )
                with self.assertRaises(
                    (module.BuildError, module.abyss_patch.PatchError)
                ):
                    self.apply(runner)
                self.assertEqual(
                    ["export", "import", "reopen-export"],
                    [call.kind for call in runner.calls],
                )
                self.assert_clean_failure()

    def test_source_hash_drift_after_each_external_stage_is_rejected(self) -> None:
        for kind in ("export", "import", "reopen-export"):
            with self.subTest(kind=kind):
                self.source.write_bytes(self.source_bytes)
                runner = FakeFfdecRunner(self.source, drift_kind=kind)
                with self.assertRaises(module.BuildError):
                    self.apply(runner)
                self.assertNotEqual(self.source_bytes, self.source.read_bytes())
                self.assert_clean_failure()

    def test_external_failures_and_cancellations_clean_owned_state(self) -> None:
        for behavior in ("failure", "cancel"):
            for kind in ("export", "import", "reopen-export"):
                with self.subTest(behavior=behavior, kind=kind):
                    self.source.write_bytes(self.source_bytes)
                    runner = FakeFfdecRunner(
                        self.source,
                        fail_kind=kind if behavior == "failure" else None,
                        cancel_kind=kind if behavior == "cancel" else None,
                    )
                    expected = (
                        subprocess.CalledProcessError
                        if behavior == "failure"
                        else KeyboardInterrupt
                    )
                    with self.assertRaises(expected):
                        self.apply(runner)
                    self.assert_clean_failure()

    def test_missing_empty_or_identical_import_output_is_rejected(self) -> None:
        for mode in ("missing", "empty", "identical"):
            with self.subTest(mode=mode):
                runner = FakeFfdecRunner(self.source, swf_mode=mode)
                with self.assertRaises(module.BuildError):
                    self.apply(runner)
                expected_calls = ["export", "import"]
                if mode == "identical":
                    expected_calls.append("reopen-export")
                self.assertEqual(expected_calls, [call.kind for call in runner.calls])
                self.assert_clean_failure()

    def test_publication_race_preserves_the_external_output(self) -> None:
        sentinel = b"external-racing-output-must-survive"
        runner = FakeFfdecRunner(
            self.source,
            race_output=self.output,
            race_bytes=sentinel,
        )

        with self.assertRaises(module.BuildError):
            self.apply(runner)

        self.assertEqual(sentinel, self.output.read_bytes())
        if self.work.exists():
            self.assertEqual([], list(self.work.iterdir()))
        self.assertEqual([], list(self.root.glob(f".{self.output.name}.*.tmp")))

    def test_transaction_cleanup_failure_never_publishes_final_output(self) -> None:
        runner = FakeFfdecRunner(self.source)
        retained: list[Path] = []

        def refuse_cleanup(path: Path) -> None:
            retained.append(Path(path))
            raise PermissionError("transaction cleanup blocked")

        with mock.patch.object(
            module.shutil, "rmtree", side_effect=refuse_cleanup
        ), self.assertRaisesRegex(module.BuildError, "clean.*transaction"):
            self.apply(runner)

        self.assertFalse(self.output.exists())
        self.assertEqual(2, len(retained))
        self.assertEqual(retained[0], retained[1])
        self.assertTrue(retained[0].is_dir())
        self.assertEqual([], list(self.root.glob(f".{self.output.name}.*.tmp")))
        shutil.rmtree(retained[0])

    def test_transient_transaction_cleanup_failure_is_retried(self) -> None:
        runner = FakeFfdecRunner(self.source)
        real_rmtree = shutil.rmtree
        cleanup_attempts: list[Path] = []

        def fail_once(path: Path) -> None:
            cleanup_attempts.append(Path(path))
            if len(cleanup_attempts) == 1:
                raise PermissionError("transient transaction cleanup failure")
            real_rmtree(path)

        with mock.patch.object(
            module.shutil, "rmtree", side_effect=fail_once
        ), self.assertRaisesRegex(module.BuildError, "clean.*transaction"):
            self.apply(runner)

        self.assertEqual(2, len(cleanup_attempts))
        self.assertEqual(cleanup_attempts[0], cleanup_attempts[1])
        self.assertFalse(self.output.exists())
        if self.work.exists():
            self.assertEqual([], list(self.work.iterdir()))
        self.assertEqual([], list(self.root.glob(f".{self.output.name}.*.tmp")))

    def test_commit_permission_error_is_stable_and_cleans_all_staging(self) -> None:
        runner = FakeFfdecRunner(self.source)

        with mock.patch.object(
            module,
            "_rename_staging_handle_no_replace",
            side_effect=PermissionError("hard link denied"),
        ), self.assertRaisesRegex(module.BuildError, "publish output SWF"):
            self.apply(runner)

        self.assert_clean_failure()

    def test_source_is_rechecked_after_transaction_cleanup_immediately_before_link(self) -> None:
        runner = FakeFfdecRunner(self.source)
        real_rmtree = shutil.rmtree

        def clean_then_drift(path: Path) -> None:
            real_rmtree(path)
            self.source.write_bytes(b"drifted-after-transaction-cleanup")

        with mock.patch.object(
            module.shutil,
            "rmtree",
            side_effect=clean_then_drift,
        ), mock.patch.object(
            module,
            "_rename_staging_handle_no_replace",
            wraps=module._rename_staging_handle_no_replace,
        ) as commit, self.assertRaisesRegex(module.BuildError, "source SWF changed"):
            self.apply(runner)

        commit.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertEqual([], list(self.root.glob(f".{self.output.name}.*.tmp")))

    def test_staging_identity_swap_before_link_is_never_published(self) -> None:
        runner = FakeFfdecRunner(self.source)
        sentinel = b"external-staging-sentinel-before-link"
        real_publish = module._publish_staged_exclusive
        staging_paths: list[Path] = []

        def swap_then_publish(staging, destination: Path, expected_hash: str):
            staging_path = Path(getattr(staging, "path", staging))
            staging_paths.append(staging_path)
            staging_path.unlink()
            staging_path.write_bytes(sentinel)
            return real_publish(staging, destination, expected_hash)

        with mock.patch.object(
            module,
            "_publish_staged_exclusive",
            side_effect=swap_then_publish,
        ), self.assertRaisesRegex(module.BuildError, "staged output SWF"):
            self.apply(runner)

        self.assertFalse(self.output.exists())
        self.assertEqual(1, len(staging_paths))
        self.assertEqual(sentinel, staging_paths[0].read_bytes())

    def test_successful_commit_never_cleans_a_new_external_staging_path(self) -> None:
        runner = FakeFfdecRunner(self.source)
        sentinel = b"external-staging-sentinel-after-publication"
        real_publish = module._publish_staged_exclusive
        staging_paths: list[Path] = []

        def publish_then_create(staging, destination: Path, expected_hash: str):
            real_publish(staging, destination, expected_hash)
            staging_path = Path(getattr(staging, "path", staging))
            self.assertFalse(staging_path.exists())
            staging_paths.append(staging_path)
            staging_path.write_bytes(sentinel)

        with mock.patch.object(
            module,
            "_publish_staged_exclusive",
            side_effect=publish_then_create,
        ):
            report = self.apply(runner)

        self.assertEqual(module.sha256_file(self.output), report.output_sha256)
        self.assertEqual(1, len(staging_paths))
        self.assertEqual(sentinel, staging_paths[0].read_bytes())

    def test_external_replacement_after_commit_is_never_rolled_back(self) -> None:
        runner = FakeFfdecRunner(self.source)
        sentinel = b"external-final-immediately-after-handle-commit"
        real_commit = module._rename_staging_handle_no_replace
        state = {"committed": False}

        def commit_then_replace(staging, destination: Path) -> None:
            real_commit(staging, destination)
            destination.unlink()
            destination.write_bytes(sentinel)
            state["committed"] = True

        with mock.patch.object(
            module,
            "_rename_staging_handle_no_replace",
            side_effect=commit_then_replace,
        ):
            self.apply(runner)

        self.assertTrue(state["committed"])
        self.assertEqual(sentinel, self.output.read_bytes())
        self.assertEqual([], list(self.root.glob(f".{self.output.name}.*.tmp")))

    def test_external_write_after_final_hash_is_denied_before_commit(self) -> None:
        runner = FakeFfdecRunner(self.source)
        real_commit = module._rename_staging_handle_no_replace
        corrupt_bytes = b"external-write-after-final-staging-hash"
        state = {"write_blocked": False}

        def try_write_then_commit(staging, destination: Path) -> None:
            import msvcrt

            ctypes, _wintypes, kernel32 = module._windows_file_api()
            raw_handle = kernel32.CreateFileW(
                str(staging.path),
                0x40000000,
                0x00000001 | 0x00000002 | 0x00000004,
                None,
                3,
                0,
                None,
            )
            if raw_handle == ctypes.c_void_p(-1).value:
                error_code = ctypes.get_last_error()
                if error_code != 32:
                    raise ctypes.WinError(error_code)
                state["write_blocked"] = True
            else:
                descriptor = msvcrt.open_osfhandle(
                    raw_handle, os.O_WRONLY | os.O_BINARY
                )
                with os.fdopen(descriptor, "wb") as external_writer:
                    external_writer.seek(0)
                    external_writer.write(corrupt_bytes)
                    external_writer.truncate()
                    external_writer.flush()
                    os.fsync(external_writer.fileno())
            real_commit(staging, destination)

        with mock.patch.object(
            module,
            "_rename_staging_handle_no_replace",
            side_effect=try_write_then_commit,
        ):
            report = self.apply(runner)

        self.assertTrue(state["write_blocked"])
        self.assertEqual(report.output_sha256, module.sha256_file(self.output))
        self.assertNotEqual(corrupt_bytes, self.output.read_bytes())

    def test_cleanup_stat_unlink_race_never_deletes_external_staging(self) -> None:
        runner = FakeFfdecRunner(self.source)
        sentinel = b"external-staging-between-stat-and-cleanup"
        real_identity = module._file_identity
        state = {"cleanup": False, "swapped": False}
        staging_paths: list[Path] = []

        def fail_before_commit(_transaction: Path) -> None:
            state["cleanup"] = True
            raise module.BuildError("forced pre-commit failure")

        def inspect_then_swap(
            path: Path,
            label: str,
            *,
            missing_ok: bool = False,
        ):
            identity = real_identity(path, label, missing_ok=missing_ok)
            if (
                state["cleanup"]
                and not state["swapped"]
                and label == "staged output SWF"
                and identity is not None
            ):
                staging_path = Path(path)
                staging_path.unlink()
                staging_path.write_bytes(sentinel)
                staging_paths.append(staging_path)
                state["swapped"] = True
            return identity

        with mock.patch.object(
            module,
            "_clean_transaction_before_publish",
            side_effect=fail_before_commit,
        ), mock.patch.object(
            module,
            "_file_identity",
            side_effect=inspect_then_swap,
        ), self.assertRaisesRegex(module.BuildError, "forced pre-commit"):
            self.apply(runner)

        self.assertTrue(state["swapped"])
        self.assertFalse(self.output.exists())
        self.assertEqual(1, len(staging_paths))
        self.assertEqual(sentinel, staging_paths[0].read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)

# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import wf_offline_bundle as bundle
import wf_offline_device as module


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def create_directory_junction(link: Path, target: Path) -> None:
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"real NTFS junction creation failed with exit code {completed.returncode}"
        )


class FakeAdbRunner:
    """Complete, deterministic test double for the read-only ADB surface."""

    def __init__(
        self,
        *,
        serial: str = "127.0.0.1:16384",
        devices: list[tuple[str, str]] | None = None,
        installed: bool = True,
        package_line: str | None = None,
        activity: str = "com.leiting.wf/com.leiting.sdk.activity.PrivacyActivity",
        airplane_mode: str = "1",
        wifi: str = "0",
        mobile: str = "0",
        ipv4_default_route: str = "",
        ipv6_default_route: str = "",
        active_network: str = "null",
        proc_tcp: str = "sl  local_address rem_address st\n",
        save_haxe: bool = False,
        dummy_data: bool = False,
        logcat: str = "I/WF: offline boot ready\n",
    ) -> None:
        self.serial = serial
        self.devices = devices if devices is not None else [(serial, "device")]
        self.installed = installed
        self.package_line = package_line
        self.activity = activity
        self.airplane_mode = airplane_mode
        self.wifi = wifi
        self.mobile = mobile
        self.ipv4_default_route = ipv4_default_route
        self.ipv6_default_route = ipv6_default_route
        self.active_network = active_network
        self.proc_tcp = proc_tcp
        self.save_haxe = save_haxe
        self.dummy_data = dummy_data
        self.logcat = logcat
        self.calls: list[tuple[str | None, tuple[str, ...]]] = []

    def adb(self, serial: str | None, *args: str) -> str:
        self.calls.append((serial, tuple(args)))
        if serial is None and args == ("devices", "-l"):
            lines = ["List of devices attached"]
            lines.extend(f"{device_serial}\t{state} product:fake" for device_serial, state in self.devices)
            return "\n".join(lines) + "\n"
        if serial != self.serial:
            raise AssertionError(f"unexpected serial: {serial!r}")
        if args == ("shell", "pm", "list", "packages", "com.leiting.wf"):
            if self.package_line is not None:
                return self.package_line
            return "package:com.leiting.wf\n" if self.installed else ""
        if args == (
            "shell",
            "cmd",
            "package",
            "resolve-activity",
            "--brief",
            "com.leiting.wf",
        ):
            return self.activity + "\n"
        if args == ("shell", "settings", "get", "global", "airplane_mode_on"):
            return self.airplane_mode + "\n"
        if args == ("shell", "settings", "get", "global", "wifi_on"):
            return self.wifi + "\n"
        if args == ("shell", "settings", "get", "global", "mobile_data"):
            return self.mobile + "\n"
        if args == ("shell", "ip", "-4", "route", "show", "default"):
            return self.ipv4_default_route
        if args == ("shell", "ip", "-6", "route", "show", "default"):
            return self.ipv6_default_route
        if args == ("shell", "dumpsys", "connectivity"):
            return self.active_network
        if args == ("shell", "cat", "/proc/net/tcp", "/proc/net/tcp6"):
            return self.proc_tcp
        if args[:4] == ("shell", "if", "[", "-e") and args[5:] == (
            "];",
            "then",
            "printf",
            "1;",
            "else",
            "printf",
            "0;",
            "fi",
        ):
            if args[4] == "/sdcard/WorldFlipper/save_haxe":
                return "1\n" if self.save_haxe else "0\n"
            if args[4] == "/sdcard/WorldFlipper/dummy":
                return "1\n" if self.dummy_data else "0\n"
        if args == ("logcat", "-d", "-v", "brief"):
            return self.logcat
        if args == ("shell", "pm", "clear", "com.leiting.wf"):
            return "Success\n"
        if args == ("uninstall", "com.leiting.wf"):
            self.installed = False
            return "Success\n"
        if len(args) == 2 and args[0] == "install":
            self.installed = True
            return "Success\n"
        raise AssertionError(f"unexpected fake ADB command: serial={serial!r}, args={args!r}")

    @property
    def destructive_calls(self) -> list[tuple[str | None, tuple[str, ...]]]:
        return [
            call
            for call in self.calls
            if call[1][:3] == ("shell", "pm", "clear")
            or call[1][:1] in (("uninstall",), ("install",))
            or "rm" in call[1]
            or "mv" in call[1]
        ]


class OfflineDeviceTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows fixed-drive regression")
    def test_receipt_directory_chain_rejects_mapped_network_drive(self) -> None:
        with (
            mock.patch.object(module, "_windows_drive_type", return_value=4) as drive_type,
            self.assertRaisesRegex(module.DeviceError, "fixed local Windows drive"),
        ):
            module._directory_chain_paths(
                Path(r"Z:\\offline-receipts"),
                label="receipt parent",
            )
        drive_type.assert_called_once_with("Z:\\")

    def setUp(self) -> None:
        # Stable directory-handle tests need a tree whose ancestors are readable
        # under the managed Windows sandbox; the workspace volume is writable.
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.serial = "127.0.0.1:16384"
        self.target = module.DeviceTarget(self.root / "fake-adb.exe", self.serial)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.apk = self.candidate / bundle.APK_NAME
        self.apk.write_bytes(b"signed-offline-apk")
        self.identity = bundle.CandidateIdentity(
            "build-fixture-001",
            sha256(self.apk.read_bytes()),
            sha256(b"data-zip"),
            sha256(b"guide"),
            sha256(b"canonical-release-evidence"),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def runner(self, **kwargs: object) -> FakeAdbRunner:
        return FakeAdbRunner(serial=self.serial, **kwargs)

    def clean_probe(self, **changes: object) -> module.DeviceProbeReport:
        values: dict[str, object] = {
            "serial_digest": sha256(b"not-a-personal-label"),
            "package_name": "com.leiting.wf",
            "airplane_mode": True,
            "wifi_disabled": True,
            "mobile_disabled": True,
            "no_default_route": True,
            "no_active_network": True,
            "companion_ports_unused": True,
            "save_haxe_present_before": False,
            "dummy_data_present_before": False,
            "fatal_log_lines": (),
        }
        values.update(changes)
        return module.DeviceProbeReport(**values)

    def checks(self) -> dict[str, bool]:
        return {name: True for name in module.REQUIRED_MANUAL_CHECKS}

    def test_probe_requires_one_explicit_online_serial_and_reports_offline_state(self) -> None:
        runner = self.runner()
        report = module.probe_device(self.target, runner=runner)
        self.assertTrue(report.airplane_mode)
        self.assertTrue(report.wifi_disabled)
        self.assertTrue(report.mobile_disabled)
        self.assertTrue(report.no_default_route)
        self.assertTrue(report.no_active_network)
        self.assertTrue(report.companion_ports_unused)
        self.assertEqual(report.package_name, "com.leiting.wf")
        self.assertEqual(len(report.serial_digest), 64)
        self.assertNotIn(self.serial, report.serial_digest)

    def test_probe_uses_android_15_mobile_data_setting_read_only(self) -> None:
        runner = self.runner(mobile="1")
        report = module.probe_device(self.target, runner=runner)

        self.assertFalse(report.mobile_disabled)
        self.assertIn(
            (self.serial, ("shell", "settings", "get", "global", "mobile_data")),
            runner.calls,
        )
        self.assertNotIn(
            (self.serial, ("shell", "svc", "data", "status")),
            runner.calls,
        )
        self.assertEqual(runner.destructive_calls, [])

    def test_probe_uses_android_15_wifi_setting_read_only(self) -> None:
        runner = self.runner(wifi="1")
        report = module.probe_device(self.target, runner=runner)

        self.assertFalse(report.wifi_disabled)
        self.assertIn(
            (self.serial, ("shell", "settings", "get", "global", "wifi_on")),
            runner.calls,
        )
        self.assertNotIn(
            (self.serial, ("shell", "cmd", "wifi", "status")),
            runner.calls,
        )
        self.assertEqual(runner.destructive_calls, [])

    def test_probe_uses_remote_shell_directly_for_shared_path_checks(self) -> None:
        runner = self.runner()
        module.probe_device(self.target, runner=runner)

        path_calls = [
            command
            for _, command in runner.calls
            if command[:4] == ("shell", "if", "[", "-e")
        ]
        self.assertEqual(len(path_calls), 2)
        self.assertEqual(
            {command[4] for command in path_calls},
            {
                "/sdcard/WorldFlipper/save_haxe",
                "/sdcard/WorldFlipper/dummy",
            },
        )
        self.assertFalse(any(command[:3] == ("shell", "sh", "-c") for _, command in runner.calls))
        self.assertEqual(runner.destructive_calls, [])

    def test_probe_rejects_no_multiple_and_wrong_serial_devices(self) -> None:
        cases = (
            ([], "exactly one"),
            ([(self.serial, "device"), ("emulator-5554", "device")], "exactly one"),
            ([(("emulator-5554"), "device")], "serial"),
        )
        for devices, message in cases:
            with self.subTest(devices=devices):
                runner = self.runner(devices=devices)
                with self.assertRaisesRegex(module.DeviceError, message):
                    module.probe_device(self.target, runner=runner)
                self.assertEqual(runner.destructive_calls, [])

    def test_probe_rejects_unauthorized_and_offline_target(self) -> None:
        for state in ("unauthorized", "offline"):
            with self.subTest(state=state):
                runner = self.runner(devices=[(self.serial, state)])
                with self.assertRaisesRegex(module.DeviceError, state):
                    module.probe_device(self.target, runner=runner)
                self.assertEqual(runner.destructive_calls, [])

    def test_probe_rejects_noncanonical_serial_and_package_target(self) -> None:
        bad_serial = module.DeviceTarget(self.target.adb, self.serial + "\nother")
        with self.assertRaisesRegex(module.DeviceError, "serial"):
            module.probe_device(bad_serial, runner=self.runner())
        bad_package = module.DeviceTarget(self.target.adb, self.serial, package="com.example.other")
        runner = self.runner()
        with self.assertRaisesRegex(module.DeviceError, "package"):
            module.probe_device(bad_package, runner=runner)
        self.assertEqual(runner.calls, [])

    def test_probe_rejects_installed_package_or_activity_mismatch(self) -> None:
        runner = self.runner(package_line="package:com.example.other\n")
        with self.assertRaisesRegex(module.DeviceError, "package"):
            module.probe_device(self.target, runner=runner)
        runner = self.runner(activity="com.example.other/.MainActivity")
        with self.assertRaisesRegex(module.DeviceError, "activity"):
            module.probe_device(self.target, runner=runner)

    def test_probe_allows_package_absent_for_clean_preparation_probe(self) -> None:
        runner = self.runner(installed=False)
        report = module.probe_device(self.target, runner=runner)
        self.assertEqual(report.package_name, "com.leiting.wf")

    def test_probe_reports_routes_active_network_and_companion_port_dependency(self) -> None:
        # /proc/net/tcp remote endpoint uses hex port 1F41 == 8001.
        runner = self.runner(
            ipv4_default_route="default via 10.0.2.2 dev eth0\n",
            active_network="Active default network: 101\n",
            proc_tcp=(
                "sl  local_address rem_address st\n"
                "0: 0100007F:C001 0200007F:1F41 01\n"
            ),
        )
        report = module.probe_device(self.target, runner=runner)
        self.assertFalse(report.no_default_route)
        self.assertFalse(report.no_active_network)
        self.assertFalse(report.companion_ports_unused)

    def test_probe_reports_shared_data_presence_and_fatal_crash_lines(self) -> None:
        runner = self.runner(
            save_haxe=True,
            dummy_data=True,
            logcat=(
                "I/WF: starting\n"
                "E/AndroidRuntime: FATAL EXCEPTION: main\n"
                "A/libc: Fatal signal 11 (SIGSEGV)\n"
            ),
        )
        report = module.probe_device(self.target, runner=runner)
        self.assertTrue(report.save_haxe_present_before)
        self.assertTrue(report.dummy_data_present_before)
        self.assertEqual(len(report.fatal_log_lines), 2)

    def test_probe_ignores_benign_android_runtime_startup_lines(self) -> None:
        runner = self.runner(
            logcat=(
                "D/AndroidRuntime: >>>>>> START com.android.internal.os.ZygoteInit uid 0 <<<<<<\n"
                "I/AndroidRuntime: Using default boot image\n"
                "I/AndroidRuntime: Leaving lock profiling enabled\n"
            )
        )

        report = module.probe_device(self.target, runner=runner)

        self.assertEqual(report.fatal_log_lines, ())
        self.assertEqual(runner.destructive_calls, [])

    def test_probe_is_read_only_and_never_clears_logcat_or_shared_storage(self) -> None:
        runner = self.runner()
        module.probe_device(self.target, runner=runner)
        self.assertEqual(runner.destructive_calls, [])
        flattened = [argument for _, command in runner.calls for argument in command]
        self.assertNotIn((self.serial, ("logcat", "-c")), runner.calls)
        self.assertNotIn("rm", flattened)
        self.assertNotIn("mv", flattened)
        self.assertNotIn("force-stop", flattened)

    def test_prepare_rejects_without_exact_serial_bound_confirmation_before_any_call(self) -> None:
        runner = self.runner()
        with self.assertRaisesRegex(module.DeviceError, "confirmation") as raised:
            module.prepare_device(
                self.target,
                self.candidate,
                self.identity,
                confirm="WRONG",
                runner=runner,
            )
        self.assertEqual(runner.calls, [])
        self.assertNotIn(self.serial, str(raised.exception))
        self.assertNotIn(module.PREPARE_CONFIRM_PREFIX, str(raised.exception))

    def test_prepare_rejects_non_ascii_wrong_confirmation_as_device_error(self) -> None:
        runner = self.runner()
        with self.assertRaisesRegex(module.DeviceError, "confirmation"):
            module.prepare_device(
                self.target,
                self.candidate,
                self.identity,
                confirm="错误口令",
                runner=runner,
            )
        self.assertEqual(runner.calls, [])

    def test_prepare_normalizes_unencodable_confirmation_to_device_error(self) -> None:
        runner = self.runner()
        with self.assertRaisesRegex(module.DeviceError, "confirmation") as raised:
            module.prepare_device(
                self.target,
                self.candidate,
                self.identity,
                confirm="\ud800",
                runner=runner,
            )
        self.assertEqual(runner.calls, [])
        self.assertNotIn(self.serial, str(raised.exception))
        self.assertNotIn(module.PREPARE_CONFIRM_PREFIX, str(raised.exception))

    def test_prepare_does_not_call_overridden_confirmation_encoder(self) -> None:
        class HostileConfirmation(str):
            def encode(self, *args: object, **kwargs: object) -> bytes:
                raise RuntimeError("raw-confirmation-leak")

        runner = self.runner()
        supplied = HostileConfirmation("WRONG")
        with self.assertRaisesRegex(module.DeviceError, "confirmation") as raised:
            module.prepare_device(
                self.target,
                self.candidate,
                self.identity,
                confirm=supplied,
                runner=runner,
            )
        self.assertEqual(runner.calls, [])
        self.assertNotIn("raw-confirmation-leak", str(raised.exception))

    def test_prepare_validates_target_before_confirmation_without_echoing_it(self) -> None:
        bad_serial = self.serial + "\nsecond-device"
        target = module.DeviceTarget(self.target.adb, bad_serial)
        runner = self.runner()
        with self.assertRaisesRegex(module.DeviceError, "serial") as raised:
            module.prepare_device(
                target,
                self.candidate,
                self.identity,
                confirm="WRONG",
                runner=runner,
            )
        self.assertEqual(runner.calls, [])
        self.assertNotIn(bad_serial, str(raised.exception))

    def test_prepare_normalizes_hostile_target_and_candidate_paths_before_adb(self) -> None:
        class BrokenPath:
            def __fspath__(self) -> str:
                raise RuntimeError("pathlike-internal-detail")

        runner = self.runner()
        bad_target = module.DeviceTarget(BrokenPath(), self.serial)  # type: ignore[arg-type]
        with self.assertRaises(module.DeviceError) as target_error:
            module.prepare_device(
                bad_target,
                self.candidate,
                self.identity,
                confirm="WRONG",
                runner=runner,
            )
        with self.assertRaises(module.DeviceError) as candidate_error:
            module.prepare_device(
                self.target,
                BrokenPath(),  # type: ignore[arg-type]
                self.identity,
                confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
                runner=runner,
            )
        self.assertEqual(runner.calls, [])
        self.assertNotIn("pathlike-internal-detail", str(target_error.exception))
        self.assertNotIn("pathlike-internal-detail", str(candidate_error.exception))

    def test_prepare_normalizes_invalid_identity_to_device_error_before_adb(self) -> None:
        invalid = bundle.CandidateIdentity(  # type: ignore[arg-type]
            None,
            self.identity.apk_sha256,
            self.identity.data_zip_sha256,
            self.identity.guide_sha256,
            self.identity.evidence_sha256,
        )
        runner = self.runner()
        with self.assertRaisesRegex(module.DeviceError, "build ID"):
            module.prepare_device(
                self.target,
                self.candidate,
                invalid,
                confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
                runner=runner,
            )
        self.assertEqual(runner.calls, [])

    def test_prepare_rejects_candidate_apk_hash_drift_without_mutation(self) -> None:
        runner = self.runner()
        wrong = replace(self.identity, apk_sha256="0" * 64)
        with self.assertRaisesRegex(module.DeviceError, "APK hash drift"):
            module.prepare_device(
                self.target,
                self.candidate,
                wrong,
                confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
                runner=runner,
            )
        self.assertEqual(runner.destructive_calls, [])

    def test_prepare_missing_apk_closes_the_stable_parent_chain(self) -> None:
        self.apk.unlink()
        runner = self.runner()
        real_close = module._close_directory_chain
        with mock.patch.object(module, "_close_directory_chain", wraps=real_close) as close:
            with self.assertRaises(module.DeviceError):
                module.prepare_device(
                    self.target,
                    self.candidate,
                    self.identity,
                    confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
                    runner=runner,
                )
        self.assertEqual(close.call_count, 1)
        self.assertEqual(runner.calls, [])

    def test_prepare_rejects_existing_save_or_dummy_before_mutation(self) -> None:
        for field in ("save_haxe", "dummy_data"):
            with self.subTest(field=field):
                runner = self.runner(**{field: True})
                with self.assertRaisesRegex(module.DeviceError, "dedicated empty instance"):
                    module.prepare_device(
                        self.target,
                        self.candidate,
                        self.identity,
                        confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
                        runner=runner,
                    )
                self.assertEqual(runner.destructive_calls, [])

    def test_prepare_requires_every_offline_probe_gate_before_first_mutation(self) -> None:
        cases = {
            "airplane": {"airplane_mode": "0"},
            "wifi": {"wifi": "1"},
            "mobile": {"mobile": "1"},
            "route": {"ipv4_default_route": "default via 10.0.2.2 dev eth0\n"},
            "network": {"active_network": "Active default network: 101\n"},
            "companion": {
                "proc_tcp": (
                    "sl  local_address rem_address st\n"
                    "0: 0100007F:C001 0200007F:1F41 01\n"
                )
            },
            "fatal": {"logcat": "E/AndroidRuntime: FATAL EXCEPTION: main\n"},
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                runner = self.runner(**changes)
                with self.assertRaises(module.DeviceError):
                    module.prepare_device(
                        self.target,
                        self.candidate,
                        self.identity,
                        confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
                        runner=runner,
                    )
                self.assertEqual(runner.destructive_calls, [])

    @unittest.skipUnless(sys.platform == "win32", "requires Windows sharing semantics")
    def test_prepare_holds_one_read_only_apk_handle_that_blocks_write_through_mutation(self) -> None:
        class WriteRaceRunner(FakeAdbRunner):
            write_blocked = False

            def adb(inner_self, serial: str | None, *args: str) -> str:
                if args == ("shell", "pm", "clear", "com.leiting.wf"):
                    try:
                        with self.apk.open("r+b") as handle:
                            handle.seek(0)
                            handle.write(b"raced")
                    except OSError:
                        inner_self.write_blocked = True
                return super(WriteRaceRunner, inner_self).adb(serial, *args)

        runner = WriteRaceRunner(serial=self.serial)
        report = module.prepare_device(
            self.target,
            self.candidate,
            self.identity,
            confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
            runner=runner,
        )
        self.assertEqual(report.package_name, "com.leiting.wf")
        self.assertTrue(runner.write_blocked)
        self.assertEqual(sha256(self.apk.read_bytes()), self.identity.apk_sha256)

    @unittest.skipUnless(sys.platform == "win32", "requires Windows sharing semantics")
    def test_prepare_holds_one_apk_handle_that_blocks_replace_and_rename(self) -> None:
        replacement = self.root / "replacement.apk"
        replacement.write_bytes(b"replacement")

        class ReplaceRaceRunner(FakeAdbRunner):
            replace_blocked = False

            def adb(inner_self, serial: str | None, *args: str) -> str:
                if args == ("shell", "pm", "clear", "com.leiting.wf"):
                    try:
                        module.os.replace(replacement, self.apk)
                    except OSError:
                        inner_self.replace_blocked = True
                return super(ReplaceRaceRunner, inner_self).adb(serial, *args)

        runner = ReplaceRaceRunner(serial=self.serial)
        module.prepare_device(
            self.target,
            self.candidate,
            self.identity,
            confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
            runner=runner,
        )
        self.assertTrue(runner.replace_blocked)
        self.assertEqual(sha256(self.apk.read_bytes()), self.identity.apk_sha256)

    @unittest.skipUnless(sys.platform == "win32", "requires Windows reparse semantics")
    def test_prepare_rejects_real_ancestor_directory_symlink_before_adb(self) -> None:
        real_tree = self.root / "real-apk-tree"
        real_candidate = real_tree / "candidate"
        real_candidate.mkdir(parents=True)
        real_apk = real_candidate / bundle.APK_NAME
        real_apk.write_bytes(b"ancestor-bound-apk")
        alias_tree = self.root / "apk-tree-alias"
        create_directory_junction(alias_tree, real_tree)
        identity = replace(self.identity, apk_sha256=sha256(real_apk.read_bytes()))
        runner = self.runner()

        with self.assertRaisesRegex(module.DeviceError, "reparse"):
            module.prepare_device(
                self.target,
                alias_tree / "candidate",
                identity,
                confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
                runner=runner,
            )
        self.assertEqual(runner.calls, [])

    @unittest.skipUnless(sys.platform == "win32", "requires Windows directory handles")
    def test_prepare_parent_chain_blocks_real_ancestor_rebind_during_mutation(self) -> None:
        outer = self.root / "apk-outer"
        candidate = outer / "candidate"
        candidate.mkdir(parents=True)
        apk = candidate / bundle.APK_NAME
        apk.write_bytes(b"ancestor-locked-apk")
        moved = self.root / "apk-outer-moved"
        identity = replace(self.identity, apk_sha256=sha256(apk.read_bytes()))

        class AncestorRaceRunner(FakeAdbRunner):
            rebind_blocked = False

            def adb(inner_self, serial: str | None, *args: str) -> str:
                if args == ("shell", "pm", "clear", "com.leiting.wf"):
                    try:
                        module.os.replace(outer, moved)
                    except OSError:
                        inner_self.rebind_blocked = True
                    else:
                        module.os.replace(moved, outer)
                return super(AncestorRaceRunner, inner_self).adb(serial, *args)

        runner = AncestorRaceRunner(serial=self.serial)
        module.prepare_device(
            self.target,
            candidate,
            identity,
            confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
            runner=runner,
        )
        self.assertTrue(runner.rebind_blocked)
        self.assertEqual(apk.read_bytes(), b"ancestor-locked-apk")

    def test_prepare_fails_closed_without_windows_stable_handle_support(self) -> None:
        runner = self.runner()
        with mock.patch.object(module, "_IS_WINDOWS", False, create=True):
            with self.assertRaisesRegex(module.DeviceError, "Windows"):
                module.prepare_device(
                    self.target,
                    self.candidate,
                    self.identity,
                    confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
                    runner=runner,
                )
        self.assertEqual(runner.calls, [])

    def test_prepare_installed_package_clears_uninstalls_and_installs_only_exact_target(self) -> None:
        runner = self.runner(installed=True)
        report = module.prepare_device(
            self.target,
            self.candidate,
            self.identity,
            confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
            runner=runner,
        )
        self.assertEqual(report.package_name, "com.leiting.wf")
        self.assertEqual(
            [call for call in runner.destructive_calls],
            [
                (self.serial, ("shell", "pm", "clear", "com.leiting.wf")),
                (self.serial, ("uninstall", "com.leiting.wf")),
                (self.serial, ("install", str(self.apk))),
            ],
        )
        self.assertFalse(
            any("/sdcard/WorldFlipper" in arg for _, call in runner.destructive_calls for arg in call)
        )

    def test_prepare_absent_package_skips_clear_and_uninstall(self) -> None:
        runner = self.runner(installed=False)
        module.prepare_device(
            self.target,
            self.candidate,
            self.identity,
            confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
            runner=runner,
        )
        self.assertEqual(runner.destructive_calls, [(self.serial, ("install", str(self.apk)))])

    def test_prepare_stops_when_mutating_adb_command_does_not_report_success(self) -> None:
        class FailedClearRunner(FakeAdbRunner):
            def adb(self, serial: str | None, *args: str) -> str:
                if args == ("shell", "pm", "clear", "com.leiting.wf"):
                    self.calls.append((serial, tuple(args)))
                    return "Failed\n"
                return super().adb(serial, *args)

        runner = FailedClearRunner(serial=self.serial)
        with self.assertRaisesRegex(module.DeviceError, "package clear"):
            module.prepare_device(
                self.target,
                self.candidate,
                self.identity,
                confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
                runner=runner,
            )
        self.assertEqual(
            runner.destructive_calls,
            [(self.serial, ("shell", "pm", "clear", "com.leiting.wf"))],
        )

    def test_prepare_requires_installed_package_activity_after_install(self) -> None:
        runner = self.runner(installed=False, activity="com.example.other/.MainActivity")
        with self.assertRaisesRegex(module.DeviceError, "activity"):
            module.prepare_device(
                self.target,
                self.candidate,
                self.identity,
                confirm=module.PREPARE_CONFIRM_PREFIX + self.serial,
                runner=runner,
            )

    def test_record_requires_all_ten_checks_in_exact_order_and_true(self) -> None:
        output = self.root / "receipt.json"
        missing = self.checks()
        missing.pop(next(iter(missing)))
        with self.assertRaisesRegex(module.DeviceError, "all manual acceptance checks"):
            module.record_manual_acceptance(self.identity, self.clean_probe(), missing, output)
        false_check = self.checks()
        false_check[next(iter(false_check))] = False
        with self.assertRaisesRegex(module.DeviceError, "all manual acceptance checks"):
            module.record_manual_acceptance(self.identity, self.clean_probe(), false_check, output)
        reversed_checks = dict(reversed(tuple(self.checks().items())))
        with self.assertRaisesRegex(module.DeviceError, "exact order"):
            module.record_manual_acceptance(self.identity, self.clean_probe(), reversed_checks, output)
        self.assertFalse(output.exists())

    def test_record_requires_every_offline_clean_and_crash_gate(self) -> None:
        invalid = {
            "airplane_mode": False,
            "wifi_disabled": False,
            "mobile_disabled": False,
            "no_default_route": False,
            "no_active_network": False,
            "companion_ports_unused": False,
            "save_haxe_present_before": True,
            "dummy_data_present_before": True,
            "fatal_log_lines": ("FATAL EXCEPTION",),
            "package_name": "com.example.other",
        }
        for field, value in invalid.items():
            with self.subTest(field=field):
                output = self.root / f"receipt-{field}.json"
                with self.assertRaises(module.DeviceError):
                    module.record_manual_acceptance(
                        self.identity,
                        self.clean_probe(**{field: value}),
                        self.checks(),
                        output,
                    )
                self.assertFalse(output.exists())

    def test_record_writes_canonical_private_atomic_receipt_and_validate_roundtrips(self) -> None:
        output = self.root / "device-acceptance.json"
        receipt = module.record_manual_acceptance(
            self.identity,
            self.clean_probe(),
            self.checks(),
            output,
        )
        raw = output.read_bytes()
        document = json.loads(raw)
        self.assertEqual(raw, bundle.canonical_json_bytes(document))
        self.assertEqual(document["build_id"], self.identity.build_id)
        self.assertEqual(document["apk_sha256"], self.identity.apk_sha256)
        self.assertEqual(document["data_zip_sha256"], self.identity.data_zip_sha256)
        self.assertEqual(document["evidence_sha256"], self.identity.evidence_sha256)
        self.assertEqual(document["serial_digest"], receipt.serial_digest)
        self.assertTrue(document["accepted_at_utc"].endswith("Z"))
        self.assertNotIn(self.serial.encode(), raw)
        self.assertNotIn(str(self.root).encode(), raw)
        self.assertEqual(module.validate_acceptance_receipt(output, self.identity), receipt)
        self.assertEqual(list(self.root.glob(f".{output.name}.tmp-*")), [])

    def test_record_never_overwrites_existing_output(self) -> None:
        output = self.root / "device-acceptance.json"
        output.write_bytes(b"keep-me")
        with self.assertRaisesRegex(module.DeviceError, "already exists"):
            module.record_manual_acceptance(
                self.identity,
                self.clean_probe(),
                self.checks(),
                output,
            )
        self.assertEqual(output.read_bytes(), b"keep-me")
        self.assertEqual(list(self.root.glob(f".{output.name}.tmp-*")), [])

    def test_record_link_then_error_removes_only_its_new_publication(self) -> None:
        output = self.root / "device-acceptance.json"
        real_rename = module._rename_receipt_handle_no_replace

        def rename_then_error(staged: object, parent: object, destination_name: str) -> None:
            real_rename(staged, parent, destination_name)
            raise OSError("injected after link")

        with mock.patch.object(
            module, "_rename_receipt_handle_no_replace", side_effect=rename_then_error
        ):
            with self.assertRaisesRegex(module.DeviceError, "atomically"):
                module.record_manual_acceptance(
                    self.identity,
                    self.clean_probe(),
                    self.checks(),
                    output,
                )
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob(f".{output.name}.tmp-*")), [])

    @unittest.skipUnless(sys.platform == "win32", "requires Windows directory handles")
    def test_record_parent_handle_blocks_real_directory_rebind_during_publication(self) -> None:
        parent = self.root / "receipts"
        parent.mkdir()
        moved = self.root / "receipts-moved"
        output = parent / "device-acceptance.json"
        real_rename = module._rename_receipt_handle_no_replace
        observations: list[bool] = []

        def race(staged: object, owned_parent: object, destination_name: str) -> None:
            try:
                module.os.replace(parent, moved)
            except OSError:
                observations.append(True)
            else:
                observations.append(False)
                module.os.replace(moved, parent)
            real_rename(staged, owned_parent, destination_name)

        with mock.patch.object(module, "_rename_receipt_handle_no_replace", side_effect=race):
            module.record_manual_acceptance(
                self.identity, self.clean_probe(), self.checks(), output
            )
        self.assertEqual(observations, [True])
        self.assertTrue(output.is_file())

    @unittest.skipUnless(sys.platform == "win32", "requires Windows reparse semantics")
    def test_record_rejects_real_ancestor_directory_symlink(self) -> None:
        real_tree = self.root / "real-receipt-tree"
        real_parent = real_tree / "receipts"
        real_parent.mkdir(parents=True)
        alias_tree = self.root / "receipt-tree-alias"
        create_directory_junction(alias_tree, real_tree)
        output = alias_tree / "receipts" / "device-acceptance.json"

        with self.assertRaisesRegex(module.DeviceError, "reparse"):
            module.record_manual_acceptance(
                self.identity, self.clean_probe(), self.checks(), output
            )
        self.assertFalse((real_parent / output.name).exists())

    @unittest.skipUnless(sys.platform == "win32", "requires Windows directory handles")
    def test_record_parent_chain_blocks_real_ancestor_rebind_during_publication(self) -> None:
        outer = self.root / "receipt-outer"
        parent = outer / "receipts"
        parent.mkdir(parents=True)
        moved = self.root / "receipt-outer-moved"
        output = parent / "device-acceptance.json"
        real_rename = module._rename_receipt_handle_no_replace
        observations: list[bool] = []

        def race(staged: object, owned_parent: object, destination_name: str) -> None:
            try:
                module.os.replace(outer, moved)
            except OSError:
                observations.append(True)
            else:
                observations.append(False)
                module.os.replace(moved, outer)
            real_rename(staged, owned_parent, destination_name)

        with mock.patch.object(module, "_rename_receipt_handle_no_replace", side_effect=race):
            module.record_manual_acceptance(
                self.identity, self.clean_probe(), self.checks(), output
            )
        self.assertEqual(observations, [True])
        module.validate_acceptance_receipt(output, self.identity)

    @unittest.skipUnless(sys.platform == "win32", "requires Windows native handles")
    def test_record_creates_and_renames_only_relative_to_stable_parent_handle(self) -> None:
        output = self.root / "receipts" / "device-acceptance.json"
        output.parent.mkdir()
        real_create = module._nt_create_file_relative
        real_rename = module._rename_file_handle_relative_no_replace
        observations: list[tuple[str, int, str]] = []

        def create(parent_handle: int, name: str) -> int:
            observations.append(("create", parent_handle, name))
            self.assertEqual(Path(name).name, name)
            self.assertFalse(Path(name).is_absolute())
            return real_create(parent_handle, name)

        def rename(file_handle: int, parent_handle: int, name: str) -> None:
            observations.append(("rename", parent_handle, name))
            self.assertGreater(file_handle, 0)
            self.assertEqual(name, output.name)
            self.assertEqual(Path(name).name, name)
            self.assertFalse(Path(name).is_absolute())
            real_rename(file_handle, parent_handle, name)

        with (
            mock.patch.object(module, "_nt_create_file_relative", side_effect=create),
            mock.patch.object(
                module, "_rename_file_handle_relative_no_replace", side_effect=rename
            ),
        ):
            module.record_manual_acceptance(
                self.identity, self.clean_probe(), self.checks(), output
            )
        self.assertEqual([item[0] for item in observations], ["create", "rename"])
        self.assertEqual(observations[0][1], observations[1][1])
        module.validate_acceptance_receipt(output, self.identity)

    @unittest.skipUnless(sys.platform == "win32", "requires Windows file sharing semantics")
    def test_record_staging_handle_blocks_real_write_and_replacement_races(self) -> None:
        output = self.root / "device-acceptance.json"
        replacement = self.root / "replacement-receipt.json"
        replacement.write_bytes(b"competitor")
        real_rename = module._rename_receipt_handle_no_replace
        observations: list[str] = []

        def race(staged: object, owned_parent: object, destination_name: str) -> None:
            try:
                with staged.path.open("r+b"):
                    pass
            except OSError:
                observations.append("write-blocked")
            try:
                module.os.replace(replacement, staged.path)
            except OSError:
                observations.append("replace-blocked")
            real_rename(staged, owned_parent, destination_name)

        with mock.patch.object(module, "_rename_receipt_handle_no_replace", side_effect=race):
            module.record_manual_acceptance(
                self.identity, self.clean_probe(), self.checks(), output
            )
        self.assertEqual(observations, ["write-blocked", "replace-blocked"])
        module.validate_acceptance_receipt(output, self.identity)

    @unittest.skipUnless(sys.platform == "win32", "requires Windows file sharing semantics")
    def test_record_no_replace_preserves_competing_destination_and_handle_cleans_stage(self) -> None:
        output = self.root / "device-acceptance.json"
        real_rename = module._rename_receipt_handle_no_replace

        def compete(staged: object, owned_parent: object, destination_name: str) -> None:
            output.write_bytes(b"competitor")
            real_rename(staged, owned_parent, destination_name)

        with mock.patch.object(module, "_rename_receipt_handle_no_replace", side_effect=compete):
            with self.assertRaisesRegex(module.DeviceError, "already exists"):
                module.record_manual_acceptance(
                    self.identity, self.clean_probe(), self.checks(), output
                )
        self.assertEqual(output.read_bytes(), b"competitor")
        self.assertEqual(list(self.root.glob(f".{output.name}.tmp-*")), [])

    @unittest.skipUnless(sys.platform == "win32", "requires Windows file sharing semantics")
    def test_record_published_handle_blocks_replacement_until_canonical_reverification(self) -> None:
        output = self.root / "device-acceptance.json"
        replacement = self.root / "replacement-receipt.json"
        replacement.write_bytes(b"competitor")
        real_verify = module._require_published_receipt_binding
        observations: list[bool] = []

        def race(staged: object, destination: Path, expected: bytes) -> None:
            try:
                module.os.replace(replacement, destination)
            except OSError:
                observations.append(True)
            else:
                observations.append(False)
            real_verify(staged, destination, expected)

        with mock.patch.object(module, "_require_published_receipt_binding", side_effect=race):
            module.record_manual_acceptance(
                self.identity, self.clean_probe(), self.checks(), output
            )
        self.assertEqual(observations, [True])
        module.validate_acceptance_receipt(output, self.identity)

    def test_record_fails_closed_without_windows_handle_publication(self) -> None:
        output = self.root / "device-acceptance.json"
        with mock.patch.object(module, "_IS_WINDOWS", False, create=True):
            with self.assertRaisesRegex(module.DeviceError, "Windows"):
                module.record_manual_acceptance(
                    self.identity, self.clean_probe(), self.checks(), output
                )
        self.assertFalse(output.exists())

    @unittest.skipUnless(sys.platform == "win32", "requires Windows file sharing semantics")
    def test_validate_holds_one_receipt_handle_that_blocks_write_and_replace(self) -> None:
        output = self.root / "device-acceptance.json"
        replacement = self.root / "replacement-receipt.json"
        replacement.write_bytes(b"competitor")
        expected = module.record_manual_acceptance(
            self.identity, self.clean_probe(), self.checks(), output
        )
        original = output.read_bytes()
        real_read = module._read_locked_file_bytes
        observations: list[str] = []

        def race(locked: object, *, label: str, max_bytes: int) -> bytes:
            try:
                with output.open("r+b"):
                    pass
            except OSError:
                observations.append("write-blocked")
            try:
                module.os.replace(replacement, output)
            except OSError:
                observations.append("replace-blocked")
            return real_read(locked, label=label, max_bytes=max_bytes)

        with mock.patch.object(module, "_read_locked_file_bytes", side_effect=race):
            actual = module.validate_acceptance_receipt(output, self.identity)
        self.assertEqual(actual, expected)
        self.assertEqual(observations, ["write-blocked", "replace-blocked"])
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(replacement.read_bytes(), b"competitor")

    def test_validate_fails_closed_without_windows_handle_reading(self) -> None:
        output = self.root / "device-acceptance.json"
        module.record_manual_acceptance(self.identity, self.clean_probe(), self.checks(), output)
        with mock.patch.object(module, "_IS_WINDOWS", False, create=True):
            with self.assertRaisesRegex(module.DeviceError, "Windows"):
                module.validate_acceptance_receipt(output, self.identity)

    def test_public_receipt_paths_normalize_pathlike_failures_to_device_error(self) -> None:
        class BrokenPath:
            def __fspath__(self) -> str:
                raise RuntimeError("pathlike-internal-detail")

        broken = BrokenPath()
        with self.assertRaises(module.DeviceError) as record_error:
            module.record_manual_acceptance(
                self.identity,
                self.clean_probe(),
                self.checks(),
                broken,  # type: ignore[arg-type]
            )
        with self.assertRaises(module.DeviceError) as validate_error:
            module.validate_acceptance_receipt(broken, self.identity)  # type: ignore[arg-type]
        self.assertNotIn("pathlike-internal-detail", str(record_error.exception))
        self.assertNotIn("pathlike-internal-detail", str(validate_error.exception))

    def test_failed_publication_attaches_parent_close_failure_to_primary_error(self) -> None:
        output = self.root / "device-acceptance.json"
        primary = module.DeviceError("primary publication failure")
        close = module.DeviceError("parent close failure")
        fake_parent = module._OwnedDirectory(output.parent, 123, (1, 2))
        with (
            mock.patch.object(module, "_open_directory_chain", return_value=(fake_parent,)),
            mock.patch.object(module, "_require_directory_chain_binding"),
            mock.patch.object(module, "_create_receipt_staging", side_effect=primary),
            mock.patch.object(module, "_close_directory_chain", side_effect=close),
        ):
            with self.assertRaisesRegex(module.DeviceError, "primary publication failure") as raised:
                module.record_manual_acceptance(
                    self.identity, self.clean_probe(), self.checks(), output
                )
        notes = getattr(raised.exception, "__notes__", ())
        self.assertTrue(any("parent" in note and "close" in note for note in notes))

    def test_failed_directory_close_keeps_owned_handle_reference(self) -> None:
        owned = module._OwnedDirectory(self.root, 123, (1, 2))
        kernel32 = mock.Mock()
        kernel32.CloseHandle.return_value = False
        with mock.patch.object(
            module, "_windows_file_api", return_value=(None, None, kernel32)
        ):
            with self.assertRaisesRegex(module.DeviceError, "close"):
                module._close_owned_directory(owned)
        self.assertEqual(owned.raw_handle, 123)
        kernel32.CloseHandle.assert_called_once_with(123)

    def test_validate_rejects_build_and_artifact_hash_drift(self) -> None:
        output = self.root / "device-acceptance.json"
        module.record_manual_acceptance(self.identity, self.clean_probe(), self.checks(), output)
        changed = (
            replace(self.identity, build_id="build-fixture-002"),
            replace(self.identity, apk_sha256="a" * 64),
            replace(self.identity, data_zip_sha256="b" * 64),
            replace(self.identity, evidence_sha256="c" * 64),
        )
        for identity in changed:
            with self.subTest(identity=identity):
                with self.assertRaisesRegex(module.DeviceError, "mismatch"):
                    module.validate_acceptance_receipt(output, identity)

    def test_validate_rejects_noncanonical_unknown_missing_or_duplicate_json(self) -> None:
        output = self.root / "device-acceptance.json"
        module.record_manual_acceptance(self.identity, self.clean_probe(), self.checks(), output)
        document = json.loads(output.read_bytes())
        variants = []
        variants.append(json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8"))
        unknown = dict(document)
        unknown["workspace"] = "relative"
        variants.append(bundle.canonical_json_bytes(unknown))
        missing = dict(document)
        missing.pop("probe")
        variants.append(bundle.canonical_json_bytes(missing))
        duplicate = output.read_text("utf-8").replace(
            '"schema_version":1', '"schema_version":1,"schema_version":1', 1
        ).encode("utf-8")
        variants.append(duplicate)
        for index, payload in enumerate(variants):
            with self.subTest(index=index):
                tampered = self.root / f"tampered-{index}.json"
                tampered.write_bytes(payload)
                with self.assertRaises(module.DeviceError):
                    module.validate_acceptance_receipt(tampered, self.identity)

    def test_validate_rejects_non_utc_missing_check_dirty_probe_and_absolute_path(self) -> None:
        output = self.root / "device-acceptance.json"
        module.record_manual_acceptance(self.identity, self.clean_probe(), self.checks(), output)
        base = json.loads(output.read_bytes())
        variants: list[tuple[str, dict[str, object], str]] = []
        non_utc = json.loads(json.dumps(base))
        non_utc["accepted_at_utc"] = "2026-07-21T10:00:00+10:00"
        variants.append(("non-utc", non_utc, "UTC"))
        missing_check = json.loads(json.dumps(base))
        missing_check["checks"].pop(module.REQUIRED_MANUAL_CHECKS[0])
        variants.append(("missing-check", missing_check, "manual"))
        dirty = json.loads(json.dumps(base))
        dirty["probe"]["dummy_data_present_before"] = True
        variants.append(("dirty", dirty, "clean"))
        absolute = json.loads(json.dumps(base))
        absolute["unexpected"] = str(self.root / "secret")
        variants.append(("absolute", absolute, "absolute path"))
        for name, document, message in variants:
            with self.subTest(name=name):
                path = self.root / f"{name}.json"
                if name == "absolute":
                    payload = (
                        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                        + "\n"
                    ).encode("utf-8")
                else:
                    payload = bundle.canonical_json_bytes(document)
                path.write_bytes(payload)
                with self.assertRaisesRegex(module.DeviceError, message):
                    module.validate_acceptance_receipt(path, self.identity)


if __name__ == "__main__":
    unittest.main()

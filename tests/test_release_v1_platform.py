from __future__ import annotations

import os
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from wf_release_v1.errors import ReleaseError
from wf_release_v1.platform import (
    CaptureStats,
    LaunchEnvironment,
    ManagedProcess,
    ProcessIdentity,
    WindowsPlatformAdapter,
    build_child_environment,
)
from wf_release_v1.target import LaunchSpec


OPERATION_ID = "20260812T010203.456789Z-00112233445566778899aabbccddeeff"


class LaunchEnvironmentTests(unittest.TestCase):
    def test_child_environment_is_host_owned_exact_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            server = root / "server"
            data = root / "data"
            cdn = root / "content" / "candidate"
            modes = root / "modes" / "candidate"
            binding = runtime / "node_modules" / "better_sqlite3.node"
            for path in (runtime / "node" / "bin", runtime / "node_modules", server, data, cdn, modes):
                path.mkdir(parents=True, exist_ok=True)
            executable = runtime / "node" / "bin" / "node.exe"
            prepare_entry = server / "out" / "content" / "sync" / "entry.js"
            server_entry = server / "out" / "cn-server.js"
            prepare_entry.parent.mkdir(parents=True)
            for path in (executable, prepare_entry, server_entry, binding):
                path.write_bytes(b"fixture")

            launch = LaunchSpec(executable, prepare_entry, server_entry, server)
            environment = LaunchEnvironment(
                data,
                cdn,
                modes,
                binding,
                listen_host="0.0.0.0",
                listen_port=8123,
                public_host="10.0.0.130",
                session_host="0.0.0.0",
                session_port=8003,
                session_public_host="10.0.0.130",
            )
            base = {
                "SECRET_TOKEN": "inherited-only",
                "CN_ADMIN_TOKEN": "admin-token-must-stay-process-only",
                "EMBEDDED_RUNTIME": "0",
                "DATA_DIR": "stale-data",
                "CDN_DIR": "stale-cdn",
                "MODES_DIR": "stale-modes",
                "NODE_PATH": "stale-node-path",
                "BETTER_SQLITE3_NATIVE_BINDING": "stale-binding",
                "WDFP_DATABASE_DIR": "forbidden",
                "CONTENT_DIR": "forbidden",
                "CONTENT_STORE_DIR": "forbidden",
                "CONTENT_STATE_DIR": "forbidden",
                "CONTENT_RUNTIME_DIR": "forbidden",
                "CN_LISTEN_HOST": "127.0.0.1",
                "CN_LISTEN_PORT": "9001",
                "CN_PUBLIC_HOST": "127.0.0.1",
                "SESSION_HOST": "127.0.0.1",
                "SESSION_PORT": "9003",
                "SESSION_PUBLIC_HOST": "127.0.0.1",
                "CDN_BASE_URL": "http://127.0.0.1:9001/patch/cn",
                "MULTI_MODE": "client",
                "WF_RELEASE_OPERATION_ID": "stale-operation",
            }

            actual = build_child_environment(launch, environment, base)

            self.assertEqual("inherited-only", actual["SECRET_TOKEN"])
            self.assertEqual(
                "admin-token-must-stay-process-only",
                actual["CN_ADMIN_TOKEN"],
            )
            self.assertEqual("1", actual["EMBEDDED_RUNTIME"])
            self.assertEqual("local", actual["ASSET_MODE"])
            self.assertEqual(os.fspath(data), actual["DATA_DIR"])
            self.assertEqual(os.fspath(cdn), actual["CDN_DIR"])
            self.assertEqual(os.fspath(modes), actual["MODES_DIR"])
            self.assertEqual(os.fspath(runtime / "node_modules"), actual["NODE_PATH"])
            self.assertEqual(os.fspath(binding), actual["BETTER_SQLITE3_NATIVE_BINDING"])
            self.assertEqual("0.0.0.0", actual["CN_LISTEN_HOST"])
            self.assertEqual("8123", actual["CN_LISTEN_PORT"])
            self.assertEqual("10.0.0.130", actual["CN_PUBLIC_HOST"])
            self.assertEqual("0.0.0.0", actual["SESSION_HOST"])
            self.assertEqual("8003", actual["SESSION_PORT"])
            self.assertEqual("10.0.0.130", actual["SESSION_PUBLIC_HOST"])
            self.assertEqual(
                "http://10.0.0.130:8123/patch/cn",
                actual["CDN_BASE_URL"],
            )
            self.assertEqual("embedded", actual["MULTI_MODE"])
            self.assertNotIn("WF_RELEASE_OPERATION_ID", actual)
            for forbidden in (
                "WDFP_DATABASE_DIR", "CONTENT_DIR", "CONTENT_STORE_DIR",
                "CONTENT_STATE_DIR", "CONTENT_RUNTIME_DIR",
            ):
                self.assertNotIn(forbidden, actual)
            self.assertEqual(base["SECRET_TOKEN"], "inherited-only")

    def test_environment_rejects_unsafe_or_ambiguous_network_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, cdn, modes = root / "data", root / "cdn", root / "modes"
            for path in (data, cdn, modes):
                path.mkdir()
            invalid = (
                {"listen_host": "127.0.0.1"},
                {"listen_host": "example.invalid"},
                {"listen_host": "192.0.2.1"},
                {"listen_port": 0},
                {"listen_port": True},
                {"public_host": "0.0.0.0"},
                {"public_host": "192.0.2.1"},
                {"session_host": "127.0.0.1"},
                {"session_port": 65536},
                {"session_port": 8001},
                {"session_public_host": "0.0.0.0"},
                {"session_public_host": "10.0.0.2"},
            )
            for values in invalid:
                with self.subTest(values=values), self.assertRaises(ReleaseError) as caught:
                    LaunchEnvironment(data, cdn, modes, **values)
                self.assertEqual("WFREL_PLATFORM_INVALID", caught.exception.code)

    def test_environment_rejects_invalid_roots_and_does_not_guess_a_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            absolute = root / "absolute"
            absolute.mkdir()
            for label, values in (
                ("relative data", (Path("relative"), absolute, absolute, None)),
                ("relative CDN", (absolute, Path("relative"), absolute, None)),
                ("relative modes", (absolute, absolute, Path("relative"), None)),
                ("missing binding", (absolute, absolute, absolute, root / "missing.node")),
            ):
                with self.subTest(label=label), self.assertRaises(ReleaseError) as caught:
                    LaunchEnvironment(*values)
                self.assertEqual("WFREL_PLATFORM_INVALID", caught.exception.code)

            runtime = root / "runtime"
            server = root / "server"
            cdn = root / "cdn"
            modes = root / "modes"
            (runtime / "node" / "bin").mkdir(parents=True)
            (runtime / "node_modules").mkdir()
            server.mkdir()
            cdn.mkdir()
            modes.mkdir()
            executable = runtime / "node" / "bin" / "node.exe"
            executable.write_bytes(b"node")
            launch = LaunchSpec(executable, server / "prepare.js", server / "server.js", server)
            child = build_child_environment(
                launch,
                LaunchEnvironment(absolute, cdn, modes),
                {"BETTER_SQLITE3_NATIVE_BINDING": "stale"},
            )
            self.assertNotIn("BETTER_SQLITE3_NATIVE_BINDING", child)

            for label, values in (
                ("data equals CDN", (absolute, absolute, modes)),
                ("CDN contains modes", (absolute, root, modes)),
            ):
                with self.subTest(label=label):
                    with self.assertRaises(ReleaseError) as caught:
                        LaunchEnvironment(*values)
                    self.assertEqual("WFREL_PLATFORM_INVALID", caught.exception.code)

    def test_environment_rejects_non_directory_and_reparse_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, cdn, modes = root / "data", root / "cdn", root / "modes"
            for path in (data, cdn, modes):
                path.mkdir()
            file_root = root / "not-a-directory"
            file_root.write_bytes(b"file")
            with self.assertRaises(ReleaseError) as caught:
                LaunchEnvironment(file_root, cdn, modes)
            self.assertEqual("WFREL_PLATFORM_INVALID", caught.exception.code)

            linked = root / "linked-cdn"
            try:
                linked.symlink_to(cdn, target_is_directory=True)
            except OSError:
                return
            with self.assertRaises(ReleaseError) as caught:
                LaunchEnvironment(data, linked, modes)
            self.assertEqual("WFREL_PLATFORM_INVALID", caught.exception.code)

    def test_node_path_must_be_the_existing_runtime_pack_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, server = root / "runtime", root / "server"
            data, cdn, modes = root / "data", root / "cdn", root / "modes"
            (runtime / "node" / "bin").mkdir(parents=True)
            for path in (server, data, cdn, modes):
                path.mkdir()
            executable = runtime / "node" / "bin" / "node.exe"
            executable.write_bytes(b"node")
            launch = LaunchSpec(executable, server / "prepare.js", server / "server.js", server)
            with self.assertRaises(ReleaseError) as caught:
                build_child_environment(launch, LaunchEnvironment(data, cdn, modes), {})
            self.assertEqual("WFREL_PLATFORM_INVALID", caught.exception.code)


class _FakeBackend:
    def __init__(self, executable: Path) -> None:
        self.executable = executable
        self.next_pid = 4100
        self.next_running = True
        self.next_exit_code = 0
        self.next_stdout = b""
        self.next_stderr = b""
        self.spawn_error: OSError | None = None
        self.open_exited_handles = False
        self.before_wait = None
        self.processes: dict[int, SimpleNamespace] = {}
        self.calls: list[tuple[object, ...]] = []
        self._handle_serial = 0

    def _new_handle(self, pid: int, source: str) -> tuple[str, int, int]:
        self._handle_serial += 1
        return source, pid, self._handle_serial

    def spawn(
        self,
        command: tuple[str, ...],
        cwd: Path,
        environment: dict[str, str],
        *,
        capture_output: bool = True,
    ) -> object:
        self.calls.append(("spawn", command, cwd, dict(environment), capture_output))
        if self.spawn_error is not None:
            raise self.spawn_error
        pid = self.next_pid
        self.next_pid += 1
        state = SimpleNamespace(
            creation_time=132_750_000_000_000_000 + pid,
            executable=self.executable,
            running=self.next_running,
            exit_code=self.next_exit_code,
            graceful=False,
        )
        self.processes[pid] = state
        return SimpleNamespace(
            pid=pid,
            handle=self._new_handle(pid, "spawn"),
            stdout=BytesIO(self.next_stdout) if capture_output else None,
            stderr=BytesIO(self.next_stderr) if capture_output else None,
            owner=object(),
        )

    def open_process(self, pid: int) -> object | None:
        self.calls.append(("open", pid))
        state = self.processes.get(pid)
        if state is None or (not state.running and not self.open_exited_handles):
            return None
        handle = self._new_handle(pid, "open")
        self.calls.append(("opened", pid, handle))
        return handle

    def identity(self, handle: object) -> ProcessIdentity:
        pid = handle[1]  # type: ignore[index]
        self.calls.append(("identity", handle))
        state = self.processes[pid]
        if not state.running:
            raise OSError("exited process image is unavailable")
        return ProcessIdentity(state.creation_time, state.executable)

    def wait(self, handle: object, timeout: float) -> bool:
        pid = handle[1]  # type: ignore[index]
        self.calls.append(("wait", handle, timeout))
        if self.before_wait is not None:
            self.before_wait(handle, timeout)
        return not self.processes[pid].running

    def exit_code(self, handle: object) -> int:
        pid = handle[1]  # type: ignore[index]
        self.calls.append(("exit_code", handle))
        return self.processes[pid].exit_code

    def send_ctrl_break(self, pid: int) -> None:
        self.calls.append(("break", pid))
        state = self.processes[pid]
        if state.graceful:
            state.running = False

    def terminate(self, handle: object) -> None:
        pid = handle[1]  # type: ignore[index]
        self.calls.append(("terminate", handle))
        self.processes[pid].running = False
        self.processes[pid].exit_code = 1

    def close(self, handle: object) -> None:
        self.calls.append(("close", handle))


class WindowsPlatformAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.runtime = self.root / "runtime"
        self.server = self.root / "server"
        self.state = self.root / "state"
        self.data = self.root / "data"
        self.cdn = self.root / "cdn"
        self.modes = self.root / "modes"
        for path in (
            self.runtime / "node" / "bin", self.runtime / "node_modules",
            self.server / "out" / "content" / "sync", self.state,
            self.data, self.cdn, self.modes,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.executable = self.runtime / "node" / "bin" / "node.exe"
        self.prepare_entry = self.server / "out" / "content" / "sync" / "entry.js"
        self.server_entry = self.server / "out" / "cn-server.js"
        for path in (self.executable, self.prepare_entry, self.server_entry):
            path.write_bytes(path.name.encode("ascii"))
        self.launch = LaunchSpec(self.executable, self.prepare_entry, self.server_entry, self.server)
        self.environment = LaunchEnvironment(self.data, self.cdn, self.modes)
        self.backend = _FakeBackend(self.executable)
        self.adapter = WindowsPlatformAdapter(
            self.state,
            self.executable,
            backend=self.backend,
            base_environment={
                "SECRET_TOKEN": "inherited",
                "CN_ADMIN_TOKEN": "admin-token-must-stay-process-only",
            },
            capture_limit=32,
            startup_grace_seconds=0.0,
            prepare_timeout_seconds=1.0,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _start(self) -> ManagedProcess:
        return self.adapter.start_server(self.launch, self.environment, OPERATION_ID)

    def test_start_persists_exact_private_identity_and_current_process_revalidates_it(self) -> None:
        process = self._start()
        raw = (self.state / "process.json").read_bytes()
        self.assertEqual(
            {
                "creationTime": process.creation_time,
                "executableSha256": process.executable_sha256,
                "operationId": OPERATION_ID,
                "pid": process.pid,
                "schemaVersion": 1,
            },
            json.loads(raw),
        )
        for private in (
            self.root,
            self.executable,
            self.server_entry,
            "SECRET_TOKEN",
            "inherited",
            "CN_ADMIN_TOKEN",
            "admin-token-must-stay-process-only",
        ):
            self.assertNotIn(os.fspath(private).encode("utf-8"), raw)
        self.assertEqual(process, self.adapter.current_process())
        spawn = next(call for call in self.backend.calls if call[0] == "spawn")
        self.assertEqual((os.fspath(self.executable), os.fspath(self.server_entry)), spawn[1])
        self.assertEqual(self.server, spawn[2])
        self.assertEqual(OPERATION_ID, spawn[3]["WF_RELEASE_OPERATION_ID"])
        self.assertFalse(spawn[4])
        self.assertEqual(
            "admin-token-must-stay-process-only",
            spawn[3]["CN_ADMIN_TOKEN"],
        )

    def test_current_process_clears_an_exact_record_when_win32_opens_a_signaled_handle(self) -> None:
        self.backend.next_stdout = b"done"
        self.backend.next_stderr = b"fail"
        process = self._start()
        self.backend.open_exited_handles = True
        self.backend.processes[process.pid].running = False
        self.backend.calls.clear()

        self.assertIsNone(self.adapter.current_process())
        self.assertFalse((self.state / "process.json").exists())
        opened = next(call for call in self.backend.calls if call[0] == "opened")
        waited = next(call for call in self.backend.calls if call[0] == "wait")
        closed = next(call for call in self.backend.calls if call[0] == "close")
        self.assertEqual(opened[1], process.pid)
        self.assertEqual(opened[2], waited[1])
        self.assertEqual(opened[2], closed[1])
        self.assertEqual(0.0, waited[2])
        self.assertFalse(any(call[0] == "identity" for call in self.backend.calls))
        self.assertEqual(CaptureStats(0, 0, False, False), self.adapter.last_capture_stats)

    def test_signaled_handle_cleanup_preserves_a_drifted_process_record(self) -> None:
        process = self._start()
        self.backend.open_exited_handles = True
        self.backend.processes[process.pid].running = False
        replacement = {
            "schemaVersion": 1,
            "operationId": process.operation_id,
            "pid": process.pid,
            "creationTime": process.creation_time,
            "executableSha256": "f" * 64,
        }

        def drift_state(_handle: object, timeout: float) -> None:
            self.assertEqual(0.0, timeout)
            (self.state / "process.json").write_text(
                json.dumps(replacement), encoding="utf-8"
            )

        self.backend.before_wait = drift_state
        with self.assertRaises(ReleaseError) as caught:
            self.adapter.current_process()
        self.assertEqual("WFREL_PROCESS_IDENTITY", caught.exception.code)
        self.assertEqual(replacement, json.loads((self.state / "process.json").read_bytes()))

    def test_live_process_revalidates_the_runtime_executable_sha(self) -> None:
        self._start()
        self.executable.write_bytes(b"changed-runtime-image")
        before = len(self.backend.calls)

        with self.assertRaises(ReleaseError) as caught:
            self.adapter.current_process()
        self.assertEqual("WFREL_PROCESS_IDENTITY", caught.exception.code)
        self.assertTrue((self.state / "process.json").exists())
        self.assertFalse(
            any(
                call[0] in {"break", "terminate"}
                for call in self.backend.calls[before:]
            )
        )

    def test_pid_reuse_identity_drift_and_foreign_process_fail_before_signal(self) -> None:
        process = self._start()
        state = self.backend.processes[process.pid]
        for label, mutate, expected_code in (
            ("PID reuse", lambda: setattr(state, "creation_time", state.creation_time + 1), "WFREL_PROCESS_IDENTITY"),
            ("image drift", lambda: setattr(state, "executable", self.server_entry), "WFREL_PROCESS_IDENTITY"),
        ):
            original_time, original_path = state.creation_time, state.executable
            mutate()
            with self.subTest(label=label):
                with self.assertRaises(ReleaseError) as caught:
                    self.adapter.current_process()
                self.assertEqual(expected_code, caught.exception.code)
            state.creation_time, state.executable = original_time, original_path

        foreign = ManagedProcess(
            process.pid, process.creation_time, "0" * 64, process.operation_id,
        )
        before = len(self.backend.calls)
        with self.assertRaises(ReleaseError) as caught:
            self.adapter.stop_owned(foreign, 0.1)
        self.assertEqual("WFREL_PROCESS_IDENTITY", caught.exception.code)
        self.assertFalse(any(call[0] in {"break", "terminate"} for call in self.backend.calls[before:]))
        self.assertTrue((self.state / "process.json").exists())

    def test_graceful_and_forced_stop_use_one_verified_handle_and_clear_state(self) -> None:
        for graceful, expected_forced in ((True, False), (False, True)):
            with self.subTest(graceful=graceful):
                process = self._start()
                self.backend.calls.clear()
                self.backend.processes[process.pid].graceful = graceful
                forced = self.adapter.stop_owned(process, 0.1)
                self.assertEqual(expected_forced, forced)
                relevant = [call for call in self.backend.calls if call[0] in {"identity", "break", "wait", "terminate"}]
                self.assertEqual("identity", relevant[0][0])
                self.assertEqual(("break", process.pid), relevant[1])
                terminate = [call for call in relevant if call[0] == "terminate"]
                self.assertEqual(expected_forced, bool(terminate))
                if terminate:
                    identity_handle = relevant[0][1]
                    self.assertEqual(identity_handle, terminate[0][1])
                self.assertFalse((self.state / "process.json").exists())

    def test_long_lived_server_does_not_depend_on_parent_owned_output_pipes(self) -> None:
        self.backend.next_stdout = b"o" * 100
        self.backend.next_stderr = b"e" * 100
        process = self._start()
        spawn = next(call for call in self.backend.calls if call[0] == "spawn")
        self.assertFalse(spawn[4])
        self.assertNotIn(process.pid, self.adapter._captures)
        self.backend.processes[process.pid].graceful = True
        self.assertFalse(self.adapter.stop_owned(process, 0.1))
        self.assertEqual(CaptureStats(0, 0, False, False), self.adapter.last_capture_stats)

    def test_prepare_and_start_failures_are_stable_bounded_and_leave_no_process_state(self) -> None:
        self.backend.next_running = False
        self.backend.next_stdout = b"o" * 100
        self.backend.next_stderr = b"e" * 100
        self.adapter.prepare_content(self.launch, self.environment)
        self.assertEqual(CaptureStats(32, 32, True, True), self.adapter.last_capture_stats)
        prepare_spawn = next(call for call in self.backend.calls if call[0] == "spawn")
        self.assertEqual((os.fspath(self.executable), os.fspath(self.prepare_entry)), prepare_spawn[1])
        self.assertTrue(prepare_spawn[4])

        self.backend.next_exit_code = 7
        with self.assertRaises(ReleaseError) as caught:
            self.adapter.prepare_content(self.launch, self.environment)
        self.assertEqual("WFREL_PROCESS_START", caught.exception.code)

        self.backend.next_exit_code = 3
        with self.assertRaises(ReleaseError) as caught:
            self._start()
        self.assertEqual("WFREL_PROCESS_START", caught.exception.code)
        self.assertFalse((self.state / "process.json").exists())

        self.backend.spawn_error = OSError("C:/private/spawn failure")
        with self.assertRaises(ReleaseError) as caught:
            self._start()
        self.assertEqual("WFREL_PROCESS_START", caught.exception.code)
        self.assertNotIn(self.temporary.name, str(caught.exception))

    def test_missing_or_escaping_launch_entries_fail_before_spawn(self) -> None:
        missing = self.server / "out" / "missing.js"
        outside = self.root / "outside.js"
        outside.write_bytes(b"outside")
        for label, launch in (
            ("missing prepare", LaunchSpec(self.executable, missing, self.server_entry, self.server)),
            ("missing server", LaunchSpec(self.executable, self.prepare_entry, missing, self.server)),
            ("escaping prepare", LaunchSpec(self.executable, outside, self.server_entry, self.server)),
        ):
            before = len(self.backend.calls)
            with self.subTest(label=label), self.assertRaises(ReleaseError) as caught:
                self.adapter.prepare_content(launch, self.environment)
            self.assertEqual("WFREL_PLATFORM_INVALID", caught.exception.code)
            self.assertFalse(any(call[0] == "spawn" for call in self.backend.calls[before:]))

    def test_prepare_timeout_terminates_only_the_spawned_handle(self) -> None:
        self.backend.next_running = True
        with self.assertRaises(ReleaseError) as caught:
            self.adapter.prepare_content(self.launch, self.environment)
        self.assertEqual("WFREL_PROCESS_TIMEOUT", caught.exception.code)
        spawn_handle = next(call for call in self.backend.calls if call[0] == "identity")
        terminate = next(call for call in self.backend.calls if call[0] == "terminate")
        self.assertEqual(spawn_handle[1], terminate[1])
        self.assertFalse((self.state / "process.json").exists())

    def test_process_state_is_strict_and_atomic_write_failure_stops_the_child(self) -> None:
        path = self.state / "process.json"
        path.write_text('{"schemaVersion":1,"schemaVersion":1}', encoding="utf-8")
        with self.assertRaises(ReleaseError) as caught:
            self.adapter.current_process()
        self.assertEqual("WFREL_PROCESS_INVALID", caught.exception.code)
        self.assertNotIn(self.temporary.name, str(caught.exception))
        path.unlink()

        path.write_text(
            json.dumps({
                "schemaVersion": 1,
                "operationId": OPERATION_ID,
                "pid": 4100,
                "creationTime": 132750000000004100,
                "executableSha256": "0" * 64,
                "extra": True,
            }),
            encoding="utf-8",
        )
        with self.assertRaises(ReleaseError) as caught:
            self.adapter.current_process()
        self.assertEqual("WFREL_PROCESS_INVALID", caught.exception.code)
        path.unlink()

        with mock.patch(
            "wf_release_v1._platform_state._atomic_write",
            side_effect=OSError("C:/private/process-state-failure"),
        ):
            with self.assertRaises(ReleaseError) as caught:
                self._start()
        self.assertEqual("WFREL_PROCESS_IO", caught.exception.code)
        self.assertFalse(path.exists())
        self.assertTrue(any(call[0] == "terminate" for call in self.backend.calls))

    def test_wait_exited_and_stale_state_never_accept_a_reused_pid(self) -> None:
        process = self._start()
        self.assertFalse(self.adapter.wait_exited(process, 0.01))
        self.backend.processes[process.pid].running = False
        self.assertTrue(self.adapter.wait_exited(process, 0.01))
        self.assertFalse((self.state / "process.json").exists())
        self.assertIsNone(self.adapter.current_process())


if __name__ == "__main__":
    unittest.main()

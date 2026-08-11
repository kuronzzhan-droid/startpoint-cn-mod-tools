from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import sys
import time
import unittest
from unittest import mock

from wf_release_v1._platform_windows import WindowsBackend


@unittest.skipUnless(os.name == "nt", "Win32 process identity requires Windows")
class RealWindowsBackendTests(unittest.TestCase):
    def test_spawn_requests_a_new_process_group_without_detaching_identity(self) -> None:
        backend = WindowsBackend()
        fake = SimpleNamespace(
            pid=4100,
            stdout=BytesIO(),
            stderr=BytesIO(),
            kill=mock.Mock(),
        )
        with (
            mock.patch("wf_release_v1._platform_windows.subprocess.Popen", return_value=fake) as popen,
            mock.patch.object(backend, "open_process", return_value=1234),
        ):
            spawned = backend.spawn((sys.executable, "fixture.py"), Path.cwd(), dict(os.environ))
        self.assertEqual(4100, spawned.pid)
        flags = popen.call_args.kwargs["creationflags"]
        self.assertTrue(flags & subprocess.CREATE_NEW_PROCESS_GROUP)
        self.assertFalse(flags & subprocess.CREATE_NO_WINDOW)

    def test_exact_handle_reports_identity_and_bounds_ctrl_break_with_exact_termination(self) -> None:
        backend = WindowsBackend()
        script = (
            "import signal,sys,time;"
            "signal.signal(signal.SIGBREAK,lambda *_:sys.exit(0));"
            "print('ready',flush=True);time.sleep(30)"
        )
        spawned = backend.spawn((sys.executable, "-c", script), Path.cwd(), dict(os.environ))
        try:
            self.assertEqual(b"ready", spawned.stdout.readline().rstrip(b"\r\n"))
            identity = backend.identity(spawned.handle)
            self.assertGreater(identity.creation_time, 0)
            self.assertTrue(os.path.samefile(identity.executable, sys.executable))
            self.assertFalse(backend.wait(spawned.handle, 0.0))
            backend.send_ctrl_break(spawned.pid)
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline and not backend.wait(spawned.handle, 0.05):
                pass
            if not backend.wait(spawned.handle, 0.0):
                backend.terminate(spawned.handle)
                self.assertTrue(backend.wait(spawned.handle, 5.0))
            self.assertNotEqual(259, backend.exit_code(spawned.handle))
        finally:
            if not backend.wait(spawned.handle, 0.0):
                backend.terminate(spawned.handle)
                backend.wait(spawned.handle, 5.0)
            spawned.stdout.close()
            spawned.stderr.close()
            backend.close(spawned.handle)
            spawned.owner.wait(timeout=5.0)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Fail-closed regressions for the local CN listener status probe."""
from __future__ import annotations

import errno
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_local_server_status as status


class LocalServerStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.saved = {
            name: os.environ.pop(name, None)
            for name in ("CN_LISTEN_HOST", "CN_LISTEN_PORT")
        }

    def tearDown(self) -> None:
        for name, value in self.saved.items():
            os.environ.pop(name, None)
            if value is not None:
                os.environ[name] = value

    def test_invalid_config_is_not_classified_as_stopped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".env").write_text(
                "CN_LISTEN_PORT=not-a-port\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(status.ServerStatusError, "invalid port"):
                status.server_running(root)

    def test_process_endpoint_overrides_dotenv_and_normalizes_wildcard(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".env").write_text(
                "CN_LISTEN_HOST=bad.invalid\nCN_LISTEN_PORT=wrong\n",
                encoding="utf-8",
            )
            os.environ["CN_LISTEN_HOST"] = "0.0.0.0"
            os.environ["CN_LISTEN_PORT"] = "8123"
            self.assertEqual(("127.0.0.1", 8123), status._endpoint(root))

    def test_connection_refused_is_classified_as_stopped(self):
        root = Path("fixture")
        refused = ConnectionRefusedError(errno.ECONNREFUSED, "refused")
        with mock.patch.object(status, "_endpoint", return_value=("127.0.0.1", 1)):
            with mock.patch.object(
                status.socket, "create_connection", side_effect=refused
            ):
                with mock.patch.object(status, "listening_ports") as ports:
                    self.assertFalse(status.server_running(root))
                ports.assert_not_called()

    def test_ambiguous_connect_is_settled_by_the_local_listener_table(self):
        # A firewall that drops instead of refusing makes every closed port
        # time out.  Treating that as unknown forever left this unable to ever
        # report "stopped", so the local listener table settles it.
        root = Path("fixture")
        for error in (
            socket.timeout("timed out"),
            OSError(errno.ENETUNREACH, "unreachable"),
        ):
            with self.subTest(error=error), mock.patch.object(
                status, "_endpoint", return_value=("127.0.0.1", 8001)
            ), mock.patch.object(
                status.socket, "create_connection", side_effect=error
            ):
                with mock.patch.object(
                    status, "listening_ports", return_value={80, 443}
                ):
                    self.assertFalse(status.server_running(root))
                with mock.patch.object(
                    status, "listening_ports", return_value={80, 8001}
                ):
                    self.assertTrue(status.server_running(root))
                with mock.patch.object(
                    status,
                    "listening_ports",
                    side_effect=status.ServerStatusError("no table"),
                ):
                    with self.assertRaises(status.ServerStatusError):
                        status.server_running(root)

    def test_a_reachable_endpoint_is_running_without_consulting_the_table(self):
        root = Path("fixture")
        with mock.patch.object(
            status, "_endpoint", return_value=("127.0.0.1", 8001)
        ), mock.patch.object(
            status.socket, "create_connection", mock.mock_open()
        ), mock.patch.object(status, "listening_ports") as ports:
            self.assertTrue(status.server_running(root))
        ports.assert_not_called()

    def test_listener_table_sees_a_real_socket_and_misses_a_closed_port(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            self.assertIn(port, status.listening_ports())
        finally:
            listener.close()

        spare = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            spare.bind(("127.0.0.1", 0))
            closed_port = spare.getsockname()[1]
        finally:
            spare.close()
        self.assertNotIn(closed_port, status.listening_ports())


if __name__ == "__main__":
    unittest.main()

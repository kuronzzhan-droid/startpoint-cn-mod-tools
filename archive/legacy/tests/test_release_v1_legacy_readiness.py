"""Loopback-only readiness contract for transition legacy servers."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from wf_release_v1.errors import ReleaseError
from wf_release_v1.legacy_readiness import wait_legacy_ready


class _Handler(BaseHTTPRequestHandler):
    current_time: object = {
        "servertime": 123,
        "date": "2026-08-13T01:02:03.000Z",
        "isCustom": False,
    }
    capabilities_status = 404

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        if self.path == "/api/server/currentTime":
            status, value = 200, type(self).current_time
        elif self.path == "/api/server/capabilities":
            status, value = type(self).capabilities_status, {"error": "not found"}
        else:
            status, value = 500, {"error": "unexpected path"}
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class LegacyReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        _Handler.current_time = {
            "servertime": 123,
            "date": "2026-08-13T01:02:03.000Z",
            "isCustom": False,
        }
        _Handler.capabilities_status = 404
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def test_accepts_existing_current_time_contract_and_exact_capabilities_404(self) -> None:
        wait_legacy_ready(self.base_url, 1.0)

    def test_rejects_modern_capabilities_or_non_404_failures(self) -> None:
        for status in (200, 401, 500):
            with self.subTest(status=status):
                _Handler.capabilities_status = status
                with self.assertRaises(ReleaseError) as raised:
                    wait_legacy_ready(self.base_url, 1.0)
                self.assertEqual("WFREL_LEGACY_READINESS", raised.exception.code)

    def test_rejects_malformed_current_time_without_falling_back(self) -> None:
        invalid = (
            {},
            {"servertime": "123", "date": "2026-08-13", "isCustom": False},
            {"servertime": 123, "date": "2026-08-13", "isCustom": 0},
            {
                "servertime": 123,
                "date": "2026-08-13T01:02:03.000Z",
                "isCustom": False,
                "extra": True,
            },
        )
        for value in invalid:
            with self.subTest(value=value):
                _Handler.current_time = value
                with self.assertRaises(ReleaseError) as raised:
                    wait_legacy_ready(self.base_url, 1.0)
                self.assertEqual("WFREL_LEGACY_READINESS", raised.exception.code)


if __name__ == "__main__":
    unittest.main()

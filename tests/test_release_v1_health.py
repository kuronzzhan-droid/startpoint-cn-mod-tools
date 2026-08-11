"""Focused readiness polling over the shared pinned loopback transport."""

from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.errors import ReleaseError
from wf_release_v1._loopback_http import wait_health_ready


@contextmanager
def _health_server(responses: list[tuple[int, object]]):
    requests: list[str] = []
    remaining = list(responses)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback
            requests.append(self.path)
            status, value = remaining.pop(0) if remaining else responses[-1]
            raw = canonical_json_bytes(value)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/healthz", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


class HealthReadyTests(unittest.TestCase):
    def test_retries_unavailable_and_not_ready_until_v1_ready(self) -> None:
        responses = [
            (503, {"contractVersion": 1, "status": "starting"}),
            (503, {"contractVersion": 1, "status": "not-ready"}),
            (200, {"contractVersion": 1, "status": "ready", "optional": True}),
        ]
        with _health_server(responses) as (url, requests):
            wait_health_ready(url, 2.0)
        self.assertEqual(["/healthz"] * 3, requests)

    def test_contract_version_and_ready_status_are_not_aliases(self) -> None:
        for value in (
            {"responseContract": 1, "status": "ready"},
            {"contractVersion": True, "status": "ready"},
            {"contractVersion": 2, "status": "ready"},
            {"contractVersion": 1, "status": True},
            {"contractVersion": 1, "status": "starting"},
        ):
            with self.subTest(value=value), _health_server([(200, value)]) as (url, requests):
                with self.assertRaises(ReleaseError) as raised:
                    wait_health_ready(url, 1.0)
                self.assertEqual("WFREL_SCHEMA_INVALID", raised.exception.code)
                self.assertEqual(["/healthz"], requests)

    def test_rejects_non_health_endpoint_and_invalid_timeout_before_network(self) -> None:
        for url, timeout in (
            ("http://127.0.0.1:9/api/server/capabilities", 1.0),
            ("http://127.0.0.1:9/healthz", 0),
            ("http://127.0.0.1:9/healthz", True),
            ("http://127.0.0.1:9/healthz", 31),
        ):
            with self.subTest(url=url, timeout=timeout), self.assertRaises(ReleaseError) as raised:
                wait_health_ready(url, timeout)
            self.assertEqual("WFREL_SCHEMA_INVALID", raised.exception.code)

    def test_timeout_is_one_total_budget_and_reports_target_unavailable(self) -> None:
        with _health_server([(503, {"contractVersion": 1, "status": "starting"})]) as (url, requests):
            with self.assertRaises(ReleaseError) as raised:
                wait_health_ready(url, 0.08)
        self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)
        self.assertGreaterEqual(len(requests), 1)


if __name__ == "__main__":
    unittest.main()

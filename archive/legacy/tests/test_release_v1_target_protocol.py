"""Strict protocol classification for modern and legacy server targets."""

from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
import unittest

from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.errors import ReleaseError
from wf_release_v1.probe import TargetProbe
from wf_release_v1.target_protocol import TargetProtocol, detect_target_protocol


HEX_A = "a" * 64
HEX_B = "b" * 64
MODE_CAPABILITIES = [
    "mode.release-contract@1",
    "mode.hook.quest-start@1",
    "mode.hook.rush-finish@1",
    "mode.hook.rush-parties-serialized@1",
    "mode.host.base-table@1",
    "mode.host.transaction-server@1",
]
GENERAL_CAPABILITIES = sorted({"content.sync@1", *MODE_CAPABILITIES})


def _capabilities() -> dict[str, object]:
    return {
        "contractVersion": 1,
        "serverCapabilities": GENERAL_CAPABILITIES,
        "serverBundle": {"version": "1.0.1", "bundleId": f"sha256:{HEX_A}"},
        "runtime": {
            "api": 1,
            "node": "20.12.2",
            "nodeAbi": "115",
            "platform": "win32",
            "arch": "x64",
        },
        "content": {
            "source": "bundled",
            "assetVersion": "1.4.58",
            "generatorVersion": 3,
            "releaseDigest": None,
            "contentDigest": f"sha256:{HEX_B}",
            "cdnTargetVersion": "1.4.58",
            "patchVersions": [],
        },
        "modes": {
            "api": 1,
            "serverCapabilities": MODE_CAPABILITIES,
            "loaded": [],
            "modeDigest": f"sha256:{HEX_B}",
        },
        "features": {
            "patchOverlaySchema": 1,
            "modeChangesRequireRestart": True,
            "activeContentManagement": False,
        },
    }


@contextmanager
def _server(
    *,
    status: int = 200,
    value: object | None = None,
    payload: bytes | None = None,
    content_type: str = "application/json",
    location: str | None = None,
    delay: float = 0,
):
    body = payload if payload is not None else canonical_json_bytes(value)
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            requests.append(self.path)
            time.sleep(delay)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if location is not None:
                self.send_header("Location", location)
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass

        def log_message(self, _format: str, *_args: object) -> None:
            return

    service = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=service.serve_forever, daemon=True)
    worker.start()
    try:
        yield (
            f"http://127.0.0.1:{service.server_port}/api/server/capabilities",
            requests,
        )
    finally:
        service.shutdown()
        service.server_close()
        worker.join(timeout=2)


def _probe(url: str, *, timeout: float = 0.3) -> TargetProbe:
    return TargetProbe(Path("unused-server"), Path("unused-runtime"), url, timeout)


class TargetProtocolTests(unittest.TestCase):
    def test_accepts_only_a_strict_modern_capabilities_contract(self) -> None:
        with _server(value=_capabilities()) as (url, requests):
            result = detect_target_protocol(_probe(url))
        self.assertIs(TargetProtocol.CAPABILITIES_V1, result)
        self.assertEqual(["/api/server/capabilities"], requests)

    def test_exact_404_is_the_only_legacy_candidate_signal(self) -> None:
        with _server(
            status=404,
            payload=b"private legacy error page",
            content_type="text/plain",
        ) as (url, requests):
            result = detect_target_protocol(_probe(url))
        self.assertIs(TargetProtocol.LEGACY_CANDIDATE, result)
        self.assertEqual(["/api/server/capabilities"], requests)

    def test_auth_and_server_failures_never_downgrade(self) -> None:
        for status in (401, 403, 500, 503):
            with self.subTest(status=status), _server(
                status=status, value={"error": "private"}
            ) as (url, _requests), self.assertRaises(ReleaseError) as raised:
                detect_target_protocol(_probe(url))
            self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)
            self.assertEqual(status, raised.exception.details.get("status"))

    def test_redirect_malformed_and_unsupported_modern_contracts_never_downgrade(self) -> None:
        wrong_version = _capabilities()
        wrong_version["contractVersion"] = 2
        missing_content_sync = _capabilities()
        missing_content_sync["serverCapabilities"] = MODE_CAPABILITIES
        cases = (
            {"status": 302, "value": {}, "location": "/legacy"},
            {"status": 200, "payload": b"not-json"},
            {
                "status": 200,
                "payload": b'{"contractVersion":1,"contractVersion":1}',
            },
            {
                "status": 200,
                "value": _capabilities(),
                "content_type": "text/plain",
            },
            {"status": 200, "value": wrong_version},
            {"status": 200, "value": missing_content_sync},
        )
        for case in cases:
            with self.subTest(case=case), _server(**case) as (
                url,
                _requests,
            ), self.assertRaises(ReleaseError):
                detect_target_protocol(_probe(url))

    def test_timeout_and_connection_failure_never_downgrade(self) -> None:
        with _server(value=_capabilities(), delay=0.2) as (
            url,
            _requests,
        ), self.assertRaises(ReleaseError) as raised:
            detect_target_protocol(_probe(url, timeout=0.03))
        self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)

        with self.assertRaises(ReleaseError) as raised:
            detect_target_protocol(_probe("http://127.0.0.1:9/api/server/capabilities"))
        self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)

    def test_rejects_non_probe_inputs_before_network(self) -> None:
        with self.assertRaises(ReleaseError) as raised:
            detect_target_protocol(object())  # type: ignore[arg-type]
        self.assertEqual("WFREL_REQUIRE_TARGET", raised.exception.code)


if __name__ == "__main__":
    unittest.main()

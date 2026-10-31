"""Rejected writes must remain 403 without consuming unbounded attacker input."""
import io
from types import SimpleNamespace

import pytest

from test_studio_drafts import live, _request  # noqa: F401
from wf.studio import http_rejection as rejection


class Connection:
    def __init__(self):
        self.timeout = 10

    def gettimeout(self):
        return self.timeout

    def settimeout(self, value):
        self.timeout = value


def test_small_rejected_body_is_consumed_without_parsing():
    stream = io.BufferedReader(io.BytesIO(b"{}tail"))
    connection = Connection()
    rejection.discard_rejected_body(SimpleNamespace(
        headers={"Content-Length": "2"}, connection=connection, rfile=stream))
    assert stream.read() == b"tail" and connection.timeout == 10


@pytest.mark.parametrize("headers", [{}, {"Content-Length": "bad"}, {"Content-Length": "-1"},
    {"Content-Length": str(rejection.MAX_DISCARD + 1)},
    {"Content-Length": "2", "Transfer-Encoding": "chunked"}])
def test_invalid_or_large_body_is_not_drained(headers):
    rejection.discard_rejected_body(SimpleNamespace(headers=headers))  # No stream may be accessed.


def test_trickling_body_has_total_deadline(monkeypatch):
    times = iter([0, 0.1, 0.26])
    monkeypatch.setattr(rejection.time, "monotonic", lambda: next(times))
    calls = []
    connection = Connection()
    stream = SimpleNamespace(read1=lambda n: calls.append(n) or b"x")
    rejection.discard_rejected_body(SimpleNamespace(
        headers={"Content-Length": "100"}, connection=connection, rfile=stream))
    assert calls == [100] and connection.timeout == 10


def test_read_timeout_does_not_replace_rejection():
    def timeout(n):
        raise TimeoutError("sender stalled")
    connection = Connection()
    rejection.discard_rejected_body(SimpleNamespace(headers={"Content-Length": "2"},
        connection=connection, rfile=SimpleNamespace(read1=timeout)))
    assert connection.timeout == 10


@pytest.mark.parametrize("method,expected", [("POST", 403), ("PUT", 405), ("DELETE", 405)])
def test_repeated_rejected_requests_never_create_drafts(live, method, expected):
    port, _, app = live
    for _ in range(40):
        status, _ = _request(port, method, "/api/drafts/7/save", {},
                             {"Content-Type": "application/json"})
        assert status == expected
    assert not app.ops.store.root.exists()

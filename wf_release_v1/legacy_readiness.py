"""Pinned loopback readiness for the existing legacy server contract."""

from __future__ import annotations

import re
import time
from typing import Final

from ._loopback_http import _timeout, read_loopback_json
from .errors import ReleaseError


_CURRENT_TIME_PATH: Final = "/api/server/currentTime"
_CAPABILITIES_PATH: Final = "/api/server/capabilities"
_DATE: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z"
)


def _error(message: str) -> ReleaseError:
    return ReleaseError("WFREL_LEGACY_READINESS", message)


def _current_time(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {
        "servertime", "date", "isCustom",
    }:
        raise _error("legacy current-time response keys are invalid")
    server_time = value["servertime"]
    date = value["date"]
    custom = value["isCustom"]
    if (
        type(server_time) is not int
        or server_time < 0
        or server_time > (1 << 53) - 1
        or not isinstance(date, str)
        or _DATE.fullmatch(date) is None
        or type(custom) is not bool
    ):
        raise _error("legacy current-time response is invalid")


def _read_current_time(base_url: str, deadline: float) -> None:
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _error("legacy server did not become ready")
        try:
            value = read_loopback_json(
                base_url + _CURRENT_TIME_PATH,
                remaining,
                expected_path=_CURRENT_TIME_PATH,
                label="legacyCurrentTime",
            )
        except ReleaseError as error:
            if (
                error.code == "WFREL_REQUIRE_TARGET"
                and error.details.get("retryable") is True
            ):
                time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
                continue
            raise _error("legacy current-time endpoint is invalid") from error
        _current_time(value)
        return


def _require_capabilities_404(base_url: str, deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _error("legacy readiness budget expired")
    try:
        read_loopback_json(
            base_url + _CAPABILITIES_PATH,
            remaining,
            expected_path=_CAPABILITIES_PATH,
            label="legacyCapabilities",
        )
    except ReleaseError as error:
        if (
            error.code == "WFREL_REQUIRE_TARGET"
            and error.details.get("status") == 404
        ):
            return
        raise _error("legacy capabilities endpoint did not return 404") from error
    raise _error("target exposes the modern capabilities contract")


def wait_legacy_ready(base_url: str, timeout_seconds: float) -> None:
    """Require the existing current-time contract and capabilities absence."""
    if not isinstance(base_url, str):
        raise _error("legacy server base URL is invalid")
    total = _timeout(timeout_seconds)
    deadline = time.monotonic() + total
    _read_current_time(base_url, deadline)
    _require_capabilities_404(base_url, deadline)


__all__ = ["wait_legacy_ready"]

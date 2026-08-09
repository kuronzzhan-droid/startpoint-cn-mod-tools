"""Stable, safe errors exposed by the release-v1 tools."""

from __future__ import annotations

from collections.abc import Mapping


class ReleaseError(RuntimeError):
    """An expected release-v1 failure with a stable machine-readable code."""

    code: str
    message: str
    details: Mapping[str, object]

    def __init__(
        self,
        code: str,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = dict(details or {})
        super().__init__(f"{code}: {message}")

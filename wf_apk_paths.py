from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def resolve_explicit_apk(
    environment: Mapping[str, str] = os.environ,
) -> Path | None:
    """Return a validated explicit APK/bundle source, or None when unset."""
    raw = environment.get("WF_APK")
    if raw is None:
        return None
    if not raw.strip():
        raise ValueError("WF_APK must be a non-empty path")

    configured = Path(raw).expanduser()
    if not configured.is_absolute():
        raise ValueError(f"WF_APK must be an absolute path: {raw}")
    configured = configured.resolve()
    if not configured.is_file():
        raise ValueError(f"WF_APK is not an existing file: {configured}")
    return configured

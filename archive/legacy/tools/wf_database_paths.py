from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def resolve_database_path(
    environment: Mapping[str, str] = os.environ,
    *,
    server_root: Path | str,
) -> Path:
    """Resolve the player database without coupling tools to the server checkout."""
    raw = environment.get("WF_DATABASE_DIR")
    if raw is None:
        return Path(server_root).resolve() / ".database" / "wdfp_data.db"
    if not raw.strip():
        raise ValueError("WF_DATABASE_DIR must be a non-empty path")

    configured = Path(raw).expanduser()
    if not configured.is_absolute():
        raise ValueError(f"WF_DATABASE_DIR must be an absolute path: {raw}")
    configured = configured.resolve()
    if not configured.is_dir():
        raise ValueError(
            f"WF_DATABASE_DIR is not an existing directory: {configured}"
        )
    return configured / "wdfp_data.db"

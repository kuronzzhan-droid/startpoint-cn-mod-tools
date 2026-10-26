"""Explicit, read-only source paths for optional cross-repository integrations."""

import os
from pathlib import Path
import unittest


def client_patch_path(relative: str) -> Path:
    configured = os.environ.get("WF_CLIENT_PATCH_DIR")
    if configured is not None:
        root = Path(configured).expanduser()
    elif os.environ.get("WF_SERVER_DIR"):
        root = Path(os.environ["WF_SERVER_DIR"]) / "client-patch"
    else:
        root = Path(__file__).resolve().parents[1] / "client-patch"
    return root / relative


def require_external_source(path: Path) -> Path:
    if not path.is_file():
        raise unittest.SkipTest(
            "external client-patch integration source unavailable; "
            f"set WF_CLIENT_PATCH_DIR to run: {path.name}"
        )
    return path


def server_source(relative: str) -> Path:
    root = Path(os.environ.get("WF_SERVER_DIR", Path(__file__).resolve().parents[1] / "external-server"))
    path = root / relative
    if not path.is_file():
        raise unittest.SkipTest(
            "external server integration source unavailable; "
            f"set WF_SERVER_DIR to run: {relative}"
        )
    return path


def require_live_store() -> Path:
    import wf_mod_tool as core

    store = core.resolve_active_store(Path(__file__).resolve().parents[1])
    if store is None or not Path(store).is_dir():
        raise unittest.SkipTest(
            "read-only live-data integration requires a configured WF_TARGET_STORE"
        )
    return Path(store)

"""Shared, lazy defaults for the two studio entry points."""
from pathlib import Path

from wf.paths import configured_path


def server_directory(explicit=None):
    """An explicit CLI value wins; an unconfigured mirror stays optional."""
    return Path(explicit) if explicit is not None else configured_path("server")

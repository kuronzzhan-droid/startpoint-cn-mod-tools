"""Deterministic identity for the builder facade and its explicit source sections."""
from __future__ import annotations

import hashlib
from pathlib import Path


def source_digest(entrypoint: Path, sections: tuple[str, ...]) -> str:
    """Hash exact names and bytes in declared load order, without source rewriting."""
    digest = hashlib.sha256()
    for name in (entrypoint.name, *sections):
        encoded = name.encode("utf-8")
        content = entrypoint.with_name(name).read_bytes()
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()

"""Stable asset inventory fingerprints, including the current draft revision."""
from __future__ import annotations

import hashlib
import json


def stamp_assets(result: dict, *, source_version: str, draft: dict | None) -> dict:
    """Return a new inventory with a content identity suitable for cache keys.

    Source inventories are immutable during a Studio process. Per-item hashes
    distinguish equal-size media; draft content distinguishes changed candidates,
    including a discarded/recreated draft whose revision counter restarted.
    """
    basis = {"sourceVersion": source_version, "assets": result, "draft": draft}
    encoded = json.dumps(basis, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    version = hashlib.sha256(encoded).hexdigest()
    return {**result, "sourceVersion": source_version, "draftRevision": draft.get("revision") if draft else None,
            "assetsVersion": version, "etag": f'"{version}"'}

"""Merge the compatibility version profile into explicit machine paths."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from wf.paths import configured_path, profile_data, version_entry, version_id

PATH_FIELDS = {"store": "store", "cdndata": "cdndata", "fallback": "source_store",
               "cdn_dir": "cdn_dir", "server_dir": "server"}


def merge_profile(
    legacy: dict, resolve_legacy: Callable[[str], Path], profile_id: str | None = None,
) -> dict | None:
    modern, _ = profile_data()
    selected = version_id(profile_id)
    modern_id, modern_entry = version_entry(modern, selected)
    legacy_id, legacy_entry = version_entry(legacy, selected)
    if modern_entry and legacy_entry and modern_id != legacy_id:
        raise ValueError("Conflicting active profiles in profiles/local.json and legacy profiles.json")
    if modern_entry.get("res_version") and legacy_entry.get("res_version") and (
        modern_entry["res_version"] != legacy_entry["res_version"]
    ):
        raise ValueError("Conflicting res_version in profiles/local.json and legacy profiles.json")
    identifier = selected or modern_id or legacy_id or "local"
    result = {"id": identifier, "label": modern_entry.get("label", legacy_entry.get("label", identifier)),
              "res_version": modern_entry.get("res_version", legacy_entry.get("res_version", ""))}
    for field, key in PATH_FIELDS.items():
        current = configured_path(key, selected)
        raw = legacy_entry.get(field)
        previous = None
        if raw is not None:
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError(f"profile {field} must be a non-empty path: {identifier}")
            previous = resolve_legacy(raw)
        if current is not None and previous is not None and current.resolve() != previous.resolve():
            raise ValueError(
                f"Conflicting {field} in legacy profiles.json and modern configuration; "
                "migrate or remove the legacy value"
            )
        result[field] = current if current is not None else previous
    return result if modern_entry or legacy_entry or any(result[k] is not None for k in PATH_FIELDS) else None

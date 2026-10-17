"""Machine paths: environment > local profile; external inputs have no guesses.

Resolving paths never creates files. Relative configured paths use WF_ROOT;
without a root, they stay in work/external inside this checkout.
"""
from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
_LOCAL_DEFAULTS = {"output": "work/m0", "pathlist": "WF_PATHLIST_recovered.txt"}
_ENV_ALIASES = {"store": "WF_TARGET_STORE", "server": "WF_SERVER_DIR"}
_PROFILE_FIELDS = {"store": "store", "server": "server_dir", "cdn_dir": "cdn_dir",
                   "cdndata": "cdndata", "source_store": "fallback"}


def _text(value: object, label: str) -> str:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError(f"{label} must be a non-empty path")
    return str(value)


def _expand(value: str | Path) -> Path:
    return Path(os.path.expandvars(str(value))).expanduser()


def profile_data() -> tuple[dict, Path]:
    """Read only WF_PATHS_PROFILE (or profiles/local.json), never WF_PROFILE."""
    explicit = "WF_PATHS_PROFILE" in os.environ
    raw = os.environ.get("WF_PATHS_PROFILE", REPOSITORY / "profiles/local.json")
    location = _expand(_text(raw, "WF_PATHS_PROFILE"))
    if not location.is_absolute():
        location = REPOSITORY / location
    if not location.exists():
        if explicit:
            raise ValueError(f"WF_PATHS_PROFILE does not exist: {location}")
        return {}, location.parent
    data = json.loads(location.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Path profile must be a JSON object: {location}")
    for field in ("paths", "profiles"):
        if field in data and not isinstance(data[field], dict):
            raise ValueError(f"{field} must be an object in {location}")
    return data, location.parent


def version_id(profile_id: str | None = None) -> str | None:
    """WF_PROFILE selects a version ID; JSON filenames use WF_PATHS_PROFILE."""
    selected = profile_id if profile_id is not None else os.environ.get("WF_PROFILE")
    if selected is not None:
        if not isinstance(selected, str) or not selected.strip():
            raise ValueError("WF_PROFILE must be a non-empty version profile ID")
        if selected.lower().endswith(".json") or "/" in selected or "\\" in selected:
            raise ValueError("WF_PROFILE is a version ID; use WF_PATHS_PROFILE for a JSON path")
    return selected


def version_entry(data: dict, profile_id: str | None = None) -> tuple[str | None, dict]:
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("profiles must be an object")
    selected = version_id(profile_id) or data.get("active")
    if selected is not None and (not isinstance(selected, str) or not selected.strip()):
        raise ValueError("active must be a non-empty version profile ID")
    if selected is not None and profiles and selected not in profiles:
        raise ValueError(f"Unknown version profile: {selected}")
    entry = profiles.get(selected, {})
    if not isinstance(entry, dict):
        raise ValueError(f"profile must be an object: {selected}")
    return selected, entry


def environment_path(name: str) -> Path | None:
    key = name.lower()
    canonical, alias = "WF_" + key.upper(), _ENV_ALIASES.get(key)
    present = [var for var in (canonical, alias) if var and var in os.environ]
    if alias in present:
        warnings.warn(f"{alias} is deprecated; use {canonical}", UserWarning, stacklevel=2)
    values = []
    for variable in present:
        value = _expand(_text(os.environ[variable], variable))
        if not value.is_absolute():
            raise ValueError(f"{variable} must be an absolute path: {value}")
        values.append(value.resolve())
    if len(values) == 2 and values[0] != values[1]:
        raise ValueError(f"Conflicting {canonical} and {alias}; keep only {canonical}")
    return values[0] if values else None


def root_path(*parts: str | Path) -> Path:
    """Resolve the explicit root, or an isolated local path for offline imports."""
    config, parent = profile_data()
    raw = os.environ.get("WF_ROOT", config.get("wf_root", config.get("WF_ROOT")))
    if raw is None:
        base = REPOSITORY / "work/external"
    else:
        base = _expand(_text(raw, "WF_ROOT / wf_root"))
        if not base.is_absolute():
            base = parent / base
    return base.resolve().joinpath(*parts)


def configured_path(name: str, profile_id: str | None = None) -> Path | None:
    """Resolve modern configuration only; legacy conflict checks live in core."""
    key = name.lower()
    environment = environment_path(key)
    if environment is not None:
        return environment
    config, _ = profile_data()
    _, entry = version_entry(config, profile_id)
    field = _PROFILE_FIELDS.get(key, key)
    raw = config.get("paths", {}).get(key, entry.get(field, config.get(key)))
    if raw is None:
        return None
    value = _expand(_text(raw, f"profile {key}"))
    return (value if value.is_absolute() else root_path() / value).resolve()


def path(name: str, *parts: str | Path) -> Path:
    """Use the same store/server/CDN configuration as the legacy core API."""
    key = name.lower()
    if key in {"root", "wf_root"}:
        return root_path(*parts)
    if key in _PROFILE_FIELDS:
        import wf_mod_tool as core
        profile = core.resolve_profile()
        base = getattr(profile, _PROFILE_FIELDS[key], None)
    else:
        base = configured_path(key)
    if base is None and key in _LOCAL_DEFAULTS:
        base = REPOSITORY / _LOCAL_DEFAULTS[key]
    if base is None:
        raise KeyError(f"Configure path {key!r} in profiles/local.json or WF_{key.upper()}")
    return base.joinpath(*parts)


def configured(name: str) -> bool:
    """Null means unconfigured; malformed values still raise an error."""
    return configured_path(name) is not None

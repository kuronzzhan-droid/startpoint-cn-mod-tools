"""Resolve machine-local paths without writing to the configured locations.

Environment variables override profiles/local.json. Relative profile values are
relative to WF_ROOT; a relative WF_ROOT is relative to the profile directory.
Nothing is created by this module. Outputs default inside this checkout.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
_DEFAULTS = {
    "store": "wf-store",
    "kulo": "startpoint-cn-kulo",
    "runtimes": "runtimes",
    "out": "out",
    "server": "startpoint-cn",
    "store131": "out/kulo-patch-toolkit/store131/production/upload",
    "asr_model": "models/faster-whisper-large-v3",
}
_LOCAL_DEFAULTS = {
    "output": "work/m0",
    "pathlist": "WF_PATHLIST_recovered.txt",
}


def _profile() -> tuple[dict, Path]:
    # WF_PROFILE historically selects a named game-version profile. Accept a
    # JSON filename for compatibility, but never interpret an ID such as 'cn'
    # as a path profile.
    legacy = os.environ.get("WF_PROFILE", "")
    default = legacy if legacy.lower().endswith(".json") else REPOSITORY / "profiles/local.json"
    location = Path(os.environ.get("WF_PATHS_PROFILE", default))
    if not location.is_absolute():
        location = REPOSITORY / location
    if not location.exists():
        return {}, location.parent
    data = json.loads(location.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Path profile must be a JSON object: {location}")
    return data, location.parent


def _expand(value: str | Path) -> Path:
    return Path(os.path.expandvars(str(value))).expanduser()


def root_path(*parts: str | Path) -> Path:
    """Get the explicitly configured data root (isolated local default)."""
    config, parent = _profile()
    raw = os.environ.get("WF_ROOT", config.get("wf_root", config.get("WF_ROOT")))
    if raw is None:
        base = REPOSITORY / "work/external"
    else:
        base = _expand(raw)
        if not base.is_absolute():
            base = parent / base
    return base.joinpath(*parts)


def path(name: str, *parts: str | Path) -> Path:
    """Resolve WF_<NAME>, then profile paths/name, then documented defaults."""
    if name.lower() in {"root", "wf_root"}:
        return root_path(*parts)
    key = name.lower()
    config, _ = _profile()
    mappings = config.get("paths", {})
    raw = os.environ.get("WF_" + key.upper(), mappings.get(key, config.get(key)))
    if raw is None:
        if key in _LOCAL_DEFAULTS:
            return (REPOSITORY / _LOCAL_DEFAULTS[key]).joinpath(*parts)
        if key not in _DEFAULTS:
            raise KeyError(f"Configure path {key!r} in profiles/local.json or WF_{key.upper()}")
        raw = _DEFAULTS[key]
    base = _expand(raw)
    if not base.is_absolute():
        base = root_path() / base
    return base.joinpath(*parts)


def configured(name: str) -> bool:
    """Whether a named location is explicit, rather than a discovery default."""
    config, _ = _profile()
    key = name.lower()
    return ("WF_" + key.upper() in os.environ
            or key in config.get("paths", {}) or key in config)

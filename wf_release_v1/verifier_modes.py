"""Static receiver checks for one sealed Mode component."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Final

from .canonical import canonical_json_bytes, load_json_strict_bytes
from .errors import ReleaseError
from .schema import ReleaseManifest, ReleaseRequirements


_DIGEST: Final = re.compile(r"[0-9a-f]{64}")
_MODE_FILE: Final = re.compile(r"[a-z0-9][a-z0-9._-]*\.mjs")
_RELEASE_CAPABILITY: Final = "mode.release-contract@1"


def _invalid(message: str) -> ReleaseError:
    return ReleaseError(
        "WFREL_COMPONENT_INVALID",
        message,
        {"label": "modes"},
    )


def _object(value: object, keys: frozenset[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or frozenset(value) != keys:
        raise _invalid(f"{label} keys do not match the Mode receiver contract")
    return value


def _read_json(path: Path, label: str) -> tuple[dict[str, object], bytes]:
    try:
        raw = path.read_bytes()
    except OSError:
        raise _invalid(f"{label} is unavailable") from None
    value = load_json_strict_bytes(raw, label=label)
    if not isinstance(value, dict) or raw != canonical_json_bytes(value):
        raise _invalid(f"{label} is not canonical")
    return value, raw


def verify_mode_component(
    release: ReleaseManifest,
    requirements: ReleaseRequirements,
    staged: dict[str, Path],
) -> None:
    """Verify static Mode bytes without importing untrusted module code."""
    if release.expected_state.mode_digest is None:
        raise _invalid("Mode expected state is missing its digest")
    if _RELEASE_CAPABILITY not in requirements.server_capabilities:
        raise _invalid("Mode release contract capability is not required")
    mode_paths = tuple(
        item.path.removeprefix("modes/")
        for item in release.files
        if item.path.startswith("modes/")
    )
    if not mode_paths or len(mode_paths) == len(release.files):
        raise _invalid("combined Release must contain both content and Mode bytes")
    required_name = "modes-required.json"
    allowlist_name = "modes-allowlist.json"
    if required_name not in mode_paths or allowlist_name not in mode_paths:
        raise _invalid("Mode control files are incomplete")

    allowlist, _raw = _read_json(
        staged[f"modes/{allowlist_name}"],
        allowlist_name,
    )
    if not allowlist or any(
        not isinstance(name, str)
        or _MODE_FILE.fullmatch(name) is None
        or not isinstance(digest, str)
        or _DIGEST.fullmatch(digest) is None
        for name, digest in allowlist.items()
    ):
        raise _invalid("Mode allowlist is invalid")
    module_names = tuple(sorted(
        (path for path in mode_paths if _MODE_FILE.fullmatch(path) is not None),
        key=lambda item: item.encode("utf-8"),
    ))
    if module_names != tuple(allowlist):
        raise _invalid("Mode allowlist does not exactly cover module files")
    for name in module_names:
        try:
            digest = hashlib.sha256(staged[f"modes/{name}"].read_bytes()).hexdigest()
        except OSError:
            raise _invalid("Mode module is unavailable") from None
        if digest != allowlist[name]:
            raise _invalid("Mode allowlist digest disagrees with module bytes")

    required, _raw = _read_json(
        staged[f"modes/{required_name}"],
        required_name,
    )
    required = _object(required, frozenset({"schemaVersion", "required"}), required_name)
    required_files = required["required"]
    if (
        type(required["schemaVersion"]) is not int
        or required["schemaVersion"] != 1
        or not isinstance(required_files, list)
        or any(not isinstance(item, str) for item in required_files)
        or len(set(required_files)) != len(required_files)
        or tuple(required_files) != tuple(sorted(required_files, key=lambda item: item.encode("utf-8")))
        or not set(required_files).issubset(allowlist)
    ):
        raise _invalid("required Mode list is invalid")

    control = {allowlist_name, required_name, *module_names}
    for relative in mode_paths:
        if relative in control:
            continue
        parts = PurePosixPath(relative).parts
        if len(parts) < 2 or not parts[0].endswith(".resources"):
            raise _invalid("Mode private resource is outside a module resource root")
        owner = parts[0].removesuffix(".resources") + ".mjs"
        if owner not in allowlist:
            raise _invalid("Mode private resource has no allowlisted module owner")


__all__ = ["verify_mode_component"]

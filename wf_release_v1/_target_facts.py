"""One strict path-free wire shape for verified target facts."""

from __future__ import annotations

import re
from typing import Final

from .errors import ReleaseError
from .probe import TargetFacts


_KEYS: Final = frozenset({
    "arch", "bundleId", "capabilities", "cdnTargetVersion", "contentDigest",
    "dependencyLock", "modeDigest", "nodeAbi", "nodeVersion", "patchOverlaySchema",
    "platform", "releaseDigest", "runtimeApi", "runtimeId", "serverVersion",
})
_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}")
_SEMVER: Final = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
_DOTTED: Final = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+")
_CAPABILITY: Final = re.compile(r"[a-z0-9][a-z0-9._-]*@[1-9][0-9]*")
_PLATFORM: Final = re.compile(r"[a-z][a-z0-9-]*")
_ARCH: Final = re.compile(r"[a-z0-9_-]+")


def _invalid(message: str) -> ReleaseError:
    return ReleaseError("WFREL_STATE_INVALID", message)


def _string(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise _invalid(f"baseline target {label} is invalid")
    return value


def target_facts_from_wire(value: object) -> TargetFacts:
    if not isinstance(value, dict) or frozenset(value) != _KEYS:
        raise _invalid("baseline target fact keys do not match the contract")
    capabilities = value["capabilities"]
    if not isinstance(capabilities, list) or not capabilities or any(
        not isinstance(item, str) or _CAPABILITY.fullmatch(item) is None
        for item in capabilities
    ) or capabilities != sorted(set(capabilities)):
        raise _invalid("baseline target capabilities are invalid")
    for label in ("runtimeApi", "patchOverlaySchema"):
        if type(value[label]) is not int or value[label] < 1:  # type: ignore[operator]
            raise _invalid(f"baseline target {label} is invalid")
    node_abi = value["nodeAbi"]
    if not isinstance(node_abi, str) or not node_abi.isdecimal():
        raise _invalid("baseline target nodeAbi is invalid")
    raw_release_digest = value["releaseDigest"]
    release_digest = None if raw_release_digest is None else _string(
        raw_release_digest, _DIGEST, "releaseDigest"
    )
    return TargetFacts(
        bundle_id=_string(value["bundleId"], _DIGEST, "bundleId"),
        server_version=_string(value["serverVersion"], _SEMVER, "serverVersion"),
        runtime_id=_string(value["runtimeId"], _DIGEST, "runtimeId"),
        runtime_api=value["runtimeApi"],  # type: ignore[arg-type]
        dependency_lock=_string(value["dependencyLock"], _DIGEST, "dependencyLock"),
        node_version=_string(value["nodeVersion"], _SEMVER, "nodeVersion"),
        node_abi=node_abi,
        platform=_string(value["platform"], _PLATFORM, "platform"),
        arch=_string(value["arch"], _ARCH, "arch"),
        capabilities=tuple(capabilities),
        content_digest=_string(value["contentDigest"], _DIGEST, "contentDigest"),
        cdn_target_version=_string(value["cdnTargetVersion"], _DOTTED, "cdnTargetVersion"),
        mode_digest=_string(value["modeDigest"], _DIGEST, "modeDigest"),
        patch_overlay_schema=value["patchOverlaySchema"],  # type: ignore[arg-type]
        release_digest=release_digest,
    )


def target_facts_to_wire(facts: TargetFacts) -> dict[str, object]:
    if not isinstance(facts, TargetFacts):
        raise _invalid("baseline target facts are invalid")
    value: dict[str, object] = {
        "arch": facts.arch,
        "bundleId": facts.bundle_id,
        "capabilities": list(facts.capabilities),
        "cdnTargetVersion": facts.cdn_target_version,
        "contentDigest": facts.content_digest,
        "dependencyLock": facts.dependency_lock,
        "modeDigest": facts.mode_digest,
        "nodeAbi": facts.node_abi,
        "nodeVersion": facts.node_version,
        "patchOverlaySchema": facts.patch_overlay_schema,
        "platform": facts.platform,
        "releaseDigest": facts.release_digest,
        "runtimeApi": facts.runtime_api,
        "runtimeId": facts.runtime_id,
        "serverVersion": facts.server_version,
    }
    if target_facts_from_wire(value) != facts:
        raise _invalid("baseline target facts are not canonical")
    return value

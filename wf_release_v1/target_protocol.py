"""Read-only classification of one managed target's server protocol."""

from __future__ import annotations

from enum import Enum

from .errors import ReleaseError
from .probe import TargetProbe


class TargetProtocol(str, Enum):
    """A proven modern contract or a candidate for later legacy inspection."""

    CAPABILITIES_V1 = "capabilities-v1"
    LEGACY_CANDIDATE = "legacy-candidate"


def _invalid(message: str) -> ReleaseError:
    return ReleaseError("WFREL_REQUIRE_TARGET", message, {"label": "targetProtocol"})


def detect_target_protocol(probe: TargetProbe) -> TargetProtocol:
    """Classify one endpoint; only an exact capabilities 404 permits fallback."""
    if not isinstance(probe, TargetProbe):
        raise _invalid("target protocol probe is invalid")
    try:
        probe.validate_live_capabilities()
    except ReleaseError as error:
        if (
            error.code == "WFREL_REQUIRE_TARGET"
            and error.details.get("label") == "capabilities"
            and error.details.get("status") == 404
        ):
            return TargetProtocol.LEGACY_CANDIDATE
        raise
    return TargetProtocol.CAPABILITIES_V1


__all__ = ["TargetProtocol", "detect_target_protocol"]

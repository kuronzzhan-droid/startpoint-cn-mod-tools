"""Path-free read-only capability level for one managed target."""

from __future__ import annotations

from dataclasses import dataclass, field
from ._target_facts import target_facts_to_wire
from .errors import ReleaseError
from .legacy_target import (
    LegacyTargetFacts,
    LegacyProcessStatus,
    inspect_legacy_target,
)
from .probe import TargetFacts
from .target import ManagedTarget
from .target_protocol import TargetProtocol, detect_target_protocol


@dataclass(frozen=True)
class TargetCapability:
    level: str
    target_protocol: str
    installable: bool
    blockers: tuple[str, ...]
    legacy_chain_tail: str | None = None
    writes_live: bool = False
    _modern_facts: TargetFacts | None = field(default=None, repr=False, compare=False)
    _legacy_facts: LegacyTargetFacts | None = field(default=None, repr=False, compare=False)

    def to_wire(self) -> dict[str, object]:
        value: dict[str, object] = {
            "blockers": list(self.blockers),
            "installable": self.installable,
            "level": self.level,
            "probeVersion": 2,
            "targetProtocol": self.target_protocol,
            "writesLive": self.writes_live,
        }
        if self._modern_facts is not None:
            value.update(target_facts_to_wire(self._modern_facts))
        if self.legacy_chain_tail is not None:
            value["legacyChainTail"] = self.legacy_chain_tail
        return value


def _modern_facts(probe: object) -> TargetFacts:
    return probe.run()  # type: ignore[attr-defined,no-any-return]


def inspect_target_capability(
    target: ManagedTarget,
    platform: object,
) -> TargetCapability:
    """Classify modern/transition/legacy without writing target state."""
    probe = target.target_probe()
    protocol = detect_target_protocol(probe)
    if protocol is TargetProtocol.CAPABILITIES_V1:
        facts = _modern_facts(probe)
        return TargetCapability(
            "modern",
            protocol.value,
            True,
            (),
            _modern_facts=facts,
        )
    try:
        reader = platform() if callable(platform) else platform
        legacy = inspect_legacy_target(target, reader)  # type: ignore[arg-type]
    except ReleaseError as error:
        return TargetCapability("legacy", "legacy", False, (error.code,))
    owned = legacy.process_status is LegacyProcessStatus.OWNED_RUNNING
    return TargetCapability(
        "transition" if owned else "legacy",
        "legacy",
        owned,
        legacy.preview_only_reasons,
        legacy_chain_tail=legacy.chain_tail,
        _legacy_facts=legacy,
    )


__all__ = ["TargetCapability", "inspect_target_capability"]

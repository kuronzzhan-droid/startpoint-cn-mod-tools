"""Explicit restart of one previously bootstrapped managed target."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import secrets

from ._loopback_http import (
    _timeout as _validated_health_timeout,
    require_local_address,
    require_tcp_endpoint_unbound,
    wait_health_ready,
)
from ._platform_state import ManagedProcess
from ._receipt_contract import new_operation_id
from ._target_facts import target_facts_to_wire
from .errors import ReleaseError
from .platform import LaunchEnvironment, PlatformAdapter
from .probe import TargetFacts
from .receipts import (
    load_active_state,
    load_previous_state,
    operation_reservation,
)
from .target import ManagedTarget
from .target_capability import inspect_target_capability


@dataclass(frozen=True)
class ResumeResult:
    outcome: str
    operation_id: str
    target_facts: TargetFacts

    def to_wire(self) -> dict[str, object]:
        return {
            **target_facts_to_wire(self.target_facts),
            "operationId": self.operation_id,
            "outcome": self.outcome,
            "targetProtocol": "capabilities-v1",
        }


def _environment(target: ManagedTarget) -> LaunchEnvironment:
    return LaunchEnvironment(
        data_root=target.data_root,
        cdn_root=target.cdn_root,
        modes_root=target.modes_root,
        listen_host=target.http_bind_host,
        listen_port=target.server_port,
        public_host=target.public_host,
        session_host=target.session_bind_host,
        session_port=target.session_port,
        session_public_host=target.session_public_host,
    )


def _modern_facts(target: ManagedTarget, platform: PlatformAdapter) -> TargetFacts:
    capability = inspect_target_capability(target, platform)
    if (
        capability.level != "modern"
        or capability.target_protocol != "capabilities-v1"
        or capability._modern_facts is None
    ):
        raise ReleaseError(
            "WFREL_REQUIRE_TARGET",
            "managed target does not expose modern capabilities",
            {"label": "targetProtocol"},
        )
    target_facts_to_wire(capability._modern_facts)
    return capability._modern_facts


def _wait_for_owned_health(
    target: ManagedTarget,
    environment: LaunchEnvironment,
    process: ManagedProcess,
    timeout: float,
) -> None:
    wait_health_ready(
        target.health_url,
        timeout,
        expected_operation_id=process.operation_id,
        expected_pid=process.pid,
        expected_bindings=environment.health_bindings(),
    )


def _cleanup_started(
    platform: PlatformAdapter,
    started: ManagedProcess,
    health_timeout: float,
    error: BaseException,
) -> None:
    try:
        if platform.wait_exited(started, 0.0):
            return
        platform.stop_owned(started, health_timeout)
    except (ReleaseError, OSError):
        raise ReleaseError(
            "WFREL_RECOVERY_FAILED",
            "resume failed and its managed process could not be stopped",
        ) from error


def resume_target(
    target: ManagedTarget,
    platform: PlatformAdapter,
    *,
    health_timeout: float = 30.0,
) -> ResumeResult:
    """Verify a running target or restart its stopped managed service."""
    if not isinstance(target, ManagedTarget):
        raise ReleaseError("WFREL_REQUIRE_TARGET", "resume target is invalid")
    health_timeout = _validated_health_timeout(health_timeout)
    operation_id = new_operation_id(
        datetime.now(timezone.utc),
        secrets.token_bytes(16),
    )

    started = None
    accepted_started = False
    try:
        with operation_reservation(target.state_root, operation_id):
            load_active_state(target.state_root)
            load_previous_state(target.state_root)
            current = platform.current_process()
            environment = _environment(target)

            if current is not None:
                _wait_for_owned_health(target, environment, current, health_timeout)
                facts = _modern_facts(target, platform)
                if platform.current_process() != current:
                    raise ReleaseError(
                        "WFREL_PROCESS_IDENTITY",
                        "managed process identity changed during resume verification",
                    )
                result = ResumeResult("noop", operation_id, facts)
            else:
                require_local_address(target.public_host, label="network.publicHost")
                require_tcp_endpoint_unbound(
                    target.http_bind_host,
                    target.server_port,
                    label="http",
                )
                require_tcp_endpoint_unbound(
                    target.session_bind_host,
                    target.session_port,
                    label="session",
                )
                launch = target.launch_spec()
                try:
                    started = platform.start_server(launch, environment, operation_id)
                    _wait_for_owned_health(target, environment, started, health_timeout)
                    facts = _modern_facts(target, platform)
                    if platform.current_process() != started:
                        raise ReleaseError(
                            "WFREL_PROCESS_IDENTITY",
                            "resume process identity changed before acceptance",
                        )
                    result = ResumeResult("succeeded", operation_id, facts)
                    accepted_started = True
                except BaseException as error:
                    if started is not None:
                        _cleanup_started(platform, started, health_timeout, error)
                    raise
    except BaseException as error:
        if accepted_started:
            raise ReleaseError(
                "WFREL_RECOVERY_FAILED",
                "resume succeeded but its operation reservation could not be released",
            ) from error
        raise
    return result


__all__ = ["ResumeResult", "resume_target"]

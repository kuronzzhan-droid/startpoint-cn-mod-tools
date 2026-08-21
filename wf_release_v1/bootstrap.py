"""Explicit first bootstrap for one stopped modern managed target."""

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
from ._receipt_contract import new_operation_id
from ._target_facts import target_facts_to_wire
from .compatibility import ActiveState
from .errors import ReleaseError
from .platform import LaunchEnvironment, PlatformAdapter
from .probe import TargetFacts
from .receipts import commit_active_state, operation_reservation
from .target import ManagedTarget


@dataclass(frozen=True)
class BootstrapResult:
    outcome: str
    target_facts: TargetFacts


def _state_conflict(message: str) -> ReleaseError:
    return ReleaseError("WFREL_STATE_CONFLICT", message)


def _empty_state(target: ManagedTarget) -> ActiveState:
    compatibility = target.compatibility
    return ActiveState(
        client_version=compatibility.client_version,
        resource_baseline=compatibility.resource_baseline,
        client_patch_profile=compatibility.client_patch_profile,
        releases=(),
        known_release_ids=(),
    )


def bootstrap_target(
    target: ManagedTarget,
    platform: PlatformAdapter,
    *,
    health_timeout: float = 30.0,
) -> BootstrapResult:
    """Prepare, accept, and commit a previously unmanaged stopped baseline."""
    if not isinstance(target, ManagedTarget):
        raise ReleaseError("WFREL_REQUIRE_TARGET", "bootstrap target is invalid")
    health_timeout = _validated_health_timeout(health_timeout)

    active_path = target.state_root / "active.json"
    previous_path = target.state_root / "previous.json"
    operation_id = new_operation_id(
        datetime.now(timezone.utc),
        secrets.token_bytes(16),
    )
    with operation_reservation(target.state_root, operation_id):
        if (
            active_path.exists()
            or active_path.is_symlink()
            or previous_path.exists()
            or previous_path.is_symlink()
        ):
            raise _state_conflict("managed target state already exists")
        if platform.current_process() is not None:
            raise _state_conflict("managed process exists without active target state")

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
        environment = LaunchEnvironment(
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
        started = None
        try:
            platform.prepare_content(launch, environment)
            started = platform.start_server(launch, environment, operation_id)
            wait_health_ready(
                target.health_url,
                health_timeout,
                expected_operation_id=operation_id,
                expected_pid=started.pid,
                expected_bindings=environment.health_bindings(),
            )
            facts = target.target_probe(timeout_seconds=health_timeout).run()
            if facts.cdn_target_version != target.compatibility.resource_baseline:
                raise ReleaseError(
                    "WFREL_REQUIRE_TARGET",
                    "live content version disagrees with the declared resource baseline",
                    {"label": "content.resourceBaseline"},
                )
            target_facts_to_wire(facts)
            if platform.current_process() != started:
                raise ReleaseError(
                    "WFREL_PROCESS_IDENTITY",
                    "bootstrap process identity changed before commit",
                )
            baseline = _empty_state(target)
            commit_active_state(target.state_root, previous=baseline, active=baseline)
            result = BootstrapResult("succeeded", facts)
        except BaseException as error:
            if started is not None:
                try:
                    current = platform.current_process()
                    if current is None:
                        pass
                    elif current == started:
                        platform.stop_owned(started, health_timeout)
                    else:
                        raise ReleaseError(
                            "WFREL_RECOVERY_FAILED",
                            "bootstrap process identity drifted during failure recovery",
                        )
                except (ReleaseError, OSError):
                    raise ReleaseError(
                        "WFREL_RECOVERY_FAILED",
                        "bootstrap failed and its managed process could not be stopped",
                    ) from error
            raise
    return result


__all__ = ["BootstrapResult", "bootstrap_target"]
